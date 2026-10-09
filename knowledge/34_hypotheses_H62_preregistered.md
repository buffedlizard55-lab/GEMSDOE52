# 34 · H62 — five ranked hypotheses, and one pre-registered validation before any H62 fit

**Status: PRE-REGISTERED before any H62 model is fitted.** The SHA-256 of this file is recorded in
`registry/h62_preregistration.json`; `scripts/run_h62.py` refuses to run if the hash moves. Nothing
below was written after seeing an H62 number. Frozen against: `knowledge/26_current_user_brief.md`
(the brief this session carries verbatim in substance), `knowledge/27_r5_findings.md`,
`knowledge/31_h61_results_and_limits.md`, `knowledge/33_hypotheses_R5.md`.

Brief rule applied: **do not spend a weekly submission slot on an idea that has not beaten the
current comparable holdout best** (`AGENTS.md`). Every number is labelled HOLDOUT-DTI (evaluator
`gems52-pooled-hide-v1`, withheld-positive count, 95% CI) or OWNER-REPORTED / ORGANIZER-CONFIRMED.
The leaderboard facts used here were re-read from the official DrivenData page on 2026-10-09
(§1.2).

---

## 1 · Starting facts, re-verified this session (not carried over from memory)

### 1.1 Why 0.2778 scored what it scored (measured from restored bytes)

`scripts/h61_forensics.py` was re-run from the restored, SHA-pinned bytes and its output compared
line-by-line with the committed receipt `evidence/h61_forensics.json`: **byte-identical except the
generation timestamp.** Relevant measured facts (`subset_pairs`):

* `ref_h33_2_b2` (the reported-0.2778 file, 37,654 off-catalogue px) is a **strict subset** of
  `scored_d28_unscored` (the reported-0.2600 file, 44,090 px): `x_only = 0`, `y_only = 6,436`.
* The champion therefore added **zero** pixels and deleted 6,436 of its parent's pixels. The
  deleted pixels all lie 100–200 m from a mapped trace; the champion's nearest dot is 223.6 m away.
* Because the metric is `DTI = T / (0.2·(T + S − M) + 0.8·(|G| − T))` (`knowledge/27` §2), pruning
  pixels that earn no credit lowers the denominator's tax and raises the ratio **without finding
  any new fault**. The 0.2778 is a precision gain on the same mass. Caveat, carried: its score is
  OWNER-REPORTED (filename token `e5eb6e7e` matches no hash convention of the file we hold, and
  GEMSDOE32's page says no organiser score exists — `IR-H61-004`).

### 1.2 Leaderboard, from the official source (fetched 2026-10-09)

Source: <https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/>

| rank | participant | best public DW-Tversky | submissions |
|---:|---|---:|---:|
| 1 | xiaofanhu | **0.3774** | 13 |
| 7 | DARD | **0.3195** | 16 |
| 13 | extradr19 | **0.2778** | 12 |

* **0.3195 is rank 7, not the top.** The brief's sentence "0.3195 is the highest score right now"
  is wrong; the board top is 0.3774. Flagged as `IR-H62-001`.
* Between the repo's 2026-10-08 snapshot and this fetch, rank 8 changed from `mzoorob 0.2884` to
  `mzoorob 0.2902`. The board moves; every bar is dated. Flagged as `IR-H62-002`.

### 1.3 Obtainability of the candidate data, checked this session

| source | reachable from this sandbox's shell? | reachable via the research fetch tool? | verdict |
|---|---|---|---|
| GitHub mirrors of the organiser rasters (SHA-pinned) | yes | — | used (`scripts/download_competition_data.sh`, all 23 pins verified (3 core, 7 external, 12 scored priors, 1 reference)) |
| DrivenData data tab | no (login wall) | not used | not used |
| USGS ComCat relocated seismicity (`earthquake.usgs.gov/fdsnws/event/1`) | **no** (host not in the sandbox allow-list) | **yes** — a count query over a 1°×1° box returned `35` (<https://earthquake.usgs.gov/fdsnws/event/1/count?starttime=2000-01-01&endtime=2026-01-01&minlatitude=40.5&maxlatitude=41.5&minlongitude=-118.5&maxlongitude=-117.5>) | **not bulk-ingestible**: a file cannot be written from the fetch tool; the H56-6 relocated-earthquake idea stays blocked until a bulk path exists |

---

## 2 · Five candidate hypotheses (ranked; none validated except §4's)

Ranking key: **expected DTI improvement, then implementation cost.** The expected-improvement column
is an *ordinal prior*, not a forecast; `knowledge/10` §5 and `knowledge/27` §5 document that the
hide-and-recover instrument cannot rank novel fields in this repository, and no candidate here has
a measured DTI.

**H-1 · Trace-correction corridor (`R5-H1`, already preregistered in `knowledge/33`).** *Rank 1 by expected value; not validated in this session.*
* Layers: `labels.tif` mapped traces (as geometry to be corrected, never as labels), LiDAR bands 6/7
  (`downface_max`, `upface_max`), 3 (`step_max`), 1, 9, 11, 12; `features` 2, 3, 9 (`rtp`, `tmi_hg`, `tmi_vg`).
* Signature: a perpendicular offset estimator — the mapped trace is *wrong* where the LiDAR one-sided
  scarp step is strongest at a lateral offset of ±1–3 px.
* Why it could catch a missing fault: the target is the **positional error of mapped traces**, which
  the organiser says exists (new-fault truth "may lie within 300 m of a known trace";
  `knowledge/25`), so it is not a copy of the catalogue.
* Differs from implemented work: no prior emission uses per-trace perpendicular offsets.
* Non-fault mimic: a lithologic contact or a stream-cut bank aligned with the trace.
* Cost: medium (1–2 days). Gate: `knowledge/33` §A-gate, not yet run (`knowledge/27` §8 lists it
  as the change that "would change the answer"). **Not validated this session: no receipt exists.**

**H-2 · Sufficiency-gated co-training (`H62`, validated in this session — §4).** *Rank 2 by expected value; lowest cost of the validatable ideas.*
* Layers: the same two views as H61. View A potential-field/subsurface; View B DEM curvature/slope,
  band 6 (radiometric total count, Spearman 1.0000 vs the external GeoDAWN TC grid), external K, Th, U.
* Mechanism under test: H61 measured View A out-of-quadrant AUC **0.516** against an in-quadrant fit of
  **0.948** (`knowledge/31` §1). That gap is the signature of an over-capacity learner memorising
  regional anomalies, not of a missing signal. A regularised View A that generalises out-of-quadrant
  would make Blum–Mitchell's sufficiency premise hold, and only then is the exchange licensed.
* Why it could catch a fault missing from the catalogue: the exchange can only pseudo-label
  whole segments where A is confident and B abstains, i.e. buried-cover candidates.
* Non-fault mimic: a basement-high or a basin-margin gravity gradient that A learns as "fault-like".
* Differs from implemented work: H61 used the unregularised 36-channel learner; H62 changes only the
  View A capacity (see §4).

**H-3 · Hot-spring alignment at fault intersections (new; not implemented anywhere in this repo).**
* Layers: `data/external/gdr_wellspring_in_footprint.csv` (GDR 1391, CC BY 4.0 per its restored
  provenance; its `dist_known_fault_px` column is label-derived and must not be used).
* Signature: ≥3 springs within 300 m on a common azimuth, and springs at the intersection of two
  trend families (the Basin-and-Range strike fabric measured in `knowledge/10` §7: dominant strike 100–110° array convention). Emit the
  line through the aligned springs, outside 200 m of any mapped trace.
* Why it could catch a missing fault: springs are an independent surface expression of
  fault-controlled permeability; the catalogue does not use them.
* Non-fault mimic: an alluvial-fan or drainage alignment producing aligned seeps.
* Differs: `H58-A` used cold-discharge geothermometers, not alignments; the wellspring file was never
  used geometrically.
* Cost: low–medium. Expected improvement: small (tens of springs in the footprint; count not yet measured).

**H-4 · Blakely–Simpson horizontal-gradient maxima on upward-continued TMI (new variant).**
* Layers: `features` 14 (`tmi`), `external` TMI up-continued 150 m (`ext_geodawn_extensions_u8`).
* Signature: non-maximum-suppressed ridges of the horizontal gradient magnitude (contacts/faults).
* Differs: the repo already killed magnetic transforms at 300 m (tilt, Laplacian, strain, `knowledge/03` N-6,
  AUC ≈ 0.52). This is the **closest prior art**, so the expected improvement is low; kept for completeness.
* Cost: low.

**H-5 · Seismicity lineaments from relocated ComCat events (`H56-6`, re-listed).**
* Blocked: §1.3. Bulk ingestion from this sandbox is not possible. Not ranked above H-3 until a bulk
  path exists; it is not validated.

---

## 3 · Why H-2 was the one validated this session

It is the only candidate that (a) uses the lane this session's brief names, (b) can be tested with the
shared instrument already in the repo without new data (§1.3 blocks H-5, H-1 needs its own gate), and
(c) targets a **measured** failure mode, so the test can fail cheaply on its first gate. The
honest expectation, stated before any run: H-2 is more likely to fail its sufficiency gate again than
to beat `single_B`. A failed gate is a valid result.

---

## 4 · H62 frozen protocol (one experiment; the budget counts it once)

**Change relative to H61, and nothing else.**
* View A learner only: `HistGradientBoostingClassifier(max_iter=120, learning_rate=0.05,
  max_leaf_nodes=7, min_samples_leaf=400, l2_regularization=5.0, early_stopping=False,
  random_state=SEED)` (H61 used `max_iter=250, max_leaf_nodes=15, min_samples_leaf=40, l2=1.0`).
* View B learner, feature sets, folds (`label-blind-quadrants-v2`), sampler, seed (`61052`), budget (9,400 dots/fold at 3 px), evaluator (`gems52-pooled-hide-v1`), canary, lane gate and placement are **identical to H61**.
* The single-view B control must reproduce the H61 `single_B` value **0.174517** exactly. Any mismatch
  is a pipeline defect and stops the run.

**Gate S1 (View A sufficiency, pre-registered).** Out-of-quadrant AUC of View A on each fold's
held-out region, sampled as in the canary (≤20,000 positives, ≤40,000 catalogue-zero negatives).
*Pass* iff the mean over the four folds is **≥ 0.60** and the minimum fold is **≥ 0.55**.

**Gate S2 (independence, unchanged).** H61's block screen, abandon threshold |ρ| = 0.60.

**Exchange rule.** Exchange runs only if S1 and S2 both pass. Otherwise no pseudo-label is created
and the post-arms equal the pre-arms (`pred_post := pred_pre`), which is recorded.

**Holdout.** The six H61 arms, pooled HOLDOUT-DTI, α = 0.2, β = 0.8, 300 m triangular kernel, paired
physical-cluster bootstrap, 1000 draws.

**Verdict rule (frozen).**
1. Format gate, lane gate (`gates.lane_report` with the H61 probe policy) and not-union check must pass.
2. The candidate arm's HOLDOUT-DTI must exceed the **best comparable arm in the same run**
   (`single_B`) with a paired-difference 95% CI lower bound **above zero**.
3. If (1) and (2) hold → "eligible for the selector, not promoted". The hide-and-recover instrument
   is disqualified for board ranking (`knowledge/10` §5), so even a pass is **not** a claim of a
   leaderboard gain. Otherwise → **NEGATIVE, research-only**: DOWNLOAD YES if format-valid and unique,
   SUBMIT NO.

**Budget.** One experiment (H62-A) — the reproduction of H61 is a verification, not an experiment. No
weekly slot is touched. No threshold is changed after a result.

**Pre-registered predictions** (to be checked, not tuned to): S1 fails with probability ≥ 0.5 by
the H61 evidence; if S1 passes, the candidate remains below `single_B` with high probability,
because the disagreement arms were 5.7× below it in H61 (0.174517 / 0.030584).
