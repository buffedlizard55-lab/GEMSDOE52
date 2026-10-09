# H71 — hypotheses and protocol, preregistered 2026-10-09 **before** any H71 fit, score or artefact

Frozen file. Its SHA-256 is recorded in `registry/h71_preregistration.json` before the first model
is fitted, and `scripts/run_h71.py` refuses to run if the hash has moved. Nothing below was written
after seeing an H71 result. Lane: the brief's two-view co-training paragraph (View A
potential-field/subsurface, View B surface, disagreement as the discovery signal).

Scope of this round: it answers the open item "a unique, lane-valid candidate" left by H61/H64/H65
(`knowledge/42` §"What is still open") inside the lane. It is a submission round: one new GeoTIFF is
built, gated and published for research, with an explicit download/submit verdict. No competition
upload is made by this lane; promotion to a weekly slot is the separate selector step.

---

## 0 · Why this, and what it must not repeat

Measured lane history (all HOLDOUT-DTI unless noted; evaluator `gems52-pooled-hide-v1`, 53,186
withheld positives, α 0.2, β 0.8, 300 m triangular kernel, paired 95% cluster bootstrap):

* H61 (`knowledge/31`): independence **holds** (max |ρ| 0.1331 on 2,089 blocks of held-out
  catalogue-zero proxies, abandon bar 0.60), but View A sufficiency **fails** — out-of-quadrant AUC
  mean 0.5163 (min fold 0.4668) while View B reaches 0.6843. Holdout: single_B **0.174517**
  [0.152316, 0.196299], disagreement_post 0.030584 [0.020940, 0.042238]. The shipped H61 file is a
  measured lane duplicate (policy max near-dot 0.8788; 9 informative priors above 0.70).
* H64 (`knowledge/40`): lower-capacity View A still fails sufficiency (mean 0.5230, min 0.4681);
  the emission is again lane-DUPLICATE (largest near-dot share 0.888), and the per-raster capped
  re-placement could not fill its budget (31,487 of 37,600 at the template budget; 18,388 of 20,000
  at the smallest tried budget).
* H65 (`knowledge/42`): a physically parameterised View A (cross-strike detrended basement/gravity
  offsets) also fails the premise (mean 0.5202, min 0.4706). No emission.

Two measured facts drive this round's design:

1. **The lane's discovery signal has never been emitted directly.** H61/H64 emitted the continuous
   rank difference A−B, in which a strict A-only pixel (A ≥ 0.95, B mid-rank) scores only ≈ 0.45 —
   below most concordant pixels. The brief says the discovery signal is the *condition* "A confident,
   B not", i.e. the A-only stratum. H71 emits that stratum itself.
2. **The lane gate failed on dense informative priors, not on our field.** H61's lane analysis
   (knowledge/31 §4): of 545 registry rasters, 31 have 3 px coverage at or above the rule's own 0.70
   trigger; the 9 informative offenders have coverage 0.7583–0.8976, so *any* footprint-wide
   emission lands ≈ coverage-fraction of its dots inside one offender's halo. Capped re-placement
   (H64) could not fill the budget. H71 instead places only in the **lane-quiet domain**: cells at
   least 3 px from every informative prior's positive pixel, so the directed near-dot fraction is 0
   for every informative prior *by construction*, and measures how large a budget that domain fills.

Already tried, and therefore not repeated: the A−B rank-difference field (H61, H64), capped
re-placement under the 70% rule (H64), premise re-tests of three different View A parameterisations
(H61 raw, H64 capacity-cut, H65 physical offsets). H71 changes the *emission field* and the
*placement domain*, not the views, the folds, the learner or the evaluator.

---

## 1 · Hypotheses (ranked by expected DTI improvement and implementation cost)

### H71-A — the A-only discovery stratum, emitted directly — RANK 1, **tested in this round**

* **Layers.** The shared store's View A (36 channels: gravity, magnetics incl. upward-continued TMI,
  strain, seismicity, basement depth, conductivity) and View B (37 channels: DEM curvature/slope,
  band 6 radiometric total count, external K/Th/U ratios), exactly as H61 — no feature is added,
  dropped or re-weighted.
* **Mechanism.** Blum & Mitchell (COLT '98, doi:10.1145/279943.279962): two learners trained on
  separate views teach each other on unlabeled data where one is confident and the other abstains.
  The brief turns the disagreement into a discovery signal: *where A is confident and B is not, the
  fault may be buried beneath cover*. H71 emits exactly those candidates: the strict A-only stratum
  **rankA ≥ 0.95 (donor_rank_min) AND rankB ∈ [0.35, 0.65] (receiver_rank_interval)** — the same
  registered thresholds H61 used for pseudo-labels — ranked by View A's own out-of-fold conviction.
  The candidate field is finite only on that stratum, so every placed dot is an A-only discovery
  candidate and gets a written geological reasoning row (Phase 2 reviewers verify faults).
* **Physical signature targeted.** A fault buried beneath basin cover: a potential-field fabric step
  (gravity/magnetic gradient, basement-depth offset, upward-continued TMI edge) with **no** DEM scarp
  and **no** radiometric lineament — invisible to the surface view, hence B's abstention.
* **Why it could catch a catalogue-missing fault.** A covered fault has no surface expression, so the
  USGS/INGENIOUS catalogue does not contain it; its potential-field signature can survive where the
  DEM cannot see it. That is precisely the A-confident/B-abstaining case.
* **Named non-fault process that could mimic it (required).** A **basin-margin or flexural hinge
  line**: basement deepens sharply across a stratigraphic hinge with no displacement; also
  **density or lithologic contacts** in the basement (a gravity/magnetic step without throw),
  **buried palaeo-channels or alluvial-fan margins**, and **interpolation seams** in the modelled
  depth-to-basement grid (band 15 is a *modelled* surface per repo notes, not an independent
  measurement — unresolved, see knowledge/34 §H62-A). These are the rows' named mimics.
* **Difference from everything already in the repo.** H61/H64 emitted rankA − rankB over the whole
  domain; H55–H60D emitted surface/edge/union fields; H62/H63 emitted corroboration fields. No prior
  round emitted the stratified A-only discovery field, and none placed in the lane-quiet domain.
* **Cost.** Zero new features: one mosaic, two rank transforms, one stratum mask, one placement.
  No new data.

### H71-B — quiet-zone placement makes the lane gate satisfiable at a real budget — RANK 2, **tested in this round**

* **Rule.** An emitted cell is *lane-quiet* iff it is at least 3 px (the lane's own near-dot radius)
  from every positive pixel of every **informative** registry raster (universal-coverage probes,
  measured 3 px coverage ≥ 0.95, are classified as in `gems52.gates.lane_report` and excluded, as
  the authoritative shared repair requires). The directed near-dot fraction of the emission against
  every informative prior is then 0 by construction, and the policy lane verdict is PASS without
  retuning the 0.70 threshold.
* **What is measured.** The quiet domain's size, the largest budget it fills at 3 px separation, and
  the candidate's HOLDOUT-DTI at that matched budget. H64 measured the *failure* of the alternative
  (capped re-placement: 31,487/37,600); H71 measures the quiet domain directly.
* **Risk, stated before running.** If the quiet domain is too small for a meaningful budget, the
  emission is small; a small emission is a weaker discovery claim but a *lane-valid* one, and the
  verdict rule below handles it.

### H71-C — the exchange still cannot rescue View A (control, expected negative) — RANK 3, **measured, not tuned**

* Three premise measurements (0.5163, 0.5230, 0.5202) say View A is at chance out of quadrant, so
  A→B pseudo-labels are noise and disagreement_post ≤ disagreement_pre. H71 re-measures the premise
  and the independence screen on this machine's rebuilt stack and reports them as controls; it does
  **not** re-tune View A a fourth time (that would repeat H64/H65).

### H71-D — B-only candidates are not emitted — RANK 4, **deferred, named reason**

* Where B is confident and A abstains, the brief says suspect surface artifacts (roads, erosion
  lines). Emitting them would spend the false-positive tax (α = 0.2) on the likeliest artifacts.
  H71 reports the B-only stratum count only. A road/hydrography veto layer would be needed to use
  this stratum; neither USGS TNM nor NHD hosts is reachable from this sandbox's egress allowlist, so
  the idea is **not viable this round** (same block as H62-C).

---

## 2 · Frozen decision rules (checked by code)

1. **Shared tools, not forks.** `run_h61.setup` (pins, store, label-blind-quadrants-v2 folds, buffer
   80 px), `run_h61.sample_train`, `run_h61.learner`, `run_h61.stage_fit`, `run_h61.stage_exchange`
   (independence screen + exactly one whole-segment exchange with buffer, no leakage into any
   evaluation region), `gems52.evaluate_holdout` (`gems52-pooled-hide-v1`), `gems52.nodes.
   spacing_select` (metric-aware placement, 3 px), `gems52.submission_writer`, `gems52.gates`
   (incl. the authoritative probe-classification lane), `scripts/audit_uniqueness.py` with the
   census receipt. The only round-specific code is the candidate field definition, the arm list,
   the quiet-domain placement and the build — all in `scripts/run_h71.py`.
2. **Controls.** The H61 six arms are re-run at the H61 budget (9,400 dots/fold) and must reproduce
   the committed H61 pooled values within |Δ| ≤ 0.001 (knowledge/39b tolerance); single_B
   0.174517 is the best comparable control. A control outside tolerance stops the round as a
   pipeline defect.
3. **Leakage canary.** Every feature, every fold, held-out sample; alarm at direction-insensitive
   AUC > 0.90. Any alarm drops the feature and is recorded.
4. **Independence.** Spatial-block (50×50 px) out-of-fold errors of the two views on labelled
   negatives (held-out catalogue-zero proxies, > 4 px from any catalogue pixel). Abandon the
   exchange if max |ρ| ≥ 0.60; the screen is measured before any transfer, as H61 did.
5. **Holdout (the decision).** Matched budget per fold per arm. Candidate arm `a_only` = the strict
   A-only stratum field (finite only on the stratum), placed by `spacing_select` at 9,400 dots/fold
   or its fill, whichever is smaller; the matched set (a_only, single_A, single_B, union_max,
   random) is then re-placed at K_c = the candidate's minimum per-fold fill so the comparison is
   eligible. Pooled HOLDOUT-DTI (α 0.2, β 0.8, 300 m triangular kernel) with paired 95% cluster
   bootstrap. **Holdout-eligible** iff the candidate's paired difference vs single_B has a 95% CI
   lower bound > 0 at the matched budget. The 9,400-dot six-arm set is reported alongside as the
   H61 control reproduction.
6. **Build.** OOF mosaic of the post-exchange predictions (out-of-fold only, as H64). Percentile
   ranks over the allowed domain (eligible ∩ sample-finite ∩ off-catalogue ∩ > 200 m from the
   visible catalogue — the 200 m ring is built from the full catalogue at build time, exactly as
   H64, because the organiser's truth is off-catalogue). Stratum = rankA ≥ 0.95 ∩ rankB ∈ [0.35,
   0.65]. Candidate field = rankA on the stratum, −inf elsewhere. Quiet domain = allowed ∩ at least
   3 px from every informative prior's positive pixel. Budget = the largest K ≤ 23,000 that
   `spacing_select` fills inside (stratum ∩ quiet). **Surface lane check before placement**
   (rank correlation of the min-max-normalised surface vs every registry raster, both literal and
   policy verdicts). **Dots lane check after placement** (directed ≤ 3 px near-dot fraction vs every
   registry raster, literal and policy). Uniqueness: tier 1 decoded-pattern uniqueness vs all
   priors; tier 2 support novelty vs informative priors; `scripts/audit_uniqueness.py` with the
   census receipt as the authoritative audit. **Not-the-union**: cell differences and Jaccard vs
   the `max(A,B)` emission at the same budget, plus Spearman of the candidate field vs the union
   field.
7. **Validator.** `submission_writer.write_submission` re-opens the written file and requires:
   one float32 band, finite everywhere, values in [0,1], EPSG:32611, shape 3,730 × 3,292 and the
   pinned transform, no mass outside the footprint. Local validation only — never an organiser
   receipt.
8. **Verdict.** `promote` only if format + policy lane + uniqueness (both tiers) + not-the-union
   + holdout-eligible all pass. Otherwise `negative`, published research-only with the download
   label. **This lane spends no weekly slot.** The literal lane statistic is always reported
   verbatim beside the policy verdict (the registry contains a measured universal-coverage lattice
   probe, so the literal rule fails for every nonempty raster — a property of the registry, measured
   in `evidence/ctd5_registry_saturation.json` and `evidence/h61_lane_analysis.json`).
9. **Budget.** Three experiments: **E1** canary + premise + independence (diagnostics on the rebuilt
   stack); **E2** exchange + matched-budget holdout (the comparison); **E3** build + gates + GeoTIFF
   + site publication. Stop after E3 or two hours, whichever first. Negative results are deliverables.

## 3 · Sources (for manual review; checked in earlier rounds of this repo, re-verified by pin this round)

* Blum & Mitchell (1998), *Combining labeled and unlabeled data with co-training*, COLT '98,
  pp. 92–100, DOI 10.1145/279943.279962: https://dl.acm.org/doi/10.1145/279943.279962
* Competition metric/format/rules: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
  and /page/968/; leaderboard: https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/
* Masking clarification (staff, thread 11516): https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4
* USGS GeoDAWN airborne magnetic/radiometric release, DOI 10.5066/P93LGLVQ:
  https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and
* GDR OpenEI submission 1391: https://gdr.openei.org/submissions/1391
* Reference solution: https://github.com/drivendataorg/gems-prize-reference-solution
* Competition rules PDF: https://docs.nlr.gov/docs/fy26osti/96647.pdf
* Prior inputs are SHA-256-pinned owner mirrors (`registry/data_manifest.json`,
  `data/restore_receipt.json` — all pins verified this session); **not** organiser-authenticated.

## 4 · AI-use disclosure

An AI assistant wrote the code, this protocol and the review text. No geologist verified any
structure, no field observation was collected, and no organiser score, acceptance or leaderboard
gain is claimed for any H71 output.
