# 97 · H102 — preregistration, frozen BEFORE any fit (2026-10-10)

Round identifier: **H102** (checked free on `origin/main` at commit `5b8c81c4` by `git grep -l "H102"`
over all `.md/.json/.py/.html` files; no match). Session branch `arena/1bc2f2ec-gemsdoe52`.
Lane: the standing brief's two-view co-training paragraph (Blum & Mitchell, COLT '98,
doi:10.1145/279943.279962). Pinned by `registry/h102_preregistration.json`; `scripts/run_h102.py`
refuses to start if this file's SHA-256 moves.

**Labels.** HOLDOUT-DTI = a reading of the shared evaluator `gems52-pooled-hide-v1` (hide-and-recover,
whole fault segments withheld with the 80 px buffer of `label-blind-quadrants-v2`, every
catalogue-derived feature computed from the fold's *visible* faults only, visible faults masked
pixel-exactly, pooled DTI at α 0.2 / β 0.8 / 300 m triangular kernel, 95 % paired CI by 1,000-draw
spatial-cluster bootstrap, seed 61052, 53,186 withheld positive px). ORGANIZER-CONFIRMED = nothing
this round (no submission-page receipts exist for any H102 number). OWNER-REPORTED and PUBLIC-BOARD =
cited only, never computed. A projection is never written as a score.

## 0 · Settled facts carried in (not re-litigated)

1. **View A sufficiency has failed nine times** (H84 mean out-of-quadrant AUC 0.5163, min fold
   0.4668; the gates are 0.60/0.55). It is re-measured here as the lane's bookkeeping obligation,
   and the round is designed so that **no arm's promotion depends on A being sufficient**: A enters
   only as a soft prior (E1) and as a capped stratum quota (E2), both of which degrade gracefully.
2. **Independence passes every time** (max |ρ| ≤ 0.14 over spatial-block OOF negative errors;
   abandon bar 0.60). Re-measured here on this round's own fits.
3. **Hard disagreement emission is below random** (H92 `disagreement_post` 0.0329 @ 37,654; H93
   A-only stratum 0.0353; H96 bidirectional 0.0725 vs random 0.0766). E2 therefore does NOT emit
   disagreement as the primary signal: it emits **consensus-first with a capped buried quota and a
   B-only veto** — disagreement is used as a *state machine* (which stratum a cell belongs to), not
   as a score.
4. **The holdout-best in-lane ranking is `B_DVA2`** (directional variogram anisotropy, H82 design):
   committed HOLDOUT-DTI 0.189200 (H82, 2026-10-09) and 0.192829 (H84 re-run, 2026-10-10; run-to-run
   jitter ≤ 3.6e-3, IR-H84-005). **The promotion bar for this round is 0.192829.**
5. **The board evidence** (knowledge/76, measured from 12 owner-reported files):
   Spearman(emitted mass, score) = −0.928; the champion `h33-h33-2-b2` (37,654 px, board 0.2778
   OWNER-REPORTED) is the d2-8 surface field with the ≤ 200 m catalogue ring deleted; the same credit
   at S ≈ 25,400 reaches 0.3195 (PUBLIC-BOARD #8 on 2026-10-10). H92's prevalence algebra puts the
   board-side budget at 17,707 (lower bound). E2's sub-halo budget 25,400 is inside that regime.
6. **The lane denominator wall** (IR-H93-004, H73 wall table knowledge/61a): any full-budget
   View-B-family greedy emission puts ≥ 0.89 of its dots within 3 px of one informative prior.
   **Pre-registered escape: per-prior quota placement** (`run_h73.place_lane`, H73 amendment 61a;
   H69 measured it lane-feasible at max near-dot 0.6985), adopted here BEFORE the fit.
7. **PROXY-SGMC** (H95 E3) is a board-anchored *diagnostic*: SGMC geologic-map faults ≥ 3 px from
   `labels.tif`, thinned by whole segments to |G| = 10,000, 5 seeds; Spearman vs the 13
   owner-reported board scores 0.567, about as informative as emitted mass alone (|ρ| 0.889).
   **It is never a score** and never promotes anything.

## 1 · Candidate hypotheses (ranked by expected HOLDOUT-DTI gain ÷ implementation cost)

Novelty check, 2026-10-10: `grep -rn "quota_state\|disagreement_state\|soft prior\|soft_prior\|
graft" src scripts knowledge` shows no implementation of (1)–(3); the nearest neighbours are
H92 (disagreement-only emission on the generic H61 View B, 17,707 px), H96 (weighted bidirectional
mix on the generic H61 View B, 25,400 px), H57/H60C (union core + novel arm), and H73 (per-prior
quota as a *lane-compliance* device on a consensus field, not a scientific stratum). None of them
emits a pre-registered **disagreement-state quota field on the DVA2 base**.

| # | Hypothesis | Layers (`training_features.tif` band / external) | Physical signature targeted | Why it should catch a fault the USGS/INGENIOUS catalogue lacks | How it differs from anything implemented here | Expected gain / cost |
|---|---|---|---|---|---|---|
| **1 (PRIMARY)** | **Disagreement-state quota emission on the DVA2 base** — E2. Cells are classified by the co-training state machine (consensus C / A-only buried / B-only artifact-suspect / abstain); the 25,400 px budget is allocated 18,000 C + 7,400 A-only, B-only vetoed; placement is per-prior quota | B: bands 12 `det_elev`, 19 `det_elev_slope`, 13 `iso_grav_anom`, 15 `depth_to_base_surf`, 18 `iso_grav_anom_hg` (H82 DVA-2 design: 8-direction fan, lags 1/2/3/4/6 px, σ per H82 constants → 50 channels); A: `view_A_with_external` store channels (gravity/magnetics/strain/seismicity/cover + upward-continued TMI 150 m) | sustained directional (elliptical) anisotropy of the surface field = damage zone / juxtaposed blocks; A-confident ∧ B-abstain = concealed fault beneath cover (the catalogue maps surface traces, so blind/buried faults are by construction absent from it); B-confident ∧ A-abstain = road / erosion-line suspects, vetoed | the anisotropy operator is catalogue-free and fires where no trace is mapped; the A-only quota explicitly targets the blind-fault population the catalogue lacks; the B-only veto removes the brief's named surface mimics instead of emitting them | H92/H96 emitted disagreement on the generic 5-channel H61 View B (measured 0.0527 single_B skill there vs 0.19 DVA2); H84/H93 *audited* the strata but never emitted a quota-allocated state field; H73's quota is a lane device, not a stratum | medium (board lever + precision) / low (no new fit beyond the two learners) |
| 2 | **Soft-prior graft on DVA2** — E1. `g_w = rB·(1 + w·(rA − 0.5))`, w ∈ {0.25 primary, 0.50 ablation}, full 37,654 budget | same as 1 | View A's weak but independent likelihood (max |ρ| 0.14 error correlation) re-weights the DVA2 ranking at the margin: where both views fire (buried or active fault with geophysical expression) the score rises; where A is silent (road, erosion line, artefact) it decays continuously — a soft veto that avoids the hard-veto "no target" problem (H84 B-only cardinal audit: no road excess to veto) | a Bayesian update with an independent weak likelihood changes exactly the borderline top-k selection where credit is decided, without moving mass | never implemented: every prior co-training round used hard label exchange (H56/H95, measured to *lower* the receiver's AUC) or hard strata (H92/H93/H96); H95 next-work #5 ("use A only as a soft prior inside B's confident set") is the open item this executes | low–medium / low (post-hoc combination of two existing OOF fields; no new fit) |
| 3 | **Consensus-only sub-halo** — E2 attribution arm. C stratum only, 25,400 px | same as 1 | isolates "A gates B" from "A adds dots": if consensus_only ≈ quota_primary on the holdout, the A-only quota is dead weight; if it is lower, the buried stratum carries independent credit | the off-catalogue hidden population is where A-gating should matter most; the catalogue instrument tests the other half of the claim | no round has compared consensus-only vs consensus+A-only at matched sub-halo mass on the E2 instrument (H96's `consensus_only` was generic-B-based, 0.0824) | low / zero (same fields, one more placement) |
| 4 | **Drainage-deflection corridors** (BLOCKED) | 1 m DEM (USGS 3DEP) via the competition's `1m_DEM_links.csv` | D8 flow-direction deflection across a buried scarp — the classic covered-fault criterion in Basin-and-Range piedmonts | streams crossing a buried scarp are deflected/straightened exactly where no trace is mapped | not implemented in this repo | high / **BLOCKED** — source named and re-checked this session: USGS 3D Elevation Program <https://www.usgs.gov/3d-elevation-program> (public domain) and the tile list on <https://www.drivendata.org/competitions/306/competition-doe-gems/data/> (login). `curl` from this sandbox 2026-10-10: `prd-tnm.s3.amazonaws.com` 000, `www.usgs.gov` 000, `www.drivendata.org` 000; `api.github.com` 200. **Not obtainable here; owner download + SHA pin required.** |
| 5 | **INGENIOUS 2 m temperature view** (BLOCKED) | GDR submission 1391 (DOI 10.15121/1881483), `gdr.openei.org` | shallow thermal-gradient anomalies along buried fault-controlled upflow | blind faults in the INGENIOUS study area carry fluid signatures invisible to the surface-trace catalogue | no thermal view exists in the shared store (H55 `btherm` was a proxy, not INGENIOUS) | unknown / **BLOCKED** — free and official, but `gdr.openei.org` returns 000 from this sandbox (H95 next-work #4); owner download + SHA pin required. Not proposed as viable here |

Only rank 1 is the primary; rank 2 is fitted as the E1 primary/ablation; rank 3 is the E2
attribution arm. Ranks 4–5 are named, checked, and blocked (the brief's rule: a candidate that
cannot be validated without new external data names the specific free official source and the
obtainability check).

## 2 · Views, learners, folds (reused, not rebuilt)

* **View B (primary ranking).** H82's DVA-2 bank (50 channels: per band × lag,
  `(max−min)/(max+min)` anisotropy and log-variance of the 8-directional semivariance), computed by
  `run_h84.stage_channels` redirected to `work/h102/features` (imported, not forked). Learner:
  `run_h61.learner_for("B", SEED)` (HistGradientBoostingClassifier, max_iter 250, lr 0.08,
  max_leaf_nodes 15, min_samples_leaf 40, l2 1.0, early stopping off, random_state 61052) on the
  store `view_B_with_external` channels + the 50 DVA2 channels (exactly H84's `B_DVA2` arm).
* **View A.** H61's shared View A learner (store `view_A_with_external` channels), exactly H84's
  `single_A` arm. No capacity change (H62's View-A capacity increase is NOT adopted: A's role here
  is a weak independent prior, and the sufficiency test uses the standard learner).
* **Folds.** `gems52.spatial.folds(cat, eligible, buffer_px=80)` = `label-blind-quadrants-v2`,
  4 folds; `SEED = 61052`. Training sample `run_h61.sample_for_fit` (20k pos / 60k neg cap,
  visible-catalogue collar 5 px). Region-only prediction, stitched per quadrant (`run_h82.stitch`
  redirected to `work/h102`).
* **Emission pool.** `eligible ∧ finite(fB) ∧ finite(fA) ∧ (dist_to_catalogue > 200 m)`.
* **Ranks.** `rB`, `rA` = `run_h61.pct_rank` of the stitched OOF probability fields over the
  emission pool (averaged ties). All strata/graft definitions below operate on these global ranks;
  the per-fold holdout allowed set is the standard one (`region ∧ ¬visible ∧ vd > 2 px`).

## 3 · Experiments (3 of 3 budget)

### E1 — soft-prior graft (full budget)

`g_w = rB · (1 + w·(rA − 0.5))` on the pool (NaN outside), w ∈ {**0.25 (primary)**, 0.50 (ablation)}.
HOLDOUT-DTI at 9,400 px/fold (37,654 total) for arms `g_025`, `g_050`, `B_DVA2`, `single_B`,
`single_A`, `random`. Promotion-relevant comparisons: `g_025 − B_DVA2` and `g_025 − single_B`
paired CIs (same draws/seed).

### E2 — disagreement-state quota emission (sub-halo 25,400 px)

Strata on the pool (deterministic ladder, no data peeking):
* **τB** = the largest value in {0.99, 0.98, 0.97, 0.95, 0.90} with
  |C| = |(rB ≥ τB) ∧ (rA ≥ 0.75)| ≥ 18,000; if none qualifies, τB = 0.90 and |C| is accepted as-is.
* **C (consensus)** = (rB ≥ τB) ∧ (rA ≥ 0.75). Quota: 18,000.
* **A-only (buried)** = (rA ≥ 0.99) ∧ (rB < τB). Quota: 7,400; if |A-only| < 7,400 the deficit is
  filled from C (never from B-only).
* **B-only (vetoed, counted for the record)** = (rB ≥ τB) ∧ (rA < 0.50). **Never emitted.**
* Combined score `s`: C cells → 2 + 0.01·(rB·rA); A-only cells → 0.01·rA; all other cells → 0
  (every C cell ranks above every A-only cell; the greedy walk therefore realises exactly the
  quota allocation).
* **Placement: `run_h73.place_lane(s, pool, K = 25,400, sups, limit = 0.70, rounds = 8)`** with
  `sups` = the informative scored-registry supports (`run_h82.restricted_registry` +
  `restricted_supports`) — H73 amendment 61a; cap `floor(0.70·K)` per offending prior; fallback to
  `nodes.spacing_select` only if the quota placement short-fills (reported verbatim).

HOLDOUT-DTI at 6,350 px/fold (25,400 total) for arms `quota_primary` (s), `consensus_only` (C only,
score rB·rA), `a_only_stratum` (A-only only, score rA), `B_DVA2@6350` (mass-matched control),
`single_B@6350`, `random@6350`. Plus the 9,400 px/fold reproduction controls `B_DVA2`, `single_B`,
`single_A`, `random` (committed targets 0.192829 / 0.174517 / — / 0.080426; tolerance 1e-3 for
`single_B` and `random`; `B_DVA2` reported verbatim against both committed readings 0.189200
(H82) / 0.192829 (H84 re-run)).

### E3 — board-anchored diagnostic (PROXY-SGMC, **never a score**)

H95's E3 recipe unchanged (SGMC map ≥ 3 px from `labels.tif`, whole-segment thinning to
|G| = 10,000, 5 seeds, 200 m allowed ring, `metric.dti` per seed): stitched fields
`{B_DVA2, g_025, s (state-machine field over the pool), single_B, single_A}` at budgets
{37,654, 28,000, 25,400} + champion `h33-2-b2` as-is + `d2-8` as-is + `random` at the same budgets.
**Question answered:** at *matched mass* on an off-catalogue instrument, does the graft or the
state machine beat plain DVA2? Report with the H95 caveat (Spearman vs board 0.567; mass |ρ| 0.889).
No gate in §4 reads this experiment.

## 4 · Frozen gates and verdict rule

| # | gate | pass condition |
|---|---|---|
| 1 | control_reproduction | `single_B` within 1e-3 of 0.174517; `random` within 1e-3 of 0.080426 (this run's 9,400/fold receipts) |
| 2 | leakage_canary | max single-channel direction-insensitive OOF AUC over all learner channels (DVA2 + store B + store A) < 0.90 |
| 3 | independence | max \|ρ\| of spatial-block (50 px) OOF negative errors between the round's `single_A` and `single_B` fields < 0.60 (H74 thresholds, `donor_rank_min` as inherited) |
| 4 | sufficiency_View_A (bookkeeping) | mean OOF AUC ≥ 0.60 ∧ min fold ≥ 0.55 — **expected FAIL; failure does not block the other gates but is reported** |
| 5 | holdout_promotion | `quota_primary` pooled HOLDOUT-DTI > **0.192829** (committed H82/H84 B_DVA2 on E2) AND paired `quota_primary − B_DVA2` (in-run, 6,350/fold, same draws/seed) 95 % CI lower bound > 0 |
| 6 | format | `gems52.gates.format_report` vs `sample_submission.tif`: 1 band float32, EPSG:32611, 3730×3292, pinned transform, 0 NaN/inf, values in [0,1] |
| 7 | uniqueness | decoded pattern not identical to any census prior; novel fraction ≥ 0.20; not the literal prior union |
| 8 | lane_surface | max Spearman of the stitched `s` rank field vs every full-census prior < 0.90 (before placement) |
| 9 | lane_dots | after placement: policy max near-3px fraction vs informative priors ≤ 0.70; the literal full-census number (including the universal-coverage lattice probe, coverage ≥ 0.95) is reported verbatim — a literal DUPLICATE/STOP via the probe alone is the known standing condition (IR-H96-002), reported, not waived |
| 10 | not_the_union | dots vs equal-budget union-max placement (max(rA, rB), same `place_lane`): Jaccard recorded; share of dots outside the union placement recorded; plus supports vs single-A-only and single-B-only top-25,400 |

**Verdict rule (frozen).** `promote` iff gates 1, 2, 3, 5, 6, 7, 8, 9 (policy), 10 (share outside
union ≥ 0.25) all PASS. Otherwise `negative`. In either case the GeoTIFF is published with
**OK TO DOWNLOAD: YES** (format-valid container) and **OK TO SUBMIT: YES only if verdict = promote**,
else **NO — research-only**. Gate 4 (sufficiency) and E3 (PROXY-SGMC) are reported, never gate the
verdict. No submission slot is picked by this session (protocol §6).

## 5 · Emission and artefacts (frozen)

* File: `submission/gems52-h102-disagreement-quota-dva2-25400px-<UTC>-<sha8>-zeros.tif`
  (single-band float32, values exactly {0,1}, 0.0 outside the organiser footprint, no NaN,
  `gems52.grid.write_geotiff_portal_exact(outside="zero")`) + ZIP wrapper.
* **Submission name:** `h102-disagreement-quota-dva2-25400px-<UTC>-<sha8>`;
  **note (134/140 chars):** `H102 co-train state machine: DVA2 consensus 18000 + buried A-only 7400, B-only veto, 25400px quota placement; vs 0.192829 bar; research`
* A-only reasoning: one CSV row per emitted A-only dot (7,400): grid ref, easting/northing, rA, rB,
  distance to mapped catalogue, dominant View-A band z-scores (H84 `A_BANDS`/`A_MECH` reading
  function, imported), geological reasoning, named non-fault mimic, falsifier, confidence LOW
  (View A failed sufficiency — stated on every row).
* Run card: `evidence/h102_run_card.json` (hypothesis, mechanism, named non-fault process,
  HOLDOUT-DTI + CI, correlation/overlap vs registry, raster sha256, validator output, submission
  name + note, verdict).
* Knowledge: `knowledge/98_h102_results_and_limits.md`; site: `docs/h102.html` +
  `docs/h102-executive-summary.html`; README/AGENTS blocks; `scripts/check_site.py` clean.

## 6 · What this round must not re-litigate

* The champion-field mass lever (subset of `h33-h33-2-b2` ranked by d2-8) is the next-work item #1
  in the *champion-field lane*; it is a literal lane duplicate for this session (100 % of a subset's
  dots within 3 px of the champion) and is **not** built here. It is cited, not executed.
* No hard pseudo-label exchange (closed negative, knowledge/03; H95 measured it below single_B).
* No road/cardinal-azimuth veto on B-only as a *primary* signal (H84 measured no excess: 0.0809 vs
  null 0.1111). The B-only veto here is a stratum rule of the state machine, not a tuned screen.
* PROXY-SGMC numbers are never promoted, quoted as scores, or used to pick the slot.
