# 41 · H65 — the never-run queue, ranked, and the frozen gate this session runs

**Status: PRE-REGISTERED before any H65 code is run.** The SHA-256 of this file is recorded in
`registry/h65_preregistration.json`; `scripts/run_h65.py` refuses to start if that hash moves.
Nothing below was written after seeing an H65 number.

## 0 · Why this session does not re-run the co-training lane

The session prompt's method paragraph (two-view co-training, Blum & Mitchell 1998,
doi:10.1145/279943.279962) is the lane this repository has already executed to a frozen negative
verdict **six times**: H56 (independence premise fired, Spearman 0.637 > 0.60), H60D, H61 (View A
out-of-quadrant AUC 0.5163 against in-quadrant 0.948), H62, H62-buriedcorr, H63 (step-normalised
View A, 0.5362), H64 (capacity-cut View A, 0.5230; both against a preregistered sufficiency bar of
0.60). `AGENTS.md` says in terms: *"Do not re-tune it into a positive result, do not promote it."*
`AGENTS.md` also says: *"Read previous failed experiments before proposing another."* The same
prompt instructs: *"Before implementing, generate 3–5 candidate geological hypotheses we haven't
tried yet … Validate the top candidate on our spatially-blocked holdout set before touching a
weekly submission slot."* This preregistration does exactly that: it ranks the never-run
hypotheses and freezes the validation of the top-ranked one. The co-training instruments
(`evaluate_holdout`, `gates`, `submission_writer`, `cotrain_r5.make_folds`) are reused unmodified,
per the prompt's "REUSE, DON'T REBUILD" rule.

**Instrument note (stated up front, not discovered later).** The pooled hide-and-recover evaluator
(`gems52-pooled-hide-v1`) structurally cannot credit corridor mass: it withholds whole catalogue
segments and hides their traces from every catalogue-derived feature, so a corridor prediction —
which is defined *relative to a visible mapped trace* — cannot be placed on a hidden segment's
corridor at all, and dots around visible traces sit outside the withheld truth's kernel support.
`knowledge/33` §A-gate already anticipated this and defined a geometric gate that is spatially
blocked but does not depend on the hide-and-recover instrument. The final dots will still be
reported on the pooled evaluator, explicitly labelled as structurally ~0 on withheld-truth
corridors, so no number can be mistaken for a single_B comparison.

## 1 · The five candidate hypotheses this session ranks (all never run; sources checked)

Ranked by expected DTI improvement, then implementation cost, as the prompt requires. "Never run"
is verified against `knowledge/03` (organiser-scored refutations), `knowledge/33` §0 (local
refutations and the queued-never-run list), and `knowledge/39` §2.

### R5-H1 · Trace-correction corridor — **rank 1, validated this session (frozen in §2)**

* **Layers:** `labels.tif` mapped traces (geometry to be corrected, never fit as labels);
  LiDAR bands 6 `downface_max`, 7 `upface_max` (one-sided scarp step), 3 `step_max`, 1 `ex_max`,
  9 `relief`, 11 `strike`, 12 `valid`; features band 12 `det_elev`; features bands 2 `rtp`,
  3 `tmi_hg`, 9 `tmi_vg` held as the subsurface tie (unused by the gate estimator, recorded).
* **Physical signature:** a perpendicular offset estimator along each mapped trace; the scarp's
  one-sided LiDAR step (|downface − upface|), LiDAR-strike/trace-strike agreement, and the second
  derivative of detrended elevation along the trace normal together locate the true scarp crest at
  a signed offset of −3…+3 px from the mapped line.
* **Why it can catch a fault missing from the catalogue:** the organiser states the population
  exists — staff, forum topic 11516, 2026-09-21: *"A new-fault ground truth pixel can indeed lie
  within 300m of a known fault trace. Such pixels would constitute corrections or modifications to
  existing fault traces. Identifying these corrections is one outcome we are aiming for."* Problem
  description (page 967): *"portions of the existing fault data may be misaligned from the true
  location of the surface fault, which is the prediction target."* Verified quotes in
  `knowledge/25` §5.
* **How it differs from everything implemented:** every prior emission excluded the ≥1 px
  catalogue-adjacent corridor (`revealed.CORRIDOR_M = 200`) or filled it with a habitat field that
  hugged traces and measured ≤0.0132 credit/px. No prior round estimated a *signed perpendicular
  offset* from an independent scarp measurement. The champion's own corridor ring earned nothing,
  but that was that family's field, not a scarp-derived estimator.
* **Expected DTI improvement:** the largest available, because it is the only hypothesis whose
  target population the organiser has confirmed. Ordinal prior only — `knowledge/10` §5 records
  that the hide instrument cannot rank novel fields, which is why validation is the §2 gate.
* **Implementation cost:** medium (one estimator, one gate, one build; all layers already in
  `data/`).
* **Named non-fault mimic:** a lithologic contact or stream-cut bank parallel to the trace, whose
  one-sided step can imitate a scarp; secondarily a road cut with asymmetric cut/fill faces.
* **Data obtainability:** everything already restored and SHA-pinned (`data/restore_receipt.json`,
  23/23 pins verified 2026-10-09). No new external data needed.

### R5-H2 · Seismicity-azimuth corridors from band 10 `deq_n100a15` — **rank 2**

* **Layers:** features 10 `deq_n100a15` (distance-to-earthquake with a=15° sector parameter —
  in **no** view or family anywhere in this repo, verified against `cotrain_r5.VIEW_A_RAW` and
  `layers.FAMILIES`), 16 `ieq_n100a15`, strain bands 4/7/8 as the geodetic tie.
* **Signature:** rank-transform band 10 (its tail is "no event in sector"), then keep ridges of the
  directional derivative along the sector azimuth where the rank rises steeply one way and falls the
  other — the one-sided event asymmetry of an active fault block, not an isotropic cluster ring.
* **Why catalogue-missing:** a buried fault under basin fill has no scarp, radiometric contrast, or
  topographic expression, but still organises seismicity; this is the only input channel that sees
  structure with zero surface expression.
* **Differs:** band 10 has never been read by any script (verified this session). H56-6 needed an
  external ComCat bulk download that is not obtainable from this sandbox (host allow-list,
  `knowledge/39` §1.3); this uses the organiser's own regridded INGENIOUS product already in
  `training_features.tif`. Staff confirmed the band's provenance (forum topic 11557, 2026-10-07).
* **Expected:** medium — structurally valuable as an independent seventh family even if alone it is
  small. **Cost:** lowest of the five (one band, one transform). **Mimic:** an aligned
  geothermal/anthropogenic event swarm that is not fault-bounded.
* **Why not validated this session:** one gate per session is the budget; R5-H1 outranks it on
  organiser-confirmed population.

### R5-H3 · Basement-depth step gated by conductivity, tied by gravity — **rank 3**

* **Layers:** features 15 `depth_to_base_surf`, 17 `cond_surf`, 18 `iso_grav_anom_hg`, 11
  `iso_grav_anom_vg`, 5 `iso_grav_anom_slope`.
* **Signature:** a three-way AND — perpendicular curvature of band 15 above its 99th percentile, a
  cross-step conductivity contrast in band 17 of at least the footprint IQR, and a co-located
  maximum of band 18, with a veto where band 15 is negative (footprint min −14.84 m is a model
  artefact class).
* **Why catalogue-missing:** basin-margin normal faults buried by their own alluvial fans have no
  surviving scarp; USGS/INGENIOUS mapping is scarp-based, so they are absent from the catalogue by
  construction. What survives is the geometry of the fill.
* **Differs:** R4/R5 feed bands 15/17 to boosted trees as raw columns; nothing has ever combined
  them geometrically. H57-D (queued, never run) was an across-strike contrast at *existing*
  candidate traces; this generates its own candidates.
* **Expected:** medium-high *conditional on* band 15 being usable (its negative-value rate is the
  pre-checked risk). **Cost:** low-medium. **Mimic:** a facies boundary at the basin margin that is
  not a fault.
* **Why not validated this session:** budget; the artefact-veto check on band 15 must run first,
  which is a second gate by itself.

### H-spring · Aligned hot/cold springs at fault intersections — **rank 4**

* **Layers:** `data/external/gdr_wellspring_in_footprint.csv` (GDR submission 1391,
  <https://gdr.openei.org/submissions/1391>, CC BY 4.0 per its restored provenance; its
  `dist_known_fault_px` column is label-derived and excluded from use).
* **Signature:** ≥3 springs within 300 m on a common azimuth, or springs straddling two trend
  families at an intersection; emit the connecting line, ≥200 m off catalogue.
* **Why catalogue-missing:** spring alignment is an independent surface expression of
  fault-controlled permeability that the catalogue does not encode.
* **Differs:** H58-A used the same file chemically (geothermometers) and died on support capacity
  (22 of 37,654 nodes); this uses it geometrically. **Expected:** small (tens of springs).
  **Cost:** low. **Mimic:** aligned seeps along an alluvial-fan or drainage axis.
* **Why not validated this session:** support capacity is the known killer; R5-H1 dominates it.

### H-upHGM · Blakely–Simpson horizontal-gradient maxima on upward-continued TMI — **rank 5**

* **Layers:** features 14 `tmi`, external up-continued TMI (`geodawn_extensions_u8`).
* **Signature:** non-maximum-suppressed ridges of the horizontal gradient magnitude — the classic
  contact/fault-edge detector (Blakely & Simpson 1986, doi:10.1190/1.1442051).
* **Why catalogue-missing:** upward continuation suppresses near-surface noise, letting deep,
  cover-buried density/magnetic contacts surface as gradient maxima.
* **Differs:** closest prior art — the repo already killed magnetic transforms at 300 m (tilt,
  Laplacian, strain; AUC ≈ 0.52, `knowledge/03` N-6), so expected improvement is low; kept for
  completeness of the ranking. **Cost:** low. **Mimic:** any lithologic contact.

**Blocked (listed for completeness, not ranked):** ComCat relocated seismicity lineaments —
`earthquake.usgs.gov/fdsnws` is reachable only through the research fetch tool, which cannot write
files; bulk ingestion from this sandbox is impossible (`knowledge/39` §1.3, re-verified). The
named free official source, should a future session have a bulk path: USGS ComCat FDSN event
service, <https://earthquake.usgs.gov/fdsnws/event/1/>.

## 2 · H65 frozen protocol — the R5-H1 §A-gate (from `knowledge/33` §A-gate, implementation fixed)

All conditions below are frozen now. The gate is spatially blocked: held-out traces live in whole
20 km blocks, and the only fitted constant (the control offset of condition G3) is fitted on the
*other three* folds. No catalogue-derived feature enters the estimator: its inputs are the LiDAR
scarp bands, the LiDAR strike band, `det_elev`, and the held-out trace's own mapped geometry
(which the premise says may be mislocated — that is the thing being corrected).

**Units.** A *trace* is a connected component (8-connectivity) of `labels.tif` catalogue ∧ valid
footprint, with ≥ 10 px. Trace fold = modal 20 km-block fold (`cotrain_r5.block_ids` at
`BLOCK_M = 20_000`, `cotrain_r5.make_folds`, k = 4, seed = 20261009) over the trace's pixels;
ties → smaller fold id. A trace is scored in fold f *only* if every pixel used lies in fold f's
blocks; traces straddling folds are scored by their modal fold and excluded from cross-fold
control fitting (recorded counts published).

**Estimator (frozen).** For trace pixel p with ≥ 5 trace pixels in its Chebyshev-5 window:
(i) local trace strike θ_p = orientation (axial, mod π) of the first principal component of those
pixels, in the raster frame, expressed in degrees clockwise from +col axis to match the LiDAR
band's presumed convention (assumption A1 below); (ii) for each integer offset
o ∈ {−3, −2, −1, 0, 1, 2, 3} along the normal n̂(θ_p), sample point q = round(p + o·n̂); q is valid
iff inside the grid, LiDAR `valid` (band 12) > 0 at q, and the feature stack is valid at q.
Terms at q: **t1** = |downface_max − upface_max|; **t2** = (1 + cos 2Δθ)/2 with
Δθ = strike_LiDAR(q) − θ_p; **t3** = 2·det_elev(q) − det_elev(q−n̂) − det_elev(q+n̂) (second
difference along the normal; a crest is positive). Each term is compressed to [0,1] by frozen
footprint-wide percentiles v ↦ clip((v − p01)/(p99 − p01), 0, 1), percentiles computed once over
valid ∧ LiDAR-valid cells and logged in the receipt. Score(o,p) = mean(t1, t2, t3). Pixel vote
ô(p) = argmax_o Score.

**Trace estimate.** ô(T) = median of ô(p) over the trace's valid-vote pixels (integer).
Measured signed perpendicular error of T = ô(T).

**Assumptions recorded (not hidden):** A1 — the LiDAR `strike` u8 band encodes an axial angle
(0–180°) linearly across 0–255; A2 — the LiDAR bands are registered to the 100 m competition grid
they ship with (same shape/CRS/transform, verified at load); A3 — `downface`/`upface` measure the
one-sided step on the down-/up-thrown side of a scarp, so |difference| peaks on a real scarp and
is small on a symmetric ridge. A1 and A3 get a sensitivity note in the results file if the gate is
marginal (within 0.05 px of a threshold).

**A1 calibration (frozen amendment, written before any H65 code ran; disclosed because the band's
angular frame — datum, chirality — is undocumented and no prior round ever read band 11).** The
band's convention is *read off the data before any gate statistic exists*, as follows. Compute
θ_p for every valid trace pixel of every trace (the frozen PCA rule). For each of the four
candidate encodings e ∈ {θ, −θ, θ+90°, −θ+90°} applied to the band angle, compute the circular
resultant R_e of 2(θ_p − e(q)) over valid offset-0 points, and the mean resultant length r_e.
Choose the encoding with the largest r_e (ties → earlier in the list); log all four r_e values and
the chosen encoding in the receipt. This is a property of the band alone (a convention read, like
checking whether a raster is stored row-flipped), uses no gate outcome, applies uniformly to all
folds and to the final map, and cannot manufacture agreement if the band is noise (all four r_e
are then ≈ their chance value ≈ 0 and the choice is vacuous). If the best r_e < 0.10, term t2 is
reported as uninformative for this band and the gate is evaluated with t2 still included at its
honest (≈ 0.5) level — no re-weighting.

**Gate conditions (all four must hold):**

- **G1.** ≥ 200 held-out traces across the four folds.
- **G2.** median |ô(T)| ≤ 1.0 px over all held-out traces.
- **G3.** the estimator beats the best constant-offset control by ≥ 0.3 px in median absolute
  error: for each fold f, c_f = median ô(T) over traces of the other three folds; control error of
  T = |ô(T) − c_{fold(T)}|; require median(control error) − median(|ô(T)|) ≥ 0.3 px.
- **G4.** fraction of traces with ô(T) = 0 ≤ 0.5 (the estimator must not merely reproduce its
  input).

**Decision rule (frozen).** PASS → build the corridor emission (§3) and publish it with a
DOWNLOAD/SUBMIT verdict determined solely by the frozen build gates (format, uniqueness,
lane, not-union). FAIL → record the negative with all numbers; no corridor build; the session's
unique TIF obligation is still met by publishing a clearly-labelled research raster only if one
exists that passes every gate honestly — otherwise no TIF is published this round and the run card
records the negative. **No condition may be re-tuned after seeing gate numbers.**

## 3 · Emission build (only on PASS; frozen now)

* Centreline pixels: every trace (all folds, whole map) at ≥ 3 px spacing along the trace
  (greedy along row-major walk, Euclidean spacing ≥ 3 px between chosen centreline pixels).
* Each chosen pixel proposes target cells p + o·n̂ for |o| ∈ {1, 2, 3} in score order (the frozen
  estimator run once on all traces — it has no fitted catalogue parameters; the footprint
  percentiles are layer-derived only). The mapped line itself (o = 0) is never emitted.
* A proposal is eligible iff: inside the grid; not a catalogue pixel (pixel-exact); LiDAR-valid;
  feature-valid; not within 3 px Euclidean of an already-accepted dot (greedy, higher score wins);
  and — novelty tier 2 — not positive in any informative registry raster (the H64 frozen
  definition; universal-coverage probes excluded), re-placing at the next-best offset up to 12
  iterations per pixel, min 3 px spacing, and reporting the substitution count.
* Binary {0,1} float32, one band, written only through `gems52.submission_writer.write_submission`
  (which refuses NaN/inf/out-of-range and re-reads the file). CRS EPSG:32611, shape 3,730 × 3,292,
  transform identical to `data/sample_submission.tif`.
* Gates after write: format report; `gates.uniqueness_report` (tier 1 decoded-identity vs every
  census raster); `gates.lane_report` on the **surface** and on the **final dots** (literal +
  saturation-policy verdicts); rank-correlation vs every census raster (drift limit 0.90);
  not-the-union-of-the-two-views check for the record. Drift rule: if rank-correlation with any
  registry raster > 0.90 or > 70% of dots within 3 px of one raster's dots → log DUPLICATE and
  stop (this session's lane).
* Per-emitted-cell reasoning CSV (Phase-2 reviewer channel): trace id, offset, the three measured
  terms, the score, distance to catalogue, and the template hypothesis sentence. Labelled as
  measured context + hypothesis, not field-verified geology.
* The run card JSON is written with every number labelled HOLDOUT-DTI / ORGANIZER-CONFIRMED /
  PROJECTION / MEASURED-LOCAL, and a verdict of promote / negative.

## 4 · Budget

Three experiments: (E1) the §A-gate; (E2) the build + all gates; (E3) the final-dots receipt
(pooled hide evaluator reported for the record with its structural caveat, plus lane/uniqueness on
final bytes) and publication. Two-hour wall-clock cap; whichever comes first stops the round.

## 5 · E2 amendment — written after E1's FAIL, before any E2 number exists

E1 result (evidence/h65_gate.json): **FAIL** — G1 1,584 traces (pass), G2 median |ô| = 1.000 px
(pass at the boundary), **G3 margin 0.000 px vs the 0.300 px requirement (fail)**, G4 frac-0 =
0.356 (pass); A1 calibration found r = 0.086 < 0.10, so the LiDAR strike band was carried at its
honest ≈ 0.5 level (t2 uninformative, as frozen). Reading: the votes concentrate at ±1 px
independently of the local scarp evidence — a constant shift does as well as the estimator — so
the one-sided-step mechanism carries no locally-localizable trace-offset signal on this footprint.
Per §2's frozen decision rule, the corridor build is cancelled and R5-H1 is recorded as refuted
at gate level. The organiser-confirmed corridor population remains real; what is refuted is *this
estimator's ability to localize it with the layers named*.

E2 therefore runs the rank-2 hypothesis of §1, **R5-H2**, in a convention-free simplification
labelled **R5-H2a**:

* **Why the simplification:** knowledge/33 R5-H2's directional-derivative form needs the sector
  azimuth of band 10 (`deq_n100a15`, "a=15° azimuth parameters"), which is documented only in
  INGENIOUS `eq_rate_density_details.docx` — not obtainable from this sandbox (GDR host not on the
  allow-list; verified in knowledge/39 §1.3). The frozen substitute needs no convention: recent
  seismicity clusters *on* active structures, so a fault trace is a **valley line of the
  distance-to-earthquake field**. Detector: v = 1 − rank01(band 10) over the footprint; smooth
  σ = 1 px; keep pixels that are local maxima of the smoothed v along the gradient direction of v
  (non-maximum suppression perpendicular to the line) with v above the footprint's 90th percentile.
  Band 10 has never been read by any script in this repository (re-verified this session), so the
  field is maximally unlikely to collide with any registry raster.
* **Validation (before any slot):** the shared hide-and-recover instrument, exactly as
  `scripts/n2_holdout.py` runs it — holdout.make_folds (mode "hide", 4 folds, buffer 4,
  prevalence 0.002, seed 0), pooled DTI α 0.2 β 0.8 R 300 m, budget 15,000 dots (the family
  credit-curve optimum S* = 4|G|β/(1−β) ≈ 16,700 at |G| ≈ 14,089, β = 0.2284 — the template's own
  15,000), arms: candidate vs single_B (logistic on DEM/slope/radiometric rank features, the
  committed comparable control) vs uniform random. Leakage canary: fold-level AUC of v alone at
  the fit pixels; alarm at 0.90. Known instrument caveat carried: knowledge/10 §5 — this
  instrument cannot rank novel fields; single_B's committed 0.174517 (evaluator
  gems52-pooled-hide-v1, 53,186 withheld positives) is the reference bar.
* **Decision rule (frozen):** the E2 numbers choose only the *published verdict* on the session's
  unique TIF: candidate beats single_B (paired CI lower bound > 0) → SUBMIT-ELIGIBLE (selector
  decides the slot); otherwise → DOWNLOAD YES (if format/unique/lane gates pass) with SUBMIT NO.
  No gate may be re-tuned after numbers.
* **File build (frozen):** the same detector on the whole map (no folds), dots = top 15,000
  cells of v subject to: valid footprint, not a catalogue pixel (pixel-exact), ≥ 3 px Euclidean
  from an accepted dot (greedy, higher v wins), and novelty tier 2 (cell not positive in any
  informative registry raster; probes excluded per the H64 frozen definition) with greedy
  re-placement at the next-best cell, max 12 iterations, logged. Binary {0,1} float32 through
  `gems52.submission_writer.write_submission`; then format gate, decoded-identity uniqueness,
  lane_report on surface and final dots (rank-correlation limit 0.90, near-dot limit 0.70,
  radius 3 px; breach → log DUPLICATE and stop), not-the-union-of-the-two-views check for the
  record, per-dot reasoning CSV, run card JSON with every number labelled.


### E2 implementation amendment 2 (before any valid E2 number; run 1 was void)

Run 1 (kept as ``evidence/h65_e2_holdout_invalid_run1.json``) is void: the template's
``transform.rank01`` is an equal-width 4096-bin CDF over the band's raw range; band 10 spans
0 to 4.96 x 10^6 m in-footprint and **66.6 % of the footprint falls in the first bin**
(measured: rank01 min = p50 = 0.6663), so the smoothed field is constant at its own p50 = p90
and the strict p90 threshold empties the field (ridge_px = 0).  No E2 number in that receipt is
informative.  Two frozen corrections, both mechanical reads of the band, not tuning:
(i) E2 ranks band 10 with an exact tie-aware rank (``scipy.stats.rankdata`` over the valid
footprint, divided by the footprint count) instead of ``rank01``; the shared template tool is
deliberately left untouched because committed H55/H61/H64 receipts depend on its current
behaviour -- recorded here instead of silently forked (brief rule 2);
(ii) the NMS comparison keeps ``>=`` (plateau-safe).  Everything else in section 5 is unchanged.
