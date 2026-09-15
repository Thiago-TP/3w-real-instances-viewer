"""3W Overlap Viewer: a GUI to inspect the real instances of the 3W dataset.

The 3W dataset stores one parquet file per instance, and the real instances of
one well are windows cut from the same continuous recording, so they often
overlap in time, and the shared samples then carry two different labels. This
package started as a viewer of those overlaps and is growing into a viewer of
the real instances at large, one page per question: a timelines page with one
interactive timeline per well (an interactive version of the
``faults_per_well.pdf`` stage-0 figure of the ``flowml`` pipeline), an
availability page saying what the sensors of each fault class or well actually
recorded, and, on click, a window with the time series of an instance and of
every instance it overlaps, on shared axes.

The backend (``dataset``, ``availability``, ``timemap``, ``labels``,
``palette``) needs only pandas, numpy and pyarrow; the frontend (``items``,
``heatmap``, ``overview``, ``availability_page``, ``instance_window``,
``window``, ``app``) is PySide6 + pyqtgraph.
"""

__version__ = "0.1.0"
