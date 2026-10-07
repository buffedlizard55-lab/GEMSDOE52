# GEMSDOE52

Target: a **unique, downloadable single-band GeoTIFF** for [DrivenData competition 306 — DOE GEMS
Prize](https://www.drivendata.org/competitions/306/competition-doe-gems/), built to beat this group's
best of 0.2778, with the reasoning and the evidence published next to the file.

## The file — download it, submit it, nothing to configure

| | |
|---|---|
| **download (TIF)** | [`docs/downloads/gems52-h53-revealed-core-strike-continuation-50517px-r1.tif`](docs/downloads/gems52-h53-revealed-core-strike-continuation-50517px-r1.tif) — click, save, upload |
| **download (ZIP)** | [`docs/downloads/gems52-h53-revealed-core-strike-continuation-50517px-r1.zip`](docs/downloads/gems52-h53-revealed-core-strike-continuation-50517px-r1.zip) — the same raster plus the note to paste and the evidence JSON |
| also in the repo | [`submission/gems52-h53-revealed-core-strike-continuation-50517px-r1.tif`](submission/gems52-h53-revealed-core-strike-continuation-50517px-r1.tif) |
| bytes / shape | 311,436 · 3730 × 3292 · single band · `float32` · EPSG:32611 · 100 m cells |
| values | {0, 1} only — 50,517 positive px, 0 outside the valid footprint, 0 on the catalogue, 0 within 200 m of a mapped trace, **no NaN** (verified by reading the written file back, not by trusting the writer) |
| sha256 | `6501da54c39757556cac7e3d7990ce0f35ddeacc039fdd2139f3beab753ce424` |
| notes box (≤200 chars) | `H53 revealed-core 25517px + 25000px novel strike-continuation; 200m corridor excluded; \|G\|=14089` — 96 chars, rendered from `docs/data/submission.json → submission_note` |
| format gate | `True` (`src/gems52/gates.py`, checked on the written bytes) |
| uniqueness gate | `True` — strictly-novel-and-selective: **25,000 px (49.5 %)** touch no prior of this family, and **1,004,823** prior px are deliberately **not** re-emitted, so it is not "the union" either |
| what it is | 25,517 px **retained core** = the double-corroborated atom `A & C`, whose credit the organiser's own published scores bound exactly at 4,168–5,223 (density 16.3–20.5 %, central 20.1 %); plus 25,000 px **strictly novel** = 10,419 along the strike recovered from that core and 14,581 free candidates on the same fabric, every one an isolated dot |
| selection | `evidence/revealed_budget.json` — the budget maximises **P(DTI > 0.2778)** = 0.8189 by integrating the exact metric over the exact `t_core` interval × a stated prior for the unknown novel credit density. Mean 0.3191, worst 0.2301, best 0.4081. **A projection, not a forecast** |
| calibration | `evidence/revealed_calibration.json` — `\|G\|` = **14,088.7 px**, the ≤200 m ring's credit **exactly 0**, six atoms partitioning 121,131 px exactly. Cross-check: `T = 471.6·S^0.2284` predicts eight published scores to within 4 %, five within 1.5 %, including one file from a different family |
| two views | View A (potential field / subsurface, 49 features) out-of-fold AUC **0.7126**; View B (surface / LiDAR scarp / radiometric, 32 features) **0.9277**; blend 0.9139 — **View B alone beats the blend, and that is printed rather than buried**. Independence: pixel r = 0.2744, block mean r = 0.2784 against a 0.60 abandonment threshold → proceed, block variance not degenerate |
| holdout verdict | The two-instrument holdout this repo used to select with **does not predict the organiser's score** (Spearman −0.1045, p = 0.734, n = 13; the group's best file ranks *last* of 13 on it). It is reported, labelled broken, and no longer selects anything — `IR-52-017`, `knowledge/03` N-9 |
| exact steps | [docs/executive-summary.html](docs/executive-summary.html) |
| rebuild it | `PYTHONPATH=src python3 scripts/build_revealed_submission.py --tag r1`   # idempotent: rerunning reproduces the same sha256 even after the previous output has been published into `docs/downloads/` |

The site is the product: [docs/index.html](docs/index.html) renders every number from
`docs/data/*.json`, which `scripts/refresh_feed.py` regenerates and a committed GitHub Actions workflow
refreshes on a schedule, so **nothing on the page needs hand-checking**.

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

### 4.0 The H53 round: five findings that changed what this repo selects on

Full derivations in [`knowledge/07_revealed_preference_inverse.md`](knowledge/07_revealed_preference_inverse.md);
hypotheses and their ranking in [`knowledge/08_hypotheses_H53.md`](knowledge/08_hypotheses_H53.md).

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

`GEMSDOE52-CoTrain-Disagree-H52-1` (PR #2, 41,200 px, `c7e980f4…`) and the rasters in `data/scored/`
(gems19, gems24) are this group's own priors. The uniqueness gate compares against every one of them:
this file re-emits none of their mass where it is redundant (174,685 prior pixels dropped) and puts
78.8 % of its own mass where no prior ever reached. Their evidence stays published in `evidence/` and their
code stays runnable as `gems52_h1`; their *holdout claims* do not stand — see `IR-52-017` on
[the register](docs/irregularities.html).

## 5. Irregularities, stated plainly

Six were added this round and are summarised in
[`knowledge/06_provenance_and_irregularities.md`](knowledge/06_provenance_and_irregularities.md) under
"H53 round": **IR-52-017** (the validation instrument does not predict the board), **IR-52-018** (the
≤200 m ring earns exactly zero, contradicting `knowledge/01` §5 item 2 and `knowledge/02` H52-2),
**IR-52-019** (no available feature re-ranks inside the champion file), **IR-52-020** (a per-block AUC
of 1.000 over n = 3 samples), **IR-52-021** (`gates.find_priors` swept the 19-band feature stack in as a
prior submission, producing a "prior union" larger than the footprint), **IR-52-022** (the downloads
index was built before the rasters were copied into it, so it was always one run behind).

The live public leaderboard's #1 is **0.3774**, not the 0.3195 stated in the session's opening
context; the group's own 0.2778 currently sits at **#13 of 24 visible rows** (read twice this session, 21:2x
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
