# 82 · H88 — results and limits (2026-10-10)

Preregistration: `knowledge/81_hypotheses_H88_preregistered.md` (SHA-256
`7f50e069e0a1594fb66bdcd9be075a0eda52e6d531fad12b4e6ed95a03de71f3`, pinned in
`registry/h88_preregistration.json`, verified at runner start-up). Runners:
`scripts/run_h61.py` (shared instrument, re-run) and `scripts/run_h88.py`.
**Verdict: NEGATIVE — DOWNLOAD YES (research), SUBMIT NO. Slots used: 0. Experiments: 3 of 3.**

Every number below is HOLDOUT-DTI (evaluator `gems52-pooled-hide-v1`, α 0.2, β 0.8, 300 m
triangular kernel, label-blind quadrant folds, 80 px buffer, visible catalogue masked, 53,186
withheld positive pixels, 9,400 dots/arm/fold, 3 px spacing, paired physical 20 km cluster
bootstrap, 1,000 draws, seed 61052) unless labelled otherwise. None is ORGANIZER-CONFIRMED.

## 1 · What was measured

| arm | HOLDOUT-DTI | 95% CI | per-fold DTI (f0..f3) |
|---|---:|---|---|
| **B_ABS** (view B + 4 ABS channels) | **0.177930** | [0.157748, 0.199356] | 0.1144 / 0.2556 / 0.1994 / 0.2386 |
| single_B (template control) | 0.174571 | [0.152313, 0.196302] | 0.1130 / 0.2576 / 0.1971 / 0.2223 |
| ABS_only | 0.091628 | [0.079232, 0.103846] | 0.0520 / 0.0965 / 0.1403 / 0.1525 |
| disagree_Aonly (A ≥ q0.90, B ∈ [q0.35, q0.65]) | 0.035301 | [0.027765, 0.044167] | stratum px 58,248 / 31,620 / 12,882 / 18,330 |
| random | 0.080426 | [0.070223, 0.090973] | — |
| paired B_ABS − single_B | **+0.003358** | **[−0.001668, +0.008780]** | B_ABS wins folds 0, 2, 3; loses fold 1 |
| paired B_ABS − random | +0.097504 | [+0.079466, +0.117028] | — |

Shared-instrument baselines (same re-run, `evidence/h61_holdout.json`): single_A 0.071954,
union_max 0.149009, disagreement_pre 0.033293, disagreement_post 0.030584.

* **Control reproduction:** single_B 0.174571 and random 0.080426 — both exact to 6 decimals
  against the committed references. Per-fold OOF AUCs identical to the H77cond receipts to 4 dp.
* **Leakage canary (brief rule 4):** per-fold max AUC of any ABS channel alone 0.524 / 0.561 /
  (folds 2–3 in `evidence/h88_fit.json`) — all far below the 0.90 alarm. **No alarm.**
* **Independence (brief rule):** block-level negative-error correlation max |ρ| = 0.1337 < 0.60
  (2,089 blocks) → exchange allowed and measured (one confident→abstain round per direction per
  fold; never shipped, N-1 settled).
* **OOF AUC:** B_ABS beats single_B in all four folds (e.g. fold 0 0.6703 vs 0.6625; fold 1
  0.7717 vs 0.7684). ABS_only is weak alone (0.53–0.58) — the channels are complementary, not
  sufficient.
* **A-only discovery stratum:** 121,080 px pooled; its holdout arm scores 0.0353, BELOW random —
  a ninth confirmation that the catalogue-confirmed hidden population is not resolved by View A
  confidence alone on this instrument. Every emitted A-only segment (15 segments intersecting the
  shipped dots) carries written geological reasoning in
  `docs/downloads/h88-a-only-reasoning.csv` (brief: Phase-2 reviewers).

## 2 · The promote rule and the verdict

Frozen rule (knowledge/81 §3): promote iff paired B_ABS − single_B CI lower bound > 0 AND
canaries pass AND independence passes AND union check passes AND lane gates pass.

* CI lower bound = −0.001668 ≤ 0 → **FAIL** (point estimate is positive; three of four folds
  positive; but the preregistered bar is the bar — no post-hoc relaxation).
* Canary PASS, independence PASS, not-merely-union PASS (Jaccard vs union_max 0.075, vs single_A
  0.006, vs single_B 0.115; bar 0.50).
* Lane: surface PASS (max Spearman 0.186, ≤ 0.90 everywhere). Dots: literal DUPLICATE/STOP —
  near-3px 1.0 vs the universal-coverage lattice probe (registry artefact, random scores ~1.0 too)
  AND policy near-3px **0.7275 > 0.70** vs `gems52-h83-offcatalogue-cotrain-37654px-e3`, which the
  random control (`evidence/h88_lane_control.json`: unspaced 0.201–0.205, spaced 0.2045) shows is
  REAL overlap, not a probe artefact. **Logged as duplicate per protocol rule 1; not waived.**

**Verdict: NEGATIVE.** File published as research:
`docs/downloads/gems52-h88-abs-cotrain-37654px-20261010T223629Z-zeros.tif`
(SHA-256 `b37c2dc8e5ad4bde121edb7ef21b4e05c2d9d2ceebfe8604180627866b726759`, 37,654 px {0,1},
all-finite zeros-outside container, min catalogue distance 223.6 m, format gate 0 problems,
decoded-pattern unique over 147 priors, novel fraction 0.230).

## 3 · What H88 learned (carried forward)

1. **Band-15 sign-asymmetric steps are the first new channel in this lane to raise View B's OOF
   AUC in all four folds** (+0.003–0.008) — and the first to raise pooled HOLDOUT-DTI over
   single_B (+0.0034), but the CI excludes a confident win. The direction is not dead; the signal
   is small at the catalogue target.
2. **The disagreement stratum itself is still anti-informative for catalogue faults** (0.035 vs
   0.080 random) — the A-only population is where mapped faults are NOT, which is exactly the
   point for an off-catalogue board but unprovable on this instrument (knowledge/76 §5).
3. **The denominator wall is now measured inside this repo's own registry:** any full-budget
   View-B-family emission overlaps ≥ 70 % (near-3px) with at least one dense prior. Shipping a
   37,654-dot surface-family file again requires either preregistered quota placement or a budget
   cut into the non-halo capacity (knowledge/65 §amendment-65b measured ≈ 9,500 such dots).
4. **Mass lever still unspent** (knowledge/76 §4): the champion is likely over-emitting 28–33 %.
   H88-MASS needs the prevalence-matched off-catalogue instrument first (knowledge/76 §6).

## 4 · Limits and irregularities of this round

* Per-fold DTI and block correlations jitter ≤ 1e−3 vs the committed H61 receipts on re-run in
  this sandbox (IR-H88-003); pooled controls reproduce exactly.
* The H83-E3 lane overlap (IR-H88-004) is against THIS repo's own research file; it is still a
  literal-rule duplicate and was logged, not argued away.
* `docs/index.html` was found with the pre-H87 archive lost (IR-H88-001); H88 restores a
  current-first page with the H87 page archived verbatim and the historical guardrail strings.
* H87's "PROMOTE" label was a build receipt, not a validation (IR-H88-002); the site now says so.
* One implementation bug found and fixed in `run_h88.py` during E2 (the random arm inherited the
  previous arm's allowed set; fixed before the valid run) and two runner bugs fixed before the
  first valid fit (grid-flat index double-mapping; H61-vs-H88 threshold mix-up). None changed the
  frozen hypothesis document.
* Budget: 3 experiments (E1 fit/canary/independence, E2 holdout, E3 build/gates), ~1.7 h, 0 slots.

## 5 · Next round (queued, in ranked order from knowledge/81)

1. H88-MASS with a prevalence-matched off-catalogue instrument (the budget lever).
2. H88-COND conductivity local residual (rank 2); H88-SEIS seismic–strain gate (rank 3).
3. If a B-family emission is shipped again: preregister quota placement or a sub-halo budget
   BEFORE the fit.
4. H88-ASTER needs an operator-side EarthExplorer download (free, login) — not viable in-sandbox.
