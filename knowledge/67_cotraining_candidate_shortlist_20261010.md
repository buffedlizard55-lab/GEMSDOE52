# Follow-on co-training hypothesis shortlist — 2026-10-10

**Status: pre-fit shortlist, not an experiment authorization.** This note ranks three geological proposals within the registered two-view lane; it does **not** establish that all three are distinct enough, cache-supported, or viable for fitting. G1’s feature names/hashes appear in the checked-in CTD5 manifest, but the runtime cache arrays are absent in this checkout, so its actual cached support cannot be re-read. H72-C’s four proposed raw channels all overlap H74’s broader A2 view; the narrower composition may be distinct, but novelty has not been established. Do not call these three verified candidates. No model was fitted, no holdout was run, no TIFF was emitted, no run-card was created, and no submission slot was used in preparing this list. H72-A is terminal and cannot be rerun; H75 is also a terminal DUPLICATE/STOP and is not a candidate. H72-D remains data-blocked and is excluded. The hypotheses below would belong to a separately authorized future round; freeze that round's exact preregistration and hash before any fitting.

## Fixed lane and evidence guardrails

- **View A:** geophysical/subsurface teacher. **View B:** the existing shared DEM/surface plus available radiometric feature list. Disagreement is the discovery signal; do not build a private feature stack or change the shared learner, sampler, evaluator, splitter, placement, or writer.
- Reuse the shared feature store if present and the H61 shared stages. The ignored runtime cache `work/r2/features` is absent in this checkout; the checked-in feature manifest records the shared gravity/potential-field channels, but this is not permission to create a private replacement. Before any authorized fit, restore/rebuild only through the shared cache builder in place and confirm the manifest; otherwise stop.
- Before fitting: preregister one candidate, comparator, candidate budget, folds, all thresholds, and the stop rule. Run per-feature leakage canaries (AUC >0.90 is an alarm) and spatial-block OOF error-dependence checks on labelled negatives. Do not exchange pseudo-labels if the registered strong-dependence stop is met. If exchange is allowed, use only confident-versus-abstaining whole segments, with the shared buffer and visible/hidden-component exclusions.
- Validate only with the shared spatial-block hide-and-recover protocol: hold out whole fault segments with the registered buffer; derive folds from visible labels only; exclude/mask the visible-fault positives exactly; use pooled DTI with α=0.2, β=0.8, and the 300 m triangular kernel; report evaluator, withheld-positive count, achieved fold budgets, paired 95% CI, and the `single_B` comparator. Do not treat a projection or public-board observation as a score.
- Check registry rank-correlation before placement and final dots. Any correlation >0.90 or >70% of dots within 3 px of one registry raster is the literal `DUPLICATE/STOP`; do not retune around it. Require the output not to be the union. Do not select or use a weekly slot; a candidate must beat the comparable holdout best before separate slot consideration.

## Ranked hypotheses (all three untested as the specified standalone view)

### 1. Gravity-boundary persistence teacher — follow-on candidate G1

- **Layers:** the checked-in `docs/data/ctd5_feature_manifest.json` lists `raw_band_05` (isostatic-gravity slope), `raw_band_11` (vertical gradient), `raw_band_13` (isostatic gravity anomaly), `raw_band_18` (horizontal gradient), and transforms `A_gravity_grad_1/3/8`, `A_gravity_persistence_1_3`, `A_gravity_persistence_3_8`, and `A_gravity_coherence`. The manifest is metadata, not a restored runtime cache: `work/r2/features` is absent here, so actual array support/values are not re-read. View B remains exactly the registered shared surface/radiometric list.
- **Physical signature:** a spatially coherent gravity-gradient edge that persists across the shared 1-, 3-, and 8-pixel scales, consistent with a basement-density boundary or abrupt basin-fill thickness change.
- **Why an unmapped fault might show it:** a covered basin-bounding or intrabasinal fault can juxtapose dense basement and lower-density basin fill while producing little present-day relief; this could yield an A-confident/B-abstaining corridor. It is only a plausibility argument: regional density changes and lithologic contacts can produce the same response.
- **Difference from prior methods:** prior broad View-A models and several structural experiments included gravity together with magnetics, strain/seismicity, basement depth, or surface evidence. This proposal isolates the gravity family as the entire View-A teacher and uses only transforms already in the shared feature manifest; it does not add an external layer or a private detector. No prior matched-budget co-training test of this exact standalone gravity view was found in the reviewed H72/H74 records.
- **Expected value / cost:** **low-to-moderate relative priority, high uncertainty**; physically relevant to buried basin structure, but likely limited by non-fault density contacts. **Moderate cost**: use existing shared channels, then the standard canary, independence, one allowed exchange, and matched holdout. If any needed feature is absent from the restored shared manifest, defer rather than derive a private substitute.
- **Named mimics:** lithologic contact, basin-fill edge not caused by a fault, volcanic density contrast, interpolation seam, or gravity-survey line artifact.

### 2. Magnetic-edge-only teacher — existing H72-B

- **Layers:** View A uses `raw_band_02` (RTP magnetic anomaly), `raw_band_03` and `raw_band_09` (TMI horizontal/vertical derivatives), `raw_band_14` (TMI), and the existing 150 m upward-continued TMI channels `X_mag_TMI_up150_*`. View B is unchanged.
- **Physical signature:** a coherent magnetic-source boundary that persists between measured shallow-field derivatives and the existing upward-continued product, specifically where the surface/radiometric view abstains.
- **Why an unmapped fault might show it:** a covered basement discontinuity can displace or juxtapose magnetic units without making a surface scarp; a continuation beneath basin cover could therefore be absent from the mapped catalogue.
- **Difference from prior methods:** magnetic channels have appeared in mixed View-A models and structural-consensus features; H72-B changes the composition by isolating the magnetic family as the complete View-A teacher. It does not change the co-training lane or invent a new transform.
- **Expected value / cost:** **low**, with high uncertainty: a persistent edge is geologically plausible but not fault-specific. **Moderate cost** using restored shared features and the same tests.
- **Named mimics:** lithologic contact, dike or intrusive edge, flight-line/tie-line artifact, or a magnetic source unrelated to displacement.

### 3. Seismo-kinematic teacher — existing H72-C

- **Layers:** View A uses earthquake distance/density `raw_band_10` and `raw_band_16` with geodetic shear and dilatation `raw_band_07` and `raw_band_08`. View B is unchanged.
- **Physical signature:** spatially coherent event-density and deformation/shear evidence in a corridor where View B abstains; the model must distinguish a linear, fault-compatible expression from isolated event clusters.
- **Why an unmapped fault might show it:** an active or recently active concealed structure could localize both deformation and seismicity despite subdued topography or cover.
- **Difference from prior methods:** H74’s 22-channel deformation/seismicity A2 view already included all four proposed raw inputs (`raw_band_07`, `_08`, `_10`, `_16`) plus transforms. H72-C is a narrower four-raw-channel teacher and was not isolated under that exact composition, but 4/4 proposed raw channels overlap H74 A2. Its novelty/distinctness versus H74 and earlier mixed methods therefore remains unverified; do not count it as a distinct viable candidate until the prior-method audit is complete.
- **Expected value / cost:** **very low / uncertain**; likely constrained by sparse events, catalogue completeness, and the fact that tectonic/volcanic swarms are not necessarily faults. **Low-to-moderate cost** with the shared feature store and evaluator.
- **Named mimics:** earthquake swarm, volcanic or hydrothermal unrest, event-catalogue density boundary, or broad interseismic loading.

## Explicit exclusions and next gate

- **H72-A:** already tested, negative/terminal, and not eligible for a rerun.
- **H72-D heat-flow gradient:** excluded because the proposed official external heat-flow payload has not been obtained, rights/resolution verified, or hash-pinned; it is data-blocked, not a viable candidate today.
- **H75:** final-dot `DUPLICATE/STOP`, support novelty 0.0, red/research-only, **NOT FOR SUBMISSION**; no override or rerun.
- The list above is not a run-card and does not authorize any fit. If a future experiment is authorized, choose one hypothesis, write and hash its full preregistration before fitting, confirm access to the shared cache and fixed View B, and stop if the cache, feature provenance, or comparator cannot be reproduced. No weekly slot is selected or consumed here.

## Official, reviewable sources

1. [DrivenData GEMS problem statement](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) — target, available inputs, incomplete catalogue, and competition metric.
2. [USGS GeoDAWN magnetic and radiometric data release](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and), DOI [10.5066/P93LGLVQ](https://doi.org/10.5066/P93LGLVQ) — public provenance for the survey family; local mirrored bytes still require their repository hashes.
3. [USGS isostatic-gravity map for the Death Valley ground-water model area](https://pubs.usgs.gov/mf/2002/mf-2381/mf-2381-c/c_508.pdf) — notes that linear isostatic-gravity anomalies may reflect mapped basin-bounding faults; it supports plausibility, not fault-specificity.
4. [USGS regional study of Nevada gravity and magnetic anomalies](https://www.usgs.gov/publications/regional-study-mineral-resources-nevada-insights-three-dimensional-analysis-gravity) — discusses density variations, basin geometry, and the limits of interpreting gravity/magnetic structure.
5. [DOE GDR INGENIOUS compilation](https://gdr.openei.org/submissions/1391), DOI [10.15121/1881483](https://doi.org/10.15121/1881483) — regional geophysical/geodetic data provenance and catalog context.
6. [USGS blind geothermal systems report](https://www.usgs.gov/publications/discovering-blind-geothermal-systems-great-basin-region-integrated-geologic-and), DOI [10.2172/1724080](https://doi.org/10.2172/1724080) — supports integrated subsurface/structural reasoning only; it does not validate these candidates.
