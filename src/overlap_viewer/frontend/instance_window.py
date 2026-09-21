"""The instance window: time series of an instance and of every instance it overlaps.

One block per instance, stacked chronologically on a shared time axis so the
overlapping stretches line up vertically: a header line, the well operational
status and the label as thin bands (the label band in the exact colors of the
overview bars), then one plot per selected feature, its background shaded by
label on the same color ladder. The plots of one feature share their y axis
across instances, every plot shares the x axis, and a crosshair follows the
pointer through all of them. An interactive counterpart of the
``fault_<n>_real_instances.pdf`` pages of the stage-0 figures.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import NamedTuple

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from overlap_viewer.algorithms.interpolation import (
    GENUINE,
    describe_sampling,
    sample_kinds,
    sampling_of,
)
from overlap_viewer.algorithms.spectral import (
    Histogram,
    Spectrum,
    format_period,
    histogram,
    lomb_scargle,
    prepare,
    prepare_irregular,
    uniform_series,
    welch,
)
from overlap_viewer.backend import theme
from overlap_viewer.backend.availability import implausible_sensors, outside_range
from overlap_viewer.backend.config import (
    BEST_EFFORT_SOURCES,
    REACH_LABELS,
    plausible_range,
    signature_of,
)
from overlap_viewer.backend.dataset import DatasetInfo, WellData, instance_title, merge_instances
from overlap_viewer.backend.labels import (
    FeatureStats,
    Segment,
    at_index_unit,
    coverage_counts,
    feature_stats,
    format_delta,
    label_fault,
    label_kind,
    label_name,
    label_segments,
    merge_label_runs,
    padded_range,
    segments_from_json,
    sensor_columns,
    sensor_stats_from_json,
    state_name,
)
from overlap_viewer.backend.model_outputs import agrees
from overlap_viewer.backend.palette import (
    background_color,
    bar_color,
    legend_label,
    state_color,
    tint,
    unknown_background,
)
from overlap_viewer.backend.timemap import TimeMap
from overlap_viewer.frontend.help import HelpWindow
from overlap_viewer.frontend.items import (
    AnchoredText,
    HeaderLabel,
    ScrollFriendlyViewBox,
    SeamsItem,
    SegmentsItem,
    TimeAxisItem,
    WheelToParent,
)
from overlap_viewer.frontend.loading import FrameCache
from overlap_viewer.frontend.overview import ElidedLabel
from overlap_viewer.frontend.spectral_items import (
    PeriodMarker,
    TransformControls,
    add_center_lines,
    add_spectrum_curve,
    add_stacked_bars,
    caption_for,
    format_width,
    period_range,
    power_axis,
    power_label,
    set_log_period_axis,
    shade_implausible,
    shade_unresolved,
    spectrum_grid,
    spectrum_xy,
)
from overlap_viewer.frontend.traces import add_trace

AXIS_WIDTH = 84  # every left axis has this width, so all plots share the same x pixels
PANEL_WIDTH = 200  # the feature panel: room for the longest variable name and its unit
SIDE_PX = (
    210  # the column beside the traces: a marginal histogram, or a spectrum turned on its side
)
BAND_PX = 18
HEADER_PX = 24
PLOT_MIN_PX = 150
AXIS_PX = 28
ROW_SPACING = 2  # between two rows of one instance block
BLOCK_SPACING = 16  # added above the header of every block but the first
SI_UNITS = ("Pa",)  # units pyqtgraph may prefix (kPa, MPa); the others stay literal
STRETCH_DELAY_MS = 150  # a pan or zoom settles this long before the stretch views are recounted

# The views of a signal beyond its time series, in the order of the toolbar.
# There was a third, a spectrogram under each trace on the shared time axis. It
# was dropped: it earned its place only over a merged recording of days, where
# the slugging period drifts, and everywhere else it said what the spectrum
# beside it already said while taking a row of its own from every feature of
# every block, which is the scarce thing in a window that stacks them.
DOTS_TIP = (
    "Mark, on every trace, the samples the plant's PI historian actually archived: they are drawn "
    "as dots in the full color, and the line through every sample, which between two dots is "
    "exactly the straight line the historian drew, runs faint beneath them. Dense dots are a "
    "sensor read every second, sparse dots on a faint line a sensor read every two minutes and "
    "filled in between. Untick for the plain line, which is what the file holds and what a "
    "pipeline reads; the figures beside each plot go on saying how much of it was measured. A "
    "valve state is never tested and has no dots either way."
)
VIEWS = ("distribution", "spectrum")
VIEW_NAMES = {"distribution": "Distribution", "spectrum": "Spectrum"}
VIEW_TIPS = {
    "distribution": (
        "A histogram of the readings to the right of every trace, turned on its side so that it "
        "shares the trace's value axis: a reading is at the same height in both. The bars are "
        "stacked by label period in the class colors, so how the fault moves the distribution is "
        "read inside one instance. Counted over the stretch of time on screen, so zooming is "
        "brushing; readings outside the plausible range are left out and counted in the caption. "
        "A bimodal shape is an oscillation."
    ),
    "spectrum": (
        "The power spectral density of the trace against the period, both logarithmic, over the "
        "stretch of time on screen: Welch's estimate with the window chosen, the mean and the "
        "linear trend removed first, the missing samples interpolated. The caption gives the "
        "dominant period and its share of the power (a few percent for a normal instance, half "
        "or more for an oscillating one), and one cycle of that period is laid against the trace, "
        "so the claim can be checked against the waves. It takes a row under the trace, the "
        "period along the bottom. With 'Measurements only' ticked it is the Lomb-Scargle "
        "periodogram of the measurements at their own instants, the historian's lines left out."
    ),
}

HINT = (
    "Tick features to add their plots | drag to pan | Ctrl + wheel to zoom (the wheel alone "
    "scrolls) | plots share the time axis, and the plots of one feature share their value axis"
)


class BandSegments(NamedTuple):
    """The stretches of one band: where they are, their color, name and texture.

    ``hatched`` marks the stretches nothing is known about, which are drawn
    with a texture rather than with yet another shade of grey.
    """

    x0: list[float]
    x1: list[float]
    colors: list[str]
    labels: list[str]
    hatched: list[bool]

    def add(self, x0: float, x1: float, color: str, label: str, hatched: bool) -> None:
        self.x0.append(float(x0))
        self.x1.append(float(x1))
        self.colors.append(color)
        self.labels.append(label)
        self.hatched.append(hatched)


class PlotStack(WheelToParent, pg.GraphicsLayoutWidget):
    """The stack of plots, scrolled by the plain wheel and zoomed by Ctrl + wheel."""


@dataclass
class StretchPanel:
    """The views of one feature of one block that are counted over the stretch of time on screen.

    The histogram and the spectrum answer for whatever the time axis shows, so
    a pan or a zoom recounts them; the items they drew last time are kept so
    that they can be taken down first.
    """

    position: int
    feature: str
    unit: str
    bounds: tuple[float, float]
    hist_plot: pg.PlotItem | None = None
    spec_plot: pg.PlotItem | None = None
    hist_items: list = field(default_factory=list)
    spec_items: list = field(default_factory=list)
    hist_note: AnchoredText | None = None
    spec_note: AnchoredText | None = None
    peak: PeriodMarker | None = None  # one dominant period laid against the trace
    histogram: Histogram | None = None
    spectrum: Spectrum | None = None


class Blocks(NamedTuple):
    """One drawing of a window's group: per block, its row, its instances and its colors.

    ``members`` are positions in the well's own instance table, whether the
    block is one instance or several merged, so everything a block is drawn
    from is reached the same way either way.
    """

    rows: pd.DataFrame
    members: list[list[int]]
    colors: list[list[tuple[int, str]]]

    @classmethod
    def of(cls, view: WellData, positions) -> "Blocks":
        positions = list(positions)
        return cls(
            view.rows.iloc[positions].reset_index(drop=True),
            [view.members[position] for position in positions],
            [view.colors[position] for position in positions],
        )

    def block_of(self, instance: int) -> int:
        """Which block draws one instance of the well."""
        for position, behind in enumerate(self.members):
            if instance in behind:
                return position
        raise ValueError(f"instance {instance} is not drawn here")


class InstanceWindow(QMainWindow):
    """Time series of one bar of the overview and of every bar it overlaps.

    One block per bar. A bar is one instance, or one merged recording: its
    instances read as the single continuous stretch they were cut from, drawn
    as one series over one set of bands, with a dashed line where each further
    instance begins. A window's unlabeled head is usually labeled by the window
    before it, so a merged ``class`` band carries far less *Unknown* than the
    instances did separately, and the blocks stay tall enough to read where a
    dozen thin slices would not.

    **The group a window opens on is all it is ever about.** Its own *Join
    overlapping instances* merges exactly the instances on screen and no
    others, so it answers what this group alone amounts to rather than what the
    whole well does; two of them that overlap only through an instance outside
    the window stay apart. A window opened from a bar the overview had already
    merged is showing that merge and has nothing of its own left to do, so its
    checkbox is ticked and disabled.
    """

    def __init__(
        self,
        data: WellData,
        index: int,
        info: DatasetInfo,
        frames: FrameCache,
        passes=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.info = info
        self._frames = frames
        # The passes over the data, when the main window shares them: the
        # Toolkit's rule on the instances shown, if a page has fitted it, and
        # the model outputs loaded, drawn as a band under the class band.
        self._passes = passes
        self._model_results = passes.model if passes is not None else None
        self.well = data.origin
        # The instance the window is about, kept across a switch: the one
        # clicked, or the first of the bar clicked, which is the one its title
        # names.
        self.subject = data.members[index][0]

        # The group is fixed here and never grows: the bars the overview would
        # have shown for this click, and the instances behind them. The two
        # drawings of it are built now, from the well's instance table alone:
        # nothing outside this window is read again or written to, so joining
        # here moves neither the grid nor another window.
        shown = Blocks.of(data, data.group(index))
        if data.joined_view:
            # Already merged outside, and by the same rule: this window is
            # showing that merge, and has nothing of its own left to join.
            self._plain, self._merged = None, shown
        else:
            self._plain = shown
            local = self.well.joined(among=[members[0] for members in shown.members])
            self._merged = Blocks.of(local, range(local.n_instances))
        self._joinable = self._plain is not None and len(self._merged.rows) < len(self._plain.rows)

        self._checks: dict[str, QCheckBox] = {}
        self._features_shown = True
        self._views: dict[str, QCheckBox] = {}
        self._plots: dict[tuple[int, str], pg.PlotItem] = {}
        self._time_plots: list[pg.PlotItem] = []  # every plot on the shared time axis
        self._stretch_panels: list[StretchPanel] = []
        self._feature_masters: dict[str, pg.PlotItem] = {}
        self._crosshairs: list[pg.InfiniteLine] = []
        self._master: pg.PlotItem | None = None
        self._x_range: tuple[float, float] | None = None
        self._help: HelpWindow | None = None
        self._stretch_timer = QTimer(self)
        self._stretch_timer.setSingleShot(True)
        self._stretch_timer.setInterval(STRETCH_DELAY_MS)
        self._stretch_timer.timeout.connect(self._refresh_stretch)

        self._adopt(self._plain is None)
        self._build_ui()
        self._rebuild()

    # -- data

    def _adopt(self, joined: bool) -> None:
        """Take one of the two drawings of the group, and read what its blocks need."""
        blocks = self._merged if joined else self._plain
        self.joined = joined
        self.rows = blocks.rows
        self.members = blocks.members
        self.colors = blocks.colors
        self.clicked = blocks.block_of(self.subject)
        self.merged = any(len(members) > 1 for members in self.members)
        self._noun = "recording" if self.merged else "instance"
        self.timemap = TimeMap.build(self.rows["start"], self.rows["end"], compressed=False)

        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            paths = self.well.rows["path"]
            self.frames = [
                merge_instances([self._frames.get(paths.iloc[m]) for m in members])
                for members in self.members
            ]
        finally:
            QApplication.restoreOverrideCursor()
        self._seams = [self._seam_positions(members) for members in self.members]
        self._groups_cache: dict[int, tuple[np.ndarray, list]] = {}
        self._kinds_cache: dict[tuple[int, str], np.ndarray | None] = {}
        self._features = self._feature_table()
        self._signature = self._signature_for_group()

        others = len(self.rows) - 1
        self.setWindowTitle(
            f"{self.well.label} | {instance_title(self.rows.iloc[self.clicked])}"
            + (
                f" and {others} overlapping {self._noun}{'s' if others > 1 else ''}"
                if others
                else ""
            )
        )

    def set_joined(self, joined: bool) -> None:
        """Draw this group as its instances, or as the merged recordings they make up.

        The same instances either way, regrouped: this window only, and nothing
        is brought in from outside it. The overview and any other instance
        window keep whatever they were showing.

        A window opened on a bar the overview had already merged has no drawing
        of the instances apart to switch to, and says so rather than trying.
        """
        if joined == self.joined or (self._merged if joined else self._plain) is None:
            self._sync_join_check()  # a switch the window has nothing to switch to
            return
        selected = set(self.selected_features())
        self._adopt(joined)
        self._x_range = None  # the axis spans a different stretch of time now
        self._sync_join_check()
        self._swap_feature_panel(selected)
        self._restyle()
        self._relayout()

    def _sync_join_check(self) -> None:
        self._join_check.blockSignals(True)
        self._join_check.setChecked(self.joined)
        self._join_check.blockSignals(False)

    def set_model_results(self, results) -> None:
        """Take the model outputs loaded (or none) and draw, or take down, their band."""
        self._model_results = results
        self._header.setText(self._header_html())
        self._rebuild()

    def _seam_positions(self, members: list[int]) -> list[float]:
        """Where, inside one merged block, each instance after the first begins."""
        if len(members) < 2:
            return []
        starts = self.well.rows["start"].iloc[members[1:]]
        return [float(x) for x in self.timemap.to_x(starts)]

    def _feature_table(self) -> pd.DataFrame:
        """Every sensor the dataset or the files declare, alphabetically, with how many blocks record it.

        ``implausible`` counts the blocks in which the sensor reads outside its
        plausible range, from the figures the catalogue holds for their instances.
        """
        names = set(self.info.sensor_names)
        for frame in self.frames:
            names.update(sensor_columns(frame))
        flagged: dict[str, int] = {}
        origin = self.well.rows
        if "sensor_stats" in origin.columns:
            for members in self.members:
                in_block: set[str] = set()
                for member in members:
                    stats = sensor_stats_from_json(str(origin.iloc[member]["sensor_stats"]))
                    in_block.update(implausible_sensors(stats, self.info))
                for name in in_block:
                    flagged[name] = flagged.get(name, 0) + 1
        rows = []
        for name in sorted(names):
            recorded = sum(
                1 for frame in self.frames if name in frame.columns and frame[name].notna().any()
            )
            rows.append({"sensor": name, "recorded": recorded, "implausible": flagged.get(name, 0)})
        return pd.DataFrame(rows)

    def _default_feature(self) -> str | None:
        recorded = self._features[self._features["recorded"] > 0]
        return str(recorded["sensor"].iloc[0]) if len(recorded) else None

    def selected_features(self) -> list[str]:
        return [name for name, check in self._checks.items() if check.isChecked()]

    def select_features(self, names: Sequence[str]) -> None:
        """Tick exactly ``names`` (those recorded here) and draw them; what another page asked for."""
        wanted = set(names)
        for name, check in self._checks.items():
            check.blockSignals(True)
            check.setChecked(name in wanted and check.isEnabled())
            check.blockSignals(False)
        self._rebuild()

    def _flagged_sensors(self, position: int) -> list[str]:
        """The sensors reading outside their plausible range in any instance behind one block."""
        origin = self.well.rows
        if "sensor_stats" not in origin.columns:
            return []
        names: list[str] = []
        for member in self.members[position]:
            stats = sensor_stats_from_json(str(origin.iloc[member]["sensor_stats"]))
            names += [name for name in implausible_sensors(stats, self.info) if name not in names]
        return names

    def _fault_of(self, position: int) -> int:
        return int(self.rows.iloc[position]["fault_class"])

    def _signature_for_group(self) -> tuple[int, tuple[str, ...], bool] | None:
        """The signature this window can offer, if any: the fault, its variables, published or not.

        The clicked block decides, since the window was opened from it: the
        event a merged one develops furthest, which is the event its bar is
        outlined with. Only when that fault has no signature at all does the
        window fall back to another fault present, and only if exactly one such
        fault is, so the box never silently mixes two events' variables.
        """
        clicked = self._fault_of(self.clicked)
        known = signature_of(clicked)
        if known is not None:
            return clicked, *known
        others = {
            fault
            for fault in {self._fault_of(i) for i in range(len(self.rows))}
            if signature_of(fault) is not None
        }
        if len(others) == 1:
            fault = others.pop()
            return fault, *signature_of(fault)
        return None

    def _signature_features(self) -> list[str]:
        """The signature variables at least one of these blocks actually recorded."""
        if self._signature is None:
            return []
        recorded = set(self._features.loc[self._features["recorded"] > 0, "sensor"])
        return [name for name in self._signature[1] if name in recorded]

    # -- construction

    def _build_ui(self) -> None:
        toolbar = QToolBar("View")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        reset = QAction("Reset view", self)
        reset.setShortcut("Ctrl+R")
        reset.triggered.connect(self.reset_view)
        toolbar.addAction(reset)
        help_action = QAction("Help", self)
        help_action.setShortcut("F1")
        help_action.setToolTip("What every fault class and every variable means (F1)")
        help_action.triggered.connect(self.show_help)
        toolbar.addAction(help_action)
        close = QAction("Close", self)
        close.setShortcuts(["Esc", "Ctrl+W"])
        close.triggered.connect(self.close)
        toolbar.addAction(close)
        toolbar.addSeparator()
        toolbar.addWidget(self._build_join_check())
        toolbar.addSeparator()
        self._show_features = QAction("Features", self)
        self._show_features.setCheckable(True)
        self._show_features.setChecked(True)
        self._show_features.setToolTip(
            "Show or hide the feature panel on the left, to give the plots its width"
        )
        self._show_features.toggled.connect(self._on_features_toggled)
        toolbar.addAction(self._show_features)
        # The views and their parameters get a row of their own: on one row
        # with the rest they fell behind the toolbar's overflow chevron as soon
        # as the window was narrower than a screen.
        self.addToolBarBreak()
        views_bar = QToolBar("Views")
        views_bar.setMovable(False)
        self.addToolBar(views_bar)
        views_bar.addWidget(QLabel(" Views "))
        for view in VIEWS:
            check = QCheckBox(VIEW_NAMES[view])
            check.setToolTip(VIEW_TIPS[view])
            check.toggled.connect(self._on_view_toggled)
            self._views[view] = check
            views_bar.addWidget(check)
        self._dots_check = QCheckBox("Measurement dots")
        self._dots_check.setChecked(True)
        self._dots_check.setToolTip(DOTS_TIP)
        self._dots_check.toggled.connect(self._rebuild)
        views_bar.addWidget(self._dots_check)
        views_bar.addSeparator()
        self._controls = TransformControls()
        self._controls.changed.connect(self._rebuild)
        views_bar.addWidget(self._controls)
        self._sync_controls()

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(8, 4, 8, 4)
        outer.setSpacing(4)
        self._header = QLabel(self._header_html())
        self._header.setTextFormat(Qt.TextFormat.RichText)
        self._header.setWordWrap(True)
        outer.addWidget(self._header)

        self._body = QHBoxLayout()
        body = self._body
        body.setSpacing(8)
        self._panel = self._build_feature_panel()
        self._panel.setVisible(self._features_shown)
        body.addWidget(self._panel)
        self._layout_widget = PlotStack()
        self._layout_widget.ci.layout.setVerticalSpacing(ROW_SPACING)
        self._layout_widget.ci.setContentsMargins(0, 0, 0, 0)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setWidget(self._layout_widget)
        body.addWidget(self._scroll, 1)
        outer.addLayout(body, 1)
        self.setCentralWidget(central)

        self._status = ElidedLabel(HINT)
        self.statusBar().addWidget(self._status, 1)
        self._layout_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)
        self._restyle()
        self.resize(1360, 860)

    def _restyle(self) -> None:
        """Take the colors of the theme now in force, for the chrome outside the plots."""
        colors = theme.current()
        self._layout_widget.setBackground(colors.plot_background)
        self._note.setStyleSheet(f"color: {colors.muted}; font-size: 8pt;")
        self._header.setText(self._header_html())

    def apply_theme(self) -> None:
        """Repaint this window in the theme now in force.

        The stack is laid out again rather than recolored: pyqtgraph fixes the
        colors of an axis when it is built, and every plot here is thrown away
        and rebuilt whenever the feature selection changes anyway.
        """
        self._restyle()
        if self._help is not None:  # its swatches carry the colors of the old theme
            self._help.close()
            self._help.deleteLater()
            self._help = None
        self._rebuild()

    # -- the views

    @property
    def dots_shown(self) -> bool:
        """Whether a trace marks the samples the historian actually archived."""
        return self._dots_check.isChecked()

    def view_on(self, view: str) -> bool:
        check = self._views.get(view)
        return check is not None and check.isChecked()

    def set_views(self, views: Sequence[str]) -> None:
        """Tick exactly ``views`` and draw them."""
        wanted = set(views)
        for view, check in self._views.items():
            check.blockSignals(True)
            check.setChecked(view in wanted)
            check.blockSignals(False)
        self._on_view_toggled()

    def _on_view_toggled(self, *args) -> None:
        self._sync_controls()
        self._rebuild()

    def _sync_controls(self) -> None:
        """Offer the parameters only the views on screen have a use for."""
        self._controls.show_spectral(self.view_on("spectrum"))
        self._controls.show_bins(self.view_on("distribution"))

    @property
    def _side_column(self) -> bool:
        """Whether anything sits in the column beside the traces."""
        return self.view_on("distribution")

    def _build_join_check(self) -> QCheckBox:
        """The toolbar's local join, which changes what this window draws and nothing else."""
        self._join_check = QCheckBox("Join overlapping instances")
        self._join_check.setChecked(self.joined)
        self._join_check.setEnabled(self._joinable)
        if self._joinable:
            self._join_check.setToolTip(
                "Read the instances shown here as the continuous recording they were cut from, "
                "merging those whose labels agree where they overlap: one series over one set of "
                "bands, a dashed line where each further instance begins, and far less Unknown in "
                "the label band than the instances carry apart. Exactly the instances on screen "
                "are merged, and this window alone changes: the overview and any other instance "
                "window are left as they are."
            )
        elif self._plain is None:
            self._join_check.setToolTip(
                "These instances were already merged in the overview, and this window is showing "
                "that merge: there is nothing left to join."
            )
        else:
            self._join_check.setToolTip(
                "No two of the instances shown here overlap with labels that agree, so there is "
                "nothing to merge."
            )
        self._join_check.toggled.connect(self.set_joined)
        return self._join_check

    def _on_features_toggled(self, shown: bool) -> None:
        self._features_shown = shown
        self._panel.setVisible(shown)

    def _swap_feature_panel(self, selected: set[str]) -> None:
        """Build the feature panel again for the blocks now drawn, keeping the selection.

        The panel is rebuilt rather than edited because every part of it
        depends on the blocks: which features any of them recorded, in how many
        of them, and which event's signature the window can offer.
        """
        previous, self._checks = self._panel, {}
        self._panel = self._build_feature_panel(selected)
        self._panel.setVisible(self._features_shown)
        self._body.replaceWidget(previous, self._panel)
        previous.setParent(None)
        previous.deleteLater()

    def _build_feature_panel(self, selected: set[str] | None = None) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(PANEL_WIDTH)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("<b>Features</b>")
        layout.addWidget(title)
        # Stacked, not side by side: the panel is as narrow as its longest
        # feature name allows, and two buttons in a row would widen it.
        buttons = QVBoxLayout()
        buttons.setSpacing(2)
        clear = QPushButton("Clear")
        clear.clicked.connect(lambda: self._set_all(False))
        every = QPushButton("All recorded")
        every.clicked.connect(lambda: self._set_all(True))
        buttons.addWidget(clear)
        buttons.addWidget(every)
        layout.addLayout(buttons)
        layout.addWidget(self._build_signature_check())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        checks = QVBoxLayout(inner)
        checks.setContentsMargins(0, 0, 0, 0)
        checks.setSpacing(2)
        default = self._default_feature()
        wanted = selected if selected is not None else {default}
        n = len(self.frames)
        for row in self._features.itertuples():
            unit = self.info.unit(row.sensor)
            text = f"{row.sensor} [{unit}]" if unit else row.sensor
            # The mark of a reading no instrument could have produced, on the
            # name itself: the tooltip says how many blocks and what range.
            check = QCheckBox(f"{text} ⚠" if row.implausible else text)
            description = self.info.sensor_descriptions.get(row.sensor, "")
            recorded = f"recorded in {row.recorded} of {n} {self._noun}{'s' if n > 1 else ''}"
            if row.implausible:
                low, high = plausible_range(unit)
                recorded += (
                    f"\n⚠ readings outside the plausible range ({low:g} to {high:g} {unit}) "
                    f"in {row.implausible} of them"
                ).replace(" )", ")")
            check.setToolTip(f"{description}\n{recorded}" if description else recorded)
            check.setEnabled(row.recorded > 0)
            check.setChecked(row.sensor in wanted and row.recorded > 0)
            check.toggled.connect(self._rebuild)
            self._checks[row.sensor] = check
            checks.addWidget(check)
        checks.addStretch(1)
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)
        self._note = QLabel(f"Greyed-out features were recorded by none of these {self._noun}s.")
        self._note.setWordWrap(True)
        layout.addWidget(self._note)
        return panel

    def _build_signature_check(self) -> QWidget:
        """The one-click selection of the variables that identify the event.

        The events the 3W paper illustrates have a published signature; the
        others a best effort read off the thesis, which the tooltip says. The
        box is disabled (and says why) when there is nothing to tick.
        """
        self._signature_check = QCheckBox("Signature")
        self._signature_check.toggled.connect(self._apply_signature)
        available = self._signature_features()
        if self._signature is None:
            self._signature_check.setEnabled(False)
            self._signature_check.setToolTip(
                "The viewer knows no signature for the events this window shows."
            )
            return self._signature_check
        fault, variables, published = self._signature
        name = self.info.fault_name(fault)
        missing = [v for v in variables if v not in available]
        # The box says only "Signature"; the event it belongs to is in the tooltip,
        # where it costs the panel no width.
        if published:
            text = (
                f"Signature of {name}: {', '.join(variables)}, the variables of the figure the "
                "3W paper illustrates the event with."
            )
        else:
            text = (
                f"Best-effort signature of {name}: {', '.join(variables)}. The 3W paper publishes "
                f"no figure of this event; the set comes from {BEST_EFFORT_SOURCES[fault]}."
            )
        if missing:
            text += f"\nNot recorded here, so left out: {', '.join(missing)}."
        if not available:
            self._signature_check.setEnabled(False)
            text += f"\nNone of them is recorded by these {self._noun}s."
        self._signature_check.setToolTip(text)
        return self._signature_check

    def _apply_signature(self, checked: bool) -> None:
        """Tick exactly the signature variables, or clear the selection."""
        wanted = set(self._signature_features()) if checked else set()
        for name, check in self._checks.items():
            check.blockSignals(True)
            check.setChecked(name in wanted and check.isEnabled())
            check.blockSignals(False)
        self._rebuild()

    def _sync_signature(self) -> None:
        """Keep the box ticked exactly while the selection is the signature."""
        available = self._signature_features()
        matches = bool(available) and set(self.selected_features()) == set(available)
        self._signature_check.blockSignals(True)
        self._signature_check.setChecked(matches)
        self._signature_check.blockSignals(False)

    def _set_all(self, checked: bool) -> None:
        for check in self._checks.values():
            check.blockSignals(True)
            check.setChecked(checked and check.isEnabled())
            check.blockSignals(False)
        self._rebuild()

    def show_help(self) -> None:
        """Open (or raise) the help window, on the tab explaining the variables."""
        if self._help is None:
            self._help = HelpWindow(self.info, parent=self)
        self._help.show_tab("Variables")

    def _header_html(self) -> str:
        rows = self.rows
        first, last = pd.Timestamp(rows["start"].min()), pd.Timestamp(rows["end"].max())
        span_h = (last - first).total_seconds() / 3600
        shared_h = sum(
            (b - a).total_seconds() / 3600
            for a, b, count in coverage_counts(rows["start"], rows["end"])
            if count >= 2
        )
        noun = self._noun
        others = len(rows) - 1
        what = f"<b>{instance_title(rows.iloc[self.clicked])}</b>" + (
            f" and the {others} {noun}{'s' if others > 1 else ''} it overlaps"
            if others
            else f" (overlaps no other {noun})"
        )
        shown = f"{len(rows)} {noun}{'s' if len(rows) > 1 else ''} shown, chronological"
        if self.merged:
            shown += f", merged from {sum(len(members) for members in self.members)} instances"
        return (
            f'<span style="font-size:11pt;"><b>{self.well.label}</b> | {what}</span><br>'
            f'<span style="color:{theme.current().muted};">{first:%Y-%m-%d %H:%M:%S} → {last:%Y-%m-%d %H:%M:%S} | {span_h:.1f} h spanned | '
            f"{shared_h:.1f} h recorded by two or more {noun}s | {shown}</span>"
        )

    def _instance_html(self, position: int) -> str:
        colors = theme.current()
        row = self.rows.iloc[position]
        keys = self.colors[position]
        # One square per color the bar carries, so the block is keyed like the bar was.
        squares = "".join(
            f'<span style="font-size:9pt; color:{bar_color(fault_class, reach)};">&#9632;</span>'
            for fault_class, reach in keys
        )
        if len(keys) > 1:
            what = " + ".join(
                legend_label(fault_class, reach, self.info.fault_names)
                for fault_class, reach in keys
            )
        else:
            fault_class = int(row["fault_class"])
            reach = "" if fault_class == 0 else f" ({REACH_LABELS[row['reach']]})"
            what = f"{self.info.fault_name(fault_class)}{reach}"
        merged = len(self.members[position])
        joined = f"{merged} instances merged | " if merged > 1 else ""
        start, end = pd.Timestamp(row["start"]), pd.Timestamp(row["end"])
        end_fmt = "%H:%M:%S" if end.date() == start.date() else "%Y-%m-%d %H:%M:%S"
        partners = sum(
            1
            for other in range(len(self.rows))
            if other != position and self._overlaps(position, other)
        )
        badge = (
            f'&nbsp;<span style="background-color:{colors.highlight}; '
            f'color:{colors.highlight_text};">&nbsp;clicked&nbsp;</span>'
            if position == self.clicked
            else ""
        )
        flagged = self._flagged_sensors(position)
        # The warning comes before the long run of details, which a narrow
        # window clips at the right; a warning clipped away is no warning.
        warning = (
            f'<span style="font-size:9pt; color:{colors.warning};">&nbsp;⚠ outside the '
            f"plausible range: {', '.join(flagged)} |</span>"
            if flagged
            else ""
        )
        discarded = self._discarded_sensors(position)
        cleaning = (
            f'<span style="font-size:9pt; color:{colors.muted};">&nbsp;╲ the Toolkit\'s '
            f"CleanSignals would discard {', '.join(discarded)} |</span>"
            if discarded
            else ""
        )
        if self._model_results is not None:
            share = self._model_results.agreement_of_members(self._member_keys(position))
            verdict = (
                f"{self._model_results.name} agrees {share:.0%} of the compared time"
                if np.isfinite(share)
                else f"not scored by {self._model_results.name}"
            )
            cleaning += (
                f'<span style="font-size:9pt; color:{colors.muted};">&nbsp;{verdict} |</span>'
            )
        return (
            f'<span style="font-size:10pt;"><b>{instance_title(row)}</b></span>{badge}'
            f"&nbsp;&nbsp;{squares}{warning}{cleaning}"
            f'<span style="font-size:9pt; color:{colors.muted};"> {what} | {joined}'
            f"{start:%Y-%m-%d %H:%M:%S} → {end.strftime(end_fmt)} | "
            f"{row['hours']:.1f} h | {int(row['n_samples']):,} samples | level {int(row['lane']) + 1} | "
            f"overlaps {partners} shown</span>"
        )

    def _overlaps(self, a: int, b: int) -> bool:
        ra, rb = self.rows.iloc[a], self.rows.iloc[b]
        return bool(ra["start"] <= rb["end"] and rb["start"] <= ra["end"])

    def _discarded_sensors(self, position: int) -> list[str]:
        """The sensors the Toolkit's CleanSignals rule would discard in any instance behind one block.

        Only once a page has fitted the rule (the availability page's box, or
        the Timelines' coloring): this window never reads the data for it.
        """
        if self._passes is None:
            return []
        cleaned = self._passes.cleaning_if_loaded(False)
        if cleaned is None:
            return []
        origin = self.well.rows
        names: list[str] = []
        for member in self.members[position]:
            key = (int(origin["fault_class"].iloc[member]), str(origin["file"].iloc[member]))
            names += [name for name in cleaned.discarded(key) if name not in names]
        return names

    # -- the grid

    def _rebuild(self, *args) -> None:
        """Lay the stack out again, keeping the stretch of time on screen.

        What the feature checkboxes are connected to, so ticking a feature does
        not throw away a zoom. A switch of view calls ``_relayout`` instead,
        having cleared the range: the blocks then span a different stretch of
        time and the old window would hide most of it.
        """
        if self._master is not None:
            self._x_range = tuple(self._master.getViewBox().viewRange()[0])
        self._relayout()

    def _relayout(self) -> None:
        """Lay out header, bands and the selected feature plots of every block."""
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            self._lay_out_stack()
        finally:
            QApplication.restoreOverrideCursor()
        self._sync_signature()
        self._apply_ranges()
        self._refresh_stretch()

    def _lay_out_stack(self) -> None:
        """Fill the stack: the shared-coverage band, then one block per bar.

        Everything on the time axis sits in the first column, and only there,
        so that the same instant is at the same pixel in every row; the second
        column, when a view asks for it, holds what shares an axis with the row
        beside it but not the time, which is the marginal histogram. The
        spectrum takes a full-width row under the trace, the period along the
        bottom, since nothing has to line up with it.
        """
        layout = self._layout_widget
        layout.clear()
        self._plots = {}
        self._time_plots = []
        self._stretch_panels = []
        self._feature_masters = {}
        self._crosshairs = []
        self._master = None  # so the new master does not link itself to the removed one
        features = self.selected_features()
        side = self._side_column
        grid = layout.ci.layout
        grid.setColumnFixedWidth(1, SIDE_PX if side else 0)
        grid.setColumnStretchFactor(0, 1)
        span = 2 if side else 1
        spectral = self.view_on("spectrum")

        heights: list[int] = []
        row = 0
        self._master = self._add_band(row, self._coverage_band_segments(), "shared")
        self._master.getViewBox().sigXRangeChanged.connect(self._schedule_stretch)
        heights.append(BAND_PX)
        row += 1
        for position in range(len(self.rows)):
            # Every block but the first carries the room that separates it from
            # the one above, so the header reads as the title of what follows it.
            header_px = HEADER_PX + (BLOCK_SPACING if position else 0)
            label = HeaderLabel(justify="left")
            label.setText(self._instance_html(position))
            label.setFixedHeight(header_px)
            layout.addItem(label, row=row, col=0, colspan=span)
            heights.append(header_px)
            row += 1
            seams = self._seams[position]
            self._add_band(row, self._state_band_segments(position), "state", seams)
            self._add_band(row + 1, self._class_band_segments(position), "class", seams)
            heights += [BAND_PX, BAND_PX]
            row += 2
            model_segments = self._model_band_segments(position)
            if model_segments is not None:
                # The loaded model's verdicts, under the labels they are judged against.
                self._add_band(row, model_segments, "model", seams)
                heights.append(BAND_PX)
                row += 1
            for k, feature in enumerate(features):
                last = k == len(features) - 1
                # The time axis closes the last trace of every block; the
                # spectrum under it carries a period axis of its own.
                trace_axis = last
                panel = StretchPanel(
                    position,
                    feature,
                    self.info.unit(feature),
                    plausible_range(self.info.unit(feature)),
                )
                self._add_feature_plot(row, position, feature, show_axis=trace_axis)
                if self.view_on("distribution"):
                    self._add_histogram_panel(row, panel, show_axis=trace_axis)
                heights.append(PLOT_MIN_PX + (AXIS_PX if trace_axis else 0))
                row += 1
                if spectral:
                    self._add_spectral_row(row, panel, span)
                    heights.append(PLOT_MIN_PX + AXIS_PX)
                    row += 1
                if panel.hist_plot is not None or panel.spec_plot is not None:
                    self._stretch_panels.append(panel)
            if not features:
                self._plots_last_axis_placeholder(row, seams)
                heights.append(AXIS_PX + 4)
                row += 1
        layout.setMinimumHeight(self._stack_height(heights))
        self._fill_widget()

    def _stack_height(self, heights: list[int]) -> int:
        """How tall the stack must be for every row to get the height it asked for.

        The stack lives in a scroll area, which sizes it to whichever is the
        larger of this figure and the viewport, and hands any surplus to the
        feature plots, they being the only rows that stretch. An underestimate
        therefore does not merely stop the scrollbar early: the grid inside
        squeezes its rows to fit and the plots at the bottom come out clipped.
        The layout's own minimum is the authority on the total, with the sum of
        the rows as a floor.

        """
        estimate = sum(heights) + ROW_SPACING * max(len(heights) - 1, 0) + 4
        minimum = self._layout_widget.ci.layout.effectiveSizeHint(Qt.SizeHint.MinimumSize).height()
        return int(max(estimate, minimum))

    def _fill_widget(self) -> None:
        """Give the stack back the whole widget after its rows have been rebuilt.

        The view sizes its central item from its own resize events. Building
        the rows again makes that item resize itself to what the new rows
        prefer, which is their floor; and when the widget itself does not
        change size (which is whenever the stack fits, the scroll area then
        holding it at the viewport), no resize follows to put the item back.
        The stack would be drawn into the top of the window with every plot at
        its minimum and the room below it left empty, so the view's own resize
        handler is called to restore the item to the widget it sits in. It
        reads nothing from the event, and a later resize simply does it again.
        """
        self._layout_widget.resizeEvent(None)

    def _new_plot(self, row: int, with_axis: bool) -> pg.PlotItem:
        """A plot on the shared time axis, in the first column, with a crosshair."""
        axis_items = {"bottom": TimeAxisItem(self.timemap)} if with_axis else {}
        plot = self._layout_widget.addPlot(
            row=row, col=0, viewBox=ScrollFriendlyViewBox(), axisItems=axis_items or None
        )
        plot.hideButtons()
        plot.getAxis("left").setWidth(AXIS_WIDTH)
        if with_axis:
            plot.getAxis("bottom").set_timemap(self.timemap, major_with_time=True)
        else:
            plot.hideAxis("bottom")
        vb = plot.getViewBox()
        vb.disableAutoRange()
        pad = 0.01 * self.timemap.span
        vb.setLimits(
            xMin=-pad, xMax=self.timemap.span + pad, minXRange=min(10 / 3600, self.timemap.span)
        )
        if self._master is not None:
            plot.setXLink(self._master)
        crosshair = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(theme.current().crosshair, width=1, style=Qt.PenStyle.DashLine),
        )
        crosshair.setZValue(40)
        crosshair.setVisible(False)
        plot.addItem(crosshair, ignoreBounds=True)
        self._crosshairs.append(crosshair)
        self._time_plots.append(plot)
        return plot

    def _new_side_plot(self, row: int, col: int = 1, colspan: int = 1) -> pg.PlotItem:
        """A plot off the time axis: no crosshair, no link, its own mouse."""
        plot = self._layout_widget.addPlot(
            row=row, col=col, colspan=colspan, viewBox=ScrollFriendlyViewBox()
        )
        plot.hideButtons()
        plot.getViewBox().disableAutoRange()
        return plot

    def _add_seams(self, plot: pg.PlotItem, seams: Sequence[float]) -> None:
        """Mark, inside a merged block, where each instance after the first begins."""
        if not len(seams):
            return
        item = SeamsItem()  # above the trace, below the crosshair
        item.set_seams(seams)
        plot.addItem(item, ignoreBounds=True)

    def _add_band(
        self, row: int, segments: BandSegments, name: str, seams: Sequence[float] = ()
    ) -> pg.PlotItem:
        plot = self._new_plot(row, with_axis=False)
        plot.setFixedHeight(BAND_PX)
        plot.setMenuEnabled(False)
        vb = plot.getViewBox()
        vb.setMouseEnabled(x=True, y=False)
        vb.setYRange(0, 1, padding=0)
        left = plot.getAxis("left")
        left.setTicks([[(0.5, name)]])
        left.setStyle(tickLength=0)
        item = SegmentsItem(z=-10)
        item.set_segments(
            segments.x0, segments.x1, segments.colors, segments.labels, hatched=segments.hatched
        )
        plot.addItem(item, ignoreBounds=True)
        self._add_seams(plot, seams)
        return plot

    def _plots_last_axis_placeholder(self, row: int, seams: Sequence[float] = ()) -> None:
        """With no feature selected, a bare time axis still closes each block."""
        plot = self._new_plot(row, with_axis=True)
        plot.setFixedHeight(AXIS_PX + 4)
        plot.setMenuEnabled(False)
        plot.getViewBox().setMouseEnabled(x=True, y=False)
        plot.getAxis("left").setStyle(showValues=False)
        self._add_seams(plot, seams)

    def _add_feature_plot(
        self, row: int, position: int, feature: str, show_axis: bool
    ) -> pg.PlotItem:
        plot = self._new_plot(row, with_axis=show_axis)
        plot.setMinimumHeight(PLOT_MIN_PX + (AXIS_PX if show_axis else 0))
        self._layout_widget.ci.layout.setRowStretchFactor(row, 1)
        vb = plot.getViewBox()
        vb.setMouseEnabled(x=True, y=True)
        frame = self.frames[position]
        unit = self.info.unit(feature)
        axis = plot.getAxis("left")
        if unit in SI_UNITS:
            axis.enableAutoSIPrefix(True)
            plot.setLabel("left", feature, units=unit)
        else:
            axis.enableAutoSIPrefix(False)
            plot.setLabel("left", f"{feature} [{unit}]" if unit else feature)

        shading = SegmentsItem(z=-10)
        background = self._class_band_segments(position, background=True)
        shading.set_segments(
            background.x0, background.x1, background.colors, hatched=background.hatched
        )
        plot.addItem(shading, ignoreBounds=True)
        self._add_seams(plot, self._seams[position])

        colors = theme.current()
        stats = feature_stats(frame, feature)
        if stats.recorded:
            x = self.timemap.to_x(frame.index)
            y = frame[feature].to_numpy(dtype=float)
            # The measurements as dots, the historian's lines faint between them.
            kinds = self._kinds_of(position, feature)
            add_trace(plot, x, y, colors.trace, 1.0, kinds if self.dots_shown else None)
            note = format_delta(stats.delta, unit) + (" (flat)" if stats.flat else "")
            if kinds is not None and not stats.flat:
                note += " | " + describe_sampling(sampling_of(kinds))
            # A reading no instrument could have produced is drawn in the
            # warning color over the trace, sample by sample, so that the
            # stretch that is garbage is seen for what it is, and called out
            # beside the figures of the panel.
            bounds = plausible_range(unit)
            warning = ""
            if outside_range(stats.low, stats.high, bounds):
                self._mark_implausible(plot, x, y, bounds)
                warning = (
                    f' | <span style="color:{colors.warning};">⚠ readings outside '
                    f"{bounds[0]:g} to {bounds[1]:g} {unit}</span>"
                ).replace("  ", " ")
            AnchoredText(
                f'<span style="font-size:8pt; color:{colors.text};">'
                f"{note} | coverage {stats.coverage:.1f} %{warning}</span>"
            ).attach(plot)
        else:
            AnchoredText(
                f'<span style="font-size:10pt; color:{colors.faint};">not recorded</span>',
                frac=(0.5, 0.5),
                anchor=(0.5, 0.5),
                boxed=False,
            ).attach(plot)

        key = (position, feature)
        self._plots[key] = plot
        if feature in self._feature_masters:
            plot.setYLink(self._feature_masters[feature])
        else:
            self._feature_masters[feature] = plot
        return plot

    # -- the views beside and under a trace

    def _add_histogram_panel(self, row: int, panel: StretchPanel, show_axis: bool) -> None:
        """The marginal histogram of one trace, sharing its value axis, in the side column."""
        plot = self._new_side_plot(row)
        plot.setMinimumHeight(PLOT_MIN_PX + (AXIS_PX if show_axis else 0))
        plot.hideAxis("left")
        if show_axis:
            plot.setLabel("bottom", "samples")
        else:
            plot.hideAxis("bottom")
        vb = plot.getViewBox()
        vb.setMouseEnabled(x=False, y=True)
        vb.setLimits(xMin=0)
        plot.setYLink(self._plots[(panel.position, panel.feature)])
        panel.hist_plot = plot
        # Bottom right: the bars reach right where the readings pile up, which
        # for a pressure under a fault is the top of the range more often than not.
        panel.hist_note = AnchoredText("", frac=(1.0, 0.0), anchor=(1.03, 1.25))
        panel.hist_note.attach(plot)

    def _add_spectral_row(self, row: int, panel: StretchPanel, span: int) -> None:
        """The spectrum in a row of its own under the trace, the period along the bottom."""
        plot = self._new_side_plot(row, col=0, colspan=span)
        plot.getAxis("left").setWidth(AXIS_WIDTH)
        set_log_period_axis(plot, "bottom", "period")
        power_axis(plot, "left", f"{panel.feature} | {power_label(panel.unit)}")
        plot.getViewBox().setMouseEnabled(x=True, y=True)
        plot.setMinimumHeight(PLOT_MIN_PX + AXIS_PX)
        self._layout_widget.ci.layout.setRowStretchFactor(row, 1)
        spectrum_grid(plot)
        panel.spec_plot = plot
        panel.peak = PeriodMarker()
        self._plots[(panel.position, panel.feature)].addItem(panel.peak, ignoreBounds=True)
        # The power climbs with the period, so the curve ends up at the right;
        # the caption goes to the left, where it is not.
        panel.spec_note = AnchoredText("", frac=(0.0, 1.0), anchor=(-0.03, -0.25))
        panel.spec_note.attach(plot)

    def _series_on_grid(self, frame: pd.DataFrame, feature: str) -> tuple[np.ndarray, int]:
        """The readings of one feature on the fixed 1 Hz grid, and how many seconds a sample spans."""
        if feature not in frame.columns:
            return np.full(len(frame), np.nan), 1
        return uniform_series(frame.index, frame[feature].to_numpy(dtype=float))

    def _kinds_of(self, position: int, feature: str) -> np.ndarray | None:
        """Which samples of one feature of one block are measurements, held, interpolated or missing.

        ``None`` for an enumerated variable, which is not tested: a valve held
        in one position for hours is a fact about the well. Computed once per
        block and feature, the frame never changing under a window.
        """
        key = (position, feature)
        if key not in self._kinds_cache:
            frame = self.frames[position]
            if self.info.is_enumerated(feature) or feature not in frame.columns:
                self._kinds_cache[key] = None
            else:
                self._kinds_cache[key] = sample_kinds(frame[feature].to_numpy(dtype=float))
        return self._kinds_cache[key]

    def _schedule_stretch(self, *args) -> None:
        self._stretch_timer.start()

    def _visible_slice(self, position: int) -> slice:
        """The samples of one block inside the stretch of time on screen."""
        frame = self.frames[position]
        if self._master is None or not len(frame):
            return slice(0, len(frame))
        x0, x1 = self._master.getViewBox().viewRange()[0]
        t0, t1 = self.timemap.to_time(x0), self.timemap.to_time(x1)
        start = 0 if t0 is None else int(frame.index.searchsorted(at_index_unit(frame, t0)))
        stop = (
            len(frame)
            if t1 is None
            else int(frame.index.searchsorted(at_index_unit(frame, t1), side="right"))
        )
        return slice(start, max(stop, start))

    def _refresh_stretch(self) -> None:
        """Count the histograms and the spectra again over the stretch of time on screen."""
        if not self._stretch_panels:
            return
        params = self._controls.params()
        for panel in self._stretch_panels:
            window = self._visible_slice(panel.position)
            frame = self.frames[panel.position]
            if panel.hist_plot is not None:
                self._refresh_histogram(panel, frame, window, params)
            if panel.spec_plot is not None:
                self._refresh_spectrum(panel, frame, window, params)

    def _sample_groups(self, position: int) -> tuple[np.ndarray, list[tuple[str, int]]]:
        """Per sample of one block, the label period it is in, as codes into a list of ``(kind, hue)`` keys.

        The keys come in the order the stacks are laid: normal, transient,
        steady, then the unlabeled, which is the ladder the bands climb.
        """
        cached = self._groups_cache.get(position)
        if cached is not None:
            return cached
        frame = self.frames[position]
        offset = self.info.transient_offset
        fault_class = self._fault_of(position)
        spans: list[tuple[int, int, tuple[str, int]]] = []
        for segment, source in self._class_runs(position):
            a = int(frame.index.searchsorted(segment.start, side="left"))
            b = int(frame.index.searchsorted(segment.end, side="right"))
            kind = label_kind(segment.value, offset)
            fault = label_fault(segment.value, offset)
            hue = fault if fault is not None else (fault_class if source is None else source)
            spans.append((a, b, (kind, hue)))
        rank = {"normal": 0, "transient": 1, "steady": 2, "unknown": 3}
        keys = sorted({key for _, _, key in spans}, key=lambda k: (rank.get(k[0], 4), k[1] or -1))
        codes = np.full(len(frame), -1, dtype=np.int64)
        for a, b, key in spans:
            codes[a:b] = keys.index(key)
        self._groups_cache[position] = (codes, keys)
        return codes, keys

    def _refresh_histogram(self, panel: StretchPanel, frame, window: slice, params) -> None:
        plot = panel.hist_plot
        for item in panel.hist_items:
            plot.removeItem(item)
        panel.hist_items = []
        colors = theme.current()
        values = (
            frame[panel.feature].to_numpy(dtype=float)[window]
            if panel.feature in frame.columns
            else np.array([])
        )
        # With the clamp off the implausible readings are counted rather than
        # left out, and the stretches of the value axis they fall in are given
        # the amber ground the viewer marks an impossible reading with
        # everywhere else. The axis itself already reaches them: it is the
        # recorded extent, which is why those samples are drawn in amber over
        # the trace beside this.
        bounds = panel.bounds if params.clamp else None
        kinds = self._kinds_of(panel.position, panel.feature)
        measured = params.genuine and kinds is not None
        result = None
        if len(values):
            codes, keys = self._sample_groups(panel.position)
            codes = codes[window]
            if measured:
                # The measurements alone: the historian's lines between them left out.
                keep = kinds[window] == GENUINE
                values, codes = values[keep], codes[keep]
            result = histogram(values, codes, params.bins, bounds, keys=keys)
        panel.histogram = result
        if result is None:
            panel.hist_note.setHtml(
                f'<span style="font-size:8pt; color:{colors.faint};">no readings on screen</span>'
            )
            plot.getViewBox().setXRange(0, 1, padding=0)
            return
        brushes = {}
        for kind, hue in result.stacks:
            if kind == "unknown":
                brushes[(kind, hue)] = pg.mkBrush(tint(unknown_background(), 0.7))
            else:
                brushes[(kind, hue)] = pg.mkBrush(bar_color(hue, kind))
        pen = pg.mkPen(colors.plot_background, width=0.5)
        panel.hist_items = add_stacked_bars(plot, result, brushes, horizontal=True, pen=pen)
        panel.hist_items += add_center_lines(plot, result.mean, result.median, horizontal=True)
        if bounds is None:
            panel.hist_items += shade_implausible(plot, panel.bounds, "y")
        top = float(result.counts.max())
        plot.getViewBox().setXRange(0, top * 1.05 if top > 0 else 1, padding=0)
        width = format_width(float(result.edges[1] - result.edges[0]), panel.unit)
        counted = int(
            ((values < panel.bounds[0]) | (values > panel.bounds[1])).sum() if len(values) else 0
        )
        if bounds is None:
            left_out = (
                f'<br><span style="color:{colors.warning};">⚠ {counted:,} implausible '
                "counted</span>"
                if counted
                else ""
            )
        else:
            left_out = (
                f'<br><span style="color:{colors.warning};">⚠ {result.left_out:,} implausible '
                "left out</span>"
                if result.left_out
                else ""
            )
        noun = "measurements" if measured else "samples"
        panel.hist_note.setHtml(
            f'<span style="font-size:8pt; color:{colors.text};">{result.total:,} {noun}<br>'
            f"{len(result.edges) - 1} bins of {width}<br>"
            f"mean {format_width(result.mean, panel.unit)} ―<br>"
            f"median {format_width(result.median, panel.unit)} ╌{left_out}</span>"
        )

    def _mark_peak(self, panel: StretchPanel, spectrum: Spectrum) -> None:
        """Lay one cycle of the dominant period against the trace, a little inside the stretch shown."""
        period, _share = spectrum.dominant()
        if not np.isfinite(period) or self._master is None:
            panel.peak.clear()
            return
        x0, x1 = self._master.getViewBox().viewRange()[0]
        panel.peak.set_period(
            x0 + 0.04 * (x1 - x0), period / 3600.0, f"peak period {format_period(period)}"
        )

    def _refresh_spectrum(self, panel: StretchPanel, frame, window: slice, params) -> None:
        plot = panel.spec_plot
        for item in panel.spec_items:
            plot.removeItem(item)
        panel.spec_items = []
        colors = theme.current()
        sub = frame.iloc[window]
        spectrum = self._spectrum_on_screen(sub, panel, window, params)
        vb = plot.getViewBox()
        if spectrum is None:
            panel.spectrum = None
            panel.peak.clear()
            what = "measurements" if params.genuine else "readings"
            panel.spec_note.setHtml(
                f'<span style="font-size:8pt; color:{colors.faint};">too few {what} on screen, '
                "or a flat signal, to transform</span>"
            )
            return
        panel.spectrum = spectrum
        self._mark_peak(panel, spectrum)
        curve = add_spectrum_curve(plot, spectrum, pg.mkPen(colors.trace, width=1.2), "x")
        panel.spec_items.append(curve)
        _x, log_power = spectrum_xy(spectrum, "x")
        finite = log_power[np.isfinite(log_power)]
        lo, hi = (float(finite.min()), float(finite.max())) if len(finite) else (-1.0, 1.0)
        if hi <= lo:
            hi = lo + 1.0
        pad = 0.05 * (hi - lo)
        vb.setYRange(lo - pad, hi + pad, padding=0)
        low, high = period_range(spectrum)
        vb.setXRange(low, high, padding=0.01)
        if not spectrum.lomb_scargle and spectrum.segment_s < len(sub):
            panel.spec_items.append(
                shade_unresolved(plot, float(np.log10(spectrum.segment_s)), "x")
            )
        caption = caption_for(spectrum, panel.unit)
        panel.spec_note.setHtml(
            f'<span style="font-size:8pt; color:{colors.text};">{caption}</span>'
        )

    def _spectrum_on_screen(self, sub: pd.DataFrame, panel: StretchPanel, window: slice, params):
        """The spectrum of one feature over the stretch on screen: Welch's on the grid, or Lomb-Scargle over the measurements."""
        if not len(sub) or panel.feature not in sub.columns:
            return None
        kinds = self._kinds_of(panel.position, panel.feature)
        if params.genuine and kinds is not None:
            keep = kinds[window] == GENUINE
            seconds = (sub.index - sub.index[0]).total_seconds().to_numpy(dtype=float)
            prepared = prepare_irregular(
                seconds[keep], sub[panel.feature].to_numpy(dtype=float)[keep], panel.bounds
            )
            return lomb_scargle(*prepared) if prepared is not None else None
        values, _step = self._series_on_grid(sub, panel.feature)
        prepared = prepare(values, panel.bounds) if len(values) else None
        return welch(prepared, params) if prepared is not None else None

    @staticmethod
    def _mark_implausible(plot: pg.PlotItem, x: np.ndarray, y: np.ndarray, bounds) -> None:
        """Draw the samples outside ``bounds`` in the warning color, over the trace.

        A stretch of them is a line; isolated ones (a sentinel leaked into a
        few samples) would not join into one, so up to a few thousand of them
        are also dotted, past which the line alone says enough.
        """
        colors = theme.current()
        bad = (y < bounds[0]) | (y > bounds[1])
        if not bad.any():
            return
        garbage = pg.PlotDataItem(
            x,
            np.where(bad, y, np.nan),
            pen=pg.mkPen(colors.warning, width=1.8),
            connect="finite",
        )
        garbage.setZValue(15)
        plot.addItem(garbage)
        garbage.setDownsampling(auto=True, method="peak")
        garbage.setClipToView(True)
        if bad.sum() <= 2000:
            dots = pg.ScatterPlotItem(
                x[bad], y[bad], size=4, pen=None, brush=pg.mkBrush(colors.warning)
            )
            dots.setZValue(15)
            plot.addItem(dots)

    # -- segments

    def _class_runs(self, position: int) -> list[tuple[Segment, int | None]]:
        """The label runs of one block, with the fault folder each stretch came from.

        A block of one instance is read from its frame, as it always was. A
        merged one is read from the label runs the catalogue already holds for
        its instances, which say the same as the merged ``class`` column and
        also say which file supplied each stretch, so a normal period labeled
        by a Normal Operation file keeps that file's color even where the
        merged recording goes on to develop a fault.
        """
        members = self.members[position]
        rows = self.well.rows.iloc[members]
        if len(members) == 1:
            folder = int(rows["fault_class"].iloc[0])
            return [(run, folder) for run in label_segments(self.frames[position], "class")]
        return merge_label_runs(
            [segments_from_json(text) for text in rows["class_runs"]],
            [int(folder) for folder in rows["fault_class"]],
        )

    def _class_band_segments(self, position: int, background: bool = False) -> BandSegments:
        fault_class = self._fault_of(position)
        offset = self.info.transient_offset
        segments = BandSegments([], [], [], [], [])
        for segment, source in self._class_runs(position):
            a, b = self.timemap.to_x([segment.start, segment.end])
            kind = label_kind(segment.value, offset)
            fault = label_fault(segment.value, offset)
            # A normal stretch takes the hue of the file that labeled it normal;
            # a faulty one names its own event, whatever file it came from.
            hue_class = fault if fault is not None else (fault_class if source is None else source)
            unknown = kind == "unknown"
            if unknown:
                color = tint(unknown_background(), 0.7) if background else unknown_background()
            elif background:
                color = background_color(hue_class, kind)
            else:
                color = bar_color(hue_class, kind)
            segments.add(
                a, b, color, label_name(segment.value, self.info.fault_names, offset), unknown
            )
        return segments

    def _member_keys(self, position: int) -> list[tuple[int, str]]:
        origin = self.well.rows
        return [
            (int(origin["fault_class"].iloc[m]), str(origin["file"].iloc[m]))
            for m in self.members[position]
        ]

    def _model_band_segments(self, position: int) -> BandSegments | None:
        """The loaded model's verdicts on one block, colored by their agreement with the labels.

        Where the model agrees with the experts the stretch is plain, in the
        live blue; where it disagrees, amber; where the experts left the
        stretch unlabeled there is nothing to compare, and the verdict is
        drawn faint. ``None`` when no outputs are loaded or the model scored
        none of the block's instances.
        """
        results = self._model_results
        if results is None:
            return None
        outputs = results.outputs
        keys = [key for key in self._member_keys(position) if outputs.has(*key)]
        if not keys:
            return None
        tracks = [outputs.runs(*key) for key in keys]
        merged = merge_label_runs(tracks, list(range(len(tracks))))
        colors = theme.current()
        offset = self.info.transient_offset
        kind = outputs.spec.kind
        class_runs = [segment for segment, _source in self._class_runs(position)]
        segments = BandSegments([], [], [], [], [])
        for run, _source in merged:
            if np.isnan(run.value):
                continue
            verdict_name = f"model: {outputs.spec.label_name(run.value)}"
            # Split the verdict at the boundaries of the labels it is judged against.
            pieces = [
                (max(run.start, c.start), min(run.end, c.end), c.value)
                for c in class_runs
                if c.start < run.end and c.end > run.start
            ] or [(run.start, run.end, np.nan)]
            for start, end, label in pieces:
                verdict = agrees(run.value, label, kind, offset)
                if verdict is None:
                    color, text = tint(colors.live, 0.45), f"{verdict_name} | no label to compare"
                elif verdict:
                    color, text = colors.live, f"{verdict_name} | agrees with the label"
                else:
                    color, text = colors.warning, f"{verdict_name} | disagrees with the label"
                a, b = self.timemap.to_x([start, end])
                segments.add(a, b, color, text, False)
        return segments if segments.x0 else None

    def _state_band_segments(self, position: int) -> BandSegments:
        frame = self.frames[position]
        segments = BandSegments([], [], [], [], [])
        for segment in label_segments(frame, "state"):
            a, b = self.timemap.to_x([segment.start, segment.end])
            unknown = bool(np.isnan(segment.value))
            state = None if unknown else int(segment.value)
            segments.add(a, b, state_color(state), state_name(segment.value), unknown)
        return segments

    def _coverage_band_segments(self) -> BandSegments:
        colors = theme.current()
        segments = BandSegments([], [], [], [], [])
        for start, end, count in coverage_counts(self.rows["start"], self.rows["end"]):
            a, b = self.timemap.to_x([start, end])
            label = f"shared by {count} instances" if count >= 2 else ""
            segments.add(a, b, colors.shared_fill(count), label, False)
        return segments

    # -- ranges

    def _apply_ranges(self) -> None:
        if self._master is None:
            return
        pad = 0.01 * self.timemap.span
        x_range = self._x_range or (-pad, self.timemap.span + pad)
        self._master.getViewBox().setXRange(*x_range, padding=0)
        for feature, master in self._feature_masters.items():
            lows, highs = [], []
            for position in range(len(self.rows)):
                stats: FeatureStats = feature_stats(self.frames[position], feature)
                if stats.recorded:
                    lows.append(stats.low)
                    highs.append(stats.high)
            low, high = (min(lows), max(highs)) if lows else (np.nan, np.nan)
            master.getViewBox().setYRange(*padded_range(low, high), padding=0)

    def reset_view(self) -> None:
        self._x_range = None
        self._apply_ranges()

    # -- pointer

    def _on_mouse_moved(self, pos) -> None:
        if self._master is None:
            return
        vb = self._master.getViewBox()
        x = vb.mapSceneToView(pos).x()
        stamp = self.timemap.to_time(x)
        inside = any(
            plot.getViewBox().sceneBoundingRect().contains(pos) for plot in self._time_plots
        )
        for line in self._crosshairs:
            line.setVisible(inside)
            line.setPos(x)
        if not inside:
            side = self._describe_side(pos)
            self._status.setText(side if side else HINT)
            return
        if stamp is None:
            self._status.setText(HINT)
            return
        parts = [f"{stamp:%Y-%m-%d %H:%M:%S}"]
        offset = self.info.transient_offset
        for position, frame in enumerate(self.frames):
            title = instance_title(self.rows.iloc[position])
            if stamp < frame.index[0] or stamp > frame.index[-1]:
                parts.append(f"{title}: outside")
                continue
            i = min(
                int(frame.index.searchsorted(at_index_unit(frame, stamp), side="right")) - 1,
                len(frame) - 1,
            )
            klass = frame["class"].iloc[i] if "class" in frame.columns else np.nan
            state = frame["state"].iloc[i] if "state" in frame.columns else np.nan
            klass = float("nan") if pd.isna(klass) else float(klass)
            state = float("nan") if pd.isna(state) else float(state)
            values = []
            for feature in self.selected_features():
                if feature in frame.columns:
                    value = frame[feature].iloc[i]
                    values.append(f"{feature} = {'—' if pd.isna(value) else f'{value:.4g}'}")
            reading = f" | {', '.join(values)}" if values else ""
            parts.append(
                f"{title}: {label_name(klass, self.info.fault_names, offset)} / {state_name(state)}{reading}"
            )
        self._status.setText("  |  ".join(parts))

    def _describe_side(self, pos) -> str:
        """What the pointer is over in the side views: a bin and its count, or a period and its power."""
        for panel in self._stretch_panels:
            title = instance_title(self.rows.iloc[panel.position])
            if (
                panel.hist_plot is not None
                and panel.hist_plot.getViewBox().sceneBoundingRect().contains(pos)
            ):
                result = panel.histogram
                if result is None:
                    return f"{title} | {panel.feature}: no readings on screen"
                value = panel.hist_plot.getViewBox().mapSceneToView(pos).y()
                k = int(np.searchsorted(result.edges, value, side="right")) - 1
                if not 0 <= k < len(result.edges) - 1:
                    return f"{title} | {panel.feature}: outside the bins"
                counts = result.counts
                share = 100.0 * counts[k] / result.total if result.total else 0.0
                stacks = ", ".join(
                    f"{label_kind_name(key)} {stack[k]:,}"
                    for key, stack in result.stacks.items()
                    if stack[k]
                )
                return (
                    f"{title} | {panel.feature} from {result.edges[k]:.4g} to "
                    f"{result.edges[k + 1]:.4g} {panel.unit}: {counts[k]:,} samples ({share:.1f} %)"
                    + (f" | {stacks}" if stacks else "")
                ).replace("  ", " ")
            if (
                panel.spec_plot is not None
                and panel.spec_plot.getViewBox().sceneBoundingRect().contains(pos)
            ):
                spectrum = panel.spectrum
                if spectrum is None:
                    return f"{title} | {panel.feature}: no spectrum on screen"
                point = panel.spec_plot.getViewBox().mapSceneToView(pos)
                log_period = point.x()
                periods = np.log10(spectrum.periods)
                k = int(np.clip(np.searchsorted(periods, log_period), 0, len(periods) - 1))
                unit = f" {panel.unit}²/Hz" if panel.unit and panel.unit != "-" else ""
                return (
                    f"{title} | {panel.feature} | period {format_period(10**log_period)}: "
                    f"power {spectrum.power[k]:.3g}{unit} at {format_period(spectrum.periods[k])}"
                )
        return ""


def label_kind_name(key) -> str:
    """``(kind, hue)`` of a histogram stack as a word: normal, transient, steady, unlabeled."""
    kind = key[0] if isinstance(key, tuple) else str(key)
    return "unlabeled" if kind == "unknown" else kind
