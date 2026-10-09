# 34c — Declared post hoc: uniqueness and lane handling for the H62 emission (2026-10-09)

Status: a **placement and gating decision** taken after the first H62 build failed the user's
uniqueness requirement. It does not touch the frozen H62 hypothesis, S1, S2, the evaluator, the six
arms, the holdout budget, or the verdict rule in `knowledge/34` and `34b`.

## 1. Build 1 was not unique (kept as a rejected receipt)

- `evidence/h62_build1_rejected_run_card.json`: canonical decoded-pattern uniqueness PASS, but
  `novel_fraction` = **0.0**. Every one of its 37,600 emitted cells already occurred in the union of
  registry rasters.
- Its verdict logic did not check novelty (`uniq_ok` ignored `novel_fraction`), so it would have
  passed as unique. Fixed in `scripts/run_h62.py`; the TIF is kept only under `work/h62/rejected_first_build/`
  (git-ignored) and is **not published**.

## 2. Registry structure (measured, `work/h62/prior_density_probe.json`)

- 548 registry rasters; 34 have more than 20% positive pixels, 33 have at least 40%.
- The lane's own classification (`gates.registry_coverage`, 3 px halo of the eligible footprint,
  threshold `gates.PROBE_COVERAGE` = 0.95) gives **35 universal-coverage probes** and **511 informative**
  rasters on this run. H61's receipt (`evidence/h61_lane_dots.json`) reports 14 probes and 531
  informative. This count difference is **unresolved and flagged**; the classification rule is the same.
- Probes are excluded from the novelty test, as the lane policy does. Without that exclusion, the union of
  all rasters covers the whole allowed footprint and no candidate can be placed.

## 3. Constraints tested

| step | constraint | result |
|---|---|---|
| exact novelty | no emitted cell is a positive pixel of any informative raster | 4,325,298 → **206,848** allowed cells |
| 3 px union halo | no emitted cell within 3 px of any informative positive | **0** cells, impossible |
| per-raster 70% rule, full budget 37,600 (cap 26,320 per raster) | from the lane rule: >70% of dots within 3 px of one raster is a duplicate | 9 rasters over cap; constrained placement reaches **31,487 of 37,600** |
| per-raster 70%, budget 30,000 | cap 21,000 | placed 26,097 of 30,000, infeasible |
| per-raster 70%, budget 25,000 | cap 17,500 | placed 22,212 of 25,000, infeasible |
| per-raster 70%, budget 20,000 | cap 14,000 | placed 18,388 of 20,000, infeasible |

So on this registry, the field's preferred region cannot be emitted with fewer than 70% of its dots near
any single raster, at any budget tried. Trying smaller budgets only moved the shortfall, and the search was
stopped after the time limit in the brief.

## 4. What was published

- Build mode `H62_NOVELTY_MODE=exact_only`, budget 37,600. Exact novelty is enforced (no emitted cell is a
  positive pixel of any informative raster); the per-raster 70% cap is **measured and reported, not
  enforced**.
- Decision (user's own rules): the file is **download-eligible** if format-valid and unique on decoded
  pixels, and **not submit-eligible**. The lane marks it DUPLICATE under the 70% per-raster rule, the
  holdout is negative (`evidence/h62_holdout.json`), and S1 failed. The file is labelled
  "research only, do not submit" in its own note.
- The holdout DTI evaluates the six fold-level arms, not this final placement. Its verdict is unchanged.

## 5. Independent re-check (`work/h62/independent_uniqueness_check.py`, outside the gate code)

- 548 of 548 priors checked: 0 identical on decoded pixels to the file.
- 35 probes share pixels with the file (expected: they cover the footprint).
- 513 informative priors (own classification, same coverage rule): 0 share a positive pixel with the file.
  The gate counts 511. The two-raster difference is unresolved and flagged.
- 9 informative rasters have more than 70% of the file's dots within 3 px (largest 0.888).

## 6. Literal lane

The literal lane remains DUPLICATE for every nonempty candidate, because probes have 3 px coverage
close to 100%. This is the saturation finding in `knowledge/31` and `gates.py`, not a new failure.
