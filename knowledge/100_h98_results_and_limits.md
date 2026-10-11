# 84 · H98 results and limits (2026-10-10)

Frozen in [`registry/h98_preregistration.json`](../registry/h98_preregistration.json) before any H98
fit; hypotheses in [`knowledge/83`](83_h98_hypotheses_preregistered.md); the prior belief that made this
arm worth testing is in [`knowledge/82`](82_h97_results_and_limits.md) §3.

**Slots used: 0. Uploads: 0. Artifacts built: 0.** Receipts: `evidence/h98_lane_precheck.json`,
`evidence/h98_holdout.json`.

## 1 · The lane gate ran first, as the protocol requires

`scripts/check_h98_lane.py` placed the 37,654-dot emanation and measured it against all 149 accessible
priors *before* any validation. Decision: **proceed-to-validation**. Literal (every prior incl. probes)
`DUPLICATE/STOP` — one universal-coverage probe, `data/scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif`,
whose 3 px halo covers 99.90 % of the eligible area; policy (priors that localise something, 148 + 1
probe) `PASS`, max Spearman **0.01083**, max near-3 px **0.40535**; canonical pattern unique, novel
fraction 0.6596, relation `strictly-novel-and-selective`.

## 2 · The validation (HOLDOUT-DTI)

Instrument `gems52-pooled-hide-v1`: label-blind quadrants, buffer 80 px, whole catalogue components
hidden, 200 m collar from the VISIBLE catalogue only, 9,400 dots per fold, `spacing_select` at 3 px,
60,894 withheld positive pixels, 1,000 paired 20 km block-bootstrap draws.

| arm | pooled DTI | 95 % CI |
|---|---:|---|
| `h98_bonly` (primary: B confident, A abstains) | **0.058435** | [0.043370, 0.075525] |
| `single_B` (the surface family alone) | 0.054606 | [0.041360, 0.069515] |
| `random` (same allowed set, same budget) | **0.077320** | [0.068767, 0.087786] |

Paired `h98_bonly` − `random` = **−0.018885** [−0.030936, −0.007620] — the whole interval is below zero.
The frozen promotion rule (CI lower > 0 ∧ lane PASS ∧ canonical unique) fails on its first clause, so
**verdict: negative**, and `scripts/build_h98_submission.py` correctly refuses to emit a file.

Leakage canary: max per-arm AUC `h98_bonly` 0.5808, `single_B` 0.5888, `random` 0.5023 against an alarm
threshold of 0.90 → no alarm. Per-fold DTIs are in the receipt (fold 2 is the only fold where the primary
beats the control; folds 0, 1 and 3 are below it).

## 3 · The finding: the two truth populations disagree in sign

The same arm, the same code path, the same 3 px placement:

| instrument | truth population | arm − matched control |
|---|---|---:|
| `gems52-offcatalogue-prevalence-matched-v1` (H97 screening) | SGMC faults ≥300 m from the competition catalogue, thinned to 14,089 px | **+0.057555** |
| `gems52-pooled-hide-v1` (this round) | the competition catalogue itself, hidden a quadrant at a time | **−0.018885** |

Both are measured; both are receipts; neither is the leaderboard. The honest reading is that this arm is
an *artefact of one truth population*, not a discovery. It is the sharpest instance so far of the
repository's standing result that in this problem the instrument's truth population moves the number more
than the method does (`knowledge/76` §6), and it is why the round ends without a file.

## 4 · Limits

1. Two instruments, two signs — the repository still has no instrument whose ordering matches the board
   (measured rank correlation ≈ 0 with the twelve restored owner-reported files).
2. The screen that selected this arm is a single-instrument, single-budget measurement. It was never
   promotable by itself, and this round is the reason that rule exists.
3. The 13gems lattice is a real prior on the board, and the literal lane rule cannot be satisfied against
   a raster that covers the domain: the literal-vs-policy distinction is inherited from the H61 template
   repair and is reported verbatim in every receipt rather than quietly dropped.
