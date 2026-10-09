# 43_h66cover · Dated amendment to knowledge/43_h66cover (H66cover) — the budget is a cap over the gate support

**Status: amendment, dated 2026-10-09, written when the build stage first ran — after the holdout
numbers existed but before any build number did.** The frozen file `knowledge/43_h66cover` is not edited; its
SHA-256 stays pinned in `registry/h66cover_preregistration.json`, and this amendment is pinned alongside it
under `amendments`. The runner verifies both hashes and refuses to run if either moves.

## What the frozen text says, and what the build measured

`knowledge/43_h66cover` §4 freezes:

> placement = nodes.spacing_select(field66, allowed, K, min_px=3.0)   (metric-aware)

and also freezes, in the same section:

> Every emitted cell is an A-only candidate by construction.

The build measured the field's actual support: after the exact-novelty mask (the lane's own uniqueness
rule, `knowledge/39c`, applied identically to every candidate), the allowed domain shrank from
4,325,298 to 164,794 cells, and the A-only gate (rankA ≥ 0.95 and 0.35 ≤ rankB ≤ 0.65 over that
domain) contains **1,657 cells**. The template budget K = 37,600 cannot be filled from a gated field:
`spacing_select(field66, allowed, 37600)` would fill the remaining 35,943 places with **−1 cells
outside the gate**, which contradicts the frozen definition's own claim that every emitted cell is an
A-only candidate. The two frozen clauses are mutually inconsistent for a sparse gated field; this
amendment resolves the inconsistency in favour of the scientific claim.

## The declared resolution (a uniqueness-constraint consequence, not a holdout-driven re-tune)

1. **The emission domain is the gate support** (`field66 > −1`), not the whole allowed domain. The
   placement is unchanged in kind: `nodes.spacing_select(field66, gate_support, min(K, gate_cells),
   min_px=3.0)` — the same metric-aware greedy, the same 3 px separation, the same score order.
2. **The template budget is a cap, not a target.** The shipped emission is the gate cells that survive
   exact novelty, the 3 px spacing and the per-raster 70% rule. Its size is measured, not chosen.
3. **The per-raster 70% cap is relative to the candidate's own dots** (`cap = floor(0.70 × target)`),
   exactly as the lane rule states ("more than 70% of YOUR dots within 3 px of one registry raster's
   dots"). If the constrained re-placement cannot reach the target, the unconstrained emission is
   kept and the dots lane gate (the authority) reads the final raster — the H64 precedent of carrying
   a DUPLICATE label rather than shipping a file that violates the lane.
4. **The holdout comparison is unchanged.** The `h66a_cover_gated_a_only` arm placed 9,400 dots per
   fold from the same gate field over each fold's own allowed domain, which does not model the
   registry-novelty constraint (the holdout's truth is the withheld catalogue; other teams'
   submissions are not in it). The shipped file is smaller than the holdout arm for exactly this
   reason, and the run card states both numbers side by side. This is a disclosure, not a
   matched-budget claim.

## Why this is not a silent re-tune

* No threshold, gate, learner, feature, fold, seed or arm changed. The holdout numbers in
  `evidence/h66_holdout.json` were produced before this amendment existed and are not re-run.
* The change decides only **where the frozen field may place dots** (its own support) and **how the
  budget is read** (cap, not target). The alternative reading emits cells the field itself scores −1.
* Logged as **IR-H66-013** in `registry/irregularities.json`.

*Namespacing note (IR-H66-015): this amendment and its parent document were renamed to the
`h66cover` prefix after a parallel-session collision on the H66 label; the pinned SHA-256 of the
frozen hypothesis document is unchanged.*
