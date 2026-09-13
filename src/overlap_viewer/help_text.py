"""What the help window says about the dataset. Text only, no Qt.

Everything here comes from the three documents in ``docs/papers`` and from the
``dataset.ini`` shipped with the dataset:

- the **2.0.0 data article** (Vargas et al., 2025), which describes the dataset
  as it stands and illustrates five of the ten classes;
- the **1.0.0 data article** (Vargas et al., 2019), which the 2.0.0 one defers
  to for what each event is;
- the **doctoral thesis** behind both (R. E. V. Vargas, 2019, in Portuguese),
  which carries the physics neither article has room for and works through a
  real instance of every event of its time.

None of the three describes every event, and the thesis warns that experts do
not even agree on the names. Where they say nothing, the entry says so: help
text that invents physics is worse than help text that admits a limit. Each
entry names the document it leans on.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Figure:
    """One illustration of the help: the file to look for and what to say about it."""

    file: str
    width: int
    caption: str
    credit: str


FIGURES: dict[str, Figure] = {
    "platform-overview": Figure(
        file="platform-v1.jpg",
        width=357,
        caption=(
            "The production path, from the reservoir to the platform. Nearly every event below is "
            "described by where it sits on this path: the production choke (PCK) topside, the "
            "christmas tree and its transducer (TPT) on the seabed, the safety valve (DHSV) in the "
            "tubing, and the downhole gauge (PDG) at the bottom. A pressure rises upstream of "
            "whatever closes or blocks, and falls downstream of it."
        ),
        credit="Figure 1 of the 3W Dataset paper (Vargas et al., 2019)",
    ),
    "platform": Figure(
        file="platform-v2.webp",
        width=880,
        caption=(
            "Where each variable is measured. Left, the subsea christmas tree and its valves, with "
            "the TPT transducer; bottom, the well itself with the safety valve (DHSV) and the "
            "downhole gauge (PDG); right, the topside of the platform, where the production line "
            "reaches the production choke (PCK) and the shutdown valve (SDV), and where the "
            "service pump and the gas compressor feed the service and gas-lift lines. The numbers "
            "are the positions the variable table of the paper refers to."
        ),
        credit="Figure 1 of the 3W Dataset 2.0.0 paper (Vargas et al., 2025), CC BY 4.0",
    ),
}


@dataclass(frozen=True)
class FaultHelp:
    """What one class label means, and how the literature says it shows in the data.

    ``source`` names the documents each entry leans on, since the three differ
    in what they cover.
    """

    name: str
    what: str
    signature: str
    figure: str = ""  # the example figure of the 2.0.0 article, when it has one
    notes: str = ""
    source: str = ""


# The transient code of an event is its class plus the transient offset; the
# events missing from this set have no transient period in the dataset at all.
TRANSIENT_CAPABLE = {1, 2, 5, 6, 7, 8, 9}

# How long a window the well-monitoring analysts at Petrobras look at before
# they will confirm an occurrence (table 1 of both articles and of the thesis).
# It is the time the evidence takes to become conclusive to a human, not how
# long the event lasts — but it is the best published measure of the pace of
# each event, and it says why some of them need a whole instance on screen and
# others a few minutes. Hydrate in Service Line arrived with version 2.0.0 and
# has no published figure.
CONFIRMATION_WINDOWS: dict[int, str] = {
    1: "12 hours",
    2: "5 to 20 minutes",
    3: "5 hours",
    4: "15 minutes",
    5: "12 hours",
    6: "15 minutes",
    7: "72 hours",
    8: "30 minutes to 5 hours",
}

FAULTS: dict[int, FaultHelp] = {
    0: FaultHelp(
        name="Normal Operation",
        what=(
            "The well is in full production, in a steady regime with no significant anomaly. Every "
            "event in the dataset starts from this state. The thesis names four mutually exclusive "
            "states a naturally flowing well can be in — closed, normal operation, starting and "
            "closing — and warns that no standard or authority defines them, so the vocabulary is "
            "Petrobras's own; version 2.0.0 of the dataset replaced them with the nine operational "
            "statuses this viewer draws in the state band."
        ),
        signature=(
            "Figure 7 of the 2.0.0 article shows a normal instance in which the well was shut down "
            "and the line depressurized: the production choke opening (ABER-CKP) steps down from "
            "100 %, the production wing valve (ESTADO-W1) goes from open to closed, and the tree "
            "temperature (T-TPT) collapses as flow stops, recovering when the valves reopen at "
            "Restart. The normal instances worked through in the 1.0.0 article and in the thesis "
            "carry a warning of their own: in both, one of the three plotted sensors is frozen "
            "from end to end."
        ),
        figure="figure 7",
        notes=(
            "The most numerous class of the dataset, and the only one with no simulated and no "
            "hand-drawn instances: normal operation was never synthesized."
        ),
        source="2.0.0 article, figure 7; thesis, section 1.1.3 and figure 12",
    ),
    1: FaultHelp(
        name="Abrupt Increase of BSW",
        what=(
            "BSW is the ratio of produced water and sediment to produced liquid. It is expected to "
            "climb over a well's life as water arrives from the aquifer or from injection, and the "
            "piping is designed for that; what hurts is a sudden jump, which costs oil production "
            "and brings problems of flow assurance, lifting, scaling and processing at the plant. "
            "No sensor measures BSW, so it has to be read off the pressures and temperatures."
        ),
        signature=(
            "The thesis gives the rule and warns there is no single canonical shape: pressures and "
            "temperatures may move either way, but as a rule <b>the pressures measured deep rise, "
            "the pressures near the surface fall, and the temperatures rise everywhere</b>. In its "
            "worked instance the tree pressure and the pressure upstream of the choke drift down "
            "over hours while the tree temperature and the temperature downstream of the choke "
            "drift up, and the downhole gauge is frozen throughout."
        ),
        notes=(
            "One of the two rarest events in the field: the dataset has very few real instances, "
            "and it is one of only two classes with hand-drawn instances, which the papers reserve "
            "for events that are both rare and hard to simulate. In the thesis's example the well "
            "took about eight and a half hours to reach the steady state."
        ),
        source="thesis, section 2.3.1 and figure 3; 1.0.0 article",
    ),
    2: FaultHelp(
        name="Spurious Closure of DHSV",
        what=(
            "The downhole safety valve sits in the production tubing and is held open by a "
            "hydraulic actuator; it is built to fail closed, so that the well shuts itself in if "
            "the platform is lost. Occasionally it closes on its own, and both the article and the "
            "thesis stress that this usually happens <b>with no indication at the surface at "
            "all</b> — not even a pressure drop in the actuator — which leaves the process "
            "variables as the only evidence. Caught in time it can be reopened by a corrective "
            "procedure, which is exactly what makes predicting it worth something."
        ),
        signature=(
            "The closed valve splits the well in two and the readings diverge accordingly: below "
            "it the downhole pressure (P-PDG) builds up, while above it the tree pressure (P-TPT), "
            "the pressure upstream of the production choke (P-MON-CKP) and the tree temperature "
            "(T-TPT) all collapse as the flow stops and the tree cools toward the seabed. In the "
            "thesis's example production had stopped entirely about 35 minutes after the onset."
        ),
        figure="figure 3",
        source="2.0.0 article, figure 3; thesis, section 2.3.2 and figure 4",
    ),
    3: FaultHelp(
        name="Severe Slugging",
        what=(
            "The critical flow instability: liquid accumulates and is then expelled in surges, "
            "which cycles the pressure of the whole production path and can stress or damage "
            "equipment in the well and in the plant. Two marks define it — a well-defined "
            "periodicity, around 30, 45 or 60 minutes, and an intensity usually large enough to be "
            "seen by every sensor along the production circuit. Recognized early, the well's "
            "operation can be changed to reverse it."
        ),
        signature=(
            "Regular cycles on everything: oscillations above 10 bar at the downhole gauge "
            "(P-PDG) and the tree (P-TPT), with the pressure upstream of the production choke "
            "(P-MON-CKP) and the temperature downstream of it (T-JUS-CKP) swinging in phase. The "
            "shape is a sawtooth, a slow build and a fast blowdown, and the choke pressure can "
            "show a sharp spike once per cycle as each slug arrives. The thesis's example cycles "
            "about every 67 minutes."
        ),
        figure="figure 6",
        notes=(
            "Has no transient period: an instance is already in the established oscillating regime "
            "where it is labeled at all."
        ),
        source="2.0.0 article, figure 6; thesis, section 2.3.3 and figure 5",
    ),
    4: FaultHelp(
        name="Flow Instability",
        what=(
            "The milder sibling of severe slugging: at least part of the monitored series shows "
            "relevant but tolerable changes, and what tells the two apart is that these changes "
            "have <b>no periodicity</b>. Neither article nor the thesis offers any mechanism "
            "beyond that contrast. It is worth catching because an instability can grow into "
            "severe slugging, with everything that entails."
        ),
        signature=(
            "The same variables as severe slugging, without the rhythm: the tree pressure and "
            "temperature and the readings around the choke wander aperiodically, by a fraction of "
            "their own level, over minutes to hours. Periodic and intense is severe slugging; "
            "aperiodic and tolerable is flow instability — that contrast is the only discriminator "
            "the sources state."
        ),
        notes=(
            "Has no transient period, and its instances often carry no normal period either. It is "
            "the second most numerous class of the dataset and the only undesirable event with no "
            "simulated instances at all: every one of them is real."
        ),
        source="thesis, section 2.3.4 and figure 6; 1.0.0 article",
    ),
    5: FaultHelp(
        name="Rapid Productivity Loss",
        what=(
            "The productivity of a naturally flowing well rests on reservoir properties — static "
            "pressure, water and sediment content, productivity index, gas-oil ratio, viscosity — "
            "and the reservoir keeps changing as it empties. When those properties change so far "
            "that the system's energy no longer overcomes its losses, the fluid can no longer "
            "reach the surface and production ceases: in the limit, the well loses its natural "
            "flow. Caught in time, the operators can move the well's operating point instead."
        ),
        signature=(
            "A slow, monotone decline across the board: in the thesis's worked instance the tree "
            "pressure and temperature, the pressure upstream of the choke and the temperature "
            "downstream of it all sag together over about ten hours, the last two so noisy that "
            "the trend reads only as an envelope."
        ),
        notes=(
            "Rare in the field: almost all of its instances in the dataset are simulated. In the "
            "thesis's example the well was intervened after about eight and three quarter hours "
            "and never reached the steady state at all, which is why so many instances of this "
            "class stop in the transient."
        ),
        source="thesis, section 2.3.5 and figure 7; 1.0.0 article",
    ),
    6: FaultHelp(
        name="Quick Restriction in PCK",
        what=(
            "The production choke is the valve at the start of the production unit that controls "
            "the well at the surface, and it is generally operated by hand, so an operational slip "
            "can restrict it sharply. The term is internal to Petrobras and undefined in the "
            "literature; the working definition is a restriction of more than some reference "
            "amplitude, 5 % say, within a short time, ten seconds say. Being a manual valve, an "
            "unwanted restriction can also be undone quickly."
        ),
        signature=(
            "The choke opening (ABER-CKP) steps down and every pressure behind it rises together — "
            "upstream of the choke (P-MON-CKP), at the tree (P-TPT) and downhole (P-PDG) — while "
            "the tree temperature and the temperature downstream of the choke fall. It develops in "
            "minutes: about eleven, in the thesis's example."
        ),
        figure="figure 4",
        notes=(
            "Among the rarest events in the field: the dataset holds only a handful of real "
            "instances."
        ),
        source="2.0.0 article, figure 4; thesis, section 2.3.6 and figure 8",
    ),
    7: FaultHelp(
        name="Scaling in PCK",
        what=(
            "Inorganic deposits build up in the production choke and can cut oil and gas "
            "production drastically. Caught in time, a scale inhibitor can be injected before the "
            "production is lost. Neither article nor the thesis says more than that about the "
            "chemistry."
        ),
        signature=(
            "The 2.0.0 article publishes no example, but the thesis's worked instance gives "
            "<b>the same directions as a quick restriction of the same valve</b> — the tree "
            "pressure and the pressure upstream of the choke climb while the tree temperature and "
            "the temperature downstream of the choke fall — spread over some ten hours instead of "
            "ten minutes. Timescale, not direction, is what tells the two apart: analysts confirm "
            "a restriction within a quarter of an hour and scaling over three days."
        ),
        notes=(
            "The only event that stays rare even after the simulated and hand-drawn instances are "
            "counted, and the one the OLGA simulations could not produce at all — hence its "
            "hand-drawn instances."
        ),
        source="thesis, section 2.3.7 and figure 9; 1.0.0 article",
    ),
    8: FaultHelp(
        name="Hydrate in Production Line",
        what=(
            "A hydrate is a crystalline compound of water and natural gas that looks like ice. It "
            "needs water and gas together at high pressure and low temperature, so lines carrying "
            "dead oil never see it and gas wells see it most, but an oil well can be blocked "
            "outright. Clearing a plug costs days or weeks of production, and sometimes an "
            "offshore rig at more than half a million dollars a day — which is why the shut-in "
            "procedures in the state band exist: depressurizing, flushing the line with diesel or "
            "gas, bullheading."
        ),
        signature=(
            "Pressures rise upstream of the forming plug — downhole (P-PDG) and at the tree "
            "(P-TPT) — while the pressure downstream of it, upstream of the production choke "
            "(P-MON-CKP), falls and the tree temperature (T-TPT) drifts down. It is a slow drift "
            "over hours or days rather than a step. In the thesis's example the collapse of the "
            "tree temperature is what says the flow had stopped completely."
        ),
        figure="figure 5",
        notes=(
            "The 2.0.0 example spends most of its length in the transient and reaches the steady "
            "state only at the very end, which is why so many instances of the hydrate classes "
            "never reach it at all. In the simulated instances the hydrate was modeled as a valve "
            "closing linearly, a deliberate simplification."
        ),
        source="2.0.0 article, figure 5; thesis, section 2.3.8 and figure 10",
    ),
    9: FaultHelp(
        name="Hydrate in Service Line",
        what=(
            "The same crystalline blockage as in the production line, but in the service line — "
            "the line that carries diesel or gas down to the well for flushing and the other "
            "operations against hydrates. The 2.0.0 article says its signature patterns are "
            "distinct from the production line's, without saying what they are."
        ),
        signature=(
            "None of the three documents publishes an example: this event was added with version "
            "2.0.0, and neither the 1.0.0 article nor the thesis covers it. Its own instruments "
            "are the ones on the service line: the pressure downstream of the service pump "
            "(P-JUS-BS) and the service pump flow rate (QBS)."
        ),
        notes="The event type added in version 2.0.0 of the dataset; version 1.0.0 has none of it.",
        source="2.0.0 article",
    ),
}


@dataclass(frozen=True)
class VariableHelp:
    """Where one variable is measured, and what is worth knowing about it."""

    where: str
    note: str = ""
    signature_of: tuple[int, ...] = field(default_factory=tuple)


# Position in the production system, from table 2 and figure 1 of the 2.0.0
# article and section 2.1 of the thesis.
DOWNHOLE = "Downhole, in the production tubing"
TREE = "Subsea christmas tree, on the seabed"
TOPSIDE = "Topside, on the production platform"
GAS_LIFT = "Topside, gas-lift line"
SERVICE = "Topside, service line"

VARIABLES: dict[str, VariableHelp] = {
    "ABER-CKGL": VariableHelp(GAS_LIFT, "How far the gas-lift choke is open, in percent."),
    "ABER-CKP": VariableHelp(
        TOPSIDE,
        "How far the production choke is open, in percent. It sets how much the well may flow, so "
        "it is the variable to read first when the pressures behind it move.",
    ),
    "ESTADO-DHSV": VariableHelp(
        DOWNHOLE,
        "State of the downhole safety valve, the valve whose spurious closure is fault class 2. "
        "That closure usually leaves no trace at the surface, which is what makes the event hard.",
    ),
    "ESTADO-M1": VariableHelp(TREE, "State of the production master valve."),
    "ESTADO-M2": VariableHelp(TREE, "State of the annulus master valve."),
    "ESTADO-PXO": VariableHelp(
        TREE, "State of the pig-crossover valve, opened to circulate between the two lines."
    ),
    "ESTADO-SDV-GL": VariableHelp(GAS_LIFT, "State of the gas-lift shutdown valve."),
    "ESTADO-SDV-P": VariableHelp(TOPSIDE, "State of the production shutdown valve."),
    "ESTADO-W1": VariableHelp(TREE, "State of the production wing valve."),
    "ESTADO-W2": VariableHelp(TREE, "State of the annulus wing valve."),
    "ESTADO-XO": VariableHelp(TREE, "State of the crossover valve."),
    "P-ANULAR": VariableHelp(
        TREE, "Pressure in the annulus, the space around the production tubing."
    ),
    "P-JUS-BS": VariableHelp(
        SERVICE,
        "Pressure downstream of the service pump. With the pump's flow rate, it is the only "
        "instrumentation on the line where fault class 9 forms.",
    ),
    "P-JUS-CKGL": VariableHelp(GAS_LIFT, "Pressure downstream of the gas-lift choke."),
    "P-JUS-CKP": VariableHelp(TOPSIDE, "Pressure downstream of the production choke."),
    "P-MON-CKGL": VariableHelp(GAS_LIFT, "Pressure upstream of the gas-lift choke."),
    "P-MON-CKP": VariableHelp(
        TOPSIDE,
        "Pressure upstream of the production choke, the last pressure before the platform, and one "
        "the thesis counts as reliable when it is there. It is downstream of everything in the "
        "well, so it falls when the line blocks and rises when the choke itself closes.",
    ),
    "P-MON-SDV-P": VariableHelp(TOPSIDE, "Pressure upstream of the production shutdown valve."),
    "P-PDG": VariableHelp(
        DOWNHOLE,
        "Pressure at the permanent downhole gauge, the deepest measurement there is, next to the "
        "reservoir. It rises whenever something downstream of it closes or blocks. With the tree "
        "pressure it is the most relevant reading for flow analysis — and, the thesis notes, also "
        "the one that most often fails or is missing, since the gauge is screwed to the production "
        "tubing and replacing it means pulling the tubing.",
    ),
    "PT-P": VariableHelp(TREE, "Tree pressure downstream of the production wing valve."),
    "P-TPT": VariableHelp(
        TREE,
        "Pressure at the tree transducer, between the well and the flowline, inside the christmas "
        "tree and considered reliable. It takes part in the signature of every event the "
        "literature illustrates.",
    ),
    "QBS": VariableHelp(SERVICE, "Flow rate at the service pump."),
    "QGL": VariableHelp(
        GAS_LIFT,
        "Gas-lift flow rate: the gas injected to lighten the produced column when the reservoir "
        "can no longer lift it on its own.",
    ),
    "T-JUS-CKP": VariableHelp(
        TOPSIDE,
        "Temperature downstream of the production choke, which swings with each slug. The fluid "
        "here can come from several wells at once, but the reading is kept because there is "
        "usually no temperature sensor upstream of the choke.",
    ),
    "T-MON-CKP": VariableHelp(TOPSIDE, "Temperature upstream of the production choke."),
    "T-PDG": VariableHelp(DOWNHOLE, "Temperature at the permanent downhole gauge."),
    "T-TPT": VariableHelp(
        TREE,
        "Temperature at the tree transducer, also considered reliable. Flowing fluid keeps the "
        "tree warm, so this reading collapses whenever production stops and is the quickest "
        "confirmation that it did.",
    ),
}

# Wording of the well operational status codes, from table 5 of the 2.0.0
# article. The thesis, which predates them, knows only four states and warns
# that no standard defines any of this vocabulary.
STATES: dict[int, str] = {
    0: (
        "All production valves are open and the auxiliary valves closed: the well is producing "
        "under regular conditions. Every other status belongs to a shut-in procedure."
    ),
    1: "At least one valve of the production path is closed, so the well is not producing.",
    2: (
        "Diesel is circulated from the service line into the production line, displacing the "
        "produced fluids toward the platform so that nothing hydrate-prone is left in the line."
    ),
    3: (
        "Gas is circulated from the service line into the production line, removing the liquids "
        "that could form hydrates and leaving a drier line behind."
    ),
    4: (
        "Diesel or gas is injected from the platform into the production line under pressure, "
        "pushing the produced fluids back down into the well."
    ),
    5: (
        "The well is closed and most of the production line is filled with diesel, following a "
        "diesel flush or a bullheading. Hydrates are highly unlikely in this condition."
    ),
    6: (
        "The well is closed and most of the production line is filled with natural gas, following "
        "a gas flush. This also mitigates the risk of hydrates."
    ),
    7: (
        "The production valves have just been reopened after a shut-in: a transient period before "
        "the well settles back into regular production."
    ),
    8: (
        "After a shut-in, the production shutdown valve and the choke are opened while the tree "
        "valves stay closed, so the line loses pressure and moves away from the conditions in "
        "which hydrates form."
    ),
}

# The dataset's own facts, for the tab that explains what is being looked at.
DATASET_NOTES = [
    (
        "One file, one instance",
        (
            "The dataset stores one parquet file per instance, sampled once a second, in a folder "
            "named after the class of the event it carries. A real instance is named after its "
            "well and the timestamp of its first sample, which is the name this viewer writes "
            "inside each bar."
        ),
    ),
    (
        "Why instances overlap",
        (
            "The real instances of one well are windows cut from the same continuous recording, "
            "and nothing keeps two of them apart in time. Where they overlap, the same samples "
            "enter a dataset twice, and often under different labels, since the end of one "
            "instance can be the normal period that precedes the event another one records. None "
            "of the three documents says how the windows were cut, or whether they may overlap; "
            "showing that they do is what this viewer is for."
        ),
    ),
    (
        "Real, simulated and hand-drawn",
        (
            "Instances come from field recordings, from OLGA simulations, or from experts drawing "
            "the curves of events too rare to have been recorded. Only real instances belong to a "
            "physical well and can overlap another, so this viewer shows only those. Keep in mind "
            "when comparing sources that simulated and hand-drawn instances are clean by "
            "construction: no missing values, no frozen sensors, no noise, no outliers."
        ),
    ),
    (
        "The data is left as it was recorded",
        (
            "Real instances keep their frozen sensors, their missing variables and their outliers: "
            "the papers leave them untreated on purpose, so that methods have to cope with them. A "
            "variable counts as <i>missing</i> when every one of its readings is missing in that "
            "instance, and as <i>frozen</i> when they all carry one single value — not always a "
            "fault, but a symptom of a sensor, configuration or network problem, and a variable "
            "that cannot show the pattern of an event. About two thirds of the variable-instance "
            "pairs of version 2.0.0 are missing and about a tenth frozen, which is why so many "
            "panels in this viewer read <i>not recorded</i> or <i>flat</i>."
        ),
    ),
    (
        "Why so many sensors are dead",
        (
            "A well carries few sensors compared with a surface plant, because they are expensive "
            "and hard to reach: some sit more than a thousand metres under water or inside the "
            "production tubing. They are not always well calibrated, and a failed one can stay "
            "failed for a long time, since in some cases intervening costs more than living with "
            "it. The downhole gauge is the extreme case, and the cruel one: it is both the reading "
            "the analysts value most and the one most likely to be frozen or absent."
        ),
    ),
    (
        "Labels, and the three periods",
        (
            "The class column is 0 during normal operation, the number of the event once it has "
            "installed itself (its steady state), and that number plus 100 while it is installing "
            "itself (its transient period). An instance therefore holds up to three periods in "
            "order — normal, faulty transient, faulty steady state — and no instance carries more "
            "than one event. The transient period is the point of the whole design: it is the "
            "stretch where the dynamics of the event are still under way, so learning it means "
            "<i>predicting</i> the steady state rather than merely detecting it. Severe Slugging "
            "and Flow Instability have no transient period. Samples whose condition the experts "
            "could not establish are left unlabeled, about one in twenty of the dataset."
        ),
    ),
    (
        "The labels are expert judgement",
        (
            "Instances were labeled by Petrobras specialists in each event, and the thesis "
            "describes the onset of a transient as the moment <i>indicated by a specialist</i> — a "
            "judgement, not a measurement. None of the documents reports how far two labelers "
            "would agree."
        ),
    ),
    (
        "The names are not settled",
        (
            "The 1.0.0 article opens its description of the events with a warning worth repeating: "
            "there is not always consensus on the names of these events or on what they mean, even "
            "among experts. The thesis says the same of the well states. What each class means "
            "here is what these documents say it means."
        ),
    ),
]

# How to work the viewer, shown in both windows.
USAGE = {
    "Overview window": [
        (
            "Every plot is one well; every bar is one real instance, from its first to its last "
            "sample. Bars that overlap in time are stacked, so the stack level is how many "
            "instances cover that moment."
        ),
        (
            "Hover a bar to outline it, outline the instances it overlaps, hatch the stretch they "
            "share and dim the rest. The status bar names them and the color key lights up the "
            "matching entries."
        ),
        "Click a bar to open the time series of that instance and of every instance it overlaps.",
        (
            "Click an entry of the color key to show only the wells that recorded that fault; "
            "click it again, or the button at the right of the toolbar, to show them all again."
        ),
        (
            "Click the title of the color key, or press Ctrl+L, to retract it to that one line and "
            "give the grid the room. Retracted it still answers hovering: the entries of the "
            "instance under the pointer, and of the instances it overlaps, pop into the title row."
        ),
        (
            "A well is recorded in bursts separated by months of silence, so the silences are "
            "collapsed to narrow dashed blanks. The time scale stays uniform everywhere else: bar "
            "length is duration, and two bars overlap on screen exactly when the instances overlap "
            "in time. Untick 'Compress silences' for a true calendar axis."
        ),
    ],
    "Instance window": [
        (
            "One block per instance, stacked in chronological order on one shared time axis, so "
            "the stretches the instances share line up vertically. The band at the very top marks "
            "those stretches."
        ),
        (
            "Tick features on the left to add a plot of them to every instance. The plots of one "
            "feature share their value axis, so the same reading sits at the same height in all of "
            "them."
        ),
        (
            "'Signature' ticks the variables whose joint behavior identifies the event, for the "
            "events the 2.0.0 article illustrates."
        ),
        (
            "A crosshair follows the pointer through every plot, and the status bar reads out the "
            "label, the well status and the selected readings of each instance at that moment."
        ),
        (
            "The bands and the plot backgrounds carry the colors of the overview bars. A stretch "
            "nobody labeled is hatched instead of merely grey, so it cannot be taken for one of "
            "the two faults whose own color is grey."
        ),
        (
            "Each panel reports the total variation of the signal and how much of the instance the "
            "sensor actually recorded. A sensor that never moves is marked flat and drawn on a "
            "padded axis instead of being magnified into noise."
        ),
    ],
    "Everywhere": [
        "Drag a plot to pan it. Ctrl with the mouse wheel zooms; the wheel alone scrolls the page.",
        "Ctrl+R resets the views of the window, F1 opens this help.",
        (
            "The Theme box of the overview toolbar switches the windows and the plots inside them "
            "together, so the two never disagree; System follows the desktop. The dark mode lifts "
            "the fault hues and shades toward its own dark ground, so the ladder of tints keeps "
            "meaning the same thing. The choice is remembered."
        ),
        (
            "Right-click a plot for pyqtgraph's own menu, which can export the plot as an image or "
            "as data."
        ),
    ],
}
