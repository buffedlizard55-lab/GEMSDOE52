# 43 · H66 pre-registration — frozen before any fit (2026-10-09)

Round label **H66**. Lane as briefed: co-training between View A (potential field / subsurface) and
View B (surface), disagreement as the discovery signal. This file is frozen; `scripts/run_h66.py`
refuses to run if its SHA-256 moves. The hash is pinned in `registry/h66_preregistration.json`.

Inputs are the manifest-pinned bytes restored this session (`data/restore_receipt.json`,
`ALL_VERIFIED=True`, 23/23 pins): `training_features.tif` (418,912,844 B,
`4371c82e3b8339b8…`), `labels.tif`, `sample_submission.tif`, the 0.2778 reference
`reference/h33-2-b2-zeros.tif`, the twelve scored priors, and the four external rasters plus the
three GDR CSVs. **Provenance class: integrity-pinned owner mirrors, NOT organiser-authenticated**
(the portal is login-walled).

---

## 0 · What is already dead, and therefore not retested

From `knowledge/03` (N-1, N-2, N-6, N-10 … N-22), `knowledge/10`, `knowledge/27`:

* pseudo-label co-training (refuted on both instruments, N-1);
* blends of View A and View B (every blend ≤ View B alone, N-16);
* disagreement as a **rank modulator** (worse than unmodulated, N-17);
* potential-field transforms at 300 m cell size (AUC ≈ 0.52, N-6);
* supervised detectors trained to reproduce the catalogue (0.1223, 0.0286);
* QFaults / INGENIOUS as positive priors (≈ 0 off-catalogue hits);
* **USGS SGMC off-catalogue fault lines as an emission** (organiser score 0.0512 at 44k px,
  implied credit density 0.0234 < uniform random 0.0279 — worse than noise);
* radiometric alteration ratios (N-12); structure-tensor coherence as a re-ranker (N-11);
* recovering the hidden truth from published scores by tomography (infeasible, IR-H60-004).

Any H66 arm must differ from all of the above. Two rules are inherited unchanged because they are
measured on organiser-scored bytes:

* **R-zero-tax** — emit nothing within 200 m of a mapped catalogue trace (`knowledge/10` §2:
  deleting the 100–200 m ring moved 0.2600 → 0.2778, +6.8 % relative).
* **R-binary** — values exactly {0, 1}; at a fixed support the metric is increasing in the mass on an
  accepted pixel, so 1.0 is optimal (`tests/test_metric.py`).

---

## 1 · Candidate hypotheses (5), ranked by expected DTI gain ÷ implementation cost

### rank 1 — **H66-A · Thermal-upflow corridor (TUC)** ← the arm this round runs

* **Layers.** External GDR Wellspring table `data/external/gdr_wellspring_in_footprint.csv`
  (27,092 rows, 12,570 unique sites, six layers: `well_features`, `well_chemistry`,
  `well_temperature`, `spring_chemistry`, `spring_temperature`, `spring_features`), fields
  `temp_c`, `geothermquartz_c`, `geothermchalc_c`, `geothermcat_c`, `thermalclass`; plus
  `training_features.tif` bands 3 (TMI horizontal gradient), 12 (detrended elevation),
  15 (depth to basement), 17 (surface conductivity), 18 (isostatic gravity horizontal gradient),
  19 (detrended-elevation slope); plus `external/lidar_scarp_features_u8.tif` (`step_max`,
  `strike`, `coh100`).
* **Physical signature targeted.** Not an edge or curvature transform. It is a **point-source
  fluid-discharge signal converted into a linear structural corridor**: (i) anomalous heat and
  solute transport at a spring or well implies a deep permeable pathway; (ii) silica (quartz /
  chalcedony) and cation geothermometers estimate *reservoir* temperature from water chemistry and
  are largely independent of sample depth, so a high value is not a deep-well artefact; (iii) a
  discharge point localises a structure but does not trace it, so the point is extended along the
  **locally measured structural strike** from the structure tensor of a multi-channel edge-energy
  composite, and cross-checked against the independent LiDAR scarp `strike` band.
* **Why it should catch a fault the catalogue does not have.** The catalogue is the USGS
  Quaternary-fault database plus INGENIOUS. A site whose measured or reservoir temperature is
  anomalous and which lies **≥ 300 m (beyond the whole DTI kernel) from every mapped fault** is, by
  construction, evidence for a permeable structure that the catalogue does not contain. The
  competition target is exactly that class ("structures that are indicative of geothermal
  resources … not contained within the current public USGS database", official problem page).
  Measured this session: **952 sites** satisfy (temp ≥ 60 °C ∨ reservoir T ≥ 100 °C ∨ class Hot)
  ∧ d(catalogue) ≥ 300 m ∧ inside the footprint, spread over **594 distinct 1 km blocks**, i.e. a
  region-wide signal, not one geothermal field.
* **How it differs from anything implemented here.** `knowledge/03` N-20 injected INGENIOUS/GDR
  *thermal lineaments* as a rank bonus on a View-B field: **3,340 cells** footprint-wide, gated by
  structure-tensor coherence at a 0.30 floor, and measured **neutral** (+0.00003). H58 used a
  deliberately restrictive *cold*-geothermometer consensus rule (`temp_c ≤ 30` ∧ geotherm ≥ 100 ∧
  |quartz − cation| ≤ 20) and produced **22 px**. `src/gems52_r4/layers.py` read the same CSV as a
  `paleo_geothermal_table` at `min_geotherm_c = 150` for a *reasoning* table, not an emission.
  No prior arm in this repo has used the **whole warm/hot population (1,156 sites) as emission
  seeds**, nor extended them into **strike-aligned corridors**, nor used the CSV's own
  `dist_known_fault_px` as a selection variable. It is also not the SGMC arm: that emits *mapped
  lines from another compilation* (measured worse than random); this emits *structure inferred from
  fluid discharge*, an independent physical observable.
* **Expected gain, and the honest bracket.** Credit density ρ of a wholly novel field is unknowable;
  `knowledge/10` §8 gives the standing prior ρ ~ U[0.0279, 0.1387]. At S = 25,000 px and
  |G| = 14,088.7 that is DTI ∈ [0.037, 0.185]; at |G| = 18,000, DTI ∈ [0.033, 0.166]. **A fully
  novel file is therefore expected to score BELOW the 0.2778 champion**, because the lane's
  uniqueness rule forbids re-emitting the exactly-accounted credited core `P1 = A ∩ C`
  (25,517 px, ρ ∈ [0.163, 0.205], DTI(P1 alone) ∈ [0.2546, 0.3190]). That cost is stated here,
  before the run, and is the price of the parallel-run protocol — not a defect of the arm.
* **Cost.** Low. All inputs are on disk; no new external data; no fitting on the emission path.

### rank 2 — H66-B · Antithetic / basin-margin pair inference from band 15

* **Layers.** band 15 (depth to basement = basin-fill thickness), bands 13 / 18 (isostatic gravity
  and its horizontal gradient), band 12.
* **Signature.** For each mapped range-front trace, search **across the adjacent basin** for the
  antithetic basement step: half-grabens are asymmetric, and the gently-dipping or antithetic
  margin is systematically less often mapped than the main border fault.
* **Why new.** It is *conditioned on the catalogue's geometry* but emits off it, so it is
  off-catalogue by construction. Differs from H60's "basement/cover-gated triple convergence",
  which gated on cover depth rather than on a paired-margin geometry.
* **Rank 2 because** band 15's own gradient has already been measured weak (H65-A premise AUC
  0.5202 with band 15 as a base layer) and the pairing rule adds a free parameter per basin.
  **Cost: medium. Not run this round** (budget: 3 experiments).

### rank 3 — H66-C · Directional variogram (anisotropic roughness) of detrended elevation

* **Layers.** band 12, band 19, `lidar_scarp_features_u8` (`relief`, `ex_max`).
* **Signature.** Fault damage zones change the *statistical* anisotropy of topography, not only its
  first/second derivative: the semivariance ratio γ(θ⊥)/γ(θ∥) at 300–900 m lags peaks on a trace.
  This is a different operator class from every gradient, Laplacian, Hessian and structure-tensor
  channel already in the repo (N-11 killed *gradient* coherence, not variogram anisotropy).
* **Why new.** No prior arm computes a directional variogram.
* **Rank 3 because** it is a whole-footprint rank field, and N-2 already killed "top-K of a
  whole-footprint rank field" as a detector; it would have to be gated by something else.
  **Cost: medium-high (lag-space search). Not run this round.**

### rank 4 — H66-D · Drainage-deflection corridors from a derived flow network

* **Layers.** band 12 → D8 flow accumulation and channel extraction (no external dependency;
  implementable in numpy/scipy), band 19.
* **Signature.** Lateral offset, beheading and deflection of alluvial-fan channels across a linear;
  the classic field criterion for a covered fault in Basin and Range piedmonts.
* **Why new.** The repo has never derived a flow network; all View-B channels are differential
  (slope, curvature, scarp step, Hessian line).
* **Rank 4 because** at 100 m cell size a 1 m-scale channel network is aliased; the 1 m DEM links
  CSV is unreachable from this sandbox (bandwidth, N-6). **Needs new external data to be viable:
  USGS 3DEP 1 m DEM tiles (public domain, official source
  <https://www.usgs.gov/3d-elevation-program>), listed in the competition's `1m_DEM_links.csv`.**
  Obtainability: **NOT obtainable here** (egress limited to github.com / pypi.org from bash; the
  mirror already holds a 12-band owner-reduced LiDAR scarp product derived from 706 of 716 tiles,
  which is the reachable substitute). **Cost: high. Not run this round.**

### rank 5 — H66-E · Seismicity-ridge coincidence (bands 10, 16)

* **Signature.** Linear ridges in earthquake density / short distance-to-event, off-catalogue.
* **Rank 5 because** H59-4 already built `field_seismicity = rank(band 16) × rank(∇band 16)` and
  the bands are 100 km-radius smoothings, so their resolution is far coarser than the 300 m kernel.
  **Cost: low, expected gain: lowest. Not run this round.**

---

## 2 · H66-A protocol (frozen)

### 2.1 Lane gates, run before any emission

* **S1 sufficiency** — View A out-of-quadrant AUC on `label-blind-quadrants` (whole 8-connected
  catalogue components hidden, buffer 80 px), identical splitter to H61/H63/H64 so the numbers are
  comparable. Bar: **mean ≥ 0.60 and every fold ≥ 0.55**. Stored measurements to beat: View A
  0.5163 (H61), 0.5362 (H63), 0.5230 (H64); View B 0.6843 / 0.6862.
* **S2 independence** — `gems52.spatial.negative_block_errors` + `independence` on held-out
  catalogue-zero proxies (50 px blocks, ≥ 32 negatives), both statistics (block MSE and block
  false-positive rate at a fixed budget), **ABANDON_R = 0.60**. Stored measurements: N-19 max
  |ρ| = 0.7625 (hide) → abandon; H62 block negative-FPR ρ = 0.1757 → pass. Both are reported;
  neither is suppressed.
* **Canary** — every channel's single-feature holdout AUC; alarm at **0.90**.
* If S1 fails, **pseudo-labelling is not run** (the brief's own rule) and disagreement is used only
  as (a) a stratification of the emission budget and (b) the source of the A-only geological
  reasoning. This is a **declared deviation from a pure co-training lane**, logged as IR-H66-001.

### 2.2 Emission (deterministic, no fit on the emission path)

1. `legal` = finite-footprint ∧ d(catalogue) ≥ 200 m ∧ ¬(labels > 0).  Footprint from
   `training_features.tif` band 12 finite: **5,165,852 px** (measured this session).
2. Seeds: unique sites with (temp_c ≥ 60) ∨ (reservoir T ≥ 100) ∨ (thermalclass Hot) ∧
   d(catalogue) ≥ 300 m ∧ legal. Evidence weight w = 1.0 (reservoir T ≥ 150 ∨ temp ≥ 100),
   0.7 (reservoir T ≥ 120 ∨ temp ≥ 80), 0.45 (reservoir T ≥ 100 ∨ temp ≥ 60), 0.30 (class Hot only).
3. Strike: structure tensor (σ = 4 px) of the edge-energy composite
   `E = mean of percentile-rank(|∇| of bands 12, 3, 18, 15)`; corridor = ±6 px along strike,
   perpendicular half-width 1 px, tip taper 1.0 → 0.4.
4. Corroboration `C` = percentile rank of `max(b3, b18, |∇b15|, |∇b17|, lidar step_max, Hessian-line
   of b12)`. **Hard gate C ≥ 0.50** on every corridor pixel.
5. Score `F = tapered corridor weight × w × (0.5 + C)`, emitted by `gems52.emit.greedy_emit`
   (coverage-greedy, hard-core) at the pre-declared budget ladder **{8,000 · 15,000 · 25,000 ·
   37,654}**; the shipped budget is the largest the gated corridor pool supports, capped at 37,654
   (the champion's mass, `knowledge/27` §6).
6. Stratification per emitted pixel from regional-percentile view fields A_rank / B_rank:
   concordant (A ≥ 0.7 ∧ B ≥ 0.7), **A-only** (A ≥ 0.7 ∧ B < 0.5) ⇒ *buried beneath cover*,
   **B-only** (B ≥ 0.7 ∧ A < 0.5) ⇒ *suspect surface artefact* (road, erosion line, fan head).
   B-only pixels with no seed within 3 px are **vetoed**. Geological reasoning is written for
   **every** A-only candidate (Phase-2 reviewers verify faults).

### 2.3 Holdout (the brief's hide-and-recover, leakage-free by construction)

Whole catalogue segments withheld with an 80 px buffer; **every catalogue-derived quantity is
recomputed per fold from the VISIBLE catalogue only** — in particular `d(catalogue)` for R-zero-tax
and for the seeds' 300 m exclusion — so a seed that sits next to a *hidden* segment stays legal and
the arm is genuinely tested on recovering hidden structure. Visible faults masked pixel-exactly
(`holdout.mask_visible`). Scored with the shared evaluator `gems52-pooled-hide-v1`
(α 0.2, β 0.8, 300 m triangular kernel, pooled TPw/FPw/FNw, 1,000-draw paired 20 km-cluster
bootstrap). Arms at matched budget and matched legal set: **TUC (candidate), single_A, single_B,
union_max, disagreement, random**. Label: **HOLDOUT-DTI**. Known defect carried forward:
**IR-H60-003 / N-9 — this instrument ranks the 0.2778 champion at 0.00479, below a random
placeholder (0.02229), and Spearman(board, instrument) = −0.099 (n = 13, p = 0.748). It cannot
promote or reject a candidate for this competition.** No number produced here is
ORGANIZER-CONFIRMED.

### 2.4 Release gates (all must be reported; PASS is not promotion)

format (single-band float32, EPSG:32611, shape 3,730 × 3,292, transform identical to
`sample_submission.tif`, values in [0,1], 0 NaN/inf inside the footprint); uniqueness against the
frozen 526-blob census (`evidence/ctd5_prior_inventory.json`, pixels re-materialised by
`scripts/fetch_prior_inventory.py` and SHA-checked) in **both** phases — surface rank correlation
(limit 0.90) and dots within 3 px (limit 0.70, literal **and** the repository's
universal-coverage-probe policy); exact novelty (no emitted cell positive in any *informative*
registry raster); not-the-union of the two views. Budget: **3 experiments, 2 h**. Slots used: **0**.

### 2.5 Prediction, written before the run

S1 will FAIL (View A has never exceeded 0.5362 on this splitter). TUC's HOLDOUT-DTI will be
**low** — the instrument's truth is the mapped catalogue, and TUC deliberately avoids it — but the
fold-recomputed-seed version is the honest reading and is expected to beat `random` and to beat
`single_A`. It is **not** expected to beat `single_B` on this instrument, and beating `single_B`
here would not be evidence of a board gain (IR-H60-003). The shipped verdict is therefore expected
to be **DOWNLOAD YES / SUBMIT NO (research-only)** unless the holdout and both lane phases pass.
