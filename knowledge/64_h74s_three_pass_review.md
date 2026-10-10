# H74S — three-pass closeout, evidence review, and limitations

**As of:** 2026-10-09 UTC

**Disposition:** **NEGATIVE / STOP. No H74S TIFF, no download, no selector eligibility, no organizer confirmation, zero competition slots used.**

**Scope:** review of the one frozen H74S run and its receipts only. H82 is a later repository round and is the current project result; H82 outcomes are not H74S outcomes. This document does not authorize another experiment, placement, or uniqueness waiver.

## Executive result

The preregistered two-view co-training/disagreement lane completed its full budget of **3 experiments in 1,652.1 seconds (27m 32.1s)**. The surface-raster gate passed against the **frozen 693-path branch snapshot** (later found incomplete for public `main`), then the final-dot audit returned **`DUPLICATE/STOP`** under the literal registered rule. The saturation-aware policy also returned `DUPLICATE/STOP`. The runner stopped before decoded-pixel uniqueness, final not-the-union, support-novelty, or TIFF-format validation. It correctly wrote no H74S TIFF. No result is eligible for download or submission.

The runner process itself exited with code 1 after writing the terminal negative state and run card: a negative branch returned a Python dict and `SystemExit(dict)` treated that object as an error. This is a **CLI exit-status defect**, not a missing run result. A transparently recorded post-run correction normalizes that CLI outcome and prevents reruns; it did not alter the frozen method, measurements, state, or run card and did not rerun H74S.

## Pass 1 — scope, preregistration, data, and source integrity

### Frozen design

- The final registration was frozen at `2026-10-09T19:23:20Z`; preregistration SHA-256: `9041c9dc04c366afd6b6c223b2ac8ce4ddc821687551a14ae99a678d9a09b38b`.
- Frozen hypothesis document: `knowledge/63_hypotheses_H74S_preregistered.md`, SHA-256 `054f809fc9b3b52af92776d3138d6f43c1698d93c204333ca8d15bc82010603c`.
- Exact executed runner SHA-256: `106080fde2eb6e4a50843d10eeea6e74f02a9c35635194dd24609abd70dfdf49`; the run card retains this hash. The post-run, CLI-only reviewed runner hash and rationale are in `evidence/h74s_postrun_code_correction.json`.
- One top-ranked hypothesis was tested: joint geodetic-strain (bands 4/7/8) plus seismicity (bands 10/16) as View A, against the unchanged surface/radiometric View B. The other three hypotheses in the preregistration remain untested. Rank order is qualitative research priority, not a numerical DTI forecast.
- Shared cached/view features, `evaluate_holdout.py`, shared metric-aware placement, and shared lane/submission tools were used. Catalogue-derived inputs were fold-visible only; visible fault pixels were masked exactly. Whole-segment spatial folds used an 80-pixel buffer. The registered DTI evaluator used pooled terms, alpha 0.2, beta 0.8, and a 300 m triangular kernel.
- The registration capped the work at 3 experiments or 2 hours, prohibited retuning/replacement placement after a stop, and required a duplicate stop at rank correlation >0.90 or >70% final dots within 3 px of any aligned registry raster.

### Registry and provenance boundary

The frozen gate covered **693 aligned raster paths in the checked-out branch snapshot**: 524 eligible entries from the stored core inventory, 105 local submission/download TIFF paths, and 64 refreshed public-owner-repository paths. The 64 extensions were downloaded/decoded/aligned with zero errors and their Git blob SHAs verified. The 2026-10-09 refresh pinned five public repositories:

| Public repository | Pinned commit | Raster paths |
|---|---|---:|
| [GEMSDOE53](https://github.com/buffedlizard55-lab/GEMSDOE53/commit/609cb0081db6ff9ca8ac3843c84ec3657a970c02) | `609cb0081db6ff9ca8ac3843c84ec3657a970c02` | included in 64 |
| [GEMSDOE54](https://github.com/buffedlizard55-lab/GEMSDOE54/commit/ba2a5ba59d3f3e0edf456dfc09874b5d38ca443a) | `ba2a5ba59d3f3e0edf456dfc09874b5d38ca443a` | included in 64 |
| [55GEMSDOE](https://github.com/buffedlizard55-lab/55GEMSDOE/commit/009754f11d6d226abf4e6c5dc77220c76be9a530) | `009754f11d6d226abf4e6c5dc77220c76be9a530` | included in 64 |
| [56GEMSDOE](https://github.com/buffedlizard55-lab/56GEMSDOE/commit/94ea54980bde5e0be3de086c8a1d57f99dad02fe) | `94ea54980bde5e0be3de086c8a1d57f99dad02fe` | included in 64 |
| [57GEMSDOE](https://github.com/buffedlizard55-lab/57GEMSDOE/commit/f639e272f5cf7437d1ca725c2a53cacaace1caf8) | `f639e272f5cf7437d1ca725c2a53cacaace1caf8` | included in 64 |

These are **public owner-mirror** bytes, not organizer-authenticated submissions. Private/unlinked submissions are outside the census. No organizer portal receipt, current official leaderboard, or organizer-confirmed score was checked. The refreshed paths, commits, Git blob IDs, file hashes, and decoded hashes are recorded in `evidence/h74s_prior_extension.json`; the full source resolution for the decisive gate entries is `evidence/h74s_lane_source_resolution.json`.

### Post-run registry-coverage discovery

After H74S had stopped, fetching the updated public `origin/main` to resolve this PR's merge conflict revealed that the frozen 693-path snapshot was not a complete snapshot of public GEMSDOE52 history. A parallel H74 research TIFF (commit `9d891a61d9570830124c45d2477ff969134ac3a1`, file SHA-256 `0dea78bc8e276a8276de94a169e59ffac43234cef6a6f978f13f0788c6232f26`) had been merged into `main` at `2026-10-09T19:16:40Z`, **before** the H74S freeze, but was absent from this session's stale checkout. A second parallel H75 TIFF (commit `2fc03cd6093f0aa8824d21d7c3f092e7f33d6028`, file SHA-256 `b97691584d514ab1925d9fff2b61c410be86bdc0bc8c844dfdaa6257a4ea7a16`) was committed at `19:41:26Z` and reached `main` at `19:44:21Z`, while H74S was still running. Neither raster was included in the 693-path lane receipts.

This is a material census-coverage limitation: the surface `PASS` is scoped to the frozen branch snapshot, **not** every public aligned raster available on `main` at freeze/run time. No decoded/pixel lane metric was retroactively measured against the H74/H75 files: the frozen round was terminal, the mandatory final-dot stop had already been proven by included priors (literal 1.0 and informative-only 0.910799), and no final TIFF/dot raster was saved for a separate audit. The added priors cannot remove that already-observed duplicate witness, so the negative/no-download/no-slot disposition remains; this notice does not claim an exhaustive current registry or authorize a rerun. The metadata-only discovery and hashes are in `evidence/h74s_postfreeze_registry_notice.json`.

## Pass 2 — experiment, holdout, and stop-rule review

### Leakage, view independence, and one exchange

- The leakage canary examined all 42 features across four spatial folds. Maximum held-out canary AUC was **0.668678** (maximum fitted top-five feature AUC 0.666555); there was **no AUC >0.90 alarm**.
- The negative-error independence diagnostic used **2,089 spatial blocks** and held-out catalogue-zero pixels, which are proxies, not verified fault absences. Maximum absolute blockwise correlation was **0.0549296**, below the preregistered 0.60 abandon threshold. This permitted the single registered exchange; it is not proof of conditional independence.
- Buffered whole-segment pseudo-labeling made exactly one round of exchange: **15,259 pixels in 873 segments** across both directions and four folds. The frozen donor/receiver ranks and segment limits were used; no second exchange was made.
- Fold OOF AUCs before exchange (View A / View B) were `0.4960/0.6625`, `0.4848/0.7684`, `0.4623/0.6112`, and `0.5368/0.6952`. After exchange they were `0.4982/0.6634`, `0.4729/0.7641`, `0.4902/0.6156`, and `0.5337/0.6918`. These are diagnostics, not competition scores.

### HOLDOUT-DTI, matched-budget caveat, and control

Every score below is a local **`HOLDOUT-DTI`**, evaluator `gems52-pooled-hide-v1`, pooled over **53,186 withheld positive pixels**, with alpha 0.2, beta 0.8, 300 m triangular radius, and a spatial-block 95% interval. None is an organizer or leaderboard score.

| Holdout arm | DTI | 95% CI |
|---|---:|---:|
| A-only disagreement after the one exchange | 0.008975 | [0.004699, 0.014496] |
| Single-A baseline | 0.011083 | [0.004801, 0.019603] |
| Single-B baseline | 0.061461 | [0.048927, 0.074703] |
| Maximum-view-union control | 0.046885 | [0.035853, 0.059859] |
| Disagreement before exchange | 0.002579 | [0.000803, 0.005195] |
| Random control | 0.013352 | [0.011518, 0.015349] |

**The matched comparison is invalid:** the A-only arm filled 1,264 dots in folds 0, 1, and 3, but only **1,126/1,264** in fold 2. `matched_comparison_valid=false`; there is no valid paired candidate-minus-single-B result. Do not describe these numbers as a matched win. The measured A-only pooled DTI is below both the random and single-B holdout controls; that is an underfilled-arm diagnostic, not a promotion result.

The fixed 9,400-dot-per-fold single-B control reproduced its prior **HOLDOUT-DTI** reference: **0.174517** [0.154024, 0.195269] over the same 53,186 withheld positives, within the preregistered 0.001 tolerance of 0.174571. All four control folds filled. This reproduces a local holdout control only; it says nothing about the organizer leaderboard.

The four holdout A-only arms were not equal to the max-view-union placement (Jaccard 0.00637, 0.01649, 0.00336, and 0.00317 by fold). This verifies the **holdout disagreement arm** was not the view union. The final full candidate's separate not-union gate was ordered after the final-dot stop and therefore was **not run**; no final-candidate union result is claimed.

### Lane audit: surface passed, final dots stopped

- **Surface gate:** literal and policy `PASS` across all 693 paths in the frozen branch snapshot, zero errors. Maximum Spearman correlation was **0.0335709**, against the local accessible prior `submission/gems52-ctd5-cover-disagreement-20261008-a24c35d1-b58bae0f0e.tif`. That local path has no pinned owner-census mapping.
- **Final dots:** the one fixed metric-aware placement contained **5,056 dots**. The literal all-prior check found no rank-correlation offender (maximum Spearman **0.0152790**), but found **38** >70% near-dot offenders; the maximum fraction within 3 px was **1.0000**. The literal maximum was a public owner-mirror H48 diagnostic raster at commit [`36d9785e28a81e859c71f4058c639ffba4b7f327`](https://github.com/buffedlizard55-lab/GEMSDOE48/blob/36d9785e28a81e859c71f4058c639ffba4b7f327/docs/downloads/diagnostics/GEMSDOE48-H56-OWDS-B2xH33D-20261007-1f7b5a4f18db-plausibility.tif). That raster is a registry path covered by the literal all-prior rule; it is not an organizer-authenticated submission.
- **Policy cross-check:** even excluding 15 universal-coverage probes, the maximum informative-prior near-dot fraction was **0.910799** (23 offenders), against [15GEMSDOE `gems-cleanup-a-20260928T195952Z-curv_scarp.tif`](https://github.com/buffedlizard55-lab/15GEMSDOE/blob/8c94b0f83f22999032ba8a29c523af7ae6cf5e76/docs/downloads/gems-cleanup-a-20260928T195952Z-curv_scarp.tif). This independently remains over 0.70.
- **Decision:** literal `DUPLICATE/STOP` is binding. No waiver, another placement, threshold change, rerun, or TIFF write. The policy check is additional diagnosis, not a substitute for or relaxation of the literal rule.

### What was not reached

Because the final-dot stop was mandatory, no H74S candidate TIFF exists. Consequently there is no TIFF file hash, decoded-pixel uniqueness comparison/result, final full-map not-union result, support-novelty result, GeoTIFF-format validation, or download. The lane receipt includes a digest of the in-memory 5,056-dot mask, but that digest is not a uniqueness comparison against priors. The existence of the holdout not-union diagnostic does not substitute for those candidate-level gates.

## Pass 3 — release state, implementation review, tests

### Download, selector, submission

The authoritative run card records `verdict=negative`, `downloadable=false`, `submit_eligible=false`, `organizer_confirmed=false`, `weekly_slot_used=false`, `raster_sha256=null`, and `submission_name=null`. No candidate TIFF or ZIP was written. No selector decision was made, no submission slot was spent, and no organizer confirmation exists. The working conclusion is **do not download or submit an H74S file**; none is available.

### Post-run CLI correction

The original process returned code 1 only because Python's `SystemExit` received the negative run-card dict. The terminal state is `negative`, stage `E3-final-dot-lane`, with a complete card and the registered duplicate stop. `evidence/h74s_postrun_code_correction.json` records both runner hashes, the unchanged run-card hash, the exact CLI-only correction, and that no experiment was rerun. The correction maps a run-card dict to process code 0, rejects reruns if the tracked card exists, and preserves the card on such rejection. It does not change scientific/method logic or any receipt measurement. The run card keeps the exact hash of the code that executed the experiment.

### Verification

- `.venv/bin/python -m py_compile scripts/run_h74s.py`: passed.
- `.venv/bin/pytest -q`: **437 passed, 2 skipped, 55 warnings** (52.52 s). Warnings are the existing rasterio `Affine` multiplication pending-deprecation warnings.
- `git diff --check`: passed after the CLI correction; final review must repeat after documentation edits.
- Freeze verification with the explicit post-run correction receipt: passed. Registration SHA and original executed runner SHA remain intact.

## Three-to-five geological hypotheses (registered before testing)

The frozen list is in `knowledge/63_hypotheses_H74S_preregistered.md`; only Rank 1 was tested:

1. **H74S-A — coupled strain–seismic activity beneath a quiet surface (tested):** View A bands 4/7/8 plus 10/16; View B unchanged surface/radiometric stack. Hypothesized joint geodetic deformation and seismicity despite weak surface expression. Mimics include earthquake swarms/aftershocks and interpolation seams. Result: negative as above.
2. **H74S-B — seismicity-only directional gradient plus surface abstention (untested):** bands 10/16. Mimics include geothermal swarms and aftershocks. Lower implementation cost, lower expected priority; not scored.
3. **H74S-C — conductivity–basement edge pair supported by gravity gradients (untested):** bands 17/15/18/11 with surface-view abstention. Mimic: lithologic or conductive clay/alluvium boundary. Medium-high fold-safe feature cost; not scored.
4. **H74S-D — multiscale strain-tensor discontinuity coherence (untested):** transform of bands 4/7/8 against unchanged surface view. Mimics include loading or gridding seams. Lowest relative priority given weak prior strain-only results; not scored.

These are hypothesis priorities, not score projections. The old H72/H73 results are not reused as H74S results.

## Source-linked context and limitations

- Competition task and data entry points: [DrivenData GEMS problem](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) and [data tab](https://www.drivendata.org/competitions/306/competition-doe-gems/data/). The data tab was login-walled in the repository's source review.
- Co-training reference: Blum & Mitchell, [“Combining Labeled and Unlabeled Data with Co-Training,” COLT 1998](https://doi.org/10.1145/279943.279962). Conditional independence and view sufficiency are assumptions, not facts established by the small measured error correlation.
- Geologic data context: [DOE GDR submission 1391 / INGENIOUS](https://gdr.openei.org/submissions/1391) and the [USGS GeoDAWN release](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and). H74S used existing competition bands and cached/shared features, not a newly fetched earthquake catalog.
- `HOLDOUT-DTI` measures performance on spatially withheld known-catalogue segments. Its catalogue-zero pixels are not confirmed absences, and its intervals do not predict or certify organizer leaderboard performance.
- Public mirrors cannot reveal private/unlinked competition submissions. No current organizer leaderboard, active competition status, weekly slot availability, or organizer score was checked. Public GitHub commits establish mirror provenance, not organizer authenticity.
- The negative result is specifically that this frozen H74S candidate violates the registered final-dot uniqueness rule and the matched A-only holdout budget. It is not evidence that the other three hypotheses work. Any future work would require its own explicit authorization, preregistration, complete refreshed registry, and budget; do not continue this stopped round.

## Receipt index

| Artifact | Contents |
|---|---|
| [`evidence/h74s_run_card.json`](../evidence/h74s_run_card.json) | Completed machine-readable negative result, stop reason, scores, budgets, and submission status |
| [`registry/h74s_preregistration.json`](../registry/h74s_preregistration.json) | Frozen registration |
| [`evidence/h74s_preregistration_freeze.json`](../evidence/h74s_preregistration_freeze.json) | Freeze hashes, gate inventory, and pre-run checks |
| [`evidence/h74s_canary.json`](../evidence/h74s_canary.json) | Per-feature leakage-canary measurements |
| [`evidence/h74s_independence.json`](../evidence/h74s_independence.json) | Pre-exchange blockwise error-independence audit |
| [`evidence/h74s_holdout.json`](../evidence/h74s_holdout.json) | Four-fold pooled HOLDOUT-DTI and matched-fill report |
| [`evidence/h74s_control_reproduction.json`](../evidence/h74s_control_reproduction.json) | 9,400-dot/fold single-B control reproduction |
| [`evidence/h74s_lane_surface.json`](../evidence/h74s_lane_surface.json) | Surface gate receipt |
| [`evidence/h74s_lane_dots.json`](../evidence/h74s_lane_dots.json) | Literal and policy final-dot lane receipts |
| [`evidence/h74s_lane_source_resolution.json`](../evidence/h74s_lane_source_resolution.json) | Owner commit, path, and hashes for decisive registry rasters |
| [`evidence/h74s_postrun_code_correction.json`](../evidence/h74s_postrun_code_correction.json) | Transparent CLI-only hardening record; confirms no rerun |
| [`evidence/h74s_postfreeze_registry_notice.json`](../evidence/h74s_postfreeze_registry_notice.json) | Post-run disclosure that parallel H74/H75 public-main TIFFs were absent from the frozen 693-path inventory |
| [`evidence/h74s_prior_extension.json`](../evidence/h74s_prior_extension.json) | Refreshed 64-path public owner-repository census |
