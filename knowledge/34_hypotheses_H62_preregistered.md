# H62 — hypotheses and protocol, preregistered 2026-10-09 **before** any H62 fit, score or artefact

Frozen file. One clarifying edit was made **before any fit** (section 1, the description of the H60-3
residual, after a discretisation check); the hash below is the post-edit hash and the registry
records the amendment. Its SHA-256 is recorded in `registry/h62_preregistration.json` before the first model
is fitted, and `scripts/run_h62.py` refuses to run if either hash has moved. Nothing below was
written after seeing an H62 result. Lane: the brief's two-view co-training paragraph (View A
potential-field/subsurface, View B surface, disagreement as the discovery signal).

Scope of this round: it answers the H61 handover item 1 ("change what View A is") with one
physically specified View A. It is **not** a new submission round. No emission is authorised by
this document.

---

## 0 · Why this, and what it must not repeat

H61 measured that View A (36 channels, raw and transformed potential-field and gravity layers)
reaches out-of-quadrant AUC **0.5163** while fitting its own quadrant at 0.92–0.95
(`evidence/h61_fit_checkpoint.json`). So the sufficiency premise of Blum & Mitchell fails for that
view. H61's handover asks for a *physically parameterised* View A whose out-of-quadrant AUC is
measured before any emission is built.

Already tried, and therefore not repeated (`knowledge/03_negative_results_and_what_they_killed.md` N-6):

* an **isotropic** basement-depth signed step at 300 m: AUC **0.5113**;
* magnetic transforms ≈ 0.52, strain-ratio Laplacian 0.4765, drainage asymmetry 0.4796.

The one physically specific candidate that was *registered but never reported* is H60-3, the
strike-projected basement step (`knowledge/25_hypotheses_H60_preregistered.md` §H60-3). Its layers
are in `src/gems52/h60.py` (`b15_step_nne`, `b15_step_nw`, `b13_step_nne`). **Its operator is
mis-specified** (§1 below), so H62 replaces it rather than reusing it.

---

## 1 · Operator audit of the H60-3 layer (measured, not asserted)

`src/gems52/h60.py` computes `|d1 + d2 − 2·arr| / PIX²` with `d1, d2` the array shifted ±1 px along
the strike unit vector. That is a **second difference along strike**. A fault offsets basement
*across* its trace, so the offset is constant *along* the trace and a second difference along strike
cannot register it. The second difference cancels a ramp, not a step.

Synthetic test (`scripts/h62_operator_audit.py`, receipt `evidence/h62_operator_audit.json`): a
400 × 400 px grid at 100 m with a 200 m basement step across a NNE line and a 0.002 regional
along-strike ramp. Measured mean response on the trace versus 20 px or more away:

| operator | on-trace mean | far mean | on-trace units |
|---|---:|---:|---|
| H60-3 along-strike second difference | 2.96e-05 | 1.0e-09 | 1/m² |
| cross-strike symmetric difference, d = 3 px | 1.970 | 0.000 | m |

The H60-3 on-trace value is about 1.5e-5 of the cross-strike response in the same grid. A
second check (run in a scratch test, not a receipt) separates the cause: with **no ramp** the
on-trace value stays at 2.96e-5 (order-1 shift) and 2.07e-5 (nearest-neighbour shift), while with a
**pure ramp and no step** it falls to the far-field level (9.0e-10 against 1.0e-9). So the residual
comes from the step's discrete pixels, not from the interpolation, and it is not the designed
signal. The layer is **flagged** (`registry/irregularities.json` IR-H62-001). Its published H60
outputs are not altered, and no number built on it is withdrawn here, but it is not reused.

---

## 2 · Hypotheses (ranked; the brief's 3–5 candidates, with status)

### H62-A — cross-strike, regionally detrended basement and gravity offsets as View A — RANK 1, **tested in this round**

* **Layers.** `training_features.tif` band 15 `depth_to_base_surf` (basement depth, units as published,
  unstated in the file's tags) and band 13 `iso_grav_anom` (isostatic gravity). Read through the
  shared store (`raw_band_15`, `raw_band_13`), not re-read from another file.
* **Operator.** For each strike set s ∈ {NNE 15°, NW 315°} with unit normal n_s, and offset
  d ∈ {3 px, 6 px} (300 m and 600 m):

  D_{b,s,d}(p) = | z_b(p + d·n_s) − z_b(p − d·n_s) |,  O_{b,s,d}(p) = | D_{b,s,d}(p) − G_σ[D_{b,s,d}](p) |,  σ = 15 px (1.5 km).

  The symmetric difference cancels any ramp of constant slope across the normal. The detrend
  subtracts a 1.5 km-scale mean, so a broad regional dip does not register as an offset.
  Eight features: b ∈ {15, 13} × s ∈ {NNE, NW} × d ∈ {3, 6}.
* **Physical signature.** A normal or oblique fault that offsets the basement or the gravity
  contact produces a finite, *localised* step across its trace (localised along strike, not a
  ramp). The off-trace response returns to the regional level within the detrend scale. This
  measures a step across a line, which H60-3 did not, and the isotropic 300 m step of N-6
  responds to any gradient, not to a line-normal step.
* **Why it could find a catalogue-missing fault.** A buried fault under alluvium has no scarp and
  no surface lineament, so the USGS/INGENIOUS surface catalogue does not contain it. A
  basement-depth or gravity offset across the same line can survive. That is the A-confident /
  B-abstaining case the lane was built to test.
* **Named non-fault process that could mimic it (required).** A **basin-margin or hinge line**: the
  basement deepens sharply across a flexural or stratigraphic hinge with no displacement. Also
  **density or lithologic contacts** in the basement (a gravity step without throw), and
  **interpolation seams** in the modelled depth grid along survey or model boundaries. The repo's own notes
  describe band 15 as a modelled basement depth (`knowledge/14_h55_edge_hypotheses_preregistered.md`,
  "modelled basement depth/cover"; `knowledge/31_h61_results_and_limits.md`, "modelled basement-depth step"); the file's tags do not say so, and this is **not independently verified**.
  So it may not be an independent measurement of depth. These are unresolved in this
  round.
* **Difference from everything already in the repo.** The isotropic step (N-6, 0.5113) has no
  strike projection and no normal restriction. H60-3 (§1) is an along-strike second difference. The
  H55 paired shoulders (`knowledge/11`) used the DEM (band 12), not basement depth or gravity. The
  R2 signed normal (`src/gems52/structural.py`) is a gravity–cover anti-alignment, not an offset.
* **Cost.** Low: about 8 grid transforms and one HGB fit per fold. No new data.

### H62-B — tilt-angle edge ridges from bands 9 and 3 (Miller & Singh 1994) — RANK 2, **not tested here**

* **Layers.** Bands 9 `tmi_vg` and 3 `tmi_hg`. Tilt θ = arctan(VD / THD).
* **Signature.** Zero-crossings of tilt approximate source edges. The published method is Miller &
  Singh (1994) *J. Applied Geophysics* 32, 213–217; the repo's band-6 check showed band 6 is not
  the tilt (`knowledge/30_..._H61` R3).
* **Why deferred.** Repo probes of magnetic edge transforms (N-6) sat at AUC ≈ 0.52, and H61 View A
  already contains bands 3 and 9. Expected gain low, and it would be a near-duplicate of H61 View A.

### H62-C — surface-artefact veto (roads, erosion lines) as a *precision* term — RANK 3, **blocked by data**

* **Signature.** Linear, low-relief, high-radiometric-contrast features in View B that the
  metric's false-positive tax penalises.
* **Blocked.** A road or drainage layer for the footprint is needed. The candidate free sources
  are USGS The National Map transportation data and NHD hydrography. Neither host
  (`prd-tnm.s3.amazonaws.com`, `nhd.usgs.gov`) is in this sandbox's egress allowlist (github.com,
  codeload.github.com, api.github.com, registry.npmjs.org, pypi.org, files.pythonhosted.org). **Not
  obtainable here**, so it is not proposed as viable this round.

### H62-D — credit localisation by terrain stratum (H61-D) — RANK 4, **deferred**

Needs no new data but was the H61 handover item 2. It informs where organiser-scored truth sits
and does not itself produce a file. Deferred to the next round because this round's budget is three
experiments.

---

## 3 · Frozen decision rules (checked by code)

1. **Folds.** `run_h61.setup()` → `gems52.spatial.folds` label-blind-quadrants-v2, buffer 80 px.
   The same four folds, training sampler (`run_h61.sample_train`, positives ≤ 20,000, negatives
   ≤ 60,000, seed 61052 + fold), learner (`run_h61.learner`) and held-out sample definition as H61.
   Results are therefore directly comparable to H61 View A and View B.
2. **Leakage canary.** Raw single-feature AUC of **every** H62 feature on every fold's held-out
   sample. Alarm at direction-insensitive AUC **> 0.90**. Any alarm drops that feature and is
   recorded; the run is not silently continued.
3. **Premise gate (the decision).** Let `m` be the mean over the four folds of the H62-A out-of-quadrant
   AUC, and `min` the minimum fold AUC. **PASS** only if `m ≥ 0.60` **and** `min ≥ 0.55`.
   The threshold 0.60 is the level at which a view can carry the lane's Blum–Mitchell premise
   forward. H61's view A sat at 0.5163, with one fold at 0.6011 and three at ≤ 0.5062.
4. **Controls.** The H61 View A and View B fits are reported beside H62-A from the stored H61
   receipts (`evidence/h61_fit_checkpoint.json`). They are not refitted, so the comparison uses
   identical numbers and no re-tuning.
5. **Falsification.** `m < 0.60` or `min < 0.55` ⇒ **NEGATIVE**: the physically specified basement
   and gravity offset does not carry out-of-quadrant information either. Then no holdout arm, no
   emission and no slot.
6. **If and only if rule 3 passes**, a matched-budget hide-and-recover comparison (H61 §3 arms,
   `gems52-pooled-hide-v1`) is authorised as the next experiment. It is *not* run in this round.
   Any emitted file would still need the lane gate, the not-union check, and a holdout result above
   the matched best control.
7. **Not an emission.** Nothing here writes a `.tif` or enters `submission/`. No competition
   upload is possible or intended. Outputs are AUC diagnostics labelled `HOLDOUT-DTI diagnostic AUC
   (not a DTI score)`, consistent with the H61 canary.

## 4 · Sources (for manual review; each checked this session)

* Blum & Mitchell (1998), *Combining labeled and unlabeled data with co-training*, COLT '98, DOI
  10.1145/279943.279962: https://dl.acm.org/doi/10.1145/279943.279962 (the ACM record; the page
  itself was checked, the pages 92–100 were not independently read).
* Miller & Singh (1994), *Potential field tilt — a new concept for location of potential field
  sources*, J. Applied Geophysics 32, 213–217. Cited in the reference lists of
  https://link.springer.com/article/10.1007/s00024-023-03375-y (checked via search, not the paper).
* Blakely & Simpson (1986), *Approximating edges of source bodies from magnetic or gravity
  anomalies*, Geophysics 51, 1494–1498. Cited in https://jesphys.ut.ac.ir/article_58910.html
  (checked via search, not the paper).
* Metric, format and dataset: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
* Masking clarification: https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4
* USGS GeoDAWN release, DOI 10.5066/P93LGLVQ: https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and
* Competition leaderboard (live check, 2026-10-09): https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/

## 5 · AI-use disclosure

An AI assistant wrote the code, this protocol and the review text. No geologist verified any
structure, no field observation was collected, and no organiser score, acceptance or leaderboard
gain is claimed for any H62 output.
