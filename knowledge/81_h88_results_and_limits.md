# 81 · H88 results and limits (2026-10-10)

Pre-registration: `knowledge/80_h88_preregistered.md`. Runner: `scripts/run_h88.py` (holdout, write). Shared gate:
`scripts/run_h85.py::gate_candidate` (moved out of H85 unchanged; H85 write re-run reproduced its raster byte-for-byte).
Independent check: `scripts/verify_h88.py` → `evidence/h88_independent_verify.json`.

## Verdict

**NEGATIVE, pre-registered rule.** DOWNLOAD YES (format-valid, decoded-unique). SUBMIT NO. Experiments used: 1 of 3.
Slots used: 0. Organiser receipts: 0.

## Numbers (all HOLDOUT-DTI, evaluator `gems52-pooled-hide-v1`, 53,186 withheld positive px, 4 folds, 1,000 paired draws, seed 61052)

| arm | HOLDOUT-DTI | 95% CI |
|---|---:|---|
| H88 basement-step coherence (candidate) | 0.048050 | [0.032189, 0.064477] |
| random, same placement (control) | 0.080426 | [0.070223, 0.090973] |
| gradient magnitude only | 0.047641 | [0.031543, 0.064464] |
| raw depth-to-basement | 0.037456 | [0.025136, 0.050826] |
| candidate top-k without spacing | 0.007335 | [0.001450, 0.015109] |

* Paired, candidate minus random: **−0.032376**, 95% CI **[−0.046704, −0.016764]**.
* Per fold, candidate vs random: 0.0168 vs 0.0439; 0.0378 vs 0.0734; 0.0822 vs 0.1618; 0.1168 vs 0.1189.
  All four folds are below random; fold 3 is closest (0.1168 vs 0.1189). Consistent sign, not one bad fold.
* Leakage canary: max single-channel AUC 0.5657 (candidate), 0.5668 (gradient), 0.5291 (raw). Bar 0.90. No alarm.
* Instrument check: random arm 0.080426 reproduces the H82 receipt to 3.5e-7 (tolerance 1e-3). PASS.
* Band-15 stats (from the file, as stored): min −14.84, max 7135.3, median 316.4; gradient p99 90.2; mean coherence 0.912.
  No NaN or nodata inside the footprint.

## Why it failed (what the numbers say, not a story)

* Placement is worth most: the same field at top-k without spacing drops to 0.0073 from 0.0481. The 3 px selector is
  doing the work, as H85 found.
* The coherence term adds nothing: gradient-only is 0.0476 against 0.0481. The "line-like step" part of the signature
  is not separating held-out truth from the allowed set.
* The raw depth-to-basement layer is also below random (0.0375). Cover thickness, in this stack, is not a signal that
  places held-out faults ahead of chance.

## Limits

* Holdout hides catalogue faults; the competition scores new faults. A negative here is evidence against this field
  on the catalogue proxy, not a measured board score.
* The output container writes 0.0 outside the footprint (every pixel finite, in [0, 1]). The organiser's page says
  "null or nan" outside the bounds. Organiser behaviour for this container is unverified (IR-H85-004, IR-H88-008).
* Lane: surface PASS; dots literal rule DUPLICATE against a universal-coverage probe raster that random dots also match
  (0.9991). Excluding probes: 0.3322 (bar 0.70). The literal rule is not waived.
* Uniqueness: 146 local priors (decoded pixels), max Jaccard 0.0119, novel fraction 0.6603, not identical to a prior.
  Scope: local rasters only, not the 567-blob census.
* Feature store rebuilt, not restored (IR-H88-007).

## What would change the verdict

Only a new pre-registered primary that beats 0.189200 on this instrument (H82 B_DVA2), with the random control
reproduced and a paired lower bound above zero. Post-hoc tuning of the coherence scale or the layer after this negative
result would be a new hypothesis with a forking-paths cost, and is not done here.
