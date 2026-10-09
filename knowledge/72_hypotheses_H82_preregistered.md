# 67 · H82 — preregistration (frozen before any H82 fit, 2026-10-09)

Round identifier: **H82**. Lane: the brief's two-view paragraph, executed on the one branch of it that
this repository has measured as informative (View B), plus the lane-gate redefinition that H75's own
next-step list ranked first. Preregistered in this file; pinned by `registry/h82_preregistration.json`;
`scripts/run_h82.py` refuses to start if this hash moves.

Labels used everywhere below: **HOLDOUT-DTI** = a reading of the shared evaluator
`gems52-pooled-hide-v1` (hide-and-recover, whole fault segments withheld with an 80 px buffer, every
catalogue-derived feature computed from the fold's *visible* faults only, visible faults masked
pixel-exactly, pooled DTI at alpha 0.2 / beta 0.8 / 300 m triangular kernel, 95 % paired CI by
resampling physical 20 km blocks). **PREMISE-AUC** = out-of-quadrant ROC AUC of one feature or one
view. **PUBLIC-BOARD** = a number read off the organiser's leaderboard page (team-level, no filename).
**ORGANIZER-CONFIRMED** = copied from a submission-page receipt. Nothing in this round is
ORGANIZER-CONFIRMED. A projection is never written as a score.

## 0 · Lane status carried in (why this is not a seventh View A rebuild)

The brief's co-training paragraph requires two *sufficient* views. Sufficiency of View A has now been
measured six times and failed six times: mixed potential-field/subsurface View A out-of-quadrant AUC
0.5163 (H61), 0.5362 (H63 step), 0.5281 (H69 basement view), 0.5202 (H65), 0.5166 (H70), and
deformation-only View A2 0.5194 with a min fold of 0.5011 (H74). Both halves of the subsurface stack
are measured, so the failure is not attributable to the potential-field channels. `AGENTS.md` records
the standing instruction: **do not re-run the co-training lane with another View A rebuild.** Re-running
it unchanged would be a seventh identical experiment and would spend the whole budget on a known
negative. H82 therefore executes the two highest-ranked *untested* items this repo already carries:

* `knowledge/66` next step 2 — DVA at more lags and more bands (15 depth-to-basement, 18 gravity
  horizontal gradient) and DVA azimuth versus the regional strike.
* `knowledge/66` next step 1 — a lane registry restricted to *scored* submissions, preregistered
  before placement, then the lane retested.

H75 is the only arm in this repository ever to beat `single_B` on the shared holdout with a CI
excluding zero (HOLDOUT-DTI 0.186352 [0.164675, 0.207868] vs 0.174517 [0.152316, 0.196299], paired
+0.011835 [0.006791, 0.017362]). Its file was blocked only by the lane rule. Extending the measured
mechanism and fixing the measured blocker is the highest-P(win) move available inside the budget.

The brief's co-training *obligations that remain satisfiable* are all still executed and reported:
the single-view baseline comparison on hide-and-recover segments (`single_A` and `single_B` arms), the
leakage canary per feature, the not-the-union-of-the-two-views test, metric-aware placement, the
uniqueness gate, and normalization to [0, 1]. The independence test and the A-only geological
reasoning record are reported as **standing measurements** from H61/H74 (max |rho| 0.0765 < 0.60, so an
exchange is *allowed*; the exchange is not run because the donor view is measured non-sufficient, which
is the brief's own abandon condition read on sufficiency rather than on independence) — see §6.

## 1 · Candidate hypotheses (3–5, ranked; each names layers, signature, off-catalogue reason, novelty)

Checked against this repository by `grep -ri` over `src/` and `scripts/` on 2026-10-09 before writing:
`variogram` appears only in `scripts/run_h75.py` and `scripts/h75_write.py`; `azimuth.py` (axial
statistics, Mardia & Jupp doubled-angle construction, null of `cos2_mean` exactly 0) is used only by
`dicoincidence.py` and `h60.py` for lineament ridge energy; `topographic position`, `gabor`,
`steerable` and `flow_dir` return no implementation. Nothing below duplicates an existing channel set.

| # | Hypothesis | Layers | Physical signature targeted | Why it should catch a fault the USGS/INGENIOUS catalogue lacks | How it differs from anything implemented here | Expected DTI gain / cost |
|---|---|---|---|---|---|---|
| **1** | **DVA-2 — extended directional variogram anisotropy** | `training_features.tif` bands **12** det_elev, **19** det_elev_slope, **13** iso_grav_anom, **15** depth_to_base_surf, **18** iso_grav_anom_hg | semivariance gamma(h, theta) at lags h = 1, 2, 3, 4, 6 px (100–600 m) over an 8-direction integer fan; per pixel and lag: anisotropy (max-min)/(max+min), log10 mean gamma, and gamma range ratio | a fault damage zone / cover boundary 300–900 m wide makes the *continuous field* directionally heterogeneous. The statistic is second-order spatial covariance, not a gradient, Laplacian, Hessian or structure-tensor channel, and it is computed from the field alone — so it is off-catalogue by construction and does not need a mapped trace to fire | H75 used 3 bands x 2 lags x 4 directions = 12 channels. DVA-2 adds cover thickness (15) and gravity horizontal gradient (18), three more lags, four more directions → 50 channels. The H75 subset is exactly recoverable from it (§3), so H75's 0.186352 is a control, not a comparison to a different field | **high / medium** |
| **2** | **VSA — variogram azimuth vs strike alignment** | the same 5 bands at lag 2 px; the fold's **visible** catalogue only | argmax azimuth of gamma per pixel converted to an axial angle, then `azimuth.axial_agreement`'s `cos2_mean` against (a) the per-fold **regional** strike and (b) the **local** strike, both measured from the smoothed visible-catalogue mask by structure-tensor axial resultant | maximum semivariance lies *across* strike for a damage zone. Where the local across-strike direction agrees with the regional Basin-and-Range fabric but no trace is mapped, the pixel is a candidate unmapped or oblique segment. The agreement statistic has a **null of exactly 0** (pinned in `tests/test_azimuth.py`), so it cannot call unrelated fields "aligned" | no code in this repo couples a variogram azimuth to a catalogue-measured strike. `azimuth.py` is used only for lineament ridge energy (H60). Strike is derived per fold from visible faults only, which is exactly what the brief's holdout rule requires | **high / medium** |
| **3** | **Antithetic paired-margin asymmetry** | band **15** depth_to_base_surf, with band 13 as context | sign-asymmetric basement-gradient pairs sampled across basin centres (the H65/H67-B operator family on a new band pair) | half-graben asymmetry means the gently dipping margin is *systematically* under-mapped — a population of faults, not scattered points | untested on band 15 pairs; `h55_paired_shoulders` is a DEM-flank operator, not a basement-thickness one | medium / medium — **deferred**, budget does not admit it (§5) |
| **4** | **Scored-registry lane redefinition** | `registry/` + `evidence/ctd5_prior_inventory.json` + `data/scored/` | not geology: the lane gate's denominator | n/a | `knowledge/66` next step 1. The literal rule is evaluated against 565 census blobs, of which many are dense 37k-dot rasters whose 3 px halos cover almost the whole footprint, so *every* surface-ranked emission is a "duplicate" by construction (measured in H69, H73, H75). Restricting to owner-scored submissions tests the rule's actual intent — am I in someone else's lane — instead of the registry's density | **shipping blocker / low** — run alongside 1+2 |
| **5** | **Drainage-deflection corridors** | 1 m DEM (USGS 3DEP) + bands 12/19 | D8 flow-direction deflection and straightened reaches across a buried scarp | the classic covered-fault criterion in Basin-and-Range piedmonts | **BLOCKED, not viable from this sandbox.** Specific free official source named and checked: USGS 3D Elevation Program, <https://www.usgs.gov/3d-elevation-program> (public domain, free of charge), plus the competition's own tile list `1m_DEM_links.csv` at <https://www.drivendata.org/competitions/306/competition-doe-gems/data/>. Both re-checked 2026-10-09: the data tab is login-walled and bash egress to `www.usgs.gov` / `www.drivendata.org` returns HTTP 000 from this sandbox. Reachable substitute already in View B: `data/external/lidar_scarp_features_u8.tif` (owner CI reduction, 706/716 tiles) | high / **not obtainable here** |

Ranking criterion is the one `knowledge/51` §3 sets: how slowly the marginal credit density rho(S)
decays with budget, because `knowledge/49` §4(b) shows the binding constraint on the score is the
ranker's rho(S) decay, not the emission budget.

## 2 · Inputs, integrity and provenance

Restored by `python3 scripts/restore_data.py --target-dir data` and verified against
`registry/data_manifest.json`: **23/23 SHA-256 pins, ALL_VERIFIED=True** (receipt
`data/restore_receipt.json`). Provenance class: **integrity-pinned, not organizer-authenticated** — the
pins authenticate the owner's mirror bytes, not the organiser's portal, which is login-walled and
unreachable from this sandbox. Feature stack: the shared cached store `work/r2/features`, rebuilt with
the repository's own `gems52.structural.build` and extended once by `python -m gems52.external`
(version `structural-core-v2-band6-B+external-geodawn-v1`, 78 columns, View A 36 / View B 37). No
private fork of the stack, the sampler, the splitter, the learner, the evaluator, the placement
function, the writer or the gates.

Environment measured, not assumed: 2 CPU cores, 3 GB RAM, 16 GB free disk, Python 3 with
numpy/scipy/rasterio/scikit-learn/scikit-image/pandas/pyproj installed from PyPI (bash egress permits
`pypi.org`; it does **not** permit `www.drivendata.org`, `www.usgs.gov` or `*.github.io`). The feature
stack is therefore rebuilt from restored bytes rather than reused from a cache — the same documented
environment-driven deviation `knowledge/59` records, not a re-implementation.

## 3 · Feature construction (frozen; the H75 subset is exactly recoverable)

Direction fan (integer offsets, exact on a square grid), with H75's convention preserved — the
semivariance is divided by `hypot(dy, dx) / h` so that a diagonal offset of the same nominal lag
contributes comparably:

```
GROUP1 (H75's four directions, theta = 0, 45, 90, 135 deg):  (0,h) (h,h) (h,0) (h,-h)
GROUP2 (four more, theta = 26.565, 63.435, 116.565, 153.435 deg): (h,2h) (2h,h) (2h,-h) (h,-2h)
lags h in {1, 2, 3, 4, 6} px  ->  100, 200, 300, 400, 600 m
```

Per band: standardize on the eligible footprint (mean/sd of finite eligible pixels), normalized
Gaussian smoothing of the validity mask (sigma 3.0 px, same as H75), `d2 = 0.5 (z_shift - z)^2` masked
by joint validity, smoothed and divided by the smoothed mask. Then per (band, lag):

* `DVA2_<band>_aniso_l<h>` = (max_theta gamma - min_theta gamma) / (max + min + 1e-9), all 8 directions
* `DVA2_<band>_logvar_l<h>` = log10(mean_theta gamma + 1e-9)

= 5 bands x 5 lags x 2 = **50 channels**. The H75 control arm uses the same code with
`bands = {12, 19, 13}`, `lags = {2, 4}` and GROUP1 only, which reproduces H75's 12 channels exactly by
construction; that arm is a *control*, and its HOLDOUT-DTI must reproduce 0.186352 within 1e-3.

VSA channels (lag h = 2 px only, all 8 directions):

* `theta_max(x)` = argmax_theta gamma(x, theta) mapped to an axial angle in [0, pi)
* regional strike `psi_reg(fold)` = axial resultant of the local trace directions of the fold's
  **visible** catalogue, computed as `0.5 * atan2` of the structure tensor of the smoothed visible mask
  weighted by tensor magnitude; reported with its resultant length `R_reg` per fold
* local strike field `psi_loc(x)` = the same structure-tensor axial angle at each pixel of the smoothed
  visible mask, plus its magnitude `XVSA_visible_tensor_mag` (one channel, canaried like any other)
* `VSA_<band>_cos2reg_l2` = `cos(2 * axial_difference(theta_max, psi_reg + pi/2))`
* `VSA_<band>_cos2loc_l2` = `cos(2 * axial_difference(theta_max, psi_loc + pi/2))`

= 5 + 5 + 1 = **11 channels**. Total new channels: **61**. Every channel is label-free except the two
strike references, which use the fold's visible catalogue only and are recomputed per fold — never from
a withheld segment.

## 4 · Test (experiment 1), arms, and the promotion rule

Shared instrument, unchanged: `run_h61.setup` / `sample_for_fit` / `learner_for` / `pct_rank` /
`to_grid`, `gems52.spatial.folds` (label-blind-quadrants-v2, buffer 80 px), `gems52.nodes.spacing_select`
(min 3 px spacing), `gems52.evaluate_holdout` (`gems52-pooled-hide-v1`, block_side 200 px = 20 km).
Budget **9,400 dots per fold per arm** (the H71/H73/H74/H75 matched budget), 4 folds, allowed set =
`fold.region & ~fold.visible & (distance to visible > ring_px)` with `ring_px` = the H61
catalogue-exclusion collar.

Arms, in the frozen order they are computed:

| arm | features | role |
|---|---|---|
| `single_B` | View B (37 cols) | **instrument control** — must reproduce 0.174517 within 1e-3 |
| `B_DVA` | View B + H75's 12 DVA channels | **H75 control** — must reproduce 0.186352 within 1e-3 |
| `B_DVA2` | View B + 50 DVA-2 channels | attribution for hypothesis 1 |
| `B_VSA` | View B + 11 VSA channels | attribution for hypothesis 2 |
| **`B_DVA2_VSA`** | View B + all 61 new channels | **PRIMARY arm** (preregistered, chosen before any fit) |
| `single_A` | View A (36 cols) | the brief's single-view baseline and the not-the-union test |
| `random` | uniform on the allowed set | the below-random reference (0.080426) |

**Promotion rule (decided now, on the primary arm only):** promote iff
`B_DVA2_VSA − single_B` paired 95 % CI lower bound > 0. Attribution arms `B_DVA2` and `B_VSA` are
reported verbatim and are **not** eligible to be promoted post hoc — selecting the best of five arms
after seeing the CIs is the multiple-comparison error this rule exists to prevent. If the primary arm
fails, the verdict is NEGATIVE and any file emitted is labelled research-only.

**Leakage canary:** every one of the 61 new channels alone, direction-insensitive AUC on each fold's
held-out region sample. AUC >= 0.90 = leakage alarm; the arm is not trusted until the alarm is cleared.

## 5 · Experiments, budget, and what is explicitly deferred

Budget: **3 experiments, 2 hours** (the brief's cap). Slots: **0** may be spent by this round —
promotion to a real slot is a separate selector step.

* **E1** — build the 61 channels, run the canary, fit all 7 arms x 4 folds, pooled holdout with paired CIs.
* **E2** — lane gate on the primary field, surface (before placement) and dots (after placement),
  against **both** registries: (a) the full 565-blob census (the literal rule, reported verbatim), and
  (b) the preregistered scored-only registry of §5.1. If the literal rule fails on either, run the
  shared `run_h73.place_lane` quota placement at K = 37,654 and report the achieved worst share and fill.
* **E3** — full-domain stitched field, 200 m catalogue ring excluded (the measured 0.2600 → 0.2778
  mechanism, `knowledge/49` §1), binary {0,1} emission at 3 px spacing, K_TOTAL = 37,654 (the champion
  mass and this repo's standard budget), GeoTIFF written by `gems52.submission_writer`, validated from
  disk, uniqueness gate, not-the-union test, A-only/B-only reasoning export, run card.

Deferred and not attempted this round, with the reason: hypothesis 3 (antithetic band-15 pairs) —
budget; any budget search over K_TOTAL — would be a fourth experiment; the co-training pseudo-label
exchange — the donor view is measured non-sufficient (§0).

### 5.1 The scored-only registry (frozen before any placement is computed)

Membership rule, decided now: a prior enters the restricted registry iff it is a single-band raster
aligned to the competition grid **and** the owner has reported a public-board score for that filename
in this repository's own score list (`README.md` / `knowledge/49`), or it is one of the organiser-side
calibration files pinned in `registry/data_manifest.json` under `scored_*` / `ref_*`. Concretely the
candidates are the files restored to `data/scored/` (11 files) and `data/reference/h33-2-b2-zeros.tif`
(1 file), i.e. **at most 12 rasters**, each with an owner-reported number. Everything else in the
526-blob census — including this repository's own 100+ research files, which carry no score — stays in
the literal registry of §4/E2(a) and is reported there.

This is a **loosening** of the literal rule and is declared as such. It does not waive anything: E2
reports the full-census verdict verbatim, and per the frozen doctrine recorded in `AGENTS.md` and
`knowledge/62` (IR-H73-011) *a policy PASS never waives a literal DUPLICATE/STOP*. The restricted
registry is evidence about the rule's intent; it is not a substitute verdict.

## 6 · Falsifiers, and what a negative result would mean

* If `B_DVA2_VSA` does not beat `single_B` with a CI excluding zero, then extending the only
  measured-positive ranker in this repo with 61 more second-order/anisotropy channels does not help,
  and the DVA mechanism is at its ceiling — the honest conclusion is that the family's rho(S) curve
  cannot be moved by feature engineering on these 19 bands, which is `knowledge/49` §4(c) confirmed
  once more. That is a deliverable, not a failure to report.
* If the canary alarms on any VSA channel, the strike reference is leaking catalogue geometry and the
  arm is discarded regardless of its DTI.
* If `B_DVA2` wins but `B_VSA` does not, hypothesis 2 is dead and should not be re-tuned.
* If the primary arm beats `single_B` but the lane fails on the full census *and* on the scored-only
  registry, no lane-valid emission exists from this field and the file is research-only.
* Named non-fault process that could mimic the DVA-2/VSA signal: **lithologic and alluvial-fan fabric.**
  Basin-and-Range piedmonts carry 300–900 m wide fan margins, dyke swarms, joint sets and volcanic
  flow contacts that are directionally anisotropic and strike-parallel without being faults; roads and
  erosion lines produce the same anisotropy on `det_elev` at 100 m. This is the brief's own View-B
  caveat and it is the reason every emitted cell carries a written reasoning row in E3.

## 7 · Expected board outcome, stated before the holdout is read

`knowledge/49` §4/§6 is arithmetic on organiser-scored bytes and it bounds this round honestly. At
S = 37,654 the required credit density is rho = 0.1387 to reach 0.2778, 0.1595 to reach 0.3195 and
0.1884 to reach 0.3774 (at |G| = 14,088.7). The champion's own measured rho is 0.1387; uniform random
is 0.0279. A **wholly novel** emission — which the lane rule requires — therefore has an expectation
bracket of roughly DTI in [0.04, 0.21] unless the new ranker sustains rho above the champion's. **No
claim is made here that H82 will beat 0.2778, 0.3195 or 0.3774.** HOLDOUT-DTI is not a board forecast:
this repository measured Spearman −0.10 between holdout DTI and public-board score across the R4 arms.
The public board is also not the scored set — the Initial Prize Round is scored on the *private* chunk
and the Final Prize Round rescores against an expanded expert-verified label set, which is why E3 writes
a reasoning row per emitted cell.

## Amendment 72a (written BEFORE any H82 fit, canary or holdout reading; re-pin required)

Four definitional fixes, adopted before a single number in this round existed, so none of them is a
post-hoc selection:

1. **`XVSA_visible_tensor_mag` is removed from the learner channel set** and kept as a *reported
   diagnostic* only (its per-fold direction-insensitive AUC is still measured and published). Reason:
   it is a monotone function of distance to the fold's visible catalogue, which is proximity
   information rather than directional information, and it would predictably trip the 0.90 canary alarm
   on a held-out-segment target and discard the whole arm. New channel count: **60** (50 DVA-2 + 10 VSA).
   The exclusion is declared before measurement, not after seeing an alarm.
2. **VSA convention fixed:** `cos2reg` and `cos2loc` are evaluated at *every* eligible pixel from the
   tensor angle; only pixels where the tensor anisotropy is exactly 0 (degenerate, no orientation
   information at all) take the value 0. No epsilon threshold is applied, because a threshold makes the
   channel zero-inflated in a halo around visible traces and therefore proximity-like rather than
   direction-like. `cos2reg` uses a single per-fold scalar strike and is proximity-free by construction.
3. **Actual offsets recorded.** GROUP2 offsets `(h,2h) (2h,h) (2h,-h) (h,-2h)` have length `h*sqrt(5)`
   px, so their nominal lag `h` is the *cardinal reach*, not the offset length; the semivariance is
   divided by `hypot(dy,dx)/h = sqrt(5)` exactly as H75 divided its diagonals by `sqrt(2)`. The 8
   axial directions are 0, 26.565, 45, 63.435, 90, 116.565, 135, 153.435 deg in the image (dy,dx)
   frame; the compass conversion used for reporting is `azimuth_compass = (90 - phi) mod 180`. The fan
   is symmetric over [0,180) but not uniformly spaced — a stated limitation of the integer-grid fan.
4. **Prediction domain.** Predictions are computed on each fold's `region` only, not on the whole
   eligible domain. This is provably sufficient and changes no statistic: the evaluator masks to
   `valid & region & ~visible`, the placement's allowed set is a subset of `region`, the per-fold
   percentile rank in both the holdout and the build is taken over indices inside `region`, and the
   build's stitch fills every pixel from the fold whose region contains it (the four regions partition
   `eligible`). It is a compute optimization for a 2-core / 3 GB sandbox, not a change of instrument.
   The check that it changed nothing is the two controls: `single_B` must reproduce **0.174517** and
   `B_DVA` must reproduce **0.186352**, each within 1e-3.
