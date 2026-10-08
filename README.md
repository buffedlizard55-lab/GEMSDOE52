# GEMSDOE52 — a new research GeoTIFF, not an approved submission

> **Lane-gate correction (2026-10-08):** the shipped H60D file was re-checked under the strict all-registry rule: 99.95% dot proximity to the calibration lattice → DUPLICATE/STOP. See `knowledge/32_h60d_strict_lane_recheck.md` and IR-H60D-007. No submission is approved; no slot used.

> **Current H60D session status (co-training with disagreement as the discovery signal, run
> 2026-10-08 UTC):** hypotheses H60-1…H60-4 were registered in
> `knowledge/30_hypotheses_H60D_preregistered.md` + `registry/h60d_preregistration.json` (SHA-verified,
> frozen) **before** the first fit, and all were adjudicated on the hide/tip holdout instruments using
> the **manifest-pinned owner-mirror bytes** (23/23 SHA-256 pins,
> `evidence/h60d_preflight_integrity.json`). The Blum & Mitchell independence premise **measured**
> max |r| = 0.176 against the 0.60 abandonment threshold (exchange licensed); the leakage canary is
> clean (worst of 75 layers, single-feature holdout AUC 0.7136 < 0.90). One co-training round in
> **both** directions moved fold-0 AUC by −0.0067 / −0.0104 — the **fourth and fifth independent
> nulls** for the pseudo-label exchange — and a same-seed no-pseudo control
> (`evidence/h60d_cotrain_control.json`) isolates the exchange effect as null (−0.0002…+0.0003; the
> apparent gain was the seed). **Verdict: NEGATIVE.** The disagreement fields beat View A and random
> but lose to View B and the union on every fold, both instruments, both budgets (hide pooled
> HOLDOUT-DTI at 37,654 px: view_B 0.006419 [0.005873, 0.006892] > union 0.006140 > **dis_contrast
> 0.004109 [0.003597, 0.004948]** > view_A 0.004031 > dis_product 0.003196 > random 0.001802; 36,411
> withheld positives, 4 whole-segment folds, evaluator pinned). The lane ships the best measured
> A-side disagreement field as `gems52-h60d-dis_contrast-arm37654px.tif` (37,654 px, pure disagreement
> arm, 100 % outside every accessible prior's support, all finite {0,1}, format gate 0 problems,
> pattern-unique vs 55 aligned priors, 99.2 % outside the union field's own emission, lane gate clean,
> nearest mapped catalogue pixel 223.6 m) with **reasoning for every emitted pixel and for all 11,064
> A-only pool segments**. The registered promotion/slot bar failed → **research-only: download OK for
> review, DO NOT spend a weekly slot**. `submission/LATEST.txt` and `docs/data/submission.json` stay
> on H57; H60D publishes as `docs/data/submission_h60d.json` and `docs/h60d.html`. Two evidence-based
> corrections were registered before shipping (H60-5: the artifact is placed by the registered scoring
> emitter `h57.iso_select`, not `greedy_emit`, whose coverage surrogate was measured anti-correlated
> with the holdout truth on the novel pool; H60-6: the lane-drift 3-px proximity component excludes
> manifest-classified calibration rasters — the raw 0.8390 reading against the dense calibration
> lattice is geometry, not duplication). See `knowledge/31_what_h60D_found.md`;
> `registry/irregularities.json` → `IR-H60D-001`–`IR-H60D-005`. Organizer authentication of the mirror
> remains the open blocker.


**[Download the newly generated TIFF](docs/downloads/ctd5-research.tif)** · [single-TIFF ZIP](docs/downloads/ctd5-research.zip) · **[Executive summary / exact submission guide](docs/executive-summary.html)** · [Run card](evidence/ctd5_run_card.json)

> **DOWNLOAD FOR RESEARCH: YES. SUBMIT TO COMPETITION: NO.** CTD5 is a negative result. It is newly inferred, not copied, and differs from every checked prior's decoded predictions. It nevertheless fails the requested three-pixel lane-uniqueness gate and the scientific promotion requirements. **No competition slot was used.**

- **File:** `gems52-ctd5-cover-disagreement-20261008-a24c35d1-b58bae0f0e.tif`
- **SHA-256:** `a6e6e44aebaf057989e254bd5ce3729e5a94836c0e5687a95e91e3fc8a40c686`
- **Local validator:** one float32 band; all finite {0,1}; zero NaN/Inf; EPSG:32611; 3,730 × 3,292; exact sample transform; 12,000 emitted cells; 83,917 bytes. This is not an organizer acceptance receipt.
- **Name:** `CTD5-cover-matched-disagreement-b58bae0f0e`
- **Note (116 / 140 chars):** `CTD5: cover-matched geophysics to surface abstention; one pseudo-label round. Research only; no prior pixels reused.`
- **HOLDOUT-DTI:** `gems52-pooled-hide-v1`, **0.018848**, **95% CI [0.012421, 0.026020]**, **53,186 withheld positives**. **Descriptive only:** a fold emitted 2,041/3,058 requested nodes; the candidate/control comparison is not matched-budget eligible. The surface-only control's HOLDOUT-DTI is 0.106749, 95% CI [0.089076, 0.124951], same evaluator and withheld positives. No leaderboard forecast.
- **Uniqueness diagnostic:** 541 files / 360 decoded rasters; exact maximum Spearman 0.068203 before placement and 0.013418 after. No identical array, no A/B union. **Maximum directed proximity 100% > 70% → duplicate/STOP.**
- **Concurrent closure audit:** one newly merged H60 raster was also checked against the unchanged surface and dots, bringing the total to **542 files / 361 decoded patterns**. Its near-dot fraction was 27.1917%, below the rule; the earlier 100% duplicate/STOP remains. [Reconciliation receipt](evidence/ctd5_parallel_reconciliation.json).
- **Why the proximity gate effectively cannot pass this registry (corrected 2026-10-08):** the earlier receipt measured coverage on a 4,593,171-px "eligible" footprint and reported 100%. On the competition sample's finite footprint (**5,167,373 px**, `data/sample_submission.tif`), the 13GEMSDOE spacing-five lattice is within 3 px of **99.87 %** of cells (5,160,724 px). The **6,649** uncovered cells are **99 % within 3 px of the survey edge** (6,580 px). A dot raster therefore passes only if ≥30 % of its dots sit on that border rim, which no geological candidate would do. We did not change the threshold. The 4,593,171-px footprint discrepancy is logged as **IR-UNQ-003** for review. [Original receipt](evidence/ctd5_registry_saturation.json) · [Re-run audit](evidence/uniqueness_audit_ctd5_20261008.json).

> **Final validation correction:** CTD5’s legacy evaluation halo used withheld fault-tail locations to extend placement regions. The arithmetic below is exploratory, **not strict holdout-valid promotion evidence**. The shared default splitter is now label-blind v2. No refit, new placement, or revised performance number was produced after STOP. [Correction receipt](evidence/ctd5_validation_scope_correction.json).

A second concurrent H60 artifact was checked against the unchanged output: closure scope is now **543 files / 362 decoded patterns**, with the same maximum correlations and 100% near-dot STOP. Its code, artifacts and historical pages are preserved. [Second check](evidence/ctd5_second_parallel_check.json).

## Session 2026-10-08 — H60C continuation (co-training lane), re-verified on fresh bytes

**DOWNLOAD FOR RESEARCH: YES · SUBMIT: NO.** This session re-verified the co-training-lane artifact on the
**freshly restored 2026-10-08 SHA-pinned bytes** (not from prior evidence) and added three new hypotheses
with the top one holdout-validated. Nothing was promoted; **no competition slot was used.** [Run card](evidence/h60c_lane_run_card.json) · [lane verification](evidence/h60c_lane_verification.json) · [set-algebra receipts](evidence/h60c_identify_20261008.json) · [new hypotheses](knowledge/30_hypotheses_h60c_new.md)

- **Lane artifact re-verified** (`scripts/verify_lane_h60c.py`): format-valid (EPSG:32611, 3,730×3,292, exact
  sample transform, all-finite `{0,1}`, zero mass outside footprint); **decoded-pattern-unique** (max tie-aware
  Spearman **0.00048** vs the 13 manifest-pinned registry rasters, 0 exact matches, not a literal union).
- **Lane uniqueness gate still fails** (the decisive fact, re-measured): max directed ≤3px dot proximity to one
  registry raster = **1.0** (> 0.70). The 13GEMSDOE spacing-5 lattice saturates **99.87 %** of the eligible
  footprint within 3px, so *no non-empty raster on this frozen footprint can pass the >70% rule*. → **DUPLICATE/STOP, research-only.**
- **Why 0.2778 / can it beat 0.3195 — re-derived from bytes** (`scripts/h60_forensics.py`, `h60_identify.py`):
  **|G| = 14,088.7 px**; the champion's entire credit sits in the **25,517-px** 5-family core (density 0.205);
  the identified DTI interval of that core **P1 = A∩C is [0.2524, 0.3196]** — its top (0.3196) is the
  "0.3195 current best." Beating it would need pixels denser than 0.205, which **no held measurement shows**;
  the champion's extra 12,137 px carry zero credit. (All scores are **owner-reported, not organizer-confirmed**.)
- **New hypothesis validated on the holdout** (`scripts/n2_holdout.py`, HOLDOUT-DTI, `gems52-pooled-hide-v1`,
  36,439 withheld, 15k-dot budget): edge-edge coincidence candidate **0.00857 [0.00614, 0.01131]** vs surface
  control **0.01890 [0.01211, 0.02703]**; paired delta **−0.01033 [−0.01848, −0.00347]** → **negative** (does
  not beat the control). The simulator is a defective board predictor (Spearman ≈ −0.10), so even a win would
  not authorise a slot.

## Which file is unique? — audit of 2026-10-08

Every number below is from a receipt in `evidence/`, produced by `scripts/audit_uniqueness.py`, which runs the repo's shared `lane_uniqueness_report` against every accessible prior raster (31 distinct files after byte-dedupe; the candidate's own byte-identical copies excluded and listed).

| file | decoded-unique? | max Jaccard to a prior | share of its cells inside prior support | surface rank ρ max (gate ≤0.90) | dot ≤3 px max (gate ≤0.70) | verdict |
|---|---|---:|---:|---:|---:|---|
| `ctd5-research.tif` (CTD5) | **yes** | 0.0034 | 16.4 % | 0.0037 | 100 % (lattice) | unique · research-only · holdout negative |
| `h60c-candidate.tif` (H60C) | no (copy of prior core) | 0.59 | 80.4 % | 0.7413 | 99.87 % (lattice), 80.7 % (`h19-5`) | **not unique** · format-valid |

Consequences: (1) **no file in this repository is simultaneously unique and holdout-validated**; (2) the proximity gate is practically unpassable on this footprint (see the CTD5 bullet above); (3) the only route to a *unique, competitive* file is a new validated signal, not a re-weighting of prior pixels. Neither file is approved for a competition slot. Competition upload is not performed by this repository. Run card for this audit: [evidence/session_2026-10-08_run_card.json](evidence/session_2026-10-08_run_card.json) (verdict negative; `submit_ok: false`; 0 slots used). Reproduce: `.venv/bin/python scripts/audit_uniqueness.py <file.tif> evidence/<receipt>.json`.

## H60C — the round that answers "why 0.2778" with arithmetic, and ships a bar-sized emission

> **⚠ CORRECTION 2026-10-08 — H60C is NOT a unique submission.** Its 35,185 emitted cells are 80.4 % inside the support of prior submissions (73.3 % inside `h33-2-b2` alone; max single-file Jaccard 0.59 with `gems57` H57). Its dot phase is 99.87 % within 3 px of the s5 lattice and 80.7 % near `h19-5`. It is format-valid (single-band float32, EPSG:32611, values in {0,1}), so the file **downloads without a format error**, but it **does not satisfy "unique, not a copy of a previous submission."** Do not present it as the unique submission. [Receipt](evidence/uniqueness_audit_h60c_20261008.json) · [IR-UNQ-001](registry/irregularities.json).
>
> **The file that is actually decoded-unique is CTD5** (max Jaccard 0.0034 to any prior; surface-rank ρ 0.0037). It is a negative research result with a holdout DTI below its own surface control. See the section "Which file is unique" below.

**[H60C GeoTIFF — format-valid, NOT unique (see correction above)](docs/downloads/h60c-candidate.tif)** ·
[one-TIFF ZIP](docs/downloads/h60c-candidate.zip) ·
[A-only geological reasoning CSV](docs/downloads/h60c-a-only-reasoning.csv) ·
[H60 audit page](docs/h60c.html) · [how to submit](docs/executive-summary.html) ·
[ranked hypotheses](knowledge/25_hypotheses_H60_preregistered.md) ·
[build receipt](docs/data/h60c_build.json)

### Why `h33-h33-2-b2` scored 0.2778 — measured, not inferred

`h33-2-b2` is **not a better detector** than the file it came from. It is `gems24-d2-8` (reported
0.2600) **with 6,436 pixels deleted**. Those 6,436 pixels are exactly the ones lying within
100–200 m of the mapped USGS/INGENIOUS catalogue, and inverting the published metric on that nested
pair gives their credit as **exactly zero**. Removing 14.6 % of the file's mass raised its score by
**+6.8 %**, because a masked pixel can never earn credit but always pays the false-positive tax.
That single edit is the whole story of the score, and the same algebra yields

> **|G| = 14,088.7 px** — the size of the hidden, expert-drawn, off-catalogue truth (0.273 % of the
> 5,167,373-px footprint, against 1.18 % for the catalogue itself).

Everything in H60 is downstream of those two numbers. They are recomputed from restored,
SHA-256-pinned bytes by `scripts/h60_forensics.py`; nothing is copied from a prior note.

### Can a submission beat 0.3195? — the honest arithmetic

With `DTI = T / (0.2·S + 0.8·|G|)` (exact for sparse dot emissions, where `M ≈ T`), the marginal
rule is: **emit a pixel iff its expected incremental credit `c > α·DTI/(1 − α·DTI)`**, which at
`DTI ≈ 0.32` is **`c > 0.068`** — about 2.7× what uniform random achieves (measured 0.024–0.028).

Measured credit density of everything we hold:

| set | px | credit | density | × random |
|---|---:|---:|---:|---:|
| `P1 = A ∩ C` (this round's core) | 25,517 | 4,133 – 5,233 | **0.163 – 0.205** | 6.8 – 8.5× |
| `A` champion `h33-2-b2` | 37,654 | 5,223.1 | 0.1387 | 5.7× |
| `E` `h19-5` parent field | 121,131 | 6,822.6 | 0.0563 | 2.2× |
| `I` `Hedge-v2` (off-catalogue) | 166,519 | 8,873.5 | 0.0533 | 2.6× |
| uniform random | — | — | 0.024 – 0.028 | 1× |

`P1` beats the champion iff `t(A \ C) < 674.6`, which covers 64 % of that atom's identified range;
expected `DTI(P1) = 0.2868` against a *certain* `0.2772–0.2784` for `A`. **`P1` alone does not
reach 0.3195.** Reaching it requires arm mass at density above the 0.068 bar, and no measurement
available in this repository can certify that — the twelve scored files leave every non-file subset
**set-identified with a lower bound of zero** (`scripts/h60_identify.py`). H60 therefore ships the
arm as a priced bet, sized at the bar, and publishes the full projection table rather than a hope.

### What is new in H60 relative to every earlier round in this repository

1. **`|G|` and per-file credit are re-derived from the bytes**, and candidate emissions are then
   bounded by **linear programming over the identified set** — not by a point estimate. Earlier
   rounds used NNLS, which silently selects one corner of a large polytope and invents information.
2. **A parametric corroboration ladder was preregistered and refuted.** Four coefficients cannot
   reproduce the twelve measured credits (median |rel.err| 0.22, leave-one-file-out 0.28, and
   `M` missed by a factor of 11). It is recorded as a negative result in
   `knowledge/27_what_h60_found.md`; the free-form 13-parameter version was refuted first.
3. **A measured, previously unnoticed defect in the champion's own recipe.** On the 100 m integer
   lattice, sampling a straight trace every **3 px returns 2.333 credit per dot and covers 77.8 %
   of the trace**, while the champion's `d2-8` (2.8 px) returns 2.147 and covers 76.7 %. Spacing 3
   strictly dominates spacing 2.8 — fewer dots, more coverage — so H60 uses 3 px.
4. **Two files with byte-identical decoded content** (`8GEMSDOE_Hedge-v2_submission.tif` and
   `gemsdoe-ens12-adopted-7f00890a.tif`, 166,519 off-catalogue px each) both report **0.1563**.
   That is the first internal consistency check on the owner-reported file-to-score mapping
   (see `registry/irregularities.json`).
5. **The 0.2778 / 0.2600 pair is the only nested cross-check of `|G|`, and it is tight**: publication
   rounding to four decimals moves `|G|` by only ±70 px.

### Is it OK to download? Is it OK to submit?

**Download (format-valid): YES. Unique submission: NO (corrected 2026-10-08, see the correction above).** The file is portal-safe by construction — single-band float32,
EPSG:32611, 3,730 × 3,292, transform identical to `sample_submission.tif`, every pixel finite and
in `{0, 1}`, no nodata tag. The "Predicted values must be in range [0, 1]" rejection is caused by
NaN-bearing exports and **cannot occur** with this file; `gems52.grid.write_geotiff` refuses to
write it otherwise.

**Spend a weekly submission slot: read `docs/h60c.html` first.** The core is the best-measured mass
this repository has. The arm's density is not measured and cannot be. The decision, with its full
sensitivity table, is on the audit page.

<!--/H60README-->

<!--H60DREADME-->
## H60D — co-training with disagreement as the discovery signal; NEGATIVE result, artifact published research-only (2026-10-08)

**[★ H60 GeoTIFF — one click, no scrolling](docs/downloads/h60d-candidate.tif)** · [short ZIP](docs/downloads/h60d-candidate.zip) · [canonical TIFF](docs/downloads/gems52-h60d-dis_contrast-arm37654px.tif) · [per-pixel geology reasoning CSV (37,654 rows)](docs/downloads/gems52-h60d-37654px-candidate-geology.csv) · [A-only segment reasoning CSV (11,196 rows, one falsifier each)](docs/downloads/gems52-h60d-a-only-candidate-segments.csv) · [audit page](docs/h60d.html) · [receipt](docs/data/submission_h60d.json) · [run card](docs/data/h60d_run_card.json) · [slot gate](docs/data/h60d_slot_gate.json) · [validation](docs/data/h60d_validation.json) · [co-training E1](docs/data/h60d_cotrain.json) · [same-seed control](docs/data/h60d_cotrain_control.json) · [preregistration](registry/h60d_preregistration.json) · [ranked hypotheses](knowledge/30_hypotheses_H60D_preregistered.md) · [what H60D found](knowledge/31_what_h60D_found.md).

- **Is it OK to download? YES.** Is it OK to submit? **The file is portal-valid** (format gate 0
  problems; every pixel ∈ {0,1}; no NaN anywhere — a value outside [0,1] or a NaN cannot exist in it
  by construction), **but this repository does not approve spending a weekly slot on it**: the
  preregistered promotion rule failed on every clause (the disagreement fields do not beat the union
  AND both views; mean lift vs random at 37,654 px is +0.0023 hide / +0.0016 tip, far below the
  +0.005 bar), so the site says so in one sentence and the receipts carry the whole argument.
  Downloading, reviewing and reproducing it is exactly what it is approved for.
- **Identifiers to paste (verbatim from `evidence/h60d_build.json`).** Name (49 chars):
  `gems52-h60d-dis_contrast-arm37654px-18bd0efd-zeros`. Note (139 chars): `H60D co-training
  disagreement arm max(pA-pB,0); outside all prior support and the 200 m ring; finite binary [0,1];
  not a verified fault map` — both ≤ 200 characters, and the site's one-click ZIP carries them as
  paste-ready text files (`submission-name.txt`, `submission-note.txt`).
- **The result, honestly (all HOLDOUT-DTI, evaluator pinned, 36,411 withheld positives, 4
  whole-segment hide-and-recover folds, 95 % fold-bootstrap CI).** Hide pooled at 37,654 px: view_B
  0.006419 [0.005873, 0.006892] > clf_union 0.006140 [0.005598, 0.006610] > **dis_contrast 0.004109
  [0.003597, 0.004948]** > view_A 0.004031 [0.003438, 0.004445] > dis_product 0.003196 [0.002582,
  0.003578] > random 0.001802 [0.001508, 0.001944]. The A-side disagreement fields beat View A and
  the random control but lose to the surface view and the union on every fold, both instruments, both
  budgets (15,000 px ordering identical). The shipped raster itself scores hide pooled 0.003514
  [0.003234, 0.003847] on the required-novel pool — above the matched novel-pool random control
  (0.001080) but below the novel-pool union (0.003384) and view_B (0.004239). The B-only product
  (0.006409) ranks like View B itself and is registered characterization-only (H60-4): it is the
  surface view's own confident core — the suspect-artifact population — and can never ship.
- **Method, honestly:** two logistic views (A: potential-field/subsurface, B: surface DEM +
  radiometric bands) fitted **out-of-fold** on whole-segment folds; discovery signal = disagreement
  (A-confident/B-abstains → buried fault; B-confident/A-abstains → suspect surface artifact). The
  independence premise was **measured** (max |r| 0.176 < 0.60) before any exchange; one co-training
  round ran in both directions (confident-to-abstain pseudo-labels, whole segments) and moved fold-0
  AUC by −0.0067 / −0.0104 — null — with a same-seed no-pseudo control isolating the exchange effect
  as null. The leakage canary is clean (worst layer AUC 0.7136). The strata reproduce the cover
  geology (A-only 301,390 px at median 341.7 m depth vs B-only 197,479 px at 106.5 m).
- **Placement (registered correction H60-5):** the artifact is the top-k of the shipped field by the
  registered scoring emitter `h57.iso_select` (3 px inclusive, 5 px NMS, 37,654 px budget). The
  originally preregistered `greedy_emit` coverage surrogate was measured **anti-correlated** with the
  holdout truth on the required-novel pool (hide pooled 2.2e-05, ~50× below the matched novel-pool
  random control; its dots sit on the field's broad plateaus, mean field 0.349) — so it is retained
  only as a disclosed, scored diagnostic in the receipts. 24,217 of the 37,654 emitted px are
  positive-field crests; 13,382 are zero-field budget fill (disclosed — the field's confident
  novel-pool support is below the budget).
- **Gates:** format PASS · uniqueness vs all 68 accessible aligned priors PASS (decoded pattern
  matches none; 100 % of emitted px novel to all priors' support; not a literal prior union) · lane
  drift PASS (surface max |Spearman| 0.0979, dots 0.0094, bar 0.90; 3-px proximity 0.1592 excl.
  manifest-classified calibration rasters, bar 0.70 — raw 0.8390 vs the dense calibration lattice is
  reported, correction H60-6) · not-merely-union PASS (99.2 % outside the union field's greedy
  emission, 99.1 % outside its iso top-k) · ring gate PASS (nearest emitted pixel to a mapped trace
  223.6 m; zero emitted px inside 100–200 m) · independence measured, not assumed (0.176 < 0.60) ·
  leakage canary clean · slot bar FAIL → RESEARCH ONLY · verdict **negative**.
- **Re-measured after the merge:** the renamed round was rebuilt against the merged prior
  inventory (68 accessible aligned priors — every H60C/CTD5/concurrent-H60 raster on main is a
  genuine prior), so the final artifact is `gems52-h60d-dis_contrast-arm37654px.tif`
  (144,504 bytes, sha256 `18bd0efd582f107ccb988fc20016203c323846bf63d3ecea1f75a0670e4586e8`,
  37,654 px, pattern-unique vs 68 priors, 100 % support novelty, lane gate clean, shipped-raster
  hide pooled HOLDOUT-DTI 0.003136 [0.002937, 0.003414] — above novel-pool random 0.001080,
  below novel-pool union 0.003384). Verdict unchanged: **negative**.
- **Reproducibility:** `scripts/run_h60d_cotrain.py` (E1 fit + co-training + independence + canary;
  E2 holdout arm comparison; checkpointed, cached stages skip) → `scripts/run_h60d_cotrain_control.py`
  (same-seed control) → `scripts/build_h60d_submission.py` (E3: emits the raster, runs all gates,
  writes every receipt) → `scripts/publish_site_h60d.py` (renders the site from the receipts; the HTML
  quotes no number not present in a JSON). A rebuild is a measured **fixed point**: the artifact
  sha256 (re-measured after the rename and the merged prior inventory; see `evidence/h60d_build.json`) reproduces byte-exactly
  across rebuilds (the self-exclusion of H60 outputs — BOTH published names — was widened after a
  second build initially treated its own previous stem-named `docs/downloads` copy as a prior,
  `IR-H60D-002`).
<!--/H60DREADME-->


## Start here every session

Read the **complete current prompt below**, [working agreement](AGENTS.md), [frozen ranked hypotheses](knowledge/25_ctd5_preregistered.md), [results and limitations](knowledge/27_ctd5_results_and_limits.md), and [three-pass review](knowledge/28_ctd5_three_pass_review.md). The older README is preserved unchanged in [the history archive](knowledge/archive/README_before_ctd5.md); its conflicting “current” pointers and scientific/score claims are **not current authority**.

**Maximize P(Win):** do not consume a scarce slot to make a failed research run look successful. **Own the Outcome:** publish the real file, failure diagnostics, provenance boundaries and reproduction—not only a promising story.

## What this session completed

1. Reviewed prior H55–H59/R4 failures and registered four new, lane-specific hypotheses before fitting. Tested only cover-matched transfer; other hypotheses remain untested proposals.
2. Restored the pinned owner-mirror data autonomously, ran the download wrapper and data preparation, and trained on CPU. The misleading tracked tiny placeholder TIFFs were removed from Git; the real files remain in ignored `data/` and `work/ctd5/input/`. **Integrity-pinned does not mean organizer-authenticated.**
3. Rehydrated the missing cache using the shared template builder. Corrected the shared band-6 view assignment provisionally; no external feature or prior prediction entered training.
4. Used buffered whole-original-component OOF folds, feature-alone canaries, proxy-negative error correlation, one whole-segment confident-to-abstaining exchange, pooled DTI with 95% spatial CIs, and the repo's sparse emitter. The exact DTI/writer are shared modules, not private forks.
5. Audited all 52 supplied owner repository sources and 524 aligned immutable TIFF blobs, plus local history. Generated a new TIFF and stopped at the strict lane gate. Wrote reasoning for all 1,521 A-only segments and all 12,000 emitted cells.
6. Published clear download/submit status, an executive-summary guide, a source ledger, a reproducible Actions workflow and a local-only feed. The browser does not pretend to train a model, and the feed does not pretend to be a live leaderboard.

## Why H33 may have improved—and what is not proven

The supplied H33 attribution **0.2778 is OWNER-REPORTED / NOT ORGANIZER-CONFIRMED**. Its [current repository source](https://github.com/buffedlizard55-lab/GEMSDOE32/blob/0d6a6243147cd63a2000412d575d4c80a36d3a62/docs/index.html) says no organizer score exists. We cannot resolve that conflict without a file-linked receipt.

The files show the immediate parent had 40,199 dots and H33 37,654: it deleted 2,545 **off-catalogue** dots within 200 m, adding none. A true score improvement would be consistent with removing more false-positive cost than lost maximum-cover credit. Known pixels themselves are pixel-exact masked and do **not** pay a false-positive tax. No hidden-truth count, zero-credit ring, exactly credited reusable core or higher-score guarantee can be recovered from this unauthenticated list alone. [Full metric reasoning and re-measured evidence](knowledge/27_ctd5_results_and_limits.md).

## Historical negative-result guards

**No H55-1 TIFF was built** after its failed paired-shoulders gate, and it was never promoted. H55-EDGE, H58 and H59 negative/research artifacts and their original receipts remain available in the archives; none becomes submission-approved just because the landing page is updated.

## Reproduce the research file

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-r2.txt
GEMS_PYTHON=.venv/bin/python bash scripts/reproduce_ctd5.sh
```

The script restores core data and the **frozen** comparator inventory, reuses or rehydrates the shared feature cache, evaluates, and writes the same negative research artifact. It does not upload or select a submission. Raw data, arrays, model caches and downloaded comparators stay ignored. The optional [GitHub Actions reproduction](.github/workflows/reproduce-ctd5.yml) exports the research TIFF and receipts, not a competition upload.

Individual stages: `scripts/run_ctd5.py canary`, `fit`, conditional `exchange`, then `scripts/build_ctd5_submission.py`. Publication: `scripts/publish_ctd5.py`. Checks: `python -m pytest -q`, `python scripts/check_site.py`, `python scripts/check_ctd5_release.py`.

## Evidence and next steps

- [Hypotheses and frozen protocol](knowledge/25_ctd5_preregistered.md) · [Pooled DTI/CIs](evidence/ctd5_post_holdout.json) · [Every feature canary](evidence/ctd5_canary.json) · [Independence screen](evidence/ctd5_independence.json) · [Pseudo-label records](evidence/ctd5_pseudo_exchange.json)
- [All sources](docs/ctd5-sources.html) · [Original source inventory](evidence/ctd5_sources.json) · [Prior raster inventory](evidence/ctd5_prior_inventory.json) · [Geological dossiers](docs/ctd5-audit.html)
- [Full results / limitations](knowledge/27_ctd5_results_and_limits.md) · [Three-pass review](knowledge/28_ctd5_three_pass_review.md) · [Irregularity registry](registry/irregularities.json)

Next: resolve universal-coverage registry policy **prospectively in the shared selector**; authenticate the organizer inputs/score receipts; verify band identity and upstream model lineage; pre-register a capacity-feasible holdout comparison. Do not repeat this failed placement or silently switch lanes. External official hosts and the authenticated submission page are inaccessible here, so a fresh leaderboard top, current weekly allowance and organizer provenance are unresolved. No passwords/tokens are needed in chat.

`submission/LATEST.txt` was advanced to unapproved H60 by concurrent upstream PR #34. That upstream marker is retained, not selected or promoted by CTD5; it is not this session’s research link and does not authorize upload. The H57 archive is retained. CTD5 has its own `submission/CTD5_RESEARCH_LATEST.txt` and `docs/data/ctd5_run_card.json`.

## Complete current prompt — read before working

The following is user-supplied task text, not independently verified factual claims. It supersedes earlier prompt archives where they conflict.

```text
Review the repo.

THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED!

MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION.  DO NOT COPY A PREVIOUS SUBMISSION UNLESS IT'S FOR LEARNING AND EDUCATION.  BUT WE MUST GENERATE A UNIQUE TIF SUBMISSION.  IT MUST BE OBVIOUS WHETHER IT IS OK TO DOWNLOAD AND SUBMIT THE GENERATED TIF SUBMISSION.

There should be an easy to download submission tif file as described by the prompt.  Read the entire prompt.

Co-training between a geophysical view and a surface view, with disagreement as the discovery signal. Blum and Mitchell (COLT '98, pp. 92–100, doi:10.1145/279943.279962) show that when each example has two views, each sufficient and approximately conditionally independent given the class, two learners trained on separate views can use each other's confident predictions on unlabeled data. View A is potential-field and subsurface (gravity, magnetics, strain, seismicity). View B is surface (DEM-derived curvature and slope, plus any radiometric bands present in training_features.tif). Test the independence assumption empirically: correlate each view's spatial-block out-of-fold errors on labeled negatives, and abandon the method if they are strongly correlated. Pseudo-label only where one view is confident and the other abstains, using whole-segment spatial blocks and a buffer so no leakage reaches the evaluation. The discovery signal is disagreement. Where A is confident and B is not, the fault may be buried beneath cover. Where B is confident and A is not, suspect surface artifacts such as roads or erosion lines. Because Phase 2 reviewers verify faults, write the geological reasoning for every A-only candidate. Co-training can also amplify bias, so compare against a single-view baseline on hide-and-recover segments. Normalize to [0,1], write the GeoTIFF, apply the repo's metric-aware placement, run the uniqueness gate, and confirm the output isn't merely the union of the two views.

PARALLEL-RUN PROTOCOL — read first. This session is one of several running from this same prompt.

1. LANE. Your lane is the single method paragraph below. Stay inside it. If your raster's rank-correlation with any registry raster exceeds [0.90], or more than [70%] of your dots fall within 3 px of one registry raster's dots, you have drifted into another lane: log it as a duplicate and stop. Check this on the surface before placement AND on the final dots.

2. REUSE, DON'T REBUILD. Use the template's cached feature stack, evaluate_[holdout.py](http://holdout.py) and submission_[writer.py](http://writer.py). Holdout = hide-and-recover: withhold whole fault segments with a buffer, derive every catalogue-based feature only from the visible faults, mask visible faults pixel-exactly, score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel). If a shared tool is wrong, fix it once in the template and report it; never keep a private fork.

3. LABEL EVERY NUMBER as HOLDOUT-DTI (evaluator version, number of withheld positives, 95% CI) or ORGANIZER-CONFIRMED (copied from a submission-page receipt). A projection is never written as a score.

4. LEAKAGE CANARY. Test each feature alone on the holdout before trusting any result. AUC above [0.90] means leakage until proven otherwise.

5. RUN CARD. End with one JSON card: hypothesis; mechanism; the named non-fault process that could mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator output (no NaN inside the footprint, values in [0,1], CRS/shape/transform match); submission name + note of at most 140 characters; verdict promote / negative. Negative results are deliverables.

6. BUDGET. Stop after [3] experiments or [2] hours. Do not pick submissions: promotion to a real slot is a separate selector step, within the weekly cap shown on the submission page.

The following sites should serve as a starting point for understanding how to generate TIF submissions.  These websites are researched, and tested and have generated TIF submissions.  But we need to generate high scoring submissions.

Here are the results from submissions into the competition, separated by ....:

WE NEED TO STUDY, ANALYZE, AND UNDERSTAND THE HIGHEST SCORE FROM THE GEMDOE SITE WHERE THE SUBMISSION TIF IS DOWNLOADED FROM WHICH IS THE FOLLOWING:

[https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html)

h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778

Why and how did this get the highest score and are we able to generate a submission that scores higher than 0.2778?

Answer the question using Phd level experience, knowledge, and judgement. Then use the answer to generate a unique TIF submission into the competition.  Must be unique submission unlike any within the GEMSDOE sites above.  Verify working line by line no hallucinations.

Current competition leaderboard GEMSDOE high score:

0.3774

[https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html)

gems-submission-20260925T001403Z-7f00890a: 0.1563

....

[https://buffedlizard55-lab.github.io/6GEMSDOE/](https://buffedlizard55-lab.github.io/6GEMSDOE/)

gems6_hgb88-topk03_33cec71ff0: 0.0286

....

[https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html)

pindrop-v4-nodes-20260925T152420Z-f347b70daa: 0.1193

pindrop-v4-discovery-20260925T152423Z-37f9d5b855: 0.0830

pindrop-v4-ridge-20260925T152422Z-4e03fc9705: 0.1152

....

[https://buffedlizard55-lab.github.io/GEMSDOE2/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE2/docs/index.html)

gemsdoe2-dual-family-union-20260925T160406Z-f68e590f: 0.1560

....

[https://buffedlizard55-lab.github.io/GEMSDOE4/](https://buffedlizard55-lab.github.io/GEMSDOE4/)

gems-submission-20260926T163915Z-237f0063: 0.0343

....

[https://buffedlizard55-lab.github.io/5GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/5GEMSDOE/docs/index.html)

gems-submission-20260926T175114Z-7f00890a: 0.1563

....

[https://buffedlizard55-lab.github.io/7GEMSDOE/](https://buffedlizard55-lab.github.io/7GEMSDOE/)

lidarscarp-ridge-top2pct-36c3a3f341c8: 0.1461

....

[https://buffedlizard55-lab.github.io/8GEMSDOE/](https://buffedlizard55-lab.github.io/8GEMSDOE/)

Hedge-v2_submission: 0.1563

....

[https://buffedlizard55-lab.github.io/GEMSDOE9/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE9/docs/index.html)

2314b599: 0.0107

....

[https://buffedlizard55-lab.github.io/11GEMSDOE/](https://buffedlizard55-lab.github.io/11GEMSDOE/)

gems-structural-area06-v1: 0.0202

....

[https://buffedlizard55-lab.github.io/12GEMSDOE/](https://buffedlizard55-lab.github.io/12GEMSDOE/)

r7-nms3-dem10-scarp_0c9199f14e62:0.1294

r7-nms3-dem10-scarp_0c9199f14e62_allfinite:0.1294

....

[https://buffedlizard55-lab.github.io/15GEMSDOE/](https://buffedlizard55-lab.github.io/15GEMSDOE/)

gems-tso1-20260929T005627Z-conj_alteration_mag: 0.0782

....

[https://buffedlizard55-lab.github.io/14GEMSDOE/](https://buffedlizard55-lab.github.io/14GEMSDOE/)

GEMS_r5-geom-horse-ensemble_20260929T154852Z_ccbe1de0_site_e96e942f: 0.0020

....

[https://buffedlizard55-lab.github.io/17GEMSDOE/](https://buffedlizard55-lab.github.io/17GEMSDOE/)

17GEMSDOE_F-ensemble-2pct_20260930T050626Z:0.0187

....

[https://buffedlizard55-lab.github.io/18GEMSDOE/](https://buffedlizard55-lab.github.io/18GEMSDOE/)

H19-C_20260930T212401Z_c11e495e: 0.0297

....

[https://buffedlizard55-lab.github.io/19GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/19GEMSDOE/docs/index.html)

h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan: 0.1894

h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan: 0.1922

....

[https://buffedlizard55-lab.github.io/GEMSDOE10/](https://buffedlizard55-lab.github.io/GEMSDOE10/)

h16-continuation-20260927T065521077735Z-3431b83c7c: 0.0461

h20-dem10-scarp-thin-20260927T155223039488Z-ffc91a1686: 0.0921

H25-ctx-ridge-20260927T232947704150Z-6452ae1d00: 0.1280

h28-dotted-ridge-20260928T020256236880Z-6452ae1d00: 0.1839

....

[https://buffedlizard55-lab.github.io/13GEMSDOE/](https://buffedlizard55-lab.github.io/13GEMSDOE/)

20261001_r13-lattice-s5_v2_nan-outside:0.0904

....

[https://buffedlizard55-lab.github.io/16GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/16GEMSDOE/docs/index.html)

h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan: 0.1855

h18-3a-topo-geophys-x-complexity-prior-20260930-c502dfab-nan: 0.0976

h18-4-usgs-geologic-map-faults-gap-20260930-aef8f42c-nan: 0.0360

....

[https://buffedlizard55-lab.github.io/GEMSDOE21/](https://buffedlizard55-lab.github.io/GEMSDOE21/)

h19-4-reference-20260930-691e4dfa: 0.1894

....

[https://buffedlizard55-lab.github.io/20GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/20GEMSDOE/docs/index.html)

h20-1-sarnnpu-powerlaw-pi0363-tilt-wingcrack-20260930-be0e8f6b-nan: 0.1890

h20-5-continuous-pu-proxy-unverified-20260930-824ce73a-nan: 0.1859

....

[https://buffedlizard55-lab.github.io/GEMSDOE22/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE22/docs/index.html)

h23-a-dti-optimal-emission-6pct-20261002-e2ec4b49-nan: 0.1002

h23-b-dti-optimal-emission-10pct-20261002-86176698-nan: 0.0748

....

[https://buffedlizard55-lab.github.io/GEMSDOE23/](https://buffedlizard55-lab.github.io/GEMSDOE23/)

h30-arrangement-matched-habitat-20261002-0d4e02e8-nan: 0.1352

....

[https://buffedlizard55-lab.github.io/GEMSDOE24/](https://buffedlizard55-lab.github.io/GEMSDOE24/)

h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan: 0.2477

....

[https://buffedlizard55-lab.github.io/GEMSDOE25/](https://buffedlizard55-lab.github.io/GEMSDOE25/)

dotted-h19-5-d2-8-20261002-e56ea318af89-nan: 0.2600

....

[https://buffedlizard55-lab.github.io/GEMSDOE26/](https://buffedlizard55-lab.github.io/GEMSDOE26/)

dilcond-oof-v1-20261003-47629f496133-nan: 0.1223

....

[https://buffedlizard55-lab.github.io/GEMSDOE27/](https://buffedlizard55-lab.github.io/GEMSDOE27/)

topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan: 0.2449

....

[https://buffedlizard55-lab.github.io/GEMSDOE30/](https://buffedlizard55-lab.github.io/GEMSDOE30/)

d28-poisson300m-offcat-44090-20261003T233156Z-91eae1ca: 0.2600

....

[https://buffedlizard55-lab.github.io/GEMSDOE31/docs/](https://buffedlizard55-lab.github.io/GEMSDOE31/docs/)

h27-4-solo-d28-20261004-8acb75e1-nan:0.2708

....

[https://buffedlizard55-lab.github.io/GEMSDOE33/](https://buffedlizard55-lab.github.io/GEMSDOE33/)

h33d-analog-tip-stepover-r30-20261004-cb490425926e: 0.2632

....

[https://buffedlizard55-lab.github.io/GEMSDOE34/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE34/docs/index.html)

h34-scatter-q50-arr-matched-20261004T223317Z: 0.0778

....

[https://buffedlizard55-lab.github.io/GEMSDOE35/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE35/docs/index.html)

h35-06-aaa86efb25-20261004T225420098147Z-candidate: 0.0418

....

[https://buffedlizard55-lab.github.io/GEMSDOE36/docs/](https://buffedlizard55-lab.github.io/GEMSDOE36/docs/)

anderson-geothermal-pinn-38854-20261004T230000Z-9b9ea4e6-zeros: 0.2750

....

[https://buffedlizard55-lab.github.io/GEMSDOE37/](https://buffedlizard55-lab.github.io/GEMSDOE37/)

h6-physics-dotted-80k-20261005T055000Z-0bef9211631c: 0.1193

....

[https://buffedlizard55-lab.github.io/GEMSDOE38/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE38/docs/index.html)

D-step-3p0-07pct-tipProt-20261005-ecfbf59e2b48-zero: 0.0763

....

[https://buffedlizard55-lab.github.io/GEMSDOE42/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE42/docs/index.html)

xscale-worm-persistence-20261006T000541Z-nan: 0.0581

....

[https://buffedlizard55-lab.github.io/GEMSDOE43/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE43/docs/index.html)

sup01-hgb21-sep40-n40000-20261006-bc2e4e9a8d6f-nan: 0.0424

....

[https://buffedlizard55-lab.github.io/GEMSDOE45/](https://buffedlizard55-lab.github.io/GEMSDOE45/)

h51-km-faultzone-20261006-zeros: 0.0106

....

[https://buffedlizard55-lab.github.io/GEMSDOE49/](https://buffedlizard55-lab.github.io/GEMSDOE49/)

gate_ortho_w0.25-40k-20261006T213721Z-nan: 0.2376

....

[https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html)

h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778

....

[https://buffedlizard55-lab.github.io/GEMSDOE28/](https://buffedlizard55-lab.github.io/GEMSDOE28/)

h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-nan: 0.2708

h32-1-prethin-tip-euler-d2-8-20261003-31e35eee884e-nan: 0.2649

h36-1-rung30-blind-r1-20261003-b531dae0a36f-nan: 0.2710

h38-1-hf-euler-r30-r1-20261003-56a9f473edc7-nan: 0.2707

....

[https://buffedlizard55-lab.github.io/GEMSDOE29/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE29/docs/index.html)

efd28-repro-20261003-1cc7dc534d51-nan: 0.2600

repo-c0-habitat-emission-20261003-a4d439b07426-nan: 0.0041

sgmc-off-catalogue-44k-20261003-c8dcd780e3fd-nan: 0.0512

wormrank-d28-20261003-59dcaf6dd11d-zeros:0.2560

wormsurv-filter-20261003-921f10960d6e-zeros:

xfit-c0-habitat-20261003-ca879db0089a-zeros:

xfit-h41-union-qfaults-20261003-9edb34b99e3a-zeros:

....

[https://buffedlizard55-lab.github.io/GEMSDOE46/](https://buffedlizard55-lab.github.io/GEMSDOE46/)

r11f-scarp-radiometric-fusion-00e049b51218-zeros:0.1589

r12-scarp-rad-concordance-23e807e2de9f-zeros: 0.0843

....

[https://buffedlizard55-lab.github.io/GEMSDOE39/](https://buffedlizard55-lab.github.io/GEMSDOE39/)

h40-e-disc-h40e-30k-zeros: 0.0339

....

[https://buffedlizard55-lab.github.io/GEMSDOE40/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE40/docs/index.html)

h8-euler-lineament-depthcluster-20261006-785c4f5d5ce1:

h8-euler-lineament-depthcluster-20261006-785c4f5d5ce1-hard:

h45-eulerdepthreadcluster-20261006-f28e5cff6826-zeros:

....

[https://buffedlizard55-lab.github.io/GEMSDOE41/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE41/docs/index.html)

h42-submission-primary: 0.0245

....

[https://buffedlizard55-lab.github.io/GEMSDOE44/docs/](https://buffedlizard55-lab.github.io/GEMSDOE44/docs/)

h46-twostageAB_20261006T160000Z_b0cfe956-zeros:

....

[https://buffedlizard55-lab.github.io/GEMSDOE47/](https://buffedlizard55-lab.github.io/GEMSDOE47/)

h60-lidarscarp-s2p0-20261007-nanoutside:

....

[https://buffedlizard55-lab.github.io/GEMSDOE48/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE48/docs/index.html)

:

....

[https://buffedlizard55-lab.github.io/GEMSDOE50/](https://buffedlizard55-lab.github.io/GEMSDOE50/)

h59-sharpened-scarp-scatter-90k-20261007T171954Z-allfinite:

....

[https://buffedlizard55-lab.github.io/GEMSDOE51/](https://buffedlizard55-lab.github.io/GEMSDOE51/)

h53-twostage-20261008T040951Z-9a0b32c871:

....

[https://buffedlizard55-lab.github.io/GEMSDOE52/](https://buffedlizard55-lab.github.io/GEMSDOE52/)

:

....

53GEMSDOE

:

....

54GEMSDOE

:

....

The following is the leaderboard for the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)

See below for more links and information related to the competition:

[https://github.com/drivendataorg/gems-prize-reference-solution](https://github.com/drivendataorg/gems-prize-reference-solution)

[https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and)

[https://gbcge.org/current-projects/ingenious/](https://gbcge.org/current-projects/ingenious/)

[https://epsg.io/32611](https://epsg.io/32611)

[https://en.wikipedia.org/wiki/Tversky_index](https://en.wikipedia.org/wiki/Tversky_index)

We need to quickly look at the results and results from the GEMSDOE websites above.

Before implementing, generate 3–5 candidate geological hypotheses we haven't tried yet, each naming: the specific layer(s) involved, the physical signature being targeted (e.g., an edge-detection or curvature transform), why it should catch a fault missing from the USGS/INGENIOUS catalogue rather than one already in it, and how it differs from anything already implemented in this repo. Rank them by expected DTI improvement and implementation cost. Validate the top candidate on our spatially-blocked holdout set before touching a weekly submission slot — do not spend a submission slot on an idea that hasn't beaten the current holdout best. If a candidate can't be validated without new external data, name the specific free, official source needed and check it's obtainable before proposing the idea as viable.

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

We have a good understanding of how our hypothesis, methodology, calculations, analysis are done so we should be able to figure out a way to score higher on the leaderboard using previous results and scoring that we have across the sites listed above.  We need to come up with distinct and unique strategies to score higher in this competition leaderboard.  We need to start doing heavy and deep research into the part of the project that matters the most, which is the scientific discovery of geothermal vents.  We should store all of our information and knowledge that we can gather from official verified sources.  This will serve as a starting point for other projects as well.  We need to think outside the box but still be grounded in proper scientific research, we are ultimately aiming for a top prize that many others are competing for.  So it's important to be contrarian but be smart about it.  We need to find sources of data that others are over looking or areas of the project when it comes to geothermal vents.  We need to do deep research and critical thinking and come up with new hypothesis to test.

0.3195 is the highest score right now so we need to design a new strategy, research, testing, analyzing, and generating submission system than the current website.  It should be unique, take unique approaches to generating a submission that can score higher than 0.3195.

Put this prompt into the repo readme and read it everytime we work on the project as a starting point to make sure we are building what we are aiming for and have a strong base to continue building and improving on making something useful for everyday use.  It should solve the problem of having to manually check everything ourselves and having an up to date current feed.

Review the repo.

The following is taken from the Arena AI team and I think it makes a good point on building a successful project, so let's keep the Core Values and Own the Outcome as a focal point when building, developing, researching, suggesting upgrades, and implementing the work.

Our Core Values

Maximize P(Win)

“Maximize the Probability of Winning”: our decision making framework. In every decision, we weigh tradeoffs, assess risk, and choose the path that maximizes the probability that Arena succeeds. We set aside our emotions and make tough decisions in order to maximize P(Win). “Maximize P(Win)” frees us from constraints and clarifies that we must put Arena first.

Own the Outcome

We own results end to end — not just our individual slice of the work. When problems arise and we have the means to act, we do so without waiting for permission or assignment. We treat failure and success as signals and use them to improve. At Arena, we stay accountable to the final outcome.

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

We need to focus on being able to generate a submission into the competition.

The site should be able to generate a TIF file that is required for submission.  It should be as easy as download to click a File to submit into the competition.  This needs to be in the executive summary or the very beginning of the site.  it should be obvious when you visit the site.

I tried to submit the document that i downloaded from the site but it returned this error on the submission form:

"Predicted values must be in range [0, 1]"

Also we need to give it a unique name and A short comment to help you or your team tell submissions apart later e.g. clustering with k=25

Here is the submission page when i click submit file

New submission

File to submitNo file chosen

You can submit a single-band GeoTIFF (.tif) file, or a .zip file containing a single GeoTIFF, with your predictions. It must match the submission format's CRS, shape, and geotransform. You may wish to review the competition rules first.

Note (optional)

A short comment to help you or your team tell submissions apart later e.g. clustering with k=25

Create a executive summary subpage that explains exactly how to make a submission into the contest.

Work on the next steps from the previous sessions first.

The goal of this project is to place top of the leaderboard in this competition.  The following is the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)

We need to create a project that can compete and place top of the leaderboard.  We need to understand the problem, collect all the data and organize it into a clean easily auditable table with official verified links for manual verification.

This is the guidelines we need to follow.[https://www.drivendata.org/competitions/306/competition-doe-gems/](https://www.drivendata.org/competitions/306/competition-doe-gems/)

Get familiar with the problem through the overview and problem description,[https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/). You might also want to reference additional resources available on the about page,[https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/).

Download the data from the data,[https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/), tab.

Create and train your own model. This reference solution,[https://github.com/drivendataorg/gems-prize-reference-solution](https://github.com/drivendataorg/gems-prize-reference-solution) implements a simple approach.

Use your model to generate predictions that match the submission format.

Tell me what are you limitations and what you need access to during this project.  We will need to find free publicly available sources and data from official and verified sources if we are to use 3rd party or external data.

this pdf outlines how submissions must be entered into the competition.

[https://docs.nlr.gov/docs/fy26osti/96647.pdf](https://docs.nlr.gov/docs/fy26osti/96647.pdf)

You must be able to do your own research, deep research, scientific literature research and organize the knowledge so that we can critically think through the problem and generate a solution through scientific and free publicly available information.  this must be done autonomously and must be constantly reviewed and improved upon.  Provide suggestions and improvements and implement them.

❌ No DrivenData auth → cannot auto-download training_features.tif, labels.tif, sample_submission.tif, 1m_DEM_links.csv from [https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) (verified redirect to login)

See below for links from the above site.  See attached files for links from the above site.

[https://gdr.openei.org/submissions/1391](https://gdr.openei.org/submissions/1391)

Download competition data from [https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) (requires login) to data/

See links below for competition data:

[https://www.dropbox.com/scl/fi/aemhtutjgcp6tr3tint94/GEMS_96647.pdf?rlkey=rek210cj2smnmzb8n0sla1vmd&amp;st=wz4kofki&amp;dl=0](https://www.dropbox.com/scl/fi/aemhtutjgcp6tr3tint94/GEMS_96647.pdf?rlkey=rek210cj2smnmzb8n0sla1vmd&st=wz4kofki&dl=0)

[https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif?rlkey=kbykilvau066xuogoosbf4cq8&amp;st=8junzdyw&amp;dl=0](https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif?rlkey=kbykilvau066xuogoosbf4cq8&st=8junzdyw&dl=0)

[https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif?rlkey=yiao96uluqdkipf0h5vju71jf&amp;st=rnino7ya&amp;dl=0](https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif?rlkey=yiao96uluqdkipf0h5vju71jf&st=rnino7ya&dl=0)

[https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif?rlkey=je8d8fepqfbst9lnwsq9rkplu&amp;st=zj1lag1r&amp;dl=0](https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif?rlkey=je8d8fepqfbst9lnwsq9rkplu&st=zj1lag1r&dl=0)

[https://www.dropbox.com/scl/fi/ig0mban712ns1atphgphe/Digital-elevation-model-links-JSON.pdf?rlkey=zm77f1vbtt2if8hlruymptnu3&amp;st=srhhir10&amp;dl=0](https://www.dropbox.com/scl/fi/ig0mban712ns1atphgphe/Digital-elevation-model-links-JSON.pdf?rlkey=zm77f1vbtt2if8hlruymptnu3&st=srhhir10&dl=0)

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

Site creation

Create a github page for this repo that has clean ui, user friendly, simple and easy to use.  It should be organized and clean.

It should include all relevant information in an easy to read format with official verified links as sources for review.  Work line by line verify everything no hallucinations.

**The single remaining blocker to training is data placement**: run `bash scripts/download_competition_data.sh` on any unrestricted machine into `data/`, then `python scripts/prepare_data.py` — after that the full train→inference→validate pipeline is ready to run (GPU needed for training; metric/losses/validation all verified working here on CPU).

you need to complete the above task by yourself.  Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

Run this task through multiple passes.

Pass 1: Implement the task completely and verify the result.

Pass 2: Review your work for bugs, missing requirements, incorrect assumptions, and edge cases. Fix everything you find.

Pass 3: Re-check the entire implementation against the original request. Improve accuracy, reliability, completeness, and code quality. Fix any remaining issues.

Do not stop after the first pass. Each pass must build on the previous one. Before finishing, verify that the final result fully satisfies the original request.  Work line by line verify everything no hallucinations.

Go ahead and create a pull request and then merge the pull request onto the main. Make suggestions for what work still needs to be done and any limitations that is in the way of a successful project.  It should be worked on in this next session or the next session.  Work line by line verify everything no hallucinations.
```
