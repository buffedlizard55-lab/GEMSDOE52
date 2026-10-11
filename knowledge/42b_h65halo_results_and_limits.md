# 42 · H65halo — historical halo-target analysis and official verification

> **Current correction (2026-10-10):** the public 0.2778 row is a time-stamped team-level observation, not a file receipt; the latest saved 2026-10-09 20:18 UTC read places it at rank 17 (public top 0.3774). The owner-reported file pairing is unverified. The local 0.2600/0.2778-labelled subset relation does not explain a score change, and removed cells are not known to be zero-credit: DrivenData staff says new-fault truth may occur within 300 m of known traces. Use [`knowledge/49`](49_why_02778_phd_answer.md); equations below are historical conditional sensitivity only.

Status: H65 NEGATIVE, research-only. No raster built. DO NOT UPLOAD. Slots used: 0. Experiments used: 1 of 3.
Pre-registration: `knowledge/41b_hypotheses_H65halo_preregistered.md`, sha256 `7ae7cd9119c8b86d8b525519819e1120c71355bd949b7a164bc7c8b12e391afc`, pinned in `registry/h65halo_preregistration.json` before any fit.
Run card: `evidence/h65halo_run_card.json`. Receipts: `evidence/h65halo_*.json`. Round page: `docs/h65halo.html`.

Evidence classes used below: **HOLDOUT-DTI** (our catalogue-truth proxy, evaluator `gems52-pooled-hide-v1`); **ORGANIZER-CONFIRMED** (quoted from an official page or staff post, with URL and date); **OWNER-REPORTED** (other participants' claimed scores, never organiser-verified); **BYTES-VERIFIED** (checked on pixels in this checkout).

## 1. What H65 changed and what it measured

One change, made in the shared template's sampler hook (`run_h61.sample_for_fit`): the H61 hard-label sample is kept draw for draw, and a halo of 30,000 pixels per fold at 0 < d < 300 m from the visible catalogue is added twice, with weights t and 1 − t, where t = 1 − d/300 m (the official triangular kernel). Learners, folds, budget, placement and evaluator are H61's. The dry run checked the hard part against H61's draw and checked that no halo pixel is hidden truth.

## 2. Results (HOLDOUT-DTI, 53,186 withheld positives, 153 clusters, 1,000 paired bootstrap draws)

| Arm | HOLDOUT-DTI | 95% CI |
|---|---|---|
| single_B, halo soft targets (H65 candidate control) | 0.176651 | [0.155476, 0.197373] |
| single_B_hard (H61 targets, re-fit this round) | 0.174571 | [0.152313, 0.196302] |
| union_max (pre-exchange) | 0.157096 | [0.136519, 0.178756] |
| single_A, halo soft targets | 0.075636 | [0.058320, 0.093568] |
| random (same domain and budget) | 0.080426 | [0.070223, 0.090973] |
| disagreement_post (= pre; S1 failed, exchange skipped) | 0.036386 | [0.024983, 0.049797] |

- Primary test, single_B_soft − single_B_hard: **+0.002079, CI [−0.001088, +0.005076]**. The CI includes zero, so the mechanism is **not confirmed**.
- Co-training candidate minus single_B_soft: **−0.140264, CI [−0.162998, −0.118399]**. The candidate is far below the single-view control and is not eligible.
- S1 View-A sufficiency (out-of-quadrant AUC, bar: mean ≥ 0.60, every fold ≥ 0.55): folds 0.5137, 0.6006, 0.4753, 0.5301; **mean 0.5299, min 0.4753 → FAIL**. Exchange therefore skipped (post := pre).
- Leakage canary (single-feature AUC, alarm 0.90): max 0.6687, no alarm.
- Control (pre-registered): single_B_hard vs H61 committed 0.174517: |Δ| = 5.4e-5 in the final run (tolerance 0.001): PASS. The first run gave |Δ| = 2.9e-7; the difference is an open reproducibility item (IR-H65halo-006).

**Why the view-A count matters:** this is the fourth View-A sufficiency failure with the same learner: H61 0.5163, H63 0.5362 (step view), H64 0.5230, H65 0.5299 (halo targets). AGENTS.md says not to propose a third View-A parameterisation without new evidence. H65 changed the targets, not the View-A parameterisation, and it failed the same screen.

**Reading:** halo targets moved the single-view holdout by +0.002, which the interval does not separate from zero. On this proxy, the 0–300 m partial-credit ring is not what limits View B. The disagreement arm stays below random, as it did in H60D, H62-buriedcorr, H63 and H64.

## 3. Official facts, verified this session (ORGANIZER-CONFIRMED unless stated)

- **Metric and format, DrivenData problem page 967** (fetched 2026-10-09). Distance-weighted Tversky: TP_w = Σ_g max_{x: d(x,g)≤R} p(x)k(d(x,g)); FP_w = Σ_{x: p(x)>0} p(x)[1 − max_g k(d(x,g))]; FN_w = Σ_g [1 − max_x p(x)k(d(x,g))]; DTI = TP_w / (TP_w + α·FP_w + β·FN_w + ε); α = 0.2, β = 0.8; kernel k(d) = max(1 − d/R, 0), R = 300 m. The page's own worked example gives TP 3.00, FP 1.89, FN 2.00 → 3/(3 + 0.2·1.89 + 0.8·2.00) = 3/4.978 = 0.60 (checked: 0.6027). Format: single layer float32, values in [0, 1], EPSG:32611, 100 m, same bounds, null or NaN outside. The page also says that "portions of the existing fault data may be misaligned from the true location of the surface fault".
- **Masking, forum topic 11516** (community.drivendata.org, fetched 2026-10-09; DrivenData Staff, chrisk-dd):
  - 16 Sep: "Pixels corresponding to known USGS/INGENIOUS faults are masked / excluded from evaluation, so they do not count towards penalty terms." Re-evaluation also masks them.
  - 21 Sep: "The mask is indeed pixel-exact - it is identical to the provided set of training fault labels." "…the buffer does not apply to known faults." "A new-fault ground truth pixel can indeed lie within 300m of a known fault trace. Such pixels would constitute corrections or modifications to existing fault traces. Identifying these corrections is one outcome we are aiming for as part of this competition."
  - The repo's earlier "staff masking" claim is therefore now verified from the primary text. The sentence about corrections is also verified, which is the basis for the R5-H1 rationale.
- **Leaderboard — PUBLIC-LEADERBOARD observations, not ORGANIZER-CONFIRMED.** An earlier 2026-10-09 page read put extradr19 at #15 and the 2026-10-08 snapshot listed #13. The later saved 2026-10-09 20:18 UTC observation places #1 xiaofanhu **0.3774**, #7 DARD **0.3195**, and #17 extradr19 **0.2778**. None provides a filename/hash receipt; see `evidence/leaderboard_observation_2026-10-09T201800Z.json` (IR-H65halo-003).
- **NLR official rules** (`docs.nlr.gov/docs/fy26osti/96647.pdf`, fetched and checked 2026-10-09): §3.2 'multiple submissions, subject to the limits specified on the competition website (three submissions per week)'; §3.2 requires the narrative to indicate 'the extent to which, if any, you used generative AI technology'; §1.1 'Participants will submit a single entry'; §1.3 eligibility (individuals: U.S. citizen or permanent resident). §2 gives a third wording of the label source (see IR-H65halo-008).
- **Reference solution** (`drivendataorg/gems-prize-reference-solution`, notebook read from `work/official/`): the output array is `np.zeros(...)` (float64) and is written with `dtype=y_final.dtype`; the page requires float32 (IR-H65halo-004).

## 4. The 0.2778 question

**Question:** why did `h33-2-b2` (GEMSDOE32, owner-reported 0.2778) score highest, and can a submission beat 0.2778 or 0.3195?

**Evidence classes.** (a) The saved public-board observation at 2026-10-09 20:18 UTC shows top 0.3774 and DARD 0.3195 at rank 7; extradr19's 0.2778 row is rank 17 in that observation. (b) The association between 0.2778 and `h33-2-b2` is OWNER-REPORTED, not organizer-confirmed; the board has no file identifier or hash. (c) No organizer receipt authenticating a repository TIFF and score has been found.

**What the bytes show (BYTES-VERIFIED, `data/reference/h33-2-b2-zeros.tif`, `data/scored/gems24-…-d2-8-…nan.tif`, `data/labels.tif`):**
- `h33-2-b2` has 37,654 positive pixels and is a strict subset of its parent `gems24-…-d2-8` (44,090 positive pixels). 6,436 pixels were removed and none were added.
- The removed pixels lie 100 m to 200 m (inclusive) from a mapped catalogue pixel (minimum 100.0 m, maximum 200.0 m). The nearest kept pixel is 223.6 m from the catalogue, and no kept pixel is within 200 m.

**Metric identities used (from the official formulas).** FN_w = |G| − TP_w exactly. With S = Σp and M = Σp·max_g k, FP_w = S − M. So DTI = TP / (0.2·TP + 0.2·(S − M) + 0.8·|G|). Under the sparse approximation M ≈ TP: DTI ≈ TP / (0.2·S + 0.8·|G|).

**Marginal rule (corrects IR-H65halo-002).** Adding one unit-probability pixel of kernel credit c to an uncovered truth pixel changes the denominator by α = 0.2 and the numerator by c, so DTI rises iff **c > α·DTI**. The repo's `metric.credit_bar` and `tests/test_metric.py` use this form. The prose form α·DTI/(1 − α·DTI) in `knowledge/01` and `05` is wrong. Checked on the repo metric: baseline DTI 0.277778, a dot with credit 0.0572 raises it to 0.278208 (bar 0.0556: passes); at baseline 0.294118 the same dot lowers it (bar 0.0588: fails). The prose form would predict the wrong sign at 0.2778.

**Historical sensitivity algebra (not an explanation of an organizer score change):** under the sparse-mass approximation and assuming the owner-reported values correspond to these two rasters, one can calculate scenarios for different assumed credit on the removed pixels. The zero-credit case yields |G| = 14,089 px; other assumed credits yield different values. These are conditional computations, not measured hidden-truth credit, and they do not establish that precision pruning caused the public row to change. The official metric and staff clarification allow new-fault truth within 300 m, so the local removed-cell credit is unknown. The old statement that pruning zero-credit mass explains the 0.2600/0.2778 difference is withdrawn; see `knowledge/49` and `IR-R5-011`.

**Can a future public score beat 0.2778 or 0.3195?** This cannot be inferred from the internal holdout. H65's 0.17–0.18 readings are HOLDOUT-DTI on a catalogue proxy, not on the public-board scale; no conversion is claimed. No candidate in this repo passes the gates, no slot is spent, and no file-to-row organizer receipt is available. Whether any file could beat a public value is unknown.

## 5. Candidate hypotheses (ranked), and what each needs

Full list: `knowledge/33_hypotheses_R5.md` (R5-H1…H6) and `knowledge/39_hypotheses_H64_preregistered.md` (H-1…H-5). Summary for this round:

1. **R5-H1, trace-correction corridor** (rank 1 in `knowledge/33`). The organiser's statement (16 and 21 Sep) confirms the population: new-fault pixels can lie within 300 m of known traces. It **cannot be validated on our holdout**, because holdout truth is the catalogue and does not contain corrections. A valid test needs an independent corrected-trace release. Not located in this session. Source checked this round: the USGS Quaternary Fault and Fold Database page (`https://www.usgs.gov/programs/earthquake-hazards/faults`, fetched 2026-10-09) lists public-domain downloads (KML 13 MB, GIS ZIP 16 MB, from `earthquake.usgs.gov/static/lfs/nshm/qfaults/`). It is obtainable, but it is the same mapped-trace family as the catalogue, so it cannot supply independent corrections. The page also calls its traces 'simplified representations'. Candidate for an independent release: the state cooperators listed on that page (e.g. Nevada Bureau of Mines and Geology). Not yet checked for corrected traces. Bash egress to usgs.gov remains blocked; `fetch_page` works.
2. **H65, metric-kernel halo targets** (tested this round): negative (section 2).
3. **H-3, hot-spring alignment** (not implemented): GDR wellspring CSV is in hand (`data/external/gdr_wellspring_in_footprint.csv`); `dist_known_fault_px` must not be used.
4. **H-4, Blakely–Simpson up-continued TMI** (low): magnetic transforms were killed at 300 m (`knowledge/03`, N-6).
5. **H-5, ComCat** (blocked): the sandbox returns counts only.

## 6. Limitations and what is still needed

- The holdout cannot score the correction population. No result here speaks to R5-H1.
- S1 failed, so the co-training arm had no exchange in H65. The disagreement result is therefore a pre-exchange result plus an unchanged post-arm.
- The control's fold-0 predictions are not bit-reproducible across two runs of the same receipts (IR-H65halo-006); the verdict does not depend on it.
- Owner-reported scores are not organiser-verified; the board does not identify files; the public score for `extradr19` is not linked to any file.
- No lane check, validator output or raster exists for H65: nothing from this round is a submission candidate.
- Access needed for further work: an independent corrected-fault release (free, official, obtainability to be verified), and a re-run of the feature store and control with pinned thread counts.

## 7. Reproduce

```
.venv/bin/python scripts/run_h65halo.py canary      # ~90 s
.venv/bin/python scripts/run_h65halo.py fit         # ~12 min (soft fits), then `control` (~5 min)
.venv/bin/python scripts/run_h65halo.py sufficiency
.venv/bin/python scripts/run_h65halo.py exchange
.venv/bin/python scripts/run_h65halo.py holdout     # ~90 s
.venv/bin/python scripts/run_h65halo.py verdict
.venv/bin/python scripts/publish_h65halo_site.py
```
Tests: `tests/test_h65halo.py` (external guard, default hook identity, halo invariants, prereg hash, acceptance bar, H64 defaults) and `tests/test_metric.py::test_credit_bar_is_the_exact_marginal_condition`.
