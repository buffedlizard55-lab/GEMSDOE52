# 74 · H89 preregistration — cover-conditioned co-training with surface-artefact demotion

**Frozen 2026-10-10, before any fit of this round.** Pinned by `registry/h89_preregistration.json`
(SHA-256 of this file). `scripts/run_h89.py` refuses to start if either hash moves.

Lane (verbatim from the session brief): *co-training between a geophysical view and a surface view,
with disagreement as the discovery signal*. View A is potential-field and subsurface (gravity,
magnetics, strain, seismicity, depth-to-basement, conductivity). View B is surface (DEM-derived
curvature and slope plus the radiometric bands present in `training_features.tif` and the GeoDAWN
radiometric grids). Everything below stays inside that paragraph.

---

## 0. What this round must not repeat (read before proposing anything)

Measured in this repository, on restored, SHA-pinned bytes. These are constraints, not opinions:

| fact | where measured |
|---|---|
| View A sufficiency has failed **seven** times (mean out-of-quadrant AUC 0.5113, worst fold 0.4309) | `evidence/h82_fit.json`, AGENTS.md H82 block |
| Plain pseudo-label exchange **lowered** View A's OOF AUC (0.5019 → 0.4759) | H71, `knowledge/58` |
| View independence **passes** (max \|ρ\| 0.1317 over 2,089 blocks, bar 0.60) | `evidence/h82_independence.json` |
| Ungated A-only disagreement emission scored HOLDOUT-DTI **0.008975** [0.0047, 0.0145] | `knowledge/64_h74s_three_pass_review.md` |
| `single_B` is the standing comparable control, **0.1745–0.1749** | `evidence/h75_holdout.json`, `evidence/h77_holdout.json` |
| Best arm ever measured here: `B_DVA2` **0.1892**; not promotable post hoc | `registry/h82_preregistration.json → attribution_arms_not_promotable` |
| The holdout hides **catalogue** faults; the board scores faults the catalogue **lacks**. Spearman(holdout, board) ≈ **−0.10** | IR-H77-005, `knowledge/10` §5 |
| The 0.2778 champion is the 0.2600 file with its 100–200 m catalogue ring deleted (+6.8 % relative for −14.6 % mass) | `knowledge/49` §1 |
| `DTI ≈ T/(0.2·S + 0.8·\|G\|)`, \|G\| ≈ 14,088.7 px; beating 0.3195 at S = 37,654 needs ρ ≈ 0.1595 vs the champion's 0.1387 | `knowledge/49` §§2–4 |
| Regional strike here is **N10°W–SSE (166.7–171.8° compass), R 0.37–0.45** — not NNE | `knowledge/73` §5 |

Consequence that shapes this round: **the holdout instrument cannot reward a buried-fault detector.**
It withholds segments of a catalogue that was itself compiled largely from surface expression, so an
arm that deliberately spends budget on sub-cover candidates pays a measurable holdout cost for a
board-side bet. That cost is priced into the decision rule in §4 *before* the fit, not after it.

---

## 1. Candidate hypotheses, ranked

Each names the layers, the physical signature, why it should catch a fault the USGS/INGENIOUS
catalogue lacks rather than one it already has, how it differs from what this repo has built, and
the honest cost. Ranking is by expected DTI improvement ÷ implementation cost. **A rank is a
judgement, not a forecast.**

### Rank 1 — H89-A · Cover-conditioned A-only discovery (tested this round, inside the primary)

* **Layers.** View A: band 18 isostatic gravity horizontal gradient, band 13 isostatic gravity
  anomaly, band 11 vertical gradient, band 2 RTP magnetics, band 3 TMI horizontal gradient, band 9
  TMI vertical gradient, band 15 depth-to-basement, band 17 conductivity, plus the derived
  `A_gravity_*` / `A_RTP_*` / `X_mag_TMI_up150_*` channels. Conditioner: **band 15**
  (depth to basement = thickness of sedimentary cover, median 316 m, p99 3,420 m in this footprint).
* **Signature.** A potential-field edge (gravity HG maximum / RTP step) that is spatially *continuous*
  — at least 4 of the 24 neighbours in a 5×5 window are also A-confident — sitting under **above-median
  cover**, while View B abstains (no scarp, no curvature anomaly, no radiometric edge).
* **Why it is off-catalogue.** The catalogue's fault traces are dominated by features with surface
  expression. A normal fault whose hanging-wall basin has been filled by Quaternary alluvium has no
  scarp to map, but still offsets the density/susceptibility contrast at the basement surface. Those
  are the Basin-and-Range structures a 100 m-cell surface product cannot see and a mapper walking the
  piedmont cannot trace.
* **Difference from this repo.** H61/H66/H74S emitted A-only disagreement **ungated** (0.0090). CTD5
  gated on a cover *proxy* but not on measured basement depth and not on edge continuity. Nothing here
  has required (A-confident) ∧ (B-abstaining) ∧ (cover above the eligible median) ∧ (lineament
  continuity) simultaneously.
* **Named non-fault process that mimics it.** A buried lithological contact or a basin-margin
  palaeochannel: both produce a continuous gravity/magnetic edge under cover with no surface trace.
  **Falsifier written per candidate** (§5).
* **Cost.** Low — two new scalar channels on the cached stack, no new fit.

### Rank 2 — H89-B · Surface-artefact demotion of B-confident / A-silent pixels (tested, inside the primary)

* **Layers.** View B: `B_curvature_plus_3`, band 12 detrended elevation, plus the six external
  radiometric gradient channels `X_rad_{K,Th,U,ThK,UK,UTh}_grad3` (GeoDAWN, USGS DOI 10.5066/P93LGLVQ,
  restored from SHA-pinned mirrors).
* **Signature.** The brief's second disagreement direction: *where B is confident and A is not,
  suspect surface artefacts such as roads or erosion lines.* A tectonic scarp usually juxtaposes
  different materials, so a radiometric (K/Th/U) edge accompanies it; an incision line or a graded
  road cuts one material and shows a topographic concavity with **no** radiometric edge.
  `artifact = ½·(1 − rad_edge_rank) + ½·valley_rank`, `valley_rank = pct(B_curvature_plus_3) ·
  pct(−band 12)`; demotion `−0.20 · artifact` applied **only** where B is confident and A abstains.
* **Why it is off-catalogue.** It does not add candidates; it raises ρ (credit density) by removing
  the mimics that a surface-only ranker promotes. `knowledge/49` §4(b) shows ρ(S) decay — not budget —
  is the binding constraint on the board score, so a pure precision lever is the cheapest real gain.
* **Difference from this repo.** Radiometry has only ever entered as learner features. It has never
  been used as an *asymmetric veto conditioned on view disagreement*. The sibling site 7GEMSDOE's
  radiometric fusion (0.1589, owner-reported) fused rather than vetoed.
* **Named mimic of the mimic-detector.** Aeolian cover or a thick vegetation/soil blanket can mute a
  real fault's radiometric edge, so this veto can delete a true positive. That is why it is a soft
  −0.20 demotion and not a hard mask.
* **Cost.** Low — three cached channels, no new fit.

### Rank 3 — H89-C · One Blum–Mitchell donation round, B → A only (tested, reported, gated)

* **Mechanism.** The literal co-training step: pixels where B is confident (rank ≥ 0.90) and A
  abstains (rank < 0.60), **restricted to the fold's buffered training domain**, become pseudo-positives
  for View A at weight 0.5; refit A; keep the refit only if out-of-quadrant AUC improves in **all four**
  folds (pre-registered, §4).
* **Why.** Blum & Mitchell (COLT '98, pp. 92–100, doi:10.1145/279943.279962) require each view to be
  sufficient. A has never been. Donation is the only mechanism in the paper that can *make* a weak view
  usable, and it has been run here once (H71) in a different configuration (both directions, no
  cover gate, different confidence band).
* **Expected value.** Low — H71 measured a loss. It is run because the lane requires it and because a
  negative with an exact receipt is a deliverable.
* **Cost.** Low — 4 extra fits (~3 s each) and 4 region predictions.

### Rank 4 — H89-D · Basement-step azimuth concordance (NOT tested this round)

* **Layers.** Band 15 depth-to-basement, band 13/18 gravity, band 12 DEM.
* **Signature.** The *azimuth* of the basement-depth step should match the strike of the surface
  lineament within ±20° where both exist; concordance in azimuth, not just in location.
* **Why not now.** H82 measured that an 8-direction integer fan quantises an argmax orientation into
  four distinct values, which is exactly what killed its VSA channels. Doing this properly needs a
  continuous sub-pixel θ (16/32-direction fan or parabolic interpolation), which is a channel-build
  round of its own. Named here so the next round can pre-register it with the fix already specified.

### Rank 5 — H89-E · 1 m 3DEP LiDAR re-reduction (NOT tested; external data named and checked)

* **Source needed.** USGS 3DEP 1 m DEM tiles listed in the competition's own `1m_DEM_links.csv`
  (public domain, <https://www.usgs.gov/3d-elevation-program>).
* **Obtainability check, performed:** this sandbox's egress allowlist is `github.com`,
  `codeload.github.com`, `api.github.com`, `registry.npmjs.org`, `pypi.org`,
  `files.pythonhosted.org`. `www.usgs.gov` and the 3DEP S3 endpoints are **not reachable**, and the
  agent's page-fetch tool cannot stream gigabytes of tiles. The already-reduced
  `lidar_scarp_features_u8` mirror is the reachable substitute and is already in the stack.
  **Verdict: not viable from this sandbox; do not propose it again without a transport.**

---

## 2. The primary arm (frozen formula)

All ranks are percentile ranks over the fold's allowed set; all thresholds are fixed here and never
re-tuned after the fit.

```
rA = pct_rank(p_A)                      rB = pct_rank(p_B)
A_conf  = rA >= 0.90     A_abst = rA < 0.60
B_conf  = rB >= 0.90     B_abst = rB < 0.60
cover   = pct_rank(raw_band_15) >= 0.50                     # above-median sedimentary cover
cont    = (# A_conf pixels in the 5x5 window) >= 4          # lineament, not speckle
disc    = A_conf & B_abst & cover & cont                    # the A-only discovery set
artifact= 0.5*(1 - rad_edge) + 0.5*valley,   in [0,1]
          rad_edge = max over the six X_rad_*_grad3 percentile ranks
          valley   = pct_rank(B_curvature_plus_3) * pct_rank(-raw_band_12)
B_art   = rB - 0.20 * artifact * (B_conf & A_abst)          # surface-artefact demotion
```

**Placement (metric-aware, the repo's shared rule).** Budget `K = 37,654` binary dots, the champion's
measured mass and the measured stopping point of this family's ρ(S) curve (`knowledge/49` §3);
minimum separation 3 px; allowed pool = eligible ∧ (distance to the catalogue > 200 m) — the single
measured free lever in `knowledge/49` §7.

1. `K1 = 33,136` (88 %) dots by `nodes.spacing_select(B_art, pool, K1, min_px=3)`.
2. `K2 = 4,518` (12 %) **reserved discovery dots** by `nodes.spacing_select` over `disc` only, on the
   pool minus the 3 px halo of step 1, ranked by `rA`.
3. If `disc` cannot fill K2, the shortfall is **recorded, not back-filled** from B.

Output raster: binary {0, 1} float32, zeros everywhere else **inside and outside the footprint**
(all-finite). Rationale: the portal rejected an earlier NaN-outside file with *"Predicted values must
be in range [0, 1]"*; every owner-scored file that the board accepted in this family is an all-finite
"-zeros" raster. Binary is optimal under the metric (`knowledge/49` §2.1).

## 3. Arms measured on the shared hide-and-recover instrument

`gems52.evaluate_holdout` v`gems52-pooled-hide-v1`; whole catalogue segments withheld by label-blind
quadrant with an 80 px buffer; every catalogue-derived feature derived from visible faults only;
visible faults masked pixel-exactly; pooled DTI with α 0.2 / β 0.8 and a 300 m triangular kernel;
1,000 paired physical-20 km-cluster bootstrap draws; matched budget **9,400 dots per fold per arm**
(88 % / 12 % split for the primary, exactly as the full build).

`single_A` · `single_B` · `union_max` · `B_art` · `A_only_cover` · **`CCD` (primary)** · `random`.

## 4. Decision rules, frozen

1. **Leakage canary.** Any single learner channel with out-of-quadrant AUC > 0.90 on a fold ⇒ ALARM;
   the round reports leakage and does not ship.
2. **Independence.** `gems52.spatial.independence` on spatial-block out-of-fold errors over labelled
   negatives, thresholds inherited verbatim from `registry/h74_preregistration.json` and read out of
   that file by the runner (block side **50 px**, donor rank **0.95**, abandon at \|ρ\| > **0.60**,
   minimum 20 blocks). \|ρ\| > 0.60 ⇒ **abandon the method** and report negative.
3. **Donation.** Keep the refit View A only if its out-of-quadrant AUC improves in **4/4** folds.
4. **Promotion of the primary.** `CCD` is **SUBMIT-ready** iff all of:
   * pooled HOLDOUT-DTI non-inferior to `single_B`: point estimate ≥ `single_B` − **0.020** and the
     paired 95 % CI lower bound > **−0.040**. *The margin is the pre-priced cost of spending 12 % of
     the budget on a signal this instrument structurally cannot reward (§0, IR-H77-005). It is set
     here, before the fit, and may not be widened afterwards.*
   * format validator PASS (1 band float32, EPSG:32611, 3730×3292, transform/bounds equal to the
     organiser template, 0 NaN, 0 inf, values ⊂ {0,1});
   * decoded-pixel uniqueness: identical to **no** prior raster in the registry;
   * lane: surface Spearman ≤ 0.90 against every registry raster, and the **policy** near-3 px share
     (informative priors only, universal-coverage probes excluded by measured coverage ≥ 0.95)
     ≤ 0.70. The literal full-census verdict is reported verbatim alongside and a restricted PASS
     never waives it in the written record;
   * not-the-union: the emitted dot set is not equal to, and not a subset of, the union-max placement,
     nor equal to the single-A or single-B placement.
5. If the primary fails rule 4 on holdout only, the artefact is still written and published as
   **DOWNLOAD YES / SUBMIT NO (research-only)**. No other arm may be substituted post hoc.
6. **Budget.** ≤ 3 experiments, ≤ 2 hours. Weekly submission slots used by this round: **0** —
   promotion to a real slot is a separate selector step.

## 5. Reviewer-facing reasoning (Phase 2 requirement)

Every A-only (`disc`) dot that reaches the raster is exported with: pixel row/column, UTM 11N
easting/northing, `rA`, `rB`, measured depth-to-basement (m), isostatic gravity horizontal gradient,
RTP magnetics, detrended elevation, slope, radiometric edge rank, distance to the nearest catalogue
trace (m), and one sentence naming **the specific non-fault process that would explain the same
observation** (buried lithological contact / palaeochannel / survey-line artefact). The export is
`docs/downloads/h89-a-only-reasoning.csv`, RFC 4180.

## 6. Irregularity policy

Anything that does not match this document is logged in `registry/irregularities.json` with an
`IR-H89-xxx` identifier and reported in the run card, whether or not it changes the verdict.
