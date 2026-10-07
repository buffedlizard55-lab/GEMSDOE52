# GEMSDOE52

Target: a **unique, downloadable single-band GeoTIFF** for [DrivenData competition 306 — DOE GEMS
Prize](https://www.drivendata.org/competitions/306/competition-doe-gems/), built to beat this group's
best of 0.2778, with the reasoning and the evidence published next to the file.

## The file — download it, submit it, nothing to configure

| | |
|---|---|
| **download** | [`docs/downloads/gems52-h53-btherm-greedy-37654px-20261007T0150Z-zeros.tif`](docs/downloads/gems52-h53-btherm-greedy-37654px-20261007T0150Z-zeros.tif) — click, save, upload |
| zip (if the portal prefers it) | [`submission/gems52-h53-btherm-greedy-37654px-20261007T0150Z-zeros.zip`](submission/gems52-h53-btherm-greedy-37654px-20261007T0150Z-zeros.zip) |
| also in the repo | [`submission/gems52-h53-btherm-greedy-37654px-20261007T0150Z-zeros.tif`](submission/gems52-h53-btherm-greedy-37654px-20261007T0150Z-zeros.tif) |
| **portal submission name** | `GEMSDOE52-H53 RadCorrTC-ViewB-CoverageGreedy-37654px` |
| **portal note (optional comment box)** | see `submission_note` in [`evidence/h53_submission_20261007T0150Z.json`](evidence/h53_submission_20261007T0150Z.json) — also quoted in [docs/executive-summary.html](docs/executive-summary.html) |
| bytes / shape | 147,617 · width 3292 × height 3730 (rows 3730, cols 3292) · single band · `float32` · EPSG:32611 · 100 m cells |
| values | [0.0, 1.0] only — **37,654 positive px**, 0 outside the valid footprint, **0 NaN**, 0 on a catalogue pixel |
| sha256 | `a0f3ed4b4524ca67a0c715beca5a905eced165ee9e59be5e5831a39b7526254d` |
| format gate | `True`, problems `[]` — `src/gems52/gates.py`, run on the written bytes, not on intent |
| uniqueness gate | `True` — **strictly-novel-and-selective**: 24,254 px (64.4%) touch none of the 18 priors scanned, and 1,048,807 prior px are deliberately **not** re-emitted, so it is not "the union" either |
| placement efficiency | `A/S` = **8.8151** = 93.97% of the 9.380298 kernel-disc ceiling, against **8.044** (85.8%) for the file that scored 0.2778. Every emitted pixel is 8-isolated (`max_component = 1`) |
| selection | evidence/h53_sweep.json — the pre-registered rule (beat matched-budget random on **both** instruments in ≥3/4 folds, then maximise `mean_tip + mean_hide`, then prefer smaller mass) chose `B_therm|greedy|37654`. Rebuilding reproduces the identical sha256 |
| **holdout verdict** | **cleared on both instruments, 4/4 folds each**: `hide` **0.09701** vs random 0.03948 (+146 %), `tip` **0.0547** vs random 0.02477 (+121 %). The H52 shipped arm scored 0.0518 / 0.0291 → **+87.5 % on the sum** |
| projection | placement gain only (the 0.2778 file's own ρ_A = 0.01287 applied to this file's measured coverage, nothing else changed): **DTI ≈ 0.3044**. Not a forecast — see §4 for what is and is not claimed |
| Phase-2 artefact | [`evidence/h53_reasoning_20261007T0150Z.json`](evidence/h53_reasoning_20261007T0150Z.json) — 510 A-confident/B-abstaining neighbourhoods at 300 m grouping, each with lat/lon, strike, elongation, extent, nine measured layer ranks, the nearest well or spring that carries a temperature, with its source DOI, and an interpretation assembled **only** from numbers in the same record. 405 carry positive support, 43 are linear over ≥1 km, 98 are corroborated by a ≥60 °C well or spring within 5 km |
| exact steps | [docs/executive-summary.html](docs/executive-summary.html) |
| rebuild it | `python3 scripts/run_h53.py --stage build --arm auto --dti 0 --ng 8129 --budget 37654 --tag 20261007T0150Z` |

The site is the product: [docs/index.html](docs/index.html) renders every number from
`docs/data/*.json`, which `scripts/refresh_feed.py` regenerates and a committed GitHub Actions workflow
refreshes on a schedule, so **nothing on the page needs hand-checking**.

**Core values this repo is run by — _Maximize P(Win)_, _Own the Outcome_.** Maximize P(Win): every
decision is taken on the number the organiser scores, at the prevalence their published scores imply, and no
weekly slot goes to an idea that has not beaten the current holdout best. Own the Outcome: the file, its
hash, its gates, its provenance, its negative results and its irregularities are all in this repo — including
the two bugs this session's own tests caught in code this session wrote (§5, IR-52-020 / IR-52-021 /
IR-52-025), and the mechanism from the brief that failed its own test a second time (§4).

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

### 1.1 The directives, itemised (the standing starting point, restated in order)

1. **Co-train** two views of the same unlabelled pixels — View A the geophysical potential fields, View B
   the surface/geomorphic layers — and treat **disagreement, not agreement, as the discovery signal**
   (Blum & Mitchell, COLT '98, doi:10.1145/279943.279962).
2. **Test the premise instead of assuming it**: conditional independence of the two views' errors given the
   label, measured on spatially-blocked out-of-fold errors; abandon the arm if the test says so.
3. **Pseudo-label only** where one view is confident and the other abstains.
4. **Hold out whole segments**, with a buffer, never random pixels.
5. **Write the reasoning for every candidate**: A-only ⇒ a fault buried under cover; B-only ⇒ suspect
   (roads, erosion, levees).
6. **Benchmark against a single-view baseline** on hide-and-recover.
7. **Normalise to [0, 1]** and write a **GeoTIFF**; place mass **metric-aware** (the kernel, the mask, the
   acceptance bar), not by percentile.
8. **Pass a uniqueness gate** and be **more than the union** of previous submissions — never copy a prior
   answer; this exercise is for learning.
9. **Propose 3–5 new geological hypotheses** with layers, physical signature, why they find
   catalogue-missing faults, diff against repo history, ranked by expected DTI gain over cost; validate the
   top one on a spatially-blocked holdout before spending a slot. New external data must be **free,
   official, and confirmed obtainable**.
10. **The site**: clean GitHub Pages, one-click `.tif` at the very top, an executive-summary subpage with
    the exact submission steps, the `[0, 1]` error explained and made impossible, a unique submission name
    with a short note, a live data feed so nothing needs manual checking, official links for manual review,
    irregularities flagged, three verification passes, then a PR and a merge to `main`.

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
scripts/        prepare_data.py restore_data.py screen_layers.py run_pipeline.py
                validate_holdout.py build_submission.py refresh_feed.py research.sh
tests/          test_metric.py  (8 tests, including the marginal acceptance rule pixel-by-pixel)
knowledge/      00_brief 01_why_02778 02_hypotheses 03_negative_results 04_free_data_and_licenses
                05_instruments 06_provenance_and_irregularities  (written for the next session)
evidence/       grid, band inventory, layer screen, folds, independence, strata, holdout tables,
                per-submission gate reports
registry/       data_manifest.json (23 pinned inputs + sha256), preregistration.json (decision rules,
                written before any fold was scored)
docs/           the GitHub Pages site; docs/data/*.json is its only source of numbers
submission/     built rasters + LATEST.txt
```

## 3. Reproduce it

```bash
bash scripts/download_competition_data.sh       # wrapper: 23 pinned inputs -> data/, sha256-checked
python3 scripts/restore_data.py                 #   ... or directly
python3 scripts/prepare_data.py                 # bands + labels + elevation -> work/derived/
python3 -m pytest -q                            # metric parity + lattice weights + emission rule
PYTHONPATH=src python3 scripts/run_pipeline.py --stage fit --rounds 1 --mode tip
PYTHONPATH=src python3 scripts/validate_holdout.py --mode tip --emit topk
PYTHONPATH=src python3 scripts/build_submission.py --mode tip --arm <winner> --emit greedy
PYTHONPATH=src python3 scripts/refresh_feed.py   # regenerate the site's data/*.json
```

### 3.1 The H53 path — the file this README now ships

```bash
python3 scripts/restore_data.py --target-dir data         # 23 inputs, sha256-verified (IR-52-020 fixed)
python3 scripts/prepare_data.py                           # audits the grid + band tags -> evidence/
python3 scripts/run_h53.py --stage layers                 # band-6 identity report + 13 radiometric/LiDAR layers
python3 scripts/run_h53.py --stage stack                  # corrected two views -> work/h53_stack.npy (uint8)
python3 scripts/calibrate_g.py                            # |G| from our own 13 scored rasters -> evidence/
python3 scripts/run_h53.py --stage fields --modes hide,tip     # 8 blocked folds, one learner per view
python3 scripts/run_h53.py --stage sweep  --modes hide,tip --greedy   # arms x emitters x budgets
python3 scripts/run_h53.py --stage build --arm auto --dti 0 --ng 8129 --budget 37654 --tag <tag>
python3 scripts/refresh_feed.py && python3 scripts/check_site.py
python3 -m pytest -q                                      # 59 passed, 2 skipped
```

`--stage build --arm auto` reads the winner out of `evidence/h53_sweep.json` with the pre-registered
rule; it does not take an arm from the command line unless you override it, and the override is
recorded in the evidence file. Rebuilding is byte-identical (same sha256), which is the
reproducibility claim.

`--mode` picks the instrument: `hide` (whole catalogue components removed), `block` (quadrant-blocked
as well), `tip` (only the along-strike ends of traces removed). Each writes its own
`evidence/*_<mode>.json`, so the two instruments' numbers cannot be confused with each other.
`bash scripts/research.sh tip hide` runs fit+validate for several modes in sequence.

## 4. What was actually found, before any of this was shipped

### 4.0 H53 — what this session found, and what it is willing to claim

Ordered by how much of the claim is arithmetic rather than inference.

1. **Band 6 of the organiser's own `training_features.tif` is a radiometric band, mis-tagged as
   magnetic.** Its TIFF tag says `magnetic_data` / "Tilt angle or total curvature". Measured on the
   bytes (`evidence/h53_band6_identity.json`, 150,000 px): Spearman **+1.0000** against the
   independently reduced USGS GeoDAWN total-count grid, **+0.9914** against K+Th+U (which is what a
   total-count channel *is*), and |ρ| ≤ **0.149** against all five magnetic bands in the same file.
   It is also strictly positive (2.953 … 88.573) where a tilt angle is bounded by ±π/2. Consequence:
   `src/gems52/features.py` filed a surface-geochemistry band inside **View A**, which corrupts the
   two-view split the brief is built on and the independence test that polices it; and the brief's
   conditional clause "plus any radiometric bands present in `training_features.tif`" resolves to
   **one band**, not to none as `knowledge/04` and IR-52-001 recorded. **IR-52-019 corrects
   IR-52-001.** Official source for the identification: Glen & Earney 2024, USGS data release,
   <https://doi.org/10.5066/P93LGLVQ>.
2. **|G| is not published, but it is recoverable — and the budget follows from it.** For a sparse
   emission (`M = T`) the metric collapses to `DTI = T/(0.2·S + 0.8·|G|)`, one unknown; `T ≤ |G|`
   then gives `|G| ≥ 0.2·DTI·S/(1 − 0.8·DTI)` per submission. Over the 13 SHA-256-verified scored
   rasters the binding row is `hedge-v2` → **|G| ≥ 8,128**, point estimate **8,129**
   (`evidence/h53_g_calibration.json`). `knowledge/01`'s independent loss decomposition of the 0.2778
   file gave 8,000 — two derivations, 1.6 % apart. The H52 budget of 37,654 was *inherited* from an
   unrelated submission; ours is selected by the rule below and happens to land on the same number,
   which is a coincidence worth stating rather than hiding.
3. **Placement is worth more than prediction, and the family left 14 % of it unspent.** One isolated
   emitted pixel can contribute at most **9.380298** of kernel-weighted coverage `A` (the disc weight
   sum, enumerated exactly). Measured on the real scored rasters: `A/S` = **8.044** for the 0.2778
   file (85.8 % of ceiling), 7.956 for `d2-8`, 6.564 for `d1-5`, 3.81–3.94 for the contiguous
   `h19`/`h16` files (41 %), 1.664 for the placeholder (18 %). For a straight trace sampled every
   `s` pixels, credited mass per emitted pixel peaks at **s = 5–6 px = 500–600 m**
   (`evidence/h53_spacing_curve.json`) — not at 100 m and not at the 150–300 m the "dotted" ancestors
   used. On `hide` fold 0, with field, permitted set, budget **and mask all held identical**, moving
   from rank-order top-K (`A/S` 2.233) to a 400 m hard-core cut (`A/S` 8.76) took DTI from 0.03196
   to 0.10101 — **+216 %** — against a matched random control of 0.04291.
4. **Regional centring is what makes a rank field usable.** `knowledge/03` N-2 correctly found that
   a whole-footprint top-K of a rank field loses to random emission, and concluded "rank inside a
   permitted set". The larger half of the fix is subtracting the field's own regional mean:
   `B_c50` / `B_c100` (rank minus its 5 km / 10 km box mean) beat the uncentred `B_only` by
   **+24 % / +18 %** on `hide` at identical emitter and budget. The maximum of a smooth field is a
   mountain; the maximum of a *locally anomalous* field is a structure.
5. **The co-training mechanism failed a second time, with the view split corrected.** With band 6
   moved to View B and six radiometric products plus LiDAR scarplets added, every blended arm scored
   at or below the surface view alone: `AB_w80` 0.09112 hide / 0.05358 tip against `B_c50` 0.09112 /
   0.05421 and `B_c100` 0.09167 / 0.05448. `A_only` — the potential-field view on its own — wins
   **1/4** `hide` folds and **2/4** `tip` folds and is *below* matched random on both, so it is not
   promotable at all. The brief's instruction was to abandon the method if the views' errors are
   strongly correlated; the sharper finding is that one view has no error to correlate with.
6. **The disagreement signal, used as a modulator, does not help either.** Boosting View B where
   View A is confident and B abstains (`Bdis_A`) and damping it where B is confident and A abstains
   (`Bsup_B`) both scored *below* unmodulated View B on `hide` fold 0 (0.06776 and 0.06902 against
   0.07387). The strata remain physically real (A-only sits in deeper cover — that measurement
   stands), but they do not improve the ranking. Reported as a negative result, not dropped.
7. **A new, official, free, previously-blocked data source is now verified and used.**
   INGENIOUS/GDR submission 1391, DOI **10.15121/1881483**, licence **CC-BY 4.0**,
   <https://gdr.openei.org/submissions/1391> — the well-and-spring temperature and aqueous-geochemistry
   database. `knowledge/02` H52-5 marked it blocked because the host would not re-resolve; it resolves
   and was read this session. Measured on the grid: **12,570** cells carry a well or spring,
   **11,258** are >300 m from any mapped fault, **8,958** are >1 km away, only **194** lie *on* a
   catalogue pixel, **362** record ≥70 °C and **147** carry a quartz geothermometer ≥100 °C. The
   derived layers turn each thermal point into a *trace* by walking it along a strike measured from a
   2 km structure tensor of the radiometric field and stopping when coherence drops below 0.30.
8. **What the winner is, and what it is not.** `B_therm | coverage-greedy | 37,654 px` — View B
   (corrected: DEM-derived + radiometric TC + K/Th/U ratios + LiDAR scarplets) rank-centred against
   its own 5 km regional mean, with thermal lineaments injected as a rank bonus, emitted by a
   coverage-greedy on the metric's own numerator. Holdout, 4 folds × 2 instruments, **4/4 wins over
   matched-budget random on both**: `hide` **0.09701** (random 0.03948, **+146 %**), `tip`
   **0.05470** (random 0.02477, **+121 %**); sum **0.15171** against the H52 shipped arm's 0.0809
   (**+87.5 %**). *Not claimed*: that this scores 0.32 or 0.37. The instruments under-forecast the
   board by roughly 4× in absolute terms (the same family scores 0.05 on folds and 0.2778 on the
   board), so a fold number is a **ranking** device and never a forecast. The only projection this
   README puts a number on is the placement gain in isolation — apply the 0.2778 file's *own*
   measured truth density ρ_A = 0.01287 to this file's measured coverage and change nothing else,
   and DTI ≈ **0.3044**. That is arithmetic given its assumption, and the assumption is stated.
9. **The thermal injection is carried but not credited.** `B_therm` beat `B_c50` — the same field
   without the thermal lineaments — by **0.00003** on the selection sum (0.15171 vs 0.15168), with
   4/4 folds on both instruments each. That is not a signal, and the pre-registered rule picked it
   anyway because the rule maximises the sum and was written before the numbers were seen. The gain
   in this file comes from items 1, 3 and 4, not from item 7.


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
* **0.2778 is a placement result, not a discovery result.** Removing 2,545 pixels of self-overlap with
  the mask (6.3 % of the mass) raised that submission's DTI by 2.6 %. See
  [`knowledge/01_why_02778_and_the_bar.md`](knowledge/01_why_02778_and_the_bar.md) for the algebra, the
  perfect-precision counterfactual (0.464 at the same budget), and the acceptance-bar table that shows
  the marginal rule across the entire live leaderboard is the same sentence: *emit a pixel iff it is
  within 224 m of a fault pixel the catalogue does not already have*.

### 1.2 Prior submissions of this family that this file must not be

`GEMSDOE52-CoTrain-Disagree-H52-1` (PR #2, 41,200 px, `c7e980f4…`) and the rasters in `data/scored/`
(gems19, gems24) are this group's own priors. The uniqueness gate compares against every one of them:
this file re-emits none of their mass where it is redundant (174,685 prior pixels dropped) and puts
78.8 % of its own mass where no prior ever reached. Their evidence stays published in `evidence/` and their
code stays runnable as `gems52_h1`; their *holdout claims* do not stand — see `IR-52-014` on
[the register](docs/irregularities.html).

## 5. Irregularities, stated plainly

The live public leaderboard's #1 is **0.3774**, not the 0.3195 stated in the session's opening
context; the group's own 0.2778 currently sits at **#13 of 24 visible rows** (read twice this session, 21:2x
and 21:33 UTC, identical both times). Every file→score
mapping in this family (including the 0.2778 one) is **owner-reported**, not organiser-authenticated —
the board exposes no filename, hash or upload receipt, and GEMSDOE47 formally retracted its alleged
mapping. Full list: [`registry/irregularities.json`](registry/irregularities.json) (machine-readable,
31 entries, every id cited anywhere in the tree must resolve — enforced by
`tests/test_scripts_and_registry.py`), [`docs/irregularities.html`](docs/irregularities.html) and
[`knowledge/06_provenance_and_irregularities.md`](knowledge/06_provenance_and_irregularities.md).

**New or corrected this session.**

| id | what | status |
|---|---|---|
| **IR-52-019** | Band 6 of the organiser's own `training_features.tif` is tagged `magnetic_data` / "Tilt angle or total curvature" but is the GeoDAWN **aeroradiometric total-count** grid (Spearman +1.0000 vs the USGS TC grid, +0.9914 vs K+Th+U, \|ρ\| ≤ 0.149 vs all five magnetic bands). `src/gems52/features.py` therefore filed a surface-geochemistry band in **View A**. **This corrects IR-52-001**, which asserted there is no radiometric band. | open — corrected in `src/gems53/radlayers.py` |
| **IR-52-020** | `scripts/download_competition_data.sh` — the README's documented one-command data placement — called `restore_data.py --group all`. That flag does not exist, so the script exited 2 with a usage message before fetching anything. It survived because nothing downstream asserted the files existed. | **fixed** + test |
| **IR-52-021** | `src/gems52/features.py` has cited `registry/irregularities.json` since it was written; the file did not exist. The register lived only as prose. | **fixed** + test |
| **IR-52-022** | The README stated the grid as "3730 × 3292", which is height × width; rasterio reports width 3292, height 3730. A transposed constant would produce a legal-looking, wrongly-georeferenced file. | mitigated — every H53 number names its axis |
| **IR-52-023** | \|G\| is not published, and `knowledge/05` inherited the budget from an unrelated submission instead of deriving it. | **closed** — \|G\| ≥ 8,128, estimate 8,129 |
| **IR-52-024** | The family's best submission spends only **85.8 %** of the kernel's placement efficiency (`A/S` 8.044 of a 9.380298 ceiling); its contiguous ancestors spend 41 %. | open — largest measured lever |
| **IR-52-025** | **A bug in code this session wrote, caught by a test this session wrote.** `coverage_greedy` updated its running cover with `np.maximum(cf[nbi], kk, out=cf[nbi])`; fancy indexing copies, so `out=` wrote into a throwaway and no pixel ever learned its disc was covered. The greedy packed into the belief field's peak and reported `A/S` = 1.8–2.1 — *worse than top-K* — which read as a property of greedy coverage. An earlier draft of `knowledge/07` H53-5 stated that "property"; the claim is **withdrawn**. Fixed, the greedy reaches `A/S` = 9.27 (98.8 %) and banks 20 % more ρ̂-weighted coverage than hard-core thinning and 33 % more than top-K. | **fixed** + test |
| **IR-52-026** | `gates.find_priors` scanned `docs/downloads/`, which is where `refresh_feed.py` *stages* the built raster — so the candidate was compared against a copy of itself and the gate reported `identical-to-a-prior, novel = 0`. That is the one false verdict that would block a legitimate submission, and it only appeared on the second build, after the first refresh had staged the file. | **fixed** + test |
| **IR-45-001** | The footprint/catalogue counts disagree across the family (5,165,852 / 5,165,840 / 5,167,373 and 60,894 / 60,988). Recounted: it is a **mask definition**, not an arithmetic error — `labels ≥ 0` gives 5,167,373 and 60,988; the all-19-bands-finite intersection gives 5,165,840 and 60,894. | closed — every fraction now names its mask |

Two of these (IR-52-025, IR-52-026) are bugs in code written *this session*, found by tests written
*this session*, and both are published rather than quietly fixed. That is the point of the register:
"the gate found a bug in the thing that writes the gate's input" is the evidence that the gate is
real (cf. IR-52-007).

Licences: all pinned inputs are the competition's own bundles or USGS/GDR open data; the sibling-derived
external CSVs in `data/external/` are **derived, not organiser-authenticated** and are used only as
optional corroboration, never as positive labels. See
[`knowledge/04_free_data_and_licenses.md`](knowledge/04_free_data_and_licenses.md).

## 6. No manual steps

`docs/data/*.json` is regenerated from `evidence/` by `scripts/refresh_feed.py`;
`.github/workflows/feed.yml` runs it nightly and on push, and the site renders only from those files.
If a number on the site is wrong, the fix is the evidence file, never the HTML.
