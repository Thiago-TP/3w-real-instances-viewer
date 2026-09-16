"""The faults page: every real instance of one fault, from every well, side by side or over one another.

Rabelo's figures 2.5 and 2.6 put two instances of the same fault side by side
to make a point: the same event, on two wells, has a different magnitude, a
different time to install itself and a different baseline. This page makes
that comparison for any fault and every well at once, on a time axis that
starts where the event begins in each instance, so that the shapes line up
whatever the clock said.

Two layouts, chosen in the *Layout* box. **Small multiples** give every
instance a small plot of its own, laid out in a grid, each with its own value
axis and its label periods shaded behind the trace: two dozen shapes can be
read at a glance, and the eye compares them one against the next. **Overlaid**
draws them all on one set of axes, which says how far apart the levels are and
little else once there are more than a handful — the reason the grid is the
default.

Each series can be scaled to its own level (a z-score over the instance, as
Rabelo's pipeline does) so that shapes can be compared where the readings
themselves cannot, and the window around the onset can be narrowed to the hours
that matter.

The instances of a fault are listed on the right with the moment each can be
aligned on, read from the label runs the catalogue keeps, so the list costs
nothing; only the instances ticked are read from disk and drawn. Beyond a couple
of dozen the page starts with the earliest ones ticked and leaves the rest to
the user.
"""

from dataclasses import dataclass, field
from math import ceil

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QCursor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from overlap_viewer import theme
from overlap_viewer.availability import ABSENT, Availability
from overlap_viewer.config import (
    FAULT_SIGNATURES,
    MAX_OVERLAID_INSTANCES,
    MAX_SMALL_MULTIPLES,
    REACH_LABELS,
    plausible_range,
)
from overlap_viewer.dataset import DatasetInfo, WellData, well_label
from overlap_viewer.faults import (
    ALIGNMENT_AXES,
    ALIGNMENT_NAMES,
    ALIGNMENTS,
    onset_from_runs,
    plausible_extent,
    relative_hours,
    window_mask,
    zscore,
)
from overlap_viewer.instance_window import AXIS_WIDTH, PANEL_WIDTH, PlotStack
from overlap_viewer.items import AnchoredText, HeaderLabel, ScrollFriendlyViewBox, SegmentsItem
from overlap_viewer.labels import (
    Segment,
    column_as_float,
    label_fault,
    label_kind,
    label_name,
    padded_range,
    segments_from_json,
    state_name,
)
from overlap_viewer.loading import FrameCache
from overlap_viewer.palette import background_color, bar_color, tint, unknown_background
from overlap_viewer.spectral import Histogram, Spectrum, format_period, histogram, prepare, welch
from overlap_viewer.spectral_items import (
    TransformControls,
    add_center_lines,
    add_spectrum_curve,
    add_stacked_bars,
    add_step_outline,
    caption_for,
    power_axis,
    power_label,
    set_log_period_axis,
    shade_unresolved,
    spectrum_grid,
    spectrum_xy,
)

HINT = (
    "Every plot is one real instance of the fault, in the color of its well, on a time axis that "
    "starts where the event begins in it · hover a trace to name it and read it · tick features "
    "on the left and instances on the right · Ctrl + wheel to zoom, the wheel scrolls · F1 for help"
)

LAYOUTS = ("Small multiples", "Overlaid")
VALUE_AXES = ("Per instance", "Shared")
# What every plot shows of the stretch selected: the readings against time, their
# distribution, or their spectrum.
DOMAINS = ("time", "distribution", "spectrum")
DOMAIN_NAMES = {"time": "Time series", "distribution": "Distribution", "spectrum": "Spectrum"}
DOMAIN_TIP = (
    "What every plot shows of the stretch the hours before and after the onset select. Time "
    "series: the readings against the hours from the onset. Distribution: a histogram of the "
    "readings, as a share of the instance's samples so that instances of different length "
    "compare, stacked by label period in the class colors in the grid, outlined in the color of "
    "the well when overlaid. Spectrum: the power spectral density against the period, both "
    "logarithmic, the mean and the trend removed first — overlaid, the spectra of two dozen "
    "instances read together where their traces did not, since the question is whether their "
    "peaks line up."
)
HIST_KINDS = ("normal", "transient", "steady", "unknown")

PLOT_PX = 230  # height of one overlaid feature plot
SMALL_PLOT_PX = 132  # height of one small multiple
SMALL_AXIS_WIDTH = 48  # every small plot keeps this width for its left axis, so the grid aligns
SMALL_AXIS_PX = 26  # the time axis under the last row of a grid section
SECTION_PX = 22  # the heading above one feature's grid
LIST_WIDTH = 380  # the instances panel: room for a title, the mark and an onset
CHIP_PX = 12  # the square of a well's color before an instance
HOVER_PX = 10  # a line closer than this to the pointer, in pixels, is the one named
FADE_ALPHA = 70  # the other lines while one is named


@dataclass
class Series:
    """One instance as drawn: which it is, its frame, where it is aligned, its hours and color."""

    well: int
    position: int  # in the well's instance table
    title: str
    frame: pd.DataFrame
    onset: pd.Timestamp
    hours: np.ndarray
    color: str
    runs: list[Segment] = field(default_factory=list)  # its label runs, for the shading

    @property
    def label(self) -> str:
        """What a small plot writes in its corner: the well and the day it was aligned on.

        Short enough to sit inside a plot a seventh of a window wide; the list
        on the right carries the filename and the hour.
        """
        return f"{well_label(self.well)} · {self.onset:%Y-%m-%d}"


class FaultsPage(QWidget):
    """The page: the fault and its alignment in the toolbar, features left, plots center, instances right.

    Signals
    -------
    status(str)
        What the main window's status bar should say: the instance under the
        pointer and its reading, or the page's hint.
    summary_changed()
        The one-line count of what is on show has changed.
    """

    status = Signal(str)
    summary_changed = Signal()

    def hint(self) -> str:
        """What the status bar says when the pointer is over nothing in particular."""
        return HINT

    def __init__(self, info: DatasetInfo, frames: FrameCache, parent=None):
        super().__init__(parent)
        self.info = info
        self._frames = frames
        self._catalogue: pd.DataFrame | None = None
        self._wells: dict[int, WellData] = {}
        self._availability: Availability | None = None
        self._instances: list[
            dict
        ] = []  # per instance of the fault: well, position, title, onset, ...
        self._items: list[QListWidgetItem] = []
        self._checks: dict[str, QCheckBox] = {}
        self._series: list[Series] = []
        self._plots: list[pg.PlotItem] = []
        self._curves: dict[
            int, list[pg.PlotDataItem]
        ] = {}  # series index -> its curve in each plot
        self._plot_series: list[
            list[tuple[int, np.ndarray, np.ndarray]]
        ] = []  # per plot: (series, x, y)
        self._spectra_by_plot: dict[tuple[int, int], Spectrum] = {}  # (plot, series) -> spectrum
        self._hover = -1
        self._x_range: tuple[float, float] | None = None
        self._building = False
        # The alignment the user asked for last, kept across faults: a fault
        # without a transient falls back to what it allows, and the next fault
        # with one goes back to the onset of the transient.
        self._preferred = "transient"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._build_toolbar())
        layout.addWidget(self._build_parameter_bar())

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(8, 0, 8, 4)
        body_layout.setSpacing(8)
        self._feature_panel = self._build_feature_panel()
        body_layout.addWidget(self._feature_panel)
        self._stack = PlotStack()
        self._stack.ci.layout.setVerticalSpacing(4)
        self._stack.ci.setContentsMargins(0, 0, 0, 0)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setWidget(self._stack)
        body_layout.addWidget(self._scroll, 1)
        self._instance_panel = self._build_instance_panel()
        body_layout.addWidget(self._instance_panel)
        layout.addWidget(body, 1)
        self._stack.scene().sigMouseMoved.connect(self._on_mouse_moved)
        self._restyle()

    # -- construction

    def _build_toolbar(self) -> QToolBar:
        bar = QToolBar("Faults")
        bar.setMovable(False)
        bar.addWidget(QLabel(" Fault "))
        self._fault = QComboBox()
        self._fault.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._fault.setToolTip("The fault whose real instances are drawn over one another")
        self._fault.currentIndexChanged.connect(self._on_fault_changed)
        bar.addWidget(self._fault)

        bar.addSeparator()
        bar.addWidget(QLabel(" Align at "))
        self._align = QComboBox()
        for key in ALIGNMENTS:
            self._align.addItem(ALIGNMENT_NAMES[key], key)
        self._align.setToolTip(
            "Where the time axis of every instance starts: the first sample labeled with the "
            "transient of the fault, the first labeled with its steady state, or the first sample "
            "of the recording. An instance whose labels never reach the state chosen cannot be "
            "aligned on it and is left out, greyed in the list."
        )
        self._align.currentIndexChanged.connect(self._on_alignment_changed)
        bar.addWidget(self._align)

        bar.addSeparator()
        bar.addWidget(QLabel(" Domain "))
        self._domain = QComboBox()
        for key in DOMAINS:
            self._domain.addItem(DOMAIN_NAMES[key], key)
        self._domain.setToolTip(DOMAIN_TIP)
        self._domain.currentIndexChanged.connect(self._on_domain_changed)
        bar.addWidget(self._domain)

        bar.addSeparator()
        bar.addWidget(QLabel(" Layout "))
        self._layout_box = QComboBox()
        self._layout_box.addItems(list(LAYOUTS))
        self._layout_box.setToolTip(
            "Small multiples give every instance a plot of its own, laid out in a grid, so that "
            "two dozen shapes can be read one against the next; overlaid draws them all on one "
            "set of axes, which says how far apart their levels are and little else once there "
            "are more than a handful."
        )
        self._layout_box.currentIndexChanged.connect(self._on_layout_changed)
        bar.addWidget(self._layout_box)
        self._grid_only: list = []
        self._grid_only.append(bar.addWidget(QLabel(" Columns ")))
        self._columns = QSpinBox()
        self._columns.setRange(1, 8)
        self._columns.setValue(3)
        self._columns.setToolTip("Small plots per row of the grid")
        self._columns.valueChanged.connect(self._replot)
        self._grid_only.append(bar.addWidget(self._columns))
        self._grid_only.append(bar.addWidget(QLabel(" Axis ")))
        self._value_axis = QComboBox()
        self._value_axis.addItems(list(VALUE_AXES))
        self._value_axis.setToolTip(
            "Per instance, every small plot scales to its own readings, so that every shape is "
            "legible whatever the level of its well; shared, they all take the same value axis, "
            "so that the plots say how far apart those levels are — which is the very thing that "
            "flattens most of them."
        )
        self._value_axis.currentIndexChanged.connect(self._replot)
        self._grid_only.append(bar.addWidget(self._value_axis))

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bar.addWidget(spacer)
        self._note = QLabel()
        bar.addWidget(self._note)
        bar.addSeparator()
        self._show_features = QAction("Features", self)
        self._show_features.setCheckable(True)
        self._show_features.setChecked(True)
        self._show_features.setToolTip(
            "Show or hide the list of features on the left, to give the plots its width"
        )
        self._show_features.toggled.connect(self._on_features_toggled)
        bar.addAction(self._show_features)
        self._show_instances = QAction("Instances", self)
        self._show_instances.setCheckable(True)
        self._show_instances.setChecked(True)
        self._show_instances.setToolTip(
            "Show or hide the list of instances on the right, to give the plots its width"
        )
        self._show_instances.toggled.connect(self._on_instances_toggled)
        bar.addAction(self._show_instances)
        return bar

    def _build_parameter_bar(self) -> QToolBar:
        """The second row: the stretch around the onset, the normalization, the parameters of the transforms.

        On one row with the rest these fell behind the toolbar's overflow
        chevron as soon as the page was narrower than a screen; the first row
        now holds what chooses the question, this one what tunes the answer.
        """
        bar = QToolBar("Parameters")
        bar.setMovable(False)
        bar.addWidget(QLabel(" Show "))
        self._before = QDoubleSpinBox()
        self._before.setRange(0.0, 999.0)
        self._before.setDecimals(1)
        self._before.setSingleStep(0.5)
        self._before.setSuffix(" h before")
        self._before.setSpecialValueText("all before")
        self._before.setToolTip(
            "Hours before the onset to draw; at zero, everything recorded before it"
        )
        self._before.valueChanged.connect(self._replot)
        bar.addWidget(self._before)
        self._after = QDoubleSpinBox()
        self._after.setRange(0.0, 999.0)
        self._after.setDecimals(1)
        self._after.setSingleStep(0.5)
        self._after.setSuffix(" h after")
        self._after.setSpecialValueText("all after")
        self._after.setToolTip(
            "Hours after the onset to draw; at zero, everything recorded after it"
        )
        self._after.valueChanged.connect(self._replot)
        bar.addWidget(self._after)

        bar.addSeparator()
        self._normalize = QCheckBox("Normalize per instance")
        self._normalize.setToolTip(
            "Scale every series to its own level: each reading as standard deviations from the "
            "mean of that sensor over the whole instance, which is how Rabelo's pipeline "
            "normalizes an instance. Wells run at different levels, and the shape of the change "
            "is what the instances have in common."
        )
        self._normalize.toggled.connect(self._replot)
        bar.addWidget(self._normalize)

        self._parameter_separator = bar.addSeparator()
        self._controls = TransformControls()
        self._controls.changed.connect(self._replot)
        bar.addWidget(self._controls)
        self._parameter_bar = bar
        self._sync_layout_controls()
        return bar

    def _on_instances_toggled(self, shown: bool) -> None:
        self._instance_panel.setVisible(shown)

    def _on_features_toggled(self, shown: bool) -> None:
        self._feature_panel.setVisible(shown)

    def _sync_layout_controls(self) -> None:
        """Show the controls only the grid, or only the domain chosen, has a use for."""
        for action in self._grid_only:
            action.setVisible(self.small_multiples)
        self._controls.show_spectral(self.domain == "spectrum")
        self._controls.show_bins(self.domain == "distribution")
        self._parameter_separator.setVisible(self.domain != "time")

    def _on_layout_changed(self, *args) -> None:
        self._sync_layout_controls()
        self._replot(keep_range=False)

    def _on_domain_changed(self, *args) -> None:
        self._sync_layout_controls()
        self._replot(keep_range=False)

    @property
    def domain(self) -> str:
        return str(self._domain.currentData() or "time")

    def set_domain(self, domain: str) -> None:
        """Show every plot in one domain, as the box would."""
        if domain not in DOMAINS:
            raise ValueError(f"unknown domain {domain!r}; expected one of {DOMAINS}")
        self._domain.setCurrentIndex(DOMAINS.index(domain))

    @property
    def small_multiples(self) -> bool:
        return self._layout_box.currentIndex() == 0

    @property
    def per_instance_axis(self) -> bool:
        """Whether every small plot scales to its own readings."""
        return self._value_axis.currentIndex() == 0

    def _build_feature_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(PANEL_WIDTH)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("<b>Features</b>"))
        buttons = QVBoxLayout()
        buttons.setSpacing(2)
        clear = QPushButton("Clear")
        clear.clicked.connect(lambda: self._set_all_features(False))
        every = QPushButton("All recorded")
        every.clicked.connect(lambda: self._set_all_features(True))
        buttons.addWidget(clear)
        buttons.addWidget(every)
        layout.addLayout(buttons)
        self._signature = QCheckBox("Signature")
        self._signature.toggled.connect(self._apply_signature)
        layout.addWidget(self._signature)
        self._feature_scroll = QScrollArea()
        self._feature_scroll.setWidgetResizable(True)
        self._feature_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._feature_box = QWidget()
        self._feature_layout = QVBoxLayout(self._feature_box)
        self._feature_layout.setContentsMargins(0, 0, 0, 0)
        self._feature_layout.setSpacing(2)
        self._feature_scroll.setWidget(self._feature_box)
        layout.addWidget(self._feature_scroll, 1)
        self._feature_note = QLabel(
            "Greyed-out features were recorded by no instance of the fault."
        )
        self._feature_note.setWordWrap(True)
        layout.addWidget(self._feature_note)
        return panel

    def _build_instance_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(LIST_WIDTH)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("<b>Instances</b>"))
        buttons = QHBoxLayout()
        buttons.setSpacing(2)
        every = QPushButton("All")
        every.clicked.connect(lambda: self._set_all_instances(True))
        none = QPushButton("None")
        none.clicked.connect(lambda: self._set_all_instances(False))
        buttons.addWidget(every)
        buttons.addWidget(none)
        layout.addLayout(buttons)
        self._list = QListWidget()
        self._list.setMouseTracking(True)
        self._list.itemChanged.connect(self._on_item_changed)
        self._list.itemEntered.connect(self._on_item_entered)
        self._list.viewportEntered.connect(lambda: self._highlight(-1))
        layout.addWidget(self._list, 1)
        self._instance_note = QLabel()
        self._instance_note.setWordWrap(True)
        layout.addWidget(self._instance_note)
        return panel

    # -- appearance

    def _restyle(self) -> None:
        colors = theme.current()
        self._stack.setBackground(colors.plot_background)
        for note in (self._feature_note, self._instance_note, self._note):
            note.setStyleSheet(f"color: {colors.muted}; font-size: 8pt;")

    def apply_theme(self) -> None:
        """Take the colors of the theme now in force; ``set_catalogue`` redraws the plots after it."""
        self._restyle()

    # -- data

    def set_catalogue(self, catalogue: pd.DataFrame, wells: list[WellData]) -> None:
        """Take a new catalogue and its wells; the fault chosen stays chosen where it still exists."""
        self._catalogue = catalogue
        self._wells = {well.well: well for well in wells}
        self._availability = Availability.from_wells(wells, self.info)
        wanted = self._fault.currentData()
        self._fault.blockSignals(True)
        self._fault.clear()
        counts = catalogue["fault_class"].value_counts()
        for fault in sorted(counts.index):
            # The name alone: how many instances on how many wells is what the
            # status bar says about the fault chosen, and the box is narrow enough
            # to leave the toolbar's other controls on screen.
            self._fault.addItem(f"{fault} · {self.info.fault_name(int(fault))}", int(fault))
        index = self._fault.findData(wanted)
        self._fault.setCurrentIndex(max(index, 0))
        self._fault.blockSignals(False)
        self._on_fault_changed()

    @property
    def fault(self) -> int | None:
        data = self._fault.currentData()
        return None if data is None else int(data)

    @property
    def alignment(self) -> str:
        return str(self._align.currentData())

    def _allowed_alignments(self, fault: int) -> list[str]:
        allowed = ["start"]
        if fault != 0:
            allowed.insert(0, "steady")
            if self.info.has_transient(fault):
                allowed.insert(0, "transient")
        return allowed

    def _on_fault_changed(self, *args) -> None:
        """A new fault: offer the alignments it allows, list its instances, offer its features."""
        fault = self.fault
        if fault is None:
            return
        allowed = self._allowed_alignments(fault)
        model = self._align.model()
        self._align.blockSignals(True)
        for i, key in enumerate(ALIGNMENTS):
            item = model.item(i)
            enabled = key in allowed
            item.setFlags(
                item.flags() | Qt.ItemFlag.ItemIsEnabled
                if enabled
                else item.flags() & ~Qt.ItemFlag.ItemIsEnabled
            )
        wanted = self._preferred if self._preferred in allowed else allowed[0]
        if self.alignment != wanted:
            self._align.setCurrentIndex(ALIGNMENTS.index(wanted))
        self._align.blockSignals(False)
        self._rebuild_instances()
        self._rebuild_features()
        self._replot(keep_range=False)

    def _on_alignment_changed(self, *args) -> None:
        self._preferred = self.alignment
        self._rebuild_instances()
        self._replot(keep_range=False)

    def _instances_of(self, fault: int) -> list[dict]:
        """Every real instance of the fault, by well and start, with the moment it aligns on."""
        found = []
        for well in sorted(self._wells):
            data = self._wells[well]
            rows = data.rows
            for position in np.flatnonzero(rows["fault_class"].to_numpy() == fault).tolist():
                row = rows.iloc[position]
                runs = (
                    segments_from_json(str(row["class_runs"]))
                    if "class_runs" in rows.columns
                    else []
                )
                found.append(
                    {
                        "well": well,
                        "position": position,
                        "title": str(row["file"]).rsplit(".", 1)[0]
                        if "file" in rows.columns
                        else str(row["title"]),
                        "reach": str(row["reach"]),
                        "start": pd.Timestamp(row["start"]),
                        "end": pd.Timestamp(row["end"]),
                        "hours": float(row["hours"]),
                        "onset": onset_from_runs(
                            runs, fault, self.info.transient_offset, self.alignment
                        ),
                        "runs": runs,
                        "implausible": self._availability is not None
                        and self._availability.implausible_any(
                            [self._availability.index_of(well, position)]
                        ),
                    }
                )
        return found

    def _well_colors(self, wells: list[int]) -> dict[int, str]:
        series = theme.current().series
        return {well: series[k % len(series)] for k, well in enumerate(sorted(set(wells)))}

    def _rebuild_instances(self) -> None:
        """List the instances of the fault, the earliest ticked, those without an onset greyed out."""
        fault = self.fault
        previously = {
            (entry["well"], entry["position"])
            for entry, item in zip(self._instances, self._items)
            if item.checkState() == Qt.CheckState.Checked
        }
        fresh = not self._instances or self._instances[0].get("fault") != fault
        self._instances = self._instances_of(fault)
        for entry in self._instances:
            entry["fault"] = fault
        colors = self._well_colors([entry["well"] for entry in self._instances])
        self._building = True
        self._list.clear()
        self._items = []
        ticked = 0
        for entry in self._instances:
            entry["color"] = colors[entry["well"]]
            item = QListWidgetItem(self._item_text(entry))
            item.setIcon(self._chip(entry["color"]))
            item.setToolTip(self._item_tooltip(entry))
            aligned = entry["onset"] is not None
            flags = Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable
            if aligned:
                flags |= Qt.ItemFlag.ItemIsEnabled
            item.setFlags(flags)
            if fresh:
                check = aligned and ticked < MAX_OVERLAID_INSTANCES
            else:
                check = aligned and (entry["well"], entry["position"]) in previously
            item.setCheckState(Qt.CheckState.Checked if check else Qt.CheckState.Unchecked)
            ticked += check
            self._list.addItem(item)
            self._items.append(item)
        self._building = False
        self._refresh_instance_note()

    def _item_text(self, entry: dict) -> str:
        onset = entry["onset"]
        when = f"{onset:%Y-%m-%d %H:%M}" if onset is not None else "no onset in the labels"
        mark = " ⚠" if entry["implausible"] else ""
        return f"{entry['title']}{mark} · {when}"

    def _item_tooltip(self, entry: dict) -> str:
        fault = self.fault
        reach = "" if fault == 0 else f" · {REACH_LABELS[entry['reach']]}"
        text = (
            f"{well_label(entry['well'])} · {self.info.fault_name(fault)}{reach}\n"
            f"{entry['start']:%Y-%m-%d %H:%M:%S} → {entry['end']:%Y-%m-%d %H:%M:%S} "
            f"({entry['hours']:.1f} h)"
        )
        if entry["onset"] is None:
            text += (
                f"\nThe labels never reach the {ALIGNMENT_NAMES[self.alignment].lower()}, so "
                "this instance cannot be aligned on it."
            )
        if entry["implausible"]:
            text += "\n⚠ A sensor reads outside its plausible range in this instance."
        return text

    @staticmethod
    def _chip(color: str) -> QIcon:
        pixmap = QPixmap(CHIP_PX, CHIP_PX)
        pixmap.fill(QColor(color))
        return QIcon(pixmap)

    def _rebuild_features(self) -> None:
        """Offer every sensor, greying those no instance of the fault recorded, the signature ticked."""
        fault = self.fault
        availability = self._availability
        for check in self._checks.values():
            self._feature_layout.removeWidget(check)
            check.deleteLater()
        self._checks = {}
        while self._feature_layout.count():
            item = self._feature_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        rows = np.flatnonzero(availability.bars["fault_class"].to_numpy() == fault)
        n = len(rows)
        recorded = {}
        for j, name in enumerate(availability.sensors):
            recorded[name] = int((availability.state[rows, j] != ABSENT).sum()) if n else 0
        signature = [name for name in FAULT_SIGNATURES.get(fault, ()) if recorded.get(name, 0) > 0]
        # With no published signature to tick, the sensor the most instances of
        # the fault recorded: the first in the alphabet is as likely as not to
        # be one none of them has, which would open the page on empty plots.
        best = sorted(recorded, key=lambda name: (-recorded[name], name))
        default = set(signature) or {next((name for name in best if recorded[name] > 0), None)}
        for name in sorted(recorded):
            unit = self.info.unit(name)
            check = QCheckBox(f"{name} [{unit}]" if unit else name)
            description = self.info.sensor_descriptions.get(name, "")
            count = f"recorded in {recorded[name]} of {n} instances of the fault"
            check.setToolTip(f"{description}\n{count}" if description else count)
            check.setEnabled(recorded[name] > 0)
            check.setChecked(name in default and recorded[name] > 0)
            check.toggled.connect(self._on_feature_toggled)
            self._checks[name] = check
            self._feature_layout.addWidget(check)
        self._feature_layout.addStretch(1)
        self._signature.blockSignals(True)
        self._signature.setEnabled(bool(signature))
        self._signature.setChecked(bool(signature))
        if signature:
            self._signature.setToolTip(
                f"Signature of {self.info.fault_name(fault)}: {', '.join(FAULT_SIGNATURES[fault])}. "
                "Ticks exactly these variables."
            )
        else:
            self._signature.setToolTip(
                "The 3W paper publishes a signature only for the events it illustrates: Normal "
                "Operation, Spurious Closure of DHSV, Severe Slugging, Quick Restriction in PCK and "
                "Hydrate in Production Line."
            )
        self._signature.blockSignals(False)

    def selected_features(self) -> list[str]:
        return [name for name, check in self._checks.items() if check.isChecked()]

    def _signature_features(self) -> list[str]:
        fault = self.fault
        return [
            name
            for name in FAULT_SIGNATURES.get(fault, ())
            if name in self._checks and self._checks[name].isEnabled()
        ]

    def _apply_signature(self, checked: bool) -> None:
        wanted = set(self._signature_features()) if checked else set()
        for name, check in self._checks.items():
            check.blockSignals(True)
            check.setChecked(name in wanted and check.isEnabled())
            check.blockSignals(False)
        self._replot()

    def _on_feature_toggled(self, *args) -> None:
        signature = self._signature_features()
        self._signature.blockSignals(True)
        self._signature.setChecked(
            bool(signature) and set(self.selected_features()) == set(signature)
        )
        self._signature.blockSignals(False)
        self._replot()

    def _set_all_features(self, checked: bool) -> None:
        for check in self._checks.values():
            check.blockSignals(True)
            check.setChecked(checked and check.isEnabled())
            check.blockSignals(False)
        self._on_feature_toggled()

    def _set_all_instances(self, checked: bool) -> None:
        self._building = True
        for item in self._items:
            if item.flags() & Qt.ItemFlag.ItemIsEnabled:
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self._building = False
        self._replot()

    def _on_item_changed(self, item) -> None:
        if not self._building:
            self._replot()

    def _checked_instances(self) -> list[dict]:
        return [
            entry
            for entry, item in zip(self._instances, self._items)
            if item.checkState() == Qt.CheckState.Checked and entry["onset"] is not None
        ]

    def _refresh_instance_note(self) -> None:
        n = len(self._instances)
        aligned = sum(1 for entry in self._instances if entry["onset"] is not None)
        drawn = len(self._checked_instances())
        parts = [f"{drawn} of {n} instances drawn"]
        if aligned < n:
            parts.append(
                f"{n - aligned} greyed out: their labels never reach the "
                f"{ALIGNMENT_NAMES[self.alignment].lower()}"
            )
        if n > MAX_OVERLAID_INSTANCES:
            parts.append(f"the earliest {MAX_OVERLAID_INSTANCES} were ticked to start with")
        if self.small_multiples and drawn > MAX_SMALL_MULTIPLES:
            parts.append(f"the grid draws the first {MAX_SMALL_MULTIPLES} of them")
        self._instance_note.setText(" · ".join(parts) + ".")
        self._note.setText(parts[0])

    # -- drawing

    def _replot(self, *args, keep_range: bool = True) -> None:
        """Read the ticked instances and lay the plots out again.

        The stretch of time on screen is kept, so that ticking a feature or an
        instance does not throw away a zoom; a new fault, a new alignment or a
        new layout is a new question, and starts from the whole of it.
        """
        if self._availability is None or self.fault is None:
            return
        self._refresh_instance_note()
        if not keep_range:
            self._x_range = None
        elif self._plots:
            self._x_range = tuple(self._plots[0].getViewBox().viewRange()[0])
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            self._series = self._load_series()
            self._lay_out()
        finally:
            QApplication.restoreOverrideCursor()
        self.summary_changed.emit()

    def _load_series(self) -> list[Series]:
        series = []
        for entry in self._checked_instances():
            data = self._wells[entry["well"]]
            frame = self._frames.get(data.rows["path"].iloc[entry["position"]])
            hours = relative_hours(frame.index, entry["onset"])
            series.append(
                Series(
                    entry["well"],
                    entry["position"],
                    entry["title"],
                    frame,
                    entry["onset"],
                    hours,
                    entry["color"],
                    entry.get("runs", []),
                )
            )
        return series

    def drawn_series(self) -> list[Series]:
        """The instances a layout actually draws: all of them, or as many as a grid can hold."""
        if self.small_multiples:
            return self._series[:MAX_SMALL_MULTIPLES]
        return self._series

    # -- one series, one feature

    def _xy(
        self, series: Series, feature: str, normalize: bool, before: float, after: float, bounds
    ) -> tuple[np.ndarray, np.ndarray] | None:
        """The hours and the readings of one series for one feature, inside the window.

        ``None`` when this instance says nothing about the feature, so that a
        plot is never built for a blank.
        """
        frame = series.frame
        if feature not in frame.columns:
            return None
        y = column_as_float(frame, feature)
        if not (~np.isnan(y)).any():
            return None
        if normalize:
            # Scaled over the plausible readings only, as the pipelines mask the
            # garbage before they normalize: one absurd level would otherwise
            # squash every genuine reading into zero.
            y = zscore(np.where((y >= bounds[0]) & (y <= bounds[1]), y, np.nan))
            if not (~np.isnan(y)).any():
                return None
        mask = window_mask(series.hours, before, after)
        x, y = series.hours[mask], y[mask]
        return (x, y) if len(x) else None

    def _window_values(
        self, series: Series, feature: str, normalize: bool, before: float, after: float, bounds
    ) -> tuple[np.ndarray, np.ndarray] | None:
        """The readings of one series inside the window, missing values kept, with the label kind of each sample.

        What the distribution and the spectrum are computed from: the same
        stretch the time series draws, in the same order, so that "2 h after
        the onset" means the same in every domain.
        """
        got = self._xy(series, feature, normalize, before, after, bounds)
        if got is None:
            return None
        _x, y = got
        mask = window_mask(series.hours, before, after)
        labels = column_as_float(series.frame, "class")[mask]
        return y, self._kind_codes(labels)

    def _kind_codes(self, labels: np.ndarray) -> np.ndarray:
        """``label_kind`` of every sample at once, as positions in ``HIST_KINDS``."""
        offset = self.info.transient_offset
        transient = (labels > offset) & (labels < 2 * offset)
        return np.select(
            [np.isnan(labels), labels == 0, transient],
            [
                HIST_KINDS.index("unknown"),
                HIST_KINDS.index("normal"),
                HIST_KINDS.index("transient"),
            ],
            default=HIST_KINDS.index("steady"),
        ).astype(np.int64)

    # -- the pieces both layouts build from

    def _new_plot(self, row: int, col: int) -> pg.PlotItem:
        """A plot in the stack; in the time domain, with the dashed vertical that marks the onset at zero."""
        plot = self._stack.addPlot(row=row, col=col, viewBox=ScrollFriendlyViewBox())
        plot.hideButtons()
        plot.getViewBox().disableAutoRange()
        if self.domain == "time":
            onset_line = pg.InfiniteLine(
                pos=0.0,
                angle=90,
                movable=False,
                pen=pg.mkPen(theme.current().gap_line, width=1, style=Qt.PenStyle.DashLine),
            )
            onset_line.setZValue(-5)
            plot.addItem(onset_line, ignoreBounds=True)
        return plot

    def _bottom_label(self, feature: str, normalize: bool) -> str:
        """What the horizontal axis of a plot means in the domain chosen."""
        if self.domain == "time":
            return ALIGNMENT_AXES[self.alignment]
        if self.domain == "distribution":
            unit = "z-score" if normalize else self.info.unit(feature)
            return f"{feature} [{unit}]" if unit else feature
        return "period"

    def _prepare_left_axis(
        self,
        plot: pg.PlotItem,
        feature: str,
        normalize: bool,
        width: int,
        values: bool,
        label: bool,
    ) -> None:
        """The left axis in the domain chosen: readings, a share of samples, or a power."""
        if self.domain == "time":
            self._prepare_axis(plot, feature, normalize, width, values, label)
            return
        axis = plot.getAxis("left")
        axis.setWidth(width)
        axis.enableAutoSIPrefix(False)
        if self.domain == "distribution":
            if label:
                plot.setLabel("left", "% of samples")
        else:
            unit = "" if normalize else self.info.unit(feature)
            power_axis(plot, "left", power_label(unit) if label else "")
        if not values:
            axis.setStyle(showValues=False)

    def _prepare_bottom_axis(self, plot: pg.PlotItem, feature: str, normalize: bool) -> None:
        """The bottom axis in the domain chosen; a period axis for the spectrum."""
        if self.domain == "spectrum":
            set_log_period_axis(plot, "bottom", "period")
        else:
            plot.setLabel("bottom", self._bottom_label(feature, normalize))

    # -- one series, one feature, off the time axis

    def _histogram_of(
        self, values: np.ndarray, codes: np.ndarray, edges: np.ndarray | None, bounds, normalize
    ):
        """The histogram of one series, stacked by label kind."""
        return histogram(
            values,
            codes,
            self._controls.params().bins,
            None if normalize else bounds,
            edges=edges,
            keys=list(HIST_KINDS),
        )

    def _spectrum_of(self, values: np.ndarray, bounds, normalize) -> Spectrum | None:
        prepared = prepare(values, None if normalize else bounds)
        if prepared is None:
            return None
        return welch(prepared, self._controls.params())

    def _kind_brush(self, kind: str):
        """The fill of one stack of a histogram: the class color of the label period, as the bands carry it."""
        if kind == "unknown":
            return pg.mkBrush(tint(unknown_background(), 0.7))
        return pg.mkBrush(bar_color(self.fault, kind))

    def _prepare_axis(
        self,
        plot: pg.PlotItem,
        feature: str,
        normalize: bool,
        width: int,
        values: bool,
        label: bool,
    ) -> None:
        """Give a plot its left axis: the same width everywhere, so a grid of them lines up."""
        axis = plot.getAxis("left")
        axis.setWidth(width)
        unit = self.info.unit(feature)
        prefixed = unit == "Pa" and not normalize
        axis.enableAutoSIPrefix(prefixed)
        if label:
            if normalize:
                plot.setLabel("left", f"{feature} (z-score)")
            elif prefixed:
                plot.setLabel("left", feature, units=unit)
            else:
                plot.setLabel("left", f"{feature} [{unit}]" if unit else feature)
        if not values:
            axis.setStyle(showValues=False)

    def _add_curve(self, plot: pg.PlotItem, series: Series, x, y) -> pg.PlotDataItem:
        curve = pg.PlotDataItem(x, y, pen=pg.mkPen(series.color, width=1.2), connect="finite")
        plot.addItem(curve)
        curve.setDownsampling(auto=True, method="peak")
        curve.setClipToView(True)
        return curve

    def _add_shading(self, plot: pg.PlotItem, series: Series) -> None:
        """Shade the label periods of one instance behind its trace, as the instance window does.

        The runs come from the catalogue, so this costs no reading; with them a
        small plot says not only what the readings did but how long the experts
        left the instance in normal operation, in the transient and in the
        steady state, which is the very thing that differs from well to well.

        A stretch nobody labeled is hatched rather than merely grey, as it is
        everywhere else in the viewer: two of the fault hues are themselves
        grey, and a texture says *nothing is known here* where one more shade
        would just read as one more class.
        """
        if not series.runs:
            return
        offset, fault = self.info.transient_offset, self.fault
        x0, x1, fills, unknown = [], [], [], []
        for run in series.runs:
            start, end = relative_hours([run.start, run.end], series.onset)
            kind = label_kind(run.value, offset)
            if kind == "unknown":
                fill = tint(unknown_background(), 0.7)
            else:
                hue = label_fault(run.value, offset)
                fill = background_color(fault if hue is None else hue, kind)
            x0.append(float(start))
            x1.append(float(end))
            fills.append(fill)
            unknown.append(kind == "unknown")
        shading = SegmentsItem(z=-10)
        shading.set_segments(x0, x1, fills, hatched=unknown)
        plot.addItem(shading, ignoreBounds=True)

    # -- laying out

    def _lay_out(self) -> None:
        stack = self._stack
        stack.clear()
        self._plots = []
        self._curves = {i: [] for i in range(len(self._series))}
        self._plot_series = []
        self._spectra_by_plot = {}
        self._hover = -1
        features = self.selected_features()
        if not features:
            label = stack.addLabel(
                "Tick a feature on the left to draw it.",
                row=0,
                col=0,
                color=theme.current().faint,
            )
            label.setMinimumHeight(60)
            stack.setMinimumHeight(80)
        else:
            height = (
                self._lay_out_grid(features)
                if self.small_multiples
                else self._lay_out_overlay(features)
            )
            stack.setMinimumHeight(max(height, self._stack_height_floor(), 80))
        stack.resizeEvent(None)
        self._apply_x_range()

    def _stack_height_floor(self) -> int:
        """The layout's own idea of its minimum height, as a floor under the estimate above.

        The estimate sums a fixed height per row and a flat few pixels per
        section for the gaps between them, which undercounts a grid with many
        rows — each real gap between two rows of a pyqtgraph layout costs its
        own spacing, and a grid of, say, eight rows has seven of them per
        feature column, not the one or two pixels the flat fudge budgets. The
        layout already knows its rows and its spacing once they are built, so
        its own effective size hint is the authority the estimate only
        approximates; short of it, the scroll area was clipping the last row.
        """
        return int(self._stack.ci.layout.effectiveSizeHint(Qt.SizeHint.MinimumSize).height())

    def _lay_out_overlay(self, features: list[str]) -> int:
        """One plot per feature, every instance drawn over the others in the color of its well."""
        if self.domain != "time":
            return self._lay_out_overlay_off_time(features)
        normalize = self._normalize.isChecked()
        before, after = self._before.value(), self._after.value()
        master = None
        for row, feature in enumerate(features):
            plot = self._new_plot(row, 0)
            plot.setMinimumHeight(PLOT_PX)
            self._stack.ci.layout.setRowStretchFactor(row, 1)
            self._prepare_axis(plot, feature, normalize, AXIS_WIDTH, values=True, label=True)
            if row == len(features) - 1:
                plot.setLabel("bottom", ALIGNMENT_AXES[self.alignment])
            else:
                plot.hideAxis("bottom")
            if master is None:
                master = plot
            else:
                plot.setXLink(master)

            drawn: list[tuple[int, np.ndarray, np.ndarray]] = []
            lows, highs = [], []
            bounds = plausible_range(self.info.unit(feature))
            for i, series in enumerate(self._series):
                got = self._xy(series, feature, normalize, before, after, bounds)
                if got is None:
                    continue
                x, y = got
                self._curves[i].append(self._add_curve(plot, series, x, y))
                drawn.append((i, x, y))
                low, high = plausible_extent(y, (-np.inf, np.inf) if normalize else bounds)
                if not np.isnan(low):
                    lows.append(low)
                    highs.append(high)
            if lows:
                plot.getViewBox().setYRange(*padded_range(min(lows), max(highs)), padding=0)
            self._plots.append(plot)
            self._plot_series.append(drawn)
        return PLOT_PX * len(features) + 8

    def _lay_out_grid(self, features: list[str]) -> int:
        """One small plot per instance, in a grid under a heading per feature."""
        if self.domain != "time":
            return self._lay_out_grid_off_time(features)
        normalize = self._normalize.isChecked()
        before, after = self._before.value(), self._after.value()
        columns = self._columns.value()
        per_instance = self.per_instance_axis
        series = self.drawn_series()
        master = None
        row, height = 0, 0
        for section, feature in enumerate(features):
            bounds = plausible_range(self.info.unit(feature))
            prepared: list[tuple[int, np.ndarray, np.ndarray]] = []
            lows, highs = [], []
            for i, one in enumerate(series):
                got = self._xy(one, feature, normalize, before, after, bounds)
                if got is None:
                    continue
                x, y = got
                prepared.append((i, x, y))
                low, high = plausible_extent(y, (-np.inf, np.inf) if normalize else bounds)
                if not np.isnan(low):
                    lows.append(low)
                    highs.append(high)
            shared = padded_range(min(lows), max(highs)) if lows else None

            heading = HeaderLabel(justify="left")
            heading.setText(self._section_html(feature, normalize, len(prepared), len(series)))
            heading.setFixedHeight(SECTION_PX)
            self._stack.addItem(heading, row=row, col=0, colspan=columns)
            row += 1
            height += SECTION_PX
            if not prepared:
                continue

            n_rows = ceil(len(prepared) / columns)
            section_master = None
            for k, (i, x, y) in enumerate(prepared):
                place, column = divmod(k, columns)
                bottom = place == n_rows - 1
                plot = self._new_plot(row + place, column)
                plot.setMinimumHeight(SMALL_PLOT_PX + (SMALL_AXIS_PX if bottom else 0))
                self._prepare_axis(
                    plot,
                    feature,
                    normalize,
                    SMALL_AXIS_WIDTH,
                    values=per_instance or column == 0,
                    label=False,
                )
                if not bottom:
                    plot.hideAxis("bottom")
                elif section == len(features) - 1:
                    plot.setLabel("bottom", ALIGNMENT_AXES[self.alignment])
                if master is None:
                    master = plot
                else:
                    plot.setXLink(master)
                if per_instance:
                    low, high = plausible_extent(y, (-np.inf, np.inf) if normalize else bounds)
                    plot.getViewBox().setYRange(*padded_range(low, high), padding=0)
                elif section_master is None:
                    section_master = plot
                    if shared is not None:
                        plot.getViewBox().setYRange(*shared, padding=0)
                else:
                    plot.setYLink(section_master)
                self._add_shading(plot, series[i])
                self._curves[i].append(self._add_curve(plot, series[i], x, y))
                AnchoredText(
                    f'<span style="font-size:7pt; color:{series[i].color};">'
                    f"{series[i].label}</span>",
                    frac=(0.02, 0.98),
                    anchor=(0, 0),
                    boxed=False,
                ).attach(plot)
                self._plots.append(plot)
                self._plot_series.append([(i, x, y)])
            row += n_rows
            height += n_rows * SMALL_PLOT_PX + SMALL_AXIS_PX + 8
        return height + 8

    # -- the other domains: the same two layouts, drawing what the transforms give

    def _prepared_off_time(self, features: list[str]):
        """Per feature, what every drawn series gives in the domain chosen: its values or its spectrum."""
        normalize = self._normalize.isChecked()
        before, after = self._before.value(), self._after.value()
        series = self.drawn_series()
        prepared: dict[str, list] = {}
        for feature in features:
            bounds = plausible_range(self.info.unit(feature))
            rows = []
            for i, one in enumerate(series):
                got = self._window_values(one, feature, normalize, before, after, bounds)
                if got is None:
                    continue
                values, codes = got
                if self.domain == "spectrum":
                    spectrum = self._spectrum_of(values, bounds, normalize)
                    if spectrum is not None:
                        rows.append((i, spectrum))
                else:
                    inside = values[~np.isnan(values)]
                    if not normalize:
                        inside = inside[(inside >= bounds[0]) & (inside <= bounds[1])]
                    if len(inside):
                        rows.append((i, values, codes, float(inside.min()), float(inside.max())))
            prepared[feature] = rows
        return series, prepared, normalize

    def _shared_edges(self, rows) -> np.ndarray | None:
        """Bins spanning the readings of every series of one feature, for histograms on one axis."""
        if not rows:
            return None
        low = min(row[3] for row in rows)
        high = max(row[4] for row in rows)
        if high <= low:
            margin = max(abs(low) * 0.01, 0.5)
            low, high = low - margin, high + margin
        return np.linspace(low, high, self._controls.params().bins + 1)

    @staticmethod
    def _log_period_span(spectra: list[Spectrum]) -> tuple[float, float]:
        lows = [np.log10(s.periods[0]) for s in spectra]
        highs = [np.log10(s.periods[-1]) for s in spectra]
        return (float(min(lows)), float(max(highs)))

    def _shade_fixed_segment(self, plot: pg.PlotItem) -> None:
        """Grey the periods a segment the user fixed cannot resolve; a whole-stretch segment differs per instance."""
        segment = self._controls.params().segment_s
        if segment > 0:
            shade_unresolved(plot, float(np.log10(segment)), "x")

    def _lay_out_overlay_off_time(self, features: list[str]) -> int:
        """One plot per feature: the histograms, or the spectra, of every instance over one another."""
        series, prepared, normalize = self._prepared_off_time(features)
        for row, feature in enumerate(features):
            rows = prepared[feature]
            plot = self._new_plot(row, 0)
            plot.setMinimumHeight(PLOT_PX)
            self._stack.ci.layout.setRowStretchFactor(row, 1)
            self._prepare_left_axis(plot, feature, normalize, AXIS_WIDTH, values=True, label=True)
            self._prepare_bottom_axis(plot, feature, normalize)
            if self.domain == "spectrum":
                spectrum_grid(plot)
            drawn: list[tuple[int, np.ndarray, np.ndarray]] = []
            vb = plot.getViewBox()
            if self.domain == "distribution":
                edges = self._shared_edges(rows)
                top = 0.0
                for i, values, codes, _low, _high in rows:
                    result = self._histogram_of(
                        values, codes, edges, plausible_range(self.info.unit(feature)), normalize
                    )
                    if result is None or result.total == 0:
                        continue
                    share = 100.0 * result.counts / result.total
                    top = max(top, float(share.max()))
                    curve = add_step_outline(
                        plot, result.edges, share, pg.mkPen(series[i].color, width=1.2)
                    )
                    self._curves[i].append(curve)
                    centers = 0.5 * (result.edges[:-1] + result.edges[1:])
                    drawn.append((i, centers, share))
                if edges is not None:
                    vb.setXRange(float(edges[0]), float(edges[-1]), padding=0.02)
                    vb.setYRange(0.0, top * 1.05 if top > 0 else 1.0, padding=0)
            else:
                spectra = [spectrum for _i, spectrum in rows]
                lows, highs = [], []
                for i, spectrum in rows:
                    curve = add_spectrum_curve(
                        plot, spectrum, pg.mkPen(series[i].color, width=1.2), "x"
                    )
                    self._curves[i].append(curve)
                    self._spectra_by_plot[(id(plot), i)] = spectrum
                    x, y = spectrum_xy(spectrum, "x")
                    drawn.append((i, x, y))
                    finite = y[np.isfinite(y)]
                    if len(finite):
                        lows.append(float(finite.min()))
                        highs.append(float(finite.max()))
                if spectra:
                    vb.setXRange(*self._log_period_span(spectra), padding=0.01)
                    low, high = min(lows), max(highs)
                    pad = 0.05 * max(high - low, 1.0)
                    vb.setYRange(low - pad, high + pad, padding=0)
                    self._shade_fixed_segment(plot)
            if not drawn:
                AnchoredText(
                    f'<span style="font-size:10pt; color:{theme.current().faint};">nothing to '
                    "transform: too few readings, or flat signals</span>",
                    frac=(0.5, 0.5),
                    anchor=(0.5, 0.5),
                    boxed=False,
                ).attach(plot)
            self._plots.append(plot)
            self._plot_series.append(drawn)
        return PLOT_PX * len(features) + 8

    def _lay_out_grid_off_time(self, features: list[str]) -> int:
        """One small plot per instance: its histogram stacked by label period, or its spectrum."""
        series, prepared, normalize = self._prepared_off_time(features)
        columns = self._columns.value()
        per_instance = self.per_instance_axis
        colors = theme.current()
        row, height = 0, 0
        for section, feature in enumerate(features):
            rows = prepared[feature]
            bounds = plausible_range(self.info.unit(feature))
            heading = HeaderLabel(justify="left")
            heading.setText(self._section_html(feature, normalize, len(rows), len(series)))
            heading.setFixedHeight(SECTION_PX)
            self._stack.addItem(heading, row=row, col=0, colspan=columns)
            row += 1
            height += SECTION_PX
            if not rows:
                continue
            edges = self._shared_edges(rows) if self.domain == "distribution" else None
            span = (
                self._log_period_span([s for _i, s in rows]) if self.domain == "spectrum" else None
            )
            n_rows = ceil(len(rows) / columns)
            section_master = None
            for k, entry in enumerate(rows):
                i = entry[0]
                place, column = divmod(k, columns)
                bottom = place == n_rows - 1
                plot = self._new_plot(row + place, column)
                plot.setMinimumHeight(SMALL_PLOT_PX + (SMALL_AXIS_PX if bottom else 0))
                self._prepare_left_axis(
                    plot,
                    feature,
                    normalize,
                    SMALL_AXIS_WIDTH,
                    values=per_instance or column == 0,
                    label=False,
                )
                if bottom:
                    self._prepare_bottom_axis(plot, feature, normalize)
                    if section != len(features) - 1:
                        plot.setLabel("bottom", "")
                elif self.domain == "spectrum":
                    set_log_period_axis(plot, "bottom", "")
                    plot.hideAxis("bottom")
                else:
                    plot.hideAxis("bottom")
                vb = plot.getViewBox()
                if self.domain == "distribution":
                    _i, values, codes, _low, _high = entry
                    result = self._histogram_of(
                        values, codes, None if per_instance else edges, bounds, normalize
                    )
                    if result is None or result.total == 0:
                        continue
                    shares = {
                        kind: 100.0 * counts / result.total
                        for kind, counts in result.stacks.items()
                    }
                    scaled = Histogram(
                        result.edges, shares, result.left_out, result.mean, result.median
                    )
                    brushes = {kind: self._kind_brush(kind) for kind in shares}
                    add_stacked_bars(
                        plot,
                        scaled,
                        brushes,
                        horizontal=False,
                        pen=pg.mkPen(colors.plot_background, width=0.5),
                    )
                    total_share = 100.0 * result.counts / result.total
                    outline = add_step_outline(
                        plot, result.edges, total_share, pg.mkPen(series[i].color, width=1.2)
                    )
                    self._curves[i].append(outline)
                    add_center_lines(plot, result.mean, result.median, horizontal=False)
                    centers = 0.5 * (result.edges[:-1] + result.edges[1:])
                    x, y = centers, total_share
                    vb.setXRange(float(result.edges[0]), float(result.edges[-1]), padding=0.02)
                    top = float(total_share.max()) * 1.05 if total_share.max() > 0 else 1.0
                else:
                    _i, spectrum = entry
                    curve = add_spectrum_curve(
                        plot, spectrum, pg.mkPen(series[i].color, width=1.2), "x"
                    )
                    self._curves[i].append(curve)
                    self._spectra_by_plot[(id(plot), i)] = spectrum
                    spectrum_grid(plot)
                    x, y = spectrum_xy(spectrum, "x")
                    vb.setXRange(*span, padding=0.01)
                    finite = y[np.isfinite(y)]
                    low_p, high_p = (
                        (float(finite.min()), float(finite.max())) if len(finite) else (0, 1)
                    )
                    pad = 0.05 * max(high_p - low_p, 1.0)
                    top = (low_p - pad, high_p + pad)
                    self._shade_fixed_segment(plot)
                if per_instance:
                    if self.domain == "distribution":
                        vb.setYRange(0.0, top, padding=0)
                    else:
                        vb.setYRange(*top, padding=0)
                elif section_master is None:
                    section_master = plot
                    if self.domain == "distribution":
                        vb.setYRange(0.0, top, padding=0)
                    else:
                        vb.setYRange(*top, padding=0)
                else:
                    plot.setYLink(section_master)
                    if not per_instance:
                        # Widen the section's shared axis to hold this plot too.
                        master_vb = section_master.getViewBox()
                        (lo, hi) = master_vb.viewRange()[1]
                        if self.domain == "distribution":
                            master_vb.setYRange(0.0, max(hi, top), padding=0)
                        else:
                            master_vb.setYRange(min(lo, top[0]), max(hi, top[1]), padding=0)
                AnchoredText(
                    f'<span style="font-size:7pt; color:{series[i].color};">'
                    f"{series[i].label}</span>",
                    frac=(0.02, 0.98),
                    anchor=(0, 0),
                    boxed=False,
                ).attach(plot)
                self._plots.append(plot)
                self._plot_series.append([(i, x, y)])
            row += n_rows
            height += n_rows * SMALL_PLOT_PX + SMALL_AXIS_PX + 8
        return height + 8

    def _section_html(self, feature: str, normalize: bool, drawn: int, total: int) -> str:
        """The heading above one feature's grid: the feature, and what its axes mean."""
        colors = theme.current()
        unit = "z-score" if normalize else self.info.unit(feature)
        head = f"{feature}" + (f" [{unit}]" if unit else "")
        what = {
            "time": "value axis",
            "distribution": "share axis",
            "spectrum": "power axis",
        }[self.domain]
        axis = f"each plot on its own {what}" if self.per_instance_axis else f"all on one {what}"
        if self.domain == "spectrum":
            axis += ", the period along the bottom"
        missing = "" if drawn == total else f" · {total - drawn} recorded none of it"
        return (
            f'<span style="font-size:10pt; color:{colors.text};"><b>{head}</b></span>'
            f'<span style="font-size:8pt; color:{colors.muted};">&nbsp;&nbsp;'
            f"{drawn} of {total} instances · {axis}{missing}</span>"
        )

    def _apply_x_range(self) -> None:
        if not self._plots or self.domain != "time":
            return  # off the time axis every plot set its own range as it was built
        vb = self._plots[0].getViewBox()
        if self._x_range is not None:
            vb.setXRange(*self._x_range, padding=0)
            return
        xs = [x for drawn in self._plot_series for _, x, _ in drawn]
        if not xs:
            return
        starts = [float(x.min()) for x in xs]
        ends = [float(x.max()) for x in xs]
        if self.small_multiples and len(xs) >= 4:
            # One instance recorded for days would leave every other plot of the
            # grid a sliver against its left edge, so the grid opens on the
            # stretch most of the instances cover and leaves the rest to the
            # zoom; the hours boxes set it outright.
            lo, hi = float(np.quantile(starts, 0.1)), float(np.quantile(ends, 0.9))
        else:
            lo, hi = min(starts), max(ends)
        before, after = self._before.value(), self._after.value()
        if before > 0:
            lo = max(lo, -before)
        if after > 0:
            hi = min(hi, after)
        if hi <= lo:
            hi = lo + 1.0
        vb.setXRange(lo, hi, padding=0.02)

    def reset_views(self) -> None:
        self._x_range = None
        self._apply_x_range()

    def summary(self) -> str:
        """One line for the status bar: the fault, its instances and wells, how many are drawn."""
        fault = self.fault
        if fault is None or self._catalogue is None:
            return ""
        n = len(self._instances)
        wells = len({entry["well"] for entry in self._instances})
        aligned = sum(1 for entry in self._instances if entry["onset"] is not None)
        version = f"3W {self.info.version} · " if self.info.version else ""
        return (
            f"{version}{self.info.fault_name(fault)} · {n} real instances on {wells} wells · "
            f"{aligned} alignable at the {ALIGNMENT_NAMES[self.alignment].lower()} · "
            f"{len(self.drawn_series())} drawn "
        )

    # -- pointer

    def _highlight(self, index: int) -> None:
        """Bring one series to the front by width and fade the others; ``-1`` restores them all."""
        if index == self._hover:
            return
        self._hover = index
        for i, curves in self._curves.items():
            if i >= len(self._series):
                continue
            color = QColor(self._series[i].color)
            if index >= 0 and i != index:
                color.setAlpha(FADE_ALPHA)
                pen = pg.mkPen(color, width=1.0)
            elif i == index:
                pen = pg.mkPen(color, width=2.6)
            else:
                pen = pg.mkPen(color, width=1.2)
            for curve in curves:
                curve.setPen(pen)

    def _on_item_entered(self, item) -> None:
        """Pointing at an instance in the list names its line."""
        try:
            position = self._items.index(item)
        except ValueError:
            return
        entry = self._instances[position]
        for i, series in enumerate(self._series):
            if series.well == entry["well"] and series.position == entry["position"]:
                self._highlight(i)
                self.status.emit(self._describe(i, None, None))
                return
        self._highlight(-1)

    def _on_mouse_moved(self, pos) -> None:
        """Name the line nearest the pointer, and read the instance at that moment."""
        for plot, drawn in zip(self._plots, self._plot_series):
            vb = plot.getViewBox()
            if not vb.sceneBoundingRect().contains(pos):
                continue
            point = vb.mapSceneToView(pos)
            px_per_y = vb.viewPixelSize()[1]
            best, best_px = -1, HOVER_PX
            for i, x, y in drawn:
                k = int(np.searchsorted(x, point.x()))
                candidates = [j for j in (k - 1, k) if 0 <= j < len(x)]
                for j in candidates:
                    if np.isnan(y[j]):
                        continue
                    distance = abs(y[j] - point.y()) / px_per_y if px_per_y > 0 else np.inf
                    if distance < best_px:
                        best, best_px = i, distance
            self._highlight(best)
            if best >= 0:
                self.status.emit(self._describe(best, plot, float(point.x())))
            else:
                self.status.emit(HINT)
            return
        self._highlight(-1)
        self.status.emit(HINT)

    def _describe(self, index: int, plot, hours: float | None) -> str:
        series = self._series[index]
        fault = self.fault
        parts = [
            (
                f"{well_label(series.well)} · {series.title} · {self.info.fault_name(fault)} · "
                f"{ALIGNMENT_NAMES[self.alignment].lower()} at {series.onset:%Y-%m-%d %H:%M:%S}"
            )
        ]
        if hours is not None and self.domain != "time":
            # Off the time axis the coordinate under the pointer is a reading or a period.
            x = hours
            drawn = next(
                (entry for k, entry in enumerate(self._plot_series) if self._plots[k] is plot), []
            )
            own = next((row for row in drawn if row[0] == index), None)
            if self.domain == "distribution":
                if own is not None:
                    _i, centers, share = own
                    k = int(np.clip(np.searchsorted(centers, x), 0, len(centers) - 1))
                    parts.append(f"around {centers[k]:.4g}: {share[k]:.1f} % of its samples")
            else:
                if own is not None:
                    _i, log_periods, log_power = own
                    k = int(np.clip(np.searchsorted(log_periods, x), 0, len(log_periods) - 1))
                    parts.append(
                        f"period {format_period(10 ** log_periods[k])}: power {10 ** log_power[k]:.3g}"
                    )
                    spectrum = self._spectra_by_plot.get((id(plot), index))
                    if spectrum is not None:
                        parts.append(caption_for(spectrum, ""))
            return " · ".join(parts)
        if hours is not None:
            stamp = series.onset + pd.Timedelta(hours=hours)
            frame = series.frame
            parts.append(f"t = {hours:+.2f} h ({stamp:%Y-%m-%d %H:%M:%S})")
            if frame.index[0] <= stamp <= frame.index[-1]:
                i = min(int(frame.index.searchsorted(stamp, side="right")) - 1, len(frame) - 1)
                klass = column_as_float(frame, "class")[i]
                state = column_as_float(frame, "state")[i]
                parts.append(
                    f"{label_name(klass, self.info.fault_names, self.info.transient_offset)} / "
                    f"{state_name(state)}"
                )
                readings = []
                for feature in self.selected_features():
                    if feature in frame.columns:
                        value = column_as_float(frame, feature)[i]
                        unit = self.info.unit(feature)
                        readings.append(
                            f"{feature} = {'—' if np.isnan(value) else f'{value:.4g} {unit}'.rstrip()}"
                        )
                if readings:
                    parts.append(", ".join(readings))
            else:
                parts.append("outside the instance")
        return " · ".join(parts)
