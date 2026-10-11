# H72 result, score provenance, and limits (2026-10-09)

## Decision in one line

**The final H72-A co-training run ended negative at the preregistered final-dot lane gate. No H72-A GeoTIFF was written or published.** The H72-A diagnostic bitmap was distinct in the accessible 619-raster inventory, but had zero support novelty, was a subset of the prior union, and failed both literal and saturation-aware final-dot near-duplicate limits. Separate legacy H72-v3/SPSC/MRAEC TIFFs from an earlier workflow are present in `docs/downloads/`; they are research archives, not H72-A outputs, and are not approved for submission. H72-A did not enter a selector, use a slot, upload, or receive an organizer decision.

| State | H72-A final run | Legacy H72 files |
|---|---|---|
| Downloadable | **NO — no H72-A TIFF emitted** | **YES — research/archive only** |
| Portal-format validation | **NOT ASSESSED — no H72-A file** | Historical local checks only; not organizer acceptance |
| Organizer-confirmed receipt | **NO receipt found** | **NO receipt found** |
| Approved for competition submission | **NO — terminal STOP** | **NO — research-only; H72-v3 is not recommended** |
| Selector/slot decision | **None; 0 slots used** | **None; 0 slots used** |

These are distinct states. A legacy download, a local format check, and organizer approval are not interchangeable.

## What the reported 0.2778 does—and does not—establish

The evidence classes below are intentionally separate. Neither the public score table nor a repository mirror is a submission receipt.

| Evidence class | Observed value / object | Evidence and limitation |
|---|---|---|
| **PUBLIC-LEADERBOARD observation** | `0.2778`, rank 17, team row `extradr19` in the live 2026-10-09 20:18 UTC observation | The saved live-page transcription is `evidence/leaderboard_observation_2026-10-09T201800Z.json`; it also shows #1 at 0.3774 and #7 at 0.3195. The earlier 2026-10-07 frozen snapshot remains historical and listed `extradr19` at a different rank. The live board is team-level and contains no filename, file hash, upload receipt, or causal explanation. The public row and internal file label are not proven to be the same scored submission. |
| **OWNER/USER-REPORTED file/score match** | Label `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros`, reported `0.2778` | `evidence/ctd5_owner_reported_results.json` records the owner-reported association; its `receipt` and `authenticated_file_sha256` are null. This is not an organizer-confirmed pairing. |
| **Local owner-mirrored bytes** | `reference/h33-2-b2-zeros.tif`; SHA-256 `c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9`; 37,654 binary dots, none on the local known-fault catalogue | `evidence/h61_forensics.json` measured the restored mirror. Its filename token `e5eb6e7e` matches none of the six recorded file/decoded/support hash variants (`token_hash_linked: []`). The file hash verifies the local bytes, not an upload or score attribution. |
| **ORGANIZER-CONFIRMED receipt** | **None located** | There is no receipt tying a submission ID, the file hash, and a score. Do not upgrade either of the preceding rows to organizer-confirmed. |

### Exact local relation; no causal score explanation established

The local H33-labelled bitmap has 37,654 dots and is a strict support subset of a separate 44,090-dot bitmap whose **0.2600 value is owner-reported**. Recomputed against the correct d2-8 parent and `data/labels.tif`, the subset comparison finds 6,436 cells removed and zero added; all removed cells are 100–200 m from known-mask positives (5,092 at 100 m; 1,344 at 200 m). H33's nearest retained cell is 223.6068 m from a known-mask positive. These are local byte/spatial facts, not evidence of which hidden pixels received score credit.

Official DrivenData staff confirms in the [scoring clarification](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4) that the known-fault mask is pixel-exact, only new-fault ground truth is scored, and new-fault pixels may lie within 300 m of known traces. Therefore the removed 100–200 m cells are **not automatically score-free or zero-credit**; hidden new-fault truth could occur in that neighborhood and receive distance-kernel credit. The local comparison is consistent with a precision-pruning hypothesis, but it does not establish why any organizer score changed.

Do not use the point `|G| = 14,088.7` as an established fact. The previous audit derived an identified interval `[5,949.3, 12,512.1]` under stated assumptions; its 14,088.7 point estimate requires the unverified assumption that the 6,436 removed cells earned exactly zero hidden-truth credit. A holdout DTI is an internal hide-and-recover measurement and cannot authenticate or reproduce a public leaderboard result.

### Snapshot-date correction

The frozen preregistration document `knowledge/59_hypotheses_H72_preregistered.md` mistakenly calls the committed public-board snapshot “dated 2026-10-09.” That file in `registry/` is actually dated **2026-10-07**; the preregistered hypothesis file was left byte-identical after fitting, so its pinned hash remains valid. A later live board read on 2026-10-09 at 20:18 UTC is separately recorded in `evidence/leaderboard_observation_2026-10-09T201800Z.json`; it is not a replacement for the older snapshot and still does not map a public row to a TIFF.

## H72 experiment and gates

The run followed the frozen two-view co-training lane: View A used `raw_band_04`, `raw_band_07`, `raw_band_08` (strain-rate tensor invariant, geodetic shear, and signed dilatation); View B stayed on the shared DEM/surface and available radiometric channels. OOF disagreement—not a union—was the discovery signal. Shared features, fit/evaluator, placement and gates were reused; no private evaluator or alternative placement was introduced. E1/E2 receipts were reused unchanged after fixing the runner's grid-flat-index gather and receipt-path bugs. The experiment ceiling was respected: **3 experiments, 2,256.6 seconds**.

| Gate | Result | Receipt |
|---|---|---|
| Per-feature leakage canary (AUC diagnostic, **not DTI**) | No alarm; max direction-insensitive AUC 0.66868, below the 0.90 alarm | `evidence/h72_canary.json` |
| Spatial-block OOF view-error correlation on catalogue-zero proxy negatives | Maximum absolute correlation 0.05064, below the 0.60 abandon threshold; one registered exchange allowed. These negatives are proxies, not verified fault absence. | `evidence/h72_independence.json`, `evidence/h72_pseudo_exchange.json` |
| Pre-placement surface comparison, 619 registry rasters | Literal PASS; max Spearman 0.05110; no errors | `evidence/h72_lane_surface.json` |
| Final-dot literal lane test, 619 rasters | **DUPLICATE/STOP.** Maximum rank correlation 0.01111; maximum fraction within 3 px of one raster = **1.00000**, above the 0.70 stop limit. A universal-coverage probe in GEMSDOE48/H56 accounts for the literal saturation. | `evidence/h72_lane_dots.json` |
| Final-dot saturation-aware policy | **DUPLICATE/STOP.** Maximum near-dot fraction **0.914359**, still above 0.70; worst informative prior is the owner-mirrored `15GEMSDOE` curvature/scarp raster. Policy does not waive the literal failure. | `evidence/h72_lane_dots.json` |
| Decoded-pattern / support uniqueness | Canonical bitmap differs from each accessible prior and from their literal union, but support novelty is **0.0** and the candidate is `subset-of-union`; research-release novelty gate fails. Inventory scope is limited to the 619 supplied/aligned rasters. | `evidence/h72_uniqueness.json` |
| Strict-stratum / union diagnostic | 5,056 diagnostic dots, all strict A-only; not equal to single A, single B, or max(A,B) placements. This is a method diagnostic, not a score or released raster. | `evidence/h72_not_union.json` |

The final-dot stop was preregistered and is terminal for this candidate. No placement retuning or gate bypass followed it.

### HOLDOUT-DTI — internal hide-and-recover only

All numbers in this table are **HOLDOUT-DTI** from evaluator `gems52-pooled-hide-v1`, with **53,186 withheld positive pixels**; the displayed intervals are 95% CIs. The metric settings are α = 0.2, β = 0.8, and a 300 m triangular kernel.

| Arm | HOLDOUT-DTI (`gems52-pooled-hide-v1`; 53,186 withheld positives) | 95% CI | Fold-fill note |
|---|---:|---:|---|
| H72 strict A-only candidate | 0.00589479 | [0.00298176, 0.00914770] | 1,264 / 1,264 / **1,092** / 1,264 (target 1,264 per fold) |
| Single-B reference | 0.06146088 | [0.04892735, 0.07470335] | Not a valid matched comparison to the underfilled candidate |

The candidate underfilled fold 2. `matched_comparison_valid=false`; **no candidate-minus-single-B paired delta is reported**. Do not present the separate arm estimates as a matched win/loss or leaderboard-score prediction. The holdout estimates and confidence intervals are not organizer results.

## Ranked hypotheses and what was learned

Four hypotheses were recorded in `knowledge/59_hypotheses_H72_preregistered.md` before fitting. H72-A was the only candidate tested; the other three are proposals, not results. Expected-improvement ranks below are qualitative research priorities, not numerical DTI projections.

1. **H72-A — strain-only A-view; highest relative expected gain among viable existing-data candidates, but likely modest and uncertain.** Layers: `raw_band_04`, `raw_band_07`, `raw_band_08`. Target: coherent shear/strain with dilatational contrast where fixed surface/radiometric View B abstains. Potential for concealed structures under cover; differs from earlier mixed A views by isolating deformation as the entire A view. Moderate cost. Mimics include broad interseismic loading, geodetic survey seams, and interpolation artifacts. **Tested; negative.**
2. **H72-B — magnetic-edge-only A-view; low expected gain.** Layers: RTP magnetic anomaly `raw_band_02`, TMI derivatives `raw_band_03`/`raw_band_09`, TMI `raw_band_14`, and existing 150 m upward-continuation channels. A persistent shallow/deep magnetic edge might expose a buried basement discontinuity; unlike prior mixed A views, the magnetic family would be isolated. Moderate cost. Mimics: lithologic contacts, flight-line/tie-line artifacts, and non-fault magnetic sources. Not tested.
3. **H72-C — seismo-kinematic A-view; very low/uncertain expected gain.** Layers: event distance/density `raw_band_10`/`raw_band_16` with shear/dilatation `raw_band_07`/`raw_band_08`. Target: a coherent event-plus-deformation corridor where surface View B abstains. The proposed A composition has not been isolated from the earlier mixed A sets. Low-to-moderate cost. Mimics: earthquake swarms, volcanic/hydrothermal unrest, and event-catalogue density artifacts. Not tested.
4. **H72-D — heat-flow-gradient teacher; potentially interesting but blocked, not viable in this run.** Proposed input: gradient/edge of an official Great Basin heat-flow grid, not present in the cache or competition feature stack. Could reflect buried permeability, but is not fault-specific. High cost and dependent on obtaining/verifying official bytes and licensing; mimic: lithology, groundwater advection, sparse-well interpolation. Not tested and not to be smuggled into H72.

The per-dot A-only reasoning CSV is preserved as an internal evidence diagnostic (`evidence/h72_a_only_reasoning_candidate.csv`), not a TIFF and not a submission file. It carries hypotheses and named non-fault alternatives; it is not field confirmation.

## Reviewable sources

- Official [DrivenData problem description and metric](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) — problem framing, input context, fault-catalogue limitations and distance-weighted evaluation.
- Official [DrivenData leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) — live reading captured 2026-10-09 20:18 UTC; see `evidence/leaderboard_observation_2026-10-09T201800Z.json`. Public-board observation only, not an organizer receipt.
- USGS [GeoDAWN airborne magnetic and radiometric release](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and), DOI [10.5066/P93LGLVQ](https://doi.org/10.5066/P93LGLVQ) — context for the survey family; H72 used mirrored competition inputs, not a newly fetched USGS raster.
- DOE Geothermal Data Repository [INGENIOUS regional compilation](https://gdr.openei.org/submissions/1391), DOI [10.15121/1881483](https://doi.org/10.15121/1881483) — record lists geodetic shear/dilatation, seismicity, gravity/magnetics and other datasets; landing-page record states CC BY 4.0. It does not authenticate the local competition mirrors.
- USGS [blind geothermal systems report](https://www.usgs.gov/publications/discovering-blind-geothermal-systems-great-basin-region-integrated-geologic-and), DOI [10.2172/1724080] — integrated geologic/geophysical plausibility only, not validation of this detector or any candidate.
- Blum & Mitchell, [“Combining labeled and unlabeled data with co-training”](https://doi.org/10.1145/279943.279962), COLT 1998 — method context; it does not establish H72 view sufficiency or conditional independence.
- USGS [Great Basin heat-flow maps and supporting data](https://doi.org/10.5066/P9BZPVUC) — a possible later data source only. The official landing record was reviewed; payload bytes were not downloaded or hash-verified and were excluded.

## Reproduction and artifacts

The final authoritative machine-readable status is [`evidence/h72_run_card.json`](../evidence/h72_run_card.json); the web copy is [`docs/data/h72_run_card.json`](../docs/data/h72_run_card.json). Evidence includes `h72_holdout.json`, `h72_lane_surface.json`, `h72_lane_dots.json`, `h72_uniqueness.json`, `h72_not_union.json`, `h72_reasoning.json`, and the per-dot CSV above. The state file `work/h72/state.json` is terminal `negative-stop`; do not rerun or retune this candidate. No selector decision, TIFF build, portal validation, upload, or merge was part of H72.
