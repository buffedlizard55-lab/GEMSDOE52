# 44 · H66 results and limits (2026-10-09)

Pre-registration: [`knowledge/43_hypotheses_H66_preregistered.md`](43_hypotheses_H66_preregistered.md) (SHA-256 `e21187387a3b646e…`, frozen before any fit).
Runner: `scripts/run_h66.py`. Publisher: `scripts/publish_h66_site.py`. Run card: `evidence/h66_run_card.json`.

## Labels used below

`PREMISE-AUC` (out-of-quadrant AUC, not a score) · `HOLDOUT-DTI` (simulated hide-and-recover, `gems52-pooled-hide-v1`) ·
`LANE` (shared gate `gems52.gates.lane_report`) · `FORMAT` (local validator; not organiser acceptance) ·
`PUBLIC BOARD` (owner-reported, dated) · `UNVERIFIED` (not checked from a primary source).

## What was run

| Stage | Result | Receipt |
|---|---|---|
| Canary (alarm > 0.90), all 73 features | max single-feature AUC 0.6687, no alarm, no features dropped | `evidence/h66_canary.json` |
| Fit, View A_local (14 channels, logistic) and View B (H61 learner) | A_local mean **0.5454**, min **0.5246** → **FAIL** (gate: mean ≥ 0.60 and min ≥ 0.55). View B mean 0.6843 | `evidence/h66_fit_checkpoint.json` |
| Non-gating diagnostic: gradient boosting on the same 14 channels | mean 0.5392, min 0.5108 | `evidence/h66_diagnostic_hgb_local.json` |
| Exchange (one round, as H61) | allowed; independence max \|ρ\| 0.1937 (threshold 0.6); 15,989 pseudo pixels | `evidence/h66_pseudo_exchange.json` |
| Holdout (53,186 withheld positives, 153 clusters, 1,000 draws, seed 520810) | see table below | `evidence/h66_holdout.json` |
| Emission (global budget 37,600; 3 px hard-core; > 200 m off catalogue) | 37,600 dots; re-derived from the frozen field, identical to the written TIF | `submission/gems52-h66-localA-cotrain-37600px.tif` |
| Format gate | PASS (single-band float32, EPSG:32611, grid identical, values exactly {0,1}, 0 NaN) | `evidence/h66_format_validator.json` |
| Lane gate, surface | literal PASS (max ρ 0.2141); policy PASS (max ρ 0.1764; 539 informative priors; 14 coverage probes excluded) | `evidence/h66_lane_surface.json` |
| Lane gate, dots | literal **DUPLICATE/STOP** (near-dot share 1.0 against coverage probes); policy **DUPLICATE/STOP** (near-dot share 0.8878 against a prior the H61 round also matched) | `evidence/h66_lane_dots.json` |
| Uniqueness audit (`scripts/audit_uniqueness.py`, census receipt as 3rd argument; 526-blob census, 0 errors; 536 priors after byte dedupe) | decoded-distinct from every prior (max Jaccard 0.035385 against `gems52-h63-stepview-cotrain-37600px.tif`); surface not duplicate (max ρ 0.0615); dots **DUPLICATE** (23 offenders) | `evidence/h66_uniqueness_audit.json` |

Holdout (HOLDOUT-DTI, 95% paired cluster bootstrap):

| Arm | DTI | 95% CI |
|---|---|---|
| single_A (H66-A, local View A) | 0.075641 | [0.060446, 0.091174] |
| **single_B (best comparable control)** | **0.174571** | [0.152313, 0.196302] |
| union_max | 0.153269 | [0.133574, 0.172795] |
| disagreement_pre | 0.043245 | [0.033079, 0.054845] |
| **disagreement_post (candidate)** | **0.039805** | [0.030131, 0.050345] |
| random | 0.080426 | [0.070223, 0.090973] |

Candidate minus single_B: −0.134766, 95% CI [−0.159731, −0.110876]. The candidate does not beat the control.

## Verdict

**NEGATIVE, research-only.** Premise FAIL; the holdout candidate is below the control; the dots lane is DUPLICATE/STOP. The file is
format-valid and decoded-distinct from every prior, so it may be downloaded for research. It is **not** a unique, lane-checked file,
and it is not submit-eligible. No weekly slot was used, nothing was uploaded, and no organiser acceptance is claimed.

Experiments used: 2 of 3 (E1 = canary + fit + premise; E2 = exchange + holdout + emission + gates). E3 was not authorised.

## Reproduction mismatch (IR-H66-010)

`single_B` in this run is 0.174571; H61's receipt is 0.174517. The difference is 5.4 × 10⁻⁵ and sits in fold 0 only. Folds 1–3 match
to seven decimals. The View B fold AUCs match H61 exactly, and the `random` arm matches exactly, so the evaluation machinery is identical.
The likely cause is a small difference in fold-0 predictions outside the AUC sample, but that is `UNVERIFIED`: the H61 feature store
is not in this sandbox. No verdict depends on it. The pre-registration says a mismatch is reported before other results are read; this
note does that, although the results were printed together during the run.

## Why 0.2778 (measured on bytes, not reported)

From `work/h66/champion_check.json` (restored bytes):

* The champion `h33-2-b2` (37,654 positive pixels, values {0,1}, no NaN) is a pixel-exact subset of the gems24 d2-8 raster (44,090
  positives; reported 0.2600). It adds zero pixels.
* The 6,436 removed pixels all lie 100–200 m from a mapped trace (min 100 m, median 100 m, max 200 m).
* The champion's nearest dot to the catalogue is 223.6 m away. Its nearest-neighbour spacing is near 3 px (median 3.00 px).
* Under `DTI = T / (0.2·(T+S−M) + 0.8·|G|)` (`src/gems52/metric.py`, identity (i)), the marginal condition is
  `c·(1−α·DTI) > α·DTI·f` (identity (ii)). For one uncovered truth pixel of kernel weight w (f = 1−w) this is **w > α·DTI = 0.0556** at
  DTI 0.2778, which the README's ≈0.055 states. The repository's `emit.accept_bar` gives α·DTI/(1−α·DTI) = **0.0588**, a stricter
  variant (IR-H66-002).
* Removing pixels raises the ratio when their expected credit is below the bar. That is consistent with the measured subset chain.
  It is an inference: the hidden truth is not available to measure the removed pixels' credit.

## Corrections made in this round

* Bar: the README's ≈0.055 is the metric's special case α·DTI = 0.0556, rounded. An earlier H66 draft replaced it with the repository's 0.0588 form and was wrong (IR-H66-002). The H65halo notes give the same special case.
* Metric denominator: `0.2·(T+S−M) + 0.8·|G|`; one README line had `0.8·(|G|−T)` and is corrected (IR-H66-003).
* Leaderboard top 0.3774 is from the dated snapshot (2026-10-08T21:40:41Z). The live page returned "Loading…" on 2026-10-09 (IR-H66-004).

## Organiser statements checked this round (DrivenData problem page, fetched 2026-10-09)

* Labels "are not complete and may even contain some inaccurate data" (supports the premise of catalogue-missing faults).
* Submission: a single float32 layer, values in [0,1], same bounds as training data, "data outside the bounds is null or nan"
  (IR-H66-009: the scored champion uses zeros).
* Sample: "a sample submission that predicts total fault absence" (IR-H66-001: the file has 60,988 ones, all on labelled faults).
* Scoring: a public and a private test split; competitors "must choose a single submission for scoring across both rounds" (IR-H66-007).

## Hypotheses (pre-registered in `knowledge/43` §1; none run)

H66-B survey-levelling stripe veto (precision; rank 2) · H66-C tilt-angle zero contours (carried from H65-B; rank 3) ·
H66-D mapping-coverage residual (observation process; rank 4). Euler deconvolution, QFaults priors, `C_*` cross features and gap
bridging are already in the repository and are not repeated.

## Limits

* The holdout is a simulator. R4 measured Spearman −0.10 against the owner-reported board, so holdout gains do not predict board gains.
* Public-board numbers are owner-reported and dated. The public split is not the final score.
* The dots lane gate is saturated by any 3 px hard-core emission against existing priors. The H61, H63 and H64 files show the same
  pattern. A future candidate needs a different emission rule, pre-registered before it is tried, to be lane-unique.
* The H66 file is research-only. Its only validation is the local format check and the lane and uniqueness receipts above.
* Input SHA pins (training features `4371c82e…`, labels `7ba308cc…`, sample `2176d08e…`) authenticate the mirror bytes only, not organiser authentication (`knowledge/36`).
* Public-board scores are owner-reported and dated; no score for this file exists, and nothing here is an organiser-confirmed result.

## Open items

* A lane-unique candidate. Not achieved in H61, H63, H64, H65 or H66.
* Legal review of the public GitHub mirrors (IR-H66-006).
* Organiser answers on the sample description and the outside-bounds convention (IR-H66-001, IR-H66-009); the rejected portal file for IR-H65-007.
* A browser re-read of the live leaderboard (IR-H66-004).
* Generative-AI disclosure in any submission narrative (IR-H66-008; text in `knowledge/43` §7).
* The `submission/gems52-r5-novel-…tif` file from another lane is outside this round and is not endorsed here.
