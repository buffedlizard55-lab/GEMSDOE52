# Working agreement

Before every work session, read `README.md`, its full current user brief, `knowledge/07_r2_hypotheses_preregistered.md`, and the newest review/irregularities record. Read previous failed experiments before proposing another.

Maximize P(Win): prioritize geological signal and trustworthy spatial validation. Never spend a competition upload slot unless the new candidate has beaten the current comparable holdout best. Own the Outcome: verify written files, served downloads, reproducibility, provenance and failure cases end to end.

Keep known-catalogue labels separate from verified fault absence, public participant scores separate from filename attribution, hypotheses separate from discoveries, and format-valid artifacts separate from promotion-approved ones. Do not invent organizer validation or claim a guaranteed leaderboard gain. A GeoTIFF with a new name or compression is not a unique prediction; compare decoded pixels.

This session's working branch is fixed by Arena. Do not change branches. Keep raw competition data and large intermediate arrays under ignored `data/` and `work/`. Publish small audit receipts, the unique compressed prediction raster and its review table.

## Current H61 continuation

Read `README.md`'s H61 block, `knowledge/30_hypotheses_H61_preregistered.md` (frozen before any fit;
`scripts/run_h61.py` refuses to run if its hash moves) and
`knowledge/31_h61_results_and_limits.md`. H61 is **negative**: View A (potential field / subsurface)
reaches out-of-quadrant AUC ~0.52 while fitting its own quadrant at ~0.93, so the Blum–Mitchell
sufficiency premise fails and the disagreement arm is noise-dominated. Do not re-tune it into a
positive result, do not promote it, and do not treat a valid file as an approved entry.

Three shared-instrument repairs are now authoritative and must not be reverted or forked: masked
support `S` (off-catalogue pixels only), `|G|` as the measured interval [5,949.3, 12,512.1] px rather
than the superseded point 14,088.7, and `gems52.gates.lane_report`'s measured universal-coverage-probe
classification (a prior whose 3 px halo covers >=95% of the eligible footprint cannot localise a lane;
its literal statistic is still reported). Band 6 is radiometric total count (Spearman 1.0000 against
the external GeoDAWN TC grid), so it belongs in View B. See `registry/irregularities.json`
IR-H61-001 … IR-H61-008.

## Previous CTD5 continuation

Read the entire current prompt in `README.md` (also `knowledge/26_current_user_brief.md`),
`knowledge/25_ctd5_preregistered.md`, `knowledge/27_ctd5_results_and_limits.md`, and the
three-pass review. CTD5 is negative and stopped: a registered survey-wide lattice makes
the >70% near-dot gate impossible on this footprint. Do not quietly exclude it, tune a
new placement, promote CTD5, or treat the archival H57 LATEST pointer as upload approval.
Raw input pins authenticate mirror bytes only. Preserve dated source and score caveats.

### H69 (2026-10-09) — the lane rule is satisfiable, and the lever is cross-family consensus

Measured this round, all reproducible from `evidence/h69_placement.json` and `scripts/run_h69.py`:

* **`gems52.gates.lane_report`'s probe classification was not the whole story.** H61 concluded the
  literal 70 % rule was unsatisfiable because of universal-coverage probes. It is also unsatisfiable for
  any emission ranked by this family's own habitat signal: an unconstrained greedy over the legal set puts
  **96.14 %** of its dots within 3 px of one informative raster, with **84 of 343** informative priors above
  the limit.
* **A per-prior quota does not converge.** `S/quota` is structurally ≈ 1.34, so the achieved share is
  pinned near **0.745 at every budget** (24,500 → 32,871; 22,960 → 30,864; 21,558 → 29,069). A quota
  computed against a *target* budget is also the wrong denominator: at quota 26,263 only 35,149 dots were
  placeable, an achieved share of 0.7472.
* **Excluding offenders' halos is not available:** the union of the 84 offenders' 3 px halos leaves
  **361 px** of the 4,859,987 px legal set.
* **What works:** restrict the pool to pixels of low **cross-family consensus** — the count of distinct
  decoded prior patterns whose 3 px halo covers the pixel. At `consensus ≤ 60` (2,741,649 px pool) the
  greedy fills the whole 37,600-dot budget at a worst informative near-dot share of **0.6985**, verified
  exactly against all 343 informative priors. Search the threshold from the loosest end and take the
  largest feasible one, so the field keeps as much signal as the lane allows.
* **`eligible` in the committed instrument is the valid footprint *including* catalogue pixels.** Passing
  the off-catalogue set empties both training classes (`spatial.folds` builds `truth = held_all & region`
  from the catalogue) and surfaces as "insufficient training classes", or, on a screen that only computes
  an AUC, as a silently wrong sufficiency number. This round produced View A mean AUC 0.6636 that way
  before the mistake was caught; the committed instrument gives **0.5281**. The wrong number is recorded in
  `knowledge/53` §2.1 so nobody resurrects it.
* **`spatial.whole_pseudo_segments` can return zero labels.** With H69's views it returned **0 pixels in
  all four folds**, so `disagreement_post` is bit-identical to `disagreement_pre` and the paired CI is
  exactly [0, 0]. Same class as `IR-H58-002`; check the count before interpreting a "post-exchange" arm.
* **A round must exclude its own artefacts from its registry.** `gates.find_priors` sweeps `submission/`,
  so a second attempt at the same stage finds the first attempt's GeoTIFF as a "prior" and reports
  identical-to-a-prior. `scripts/run_h69.py` filters `gems52-h69-*` and says so.
* **Cache the lane reports.** Two `lane_report` phases over 566 rasters cost ~13 min; they are now cached
  against the SHA-256 of the emission plus the prior count, which is the difference between a fixable
  crash and a lost quarter-hour.
