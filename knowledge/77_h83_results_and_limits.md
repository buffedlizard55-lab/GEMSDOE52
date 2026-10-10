# H83 results, limits, and what the next session must not redo

Round: H83 / 2026-10-10. Lane: co-training View A (potential-field / subsurface) against
View B (surface DEM curvature + slope + radiometrics), with disagreement as the discovery signal.
Hypotheses: `knowledge/74_hypotheses_H83_preregistered.md`. Brief: `knowledge/75_...`.
Budget accounting: `knowledge/76_why_02778_and_what_beating_03195_requires.md`.

**Slots used: 0.** Verdict **negative**. Download **YES**, submit **NO – research artefact only**.

---

## 1. The measured result

| Instrument | Arm | DTI | 95 % CI |
|---|---|---|---|
| HOLDOUT-DTI `gems52-pooled-hide-v1` | `single_B` | **0.174571** | [0.152313, 0.196302] |
| HOLDOUT-DTI | `E3_single_B_quota` | 0.154456 | — |
| HOLDOUT-DTI | `union_max` | 0.149009 | — |
| HOLDOUT-DTI | `B_only` | 0.105356 | — |
| HOLDOUT-DTI | `random` | 0.080426 | — |
| HOLDOUT-DTI | `single_A` | 0.071954 | — |
| HOLDOUT-DTI | `disagreement_post` | 0.036988 | — |
| HOLDOUT-DTI | `A_only` | **0.033293** | — |
| paired `disagreement_post` − `single_B` (HOLDOUT) | | **−0.137583** | **[−0.161887, −0.113776]** |
| OFFCAT-DTI `gems52-offcatalogue-v1` | `E3_single_B_quota` | 0.090798 | [0.076792, 0.106536] |
| OFFCAT-DTI | `single_B` | 0.090632 | [0.078941, 0.102324] |
| OFFCAT-DTI | `union_max` | 0.089747 | [0.074431, 0.106858] |
| OFFCAT-DTI | `disagreement_post` | 0.065682 | [0.043691, 0.092752] |
| paired `disagreement_post` − `single_B` (OFFCAT) | | −0.024951 | [−0.049522, +0.002972] |
| OFFCAT-DTI `gems52-offcatalogue-b-v1` | `single_B` | 0.107456 | — |
| OFFCAT-DTI-b paired `disagreement_post` − `single_B` | | −0.050379 | [−0.071342, −0.023896] |

The frozen promotion rule is "lower bound of the paired CI against `single_B` > 0". It is
−0.161887, so H83 is **not** promoted. Both off-catalogue instruments point the same way: on `gems52-offcatalogue-v1` the paired
difference straddles zero (−0.024951, CI [−0.049522, +0.002972]) and on
`gems52-offcatalogue-b-v1` it is clearly negative (−0.050379, CI [−0.071342, −0.023896]).
Neither instrument finds the disagreement field better than a single view.

## 2. The most important thing H83 found (and it is not the DTI table)

`evidence/h83_emission_composition.json`, reproduced in `evidence/h83_run_card.json` under
`emission`, classifies **every one of the 37,654 emitted cells** against both views' own
out-of-fold ranks at the **preregistered** thresholds (donor rank ≥ 0.98, receiver rank in
[0.35, 0.65]):

| Class | Cells | Share |
|---|---|---|
| neither view confident | 33,970 | 90.22 % |
| B-only (B confident, A abstains ⇒ surface artefact) | 3,191 | 8.47 % |
| consensus (both confident) | 492 | 1.31 % |
| **A-only (A confident, B abstains ⇒ candidate buried structure)** | **1** | **0.00 %** |

Before the 3 px density fill the pseudo-label branch produced 10,812 whole-segment pixels
(2,912 A→B, 7,900 B→A) = 28.7 % of the emission. After the fill the discovery branch has
collapsed to **one cell**.

Two consequences, both of which must survive into the next session:

1. **The emission is budget-shaped, not evidence-shaped.** 90 % of the raster is lattice
   filler. Any round that reports "co-training worked" while emitting a uniform 3 px lattice
   is measuring the lattice, not the views.
2. **The B→A branch dominates the A→B branch 2.7 : 1** (7,900 vs 2,912 pixels) and
   3,191 : 1 in the shipped raster. Under this lane's own reading that is a *negative*
   signal: the surface view is confidently tagging things the subsurface view does not
   corroborate, which is exactly the road / canal / erosion artefact signature.

**`A_only` scores 0.033293 on the mandated holdout, below `random` at 0.080426.** The arm built
from exactly the cells this lane calls the discovery signal is worse than placing dots at
random. Nothing else in the round says as much in one line, and it is the single strongest
argument against spending another experiment on this disagreement definition.

## 3. Why the disagreement field loses

The conditional-independence screen passed: max |Spearman ρ| between the two views'
spatial-block out-of-fold errors on 2,089 blocks of held-out catalogue-zero proxies is
**0.1526**, far under the 0.60 bar, so the exchange was allowed to proceed. The leakage
canary also stayed quiet (max single-feature AUC alarm 0.6710, no alarm raised).
Independence is necessary, not sufficient. The failure is in the composition above: with 90 % of the
emission coming from the density fill and the A-only branch essentially empty, the
disagreement field has almost no pixels where it differs from a plain single-view ranking,
but it still pays the full emission budget — and under `DTI = T / (0.2·S + 0.8·|G|)` every
emitted pixel that does not capture credit costs 0.2 in the denominator.

## 4. Lane gate (uniqueness): three readings, all reported

| Reading | Registry | Surface | Dots | Outcome |
|---|---|---|---|---|
| Full census | 571 priors (524 present) | PASS, max ρ 0.1517 | literal **1.000** near-3px, policy **0.8719** | literal **DUPLICATE/STOP**, policy **DUPLICATE/STOP** |
| Scored-only | 13 rasters (`data/scored/*.tif` + `h33-2-b2-zeros.tif`) | PASS, max ρ 0.0534 | literal 1.000 (sole probe `13gems_20261001_r13-lattice-s5_v2_nan-outside.tif`), policy **0.5439** | literal **DUPLICATE/STOP**, policy **PASS** |

Receipts: `evidence/h83_lane_summary.json`, `h83_lane_surface.json`, `h83_lane_dots.json`,
`h83_lane_scored_only.json`. The dots policy found **14** "universal coverage" probes against
the full census — priors whose own dots are within 3 px of essentially any candidate on the
3 px lattice. The candidate is identical to no prior's decoded pattern in any reading.

**The literal rule as written is unsatisfiable.** "More than 70 % of a candidate's dots within
3 px of one registry raster's dots" is satisfied by *every* non-empty raster once the registry
contains any lattice raster, because a 3 px lattice is 3 px from itself. This is recorded in
`registry/irregularities.json` as **IR-H83-003** and must be raised with the organisers; the
restricted (scored-only) PASS is reported and **never** waives the literal rule.

## 5. Irregularities logged this round

`IR-H83-001` … `IR-H83-005` in `registry/irregularities.json` (223 entries total).

## 6. Next session — ordered, with the reasoning for the order

1. **Fix the emission before testing another co-training variant.** Every experiment in this
   lane inherits the 90 %-filler problem. Concretely: make the budget a *consequence* of
   confidence (emit only cells that clear a view-driven threshold, then report the resulting
   S) instead of a *constraint* (fill 37,654 lattice sites and let 90 % be unselected).
   `knowledge/76` shows why: at |G| = 14,089 the champion's 0.2778 implies a credit density of
   13.87 %, while 0.3195 needs 15.95 %; equivalently `DTI = 0.3195` at fixed T needs
   **S ≈ 25,400 px, i.e. 28–33 % fewer pixels than we emit**. The same conclusion from two
   independent directions is the strongest signal in the repository.
2. **Do not re-run the lane gate.** It is done for this raster, on three readings, and the
   literal rule cannot be passed by any non-empty raster. Re-run it only for a genuinely new
   raster.
3. **Ask the organisers about IR-H83-003** (the 3 px dots rule) before spending another slot.
4. Two of the three allowed experiments are unspent. Spend them on (1), not on a new
   disagreement definition.
5. `scripts/prepare_data.py` has still not been run this session — nothing this round depends
   on it, but confirm before any round that rebuilds `work/r2/features`.

## 7. Limitations, stated plainly

- The off-catalogue instrument is a **proxy**: its truth is SGMC faults ≥ 300 m from
  `labels.tif`, which is not the competition's truth. It can demote, never promote.
- `gems52-pooled-hide-v1` scores recovery of **catalogue** faults. The competition scores
  recovery of faults the catalogue **lacks**. Spearman(score, owner-reported board) = −0.10
  over 12 owner-scored priors: the instrument ranks, it does not forecast.
- Every number above is HOLDOUT-DTI or OFFCAT-DTI as labelled. **No number in this file is a
  board score or an organiser-confirmed figure.**
- The single A-only cell is a real measured result, not a rounding artefact — and n = 1 is
  not evidence of anything on its own. It is reported because the lane brief requires
  geological reasoning for *every* A-only candidate; that reasoning is in the per-cell CSV.

## 8. Artefacts

- Raster: `submission/gems52-h83-offcatalogue-cotrain-37654px-e3-20261010T202956Z.tif`,
  sha256 `de580306…0ef7`, 37,654 cells, values exactly {0,1}, no non-finite pixel.
- Byte-structural NaN twin: `...-zeros.tif` variant published as
  `docs/downloads/h83-candidate-template-nan.tif`. Upload one, never both.
- Per-cell reasoning (37,654 rows, 20 columns incl. both views' out-of-fold ranks and the
  geological sentence): `docs/downloads/gems52-h83-...-a-only-reasoning.csv`.
- Site: `docs/index.html`, `docs/h83.html`, `docs/h83-executive-summary.html`,
  `docs/h83-hypotheses.html`, `docs/h83-sources.html`.
- Verification: `python3 scripts/check_site.py` → exit 0; `pytest -q` → 491 passed, 6 skipped.
