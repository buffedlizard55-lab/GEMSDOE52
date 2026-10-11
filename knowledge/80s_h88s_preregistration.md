# 80 · H88 — co-training lane: sufficiency-screened exchange, disagreement-stratified emission, metered budget (preregistered)

Round identifier: **H88**. Lane: the brief's two-view co-training paragraph
(Blum & Mitchell, *Combining labeled and unlabeled data with co-training*, COLT '98 pp. 92–100,
DOI [10.1145/279943.279962](https://doi.org/10.1145/279943.279962)) — View A potential-field /
subsurface, View B surface, **disagreement as the discovery signal**.

Frozen **before any H88 fit**. Pinned by `registry/h88_preregistration.json`; the runner
`scripts/run_h88_cotrain_lane.py` refuses to start if the hash of this file has moved. Nothing below is
edited after the freeze; results go to `knowledge/82_h88_results_and_limits.md`.

## 0 · What is already settled in this repository, and what H88 therefore does *not* repeat

The repo has measured the co-training lane repeatedly (`knowledge/03` N-1; H61, H63, H65, H69, H70, H74,
H82, H84). Settled facts carried in, each with its own receipt:

| fact | receipt |
|---|---|
| View A sufficiency has failed **eight** times on the mandated instrument (H61 0.5163, H63 0.5362, H69 0.5281, H65 0.5202, H70 0.5166, H74 0.5194, H82 0.5113, H84 0.5163) | `AGENTS.md` §H83; `evidence/h82_fit.json`, `evidence/h84_holdout.json` |
| Conditional independence **passes**: max \|ρ\| 0.1526 (H83) / 0.0765 (H61) — so the brief's *abandonment* condition never fired | `evidence/h83_holdout.json`, `knowledge/72` §6 |
| Pseudo-labels used as a **label source** were the worst arm ever measured here (0.0084 tip / 0.0078 hide vs random 0.0253 / 0.0396) | `knowledge/03` N-1 |
| Disagreement strata adopted as **stratify-and-suppress**, not as a label donor | `src/gems52/views54.py` docstring, `knowledge/03` N-1 |
| Current promotable holdout bar: `B_DVA2` **0.192829** [0.170790, 0.213691]; `single_B` 0.174571; `single_A` 0.071954; random 0.080426 | `evidence/h84_holdout.json` |
| Holdout DTI does **not** rank board scores (Spearman −0.1045, n = 13) | `knowledge/06` IR-52-017 |
| Board-family mass lever: Spearman(mass, score) = −0.928 over the restored scored rasters | `knowledge/76` §4 |
| The ≤ 200 m ring around the mapped catalogue earns **zero** credit; deleting it raised 0.2600 → 0.2778 | `knowledge/01` §5 item 2 (refuted half struck through); `knowledge/06` IR-52-018 |

So H88 does **not** rebuild View A a ninth time and does not re-open the pseudo-label-as-label arm. What
is genuinely untested in this repo, and is what H88 measures:

1. the mandated exchange run **under a sufficiency screen** — the exchange is executed and its effect
   measured instead of assumed, and the screen's decision is recorded per fold;
2. the disagreement strata used as a **suppressor on a strong surface view** (`corroborated_B`:
   View B confident, minus the B-only stratum the brief calls a surface artefact) measured against
   `single_B` and against the stratum arms;
3. the **metered budget** (mass discipline) on the instrument — DTI as a function of the emitted dot
   budget, never measured in this repository before;
4. the **geological reasoning record for every A-only candidate**, exported as a review table.

## 1 · Candidate hypotheses (5), ranked; each names layers, signature, off-catalogue reason, novelty, cost

Ranking is by (plausibility that the emitted dots land within 2 px of an *uncatalogued* fault pixel) ×
(data in place) ÷ (cost). **No expected-DTI number is given anywhere**: no candidate here has a validated
estimate, and a projection is never written as a score. Bands are 1-based positions in
`training_features.tif` with the file's own tag (verified inventory: `docs/data/band_inventory.json`,
19 float32 bands).

| rank | id | layer(s) | physical signature targeted | why it could catch a catalogue-missing fault | how it differs from what is already implemented | cost | status |
|---|---|---|---|---|---|---|---|
| **1** | **H88-P `corroborated_B`** | View B: band 12 `det_elev`, 19 `det_elev_slope`, 6 `tc` (radiometric total count, per IR-H85-005), external `geodawn_rad_u8` K/Th/U/TC + Th/K, U/K, U/Th, external `lidar_scarp_features_u8` (ex_max, step_max, lapneg_max, lappos_max, downface_max, upface_max, coh100, relief); View A: bands 1,2,3,4,5,7,8,9,10,11,13,15,17,18 | multi-scale curvature/relief wavelength contrast + scarp-face asymmetry + radiometric K/Th, **with the B-only stratum suppressed by A** | the surface expression of a fault that the catalogue missed (truncated trace, cover edge, unmapped splay) is still a linear relief/curvature feature; suppression removes the B-only stratum the brief calls road/erosion/levee | H61/H82/H84 used View B without the disagreement suppressor; H87 used a hand-weighted mixture with no holdout; no round has placed a View-B field through the strata and then metered the budget | medium (channels + 8 fits) | **tested in this round** |
| 2 | H88-X `exchange_B` | same channels as #1, plus A-only pseudo-positives | co-training exchange itself (donor = A, receiver = B) | if A can donate anything, B's held-out recall rises | the exchange was run in H61/H63 but *never under a per-fold sufficiency screen*, and its donor was assumed sufficient | medium (+1 fit/fold) | **tested in this round** |
| 3 | H88-A `a_only` | View A channels only | A-confident ∧ B-abstains = "buried fault beneath cover", the brief's discovery signal | a concealed normal fault under basin fill has a potential-field step and no scarp | this *is* the brief's signal, run here with spacing + collar + per-candidate geology, and compared to `single_A` and random | low (already computed) | **tested in this round** |
| 4 | H88-K `budget_curve` | none new — the metered budget applied to arms #1–#3 | the metric's marginal-credit rule: at DTI ≈ 0.28 a pixel pays for itself only inside ≈ 282 m of a hidden fault, so mass beyond the ranking's reach is pure tax | the board family shows spearman(mass, score) = −0.93; the same credit in fewer dots dominates | no previous round swept K on the instrument; every round inherited K = 9,400/fold (37,600 total) from H82 | low (re-use of the same fields) | **tested in this round** |
| 5 | H88-L `lidar_only_B` | external `lidar_scarp_features_u8` alone (12 bands) | 1 m-LiDAR scarp-face/relief channels resampled to 100 m | the catalogue's mapped traces were drawn from coarser mapping; LiDAR sees scarps the map does not carry | LiDAR is used in this repo only as a *component* (H55/H60/H85 mention it); no standalone holdout receipt exists | low (channels already read for #1) | **reported as a diagnostic arm only** |

**Named non-fault mimics for every hypothesis above** (the brief's "named non-fault process" field):
roads, canals/levees, quarry faces, railroad grades, fence lines, playa shorelines and erosion lines for
the surface channels; lithological contacts, intrusive margins, basement steps and paleo-channels for the
potential-field channels; interpolation seams for the gridded interpolation of point datasets; solar
aspect and soil moisture for the radiometric ratios.

## 2 · Pre-registered gates (frozen before any fit)

| # | gate | threshold |
|---|---|---|
| 1 | leakage canary — every single channel's OOF AUC on held-out truth | alarm if max AUC > 0.90 |
| 2 | independence — \|ρ\| of the two views' **block-level out-of-fold errors on labelled negatives** | abandon the exchange if max \|ρ\| > 0.60 |
| 3 | sufficiency screen — per-view OOF AUC of the *score* against held-out truth | exchange allowed only if the donor view's per-fold AUC ≥ 0.60; the decision is recorded per fold, and the exchange arm is still run and reported |
| 4 | primary vs `single_B` (paired, 95 % spatial-cluster CI) | promotion candidate only if the paired CI lower bound > 0 |
| 5 | random control reproduction | `random` must land inside 0.0702–0.0910 (H84's CI), else the run is void |
| 6 | format validator on the shipped file | single band, float32, shape/CRS/transform equal to `sample_submission.tif`, all-finite, values in [0, 1], zeros outside the domain, zero on catalogue, zero inside the 200 m ring |
| 7 | decoded uniqueness | no byte-identical or value-identical prior; ≥ 20 % novel support vs the binary-prior union, or ≥ 0.5 vs the continuous-proposal union |
| 8 | lane (parallel-run protocol) | surface max \|Spearman\| ≤ 0.90 and final dots ≤ 70 % within 3 px of any one registry raster (universal-coverage probes reported, not waived) |
| 9 | not-the-union | the shipped dots must not equal View A's dots, View B's dots, their set union, or the union-max field's dots |

## 3 · Budget

Three experiments (fit + independence; holdout arms with the budget curve; build + gates), two hours of
wall clock. **No competition slot is used by this round.** Promotion is a separate selector step.

## 4 · Sources used to write this preregistration

* Blum & Mitchell, COLT '98: https://doi.org/10.1145/279943.279962
* Competition problem description and metric: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
* GeoDAWN airborne magnetics/radiometrics: https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and (DOI 10.5066/P93LGLVQ)
* INGENIOUS / GDR 1391 catalogue and well-spring data: https://gdr.openei.org/submissions/1391
* CRS: https://epsg.io/32611
* Repo primary records: `registry/data_manifest.json` (23 SHA-256 pins), `src/gems52/metric.py`,
  `src/gems52/evaluate_holdout.py`, `src/gems52/spatial.py`, `src/gems52/views54.py`,
  `evidence/h84_holdout.json`, `knowledge/01`, `knowledge/03`, `knowledge/06`, `knowledge/76`.
