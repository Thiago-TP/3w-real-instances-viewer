"""The Qt pieces of the signal views, shared by the instance window and the faults page.

``TransformControls`` is the toolbar widget holding every parameter a view
takes — the segment length, the overlap, the window function, the number of
bins — so that the two windows offer the same widgets and mean the same thing
by them. ``LogPeriodAxisItem`` labels an axis of log10 seconds in the units a
person says a period in. The rest are the builders both windows draw with: a
histogram as stacked bars or as a step outline, a spectrum curve, the image of
a spectrogram on a single-hue ramp, and the shading of the periods a segment
cannot resolve.

Every spectral plot carries its data in log10: the period axis because the
events span seconds to days, the power axis because a line an order of
magnitude above the noise is what a spectrum is read for. The axes are told
so (``AxisItem.setLogMode`` for power, this module's own axis for period) and
print real values; the items themselves are never put in log mode, since an
image item or a bar item would not follow.
"""

from collections.abc import Sequence

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QSpinBox, QWidget

from overlap_viewer import theme
from overlap_viewer.palette import tint
from overlap_viewer.spectral import (
    WINDOWS,
    Histogram,
    Spectrogram,
    Spectrum,
    TransformParams,
    format_period,
)

# The periods an axis may put a tick at, in seconds: from one second to a month.
TICK_PERIODS_S = (
    1,
    2,
    5,
    10,
    15,
    30,
    60,
    120,
    300,
    600,
    900,
    1800,
    3600,
    7200,
    10800,
    21600,
    43200,
    86400,
    172800,
    604800,
    2592000,
)
MIN_TICK_PX = 34  # two ticks of a period axis closer than this collide

DEFAULT_SEGMENT_MIN = 45  # what the box offers once the whole stretch is unticked
DEFAULT_OVERLAP_PCT = 50  # Rabelo's windows overlap by half
DEFAULT_BINS = 40
GRID_ALPHA = 0.25  # the grid of a spectrum plot, faint enough to stay behind the curve
PEAK_BAR_PX = 14  # how far under the top of a trace plot the bar of one peak period sits
PEAK_FONT_PX = 10


class TransformControls(QWidget):
    """The parameters of the views that transform, as toolbar widgets.

    Signals
    -------
    changed()
        A parameter was edited; the views should be computed again.
    """

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._segment_label = QLabel(" Segment ")
        self._whole = QCheckBox("whole stretch")
        self._whole.setChecked(True)
        self._whole.setToolTip(
            "Take the spectrum over the whole stretch shown, in one segment (a periodogram), "
            "which is the only way to see the events: severe slugging cycles every 50 to 90 "
            "minutes, and a segment of a few minutes holds no cycle of it. The spectrogram, "
            "which needs more than one segment, then slices the recording into eighths. Untick "
            "to set the segment length yourself."
        )
        self._segment = QSpinBox()
        self._segment.setRange(1, 24 * 60)
        self._segment.setValue(DEFAULT_SEGMENT_MIN)
        self._segment.setSuffix(" min")
        self._segment.setEnabled(False)
        self._segment.setToolTip(
            "Length of the segments the spectrum averages over and the spectrogram is sliced "
            "into, in minutes. Nothing longer than a segment can be resolved, so the axis is "
            "greyed beyond it."
        )
        self._overlap_label = QLabel(" Overlap ")
        self._overlap = QSpinBox()
        self._overlap.setRange(0, 90)
        self._overlap.setValue(DEFAULT_OVERLAP_PCT)
        self._overlap.setSuffix(" %")
        self._overlap.setSingleStep(10)
        self._overlap.setToolTip(
            "How much of a segment the next one repeats. More overlap gives the spectrogram more "
            "slices and the spectrum more segments to average, from the same stretch."
        )
        self._window_label = QLabel(" Window ")
        self._window = QComboBox()
        self._window.addItems(list(WINDOWS))
        self._window.setToolTip(
            "The taper applied to every segment before it is transformed. Hann is the usual "
            "choice; rectangular is no taper at all, which leaks the strong lines into their "
            "neighbours."
        )
        self._bins_label = QLabel(" Bins ")
        self._bins = QSpinBox()
        self._bins.setRange(5, 200)
        self._bins.setValue(DEFAULT_BINS)
        self._bins.setToolTip("How many bins the histograms count the readings into")

        for widget in (
            self._segment_label,
            self._whole,
            self._segment,
            self._overlap_label,
            self._overlap,
            self._window_label,
            self._window,
            self._bins_label,
            self._bins,
        ):
            layout.addWidget(widget)
        self._whole.toggled.connect(self._on_whole_toggled)
        self._segment.valueChanged.connect(self.changed)
        self._overlap.valueChanged.connect(self.changed)
        self._window.currentIndexChanged.connect(self.changed)
        self._bins.valueChanged.connect(self.changed)

    def _on_whole_toggled(self, checked: bool) -> None:
        self._segment.setEnabled(not checked)
        self.changed.emit()

    def params(self) -> TransformParams:
        return TransformParams(
            segment_s=0 if self._whole.isChecked() else self._segment.value() * 60,
            overlap=self._overlap.value() / 100.0,
            window=self._window.currentText(),
            bins=self._bins.value(),
        )

    def show_spectral(self, shown: bool) -> None:
        """Show the segment, overlap and window widgets only while a spectral view is on."""
        for widget in (
            self._segment_label,
            self._whole,
            self._segment,
            self._overlap_label,
            self._overlap,
            self._window_label,
            self._window,
        ):
            widget.setVisible(shown)

    def anything_shown(self) -> bool:
        """Whether any widget is on show, so a toolbar row holding only this can hide with it."""
        return self._segment.isVisibleTo(self) or self._bins.isVisibleTo(self)

    def show_bins(self, shown: bool) -> None:
        """Show the bins widget only while a distribution view is on."""
        self._bins_label.setVisible(shown)
        self._bins.setVisible(shown)


class LogPeriodAxisItem(pg.AxisItem):
    """An axis whose values are log10 of a period in seconds, labeled ``30 s``, ``5 min``, ``1.5 h``.

    The ticks sit at the periods a person would name, as many of them as the
    axis has room for at the current zoom.
    """

    def tickValues(self, minVal, maxVal, size):
        if maxVal <= minVal or size <= 0:
            return []
        px_per_unit = size / (maxVal - minVal)
        values = []
        last_px = -np.inf
        for period in TICK_PERIODS_S:
            value = np.log10(period)
            if value < minVal or value > maxVal:
                continue
            px = (value - minVal) * px_per_unit
            if px - last_px >= MIN_TICK_PX:
                values.append(float(value))
                last_px = px
        return [(1.0, values)]

    def tickStrings(self, values, scale, spacing):
        return [format_period(10.0**value) for value in values]


def power_axis(plot: pg.PlotItem, side: str, label: str) -> None:
    """Make one axis of ``plot`` print the powers its log10 data stand for."""
    axis = plot.getAxis(side)
    axis.setLogMode(True)
    axis.enableAutoSIPrefix(False)  # a prefix on a logarithmic axis reads as a stray factor
    plot.setLabel(side, label)


def spectrum_grid(plot: pg.PlotItem) -> None:
    """The faint grid of a spectrum plot: a decade of power and a named period per line."""
    plot.showGrid(x=True, y=True, alpha=GRID_ALPHA)


def add_center_lines(
    plot: pg.PlotItem, mean: float, median: float, horizontal: bool
) -> list[pg.InfiniteLine]:
    """The mean (solid) and the median (dashed) of a distribution, as lines across its plot.

    ``horizontal`` for a marginal histogram, whose values run up the side.
    """
    colors = theme.current()
    items = []
    for value, style in ((mean, Qt.PenStyle.SolidLine), (median, Qt.PenStyle.DashLine)):
        if not np.isfinite(value):
            continue
        line = pg.InfiniteLine(
            pos=value,
            angle=0 if horizontal else 90,
            movable=False,
            pen=pg.mkPen(colors.muted, width=1.2, style=style),
        )
        line.setZValue(12)
        plot.addItem(line, ignoreBounds=True)
        items.append(line)
    return items


class PeriodMarker(pg.GraphicsObject):
    """One cycle of the dominant period, drawn as a bar under the top edge of a trace plot.

    The spectrum says the signal repeats every 89 minutes; this puts 89 minutes
    against the trace, so the eye can check the claim against the waves. The
    bar starts a little inside the left edge of the stretch on screen and is
    as long as the period; its label names the period. Drawn in device pixels
    after the ends are mapped, as the other items of the viewer are, so the
    bar keeps its thickness and its text its size at every zoom.
    """

    def __init__(self, z: float = 30.0):
        super().__init__()
        self.setZValue(z)
        self._x0 = np.nan
        self._length = 0.0
        self._label = ""

    def set_period(self, x0: float, length: float, label: str) -> None:
        """Put the bar from ``x0`` over ``length`` (both in the plot's x units), named ``label``."""
        self._x0, self._length, self._label = float(x0), float(length), label
        self.prepareGeometryChange()
        self.update()

    def clear(self) -> None:
        self.set_period(np.nan, 0.0, "")

    def dataBounds(self, ax, frac=1.0, orthoRange=None):
        return None

    def pixelPadding(self):
        return 0

    def _view_rect(self) -> QRectF:
        vb = self.getViewBox()
        if vb is None or not hasattr(vb, "viewRange"):
            return QRectF()
        (xmin, xmax), (ymin, ymax) = vb.viewRange()
        return QRectF(QPointF(xmin, ymin), QPointF(xmax, ymax)).normalized()

    def boundingRect(self):
        return QRectF() if not np.isfinite(self._x0) else self._view_rect()

    def viewRangeChanged(self, *args):
        self.prepareGeometryChange()
        self.update()

    def paint(self, p: QPainter, option, widget=None):
        if not np.isfinite(self._x0) or self._length <= 0:
            return
        rect = self._view_rect()
        if rect.isNull():
            return
        colors = theme.current()
        transform = p.transform()
        left = transform.map(QPointF(self._x0, rect.top()))
        right = transform.map(QPointF(self._x0 + self._length, rect.top()))
        top = min(transform.map(rect.topLeft()).y(), transform.map(rect.bottomLeft()).y())
        y = top + PEAK_BAR_PX
        p.save()
        p.resetTransform()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(colors.text), 1.6)
        p.setPen(pen)
        p.drawLine(QPointF(left.x(), y), QPointF(right.x(), y))
        for end in (left.x(), right.x()):
            p.drawLine(QPointF(end, y - 4), QPointF(end, y + 4))
        font = QFont()
        font.setPixelSize(PEAK_FONT_PX)
        p.setFont(font)
        metrics = QFontMetricsF(font)
        width = metrics.horizontalAdvance(self._label)
        text_x = max(left.x(), min(0.5 * (left.x() + right.x()) - width / 2, right.x() - width))
        p.drawText(QPointF(text_x, y + 4 + metrics.ascent()), self._label)
        p.restore()


def spectrogram_colormap() -> pg.ColorMap:
    """One hue, from the plotting ground to the trace color of the theme in force.

    A magnitude wants a single hue running away from the background, so that
    the eye reads "more" as "darker" (or, on a dark ground, "brighter") and
    never as a change of hue; the trace color is the hue every plot of the
    viewer already draws its signal in.
    """
    colors = theme.current()
    stops = [
        colors.plot_background,
        tint(colors.trace, 0.35),
        tint(colors.trace, 0.7),
        colors.trace,
    ]
    return pg.ColorMap(pos=np.array([0.0, 0.35, 0.7, 1.0]), color=[QColor(stop) for stop in stops])


def unresolved_brush() -> QColor:
    """The fill of the periods a segment cannot resolve: the shade of an unknown, translucent."""
    color = QColor(theme.current().unknown)
    color.setAlpha(150)
    return color


def add_stacked_bars(
    plot: pg.PlotItem,
    result: Histogram,
    brushes: dict,
    horizontal: bool,
    pen=None,
) -> list[pg.BarGraphItem]:
    """The stacks of a histogram as bars, one item per stack, laid along the value axis.

    ``horizontal`` lays the value axis vertically and the counts to the right,
    the shape of a marginal beside a time series; otherwise the values run
    along x and the counts up. ``brushes`` maps a stack key to what fills it.
    """
    items = []
    base = np.zeros(len(result.edges) - 1, dtype=float)
    lower, upper = result.edges[:-1], result.edges[1:]
    for key, counts in result.stacks.items():
        top = base + counts
        if horizontal:
            item = pg.BarGraphItem(
                x0=base, x1=top, y0=lower, y1=upper, brush=brushes.get(key), pen=pen
            )
        else:
            item = pg.BarGraphItem(
                x0=lower, x1=upper, y0=base, y1=top, brush=brushes.get(key), pen=pen
            )
        plot.addItem(item)
        items.append(item)
        base = top
    return items


def add_step_outline(
    plot: pg.PlotItem, edges: np.ndarray, heights: np.ndarray, pen, horizontal: bool = False
) -> pg.PlotDataItem:
    """The outline of a histogram as a step curve: what several of them can share one plot as."""
    if horizontal:
        # A step curve only steps along x, so a sideways outline is drawn as
        # the polygon of its corners.
        ys = np.repeat(edges, 2)
        xs = np.concatenate(([0.0], np.repeat(heights, 2), [0.0]))
        curve = pg.PlotDataItem(xs, ys, pen=pen)
    else:
        curve = pg.PlotDataItem(edges, heights, stepMode="center", pen=pen)
    plot.addItem(curve)
    return curve


def spectrum_xy(spectrum: Spectrum, period_axis: str) -> tuple[np.ndarray, np.ndarray]:
    """The log10 coordinates of a spectrum as drawn, binned in log period, the period along ``period_axis``."""
    floor = np.finfo(float).tiny
    periods, power = spectrum.binned()
    log_period = np.log10(periods)
    log_power = np.log10(np.maximum(power, floor))
    return (log_period, log_power) if period_axis == "x" else (log_power, log_period)


def add_spectrum_curve(
    plot: pg.PlotItem, spectrum: Spectrum, pen, period_axis: str
) -> pg.PlotDataItem:
    x, y = spectrum_xy(spectrum, period_axis)
    curve = pg.PlotDataItem(x, y, pen=pen)
    plot.addItem(curve)
    return curve


def shade_unresolved(
    plot: pg.PlotItem, log_segment: float, period_axis: str
) -> pg.LinearRegionItem:
    """Grey the periods beyond the segment length, which the estimate cannot resolve."""
    far = log_segment + 6.0
    region = pg.LinearRegionItem(
        values=(log_segment, far),
        orientation="vertical" if period_axis == "x" else "horizontal",
        brush=pg.mkBrush(unresolved_brush()),
        pen=pg.mkPen(None),
        movable=False,
    )
    region.setZValue(-8)
    plot.addItem(region, ignoreBounds=True)
    return region


def add_spectrogram_image(
    plot: pg.PlotItem, image: Spectrogram, x_of_seconds, levels: tuple[float, float] | None = None
) -> pg.ImageItem:
    """Draw a spectrogram into ``plot``: time along x, log10 period along y, log10 power as color.

    ``x_of_seconds`` maps seconds from the first sample of the series to the
    plot's x; the image is stretched over the segments' centers, half a hop
    beyond the first and the last. ``levels`` fixes the two powers the ramp
    runs between; by default the 5th and the 99.5th percentiles of the image,
    so that one bright line does not wash out the rest.
    """
    item = pg.ImageItem(image.power, axisOrder="col-major")
    item.setColorMap(spectrogram_colormap())
    if levels is None:
        finite = image.power[np.isfinite(image.power)]
        if len(finite):
            levels = (float(np.percentile(finite, 5)), float(np.percentile(finite, 99.5)))
            if levels[1] <= levels[0]:
                levels = (levels[0] - 1.0, levels[0] + 1.0)
        else:
            levels = (-1.0, 1.0)
    item.setLevels(levels)
    half = image.hop_s / 2.0
    x0 = float(x_of_seconds(image.centers[0] - half))
    x1 = float(x_of_seconds(image.centers[-1] + half))
    y0, y1 = float(image.log_periods[0]), float(image.log_periods[-1])
    step = (y1 - y0) / max(len(image.log_periods) - 1, 1)
    item.setRect(QRectF(x0, y0 - step / 2, x1 - x0, (y1 - y0) + step))
    item.setZValue(-1)
    plot.addItem(item)
    return item


def period_range(image_or_spectrum) -> tuple[float, float]:
    """The log10 period span an axis should show for a spectrum or a spectrogram."""
    if isinstance(image_or_spectrum, Spectrogram):
        return (float(image_or_spectrum.log_periods[0]), float(image_or_spectrum.log_periods[-1]))
    periods = image_or_spectrum.periods
    return (float(np.log10(periods[0])), float(np.log10(periods[-1])))


def caption_for(spectrum: Spectrum, unit: str, compact: bool = False) -> str:
    """What a spectrum plot writes in its corner: the dominant period, its share, the segments.

    ``compact`` breaks it into short lines, for a plot a couple of hundred
    pixels wide.
    """
    period, share = spectrum.dominant()
    if np.isfinite(period):
        line = (
            f"peak {format_period(period)}<br>{share * 100:.0f} % of the power"
            if compact
            else f"dominant period {format_period(period)} · {share * 100:.0f} % of the power"
        )
    else:
        line = "no dominant period"
    segments = (
        f"whole stretch ({format_period(spectrum.segment_s)})"
        if spectrum.n_segments == 1
        else f"{spectrum.n_segments} segments of {format_period(spectrum.segment_s)}"
    )
    return f"{line}<br>{segments}" if compact else f"{line} · {segments}"


def format_width(width: float, unit: str) -> str:
    """The width of a bin with its unit, prefixed (``31.1 kPa``) when the unit takes a prefix."""
    if unit == "Pa":
        return pg.siFormat(width, precision=3, suffix=unit)
    return f"{width:.3g} {unit}".rstrip()


def stack_keys(kinds: Sequence[str]) -> list[str]:
    """The order the stacks of a histogram are laid in: normal, transient, steady, then unknown."""
    order = ("normal", "transient", "steady", "unknown")
    return [kind for kind in order if kind in set(kinds)]


def set_log_period_axis(plot: pg.PlotItem, side: str, label: str = "period") -> LogPeriodAxisItem:
    """Replace one axis of ``plot`` with a period axis and label it."""
    axis = LogPeriodAxisItem(orientation=side)
    plot.setAxisItems({side: axis})
    plot.setLabel(side, label)
    return axis


def power_label(unit: str) -> str:
    """The label of a power axis: the density's unit when the series has one."""
    return f"power [{unit}²/Hz]" if unit and unit != "-" else "power"
