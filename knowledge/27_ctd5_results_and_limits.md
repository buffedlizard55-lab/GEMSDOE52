# CTD5 results: a new raster, a failed method gate, and a saturated uniqueness registry

**Verdict: NEGATIVE. Download for research is OK. DO NOT SUBMIT. No competition slot was used.**

The new file is `gems52-ctd5-cover-disagreement-20261008-a24c35d1-b58bae0f0e.tif`.
SHA-256: `a6e6e44aebaf057989e254bd5ce3729e5a94836c0e5687a95e91e3fc8a40c686`.
It contains newly inferred predictions, not copied prior pixels. Local format validity and decoded-pattern novelty **do not** override a failed lane gate or authorize a weekly upload.

## 1. Answer to the H33 question, with the evidence boundary intact

The **owner-reported, NOT ORGANIZER-CONFIRMED** attribution is `h33-h33-2-b2` → **0.2778**. The current [GEMSDOE32 source](https://github.com/buffedlizard55-lab/GEMSDOE32/blob/0d6a6243147cd63a2000412d575d4c80a36d3a62/docs/index.html) instead explicitly says **“NO ORGANISER SCORE EXISTS”**. We cannot settle the conflict without a submission-page receipt tying the file/hash to the score. The user also supplied conflicting statements about the leaderboard top; neither is a fresh, authenticated observation from this session.

What **is** measured from the hash-verified rasters (`evidence/ctd5_reference_forensics.json`):

- The immediate H27 base has **40,199** positive cells; H33 has **37,654**.
- H33 adds **zero** cells and removes **2,545**. Every removed cell is **off** the known-fault pixels but within **200 m** of them.
- H33 is exactly the base restricted to distance **greater than 200 m** from the catalogue. It is a flank-pruning ablation, not a new geological detector.
- These are raster counts/distances, not competition scores. The alternate 6,436-cell story compares a different, larger ancestor, not this immediate parent.

Under the requested DTI, write `T=TPw`, `F=FPw`, `N=FNw`. For a fixed hidden truth set, deleting predictions cannot increase `T`, cannot increase `F`, and cannot decrease `N`. A genuine paired score increase therefore means the false-positive reduction more than compensates for lost maximum-cover credit. If deletion loses credit `c` and removes false-positive mass `f`, the exact condition is:

`c × (1 − 0.2 × old_DTI) < 0.2 × old_DTI × f`.

The [organizer's pixel-exact mask clarification](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4), preserved in the prior dated source audit, excludes **known pixels** from penalties. It does not automatically exempt the off-catalogue ring. Thus the old homepage's “masked pixels always pay the false-positive tax” explanation is wrong. Likewise, “the removed ring earned exactly zero”, a solved hidden-truth count, an exactly credited reusable core, and a guaranteed leaderboard ceiling do **not** follow from the public score/file list. They require additional, unverified assumptions about max-cover overlap and score attribution.

**Can a higher-scoring submission be generated?** It is scientifically possible, but this run supplies **no evidence that its new file would do so**. The testable route was new geophysical/surface disagreement, with no H33 core reuse. Its registered test failed; promising a higher score would contradict the evidence. Fault candidates also do not establish geothermal vents, fluid permeability or a reservoir.

## 2. What was actually run

Read the frozen hypotheses/protocol in `knowledge/25_ctd5_preregistered.md` and its hash in `registry/ctd5_preregistration.json`.

- Restored all manifest-pinned mirror inputs without user input; moved the real core bytes into ignored `data/`; ran the repository download wrapper and `prepare_data.py`. Removed the misleading small tracked placeholder TIFFs from Git, **not** the local restored data. Core provenance is integrity-pinned, not organizer-authenticated.
- The cache was absent. Rehydrated the existing shared `structural.build` once, not a new feature pipeline. Used **33 A / 19 B channels**, no external features, no prior predictions. The disputed band 6 is provisionally isolated in B; its primary identity/units remain unresolved.
- Used the shared whole-original-component folds, **80 px Euclidean buffer**, **36 px transform support**, fold-visible catalogue only, and pixel-exact visible-fault masking. No translated pseudo-truth, no catalogue-distance predictor, no core copied from any prior submission.
- Ran a raw and shallow-model feature-alone leakage canary for every used feature on every fold. **HOLDOUT-DTI diagnostic AUC**, not a DTI score: maximum direction-insensitive AUC **0.668330**, below the registered alarm **0.90**. This screens for obvious leakage; it does not prove that all upstream data are independent of mapping.
- **HOLDOUT-DTI diagnostic negative-error correlation**, not a score: maximum absolute Pearson/Spearman **0.098507** across **2,085** blocks before transfer, **0.106907** after. Both are below the abandonment threshold **0.60**. Catalogue-zero negatives are proxies, not verified fault absence. Weak error correlation does not establish the sufficient-view or conditional-independence premises of Blum–Mitchell.
- Executed exactly **one** pseudo-label exchange, **14,919** total receiver-training pixels across folds and directions. Donor rank at least .95, receiver rank .35–.65, whole connected segments, wholly inside training and a single 50×50 block, no overlap with evaluation or sampled training labels. No second exchange or post-result hyperparameter search.
- Used the template's 3 px sparse-node placement. It is a fixed metric-motivated **heuristic**, not a theorem about optimal spacing. No zero-score fill.

## 3. HOLDOUT-DTI — descriptive results, not a promotion claim

Every entry below is **HOLDOUT-DTI**, evaluator **`gems52-pooled-hide-v1`**, **53,186 withheld positive pixels**, pooled TPw/FPw/FNw, alpha **0.2**, beta **0.8**, **300 m triangular kernel**. Intervals are conditional **95%** paired physical-spatial-cluster bootstrap intervals, **148** active 20 km clusters / **1,000** draws. They are not organizer scores or leaderboard intervals.

| Procedure | HOLDOUT-DTI | 95% CI |
|---|---:|---:|
| Single A control | 0.027431 | [0.019046, 0.036832] |
| Cover-matched A control | 0.026722 | [0.017924, 0.036294] |
| Single B control | 0.106749 | [0.089076, 0.124951] |
| A/B maximum control | 0.102361 | [0.084791, 0.121174] |
| Disagreement before transfer | 0.021217 | [0.014514, 0.028823] |
| Disagreement after the registered transfer | **0.018848** | **[0.012421, 0.026020]** |

**Mandatory comparability warning:** the attempted per-fold budgets were 5,920 / 3,058 / 1,233 / 1,794. All single-view/union controls filled them; the candidate filled only **2,145** (before) and **2,041** (after) in fold 1. The other folds filled their target. Consequently the primary candidate-versus-control comparison is **budget-incomparable and ineligible for promotion**, regardless of the large descriptive gap. The result rejects this procedure at the registered operating point; it is not a clean falsification of the buried-fault geological mechanism. We did not change the budget or fill empty support to rescue it.

The final artifact has a **12,000-cell** global budget. It is an OOF mosaic, not a subsequently refit all-data model; inter-fold rank calibration and model-boundary seams are additional unvalidated limitations. The holdout measures fold-specific hiding/emission masks, not the submitted file against inaccessible new-fault truth. Historical R4 capture, H59 tip/mean-DTI and translated pseudo-truth values are not pooled-DTI comparators; they were not relabelled as this run's current holdout best. No result here satisfies the user's required current-best promotion condition.

Receipts: `evidence/ctd5_holdout.json`, `ctd5_post_holdout.json`, `ctd5_pseudo_exchange.json`, `ctd5_independence.json`, `ctd5_canary.json`.

## 4. The uniqueness rule really fired — no workaround

The source audit read all **52 supplied owner repositories**. It downloaded **526 distinct Git blobs**; **524** are aligned single-band predictions. With local historical submissions, the gate processed **541** files, **360** distinct decoded arrays. One H60 raster arrived through upstream PR #34 after the frozen scan. A supplemental check against the unchanged field/dots raises the closure total to 542 files / 361 decoded patterns; its three-pixel fraction is 0.271917 and does not change the original STOP. This is not a claim to cover private, release-only or externally stored artifacts. No URLs were provided for 53GEMSDOE / 54GEMSDOE.

Exact tie-aware Spearman over **4,593,171 eligible pixels**:

- Maximum against the pre-placement surface: **0.068203**.
- Maximum against final dots: **0.013418**.
- Exact decoded matches: **0**.
- Maximum directed fraction within 3 px of a prior: **1.000000** → exceeds **0.70**, therefore **DUPLICATE / STOP**.

This is not a cosmetic hash change; the raster is new inference and not a maximum/union. Nonetheless, under the **literal registered proximity rule** it fails. The [13GEMSDOE spacing-five lattice](https://github.com/buffedlizard55-lab/13GEMSDOE/blob/92ee6f074323f161eed837b80ec3ee5b662e26f5/docs/downloads/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif) covers **every eligible pixel** within 3 px, measured independently in `evidence/ctd5_registry_saturation.json`. Therefore **no nonempty prediction on this frozen footprint can pass this inclusive registry's proximity rule**. A spacing-five square lattice on integer cells has maximum interior distance sqrt(2²+2²), already below three pixels; the measured footprint coverage confirms the boundary case too.

We did not remove that inconvenient prior, restrict the output to avoid it, relax the threshold, or try another hypothesis. The negative artifact remains downloadable for inspection, explicitly **not a successful unique-lane competition submission**. A future shared selector must define the registry's treatment of universal-coverage probes *before* another experiment, or stop at a cheap registry-saturation preflight. That is a future protocol decision, not a private exception made here.

## 5. Geological review and output checks

The TIFF is **83,917 bytes**, single-band float32, EPSG:32611, shape **3,730 × 3,292**, Affine coefficients **[100, 0, 243350, 0, -100, 4508550]**, no nodata tag, all finite **{0,1}**, **zero** mass outside the feature footprint. The writer rejects NaN, infinity and range violations before writing; a separate validator reopens the file and compares it to the pinned sample. The ZIP contains **only one TIFF**, byte-identical to the canonical file. A local pass does not guarantee organizer acceptance. The exact historical cause of the user's range-error message remains unconfirmed.

Every one of **1,521 A-only proposal segments** has a geological-review row, and every emitted cell has a row (**12,000**, of which **3,234** meet the strict A-only criterion). Context is measured A/B operating rank, cover-band value, gravity gradient and slope. The named confounder is **a non-fault basin-fill density boundary or volcanic lithologic contact**; the falsifier is independent terrain/contact/field-offset evidence. No local road, rock type, hydrothermal alteration or slip event is invented.

The asymmetric surface differs from `max(A,B)`; the final file differs from the union of separately emitted A/B controls, from the maximum-field emission, and from both single views. The maximum-field control differs at **23,798** cells. A high-A/middle-B point and a high-A/high-B point have equal union score but different disagreement scores, so the method is not merely a rescaling of the union.

## 6. What should happen next — not another blind retune

1. Resolve the **registry saturation** policy in the shared selector, prospectively. Until then, this lane cannot produce a nonempty proximity-gate pass on this footprint.
2. Obtain organizer-authenticated input checksums/download provenance and a file-linked submission receipt. No credentials should be put in chat or the repository. Current weekly allowance cannot be inferred from historic pages.
3. Audit the physical identity and upstream derivation of band 6 and modeled basement/conductivity layers against official release documentation; mirror-to-mirror agreement is not independent source verification.
4. Plan a genuinely budget-feasible disagreement protocol **before** scoring. Do not quietly re-register CTD5 thresholds to cure fold 1. Surface-only detection remains a control, not a permitted replacement lane in this session.
5. For a future data expansion, official USGS 3DEP/GeoDAWN raw products and INGENIOUS resources are named in the source table, but those hosts were not obtainable under this sandbox's egress policy. None is claimed downloaded from its official host or viable for this completed run.
6. Preserve the negative outcome and AI-use disclosure. This assistant wrote code, documentation and candidate-review templates; no geologist verified the emitted structures and no field observations were collected.

**Operational values:** Maximize P(Win) means not spending a scarce slot on an unvalidated candidate. Own the Outcome means publishing the file, failed gates, raw evidence, provenance gaps and working reproduction—not changing the verdict to make the run look successful.
