# 97 · Hypotheses H97 (preregistered, frozen before any fit) — 2026-10-10

Lane (the standing brief's single method paragraph, verbatim in `knowledge/94`): **two-view
co-training between a geophysical view (A) and a surface view (B), with disagreement as the
discovery signal** (Blum & Mitchell, *Combining Labeled and Unlabeled Data with Co-Training*,
COLT '98, pp. 92–100, doi:10.1145/279943.279962).

This round asks two questions that the previous eight co-training rounds in this repository
(H56, H57, H59, H61, H62, H63, H87, H88/H96) never asked, and it is written so that either answer
is a deliverable.

Nothing below is a score. Every number produced by this round is labelled **HOLDOUT-DTI**
(evaluator version, withheld positives, 95 % CI) or **OWNER-REPORTED** (copied from the owner's
submission-page receipts in `knowledge/75`), never "ORGANIZER-CONFIRMED" unless a submission-page
receipt is quoted verbatim.

Inputs: the integrity-pinned mirrors restored by `scripts/restore_data.py` (receipt
`data/restore_receipt.json`, ALL_VERIFIED = True this session). Pinned, **not**
organizer-authenticated, because the DrivenData data tab is login-walled:
<https://www.drivendata.org/competitions/306/competition-doe-gems/data/>.

---

## E1 — Instrument fidelity: does our holdout rank the board's own scored files?

**Hypothesis.** The pooled catalogue hide-and-recover instrument
(`gems52-pooled-hide-v1`, whole-component quadrant folds, visible catalogue masked pixel-exactly)
scored on the twelve OWNER-REPORTED prior rasters **as they were submitted** (`as_is`, no budget
cutting — `gems52.holdout.arm_scores`) is **not** rank-correlated with those files' board scores,
because the instrument's positives are *catalogue* pixels hidden from the fold, while the board's
`|G|` is the *off-catalogue* hidden population (`knowledge/76` §5: the surface detector keeps 7 %
of its skill off-catalogue).

**Falsifier.** Spearman(board score, HOLDOUT-DTI) ≥ 0.50 over the twelve files. If it is ≥ 0.50 the
instrument tracks the board and the frozen bar is board-validated; if it is < 0.50 the bar is
instrument-local and any "beat the bar" claim is a statement about catalogue recovery only.

**Named non-fault process that could mimic the result.** Mass. The board's own history shows
Spearman(emitted mass, board score) = −0.928 (`knowledge/76` §4). A holdout instrument that also
punishes mass can appear "correlated with the board" through mass alone. Therefore E1 reports
(a) the raw rank correlation, (b) the partial correlation of board score and HOLDOUT-DTI
controlling for log mass, and (c) the correlation of board score with mass in this same twelve-file
set. A conclusion is drawn only from the partial.

**Controls.** `random` at 37,654 dots and at 25,400 dots under the same placement rule
(`gems52.nodes.spacing_select`, 3 px minimum separation, 200 m catalogue collar), same folds.

**Cost.** One pass over four folds; no fit.

---

## E2 — Co-training at the metric-implied budget, with the surface view at full channel width

**Why this is not a re-run of H96.** H96's `single_B` composite used five unfitted channels
(slope, ridge curvature, topo edge, K/Th, total count) and scored 0.0527 while the *fitted* H61/H84
View B on the same lane scores 0.1746–0.1928. H96's own note
(`AGENTS.md`, H96 block) is that the signal it measured was "the View-A prior, not the disagreement".
E2 therefore changes exactly one thing relative to H96 and keeps everything else frozen: **View B
gains the surface channels the certified-best fitted instrument actually uses**, namely the
LiDAR-scarp layers (`data/external/lidar_scarp_features_u8.tif` bands 1, 3, 7, 9, 10) and the
GeoDAWN radiometric ratio grids (`data/external/geodawn_extensions_u8.tif` bands 1–3), and the
emission is the **metric-implied mass lever** instead of a full-width top-k.

**Hypothesis.** At the metrics-implied budget the disagreement stratum carries more credit per
emitted pixel than the consensus stratum and than View B alone, so a **disagreement-stratified,
mass-levered** emission beats (a) `single_B`, (b) `cons_only` and (c) `random` on the pooled
instrument, with paired 95 % CI lower bound > 0, and reaches the frozen promotion bar 0.190147
(H84 `B_DVA2_HVA`, `evidence/h84_holdout.json`).

**Mechanism.** Concealed normal faults offset basement beneath alluvial cover: potential-field
edges (gravity/magnetic horizontal gradients), cover-thickness steps, shear-strain steps and
seismicity lineations register in View A while DEM curvature and slope see no scarp; radiometric
ratios and LiDAR scarp layers are the only surface channels that respond to a *buried* trace.

**Named non-fault processes that could mimic it.** Lithologic contacts and intrusive margins
(potential-field edges with no fault offset); basin-margin facies steps (cover-thickness steps with
no faulting); paleo-channels; aftershock clusters; road cuts and erosion lines (the B-only
population, vetoed); and DEM/radiometric acquisition seams.

**Frozen arms (per fold, both budgets).**

| arm | ranking field |
|---|---|
| `cotrain_dis` **(primary)** | `(0.45·cons + 0.55·buried)·(1 − 0.70·veto_B_only)` — identical functional form to H96's amended veto, so the *only* difference from H96 is the View-B channel set |
| `cons_only` | A·B |
| `buried_only` | A·clip(A−B, 0, 1) |
| `single_B` | View B composite |
| `single_A` | View A composite |
| `random` | uniform on the allowed set |

**Budgets.** matched 9,400 dots per fold (37,654 total, the family's standard) and the
**metric-implied mass lever 6,350 dots per fold (25,400 total)**, derived in `knowledge/76` §3 from
`DTI = T/(0.2·S + 0.8·|G|)` at the 0.3195 target: 0.3195 at the champion's credit needs
S ≈ 25,384 px.

**Frozen gates (all must pass for a promote verdict).**

| gate | threshold | source |
|---|---|---|
| independence (spatial-block OOF negative errors) | abandon if max abs ρ ≥ 0.60 | `registry/h84_preregistration.json` |
| leakage canary (single channel, out-of-quadrant AUC) | alarm if ≥ 0.90 | same |
| promotion | paired CI95 lower of (primary − best control) > 0 **and** primary ≥ 0.190147 | H84 bar |
| format | 1 band float32, EPSG:32611, 3730×3292, transform == `sample_submission.tif`, 0 NaN, 0 inf, values in [0,1] | problem page §submission-format |
| uniqueness | identical to none of the registry priors | standing brief |
| lane surface | max Spearman vs registry rasters < 0.90 | standing brief |
| lane dots | ≤ 70 % of dots within 3 px of any single registry raster | standing brief |
| not the union | Jaccard vs (spaced A-top-k ∪ spaced B-top-k) < 0.50 | standing brief |

**Emission (only if a gate-compliant field exists; otherwise the round is a negative deliverable).**
Binary {0,1}; **all-finite container, `nodata` tag None** — the champion's own container
(`knowledge/76` §1), which cannot fail the portal's literal *"Predicted values must be in range
[0,1]"* test; 3 px minimum separation (`gems52.nodes.spacing_select`, the repo's metric-aware
placement); 200 m catalogue collar (the champion's measured discipline: minimum distance from an
emitted pixel to the mapped catalogue 223.6 m); values normalised to [0,1] before binarisation.

**Budget.** 3 experiments (E1 instrument, E2 co-training holdout, E3 gates/write), 2 hours,
**0 submission slots** — promotion is a separate selector step.

**What would make this round a negative.** If the primary fails its paired CI, or the independence
gate abandons, or the canary alarms, or any format/uniqueness/lane gate fails, the round is
**negative**, and the file is published with **OK TO DOWNLOAD: YES / OK TO SUBMIT: NO**, which the
standing brief counts as a deliverable.

---

## Provenance of the numbers quoted above

| claim | source |
|---|---|
| DTI = TPw/(TPw + α·FPw + β·FNw), α 0.2, β 0.8, R = 300 m, triangular kernel | organizer page <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric>, transcribed in `src/gems52/metric.py`, pinned by `tests/test_metric.py` |
| submission format (EPSG:32611, 100 m, single band, float32, values in [0,1], NaN outside) | same page, §submission-format |
| champion `h33-2-b2` scored 0.2778, mass 37,654, container all-finite | `knowledge/76` §1 + the owner's receipt |
| mass lever S ≈ 25,384 for 0.3195 | `knowledge/76` §3, arithmetic on the published metric |
| Spearman(mass, board score) = −0.928 | `knowledge/76` §4 |
| off-catalogue skill retention ≈ 7 % | `knowledge/76` §5 (`gems52-offcatalogue-v1`) |
| H84 bar 0.192829 / 0.190147 | `evidence/h84_holdout.json` |
| H96 `single_B` 0.0527, independence 0.0965 | `evidence/h96_holdout.json` |
| Blum & Mitchell COLT '98 | doi:10.1145/279943.279962 |
