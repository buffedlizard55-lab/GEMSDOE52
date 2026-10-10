# 75 · Current user brief — session of 2026-10-10 (round H87)

This is the operative brief for the current session, captured for audit and for the next session to
read first (AGENTS.md requires it). It is organised, not paraphrased away: every instruction below
appears in the session request.

## Non-negotiables stated at the top of the brief

1. **Generate a UNIQUE TIF submission for the competition.** Do not copy a previous submission
   except for learning. It must be **obvious whether it is OK to download and submit** the generated
   TIF.
2. There must be an **easy-to-download submission TIF**, as described by the brief, surfaced at the
   very beginning of the site / executive summary.
3. Earlier upload attempt failed on the portal with **"Predicted values must be in range [0, 1]"** —
   so the shipped raster must be all-finite in [0, 1] (zeros, never NaN, outside the emitted set).
4. The submission form needs **a unique name** and **a short note** (≤ 140 characters, e.g.
   "clustering with k=25"); both must be published with the file.
5. Work line by line from official, verified sources; provide links for manual review; flag
   irregularities; **no hallucinations**; no manual input required from the user.
6. Core values to apply: **Maximize P(Win)** and **Own the Outcome** (Arena AI team values quoted in
   the brief).

## The lane for this session (single method paragraph, to be stayed inside)

Co-training between a geophysical view and a surface view, with **disagreement as the discovery
signal**. Blum & Mitchell (COLT '98, pp. 92–100, doi:10.1145/279943.279962) show that when each
example has two views, each sufficient and approximately conditionally independent given the class,
two learners trained on separate views can use each other's confident predictions on unlabeled data.
View A is potential-field and subsurface (gravity, magnetics, strain, seismicity). View B is surface
(DEM-derived curvature and slope, plus any radiometric bands present in `training_features.tif`).
Test the independence assumption empirically: correlate each view's spatial-block out-of-fold errors
on labelled negatives, and abandon the method if they are strongly correlated. Pseudo-label only
where one view is confident and the other abstains, using whole-segment spatial blocks and a buffer
so no leakage reaches the evaluation. The discovery signal is disagreement. Where A is confident and
B is not, the fault may be buried beneath cover. Where B is confident and A is not, suspect surface
artefacts such as roads or erosion lines. Because Phase 2 reviewers verify faults, write the
geological reasoning for every A-only candidate. Co-training can also amplify bias, so compare
against a single-view baseline on hide-and-recover segments. Normalise to [0,1], write the GeoTIFF,
apply the repo's metric-aware placement, run the uniqueness gate, and confirm the output isn't merely
the union of the two views.

## Parallel-run protocol (as given)

1. **Lane.** Stay inside the method paragraph. If the raster's rank correlation with any registry
   raster exceeds **0.90**, or more than **70 %** of the dots fall within 3 px of one registry
   raster's dots, that is drift: log it as a duplicate and stop. Check on the surface before
   placement **and** on the final dots.
2. **Reuse, don't rebuild.** Use the template's cached feature stack, `evaluate_holdout.py` and
   `submission_writer.py`. Holdout = hide-and-recover: withhold whole fault segments with a buffer,
   derive every catalogue-based feature only from visible faults, mask visible faults pixel-exactly,
   score pooled DTI (α 0.2, β 0.8, 300 m triangular kernel). Fix a wrong shared tool once in the
   template and report it; never keep a private fork.
3. **Label every number** as HOLDOUT-DTI (evaluator version, number of withheld positives, 95 % CI)
   or ORGANIZER-CONFIRMED (copied from a submission-page receipt). A projection is never written as
   a score.
4. **Leakage canary.** Test each feature alone on the holdout before trusting any result. AUC above
   **0.90** means leakage until proven otherwise.
5. **Run card.** End with one JSON card: hypothesis; mechanism; the named non-fault process that
   could mimic it; holdout DTI + CI; correlation/overlap vs registry; raster SHA-256; validator
   output (no NaN inside the footprint, values in [0,1], CRS/shape/transform match); submission name
   + note of at most 140 characters; verdict promote / negative. **Negative results are
   deliverables.**
6. **Budget.** Stop after **3** experiments or **2** hours. Do not pick submissions: promotion to a
   real slot is a separate selector step, within the weekly cap on the submission page.

## Research instruction

Before implementing, generate **3–5 candidate geological hypotheses** not yet tried, each naming the
specific layer(s), the physical signature targeted (edge detection, curvature transform, …), why it
should catch a fault missing from the USGS/INGENIOUS catalogue rather than one already in it, and
how it differs from anything already implemented. Rank by expected DTI improvement and implementation
cost. Validate the top candidate on the spatially-blocked holdout **before** touching a weekly
submission slot. If a candidate needs new external data, name the specific free, official source and
**check it is obtainable** before proposing it as viable.

## Score context supplied with the brief (all OWNER-REPORTED, not organizer-confirmed)

* Highest owner-reported file in the sibling family: `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros`
  = **0.2778** (GEMSDOE32). The brief asks *why* it scored highest and whether it can be beaten.
  Answer re-measured from bytes in `knowledge/49`: it is the 0.2600 file with its 100–200 m
  catalogue ring deleted — arithmetic, not geology.
* Public leaderboard high score quoted in the brief: **0.3774**; and later **0.3195** is given as
  "the highest score right now", so the design target is a strategy that could exceed **0.3195**.
* ~60 sibling GEMSDOE sites with per-file owner-reported scores are listed in the brief; the full
  list is preserved in the README's brief section.

## Official links named in the brief

* Competition: <https://www.drivendata.org/competitions/306/competition-doe-gems/>
  · problem description <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>
  · about <https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/>
  · data (login-walled) <https://www.drivendata.org/competitions/306/competition-doe-gems/data/>
  · leaderboard <https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/>
* Reference solution: <https://github.com/drivendataorg/gems-prize-reference-solution>
* USGS GeoDAWN: <https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and>
* INGENIOUS: <https://gbcge.org/current-projects/ingenious/>
* GDR submission 1391: <https://gdr.openei.org/submissions/1391>
* EPSG:32611: <https://epsg.io/32611> · Tversky index: <https://en.wikipedia.org/wiki/Tversky_index>
* Submission-format PDF cited in the brief: <https://docs.nlr.gov/docs/fy26osti/96647.pdf>
  (**irregularity:** this host is outside the sandbox egress allowlist and was not fetched this
  session; the Dropbox mirror `GEMS_96647.pdf` named in the brief is likewise unreachable. The
  format rules used here come from the official competition page 967, which *was* read, and from the
  organiser's own `sample_submission.tif` bytes.)

## Standing limitations restated

* No DrivenData credentials in this sandbox → the three official rasters cannot be pulled from the
  portal. They are restored from SHA-256-pinned owner mirrors by `scripts/restore_data.py` and are
  labelled **integrity-pinned, not organizer-authenticated**.
* Sandbox egress is limited to `github.com`, `codeload.github.com`, `api.github.com`,
  `registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org`. USGS/3DEP/GDR/DrivenData hosts are not
  reachable from `bash`.
* Weekly submission slots are a separate selector decision; this project never spends one
  automatically.
