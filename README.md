# 3W Overlap Viewer

A desktop GUI to inspect how the **real instances of a well overlap in time** in the
[Petrobras 3W dataset](https://github.com/petrobras/3W), and how their fault labels differ.

3W stores one parquet file per instance. The real instances of a well are windows cut from the
same continuous recording, so many of them overlap: the shared samples enter a dataset twice, and
under two different labels, since the end of one instance is often the start of the next. Before
anything can be done about that, one has to see it. This viewer shows it.

![Overview window](docs/assets/overview.png)

## What it shows

**Overview window** — a grid of plots, one per well. Every real instance recorded on the well is a
bar from its first to its last timestamp; instances that overlap in time are stacked on top of each
other (the row is the *stack level*), so a well recorded twice shows at a glance. The months of
silence between bursts of recording are collapsed to narrow dashed blanks, and the time scale is
uniform everywhere else: a bar's length is a duration and two bars overlap on screen exactly when
the instances overlap in time. Untick *Compress silences* for a true calendar axis.

- **Hover** a bar: it gets a heavy outline, every instance of the well that overlaps it gets a
  lighter one, the stretch they share is hatched, every other bar fades, and the status bar names
  the instance, its fault, how far the fault got, its time span, size, stack level and partners.
  The colors those instances carry light up in the key above the grid, and the rest dim, so the
  color under the pointer can be named without leaving the plot.
- **Click** a bar: an instance window opens with the time series of that instance and of every
  instance it overlaps.
- **Click a color in the key**: the grid shows only the wells that recorded that fault. Clicking it
  again, or the button that appears at the right of the toolbar, brings every well back.
- **Retract the key** by clicking its title (or `Ctrl+L`) to give the grid the room. Retracted it
  still answers hovering: the entries of the instance under the pointer, and of the instances it
  overlaps, pop into the title row.
- **Drag** to pan, **Ctrl + wheel** to zoom (the plain wheel scrolls the grid), **right-click** for
  pyqtgraph's menu (view all, export).
- The toolbar sets the number of columns, filters the grid to the wells that have overlaps, sorts
  wells by number, overlapping instances, instances or deepest pile-up, rescans the dataset, and
  opens the help (**F1**).

**Instance window** — one block per instance, stacked chronologically on a shared time axis, so the
overlapping stretches line up vertically. Each block has a header line, the well operational status
(`state`) and the label (`class`) as thin bands, then one plot per selected feature. A band at the
top marks the stretches recorded by two or more of the instances shown.

![Instance window](docs/assets/instance_window.png)

- **Features** are chosen with the checkboxes on the left (features none of the instances recorded
  are greyed out). By default only the first feature in alphabetical order among the recorded ones
  is plotted.
- **Signature** ticks, in one click, the handful of variables whose joint behaviour identifies the
  event — the ones the 3W paper puts on its example figures. Only the five events it illustrates
  have one (Normal Operation, Spurious Closure of DHSV, Severe Slugging, Quick Restriction in PCK,
  Hydrate in Production Line); for any other the box is disabled and says why. The screenshot above
  is the severe-slugging signature: four variables cycling in phase, as figure 6 of the paper
  describes.
- All plots **share the time axis**, and the plots of one feature **share their value axis** across
  instances, so the same reading is at the same height everywhere.
- A **crosshair** follows the pointer through every plot; the status bar gives the time under it and,
  per instance, the label, the operational status and the selected readings at that time.
- Each plot reports the total variation of the signal (Δ = max − min, marked *flat* for a frozen
  sensor) and the share of samples carrying a reading. A sensor never moving is held on a padded
  axis instead of being autoscaled into noise.

Both windows are interactive counterparts of the stage-0 figures of the `flowml` pipeline:
`faults_per_well.pdf` and `fault_<n>_real_instances.pdf`.

**Help** (`F1` in either window) explains what is on screen, from the 3W papers in
[`docs/papers/`](docs/papers): every class label and what the literature says it does to the
readings, every variable and where in the production system it is measured, every well operational
status, and how to work the two windows. Two schematics of the production system illustrate it.
Where the papers describe no signature for an event, the help says so rather than inventing one.

![Help window](docs/assets/help.png)

## Color code

A bar's hue is the **fault-class folder** the instance comes from, and its tint says how far the
fault developed inside that window: full strength once the steady fault state is labeled, lighter
when only the transient state is, lightest when the window never leaves normal operation (43 of the
instances filed under *Hydrate in Service Line* never do). Normal instances (folder 0) stay full
strength. The legend above the grid keys every color actually drawn, one swatch per fault and
reach.

In the instance window the `class` band carries these exact colors (a normal stretch of a fault
instance has the *no fault reached* tint of that fault, a transient stretch the *transient* tint,
and so on), and the plot backgrounds use the same hues on the same three-step ladder, compressed
toward white so the trace stays legible. Unlabeled stretches are grey; the `state` band uses one
color per operational status.

A fault that appears at several tints is a gradient, and its steps are only readable side by side,
so the key gives such a group a row of its own; faults that draw a single color flow together on
the remaining rows, on a fixed column pitch so that entries line up down the rows.

Stretches the experts left unlabeled are hatched rather than merely grey: two of the fault hues are
themselves grey, and a texture says *nothing is known here* where one more shade would just read as
one more class.

## Running

Requires Python 3.11 or newer, [uv](https://docs.astral.sh/uv/) and a local copy of the 3W dataset.

```bash
cd app                     # this directory
uv sync                    # creates .venv with PySide6, pyqtgraph, pandas, numpy, pyarrow
uv run overlap-viewer --raw-dir /path/to/3W/dataset
```

From the root of the `flow-assurance-ml` repository the same is `uv run --project app overlap-viewer`.
Without `--raw-dir`, the dataset is taken from the `FLOWML_RAW_DATA_DIR` environment variable, then
from `../3W/dataset`, `dataset` or `3W/dataset` relative to the working directory; if none holds a
dataset, a folder dialog asks for it. `uv run main.py` and `uv run python -m overlap_viewer` are
equivalent entry points.

| Option | Default | Meaning |
| ------ | ------- | ------- |
| `--raw-dir PATH` | see above | root of the 3W dataset (the folder holding `0/` … `9/` and `dataset.ini`) |
| `--columns N` | 2 | plots per row of the overview (1 to 4) |
| `--gap-hours H` | 12 | a silence at least this long splits a well's recording into two bursts |
| `--no-cache` | off | read every instance again instead of using the cached catalogue |

The first launch reads the time span and labels of every real instance (about 5 s for the 1,119
instances of 3W 2.0.0, behind a progress dialog) and caches the result under the platform cache
directory (`~/.cache/overlap-viewer/` on Linux). Later launches validate the cache against the
files' sizes and modification times and start instantly; any changed, added or removed file
triggers a fresh scan, as does the *Rescan dataset* button.

Only real instances (`WELL-*` files) are shown: simulated and hand-drawn instances have no well to
overlap on.

## Layout

```
app/
├── pyproject.toml            standalone uv project (package overlap_viewer, script overlap-viewer)
├── main.py                   runs the viewer from a checkout without installing
├── docs/
│   ├── assets/               screenshots · the platform schematics the help shows
│   └── papers/               the 3W data articles and the thesis the help draws on
├── tests/test_backend.py     backend tests on a synthetic miniature of the 3W layout
└── src/overlap_viewer/
    ├── config.py             dataset fallbacks · palettes · signatures · layout · cache location
    ├── dataset.py            dataset.ini · instance catalogue and its cache · overlaps per well
    ├── timemap.py            gap-compressed (or calendar) time axis in hours
    ├── labels.py             label kinds and names · runs · feature statistics · coverage counts
    ├── palette.py            fault hues tinted by reach · legend entries
    ├── help_text.py          what the help says: classes, variables, statuses, usage
    ├── loading.py            progress dialog · cache of loaded instances
    ├── items.py              pyqtgraph items: segments, instance bars, time axis, anchored text
    ├── legend.py             the clickable color key and its flow layout
    ├── help.py               the help window
    ├── overview.py           the grid of well timelines
    ├── instance_window.py    the time series of a group of overlapping instances
    └── app.py                command line and start-up
```

The backend (`config`, `dataset`, `timemap`, `labels`, `palette`, `help_text`) depends on pandas,
numpy and pyarrow only, and reads what the dataset states about itself from `dataset.ini` (event
names and labels, the transient offset, variable units), with built-in fallbacks for 3W 2.0.0. The
frontend is PySide6 and pyqtgraph. The lane-packing rule that stacks the instances is the one the
`flowml` pipeline uses to drop overlapping instances: what the overview shows on stack level 2 or
higher is exactly what the pipeline removes by default.

The help text and the signature variables come from the 3W Dataset 2.0.0 data article
([doi:10.1038/s41597-026-07225-z](https://doi.org/10.1038/s41597-026-07225-z)); its figures 3 to 7
are the source of the five published signatures.

## Development

```bash
uv sync --all-groups       # adds pytest and ruff
uv run pytest
uv run ruff check . && uv run ruff format .
```

Tests cover the backend only; the widgets were checked by rendering them offscreen
(`QT_QPA_PLATFORM=offscreen`) against the full dataset.
