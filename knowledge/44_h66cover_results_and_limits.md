# 44_h66cover · H66cover results and limits (rendered from the receipts by `scripts/publish_h66cover_site.py`)

**Verdict: `NEGATIVE, research-only. DOWNLOAD YES (format-valid and unique on decoded pixels); SUBMIT NO (gates: format=True lane_policy=False unique=True not_union=True beats_single_B=False). No certified leaderboard gain.`**

Artefact `gems52-h66-covergate-cotrain-633px.tif`, SHA-256 `0ce05c52194a8d234aac98684bee6f96bad9c7c5c5c2f79cf580a5df72707629`, 58473 bytes, 633 emitted cells.
Pre-registration: `knowledge/43_h66cover_hypotheses_preregistered.md` (SHA-256 in `registry/h66cover_preregistration.json`).
Namespacing (IR-H66-015): this round is the cover-gated co-training H66; the site's `h66-*` pages belong to
the structural-coherence H66 (PR #56).

## 1 · Independence screen (the brief's mandated empirical test)
Max |Spearman rho| of the two views' 50x50 px block OOF errors on held-out catalogue-zero negatives:
**0.1331** over 2,089 blocks
(threshold 0.60). Exchange allowed;
15,443 pseudo-label pixels in one whole-segment round.
Leakage canary: max single-feature raw AUC **0.6687** (alarm 0.90), any alarm: False.

## 2 · HOLDOUT-DTI (evaluator gems52-pooled-hide-v1)
| arm | HOLDOUT-DTI | 95% CI | withheld positives |
|---|---:|---:|---:|
| h66a_cover_gated_a_only | 0.045745 | [0.031303, 0.062135] | 53,186 |
| single_A | 0.071954 | [0.056636, 0.088566] | 53,186 |
| single_B | 0.174517 | [0.152316, 0.196299] | 53,186 |
| union_max | 0.148981 | [0.128084, 0.169418] | 53,186 |
| disagreement_pre | 0.033293 | [0.023815, 0.044556] | 53,186 |
| disagreement_post | 0.031535 | [0.020459, 0.044217] | 53,186 |
| random | 0.080426 | [0.070223, 0.090973] | 53,186 |

Paired difference, h66a minus single_B: **-0.128772**, 95% CI [-0.151680, -0.106031].

## 3 · Gates
* Format gate (single-band float32 GeoTIFF, EPSG:32611, shape and transform as pinned): **PASS**
* Values exactly {0, 1}; 0 NaN; 0 infinite: **PASS**
* Decoded-pattern uniqueness (not identical to any registry raster): **PASS**
* Exact novelty vs the 516 informative registry rasters (share of emitted cells that are not positive in any of them): **1.0000**
* Not the union of the two views: **PASS**
* Every emitted cell inside the A-only gate (A confident, B abstains): **PASS (633/633)**
* Independence screen (|rho| of block OOF errors on labelled negatives < 0.60): **PASS (max |rho| 0.1331)**
* Leakage canary (max single-feature AUC < 0.90): **PASS (max 0.6687)**
* Lane gate, literal, surface / dots: **PASS / DUPLICATE/STOP**
* Lane gate, saturation policy, surface / dots: **PASS / DUPLICATE/STOP**
* Holdout beats single_B (paired CI lower bound > 0): **FAIL**

## 4 · Limits
* The holdout instrument does not rank the board (`knowledge/10` section 5). These are HOLDOUT-DTI values only.
* Prevalence: the holdout withholds about 1.04% of the footprint; the competition truth is about 0.12-0.25%.
* The lane gate, uniqueness and projections are measured against the registry census available on disk at build time.
* The reasoning CSV is measured context plus a template hypothesis, not field-verified geology.
* The frozen A-only gate has only 1657 exact-novel cells, so the shipped emission is
  633 cells and the template budget 37600 is a cap (IR-H66-013).
* 100% of the emitted dots fall within 3 px of the H64 raster's dots, so the dots lane gate reads
  DUPLICATE/STOP and the file is not submittable (IR-H66-014).
