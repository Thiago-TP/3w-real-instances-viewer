"""Backend tests on a synthetic miniature of the 3W layout; no Qt involved."""

import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from overlap_viewer import dataset as ds
from overlap_viewer import help_text, theme
from overlap_viewer.config import (
    DEFAULT_FAULT_NAMES,
    DEFAULT_SENSOR_UNITS,
    FAULT_SIGNATURES,
    REACH_TINTS,
    WELL_STATES,
    asset_path,
    cache_dir,
)
from overlap_viewer.labels import (
    Segment,
    column_as_float,
    coverage_counts,
    fault_reach,
    feature_stats,
    label_kind,
    label_name,
    label_segments,
    labels_agree,
    merge_label_runs,
    padded_range,
    runs,
    segments_from_json,
    segments_to_json,
)
from overlap_viewer.legend import row_breaks
from overlap_viewer.palette import (
    background_color,
    bar_color,
    blend,
    fault_color,
    legend_entries,
    legend_key,
    state_color,
    text_color,
    tint,
    to_rgb,
    unknown_background,
)
from overlap_viewer.timemap import TimeMap

T0 = pd.Timestamp("2017-02-01 01:00:00")

# Where ``config.cache_dir`` looks on the platform the tests are running on. A
# test that wants the cache inside its ``tmp_path`` sets this one rather than
# faking ``os.name`` to reach the other branch: ``os.name`` is also what tells
# ``pathlib`` which flavour of ``Path`` to build, so a Windows interpreter told
# it is POSIX hands out ``PosixPath`` objects that raise on their first join.
CACHE_HOME = "LOCALAPPDATA" if os.name == "nt" else "XDG_CACHE_HOME"


@pytest.fixture(autouse=True)
def light_theme():
    """The theme is global, so a test that switches it must not colour the next one."""
    theme.use("light")
    yield
    theme.use("light")


def hours(h: float) -> pd.Timestamp:
    return T0 + pd.Timedelta(hours=h)


def segments(*spans) -> list[Segment]:
    """Label runs from ``(start_hour, end_hour, value)`` triples."""
    return [Segment(hours(a), hours(b), float(v)) for a, b, v in spans]


def instance_row(well: int, fault_class: int, start: pd.Timestamp, labels) -> dict:
    """The catalogue row of an in-memory instance sampled once a second, files left out."""
    index = pd.date_range(start, periods=len(labels), freq="1s", name="timestamp")
    frame = pd.DataFrame({"class": pd.array(labels, dtype="Int16")}, index=index)
    return {
        "file": f"WELL-{well:05d}_{start:%Y%m%d%H%M%S}.parquet",
        "fault_class": fault_class,
        "well": well,
        "start": index[0],
        "end": index[-1],
        "n_samples": len(index),
        "reach": fault_reach(column_as_float(frame, "class")),
        "class_runs": segments_to_json(label_segments(frame, "class")),
        "size": 0,
        "mtime_ns": 0,
        "stamp": index[0],
        "hours": (index[-1] - index[0]).total_seconds() / 3600,
    }


def write_instance(folder: Path, well: int, start: pd.Timestamp, n: int, classes) -> Path:
    """One parquet file shaped like a 3W instance: timestamp index, sensors, nullable labels."""
    index = pd.date_range(start, periods=n, freq="1s", name="timestamp")
    frame = pd.DataFrame(
        {
            "P-PDG": np.linspace(1.0e7, 1.1e7, n),
            "T-TPT": np.full(n, 118.5),
            "QGL": np.full(n, np.nan),
            "class": pd.array(classes, dtype="Int16"),
            "state": pd.array([0] * n, dtype="Int16"),
        },
        index=index,
    )
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"WELL-{well:05d}_{start:%Y%m%d%H%M%S}.parquet"
    frame.to_parquet(path)
    return path


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    root = tmp_path / "dataset"
    (root / "dataset.ini").parent.mkdir()
    (root / "dataset.ini").write_text(
        "[VERSION]\nDATASET = 9.9.9\n"
        "[PARQUET_FILE_PROPERTIES]\ntimestamp = Instant\nP-PDG = Downhole pressure [Pa]\n"
        "T-TPT = Xmas-tree temperature [oC]\nQGL = Gas lift flow rate [m3/s]\n"
        "ESTADO-W1 = State of the PWV [0, 0.5, or 1]\nclass = Label\nstate = Status\n"
        "[EVENTS]\nNAMES = NORMAL, HYDRATE_IN_SERVICE_LINE\nTRANSIENT_OFFSET = 100\n"
        "[NORMAL]\nLABEL = 0\nDESCRIPTION = Normal Operation\n"
        "[HYDRATE_IN_SERVICE_LINE]\nLABEL = 9\nDESCRIPTION = Hydrate in Service Line\nTRANSIENT = True\n",
        encoding="utf-8",
    )
    n = 3600
    # Well 1: a chain of three windows, each overlapping the next by one hour.
    write_instance(root / "0", 1, hours(0), 2 * n, [0] * (2 * n))
    write_instance(root / "0", 1, hours(1), 2 * n, [0] * (2 * n))
    write_instance(root / "0", 1, hours(2), 2 * n, [0] * (2 * n))
    # Well 2: one hydrate instance that reaches the transient only, and one that never leaves normal.
    write_instance(root / "9", 2, hours(0), n, [pd.NA] * 600 + [0] * 1800 + [109] * 1200)
    write_instance(root / "9", 2, hours(48), n, [0] * n)
    # A simulated file must be ignored.
    (root / "9" / "SIMULATED_00001.parquet").write_bytes(b"not parquet")
    return root


def test_parse_names():
    assert ds.parse_well_id("WELL-00026_20170608230000.parquet") == 26
    assert ds.parse_well_id("SIMULATED_00001.parquet") is None
    assert ds.filename_stamp("WELL-00026_20170608230000.parquet") == pd.Timestamp(
        "2017-06-08 23:00:00"
    )
    assert ds.filename_stamp("WELL-00026.parquet") is None
    assert ds.well_label(7) == "WELL-00007"


def test_dataset_info_reads_ini(raw_dir: Path):
    info = ds.DatasetInfo.load(raw_dir)
    assert info.version == "9.9.9"
    assert info.fault_names == {0: "Normal Operation", 9: "Hydrate in Service Line"}
    assert info.sensor_names == ["P-PDG", "T-TPT", "QGL", "ESTADO-W1"]
    assert info.unit("P-PDG") == "Pa"
    assert info.unit("T-TPT") == "°C"
    assert info.unit("QGL") == "m³/s"
    assert info.unit("ESTADO-W1") == ""  # enumerated states have no unit
    assert info.fault_classes == [0, 9]


def test_dataset_info_falls_back_without_ini(tmp_path: Path):
    info = ds.DatasetInfo.load(tmp_path)
    assert info.fault_name(3) == "Severe Slugging"
    assert "P-TPT" in info.sensor_names


def test_pack_lanes_alternates_along_a_chain():
    starts = np.array([hours(h) for h in (0, 1, 2, 3)], dtype="datetime64[ns]")
    ends = np.array([hours(h) for h in (1.5, 2.5, 3.5, 4.5)], dtype="datetime64[ns]")
    assert ds.pack_lanes(starts, ends).tolist() == [0, 1, 0, 1]


def test_overlap_matrix_counts_a_shared_second():
    starts = np.array([hours(0), hours(1), hours(5)], dtype="datetime64[ns]")
    ends = np.array([hours(1), hours(2), hours(6)], dtype="datetime64[ns]")
    hits = ds.overlap_matrix(starts, ends)
    assert hits[0, 1] and hits[1, 0]
    assert not hits[0, 2] and not hits.diagonal().any()


def test_fault_reach_and_label_kinds():
    assert fault_reach(np.array([np.nan, 0.0, 109.0, 9.0])) == "steady"
    assert fault_reach(np.array([0.0, 109.0])) == "transient"
    assert fault_reach(np.array([0.0, np.nan])) == "normal"
    assert [label_kind(v) for v in (np.nan, 0.0, 4.0, 104.0, 250.0)] == [
        "unknown",
        "normal",
        "steady",
        "transient",
        "unknown",
    ]
    names = {0: "Normal Operation", 9: "Hydrate in Service Line"}
    assert label_name(109.0, names) == "Hydrate in Service Line - Transient"
    assert label_name(9.0, names) == "Hydrate in Service Line"
    assert label_name(np.nan, names) == "Unknown"


def test_runs_and_segments_tile_the_recording():
    values = np.array([np.nan, np.nan, 0.0, 0.0, 109.0])
    found = runs(values)
    assert [(s, e) for s, e, _ in found] == [(0, 2), (2, 4), (4, 5)]
    assert np.isnan(found[0][2]) and [v for _, _, v in found[1:]] == [0.0, 109.0]
    index = pd.date_range(T0, periods=5, freq="1s", name="timestamp")
    frame = pd.DataFrame({"class": pd.array([pd.NA, pd.NA, 0, 0, 109], dtype="Int16")}, index=index)
    segments = label_segments(frame, "class")
    assert [s.start for s in segments] == [index[0], index[2], index[4]]
    assert segments[-1].end == index[-1] + pd.Timedelta(seconds=1)
    assert segments[0].end == segments[1].start


def test_label_runs_survive_the_catalogue_cache():
    index = pd.date_range(T0, periods=5, freq="1s", name="timestamp")
    frame = pd.DataFrame({"class": pd.array([pd.NA, pd.NA, 0, 0, 109], dtype="Int16")}, index=index)
    original = label_segments(frame, "class")
    back = segments_from_json(segments_to_json(original))
    assert [(s.start, s.end) for s in back] == [(s.start, s.end) for s in original]
    assert np.isnan(back[0].value) and [s.value for s in back[1:]] == [0.0, 109.0]
    assert segments_from_json(segments_to_json([])) == []


def test_labels_agree_only_where_both_tracks_know_the_label():
    a = segments((0, 2, 0), (2, 3, 109))  # normal for two hours, then the transient
    assert labels_agree(a, segments((1, 2, 0), (2, 4, 109)))  # the same labels where shared
    assert not labels_agree(a, segments((1, 3, 0)))  # normal where ``a`` says transient
    assert labels_agree(a, segments((1, 3, np.nan)))  # unknown agrees with anything
    assert labels_agree(a, segments((5, 6, 4)))  # nothing shared at all
    assert labels_agree(a, []) and labels_agree([], a)
    # A contradiction one sampling step long still counts.
    second = pd.Timedelta(seconds=1)
    b = segments((0, 2, 0)) + [Segment(hours(2), hours(2) + second, 4.0)]
    assert not labels_agree(a, b) and not labels_agree(b, a)


def test_merged_label_runs_fill_the_unknown_and_remember_whose_label_it_is():
    """Merging labels shrinks the unlabeled stretches and keeps each one's folder."""
    normal = segments((0, 1, np.nan), (1, 4, 0))  # a Normal Operation file, unlabeled head
    hydrate = segments((3, 5, np.nan), (5, 6, 0), (6, 8, 108))  # a hydrate file, unlabeled head

    def spell(found):
        """The runs as ``(start hour, end hour, label or 'unlabeled', source)``."""
        return [
            (
                (s.start - T0) / pd.Timedelta(hours=1),
                (s.end - T0) / pd.Timedelta(hours=1),
                "unlabeled" if np.isnan(s.value) else s.value,
                source,
            )
            for s, source in found
        ]

    assert spell(merge_label_runs([normal, hydrate], [0, 8])) == [
        (0.0, 1.0, "unlabeled", None),  # nothing knows the first hour
        # The Normal Operation file's own label, which also fills the unlabeled
        # head of the hydrate window where the two overlap, at hour 3.
        (1.0, 4.0, 0.0, 0),
        (4.0, 5.0, "unlabeled", None),  # its window has ended, the hydrate's head is still blank
        (5.0, 6.0, 0.0, 8),  # normal, but labeled by the hydrate file: that file's color
        (6.0, 8.0, 108.0, 8),
    ]
    # One track is passed through as it is, and runs that agree coalesce.
    assert spell(merge_label_runs([normal], [0])) == [
        (0.0, 1.0, "unlabeled", None),
        (1.0, 4.0, 0.0, 0),
    ]
    assert merge_label_runs([], []) == []


def test_join_groups_merges_agreeing_chains_and_splits_conflicts():
    starts = np.array([hours(h) for h in (0, 1, 2.5, 3.5, 4.5)], dtype="datetime64[ns]")
    ends = np.array([hours(h) for h in (2, 3, 4, 5, 6)], dtype="datetime64[ns]")
    tracks = [
        segments((0, 2, 0)),
        segments((1, 3, 0)),
        segments((2.5, 3, 0), (3, 4, 109)),  # agrees with the one before on their shared half hour
        segments((3.5, 5, 0)),  # normal where the one before is transient: a conflict
        segments((4.5, 6, 109)),  # transient where the one before is normal: another
    ]
    assert ds.join_groups(starts, ends, tracks) == [[0, 1, 2], [3], [4]]
    # Nothing overlapping, nothing joined.
    assert ds.join_groups(starts[::2], ends[::2] - np.timedelta64(1, "h"), tracks[::2]) == [
        [0],
        [1],
        [2],
    ]


def test_joined_well_merges_agreeing_instances_and_carries_every_color():
    n = 3600
    catalogue = pd.DataFrame(
        [
            # A normal window whose tail is the normal period of a hydrate instance: joinable.
            instance_row(7, 0, hours(0), [0] * (2 * n)),
            instance_row(7, 8, hours(1), [0] * n + [108] * n + [8] * n),
            # A flow-instability window over the hydrate's steady state: a labeling conflict.
            instance_row(7, 4, hours(3.5), [4] * n),
            # A hydrate window that never leaves normal operation, apart from the rest.
            instance_row(7, 8, hours(5), [0] * n),
        ]
    )
    well = ds.WellData.from_catalogue(catalogue, 7)
    assert not well.joined_view and well.origin is well
    assert well.members == [[0], [1], [2], [3]]
    assert well.n_instances == 4 and well.n_overlapping == 3 and well.n_lanes == 2

    joined = well.joined()
    assert joined.joined_view and joined.origin is well and joined.joined() is joined
    assert joined.members == [[0, 1], [2], [3]]
    assert joined.colors == [[(0, "normal"), (8, "steady")], [(4, "steady")], [(8, "normal")]]
    rows = joined.rows
    assert rows["title"].tolist() == [
        "WELL-00007_20170201010000 +1",
        "WELL-00007_20170201043000",
        "WELL-00007_20170201060000",
    ]
    assert rows["fault_class"].tolist() == [8, 4, 8]
    assert rows["reach"].tolist() == ["steady", "steady", "normal"]
    assert rows["start"].iloc[0] == hours(0) and rows["end"].iloc[0] == hours(4) - pd.Timedelta(
        seconds=1
    )
    assert rows["hours"].iloc[0] == pytest.approx((4 * n - 1) / n)
    # The hour the two joined instances share is counted once.
    assert rows["n_samples"].tolist() == [4 * n, n, n]
    assert rows["stamp"].iloc[0] == hours(0)
    # The conflict is what still overlaps; the well keeps every color it drew before.
    assert joined.n_instances == 3 and joined.n_overlapping == 2 and joined.n_lanes == 2
    assert joined.present_colors() == well.present_colors()
    assert joined.fault_classes() == {0, 4, 8}
    # Clicking the joined bar opens it and the bar it overlaps, two blocks of three instances.
    assert joined.group(0) == [0, 1]
    assert [joined.members[p] for p in joined.group(0)] == [[0, 1], [2]]
    # The well-wide view is built once, so the overview and the windows share it.
    assert well.joined() is joined and joined.joined() is joined
    assert ds.instance_title(rows.iloc[0]) == "WELL-00007_20170201010000 +1"
    assert ds.instance_title(well.rows.iloc[0]) == "WELL-00007_20170201010000"


def test_joining_a_chosen_set_says_what_that_set_alone_amounts_to():
    """An instance window joins its own group, not the well: a bridge left out stays out."""
    n = 3600
    catalogue = pd.DataFrame(
        [
            instance_row(3, 0, hours(0), [0] * (2 * n)),  # [0 h, 2 h)
            instance_row(3, 0, hours(1), [0] * (2 * n)),  # [1 h, 3 h), overlapping both others
            instance_row(3, 0, hours(2.5), [0] * (2 * n)),  # [2.5 h, 4.5 h)
        ]
    )
    well = ds.WellData.from_catalogue(catalogue, 3)
    # The well reads as one recording: the middle instance bridges the other two.
    assert well.joined().members == [[0, 1, 2]]
    # Asked about the first and the last alone, it says they are two recordings. They
    # share no sample, and what would bridge them is not in the set being asked about.
    assert well.joined(among=[0, 2]).members == [[0], [2]]
    assert well.joined(among=[0, 1]).members == [[0, 1]]
    assert well.joined(among=[1]).members == [[1]]
    # Only the well-wide join is remembered, and asking about a subset leaves it alone.
    remembered = well.joined()
    assert well.joined(among=[0, 2]) is not remembered
    assert well.joined() is remembered
    # A joined bar still knows the instances behind it, whichever set it came from.
    pair = well.joined(among=[0, 1])
    assert pair.n_instances == 1 and pair.origin is well
    assert pair.rows["title"].iloc[0].endswith(" +1")


def test_merging_instances_keeps_each_instant_once_and_fills_what_one_window_missed():
    """Two windows of one recording read as the single series they were cut from."""
    index = pd.date_range(T0, periods=4, freq="1s", name="timestamp")
    early = pd.DataFrame(
        {
            "P-PDG": [1.0, 2.0, 3.0, 4.0],
            "T-TPT": [np.nan] * 4,  # a sensor this window did not record
            "class": pd.array([0, 0, 0, 0], dtype="Int16"),
        },
        index=index,
    )
    late = pd.DataFrame(
        {
            "P-PDG": [3.0, 4.0, 5.0],
            "T-TPT": [10.0, 11.0, 12.0],
            "class": pd.array([pd.NA, pd.NA, 109], dtype="Int16"),  # an unlabeled head
        },
        index=pd.date_range(T0 + pd.Timedelta(seconds=2), periods=3, freq="1s", name="timestamp"),
    )
    merged = ds.merge_instances([early, late])
    assert len(merged) == 5 and merged.index.is_monotonic_increasing
    assert merged["P-PDG"].tolist() == [1.0, 2.0, 3.0, 4.0, 5.0]
    # What one window says nothing about, the other one fills: the head of the later
    # window is labeled by the earlier one, and its sensor fills the earlier one's blank.
    assert merged["class"].tolist()[:4] == [0, 0, 0, 0] and merged["class"].iloc[4] == 109
    assert merged["class"].dtype == early["class"].dtype
    assert merged["T-TPT"].isna().tolist() == [True, True, False, False, False]
    assert merged["T-TPT"].dropna().tolist() == [10.0, 11.0, 12.0]
    assert merged.index.name == "timestamp"
    # One window is handed back untouched, and instances that do not overlap simply follow on.
    assert ds.merge_instances([early]) is early
    apart = ds.merge_instances([early, late.set_index(late.index + pd.Timedelta(hours=1))])
    assert len(apart) == 7 and apart.index.is_monotonic_increasing


def test_timemap_compressed_roundtrip_and_gaps():
    starts = [hours(0), hours(2), hours(100)]
    ends = [hours(3), hours(5), hours(101)]
    timemap = TimeMap.build(starts, ends, gap_hours=12.0, compressed=True)
    assert len(timemap.blocks) == 2
    assert timemap.recorded_hours == pytest.approx(6.0)
    x = timemap.to_x(starts)
    assert x[0] == 0.0 and x[1] == pytest.approx(2.0)
    assert x[2] > 5.0  # after the collapsed silence
    for value, stamp in zip(x, starts):
        assert timemap.to_time(float(value)) == stamp
    assert timemap.to_time(timemap.gap_centers()[0]) is None
    assert timemap.to_x(ends)[2] == pytest.approx(timemap.span)


def test_timemap_linear_extrapolates():
    timemap = TimeMap.build([hours(0), hours(48)], [hours(1), hours(49)], compressed=False)
    assert len(timemap.blocks) == 1
    assert timemap.span == pytest.approx(49.0)
    assert timemap.to_time(-2.0) == hours(-2)
    assert timemap.to_time(60.0) == hours(60)


def test_coverage_counts_sweeps_boundaries():
    stretches = coverage_counts([hours(0), hours(1), hours(5)], [hours(2), hours(3), hours(6)])
    assert [(a, b, c) for a, b, c in stretches] == [
        (hours(0), hours(1), 1),
        (hours(1), hours(2), 2),
        (hours(2), hours(3), 1),
        (hours(3), hours(5), 0),
        (hours(5), hours(6), 1),
    ]


def test_padded_range_and_stats():
    low, high = padded_range(5.0, 5.0)
    assert low < 5.0 < high and high - low == pytest.approx(1.0)
    assert padded_range(0.0, 10.0) == (-0.6, 10.6)
    frame = pd.DataFrame({"a": [1.0, np.nan, 3.0], "b": [np.nan, np.nan, np.nan]})
    stats = feature_stats(frame, "a")
    assert (stats.n_valid, stats.n_total, stats.low, stats.high) == (2, 3, 1.0, 3.0)
    assert stats.coverage == pytest.approx(200 / 3)
    assert not feature_stats(frame, "b").recorded
    assert not feature_stats(frame, "missing").recorded


def test_palette_ladder_and_legend():
    assert tint("#000000", 0.0) == "#ffffff"
    assert tint("#17becf", 1.0) == "#17becf"
    steady, transient, normal = (bar_color(9, r) for r in ("steady", "transient", "normal"))
    assert steady == "#17becf"
    assert len({steady, transient, normal}) == 3
    assert bar_color(0, "normal") == bar_color(0, "steady") == "#4c9e4c"
    assert blend(["#000000", "#ffffff"]) == "#808080" and blend(["#17becf"]) == "#17becf"
    names = {0: "Normal Operation", 9: "Hydrate in Service Line"}
    entries = legend_entries({(0, "normal"), (9, "transient"), (9, "steady")}, names)
    assert [entry.label for entry in entries] == [
        "Normal Operation",
        "Hydrate in Service Line (steady state reached)",
        "Hydrate in Service Line (transient state reached)",
    ]
    assert [entry.fill for entry in entries] == [bar_color(0, "steady"), steady, transient]
    # The three reaches of a normal instance share one entry, so one key each.
    assert legend_key(0, "normal") == legend_key(0, "steady") == entries[0].key
    assert legend_key(9, "transient") == entries[2].key


def distance_from_ground(color: str) -> float:
    """How far a color has travelled from the plotting ground it is mixed toward."""
    ground = to_rgb(theme.current().plot_background)
    return sum(abs(a - b) for a, b in zip(ground, to_rgb(color)))


def test_every_theme_colors_everything_the_viewer_can_draw():
    for colors in theme.THEMES.values():
        assert set(colors.faults) == set(DEFAULT_FAULT_NAMES)
        assert set(colors.states) == set(WELL_STATES) | {None}
        assert set(colors.swatches) == {"plain", "highlight", "selected", "dimmed"}
        assert colors.name in theme.MODES


def test_a_mode_changes_every_color_the_plots_carry():
    light = {
        "bar": bar_color(9, "steady"),
        "hue": fault_color(3),
        "state": state_color(0),
        "unknown": unknown_background(),
    }
    assert theme.use("dark").dark
    dark = {
        "bar": bar_color(9, "steady"),
        "hue": fault_color(3),
        "state": state_color(0),
        "unknown": unknown_background(),
    }
    assert all(light[key] != dark[key] for key in light)
    with pytest.raises(ValueError):
        theme.use("solarized")


def test_the_tint_ladder_runs_away_from_the_ground_of_each_mode():
    """A weaker reach is always a step back toward the background, dark or light."""
    for mode in theme.MODES[1:]:
        colors = theme.use(mode)
        assert tint("#000000", 0.0) == colors.plot_background
        assert tint(colors.faults[9], 1.0) == colors.faults[9]
        steps = [distance_from_ground(bar_color(9, reach)) for reach in REACH_TINTS]
        assert steps == sorted(steps, reverse=True), mode  # steady, transient, normal
        # A bar always says its own color rather than blending into the plot.
        assert min(steps) > 0.05, mode
        # And whatever the bar, the stamp written inside it stays readable.
        for reach in REACH_TINTS:
            fill = bar_color(9, reach)
            assert text_color(fill) != fill


def luminance(color: str) -> float:
    r, g, b = to_rgb(color)
    return 0.299 * r + 0.587 * g + 0.114 * b


def test_the_trace_stays_visible_over_every_shading_it_can_sit_on():
    """A time series line keeps to one side of the ladder, the far side of it."""
    for mode in theme.MODES[1:]:
        colors = theme.use(mode)
        grounds = [background_color(f, r) for f in DEFAULT_FAULT_NAMES for r in REACH_TINTS]
        grounds += [tint(unknown_background(), 0.7), colors.plot_background]
        gaps = [luminance(ground) - luminance(colors.trace) for ground in grounds]
        if colors.dark:
            assert max(gaps) < -0.3, mode  # the trace sits above every shading
        else:
            assert min(gaps) > 0.3, mode  # and below every one of them here


def test_the_coverage_band_only_speaks_where_instances_pile_up():
    colors = theme.use("dark")
    assert colors.shared_fill(0) == colors.plot_background
    assert colors.shared_fill(1) == colors.block_fill
    assert colors.shared_fill(2) == colors.shared_fills[0]
    assert colors.shared_fill(99) == colors.shared_fills[-1]


def test_legend_keeps_each_gradient_on_its_own_row():
    """A fault drawn at several tints is only readable with its steps side by side."""
    names = {n: f"Fault {n}" for n in range(6)}
    entries = legend_entries(
        {(0, "normal"), (1, "steady"), (2, "steady"), (2, "transient"), (3, "steady")}, names
    )
    assert [(e.fault_class, e.reach) for e in entries] == [
        (0, "steady"),
        (1, "steady"),
        (2, "steady"),
        (2, "transient"),
        (3, "steady"),
    ]
    # Fault 2 is a gradient: it starts a row, and fault 3 starts the next one.
    assert row_breaks(entries) == [False, False, True, False, True]
    # With no gradient at all, nothing is forced onto its own row.
    plain = legend_entries({(0, "normal"), (1, "steady")}, names)
    assert row_breaks(plain) == [False, False]
    assert row_breaks([]) == []


def test_help_figures_are_declared_and_shipped():
    """The help's illustrations name a caption, a credit and a file that is there."""
    assert {"platform", "platform-overview"} <= set(help_text.FIGURES)
    for figure in help_text.FIGURES.values():
        assert figure.caption and figure.credit and figure.width > 0
        assert asset_path(figure.file) is not None, f"{figure.file} is not shipped"
    assert asset_path("no-such-illustration.png") is None


def test_help_text_covers_the_dataset():
    """Every class, variable and status the viewer can draw has help to show for it."""
    assert set(help_text.FAULTS) == set(DEFAULT_FAULT_NAMES)
    assert set(help_text.VARIABLES) == set(DEFAULT_SENSOR_UNITS)
    assert set(help_text.STATES) == set(WELL_STATES)
    assert set(help_text.TRANSIENT_CAPABLE) == set(DEFAULT_FAULT_NAMES) - {0, 3, 4}
    # A signature only ever names variables the dataset actually has.
    for fault, variables in FAULT_SIGNATURES.items():
        assert fault in DEFAULT_FAULT_NAMES
        assert set(variables) <= set(DEFAULT_SENSOR_UNITS)
        assert help_text.FAULTS[fault].figure, f"fault {fault} has a signature but names no figure"
        # ... and the figure is reproduced, with its own caption and credit.
        assert help_text.FAULTS[fault].illustration in help_text.FIGURES
    for entry in help_text.FAULTS.values():
        assert entry.what and entry.signature and entry.source
    # Every variable has its position in the paper's schematic, and no two share one.
    positions = [entry.position for entry in help_text.VARIABLES.values()]
    assert all(re.fullmatch(r"\d+\.\d+", position) for position in positions)
    assert len(set(positions)) == len(positions)
    # Every event but normal operation and the one added in 2.0.0 has a published
    # confirmation window; normal operation is not an occurrence to confirm.
    assert set(help_text.CONFIRMATION_WINDOWS) == set(DEFAULT_FAULT_NAMES) - {0, 9}


def test_cache_dir_sits_under_the_platform_cache_home(tmp_path: Path, monkeypatch):
    """The catalogue cache goes where this platform keeps caches, named after the app."""
    monkeypatch.setenv(CACHE_HOME, str(tmp_path / "somewhere"))
    assert cache_dir() == tmp_path / "somewhere" / "overlap-viewer"


def test_cache_dir_falls_back_to_the_home_directory(monkeypatch):
    """With no cache home named, the cache still lands somewhere inside the user's home."""
    monkeypatch.delenv(CACHE_HOME, raising=False)
    assert Path.home() in cache_dir().parents


def test_catalogue_scan_wells_and_cache(raw_dir: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setenv(CACHE_HOME, str(tmp_path / "cache"))
    info = ds.DatasetInfo.load(raw_dir)

    seen = []
    catalogue = ds.load_catalogue(info, progress=lambda i, n, name: seen.append((i, n)) or True)
    assert seen[-1] == (5, 5)
    assert list(catalogue["well"]) == [1, 1, 1, 2, 2]
    assert list(catalogue["reach"]) == ["normal", "normal", "normal", "transient", "normal"]
    assert catalogue["n_samples"].tolist() == [7200, 7200, 7200, 3600, 3600]
    assert all(isinstance(p, Path) and p.exists() for p in catalogue["path"])
    assert catalogue["hours"].iloc[3] == pytest.approx((3600 - 1) / 3600)
    # Inside the temporary directory, not in the user's real cache: were the
    # redirection to slip, a cache file left by an earlier run would let every
    # assertion below pass while testing nothing.
    assert ds.cache_path(raw_dir).is_relative_to(tmp_path)
    assert ds.cache_path(raw_dir).exists()

    def no_scan(*args, **kwargs):
        raise AssertionError("the cache should have been used")

    monkeypatch.setattr(ds, "scan_instances", no_scan)
    cached = ds.load_catalogue(info)
    pd.testing.assert_frame_equal(cached.drop(columns="path"), catalogue.drop(columns="path"))

    # Touching a file invalidates the cache and forces a new scan.
    monkeypatch.undo()
    monkeypatch.setenv(CACHE_HOME, str(tmp_path / "cache"))
    path = catalogue["path"].iloc[0]
    path.touch()
    calls = []
    original = ds.scan_instances
    monkeypatch.setattr(ds, "scan_instances", lambda *a, **k: calls.append(1) or original(*a, **k))
    ds.load_catalogue(info)
    assert calls == [1]

    # The label runs come out of the scan (and the cache) as they went in.
    hydrate_runs = segments_from_json(catalogue["class_runs"].iloc[3])
    assert [np.isnan(s.value) or s.value for s in hydrate_runs] == [True, 0.0, 109.0]
    assert hydrate_runs[0].start == hours(0) and hydrate_runs[-1].end == hours(1)

    wells = ds.split_wells(catalogue)
    assert [w.well for w in wells] == [1, 2]
    chain = wells[0]
    assert chain.n_instances == 3 and chain.n_overlapping == 3 and chain.n_lanes == 2
    assert chain.rows["lane"].tolist() == [0, 1, 0]
    assert chain.group(1) == [0, 1, 2]
    assert chain.group(0) == [0, 1]
    # All three windows carry the same label, so joined they are one four-hour bar.
    joined = chain.joined()
    assert joined.n_instances == 1 and joined.members == [[0, 1, 2]] and joined.n_lanes == 1
    assert joined.rows["n_samples"].iloc[0] == 4 * 3600
    assert joined.rows["title"].iloc[0] == "WELL-00001_20170201010000 +2"
    hydrate = wells[1]
    assert hydrate.n_overlapping == 0 and hydrate.n_lanes == 1
    assert hydrate.group(0) == [0]
    assert hydrate.present_colors() == {(9, "transient"), (9, "normal")}
    assert ds.lane_slots(wells, minimum=2, maximum=8) == 2


def test_cancelling_the_scan(raw_dir: Path):
    info = ds.DatasetInfo.load(raw_dir)
    entries = ds.list_real_instances(raw_dir, info.fault_classes)
    assert len(entries) == 5
    with pytest.raises(ds.ScanCancelled):
        ds.scan_instances(entries, progress=lambda i, n, name: False)
