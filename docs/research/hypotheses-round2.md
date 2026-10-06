# Round-2 candidate hypotheses (GEMSDOE52)

This document is the canonical record of every geological hypothesis tested in this
repository, with the layer, physical signature, holdout result, and the failure mode
(if any). See `docs/hypotheses.html` for the human-readable version.

## H-A-COTRAIN &mdash; Geophysically-confident, topographically-silent A-only discovery

**Inputs.** View A = 17 bands: mag_anom, rtp, tmi_hg, geod_2ndinv, iso_grav_anom_slope, tc,
geod_shearrate, geod_dilaterate, tmi_vg, deq_n100a15, iso_grav_anom_vg, iso_grav_anom, tmi,
depth_to_base_surf, ieq_n100a15, cond_surf, iso_grav_anom_hg.

**Physical signature.** `HistGradientBoostingClassifier(max_iter=80, learning_rate=0.15,
max_leaf_nodes=21)` trained on the 3-quadrant complement of each held-out fold; out-of-fold
`P(positive | view A)` is computed for the entire footprint. The discovery rule keeps
cells where `(P(View-A) ≥ 0.55) ∧ (P(View-B) ≤ 0.30)` &mdash; A is confident, B abstains.

**Why it catches a fault the catalogue misses.** A buried fault beneath alluvial cover or a
clay-capped blind upflow column erases the topographic scarp that the surface view (B)
needs to fire; only the strain + seismicity + gravity-gradient signature in View A
remains. The disagreement rule is exactly the signal the prompt asks for ("where A is
confident and B is not, the fault may be buried beneath cover").

**How it differs from prior repos.** GEMSDOE32's H32-A uses a deterministic Odd/Even parity
decomposition on `iso_grav_anom` &mdash; same family of geophysical inputs but no
classifier, no independence gate, no per-cell A-band reasoning. GEMSDOE33-49 do not
implement the Blum-Mitchell rule anywhere.

**Holdout result.** 3,000 top-confidence cells: cat-hid 0.0007, sgmc_cal 0.06292,
drift 0.02856. Random-control at matched mass: cat-hid 0.039. The sgmc_cal improvement
(+0.00163 vs H32-D baseline) is small but in the right direction; the cat-hid
deterioration is expected (the discovery is off-catalogue by construction).

## H-B-COTRAIN &mdash; Topographically-confident, geophysically-silent surface artefact suspicion

**Inputs.** View B = det_elev, det_elev_slope, 4 GeoDAWN radiometric bands, 4 GeoDAWN
K/Th/U ratio + alteration indicators, 2 3DEP 1&nbsp;m LiDAR scarp channels.

**Physical signature.** Symmetric to H-A-COTRAIN; cells where `P(View-B) ≥ 0.55 ∧
P(View-A) ≤ 0.30` are flagged. Per the prompt these are kept *only* as the "suspect
surface artefact" branch (roads, terrace risers, erosion lines) and are capped at 200
pixels in the canonical submission.

**Why it catches an uncatalogued artefact.** The geophysical view is known to under-fire
on gentle cultural scarps (compacted dirt road across bedrock, ploughed terrace) where
the topographic view fires confidently. Flagging them prevents them from poisoning the
emission.

**How it differs from prior repos.** GEMSDOE32's H32-B uses a Kostrov transtensional
invariant, not a co-training disagreement rule. No prior repo discriminates the
"B-confident, A-abstains" branch as a suspect-artifact signal.

**Holdout result.** 200 top-confidence cells: not separately scored because they are
capped small and do not contribute meaningfully to the emission. The whole-segment
spatial-block filter (≥ 5 px connected components) ensures no isolated speckle reaches
the evaluation.

## Validation gates

| gate | value | required | result |
| --- | --- | --- | --- |
| Empirical independence of views (Pearson r on OOF residuals) | +0.190 | < 0.60 | **PASS** |
| Per-cell A-band reasoning coverage | 3,000 / 3,000 | 100% | **PASS** |
| Whole-segment spatial-block filter (no isolated single-px speckle) | 100% | 100% | **PASS** |
| Comparison against single-view baseline on holdout (H32-D) | +0.00163 sgmc_cal | > 0 | **PASS** (small) |
| Uniqueness gate (Jaccard vs every calibrated artifact) | 0.2810 | ≥ 0.01 | **PASS** |
| Not the union of two views | 0.2455 | ≥ 0.01 | **PASS** |
| 12-point DrivenData audit (range [0, 1], no NaN, 0 on-catalogue) | 12/12 | 12/12 | **PASS** |

## What was tried and failed (logged for the next session)

* **H-A-COTRAIN with a larger discovery budget (10,000 cells)** &mdash; cat-hid dropped to
  0.0014, sgmc_cal to 0.00076. Too many low-confidence off-catalogue cells dilute the
  emission without raising coverage of the verified SGMC off-catalogue truth.
* **H-A-COTRAIN as a *replacement* for the H32-D base** &mdash; cat-hid dropped to
  near-zero; sgmc_cal dropped to 0.005. A-only is too narrow without the multi-physics
  H32-D scaffolding to anchor the emission.
* **Adding B-only cells at the same mass as A-only** &mdash; B-only cat-hid 0.0108,
  sgmc_cal 0.0087. Including them at the same mass as A-only *reduces* coverage because
  B-only cells concentrate on roads and erosion lines, not on the SGMC off-catalogue
  truth.
* **Pruning H32-D cells within 1 px of catalogue and replacing with A-only** &mdash;
  cat-hid dropped from 0.10122 to 0.03219. The catalogue kernel covers the visible
  catalogue at 1-px adjacency, so removing those dots loses more credit than the
  off-catalogue A-only cells earn.

The strongest variant kept was **flank-3 prune + 3,000 A-only + 200 B-only**, which
scores cat-hid 0.00074, sgmc_cal 0.06292, drift 0.02856. The cat-hid is near zero by
construction; the sgmc_cal improvement over H32-D (+0.00163) is the relevant signal.