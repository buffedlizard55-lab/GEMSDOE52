# 80a · H88 pre-registration amendment — veto rank on positive support only (written before any fit)

**Date:** 2026-10-10, same session, **before any view was computed and before any holdout was run.**
**Original registration:** `registry/h88_preregistration.json`, SHA-256
`0f664c43f166264864c3815d31a9230f5b95b257a426d4670a8b5ed7c78f7094` — **unchanged** (repo
protocol: an amendment is a new, hashed record; the frozen spec is never rewritten).

## What was wrong in the frozen formula

The frozen field formula was `veto = rank01(clip(b - a, 0, 1))`, where `rank01` is the
argsort-argsort rank inside the footprint (`scripts/run_h86_holdout.py:rank01`). On an
approximately independent pair of rank fields `a`, `b`, about half of the footprint has
`b - a <= 0`, so `clip(b - a, 0, 1)` is **zero on roughly half the pixels**. The argsort-argsort
rank of a tied zero block is a mid-rank spread over the lower half of [0,1] (roughly 0.25 on
average), so pixels where View A dominates (the round's own buried-fault targets) would still
receive a veto penalty of about `1 - 0.70*0.25 = 0.825`. That contradicts the stated intent —
"veto where B is confident and A abstains" — and penalises exactly the population the lane asks
us to emit.

This was found by reading the frozen formula against the shared `rank01` implementation, not by
any fit or holdout result. No experiment has been run yet this round.

## The amendment (frozen from this point)

```
art  = clip(b - a, 0, 1)                       # unchanged
veto = 0 where art == 0                        # A >= B: no artifact suspicion, no penalty
veto = rank01(art) evaluated on art > 0 only   # graded percentile among suspected pixels
field = (0.45 * consensus + 0.55 * buried) * (1 - 0.70 * veto)   # unchanged
```

Everything else in `registry/h88_preregistration.json` stands: component lists, weights, budgets,
arms, gates, lane thresholds, bar 0.192829, and the independence gate at 0.6.

## Record

* Amendment file hash is pinned in `scripts/run_h88_cotrain_bidir.py` next to the original
  registration hash; the runner refuses to start if either moves.
* This document is evidence of an amendment **before any fit**; if any later receipt shows a fit
  timestamped before 2026-10-10T22:12:00Z, this amendment is void and the round must be discarded.
