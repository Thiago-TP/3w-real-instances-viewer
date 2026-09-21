"""Installing a theme: Qt's palette, pyqtgraph's configuration, and the saved mode.

One call settles both halves of the viewer's appearance, so that the windows and
the plots inside them can never be painted from two different ideas of what the
background is. ``apply`` also tells Qt which color scheme it is in, which is what
makes the pieces this application does not paint itself — the window frames, the
native folder dialog, the message boxes — follow along.

A mode is ``light``, ``dark``, or ``system`` for the desktop's own choice. The
choice is remembered between runs; ``--theme`` overrides it for one run.
"""

import pyqtgraph as pg
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from overlap_viewer.backend import theme
from overlap_viewer.backend.theme import Theme

SETTINGS = ("overlap-viewer", "3W Overlap Viewer")  # organization, application
THEME_KEY = "appearance/theme"

# Qt's own name for each mode. ``Unknown`` is not a failure: it is what tells Qt
# to stop overriding the desktop and report the scheme the desktop asks for,
# which is exactly what ``system`` means here.
SCHEMES = {"light": Qt.ColorScheme.Light, "dark": Qt.ColorScheme.Dark}


def saved_mode(default: str = "system") -> str:
    """The mode remembered from the last run, or ``default`` if none is."""
    mode = QSettings(*SETTINGS).value(THEME_KEY, default)
    return mode if mode in theme.MODES else default


def save_mode(mode: str) -> None:
    """Remember ``mode`` for the next run."""
    QSettings(*SETTINGS).setValue(THEME_KEY, mode)


def resolve(mode: str) -> str:
    """The theme ``mode`` asks for, after telling Qt which scheme it is in.

    Qt is told first and read back second, because under ``system`` the answer
    is Qt's to give: the override has to be lifted before the desktop's own
    choice shows through again. The scheme is only ever written when it differs
    from the one in force, so that applying a mode the application is already in
    does not announce a change that has not happened.
    """
    app = QApplication.instance()
    if app is None:  # a scripted run without a GUI: nothing to ask
        return mode if mode in theme.THEMES else "light"
    hints = app.styleHints()
    wanted = SCHEMES.get(mode, Qt.ColorScheme.Unknown)
    if hints.colorScheme() != wanted:
        hints.setColorScheme(wanted)
    if mode in theme.THEMES:
        return mode
    return "dark" if hints.colorScheme() == Qt.ColorScheme.Dark else "light"


def qt_palette(colors: Theme) -> QPalette:
    """The window chrome of one theme, as Qt wants it.

    Every role is stated rather than left to the style's own defaults: a palette
    half filled in is how a dark window ends up with the text color of a light
    one, which is the clash this module exists to prevent.
    """
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: colors.window,
        QPalette.ColorRole.WindowText: colors.text,
        QPalette.ColorRole.Base: colors.base,
        QPalette.ColorRole.AlternateBase: colors.alternate_base,
        QPalette.ColorRole.ToolTipBase: colors.tooltip,
        QPalette.ColorRole.ToolTipText: colors.tooltip_text,
        QPalette.ColorRole.Text: colors.text,
        QPalette.ColorRole.Button: colors.button,
        QPalette.ColorRole.ButtonText: colors.text,
        QPalette.ColorRole.BrightText: colors.highlight_text,
        QPalette.ColorRole.Link: colors.link,
        QPalette.ColorRole.LinkVisited: colors.link,
        QPalette.ColorRole.Highlight: colors.highlight,
        QPalette.ColorRole.HighlightedText: colors.highlight_text,
        QPalette.ColorRole.PlaceholderText: colors.faint,
        QPalette.ColorRole.Mid: colors.border,
        QPalette.ColorRole.Midlight: colors.alternate_base,
        QPalette.ColorRole.Dark: colors.border,
        QPalette.ColorRole.Shadow: colors.border,
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.HighlightedText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors.faint))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(colors.alternate_base)
    )
    return palette


def style_sheet(colors: Theme) -> str:
    """The few rules the palette cannot state: separators, frames, tooltip border."""
    return f"""
        QToolTip {{ color: {colors.tooltip_text}; background-color: {colors.tooltip};
                    border: 1px solid {colors.border}; }}
        QToolBar {{ border: none; border-bottom: 1px solid {colors.border}; }}
        QToolBar::separator {{ background-color: {colors.border}; width: 1px; margin: 4px 6px; }}
        QStatusBar::item {{ border: none; }}
        QTabWidget::pane {{ border: 1px solid {colors.border}; }}
    """


def apply(mode: str) -> Theme:
    """Put ``mode`` in force everywhere: Qt, pyqtgraph and the current theme.

    Returns the theme now in force, whose ``name`` says which of the two a
    ``system`` mode resolved to.
    """
    colors = theme.use(resolve(mode))
    pg.setConfigOptions(background=colors.plot_background, foreground=colors.plot_foreground)
    app = QApplication.instance()
    if app is not None:
        app.setPalette(qt_palette(colors))
        app.setStyleSheet(style_sheet(colors))
    return colors
