# 25 · Official clarifications verified 2026-10-08, and every repo claim they change

Fetched this session from the organiser's own pages and from DrivenData staff posts on the
competition forum. Nothing here is inferred, remembered or reconstructed: each item is a quotation
with a URL and a date, followed by what it does to a claim this repo has been carrying. Where an
official statement and a local measurement disagree, both are printed and the disagreement is
registered in `registry/irregularities.json` rather than resolved by preference.

| # | Source | Fetched |
| --- | --- | --- |
| S1 | Problem description, <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/> | 2026-10-08 |
| S2 | Public leaderboard, <https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/> | 2026-10-08 |
| S3 | Forum topic 11516 "Scoring clarification: are known USGS/INGENIOUS faults masked when scoring…", <https://community.drivendata.org/t/11516> — staff answers 2026-09-16 and 2026-09-21 | 2026-10-08 |
| S4 | Forum topic 11527 "How were the new test faults identified?", <https://community.drivendata.org/t/11527> — staff answer 2026-09-23 | 2026-10-08 |
| S5 | Forum topic 11550 "Leaderboard aggregation: pooled over public-test pixels, or mean of per-chunk scores?", <https://community.drivendata.org/t/11550> — staff answer 2026-10-01 | 2026-10-08 |
| S6 | Forum topic 11557 "Units and very large values in `deq_n100a15` (and meaning of `ieq_n100a15`)", <https://community.drivendata.org/t/11557> — staff answer 2026-10-07 | 2026-10-08 |
| S7 | Band tags read out of `data/training_features.tif` itself (`rasterio` `descriptions` and per-band `tags`) | 2026-10-08 |

The forum's own category index is <https://community.drivendata.org/c/gems-prize-challenge/111>; the
staff account answering S3–S6 is `chrisk-dd`, whose flair is `drivendata-staff` and whose account
flags are `staff: true, moderator: true, admin: true` in the forum's JSON. `fetch_page` reached all
of these hosts even though the sandbox's shell has no route to them; the raw text is quoted below so
the record does not depend on the fetch staying reachable.

## 1. What the ground truth is (S1, S4)

> "we have consulted with fault experts who have manually identified faults that are not contained
> within the current public USGS database. These new faults will comprise the test dataset for the
> initial prize round of the challenge." — S1

> "The GeoDAWN region is chunked and split into a public test set and a private test set. Competitors'
> performance against the public test set is shown on the public leaderboard during the competition."
> — S1

> "We're not sharing details about the data sources, fault types, or coverage behind the test faults
> beyond what's in the problem description." — S4, staff

So the target is a set of expert-mapped faults that are, by construction, **absent from the USGS and
INGENIOUS traces we are given as labels** — which is the same conclusion `knowledge/10` §2 reached
from the bytes alone, now stated by the organiser. What the truth is *made of* (lidar scarps,
geophysics-only inferences, field mapping) is explicitly closed: nobody can claim to know, and any
repo sentence that says otherwise is a guess.

## 2. Two rounds, and the second one is the big one (S1, S4)

| Round | Prize | Ground truth |
| --- | --- | --- |
| Initial Prize Round | $50,000 (top 5, $10K each) | "A *fixed* private set of new faults that the sponsor's experts labeled **before** the competition started" (S1) |
| Final Prize Round | $250,000 ($100K · $70K · $40K · $25K · $15K) | "An **expanded** label set — Initial Prize Round labels **plus** previously-unknown faults that experts verify after reviewing *every team's* submission" (S1) |

> "Note that the largest prize pool (Phase 2) will use a test set that is updated by expert review of
> all Phase 1 submissions, so your fault predictions have an impact on final evaluation **even if they
> are not the most performant in Phase 1**." — S4, staff

> "Competitors must choose a **single** submission for scoring across both rounds before the deadline,
> without knowing their private test set performance." — S1

Three consequences this repo had not written down:

1. **A geologically defensible candidate that scores middling in Phase 1 can still pay in Phase 2**,
   because experts read the submissions. That is an official reason to ship reasoning with pixels —
   the brief's "write the geological reasoning for every A-only candidate" is not paperwork, it is the
   Phase-2 channel, and `docs/downloads/a_only_reasoning_r5.csv` is written for it.
2. **One file serves both rounds**, so the file has to be chosen under two different `|G|` values
   (§5 below) and cannot be tuned to either.
3. Phase 2 re-evaluation is "on the entire GeoDAWN area" (S5), i.e. a strictly larger truth set than
   the public chunk the leaderboard reports.

## 3. The metric, verbatim (S1) — and it is what `src/gems52/metric.py` implements

> `TI(α,β) = Σ p(x)g(x) / [Σ p(x)g(x) + α Σ p(x)(1−g(x)) + β Σ (1−p(x))g(x)]`
> `k(d) = (1 − d/R)+ = max(1 − d/R, 0)`, "where the range R is 300 meters (i.e., 3 pixels at 100m
> resolution)"
> `TPw = Σ_{g∈G} max_{x: d(x,g)≤R} p(x)·k(d(x,g))`
> `FPw = Σ_{x: p(x)>0} p(x)·[1 − max_{g∈G} k(d(x,g))]`
> `FNw = Σ_{g∈G} [1 − max_{x: d(x,g)≤R} p(x)·k(d(x,g))]`
> `DTI(α,β) = TPw / (TPw + α·FPw + β·FNw + ε)`
> "For this competition, we set α = 0.2 and β = 0.8" — S1

Worked example given by the organiser: a single vertical truth line, `TPw = 3.00, FPw = 1.89,
FNw = 2.00`, `TI_w = 3.00 / (3.00 + 0.2·1.89 + 0.8·2.00) = 0.60`.

Checked against the repo's algebra, line by line: `FNw = |G| − TPw` identically, so for a binary
`p ∈ {0,1}` emission `DTI = T / (0.2·(T + S − M) + 0.8·|G|)` with `T = TPw`, `S` = evaluated emitted
mass and `M = Σ_g max_x k`. Two things the official text settles that the repo had been arguing about:

* **`FPw` is summed over emitted pixels, `TPw` over truth pixels.** They are different sums, so
  `Σ_x max_g k` is *not* generally `Σ_g max_x k`; they coincide only when dots are far enough apart
  that no two compete for one truth pixel. `knowledge/10` §9.1 already listed this as an
  approximation. It is an approximation, not an identity, and the champion's >200 m dot separation is
  what licenses it.
* **`p` is a probability, and the metric is not scale-invariant.** For one pixel of weight λ,
  `DTI = λk/(0.2λ + 0.8)` increases in λ, so the best mass on any accepted pixel is 1.0 — the
  repo's "binary is optimal" conclusion, now from the organiser's own formula rather than from a
  local derivation.

## 4. Submission format, verbatim (S1) — and the R5 file complies with every clause

> * "same projected coordinate reference system as the training data (… UTM zone 11N, EPSG 32611)"
> * "same resolution as the training data (100m)"
> * "same bounds as the training data, and data outside the bounds is null or nan"
> * "a single layer with datatype of 32-bit float (`float32`) with values between 0 and 1"
> * "A sample submission that predicts total fault absence is provided … You can use this as a
>   template" — S1

Measured back off the written bytes for `gems52-r5-novel-n5_strike_ridge-16681px-…-zeros.tif`
(`evidence/r5_novel_emission.json` → `values`): `dtype float32`, `crs EPSG:32611`,
`transform [100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0]` (identical to
`data/sample_submission.tif`), `bands 1`, `min 0.0`, `max 1.0`, `unique_values 2`,
`finite_pixels 12,279,160 / 12,279,160`, `nodata_tag None`.

That is the whole of the portal's `"Predicted values must be in range [0, 1]"` rejection: it needs a
non-finite or out-of-range cell, and `gems52.grid.write_geotiff` now *raises* before writing if the
array has a NaN/inf or leaves [0,1], then re-reads the file and returns what the file says. A file
that reaches the site cannot carry the defect.

## 5. Masking and aggregation — the two answers that change strategy (S3, S5)

> 1. "Pixels corresponding to known USGS/INGENIOUS faults are masked / excluded from evaluation, so
>    they do not count towards penalty terms."
> 2. "Re-evaluation will also mask/exclude the existing USGS/INGENIOUS faults."
> 3. "for scoring purposes it should not matter whether these known faults are included with
>    predictions or not." — S3, staff, 2026-09-16

> 1. "**The mask is indeed pixel-exact** — it is identical to the provided set of training fault
>    labels."
> 2. "Only new-fault ground truth is considered for scoring purposes. A predicted pixel that is near a
>    known fault trace but far from a new-fault ground truth pixel **will be fully penalized**, i.e.,
>    the buffer does not apply to known faults."
> 3. "**A new-fault ground truth pixel can indeed lie within 300m of a known fault trace.** Such
>    pixels would constitute corrections or modifications to existing fault traces. **Identifying
>    these corrections is one outcome we are aiming for as part of this competition.** Such corrections
>    may already exist in the new-fault set, and may also exist in the final round evaluation set."
>    — S3, staff, 2026-09-21

> 1. "The public leaderboard score is computed by **pooling over all pixels in the public subset and
>    computing a single Tversky index**."
> 2. "We are not providing any information on the chunking / subsets."
> 3. "The private leaderboard score is computed the same way. **The final re-evaluation will be on the
>    entire GeoDAWN area.**" — S5, staff, 2026-10-01

What each one does to a standing repo claim:

| Repo claim | Status after S3/S5 | Where it is corrected |
| --- | --- | --- |
| "emit nothing inside 200 m of a mapped trace … the single change with the largest measured effect in this repo's history" (`knowledge/10` §2) | **Too strong.** The mask is pixel-exact, so the 100–200 m corridor is *evaluated* mass, and the organiser says truth can sit there and that finding it is a goal. What is measured is narrower: *this family's* 6,436 corridor pixels earned 0–85 credit, a density ≤0.0132 against 0.0279 for uniform random. | `IR-R5-006`; `knowledge/26` H60-A proposes the correction detector the corridor actually needs |
| `|G| = 14,088.7` is "exact" (`knowledge/10` §2) | **Exact only given "the corridor earned zero".** Solving `T_B − T_A = 200.62 − 0.01424·|G|` with the independent bracket `|G| ≥ 8,128` bounds the corridor's credit at 0–85 px, so `|G| ∈ [14,030, 14,089]` rather than being a single number. The bound is tight enough to keep every downstream figure. | `knowledge/27` §3 |
| "deleting 2,545 masked pixels raised the score by 2.6 % … a pixel the organiser has masked can never earn credit but can always pay the false-positive tax" (`knowledge/01` §1) | **Wrong mechanism.** Masked pixels pay nothing (S3 answer 1). The gain came from the 6,436 *unmasked* corridor pixels. The set arithmetic reconciles: A emits 40,199 px of which 2,545 are masked → 37,654 evaluated; B emits 46,635 of which the same 2,545 are masked → 44,090 evaluated; difference 6,436. | `IR-R5-007`; `knowledge/27` §2 |
| DTI is one pooled index over the evaluated footprint | **Confirmed** (S5). No per-chunk averaging, so there is no reason to spread mass thinly across chunks to avoid a zero-scoring chunk. | — |
| The budget rule optimises against `|G| = 14,088.7` | **Round-dependent.** The DTI-optimal budget for a credit curve `T = c·S^β` is `S* = 4|G|β/(1−β)`, which scales *linearly* in `|G|`. The final round is scored on the entire GeoDAWN area with an expanded label set, so its `|G|` is larger by an unknown factor and its optimal budget is larger by the same factor. | `knowledge/27` §6, `knowledge/26` H60-E |

## 6. The nineteen bands, as the file itself describes them (S7), against the organiser's list (S1)

Read with `rasterio`: `descriptions[i]` and `tags(i)` for `data/training_features.tif`. Quoted
verbatim, because two of them are wrong and one organiser-listed product is missing.

| # | `band_name` | `data_category` | description in the file | used by R5 |
| --- | --- | --- | --- | --- |
| 1 | `mag_anom` | magnetic_data | "Magnetic anomaly - deviation from expected Earth's magnetic field" | View A, mag family |
| 2 | `rtp` | magnetic_data | "Reduced to pole magnetic data - magnetic anomaly corrected for latitude effects" | mag family |
| 3 | `tmi_hg` | magnetic_data | "Total magnetic intensity horizontal gradient - rate of change in horizontal direction" | View A, mag family |
| 4 | `geod_2ndinv` | geodetic | "Geodetic second invariant - measure of strain rate tensor magnitude" | View A, strain family |
| 5 | `iso_grav_anom_slope` | gravity | "Isostatic gravity anomaly slope - gradient of gravity after isostatic correction" | View A, grav family |
| 6 | `tc` | magnetic_data | "Tilt angle or total curvature - magnetic field derivative for edge detection" | **View B**, rad family |
| 7 | `geod_shearrate` | geodetic | "Geodetic shear rate - rate of angular deformation from GPS/InSAR" | strain family |
| 8 | `geod_dilaterate` | geodetic | "Geodetic dilatation rate - rate of volumetric strain (expansion/contraction)" | strain family |
| 9 | `tmi_vg` | magnetic_data | "Total magnetic intensity vertical gradient - rate of change in vertical direction" | mag family |
| 10 | `deq_n100a15` | **seismic** | "Distance to earthquake (n=100km radius, a=15° azimuth parameters)" | **nowhere — see H60-B** |
| 11 | `iso_grav_anom_vg` | gravity | "Isostatic gravity anomaly vertical gradient - vertical rate of change" | grav family |
| 12 | `det_elev` | topographic | "Detrended elevation - topography with regional trends removed" | View B, topo family |
| 13 | `iso_grav_anom` | gravity | "Isostatic gravity anomaly - gravity after compensating for topographic mass" | View A, grav family |
| 14 | `tmi` | magnetic_data | "Total magnetic intensity - total strength of magnetic field" | mag family |
| 15 | `depth_to_base_surf` | subsurface | "Depth to basement surface - thickness of sedimentary cover" | View A, sub family |
| 16 | `ieq_n100a15` | **seismic** | "Earthquake intensity or density (n=100km radius, a=15° parameters)" | View A, strain family |
| 17 | `cond_surf` | subsurface | "Conductivity surface - electrical conductivity of subsurface" | View A, sub family |
| 18 | `iso_grav_anom_hg` | gravity | "Isostatic gravity anomaly horizontal gradient - horizontal rate of change" | grav family |
| 19 | `det_elev_slope` | topographic | "Detrended elevation slope - gradient of elevation after detrending" | View B, topo family |

Three findings from putting S7 next to S1 and S6:

* **Band 6's tag is wrong and the bytes say so.** S1's own figure caption reads "total radiometric
  counts per second (left) and total magnetic intensity (right)", and S1's feature list contains no
  tilt-angle product at all; `IR-52-034` measured Spearman(band 6, GeoDAWN total-count grid) =
  **+1.0000** and Spearman(band 6, K+Th+U) = **+0.9915**. Band 6 is radiometric total count. This is
  why R5 puts it in **View B**: the brief defines View B as "DEM-derived curvature and slope, plus any
  radiometric bands in `training_features.tif`", and band 6 is that radiometric band. R4 excluded it
  on the strength of the tag; that exclusion rested on a false premise (`IR-R5-001`, `IR-52-034`).
* **Bands 10 and 16 are the "Density of earthquakes" of S1**, and staff name the upstream product:
  > "Those bands are the INGENIOUS earthquake rate density layers that have been clipped to the
  > GeoDAWN area and re-gridded to 100m. For more detailed information, you can look at the original
  > dataset on the INGENIOUS site (download 'Earthquake Density Models.zip', extract it, then look at
  > `eq_rate_density_details.docx`)." — S6, staff, with the link <https://gdr.openei.org/submissions/1391>

  That closes `IR-R4-002`: band 10's maximum of ~4.96 × 10⁶ is a *distance* in metres with no
  earthquake inside the 100 km / 15° sector, not a corrupted depth. Its footprint distribution
  (p1 118, median 623, p75 1,685, p99 50,237, max ~4.96 × 10⁶ — quoted by the asker in S6 and
  consistent with the bytes) is why it must be rank-encoded before any model sees it, and why R5 left
  it out. It is the only organiser band used nowhere in R5. See H60-B.
* **One product S1 lists is not in the file.** S1 promises magnetics "including reduced-to-pole
  magnetic anomaly, total magnetic intensity, the vertical and horizontal slope of total magnetic
  intensity, **and the top-of-crustal magnetic source depth estimate**". The five magnetic bands are
  `mag_anom`, `rtp`, `tmi`, `tmi_vg`, `tmi_hg` — anomaly, RTP, TMI and its two gradients. None is a
  source-depth estimate, and no band of any category is described as one. Recorded as `IR-R5-008`:
  do not write a hypothesis that depends on a magnetic source-depth layer, because it does not exist
  in the delivered data.

## 7. The board as it actually stands (S2)

Preserved row by row in `registry/leaderboard_snapshot_2026-10-08.json`, top 22 of the fetched list:

| rank | team | best public DW-Tversky | submissions |
| --- | --- | --- | --- |
| 1 | xiaofanhu | **0.3774** | 13 |
| 2 | alexoktaba | 0.3345 | 25 |
| 3 | nchuzhoy | 0.3262 | 6 |
| 4 | joeyfezster | 0.3260 | 24 |
| 5 | kinghorton42 | 0.3222 | 9 |
| 6 | Batik Shirt Brothers | 0.3221 | 23 |
| 7 | DARD | **0.3195** | 16 |
| 8 | ndavis7 | 0.2888 | 9 |
| 9 | mzoorob | 0.2884 | 27 |
| 10 | GrigorSargsyan | 0.2876 | 14 |
| 11 | HardcoreTechGod | 0.2854 | 6 |
| 12 | op01 | 0.2797 | 8 |
| 13 | **extradr19** (this family, owner-reported) | **0.2778** | 12 |
| 14 | arnofault | 0.2764 | 1 |
| 15 | No Fault of Our Own | 0.2761 | 24 |
| 16 | notmyfault | 0.2758 | 16 |
| 17 | wbg1 | 0.2750 | 14 |
| 18 | raboush2 | 0.2747 | 9 |
| 19 | li002666 | 0.2726 | 4 |
| 20 | smashi34 | 0.2710 | 12 |
| 21 | smrtdoog5 | 0.2708 | 12 |
| 22 | bot_account | 0.2707 | 1 |

**The brief's premise is wrong and it matters** (`IR-R5-005`): 0.3195 is rank **7**, not the top. The
top is 0.3774, exactly as this repo's own 2026-10-07 snapshot recorded and exactly as the H57
acceptance addendum in `README.md` warned ("never call 0.3195 'the highest score right now'"). Every
projection in this round therefore carries three bars, not one: 0.2778 (this family's best, rank 13),
0.3195 (the brief's stated target, rank 7) and 0.3774 (the board top, rank 1).

Two structural facts in the table are worth more than any single row:

* **There is a gap, not a gradient.** Ranks 8–22 span 0.2707–0.2888 (0.018 wide, fifteen teams);
  ranks 1–7 span 0.3195–0.3774. Between rank 7 and rank 8 the board jumps 0.031. Eleven teams sit in
  a band the width of our own best-to-worst spread, which is what a *shared ceiling* looks like: a
  family of approaches that all find the same easy fraction of the truth and then stall.
* **`arnofault` is rank 14 at 0.2764 with a single submission.** One attempt, inside 0.0014 of a
  family that has spent twelve. Whatever that team did, it did not need iteration — which is evidence
  that the ceiling is about *what you emit*, not about how many times you get to measure it.

## 8. What is still not verified, stated plainly

* No filename, hash, upload receipt or organiser-side score for any submission of this family. The
  file-to-score pairing remains owner-reported (`knowledge/06`, unchanged).
* The public/private chunking is unknown by explicit refusal (S5 answer 2), so the factor between the
  effective `|G| = 14,088.7` measured here and the final round's whole-area `|G|` cannot be computed.
* The mirror bytes in `data/` are integrity-pinned against a 23-file SHA-256 manifest but are **not**
  organiser-authenticated; `drivendata.org/competitions/306/competition-doe-gems/data/` still requires
  a login this sandbox does not have.
* Nothing in S1–S7 identifies which pixels are credited in any scored file. `|G|`, the atom credits
  and every ρ in `knowledge/10` remain inversions from reported scores, not measurements of truth.
