"""The optional dependency groups: what each enables, what it imports, how it is installed.

The core of the viewer needs numpy, pandas, pyarrow, PySide6 and pyqtgraph, and
nothing else. Everything heavier is declared in ``pyproject.toml`` as an
optional extra, one group per capability, and listed here again with the
import names that prove the group is installed. A feature that needs a group
asks :func:`missing` first: ``None`` means go ahead; a string is the one
sentence to put in the tooltip of the greyed control, naming what is missing
and the command that installs it. Nothing here imports an optional package at
module level, so the viewer starts whether or not the extras are there.

The test suite checks that this table and ``pyproject.toml`` name the same
groups, so that a group cannot be added in one place and forgotten in the
other.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Extra:
    """One optional group.

    ``name`` is the extra as ``pyproject.toml`` and ``uv sync --extra`` know
    it; ``modules`` are the import names that must resolve for the group to
    count as installed (the distribution names differ: ``scikit-learn`` imports
    as ``sklearn``); ``enables`` says, for the README and the tooltips, what
    the viewer does with it.
    """

    name: str
    modules: tuple[str, ...]
    enables: str


EXTRAS: dict[str, Extra] = {
    "analysis": Extra(
        "analysis",
        ("sklearn",),
        "the Instances map (embeddings, clusterings and their scores, the novelty audit) "
        "and the mutual-information matrices",
    ),
    "umap": Extra(
        "umap",
        ("umap",),
        "the UMAP embedding of the Instances map",
    ),
    "dtw": Extra(
        "dtw",
        ("dtaidistance",),
        "the DTW representation of the Instances map: each instance's shape compared with "
        "the others of its class, the 3W Toolkit's rule",
    ),
}

_checked: dict[str, str | None] = {}


def install_command(name: str) -> str:
    """The command that installs one group into the project's environment."""
    return f"uv sync --extra {name}"


def missing(name: str) -> str | None:
    """``None`` when the group imports; otherwise one sentence saying what to install.

    The answer is cached: an import that failed once at start-up would fail
    again, and the controls ask on every rebuild.
    """
    if name not in _checked:
        extra = EXTRAS[name]
        absent = [m for m in extra.modules if not _imports(m)]
        _checked[name] = (
            None
            if not absent
            else (
                f"Needs the optional '{name}' group ({', '.join(absent)}), which enables "
                f"{extra.enables}. Install it with `{install_command(name)}`."
            )
        )
    return _checked[name]


def available(name: str) -> bool:
    """Whether every module of the group imports."""
    return missing(name) is None


def _imports(module: str) -> bool:
    try:
        importlib.import_module(module)
    except ImportError:
        return False
    return True


def forget() -> None:
    """Drop the cached answers, so that a group installed meanwhile is seen (tests)."""
    _checked.clear()
