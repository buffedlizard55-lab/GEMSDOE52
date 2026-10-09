# H62 — hypotheses and protocol, preregistered 2026-10-09 **before** any H62 fit, score or artefact

Frozen file: this document's SHA-256 is recorded in `registry/h62_preregistration.json` before the
first model is fitted, and `scripts/run_h62.py` refuses to run if either hash has moved. Nothing
below was written after seeing an H62 result. Lane: the brief's two-view co-training paragraph
(View A potential-field/subsurface, View B surface), disagreement as the discovery signal —
Blum & Mitchell, COLT '98, pp. 92–100, doi:10.1145/279943.279962.

H62 is the direct continuation of the H61 lane with the one repair H61 §8 item 1 named as the
obvious next candidate: **change what View A is**. H61 measured that a View A built from raw
potential-field band values does not transfer between quadrants (mean out-of-fold AUC 0.5163
against View B's 0.6843, in-sample 0.948), so the Blum–Mitchell sufficiency premise failed and the
A→B pseudo-label transfer had nothing to transfer. H62 rebuilds View A as a *physically
parameterised* view — matched step filters and along-strike persistence of the subsurface fields —
and re-runs the full preregistered protocol unchanged so the comparison to H61 is exact.

---

## 0 · What H62 inherits (measured in H61, not re-derived here)

All receipts already committed: `evidence/h61_forensics.json`, `evidence/h61_holdout.json`,
`evidence/h61_pseudo_exchange.json`, `evidence/h61_canary.json`.

* **Masked support `S`** — known catalogue pixels are masked out of evaluation; `S` counts
  off-catalogue pixels (witness: `Hedge-v2` ≡ `ens12-7f00890a`, identical off-catalogue support,
  identical reported 0.1563, masked credit 6,967.0 for both).
* **`|G|` is the interval [5,949.3, 12,512.1] px**, not the superseded point 14,088.7.
* **Band 6 is radiometric total count** (Spearman 1.0000 against the external GeoDAWN TC grid,
  0.0175 against the tilt angle of TMI) and stays in View B.
* **Attribution**: only 3 of 13 owner-reported scores are hash-linked to held bytes; the
  champion's `0.2778` is FILENAME-ONLY-OWNER-REPORTED. Nothing here is ORGANIZER-CONFIRMED.
* **Splitter**: `gems52.spatial.folds` label-blind-quadrants-v2, buffer 80 px, whole 8-connected
  catalogue components hidden in full.
* **Lane gate**: `gems52.gates.lane_report` with the measured universal-coverage-probe
  classification (a prior whose 3 px halo covers ≥ 95 % of the eligible footprint localises
  nothing; literal statistics still reported for every prior).
* **Evaluator**: `gems52.evaluate_holdout` (`gems52-pooled-hide-v1`), pooled TPw/FPw/FNw,
  α 0.2, β 0.8, 300 m triangular kernel, 95 % paired physical-cluster bootstrap.

## 1 · What H62 changes

**View A is rebuilt; View B is byte-identical to H61's View B.**

* **New View A (38 channels, no raw band values).** The template's matched step filter
  `structural.normal_profile` — previously applied only to the DEM (H55/H2 profile features) —
  is applied to the three subsurface fields, at offsets 2 px (200 m) and 4 px (400 m), σ = 3:
  * fields: band 13 `iso_grav_anom` (isostatic gravity anomaly), band 15 `depth_to_base_surf`
    (depth to basement = sedimentary cover thickness), band 2 `rtp` (reduced-to-pole magnetic);
  * per field and offset: `A_step_<tag>_signed_<off>px` (detrended cross-normal step),
    `A_step_<tag>_abs_<off>px` (direction-insensitive step magnitude), and
    `A_step_<tag>_persist_<off>px` (along-strike persistence of |step|) — 18 channels;
  * retained template local-contrast channels: `A_gravity_grad_{1,3,8}`, `A_cover_grad_{1,3,8}`,
    `A_gravity_cover_signed_{1,3,8}`, `A_gravity_persistence_{1_3,3_8}`,
    `A_cover_persistence_{1_3,3_8}`, `A_gravity_coherence`, `A_cover_coherence`,
    `A_RTP_grad_{1,3}` — 17 channels;
  * external deep-magnetic channels: `X_mag_TMI_up150_rank`, `X_mag_TMI_up150_grad1`,
    `X_mag_TMI_up150_grad3` — 3 channels.
  * **No `raw_band_*` channel enters View A.** That exclusion is the defining property of the
  round and is asserted by the runner's setup and by `tests/test_h62.py`.
* **View B (37 channels, unchanged from H61)**: raw bands 6 (radiometric total count), 12
  (`det_elev`), 19 (`det_elev_slope`); the template's elevation/curvature/slope/local-residual
  channels; the external radiometric K, Th, U and Th/K, U/K, U/Th rank and gradient channels.
* The extension is a **shared template module** `src/gems52/h62.py`, used exactly like
  `src/gems52/external.py`; there is no round-private fork. The store version becomes
  `structural-core-v2-band6-B+external-geodawn-v1+h62-step-v1`.

## 2 · Ranked candidate hypotheses (the brief's 3–5, with layers / signature / novelty / cost)

### H62-A — Step-normalised potential-field View A — RANK 1, **implemented this session**

* **Layers.** Bands 13 `iso_grav_anom`, 15 `depth_to_base_surf`, 2 `rtp` (descriptions read from
  the restored file, verified 2026-10-09), transformed by the template's `normal_profile` matched
  step filter at σ = 3, offsets 200 m / 400 m; plus the retained local-contrast and
  upward-continued-TMI channels listed in §1.
* **Physical signature targeted.** A *localised cross-strike step that persists along strike*.
  A fault buried beneath basin cover offsets the basement surface and produces an isostatic
  gravity and magnetic-fabric step that is sharp across the structure and continuous along it.
  The transform subtracts the local first-order plane (a uniform regional gradient is not a
  step), takes the direction-insensitive magnitude (either side may be the downthrown one), and
  averages |step| along the local tangent (faults are along-strike continuous; point noise,
  flight-line artefacts and isolated boulders are not). This is an edge/contrast transform, not a
  new detector family: it is the same paired-normal filter the repo already trusts for the DEM,
  pointed at the fields that actually sense the subsurface.
* **Why it should catch a fault missing from the USGS/INGENIOUS catalogue.** The catalogue is
  compiled from *surface expression*. A range-front or basin-margin fault buried under alluvium
  has a deep basement-depth and gravity/magnetic step but no scarp and no radiometric lineament
  — exactly the "A confident, B abstaining" cell the brief assigns to buried structure. Raw band
  values cannot express this because the regional trend and the survey geometry dominate them;
  H61 measured that a raw-value view is at chance out of quadrant (0.5163).
* **How it differs from anything already implemented in this repo.** Every prior View A
  (H55, H56, H57, H59, H60, H60D, CTD5, H61) mixed raw band values; H61 is the round that
  measured the consequence. The step/persistence transform existed in the template but was
  applied only to the DEM and tagged as a separate "H55" view; H62 applies it to the subsurface
  fields and tags the result View A. No prior round normalised a potential-field channel by its
  along-strike behaviour.
* **Expected DTI improvement / cost.** **None claimed a priori.** The acceptance bar from the
  H61 economics is a credit density above 0.0907–0.1295 per emitted pixel (8.3–5.6× uniform
  random) to match the reported champion at 37,600 dots, and no instrument in this repository can
  certify that for novel mass. The pre-registered read is the **sufficiency screen**: mean
  out-of-fold AUC of the new View A across the four folds, measured before any exchange. Cost:
  medium (~1 h CPU on 2 cores, no new data).

### H62-B — B-only arm with surface-artefact rejection — RANK 2, **not run this session**

* **Layers.** Bands 12/19 (detrended elevation/slope), the H2 paired-profile features, band 6
  radiometrics; the A-abstention mask from H62-A's View A.
* **Signature.** The brief's other disagreement direction: where B is confident and A abstains,
  suspect roads/erosion lines — but a *subset* may be real scarps in density- and
  magnetisation-homogeneous alluvium that the geophysics cannot see. The discriminator would be
  scarp geometry that cuts drainage (fault) versus follows it (erosion line), plus radiometric
  discordance across a lithologic scarp.
* **Difference from prior work.** No round has ever emitted or scored the B-only direction; H61
  shipped only the A−B field and labelled B-only as the artefact class.
* **Why deferred.** It needs the optional H2/H55 profile features (`include_optional_profiles=
  True`, a separate store build) plus a second holdout run; that exceeds this session's
  three-experiment budget once H62-A is implemented. Ranked second because the brief names the
  direction explicitly and it is the cheapest untried *emission* direction left in the lane.

### H62-C — Along-strike continuity weighting of the disagreement field — RANK 3, **not run**

* **Layers.** H62-A's own `A_step_*_persist_*` channels.
* **Signature.** Weight the placed field `rank(A) − rank(B)` by the along-strike persistence of
  A's step, so isolated single-pixel disagreements cannot consume the 37,600-dot budget.
* **Difference.** H61 placed the raw rank difference; no round has weighted disagreement by
  continuity. Cost: low (a transform of existing outputs), but it is a *placement* change, and the
  lane rule forbids post-result retuning — it needs its own preregistered holdout run.
* **Why deferred.** Budget; also a weaker prior than H62-A because the placement heuristic
  (`spacing_select` at 3 px) already suppresses isolated dots.

### H62-D — Sub-canopy 1 m LiDAR scarp detection — RANK 4, **not viable this session (external data unobtainable)**

* **Layers.** USGS 3DEP 1 m DEM (https://www.usgs.gov/3d-elevation-program) over the GeoDAWN
  footprint — the specific free, official source this idea needs.
* **Signature.** Hillshade/sharpness transforms at 1 m detecting scarps under canopy that the
  100 m detrended DEM cannot resolve.
* **Why it should catch a catalogue-missing fault.** The catalogue is surface-compiled at
  regional scale; a fresh 1 m scarp under canopy is invisible to it and to every view in this
  repository.
* **Difference.** No prior round used sub-100 m topography (the 12-band 1 m LiDAR scarp-feature
  raster in `data/external` was inventoried but never fused into a view).
* **Viability check, done.** Sandbox egress is limited to github.com, codeload.github.com,
  api.github.com, registry.npmjs.org, pypi.org and files.pythonhosted.org; usgs.gov is
  unreachable (verified in earlier sessions; unchanged). The 1 m DEM is therefore **not
  obtainable this session** and the idea is recorded, not proposed as viable.

### H62-E — Cross-file credit localisation by terrain stratum — RANK 5, **inherited from H61-D, not run**

* The H61 round's deferred H61-D: cross the LP atoms (file-membership signatures) with slope,
  modelled cover thickness and radiometric alteration strata and bound credit per stratum, so the
  organiser's own scores say *where* hidden truth sits rather than *which prior* found it. No new
  data needed. Deferred because it is an analysis-lane experiment: it consumes budget without
  producing a submission, and the lane's deliverable this session is a unique artefact.

## 3 · Frozen decision rules (checked by code, not by prose)

1. **Folds.** `gems52.spatial.folds` label-blind-quadrants-v2, buffer 80 px, whole components
   hidden in full. The rejected CTD5-v1 tail-halo splitter is never used.
2. **Leakage canary.** Raw single-feature AUC of **every** used feature on **every** fold's
   held-out sample (held-out positives + catalogue-zero proxies ≥ 5 px from any visible trace).
   Alarm at AUC > **0.90** (direction-insensitive); the top-5 also get a fitted single-feature
   HGB AUC. Any alarm ⇒ the feature is dropped and the drop recorded.
3. **Sufficiency screen (new this round, measured before any exchange).** Mean held-out-region
   AUC of View A over the four folds. Blum–Mitchell needs each view sufficient. Reporting rule:
   if the mean is below **0.60** the run card states the sufficiency premise is not met. The
   exchange is still executed iff the independence screen allows it — the brief's only
   abandonment criterion is the correlation test — and the verdict rule in §2.11 decides.
4. **Independence.** `spatial.negative_block_errors` on 50×50 px blocks (min 32 negatives) over
   held-out catalogue-zero proxies, then `spatial.independence`, abandon at max |ρ| ≥ **0.60**
   on Pearson and Spearman of block MSE and block false-positive rate.
5. **Pseudo-label exchange.** Exactly **one** round, `spatial.whole_pseudo_segments`, donor
   operating rank ≥ 0.95, receiver rank ∈ [0.35, 0.65], whole 8-connected segments of ≥ 5 px,
   wholly inside the fold's training domain, wholly inside one 50×50 block, disjoint from the
   evaluation region, the hidden components, the visible catalogue and its 4 px collar, and the
   sampled training labels. Cap 2,000 px per direction per fold. No second exchange, no
   post-result hyperparameter search.
6. **Budgets.** K = 9,400 dots per fold for every arm, `nodes.spacing_select` at min_px = 3.0.
   Arms: `single_A`, `single_B`, `union_max`, `disagreement_pre`, `disagreement_post`, `random`.
   An arm that cannot fill K invalidates the comparison and is reported, not rescued.
7. **Score.** `gems52.evaluate_holdout` (`gems52-pooled-hide-v1`), pooled, α 0.2, β 0.8, 300 m
   triangular kernel, 95 % paired physical-cluster bootstrap (200 px = 20 km blocks, 1,000
   draws). Every number is labelled **HOLDOUT-DTI** with evaluator version, withheld positive
   count and CI. No HOLDOUT-DTI is written as a score, and none is used alone to promote.
8. **Emission domain.** Eligible footprint ∧ sample-submission finite footprint ∧ off catalogue
   ∧ > 200 m from any catalogue pixel. Values exactly {0, 1}, float32, no NaN anywhere, grid
   identical to `sample_submission.tif`.
9. **Lane gate.** `gates.lane_report` against the whole 526-blob census plus this repository's
   own `submission/` directory, on the **surface before placement** and on the **final dots**.
   Literal and saturation-policy verdicts are both reported; Spearman > 0.90 or near-dot
   fraction > 0.70 against any *informative* prior ⇒ DUPLICATE / STOP.
10. **Not-the-union check.** The shipped field must differ from `max(A, B)`, from each single
    view, and from the union of separately emitted A/B controls, with differing-cell counts
    published.
11. **Verdict.** `promote` only if the artefact passes the format gate, the lane gate (policy),
    the decoded-pattern uniqueness and the not-union check **and** its projected
    organiser-DTI interval exceeds the champion's owner-reported 0.2778 at *both* ends of the
    |G| interval. Otherwise `negative` / research-only, and the page must say
    **DOWNLOAD: YES · SUBMIT: NO** without ambiguity. Promotion to a weekly slot is a separate
    selector step; this round spends **0** slots.

## 4 · The named non-fault process that could mimic H62-A's signal

**A non-fault basin-fill density boundary or a volcanic lithologic contact in the basement.**
Both produce a step in modelled basement depth and an isostatic-gravity / magnetic-fabric edge
under alluvium with no surface scarp — the exact A-confident/B-abstaining signature, and the
step filter fires on any sharp cross-strike contrast, not only on fault offsets. Secondary mimics:
buried palaeo-channels and alluvial-fan margins (linear, low-slope, along-strike persistent
contrast edges), dyke swarms, and the airborne survey's own flight-line artefacts, which appear as
parallel linear steps in the continued magnetics and are only partially suppressed by the
persistence term. The falsifier for each candidate is independent evidence of *offset* — a
displaced contact or marker bed, deflected or offset drainage, a facies termination, or a
published structural interpretation — none of which is claimed here. Fault candidates are not
geothermal vents, and neither establishes permeability or a reservoir.

## 5 · Falsification conditions

* Any single feature with held-out AUC > 0.90 ⇒ that feature is leaked until proven otherwise.
* max |ρ| ≥ 0.60 on block negative errors ⇒ the pseudo-label exchange is abandoned.
* Mean View A out-of-fold AUC < 0.60 ⇒ the sufficiency premise is not met (reported; the verdict
  rule still applies, and a negative verdict is a deliverable).
* `disagreement_post` not above the best single-view control at matched budget, with a paired CI
  that includes zero ⇒ the discovery signal is refuted at this operating point.
* Near-dot fraction > 0.70 or Spearman > 0.90 against any informative prior ⇒ DUPLICATE / STOP.
* Projected DTI interval not above the champion at both ends of |G| ⇒ research-only, no slot.

## 6 · Official sources for manual review

* Metric, submission format, dataset: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
* About page and resources: https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/
* Data tab (login required): https://www.drivendata.org/competitions/306/competition-doe-gems/data/
* Leaderboard: https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/
* Staff masking clarification, thread 11516 post 4: https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4
* Blum & Mitchell, COLT '98 pp. 92–100: https://doi.org/10.1145/279943.279962
* USGS GeoDAWN airborne magnetic & radiometric survey: https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and (DOI 10.5066/P93LGLVQ)
* USGS 3DEP (named for H62-D, not fetched): https://www.usgs.gov/3d-elevation-program
* INGENIOUS / Great Basin Center for Geothermal Energy: https://gbcge.org/current-projects/ingenious/
* GDR submission 1391 (CC BY 4.0): https://gdr.openei.org/submissions/1391
* EPSG:32611 (UTM zone 11N): https://epsg.io/32611 · Tversky index: https://en.wikipedia.org/wiki/Tversky_index
* Reference solution: https://github.com/drivendataorg/gems-prize-reference-solution
* Rules PDF as supplied by the owner (host not reachable from this sandbox; not independently verified): https://docs.nlr.gov/docs/fy26osti/96647.pdf

## 7 · AI-use disclosure

An AI assistant wrote the code, this protocol and the candidate-review templates. No geologist
verified any emitted structure, no field observation was collected, and no organiser score,
acceptance or leaderboard gain is claimed for any H62 artefact.
