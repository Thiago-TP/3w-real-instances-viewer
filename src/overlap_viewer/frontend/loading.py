"""Loading with feedback: the catalogue behind a progress dialog, instances behind a cache."""

from collections import OrderedDict
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QProgressDialog, QWidget

from overlap_viewer.config import FRAME_CACHE_ROWS
from overlap_viewer.dataset import (
    DatasetInfo,
    JoinedStats,
    PairCounts,
    WellData,
    load_catalogue,
    load_instance,
    load_joined_stats,
    load_pair_counts,
)


class FrameCache:
    """Recently loaded instances, kept while they fit in ``max_rows`` samples.

    Neighbouring instances of a well are usually clicked one after the other,
    and the same file then belongs to several groups; reading a parquet file
    is quick, but not free for the 700,000-sample recordings of some wells.
    """

    def __init__(self, max_rows: int = FRAME_CACHE_ROWS):
        self._max_rows = max_rows
        self._frames: OrderedDict[Path, pd.DataFrame] = OrderedDict()
        self._rows = 0

    def get(self, path: Path) -> pd.DataFrame:
        path = Path(path)
        if path in self._frames:
            self._frames.move_to_end(path)
            return self._frames[path]
        frame = load_instance(path)
        self._frames[path] = frame
        self._rows += len(frame)
        while self._rows > self._max_rows and len(self._frames) > 1:
            _, evicted = self._frames.popitem(last=False)
            self._rows -= len(evicted)
        return frame


def _progress_dialog(text: str, parent: QWidget | None):
    """A cancellable progress dialog and the callback that drives it, for a scan of the files."""
    dialog = QProgressDialog(text, "Cancel", 0, 100, parent)
    dialog.setWindowTitle("3W Overlap Viewer")
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.setMinimumDuration(400)
    dialog.setMinimumWidth(420)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)

    def progress(done: int, total: int, name: str) -> bool:
        dialog.setMaximum(total)
        dialog.setValue(done)
        dialog.setLabelText(f"Reading {name}\n({done} of {total} instances)")
        QApplication.processEvents()
        return not dialog.wasCanceled()

    return dialog, progress


def catalogue_with_progress(
    info: DatasetInfo, use_cache: bool = True, parent: QWidget | None = None
) -> pd.DataFrame:
    """Load the catalogue, showing a cancellable progress dialog if the scan takes long.

    Raises ``dataset.ScanCancelled`` when the user cancels. A catalogue served
    from the cache never shows the dialog.
    """
    dialog, progress = _progress_dialog("Scanning the instances of the dataset…", parent)
    try:
        return load_catalogue(info, use_cache=use_cache, progress=progress)
    finally:
        dialog.close()
        dialog.deleteLater()


def joined_stats_with_progress(
    info: DatasetInfo,
    wells: list[WellData],
    sensors: list[str],
    use_cache: bool = True,
    parent: QWidget | None = None,
) -> JoinedStats:
    """Load the merged figures of every well, behind a progress dialog when the data is read.

    Raises ``dataset.ScanCancelled`` when the user cancels; served from the
    cache, the dialog never shows.
    """
    dialog, progress = _progress_dialog(
        "Reading the overlapping instances as the recordings they were cut from…", parent
    )
    try:
        return load_joined_stats(info, wells, sensors, use_cache=use_cache, progress=progress)
    finally:
        dialog.close()
        dialog.deleteLater()


def pair_counts_with_progress(
    info: DatasetInfo,
    sensors: list[str],
    use_cache: bool = True,
    parent: QWidget | None = None,
) -> PairCounts:
    """Load the pair counts of every instance, behind a progress dialog when the data is read.

    Raises ``dataset.ScanCancelled`` when the user cancels; served from the
    cache, the dialog never shows.
    """
    dialog, progress = _progress_dialog(
        "Reading which sensors carry a reading at the same instant…", parent
    )
    try:
        return load_pair_counts(info, sensors, use_cache=use_cache, progress=progress)
    finally:
        dialog.close()
        dialog.deleteLater()
