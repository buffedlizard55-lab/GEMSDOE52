# H74 — preregistered hypotheses (frozen before any fit)

Round label: **H74**. Lane: the brief's co-training paragraph (Blum & Mitchell, COLT '98 pp. 92–100,
[doi:10.1145/279943.279962](https://doi.org/10.1145/279943.279962)) — View A potential-field /
subsurface, View B surface, **disagreement as the discovery signal**.

Frozen UTC: see `registry/h74_preregistration.json` (`preregistered_utc`). The runner
`scripts/run_h74.py` recomputes this file's SHA-256 at start-up and refuses to run if it has moved.
Nothing in this document was edited after the first fit.

---

## 0 · Why this round exists — the one defect in five consecutive negatives

H61, H63, H64, H65, H66cover, H70 and H71 all ran this lane and all ended negative. Their common
stopping point is the **sufficiency gate S1**: View A's out-of-quadrant AUC against *held-out
catalogue fault pixels* measured 0.5163 / 0.5362 / 0.5230 / 0.5202 / 0.5166 — five readings in a row
at chance, against a 0.60 bar (`evidence/h70_sufficiency.json`, `knowledge/55` §3).

**That gate is measured against a biased target, and the bias runs in exactly the direction that
makes View A look useless.** The USGS/INGENIOUS catalogue is a map of faults *that were mapped*, and
a fault is mapped when it is visible: a scarp, a lineament, a vegetation or tonal break. The label
set is therefore enriched in surface-expressed structures — which is View B's domain by construction
— and depleted in exactly the concealed structures the brief says View A should find ("Where A is
confident and B is not, the fault may be buried beneath cover"). Two independent measurements in this
repository are consistent with that reading and with nothing else:

* `single_B` 0.1746 vs `single_A` 0.0720 on the shared holdout (`knowledge/55` §3) — the surface view
  is 2.4× the potential-field view *at recovering mapped traces*;
* H70-B measured that vetoing the B-only stratum **loses** score (Δ −0.0074, CI excludes 0), i.e.
  "B confident, A abstaining" pixels are real mapped faults, not roads or erosion lines.

So S1 as written cannot distinguish "View A is uninformative" from "View A is informative about a
population the labels under-sample". H74 separates those two readings for the first time, with a
**conditional** sufficiency test, and then tests the only emission design that can profit from a
conditional premise.

This is a lane-internal correction, not a View A repair: no new View A channel is proposed, and the
AGENTS.md instruction "stop proposing View A repairs" is respected.

---

## 1 · Ranked candidate hypotheses

Ranked by expected HOLDOUT-DTI improvement over the standing best comparable control
(`single_B` = 0.174517, evaluator `gems52-pooled-hide-v1`), divided by implementation cost.
Only H74-A and H74-B are executed this round; C, D, E are registered and deferred.

### Rank 1 — H74-A · Conditional-sufficiency co-training: "B-core + A-rescue swap"

* **Layers.** View A: `raw_band_01/02/03/09/14` (magnetics: anomaly, RTP, TMI and its horizontal /
  vertical gradients), `raw_band_05/11/13/18` (isostatic gravity: anomaly, slope, vertical and
  horizontal gradient), `raw_band_04/07/08` (geodetic strain: 2nd invariant, shear rate, dilatation
  rate), `raw_band_10/16` (seismicity: distance, density), `raw_band_15/17` (depth to basement,
  surface conductivity) plus the shared external upward-continued TMI channels. View B:
  `raw_band_12/19` (detrended elevation and slope) and every DEM curvature/structure channel in the
  shared store, plus `raw_band_06` (radiometric **total count** — identity measured, Spearman 1.0000
  against the external GeoDAWN TC grid, IR-52-019) and the external GeoDAWN K/Th/U ratio channels.
  The split is the committed `view_A_with_external` / `view_B_with_external` lists; the runner
  asserts the two sets are disjoint before fitting.
* **Physical signature targeted.** A density/susceptibility/strain discontinuity with **no**
  co-located topographic or radiometric step: a fault that offsets basement and basin fill but whose
  scarp is buried under Quaternary alluvium, so the 100 m DEM sees nothing.
* **Why it should catch a fault the catalogue lacks rather than one it already has.** Mapped traces
  are surface-expressed by selection. A structure that produces a potential-field edge and *no*
  surface step is, by the same selection rule, the kind of structure the mappers could not see. The
  emission is additionally restricted to >200 m from any mapped trace, so a dot cannot be a
  re-statement of a known fault.
* **How it differs from everything already in this repository.** Previous rounds emitted the A-only
  stratum *alone* (H70 pure stratum 0.0174, H71 0.0095) or ranked the soft field `rank_A − rank_B`
  over the whole domain (H61/H63/H64 `disagreement_*` ≈ 0.033). Both throw away View B's measured
  advantage. H74-A instead keeps View B as the backbone and **swaps a measured fraction φ of the
  budget** — the weakest φ of the B-ranked dots — for the strongest View A cells that lie inside
  View B's *blind band* (`rank_B` inside the preregistered abstain interval). φ = 0 is exactly
  `single_B`, so the arm nests the control and the comparison is paired and honest. No previous round
  in this repository, or in any sibling listed in the brief, has run a nested swap of this form.
* **Named non-fault process that could mimic it.** A buried lithologic contact (e.g. a Tertiary
  volcanic unit against basin fill) produces the same gravity/magnetic edge with no surface step, and
  is **not** a fault. A second mimic is a survey artefact: flight-line and tie-line levelling residues
  in the aeromagnetic grid are linear, have no surface expression, and strike with the flight plan.
  Both are named per candidate cluster in the reasoning CSV, with the falsifier (strike vs the
  regional Basin-and-Range N–S to NNE grain, and strike vs the survey flight azimuth).
* **Cost.** Low — reuses the shared store, folds, learner, exchange, evaluator, placer, gates.

### Rank 2 — H74-B · Trace-integrated ("line-support") re-ranking of the co-trained field

* **Layers.** No new layer: a transform of the *operating field* produced by H74-A.
* **Physical signature.** The metric credits a truth **trace**, not a truth pixel:
  `TPw = Σ_g max_x p(x)·k(d(x,g))`. A dot's expected credit is therefore proportional to the expected
  **length of fault trace inside its 300 m disc**, not to the probability that the dot itself is a
  fault pixel. H74-B replaces the point score with `max over 12 orientations of the mean operating
  score along a 600 m chord through the pixel`, which rewards coherent lineaments and demotes
  isolated anomalies.
* **Why it should help on uncatalogued faults.** Regional potential-field blobs (basement highs,
  basin-scale gravity lows) are the dominant failure mode of any top-K of a pixel field (negative
  result N-2 in `knowledge/03`). Line integration is the cheapest available discriminator between a
  10 km blob and a 3 km lineament, and the hidden truth is lineaments.
* **How it differs.** The repo's existing line responses (`B_line_resp`, `structural.coherence`) are
  computed on *raw DEM or raw potential-field bands*, before any learner. H74-B integrates the
  **fitted two-view operating field**, which is a different object and has never been placed or
  scored here.
* **Mimic.** Roads, canals, powerline corridors and field boundaries are the straightest lines in the
  Great Basin and will score highly on any line-integral. The 200 m catalogue ring does not exclude
  them. Mitigation: orientation is reported per candidate and anything within 10° of due E–W or due
  N–S *and* perfectly straight over >3 km is flagged in the reasoning CSV as a suspected cultural
  lineament (the brief's "surface artifacts such as roads or erosion lines" clause).
* **Cost.** Low (one separable convolution per orientation).

### Rank 3 — H74-C · Metric-optimal dot spacing (deferred)

The family ships 3.0 px spacing. For a 1-D truth trace and binary dots, credit per dot is
`s·(1 − s/12)` and total DTI is maximised at `s* = (−a + √(a² + 12ab))/b` with `a = 0.2·L`,
`b = 0.8·|G|`; at the champion's `L ≈ 113,000` px and `|G| = 14,088.7` this gives **s\* ≈ 3.29 px**,
i.e. the shipped 3.0 px is within 10 % of optimal and the available gain is < 5 %. Registered,
**not executed** — the measured headroom does not justify an experiment slot.

### Rank 4 — H74-D · Cover-thickness-conditioned budget allocation (deferred)

Allocate the dot budget across 10 km blocks in proportion to (block mean operating score) ×
(mean depth-to-basement), rather than globally by rank. Rationale: unmapped faults concentrate under
cover, and a global top-K spends its budget where the score is high, which is where mapping is
already dense. H66cover's cover **gate** lifted the A-only arm +45 % relative (0.0315 → 0.0457) on a
very low base; a budget **allocator** is the untested form. Deferred: it interacts with H74-A's swap
and would confound the φ measurement.

### Rank 5 — H74-E · External heat-flow teacher (named, checked, NOT viable this round)

Required source: **USGS Great Basin heat-flow maps and supporting data**, DOI
[10.5066/P9BZPVUC](https://doi.org/10.5066/P9BZPVUC) (free, official, public domain). **Checked and
not obtainable from this sandbox**: bash egress is restricted to `github.com`, `codeload.github.com`,
`api.github.com`, `registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org`; `www.usgs.gov`,
`www.sciencebase.gov` and `gdr.openei.org` are not reachable, and the agent page-fetch tool cannot
stream raster payloads. Registered so the next operator with egress can run it; **not** proposed as
viable here, and no heat-flow proxy is smuggled into H74.

---

## 2 · Frozen protocol

| item | frozen value |
|---|---|
| Folds | `gems52.spatial.folds`, label-blind-quadrants-v2, whole intersecting catalogue segments hidden, `buffer_px = 80` |
| Evaluator | `gems52.evaluate_holdout` v`gems52-pooled-hide-v1`, α 0.2, β 0.8, 300 m triangular kernel, pooled over folds, paired 200 px (20 km) cluster bootstrap, 1,000 draws, seed = `run_h61.SEED` |
| Placement | `gems52.nodes.spacing_select`, 3.0 px minimum separation |
| Holdout budget | 9,400 dots per fold per arm (identical to H61/H63/H64/H70/H71, so the control reproduces) |
| Control reproduction tolerance | `single_B` must reproduce 0.174517 within 0.001 absolute, else the round is void |
| Leakage canary | per-feature held-out AUC; **alarm at > 0.90** |
| Independence / abandonment | max abs correlation of the two views' 50×50 px block OOF errors on labelled negatives; **abandon at ≥ 0.60** |
| Pseudo-labels | `gems52.spatial.whole_pseudo_segments`, donor rank ≥ 0.95, receiver (abstain) interval [0.35, 0.65], min 5 px, cap 2,000 px/fold, exactly one round per direction per fold, forbidden set = evaluation region ∪ hidden components ∪ 4 px catalogue collar |
| Surface-blind band (H74-A) | `rank_B ∈ [0.35, 0.65]` — the same abstain interval the exchange uses, not a new free parameter |
| A-confidence for the swap | `rank_A ≥ 0.95` — the same donor threshold the exchange uses |
| Swap fractions tested | φ ∈ {0.00, 0.10, 0.25, 0.50}; φ = 0.00 **is** `single_B` |
| Line-support (H74-B) | 12 orientations, 600 m chord (7 px total length), mean of the operating rank along the chord, max over orientations |
| Catalogue exclusion | emission > 200 m from any **visible** catalogue trace (label-blind inside folds) |
| Emission budget (shipped file) | 37,654 cells, the champion's measured budget, so the board comparison is at matched mass |
| Lane rule | STOP if Spearman > 0.90 against any registry raster, or > 70 % of dots within 3 px of **one** registry raster's dots; checked on the surface **before** placement and on the final dots |
| Experiment ceiling | **3** experiments, **2** hours |

## 3 · Promotion rule (frozen; a projection is never written as a score)

The shipped GeoTIFF may be recommended for a weekly competition slot **only if all six clauses hold**:

1. format gate PASS (single-band float32, EPSG:32611, pinned shape/transform, 0 NaN, values in [0,1]);
2. decoded-pattern uniqueness PASS against every aligned registry raster, and the emission is **not**
   the literal union of the priors;
3. lane gate PASS on the **final dots** under the saturation-aware policy (and the literal statistic
   reported verbatim either way);
4. not-the-union-of-the-two-views PASS (Jaccard with the `max(A,B)` emission at the same budget < 0.5
   and the swapped cells provably outside the `single_B` emission);
5. **conditional sufficiency S1′ PASS** — View A's out-of-quadrant AUC restricted to held-out truth
   pixels in View B's blind band ≥ 0.60, and at least 0.05 above View A's AUC on the surface-expressed
   truth pixels;
6. **HOLDOUT-DTI: the best swap arm beats `single_B` with a paired 95 % CI whose lower bound is > 0.**

If any clause fails the verdict is `negative, research-only`: the file is still published and
downloadable (format-valid), and the site says **SUBMIT: NO** in one line. **Slots used must remain 0
unless clause 6 passes.**

## 4 · Pre-stated expectation (so the result cannot be re-read after the fact)

Base rates measured in this repository: a fully novel emission forced off the registry's agreed
habitat has credit density ρ ∈ [0.0279, 0.1387] (uniform random … champion), so at S = 37,654 and
|G| ∈ [5,949, 12,512] its board DTI would sit in **[0.08, 0.40]** — an interval so wide that it is not
a prediction, and it is written here only to stop anyone later quoting a point value. The holdout
instrument measured Spearman **−0.10** against the owner-reported board in round R4, so a HOLDOUT-DTI
is a *screen*, not a forecast. **No number produced by this round is ORGANIZER-CONFIRMED.**

Prior probability, stated before the fit, that clause 6 passes: **low** — six rounds of this lane have
failed it. The reason to run H74-A anyway is that it is the first arm that *nests* the control, so a
failure is informative (it bounds how much of View B's budget is wasted) and a success is directly
usable.
