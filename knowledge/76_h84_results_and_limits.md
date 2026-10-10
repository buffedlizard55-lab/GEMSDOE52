# 76 · H84 — results and limits (2026-10-10)

Preregistration: [`knowledge/74`](74_hypotheses_H84_preregistered.md) (frozen 2026-10-10T19:54:01Z, SHA-256
pinned in `registry/h84_preregistration.json`, not edited after the freeze). Runner: `scripts/run_h84.py`
(stages `channels fit holdout independence build lane write card`, each in its own process). Machine
receipts: `evidence/h84_*.json`; run card `evidence/h84_run_card.json`. Brief: [`knowledge/75`](75_current_user_brief_2026-10-10_H84.md).

> **Round number.** Preregistered and run as **H83**; renamed **H84** at merge because two parallel sessions
> merged their own H83 rounds to main meanwhile (IR-H84-006). The rename is identifier-only: replacing H84→H83
> in `knowledge/74` reproduces the frozen SHA-256 `521eca05…` byte-for-byte. The GeoTIFF bytes are unchanged.
> Lane check of the H84 dots against the three parallel H83 rasters: max ρ 0.0095, near-3px 0.2418, none
> identical → PASS (`evidence/h84_lane_vs_parallel_h83.json`). The parallel H83 structcon file is marked
> SUBMIT YES on main with `holdout_dti: NOT_EVALUATED`; see IR-H84-007 before acting on it.

## Verdict: NEGATIVE — DOWNLOAD YES, SUBMIT NO, 0 slots used, 1 of 3 experiments used

The harmonic (elliptical) variogram-anisotropy channels **did not beat the current holdout best**. The
primary `B_DVA2_HVA` is 0.002682 *below* its own control `B_DVA2` in the paired comparison, with a 95% CI
[−0.005505, +0.000177] that straddles zero. That is what §7 of the preregistration said was most
likely. Three of eight frozen gates fail (1, 3, 5 below). The raster exists, is format-valid and
decoded-distinct, and is published as a research artefact only.

## 1 · Holdout (HOLDOUT-DTI)

Evaluator `gems52-pooled-hide-v1`, 53,186 withheld positive pixels, folds `label-blind-quadrants-v2`
(80 px buffer), 9,400 dots per fold per arm, α 0.2 / β 0.8, triangular R 300 m, 95% paired spatial-cluster
bootstrap with 1,000 draws. Holdout DTI does not rank board scores in this repository (Spearman −0.10,
`knowledge/10` §5), so **none of these numbers is a board forecast.**

| arm | role | HOLDOUT-DTI | 95% CI | primary − arm (paired) | mean out-of-quadrant AUC |
|---|---|---:|---|---|---:|
| **`B_DVA2_HVA`** | PRIMARY | **0.190147** | [0.168893, 0.211154] | — | 0.7111 |
| `B_DVA2` | control / current holdout best | 0.192829 | [0.170790, 0.213691] | **−0.002682 [−0.005505, +0.000177]** | 0.7118 |
| `B_DVA2_HVA_COH` | attribution (not promotable) | 0.190565 | [0.169058, 0.211437] | −0.000418 [−0.002816, +0.002202] | 0.7128 |
| `single_B` | single-view baseline / control | 0.174571 | [0.152313, 0.196302] | +0.015576 [+0.007964, +0.023699] | 0.6843 |
| `single_A` | single-view baseline (View A) | 0.071954 | [0.056636, 0.088566] | +0.118193 [+0.098982, +0.136335] | 0.5163 |
| `random` | floor | 0.080426 | [0.070223, 0.090973] | +0.109722 [+0.092175, +0.129440] | — |

Per-fold out-of-quadrant AUC, primary vs `B_DVA2`: 0.6872/0.6840, 0.7881/0.7867, 0.6450/0.6479,
0.7241/0.7284. The primary is ahead in 2 folds and behind in 2. COH-attribution minus `B_DVA2`:
−0.002264 [−0.005032, +0.000463].

**Reading.** At fixed lag, the harmonic eccentricity √(b²+c²)/a carries almost exactly the information
DVA-2's (max−min)/(max+min) already carries. Adding 25 HVA channels to the 50 DVA-2 channels adds
redundancy, not signal; adding 5 COH channels does not help either. View B with any anisotropy family
beats `single_B` (+0.0156 with the CI clear of zero), which re-confirms H75/H82: **directional variogram
anisotropy helps, but the reduction operator is not the bottleneck.**

## 2 · Frozen promotion gates (knowledge/74 §3)

| # | gate | result |
|---|---|---|
| 1 | primary − `B_DVA2` CI lower bound > 0 | **FAIL** (−0.005505) |
| 2 | primary − `single_B` CI lower bound > 0 | PASS (+0.007964) |
| 3 | controls reproduce within 1e−3 | **FAIL**: `single_B` 0.174571 vs 0.174517 PASS; `B_DVA2` 0.192829 vs 0.189200 (|Δ| 3.63e−3) FAIL → IR-H84-005 |
| 4 | leakage canary < 0.90 | PASS (max single-channel AUC 0.6237, `HVA_det_elev_slope_h2amp_l2`) |
| 5 | lane: literal surface PASS and literal full-census dots PASS | **FAIL** (surface PASS, dots DUPLICATE/STOP) → IR-H84-001 |
| 6 | format validator and not-the-union | PASS / PASS |

## 3 · Co-training obligations (Blum & Mitchell 1998, <https://doi.org/10.1145/279943.279962>)

* **Independence** (spatial-block OOF errors on labelled negatives): max |ρ| **0.1337** over 2,089 blocks /
  4,095,103 proxy negatives; abandon bar 0.60 → not strong, exchange *allowed by this test*. The instrument's
  caveat applies: the negatives are catalogue-zero proxies, and weak error correlation is necessary for
  co-training but does not prove conditional independence.
* **Sufficiency of View A**: mean out-of-quadrant AUC 0.5163, worst fold 0.4668 (gates 0.60 / 0.55) →
  **FAIL, for the eighth time in this repository.** There is no confident donor view, so **the pseudo-label
  exchange was not run.** This standing deviation is stated in the preregistration, not hidden; H71/H74 measured
  that exchange lowered the receiving view's AUC.
* **Disagreement as discovery**: the A-only stratum (View A rank ≥ 0.95 ∧ primary rank ∈ [0.35, 0.65]) has
  52,589 px → 9,225 spacing-thinned candidates, each with a geological-reasoning row: reading, named mimic,
  falsifier, confidence (`docs/downloads/gems52-h84-hva-ellipse-B-37654px-20261010T204630Z-a-only-reasoning.csv`).
  All are marked LOW confidence because View A failed sufficiency. B-only: 9,691 candidates; the share
  within 5° of N–S/E–W (section-line roads/fences) is 0.0809 against an isotropic null of 0.1111, so there
  is **no** road/section-line excess.
* **Single-view baselines on the same instrument**: `single_B` and `single_A` above.
* **Not the union**: 3,961 of 37,654 cells are shared with the equal-budget union-max placement (Jaccard
  0.0555); 568 shared with View-A-only (0.0076) and 5,524 with View-B-only (0.0792). The file is identical to,
  and a subset of, none of them → PASS.

## 4 · Lane and uniqueness

| check | verdict | statistic |
|---|---|---|
| surface vs literal full census (584 rasters) | PASS | max Spearman 0.4953 |
| surface vs scored-only registry (13) | PASS | max Spearman 0.1895 |
| final dots vs literal full census | **DUPLICATE/STOP** | max near-3px 1.0000 (lattice probes); max Spearman 0.1939 |
| final dots vs full census, informative-prior policy | **DUPLICATE/STOP** | max near-3px 0.9441 vs GEMSDOE22 `gems22-h23-b-dti-optimal-emission-10pct-…-allfinite.tif`; 56 dense offenders, all Spearman ≤ 0.054 |
| final dots vs scored-only registry | literal DUPLICATE (1 lattice probe) / policy PASS | policy max near-3px 0.6983 (the quota placement's bound) |
| decoded uniqueness | distinct from all 584 compared priors | no identical prior; audit complete |

Placement: `run_h73.place_lane` quota placement against the scored-only informative supports filled
37,654/37,654 cells at 3 px spacing, worst share 0.6983 (bar 0.70), from a 4,325,298-px pool with the 200 m
catalogue ring excluded. Catalogue distance of emitted cells: minimum 223.6 m, median 1,431.8 m, 15.28% within
300 m. Overlap with named priors: the OWNER-REPORTED 0.2778 file shares 1,644 cells (Jaccard 0.0223); H82
shares 2,839 (0.0392).

## 5 · The file

`submission/gems52-h84-hva-ellipse-B-37654px-20261010T204630Z.tif` = `docs/downloads/h84-candidate.tif`,
141,678 bytes, SHA-256 `6bb18056c521a1a6a7bcefa75f3be7cb37653b8066efd4252a8b5c096b90b73e`. ZIP
`docs/downloads/h84-candidate.zip` (SHA-256 `feee6d3c…59fd`) holds the same bytes. Validator (re-read from disk
and checked again independently): 1 band float32, EPSG:32611, 3730×3292, transform/bounds equal to
`data/sample_submission.tif`, values exactly {0, 1}, 0 NaN, 0 infinite, 37,654 ones, 0 ones outside the
footprint, 0.0 everywhere else.
Name `h84-hva-ellipse-B-37654px-20261010T204630Z`; note (126/140) `H84: View-B + DVA2 + harmonic
variogram-ellipse anisotropy (8-dir LS fit, lags 100-600m); 200m ring cut; binary dots; research`.

## 6 · Why 0.2778, and can it be beaten (answer carried from knowledge/49, unchanged by H84)

`h33-2-b2` (OWNER-REPORTED 0.2778) is the OWNER-REPORTED 0.2600 file with its 100–200 m catalogue ring
deleted: 6,436 px removed, nothing added. Its credit density ρ = 0.1387 at |G| = 14,088.7 is 5.0× uniform
random, and it sits exactly where its own field stops paying. At 37,654 px, reaching the PUBLIC-BOARD #8
score 0.3195 needs ρ = 0.1595 (+15%), and #1 (0.3774) needs ρ = 0.1884. H84 does not change this. Holdout
gains of +0.0156 over `single_B` cannot be converted into a board forecast here (Spearman −0.10).

PUBLIC-BOARD 2026-10-10 (`registry/leaderboard_snapshot_2026-10-10.json`): #1 0.3774, #2 0.3418, #3 0.3361,
#8 0.3195, #22 0.2778 (team-level; the board shows no filenames, so attributing that row to `h33-2-b2` is NOT
confirmed). The brief's "top is 0.3195" is rank 8 (IR-H84-002).

## 7 · Ranked next hypotheses (none validated; none may take a slot before its own holdout)

| rank | hypothesis | expected holdout effect | cost | note |
|---|---|---|---|---|
| 1 | **`B_DVA2` pre-registered fresh as primary**, emitted with a quota placement against the **full-census** informative supports (not only the 13 scored-only files) | ≈ the `B_DVA2` row above (+0.018 over `single_B` in this run); the open question is lane feasibility, not DTI | low (≈45 min, reuses H84 channels) | the only way the repository's best holdout arm can ever become promotable; IR-H84-001 shows the scored-only quota is not enough |
| 2 | Budget/ring sweep on the `B_DVA2` field (25,517–60,069 px; ring 200–300 m) on the same instrument | knowledge/49 shows that the stopping point, not the detector, set 0.2778 | low | tests the metric's marginal rule on a better field |
| 3 | HVA/DVA-2 on the GeoDAWN external layers (`data/external/geodawn_*`) | unknown | low | H84 rank 3, deferred |
| 4 | Seismicity-only View A vs View-B abstention (H74S-B) | low (View A insufficient 8×) | medium | |
| 5 | Drainage-deflection corridors from the 1 m DEM | possibly high | high, **BLOCKED here** | official free sources: USGS 3DEP <https://www.usgs.gov/3d-elevation-program>, and the tile list on the competition data page <https://www.drivendata.org/competitions/306/competition-doe-gems/data/>; neither is reachable from this sandbox |

## 8 · Limitations

* One experiment of the three allowed; two hours of budget. The 3 px lane rule cannot be passed by any
  37,654-dot set against universal-coverage probes, and H84 adds that it is also failed against dense
  (30–90% coverage) informative priors.
* `B_DVA2` drifted 3.6e−3 from its committed value (IR-H84-005); part of that drift is run-to-run
  (`single_B` fold AUCs also move by up to 3e−3). Per-channel array digests are now stored so future drift can
  be attributed.
* IR-H84-003: channel files were torn after verified writes on two builds; the root cause is not identified.
  Every reported number comes from the third, fully audited build, read from verified in-RAM copies.
* Negatives are catalogue-zero proxies; the holdout is conditional on the catalogue; no organiser
  confirmation of any number; no DrivenData credentials (the repository has never uploaded).
