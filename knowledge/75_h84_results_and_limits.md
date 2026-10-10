# 75 · H84 results and limits (2026-10-10)

Preregistered in [`74_hypotheses_H84_preregistered.md`](74_hypotheses_H84_preregistered.md)
(SHA-256 `b7da44db742c545511738a091b31d747dcf9c3de42dc4994005ba3f51bf34b17`, frozen before any fit, canary, holdout or placement
read; amendment 74a corrected only a channel count, before any fit). Receipts:
`evidence/h84_channels.json`, `evidence/h84_fit.json`, `evidence/h84_holdout.json`,
`evidence/h84_independence.json`, `evidence/h84_build_placement.json`,
`evidence/h84_lane.json`, `evidence/h84_build.json`, `evidence/h84_run_card.json`.

**Verdict: NEGATIVE — research artefact, do not upload.
Slots used 0. Experiments used 1 of 3.**

## 1. The one-sentence result

The primary arm did not beat the single-view control with a paired 95% CI entirely above zero, so the frozen promotion rule does not fire.

## 2. HOLDOUT-DTI — the only score this repository can compute for itself

Evaluator `gems52-pooled-hide-v1` · 53,186 withheld positive pixels ·
9,400 dots per fold per arm · k(d) = max(1 − d/R, 0), R = 300 m = 3 px ·
α 0.2, β 0.8 · 1,000 paired physical-block bootstrap draws (block side 200 px).

| arm | pooled HOLDOUT-DTI | 95 % CI | role |
|---|---|---|---|
| `single_A` | 0.078181 | [0.063473, 0.094017] |  |
| `single_B` | 0.173444 | [0.152576, 0.194991] | control |
| `B_DVA3c` | 0.169532 | [0.152274, 0.188307] |  |
| `B_DVA3` | 0.160157 | [0.142561, 0.179115] |  |
| `B_CSA` | 0.169247 | [0.150782, 0.188387] | primary |
| `random` | 0.079908 | [0.070672, 0.089335] |  |

Paired differences (primary − arm):

| comparison | Δ | 95 % CI | reading |
|---|---|---|---|
| `B_CSA − single_A` | 0.091066 | [0.073786, 0.108760] | above zero |
| `B_CSA − single_B` | -0.004197 | [-0.016143, 0.008684] | straddles zero |
| `B_CSA − B_DVA3c` | -0.000286 | [-0.007287, 0.007428] | straddles zero |
| `B_CSA − B_DVA3` | 0.009090 | [0.002176, 0.015869] | above zero |
| `B_CSA − random` | 0.089338 | [0.073486, 0.106633] | above zero |

`single_B` control: measured 0.173444 against committed 0.174517
(|Δ| 1.07e-03, tolerance 0.001) → FAIL.

**These are holdout numbers, not board forecasts.** In this repository the hide-and-recover
instrument does not rank leaderboard performance (measured Spearman −0.10 against owner-reported
board scores over R4, `knowledge/10` §5).

## 3. The lane's premise tests

| test | measurement | bar | verdict |
|---|---|---|---|
| leakage canary (max direction-insensitive single-channel AUC, 84 channels) | 0.622041 | 0.9 | clean |
| View A sufficiency (mean / min-fold out-of-quadrant AUC) | 0.5315 / 0.4556 | 0.60 / 0.55 | FAIL — standing negative |
| View independence (max |ρ| over spatial blocks) | 0.1370681276676306 | 0.6 | allow_exchange = True |

Independence thresholds were inherited verbatim from `registry/h74_preregistration.json`
(SHA-256 `44d8eeba549abccd…`); they were not re-tuned for H84.

## 4. Measured strike, from each fold's own visible catalogue

- fold 0: 169.73° compass, resultant length R 0.371, axial circular SD 80.70568614845944, corridor 241,871 px, derived from fold['visible'] only
- fold 1: 171.82° compass, resultant length R 0.367, axial circular SD 81.13860300784427, corridor 392,124 px, derived from fold['visible'] only
- fold 2: 166.72° compass, resultant length R 0.453, axial circular SD 72.11232754548921, corridor 434,494 px, derived from fold['visible'] only
- fold 3: 167.19° compass, resultant length R 0.378, axial circular SD 79.89815202055922, corridor 425,661 px, derived from fold['visible'] only

R is only 0.37–0.45, so the visible catalogue is genuinely multi-directional and a scalar regional
strike is a weak summary. That is exactly why the alignment channel was made **continuous** rather
than a single-strike comparison: a 4-valued categorical recoding (H82) cannot express "close to the
regional strike but not on it".

## 5. Uniqueness and the lane gate

- Full census (573 rasters): surface literal
  **PASS**, dots literal **DUPLICATE/STOP**
  (max ρ 0.0795, max near-3px share 1.0000),
  dots policy **DUPLICATE/STOP**.
- Restricted scored-only registry (13 rasters): surface
  literal **PASS**, dots literal
  **DUPLICATE/STOP** (max ρ 0.0385, max near
  1.0000), dots policy **PASS**.
- Quota placement against the restricted informative supports:
  37,654 dots, worst share
  0.5829.
- Doctrine: a restricted or policy PASS never waives a literal full-census DUPLICATE/STOP.

## 6. Not the union of the two views

| comparison | shared px | Jaccard | identical |
|---|---|---|---|
| primary vs `max(pA,pB)` | 1,496 | 0.0203 | no |
| primary vs `single_A` | 665 | 0.0089 | no |
| primary vs `single_B` | 1,765 | 0.0240 | no |
| primary vs B-only-suppressed | 27,429 | 0.5729 | no |

Gate: **PASS**.

## 7. Placement and catalogue ring

37,654 dots from a 4,325,298-px pool (4,593,171 eligible); 200 m ring
excluded; minimum distance to a mapped trace 223.6 m, median
1389.2 m, 14.19% of dots inside the
metric's 300 m kernel. The B-only disagreement stratum was used as a **suppression** set:
643,861 px vetoed, leaving
3,681,437 px, of which the emission took
37,654.

## 8. Irregularity IR-H84-001

30 of 102 channel files failed `run_h82.Bank`'s byte-integrity guard after passing
`run_h82.save_verified`. `scripts/repair_h84_channels.py` recomputed them from the pinned rasters
with the same arithmetic and a digest-stability check, then re-hashed the whole bank and re-verified
it. The mechanism is the environment-level torn write already recorded as IR-H82-002; it is
**not** resolved at the repository level, and any future channel build must run the repair before
fitting.

## 9. Limits

- No organizer receipt exists for any file here; every score quoted from the brief or a sibling site
  is OWNER-REPORTED/PUBLIC, never ORGANIZER-CONFIRMED.
- The holdout instrument hides catalogue faults while the competition scores faults the catalogue
  lacks; SGMC is ~95 % disjoint from `labels.tif`. The mismatch is the likeliest cause of the
  measured Spearman −0.10 between holdout DTI and board score.
- The 1 m DEM tiles behind the LiDAR scarp layer are not obtainable from this sandbox
  (egress limited to github/npm/pypi), so no new native-resolution scarp reduction is possible here.
- Pseudo-label exchange is still not run: View-A sufficiency has now failed eight consecutive times.
