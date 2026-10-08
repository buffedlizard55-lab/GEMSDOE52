# 32 · R5-H1…R5-H6 — five new geological hypotheses and one scoring item, ranked, with the gate that decides the first one

**On the name.** An earlier draft of this file called these R5-H1…R5-H6. `main` already carries three
parallel rounds named H60, H60C and H60D (with their own preregistrations, scripts, site pages and an
`IR-H60D-006` recorded specifically about a file-name collision), and `H61` is already referenced in
main's CTD5 sources. These are therefore labelled by the round that produced them — R5 — which cannot
collide with a hypothesis number another session is using. Nothing else changed.

Written before any of them is implemented, per `AGENTS.md`: read the failed experiments before
proposing new ones. Everything already tried and killed is listed in §0 so that "new" here means new
against the record, not new against memory. Layer names are the organiser's own band tags, quoted in
`knowledge/25` §6. External sources are named with a URL and an obtainability statement; where
obtainability could not be tested from this sandbox, that is said instead of assumed.

## 0. What is already tried, so these five are not repeats

Killed by an organiser score (`knowledge/03`): SGMC off-catalogue emission (0.0512 at 44k px ≈
random), lattice and scatter fields (0.0904, 0.0107, 0.0778, 0.1352, 0.0360, 0.0041), huge-budget
ridge fields (0.1461, 0.1294), fitting the catalogue itself (0.1223, 0.0286), continuous or weighted
outputs, emitting inside 200 m of a mapped trace with *this family's* field (≤0.0132 credit density
over 6,436 px).

Killed by a local instrument: H55-1 paired DEM shoulders (registered gate failed, +0.002361 vs
+0.005 required), H55-2 Th/K and U/K ratio steps as a *pixel-level* detector, H56 independence
(Spearman 0.637 > 0.60 on that round's views), H59 corroboration weighting / artefact veto / strain
ranking / halo-pool restriction / pseudo-labels-as-training, H58-A cold-discharge geothermometer
agreement (22 of 37,654 nodes emitted — support-capacity failure, `IR-H58-002`), H53 coincidence-
gated singles, R4's 74-layer stack (independence premise fired at 0.7051).

Queued and never run: H57-C antisymmetric edge coincidence across families, H57-D
conductivity–depth paired across-strike contrast, H56-4 2-m INGENIOUS temperature-probe residual
corridors, H56-6 ComCat/NV relocated-earthquake lineaments, H58-B fixed short-/long-wavelength
residual ratio. R5-H2 and R5-H3 below are *not* those two: §4 and §3 say exactly what differs.

Structural facts that constrain all five: `|G| ≈ 14,088.7` px of new-fault truth in the evaluated
footprint; the family's credit curve is `T(S) = 471.6·S^0.2284`, validated on eight files across two
families to within 4 %; the best credit density ever measured is 0.2010 on 25,502 px of *inherited*
mass and 0.1387 on the champion's 37,654 px; uniform random is 0.0279; and no per-pixel feature this
repo can compute re-ranks credit inside the champion (63 point features and 108 structure-tensor
features, best AUC 0.5453 — `knowledge/10` §6).

## R5-H1 · The trace-correction corridor: estimate where the mapped line is *wrong*

**Rank 1. Expected DTI improvement: the largest available, because it is the only hypothesis whose
target population the organiser has confirmed exists. Implementation cost: medium.**

*Layers.* `labels.tif` (the mapped traces, used as *geometry to be corrected*, never as labels to
fit); `lidar` bands 6 and 7 (`downface_max`, `upface_max` — the one-sided step of a normal-fault
scarp), 3 (`step_max`), 1 (`ex_max`), 9 (`relief`), 11 (`strike`), 12 (`valid`); `features` 12 and 19
(`det_elev`, `det_elev_slope`); `features` 2, 3, 9 (`rtp`, `tmi_hg`, `tmi_vg`) as the subsurface tie
that says whether the offset line continues under cover. External, optional and already in hand:
`data/external/gdr_qfaults_traces.csv`, 1,126 traces from the OpenEI GDR mirror of USGS Qfaults
(<https://gdr.openei.org/submissions/1391>), for trace-level dip direction and slip type.

*Physical signature.* A **perpendicular offset estimator**. For each mapped trace, walk the local
normal in integer pixel steps from −3 to +3 px (−300 m to +300 m, the metric's whole kernel support).
At each offset, score the line by three things measured on *independent* data: (i) the LiDAR
down-face/up-face asymmetry `|downface_max − upface_max|`, which is a normal-fault scarp's diagnostic
one-sided step and is near zero on a lithologic contact; (ii) the agreement between the LiDAR `strike`
band and the mapped trace's own local strike, which must stay high for a real trace and collapses at
the end of one; (iii) the second derivative of `det_elev` along the normal, which peaks at a scarp
crest. Emit the argmax of that score over the offset, **not** the mapped line, and emit nothing where
the argmax is the mapped line itself (there the organiser's pixel-exact mask already makes the
prediction worthless).

*Why it catches a fault that is missing from the catalogue.* Because the organiser says the truth
contains exactly these pixels. Verbatim, staff, 2026-09-21, forum topic 11516: "A new-fault ground
truth pixel can indeed lie within 300m of a known fault trace. Such pixels would constitute
corrections or modifications to existing fault traces. **Identifying these corrections is one outcome
we are aiming for as part of this competition.**" And the problem description, page 967: "portions of
the existing fault data may be misaligned from the true location of the surface fault, **which is the
prediction target**." A correction pixel is by construction within 300 m of a mapped trace and not on
it — the population this repo has excluded outright since R2.

*How it differs from anything implemented here.* Every emission in this repo's history either
excluded the corridor (`revealed.CORRIDOR_M = 200`, inherited by R5's `legal` set) or filled it with
a habitat field that hugs mapped traces, which is why its corridor pixels earned ≤0.0132 credit per
pixel. Nothing here has ever estimated a *signed perpendicular offset* to a mapped trace from an
independent scarp measurement. H55-1 measured paired DEM shoulders but targeted novel off-catalogue
traces and failed its registered gate on the tip/hide instruments; R5-H1 targets the corridor itself,
uses the LiDAR scarp bands rather than the 100 m DEM, and has a geometric gate that does not depend
on the disqualified hide-and-recover instrument (§A-gate below).

*Expected effect, honestly bounded.* Upside: dots placed 1–3 px from a mapped trace that is itself
0–3 px from a corrected truth trace land inside the kernel at high weight, so ρ could plausibly reach
0.2–0.4, against the best ρ ever measured here (0.2010, inherited). At ρ = 0.25 and S = 20,000,
`DTI = 5,000/(4,000 + 11,271) = 0.3275`; at ρ = 0.30 and S = 25,000, `0.4595`. Downside: the
corridor may be genuinely empty in the public chunk. This family measured 0–85 credit over its own
6,436 corridor pixels, and solving `T_B − T_A = 200.62 − 0.01424|G|` over the independent bracket
`|G| ≥ 8,128` puts that density at ≤0.0132, half of uniform random. Both readings are consistent
with the organiser's answer: the staff said truth *can* be there, not that it *is* there in quantity.
The hypothesis is worth one experiment, not one submission slot, until §A-gate passes.

**§A-gate — the frozen validation, run before any slot is spent.** Hold out whole mapped traces by
spatial fold (the four 20 km whole-block folds already built in `cotrain_r5.make_folds`, so the
held-out traces are never in the estimator's neighbourhood). For each held-out trace with ≥ 10 px,
run the estimator using only the *visible* traces and the LiDAR/DEM layers, and measure the signed
perpendicular error against the held-out trace's own pixels. Gate, all four conditions, frozen now:

1. ≥ 200 held-out traces across the four folds;
2. median |perpendicular error| ≤ **1.0 px** (100 m) — beyond 3 px the kernel weight is zero, so an
   estimator that misses by more than the mapped line already does is worthless by construction;
3. the estimator must beat the best **constant-offset control** (a single global shift, fitted on
   three folds and applied to the fourth) by ≥ **0.3 px** in median absolute error — this is what
   separates "it can locate a trace" from "it has a systematic down-thrown bias";
4. the fraction of held-out traces whose argmax offset is exactly 0 must be ≤ 0.5, otherwise the
   estimator is reproducing the input and emitting nothing.

If the gate passes, the estimator has demonstrated the one thing the hypothesis needs: that an
independent scarp measurement can locate a fault trace to within a pixel where the trace itself is
not given. If it fails, R5-H1 is recorded as refuted with the numbers, and the corridor stays
excluded — on evidence rather than on a rule inherited from one family's habitat field. What the gate
**cannot** measure is whether the organiser's mapped traces are in fact offset from their truth; that
is unknowable locally and is stated as unknowable wherever the result is published.

## R5-H2 · Seismicity-azimuth corridors from the one organiser band this repo has never used

**Rank 4. Expected DTI improvement: unknown, plausibly small on its own and larger as an independent
seventh family. Implementation cost: the lowest of the five.**

*Layers.* `features` 10, `deq_n100a15` — "Distance to earthquake (n=100km radius, a=15° azimuth
parameters)", `data_category = seismic`; with `features` 16 `ieq_n100a15` ("Earthquake intensity or
density") and `features` 4/7/8 (strain-rate) as the geodetic tie.

*Physical signature.* Band 10 is not an isotropic distance field: the `a=15°` parameter makes it a
distance **within an azimuth sector**, so a pixel can be close to seismicity to the north-east and far
from it to the south-west. Rank-encode it first (its raw distribution is p1 118 m, median 623 m,
p75 1,685 m, p99 50,237 m, max ≈4.96 × 10⁶ m — the tail is "no event in the sector", which is why a
raw-value model treats 0.3 % of the footprint as an outlier of astronomical magnitude and is the
reason R4 dropped the band, `IR-R4-002`). Then take the *directional* derivative of the rank field
along the sector azimuth and keep the ridges where the rank rises steeply in one direction and falls
in the opposite one. A single active fault produces exactly that asymmetry: one block accumulates
events, the other does not. An isotropic cluster produces a ring, which the directional test rejects.

*Why it catches a missing fault.* A buried fault under basin fill has no scarp, no radiometric
contrast and no topographic expression — the three things this family's champion field ranks on — but
it still organises small earthquakes along its trace, because the stress field does not care whether
the fault is visible. Seismicity is the only channel in the file that can see a structure with no
surface expression at all, which is the definition of the population the prize exists to find.

*How it differs.* Band 10 is in **no family and no view anywhere in this repo** — verified against
`layers.FAMILIES` and `cotrain_r5.VIEW_A_RAW` this session: band 16 is in View A and in the `strain`
family, band 10 is in neither, and no script has ever read it. The queued-but-never-run H56-6
("ComCat/NV relocated-earthquake lineaments") needs an external catalogue download and event-level
relocation data; R5-H2 uses the organiser's own regridded INGENIOUS product that is already in
`data/training_features.tif`.

*External data (for validation and unit semantics only).* INGENIOUS "Earthquake Density Models.zip" →
`eq_rate_density_details.docx`, at <https://gdr.openei.org/submissions/1391>, named by DrivenData
staff on 2026-10-07 in forum topic 11557: "Those bands are the INGENIOUS earthquake rate density
layers that have been clipped to the GeoDAWN area and re-gridded to 100m." Free, no login on the GDR
landing page. **Obtainability not tested from this sandbox** — `gdr.openei.org` is not on the allowed
host list here, so this is a named source with a staff-given path, not a verified download. Stated as
such rather than claimed.

*Cost and expected effect.* One band, one rank transform, one directional derivative: hours, not days.
Its main value is structural — the six-family corroboration detector currently has mag, grav, strain,
topo, rad, sub and no dedicated seismic channel, so `strain` is doing double duty for band 16. Adding
a `seis` family makes the corroboration count a genuinely independent seven-way vote.

## R5-H3 · Basement-depth step gated by conductivity: the basin-margin fault under its own fan

**Rank 2. Expected DTI improvement: medium-high, on the population the brief calls A-only.
Implementation cost: low-medium.**

*Layers.* `features` 15 `depth_to_base_surf` ("Depth to basement surface - thickness of sedimentary
cover"), 17 `cond_surf` ("electrical conductivity of subsurface"), 18 `iso_grav_anom_hg` and 11
`iso_grav_anom_vg`, 5 `iso_grav_anom_slope`.

*Physical signature.* A three-way AND, not a weighted sum. (i) **Curvature**: the second derivative of
band 15 perpendicular to its own gradient, thresholded at the 99th footprint percentile — a
basin-margin normal fault is a *step* in cover thickness, and a step is curvature, not gradient.
(ii) **Conductivity contrast**: the down-thrown side must be more conductive than the up-thrown side
by at least the footprint's interquartile range of band 17, which is what clay-rich, saturated basin
fill against consolidated basement looks like electrically. (iii) **Gravity tie**: a co-located
maximum of band 18 (isostatic gravity horizontal gradient), because a thickness step in cover is a
density step and the isostatic residual must see it. Require all three within 1 px of each other, and
**veto any pixel where band 15 is negative** — it is a model, not an observation, and it contains
negative "depths" (footprint min −14.84), which is an artefact class the veto removes rather than
ranks.

*Why it catches a missing fault.* Basin-margin faults buried by their own alluvial fans are the
textbook missing fault of the Basin and Range: the scarp is destroyed by the fan it created, the DEM
sees a smooth apron, and radiometrics see fan sediment on both sides. What survives is the geometry of
the fill — a thickness step with a conductivity contrast — which is only in the modelled subsurface
bands. USGS/INGENIOUS mapping is scarp-based, so a fault with no surviving scarp is absent from the
catalogue by construction, not by oversight.

*How it differs.* R4 and R5 feed bands 15 and 17 to a gradient-boosted propensity as raw columns
(`VIEW_A_RAW`), so they contribute whatever a tree splits on and are never combined geometrically.
H57-D ("conductivity–depth paired across-strike contrast") was queued and never run, and was defined
as an across-strike contrast on a *pair* of bands at candidate traces this repo had already found;
R5-H3 is the perpendicular-curvature form, it generates its own candidates rather than re-ranking
existing ones, and it carries an explicit artefact veto for the negative-value class. `knowledge/03`
records the refutation of the strain fields at 100 m ("smoothed below fault-resolution"); that
argument does not transfer to bands 15/17/18, which are not strain and are not smoothed at the scale
of a basin margin.

*Cost and expected effect.* All layers are already restored and loaded by the `sub` and `grav`
families; the work is the three transforms and the veto, a day. Expected effect is medium-high
*conditional on* band 15 being a usable model — which is exactly what the negative-value rate and the
p99 of 3,420 m against a median of 316 m put in doubt. So the pre-registered check is first: measure
the fraction of the footprint where band 15 is negative or above 5,000 m, and if it exceeds 5 %, the
curvature term is computed on a winsorised rank transform instead of on raw metres, and that
substitution is recorded rather than quietly adopted.

## R5-H4 · Along-strike persistence and sign consistency of a radiometric ratio step

**Rank 5. Expected DTI improvement: medium-low alone, useful as an independent family.
Implementation cost: the lowest, tied with R5-H2.**

*Layers.* `ext` 1 (`Th/K`), 2 (`U/K`), 3 (`U/Th`); `rad` 1–4 (K, Th, U, TC); `features` 6 `tc` —
radiometric total count, whose band tag says "Tilt angle or total curvature" and whose bytes say
otherwise (Spearman with the GeoDAWN total-count grid = **+1.0000**, with K+Th+U = **+0.9915**,
`IR-52-034`; the organiser's own figure caption on page 967 says "total radiometric counts per
second").

*Physical signature.* Not the step — the *persistence of the step along strike*, with its sign held
constant. Compute the directional derivative of `ext_1` (Th/K) along the R5 strike field, then
integrate it along-strike with the persistence kernel already built and tested
(`emit_r5.persistence_length`). Keep a lineament only where the contrast **sign is the same for
≥ 2 km of contiguous strike** and the integrated magnitude exceeds the 99th percentile. The physics:
a fault juxtaposes K-poor against K-rich ground and keeps doing so along its whole length; a
lithologic contact curves, pinches and reverses; a survey flight-line artefact is straight but has no
consistent material contrast across it and reverses sign where the lines overlap.

*Why it catches a missing fault.* Windblown and alluvial cover carries the potassium signature of
what lies within a metre or two of the surface, so a fault that juxtaposes fan deposits against
bedrock leaves a *material* lineament even where it leaves no scarp. Scarp-based mapping cannot see
it; a ratio-step lineament with 2 km of sign-consistent persistence can.

*How it differs.* H55-2 ("Th/K & U/K ratio steps") was tried and refuted as a **pixel-level** step
detector at the 100 m grid, with no along-strike integration and no sign-consistency requirement —
which is the version that drowns in survey noise. The repo has applied along-strike persistence only
to its own six-family trace mask (`traces.py`, `emit_r5.persistence_length`), never to a ratio band.
The new content is the test, not the layer.

*Cost and expected effect.* Hours. Expected effect medium-low: `knowledge/10` §6 already measured that
the champion's dots sit on potassium-poor ground (AUC 0.6494 for inverted `rad_K`) *and* that
potassium habitat does not separate credited from uncredited atoms. R5-H4 therefore cannot claim that
K-depletion predicts credit; it claims only that K-depletion *persistence along a coherent strike* is
a better structural filter than K-depletion at a point, and that claim is testable against the same
atoms before anything is emitted.

## R5-H5 · Fan-apex step lineaments in low-slope ground: the buried range front's last visible trace

**Rank 3. Expected DTI improvement: medium. Implementation cost: low-medium.**

*Layers.* `lidar` 3 (`step_max`), 6/7 (`downface_max`/`upface_max`), 1 (`ex_max`), 9 (`relief`);
`features` 19 (`det_elev_slope`) and 12 (`det_elev`) as the gate.

*Physical signature.* **Steps where there should be no steps.** Take the local maxima of `lidar`
`step_max`, then keep only those in pixels whose `det_elev_slope` (band 19) is *below* the footprint
median of 3.75 — i.e. scarps in flat ground, which is what a fault scarp buried under a thin fan
looks like, as opposed to a range-front cliff where every pixel is steep. Then run the structure
tensor over the surviving maxima density at σ = 4 px and keep only pixels whose local **coherence
exceeds 0.8**, the threshold `knowledge/10` §7 measured at 16.8 % for the credited cloud against 2.2 %
for a mass-matched random cloud. The output is a set of kilometre-scale, coherent, low-slope step
lines: fan apices and deflected drainage aligned along a buried front.

*Why it catches a missing fault.* The champion field ranks on topographic roughness and potassium
poverty, which is the signature of an *exposed* range front; a buried front has low slope by
definition, so a roughness-ranked field ranks it below random (measured: this round's habitat field
scores 0.0003 on the localisation assay against 0.0275 for uniform random — `evidence/r5_budget.json`).
A step-in-flat-ground detector targets exactly the complement, and a buried front is precisely a fault
missing from a scarp-based catalogue.

*How it differs.* GEMSDOE46's `r11f-scarp-radiometric-fusion` (owner-reported 0.1589) fused scarp and
radiometric response with no low-slope gate and no coherence test, so it selected exposed scarps —
which is the population the catalogue already contains. The `topo` family uses the same LiDAR bands as
raw model features, which cannot express "step *and* flat *and* coherent over kilometres" because a
tree splits on one at a time. Nothing in the repo has combined the three.

*Cost and expected effect.* All layers restored; the transforms exist (`RV.strike_field`,
`EM.persistence_length`). A day. Expected effect medium: the low-slope gate is what makes it
complementary to everything already emitted, and complementarity is the only property that can add
credit rather than re-cover it.

## Ranking, and what the ranking is worth

Ranked by expected DTI improvement per unit of implementation cost, with the honest caveat that no
instrument in this repo can *measure* expected DTI for a novel field (`knowledge/10` §5, §6, and
§5 of `knowledge/27` for this round's replication):

| rank | id | expected improvement | cost | why this order |
| --- | --- | --- | --- | --- |
| 1 | **R5-H1** trace-correction corridor | largest: targets the only population the organiser has confirmed exists, at ρ plausibly 0.2–0.4 | medium (a day or two) | the only one of the five with an official statement that its target pixels are in the truth, and the only one with a geometric gate that does not depend on a disqualified instrument |
| 2 | **R5-H3** basement step × conductivity | medium-high | low-medium (a day) | the brief's own A-only buried-fault case, on layers no prior emission has used geometrically, with an artefact veto |
| 3 | **R5-H5** fan-apex low-slope steps | medium | low-medium (a day) | strictly complementary to the champion field, which is measured to be *below* random on that population |
| 4 | **R5-H2** seismicity-azimuth corridors | unknown; small alone, larger as an independent family | lowest (hours) | the only unused organiser band; adds a seventh independent vote to the corroboration detector |
| 5 | **R5-H4** ratio-step persistence | medium-low | lowest (hours) | a re-test of a refuted idea with the test changed, which is legitimate but is the weakest prior of the five |

**Do not spend a weekly submission slot on any of these until its own gate passes.** For R5-H1 the
gate is §A-gate above and it is frozen; for R5-H3/D/E the gate is the same one this round had to fall
back on — the emission must be judged on structure and on the prior over ρ, because the
hide-and-recover instrument is disqualified (`knowledge/10` §5) and this round reproduced the
disqualification on new data (§5 of `knowledge/27`). A hypothesis validated only on that instrument
is not validated.

## Non-geological item that outranks three of these on value per hour

**R5-H6 · Re-budget for the round that pays five times as much.** Not a geological hypothesis, listed
separately so it is not confused with one. Staff answer, forum topic 11550, 2026-10-01: "The final
re-evaluation will be on the entire GeoDAWN area." For a credit curve `T = c·S^β` the DTI-optimal
budget is `S* = 4|G|β/(1−β)`, which scales **linearly in |G|**. With the measured β = 0.2284 and the
effective `|G| = 14,088.7` this round shipped `S* = 16,681` px; if the whole-area `|G|` is 2× that,
`S* = 33,400`, and if 4×, `S* = 66,800`. One file must serve both rounds and the chunking is
undisclosed by explicit refusal, so the budget is a bet. Cost: zero compute. Deliverable: the
`DTI(S)` table under both `|G|` scenarios in `knowledge/27` §6, so the bet is placed with the numbers
in front of it rather than by default.
