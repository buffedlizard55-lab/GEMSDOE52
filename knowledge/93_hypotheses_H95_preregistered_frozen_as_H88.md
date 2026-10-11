# 80 · H88 — hypotheses ranked, and the frozen preregistration (written before any H88 fit)

Written 2026-10-10 in the H88 session. Frozen by SHA-256 in `registry/h88_preregistration.json`.
`scripts/run_h88.py` refuses to start if this file's bytes change. The round identifier is H88 because
`main` already holds H87 (the README's last block, `scripts/build_h87_cotrain_wavelength.py`).

## 0 · What was measured *before* this document was frozen (diagnostics, no candidate involved)

These probes touched only the 13 owner-reported board files, the catalogue and the SGMC proxy.
No H88 field existed when they ran. Scripts and outputs: `scripts/h88_probe_*.py` (champion, board_instrument, board_instrument_segthin, lidar_coverage),
`evidence/h88_board_instrument.json`.

| probe | result |
|---|---|
| champion `h33-2-b2` bytes | 37,654 px, values exactly {0,1}, nearest dot 223.6 m from `labels.tif`, 5.77 % of dots within 300 m, median distance 1,965 m, median slope (band 19) 7.65 vs footprint 3.75 vs catalogue 5.56 |
| catalogue hide-and-recover truth vs board (n = 13) | Spearman **−0.490** (anti-correlated, consistent with IR-H60-003's −0.099 on a different arm set) |
| SGMC off-catalogue (≥ 3 px) truth, unthinned (63,121 px) | Spearman +0.162 |
| SGMC off-catalogue, **thinned by whole segments to |G| ≈ 10,000 px** (5 seeds) | Spearman **+0.567** (per-seed 0.567–0.580); **+0.911 excluding the universal-coverage lattice probe** |
| same, |G| = 6,000 / 12,500 | +0.567 / +0.580 (excl. lattice +0.911 / +0.928) |
| mass alone vs board (n = 13) | Spearman −0.889 |
| fraction of dots inside 1 m lidar coverage | 0.754–0.779 for every file (footprint 0.754), no discrimination; **abandoned** |

Reading: the segment-thinned SGMC instrument (`gems52-offcat-segthin-v1`) is the first instrument in this
repository whose ranking of scored files agrees in sign with the board. It largely tracks emitted mass, the
same thing mass alone does, so it is a **diagnostic**, not a score and not a promotion instrument. Its truth
is SGMC geologic-map faults, *not* the hidden expert faults: an SGMC-off-catalogue file was itself scored at
0.0512 on the board (owner-reported, GEMSDOE29 `sgmc-off-catalogue-44k`), so SGMC is a proxy population only.
Any field that uses SGMC as an input is leaky on it; no H88 field does.

## 1 · Candidate hypotheses (3–5), ranked by expected value ÷ cost

"Expected DTI" is an ordinal prior, never a projection. Repository grep before writing: lidar-scarp
channels have already been in View B (H57, H60d, H62, views54); Euler (H86), variogram anisotropy
(H75/H82/H84), geo-concordance (H85) and wavelength/Th-K (H87, unvalidated) are taken.

| rank | id | layers | physical signature | why it could catch a catalogue-missing fault | how it differs from the repo | cost | status |
|---|---|---|---|---|---|---|---|
| 1 | **H88-1 co-trained View B, scored on the board-anchored instrument** | View A: store `view_A_with_external` (bands 1–5, 7–11, 13–18 + derived gravity/cover/RTP gradients + TMI↑150 m). View B: store `view_B_with_external` (bands 6, 12, 19 + DEM curvature/slope derivatives + GeoDAWN K/Th/U and ratios) | surface curvature/slope discontinuities (B), potential-field edges (A); A→B whole-segment pseudo-labels where A is confident (rank ≥ 0.95) and B abstains (rank 0.35–0.65) | A-confident/B-abstaining segments are the brief's buried-fault population; giving them to B lets the surface learner extend into cover | every earlier lane round was judged only on the catalogue instrument, which ranks the board in the wrong order (ρ −0.49). H88 is the first to score the lane's arms on an instrument that ranks the board in the right order | low (shared H61 stages) | **primary, run** |
| 2 | **H87-V first holdout of the shipped H87 file's rule** | H87 hand-weighted View A (9 bands) and View B (wavelength contrast, slope, curvature, Th/K, U) | A > B disagreement emission | as H87 | H87 shipped without any holdout (its README: "No holdout DTI score yet") | very low | **run (closes previous session's next step)** |
| 3 | H88-3 mass lever on our own field | same field as the primary | fewer, higher-ranked dots | metric identity: each dot must clear ≈ 0.059 credit (knowledge/76 §3) | never tested on an instrument whose prevalence matches the board's | very low | **run as a pre-registered diagnostic on the SGMC instrument only** |
| 4 | H88-4 INGENIOUS 2-m temperature probes as a thermal View | GDR 1391 "2m Temperature Probes" (DOI 10.15121/1881483) | shallow thermal anomaly along a trend | fluid-carrying faults leak heat even without a trace | never used | — | **not viable in this sandbox**: `gdr.openei.org` is not on the egress allowlist (github.com, codeload, api.github.com, npm, pypi only). Needs an owner download with SHA pins. |
| 5 | H88-5 road/drainage artefact screen of B-only dots | View B orientation + slope aspect | cardinal-azimuth (section-line roads) or fall-line (erosion rills) alignment | removes the brief's named B-only mimics | `_disagreement_audit` in H77cond exists as an audit only | medium | deferred (budget) |

## 2 · Frozen protocol (H88)

* **Experiments (3 of 3):** E1 = H87-V holdout; E2 = H88-1 lane run (canary → fit → independence →
  one exchange → holdout); E3 = SGMC-instrument scoring of full-domain stitched fields + H88-3 mass lever.
* **Instrument for promotion:** `gems52-pooled-hide-v1` only (shared `gems52.evaluate_holdout`, label-blind
  quadrant folds, 80 px buffer, whole segments hidden, visible catalogue masked pixel-exactly, catalogue
  features from the visible catalogue only, α 0.2, β 0.8, R 300 m, 9,400 dots/fold/arm, 3 px spacing,
  200 m collar from the **visible** catalogue, paired physical-cluster bootstrap 1,000 draws).
* **Thresholds:** reused verbatim from `registry/h61_preregistration.json` (canary alarm 0.90, abandon
  if max |ρ| of block OOF negative errors ≥ 0.60, donor rank ≥ 0.95, receiver abstain band [0.35, 0.65],
  50 px blocks, ≥ 5 px segments, ≤ 2,000 pseudo px/fold, exactly one exchange).
* **Control reproduction:** `single_B` must reproduce H61's 0.174517 within 1e-3, else the run is invalid.
* **E2 arms:** `single_A`, `single_B` (single-view baseline), `union_max`, `disagreement_pre` (A-only),
  `cotrain_B` (= post-exchange View B, **primary**), `random`.
* **Promotion rule (SUBMIT YES):** primary HOLDOUT-DTI > **0.190147** (repo promotable best, H84 primary),
  AND paired CI of primary − `single_B` excludes 0 on the positive side, AND every gate passes (format,
  lane on surface and dots, uniqueness, not-the-union). Otherwise SUBMIT NO; the file may still be
  DOWNLOAD YES (format-valid research copy).
* **Abandon rule:** if the independence screen fires (max |ρ| ≥ 0.60) no exchange happens and
  `cotrain_B` ≡ `single_B`; the method is reported as abandoned.
* **E3 (diagnostic only, labelled PROXY-SGMC, never a score):** full-domain stitched OOF fields of the six
  arms + the H87 field, each placed with `nodes.spacing_select` (3 px) outside the 200 m collar of the
  full catalogue, at 37,654 and at 28,000 dots, scored against `gems52-offcat-segthin-v1`
  (|G| = 10,000, 5 seeds, mean) next to the champion and `d2-8` references.
* **Shipped file (fixed now):** primary field (`cotrain_B` stitched), 3 px spacing, 200 m collar,
  budget = whichever of {37,654, 28,000} scores higher on PROXY-SGMC (rule fixed before E3 runs);
  all-finite, 0 outside the footprint, values {0,1}, single-band float32 EPSG:32611 on the sample grid.
* **Lane check:** Spearman of the stitched surface and near-3 px share of final dots against every restored
  registry raster (`data/scored`, `data/reference`, `submission/`, `docs/downloads/`), bars 0.90 / 0.70,
  reported both literally and with universal-coverage probes (random-dot share ≥ 0.95) flagged.
* **A-only reasoning:** every shipped dot in the A-only stratum (A rank ≥ 0.95, B rank in [0.35, 0.65])
  gets a row with its measured channel values and the geological reasoning.
* **Budget:** 3 experiments or 2 hours. No submission slot is used by this session.
