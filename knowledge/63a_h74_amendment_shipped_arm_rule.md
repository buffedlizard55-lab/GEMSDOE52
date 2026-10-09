# 63a — H74 amendment: which arm gets written to the shipped GeoTIFF

**Written before `stage_holdout` executed.** At the time of writing, the only H74 numbers that exist
are the leakage canary (max AUC 0.6691, `B_slope_grad_3`, no alarm) and two of the eight per-fold
view fits from `stage_diag`. No arm score exists yet. This amendment therefore binds the same way
the base preregistration does: it cannot be tuned to a result that has not been measured.

## Why an amendment is needed

`knowledge/63_hypotheses_H74_preregistered.md` §3 fixes the **verdict** rule (six clauses, all must
pass to recommend spending a weekly slot). It does not say **which field is written to the TIFF when
clause 6 fails**, because the brief requires a unique downloadable TIF in every case and the verdict
rule can legitimately return "negative". Leaving that choice until after the numbers are visible
would be a post-hoc degree of freedom. It is closed now.

## The rule (frozen)

1. The shipped field is always one of the round's **new** arms:
   `{swap_010, swap_025, swap_050, line_support_B}`. The controls
   (`single_A`, `single_B`, `union_max`, `disagreement_pre`, `disagreement_post`, `random`) are
   measured for comparison and are **never** shipped — shipping a control would publish a relabelled
   single-view baseline, which the brief explicitly forbids ("confirm the output is not merely the
   union of the two views", and by the same logic not merely one view).
2. Among those four, ship the one with the **highest pooled point HOLDOUT-DTI**. Ties break in the
   listed order (lowest φ first, then `line_support_B`), i.e. toward the arm closest to the
   measured baseline.
3. The choice of shipped arm **does not alter the verdict**. Clause 6 is still
   "the shipped arm's paired 20 km cluster-bootstrap CI lower bound against `single_B` is > 0".
   If the best new arm does not clear it, the published verdict is **NEGATIVE / research-only** and
   the site must say, in the same words, that the file is fine to download but must not be spent on
   a weekly slot.
4. `φ = 0` is not in the candidate set, because `_swap_field` at φ = 0 reproduces `single_B`
   bit-for-bit and would re-publish the baseline under a new name.

## Consequence accepted in advance

This guarantees the shipped raster is a genuine co-training product (View B backbone with a View A
rescue stratum, or a trace-integrated transform of the co-trained operating field) and that its
headline number is reported honestly even when that number is worse than the baseline. A negative
result is a deliverable; a laundered baseline is not.

## Placement, unchanged from §2 of the base document

Greedy top-S on the composite field inside the legal set (valid ∧ not catalogue ∧ > 200 m from a
mapped trace), 3 px hard-core separation, per-prior near-dot quota `floor(0.6985 · S)` enforced on
the achieved budget, cross-family consensus threshold searched from the loosest value downward and
the first lane-feasible threshold taken. `S = 37,654`.
