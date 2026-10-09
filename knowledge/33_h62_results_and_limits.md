# 33 — What H62 found (session 2026-10-09): buried corridors adjudicate NEGATIVE

Preregistered in [`32_hypotheses_H62_preregistered.md`](32_hypotheses_H62_preregistered.md),
frozen in [`registry/h62_buriedcorr_preregistration.json`](../registry/h62_buriedcorr_preregistration.json)
(SHA-256 `e3a8cfd25a1dec233f3a5738a17055390dfc0003f87515d8d50f431d97976552`) before any H62
fit ran. Every number below was computed on the manifest-pinned bytes (23/23 SHA-256 verified,
`evidence/h62_buriedcorr_preflight.json`; integrity-pinned owner mirrors, **not organizer-authenticated**).
Receipts: `evidence/h62_buriedcorr_cotrain.json` (E1), `evidence/h62_buriedcorr_validation.json` (E2),
`evidence/h62_buriedcorr_build.json` + `h62_format_gate.json` + `h62_uniqueness.json` + `h62_lane_surface.json`
+ `h62_lane_gate.json` + `h62_slot_gate.json` + `h62_run_card.json` (E3). Site: `docs/h62-buriedcorr.html`.

**Verdict: NEGATIVE (research-only artifact).** The cover→edge→persistence gate chain on the
A-only disagreement field does **not** improve the catalogue-truth holdout ranking: hide pooled
at 37,654 px, H62-1 **0.003410** [CI in receipt] vs ungated `dis_contrast` **0.004145** >
random **0.001802**; and on the preregistered weak-surface-expression subgroup the field loses
to view_B on **0/4** folds (0.004694 vs 0.006150). Every clause of the frozen promotion bar that
required a win failed; clauses (canary, independence, format, uniqueness, not-union, ring) pass.
A negative result is a deliverable; no competition slot is recommended.

## 1. E1 — the lane premises re-measured on fresh bytes (all reproduce H60D)

- **Independence (Blum & Mitchell premise):** per-50×50-block OOF negative-error Spearman
  **0.1763** (< 0.60 abandonment threshold; 8,588 blocks) — exchange licensed; matches H60D's
  0.176 to three decimals on independent re-derivation.
- **Leakage canary:** worst of 75 cached layers `B_lidar_step_max_grad` AUC **0.7136** < 0.90.
- **Strata:** A-only 299,856 px at median depth-to-basement **340.3 m** vs B-only 196,143 px at
  **107.0 m** (cover geology reproduced). 36,411 withheld positives, 4 whole-segment hide folds,
  seed 20261009.

## 2. E2 — the H62-1 gate chain, measured

Gate chain on `max(pA−pB, 0)`: disagreement∩cover(≥200 m)∩edge(≥P75) = 602,142 px → line opening
(half-widths 2–4 px, 4 azimuths) 562,922 px → persistence filter (skeleton length ≥ 15 px,
elongation ≥ 3) **220,863 px in 261 of 2,387 components**.

HOLDOUT-DTI, hide pooled, 37,654 px (evaluator pinned in `evidence/h62_buriedcorr_validation.json`,
36,411 withheld positives, fold-bootstrap CIs in the receipt):

| field | hide pooled | tip pooled |
|---|---:|---:|
| view_B | 0.0062 | 0.0052 |
| clf_union | 0.0062 | 0.0050 |
| dis_contrast (ungated) | **0.0041** | 0.0032 |
| **H62_1_corridors** | **0.0034** | 0.0022 |
| view_A | 0.0040 | 0.0036 |
| random | 0.0018 | 0.0017 |

At 15,000 px the ordering is the same. **The gates subtract ranking quality** relative to the
ungated disagreement field on withheld catalogue segments — plausibly because a withheld
catalogue segment is by construction a *mapped* (surface-expressed) fault, and the cover gate
(≥200 m burial) removes exactly the ground where those segments live. The weak-surface subgroup
(below-median view-B expression along the withheld trace) was the preregistered place where the
lane predicted its advantage; it lost there too (0/4 folds vs view_B).

**Reading (three sentences).** The instrument's truth is surface-mapped catalogue segments; the
board's truth is expert-drawn faults *absent* from that catalogue (official problem page). A
cover-gated discovery field is structurally mis-targeted for the instrument and unmeasurable for
the board from public information (IR-H60-003: board/instrument Spearman −0.099 across 13 scored
priors; the 0.2778 champion scores below random on this instrument). H62 adds one more measured
null to the family: physical gating of the disagreement field does not transfer to catalogue-truth
ranking, and no available instrument can certify its board value.

## 3. E3 — the artifact (unique; research-only)

`submission/gems52-h62-buriedcorr-37627px.tif` (107,698 bytes, SHA-256
`1f25c4fbeaf1aaf945b789bdb480971178bd0247c02da53617d20ee3d24dd8d2`), portal name
`gems52-h62-buriedcorr-37627px-1f25c4fb-zeros`, note (138/140): *"H62 buried corridors:
cover/edge/persistence gates on A-only disagreement; finite binary [0,1]; off-prior; hypotheses,
not verified faults"*.

Gates (all measured): format 0 problems (single band, float32, EPSG:32611, 3,730×3,292, exact
sample transform, **all finite {0,1}**, zeros outside footprint — the portal's
"Predicted values must be in range [0, 1]" error cannot occur on this file) · decoded-pattern
unique vs **71** accessible priors · **100 %** of emitted pixels outside every prior's support ·
lane drift clean (surface max |ρ| 0.048; dots max |ρ| 0.0094; ≤3 px proximity 0.3623 excluding
manifest-classified calibration rasters per H60-6, raw 0.8307 disclosed) · not-merely-union
(37,269/37,627 outside the union field's matched-budget top-k) · ring clean (min distance to a
mapped catalogue pixel 223.6 m) · one written geological reasoning per emitted pixel
(37,627 rows) and per A-only corridor segment (1,120 rows), each with an explicit falsifier.

**Disclosed weakness (the important one):** on the required-novel pool the corridor field has
only **1,707** crest pixels; the remaining **35,920** of the matched 37,654 budget is zero-field
fill (emitted for budget comparability with the validation cells, and because DTI = T/(0.2S+0.8|G|)
grows with S at any positive density). Shipped-raster hide pooled HOLDOUT-DTI is 0.0025 (folds
0.0011–0.0044); the matched novel-pool controls are in `evidence/h62_buriedcorr_build.json`.

## 4. Why 0.2778, and can anything beat it — the cross-checked answer

**Why 0.2778 (owner-reported attribution).** The file `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros`
(SHA-256 `c55bafc470054e82…`, restored and re-measured here) is `gems24-…-d2-8` (reported 0.2600)
**minus 6,436 pixels lying 100–200 m from the mapped catalogue**. Inverting the published metric
on the nested pair credits the deleted ring with **exactly zero**; deleting 14.6 % of the mass
raised the reported score 6.8 %. It won by understanding the metric's tax term — not by a better
detector. GEMSDOE32's own page (read 2026-10-08) states **"NO ORGANISER SCORE EXISTS for this or
any artifact in this repository"** and quotes a *projection* of 0.2747 — so the 0.2778
attribution is **OWNER-REPORTED, not ORGANIZER-CONFIRMED**, and is flagged as a provenance
conflict in `registry/irregularities.json` (IR-H62-009).

**Can we beat it — and 0.3195/0.3262?** The leaderboard read verified from GEMSDOE32's stored
snapshot (2026-10-04): #1 nchuzhoy **0.3262**, #2 DARD **0.3195**, #3 alexoktaba 0.3042
(owner-reported reads of the public page; this sandbox cannot authenticate the live board).
The metric algebra (exact for sparse dot emissions): `DTI = T / (0.2·S + 0.8·|G|)`, with |G|
bracketed **≈ 18,000–27,400 px** by the nested-pair arithmetic once the unmeasured `M = T`
assumption is dropped (IR-H60-002; GEMSDOE32's truth model instead infers 12,691 px — the
spread is itself evidence of non-identification). The marginal rule: a pixel's expected credit
must exceed `α·DTI/(1−α·DTI)` — ≈0.055 at 0.2778, ≈0.068 at 0.32 — against measured uniform-random
credit density 0.024–0.028. Everything we can measure sits below the bar except the champion's
own attributed core (0.163–0.205 density on 25,517 px, identified interval [0.2524, 0.3196] —
consistent with the 0.3195–0.3262 leaders being re-weightings of that same mass). **Beating
0.32 requires new mass at density above ~0.07 that no instrument in this repository can
certify**; the hide instrument is anti-correlated with the board for exactly the population the
board rewards. That is the honest state of the art here, and H62 does not change it.

## 5. What H62 contributes to the family

1. **A fourth physical null:** cover-gating + edge-conditioning + line persistence *reduces*
   catalogue-truth ranking versus the ungated disagreement field (0.0034 vs 0.0041 hide pooled).
   The gates are geologically sensible and still negative — registered so nobody re-tries them
   without new information.
2. **The weak-surface subgroup instrument** (new): withheld segments split by mean view-B
   expression along the trace. Even where surface expression is weak, view_B beats the buried
   corridor field 4/4 folds. Registered as the lane's fairest test; it failed.
3. **A reproducibility fixed point:** the OOF fields, strata (±2 px), canary and independence
   statistics re-derive on fresh restored bytes to H60D's values; the shared-template stale
   checkpoint defect (IR-H62-006) and the subgroup OOM (IR-H62-008) were fixed once in shared
   code, with tests (`tests/test_h62_buriedcorr.py`).
4. **Novel-ground scarcity, quantified:** the A-only corridor population overlaps existing prior
   submissions' support by ~99.2 % (only 1,707 crest px survive on required-novel ground). Any
   future "unique discovery" file faces the same wall: the family's priors already cover the
   corridor population.

## 6. Limitations and next steps

- The promotion bar compares on catalogue truth; the board rewards off-catalogue truth. No
  public instrument resolves this (IR-H60-003). The run card carries the conditional projection
  table labelled as projection, never a score.
- The zero-field fill fraction (35,920/37,627) is disclosed; a crest-only file would be
  score-capped near 0.10 by the |G| term alone at 1,707 px — both facts are in the receipts.
- Organizer authentication of the mirror bytes and of the score-to-file mapping remains the open
  blocker for any ORGANIZER-CONFIRMED number.
- Registered but untested (precondition "H62-1 passes clause (a)" failed): H62-2 step-over nodes,
  H62-3 alteration concordance, H62-4 ratcheted multi-round co-training, H62-5 B-only
  hard-negative de-biasing. Do not promote them to testing without a new falsifiable angle.

## Post-merge amendment (2026-10-09) — artifact identity, IR-H62-010

The concurrent H61/H62-concordance session's files (PRs #43–46) joined the prior registry after this
round's E3 freeze. Registry-relative claims re-measured on the merged tree (80 aligned priors):

| artifact | emitted px | sha256 (prefix) | pattern-unique vs 80 | novel fraction vs 80 | status |
|---|---:|---|---|---:|---|
| `gems52-h62-buriedcorr-37627px.tif` (E3 freeze, 00:55Z) | 37,627 | `1f25c4fbeaf1…` | yes | **0.9924** | superseded; kept with dated sidecar for provenance |
| `gems52-h62-buriedcorr-37626px.tif` (rebuild, 01:40Z) | 37,626 | `6b494e7d1abc…` | yes | **1.0000** | **current research candidate** (DOWNLOAD YES / SUBMIT NO) |

Mechanism: the required-novel pool excludes every prior's support, so selection is a function of the
registry; the rebuild placed 1,709 crest px + 35,917 zero-field fill, clipped 28 ring violations. The
frozen name prediction (`…37627px-1f25c4fb-zeros`) therefore does not describe the shipped bytes
(`…37626px-6b494e7d-zeros`); the preregistration itself is untouched.

The preregistered 3 px lane-proximity gate reads 0.9994 (excl. calibration) on the rebuild — any
lattice-placed emission now trips it because the registry contains several lattice-dense emissions
(sibling IR-H61-005/009, IR-H62-004 on the diamond geometry). Reported as registry-saturated; the
promotion bar had already failed on clauses (a) and (b), so the verdict is unchanged: **negative**.

Shipped-raster HOLDOUT-DTI of the current candidate (recomputed): hide pooled **0.002247**
[0.001112, 0.003675] (36,411 withheld positives); tip pooled 0.001663. E1/E2 numbers above are
untouched by the merge (holdout machinery is registry-independent).

Second re-measure (after the H63 round merged, PR #48): the candidate's novel fraction against the
then-current registry (83 priors) is **0.9959** (pattern still unique) — ~155 of its pixels now lie
inside the H63 emission's support. This is IR-H62-010's point again: zero-copy claims are
registry-relative and decaying by construction as concurrent rounds publish; the build-time claim
(1.0000 vs 80) stands as the measured certification of the shipped bytes, and no further rebuild is
chased (the emission is a function of the registry; nothing was submitted).
