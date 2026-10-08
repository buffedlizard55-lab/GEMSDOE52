# 27 · R5: why 0.2778 is 0.2778, what would beat it, and what this round shipped

The brief asks for a PhD-level answer to one question — why did
`h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` score 0.2778, and can this repo generate something
better — and then asks for the answer to be turned into a unique submission. This file is the answer
and the turning. Every number is either measured on restored bytes in this checkout, quoted from an
official source in `knowledge/25`, or labelled as a prior with its bounds printed.

## 1. The three bars, with their owners

| bar | value | whose | source |
| --- | --- | --- | --- |
| this family's best | **0.2778** | `extradr19`, rank 13, 12 submissions | board fetch 2026-10-08, `registry/leaderboard_snapshot_2026-10-08.json`; owner-reported file↔score pairing |
| the brief's stated target | **0.3195** | `DARD`, rank **7**, 16 submissions | same |
| the board top | **0.3774** | `xiaofanhu`, rank 1, 13 submissions | same |

The brief says "current leaderboard best is 0.3195". It is not; it is rank 7 (`IR-R5-005`). This repo
already knew: the 2026-10-07 snapshot recorded 0.3774 at rank 1, and the H57 acceptance addendum in
`README.md` says in terms "never call 0.3195 'the highest score right now'". All three bars are
carried through every projection below, because a strategy aimed at seventh place is not a strategy
aimed at first.

The shape of the board matters more than any row. Ranks 8–22 span 0.2707–0.2888 — fifteen teams
inside 0.018 — and then there is a **gap of 0.031** to rank 7. A cluster that tight with a step above
it is what a shared ceiling looks like: eleven teams are finding the same easy fraction of the truth
and stalling. This family is inside the cluster, at 0.2778, and has been for twelve submissions.
`arnofault` is rank 14 at 0.2764 with **one** submission, which says the ceiling is about what you
emit, not about how many times you get to measure it.

## 2. Why 0.2778, exactly

The file is `h27-4-r1` with the catalogue mask removed. Set arithmetic on the restored bytes:

```
A = h33-2-b2      40,199 emitted px, of which 2,545 sit on label pixels → S_eval = 37,654   score 0.2778
B = gems24-d2-8   46,635 emitted px, same 2,545 masked                → S_eval = 44,090   score 0.2600
A ⊂ B ;  B \ A = 6,436 px, every one of them 100–200 m from a mapped trace
min distance-to-catalogue inside A = 223.6 m
```

With the organiser's own formula (`knowledge/25` §3) and binary mass, `DTI = T/(0.2 S + 0.8 |G|)`
where `T = TPw` and `M = T` because A's dots are more than 200 m apart:

```
T(A) = 0.2778 (0.2·37,654 + 0.8|G|)      T(B) = 0.2600 (0.2·44,090 + 0.8|G|)
T(B) − T(A) = 200.62 − 0.01424·|G|
```

`B \ A` is the 100–200 m corridor. Setting its credit to zero — which is what "deleting it raised the
score" means — gives **`|G| = 14,088.7 px`**, and then `T(A) = T(B) = 5,223.1`, so

> **ρ(A) = T/S = 0.1387 credit per emitted pixel = 5.0× uniform random (0.0279).**

The +6.8 % came from deleting 6,436 px of pure false-positive mass. **Not** from deleting the 2,545
on-label pixels: staff confirmed on 2026-09-16 that masked pixels "do not count towards penalty
terms", so those were already score-neutral (`IR-R5-007` corrects `knowledge/01` §1, which had the
mechanism backwards). The distinction is not pedantry — it is the difference between "the organiser
hides a 2 px buffer around known faults" (false) and "this family's corridor pixels were worthless"
(true, and a statement about this family's field, not about the corridor).

What the champion's 5,223 credits are made of, from the atom partition of `{A, B, C = d1-5, E = h19-5}`
(`knowledge/10` §3, re-derived on the restored bytes this session):

| atom | px | credit | density ρ | reading |
| --- | --- | --- | --- | --- |
| `P1 = A ∩ C` | 25,502 | **[4,168, 5,223]**, central 5,140 | **0.163–0.205** | selected by two independent thinnings of the same field |
| `P2 = A \ C` | 12,136 | [0, 1,055] | 0–0.087 | selected by one |
| `P3, P4 = B \ A` | 6,436 | **0** (bounded 0–85) | ≤0.0132 | the corridor: half of random |
| `P5, P6 = E \ B` | 66,142 | 1,599 measured | **0.0242** | the family field's own tail: random |

Three things follow, and they are the whole of the strategic picture:

1. **The family's field is exhausted.** Its unemitted tail — 66,142 px beyond `d2-8` — earns ρ =
   0.0242, indistinguishable from uniform random at 0.0279. There is nothing left to win by
   re-ranking the same field; `T(E) − T(B) = 1,599` is the entire remaining yield of 121,131 px.
2. **Corroboration is the only sub-ranking the published scores can see.** Two independent thinnings
   agreeing (P1, ρ = 0.201) beats one (P2, ρ ≤ 0.087) by a factor of 2.3 or more, and beats the
   field's average (0.1387) by 1.45. That is a property of the *selection procedure*, which is why it
   is the one law in this repo that plausibly transfers to a new field — and why R5's emission is
   built on a multi-family agreement test rather than on one rank.
3. **Emitting P1 alone would score 0.2546–0.3190 (central 0.3139)** with no new geology at all. The
   upper end of that interval is 0.0005 below the brief's target. It is also 63 % of the champion's
   own pixels, which is why R5 did not ship it (§6).

## 3. What `|G|` is, with the bound corrected

`knowledge/10` §2 calls `|G| = 14,088.7` exact. It is exact **given** "the corridor earned nothing".
Solving `T(B) − T(A) = 200.62 − 0.01424|G|` for the corridor credit `Δ` and intersecting with the
independent bound `|G| ≥ 8,128` (from `T ≤ |G|` applied to `8GEMSDOE_Hedge-v2`, 166,519 px at
0.1563) gives `Δ ∈ [0, 85]` and therefore

> **`|G| ∈ [14,030, 14,089]` px = 0.272–0.273 % of the 5,165,840 px footprint.**

The interval is 0.4 % wide, so every downstream figure is unaffected; the *word* "exact" was not
earned and is corrected here. Independently: the organiser says the truth is "faults that are not
contained within the current public USGS database" (`knowledge/25` §1), so `|G|` counts expert-mapped
**new** faults only, and the mask is pixel-exact on the known ones — which is why `|G|` is a small
number and why the catalogue's own 60,988 px are irrelevant to it except as geometry (§H60-A).

## 4. What it would take to beat each bar

For a binary emission `DTI = T/(0.2 S + 0.8|G|)` with `T ≤ min(ρS, |G|)`. Required credit density:

| S (emitted px) | ρ needed for 0.2778 | ρ for 0.3195 | ρ for 0.3774 | best ρ ever measured here |
| --- | --- | --- | --- | --- |
| 16,681 | 0.2121 | 0.2442 | 0.2875 | 0.2010 (inherited, P1) |
| 25,000 | 0.1812 | 0.2087 | 0.2456 | " |
| 37,654 | 0.1424 | 0.1640 | 0.1930 | 0.1387 (the champion, at this S) |
| 40,000 | 0.1339 | 0.1542 | 0.1815 | — |
| 60,000 | 0.1077 | 0.1240 | 0.1459 | — |
| 100,000 | 0.0869 | 0.0999 | 0.1176 | — |
| 166,519 | 0.0714 | 0.0822 | 0.0967 | 0.0418 (Hedge-v2, at this S) |

and the `|G|` cap binds at `S = |G|/ρ`, beyond which more mass only adds tax. Reading the table
against the record:

* **To beat 0.2778** a novel field needs ρ ≥ 0.134 at S = 40,000, i.e. **as good as the champion's
  own field at the same budget**. Not impossible — an outside-family PINN file scored 0.2750 at
  38,854 px, ρ = 0.135 (`knowledge/10` §4) — but nothing in this repo has measured a novel field
  reaching it.
* **To beat 0.3195** it needs ρ ≥ 0.154 at 40,000, or ρ ≥ 0.0999 at 100,000. The only mass here that
  has ever measured above 0.154 is P1, which is inherited.
* **To beat 0.3774** it needs ρ ≥ 0.182 at 40,000 or ρ ≥ 0.118 at 100,000 — above anything this repo
  has measured anywhere, inherited or not. The board top is not a budget choice; it is a better field.

Two structural levers, both derived rather than hoped for:

**(a) The budget law.** For a credit curve `T = c·S^β`, `DTI(S)` is maximised at

> **`S* = 4|G|β/(1−β)`**  (the amplitude `c` cancels), giving `DTI* = c·S*^β/(0.2 S* + 0.8|G|)`.

With the measured `β = 0.2284` from `T(S) = 471.6·S^0.2284` — fitted on three family members and
validated on five more across two families to within 4 % — `S* = 16,681 px` (9,945–24,152 over
β ∈ [0.15, 0.30]). `knowledge/10` §8 reached the same 15–20k window from a completely different
prior, which is the reason this round treated it as a law and froze it rather than tuning a budget.

**(b) The marginal rule.** `d(DTI)/dS > 0` iff the *marginal* credit rate exceeds `0.2·DTI`. At
DTI = 0.28 the bar is ρ_marginal > 0.056; at 0.32 it is 0.064. Uniform random mass (0.0279) is below
both, so **padding an emission with random or habitat-ranked pixels always hurts**, and the only
legitimate way to grow `S` is to have pixels above the bar.

**(c) The round-dependence.** `S*` scales linearly in `|G|`, and the final round is scored "on the
entire GeoDAWN area" with expanded labels (`knowledge/25` §5). If the whole-area `|G|` is 2× the
effective public one, `S*` is 33,400; if 4×, 66,800. One file serves both rounds, so the shipped
budget is a bet on the round whose `|G|` can be measured. It is placed on the measurable one, and the
bet is written down (`knowledge/26` H60-F).

## 5. Why no instrument in this repo can rank a novel field — replicated this round on new data

Three disqualifications, all measured, and R5 reproduced the first with a different detector and
different folds:

1. **The hide-and-recover localisation assay does not predict the board.** `knowledge/10` §5:
   Spearman(reported score, simulated DTI) = −0.1045, p = 0.734, n = 13; the champion is the *worst*
   of the 13 on that instrument and the best on the board. R5 rebuilt the instrument (whole-component
   folds, lateral error instead of capture, four 20 km block folds, emission restricted to each fold's
   legal set) and got the same inversion: on it, the champion family's habitat field scores
   **0.0003**, uniform random **0.0275**, and the new six-family trace field **0.0395**
   (`evidence/r5_budget.json`, `work/r5/r5_assay.json`). A ranking that puts habitat below random
   cannot be used to promote anything, in either direction. The mechanism is visible: the assay's
   truth is *mapped* catalogue inside a hidden fold, and its emission is forbidden within 200 m of
   *visible* catalogue, so a field that ranks on proximity to mapped faults has its advantage removed
   and its mass left in the least fault-like places.
2. **No per-pixel feature re-ranks credit inside the champion.** 63 point and local-differential
   features and 108 structure-tensor features, best AUC(P1 vs P2) = 0.5453 and 0.5122
   (`knowledge/10` §6). Habitat AUC reaches 0.7023, and P2/P5/P6 have almost the same habitat AUCs as
   P1 while carrying 20× less credit. **Habitat is not credit.**
3. **R5 replicated #2 with a brand-new detector.** The six-family corroborated-ridge pool
   (`corr99 ≥ 2`, 653,593 px, 13.4 % of the legal footprint) contains the champion's emission at
   **1.54×** enrichment — and contains every credit tier at the same rate: P1 **1.47×**, P2 1.70×,
   P5 1.64×, P6 1.66×, the family's tail 1.65×. The pool captures where this family *emits* and says
   nothing about which emissions were *right*. A new detector, a new measurement, the same result.

What is left, and it is not nothing: the **strike coherence of the credited cloud** (`knowledge/10`
§7), which is a property of an emission's *arrangement* rather than of its pixels' habitat, and which
is therefore not touched by disqualification #2. R5 rebuilt it and it replicates: the champion's
37,638-dot cloud has mean coherence **0.5309** at σ = 4 px and **15.85 %** of dots above 0.8, against
**0.3886** and **2.27 %** for a mass-matched random cloud — the published values were 0.531 / 16.8 %
and 0.362 / 2.2 %, so the instrument reproduces to three decimal places on independently restored
bytes.

## 6. What R5 shipped, and the four rules that chose it

`scripts/run_r5_novel.py` froze its rules **before** the candidates were built. They are printed in
the script's docstring and in `evidence/r5_novel_emission.json → frozen_rules`; the numbers below are
what came out.

**R1 — strictly novel.** No pixel emitted by any of the **55** rasters this repo has ever produced
(the 13 organiser-scored files *and* every research artifact in `submission/` and `docs/downloads/`;
their union is 1,365,956 px), and no pixel within 200 m of a mapped trace. Measured result:
`novel_fraction = 1.0000` against all 55, and 1.0000 against the 13 scored files separately. The
first build of this file reported 0.8021, because it excluded only the 13 scored priors and 19.8 % of
its pixels turned out to have been emitted by this repo's own never-submitted research artifacts;
the exclusion set was widened and the file was rebuilt. That is the difference between "unique" as a
claim and unique as a measurement.

**R2 — the budget is derived, not tuned.** `S* = 4|G|β/(1−β) = 16,681 px` (§4a).

**R3 — the choice among candidates is made on coherence, not on the assay.** Seven candidates at
S = 16,681, all strictly novel, judged on the §7 instrument against a random control at the same
budget:

| candidate | what it is | mean coh σ4 | frac > 0.8 | dominant strike | in credited band | lift over random |
| --- | --- | --- | --- | --- | --- | --- |
| N9 random control | uniform over the novel pool | 0.2997 | 0.0147 | 95° | — | — |
| N1 trace field | six-family rank + persistence, peaks | 0.4047 | 0.0640 | 95° | yes | +0.1543 |
| N4 strike-gated field | N1 × network coherence × azimuth match | 0.3922 | 0.0412 | 5° | no | +0.1198 |
| N6 habitat | two-view co-training propensity | 0.4408 | 0.0633 | 85° | no | +0.1898 |
| N2 ridge C≥2 | N1's rank walked along the ≥2-family network | 0.4991 | 0.2165 | 95° | yes | +0.4159 |
| N3 ridge C≥3 | same on the ≥3-family network (capacity 9,259 of 16,681) | 0.6035 | 0.4197 | 75° | no | +0.7088 |
| **N5 strike ridge** | **N4's score walked along the ≥2-family network** | **0.5350** | **0.2520** | **95°** | **yes** | **+0.4726** |
| *reference: the champion's own cloud* | *37,638 dots, scored 0.2778* | *0.5309* | *0.1585* | *95°* | *yes* | — |

N3 has the largest lift but fails the azimuth condition (75°, twenty degrees off the credited fabric)
and could not fill the budget from the ≥3-family network; N5 is the largest lift inside the band. Its
coherence (0.5350) is within 0.004 of the credited cloud's (0.5309) and its high-coherence fraction is
1.6× the credited cloud's, at 2.3× fewer dots — so the comparison is stated with the density
difference attached rather than as a match.

**R4 — the projection is a probability over a bounded unknown, never a point.** With
`T(S) = κ·471.6·S^0.2284` and `κ ~ U[0.3, 1.3]` (κ = 1 is "as good as this family's field at the same
budget"; the measured spread across the repo's 13 files is κ ≈ 0.1 for `PLACEHOLDER` to ≈ 1.0 for the
champion, and an outside-family PINN file also sits at ≈ 1.0):

| | value |
| --- | --- |
| DTI at κ = 1 | **0.2974** (credit 4,344) |
| DTI at κ = 0.3 | 0.0892 |
| DTI at κ = 1.3 | 0.3866 — the `|G|` cap does not bind anywhere in this prior (it would take κ = 3.24) |
| **P(DTI > 0.2778)** | **0.366** (needs κ ≥ 0.934, i.e. credit ≥ 4,058) |
| **P(DTI > 0.3195)** | **0.226** (needs κ ≥ 1.074, credit ≥ 4,667) |
| **P(DTI > 0.3774)** | **0.031** (needs κ ≥ 1.269, credit ≥ 5,513) |

Re-running the script reproduces the file **bit for bit** (SHA-256 prefix `33b27433` both times,
99,210 bytes, 16,681 px), so the emission is deterministic end to end and the only thing a re-run
changes is the UTC stamp in its name.

**Shipped:** `submission/gems52-r5-novel-n5_strike_ridge-16681px-20261008T220210Z-33b27433-zeros.tif`
— 16,681 px, 99,210 bytes, float32 single band, EPSG:32611, transform identical to
`sample_submission.tif`, values exactly {0, 1}, all 12,279,160 cells finite, no nodata tag, format
gate 0 problems, pattern-unique against 55 priors, minimum distance to a mapped trace 223.6 m,
median 2,360 m. Portal note (≤200 chars) and the exact upload steps are in
`docs/executive-summary.html`.

## 7. The choice this round did **not** make, and what it would have been worth

The arithmetic in §2 point 3 says a core+novel composite — P1's 25,502 exactly-accounted px plus
16,681 novel px — would score `DTI = (t_core + ρ_n·16,681)/19,711` with `t_core ∈ [4,168, 5,223]`:

| t_core | ρ_novel | DTI |
| --- | --- | --- |
| 4,168 | 0.0242 (measured tail) | 0.2319 |
| 5,223 | 0.0242 | 0.2852 |
| 4,168 | 0.1387 (champion rate) | 0.3357 |
| 5,223 | 0.1387 | 0.3890 |

`P(DTI > 0.2778) ≈ 0.77` and `P(DTI > 0.3195) ≈ 0.38` under the same priors — roughly double the
shipped file's chances. **R5 did not ship it.** 63 % of its pixels would be the champion's own, and
the brief's first requirement is a unique submission that is not a copy of a previous one; previous
rounds shipped exactly such composites (`gems52-h57-union-novel-core25517px-arm14804px.tif`,
`gems52-h59-union-core25517px-arm14783px.tif`), so this is a deliberate departure, not an oversight.
The trade is printed here with numbers on both sides so the next session can reverse it knowingly.

There is also an official argument for the unique file that has nothing to do with the brief. Staff,
2026-09-23: "the largest prize pool (Phase 2) will use a test set that is updated by expert review of
all Phase 1 submissions, so **your fault predictions have an impact on final evaluation even if they
are not the most performant in Phase 1**." Re-emitting an accounted core gives experts nothing they
have not already been given twelve times; 16,681 strictly novel, strike-coherent, individually
reasoned candidates are exactly the input Phase 2 asks for. The larger prize rewards the file this
round shipped.

## 8. What R5 measured on the brief's own method (co-training), including the parts that failed

Views as the brief defines them: **A** = potential field and subsurface (bands 1, 3, 4, 5, 13, 15, 16,
17 plus the mag/grav/strain/sub family responses, corroboration and persistence = 14 layers); **B** =
surface (bands 6, 12, 19 plus five LiDAR scarp bands and three radiometric bands, plus the topo/rad
family responses = 15 layers). Band 6 is in B because it is radiometric total count, whatever its tag
says (`knowledge/25` §6). Four whole-block folds of 20 km blocks, a 4 px fold-boundary buffer
(441,795 px), 60,000 positive + 240,000 negative sampled rows, gradient-boosted trees, out-of-fold
propensity over the whole footprint.

* **Skill.** View A mean fold AUC **0.6076** (0.6142 / 0.6532 / 0.5730 / 0.5902); view B **0.6842**
  (fold 0 = 0.6948). Both are weak-to-moderate, and A is weaker — which is what makes the exchange
  asymmetric below.
* **The independence premise holds this round.** Per-block false-positive rate on labelled negatives
  at each view's own top-1 % threshold, over 159 blocks containing both classes: Spearman **0.22757**,
  Pearson 0.10675, max |r| 0.22757 against the 0.60 abandonment threshold → **do not abandon**. R4's
  score-level version of the same test fired at 0.7051. Both numbers are published; the difference is
  the statistic (per-block FP rate at a fixed threshold vs raw score correlation), not the data.
* **The disagreement signal is real but atomised.** A-only (A in its top 1 %, B below its 90th) =
  **43,672 px**, median `depth_to_base_surf` 301.2 m; B-only = 43,799 px, median 287.4 m. The A-only
  population is *not* deeper than the B-only population by any useful margin, so "buried under cover"
  is not confirmed as the A-only signature — it is a hypothesis the numbers do not support strongly.
* **Pseudo-labelling, both readings of "whole segment".** Under the connected-component reading the
  donor-confident ∧ receiver-abstaining cut is **empty in both directions**: 4,992 raw px in 4,531
  components, largest component 5 px, at **1.027×** the count independence predicts (4,862 px) — a
  sprinkling, not segments. Under the whole-20 km-block reading it admits 4,948 px in 4,488 blocks
  (A→B) and 4,691 px in 4,614 blocks (B→A). Both are published
  (`evidence/r5_cotrain.json → pseudo_label_reading`); neither is tuned until something appears.
* **The exchange, and the bias amplification the brief warns about.** Fold 0: A→B moves the receiver's
  AUC 0.6948 → 0.6977 (**+0.0029**); B→A moves it 0.6143 → 0.5896 (**−0.0247**). Co-training the
  weaker view on the stronger view's confident pseudo-labels **hurts it by eight times the benefit the
  other direction gets**. That is the brief's warning confirmed on real bytes, and it is the reason
  the shipped emission is not a co-trained propensity field. Two caveats are attached wherever these
  numbers are quoted: the block-unit pseudo-labels overlap the fold buffer (`leak_free = false`, and
  `apply_pseudo_labels` excludes buffered rows from training, which is a weaker fix than a clean
  protocol), and the OOF-donor protocol has a second-order leak — a pseudo-label at a pixel in fold j
  comes from a donor trained on folds ≠ j, so admitting it into the receiver's fold-k model (k ≠ j)
  trains that model on a quantity derived from fold k's own labels. A strictly leak-free exchange
  needs per-fold donor refits predicting in-split pixels of folds ≠ k; that is written up as the next
  implementation item, not as a result.
* **A-only reasoning for Phase 2.** `docs/downloads/a_only_reasoning_r5.csv`: one row per A-only
  candidate segment of ≥ 3 px — **4,164 candidates, 21,356 px, 48.9 % of the A-only mass** — each with
  its own measured geometry, per-family response percentiles, band values quoted as published against
  the footprint's own distribution, distance to the nearest mapped and SGMC trace, an evidence grade
  (100 strong / 1,510 moderate / 2,554 weak), a reasoning sentence whose every clause is conditional
  on that row's numbers, and five named competing explanations. The 18,123 components of 1–2 px
  (22,316 px) are below review resolution and are accounted for in aggregate in
  `evidence/r5_a_only_reasoning.json` rather than dropped silently. 465 of the reviewed candidates
  carry 1,834 of the emitted dots.

## 9. Limitations, and what would change the answer

1. **No organiser authentication of anything.** The bytes are integrity-pinned to a 23-file SHA-256
   manifest but came from an owner mirror; every score is owner-reported; the board publishes no
   filenames. `|G|`, ρ, the atom credits and every projection inherit that.
2. **`P(win) = 0.366` against the family's own bar is a coin flip weighted slightly against us, and
   0.226 against the brief's stated bar.** The shipped file is not expected to beat 0.2778. It is
   format-valid, unique, reasoned and structurally matched to the only positive signal available; it
   is not a predicted winner, and the site says so in the first line a visitor reads.
3. **The effective `|G|` is the public chunk's.** The chunking is undisclosed by explicit refusal, so
   the ratio between it and the final round's whole-area `|G|` is unknown, and with it the correct
   budget for the round that pays five times as much (§4c, H60-F).
4. **Two runs of identical stage-3 code logged different numbers**, and both saved propensity fields
   carry 620 impossible zeros in the out-of-footprint prefix of row 0. Neither is explained; both are
   bounded; the published stage-3 numbers reproduce exactly from the arrays on disk (`IR-R5-003`).
5. **`8GEMSDOE_Hedge-v2` and `gemsdoe-ens12-adopted` have identical evaluated support and an
   identical reported score**, so the inversions have n = 12 distinct observations, not 13
   (`IR-R5-004`).
6. **What would change the answer, in order of value:** (i) H60-A's §A-gate passing — that would put a
   measured perpendicular-error number behind the only officially confirmed truth population, and is
   worth more than any further tuning of what exists; (ii) an organiser-side receipt for one
   submission, which would turn every ρ in this file from an inversion into a measurement; (iii) the
   whole-area `|G|`, or any bound on the public/private split, which would settle the budget;
   (iv) a leak-free per-fold-donor exchange, which would settle whether the −0.0247 on view A is real
   or protocol.
