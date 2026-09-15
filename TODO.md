# TODO

This file stores a list of tasks that are not yet implemented in this project. 
It is meant to be a living document that is updated as new tasks are identified and completed.
Tasks are categorized into three types: cosmetic, documentational, and feature.
A task is an idea in the [IDEAS.md](IDEAS.md) file that has been deemed worth implementing.

---

**2026-09-14 Batch**

- [x] cosmetic: in side bar in instance plot window,
    - [x] stack buttons "Clear" and "All recorded" vertically to save horizontal space;
    - [x] rename "Signature of {fault class}" to "Signature" to save horizontal space.
- [x] cosmetic: add texture to "Unknown" status colorbox in Help -> Well status for consistency with instance plots.
- [x] documentational: in Help -> Variables, say what position number the sensor occupies relative to the illustration (use the 3W 2.0.0 paper).
- [x] documentational: comment on and illustrate fault signatures (use the 3W 2.0.0 paper).
- [x] feature: a checkbox in the main window that joins instances with overlapping time ranges.
    > [!CAUTION]
    > Join is only valid if there is no labeling disagreement within the overlapping time range,
    > i.e., if the earlier instance has label "X" or "Unknown" (NaN), then the latter instance must have label "X" or "Unknown" as well. 
    > Otherwise, the instances cannot be joined.
    
    > [!TIP]
    > If instances come from different fault folders, but have valid join, 
    > the resulting instance box should present the colors of all its parents. 

---

**2026-09-14 Batch — data availability** (from *Expanding the application's functionality* in [IDEAS.md](IDEAS.md))

The first cut, steps 1 to 3 of the plan, plus the plausibility warnings:

- [x] feature: record, per instance and sensor, how many samples carry a reading and the smallest and largest of them, in the catalogue scan, from the parquet footers (a file without footer statistics is read in full); an older cache is rebuilt on its own.
- [x] feature: the availability model — per instance and sensor, one of three states (absent, frozen, live); groups of instances (fault class, well, instance, everything) folded into shares of samples and counts of instances; readings outside the plausible ranges of the `flowml` pipeline flagged.
    > [!CAUTION]
    > The `ESTADO-*` variables are valve states (fully open, fully closed, in between) and are never *frozen* the way a pressure sensor is:
    > a valve that holds one position for a whole recording is a fact about the well. They are only ever *absent* or *live*.
    > The dataset marks them by writing their "unit" as the list of values they take, which is how the viewer tells them apart.
- [x] feature: the main window becomes pages (Timelines, Availability) under one shared toolbar (Theme, Reset views, Rescan, Help) and over one shared status bar; each page owns its own controls.
- [x] feature: the Availability page — a matrix of stacked-share cells with a *Rows* box (fault classes / wells / instances of one well / instances of one fault class), sensors in dataset order or by coverage, a total row, the figures behind a cell, a sensor or a row in the status bar on hover, and a click on a fault class or a well to see its instances one by one.
- [x] feature: plausible-range warnings, clear but discreet — an amber mark in the corner of a cell, an amber note beside the figures of an instance-window plot and in the tooltip of its feature checkbox, and a note at the end of the status line of a hovered timeline bar.
- [x] documentational: a *Data availability* tab in the help (states, plausible ranges and why, how the shares are counted, what 3W 2.0.0 shows, sources); usage help for the page; README.

The remaining steps, greenlit after the first cut was evaluated:

- [x] feature: clicking an instance cell of the Availability page opens the instance window with that sensor ticked; clicking its label opens it with the default features.
- [x] feature: toggles that change the availability picture — *Cells* by samples (as Rabelo counts) or by instances (as Rozo counts); *Available from*, the share of samples a sensor needs readings in to count as available in an instance (Rabelo's rule at 50 %); *Join overlapping instances*, counting the bars of the joined view as merged recordings, each shared sample once, from a pass over the data that is cached like the catalogue.
- [x] feature: *Bar color: Availability of a sensor* on the Timelines page tints every bar by the share of its samples in which one sensor is live, grey for frozen, empty for absent, with its own key in place of the fault key; the amber corner mark of an implausible reading is drawn on the bars in either coloring.
- [x] feature: the warnings of implausible readings reach the instance plots themselves — the affected samples drawn in amber over the trace, the header of the block naming the sensors, the feature's checkbox wearing a ⚠ — after the caption alone was judged too easy to miss.
- [x] cosmetic: the cells of the Availability page stretch to the width of the window, between a floor and a ceiling, instead of leaving the right of a wide window blank.
- [x] feature: the Faults page — every real instance of one fault, from every well, drawn over the others, one plot per feature, one line per instance in the color of its well, aligned at the onset of the transient (or of the steady state, or the start of the recording), with per-instance z-score normalization, a window of hours around the onset, the signature variables ticked by default, and hover naming the line and reading the instance at that moment.
- [ ] cosmetic: rename the project, whose name no longer describes it; awaiting a name (proposals in the discussion of 2026-09-14). The focus on real instances stays.

---

**2026-09-14 Batch — reading the pages** (raised on reviewing the availability and faults pages)

- [x] cosmetic: hovering an availability cell shows its coverage in a tooltip where the pointer is, after Rozo's heatmap, which writes the figure inside every cell; the sensor headers and the row labels have one too.
- [x] feature: small multiples on the Faults page — one small plot per instance in a grid under a heading per feature, each with its own value axis (or all on one), its label periods shaded behind the trace, and its well and onset in the corner. The default layout, the overlay being kept as the other choice: the aggregate said too little once there were more than a handful of instances.
    > [!TIP]
    > The grid opens on the stretch of time most of the instances cover, not all of it:
    > one instance recorded for days would otherwise leave every other plot a sliver against its left edge.
- [x] feature: coverage per pair of sensors (Rabelo's figure 2.10) as a second matrix of the Availability page — the sensors on both axes, every cell the share of the samples in which both carry a reading at the same instant, over every instance or over one fault class or one well, counting either both-live or both-recorded. The footers cannot answer it, so a data pass reads it once and caches it like the catalogue.

Noticed while building, then acted on:

- [x] feature: *Join overlapping instances* applies to the pair map too — the merged recordings are read pair by pair in the same data pass that reads their sensor figures, so one pass and one cache serve both. Joining changes the answer rather than the arithmetic: a sensor one window missed is filled in by the window it overlaps.
- [x] feature: *Sensors: grouped by co-occurrence*, an order for the pair map that puts the sensors recorded at the same instant together (a spectral seriation on the Fiedler vector of their overlap, numpy only), so that the blocks of the matrix read as the sets of sensors a well carries or lacks together. On 3W 2.0.0 it brings the valve states into one block and sends the four never-recorded sensors to the end.
- [x] cosmetic: the small multiples of the Faults page hatch the stretches nobody labeled, as the bands and the plot backgrounds of the instance window do.

Still open:

- [ ] cosmetic: rename the project, whose name no longer describes it; awaiting a name. The focus on real instances stays.

---
