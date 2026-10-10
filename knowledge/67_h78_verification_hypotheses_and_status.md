# 67 · H78 — verification of the shipped GeoTIFF, the 0.2778 mechanism, five new hypotheses, and an unambiguous submission status (2026-10-09)

**Labels used below.** `MEASURED-H78` = re-computed in this session from restored bytes (script `scripts/h78_verify_h75.py`,
receipt `evidence/h78_verify_h75.json`). `HOLDOUT-DTI` = evaluator `gems52-pooled-hide-v1`, value carried from the H75
receipt, **not re-run** this session. `OWNER-REPORTED` = a public score attached to a file by the owner's own
notes or the owner's list, **not** an organizer receipt. `ORGANIZER-CONFIRMED` = **none exists anywhere in this repo.**
`SOURCE` = official page fetched or searched in this session (links in §9).

---

## 0. The answer, in one table (read this first)

| Question | Answer | Basis |
|---|---|---|
| Is there a unique GeoTIFF to download? | **YES — `submission/gems52-h75-dva-variogram-anisotropy-B-37654px-20261009T200333Z.tif`** (142,941 bytes, SHA-256 `b97691584d514ab1925d9fff2b61c410be86bdc0bc8c844dfdaa6257a4ea7a16`). Format-valid and not identical to any of the 13 restored rasters. | MEASURED-H78 §1, §4 |
| Is it OK to **submit** it to the competition? | **NOT under the repo's own rules.** The parallel-run lane rule fails: 0.922 of dots lie within 3 px of one registry raster (limit 0.70). Submitting is an **owner override** decision. It is not a validator decision. | receipt `evidence/h75_gates.json`; §5 |
| Does the file pass the official format? | Yes on every item the official page lists **except one convention question** (zeros, not NaN, outside the 5,167,373-px footprint; §3.3). Values are exactly {0, 1}, so the `Predicted values must be in range [0, 1]` rule is met. | MEASURED-H78 §1; SOURCE §9 |
| Did this session generate a *new* raster? | **No.** Only one holdout-positive ranker exists (H75). Any new raster would be either unvalidated or a lane duplicate, and this round had no validated candidate. §6 explains. | §6 |
| Slots used this round | **0.** No submission was made, and nothing was uploaded to DrivenData. | — |
| Does H75 beat 0.2778 or 0.3195? | **Unknown.** Holdout says H75 beats its own control `single_B` by +0.0118 [0.0068, 0.0174] (HOLDOUT-DTI). No organizer score exists for any file. Holdout DTI does not predict the board (repo measurement R4, Spearman −0.10). | §4, §5 |

**Plain-language status for the site:** download = **yes**; submit = **not approved by the lane rule**; owner must
decide the override. The site header now says this in the first screen (docs/index.html).

---

## 1. The shipped file, re-measured from disk (MEASURED-H78)

| Property | Value | Check |
|---|---|---|
| Format | single band, float32, deflate, tiled | `rasterio` 1.4.3 |
| CRS | EPSG:32611 | = `data/sample_submission.tif` |
| Shape | 3,730 × 3,292 | = template |
| Transform | (100, 0, 243350; 0, −100, 4508550) | = template; `transform_match: true` |
| NaN / inf | 0 / 0 | pass |
| Unique values | exactly {0.0, 1.0} | in [0, 1] |
| Positive pixels | 37,654 | dots |
| Positive pixels outside domain | 0 | `labels.tif == −1` → 0 dots |
| Out-of-domain pixels (labels == −1) | 7,111,787, written as **0** | see §3.3 |
| In-domain footprint | 5,167,373 px | matches `gates.py` comment |
| Catalogue (labels == 1) | 60,988 px | |
| Min distance dot → catalogue | 223.6 m (0 dots within 200 m) | the 200 m ring cut is applied |
| Median distance dot → catalogue | 1,552.4 m | |
| SHA-256 (file) | `b97691584d514ab1925d9fff2b61c410be86bdc0bc8c844dfdaa6257a4ea7a16` | matches the H75 receipt |

---

## 2. Why 0.2778 scored highest — the arithmetic, re-measured (answer to the brief's question)

**Short answer.** Among the owner's listed submissions, `h33-2-b2` (0.2778, OWNER-REPORTED) is the 0.2600 file
(`dotted-h19-5-d2-8`, OWNER-REPORTED) with its 100–200 m catalogue ring deleted. Deleting the ring raised the score. That is
only possible if the ring earned less credit than it cost in false-positive mass. The ring's implied credit density
is below break-even at every |G| in the repo's identified interval. The mechanism is measured. The organizer's
attribution of the score is not.

### 2.1 Pixel identities (MEASURED-H78)
* `h33-2-b2` (reference, 37,654 px, SHA `c55bafc4…ab6fa9`) ⊂ `d2-8` (44,090 px): **subset = True**.
* Pixels in `d2-8` but not in the reference: **6,436** (14.6 % of `d2-8`). All lie **100.0 – 200.0 m** from the catalogue (median 100 m).
* The reference has **0** dots within 200 m of the catalogue.

### 2.2 Credit density the ring must have had (MEASURED-H78, approximation stated)
Approximation: `DTI ≈ T / (0.2·S + 0.8·|G|)` (valid for dots more than 200 m apart; mass M ≈ T). Inputs: the two owner-reported
scores and the two dot counts. Solve for credited mass T; the ring's credit is the difference.

| \|G\| assumption (px) | Ring credit (T lost) | Ring credit density (per deleted px) | Break-even (0.2 × DTI = 0.2 × 0.2600) |
|---|---:|---:|---:|
| 5,949.3 (low end of repo's identified interval) | 115.9 | **0.0180** | 0.052 |
| 12,512.1 (high end of identified interval) | 22.5 | **0.0035** | 0.052 |
| 14,088.7 (superseded point estimate, shown for completeness) | 0.0007 | ≈ 0 | 0.052 |

**Read:** a deleted pixel is worth more than break-even only if its credit density exceeds 0.052. Every measured
bound is below it. So deleting the ring raised DTI. Recorded in `evidence/h78_verify_h75.json → ring_credit_density_implied`.

### 2.3 What it implies (interpretation, labelled as inference)
* One owner-reported pair is consistent with **hidden faults rarely lying 100–200 m from a catalogue trace**. The competition's
  hidden set is, by design, faults the USGS database lacks (SOURCE: problem page §"Competition structure"). Such faults can still
  sit near catalogue traces, but this pair suggests that the 100–200 m band carries little credit.
* Consequence: H75 keeps the 200 m exclusion. Any future candidate should keep it too. This is the one measured precision gain in the
  family, and it is free.
* **Limit:** n = 1 pair; both scores OWNER-REPORTED; the board is team-level and partial (public chunk), and the Phase-1 score is
  computed on a private test set. This is a consistent mechanism, not an organizer-confirmed one.

### 2.4 What the metric says about beating 0.3195 / 0.3774 (from the repo's algebra, re-checked)
`knowledge/49` §4 gives the required credit density. The repo's own conclusion stands: beating 0.3195 needs a
better ranker at roughly the same budget, not a smaller budget. H75 is the first measured holdout gain of this kind
(+0.0118). It is far from what the ρ-table requires, so **no evidence here says H75 will beat 0.2778 on the private set.**

---

## 3. The official rules that bind the choice (SOURCE; checked against the repo's files)

### 3.1 Metric (SOURCE: problem page, DrivenData page 967, chunk 1)
`DTI(α=0.2, β=0.8)`, distance-weighted with a triangular kernel, `R = 300 m` (3 px). `p(x) ∈ [0, 1]`.
FP-weight sums only over `p(x) > 0`. Read this session: `src/gems52/metric.py` computes TP_w, FP_w = mass − Σp·q, FN_w and `DTI = TP_w / (TP_w + αFP_w + βFN_w + ε)`, the same structure as the official equation.

### 3.2 Submission format (SOURCE: problem page, chunk 1; NLR rules PDF §3)
* EPSG:32611, 100 m, same bounds as training data.
* **Single layer, float32, values between 0 and 1.**
* **"data outside the bounds is null or nan."**
* "one GeoTIFF per user/team" (problem page diagram); "Participants will submit a single entry" (NLR rules §1.1).
* The **Final** round rescores the *same* file against an expanded label set (problem page, "Competition structure"). The choice of one file matters for both rounds.

### 3.3 The NaN-versus-zero question (open; owner decision)
* The official sample `data/sample_submission.tif` writes **NaN on exactly the 7,111,787 out-of-domain pixels** (verified: NaN pattern equals `labels == −1`).
* H75 writes **0** on those pixels. The metric is unaffected: zeros contribute nothing, and FP sums only `p > 0`.
* The owner-reported 0.2778 reference also writes zeros (`knowledge/62` IR-H73-001).
* Both conventions appear among public owner-reported scores (names ending `-zeros` and `-nan`). So both have been accepted by the platform in the owner's experience. This is OWNER-REPORTED, not a platform receipt.
* **Decision for the owner:** keep zeros (the 0.2778-style convention, the current file) or switch to the sample's NaN convention. Either way the 37,654 positive pixels are identical. Submit only one of them (one entry per team).

### 3.4 Irregularity in the official text (flag for review)
The problem page says "A sample submission that **predicts total fault absence** is provided." The repo's template is **not** total absence. Its 60,988 ones are exactly the labelled catalogue positives (verified this session). The registry already records this (`data_manifest.json` note). Any submission built by *copying the template's values* would be a copy of the catalogue. H75 uses the template only for grid, CRS and transform.

---

## 4. Uniqueness and overlap (MEASURED-H78, restored subset; the full census is a receipt)

| Comparison | Result (MEASURED-H78) |
|---|---|
| H75 pattern identical to any of 13 restored rasters | **No** (`identical_pattern = False` for all) |
| H75 equal to the union of the 13 restored rasters | **No** |
| Max binary correlation (phi) to a restored raster | **0.064** (`gems19-h19-5`) |
| H75 vs 0.2778 reference: shared dots | **1,742 px** (of 37,654); phi **0.039**; 54.9 % of H75 dots within a 3 px disk of a reference dot (receipt used a 7×7 box and reported 64.2 %; definitions differ, both are shown) |
| Full 565-raster census (receipt `evidence/h75_build.json`, `evidence/h75_gates.json`) | decoded-unique = true; equals union = false (**receipt, not re-run here**) |
| Census cross-check (this session) | All 13 restored rasters match census records by decoded SHA-256 (values with NaN set to 0). Their census near-dot values equal this session's independent measurements to three decimals (e.g. reference 0.549, `gems19-h19-4` 0.664). The receipt is therefore consistent with the bytes. |

Restored set: `data/sample_submission.tif`, `data/labels.tif`, the 0.2778 reference and 12 scored priors, all SHA-256 verified by `scripts/restore_data.py` (ALL_VERIFIED=True).

---

## 5. Lane gate — why H75 is not submittable under the repo's rules (MEASURED in receipt)

The parallel-run protocol (the user's brief) sets two lane limits against any *registry* raster:
rank correlation > 0.90, or > 70 % of dots within 3 px of one registry raster's dots.

| Statistic | Value | Verdict | Source |
|---|---|---|---|
| Surface max Spearman vs 565 priors | 0.466 | PASS | `evidence/h75_gates.json` |
| Dots max Spearman | 0.108 | PASS | same |
| Dots max near-dot (3 px) — informative priors | **0.922** (38 offenders; worst is a non-probe prior) | **FAIL (> 0.70)** | same |
| Literal max near-dot incl. 7 universal-coverage probes | 1.000 | probes cannot localise a lane (`gates.PROBE_COVERAGE = 0.95`) | same |
| Restored 13-raster subset, informative max near-dot | 0.664 | PASS **on this subset only** | MEASURED-H78 |

**Important nuance (flag for review).** The subset check passes, but the verdict is set by the **565-raster census**, of which
only 13 rasters are restored here. None of the 38 informative offenders is among the 13 restored rasters (their census
digests are not among ours), and the worst offender (0.922) is not restored. So the subset is not evidence of a pass. The census receipt remains the authority.

**What the lane rule is.** It is the parallel-run protocol's *internal* diversity rule, measured against the owner's own registry.
It is **not** a DrivenData competition rule. Whether to submit a holdout-best file that duplicates other internal submissions is
a team-coordination decision. The file is not disqualified by the competition's text.

---

## 6. Why no new raster was generated this session

1. **Only one measured holdout gain exists** (H75, +0.0118, CI excludes zero). Any new raster needs the 419 MB training raster
   restored and a holdout run. The restore is redistribution-sensitive (§8.2). I did not restore the training raster this session.
2. **The protocol's three-experiment budget** is already spent on H75. A new raster would need a new preregistration first.
3. **Any candidate that would pass the lane rule on the full census is structurally blocked** (`knowledge/65`–`66`, `knowledge/62` IR-H73-001,
   §5 above): the registry's dense priors leave no room for a lane-valid emission at this budget. Generating another file to
   pass the lane gate would be a lane duplicate by construction.
4. The user asked for the answer and a candidate that is **validated before** a slot is used. A raster without a validation
   would not meet that standard. The five hypotheses in §7 are the route to the next validated raster.

---

## 7. Five candidate hypotheses (not yet tested), ranked

**Ranking rule.** Rank by *expected DTI improvement* (qualitative: L / M / H, grounded in the measured holdout behaviour of
the family) against *implementation cost* (L / M / H). No number below is a score (protocol: "a projection is never written as a score").
"Validatable here" means: can the holdout be run from this sandbox with the data it needs?

| Rank | ID | Layer(s) and physical signature | Why it should catch a fault the catalogue lacks | How it differs from what is implemented | Mimic (named non-fault process) | Expected gain / cost | Data access (verified) | Validatable here? |
|---|---|---|---|---|---|---|---|---|
| **1** | **H78-1 · strike-aligned directional variogram (DVA+)** | `det_elev`, `det_elev_slope`, `iso_grav_anom` (as H75); add bands 15 (depth-to-basement) and 18 (grav HG), per H75 next steps. Directional semivariance at 200/400 m lags, azimuth **aligned to the regional NNE Basin-and-Range strike** rather than four fixed azimuths. | A 300–900 m damage zone makes local texture strike-parallel-smooth and strike-normal-rough. Aligning the azimuth to the regional fault set tests the *family* of hidden faults, not just any anisotropy. | H75 already has 4-azimuth DVA (README H75 block: "lags 200/400 m, 4 azimuths"). H78-1 adds a strike prior and two bands. Same learner, same holdout. | Linear drainage incision, roads and range-front bajada edges make anisotropic topographic texture. Bedding in gravity. | **L–M / L** (H75 measured +0.0118 over control) | Competition inputs: owner mirror (§8.2). Feature store must be rebuilt. | **Yes**, if the training raster is restored (redistribution question first). |
| 2 | **H78-2 · INGENIOUS 2 m shallow-temperature probes as a cover test** | GDR 1391 `2m Temperature Probes.zip` (1.03 MB, CC BY 4.0). Shallow temperature anomaly after removing a background (elevation, slope, albedo, vegetation covariates), tested for alignment with candidate structures. | Hot fluid rising along a permeable fault in cover warms the ground at 2 m. This is a physical measurement independent of mapped traces, and it targets the brief's "fault buried beneath cover" case. | Not used anywhere in `src/` or `scripts/` (grep, this session). The repo's shallow-temperature knowledge is only the r3 list entry. | Shallow groundwater, irrigation, soil moisture, vegetation, cold-air drainage; **non-random probe placement** (sites chosen where anomalies were expected). | **M / M** | GDR 1391 (CC BY 4.0). **Not obtainable from this sandbox** (`gdr.openei.org` returns 000; fetch tool HTTP 500). Owner must download and pin SHA-256. | No, until the owner supplies the zip. Sparse points need declustering and a background model before any holdout. |
| 3 | **H78-3 · Landsat TIRS night-time surface-temperature residual** | USGS Landsat C2 L2 **ST** (public domain). TIRS is 100 m native (resampled to 30 m by USGS), which matches the 100 m competition grid. Night-time ST residual after elevation, slope, albedo and thermal-inertia correction, following the Coolbaugh et al. (2007) ASTER method. | Surface heat from the subsurface reaches the surface along fault pathways. A residual at night, after removing the solar-heating terms, is the physical signature. | No Landsat or thermal-residual feature exists in this repo (grep: 0 hits in `src/` and `scripts/`). | Thermal-inertia contrasts (lithology, dark basalt, playa, water bodies), irrigation, roads (the brief names roads as a surface artifact), cold-air pooling. | **M–H / H** | USGS Collection 2 L2 ST: public domain (SOURCE). Download is through EarthExplorer or an AWS mirror (SOURCE: USGS page); whether an account is required is **to be confirmed by the owner**. **Neither route is reachable from this sandbox** (usgs.gov returns 000). | No. Scene selection, cloud masking and day/night compositing are required first. |
| 4 | **H78-4 · paleo spring-deposit (sinter/tufa) proximity as a fossil-upflow prior** | GDR 1391 `Paleo Geothermal Features.zip` (82 kB, CC BY 4.0): mapped sinter and tufa deposits. Distance to deposits, tested as a *positive* prior along structures. | Fossil springs mark past upflow. Their alignment with structure is the signature. | Planned as H58-D and never validated (`knowledge/19`, `scripts/publish_h58_site.py`). Not in the feature store. | **Wave (shoreline) tufa** forms along former lake margins, not over faults, so it lies on a lake-level contour. Spring-fed tufa *columns* are the fault-linked form (SOURCE: Coolbaugh et al. 2009 as summarised in the ResearchGate record). A shoreline-elevation test must separate the two. | **L–M / L–M** | GDR 1391, 82 kB, CC BY 4.0. **Not obtainable from this sandbox** (same gdr.openei.org failure). | No, until the owner supplies the file. |
| 5 | **H78-5 · USGS Great Basin conductive heat-flow residual** | USGS heat-flow maps, DOI 10.5066/P9BZPVUC (public; in GDR 1391 "Heat Flow Maps"). Residual = observed-minus-background heat flow (per the USGS description). | Hydrothermal convection shows as a positive residual above background conduction. | Proposed as H72-D and judged not viable (`knowledge/59`). Not in the feature store. | Regional groundwater and basin-fill thermal conductivity contrasts. | **L / L** | Public USGS data release (SOURCE). Not reachable from this sandbox. | No. Grid is km-scale; the 100 m dot metric cannot resolve the faults it would point to. Rank last for that reason. |

**Considered and rejected for this round**
* *Phase congruency / scale-space ridges on existing DEM.* Overlaps the 16 curvature and 13 structure-tensor files already in `src/`/`scripts/`. Low novelty.
* *Euler-deconvolution lineaments.* Already tested as H8 (the owner's list reports `h8-euler-lineament-depthcluster` at 0.0355; 'Euler' appears in 8 knowledge files). Not new.
* *GDR 1391 "Quaternary Faulting Slip and Dilation Tendency" (DOI 10.5066/P9YL58W6).* Derived from the Qfaults catalogue. It cannot find faults the catalogue lacks. Circular for this metric.
* *GDR 1391 MT electrical conductance, detrended elevation, gravity and magnetics, earthquake density, geodetic shear.* All are already in the competition feature stack (problem page feature list). Not new.
* *GDR 1391 well and spring chemistry (19.85 MB).* Could support geothermometry (H58-C, never run). Deferred; it is a well-and-spring product, not a fault product, and needs a temperature model first.

**Top candidate and why.** H78-1 is ranked first because it is the only candidate with a measured positive holdout behaviour
in this family (H75), it is the cheapest to validate, and its mimic set is named. Its gain is expected to be small.
**It is not validated in this session.** Validation requires a preregistration (`knowledge/68`, not written this round), the training raster
(§8.2), and a run of the H75 instrument with the strike prior. That is the next session's first step.

---

## 8. Access, limits and what must be decided

### 8.1 Sandbox egress (MEASURED this session)
* `api.github.com` → 200. `gdr.openei.org` → 000 (no connection). `www.usgs.gov` → 000. The allowlist is GitHub, PyPI and npm only.
* Consequence: every GDR 1391 file and every USGS raster is **owner-download only**. H78-2, H78-3, H78-4, H78-5 cannot be validated here.

### 8.2 Competition-input provenance (flag for review)
* The DrivenData data tab is login-walled (SOURCE: the repo's data-manifest note).
* The repo restores the competition rasters from **the owner's public GitHub repositories** (`registry/data_manifest.json`), verified by SHA-256 against pins. This is an integrity check, **not** organizer authentication.
* **Review item:** the competition rules may restrict redistribution of competition data. Whether a public GitHub mirror of the three official rasters complies with those rules has **not** been verified. This session restored only the template, the labels, the 0.2778 reference and 12 scored priors (small). The 419 MB training raster was **not** restored.
* DrivenData's Terms of Use prohibit automated access (`registry/source_policy.json`). This session made no automated portal or leaderboard requests. Two official pages were read once each through the page-fetch tool (problem page; NLR rules PDF). The leaderboard figures come from the existing 2026-10-08 snapshot.

### 8.3 Decisions only the owner can make
1. **Submit H75 under a lane override?** Download is yes. Submit is an owner override (§5).
2. **Zeros or NaN outside the domain?** Both are allowed by the official text; the positives are identical (§3.3).
3. **Lane rule scope.** Should the internal diversity rule be measured against the full census (current) or against scored submissions only (`knowledge/66` next step 1)? The answer changes whether any lane-valid file exists.
4. **Redistribution.** Confirm the competition rules allow the owner's public mirror, or stop using it.
5. **Free sources the owner must download.** GDR 1391 (2 m probes, paleo features; CC BY 4.0) and USGS Landsat C2 L2 ST (public domain; needs a free EarthExplorer account).

---

## 9. Sources (every link is official or a peer-reviewed/record citation; open these for manual review)

| Claim | Link | Checked |
|---|---|---|
| Metric, format, one-entry rule, feature list | <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/> | fetched this session (chunks 0–1) |
| Official rules: single entry, format, two phases | <https://docs.nlr.gov/docs/fy26osti/96647.pdf> | fetched this session (chunks 0–1) |
| Leaderboard (manual review only; not scraped) | <https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/> | snapshot `registry/leaderboard_snapshot_2026-10-08.json` |
| Competition data page (login-walled) | <https://www.drivendata.org/competitions/306/competition-doe-gems/data/> | not accessed |
| INGENIOUS regional compilation GDR 1391 (CC BY 4.0; 2 m probes; paleo features; heat flow DOI) | <https://gdr.openei.org/submissions/1391> · DOI <https://doi.org/10.15121/1881483> | fetched this session |
| 2 m probe zip | <https://gdr.openei.org/files/1391/2m_temperature_probe_INGENIOUS_regional_data.zip> | HTTP 500 via fetch; 000 via shell |
| Paleo geothermal features zip | <https://gdr.openei.org/files/1391/paleo_geothermal_regional.zip> | HTTP 500 via fetch; 000 via shell |
| USGS Great Basin heat-flow maps (DOI 10.5066/P9BZPVUC) | <https://doi.org/10.5066/P9BZPVUC> · <https://catalog.data.gov/dataset/heat-flow-maps-and-supporting-data-for-the-great-basin-usa> | searched this session |
| Landsat Collection 2 Level-2 Surface Temperature (public domain; ST = DN×0.00341802 + 149.0 K) | <https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-temperature> · DOI <https://doi.org/10.5066/P9OGBGM6> | searched this session |
| Landsat 8 TIRS: 100 m native, resampled to 30 m | <https://science.nasa.gov/mission/landsat-8/> · <https://www.usgs.gov/centers/eros/science/usgs-eros-archive-landsat-archives-landsat-8-9-operational-land-imager-and> | searched this session |
| Coolbaugh et al. (2007) ASTER TIR at Bradys Hot Springs; diurnal and thermal-inertia correction; named mimics | Remote Sens. Environ. 106(3):350–359 · PDF <https://pages.mtu.edu/~scarn/teaching/GE4250/coolbaugh_RSE07_ASTERGeothermal.pdf> | searched this session |
| Thermal IR remote sensing of geothermal systems (review) | <https://link.springer.com/chapter/10.1007/978-94-007-6639-6_22> | searched this session |
| Spring-fed tufa columns mark faults; wave tufa forms on shorelines (Pyramid Lake / Lake Lahontan) | <https://www.researchgate.net/publication/289616550_Carbonate_tufa_columns_as_exploration_guides_for_geothermal_systems_in_the_Great_Basin> · <https://www.sciencedirect.com/science/article/abs/pii/S003442571000146X> · Dudley et al. 2012 (Astor Pass tufa columns along a fault; NASA ADS record, no direct link captured) | searched this session |
| Blum & Mitchell 1998 co-training | <https://doi.org/10.1145/279943.279962> | cited in the brief |
| Tversky index | <https://en.wikipedia.org/wiki/Tversky_index> | cited in the brief |

---

## 10. Irregularities (flagged for review; recorded in `registry/irregularities.json` as IR-H78-001…009)

* **IR-H78-001** — The brief says 0.3195 is "the highest score right now." The 2026-10-08 snapshot shows 0.3774 (xiaofanhu) at rank 1. 0.3195 is rank 7 (DARD). Owner-reported public values, not organizer-confirmed.
* **IR-H78-002** — The official sample is described as "total fault absence." The repo's template is the catalogue itself (60,988 ones = catalogue positives).
* **IR-H78-003** — H75's zeros outside the domain versus the official "null or nan" (7,111,787 px). Open owner decision (§3.3).
* **IR-H78-004** — The H75 executive summary said the zeros "fix" the "must be in range" error. That was not verified: the cause of the earlier error on another file is unknown. Corrected in this round's edit.
* **IR-H78-005** — The lane verdict depends on the 565-raster census. The 13 restored rasters are census members (decoded digests match), and their near-dot values match this session's measurements, but none of the 38 offenders is among them (their maximum is 0.664, under 0.70). The subset therefore cannot show a pass. The receipt is the authority (§5).
* **IR-H78-006** — Competition inputs are restored from the owner's public GitHub mirrors. Redistribution compliance is unverified (§8.2).
* **IR-H78-007** — The 0.2778 file ↔ score link is OWNER-REPORTED and the board is team-level. The mechanism in §2 is measured on bytes, but the score attribution is not (§2.3).

* **IR-H78-008** — `scripts/check_site.py` failed (exit 1) on R5's novelty: recomputed 0.992087 vs receipt 1.0. Cause: the H75 raster was dated only by day (`20261009`), so the checker could not date it and counted it as present when R5 was built (build time 2026-10-08T23:51:56Z). With H75 moved out, the check gives 1.0000 over 58 rasters, and the check passes. Fix (disposition below): the H75 raster, sidecar and zip were renamed with the UTC write time `…20261009T200333Z` (the file's own mtime, 2026-10-09 20:03:33 UTC). The TIF bytes are unchanged (SHA-256 `b97691584d…`). The zip was rebuilt with the new inner name; its SHA-256 is now `7ff4e50d…` (the old zip `c9285571…` no longer exists). The restored owner rasters in `data/scored` and `data/reference` were removed from the git-ignored `data/` after the census check, to match CI, which restores only the template and labels. Re-restore with `scripts/restore_data.py` to reproduce.

* **IR-H78-009** — `origin/main` (after PR #76) fails `scripts/check_site.py`: R5 novelty 0.991607 != receipt 1.0. Cause: PR #76's H76 gravity raster is undated, so the checker counts it as present at R5's build. It shares 8 exact dots with R5. On this branch the value is 0.999520. Not caused by this PR, and not changed here: the true build time is not recorded in the repo. Owner or that round's author must date it (§ registry IR-H78-009).
