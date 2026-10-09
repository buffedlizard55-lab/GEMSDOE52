# 41b · H69 pre-registration AMENDMENT — the placement rule, changed before placement ran

**Status.** `knowledge/52_hypotheses_H69_preregistered.md` stays pinned at SHA-256
`7bd6e6824566e96d48156304976cdb42e4109252c84593d7d6b14009ad854ba6` and is **not edited**. This file is an
amendment to one clause of it, written after the two-view fit and **before any placement was executed**,
with its own SHA-256 recorded in `registry/h69_preregistration.json` under `amendment_sha256`.

## What changed

Prereg §4.2–§4.5 pre-registered an emission built from the **measured double-corroborated credited core**
`P1 = A ∩ C` (25,502 px inside the legal set) plus the smallest novel mass that satisfies the brief's
70 % per-raster rule. That clause is **withdrawn and will not be built**.

## Why — new information found after pre-registration, in this repository's own record

Pre-registration was written from `knowledge/40`, `39c`, `38`, `33`, `10` and `01`. It was **not** written
against the H60C correction block in `README.md` and `IR-H61-007` / `IR-UNQ-001` in
`registry/irregularities.json`, which were read afterwards. Those records say, about a file built the same
way:

> **⚠ CORRECTION 2026-10-08 — H60C is NOT a unique submission.** Its 35,185 emitted cells are 80.4 %
> inside the support of prior submissions (73.3 % inside `h33-2-b2` alone; max single-file Jaccard 0.59).
> … it **does not satisfy "unique, not a copy of a previous submission."** Do not present it as the unique
> submission.

and

> **H60C would fail the brief's own lane rule**: near-dot 0.7929 against the champion and 0.8087 against
> `h19-5`, Spearman 0.7083 — DUPLICATE/STOP under the literal rule *and* under the policy. [IR-H61-007]

and, in the H61 summary of why 0.2778 won:

> Beating it therefore needs either **a recombination of existing public mass — which is a duplicate by
> construction and outside this lane** — or a detector above 0.1295 credit density on *novel* mass.

The pre-registered core+novel file would have sat at a near-dot fraction of ≈ 0.695 against the champion:
inside the literal 0.70 threshold, but the same object as the one this repository already corrected, only
tuned to pass by 0.005. Sizing a file so that it lands just under a threshold that a previous round was
corrected for exceeding is exactly the "re-tune a negative result into a positive" failure mode the working
agreement forbids. It is withdrawn.

## What replaces it

1. **The emission is novel-only.** Every emitted pixel is a pixel that no prior raster in the registry
   emitted. The measured credited core is used **only as analysis**: its exact credit interval enters the
   PROJECTION table as the counterfactual "what a recombination would have been worth", clearly labelled as
   not shipped.
2. **Lane feasibility is still enforced during placement, not checked afterwards.** A quota-constrained
   greedy: place in field-rank order with hard-core 3 px spacing; for every informative prior whose near-dot
   count would exceed `floor(0.6985 · S)`, further candidates inside that prior's 3 px halo are skipped.
   The offender set is measured, the greedy re-run under quotas, and the result re-measured against **all**
   informative priors. The file ships only if the re-measurement is clean.
3. **Budget** `S = 37,600` px, the H63/H64 convention (4 × 9,400), which is also within 54 px of the
   champion's 37,654, so the projection is a like-for-like comparison at matched mass.
4. **Ranking field** (unchanged from prereg §4.3): stitched per-fold operating percentile ranks,
   `field = r_B · r_A^0.25 · (1 + 0.5 · consensus / consensus_max)`, restricted to the legal set.
5. Everything else in `knowledge/52` is unchanged: the gates, the instruments, the S1/S2 thresholds, the
   canary alarm, the projection algebra, the verdict rule, and the three-experiment budget.

## Consequence, stated in advance rather than after the fact

Withdrawing the core removes the only mass in this repository whose credit is bounded *exactly* by the
organiser's own reported scores. The shipped file's credit density is therefore unknown and bounded only by
the prior `[0.0279, 0.1387]`. At `S = 37,600` the break-even density needed to match the reported champion
is 0.0907 at `|G| = 5,949.3` and 0.1295 at `|G| = 12,512.1`. **The expected verdict for a novel-only file is
therefore DOWNLOAD YES / SUBMIT NO**, and this amendment says so before the number is known rather than
after. The value of the round is then: the lane measured a fourth time on a rebuilt View A, the first
placement in this repository that satisfies the lane rule by construction, and a quantified statement of
exactly how much a recombination would have been worth and why it is not shipped.
