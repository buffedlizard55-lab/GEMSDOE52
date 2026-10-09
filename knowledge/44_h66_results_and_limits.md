# 44 · H66 results and limits (rendered from the receipts by `scripts/publish_h66_site.py`)

**Verdict: `NEGATIVE, research-only. DOWNLOAD YES (format-valid and unique on decoded pixels); SUBMIT NO. lane_policy=False; holdout_beats_single_B=False. No weekly slot spent by this lane.`**

Artefact `gems52-h66-aonly-stratum-fallback-uncapped-3080px-20261009T073227Z.tif`, SHA-256 `369b844e04c4b092d63215cf325eae6872042e4e56c7576dcf0ef41d111ea95c`, 64933 bytes, 3080 emitted cells,
every one a strict A-only discovery candidate with a written geological reasoning row
(`docs/downloads/h66-a-only-reasoning.csv`). Pre-registration: `knowledge/43_hypotheses_H66_preregistered.md`
(SHA-256 in `registry/h66_preregistration.json`).

## 1 · What H66 changed

H61/H64 emitted the continuous rank difference A−B; H66 emits the lane's discovery signal directly — the strict
A-only stratum (View A out-of-fold rank ≥ 0.95, View B rank in the abstain interval [0.35, 0.65]) — and places it
inside the **lane-quiet domain**: at least 3 px from every informative registry prior's positive pixel, so the
directed near-dot fraction against every informative prior is 0 by construction (the lane's own 70% rule) instead of
capped re-placement (H64's constrained greedy could not fill its budget: 31,487 of 37,600).

## 2 · Independence and premise (the lane's mandated tests)

Independence screen (spatial-block OOF errors on labelled negatives, held-out catalogue-zero proxies): max |ρ|
**0.1337** against the 0.60 abandon bar → exchange
**allowed**. Premise control (not re-tuned): View A out-of-quadrant
AUC mean **0.5163**, View B mean **0.6843**. Leakage canary:
max alarm AUC **0.6687**, any alarm **False**
(bar 0.90).

## 3 · HOLDOUT-DTI (evaluator gems52-pooled-hide-v1), matched budget 1264 dots/fold

| arm | HOLDOUT-DTI | 95% CI | withheld positives |
|---|---:|---:|---:|
| a_only | 0.009532 | [0.005836, 0.014281] | 53,186 |
| single_B | 0.059676 | [0.047002, 0.073687] | 53,186 |
| single_A | 0.013884 | [0.008789, 0.019546] | 53,186 |
| union_max | 0.045017 | [0.035240, 0.056095] | 53,186 |
| random | 0.012329 | [0.009853, 0.014929] | 53,186 |

Paired difference, candidate (a_only) minus single_B: -0.050144, 95% CI [-0.064233, -0.036779].
Control reproduction at the H61 budget (9,400 dots/fold): single_B 0.174571 vs committed H61
0.174517, |Δ| 5.44e-05 (tolerance 0.001).

## 4 · Gates
* Format gate (single-band float32 GeoTIFF, EPSG:32611, shape and transform as pinned): **PASS**
* Values exactly {0, 1}; 0 NaN; 0 infinite: **PASS**
* Decoded-pattern uniqueness (not identical to any of the 553 registry rasters): **PASS**
* Support novelty vs the 516 informative registry rasters: **0.3104**
* Not the union of the two views: **PASS**
* Lane gate, literal, surface / dots: **PASS / DUPLICATE/STOP**
* Lane gate, saturation policy, surface / dots: **PASS / DUPLICATE/STOP**
* Lane policy max near-dot share (bar 0.70): **0.8903**
* Audit (audit_uniqueness.py, census): surface max Spearman / dots max near-3px: **0.0232 / 1.0000**
* Holdout beats single_B (paired CI lower bound > 0): **FAIL**

## 5 · Limits
* The holdout instrument does not rank the board (`knowledge/10` §5, `knowledge/31` §2). These are HOLDOUT-DTI values only.
* The literal lane rule fails for every nonempty raster on this registry (measured universal-coverage lattice probe);
  the policy verdict classifies probes by measured coverage ≥ 0.95 and is the repository's authoritative lane.
* Prevalence: the holdout withholds about 1.04% of the footprint; the competition truth is about 0.12–0.25%.
* Inputs are SHA-256-pinned owner mirrors, not organiser-authenticated downloads.
* The reasoning CSV is measured context plus a template hypothesis, not field-verified geology.
