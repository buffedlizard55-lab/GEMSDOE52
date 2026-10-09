# 63 · H74 — preregistration (frozen before any H74 fit, 2026-10-09)

Labels: HOLDOUT-DTI = reading of `gems52-pooled-hide-v1` (pooled, alpha 0.2, beta 0.8, 300 m triangular kernel,
whole-segment quadrant folds with buffer, visible catalogue masked). Nothing here is ORGANIZER-CONFIRMED.

## Lane status carried in
The brief's co-training lane (View A geophysics × View B surface) failed View-A sufficiency five consecutive
rounds (H62–H70, AUC ≈ 0.52; `knowledge/55`). Re-running it unchanged would be a sixth identical experiment, so
H74 does **not** re-fit co-training. It tests the top-ranked untested hypothesis from `knowledge/62` §4.

## Candidate hypotheses (ranked; cost = implementation effort here)
| # | Hypothesis | Layers | Signature | Why off-catalogue | New vs repo | Exp. gain / cost |
|---|---|---|---|---|---|---|
| 1 | **Directional variogram anisotropy (DVA)** | band 12 det_elev, band 19 det_elev_slope, band 13 iso_grav_anom | local semivariance at lags 2/4 px in 4 azimuths; anisotropy=(max−min)/(max+min) | statistic of the continuous field, not of catalogue traces; a 300–900 m damage zone makes the field anisotropic even where no trace is mapped | grep `variogram` in src/scripts: no implementation | medium / medium |
| 2 | Antithetic paired-margin asymmetry (band 15 depth to basement) | 15 | asymmetric basement-gradient pairs across basins | gentle half-graben margins under-mapped | untested (H67-B) | medium / medium |
| 3 | Lane-aware placement with target-budget quotas | registry | placement only | n/a (no geology) | partial (H69/H73) | low / low |
| 4 | Deformation-only View A2 (bands 4,7,8) | 4,7,8 | strain-rate gradients | geodetic, independent of maps | untested (H70-E) | low (coarse 10 km) / low |

## Test (one experiment, budget 3)
Arms at 9,400 dots/fold, 3 px spacing, allowed = fold region \ visible \ 200 m ring:
`single_B` (H61 rows/learner/seed — must reproduce 0.174571 within 1e-4), `B_DVA` (View B + 12 DVA channels,
same rows/learner/seed), `DVA_only`, `random`.
**Promote rule:** `B_DVA` − `single_B` paired 95 % CI lower bound > 0. Otherwise verdict NEGATIVE.
**Canary:** each DVA channel alone, held-out region AUC; ≥ 0.90 = leakage alarm.
**Emission (regardless of verdict, labelled research if negative):** full-domain stitched B_DVA rank, cells within
200 m of the catalogue excluded (the measured 0.2600→0.2778 mechanism, `knowledge/49`), binary {0,1}, 37,654 dots,
3 px spacing. Gates: rank-corr ≤ 0.90 and near-dot share ≤ 0.70 against every registry raster available locally.

## Amendment 63a (written after the experiment-1 holdout and the dots lane gate, BEFORE experiment 2)
Experiment 1 result: B_DVA beat single_B on the holdout; surface lane PASS; dots lane DUPLICATE/STOP (policy max
near-dot 0.9220, 38 informative offenders). Experiment 2 = the H73 amendment-61a placement (`run_h73.place_lane`,
greedy + per-prior quota at floor(0.70·K), up to 8 re-placement rounds) applied unchanged to the B_DVA field over
the same 200 m-ring-excluded pool, K = 37,654. If it fills K with worst share ≤ 0.70, the same placement is run per
fold at 9,400 dots and must still beat single_B (paired CI lower bound > 0) before any file is called submittable.
If it does not fill, the file is published as research-only with the lane failure stated.

## Amendment 63b (after experiment 2, BEFORE experiment 3 — the last of 3)
Experiment 2: place_lane at K = 37,654 short-filled (35,858 dots; worst 0.7350; 23 quota priors) — the same
denominator wall H73 measured. Capacity outside the 23 quota halos ≈ 35,858 − 0.70·37,654 ≈ 9,500 dots, so the
30 % non-halo share is reachable only for K ≲ 31,600. Experiment 3 = the identical placement at one fixed budget
**K = 30,000** (holdout 7,500 dots/fold), no further budget search. Same promotion rule as 63a.
