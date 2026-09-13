"""3W Overlap Viewer: a GUI to inspect how the real instances of a well overlap in time.

The 3W dataset stores one parquet file per instance, and the real instances of
one well are windows cut from the same continuous recording, so they often
overlap in time, and the shared samples then carry two different labels. This
package shows those overlaps: an overview window with one interactive timeline
per well (an interactive version of the ``faults_per_well.pdf`` stage-0 figure
of the ``flowml`` pipeline) and, on click, a window with the time series of an
instance and of every instance it overlaps, on shared axes.

The backend (``dataset``, ``timemap``, ``labels``, ``palette``) needs only
pandas, numpy and pyarrow; the frontend (``items``, ``overview``,
``instance_window``, ``app``) is PySide6 + pyqtgraph.
"""

__version__ = "0.1.0"
