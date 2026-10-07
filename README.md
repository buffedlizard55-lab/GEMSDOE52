# GEMSDOE52 — fault-prediction research, evidence first

> **Current file (2026-10-07): research-only, do not upload.** H55 is a fresh, decoded-pattern-distinct single-band GeoTIFF and its on-disk range/grid checks pass. Its preregistered spatial holdout gate failed, so this run used **0 weekly competition slots** and has **no official score**.

## Current artifact — one-click download, with the gate shown first

| | |
|---|---|
| **GeoTIFF** | [`docs/downloads/gems52-h55-grav-rtp-logedge-37654-c4b8c10205da-zeros.tif`](docs/downloads/gems52-h55-grav-rtp-logedge-37654-c4b8c10205da-zeros.tif) |
| **ZIP** | [`docs/downloads/gems52-h55-grav-rtp-logedge-37654-c4b8c10205da-zeros.zip`](docs/downloads/gems52-h55-grav-rtp-logedge-37654-c4b8c10205da-zeros.zip) — contains exactly one GeoTIFF |
| **File / hash** | `gems52-h55-grav-rtp-logedge-37654-c4b8c10205da-zeros.tif` · SHA-256 `f0732d40d57b92d3f082eb2b910b6e6951b7238e7616f9e6e9c6c22ee9f1c7f8` |
| **Bytes / grid** | 134,874 · 3730 × 3292 · one float32 band · EPSG:32611 · 100 m |
| **Range error fixed locally** | Written-byte read-back: min 0, max 1, no NaN/Inf; exact sample bounds/transform; internal validity mask matches the sample footprint. This does not certify organizer portal acceptance. |
| **Identifying note (≤200 chars)** | `H55 paired gravity-RTP LoG edges; 37,654 metric-placed cells; spatial holdout FAILED; research-only, unscored.` (110 chars) |
| **Decoded uniqueness** | Exact canonical prediction pattern differed from all **414** supplied accessible aligned prior rasters; matched-budget A/B max-union also differed. The all-prior support union is saturated: **0% novel support**, so the strict support-novelty/slot gate remains failed. Scope excludes unlinked/private/inaccessible files. |
| **Holdout / promotion** | Mean local catalogue-recovery DTI **0.195217** vs View-B **0.194671**; lift **+0.000546**, positive in **2/4** folds. Required: +0.005 and 3/4. **Failed. Do not spend a weekly slot.** |
| **Official score / slots** | No upload, no organizer evaluation, no authenticated public score; **0 slots used**. |
| **Protocol boundary** | The H55-1 register listed LoG transforms for bands 13/11/18 and 2/9; code applied the new transform only to bands 13 and 2. Bands 11/18/9 remained raw/pre-existing R2 features. The failed result is for this narrower implementation, not the full registered feature set; see [post-run audit](evidence/protocol_deviation_h55.json). |
| **Per-pixel geology** | [816 emitted A-only candidate rows](docs/downloads/gems52-h55-grav-rtp-logedge-37654-c4b8c10205da-zeros-a-only-reasoning.csv) with coordinates, measured inputs, alternative explanations and verification caveats. Hypotheses only—not confirmed faults or geothermal vents. |
| **Exact checks / receipts** | [Full raster receipt](docs/downloads/gems52-h55-grav-rtp-logedge-37654-c4b8c10205da-zeros-audit.json) · [validation page](docs/validation.html) · [hypothesis register](knowledge/12_h55_hypotheses_preregistered.md) |
| **Current site** | [Open the landing page](docs/index.html) · [submission guide](docs/executive-summary.html) |

## What the new test did — and did not establish

Four hypotheses were ranked **before** H55-1 implementation. A post-run source audit found a protocol deviation: the frozen candidate-feature list names LoG transforms for gravity bands 13/11/18 and magnetic bands 2/9, but the actual H55 transform was applied only to bands 13 and 2. Bands 11/18/9 remain raw/pre-existing R2 features, not H55-transformed channels. The +0.000546, 2/4 result therefore evaluates the narrower implemented variant—not the full registered feature set. The original registration is preserved; do not retest omitted channels on these same folds. See [the deviation receipt](evidence/protocol_deviation_h55.json) and [IR-52-037](knowledge/06_provenance_and_irregularities.md).

USGS Death Valley/Amargosa reports support broad physical plausibility but also document magnetic/lithologic and fluvial alternatives; they do not validate any H55 pixel. The H55 co-training diagnostic found weak blockwise negative-error correlation (max |r| 0.0844 over 2,093 blocks), which is not proof of conditional independence. One separate whole-segment exchange changed View B by +0.001488 mean over baseline (3/4 positive), below the frozen +0.005 bar; the reverse exchange hurt View A. Co-training was not used in the emitted primary TIFF.

The public DrivenData leaderboard was fetched manually on 2026-10-07: leader 0.3774; `DARD` 0.3195 at rank 7; participant `extradr19` 0.2778 at rank 13. The board does not expose TIFF filenames or hashes. It does not authenticate 0.2778 to the sibling site's H33-2-B2 file or to this repository. H33 pixel forensics confirm a 2,545-cell flank-pruning relation to its cited base, not the cause of any score. See the [dated board snapshot](registry/leaderboard_snapshot_2026-10-07.json) and [0.2778 autopsy](docs/forensics.html).

A fresh owner-site crawl found **395 distinct linked TIFF URLs**, of which **389** were aligned single-band prediction rasters; all 389 eligible bytes are now in ignored `data/review/priors/`. Four linked TIFFs were not eligible submissions and two historical links no longer resolve. There are still no supplied links for `53GEMSDOE` or `54GEMSDOE`; private/unlinked/external files are outside scope. The stricter ≥20% support-novelty diagnostic remains failed because dense/diagnostic prior supports saturate the union. Exact decoded-pattern difference is reported separately; neither result proves global novelty.

## Start here each session

Read this current status, the full original brief preserved below, `knowledge/08_current_user_prompt.md`, `knowledge/12_h55_hypotheses_preregistered.md`, `knowledge/06_provenance_and_irregularities.md`, and `registry/h55_preregistration.json`. Historical sections below are retained as an audit trail; where they present an older H53/H54/R2 artifact as current, this current-session block supersedes them.

**Maximize P(Win):** do not use a limited portal slot for an idea that missed the registered spatial gate. **Own the Outcome:** the output was read back from disk, compared against the finite accessible prior inventory, and its failed gates are published rather than softened. The 4-fold known-catalogue hide/recover score is not a forecast of hidden-label performance.

## Reproduce H55 from the pinned local data

```bash
.venv/bin/python scripts/restore_data.py
.venv/bin/python scripts/prepare_data.py
.venv/bin/python scripts/review_sources.py --download-priors --workers 4
.venv/bin/python scripts/run_structural_pipeline.py --stage all
.venv/bin/python scripts/validate_h55.py --stage all
.venv/bin/python scripts/refresh_feed.py
.venv/bin/python scripts/publish_site_h55.py
.venv/bin/python -m pytest -q
.venv/bin/python scripts/check_site.py
```

The core 23 input files match owner-side pinned SHA-256 values, not organizer-authenticated bytes. No radiometric band is present in the 19-band `training_features.tif`; no external GDR dataset or prior-submission pixels entered H55 model inputs. `data/`, `work/`, feature arrays and models remain ignored; only the small GeoTIFF/ZIP, reasoning table, and audit receipts are published. Automated DrivenData scraping is disabled by source policy; the board is a dated manual snapshot, not a live feed. There is no automatic portal upload.

## AI-use disclosure

If this candidate is ever considered for a submission narrative, disclose that generative AI assisted with repository/source review, hypothesis drafting, code assistance and documentation. Numerical data restoration checks, feature transforms, model fitting, fold scoring, pseudo-label diagnostics, TIFF writing/read-back and audits were executed by the listed scripts; no hidden labels, portal scores or prior-prediction targets were supplied. The full statement and limits are in [`knowledge/13_ai_use_h55.md`](knowledge/13_ai_use_h55.md), as required by the official rules.

## Historical brief and session record

The material below preserves earlier session notes and the verbatim user prompt. Claims such as an older artifact being "current", a stale board score, or a previous projection are **historical claims**, not the present release decision. See the dated receipts above for current facts.

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
task prompt as a fenced block, and that block is reproduced here unaltered — including the URLs, the
character counts and the sentence about radiometric bands, which is *conditional* ("any radiometric bands in
`training_features.tif`") and resolves to none, as `knowledge/04` and `docs/irregularities.html` explain.
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

The H53 artefact — the one the site offers at the top — is built by a single idempotent command:

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

`docs/data/*.json` is regenerated from `evidence/` by `scripts/refresh_feed.py`;
`.github/workflows/feed.yml` runs it nightly and on push, and the site renders only from those files.
If a number on the site is wrong, the fix is the evidence file, never the HTML.

## 6.1 Two rounds now share this repo — who generates what

Three rounds shipped artefacts and two of them rewrote the same files, so the ownership is written down
rather than left to be rediscovered:

| owner | generates | artefact |
|---|---|---|
| **H54 (this round)** | `docs/h54.html`, and the one-click download bar inserted at the top of `docs/index.html` and `docs/executive-summary.html` between `<!--H54BAR-->` sentinels | `submission/gems52-h54-revealed-core-strike-continuation-50517px-r1.tif` — **the candidate this round offers**, `submission/LATEST.txt` |
| R2 (PR #9) | `scripts/publish_site_r2.py` → `index.html`, `executive-summary.html`, `validation.html`, `forensics.html`, `method.html`, `hypotheses.html`, `sources.html`, `irregularities.html`, `feed.html`, `h53.html`, `downloads/index.html`, `README.md` | `submission/gems52-r2-signednormal-37654-1f751ac9b6ee-zeros.tif`, self-labelled *"Research-only. Do not upload this run."*, `submission/R2_LATEST.txt` |
| H53 (PR #8) | `scripts/build_h53_submission.py`, `docs/h53.html` | `submission/gems52-h53-coincidence-gated-singles-37654px-r1.tif` |
| both | `scripts/refresh_feed.py` → `docs/data/*.json`, stages rasters and the ZIP into `docs/downloads/` | — |

`scripts/make_site_pages.py` used to write `validation.html`, `feed.html`, `irregularities.html` and
`sources.html` from its own templates. **It does not any more** — that clobbered the R2 site and failed
R2's `check_site.py` invariants (arm means rendered from the current receipt; a failed-gate warning on the
two top pages). It now writes exactly one page and edits two, idempotently.

`refresh_feed.latest_submission()` prefers whichever marker file names an artefact that has a complete
gate report of its own (`evidence/submission_<stem>.json`), so the site never offers a file whose audit it
cannot show. Today that is `LATEST.txt` → the H54 raster. `IR-52-029` records the choice, the reason, and
that reverting is one line. Both other artefacts stay in `submission/`, stay downloadable, and are now
*priors* for the uniqueness gate: measured prior union **1,137,974 px over 23 rasters**, novel pool
440,192 px, **0** collisions between the H54 novel mass and any prior pixel.

## 7. Remaining work, limitations, and what would change the answer

Ordered by expected effect on the score the organiser actually computes.

1. **Recover the `h19-5` field, not its emission.** The single highest-value artefact this group could
   produce next is the top 16,678 px of the *ranked field* behind `gems19-h19-5`, worth ≈0.2975 by the
   same algebra that predicts eight published scores to within 4 %. We hold only its thresholded
   emission, and `knowledge/07` §6 measures that no feature computable from the provided grids
   re-ranks inside it (best blocked AUC 0.5453 over 63 point features, 0.5122 over 108 structure-tensor
   features). If any sibling checkout still holds the field array, this is a one-command win.
2. **Get real egress.** Only `pypi.org` and `api.github.com` respond from this sandbox;
   `raw.githubusercontent.com` and `drivendata.org` both die at HTTP 000. That blocks three things at
   once: the live board (so every file→score mapping here stays owner-reported, `IR-52-003`), USGS
   ComCat event-level seismicity (`knowledge/04` D-1 — service and licence verified live, 7,519 events
   for a comparable query, no authentication), and the QFaults **trace geometry**. The restored
   `gdr_qfaults_traces.csv` carries 1,126 traces with `slip_rate`, `recency`, `slip_sense` and
   `map_scale` but **centroids only** — 376 in the footprint, 77 on the mapped catalogue, mean distance
   to it 595 m, so the layer is largely independent of the labels and worth rasterising the moment a
   polyline is obtainable.
3. **Separate the two readings of the dead ring.** Either the organiser's mask is a ~2 px buffer
   (contradicting the staff reading recorded in `knowledge/01` §1 and `knowledge/02` H52-2) or the
   hidden truth never comes within 200 m of the mapped catalogue. One question in the discussion forum
   resolves it, and the answer changes whether the 1–2 px corridor is emittable at all. Both readings
   give the same rule today, so this is not blocking — but it is the cheapest large uncertainty left.
4. **Replace the broken instrument rather than only labelling it.** `IR-52-017` says the whole-component
   hide simulator carries no information about the real score. A calibrated replacement needs a
   pseudo-truth that reproduces the hidden truth's *measured* statistics — ~14,089 px, ≥200 m from the
   mapped catalogue, NNE–SSW linear traces — and any such construction embeds the hypothesis it is meant
   to test. Until one exists, every claim here rests on the set algebra, and the algebra only covers
   artefacts the organiser has already scored.
5. **`ρ_novel` is a prior, and that is the whole risk.** The retained half of this file's credit is
   bounded exactly; the novel half's is not, and `knowledge/07` §6 explains why nothing available here
   can measure it. The budget was chosen so the retained core carries the score if the novel half is
   worthless (worst case 0.2301 against a 0.2778 floor), and the projection is an integral over a
   stated prior — printed on the overview page, never described as a forecast.
6. **Approximations to tighten if the arithmetic is ever reused elsewhere.** `M = T` (licensed by the
   >200 m dot separation, not exact); additivity across disjoint atoms (submodularity alone gives weaker
   bounds); `|G|` *defined* by "the ring earns nothing", so a ring that earns a little moves every
   credit in §3 of `knowledge/07` down with it.
7. **Small, open, and worth a look.** `refresh_feed.py` still cannot parse the live board because the
   table is built client-side (`IR-52-016`) — the site serves a dated snapshot and says so; the H52
   artefact and its `evidence/` remain in the repo with their holdout claims labelled as not standing,
   rather than being deleted, because a removed measurement cannot be re-checked.
