# H97-A — results, limits, and disposition

**Verdict: NEGATIVE. No competition GeoTIFF was written. OK to download: NO (there is no H97 TIFF). OK to submit: NO. No slot was selected or spent.** The literal final-dot uniqueness stop was obeyed; this result is not an organizer score and no H97 leaderboard result exists.

H97-A was the sole proposal run this round, within the two-hour cap. H97-B/C/D remain ranked, unrun hypotheses in [`knowledge/97_hypotheses_H97_preregistered.md`](97_hypotheses_H97_preregistered.md). Planning ranges in that document are priors, not scores. The run card is [`evidence/h97_run_card.json`](../evidence/h97_run_card.json); staged receipts are under `evidence/h97_*.json`.

## Matched protocol and view separation

- The shared H82/H84 mask was rebuilt exactly: **4,593,171 eligible pixels** and **53,186 withheld positives**, with fold truth counts `[27,309, 10,677, 6,813, 8,387]`. The 80-pixel buffered, whole-component spatial folds and shared `gems52-pooled-hide-v1` evaluator were used. H96's 60,894-positive mask is not comparable and was not used.
- The evaluator masks visible catalogue faults pixel-exactly, derives catalogue features from visible faults only, and reports pooled distance-weighted Tversky with α=0.2, β=0.8 and a 300 m triangular kernel. It is the shared holdout/writer, not a private fork. Implementation hashes are in `evidence/h97_holdout.json`.
- View A remained geophysical and included the two registered magnetic tilt-depth channels; View B remained strictly surface/radiometric with DVA2/HVA/COH channels only for elevation and elevation-slope bands. The H84 `B_DVA2` historical incumbent is **not** a pure-B H97 feature set: its mixed-view channel bank includes gravity/depth bands as well as elevation/slope. It was refit only as a clearly disclosed incumbent control.
- The same-run H84 refit used the exact H97 mask and reproduced the historical project-reported H84 value within the frozen 0.001 tolerance. That reproduction validates the comparison setup; it does not turn the historical value into an organizer score.

## Canary, sufficiency, independence, and exchange decision

The leakage canary checked 157 features. Maximum direction-insensitive out-of-quadrant AUC was **0.6707506** (alarm threshold 0.90): **PASS**.

| Fold | View A OOF AUC | View B OOF AUC |
|---:|---:|---:|
| 0 | 0.5084 | 0.6758 |
| 1 | 0.5966 | 0.7824 |
| 2 | 0.4447 | 0.6455 |
| 3 | 0.4906 | 0.7117 |
| **Mean / minimum** | **0.5101 / 0.4447** | — |
| **Required for A sufficiency** | **mean ≥0.60 and every fold ≥0.55** | — |
| **Result** | **FAIL** | — |

Spatial-block OOF error-correlation measurement ran over 2,089 blocks and 4,095,103 labelled-negative proxy predictions. Maximum absolute correlation was **0.09666** (the frozen stop threshold is 0.60), but these catalogue-zero pixels are proxies, not verified fault absence, and weak error correlation is not proof of conditional feature independence. Most importantly, passing the correlation screen cannot override View-A's failed sufficiency screen. **Conditional pseudo-label exchange was abandoned; `pseudo_label_training_used=false`.**

## Tilt-depth feature diagnostic

The registered rasterized nearest-contour proxy yielded **5 +45° threshold cells and 5 −45° threshold cells**. Those counts are disclosed and are not treated as connected contours. The depth-proxy distribution saturated at its 5,000 m cap: p50 = p95 = p99 = maximum = **5,000 m**. The proxy therefore did not produce a resolved depth distribution on this grid; it is not a validated inversion or ground-truth source depth. The zero-proximity channel remains a feature, but the sparse contours and capped proxy are a physical/method limitation, not evidence for a buried fault. See `evidence/h97_tilt_depth.json` and IR-H97-001.

## HOLDOUT-DTI results

**Every value below is HOLDOUT-DTI**, from evaluator `gems52-pooled-hide-v1`, on **53,186 withheld positives**, with paired physical-spatial-cluster percentile 95% confidence intervals (153 clusters, 1,000 draws, seed 61,052). They are project-evaluated holdout estimates, **not organizer-confirmed scores and not leaderboard projections**.

| Arm | HOLDOUT-DTI [95% CI] |
|---|---:|
| H97-A aligned-disagreement candidate | **0.1862646 [0.1648063, 0.2075371]** |
| Strict single View B, before exchange | 0.1865196 [0.1648984, 0.2080149] |
| Strict single View B, after exchange | 0.1865196 [0.1648984, 0.2080149] |
| Single View A, before / after | 0.0723396 [0.0563326, 0.0889441] |
| Union-max, before exchange | 0.1571029 [0.1357191, 0.1782365] |
| A-only disagreement | 0.0175894 [0.0127715, 0.0232973] |
| Same-mask H84 `B_DVA2` refit control | **0.1928308 [0.1707905, 0.2136956]** |
| Random | 0.0804256 [0.0702226, 0.0909733] |

The historical project-reported H84 control is **0.1928291**; the same-mask refit is **0.1928308**, absolute difference **1.73×10⁻⁶** (tolerance 0.001; reproduction PASS). The H97 candidate minus the same-run H84 control is **−0.0065662**, paired 95% CI **[−0.0151041, +0.0002708]**. It is below the historical bar and the paired interval does not clear zero. The primary promotion gate therefore **fails**. The candidate minus strict single-B difference is **−0.0002550**, 95% CI **[−0.0007003, +0.0000384]**. The candidate does not demonstrate incremental improvement over the strong strict-B baseline.

## Surface and final-dot lane; why no TIFF exists

The frozen 526-entry/50-repository prior census was restored and verified before lane checks: 526/526 Git blobs, 524/524 eligible aligned raster hashes/shape/CRS, zero restore errors. Including local artifacts and documented downloads, the checks covered **703 aligned/registered raster paths** with zero registry errors.

1. **Surface-before-placement: PASS.** Maximum registered Spearman correlation was **0.4725123**, below the strict 0.90 stop.
2. **Final dots: DUPLICATE/STOP.** The 37,654-dot audit placement has maximum literal fraction within 3 px of a registered prior of **1.0000**, exceeding the 0.70 stop. This is not only a universal-coverage-probe artifact: the secondary informative-prior audit (689 informative priors, with 14 broad-coverage probes excluded for diagnosis only) also returns **DUPLICATE/STOP**, with maximum within-3-pixel fraction **0.9229** against the GEMSDOE22 H23-B 10%-emission raster; that prior's 3 px support covers only **0.5328** of the eligible footprint.
3. **View contribution diagnostic.** The emitted placement is exactly equal to the strict single-View-B placement (`equal_single_B=true`, Jaccard 1.0). It is not equal to and is not a subset of the `max(A,B)` union placement (`equal_union=false`, `subset_of_union=false`, Jaccard 0.4012), so the registered candidate-vs-union criterion **passes**. Single-B equality is reported separately: the candidate placement shows no incremental A-only disagreement contribution at the fixed 37,654-dot budget. These facts are not conflated.
4. **Reasoning table.** No A-only final dots were emitted, so `docs/downloads/h97-a-only-reasoning.csv` has zero data rows. There is no A-only geological claim to promote.

No TIFF or ZIP exists in `submission/` or `docs/downloads/` for H97. `evidence/h97_write.json` records `artifact_written=false`, `download_ok=false`, `submit_ok=false`; the run card records no name/hash and no slot use. The lane stop is not waived. **Do not create a duplicate TIFF after the fact or upload one.** The feed-owned `docs/data/submission.json` continues to point to the prior H96 research-only file (`approved_for_weekly_slot=false`, slots used 0); it was not repointed to H97 because H97 has no artifact and no selection.

### Audit correction to the union diagnostic

A first draft of the stored build receipt had set `not_union_pass=false` whenever the placement equalled a single view. That was stricter than the preregistered candidate-vs-union test. It has been corrected deterministically from the already-recorded comparisons: `not_union_pass` means only “not identical to and not a subset of the union-max placement”; the exact single-View-B identity is a separate diagnostic. The corrected build receipt explicitly records the interpretation change. **No model was refit, no dots were re-placed, and no score or lane result changed.** The run remains negative because the holdout gate and final-dot uniqueness gate fail.

## H33-2-B2, leaderboard, and provenance caveat

The GEMSDOE32 owner-maintained page describes H33-2-B2 as its main artifact and gives a **projected 0.2747**, while explicitly saying that there is no organizer score receipt. A projection is not a score. The public DrivenData board is team-level and does not link a row to a filename or hash, so the file-to-score attribution between the H33-2-B2 artifact and the `extradr19` **0.2778** row remains **unresolved**; do not call 0.2778 an H33-2-B2 organizer score.

The archived 2026-10-10 snapshot (also the earlier 2026-10-11 observation supplied for this round) showed **#1 0.3774** and **#8 0.3195**. A live public-page reread later on 2026-10-11 showed #1 had moved to **0.4133**, while DARD remained #8 at **0.3195** and `extradr19` remained at **0.2778** but moved from #22 to #23. The selected rows are preserved in [`registry/leaderboard_snapshot_2026-10-11.json`](../registry/leaderboard_snapshot_2026-10-11.json); the full archived 2026-10-10 snapshot is [`registry/leaderboard_snapshot_2026-10-10.json`](../registry/leaderboard_snapshot_2026-10-10.json). These are volatile, team-level **PUBLIC-BOARD** observations, not scores for any particular file and not evidence that H97 beats the board.

## Three-pass review, tests, and next action

The three completed review passes are recorded in [`knowledge/99_h97_three_pass_review.md`](99_h97_three_pass_review.md) and [`evidence/h97_review_passes.json`](../evidence/h97_review_passes.json). The regression tests cover preregistration pins, strict View-A/View-B channel separation, tilt proxy semantics, disagreement formula, pseudo-label row handling, full-inventory fail-closed behavior, corrected not-union semantics, and no-artifact run-card fields.

The complete suite is recorded after the final docs/code edits in the H97 review evidence. H97-A is closed as a negative result; do not run H97-B/C/D under this registration, alter the failed gates, choose a slot, or treat a planning prior as a score. Any new strategy requires a separate preregistration and fresh budget decision.

## References

- Official DrivenData metric and submission-format page: <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>.
- Official DrivenData public leaderboard: <https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/>.
- Official USGS GeoDAWN airborne magnetic/radiometric survey release: <https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and>.
- Salem et al. (2007), “Tilt-depth method: A simple depth estimation method using first-order magnetic derivatives,” DOI <https://doi.org/10.1190/1.2821934>.
- Blum & Mitchell (1998), co-training, DOI <https://doi.org/10.1145/279943.279962>. This supports the method's assumptions, not evidence that H97 satisfies them.
- Owner-maintained H33-2-B2 project page (not an organizer receipt): <https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html>.
