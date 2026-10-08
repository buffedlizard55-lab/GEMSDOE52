# 25 — H60 preregistered hypotheses: co-training with disagreement as the discovery signal

**Lane (fixed by the session brief, verbatim method paragraph):** co-training between a
geophysical view and a surface view, with disagreement as the discovery signal (Blum & Mitchell,
COLT '98, pp. 92–100, doi:10.1145/279943.279962). View A = potential-field and subsurface
(gravity, magnetics, strain, seismicity). View B = surface (DEM-derived curvature and slope, plus
any radiometric bands present in `training_features.tif`). Independence is tested empirically on
spatial-block out-of-fold errors on labelled negatives; the method is abandoned if they are
strongly correlated. Pseudo-labels only where one view is confident and the other abstains, using
whole-segment spatial blocks and a buffer so no leakage reaches the evaluation. Discovery signal =
disagreement. Co-training can amplify bias, so compare against a single-view baseline on
hide-and-recover segments. Normalize to [0,1], write the GeoTIFF, apply the repo's metric-aware
placement, run the uniqueness gate, and confirm the output isn't merely the union of the two views.

**Written and frozen before any H60 fit ran.** Machine-readable twin:
`registry/h60_preregistration.json` (SHA-256 recorded there). Prior rounds this builds on:
H57 (`knowledge/18`), H59 (`knowledge/21`). What is NEW here, and why it is not a re-run:

- H59 scored arms ranked by `max(pA, pB)` and by *multiplicative reweightings of that union*
  (H59-A/B/E, all refuted). **No round has ever scored a field whose discovery signal is the
  disagreement itself** — H57 tested the A-only *population* as a pool (worst of eight arms),
  never the disagreement *product* as a ranking field on the pinned bytes.
- H59's out-of-fold fields came from quadrant-block folds; H60 fits them on **hide-and-recover
  whole-segment folds** (the brief's own instrument: withhold whole fault segments with a
  buffer, derive every catalogue-based feature only from the visible faults, mask visible
  faults pixel-exactly, score pooled DTI with alpha 0.2 / beta 0.8 / 300 m triangular kernel).
- The lane drift gate (rank-correlation and dots-within-3-px against every registry raster,
  checked on the ranking surface before placement AND on the final dots) is new machinery; no
  prior round measured it.

## The hypotheses

### H60-1 (primary) — the disagreement product ranks buried-structure candidates

- **Field:** `d_A = pA * (1 - pB)` over out-of-fold view probabilities.
- **Layers involved:** View A bands {1 mag_anom, 2 rtp, 3 tmi_hg, 4 geod_2ndinv (strain),
  5 grav_slope, 9 tmi_vg, 11 grav_vg, 13 grav_anom, 14 tmi, 15 depth_to_base, 16 eq_density
  (seismicity), 17 cond_surf, 18 grav_hg} each as value / |grad| / 5x5 range; View B bands
  {6 radiometric TC, 12 det_elev, 19 det_elev_slope} plus the restored external 1 m LiDAR scarp
  stack and GeoDAWN radiometric/ratio bands.
- **Physical signature targeted:** a fault buried beneath Quaternary cover produces a
  potential-field edge — a paired gravity high/low or a magnetic susceptibility step, a strain
  gradient, and an aligned seismicity lineament — while the DEM-derived surface view shows no
  slope/curvature break, so View A fires exactly where View B abstains. The product
  `pA*(1-pB)` is large only in that cell of the 2x2 confidence table.
- **Why it should catch a fault the USGS/INGENIOUS catalogue missed:** catalogue faults are mapped
  from surface expression; a trace whose surface expression is masked by alluvial cover is
  precisely the trace a surface-only mapper never draws, while its geophysical edge remains.
- **How it differs from everything already in the repo:** every prior arm was a function of
  `max(pA,pB)` (union, corroborated, vetoed, conductivity-modified) or a population pool; none
  was the disagreement product. It is also NOT the union of the two views: it is large where the
  union is *small* (B abstains).
- **Named non-fault processes that could mimic it (the run card must name them):**
  (1) alluvial-fan and basin-margin gravel wedges — density/magnetic-susceptibility contrasts
  with no fault; (2) airborne-survey drape/terrain clearance over steep topography — the GeoDAWN
  magnetics are airborne, so ridge-flank flight-line gradients mimic structure;
  (3) anthropogenic compaction (roads, canal levees) — conductivity/strain anomalies with no
  fault; (4) groundwater salinity boundaries — surface-conductivity steps unrelated to faulting.

### H60-2 (secondary) — the signed contrast is an equivalent combination rule

- **Field:** `d_C = max(pA - pB, 0)`.
- Same mechanism as H60-1, additive instead of multiplicative combination. Registered so a
  "the product won only because of its functional form" objection is decidable from the table.

### H60-3 — one co-training round (both directions) moves the ranking fields

- **Treatment:** pseudo-labels exchanged confident-donor -> abstaining-receiver, whole
  8-connected segments inside one 50x50 block each, never on a catalogue/corridor/boundary
  pixel, fold-0 fit region, both directions (A labels B, B labels A); views refit; the
  round-1 fields `pA1`, `pB1` are scored as arms against their round-0 fields.
- The family's three prior measurements of this exchange are null (−0.0159/−0.0303,
  +0.0027, −0.0011 AUC). This is the fourth, on pinned bytes, both directions, with the
  holdout DTI (not only AUC) as the readout. A null is a deliverable, not a failure to hide.

### H60-4 (characterization, never a promotion candidate) — the B-only stratum is the artifact set

- **Field:** `d_B = pB * (1 - pA)`.
- The brief: where B is confident and A is not, suspect surface artifacts (roads, erosion
  lines, canal levees, quarry faces). Measured to (a) confirm the suspicion quantitatively and
  (b) size the suppression set. It is scored for the record; the registered promotion rule
  does not allow it to ship.

### Baselines (the brief's own requirement)

`view_A` (single view), `view_B` (single view), `clf_union = max(pA,pB)` (the H59 incumbent
field), `random` (matched-budget uniform control, rebuilt per fold per budget). "Co-training
can also amplify bias, so compare against a single-view baseline on hide-and-recover
segments."

## Instruments and rules (frozen)

- **Data:** `work/pinned` — the 23-file manifest-pinned owner-mirror restore, SHA-256 verified
  before any read (integrity-pinned, NOT organizer-authenticated). Tracked `data/*.tif` stubs
  are measured and recorded as unused; never overwritten.
- **Folds:** `gems52.holdout.make_folds(mode="hide", n_folds=4, buffer_px=4, prevalence=0.002,
  seed=20261009)` — whole 8-connected catalogue components withheld, 4 px buffer,
  prevalence-matched truth; `mode="tip"` as the secondary instrument. The OOF view fields are
  fitted per fold on `fold["fit"]` (which excludes the held segments and their buffer), so
  every catalogue-based feature is derived only from the visible faults.
- **Views:** `gems52.h57` layer stack (75 cached uint8 rank layers, the template's cached
  feature stack — reused, not rebuilt), `h57.VIEW_A_LAYERS` / `h57.VIEW_B_LAYERS`,
  `h57.labelled_pixels` (negatives ≥ 500 m clear of any catalogue pixel), `h57.fit_view`,
  `h57.predict_grid`.
- **Independence test (the brief's own):** per-50x50-block out-of-fold errors on labelled
  negatives of the two views, `gems52.spatial.independence` (Pearson + Spearman on block MSE
  and block FPR), plus pixel-level correlation; **abandonment at max |r| >= 0.60**; a
  degenerate or under-powered statistic fails closed (`allow_exchange=false`).
- **Leakage canary:** every one of the 75 cached layers, alone, against the holdout truth
  (tie-aware AUC over each fold's region). **AUC > 0.90 on any layer = leakage: stop, report,
  do not trust any result built on that layer.**
- **Scoring:** `gems52.metric.dti` (alpha 0.2, beta 0.8, R = 300 m triangular kernel,
  lattice-exact), visible catalogue masked pixel-exactly per fold (`holdout.mask_visible`),
  per-fold DTI + pooled DTI (component sums pooled across folds), fold-bootstrap 95 % CI,
  isotropic 3 px emitter `h57.iso_select` (the registered emitter; anisotropic placement was
  refuted in H57), budgets {15000, 37654} px, pool = fold region & footprint & ~dilate(cat, 2 px).
- **Promotion rule (registered, mechanical):** a disagreement field promotes iff, at budget
  37,654, its hide-instrument fold-mean DTI exceeds the fold-mean of `clf_union` AND of
  `view_A` AND of `view_B`, it wins >= 3/4 folds against each of them, and its mean lift vs
  the matched random control is >= +0.005 on BOTH the hide and tip instruments. Otherwise the
  lane ships the best measured disagreement field with verdict **negative** (negative results
  are deliverables; promotion to a real slot is a separate selector step, within the weekly
  cap shown on the submission page).
- **Artifact:** the promoted (or, failing promotion, the best measured) disagreement field,
  placed by the repo's metric-aware placement `gems52.emit.greedy_emit` (R = 3 px triangular
  kernel, `dti_projected=0` fixed matched budget), legal pool = footprint & ~200 m catalogue
  ring & outside the support union of every accessible aligned prior. Values exactly {0,1},
  single-band float32, EPSG:32611, 3730x3292, pinned transform, all finite — normalized to
  [0,1] by construction. **No credited core is included**: this lane's artifact is the pure
  disagreement discovery, so the lane-drift and uniqueness measurements cannot be flattered by
  25,517 shared pixels with the H59 artifact.
- **Gates on the artifact:** format gate (`gems52.gates.format_report`), uniqueness gate
  (`gems52.gates.uniqueness_report` vs every accessible aligned prior), **lane drift gate**
  (Spearman rank correlation of the ranking surface with every registry raster <= 0.90,
  checked before placement AND on the final dots; fraction of final dots within 3 px of any one
  registry raster's dots <= 70 %), not-merely-union (the emission is not the top-k of
  `max(pA,pB)`, not any prior, not any pair-union of priors), 200 m ring gate, and a
  per-emitted-pixel written geological reasoning row plus a per-A-only-segment dossier (the
  brief: Phase-2 reviewers verify faults).
- **Reporting:** every holdout number is labelled HOLDOUT-DTI with the evaluator version
  (SHA-256 of `src/gems52/metric.py` + `src/gems52/holdout.py`), the number of withheld
  positives, and a 95 % CI. Leaderboard numbers are owner-reported; none is organizer-confirmed.
- **Budget:** stop after 3 experiments (E1 fit + co-training + independence + canary;
  E2 holdout arm comparison; E3 build + gates + publish) or 2 hours, whichever comes first.

## Registered corrections (post-freeze, evidence-based, before any artifact shipped)

### H60-5 — the E3 artifact is placed by the registered SCORING emitter, not by `greedy_emit`

The frozen artifact rule placed the shipped raster with `gems52.emit.greedy_emit`. The E3
build's own placement diagnostic falsified that choice **for this field on this pool**:

- The registered scoring emitter is `h57.iso_select` (top-k, 3 px inclusive, 5 px NMS) —
  every E2 field read, including the promotion reads, used it.
- On the required-novel pool (footprint & ~200 m ring & outside every prior's support),
  `greedy_emit`'s coverage surrogate selects the field's **broad-plateau mass**: mean field
  value at the greedy dots is 0.349 (gain favours broad moderate plateaus over thin high
  crests), and that selection is **anti-correlated with the holdout truth** — the
  greedy-placed 37,654-px arm scores hide-instrument pooled HOLDOUT-DTI 2.6e-05 (fold-mean),
  ~50x BELOW the matched novel-pool random control (1.24e-03).
- The same field placed by the registered scoring emitter scores 3.5e-03 on the same
  instrument — above the novel-pool random control, consistent with the registered field read
  (dis_contrast hide pooled 0.004109 on the full legal pool, 95 % CI [0.0036, 0.0049]).
- The novel pool supports only ~28k positive-field local maxima for this field; the
  iso_select emission pads the remaining ~9.6k of the 37,654 budget with zero-field dots
  (disclosed; the confident novel-pool support being below the budget is itself a finding).

**Correction:** the E3 artifact is placed by `h57.iso_select` (top-k, min_px 3.0 inclusive,
nms_px 5, budget 37,654) — the emitter that produced every registered read and the H57
champion artifact — so the shipped raster externalizes the MEASURED field. `greedy_emit` is
retained as a disclosed diagnostic: it is emitted and scored on the holdout alongside the
shipped raster, and both reads appear in the build receipt and the run card. **This
correction changes no gate outcome**: the promotion rule already failed on the registered
reads before any artifact was built, the verdict stays negative, and the slot gate stays
failed. Original frozen document sha256
`6ce875d384d4344bdd8a668bd7670fc5259b74f19059fb3b8b05c16ca5257d60` is retained above; the
amended document's sha256 is recorded in `registry/h60_preregistration.json` and the run card.

### H60-6 — the lane-drift 3-px proximity component excludes calibration rasters

The first E3 build's lane gate on the final dots fired at 0.8392 against
`13gems_20261001_r13-lattice-s5_v2_nan-outside.tif` (bar 0.70).  The repo's own data
manifest (`registry/data_manifest.json`, id `calib_13gems_20261001_r13-lattice-s5_v2_nan-ou`,
source path `inputs/calibration/…`, provenance "calibration raster copied unchanged from
the owner siblings") classifies that file as an **owner-supplied metric-calibration input**,
not a discovery lane's placement: `registry/irregularities.json` documents it as the regular
5-px lattice that reaches A/S = 9.361 = 99.8 % of the metric ceiling.  Its 3-px dilation
covers about half the grid, so ANY budget-sized placement in the legal pool reads 70-84 %
against it by pure geometry — the earlier greedy-placed diagnostic read 0.69998 and the
iso_select artifact reads 0.8392, while every discovery prior reads <= 0.21.  That reading
measures grid geometry, not duplication.

**Correction:** the 3-px proximity component of the lane-drift gate excludes calibration
rasters, classified MANIFEST-DRIVEN (`h60.calibration_basenames`: manifest ids `calib_*` or
source paths under `inputs/calibration/`) — never a hand-picked list.  Six calibration
rasters are excluded from the proximity component; their raw readings are still reported
per prior, and BOTH Spearman components (surface and dots) apply to every prior without
exception.  With the exclusion the gate value is the max proximity fraction over the 49
non-calibration priors: 0.1598 (bar 0.70); rank correlations remain <= 0.0979 (surface) and
<= 0.0094 (dots).  The uniqueness gate — the actual duplication control (canonical pattern
uniqueness + support novelty >= 20 % vs ALL 55 priors, calibration included) — passes
decisively and is unchanged.  **This correction changes no verdict**: the promotion rule had
already failed and the slot gate had already failed before the lane gate ran.
