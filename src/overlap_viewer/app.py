"""Entry point: locate the dataset, catalogue it, open the main window.

Usage
-----
    overlap-viewer [--raw-dir PATH] [--no-cache] [--gap-hours H] [--columns N]
                   [--theme MODE]

The dataset root is taken from ``--raw-dir``, else from the
``FLOWML_RAW_DATA_DIR`` environment variable, else from the usual relative
locations (``../3W/dataset``, ``dataset``); when none holds a dataset, a
folder dialog asks for it.
"""

import argparse
import os
import sys
from pathlib import Path

import pyqtgraph as pg
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from overlap_viewer import __version__
from overlap_viewer.backend import theme
from overlap_viewer.backend.config import DEFAULT_GAP_HOURS, RAW_DIR_CANDIDATES, RAW_DIR_ENV
from overlap_viewer.backend.dataset import DatasetInfo, ScanCancelled
from overlap_viewer.frontend import styling
from overlap_viewer.frontend.loading import catalogue_with_progress
from overlap_viewer.frontend.window import MainWindow


def looks_like_dataset(path: Path) -> bool:
    """Whether ``path`` is the root of a 3W dataset: an ini file or numbered folders."""
    if not path.is_dir():
        return False
    if (path / "dataset.ini").exists():
        return True
    return any(p.is_dir() and p.name.isdigit() for p in path.iterdir())


def resolve_raw_dir(requested: Path | None) -> Path | None:
    """Pick the dataset root from the argument, the environment, the usual places, or a dialog."""
    candidates = []
    if requested is not None:
        candidates.append(Path(requested))
    if os.environ.get(RAW_DIR_ENV):
        candidates.append(Path(os.environ[RAW_DIR_ENV]))
    candidates.extend(RAW_DIR_CANDIDATES)
    for candidate in candidates:
        if looks_like_dataset(candidate):
            return candidate.resolve()
    if requested is not None:
        QMessageBox.critical(
            None, "3W Overlap Viewer", f"{requested} does not look like a 3W dataset root."
        )
    chosen = QFileDialog.getExistingDirectory(
        None, "Select the root of the 3W dataset (the folder holding 0/ … 9/ and dataset.ini)"
    )
    if not chosen:
        return None
    path = Path(chosen)
    if not looks_like_dataset(path):
        QMessageBox.critical(
            None, "3W Overlap Viewer", f"{path} does not look like a 3W dataset root."
        )
        return None
    return path.resolve()


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="overlap-viewer", description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=None, help="root of the 3W dataset")
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="scan every instance instead of using the cached catalogue",
    )
    parser.add_argument(
        "--gap-hours",
        type=float,
        default=DEFAULT_GAP_HOURS,
        help=f"silence that splits a well's recording into two bursts (default: {DEFAULT_GAP_HOURS:g})",
    )
    parser.add_argument(
        "--columns", type=int, default=2, choices=range(1, 5), help="plots per row (default: 2)"
    )
    parser.add_argument(
        "--theme",
        choices=theme.MODES,
        default=None,
        help="color mode of the windows and the plots (default: the last one chosen)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def build_window(args: argparse.Namespace) -> MainWindow | None:
    """Everything up to the main window, for ``main`` and for scripted runs.

    The theme goes in first: pyqtgraph fixes the colors of an item when it is
    built, and the dialogs of the scan are on screen before that.
    """
    mode = args.theme or styling.saved_mode()
    styling.apply(mode)
    raw_dir = resolve_raw_dir(args.raw_dir)
    if raw_dir is None:
        return None
    info = DatasetInfo.load(raw_dir)
    try:
        catalogue = catalogue_with_progress(info, use_cache=not args.no_cache)
    except ScanCancelled:
        return None
    except FileNotFoundError as error:
        QMessageBox.critical(None, "3W Overlap Viewer", str(error))
        return None
    return MainWindow(
        info, catalogue, gap_hours=args.gap_hours, columns=args.columns, theme_mode=mode
    )


def main(argv=None) -> int:
    args = parse_args(argv)
    pg.setConfigOptions(antialias=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setOrganizationName(styling.SETTINGS[0])
    app.setApplicationName(styling.SETTINGS[1])
    app.setStyle("Fusion")  # the one style that honors a palette on every platform
    window = build_window(args)
    if window is None:
        return 1
    window.resize(1500, 950)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
