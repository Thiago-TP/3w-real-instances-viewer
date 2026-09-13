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

from typing import NamedTuple

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtCore import Qt
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

from overlap_viewer.config import FAULT_SIGNATURES, REACH_LABELS, TRACE_COLOR
from overlap_viewer.dataset import DatasetInfo, WellData, instance_title
from overlap_viewer.help import HelpWindow
from overlap_viewer.items import (
    AnchoredText,
    HeaderLabel,
    ScrollFriendlyViewBox,
    SegmentsItem,
    TimeAxisItem,
    WheelToParent,
)
from overlap_viewer.labels import (
    FeatureStats,
    coverage_counts,
    feature_stats,
    format_delta,
    label_fault,
    label_kind,
    label_name,
    label_segments,
    padded_range,
    sensor_columns,
    state_name,
)
from overlap_viewer.loading import FrameCache
from overlap_viewer.overview import ElidedLabel
from overlap_viewer.palette import (
    background_color,
    bar_color,
    state_color,
    tint,
    unknown_background,
)
from overlap_viewer.timemap import TimeMap

AXIS_WIDTH = 84  # every left axis has this width, so all plots share the same x pixels
BAND_PX = 18
HEADER_PX = 24
PLOT_MIN_PX = 150
AXIS_PX = 28
ROW_SPACING = 2  # between two rows of one instance block
BLOCK_SPACING = 16  # added above the header of every block but the first
SHARED_COLORS = {2: "#9a9a9a", 3: "#6f6f6f"}  # instances sharing a stretch; darker beyond
SI_UNITS = ("Pa",)  # units pyqtgraph may prefix (kPa, MPa); the others stay literal

HINT = (
    "Tick features to add their plots · drag to pan · Ctrl + wheel to zoom (the wheel alone "
    "scrolls) · plots share the time axis, and the plots of one feature share their value axis"
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


class InstanceWindow(QMainWindow):
    """Time series of one instance and of the instances of its well that overlap it."""

    def __init__(
        self, data: WellData, index: int, info: DatasetInfo, frames: FrameCache, parent=None
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.info = info
        self.well = data
        members = data.group(index)
        self.rows = data.rows.iloc[members].reset_index(drop=True)
        self.clicked = members.index(index)
        self.timemap = TimeMap.build(self.rows["start"], self.rows["end"], compressed=False)

        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            self.frames = [frames.get(path) for path in self.rows["path"]]
        finally:
            QApplication.restoreOverrideCursor()

        self._features = self._feature_table()
        self._checks: dict[str, QCheckBox] = {}
        self._plots: dict[tuple[int, str], pg.PlotItem] = {}
        self._feature_masters: dict[str, pg.PlotItem] = {}
        self._crosshairs: list[pg.InfiniteLine] = []
        self._master: pg.PlotItem | None = None
        self._x_range: tuple[float, float] | None = None
        self._signature = self._signature_for_group()
        self._help: HelpWindow | None = None

        clicked = instance_title(self.rows.iloc[self.clicked])
        others = len(self.rows) - 1
        self.setWindowTitle(
            f"{data.label} · {clicked}"
            + (f" and {others} overlapping instance{'s' if others > 1 else ''}" if others else "")
        )
        self._build_ui()
        self._rebuild()

    # -- data

    def _feature_table(self) -> pd.DataFrame:
        """Every sensor the dataset or the files declare, alphabetically, with how many instances record it."""
        names = set(self.info.sensor_names)
        for frame in self.frames:
            names.update(sensor_columns(frame))
        rows = []
        for name in sorted(names):
            recorded = sum(
                1 for frame in self.frames if name in frame.columns and frame[name].notna().any()
            )
            rows.append({"sensor": name, "recorded": recorded})
        return pd.DataFrame(rows)

    def _default_feature(self) -> str | None:
        recorded = self._features[self._features["recorded"] > 0]
        return str(recorded["sensor"].iloc[0]) if len(recorded) else None

    def selected_features(self) -> list[str]:
        return [name for name, check in self._checks.items() if check.isChecked()]

    def _fault_of(self, position: int) -> int:
        return int(self.rows.iloc[position]["fault_class"])

    def _signature_for_group(self) -> tuple[int, tuple[str, ...]] | None:
        """The documented signature this window can offer, if any.

        The clicked instance decides, since the window was opened from it. Only
        when its own fault has no published signature does the window fall back
        to another fault present, and only if exactly one such fault is, so the
        button never silently mixes two events' variables.
        """
        clicked = self._fault_of(self.clicked)
        if clicked in FAULT_SIGNATURES:
            return clicked, FAULT_SIGNATURES[clicked]
        others = {self._fault_of(i) for i in range(len(self.rows))} & set(FAULT_SIGNATURES)
        if len(others) == 1:
            fault = others.pop()
            return fault, FAULT_SIGNATURES[fault]
        return None

    def _signature_features(self) -> list[str]:
        """The signature variables at least one of these instances actually recorded."""
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

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(8, 4, 8, 4)
        outer.setSpacing(4)
        header = QLabel(self._header_html())
        header.setTextFormat(Qt.TextFormat.RichText)
        header.setWordWrap(True)
        outer.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(8)
        body.addWidget(self._build_feature_panel())
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
        self.resize(1360, 860)

    def _build_feature_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(250)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("<b>Features</b>")
        layout.addWidget(title)
        buttons = QHBoxLayout()
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
        n = len(self.frames)
        for row in self._features.itertuples():
            unit = self.info.unit(row.sensor)
            check = QCheckBox(f"{row.sensor} [{unit}]" if unit else row.sensor)
            description = self.info.sensor_descriptions.get(row.sensor, "")
            recorded = f"recorded in {row.recorded} of {n} instance{'s' if n > 1 else ''}"
            check.setToolTip(f"{description}\n{recorded}" if description else recorded)
            check.setEnabled(row.recorded > 0)
            check.setChecked(row.sensor == default)
            check.toggled.connect(self._rebuild)
            self._checks[row.sensor] = check
            checks.addWidget(check)
        checks.addStretch(1)
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)
        note = QLabel("Greyed-out features were recorded by none of these instances.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #666666; font-size: 8pt;")
        layout.addWidget(note)
        return panel

    def _build_signature_check(self) -> QWidget:
        """The one-click selection of the variables that identify the event.

        Only the events the 3W paper illustrates have a published signature, so
        the box is disabled — and says why — for the others.
        """
        self._signature_check = QCheckBox("Signature")
        self._signature_check.toggled.connect(self._apply_signature)
        available = self._signature_features()
        if self._signature is None:
            self._signature_check.setEnabled(False)
            self._signature_check.setToolTip(
                "The 3W paper publishes a signature only for the events it illustrates "
                "(figures 3 to 7): Normal Operation, Spurious Closure of DHSV, Severe Slugging, "
                "Quick Restriction in PCK and Hydrate in Production Line. This window shows none "
                "of them."
            )
            return self._signature_check
        fault, variables = self._signature
        name = self.info.fault_name(fault)
        missing = [v for v in variables if v not in available]
        text = f"Signature of {name}: {', '.join(variables)}. These variables identify the event."
        if missing:
            text += f"\nNot recorded here, so left out: {', '.join(missing)}."
        if not available:
            self._signature_check.setEnabled(False)
            text += "\nNone of them is recorded by these instances."
        self._signature_check.setToolTip(text)
        self._signature_check.setText(f"Signature of {name}")
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
        clicked = instance_title(rows.iloc[self.clicked])
        others = len(rows) - 1
        what = f"<b>{clicked}</b>" + (
            f" and the {others} instance{'s' if others > 1 else ''} it overlaps"
            if others
            else " (overlaps no other instance)"
        )
        return (
            f'<span style="font-size:11pt;"><b>{self.well.label}</b> · {what}</span><br>'
            f'<span style="color:#444444;">{first:%Y-%m-%d %H:%M:%S} → {last:%Y-%m-%d %H:%M:%S} · {span_h:.1f} h spanned · '
            f"{shared_h:.1f} h recorded by two or more instances · {len(rows)} instance{'s' if len(rows) > 1 else ''} shown, "
            f"chronological</span>"
        )

    def _instance_html(self, position: int) -> str:
        row = self.rows.iloc[position]
        fault_class = int(row["fault_class"])
        color = bar_color(fault_class, row["reach"])
        fault = self.info.fault_name(fault_class)
        reach = "" if fault_class == 0 else f" ({REACH_LABELS[row['reach']]})"
        start, end = pd.Timestamp(row["start"]), pd.Timestamp(row["end"])
        end_fmt = "%H:%M:%S" if end.date() == start.date() else "%Y-%m-%d %H:%M:%S"
        partners = sum(
            1
            for other in range(len(self.rows))
            if other != position and self._overlaps(position, other)
        )
        badge = (
            '&nbsp;<span style="background-color:#333333; color:#ffffff;">&nbsp;clicked&nbsp;</span>'
            if position == self.clicked
            else ""
        )
        return (
            f'<span style="font-size:10pt;"><b>{instance_title(row)}</b></span>{badge}'
            f'&nbsp;&nbsp;<span style="font-size:9pt; color:{color};">&#9632;</span>'
            f'<span style="font-size:9pt; color:#333333;"> {fault}{reach} · {start:%Y-%m-%d %H:%M:%S} → {end.strftime(end_fmt)} · '
            f"{row['hours']:.1f} h · {int(row['n_samples']):,} samples · level {int(row['lane']) + 1} · "
            f"overlaps {partners} shown</span>"
        )

    def _overlaps(self, a: int, b: int) -> bool:
        ra, rb = self.rows.iloc[a], self.rows.iloc[b]
        return bool(ra["start"] <= rb["end"] and rb["start"] <= ra["end"])

    # -- the grid

    def _rebuild(self, *args) -> None:
        """Lay out header, bands and the selected feature plots of every instance."""
        if self._master is not None:
            self._x_range = tuple(self._master.getViewBox().viewRange()[0])
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            self._lay_out_stack()
        finally:
            QApplication.restoreOverrideCursor()
        self._sync_signature()
        self._apply_ranges()

    def _lay_out_stack(self) -> None:
        """Fill the stack: the shared-coverage band, then one block per instance."""
        layout = self._layout_widget
        layout.clear()
        self._plots = {}
        self._feature_masters = {}
        self._crosshairs = []
        self._master = None  # so the new master does not link itself to the removed one
        features = self.selected_features()

        heights: list[int] = []
        row = 0
        self._master = self._add_band(row, self._coverage_band_segments(), "shared")
        heights.append(BAND_PX)
        row += 1
        for position in range(len(self.rows)):
            # Every block but the first carries the room that separates it from
            # the one above, so the header reads as the title of what follows it.
            header_px = HEADER_PX + (BLOCK_SPACING if position else 0)
            label = HeaderLabel(justify="left")
            label.setText(self._instance_html(position))
            label.setFixedHeight(header_px)
            layout.addItem(label, row=row, col=0)
            heights.append(header_px)
            row += 1
            self._add_band(row, self._state_band_segments(position), "state")
            self._add_band(row + 1, self._class_band_segments(position), "class")
            heights += [BAND_PX, BAND_PX]
            row += 2
            for k, feature in enumerate(features):
                last = k == len(features) - 1
                self._add_feature_plot(row, position, feature, show_axis=last)
                heights.append(PLOT_MIN_PX + (AXIS_PX if last else 0))
                row += 1
            if not features:
                self._plots_last_axis_placeholder(row)
                heights.append(AXIS_PX + 4)
                row += 1
        layout.setMinimumHeight(self._stack_height(heights))

    def _stack_height(self, heights: list[int]) -> int:
        """How tall the stack must be for every row to get the height it asked for.

        The stack lives in a scroll area, which sizes it to its own minimum
        height whenever that is the larger. An underestimate therefore does not
        merely stop the scrollbar early: the grid inside squeezes its rows to
        fit, and the plots at the bottom come out clipped. The layout's own
        minimum is the authority on the total, with the sum of the rows as a
        floor for the moment before that minimum has been computed.
        """
        estimate = sum(heights) + ROW_SPACING * max(len(heights) - 1, 0) + 4
        minimum = self._layout_widget.ci.layout.effectiveSizeHint(Qt.SizeHint.MinimumSize).height()
        return int(max(estimate, minimum))

    def _new_plot(self, row: int, with_axis: bool) -> pg.PlotItem:
        axis_items = {"bottom": TimeAxisItem(self.timemap)} if with_axis else None
        plot = self._layout_widget.addPlot(
            row=row, col=0, viewBox=ScrollFriendlyViewBox(), axisItems=axis_items
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
            angle=90, movable=False, pen=pg.mkPen("#333333", width=1, style=Qt.PenStyle.DashLine)
        )
        crosshair.setZValue(40)
        crosshair.setVisible(False)
        plot.addItem(crosshair, ignoreBounds=True)
        self._crosshairs.append(crosshair)
        return plot

    def _add_band(self, row: int, segments: BandSegments, name: str) -> pg.PlotItem:
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
        return plot

    def _plots_last_axis_placeholder(self, row: int) -> None:
        """With no feature selected, a bare time axis still closes each block."""
        plot = self._new_plot(row, with_axis=True)
        plot.setFixedHeight(AXIS_PX + 4)
        plot.setMenuEnabled(False)
        plot.getViewBox().setMouseEnabled(x=True, y=False)
        plot.getAxis("left").setStyle(showValues=False)

    def _add_feature_plot(self, row: int, position: int, feature: str, show_axis: bool) -> None:
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

        stats = feature_stats(frame, feature)
        if stats.recorded:
            x = self.timemap.to_x(frame.index)
            y = frame[feature].to_numpy(dtype=float)
            curve = pg.PlotDataItem(x, y, pen=pg.mkPen(TRACE_COLOR, width=1), connect="finite")
            # Added before clipping and downsampling are switched on: while an item is being
            # added, pyqtgraph resolves its view to the layout widget, which those options query.
            plot.addItem(curve)
            curve.setDownsampling(auto=True, method="peak")
            curve.setClipToView(True)
            note = format_delta(stats.delta, unit) + (" (flat)" if stats.flat else "")
            AnchoredText(
                f'<span style="font-size:8pt; color:#222222;">{note} · coverage {stats.coverage:.1f} %</span>'
            ).attach(plot)
        else:
            AnchoredText(
                '<span style="font-size:10pt; color:#8a8a8a;">not recorded</span>',
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

    # -- segments

    def _class_band_segments(self, position: int, background: bool = False) -> BandSegments:
        frame = self.frames[position]
        fault_class = self._fault_of(position)
        offset = self.info.transient_offset
        segments = BandSegments([], [], [], [], [])
        for segment in label_segments(frame, "class"):
            a, b = self.timemap.to_x([segment.start, segment.end])
            kind = label_kind(segment.value, offset)
            fault = label_fault(segment.value, offset)
            hue_class = fault if fault is not None else fault_class
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
        segments = BandSegments([], [], [], [], [])
        for start, end, count in coverage_counts(self.rows["start"], self.rows["end"]):
            a, b = self.timemap.to_x([start, end])
            if count <= 0:
                segments.add(a, b, "#ffffff", "", False)
            elif count == 1:
                segments.add(a, b, "#f4f4f4", "", False)
            else:
                label = f"shared by {count} instances"
                segments.add(a, b, SHARED_COLORS.get(count, "#444444"), label, False)
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
            plot.getViewBox().sceneBoundingRect().contains(pos)
            for plot in [self._master, *self._plots.values()]
        )
        for line in self._crosshairs:
            line.setVisible(inside)
            line.setPos(x)
        if not inside or stamp is None:
            self._status.setText(HINT)
            return
        parts = [f"{stamp:%Y-%m-%d %H:%M:%S}"]
        offset = self.info.transient_offset
        for position, frame in enumerate(self.frames):
            title = instance_title(self.rows.iloc[position])
            if stamp < frame.index[0] or stamp > frame.index[-1]:
                parts.append(f"{title}: outside")
                continue
            i = min(int(frame.index.searchsorted(stamp, side="right")) - 1, len(frame) - 1)
            klass = frame["class"].iloc[i] if "class" in frame.columns else np.nan
            state = frame["state"].iloc[i] if "state" in frame.columns else np.nan
            klass = float("nan") if pd.isna(klass) else float(klass)
            state = float("nan") if pd.isna(state) else float(state)
            values = []
            for feature in self.selected_features():
                if feature in frame.columns:
                    value = frame[feature].iloc[i]
                    values.append(f"{feature} = {'—' if pd.isna(value) else f'{value:.4g}'}")
            reading = f" · {', '.join(values)}" if values else ""
            parts.append(
                f"{title}: {label_name(klass, self.info.fault_names, offset)} / {state_name(state)}{reading}"
            )
        self._status.setText("  ·  ".join(parts))
