# 99 · Standing user brief for round H97 (2026-10-10) — verbatim

> Read this at the start of every session (AGENTS.md working agreement). It is reproduced verbatim in
> `README.md` → the `<!--H97-README-->` block. Numbers inside it are the owner's; where this
> repository measured something different, the difference is recorded in
> `registry/irregularities.json` (IR-H97-*), never edited here.

---

1. **Review the repo**, then explain at PhD level *why*
   `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` scored **0.2778** and whether a higher-scoring
   unique submission can be produced.

2. **MUST generate a unique TIF submission** — never copy a previous submission (only for learning);
   it must be *obvious on the site whether it is OK to download and submit*; the submission `.tif`
   must be easy to download (linked per the prompt), be a single-band GeoTIFF matching the submission
   format CRS/shape/transform, values strictly in **[0,1]** (an earlier upload failed with
   *"Predicted values must be in range [0, 1]"*), with a unique name and a short note (≤140 chars).

3. **Method (this session's lane, stay inside it):** co-training between a
   geophysical/potential-field/subsurface View A (gravity, magnetics, strain, seismicity) and a
   surface View B (DEM curvature/slope + any radiometric bands in `training_features.tif`),
   disagreement as discovery signal, per Blum & Mitchell COLT '98 doi:10.1145/279943.279962. Test the
   conditional-independence premise empirically on labeled negatives (spatial blocks) and abandon the
   arm if errors are strongly correlated. Pseudo-label only where one view is confident and the
   other abstains, whole-segment blocks + buffer. A-confident/B-abstains ⇒ possibly buried fault
   under cover (write geological reasoning **for every A-only candidate**); B-confident/A-abstains ⇒
   suspect surface artifacts (roads, erosion). Compare against single-view baseline on
   hide-and-recover. Normalize to [0,1], write GeoTIFF, apply metric-aware placement, run uniqueness
   gate, and **confirm the output is not merely the union of the two views**.

4. **Parallel-run protocol:** lane-drift check — if raster rank-correlation with any registry raster
   > **0.90**, or > **70 %** of dots fall within 3 px of one registry raster's dots, log as duplicate
   and stop; check on the surface *before* placement and on final dots. Reuse the template cached
   feature stack and the `scripts`/`src` holdout + submission writer (no private forks — fix shared
   tools once and report). Label every number **HOLDOUT-DTI (evaluator version, # withheld positives,
   95 % CI)** or **ORGANIZER-CONFIRMED**; a projection is never a score. Leakage canary: any single
   feature with holdout AUC > **0.90** is leakage until proven otherwise. End with a one-JSON run card
   (hypothesis; mechanism; named non-fault process that could mimic it; holdout DTI + CI;
   correlation/overlap vs registry; raster sha256; validator output — no NaN in footprint, values in
   [0,1], CRS/shape/transform match; submission name + ≤140-char note; verdict promote/negative).
   Negative results are deliverables.

5. Beat the current best: the owner states the current competition high score is **0.3195**; the same
   message also cites a GEMSDOE high score **0.3774** (and GEMSDOE32's 0.2778 as the site whose TIF
   was downloaded). Design a fundamentally new strategy/research/test/submission system not used by
   the existing GEMSDOE sites.

6. Emphasis: deep, autonomous, literature-grounded research (no manual input); free official verified
   sources only, with links for manual review; **no hallucinations — verify line by line**; flag
   irregularities; run the work through ≥3 passes (implement → bug/edge-case review → full re-check
   vs the original request); create a PR and merge to `main`; list limitations and remaining work.

---

## Standing owner constraints (carried forward, still in force)

* Uniqueness is mandatory and highest-urgency: **do not copy a previous submission** except for
  learning, and make it obvious on the site whether the generated TIF may be downloaded and
  submitted.
* The submission page must offer an easy download at the top / executive summary, and an
  executive-summary subpage must explain exactly how to submit to the contest.
* Predictions must lie inside [0,1] with no NaN inside the footprint, and match the sample's
  CRS/shape/geotransform.
* No hallucinations: verify line by line against official/trusted sources, with links for manual
  review; flag any irregularity for review.
* Work autonomously; run the task to completion with no manual input.
* Do not spend a weekly submission slot on an idea that has not beaten the current holdout best.
* Adopt the Arena Core Values as focal points: **Maximize P(Win)** and **Own the Outcome**.
* Deliver through 3 passes, open a PR against `main`, merge it, and list limitations/remaining work.

## What "the bar" means in this repository

The owner's numbers are *board* numbers (public leaderboard / owner-reported site scores). The
repository's **HOLDOUT-DTI** is a local instrument (`gems52-pooled-hide-v1`) and **is not a board
score**; the promotable bar it uses is **0.192829** (`evidence/h82_holdout.json`, H82 `B_DVA2`).
Every DTI quoted in this round's documents is labelled with its evaluator version, withheld-positive
count and 95 % CI, or it is an input measurement. Nothing in this round is ORGANIZER-CONFIRMED.
