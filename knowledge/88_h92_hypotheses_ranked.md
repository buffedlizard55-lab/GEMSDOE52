# 80 · H92 hypotheses, ranked — written before any H92 fit

Written 2026-10-10 in the H92 session. Scope: the standing brief asks for 3–5 candidate geological
hypotheses the repository has **not** tried, each naming the specific layers involved, the physical
signature targeted, why it should catch a fault missing from the USGS/INGENIOUS catalogue rather than
one already in it, and how it differs from anything already implemented here, ranked by expected DTI
improvement and implementation cost. The top candidate is to be validated on the spatially-blocked
holdout before a weekly slot is touched.

**Honest prior, stated first.** This repository's own negative record is long and specific: every
potential-field transform measured on the 100 m grid sits at or near chance for whole-segment recovery
(View A out-of-quadrant AUC ≈ 0.47–0.60, eight consecutive failures: H61, H63, H64, H65, H70, H71,
H74, H83), and every 2-D edge/curvature reduction of the same two bands has been measured within
±0.01 DTI of the single-view control (H67, H77, H82, H84, H86). "Expected DTI" below is therefore an
**ordinal prior, not a projection**, and no candidate is claimed to beat the current holdout best
(`B_DVA2` 0.189200, H82) until the holdout says so.

**Novelty evidence for this table (verified in this session, not quoted from memory).** Repository
greps over `src/` and `scripts/`: `tilt_depth` 0 files, `tilt-depth` 0, `theta_map` 0,
`second_vertical` 0, `2vd` 0, `werner` 0, `helbig` 0, `kmeans` 0, `GMM` 0, `worm` 0,
`multiscale` 0. `upward` matches 18 files but only as the **pre-computed external TMI 150 m channel**
(`src/gems52/external.py:53`) — the repository never continues the *gravity* field. `comcat` matches
2 files, both of which record that USGS ComCat **failed from this sandbox** (TLS failure before
response, `scripts/publish_h55_profile_site.py:87`); `gdr.openei.org` is likewise outside the sandbox
egress allowlist (`AGENTS.md`, H85 block). Unreachable candidates are listed but marked **not viable
in this sandbox** with the exact source named, as the brief requires.

| rank | id | layers (band index and the file's own tag) | physical signature targeted | why it could find a catalogue-missing fault | how it differs from what this repo does | expected DTI | cost | status |
|---|---|---|---|---|---|---|---|---|
| **1** | **H92-A** tilt-depth (Salem et al. 2007, doi:10.1190/1.2431639) | band 2 `rtp`, band 13 `iso_grav_anom`, derivatives computed from them; band 9 `tmi_vg` / band 11 `iso_grav_vg` as supplied gradients | the depth to the top of the source read **from the spacing of the tilt-angle contours** (±45° to 0°); the 0° contour tracks the contact in map view | the catalogue records faults that reach the surface; a tilt-depth solution whose depth is *greater* than the local cover thickness is a contact the map cannot have — a buried fault with no scarp to map | the repository has tilt-curvature as an **edge map only** (`A_mag_tilt_abs`); it has **no depth attribute anywhere** (`tilt_depth`, `werner`, `helbig` all 0 files). Tilt-depth is a single-window closed form, unlike the least-squares Euler inversion that failed as H86-E | ordinal: medium (only untried mechanism that adds a depth axis, and it is depth that separates "buried" from "mapped") | low (~200 lines, CPU only, reuse the existing `gems53`/`Structural` smoothing) | **not run in this session** (budget); preregistration needed before any fit |
| 2 | **H92-B** gravity upward continuation + second vertical derivative | band 13 `iso_grav_anom` (continuation), band 11 `iso_grav_vg` (comparison) | a *deep* step edge: up-continuation to 500 m / 1 km removes the shallow short-wavelength field, then ∂²/∂z² peaks over the buried step and is silent over shallow lithological noise | catalogue faults in this footprint are the ones that express at the surface; the continued field isolates the *basement* step beneath the alluvium, which is exactly the population the catalogue is expected to miss | the repository up-continues **only TMI, and only as a pre-computed external channel**; gravity is used raw (band 13) in every gravity feature. `second_vertical`/`2vd` are 0 files | ordinal: low-medium | low (FFT on the 12.3 Mpixel grid, minutes) | not run |
| 3 | **H92-C** Werner deconvolution (Hartman et al. 1971, doi:10.1190/1.1440226) | band 2 `rtp`, band 9 `tmi_vg`, horizontal derivatives of band 2 | per-window analytic solution for **depth, dip and susceptibility contrast** of a thin magnetic sheet; a coherent run of solutions along a line is a contact, an incoherent scatter is not | solves for **dip** as well as depth, so a steeply dipping buried contact is distinguishable from a shallow intrusive margin — the named non-fault mimic for the Euler attempt | `werner` is 0 files; H86-E tested Euler SI 0 (0.0777, paired CI spanning zero against random) and its failure mode was window-edge solutions with no dip constraint | ordinal: low | medium (7×7 moving solve, needs a stability policy for singular windows) | not run |
| 4 | **H92-D** azimuth-space clustering of the potential-field gradient tensor (k-means/GMM over dip-azimuth, magnitude, depth) | bands 2, 13, 9, 11 | a *fault corridor* is a spatially coherent cluster in (azimuth, magnitude) space; a lithological contact is a single azimuth line; an intrusive margin is a radial azimuth fan | a buried fault population should appear as one or two dominant azimuth clusters that are **not** the N10°W–SSE regional strike (measured 166.7–171.8°, R 0.37–0.45, H82), i.e. as a systematic departure from the mapped grain | clustering is 0 files (`kmeans`, `GMM`); the repository reduces the tensor to scalar channels (`A_gravity_grad_*`, `A_gravity_coherence`) and never models the azimuth distribution. Note the known trap: `cos2`-style reductions of an 8-direction argmax take only 4 distinct values (H82 §2), which is precisely why a *distribution* model rather than a scalar reduction is worth trying | ordinal: low (and at high risk of the H82 quantisation trap) | medium | not run |
| 5 | **H92-E** external thermal/alteration layers | **external, blocked**: GDR 1391 INGENIOUS 2 m temperature survey | shallow temperature anomaly over a fault-fed hydrothermal system | an independent *surface* measurement of the hydrothermal system, not a derivative of DEM or magnetics | never used in this repository (H85 block records it as "the 2-m temperature survey never used here") | ordinal: unknown | — | **NOT VIABLE IN THIS SANDBOX**: `gdr.openei.org` is outside the egress allowlist (only github.com, codeload.github.com, api.github.com, registry.npmjs.org, pypi.org, files.pythonhosted.org are reachable). Source to check: <https://gdr.openei.org/submissions/1391>. Requires an owner-side download SHA-pinned into the manifest first |
| 6 | **H92-F** seismicity b-value / declustered background-rate maps | **external, blocked**: USGS ComCat FDSN | spatial b-value and background rate along the Walker Lane | b-value drops along critically stressed fault segments | uses only the organiser's supplied seismicity bands 10/16 (distance and density), never a temporal or magnitude distribution | ordinal: low-medium | — | **NOT VIABLE IN THIS SANDBOX**: a ComCat FDSN request failed TLS before response (recorded in this repo). Source: <https://earthquake.usgs.gov/fdsnws/event/1/> |

## Why H92-A is ranked first, and what would falsify it

It is the only entry that adds an *independent axis* (depth) using **layers already in the store**, at
low cost, with a closed-form estimator. The falsifier is clean and pre-registerable: if tilt-depth
solutions do not place the buried (catalogue-absent) population deeper than the visible catalogue
population, the mechanism is dead. Two named non-fault mimics must be carried in the reasoning rows:
basement lithological steps under cover (no displacement) and the edge artefact of the grid itself.

**Ranking caveat.** Ranks 1–3 all read the *same* two potential-field bands through different
operators. The repository has now measured this family eight times at or near chance (see the honest
prior above), so the probability that a new reduction of the same bands breaks 0.32 is low even where
the operator is genuinely new. That is why **the round actually executed this session is not a new
operator at all** — it is a calibration question about the existing emission, which the algebra says
is worth more than a marginal change of ranking: see `knowledge/81_h92_results_and_limits.md`.

## Budget used

Hypotheses written before any H92 fit, as required. Experiments: 3 of 3 (instrument audit; budget
ladder; emission + gates). Hours: within the 2-hour cap. Submission slots used: 0.
