# 81 · H93 — hypotheses ranked and experiment plan (FROZEN before any fit)

Round label: **H93**. Lane: the brief's co-training paragraph (Blum & Mitchell, COLT '98 pp. 92–100,
[doi:10.1145/279943.279962](https://doi.org/10.1145/279943.279962)) — View A potential-field /
subsurface, View B surface, disagreement as the discovery signal.

This document is pinned by SHA-256 in `registry/h93_preregistration.json` BEFORE any fit.
`scripts/run_h93.py` recomputes the hash at start-up and refuses to run if it has moved.
Nothing in this document may be edited after the first fit; amendments go in a separate file
appended later (precedent: knowledge/65a, 67a).

Labels: HOLDOUT-DTI = `gems52-pooled-hide-v1` (pooled, α 0.2, β 0.8, 300 m triangular kernel,
label-blind quadrant folds hiding whole segments with an 80 px buffer, visible catalogue masked
pixel-exactly, catalogue-based features derived from visible faults only). Board numbers are PUBLIC
or OWNER-REPORTED, never ORGANIZER-CONFIRMED. A projection is never written as a score.

---

## 0 · What is settled and not re-litigated (carried from AGENTS.md and knowledge/03, 76, 78)

* Pseudo-labels **as a label source** are refuted (N-1: 0.0084 vs 0.0396 random). Disagreement is
  used to stratify/suppress, and the exchange is measured and reported, never shipped.
* View A sufficiency has failed eight consecutive rounds on the catalogue target (mean OOF AUC
  ≈ 0.52). Independence passes (max |ρ| 0.1526 < 0.60). H77cond showed the conditional margin is
  negative in every fold. No plain View-A repair is proposed.
* Placement dominates field choice at weak-field strength (H85: 0.072 spaced vs 0.017 clumped).
  All H93 placements use `gems52.nodes.spacing_select`, min 3 px.
* The all-finite zeros-outside container is the only container that cannot fail a literal `[0,1]`
  range test (IR-H85-004). H93 ships that container.
* Holdout DTI does not forecast the board (Spearman −0.10, R4). A holdout win is necessary, not
  sufficient; a holdout loss is final for slot purposes.
* Mass is the strongest measured board predictor in the family (Spearman −0.93 over 12 scored
  priors; knowledge/76 §4). The champion is likely over-emitting by 28–33 %. This is recorded as
  the next round's lever (candidate H93-MASS below); H93 itself keeps the standing 37,654 budget
  for lane/uniqueness comparability.

## 1 · Candidate hypotheses (3–5 required; novelty greps run this session)

Novelty method: `grep -rln` over `src/` and `scripts/` (counts below are this session's). Band
tags are the file's own descriptions (`evidence/band_inventory.json`), 1-based GeoTIFF bands.

| rank | id | layers | physical signature targeted | why it could catch a catalogue-missing fault | difference from the repo | cost |
|---|---|---|---|---|---|---|
| **1** | **H93-ABS** antithetic / sign-asymmetric basement step | band 15 `depth_to_base_surf` (view A, subsurface) | signed one-sided step `|Δ+| − |Δ−|` at 300 m and 100 m along 4 axes, plus paired opposite-sign steps ≤ 600 m apart (antithetic half-graben margins) | half-graben antithetic margins and fan-buried range-fronts carry a basement-depth throw with no surface expression; the catalogue is built from surface mapping, so these are systematically under-mapped | the queued H81-2 / H66-B statistic, **never run** (knowledge/69 row 2 "NOT RUN"; knowledge/45 rank 2 "Not run this round"). H77-D tested only an UNSIGNED grad-magnitude × basin-floor product (DTI ≈ 0.04, dead); the store's band-15 channels are gradient magnitude, persistence and coherence only — no signed step | low–medium |
| 2 | H93-COND conductivity local residual decoupled from cover | band 17 `cond_surf`, band 15 | high-frequency conductivity residual after removing the cover-thickness trend: fault-fluid / clay-alteration conductors that are not explained by sediment thickness | hydrothermal fluid pathways along unmapped faults alter conductivity at scales the catalogue never saw | H77-C tested `grad(cond) × grad(band 15)` (dead); a local-residual form exists for DEM elevation and slope (`B_*_local_residual` in the store) but NOT for band 17 (grep `residual` in store manifest: elevation + slope only) | medium |
| 3 | H93-SEIS seismic–strain gate on the surface field | bands 4 `geod_2ndinv`, 10 `deq_n100a15`, 16 `ieq_n100a15` as a gate on view-B emission | actively-deforming cells (high strain invariant AND nearby seismicity) that have no mapped trace | geodetic strain and seismicity see creeping/hidden structures independent of any map; the catalogue cannot contain what was never mapped | bands 10/16 were used as view-A raw channels (H60C point-process, H74 deformation-only view A sufficiency 0.5194 — dead AS A VIEW); never as a multiplicative gate on the view-B surface field (grep `gate` + band 10/16: 0 files) | low |
| 4 | H93-MASS budget discipline (metric lever, not geology) | placement only | none | — | knowledge/76 §4: the champion's own credit at S ≤ 25,384 reaches 0.3195; untested because no instrument could certify top-heavy ranking. Queued for a round with a prevalence-matched off-catalogue instrument (knowledge/76 §6) | low, separate round |
| 5 | H93-ASTER alteration band ratios (external) | ASTER L1T VNIR/SWIR band ratios (clay, iron-oxide indices) | hydrothermal alteration halos around fault-fed systems | alteration is a surface expression invisible to the 100 m geophysics | **NOT VIABLE IN THIS SANDBOX.** Free official source named and checked: USGS EarthExplorer ASTER L1T (free, registration required), https://earthexplorer.usgs.gov/ ; sandbox egress allowlist excludes it. Needs an operator-side download with SHA pins before it can be proposed further | high |

## 2 · H93-ABS channel definitions (frozen, label-free, catalogue-free)

Let `z` = band 15 inside the eligible footprint `P`, NaN outside. Axes
`k ∈ {(0,1), (1,0), (1,1)/√2, (1,−1)/√2}` realised as integer shifts (diagonals nearest-neighbour).
At offsets 1 px (100 m) and 3 px (300 m) along axis `k`:

```
Δ+_k(x) = z(x + 3·n̂_k) − z(x)          Δ−_k(x) = z(x) − z(x − 3·n̂_k)
ASY_k(x) = |Δ+_k| − |Δ−_k|              (signed one-sided-step asymmetry)
```

Channels (all NaN where any shifted sample leaves `P`):

1. `ABS_step3 = max_k |ASY_k|` at 300 m — one-sided basement throw (the queued H81-2 statistic).
2. `ABS_step1 = max_k |ASY_k|` at 100 m — sharp, shallow throw.
3. `ABS_pair6 = max_k [ |ASY_k(x)| · max(|ASY_k(x + 6·n̂_k)|) · 1{opposite sign} ]` — antithetic
   pair: two opposite-dip basement steps ~600 m apart along one axis (half-graben geometry).
4. `ABS_cover = ABS_step3 · pct_rank(z)` — step under deep cover (the A-only discovery population;
   N-1 measured A-only pixels sit at median band-15 rank 455 vs 251 concordant).

Reading: a smooth ramp or regional tilt gives ASY ≈ 0 (both sides step equally); a normal-fault
step gives |ASY| ≈ throw; an antithetic pair lights `ABS_pair6`. Named non-fault mimics (required
by the run-card rule): differential compaction over buried lithologic steps, palaeo-channel
incision into basement, and interpolation/smoothing artefacts of the basement-depth MODEL itself
(band 15 is a model-derived product, not a measurement — stated in the band description).

## 3 · Experiment plan (budget: 3 experiments, ≤ 2 h, 0 slots)

Instrument: `scripts/run_h61.py` (canary, fit, exchange) then `scripts/run_h93.py`
(fit/holdout/build), unchanged shared tools: `run_h61.setup/sample_for_fit/learner_for/pct_rank/
to_grid`, `gems52.spatial.folds`, `gems52.evaluate_holdout` (`gems52-pooled-hide-v1`),
`gems52.nodes.spacing_select`, `gems52.gates`, `gems52.grid.write_geotiff_portal_exact`.

**E1 — fit, canaries, independence.** Shared store + run_h61 canary/fit/exchange (view A, view B
OOF predictions; exactly-one confident→abstain whole-segment exchange, measured, not shipped).
Build the four ABS channels label-free. Canary: each ABS channel ALONE, per-fold AUC on held-out
region truth vs region negatives ≥ 5 px from catalogue; alarm ≥ 0.90 (brief rule 4). Independence:
the run_h61 pre-exchange block-level negative-error correlation, threshold |ρ| ≤ 0.60 else the
exchange is abandoned per the brief (the field arms still run; the emission then carries the flag
"independence gate failed").

**E2 — holdout (the validation the brief mandates before any slot).** Arms, each 9,400 dots/fold,
3 px spacing, allowed = fold region \ visible catalogue \ 200 m ring:

| arm | definition |
|---|---|
| `single_B` | template view-B model (must reproduce HOLDOUT-DTI 0.174571 within 1e−3) |
| `B_ABS` | view-B channels + 4 ABS channels, same rows/learner/seed (THE candidate) |
| `ABS_only` | 4 ABS channels only |
| `disagree_Aonly` | pooled run_h61 pre-exchange ranks; field = pct_rank(A) inside the stratum A ≥ q0.90 ∧ B ∈ [q0.35, q0.65], −1 outside (A-confident, B-abstains → buried candidate) |
| `random` | seeded uniform on the same allowed set (control; must reproduce 0.080426 within 1e−3) |

Plus the six run_h61 arms (single_A, single_B, union_max, disagreement_pre, disagreement_post,
random) from the shared holdout stage — the brief's "compare against a single-view baseline".
**Promote rule (frozen):** `B_ABS − single_B` paired cluster-bootstrap 95 % CI lower bound > 0
(1,000 draws, seed 61052) AND both canaries pass AND the union check (§4) passes. Otherwise the
verdict is NEGATIVE and the file is research-only (negative results are deliverables).

**E3 — build, gates, artefact.** Stitch the `B_ABS` OOF field (each pixel gets its own fold's
prediction, H73/H75 pattern). Pool = eligible ∩ finite \ catalogue \ 200 m ring.
`nodes.spacing_select`, K = 37,654, min 3 px. Then:
* A-only reasoning CSV (brief: "write the geological reasoning for every A-only candidate"):
  connected components of the A-only stratum intersecting the shipped dots; one row per segment
  with centroid UTM, px count, median band-15 depth, median gravity-gradient magnitude (store
  `A_gravity_grad_3`), and the templated reasoning sentence.
* not-merely-union check: Jaccard of shipped dots vs the `union_max`, `single_A`, `single_B`
  holdout placements pooled across folds; bar 0.50 (h77cond precedent: 0.0037).
* lane gates: `gates.lane_report` surface phase AND dots phase against the full registry
  (docs/downloads, submission/, data/scored, data/reference); STOP rule rank > 0.90 or near-3 px
  share > 0.70 vs ONE registry raster. Universal-coverage probes (coverage ≥ 0.95 of the eligible
  domain) are reported separately because near-3 px vs them is ~1.0 for ANY non-empty raster
  including random (measured H75/H85); the literal number is still recorded.
* uniqueness: `gates.uniqueness_report` decoded-pixel comparison vs every prior; self-copies
  excluded by path (IR-H85-001).
* format gate: single-band float32 EPSG:32611, shape/transform/CRS = sample_submission, all
  finite in [0,1], zeros outside the domain, zero mass on catalogue and inside the 200 m collar.
* container: `write_geotiff_portal_exact(..., outside="zero")` (IR-H85-004); ZIP twin.
* artefact name `gems52-h93-abs-cotrain-37654px-<UTC>-zeros.tif`, submission name
  `h93-abs-cotrain-37654px`, note ≤ 140 chars:
  `H93 antithetic basement step + view B co-training, A>B disagreement strata, 37654px, 3px spacing`.
* run card JSON per brief rule 5.

## 4 · Verdict ladder (frozen)

1. Promote-rule pass AND lane gates pass AND format/uniqueness pass → **DOWNLOAD YES, SUBMIT
   CANDIDATE** (promotion to a real slot remains the selector's decision, within the weekly cap).
2. Otherwise → **DOWNLOAD YES (research), SUBMIT NO**, with the failing gate named. The TIF is
   still generated and published (the brief requires a unique generated TIF and an obvious
   OK / not-OK status), and the negative result is recorded as a deliverable.

## 5 · Honest priors (written before any result is seen)

* ABS enters as four extra channels to a view whose OOF AUC is 0.61–0.77; band 15 alone canaried at
  AUC ≈ 0.53 in H77cond. Expected B_ABS − single_B is therefore near zero with a genuine chance of
  a small positive (a new, physically-motivated subsurface channel the surface view lacks). The
  promote rule is calibrated to detect exactly that.
* The holdout hides CATALOGUE faults; the board scores OFF-CATALOGUE faults (knowledge/76 §5:
  surface skill retains ~7 % there). Even a holdout win would not be a board forecast.
* The strongest known lever (mass, knowledge/76 §4) is deliberately NOT spent this round because
  the lane protocol fixes comparability at 37,654; it is queued as H93-MASS for the next round.
