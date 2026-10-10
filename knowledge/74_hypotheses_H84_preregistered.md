# 74 · H84 — preregistration (frozen before any H84 fit, 2026-10-10)

Round identifier: **H84** (checked free on `origin/main` at commit `22091610` by `grep -rl "H84"` over all
`.md/.json/.py` files and `gh pr list --state all`, 2026-10-10). Lane: the brief's two-view co-training
paragraph. Pinned by `registry/h84_preregistration.json`; `scripts/run_h84.py` refuses to start if this
file's SHA-256 moves.

Labels: **HOLDOUT-DTI** = a reading of the shared evaluator `gems52-pooled-hide-v1` (hide-and-recover,
whole fault segments withheld with an 80 px buffer, every catalogue-derived feature computed from the
fold's *visible* faults only, visible faults masked pixel-exactly, pooled DTI at α 0.2 / β 0.8 / 300 m
triangular kernel, 95 % paired CI by resampling physical blocks). **PUBLIC-BOARD** = read off the
organiser's leaderboard page (team-level, no filename). **OWNER-REPORTED** = a file↔score pairing typed
by the owner in the brief. **ORGANIZER-CONFIRMED** = copied from a submission-page receipt; nothing in
this round is. A projection is never written as a score.

## 0 · What this round continues, and what it must not re-litigate

The previous round (H82, `knowledge/73`) left one explicit next step (`AGENTS.md` H82 block):

> `B_DVA2` may not be promoted post hoc … It must be pre-registered fresh as H77's primary *before any
> fit*, together with the fix for the quantisation above (a 16/32-direction fan, or a continuous
> sub-pixel θ_max by parabolic interpolation across the fan or a structure tensor on the γ field).

H84 executes exactly that, as a fresh preregistration. Settled facts carried in, not re-tested:

* View A sufficiency has failed **seven** times (H82 mean out-of-quadrant AUC 0.5113, min fold 0.4309);
  H77cond showed View A is *least* informative exactly where View B is blind (0.4685 < 0.4893 < 0.5436).
  Independence passes every time (H82 max |ρ| 0.1317 < 0.60). Pseudo-label exchange lowered the
  donor-receiving view's AUC when it was run (H71/H74: 0.5019 → 0.4759). **H84 does not run another
  exchange**; it re-measures independence and sufficiency with its own fits and reports them (§6).
* VSA (variogram azimuth vs strike) *hurt* (−0.038609 vs `B_DVA2`), because θ_max was quantised to 8
  values and `cos2loc` was 0 on 47–70 % of pixels. H84 does **not** couple any channel to a
  catalogue-derived strike.
* Placement headroom is closed (H77): binary {0,1}, 3 px spacing, 200 m catalogue ring, 37,654 cells.
  H84 reuses that placement unchanged.

## 1 · Candidate hypotheses (ranked by expected HOLDOUT-DTI gain ÷ cost)

Novelty check, 2026-10-10, `grep -rn "harmonic\|cos2phi\|lag_coherence\|h2amp" src scripts` → no
implementation. The only variogram code is `scripts/run_h75.py`, `scripts/h75_write.py`,
`scripts/run_h81.py` and `scripts/run_h82.py`, all of which reduce the directional semivariance with
`(max − min)/(max + min)` (two order statistics of 4 or 8 directions). View B already contains one
single-scale gradient structure-tensor coherence channel (`B_surface_coherence`, σ = 3 px,
`src/gems52/structural.py` line ≈316); §1.1 states exactly how H84-1 relates to it.

| # | Hypothesis | Layers (`training_features.tif` band) | Physical signature | Why it should catch a fault the USGS/INGENIOUS catalogue lacks | How it differs from anything implemented here | Expected gain / cost |
|---|---|---|---|---|---|---|
| **1** | **HVA — harmonic (elliptical) variogram anisotropy** (PRIMARY) | 12 det_elev, 19 det_elev_slope, 13 iso_grav_anom, 15 depth_to_base_surf, 18 iso_grav_anom_hg | least-squares fit of the 8 directional semivariances to γ(θ) = a + b·cos2θ + c·sin2θ at each lag h ∈ {1,2,3,4,6} px; channel = √(b²+c²)/a, the eccentricity of the geometric-anisotropy ellipse | a fault zone (damage zone, juxtaposed blocks, cover-thickness step) makes the field's spatial covariance elliptical with its long axis along strike. The statistic is computed from the continuous field alone — no catalogue input — so it fires where no trace is mapped | `(max−min)/(max+min)` is the range of 8 noisy estimates and is upward-biased under isotropic noise (order-statistic inflation); the harmonic fit uses all 8 directions with a fixed 3×8 linear operator, is continuous in orientation (the H82 quantisation defect), and is exactly the ellipse eccentricity under geometric anisotropy (§1.1) | **medium / low** |
| **2** | **COH — multi-lag orientation coherence** (attribution arm) | same 5 bands | per band, \|Σ_h (b_h + i·c_h)/a_h\| / Σ_h \|b_h + i·c_h\|/a_h over the 5 lags: 1 when the anisotropy axis is the same at 100–600 m, 0 when it rotates with scale | a planar discontinuity has one orientation at every scale; texture, drainage dendrites and noise rotate with scale. Catalogue-free | no scale-coherence statistic exists in this repo; H82's VSA compared one lag against a catalogue strike instead | low–medium / low |
| 3 | HVA on the GeoDAWN external layers (`data/external/geodawn_rad_u8.tif`, `geodawn_extensions_u8.tif`) | external radiometric K/eTh/eU and magnetic extensions, already in the shared store | same operator on radiometric and upward-continued magnetic fields | alteration halos and buried magnetic contrasts along unmapped faults | the operator has never been applied to external layers | unknown / low — **deferred** (one primary per round) |
| 4 | Seismicity-only View A vs View-B abstention (H74S-B) | bands 10, 16 | A-confident ∧ B-abstains stratum | microseismicity on blind faults | listed untested in `knowledge/63` | low (View A measured insufficient seven times) / medium — **deferred** |
| 5 | Drainage-deflection corridors | 1 m DEM (USGS 3DEP) via the competition's `1m_DEM_links.csv` | D8 flow-direction deflection across a buried scarp | the classic covered-fault criterion in Basin-and-Range piedmonts | not implementable here | high / **BLOCKED** — source named and checked this session: USGS 3D Elevation Program <https://www.usgs.gov/3d-elevation-program> (public domain) and the tile list on <https://www.drivendata.org/competitions/306/competition-doe-gems/data/> (login). `curl` from this sandbox, 2026-10-10: `prd-tnm.s3.amazonaws.com` 000, `www.usgs.gov` 000, `www.drivendata.org` 000, `gdr.openei.org` 000; `api.github.com` 200, `pypi.org` 200. **Not obtainable here.** |

Only rank 1 is the primary. Rank 2 is fitted as a non-promotable attribution arm.

### 1.1 · Why the harmonic fit is the right reduction (stated before any fit)

Under geometric anisotropy the variogram depends on the lag vector through a positive-definite quadratic
form, γ(**h**) = γ₀(√(**h**ᵀB**h**)) (standard geostatistics; e.g. the geometric-anisotropy definition
in Budrikaitė & Ducinskas, <http://www.techmat.vgtu.lt/~art/proc/file/BudrLi.pdf>, and the ellipse
parameterisation in <https://www.causeweb.org/usproc/sites/default/files/usresp/2018-1/Exploring_Geometric_Anisotropy_for_Point-Referenced_Spatial_Data.pdf>).
For **h** = h(cos θ, sin θ):

  **h**ᵀB**h** = h² · [ (B₁₁+B₂₂)/2 + (B₁₁−B₂₂)/2 · cos 2θ + B₁₂ · sin 2θ ].

So for a variogram that is linear or quadratic near the origin, the directional semivariance at a fixed
lag is (to first order) a + b·cos2θ + c·sin2θ, and √(b²+c²)/a = (λ₁−λ₂)/(λ₁+λ₂) is the ellipse's
eccentricity. As h → 0 with Gaussian smoothing, B tends to the smoothed gradient structure tensor, so at
lag 1 px on band 12 the channel is a close relative of View B's existing `B_surface_coherence`; at lags
2–6 px (200–600 m, i.e. the 300–900 m damage-zone widths named in H82) and on bands 13/15/18/19 it is not.
The fan's 2θ values (0°, 90°, 180°, 270°, 53.1°, 126.9°, 233.1°, 306.9°) span the circle, so the 3×3
normal matrix is well conditioned; its condition number is recorded in the channel manifest.

γ_k is the **same** normalised, Gaussian-smoothed semivariance H82 computed (offset-length normalisation
`hypot(dy,dx)/h`, σ = 3 px, support-weight normalisation), so the `B_DVA2` control and the primary see
identical inputs and differ only in the extra channels.

## 2 · Arms (frozen)

| Arm | Store columns | Extra channels | Role |
|---|---|---|---|
| `single_B` | View B (`view_B_with_external`) | — | control; committed HOLDOUT-DTI 0.174517 (tol 1e−3) |
| `B_DVA2` | View B | 50 DVA2 (aniso + logvar, H82 definition) | control and **current holdout best** (H82 measured 0.189200; tol 1e−3) |
| **`B_DVA2_HVA`** | View B | 50 DVA2 + **25 HVA** `HVA_<band>_h2amp_l<h>` | **PRIMARY** |
| `B_DVA2_HVA_COH` | View B | primary + **5 COH** `COH_<band>` | attribution, **not promotable** |
| `single_A` | View A (`view_A_with_external`) | — | lane single-view baseline; sufficiency re-measure |
| `random` | — | — | floor |

Learner, sampling, folds, region-only prediction and the matched budget are the shared ones:
`run_h61.learner_for / sample_for_fit`, `gems52.spatial.folds` (label-blind-quadrants-v2, 80 px buffer),
9,400 dots per fold per arm, `gems52.nodes.spacing_select` at 3 px, seed `run_h61.SEED`.

## 3 · Promotion rule (frozen; "beat the current holdout best")

The candidate is **PROMOTE-ELIGIBLE for the selector step** only if *all* hold:

1. paired 95 % CI lower bound of (`B_DVA2_HVA` − `B_DVA2`) **> 0** — it beats the current holdout best;
2. paired 95 % CI lower bound of (`B_DVA2_HVA` − `single_B`) **> 0**;
3. controls reproduce: `single_B` within 1e−3 of 0.174517 and `B_DVA2` within 1e−3 of 0.189200;
4. leakage canary: no single learner channel reaches direction-insensitive AUC 0.90 in any fold;
5. lane: literal surface verdict PASS before placement **and** literal full-census dot verdict PASS on
   the final dots (the doctrine "a restricted-registry PASS never waives a literal full-census
   DUPLICATE/STOP" is retained verbatim; see §5);
6. format validator PASS and not-the-union PASS.

Failure of any item → verdict **NEGATIVE / research-only**. No attribution arm can be promoted. No slot is
spent by this round in any case (selector step is separate).

## 4 · Emission (frozen)

Full-domain field = per-fold percentile ranks of the primary stitched over the four regions (H73/H82
convention). Pool = eligible ∧ finite ∧ distance to mapped catalogue > 200 m. **E3 output = quota
placement** `run_h73.place_lane` of 37,654 cells at 3 px spacing against the informative supports of the
scored-only registry (`registry/h82_scored_registry.json` membership, universal-coverage probes ≥ 0.95
excluded), limit 0.70 — this is H82's recommendation ("pre-register the quota-placed emission as its E3
output rather than the unconstrained one"). If the quota placement short-fills, the unconstrained
`spacing_select` placement is emitted instead and the short fill is reported. Values exactly {0, 1};
**0.0 outside the footprint, no NaN anywhere** (the encoding of the OWNER-REPORTED 0.2778 `-zeros` file
and the repository's documented fix for the portal's "Predicted values must be in range [0, 1]" error,
`knowledge/03` N-5, IR-52-006). Writer: `gems52.submission_writer.write_submission` (fail-closed,
re-reads its output).

## 5 · Lane gate (frozen)

Thresholds from the brief: rank correlation > 0.90 with any registry raster, or > 70 % of dots within
3 px of one registry raster's dots → DUPLICATE/STOP. Checked on the surface **before** placement and on
the final dots, against (a) the literal full census (`work/h61/prior_fetch_receipt.json` +
`submission/` + `data/scored` + `data/reference`, own files excluded) and (b) the scored-only registry.
Both verdicts reported verbatim. If the literal *surface* check is DUPLICATE the round stops before
placement and logs a duplicate.

**Known structural irregularity, stated before running:** the full census contains universal-coverage
lattice probes whose 3 px halo covers ≥ 95 % of the footprint; against those, *every* non-empty dot set
has a near-3px share of 1.0 (H73, H75, H82 measured this). Under the retained doctrine item 5 of §3 can
therefore not pass for any emission. H84 does not waive it; it reports it as an owner decision
(IR-H84-001).

## 6 · Co-training obligations, and how each is met

| Obligation in the brief | H84 action |
|---|---|
| Two views: A potential-field/subsurface, B surface | store's `view_A_with_external` / `view_B_with_external`, overlap asserted empty by `run_h61.setup` |
| Test independence: correlate spatial-block OOF errors on labelled negatives; abandon if strong | `gems52.spatial.independence` on H84's own `single_A`/`single_B` OOF predictions, thresholds inherited verbatim from `registry/h74_preregistration.json` (abandon bar \|ρ\| > 0.60) |
| Pseudo-label only where one view is confident and the other abstains, whole-segment blocks + buffer | **not run** (standing deviation): sufficiency of View A is re-measured; if mean AUC < 0.60 or min fold < 0.55 there is no confident donor. Recorded, not hidden |
| Disagreement as discovery; geological reasoning for every A-only candidate | A-only stratum = A rank ≥ 0.95 ∧ primary rank ∈ [0.35, 0.65], spacing-thinned; one reasoning row per A-only candidate (`docs/downloads/*-a-only-reasoning.csv`); B-only stratum counted with a cardinal-orientation (road/section-line) audit |
| Compare against a single-view baseline on hide-and-recover | `single_B` and `single_A` arms on the same instrument |
| Normalise to [0,1], write GeoTIFF, metric-aware placement, uniqueness gate, not the union | §4, `gates.uniqueness_report`, union-max comparison at equal budget |

## 7 · Honest expectation, written before the holdout is read

H82 measured `B_DVA2` − `single_B` ≈ +0.0143 in point estimate, and `B_DVA` − `single_B` +0.011835 with
CI [0.006791, 0.017362]. A refinement of the anisotropy statistic is a second-order change; the most
likely outcome is a point gain of 0 to +0.005 over `B_DVA2` with a CI that straddles zero, which fails
item 1 of §3. Holdout DTI does not rank board performance in this repository (Spearman −0.10,
`knowledge/10` §5), so **no board score is projected**. The OWNER-REPORTED board bar is 0.2778
(`h33-2-b2`); the PUBLIC-BOARD #8 is 0.3195 and #1 is 0.3774 (snapshot `registry/leaderboard_snapshot_2026-10-10.json`).

## 8 · Budget

Experiments: this is **experiment 1 of 3**; 2-hour wall-clock budget from the freeze timestamp in the
registry. Slots: 0. The sandbox has 2 CPUs and 3.9 GB RAM (measured `nproc`, `free -m`); channel arrays
are written through `save_verified` (IR-H82-002 pattern) to the ignored `work/h84/`.
