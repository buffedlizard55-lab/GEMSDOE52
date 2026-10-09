# 59 · H73 — preregistration (frozen before any H73 fit)

Status: **preregistered 2026-10-09 (session H73), before any H73 model fit or placement.**
Pinned in `registry/h73_preregistration.json`; `scripts/run_h73.py` refuses to run if this file's
SHA-256 moves. Experiment budget: this is **1 of 3** (the protocol's cap of 3 experiments / 2 hours).

## Why this round exists (the gap it fills)

* Every co-training round in this repository (H55–H71) has failed to beat the **single-view
  surface baseline `single_B`** on the hide-and-recover holdout (H71 control: `single_B` = 0.174571 at
  9,400 dots/fold, reproduced within 5.4e-05 of H61). The strongest measured arm in the family is
  therefore the one-view surface ranking, not any two-view combination.
* No round has tested whether that strongest arm can be **emitted under the lane rule**
  (max informative near-dot share ≤ 0.70 and surface Spearman ≤ 0.90 against every registry raster).
  H69 satisfied the lane rule only for a co-training field; H71 failed it. A lane-compliant surface
  emission is the cheapest unique file that can be shipped at a holdout level the family has measured.

## Hypothesis H73-B

**Surface-only (View B) ranking, emitted under the lane rule, keeps at least 90 % of the unconstrained
`single_B` holdout DTI on the same folds, budget and evaluator, and passes the policy lane.**

* **Layers:** View B only — the surface view of `structural.FeatureStore` as defined by
  `run_h61.setup()` (radiometric total count, K/Th/U and ratio channels, DEM-derived channels;
  band 6 = radiometric total count, IR-H61-008). View A is **not used**. No pseudo-labels, no exchange.
* **Physical signature targeted:** surface alteration and permeability contrast adjacent to
  buried-or-mapped fault traces, read through the B-view learner's out-of-fold rank (percentile of the
  held-out fold's OOF probability over the allowed domain).
* **Why it could find faults missing from the USGS/INGENIOUS catalogue:** the B-view is trained only on
  the visible (non-withheld) catalogue, so its ranking is evaluated on withheld segments it never saw.
  This is the holdout's own test, not an argument from the catalogue.
* **How it differs from anything already in the repository:** it is the H61 View-B learner with no
  View-A conditioning and no disagreement term, emitted through a **consensus-restricted pool**
  (below) that no single-view round has used.

### Lane construction (fixed here)

1. **Informative priors** = registry rasters whose measured 3 px coverage of the eligible footprint is
   below 0.95 (the universal-coverage probe threshold, IR-H61-series). Probes are reported, not deleted.
2. **Consensus** c(x) = number of distinct informative prior decoded patterns whose 3 px halo covers x.
3. **Pool** = {x ∈ legal footprint : c(x) ≤ T}. T is searched from the loosest end (largest T first) and
   the **largest feasible T** is kept: the first T at which a greedy `nodes.spacing_select` fill of the full
   budget has max informative near-dot share ≤ 0.70.
4. The shipped field is the stitched per-fold B rank restricted to the pool; emission uses the same
   3 px hard-core greedy as every other arm.

## Measurement plan (all labelled)

* **HOLDOUT-DTI** via `gems52.evaluate_holdout` (`gems52-pooled-hide-v1`), 4 folds, 9,400 dots per fold per arm,
  pooled over folds, 1,000 paired draws on 20 km blocks. Arms: `single_B` (control),
  `H73_B_lane` (candidate: `single_B` restricted to the pool), `random` (control).
  Paired Δ = candidate − `single_B` with its 95 % CI.
* **Control reproduction:** `single_B` must reproduce the H71 receipt value 0.174571 within 0.001
  (same features, seed, splitter). A failed reproduction voids the round's comparison, not just the number.
* **Canary:** the B feature set alone must score out-of-quadrant AUC below 0.90 (leakage alarm).
* **Lane (authoritative):** `gates.lane_report` in phase `dots` against every census prior
  (`evidence/ctd5_prior_inventory.json` restored by `scripts/fetch_prior_inventory.py`), literal and policy;
  and phase `surface` for the Spearman ≤ 0.90 check.
* **Uniqueness:** `gates.uniqueness_report` (decoded pixels) against every census prior and every local
  artefact; the candidate's own byte-copies are excluded and listed.
* **Format:** `gates.format_report` (float32, EPSG:32611, 3,730 × 3,292, transform pinned,
  values in [0,1], no NaN inside the footprint; zeros outside the footprint, as in the scored
  reference `data/reference/h33-2-b2-zeros.tif`).

## Verdict rule (decided now)

* **Negative** if the control does not reproduce, or if the candidate fails the lane policy.
* **Promote-eligible** only if: control reproduces; lane **policy** PASS on final dots and surface
  Spearman ≤ 0.90; uniqueness PASS; candidate DTI ≥ 0.90 × `single_B` DTI on the same folds; candidate
  DTI > `random` with a paired CI above zero.
* **Not a slot decision.** Promote-eligible means "may be considered for the selector step"; it does not
  spend a competition slot. Slots used by this round: **0**.

## Named non-fault mimics (declared before the run)

* **Lithology / soil cover:** playa, alluvium and fan deposits raise K/Th/TC independently of faults.
  A surface-only learner trained on fault-adjacent radiometrics can rank these high. Test: the holdout
  itself (a non-fault mimic lowers the withheld-segment DTI).
* **Erosion lines and roads:** linear surface features with high radiometric contrast along drainages
  or road cuts. Not separately testable here (no roads layer reachable from the sandbox egress
  allowlist, see `knowledge/04_free_data_and_licenses.md`); flagged as an unmeasured confound.

## What this round cannot show

* It cannot show that the candidate beats the public leaderboard. HOLDOUT-DTI is an instrument reading,
  never a forecast (`knowledge/10` §5 measured Spearman −0.10 against the owner-reported board).
* Board scores (0.3774, 0.3195, 0.2778, ...) are public-page or owner-reported values and are not
  ORGANIZER-CONFIRMED anywhere in this repository.
