# 80 · H88 preregistration — co-training with a disagreement-gated A-only stratum (frozen before any holdout fit)

Frozen **before** `scripts/run_h88_holdout.py` is executed. The runner refuses to start if this file's
SHA-256 differs from the value pinned in `registry/h88_preregistration.json`.

## 0 · Why this round exists (what it must add that the repository does not already have)

* 87 rounds in this repository have run the co-training lane. The repository's own record (AGENTS.md, knowledge/78,
  knowledge/76) says: View A **sufficiency** has failed eight times on the mandated fitted instrument; independence
  passes; plain pseudo-label exchange lowers A's out-of-fold AUC; the best holdout arm on the shared instrument is
  H84 `B_DVA2` **0.192829** [0.170789, 0.213691] (`evidence/h84_holdout.json`), with random at **0.080426**.
* **H87 (`submission/gems52-h87-cotrain-wavelength-thk-37654px-20261010T213656Z.tif`) has never been holdout-scored.**
  Its own receipt says `HOLDOUT-DTI (not yet run)`. Its emission is a *continuous* ranking of `(A − B)·gate`, not the
  "A confident and B abstains" pseudo-label rule its docstring names. H88 measures that gap rather than assuming it.
* H88 tests the protocol's literal rule: **emit only from the stratum where A is confident and B abstains**,
  then compares that stratum against the single-view baselines on hide-and-recover folds. A co-training method
  that does not beat its own single-view baseline has donated nothing.

## 1 · Views (catalogue-free; computed once on the full eligible footprint)

Eligible footprint = all-19-band finite pixels AND the organiser domain (`data/sample_submission.tif` finite mask),
the same definition as `scripts/run_h86_holdout.py` (IR-52-002).

* **View A (subsurface / potential field / strain):** `build_h87_cotrain_wavelength.compute_view_a`, imported, not
  forked. Bands by the file's own tags: 5 `iso_grav_anom_slope`, 11 `iso_grav_anom_vg`, 18 `iso_grav_anom_hg`,
  3 `tmi_hg`, 9 `tmi_vg`, 4 `geod_2ndinv`, 7 `geod_shearrate`, 15 `depth_to_base_surf`, 17 `cond_surf`.
* **View B (surface):** `build_h87_cotrain_wavelength.compute_view_b`, imported. DEM bands 12 `det_elev`,
  19 `det_elev_slope` (training_features), plus GeoDAWN `ThK` (external `geodawn_extensions_u8` band 1) and
  GeoDAWN `U` (external `geodawn_rad_u8` band 3). *Declared deviation:* `training_features.tif` carries **no**
  band tagged radiometric (see IR-H88-001); the radiometric terms therefore come from the external GeoDAWN layers.
* Rank normalisation `rA = rank01(view_A, eligible)`, `rB = rank01(view_B, eligible)` (ranks over the whole eligible
  footprint, so the same ranks serve every fold; ranks never see the catalogue).

## 2 · Strata (pre-registered thresholds, not tuned)

* `S_AB` = eligible & (rA ≥ 0.75) & (rB ≤ 0.25) — **A confident, B abstains** (buried-fault hypothesis, measured here).
* `S_BA` = eligible & (rB ≥ 0.75) & (rA ≤ 0.25) — **B confident, A abstains** (surface-artefact control; NOT a candidate).

## 3 · Arms (identical folds, identical allowed sets, identical budget)

| arm | field used for spaced placement | role |
|---|---|---|
| `P_strict_cotrain` | `rA + 1.0·S_AB` | **PRIMARY** — co-training as the protocol states it |
| `h87_asbuilt` | `build_h87…compute_disagreement_field(view_A, view_B, eligible, cat)` | the shipped H87 rule, measured for the first time |
| `single_A` | `rA` | single-view baseline (View A alone) |
| `single_B` | `rB` | single-view baseline (View B alone) — the co-training donation test |
| `S_BA_control` | `rB + 1.0·S_BA` | tests the "B-confident = surface artefact" suspicion; never shipped |
| `random` | uniform over allowed, seed `88001 + fold` | floor |

Placement: `gems52.nodes.spacing_select(field, allowed, K, min_px=3.0)` with **K = 9,400 dots per fold**.
Allowed set per fold = `region & eligible & ~visible & (distance to visible catalogue > 2 px)`, identical to H86.

Scoring: `gems52.evaluate_holdout.evaluate` (evaluator `gems52-pooled-hide-v1`, α 0.2, β 0.8, 300 m triangular kernel,
200 px blocks), pooled over folds, `pooled_summary(draws=1000, seed=88001, candidate='P_strict_cotrain')`. Every
number produced is labelled **HOLDOUT-DTI** with its 95 % CI and withheld-positive count.

## 4 · Gates that run before any verdict

1. **Leakage canary.** Each feature alone (`rA`, `rB`, the `P` score, the `h87` field) scored as AUC against held-out
   truth inside the allowed set. Alarm if **AUC > 0.90**; an alarm voids the round.
2. **Independence proxy (Blum–Mitchell).** `gems52.spatial.negative_block_errors(rA, rB, negatives, fold,
   thresholds=(q75(rA), q75(rB)))` on held-out labelled negatives (`region & eligible & ~truth`), then
   `spatial.independence(rows, threshold=0.60)`. **Caveat, stated now:** the two scores are unsupervised, so their
   "errors" are the score values on negatives; this is a proxy for conditional independence, not the fitted
   OOF-error test the repository used in earlier rounds.
3. **View sufficiency proxy.** Canary AUCs of `rA` and `rB` against held-out truth are reported as the unsupervised
   sufficiency reading. No fitted classifier is trained in this round.

## 5 · Decision rule (fixed now)

* If the canary alarms, or independence measures max |ρ| ≥ 0.60 (abandon co-training), the round is **NEGATIVE** and no
  file is promoted.
* **POSITIVE (promotion-eligible, still not a submission)** iff all hold:
  (a) `P_strict_cotrain` HOLDOUT-DTI ≥ **0.192829** (the best measured arm on this instrument);
  (b) paired CI of `P` − `single_B` has lower bound > 0 (co-training beats its own surface-only view);
  (c) paired CI of `P` − `random` has lower bound > 0.
* Otherwise **NEGATIVE**. The file is still written so that it can be downloaded and audited, but the site must say
  **SUBMIT NO**.
* The `h87_asbuilt` arm is reported as a measured comparison only. It cannot be promoted post hoc because it was not the
  pre-registered primary.

## 6 · Shipped artefact (written only after the holdout is final)

* Full-footprint version of the **primary** rule: `P` score, top **37,654** dots, 3 px spacing (`nodes.spacing_select`),
  200 m collar on the full catalogue (2 px), zero outside, float32 `{0,1}`, EPSG:32611, 3730 × 3292, Affine transform
  matching `data/sample_submission.tif`.
* Filename: `gems52-h88-cotrain-strict-AB-37654px-<UTC>.tif`. Name: `h88-cotrain-strict-AB-37654px`.
* Note (≤140 chars): `H88 co-train A-conf/B-abstain stratum, 3px spacing, 200m collar, zeros outside; holdout-gated`.
* Uniqueness: `scripts/audit_uniqueness.py` over all accessible priors (the 524-blob census restored through
  `scripts/fetch_prior_inventory.py`, plus local submission/docs/data globs). The candidate's own byte-identical copies
  are excluded by name (IR-H85-001). Surface and dot lane checks are run on the final dots (protocol §1).

## 7 · Budget (protocol §6)

* Experiments: **1 of 3** (this holdout run). Reserved: 2 (no re-run is planned).
* Slots: **0**. No competition upload is made by this round.
* Wall-clock budget: 2 h from the first holdout fit.
