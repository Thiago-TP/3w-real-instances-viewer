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

**2026-09-16 Batch**

*More analysis domains*

The current viewer shows features as is, i.e., time series.
More sofisticated analysis refer to the stochastic/non-stationary nature of the signals, as well as its frequency content.
It could be useful to have plots showing the histograms and frequency content of the signals,
allowing users to identify patterns and anomalies in the data that may not be apparent in the time domain.
For example, the magnitude spectrum of a severe slugging event would highlight the dominant frequencies of the oscillations, which is difficult to perceive in the time domain.

I'm not sure how to implement this in the GUI, and am leaning towards having a "Histograms" and a "Frequency domain" page in the instace plot window + a "Histograms" and a "Frequency domain" subpages in the "Fault" page of the main window.
Inside the "Frequency domain" page, user could select the type of transform (magnitude spectrum, power spectrum, phase spectrum, wavelet transform, power spectral density, spectrogram, etc.) and the parameters of the transform (e.g., window size, overlap, etc.).

> [!NOTE]
> **Proposed 2026-09-16: not pages but three more views of the same plots, each placed where it can share
> an axis with the trace; one estimator per view, and a period axis instead of a frequency axis.**
>
> *What the data allows, measured before designing.* The grid is a fixed 1 Hz: none of the 32 real
> severe-slugging instances has a step other than one second, and their pressures miss at most 2.5 % of
> their samples, so a transform can interpolate over the holes and needs no resampling. The events are
> slow: severe slugging on WELL-00014 cycles every 50 to 90 minutes, flow instability on WELL-00001 every
> 45, the pressures of a DHSV closure every 45 to 80, so a six-hour instance holds four to seven cycles.
> That decides three things. A frequency axis in hertz would read 0.0002 and 0.0003, so the axis must be
> the **period**, logarithmic, from seconds to hours. Rabelo's 300 s window holds no cycle at all, so the
> default spectrum must be taken over the whole stretch shown, and shorter segments offered as an option.
> And a spectrogram of one instance has one to three slices at those periods, so it says something about
> a *joined* recording, where it would show what the periodogram already hints at: the slugging period of
> WELL-00014 drifts from 90 minutes on 18 September to 72 on the 20th, 60 on the 26th and 51 by 28 October.
> Normal instances have no line to speak of, 1 to 2 % of the power in their strongest one against 40 to
> 95 % for slugging and instability, so a caption-sized figure, *dominant period and its share of the
> power*, is itself a signature. The transforms cost 15 ms on six days of samples, so they are computed
> on the fly for whatever is on screen, with no cache and no progress dialog.
>
> *Why views and not pages.* The instance window exists to line things up vertically on one time axis; a
> "Histograms" tab gives that up and makes the user switch back and forth to learn which stretch produced
> which peak, which is the whole question for a non-stationary signal. And of the transforms listed,
> magnitude, power and density spectra are the same picture on three scales, the phase spectrum means
> nothing for one signal on its own (it means something *between two* sensors, see below), and the wavelet
> transform needs either a dependency the project has kept out or a numpy Morlet that is not needed until
> the spectrogram proves too coarse. So: three views, each with one estimator, each with an axis in
> common with the trace, and each sitting where it can share it. The toolbar of the instance window gets
> three checkboxes, **Distribution**, **Spectrum**, **Spectrogram**, the time series always on, and every
> feature plot becomes up to four panels:
>
> ```
> [ time series                     ][ distribution — shares the value axis ]
> [ spectrogram — shares the time axis ][ spectrum — shares the period axis  ]
> ```
>
> *Distribution.* A marginal histogram to the right of each trace, turned on its side so its value axis
> is the trace's and a reading is at the same height in both. Bars stacked by label period in the class
> colors (normal, transient, steady, the unlabeled hatched), so that how the fault moves the distribution
> is read inside one instance, Rabelo's pairplot diagonal per stretch instead of per class. Counted over
> the stretch of time visible, so zooming is brushing; implausible readings left out and counted in the
> caption; a bimodal shape is an oscillation (the slugging pressures have a kurtosis of −1.2).
>
> *Spectrum.* One estimator, Welch's power spectral density with a Hann window, after removing the mean
> and the linear trend (otherwise the trend owns every long period) and interpolating the missing samples
> inside the stretch; a stretch with fewer than half its readings, or a frozen sensor, gets a note instead
> of a plot. Log power against log period, the period on the *vertical* axis so it is the spectrogram's.
> A **Resolution** combo sets the segment: *whole stretch* (a periodogram, the default), 4 h, 2 h, 1 h,
> 15 min, 5 min; shorter segments average more and see nothing longer than themselves, and the axis is
> greyed beyond the segment length to say so. Caption: the dominant period and its share of the power.
> Computed over the visible stretch, like the histogram.
>
> *Spectrogram.* A short-time transform with the chosen segment and 50 % overlap (Rabelo's), its power
> resampled onto a logarithmic period grid because the image item wants a uniform one, drawn under the
> trace on the shared time axis for the whole recording; the label bands above already say which stretch
> is which. It earns its place over joined recordings and at periods under an hour; the help says plainly
> that on a single six-hour instance it cannot resolve the slugging period.
>
> *Faults page.* A **Domain** combo, *Time series*, *Distribution*, *Spectrum*, changes what every small
> plot shows; no spectrogram there, a grid of them says nothing. The *Overlaid* layout, judged unreadable
> for traces, is the natural one for spectra: they are positive, on a log scale, and whether their peaks
> line up is exactly the question the overlay failed to answer for the shapes. *Normalize per instance*
> puts the histograms of different wells on one z-score axis and the spectra in units of variance. The
> hours before and after the onset pick the stretch transformed, so "2 h after" gives the spectrum of the
> fault alone; *Align at* stays as the anchor of that window.
>
> *Help and README.* A *Signal views* section of *Using the viewer* and a paragraph among the dataset
> notes: what detrending and interpolation do, why the axis is a period, how to read a peak and a bimodal
> histogram, with the measured periods above as the example, and the caveat on the spectrogram.
>
> *Later, not now.* The cross-spectrum phase between two sensors, which would measure the paper's "four
> variables cycling in phase" and tell whether PDG leads TPT; the histogram of the same sensor over the
> normal instances of the well as a faint reference behind an instance's; a numpy Morlet transform if the
> fixed segment proves too coarse; and the dominant period and its share as a column of the catalogue
> (a data pass, cached like the pairs), which would be the first statistic across the instances of a
> fault that the Faults page still lacks. If the four-panel block proves too wide in practice, the
> fallback is the tabs first thought of, with the same three views and estimators behind them.
>
> *Settled on review, 2026-09-16.* Three points. **Why no phase spectrum of one signal:** the phase of a
> transform at a period is the instant, inside the record, at which that cycle peaks, and shifting the
> start of the record by τ adds 2πτ/T to every phase; so it depends on where the file happens to begin,
> is random at every period that carries no power, and at the dominant period tells only where the
> peaks are, which the trace shows. The start cancels in the *difference* of the phases of two sensors
> over the same stretch, which is why the cross-spectrum phase is meaningful and the single one is not.
> **Parameters are widgets:** wherever a view is parameterized, the values are set by the user in the
> toolbar, not chosen from a fixed list: the segment length in minutes (zero meaning the whole stretch),
> the overlap in percent, the window function, and the number of histogram bins; the same widgets serve
> the instance window and the Faults page. **A joined recording is one signal:** with *Join overlapping
> instances* ticked, every view is computed over the merged recording as a single series, never stitched
> from the views of its parts; the seams are drawn on the spectrogram as they are on the trace.

---