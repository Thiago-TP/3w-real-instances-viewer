"""Light and dark color schemes: every color one mode paints, plots and windows alike.

The viewer draws in two systems at once. The plots are pyqtgraph's, whose
background and foreground are global configuration read when an item is built;
the windows around them are Qt's, painted from the application palette. Left to
their own defaults the two disagree — white plots inside the dark windows a dark
desktop hands out, each with the text color the other one wanted — so both
halves are settled here, together, as one ``Theme``. A mode is therefore a
single object, and switching is a single call.

``styling`` installs a theme into Qt and into pyqtgraph, ``palette`` combines
the hues below into the colors a bar or a band actually carries, and the widgets
read the current theme as they build.

Every color is a ``#rrggbb`` string and no Qt is imported here, so the backend
and its tests stay free of it.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    """Every color of one mode, from the window chrome down to the fault hues."""

    name: str
    dark: bool

    # -- the windows: what Qt paints, and the three weights of text on it
    window: str
    base: str  # lists, text panes, entry fields
    alternate_base: str
    button: str
    border: str
    text: str
    muted: str  # a summary beside a title, a caption under a panel
    faint: str  # a hint, a disabled entry
    highlight: str
    highlight_text: str
    link: str  # a hyperlink of the help, which sits on ``base`` rather than on ``highlight``
    tooltip: str
    tooltip_text: str

    # -- the plots: what pyqtgraph paints
    plot_background: str  # also what every tint mixes toward; see ``palette.tint``
    plot_foreground: str  # axes, their ticks and their labels
    block_fill: str  # a stretch of recording, behind the bars of a well
    grid_line: str  # the separator between two stack levels
    gap_line: str  # the dashed mark of a collapsed silence
    outline: str  # the heavy edge of a hovered bar
    overlap_hatch: str  # the texture over the stretch two instances share
    crosshair: str
    trace: str  # a time series line; saturated, it sits on tinted shading
    # An unlabeled stretch is a neutral grey under these strokes. The shade
    # alone would read as one more class — two of the fault hues are themselves
    # grey — so the texture, not the color, is what says "nothing is known here".
    hatch: str
    unknown: str
    note_fill: str  # the boxed note pinned in the corner of a plot
    note_border: str
    shared_fills: tuple[str, ...]  # a stretch recorded by two, three, more instances

    # -- the data
    faults: dict[int, str]
    fallback_fault: str  # a folder the palette does not know
    states: dict[int | None, str]
    swatches: dict[str, tuple[str, str, str]]  # legend entry: background, border, text

    def shared_fill(self, count: int) -> str:
        """Fill of a stretch of the coverage band recorded by ``count`` instances.

        Nothing recorded is the plain plotting ground and one instance the
        ordinary recording fill, so the band only starts saying something where
        the instances actually pile up, and says it louder the deeper they do.
        """
        if count <= 0:
            return self.plot_background
        if count == 1:
            return self.block_fill
        return self.shared_fills[min(count - 2, len(self.shared_fills) - 1)]


LIGHT = Theme(
    name="light",
    dark=False,
    window="#f2f2f2",
    base="#ffffff",
    alternate_base="#e9e9e9",
    button="#e8e8e8",
    border="#c4c4c4",
    text="#1a1a1a",
    muted="#555555",
    faint="#8a8a8a",
    highlight="#3d6fa8",
    highlight_text="#ffffff",
    link="#2a6099",
    tooltip="#ffffdc",
    tooltip_text="#1a1a1a",
    plot_background="#ffffff",
    plot_foreground="#1a1a1a",
    block_fill="#f4f4f4",
    grid_line="#dcdcdc",
    gap_line="#9a9a9a",
    outline="#000000",
    overlap_hatch="#000000",
    crosshair="#333333",
    trace="#1f4e79",
    hatch="#8a8a8a",
    unknown="#e9e9e9",
    note_fill="#ffffff",
    note_border="#666666",
    shared_fills=("#9a9a9a", "#6f6f6f", "#444444"),
    # One hue per fault-class folder. Normal is green; the faults get distinct
    # categorical colors.
    faults={
        0: "#4c9e4c",
        1: "#1f77b4",
        2: "#ff7f0e",
        3: "#d62728",
        4: "#9467bd",
        5: "#8c564b",
        6: "#e377c2",
        7: "#7f7f7f",
        8: "#bcbd22",
        9: "#17becf",
    },
    fallback_fault="#555555",
    states={
        None: "#d9d9d9",
        0: "#4c9e4c",
        1: "#d95f5f",
        2: "#c9a227",
        3: "#8f7ee6",
        4: "#5fa8d3",
        5: "#e6a23c",
        6: "#7f8c8d",
        7: "#3fbf9f",
        8: "#d47fb8",
    },
    swatches={
        "plain": ("transparent", "transparent", "#333333"),
        "highlight": ("#e8eef7", "#4a6fa5", "#12305e"),
        "selected": ("#ececec", "#333333", "#000000"),
        "dimmed": ("transparent", "transparent", "#aaaaaa"),
    },
)

# The dark mode is not the light one inverted: the hues are lifted, because a
# categorical palette chosen to read as ink on paper (the browns and the blues
# above all) sinks into a dark ground, and every neutral that was a step toward
# white becomes a step toward black, so that the ladder of tints keeps its
# direction — away from the background the color is drawn on.
DARK = Theme(
    name="dark",
    dark=True,
    window="#232529",
    base="#1a1c1f",
    alternate_base="#26282c",
    button="#2e3136",
    border="#3a3e45",
    text="#e6e8ea",
    muted="#a6abb3",
    faint="#7c828b",
    highlight="#4a7fc1",
    highlight_text="#ffffff",
    link="#7fb3e8",
    tooltip="#2e3136",
    tooltip_text="#e6e8ea",
    plot_background="#16181b",
    plot_foreground="#d6d9dd",
    block_fill="#1e2024",
    grid_line="#34383e",
    gap_line="#6a6f77",
    outline="#ffffff",
    overlap_hatch="#ffffff",
    crosshair="#c8cbd0",
    # Pale rather than merely blue: the trace has to stay visible over the
    # brightest shading a fault can put behind it, which on a dark ground is
    # the top of the range rather than the bottom.
    trace="#d5e6fa",
    hatch="#7c828b",
    unknown="#2b2e33",
    note_fill="#1a1c1f",
    note_border="#5a5f66",
    shared_fills=("#6a6f77", "#8f959d", "#b0b6be"),
    faults={
        0: "#5cb85c",
        1: "#5b9bd5",
        2: "#ff9e3d",
        3: "#ef6f6c",
        4: "#b18fd8",
        5: "#c08d7f",
        6: "#f094d1",
        7: "#adadad",
        8: "#d3d44f",
        9: "#4fd0e0",
    },
    fallback_fault="#9a9a9a",
    states={
        None: "#5b6068",
        0: "#5cb85c",
        1: "#e58080",
        2: "#d6b84a",
        3: "#a596ee",
        4: "#77bde0",
        5: "#edb45f",
        6: "#9aa6a7",
        7: "#57d3b4",
        8: "#e09ac9",
    },
    swatches={
        "plain": ("transparent", "transparent", "#d2d6dc"),
        "highlight": ("#2b3b52", "#6f9ad0", "#cfe2ff"),
        "selected": ("#343840", "#c8ccd4", "#ffffff"),
        "dimmed": ("transparent", "transparent", "#6d727a"),
    },
)

THEMES: dict[str, Theme] = {LIGHT.name: LIGHT, DARK.name: DARK}

# What the user can ask for: a mode, or the desktop's own choice of one.
MODES = ("system", "light", "dark")

# The theme in force. Colors are read wherever a widget is built or painted, in
# every module of the frontend, and threading a theme through all of them would
# put an argument on every signature for something that is global by nature:
# pyqtgraph's background and foreground are global too. It is set once at
# start-up by ``styling.apply`` and again whenever the user picks another mode,
# after which the windows rebuild themselves from it.
_current: Theme = LIGHT


def current() -> Theme:
    """The theme in force."""
    return _current


def use(name: str) -> Theme:
    """Make ``name`` (``light`` or ``dark``) the theme in force, and return it."""
    global _current
    try:
        _current = THEMES[name]
    except KeyError:
        raise ValueError(f"unknown theme {name!r}; expected one of {sorted(THEMES)}") from None
    return _current
