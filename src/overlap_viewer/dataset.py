"""The dataset side of the viewer: metadata, instance catalogue, per-well overlaps.

``DatasetInfo`` reads what the 3W ``dataset.ini`` states about the data; the
catalogue lists every real instance with the facts the overview needs (well,
fault folder, time span, reach) and is cached on disk, since gathering them
means opening every file; ``WellData`` stacks the instances of one well and
finds which ones overlap. Only pandas, numpy and pyarrow are needed here.
"""

import configparser
import contextlib
import hashlib
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from overlap_viewer.config import (
    DEFAULT_FAULT_NAMES,
    DEFAULT_SENSOR_UNITS,
    DEFAULT_TRANSIENT_OFFSET,
    LABEL_COLUMNS,
    REACH_TINTS,
    REAL_PREFIX,
    cache_dir,
)
from overlap_viewer.labels import (
    Segment,
    column_as_float,
    coverage_counts,
    fault_reach,
    label_segments,
    labels_agree,
    segments_from_json,
    segments_to_json,
)

# Facts recorded per instance by ``scan_instances`` and kept in the cache.
# ``class_runs`` holds the runs of the ``class`` column (``labels.segments_to_json``),
# which is what deciding whether two overlapping instances may be joined needs.
CATALOGUE_COLUMNS = [
    "file",
    "fault_class",
    "well",
    "start",
    "end",
    "n_samples",
    "reach",
    "class_runs",
    "size",
    "mtime_ns",
]

ProgressCallback = Callable[[int, int, str], bool]


class ScanCancelled(Exception):
    """Raised when the progress callback asks the scan to stop."""


# -- dataset.ini ------------------------------------------------------------------


@dataclass(frozen=True)
class DatasetInfo:
    """What the dataset says about itself, with fallbacks for a missing ini file.

    Attributes
    ----------
    raw_dir : Path
        Root of the dataset (the folder holding ``0/`` .. ``9/``).
    fault_names : dict[int, str]
        Event description per fault-class label.
    transient_offset : int
        Offset between a fault label and its transient label.
    sensor_units : dict[str, str]
        Unit per variable, in dataset order (``-`` for enumerated states).
    sensor_descriptions : dict[str, str]
        Full description per variable, for tooltips.
    version : str
        Dataset version, empty when unknown.
    """

    raw_dir: Path
    fault_names: dict[int, str] = field(default_factory=lambda: dict(DEFAULT_FAULT_NAMES))
    transient_offset: int = DEFAULT_TRANSIENT_OFFSET
    sensor_units: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_SENSOR_UNITS))
    sensor_descriptions: dict[str, str] = field(default_factory=dict)
    version: str = ""

    @property
    def sensor_names(self) -> list[str]:
        """Every variable the dataset declares, in dataset order."""
        return list(self.sensor_units)

    @property
    def fault_classes(self) -> list[int]:
        """Fault-class folders present under ``raw_dir``, ascending."""
        return sorted(
            int(p.name) for p in self.raw_dir.iterdir() if p.is_dir() and p.name.isdigit()
        )

    def fault_name(self, fault_class: int) -> str:
        return self.fault_names.get(fault_class, f"Class {fault_class}")

    def unit(self, sensor: str) -> str:
        unit = self.sensor_units.get(sensor, "")
        return "" if unit == "-" else unit

    @classmethod
    def load(cls, raw_dir: Path) -> "DatasetInfo":
        """Read ``dataset.ini`` under ``raw_dir``; fall back to the built-in constants."""
        raw_dir = Path(raw_dir)
        ini_path = raw_dir / "dataset.ini"
        if not ini_path.exists():
            return cls(raw_dir)
        parser = configparser.ConfigParser()
        parser.read(ini_path, encoding="utf-8")

        units, descriptions = dict(DEFAULT_SENSOR_UNITS), {}
        if "PARQUET_FILE_PROPERTIES" in parser:
            units, descriptions = {}, {}
            for key, desc in parser["PARQUET_FILE_PROPERTIES"].items():
                name = key.upper()
                if name in ("TIMESTAMP", *(c.upper() for c in LABEL_COLUMNS)):
                    continue
                match = re.search(r"\[([^\[\]]+)\]\s*$", desc)
                unit = match.group(1) if match else ""
                if "," in unit or " or " in unit:
                    unit = "-"
                units[name] = unit.replace("oC", "°C").replace("m3/s", "m³/s")
                descriptions[name] = re.sub(r"\s*\[[^\[\]]+\]\s*$", "", desc)

        names, offset = dict(DEFAULT_FAULT_NAMES), DEFAULT_TRANSIENT_OFFSET
        if "EVENTS" in parser:
            events = parser["EVENTS"]
            offset = events.getint("TRANSIENT_OFFSET", DEFAULT_TRANSIENT_OFFSET)
            listed = [n.strip() for n in events.get("NAMES", "").replace("\n", " ").split(",")]
            parsed = {}
            for event in filter(None, listed):
                if event in parser and "LABEL" in parser[event]:
                    label = parser[event].getint("LABEL")
                    parsed[label] = parser[event].get(
                        "DESCRIPTION", event.replace("_", " ").title()
                    )
            if parsed:
                names = parsed

        version = parser["VERSION"].get("DATASET", "") if "VERSION" in parser else ""
        return cls(raw_dir, names, offset, units, descriptions, version)


# -- Instance discovery -------------------------------------------------------------


def parse_well_id(filename: str) -> int | None:
    """Well number of a real instance filename (``WELL-00026_...`` -> 26)."""
    match = re.match(r"WELL-(\d+)", Path(filename).stem, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def well_label(well: int) -> str:
    """Filename-style name of a well (``WELL-00026``)."""
    return f"WELL-{well:05d}"


def filename_stamp(filename: str) -> pd.Timestamp | None:
    """Timestamp a real instance filename is keyed by, when it carries one.

    Real instances are named ``WELL-000{id}_{YYYYMMDDhhmmss}.parquet``; the
    stamp is the first timestamp of the recording and the literal piece of the
    filename a suspicious bar can be looked up by.
    """
    match = re.search(r"_(\d{14})", Path(filename).stem)
    if not match:
        return None
    stamp = pd.to_datetime(match.group(1), format="%Y%m%d%H%M%S", errors="coerce")
    return None if pd.isna(stamp) else stamp


def list_real_instances(raw_dir: Path, fault_classes: list[int]) -> list[tuple[int, Path]]:
    """Every real instance file, folder by folder, sorted by name within a folder."""
    entries = []
    for fault_class in fault_classes:
        class_dir = Path(raw_dir) / str(fault_class)
        if not class_dir.is_dir():
            continue
        for path in sorted(class_dir.glob("*.parquet")):
            if path.name.upper().startswith(REAL_PREFIX) and parse_well_id(path.name) is not None:
                entries.append((fault_class, path))
    return entries


def _listing(entries: list[tuple[int, Path]]) -> pd.DataFrame:
    """Name, folder, size and modification time of every entry, for cache validation."""
    rows = []
    for fault_class, path in entries:
        stat = path.stat()
        rows.append((path.name, fault_class, stat.st_size, stat.st_mtime_ns))
    return pd.DataFrame(rows, columns=["file", "fault_class", "size", "mtime_ns"])


def scan_instances(
    entries: list[tuple[int, Path]],
    transient_offset: int = DEFAULT_TRANSIENT_OFFSET,
    progress: ProgressCallback | None = None,
) -> pd.DataFrame:
    """Read the time span, length, reach and label runs of every instance.

    Only the ``class`` column (and the timestamp index) of each file is read,
    which takes a few seconds over the whole dataset.

    Parameters
    ----------
    entries : list[(int, Path)]
        Fault class and path of every file, from ``list_real_instances``.
    transient_offset : int
        Offset between a fault label and its transient label.
    progress : callable, optional
        Called as ``progress(done, total, filename)`` after each file; return
        ``False`` to cancel, which raises ``ScanCancelled``.

    Returns
    -------
    pd.DataFrame
        One row per instance with ``CATALOGUE_COLUMNS``.
    """
    rows = []
    for i, (fault_class, path) in enumerate(entries, start=1):
        labels = pd.read_parquet(path, columns=["class"])
        stat = path.stat()
        rows.append(
            {
                "file": path.name,
                "fault_class": fault_class,
                "well": parse_well_id(path.name),
                "start": labels.index.min(),
                "end": labels.index.max(),
                "n_samples": len(labels),
                "reach": fault_reach(column_as_float(labels, "class"), transient_offset),
                "class_runs": segments_to_json(label_segments(labels, "class")),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        )
        if progress is not None and not progress(i, len(entries), path.name):
            raise ScanCancelled()
    return pd.DataFrame(rows, columns=CATALOGUE_COLUMNS)


def cache_path(raw_dir: Path) -> Path:
    """Cache file of one dataset root, named by a digest of its resolved path."""
    digest = hashlib.sha1(str(Path(raw_dir).resolve()).encode("utf-8")).hexdigest()[:12]
    return cache_dir() / f"catalogue_{digest}.parquet"


def _cache_is_current(cached: pd.DataFrame, listing: pd.DataFrame) -> bool:
    """Whether the cached catalogue describes exactly the files listed now."""
    if len(cached) != len(listing) or not set(CATALOGUE_COLUMNS) <= set(cached.columns):
        return False
    keys = ["file", "fault_class"]
    merged = listing.merge(
        cached[keys + ["size", "mtime_ns"]], on=keys, how="left", suffixes=("", "_cached")
    )
    return bool(
        merged["size_cached"].notna().all()
        and (merged["size"] == merged["size_cached"]).all()
        and (merged["mtime_ns"] == merged["mtime_ns_cached"]).all()
    )


def load_catalogue(
    info: DatasetInfo,
    use_cache: bool = True,
    progress: ProgressCallback | None = None,
) -> pd.DataFrame:
    """The catalogue of every real instance, from the cache when it is current.

    The cache is keyed by the dataset path and validated against the current
    listing (names, sizes, modification times) with a handful of ``stat``
    calls, so a changed or added file triggers a fresh scan. Writing the cache
    is best effort: a read-only home directory only costs the speed-up.

    Parameters
    ----------
    info : DatasetInfo
        Dataset to catalogue.
    use_cache : bool
        Read and write the on-disk cache (default on).
    progress : callable, optional
        Progress callback of ``scan_instances``.

    Returns
    -------
    pd.DataFrame
        ``CATALOGUE_COLUMNS`` plus ``path`` (the file's location), ``stamp``
        (the filename timestamp, falling back to ``start``) and ``hours`` (the
        recording's duration), sorted by well and start.
    """
    entries = list_real_instances(info.raw_dir, info.fault_classes)
    if not entries:
        raise FileNotFoundError(f"No real ({REAL_PREFIX}*) instances under {info.raw_dir}")
    listing = _listing(entries)
    path = cache_path(info.raw_dir)

    catalogue = None
    if use_cache and path.exists():
        try:
            cached = pd.read_parquet(path)
            if _cache_is_current(cached, listing):
                catalogue = cached[CATALOGUE_COLUMNS]
        except Exception:  # noqa: BLE001 - a corrupt cache is simply rebuilt
            catalogue = None

    if catalogue is None:
        catalogue = scan_instances(entries, info.transient_offset, progress)
        if use_cache:
            # Caching is a convenience, never a requirement: a read-only home costs the speed-up only.
            with contextlib.suppress(Exception):
                path.parent.mkdir(parents=True, exist_ok=True)
                catalogue.to_parquet(path, index=False)

    catalogue = catalogue.copy()
    locations = {(fault_class, p.name): p for fault_class, p in entries}
    catalogue["path"] = [
        locations[(fc, name)] for fc, name in zip(catalogue["fault_class"], catalogue["file"])
    ]
    catalogue["start"] = pd.to_datetime(catalogue["start"])
    catalogue["end"] = pd.to_datetime(catalogue["end"])
    stamps = [filename_stamp(name) for name in catalogue["file"]]
    catalogue["stamp"] = [s if s is not None else t for s, t in zip(stamps, catalogue["start"])]
    catalogue["hours"] = (catalogue["end"] - catalogue["start"]).dt.total_seconds() / 3600.0
    return catalogue.sort_values(["well", "start", "file"]).reset_index(drop=True)


def load_instance(path: Path) -> pd.DataFrame:
    """Read one instance in full, sensors as floats, timestamp-indexed."""
    return pd.read_parquet(path)


def merge_instances(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """One continuous recording from the instances of a well that overlap in time.

    The instances of a well are windows cut from the same recording, so the
    samples two of them share carry the same readings twice; the merged frame
    keeps every instant once. Where one window says nothing about a column — a
    sensor it did not record, or a sample the experts left unlabeled — the
    value is taken from whichever window does say something, which is what
    makes merging worth doing: the unlabeled head of a window is usually
    labeled by the window before it, so the ``class`` column comes out with far
    fewer unlabeled samples than any of its parts, and a model is trained on
    what a reader of the merged recording would see.

    Windows only reach this function when their labels agree wherever both are
    known (see ``join_groups``), so nothing is silently preferred over a
    different reading. On 3W 2.0.0 no two real instances disagree on a known
    value of any column at a shared timestamp.
    """
    if len(frames) == 1:
        return frames[0]
    stacked = pd.concat(frames)
    if not stacked.index.has_duplicates:
        return stacked.sort_index(kind="stable")
    # ``first`` is per column and skips the missing values, which is the fill
    # above; it also sorts by the index, so the result is chronological.
    return stacked.groupby(level=0).first()


# -- Overlaps within a well -----------------------------------------------------------


def pack_lanes(starts: np.ndarray, ends: np.ndarray) -> np.ndarray:
    """Stack overlapping instances, one lane per level of simultaneity.

    Instances are placed in chronological order, each one taking the lowest
    lane whose last instance has already ended; a new lane opens only when
    every existing one is still busy. Two instances therefore share a lane
    exactly when they do not overlap, so the number of lanes is the deepest
    pile-up of the well, and a chain of sliding windows alternates between
    two lanes, its overlaps visible as the horizontal offset between them.
    This is the very rule the ``flowml`` pipeline drops overlapping instances
    by (it keeps the bottom lane only).

    Returns the lane index (0-based) per instance, in the input order.
    """
    lane_of = np.zeros(len(starts), dtype=int)
    lane_ends: list = []
    for i in np.argsort(starts, kind="stable"):
        for lane, lane_end in enumerate(lane_ends):
            if starts[i] > lane_end:
                lane_of[i] = lane
                lane_ends[lane] = ends[i]  # starts are sorted, so this only grows
                break
        else:
            lane_of[i] = len(lane_ends)
            lane_ends.append(ends[i])
    return lane_of


def overlap_matrix(starts: np.ndarray, ends: np.ndarray) -> np.ndarray:
    """Which pairs of instances share at least one timestamp.

    Touching at a single shared second counts, since that second is then
    labeled twice. The diagonal is ``False``.
    """
    starts, ends = np.asarray(starts), np.asarray(ends)
    hits = (starts[:, None] <= ends[None, :]) & (starts[None, :] <= ends[:, None])
    np.fill_diagonal(hits, False)
    return hits


def join_groups(starts: np.ndarray, ends: np.ndarray, runs: list[list[Segment]]) -> list[list[int]]:
    """Group the instances that overlap in time and agree in their labels.

    Instances are taken in order of start. Each one joins the first group that
    holds an instance it overlaps, provided its labels agree
    (``labels.labels_agree``) with those of every member it overlaps, and
    opens a group of its own otherwise. A group is therefore one continuous
    stretch of recording — every member overlaps another — in which no sample
    sits under two different known labels, so its members can be read as a
    single instance.

    Two groups that still overlap afterwards always disagree somewhere: the
    instance that opened the later group overlapped a member of the earlier
    one when it was placed (or a member added since overlaps one it did) and
    was refused, which only a disagreement does. What stays stacked after a
    join is exactly the labeling conflicts.

    Parameters
    ----------
    starts, ends : array-like of datetime64
        First and last timestamp of every instance.
    runs : list[list[Segment]]
        The ``class`` runs of every instance, as ``labels.label_segments``
        returns them.

    Returns
    -------
    list[list[int]]
        The positions of every group's members; groups and members in
        chronological order.
    """
    starts, ends = np.asarray(starts), np.asarray(ends)
    groups: list[list[int]] = []
    for i in np.argsort(starts, kind="stable").tolist():
        for group in groups:
            touching = [m for m in group if starts[i] <= ends[m] and starts[m] <= ends[i]]
            if touching and all(labels_agree(runs[i], runs[m]) for m in touching):
                group.append(i)
                break
        else:
            groups.append([i])
    return groups


def _distinct_samples(part: pd.DataFrame, runs: list[list[Segment]]) -> int:
    """How many sampling instants a group of instances covers between them.

    The shared samples of overlapping instances are counted once: the runs of
    each instance tile it up to one sampling step past its last sample, so the
    union of those spans, in steps, is the number of distinct instants.
    """
    if len(part) == 1 or any(not track for track in runs):
        return int(part["n_samples"].sum())
    tiled_ends = [track[-1].end for track in runs]
    step = tiled_ends[0] - pd.Timestamp(part["end"].iloc[0])
    covered = sum(
        (b - a for a, b, count in coverage_counts(part["start"], tiled_ends) if count >= 1),
        pd.Timedelta(0),
    )
    return round(covered / step)


@dataclass
class WellData:
    """The bars of one well, stacked, with their overlaps resolved.

    A bar is one real instance, or — in the view ``joined`` builds — one group
    of overlapping instances whose labels agree, drawn as one.

    Attributes
    ----------
    well : int
        Well number.
    rows : pd.DataFrame
        One row per bar, sorted by start and re-indexed from zero, with the
        catalogue facts of the instance (or the summary of the group), its
        ``title``, plus ``lane`` (stack level, 0-based) and ``overlaps``
        (whether the bar shares a timestamp with another).
    partners : list[np.ndarray]
        Per bar, the row positions of the bars it overlaps.
    members : list[list[int]]
        Per bar, the positions in ``origin.rows`` of the instances behind it:
        the bar's own position when nothing is joined.
    colors : list[list[tuple[int, str]]]
        Per bar, the fault class and reach of every instance behind it, one
        entry per distinct pair, by fault class and then by decreasing tint
        strength — the colors the bar has to carry.
    source : WellData or None
        The unjoined bars a joined view was built from; ``None`` otherwise.
    """

    well: int
    rows: pd.DataFrame
    partners: list[np.ndarray]
    members: list[list[int]]
    colors: list[list[tuple[int, str]]]
    source: "WellData | None" = None
    # The joined view of this well, built once and handed to everyone who asks
    # for it: the overview draws it, and an instance window opened from either
    # view switches between the two without building anything again.
    _joined: "WellData | None" = field(default=None, repr=False, compare=False)

    @classmethod
    def from_catalogue(cls, catalogue: pd.DataFrame, well: int) -> "WellData":
        rows = (
            catalogue[catalogue["well"] == well]
            .sort_values(["start", "file"])
            .reset_index(drop=True)
        )
        if rows.empty:
            raise ValueError(f"No instances of {well_label(well)} in the catalogue")
        rows["title"] = [os.path.splitext(str(name))[0] for name in rows["file"]]
        members = [[i] for i in range(len(rows))]
        colors = [
            [(int(fault_class), str(reach))]
            for fault_class, reach in zip(rows["fault_class"], rows["reach"])
        ]
        return cls._stacked(well, rows, members, colors, None)

    @classmethod
    def _stacked(
        cls,
        well: int,
        rows: pd.DataFrame,
        members: list[list[int]],
        colors: list[list[tuple[int, str]]],
        source: "WellData | None",
    ) -> "WellData":
        """Lay ``rows`` (chronological) on their lanes and find which ones overlap."""
        starts = rows["start"].to_numpy(dtype="datetime64[ns]")
        ends = rows["end"].to_numpy(dtype="datetime64[ns]")
        hits = overlap_matrix(starts, ends)
        rows["lane"] = pack_lanes(starts, ends)
        rows["overlaps"] = hits.any(axis=1)
        return cls(well, rows, [np.flatnonzero(row) for row in hits], members, colors, source)

    def joined(self, among: list[int] | None = None) -> "WellData":
        """The groups of agreeing, overlapping instances of this well, each drawn as one bar.

        The groups are those of ``join_groups``, read from the ``class_runs``
        the catalogue carries. A joined bar spans from the first start to the
        last end of its members and remembers them in ``members``; its
        ``colors`` are those of all of them, and its ``fault_class`` and
        ``reach`` summarize what the joined labels reach: the strongest reach
        among the members, and the class of the member that reached it (a
        fault before normal operation, and the earliest, on a tie). Its title
        is the first member's followed by how many more it joins.

        Parameters
        ----------
        among : list[int], optional
            Join only these instances, and return only what they make up.
            Two of them that overlap only through an instance left out stay
            apart, so the result is what joining that set alone says rather
            than what the whole well says — which is what an instance window
            asks for, its own group being all it is about. The default joins
            the well, and is built once and remembered, so that asking for it
            again hands back the very object the overview is drawing.
        """
        if self.source is not None:
            return self
        if among is not None:
            return self._build_joined(sorted(among))
        if self._joined is None:
            self._joined = self._build_joined(None)
        return self._joined

    def _build_joined(self, among: list[int] | None) -> "WellData":
        rows = self.rows
        taken = list(range(len(rows))) if among is None else list(among)
        scope = rows.iloc[taken]
        runs = {p: segments_from_json(text) for p, text in zip(taken, scope["class_runs"])}
        # ``join_groups`` numbers what it is given; the groups are put back into
        # the well's own numbering, which is what ``members`` promises.
        groups = [
            [taken[k] for k in group]
            for group in join_groups(
                scope["start"].to_numpy(dtype="datetime64[ns]"),
                scope["end"].to_numpy(dtype="datetime64[ns]"),
                [runs[p] for p in taken],
            )
        ]
        records, members, colors = [], [], []
        for group in groups:
            part = rows.iloc[group]
            first = part.iloc[0]
            classes = [int(fault_class) for fault_class in part["fault_class"]]
            reaches = [str(reach) for reach in part["reach"]]
            lead = max(
                range(len(group)),
                key=lambda k: (REACH_TINTS[reaches[k]], classes[k] != 0, -k),
            )
            keys = sorted(
                set(zip(classes, reaches)), key=lambda key: (key[0], -REACH_TINTS[key[1]])
            )
            start, end = pd.Timestamp(part["start"].min()), pd.Timestamp(part["end"].max())
            more = len(group) - 1
            records.append(
                {
                    "title": f"{first['title']} +{more}" if more else str(first["title"]),
                    "fault_class": classes[lead],
                    "well": self.well,
                    "start": start,
                    "end": end,
                    "n_samples": _distinct_samples(part, [runs[i] for i in group]),
                    "reach": reaches[lead],
                    "stamp": first["stamp"],
                    "hours": (end - start).total_seconds() / 3600.0,
                }
            )
            members.append(list(group))
            colors.append(keys)
        return self._stacked(self.well, pd.DataFrame(records), members, colors, self)

    @property
    def joined_view(self) -> bool:
        """Whether the bars are groups of instances rather than the instances themselves."""
        return self.source is not None

    @property
    def origin(self) -> "WellData":
        """The instances themselves: ``source`` of a joined view, else this object."""
        return self.source if self.source is not None else self

    @property
    def label(self) -> str:
        return well_label(self.well)

    @property
    def n_instances(self) -> int:
        return len(self.rows)

    @property
    def n_overlapping(self) -> int:
        return int(self.rows["overlaps"].sum())

    @property
    def n_lanes(self) -> int:
        return int(self.rows["lane"].max()) + 1

    @property
    def starts(self) -> np.ndarray:
        return self.rows["start"].to_numpy(dtype="datetime64[ns]")

    @property
    def ends(self) -> np.ndarray:
        return self.rows["end"].to_numpy(dtype="datetime64[ns]")

    def group(self, index: int) -> list[int]:
        """Row positions of one bar and of every bar it overlaps, chronological."""
        return sorted({int(index), *(int(j) for j in self.partners[index])})

    def fault_classes(self) -> set[int]:
        """The fault-class folders this well has instances in."""
        return {fault_class for keys in self.colors for fault_class, _ in keys}

    def present_colors(self) -> set[tuple[int, str]]:
        """Fault class and reach of every color this well draws."""
        return {key for keys in self.colors for key in keys}


def split_wells(catalogue: pd.DataFrame) -> list[WellData]:
    """One ``WellData`` per well of the catalogue, by ascending well number."""
    return [
        WellData.from_catalogue(catalogue, int(well)) for well in sorted(catalogue["well"].unique())
    ]


def lane_slots(wells: list[WellData], minimum: int, maximum: int) -> int:
    """Stack levels every timeline shows: the deepest pile-up, within bounds."""
    deepest = max((well.n_lanes for well in wells), default=1)
    return int(min(max(deepest, minimum), maximum))


def instance_title(row: pd.Series) -> str:
    """The name of a bar: its ``title`` when it has one, else its filename without extension."""
    if "title" in row.index:
        return str(row["title"])
    return os.path.splitext(str(row["file"]))[0]
