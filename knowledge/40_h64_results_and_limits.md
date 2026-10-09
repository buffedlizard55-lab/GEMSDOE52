# 40 · H64 results and limits (rendered from the receipts by `scripts/publish_h64_site.py`)

**Verdict: `NEGATIVE, research-only. DOWNLOAD YES (format-valid and unique); SUBMIT NO (holdout does not beat single_B and/or literal lane not PASS). gates: format=True lane=False unique=True not_union=True S1=False holdout_beats_single_B=False`**

Artefact `gems52-h64-sufgate-cotrain-37600px-20261009T022631Z.tif`, SHA-256 `739a8e7c4b54436508fc2b9da6b8ddc56e44a0d1ad273dc88c07a2003637f8bb`, 133668 bytes, 37600 emitted cells.
Pre-registration: `knowledge/39_hypotheses_H64_preregistered.md` (SHA-256 in `registry/h64_preregistration.json`), amended
for the control tolerance only: `knowledge/39b_amendment_control_tolerance.md`.

## 1 · Sufficiency gate S1 (the premise of co-training)
Mean View-A out-of-quadrant AUC **0.5230** (fold minimum 0.4681); thresholds mean ≥ 0.60, fold ≥ 0.55.
**FAIL.** Measured against H61's 0.5163, the capacity cut did not change the picture.

## 2 · HOLDOUT-DTI (evaluator gems52-pooled-hide-v1)
| arm | HOLDOUT-DTI | 95% CI | withheld positives |
|---|---:|---:|---:|
| single_A | 0.065101 | [0.048643, 0.081659] | 53,186 |
| single_B | 0.174517 | [0.152316, 0.196299] | 53,186 |
| union_max | 0.149659 | [0.128675, 0.171048] | 53,186 |
| disagreement_pre | 0.031233 | [0.021219, 0.043309] | 53,186 |
| disagreement_post | 0.031233 | [0.021219, 0.043309] | 53,186 |
| random | 0.080426 | [0.070223, 0.090973] | 53,186 |

Paired difference, candidate minus single_B: -0.143284, 95% CI [-0.165564, -0.121457].
Control: single_B 0.1745172876 vs committed H61 0.174517, |Δ| 2.88e-07.

## 3 · Gates
* Format gate (single-band float32 GeoTIFF, EPSG:32611, shape and transform as pinned): **PASS**
* Values exactly {0, 1}; 0 NaN; 0 infinite: **PASS**
* Decoded-pattern uniqueness (not identical to any of the 548 registry rasters): **PASS**
* Exact novelty: share of emitted cells that are not positive in any of the 511 informative registry rasters: **1.0000**
* Not the union of the two views: **PASS**
* Sufficiency gate S1 (View A out-of-quadrant AUC): **FAIL**
* Lane gate, literal, surface / dots: **PASS / DUPLICATE/STOP**
* Lane gate, saturation policy, surface / dots: **PASS / DUPLICATE/STOP**
* Holdout beats single_B (paired CI lower bound > 0): **FAIL**

## 4 · Limits
* The holdout instrument does not rank the board (`knowledge/10` §5, `knowledge/31` §2). These are HOLDOUT-DTI values only.
* No exchange was run (S1 failed), so the S2 independence statistic was not evaluated in this round.
* Prevalence: the holdout withholds about 1.04% of the footprint; the competition truth is about 0.12–0.25%.
* The lane gate, uniqueness and projections are measured against the registry census available on disk at build time.
