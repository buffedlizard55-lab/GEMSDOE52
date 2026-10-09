# 42 · H69 results and limits — the lane measured a fourth time, and the first lane-feasible placement

Round **H69**, 2026-10-09. Preregistration `knowledge/52_hypotheses_H69_preregistered.md`
(SHA-256 `7bd6e682…`), amendment `knowledge/52b_h69_prereg_amendment_placement.md`. Runner
`scripts/run_h69.py`, which refuses to execute if the pinned preregistration hash moves. Every number
below is read out of `evidence/h69_*.json`, produced from rasters restored and SHA-256 verified this
session (`data/restore_receipt.json`, `ALL_VERIFIED=True`) and a 526-blob prior census re-materialised
and SHA-verified into `work/h69/priors/` (`work/h69/prior_fetch_receipt.json`, `errors=0`, 526 fetched,
524 file-hash matches against the frozen census).

**Verdict: `negative`. Download YES · the portal will accept this file's format YES · spend a weekly
submission slot NO. Competition slots used: 0.**

**The one thing that is new and true:** this is the **first file in this repository that satisfies the
brief's lane rule** — max directed 3 px near-dot share 0.6985 against a limit of 0.70, and max rank
correlation 0.0096 against a limit of 0.90, verified over 566 aligned registry rasters with 0 errors.
H63 measured 0.8188 and H64 0.888 and both shipped files labelled DUPLICATE. The lever that made it
possible is in §3, and its cost is quantified in §1b.

## 1 · Headline results

| quantity | value | receipt |
|---|---:|---|
| withheld positive pixels | 60,894 | `evidence/h69_holdout.json` |
| HOLDOUT-DTI `single_A` | 0.071893 [0.058418, 0.085832] | same |
| HOLDOUT-DTI `single_B` | **0.137947** [0.117079, 0.158755] | same |
| HOLDOUT-DTI `union_max` | 0.125726 [0.105934, 0.144232] | same |
| HOLDOUT-DTI `disagreement_pre` | 0.036473 [0.027471, 0.045996] | same |
| HOLDOUT-DTI `disagreement_post` | **0.036473** [0.027471, 0.045996] | same |
| HOLDOUT-DTI `random` | 0.072032 [0.063558, 0.080098] | same |
| paired candidate − `single_B` | **−0.101474** [−0.123610, −0.080051] | same |
| S1 View A out-of-quadrant AUC | mean **0.528121**, min fold 0.489598 → **FAIL** | `evidence/h69_s1.json` |
| S1 View B out-of-quadrant AUC | mean 0.662483, min fold 0.620992 | same |
| S2 independence max \|ρ\| | 0.227116 over 2,283 blocks (abandon at 0.60) → exchange allowed | `evidence/h69_independence.json` |
| pseudo-labels that survived the whole-segment rule | **0 in all four folds** | same |
| leakage canary, worst single channel | 0.622413 (`b_ext_rad_contrast_unverified`) vs alarm 0.90 → clean | `evidence/h69_canary.json` |
| A-only discovery set | 63,328 px in 5,686 segments; 2,348 segments ≥ 3 px carry written reasoning | `evidence/h69_a_only.json` |

All six arms filled their 9,400-dot-per-fold budget at 3 px separation, so the comparison is at matched
mass (`all_arms_filled: true`).

## 1b · The shipped file, and every gate measured on it

`gems52-h69-cotrain-basementview-consensus-lanefeasible-37600px-20261009T062239Z.tif` — **147,247 bytes**, SHA-256 `9501c1c88fa1b80ac76b0d2652afb6234c470f8583a2d634dd62fc23c6ae8461`,
**37,600** emitted cells. Three byte-identical copies are served
(`docs/downloads/h69-candidate.tif`, `docs/downloads/gems52-h69-cotrain-basementview-consensus-lanefeasible-37600px-20261009T062239Z.tif`,
`submission/gems52-h69-cotrain-basementview-consensus-lanefeasible-37600px-20261009T062239Z.tif`), all matching that SHA-256.

| gate | result |
|---|---|
| Format (1 band, float32, EPSG:32611, 3,730 × 3,292, pinned transform, matches `sample_submission.tif`) | **PASS**, 0 problems |
| Values | exactly {0.0, 1.0} ⊂ [0, 1]; **0 NaN, 0 infinite**, 0 mass outside the valid footprint |
| Decoded-pattern uniqueness over 566 aligned priors (372 distinct decoded patterns, 0 errors) | **PASS** |
| Equals the literal prior union | False |
| Lane, **saturation policy**, final dots | **PASS** — max near-dot **0.6985** (limit 0.70), max Spearman **0.0096** (limit 0.90) |
| Lane, saturation policy, continuous surface | **PASS** — max Spearman 0.5057 |
| Lane, **literal** rule (probes included), final dots | DUPLICATE/STOP — one universal-coverage probe at 1.0000, which is a property of that raster (its 3 px halo covers ≥ 95 % of the legal set) and not of this candidate; reported, not waived |
| Not the union of the two views | **PASS** — min 46,228 differing cells per fold |
| ≥ 20 % exact support novelty vs the all-prior union | **FAILED diagnostic**, reported not waived (§6.4) |
| S1 sufficiency | **FAIL** — View A mean 0.5281, min fold 0.4896 |
| HOLDOUT-DTI beats `single_B` | **FAIL** — -0.101474 [-0.123610, -0.080051] |
| **Verdict** | **`negative`** · download **YES** · portal will accept the format **YES** · spend a weekly slot **NO** · slots used **0** |

Submission name (79 chars) and note (127 chars, complete, never
truncated mid-word) are in `submission/gems52-h69-cotrain-basementview-consensus-lanefeasible-37600px-20261009T062239Z-submission-name.txt` and `…-note.txt`.

**Projection (never a score)** for the shipped novel-only file, `t_core = 0` and
ρ_novel ~ U[0.02795, 0.13871] at `S = 37,600`:

| \|G\| | P(DTI > 0.2778) | P(DTI > 0.3195) | P(DTI > 0.3774) | mean | worst | best |
|---|---:|---:|---:|---:|---:|---:|
| 5,949.3 px | 0.435 | 0.311 | 0.143 | 0.2552 | 0.0856 | 0.4247 |
| 9,230.7 px | 0.261 | 0.112 | 0.000 | 0.2102 | 0.0705 | 0.3499 |
| 12,512.1 px | 0.087 | 0.000 | 0.000 | 0.1787 | 0.0600 | 0.2975 |

**Counterfactual, NOT SHIPPED** (the withdrawn `P1 = A ∩ C` core of 25,502 px + 11,200 novel px,
`S = 36,702`): P(DTI > 0.2778) = 0.684 at `|G| = 5,949.3` and
0.791 at `|G| = 12,512.1`, mean DTI 0.3006 and
0.3021, with `t_core` re-solved at each `|G|` from the reported scores of the nested
family. That is roughly **0.05–0.09 of mean DTI and 0.25–0.5 of P(win) more than the shipped file**, and
it is the measured price of the uniqueness rule. No such file was written, served or offered.

The single most striking number in the round is the dots-phase rank correlation: **0.0096**
against a limit of 0.90. The shipped emission is essentially *orthogonal* to all 372 distinct published
prediction patterns in the family. That is exactly what the lane rule asks for, and exactly why its credit
density cannot be certified: it is not standing where anything that has ever scored is standing.

## 2 · The three things this round actually established

### 2.1 Rebuilding View A as basement-surface differential geometry did **not** rescue sufficiency

View A this round was 18 channels and none of them a raw band level used the way H61 used it:
`|∇|` of band 15 (depth to basement) at σ = 2, 4, 8 px, `|∇²|` of band 15 at σ = 3, a
difference-of-Gaussians band-pass of the isostatic anomaly (σ = 8 px minus σ = 40 px, i.e. roughly
800 m – 4 km), its absolute value, the `|cos ∠|` between ∇(isostatic gravity) and ∇(RTP magnetics),
the conductivity edge, the geodetic strain invariant and dilatation, and the organiser's own seismic
bands 10 and 16. Out-of-quadrant AUC against the held-out truth: **0.5209, 0.6022, 0.4896, 0.4998**,
mean **0.5281**. For comparison, on the identical committed splitter: H61 0.5163, H63 0.5362,
H64 0.5230. The improvement is inside the run-to-run spread of a method that does not work.

**Retraction, recorded because it was measured and then thrown away.** An early version of this round
fitted the sufficiency screen on `holdout.make_folds(mode="block")` with prevalence-thinned truth and
reported View A mean AUC **0.6636**. That number is **not comparable to anything in this repository**
and must not be quoted: it used a different splitter, a different truth definition and a different
negative pool from the committed instrument. The committed instrument is `spatial.folds` (label-blind
quadrants, `buffer_px = 80`), positives = `fold["truth"] & fold["region"]`, negatives =
`region & ~catalogue & distance-to-catalogue > 5 px`, and it gives 0.5281. The 0.6636 reading is
recorded here so that nobody resurrects it.

### 2.2 The committed whole-segment pseudo-label rule produces **zero** labels with these views

`spatial.whole_pseudo_segments` requires a candidate component to be ≥ 5 px, whole, entirely inside the
fold's training domain, entirely inside one 50 × 50 block, with donor percentile ≥ 0.95 and receiver
percentile inside [0.35, 0.65]. Across four folds it returned **0 pixels in both directions**. That is
why `disagreement_post` is bit-identical to `disagreement_pre` (both 0.036473, and the paired
difference has a degenerate CI of exactly [0, 0]): there was no exchange to be after. This is the same
class of failure as `IR-H58-002` (22 of 37,654 nodes emitted — support-capacity failure), now measured
at exactly zero. **The co-training mechanism cannot be executed as specified on this data with these
views**, which is a stronger statement than "it was executed and did not help".

### 2.3 The disagreement arm is below uniform random for the fourth consecutive round

0.036473 against `random` 0.072032 and `single_A` 0.071893. View A alone is indistinguishable from
uniform random on this instrument (0.0719 vs 0.0720, paired CI on the difference spans zero at
−0.000139 ± 0.012), and selecting where View A is confident while View B abstains is *worse* than
selecting at random. Rounds H61, H63, H64 and H69 agree. The Blum–Mitchell discovery premise — that
the confident/abstaining disagreement class is enriched for the target — is refuted on this data four
times over, and the reason is visible in S1: a view at chance cannot produce a *confident* tail that
means anything.

## 3 · The one genuinely new engineering result: the lane rule IS satisfiable, and here is the lever

Every previous round placed first and checked the lane afterwards, and every one of them shipped a file
labelled DUPLICATE (H63 max informative near-dot 0.8188, H64 0.888). H69 measured three constructions
and only the third works. All three numbers are in `evidence/h69_placement.json`.

**(a) Unconstrained greedy — the baseline.** 37,600 dots placed in field-rank order with hard-core 3 px
spacing over the 4,859,987 px legal set. Worst informative near-dot **36,149 / 37,600 = 0.9614**
(`509be169fe6253f94bf8b7323398e1b80e972c96.tif`), with **84 of 343** informative priors above the
0.70 limit. So a field ranked by this repository's habitat signal puts 96 % of its mass within 3 px of a
single published raster. That is the lane rule working as intended, not a threshold artefact.

**(b) Per-prior quota, iterated to a fixed point — does not converge.** Setting every offender's quota to
`floor(0.6985·S)` and re-placing gives:

| quota | dots placed | worst near-dot | achieved share | allowed at that budget |
|---:|---:|---:|---:|---:|
| 24,500 | 32,871 | 24,500 | 0.7453 | 22,960 |
| 22,960 | 30,864 | 22,960 | 0.7439 | 21,558 |
| 21,558 | 29,069 | 21,558 | 0.7416 | 20,304 |

`S/quota` is structurally ≈ 1.34, so the achieved share is pinned near **0.745 at every budget**.
Tightening the quota shrinks the file and the violation together. A quota computed against a *target*
budget is also simply the wrong denominator: at quota 26,263 only 35,149 dots were placeable, an
achieved share of **0.7472** — a violation created by the cap's own arithmetic.

**(c) Excluding the offenders' halos — not available at all.** The union of the 84 offenders' 3 px halos
leaves **361 px** of the 4,859,987 px legal set. Exclusion cannot fund a budget.

**(d) The lever that works: restrict the pool to pixels of low cross-family consensus.** `consensus(x)` is
the number of distinct decoded prior patterns whose 3 px halo covers `x` (H69-2). Over the legal set it
runs 0 → 276 with mean 72.7. Restricting the pool to `consensus ≤ c` and placing under the same quota:

| c | pool px | dots placed | worst near-dot | share | allowed | feasible |
|---:|---:|---:|---:|---:|---:|:--|
| 160 | 4,339,239 | 36,193 | 26,263 | 0.7256 | 25,280 | no |
| 120 | 3,994,592 | 36,088 | 26,263 | 0.7277 | 25,207 | no |
| 100 | 3,819,056 | 36,403 | 26,263 | 0.7215 | 25,427 | no |
| 80 | 3,460,886 | 36,987 | 26,263 | 0.7101 | 25,835 | no |
| **60** | **2,741,649** | **37,600** | **26,263** | **0.6985** | **26,263** | **YES** |

`c = 60` fills the whole 37,600-dot budget and lands at **0.6985**, inside the brief's literal 0.70, and
that was then re-verified by exact measurement against **all 343 informative priors**
(`evidence/h69_lane_dots.json`). Lower thresholds (50, 40, 30, 25, 22, 20) were not needed; the search
takes the *largest* feasible threshold so the ranking field keeps as much of its signal as the lane
allows.

The reading matters more than the number. The lane rule is not unsatisfiable because of
universal-coverage probes, which was H61's diagnosis (`IR-H61-005`). It is unsatisfiable **for any
emission ranked by the family's own habitat signal**, because 84 informative priors agree with that
signal closely enough to cover 96 % of its top mass. What makes an emission lane-legal is ranking it by
something the family did *not* agree on — here, deliberately moving 30 % of the mass to pixels that at
most 60 of 356 published rasters cover. **The lane rule is a novelty constraint, and this round is the
first to pay its price explicitly instead of failing it.**

Registry census measured this session (`work/h69/probe.json`, reproduced by `scripts/h69_probe.py`):
568 prior paths, **372 distinct decoded patterns**, of which 356 are aligned single-band rasters on the
competition grid, **13 universal-coverage probes** (3 px halo covering ≥ 95 % of the legal set) and
**343 informative**. The probe count differs from H64's 35 / 511 and H63's 14 / 531; the classification
rule is identical and the difference is the prior set each round assembled (§6.3).

## 4 · Why the credited core was pre-registered and then withdrawn

Prereg §4 pre-registered an emission built from `P1 = A ∩ C`, the double-corroborated credited core,
25,502 px inside the legal set, whose credit is bounded *exactly* by the organiser's own reported
scores: `t(P1) ∈ [T(A)+T(C)−T(E), T(A)]`. That is the only mass in this repository with an exact credit
bound, and the arithmetic is favourable — the withdrawn design would have projected
`P(DTI > 0.2778)` of roughly 0.83–1.00 across the measured `|G|` bracket.

It was withdrawn before placement ran, because `README.md`'s H60C correction and `IR-H61-007` /
`IR-UNQ-001` had already adjudicated exactly this object:

> **H60C is NOT a unique submission.** Its 35,185 emitted cells are 80.4 % inside the support of prior
> submissions (73.3 % inside `h33-2-b2` alone) … it **does not satisfy "unique, not a copy of a previous
> submission."** Do not present it as the unique submission.

The pre-registered core+novel file would have sat at a near-dot fraction of ≈ 0.695 against the
champion — inside the literal 0.70 threshold, but the same object as the one already corrected, sized
to pass by 0.005. That is re-tuning a negative result into a positive, which the working agreement
forbids. `knowledge/52b` records the withdrawal; the counterfactual projection is still computed and
published in `evidence/h69_run_card.json` under
`projection.counterfactual_recombination_NOT_SHIPPED`, labelled as analysis and not as a candidate.

The consequence is stated plainly: **withdrawing the core removes the only mass whose credit is known,
so the shipped file's credit density is unknown and bounded only by the prior [0.0279, 0.1387].** At
`S = 37,600` the break-even density needed to match the reported champion is 0.0907 at
`|G| = 5,949.3` and 0.1295 at `|G| = 12,512.1`. The expected verdict for a novel-only file was
therefore DOWNLOAD YES / SUBMIT NO **before the number was known**, and `knowledge/52b` says so.

## 5 · Why the reported champion scored 0.2778, and whether it can be beaten

Re-derived from the restored bytes this session, not copied (`work/h69/probe.py`,
`evidence/h61_forensics.json`):

* The reported-0.2778 file `h33-2-b2` (37,654 px) is a **strict subset** of the reported-0.2600 file
  (44,090 px), which is a strict subset of the reported-0.1922 parent field (121,131 px). The champion
  added **zero** pixels and deleted 6,436, every one of them between 100 m and 200 m of a mapped trace;
  its own nearest dot is 223.6 m away.
* For a binary emission whose dots are separated by more than the kernel support, `M = T` and the metric
  collapses to `DTI = T / (0.2·S + 0.8·|G|)`. Deleting mass that earns no credit removes denominator and
  no numerator. **The single move that separates 0.2600 from 0.2778 is precision, not detection.**
* The champion's credit density is 0.0907 at `|G| = 5,949.3` and 0.1387 at `|G| = 14,088.7`, against
  0.0279 for uniform random over the legal set — 3.2× to 5.0× random.
* Its mass is concentrated: `P1 = A ∩ C` is 25,517 px carrying credit density 0.163–0.205, while the
  ≤ 200 m corridor atoms carry **exactly zero**.
* `|G|` is an **interval [5,949.3, 12,512.1] px**, not a point. The often-quoted 14,088.7 requires the
  champion's deleted 6,436 px to earn exactly zero credit; 25 credit of ring income moves it to 12,333.

**Can it be beaten?** Two routes, and only two:

1. **Recombination of existing public mass.** This is the route with an exact credit bound, and the
   projection says it clears 0.2778 across the whole `|G|` bracket. It is not available: it is a
   duplicate by construction (§4).
2. **A detector above 0.0907–0.1295 credit density on *novel* mass.** No instrument in this repository
   can certify that. The hide-and-recover simulator anti-ranks the board (ρ = −0.1045, p = 0.734,
   n = 13; the champion ranks 13th of 13 locally and 1st publicly), and the revealed-preference
   instrument is a similarity statistic to one prior file. This round's own novel field is ranked by a
   view at chance and a view at 0.66 habitat AUC, and habitat is not credit (`knowledge/10` §6: 63 point
   features and 108 structure-tensor features, best AUC(P1 vs P2) 0.5453).

The top of the board at 0.3774 needs `T ≈ 6,620` at `S = 37,654` and `|G| = 12,512` (density 0.176) or
`T ≈ 4,638` at `|G| = 5,949` (density 0.123) — i.e. a detector better than anything this family has
published. **The honest conclusion is that 0.2778 is beatable in arithmetic and not beatable with any
detector this repository can validate, and that the only un-run idea whose target population the
organiser has confirmed exists is R5-H1, the trace-correction corridor** (`knowledge/33`, frozen §A-gate,
never executed). It is still rank 1 and still open.

## 6 · Limits, discrepancies and irregularities

1. **No organiser receipt exists for this round.** Nothing here is ORGANIZER-CONFIRMED. The 0.2778 /
   0.3195 / 0.3774 figures are owner-reported or read off the public leaderboard page; the board
   publishes no filename, so file-to-score pairing is owner-reported. Only 3 of 13 owner-reported scores
   hash-link to bytes held, and the champion's token `e5eb6e7e` matches none of six hash conventions of
   the file held (`IR-H61-004`).
2. **The instrument control did not reproduce.** The preregistration required `single_B` to reproduce
   0.1745172876 to |Δ| ≤ 0.001. It measured 0.137947 — the clause is unsatisfiable for a round that
   deliberately changes View B's channel set, and it is reported as FAILED rather than hidden. The
   model-free control that *can* reproduce across channel changes is the `random` arm: 0.072032 here
   against 0.080426 in H64, |Δ| = 0.0084, also outside 0.001. The residual difference is the `eligible`
   mask: the committed rounds use `structural.FeatureStore.valid` from `work/r2/features`, which is
   git-ignored and absent in a fresh sandbox, so this round used the all-19-bands-finite ∩
   sample-submission-finite footprint (5,164,300 px) and withheld 60,894 positives against H64's 53,186.
   **Within-round paired comparisons are exact** (same folds, same budget, same masks for every arm);
   **across-round level comparisons are approximate.**
3. **Probe/informative counts keep moving**: H63 14 probes / 531 informative, H64 35 / 511, H69 15 / 551 at the gate and 13 / 343 at the probe
   over 356 aligned distinct patterns (372 distinct decoded patterns were seen, 16 of them not on the
   competition grid or empty). The classification rule is identical
   (`gates.registry_coverage ≥ 0.95`); what moves is the prior set each round assembled. H69's set is the
   frozen 526-blob census plus `submission/`, `data/scored/` and `data/reference/`, de-duplicated by
   decoded SHA-256. The cause of the earlier discrepancies is still not resolved and is recorded rather
   than explained away.
4. **Exact support novelty is impossible on this registry.** `work/h69/probe.py` measured the union of all
   informative priors' 3 px halos covering **100 %** of the 4,859,987 px legal set
   (`novel_pool_exactly_novel_vs_all_informative = 0`). The ≥ 20 % support-novelty diagnostic therefore
   fails for *every* nonempty candidate and is reported as a failed diagnostic, never silently waived.
5. **Band 6's own metadata contradicts its bytes.** The file says "Tilt angle or total curvature —
   magnetic field derivative for edge detection"; the bytes rank-match external radiometric total count at
   ρ = 0.99995 and the tilt angle at ρ = 0.0175. It is treated as radiometric and placed in View B.
   Flagged, not silently corrected. This session re-measured the external GeoDAWN radiometric raster's
   four bands against band 6 (ρ = 0.88616, 0.91294, 0.71734, **0.99995**) and identified band 4 as the
   total count; that file carries **no band tags at all**, so the other three bands are averaged into one
   contrast channel whose identity is UNVERIFIED.
6. **The A-only geological reasoning is measured context plus a template mechanism**, not field-verified
   geology. Each row names the non-fault process that could mimic it (a lithologic contact or a basin axis
   with a density and magnetisation contrast and no relief). With S1 at 0.5281 the class is
   noise-dominated and is reported as a discovery signal, never promoted.
7. **The hide-and-recover instrument withholds ~1.2 % of the footprint** against an estimated true
   prevalence of 0.12–0.25 %, and its ranking of the board is ρ = −0.1045. HOLDOUT-DTI is an instrument
   reading, never a forecast.
8. **`ρ_novel` is a prior, not a measurement.** Every projection integrates over
   `[0.0279, 0.1387]` — the two credit densities that are actually measured. Nothing here certifies where
   inside that interval this round's novel mass falls.
9. **No submission slot was used and none can be used from this sandbox**: the portal is login-walled and
   `drivendata.org` is not reachable from here.
10. **ComCat is not bulk-downloadable from this sandbox**, so the seismicity channels are the organiser's
    own bands 10 and 16 rather than a fresh earthquake catalogue.

## 7 · Reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-r2.txt
bash scripts/download_competition_data.sh                 # restores data/, SHA-256 verified
.venv/bin/python scripts/prepare_data.py                  # re-derives evidence/grid.json
.venv/bin/python scripts/fetch_prior_inventory.py \
    --out work/h69/priors --receipt work/h69/prior_fetch_receipt.json
.venv/bin/python work/h69/probe.py                        # legal set, core, census, lane arithmetic
.venv/bin/python scripts/run_h69.py --stage features
.venv/bin/python scripts/run_h69.py --stage lane
.venv/bin/python scripts/run_h69.py --stage place
.venv/bin/python scripts/run_h69.py --stage gates
.venv/bin/python scripts/publish_h69_site.py
```

`requirements-r2.txt` pins numpy 2.2.6 / scipy 1.15.3 / scikit-learn 1.7.2 / rasterio 1.4.3 and this
round ran on exactly those versions.
