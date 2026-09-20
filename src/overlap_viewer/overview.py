"""The timelines page: a grid of well timelines, one interactive per-well plot each.

Every plot is one well. Each real instance recorded on it is a bar from its
first to its last timestamp, stacked on the instances it overlaps in time, so a
well recorded twice shows at a glance. Hovering a bar highlights the instances
it overlaps and hatches the stretch they share; clicking it asks the main
window for an ``InstanceWindow`` with their time series. The bars are colored
by their fault folder, or, at the user's choice, by how much of one sensor
each instance recorded, which turns the grid into the history of that sensor
on every well.
"""

from functools import partial

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QFontMetrics
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from overlap_viewer import theme
from overlap_viewer.availability import ABSENT, FROZEN, LIVE, Availability
from overlap_viewer.config import (
    BAR_HEIGHT,
    DEFAULT_GAP_HOURS,
    GRID_SPACING,
    MAX_LANE_SLOTS,
    MIN_LANE_SLOTS,
    REACH_LABELS,
)
from overlap_viewer.dataset import (
    DatasetInfo,
    WellData,
    instance_title,
    lane_slots,
)
from overlap_viewer.heatmap import StateKey, ramp_color
from overlap_viewer.items import (
    InstanceBarsItem,
    ScrollFriendlyViewBox,
    SegmentsItem,
    TimeAxisItem,
    WheelToParent,
)
from overlap_viewer.legend import LegendBar
from overlap_viewer.palette import (
    bar_color,
    fault_color,
    legend_entries,
    legend_key,
    legend_label,
)
from overlap_viewer.timemap import TimeMap

HINT = (
    "Hover a bar to see the instance and the instances it overlaps · click a bar to open their "
    "time series · click a color in the key to show only that fault's wells · drag to pan · "
    "Ctrl + wheel to zoom · F1 for help"
)

LANE_PX = 26  # height of one stack level on screen
PLOT_CHROME_PX = 26 + 12  # time axis, margins

SORT_KEYS = {
    "Well number": lambda w: (w.well,),
    "Overlapping instances": lambda w: (-w.n_overlapping, w.well),
    "Instances": lambda w: (-w.n_instances, w.well),
    "Deepest pile-up": lambda w: (-w.n_lanes, -w.n_overlapping, w.well),
}

# What a bar's fill can say.
COLORINGS = ("Fault folder", "Availability of a sensor")


def faults_of(data: WellData, index: int, info: DatasetInfo) -> str:
    """The fault behind one bar — or every fault, ``+``-joined, when a joined bar mixes folders."""
    return " + ".join(
        info.fault_name(fault_class)
        for fault_class in sorted({fault_class for fault_class, _ in data.colors[index]})
    )


def bar_rows(availability: Availability, data: WellData, index: int) -> list[int]:
    """The rows of ``availability`` behind one bar: the instances it stands for."""
    return [availability.index_of(data.well, member) for member in data.members[index]]


def implausible_of(availability: Availability | None, data: WellData, index: int) -> list[str]:
    """The sensors with a reading outside the plausible range in any instance behind one bar."""
    if availability is None:
        return []
    rows = bar_rows(availability, data, index)
    flagged = availability.implausible[rows].any(axis=0)
    return [name for name, flag in zip(availability.sensors, flagged) if flag]


def describe_instance(
    data: WellData, index: int, info: DatasetInfo, availability: Availability | None = None
) -> str:
    """One line about a bar: name, fault, reach, span, size, level, partners, implausible readings.

    A bar joined from several instances names them, and every color it
    carries, in place of a single fault and reach.
    """
    row = data.rows.iloc[index]
    members = data.members[index]
    if len(members) > 1:
        origin = data.origin.rows
        names = [
            f"{instance_title(origin.iloc[m])} ({info.fault_name(int(origin.iloc[m]['fault_class']))})"
            for m in members[:4]
        ]
        if len(members) > 4:
            names.append(f"+{len(members) - 4} more")
        what = f"joins {len(members)} instances: {', '.join(names)} · " + " + ".join(
            legend_label(fault_class, reach, info.fault_names)
            for fault_class, reach in data.colors[index]
        )
    else:
        fault_class = int(row["fault_class"])
        reach = "" if fault_class == 0 else f" · {REACH_LABELS[row['reach']]}"
        what = f"{info.fault_name(fault_class)}{reach}"
    start, end = pd.Timestamp(row["start"]), pd.Timestamp(row["end"])
    end_fmt = "%H:%M:%S" if end.date() == start.date() else "%Y-%m-%d %H:%M:%S"
    noun = "bar" if data.joined_view else "instance"
    partners = data.partners[index]
    if len(partners):
        names = [
            f"{instance_title(data.rows.iloc[j])} ({faults_of(data, j, info)})"
            for j in partners[:4]
        ]
        if len(partners) > 4:
            names.append(f"+{len(partners) - 4} more")
        overlap = (
            f"overlaps {len(partners)} {noun}{'s' if len(partners) > 1 else ''}: "
            + ", ".join(names)
        )
    else:
        overlap = f"overlaps no other {noun}"
    flagged = implausible_of(availability, data, index)
    warning = f" · ⚠ readings outside the plausible range: {', '.join(flagged)}" if flagged else ""
    return (
        f"{instance_title(row)} · {what} · {start:%Y-%m-%d %H:%M:%S} → {end.strftime(end_fmt)} "
        f"({row['hours']:.1f} h, {int(row['n_samples']):,} samples) · stack level {int(row['lane']) + 1} · {overlap}"
        f"{warning}"
    )


def describe_sensor_in_bar(
    availability: Availability, data: WellData, index: int, sensor: str
) -> str:
    """How much of one sensor the instances behind a bar recorded: the sentence behind its tint."""
    shares, flagged = availability.shares_of(
        bar_rows(availability, data, index), availability.sensors.index(sensor)
    )
    parts = [f"{sensor}: live in {shares[LIVE]:.0%} of the samples"]
    if shares[FROZEN] > 0:
        parts.append(f"frozen in {shares[FROZEN]:.0%}")
    if shares[ABSENT] > 0:
        parts.append(f"absent from {shares[ABSENT]:.0%}")
    return ", ".join(parts) + (" · ⚠ readings outside the plausible range" if flagged else "")


class ElidedLabel(QLabel):
    """A single-line label that elides its text instead of growing the window."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:
        self._full = text
        self.setToolTip(text)
        self._refresh()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        metrics = QFontMetrics(self.font())
        super().setText(
            metrics.elidedText(self._full, Qt.TextElideMode.ElideRight, max(self.width() - 8, 50))
        )


class WellTimelinePlot(WheelToParent, pg.PlotWidget):
    """One well: its instances as bars on stack levels, over a gap-compressed time axis.

    Signals
    -------
    hovered(int)
        Row position of the instance under the pointer, ``-1`` when none.
    clicked(int)
        Row position of the instance clicked with the left button.
    """

    hovered = Signal(int)
    clicked = Signal(int)

    def __init__(
        self,
        data: WellData,
        info: DatasetInfo,
        slots: int,
        compressed: bool = True,
        gap_hours: float = DEFAULT_GAP_HOURS,
        parent=None,
    ):
        self._axis = TimeAxisItem(orientation="bottom")
        super().__init__(
            parent=parent, viewBox=ScrollFriendlyViewBox(), axisItems={"bottom": self._axis}
        )
        self.data = data
        self.info = info
        self.slots = max(slots, data.n_lanes)
        self._gap_hours = gap_hours
        self._hover = -1
        self._timemap: TimeMap | None = None
        self._x0 = np.empty(0)
        self._x1 = np.empty(0)
        self._gap_lines: list[pg.InfiniteLine] = []
        # What the bars are filled with and which wear the mark; the fault
        # colors until a page says otherwise.
        self._fills: list[list[str]] | None = None
        self._marks: list[bool] | None = None
        # The summary of the title counts bursts, which only the compressed map knows.
        self._bursts = TimeMap.build(data.starts, data.ends, gap_hours=gap_hours, compressed=True)

        plot = self.getPlotItem()
        vb = plot.getViewBox()
        vb.invertY(True)
        vb.setMouseEnabled(x=True, y=False)
        vb.setMouseMode(pg.ViewBox.PanMode)
        plot.hideButtons()
        left = plot.getAxis("left")
        left.setTicks([[(lane, str(lane + 1)) for lane in range(self.slots)]])
        left.setWidth(30)
        left.setStyle(tickLength=3)
        plot.setYRange(-0.7, self.slots - 0.3, padding=0)
        vb.setLimits(yMin=-0.7, yMax=self.slots - 0.3)

        self._blocks = SegmentsItem(z=-20)
        plot.addItem(self._blocks, ignoreBounds=True)
        for lane in range(data.n_lanes):
            line = pg.InfiniteLine(
                pos=lane, angle=0, pen=pg.mkPen(theme.current().grid_line, width=1), movable=False
            )
            line.setZValue(-15)
            plot.addItem(line, ignoreBounds=True)
        self._bars = InstanceBarsItem()
        plot.addItem(self._bars)

        # Until the user pans or zooms, the view follows the widget size (see resizeEvent).
        self._auto_view = True
        vb.sigRangeChangedManually.connect(self._on_manual_range)
        self.set_compressed(compressed)

        self.scene().sigMouseMoved.connect(self._on_mouse_moved)
        self.scene().sigMouseClicked.connect(self._on_mouse_clicked)

    # -- layout

    @property
    def timemap(self) -> TimeMap:
        return self._timemap

    def default_fills(self) -> list[list[str]]:
        """The fault colors of the bars: one color per distinct legend entry behind each."""
        return [
            list(dict.fromkeys(bar_color(fault_class, reach) for fault_class, reach in keys))
            for keys in self.data.colors
        ]

    def set_coloring(self, fills: list[list[str]] | None, marks: list[bool] | None) -> None:
        """Fill the bars with ``fills`` (``None`` for the fault colors) and mark those in ``marks``."""
        self._fills = fills
        self._marks = marks
        self._draw_bars()

    def _draw_bars(self) -> None:
        data = self.data
        rows = data.rows
        edges = [fault_color(int(fc)) for fc in rows["fault_class"]]
        suffixes = [f" +{len(members) - 1}" if len(members) > 1 else "" for members in data.members]
        self._bars.set_bars(
            self._x0,
            self._x1,
            rows["lane"].to_numpy(dtype=float),
            self._fills if self._fills is not None else self.default_fills(),
            edges,
            rows["stamp"],
            suffixes,
            self._marks,
        )

    def set_compressed(self, compressed: bool) -> None:
        """Lay the bars on a gap-compressed axis (``True``) or on the calendar."""
        data = self.data
        timemap = TimeMap.build(
            data.starts, data.ends, gap_hours=self._gap_hours, compressed=compressed
        )
        self._timemap = timemap
        self._x0 = timemap.to_x(data.starts)
        self._x1 = timemap.to_x(data.ends)
        self._draw_bars()

        colors = theme.current()
        spans = timemap.block_spans()
        self._blocks.set_segments(
            [a for a, _ in spans], [b for _, b in spans], [colors.block_fill] * len(spans)
        )
        plot = self.getPlotItem()
        for line in self._gap_lines:
            plot.removeItem(line)
        self._gap_lines = []
        for x in timemap.gap_centers():
            line = pg.InfiniteLine(
                pos=x,
                angle=90,
                movable=False,
                pen=pg.mkPen(colors.gap_line, width=1, style=Qt.PenStyle.DashLine),
            )
            line.setZValue(-12)
            plot.addItem(line, ignoreBounds=True)
            self._gap_lines.append(line)

        self._axis.set_timemap(timemap, major_with_time=timemap.calendar_days < 2)
        span = timemap.span
        vb = plot.getViewBox()
        vb.setLimits(
            xMin=-0.25 * span, xMax=1.05 * span, minXRange=min(1 / 60, span), maxXRange=1.3 * span
        )
        self._auto_view = True
        self.reset_view()
        if self._hover >= 0:
            self._set_hover(self._hover)

    def reset_view(self) -> None:
        """Show the whole axis, with room on the left for the date of the first recording block.

        A tick label is drawn only when it fits inside the axis, so the label
        of the first block start, which sits at the very left, needs half its
        width of padding before it; the padding is converted from pixels at
        the current widget width.
        """
        vb = self.getPlotItem().getViewBox()
        span = self._timemap.span
        width = vb.width() if vb.width() > 50 else 700.0
        left = (0.5 * self._axis.major_label_px() + 4.0) / width * span
        vb.setXRange(-left, span + 0.01 * span, padding=0)

    def _on_manual_range(self, *args) -> None:
        self._auto_view = False

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # pyqtgraph resizes the view from its own constructor, before this class has set anything.
        if getattr(self, "_auto_view", False) and getattr(self, "_timemap", None) is not None:
            self.reset_view()

    def title_html(self) -> str:
        """The well's name and a one-line summary of its recording, for the label above the plot."""
        data, bursts = self.data, self._bursts
        rows = data.rows
        first, last = pd.Timestamp(rows["start"].min()), pd.Timestamp(rows["end"].max())
        days = bursts.calendar_days
        share = bursts.recorded_hours / max(24 * days, 1e-9)
        n_blocks = len(bursts.blocks)
        n_bars, instances = data.n_instances, data.origin.n_instances
        if data.joined_view and n_bars < instances:
            still = data.n_overlapping
            counts = (
                f"{instances} instances joined into {n_bars} bar{'s' if n_bars > 1 else ''} · "
                f"{still} still overlap{'s' if still == 1 else ''} another"
                + (" (labels disagree)" if still else "")
            )
        else:  # nothing to join on this well: the plain count says it all
            counts = (
                f"{data.n_instances} instance{'s' if data.n_instances > 1 else ''} · "
                f"{data.n_overlapping} overlap another"
            )
        summary = (
            f"{counts} · deepest pile-up {data.n_lanes} · "
            f"{bursts.recorded_hours:,.1f} h in {n_blocks} burst{'s' if n_blocks > 1 else ''} over "
            f"{days:,.0f} day{'s' if round(days) != 1 else ''} ({share:.1%}) · {first:%Y-%m-%d} → {last:%Y-%m-%d}"
        )
        return (
            f'<span style="font-size:10pt; font-weight:bold;">{data.label}</span>'
            f'&nbsp;&nbsp;<span style="font-size:8pt; color:{theme.current().muted};">{summary}</span>'
        )

    # -- mouse

    def _hit(self, scene_pos) -> int:
        vb = self.getPlotItem().getViewBox()
        if not vb.sceneBoundingRect().contains(scene_pos):
            return -1
        point = vb.mapSceneToView(scene_pos)
        tolerance = 2.0 * vb.viewPixelSize()[0]  # two pixels, so a sliver can be hit
        lanes = self.data.rows["lane"].to_numpy(dtype=float)
        hits = np.flatnonzero(
            (point.x() >= self._x0 - tolerance)
            & (point.x() <= self._x1 + tolerance)
            & (np.abs(point.y() - lanes) <= BAR_HEIGHT / 2)
        )
        return int(hits[0]) if len(hits) else -1

    def _on_mouse_moved(self, pos) -> None:
        index = self._hit(pos)
        if index != self._hover:
            self._set_hover(index)

    def _set_hover(self, index: int) -> None:
        self._hover = index
        if index < 0:
            self._bars.clear_highlight()
        else:
            partners = self.data.partners[index]
            starts, ends = self.data.starts, self.data.ends
            lanes = self.data.rows["lane"].to_numpy(dtype=float)
            hatches = []
            for j in partners:
                shared_start = max(starts[index], starts[j])
                shared_end = min(ends[index], ends[j])
                hx0, hx1 = self._timemap.to_x([shared_start, shared_end])
                hx1 = max(hx1, hx0 + 1e-6)
                hatches.append((float(hx0), float(hx1), float(lanes[j])))
                hatches.append((float(hx0), float(hx1), float(lanes[index])))
            self._bars.set_highlight(index, partners, hatches)
        self.hovered.emit(index)

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        if self._hover != -1:
            self._set_hover(-1)

    def _on_mouse_clicked(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or event.double():
            return
        index = self._hit(event.scenePos())
        if index >= 0:
            event.accept()
            self.clicked.emit(index)


class WellCell(QWidget):
    """One cell of the grid: the well's title, wrapping as needed, above its timeline."""

    def __init__(self, plot: WellTimelinePlot, parent=None):
        super().__init__(parent)
        self.plot = plot
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        self.title = QLabel(plot.title_html())
        self.title.setTextFormat(Qt.TextFormat.RichText)
        self.title.setWordWrap(True)
        self.title.setContentsMargins(6, 0, 6, 0)
        layout.addWidget(self.title)
        layout.addWidget(plot)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


class TimelinesPage(QWidget):
    """Grid of well timelines with filtering, sorting and the legend of the colors drawn.

    Signals
    -------
    status(str)
        What the main window's status bar should say: the instance under the
        pointer, or the page's hint.
    summary_changed()
        The one-line count of what is on show has changed.
    open_requested(WellData, int)
        A bar was clicked: the well as drawn, and the bar's row position.
    """

    status = Signal(str)
    summary_changed = Signal()
    open_requested = Signal(object, int)

    def hint(self) -> str:
        """What the status bar says when the pointer is over nothing in particular."""
        return HINT

    def __init__(
        self,
        info: DatasetInfo,
        gap_hours: float = DEFAULT_GAP_HOURS,
        columns: int = 2,
        parent=None,
    ):
        super().__init__(parent)
        self.info = info
        self._gap_hours = gap_hours
        self._plots: dict[int, WellTimelinePlot] = {}
        self._cells: dict[int, WellCell] = {}
        self.wells: list[WellData] = []
        self._joined_wells: list[WellData] = []
        self._availability: Availability | None = None
        self._fault_filter: int | None = None
        self._catalogue = None
        self._summary = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._build_toolbar(columns))
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(8, 0, 8, 4)
        body_layout.setSpacing(6)
        # The key of the bars when they say how much of a sensor was recorded;
        # the color key of the faults takes its place otherwise.
        self._state_key = StateKey(("ramp", "frozen", "absent", "implausible"))
        self._state_key.hide()
        body_layout.addWidget(self._state_key, 0, Qt.AlignmentFlag.AlignLeft)
        self._legend = LegendBar()
        self._legend.fault_clicked.connect(self.toggle_fault_filter)
        body_layout.addWidget(self._legend)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._container = QWidget()
        self._grid = QGridLayout(self._container)
        self._grid.setContentsMargins(0, 2, 0, 2)
        self._grid.setHorizontalSpacing(GRID_SPACING[0])
        self._grid.setVerticalSpacing(GRID_SPACING[1])
        self._empty = QLabel("No well matches the current filters.")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.hide()
        self._scroll.setWidget(self._container)
        body_layout.addWidget(self._scroll, 1)
        body_layout.addWidget(self._empty)
        layout.addWidget(body, 1)
        self._restyle()

    # -- construction

    def _build_toolbar(self, columns: int) -> QToolBar:
        bar = QToolBar("Timelines")
        bar.setMovable(False)

        bar.addWidget(QLabel(" Columns "))
        self._columns = QSpinBox()
        self._columns.setRange(1, 4)
        self._columns.setValue(columns)
        self._columns.valueChanged.connect(self._relayout)
        bar.addWidget(self._columns)

        bar.addSeparator()
        bar.addWidget(QLabel(" Show "))
        self._filter = QComboBox()
        self._filter.addItems(["All wells", "Wells with overlaps"])
        self._filter.currentIndexChanged.connect(self._relayout)
        bar.addWidget(self._filter)

        bar.addWidget(QLabel(" Sort by "))
        self._sort = QComboBox()
        self._sort.addItems(list(SORT_KEYS))
        self._sort.currentIndexChanged.connect(self._relayout)
        bar.addWidget(self._sort)

        bar.addSeparator()
        self._compress = QCheckBox("Compress silences")  # the name the help and README use
        self._compress.setChecked(True)
        self._compress.setToolTip(
            "Collapse the months of silence between bursts of recording to narrow dashed blanks, "
            "so the instances stay visible; uncheck for a true calendar axis."
        )
        self._compress.toggled.connect(self._set_compressed)
        bar.addWidget(self._compress)
        self._join = QCheckBox("Join overlapping instances")
        self._join.setToolTip(
            "Merge the instances of a well that overlap in time into one bar wherever their labels "
            "agree on the shared stretch (an unlabeled sample agrees with anything). Instances "
            "whose labels disagree there stay apart, so the overlaps that remain are exactly the "
            "labeling conflicts. A bar joined from several fault folders is striped with every "
            "folder's color; clicking it opens the time series of every instance behind it."
        )
        self._join.toggled.connect(self._on_join_toggled)
        bar.addWidget(self._join)

        bar.addSeparator()
        bar.addWidget(QLabel(" Bar color "))
        self._coloring = QComboBox()
        self._coloring.addItems(list(COLORINGS))
        self._coloring.setToolTip(
            "What fills a bar: the fault folder of its instance, tinted by how far the fault "
            "developed; or how much of one sensor the instance recorded, so that the grid shows "
            "the history of that sensor on every well, an era of absence or a scattering of it."
        )
        self._coloring.currentIndexChanged.connect(self._recolor)
        bar.addWidget(self._coloring)
        self._sensor = QComboBox()
        self._sensor.setToolTip("The sensor the bars are tinted by")
        self._sensor.currentIndexChanged.connect(self._recolor)
        self._sensor_action = bar.addWidget(self._sensor)
        self._sensor_action.setVisible(False)

        # No button of its own: the key's own title bar is how it is retracted.
        key_action = QAction("Color key", self)
        key_action.setShortcut("Ctrl+L")
        key_action.triggered.connect(lambda: self._legend.set_collapsed(not self._legend.collapsed))
        self.addAction(key_action)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bar.addWidget(spacer)
        self._fault_button = QPushButton()
        self._fault_button.setToolTip("Show every well again")
        self._fault_button.clicked.connect(lambda: self.toggle_fault_filter(self._fault_filter))
        # A widget in a toolbar is shown through its action, which overrides hide().
        self._fault_action = bar.addWidget(self._fault_button)
        self._fault_action.setVisible(False)
        return bar

    def set_catalogue(self, catalogue: pd.DataFrame, wells: list[WellData]) -> None:
        """Take a new catalogue and its wells: join each, read what they recorded, rebuild the grid."""
        self._catalogue = catalogue
        self.wells = list(wells)
        self._joined_wells = [well.joined() for well in self.wells]
        self._availability = Availability.from_wells(self.wells, self.info)
        wanted = self._sensor.currentText()
        self._sensor.blockSignals(True)
        self._sensor.clear()
        self._sensor.addItems(self._availability.sensors)
        index = self._sensor.findText(wanted)
        self._sensor.setCurrentIndex(max(index, 0))
        self._sensor.blockSignals(False)
        self._build_grid()

    def _shown_wells(self) -> list[WellData]:
        """The wells as the grid draws them: instance by instance, or joined into bars."""
        return self._joined_wells if self._join.isChecked() else self.wells

    def _on_join_toggled(self, *args) -> None:
        """Join or unjoin the instances, keeping the well the reader was looking at in view.

        The same wells, in the same order, are drawn either way — only the bars
        inside them change — so throwing the reader back to the first well of a
        long grid loses the very comparison the tick was made to see.
        """
        anchor = self._scroll_anchor()
        self._build_grid(keep_scroll=True)
        self._restore_scroll(anchor)

    def _build_grid(self, *args, keep_scroll: bool = False) -> None:
        """Build every timeline again, from the instances or from their joins."""
        for cell in self._cells.values():
            self._grid.removeWidget(cell)
            cell.hide()  # gone from the screen at once, not only when Qt gets to deleting it
            cell.deleteLater()
        self._plots = {}
        self._cells = {}
        shown = self._shown_wells()
        self.slots = lane_slots(shown, MIN_LANE_SLOTS, MAX_LANE_SLOTS)
        height = PLOT_CHROME_PX + LANE_PX * self.slots
        for well in shown:
            plot = WellTimelinePlot(
                well, self.info, self.slots, self._compress.isChecked(), self._gap_hours
            )
            plot.setFixedHeight(height + LANE_PX * max(0, well.n_lanes - self.slots))
            plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            plot.set_coloring(*self._coloring_of(well))
            plot.hovered.connect(partial(self._on_hover, plot))
            plot.clicked.connect(partial(self._on_click, plot))
            self._plots[well.well] = plot
            self._cells[well.well] = WellCell(plot)

        present = set().union(*(well.present_colors() for well in shown))
        self._legend.set_entries(
            legend_entries(present, self.info.fault_names), self.info.fault_names
        )
        n_over = sum(1 for well in shown if well.n_overlapping > 0)
        n_overlapping = sum(well.n_overlapping for well in shown)
        version = f"3W {self.info.version} · " if self.info.version else ""
        instances = f"{version}{len(self._catalogue)} real instances on {len(shown)} wells"
        if self._join.isChecked():
            bars = sum(well.n_instances for well in shown)
            self._summary = (
                f"{instances}, joined into {bars} bars, "
                f"{n_overlapping} still overlapping on {n_over} wells "
            )
        else:
            self._summary = f"{instances}, {n_overlapping} overlapping on {n_over} wells "
        self.summary_changed.emit()
        self._show_key()
        self._relayout(keep_scroll=keep_scroll)

    def summary(self) -> str:
        """One line for the status bar: what the grid is showing."""
        return self._summary

    # -- coloring

    @property
    def sensor_coloring(self) -> str | None:
        """The sensor the bars are tinted by, or ``None`` while they carry their fault colors."""
        if self._coloring.currentIndex() == 0 or self._availability is None:
            return None
        return self._sensor.currentText() or None

    def _coloring_of(self, data: WellData) -> tuple[list[list[str]] | None, list[bool]]:
        """What fills the bars of one well and which wear the mark, under the current choice.

        In the fault coloring a bar is marked when any sensor of any instance
        behind it reads outside its plausible range; tinted by one sensor, it
        is marked for that sensor alone, the bar being about that sensor.
        """
        availability = self._availability
        if availability is None:
            return None, [False] * data.n_instances
        sensor = self.sensor_coloring
        if sensor is None:
            marks = [
                availability.implausible_any(bar_rows(availability, data, index))
                for index in range(data.n_instances)
            ]
            return None, marks
        colors = theme.current()
        column = availability.sensors.index(sensor)
        fills, marks = [], []
        for index in range(data.n_instances):
            shares, flagged = availability.shares_of(bar_rows(availability, data, index), column)
            if shares[LIVE] > 0:
                fills.append([ramp_color(shares[LIVE])])
            elif shares[FROZEN] > 0:
                fills.append([colors.frozen])
            else:
                fills.append([colors.block_fill])
            marks.append(flagged)
        return fills, marks

    def _recolor(self, *args) -> None:
        """Fill the bars again under the choice of the Bar color box, without rebuilding the grid."""
        for plot in self._plots.values():
            plot.set_coloring(*self._coloring_of(plot.data))
        self._show_key()
        self.status.emit(HINT)

    def _show_key(self) -> None:
        """Show the key that names the bars' fills: the faults', or the sensor's."""
        sensor = self.sensor_coloring
        self._sensor_action.setVisible(self._coloring.currentIndex() == 1)
        self._legend.setVisible(sensor is None)
        self._state_key.setVisible(sensor is not None)
        if sensor is not None:
            self._state_key.set_text("ramp", f"{sensor}: share of samples live, from a few to all")

    # -- appearance

    def _restyle(self) -> None:
        """Take the colors of the theme now in force, for the chrome this page owns."""
        self._empty.setStyleSheet(f"color: {theme.current().faint}; padding: 40px;")

    def apply_theme(self) -> None:
        """Take the colors of the theme now in force; the grid itself is rebuilt by ``set_catalogue``."""
        self._restyle()
        self._legend.apply_theme()
        self._state_key.apply_theme()

    # -- behaviour

    def _selected_wells(self) -> list[WellData]:
        wells = self._shown_wells()
        if self._filter.currentIndex() == 1:
            wells = [well for well in wells if well.n_overlapping > 0]
        if self._fault_filter is not None:
            wells = [well for well in wells if self._fault_filter in well.fault_classes()]
        return sorted(wells, key=SORT_KEYS[self._sort.currentText()])

    def _relayout(self, *args, keep_scroll: bool = False) -> None:
        for cell in self._cells.values():
            self._grid.removeWidget(cell)
            cell.hide()
        columns = self._columns.value()
        selected = self._selected_wells()
        for i, well in enumerate(selected):
            cell = self._cells[well.well]
            self._grid.addWidget(cell, i // columns, i % columns)
            cell.show()
        for column in range(4):
            self._grid.setColumnStretch(column, 1 if column < columns else 0)
        # A stretch row below the cells keeps a short grid at the top instead of spread out.
        rows = (len(selected) + columns - 1) // columns
        for row in range(self._grid.rowCount()):
            self._grid.setRowStretch(row, 0)
        self._grid.setRowStretch(rows, 1)
        self._scroll.setVisible(bool(selected))
        self._empty.setVisible(not selected)
        if not keep_scroll:
            # A new set of wells, or a new order for them, is a new page: it
            # starts at the top. What only redraws the same wells says so.
            self._scroll.verticalScrollBar().setValue(0)

    # -- keeping the reader's place

    def _scroll_anchor(self) -> tuple[int, float] | None:
        """The well at the top of the viewport, and how far into its cell the view has scrolled.

        A pixel offset on its own does not survive a rebuild: joining leaves a
        well fewer stack levels, so its cell is shorter, and an offset measured
        against the taller one lands past the end of it, on a well further
        down. The distance is therefore kept as a share of the cell, which
        means the same place whatever height it comes back at.
        """
        tops = sorted((cell.y(), well) for well, cell in self._cells.items() if not cell.isHidden())
        if not tops:
            return None
        y = self._scroll.verticalScrollBar().value()
        top, well = tops[0]
        for other_top, other_well in tops:
            if other_top > y:
                break
            top, well = other_top, other_well
        return well, (y - top) / max(self._cells[well].height(), 1)

    def _restore_scroll(self, anchor: tuple[int, float] | None) -> None:
        """Bring the anchored well back to the top of the viewport.

        The cells are laid out at once so their positions can be read, but the
        scroll range only catches up when Qt gets to the layout request the
        rebuild posted, and a value beyond a stale range would be clamped away;
        hence the second, exact attempt on the next turn of the event loop.
        """
        if anchor is None:
            return
        well, share = anchor
        cell = self._cells.get(well)
        if cell is None or cell.isHidden():
            return
        self._grid.activate()
        bar = self._scroll.verticalScrollBar()
        wanted = max(0, round(cell.y() + share * cell.height()))
        bar.setValue(min(wanted, bar.maximum()))
        QTimer.singleShot(0, lambda: bar.setValue(min(wanted, bar.maximum())))

    def toggle_fault_filter(self, fault_class: int | None) -> None:
        """Show only the wells that recorded ``fault_class``; the same fault again clears it."""
        self._fault_filter = None if fault_class == self._fault_filter else fault_class
        self._legend.set_selected_fault(self._fault_filter)
        if self._fault_filter is not None:
            name = self.info.fault_name(self._fault_filter)
            wells = sum(1 for well in self.wells if self._fault_filter in well.fault_classes())
            self._fault_button.setText(f"✕  {name}")
            self._fault_button.setToolTip(
                f"Showing the {wells} wells that recorded {name}. Click to show every well again."
            )
        self._fault_action.setVisible(self._fault_filter is not None)
        self._relayout()

    def _set_compressed(self, compressed: bool) -> None:
        for plot in self._plots.values():
            plot.set_compressed(compressed)

    def reset_views(self) -> None:
        for plot in self._plots.values():
            plot._auto_view = True
            plot.reset_view()

    def _on_hover(self, plot: WellTimelinePlot, index: int) -> None:
        """Describe the instance under the pointer and key its color in the legend."""
        if index < 0:
            self.status.emit(HINT)
            self._legend.highlight(set())
            return
        text = describe_instance(plot.data, index, self.info, self._availability)
        sensor = self.sensor_coloring
        if sensor is not None:
            text += " · " + describe_sensor_in_bar(self._availability, plot.data, index, sensor)
        self.status.emit(text)
        data = plot.data
        self._legend.highlight(
            {
                legend_key(fault_class, reach)
                for i in (index, *data.partners[index])
                for fault_class, reach in data.colors[i]
            }
        )

    def _on_click(self, plot: WellTimelinePlot, index: int) -> None:
        self.open_requested.emit(plot.data, index)
