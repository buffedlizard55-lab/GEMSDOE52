# 88 · H92 hypotheses, ranked — frozen BEFORE any H92 fit

Written 2026-10-10 in the H92 session, on branch `arena/f57253db-gemsdoe52` (base commit `bc26fe2`,
README round H87). This file is hashed into `registry/h92_preregistration.json`; `scripts/run_h92.py`
refuses to start if either the file or the pin has moved.

Lane: **the brief's co-training paragraph**. View A is potential-field and subsurface; View B is
surface (DEM-derived curvature and slope, plus any radiometric bands present in
`training_features.tif`). The discovery signal is **disagreement**. Nothing here leaves that lane.

---

## 1 · What the repository has already measured (the honest prior)

| Fact | Source | Evidence class |
|---|---|---|
| View A, H61's raw potential-field channels, spatial-block OOF AUC | `knowledge/03`, `ACTIVE_CONTEXT` | 0.5163 mean over 4 folds, min 0.4309 — **anti-informative**, i.e. sufficiency fails |
| View B, H61/H82's DEM channels, spatial-block OOF AUC | `evidence/h82_holdout.json`, `ACTIVE_CONTEXT` | 0.6843–0.6849 — **the only measured repeatable signal** |
| **Directional variogram anisotropy (DVA)** — an 8-direction fan of lag-`h` semivariances, reduced to `(max−min)/(max+min)` and `log10(mean)` — is the best arm this repository has | H82 `B_DVA2`: HOLDOUT-DTI **0.189200**, mean OOF AUC 0.7124 | HOLDOUT-DTI, `gems52-pooled-hide-v1` |
| Every unsupervised, catalogue-free structural field tested so far sits at or below the random control (0.0754–0.0804) | H85, H86, H77's five detectors | HOLDOUT-DTI |
| **DVA has only ever been computed on bands 12, 19, 13, 15, 18** (`scripts/run_h82.py` `BANDS`) | grep of `run_h82.py`, this session | code read |
| DVA has **never** been computed on a magnetic band, on the radiometric band 6, or on the earthquake-density bands | grep of `run_h82.py` `BANDS` vs the 19-band tag list, this session | code read |
| Plain pseudo-label exchange on a non-sufficient View A *lowers* its OOF AUC | H71 (`knowledge/58`) | HOLDOUT-DTI |
| Holdout DTI and the public board are not correlated, Spearman −0.10 | `AGENTS.md`, IR-H77-005 | measured (cross-round) |

**Why this matters for the lane.** The brief says "Test the independence assumption empirically …
and abandon the method if they are strongly correlated." The repository has done the *independence*
half eight times (it keeps passing: max |ρ| 0.13–0.15 against a 0.60 bar) and the *sufficiency* half
eight times (View A keeps failing). Independence without sufficiency gives co-training nothing to
donate. So the scientifically interesting question this round is **not** "does plain exchange work"
(measured: no, H71) but **"can View A be made sufficient by changing its representation, using only
bytes already in the stack?"**

## 2 · Ranked candidate hypotheses (new, layer-named, mechanism-named, ranked by expected value ÷ cost)

| rank | id | layer(s) (band index, tag) | physical signature targeted | why it could catch a fault missing from the USGS/INGENIOUS catalogue | how it differs from everything already in this repo | cost | status |
|---|---|---|---|---|---|---|---|
| **1** | **H92-T "texture View A"** | **band 2 `rtp`** (reduced-to-pole magnetics), **band 9 `tmi_vg`** (magnetic vertical gradient), **band 13 `iso_grav_anom`** (isostatic gravity) | directional variogram anisotropy of the *potential field itself*: an elongated, laterally-persistent semivariance maximum at the fault strike, 100–600 m lag | a buried fault is a **correlated** magnetic/gravity boundary over hundreds of metres. Raw amplitude (what H61 fed View A) is dominated by the source body; the **anisotropy of the variogram** isolates the *boundary geometry* instead, which survives under cover | H82's DVA2 never touched a magnetic band, and never used the vertical gradient band 9 at all. This is a **representation change for the failing view**, not a re-tuning of the working one | medium (24 filters/band, reuse `run_h61.setup`) | **VALIDATED IN THIS ROUND — see §4** |
| 2 | H92-R "radiometric texture in View B" | **band 6 `tc`** (tagged magnetic TC; measured to be radiometric total count by bytes, IR-H85-005) | DVA + gradient texture of the radiometric surface: K/Th/U lineaments | hydrothermal alteration is *linear* along fault-fluid pathways; texture, not amplitude, is what a lineament is | the repo uses band 6 as a **raw channel** (`raw_band_06`) and as external radiometric *gradients*; it has never computed a **directional variogram** on it | low (folded into rank 1's fit) | tested as part of the rank-1 feature block |
| 3 | H92-S "seismicity lineation texture" | bands 10 `deq_n100a15`, 16 `ieq_n100a15` | DVA of earthquake density — a lineated epicentral trend | faults that are active but unmapped must show a directional seismicity trend | the bands sit in View A as *raw* channels; their texture has never been isolated | low–medium | **not run this round** (budget); named for the next |
| 4 | H92-B "cover-step texture" | band 15 `depth_to_base_surf` | DVA + oriented step in cover thickness | a buried normal fault offsets the basement surface under a flat top surface | H85-next-B named this but it has no holdout receipt; it is a *step* detector, not a texture | low | **not run this round** (budget) |
| 5 | H92-A "ASTER/EMIT alteration indices" | external | clay / iron-oxide / silica absorption indices | surface alteration halo around a fault-fed system | **not viable in this sandbox**: the egress allowlist is `github.com`, `codeload.github.com`, `api.github.com`, `registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org` (`knowledge/78` §6). USGS EarthExplorer / NASA Earthdata both require a login and are not reachable | high | **blocked — needs an operator-side download with a SHA pin first** |

Ranking is by (prior plausibility for a *catalogue-missing* fault) × (bytes already on disk) ÷ (cost).
**No expected-DTI number is given for any row**: nothing below has a validated estimate, and a
projection is never written as a score (`AGENTS.md`).

## 3 · Frozen H92 protocol (written before the first fit)

* **Primary arm `xtex_dis`**: `pct_rank(P_A) − pct_rank(P_B)` inside the allowed set, where `P_A` is
  the out-of-fold View-A *texture* learner and `P_B` the View-B texture learner. This is the brief's
  "A is confident and B abstains" emission, in the co-training lane.
* **Controls, matched budget, same allowed set, same seed family**: `single_Atex` (View A alone),
  `single_Btex` (View B alone), `xtex_agree` (`min(P_A, P_B)` — the consensus twin, so that a
  disagreement win cannot be explained by "more mass near the top of either view"), `random` (floor).
* **Budget**: K = 9,400 dots per fold per arm, `nodes.spacing_select(min_px=3.0)`, the 200 m collar
  and the emission domain built from the fold's **visible** catalogue only.
* **Evaluator**: `gems52.evaluate_holdout` (version `gems52-pooled-hide-v1`), α 0.2, β 0.8, 300 m
  triangular kernel, paired physical 20 km spatial-cluster bootstrap, 1,000 draws.
* **Folds**: `gems52.spatial.folds(cat, eligible, buffer_px=80)` — whole catalogue components, label-blind
  quadrants. The same splitter every prior round used, so numbers are comparable.
* **Sufficiency read**: per-view held-out-region OOF AUC (positives = the fold's withheld truth inside
  the region; negatives = region ∩ not-catalogue ∩ >500 m from any catalogue pixel).
* **Independence read (the brief's own test)**: Pearson correlation of the two views' **spatial-block
  mean errors on labelled negatives** (200 px = 20 km blocks), reported per fold with a bar of
  **0.90** (the brief's number) *and* the repository's stricter 0.60. Abandonment is required only if
  the brief's 0.90 bar is crossed.
* **Leakage canary**: each individual texture channel's own AUC against the withheld truth inside the
  allowed set; alarm above **0.90**.
* **Fixed a priori, never tuned on the holdout**: fan = the same 8 axial offsets H82 used,
  lags = (1, 2, 3) px, Gaussian σ = 3 px, standardization per band inside the eligible footprint.

## 4 · Result

Filled in after the run; see `evidence/h92_holdout.json` and `evidence/h92_run_card.json`.
The **verdict and every number are in those receipts**, not here. This section is deliberately not
written before the fit.
