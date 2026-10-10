# H87 — result, review passes, and limits

**Verdict: NEGATIVE. DOWNLOAD YES (inspection only); SUBMIT NO.** The TIFF is a new decoded pattern in the accessible local inventory and passes the local file-format validator and both literal lane checks. It does not qualify for a weekly slot: View A fails the preregistered sufficiency screen, no pseudo-label exchange was run, and the A-only holdout arm cannot fill the fixed placement budget. No leaderboard improvement or organizer score is claimed.

## Frozen hypothesis and input audit

The candidate slate and H87-A protocol were written before the successful model fit and hash-pinned in `registry/h87_preregistration.json`:

- Preregistration: `knowledge/80_h87_hypotheses_preregistered.md`
- SHA-256: `5d9d064d5c7940faf6294d8b9c7df10b954eeac179da31f6e13ff080b5617fad`
- Four ranked hypotheses are documented there, with bands, mechanism, off-catalogue rationale, differences from prior work, ordinal expected lift, cost, and availability. H87-A was the only locally runnable strict-view test inside the time budget.
- Input bytes match `registry/data_manifest.json`; the manifest and receipts are owner-mirrored integrity pins, **not organizer authentication**. No external data were used.
- Shared `work/r2/features` cache: 4,593,171 eligible pixels after all-band validity and 36-pixel support erosion. The fixed sample grid has 5,167,373 finite cells. The label raster contains 60,988 catalogue positives and 5,106,385 catalogue-zero cells in that domain; zeros are proxies, not verified fault absence.
- View A has 60 label-free DVA columns derived only from bands 2, 13, 15, 17, 7, and 16. View B has 19 shared-cache raw/derived columns from bands 6, 12, and 19. The two registered feature lists have **zero overlap**. Band 6's metadata identity conflict remains open; its use here is confined to B and is recorded as provisional. No band-17 thermal-conductivity interpretation is made; band 17 is the in-stack surface-conductivity field.

## Experiment and holdout results

All scoring uses the shared `gems52.evaluate_holdout` implementation, version `gems52-pooled-hide-v1`: whole 8-connected segments hidden by `label-blind-quadrants-v2`, 80-pixel train/evaluation buffer, visible-label pixel-exact masking, pooled DTI (`alpha=0.2`, `beta=0.8`, 300 m triangular kernel), and paired 20 km physical-block bootstrap (1,000 draws).

### Leakage canaries and exchange gates

- Highest direction-insensitive single-feature canary AUC: **0.6543**, below the frozen 0.90 leakage alarm. Per-fold maxima: 0.6014, 0.6543, 0.6243, 0.6271.
- View A mean region OOF diagnostic AUC: **0.4920** (folds 0.5076, 0.5300, 0.4562, 0.4743), below the predeclared 0.60 sufficiency screen.
- View B mean region OOF diagnostic AUC: **0.6656** (folds 0.6469, 0.7487, 0.6013, 0.6655), above that screen.
- The block error diagnostic was defined on **2,097** 50×50-pixel blocks and 4,537,871 included negative predictions. The maximum absolute Pearson/Spearman correlation was **0.0782**: negative-MSE Pearson/Spearman 0.0636/0.0782; negative-FPR Pearson/Spearman −0.0135/0.0666. This is weak correlation on catalogue-zero proxies, **not** evidence of conditional independence.
- Although the independence diagnostic itself was measured below 0.60, the combined exchange gate failed because View A did not meet sufficiency. **No pseudo-labels were exchanged.**

The View-A/View-B AUCs above are diagnostic AUCs, not DTI scores. Details and sample counts are in `evidence/h87_canary.json` and `evidence/h87_fit.json`; the block calculations are in `evidence/h87_independence.json`.

### Hide-and-recover DTI

| Arm | HOLDOUT-DTI | 95% physical-block CI | Placed per fold | Budget status |
|---|---:|---:|---:|---|
| A-only disagreement (primary) | 0.020945 | [0.016885, 0.025601] | 7,162 / 3,454 / 1,209 / 1,823 | **Underfilled; invalid for matched-budget ranking** |
| Single A | 0.062855 | [0.051786, 0.074869] | 9,400 each | Filled |
| Single B | 0.174577 | [0.154860, 0.196354] | 9,400 each | Filled |
| `max(A,B)` union control | 0.144927 | [0.127059, 0.164959] | 9,400 each | Filled |
| Matched random | 0.081343 | [0.071337, 0.091382] | 9,400 each | Filled |

There were **53,186 withheld positive pixels** across the four folds. The A-only arm placed 13,648 cells in total against a 37,600-cell four-fold target. Its reported DTI and bootstrap interval describe that actual sparse emission; they are **not** an equal-budget comparison. The calculated paired differences are retained in `evidence/h87_holdout.json` for audit, explicitly marked invalid for the fixed-budget gate. The point-estimate leader among the filled controls is single B, but the A-only result is not called a comparable challenger. No control budget was altered and no extra pixels were added to rescue the hypothesis.

The result is enough to reject promotion of H87-A under its frozen protocol; it is not enough to establish that geophysical co-training is universally ineffective. The proposed geophysical-only representation was not sufficient on these folds, and disagreement constrained the A-only support too strongly to meet the registered emission budget.

## New research TIFF and gates

- Research TIFF: [`submission/gems52-h87-dva-aonly-13966px-20261010.tif`](../submission/gems52-h87-dva-aonly-13966px-20261010.tif)
- Direct download: [`docs/downloads/h87-candidate.tif`](../docs/downloads/h87-candidate.tif)
- Single-TIFF ZIP: [`docs/downloads/h87-candidate.zip`](../docs/downloads/h87-candidate.zip)
- File SHA-256: `3fc7708422774f3766d12ecf1fa7e5a3493117ee67c61e1b19dadbe0b6f2d704`
- Decoded-pixel SHA-256: `4a8ebb62ecbf6d1bee1414334d1b0e984854bc3e9cc460a452c8331eb8ea4b89`
- 13,966 binary positive cells (the 3-pixel spacing rule could not place 37,654); one-band float32; 3730×3292; EPSG:32611; 100 m; finite values in [0,1], zero outside the eligible footprint; 92,018 bytes.
- The shared on-disk format validator passed: no NaN/infinity, CRS/shape/transform exact match, values [0,1], no positive mass outside the eligible footprint. This is a local validation, not portal acceptance.
- Decoded uniqueness passed against **129 accessible local priors** (55 distinct decoded prior patterns): no identical prior, complete aligned audit, 71.68% of emitted support outside the prior union, and the shared support-novelty gate passed. This scope cannot establish uniqueness against private or unlinked submissions.
- Literal lane test on the surface before placement: maximum Spearman 0.0277, PASS. Literal final-dot test across the same 129 priors: maximum Spearman 0.0112; greatest directed within-3-pixel fraction 0.3273 (H59 local raster), below the 0.70 stop bar; PASS. `evidence/h87_lane.json` preserves both complete reports.
- Not merely a view union: candidate Jaccard was 0.0319 versus equal-budget single A, 0.0000 versus single B, 0.0139 versus equal-budget `max(A,B)`, and 0.0211 versus the union of separately placed single-view supports; exact equality to none.
- The compressed geological review file has one row for every emitted cell, with coordinates, A/B ranks, all 12 A-view two-lag DVA anisotropy values, all 19 View-B cache features, and raw values for the six A input bands. Each row now names its leading A band (the greatest mean of its two normalized-lag anisotropy features), gives a band-specific physical interpretation, a specific non-fault mimic, and a falsifier: [`docs/downloads/h87-a-only-reasoning.csv.gz`](../docs/downloads/h87-a-only-reasoning.csv.gz). This relative per-cell channel ranking is a review aid, not calibrated significance; all cells remain **model review targets, not verified faults, vents, or geothermal systems**. The rebuilt CSV is 5,872,421 bytes, SHA-256 `156beeec79d36d6ff1ecf554a16eea909962b69c6a92b49db3efcef07d195856`.

The short submission name is `h87-dva-aonly-13966px-20261010` (34 characters). Note (94/140 characters): `H87 geophysical DVA vs surface/radiometric abstention; 3px spaced; research only; no slot used`.

**Post-run evidence boundary:** after the successful run, the only model-adjacent update was rebuilding the all-candidate review CSV from the existing final coordinates and pinned shared feature cache to add candidate-specific band explanations and updated its receipts. No model fit, holdout, selector, TIFF write, lane/uniqueness test, upload, or organizer-score request was run again; H87's scientific metrics and TIFF are unchanged.

## Three review passes and claim discipline

1. **Pre-fit / hypothesis pass:** verified the candidate slate and frozen hash; checked the manifest pins, band descriptions, strict view separation, 36-pixel feature support, whole-segment fold receipts, label-blind evaluation quadrants, visible-label masking, and no external-layer dependency. H82 was not misrepresented as a prior strict-view experiment.
2. **Statistical / leakage pass:** independently checked the per-channel canaries, per-view OOF AUCs, negative-error block count/correlations, combined exchange decision, withheld-positive count, fixed per-arm budgets, DTI formula/evaluator ID, and the validity of the paired contrast. The underfilled candidate is explicitly marked non-comparable; no score projection or organizer claim is made.
3. **Artifact / physical interpretation pass:** reopened the TIFF; checked its decoded SHA, metadata, finite binary values, 3-pixel spacing placement, exact local prior census, surface and final lane statistics, candidate-vs-union comparisons, single-file ZIP round-trip, short note/name, and all-row geology review. Non-fault alternatives include lithologic/basin-fill boundaries, inversions or gridding seams; none of the detections is asserted to be a fault.

A first engineering attempt failed before the complete cache existed because the callback did not accept the shared builder's `flush=True`; the successful cache was rebuilt and hash-checked. A later run reached its first A-view fold fit but failed when saving because `work/h87/` did not yet exist; no fit receipt or prediction checkpoint from that interruption is used. The runner was fixed to create its output directory. These execution irregularities and their scope are logged in `evidence/h87_process_notes.json`; they did not change the frozen hypothesis, DTI evaluator, final raster, or the successful run's metrics.

## Explicit decision and next work

**DOWNLOAD: YES, for inspection/research. SUBMIT: NO.** Do not use a weekly competition slot for this TIFF. No organizer receipt exists and no H87 submission has been uploaded. Any later upload requires the separate weekly selector to choose a candidate; this run did not select or promote one and used zero slots.

If pursuing this lane later, do not tune H87-A on the same folds. A new preregistration should first investigate why the geophysical-only DVA view loses regional ranking (including measurement dependence in basement-depth products), then test a genuinely sufficient View A or discontinue co-training. Keep the strict view split, error-block test, single-view controls, equal-budget requirement, and local-prior/lane gates. The prior public leaderboard snapshot and sibling-repository score attributions are not organizer receipts, and this H87 run does not establish any score above the prior reported 0.2778 or the recorded public top.

## Manual-review sources

- [Competition metric/data page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
- [Blum & Mitchell, *Combining labeled and unlabeled data with co-training* (DOI)](https://doi.org/10.1145/279943.279962)
- [DOE/OSTI blind-system and structural-setting inventory](https://www.osti.gov/biblio/1724082)
- [USGS GeoDAWN survey context](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and)
- [USGS Lund North blind-system investigation](https://www.usgs.gov/publications/exploration-blind-geothermal-systems-eastern-great-basin-utah-update-lund-north)
