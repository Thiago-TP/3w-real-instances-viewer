# IDEAS

This file stores a list of ideas that are not yet implemented in this project.
It is meant to be a living document that is updated as new ideas are identified and completed.
At this point, brainstorming is encouraged, so ideas do not need to be fully fleshed out or well-defined.

---

**2026-09-14 Batch**

*Expanding the application's functionality*

The current app is great for supporting well-wise explorations, but is lacking in tools for fault-wise or feature-wise analysis support. 
This is expected, given the initial goal of this project was to check overlap of real instances. 

Now, I'm thinking of expanding it to check real instances more generally, starting with data availability analysis based on [the work of Gabriel Rozo](https://github.com/GabrielRozo123/3W/blob/new_3w_datasets_overviews/dataset/demos/GabrielRozo/main.ipynb) and [Gabriel Rabelo](docs/papers/final_graduation_project_gabriel_rabelo.pdf). 

Should I make this expansion on the current app, or create a new one? If the current, how would the new tools be designed and integrated into the GUI?

> [!NOTE]
> **Answered 2026-09-14: expand the current app, as pages of one main window over the same catalogue.**
>
> *Same app, because the pieces are already here.* The catalogue scan opens every real instance once and caches
> the result, and it rebuilds itself when a newer viewer records more per instance than the cache holds; the
> instance window already measures coverage and flatness per sensor; the theme, palette, legend, help, time
> axis and progress dialog are most of the code and would all be duplicated by a second app. Overlap and
> availability are not independent either: Rozo averages over instances and Rabelo over seconds, so both count
> the samples two overlapping instances share twice, and only this app can count them once, over joined
> recordings. The one cost is the name, which stops describing the tool; it will be changed once the pages
> settle. The focus on the real instances stays.
>
> *How the tools fit the GUI.* The catalogue is one table, and well-wise, fault-wise and feature-wise are three
> groupings of its rows; the timelines are the well-wise one. So the main window became tabs sharing one toolbar
> (Theme, Reset views, Rescan, Help) and one status bar, each page owning the controls that only mean something
> to it. The **Availability** page is one matrix: a column per sensor, a row per group of instances chosen in a
> *Rows* box (fault classes, wells, or the instances of one well or one fault class), a last row folding
> everything shown, and in every cell the share of the group's samples in which the sensor is live, frozen or
> absent. Frozen is told apart from live because a count of non-missing values passes a dead downhole gauge off
> as available, and the `ESTADO-*` valve states are never frozen, only absent or live. Readings outside the
> plausible ranges of the `flowml` pipeline are marked in the corner of a cell and called out, in amber, on the
> plots of the instance window and in the status line of a hovered timeline bar. Hovering a cell, a sensor or a
> row puts the figures behind it in the status bar; clicking a fault class or a well shows its instances one by
> one. The figures come from the parquet footers, in the same scan pass as the labels.
>
> *What came after the first cut is in [TODO.md](TODO.md), all of it shipped after the first cut was
> evaluated:* opening an instance window from a cell with the sensor ticked; the toggles that change the picture
> (cells by samples or by instances, an availability threshold per instance, counting joined recordings once,
> from a pass over the data cached like the catalogue); coloring the timeline bars by the availability of one
> sensor; and the fault-wise page below. The evaluation also asked for the warnings of implausible readings to
> reach the instance plots themselves, and for the availability cells to use the width of a wide window.

*Fault-wise exploration across wells*

The instances of one fault come from many wells, and Rabelo's figures 2.5 and 2.6 make the point by hand: the
same fault, on two wells, has a different magnitude, a different time to install itself and a different baseline.
The **Faults** page picks a fault class and draws every real instance of it, from every well, over the others,
one plot per feature and one line per instance in the color of its well, on a time axis aligned at the onset of
the transient (or of the steady state, for the two faults that have no transient, or the start of the recording),
with the signature variables ticked by default and per-instance normalization as an option, so that the shapes
can be compared where the absolute levels cannot. Shipped 2026-09-14, and rebuilt the same day around **small
multiples** after the overlay was judged unreadable: the aggregate of two dozen traces says how far apart the
levels are and nothing about the shapes, so the default is now one small plot per instance, each on its own
value axis, with its label periods shaded behind the trace. What it still does not do is any statistic across
the instances (a median shape, a spread, a distance between two of them), which would be the first *feature* in
the wider sense of the word.

*Which sensors were recorded together*

A column of the availability matrix says how much of a sensor there is; it cannot say whether two sensors were
ever recorded *at the same instant*, and two of them can each cover half a recording and never overlap. Rabelo's
figure 2.10 measures it, and a model needing two sensors can only be trained where both are there. Shipped
2026-09-14 as the **Sensor pairs** matrix of the availability page; of the 351 pairs of 3W 2.0.0, 102 never
carry a reading at the same instant. What would make it say more is an order that groups the sensors which
co-occur — a seriation, or a clustering of the matrix — so that its blocks read as groups of sensors that live
and die together, which is close to saying which subsets of the dataset a model could actually be built on.

*A view of the cleaned and processed dataset*

In an ideal case the app would also show what a cleaned and processed 3W dataset would look like: plots of the
original-but-sanitized data (histograms, time series, coverage analysis after the cleaning rules are applied) and
of the features extracted from it (statistical moments, frequency-domain features, more histograms). Note that
in this case a *feature* is no longer just a column of the dataframe but any information extracted from them,
which is why the viewer's own vocabulary should keep calling the raw columns *sensors* or *variables*. Kept in
mind for the design of the pages; not to be acted on yet.

---
