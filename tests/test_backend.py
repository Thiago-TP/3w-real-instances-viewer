"""Backend tests on a synthetic miniature of the 3W layout; no Qt involved."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from overlap_viewer import dataset as ds
from overlap_viewer import help_text
from overlap_viewer.config import (
    DEFAULT_FAULT_NAMES,
    DEFAULT_SENSOR_UNITS,
    FAULT_SIGNATURES,
    WELL_STATES,
    asset_path,
)
from overlap_viewer.labels import (
    coverage_counts,
    fault_reach,
    feature_stats,
    label_kind,
    label_name,
    label_segments,
    padded_range,
    runs,
)
from overlap_viewer.legend import row_breaks
from overlap_viewer.palette import bar_color, legend_entries, legend_key, tint
from overlap_viewer.timemap import TimeMap

T0 = pd.Timestamp("2017-02-01 01:00:00")


def hours(h: float) -> pd.Timestamp:
    return T0 + pd.Timedelta(hours=h)


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
    for entry in help_text.FAULTS.values():
        assert entry.what and entry.signature and entry.source
    # Every event but normal operation and the one added in 2.0.0 has a published
    # confirmation window; normal operation is not an occurrence to confirm.
    assert set(help_text.CONFIRMATION_WINDOWS) == set(DEFAULT_FAULT_NAMES) - {0, 9}


def test_catalogue_scan_wells_and_cache(raw_dir: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setattr(ds.os, "name", "posix")
    info = ds.DatasetInfo.load(raw_dir)

    seen = []
    catalogue = ds.load_catalogue(info, progress=lambda i, n, name: seen.append((i, n)) or True)
    assert seen[-1] == (5, 5)
    assert list(catalogue["well"]) == [1, 1, 1, 2, 2]
    assert list(catalogue["reach"]) == ["normal", "normal", "normal", "transient", "normal"]
    assert catalogue["n_samples"].tolist() == [7200, 7200, 7200, 3600, 3600]
    assert all(isinstance(p, Path) and p.exists() for p in catalogue["path"])
    assert catalogue["hours"].iloc[3] == pytest.approx((3600 - 1) / 3600)
    assert ds.cache_path(raw_dir).exists()

    def no_scan(*args, **kwargs):
        raise AssertionError("the cache should have been used")

    monkeypatch.setattr(ds, "scan_instances", no_scan)
    cached = ds.load_catalogue(info)
    pd.testing.assert_frame_equal(cached.drop(columns="path"), catalogue.drop(columns="path"))

    # Touching a file invalidates the cache and forces a new scan.
    monkeypatch.undo()
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    path = catalogue["path"].iloc[0]
    path.touch()
    calls = []
    original = ds.scan_instances
    monkeypatch.setattr(ds, "scan_instances", lambda *a, **k: calls.append(1) or original(*a, **k))
    ds.load_catalogue(info)
    assert calls == [1]

    wells = ds.split_wells(catalogue)
    assert [w.well for w in wells] == [1, 2]
    chain = wells[0]
    assert chain.n_instances == 3 and chain.n_overlapping == 3 and chain.n_lanes == 2
    assert chain.rows["lane"].tolist() == [0, 1, 0]
    assert chain.group(1) == [0, 1, 2]
    assert chain.group(0) == [0, 1]
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
