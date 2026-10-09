# H66 — results and limits (2026-10-09)

Round: **H66 — strict A-only isolation in the two-view co-training lane, with a lane-valid build.**
Preregistered in [`knowledge/43`](43_hypotheses_H66_preregistered.md) (SHA-256
`1da0fa6cef50118cbdb5ebd4ed7a3e3e3077e5578c8cc62dafcb6bb7072eaa1c`, pinned in
`registry/h66_preregistration.json` before the first fit). Runner: `scripts/run_h66.py` (refuses to run
if the hash moves). Lane: the brief's co-training paragraph. **Verdict: NEGATIVE, research-only.**
Experiments used: 3 of 3 (E1 canary+independence, E2 fit+exchange+nine-arm holdout+capacity, E3 build).
Competition slots used: **0**.

Every DTI number below is **HOLDOUT-DTI** (evaluator `gems52-pooled-hide-v1`, α 0.2, β 0.8, 300 m
triangular kernel, 53,186 withheld positive pixels, 95 % paired 20 km-cluster bootstrap, 1,000 draws).
No number here is a leaderboard score; none is ORGANIZER-CONFIRMED.

---

## 1 · The question this round closes

Every previous "disagreement" arm (H61, H63, H64) ranked the soft field `rankA − rankB` over the whole
eligible domain — a pool of A-only, B-only and concordant-tail pixels. The brief's discovery signal is
specifically *"where A is confident and B is not, the fault may be buried beneath cover"*. That strict
stratum had never been isolated, scored, or emitted from. H66 isolates it (H66-A), and validates two
further lane variants in the same matched-budget holdout: the B-only artifact veto (H66-B) and the
concordant ranking (H66-C).

## 2 · E1 — the brief's two mandated tests, measured first

| test | measured | bar | result |
|---|---|---|---|
| Leakage canary (max single-feature held-out AUC; 75 features × 4 folds, plus the fitted top-5) | **0.6687** (`B_slope_grad_3`, fold 1); fitted max 0.6666 | alarm > 0.90 | **no alarm** |
| Independence: max |ρ| of the two views' spatial-block OOF errors on labelled negatives (2,089 50×50 px blocks) | **0.1337** | abandon ≥ 0.60 | **HELD — exchange allowed** |

Receipts: `evidence/h66_canary.json`, `evidence/h66_independence.json`. The brief's abandonment clause
("abandon the method if they are strongly correlated") does **not** fire: the views' errors are
conditionally independent on this stack. The method fails on *sufficiency* and on the *discovery
signal*, not on dependence.

## 3 · E2 — fit, exchange, nine-arm matched-budget holdout

Shared H61 stages, unchanged (same sampler, learner, folds, thresholds; nothing forked). The control
reproduces the committed value: single_B **0.174571** vs 0.174517 committed (|Δ| = 5.4e-05), so the
comparison is on the identical instrument as H61/H63/H64.

| arm | HOLDOUT-DTI | 95 % CI | vs single_B (paired Δ, 95 % CI) |
|---|---:|---|---|
| single_A | 0.071954 | [0.0566, 0.0886] | −0.1026 [−0.1250, −0.0815] |
| **single_B (control)** | **0.174571** | [0.1523, 0.1963] | — |
| union_max | 0.149009 | [0.1281, 0.1694] | −0.0256 [−0.0441, −0.0070] |
| disagreement_pre | 0.033293 | [0.0238, 0.0446] | −0.1413 [−0.1621, −0.1204] |
| disagreement_post | 0.032884 | [0.0219, 0.0457] | −0.1417 [−0.1654, −0.1185] |
| **a_only (H66-A, new)** | **0.046023** | [0.0314, 0.0621] | **−0.1285 [−0.1513, −0.1062]** |
| single_B_veto_Bonly (H66-B, new) | 0.167221 | [0.1472, 0.1865] | −0.0074 [−0.0112, −0.0034] |
| concordant (H66-C, new) | 0.119590 | [0.1022, 0.1371] | −0.0550 [−0.0714, −0.0371] |
| random | 0.080426 | [0.0702, 0.0910] | −0.0941 [−0.1098, −0.0785] |

All nine arms placed exactly 9,400 dots per fold at 3 px minimum separation and filled their budgets
on all four folds (`evidence/h66_holdout.json`). The exchange ran (independence held): 15,446 pseudo
pixels, one whole-segment round per direction per fold, and transferred nothing
(disagreement_post − disagreement_pre = −0.0004, in line with H63's −0.000364).

**Sufficiency S1, fifth consecutive failure:** View A out-of-quadrant AUC mean **0.5166**, min fold
**0.4673** (gate ≥ 0.60 / ≥ 0.55) — H61 0.5163 · H63 0.5362 · H64 0.5230 · H65 0.5202 · H66 0.5166
(`evidence/h66_sufficiency.json`).

### 3.1 · The pure stratum — the brief's literal signal, measured purely

The holdout's `a_only` arm is the top-K of the gated field; because the stratum's 3 px-thinned cells
are fewer than K on every fold, most of that arm's dots sit at field = −1 **outside** the stratum
(measured per fold in `evidence/h66_a_only_capacity.json`:
[5,239/4,161], [2,910/6,490], [1,272/8,128], [1,729/7,671] inside/outside). The pure stratum — placed
only inside the gate, at its achieved budget, never rescued to K — scores:

| pure strict A-only stratum | HOLDOUT-DTI (unmatched budget) | 95 % CI | vs single_B | vs random |
|---|---:|---|---|---|
| achieved budgets 5,239 / 2,910 / 1,272 / 1,729 px per fold | **0.017351** | [0.0124, 0.0235] | −0.1550 [−0.1767, −0.1323] | **−0.0631 [−0.0739, −0.0521]** |

**The brief's literal discovery signal is anti-informative on this stack.** Mass placed where View A is
confident and View B abstains lands where hidden faults are *less* likely than under uniform placement.
View A's confident tail is systematically misplaced out of quadrant (OOF AUC ≈ 0.52 for the fifth
consecutive round), so the disagreement signal inverts: the pixels where the potential-field view is
most confident and the surface view abstains are the pixels where hidden faults are *least* likely.

### 3.2 · The two further lane variants — both negative, paired CIs exclude 0

* **H66-B (B-only artifact veto):** single_B minus the B-only stratum scores 0.1672, *below* single_B
  (paired Δ −0.0074 [−0.0112, −0.0034]). The brief's artifact clause is falsified on this stack:
  B-confident ∧ A-abstaining pixels are faults, not roads or erosion lines — vetoing them removes real
  signal.
* **H66-C (concordant ranking):** `min(rankA, rankB)` scores 0.1196, below single_B (Δ −0.0550
  [−0.0714, −0.0371]). Requiring the potential-field view's agreement dilutes the surface view's
  ranking — View A contributes no transferable out-of-quadrant skill to a joint ranking.

## 4 · E3 — the build, and why the file is small and lane-DUPLICATE

The build emits the strict A-only post-exchange field with the lane-valid constrained placement of
prereg §3 (every informative prior constrained from the first placement; budget discovered by
descending feasibility probes over [16,000, 40,000]).

* The registry for this build: **553** rasters (524 census + 29 local artefacts) → **516 informative**,
  **35** universal-coverage probes (measured 3 px coverage ≥ 0.95).
* The exact-novelty rule (no emitted cell is a positive pixel of an informative prior; declared post hoc
  in knowledge/39c, unchanged) shrinks the allowed domain from 4,325,298 to **164,794** px.
* The strict A-only gate over that domain leaves a candidate set whose 3 px-thinned cells number
  **610** — every budget probe placed exactly 610 (candidate exhaustion).
* **No lane-valid emission exists from this candidate set.** The largest placement (610 dots) has a
  worst informative near-dot share of **1.0000**: every placeable strict-A-only cell lies within 3 px of
  one registry raster's dots (measured; `evidence/h66_lane_dots.json`, policy verdict
  DUPLICATE/STOP, max near-dot 1.0). The H64 file's dots sit on the same lineaments, so the stratum is
  a strict duplicate of an existing lane under the brief's own 70 % rule. Per the lane rule this is
  logged as a duplicate and the round stops.

The published file is the largest constrained placement (610 dots), labelled honestly:

| gate | result |
|---|---|
| Format (single-band float32, EPSG:32611, 3,730×3,292, sample transform, finite, values exactly {0,1}, 0 NaN, no mass outside the footprint) | **PASS** |
| Decoded-pattern uniqueness, tier 1 (all 553 priors) | **PASS** (canonical pattern unique; identical to none) |
| Exact novelty, tier 2 (516 informative priors) | **1.0** (no emitted cell is a positive pixel of an informative prior) |
| Not the union of the two views | **PASS** (Jaccard vs union_max 0.0184; vs single_A 0.0463; vs single_B 0.0000) |
| Lane, literal (dots) | **DUPLICATE/STOP** (max near-dot 1.0 — saturated by the registry lattice probe for any nonempty candidate) |
| Lane, saturation policy (dots) | **DUPLICATE/STOP** (max informative near-dot 1.0) |
| Lane, surface (literal / policy) | PASS / PASS (the continuous field, before placement) |
| S1 sufficiency | **FAIL** (0.5166 / 0.4673) |
| Holdout beats single_B (paired 95 % CI > 0) | **FAIL** (−0.1285 [−0.1513, −0.1062]) |

**Verdict: NEGATIVE, research-only. DOWNLOAD YES (format-valid and unique on decoded pixels);
SUBMIT NO.** Competition slots used: 0. Run card: `evidence/h66_run_card.json`.

* **File:** `gems52-h66-aonly-cotrain-610px-20261009T055521Z.tif` — 58,363 bytes, 610 emitted cells
* **SHA-256:** `ea9774a871929427e60261cdfe2f64fdab0d0c8c2253cf2eac119cc404e28af3`
* **Submission name:** `gems52-h66-aonly-cotrain-610px-20261009T055521Z` · **note (132/140 chars):**
  `H66 strict A-only co-training discovery stratum; constrained placement at 610 dots, lane-DUPLICATE;
  research only, not slot-approved`

(A first build iteration adopted a budget of 610 but emitted the 427-dot capped re-placement and
verified its share against the wrong denominator — a self-caught bookkeeping bug, IR-H66-002. The
fallback in `scripts/run_h66.py` now verifies with the true emission size; the corrected build emits the
610-dot largest placement and supersedes it. The superseded artefact was removed; the corrected TIF's
bytes and SHA-256 are the ones above. The submission note's wording was corrected in the receipts only —
the TIF bytes never changed.)

## 5 · What the round establishes (the deliverable is the negative result)

1. **The brief's literal discovery signal is falsified, purely and decisively.** The strict
   A-confident ∧ B-abstaining stratum scores 0.0174 pooled at its achieved budget — significantly below
   uniform random (paired Δ −0.0631 [−0.0739, −0.0521]) and far below the single-view control
   (Δ −0.1550). Five rounds of View A rebuilds (H61 raw, H63 step-normalised, H64 capacity-cut,
   H65 cross-strike, H66 unchanged-learner control) all measure OOF AUC ≈ 0.52, and the one stratum
   that would have rescued the disagreement idea inverts.
2. **The artifact clause is falsified.** B-only pixels are faults, not artifacts (vetoing them costs
   0.0074, CI excludes 0).
3. **The concordance clause is falsified.** Requiring both views to agree dilutes the surface view
   (Δ −0.0550, CI excludes 0).
4. **The independence premise held** (max |ρ| 0.1337 < 0.60) — the abandonment clause does not fire;
   the lane dies on sufficiency and on the discovery signal itself.
5. **The stratum is a duplicate lane.** After exact novelty, every placeable strict-A-only cell lies
   within 3 px of an existing registry raster's dots. The lane rule's own stop condition is met.
6. **The co-training exchange transferred nothing, again** (post − pre ≈ −0.0004), on 15,446 pseudo
   pixels, with the independence screen passed first.

## 6 · Limits

* The pure-stratum number is at an **unmatched** achieved budget (5,239 / 2,910 / 1,272 / 1,729 dots per
  fold); it is a labelled diagnostic, not a matched-budget comparison. The matched-budget `a_only` arm
  (0.0460) is a mix (per-fold inside/outside splits in `evidence/h66_a_only_capacity.json`).
* The holdout simulator measured Spearman −0.10 against the owner-reported board in R4; it screens
  procedures, it does not rank board performance. No projection to a board score is made.
* Catalogue-zero negatives are proxies, not verified fault absence (IR-52-004).
* Inputs are integrity-pinned owner mirrors (SHA-256 verified after restore), not
  organiser-authenticated downloads; the portal data tab is login-walled.
* Every board number cited anywhere in this repository is PUBLIC BOARD or OWNER-REPORTED; none is
  ORGANIZER-CONFIRMED. The live board top on 2026-10-09 is 0.3774 (xiaofanhu); 0.3195 is rank 7 (DARD);
  the 0.2778 row (rank 13, extradr19) is not linked to any file (IR-H65-003).
* The lane's literal gate is saturated by a registry spacing-5 lattice probe (measured 3 px coverage
  ≥ 95 % of the eligible footprint), so it reads DUPLICATE/STOP for every nonempty candidate — a
  property of the registry, disclosed, with the saturation-aware policy reported alongside.
* The file is a research artefact: unique on decoded pixels and exactly novel, but lane-DUPLICATE under
  the policy rule and below the single-view control on holdout. It must not be uploaded.

## 7 · Suggested next work (for the selector and the next round)

* The co-training lane is closed on this stack: five sufficiency failures, an anti-informative
  discovery stratum, a falsified artifact clause, a falsified concordance clause, and a duplicate-lane
  stop. Do not re-run it with another View A rebuild (H66-E, deformation-only View A2, is the only
  untested View A variant left; it needs its own round and its own store build).
* The measured facts that survive every round: **single_B (surface + radiometrics) is the only arm
  that beats random** (0.1746 vs 0.0804); binary {0,1} mass is metric-optimal at fixed support; mass
  within 200 m of a mapped trace earns no credit and pays the false-positive tax; placement is worth
  more than detector recall (scatter control 0.0778 at the champion's mass).
* The open question with real upside is not another detector but **credit-density placement on the
  surface view's ranking**: the champion family's edge is placement discipline, and the live board's
  0.3774 leader is nearly maxed on it. A candidate that beats 0.2778 must rank pixels by "probability an
  uncatalogued fault pixel lies within 224 m", which no instrument in this repository can certify.
* H66-D (radiometric-cover gating of A-only) and H66-E (deformation-only View A2) remain deferred from
  the preregistration; both are now moot for the A-only stratum (it is anti-informative and a duplicate
  lane), and H66-E alone would justify a fresh round if a deformation-based discovery signal is wanted.
