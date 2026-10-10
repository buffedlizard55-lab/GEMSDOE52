# 80 · H90 results and limits (2026-10-10)

Read with `knowledge/77` (the standing brief, verbatim), `knowledge/78` (why 0.2778; the metric identity), `knowledge/79` (H86 ranked hypotheses) and `registry/irregularities.json` IR-H90-001…009.

**Lane (the brief's method paragraph, unchanged):** co-training between View A (potential-field and subsurface) and View B (surface DEM), disagreement as the discovery signal, whole-segment blocks, single-view baseline, not-the-union test.

## 0 · Answer in one table

| Question | Answer | Evidence class |
|---|---|---|
| Is there a unique, format-valid TIF to download? | **Yes.** `docs/downloads/h90-candidate.tif` (ZIP with name and note: `docs/downloads/h90-candidate.zip`). 37,654 binary cells, EPSG:32611, 3730×3292, finite, in [0,1]. | local validator, independent re-read |
| Is it OK to **download**? | **Yes, for research and review.** | repo convention (H60D, H62, H85 precedent) |
| Is it OK to **submit**? | **No.** Holdout is below the best comparable arm on the same instrument, the disagreement field is below random on the competitor-realistic pool, and the literal dot-lane gate returns DUPLICATE/STOP. | HOLDOUT-DTI + gates |
| Does the reproduction of the lane hold on restored bytes? | **Yes.** Every checked number matches the committed receipts (see §2). | reproduction |
| Did we find a bug in the shared holdout? | **Yes, two instrument issues** (IR-H90-001 ring rule; IR-H90-003 negative sampler). | measured |
| Did we beat 0.2778? | **Not demonstrated.** The holdout cannot say anything about the public board: the repo measured Spearman −0.10 between holdout DTI and board score (`AGENTS.md`; IR-H77-005; knowledge/78 §2). | — |

## 1 · What was run (budget: 3 experiments, 2 hours)

| # | Run | Output | Experiment? |
|---|---|---|---|
| 0 | Restore the three official rasters and seven external layers via `scripts/download_competition_data.sh` (SHA-256 verified) | `data/`, `data/restore_receipt.json` | no (setup) |
| R | Reproduce H60D on restored bytes: `scripts/run_h60d_cotrain.py` | `evidence/h90_h60d_reproduction.log` | no (verification) |
| E1 | **H87-L** clean-sampler leakage audit (pre-registered, `registry/h87_negclear_preregistration.json`) | `evidence/h90_negclear_audit.json` | yes (1 of 3) |
| E2 | **H87-R** legal-pool ring audit (pre-registered, `registry/h87_ring_preregistration.json`) | `evidence/h90_ring_audit.json` | yes (2 of 3) |
| E3 | **H90-C** candidate build from the clean-sampler OOF fields (no new fit beyond E1) | `submission/gems52-h90-cleanoof-disagree-37654px.tif` | yes (3 of 3) |

Compute: about 40 minutes wall clock (21:33–22:06 UTC) on 2 CPUs, 3.9 GB RAM. Slots used: 0. Submissions made: 0.

## 2 · Reproduction on restored bytes (verification, not a new score)

Every number below is read from a file, not typed from the README.

| Quantity | Committed receipt / README | Reproduced here |
|---|---|---|
| Independence max \|r\| (block OOF errors) | 0.176 | 0.17604 |
| Withheld positives, 4 hide folds | 36,411 | 36,411 |
| Leakage canary worst layer | 0.7136 | 0.7136 (`B_lidar_step_max_grad`) |
| Co-training AUC change, View A / View B | −0.0067 / −0.0104 | −0.0067 / −0.0104 |
| Shipped View B pooled HOLDOUT-DTI at 37,654 px | 0.006419 [0.005873, 0.006892] | 0.006419 [0.005873, 0.006892] |
| Shipped dis_contrast | 0.004109 [0.003597, 0.004948] | 0.004109 [0.003598, 0.004948] |
| Shipped View A | 0.004031 [0.003438, 0.004445] | 0.004031 [0.003438, 0.004445] |
| Shipped clf_union | 0.006140 [0.005598, 0.006610] | 0.006140 [0.005598, 0.006610] |

The reproduction differed from the committed `evidence/h60d_cotrain.json` only in `round` label and `runtime_s`. The tracked file was restored, so the repo carries no cosmetic diff.

## 3 · H87-L: the sampler (E1)

Shipped negatives come from the whole footprint and are cleared by 5 px from the full catalogue, including held-out truth. The clean arm fits each view on fit-region positives and fit-region negatives only, with the fit catalogue for clearance.

| Arm (37,654 px, HOLDOUT-DTI, H60D instrument) | Pooled | Fold-bootstrap 95% CI |
|---|---:|---|
| shipped view_B | 0.006419 | [0.005873, 0.006892] |
| clean view_B | 0.006533 | [0.005923, 0.007093] |
| shipped view_A | 0.004031 | [0.003438, 0.004445] |
| clean view_A | 0.003728 | [0.002610, 0.004260] |
| shipped dis_contrast | 0.004109 | [0.003598, 0.004948] |
| clean dis_contrast | 0.003850 | [0.003519, 0.004220] |
| shipped clf_union | 0.006140 | [0.005598, 0.006610] |
| clean clf_union | 0.006498 | [0.006021, 0.006908] |
| random | 0.001992 | [0.001904, 0.002120] |

Paired, clean minus shipped (fold bootstrap, 4 folds):

* view_A: **−0.000389 [−0.000832, −0.000104]**. The shipped View A holdout is inflated by about 10% (CI excludes zero).
* view_B: +0.000108 [−0.000040, +0.000348]. Not inflated (CI spans zero).
* dis_contrast: −0.000218 [−0.000728, +0.000234]. Spans zero.
* clf_union (not pre-registered as primary): +0.000329 [+0.000065, +0.000615]. The clean sampler raises the shipped union; the CI excludes zero. This is reported, not used for a verdict.

Pre-registered verdict: **MIXED** (not "leak confirmed", because View B's CI does not sit below zero, and not "no leak", because View A's does not span zero). Leakage canary max single-layer AUC 0.7454 < 0.90 on fields from both samplers (fold-region canary; IR-H90-004).

## 4 · H87-R: the ring (E2)

Shipped legal pool: `valid & ~dilate(full catalogue, 2 px) & ~dilate(visible, 2 px)`. Truth pixels are in this pool **0 times in all 4 folds**: the credit available to a dot comes only from the 200–300 m annulus around each held-out trace. Variant: `valid & ~dilate(visible, 2 px)`, which is what a competitor can see.

| Arm (37,654 px, same OOF fields, same scorer) | Shipped ring | Visible ring | Ratio |
|---|---:|---:|---:|
| view_B | 0.006419 | **0.053706** | 8.37 |
| clf_union | 0.006140 | 0.050728 | 8.26 |
| random | 0.001992 | 0.041594 | 20.9 |
| dis_contrast | 0.004109 | **0.031379** | 7.64 |
| view_A | 0.004031 | 0.020507 | 5.09 |

Arm order **changes**. Shipped: view_B > union > dis_contrast > view_A > random. Visible ring: view_B > union > **random > dis_contrast > view_A**. The disagreement field loses to random on the pool a competitor faces.

Two consequences:

1. The shipped H60-family holdout is an annulus test, not the competitor-realistic test. This may explain part of the ~27× scale gap to the H82/H85 instrument (IR-H90-007), but this round did **not** verify that attribution; it needs both arms on one instrument.
2. The co-training disagreement signal is **negative** on the visible-ring pool. Single-view B and the union remain above random under both pools.

## 5 · H90-C: the candidate file (E3)

* Field: `dis_contrast = max(pA_clean − pB_clean, 0)` on clean-sampler OOF fields, full footprint covered (5,165,840 px, 0 uncovered).
* Legal pool: footprint ∩ sample-submission footprint, outside the 200 m ring of the full catalogue, outside the support of **all 142** accessible priors (`gems52.gates.find_priors`; 2,037,988 px removed). Pool 3,185,615 px.
* Emitter: `gems52.h57.iso_select(score, pool, 37654, min_px=3, nms_px=5)`, the registered H60D emitter.
* Writer: `gems52.grid.write_geotiff_portal_exact(..., outside="zero")`.

Gates and measurements (all from `evidence/h90_build.json`, independently re-checked):

| Gate | Result |
|---|---|
| Format (CRS, shape, transform, band, dtype) | PASS (no problems) |
| Values | exactly {0, 1}; finite everywhere; in [0, 1]; 0 positives outside footprint; 0 NaN inside footprint |
| Uniqueness (decoded pixels, 142 priors) | canonical pattern unique: True; novel fraction 1.0 |
| Exact pixel overlap with any prior | 0 (by construction; spot-checked against 5 priors) |
| Surface lane gate (max \|ρ\| vs any registry raster; bar 0.90) | 0.0883 PASS |
| Dots lane gate, 3 px proximity (bar 0.70) | **0.9981 vs `13gems_…r13-lattice-s5…` → literal DUPLICATE/STOP.** H60-6 (knowledge/30) excludes calibration rasters from this component; under that registered correction the next-highest proximity is 0.6534 < 0.70 and the dots gate would PASS. Owner decision (IR-H90-006) |
| Dots proximity vs H60D's own dis_contrast file | 0.6534 (under the bar, high; IR-H90-005) |
| Not-the-union (overlap with union-of-views emission) | 0.0147 PASS |
| Ring gate (nearest emitted cell to a catalogue trace) | 223.6 m ≥ 200 m PASS |
| Holdout of this arm (clean dis_contrast, per-fold emission) | 0.003850 [0.003519, 0.004220] (H60D instrument) |

**Honest read of the file.** It is pixel-unique and inside the lane's emitter and pool rules. It is a near-sibling of H60D: 65% of its dots lie within 3 px of H60D's dots, and its holdout is below the shipped H60D arm (paired −0.000218, CI spans zero). Its field loses to random on the competitor-realistic pool. It is not a discovery claim.

## 6 · Verdict

**H90 verdict: negative.** Download yes (research). Submit no. Slots used 0. Promotion: none.

Why it is not promoted, each clause measured:

1. HOLDOUT-DTI 0.003850 [0.003519, 0.004220] is below the best comparable arm on the same instrument, view_B 0.006419 [0.005873, 0.006892].
2. On the visible-catalogue pool the disagreement field (0.031379) is below random (0.041594).
3. The literal dot-lane rule returns DUPLICATE/STOP against the calibration lattice. Under the H60-6 exclusion the rule would pass. This is an owner decision and does not change the verdict, which clause 1 decides.

## 7 · What the owner needs to decide

* **IR-H90-001 (instrument):** should the shared holdout use the visible-catalogue ring (competitor-realistic) rather than the full-catalogue ring? Every H60-family holdout receipt depends on the current rule. My recommendation is to switch and re-score the registered arms before any further comparison; not done here, because the switch changes every receipt.
* **IR-H90-006 (lane gate, conflicting precedents):** H60-6 (knowledge/30) excluded `13gems_…r13-lattice-s5…` from the 3-px dot component, reasoning that budget-sized placements read 70–84% against it by grid geometry. H85 (IR-H85-009) reported the literal rule without waiver, because random dots read 0.999 against it. The two readings of the same raster disagree. Decide which rule governs before the next lane gate. Under H60-6 the H90 dot gate would pass (0.6534 vs H60D); under the literal rule it fails. The H90 verdict is negative either way.
* **IR-H90-007:** do not rank rounds across instruments until both arms are reproduced on one instrument.

## 8 · Hypotheses proposed next (ranked; none validated in this round)

Ranking uses the evidence above. "Expected gain" is an ordinal prior, not a projection. None is validated, so none should be written as a score.

| rank | id | layers | signature | why it could find a catalogue-missing fault | how it differs from what is implemented | cost | status |
|---|---|---|---|---|---|---|---|
| 1 | **H90-P1 re-score on one instrument** | band 2 `rtp`, band 13 `iso_grav_anom`, band 12 `det_elev`, band 15 `depth_to_base_surf` | none new: re-score the registered view_B, union and H82 B_DVA2 OOF fields on the visible-ring pool | tests whether the 0.19 vs 0.006 scale gap is the ring rule (IR-H90-007) before any new hypothesis is spent | not a new field: it is a measurement fix | low (no refit if OOF fields exist; H82 OOF must be regenerated) | proposal |
| 2 | **H90-P2 single-view B with the visible ring as the training negative pool** | View B layers only, no co-training | surface-DEM confidence, emitted at 3 px spacing | View B is the only arm above random on both pools; the question is whether the lift survives a clean sampler | co-training is not used; this is the single-view baseline the brief asks for, under the clean sampler | medium (refit 4 folds) | proposal; the clean sampler (`run_h90_negclear_audit.py`) is ready |
| 3 | **H90-P3 cover-gated buried candidates on the visible ring** | band 15 `depth_to_base_surf` ≥ 200 m; A-only disagreement; band 9 `tmi_vg` edge | buried structure under cover where View B abstains | H62-1 (cover-gated A-only disagreement) was tested and was NEGATIVE on the full-ring pool (corridors 0.0034 vs ungated dis_contrast 0.0041, README H62 block); not yet tested on the visible ring | the visible-ring pool may change that result; re-test it there | medium | proposal; no new data needed |

Named data sources for any idea that would need new data: none are needed for P1–P3. External layers already in the repo: `data/external/gdr_qfaults_traces.csv` (GDR 1391 INGENIOUS Quaternary fault traces, attributes only, per `registry/data_manifest.json`), `data/external/lidar_scarp_features_u8.tif` (derived from USGS 3DEP 1 m DEM tiles, per the manifest), and `data/external/geodawn_rad_u8.tif` (derived from the USGS GeoDAWN release, DOI 10.5066/P93LGLVQ, which `knowledge/04_free_data_and_licenses.md` also cites). Nothing new is required for P1–P3.

## 9 · Limits (stated, not hidden)

* Holdout numbers are HOLDOUT-DTI on the H60D instrument. They are not leaderboard estimates. The repo measured Spearman −0.10 between holdout DTI and board score (`AGENTS.md`, IR-H77-005).
* Fold-bootstrap CIs over 4 folds are coarse and are reported as that, not as significance tests.
* The restored data are integrity-pinned owner mirrors. They are **not** organiser-authenticated (`registry/data_manifest.json` note).
* `work/pinned` is a symlink to `data/` (both gitignored). The H60 scripts expect that path, and no script in the repo creates it. This should be added to the restore script next round (IR-H90-009).
* The canary on the legal set is undefined by construction (IR-H90-004); the canary used is on the fold region.
* No new external data were added. Nothing was submitted to the competition.
