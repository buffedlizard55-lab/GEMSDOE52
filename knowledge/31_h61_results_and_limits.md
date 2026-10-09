# H61 results and limits — deep-sharp two-view co-training

**Verdict: `NEGATIVE`. Download for research: YES.
Submit to the competition: NO. Competition slots used: 0.**

Artefact `gems52-h61-deepsharp-cotrain-37600px.tif`, SHA-256 `7c86853164f9cfa7aea34de029c7d5ccf3a6b43dbbb2b14de570e558384d2755`, 131,771 bytes,
37,600 emitted cells of exactly {0, 1} with 0 NaN.
Preregistered before any fit in `knowledge/30_hypotheses_H61_preregistered.md`
(SHA-256 `e2cbec44c3c5fb2f8a85b3238ca95109628f17da8faca69de56e2065101c5344`); `scripts/run_h61.py` refuses to run if that hash moves.
This document was rendered from the receipts by `scripts/h61_knowledge.py`; no number here was typed
by hand.

## 1 · The primary result: View A does not transfer, so co-training has nothing to transfer

Blum and Mitchell's guarantee needs two views that are each *sufficient* for the class and
approximately conditionally independent given it. On the corrected label-blind quadrant splitter
the second condition holds and the first does not:

| fold | View A OOF AUC | View B OOF AUC | View A in-sample | View B in-sample |
|---|---:|---:|---:|---:|
| 0 | 0.5062 | 0.6625 | 0.9481 | 0.8762 |
| 1 | 0.6011 | 0.7684 | 0.9251 | 0.8367 |
| 2 | 0.4668 | 0.6112 | 0.9201 | 0.8501 |
| 3 | 0.4910 | 0.6952 | 0.9135 | 0.8491 |
| **mean** | **0.5163** | **0.6843** | | |

View A is the potential-field/subsurface view (36 channels, including the
external upward-continued TMI). It fits its own quadrant at AUC 0.948
and predicts **chance** in the next one (0.516). View B — DEM curvature and slope, band 6
(radiometric total count) and the external K, Th, U, Th/K, U/K, U/Th — reaches 0.684. A
sufficient view cannot be at chance out of sample, so the A→B transfer hands View B noise. This is
the mechanism behind the failed disagreement arms in H55, H56, H57 (A-only density 0.000785 against
a matched random control of 0.001057), H59 and CTD5: those rounds all reported weak or negative
disagreement arms without ever measuring *why*. H61 measures why.

Diagnostics that were clean, so the failure is the premise and not the plumbing:

* leakage canary on all 73 channels, every
  fold, held-out sample: maximum direction-insensitive AUC 0.6687 against
  an alarm at 0.9; fitted single-feature canary on the five strongest
  0.6666. **No alarm.**
* independence screen on 2089 50×50 px blocks of held-out
  catalogue-zero proxies: max |ρ| = 0.1331 against an
  abandon threshold of 0.6 → exchange **allowed**. Weak proxy-error
  correlation is not proof of conditional independence, and it is not evidence of sufficiency either.
* exactly one exchange, 15,441 pseudo-label pixels in whole segments inside
  the training domain; refit changed held-out AUC by
  0.0114 (A, fold 0) —
  i.e. nothing, as expected when the donor has no signal.

## 2 · HOLDOUT-DTI, matched budget for the first time in this lane

Evaluator `gems52-pooled-hide-v1`, 53,186 withheld
positive pixels, pooled TPw/FPw/FNw, α 0.2, β 0.8, 300 m triangular kernel, 95% paired
physical-cluster bootstrap (153 clusters,
1000 draws). Every arm placed exactly
9,400 dots per fold at 3 px minimum
separation — all arms filled their budget, so the comparison is eligible.
CTD5's primary comparison was ineligible precisely because its candidate arm filled 2,041 of 3,058
requested dots; H61 fixes that by ranking a field that is finite over the whole allowed domain
instead of thresholding a hard mask.

| arm | HOLDOUT-DTI | 95% CI |
|---|---:|---:|
| single_A | 0.071954 | [0.056636, 0.088566] |
| single_B | 0.174517 | [0.152316, 0.196299] |
| union_max | 0.148981 | [0.128084, 0.169418] |
| disagreement_pre | 0.033293 | [0.023815, 0.044556] |
| **disagreement_post** | 0.030584 | [0.020940, 0.042238] |
| random | 0.080426 | [0.070223, 0.090973] |

Best comparable control: `single_B`. Paired differences against the
candidate: single_A Δ -0.041370 [-0.054559, -0.027645], single_B Δ -0.143933 [-0.167383, -0.121183], union_max Δ -0.118397 [-0.139437, -0.097697], disagreement_pre Δ -0.002709 [-0.007519, 0.003072], random Δ -0.049841 [-0.060303, -0.039698].

**Instrument validity, stated before the numbers are used for anything.**

1. This simulator measured Spearman −0.10 against the owner-reported board in round R4, and uniform
   random beat the champion on it. It screens procedures; it does not promote. No value above is a
   score or a leaderboard forecast.
2. **Prevalence mismatch, measured.** The folds withhold 53,186
   catalogue pixels = 1.04% of
   the eligible footprint, whereas the hidden truth is
   0.12–0.25%
   of it. The simulator is therefore 4.3–8.9×
   richer in truth than the real task, which makes every density measured here **optimistic** for the
   competition. The candidate is already below uniform random at that inflated prevalence, so the
   negative verdict does not depend on this correction.
3. The folds hide *catalogue* components. The competition's hidden truth is expert-drawn
   **off-catalogue** structure more than 200 m from any mapped trace, which is a related but not
   identical recovery task.

## 3 · Repaired organiser-score algebra (measured from pinned bytes)

`scripts/h61_forensics.py` → `evidence/h61_forensics.json`. Eligible footprint
5,103,406 px; catalogue 60,988 px.

* **Masked support.** Known catalogue pixels are masked out of evaluation, so `S` counts off-catalogue
  pixels. Witness: `Hedge-v2` and `ens12-7f00890a` have identical off-catalogue support
  (Jaccard 1.000) and identical reported scores, yet raw-`S` accounting gave them credit
  8873.5 vs
  7168.8; masked accounting gives
  both 6967.0.
* **|G| is an interval: [5,949.3, 12,512.1] px.** Thirteen scores
  give thirteen equations in fourteen unknowns. Lower bound binds on
  `calib_8GEMSDOE_Hedge-v2_submission`; upper bound on the nested pair
  `scored_d15_scored` ⊂ `scored_gems27_tgc_v2_d15`
  (0.2477 > 0.2449 with fewer pixels).
  The previously published point value
  14,088.7 px is **outside** that interval; it needs the
  6,436 px the champion deleted to earn exactly zero credit, and
  12333 px is what
  25 credit of ring income alone does to it.
* **Nested lattice, measured:** A ⊂ B ⊂ E, A ⊂ E, C ⊂ D, C ⊂ E, and Hedge-v2 ≡ ens12
  (`evidence/h61_forensics.json → subset_pairs`). The reported-0.2778 champion added **zero** pixels
  to the reported-0.2600 file and deleted
  6,436, every one of them between
  100 m and
  200 m of a mapped trace;
  the champion's own nearest dot is
  223.6 m away. **That pruning, not
  a better detector, is the score.**
* **Band 6 is radiometric total count.** Spearman
  1.0000 against the independently derived
  external TC grid, 0.0175 against the tilt angle
  of TMI computed from bands 9 and 3, and
  -0.1512 against `tmi_hg` — on
  400,000 eligible pixels. The input file's own description
  ("tc - Tilt angle or total curvature - magnetic field derivative for edge detection") is contradicted by its bytes. Units remain
  unauthenticated.
* **Attribution strength is not uniform.** Only
  3 of
  13 owner-reported scores are hash-linked to the bytes held. The champion's token
  `e5eb6e7e` matches none of six hash conventions of the file we hold, and GEMSDOE32's own page says
  no organiser score exists. Everything here is **OWNER-REPORTED, NOT ORGANIZER-CONFIRMED**.

## 4 · Lane gate: the literal rule, the saturation repair, and what they say about this file

The 526-blob census was re-materialised and SHA-verified (`scripts/fetch_prior_inventory.py`:
545 rasters checked, 364 distinct decoded
patterns). The 13GEMSDOE spacing-five lattice has 3 px coverage
1.0000
of the eligible footprint, so the literal "70% of dots within 3 px" rule returns DUPLICATE for
**every** nonempty raster — which is why CTD5 stopped. The repair classifies a prior with measured
coverage ≥ 0.95 as a universal-coverage probe, applies the literal rule to informative
priors, and still reports the literal statistic for every prior.

| verdict | max Spearman | max near-dot fraction | source |
|---|---:|---:|---|
| literal (all priors) | 0.0361 | 1.0000 | `cd838daadd39de3ccdb9d30025b7feacc4d87c9f.tif` |
| policy (informative priors) | 0.0209 | 0.8788 | `4e50a598eae16b3c098ca2653542dc142f1da8a8.tif` |

Surface phase before placement: literal `PASS`, policy
`PASS`. Probes measured: 14; informative
priors: 531. Decoded-pattern uniqueness:
PASS; literal union of the
priors: NO; novel support
fraction 0.0000.

**Why the literal rule fires, measured against chance.** The directed statistic has a chance level
equal to the prior's own 3 px coverage, because a uniformly random emission lands inside that halo with
exactly that probability. Of 545 registry rasters,
31 have coverage at or above
the rule's own 0.70 trigger. Of 23 near-offenders,
14 are probes, and **all
9 informative ones have coverage
0.7583–0.8976
with negative excess over chance**
(-0.0291
to -0.0054).
Across the whole registry the median excess is
-0.0766 and only
108 of
545 priors are positive: this emission is *less* clustered near
prior dots than uniform chance, and its maximum Spearman is 0.0361 against a 0.90
trigger. The preregistered threshold was **not** relaxed — the STOP stands and the artefact stays
research-only — and the prospective fix (apply the rule only to priors whose coverage is below its own
trigger, or test the chance-normalised excess) is handed to the shared selector. [IR-H61-009]

Re-measured with the same instrument, two inherited artefacts are placed correctly: **CTD5** has
informative-prior near-dot fractions of 0.1063–0.1368 and |ρ| ≤ 0.0046 — its STOP was entirely the
probe, so the repair vindicates its own diagnosis. **H60C** has near-dot fraction 0.7929 against the
champion and 0.8087 against `h19-5`, with Spearman 0.7083: DUPLICATE/STOP under the literal rule
*and* under the policy, because those priors are informative. H60C's published gate used
support-novelty and Jaccard and never applied the brief's rule; it is flagged as IR-H61-007 and is
neither promoted nor deleted here.

**Concurrent closure.** The parallel R5 and H60D rounds merged into `main` after the census was
frozen, so the unchanged emission was re-checked against the
2 newly added decoded patterns
(`scripts/h61_concurrent_closure.py`): verdict **PASS**,
max near-dot 0.1894 (H60D, coverage
0.1713),
max Spearman 0.0037. The artefact was not rebuilt,
re-placed or re-tuned for that check, and a pass there does not overturn the recorded STOP.

## 5 · Not the union of the two views

72,966 cells differ from the `max(A, B)`
emission, 69,594 from View A alone and
75,200 from View B alone;
1,117 dots coincide with the union emission
(Jaccard 0.0151), and the field's Spearman against
`max(A, B)` is 0.0051. A high-A/middle-B pixel and a
high-A/high-B pixel have the same union score and opposite disagreement scores, so the field is not a
rescaling of the union. Strict A-only candidates (donor rank ≥
0.95, receiver rank inside
[0.35, 0.65]): 55,193 px,
of which 594 are emitted cells.

## 6 · The projection, which is never a score

DTI = T / (0.2·(T + S − M) + 0.8·(|G| − T)); with sparse dots M ≈ T, so DTI = d·S / (0.2·S + 0.8·|G|)
for credit density d. At S = 37,600 dots the break-even density to
match the reported champion is
**0.0907–0.1295**
per emitted pixel (8.3–5.6×
uniform random, which is 0.0230–0.0109).
If the arm's density equalled its HOLDOUT-DTI density
(0.0409), the projected DTI would be
0.1251–0.0876
— below the champion at both ends. Pixels outside all thirteen scored files belong to no identified
atom, so organiser-tied evidence bounds their credit only by [0, |G|]: neither "worthless" nor
"valuable" is proven, and the holdout density comes from an instrument that does not predict the
board. **No leaderboard gain is claimed, and none is projected.**

## 7 · Limits

1. The shipped surface is an out-of-fold mosaic of four quadrant models, not one model refit on
   everything; inter-fold rank calibration and quadrant seams are unvalidated.
2. The hidden truth is expert-drawn off-catalogue structure. The holdout hides *catalogue*
   components, so it measures a related but different recovery task.
3. Inputs are SHA-256-pinned owner mirrors of a login-walled portal file. Pins prove mirror
   consistency, not organiser authentication. No organiser receipt, authenticated weekly allowance or
   live leaderboard observation was available in this sandbox, whose egress is limited to github.com,
   api.github.com, codeload.github.com, pypi.org and files.pythonhosted.org.
4. External radiometrics are uint8 percentile quantisations derived by the owner's CI from the USGS
   GeoDAWN release (DOI 10.5066/P93LGLVQ); only rank and gradient transforms are used, and absolute
   units are unauthenticated.
5. Fault candidates are not geothermal vents and establish neither permeability nor a reservoir.
   `docs/downloads/h61-a-only-reasoning.csv` gives every emitted cell a measured context, the named
   non-fault mimic (a basin-fill density boundary or volcanic lithologic contact; secondarily buried
   palaeo-channels, fan margins, dykes and flight-line artefacts in the continued field) and a
   falsifier. No geologist reviewed any structure and no field observation was collected.

## 8 · What should happen next

1. **Change what View A is.** Raw potential-field channels do not transfer between quadrants. A
   physically parameterised predictor — a modelled basement-depth step across a candidate trace, a
   strike-continuity score along an interpreted lineament, an isostatic-residual discontinuity — is a
   different object from a band value and is the obvious next candidate. Measure its out-of-quadrant
   AUC **before** building an emission.
2. **Run H61-D: cross-file credit localisation by terrain stratum.** Cross the LP atoms with slope,
   modelled cover thickness and radiometric alteration strata and bound credit per stratum, so the
   organiser's own scores say *where* hidden truth sits rather than *which prior* found it. No new
   data needed; deferred only by this round's three-experiment budget.
3. **Hand the selector a priced option, not a lane violation.** The only mass measured above the
   break-even density is inside the champion family, and emitting it is a duplicate by construction.
   That decision belongs to the selector with the weekly cap in front of it; this lane must not
   smuggle it in as "novel".
4. **Authenticate.** One submission-page receipt tying a file SHA-256 to a score would convert
   IR-H61-004 from a caveat into a calibration, and would settle whether 0.2778 exists at all.
5. **Reconcile `registry/data_manifest.json` provenance text** with the owner's score list
   (IR-H61-008) without touching the pins.

**Operational values.** Maximize P(Win): do not spend a scarce weekly slot on an arm whose only
density estimate comes from a simulator that does not predict the board, and whose projected interval
starts at zero. Own the Outcome: publish the file, the failed premise, the repaired instruments, the
provenance gaps and a working reproduction — not a hopeful story.
