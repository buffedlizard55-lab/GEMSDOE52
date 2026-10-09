# 39b · Amendment to H64 — control tolerance, measured before any H64 fit

**Dated 2026-10-09 (UTC), recorded before any H64 model is fitted.** This is an *amendment*, not an edit:
`knowledge/39_hypotheses_H64_preregistered.md` is unchanged and its SHA-256 still matches the registry.

**Why.** `knowledge/39` §4 said the single-view B control must reproduce the H61 `single_B` value
`0.174517` *exactly*. That rule was written before the H61 pipeline had been re-run on this machine.
It has now been re-run from the same restored bytes, the same seeds and the same code
(`scripts/run_h61.py all`, feature store rebuilt by `structural.build` + `gems52.external`):

| quantity | committed H61 receipt | reproduced on this machine | difference |
|---|---:|---:|---:|
| `single_A` HOLDOUT-DTI | 0.0719542277 | 0.0719542277 | 0.0 |
| `single_B` HOLDOUT-DTI | 0.1745172876 | 0.1745713589 | 5.41×10⁻⁵ |
| `single_B` 95% CI | [0.152316, 0.196299] | [0.152313, 0.196302] | ≤ 3×10⁻⁶ |
| independence max \|ρ\| | 0.1330652553 | 0.1336850745 | 6.2×10⁻⁴ |
| exchange pseudo pixels | 15,441 | 15,446 | +5 |
| canary (every feature, every fold) | identical | identical | 0 |

The canary is byte-identical, so the **feature stack is identical**. The movement is in the gradient-boosting
fit (`HistGradientBoostingClassifier` with OpenMP histogram reductions is not bit-stable across thread
schedules), which then propagates to the pseudo-label count and the independence statistic. Neither changes
any verdict in H61: the exchange still runs, the independence screen still passes at |ρ| ≤ 0.6, and the
H61 disagreement arms still sit far below `single_B`.

**Amended control rule (replaces the "exact" wording in `knowledge/39` §4 only).** The H64 control
`single_B` must reproduce the H61 committed value within **|Δ| ≤ 0.001** (about 18× the measured
nondeterminism). A larger gap stops the run and is reported as a pipeline defect. The committed H61
receipts are **not** altered by this; they remain the published H61 record.

**What is not changed.** The S1 threshold (mean ≥ 0.60, min fold ≥ 0.55), S2, the holdout evaluator, the six
arms, the budget and the verdict rule are all as pre-registered.

**Irregularity recorded.** `IR-H64-003`: H61 fit is not bit-reproducible across runs on this 2-CPU
sandbox; published H61 numbers are reproducible only to about 1e-4 in DTI.
