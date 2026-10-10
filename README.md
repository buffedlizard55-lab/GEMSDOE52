# GEMSDOE52 — DOE GEMS Prize (DrivenData #306): submission status and method

**Competition:** [DOE GEMS Prize, DrivenData #306](https://www.drivendata.org/competitions/306/competition-doe-gems/) ·
[Problem description and metric](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) ·
[Leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) ·
[Data tab (login)](https://www.drivendata.org/competitions/306/competition-doe-gems/data/)

**Site:** `docs/index.html` (GitHub Pages) · **Session branch:** `arena/9d9926bc-gemsdoe52` · **Last update:** H88 round, 2026-10-10

---

## START HERE — the current file

| | |
|---|---|
| **Download** | [`docs/downloads/h88-candidate.tif`](docs/downloads/h88-candidate.tif) (single-band float32 GeoTIFF) · [`.zip`](docs/downloads/h88-candidate.zip) |
| **Suggested submission name** | `h88-basement-step-cat200-37654px-20261010` |
| **Note (≤140 chars)** | `H88 basement-step coherence (band 15 cover); 3px spaced; 200m ring out; binary; see holdout` |
| **SHA-256** | `636b4b9f75cc19980387b410575d433a8f1a93bfb29ffdde7386d75a6209aa4c` |
| **DOWNLOAD** | **YES** — format-valid (independent check PASS, `evidence/h88_independent_verify.json`), decoded-pixel unique |
| **SUBMIT** | **NO** — pre-registered holdout test is negative (below the random control) |
| **Organiser score** | none. No file in this repository has an organiser receipt. |

**How a submission is made** (the portal form asks for a file, a name and a note): download the `.tif` above, open the competition's submission page (login required; reached from the [competition page](https://www.drivendata.org/competitions/306/competition-doe-gems/)), upload the file, enter the name and note, and submit. The owner reported the portal error "Predicted values must be in range [0, 1]" for an earlier upload; which container caused it is **not verified**. This file writes 0.0 outside the footprint, so every pixel is finite and inside [0, 1]; the organiser's page says "null or nan" outside the bounds (IR-H85-004).

**Do not submit this file to beat the leaderboard.** Its holdout score is below random (table below). A new round
must beat the repository's holdout bar (0.189200, H82) before any slot decision, and the slot decision is the owner's.

---

## What the H88 round measured

Instrument: the repository's shared hide-and-recover folds (label-blind quadrants, 80 m buffer, visible-catalogue collar),
evaluator `gems52-pooled-hide-v1` (α 0.2, β 0.8, 300 m triangular kernel), `53,186` withheld
positive pixels over 4 folds. Every number below is **HOLDOUT-DTI** (not an organiser score).

| arm | HOLDOUT-DTI | 95% CI |
|---|---:|---|
| **H88 basement-step coherence (this file)** | **0.048050** | [0.032189, 0.064477] |
| random (same placement, control) | 0.080426 | [0.070223, 0.090973] |
| gradient magnitude only | 0.047641 | [0.031543, 0.064464] |
| raw depth-to-basement | 0.037456 | [0.025136, 0.050826] |
| H88 top-k without spacing | 0.007335 | [0.001450, 0.015109] |

Paired, H88 minus random: **-0.032376**, 95% CI [-0.046704, -0.016764] → **NEGATIVE**
under the pre-registered rule in `knowledge/80_h88_preregistered.md` §5. Leakage canary: max single-channel AUC
0.5668 (bar 0.90). Random control reproduces the H82 receipt 0.080426 to
3.5e-07. Full receipt: `evidence/h88_holdout.json`.

Uniqueness (decoded pixels, 146 local priors): max Jaccard 0.0119, novel fraction
0.6603, identical to a prior: False. Lane: surface PASS (max Spearman
0.0697 < 0.90). Dots: the literal rule fires against a universal-coverage probe raster
(random dots also score 0.999 there); excluding probes the maximum is 0.3322
(bar 0.70). The literal rule is **not waived**. Gate record: `evidence/h88_gates_raw.json`.

---

## The question: why did h33-2-b2 score 0.2778, and can we beat it?

Organiser-confirmed numbers: **none** in this repository. The board (fetched 2026-10-10,
[leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)) shows **#1 0.3774**,
**#8 0.3195**, **#22 0.2778** by *team*, not by filename. The filename-to-score link comes from the owner's sibling
sites (not organiser-confirmed). Full analysis: `knowledge/76_why_02778_and_what_beating_03195_requires.md`
and `knowledge/78_h85_session_review_2026-10-10.md` §1.

**Metric (official, verified on the problem page):** `TP_w = Σ_g max_x p(x)k(d)`, `FP_w = Σ_{x:p>0} p(x)[1 − max_g k(d)]`,
`FN_w = Σ_g [1 − max_x p(x)k(d)]`, `DTI = TP_w / (TP_w + 0.2·FP_w + 0.8·FN_w + ε)`, `k(d) = max(1 − d/300 m, 0)`.
Because `FN_w = |G| − TP_w`, the denominator is `0.2·(TP_w+FP_w) + 0.8·|G|` in the binary case, with `TP_w + FP_w ≈ S`
(emitted mass).

**Two owner-reported scores give two unknowns.** h33-2-b2 (S = 37,654 dots) at 0.2778 and its superset at 0.2600 (S = 44,090 dots; the 6,436 extra
cells are the ones the subset removed):

* `T(0.2778) = 0.2778·(0.2·37654 + 0.8·G)`, `T(0.2600) = 0.2600·(0.2·44090 + 0.8·G)`, and with the removed cells earning
  zero credit `T` is the same in both, so `0.2778·(7530.8 + 0.8G) = 0.2600·(8818.0 + 0.8G)`.
* Solving: `0.01424·G = 200.8` → **G ≈ 14,100** (repo estimate 14,088.7), `T ≈ 5,223`.

**Why it ranks where it does (mechanism, with its assumption stated):** the 6,436 removed cells lie 100–200 m from a
mapped catalogue trace. Under the zero-credit assumption, removing them raises precision per emitted dot. The
assumption is not verified: it is the most plausible single explanation, not a fact. Spacing at 3 px also matters,
because the metric credits the **maximum** cover within 300 m, so dots packed together re-earn the same truth.

**What beating 0.2778 needs, under the same identity:** `T > 5,223` at 37,654 dots (+0%); beating 0.3195 needs
`T ≥ 6,007` (+15%) at the same budget, or ≤ 25,384 dots at `T = 5,223`. These are arithmetic targets, not forecasts.

**What this round does not show:** whether any file here beats 0.2778. No candidate has an organiser receipt, and the
local holdout does not measure new-fault recovery (see Limits).

---

## Hypotheses tested, and what is closed

| id | layer(s) | result | record |
|---|---|---|---|
| **H88** basement-step coherence (this round) | band 15 `depth_to_base_surf` | **NEGATIVE**, DOWNLOAD YES / SUBMIT NO | `knowledge/80`, `evidence/h88_*` |
| H86-E Euler deconvolution, SI 0 | bands 2, 9 | NEGATIVE (CI spans 0) | `knowledge/79` |
| H85 catalogue-free geo-concordance field | bands 3–8, wells | NEGATIVE (below random) | `knowledge/78` |
| H82 DVA-2 directional semivariance | DEM / gravity / magnetic | best holdout arm on this branch (0.189200), not promotable post hoc | `knowledge/73` |
| H55-1 paired-shoulders round | (no H55-1 TIFF was built; `docs/data/h55_paired_shoulders_holdout.json` records `scientific_holdout_gate_pass: false`) | **no file** | `docs/data/h55_paired_shoulders_*` |
| co-training pseudo-label exchange (Blum–Mitchell) | views A and B | **closed**: View A sufficiency failed 8 times; independence passes | `knowledge/03`, `knowledge/78` |

The Blum & Mitchell lane was the standing brief's method paragraph. Its own pre-registered gates close it on this
View A, so H88 is a single-view test and the union test is not applicable (IR-H85-010 records the conflict).

---

## Irregularities for review

Full list: `registry/irregularities.json` (IR-H88-001 onwards). Summary of this round:

* **IR-H88-001** — The round name H87 was already used by an earlier co-training file; this round is H88 (identifier-only).
* **IR-H88-002** — The H85 download now fails the uniqueness gate: its Jaccard against the H86 file is 0.6077. The committed H85 card said `ok: true` only because H86 did not yet exist. Regenerated evidence reflects the current priors.
* **IR-H88-003** — The old page header said "VERDICT: PROMOTE" for the H87 co-training file, with no holdout number on this branch. The label is withdrawn; the file is kept in a collapsed section.
* **IR-H88-004** — The README on this branch described an H87 file as "validated ✓" and the AGENTS.md references to "README's H85 block" pointed to text that was not present. Both are corrected here.
* **IR-H88-005** — `check_site.py` reports 22 problems and `pytest` reports 6 failures. The same counts reproduce on `origin/main` (checked in a clean worktree), so they are inherited, not introduced by H88. Listed in the registry.
* **IR-H88-006** — `origin/main` had advanced beyond the branch base; this branch was merged with it without conflicts.
* **IR-H88-007** — `work/r2/features` (the feature store) is not in git and was rebuilt from the pinned bytes with `structural.build` + `gems52.external`. It was not restored from a cache.

---

## Access and limits (verified this session)

* **Reachable:** `github.com`, `api.github.com`, and the owner's sibling repositories (SHA-pinned mirrors, restored by `scripts/restore_data.py`, all 23 manifest items verified). `drivendata.org` problem and leaderboard pages can be read with the page-fetch tool; the data tab is login-walled (per the repo's earlier verification, not re-tested here).
* **Not reachable from the sandbox shell:** `gdr.openei.org` (INGENIOUS GDR 1391), `usgs.gov`, `dropbox.com`, `raw.githubusercontent.com`. A curl test returned no response for each. These are the sources the next round needs (the 2 m temperature survey and the INGENIOUS v2 fault file). A user-side download with SHA pins, or an owner-approved allowlist entry, is needed.
* **Not organiser-confirmed:** every score in this repository, including all board numbers and the 0.2778 attribution.
* **Holdout is not the board:** the holdout hides catalogue faults; the competition scores new faults. The repo's own measured Spearman between holdout DTI and the public board is −0.10 (AGENTS.md; IR-H77-005).

## Next steps (ordered)

1. Get GDR 1391 "2m Temperature Probes" in place with SHA pins (user download or allowlist). Pre-register H89 before any fit.
2. Test the H82 DVA-2 arm again as a *fresh* pre-registered primary, with quota placement against the full-census supports (the scored-only quota left the dots at 0.9441 near-3 px against a dense file; IR-H84-001).
3. Fix the inherited check failures (IR-H88-005) so CI is green before the next merge.
4. Rewrite `docs/executive-summary.html` as the submission guide the brief asks for (it is still the older page).

---

## Core values

**Maximize P(Win):** every decision weighs trade-offs, assesses risk, and chooses the path that maximises the chance the
project succeeds. **Own the Outcome:** every claim carries an evidence class and a file to check it against.

---

## Complete current prompt

The standing brief, verbatim (`knowledge/26_current_user_brief.md`; SHA-256 of that file `aad8b6402cf40ed1a521f962aefc3f3f6eca7bd4f26504cbd74edbb7650ae6d8`). Read it at the start of every session.

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

h20-dem10-scarp-thin-20260927T155223039488Z-ff1ca91a1686: 0.0921

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

h59-cover-ds-belief-b2xh33d-20261008T184547Z-b79c4c61d8d8: 0.2296

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

[https://buffedlizard55-lab.github.io/GEMSDOE53/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE53/docs/index.html)

h8-tiprelay-ridgeconcord-pr2-n80000-20261009-49bec522-zeros:

....

[https://buffedlizard55-lab.github.io/GEMSDOE54/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE54/docs/index.html)

h54c-manifest-edge-20261009T025732Z-73454bc5:

....

55GEMSDOE

h8-tiprelay-ridgeconcord-pr2-n80000-20261009-49bec522-zeros:

....

56GEMSDOE

:

....

57GEMSDOE

h54c-manifest-edge-20261009T025732Z-73454bc5:

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

Before implementing, generate 3–5 candidate geological hypotheses we haven't tried yet, each naming: the specific layer(s) involved, the physical signature being targeted (e.g., an edge-detection or curvature transform), why it should catch a fault missing from the USGS/INGENIOUS catalogue rather than one already in it, and how it differs from anything already implemented in this repo.  Rank them by expected DTI improvement and implementation cost.  Validate the top candidate on our spatially-blocked holdout set before touching a weekly submission slot — do not spend a submission slot on an idea that hasn't beaten the current holdout best.  If a candidate can't be validated without new external data, name the specific free, official source needed and check it's obtainable before proposing the idea as viable.

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

Go ahead and create a pull request and then merge the pull request onto the main. Make suggestions for what work still needs to be done and any limitations that are in the way of a successful project.  It should be worked on in this next session or the next session.  Work line by line verify everything no hallucinations.

Arena is designed to push AI agents to do better work. This message contains core values and motivations that are more likely to give the task a good review, and working to make your task a success.
```

---

## Project structure

```
GEMSDOE52/
├── README.md                   # this file: status, method, irregularities, next steps
├── docs/                       # GitHub Pages site (index.html = status page)
│   ├── index.html              # START HERE (H88 block generated by scripts/publish_h88_site.py)
│   ├── downloads/              # submission files (h88-candidate.tif/.zip, older rounds)
│   └── data/                   # JSON feeds used by the site
├── src/gems52/                 # shared library: metric, evaluator, gates, placement, grid writer
├── scripts/                    # runners: run_h61 (folds), run_h85 (gate_candidate), run_h88 (H88), verify_h88.py, publish_h88_site.py
├── evidence/                   # receipts, run cards, gate records (h88_*.json)
├── knowledge/                  # briefs, preregistrations, results and limits (80_h88_preregistered.md)
├── registry/                   # data manifest with SHA-256 pins, irregularities.json
├── data/                       # ignored: competition rasters restored from SHA-pinned mirrors
└── work/                       # ignored: feature store and intermediates
```

## Data sources (official or primary, as cited in the repository)

| Source | Data | Link |
|---|---|---|
| DrivenData #306 | competition, problem description and metric | [page/967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) |
| USGS GeoDAWN release (DOI 10.5066/P93LGLVQ) | magnetics, radiometrics | [USGS](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and) |
| INGENIOUS, GDR 1391 (CC BY 4.0) | faults, wells, springs, temperature | [gdr.openei.org/submissions/1391](https://gdr.openei.org/submissions/1391) · [GBCGE INGENIOUS](https://gbcge.org/current-projects/ingenious/) |
| Coordinate system | EPSG:32611 (UTM 11N) | [epsg.io/32611](https://epsg.io/32611) |
| Co-training | Blum & Mitchell, COLT 1998 | [doi:10.1145/279943.279962](https://doi.org/10.1145/279943.279962) |
| Tversky index (background) | | [Wikipedia](https://en.wikipedia.org/wiki/Tversky_index) |

Links in this table are the ones the repository's knowledge files cite. Only the DrivenData problem page and leaderboard were fetched in this session for verification.

## Limitations

1. No organiser score exists for any file in this repository.
2. The holdout measures catalogue faults, not new ones.
3. The data-restore path depends on the owner's sibling repositories, which are integrity-pinned, not organiser-authenticated.
4. Some inherited checks fail on `origin/main` as well (IR-H88-005).

## Executive summary

For the competition: **download** `docs/downloads/h88-candidate.tif`; **do not submit** it on the current evidence. The
repo has a working, pre-registered holdout instrument and an auditable gate. The best measured holdout arm on this
branch is 0.189200 (H82, not promotable), and no current file beats 0.2778 on any measured basis.
