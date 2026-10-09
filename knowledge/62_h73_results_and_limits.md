# 60 · H73 — results, walls, irregularities, and the next hypotheses (2026-10-09)

**Verdict: NEGATIVE at the lane gate. No H73 file was emitted. Competition slots used: 0.**
Preregistered in [`knowledge/61`](61_hypotheses_H73_preregistered.md), amended before any holdout arm or shipped
placement in [`knowledge/61a`](61a_h73_preregistration_amendment_quota_placement.md). Runner:
[`scripts/run_h73.py`](../scripts/run_h73.py). Experiments used: **1 of 3**. Wall clock: ~1 h 30 min.

Labels: **HOLDOUT-DTI** = instrument reading (evaluator `gems52-pooled-hide-v1`, withheld positives and 95 % CI given);
**MEASURED** = a receipt value; **ORGANIZER-CONFIRMED** = nothing in this document (no organiser receipt exists here).

## 0 · Identifier rename (read first)

This round was first frozen as **H72**. A parallel session had already merged a different H72 round to `main`
(strain-only View A × surface B, with the same file names). Per the repository's identifier-only rename practice
(README, H71 note), this round is **H73**. The rename changed labels only: the preregistered hypothesis text, the
amendment text and every measured number are the same. The preregistration was re-pinned after the rename, and the old
and new hashes are recorded in `registry/h73_preregistration.json` (`renamed_from`). Anyone auditing the pin should
compare the content, not the file name.

## 1 · What was tested

Hypothesis H73-B: a surface-only (View B) ranking, emitted under the brief's lane rule, keeps ≥ 90 % of the
unconstrained `single_B` holdout DTI. View A is not used; no co-training; no pseudo-labels.

## 2 · Measurements, each labelled

| Step | Label | Result | Receipt |
|---|---|---|---|
| Restore of 23 competition inputs (SHA-256 + byte pins) | MEASURED | 23/23 match | `data/restore_receipt.json` |
| Test suite before this round's code | MEASURED | 416 passed, 1 skipped | `pytest` (run in `/home/user/.venv-gems`) |
| Feature store rebuilt + external layers | MEASURED | built in ~3 min; 19-band template matches | `work/r2/features` (ignored) |
| Canary: each View-B feature alone, held-out region | MEASURED (leakage canary) | max direction-insensitive AUC 0.6689 (fold 1); alarm at 0.90 → **no alarm** | `evidence/h73_fit.json` |
| View-B out-of-quadrant AUC per fold | MEASURED | 0.6625 / 0.7684 / 0.6112 / 0.6952 | `evidence/h73_fit.json` |
| Census re-materialised (526 blobs) | MEASURED | 524/524 eligible file-SHA match, shapes and CRS match, 0 errors | `work/h61/prior_fetch_receipt.json` |
| Registry used by the lane gate | MEASURED | 560 rasters (524 census + 36 local); 2 ineligible census entries skipped; 181 decoded duplicates; 14 universal-coverage probes; **350 informative distinct** | `evidence/h73_consensus.json` |
| **Plain greedy under the consensus pool (preregistered construction)** | MEASURED | best worst-prior near-dot share **0.8916 at T = 150**; unrestricted 0.9377; **no T reaches 0.70** | `evidence/h73_choose_plain_greedy_wall.json` |
| **Amended quota placement (61a), 6 thresholds** | MEASURED | all six fail. T=200 0.7382; T=150 0.7340; T=100 0.7317; T=80 0.7268; T=60 0.7223; T=40 0.7043 (short fill: 37,372 of 37,600 dots) | `evidence/h73_choose.json` |
| **Instrument control: `single_B` at 9,400 dots/fold** | HOLDOUT-DTI, n = 53,186 withheld positives, evaluator `gems52-pooled-hide-v1` | **0.174571**, 95 % CI [0.152313, 0.196302]; committed H71 receipt 0.174571 → \|Δ\| = 3.6e-07 → **reproduces** | `evidence/h73_control.json` |
| Control: `random` at 9,400 dots/fold | HOLDOUT-DTI, same withheld set | 0.080426, 95 % CI [0.070223, 0.090973] (H64 random arm 0.080426, as cited in H69) | `evidence/h73_control.json` |
| Control paired difference `single_B` − `random` | HOLDOUT-DTI | +0.094146, 95 % CI [0.073841, 0.114562] | `evidence/h73_control.json` |
| Candidate `H73_B_lane` holdout | **not measured** | the preregistered holdout stage refuses to run without a lane-feasible T (by design) | — |
| Shipped H73 file | **not emitted** | no lane-feasible threshold → nothing written; no SHA, no validator, no name/note | — |

**Reading the walls.** The shipped surface view ranks dots that cluster on the same few dense priors. Greedy placement
therefore puts ≈ 90 % of its dots within 3 px of one registry raster. Restricting the pool by consensus moves that only
to ≈ 0.89. Per-prior quotas (H69's rule) push the worst share to ≈ 0.72–0.73, but they also exhaust the candidate
pool, so the fill comes up short (e.g. 35,654 of 37,600 at T = 200). The near-dot share divides by the **placed**
count, so a short fill inflates it. This is the same denominator effect H69 documented (its "pinned near 0.745"),
and it is why quotas alone cannot reach 0.70 on this registry at this budget. H69 reached 0.6985 with a *different*
registry (555 priors counting duplicates) and a 2.74 M px pool; the two results are not directly comparable and the
difference is recorded as an open question, not explained.

## 3 · What this round does and does not say

* **Says:** a surface-only emission at 37,600 dots cannot be made lane-feasible on this 350-prior distinct registry
  with the two placement rules this repository has used. The lane rule, not the holdout, is the binding constraint.
* **Says:** the instrument is trustworthy in this fresh sandbox (control reproduces to 3.6e-07).
* **Does not say:** that a surface view cannot score. The holdout control `single_B` at 0.1746 is the best arm this
  family has measured, but it cannot be shipped under the lane rule.
* **Does not say:** anything about the public board. Scores (0.3774, 0.3195, 0.2778, …) are PUBLIC-PAGE or
  OWNER-REPORTED. See §5.

## 4 · Next hypotheses (ranked by expected holdout gain per unit cost; none validated this round)

These were checked against the repository by grep (`variogram`, `antithetic`, `deflection`, `flow_dir` return no
implementation in `src/` or `scripts/`) and against the access test below. Ranking follows the criterion in
`knowledge/51` §3 (how slowly the marginal credit density decays with budget).

1. **Directional variogram anisotropy on bands 12, 19 and the LiDAR scarp product** (the repo's H67-C). A damage zone
   300–900 m wide is matched to the 300 m kernel, and a semivariance statistic is not a gradient, Laplacian, Hessian
   or structure-tensor channel. *Not* catalogue-derived: it is computed from the continuous field, so it is off
   catalogue by construction. Free sources already mirrored and SHA-pinned: `data/training_features.tif` bands 12
   and 19, `data/external/lidar_scarp_features_u8.tif`. Cost: medium-high. Obtainable here: **yes**. Validate first
   on the holdout against `single_B`; it must not be lane-tested before that.
2. **Antithetic paired-margin asymmetry from band 15** (the repo's H67-B). Half-graben asymmetry means the gently dipping
   margin is systematically under-mapped, which is a *population* of faults, not scattered points. Cost: medium.
   Obtainable: **yes**.
3. **Lane-aware placement that fixes the denominator, not the field.** Enforce the per-prior quota against the
   *target* budget and use spacing-aware tie-breaking so the fill cannot fall short. This does not add geology; it is
   a placement fix that the measurements above show is needed before *any* holdout-positive candidate can ship. Cost:
   low. Expected gain: only realised if a candidate beats `single_B`. Recommended to run alongside 1 or 2.
4. **1 m-DEM-derived scarp product at native resolution.** The one lever that could reduce the aliasing of a scarp at
   100 m. Official source: USGS 3D Elevation Program, free and public domain
   (<https://www.usgs.gov/3d-elevation-program>, checked 2026-10-09; the page states "All 3DEP products are available
   free of charge and without use restrictions"). **Obtainable here: no.** A direct fetch of the USGS data host fails
   from this sandbox (HTTP 000), and the competition's own tile list `1m_DEM_links.csv` sits behind the DrivenData login
   (<https://www.drivendata.org/competitions/306/competition-doe-gems/data/>). Needs an unrestricted machine.
5. **Drainage-deflection corridors** (H67-D). Classic covered-fault criterion in Basin and Range piedmonts, but needs a
   D8 network from the 1 m DEM. Blocked by the same data gap as 4. Cost: high.
6. **Seismicity-ridge coincidence** (H67-E). Cheapest, lowest expected gain: bands 10 and 16 are 100 km smoothings,
   coarser than the 300 m kernel.

## 5 · Irregularities flagged for review (each has a receipt or a link)

* **IR-H73-001 — the portal's NaN rule vs. the repo's zeros.** The official page says the submitted GeoTIFF's values are
  between 0 and 1 and that "data outside the bounds is null or nan"
  (<https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>). The repository writes **0** outside
  the footprint; the official template `data/sample_submission.tif` writes NaN outside (7,111,787 px). The 0.2778
  reference `data/reference/h33-2-b2-zeros.tif` (owner-reported as scored) also writes zeros, with no NaN. The metric is unaffected (zero
  pixels contribute nothing), so this is a format question for the organiser, not a score question. **Not confirmed
  by the portal.**
* **IR-H73-002 — the leaderboard could not be verified.** The DrivenData leaderboard page renders client-side and
  returned "Loading..." to the fetch tool. The 0.3774 top score, the 0.3195 and 0.2778 values are therefore
  **PUBLIC-PAGE or OWNER-REPORTED** in this repository. Per-file attribution (which file produced which score) is
  filename-only and owner-reported (see `knowledge/49`).
* **IR-H73-003 — one submission per team.** The official page says competitors "must choose a **single** submission"
  across both prize rounds, and each team submits "one GeoTIFF per user/team"
  (<https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>). The repository's 60-plus
  submission-named files are research artefacts; only one may be chosen for scoring. **Decision for the user.**
* **IR-H73-004 — registry count differs from earlier rounds.** This round's lane registry is 560 rasters (350
  informative distinct); H69 cites 566 and 555. Different census receipts; not reconciled.
* **IR-H73-005 — the withheld-positive count differs from H69 for the same evaluator.** H73 control: 53,186; H69 cites
  60,894. Not explained by this round; flagged rather than adjusted.
* **IR-H73-006 — the preregistered T grid was reduced** from 12 values to 6 by amendment 61a, before any holdout or
  shipped placement. Documented; the reduced grid was fixed before the quota run.
* **IR-H73-007 — a runner defect found and fixed in this round:** `choose` read thresholds from the H61 registry
  (no `consensus_T_grid` key) and was re-pointed at the H73 preregistration. The fit stage ran before that fix; its
  canary and lane thresholds are numerically identical (0.90, 0.95), so its receipt is unaffected.
* **IR-H73-008 — an out-of-memory kill** in the first `choose` attempt (350 dense prior masks ≈ 4 GB). Fixed by sparse
  support coordinates; no result from the killed run was used.
* **IR-H73-009 — census `sha256` column is file bytes**, not decoded bands (receipt field `sha_column_reading`). The
  decoded-SHA column in the receipt is therefore 0 matches by design; the file-SHA column is the verified one (524/524).
* **IR-H73-010 — the H69 holdout does not reproduce today.** H69's receipt gives `single_B` = 0.137947 and `random` =
  0.072032; this round's control gives `single_B` = 0.174571 (reproduces H71 to 3.6e-07) and `random` = 0.080426 (reproduces
  H64). H69 says its View-B channel set changed, which would explain the gap, but the change is not in this round's
  receipts. Cross-round holdout comparisons that use H69's `single_B` are declared differences, not reproductions.
* **IR-H73-011 — the H69 file fails the literal lane rule, so it is not cleared for download as a submission file.**
  Audit (`evidence/h73_audit_h69_file.json`): the literal rule returns **DUPLICATE/STOP** with max near-dot share 1.0 on
  14 probe priors. Each of those priors covers 99.9–100 % of the eligible footprint within 3 px (`probe_coverage`), so
  every dot is "within 3 px" of them. The informative-prior policy (528 informative priors) returns PASS at max 0.6985.
  The run's own rule states that a policy PASS never waives a literal duplicate/STOP (`scripts/run_h73.py` docstring;
  AGENTS.md, H73 section). The verdict is therefore **DOWNLOAD NO** (research copy only). The earlier H69 verdict
  (DOWNLOAD YES) is superseded. Max Jaccard with the priors is 0.0092: 542 priors are byte-distinct and 378 are
  decoded-distinct.

## 6 · Reproduce

```
python3 scripts/restore_data.py --target-dir data        # 23/23 pins
PYTHONPATH=src python -c "from gems52 import structural; structural.build(dest='work/r2/features', include_optional_profiles=False)"
PYTHONPATH=src python -m gems52.external
python scripts/fetch_prior_inventory.py                  # census, 526 blobs, ~20 min
python scripts/run_h73.py fit && python scripts/run_h73.py consensus && python scripts/run_h73.py choose
python scripts/run_h73.py control                        # the instrument check that reproduces 0.174571
```
