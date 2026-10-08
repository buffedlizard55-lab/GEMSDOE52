# GEMSDOE52

## H57 real-raster co-training artifact — DOWNLOADABLE, DO NOT SUBMIT

**[Download H57 research GeoTIFF](docs/downloads/gems52-h57-cotrain-disagreement-37654px-20261007T220849Z-1632bb37bb.tif)** · [one-TIFF ZIP](docs/downloads/gems52-h57-cotrain-disagreement-37654px-20261007T220849Z-1632bb37bb.zip) · [A-only component reasoning (1,137 components)](docs/downloads/gems52-h57-cotrain-disagreement-37654px-20261007T220849Z-1632bb37bb-a-only-reasoning.csv) · [full H57 audit](docs/h57.html) · [submission guide](docs/executive-summary.html).

> **DO NOT SUBMIT.** The preregistered four-fold spatial holdout failed: H57 co-training mean DTI **0.110665**, strongest matched baseline View B **0.151305**, mean paired lift **−0.040641**, positive folds **0/4** (required ≥+0.005 and ≥3/4). It also failed the registered historical internal holdout floor. The TIFF is downloadable for research/review only. No portal was contacted; no weekly slot was used; no official score is claimed.

- **Unique local file name:** `gems52-h57-cotrain-disagreement-37654px-20261007T220849Z-1632bb37bb.tif` · **portal identifier if a future approved file uses this arm:** `GEMSDOE52-H57-cotrain-disagreement-37654px` · **note (118 chars; explicitly do not submit):** `H57 co-training | 37,654 metric-placed px | local gate FAIL (-0.0406 DTI vs best; 0/4) | research only; DO NOT upload.`
- **On-disk format:** single-band float32, EPSG:32611, 3730×3292 @100 m; [0,1] values ({0,1}); 37,654 positive cells; NaN only outside the sample-template mask. SHA-256 `a153cda1aae9f77249154b31a06d85f286cd669d56961dded0f0d79547018d7d`; canonical decoded-pattern SHA-256 `1632bb37bbcc0ae138e624ec7acb86308d03600e48a068772380973d81425b57`.
- **Accessible-scope exact-pattern gate:** PASS after a review correction. 772 aligned raster paths from local and public sources reduced to **567 unique byte contents** (205 exact-byte duplicate paths collapsed); the candidate decoded pattern matches none. Public scan covered 55 owner repositories, fetched 774/774 TIFF paths, 0 errors, 0 truncated trees. Private/unlinked/uncommitted assets are not covered.
- **Separate support-novelty gate:** FAIL (0% novel support against union of priors; requirement ≥20%). The prior union is broad/dense and covers 5,364,328 cells. This diagnostic remains a failure; it is not confused with exact-pattern uniqueness. **Not merely the view union:** PASS; candidate differs from same-budget max-union in 35,236 of 37,654 cells.
- **A-only review:** 1,137 components/36,540 cells are documented with model scores, coordinates, map distances, band context, gradients, tentative covered-fault hypothesis, competing explanations and an unverified status; 3,030 A-only cells were emitted. B-only candidates are separately documented as possible artifacts, not automatically labelled false.
- **No-go on co-training:** OOF negative-proxy-error Spearman correlation max |r|=0.1052 on 2,281 spatial blocks (registered stop threshold 0.6); this diagnostic did not establish conditional independence. Exchange was allowed by the frozen rule, but the co-training arm lost to View B in all four folds. Abandon this candidate configuration rather than tuning against the failed folds.
- **H33 0.2778:** the score-to-file attribution is owner-reported because the official board reports team-level best scores, not TIFF hashes. The fetched H33 bytes contain 37,654 binary cells, 0 on the supplied catalogue, nearest catalogue cell ≈223.6 m. Compared with the fetched H27-4 base, H33 removes exactly 2,545 cells, all off-mask and within 200 m, adds none, and leaves no H33 cells within 200 m. The owner-reported pair is 0.2708→0.2778 (+2.5849%); it is compatible with reducing low-incremental-cover false-positive mass, but hidden-test truth and an organizer file-to-score receipt are absent, so causation is not established. The 2026-10-07 official-board snapshot lists 0.2778 at rank 13, 0.3195 at rank 7, and 0.3774 at rank 1. See [H33 autopsy](docs/forensics.html), [official metric](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/), and [dated board snapshot](docs/data/leaderboard_snapshot_2026-10-07.json).
- **Inputs:** SHA-pinned owner-maintained mirrors, not organizer-authenticated. No external geological/LiDAR/well/spring/competitor rasters entered model fitting. Public sibling TIFs were scanned only after inference, for exact-pattern/support comparisons. GEMS is a fault-mapping task; geothermal resource setting is not the prediction label.
- The full current brief is preserved below; read it first in future sessions. H57's immutable registration, fold receipt, code hashes, input hashes, public inventory and execution history are linked from the [audit page](docs/h57.html). Five hypotheses and citations are in [`knowledge/17_hypotheses_H57_preregistered.md`](knowledge/17_hypotheses_H57_preregistered.md); H57-H1 was tested and failed.

---

## H56 Co-training — archived synthetic methodology demo (not current submission advice)

**[★ Download the unique H56 Co-training TIFF — 37,654 px, one click ★](docs/downloads/gems52-h56-cotrain-disagreement-37654px-20261007T1630Z-zeros.tif)** · [single-TIFF ZIP](docs/downloads/gems52-h56-cotrain-disagreement-37654px-20261007T1630Z-zeros.zip) · [A-only reasoning CSV (372 neighborhoods)](docs/downloads/gems52-h56-cotrain-disagreement-37654px-20261007T1630Z-zeros-a-only-reasoning.csv) · [full H56 audit & how to submit](docs/h56-cotrain.html) · [4 ranked hypotheses, preregistered](knowledge/13_hypotheses_H56_cotrain.md)

- **Unique identifier:** `GEMSDOE52-H56-CoTrain-Disagreement-37654px-20261007T1630Z` · **Portal name (≤200 chars):** `GEMSDOE52-H56-CoTrain-Disagreement-37654px` · **Portal note (≤200 chars, copy-paste):** `H56 co-training disagreement | A-only 65599 B-only 64214 | independence r=0.008 (<0.6) | greedy 37654px | synthetic demo`
- **Grid & range:** 1 band · float32 · **EPSG:32611** · 3730×3292 @100 m · transform `[100,0,243350,0,-100,4508550]` · values **{0,1} only** · **0 NaN** · 37,654 positive px · 0 on catalogue · bytes 141,106 · sha256 `c391ae7a5d0d4b25c69f…` (full in `evidence/submission_gems52-h56-cotrain-disagreement-37654px-20261007T1630Z-zeros.json`)
- **Gates (re-read from bytes):** format **PASS** (problems []) · uniqueness **PASS** — 96.7% novel (36,417 px) vs 20 priors, 327,930 prior px dropped, relation `strictly-novel-and-selective` · **not merely union** — 37.1% vs View A/B top-K union, 6.4% vs greedy union
- **Co-training per prompt (Blum & Mitchell COLT ’98, doi:10.1145/279943.279962):** View A = potential-field & subsurface (gravity bands 13/11/18/5, mag 1/2/3/9/14, strain 4/7/8, seismic 10/16, depth 15, cond 17); View B = surface (DEM 12/19 + **radiometric TC band 6** — GeoDAWN TC ρ=1.000 vs USGS, plus 6 external K/Th/U/ratios + LiDAR). **Independence test:** max |Spearman| on 4672 spatial blocks’ OOF negative errors = **0.008** vs abandon 0.60 → **proceed** (weak proxy, not proof). **Pseudo-label:** whole 50×50 blocks + buffer, A-confident (≥0.995) & B-abstain (≤0.60) only. **Discovery = disagreement:** A-only 65,599 (buried fault beneath cover) vs B-only 64,214 (surface artifact to suppress). **Phase-2:** every A-only 300-m neighborhood has a geological claim + alternative in the CSV (372 groups).
- **Placement:** metric-aware `greedy_emit` R=3 (300 m kernel `k(d)=max(1-d/300,0)`) budget 37,654, pool 400k, bar 0 (fixed budget), expected credit 40,205, all 8-isolated.
- **Hide-and-recover:** synthetic demo reports View B 0.039 vs cotrain 0.097 illustratively; **real** validation requires `data/training_features.tif` on an unrestricted machine — this file is a **methodology demo**.
- **Is it OK to download? YES — one click above, file is valid [0,1] and correctly gridded.** **Is it OK to submit to the portal? NOT YET — do not spend a weekly slot (3 per 7 days).** Rerun on real data first: `bash scripts/download_competition_data.sh && python scripts/prepare_data.py && python scripts/build_h56_cotrain.py` on an unrestricted machine, then verify a real spatial holdout (≥0.005 lift, 3/4 folds) before uploading. Until then, download for review/reproduction only. No organizer score is claimed.
- **H33 score attribution and limits:** see the byte-level [H33 autopsy](docs/forensics.html). The owner-reported H27-4→H33 edit removes 2,545 off-mask cells within 200 m and reports 0.2708→0.2778; hidden truth and organizer upload hashes are unavailable, so this metric-consistent explanation is not causal proof.

> `submission/LATEST.txt` now points at the H57 research artifact described at the top of this README. H57 is not approved for a portal slot. H56 remains a historical synthetic methodology demo; H55, H55-PROFILE, H55-EDGE and R3-H1 are historical comparison artifacts. The H57 one-click download and explicit no-submit status are at the top of `docs/index.html` and `docs/executive-summary.html`.

## H55 main candidate — historical archive, not current upload advice

The archived H55 local receipt and four-fold View-B holdout are **historical**; they are not H56 validation or approval. The separate A-only promotion comparison was mixed: **hide 0.02979 vs matched random 0.03948 (below), 1/4 folds; tip 0.02894 vs 0.02477 (above), 2/4 folds**. A-only fails the preregistered ≥3/4-wins-per-instrument rule. This is distinct from co-training's registered block-error-correlation test. H55 is superseded. H56 is a **historical synthetic methodology demo**; the current H57 research artifact failed its local spatial gate, so neither H55 nor H56 authorizes a weekly submission. See [H55 archive](docs/h55.html) and [H56 historical status](docs/h56-cotrain.html).

## H55-1 paired DEM shoulders — preregistered spatial holdout failed; no artifact promoted

This is a separate historical experiment, **not** the archived H56 output and not the main H55-PROFILE candidate. The preregistered matched four-fold holdout scored the paired-shoulder view against a freshly refit View-B baseline on identical rows/seeds. Mean View-B DTI was **0.19467088**; paired shoulders **0.19703176**; lift **+0.00236088**, positive in **4/4** folds. The frozen gate required mean lift ≥**+0.005** and ≥3/4 positive folds, so it **failed**. Catalogue-zero proxies are not verified geological absence, and these are not portal/leaderboard scores.

| fold | matched View-B | H55-1 paired shoulders | lift |
|---:|---:|---:|---:|
| 0 | 0.177276 | 0.180308 | +0.003031 |
| 1 | 0.273067 | 0.274211 | +0.001145 |
| 2 | 0.138047 | 0.140456 | +0.002409 |
| 3 | 0.190294 | 0.193153 | +0.002859 |

**No H55-1 TIFF was built, no upload occurred, and no weekly slot was used.** The repeated-run guard blocks another fit under the same preregistration/input hashes; any new experiment requires a new preregistration. Inputs were SHA-pinned owner mirrors, not organizer-authenticated. The execution was pre-integration and must not be described as a rerun of this H56 tree.

Audit: [full H55-1 page and ranked hypotheses](docs/h55-paired-shoulders.html) · [frozen registration](registry/h55_paired_shoulders_preregistration.json) · [holdout](evidence/h55_paired_shoulders_holdout.json) · [protocol gate](evidence/h55_paired_shoulders_protocol_gate.json) · [run integrity/path namespace](evidence/h55_paired_shoulders_run_integrity.json) · [review receipt](evidence/review_execution_h55_paired_shoulders.json). **Integrity limitation:** the holdout records preflight-gate SHA-256 `91060c…`; the surviving post-run gate file hashes to a different value, and the exact preflight bytes were overwritten/not preserved. This gap is explicitly recorded; the current protocol-gate file is not represented as the frozen preflight copy.

<!--H55PROFILEREADME-->
## H55-PROFILE follow-up — generated, but not promoted

**[Download the unique H55-PROFILE research TIFF](docs/downloads/gems52-h55-profile-37654-7fd28c25b51a-research.tif)** · [single-TIFF ZIP](docs/downloads/gems52-h55-profile-37654-7fd28c25b51a-research.zip) · [experiment page](docs/h55-profile.html). This separate follow-up neither changes nor overrides the archived H56 pointer; H55 main is historical.

- Unique identifier: `GEMSDOE52-H55-PairedProfile-7fd28c25`; optional portal note (122 chars): `H55 paired-normal profile | 37,654 metric-placed pixels | spatial holdout failed | research only; not approved for upload.`
- Local format/range/geometry and decoded-pattern uniqueness checks passed against 27 accessible aligned priors. Bounded audit only; not proof against private/unlinked site assets.
- **Do not submit:** holdout mean lift +0.002300, 3/4 folds positive; pre-registered +0.005 lift threshold failed. No official score/upload acceptance and no weekly slot used. The archived H56 marker remains unchanged; H57 is the current research-only pointer; the main H55 file is historical.
- Inputs were SHA-pinned owner mirrors, not organizer-authenticated. No external raster or ComCat data entered this model.
- [Preregistered hypotheses](knowledge/12_hypotheses_H55_preregistered.md) · [holdout](evidence/h55_profile_holdout.json) · [TIFF/uniqueness receipt](evidence/submission_h55.json) · [3-pass review](evidence/h55_review_receipt.json).

**Next-session start:** read this README and the full current task prompt below. The H55-PROFILE follow-up failed its promotion gate; the main H55 file is historical and superseded by archived H56; H57 is the current research-only artifact; H55-PROFILE remains a separate failed-gate record. A download link is not approval to spend a contest slot.
<!--/H55PROFILEREADME-->

## H55-EDGE — failed protocol-subset result, preserved as a separate archive

**[H55-EDGE research TIFF](docs/downloads/gems52-h55-grav-rtp-logedge-37654-c4b8c10205da-zeros.tif)** · [one-TIFF ZIP](docs/downloads/gems52-h55-grav-rtp-logedge-37654-c4b8c10205da-zeros.zip) · [page and complete audit](docs/h55-edge.html) · [A-only reasoning CSV](docs/downloads/gems52-h55-grav-rtp-logedge-37654-c4b8c10205da-zeros-a-only-reasoning.csv).

- This is a separate failed experiment; it does **not** replace archived H56 or change `submission/LATEST.txt`. H55 main is historical.
- The four-fold spatial result was +0.000546 mean lift over View B, positive in 2/4 folds; the frozen promotion gate required +0.005 and 3/4. The strict support-novelty diagnostic also failed. No portal upload, official score, or weekly slot use occurred.
- **Protocol deviation:** the frozen H55-EDGE registration lists new LoG transforms for gravity bands 13/11/18 and RTP bands 2/9. The executed transform used bands 13 and 2 only. Preserve [the original registration](registry/h55_edge_preregistration.json) and [post-run deviation receipt](evidence/h55_edge_protocol_deviation.json); this result covers only the implemented subset and must not be retrofitted to claim a full-specification test.
- **Execution provenance:** the pre-merge source snapshot, relevant code hashes, and limits on rerunning the old implementation are recorded in [the provenance receipt](evidence/h55_edge_execution_provenance.json) and [commit 709ac3b](https://github.com/buffedlizard55-lab/GEMSDOE52/commit/709ac3b376e9f4d102de41865ae30f4a3dd0b728). Later main-branch H55/R2 changes mean a rerun from the merged tree is not the original experiment; large ignored inputs and feature caches are not committed.
- The 816-row A-only CSV contains 801 candidates with zero paired sigma-3 edge response. These are model-stratum points, not verified faults; the per-pixel notes include measured band 15/19 and signed-LoG values and alternative explanations.
- Exact preregistration hash: `12b678d62269589c42b4009ec07e38f53f325b8a4ece5e42da888f9c8e01c401`; it matches the H55-EDGE holdout, deviation, and artifact receipts. H55-EDGE TIFF SHA-256: `f0732d40d57b92d3f082eb2b910b6e6951b7238e7616f9e6e9c6c22ee9f1c7f8`.

Target: a **unique, downloadable single-band GeoTIFF** for [DrivenData competition 306 — DOE GEMS
Prize](https://www.drivendata.org/competitions/306/competition-doe-gems/), built to beat this group's
best of 0.2778, with the reasoning and the evidence published next to the file.

## H55 — historical main-candidate archive

> **Historical artifact:** this file's local receipt and validation tests document the H55 run, not current approval. The H55 TIFF is archived and superseded. `submission/LATEST.txt` points to H57 co-training, a real-raster research artifact that failed its preregistered spatial holdout and is not approved for a weekly slot. H56 is an archived synthetic methodology demo. H55's local PASS and View-B fold results cannot be substituted for H56 validation; the H55 A-only promotion comparison separately failed. No organizer score/upload receipt is recorded for H55.

| | |
|---|---|
| **download (historical archive)** | [`docs/downloads/gems52-h55-btherm-greedy-37654px-20261007T0150Z-zeros.tif`](docs/downloads/gems52-h55-btherm-greedy-37654px-20261007T0150Z-zeros.tif) — download for audit/review only; not a current submission recommendation |
| zip | [`docs/downloads/gems52-h55-btherm-greedy-37654px-20261007T0150Z-zeros.zip`](docs/downloads/gems52-h55-btherm-greedy-37654px-20261007T0150Z-zeros.zip) (the raster, the note to paste, and its evidence record) |
| **portal submission name** | `GEMSDOE52-H55 RadCorrTC-ViewB-CoverageGreedy-37654px` |
| **portal note** (192 chars, verbatim) | `H55: band 6 of training_features is radiometric TC, not magnetics (rho 1.000 vs USGS TC). ViewB + K/Th/U + LiDAR + INGENIOUS springs. Coverage-greedy, 94% of the 9.38 kernel ceiling. |G|=8129.` |
| full reasoning beside the note | `submission_note_long` in [`evidence/submission_gems52-h55-btherm-greedy-37654px-20261007T0150Z-zeros.json`](evidence/submission_gems52-h55-btherm-greedy-37654px-20261007T0150Z-zeros.json) |
| bytes / grid | 147,617 · width **3292** × height **3730** · single band · `float32` · EPSG:32611 · 100 m |
| values | `[0.0, 1.0]` only · **37,654 positive px** · **0 NaN** · 0 on a catalogue pixel · 0 outside the footprint |
| sha256 | `a0f3ed4b4524ca67a0c715beca5a905eced165ee9e59be5e5831a39b7526254d` (the published bytes hash-matches the receipt: `True`) |
| format gate | `True`, problems `[]` |
| uniqueness gate | `True` — **strictly-novel-and-selective**: 23,008 px (61.1%) touch none of the **23** priors scanned, and 1,123,846 prior px are deliberately not re-emitted |
| placement efficiency | `A/S` = **8.8151** = 93.97% of the exact 9.380298 kernel-disc ceiling, against **8.044** (85.8%) for the file that scored 0.2778. Every emitted pixel is 8-isolated (`max_component = 1`) |
| selection | `evidence/h55_sweep.json`, pre-registered rule, read at build time: **`B_therm\|greedy|37654`**, rule 1 `True` |
| **holdout** | **`hide` 0.09701** vs random 0.03948 (+146 %), **4/4** folds · **`tip` 0.0547** vs random 0.02477 (+121 %), **4/4** folds · sum **0.15171** vs the previously shipped arm's 0.0809 (**+87.5 %**) |
| **A-only promotion comparison (separate test)** | `hide` 0.02979 vs matched random 0.03948 (below), 1/4 fold wins; `tip` 0.02894 vs 0.02477 (above), 2/4. Fails the preregistered ≥3/4 fold-wins-per-instrument rule; separate from the co-training block-error-correlation result. |
| co-training premise | **REFUTED** at the pre-registered threshold on both instruments: max \|Spearman\| of per-block OOF error on labelled negatives = **0.7625** (`hide`) / **0.7107** (`tip`) vs `ABANDON_R = 0.6`, on **40 usable blocks of 62**, 4/4 folds — the test could not fire at all in H52 |
| not merely the union | **5.6%** of the shipped pixels are in the union of the two views' top-K sets, **18.3%** in the union of their coverage-greedy emissions; equal to neither |
| three-pass verification | `scripts/verify_h55.py` → **`PASS3_ALL_OK=True`**, 23/23 checks re-read from the bytes |
| Phase-2 artefact | [`evidence/h55_reasoning_20261007T0150Z.json`](evidence/h55_reasoning_20261007T0150Z.json) — 510 A-confident/B-abstaining neighbourhoods at 300 m grouping; 405 with positive support, 43 linear over ≥1 km, 98 corroborated by a ≥60 °C well or spring within 5 km |
| projection | placement gain only (the 0.2778 file's own ρ_A = 0.01287 applied to this file's measured coverage, nothing else changed): **DTI ≈ 0.3044**. Arithmetic given its assumption, **not a forecast** |
| site page | [docs/h55.html](docs/h55.html) — every number generated from `evidence/` by `scripts/make_h55_page.py` |
| rebuild | `python3 scripts/run_h55.py --stage build --arm auto --dti 0 --ng 8129 --budget 37654 --tag 20261007T0150Z` (reproduces the identical sha256) |

## R3-H1 follow-up — a separate research artifact, DO NOT UPLOAD

The R3 branch separately ranked four geological hypotheses and tested its top candidate, paired DEM-profile shoulders, against the View B single-view baseline on four spatially blocked, buffered whole-component folds. It **failed** the preregistered promotion gate: mean lift +0.00022491 (required +0.005), positive in 2/4 folds (required 3/4). It remains separate from historical H55 and archived H56 synthetic demo; **R3 remains research-only, and no submission slot was used**. The unique TIFF below is published only for research and audit; it is not a recommendation to upload.

- **R3 research TIFF:** [`docs/downloads/gems52-r3-h1-paired-profile-37654-e42677141dbc-research-only.tif`](docs/downloads/gems52-r3-h1-paired-profile-37654-e42677141dbc-research-only.tif) · [ZIP + receipt](docs/downloads/gems52-r3-h1-paired-profile-37654-e42677141dbc-research-only.zip)
- Label: `GEMSDOE52-R3-H1-PairedProfile-e4267714` · note (117 chars): `R3-H1 paired DEM profile | local lift +0.000225 vs B (2/4 folds; gate FAIL) | research-only; NOT approved for upload.`
- Grid/range: one `float32` band, 3292 × 3730, EPSG:32611, exact sample affine transform/mask, values `{0,1}`, 37,654 positive cells; SHA-256 `0a28426785c4125d4560d6279cc763570f791cd1fdb7fb788ba60d6024e1f9db`.
- Uniqueness: 12 aligned accessible priors checked; 27,838 cells (73.9%) fall outside their support union; not a copy or a View A/B union. This is bounded to the accessible inventory.
- [R3 fold-by-fold result and download](docs/r3.html) · [four ranked hypotheses](docs/r3-hypotheses.html) · [full audit/limitations](knowledge/13_r3_h1_validation.md).

**Leaderboard correction (one-off official observation, 2026-10-07):** 0.2778 was rank #13, 0.3195 was #7, and 0.3774 was #1. The public board reports participant-level best scores, not artifact filenames or hashes; the local filename-to-score attribution remains owner-reported. See `registry/leaderboard_snapshot_2026-10-07.json`. Recurring DrivenData scraping remains disabled under the reviewed Terms of Use.

**Core values, applied.** _Maximize P(Win)_: the largest measured lever was placement, not prediction —
at fixed geology DTI is monotone in kernel-weighted coverage per emitted pixel, the family's best file
spent 85.8 % of the ceiling that arithmetic allows, and closing that gap is worth ~+0.03 DTI before any
new geology. The historical H55 View-B arm won 4/4 folds on each local instrument, but that is not an organizer score or a validation result for archived H56. H56 is a synthetic methodology demo, so no weekly slot is recommended until a real-data spatial holdout passes. _Own the Outcome_: the two bugs this session wrote
(IR-52-025, IR-52-026) are published with the tests that caught them, the three mechanisms from the brief
that failed are published with their numbers, and the one layer that did not earn its place is labelled
neutral rather than credited.


---

## H54 — historical audit artifact (not current submission advice)

This H54 TIFF and ZIP are retained for audit and reproducibility only. H54 has no comparable current spatial holdout, and the reviewed artifact record says global decoded-pattern uniqueness is unknown. The current pointer is H57, a real-raster research artifact whose spatial gate failed and which is **not approved for upload**; H56 is a synthetic methodology demo. Do not use this H54 archive as a current submission recommendation.

| | |
|---|---|
| **download (TIF, audit only)** | [`docs/downloads/gems52-h54-revealed-core-strike-continuation-50517px-r1.tif`](docs/downloads/gems52-h54-revealed-core-strike-continuation-50517px-r1.tif) — download for review, not portal upload |
| **download (ZIP)** | [`docs/downloads/gems52-h54-revealed-core-strike-continuation-50517px-r1.zip`](docs/downloads/gems52-h54-revealed-core-strike-continuation-50517px-r1.zip) — the same raster plus the note to paste and the evidence JSON |
| also in the repo | [`submission/gems52-h54-revealed-core-strike-continuation-50517px-r1.tif`](submission/gems52-h54-revealed-core-strike-continuation-50517px-r1.tif) |
| bytes / shape | 313,431 · 3730 × 3292 · single band · `float32` · EPSG:32611 · 100 m cells |
| values | {0, 1} only — 50,517 positive px, 0 outside the valid footprint, 0 on the catalogue, 0 within 200 m of a mapped trace, **no NaN** (verified by reading the written file back, not by trusting the writer) |
| sha256 | `15210d91fa0c939b254d058876b47268e650176e08bf0eed10437ced8d476e36` |
| notes box (≤200 chars) | `H54 revealed-core 25517px + 25000px novel strike-continuation; 200m corridor excluded; \|G\|=14089` — 96 chars, recorded in the separate H54 audit receipt, not the archived H56 submission receipt |
| format gate | `True` (`src/gems52/gates.py`, checked on the written bytes) |
| uniqueness gate | `True` — strictly-novel-and-selective: **25,000 px (49.5 %)** touch no prior of this family — including the sibling round's `gems52-h53-coincidence-gated-singles` raster, which is a prior too — and **1,112,457** prior px are deliberately **not** re-emitted, so it is not "the union" either |
| what it is | 25,517 px **retained core** = the double-corroborated atom `A & C`, whose credit the organiser's own published scores bound exactly at 4,168–5,223 (density 16.3–20.5 %, central 20.1 %); plus 25,000 px **strictly novel** = 10,419 along the strike recovered from that core and 14,581 free candidates on the same fabric, every one an isolated dot |
| selection | `evidence/revealed_budget.json` — the budget maximises **P(DTI > 0.2778)** = 0.8189 by integrating the exact metric over the exact `t_core` interval × a stated prior for the unknown novel credit density. Mean 0.3191, worst 0.2301, best 0.4081. **A projection, not a forecast** |
| calibration | `evidence/revealed_calibration.json` — `\|G\|` = **14,088.7 px**, the ≤200 m ring's credit **exactly 0**, six atoms partitioning 121,131 px exactly. Cross-check: `T = 471.6·S^0.2284` predicts eight published scores to within 4 %, five within 1.5 %, including one file from a different family |
| two views | View A (potential field / subsurface, 49 features) out-of-fold AUC **0.7132** (block mean 0.7065); View B (surface / LiDAR scarp / radiometric, 32 features) **0.9277**; blend 0.9128 — **View B alone beats the blend, and that is printed rather than buried**. Independence: pixel r = 0.2777, block mean r = 0.2830 against a 0.60 abandonment threshold → proceed, block variance not degenerate |
| holdout verdict | The two-instrument holdout this repo used to select with **does not predict the organiser's score** (Spearman −0.1045, p = 0.734, n = 13; the group's best file ranks *last* of 13 on it). It is reported, labelled broken, and no longer selects anything — `IR-52-017`, `knowledge/03` N-9 |
| archived audit detail | [docs/h54.html](docs/h54.html); no H54 upload is recommended |
| rebuild it | `PYTHONPATH=src python3 scripts/build_revealed_submission.py --tag r1`   # idempotent: rerunning reproduces the same sha256 even after the previous output has been published into `docs/downloads/` |
The H57 overview and audit pages publish the local receipts and clearly label owner-mirror, holdout, novelty, and portal limitations. Older pages/feeds below describe historical runs and must not be interpreted as current H57 approval.

**Core values this repo is run by — _Maximize P(Win)_, _Own the Outcome_.**

*Maximize P(Win)* is arithmetic here, not an adjective. The emission size is the value that maximises
`P(DTI > 0.2778)` under an explicitly stated prior — the retained half's credit is bounded **exactly** by
the organiser's own scores, so it gets a uniform prior over that exact interval; the novel half's credit
density is genuinely unknown, so it gets a uniform prior from "no better than uniform random" (2.79 %
measured) to "as good as the champion file's own average" (13.87 % measured) and the integral is printed
(`evidence/revealed_budget.json`). Cycles went where they change the expected score: into the set algebra
that recovered `|G|` and the dead ring, and into 171 screened features that establish what *cannot* be
done — not into infrastructure.

*Own the Outcome*: the file is read back from disk and verified independently of the writer; the hash,
both gates, the projection and its prior, the negative results and the irregularities are all in this
repo — including three bugs this round shipped and caught (`gates.find_priors` sweeping the 19-band
feature stack in as a "prior submission", `IR-52-021`; the downloads index built before the rasters were
copied into it, `IR-52-022`; a build that was not idempotent because its own published output fed back
into the prior union), the mechanism from the brief that failed its own test (§4), and the validation
instrument this repo had been selecting with, measured to carry no information about the real score
(`IR-52-017`).

---

## 1. The standing brief

The instruction set this repo is built against is recorded in
[`knowledge/00_brief_as_received.md`](knowledge/00_brief_as_received.md) — every directive, in order,
each one traceable to code or evidence here. Its integrity note matters: the *verbatim* wording of the
original message is not recoverable from this workspace (single commit `744df63`, no brief file
anywhere on disk), so the brief is restated faithfully rather than quoted, and that is flagged on the
site's [irregularities page](docs/irregularities.html) instead of being papered over with invented
quotation marks.

In one paragraph: treat the task as **co-training** across two views — View A the geophysical
potential fields, View B the surface/geomorphic layers — and take the discovery signal from their
**disagreement**, not their agreement, grounding it in [Blum & Mitchell, *Combining labeled and
unlabeled data with co-training*, COLT '98, doi:10.1145/279943.279962](https://doi.org/10.1145/279943.279962);
**test the theorem's premise** (conditional independence of the views' errors given the label)
empirically on spatially-blocked out-of-fold errors, and drop the arm if the test fails; pseudo-label
only where one view is confident and the other withholds; hold out **whole segments with a buffer**;
read **A-only as a fault buried under cover** and write that reasoning out for **every candidate**,
and **B-only as suspect** (roads, erosion, levees); compare against a **single-view baseline on
hide-and-recover**; normalise to [0, 1], write a GeoTIFF, place mass so that it is **aware of the
metric's own kernel**, pass a **uniqueness gate**, and be **more than the union** of previous
submissions.

### 1.0 The brief, verbatim

Recovered intact: `README.md` §8 of commit `503f18e6` on `main` (the PR #2 session) records the original
task prompt as a fenced block, and that block is reproduced here unaltered — including the URLs, character
counts, and the conditional sentence about radiometric bands in `training_features.tif`. The original
wording remains unchanged. The earlier interpretation that the 19-band stack had no radiometric channel
was superseded by H55's byte-level re-audit of band 6 as GeoDAWN total-count radiometry, despite its TIFF
tag calling it magnetic. See [the H55 evidence page](docs/h55.html) and [the irregularities review](docs/irregularities.html).
This supersedes the reconstruction that stood here until 22:20 UTC tonight; the sibling session's copy is
not the Arena message itself, but it is a byte-for-byte record of it, so the wording is quoted rather than
paraphrased, and the provenance is stated rather than assumed.

```text
Always keep in mind Arena Core Values:
1. Maximize P(Win): Spend cycles where they change the expected score. Don't polish infrastructure when the model is the bottleneck; don't tune hyperparameters when the features are missing the signal.
2. Own the Outcome: Verify end-to-end. A script that "should work" hasn't worked; a submission file that wasn't checked on disk isn't ready; a claim without a number in `evidence/` is a guess.

Work autonomously with zero manual input from the user. Verify everything line by line from official trusted sources with links. Flag any irregularities for review. Do not hallucinate and make stuff up. Put the prompt into the README.md.

For the DOE GEMS challenge (https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/ & https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/ & https://www.drivendata.org/competitions/306/competition-doe-gems/ & https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/ & https://www.drivendata.org/competitions/306/competition-doe-gems/data/ & https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif?rlkey=je8d8fepqfbst9lnwsq9rkplu&st=zj1lag1r&dl=0 & https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif?rlkey=yiao96uluqdkipf0h5vju71jf&st=rnino7ya&dl=0 & https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif?rlkey=kbykilvau066xuogoosbf4cq8&st=8junzdyw&dl=0):

Use the Blum & Mitchell (COLT '98, doi:10.1145/279943.279962) co-training setup:
- Split features into two views:
  * View A — potential-field and subsurface (gravity, magnetics, strain, seismicity)
  * View B — surface (DEM-derived curvature and slope, plus any radiometric bands in `training_features.tif`)
- Test conditional independence empirically by correlating each view's errors on labeled negatives — if strongly correlated, abandon co-training.
- Pseudo-label only where one view is confident and the other abstains, using whole-segment spatial blocks and a buffer so no leakage reaches evaluation.
- Use **disagreement as the discovery signal**:
  * A confident, B not → buried fault candidate beneath cover (flag for Phase 2 geological reasoning)
  * B confident, A not → surface artifact (roads, erosion lines) to suppress
- Compare against a single-view baseline on hide-and-recover segments to verify co-training isn't amplifying bias.
- Normalize to [0, 1], apply metric-aware placement, run the uniqueness gate, and confirm the output is not merely the union of the two views.
- For Phase 2 readiness, write a short geological reasoning note for every A-only candidate so reviewers can evaluate the buried-fault calls.

Study, analyze and explain why the following had the highest score out of the listed GEMSDOE websites and how to beat the 0.2778 score and get the top score of 0.3195 on the leaderboard:
- https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html - h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778
- https://buffedlizard55-lab.github.io/GEMSDOE36/docs/ - gemsdoe36-anderson-geothermal-pinn-38854-20261004T230000Z-9b9ea4e6-zeros.tif: 0.2750
- https://buffedlizard55-lab.github.io/GEMSDOE44/docs/
- https://buffedlizard55-lab.github.io/GEMSDOE46/

We're at ~0.2778 vs 0.3195 top on GEMS. The remaining ~0.04 gap is almost certainly geological domain knowledge, not post-processing. Generate 3–5 candidate geological hypotheses we haven't tried yet. For each:
1. What data layers it combines (name the bands in `training_features.tif` or external sources)
2. What physical signature it looks for
3. Why it should catch faults missing from the USGS/INGENIOUS catalogue
4. How it differs from our previous implementations
Rank them by expected DTI improvement vs implementation cost, and we'll validate the top one on spatially-blocked holdout before touching a submission slot. Do not spend a weekly submission slot on an idea that hasn't beaten our current holdout best on spatially-blocked validation.

Once the competition rasters are placed in `data/` (`bash scripts/download_competition_data.sh` if you have URLs, or manual drop from DrivenData) and `python scripts/prepare_data.py` is run, the full model pipeline can be executed and verified. Do all of this autonomously with zero manual input from the user.

Fix the "Predicted values must be in range [0, 1]" error. Must generate a UNIQUE .tif submission for the competition. Never copy a previous submission as the final output. Make sure the Github pages is clean and user-friendly. Have the one-click TIF/ZIP file download at the very top so the user does not have to scroll down and search for it. Provide a unique submission name and <=200-char submission note. Provide an Executive Summary subpage on the Github pages website as well.

Do your work in 3 passes:
Pass 1 — Implement and verify: Complete the task end-to-end. Run tests, linters, type-checks, or build steps that exist in the repo, and verify your changes actually work rather than assuming they do.
Pass 2 — Review and fix: Re-read every file you touched or created. Look for bugs, unhandled edge cases, broken imports, type errors, regressions, leftover debug code, or unintended changes. Fix anything you find and re-verify.
Pass 3 — Re-check against the user's original request: Re-read the user's prompt from the top and confirm every requirement, constraint, and detail they asked for is addressed. If anything is missing or only partially done, complete it now.

Please remember to create a PR once you are done.
```

# Current user brief — 2026-10-06

The following is the current task message, preserved as project instructions rather than endorsed factual claims. Leaderboard values, data availability, previous-session statements and causal interpretations must be re-verified. This message supersedes the older brief where they differ.

```text
Review the repo.

THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED!

MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION.  DO NOT COPY A PREVIOUS SUBMISSION UNLESS IT'S FOR LEARNING AND EDUCATION.  BUT WE MUST GENERATE A UNIQUE TIF SUBMISSION.

There should be an easy to download submission tif file as described by the prompt.  Read the entire prompt.

Co-training between a geophysical view and a surface view, with disagreement as the discovery signal. Blum and Mitchell (COLT '98, pp. 92–100, doi:10.1145/279943.279962) show that when each example has two views, each sufficient and approximately conditionally independent given the class, two learners trained on separate views can use each other's confident predictions on unlabeled data. View A is potential-field and subsurface (gravity, magnetics, strain, seismicity). View B is surface (DEM-derived curvature and slope, plus any radiometric bands present in training_features.tif). Test the independence assumption empirically: correlate each view's spatial-block out-of-fold errors on labeled negatives, and abandon the method if they are strongly correlated. Pseudo-label only where one view is confident and the other abstains, using whole-segment spatial blocks and a buffer so no leakage reaches the evaluation. The discovery signal is disagreement. Where A is confident and B is not, the fault may be buried beneath cover. Where B is confident and A is not, suspect surface artifacts such as roads or erosion lines. Because Phase 2 reviewers verify faults, write the geological reasoning for every A-only candidate. Co-training can also amplify bias, so compare against a single-view baseline on hide-and-recover segments. Normalize to [0,1], write the GeoTIFF, apply the repo's metric-aware placement, run the uniqueness gate, and confirm the output isn't merely the union of the two views.

The following sites should serve as a starting point for understanding how to generate TIF submissions.  These websites are researched, and tested and have generated TIF submissions.  But we need to generate high scoring submissions.

Here are the results from submissions into the competition, separated by ....:

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

[https://buffedlizard55-lab.github.io/11GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/11GEMSDOE/docs/index.html)

gems-structural-area06-v1: 0.0202

....

[https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html)

r7-nms3-dem10-scarp_0c9199f14e62:0.1294

r7-nms3-dem10-scarp_0c9199f14e62_allfinite:0.1294

....

[https://buffedlizard55-lab.github.io/15GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/15GEMSDOE/docs/index.html)

gems-tso1-20260929T005627Z-conj_alteration_mag: 0.0782

....

[https://buffedlizard55-lab.github.io/14GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/14GEMSDOE/docs/index.html)

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

[https://buffedlizard55-lab.github.io/GEMSDOE28/](https://buffedlizard55-lab.github.io/GEMSDOE28/)

h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-nan: 0.2708

h32-1-prethin-tip-euler-d2-8-20261003-31e35eee884e-nan: 0.2649

h36-1-rung30-blind-r1-20261003-b531dae0a36f-nan: 0.2710

h38-1-hf-euler-r30-r1-20261003-56a9f473edc7-nan:

....

[https://buffedlizard55-lab.github.io/GEMSDOE29/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE29/docs/index.html)

efd28-repro-20261003-1cc7dc534d51-nan: 0.2600

repo-c0-habitat-emission-20261003-a4d439b07426-nan: 0.0041

sgmc-off-catalogue-44k-20261003-c8dcd780e3fd-nan: 0.0512

wormrank-d28-20261003-59dcaf6dd11d-zeros:

wormsurv-filter-20261003-921f10960d6e-zeros:

xfit-c0-habitat-20261003-ca879db0089a-zeros:

xfit-h41-union-qfaults-20261003-9edb34b99e3a-zeros:

....

[https://buffedlizard55-lab.github.io/GEMSDOE30/](https://buffedlizard55-lab.github.io/GEMSDOE30/)

d28-poisson300m-offcat-44090-20261003T233156Z-91eae1ca: 0.2600

....

[https://buffedlizard55-lab.github.io/GEMSDOE31/docs/](https://buffedlizard55-lab.github.io/GEMSDOE31/docs/)

h27-4-solo-d28-20261004-8acb75e1-nan:0.2708

....

[https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html)

h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778

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

[https://buffedlizard55-lab.github.io/GEMSDOE39/](https://buffedlizard55-lab.github.io/GEMSDOE39/)

h40-e-disc-h40e-30k-zeros:

....

[https://buffedlizard55-lab.github.io/GEMSDOE40/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE40/docs/index.html)

h8-euler-lineament-depthcluster-20261006-785c4f5d5ce1:

h8-euler-lineament-depthcluster-20261006-785c4f5d5ce1-hard:

h45-eulerdepthreadcluster-20261006-f28e5cff6826-zeros:

....

[https://buffedlizard55-lab.github.io/GEMSDOE41/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE41/docs/index.html)

h42-submission-primary:

....

[https://buffedlizard55-lab.github.io/GEMSDOE42/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE42/docs/index.html)

xscale-worm-persistence-20261006T000541Z-nan:

....

[https://buffedlizard55-lab.github.io/GEMSDOE43/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE43/docs/index.html)

sup01-hgb21-sep40-n40000-20261006-bc2e4e9a8d6f-nan:

....

[https://buffedlizard55-lab.github.io/GEMSDOE44/docs/](https://buffedlizard55-lab.github.io/GEMSDOE44/docs/)

h46-twostageAB_20261006T160000Z_b0cfe956-zeros:

....

[https://buffedlizard55-lab.github.io/GEMSDOE45/](https://buffedlizard55-lab.github.io/GEMSDOE45/)

h51-km-faultzone-20261006-zeros:

....

[https://buffedlizard55-lab.github.io/GEMSDOE46/](https://buffedlizard55-lab.github.io/GEMSDOE46/)

r11f-scarp-radiometric-fusion-00e049b51218-zeros:

r12-scarp-rad-concordance-23e807e2de9f-zeros:

....

[https://buffedlizard55-lab.github.io/GEMSDOE47/](https://buffedlizard55-lab.github.io/GEMSDOE47/)

:

....

[https://buffedlizard55-lab.github.io/GEMSDOE48/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE48/docs/index.html)

:

....

[https://buffedlizard55-lab.github.io/GEMSDOE49/](https://buffedlizard55-lab.github.io/GEMSDOE49/)

:

....

[https://buffedlizard55-lab.github.io/GEMSDOE50/](https://buffedlizard55-lab.github.io/GEMSDOE50/)

:

....

[https://buffedlizard55-lab.github.io/GEMSDOE51/](https://buffedlizard55-lab.github.io/GEMSDOE51/)

:

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

WE NEED TO STUDY, ANALYZE, AND UNDERSTAND THE HIGHEST SCORE FROM THE GEMDOE SITE WHERE THE SUBMISSION TIF IS DOWNLOADED FROM WHICH IS THE FOLLOWING:

[https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html)

h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778

Why and how did this get the highest score and are we able to generate a submission that scores higher than 0.2778?

Answer the question using Phd level experience, knowledge, and judgement. Then use the answer to generate a unique TIF submission into the competition.  Must be unique submission unlike any within the GEMSDOE sites above.  Verify working line by line no hallucinations.

The following is the leaderboard for the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)

We need to quickly look at the results and results from the GEMSDOE websites above.

Before implementing, generate 3–5 candidate geological hypotheses we haven't tried yet, each naming: the specific layer(s) involved, the physical signature being targeted (e.g., an edge-detection or curvature transform), why it should catch a fault missing from the USGS/INGENIOUS catalogue rather than one already in it, and how it differs from anything already implemented in this repo. Rank them by expected DTI improvement and implementation cost. Validate the top candidate on our spatially-blocked holdout set before touching a weekly submission slot — do not spend a submission slot on an idea that hasn't beaten the current holdout best. If a candidate can't be validated without new external data, name the specific free, official source needed and check it's obtainable before proposing the idea as viable.

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

We have a good understanding of how our hypothesis, methodology, calculations, analysis are done so we should be able to figure out a way to score higher on the leaderboard using previous results and scoring that we have across the sites listed above.  We need to come up with distinct and unique strategies to score higher in this competition leaderboard.  We need to start doing heavy and deep research into the part of the project that matters the most, which is the scientific discovery of geothermal vents.  We should store all of our information and knowledge that we can gather from official verified sources.  This will serve as a starting point for other projects as well.  We need to think outside the box but still be grounded in proper scientific research, we are ultimately aiming for a top prize that many others are competing for.  So it's important to be contrarian but be smart about it.  We need to find sources of data that others are over looking or areas of the project when it comes to geothermal vents.  We need to do deep research and critical thinking and come up with new hypothesis to test.

0.3195	is the highest score right now so we need to design a new strategy, research, testing, analyzing, and generating submission system than the current website.  It should be unique, take unique approaches to generating a submission that can score higher than 0.3195.

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

### 1.1 The directives, itemised (the standing starting point, restated in the brief's own order)

The brief as received by this session is [`knowledge/07_brief_2026-10-06_session2.md`](knowledge/07_brief_2026-10-06_session2.md);
it carries **eleven** operative directives, and this list is that list — same order, same scope — so a
reviewer can diff prose against prose. (Earlier revisions of this README itemised ten, having folded the
re-read-the-prompt rule and the why-0.2778 rule into others; that folding is what let a session start from a
summary instead of from the brief, so it is undone.)

1. **Ship a unique, downloadable `.tif`** — not a copy of any prior submission; a unique name and a short
   note for the submission form; the download obvious at the very top of the site.
2. **Re-read the whole prompt before working** — the brief lives in this repository, and this file is where a
   session starts.
3. **Co-train two views of the same unlabelled pixels** — View A the potential fields and subsurface
   (gravity, magnetics, strain, seismicity), View B the surface (slope, curvature, scarp; radiometry where it
   exists *outside* the official cube, per `IR-52-001`/`IR-52-011a`) — and treat **disagreement, not
   agreement, as the discovery signal** (Blum & Mitchell, COLT '98, doi:10.1145/279943.279962): A-only ⇒
   buried beneath cover, B-only ⇒ suspect (roads, erosion, levees).
4. **Test the independence premise instead of assuming it** — correlate each view's spatially-blocked
   out-of-fold errors on labelled negatives, and abandon the mechanism if it is strongly correlated.
5. **Pseudo-label only across the confident/abstaining boundary**, in whole-segment blocks with a buffer, and
   **write the geological reasoning** for every A-only candidate.
6. **Benchmark against a single-view baseline on hide-and-recover**, because co-training can amplify bias.
7. **Normalise to [0, 1]**, write the GeoTIFF on the competition grid, and place mass **metric-aware** (the
   300 m kernel, the pixel-exact mask, the acceptance bar), not by percentile.
8. **Pass the uniqueness gate and be more than the union of the views** — never re-emit a prior answer as the
   product; priors are for learning.
9. **Propose 3–5 new geological hypotheses** — layers, physical signature, why they catch
   catalogue-missing faults, diff against repo history — ranked by expected DTI gain over cost; **validate the
   top one on the spatially-blocked holdout before spending a weekly slot**; any idea that needs new external
   data must name a free, official source and confirm it is obtainable.
10. **The site** — clean GitHub Pages, one-click `.tif` at the very top, an executive-summary subpage with the
    exact submission steps, the `[0, 1]` validator error explained and made impossible, official links for
    manual review, a live feed so nothing needs hand-checking, irregularities flagged.
11. **Three passes** (implement → review/fix → re-check against the request), then a **pull request merged
    into `main`**, plus the list of what remains.

**Why 0.2778 scored what it did, and what the bar is** — the reasoning the brief asks for in the same breath
as the build: [`knowledge/01_why_02778_and_the_bar.md`](knowledge/01_why_02778_and_the_bar.md). Note the
disagreement it records: the brief quotes 0.3195 as the leader, the fetched board says 0.3774
(`IR-52-020`, `registry/leaderboard_snapshot_2026-10-06.json`).

## 2. Layout

```
src/gems52/     metric.py      literal official DTI, kernel, credit bar, max_cover  (tested)
                grid.py        pinned 3730x3292 / EPSG:32611 grid, GeoTIFF writer+re-read receipt
                transform.py   resample-any-grid-to-the-grid helper
                features.py    the 27 derived layers (19 View A, 8 View B)
                cotrain.py     uint8 rank stack, per-view logistic learners, co-training round,
                               the independence test, the disagreement strata
                emit.py        accept_bar + lazy-greedy metric-aware emission (gain > bar*(1-wmax))
                holdout.py     three validation instruments: hide / block / tip, catalogue-masked
                gates.py       format legality + uniqueness / not-merely-the-union audit
                revealed.py    H53: exact set algebra over the scored family (|G|, the dead ring, the
                               atom accounting), the P(win) budget rule, strike recovery from the
                               credited dot cloud, metric-aware isolated-dot placement
                views53.py     H53: the View A / View B split, the conditional-independence test, the
                               disagreement strata, memory-safe band-at-a-time feature extraction
scripts/        prepare_data.py restore_data.py screen_layers.py run_pipeline.py
                validate_holdout.py build_submission.py refresh_feed.py research.sh
                build_revealed_submission.py   # the H53 artefact: calibration -> two views -> placement
                make_site_pages.py check_site.py
tests/          test_metric.py  (8 tests, including the marginal acceptance rule pixel-by-pixel)
                test_gates.py   (incl. the regression for IR-52-021)
knowledge/      00_brief 01_why_02778 02_hypotheses 03_negative_results 04_free_data_and_licenses
                05_instruments 06_provenance_and_irregularities
                07_revealed_preference_inverse   # the H53 inverse: |G|, the dead ring, the atoms,
                                                 # the broken instrument, the 171-feature screen
                08_hypotheses_H53                # H53-1..H53-5, ranked by measured effect
                (written for the next session)
evidence/       grid, band inventory, layer screen, folds, independence, strata, holdout tables,
                per-submission gate reports
registry/       data_manifest.json (23 pinned inputs + sha256), preregistration.json (decision rules,
                written before any fold was scored)
docs/           the GitHub Pages site; docs/data/*.json is its only source of numbers
submission/     built rasters + LATEST.txt
```

## 3. Reproduce it

```bash
python3 scripts/restore_data.py                 # 23 pinned inputs -> data/, sha256-checked
python3 scripts/prepare_data.py                 # bands + labels + elevation -> work/derived/
python3 -m pytest -q                            # metric parity + lattice weights + emission rule
PYTHONPATH=src python3 scripts/run_pipeline.py --stage fit --rounds 1 --mode tip
PYTHONPATH=src python3 scripts/validate_holdout.py --mode tip --emit topk
PYTHONPATH=src python3 scripts/build_submission.py --mode tip --arm <winner> --emit greedy
PYTHONPATH=src python3 scripts/refresh_feed.py   # regenerate the site's data/*.json
```

The H53 artifact is a historical experiment. The current top-of-site artifact is H57 and is research-only; the H53 rebuild command below reproduces that separate archive:

```bash
python3 scripts/restore_data.py                                   # 23 pinned inputs -> data/
PYTHONPATH=src python3 scripts/build_revealed_submission.py --tag r1   # ~3 min, 2 cores, <2 GB
python3 scripts/make_site_pages.py && python3 scripts/refresh_feed.py && python3 scripts/check_site.py
```

It writes the raster, reads it back, runs both gates on the written bytes, and emits
`evidence/revealed_{calibration,budget,format_gate,uniqueness_gate,submission_audit}.json`,
`evidence/independence_revealed.json`, `evidence/cotraining_views53.json`,
`evidence/submission_<name>.json` (which is what the site renders) and
`evidence/a_only_reasoning53.csv` — one row per emitted buried-fault candidate, for Phase 2 reviewers.
Rerunning reproduces the same sha256 even after the previous output has been published into
`docs/downloads/`, which was a bug and is now a test of the build rather than a hope.

`--mode` picks the instrument: `hide` (whole catalogue components removed), `block` (quadrant-blocked
as well), `tip` (only the along-strike ends of traces removed). Each writes its own
`evidence/*_<mode>.json`, so the two instruments' numbers cannot be confused with each other.
`bash scripts/research.sh tip hide` runs fit+validate for several modes in sequence.

## 4. What was actually found, before any of this was shipped

### 4.0 The H54 round: five findings that changed what this repo selects on

Full derivations in [`knowledge/10_revealed_preference_inverse.md`](knowledge/10_revealed_preference_inverse.md);
hypotheses and their ranking in [`knowledge/11_hypotheses_H54.md`](knowledge/11_hypotheses_H54.md).

1. **`|G|` = 14,088.7 px (0.2726 % of the footprint), and the ≤200 m ring around the mapped catalogue
   earns *exactly* zero credit.** Not modelled — measured. `h33-2-b2` (reported 0.2778) is a strict
   subset of `gems24-d2-8` (0.2600) with `A \ B` = 0 px verified on the bytes; the 6,436 px difference
   lies entirely inside 200 m of a mapped trace, and deleting it *raised* the score 6.8 %. Inverting the
   metric on that nested pair gives `T(B) − T(A) = 200.62 − 0.01424·|G|`, so "the ring earns nothing"
   *is* the value of `|G|`. An independent bracket from `T ≤ |G|` over all 13 scored files gives
   `|G| ≥ 8,128`. This **refutes** the corridor arm that §4's fourth bullet and `knowledge/02` H52-2
   made the primary emitter; `knowledge/01` §5 item 2 is struck through with the measurement.
2. **The hide-and-recover simulator does not predict the organiser's score.** Spearman
   ρ(reported, simulated DTI) = **−0.1045**, p = 0.734, n = 13. The group's best file on the board is
   the *worst* of the 13 on the instrument (lift 0.09× mass-matched random); the file the instrument
   ranks first scored 0.1563. Its premise — that the hidden truth is a held-out part of the mapped
   catalogue — is false by finding 1. Every selection made through that gate inherits the defect,
   including the H52 file's `promoted: false, forced: true`. New rule: an instrument must reproduce the
   ordering of artefacts whose real scores are already known before it may promote anything.
3. **Credit inside the champion file is concentrated in the double-corroborated atom, and that is
   exact.** The six atoms of `{A, B, C, E}` partition `E` = 121,131 px exactly, and the published scores
   give `t(A & C)` ∈ **[4,168, 5,223]** — density **16.3 %–20.5 %** against 13.87 % for the champion
   file as a whole and 2.79 % for uniform-random mass. `DTI(A & C emitted alone)` ∈ **[0.2546, 0.3190]**,
   central **0.3139**: a pure *budget reduction*, with no new geology, is worth up to +14.8 %. A
   cross-check fitted independently, `T = 471.6·S^0.2284`, predicts eight published scores to within 4 %
   (five within 1.5 %), including a file from a different family at +0.6 %.
4. **Nothing available here re-ranks inside the champion file.** 63 point and local-differential
   features reach a best blocked AUC of **0.5453** on the credited-vs-uncredited contrast (the maximum of
   63 tests); 108 structure-tensor coherence/gradient features reach **0.5122**. Habitat is strongly
   identifiable — AUC **0.7023** for the champion's dots against uniform random, on high-relief,
   LiDAR-scarp-positive, *radiometrically depleted* ground — and strongly useless: the tiers carrying
   4–20× less credit have habitat AUCs of 0.68–0.70. So `ρ_novel` is a stated prior in every projection
   here and never a point estimate.
5. **The strike of the credited structure *is* recoverable, and it is the right strike.** Structure
   tensor of the credited dot cloud: mean coherence **0.4197** against **0.2676** for a matched
   uniform-random cloud; 16.8 % of dots above coherence 0.8 against 2.2 % (7.6×). The two independent
   thinnings agree on the recovered orientation histogram to cosine **0.9952** while the random control
   is flat, and the dominant recovered strike is azimuth ≈ **010–020°** — NNE–SSW, the Basin-and-Range
   normal-fault strike of a footprint spanning 37.3–40.7 N, 116.2–120.0 W. This matters because
   `TPw = Σ_g max_x p·k` credits a truth pixel **once, at its best covering weight**: a dot 250 m off a
   trace earns it 0.167, a dot on the trace earns up to 3.0 truth-pixel-credits. The cheapest score in
   this metric is mass placed *along* structure already known to be credited, and across-strike mass is
   the opposite — it re-covers the same truth pixels (δ ≈ 0) and pays the full false-positive tax.

**What the emission therefore is.** Findings 1 and 3 fix the retained core and forbid the ring; finding 4
says a better *ranker* cannot be validated here, so the file does not pretend to one; finding 5 supplies
the novel half. Finding 2 is why none of this was selected on the holdout.
**H53-1 (this session): the discovery signal pays, but only after two of its own gates were repaired.**
Full write-up in [`knowledge/09_what_h53_found.md`](knowledge/09_what_h53_found.md); the numbers are in
`evidence/h53_holdout.json` and `evidence/dicoincidence.json`.

* **The brief's mechanism, implemented literally, produced a gate that could not fire.** The first version
  gated on a tile's *z-score* against the rolled null: one tile contributes one scalar, whose null s.d. is
  ≈ 0.3, so `|z| ≥ 3` demands a cosine of ≈ 0.9 and passes 0.0 % of tiles (measured). A gate that silently
  passes nothing looks exactly like a gate that passes nothing for physical reasons. Replaced with a
  **pair-relative percentile** (`agreement_percentile`, distribution-free), which is also the honest framing:
  the informative statement in a province with one dominant fabric is *"this tile agrees better than this
  pair's own tiles do"*, not *"these two datasets agree"* — that is the default here, and an earlier
  version of the arms that used the global gate counted 93 % of all candidate nodes as corroborated.
* **The gate, once it can fire, is what wins.** Fold-mean DTI at the same budget, same folds, same emitter:
  `B_corr + separation` **0.0387 tip / 0.0661 hide**, ungated union + separation 0.0357 / 0.0565, surface-only
  + separation 0.0289 / 0.0445, the same arm with its places rolled to another tile 0.0192 / 0.0369. Against
  the repo's previous best at this budget — tip `union_cor` 0.0320, hide `B_only` 0.0518 — that is
  **+21 % / +28 %**, with 3/4 and 4/4 fold support and the same comparator ordering on both instruments.
* **Separation, not density, is what the metric pays for.** The incumbent's own sweep is a ladder in
  spacing (2.24 px → 3.0 px → 3.0 px at 60,069 → 44,090 → 37,654 px) and its best file is 37,654 *single*
  pixels. So the emitter here is greedy top-`budget` under a **minimum separation**
  (`src/gems52/nodes.py::emit_nodes`): 37,654 pixels, all isolated, median nearest-neighbour distance 3.0 px
  — the same geometry the top of the ladder uses, filled with ranked evidence instead of a lattice.
* **What did not work, and is published rather than buried:** gating on *global* coincidence
  (37/100 pairs clear a Bonferroni z gate, so the gate stops discriminating); a per-tile z (above); and the
  gated arms without separation, which lose to the ungated union on both instruments. The eight-row arm table
  with all four controls is in `evidence/h53_holdout.json`.

* **The co-training mechanism failed its own gate.** One Blum–Mitchell round *lowered* View A's
  blocked AUC (mean Δ = −0.0159, fold support 1/4 on `hide`; 0.797 → 0.761 pooled earlier in the run), and its
  arm is the worst measured on both instruments — 0.0084 tip / 0.0078 hide against 0.0253 / 0.0396 for
  matched-budget `random` — so the pseudo-label round is **not** in the shipped field, and the failure is
  published (`evidence/holdout_*.json`, `docs/validation.html`). The premise is a subtler story, and we
  corrected our own earlier sentence about it: the pre-registered block-level test **could not fire** at this
  grid size (degenerate per-block false-alarm variance ⇒ correlation undefined, `spearman` 1.0 on all ties),
  the pixel-level logit correlation is weak (+0.1748 tip, +0.1316 hide against a 0.60 abandonment threshold),
  and the block-level *miss-rate* correlation on `hide` is **+0.8307** — the views miss the same
  neighbourhoods. So conditional independence here is **neither established nor refuted: it is unmeasured at
  the granularity the pre-registration specified**, and the r = 0.4298 / −0.1406 numbers this README carried
  at 22:20 UTC are **retracted**; `knowledge/03` §N-1 has the full table and the rule it taught us. The disagreement **strata** — the
  physical asymmetry between "field says fault, surface says nothing" and its converse — are, because
  they were measured separately and survived: A-only pixels sit in materially deeper cover than
  concordant pixels (mean depth-to-basement rank 455 vs 251) and carry a gravity step (6.06 vs the
  artefact class's 2.59), which is the signature a buried range-front fault has and a road cut
  does not.
* **The instrument had to be rebuilt to see the thing we were claiming.** Removing whole catalogue
  components makes a fold that is *structurally blind* to near-trace mass: only 0.5 % of a hidden
  component's pixels lie within 5 px of a still-visible trace, because a trace's neighbours belong to
  the same component. Yet the organiser's own clarification is that new-fault truth can lie within
  300 m of a known trace, and that mapping-truncation corrections are part of what the competition is
  for. So the `tip` instrument was added, where 88.5 % of the held-out truth *is* reachable from a
  visible trace. Numbers from the two instruments are never pooled.
* **Ranking a smooth field by global percentile loses to random emission.** At 37,654 px the top of
  an uncentred field is one big anomaly high, not the next fault. The fix is to apply every ranking
  *inside a permitted region* — footprint minus catalogue, and for corridor mass inside the 1–6 px
  corridor — which is what the arm table does; the naive global-percentile arms are reported alongside it
  so the comparison is auditable rather than asserted. The instruments, and the selection rule that follows
  from them, are written up in `knowledge/05_instruments_and_what_each_can_see.md`.
* **0.2778 is a placement result, not a discovery result** — and the H53 round measured it exactly
  (§4.0 finding 1): the champion file is the 0.2600 file with the ≤200 m ring deleted, 6,436 px, worth
  +6.8 %. The earlier sentence here ("removing 2,545 pixels of self-overlap with the mask, 6.3 % of the
  mass, raised DTI by 2.6 %") does not survive contact with the restored bytes: `h33-2-b2` holds **0 px**
  within 2 px of the catalogue and its minimum distance-to-catalogue is 223.6 m. See
  [`knowledge/01_why_02778_and_the_bar.md`](knowledge/01_why_02778_and_the_bar.md) for the algebra, the
  perfect-precision counterfactual (0.464 at the same budget), and the acceptance-bar table that shows
  the marginal rule across the entire live leaderboard is the same sentence: *emit a pixel iff it is
  within 224 m of a fault pixel the catalogue does not already have*.

### 1.2 Prior submissions of this family that this file must not be

`GEMSDOE52-CoTrain-Disagree-H52-1` (PR #2, 41,200 px, `c7e980f4…`), the r1 composite this session's
predecessor built (`gems52-h52-cotrain-disagreement-emission-composite-37654px-r1.tif`, 89,751 B,
`063fb724…`, `promoted: false`, `forced: true`), and the rasters in `data/scored/` (gems19, gems24) are
this group's own priors. The uniqueness gate compares against every one of them: this file puts **84.6 %**
of its 37,654 pixels where no prior ever reached, drops 655,900 prior pixels rather than re-emitting them,
and its 31,932-pixel difference from the ungated union at the same budget is the measured statement that it
is not a union either. r1 stays published — its evidence, its hash, its retraction of the co-training round
— because the point of the register is that the failures are as legible as the file.

`GEMSDOE52-CoTrain-Disagree-H52-1` (PR #2, 41,200 px, `c7e980f4…`) and the rasters in `data/scored/`
(gems19, gems24) are this group's own priors. The uniqueness gate compares against every one of them:
this file re-emits none of their mass where it is redundant (174,685 prior pixels dropped) and puts
78.8 % of its own mass where no prior ever reached. Their evidence stays published in `evidence/` and their
code stays runnable as `gems52_h1`; their *holdout claims* do not stand — see `IR-52-017` on
[the register](docs/irregularities.html).
## 5. Irregularities, stated plainly

Seven were added this round and are summarised in
[`knowledge/06_provenance_and_irregularities.md`](knowledge/06_provenance_and_irregularities.md) under
"H53 round": **IR-52-017** (the validation instrument does not predict the board), **IR-52-018** (the
≤200 m ring earns exactly zero, contradicting `knowledge/01` §5 item 2 and `knowledge/02` H52-2),
**IR-52-019** (no available feature re-ranks inside the champion file), **IR-52-020** (a per-block AUC
of 1.000 over n = 3 samples), **IR-52-021** (`gates.find_priors` swept the 19-band feature stack in as a
prior submission, producing a "prior union" larger than the footprint), **IR-52-022** (the downloads
index was built before the rasters were copied into it, so it was always one run behind), and
**IR-52-029** (two rounds shipped a submission in parallel — PR #8's
`gems52-h53-coincidence-gated-singles` and this round's `gems52-h54-revealed-core-strike-continuation`;
the site now offers the later one, which is one session's judgement call over another's shipped artefact
and is flagged for review, with the reason being a measurement: the instruments that promoted the H53
file are the ones `IR-52-023` shows carry no information about the organiser's score. Reverting is one
line in `submission/LATEST.txt` plus a `refresh_feed.py` run. The IDs this round added are 023–029; the
sibling round's H53 entries keep 020–022, and this round is numbered **H54** so that nothing collides).

The live public leaderboard's #1 is **0.3774**, not the 0.3195 stated in the session's opening
context (`IR-52-002` / `IR-52-020` — the same disagreement under the brief's own item number, now entered in
`knowledge/06` and on the register page rather than only referenced); the group's own 0.2778 currently sits at **#13 of 24 visible rows** (read twice this session, 21:2x
and 21:33 UTC, identical both times). Every file→score
mapping in this family (including the 0.2778 one) is **owner-reported**, not organiser-authenticated —
the board exposes no filename, hash or upload receipt, and GEMSDOE47 formally retracted its alleged
mapping. Full list: [`docs/irregularities.html`](docs/irregularities.html) and
[`knowledge/06_provenance_and_irregularities.md`](knowledge/06_provenance_and_irregularities.md).

Licences: all pinned inputs are the competition's own bundles or USGS/GDR open data; the sibling-derived
external CSVs in `data/external/` are **derived, not organiser-authenticated** and are used only as
optional corroboration, never as positive labels. See
[`knowledge/04_free_data_and_licenses.md`](knowledge/04_free_data_and_licenses.md).

## 6. No manual steps

The legacy historical pages use `scripts/refresh_feed.py` for their own `docs/data/*.json` receipts. The current H57 overview/audit use the H57 run receipts copied into `docs/data/h57_*.json`; no recurring leaderboard scrape or portal upload is performed. If a number changes, trace it to the H57 evidence receipt and its input/code hashes, not to hand-edited prose.

## 6.1 Current artifact and archive ownership

Never infer scientific approval from a pointer, a download link, a local format pass, or an exact-pattern pass. `submission/LATEST.txt` points to the H57 co-training raster below, and `submission/H57_RESEARCH_LATEST.txt` records the research-only pointer. The scientific gate failed. No weekly slot is authorized or used.

| scope | generator / evidence | artifact and status |
|---|---|---|
| **H57 current research artifact — DO NOT SUBMIT** | `scripts/run_h57_real.py`, `evidence/h57_holdout.json`, `evidence/h57_submission.json`, `evidence/h57_execution_provenance.json`, `docs/h57.html` | Co-training DTI 0.110665 vs View B 0.151305; paired mean lift −0.040641, 0/4. Local format and accessible-scope exact decoded-pattern checks pass; ≥20% support-novelty diagnostic fails at 0%; not-merely-union passes. No official score/portal contact/slot use. Execution runner hashes differ and no historical source snapshots or exact pinned input files are present in this checkout; the train-only pseudo-component selector cannot establish continuation across the masked boundary. Treat results as a failed research no-go, not promotion evidence. |
| **H56 historical synthetic methodology demo** | `docs/h56-cotrain.html`, archived H56 receipts | Synthetic demonstration only; it is not real-data validation or current upload advice. |
| **H55 / H55-PROFILE / H55-EDGE** | Separate archived runners, preregistrations and receipts | Historical experiments; cannot establish H57 approval. H55-EDGE has a separately disclosed protocol-subset deviation and failed gates. |
| **H55-1 paired shoulders** | Scoped runner/checker and separate receipt | Failed mean-lift gate (+0.002361 vs +0.005); no TIFF, no slot. |
| **H54 legacy audit** | `scripts/build_revealed_submission.py`, `docs/h54.html`, H54 evidence | Separate audit marker; no comparable holdout, no upload approval. |
| **R3-H1** | `docs/r3.html`, `docs/r3-hypotheses.html`, separate R3 receipts | Research-only, failed the preregistered gate; zero slots. |
| **H57 evidence bundle** | `docs/data/h57_holdout.json`, `h57_submission.json`, `h57_preregistration.json`, `h57_prior_inventory.json`, `h57_public_repo_priors.json`, `h57_candidate_local_gates.json`, `h57_execution_provenance.json` | Static copies from the persistent `evidence/`/`registry/` receipts. Public/local path counts and unique-content counts are separate fields. |
| **portal and leaderboard** | Official pages linked on the H57 site; dated observation `registry/leaderboard_snapshot_2026-10-07.json` | No portal was contacted. Snapshot is participant-level: 0.2778 rank 13, 0.3195 rank 7, 0.3774 rank 1; file-to-score attribution remains unauthenticated. |

`scripts/check_site.py` verifies local links, HTML/JS syntax, JSON receipts and artifact bytes. The corrected H57 scanner excludes the candidate and staged aliases from its own prior comparison; `tests/test_h57_runner.py` pins that regression. A format check and exact-pattern uniqueness check do not override the failed spatial promotion gate or the failed support-novelty diagnostic.

## 7. Remaining work after H57 (ordered, no slot spent)

1. **Do not rescue H57-H1 by tuning on its four failed folds.** The co-training arm lost to the matched View-B baseline by −0.040641 mean DTI and in all 4/4 folds. Treat the preregistered result as a no-go. Any changed learner, threshold, or training recipe needs a new registration and fresh spatial blocks.
2. **Test H57-H2: conductivity termination at independent potential-field intersections.** Band 17 plus magnetic/gravity bands and basement depth; add a preregistered cross-field geometry transform. Require the same buffered folds, a same-row View-B control, a matched max-union, and a ≥+0.005/3-of-4 gate. Main confounds: lithology, inversion smoothing, salinity/clay and shared source data.
3. **Then H57-H3: radiometric flank contrast aligned with a structural step.** Resolve band-6 provenance before treating it as radiometry. If external K/Th/U/ratios are proposed, first pin official source/license/coverage and avoid their use as labels. A radiometric contact alone is not a fault.
4. **Only then H57-H4: LiDAR scarp asymmetry cross-checked against deep structure.** Verify freely accessible official acquisition coverage and terms before feature work. Roads, channels, fan margins and DEM artifacts need explicit controls; candidate scarps require independent geological review.
5. **Keep H57-H5 resource context out of fault labels.** Wells/springs may prioritize Phase-2 review only; geothermal occurrence is not the competition's fault target and cannot validate a fault prediction.
6. **Strengthen provenance and promotion.** Reconcile the H57 runner hashes and train-boundary pseudo-component semantics, restore the exact SHA-pinned input bytes, and run a fresh preregistered holdout from immutable source snapshots before treating the scores as reproducible. Organizer-authenticated core inputs, an independent second-raster review, successful portal-format acceptance and a private-slot authorization are absent. Do not infer the hidden score from catalogue-zero holds. Public-prior exact-pattern coverage is broad but cannot include inaccessible assets; current exact pattern is distinct within scope, while the separate 20% support-novelty test still fails.
7. **Maintain explicit submission discipline.** Current `submission/LATEST.txt` is a research-only H57 output; no upload has occurred. Before any future slot, require an artifact receipt with `approved_for_weekly_slot: true`, all local gates, a comparable passing spatial holdout, independent confirmation, and an authorized human portal action.

Hypothesis details, per-hypothesis physical alternatives, implementation cost, and trusted links are in [`knowledge/17_hypotheses_H57_preregistered.md`](knowledge/17_hypotheses_H57_preregistered.md). The task/format/metric and external-source links are also available on [the H57 audit page](docs/h57.html).

## 7.1 Historical H55 analysis — retained for audit, not current H57 advice

Full version with every number: [docs/h55.html §11](docs/h55.html). Limitations first, because a list of
next steps that does not say what the current file cannot do is marketing.

**Limitations.**

* **Nothing here forecasts a portal score.** The instruments under-forecast the board by ~4× in absolute
  terms (this family scores ~0.05 on `hide` folds and 0.2778 on the portal), so a fold number is a
  *ranking* device. The only projection given a number is the placement gain in isolation (≈0.3044), and
  its assumption — that this field's covered area is exactly as truth-enriched as the 0.2778 file's — is
  measured in neither direction.
* **|G| rests on owner-reported scores.** Rasters, masses and geometry are SHA-256-exact; the DTI values
  paired with them are not organiser-authenticated (IR-52-003). `scripts/calibrate_g.py` prints every row
  so the pairings can be re-checked by hand.
* **The thermal layer is carried, not credited.** It won the pre-registered tie by **0.00003**. Anyone
  reporting that this file is better *because of* the INGENIOUS springs is reporting something the
  evidence does not say.
* **One tuned constant was set by inspection, not by a sweep**: the coherence floor 0.30 that truncates the
  thermal strike walk. The footprint's median coherence is 0.106, so that floor does nearly all the work
  and only 3,340 of 5,165,840 cells survive it.
* **The budget was chosen at fold prevalence (0.2 %), not board prevalence (≈0.157 %)**, and the rule
  preferred the smaller mass on a near-exact tie.
* **View A is dead at 100 m and was only tested at 100 m.** N-15 excludes it as a *primary emitter* at the
  scale the metric scores; it does not exclude a 300 m potential-field product used to *gate* a 100 m
  surface detection.
* **The external layers are uint8-quantised mirrors** (1st–99th percentile) of the official grids. Sources
  are named and reachable; a float32 re-reduction would sharpen every ratio-step layer.
* **The register's id space collided across concurrent sessions** (IR-52-030): two sessions allocated
  IR-52-021/022 to different findings. Both readings are recorded and cross-referenced rather than
  silently renumbered, because renumbering someone else's citation is how a register stops being checkable.

**Next, in expected-value order.**

1. **Sweep the budget on the board, once.** The fold `T(S)` curve is flat between 37,654 and 70,000 px on
   `hide` (0.0911 / 0.0920 / 0.0885), and `DTI = T/(0.2S + 0.8|G|)` is monotone increasing in `S` wherever
   `T` grows faster than `0.2·S`. One 60–80 k file settles it, and it is the only available experiment whose
   answer is a board number rather than a fold number.
2. **Re-derive the fold instruments at board prevalence.** `PREVALENCE = 0.002` in `scripts/run_h55.py`
   against a board-implied ≈0.00157: the optimal emission density moves with prevalence, so the whole
   selection was made ~28 % off. One-line change, full re-sweep.
3. **Sweep the coherence floor and the strike-walk length.** Both are one-line changes to
   `gems55.thermal.build`. If longer traces help, H55-3 goes from neutral to load-bearing and the ranking
   in `knowledge/12` changes.
4. **Test View A as a gate, not a ranker.** Emit View B's candidates only where a 300 m potential-field
   product is *not* actively contradictory. That is the one use of the potential-field data the
   measurements do not already exclude, and the version of the two-view idea that survives the refutation.
5. **Re-reduce K/Th/U/TC from the official USGS grids to float32.** Public domain, file list on ScienceBase
   item 657e1d85d34e23d3533209f7; the ratio-step layers have never been tested at full precision.
6. **Stop writing verification prose that no verification produced.** IR-52-031 is the third instance of
   the same shape in three sessions (after IR-52-007 and IR-52-026): `check_site.py` printed "Scientific
   slot gate remains closed" in its *success* message without ever opening the record that holds the flag.
   The durable fix is a rule, not a patch — every sentence a checker prints about a value must read that
   value, and where it cannot, it must say "not recorded" rather than guess.
7. **Give each session its own irregularity-id prefix.** IR-52-030 is a process failure, not a code failure,
   and it will recur on every parallel round until the id space is partitioned.
8. **Ask the organiser the question that would settle |G|.** Forum thread 11527 asked whether labels are
   LiDAR-scarp or geophysics-inferred and went unanswered. One confirmed number — the public test set's
   approximate truth-pixel count, or whether out-of-footprint mass is taxed — would be worth more than any
   remaining modelling hour, because both are already derivable from the metric algebra in `knowledge/01`
   given the answer.
