# 32 — H62 preregistered hypotheses: buried structural corridors (co-training lane)

**Lane (fixed by the session brief, verbatim method paragraph):** co-training between a
geophysical view and a surface view, with disagreement as the discovery signal (Blum &
Mitchell, COLT '98, pp. 92–100, doi:10.1145/279943.279962). View A = potential-field and
subsurface (gravity, magnetics, strain, seismicity). View B = surface (DEM-derived curvature
and slope, plus any radiometric bands present in `training_features.tif`). Independence is
tested empirically on spatial-block out-of-fold errors on labelled negatives; the method is
abandoned if they are strongly correlated. Pseudo-labels only where one view is confident and
the other abstains, using whole-segment spatial blocks and a buffer so no leakage reaches the
evaluation. Discovery signal = disagreement. Co-training can amplify bias, so compare against
a single-view baseline on hide-and-recover segments. Normalize to [0,1], write the GeoTIFF,
apply the repo's metric-aware placement, run the uniqueness gate, and confirm the output
isn't merely the union of the two views.

**Written and frozen before any H62 fit ran** (machine-readable twin
`registry/h62_preregistration.json`, SHA-256 recorded there). Data: the 23 manifest-pinned
owner-mirror files under `work/pinned` (integrity-pinned, NOT organizer-authenticated).
Views, folds, thresholds and budgets are the H60D protocol values so every H62 number is
comparable with `evidence/h60d_*.json` (seed 20261009, hide folds, 4 whole-segment folds,
buffer 4 px, prevalence 0.002, q_conf 0.6, q_abstain 0.4, budgets 15,000 / 37,654 px).

## Why this round exists (the gap in the evidence)

H60D adjudicated the *ungated* disagreement fields negative on the hide instrument
(`knowledge/31_what_h60D_found.md`): `dis_contrast` 0.004109 vs view_B 0.006419 hide pooled
at 37,654 px. But two measured facts were never converted into an emission rule:

1. The A-only stratum sits at median depth-to-basement 341.7 m vs 106.5 m for B-only
   (`evidence/h60d_cotrain.json` → strata) — the burial regime where surface mapping has no
   signal.
2. The competition's private truth is expert-drawn faults **not in the public USGS database**
   (official problem page, <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>),
   and the catalogue is surface-mapped. A buried fault is therefore the canonical
   off-catalogue fault — the board population — while the hide instrument scores withheld
   *catalogue* segments and is structurally blind to that population (see also the registered
   instrument defect IR-H60-003: board/instrument Spearman −0.099 across 13 scored priors).

H62 therefore tests whether **geologically gated disagreement** (cover + potential-field edge
+ strike persistence) concentrates off-catalogue fault candidates, and — preregistered —
whether it beats view_B exactly where the lane predicts its advantage: withheld segments
with weak surface expression.

## The five hypotheses (ranked by expected DTI improvement / cost)

### H62-1 (primary) — Buried structural corridors

- **Field:** `d = max(pA − pB, 0)` on the H60D OOF view probabilities, then three gates:
  (i) **cover gate** — band-15 depth-to-basement ≥ 200 m (scarp cannot survive burial);
  (ii) **edge gate** — local potential-field edge strength (layer-stack `grav_anom_grad` or
  `rtp_grad` or `tmi_hg_grad`) ≥ its footprint 75th percentile;
  (iii) **persistence gate** — the surviving mask must belong to a linear corridor of
  skeleton length ≥ 15 px (1.5 km) with elongation ≥ 3 (morphological line opening,
  scipy.ndimage, line structuring elements at 2,3,4 px half-widths unioned; connected
  components on the opened mask).
- **Physical signature:** a density or susceptibility step that continues along strike for
  kilometres beneath cover, with no DEM/LiDAR scarp. A gravity step without a topographic
  step in an extensional basin with basin-wide alluvium means the structure is there and
  buried (H52-1's population measurement: A-only mean cover-depth rank 455 vs concordant
  251, `evidence/strata_hide.json`).
- **Why it should catch a fault the USGS/INGENIOUS catalogue missed:** the labels come from
  USGS Quaternary fault maps and INGENIOUS surface mapping; expert reviewers added faults
  "not contained within the existing USGS database." Where cover kills the scarp, the
  mapping method has no signal, so catalogue absence is weak evidence of absence. The
  competitor whose prediction the Phase 2 panel can verify must carry the geophysical
  argument in the pixels themselves — a persisted edge corridor does that.
- **How it differs from everything already in this repo:** H60D emitted the *raw* disagreement
  field top-k with no physical gate. H52-1 used cover depth as population corroboration only
  and measured coarse-ranked A-only mass below random as an emitter on the near-trace
  corridor; it never combined cover ∧ edge ∧ persistence on OOF logistic disagreement, and
  never on the required-novel pool. No round anywhere in this repository filtered a
  disagreement mask for line persistence (skeleton length / elongation / line opening).
- **Named non-fault process that could mimic it:** buried paleochannels and basin-fill edges
  (a density contrast that is not a fault), lithologic contacts, dike swarms.
- **Cost:** one fit pass (shared stack) + morphology; ≈ 25 min CPU.

### H62-2 — Step-over nodes inside buried corridors

- **Field:** pixels where an H62-1 corridor crosses another corridor (8-connected skeleton
  intersection within 2 px) AND (band-16 earthquake density ≥ P75 OR band-4 geodetic second
  invariant ≥ P75).
- **Physical signature:** fault intersections and dilational step-overs localize extension,
  seismicity and hydrothermal upflow — the INGENIOUS play-fairway logic for where a
  geothermal system sits on a fault network.
- **Why off-catalogue:** an intersection buried under cover has neither a scarp nor two
  mappable traces; it is the least surface-expressible part of the network.
- **How it differs:** H53's nodes were azimuth-coincidence tiles between channel pairs; the
  GEMSDOE3 "pindrop" nodes were another repository's emission. No round here extracted
  crossing nodes of a disagreement corridor skeleton or gated them on seismicity/strain.
- **Mimic:** induced seismicity clusters, quarry blasts, mining districts.
- **Cost:** low (piggyback on H62-1 output).

### H62-3 — Alteration-concordant buried corridors

- **Field:** H62-1 corridors ∧ radiometric alteration anomaly (external GeoDAWN K, Th/K, U/K
  bands from `ext_geodawn_rad_u8`/`ext_geodawn_extensions_u8`, anomaly = K ≥ P75 and
  Th/K ≤ P25 — the silicic/argillic pattern of a convective geothermal system).
- **Physical signature:** hydrothermal alteration along buried structure; blind geothermal
  systems leave an alteration halo and no fault scarp.
- **Why off-catalogue:** alteration is not a criterion of a fault map, and the faults hosting
  the system may be entirely covered.
- **How it differs:** GEMSDOE46 (sibling site) fused scarp+radiometric on *surface* features;
  inside this repository radiometric bands entered View B and H53's coincidence pairs only,
  never as a concordance gate on A-only corridors.
- **Mimic:** ash-flow tuffs with primary K anomalies, lithologic K variation, evaporites.
- **Cost:** medium.

### H62-4 — Ratcheted multi-round co-training

- **Field:** 3 exchange rounds (Blum & Mitchell's full iterative protocol) with monotone
  confidence thresholds 0.60 → 0.70 → 0.80, whole-segment pseudo-labels, same-seed
  no-exchange control per round.
- **Why:** H60D ran one round; the cumulative pseudo-label literature says rounds amplify
  bias — this measures whether ratcheting turns the five measured nulls into signal.
- **Mimic:** self-training drift (the named failure mode).
- **Cost:** low; **expected value: low** (five independent nulls already measured).

### H62-5 — B-only artifact hard-negatives to de-bias View A

- **Field:** refit View A with the B-confident/A-abstain population (roads, quarry faces,
  erosion lines — the lane's suspect-artifact class) added as labelled negatives, then
  re-rank A-only disagreement.
- **Why:** co-training amplifies bias; the lane itself names the B-only stratum as suspect
  surface artifacts. Turning that population into explicit hard negatives is the cheapest
  registered de-biasing arm.
- **Mimic:** real faults that cross a road (a true fault down-weighted as artifact).
- **Cost:** low; external roads vectors (TIGER/OSM) would strengthen it but are NOT required
  (the B-only population is the proxy). If tried with roads, the free official source is
  USGS TIGER/Line (<https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html>)
  — availability not verified in this sandbox, so H62-5 as registered does not depend on it.

## Ranking (expected DTI improvement / implementation cost)

| rank | id | expected improvement | cost | decision |
|---|---|---|---|---|
| 1 | H62-1 | high (first physical gate on the discovery signal) | medium | **validate now** |
| 2 | H62-2 | medium-high (highest per-pixel density if H62-1 is real) | low | validate iff H62-1 passes (a) |
| 3 | H62-3 | medium | medium | proposal only this session |
| 4 | H62-5 | medium | low | proposal only this session |
| 5 | H62-4 | low (five nulls measured) | low | proposal only this session |

## Preregistered decision rules (frozen)

1. **Independence gate (lane):** compute per-50×50-block OOF error rows on labelled negatives
   per H60D; abandon the co-training framing if max |Spearman| ≥ 0.60.
2. **Leakage canary:** every cached layer alone vs the holdout truth; AUC > 0.90 = leakage
   until proven otherwise (flag and stop).
3. **Weak-surface subgroup (the lane claim):** for each withheld whole segment, mean view-B
   OOF probability along its pixels; segments below the median across segments = "weak
   surface expression". Prediction: H62-1 beats view_B on this subgroup at matched budget
   with ≥ 3/4 fold wins (hide instrument).
4. **Promotion bar (all clauses required, else verdict = negative):**
   (a) at 37,654 px on hide pooled, H62-1 > ungated `dis_contrast` AND > matched random;
   (b) clause 3's subgroup win;
   (c) overall hide pooled ≥ matched random (sanity);
   (d) format gate 0 problems, all-finite {0,1}, CRS/shape/transform match;
   (e) uniqueness: no decoded-pattern match to any accessible prior; rank-corr ≤ 0.90 and
   dot-proximity ≤ 0.70 vs registry rasters **excluding manifest-classified calibration
   rasters** (registered correction H60-6 — a survey-wide lattice is geometry, not lane
   duplication; the raw proximity incl. calibration is reported);
   (f) not-merely-union: ≥ 90 % of emitted pixels outside `max(pA, pB)` confident support
   union of the two single-view emissions at matched budget.
5. **Budgets:** validation at 15,000 and 37,654 px; final artifact 37,654 px (the mass of
   the best off-catalogue scored prior, `evidence/h60_budget_amendment.json`).
6. **Emitter:** `gems52.h57.iso_select` (min_px 3, nms_px 5) — the registered scoring
   emitter (H60-5: `greedy_emit`'s coverage surrogate anti-correlated with holdout truth).
7. **Ring rule:** no emission inside `binary_dilation(catalogue, 2 px)` (≤ 200 m) — the
   measured zero-tax ring (champion's 6,436-px deletion, +6.8 %).
8. **Raster:** single-band float32, binary {0,1}, **all finite — zeros outside footprint**
   (the portal rejected a NaN-bearing file with "Predicted values must be in range [0, 1]");
   EPSG:32611, 3,730 × 3,292, transform identical to `sample_submission.tif`.
9. **Every number labelled** HOLDOUT-DTI (evaluator version, withheld positives, 95 % CI) or
   OWNER-REPORTED (copied from a submission-page receipt; projections never written as
   scores).
10. **Budget of work:** 3 experiments (E1 baselines/canary, E2 H62-1 validation, E3 build +
    gates) or 2 hours, whichever comes first. Negative results are deliverables.
