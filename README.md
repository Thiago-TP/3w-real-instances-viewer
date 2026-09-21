# 3W Overlap Viewer

A desktop GUI to inspect the **real instances** of the
[Petrobras 3W dataset](https://github.com/petrobras/3W): how the real instances of a well overlap in
time and how their fault labels differ, what their sensors actually recorded, and how the instances
of one fault compare across wells.

3W stores one parquet file per instance. The real instances of a well are windows cut from the
same continuous recording, so many of them overlap: the shared samples enter a dataset twice, and
under two different labels, since the end of one instance is often the start of the next. Before
anything can be done about that, one has to see it. This viewer started as the tool that shows it,
and has grown into a viewer of the real instances at large, one page per question over the same
catalogue.

![Timelines page](docs/assets/overview.png)

## What it shows

**Timelines page** — a grid of plots, one per well. Every real instance recorded on the well is a
bar from its first to its last timestamp; instances that overlap in time are stacked on top of each
other (the row is the *stack level*), so a well recorded twice shows at a glance. The months of
silence between bursts of recording are collapsed to narrow dashed blanks, and the time scale is
uniform everywhere else: a bar's length is a duration and two bars overlap on screen exactly when
the instances overlap in time. Untick *Compress silences* for a true calendar axis.

- **Hover** a bar: it gets a heavy outline, every instance of the well that overlaps it gets a
  lighter one, the stretch they share is hatched, every other bar fades, and the status bar names
  the instance, its fault, how far the fault got, its time span, size, stack level and partners,
  and the sensors, if any, that read outside their plausible range in it. The colors those
  instances carry light up in the key above the grid, and the rest dim, so the color under the
  pointer can be named without leaving the plot.
- **Click** a bar: an instance window opens with the time series of that instance and of every
  instance it overlaps.
- **Click a color in the key**: the grid shows only the wells that recorded that fault. Clicking it
  again, or the button that appears at the right of the page's toolbar, brings every well back.
- **Join overlapping instances** (toolbar checkbox) merges the instances of a well that overlap in
  time into one bar wherever their labels agree on the shared stretch; an unlabeled sample agrees
  with anything. Instances whose labels disagree there stay apart, so what still overlaps after the
  join is exactly the labeling conflicts, and *Wells with overlaps* then lists the wells that have
  one. A bar joined from several fault folders is striped with every folder's color and says how
  many more instances it joins after its timestamp (`+2`); clicking it opens its instances as the
  single continuous recording they were cut from.
- **Bar color: Availability of a sensor** tints every bar by the share of its samples in which the
  chosen sensor is live, faint for a few and full for all, grey for a sensor that never moved,
  empty for one never recorded, so the grid becomes the history of that sensor on every well: an
  era of absence, or a scattering of it. A key of its own takes the place of the fault key while it
  is on; the outline of a bar keeps its fault hue.
- **Bar color: Measurements of a sensor** tints every bar by the share of the sensor's *live*
  samples that were actually measured rather than filled in by the plant's historian (see
  [Measurements, not samples](#measurements-not-samples)), so an era in which a sensor was archived
  every two minutes reads apart from one in which it was read every second. Hover a bar for the
  share and the interval. The first time, it reads every instance in full behind a progress dialog
  and keeps the result in the cache.
- **Bar color: Descriptor of a sensor** tints every bar by one figure of the sensor's series — the
  time its autocorrelation takes to halve, its signal-to-noise ratio, the slope of Zhang's
  Gaussianity regression, its skewness or its kurtosis — ranked among the bars on show, faint for
  the smallest and full for the largest, so the grid shows which recordings of a sensor were slow,
  noisy, heavy-tailed or skewed. The *on* box takes the figure on the 1 Hz grid or on the
  measurements alone; on the grid the key and the hover carry the caveat that the historian's lines
  inflate the first two. Hover a bar for both values and the rank.
- A small **amber triangle** in the corner of a bar marks an instance in which a sensor reads
  outside its plausible range; tinted by one sensor, the mark is for that sensor alone.
- **Retract the key** by clicking its title (or `Ctrl+L`) to give the grid the room. Retracted it
  still answers hovering: the entries of the instance under the pointer, and of the instances it
  overlaps, pop into the title row.
- **Drag** to pan, **Ctrl + wheel** to zoom (the plain wheel scrolls the grid), **right-click** for
  pyqtgraph's menu (view all, export).
- The page's toolbar sets the number of columns, filters the grid to the wells that have overlaps,
  and sorts wells by number, overlapping instances, instances or deepest pile-up. The right end of
  the status bar counts the instances, wells and overlaps on show.

**Availability page** — which sensors the real instances actually recorded. Every instance file
carries every column the dataset declares, whether or not the well had the sensor, so what was
recorded is a question of its own. The **Matrix** box holds two answers.

*Sensor availability* is a column per sensor, a row per group of instances, and in every cell the
share of the group in which the sensor is **live** (readings that move), **frozen** (readings, but
one constant value from end to end) or **absent**, side by side from the left, so that the fuller
the cell, the more of the sensor there is. A last row folds every instance shown. The cells take
the width of the window.

![Availability page](docs/assets/availability.png)

- **Rows** chooses the grouping: the fault classes (the fault-wise view: the availability maps of
  Rozo and of Rabelo's figure 2.8, over every real instance rather than a sample of them), the
  wells (a well-wise view neither has, and four wells hold over half of the real instances), or
  the instances of one well or of one fault class, one row each, in chronological order.
  **Click** a fault class or a well, on its label or on any of its cells, to see its instances one
  by one; **click an instance**, on its label or on a cell, to open its time series with that
  sensor drawn.
- A **tooltip** carries the figure the cell draws, where the pointer is, as a printed availability
  map writes it inside the cell; a cell 34 pixels wide could not hold it, and the status bar is at
  the other end of the window. The sensor headers and the row labels have one too.
- **Sensors** orders the columns as the dataset declares them or *by coverage*, the sensor live in
  the largest share of what is on show first; read along the last row for the feature-wise view.
- **Cells** splits each cell by samples, so that a six-day instance weighs more than a six-hour
  one (as Rabelo counts), or by instances, each weighing the same (as Rozo counts). The two
  disagree because instances range from hours to days.
- **Available from** sets the share of its samples a sensor needs readings in to count as
  available in an instance at all; below it the instance counts as absent for that sensor,
  readings and all. Rabelo's pipeline drops an instance whose P-TPT is more than half missing:
  50 % shows what that rule keeps.
- **Join overlapping instances** counts the bars the timelines draw when joined: overlapping
  instances whose labels agree, read as the single recording they were cut from, in which a
  sample two windows share is counted once and a sensor one window missed is filled in by
  another. The footers of the files cannot say which instants two windows share, so the first
  tick reads the data (about 15 s for 3W 2.0.0, behind a progress dialog) and keeps the result in
  the cache next to the catalogue.
- **Measured vs filled** splits the live share of every cell into the samples that were measured,
  solid, and the samples the historian filled in between measurements, pale — most of every live
  cell on 3W 2.0.0 (see [Measurements, not samples](#measurements-not-samples)). The tooltip and
  the status bar then give the share and the interval between measurements. The split is of
  samples, so it rests while the cells count instances, and it applies to the joined bars as much
  as to the instances, each merged recording profiled as the one series it is. The first tick
  reads every instance in full (about 100 s for 3W 2.0.0, behind a progress dialog) and keeps the
  result in the cache.
- **Hover** a cell: the status bar gives the three shares, how many instances of the row have the
  sensor in each state, the smallest and largest reading, and how many instances read outside the
  plausible range. Hover a sensor's name for what it is and its plausible range, a row's label for
  what the row holds.
- A **frozen** sensor is one whose readings never move, by the same rule the instance window marks
  a plot *flat*: a count of non-missing values alone would pass a dead downhole gauge off as
  available, and in 3W 2.0.0 the downhole pressure is frozen in more than half of the real
  instances. A valve state (the `ESTADO-*` variables) is never frozen: a valve that holds one
  position for a whole recording is a fact about the well, so those variables are only ever absent
  or live.
- A small **amber triangle** in the corner of a cell marks a reading no instrument could have
  produced, in at least one instance of the row: a negative absolute pressure, a temperature
  outside −50 to 250 °C, a magnitude beyond 1e8. The limits are those the `flowml` pipeline masks
  readings by, from its survey of every instance of 3W 2.0.0; the help lists them and says why.
- Without the join, the shares are of samples as the files carry them, so a sensor recorded for
  part of an instance shows as partly absent and a sample two overlapping instances share is
  counted in both. The figures come from the footer of each parquet file (a count of the missing
  values and the minimum and maximum of every column), read in the same pass as the labels and
  cached with the catalogue, so the page costs nothing to open.

*Sensor pairs* puts the sensors on both axes and asks what no column of the first matrix answers:
how often two sensors carry a reading **at the same instant**. Two sensors can each cover half a
recording and never overlap, so a pair can be empty however well covered each of its sensors is,
and a pair with little coverage is one no model can train on and a correlation nobody should
trust. This is Rabelo's figure 2.10. Of the 351 pairs of 3W 2.0.0, 102 never carry a reading at
the same instant.

![Sensor pairs](docs/assets/pairs.png)

- The **diagonal** is each sensor's own coverage. **Over** counts the pairs over every real
  instance, or over those of one fault class or one well. **Count** asks either that both sensors
  be *live* in an instance for it to count, so that a dead instrument and a sensor below the
  availability threshold contribute nothing, or merely that both be *recorded*, frozen readings
  included, which is how Rabelo counts.
- **Sensors: grouped by co-occurrence** lays the sensors out so that those recorded at the same
  instant sit together, and both axes take that order. It is a spectral seriation: sensors are
  placed on a line by the second eigenvector of the Laplacian of their overlap, which puts
  strongly related ones near one another. The blocks of the matrix then read as the sets of
  sensors a well carries or lacks together, and those sets are what say which subsets of the
  dataset a model could be built on at all. *By coverage* ranks them instead, which is the view
  for asking what is best covered.
- **Join overlapping instances** applies here too, and changes the answer rather than merely the
  arithmetic: a sensor one window did not record may be there in the window it overlaps, so two
  sensors that never share a sample inside one window can share plenty inside the recording the
  windows were cut from.
- The footers cannot answer this one: a count of missing values says how much of a column is
  there, not *which* samples are there. So the first look reads the data (about 9 s for 3W 2.0.0,
  behind a progress dialog) and caches the result beside the catalogue.

*Sensor correlations* asks the next question: of two sensors recorded together, how do they move
together? Melo's exploratory methodology (doctoral thesis, section 4.1.5) reads the relations
between variables three ways at once, and the matrix offers the three
([`algorithms/correlation.py`](src/overlap_viewer/algorithms/correlation.py)).

- **Coefficient**: *Pearson*, the linear correlation, blue positive and amber negative, full at ±1,
  exact over every sample of the scope in which both sensors carry a plausible reading, pooled;
  *Mutual information*, Laarne's coefficient √(1 − e⁻²ᴵ) of the mutual information estimated by
  nearest neighbours on an even subsample of a few thousand of the same samples, 0 for
  independent sensors and 1 for a deterministic relation, equal to |Pearson| when the pair is
  jointly Gaussian; *Nonlinear*, Zhang's ρ_I·(1 − |ρ|), what the second says beyond the first. The
  title sums each into Melo's global coefficient (his equations 4.16 and 4.15). A pair with fewer
  than 300 co-valid samples is left blank, and the valve states are left out: a position is not a
  measurement. The two nonlinear coefficients need the `analysis` extra.
- **Smoothing** takes a moving average of 5 s to 5 min before the coefficients, all lengths in one
  pass; the tooltip of a cell gives the Pearson coefficient at every length. Melo's figures 4.11
  and 4.26 show a process's coefficients rising as the window grows, and the historian's lines
  between measurements (below) were his reason to distrust any coefficient taken on the grid. What
  3W 2.0.0 says is more sobering: pooled over a scope, the coefficients hardly move with smoothing
  (the global coefficient of the whole dataset goes from 0.420 to 0.424 between none and five
  minutes), because a pooled coefficient is set by the levels the sensors sit at from one instance
  to the next, not by what happens between two measurements. The lines' spurious dynamics live
  inside one instance, at the scale of seconds, where the Dispersion page looks.
- **Over** is the scope, and it carries the caveat that does bite, stated in the title: pooling the
  instances of a class or of the whole dataset mixes the levels of different wells into the
  coefficient. With every well pooled the mutual-information coefficient of almost every pair reads
  1.00, since knowing one sensor's level is enough to know the well and so the other's; over one
  well (WELL-00007) nearly every pair of pressures and temperatures correlates at ±0.99, through
  the well's shut-ins and restarts. **Join overlapping instances** pools the merged recordings of
  the bars, so that a sample two windows share is counted once. The first look at a scope reads its
  instances behind a progress dialog (about two minutes for the whole dataset); the result is kept
  for the session.

**Faults page** — every real instance of one fault, from every well, side by side. Rabelo's figures
2.5 and 2.6 put two instances of the same fault next to each other to make a point: the same event,
on two wells, has a different magnitude, a different time to install itself and a different
baseline. This page makes that comparison for any fault and every well at once, on a time axis that
starts where the event begins in each instance, so that the shapes line up whatever the clock said.

![Faults page](docs/assets/faults.png)

- **Layout** chooses between the two ways of showing them. *Small multiples*, the default, give
  every instance a plot of its own in a grid under a heading per feature, each with its own value
  axis and its **label periods shaded behind the trace**, hatched where nobody labeled it, so that
  two dozen shapes can be read one against the next and the grid says how long each instance
  stayed in normal operation, in the transient and in the steady state, and how much of it the
  experts left unlabeled. *Overlaid* draws them all on one set of axes, which says how far apart
  the levels are and little else once there are more than a handful — the reason the grid is the
  default.
- **Columns** sets the width of the grid and **Axis** puts every small plot on its own value axis
  or all of them on one. The grid opens on the stretch of time most of the instances cover, so
  that one instance recorded for days does not leave every other plot a sliver against its left
  edge; Ctrl with the wheel zooms out to the rest.
- **Fault** picks the class; **Align at** picks the moment the axis of every instance starts from,
  the onset of the transient, the onset of the steady state, or the start of the recording. An
  instance whose labels never reach the moment chosen cannot be aligned on it and is greyed out in
  the list on the right; the moments come from the label runs the catalogue keeps, so the list
  costs nothing, and only the instances ticked are read from disk.
- **Normalize per instance** scales every series to its own level, each reading as standard
  deviations from the mean of that sensor over the whole instance, which is how Rabelo's pipeline
  normalizes: wells run at different levels, and the shape of the change is what the instances
  share. Readings outside the plausible range are left out before scaling, as the pipelines mask
  them before they normalize. **Show … h before / after** narrows the plots to the hours around the
  onset; at zero, everything recorded is drawn.
- **Hover** a line to bring it forward and name it; the status bar gives the instance, its onset,
  the time under the pointer relative to it, the label and the well status at that moment, and the
  readings of the selected features. Pointing at an instance in the list does the same.
- Beyond two dozen instances the earliest are ticked to start with, and the grid draws at most
  four dozen of them; **All** and **None** and the checkboxes choose. Readings outside the
  plausible range are left out of the value axis, so one broken gauge does not flatten every other
  line; the instance carrying them wears a ⚠ in the list.
- **Features** work as in the instance window: **Signature** ticks the variables the 3W paper puts
  on its example figure of the event, for the five events it illustrates, and features no instance
  of the fault recorded are greyed out.

**Features page** — the faults page with the question turned round. It fixes one **sensor** and
gives every fault class a section, so that what a gauge reads under a hydrate can be set beside
what the same gauge reads under severe slugging and under normal operation. That is the
feature-wise grouping of the catalogue: the timelines are the well-wise one and the faults page the
fault-wise one. The two pages share their whole drawing machinery — the same two layouts, the same
three domains, the same window of hours around an onset, the same transforms and the same hover.

- **Feature** picks the sensor; the count beside a name is how many real instances recorded it, and
  one no instance recorded is greyed out. The page opens on the sensor the most instances record a
  *moving* reading of, which keeps a valve state out of the way of the default: nearly every
  instance carries one, and a valve holding its position for a whole recording would open the page
  on a row of flat lines whose spectrum declines every one of them. **Well** narrows everything to
  one well, so the classes are compared at one place and one set of instruments.
- **The classes on the left** choose the sections and are the color key; **the instances on the
  right** choose what is read from disk. The earliest few of *each* class are ticked to start with,
  rather than the earliest few overall — a class whose instances all come later would otherwise
  open with nothing in its section — and the grid spends its cap per class for the same reason.
- **Layout** means something particular here. *Small multiples* give every instance a plot of its
  own in a grid under a heading per class; because the heading already names the class, the trace
  takes the neutral color and the class hues are left to the shading of the label periods behind it
  and to the stacks of a histogram, which a line of the same hue would vanish into. **Overlaid**
  puts every class on one set of axes, each instance in its class's color — the view the page
  exists for, and the natural one for histograms and spectra, where the question is whether the
  classes sit at different values or peak at different periods.
- **Align at** starts on the start of the recording, the one anchor every class has: normal
  operation has no transient and no steady fault state, so anchoring on either would silently leave
  every normal instance out.

**Instances map** — every real instance as one point, from above. The other pages look at the
instances one well, one fault or one sensor at a time; this one places all of them on a plane by
what their sensors amount to, colors them by class, by well, by cluster, by typicality or by the
verdict of a one-class model, and opens any of them on a click. The unit is the instance, never
the window a pipeline cuts: 1,119 points, which a reader can hold in view. Nothing here is a model
of the process; everything is an analysis of the catalogue, recomputed on every change of a box.

- **Representation** is what an instance becomes a point by. *Descriptors*: per sensor the moments,
  the quantiles, the autocorrelation time, the signal-to-noise ratio, the Gaussianity slope and how
  it was measured (the profile pass of [Measurements, not samples](#measurements-not-samples)),
  one standardized column each; a sensor enters only if it is live in at least half of the points
  (six on 3W 2.0.0), and a cell an instance lacks takes the column's median, the note under the
  map saying how much was made up that way. *Shape only* leaves the levels out, so that the level
  of a well does not place its instances. *DTW of a sensor, within a class* is the 3W Toolkit's
  own comparison of instances, the dynamic time warping distance between the series of one sensor,
  each z-scored and averaged into 400 blocks first (a matter of cost, not the resampling of every
  instance to one length), under a window of a tenth of the length.
- **on** chooses whether the descriptors were taken on the 1 Hz grid, which is what a pipeline
  reads, or on the measurements alone, which is what the process did; on the grid the historian's
  lines make every series look smoother than the process, so the map drawn from the grid is partly
  a map of how each sensor was archived.
- **Embedding** lays the points on the plane: *PCA* (numpy; the axes say how much variance each
  carries, and on a DTW representation it becomes the principal coordinates of the distances),
  *t-SNE* and *UMAP*, which keep neighbourhoods rather than distances and take a few seconds on
  the whole dataset.
- **Clustering** groups the points — k-means, a Gaussian mixture, agglomerative clustering, DBSCAN,
  the list Siqueira's notebooks on 3W work through — and the line beside it scores the result: the
  silhouette, and the agreement with the fault classes and with the wells as the adjusted Rand
  index and the normalised mutual information, 1 for a clustering that is the classes (or the
  wells) under other names. That is the question the page asks: whether what places the instances
  is the event or the well they came from.
- **Typicality** is how ordinary an instance of its class each one is: its distance to the medoid
  of its class in the representation, as a rank inside the class (1 the medoid, 0 the farthest).
  It colors the points, it is a *Bar color* of the Timelines, and it is a *Sort* order of the
  instance lists of the Faults and Features pages, whose tooltips carry it.
- The **label audit** on the right is what a one-class model of the normal instances (a
  radial-basis one-class SVM, as in Siqueira's notebooks, 5 % of the normal instances allowed
  outside its boundary) makes of every label: class by class, the fault instances that *look
  normal* to it and the normal instances that *look anomalous*, each a click away. It is an audit
  of the labels, not a detector; under the *Novelty* coloring the disagreements wear a dark ring.
- **Join overlapping instances** makes the points the bars of the joined view, each merged
  recording profiled as the one series it is; the Timelines take the map's colorings only on the
  view it was drawn on.
- The first time the page is shown it reads every instance in full behind a progress dialog (the
  same pass the availability split uses) and keeps the result in the cache. t-SNE, the
  clusterings, their scores and the one-class model need the `analysis` extra, UMAP the `umap`
  extra, the DTW representation the `dtw` extra; a control whose extra is missing is greyed, and
  its tooltip names the install command.

**Dispersion page** — two sensors against each other, every sample of the instances of a scope one
dot, the density of the samples shaded behind. It is the scatter plot of Melo's exploratory
methodology made readable: his figures of two 3W variables (thesis, section 4.2.5) were where he
saw the historian's hand, the cloud of two interpolated series being the trajectories of the two
interpolations, straight segments between the few instants that were measured. A static scatter
of a million points is a smear; this one names the instance and the instant of every dot on hover,
opens the instance on a click, and thins itself to the measurements alone
([`algorithms/dispersion.py`](src/overlap_viewer/algorithms/dispersion.py),
[`frontend/dispersion_page.py`](src/overlap_viewer/frontend/dispersion_page.py)).

- **X**, **Y** are the two sensors (analog ones; readings outside the plausible range left out) and
  **Over** the scope: every real instance, one fault class or one well, the joined bars with **Join
  overlapping instances**. The first look at a scope reads its instances in full behind a progress
  dialog, every analog sensor at once, and keeps an even subsample of the rows for the session,
  400,000 in all (one row in a few for one well, one in fifty for the whole dataset, which takes
  about two minutes), so that everything else is instant; at most 150,000 of them are drawn as
  dots, evenly, and the **density** behind the dots, a two-dimensional histogram on a logarithmic
  scale, counts them all.
- **Color by** colors the dots by fault class, by well or by label period, or shows the density
  alone; **Label periods** switches the samples of normal operation, the transient, the steady
  state and the unlabeled on and off, so that a fault's steady state alone shows the relation under
  the fault and normal operation alone the relation it departs from.
- **Measurements only** keeps the samples at which both sensors were actually read, a few per cent
  of the dots, from which the historian's straight trajectories vanish. It carries a caveat of its
  own: a historian archives a reading when it has moved enough, so the instants at which both
  sensors were archived are instants at which both moved, and this cloud favours the relation
  between them — over the severe-slugging instances P-TPT × T-TPT reads +0.40 on every sample and
  +0.95 on the 5 % at which both were measured. **Smoothing** applies a moving average of 5 s to
  5 min to both series first, which is what a pipeline's smoothing does to the cloud (and reads the
  scope again, once per window). The caption gives the counts, one in how many, and the Pearson
  coefficient over the samples on show, so that the cloud and the correlation matrix can be read
  against each other: no pooled coefficient betrays the lines, every scatter plot does.
- **Hover** a dot for its instance, its instant, its label period, its two readings and whether
  each was measured or filled in; the status bar also counts the samples in the density cell under
  the pointer. **Click** a dot to open its instance. Pooling wells carries its usual caveat: two
  clouds side by side may be two wells rather than one relation, and *Color by: Well* tells them
  apart.

**Instance window** — one block per bar of the timelines, stacked chronologically on a shared time
axis, so the overlapping stretches line up vertically. Each block has a header line, the well
operational status (`state`) and the label (`class`) as thin bands, then one plot per selected
feature. A band at the top marks the stretches recorded by two or more of the bars shown.

![Instance window](docs/assets/instance_window.png)

- A **joined bar opens as one block**: its instances are read as the single continuous recording
  they were cut from, drawn as one series over one set of bands, with a dashed line where each
  further instance begins. Every instant appears once, and what one window says nothing about the
  others fill in — a sensor it did not record, or a sample its experts left unlabeled. The `class`
  band of a merged recording therefore carries far less *Unknown* than its instances did apart: on
  the largest join of 3W 2.0.0, seventy-one windows over six days, 1.6 % of the samples against a
  third of the samples the windows carried separately. That matters because unlabeled samples are
  dropped, so the merged recording is what a model would actually be trained on. Each stretch keeps
  the color of the file that labeled it, so a normal period labeled by a *Normal Operation* file
  stays green inside a recording that goes on to develop a fault. Stacked slices also become
  unreadably thin long before seventy of them; one block does not.
- **Join overlapping instances** is also a checkbox in this window's own toolbar, and **the group a
  window opens on is all it is ever about**: the box merges exactly the instances on screen, so it
  answers what this group alone amounts to rather than what the whole well does. Two of them that
  overlap only through an instance outside the window therefore stay apart, and nothing is ever
  brought in. It changes this window and nothing else, neither the grid nor any other instance
  window, and turning it off lands exactly where it started, feature selection included. A window
  opened from a bar the timelines had already merged is showing that merge and has nothing of its
  own left to do, so its box is ticked and disabled; a group with nothing to merge disables it too,
  and says which case it is.
- **Features** are chosen with the checkboxes on the left (features none of the instances recorded
  are greyed out). By default only the first feature in alphabetical order among the recorded ones
  is plotted; opened from the availability page, the sensor clicked is.
- **Signature** ticks, in one click, the handful of variables whose joint behaviour identifies the
  event — the ones the 3W paper puts on its example figures. Only the five events it illustrates
  have one (Normal Operation, Spurious Closure of DHSV, Severe Slugging, Quick Restriction in PCK,
  Hydrate in Production Line); for any other the box is disabled and says why. The screenshot above
  is the severe-slugging signature: four variables cycling in phase, as figure 6 of the paper
  describes.
- All plots **share the time axis**, and the plots of one feature **share their value axis** across
  instances, so the same reading is at the same height everywhere.
- A **crosshair** follows the pointer through every plot; the status bar gives the time under it and,
  per instance, the label, the operational status and the selected readings at that time.
- Each plot reports the total variation of the signal (Δ = max − min, marked *flat* for a frozen
  sensor), the share of samples carrying a reading, and how the sensor was measured: the share of
  its readings that are measurements and the interval between them. A sensor never moving is held
  on a padded axis instead of being autoscaled into noise.
- Every trace draws its **measurements as dots**, with the line through every sample faint
  beneath them; between two dots that line is exactly the straight line the historian drew, so
  dense dots are a sensor read every second and sparse dots on a faint line a sensor read every
  two minutes and filled in between. A valve state is not tested and keeps its plain line, and so
  does a sensor measured at every sample. The Faults and Features pages draw their traces the
  same way, in the color of the series.
- A **reading outside the plausible range** is drawn in amber over the trace, sample by sample, so
  the stretch that is garbage is seen for what it is; the panel's figures call it out, the header
  of the block names the sensors, and the feature's checkbox wears a ⚠.

**Signal views** — two more views of every feature plot of the instance window, each placed
where it shares an axis with the trace, and a *Domain* box on the Faults and Features pages that
draws every instance in one of them. The events are slow: severe slugging on WELL-00014 cycles every
50 to 90 minutes, flow instability on WELL-00001 every 45, so a six-hour instance holds four to
seven cycles, and the spectral axis is a **period**, logarithmic, not a frequency that would read
0.0002 Hz.

![Signal views](docs/assets/signal_views.png)

- **Distribution** is a marginal histogram to the right of the trace, turned on its side so its
  value axis is the trace's; the bars are stacked by label period in the class colors, so how the
  event moves the readings is read inside one instance, and a solid line marks the mean, a dashed
  one the median. A bimodal shape is an oscillation.
- **Spectrum** is Welch's estimate of the power spectral density against period, both logarithmic,
  the mean and the linear trend removed first and the missing samples interpolated, readings
  outside the plausible range left out. It takes a row under the trace, the period along the
  bottom. Its caption gives the **dominant period and its share of the power**: a few percent for a
  normal instance, half or more for an oscillating one; and one cycle of that period is laid as a
  bar against the trace, so the claim can be checked against the waves.
- Both are counted over the **stretch of time on screen**, so zooming is brushing. A merged
  recording is transformed as the single series it is, never stitched from its parts.

There was a third view, a **spectrogram** under each trace on the shared time axis. It was dropped:
it earned its place only over a merged recording of days, where the slugging period drifts, and
everywhere else it said what the spectrum already said while taking a row of its own from every
feature of every block — which is the scarce thing in a window that stacks them.
- **Plausible only**, beside *Bins*, is what every histogram counts by default: the readings inside
  the plausible range of the `flowml` pipeline. That is what a histogram is normally asked for —
  one gauge reporting 10¹² Pa would otherwise put every genuine reading into the first bin — but it
  hides the very thing a data review is looking for, so unticking it counts the garbage too, on an
  amber ground beyond the range, with the caption saying how many were *counted* rather than how
  many were left out. The one tick serves the marginal of an instance window, the *Distribution*
  domain of the faults page and the features page. Spectra are not affected: interpolating over a
  spike of 10¹² gives the spectrum of the spike, not of the signal, so they always mask it.
- **Measurements only**, beside it, counts and transforms the measurements alone, leaving out the
  samples the historian filled in between them. A histogram then counts what was read, and says
  so in its caption; a spectrum becomes the **Lomb–Scargle periodogram** of the readings at their
  own instants, which fits a sinusoid of each period to them by least squares and needs no grid —
  the honest spectrum of a series read every ten seconds or every two minutes, where a transform
  of the 1 Hz grid is a transform of the historian's lines. Its caption gives the share of the
  variance a sinusoid of the peak period explains and how many measurements it was taken over;
  the periods run from twice the typical interval between measurements up to the stretch; and it
  is scaled so that it integrates to the variance of the measurements, as a density does, so it
  sits on the axis Welch's estimate would and pools with it band by band under *Overall*. The one
  tick serves the instance window, the Faults page and the Features page.
- **Segment**, **Overlap**, **Window** and **Bins** are the parameters, the same widgets in both
  windows, on a toolbar row of their own so that a narrow window never hides them. Nothing longer
  than a segment can be resolved, so the plots grey the periods beyond it; with *whole stretch*
  ticked the spectrum is the periodogram of everything on screen, the only way to see a slugging
  line, since a segment of a few minutes holds no cycle of it.
- On the **Faults page**, *Overlaid* spectra read together where overlaid traces did not, the
  question being whether their peaks line up; **Overall** pools instead of overlaying — on the
  Faults page into one curve per feature across every well, on the Features page into one curve
  per fault class, which is the feature-level histogram this was built for. A distribution pools
  by putting the readings together; a spectrum never pools by concatenation, since a transform
  reads consecutive samples as one second apart and the months between two instances would become
  a step, so the estimates are averaged band by band on a shared period axis, as Welch's method
  already does one level down. **Join overlapping**, beside it, first reads the windows of a well
  that overlap as the single recording they were cut from, so the samples two windows share are
  counted once instead of twice — which otherwise inflates a pooled histogram at exactly the
  levels that well was recorded twice at. Overall is offered off the time axis only: instances
  cut from different months have no common clock. Histograms are drawn as a share of each
  instance's
  samples — stacked bars in the grid, a filled area in the series color when overlaid, so that
  where two distributions sit on top of one another reads as a deeper shade — with the mean and
  the median of each as lines in the grid and a **triangle over the fullest bin** of each in
  either layout — the value that instance spends most of its time at,
  which the mean and the median both miss once a fault has skewed the readings or split them in
  two, and which hovering the curve reads out — and *Normalize per instance*
  puts different wells on one z-score axis. The hours before and after the onset pick the stretch
  transformed, so "2 h after" gives the spectrum of the fault alone — which is the only way *Align
  at* reaches these two domains, nothing being drawn against the hours from the onset, so with both
  hour boxes at *all* the box is greyed and comes back as soon as hours are asked for. **Features**
  and
  **Instances**, at the right end of the toolbar, hide the feature panel and the instance list to
  give the plots their width; the instance window has the same **Features** toggle beside *Join
  overlapping instances*.

![Spectra of every severe slugging instance](docs/assets/faults_spectra.png)

There is deliberately no phase spectrum of a single signal (its phase depends on where the file
begins and tells nothing the trace does not) and no wavelet transform; the cross-spectrum phase
between two sensors, and any other view of how a period moves along a recording, are left for a
later version.

The pages are interactive counterparts of stage-0 figures of the `flowml` pipeline: the timelines
of `faults_per_well.pdf` and `fault_<n>_real_instances.pdf`, the availability page of the cleaning
rules the pipeline applies before anything is computed, the faults page of the per-fault figures.

**Help** (`F1` anywhere) explains what is on screen, from the 3W papers in
[`docs/papers/`](docs/papers): every class label and what the literature says it does to the
readings, with the example figure of the 2.0.0 paper reproduced and commented for each of the five
events it illustrates; every variable, where in the production system it is measured and the
position number that marks its sensor in the paper's schematic; every well operational status, the
unknown one hatched as the bands hatch it; the three states of the availability page, the plausible
ranges and why they are what they are; and how to work the pages and the windows. Two schematics
of the production system illustrate it. Where the papers describe no signature for an event, the
help says so rather than inventing one.

![Help window](docs/assets/help.png)

## Measurements, not samples

The dataset is sampled once a second, but the sensors were not read once a second. Afrânio Melo
noticed it on the normal instances of WELL-00001 (doctoral thesis, section 4.2.5, in
[`docs/papers/`](docs/papers)): the readings sit on straight lines between a few extremes, the
plant's PI historian having interpolated linearly between the values it archived, and the scatter
plot of two such series shows trajectories that are nothing but the ups and downs of two
interpolations — spurious dynamics and spurious correlations, an impediment to the exploratory
analysis he set out to do, so he stopped there. The viewer takes the direct route he considered
too uncertain to take on the whole dataset: a straight line is a run of samples whose first
difference is constant.

The rule ([`algorithms/interpolation.py`](src/overlap_viewer/algorithms/interpolation.py)): a
sample equal to the one before it is **held**; a sample collinear with both its neighbours, with a
non-zero slope, is **interpolated**; everything else — the ends of every line and the first of
every held run — is a **measurement**, one per value the historian archived. Interpolated and held
together are *filled*. Collinearity needs a tolerance, and the data says which: on the real files
the second differences along a ramp sit in a clean band at 10⁻⁷ to 10⁻⁶ of the reading (the
interpolation was evidently done in single precision; every pressure value is exactly
representable as a 32-bit float) while genuine changes of slope sit at 10⁻⁴ and above, so the
tolerance is one part in a million of the largest reading, in the gap. Exact equality catches only
a third of the ramps. What the test cannot decide it counts as filled — a quantized sensor that
repeats a value for three seconds, or climbs one step a second, draws the very lines the historian
does — and the valve states are not tested at all.

On 3W 2.0.0 the finding is stark. Over every live analog sensor of every real instance, **6 % of
the samples are measurements**, 55 % are interpolated and 39 % held; the median interval between
two measurements is 33 s. Where they are live, P-MON-CKP is read every 12 s, P-PDG every 13 s,
T-TPT every 16 s, QGL every 21 s, P-TPT every 100 s, T-JUS-CKP every two minutes and P-ANULAR
every four. Every figure taken on the 1 Hz grid inherits the lines: the signal-to-noise ratio of
T-JUS-CKP is 36,000 on the grid and 1.5 on its measurements, and its autocorrelation takes seven
minutes to halve on the grid against 73 s on the measurements. The pass that finds this
([`backend/profiles.py`](src/overlap_viewer/backend/profiles.py)) reads every file in full once,
about 100 s for the whole dataset, and keeps the result in the cache; it profiles every sensor of
every instance and of every bar of the joined view as the merged recording it is, and computes the
descriptors of each ([`algorithms/descriptors.py`](src/overlap_viewer/algorithms/descriptors.py):
moments, quantiles, autocorrelation time, signal-to-noise ratio, Gaussianity, Melo's own set) both
on the grid and on the measurements alone, so that wherever a figure taken on the grid is shown
the viewer can say so.

The measurements show in four places: as dots on every trace, in the *Measured vs filled* split of
the availability page, in the Timelines' *Bar color: Measurements of a sensor*, and under the
*Measurements only* tick of the signal views, where the spectrum becomes a Lomb–Scargle
periodogram of the readings at their own instants.

The descriptors travel as columns of the catalogue. *Bar color: Descriptor of a sensor*, on the
Timelines, tints every bar by the autocorrelation time, the signal-to-noise ratio, the Gaussianity
slope, the skewness or the kurtosis of one sensor, ranked among the bars on show; *Sort*, above the
instance lists of the Faults and Features pages, orders the instances by the same figures of the
feature on show, largest first, the tooltip of every instance carrying both the grid's and the
measurements' value. Each has an *on* box choosing the grid or the measurements, and on the grid
the key, the hover and the tooltip carry the caveat that the historian's lines inflate the first
two: on 3W 2.0.0 the autocorrelation time of T-JUS-CKP is 444 s on the grid and 73 s on the
measurements.

## The 3W Toolkit

The viewer meets the [3W Toolkit](https://github.com/petrobras/3W) in two places, by rule and by
file.

**By rule.** The Toolkit's preprocessing step `CleanSignals` decides, per instance and per sensor,
whether a signal is to be believed: fitted on the dataset, it puts bounds at the quartiles of the
instances' means and spreads, three interquartile ranges out on either side, discards the sensor
in an instance whose mean or spread falls outside them (a spread below 1e-6 always fails), drops a
sensor entirely missing in 60 % or more of the instances, and leaves the valve states alone. The
profile pass holds exactly what the rule needs, so the viewer applies it at no cost
([`algorithms/cleaning.py`](src/overlap_viewer/algorithms/cleaning.py)) and lets its thresholds
move: *Toolkit's CleanSignals*, on the Availability page, marks every cell in which the rule would
discard the sensor in at least one instance of the row with a slash, greys the columns it would
drop, and says in the tooltip how many and which bound; the *IQR ×* and *drop if missing in* boxes
move the thresholds; the rule is fitted afresh on the joined bars when the view is joined. The
Timelines offer *Bar color: Sensors the Toolkit's CleanSignals keeps*, every bar tinted by the
share of its live sensors the rule keeps, hovering it naming what the rule discards and why. The
header of every block of an instance window names the sensors the rule would discard in it, once
the rule has been fitted anywhere. One difference is kept on purpose: the profiles describe the
plausible readings, so a sensor whose readings are instrument garbage is not discarded here by a
mean of 10⁴² — it wears the amber mark instead, which says more.

**By file.** *Export file list…*, in the main toolbar, writes the instances the current page has on
show — the wells filtered on the Timelines, the rows of the Availability page, the instances ticked
on the Faults and Features pages, the points of the Instances map, a joined bar as its instances —
as the JSON of a Toolkit `ParquetDatasetConfig` with `split="list"`, each file a path relative to
the dataset root, which the Toolkit loads with `ParquetDatasetConfig(**json.load(open(path)))`;
its provenance is written beside it. [`scripts/export_file_list.py`](scripts/export_file_list.py)
writes the same from the command line, by fault class and by well, and
[`examples/`](examples/README.md) holds one it produced, the severe-slugging instances of
WELL-00014, with its provenance.

**What cannot come back.** The Toolkit's `ModelAssessment` exports `predictions_<timestamp>.csv`
with the columns `true_values`, `predictions`, `model_name`, `task_type` and `timestamp`: one row
per window the model scored, in the order the windows were fed, with no instance and no instant in
it. Nothing in that file says which file, let alone which second, a prediction belongs to, so the
viewer cannot draw it onto the data. The viewer's own model-output format (next section) is what
such an export would have to carry.

## Model outputs

The viewer displays what a model said; it does not train one. For a model's verdicts to be drawn
onto the data, every verdict has to say which instance and which instant it is about, so the viewer
defines the format itself ([`backend/model_outputs.py`](src/overlap_viewer/backend/model_outputs.py)),
the smallest one that says both, and ships an example of it with its provenance written down.

**The format** is a folder: `model.json` beside one `<fault_class>/<instance>.parquet` per instance
scored, laid out as the dataset is. `model.json` holds `name`; `kind`, `"detection"` for a model
that says *anomalous or not* and `"classification"` for one that names the event by its 3W class
number; `labels`, the meaning of every label value the files carry; a `description`; and
`provenance`, who produced the outputs, with what script and parameters, on which dataset version,
when. Each parquet file has the `timestamp` of every sample scored as its index, an integer `label`
column and, optionally, a float `score` column. A model need not score every sample, nor every
instance.

**Agreement** is measured against the experts' `class` labels over the stretches where both said
something: a detection model agrees where it says *anomalous* and the label is a fault (transient or
steady) and where it says *normal* and the label is 0; a classification model where its class equals
the fault the label names. The share of the compared time in agreement is the instance's agreement,
computed from the label runs the catalogue already holds, so loading a set of outputs costs only
reading them.

**Where it shows.** *Load model outputs…*, in the main toolbar, opens a folder in the format. Then:
a third band, *model*, under the class band of every instance window, plain where the verdict
agrees with the label under it and **amber where it disagrees**, the header of the block giving the
agreement; *Bar color: Agreement with the model outputs* on the Timelines; *Color by: Model
agreement* on the Instances map; *Sort: Agreement with the model outputs* and *Shade by: Model
outputs* on the Faults and Features pages, the latter shading the label periods behind the small
plots with the model's verdicts in the dataset's own vocabulary (a detector's *anomalous* as the
instance's own fault), so that where the two differ is seen against the trace.

**The example.** [`examples/model_outputs/pca_control_chart_well7`](examples/README.md) holds the
outputs of a PCA control chart over the twelve real instances of WELL-00007: one model fitted on the
well's two Normal Operation instances over the ten analog sensors live in both, Hotelling's T² and
Q followed along every instance of the well, a sample called anomalous beyond the 99th percentile
of either statistic over the training samples. It was produced by
[`scripts/pca_control_chart.py`](scripts/pca_control_chart.py), whose command, parameters and
fitted limits are in the example's `model.json`; on WELL-00007 it agrees with the labels 98 % of
the time on the normal instances and 100 % on the ten severe-slugging ones. It is one producer of
the format among many — the U-Net segmentation of Lopes *et al.*, the Toolkit's own models with an
export that carries the instance and the instant, a hand-labeled review — and the model itself is
not built into the viewer: its outputs are stored and shown.

## Color code

A bar's hue is the **fault-class folder** the instance comes from, and its tint says how far the
fault developed inside that window: full strength once the steady fault state is labeled, lighter
when only the transient state is, lightest when the window never leaves normal operation (43 of the
instances filed under *Hydrate in Service Line* never do). Normal instances (folder 0) stay full
strength. The legend above the grid keys every color actually drawn, one swatch per fault and
reach.

In the instance window the `class` band carries these exact colors (a normal stretch of a fault
instance has the *no fault reached* tint of that fault, a transient stretch the *transient* tint,
and so on), and the plot backgrounds use the same hues on the same three-step ladder, compressed
toward white so the trace stays legible. Unlabeled stretches are grey; the `state` band uses one
color per operational status.

A fault that appears at several tints is a gradient, and its steps are only readable side by side,
so the key gives such a group a row of its own; faults that draw a single color flow together on
the remaining rows, on a fixed column pitch so that entries line up down the rows.

Stretches the experts left unlabeled are hatched rather than merely grey: two of the fault hues are
themselves grey, and a texture says *nothing is known here* where one more shade would just read as
one more class.

With *Join overlapping instances* ticked a bar may stand for several instances. When they come from
different folders the bar is striped with every color they had, top to bottom in the order of the
key, so each stripe is still a color the key names; its outline is the hue of the event the joined
labels develop furthest, and hovering it lights up every one of its entries in the key.

The availability page has three colors of its own, keyed at the right of its title line: a slate
blue for *live* that no fault hue comes close to, so a cell can never be read as a class; a grey
under a flat line for *frozen*, the line saying what the color alone would not; and the empty cell
for *absent*. With *Measured vs filled* on, the live span of a cell ends in a paler blue for the
samples the historian filled in, the solid part being the measurements. The timelines take the
same colors when they are tinted by a sensor, the blue on a ramp from faint to full with the share
of samples live, or with the share of the live samples that were measured. Amber, used nowhere else, marks a reading
outside the plausible range, wherever it appears: the corner of a cell or a bar, the samples of a
trace, the caption and the header of an instance plot, the checkbox of a feature. The rows of the
fault classes and of the instances carry the fault hue of the timelines as a small square before
their label.

The faults page colors its lines by **well**, from a palette of twelve that no other page uses,
fixed per well over the whole catalogue so that a well keeps its color from one fault to the next,
and cycled only when the dataset holds more wells than the palette has colors; the list on the
right is its key. The well code and the fault code are drawn in the same plot — a trace over the
shading of its label periods, the outline of a histogram over stacks in the fault's own hue — so
they are separated by **register** rather than by hue, which ten fault hues leave no room for.
Every well color sits on the far side of every fault hue in luminance: deeper than all of them in
the light mode, paler than all of them in the dark one. That is the band the trace color already
keeps to, and for the same reason — a line has to stay legible over every shading it can be drawn
on.

## Light and dark

The **Theme** box of the toolbar switches both halves of the viewer at once — the windows Qt paints
and the plots pyqtgraph paints — so they can never disagree; *System* follows the desktop, and
follows it live. The choice is remembered between runs, and `--theme light|dark|system` overrides it
for one run.

The dark mode is not the light one inverted. The fault hues are lifted, because a categorical
palette chosen to read as ink on paper sinks into a dark ground, and the ladder of tints mixes
toward the plotting background of the mode rather than always toward white, so that a weaker tint
always means less of the hue and more of the ground, whichever way round the two are. The trace of a
time series crosses to the other end of the scale for the same reason: dark on the pale shading of
the light mode, pale on the dark shading of the other. Every color of a mode is stated in one place,
[`theme.py`](src/overlap_viewer/backend/theme.py), and the windows rebuild from it when the mode changes.

## Running

Requires Python 3.11 or newer, [uv](https://docs.astral.sh/uv/) and a local copy of the 3W dataset.

```bash
cd app                     # this directory
uv sync                    # creates .venv with PySide6, pyqtgraph, pandas, numpy, pyarrow
uv run overlap-viewer --raw-dir /path/to/3W/dataset
```

From the root of the `flow-assurance-ml` repository the same is `uv run --project app overlap-viewer`.
Without `--raw-dir`, the dataset is taken from the `FLOWML_RAW_DATA_DIR` environment variable, then
from `../3W/dataset`, `dataset` or `3W/dataset` relative to the working directory; if none holds a
dataset, a folder dialog asks for it. `uv run main.py` and `uv run python -m overlap_viewer` are
equivalent entry points.

| Option | Default | Meaning |
| ------ | ------- | ------- |
| `--raw-dir PATH` | see above | root of the 3W dataset (the folder holding `0/` … `9/` and `dataset.ini`) |
| `--columns N` | 2 | plots per row of the timelines (1 to 4) |
| `--gap-hours H` | 12 | a silence at least this long splits a well's recording into two bursts |
| `--theme MODE` | the last one chosen | `light`, `dark`, or `system` to follow the desktop |
| `--no-cache` | off | read every instance again instead of using the cached catalogue |

The first launch reads the time span and labels of every real instance, and what every sensor
recorded from the footer of each file (about 7 s for the 1,119 instances of 3W 2.0.0, behind a
progress dialog), and caches the result under the platform cache directory
(`~/.cache/overlap-viewer/` on Linux). Later launches validate the cache against the files' sizes
and modification times and start instantly; any changed, added or removed file triggers a fresh
scan, as does the *Rescan dataset* button, and so does a version of the viewer that records more
about each instance than the cache holds (the label runs the join reads, and the sensor figures the
availability page reads, were added this way). Three figures the footers cannot give are read from
the data the first time they are asked for, each behind its own progress dialog and cached the same
way: the merged figures the availability page's join needs, sensor by sensor and pair by pair, in
one pass (about 30 s); the pair counts of the instances as the dataset stores them (about 9 s); and
the profiles of every sensor of every instance and bar — which samples are measurements, and what
each sensor amounts to — which read every file in full (about 100 s). A pass one page has paid for
is shared with every other.

Only real instances (`WELL-*` files) are shown: simulated and hand-drawn instances have no well to
overlap on and no sensor to lack, and this viewer is about the real ones.

### Optional extras

The core of the viewer needs numpy, pandas, pyarrow, PySide6 and pyqtgraph, and nothing else.
The heavier analyses are grouped into optional extras, one per capability, so that a plain
`uv sync` stays light. A control whose group is not installed is greyed, and its tooltip names the
group and the command that installs it; nothing else changes.

| Group | Installs | Enables |
| ----- | -------- | ------- |
| `analysis` | scikit-learn | the Instances map (embeddings, clusterings and their scores, the novelty audit) and the mutual-information matrices |
| `umap` | umap-learn | the UMAP embedding of the Instances map |
| `dtw` | dtaidistance | the DTW representation of the Instances map: each instance's shape compared with the others of its class, the 3W Toolkit's rule |

```bash
uv sync --extra analysis           # one group
uv sync --all-extras               # every group
```

The table lives in [`backend/extras.py`](src/overlap_viewer/backend/extras.py) as well as in
`pyproject.toml`, and the tests check that the two agree.

## Layout

```
app/
├── pyproject.toml            standalone uv project (package overlap_viewer, script overlap-viewer, the optional extras)
├── main.py                   runs the viewer from a checkout without installing
├── docs/
│   ├── assets/               screenshots · the platform schematics the help shows
│   └── papers/               the 3W data articles, the thesis and the graduation project the help draws on
├── examples/                 one explained example of every file the viewer reads or writes, with its provenance
├── scripts/                  what produces the examples, outside the GUI: export_file_list.py, pca_control_chart.py
├── tests/
│   ├── conftest.py           the synthetic miniature of the 3W layout every test module shares
│   ├── test_backend.py       tests of the backend
│   ├── test_algorithms.py    tests of the algorithms, on series with known answers
│   ├── test_profiles.py      tests of the profile pass and of the measured/filled split
│   ├── test_map.py           tests of the Instances map's analyses, on planted clouds
│   ├── test_cleaning.py      tests of the Toolkit's CleanSignals rule and of the file-list export
│   ├── test_model_outputs.py tests of the model-output format, its loader and the agreement figure
│   ├── test_correlation.py   tests of the correlation matrices: Pearson exact over pooled samples, the mutual-information coefficient, smoothing
│   └── test_dispersion.py    tests of the dispersion pass: the subsample, the label periods, the measurements, the pair and its density
└── src/overlap_viewer/
    ├── app.py                command line and start-up
    ├── backend/              what the data is — pandas, numpy and pyarrow only
    │   ├── config.py         dataset fallbacks · plausible ranges · the tint ladder · signatures · layout · cache
    │   ├── dataset.py        dataset.ini · instance catalogue and its cache · sensor figures from the footers, from merged recordings and pair by pair · overlaps and joins per well
    │   ├── profiles.py       the pass that profiles every sensor of every instance and bar: how it was measured, what it amounts to, cached
    │   ├── labels.py         label kinds and names · runs, their agreement and their merge · feature statistics · coverage counts · a stamp at a frame's own resolution
    │   ├── timemap.py        gap-compressed (or calendar) time axis in hours
    │   ├── availability.py   the three states of a sensor in a bar · the measured/filled split of the live share · groups folded into shares of samples or of bars · the pair map of a scope
    │   ├── extras.py         the optional dependency groups: what each enables, whether it is installed, how it is installed
    │   ├── export.py         the Toolkit file list: a ParquetDatasetConfig of the instances on show, with its provenance
    │   ├── model_outputs.py  the model-output format: model.json beside per-instance parquet files, its loader, the agreement with the labels
    │   ├── theme.py          every color of the light and of the dark mode
    │   ├── palette.py        fault hues tinted by reach · legend entries
    │   └── help_text.py      what the help says: classes, variables, statuses, availability, usage
    ├── algorithms/           what is computed from the data — numpy only; anything heavier is an optional extra
    │   ├── faults.py         where the event begins in an instance · z-scores · the plausible extent of a series
    │   ├── interpolation.py  which samples are measurements and which the historian drew: held, interpolated, genuine · the spacing of the measurements
    │   ├── descriptors.py    what a series amounts to: moments, quantiles, autocorrelation time, signal-to-noise ratio, Zhang's Gaussianity test
    │   ├── cleaning.py       the Toolkit's CleanSignals rule on the profiles: bounds at the quartiles, the sensors discarded and dropped
    │   ├── embedding.py      the Instances map: representations, PCA and MDS in numpy, t-SNE and UMAP, the clusterings and their scores, typicality, the one-class audit
    │   ├── dtw.py            the DTW distance between the decimated, z-scored series of one sensor (the ``dtw`` extra)
    │   ├── correlation.py    how the sensors move together over a scope: Pearson exact over the pooled samples, the mutual-information and nonlinear coefficients, per smoothing window
    │   ├── dispersion.py     two sensors against each other over a scope: an even subsample of every instance with its label periods and measurements, the pair, its density
    │   └── spectral.py       the signal views: a series prepared · Welch's density and the dominant period · the Lomb–Scargle periodogram of the measurements · histograms stacked by label, with their peak
    └── frontend/             how it is shown — PySide6 and pyqtgraph
        ├── styling.py        installing a theme into Qt and pyqtgraph · the saved mode
        ├── loading.py        progress dialogs · cache of loaded instances
        ├── passes.py         the passes over the data, read once behind a dialog and shared by every page
        ├── traces.py         a time series drawn as measurements (dots) and the historian's lines (faint) between them
        ├── items.py          pyqtgraph items: segments, instance bars and their marks, time axis, anchored text
        ├── spectral_items.py the parameter widgets, the period axis and the builders of the signal views
        ├── heatmap.py        the matrix widget of the availability page, its tooltips and the keys of the states
        ├── legend.py         the clickable color key and its flow layout
        ├── help.py           the help window
        ├── overview.py       the timelines page: the grid of well timelines
        ├── availability_page.py  the availability page: its three matrices — availability, sensor pairs, sensor correlations — and what each says
        ├── series_page.py    what the faults and features pages both are: sections of instances, in a chosen domain and layout
        ├── faults_page.py    the faults page: one fault, a section per feature, its instances in the color of their well
        ├── features_page.py  the features page: one sensor, a section per fault class, the classes over one another when overlaid
        ├── map_page.py       the Instances map: the points, their colorings, the clustering scores, the label audit
        ├── dispersion_page.py    the Dispersion page: two sensors against each other over a scope, the dots, the density, the measurements alone
        ├── instance_window.py    the time series of a group of overlapping instances, with their distributions and spectra
        └── window.py         the main window: the pages, the shared toolbar and status bar, the windows they open
```

The three packages are layers, and the dependencies grow from one to the next. `backend` is what
the data is: it depends on pandas, numpy and pyarrow only, and reads what the dataset states about
itself from `dataset.ini` (event names and labels, which events have a transient, the transient
offset, variable units, which variables are valve states), with built-in fallbacks for 3W 2.0.0.
`algorithms` is what is computed from the data, in numpy; whatever needs more is an optional extra
(above). `frontend` is how it is shown, in PySide6 and pyqtgraph; `app.py`, at the top, is the one
module that imports from all three. Same-focus code sits together: a new analysis goes into
`algorithms` with its tests, and the page that shows it into `frontend`. The lane-packing rule
that stacks the instances is the one the `flowml` pipeline uses to drop overlapping instances: what
the timelines show on stack level 2 or higher is exactly what the pipeline removes by default. The
plausible ranges are the pipeline's cleaning rules.

The help text and the signature variables come from the 3W Dataset 2.0.0 data article
([doi:10.1038/s41597-026-07225-z](https://doi.org/10.1038/s41597-026-07225-z)); its figures 3 to 7
are the source of the five published signatures and are reproduced in the help
(`docs/assets/signature-*.png`), and its table 2 gives the position of every sensor in its
figure 1. The availability page follows the availability map of
[G. Rozo](https://github.com/GabrielRozo123/3W/blob/new_3w_datasets_overviews/dataset/demos/GabrielRozo/main.ipynb)
and section 2.3.2 of the
[final graduation project of G. Rabelo de Oliveira](docs/papers/final_graduation_project_gabriel_rabelo.pdf),
counting the real instances only, and every one of them; its pair matrix is his figure 2.10, and
the faults page makes the comparison of his figures 2.5 and 2.6 for every fault. The features page
is the same machinery with the roles of fault and feature swapped, and its overlaid histogram of
one sensor per class is the closest the viewer comes to the diagonal of a pairplot.

## Development

```bash
uv sync --all-groups       # adds pytest and ruff
uv run pytest
uv run ruff check . && uv run ruff format .
```

Tests cover the backend and the algorithms; the widgets were checked by rendering them offscreen
(`QT_QPA_PLATFORM=offscreen`) against the full dataset.
