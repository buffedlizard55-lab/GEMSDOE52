# 42 · H65 results, official verification, and the 0.2778 answer (2026-10-09)

Status: H65 NEGATIVE, research-only. No raster built. DO NOT UPLOAD. Slots used: 0. Experiments used: 1 of 3.
Pre-registration: `knowledge/41_hypotheses_H65_preregistered.md`, sha256 `7ae7cd9119c8b86d8b525519819e1120c71355bd949b7a164bc7c8b12e391afc`, pinned in `registry/h65_preregistration.json` before any fit.
Run card: `evidence/h65_run_card.json`. Receipts: `evidence/h65_*.json`. Round page: `docs/h65.html`.

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
- Control (pre-registered): single_B_hard vs H61 committed 0.174517: |Δ| = 5.4e-5 in the final run (tolerance 0.001): PASS. The first run gave |Δ| = 2.9e-7; the difference is an open reproducibility item (IR-H65-006).

**Why the view-A count matters:** this is the fourth View-A sufficiency failure with the same learner: H61 0.5163, H63 0.5362 (step view), H64 0.5230, H65 0.5299 (halo targets). AGENTS.md says not to propose a third View-A parameterisation without new evidence. H65 changed the targets, not the View-A parameterisation, and it failed the same screen.

**Reading:** halo targets moved the single-view holdout by +0.002, which the interval does not separate from zero. On this proxy, the 0–300 m partial-credit ring is not what limits View B. The disagreement arm stays below random, as it did in H60D, H62-buriedcorr, H63 and H64.

## 3. Official facts, verified this session (ORGANIZER-CONFIRMED unless stated)

- **Metric and format, DrivenData problem page 967** (fetched 2026-10-09). Distance-weighted Tversky: TP_w = Σ_g max_{x: d(x,g)≤R} p(x)k(d(x,g)); FP_w = Σ_{x: p(x)>0} p(x)[1 − max_g k(d(x,g))]; FN_w = Σ_g [1 − max_x p(x)k(d(x,g))]; DTI = TP_w / (TP_w + α·FP_w + β·FN_w + ε); α = 0.2, β = 0.8; kernel k(d) = max(1 − d/R, 0), R = 300 m. The page's own worked example gives TP 3.00, FP 1.89, FN 2.00 → 3/(3 + 0.2·1.89 + 0.8·2.00) = 3/4.978 = 0.60 (checked: 0.6027). Format: single layer float32, values in [0, 1], EPSG:32611, 100 m, same bounds, null or NaN outside. The page also says that "portions of the existing fault data may be misaligned from the true location of the surface fault".
- **Masking, forum topic 11516** (community.drivendata.org, fetched 2026-10-09; DrivenData Staff, chrisk-dd):
  - 16 Sep: "Pixels corresponding to known USGS/INGENIOUS faults are masked / excluded from evaluation, so they do not count towards penalty terms." Re-evaluation also masks them.
  - 21 Sep: "The mask is indeed pixel-exact - it is identical to the provided set of training fault labels." "…the buffer does not apply to known faults." "A new-fault ground truth pixel can indeed lie within 300m of a known fault trace. Such pixels would constitute corrections or modifications to existing fault traces. Identifying these corrections is one outcome we are aiming for as part of this competition."
  - The repo's earlier "staff masking" claim is therefore now verified from the primary text. The sentence about corrections is also verified, which is the basis for the R5-H1 rationale.
- **Leaderboard** (live page, fetched 2026-10-09; receipt `docs/data/leaderboard_snapshot_2026-10-09.json`): #1 xiaofanhu **0.3774** (13 submissions); #7 DARD **0.3195**; #15 extradr19 **0.2778** (13 submissions). The repo snapshot in `knowledge/39` lists extradr19 at rank 13 (IR-H65-003).
- **NLR official rules** (`docs.nlr.gov/docs/fy26osti/96647.pdf`, read in an earlier session): three submissions per week; one final submission is selected before the deadline; Appendix A requires a narrative disclosure of generative-AI use.
- **Reference solution** (`drivendataorg/gems-prize-reference-solution`, notebook read from `work/official/`): the output array is `np.zeros(...)` (float64) and is written with `dtype=y_final.dtype`; the page requires float32 (IR-H65-004).

## 4. The 0.2778 question

**Question:** why did `h33-2-b2` (GEMSDOE32, owner-reported 0.2778) score highest, and can a submission beat 0.2778 or 0.3195?

**Premise corrections.** (a) The top of the public board is 0.3774, not 0.3195; 0.3195 is DARD at rank 7. (b) 0.2778 is OWNER-REPORTED for `h33-2-b2`; the public board also shows 0.2778 for `extradr19` at rank 15, and the board does not identify files, so it confirms neither attribution. (c) GEMSDOE32's own page states that no organiser score exists for its artefacts (`knowledge/27`, IR-H62-009).

**What the bytes show (BYTES-VERIFIED, `data/reference/h33-2-b2-zeros.tif`, `data/scored/gems24-…-d2-8-…nan.tif`, `data/labels.tif`):**
- `h33-2-b2` has 37,654 positive pixels and is a strict subset of its parent `gems24-…-d2-8` (44,090 positive pixels). 6,436 pixels were removed and none were added.
- The removed pixels lie 100 m to 200 m (inclusive) from a mapped catalogue pixel (minimum 100.0 m, maximum 200.0 m). The nearest kept pixel is 223.6 m from the catalogue, and no kept pixel is within 200 m.

**Metric identities used (from the official formulas).** FN_w = |G| − TP_w exactly. With S = Σp and M = Σp·max_g k, FP_w = S − M. So DTI = TP / (0.2·TP + 0.2·(S − M) + 0.8·|G|). Under the sparse approximation M ≈ TP: DTI ≈ TP / (0.2·S + 0.8·|G|).

**Marginal rule (corrects IR-H65-002).** Adding one unit-probability pixel of kernel credit c to an uncovered truth pixel changes the denominator by α = 0.2 and the numerator by c, so DTI rises iff **c > α·DTI**. The repo's `metric.credit_bar` and `tests/test_metric.py` use this form. The prose form α·DTI/(1 − α·DTI) in `knowledge/01` and `05` is wrong. Checked on the repo metric: baseline DTI 0.277778, a dot with credit 0.0572 raises it to 0.278208 (bar 0.0556: passes); at baseline 0.294118 the same dot lowers it (bar 0.0588: fails). The prose form would predict the wrong sign at 0.2778.

**What the owner pair implies (sparse approximation, owner-reported scores; computed):**
- If the removed ring carried **zero** credit, the 0.2600 → 0.2778 change needs |G| = 14,089 px. That is above the top of the repo's identified |G| interval, [5,949, 12,512] px (IR-H61-001, IR-H62-005).
- Within the identified interval, the owner pair needs the removed ring to have carried about **0.5% to 3.3%** of the parent's TP credit (3.3% at |G| = 5,949; 1.3% at 10,000; 0.5% at 12,512).
- So the explanation "precision: pruning zero-credit mass" is approximately right: the ring carried almost no credit, but not provably zero. Our previous "zero credit" wording (`knowledge/27`) overstated it. Under the official metric the ring's credit depends on new-fault labels within 300 m, which staff say can exist (IR-H65-007).

**Can a submission beat 0.2778 or 0.3195?** On today's board, a score above 0.2778 would place a submission at rank 15 or better, and a score above 0.3195 at rank 7 or better. Our holdout numbers (0.17 to 0.18 for the best single view) are HOLDOUT-DTI on a catalogue proxy; they are **not** on the board's scale and no conversion is claimed. No candidate in this repo passes the gates, so no slot is spent. Whether any file can beat 0.2778 is unknown; there is no organiser evidence for this repo's files.

## 5. Candidate hypotheses (ranked), and what each needs

Full list: `knowledge/33_hypotheses_R5.md` (R5-H1…H6) and `knowledge/39_hypotheses_H64_preregistered.md` (H-1…H-5). Summary for this round:

1. **R5-H1, trace-correction corridor** (rank 1 in `knowledge/33`). The organiser's statement (16 and 21 Sep) confirms the population: new-fault pixels can lie within 300 m of known traces. It **cannot be validated on our holdout**, because holdout truth is the catalogue and does not contain corrections. A valid test needs an independent corrected-trace release. Not located in this session. The obtainability of candidate sources was not verified (USGS and GDAWN hosts are unreachable from the sandbox's bash; `fetch_page` was not tested on a specific corrected-trace release).
2. **H65, metric-kernel halo targets** (tested this round): negative (section 2).
3. **H-3, hot-spring alignment** (not implemented): GDR wellspring CSV is in hand (`data/external/gdr_wellspring_in_footprint.csv`); `dist_known_fault_px` must not be used.
4. **H-4, Blakely–Simpson up-continued TMI** (low): magnetic transforms were killed at 300 m (`knowledge/03`, N-6).
5. **H-5, ComCat** (blocked): the sandbox returns counts only.

## 6. Limitations and what is still needed

- The holdout cannot score the correction population. No result here speaks to R5-H1.
- S1 failed, so the co-training arm had no exchange in H65. The disagreement result is therefore a pre-exchange result plus an unchanged post-arm.
- The control's fold-0 predictions are not bit-reproducible across two runs of the same receipts (IR-H65-006); the verdict does not depend on it.
- Owner-reported scores are not organiser-verified; the board does not identify files; the public score for `extradr19` is not linked to any file.
- No lane check, validator output or raster exists for H65: nothing from this round is a submission candidate.
- Access needed for further work: an independent corrected-fault release (free, official, obtainability to be verified), and a re-run of the feature store and control with pinned thread counts.

## 7. Reproduce

```
.venv/bin/python scripts/run_h65.py canary      # ~90 s
.venv/bin/python scripts/run_h65.py fit         # ~12 min (soft fits), then `control` (~5 min)
.venv/bin/python scripts/run_h65.py sufficiency
.venv/bin/python scripts/run_h65.py exchange
.venv/bin/python scripts/run_h65.py holdout     # ~90 s
.venv/bin/python scripts/run_h65.py verdict
.venv/bin/python scripts/publish_h65_site.py
```
Tests: `tests/test_h65.py` (external guard, default hook identity, halo invariants, prereg hash, acceptance bar, H64 defaults) and `tests/test_metric.py::test_credit_bar_is_the_exact_marginal_condition`.
