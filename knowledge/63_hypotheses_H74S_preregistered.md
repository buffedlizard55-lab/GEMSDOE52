# H74S — preregistered co-training hypotheses and frozen test plan

**Round identity:** `H74S` (geophysics/surface co-training; seismicity–strain View A). Frozen before any H74S fit, canary calculation, holdout evaluation, or candidate placement. This name is distinct from the repository's parallel-session `H72` and `H73` records; those records are not changed or reused as H74S results.

**Scope:** this is the single method lane in the current brief: two-view co-training, with disagreement as the discovery signal. It does not fit a third view, use prior prediction rasters as model features, or select/spend a DrivenData submission slot. A local GeoTIFF is allowed only after all frozen gates pass; passing them would make it selector-eligible, not organizer-approved.

## 1. Repository review and current scientific starting point

Before proposing H74S, reviewed the current feature manifest and code paths, `knowledge/03`, `knowledge/31`, `knowledge/38`, `knowledge/40`, `knowledge/42`, `knowledge/48`, `knowledge/53`, `knowledge/55`, `knowledge/58`, `knowledge/60`, `knowledge/62`, and the H61–H73 preregistrations, run cards, and results. The key prior co-training outcome is H72: strain-only View A used bands 4/7/8 and the unchanged H61 surface View B. Its leakage canary did not fire and its blockwise error-correlation screen permitted one exchange, but the A-only arm could not fill the fixed per-fold holdout budget (1,092/1,264 in one fold), so the comparison was **invalid as a matched-budget comparison**. The measured A-only HOLDOUT-DTI was 0.005895 [0.002982, 0.009148] (evaluator `gems52-pooled-hide-v1`, 53,186 withheld positives); this is an underfilled-arm result, not evidence that A-only beats the control. Its surface rank passed, but its final dots violated the literal lane rule: 91.44% were within 3 px of one informative prior, so H72 stopped and wrote no TIFF. These are H72 receipts, not H74S measurements.

H61's broad View A already included raw seismic bands 10/16 among many geophysical/subsurface channels. The repository's preregistered R5-H2 queue identified a dedicated seismicity corridor test as not run. H72 separately isolated raw strain bands 4/7/8. H74S therefore tests a **frozen, restricted joint strain–seismic View A**, not a renamed H61 field or a repeat of H72. Its novelty claim is limited to that feature grouping and test; the bands themselves are not new data.

The source checkout initially had no `data/` rasters and no `work/r2/features` cache. The only permitted recovery path used here is the repository's hash-pinned GitHub owner mirrors. Those SHA-256 checks establish mirror integrity only; they do **not** authenticate that the mirrored bytes are identical to organizer-served bytes. H74S will not claim portal authentication or any organizer score.

## 2. Four new co-training hypotheses, ranked before H74S fit

The rankings are qualitative research priorities, **not numeric DTI predictions**. Each candidate uses the shared cached/view builder, H61's unchanged View B, whole-segment spatial folds, and the same independence/holdout/lane gates. Only the top-ranked hypothesis is run in H74S; the other three remain untested.

### Rank 1 — H74S-A: coupled strain–seismic activity beneath a quiet surface (selected)

- **Layers:** View A = competition feature bands 4 (geodetic second invariant), 7 (geodetic shear rate), 8 (geodetic dilatation rate), 10 (distance-to-earthquake surface), and 16 (earthquake intensity/density surface). View B = the unchanged H61 surface feature list: DEM-derived curvature/slope and radiometric inputs. Band descriptions are read from the local GeoTIFF tags/inventory; because those bytes are an owner mirror, the descriptions are not represented here as organizer-authenticated metadata.
- **Physical signature:** a learned local conjunction of spatially concentrated strain magnitude/shear/dilatation and the provided seismic distance/intensity pattern, with the candidate emitted only where the View-A OOF rank is at least 0.95 and the View-B OOF rank is in [0.35, 0.65]. This is a joint-response hypothesis; it does **not** assert that high strain or an earthquake-distance surface alone identifies a fault.
- **Why it might detect a missing fault:** a buried or covered fault can lack a DEM scarp while still being associated with localized deformation or seismic activity. The spatially withheld segments, not proximity to the visible catalogue, are the test of that idea. The layer names do not establish event timing or fault causality.
- **Difference from implemented work:** H61 fit a broad A set in which these bands were only members; H72 tested raw strain bands 4/7/8 alone; H74S isolates the strain-plus-seismicity combination. It uses no prior submission raster as a feature, no catalogue-derived distance to hidden faults, and no A/B union.
- **Expected DTI improvement / cost:** highest relative priority among the four, but high uncertainty given H61/H72 results; medium implementation cost because the required inputs are already in the shared feature stack. No score projection is made.
- **Named non-fault mimic:** a geothermal or volcanic earthquake swarm, aftershock sequence, or a geodetic interpolation/survey seam that is not a mapped fault.

### Rank 2 — H74S-B: seismicity-only directional gradient against surface abstention (deferred)

- **Layers:** View A = bands 10 and 16 only; View B = the unchanged H61 surface view.
- **Physical signature:** a multi-scale spatial change in the 100-km / 15-degree-parameter seismic-distance surface accompanied by local event-intensity structure. The transformation would be fitted inside the training folds and must not infer an azimuth from the band description unless its original metadata confirms that meaning.
- **Why it might detect a missing fault:** seismic activity can be structured by buried faults even when surface relief is muted; this is directly testable on withheld catalogue segments.
- **Difference:** a dedicated seismic-only learner, rather than H61's mixed A model or H74S-A's joint strain–seismic view. The seismic corridor idea is queued in `knowledge/45_h65b_preregistered.md`, but that document labels it unrun; H74S does not count it as an observed result.
- **Expected DTI improvement / cost:** medium-low relative priority; low-to-medium cost. No external data are needed if limited to the two competition bands.
- **Named non-fault mimic:** a non-tectonic geothermal swarm or aftershock cluster.

### Rank 3 — H74S-C: conductivity–basement edge pair beneath radiometric/terrain abstention (deferred)

- **Layers:** View A = competition band 17 (conductivity), band 15 (depth to basement), and gravity horizontal/vertical gradient bands 18/11; View B = DEM curvature/slope and radiometric layers.
- **Physical signature:** co-located conductivity and basement-step discontinuity with gravity-gradient support; the prediction must remain A-confident/B-abstaining. It is not a simple sum of four ranks.
- **Why it might detect a missing fault:** a fault buried under basin fill may juxtapose conductive alteration or fluids and a basement offset without a surface scarp. The holdout is still required because lithology can cause the same contrast.
- **Difference:** this uses an explicit conductivity–basement cross-layer interaction. Prior broad A stacks contained some of these raw channels, and H69 proposed basement/gravity transforms; therefore this has lower novelty than H74S-A and must be checked against those exact receipts before any later run.
- **Expected DTI improvement / cost:** low-to-medium relative priority; medium-to-high cost for normalized, fold-safe edge features and coverage tests.
- **Named non-fault mimic:** a lithologic contact or conductive clay/alluvium boundary across a basin margin.

### Rank 4 — H74S-D: strain-tensor discontinuity coherence (deferred)

- **Layers:** View A = bands 4/7/8; View B = the unchanged H61 surface view.
- **Physical signature:** multi-scale strain-gradient magnitude and cross-channel gradient alignment, rather than the raw strain magnitude tested in H72; emit only A-confident/B-abstaining pixels.
- **Why it might detect a missing fault:** a buried structure can localize strain gradients even when topographic lineaments are absent.
- **Difference:** a transform of the H72 channels. H72 already tested the raw strain view and had an underfilled, below-baseline A-only result; the transformed version is not represented as tested or validated here.
- **Expected DTI improvement / cost:** lowest relative priority because it reuses a weak H72 family; medium implementation cost for a shared, tested transform and a complete rebuilt cache.
- **Named non-fault mimic:** broad interseismic loading, gridding seams, or interpolation edges.

## 3. Frozen H74S-A protocol and decision rules

### Data and shared tools

- Restore only the hash-pinned owner-mirror copies of `training_features.tif`, `labels.tif`, `sample_submission.tif`, and the two GeoDAWN rasters needed by the already-shared external feature extension. Verify each file against `registry/data_manifest.json` and run `scripts/prepare_data.py`. Report them as **owner-mirror integrity verified; organizer authentication unavailable**.
- Use `src/gems52/structural.py` and `src/gems52/external.py` as the shared feature-stack implementation; do not write a private feature builder. Recreate `work/r2/features` only because the cache was absent in this fresh checkout, and disclose that recreation. Do not copy or train on prior prediction rasters.
- Reuse `scripts/run_h61.py`'s folds, sampler, HGB learner, prediction and whole-segment exchange hooks; `src/gems52/evaluate_holdout.py` (`gems52-pooled-hide-v1`); `src/gems52.metric`; `src/gems52.nodes.spacing_select`; `src/gems52.gates`; and `src/gems52.submission_writer`. A shared defect is fixed in the shared tool, not a local fork.
- Whole-fault-segment hide-and-recover folds use an 80-pixel (8 km) train/evaluation buffer. For each fold, derive catalogue-based features/support only from fold-visible catalogue pixels and mask those visible pixels exactly. Never use held-out positive pixels to build a feature, emission mask, normalization, or threshold.

### E1 — leakage and fold-fit gate

- Test each of the five View-A features individually on the fold-held-out region before trusting a model. The 0.90 threshold is a **leakage-canary AUC alarm**, not a performance target: an AUC > 0.90 is treated as leakage until proven otherwise, and the run stops for investigation.
- Fit the selected A and fixed B learners on the same training fold; save OOF predictions for the fold's held-out region only. All fold-derived normalizations/ranks are computed without using withheld labels.

### E2 — independence, at most one exchange, hide-and-recover

- Correlate the two views' spatial-block OOF errors on labelled negatives using 50×50-pixel blocks. Negative pixels are catalogue-zero proxies, **not verified absences**. If either absolute Pearson or Spearman correlation is undefined or at least 0.60, abandon co-training and perform no pseudo-label exchange.
- If the independence gate permits exchange, pseudo-label only whole segments chosen by `spatial.whole_pseudo_segments`: donor OOF rank ≥0.95; receiver OOF rank in [0.35,0.65]; segment separated from evaluation/held-out labels by the frozen 80-pixel buffer; minimum 5 pixels and maximum 2,000 pixels per fold; one exchange round total. Verify no pseudo-label intersects the evaluation region, held-out components, or catalogue-positive pixels.
- Evaluate the A-only disagreement arm and the single-view `single_B` baseline at a fixed **1,264 emitted dots per fold per arm** with 3-pixel minimum spacing. If any arm cannot fill that same budget in every fold, label the comparison invalid; do not lower the budget or re-tune after seeing results.
- Pool the evaluator's weighted terms and bootstrap on 20-km spatial blocks, 1,000 paired draws, 95% interval. Use alpha=0.2, beta=0.8, triangular radius=300 m. The report must include the measured withheld-positive count and evaluator version. Re-run the shared `single_B` control at 9,400 dots/fold and require it to reproduce the prior comparable HOLDOUT-DTI reference 0.174571 within 0.001; label this a control-reproduction check. Separately compare H74S-A with `single_B` and random at the fixed 1,264-dot/fold budget. These are local HOLDOUT-DTI diagnostics, not leaderboard projections.
- Holdout promotion criterion for any later selector: the 9,400-dot/fold `single_B` control reproduces the reference within 0.001; candidate-minus-single_B paired 95% CI lower bound >0 at 1,264 dots/fold; all arms fill matched budgets; and candidate exceeds the holdout random control. Even then, do not use or select a competition slot here.

### E3 — conditional build and gates (only if authorized by E1/E2)

- First normalize the full OOF surface to [0,1] and run the shared `lane_report(phase="surface")` against the frozen accessible-prior census plus local previous submissions. If any registry-raster rank-correlation exceeds 0.90, record `DUPLICATE/STOP` and do not place dots.
- If the surface gate passes, apply shared 3-pixel metric-aware placement. Re-run `lane_report(phase="dots")`; if >70% of the emitted dots lie within 3 px of any one registry raster, record `DUPLICATE/STOP` and do not write or publish a TIFF. No placement tuning after this gate.
- Require shared decoded-pixel uniqueness, at least 20% support novelty relative to accessible aligned priors, and a not-the-union comparison against both views. If any fail, stop without a submission TIFF.
- Only after these gates pass, write one uniquely named, single-band GeoTIFF with `submission_writer`; re-open it and check no NaN inside the sample footprint, all predictions in [0,1], and CRS/shape/geotransform identical to `sample_submission.tif`. Generate one geological-reasoning row per A-only dot, including measured feature values and an explicit non-fault alternative. Local format validity is not an organizer acceptance receipt.

### Budget and allowed verdicts

- Maximum: three experiments or two wall-clock hours. E1, E2, and conditional E3 are the only experiments; no hyperparameter search or extra placement attempt.
- Verdict is `negative` unless every frozen gate passes. A negative result is a deliverable. No automatic or manual competition upload, no slot selection, and no claim of an organizer-confirmed score.

## 4. Source/access boundary and scientific limits

- Competition task/rules and official data entry point: [DrivenData GEMS problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) and [data tab](https://www.drivendata.org/competitions/306/competition-doe-gems/data/). The repository records the data tab as login-walled; no DrivenData credentials are available in this run.
- Method reference: Blum & Mitchell, *Combining Labeled and Unlabeled Data with Co-Training*, COLT 1998, pp. 92–100, [DOI 10.1145/279943.279962](https://doi.org/10.1145/279943.279962). Their assumptions (view sufficiency and approximate conditional independence) are not guaranteed by these rasters; H74S tests error correlation as a diagnostic, not as proof of independence.
- Geological data context: [DOE Geothermal Data Repository submission 1391 / INGENIOUS](https://gdr.openei.org/submissions/1391) and [USGS GeoDAWN data release](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and). The H74S model uses only channels already in the competition training raster and its pre-existing shared GeoDAWN extension; it does not download a new external dataset.
- If a later hypothesis requires independently updated earthquake events, the named free official source is the [USGS ComCat/FDSN earthquake catalog](https://earthquake.usgs.gov/data/comcat/). It is **not required or used** for H74S. This sandbox's egress allowlist does not include `usgs.gov`, so a new ComCat fetch is not currently obtainable here; the mirrored competition bands are the only seismicity data used.
- The target remains fault susceptibility/trace recovery for this competition, not verified geothermal vents or surface truth. Phase-2 geological review is not replaced by model confidence. No A-only candidate may be described as a confirmed fault.
