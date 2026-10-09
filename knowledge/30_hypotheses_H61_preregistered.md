# H61 — hypotheses and protocol, preregistered 2026-10-08 **before** any H61 fit, score or artefact

Frozen file: this document's SHA-256 is recorded in `registry/h61_preregistration.json` before the
first model is fitted, and `scripts/run_h61.py` refuses to run if either hash has moved. Nothing
below was written after seeing an H61 result. Lane: the brief's two-view co-training paragraph
(View A potential-field/subsurface, View B surface), disagreement as the discovery signal.

---

## 0 · What H61 repairs, and why that came first

The brief says: reuse the shared tools, and *if a shared tool is wrong, fix it once in the template
and report it*. Three repairs were made before any model was fitted, all measured from
SHA-256-pinned bytes by `scripts/h61_forensics.py` (`evidence/h61_forensics.json`):

**R1 — masked support `S`.** The organiser masks known USGS/INGENIOUS fault pixels out of
evaluation (staff, community thread 11516, posts #2 and #4, quoted in `src/gems52/holdout.py`).
H60 nevertheless charged each file its raw positive count. The bytes settle it:
`8GEMSDOE_Hedge-v2_submission.tif` and `gemsdoe-ens12-adopted-7f00890a.tif` have **identical**
off-catalogue support (166,519 px, verified pixel-for-pixel, Jaccard 1.000) and both report
**0.1563**, yet raw-`S` accounting gives them different credit (8,873.5 vs 7,168.8). Masked
accounting gives both **6,967.0**. All H61 economics use masked `S`.

**R2 — `|G|` is an interval, not a measurement.** The 13 score equations carry 14 unknowns (13
credits + `|G|`), so `|G|` is only set-identified. Two rigorous constraint families bound it:
`T_i ≤ |G|` for every file, and max-cover monotonicity `T_X ≤ T_Y` on every nested pair
`X ⊆ Y`. Measured on the bytes, with masked `S`:

> **|G| ∈ [5,949.3, 12,512.1] px.** Lower bound binds on `Hedge-v2`; upper bound binds on the
> nested pair `gems24-d1-5 ⊂ gems27-tgc-v2` (0.2477 > 0.2449 with 60,069 ⊂ 61,328 px).

The previously published point value **|G| = 14,088.7 lies outside that interval**. It is what the
champion/base nested pair yields *only* under the extra assumption that the 6,436 px the champion
deleted earn exactly zero credit; the sensitivity table shows `|G|` falls to 12,333 at just 25
credit of ring income and to 7,066 at 100. H61 therefore reports economics at both interval ends
and never reuses 14,088.7 as a measurement. Nested-pair lattice, measured: `A ⊂ B ⊂ E`,
`A ⊂ E`, `C ⊂ D`, `C ⊂ E`, `Hedge-v2 ≡ ens12`.

**R3 — band 6 identity resolved.** The file's own description says *"tc — Tilt angle or total
curvature — magnetic field derivative for edge detection"*, and three rounds carried that as an
unresolved irregularity (IR-52-019 / IR-52-034). Measured against the independently derived,
SHA-pinned external GeoDAWN grids on 400,000 eligible pixels:

| comparison | Spearman ρ |
|---|---:|
| band 6 vs external **TC** (radiometric total count) | **1.0000** |
| band 6 vs tilt angle of TMI computed from bands 9/3 | 0.0175 |
| band 6 vs `tmi_hg` (band 3) | −0.1512 |
| band 6 vs `tmi` (band 14) | −0.1483 |

Band 6 is **radiometric total count**, in View B. This is provisional-identity-resolved, not
units-authenticated: the external grid is a uint8 percentile quantisation of the USGS GeoDAWN
release (DOI 10.5066/P93LGLVQ) and its absolute units are not verified here.

**R4 — attribution strength is not uniform.** Only **3 of 13** owner-reported scores are
hash-linked to the bytes held (the owner's filename token is a prefix of the file SHA-256):
`d28-poisson300m-offcat-44090 → 0.2600` (91eae1ca), `gems-submission-…-7f00890a → 0.1563`,
`2314b599 → 0.0107`. The champion's `0.2778` token `e5eb6e7e` matches **none** of six hash
conventions of the bytes held, and GEMSDOE32's own page says no organiser score exists. So the
single number the whole `|G|` story rests on is the *weakest*-linked number in the set. H61 labels
it `FILENAME-ONLY-OWNER-REPORTED` and never as ORGANIZER-CONFIRMED.

---

## 1 · Ranked candidate hypotheses (the brief's 3–5, with layers / signature / novelty / cost)

### H61-A — Deep-sharp co-training: upward-continued magnetics × radiometric alteration — RANK 1, implemented

* **Layers.** View A: `training_features` bands 1 `mag_anom`, 2 `rtp`, 3 `tmi_hg`, 5
  `iso_grav_anom_slope`, 9 `tmi_vg`, 11 `iso_grav_anom_vg`, 13 `iso_grav_anom`, 14 `tmi`,
  18 `iso_grav_anom_hg`, 4 `geod_2ndinv`, 7 `geod_shearrate`, 8 `geod_dilaterate`, 10
  `deq_n100a15`, 16 `ieq_n100a15`, 15 `depth_to_base_surf`, 17 `cond_surf`, plus the template's
  derived gravity/cover/RTP gradient, persistence and coherence channels, **plus the external
  `TMI_up150`** (upward continued 150 m) rank and its σ=1, 3 gradient magnitudes.
  View B: bands 12 `det_elev`, 19 `det_elev_slope`, 6 `tc` (= radiometric total count, R3), the
  template's derived elevation/curvature/slope/local-residual channels, **plus the external
  radiometric K, Th, U and the Th/K, U/K, U/Th ratios**, rank and σ=1, 3 gradients.
  External TC is excluded as a column because it is rank-identical to band 6 (ρ = 1.0000).
* **Physical signature targeted.** A *depth separation*, not a new edge detector. Upward
  continuation is a low-pass filter in the wavenumber domain: continuing TMI to 150 m attenuates
  shallow, short-wavelength sources and passes deep basement-scale ones, so View A becomes
  genuinely "deep structure". Gamma-ray spectrometry senses only the top ~30–50 cm of the ground,
  so K/Th/U and their ratios are genuinely "surface/sub-outcrop lithology and alteration". The two
  views then differ in *sampling depth*, which is the physical content the Blum–Mitchell
  conditional-independence premise needs and which a single-raster feature split cannot supply.
* **Why it should catch a catalogue-missing fault.** The USGS/INGENIOUS Quaternary-fault catalogue
  is compiled from *surface expression*. A range-front or basin-margin fault buried under alluvium
  has (i) a deep magnetic/gravity fabric step that survives upward continuation, and (ii) **no**
  surface scarp and no radiometric lineament, because nothing is exhumed. That is exactly
  "A confident, B abstaining". Conversely "B confident, A abstaining" is the surface-artefact class
  (road cut, erosion line, graded fan margin, lithologic contact) and is *not* emitted.
* **Difference from everything already in this repository.** H55/H56/H57/H59/H60/CTD5 all built
  View A and View B from `training_features.tif` alone (`external_data_used: false` in every
  stored manifest), so their "two views" were two band groups of one survey at one sensing depth.
  H61 is the first round in which the external GeoDAWN radiometrics enter View B and the
  upward-continued TMI enters View A, and the first in which band 6's identity is measured rather
  than assumed. `src/gems52/external.py` is the shared extension; there is no private fork.
* **Expected DTI improvement / cost.** Expected DTI improvement: **none claimed**. The economics
  in §0 put the acceptance bar at credit density 0.056–0.059 per emitted pixel (α·DTI at
  DTI = 0.2778) against 0.010–0.021 for uniform random, i.e. a detector must be 3–6× better than
  random per dot merely to raise DTI, and ≥ 0.129 density to *tie* the champion. No instrument in
  this repository can certify that for novel mass (R4 and §3). Cost: medium, ~30–45 CPU-minutes on
  2 cores, no new external data.

### H61-B — Matched-budget disagreement ranking (a protocol repair, not a geology claim) — RANK 2, implemented

* **Layers.** The two OOF probability mosaics from H61-A.
* **Signature.** Disagreement as a *continuous rank difference* `rank(p_A) − rank(p_B)`, defined on
  every eligible pixel, rather than as a hard confident/abstaining mask.
* **Why.** CTD5's primary comparison was declared budget-incomparable and therefore ineligible:
  its candidate arm filled only 2,041 of 3,058 requested dots in fold 1 while every control filled
  its budget. A rank-difference field cannot run out of support, so `nodes.spacing_select` fills
  every arm's budget exactly and the comparison becomes eligible. This repairs the *instrument*,
  which is the reason CTD5's negative result could not falsify the geological mechanism.
* **Difference from prior work.** H57/H59/CTD5 all emitted hard-masked disagreement sets.
* **Cost.** Low.

### H61-C — Registry-saturation policy for the lane gate (a gate repair) — RANK 3, implemented

* **Layers.** The 526-blob prior census `evidence/ctd5_prior_inventory.json`, re-materialised and
  SHA-verified by `scripts/fetch_prior_inventory.py` (524/526 census-hash matches; the 2 exceptions
  are the census' own two ineligible entries: a 32×48 fixture and a format-test file).
* **Problem, measured.** CTD5 stopped because the literal rule ("more than 70% of your dots within
  3 px of ONE registry raster's dots") is unsatisfiable on this footprint: the 13GEMSDOE
  spacing-five lattice `20261001_r13-lattice-s5_v2_nan-outside.tif` covers **every** eligible pixel
  within 3 px (`evidence/ctd5_registry_saturation.json`). A spacing-5 square lattice has maximum
  interior distance √(2²+2²) = 2.83 px < 3 px, so *no nonempty raster can pass*. A gate that no
  admissible answer can pass carries no information about lane drift.
* **Policy, fixed prospectively in the shared gate, not per-round.** Classify each registry raster
  by measured **3 px coverage** = fraction of eligible pixels within 3 px of its support. A raster
  with coverage ≥ 0.95 is a `universal-coverage probe`: it localises nothing, so the directed
  proximity statistic against it is vacuous. The literal 0.70/3 px rule and the 0.90 rank-correlation
  rule are then applied to **informative** rasters only, while the raw literal value against *every*
  raster — probes included — is still reported, unaltered, next to the policy verdict. Nothing is
  deleted, no threshold is relaxed, and the classification is a measured property of the prior, not
  of the candidate.
* **Cost.** Low. Already implemented in `src/gems52/gates.py::lane_report`.

### H61-D — Cross-file credit localisation by terrain stratum — RANK 4, **not run this session**

* **Idea.** Cross the LP atoms (file-membership signatures) with terrain strata (slope, modelled
  cover thickness, radiometric alteration) and bound credit per stratum, to learn from organiser
  scores *where* hidden truth sits rather than *which prior* found it.
* **Why deferred.** Budget rule: stop after 3 experiments. H61-A/B/C are the three. This is the
  highest-value next experiment and needs no new data.

### H61-E — New external data that would be needed for anything stronger — named, availability checked

* Free and official, named for manual review: USGS GeoDAWN release DOI **10.5066/P93LGLVQ**
  (raw K/Th/U/TC and magnetics, not the uint8 mirror); USGS **3DEP** 1 m DEM
  (https://www.usgs.gov/3d-elevation-program); GDR submission **1391** (INGENIOUS,
  https://gdr.openei.org/submissions/1391, CC BY 4.0); USGS SGMC geologic map faults; Nevada
  Bureau of Mines and Geology 1:250,000 plates.
* **Availability from this sandbox: NOT obtainable.** Egress is limited to github.com,
  codeload.github.com, api.github.com, registry.npmjs.org, pypi.org and files.pythonhosted.org.
  Every USGS/GDR/DrivenData host is unreachable, so no idea requiring a fresh official download is
  proposed as viable this session. The pinned mirrors are used instead and are labelled as such.

---

## 2 · Frozen decision rules (checked by code, not by prose)

1. Folds: `gems52.spatial.folds` **label-blind-quadrants-v2** (the corrected splitter), buffer
   80 px, whole 8-connected catalogue components hidden in full. The rejected v1 tail-halo splitter
   is never used for promotion evidence.
2. Leakage canary: raw single-feature AUC of **every** used feature on **every** fold's held-out
   evaluation sample (held-out positives + catalogue-zero proxies ≥ 5 px from any visible trace).
   Alarm at AUC > **0.90** (direction-insensitive); the top-5 features also get a fitted
   single-feature HGB AUC to catch non-monotone leakage. Any alarm ⇒ the feature is dropped and the
   drop is recorded; the run is not silently continued.
3. Independence: `spatial.negative_block_errors` on 50×50 px blocks (min 32 negatives) over
   held-out catalogue-zero proxies, then `spatial.independence` with abandon threshold
   **max |ρ| ≥ 0.60** on Pearson and Spearman of both block MSE and block false-positive rate.
   If it fires, the pseudo-label exchange is **abandoned**, the pre-exchange field ships, and the
   receipt says so.
4. Pseudo-label exchange: exactly **one** round, `spatial.whole_pseudo_segments`, donor operating
   rank ≥ 0.95, receiver rank ∈ [0.35, 0.65], whole 8-connected segments of ≥ 5 px, wholly inside
   the fold's training domain, wholly inside one 50×50 block, and disjoint from the evaluation
   region, the hidden components, the visible catalogue and its 4 px collar, and the sampled
   training labels. Cap 2,000 px per direction per fold. No second exchange, no post-result
   hyperparameter search.
5. Budgets: **K = 9,400 dots per fold for every arm**, placed by `nodes.spacing_select` with
   `min_px = 3.0` (the 300 m kernel radius). Arms: `single_A`, `single_B`, `union_max`,
   `disagreement_pre`, `disagreement_post`, `random`. An arm that cannot fill K invalidates the
   comparison and the receipt must say so; no arm may be rescued by changing K afterwards.
6. Score: `gems52.evaluate_holdout` (evaluator `gems52-pooled-hide-v1`), pooled TPw/FPw/FNw,
   α 0.2, β 0.8, 300 m triangular kernel, 95% paired physical-cluster bootstrap (200 px = 20 km
   blocks, 1,000 draws). Every number is labelled **HOLDOUT-DTI** with evaluator version, withheld
   positive count and CI. **No HOLDOUT-DTI is written as a score, and none is used alone to
   promote**: R4 of `knowledge/29` records that this simulator measured Spearman −0.10 against the
   owner-reported board and that uniform random beat the champion on it.
7. Emission domain: eligible footprint ∧ > 200 m from any catalogue pixel (the measured zero/low
   credit ring, §0 R2 sensitivity) ∧ inside the sample-submission finite footprint. Values exactly
   {0, 1}, float32, no NaN anywhere, grid identical to `sample_submission.tif`.
8. Uniqueness/lane gate: `gates.lane_report` against the **whole** 526-blob census, with the R4
   saturation policy. Verbatim literal statistics are reported for every prior. Spearman > 0.90 or
   near-dot fraction > 0.70 against any *informative* prior ⇒ **DUPLICATE / STOP**.
9. Not-the-union check: the shipped field must differ from `max(A, B)`, from each single view, and
   from the union of separately emitted A/B controls, with the differing-cell counts published.
10. Verdict: `promote` only if the artefact passes the format gate, the lane gate, the not-union
    check **and** its projected organiser-DTI interval exceeds the champion's under masked
    accounting at *both* ends of the `|G|` interval. Otherwise `negative` / research-only, and the
    page must say **DOWNLOAD: YES · SUBMIT: NO** without ambiguity.

## 3 · The named non-fault process that could mimic H61-A's signal

**A non-fault basin-fill density boundary or a volcanic lithologic contact.** Both produce a
gravity-gradient step and a magnetic fabric edge under alluvium with no surface scarp — the exact
A-confident/B-abstaining signature. Radiometric K/Th contrast also occurs at lithologic contacts
with no structure at all. Secondary mimics: buried palaeo-channels and alluvial-fan margins
(linear, low-slope, conductivity contrasts), dyke swarms, and the survey's own flight-line
artefacts, which appear as parallel linear features in upward-continued magnetics. The falsifier
for each candidate is independent evidence of *offset* — a displaced contact, a deflected drainage,
a facies termination or a published structural interpretation — none of which is claimed here.
Fault candidates are not geothermal vents, and neither establishes permeability or a reservoir.

## 4 · Falsification conditions

* Any single feature with held-out AUC > 0.90 ⇒ that feature is leaked until proven otherwise.
* max |ρ| ≥ 0.60 on block negative errors ⇒ co-training abandoned (this would be the fourth or
  fifth independent refutation in this family: H57 0.1108, H59 0.1071, H60 0.1175, R4 0.7051).
* `disagreement_post` not above the best single-view control at matched budget, with a paired CI
  that includes zero ⇒ the discovery signal is refuted at this operating point.
* Near-dot fraction > 0.70 or Spearman > 0.90 against any informative prior ⇒ DUPLICATE / STOP.
* Projected DTI interval not above the champion at both ends of `|G|` ⇒ research-only, no slot.

## 5 · Official sources for manual review

* Metric, submission format, dataset: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
* Masking clarification (staff): https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4
* Blum & Mitchell, COLT '98 pp. 92–100: https://doi.org/10.1145/279943.279962
* USGS GeoDAWN airborne magnetic & radiometric survey: https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and (DOI 10.5066/P93LGLVQ)
* INGENIOUS / Great Basin Center for Geothermal Energy: https://gbcge.org/current-projects/ingenious/
* GDR submission 1391: https://gdr.openei.org/submissions/1391
* EPSG:32611 (UTM zone 11N): https://epsg.io/32611
* Tversky index: https://en.wikipedia.org/wiki/Tversky_index
* Reference solution: https://github.com/drivendataorg/gems-prize-reference-solution

## 6 · AI-use disclosure

An AI assistant wrote the code, this protocol and the candidate-review templates. No geologist
verified any emitted structure, no field observation was collected, and no organiser score,
acceptance or leaderboard gain is claimed for any H61 artefact.
