# 78 · H85 session review (2026-10-10): why 0.2778, can we beat it, what we measured, what is still missing

Read with `knowledge/77_standing_brief_2026-10-10.md` (verbatim brief) and `README.md` (H85 block).

**Round identity.** The brief's first run of this work was labelled H84 on branch `arena/ffd3ba3f-gemsdoe52`.
`origin/main` already held an H84 round from another session (PR #83: harmonic variogram-ellipse anisotropy),
so this round was renamed **H85** before merge (identifier-only; no bytes changed; precedent IR-H66-015, IR-H84-006).
Every H85 artifact in this session uses the name H85.

**Slots used: 0. Competition uploads made: 0. Organiser receipts held: 0.**

---

## 0 · Verdict in one table

| Question | Answer | Evidence class |
|---|---|---|
| Can we generate a **unique, format-valid** TIF now? | **Yes.** `docs/downloads/h85-candidate.tif`, all 37,654 positives, every pixel finite in [0,1], EPSG:32611, 3730×3292. | local validator, decoded-pixel uniqueness |
| Is it OK to **submit** it? | **No.** Its HOLDOUT-DTI is below the random control. | HOLDOUT-DTI |
| Does the lane gate pass? | **Surface: PASS. Dots: literal DUPLICATE/STOP** (near-3 px 0.998 vs a universal-coverage lattice probe, `data/scored/13gems_…r13-lattice…`). Random dots score 0.999 against that probe, so the literal test is uninformative for it. Excluding probes the maximum is 0.27, but the literal rule is not waived. | shared `gates.lane_uniqueness_report` + probe control |
| Did H83 (the file shipped earlier as "SUBMIT: YES") get holdout-validated? | **It had not.** Measured here: the same field under its own clumped top-k placement scores **0.017201**, far below random. | HOLDOUT-DTI |
| Can we beat 0.2778? | **Not demonstrated.** No candidate in this repository beats the random control on the local holdout except the learned View-B arms of H82/H84 (see §3), and no file here has an organiser receipt. | — |

---

## 1 · Why did h33-2-b2 (0.2778) score highest? (PhD-level reading, with the limits stated)

### 1.1 What is verified about the file

Source: `data/reference/h33-2-b2-zeros.tif` (restored from the owner's mirror `buffedlizard55-lab/GEMSDOE32`, path
`docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif`, sha-pinned in `registry/data_manifest.json`).

* 37,654 binary cells, EPSG:32611, values {0,1}, no NaN (measured this session).
* Nearest-neighbour spacing: **median 3.0 px**, minimum 2.83 px (measured). The cells form a thinned lattice, not blobs.
* Its nearest mapped catalogue trace is **≥ 223.6 m**, and 2,171 of its cells lie within 300 m of the catalogue (measured).
* It is a strict subset of `data/scored/gems24-h25-1-dotted-h19-5-d2-8-…-nan.tif` (0.2600 owner-reported, 44,090 cells).
  The **6,436 cells removed all lie 100–200 m from a mapped trace** (min 100 m, median 100 m, max 200 m; measured).
  This is the "200 m catalogue ring" that the champion's own docstring describes (`scripts/run_h83_structural_concordance.py`).

### 1.2 The metric arithmetic that explains the ranking

From the official page (DrivenData, *Problem description*, "Performance metric"; fetched 2026-10-10):

    TPw = Σ_g max_{x: d≤R} p(x) k(d),   FPw = Σ_{x:p>0} p(x)[1 − max_g k(d(x,g))],   FNw = |G| − TPw
    DTI = TPw / (TPw + 0.2·FPw + 0.8·FNw),   k(d) = max(1 − d/300 m, 0)

Because FNw = |G| − TPw, the denominator is 0.2·(TPw+FPw) + 0.8·|G|. With binary p and one-to-one cover, TPw+FPw ≈ S
(the emitted mass). That gives the approximation the repo uses, **DTI ≈ T / (0.2·S + 0.8·|G|)**, where T is credited
mass and S is emitted mass. `src/gems52/metric.py` states the exact form; the approximation is only used as a
readable identity.

Two owner-reported numbers, 0.2778 (S = 37,654) and 0.2600 (S = 44,090), determine two unknowns (T, |G|) exactly:

    |G| = 14,088.7   (range 13,953–14,226 under four-decimal rounding of both scores; measured here)
    T   = 5,223.1    (range 5,194–5,253)

**Identifying assumption (the weak point):** the 6,436 deleted cells earned **zero** credit in T. Two scores with two
unknowns always solve, so the fit is not a test. The only independent support is that |G| = 14,088.7 agrees with the
value `knowledge/10` reached by a different route (as the repo already reports). Treat the mechanism as the most
plausible single explanation, not as a verified fact.

### 1.3 Why the champion is high, in plain terms

1. **Precision per emitted cell.** The score is credited mass per unit emitted mass. Removing cells whose expected credit
   is below the marginal threshold raises DTI. The metric's own marginal rule (`metric.py` docstring, part ii) gives
   **expected credit ≥ 0.2·DTI/(1−0.2·DTI) ≈ 0.0588 per fully-false-positive cell** at DTI 0.2778. Cells 100–200 m
   from a known trace are mostly false positives unless the truth set contains faults right next to the catalogue. The
   organiser defines the scored set as faults *not contained within the current public USGS database* (official page).
2. **Spacing against max-cover.** Credit uses the **maximum** cover within 300 m, so dots packed together re-earn the
   same truth. The champion's 3-px spacing (median) is the metric-aware placement the repo's `nodes.spacing_select`
   implements. §3 measures the size of this effect.
3. **What it does not show.** It does not show that the new (expert-labelled) faults lie far from the catalogue.
   That would raise T for the ring cells and reverse the gain. The organiser's text says new-fault truth "can lie within
   300 m of a known trace" (quoted in `knowledge/03`, secondary source). We have not seen that statement on the
   official page this session.

### 1.4 What it would take to beat 0.2778 / 0.3195 under the same identity (targets, not projections)

| target | condition under DTI ≈ T/(0.2S+0.8G), G = 14,088.7 | value |
|---|---|---|
| beat 0.2778 at S = 37,654 | T > 0.2778 × 18,801.7 | T > 5,223 (+0%) |
| beat 0.3195 at S = 37,654 | T ≥ 0.3195 × 18,801.7 | **T ≥ 6,007 (+15%)** |
| beat 0.3195 at T = 5,223 | S ≤ (5,223/0.3195 − 0.8G)/0.2 | **S ≤ 25,384 (−33% emitted)** |

These are arithmetic targets from two owner-reported numbers. They are not forecasts (`AGENTS.md`: a projection is never
written as a score).

---

## 2 · What H85 measured (HOLDOUT-DTI)

Instrument: the repo's shared hide-and-recover folds (`run_h61.setup()`, label-blind quadrants, 80 m buffer), evaluator
`gems52-pooled-hide-v1` (α 0.2, β 0.8, 300 m triangular kernel), 53,186 withheld positive pixels, 9,400 dots per fold,
`nodes.spacing_select` (3 px), 1,000 paired cluster-bootstrap draws, seed 61052.

| arm | HOLDOUT-DTI | 95% CI | note |
|---|---:|---|---|
| **H85 geo-concordance field, spaced** (the H83 field, catalogue-free) | **0.072384** | [0.059310, 0.086983] | candidate |
| concordance only (no geothermal term) | 0.074146 | [0.062373, 0.086021] | paired vs H85: −0.001762 [−0.011811, +0.007279] |
| magnetic linearity only (surrogate) | 0.067452 | [0.055427, 0.079927] | non-learned |
| DEM linearity only (surrogate) | 0.068375 | [0.055649, 0.081135] | non-learned |
| gravity linearity only (surrogate) | 0.054823 | [0.045596, 0.064830] | non-learned |
| geothermal wells only | 0.045126 | [0.031207, 0.059676] | single non-geophysical channel |
| H83 **clumped top-k, no spacing** (the shipped placement) | **0.017201** | [0.011695, 0.023879] | placement ablation |
| **random** (same allowed set, same K) | **0.080426** | [0.070223, 0.090973] | control |

* Controls: the random arm reproduces the H82 committed receipt **0.080426** to 3.5×10⁻⁷ (tolerance 1e−3). The
  instrument is therefore reproduced in this clone.
* Paired, H85 minus random: **−0.008042, 95% CI [−0.019670, +0.004875]**. The CI crosses zero, and the point estimate is
  below the control. Verdict: **negative**, not promotable.
* Leakage canary (single channel, AUC on held-out truth vs allowed negatives; bar 0.90): max **0.6228** (DEM-only); H85 field
  0.5505. **No alarm.** The H85 field reads no label; the catalogue exclusion in the original H83 code was neutralised for
  the holdout because it would read held-out truth.
* Placement effect (same field, same instrument): spacing 0.072384 vs clumped top-k 0.017201. Spacing is the largest
  single effect measured this session. The shipped H83 file used the clumped placement (99.2% of its cells have a
  1-px neighbour; measured).
* Comparison bar: the repo's other holdout receipts on the same instrument are H82 `B_DVA2` 0.189200 and main's H84
  primary `B_DVA2_HVA` 0.190147 [0.1689, 0.2112] (`README.md` H84 block). H85 is far below both.

**Note on what this does and does not say.** The holdout hides *catalogue* faults. The competition scores *new* faults
the catalogue lacks. The repo already records that holdout DTI and the public board are not correlated
(Spearman −0.10, `AGENTS.md`). So this negative result means "the unsupervised structural field carries no measurable
catalogue-fault signal here", not "the file would score zero on the board".

---

## 3 · Candidate file (download yes, submit no)

* File: `docs/downloads/h85-candidate.tif` (copy of `submission/gems52-h85-geoconc-spaced-37654px-20261010.tif`), ZIP `docs/downloads/h85-candidate.zip`.
* SHA-256: `a4a6662009ad2118da8c1b638befb18dff62082757b6c6d89bb207336c17b32a` (the same hash in the first and refreshed runs).
* Submission name: `h85-geoconc-spaced-cat200-37654px-20261010` (≤140 chars note: `H85 geo-concordance, catalogue-free; 3px spaced; 200m ring out; binary; holdout below random`).
* Container: organiser-template profile (LZW, stripped, pinned grid) with **outside-footprint 0.0 and no nodata tag**, so
  every pixel is finite and in [0,1]. Added as `write_geotiff_portal_exact(..., outside="zero")` in `src/gems52/grid.py`
  (default unchanged: the H77 NaN-outside container still applies to every other caller).
* Uniqueness (decoded pixels; the candidate's own download copies excluded; IR-H85-001): **137 local priors checked**
  (`submission/`, `docs/downloads/`, `data/scored/`); canonical pattern unique = True; novel fraction 0.5545; maximum Jaccard
  of positive support against any prior **0.0766**. Scope: local rasters only, not the 567-blob census (not restorable here).
* Lane (shared gate, final dots): surface **PASS** (max Spearman 0.1525 < 0.90); dots **literal DUPLICATE/STOP** (near-3 px 0.9984
  vs `data/scored/13gems_…r13-lattice…`, which random dots also hit at 0.9991, so it is a probe); excluding probes the maximum is 0.2698 (bar 0.70).
* Organiser decision that is still open: whether the portal accepts 0.0 outside the footprint. The public page says
  "data outside the bounds is null or nan"; we have not seen a receipt for either container (IR-H85-004).

---

## 4 · Hypotheses (3–5), ranked, with what is already tested

Ranked by (prior plausibility for an *off-catalogue* fault) × (data is already here) ÷ (cost). **No expected-DTI number is
given**: no candidate has a validated estimate, and a projection is not a score.

| rank | id | layer(s) (GeoTIFF band, `training_features.tif` tag) | physical signature | why it could find a catalogue-missed fault | why it is not already in the repo | free source | status |
|---|---|---|---|---|---|---|---|
| 1 | **H85-next-A · 2-m soil temperature anomaly** | none in the training stack; **INGENIOUS GDR 1391 "2m Temperature Probes"** (DOI 10.15121/1881483, CC BY 4.0) | positive shallow-thermal anomaly, linear along a trend, above a regional baseline | a fault that carries hot fluids can leak heat to the upper 2 m even where no trace is mapped | the repo cites this dataset only as context (`knowledge/12`, R3-H1: "no new GDR resource bytes were used"); its bytes are not used anywhere | GDR 1391 (verified on page) | **untested; NOT obtainable from this sandbox** (gdr.openei.org not on the egress allowlist). Needs a user download or an allowlist change. Mimics: solar aspect, soil moisture, vegetation, roads, buildings. |
| 2 | **H85-next-B · cover-thickness basement step** | band 15 `depth_to_base_surf` (cover thickness) | an oriented, sustained step in basement depth across a line | a buried normal-fault offset shows as a cover step with no surface trace | partially tested only: H60-3 (`knowledge/25`, synthetic check; "cannot be cited as a step detector"). Band 15 is used as a covariate in many rounds; no standalone step-detector holdout receipt was found in this review | in stack | untested as a holdout arm. Mimics: basin margins, facies changes, paleo-channels. Cheap. |
| 3 | **H85-next-C · seismicity lineation** | bands 10 `deq_n100a15`, 16 `ieq_n100a15` | directional gradient of earthquake density, lineated | faults that are seismically active but not mapped | the bands sit in View A co-training (`knowledge/63` says H61 already included them as raw channels). The *standalone* directional test (H74S-B) has no run receipt in this review | in stack | untested standalone. Mimics: aftershock clusters, induced seismicity, mining. The 100 km kernel is coarse for 100 m cells. |
| 4 | **H85-next-D · geodetic strain discontinuity** | bands 4 `geod_2ndinv`, 7 `geod_shearrate`, 8 `geod_dilaterate` | sharp, linear discontinuity in strain | a locked fault shows a strain step | the bands were isolated in H72; the discontinuity test (H74S-D) is not run | in stack | untested. Mimics: broad loading, interpolation seams. Expected to be weak at 100 m. |
| 5 | **H85-audit · INGENIOUS v2 vs labels** | none (audit only) | not a detector | measures whether `labels.tif` omits traces in the INGENIOUS "Quaternary Faults v2" file | the labels are documented as coming from USGS **and INGENIOUS** (`page/967`), so the gap may be small | GDR 1391 "Quaternary Faults v2" (page-verified) | not runnable here (same access limit). An audit, not a submission path. |

**Already tested and closed (do not re-propose without a new mechanism):** co-training pseudo-label exchange (N-1,
`knowledge/03`); whole-footprint top-k (N-2); the geo-concordance field (H85, negative); the variogram/anisotropy family
(H82, H84-main, best measured 0.192829 as an attribution arm); the radiometric fusion family (`GEMSDOE46` on the board,
not in this repo's holdout).

---

## 5 · Irregularities (flagged for review)

Full entries in `registry/irregularities.json` (IR-H85-001…). Summary:

* **IR-H85-001** — Uniqueness self-match: the shipped H83 audit compared the candidate with its own output copy; the first
  H85 refresh did the same with `docs/downloads/h85-candidate.tif`. Fixed in `scripts/run_h85.py`; the self-copy is now excluded.
* **IR-H85-002** — H83's own evidence file is internally inconsistent: `near_catalogue_200m: 0` and `distance_analysis.within_200m_catalogue: 61`. The 61 comes from `distance_transform_edt(~cat & valid)`, whose zeros include the footprint edge, so it is a measurement bug, not a finding. Corrected Euclidean counts for the shipped H83 file: **0 within 200 m, 1,365 within 300 m** (run card said 1,167, a cross-structure undercount).
* **IR-H85-003** — H83 "SUBMIT: YES / verdict promote" (run card, README) contradicts its own run card (`holdout_dti: NOT_EVALUATED`) and its receipt (`approved_for_weekly_slot: false`). The H83 file is download-only; the holdout is now measured (§2).
* **IR-H85-004** — Output container conflict in the repo: `gates.format_report` rejects NaN outside the footprint, while the public page says "null or nan" outside bounds, and the organiser's own `sample_submission.tif` is NaN-outside. H85 uses zero-outside to be safe against a naive [0,1] test. Organiser behaviour is unknown.
* **IR-H85-005** — Band 6 tag mismatch: `training_features.tif` band 6 is tagged `tc` ("tilt angle or total curvature, magnetic"), but its bytes have Spearman **1.0000** with the GeoDAWN total-count (TC) band (`data/external/geodawn_rad_u8.tif` band 4, USGS DOI 10.5066/P93LGLVQ). The repo already treats band 6 as radiometric (`src/gems52/external.py`); the metadata is wrong. This answers the brief's "any radiometric bands present": **yes, by bytes, one band (6)**.
* **IR-H85-006** — Official sample file vs its description: `sample_submission.tif` has 60,988 cells equal to 1, and they are **identical** to the catalogue (`labels == 1`). The competition page says it "predicts total fault absence". Organiser clarification needed.
* **IR-H85-007** — The wells source: the CSV has **27,092 rows**, but only **8,693** carry a positive temperature or quartz value (measured). H83's "weighted by temperature across 27,092 wells" overstates the weighting.
* **IR-H85-008** — Leaderboard numbers in the brief conflict. The brief says "0.3195 is the highest score right now" and also "0.3774". The official board (fetched 2026-10-10) shows **#1 0.3774 (xiaofanhu)**, **#8 0.3195 (DARD)**, **#22 0.2778 (extradr19)**. The board prints team names, not filenames, so no filename-to-score mapping is organiser-confirmed.
* **IR-H85-009** — The lane's literal dots rule fires against a universal-coverage probe (`13gems…r13-lattice…`, 206,895 positives): random dots score 0.999. The literal rule is therefore uninformative for that raster. Reported, not waived.
* **IR-H85-010** — The Blum & Mitchell co-training lane (the brief's method paragraph) is closed by the repo's own pre-registered gates (View A sufficiency, `knowledge/03`, H82/H84 notes). H85 is not a co-training round. The brief's "Stay inside [the lane]" and "think outside the box" pull in opposite directions; the owner should decide which governs the next round.

---

## 6 · Limits, needs, and the next session

* **Needs access:** GDR 1391 bytes (the 2-m temperature survey, the INGENIOUS v2 fault file). The sandbox egress allowlist is `github.com`, `codeload.github.com`, `api.github.com`, `registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org`. GDR and USGS are not reachable (the restore script says so, `scripts/restore_data.py`). Either a user-side download into `data/external/` with SHA pins, or an owner-approved allowlist entry for `gdr.openei.org`.
* **Organiser-confirmed numbers:** none. The only score receipts are owner-reported board values.
* **Next session, in order:** (1) get GDR 1391 "2m Temperature Probes" in place and pin it; (2) pre-register H85-next-A and H85-next-B *before* any fit; (3) run each on the same instrument with the random control reproduced; (4) only a candidate that beats the repo's promotable holdout bar (H84-main primary 0.190147) may be considered for a slot, and the slot decision stays with the owner.

---

## 7 · Sources (official or primary, verified this session)

* DrivenData competition, problem description and metric: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
* DrivenData leaderboard (public DW-Tversky, team-level): https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/
* INGENIOUS GDR 1391 (DOI 10.15121/1881483, CC BY 4.0): https://gdr.openei.org/submissions/1391 · project site: https://gbcge.org/current-projects/ingenious/
* GeoDAWN USGS release (DOI 10.5066/P93LGLVQ), as cited by the competition page: https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and
* Coordinate system: https://epsg.io/32611
* Tversky index (background only): https://en.wikipedia.org/wiki/Tversky_index
* Blum & Mitchell, COLT 1998: https://doi.org/10.1145/279943.279962
* Repo primary records: `registry/data_manifest.json`, `src/gems52/metric.py`, `src/gems52/evaluate_holdout.py`, `src/gems52/grid.py`, `src/gems52/gates.py`, `evidence/h85_holdout.json`, `evidence/h85_run_card.json`, `evidence/h85_gates_raw.json`, `evidence/h82_holdout.json` (H82 receipts), and main's `evidence/h84_run_card.json` (other session).
