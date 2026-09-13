"""Constants of the viewer: dataset conventions, palettes, layout tunables, cache location.

Everything the dataset itself can state — event names and labels, variable
units, the transient offset — is read from the 3W ``dataset.ini`` at run time
(see ``dataset.DatasetInfo``); the values here are the fallbacks used when the
file is missing, plus everything that is a choice of this viewer rather than a
property of the data.
"""

import os
from pathlib import Path

# -- Dataset conventions (fallbacks for a dataset without ``dataset.ini``) -----

# Event descriptions of 3W 2.0.0, keyed by the label of the fault-class folder.
DEFAULT_FAULT_NAMES: dict[int, str] = {
    0: "Normal Operation",
    1: "Abrupt Increase of BSW",
    2: "Spurious Closure of DHSV",
    3: "Severe Slugging",
    4: "Flow Instability",
    5: "Rapid Productivity Loss",
    6: "Quick Restriction in PCK",
    7: "Scaling in PCK",
    8: "Hydrate in Production Line",
    9: "Hydrate in Service Line",
}

# A transient label is the fault label plus this offset (``[EVENTS]`` section).
DEFAULT_TRANSIENT_OFFSET = 100

# Variables an instance file may carry, in dataset order, with their units.
DEFAULT_SENSOR_UNITS: dict[str, str] = {
    "ABER-CKGL": "%",
    "ABER-CKP": "%",
    "ESTADO-DHSV": "-",
    "ESTADO-M1": "-",
    "ESTADO-M2": "-",
    "ESTADO-PXO": "-",
    "ESTADO-SDV-GL": "-",
    "ESTADO-SDV-P": "-",
    "ESTADO-W1": "-",
    "ESTADO-W2": "-",
    "ESTADO-XO": "-",
    "P-ANULAR": "Pa",
    "P-JUS-BS": "Pa",
    "P-JUS-CKGL": "Pa",
    "P-JUS-CKP": "Pa",
    "P-MON-CKGL": "Pa",
    "P-MON-CKP": "Pa",
    "P-MON-SDV-P": "Pa",
    "P-PDG": "Pa",
    "PT-P": "Pa",
    "P-TPT": "Pa",
    "QBS": "m³/s",
    "QGL": "m³/s",
    "T-JUS-CKP": "°C",
    "T-MON-CKP": "°C",
    "T-PDG": "°C",
    "T-TPT": "°C",
}

# Well operational status codes of the ``state`` column (Table 5 of the 3W
# Dataset 2.0.0 paper); the ini file does not list them.
WELL_STATES: dict[int, str] = {
    0: "Open",
    1: "Shut-In",
    2: "Flushing Diesel",
    3: "Flushing Gas",
    4: "Bullheading",
    5: "Closed With Diesel",
    6: "Closed With Gas",
    7: "Restart",
    8: "Depressurization",
}

# The two label columns of an instance; every other column is a sensor.
LABEL_COLUMNS = ("class", "state")

# Variables that carry the visual signature of an event, i.e. the ones whose
# joint behavior an expert reads to recognize it. Each entry reproduces the
# variable set of the corresponding example figure of the 3W Dataset 2.0.0
# paper (https://doi.org/10.1038/s41597-026-07225-z), which is why only the
# events illustrated there — figures 3 to 7 — have a signature: the remaining
# ones have no published reference set to copy.
FAULT_SIGNATURES: dict[int, tuple[str, ...]] = {
    0: ("ABER-CKP", "ESTADO-SDV-P", "ESTADO-W1", "T-TPT"),  # figure 7
    2: ("P-MON-CKP", "P-PDG", "P-TPT", "T-TPT"),  # figure 3
    3: ("P-MON-CKP", "P-PDG", "P-TPT", "T-JUS-CKP"),  # figure 6
    6: ("ABER-CKP", "P-MON-CKP", "P-PDG", "P-TPT"),  # figure 4
    8: ("P-MON-CKP", "P-PDG", "P-TPT", "T-TPT"),  # figure 5
}

# Filename prefix of the instances recorded on a physical well. Simulated and
# hand-drawn instances have no well to overlap on and are ignored.
REAL_PREFIX = "WELL-"

# -- Palettes ------------------------------------------------------------------

# One hue per fault-class folder. Normal is green; the faults get distinct
# categorical colors.
FAULT_COLORS: dict[int, str] = {
    0: "#4c9e4c",
    1: "#1f77b4",
    2: "#ff7f0e",
    3: "#d62728",
    4: "#9467bd",
    5: "#8c564b",
    6: "#e377c2",
    7: "#7f7f7f",
    8: "#bcbd22",
    9: "#17becf",
}
FALLBACK_FAULT_COLOR = "#555555"  # a folder the palette does not know

# Colors of the well operational status band; ``None`` stands for unknown.
STATE_COLORS: dict[int | None, str] = {
    None: "#d9d9d9",
    0: "#4c9e4c",
    1: "#d95f5f",
    2: "#c9a227",
    3: "#8f7ee6",
    4: "#5fa8d3",
    5: "#e6a23c",
    6: "#7f8c8d",
    7: "#3fbf9f",
    8: "#d47fb8",
}

# Unlabeled stretches: a pale grey, hatched with these strokes. Grey alone
# would read as one more class — two of the fault hues are themselves grey —
# so the texture, not the shade, is what says "nothing is known here".
UNKNOWN_LABEL_COLOR = "#e9e9e9"
HATCH_COLOR = "#8a8a8a"

# How far the fault developed inside an instance fixes the tint of its bar:
# full hue once the steady fault state is labeled, lighter when only the
# transient is, lightest when the window never leaves normal operation.
REACH_TINTS: dict[str, float] = {"steady": 1.00, "transient": 0.55, "normal": 0.25}
REACH_LABELS: dict[str, str] = {
    "steady": "steady state reached",
    "transient": "transient state reached",
    "normal": "no fault reached",
}

# The time series plots shade their background with the same hues and the same
# three-step ladder, compressed toward white so the trace stays legible; the
# band above each plot carries the exact bar colors.
BACKGROUND_TINTS: dict[str, float] = {"steady": 0.62, "transient": 0.38, "normal": 0.18}

# Line color of a time series; saturated, since it sits on tinted backgrounds.
TRACE_COLOR = "#1f4e79"

# -- Layout ---------------------------------------------------------------------

# A silence at least this long splits a well's recording into two bursts, and
# the overview collapses every silence to a fixed narrow blank (see
# ``timemap.TimeMap``); in total the blanks get this share of the axis.
DEFAULT_GAP_HOURS = 12.0
GAP_SHARE = 0.12

# Bars taller than this share of a stack level would touch their neighbours.
BAR_HEIGHT = 0.62

# Room between two well plots of the overview grid, in pixels: enough that the
# dates under one plot are not read as the title of the next.
GRID_SPACING = (14, 20)  # (horizontal, vertical)

# Every well timeline shows at least this many stack levels, and at most this
# many before growing taller, so the grid stays comparable across wells.
MIN_LANE_SLOTS = 2
MAX_LANE_SLOTS = 8

# A signal whose range is this small relative to its own level counts as flat
# and is drawn on a padded axis instead of being autoscaled into noise.
FLAT_SPAN = 1e-4

# Loaded instances kept in memory across windows, in samples.
FRAME_CACHE_ROWS = 6_000_000

# -- Locating the dataset ---------------------------------------------------------

# Environment variable naming the dataset root (shared with the flowml pipeline).
RAW_DIR_ENV = "FLOWML_RAW_DATA_DIR"

# Where the dataset usually sits relative to the working directory: next to a
# checkout of this project (``../3W/dataset``) or inside the 3W repository.
RAW_DIR_CANDIDATES = (Path("../3W/dataset"), Path("dataset"), Path("3W/dataset"))


# Illustrations the help window shows. They live in the project's docs
# directory; a copy inside the package is looked for first, so that an
# installed distribution can carry them without the docs tree.
ASSET_DIRS = (
    Path(__file__).resolve().parent / "assets",
    Path(__file__).resolve().parents[2] / "docs" / "assets",
)


def asset_path(name: str) -> Path | None:
    """Locate one illustration, or ``None`` when it is not shipped.

    The help degrades to text when an image is missing rather than breaking,
    so a checkout without the docs directory still opens.
    """
    for directory in ASSET_DIRS:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def cache_dir() -> Path:
    """Directory of the catalogue cache, following the platform's conventions."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "overlap-viewer"
