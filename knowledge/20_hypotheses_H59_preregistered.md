# H59 hypothesis slate and frozen protocol — 2026-10-08

**Status at registration:** five geological hypotheses reviewed; all five are runnable from the
integrity-pinned staged inputs (`work/h59_pinned`, 23 files, SHA-256/byte-verified against
`registry/data_manifest.json`). This document and `registry/h59_preregistration.json` are committed
**before** any H59 model fit, holdout score, or TIFF is produced. At registration there is no H59
implementation, holdout result, score claim, or TIFF. All expected effects are qualitative; no
numerical DTI forecast is made. No new external data is required by any candidate; nothing in this
slate depends on an unobtainable source.

## 0. What this round is

H59 is the brief's two-view co-training round executed end-to-end on the pinned mirror, with
**disagreement as the discovery signal** and every previously-measured negative result kept in
force:

* View A = potential-field and subsurface (magnetics, gravity, **geodetic strain**, **seismicity**,
  depth-to-basement, conductivity). H57's View A carried only band 4 and band 16 of the
  strain/seismicity families; H59 adds bands 7, 8 and 10, completing the brief's definition. Those
  bands appeared as rank features in the earlier R2/structural pipelines (`src/gems52/features.py`,
  `src/gems52_h1`, `src/gems57/feat.py`) but were never in either co-training view.
* View B = surface (DEM-derived detrended elevation and slope, the radiometric total-count band
  measured into `training_features.tif` band 6 — IR-52-019, `evidence/h53_band6_identity.json` —
  plus the external GeoDAWN K/Th/U ratio grids and LiDAR scarp layers).
* The pseudo-label exchange is **diagnostic only**: knowledge/03 N-1 and H57 §3 both measured it as
  noise (−0.0159/−0.0303 and +0.0027 AUC). It is run because the brief asks for it, and its result
  can never alter the shipped field.
* The A-only stratum is measured honestly even though H57 found it the worst of eight arms against
  the catalogue proxy: the private truth is expert faults **not in the public map**, so the local
  proxy cannot certify or refute the buried-fault bet. Every A-only candidate in the shipped
  emission carries a written geological reasoning row with an explicit falsifier (Phase-2 duty).
* Nothing in the emission may sit inside the ≤ 200 m ring of a mapped trace (knowledge/01 §5:
  the ring's credit is exactly zero and it pays pure tax), on an invalid pixel, or outside the
  sample-submission domain. Emitted values are exactly `{0, 1}` — binary is metric-optimal and
  NaN-free, so the historical "Predicted values must be in range [0, 1]" portal rejection cannot
  recur.

## 1. Verified task and data boundary (unchanged from H58, re-verified on this staging)

The official problem defines a 300 m triangular kernel, `alpha=0.2`, `beta=0.8`, one float32
GeoTIFF on EPSG:32611 at 100 m, 3,292 × 3,730, values in [0, 1]
([problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)).
The staged inputs are integrity-pinned owner mirrors, **not organizer-authenticated**
(IR-52-003, IR-H58-001). The tracked `data/*.tif` rasters differ from the staged mirror and are
never read by H59. The staged sample raster supplies geometry and its finite domain only; its cell
values are never used. Staged labels (`labels==1`) give 60,988 catalogue pixels on the 5,167,373-px
footprint. Every file H59 reads is hash-recorded in the run receipt.

## 2. The five ranked geological hypotheses

"Expected DTI" is a qualitative rank against implementation cost, not a prediction. Catalogue-zero
is not verified absence. Every candidate names its layers, its physical signature, why it should
find a fault **missing from** the USGS/INGENIOUS catalogue rather than one already in it, and how
it differs from what this repository has already implemented.

| Rank | Hypothesis, layers, signature | Why catalogue-missing | Difference from prior work | Expected DTI / cost |
|---|---|---|---|---|
| **1 — H59-1 surface-artifact veto on the union field** | Layers: the two out-of-fold view probability fields `p_A` (16 potential-field/subsurface bands) and `p_B` (12 surface bands). Signature: linear surface lineaments that View B rates ≥ 0.60 while View A abstains (≤ 0.40) — the road / levee / erosion-line / agricultural-edge family. The candidate **emission field stays `max(p_A, p_B)`**; the veto only removes that stratum from the emission pool. | A young active fault almost always leaves *some* potential-field or basement-depth discontinuity; a road or a gully does not. Removing uncorroborated surface lineaments deletes false-positive tax (the 0.2778 incumbent lost more score to tax, 6,757 units, than it earned in credit, 3,870 — knowledge/01 §2), while catalogue-missing faults that both views can see keep their union rank. | `build_h57_submission.py` carried a `--veto-b-only` flag that its own help text records as "off by default — never measured". No round has measured the veto. | **Medium** (tax is the largest known loss term); **low cost** (fields already computed). |
| **2 — H59-2 agreement-weighted product rank** | Layers: `p_A`, `p_B`. Signature: rank by `p_A · p_B`, so a pixel must be warm in **both** an independent potential-field view and an independent surface view to rank high — the Blum–Mitchell high-precision agreement set, contingent on the measured independence premise. | The catalogue misses two opposite families: buried faults (no surface trace) and non-magnetic faults in sedimentary cover (no potential-field contrast). The pixels where *both* views are nonetheless warm are the highest-precision off-catalogue candidates; single-view-hot pixels are where each view's own artifact family lives. | H57's field was `max(p_A, p_B)`; the product has never been measured as a ranking field in this repository. | **Medium, uncertain** (H57 measured the *concordant stratum as a pool* at 0.81× random — a warning, not a measurement of the product ranking); **low cost**. |
| **3 — H59-3 basement-step buttress field** | Layers: band 15 `depth_to_base_surf` (gradient), band 13 `iso_grav_anom` (gradient), band 15 value as the cover qualifier. Signature: lateral **steps** in the modelled basement surface (high `\|∇depth\|`) collocated with isostatic-gravity gradient ridges (high `\|∇gravity\|`), under at-or-above-median cover thickness. Field = rank(∇band15) · rank(∇band13), restricted to cover ≥ footprint median. | A basin-bounding normal fault under alluvial cover has no surface trace for the USGS map to draw, but holds a basement throw and a gravity gradient across it. The over-representation of thick-cover pixels is the point: it targets exactly where the mapper could not see. | Depth-to-basement has only ever entered as a passive classifier feature (val/grad/range in H57's stack). No step-detector ranking field exists in this checkout; the registered H57-D conductivity–depth contrast was never run. | **Medium** (the buried bet, restated geologically instead of via classifier strata); **medium cost** (one field build on the cached layer stack). |
| **4 — H59-4 seismicity-lineament field** | Layers: bands 16 (`ieq_n100a15` earthquake density) and 10 (`deq_n100a15` distance to earthquake) — band 10 has never been in any view. Signature: zones that are both high-density and steep-gradient in the smoothed seismicity field (field = rank(band16 value) · rank(band16 gradient)), i.e. the edges of active microseismic clusters that active fault strands produce. | A blind fault with microseismicity but no surface rupture is seismically active and unmapped at once. | Band 16 was only ever a passive View-A feature; band 10 was never used by the co-training instrument. No prior field ranks by a seismicity transform. | **Low** (the band is smoothed at a ~100 km radius per its own description, so 100 m localization is model-borrowed); **low cost**. |
| **5 — H59-5 multi-scale potential-field residual ratio** | Layers: band 13 (isostatic gravity), band 2 (RTP magnetics). Signature: short-wavelength residual (band minus a fixed broad regional) normalized by the regional magnitude — narrow basement block edges under cover. | A shallow basement fault block shows as short-wavelength gravity texture where the regional field is smooth. | H58-B registered this family and never ran it; no Fourier/multi-scale transform exists in this checkout. The H55-EDGE gravity LoG edge detector (nearest implemented cousin) failed its promotion gate (+0.000546, 2/4 folds). | **Low-medium**; **medium cost** (2–4 CPU-hours). **Registered as queued; not run in H59** unless a cheaper slot opens, because its nearest cousin already failed a gate. |

All five validate on the staged inputs; none needs external data. Had any required a new source, the
free official source would have been the USGS GeoDAWN release
(DOI [10.5066/P93LGLVQ](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and))
or the INGENIOUS GDR submission
([1391](https://gdr.openei.org/submissions/1391), CC BY 4.0) — both already staged and pinned here.

## 3. Frozen H59 protocol (registered before implementation/results)

### Inputs and reproducibility

1. Data root `work/h59_pinned`, verified file-by-file against `registry/data_manifest.json`
   (SHA-256 + byte count) before anything else; the runner fails closed on any mismatch and records
   every input hash in the receipt. Never read tracked `data/*.tif`. State that a matching
   owner-mirror pin is not organizer authentication.
2. Views from the H57 layer machinery (value / Gaussian-gradient magnitude / 5×5 range, each
   min-max rank-encoded to uint8 over the all-band-valid footprint):
   * **View A (48 features):** bands 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18 of
     `training_features.tif`.
   * **View B (36 features):** bands 6, 12, 19 of `training_features.tif`; GeoDAWN `TC` (rad band 4)
     and `Th/K`, `U/K`, `U/Th` (extensions bands 1–3); LiDAR scarp bands 1, 3, 7, 9, 10.
3. Learner: L2 logistic (`C=1.0`, balanced, lbfgs), positives = catalogue pixels inside the fold's
   fit mask, negatives = 60,000 fit-mask pixels ≥ 500 m (Euclidean) from every training-visible
   catalogue pixel (`h58.training_pixels`, which never consults hidden geometry).

### Two fold instruments, each with one job

4. **OOF instrument (whole-component quadrant folds, 4 px buffer, H57 configuration).** Four
   contiguous quadrants; whole 8-connected catalogue components assigned by majority quadrant; a
   4 px collar around each held quadrant and the footprint edge excluded from fitting. Fit both
   views outside the held quadrant, keep predictions inside it; the four kept regions tile the
   footprint, so every pixel carries a genuine out-of-fold `p_A`, `p_B`. These fields feed the
   strata, the independence blocks, the pseudo-label segments, and the **artifact** (full coverage
   is why this instrument exists; the 80 px collar of the evaluation instrument would leave ~22% of
   the footprint unscored).
5. **Evaluation instruments (H58 `make_folds`, hide and block, 80 px collar).** Whole components,
   prevalence-matched truth at 0.2% of each fold's scored region, seed `20261008`; block mode
   quarantines whole crossing components and excludes an 80 px Euclidean collar around the scored
   region and the footprint edge. For every evaluation fold, **refit both views on that fold's fit
   mask** — an arm is never scored on an in-sample probability. Budgets: primary 37,654,
   secondary 15,000; block-mode budgets scaled by the fold's legal-share of the footprint. Emitter
   for every arm: `h57.iso_select`, isotropic 3 px minimum separation, NMS 5 (the placement every
   scored file in this family used; the anisotropic variant is refuted, H57-A).

### The brief's co-training protocol, in order

6. **Independence test (fail-closed).** On the OOF fields, per 50×50 block, on labelled negatives
   ≥ 500 m from every catalogue pixel, ≥ 300 negatives per block: correlate the two views'
   out-of-fold mean-squared error and false-positive-rate (≥ 0.60) errors, Pearson and Spearman.
   Abandon co-training (skip the exchange, restrict the shipped field to single views) if any
   \|r\| ≥ 0.60, or fewer than 20 usable blocks, or any undefined statistic. Also report the
   pixel-level OOF logit correlation. Weak correlation is not proof of conditional independence.
7. **Disagreement strata.** `A-only` = p_A ≥ 0.60 and p_B ≤ 0.40 (buried-structure stratum);
   `B-only` = p_B ≥ 0.60 and p_A ≤ 0.40 (surface-artifact suspicion stratum); `concordant`,
   `neither`. Report counts and median depth-to-basement per stratum — H57 measured A-only at
   410.9 m vs 161.2 m for B-only, the brief's geological claim.
8. **Pseudo-label exchange (diagnostic, both directions).** Only if the independence gate passes.
   In the OOF instrument's fold-0 unlabelled quadrant: whole 8-connected segments, ≥ 5 px, entirely
   inside one 50×50 block, entirely inside the unlabelled region, no catalogue or corridor pixel,
   ≥ 80 px from the evaluation pixels; donor ≥ 0.60 and receiver in [0.40, 0.60] (abstention, never
   confident-negative); cap 2,000 px per direction; pseudo weight 0.25. Run B→A and A→B. AUC
   before/after on the fold's primary-held components vs catalogue-zero proxy negatives ≥ 500 m
   **Euclidean** from every catalogue pixel (the Euclidean disk fixes IR-H58-003's cross-dilation
   flaw). The exchange can never alter the shipped field.
9. **Hide-and-recover single-view comparison (the brief's bias check).** On both evaluation
   instruments, at both budgets, score: `view_A`, `view_B`, `union = max(p_A, p_B)` (the re-measured
   incumbent field — H57's numbers were withdrawn with the old staging), `product` (H59-2),
   `vetoB` (H59-1: union ranked on the pool minus the B-only stratum), `basestep` (H59-3),
   `seismicity` (H59-4), `a_only_stratum` (diagnostic), and a seeded random control rebuilt at each
   budget from the same legal pool. All arms share pool, emitter, budget and seed.
10. **Frozen field decision.** Eligible fields = those beating the random control on ≥ 3/4 folds in
    **both** modes at the primary budget. Shipped field = the eligible field with the highest mean
    hide-DTI at the primary budget; ties broken by block-mode mean, then by simplicity
    (single view < union < product/vetoB < layer fields). If the independence gate abandoned
    co-training, the shipped field is the best single view. If no new candidate beats the union,
    the union ships and the candidates are recorded as refutations. No threshold, weight or
    parameter may be tuned after any holdout result is seen.

### Artifact, gates, and the slot verdict

11. **Artifact.** Pool = valid footprint ∩ sample-submission finite domain ∖ the ≤ 200 m catalogue
    ring. Field = the shipped field on the OOF grids. Emission = `iso_select` at exactly 37,654
    nodes, 3 px separation. Single-band float32, EPSG:32611, exact competition transform, values
    exactly `{0, 1}`, **0 NaN/Inf anywhere** (zeros outside the emission — the "-zeros" convention
    that cannot trigger the portal's [0, 1] rejection). No pixel is copied from any prior raster:
    every emitted cell is computed from the H59 fields on this staging.
12. **Gates, read back from the written bytes.** (a) format gate (bands/dtype/CRS/transform/shape/
    range/all-finite/in-footprint); (b) decoded-pattern uniqueness against **every** accessible
    aligned prior (tracked + staged scored/calibration/reference inventory, scope disclosed);
    (c) *not merely the union of the two views*: the decoded pattern must differ from the same-
    budget iso-emissions of `view_A`, `view_B`, `union`, and from the set-union of the view_A and
    view_B emissions; (d) minimum distance to a mapped catalogue pixel > 200 m; (e) nearest-
    neighbour spacing ≥ 3 px; (f) support-novelty fraction vs the prior-support union and overlap
    with the 0.2778 reference, both reported as numbers with no threshold (independent methods
    converging on the same geology is evidence, not copying — the whole pattern is what uniqueness
    means); (g) a reasoning row for **every** emitted pixel, with written geological reasoning and
    an explicit falsifier for every A-only pixel.
13. **Slot verdict (frozen).** The page states one obvious verdict. **"Gates pass — recommended as
    the next weekly submission"** requires: every gate in (12) passing AND the shipped field
    beating the strongest same-fold single-view baseline by ≥ +0.003 mean DTI on **both**
    instruments at the primary budget with ≥ 3/4 strict fold wins on both AND full-budget emission
    on every primary fold AND the independence gate not having abandoned the method. Anything less
    is **"research only — do not spend a slot"** with the failing numbers printed. Local holdout
    success is never organizer validation; the owner-mirror provenance caveat is printed beside
    either verdict. No upload occurs in this round; slots used: 0.

### What H59 does not claim

* No leaderboard score is forecast; Spearman(reported score, simulated DTI) = −0.1045 (p = 0.734,
  n = 13) in this family — the simulator ranks arms on identical rows, it does not predict boards.
* No emitted pixel is a verified fault; every A-only row is a Phase-2 hypothesis with a falsifier.
* Catalogue-zero pixels are proxies for absence, not verified absence.
* The file-to-score mapping for every prior in this family is owner-reported, not
  organizer-authenticated (IR-52-003).

**Registration chronology:** this slate, the frozen protocol, and
`registry/h59_preregistration.json` are committed before `src/gems52/h59.py`, `scripts/run_h59.py`
or any H59 result exists. No result informed any number above. Preserve all thresholds after
opening results; store outputs in new evidence files; never retrofit this registration.
