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

from overlap_viewer import theme
from overlap_viewer.config import FAULT_SIGNATURES, REACH_LABELS
from overlap_viewer.dataset import DatasetInfo, WellData, instance_title, merge_instances
from overlap_viewer.help import HelpWindow
from overlap_viewer.items import (
    AnchoredText,
    HeaderLabel,
    ScrollFriendlyViewBox,
    SeamsItem,
    SegmentsItem,
    TimeAxisItem,
    WheelToParent,
)
from overlap_viewer.labels import (
    FeatureStats,
    Segment,
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
    state_name,
)
from overlap_viewer.loading import FrameCache
from overlap_viewer.overview import ElidedLabel
from overlap_viewer.palette import (
    background_color,
    bar_color,
    legend_label,
    state_color,
    tint,
    unknown_background,
)
from overlap_viewer.timemap import TimeMap

AXIS_WIDTH = 84  # every left axis has this width, so all plots share the same x pixels
PANEL_WIDTH = 200  # the feature panel: room for the longest variable name and its unit
BAND_PX = 18
HEADER_PX = 24
PLOT_MIN_PX = 150
AXIS_PX = 28
ROW_SPACING = 2  # between two rows of one instance block
BLOCK_SPACING = 16  # added above the header of every block but the first
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
        self, data: WellData, index: int, info: DatasetInfo, frames: FrameCache, parent=None
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.info = info
        self._frames = frames
        self.well = data.origin
        # The instance the window is about, kept across a switch: the one
        # clicked, or the first of the bar clicked, which is the one its title
        # names.
        self.subject = data.members[index][0]

        # The group is fixed here and never grows: the bars the overview would
        # have shown for this click, and the instances behind them. The two
        # drawings of it are built now, from the well's instance table alone —
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
        self._plots: dict[tuple[int, str], pg.PlotItem] = {}
        self._feature_masters: dict[str, pg.PlotItem] = {}
        self._crosshairs: list[pg.InfiniteLine] = []
        self._master: pg.PlotItem | None = None
        self._x_range: tuple[float, float] | None = None
        self._help: HelpWindow | None = None

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
        self._features = self._feature_table()
        self._signature = self._signature_for_group()

        others = len(self.rows) - 1
        self.setWindowTitle(
            f"{self.well.label} · {instance_title(self.rows.iloc[self.clicked])}"
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

    def _seam_positions(self, members: list[int]) -> list[float]:
        """Where, inside one merged block, each instance after the first begins."""
        if len(members) < 2:
            return []
        starts = self.well.rows["start"].iloc[members[1:]]
        return [float(x) for x in self.timemap.to_x(starts)]

    def _feature_table(self) -> pd.DataFrame:
        """Every sensor the dataset or the files declare, alphabetically, with how many blocks record it."""
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

        The clicked block decides, since the window was opened from it — the
        event a merged one develops furthest, which is the event its bar is
        outlined with. Only when that fault has no published signature does the
        window fall back to another fault present, and only if exactly one such
        fault is, so the box never silently mixes two events' variables.
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
                "are merged, and this window alone changes — the overview and any other instance "
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

    def _swap_feature_panel(self, selected: set[str]) -> None:
        """Build the feature panel again for the blocks now drawn, keeping the selection.

        The panel is rebuilt rather than edited because every part of it
        depends on the blocks: which features any of them recorded, in how many
        of them, and which event's signature the window can offer.
        """
        previous, self._checks = self._panel, {}
        self._panel = self._build_feature_panel(selected)
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
            check = QCheckBox(f"{row.sensor} [{unit}]" if unit else row.sensor)
            description = self.info.sensor_descriptions.get(row.sensor, "")
            recorded = f"recorded in {row.recorded} of {n} {self._noun}{'s' if n > 1 else ''}"
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
        # The box says only "Signature"; the event it belongs to is in the tooltip,
        # where it costs the panel no width.
        text = f"Signature of {name}: {', '.join(variables)}. These variables identify the event."
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
            f'<span style="font-size:11pt;"><b>{self.well.label}</b> · {what}</span><br>'
            f'<span style="color:{theme.current().muted};">{first:%Y-%m-%d %H:%M:%S} → {last:%Y-%m-%d %H:%M:%S} · {span_h:.1f} h spanned · '
            f"{shared_h:.1f} h recorded by two or more {noun}s · {shown}</span>"
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
        joined = f"{merged} instances merged · " if merged > 1 else ""
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
        return (
            f'<span style="font-size:10pt;"><b>{instance_title(row)}</b></span>{badge}'
            f"&nbsp;&nbsp;{squares}"
            f'<span style="font-size:9pt; color:{colors.muted};"> {what} · {joined}'
            f"{start:%Y-%m-%d %H:%M:%S} → {end.strftime(end_fmt)} · "
            f"{row['hours']:.1f} h · {int(row['n_samples']):,} samples · level {int(row['lane']) + 1} · "
            f"overlaps {partners} shown</span>"
        )

    def _overlaps(self, a: int, b: int) -> bool:
        ra, rb = self.rows.iloc[a], self.rows.iloc[b]
        return bool(ra["start"] <= rb["end"] and rb["start"] <= ra["end"])

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

    def _lay_out_stack(self) -> None:
        """Fill the stack: the shared-coverage band, then one block per bar."""
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
            seams = self._seams[position]
            self._add_band(row, self._state_band_segments(position), "state", seams)
            self._add_band(row + 1, self._class_band_segments(position), "class", seams)
            heights += [BAND_PX, BAND_PX]
            row += 2
            for k, feature in enumerate(features):
                last = k == len(features) - 1
                self._add_feature_plot(row, position, feature, show_axis=last)
                heights.append(PLOT_MIN_PX + (AXIS_PX if last else 0))
                row += 1
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
        change size — which is whenever the stack fits, the scroll area then
        holding it at the viewport — no resize follows to put the item back.
        The stack would be drawn into the top of the window with every plot at
        its minimum and the room below it left empty, so the view's own resize
        handler is called to restore the item to the widget it sits in. It
        reads nothing from the event, and a later resize simply does it again.
        """
        self._layout_widget.resizeEvent(None)

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
            angle=90,
            movable=False,
            pen=pg.mkPen(theme.current().crosshair, width=1, style=Qt.PenStyle.DashLine),
        )
        crosshair.setZValue(40)
        crosshair.setVisible(False)
        plot.addItem(crosshair, ignoreBounds=True)
        self._crosshairs.append(crosshair)
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
        self._add_seams(plot, self._seams[position])

        colors = theme.current()
        stats = feature_stats(frame, feature)
        if stats.recorded:
            x = self.timemap.to_x(frame.index)
            y = frame[feature].to_numpy(dtype=float)
            curve = pg.PlotDataItem(x, y, pen=pg.mkPen(colors.trace, width=1), connect="finite")
            # Added before clipping and downsampling are switched on: while an item is being
            # added, pyqtgraph resolves its view to the layout widget, which those options query.
            plot.addItem(curve)
            curve.setDownsampling(auto=True, method="peak")
            curve.setClipToView(True)
            note = format_delta(stats.delta, unit) + (" (flat)" if stats.flat else "")
            AnchoredText(
                f'<span style="font-size:8pt; color:{colors.text};">'
                f"{note} · coverage {stats.coverage:.1f} %</span>"
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

    # -- segments

    def _class_runs(self, position: int) -> list[tuple[Segment, int | None]]:
        """The label runs of one block, with the fault folder each stretch came from.

        A block of one instance is read from its frame, as it always was. A
        merged one is read from the label runs the catalogue already holds for
        its instances, which say the same as the merged ``class`` column and
        also say which file supplied each stretch — so a normal period labeled
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
