"""The main window: a grid of well timelines, one interactive per-well plot each.

Every plot is one well. Each real instance recorded on it is a bar from its
first to its last timestamp, stacked on the instances it overlaps in time, so a
well recorded twice shows at a glance. Hovering a bar highlights the instances
it overlaps and hatches the stretch they share; clicking it opens an
``InstanceWindow`` with their time series.
"""

from functools import partial

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from overlap_viewer import styling, theme
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
    ScanCancelled,
    WellData,
    instance_title,
    lane_slots,
    split_wells,
)
from overlap_viewer.help import HelpWindow, real_instance_counts
from overlap_viewer.items import (
    InstanceBarsItem,
    ScrollFriendlyViewBox,
    SegmentsItem,
    TimeAxisItem,
    WheelToParent,
)
from overlap_viewer.legend import LegendBar
from overlap_viewer.loading import FrameCache, catalogue_with_progress
from overlap_viewer.palette import bar_color, fault_color, legend_entries, legend_key
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


def describe_instance(data: WellData, index: int, info: DatasetInfo) -> str:
    """One line about an instance: name, fault, reach, span, size, level, partners."""
    row = data.rows.iloc[index]
    fault_class = int(row["fault_class"])
    fault = info.fault_name(fault_class)
    reach = "" if fault_class == 0 else f" · {REACH_LABELS[row['reach']]}"
    start, end = pd.Timestamp(row["start"]), pd.Timestamp(row["end"])
    end_fmt = "%H:%M:%S" if end.date() == start.date() else "%Y-%m-%d %H:%M:%S"
    partners = data.partners[index]
    if len(partners):
        names = [
            f"{instance_title(data.rows.iloc[j])} ({info.fault_name(int(data.rows.iloc[j]['fault_class']))})"
            for j in partners[:4]
        ]
        if len(partners) > 4:
            names.append(f"+{len(partners) - 4} more")
        overlap = (
            f"overlaps {len(partners)} instance{'s' if len(partners) > 1 else ''}: "
            + ", ".join(names)
        )
    else:
        overlap = "overlaps no other instance"
    return (
        f"{instance_title(row)} · {fault}{reach} · {start:%Y-%m-%d %H:%M:%S} → {end.strftime(end_fmt)} "
        f"({row['hours']:.1f} h, {int(row['n_samples']):,} samples) · stack level {int(row['lane']) + 1} · {overlap}"
    )


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

    def set_compressed(self, compressed: bool) -> None:
        """Lay the bars on a gap-compressed axis (``True``) or on the calendar."""
        data = self.data
        timemap = TimeMap.build(
            data.starts, data.ends, gap_hours=self._gap_hours, compressed=compressed
        )
        self._timemap = timemap
        self._x0 = timemap.to_x(data.starts)
        self._x1 = timemap.to_x(data.ends)
        rows = data.rows
        fills = [bar_color(int(fc), reach) for fc, reach in zip(rows["fault_class"], rows["reach"])]
        edges = [fault_color(int(fc)) for fc in rows["fault_class"]]
        self._bars.set_bars(
            self._x0, self._x1, rows["lane"].to_numpy(dtype=float), fills, edges, rows["stamp"]
        )

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
        summary = (
            f"{data.n_instances} instance{'s' if data.n_instances > 1 else ''} · "
            f"{data.n_overlapping} overlap another · deepest pile-up {data.n_lanes} · "
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


class OverviewWindow(QMainWindow):
    """Grid of well timelines with filtering, sorting and the legend of the colors drawn."""

    def __init__(
        self,
        info: DatasetInfo,
        catalogue: pd.DataFrame,
        gap_hours: float = DEFAULT_GAP_HOURS,
        columns: int = 2,
        frames: FrameCache | None = None,
        theme_mode: str = "system",
        parent=None,
    ):
        super().__init__(parent)
        self.info = info
        self._gap_hours = gap_hours
        self._frames = frames or FrameCache()
        self._windows: list[QMainWindow] = []
        self._plots: dict[int, WellTimelinePlot] = {}
        self._cells: dict[int, WellCell] = {}
        self._fault_filter: int | None = None
        self._help: HelpWindow | None = None
        self._theme_mode = theme_mode
        self.setWindowTitle(f"3W Overlap Viewer — {info.raw_dir}")

        self._build_toolbar(columns)
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        self._legend = LegendBar()
        self._legend.fault_clicked.connect(self.toggle_fault_filter)
        layout.addWidget(self._legend)
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
        layout.addWidget(self._scroll, 1)
        layout.addWidget(self._empty)
        self.setCentralWidget(central)

        self._status = ElidedLabel(HINT)
        self.statusBar().addWidget(self._status, 1)

        self._restyle()
        self.set_catalogue(catalogue)

        # A ``system`` mode has to keep up with the desktop changing its mind.
        # Queued, because installing a theme sets the color scheme itself and
        # would otherwise re-enter this window in the middle of a rebuild.
        QApplication.instance().styleHints().colorSchemeChanged.connect(
            self._on_system_scheme, Qt.ConnectionType.QueuedConnection
        )

    # -- construction

    def _build_toolbar(self, columns: int) -> None:
        bar = QToolBar("View")
        bar.setMovable(False)
        self.addToolBar(bar)

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
        self._compress = QCheckBox("Compress silences between recordings")
        self._compress.setChecked(True)
        self._compress.setToolTip(
            "Collapse the months of silence between bursts of recording to narrow dashed blanks, "
            "so the instances stay visible; uncheck for a true calendar axis."
        )
        self._compress.toggled.connect(self._set_compressed)
        bar.addWidget(self._compress)

        bar.addSeparator()
        bar.addWidget(QLabel(" Theme "))
        self._theme = QComboBox()
        self._theme.addItems([mode.capitalize() for mode in theme.MODES])
        self._theme.setCurrentIndex(theme.MODES.index(self._theme_mode))
        self._theme.setToolTip(
            "Light or dark for both the windows and the plots inside them; System follows the "
            "desktop. The choice is remembered."
        )
        self._theme.currentIndexChanged.connect(
            lambda index: self.set_theme_mode(theme.MODES[index])
        )
        bar.addWidget(self._theme)

        bar.addSeparator()
        reset = QAction("Reset views", self)
        reset.setShortcut("Ctrl+R")
        reset.triggered.connect(self.reset_views)
        bar.addAction(reset)
        rescan = QAction("Rescan dataset", self)
        rescan.setToolTip("Read every instance again, ignoring the cached catalogue")
        rescan.triggered.connect(self._rescan)
        bar.addAction(rescan)
        help_action = QAction("Help", self)
        help_action.setShortcut("F1")
        help_action.setToolTip("What every fault class and every variable means (F1)")
        help_action.triggered.connect(self.show_help)
        bar.addAction(help_action)
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
        self._dataset_label = QLabel()
        bar.addWidget(self._dataset_label)

    def set_catalogue(self, catalogue: pd.DataFrame) -> None:
        """Rebuild every timeline from a new catalogue."""
        for cell in self._cells.values():
            self._grid.removeWidget(cell)
            cell.deleteLater()
        self._catalogue = catalogue
        if self._help is not None:  # its instance counts describe the old catalogue
            self._help.close()
            self._help.deleteLater()
            self._help = None
        self._plots = {}
        self._cells = {}
        self.wells = split_wells(catalogue)
        self.slots = lane_slots(self.wells, MIN_LANE_SLOTS, MAX_LANE_SLOTS)
        height = PLOT_CHROME_PX + LANE_PX * self.slots
        for well in self.wells:
            plot = WellTimelinePlot(
                well, self.info, self.slots, self._compress.isChecked(), self._gap_hours
            )
            plot.setFixedHeight(height + LANE_PX * max(0, well.n_lanes - self.slots))
            plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            plot.hovered.connect(partial(self._on_hover, plot))
            plot.clicked.connect(partial(self._on_click, plot))
            self._plots[well.well] = plot
            self._cells[well.well] = WellCell(plot)

        present = set().union(*(well.present_colors() for well in self.wells))
        self._legend.set_entries(
            legend_entries(present, self.info.fault_names), self.info.fault_names
        )
        n_over = sum(1 for well in self.wells if well.n_overlapping > 0)
        n_overlapping = sum(well.n_overlapping for well in self.wells)
        version = f"3W {self.info.version} · " if self.info.version else ""
        self._dataset_label.setText(
            f"{version}{len(catalogue)} real instances on {len(self.wells)} wells, "
            f"{n_overlapping} overlapping on {n_over} wells "
        )
        self._relayout()

    # -- appearance

    def _restyle(self) -> None:
        """Take the colors of the theme now in force, for the chrome this window owns."""
        colors = theme.current()
        self._empty.setStyleSheet(f"color: {colors.faint}; padding: 40px;")
        self._dataset_label.setStyleSheet(f"color: {colors.muted};")

    def set_theme_mode(self, mode: str) -> None:
        """Switch to ``light``, ``dark`` or ``system``, and repaint every open window.

        The plots cannot be recolored in place: pyqtgraph reads its background
        and its foreground when an item is built, so the grid is built again
        from the same catalogue, which is the path a rescan already takes.
        """
        self._theme_mode = mode
        styling.save_mode(mode)
        if self._theme.currentIndex() != theme.MODES.index(mode):  # a mode set in code
            self._theme.blockSignals(True)
            self._theme.setCurrentIndex(theme.MODES.index(mode))
            self._theme.blockSignals(False)
        before = theme.current()
        if styling.apply(mode) is before:
            return  # e.g. System on a light desktop, chosen while already light
        self._restyle()
        for window in list(self._windows):
            window.apply_theme()
        self.set_catalogue(self._catalogue)

    def _on_system_scheme(self, *args) -> None:
        """Follow the desktop switching between light and dark, while ``system`` is chosen."""
        if self._theme_mode == "system":
            self.set_theme_mode("system")

    # -- behaviour

    def _selected_wells(self) -> list[WellData]:
        wells = self.wells
        if self._filter.currentIndex() == 1:
            wells = [well for well in wells if well.n_overlapping > 0]
        if self._fault_filter is not None:
            wells = [well for well in wells if self._fault_filter in well.fault_classes()]
        return sorted(wells, key=SORT_KEYS[self._sort.currentText()])

    def _relayout(self, *args) -> None:
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
        self._scroll.verticalScrollBar().setValue(0)

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

    def show_help(self) -> None:
        """Open (or raise) the help window, on the tab explaining the fault classes."""
        if self._help is None:
            self._help = HelpWindow(
                self.info, counts=real_instance_counts(self._catalogue), parent=self
            )
        self._help.show_tab("Fault classes")

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
            self._status.setText(HINT)
            self._legend.highlight(set())
            return
        self._status.setText(describe_instance(plot.data, index, self.info))
        rows = plot.data.rows
        self._legend.highlight(
            {
                legend_key(int(rows.iloc[i]["fault_class"]), rows.iloc[i]["reach"])
                for i in (index, *plot.data.partners[index])
            }
        )

    def _on_click(self, plot: WellTimelinePlot, index: int) -> None:
        from overlap_viewer.instance_window import (
            InstanceWindow,
        )

        try:
            window = InstanceWindow(plot.data, index, self.info, self._frames)
        except Exception as error:  # noqa: BLE001 - one unreadable file must not take the app down
            QMessageBox.warning(
                self, "Could not open the instances", f"{type(error).__name__}: {error}"
            )
            return
        window.destroyed.connect(
            lambda *_: self._windows.remove(window) if window in self._windows else None
        )
        self._windows.append(window)
        window.show()

    def _rescan(self) -> None:
        try:
            catalogue = catalogue_with_progress(self.info, use_cache=False, parent=self)
        except ScanCancelled:
            return
        except Exception as error:  # noqa: BLE001 - report, keep the current catalogue
            QMessageBox.critical(self, "Rescan failed", f"{type(error).__name__}: {error}")
            return
        self.set_catalogue(catalogue)

    def closeEvent(self, event) -> None:
        for window in list(self._windows):
            window.close()
        super().closeEvent(event)
