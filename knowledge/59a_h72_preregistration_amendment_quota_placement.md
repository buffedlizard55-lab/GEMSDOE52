# 59a · H72 preregistration amendment — per-prior quota placement (dated 2026-10-09, BEFORE any holdout or shipped-file placement)

Amends `knowledge/59_hypotheses_H72_preregistered.md` §"Lane construction" step 3–4. Everything else in 59 is unchanged:
the hypothesis, the layers, the consensus pool, the holdout arms' budget and evaluator, the reproduction target, the
canary, the lane limits (0.70 near-dot, 0.90 Spearman), the uniqueness rule and the verdict rule.

## What was measured before this amendment (the reason for it)

`scripts/run_h72.py choose` (plain greedy `nodes.spacing_select` over a consensus pool, 350 informative distinct
census priors, 37,600 dots) measured the worst informative prior's near-dot share for every threshold tried:

| consensus T | pool px | max near-dot share |
|---:|---:|---:|
| unrestricted | 4,592,949 | 0.9377 |
| 200 | 4,517,736 | 0.9315 |
| 150 | 4,109,473 | **0.8916 (lowest)** |
| 120 | 3,808,830 | 0.8971 |
| 100 | 3,664,087 | 0.9013 |
| 80 | 3,408,077 | 0.9039 |
| 60 | 2,930,680 | 0.9037 |
| 50 | 2,561,858 | 0.9029 |
| 40 | 2,105,247 | 0.8999 |
| 30 | 1,630,718 | 0.8935 |

No threshold reaches 0.70. The preregistered construction (pool restriction + greedy) is therefore **infeasible for
this registry**, and the measurement is reported as a wall, not hidden. Receipt: `evidence/h72_choose.json`.

## The amendment

The repository's own lane-feasible method is the per-prior quota of `scripts/run_h69.py::stage_place` (H69 measured
the lane rule satisfied at max near-dot 0.6985 with it). H72 adopts the same rule, re-implemented in
`scripts/run_h72.py::place_quota` (not forked from run_h69, whose stage depends on its own checkpoints):

1. Place greedily in field-rank order over the pool with the same hard-core spacing as `nodes.spacing_select`
   (rejects a candidate with squared distance < 9 px² to an accepted dot).
2. Measure every informative prior's near-dot share (dots within 3 px of that prior's support, divided by dots).
3. Each prior above 0.70 gets a **quota**: at most `floor(0.70 · K)` dots within its 3 px halo. When a quota fills,
   that prior's halo is forbidden for the rest of the placement, so the cap cannot be exceeded.
4. Re-place and re-measure all informative priors; add new offenders to the quota set; stop when none exceed 0.70
   (at most 6 rounds; not converging is reported as infeasible).
5. **T search** keeps the preregistered rule (loosest first, take the first feasible T), over the grid
   `200, 150, 100, 80, 60, 40` (the unrestricted and 300 grid points were dropped to save compute; the grid was fixed
   here, before the quota run, and the plain-greedy trials above already showed those values are not feasible
   without quotas).

The same placement is used for the candidate holdout arm (`H72_B_lane`, per fold, K = 9,400, same T, same quota rule
on that fold's allowed domain). The control arms are unchanged: `single_B` and `random` use plain `spacing_select`
exactly as H61 did, so the reproduction check still applies.

## Why this is not a holdout-driven change

It was adopted from a lane measurement on the **placement** surface, before any holdout arm and before any shipped
file was built. No HOLDOUT-DTI number from H72 existed when this was written. The amendment cannot be tuned against the
holdout because the holdout reads the same placement rule for every candidate.

## What this amendment does NOT do

* It does not make the lane rule easier: the limits are unchanged (0.70 literal near-dot share; 0.90 Spearman).
* It does not make H72 promote-eligible. The verdict rule in 59 is unchanged and still requires the holdout test.
* It does not spend a competition slot.
