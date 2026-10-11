# 97 · H102 hypotheses — potential-field directional anisotropy (PAF-DVA) as View A, with anisotropy disagreement as the discovery signal

Frozen before any fit. Machine-readable twin: `registry/h102_preregistration.json`.
Lane: the standing brief's co-training paragraph (Blum & Mitchell, COLT '98,
doi:10.1145/279943.279962). Round label H102 because `main` already holds H88–H96.

---

## 0 · Why this round exists, in one paragraph

Eight rounds have now measured that **View A (potential field / subsurface) is not sufficient**: the
out-of-quadrant AUC of a learner trained on gravity, magnetics, strain and seismicity alone has been at
or below chance in every round that reported it (H82: 0.5113 mean, fold 2 = 0.4309; H95: 0.46–0.60;
H96: A-only discovery pool AUC near chance). Every one of those View-A channel sets was built from
**per-pixel** operators — gradients, steps, ranks, roughness. The best-measured feature family in this
repository is not per-pixel: it is the **directional semivariance anisotropy** of H82 (`B_DVA2`,
HOLDOUT-DTI 0.189200 [0.167891, 0.209115]), and it has only ever been computed on **surface** bands
plus two borrowed gravity bands. H102 computes that same operator **on the potential-field and
subsurface bands** and asks the lane's question with a physically separated pair of views.

## 1 · Hypothesis

Directional semivariance anisotropy measured on the potential-field / subsurface bands
(`iso_grav_anom` 13, `iso_grav_anom_hg` 18, `rtp` 2, `depth_to_base_surf` 15) is a texture of the
**subsurface** that is not a copy of the surface texture. Where View A's anisotropy is confident and
View B's (detrended-elevation) anisotropy abstains, the candidate is a **buried** fault and is therefore
a candidate the surface-expression catalogue cannot contain.

## 2 · Mechanism (stated as a hypothesis, not as a citation)

A fault offsets and fractures rock over a damage zone of hundreds of metres. Fracturing lowers bulk
density, and hydrothermal circulation along the damage zone destroys magnetite; both effects change the
directional roughness of the isostatic gravity and reduced-to-pole magnetic fields along the fault's own
strike, while a cover of alluvium removes the surface expression. The H82 operator resolves the
perpendicular direction at 22.5° (8-direction integer fan) at lags 100–600 m, and its `aniso`
statistic is scale-free: `(max − min)/(max + min)` of the smoothed semivariance over the fan.

**This paragraph is mechanism reasoning, not a literature citation.** The only sources verified for this
round are those listed in §7; no claim above is attributed to a paper that was not fetched.

## 3 · The named non-fault processes that could mimic it

Frozen as a list before any fit, because the brief requires each A-only candidate to carry its own
geological reasoning row:

1. **Lithologic and intrusive contacts**, in particular Tertiary volcanic flow margins and
   intrusive-country-rock contacts, which show in `depth_to_base_surf` and in the magnetic field.
2. **Basin-margin facies steps** and the range-front bajada toe: a real gravity gradient with a
   preferred direction and no fault.
3. **Airborne-survey flight-line, levelling and terrain-correction striping**: directional by
   construction in magnetic and gravity grids; the single most likely instrument artefact here.
4. **Karst and paleochannel scour** at the basement surface.
5. **Isostatic and Bouguer terrain-correction artefacts** at the margins of the survey blocks.

Each emitted cell carries a reasoning row naming the fired components and these alternatives
(`scripts/run_h102.py` stage `write`).

## 4 · The independence assumption, tested as the brief requires

Blum–Mitchell co-training needs the two views to be *approximately conditionally independent* given the
class. H102 tests it the way the brief specifies: **correlate each view's spatial-block out-of-fold errors
on labelled negatives**. The instrument is `gems52.spatial.negative_block_errors` + `spatial.independence`
and the thresholds are inherited **verbatim** from `registry/h74_preregistration.json`
(`block_side_px`, `donor_rank_min`, abandon if |rho| > 0.60). They are not re-tuned for H102 and the
inheritance is recorded with the source file's SHA-256.

A high correlation means the two views make the same mistakes, and co-training between them can only
amplify a shared bias — that is a **stop** condition, recorded as such, not worked around.

## 5 · Arms, and the frozen promotion rule

| arm | field |
|---|---|
| `single_A2` | store `view_A_with_external` + 40 PAF-DVA channels |
| `single_B2` | store `view_B_with_external` + 20 surface-DVA channels |
| `cotrain_disagree` **(primary)** | rank of `rank(A2) − rank(B2)` inside the fold's allowed set |
| `consensus` | rank of `min(rank A2, rank B2)` |
| `buried_only` | rank of `rank(A2)` where `rank(B2) ≤ 0.5` (A confident, B abstains) |
| `union_max` | rank of `max(rank A2, rank B2)` |
| `random` | uniform random on the same allowed set, same budget |

**Promotion (frozen before the fit):** promote only if the pooled `cotrain_disagree` minus the best
comparable control has a paired 95 % CI lower bound above zero **and** the pooled DTI reaches the
standing bar 0.190147. Attribution arms are never promotable post hoc.

**Budget (frozen before the fit):** the artifact's emitted mass is chosen on the same instrument from the
sweep {9 400, 16 000, 25 400} dots per fold, taking the *smallest* budget within 0.002 of the best
pooled DTI. The tie-break toward less mass is registered in advance because
`knowledge/76` measures Spearman(mass, board score) = −0.93 over this family's twelve scored files.

## 6 · What this round may not claim

* The hide-and-recover instrument withholds **catalogue** faults, which were mapped from surface
  expression; the competition scores faults the catalogue lacks. This repository has measured that the
  instrument does not rank leaderboard performance (Spearman ≈ −0.10 over R4, `knowledge/10` §5). A
  holdout number here is evidence about *this instrument*, never a board forecast.
* View A has failed sufficiency seven times. A negative View-A result here is the expected outcome and
  is reported as such.
* No new external data is used. The one external layer that was ranked highest-unexplored
  (GDR 1391 two-metre temperature probes, DOI 10.15121/1881483) is **not reachable from this sandbox**
  (`gdr.openei.org` is not on the egress allowlist) and is therefore not used.

## 7 · Sources verified for this round

* Metric, submission format and round structure:
  <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/> (fetched 2026-10-10)
* Public leaderboard (rank 1 = 0.3774): <https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/> (fetched 2026-10-10)
* Blum & Mitchell, COLT 1998: <https://doi.org/10.1145/279943.279962>
* USGS GeoDAWN release, DOI 10.5066/P93LGLVQ:
  <https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and>
* INGENIOUS / GDR 1391, DOI 10.15121/1881483: <https://gdr.openei.org/submissions/1391>
* EPSG:32611: <https://epsg.io/32611>
* Tversky index (the metric's parent): <https://en.wikipedia.org/wiki/Tversky_index>
* Reference solution (U-Net + Tversky loss, John Lipor):
  <https://github.com/drivendataorg/gems-prize-reference-solution>
