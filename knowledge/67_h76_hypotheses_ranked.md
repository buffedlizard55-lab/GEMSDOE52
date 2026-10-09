# 67 · Ranked candidate hypotheses for the next rounds (written 2026-10-09, before the H76 holdout was read)

Labels: HOLDOUT-DTI = gems52-pooled-hide-v1 (alpha 0.2, beta 0.8, 300 m triangular kernel, 53,186 withheld positives).
Board numbers are PUBLIC or OWNER-REPORTED, never ORGANIZER-CONFIRMED. Every "not implemented" claim below was checked by
grepping `src/` and `scripts/` for the term (counts given), so a reader can repeat the check.

## Layer facts (verified from the restored `data/training_features.tif`, 19 bands, EPSG:32611, 100 m)
The band list matches the organiser's "Provided features" section, <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>
(fetched 2026-10-09). Band indices used below are 1-based GeoTIFF bands.
- 3 `tmi_hg` (magnetic horizontal gradient), 6 `tc` (tilt/total curvature), 12 `det_elev`, 13 `iso_grav_anom`,
  15 `depth_to_base_surf`, 17 `cond_surf`, 18 `iso_grav_anom_hg`, 19 `det_elev_slope`, 4/7/8 geodetic strain, 10/16 seismicity.

## Ranking (expected DTI gain × implementation cost; the gain column is a qualitative judgement, not a forecast)

| Rank | Hypothesis | Layers | Physical signature targeted | Why it should find a fault missing from the USGS/INGENIOUS catalogue | How it differs from what the repo already has | Cost | Status after this round |
|---|---|---|---|---|---|---|---|
| 1 | **H76-1: directional variogram anisotropy (DVA) of the isostatic-gravity horizontal gradient** | 18 | lag-2/4 px semivariance anisotropy of a gradient field (damage-zone texture) | a damage zone is a property of the continuous field, not of a mapped trace | H75 used DVA on bands 12, 19, 13 only; band 18 had no variogram (grep: 1 src file, not a variogram) | low (reuses H75 code) | **TESTED: NEGATIVE** (`knowledge/69`). Holdout +0.0020, CI [−0.0015, +0.0052] |
| 2 | **H76-2: antithetic basement-step asymmetry** | 15 `depth_to_base_surf` | sign-asymmetric step across a candidate line: |Δ+| − |Δ−| at 300 m, on both sides of a half-graben margin | half-graben margins with gentler antithetic dip are under-mapped in regional catalogues | "antithetic" has 0 src hits; band 15 is used by 13 src files but never as an asymmetric step statistic | medium (new feature, preregistration needed) | **NOT RUN** (budget: one experiment this round). Queued as H76-2 with its own preregistration |
| 3 | **H76-3: DVA of the magnetic horizontal gradient** | 3 `tmi_hg` (and 6 `tc` as a second variant) | magnetic edge texture anisotropy from dikes, contacts, and basement structure | dike swarms and lithologic contacts are not mapped as faults in the catalogue | the repo has tilt/HG/edge features (tilt: 34 src hits), but no directional-variogram statistic on the magnetic gradient | low–medium | **NOT RUN**. **Named mimic to test first:** GeoDAWN flight-line direction. Survey-line artefacts are anisotropic and can dominate any directional statistic. Need a line-artefact check before any holdout is read |
| 4 | **H76-4 (governance, not geology): lane-rule redefinition and denominator-aware placement** | registry + placement | none (no geology) | — | H73 placement quotas; H75 near-dot gate | low | **NOT RUN, owner decision.** Every surface-ranked emission fails the literal near-dot rule (H73, H75). A registry restricted to scored submissions would change the rule, so it needs a preregistered amendment from the owner, not a quiet change |
| 5 | **H76-5: 1 m DEM scarps from USGS 3DEP** | new raster (1 m DEM) | fault scarps at 1 m resolution | scarps are often too small for the 100 m features | the repo's `lidar_scarp_features_u8` already exists (data/external) | high | **BLOCKED.** The 3DEP page says products are free with no use restrictions (<https://www.usgs.gov/3d-elevation-program>, fetched 2026-10-09). The sandbox egress allows only github/npm/pypi hosts, so the USGS tiles cannot be downloaded here. The competition's `1m_DEM_links.csv` is behind the DrivenData login and is not restored |

## Already tried (not re-proposed)
- Deformation-only View A (H74, bands 4/7/8/10/16): sufficiency AUC 0.5194; co-training View A failed six consecutive rounds (`knowledge/55`, `knowledge/64`).
- Tilt, structure tensor, curvature, corroboration and cover gating: each has many src/knowledge hits (tilt 34, structure tensor 23, curvature 45, corroborat 65). Treat any new one as a re-run unless it has a new statistic.
- Holdout-to-board prediction: holdout DTI does not forecast the board score (Spearman −0.10, measured in R4; `README.md`, R4 block). A holdout win is therefore a necessary condition for a candidate, not a sufficient one.

## What "beat 0.3195" needs, from the repo's own algebra (`knowledge/49`)
A holdout gain of 0.002 cannot move the board by the amount needed. `knowledge/49` §4 gives the credit density needed to
reach 0.3195 at 37,654 px as ρ ≈ 0.16 against 0.139 for the 0.2778 file. The candidates above do not measure ρ on the board.
