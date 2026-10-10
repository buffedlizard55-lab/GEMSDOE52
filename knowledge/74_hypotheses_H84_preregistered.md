# 74 — H84 hypotheses, pre-registered before any fit

Round **H84**, frozen 2026-10-10. Lane: the assigned **two-view co-training** method (Blum & Mitchell,
COLT '98, pp. 92–100, doi:10.1145/279943.279962). View A = potential-field and subsurface (gravity,
magnetics, geodetic strain, seismicity). View B = surface (DEM-derived curvature and slope, plus the
radiometric band actually present in `training_features.tif`). Disagreement is the discovery signal.

This document is **frozen before any fit**. Its SHA-256 is pinned in
`registry/h84_preregistration.json`. If the hash moves, `scripts/run_h84.py` refuses to run.

---

## 0. Three measured facts this round is built on (measured in this session, from restored bytes)

All rasters restored by `scripts/restore_data.py` and verified against
`registry/data_manifest.json` — 23/23 SHA-256 pins, `data/restore_receipt.json → all_ok = true`.

1. **The evaluation truth is faults that are NOT in the catalogue.** Official problem page, fetched
   2026-10-10 (<https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>):
   *"the sponsors have compiled a set of newly identified faults in the GeoDAWN region that are not
   included in the existing USGS fault database. These new faults … comprise the test dataset."*
   Consequence, and it is a hard constraint not a preference: emitted mass near a *mapped* trace earns
   zero `TPw`. This round therefore excludes a 200 m catalogue ring, exactly as the family does.
2. **`training_features.tif` band 6 is radiometric, not magnetic.** Measured from the organiser's own
   file: band 6 carries `data_category = magnetic_data` and description *"Tilt angle or total
   curvature"*, but its value range is 2.95–88.57 and `docs/data/h55_band6_identity.json` records
   Spearman 0.99995 against the GeoDAWN total-count grid and 0.9914 against K+Th+U, versus
   −0.025 against TMI (band 14). The tag is wrong; the band is the **aeroradiometric total count**.
   This is the only radiometric band in `training_features.tif` and it is used as View B input.
   Re-reported as an irregularity rather than silently relied on (see §6).
3. **Grid, measured:** EPSG:32611, 3730 × 3292, transform `(100, 0, 243350, 0, −100, 4508550)`.
   `labels.tif` is int8 with values `{−1: 7,111,787; 0: 5,106,385; 1: 60,988}`. In-domain footprint
   (`labels != −1`) = **5,167,373** px; the intersection of all 19 feature bands being finite =
   **5,165,840** px. The two differ by 1,533 px, so a submission that emits only on the feature
   intersection still has to write a finite value on those 1,533 px — this round writes 0.0 there.

Container evidence, also measured this session: of 12 owner-scored rasters restored into
`data/scored/` plus the 0.2778 reference, **11 are stripped/LZW with `nodata=nan` and 7,111,787 NaN
outside the footprint**, and **2 are all-finite with zeros outside and no nodata tag** — one of which
is `h33-2-b2-zeros.tif`, the 0.2778 file. Both containers have therefore been accepted by the portal.
The all-finite/zeros container cannot trip *"Predicted values must be in range [0, 1]"* under any
reader, NaN-honouring or not, so **H84 ships that container** and the reason is evidence, not taste.

---

## 1. H84-A — Locked-fault geodetic strain dipole (odd-symmetric fault-normal sign reversal)

**RANK 1 — the only candidate tested this round.**

* **Layers.** View A: band 8 *geodetic dilatation rate*, band 7 *geodetic shear rate*, band 4
  *geodetic second invariant* (all `geodetic_strain`), plus bands 13 *isostatic gravity anomaly* and
  18 *isostatic gravity anomaly horizontal gradient* as a **cross-family antisymmetry control**.
  View B unchanged: bands 12 *detrended elevation*, 19 *detrended elevation slope*, 6 *radiometric
  total count*.
* **Physical signature targeted.** A **signed, odd-symmetric profile response across the trace**, not
  an edge magnitude. For each pixel the local fault-normal direction `n̂` is measured from the fold's
  *visible* catalogue only (structure tensor over a 7 px-dilated trace corridor, axial resultant,
  `n̂ = ψ + 90°`, quantised to 8 compass directions — a disclosed approximation). The Gaussian-smoothed
  field `B` is sampled at `±h·n̂` for `h ∈ {1, 2}` px and decomposed into
  `odd = (B(+h) − B(−h))/2` and `even = (B(+h) + B(−h))/2`. Three statistics are emitted per
  (band, lag): `|odd|`; the **odd-dominance** `odd² / (|odd| + |even| + ε)`; and the **sign-reversal
  couple** `min(|B(+h)|, |B(−h)|) · 1[sign(B(+h)) ≠ sign(B(−h))]`.
  The discriminator is odd-dominance: a locked or creeping normal fault partitions geodetic strain
  into an **antisymmetric couple** about its trace — dilatant on one side, relatively contractile on
  the other — so the trace sits at a zero crossing of the dilatation field with a large odd part and
  a small even part. A lithologic contact, a basin-margin ramp, a road cut or an erosion line is a
  **monotone step**, which is even-dominant after centring. `|∇|`, coherence, tilt and variogram
  anisotropy are all sign-blind and cannot make that separation; this operator can.
* **Why it should catch a fault the catalogue does not have.** The USGS Quaternary Fault and Fold
  Database and the INGENIOUS fault layers are compiled from **surface-rupturing, geomorphically
  expressed** structures. A fault that is locked at depth, creeping without surface rupture, or buried
  under basin fill accumulates and partitions **geodetic** strain while producing no Quaternary scarp.
  It is therefore absent from the catalogue *by construction* while remaining visible in a
  GPS/InSAR-derived strain-rate field. This is precisely the lane's *"A confident and B abstains → the
  fault may be buried beneath cover"* quadrant, reached by physics rather than by a residual.
* **How it differs from anything implemented in this repository.** Every View A operator already built
  here is sign-blind or magnitude-based: gradient magnitude on bands 3/5/18/19, structure-tensor
  coherence, directional variogram anisotropy (H75, H82), tilt/RTP magnitude (killed as N-6, N-22),
  and raw strain band values (H74S-A, negative). A grep over `src/`, `scripts/`, `knowledge/`,
  `registry/` and `evidence/` for `dipole`, `odd_sym`, `strain_dipole`, `odd-symmetric` and
  `derivative of gaussian` returns **no implementation**. The only registered antisymmetry idea,
  **H57-C**, is a *cross-family edge-orientation* coincidence (`cos 2(θ_A − θ_B) → −1`), is recorded
  in `knowledge/18` §9 as *"registered as queued and never run"*, and never samples a signed profile
  along a fault normal. H84-A is a different operator on a different quantity.
* **The named non-fault process that could mimic it.** The geodetic strain layers are a smooth
  interpolation of sparse GPS/InSAR observations, so four mimics are expected and are named in
  advance: (i) **station-density gradients and block-boundary smoothing seams** in the interpolated
  velocity field, which produce signed couples with no structure at all; (ii) **magmatic
  inflation/deflation**, which is dilatant by definition and is the target signal of a geothermal
  system rather than a fault; (iii) **post-seismic viscoelastic relaxation** around the 1954 Fairview
  Peak and 1959 Hebgen Lake sequences; (iv) **elastic strain accumulation on an already-mapped
  fault**, removed by the 200 m catalogue ring rather than by the detector.
* **Cost.** Low. 20 View A channels; every one is an elementwise reduction of two shifted copies of a
  smoothed band, so no eigen-decomposition and no iterative solver.

## 2. H84-B — Cross-family magnetic–gravity antisymmetric edge coincidence (H57-C, executed)

**RANK 2 — not run separately.** The registered-but-never-run H57-C is *partially executed inside
H84-A* as the bands 13/18 odd-dominance control, so the cross-family antisymmetry question gets a
measured answer at zero extra cost. A full H57-C (orientation-pair `cos 2(θ_A − θ_B)` on
`mag_vg`/`mag_hg` against `iso_grav_vg`/`iso_grav_hg`) remains untested. Mimic: a susceptibility
contrast interface that is not faulted. Cost: medium.

## 3. H84-C — Depth-to-basement facet step under a surface-blank gate

**RANK 3 — not run.** Layers: band 15 *depth to basement surface* against band 19 *detrended
elevation slope*. Signature: a signed step in basement depth of several hundred metres whose surface
expression is absent (`slope` in its lowest decile), i.e. a buried range-front or intra-basin fault
under alluvium. Why off-catalogue: mapping follows scarp expression, so a basement step with no
scarp is systematically missed. Mimic: basement **paleotopography** (a buried valley or horst is not a
fault), basin depocentre axes, and inversion artefacts in the geophysical basement model itself —
which is smooth by construction and can produce steps at model-parameterisation boundaries. Differs
from H60/CTD5 cover-gating, which gated on conductivity and triple convergence rather than on a
basement-depth facet step. Cost: medium.

## 4. H84-D — Seismicity *alignment* rather than seismicity density

**RANK 4 — not run, and flagged as confounded before it is proposed as viable.** Layers: band 16
*earthquake intensity or density* and band 10 *distance to earthquake*. Signature: an anisotropic
line-tuned response requiring **elongation** at the measured fabric, not amplitude — Great Basin
faults are located by linear alignments of small events, and both provided bands destroy that
geometry by smoothing it into a scalar. Mimic: aftershock sequences and swarms.
**Confounding irregularity, read from the organiser's own band tag:** bands 10 and 16 are described as
*"(n=100km radius, a=15° azimuth parameters)"*. A kernel with an azimuth parameter is potentially
**anisotropic**, and a line-tuned filter would amplify a provider-imposed directional bias rather than
detect structure. That anisotropy must be measured before H84-D is treated as viable. No new external
data is required, so the source-obtainability test is satisfied; the blocker is internal, not access.

## 5. Ranking rationale, frozen

Rank 1 goes to H84-A because it is the only candidate whose signature is **odd-symmetric by physics**
and therefore separable from the even-symmetric lithologic and topographic steps that dominate this
family's false-positive population, and because it targets a specific, nameable catalogue blind spot
(no Quaternary surface rupture) rather than "more of the same structure". It also has the lowest
implementation cost. Ranking is qualitative priority, **not** a DTI forecast: no number in this
document predicts a leaderboard score.

## 6. Frozen protocol

* **Instrument.** `src/gems52/holdout.py::make_folds(mode="hide")` — hide-and-recover, whole 8-connected
  catalogue components withheld, prevalence-matched to 0.002 of the footprint, 4 folds, 8 px buffer,
  visible catalogue masked pixel-exactly. Scoring via `src/gems52/evaluate_holdout.py`
  (`gems52-pooled-hide-v1`, pooled DTI, α 0.2, β 0.8, R 300 m triangular kernel, 1000 paired
  physical-cluster bootstrap draws at 200 px block side). No private fork of any shared tool.
* **Budget per arm per fold.** 9,400 dots, 3 px minimum separation, inherited from
  `registry/h74_preregistration.json`.
* **Arms.** PRIMARY `A_ODD_gated` = View A odd-dominance field restricted to pixels where View B
  **abstains** (out-of-fold B probability below the fold median over the eligible pool) — the
  buried-fault quadrant. Controls: `single_A`, `single_B`, `A_ODD_ungated` (attribution),
  `B_conf_A_abstain` (surface-artefact suspects, reported not promoted), `random`.
* **Promotion rule, frozen.** Promote only if the primary's **paired 95 % CI lower bound against
  `single_B` is above zero**. Attribution arms are **not promotable post hoc**. If the rule fails the
  verdict is NEGATIVE and the artefact is research-only: DOWNLOAD yes, SUBMIT no, 0 slots spent.
* **Leakage canary.** Any single channel with out-of-fold AUC ≥ **0.90** on the held-out region is
  leakage until proven otherwise. Channels monotone in distance-to-visible-catalogue are demoted to
  diagnostics **before any fit**.
* **Independence.** `src/gems52/spatial.py::negative_block_errors` + `independence` on spatial-block
  out-of-fold errors of the two views over held-out catalogue-zero **proxy** negatives. Thresholds
  inherited **verbatim** from `registry/h74_preregistration.json`: donor rank 0.95, block side 50 px,
  abandon bar |ρ| > **0.60**, minimum 20 blocks. Not re-tuned for H84. If |ρ| > 0.60 the method is
  abandoned. Passing is necessary, not sufficient: exchange additionally requires View A sufficiency
  (mean OOF AUC ≥ 0.60, min fold ≥ 0.55), which has failed seven consecutive times in this repository.
* **Lane rule.** Check rank correlation and directed ≤3 px dot proximity against every aligned
  registry raster **on the surface before placement** and **on the final dots after placement**.
  STOP at Spearman ρ > 0.90 or > 70 % of dots within 3 px of one raster's dots. A stop is logged as a
  duplicate and no second placement is made.
* **Not the union.** Compare the authorized final candidate against `max(z_A, z_B)` and against each
  single view **at the same budget**, and report shared-cell counts and Jaccard.
* **Output.** Normalised to [0,1], binary {0,1} on the emission (the metric is linear in mass and the
  optimum is a corner, pinned in `tests/test_metric.py`), all-finite float32 with zeros outside the
  footprint, written through `src/gems52/grid.py` and re-read from disk before any claim.
* **Budget.** At most 3 experiments / 2 hours. A negative result is a deliverable.

## 7. Expected outcome, stated before the fit

`knowledge/49` measures, from two owner-scored files with a strict subset relation, that the board
satisfies `DTI = T / (0.2·S + 0.8·|G|)` with `|G| ≈ 14,089` and champion credit `T ≈ 5,223`
(37 % of `|G|`). Under that algebra a **fully novel** field is expected to score *below* 0.2778, and
the shortfall is the price of the lane's uniqueness rule, not a defect of the geology. This round's
realistic best case is a **measured improvement in out-of-fold AUC for View A** — the thing that has
failed seven times — and an honest negative on the board-facing question. Nothing here is a forecast.
