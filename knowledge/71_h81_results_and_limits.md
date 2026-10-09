# 69 · H81 round: reproduction of the H75 file, one experiment (H81-1), gates, irregularities (2026-10-09)

Preregistration: `knowledge/70_h81_preregistered.md` (SHA-256 pinned in `registry/h81_preregistration.json`, checked by
`scripts/run_h81.py` before it runs). Ranked candidates: `knowledge/69_h81_hypotheses_ranked.md`.
Run card: `evidence/h81_run_card.json`. Experiments used this round: **1 of 3** (H81-1). Slots used: **0**.
Reproduction runs of H75 are not counted as experiments.

## 1. Inputs and tests (MEASURED this session)
| Step | Result | Receipt |
|---|---|---|
| Competition inputs restored, SHA-256 pinned | 23/23 `ALL_VERIFIED=True`. The bytes come from the owner's sibling GitHub mirrors, **not** DrivenData (login-walled). Integrity-pinned, not organiser-authenticated (IR-H81-006) | `data/restore_receipt.json` (git-ignored) |
| Feature store built, then extended with the shared external layers | built (57 features); `python -m gems52.external` is a required step, missing from the README (IR-H81-008) | `work/r2/features` (git-ignored) |
| Prior-raster census fetched | 526 blobs fetched, 0 errors, 524 eligible file SHA-256 match the census | `work/h61/prior_fetch_receipt.json` (git-ignored) |
| Test suite | **450 passed, 2 skipped** (pinned `requirements-r2.txt` stack, Python 3.11) | `pytest` |
| Official rules re-read | one GeoTIFF per team; float32; values in [0,1]; "null or nan" outside bounds; 300 m triangular kernel; α 0.2, β 0.8 | <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/> (fetched 2026-10-09) |

## 2. H75 file: reproduced line by line from restored bytes
| Claim | Re-measured here | Verdict |
|---|---|---|
| SHA-256 `b97691584d514ab1925d9fff2b61c410be86bdc0bc8c844dfdaa6257a4ea7a16` (142,941 bytes) | identical in `submission/` and `docs/downloads/` | **reproduced** |
| float32, EPSG:32611, 3730×3292, transform = sample | True / True / True | **reproduced** |
| values exactly {0,1}; 37,654 ones; 0 NaN inside the footprint | {0.0, 1.0}; 37,654; 0 | **reproduced** |
| placement regenerated from the pipeline equals the shipped file pixel for pixel | `np.array_equal` True, 37,654 dots | **reproduced** |
| Fold AUCs for single_B / B_DVA | fold 0 0.6625 / 0.6798; fold 1 0.7684 / 0.7818; fold 2 0.6112 / 0.6445 — identical to the H75 receipt | **reproduced** |
| Holdout single_B | fresh process **0.174571** (H71 and H73 receipts 0.174571); the committed H75 receipt said 0.174517 | **corrected** (IR-H81-003) |
| Holdout B_DVA | 0.186352 [0.164675, 0.207868] (same in both runs) | **reproduced** |
| Paired B_DVA − single_B | corrected **+0.011781 [0.006700, 0.017313]** (committed: +0.011835 [0.006791, 0.017362]); the promotion rule still holds | **corrected** |
| Canary (12 DVA channels alone) | max AUC 0.623, no alarm | reproduced |
| Lane, surface (literal and policy) | literal PASS, max Spearman 0.4657; policy PASS | **reproduced** |
| Lane, final dots, literal | **DUPLICATE/STOP** (max 3 px near-dot share **1.000**) | **measured, fails** |
| Lane, final dots, policy | **DUPLICATE/STOP** (max 0.9220, 38 informative offenders of 552) | **reproduced, fails** |
| Uniqueness, canonical decoded pattern | unique vs 566 priors | reproduced |
| Uniqueness, support novelty (≥ 20 % required) | **novel_fraction 0.0 → gate FAILED**; `relation_to_union: subset-of-union` (every dot's support lies inside the union of the 566 priors) | **NEW MEASUREMENT: fails** (IR-H81-001) |

**The committed `evidence/h75_gates.json` already recorded `novel_fraction` 0.0 and `ok: False`** (565 priors at the time; the re-run uses 566 and gives the same verdict). **The H75 README's "uniqueness PASS" describes only the canonical decoded pattern.** The support-novelty gate
(`gems52.gates.uniqueness_report`, called by `scripts/h75_gates.py`) fails. The brief asks that the output not be merely the union of existing predictions;
on support it is. The file is research-only, and the verdict is changed in §5.

## 3. H81-1: DVA of band 18 added to View B — NEGATIVE
Same rows, learner, seed, folds and allowed masks as H75. single_B and B_DVA predictions reused from H75; B_DVA18 is the only fit.

| Arm | HOLDOUT-DTI (gems52-pooled-hide-v1, 53,186 withheld positives, 9,400 dots/fold) | 95 % CI |
|---|---:|---|
| single_B | 0.174571 | [0.152316, 0.196299] |
| B_DVA (H75) | 0.186352 | [0.164675, 0.207868] |
| **B_DVA18 (H81-1)** | **0.188333** | [0.167850, 0.209106] |
| random | 0.080426 | [0.070223, 0.090973] |

**Paired B_DVA18 − B_DVA: +0.001980, 95 % CI [−0.001462, +0.005216]** (evaluator's own paired block bootstrap, 153 clusters, 1,000 draws).
The preregistered promotion rule requires a CI lower bound > 0. **It is not met → NEGATIVE.** Canary max AUC 0.596 (no alarm).
Per-fold: B_DVA18 beat B_DVA in 4/4 folds, by +0.0004 to +0.0052 (fold 0 +0.0020, fold 1 +0.0004, fold 2 +0.0005, fold 3 +0.0052). The pooled CI still includes zero.

Label: HOLDOUT-DTI. Not ORGANIZER-CONFIRMED. No emission file was written and no placement was run, per the preregistration.

## 4. What this round says about the lane (the actual blocker)
The holdout is not what stops a submission. The lane is. Two independent readings of the H75 dots both fail (§2). A
holdout improvement of 0.002 would not change that. The next lever is the rule, not the ranker, and that is an owner
decision (H81-4 in `knowledge/67`).

## 5. Verdicts (plain language)
- **H75 file (`docs/downloads/h75-candidate.tif`):** DOWNLOAD — research copy only. **SUBMIT — NO.** It fails the lane gate (literal and policy) and the support-novelty gate (0.0 vs ≥ 0.20). Its format is valid. A competition submission would need an explicit owner override of two gates, and the support-novelty failure would still have to be accepted.
- **H81-1 (band 18):** NEGATIVE. No file. Nothing to download or submit.
- **Is there any file in this repo that passes every gate?** No. The H74 file passes the format gate and fails holdout and lane. H75 passes holdout and fails lane and support novelty. H72-v3 has a holdout below random.

## 6. Irregularities (all logged in `registry/irregularities.json`, IR-H81-001 … -011)
See the registry for the full text. The ones that change a decision are IR-H81-001 (support novelty), IR-H81-003 (in-process
holdout artefact and corrected paired number), and IR-H81-006 (the competition rasters come from owner mirrors, not the portal).

## 7. Next steps (ranked; none run)
1. Owner decision on the lane rule (H81-4). Without it no file can be submitted, whatever its holdout.
2. H81-2 (antithetic basement step, band 15) with its own preregistration and one experiment.
3. H81-3 magnetic-gradient DVA, but only after a flight-line artefact check (the named mimic).
4. Split the fit and holdout stages into separate processes for every run (IR-H81-003 fix), and add `gems52.external` and the census fetch to the README reproduce steps.
