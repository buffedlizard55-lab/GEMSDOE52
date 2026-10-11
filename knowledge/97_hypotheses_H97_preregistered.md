# 97 · H97 — hypotheses ranked, and the frozen preregistration (written before any H97 fit)

Written 2026-10-10 (session branch `arena/7947af94-gemsdoe52`). Frozen by SHA-256 in
`registry/h97_preregistration.json`; `scripts/run_h97.py` refuses to run if these bytes move.
Round label H97: `main` (7eb226d) already holds H83–H96, and a repository grep found no `h97`/`H97`
artefact other than incidental substrings inside compressed files.

## 0 · Starting point (what is settled; not re-litigated here)

* Holdout bar to beat: **0.190147** (H84 primary `B_DVA2_HVA`, HOLDOUT-DTI `gems52-pooled-hide-v1`,
  53,186 withheld px). Holdout best overall: `B_DVA2` **0.192829** [0.170790, 0.213691] (same instrument).
* View A has failed sufficiency nine times (OOF AUC ≈ 0.50–0.53). Pseudo-label exchange A→B has never
  beaten single-view B (H61, H95: −0.0022 [−0.0062, +0.0017]). The A-only stratum scored below random on
  the catalogue instrument (H93 0.0353 vs 0.0804).
* H96: within a co-training structure the *consensus* arm was the best (0.0824) and the next step named
  there was "graft the disagreement arm onto the strong H82/H84 surface channels".
* H95 deferred item H95-5: "road/drainage artefact screen of B-only dots (cardinal-azimuth and fall-line
  alignment) — targets the brief's named B-only mimics". Never run. H84 measured only the cardinal
  fraction of B-only candidates as an audit (no veto, no holdout).
* **Irregularity found while designing this round (IR-H97-001):** the "View B" learner `B_DVA2` (H82/H84,
  the holdout best) includes directional-variogram channels of bands 13 (isostatic gravity), 15 (depth to
  basement) and 18 (gravity horizontal gradient) — `run_h82.BANDS`. Those are View-A physics. The holdout
  best is therefore **not a pure surface view**, so its "B-confident / A-not" disagreement is partly
  A-vs-A. H97 adds the lane-pure `B_DVA2s` (DVA2 of bands 12 and 19 only) and reports both.

## 1 · Candidate hypotheses (ranked by expected DTI gain ÷ cost; "expected" is an ordinal prior, not a score)

| rank | id | layers | physical signature | why it could catch a catalogue-missing fault / remove a non-fault | how it differs from the repo | cost |
|---|---|---|---|---|---|---|
| 1 | **H97-1 fall-line/cardinal artefact veto of the B-only stratum** (primary) | View B field `B_DVA2` (OOF), View A field `single_A` (OOF), band 12 detrended elevation (Hessian + gradient, σ = 2 px), band 19 slope | In B-confident/A-not cells, the local linear feature's axis (Hessian eigenvector of the *smaller* \|curvature\|) is compared with the downslope direction. Gullies, rills and drainage lines run **down** the fall line; fault scarps (Wallace 1977, GSA Bull. 88:1267, doi:10.1130/0016-7606(1977)88<1267:PAAOYF>2.0.CO;2) are steps whose crest runs **across** slope. Section-line roads/fences run exactly N–S/E–W on low-slope valley floors. Those cells are demoted below every other cell; the freed budget goes to the next-best cells. | Precision lever: each dot must clear ≈ 0.2·DTI of kernel credit; removing artefact-type B-only dots and refilling with the next-ranked cells raises credit per dot if the brief's reading of B-only cells is right | First veto/holdout of the B-only stratum. H84 only *counted* cardinal B-only candidates; nobody used fall-line geometry; no round used the Hessian axis | low (no refit) |
| 2 | H97-2 consensus graft | `B_DVA2` × `single_A` | r_B·(0.9 + 0.1·r_A): A as a tie-breaker inside B's ranking | H96: the intersection carried the weak signal; H95 next-work #5: "use A only as a soft prior inside B's confident set" | never applied to the strong surface field | very low |
| 3 | H97-3 contour-parallel prior without disagreement | `B_DVA2`, band 12 | r_B·(1 − 0.25·FL) everywhere | separates "geometry helps" from "disagreement-conditioned geometry helps" | new | very low |
| 4 | H97-4 lane-pure View B (`B_DVA2s`) | store View B + DVA2 of bands 12/19 only | directional variogram anisotropy of elevation/slope only | restores the two-view separation the lane requires (IR-H97-001) | new learner arm | low (one fit/fold) |
| 5 | H97-5 INGENIOUS 2 m temperature probes as a thermal third view | GDR submission 1391 (https://gdr.openei.org/submissions/1391) | shallow heat anomaly along a trend | fluid-bearing faults leak heat even under cover | never used | **not viable here**: `gdr.openei.org` is not on this sandbox's egress allowlist (github.com, codeload, api.github.com, npm, pypi). Needs an owner download with SHA pins. |

## 2 · Frozen protocol

* **Experiments (3 of 3):** E1 = fit (`single_A`, `single_B`, `B_DVA2`, `B_DVA2s`) + leakage canary +
  independence; E2 = matched-budget holdout of all arms in §2 (veto arms need no refit); E3 = stitch, build,
  lane/uniqueness/format/not-the-union gates, write.
* **Instrument:** `gems52-pooled-hide-v1` via the shared `gems52.evaluate_holdout` (label-blind quadrant
  folds `gems52.spatial.folds`, 80 px buffer, whole segments withheld, visible catalogue masked pixel-exactly,
  catalogue features from the visible catalogue only, α 0.2, β 0.8, triangular 300 m kernel), 9,400 dots per
  fold per arm, `gems52.nodes.spacing_select` at 3 px, 200 m collar from the **visible** catalogue,
  paired spatial-cluster bootstrap 1,000 draws, seed = `run_h61.SEED`.
* **Learners:** `run_h61.learner_for` / `sample_for_fit` unchanged (shared). DVA2 channels computed by the
  shared `run_h84._compute_band` (identical to H82's operator). Channel files mmap-read through
  `run_h82.Bank` (digest-checked on open).
* **Ranks:** r_A, r_B = percentile ranks within the fold's allowed cells (holdout) or within each stitched
  fold region (build).
* **Orientation (fixed now):** on band 12 (z-scored over eligible), Gaussian derivatives at σ = 2.0 px:
  gradient g = (∂x, ∂y); Hessian H = [[∂xx, ∂xy], [∂xy, ∂yy]]. Feature axis u = eigenvector of the eigenvalue
  with the smaller absolute value. FL = |cos∠(u, g)| ∈ [0, 1], **defined** only where |g| exceeds its 25th
  percentile over eligible cells (FL = 0 elsewhere). Axis azimuth θ_u (image frame, axial); d_card = angular
  distance of θ_u to the nearest of {0°, 90°}.
* **Strata:** B-only = r_B ≥ 0.95 AND r_A < 0.65. A-only (for reasoning) = r_A ≥ 0.95 AND r_B ∈ [0.35, 0.65].
* **Artefact flags inside B-only:** erosion = FL ≥ cos 30° (0.8660); road = d_card ≤ 5° AND band-19 slope ≤
  its eligible median. Null fractions under isotropic orientation: erosion 60°/180° = 1/3; road (20°/180°)·½ = 1/18.
* **Arms (all at 9,400/fold):** `single_A`, `single_B`, `B_DVA2` (control), `B_DVA2s`, `random`,
  **`H97_veto`** (primary: B_DVA2 with erosion OR road B-only cells set to r_B − 2), `H97_veto_fl`,
  `H97_veto_card`, `H97_veto_s` (same veto on `B_DVA2s`), `H97_scarp_soft` (r_B·(1 − 0.25·FL)),
  `H97_consensus` (r_B·(0.9 + 0.1·r_A)).
* **Controls:** `single_B` must reproduce 0.174571 and `B_DVA2` 0.192829 within 1e-3 (both measured on
  this instrument by H84), else the run is invalid.
* **Leakage canary:** every learner channel *and* FL, d_card alone, direction-insensitive AUC against the
  fold's withheld truth vs region negatives (> 5 px from catalogue); alarm ≥ 0.90.
* **Independence (the lane's test):** `gems52.spatial.negative_block_errors` / `independence` on
  `single_A` vs `B_DVA2s` and vs `B_DVA2`, thresholds from `registry/h74_preregistration.json`
  (abandon if max |ρ| ≥ 0.60). If it fires, the veto arms are still reported but the co-training reading is
  abandoned. **No pseudo-label exchange this round** (closed negative twice; the disagreement is used as a
  veto set, not as training labels — so no pseudo-label can leak into the evaluation).
* **Promotion rule (SUBMIT YES):** `H97_veto` HOLDOUT-DTI > 0.190147 AND paired CI95 lower bound of
  (`H97_veto` − `B_DVA2`) > 0 AND controls reproduce AND no canary alarm AND literal surface lane PASS AND
  dot lane PASS (literal, or policy with universal-coverage probes excluded, both reported) AND uniqueness
  PASS AND format PASS AND not-the-union PASS. Otherwise SUBMIT NO; the file may still be DOWNLOAD YES.
* **Shipped file (fixed now, whatever the holdout says):** the primary rule applied to the stitched OOF
  fields; pool = eligible cells > 200 m from the **full** catalogue; 37,654 dots; placement
  `run_h73.place_lane` against the scored-only informative supports (limit 0.70), fallback
  `spacing_select` 3 px; values exactly {0,1}; 0.0 outside the footprint; no NaN; single-band float32
  on the sample grid via `gems52.submission_writer`.
* **Lane check:** surface (before placement) and dots (after) with `gems52.gates.lane_report` against the
  526-blob census (`scripts/fetch_prior_inventory.py`) + `submission/` + `data/scored` + `data/reference`,
  bars ρ 0.90 / near-3px 0.70.
* **A-only reasoning:** every A-only candidate (3 px spacing) on the shipped pool gets a CSV row.
* **Budget:** 3 experiments or 2 hours. No submission slot is used by this session.
