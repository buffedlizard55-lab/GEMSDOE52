# 98 · H97 results and limits — the instrument does not track the board, and the co-training signal does not resolve the hidden population

Round H97, 2026-10-10/11. Preregistered **before any fit** in
`registry/h97_masslever_preregistration.json` (SHA-256 `02668421f590ea8f4f13aa7052a4f3240beb410214db9ef80b7ac8a8e8f96703`
of `knowledge/105_h97_masslever_hypotheses_preregistered.md`, 8,801 bytes). One hundred per cent of the
numbers below are read back from receipts written by `scripts/run_h97_masslever.py`; where a number comes
from somewhere else it is named in the row.

| receipt | what it holds |
|---|---|
| `evidence/h97_masslever_folds.json` | the frozen fold set |
| `evidence/h97_masslever_instrument.json` | E1, the instrument-fidelity test |
| `evidence/h97_masslever_views.json` | the frozen View A / View B composites |
| `evidence/h97_masslever_holdout.json` | E2, the pooled hide-and-recover arms |
| `evidence/h97_masslever_build.json`, `evidence/h97_masslever_format_gate.json`, `evidence/h97_masslever_uniqueness.json`, `evidence/h97_masslever_lane_dots.json`, `evidence/h97_masslever_write.json`, `evidence/h97_masslever_run_card.json` | E3, the artifact and every gate re-read from the written bytes |

---

## 1 · E1 — the decisive result: our instrument is anti-correlated with the board

Every one of the twelve **OWNER-REPORTED** scored priors (the owner's submission-page receipts;
**not** organizer-confirmed, no receipt is quoted in this repository) was scored **exactly as it was
submitted** (`as_is`: no budget cutting, no re-placement, visible catalogue masked pixel-exactly) on
the frozen fold set, together with two random controls under the same placement rule.

| file (as submitted) | OWNER-REPORTED board score | **HOLDOUT-DTI** [95 % CI] | emitted px (whole file) |
|---|---|---|---|
| `h33-2-b2-zeros` (the champion) | 0.2778 | **0.006696** [0.0060, 0.0075] | 37,654 |
| `d2-8` | 0.2600 | 0.161564 [0.1489, 0.1751] | 44,090 |
| `d1-5` | 0.2477 | 0.171730 [0.1583, 0.1858] | 60,069 |
| `tgc-v2-on-d1-5` | 0.2449 | 0.172543 [0.1591, 0.1866] | 61,328 |
| `h19-5` | 0.1922 | 0.166160 [0.1522, 0.1798] | 121,131 |
| `h19-4` | 0.1894 | 0.167263 [0.1535, 0.1810] | 123,779 |
| `h16-1` | 0.1855 | 0.166685 [0.1527, 0.1806] | 123,939 |
| `h28-dotted-ridge` | 0.1839 | 0.371636 [0.3605, 0.3818] | 69,281 |
| `ens12-adopted` | 0.1563 | 0.229952 [0.2145, 0.2430] | 172,974 |
| `Hedge-v2` | 0.1563 | **0.665283** [0.6408, 0.6909] | 227,507 |
| `h25-ctx-ridge` | 0.1280 | 0.398814 [0.3827, 0.4139] | 174,232 |
| `r13-lattice-s5` | 0.0904 | 0.244653 [0.2335, 0.2553] | 206,895 |
| `2314b599` | 0.0107 | 0.046145 [0.0362, 0.0554] | 343,816 |
| `random` control @ 37,654 dots | — | 0.072429 [0.0655, 0.0795] | 37,654 |
| `random` control @ 25,400 dots | — | 0.050110 [0.0432, 0.0571] | 25,400 |

Evaluator `gems52-pooled-hide-v1`, 60,894 withheld positive px, 4 label-blind quadrants,
buffer 80 px, catalogue collar 2 px, 1000 bootstrap draws over 161 physical 20 km blocks, seed 97001.

* **Spearman(board score, HOLDOUT-DTI) = −0.4897** over the thirteen files.
* **Partial correlation controlling for log emitted mass = +0.1264** — i.e. **zero**.
* Spearman(board score, emitted mass) = **−0.9436**, independently reproducing the twelve-file
  figure −0.928 in `knowledge/76` §4 on thirteen files.

**Reading.** The instrument's positives are *catalogue* pixels; the board's `|G|` is the
*off-catalogue* hidden population the competition actually scores. A file that covers the survey
with a dense lattice (`Hedge-v2`) is rewarded by our instrument and scores 0.1563 on the board; the
champion deliberately avoids the mapped catalogue (0.74 % of its mass inside the 300 m kernel of
`labels.tif`, `knowledge/76` §1), scores 0.006696 on our instrument and 0.2778 on the board. The
two rankings are not merely uncorrelated, they are **opposed at the top of the ladder**.

**Consequence, stated in the preregistration before the numbers existed.** The frozen promotion
bar (H84 primary `B_DVA2_HVA`, 0.190147) is *instrument-local*: beating it is a statement about
catalogue recovery, and E1 measures that it is **not** a statement about the leaderboard. Every
"beat the bar" promotion decision this repository has made — including the eight co-training rounds —
was made on an instrument that does not rank the board's own files. That is the honest explanation
of the 0.2778-vs-0.19 gap that `knowledge/76` §5 left open, and it is the most useful result of this
round.

## 2 · E2 — the co-training arms at the metric-implied mass lever

Frozen arms, matched budget 9,400 dots/fold (37,654 total) and the metric-implied mass lever
6,350 dots/fold (25,400 total, `knowledge/76` §3). Independence: max |ρ| **0.0616** over the
block-level OOF negative errors (abandon threshold 0.60) → exchange allowed. Leakage canary: max
single-channel out-of-quadrant AUC **0.6190** (`scarp_upface_max`), alarm 0.90 → no alarm.
Whole-segment A-confident/B-abstain pseudo-label candidates: 114 segments, 1,997 px (counted, not
used — iterative exchange is a closed negative in this repository).

| arm | HOLDOUT-DTI, matched 9,400/fold | HOLDOUT-DTI, mass lever 6,350/fold |
|---|---|---|
| `cotrain_dis` (primary) | 0.069041 [0.0569, 0.0822] | 0.049286 [0.0391, 0.0605] |
| `cons_only` | **0.093310** [0.0767, 0.1081] | — |
| `buried_only` | 0.050026 [0.0375, 0.0630] | — |
| `single_B` | 0.058666 [0.0464, 0.0711] | 0.039622 [0.0304, 0.0498] |
| `single_A` | 0.074518 [0.0617, 0.0877] | — |
| `random` | 0.075717 [0.0665, 0.0860] | 0.053666 [0.0467, 0.0610] |

* Paired `cotrain_dis − cons_only` = **−0.024269** [−0.038071, −0.009208] → the disagreement/veto
  machinery **significantly hurts** relative to the plain consensus product.
* Mass lever: `cotrain_dis` 0.049286 is **below** the mass-matched random control 0.053666;
  paired −0.004380 [−0.016848, +0.008570] (spans zero).
* Frozen verdict: **negative** (`primary` 0.069041 < bar 0.190147, paired CI excludes zero in the
  wrong direction).

**What this adds to the eight previous co-training negatives.** H96's `single_B` composite scored
0.0527 with five unfitted channels. H97 gave View B the channels the *certified-best fitted* surface
instrument uses (LiDAR scarp bands 1, 3, 7, 9, 10 — coverage 26–32 % of the footprint — and GeoDAWN
radiometric ratio grids, coverage 42 %), i.e. the "graft the disagreement arm onto the strong surface
channels" repair that `AGENTS.md` named as H96's next step. The unfitted composite still lands at
0.058666, and the disagreement stratum still does not resolve the hidden population. **The layer
that lifts the surface instrument from ~0.06 to ~0.19 is the fitted learner (H61: 250-tree
HistGradientBoosting over the same channels), not the channel list**; a rank-weighted composite is
not a substitute, and this round measures that directly rather than assuming it.

## 3 · E3 — the artifact

* `submission/gems52-h97-cotrain-disagree-masslever-25400px-<stamp>-<digest>-zeros.tif`
  (see `evidence/h97_masslever_write.json` for the exact name, size and SHA-256).
* Container: single-band float32, EPSG:32611, 3730 × 3292, transform identical to
  `sample_submission.tif`, **nodata tag None, all pixels finite, values exactly {0, 1}** — the same
  container the champion used, and the one that cannot trip the portal's literal
  *"Predicted values must be in range [0,1]"* test (the failure the owner hit on a NaN-tagged file).
* Placement: `gems52.nodes.spacing_select`, minimum separation 3 px, 200 m catalogue collar,
  **25,400 dots placed exactly** (`evidence/h97_masslever_build.json`).
* Composition: 18,967 dots (74.67 %) are buried-dominant (View A favouring, View B abstaining),
  6,433 are consensus-dominant; Jaccard against the spaced top-k union of the two views is
  **0.0529**, with 21,581 dots outside that union → **not merely the union of the two views**.
* Lanes: surface (pre-placement) max Spearman **0.1155** → PASS; dots (post-placement) statistics and
  uniqueness are in `evidence/h97_masslever_lane_dots.json`, `evidence/h97_masslever_uniqueness.json` and the run card.
* Every A-only (buried-dominant) dot carries written geological reasoning, the named non-fault
  mimic, and an explicit falsifier in the adjacent `-a-only-reasoning.csv` (the Phase-2 duty).

## 4 · Limits, honestly

1. **No leaderboard claim.** HOLDOUT-DTI is a leave-the-catalogue-out recovery score. E1 measures
   that it does not rank the board's own scored files (Spearman −0.4897; partial | log mass
   +0.1264). Nothing in this round is predicted to score above 0.2778; the round does not certify
   a leaderboard gain.
2. **Two views, not two instruments.** Both views here are unfitted rank composites, so E2 tests
   the *disagreement machinery*, not the co-training theorem's sufficiency assumption (View A has
   failed sufficiency in ten fits now).
3. **Byte provenance.** All inputs are integrity-pinned mirrors (`data/restore_receipt.json`,
   ALL_VERIFIED=True, 23 files, 531 MB): pins prove mirror consistency, **not** organizer
   authentication, because the DrivenData data tab is login-walled.
4. **Registry is local.** The uniqueness/lane verdicts cover the 190+ aligned rasters accessible in
   this checkout plus the restored scored set; they are not a proof against unlinked private
   submissions.
5. **Budget deviation.** The standing protocol allows 3 experiments or 2 hours. Three experiments
   were run; E3's write stage was re-run twice after a `ValueError` on the 140-character note limit
   and a `KeyError` on a legacy uniqueness key name (both fixed in the shared runner, no private
   fork). Wall-clock exceeded 2 hours because the deliverable — a downloadable, validated TIF and
   its pages — was the session's highest-priority instruction. Slots used: **0**.

## 5 · Next work, ranked by expected value after E1

1. **Build a board-validated instrument.** Everything else is secondary: no round can certify a
   leaderboard gain while the only instrument available ranks the board backwards. The proxy the
   repository already has (`gems52-offcatalogue-v1`/`-b-v1`, SGMC faults ≥ 300 m from
   `labels.tif`) is the obvious candidate; it must be validated the way E1 validates this one
   (score the scored priors on it, require Spearman > 0.5 with the board).
2. **Then, and only then, re-open the model work:** the fitted surface learner over the LF/HVA
   channel families is the only measured lift this repository has (0.1746 → 0.1928), and the mass
   lever is the only board-measured lever (S ≈ 25,400 for 0.3195).
3. **The A-only stratum stays a Phase-2 deliverable, not a DTI bet:** it is emitted with reasoning
   (this round) because the brief demands it, but it has now scored below random on the catalogue
   instrument in three rounds (H93, H95, H97).
