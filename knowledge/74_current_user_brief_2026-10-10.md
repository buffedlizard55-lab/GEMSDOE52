# Current user brief — 2026-10-10 (active direction; not a verbatim prompt)

This note records the active request and hard constraints for the next session. The preserved 2026-10-09 user prompt remains at `knowledge/36_current_user_brief_2026-10-09.md` and in the README; read that historical prompt too, but do not treat its score attributions or stale status as verified facts.

## Active request

Continue review of GEMSDOE52 autonomously. Give a source-grounded analysis of the reported H33 result without describing an owner-reported file/score association as organizer-confirmed. Develop and rank **3–5 genuinely distinct geological hypotheses**, state their layers, physical signatures, plausible catalogue-missing explanation, project novelty, likely DTI value versus cost, named non-fault mimics, and official free/licensed data sources. Test the best candidate on the spatially blocked holdout before any slot decision. Generate an auditable, unique GeoTIFF only if the inputs and frozen protocol actually permit it. Keep the README direction and public website/feed useful and current. Complete three review passes, disclose limitations/irregularities, and use the required pull-request-then-merge workflow.

The output must say unmistakably whether a newly generated file is safe to download and whether it is approved to submit. A format-valid research artefact is not automatically a promotion decision. Do not spend or select a competition slot: the task authorizes **zero** slots.

**Task framing:** the official competition target is geological fault prediction; its expert labels include newly identified faults, and external data are permitted only subject to the competition rules. Do not describe a fault-prediction raster as a geothermal-vent map.

## Binding method, validation and release constraints

- The intended method lane is co-training of geophysical/subsurface View A and surface View B, with disagreement treated as a discovery hypothesis—not as an automatic union. A-only candidates need per-candidate geological reasoning; B-only candidates may be roads, erosion, or other surface artefacts.
- Apply the literal parallel-run gate before placement and again to final dots: stop and record DUPLICATE/STOP if Spearman correlation with any registry raster is above 0.90 or if more than 70% of candidate dots lie within 3 px of any one registry raster. Do not waive or narrow the census to manufacture a pass.
- Reuse the shared cache and shared `evaluate_holdout.py` / `submission_writer.py`; fix shared tools in the template if required. Do not create a private fork.
- Holdout must hide whole fault segments with a buffer; derive catalogue-based features from visible faults only; mask visible faults pixel-exactly; use pooled distance-weighted Tversky with α=0.2, β=0.8, a 300 m triangular kernel, and report the evaluator, withheld-positive count, and 95% CI.
- Test features individually; AUC >0.90 is a leakage alarm. Measure spatial-block OOF-view error correlation on labelled negatives. Co-training requires both its sufficiency and independence gates. Pseudo-label only where one view is confident and the other abstains, in buffered whole-segment blocks; compare with a single-view baseline at equal mass.
- Normalize/write/re-open any GeoTIFF; use metric-aware placement; run uniqueness and not-the-union checks. Scores must be labelled HOLDOUT-DTI or ORGANIZER-CONFIRMED from a copied submission-page receipt. A projection is never a score. Public leaderboard values are instead explicitly labelled PUBLIC-BOARD and do not identify a file.
- End an actual run with one JSON card containing the hypothesis, mechanism, named mimic, HOLDOUT-DTI/CI, registry correlation/overlap, raster SHA-256, validator results (inside-footprint NaN, range, CRS, shape, transform), submission name and a note no longer than 140 characters, plus promote/negative verdict. If no candidate was run, state NOT RUN and use nulls rather than borrowing an older run's values.
- Maximum budget: 3 experiments or 2 hours. Respect the weekly cap shown on the portal; do not select or push a slot. Keep raw/large data out of Git and record source/license/obtainability gaps.
- Preserve the values “Maximize P(Win)” and “Own the Outcome.” Work on the Arena-provided branch, open a PR from it, then merge as explicitly requested.

## Newly binding result and current stop conditions

`AGENTS.md` and `knowledge/68_h77cond_results_and_limits.md` close the ordinary co-training lane. H77cond tested the buried-fault rescue argument conditionally and found the opposite ordering in all four folds. Do **not** repeat that experiment or pseudo-label exchange without a genuinely new, preregistered mechanism that survives sufficiency and the full literal lane gate. The full-census literal near-3-pixel rule is recorded as DUPLICATE/STOP for every nonempty raster because universal-coverage probes saturate it; never omit those probes.

The public leaderboard was observed again on 2026-10-10. Its current public top is 0.3774; 0.3195 is rank 8; 0.2778 appears at rank 22 for the team `extradr19`. All are PUBLIC-BOARD, team-level observations; none confirms that any named TIFF/hash received that score. The current snapshot is `registry/leaderboard_snapshot_2026-10-10.json`.

This H83 continuation is a preflight/review, **not** an experiment. At its start, `data/`, `work/r2/features`, and `work/h82` were absent. No 1 m DEM tile list or raw tiles were staged. No new holdout, TIFF, portal upload, or submission receipt is authorized unless the stop conditions are independently cleared. Negative evidence is a valid deliverable; do not fabricate a submission to satisfy an earlier high-urgency instruction.
