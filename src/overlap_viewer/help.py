"""The help window: what the fault classes, the variables and the colors mean.

One window with a tab per question a reader of these plots actually has — what
is this event, what is this variable, what is this well status, how do I work
the viewer — rendered as rich text so the swatches can carry the very colors
the plots draw. Both windows open it, on the tab that suits them.
"""

import pandas as pd
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QImage, QTextDocument
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
)

from overlap_viewer.config import FAULT_SIGNATURES, WELL_STATES, asset_path
from overlap_viewer.dataset import DatasetInfo
from overlap_viewer.help_text import (
    CONFIRMATION_WINDOWS,
    DATASET_NOTES,
    FAULTS,
    FIGURES,
    STATES,
    TRANSIENT_CAPABLE,
    USAGE,
    VARIABLES,
)
from overlap_viewer.palette import bar_color, fault_color, state_color

PAPER = (
    "Vargas et al., <i>3W Dataset 2.0.0: a realistic and public dataset with rare undesirable real "
    'events in oil wells</i>, 2025 — <a href="https://doi.org/10.1038/s41597-026-07225-z">'
    "doi.org/10.1038/s41597-026-07225-z</a>"
)

# Everything in this window comes from these three, and each entry says which.
SOURCES = (
    "Sources: "
    "the <b>2.0.0 data article</b> (" + PAPER + "); "
    "the <b>1.0.0 data article</b>, Vargas et al., <i>A realistic and public dataset with rare "
    'undesirable real events in oil wells</i>, 2019 — <a href="https://doi.org/10.1016/j.petrol.'
    '2019.106223">doi.org/10.1016/j.petrol.2019.106223</a>; and the <b>doctoral thesis</b> of '
    "R. E. V. Vargas, which the two articles condense."
)

STYLE = """
<style>
  body { font-size: 10pt; }
  h2 { font-size: 12pt; margin-bottom: 2px; }
  h3 { font-size: 10.5pt; margin-bottom: 2px; }
  p { margin-top: 3px; margin-bottom: 8px; }
  .muted { color: #666666; }
  .sub { color: #444444; font-size: 9pt; }
  th { text-align: left; background-color: #efefef; }
</style>
"""

# Reaches a bar can carry, in the order the legend lists them.
REACH_ROWS = (
    ("steady", "steady state reached", "the event is installed inside this instance"),
    (
        "transient",
        "transient state reached",
        "the event is still installing itself when the recording ends",
    ),
    ("normal", "no fault reached", "the window closes before the event shows in the labels"),
)


def _swatch(color: str, width: int = 34) -> str:
    """A colored cell, for a legend-like table."""
    return f'<td width="{width}" bgcolor="{color}" style="border: 1px solid #888888;">&nbsp;</td>'


def _document(body: str) -> str:
    return f"<html><head>{STYLE}</head><body>{body}</body></html>"


class Figures:
    """The illustrations the help can show, loaded once and shared by the tabs.

    A figure the project does not ship simply does not appear: the help is
    text first, and an installation without the docs directory still opens.
    """

    def __init__(self) -> None:
        self.images: dict[str, QImage] = {}
        for name, figure in FIGURES.items():
            path = asset_path(figure.file)
            if path is None:
                continue
            image = QImage(str(path))
            if not image.isNull():
                self.images[name] = image

    def html(self, name: str) -> str:
        """The figure and its caption, or nothing when it is not available."""
        if name not in self.images:
            return ""
        figure = FIGURES[name]
        return (
            f'<p align="center"><img src="{name}" width="{figure.width}"></p>'
            f'<p align="center" class="sub">{figure.caption}<br><i>{figure.credit}</i></p>'
        )

    def attach(self, browser: QTextBrowser) -> None:
        """Make the images resolvable by the ``img`` tags of one browser."""
        document = browser.document()
        for name, image in self.images.items():
            document.addResource(QTextDocument.ResourceType.ImageResource, QUrl(name), image)


def fault_page(
    info: DatasetInfo, counts: dict[int, int] | None = None, figures: "Figures | None" = None
) -> str:
    """The class labels: what each event is, how it shows, and the colors it takes."""
    parts = [
        "<h2>Fault classes</h2>",
        (
            "<p>Every instance sits in the folder of the event it carries, and that folder fixes "
            "the <b>hue</b> of its bar. How far the event developed <i>inside that particular "
            "recording</i> fixes the <b>tint</b>:</p>"
        ),
        '<table cellspacing="0" cellpadding="4">',
    ]
    for reach, name, meaning in REACH_ROWS:
        parts.append(
            f"<tr>{_swatch(bar_color(9, reach))}<td><b>{name}</b></td>"
            f'<td class="sub">{meaning}</td></tr>'
        )
    parts.append("</table>")
    parts.append(
        '<p class="sub">Normal-operation instances are never tinted: they have no event to develop.'
        " The example above uses one fault's hue; every fault has its own. Stretches the experts"
        " left unlabeled are drawn in pale grey under a diagonal hatch — a texture rather than one"
        " more shade, since two of the fault hues are themselves grey.</p>"
    )
    if figures is not None:
        parts.append(figures.html("platform-overview"))

    for number in sorted(info.fault_names):
        entry = FAULTS.get(number)
        name = info.fault_name(number)
        hue = fault_color(number)
        parts.append(f'<hr><h3><font color="{hue}">■</font> {number} — {name}</h3>')

        codes = [f"<b>{number}</b> once the event is installed (steady state)"]
        if number in TRANSIENT_CAPABLE:
            codes.append(
                f"<b>{number + info.transient_offset}</b> while it installs itself (transient)"
            )
        else:
            codes.append("no transient period in the dataset")
        if number == 0:
            codes = ["<b>0</b> throughout"]
        line = " · ".join(codes)
        if counts is not None:
            n = counts.get(number, 0)
            line += f" · <b>{n}</b> real instance{'s' if n != 1 else ''} in this dataset"
        parts.append(f'<p class="sub">class label: {line}</p>')

        if entry is None:
            parts.append(
                '<p class="muted">This class is not one of the ten the paper describes.</p>'
            )
            continue
        parts.append(f"<p>{entry.what}</p>")
        parts.append(f"<p><b>In the readings.</b> {entry.signature}</p>")
        window = CONFIRMATION_WINDOWS.get(number)
        if window:
            parts.append(
                '<p class="sub">The analysts who monitor the wells confirm an occurrence of this '
                f"event over a window of about <b>{window}</b> — the span its evidence needs to "
                "become conclusive to a reader, and a fair default to put on screen.</p>"
            )
        if number in FAULT_SIGNATURES:
            variables = ", ".join(FAULT_SIGNATURES[number])
            parts.append(
                f'<p class="sub">Signature variables, from {entry.figure} of the paper: '
                f"<b>{variables}</b>. The Signature button of an instance window ticks exactly "
                "these.</p>"
            )
        if entry.notes:
            parts.append(f'<p class="muted">{entry.notes}</p>')
        if entry.source:
            parts.append(f'<p class="sub"><i>Source: {entry.source}</i></p>')
    parts.append(f'<hr><p class="sub">{SOURCES}</p>')
    return _document("".join(parts))


def variable_page(info: DatasetInfo, figures: "Figures | None" = None) -> str:
    """The variables: where each one is measured and what it is good for."""
    signature_of: dict[str, list[str]] = {}
    for fault, variables in FAULT_SIGNATURES.items():
        for variable in variables:
            signature_of.setdefault(variable, []).append(info.fault_name(fault))

    parts = [
        "<h2>Variables</h2>",
        (
            "<p>Every instance file carries all of these columns, whether or not the well recorded "
            "them, so a column that is entirely missing is normal rather than an error. Readings "
            "are one per second. Pressures are stored in pascal, temperatures in degrees Celsius, "
            "choke openings in percent, flow rates in cubic metres per second; a valve state is "
            "0 closed, 1 open, 0.5 anything else.</p>"
        ),
    ]
    if figures is not None:
        parts.append(figures.html("platform"))
    parts += [
        '<table cellspacing="0" cellpadding="5" width="100%">',
        "<tr><th>Variable</th><th>Where it is measured</th><th>What it is</th></tr>",
    ]
    for name in info.sensor_names:
        entry = VARIABLES.get(name)
        unit = info.unit(name)
        described = info.sensor_descriptions.get(name, "")
        cell = [f"<b>{name}</b>"]
        if unit:
            cell.append(f' <span class="sub">[{unit}]</span>')
        what = []
        if described:
            what.append(described)
        if entry is not None and entry.note:
            what.append(f'<span class="sub">{entry.note}</span>')
        if name in signature_of:
            what.append(
                f'<span class="sub">Signature variable of: {", ".join(signature_of[name])}.</span>'
            )
        where = entry.where if entry is not None else '<span class="muted">not documented</span>'
        parts.append(
            f'<tr><td valign="top">{"".join(cell)}</td>'
            f'<td valign="top" class="sub">{where}</td>'
            f'<td valign="top">{"<br>".join(what) or "&mdash;"}</td></tr>'
        )
    parts.append("</table>")
    parts.append(f'<p class="sub">Source: {PAPER}, tables 2 and 3, and the dataset.ini.</p>')
    return _document("".join(parts))


def state_page() -> str:
    """The well operational status codes drawn in the ``state`` band."""
    parts = [
        "<h2>Well operational status</h2>",
        (
            "<p>The second label of an instance says what was being done to the well, "
            "independently of whether an event was under way. Every status other than Open belongs "
            "to a shut-in procedure, and several of them are the operators' countermeasures "
            "against hydrates. These are the colors of the <b>state</b> band above each time "
            "series.</p>"
        ),
        # '<table cellspacing="0" cellpadding="5" width="100%">',
        # "<tr><th>Status</th><th>What it means</th></tr>",
    ]
    for code, name in WELL_STATES.items():
        parts.append(
            f"<tr>{_swatch(state_color(code), 22)}"
            f'<td valign="top" width="150"><b>{name}</b> <span class="sub">({code})</span></td>'
            f'<td valign="top">{STATES.get(code, "")}</td></tr>'
        )
    parts.append(
        f'<tr>{_swatch(state_color(None), 22)}<td valign="top"><b>Unknown</b></td>'
        '<td valign="top">The condition of the well at that moment could not be established.</td></tr>'
    )
    parts.append("</table>")
    parts.append(f'<p class="sub">Source: {PAPER}, table 5.</p>')
    return _document("".join(parts))


def usage_page() -> str:
    """How to work the two windows, and what the dataset underneath them is."""
    parts = ["<h2>Using the viewer</h2>"]
    for section, lines in USAGE.items():
        parts.append(f"<h3>{section}</h3><ul>")
        parts.extend(f"<li>{line}</li>" for line in lines)
        parts.append("</ul>")
    parts.append("<h2>About the data</h2>")
    for title, text in DATASET_NOTES:
        parts.append(f"<h3>{title}</h3><p>{text}</p>")
    parts.append(f'<hr><p class="sub">Source: {PAPER}</p>')
    return _document("".join(parts))


class HelpWindow(QDialog):
    """Tabbed help on the dataset and on the viewer, shared by both windows."""

    TABS = ("Fault classes", "Variables", "Well status", "Using the viewer")

    def __init__(self, info: DatasetInfo, counts: dict[int, int] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowTitle("3W Overlap Viewer — Help")
        self.resize(1000, 800)

        figures = Figures()
        self._tabs = QTabWidget()
        for title, html in zip(
            self.TABS,
            (
                fault_page(info, counts, figures),
                variable_page(info, figures),
                state_page(),
                usage_page(),
            ),
        ):
            browser = QTextBrowser()
            browser.setOpenExternalLinks(True)
            figures.attach(browser)  # before the html, so the img tags resolve
            browser.setHtml(html)
            self._tabs.addTab(browser, title)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        buttons.accepted.connect(self.close)
        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addWidget(buttons)

    def show_tab(self, title: str) -> None:
        """Raise the window with one tab selected."""
        if title in self.TABS:
            self._tabs.setCurrentIndex(self.TABS.index(title))
        self.show()
        self.raise_()
        self.activateWindow()


def real_instance_counts(catalogue: pd.DataFrame) -> dict[int, int]:
    """Real instances per fault class, for the help window's class table."""
    return {int(k): int(v) for k, v in catalogue["fault_class"].value_counts().items()}
