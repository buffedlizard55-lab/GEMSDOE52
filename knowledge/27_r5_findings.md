# 27 · Historical R5 analysis — conditional arithmetic, not a causal score explanation

> **Superseded 2026-10-10:** 0.2778 is a team-level public-board value at rank 17 in the saved 2026-10-09 20:18 UTC observation; it is not the public high score and no organizer receipt maps a TIFF hash to it. The locally measured 37,654/44,090 subset relation is not proof of why an organizer score changed. The known-fault mask is pixel-exact, only new-fault truth is scored, and new-fault truth may occur within 300 m of known traces, so removed 100–200 m cells are not known to be score-free. All score-derived algebra below is historical, owner-report-conditioned scenario arithmetic—not hidden-truth measurement or an organizer score explanation. Current account: [`knowledge/49`](49_why_02778_phd_answer.md) and `IR-R5-011`.

The brief asks why the H33-labelled file was reported at 0.2778 and whether a future candidate could improve. The file/score association is owner-reported; no organizer receipt maps a TIFF hash to that value. This historical note does not answer the causal question. `knowledge/49` is the current evidence-classification reference; calculations retained below are conditional or local-only as explicitly labelled.

## 1. The three bars, with their owners

| bar | value | whose | source |
| --- | --- | --- | --- |
| owner-reported reference | **0.2778** | `extradr19`, rank 13 in the 2026-10-08 snapshot; rank 17 in the later 2026-10-09 20:18 UTC observation | dated PUBLIC-LEADERBOARD observations; file↔score pairing remains OWNER-REPORTED, no organizer receipt |
| the brief's stated target | **0.3195** | `DARD`, rank **7**, 16 submissions | same |
| the board top | **0.3774** | `xiaofanhu`, rank 1, 13 submissions | same |

The brief’s 0.3195-as-highest claim was incorrect: the saved 2026-10-09 20:18 UTC public observation records 0.3774 at rank 1, 0.3195 at rank 7, and 0.2778 at rank 17. Those are team-level rows, not file/hash receipts. Any historical cluster or rank narrative describes a dated board snapshot only; it cannot identify a shared geological ceiling, hidden-truth fraction, or what a particular bitmap scored. See `knowledge/49` and `evidence/leaderboard_observation_2026-10-09T201800Z.json`.

## 2. Historical conditional arithmetic (not an established explanation)

The local bitmap set arithmetic is measured on restored bytes; the score associations shown beside it are owner-reported only:

```
A = H33-labelled bitmap  40,199 emitted px, 2,545 exact known-label cells → 37,654 evaluated cells   owner-reported association: 0.2778
B = d2-8-labelled bitmap 46,635 emitted px, same 2,545 known-label cells → 44,090 evaluated cells   owner-reported association: 0.2600
A ⊂ B ;  B \ A = 6,436 px, every one of them 100–200 m from a mapped trace
min distance-to-catalogue inside A = 223.6 m
```

The official formula is `DTI = T / (0.2·(T + S − M) + 0.8·|G|)`. The hidden new-fault set, `T`, and the overlap term `M` are not present in this checkout, and the owner-reported score values are not linked to these local hashes. Therefore the score equations cannot be inverted as observations from these bytes.

`B \ A` is a local 6,436-cell difference at 100–200 m from the known-fault mask. That distance does not determine hidden-truth credit: official staff says new-fault truth may occur within 300 m of a known trace. The former “zero-credit ring”, +6.8% gain, `|G| = 14,088.7`, and 5,223-credit values are withdrawn as measured findings. Any such arithmetic is conditional on unverified file/score mappings and assumptions about hidden truth and `M`; it is not an organizer score explanation.

The exact local atom sizes are useful for byte forensics, but their hidden-truth credit is unknown:

| local atom | pixels | hidden-truth credit |
| --- | ---: | --- |
| `P1 = A ∩ C` | 25,502 | unknown |
| `P2 = A \ C` | 12,136 | unknown |
| `P3 ∪ P4 = B \ A` | 6,436 | unknown |
| `P5 ∪ P6 = E \ B` | 66,142 | unknown |

No selection rule, credit density, random baseline, or causal score improvement follows from these counts alone.

## 3. `|G|` is not recovered from the public board

The earlier `|G| = 14,088.7` point and narrow interval depended on treating owner-reported score labels as exact mappings to local TIFFs and on assigning an unsupported credit to the 100–200 m difference set. Those assumptions are not measurements. The competition’s hidden new-fault labels and organizer receipts are unavailable here, so this local comparison does not recover `|G|`, a truth density, or the score-change mechanism.

## 4. Conditional break-even algebra (sensitivity only; never a score or prediction)

The former threshold table assumed `|G| = 14,088.7`, an unverified scenario value. The table’s algebra is not a forecast; it does not explain 0.2778 or estimate the chance that any future raster will score above it. No “best credit density” is measured from the local byte comparison because hidden-truth credit is unknown.

For a hypothetical known `|G|`, the required density follows `ρ = target·(0.2 + 0.8·|G|/S)`. Since `|G|` is not identified here, any numerical table is conditional and must be read as a sensitivity illustration only. The submission decision must use preregistered HOLDOUT-DTI with its evaluator, withheld-positive count, and confidence interval—not this arithmetic.

## 5. Historical holdout diagnostics are not a public-score calibration

The measurements below compare internal hide-and-recover diagnostics with owner-reported score associations. They do not authenticate the public scores or establish how the hidden new-fault labels behave. The diagnostics remain useful only for their preregistered local holdout purpose:

1. **The hide-and-recover localisation assay is not a public-score calibration.** `knowledge/10` §5 reports
   Spearman(reported score association, simulated DTI) = −0.1045, p = 0.734, n = 13; these are owner-report
   associations, not authenticated score/file pairs. R5 separately measured the champion-family proxy
   field at **0.0003**, uniform random at **0.0275**, and the new six-family trace field at **0.0395**
   (`evidence/r5_budget.json`, `work/r5/r5_assay.json`). These are internal holdout diagnostics on mapped
   catalogue segments, not scores on the hidden new-fault set. The assay excludes a 200 m neighborhood
   of visible catalogue as part of its design; this changes what the local holdout measures and does not
   establish that the competition’s 100–200 m near-catalogue cells are zero-credit.
2. **Feature diagnostics do not provide hidden-truth labels.** The historical 63 point/local-differential and 108 structure-tensor screens compared local set partitions, not known credited and uncredited pixels. Their AUC values cannot be interpreted as credit ranking or evidence about hidden truth.
3. **R5 measured local mask enrichment, not credit.** The six-family corroborated-ridge pool
   (`corr99 ≥ 2`, 653,593 px, 13.4 % of the legal footprint) overlaps the H33-labelled bitmap at
   **1.54×** enrichment. Any P1/P2/P5/P6 “credit tier” comparisons are conditional on the withdrawn
   score inversion; this spatial enrichment measures where the rasters emit, not which emissions
   match hidden truth.

The local H33-labelled bitmap has measurable spatial coherence as a geometric property. The former
“credited cloud” interpretation is not supported without hidden-truth labels and an authenticated score-to-file
receipt. The coherence comparison against mass-matched random rasters is an internal spatial diagnostic,
not evidence that these pixels are credited or geologically correct.

## 6. What R5 shipped, and the four rules that chose it

`scripts/run_r5_novel.py` froze its rules **before** the candidates were built. They are printed in
the script's docstring and in `evidence/r5_novel_emission.json → frozen_rules`; the numbers below are
what came out.

**R1 — strictly novel (at build time).** No pixel emitted by any of the **71**
rasters in the checked inventory (13 rasters listed as scored/owner-labelled *and* every research artifact in
`submission/` and `docs/downloads/`, including the CTD5, H60, H60C and H60D rounds merged from `main`
in parallel with this one; their union is 1,467,623 px), and no pixel within 200 m of
a mapped trace. Measured result: `novel_fraction = 1.0000` against
all 71, and
1.0000 against the 13 scored files separately. The rule was
enforced twice by rebuild rather than argued about. The first build reported 0.8021 because it excluded
only the 13 scored priors — 19.8 % of its pixels had been emitted by this repo's own never-submitted
research artifacts — and the second build reported 0.9582 after `main`'s four parallel rounds landed,
i.e. 4.2 % of the emission had been emitted by another session's artifact hours earlier. Both times the
exclusion set was widened and the file was rebuilt. That is the difference between "unique" as a claim
and unique as a measurement, and it is why `scripts/check_site.py` recomputes novelty from the bytes on
every run instead of reading the receipt.

**R2 — the budget is derived, not tuned.** `S* = 4|G|β/(1−β) = 16,681 px` (§4a).

**R3 — the choice among candidates is made on coherence, not on the assay.** Seven candidates at
S = 16,681, all strictly novel, judged on the §7 instrument against a random control at the same
budget:

| candidate | what it is | mean coh σ4 | frac > 0.8 | dominant strike | in conditional band scenario | lift over random |
| --- | --- | --- | --- | --- | --- | --- |
| N3_ridge_C3 | the same rank walked along the ≥3-family network | 0.6010 | 0.4145 | 75° | no | +0.7016 |
| **N5_strike_ridge** | N4's score walked along the ≥2-family ridge network | **0.5326** | 0.2472 | 95° | yes | +0.4658 |
| N2_ridge_C2 | the same rank walked along the ≥2-family network | 0.4965 | 0.2119 | 95° | yes | +0.3944 |
| N6_habitat | the two-view co-training propensity (contrast) | 0.4394 | 0.0647 | 85° | no | +0.1902 |
| N1_trace_field | six-family rank + persistence, peaks | 0.4041 | 0.0636 | 95° | yes | +0.1538 |
| N4_strike_gated | trace rank × network coherence × credited-azimuth match | 0.3926 | 0.0421 | 5° | no | +0.1207 |
| N9_random_control | uniform random over the strictly-novel pool (the control) | 0.3000 | 0.0140 | 95° | yes | +0.0000 |
| *reference: H33-labelled local bitmap* | *37,638 dots; owner-reported score association 0.2778* | *0.5309* | *0.1585* | *95°* | *conditional only* | — |

N3 has the largest lift but fails the historical azimuth condition (75°, off the hypothesized fabric)
and could only place 9,165 of 16,681 dots from the ≥3-family network; N5 is the largest lift inside the band. Its
coherence (0.5326) is within 0.0018 of the H33-labelled local bitmap's (0.5309) and its high-coherence fraction is
1.6× that bitmap's, at 2.3× fewer dots. This is a geometric comparison, not credit corroboration.

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

The build is deterministic: two runs against the same prior set produced byte-identical files (SHA-256
prefix `33b27433` twice, 99,210 bytes). The shipped file is a *later* build, SHA-256 `d2bfb0f7`,
because the prior set changed underneath it when `main`'s four parallel rounds (CTD5, H60, H60C, H60D)
merged: the same rule, the same candidate, the same budget and the same 16,681 px, with
different pixels exactly where another session had already emitted. Against a fixed prior set the build
reproduces bit for bit.

**Shipped:** `submission/gems52-r5-novel-n5_strike_ridge-16681px-20261008T234033Z-d2bfb0f7-zeros.tif`
— 16,681 px, 99,231 bytes, float32 single band, EPSG:32611, transform identical to
`sample_submission.tif`, values exactly {0, 1}, all 12,279,160 cells finite, no nodata tag, format
gate 0 problems, pattern-unique against 71 build-time priors (later current-inventory support novelty is 0.874408 over 120 rasters), minimum distance to a mapped trace 223.6 m,
median 2,360 m. Portal note (≤200 chars) and the exact upload steps are in
`docs/executive-summary.html`.

## 6.1 The output is not the union of the two views — measured, and what that costs the story

The brief asks for this confirmation explicitly, and `gems52.gates` does not test it (the uniqueness
gate compares against *prior submissions*, a different question). `scripts/run_r5_union_check.py`
compares the shipped emission against every set "the union of the two views" could mean
(`evidence/r5_not_the_union.json`):

| comparison set | px in set | shared with the emission | fraction of the 16,681 emitted | Jaccard |
| --- | --- | --- | --- | --- |
| disagreement union (A-only ∪ B-only) | 87,471 | 333 | **0.0200** | 0.0032 |
| top-S of the pointwise max of the two propensity ranks | 16,681 | 70 | **0.0042** | 0.0021 |
| half from each view's own top-S/2 | 16,662 | 70 | **0.0042** | 0.0021 |
| view A's own top-S | 16,681 | 72 | **0.0043** | 0.0022 |
| view B's own top-S | 16,681 | 59 | **0.0035** | 0.0018 |
| A-only alone | 43,672 | 177 | **0.0106** | 0.0029 |
| B-only alone | 43,799 | 156 | **0.0094** | 0.0026 |

and the Spearman correlation between the emitted pixels' own score and each view's propensity is
**+0.028** (A), **-0.007** (B), **+0.012** (pointwise max) — indistinguishable from zero.

So the confirmation the brief asks for is as strong as it can be, and it has to be read together with
what it implies: **the shipped emission is not a co-training product.** Co-training was built, run and
measured exactly as the brief specifies (§8), and then its ranking lost. The habitat candidate N6 —
the pointwise maximum of the two out-of-fold propensities — has the second-smallest coherence lift of
the seven candidates (+0.1902 against N5's +0.4658), fails the credited-azimuth condition, and
overlaps the emission by 0.3 %. Its propensity field is also the worst of the candidates on the
localisation assay (simDTI 0.0003 against 0.0275 for uniform random), which §5 explains rather than
excuses. The honest summary is: **the brief's method was executed, its independence premise held, its
pseudo-label exchange measurably harmed the weaker view, and its propensity ranking was not selected**
— three findings, all reported, none of them a reason to pretend the shipped file came out of
co-training. What shipped came out of the six-family corroboration detector and the §7 coherence
instrument.

## 6.2 What the disagreement signal did and did not say

The brief's reading is that A-confident/B-abstaining means "buried beneath cover" and
B-confident/A-abstaining means "suspect surface artifacts such as roads or erosion lines". Measured on
the restored bytes (`evidence/r5_cotrain.json → disagreement`):

| stratum | px | median `depth_to_base_surf` | median `det_elev_slope` |
| --- | --- | --- | --- |
| A-only | 43,672 | 301.2 | **3.58** |
| B-only | 43,799 | 287.4 | **4.47** |
| both confident | 482 | 259.8 | 4.55 |

The B-only side behaves as the brief predicts: it sits on ground **25 % steeper** than the A-only side
(4.47 against 3.58, footprint median 3.75), which is where erosion lines, drainage and roads cut
rather than where a buried front would be. The A-only side does **not** behave as the brief predicts:
its median modelled basement depth is 301.2 m against 287.4 m for B-only — a 14 m difference on a field
whose footprint median is 316 m and whose p99 is 3,420 m. **"A-only means deeper burial" is not
supported by these bytes**, and the A-only reasoning CSV is written accordingly: its burial clause is
conditional on each row's own measured depth and says so when the row is shallower than median.

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
  `evidence/r5_a_only_reasoning.json` rather than dropped silently. 463 of the reviewed candidates carry 1830 of the emitted dots.

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
   budget for the round that pays five times as much (§4c, R5-H6).
4. **Two runs of identical stage-3 code logged different numbers**, and both saved propensity fields
   carry 620 impossible zeros in the out-of-footprint prefix of row 0. Neither is explained; both are
   bounded; the published stage-3 numbers reproduce exactly from the arrays on disk (`IR-R5-003`).
5. **`8GEMSDOE_Hedge-v2` and `gemsdoe-ens12-adopted` have identical evaluated support and an
   identical reported score**, so the inversions have n = 12 distinct observations, not 13
   (`IR-R5-004`).
6. **What would change the answer, in order of value:** (i) R5-H1's §A-gate passing — that would put a
   measured perpendicular-error number behind the only officially confirmed truth population, and is
   worth more than any further tuning of what exists; (ii) an organiser-side receipt for one
   submission, which would turn every ρ in this file from an inversion into a measurement; (iii) the
   whole-area `|G|`, or any bound on the public/private split, which would settle the budget;
   (iv) a leak-free per-fold-donor exchange, which would settle whether the −0.0247 on view A is real
   or protocol.
