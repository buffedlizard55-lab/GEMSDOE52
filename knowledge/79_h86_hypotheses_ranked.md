# 74 · H86 hypotheses, ranked — written before any H86 fit

Written 2026-10-10 in the H86 session. Scope: the brief asked for 3–5 candidate geological hypotheses
that the repository has not tried, each naming layers, physical signature, why it should catch a
fault missing from the USGS/INGENIOUS catalogue, and how it differs from what is implemented, ranked by
expected DTI improvement and implementation cost, with the top one validated on the spatially
blocked holdout before any slot decision.

**Honest prior.** The repository's own negative record (knowledge/03, N-6) says potential-field transforms
at the 300 m cell sit at holdout AUC ≈ 0.52, and H82/H86 measured structure-tensor and geothermal
channels at or near random. So no candidate below has a strong expected gain; the ranking is by how much
*new information* it adds, not by a claim of improvement. "Expected DTI" entries are therefore
ordinal priors, not projections, and are labelled as such.

Repository grep (this session, `src/` and `scripts/`): tilt/total-curvature (29 files), upward
continuation (16), structure tensor (21), lineament (44), scarp (67), radiometric (83), seismic (38) are
already implemented or used. `total horizontal`, `theta map`, `wavelet`, `resistivity`, `fault zone`: 0 files.
Euler deconvolution is named in `knowledge/43` as "already in the README's scored-file records"
(owner-reported sister submissions, e.g. `h38-1-…euler…` 0.2707), i.e. it is on the board but **not in this
repository's own pipeline**; it is new *to this repo*, not new to the competition.

| rank | id | layers (band index, tag from the file's own descriptions) | physical signature targeted | why it could find a catalogue-missing fault | how it differs from what the repo does | cost | status |
|---|---|---|---|---|---|---|---|
| **1** | **H86-E** Euler deconvolution, structural index 0 | band 2 `rtp` (field), band 9 `tmi_vg` (vertical derivative), horizontal derivatives from band 2 | depth-resolved source edges: Euler solutions (x0,y0,z0) cluster along contacts/steps at depth 50–1500 m | adds a **depth** constraint the 2-D transforms lack, so a buried step under cover can be located even where no surface expression exists | no depth estimate anywhere in the repo; tilt/curvature are depth-blind 2-D edge maps | medium (windowed 3×3 solves, ~3 min CPU) | **VALIDATED ON HOLDOUT in this session — see §Result** |
| 2 | H86-T theta map (normalised total horizontal derivative of tilt, Wijns et al. 2005) | band 2 `rtp` | equal-amplitude edge map of magnetic contacts | cheap alternative edge detector that does not saturate on strong sources | tilt angle is implemented (`tc`, 29 files) — theta is a re-normalisation of the same information, so low novelty | low | untested; ranked below 1 because the information is already in the repo's tilt |
| 3 | H86-H multi-azimuth hillshade lineament density | band 12 `det_elev` (DEM) | illumination-dependent linear relief | surface lineaments independent of the potential-field layers | scarp, curvature and lineament modules already cover DEM linearity (44 files) | low | untested; overlap with existing DEM lineament modules is high |
| 4 | H86-A hydrothermal alteration from ASTER/Landsat band ratios (e.g. clay/iron-oxide indices) | **external**: ASTER L1T/SWIR or Landsat 8/9 surface reflectance | surface alteration halo around active fault-fed hydrothermal systems | surface geochemistry independent of geophysics | **blocked in this sandbox**: egress allowlist is github.com, codeload, api.github.com, registry.npmjs.org, pypi.org, files.pythonhosted.org only; NASA/USGS bulk scenes cannot be downloaded here, so this cannot be validated in-session | high | **not viable in this sandbox — needs an operator-side download of a free official product (USGS EarthExplorer / NASA Earthdata, login required) first** |

## Why H86-E is first

Euler's method (Reid et al. 1990, Geophysics 55(1), 80–91, doi:10.1190/1.1442774) solves for the source position and depth from the field and its
gradients inside a moving window; the structural index sets the source geometry: for magnetic sources Reid & Thurston (2014, Table 1,
https://www.reid-geophys.co.uk/wp-content/uploads/2017/11/Reid-Thurston-2014.pdf) give SI 0 for an infinite
contact/fault, 1 for a thin sheet edge, 2 for a pipe or thin-bed fault, and 3 for a sphere. It is the only candidate above that adds an *independent axis*
(depth) to a repository that has measured every 2-D transform at chance. It is also the only candidate
whose failure mode is clean: if Euler solutions do not cluster beyond random, the holdout will show it.

Named non-fault mimics: dike swarms and intrusive contacts (SI 1 bodies would be mis-classified
by SI 0), basement steps from lithology rather than faulting, and window-edge artefacts. Structural
index choice was fixed before any fit (SI = 0), not tuned on the holdout.

## Not done in this session (honest limits)

* No candidate was tuned on the holdout. Window size (7 px), depth gate (50–1500 m), σ (1.5 px) were
  set a priori from the 100 m grid, not optimised.
* The vertical derivative sign convention of band 9 is taken as stored; if it is up-positive the
  depth gate will reject many solutions. This is a documented risk, not a verified fact (see the H86
  receipts for the accepted-solution count).
* Band 9 is a *stored* vertical gradient, so its units are whatever the organiser used; no unit check
  was possible from the file tags alone.

## Result — the top candidate was validated; it did not beat random

Protocol: `scripts/run_h86_euler.py` (H86-E, pre-registered SI 0, 7 px window, depth 50–1500 m, σ 1.5 px).
Same folds (`gems52.spatial.folds`, buffer 80 px, 200 m collar from visible catalogue), same budget
(9,400 dots per fold), same evaluator (`gems52-pooled-hide-v1`, α 0.2, β 0.8, R 300 m), same random seeds.
Numbers are from `evidence/h86_euler_holdout.json`, read by `scripts/publish_h86.py`.

| arm | HOLDOUT-DTI | 95% CI (paired cluster bootstrap) | withheld positive px |
|---|---:|---|---:|
| **H86-E Euler, SI 0** | **0.0777** | [0.0700, 0.0857] | 60,894 |
| random (same allowed set) | 0.0754 | [0.0675, 0.0834] | 60,894 |
| paired, Euler minus random | **+0.0022** | [−0.0030, +0.0072] | — |

* **Verdict: negative.** The CI of the paired difference spans zero, so there is no measured
  improvement over random. Euler is also far below the repo's comparable best reported by H82
  (0.1892), with the cross-run caveat in IR-H86-007.
* **Leakage canary:** per-fold AUC of the Euler score against held-out truth in the allowed set is
  0.515, 0.521, 0.531, 0.520 (max 0.531, alarm 0.90 → no alarm). Euler uses no catalogue, so the canary
  is a sanity check of the score, not of a leak.
* **Depth sanity:** 2,423,592 of 5,164,300 windows yield an accepted solution; median accepted depth
  207 m. Whether that shallow median reflects the sign convention of band 9 is untested (see §"Not done").
* **What this does and does not kill.** It kills SI-0 Euler on the 100 m grid with these windows.
  It does not test SI 1, other window sizes, or the upward-continued field, and those would be new
  experiments that the 3-experiment budget does not cover in this session.

## Budget used

Experiments: 2 of 3 (H86 holdout with four arms; H86-E Euler). Hours: about 1 of 2. No submission
slot was used. Hypothesis H86-T (theta map) and H86-H (hillshade) were not tested because their
information overlaps the repo's implemented tilt and DEM-lineament modules; H86-A is blocked by sandbox
egress (see the table above).
