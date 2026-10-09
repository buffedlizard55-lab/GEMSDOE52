# 60 · H74 results and limits (rendered from the receipts by `scripts/publish_h74_site.py`)

**Verdict: `NEGATIVE, research-only. DOWNLOAD YES (format-valid and unique on decoded pixels); SUBMIT NO. Failed gates: lane_policy, S1, holdout_beats_single_B. No weekly slot spent by this lane.`**

Artefact `gems52-h74-a2deform-cotrain-721px-20261009T174546Z.tif`, SHA-256 `0dea78bc8e276a8276de94a169e59ffac43234cef6a6f978f13f0788c6232f26`, 58475 bytes, 721 emitted cells,
every one a strict A2-only discovery candidate with a written geological reasoning row
(`docs/downloads/h74-a-only-reasoning.csv`). Pre-registration: `knowledge/63_hypotheses_H74_preregistered.md`
(SHA-256 in `registry/h74_preregistration.json`).

## 1 · What H74 changed

H74 executes the deferred **H70-E** variant: a **deformation-only View A2** built from the geodetic
strain bands (4 second invariant, 7 shear, 8 dilatation) and the seismicity bands (10 distance, 16
density), with gradient transforms at the shared scales and strain coherence — 22 channels — while
View B (surface, 37 channels) is unchanged. Every previous View A mixed potential-field and
deformation channels; none isolated the deformation half, so the five sufficiency failures
(H61 0.5163 · H63 0.5362 · H64 0.5230 · H65 0.5202 · H70 0.5166) could not be attributed. H74
attributes them on the A2/B pair and re-runs the lane's full mandated protocol: independence screen,
one whole-segment confident-to-abstaining exchange per direction, nine-arm matched-budget
hide-and-recover holdout against the single-view baseline, then the strict A2-only discovery stratum
built with the H70 §3 lane-valid constrained placement.

## 2 · Independence, canary and sufficiency (the lane's mandated tests)

Independence screen (spatial-block OOF errors on labelled negatives, held-out catalogue-zero proxies): max |ρ|
**0.0765** against the 0.60 abandon bar → exchange
**allowed** (H70 measured 0.1337 on the potential-field pair).
Leakage canary: max alarm AUC **0.6687**, any alarm **False**
(bar 0.90). S1 sufficiency on View A2 (out-of-quadrant AUC): mean **0.5194**,
min fold **0.5011** → **FAIL**
(gate 0.60 / 0.55). View B mean **0.6843** (H61: 0.6843).

## 3 · HOLDOUT-DTI (evaluator gems52-pooled-hide-v1), matched budget 9400 dots/fold/arm

| arm | HOLDOUT-DTI | 95% CI | withheld positives |
|---|---:|---:|---:|
| a_only | 0.050048 | [0.035285, 0.065611] | 53,186 |
| single_B | 0.174517 | [0.152316, 0.196299] | 53,186 |
| single_A2 | 0.070000 | [0.054826, 0.086633] | 53,186 |
| union_max | 0.148599 | [0.128721, 0.168434] | 53,186 |
| disagreement_pre | 0.039789 | [0.029721, 0.051799] | 53,186 |
| disagreement_post | 0.035789 | [0.026034, 0.046255] | 53,186 |
| single_B_veto_Bonly | 0.167026 | [0.146221, 0.187384] | 53,186 |
| concordant | 0.118511 | [0.097657, 0.139208] | 53,186 |
| random | 0.080426 | [0.070223, 0.090973] | 53,186 |

Paired difference, candidate (a_only) minus single_B: -0.124469, 95% CI [-0.149150, -0.099436].
Control reproduction at the H61 budget (9,400 dots/fold): single_B 0.174517 vs committed H61
0.174517, |Δ| 2.88e-07 (tolerance 0.001).

## 4 · Gates
* Format gate (single-band float32 GeoTIFF, EPSG:32611, shape and transform as pinned): **PASS**
* Values exactly {0, 1}; 0 NaN; 0 infinite: **PASS**
* Decoded-pattern uniqueness (not identical to any of the 560 registry rasters): **PASS**
* Support novelty vs the 523 informative registry rasters: **1.0000**
* Not the union of the two views: **PASS**
* Lane gate, literal, surface / dots: **PASS / DUPLICATE/STOP**
* Lane gate, saturation policy, surface / dots: **PASS / DUPLICATE/STOP**
* Lane policy max near-dot share (bar 0.70): **0.8835**
* Audit (audit_uniqueness.py, census): surface max Spearman / dots max near-3px: **0.0058 / 1.0000**
* S1 sufficiency (View A2 out-of-quadrant AUC mean ≥ 0.60, min fold ≥ 0.55): **FAIL (0.5194 / 0.5011)**
* Holdout beats single_B (paired CI lower bound > 0): **FAIL**

## 5 · Limits
* The holdout instrument does not rank the board (`knowledge/10` §5, `knowledge/31` §2). These are HOLDOUT-DTI values only.
* The literal lane rule fails for every nonempty raster on this registry (measured universal-coverage lattice probe);
  the policy verdict classifies probes by measured coverage ≥ 0.95 and is the repository's authoritative lane.
* Prevalence: the holdout withholds about 1.04% of the footprint; the competition truth is about 0.12–0.25%.
* Inputs are SHA-256-pinned owner mirrors, not organiser-authenticated downloads.
* The reasoning CSV is measured context plus a template hypothesis, not field-verified geology.
