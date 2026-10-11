# 42 · H69 historical results — co-training holdout and literal lane stop

> **Current evidence correction (2026-10-10):** the historical 0.2778 discussion below is superseded where it infers a causal score change or zero-credit ring. The saved 2026-10-09 20:18 UTC public observation places extradr19 at rank 17; no public row maps a TIFF hash to a score, and the file association remains owner-reported. The 37,654/44,090 local subset and 100–200 m distances do not identify hidden-truth credit. Official staff confirms new-fault truth may lie within 300 m of known traces. All score-derived densities below are conditional model arithmetic, not hidden-truth measurements or an organizer score explanation; see [`knowledge/49`](49_why_02778_phd_answer.md).

Round **H69**, 2026-10-09. Preregistration `knowledge/52_hypotheses_H69_preregistered.md`
(SHA-256 `7bd6e682…`), amendment `knowledge/52b_h69_prereg_amendment_placement.md`. Runner
`scripts/run_h69.py`, which refuses to execute if the pinned preregistration hash moves. Every number
below is read out of `evidence/h69_*.json`, produced from rasters restored and SHA-256 verified this
session (`data/restore_receipt.json`, `ALL_VERIFIED=True`) and a 526-blob prior census re-materialised
and SHA-verified into `work/h69/priors/` (`work/h69/prior_fetch_receipt.json`, `errors=0`, 526 fetched,
524 file-hash matches against the frozen census).

**Disposition:** research download **YES**; local format checks **PASS**; portal acceptance **UNVERIFIED**; submission **NO — literal `DUPLICATE/STOP`**. Competition slots used: **0**.

**Lane result, with the rule boundary made explicit:** the H69 placement passes the informative-prior
saturation-policy diagnostic (near-dot 0.6985; max Spearman 0.0096) but fails the literal all-prior
rule because a universal-coverage probe yields a 1.0000 near-dot fraction. The final literal status is
`DUPLICATE/STOP`; the policy-only pass does not waive it or make this a submission candidate.

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

## 1b · The archived research file, and every local gate measured on it

`gems52-h69-cotrain-basementview-consensus-lanefeasible-37600px-20261009T062239Z.tif` — **147,247 bytes**, SHA-256 `9501c1c88fa1b80ac76b0d2652afb6234c470f8583a2d634dd62fc23c6ae8461`,
**37,600** emitted cells. Three byte-identical copies are served
(`docs/downloads/h69-candidate.tif`, `docs/downloads/gems52-h69-cotrain-basementview-consensus-lanefeasible-37600px-20261009T062239Z.tif`,
`submission/gems52-h69-cotrain-basementview-consensus-lanefeasible-37600px-20261009T062239Z.tif`), all matching that SHA-256.

| gate | result |
|---|---|
| Local format validation (1 band, float32, EPSG:32611, 3,730 × 3,292, pinned transform, matches `sample_submission.tif`) | **PASS**, 0 local problems; portal acceptance unverified |
| Values | exactly {0.0, 1.0} ⊂ [0, 1]; **0 NaN, 0 infinite**, 0 mass outside the valid footprint; 372 distinct decoded patterns checked | **PASS** |
| Equals the literal prior union | False |
| Lane, **saturation policy**, final dots | **PASS** — max near-dot **0.6985** (limit 0.70), max Spearman **0.0096** (limit 0.90) |
| Lane, saturation policy, continuous surface | **PASS** — max Spearman 0.5057 |
| Lane, **literal** rule (probes included), final dots | **DUPLICATE/STOP** — a universal-coverage probe yields 1.0000; literal stop controls |
| Not the union of the two views | **PASS** — min 46,228 differing cells per fold |
| ≥ 20 % exact support novelty vs the all-prior union | **FAILED diagnostic**, reported not waived (§6.4) |
| S1 sufficiency | **FAIL** — View A mean 0.5281, min fold 0.4896 |
| HOLDOUT-DTI candidate minus `single_B` | **−0.101474** [−0.123610, −0.080051] — the promotion criterion fails |
| **Disposition** | Research download **YES** · local format **PASS** · portal acceptance **UNVERIFIED** · submission **NO — DUPLICATE/STOP** · slots used **0** |

The artifact is retained for research review only; no submission name, paste-ready note, or upload steps
are provided here. No organizer-confirmed submission receipt exists.

**Conditional scenario arithmetic only (never a score or forecast)** for the archived novel-only file,
using `t_core = 0`, assumed `|G|` values, and an assumed `ρ_novel` prior over [0.02795, 0.13871].
These inputs are not recovered hidden truth or measured credit:

| Assumed \|G\| scenario | Conditional P(DTI > 0.2778) | Conditional P(DTI > 0.3195) | Conditional P(DTI > 0.3774) | scenario mean | worst | best |
|---|---:|---:|---:|---:|---:|---:|
| 5,949.3 px | 0.435 | 0.311 | 0.143 | 0.2552 | 0.0856 | 0.4247 |
| 9,230.7 px | 0.261 | 0.112 | 0.000 | 0.2102 | 0.0705 | 0.3499 |
| 12,512.1 px | 0.087 | 0.000 | 0.000 | 0.1787 | 0.0600 | 0.2975 |

**Withdrawn scenario, NOT SHIPPED:** the 25,502-cell `P1 = A ∩ C` support overlap plus 11,200
novel-view cells was evaluated only by conditional inversion of owner-reported score associations,
assumed `|G|`, and a sparse-emission model. The listed probabilities and DTI values are scenario outputs,
not measured hidden-truth credit, not an estimate of organizer scoring, and not evidence of the cost or
benefit of the uniqueness rule. No such file was written, served, or offered.

The informative-prior dots-phase max rank correlation is **0.0096** under the saturation-policy
calculation. This is a local registry comparison only. It does not establish eligibility under the literal
all-prior rule, hidden-truth novelty, or credit density; the universal-coverage probe still makes the
literal result `DUPLICATE/STOP`.

### Post-merge re-verification against the enlarged registry

`origin/main` gained four more rounds (H65b, H65halo, H66, H67) while this branch was open, so the whole
gate battery was re-run against the enlarged registry rather than trusted from the pre-merge receipt:
**572 `.tif` files found, 570 aligned single-band
priors used, 2 excluded as not on the competition grid,
376 distinct decoded patterns, 15 universal-coverage
probes, 555 informative, 0 errors.**

The informative-prior policy result remained **PASS** (max near-dot **0.6985**, max Spearman **0.0096**).
The literal result remains **DUPLICATE/STOP** because universal-coverage probes are included in that rule.
The policy-only result is not a submission clearance.

The placement itself was computed against the pre-merge census (343 informative priors, frozen in
`evidence/ctd5_prior_inventory.json` + `submission/` + `data/scored` + `data/reference` at that time), and
the gate was then re-measured against 555. Both numbers are published because
they are different registries and pretending otherwise would hide the only thing that could have broken
this round after the fact.

### Packaging

The artefact is written by `gems52.submission_writer.write_submission`, the shared fail-closed packager the
brief says to reuse, not by a hand-rolled ZIP. It delegates to the same `grid.write_geotiff`, so adopting it
changed **nothing** about the TIFF: SHA-256 `9501c1c88fa1b80ac76b0d2652afb6234c470f8583a2d634dd62fc23c6ae8461` before and after, asserted in
`scripts/run_h69.py` rather than assumed. What it adds is the name/note 140-character enforcement, the
no-positive-mass-outside-footprint check, the single-TIFF ZIP roundtrip assertion, and the receipt at
`submission/gems52-h69-cotrain-basementview-consensus-lanefeasible-37600px-20261009T062239Z.json` carrying
`approved_for_weekly_slot=False` and
`submission_slots_used=0`. ZIP SHA-256
`65ccdf8d5f593f588ac48f4614fc86aee70409c38dc84b4fc52b2bb0de44137e`. `--stamp` lets an unchanged emission reproduce its published filename
byte-for-byte instead of minting a second identical artefact.

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

### 2.3 The disagreement arm is below uniform random on this holdout instrument

0.036473 against `random` 0.072032 and `single_A` 0.071893. View A alone is indistinguishable from
uniform random on this instrument (0.0719 vs 0.0720, paired CI on the difference spans zero at
−0.000139 ± 0.012), and selecting where View A is confident while View B abstains is *worse* than
selecting at random. H61, H63, H64 and H69 show the same direction on their recorded holdout runs.
This does not establish organizer-score behavior or refute the method universally; it indicates the
registered discovery premise is not supported by these internal measurements. View-A sufficiency at
chance is consistent with the weak disagreement result.

## 3 · Placement diagnostics — informative-prior policy pass does not clear the literal stop

H69 compared three placement constructions. The recorded greedy and per-prior quota results are
engineering diagnostics over the 343 informative priors in the frozen pre-merge census; the later gate
used a larger registry. The consensus-restricted placement attained 0.6985 maximum directed 3 px
near-dot share and 0.0096 maximum Spearman under the **informative-prior saturation policy**. That is a
policy diagnostic, not the literal lane verdict.

The literal all-prior check includes universal-coverage probes. At least one such probe has a directed
3 px near-dot fraction of 1.0000, so the candidate is **`DUPLICATE/STOP` under the literal rule**. Do not
call H69 lane-feasible or submit-eligible based on the informative-only result. The local placement
arithmetic explains how the policy-only numbers were achieved; it does not reverse the stop or establish
any score/credit claim.

The registry census changed during this work and the files/probe classes differed between frozen
placement and later gate runs. Those counts are retained as provenance, not combined as though they were
one unchanged registry. Exact support novelty against the union of informative-prior 3 px halos was also
0 because the union covered the legal set in the measured census; that is a registry-level diagnostic,
not proof that a candidate has no hidden-truth novelty.

## 4 · Why the local-overlap recombination was withdrawn

Preregistration considered `P1 = A ∩ C`, a 25,502-cell local support overlap, alongside novel-view
cells. The overlap is a raster relationship; its hidden-truth credit is not directly observed. Previous
score inversion assigned it conditional credit using owner-reported score associations, an assumed `|G|`,
and a sparse-emission approximation. Those assumptions do not make the credit bound organizer-confirmed
or measured.

The recombination was withdrawn before placement. Independently, H60C's prior uniqueness correction
(`IR-H61-007`, `IR-UNQ-001`) means historical overlap with previous submissions is not a promotion path.
Any associated `P(DTI > threshold)` values are scenario arithmetic only, are NOT SHIPPED, and are not
submission candidates. The archived H69 novel-only TIFF is not submit-eligible because its literal lane
status is `DUPLICATE/STOP` and its S1/holdout promotion gates fail.

## 5 · Local evidence about the reported 0.2778 — no causal conclusion

The saved official public-board observation at 2026-10-09 20:18 UTC lists `extradr19` at rank 17 with 0.2778; it lists 0.3774 at rank 1. This is a team-level PUBLIC-LEADERBOARD observation, not an organizer receipt or file/hash mapping. The 0.2778 association with an H33-labelled TIFF remains OWNER-REPORTED.

Local bytes show that a 37,654-cell H33-labelled bitmap is a strict subset of a separate 44,090-cell bitmap associated by an owner report with 0.2600: 6,436 cells are removed and none added. The removed cells are 100–200 m from the provided known-fault mask. These are byte/spatial facts only. The official known-fault mask is pixel-exact; only new-fault truth is scored; new-fault truth may occur within 300 m of known traces. Thus the removed cells' hidden-truth credit is unknown. The subset relation does not establish that either file received its reported value or explain why an organizer score changed.

Any prior inversion of the two reported numbers is conditional on their owner-reported mapping, the sparse-emission approximation, and an assumed credit for the removed pixels. The zero-credit case is one scenario, not a measurement. It is not used here as a score explanation. See [`knowledge/49`](49_why_02778_phd_answer.md) and `IR-R5-011` for current evidence classes.

Whether a future submission can exceed 0.2778 or 0.3195 is unknown. H69's HOLDOUT-DTI values are internal measurements under the named hide-and-recover evaluator, not a public-board predictor; no conversion or projection is claimed.

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
8. **`ρ_novel` is a scenario prior, not a measurement.** Every projection integrates over
   `[0.0279, 0.1387]`, an assumption derived from owner-reported score associations. No instrument here
   certifies hidden-truth credit for the novel mass or where it lies within that interval.
9. **No submission slot was used.** The literal `DUPLICATE/STOP` is terminal for this artifact; no override or upload procedure is provided. Portal acceptance is unverified.
10. **ComCat is not bulk-downloadable from this sandbox**, so the seismicity channels are the organiser's
    own bands 10 and 16 rather than a fresh earthquake catalogue.

## 7 · Archived evidence and provenance

The historical artifacts are reviewable in `evidence/h69_*.json`, with the method and source provenance
in `docs/h69.html` and `docs/h69-sources.html`. The scripts remain in the repository as historical
provenance, but this note does not authorize an experiment rerun, candidate rebuild, new run-card, or
submission. No command sequence is provided because H69 is terminal under the literal `DUPLICATE/STOP`.
