# 97 · H97 hypotheses and frozen protocol — view-pure radiometric DVA co-training

**Written and frozen before any H97 channel was computed or any H97 learner was fitted (2026-10-10 UTC).**
Lane: the standing brief's two-view co-training paragraph. This round follows the next action in
`knowledge/96_h96_results_and_limits.md`: keep H96's disagreement exchange but give the surface learner
the directional-anisotropy signal that made H82/H84 strong. It also fixes a view-separation defect in
those older rounds: H82's arm called `B_DVA2` included gravity and depth-to-basement channels. H97 puts
those channels in View A and keeps only DEM/radiometrics in View B.

"Expected DTI improvement" below is an **ordinal prior (high/medium/low), not a score or projection**.
No weekly submission slot is authorized by this document.

## 1. Candidate hypotheses ranked before implementation

| rank | id | specific layers | physical signature / transform | why it can find a fault missing from the USGS/INGENIOUS catalogue | difference from this repository's prior work | expected value / cost | viability |
|---:|---|---|---|---|---|---|---|
| **1** | **H97-RDVA — view-pure directional anisotropy + one weighted disagreement exchange** | **A:** competition bands 13 isostatic gravity, 15 depth to basement, 18 gravity horizontal gradient, plus the shared potential-field/strain/seismicity features. **B:** bands 12 detrended DEM, 19 detrended slope, band 6 total-count-by-byte-content, and GeoDAWN K/Th/U/TC. | Eight-direction local semivariograms at 100, 200, 300, 400 and 600 m; `(max γ − min γ)/(max γ + min γ)` and `log10(mean γ)`, Gaussian support σ=300 m. One A↔B exchange uses only whole A-confident/B-abstaining or B-confident/A-abstaining components, inside 5 km blocks and outside an evaluation/held-fault/400 m visible-fault buffer. Donated positives have sample weight 0.25 to limit bias amplification. | A concealed basin fault can offset basement and density/susceptibility structure with no DEM scarp (A-only). A permeable altered zone can make a linear K/Th/U texture even where a public trace stops; this gives B a surface-geochemistry cue not requiring a mapped fault. The exchange is driven by disagreement rather than the union. | H82/H84 computed DVA/HVA on DEM **and** gravity/cover in one learner and did not exchange pseudo-labels. H95 exchanged pseudo-labels but had no DVA channels. Repository grep found no directional-semivariance transform of the radiometric grids. H97 is the first strict A/B split with radiometric DVA and actual exchange. | **highest / medium** | **Primary; run now.** All bytes are already restored and SHA-pinned. |
| 2 | H97-GRAFT — H84 DVA2/HVA field with H96 buried boost/artifact veto | Existing H84 DVA2/HVA field; H96 pre-A/pre-B disagreement | Rank-calibrated A-only boost and B-only veto on the already fitted H84 surface | Keeps H84's high catalogue-recovery field while reserving support for cover-buried faults | H96 used generic slope/curvature ranks, not H84's field | medium / low | Viable, but H84 measured HVA below DVA2 and the old field mixes views; not selected. |
| 3 | H97-ART — road/drainage orientation veto | DEM/slope local orientation, H84 `THETA_det_elev_l2`, slope aspect; B-only candidates | Downweight cardinal section-line roads and fall-line erosion/rills; retain non-cardinal persistent lineaments | Removes named B-only false processes without suppressing A-only buried structures | H77cond/H84 wrote orientation diagnostics, but no learner or emitted-field veto used both cardinality and fall-line alignment | medium / medium | Viable from cached layers; deferred by the three-experiment/two-hour budget. |
| 4 | H97-T2M — 2 m temperature as a thermal surface/subsurface bridge | INGENIOUS GDR 1391 “2m Temperature Probes”, DOI 10.15121/1881483 | Robust local thermal residual and along-strike thermal-gradient edge | Advective leakage can persist above a blind permeable fault without a mapped scarp | No repository round has used the probe table | potentially high / medium | **Not viable here:** `gdr.openei.org` is outside the sandbox allowlist and this manifest does not contain the table. It requires the free official file, an organizer/source filename, and a SHA-256 pin before preregistration. |

Named non-fault processes for the selected hypothesis: lithologic or intrusive contacts (potential-field
and radiometric edges without fault displacement), basin-margin facies changes, radiometric flight-line
or interpolation striping, differential compaction, palaeochannels, roads, and erosion/rills.

## 2. Frozen views and channels

The shared feature store is `work/r2/features`, produced by `gems52.structural.build` and extended once by
`python -m gems52.external`. It is reused; H97 does not fork it.

* **View A (geophysical/subsurface):** `view_A_with_external` plus DVA2 channels for bands 13, 15 and 18.
* **View B (surface):** `view_B_with_external` plus DVA2 channels for bands 12 and 19 and new DVA2
  channels for GeoDAWN K, Th, U and total count (bands 1–4 of `geodawn_rad_u8.tif`). Band 6 remains in
  B only because its bytes are nearly rank-identical to GeoDAWN total count, although its competition
  tag calls it magnetic; this unresolved metadata conflict remains an irregularity, not an invented fact.
* **No channel is in both views.** No catalogue-derived value is a learner input. Fold-visible labels are
  used only as training labels and to define the legal collar; withheld segments never contribute to a
  training feature.

The DVA operator is imported from `scripts/run_h82.py`: eight offsets
`(0,1),(1,1),(1,0),(1,-1),(1,2),(2,1),(2,-1),(1,-2)`, lags 1/2/3/4/6 pixels,
σ=3 pixels, exact offset-length normalization, support-normalized smoothing. Each source produces ten
channels (`aniso` and `logvar` at five lags). Radiometric values are standardized only over the fixed
eligible footprint; this transform is label-free.

## 3. Frozen experiment and leakage controls

This is **one frozen experiment with attribution arms**, not a threshold search.

1. Fit H61's `HistGradientBoostingClassifier` independently to A and B for each of the four
   `label-blind-quadrants-v2` folds. Train only outside the held quadrant and an 80-pixel buffer.
2. Test every added DVA channel alone on the held-out positives versus far catalogue-zero proxies.
   Direction-insensitive AUC **> 0.90 is a leakage alarm** and makes the verdict negative.
3. Correlate A/B spatial-block OOF errors on the exact same labelled negatives with
   `gems52.spatial.negative_block_errors` and `independence`. If max |Pearson or Spearman| **≥ 0.60**,
   abandon exchange; `cotrain_B_RDVA` becomes the unexchanged B field and the verdict is negative.
4. If allowed, do exactly one bidirectional exchange. Donor rank ≥0.95; receiver rank in [0.35,0.65];
   whole 8-connected segments only; minimum 5 pixels; maximum 2,000 pixels per direction/fold; every
   component must lie wholly in one 50×50-pixel block and wholly in the fold training domain. The
   forbidden mask is the held/evaluation region, every held component, every catalogue pixel, and the
   4-pixel collar around the fold-visible catalogue. Donated positives receive weight **0.25**; no second
   round and no post-result retuning.
5. Hide-and-recover arms at an exactly matched 9,400 placed dots/fold, 3-pixel minimum spacing and a
   200 m fold-visible-catalogue collar: `single_A_RDVA`, `single_B_RDVA`, `cotrain_B_RDVA` (**primary**),
   `union_pre`, `Aonly_pre`, and `random`.
6. Score pooled distance-weighted Tversky with shared `gems52.evaluate_holdout`, α=0.2, β=0.8,
   300 m triangular kernel, and 1,000 paired 20 km spatial-cluster bootstrap draws.

**Promotion gate:** primary HOLDOUT-DTI must be strictly above **0.1928290705**, the current measured
HOLDOUT-DTI best (`evidence/h84_holdout.json`, 53,186 withheld positives), and the paired 95% CI for
primary minus `single_B_RDVA` must have lower bound >0. Canary, independence, surface lane, final-dot
lane, decoded uniqueness, not-the-union and format gates must all pass. Otherwise verdict **negative**,
SUBMIT NO, zero slots used. The 0.192829 result itself had a failed reproduction control in H84; H97
reports that caveat and still uses the larger observed value as the conservative bar.

The final research artifact, even after a negative holdout, is fixed as the stitched out-of-fold primary
field outside a 200 m full-catalogue collar, 25,400 binary dots, 3-pixel spacing. The 25,400 mass is the
predeclared H96 mass lever; it is **not** selected after looking at H97 results. It must be written through
`gems52.submission_writer`, all finite and in [0,1].

## 4. Lane, uniqueness, union and reasoning gates

* Before placement, Spearman rank correlation of the stitched primary surface is checked against every
  locally available prior. Any one >0.90 is `DUPLICATE/STOP`.
* After placement, any one informative prior with >70% of H97 dots inside its 3-pixel halo is
  `DUPLICATE/STOP`. Universal-coverage probes are reported literally; they do not become evidence that a
  particular method is the same, but the literal result is never hidden.
* Decoded-pixel identity, Jaccard, and literal-prior-union checks use `gems52.gates`.
* “Not merely the union” compares the candidate with the equal-budget union of A-only and B-only spaced
  placements and with each view. Equality or Jaccard ≥0.99 fails.
* The reasoning CSV contains **every final emitted A-confident/B-abstaining cell** and names measured
  signatures and alternatives. A second CSV contains every donated A→B whole segment. These are Phase-2
  hypotheses, never verified faults.

## 5. Budget and evidence labels

Maximum: three experiments or two hours; this protocol uses one fit/holdout experiment, one build/gate
experiment and one verification pass. No DrivenData upload occurs. Every model number is labelled
**HOLDOUT-DTI** with evaluator version, 53,186 expected withheld positives and a 95% CI; leaderboard
numbers are copied only from dated repository snapshots and are not filename-authenticated.

## 6. Sources and verification status (as known before fit)

| source | verification in this sandbox | manual-review link |
|---|---|---|
| DrivenData reference solution | GitHub repository cloned at commit `aebe92f7c8a990f0e3443451b7a825d9afd6336b`; its notebook normalizes features to [0,1], uses Tversky α=0.2/β=0.8, and writes one GeoTIFF layer using the labels raster CRS/transform. It is a baseline, not this method. | https://github.com/drivendataorg/gems-prize-reference-solution/commit/aebe92f7c8a990f0e3443451b7a825d9afd6336b |
| Blum & Mitchell, COLT 1998 | Bibliographic claim supplied by the brief; DOI host cannot be fetched from this allowlist. The implementation tests the two assumptions the brief names rather than asserting them. | https://doi.org/10.1145/279943.279962 |
| Competition inputs | Restored from owner mirrors and matched `registry/data_manifest.json` byte counts and SHA-256. This proves mirror integrity, **not organiser authentication**. | https://www.drivendata.org/competitions/306/competition-doe-gems/data/ |
| GeoDAWN radiometrics | Local derivative SHA-256 `c22420f75999030d7cc65c9e31e50d232ea6158423bca051613a18a8b20ba682`, grid-aligned, manifest says derived from USGS DOI 10.5066/P93LGLVQ. Official USGS host cannot be fetched here. | https://doi.org/10.5066/P93LGLVQ |
| Submission grid | Local sample bytes: EPSG:32611, 3730×3292, 100 m cells, transform `(100,0,243350,0,-100,4508550)`; the writer must match it exactly. | https://epsg.io/32611 |

## 7. Pre-fit answer to the 0.2778 question

The repository bytes and owner-reported nested scores support a metric explanation, not a geological
proof: `h33-2-b2` has 37,654 3-pixel-spaced binary dots and removes the 100–200 m catalogue flank from a
44,090-dot parent. Under the documented zero-credit approximation for those removed pixels, the two
scores imply hidden mass ≈14,089 and kernel credit ≈5,223. The improvement 0.2600→0.2778 is therefore
consistent with removing false-positive mass while retaining credit. The filename-to-0.2778 link is
owner-reported, not organiser-authenticated. At the same 37,654 mass, 0.3195 requires roughly 15% more
kernel credit and 0.3774 roughly 36% more than the 0.2778 file. Those are arithmetic targets, never
predicted H97 scores. H97 can honestly claim an expected gain only if the frozen holdout gate passes.
