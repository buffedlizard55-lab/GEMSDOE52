# GEMSDOE52 — DOE GEMS Prize: H88 prevalence-calibrated co-training

**Competition:** [DOE GEMS Prize — DrivenData #306](https://www.drivendata.org/competitions/306/competition-doe-gems/)
· **Round:** H88, built 2026-10-10 · **Branch:** `arena/04b2bb40-gemsdoe52`
· **Site:** [`docs/index.html`](docs/index.html) · **How to submit:** [`docs/h88-executive-summary.html`](docs/h88-executive-summary.html)

## ⬇️ Download the files (and whether you may submit them)

| file | what | OK to download? | OK to submit? |
|---|---|---|---|
| [`docs/downloads/gems52-h88-cotrain-strat-pmcal-27000px-20261010T222229Z.tif`](docs/downloads/gems52-h88-cotrain-strat-pmcal-27000px-20261010T222229Z.tif) (27,000 dots, 119,127 B) | this round's candidate | **YES** | **NO** — loses to `single_B` on both hide instruments and 97.9 % of its dots sit within 3 px of the published `h83-candidate.tif` placement (brief's lane rule: log duplicate and stop) |
| [`docs/downloads/gems52-h87-cotrain-wavelength-thk-37654px-20261010T213656Z.tif`](docs/downloads/gems52-h87-cotrain-wavelength-thk-37654px-20261010T213656Z.tif) (37,654 dots, 128,024 B) | previous round's artefact, measured this round | **YES** | **NO** — its field loses to its own random control on the mandate instrument (paired vs random -0.017952 [-0.030631, +0.001185]) and its field DTI 0.063641 stays below the best measured arm (0.192829). The shipped raster's own file-protocol number (0.006474) is **not** a rejection: the owner-reported 0.2778 champion scores 0.006570 on that same protocol (IR-H88-007) |

Nothing built this round clears the repository's bar — the best measured holdout arm remains
**B_DVA2 0.192829** (single_B 0.174571, random 0.080426)
on `gems52-pooled-hide-v1` at 9,400 dots/fold. Under the standing rule ("do not spend a weekly submission
slot on an idea that has not beaten the current comparable holdout best") the recommendation is **not to
submit this week**. Both files stay downloadable as research records; the slot decision is the owner's.

## Why `h33-h33-2-b2-…-zeros` scored 0.2778, and what beating it takes

Measured from the restored bytes (`data/reference/h33-2-b2-zeros.tif`): values exactly {0, 1},
**37,654 cells**, minimum distance to `labels.tif` **223.6 m** (its ≤200 m catalogue ring was deleted),
median distance to the catalogue 1,965 m, `M = Σ p·k(d)` over the catalogue 277.9. It is the `d2-8`
surface field with the ring removed — **no detector change** — and the lineage `d1-5` (60,069 px, 0.2477) →
`d2-8` (44,090 px, 0.2600) → `h33-2-b2` (37,654 px, 0.2778) earned **+0.030 DTI by shipping fewer,
better-placed dots**. Across the 13 restore-able scored rasters Spearman(emitted mass, owner-reported
score) = **−0.94**. The metric explains it: with `T = TPw` and `FNw ≡ |G| − T`,

```
DTI = T / ( 0.2·(T + S − M) + 0.8·|G| )
```

mass that is not within 300 m of a hidden fault pays 0.2 per unit and earns nothing. Beating 0.3195 at the
same mass needs **+15.0 % credit density**; equivalently the champion's own credit delivered in **≈27,000
cells instead of 37,654** (champion-lineage elasticity −0.42). Full derivation:
[`knowledge/80_why_02778_verified_and_the_mass_lever.md`](knowledge/80_why_02778_verified_and_the_mass_lever.md).

## H88 in one screen

* **New instrument (this round's real contribution).** Every prior instrument in this repository scored a
  truth set ≈4× denser than the organiser-implied hidden prevalence (0.112–0.294 % of the footprint), which
  over-rewards recall — the instrument's DTI rises with mass while the board's score falls. H88 thins the
  truth to that bracket **keeping whole 8-connected fault components** and calibrates the emission budget on
  the result (`gems52-pm-hide-v1`, `gems52-pm-offcatalogue-v1`). Frozen rule: maximise the average rank of the candidate's pooled DTI over the two prevalence-matched instruments; ties broken toward the smaller budget.
* **Result on the candidate.** Prevalence-matched hide: 0.094615 vs single_B
  0.104672 and random 0.049857; champion density:
  0.156119 vs 0.174571 /
  0.081592; off-catalogue (diagnostic): 0.048797
  vs random 0.048188. The candidate **beats random but loses to the single-view
  surface control on every instrument** — verdict `negative`.
* **The reserved A-only stratum (the brief's discovery share, 15.0 % of dots) is measurably
  anti-informative**: A-only 0.019699 vs random 0.049857 on the
  prevalence-matched instrument. It is kept as a labelled reservation with a written geological reasoning
  row per dot, never as a claimed gain.
* **The conflict is a finding.** On a prevalence-matched instrument the surface view still dominates and
  larger budgets still score higher, so the board's mass preference is *not* reproduced inside the
  instrument; the shipped mass therefore follows the board-derived target of `knowledge/80` inside the
  frozen guard band (27,000 cells after the 200 m collar and 3 px spacing).
* **H87 measured for the first time (IR-H88-003 closed).** Its disagreement field scores
  0.063641 vs random 0.081592 on the mandate instrument (paired
  -0.017952); the shipped raster scores 0.006474
  on the file protocol. Its lane is clean against informative priors (max near-3px
  0.4226, bar 0.70; 1 universal-coverage probe
  separated out), and the two views are independent (correlation −0.150136). The build receipt's
  `promote` verdict — issued on format and uniqueness alone — is superseded by these measurements.
* **The instrument boundary, measured (IR-H88-007).** Scored verbatim on the same file protocol, the
  owner-reported **0.2778 champion raster scores 0.006570** (T=323.4 of |G|=53,186),
  statistically identical to this round's fresh 37,654-dot catalogue-flank emission
  (0.006474) and *below* the H88 raster
  (0.015268). All three sit in one spatial family (3.000 px minimum
  dot spacing; median distance to the known catalogue 19.6 / 21.2 / 17.9 px). **File-level DTIs near 0.006
  therefore carry no evidence against a catalogue-flank file**, and no page may compare them with the
  arm-protocol bars (`evidence/h88_champion_file_protocol.json`).
* **Leakage canary:** max single-channel AUC 0.7480 (bar 0.9),
  no alarm. **Lane (corrected, IR-H88-005):** the H88 candidate's dots are 97.9 % within 3 px of the
  published H83 e3 placement (`docs/downloads/h83-candidate.tif`) — policy DUPLICATE/STOP, bar 0.70; the
  literal reading's 1.0 comes from the registry's usual universal-coverage probe
  (`13gems_20261001_r13-lattice-s5_v2_nan-outside.tif`, coverage 1.0 of the footprint), which the corrected
  lane separates out.
* **Every number is labelled by instrument.** `HOLDOUT-DTI` = `gems52-pooled-hide-v1` with the withheld
  positive count in the receipt; `OFFCAT-DTI` = prevalence-matched off-catalogue proxy (diagnostic only);
  no number here is a leaderboard forecast — the instrument and the public board rank differently
  (Spearman −0.10; `knowledge/10`). All board scores attributed to files in this project are
  OWNER-REPORTED; nothing is ORGANIZER-CONFIRMED.

## Candidate hypotheses, ranked (3–5) — see [`knowledge/81`](knowledge/81_h88_hypotheses_ranked.md)

1. **H88-A — prevalence-matched budget calibration + disagreement-stratified emission.** Built and
   measured this round; verdict **negative** (above). It is the prerequisite for judging any detector,
   because it removes the instrument's 4× prevalence gap.
2. **H88-B — de-trended K/Th alteration residual** (GeoDAWN radiometrics; hydrothermal K-enrichment
   relative to a 5 km local trend). Untested; low cost.
3. **H88-C — seismicity lineation** (bands 10/16, directional gradient of the 100 km-kernel density).
   Untested standalone.
4. **H88-D — theta map on the RTP magnetic field** (normalised horizontal-derivative-of-tilt). Untested;
   expected small because the information overlaps tilt.
5. **H88-E — Euler deconvolution, SI 1, on the upward-continued TMI.** Untested variant; the SI-0 family
   already measured at random (H86).

**H88-F (external data) is not viable in this sandbox**: the egress allowlist here is `github.com`,
`codeload.github.com`, `api.github.com`, `registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org`, so the
named free sources — INGENIOUS GDR 1391 “2m Temperature Probes”
([gdr.openei.org/submissions/1391](https://gdr.openei.org/submissions/1391), DOI 10.15121/1881483) and
NASA/USGS ASTER L1T scenes — cannot be fetched. A user-side download with SHA-256 pins (or an allowlist
entry) is the prerequisite.

## Irregularities filed / closed this session (`registry/irregularities.json`)

* **IR-H88-004** — the base commit shipped three red pinned tests (the H55 README sentence, the two CTD5
  page labels, and the missing brief fence). Fixed here; `pytest -q` now 498 passed / 5 skipped.
* **IR-H88-005** — the H88 lane reading had been computed on the wrong eligible mask (every finite grid
  pixel instead of the feature store's valid footprint) and a publish alias was being compared with its
  own bytes. `gates.lane_report` now separates same-bytes priors (`self_matches`) from both verdicts, and
  the corrected reading is published in `evidence/h88_lane_full_registry.json`.
* **IR-H88-006** — H87's build-stage `promote` had no held-out measurement; the measurement is negative
  (field 0.063641 vs random 0.081592; paired vs random
  -0.017952).
* **IR-H88-007** — the file protocol scores the owner-reported 0.2778 champion raster at
  0.006570, so file-level DTIs near 0.006 cannot reject a catalogue-flank file.
  Measured in `scripts/measure_champion_file_protocol.py`; `evidence/h88_champion_file_protocol.json`.

## Repository map

| path | what it is |
|---|---|
| `docs/` | GitHub Pages site; `docs/downloads/` holds the ready-to-download GeoTIFFs |
| `docs/h88-executive-summary.html` | exactly how to submit, including the `Predicted values must be in range [0, 1]` failure mode |
| `src/gems52/` | metric, gates, placement, holdout evaluator, writers, feature store |
| `scripts/run_h88.py` | this round's runner (`pm`, `holdout`, `build`, `card`) |
| `scripts/eval_h87_holdout.py` | the H87 measurement (IR-H88-003) |
| `evidence/` | every receipt behind every number (`h88_*.json`, `h87_holdout.json`) |
| `registry/` | data manifest with SHA-256 pins, irregularities, leaderboard snapshots |
| `knowledge/` | the analysis and hypothesis record; `knowledge/26` holds the standing brief |

## Historical pins preserved in this README

* The failed H55-1 paired-shoulders round never shipped a raster: **no h55-1 tiff was built** (its own
  slot gate refused promotion, `evidence/h55_paired_shoulders_holdout.json`). This sentence is pinned by
  `tests/test_h55_paired_shoulders_decision_gate.py`; it was missing from the README at the base commit and
  is recorded as IR-H88-004.
* The CTD5 release stands as a negative: `docs/index.html`, `docs/executive-summary.html` and
  `docs/ctd5-audit.html` all carry the literal **DO NOT SUBMIT** label, pinned by `tests/test_ctd5.py`
  (`docs/index.html` additionally carries `HOLDOUT-DTI` for the same pin).

## Provenance and honesty rules

The DrivenData data tab is login-walled here, so the competition rasters are restored from the owner's
SHA-256-pinned mirrors through the GitHub API (`scripts/restore_data.py`, `ALL_VERIFIED=True`, 23 files).
**The pins prove mirror consistency, not organiser authentication.** Every score attributed to a filename
is OWNER-REPORTED. No page in this repository claims a certified leaderboard gain, and the submission
decision stays with the owner.

## Remaining work and limitations

* **No scored receipt.** Nothing in this repository has an ORGANIZER-CONFIRMED score; the mass lever is
  measured only on the 13 restore-able owner-reported rasters.
* **The instrument does not rank the board** (Spearman −0.10), so "beat the holdout best" is a conservative
  screen, not a forecast of board points.
* **H88-B…E are untested**; the protocol's three-experiment cap stopped the round after H88-A.
* **External ASTER / 2 m-temperature data are blocked** by this sandbox's egress allowlist (named sources
  above).
* **The A-only stratum is a cost**, not a gain; a future round should either find a detector where A-only
  is informative or report the reservation as a price paid for the brief's discovery mandate.
* **No shipped raster can be validated by the local instruments.** The champion's own file scores
  0.006570 on the file protocol and the arm protocol is not the board; the only
  board-derived evidence in this repository is the owner-reported mass/score relation (Spearman −0.94 over
  13 rasters). A future round should either reproduce the board's fold structure or state plainly that its
  bar is an internal screen.
* **The catalogue-adjacent mass lever is still the strongest board evidence** and is untouched by this
  round: the champion's 37,654 dots sit at median 19.6 px from the known catalogue, and H88's/H87's copies
  of that geometry (21.2 / 17.9 px) score zero-to-weakly-positive on the local instruments while the
  owner-reported board places the same geometry at 0.2778.

---

## Complete current prompt (the standing brief, preserved verbatim)

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
