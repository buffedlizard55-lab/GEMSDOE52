# 80 · H88 pre-registration — basement-step coherence on cover thickness (written before any H88 fit)

Date: 2026-10-10. Session branch: `arena/9d9926bc-gemsdoe52`. Experiment 1 of 3 in this session.
Source of the choice: `knowledge/78` §4 row 2 (H85-next-B) and `knowledge/79` (H86 ranking). Chosen because it is
the cheapest untested candidate that uses a layer already in the stack, with no new external data.

## 1. Hypothesis (one sentence)

A buried, basin-bounding normal fault offsets the top of basement, so the **depth to basement surface**
(band 15 `depth_to_base_surf`, tag "Depth to basement surface - thickness of sedimentary cover") shows an
**oriented, sustained step**: large gradient magnitude that is *coherent* (aligned along a line) over a
few hundred metres. A coherent step in cover thickness should mark a fault that has no surface trace.

## 2. Layers and signature

* Layer: band 15 of `data/training_features.tif` (EPSG:32611, 100 m, 19 float32 bands). Units are not stated in
  the file tags; they are taken as stored (checked and reported at run time, not assumed).
* Pre-smoothing: Gaussian σ = 2 px (200 m).
* Gradient: `np.gradient` of the smoothed field, magnitude `g` (depth units per px).
* Coherence: structure tensor of the gradient vector field, outer Gaussian σ = 4 px (400 m);
  `C = sqrt((Jxx−Jyy)² + 4Jxy²) / (Jxx+Jyy+ε)` in [0,1]. C near 1 means the gradients line up (a line),
  near 0 means they point in many directions (noise or a bowl).
* **Primary score** `S_step = g · C`, rank-normalised over the evaluation footprint to [0,1].

## 3. Arms (fixed now)

| arm | definition | role |
|---|---|---|
| `H88_step` | `S_step` | **primary candidate** |
| `H88_gradient_only` | rank(g) | ablation: is the coherence term doing work |
| `random` | seeded uniform (`SEED+500+fold`) on the same allowed set | control, same placement |
| `raw_depth_to_base` | rank(band 15) | canary channel (single raw layer) |

Placement for every arm: `gems52.nodes.spacing_select(field, allowed, 9400, min_px=3.0)` per fold,
the same as H85 and H82. Budget 9,400 dots per fold; 4 folds.

## 4. Instrument (reused, not forked)

* Folds: `scripts/run_h61.setup()` (label-blind quadrants, 80 m buffer, visible-catalogue collar).
* Allowed set: `run_h85.allowed_of(fold, ring_px)` = region ∖ visible ∖ 200 m visible collar.
* Evaluator: `gems52.evaluate_holdout` version `gems52-pooled-hide-v1` (α 0.2, β 0.8, 300 m triangular kernel),
  `pooled_summary` with 1,000 paired cluster-bootstrap draws, seed 61052.
* The field uses no catalogue and no label. Band 15 is raw feature data, so no label is read anywhere.
* Canary: single-channel AUC of each arm against held-out truth vs allowed negatives. Bar 0.90.

## 5. Decision rule (fixed now)

* **PASS (eligible for the slot selector, which is still the owner's decision):** `H88_step` point DTI >
  **0.189200** (H82 `B_DVA2`, the best arm this branch has measured on this instrument) AND the paired CI of
  (`H88_step` − `random`) has a lower bound > 0 AND the canary is clear (no channel AUC > 0.90).
* **NEGATIVE otherwise.** A negative result is a deliverable and is not a reason to change the rule.
* The rule is **not** tuned after seeing results. Any post-hoc change is recorded as a protocol deviation.

## 6. Prior expectation (stated so a null is not over-read)

The repo's own record (`knowledge/79`, `knowledge/78` §2) says structure-tensor and potential-field channels on this
instrument sit near random, and that H85 (structure linearity) scored below random. So the prior for PASS
is low. This is a test of a *new physical layer*, not a claim of improvement.

## 7. Named non-fault mimics (fixed now)

Basin-margin alluvial fans and their bounding fronts (a real cover-thickness step with no fault), lithological
facies boundaries in the basement, paleo-channel incisions in the cover, and DEM-to-basement interpolation seams.
These are the reasons a PASS would still need field or geophysical support before any geological claim.

## 8. Scope limits

* Holdout only hides *catalogue* faults. The competition scores *new* faults. A PASS on the holdout does not
  establish a competition score (AGENTS.md: holdout DTI and board are not correlated, Spearman −0.10).
* No organiser receipt exists for any file this session. Board numbers are owner-reported, not organiser-confirmed.
