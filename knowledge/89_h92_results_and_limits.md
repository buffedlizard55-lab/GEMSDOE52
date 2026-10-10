# 81 · H92 — support-size calibration of the mandated disagreement emission: results and limits

Round H92, 2026-10-10. Lane: the two-view co-training paragraph of the brief.
Artefacts: `scripts/run_h92.py` (stages `audit | fit | ladder | emit`), `scripts/h92_run_card.py`,
`scripts/h92_reasoning.py`, `evidence/h92_audit.json`, `evidence/h92_ladder.json`,
`evidence/h92_run_card.json`, `docs/downloads/h92-a-only-reasoning.csv`,
`submission/gems52-h92-cotrain-disagree-supportcal-17707px-20261010T222145Z.tif`.

## Verdict up front

* **DOWNLOAD YES** — the GeoTIFF is format-valid (single band, float32, EPSG:32611, all finite,
  values exactly {0,1}, 17,707 set pixels, SHA-256
  `ddf09d89003eacb8a9df8896a9783e078a6fca5500445b24f3375d3db4d79d4f`) and decoded-pattern unique
  against all 146 aligned priors still on disk (novel fraction 0.229, not identical to and not a
  subset of any prior, not the literal union of the registry).
* **SUBMIT NO** — two independent reasons, both recorded in the run card:
  1. **HOLDOUT-DTI NEGATIVE.** The mandated field scores **0.0632** pooled on the shared
     hide-and-recover instrument at its own optimum (75.2k dots), against **0.1346** for a random
     placement at the same budget and **0.2228** for the single-view B control. The paired
     difference against `single_B` is **−0.1596 [−0.1821, −0.1374]**, so the pre-registered
     promotion rule (same-budget paired CI excluding zero, in the candidate's favour) fails.
  2. **LANE STOP.** Directed ≤3 px dot proximity to the largest offender is **0.969** (> 0.70) and
     to the scored lattice probe **1.000** (> 0.70). The rule is "no lane retuning", so the file
     is labelled research-only rather than re-placed.

## What was measured

**Instrument (`gems52-pooled-hide-v1`, label-blind quadrants v2, 200 px blocks, 1000 draws,
seed 520810; 53,186 withheld positives over 4 folds).** Pooled HOLDOUT-DTI by arm and instrument
budget (dots per fold):

| arm | 4k7 | 9k4 | 18k8 | 37k6 | 75k2 |
|---|---|---|---|---|---|
| `single_B` (comparator) | 0.0590 | 0.0861 | 0.1262 | 0.1746 | **0.2228** |
| `union_max` (comparator) | 0.0452 | 0.0699 | 0.1027 | 0.1490 | 0.1974 |
| `random` (control) | 0.0133 | 0.0245 | 0.0461 | 0.0804 | 0.1346 |
| `a_only_stratum` (strict A-only mask) | 0.0053 | 0.0111 | 0.0234 | 0.0428 | 0.0887 |
| `disagreement_post` (**the mandated field**) | 0.0044 | 0.0075 | 0.0155 | 0.0329 | **0.0632** |

Every arm's curve is still rising at the top rung, so the instrument has not found a peak; all
budget statements below are lower bounds. `single_B` at the 37k6 rung reproduces the committed
H61 value 0.174517 to 5 significant figures.

**Support calibration.** The board prevalence is not the instrument prevalence. The instrument runs
at **1.1579 %** pooled positive density (0.9123–1.4462 % per fold); the board's truth, recovered
from the score algebra below, is **0.27265 %** of the sample footprint (bracket 0.112–0.294 % from
the published scoring docstring). Ratio **4.247** (score-algebra) or **5.790** (docstring midpoint).
Dividing the instrument optimum by 4.247 gives a board-side budget of **17,707 dots** — the budget
the shipped file uses. Because every curve is monotone rising on the instrument, this corrected
budget is a lower bound, not a measurement.

**Board algebra reproduced from restored bytes** (`run_h92.py audit`, no owner-reported file read
during the algebra): the 0.2778 reference is a strict subset of its 0.2600 parent; the 6,436
parent-only pixels all sit within 2 px of the mapped catalogue; the reference's nearest catalogue
distance is 2.236 px. Inverting the metric on that nested pair gives implied truth
**14,088.75 px** (rounding band 13,952.96–14,226.07) = 0.3067 % of the eligible footprint and
0.27265 % of the sample footprint, i.e. **|G| ≈ 14.1k px**, and a credit of **T = 5,223.1 px** for
the 0.2778 file. For reference: beating 0.3195 needs T ≥ 6,007.2 px at S = 37,654, or T ≥ 4,240.1
if the same credit were carried by 10,000 pixels. These are reconstructions from two
owner-reported scores, not measurements of any submission's internals.

**The shipped file.** 17,707 dots, 200 m catalogue collar, 3 px minimum separation, out-of-fold
over the whole footprint (each quadrant placed from its own fold). Not-the-union check (same dot
count, same code path): Jaccard against `max(A,B)` = **0.0121**, rank correlation of the field
with `max(A,B)` = **0.0321**, 0 dots in common with the single-view B placement, 909 with A. The
emission is therefore *not* a rescaled union of the two views — but it is also not what the lane
called for: only **499 of 17,707** dots fall in the strict A-only stratum (A in its confident tail
while B abstains), out of 11,233 such pixels in the placement domain. The rest are stratum 0.

## Findings

1. **The mandated disagreement field is worse than a random placement at every rung** on this
   instrument, and so is the strict A-only stratum mask. Both are far below the single-view B
   control. The lane's discovery signal does not survive its own hide-and-recover test.
2. **`rank(A) − rank(B)` is not the A-only stratum.** The rank difference is maximised where B is
   *low*, not where A is confident; 97 % of the shipped dots are stratum 0 (silent) pixels. The
   family has been calling this emission "disagreement" while it is largely surface-view
   abstention. This is an operationalisation gap worth remembering for every earlier round with
   the same code path.
3. **Prevalence, not geology, sets the right support size.** A detector tuned on a 1.16 %-dense
   truth field is tuned too high for a 0.27 %-dense board; the same field with the same credit
   carried by fewer, better-placed dots converts the 0.2-per-pixel tax into score.
4. **The uniqueness picture separates two questions.** Decoded-pattern uniqueness passes (not a
   copy, not a union, novel fraction 0.229). Directed dot proximity fails, against our own
   H61-family candidate (0.969) and against the scored lattice probe (1.000). The H75 card shows
   the same pattern (0.922), so this is a property of dense 3 px dot emissions in this registry,
   not of this round — but it is reported, not waived.

## Limits

* The instrument hides *catalogue* faults and the board scores *uncatalogued* ones; R4 measured
  Spearman ≈ −0.10 between them. Nothing here is a board prediction.
* 37,654 / 40,199 / 44,090 / 17,707 are pixel budgets in a 100 m grid; the collar, spacing and
  kernel radius are conventions, not surveyed facts.
* The prevalence correction is a proportionality argument for a self-similar field. The bracket
  spans 4.2× (0.112–0.294 %), so the corrected budget spans roughly 25k–9.4k dots.
* No geologist verified any emitted structure; no field observation was collected. The reasoning
  CSV is a template (interpretation + named non-fault mimic + falsifier), not an interpretation.
* The registry used for the lane and uniqueness gates is the 146 aligned rasters still on disk;
  the 545-raster `work/h61/priors` inventory used by the H61/H75 cards is gone, so the gate's
  scope is narrower than in those rounds. This is stated in the run card.

## Next steps, ranked

1. **Re-run the budget ladder on a prevalence-thinned instrument** (thin the held truth to
   0.2–0.3 % with whole components, keeping the placement domain) and re-select the support size
   on the *corrected* prevalence instead of dividing an instrument optimum. Needs no new data —
   `data/labels.tif` and the existing folds are enough.
2. **Fix the operationalisation**: emit the strict A-only stratum (or a cover-gated variant) as the
   candidate field and re-run the same ladder; the H92 ladder already shows this arm is the better
   of the two, but it still must clear `random` *and* `single_B` before promotion.
3. **Tilt-depth / theta map on the GeoDAWN magnetics currently on disk**
   (<https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and>,
   <https://doi.org/10.5066/P93LGLVQ>; already downloaded, public domain) — the top-ranked
   untried hypothesis in `knowledge/80`. It is obtainable: the files are in `data/external/`.
4. **GDR geothermal-play fairway + USGS Quaternary fault density** as a prior map: the INGENIOUS
   dataset at <https://gdr.openei.org/submissions/1391> is CC BY 4.0 but `gdr.openei.org` is **not
   reachable from this sandbox** (measured in H85) — do not propose it as viable until a mirror is
   confirmed reachable.
5. **Do not repeat**: independence screens, plain pseudo-label exchange, the five H77 detectors,
   the H86-E Euler SI, the H84 harmonic variogram, the H82 VSA channel — all measured negative on
   this instrument.

## Note on regenerated receipts

Running the shared template (`run_h61.stage_fit` / `stage_exchange`, invoked by the H92 ladder and
emit stages because `work/h61` had no checkpoints) rewrites `evidence/h61_independence.json`,
`evidence/h61_pseudo_exchange.json` and `evidence/h61_fit_checkpoint.json` with freshly refit
values that differ in the third decimal (`pseudo_exchange` spearman 0.133065 → 0.133685). Those
committed H61 receipts were restored to their historical state; the numbers H92 actually used are
recorded in `evidence/h92_ladder.json`, `evidence/h92_audit.json` and the H92 run card.

