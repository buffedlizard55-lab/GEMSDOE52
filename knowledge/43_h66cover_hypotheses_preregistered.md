# 43 · H66 — five ranked hypotheses for the co-training lane, one pre-registered validation

**Status: PRE-REGISTERED before any H66 model is fitted.** The SHA-256 of this file is recorded in
`registry/h66_preregistration.json`; `scripts/run_h66.py` refuses to run if the hash moves. Nothing
below was written after seeing an H66 number. Frozen against: the current user brief
(`knowledge/36_current_user_brief_2026-10-09.md`, carried verbatim in `README.md` §"Complete current
prompt"), `knowledge/31_h61_results_and_limits.md`, `knowledge/38_h63_results_and_limits.md`,
`knowledge/40_h64_results_and_limits.md`, `knowledge/42_h65_results_and_limits.md`.

Lane (unchanged, from the brief): **co-training between a geophysical view and a surface view, with
disagreement as the discovery signal** (Blum & Mitchell, COLT '98, pp. 92–100,
doi:10.1145/279943.279962). View A = potential-field and subsurface (gravity, magnetics, strain,
seismicity). View B = surface (DEM-derived curvature and slope, plus the radiometric bands in
`training_features.tif`). The brief's mandated protocol is executed in full this round:

1. **Independence test (empirical).** Correlate each view's spatial-block out-of-fold errors on
   labeled negatives; abandon the exchange if they are strongly correlated
   (`|rho| >= 0.60`, H61 threshold, restated in §5).
2. **Pseudo-label only where one view is confident and the other abstains**, using whole-segment
   spatial blocks and a buffer so no leakage reaches the evaluation (H61's `stage_exchange`,
   reused unchanged: `spatial.whole_pseudo_segments`, forbidden = evaluation region ∪ hidden
   components ∪ ≤4 px of the fold's visible catalogue).
3. **Disagreement is the discovery signal.** A-only = potential-field confident, surface abstains =
   possibly buried beneath cover. B-only = surface confident, potential-field abstains = suspect
   surface artifacts (roads, erosion lines).
4. **Geological reasoning for every A-only candidate** (reasoning CSV, one row per emitted cell).
5. **Compare against a single-view baseline** on hide-and-recover segments (pooled HOLDOUT-DTI,
   `gems52-pooled-hide-v1`, α 0.2, β 0.8, 300 m triangular kernel).
6. **Normalize to [0,1], write the GeoTIFF, apply the metric-aware placement, run the uniqueness
   gate, and confirm the output is not merely the union of the two views.**

---

## 1 · What six prior rounds measured (the starting facts, all labelled)

| round | change vs H61 | View A out-of-quadrant AUC (PREMISE-AUC, not DTI) | holdout verdict |
|---|---|---|---|
| H61 | raw-value View A, HGB 250 it | mean 0.5163 (min fold below 0.52) | NEGATIVE: disagreement_post 0.0306 vs single_B 0.1745 (HOLDOUT-DTI, 53,186 withheld px) |
| H63 | View A = step-normalised columns, no raw bands | 0.536 vs View B 0.686 | NEGATIVE: disagreement_post 0.0403 vs single_B 0.1742 |
| H64 | View A capacity cut (HGB 120 it, 7 leaves) | 0.5230 (min fold 0.4681); S1 gate FAIL | NEGATIVE: disagreement 0.0312 vs single_B 0.1745 |
| H65 | View A = cross-strike detrended offsets of bands 15/13 | 0.5202 (min fold 0.4706); premise FAIL | not run (gate failed before the holdout arm) |
| H60D | disagreement contrast arm (concurrent) | — | NEGATIVE (research-only artifact) |
| H56 | first co-training disagreement emission | — | negative lineage |

* H61's **independence screen passed**: max |Spearman ρ| of the two views' 50×50 px block errors on
  held-out catalogue-zero negatives = **0.1331** (< 0.60), 2,089 blocks, 4,095,103 negative
  predictions (`evidence/h61_independence.json`). The compatibility premise holds; the **sufficiency**
  premise (View A transfers out of quadrant) is what fails, at ~0.52 every time.
* H61's **leakage canary was clean**: max single-feature raw AUC 0.6687 (a View-B slope gradient),
  max fitted top-5 held-out AUC 0.6666, alarm threshold 0.90 (`evidence/h61_canary.json`).
* The best comparable holdout arm remains **single_B = 0.1745** [0.1523, 0.1963] (HOLDOUT-DTI,
  evaluator `gems52-pooled-hide-v1`, 53,186 withheld positives, 95% paired cluster bootstrap,
  1,000 draws). No co-training arm has beaten it in any round.
* The simulator's validity caveat is carried verbatim: R4 measured Spearman **−0.10** between this
  hide-and-recover instrument and the owner-reported board; it screens procedures, it does not
  promote.

### 1.1 Why 0.2778 scored what it scored (measured, carried from `knowledge/27`)

`ref_h33_2_b2` (reported 0.2778, OWNER-REPORTED, not ORGANIZER-CONFIRMED) is a strict subset of the
reported-0.2600 file: it added zero pixels and deleted 6,436 pixels, all 100–200 m from a mapped
trace. Because `DTI = T / (0.2·(T+S−M) + 0.8·(|G|−T))`, deleting zero-credit pixels raises the ratio
by +6.8 % without detecting anything new. **The champion is a precision edit, not a better
detector.** `|G|` (the hidden expert-drawn truth mass) is identified only as the interval
[5,949.3, 12,512.1] px (H61 shared-instrument repair R2; the point value 14,088.7 is superseded).
Live board 2026-10-09 (PUBLIC BOARD, not ORGANIZER-CONFIRMED): top **0.3774** (xiaofanhu), 0.3195
is rank 7 (DARD), 0.2778 is rank 13 (extradr19).

---

## 2 · Five candidate hypotheses (ranked by expected DTI gain / implementation cost)

None of these has been implemented in this repository. H61/H63/H64/H65 all shipped the **plain
rank-difference field** `rankA − rankB` over the whole allowed domain; H66's candidates change what
is emitted inside the disagreement stratum, which is the part of the brief no prior round touched.

### Rank 1 — H66-A · cover-gated A-only emission (VALIDATED THIS ROUND, §4)

* **Layers involved:** the post-exchange View A and View B operating-rank surfaces (H61 learners,
  unchanged), plus `raw_band_15` (depth to basement = sedimentary cover thickness) as the cover
  prior.
* **Physical signature targeted:** the brief's own mechanism — where the potential-field view is
  confident and the surface view abstains, the fault may be **buried beneath cover**. A buried
  basin-bounding fault keeps a deep density/magnetic fabric step and thick cover above it while
  producing no DEM scarp and no radiometric lineament.
* **Why it should catch a fault the USGS/INGENIOUS catalogue misses:** the catalogue is compiled
  from surface expression; a fault whose trace is entirely under basin fill cannot appear in it,
  but its cover thickness and deep potential-field step remain measurable. H61/H63/H64 emitted the
  global A−B tail, which mixes thick-cover A-only segments with thin-cover ones; gating and
  weighting by cover concentrates the budget on the geologically plausible stratum.
* **How it differs from anything already implemented:** every prior round placed
  `rankA − rankB` (H61/H64) or step-view differences (H63) over the whole allowed domain. H66-A
  places `(rankA − rankB) × cover_norm` **restricted to the A-only stratum** (rankA ≥ 0.95 and
  rankB ∈ [0.35, 0.65], the H61 donor/receiver thresholds), so every emitted cell is an A-only
  candidate by construction and the reasoning CSV covers every emitted cell.
* **Expected DTI gain:** low. View A's transfer is weak (0.52 in every variant tried), so the
  A-only stratum is mostly anti-signal in the holdout (H61: disagreement_post 0.0306 < random
  0.0804). The gate cannot create signal; it can only stop spending budget on thin-cover A-only
  pixels. **Expected to remain below single_B; validated, not assumed.**
* **Cost:** low — no new features, no refit; one extra holdout arm and one build.

### Rank 2 — H66-B · two-round pseudo-label exchange (deferred)

* **Layers:** unchanged views; the exchange iterated once more (Blum–Mitchell allow iteration;
  H61 ran exactly one round).
* **Signature / rationale:** a second confident-to-abstaining round could compound the first.
* **Why deferred:** H61 measured post ≈ pre (0.0333 → 0.0306 HOLDOUT-DTI): the exchange adds
  nothing because View A's pseudo-labels are noise. Expected gain very low; cost medium (refit).
* **Not run** (budget).

### Rank 3 — H66-C · strain–seismicity View A (deferred)

* **Layers:** bands 4 (geodetic second invariant), 7 (shear rate), 8 (dilatation rate), 10
  (distance to earthquake), 16 (earthquake density) and their gradients — the "strain, seismicity"
  half of the brief's View A definition, as a dedicated view.
* **Signature / rationale:** active faults concentrate interseismic strain and microseismicity; a
  buried, recently active segment could be seismically visible while geomorphically silent.
* **Why it should catch catalogue-missing faults:** the catalogue is surface-mapped; seismicity is
  not.
* **Why deferred:** these channels were already inside H61's raw View A (36 channels), and none
  entered any fold's canary top-5 (best raw View-A single feature: `raw_band_07` 0.5816, fold 0);
  a dedicated view is unlikely to beat a pooled learner that already had them. Expected gain
  low-moderate; cost high (new fit + new premise gate). **Not run** (budget). The free official
  source that would strengthen it — USGS ComCat (`earthquake.usgs.gov/fdsnws/event/1`) — is NOT
  bulk-ingestible from this sandbox (H64 §1.3); the in-file bands 10/16 remain the only seismicity
  channels.
* **Not run** (budget).

### Rank 4 — H66-D · long-wavelength deep-edge View A (deferred)

* **Layers:** bands 13 (isostatic gravity anomaly), 15 (depth to basement), 2 (RTP), 14 (TMI),
  low-pass at σ = 8–15 px (800 m–1.5 km), gradient magnitude + multi-scale edge coherence.
* **Signature / rationale:** a regional-scale edge detector matched to the wavelength of
  basin-bounding fault contrasts, suppressing the short-wavelength survey noise that dominates the
  raw bands.
* **Why deferred:** the template already carries σ = 8 gravity/cover gradients inside H61's View A;
  H63's σ = 3 step columns (0.536) and H65's cross-strike offsets (0.5202) both failed the
  premise. Expected gain low; cost medium (new shared-store columns + new premise gate).
* **Not run** (budget).

### Rank 5 — H66-E · B-only emission (control; named non-fault process; not run)

* **Layers:** View B confident & View A abstaining stratum.
* **Signature / rationale:** the brief's reading of B-only is "suspect surface artifacts such as
  roads or erosion lines" — a scarp-like DEM/radiometric lineament with no deep potential-field
  support.
* **Expected value:** negative as a fault detector (it is the complement of the A-only stratum and
  the holdout shows disagreement mass scores below random); recorded as the **named non-fault
  process** for this lane: *anthropogenic or erosional linear features (roads, tracks, gullies,
  fan margins) and lithologic contacts produce surface lineaments with no deep structure*.
* **Not run** (budget; it is the control reading, not a candidate).

---

## 3 · What H66-A changes, mechanically (the single pre-registered change)

Shared and **not forked** (reused byte-for-byte from the template): `gems52.structural` feature
store + `gems52.external` extension, `gems52.spatial.folds` (label-blind-quadrants-v2, buffer
80 px), `gems52.evaluate_holdout` (`gems52-pooled-hide-v1`), `gems52.metric`, `gems52.nodes
.spacing_select`, `gems52.submission_writer`, `gems52.gates`, and `run_h61`'s `stage_canary`,
`stage_fit`, `stage_exchange` (same views, same learner, same seed → H61's fits are reproduced,
not re-tuned).

Round-specific: (a) one **extra holdout arm** `h66a_cover_gated_a_only` alongside the six
preregistered H61 arms, and (b) the **build field** of §4. Nothing else changes.

### §4 Frozen definition of the H66-A field (holdout arm and shipped raster use the same rule)

Over the allowed emission domain (`eligible & sample-footprint & ~catalogue & catalogue-distance >
200 m`, then the exact-novelty mask of `knowledge/39c` — no emitted cell is a positive pixel of an
informative registry raster):

```
rankA, rankB   = percentile ranks of the post-exchange OOF mosaic views over the allowed domain
cover_norm     = (log1p(max(raw_band_15, 0)) - min) / (max - min)   over the allowed domain
A_confident    = rankA >= 0.95                    (H61 donor_rank_min)
B_abstain      = 0.35 <= rankB <= 0.65            (H61 receiver_rank_interval)
field66        = (rankA - rankB) * cover_norm  where A_confident & B_abstain & allowed
               = -1                          elsewhere
placement      = nodes.spacing_select(field66, allowed, K, min_px=3.0)   (metric-aware)
```

Per holdout fold the same rule is applied inside the fold's own allowed domain (region & ~visible &
visible-distance > 2 px ring), K = 9,400 dots per fold per arm, identical to the other arms.

**Why this is not the union of the two views:** the field is zero outside the A-only stratum; the
union field `max(rankA, rankB)` is positive wherever *either* view is high. The not-union check
compares the placed emission against freshly placed `single_A`, `single_B` and `union_max`
emissions at the same budget and reports cell differences, shared dots, Jaccard and the
field-vs-union Spearman.

---

## 5 · Thresholds (restated from H61; unchanged)

| key | value |
|---|---|
| canary_auc_alarm | 0.90 |
| independence_abandon_max_abs_rho | 0.60 |
| donor_rank_min | 0.95 |
| receiver_rank_interval | [0.35, 0.65] |
| buffer_px (folds) | 80 |
| block_side_px (independence) | 50 |
| min_pseudo_pixels | 5 |
| pseudo_cap_per_fold | 2,000 |
| budget_dots_per_fold_per_arm | 9,400 |
| min_dot_separation_px | 3.0 |
| catalogue_exclusion_m | 200.0 |
| bootstrap_draws | 1,000 |
| lane_near_dot_fraction | 0.70 |
| lane_near_dot_radius_px | 3.0 |
| lane_rank_correlation | 0.90 |
| universal_coverage_probe_threshold | 0.95 |

## 6 · Verdict rule (frozen)

`promote` (eligible for the separate selector step; still no slot spent here) **only if all of**:
format gate PASS · lane gate PASS (policy; literal reported alongside) · decoded-pattern unique vs
the registry (tier 1 exact + tier 2 novelty 1.0) · not-the-union PASS · **and** the H66-A arm beats
`single_B` on the pooled holdout with the paired 95% CI of (h66a − single_B) entirely above 0.
Otherwise `negative` / research-only. The champion-projection table (both ends of the measured
`|G|` interval) is reported as a PROJECTION, never a score. ORGANIZER-CONFIRMED: none — no
submission-page receipt exists for any file in this repository.

## 7 · Budget

Max 3 experiments. **E1** leakage canary + fit + independence screen (the brief's mandated test).
**E2** one pseudo-label exchange + hide-and-recover holdout, seven arms (six H61 arms + H66-A),
pooled HOLDOUT-DTI + paired 95% CI. **E3** build + gates + unique GeoTIFF + run card. Stop after
E3 or at 2 hours, whichever first.

## 8 · Labels policy

Every number is labelled HOLDOUT-DTI (evaluator version, withheld-positive count, 95% CI),
PREMISE-AUC / SYNTHETIC / PROJECTION (never scores), OWNER-REPORTED, or ORGANIZER-CONFIRMED (only
copied from a submission-page receipt — none exists). A projection is never written as a score.
