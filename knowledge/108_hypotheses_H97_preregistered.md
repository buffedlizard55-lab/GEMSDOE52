# 97 · H97 pre-registration — disagreement graft onto the strongest measured surface learner (frozen before the graft is scored)

Status: FROZEN before any graft field is computed. Hash pinned in `registry/h97_preregistration.json`.
Runner: `scripts/run_h97.py` refuses to start if this file's SHA-256 moves.
Lane: co-training between a geophysical view and a surface view, disagreement as the discovery signal
(Blum & Mitchell, COLT 1998, doi:10.1145/279943.279962).

## Why this round exists

* H96 (knowledge/96) measured bidirectional disagreement on the *weak* H61 View B learner and found the
  field at random level. Its own diagnosis: the signal came from the View-A prior, not from the disagreement.
* H84 (`registry/h84_preregistration.json`) measured the strongest surface learner in this lane,
  `B_DVA2_HVA`, at HOLDOUT-DTI 0.190147, the promotable bar.
* H97 grafts the H96 disagreement formula onto the H84 learner. It needs no new learner fit: it uses the
  already-frozen per-fold predictions of two H84 arms (`single_A`, `B_DVA2_HVA`).

## Views (unchanged from H84; no new channels)

* View A (potential field and subsurface): H84 `single_A` learner over the View-A store columns.
* View B (surface): H84 `B_DVA2_HVA` learner (DVA-2 directional variogram channels + HVA ellipse channels
  over DEM/elevation/slope/gravity-gradient/radiometric bands, `gems52.structural` store).

## Graft formula (weights copied from H96, not tuned)

For each fold, on the fold's allowed cells (`gems52-pooled-hide-v1` mask, ring excluded):

* a = rank01(single_A prediction), b = rank01(B_DVA2_HVA prediction), both in [0, 1].
* consensus = a·b
* buried = a·clip(a − b, 0, 1)            (A confident, B abstains: buried-fault candidate)
* veto = rank01(clip(b − a, 0, 1))        (B confident, A abstains: surface-artefact suspect)
* **field = (0.45·consensus + 0.55·buried)·(1 − 0.70·veto)**

## Arms (all scored on the same folds and budget)

| arm | definition | role |
|---|---|---|
| `B_DVA2_HVA` | b alone | control, must be the H84 primary |
| `single_A` | a alone | View-A-only control |
| `graft_primary` | the field above | candidate |
| `consensus_only` | a·b | decomposes the graft: is the disagreement term adding anything beyond agreement? |
| `random` | uniform random on allowed cells | floor |

## Budget, placement, emission

* 9,400 dots per fold per arm (37,600 total, matching the H84 shipped budget 37,654 with the H84 fold
  remainder). Placement `gems52.nodes.spacing_select`, minimum spacing 3 px. Catalogue collar 200 m (2 px
  at 100 m) masked pixel-exactly. Emission binary {0,1}, outside footprint 0.0, no NaN.

## Decision rule (frozen)

* Controls must reproduce: `B_DVA2_HVA` measured HOLDOUT-DTI within 1e-3 of the committed H84 value 0.190147.
  If not, the round is void (no decision), and the discrepancy is an irregularity.
* **Promote-candidate** only if ALL of:
  1. `graft_primary` pooled HOLDOUT-DTI > 0.190147;
  2. paired 95 % CI lower bound of (`graft_primary` − `B_DVA2_HVA`) > 0;
  3. paired 95 % CI lower bound of (`graft_primary` − `consensus_only`) > 0 (the disagreement term must add
     something beyond agreement);
  4. leakage canary (single-feature out-of-quadrant AUC) below 0.90 on all channels (H84 canary receipt);
  5. literal surface lane PASS (max |Spearman| < 0.90 against every registry raster) AND dot lane PASS
     (literal, not policy: max share of dots within 3 px of any one registry raster < 0.70); AND validator
     PASS; AND uniqueness PASS (no identical raster; decoded pattern not in the registry).
* Otherwise: **negative**. A lane DUPLICATE is reported as DUPLICATE; it is not waived.
* Promotion to a real weekly slot is a separate selector step and is NOT made by this round.

## Leakage and independence guards

* Canary: each feature alone, held-out truth inside the allowed set, alarm at AUC >= 0.90 (reuse H84 fit receipt).
* Independence: H84 `stage_independence` receipt (spatial-block OOF error correlation, abandon at |rho| >= 0.60).

## Non-fault mimics named in advance (for the A-only reasoning and the reviewer)

Lithologic contacts and intrusive margins; basin-margin facies steps; paleo-channels; road cuts;
erosion lines and drainage incision; aftershock or induced-seismicity clusters. The graft's buried term
is the one most exposed to lithologic contacts; its veto term is the one most exposed to roads and erosion.

## Budget

Experiments: 1 (this graft, scored once). Hours: 2. Submission slots: 0.
