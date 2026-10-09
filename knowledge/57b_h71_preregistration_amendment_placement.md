# 57b · H71 preregistration amendment 2 — placement design after the measured halo statistics

**Status: amendment to `knowledge/57` (H71), superseding the placement clause of `knowledge/57a`.
Recorded after the halo measurement (`evidence/h71_halostats.json`) and before the final E3 build.
The frozen thresholds, the candidate definition, the experiments and the verdict rule of 57 are
unchanged.**

## 1 · What 57a assumed and what the build measured

57a placed in the **exact-novel** A-only stratum (no emitted cell on any informative prior's positive
pixel) with a per-prior near-dot cap of `floor(0.70 · B)` for a *requested* budget `B`, scanning for a
budget that fills exactly. The E3 build measured:

* exact-novel stratum: **1,754 px**; capacity at 3 px separation: **616 dots**;
* the fill stopped at **exactly `floor(0.70 · B)` for every requested `B` tried** (616→431, 591→413,
  566→396, …), which happens iff at least one informative prior's 3 px halo covers essentially every
  candidate the greedy would take;
* the halo statistics confirm it: **8 informative priors cover > 70% of the exact-novel subset**
  (one covers 100.0% of it), and **20 informative priors cover > 70% of the full stratum**
  (max 90.65%, prior `4e50a598…`, footprint 3 px coverage 0.8976).

Two separate problems were conflated in 57a:

1. **the cap must be set relative to the FILLED count**, because the lane's statistic is
   `near_i / filled`, not `near_i / requested_budget`. A cap `0.70 · B` with `filled < B` is
   stricter than the lane requires and (as measured) never admits an exact fill;
2. **restricting placement to the exact-novel subset removes the room the cap needs.** The lane's
   70% rule is satisfiable exactly when enough dots can be sourced *outside* each high-coverage
   prior's halo; the novel subset is too small and too dominated by one prior's halo to do that.

## 2 · The amendment

1. **Placement domain = the full A-only stratum** (57,143 px, all inside the allowed emission
   domain), not the exact-novel subset. Exact-novelty is handled by ordering (rule 3), not by
   excluding 97% of the domain.
2. **Cap relative to the filled count.** The placement searches for the largest fill `f` under a
   per-informative-prior near-dot cap `c` such that **`c ≤ 0.70 · f`** — i.e. the built file
   satisfies the lane's own rule (near-dot fraction ≤ 0.70 against every informative prior) by
   construction. The search probes a descending grid of caps, places greedily at 3 px for each,
   and keeps the feasible `(c, f)` with the largest `f`; floor 300 dots. The dots lane check after
   placement verifies the built bytes against the same rule (`gems52.gates.lane_report`).
3. **Novelty ordering.** Candidate order is: exact-novel cells (not on any informative prior's
   positive pixel) first, then non-novel cells — in both cases by View A's out-of-fold rank
   descending, at 3 px separation. Rationale: the repo's own uniqueness gate
   (`gems52.gates.uniqueness_report`, `support_novelty_gate_ok`) requires ≥ 20% support novelty,
   and the exact-novel pool (1,754 px, capacity 616 at 3 px) is the only domain where novelty is
   possible; drawing those dots first makes the ≥ 20% tier-2 gate attainable at a total budget
   ≤ ~3,080 dots. This is a placement-order preference, not a threshold change.
4. **Fallback.** If no cap in the grid admits `f ≥ 300`, the build places the novel-first greedy
   emission without an effective cap (budget 23,000), reports the measured policy-lane verdict
   verbatim (expected DUPLICATE/STOP, with the binding priors named), and the verdict rule of 43
   then reads NEGATIVE on the lane gate. The file is still written, validated and published for
   research — a measured STOP is a deliverable, and the round's holdout gate has already failed,
   so no verdict can be promote-eligible either way.
5. **What does not change:** the candidate field, all thresholds (donor ≥ 0.95, receiver abstain
   [0.35, 0.65], 3 px separation, 200 m catalogue exclusion, 23,000 build cap), the control
   reproduction bar, the six gate verdicts of rule 8, the experiment budget (this is still E3),
   and the no-slot rule.
