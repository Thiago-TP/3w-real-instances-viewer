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

from overlap_viewer.config import DEFAULT_TRANSIENT_CAPABLE


@dataclass(frozen=True)
class Figure:
    """One illustration of the help: the file to look for and what to say about it."""

    file: str
    width: int
    caption: str
    credit: str


# The example figures of the 2.0.0 article are screenshots of the Petrobras
# labeling tool, whose colors and units are not this viewer's; every caption of
# one says so, since the reader has just been told what the viewer's colors mean.
TOOL_COLORS = (
    "The colors are the labeling tool's, not this viewer's: the lower half of each panel is the "
    "class label — light green normal operation, yellow the transient, red the steady state of "
    "the event — and the upper half the well status, dark green for Open."
)
TOOL_UNITS = (
    "Pressures are in the tool's own units (bar, kPa, kgf/cm²) rather than the pascal of the "
    "dataset."
)


def _paper_figure(number: int) -> str:
    return f"Figure {number} of the 3W Dataset 2.0.0 paper (Vargas et al., 2025), CC BY 4.0"


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
        credit=_paper_figure(1),
    ),
    # The five events the 2.0.0 article illustrates, one real instance each, in
    # the variables this viewer's Signature box ticks. Shown at their own size,
    # so the axis figures stay readable.
    "signature-normal": Figure(
        file="signature-normal.png",
        width=863,
        caption=(
            "A real Normal Operation instance (2015-03-16 10:15 to 2015-03-17 03:00) in which the "
            "well was shut in and its line depressurized, so the class label stays 0 throughout "
            "and the state label tells the story. At 16:00 the production choke (ABER-CKP) closes "
            "from 100 %, the shutdown valve (ESTADO-SDV-P) and the wing valve (ESTADO-W1) both go "
            "to 0, and the tree temperature (T-TPT) collapses from 32 °C to about 5 °C as the flow "
            "stops: Shut-In, grey. The shutdown valve reopens at about 18:10 and the choke partly "
            "with it; the line is depressurized between about 21:00 and 22:00 (salmon); at about "
            "23:00 the wing valve reopens, the temperature recovers at once, and the well is in "
            "Restart (magenta) until the window ends. The lower half of every panel stays light "
            "green: normal operation from end to end, which is what this viewer's state band is "
            "for. " + TOOL_COLORS
        ),
        credit=_paper_figure(7),
    ),
    "signature-dhsv": Figure(
        file="signature-dhsv.png",
        width=865,
        caption=(
            "A real Spurious Closure of DHSV (2017-07-28, 14:00 to 17:30). Until about 15:40 "
            "nothing moves; then the four readings part on either side of the closed valve. Below "
            "it the downhole pressure (P-PDG) climbs by some 30 bar over the rest of the window; "
            "above it the tree pressure (P-TPT), the pressure upstream of the production choke "
            "(P-MON-CKP) and the tree temperature (T-TPT) fall away as the flow stops, the "
            "temperature from 111 °C toward that of the seabed. The experts labeled the transient "
            "from the divergence to about 16:55 and the steady state after it. "
            + TOOL_COLORS
            + " "
            + TOOL_UNITS
        ),
        credit=_paper_figure(3),
    ),
    "signature-severe-slugging": Figure(
        file="signature-severe-slugging.png",
        width=866,
        caption=(
            "A real Severe Slugging instance (2016-08-04, 06:24 to 13:30), labeled in the steady "
            "state from end to end: there is no transient to this event. Every reading cycles "
            "with the same period of about 35 minutes, twelve slugs in seven hours. The downhole "
            "pressure (P-PDG) and the tree pressure (P-TPT) swing by some 12 bar each, the pressure "
            "upstream of the choke (P-MON-CKP) by 2 to 3 bar with a sharp spike as each slug "
            "arrives, and the temperature downstream of the choke (T-JUS-CKP) by about 4 °C in a "
            "sawtooth. " + TOOL_COLORS + " " + TOOL_UNITS
        ),
        credit=_paper_figure(6),
    ),
    "signature-quick-restriction": Figure(
        file="signature-quick-restriction.png",
        width=864,
        caption=(
            "A real Quick Restriction in PCK (2015-06-10, 03:30 to 16:15). The choke opening "
            "(ABER-CKP) holds 100 % until about 11:50, then steps down to some 10 % within an "
            "hour, and every pressure behind the choke rises in answer: upstream of it (P-MON-CKP) "
            "from 9 to about 60 bar, at the tree (P-TPT) from 49 to about 110 bar, downhole (P-PDG) "
            "from 87 to about 170 bar. The pressures keep rising for four hours, and the experts "
            "kept the label in the transient for as long, calling the steady state only in the "
            "last minutes of the window. " + TOOL_COLORS + " " + TOOL_UNITS
        ),
        credit=_paper_figure(4),
    ),
    "signature-hydrate-production": Figure(
        file="signature-hydrate-production.png",
        width=866,
        caption=(
            "A real Hydrate in Production Line (2019-05-03 20:15 to 2019-05-06 08:00, two and a "
            "half days). Upstream of the forming plug the pressures drift up — downhole (P-PDG) "
            "from 167 to about 197 kgf/cm², at the tree (P-TPT) from 12.2 to about 15 MPa — while "
            "downstream of it the pressure upstream of the choke (P-MON-CKP) sags from 5.3 to "
            "about 2.5 MPa and the tree temperature (T-TPT) cools from 25.5 to about 21.5 °C. "
            "Nothing steps: the labels leave normal operation early on 4 May and stay in the "
            "transient for two days, the steady state being called only in the last hour. "
            + TOOL_COLORS
            + " "
            + TOOL_UNITS
        ),
        credit=_paper_figure(5),
    ),
}


@dataclass(frozen=True)
class FaultHelp:
    """What one class label means, and how the literature says it shows in the data.

    ``source`` names the documents each entry leans on, since the three differ
    in what they cover; ``illustration`` names the entry of ``FIGURES`` that
    shows the event, for the five the 2.0.0 article illustrates.
    """

    name: str
    what: str
    signature: str
    figure: str = ""  # the example figure of the 2.0.0 article, when it has one
    illustration: str = ""  # the ``FIGURES`` entry reproducing that figure
    notes: str = ""
    source: str = ""


# The transient code of an event is its class plus the transient offset; the
# events missing from this set have no transient period in the dataset at all.
TRANSIENT_CAPABLE = set(DEFAULT_TRANSIENT_CAPABLE)

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
        illustration="signature-normal",
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
        illustration="signature-dhsv",
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
        illustration="signature-severe-slugging",
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
        illustration="signature-quick-restriction",
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
        illustration="signature-hydrate-production",
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
    """Where one variable is measured, and what is worth knowing about it.

    ``position`` is the number that marks the sensor in figure 1 of the 2.0.0
    article (the ``platform`` figure above the table), from its table 2: the
    figure before the point names a spot in the production system — 2 is the
    production choke, 14 the downhole gauge, 15 the tree transducer — and the
    figure after it tells the measurements taken at that spot apart.
    """

    where: str
    note: str = ""
    position: str = ""
    signature_of: tuple[int, ...] = field(default_factory=tuple)


# Position in the production system, from table 2 and figure 1 of the 2.0.0
# article and section 2.1 of the thesis.
DOWNHOLE = "Downhole, in the production tubing"
TREE = "Subsea christmas tree, on the seabed"
TOPSIDE = "Topside, on the production platform"
GAS_LIFT = "Topside, gas-lift line"
SERVICE = "Topside, service line"

VARIABLES: dict[str, VariableHelp] = {
    "ABER-CKGL": VariableHelp(
        GAS_LIFT, "How far the gas-lift choke is open, in percent.", position="1.1"
    ),
    "ABER-CKP": VariableHelp(
        TOPSIDE,
        "How far the production choke is open, in percent. It sets how much the well may flow, so "
        "it is the variable to read first when the pressures behind it move.",
        position="2.1",
    ),
    "ESTADO-DHSV": VariableHelp(
        DOWNHOLE,
        "State of the downhole safety valve, the valve whose spurious closure is fault class 2. "
        "That closure usually leaves no trace at the surface, which is what makes the event hard.",
        position="3.1",
    ),
    "ESTADO-M1": VariableHelp(TREE, "State of the production master valve.", position="4.1"),
    "ESTADO-M2": VariableHelp(TREE, "State of the annulus master valve.", position="5.1"),
    "ESTADO-PXO": VariableHelp(
        TREE,
        "State of the pig-crossover valve, opened to circulate between the two lines.",
        position="6.1",
    ),
    "ESTADO-SDV-GL": VariableHelp(
        GAS_LIFT, "State of the gas-lift shutdown valve.", position="7.1"
    ),
    "ESTADO-SDV-P": VariableHelp(
        TOPSIDE, "State of the production shutdown valve.", position="8.1"
    ),
    "ESTADO-W1": VariableHelp(TREE, "State of the production wing valve.", position="9.1"),
    "ESTADO-W2": VariableHelp(TREE, "State of the annulus wing valve.", position="10.1"),
    "ESTADO-XO": VariableHelp(TREE, "State of the crossover valve.", position="11.1"),
    "P-ANULAR": VariableHelp(
        TREE,
        "Pressure in the annulus, the space around the production tubing.",
        position="12.1",
    ),
    "P-JUS-BS": VariableHelp(
        SERVICE,
        "Pressure downstream of the service pump. With the pump's flow rate, it is the only "
        "instrumentation on the line where fault class 9 forms.",
        position="13.1",
    ),
    "P-JUS-CKGL": VariableHelp(
        GAS_LIFT, "Pressure downstream of the gas-lift choke.", position="1.2"
    ),
    "P-JUS-CKP": VariableHelp(
        TOPSIDE, "Pressure downstream of the production choke.", position="2.2"
    ),
    "P-MON-CKGL": VariableHelp(
        GAS_LIFT, "Pressure upstream of the gas-lift choke.", position="1.3"
    ),
    "P-MON-CKP": VariableHelp(
        TOPSIDE,
        "Pressure upstream of the production choke, the last pressure before the platform, and one "
        "the thesis counts as reliable when it is there. It is downstream of everything in the "
        "well, so it falls when the line blocks and rises when the choke itself closes.",
        position="2.3",
    ),
    "P-MON-SDV-P": VariableHelp(
        TOPSIDE, "Pressure upstream of the production shutdown valve.", position="8.2"
    ),
    "P-PDG": VariableHelp(
        DOWNHOLE,
        "Pressure at the permanent downhole gauge, the deepest measurement there is, next to the "
        "reservoir. It rises whenever something downstream of it closes or blocks. With the tree "
        "pressure it is the most relevant reading for flow analysis — and, the thesis notes, also "
        "the one that most often fails or is missing, since the gauge is screwed to the production "
        "tubing and replacing it means pulling the tubing.",
        position="14.1",
    ),
    "PT-P": VariableHelp(
        TREE, "Tree pressure downstream of the production wing valve.", position="4.2"
    ),
    "P-TPT": VariableHelp(
        TREE,
        "Pressure at the tree transducer, between the well and the flowline, inside the christmas "
        "tree and considered reliable. It takes part in the signature of every event the "
        "literature illustrates.",
        position="15.1",
    ),
    "QBS": VariableHelp(SERVICE, "Flow rate at the service pump.", position="13.2"),
    "QGL": VariableHelp(
        GAS_LIFT,
        "Gas-lift flow rate: the gas injected to lighten the produced column when the reservoir "
        "can no longer lift it on its own.",
        position="13.3",
    ),
    "T-JUS-CKP": VariableHelp(
        TOPSIDE,
        "Temperature downstream of the production choke, which swings with each slug. The fluid "
        "here can come from several wells at once, but the reading is kept because there is "
        "usually no temperature sensor upstream of the choke.",
        position="2.4",
    ),
    "T-MON-CKP": VariableHelp(
        TOPSIDE, "Temperature upstream of the production choke.", position="2.5"
    ),
    "T-PDG": VariableHelp(
        DOWNHOLE, "Temperature at the permanent downhole gauge.", position="14.2"
    ),
    "T-TPT": VariableHelp(
        TREE,
        "Temperature at the tree transducer, also considered reliable. Flowing fluid keeps the "
        "tree warm, so this reading collapses whenever production stops and is the quickest "
        "confirmation that it did.",
        position="15.2",
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
            "panels in this viewer read <i>not recorded</i> or <i>flat</i>. The Availability page "
            "counts them, sensor by sensor."
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
    (
        "How slow the events are",
        (
            "The 2.0.0 article shows a severe slugging instance with pressure oscillations above "
            "10 bar and says nothing of their period. Measured on the real instances with the "
            "spectrum view, severe slugging on WELL-00014 cycles every 50 to 90 minutes, the "
            "period drifting from 90 minutes on 18 September 2017 to 51 by 28 October; flow "
            "instability on WELL-00001 cycles every 45 minutes, with up to 95 % of the power in "
            "that one line; the pressures of a spurious DHSV closure oscillate every 45 to 80 "
            "minutes; a normal instance has no line to speak of, 1 to 2 % of the power in its "
            "strongest one. A six-hour instance therefore holds four to seven cycles of the "
            "events, which is why the viewer's spectral axis is a period rather than a frequency, "
            "why the default spectrum is taken over the whole stretch, and why the spectrogram of "
            "a single instance says little at those periods."
        ),
    ),
]

# What the availability page shows, for the help tab of the same name.
AVAILABILITY_INTRO = (
    "Every real instance carries every column the dataset declares, whether or not the well had "
    "the sensor, so what was actually recorded is a question of its own, and the "
    "<b>Availability</b> page answers it. Its rows are groups of instances (the fault classes, "
    "the wells, or the instances of one well or of one fault class, one by one) and its columns "
    "the sensors; every cell splits the samples of its row into three states, side by side from "
    "the left, so that the fuller the cell, the more of the sensor there is:"
)

# The kinds of cell of the availability page, in the order of the key: the
# swatch name (``heatmap.SWATCH_KINDS``), what to call it, what it means.
AVAILABILITY_STATES: list[tuple[str, str, str]] = [
    ("live", "Live", "Samples carrying a reading that moves over the instance."),
    (
        "frozen",
        "Frozen",
        (
            "Samples carrying a reading, but one single value from end to end: a dead or "
            "disconnected instrument, which a count of readings alone would pass off as "
            "available. The rule is the one the instance window marks a plot <i>flat</i> by, so "
            "the two never disagree about a sensor. A valve state (the ESTADO variables) is never "
            "frozen: a valve that holds one position for a whole recording is a fact about the "
            "well, so those variables are only ever absent or live."
        ),
    ),
    (
        "absent",
        "Absent",
        "Samples carrying no reading: the well does not have the sensor, or lost it.",
    ),
    (
        "implausible",
        "Implausible",
        (
            "The mark of a reading no instrument could have produced, in at least one instance "
            "of the row: a negative absolute pressure, a temperature outside the band below, a "
            "magnitude beyond 1e8. Such a sensor is still live, since its readings are there and "
            "move, but what they say is not a measurement. Hover the cell for how many "
            "instances, and the plots of the instance window call the readings out in the same "
            "amber."
        ),
    ),
]

# Why each plausible range is what it is, per unit of ``config.PLAUSIBLE_RANGES``:
# the quantity, and the reasoning of the ``flowml`` survey of 3W 2.0.0.
PLAUSIBLE_RANGE_NOTES: dict[str, tuple[str, str]] = {
    "Pa": (
        "Pressures",
        (
            "Absolute pressures (table 3 of the paper), so a negative reading is impossible; 106 "
            "files of 3W 2.0.0 carry one, usually for the whole recording, a broken or mis-mapped "
            "tag the paper itself warns about. Zero is left alone: a sensor frozen at zero is "
            "another defect, and shows as frozen."
        ),
    ),
    "°C": (
        "Temperatures",
        (
            "The floor is below every genuine reading of the dataset (T-TPT reaches -33.8 °C "
            "during a blowdown, which is real: the cooling of a gas expanding is exactly the "
            "condition hydrates form in) and the ceiling twice the hottest one (127.7 °C). The "
            "band catches the sentinels -999 and -99.99 the plant's information system leaks "
            "into the data, and T-PDG readings of 30,000 °C."
        ),
    ),
    "%": (
        "Choke openings",
        (
            "Percentages, so a negative reading is impossible; one well reports an opening of "
            "-99.99 %, a sentinel."
        ),
    ),
}
MAGNITUDE_NOTE = (
    "Every variable, these included, must also stay below <b>1e8</b> in magnitude: some sensors "
    "are frozen at absurd levels (one well reports P-PDG = -1.2e42 Pa for whole instances) or "
    "off by orders of magnitude (P-JUS-CKP around 1.4e9 Pa, that is 14,000 bar), and a survey of "
    "every instance of 3W 2.0.0 found a clean gap around this limit, the largest varying reading "
    "below it being 4.9e7 Pa and the smallest value above it 1.3e8, so the limit removes no real "
    "signal, which matters because genuine spikes are fault signatures. Valve states and flow "
    "rates are held to this rule only."
)

AVAILABILITY_NOTES = [
    (
        "Sensor pairs",
        (
            "The <b>Sensor pairs</b> matrix puts the sensors on both axes and asks what no column "
            "of the first matrix answers: how often two sensors carry a reading <i>at the same "
            "instant</i>. Two sensors can each cover half a recording and never overlap, so a pair "
            "can be empty however well covered each of its sensors is, and a pair with little "
            "coverage is one no model can train on and a correlation nobody should trust — the "
            "point of Rabelo's figure 2.10. The diagonal is each sensor's own coverage, the "
            "<i>Over</i> box counts the pairs over every real instance or over those of one fault "
            "class or one well, and <i>Count</i> asks either that both sensors be live in an "
            "instance for it to count, or merely that both be recorded, frozen readings included, "
            "which is how Rabelo counts. Of the 351 pairs of 3W 2.0.0, 102 never carry a reading "
            "at the same instant. The footers cannot answer this one — a count of missing values "
            "says how much of a column is there, not which samples — so the first look reads the "
            "data, behind a progress dialog, and keeps the result in the cache.<br><br>"
            "<i>Join overlapping instances</i> changes the answer here rather than merely the "
            "arithmetic: a sensor one window did not record may be there in the window it "
            "overlaps, so two sensors that never share a sample inside one window can share "
            "plenty inside the recording the windows were cut from. And <i>Sensors: grouped by "
            "co-occurrence</i> lays the sensors out so that those recorded at the same instant "
            "sit together — a spectral seriation, the sensors placed on a line by the second "
            "eigenvector of the Laplacian of their overlap — which turns the blocks of the matrix "
            "into the sets of sensors a well carries or lacks together, and those sets are what "
            "say which subsets of the dataset a model could be built on at all."
        ),
    ),
    (
        "How the shares are counted",
        (
            "Shares are of samples: every sample of every instance in a row is absent, frozen or "
            "live, so the three parts of a cell add up to the whole cell, and a sensor recorded "
            "for part of an instance shows as partly absent. A sample two overlapping instances "
            "share is counted in both, once per instance; joining the instances first is not "
            "applied here yet. The last row folds every instance shown, and <i>Sensors: By "
            "coverage</i> orders the columns by it, the sensor live in the largest share of the "
            "samples first."
        ),
    ),
    (
        "Where the figures come from",
        (
            "The footer of every parquet file keeps, per column, a count of the missing values "
            "and the smallest and the largest value, so what every sensor recorded is read "
            "without reading the data, in the same pass that reads the labels, and cached with "
            "the catalogue. A file written without those figures is read in full instead."
        ),
    ),
    (
        "What 3W 2.0.0 shows",
        (
            "Four variables are recorded by no real instance at all: the service line's pressure "
            "and flow rate (P-JUS-BS, QBS), the pressure upstream of the production shutdown "
            "valve (P-MON-SDV-P) and the tree pressure downstream of the wing valve (PT-P). The "
            "downhole gauge is the cruel case the papers describe: its pressure (P-PDG) is frozen "
            "in more than half of the real instances and its temperature (T-PDG) in over a third. "
            "The pressure downstream of the production choke and the temperature upstream of it "
            "(P-JUS-CKP, T-MON-CKP) hardly exist outside the Hydrate in Production Line folder. "
            "And 113 instances on 18 wells carry a reading outside the plausible range, most often "
            "a negative pressure downstream of the gas-lift choke or a downhole gauge frozen at an "
            "absurd level."
        ),
    ),
    (
        "Why it matters for a model",
        (
            "Rabelo finds that the three sensors with the least coverage in the dataset (T-PDG, "
            "QGL, P-JUS-CKGL) are also the three his models lean on least, and the five with the "
            "most (P-TPT, P-PDG, P-MON-CKP, T-TPT, T-JUS-CKP) the ones they lean on most: a "
            "sensor has to be there to be learned from. His pipeline drops the columns that are "
            "entirely missing, forward-fills gaps of up to a minute, and drops an instance when "
            "more than half of its P-TPT samples are missing, which is what the absent share of "
            "a cell says such a rule would cost."
        ),
    ),
]

AVAILABILITY_SOURCES = (
    "Sources: the availability map of <b>G. Rozo</b> (the <i>main.ipynb</i> notebook of his "
    'fork of the 3W repository, <a href="https://github.com/GabrielRozo123/3W/blob/'
    'new_3w_datasets_overviews/dataset/demos/GabrielRozo/main.ipynb">github.com/GabrielRozo123/3W'
    "</a>, 2026), which measures the share of missing readings per sensor and event class on a "
    "sample of twenty events per class; the <b>final graduation project of G. Rabelo de "
    "Oliveira</b>, <i>Análise e modelagem integrada de dados de garantia de escoamento</i> "
    "(Universidade de Brasília, 2026, in <code>docs/papers</code>), whose section 2.3.2 measures "
    "the missing data per sensor and class (figure 2.8), the coverage of every sensor (figure 2.9) "
    "and of every pair of sensors (figure 2.10), and whose section 5.3.1 relates coverage to what "
    "the models learn; and the <b>flowml</b> pipeline, whose cleaning rules the plausible ranges "
    "are. This page counts the real instances only, and every one of them, where both studies "
    "count every kind of instance and Rozo a sample of them."
)

# How to work the viewer, shown in both windows.
USAGE = {
    "Timelines page": [
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
        (
            "Tick 'Join overlapping instances' to merge the instances of a well that overlap in "
            "time into one bar wherever their labels agree on the shared stretch (an unlabeled "
            "sample agrees with anything). Instances whose labels disagree there stay apart, so "
            "the overlaps left are exactly the labeling conflicts. A bar joined from instances of "
            "several fault folders is striped with every folder's color and says how many more "
            "instances it joins after its timestamp; clicking it opens them as the single "
            "continuous recording they were cut from."
        ),
        (
            "'Bar color: Availability of a sensor' tints every bar by the share of its samples in "
            "which the chosen sensor is live, faint for a few and full for all, grey under the "
            "frozen key for a sensor that never moved, empty for one never recorded, so the grid "
            "becomes the history of that sensor on every well: an era of absence, or a scattering "
            "of it. The key above the grid changes with it."
        ),
        (
            "A small amber triangle in the corner of a bar marks an instance in which a sensor "
            "reads outside its plausible range; the status bar names the sensors. Tinted by one "
            "sensor, the mark is for that sensor alone."
        ),
    ],
    "Availability page": [
        (
            "Every column is a sensor and every row a group of instances: choose the fault "
            "classes, the wells, or the instances of one well or of one fault class in the Rows "
            "box. The last row folds every instance shown."
        ),
        (
            "A cell splits the samples of its row into live, frozen and absent, left to right, in "
            "the colors of the key at the right of the toolbar; the fuller the cell, the more of "
            "the sensor there is. A small triangle in its corner marks a reading outside the "
            "plausible range."
        ),
        (
            "Hover a cell for the shares, the instance counts, the extreme readings and the "
            "implausible ones; hover a sensor's name for what it is and its plausible range; "
            "hover a row's label for what the row holds. A tooltip carries the figure the cell "
            "draws, where the pointer is, as a printed availability map writes it inside the "
            "cell; the status bar carries that and the rest."
        ),
        (
            "The 'Matrix' box switches to 'Sensor pairs': the sensors on both axes, every cell "
            "the share of the samples in which both carry a reading at the same instant. The "
            "'Over' box counts them over every real instance or over one fault class or one well, "
            "and 'Count' asks either that both sensors be live or merely that both be recorded."
        ),
        (
            "In the pair map 'Sensors' offers a third order, 'Grouped by co-occurrence', which "
            "puts the sensors recorded at the same instant next to one another, so that the "
            "blocks of the matrix read as the sets of sensors a well carries or lacks together "
            "rather than as a ranking. 'Join overlapping instances' applies here too, and changes "
            "what the map says: a sensor one window missed is filled in by the window it overlaps."
        ),
        (
            "Click a fault class or a well, on its label or on any of its cells, to see its "
            "instances one by one; the Rows box takes you back. Click an instance, on its label "
            "or on a cell, to open its time series with that sensor drawn."
        ),
        (
            "'Sensors: By coverage' orders the columns by the share of what is on show in which "
            "each sensor is live, largest first."
        ),
        (
            "'Cells' splits each cell by samples, so that a six-day instance weighs more than a "
            "six-hour one (as Rabelo counts), or by instances, each weighing the same (as Rozo "
            "counts); the two disagree because instances range from hours to days."
        ),
        (
            "'Available from' sets the share of its samples a sensor needs readings in to count "
            "as available in an instance at all; below it the instance counts as absent for that "
            "sensor, readings and all. Rabelo's pipeline drops an instance whose P-TPT is more "
            "than half missing: 50 % shows what that rule keeps."
        ),
        (
            "'Join overlapping instances' counts the bars the timelines draw when joined: "
            "overlapping instances whose labels agree, read as the single recording they were cut "
            "from, in which a sample two windows share is counted once and a sensor one window "
            "missed is filled in by another. The footers of the files cannot say which instants "
            "two windows share, so the first tick reads the data, behind a progress dialog, and "
            "keeps the result in the cache."
        ),
    ],
    "Faults page": [
        (
            "Pick a fault: every real instance of it, from every well, is drawn in the color of "
            "its well on a time axis that starts where the event begins in it, so the shapes line "
            "up whatever the clock said; 'Align at' chooses that moment, the onset of the "
            "transient, of the steady state, or the start of the recording."
        ),
        (
            "'Layout' chooses between the two. <b>Small multiples</b>, the default, give every "
            "instance a plot of its own in a grid under a heading per feature, each with its own "
            "value axis and its label periods shaded behind the trace — hatched where nobody "
            "labeled it, as everywhere else in the viewer — so that two dozen shapes can be read "
            "one against the next; 'Columns' sets the width of the grid and 'Axis' "
            "puts every plot on its own value axis or all of them on one, which says how far "
            "apart the levels are and flattens most of the plots saying it. <b>Overlaid</b> draws "
            "them all on one set of axes. The grid opens on the stretch of time most of the "
            "instances cover, so that one instance recorded for days does not leave every other "
            "plot a sliver; Ctrl + wheel zooms out to the rest."
        ),
        (
            "An instance whose labels never reach the moment chosen cannot be aligned on it and "
            "is greyed out in the list on the right. Beyond two dozen instances the earliest are "
            "ticked to start with, and the grid draws at most four dozen of them; tick and untick "
            "to choose, All and None do it at once."
        ),
        (
            "'Normalize per instance' scales every series to its own level, each reading as "
            "standard deviations from the mean of that sensor over the whole instance, which is "
            "how Rabelo's pipeline normalizes: wells run at different levels, and the shape of "
            "the change is what the instances share. 'Show … h before/after' narrows the plots "
            "to the hours around the onset; at zero, everything recorded is drawn."
        ),
        (
            "Hover a line to bring it forward and name it, with the label, the well status and the "
            "readings of that instance at that moment in the status bar; pointing at an instance "
            "in the list does the same. Readings outside the plausible range are left out of the "
            "value axis, so one broken gauge does not flatten every other line; the instance "
            "carrying them wears the ⚠ in the list."
        ),
        (
            "'Signature' ticks the variables whose joint behavior identifies the event, for the "
            "events the 2.0.0 article illustrates; features no instance of the fault recorded are "
            "greyed out."
        ),
    ],
    "Instance window": [
        (
            "One block per bar of the overview, stacked in chronological order on one shared time "
            "axis, so the stretches they share line up vertically. The band at the very top marks "
            "those stretches."
        ),
        (
            "A bar the overview has joined opens as one block: its instances are read as the "
            "single continuous recording they were cut from, drawn as one series over one set of "
            "bands, with a dashed line where each further instance begins. Every instant appears "
            "once, and what one window says nothing about the others fill in — so the label band "
            "of a merged recording carries far less Unknown than its instances did apart, which "
            "is what a model trained on it would see, unlabeled samples being dropped. Each "
            "stretch keeps the color of the file that labeled it, so a normal period labeled by a "
            "Normal Operation file stays that file's color inside a recording that goes on to "
            "develop a fault."
        ),
        (
            "'Join overlapping instances' is in this window's toolbar too, and merges exactly the "
            "instances on screen: the group the window opened on is all it is about, so two of "
            "them that overlap only through an instance outside the window stay apart, and what "
            "the well as a whole would join is not brought in. It changes this window alone, and "
            "turning it off lands where it started. A window opened from a bar the overview had "
            "already merged is showing that merge, so its box is ticked and disabled."
        ),
        (
            "Tick features on the left to add a plot of them to every instance. The plots of one "
            "feature share their value axis, so the same reading sits at the same height in all of "
            "them. 'Features' in the toolbar, beside 'Join overlapping instances', hides that "
            "panel to give the plots its width; the choice survives a join toggled or a new group "
            "opened."
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
        (
            "A reading outside the plausible range is drawn in amber over the trace, sample by "
            "sample, so the stretch that is garbage is seen for what it is; the panel's figures "
            "call it out, the header of the block names the sensors, and the feature's checkbox "
            "wears a ⚠."
        ),
    ],
    "Signal views": [
        (
            "The 'Views' boxes of the instance window add, to every feature plot, up to three "
            "views of the same signal, each placed where it shares an axis with the trace. "
            "<b>Distribution</b> is a histogram turned on its side to the right of the trace, on "
            "the trace's value axis, its bars stacked by label period in the class colors, so "
            "that how the event moves the readings is seen inside one instance; a bimodal shape "
            "is an oscillation. A solid line marks the mean and a dashed one the median. "
            "<b>Spectrogram</b> sits under the trace on the shared time axis, the period up its "
            "side and the power as a shade. <b>Spectrum</b> sits beside the spectrogram sharing "
            "its period axis, or, on its own, in the spectrogram's place with the period along "
            "the bottom; whenever it is on, one cycle of its dominant period is laid as a bar "
            "against the trace, so the claim can be checked against the waves."
        ),
        (
            "The histogram and the spectrum are counted over the stretch of time on screen, so "
            "zooming the trace is brushing: narrow the view to a stretch and read its "
            "distribution and its spectrum. The spectrogram covers the whole recording. A merged "
            "recording is transformed as the single series it is, never stitched from its parts."
        ),
        (
            "The spectral axis is the <b>period</b>, logarithmic, from two seconds up to the "
            "length of the stretch, and not a frequency: the events are slow — severe slugging on "
            "WELL-00014 cycles every 50 to 90 minutes, flow instability on WELL-00001 every 45 "
            "— which in hertz reads 0.0002 and says nothing. The spectrum is Welch's estimate of "
            "the power spectral density, the mean and the linear trend removed first (a trend "
            "would otherwise own every long period), the missing samples interpolated (the grid "
            "is a fixed 1 Hz and the holes are rare), readings outside the plausible range left "
            "out. A frozen sensor, or a stretch with fewer than half its readings, gets a note "
            "instead."
        ),
        (
            "'Segment' sets the length of the segments the spectrum averages over and the "
            "spectrogram is sliced into, once 'whole stretch' is unticked; 'Overlap' how much "
            "each repeats of the last; 'Window' the taper. Nothing longer than a segment can be "
            "resolved, and the plots grey the periods beyond it rather than leave them silently "
            "empty. With 'whole stretch' ticked the "
            "spectrum is the periodogram of everything on screen, which is the only way to see "
            "the slugging line: a segment of five minutes, the size a pipeline windows by, holds "
            "no cycle of it. The spectrogram then slices the recording into eighths, so on a "
            "six-hour instance it resolves periods up to three quarters of an hour and says "
            "something about the shorter ones only; over a merged recording of days it shows the "
            "period drifting. 'Bins' is the number of bins of the histograms."
        ),
        (
            "The caption of a spectrum gives its <b>dominant period</b> and the share of the power "
            "in it: a few percent for a normal instance, whose power is spread thin, half or more "
            "for an oscillating one. The period is looked for among those the stretch holds at "
            "least four cycles of, so a trend is not mistaken for a line."
        ),
        (
            "On the Faults page the 'Domain' box draws every instance of the fault in one of the "
            "three domains — time series, distribution, spectrum — in either layout, over the "
            "stretch the hours before and after the onset select, so '2 h after' gives the "
            "spectrum of the fault alone. Overlaid spectra read together where overlaid traces "
            "did not, since the question is whether their peaks line up; histograms are drawn as "
            "a share of each instance's samples, so instances of different length compare, with "
            "the mean and the median of each as lines in the grid, and 'Normalize per instance' "
            "puts those of different wells on one z-score axis. The second row of the toolbar "
            "holds the hours around the onset, the normalization and the parameters of the "
            "domain chosen; 'Features' and 'Instances' at the right end of the first row hide "
            "the feature panel and the instance list to give the plots its width."
        ),
        (
            "There is no phase spectrum of a single signal: the phase of a transform at a period "
            "is the instant inside the record at which that cycle peaks, so it depends on where "
            "the file happens to begin and tells nothing the trace does not. The phase "
            "<i>difference</i> between two sensors over the same stretch is meaningful, and is "
            "left for a later version."
        ),
    ],
    "Everywhere": [
        "Drag a plot to pan it. Ctrl with the mouse wheel zooms; the wheel alone scrolls the page.",
        "Ctrl+R resets the views of the window, F1 opens this help.",
        (
            "The Theme box of the main toolbar switches the windows and the plots inside them "
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
