# Current user brief, verbatim (recorded 2026-10-10; this is the standing starting point)

> Provenance: typed by the owner into the Arena session that produced round **H83**. Recorded
> here so every later session reads the same text. It is additive to
> `knowledge/00_brief_as_received.md` (the 2026-10-06 brief) and to the later briefs in
> `knowledge/08`, `22`, `26`, `36`, `56`, `64b`; where they differ, the newest text wins for
> *process* and the oldest text never expires for *method*.

---

## THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED!

MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION.  DO NOT COPY A PREVIOUS SUBMISSION
UNLESS IT'S FOR LEARNING AND EDUCATION.  BUT WE MUST GENERATE A UNIQUE TIF SUBMISSION.  IT MUST
BE OBVIOUS WHETHER IT IS OK TO DOWNLOAD AND SUBMIT THE GENERATED TIF SUBMISSION.

There should be an easy to download submission tif file as described by the prompt.  Read the
entire prompt.

## The method lane (co-training, Blum & Mitchell COLT '98 pp. 92–100, doi:10.1145/279943.279962)

Co-training between a geophysical view and a surface view, with disagreement as the discovery
signal. Blum and Mitchell show that when each example has two views, each sufficient and
approximately conditionally independent given the class, two learners trained on separate views
can use each other's confident predictions on unlabeled data. View A is potential-field and
subsurface (gravity, magnetics, strain, seismicity). View B is surface (DEM-derived curvature
and slope, plus any radiometric bands present in training_features.tif). Test the independence
assumption empirically: correlate each view's spatial-block out-of-fold errors on labeled
negatives, and abandon the method if they are strongly correlated. Pseudo-label only where one
view is confident and the other abstains, using whole-segment spatial blocks and a buffer so no
leakage reaches the evaluation. The discovery signal is disagreement. Where A is confident and B
is not, the fault may be buried beneath cover. Where B is confident and A is not, suspect surface
artifacts such as roads or erosion lines. Because Phase 2 reviewers verify faults, write the
geological reasoning for every A-only candidate. Co-training can also amplify bias, so compare
against a single-view baseline on hide-and-recover segments. Normalize to [0,1], write the
GeoTIFF, apply the repo's metric-aware placement, run the uniqueness gate, and confirm the output
isn't merely the union of the two views.

## PARALLEL-RUN PROTOCOL

1. **LANE.** Your lane is the single method paragraph above. Stay inside it. If your raster's
   rank-correlation with any registry raster exceeds 0.90, or more than 70 % of your dots fall
   within 3 px of one registry raster's dots, you have drifted into another lane: log it as a
   duplicate and stop. Check this on the surface before placement AND on the final dots.
2. **REUSE, DON'T REBUILD.** Use the template's cached feature stack, `evaluate_holdout.py` and
   `submission_writer.py`. Holdout = hide-and-recover: withhold whole fault segments with a
   buffer, derive every catalogue-based feature only from the visible faults, mask visible faults
   pixel-exactly, score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel). If a shared
   tool is wrong, fix it once in the template and report it; never keep a private fork.
3. **LABEL EVERY NUMBER** as HOLDOUT-DTI (evaluator version, number of withheld positives, 95 %
   CI) or ORGANIZER-CONFIRMED (copied from a submission-page receipt). A projection is never
   written as a score.
4. **LEAKAGE CANARY.** Test each feature alone on the holdout before trusting any result. AUC
   above 0.90 means leakage until proven otherwise.
5. **RUN CARD.** End with one JSON card: hypothesis; mechanism; the named non-fault process that
   could mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator
   output (no NaN inside the footprint, values in [0,1], CRS/shape/transform match); submission
   name + note of at most 140 characters; verdict promote / negative. Negative results are
   deliverables.
6. **BUDGET.** Stop after 3 experiments or 2 hours. Do not pick submissions: promotion to a real
   slot is a separate selector step, within the weekly cap shown on the submission page.

## Targets and the question to answer

* Champion to beat: `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` **0.2778**
  (https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html).
* Current competition leaderboard high score stated by the owner: **0.3774**
  (https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html), with **0.3195** named as the
  bar to design against in the newest instruction.
* Question: *why and how did that file get the highest score, and can we generate a submission
  that scores higher?*

### Owner-reported scores across the GEMSDOE sites (verbatim list, as supplied)

| Site | Submission | Score |
|---|---|---|
| GEMSDOE | gems-submission-20260925T001403Z-7f00890a | 0.1563 |
| 6GEMSDOE | gems6_hgb88-topk03_33cec71ff0 | 0.0286 |
| GEMSDOE3 | pindrop-v4-nodes-20260925T152420Z-f347b70daa | 0.1193 |
| GEMSDOE3 | pindrop-v4-discovery-20260925T152423Z-37f9d5b855 | 0.0830 |
| GEMSDOE3 | pindrop-v4-ridge-20260925T152422Z-4e03fc9705 | 0.1152 |
| GEMSDOE2 | gemsdoe2-dual-family-union-20260925T160406Z-f68e590f | 0.1560 |
| GEMSDOE4 | gems-submission-20260926T163915Z-237f0063 | 0.0343 |
| 5GEMSDOE | gems-submission-20260926T175114Z-7f00890a | 0.1563 |
| 7GEMSDOE | lidarscarp-ridge-top2pct-36c3a3f341c8 | 0.1461 |
| 8GEMSDOE | Hedge-v2_submission | 0.1563 |
| GEMSDOE9 | 2314b599 | 0.0107 |
| 11GEMSDOE | gems-structural-area06-v1 | 0.0202 |
| 12GEMSDOE | r7-nms3-dem10-scarp_0c9199f14e62 | 0.1294 |
| 12GEMSDOE | r7-nms3-dem10-scarp_0c9199f14e62_allfinite | 0.1294 |
| 15GEMSDOE | gems-tso1-20260929T005627Z-conj_alteration_mag | 0.0782 |
| 14GEMSDOE | GEMS_r5-geom-horse-ensemble_20260929T154852Z_ccbe1de0_site_e96e942f | 0.0020 |
| 17GEMSDOE | 17GEMSDOE_F-ensemble-2pct_20260930T050626Z | 0.0187 |
| 18GEMSDOE | H19-C_20260930T212401Z_c11e495e | 0.0297 |
| 19GEMSDOE | h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan | 0.1894 |
| 19GEMSDOE | h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan | 0.1922 |
| GEMSDOE10 | h16-continuation-20260927T065521077735Z-3431b83c7c | 0.0461 |
| GEMSDOE10 | h20-dem10-scarp-thin-20260927T155223039488Z-ffc91a1686 | 0.0921 |
| GEMSDOE10 | H25-ctx-ridge-20260927T232947704150Z-6452ae1d00 | 0.1280 |
| GEMSDOE10 | h28-dotted-ridge-20260928T020256236880Z-6452ae1d00 | 0.1839 |
| 13GEMSDOE | 20261001_r13-lattice-s5_v2_nan-outside | 0.0904 |
| 16GEMSDOE | h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan | 0.1855 |
| 16GEMSDOE | h18-3a-topo-geophys-x-complexity-prior-20260930-c502dfab-nan | 0.0976 |
| 16GEMSDOE | h18-4-usgs-geologic-map-faults-gap-20260930-aef8f42c-nan | 0.0360 |
| GEMSDOE21 | h19-4-reference-20260930-691e4dfa | 0.1894 |
| 20GEMSDOE | h20-1-sarnnpu-powerlaw-pi0363-tilt-wingcrack-20260930-be0e8f6b-nan | 0.1890 |
| 20GEMSDOE | h20-5-continuous-pu-proxy-unverified-20260930-824ce73a-nan | 0.1859 |
| GEMSDOE22 | h23-a-dti-optimal-emission-6pct-20261002-e2ec4b49-nan | 0.1002 |
| GEMSDOE22 | h23-b-dti-optimal-emission-10pct-20261002-86176698-nan | 0.0748 |
| GEMSDOE23 | h30-arrangement-matched-habitat-20261002-0d4e02e8-nan | 0.1352 |
| GEMSDOE24 | h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan | 0.2477 |
| GEMSDOE25 | dotted-h19-5-d2-8-20261002-e56ea318af89-nan | 0.2600 |
| GEMSDOE26 | dilcond-oof-v1-20261003-47629f496133-nan | 0.1223 |
| GEMSDOE27 | topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan | 0.2449 |
| GEMSDOE30 | d28-poisson300m-offcat-44090-20261003T233156Z-91eae1ca | 0.2600 |
| GEMSDOE31 | h27-4-solo-d28-20261004-8acb75e1-nan | 0.2708 |
| GEMSDOE33 | h33d-analog-tip-stepover-r30-20261004-cb490425926e | 0.2632 |
| GEMSDOE34 | h34-scatter-q50-arr-matched-20261004T223317Z | 0.0778 |
| GEMSDOE35 | h35-06-aaa86efb25-20261004T225420098147Z-candidate | 0.0418 |
| GEMSDOE36 | anderson-geothermal-pinn-38854-20261004T230000Z-9b9ea4e6-zeros | 0.2750 |
| GEMSDOE37 | h6-physics-dotted-80k-20261005T055000Z-0bef9211631c | 0.1193 |
| GEMSDOE38 | D-step-3p0-07pct-tipProt-20261005-ecfbf59e2b48-zero | 0.0763 |
| GEMSDOE42 | xscale-worm-persistence-20261006T000541Z-nan | 0.0581 |
| GEMSDOE43 | sup01-hgb21-sep40-n40000-20261006-bc2e4e9a8d6f-nan | 0.0424 |
| GEMSDOE45 | h51-km-faultzone-20261006-zeros | 0.0106 |
| GEMSDOE49 | gate_ortho_w0.25-40k-20261006T213721Z-nan | 0.2376 |
| GEMSDOE32 | **h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros** | **0.2778** |
| GEMSDOE28 | h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-nan | 0.2708 |
| GEMSDOE28 | h32-1-prethin-tip-euler-d2-8-20261003-31e35eee884e-nan | 0.2649 |
| GEMSDOE28 | h36-1-rung30-blind-r1-20261003-b531dae0a36f-nan | 0.2710 |
| GEMSDOE28 | h38-1-hf-euler-r30-r1-20261003-56a9f473edc7-nan | 0.2707 |
| GEMSDOE29 | efd28-repro-20261003-1cc7dc534d51-nan | 0.2600 |
| GEMSDOE29 | repo-c0-habitat-emission-20261003-a4d439b07426-nan | 0.0041 |
| GEMSDOE29 | sgmc-off-catalogue-44k-20261003-c8dcd780e3fd-nan | 0.0512 |
| GEMSDOE29 | wormrank-d28-20261003-59dcaf6dd11d-zeros | 0.2560 |
| GEMSDOE29 | wormsurv-filter-20261003-921f10960d6e-zeros | 0.0532 |
| GEMSDOE29 | xfit-c0-habitat-20261003-ca879db0089a-zeros | 0.0439 |
| GEMSDOE46 | r11f-scarp-radiometric-fusion-00e049b51218-zeros | 0.1589 |
| GEMSDOE46 | r12-scarp-rad-concordance-23e807e2de9f-zeros | 0.0843 |
| GEMSDOE39 | h40-e-disc-h40e-30k-zeros | 0.0339 |
| GEMSDOE40 | h8-euler-lineament-depthcluster-20261006-785c4f5d5ce1 | 0.0355 |
| GEMSDOE40 | h8-euler-lineament-depthcluster-20261006-785c4f5d5ce1-hard | 0.0397 |
| GEMSDOE41 | h42-submission-primary | 0.0245 |
| GEMSDOE44 | h46-twostageAB_20261006T160000Z_b0cfe956-zeros | 0.0715 |
| GEMSDOE47 | h60-lidarscarp-s2p0-20261007-nanoutside | 0.0430 |
| GEMSDOE48 | h59-cover-ds-belief-b2xh33d-20261008T184547Z-b79c4c61d8d8 | 0.2296 |
| GEMSDOE50 | h59-sharpened-scarp-scatter-90k-20261007T171954Z-allfinite | 0.0764 |
| GEMSDOE51 | h53-twostage-20261008T040951Z-9a0b32c871 | 0.1047 |
| GEMSDOE53 | h8-tiprelay-ridgeconcord-pr2-n80000-20261009-49bec522-zeros | 0.0159 |

(Empty-score rows in the owner's list — GEMSDOE52, GEMSDOE29 `xfit-h41-union-qfaults`,
GEMSDOE40 `h45-...-zeros`, GEMSDOE54, 55GEMSDOE, 56GEMSDOE, 57GEMSDOE — were supplied without a
number and are not claimed here.)

## Submission mechanics the owner needs to work, every time

* The DrivenData *New submission* form accepts a single-band GeoTIFF, or a ZIP containing
  **one** GeoTIFF, matching the submission format's CRS, shape and geotransform.
  Competition: https://www.drivendata.org/competitions/306/competition-doe-gems/
  · rules/submission page: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
  · data: https://www.drivendata.org/competitions/306/competition-doe-gems/data/
* Known portal rejection seen by the owner: **"Predicted values must be in range [0, 1]"**.
* Each submission needs a **unique name** and a **short note** (≤ 140 characters).
* There must be an **executive-summary subpage** that explains exactly how to make a submission,
  and the download must be obvious on first visit.

## Standing project values (owner, from the Arena team)

* **Maximize P(Win)** — weigh tradeoffs, assess risk, choose the path that maximises the
  probability of winning; set aside emotion; put the outcome first.
* **Own the Outcome** — own results end to end, not just one slice; act without waiting for
  permission; treat failure and success as signals.
* **Verification discipline** — work line by line, verify from official/trusted sources, provide
  links for manual review, flag irregularities, **no hallucinations**.
* Build it so it does not require manual checking every time, and keep an up-to-date current
  feed.
