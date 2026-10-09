# 41 · H65 — metric-kernel halo targets for the two co-training views (preregistered)

Frozen before any H65 fit. The SHA-256 of this file is pinned in `registry/h65_preregistration.json`;
`scripts/run_h65.py` refuses to start if the hash moves. One experiment, not three: the budget
counts as one of the three experiments the brief allows per session.

## 1. Why this round, against the record

* Every prior co-training round trained both views on **hard** labels: visible-catalogue pixels are
  positives, and negatives are taken only more than 5 px (500 m) from the visible catalogue
  (`scripts/run_h61.py::sample_train`). The 0–500 m zone around mapped traces therefore never enters
  training, and the 200 m emission exclusion (`catalogue_exclusion_m`) sits inside that blind zone.
* The metric is not a hard-label metric. The official kernel is triangular with radius
  R = 300 m (`src/gems52/metric.py`, `k(d) = max(1 − d/R, 0)`), so a pixel 150 m from a truth pixel
  earns half credit. A classifier trained on pixel-exact labels is fitting the wrong target for a
  300 m-tolerant score.
* Searched `knowledge/`, `scripts/` and `src/` before writing this: no round used kernel-weighted
  training targets. Existing `sample_weight` uses are pseudo-label weights of 0.25 (`run_h58.py`, `run_h59_viewb.py`,
  `run_ctd5.py`, `run_structural_pipeline.py`), not distance-based targets. The H60 "tax term" target
  is a placement rule, not a learner target. H57 excluded the catalogue halo from the candidate pool,
  and H59-D restricted the pool to a halo (refuted as a restriction). Neither trained on halo targets.

## 2. Hypothesis

**H65.** Training both views on the metric's own coverage target,
`q(x) = max(0, 1 − d_vis(x)/300 m)`, instead of the pixel-exact mask, raises holdout DTI of the
single-view control `single_B` above its hard-label control (paired 95% CI lower bound > 0). The
mechanism is that the 100–300 m halo of each visible trace carries partial metric credit, and a
learner that is told so ranks halo-like terrain above background.

* **Layers.** Unchanged from H61: View A = potential-field and subsurface channels (gravity, RTP,
  TMI, strain, seismicity); View B = surface channels (DEM curvature and slope, plus radiometric
  band 6 as isolated by H61). Feature store rebuilt by `structural.build` + `gems52.external` +
  `h63.extend_store`, the same sequence as the README reproduction block.
* **Physical signature.** Terrain that is fault-like within 300 m but not on the mapped trace:
  damage-zone gradients, flexure-scale curvature, and strain-rate magnitude that decays away from
  a trace. The learner sees only features, never hidden truth.
* **Named non-fault mimic.** A basin-margin gravity gradient or lithologic contact that runs parallel
  to a mapped trace inside 300 m. It produces the same halo signature without any fault, so a
  positive result here would be ambiguous unless the holdout separates it from faults.
* **Why it could catch a catalogue-missing fault.** Official problem text (DrivenData page 967)
  says the existing fault data "may be misaligned from the true location", and staff have said
  new-fault pixels can lie within 300 m of a mapped trace (forum topic 11516, as cited in
  `knowledge/33`; **not re-verified in this round**). Halo-aware scoring is the only way the model
  can express that.

## 3. The one change (versus H61)

Training rows, labels and weights for each fold, computed by a new hook `sample_for_fit`:

1. **Hard part (unchanged).** Exactly H61's `sample_train` draws, so the hard `single_B` control
   reproduces H61.
2. **Halo part (new).** Pixels with `fold.train ∧ ¬cat ∧ 0 < d_vis < 300 m`, where `d_vis` is the
   distance to the fold's visible catalogue. Sample up to 30,000 of them with a separate generator
   (seed `SEED + 900 + fold`). Each halo pixel enters twice, with label 1 and weight `t` and with
   label 0 and weight `1 − t`, where `t = max(0, 1 − d_vis/300 m)`. The weighted log-loss
   minimiser is then the soft target `t`.
3. **Unchanged.** Visible-catalogue positives (`t = 1`), far negatives (`d > 5 px`, `t = 0`), the
   3–5 px ring (kept out of training as in H61), learners (H61 for both views; **no** View-A
   capacity change), seed, folds, feature sets, budget, placement.

The change is applied to both views. Learners and feature sets are untouched, so the View-A
parameterisation is not revisited (AGENTS.md).

## 4. Arms and evaluation

* Six arms exactly as H61: `single_A`, `single_B`, `union_max`, `disagreement_pre`,
  `disagreement_post`, `random`. Each emits K = 9,400 dots per fold through `nodes.spacing_select`
  (3 px minimum separation) on the label-blind emission domain (`region ∧ ¬visible ∧ d_vis > 200 m`).
* **Control (not a candidate):** `single_B_hard`, the H61 hard-label `single_B`, re-run in this
  process. Pipeline control: it must reproduce H61's `single_B` 0.174517 within ±0.001
  (`single_B_control_abs_tolerance`); outside tolerance = pipeline defect, stop.
* Scoring: `gems52.evaluate_holdout` (`gems52-pooled-hide-v1`), pooled over folds; α = 0.2,
  β = 0.8, R = 300 m triangular kernel; visible catalogue masked pixel-exactly; 53,186 withheld
  positives; paired 95% physical-cluster bootstrap, 1,000 draws, seed `SEED`.
* **Primary comparison (the mechanism test):** `single_B_soft − single_B_hard`, paired 95% CI.
* **Secondary comparison (the co-training lane):** `disagreement_post − single_B_soft`, paired CI.
  The best comparable control is reported as the larger of the two single-view arms.

## 5. Gates (thresholds inherited from H61 unless stated)

* **Canary.** Single-feature held-out AUC alarm at 0.90. Re-run in H65 on the H65 feature store.
* **S1 sufficiency.** Mean out-of-quadrant View-A AUC ≥ 0.60 and minimum fold ≥ 0.55, scored
  against hard labels as in H64. **If S1 fails, no exchange runs and post-arms equal pre-arms**
  (H64 rule). S2 (independence, |ρ| ≥ 0.60 abandons) is evaluated only inside the exchange.
* **Lane.** `gates.lane_report` on the surface before placement, and on the final dots. Literal
  rule: >70% of dots within 3 px of one informative registry raster → DUPLICATE, stop.
* **Not-union.** The shipped field must differ from max(A,B), from either single view, and from
  their union (as H64 measured).
* **Format.** Single-band float32 GeoTIFF, EPSG:32611, 100 m, same bounds, values in [0, 1],
  outside bounds null. `submission_writer` validator must pass.
* **Uniqueness.** Decoded pixels compared against all 548 registry rasters. Exact novelty is
  required; lane rule as above.

## 6. Verdict rule (frozen)

* **Mechanism confirmed** only if `single_B_soft − single_B_hard` has a 95% CI lower bound > 0.
  Reported either way; a single-view result does **not** make a co-training candidate.
* **Eligible for the selector** only if ALL hold: S1 pass; lane PASS (surface and final); not-union
  PASS; format PASS; exact-unique PASS; `disagreement_post` > `single_B_soft` with CI lower bound > 0.
* Otherwise **NEGATIVE, research only**: DOWNLOAD YES if the file is valid and exact-unique; SUBMIT NO.
* Nothing uploads. No weekly slot is touched. Promotion is a separate selector step.

## 7. What would embarrass this round

* A halo-trained `single_B` that improves by moving emission into the 200–300 m band of the visible
  catalogue, with the gain concentrated in holdout clusters adjacent to visible traces. That would
  be a catalogue-proximity artefact, not a fault signal. The run card must report the share of
  gain from halo cells (cells at 200–300 m from visible traces) and must not present it as
  geology if that share dominates.
* Canary alarm, control reproduction failure, or any hash mismatch.

## 8. Limitations, stated before the run

* The holdout truth is the catalogue. Correction pixels (new fault pixels within 300 m of a mapped
  trace, which R5-H1 targets) are **not** in this truth set, so H65 cannot test R5-H1.
* The official metric text (page 967) does not state that catalogue-known pixels are masked from
  false positives. The repo's pixel-exact masking is an inference from owner-reported scores.
  This is a limitation for every holdout number in the repo, not a new one.
* Owner-reported scores (for example 0.2778) are not organiser-confirmed, and this round does not
  use them as evidence.
