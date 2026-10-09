# 35 — H65 results and limits (2026-10-09)

**Verdict: NEGATIVE at the premise gate. H65 is not promoted.** H65-A (cross-strike, regionally
detrended basement and gravity offsets as View A) has no out-of-quadrant signal above the premise
threshold. No holdout arm was run, no GeoTIFF was emitted, and no competition slot was used.

Frozen protocol: `knowledge/41_hypotheses_H65_preregistered.md`, SHA-256
`4d9d559fe6e4b42cffef206d366ccf785b1eda2146a686be98e376a1352bef71`, pinned in
`registry/h65_preregistration.json`. Source-claim correction (dated, does not edit the frozen file):
`knowledge/41a_amendment_2026-10-09_H65_sources.md`.

Experiment budget: 3. Used: E1 operator audit, E2 premise. Not authorised: E3 holdout arm
(it needs the premise gate to pass first).

## Labels used below

* **PREMISE-AUC** — internal out-of-quadrant AUC of a fitted H65-A model on the label-blind
  quadrant folds (buffer 80 px). This is not HOLDOUT-DTI. Nothing here is ORGANIZER-CONFIRMED.
* **HOLDOUT-DTI** — **not produced**. The premise gate failed before the hide-and-recover arm.
* **SYNTHETIC** — operator check on a generated grid, not on survey data.

## E1 — H60-3 operator audit (SYNTHETIC)

Receipt: `evidence/h65_operator_audit.json` (script `scripts/h65_operator_audit.py`).

* Grid 400×400 px at 100 m; basement step of 200 m across a NNE (15°) trace.
* H60-3 operator (`src/gems52/h60.py`: `d1 + d2 − 2·arr` with shifts along strike): on-trace mean
  2.96e-05. Far-field mean 1.0e-09.
* H65-A cross-strike symmetric difference, d = 3 px: on-trace mean 1.970. d = 6 px: 2.000.
* Ratio H60-3 on-trace / cross-strike d = 3 px = **1.50e-05**.
* A pure ramp (no step) gives a near-zero response, so the residual is discretisation of the step.

**Consequence.** H60-3 does not detect a step across a strike-parallel trace. It is logged as
IR-H65-001. H60 outputs are not edited here. Any H60 result that uses `b15_step_*` as a feature
should be treated as unverified until re-run.

## E2 — H65-A premise (PREMISE-AUC)

Receipt: `evidence/h65_premise.json` (runner `scripts/run_h65.py`, which refuses if the protocol hash moves).

Features: 8 layers `H65_b{15,13}_{nne,nw}_d{3,6}` in `work/h65/feat/` (footprint 4,593,171 px, no NaN).
Each layer is |z(p+d·n) − z(p−d·n)| minus a 15 px detrend, on `raw_band_15` and `raw_band_13`,
normals NNE 15° and NW 315°, d ∈ {3, 6}, nearest-valid fill.

| fold | held-out region AUC | region positives | region negatives |
|---|---|---|---|
| 0 | 0.5325 | 27,309 | 1,941,302 |
| 1 | 0.5689 | 10,677 | 1,032,665 |
| 2 | 0.4706 | 6,813 | 393,204 |
| 3 | 0.5089 | 8,387 | 595,321 |

* Mean PREMISE-AUC **0.5202**; min fold **0.4706**.
* Gate: mean ≥ 0.60 **and** min fold ≥ 0.55. **premise_passed = False.**
* Controls, from the stored H61 receipt (`evidence/h61_fit_checkpoint.json`, not refitted):
  View A mean 0.5163, View B mean 0.6843. H65-A sits at View A's level, not View B's.

## Leakage canary (PREMISE-AUC inputs)

Receipt: `evidence/h65_canary.json`. Alarm threshold 0.90.

* Max single-feature raw AUC: **0.5904**.
* Max fitted top-5 held-out AUC: **0.5439**.
* Any alarm: **False**. No leakage flag.

## Uniqueness check on the existing H61 file (not a new submission)

Receipt: `evidence/h61_uniqueness_census_20261009.json` (script `scripts/audit_uniqueness.py`, census
`work/h61/prior_fetch_receipt.json`, 526 census entries; 530 priors after byte dedupe).

* Candidate `docs/downloads/h61-candidate.tif`, SHA-256 `7c86853164f9cfa7aea34de029c7d5ccf3a6b43dbbb2b14de570e558384d2755`.
* Surface phase (rank correlation): max Spearman **0.0342**, 0 offenders. **PASS.**
* Dots phase, literal rule: max near-dot **1.0000**, from the 13GEMSDOE lattice probe. **DUPLICATE/STOP.**
* Dots phase, repository policy (`gems52.gates.lane_report`, probes = 3 px coverage ≥ 0.95, 14 found):
  max near-dot **0.87875** against `work/h61/priors/4e50a598eae16b3c098ca2653542dc142f1da8a8.tif`;
  9 informative priors above 0.70. **DUPLICATE/STOP.**
* Jaccard overlap of binary support (>0) against the priors: max 0.0124. The directed 3 px dot test is what flags it, not overlap.

**Consequence for H61.** The one-click file is measured as a lane duplicate under both the literal
rule and the repository's policy. The download-for-research label on the site is kept as recorded
and is flagged as IR-H65-004. It must not be presented as a lane-valid unique submission.

## Leaderboard (PUBLIC BOARD, not ORGANIZER-CONFIRMED)

Live fetch 2026-10-09 (chunk 0 of 3): #1 xiaofanhu **0.3774**; #7 DARD **0.3195**; #13 extradr19 **0.2778**.
Source: https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/

The brief said 0.3195 is the highest score. It is not; the top is 0.3774 (IR-H65-002). The 0.2778 row
belongs to team extradr19; the repository's file attribution to `h33-2-b2` is owner-reported and not
linked to that row (IR-H65-003).

## What is still open

* **No unique, lane-valid GeoTIFF for submission exists in this round.** No candidate passed the premise gate,
  and the one existing file is a measured lane duplicate.
* **HOLDOUT-DTI** for H65 has not been measured. The hide-and-recover comparison against the single-view
  baseline was not run.
* **Source checks** in `knowledge/41` §4 are partly unverified (see `knowledge/41a`). Items 4–6 (DrivenData page 967,
  the masking thread, USGS GeoDAWN) were not opened.
* **Public-board 0.2778 to file link** still needs a submission-page receipt.
* **Portal error** "Predicted values must be in range [0, 1]" is not reproduced from the repository (IR-H65-007).
* **H65-B, C, D** are not tested (see §2 of the protocol). H65-C is blocked by data egress.

## Hypotheses generated (3–5 required; 4 written)

Ranked by expected DTI gain and implementation cost (protocol §2).

| rank | id | layers | status |
|---|---|---|---|
| 1 | H65-A | bands 15, 13 cross-strike offsets, detrended | **tested; premise failed** |
| 2 | H65-B | tilt-angle edge ridges, bands 9 and 3 | not tested; expected gain low (N-6 AUC ≈ 0.52; overlaps H61 View A) |
| 3 | H65-C | surface artefact veto (roads, erosion) | blocked (no roads/hydro data reachable) |
| 4 | H65-D | credit localisation by terrain stratum | deferred; does not itself produce a file |

## Run card

`evidence/h65_run_card.json`.
