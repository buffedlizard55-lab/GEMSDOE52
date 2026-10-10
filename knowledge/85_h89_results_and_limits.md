# 76 · H89 results and limits

Round **H89**, 2026-10-10T21:48:10+00:00. Preregistration `knowledge/83_hypotheses_H89_preregistered.md`
(SHA-256 `4fc5e57b19a450c061cbd55a398b1c6737f4699f5bf4c2eda561e6a10eca78f8`), frozen before any fit and pinned by
`registry/h89_preregistration.json`. Every number below is read from `evidence/h89_*.json`.

**Verdict: NEGATIVE · DOWNLOAD YES · SUBMIT NO - not auto-promoted: lane_dots_policy · slots used 0.**

Artefact: `submission/gems52-h89-coverco-disagree-37654px-20261010T214732Z.tif` — 142,450 bytes, SHA-256 `9d3e2be69efd476c91c8772a28c09ffccadac4281cc2025e376e0c8c8ffba04a`.
Submission name `h89-coverco-disagree-37654px-20261010T214732Z`; note (133/140) `H89 cover-conditioned co-training: artefact-demoted View B + 12% reserved A-only sub-cover dots; 200m catalogue ring excluded; binary`.

---

## 1. Hide-and-recover holdout (the only measured score here)

Evaluator `gems52-pooled-hide-v1`; 53,186 withheld positive pixels;
9,400 dots per fold per arm at 3 px separation; the fold's visible catalogue
masked pixel-exactly and a 200 m ring excluded; α 0.2, β 0.8, 300 m triangular kernel; 1,000 paired
physical-cluster bootstrap draws.

| arm | HOLDOUT-DTI | 95 % CI | role |
|---|---:|---|---|
| `CCD` | 0.160544 | [0.138592, 0.182124] | primary (pre-registered) |
| `single_B` | 0.175326 | [0.154474, 0.196640] | control |
| `B_art` | 0.170046 | [0.147775, 0.191515] | attribution arm — not promotable post hoc |
| `union_max` | 0.150712 | [0.129462, 0.171254] | attribution arm — not promotable post hoc |
| `single_A` | 0.072768 | [0.056962, 0.089230] | control |
| `A_only_cover` | 0.016073 | [0.011322, 0.021397] | attribution arm — not promotable post hoc |
| `random` | 0.079759 | [0.070682, 0.089048] | control |

Frozen promotion test: paired **CCD − single_B = -0.014782** [-0.021456,
-0.008398]. Non-inferiority (point ≥ single_B − 0.020 **and** CI lower bound >
−0.040): **PASS**. Superiority: **no**.

Per fold:

| fold | withheld truth px | allowed px | A-only discovery pool px | CCD | single_B | A_only_cover |
|---:|---:|---:|---:|---:|---:|---|
| 0 | 27,309 | 2,265,054 | 45,099 | 0.098128 | 0.117418 | 0.016296 (5,561 placed) |
| 1 | 10,677 | 1,170,301 | 27,727 | 0.239547 | 0.258195 | 0.010632 (3,359 placed) |
| 2 | 6,813 | 471,065 | 15,078 | 0.200073 | 0.196476 | 0.029712 (1,793 placed) |
| 3 | 8,387 | 686,529 | 16,485 | 0.201114 | 0.214652 | 0.011208 (1,818 placed) |

**Three honest readings of this table.**

1. The primary is **non-inferior, not superior**. The 12 % reserved discovery budget costs
   0.0148 DTI on this instrument, which is inside the margin that was priced in
   *before* the fit precisely because the instrument withholds **catalogue** faults — features that
   were mapped from surface expression — while the competition scores faults the catalogue lacks.
2. `A_only_cover` **short-fills** its matched budget in every fold (see the per-fold counts), so its
   number is not a matched comparison. That is the same defect H74S recorded; it is reported, not
   repaired by back-filling.
3. `B_art` (0.170046) is slightly below `single_B` (0.175326). The
   artefact veto is a hypothesis about **off-catalogue precision**; this instrument cannot test it,
   so the small loss is evidence about the instrument as much as about the veto. The weight was not
   re-tuned after seeing it.

## 2. Leakage canary

Every learner channel scored alone, direction-insensitively, on each fold's held-out region
(all withheld positives plus up to 200,000 random negatives):

| fold | strongest single channel | AUC | positives | negatives |
|---:|---|---:|---:|---:|
| 0 | `B_slope_grad_3` | 0.5995 | 27,309 | 200,000 |
| 1 | `B_slope_grad_3` | 0.6566 | 10,677 | 200,000 |
| 2 | `B_curvature_plus_3` | 0.6247 | 6,813 | 200,000 |
| 3 | `X_rad_Th_rank` | 0.6276 | 8,387 | 200,000 |

Maximum 0.6566 against an alarm bar of 0.9 → **no leakage alarm**.

## 3. View sufficiency and independence

| fold | View A out-of-quadrant AUC | View B |
|---:|---:|---:|
| 0 | 0.5038 | 0.6430 |
| 1 | 0.5944 | 0.7459 |
| 2 | 0.4593 | 0.6014 |
| 3 | 0.5037 | 0.6742 |

Means: A **0.5153**, B **0.6661**. This is the **eighth** measurement
in this project that View A is not a sufficient view for catalogue faults.

Independence (the lane's mandated test): spatial-block out-of-fold error correlation on labelled
negatives, max |ρ| = **0.137151** over 2,089 blocks,
abandon bar 0.6 → **co-training is not abandoned**
(`allow_exchange = True`). Thresholds inherited verbatim from
`registry/h74_preregistration.json` (SHA-256 `44d8eeba549abccd21483bb3…`), not
re-tuned. Standing caveat from the shared tool: catalogue-zero proxy negatives are not verified
fault absence, and a weak error correlation is not proof of conditional feature independence.

## 4. Pseudo-label donation, B → A, one round

| fold | donated px | whole segments | A AUC before | after | improved |
|---:|---:|---:|---:|---:|---|
| 0 | 1,997 | 89 | 0.5038 | 0.4968 | False |
| 1 | 2,000 | 99 | 0.5944 | 0.5821 | False |
| 2 | 1,996 | 98 | 0.4593 | 0.4738 | True |
| 3 | 1,999 | 50 | 0.5037 | 0.5045 | True |

Decision: **pre-exchange View A retained (frozen rule: improvement required in 4/4 folds)** (the frozen rule requires improvement in
4/4 folds).

**IR-H89-001.** The first execution of this stage donated **0 px in all four folds** because the fit
stage predicts on each fold's *evaluation region* only, so the checkpointed grids are NaN across the
buffered training domain — exactly where a pseudo-label is permitted to originate. The stage now
re-derives donor/receiver fields on the training domain from bit-identical refits (same seed, same
sample, deterministic learner). The holdout and the build had already been computed with the
pre-exchange View A, and the corrected run did not change that decision, so no result depends on the
defect. Both receipts exist.

## 5. Placement, and what the metric actually pays for

37,654 binary dots at 3 px minimum separation, 4,518 of them A-only
sub-cover discovery dots (33,136 + 4,518,
shortfall 0). Distance to the nearest mapped catalogue
trace: minimum **223.6 m**, median **1,803 m**,
12.31 % inside the metric's 300 m kernel. Median nearest-neighbour spacing
3.2 px.

The 200 m ring exclusion is not a style choice: on organiser-scored bytes, deleting the 100–200 m
ring moved an owner-reported 0.2600 file to 0.2778 (`knowledge/49` §1), i.e. that ring earned zero
credit while paying the full false-positive tax.

## 6. Uniqueness, lane and not-the-union

Checked against **573** aligned prior rasters — the owner's 526-blob public census
(re-materialised and byte-checked this session) plus this repository's own artefacts — and the
13-raster scored-only registry.

* identical to a prior raster: **None**
* surface maximum Spearman: **0.464132** (lane bar 0.90)
* dots, literal verdict: **DUPLICATE/STOP**, max near-3 px 1.0000
* dots, policy verdict (universal-coverage lattice probes excluded by *measured* coverage ≥ 0.95):
  **DUPLICATE/STOP**, max near-3 px 0.8925

Both verdicts are published. The literal rule is known to return a duplicate verdict against this
census for *every* non-empty raster, because the census contains full-coverage lattice probes; a
restricted PASS never waives the literal result in the written record.

Not-the-union (the lane's explicit requirement): shared with the union-max placement
15,007 px (Jaccard 0.2489),
with single-A 4,226, with single-B
20,845; equal to the union False,
subset of the union False → **PASS**.

## 7. Conditioner sign checks (measured, not assumed)

Top 1 % of `B_curvature_plus_3` sits at 260.4 m
detrended elevation; top 1 % of `B_curvature_minus_3` at
611.7 m; footprint mean
-12.4 m → the positive principal curvature is the
concave-up (valley) one, which is what the artefact term assumes
(`valley_convention_consistent = True`).
Modelled cover in the eligible footprint: median 319.0 m,
p90 1301.3 m, max 7135.3 m; the
discovery gate uses the median as its threshold.

## 8. Limits — what this round does **not** establish

1. **It is not a leaderboard projection.** No number here is ORGANIZER-CONFIRMED. The only honest
   board statement this project can make is the algebra in `knowledge/49`: at S = 37,654 px and
   |G| ≈ 14,088.7 px, a board DTI of 0.3195 needs credit density ρ ≈ 0.1595 versus the 0.1387 the
   owner-reported champion achieved. Nothing measured this round establishes that this file reaches
   it.
2. **The holdout is the wrong instrument for the hypothesis.** It hides catalogue faults; the
   hypothesis is about faults the catalogue never had. An off-catalogue instrument remains the
   highest-value unbuilt tool in this repository — and SGMC is *not* the target to build it on
   (off-catalogue SGMC lines scored 0.0512 on 44 k px, i.e. ρ 0.0234, below uniform random 0.0279).
3. **The artefact veto can delete true positives** wherever aeolian cover or soil mutes a real
   fault's radiometric contrast. It is a soft −0.20 demotion for that reason.
4. **Competition rasters are integrity-pinned mirrors**, verified by SHA-256 against
   `registry/data_manifest.json`, **not** organizer-authenticated downloads.
5. **Local format validation is not upload acceptance.**

## 9. What the next round should do

1. **Build the off-catalogue instrument** (named in AGENTS.md since H77 and still unbuilt). Target
   candidates: Quaternary fault traces from the GDR 1391 tables that are > 200 m from `labels.tif`,
   scored as a *ranking* test, never as an emission target.
2. **Pre-register `B_DVA2` with a continuous sub-pixel orientation** (16/32-direction fan or
   parabolic interpolation). It measured 0.189200 in H82 — the best arm this repository has ever
   produced — and may not be promoted post hoc, so it needs a fresh pre-registration.
3. **Test the artefact veto on its own terms**: hold out *non-tectonic* linear features (mapped roads
   or drainage lines) and measure whether the veto suppresses them more than it suppresses withheld
   catalogue faults. That is a direct test of the mechanism rather than a side-effect measurement.
