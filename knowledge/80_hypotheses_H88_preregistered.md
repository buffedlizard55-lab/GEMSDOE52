# 80 · H88 hypotheses, ranked, and the frozen H88 specification — written before any fit

Written 2026-10-10 in the H88 session (branch `arena/90369109-gemsdoe52`), **before any view was
computed and before any holdout was run**. The frozen machine-readable twin is
`registry/h88_preregistration.json` (hash-pinned by `scripts/run_h88_cotrain_bidir.py`, which
refuses to start if the registration hash moves).

Lane (the session's assigned method paragraph, verbatim from the standing brief): **co-training
between a geophysical view and a surface view, with disagreement as the discovery signal**
(Blum & Mitchell, COLT '98, pp. 92–100, doi:10.1145/279943.279962). Everything below stays inside
that lane. The brief also demands: test view-error independence on labelled negatives and abandon
if strongly correlated; compare against a single-view baseline on hide-and-recover segments;
write geological reasoning for every A-only candidate; confirm the output is not merely the union
of the two views; normalize to [0, 1], metric-aware placement, uniqueness gate.

## 1 · Ranked candidate hypotheses (3–5), each naming layers, signature, why off-catalogue, and novelty

Ranked by (prior plausibility for an **off-catalogue** fault) × (data present in this sandbox) ÷
(cost). "Expected DTI" is ordinal only: no projection is written as a score (standing brief rule 3).

| rank | id | layer(s) (band index, tag read from `training_features.tif` band tags this session) | physical signature | why it could catch a fault the USGS/INGENIOUS catalogue lacks | how it differs from everything in this repo | status |
|---|---|---|---|---|---|---|
| **1** | **H88 · bidirectional co-training disagreement with cover-step View A** | A: 18 `iso_grav_anom_hg`, 3 `tmi_hg`, **15 `depth_to_base_surf` STEP** (gradient magnitude, σ=2 px), **10 `deq_n100a15` LINEATION** (gradient magnitude), **7 `geod_shearrate` STEP** (gradient magnitude), 9 `tmi_vg`, 17 `cond_surf`. B: 19 `det_elev_slope`, 12 `det_elev` ridge curvature + edges, **K/Th ratio** (`geodawn_rad_u8.tif` b1/b2), 6 `tc` (radiometric total count by bytes, IR-52-019) | A sustained step in cover thickness and in shear strain across a line, coincident with a gravity/magnetic edge, while the surface view abstains → **buried fault beneath alluvial cover**; the reverse disagreement (B confident, A abstains) is treated as a **surface-artifact suspect** (roads, erosion lines) and vetoed | a buried normal fault offsets the basement without a scarp: the catalogue (built from surface traces) misses it; the cover step is the only in-stack expression | no prior round used the band-15 **step** as a detector (H60-3 was a synthetic check only, `knowledge/25`); no prior used bands 10/7 gradients standalone (H74S-B/H74S-D were never run, `knowledge/78` §4); H87 used one-directional (A−B) emission on wavelength-contrast + Th/K — this round is **bidirectional** (A>B boost **and** B>A veto) on **different transforms** and ships the **mass-lever budget** | tested this session (views + independence + holdout + build) |
| **2** | **H88-M · mass-lever emission budget** | not a detector: any field | the same credit delivered with less mass (knowledge/76 §3: 0.3195 needs S≈25,384 at the champion's credit) | not fault-specific — it is the metric's own marginal rule | no submission in the 44-repo family shipped S≈25,400; all top scorers shipped 37,654–44,090 | tested this session as the shipped budget (25,400) + holdout budget curve (9,400/6,350/4,700 per fold) |
| 3 | H89-S · 2-m soil-temperature anomaly (GDR 1391) | external: INGENIOUS "2 m Temperature Probes", DOI 10.15121/1881483, CC BY 4.0 | positive shallow-thermal anomaly lineated along a trend | a fault carrying hot fluids leaks heat into the upper 2 m even where no trace is mapped | cited only as context in `knowledge/12`; its bytes are used nowhere | **blocked in this sandbox** (gdr.openei.org not on the egress allowlist); needs owner-side download into `data/external/` with SHA pin |
| 4 | H89-T · theta map (Wijns et al. 2005) | A: band 2 `rtp` | normalised total-horizontal-derivative of tilt: equal-amplitude edge map | edge map of magnetic contacts that does not saturate on strong sources | tilt is already implemented (29 files); theta re-normalises the same information | untested; novelty low (ranked below the new mechanisms) |
| 5 | H89-P · prevalence-matched off-catalogue instrument | instrument only | thins `gems52-offcatalogue-b-v1` truth to the estimated hidden prevalence (|G| ≈ 5,949–12,512 px) | lets the **mass lever** be tested without a submission slot | H83's instrument over-rewards recall (4× prevalence, knowledge/76 §6); no prevalence-matched variant exists | untested; an instrument fix, not a submission path |

**Named non-fault processes that could mimic H88 (pre-registered):** lithologic contacts and
intrusive margins (gravity/magnetic edges with no fault offset); basin-margin facies steps
(cover-thickness steps without faulting); paleo-channels (elongated cover thinness); aftershock
clusters and induced seismicity (seismicity lineations off-fault); road cuts and canals (surface
linear features that raise View B); erosion lines in badlands (surface texture without structure).
Every A-only emitted dot gets a written reasoning row naming which components fired and these
alternatives (`docs/downloads/…-a-only-reasoning.csv`).

## 2 · Frozen H88 specification (no parameter is tuned after this point)

Views are rank-01 normalised inside the 19-band-finite ∩ organiser-domain footprint, combined with
the fixed weights below, then rank-01 again to get `a` and `b` in [0,1].

**View A (potential-field and subsurface)** — weights: `|iso_grav_anom_hg|` 0.22, `|tmi_hg|` 0.18,
cover-step `|∇(depth_to_base_surf)|` (σ=2 px Gaussian gradient magnitude) 0.22, seismicity-lineation
`|∇(deq_n100a15)|` (σ=2 px) 0.13, strain-step `|∇(geod_shearrate)|` (σ=2 px) 0.10, `|tmi_vg|` 0.10,
`cond_surf` 0.05. (Weights sum to 1.00. Pre-registered: cover-step is the largest single term with
the gravity edge because the round's geological thesis is burial.)

**View B (surface)** — weights: `det_elev_slope` 0.25, ridge curvature `|λ_min(Hessian(det_elev))|`
(σ=1.5 px) 0.30, topographic edge `|∇(det_elev)|` (σ=1.5 px) 0.20, **K/Th** = rad_K/(rad_Th+ε) 0.15,
`tc` (radiometric total count, band 6 by bytes) 0.10. (The K/Th direction is the inverse of H87's
Th/K: potassic alteration raises K relative to Th along fault-fed hydrothermal pathways,
`src/gems55/radlayers.py`.)

**Bidirectional disagreement field (the discovery signal):**

```
consensus = a * b
buried    = a * clip(a - b, 0, 1)          # A confident & B abstains  -> buried-fault candidate
artifact  = clip(b - a, 0, 1)               # B confident & A abstains  -> road/erosion suspect
veto      = rank01(artifact)                # percentile-ranked inside the footprint
field     = (0.45 * consensus + 0.55 * buried) * (1 - 0.70 * veto)
```

Fixed before any fit: buried weight 0.55 > consensus 0.45 (the lane says the discovery signal is
disagreement); veto 0.70 (strong, not absolute — `src/gems52/cotrain.py` warns that B-only can be a
real surface fault, not automatically a road).

**Not-the-union test (pre-registered):** the field requires A-support (both terms contain `a`) and
penalises B-only mass; the run card must show the emitted dots are not the union of the two views'
top-k supports (Jaccard against `topk(a) ∪ topk(b)` at the same K, and the fraction of dots whose
buried term dominates vs consensus-dominant).

**Independence gate (the Blum–Mitchell assumption, tested empirically):** per fold, block the
footprint into 50 px blocks; the "error" of each view on labelled negatives is its score on pixels
of `fold['region'] & ~fold['visible'] & ~fold['truth']` outside the 200 m visible-catalogue collar;
thresholds are each view's 90th percentile on those negatives; correlate (Pearson and Spearman)
block-level MSE and FPR between views with `gems52.spatial.negative_block_errors` +
`gems52.spatial.independence` (threshold 0.60). **If `allow_exchange` is false the co-training
method is abandoned and reported as such.** Iterative pseudo-label exchange is NOT run: it is a
closed negative (N-1, `knowledge/03`). `spatial.whole_pseudo_segments` (whole components, blocked
by train/block boundaries and catalogue buffers) is run only as a diagnostic count.

**Leakage canary:** every single component above is scored alone on the held-out truth inside the
allowed set per fold; AUC > 0.90 is treated as leakage until proven otherwise.

**Placement and emission:** `gems52.nodes.spacing_select`, min 3 px spacing (metric-aware), 200 m
catalogue collar (2 px) measured from the **visible** catalogue only in folds and from the full
catalogue in the shipped file; allowed set excludes visible catalogue pixels exactly (the organiser
masks them pixel-exactly — DrivenData thread 11516 posts #2/#4, recorded in `src/gems52/holdout.py`).

**Budgets:** holdout arms at 9,400 dots/fold (the matched budget of every comparable receipt) and
the mass-lever arm at 6,350/fold (= 25,400 over 4 folds); shipped file S = **25,400** (knowledge/76
§3: the same champion credit at S = 25,384 reaches 0.3195; the champion family over-emits 28–33 %).

**Holdout instrument (unchanged, reused):** `gems52.spatial.folds(cat, valid, buffer_px=80)`
(whole 8-connected components, label-blind quadrants), `gems52.evaluate_holdout.evaluate`
(`gems52-pooled-hide-v1`, α 0.2, β 0.8, R 300 m triangular kernel), `pooled_summary` (paired
20 km spatial-cluster bootstrap, 1,000 draws). **Bar to beat for promotion: HOLDOUT-DTI 0.192829**
(H82 `B_DVA2`, `evidence/h82_holdout.json`); H84-main primary 0.190147 [0.1689, 0.2112]. A candidate
that does not beat the bar is `verdict: negative` for slot purposes; a negative result is still a
deliverable and the file is still generated and published for download.

**Arms (6 × 4 folds):** `cotrain_bi` (PRIMARY, the field above), `consensus_only` (ablation),
`buried_only` (ablation), `single_A` (view A alone), `single_B` (view B alone, the single-view
baseline the brief demands), `random` (floor, seed 88001 + fold).

## 3 · Lane-drift discipline (parallel-run protocol rule 1)

Before placement (on the raw field) and again on the final dots: Spearman rank-correlation of the
shipped raster against every registry raster must be ≤ 0.90, and ≤ 70 % of shipped dots may fall
within 3 px of any single registry raster's dots (excluding the candidate's own download copies,
IR-H85-001). Registry = `submission/`, `docs/downloads/`, `data/scored/`, `data/reference/`.
The universal-coverage probe caveat (IR-H85-009) is reported, not silently waived.

## 4 · What is deliberately NOT claimed

* No ORGANIZER-CONFIRMED number exists for any file in this family; every score in this round is
  HOLDOUT-DTI (evaluator `gems52-pooled-hide-v1`) or an owner-reported board value quoted from the
  standing brief (unverified by receipt).
* Holdout DTI and the public board are not correlated in this family (Spearman −0.10, `AGENTS.md`);
  a holdout result is a gate, not a forecast.
* The champion's identity and its 0.2778 attribution are owner-reported; the raster itself is
  integrity-pinned, not organiser-authenticated (`registry/data_manifest.json`).
