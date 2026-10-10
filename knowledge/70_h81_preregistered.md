# 68 · H81 — preregistration (frozen before any H81 fit, 2026-10-09)

Labels: HOLDOUT-DTI = reading of `gems52-pooled-hide-v1` (pooled, alpha 0.2, beta 0.8, 300 m triangular
kernel, whole-segment quadrant folds with buffer, visible catalogue masked). Nothing here is ORGANIZER-CONFIRMED.
Ranked candidate list that motivates this test: `knowledge/69_h81_hypotheses_ranked.md`.

## Hypothesis (H81-1)
Adding the **directional variogram anisotropy (DVA)** of band 18 `iso_grav_anom_hg` (isostatic gravity
horizontal gradient) to View B, on top of the H75 DVA channels (bands 12, 19, 13), improves hide-and-recover
recovery over H75's `B_DVA`.

Mechanism: a 300-900 m fault damage zone makes the local gravity-gradient texture direction-dependent
(strike-parallel smooth, strike-normal rough). Band 18 is a gradient of the gravity field, so its variogram
is a statistic of a different continuous field than H75's band 13 (gravity itself). Band 18 has never had a
variogram statistic in this repository (grep: 1 src file mentions it, and not as a variogram).

Named non-fault mimic: a gravity texture produced by bedding-parallel density contrasts in sediments or by
topographic-compensation residuals along range fronts would also be anisotropic.

## Arms (identical rows, learner, seed, folds and allowed masks as H75)
- `single_B` — **reused** from H75 predictions (`work/h75/pred_single_B_f*.npy`), not refitted.
- `B_DVA` — **reused** from H75 predictions (`work/h75/pred_B_DVA_f*.npy`), not refitted.
- `B_DVA18` — View B + H75's 12 DVA channels + 4 new band-18 DVA channels (anisotropy and log semivariance at
  lags 2 and 4 px). **The only new fit.** Canary per channel alone, held-out region AUC.
- `random` — reused from H75 (`SEED + 500 + fold`).
- Budget 9,400 dots/fold, 3 px spacing, allowed = fold region minus visible minus 200 m ring (as H75).

## Promotion rule (decided now)
PROMOTE the candidate **only if** the paired HOLDOUT-DTI difference `B_DVA18 − B_DVA` has a 95% CI lower
bound **> 0** (pooled, 1,000 draws, `evaluator.pooled_summary`, candidate `B_DVA18`), **and** the leakage
canary max AUC is **< 0.90**. Otherwise the verdict is NEGATIVE.

## What this round does NOT do
- No placement, no emission file, no competition slot. A PROMOTE here would only earn the right to run the
  lane gates in a later round.
- The lane gate (near-dot share ≤ 0.70 against any registry raster) is unchanged and is not evaluated here.
- No new preregistration amendment after the holdout is seen.

## Budget
1 experiment (of the protocol's 3 per round) and at most 2 hours of compute, counting the H75 reproduction
that feeds the reused arms.
