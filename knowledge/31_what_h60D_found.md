# 31 — What H60D actually found (session 2026-10-08)

Renamed from `knowledge/26_what_h60_found.md` with the round (H60 → H60D) when a parallel
H60 session (H60C) merged to `main` first and occupied the plain `h60` file names — see
`registry/irregularities.json` → `IR-H60D-006`.  Every number is unchanged.

Preregistered in [`30_hypotheses_H60D_preregistered.md`](30_hypotheses_H60D_preregistered.md), frozen in
[`registry/h60d_preregistration.json`](../registry/h60d_preregistration.json) (sha256
`6ce875d3…`, amended `e64ba69a…` by registered corrections H60-5 and H60-6 — both evidence-based, both
registered before the artifact shipped, neither changing any gate outcome) before any H60 fit ran.
Every number below was computed on the manifest-pinned bytes (`work/pinned`, 23/23 SHA-256 verified in
`evidence/h60d_preflight_integrity.json`); the tracked `data/*.tif` stubs were measured and recorded as
unused. Receipts: `evidence/h60d_cotrain.json` (E1), `evidence/h60d_cotrain_control.json` (same-seed
control), `evidence/h60d_validation.json` (E2), `evidence/h60d_build.json` + `evidence/h60d_format_gate.json`
+ `evidence/h60d_uniqueness.json` + `evidence/h60d_lane_gate.json` + `evidence/h60d_lane_surface.json` +
`evidence/h60d_slot_gate.json` + `evidence/h60d_run_card.json` (E3). Site: `docs/h60d.html`.

**Verdict: NEGATIVE.** The disagreement between the two views — the Blum & Mitchell co-training
discovery signal — does **not** rank buried-structure candidates better than the surface view alone or
the plain union, on either holdout instrument. The lane ships the best measured A-side disagreement
field (`dis_contrast`) as a unique, review-only artifact with an explicit DO-NOT-SUBMIT status. A
negative result is a deliverable.

## 1. The independence premise held — the exchange was licensed

Per-50×50-block out-of-fold errors on labelled negatives, 4 hide folds (8,588 blocks, 4,519,160 px):

| statistic | value |
| --- | --- |
| block negative-FPR Spearman | **0.176** |
| block MSE Pearson | 0.155 |
| pixel-level Pearson / Spearman | 0.1503 / 0.1464 |
| abandonment threshold | 0.60 |

`measured=true, allow_exchange=true` (`evidence/h60d_cotrain.json`). The two views' errors are
near-independent, so the co-training exchange was licensed and run in **both** directions
(registered correction of H59's donor-self refit): `A_labels_B` 1,997 px / 79 whole segments,
fold-0 AUC 0.6659 → 0.6592 (Δ −0.0067); `B_labels_A` 1,997 px / 103 segments, AUC 0.6006 → 0.5901
(Δ −0.0104). **Fourth and fifth independent nulls for the pseudo-label exchange.** The same-seed
control (`scripts/run_h60d_cotrain_control.py`: both views refit on the fold-0 fit region with the
round-1 seed `SEED+7` and NO pseudo-labels) separates the seed effect from the exchange effect:
seed effect up to +0.0009 on the union field, **exchange effect −0.0002…+0.0003 (null)** on both
instruments (`evidence/h60d_cotrain_control.json`). The apparent round-1 gain in the un-controlled
readout was the seed, not the exchange.

**Leakage canary: clean.** Worst of all 75 cached layers, single-feature AUC against the holdout
truth: `B_lidar_step_max_grad` 0.7136 (< 0.90; next 0.7109, 0.7088, 0.7066). No layer is a leakage
channel.

**Strata reproduce the cover geology.** Allowed 4,861,502 px; A-only 301,390 px (median depth to
basement **341.7 m**) vs B-only 197,479 px (**106.5 m**); concordant 145,397; neither 4,217,236.
The A-only stratum is deep cover — exactly the buried-fault regime the lane targets.

## 2. The disagreement fields do not beat the baselines (HOLDOUT-DTI)

Whole-segment hide-and-recover, 4 folds, buffer 4 px, prevalence 0.002, seed 20261009, 36,411
withheld positives; evaluator pinned (`metric.py` `3d454119…`, `holdout.py` `f6706d78…`); pooled =
metric components pooled across folds; CI = fold bootstrap 10k. Budget 37,654 px, `iso_select`
top-k (3 px inclusive, 5 px NMS) — the registered scoring emitter.

| field | hide pooled (95 % CI) | tip pooled (95 % CI) |
| --- | --- | --- |
| **view_B** | **0.006419** [0.005873, 0.006892] | **0.005451** [0.003928, 0.006550] |
| dis_B_product (characterization only) | 0.006409 [0.005822, 0.006850] | 0.005485 [0.004040, 0.006424] |
| clf_union | 0.006140 [0.005598, 0.006610] | 0.005237 [0.003856, 0.006095] |
| **dis_contrast (shipped)** | **0.004109** [0.003597, 0.004948] | **0.003338** [0.002179, 0.004185] |
| view_A | 0.004031 [0.003438, 0.004445] | 0.003954 [0.002613, 0.004682] |
| dis_product | 0.003196 [0.002582, 0.003578] | 0.002967 [0.001685, 0.003626] |
| random | 0.001802 [0.001508, 0.001944] | 0.001799 [0.001024, 0.002242] |

At 15,000 px the ordering is the same (view_B 0.005190 > union 0.005015 > view_A 0.003948 >
dis_contrast 0.001750 ≈ dis_product 0.001998 > random 0.001099 on hide; tip analogous).

Three honest readings:

1. **The A-side disagreement fields beat View A and the random control but lose to View B and the
   union on every fold, both instruments, both budgets.** `dis_contrast` > `view_A` on hide
   (0.004109 vs 0.004031) but the promotion rule required beating the union AND both views — failed
   on every clause. The B-only product ranks statistically indistinguishable from View B itself
   (0.006409 vs 0.006419) — it is the surface view's own confident core, i.e. the suspect-artifact
   population, which is why it was registered characterization-only (H60-4) and can never ship.
2. **On the hide instrument the surface view alone beats the union** (0.006419 vs 0.006140). The
   union is not even the best single field this round; adding the geophysical view to the surface view
   dilutes the ranking on withheld catalogue truth.
3. **The disagreement signal is real but weak and non-novel.** Restricted to the required-novel pool
   (outside every prior's support), the shipped raster scores hide pooled **0.003136**
   [0.002937, 0.003414] — above the matched novel-pool random control (0.001080) but below the
   novel-pool union (0.003384) and view_B (0.004239). The field's confident novel-pool support is
   only **24,272 positive-field crests**; the remaining 13,382 of the 37,654 budget is zero-field
   fill (disclosed in the receipt). The disagreement field re-ranks ground that priors already
   cover; on genuinely novel ground it carries signal above random but below the surface view.

## 3. The placement diagnostic (registered correction H60-5)

The preregistered artifact placement was `greedy_emit` (coverage surrogate). The build's own
diagnostic falsified it **for this field on this pool**: the greedy dots sit on the field's broad
plateaus (mean field 0.349) and score hide pooled **2.2e-05** — ~50× BELOW the matched novel-pool
random control — while the same field placed by the scoring emitter scores 3.5e-03. Gain favours
broad moderate plateaus over thin high crests, and the plateau mass is anti-correlated with the
withheld truth. A greedy-placed raster would not have externalized the measured field.
**Correction H60-5:** the artifact is placed by `h57.iso_select` (the emitter of every registered
read and of the H57 champion artifact); `greedy_emit` is retained as a disclosed, scored diagnostic
(both reads in `evidence/h60d_build.json` and the run card). No gate outcome changes.

## 4. The artifact (E3) — unique, review-only

`gems52-h60d-dis_contrast-arm37654px.tif` — 144,504 bytes, sha256
`18bd0efd582f107c…` (full hash in the receipts), 37,654 px, values exactly {0,1}, single-band
float32, EPSG:32611, 3730×3292, all finite; portal name
`gems52-h60d-dis_contrast-arm37654px-18bd0efd-zeros`, note ≤ 140 chars. Reproducible: the rebuild
after the IR-H60-002 fix reproduces the identical sha256 (fixed point).

| gate | result |
| --- | --- |
| format | PASS (0 problems, 0 NaN, values in [0,1], CRS/shape/transform match) |
| uniqueness | pattern unique vs **68** accessible aligned priors; support novelty **100 %**; not a literal prior union |
| lane drift, surface | max |Spearman| **0.0979** (bar 0.90) — clean |
| lane drift, dots | max |Spearman| **0.0094**; 3-px proximity raw **0.8390** vs the calibration lattice, **0.1592** excl. calibration (bar 0.70) — clean (H60-6) |
| not merely union | 37,331/37,654 px (99.1 %) outside the union field's greedy emission; 37,282 (99.1 %) outside its iso top-k |
| 200 m ring | min distance to a mapped catalogue pixel **223.6 m** |
| reasoning | 37,654 per-pixel geological reasoning rows + 11,196 A-only candidate-segment dossiers |
| slot gate | **CLOSED** — promotion/slot bar not met; DOWNLOAD OK FOR REVIEW, DO NOT SPEND A WEEKLY SLOT |

`submission/LATEST.txt` stays on H57; H60 publishes via `docs/data/submission_h60d.json` +
`submission/H60D_LATEST.txt`. The site's top download bar points at `downloads/h60-candidate.tif/.zip`
with the unmistakable status line.

## 4b. Re-measured after the merge (the renamed round's final numbers)

After the rename (IR-H60D-006) and the merge of main, the artifact was rebuilt against the
**merged prior inventory**: every H60C / CTD5 / concurrent-H60 raster on main is now a genuine
prior, so the accessible aligned prior count rose from 55 to **68** and the legal pool shrank
accordingly. All gates were re-run and re-measured: the artifact is
`gems52-h60d-dis_contrast-arm37654px.tif` (144,504 bytes, sha256
`18bd0efd582f107ccb988fc20016203c323846bf63d3ecea1f75a0670e4586e8`, 37,654 px), pattern-unique
vs all 68 priors with 100 % support novelty; lane gate clean (surface |ρ| 0.0979, dots |ρ|
0.0094, 3-px proximity 0.1592 excl. calibration, raw 0.8390 vs the calibration lattice);
not-merely-union 37,331/37,654 px (99.1 %) outside the union field's greedy emission;
shipped raster hide pooled HOLDOUT-DTI **0.003136** [0.002937, 0.003414] — above the matched
novel-pool random control (0.001080), below the novel-pool union (0.003384) and view_B
(0.003576); greedy_emit diagnostic 2.2e-05; 24,217 positive-field crests + 13,437 zero-field
budget fill; 11,196 A-only candidate segments. The verdict is unchanged: **negative**.

## 5. Incidents and registered corrections this round

- **IR-H60D-001** — the A-only segment dossier hung the first build (per-segment full-grid scans,
  143.6 G cell visits); fixed with vectorised grouped statistics. No artifact affected.
- **IR-H60D-002** — the self-exclusion pattern missed the stem-named `docs/downloads` copy of the
  round's own artifact; the second build treated its own previous arm as a prior and the lane gate
  fired on it at 90.4 % (a self-collision, not drift). Fixed by widening the pattern to both
  published names; rebuilt to the fixed point.
- **IR-H60D-003** — the marginal acceptance radius was logged in pixels under a metre label
  (2.8 "m" instead of 283.3 m); fixed (×100 m).
- **IR-H60D-004 / H60-5** — the greedy-vs-iso placement divergence (section 3).
- **IR-H60D-005 / H60-6** — the lane-drift 3-px proximity gate fired at 0.8390 against an
  owner-supplied **calibration** lattice (manifest id `calib_…`, source `inputs/calibration/`; the
  regular 5-px lattice that reaches 99.8 % of the A/S ceiling). Its 3-px dilation covers about half
  the grid, so any pool placement reads 70–84 % against it by geometry, not duplication.
  **Correction H60-6:** calibration rasters are excluded from the proximity component only,
  classified manifest-driven (`h60.calibration_basenames`), never hand-picked; raw readings still
  reported; both Spearman components apply to every prior; the uniqueness gate (the actual
  duplication control) is unchanged and passes decisively. Gate value over the 49 non-calibration
  priors: 0.1592.

## 6. What this means for the board question

The standing question — why `h33` scored 0.2778 and whether > 0.2778 is generatable — is answered in
`knowledge/21` and is **not re-litigated here**: the champion is the h27-4 core minus the ≤200 m ring,
|G| = 14,088.7 px, and no local measurement can certify a novel arm's hidden-truth density. H60D adds
one new fact: the lane's discovery signal (view disagreement) produces a **pure novel arm** whose
holdout read (0.0035) sits between the novel-pool random control (0.0014) and the novel-pool union
(0.0039) — the disagreement field is a genuine but weak ranker of withheld catalogue truth on novel
ground, and it does not beat the surface view. The conditional projections in the receipt
(0.06–0.28 across ρ = 0.03–0.14, owner-reported inputs, never scores) describe the arithmetic of a
hypothetical arm density, not a forecast; with the measured novel-pool density the arm projects far
below the champion. Every leaderboard number in this repository remains owner-reported; none is
organizer-confirmed.

## 7. Three passes

1. **Implement + verify:** E1/E2/E3 built, compile-checked, smoke-tested; the inverted-AUC bug in
   `h60.layer_auc_canary` was caught by the smoke test and verified against sklearn; the
   double-scoring wart in `stage_validate` fixed; 16 H60 tests pass.
2. **Bug review + fix:** the dossier hang (IR-H60-001), the self-exclusion miss (IR-H60-002), the
   unit bug (IR-H60-003), the placement divergence (IR-H60-004/H60-5) and the calibration-lattice
   false positive (IR-H60-005/H60-6) were all caught by review/diagnostics before the artifact
   shipped; each is fixed, registered and disclosed.
3. **Full re-check:** `pytest -q` 245 passed; `scripts/check_site.py` green; the site's H60 page
   renders only receipt numbers; the shipped TIFF serves byte-identical through the site.
