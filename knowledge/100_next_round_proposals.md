# 100 · Next-round candidates, ranked by expected board gain per unit of cost

Written after H97 (negative) and its two geometry diagnostics, with everything below constrained to data
that is **already on disk and SHA-pinned** unless the row says otherwise. Costs are in sandbox CPU time
(2 cores available) and are estimates, not measurements; gains are stated as the *quantity that has to move*
(the metric's own terms) rather than as predicted leaderboard numbers, because this repository has measured
that its hide-and-recover instrument does not rank the board (Spearman ≈ −0.10 over R4, `knowledge/10` §5).

The metric, verified from the organiser's page this session:
`DTI = TPw / (TPw + 0.2·FPw + 0.8·FNw)` with `FNw = |G| − TPw`, hence
`DTI = TPw / (0.2·TPw + 0.2·(S − M) + 0.8·|G|)` — see `knowledge/98`.

---

## Ranking summary (revised after E4b ran — the first draft's rank 1 is now falsified)

The first draft of this note ranked *coverage emission of the surface-anisotropy field* first. E4b ran the
same session and killed it (table below), so the ranking now starts with the instrument that must exist
before emitted mass or emission shape can be tested at all.

| # | candidate | expected effect on the metric's terms | cost | new external data? | verdict |
|---|---|---|---|---|---|
| 1 | **Prevalence-matched off-catalogue instrument (H89-P)** | does not score; makes the mass lever *certifiable* | medium (~1 h) | no | **do first** |
| 2 | **Alteration-ratio anisotropy (Th/K, U/K, U/Th) as a third view** | new `TPw` where the scarp is gone | medium (~1.5 h) | no | test next |
| 3 | **Tip-and-stepover continuation gated by the surface fabric** | `TPw` at the ends of mapped faults | low–medium (~40 min) | no | test |
| 4 | ~~Coverage emission of the surface-anisotropy field (trace instead of dots)~~ | — | — | — | **FALSIFIED by E4/E4b — do not retry** |
| 5 | **Two-metre temperature-probe thermal anomaly as a View-A channel** | new `TPw` on the hidden population | high | **YES — not obtainable here** | blocked |

### The E4/E4b geometry result in one table (4 folds, 53,186 withheld positive px, mass-matched)

With the mandatory random control (`evidence/h97_e4_coverage.json`, `evidence/h97_e4b_hysteresis.json`;
interpretation and its limits in `knowledge/99` §7–§8):

| field | dots @ 9,400 | trace @ matched mass | dots @ matched mass | random @ matched mass |
|---|---:|---:|---:|---:|
| `cotrain_disagree` (H97 primary) | 0.029460 | 0.024497 bridge / 0.021537 hysteresis | **0.201789 / 0.238451** | 0.178690 / 0.196837 |
| `single_B2` (surface anisotropy) | 0.185968 | 0.153403 bridge / 0.144522 hysteresis | **0.254062 / 0.248644** | 0.176328 / 0.196093 |

Two independent trace constructions both lose to the same mass spent as well-separated dots, on both fields,
with paired CIs excluding zero — and both also lose to *random* at the same mass. That is a statement about
this instrument (truth = the mapped catalogue, mass ~4× real prevalence), not about the board.

---

## 1 · Prevalence-matched off-catalogue instrument (H89-P) *(rank 1)*

* **Layers.** `data/labels.tif` (the catalogue) and `data/external/derived_sgmc_faults_100m_u8.tif`
  (SGMC faults) — both already restored and SHA-pinned.
* **Physical signature targeted.** None — this is an *instrument*, not a detector: it thins the
  off-catalogue truth set to the prevalence the competition implies (`|G| ≈ 5,949–12,512` px, the bracket
  pinned in `knowledge/76` §2) so that a budget curve measured on it is meaningful.
* **Why it matters more than another detector.** The single largest unspent lever in the project is emitted
  mass (`Spearman(mass, score) = −0.93` across the family's twelve scored files), and `knowledge/76` §6 states
  that the existing off-catalogue instrument cannot test it because its truth is ~4× the real prevalence.
  §1a above shows the catalogue instrument cannot test it either (random placement improves with mass).
* **Why it now ranks first.** E4/E4b show that on the catalogue instrument *mass alone* dominates every shape
  decision (`random@S` reaches 0.177–0.197 while every trace construction loses), and the only off-catalogue
  instrument in the repo carries ~4× the true prevalence, so neither instrument can certify a mass change.
  The largest unspent lever in the project is emitted mass (`Spearman(mass, score) = −0.93` over the family's
  twelve scored files) and no existing instrument can measure it. Until this exists, every "emit more / emit
  differently" proposal is unmeasurable here.
* **How it differs.** H83's `gems52-offcatalogue-v1` / `-b-v1` are the only off-catalogue instruments that
  exist; neither is prevalence-matched, and both were explicitly declared invalid for budget choice.
* **Falsifier.** Thinning changes nothing about the ranking of arms, or the thinned curve still rises
  monotonically with mass (which would mean the real optimum is not reachable by thinning alone and a
  reweighted (importance-weighted) objective is needed instead).
* **Cost.** Medium: ~1 hour including the thinning calibration and a full 4-fold × 6-arm pass.

## 2 · Alteration-ratio anisotropy as a third view *(rank 2)*

* **Layers.** The pinned external GeoDAWN radiometric layers already in `data/external/`:
  `geodawn_extensions_u8.tif` bands 1–3 (Th/K, U/K, U/Th) and `geodawn_rad_u8.tif` bands 1–3 (K, Th, U).
* **Physical signature targeted.** The H82 `DVA2` operator applied to the **alteration ratios** rather than
  to topography: directional anisotropy of the K/Th/U field, i.e. a texture that tracks
  hydrothermal alteration rather than topographic relief.
* **Why it should catch an off-catalogue fault.** Alteration halos around a fault's damage zone persist after
  the scarp has been eroded or buried, so the ratio field can carry structure where the DEM cannot.
* **How it differs.** Radiometrics have been used in this repository only as per-pixel ranks/gradients inside
  View B (`gems52.external`, H96 §2's channel gap). No directional-texture operator has ever been applied to
  the ratio bands, and the ratio bands were never in a view of their own.
* **Named mimic and control.** Airborne gamma-ray **flight-line striping is directional by construction** —
  the single most dangerous artefact for this exact feature. The round must therefore include a striping
  control: the same operator on a **rotated** version of the grid (or on the ratio of the same grid to its own
  along-line median), and it must show the signal is not the survey geometry. Without that control the
  hypothesis is not testable, and it should not be run.
* **Cost.** Medium (~1.5 h): one channels pass over 6 external bands at 5 lags (the operator costs ~30 s per
  band at 5 lags, measured in H97) plus one fit/holdout pass.

## 3 · Tip-and-stepover continuation gated by the surface fabric *(rank 3)*

* **Layers.** `data/labels.tif` (visible catalogue, per fold), the H82/H97 surface anisotropy field, and the
  store's `B_*` DEM columns.
* **Physical signature targeted.** The **along-strike fabric of the surface field beyond a mapped fault's
  tip**: if the local anisotropy ridge continues in a stable direction for N pixels past the tip, the mapped
  fault probably continues there and was truncated by mapping practice, not by geology.
* **Why it should catch a fault the catalogue lacks.** A large share of the real gaps in a state-scale fault
  map are at *ends* of mapped traces (county lines, mapping extents, or where the scarp dies out). Those
  faults are in the hidden set by construction if the catalogue stops short of them.
* **How it differs.** The earlier continuation rounds (H16, H53/H54 "revealed core", H56 "consensus core")
  extend from a catalogue core using the **catalogue's own strike**, and H33d does tip-stepping on an
  analogue field. None of them *gates the continuation direction on the measured local anisotropy ridge*, and
  none uses the hysteresis ridge as the continuation carrier.
* **Falsifier.** Continuation cells added at matched mass score no better than the same mass spent on the
  unmodified field, or the continued traces leave the withheld-segment buffer (which the hide-and-recover
  instrument would catch as leakage).
* **Cost.** Low–medium (~40 min): no new channels; a ridge-following pass plus one holdout pass.

## 4 · Two-metre temperature-probe thermal anomaly as a View-A channel *(rank 4 — BLOCKED)*

* **Layers.** GDR 1391 "2 m Temperature Probes" (Great Basin Center for Geothermal Energy / INGENIOUS),
  DOI **10.15121/1881483**, CC BY 4.0 — <https://gdr.openei.org/submissions/1391>.
* **Physical signature targeted.** Shallow (2 m) temperature as a direct geothermal-expression channel;
  a positive thermal anomaly along a fault is the least indirect evidence available in this region.
* **Why it should catch an off-catalogue fault.** A buried fault with fluid circulation should show a shallow
  thermal anomaly even with no surface scarp — the exact population the competition rewards.
* **How it differs.** No thermal channel exists anywhere in `training_features.tif`, and no round has used one.
* **Obtainability check (required before proposing it as viable).** **FAILS in this sandbox.**
  `gdr.openei.org` is not on the egress allowlist (only `github.com`, `codeload.github.com`, `api.github.com`,
  `registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org` are reachable from bash), and the layer is not
  mirrored in any sibling repository in this family (`registry/data_manifest.json` carries seven external
  layers; none is thermal). **Owner action required:** download the file once from the GDR page into
  `data/external/`, record its SHA-256 and byte count, and add it to `registry/data_manifest.json` with
  provenance "GDR official release, DOI 10.15121/1881483, CC BY 4.0". Until that pin exists this is a plan,
  not a proposal.

## What must **not** be done next

* Do not spend a weekly submission slot on any arm whose holdout number has not first beaten the standing
  bar on the shared instrument; the selector owns that decision and this repository has used 0 slots so far.
* Do not re-`fit` a View-A-only arm again: eight consecutive sufficiency failures (`knowledge/99` §3) mean the
  potential-field view is a context/veto layer, not a learner.
* Do not re-try emission **geometry** as a coverage fix on the catalogue instrument: bridging (E4) and
  hysteresis growth (E4b) both lost to mass-matched dots *and* to random at the same mass. Reopening that
  question requires the prevalence-matched off-catalogue instrument (rank 1).
* Do not re-fetch the 526-blob prior census without budgeting for it; if it is needed, run
  `scripts/fetch_prior_inventory.py` as its own step and record the receipt (IR-H97-003).
