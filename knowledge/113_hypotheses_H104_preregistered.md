# 97 · H104 — preregistered hypotheses (frozen before any fit)

Machine-readable twin: `registry/h104_preregistration.json`
(frozen 2026-10-10T23:20:00Z, SHA-256 `8cd93f2290d002c82b9770887f79a220352aeb42a94c238b713abaaf5f6bad1f`,
frozen **before** the first fit of this round; the runner refuses to run on a hash mismatch).

Session branch: `arena/86f85e87-gemsdoe52`.

This file is the document the registration names in its `document` field. It is written after the
fact of the *registration* but **before** the analysis it governs, and it contains no result: every
number in it is an *input measurement* (taken with the shared tools on restored bytes), not an
outcome. Results are in `98_h104_results_and_limits.md`.

---

## 1. Lane (unchanged, inherited from the standing brief)

Co-training between

* **View A** — a geophysical / potential-field / subsurface view, and
* **View B** — a surface view,

with **disagreement as the discovery signal**, per Blum & Mitchell, *Combining Labeled and Unlabeled
Data with Co-Training*, COLT '98, pp. 92–100, **doi:10.1145/279943.279962**. The premise to test
empirically on labelled negatives is **conditional independence of the two views' errors**; if the
errors are strongly correlated the arm must be abandoned rather than reported.

## 2. The new mechanism the round registers

**Thermal-gap hypothesis.** A hot spring, or a well whose geothermometry indicates a high reservoir
temperature, that the *visible* fault catalogue cannot explain — i.e. whose distance to the nearest
visible catalogue fault is **> 3 px (300 m)** — is surface evidence of a fault **absent from that
catalogue**.

Why this is *not* a re-run of anything already closed in this repository (the `why_new` field of the
registration, verbatim):

> The GDR 1391 INGENIOUS well/spring catalogue (sha-pinned in `registry/data_manifest.json`) has been
> used in this repository only as smooth **distance** channels (`B_spring_dist`,
> `B_paleo_geotherm_dist`, the H58 cold-geothermometer field, H55/H57/H86 thermal priors). It has
> never been used as a **per-site existence test against the visible catalogue**, which is the
> mechanism registered here.

Measured motivation (inputs, not results):

| measurement | value | how |
|---|---|---|
| unique (row, col) sites in `gdr_wellspring_in_footprint.csv` | 12,570 | dedup of 27,092 rows / 6 layers |
| of those, "evidence" sites (T ≥ 30 °C ∨ quartz ≥ 100 °C ∨ cat ≥ 100 °C) | 1,331 | H58 rule |
| evidence sites inside the footprint | 1,324 | `grid` footprint |
| evidence sites **> 3 px from the full catalogue** | 1,106 | EDT to `labels.tif` class 1 |
| evidence sites within 300 m of the catalogue | 23.3 % | vs ≈14 % expected for uniform scatter |
| `dist_known_fault_px` (the file's own column) vs EDT to `labels.tif` | Pearson = Spearman = **1.0000** | re-measured this session |

The last row matters: the supply catalogue's own distance column is *exactly* the distance to
`labels.tif`, so the gap sites are not an artefact of a different reference geometry — the visible
catalogue genuinely does not explain them.

**Named non-fault process that could mimic this** (required by the brief, verbatim from the
registration): fracture mesh without a through-going fault; shallow aquifer / irrigation return
flow; lithologic contact or intrusive margin; basin-margin facies step; paleo-channel; road cut and
erosion lines (the vetoed B-only set).

## 3. Views and field (H96 specification, reused — not forked)

**View A** (`grav_hg` 0.22, `mag_hg` 0.18, `cover_step` 0.22, `seis_line` 0.13, `strain_step` 0.10,
`mag_vg` 0.10, `cond` 0.05) and **View B** (`slope` 0.25, `ridge_curv` 0.30, `topo_edge` 0.20,
`K_over_Th` 0.15, `tc` 0.10) are the H96 channel sets, read from the cached feature stack.

Field components: `consensus = a·b`, `buried = a·clip(a − b, 0, 1)`, `artefact = clip(b − a, 0, 1)`,
`shipped_field = (0.45·consensus + 0.55·buried)·(1 − 0.70·veto)` with `veto = rank01(artefact)` on the
positive support only.

## 4. Placement

`gems52.nodes.spacing_select`, priority order **thermal-gap dots first, co-training field second**;
minimum spacing 3.0 px; the visible catalogue masked pixel-exact; **3 px (300 m) collar** around the
visible catalogue. The collar is registered at 3 px, not 2 px, because the champion family shows the
≤ 200 m ring earns exactly zero credit (`knowledge/76` §§1, 7) and the hidden truth is not inside the
kernel of any *mapped* fault under that same measurement.

**Only this composition is writable.** The runner's field-fill budget is 9,400 px by default, so the
shipped composition is always at most 9,400 + (gap dots inside the 3 px collar) — it can never
silently become a full-budget replay of the H96 file.

## 5. Experiments

**E1 — hide and recover (`gems52-pooled-hide-v1`).** Whole-component label-blind quadrants,
`buffer_px=80`, visible catalogue masked pixel-exact. Arms, 9,400 dots per fold per arm:

| arm | what it measures |
|---|---|
| `thermal_gap_cotrain` | **PRIMARY** — gap dots first, co-training field fill |
| `thermal_gap` | gap dots alone |
| `thermal_gap_line` | gap sites projected onto the nearest lineament ridge |
| `random_gap` | random dots at the *same count as the gap arm in that fold* |
| `random_gap_full` | random dots at the full 9,400 budget (mass-matched control) |
| `random_uniform` | uniform random over the allowed support |
| `single_A` | View A alone |
| `single_B` | View B alone |
| `cotrain_bi` | bidirectional co-training field, no thermal gating |

**Primary claim:** `thermal_gap_cotrain > random_gap` with a paired 20 km spatial-cluster bootstrap
95 % CI excluding 0, **and** `thermal_gap_cotrain ≥ 0.192829` (bar from `evidence/h82_holdout.json`,
H82 `B_DVA2`).

**E2 — off-catalogue instrument (`gems52-offcat-prevalence-h104`).** SGMC fault pixels > 3 px from
`labels.tif`, thinned by whole 8-connected components (seed 9700) to ≤ 14,088 px, i.e. prevalence
matched to the `|G|` bracket (5,764–15,179; nested-pair inversion 14,088.7, `knowledge/76`).
**Ranking instrument only — never used to choose a budget** (IR-H95-003: the earlier board-anchored
proxy was explained by mass alone). E2 also reports a mass curve of the shipped ranking, labelled as a
ranking diagnostic and never as a score.

## 6. Gates (all frozen)

| gate | threshold |
|---|---|
| independence | `max |r|` of view errors on labelled negatives < 0.60, else abandon the exchange |
| leakage canary | any single feature out-of-quadrant AUC ≤ 0.90 |
| promotion | primary claim satisfied **and** primary ≥ 0.192829 **and** every gate PASS |
| format | `gems52.gates.format_report`: single band float32, EPSG:32611, 3730×3292, transform match, all-finite, values in [0,1] |
| uniqueness | `gems52.gates.uniqueness_report` over `submission/`, `docs/downloads/`, `data/scored/`, `data/reference/` |
| lane | Spearman ≤ 0.90 vs any registry raster **and** ≤ 70 % of dots within 3 px of any single registry raster; checked on the **surface** before placement and on the **final dots** |
| not-the-union | Jaccard vs the union of the two views' spaced top-k supports at the same budget |

## 7. Verdict rules

* **promote** — every clause of the promotion gate above passes.
* **negative** — anything else. The run card and the site must then read
  **OK TO DOWNLOAD: YES / OK TO SUBMIT: NO (research-only)**, and the round must **not** spend a
  weekly submission slot. Negative results are deliverables.

## 8. Budget

3 experiments, 2 hours, **0 submission slots** (promotion is the separate selector step).
