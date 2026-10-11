# 102 · H100 hypotheses, ranked — frozen BEFORE any H100 fit

Written 2026-10-10 in the H99/H100 session, branch `arena/f57253db-gemsdoe52`. This file is hashed into
`registry/h100_preregistration.json`; the shared runner `scripts/run_h99.py` refuses to start if either
the document or the pin has moved.

Round identity: **H100** is the second experiment of this session, and it exists because of a measured
H100-predecessor result (H99), not because of a guess. `knowledge/101` §3 froze H99; §4 of that file is
filled in only after its run. This document is frozen before the first H100 fit.

---

## 1 · What H99 measured, and why it forces this round

Instrument: `gems52-pooled-hide-v1`, `gems52.spatial.folds(cat, valid, buffer_px=80)`, 1000-draw paired
physical 20 km spatial-cluster bootstrap, K = 9,400 dots per fold per arm,
`nodes.spacing_select(min_px=3.0)`, 200 m collar from the fold's **visible** catalogue only.
Source: `evidence/h99_fit.json`, `evidence/h99_holdout.json`.

| arm (H99) | HOLDOUT-DTI | paired vs random (95 % CI) |
|---|---:|---|
| `xtex_dis` (primary: A-confident ∧ B-abstains) | **0.034799** | **−0.045627 [−0.054106, −0.037194]** |
| `xtex_agree` (min of the two views) | 0.128009 | −0.093211 [−0.107202, −0.078695] |
| `single_Atex` (View A texture alone) | 0.081910 | −0.047111 [−0.056514, −0.037718] |
| `single_Btex` (View B texture alone) | 0.164883 | — |
| `random` (floor, same allowed set) | 0.080426 | 0 (reference) |

**The random control reproduces the committed H82/H85 receipt 0.080426 exactly**, so the instrument is
reproduced in this clone.

Per-view spatial-block OOF AUC on the held-out region:

| view | fold 0 | fold 1 | fold 2 | fold 3 | mean |
|---|---:|---:|---:|---:|---:|
| View A texture (bands 2, 9, 13 — short lags 1–3 px) | 0.5275 | 0.5339 | 0.4929 | 0.5724 | **0.5317** |
| View B texture (bands 12, 19, 6 — short lags 1–3 px) | 0.6812 | 0.7500 | 0.6713 | 0.6848 | **0.6968** |

Independence (the brief's own test, spatial-block mean errors on labelled negatives, 200 px = 20 km
blocks): ρ = +0.4285, +0.3464, −0.0950, +0.4510; **max |ρ| = 0.4510**, below both the repository's
0.60 bar and the brief's 0.90 abandon bar. Leakage canary: max single-channel AUC **0.5977** (bar 0.90).

**Reading.** Independence passes but **sufficiency fails on View A for the ninth time in this
repository** (0.5317, one fold below chance). Blum & Mitchell's precondition is *both views
sufficient*; with View A at chance the exchange has nothing to donate, and the
A-confident-∧-B-abstains arm is worse than the random floor with a CI that excludes zero. That is a
clean, strict negative — the strongest form this repository has produced — and it is a deliverable.

The H99 result does **not** distinguish two explanations:

1. **The view itself carries no catalogue-fault signal** (potential fields at this footprint are
   dominated by source bodies, not boundaries), or
2. **The scale was wrong.** H99 computed semivariance anisotropy at lags 1–3 px = **100–300 m**.
   The kernel radius of the competition metric is 300 m and the grid is 100 m, so lags of 100–300 m
   probe the *near-surface* field. A fault buried beneath alluvial cover is a **deep** boundary; the
   sensitivity of a potential-field boundary texture to source depth scales with the lag.

H100 tests explanation 2, because it is the only one of the two that is actionable with bytes already
on disk.

## 2 · Ranked candidate hypotheses for H100 (new relative to everything in this repository)

| rank | id | layer(s) (band index, tag) | physical signature targeted | why it could catch a fault missing from the USGS/INGENIOUS catalogue | how it differs from everything already in this repo | cost | status |
|---|---|---|---|---|---|---|---|
| **1** | **H100-L "deep-scale View A"** | bands **2 `rtp`**, **9 `tmi_vg`**, **11 `iso_grav_anom_vg`**, **13 `iso_grav_anom`**, **15 `depth_to_base_surf`**, **17 `cond_surf`** | directional variogram anisotropy at lags **4, 6, 8 px = 400–800 m** | a concealed normal fault offsets basement by tens of metres under a flat top surface. At 400–800 m the gravity/magnetic boundary texture is sensitive to that offset; at 100–300 m (H99) it is dominated by near-surface and gridding noise. These are the brief's own View-A ingredients: gravity, magnetics, subsurface | every DVA channel in this repository (H75, H82, H84, H99) used lags 1–6 px with the **fan concentrated at 1–2 px**; the vertical-gradient gravity band 11, the cover band 15 and the conductivity band 17 have **never** carried a variogram channel at any lag | medium (~2 min channels, reuse `run_h61.setup`) | **RUN IN THIS ROUND — see `evidence/h100_*.json`** |
| 2 | H100-S "seismicity lineation texture at long lag" | bands 10 `deq_n100a15`, 16 `ieq_n100a15` | DVA of earthquake density | an active-but-unmapped fault must show a directional epicentral trend | the bands are in View A as raw channels only; their texture has never been isolated | low | **not run** (budget) |
| 3 | H100-B "cover-step detector" | band 15 `depth_to_base_surf` | oriented step in cover thickness (not texture) | a buried normal fault offsets the basement under a flat top | H85-next-B named it; no holdout receipt exists anywhere in this repository | low | **not run** (budget) |
| 4 | H100-M "multi-scale fusion of 1 and 3" | bands 2, 9, 11, 13, 15, 17 | DVA at lags 1–8 jointly | if the true boundary scale is unknown a priori, a two-scale fan should dominate either single scale | nothing in the repo fuses two lag families in one learner | low | **not run** (budget) |
| 5 | H100-A "ASTER/EMIT alteration indices" | external | clay / silica / iron-oxide absorption | surface alteration halo around a fault-fed hydrothermal system | **blocked in this sandbox**: egress allowlist is `github.com`, `codeload.github.com`, `api.github.com`, `registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org`. EarthExplorer and Earthdata both require a login | high | **blocked — needs an operator download with a SHA pin** |

Ranking is by (prior plausibility for a catalogue-missing fault) × (bytes on disk) ÷ (cost). No
expected-DTI number is asserted: nothing here has a validated estimate and a projection is never
written as a score.

## 3 · Frozen H100 protocol (identical to H99 except where stated)

* **Changed and frozen a priori, never tuned on the holdout**: `lags_px = [4, 6, 8]`,
  `view_a_bands = [2, 9, 11, 13, 15, 17]`, `view_b_bands = [12, 19, 6]` (unchanged), `sigma_px = 3.0`,
  the same eight-direction axial fan.
* **Unchanged**: `buffer_px = 80`; 200 m catalogue collar built from the fold's *visible* catalogue;
  K = 9,400 dots per fold per arm; `nodes.spacing_select(min_px = 3.0)`;
  evaluator `gems52-pooled-hide-v1` (α 0.2, β 0.8, 300 m triangular kernel); 1,000-draw paired
  physical 20 km spatial-cluster bootstrap; seed family `base.SEED`; the same five arms with the same
  definitions; the same sufficiency, independence (0.90 brief bar, 0.60 repo bar) and leakage-canary
  (0.90) reads.
* **Decision rule, frozen**: H100-L is **supported** only if `xtex_dis`'s paired difference against
  `random` has a 95 % CI whose lower bound is above 0. Anything else is a negative and is reported
  as one. A negative H100-L closes the "wrong scale" explanation for this footprint and leaves only
  "the view carries no catalogue-fault signal here".

## 4 · Result

Written after the run. See `evidence/h100_fit.json`, `evidence/h100_holdout.json`,
`evidence/h100_run_card.json`. Every number is labelled HOLDOUT-DTI with the evaluator version, the
withheld positive pixel count and a 95 % CI, or it is not reported.
