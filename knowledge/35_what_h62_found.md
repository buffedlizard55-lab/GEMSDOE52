# 33 — What H62 actually found (session 2026-10-09)

Preregistered in [`34_hypotheses_H62_preregistered.md`](34_hypotheses_H62_preregistered.md)
(sha256 `fd781e4f…`, frozen before any fit; verified at start-up by `scripts/run_h62.py`) and in
[`registry/h62_preregistration.json`](../registry/h62_preregistration.json). Every number below was
computed this session on the manifest-pinned bytes (`data/`, 23/23 SHA-256 pins verified in
`evidence/h62_preflight_integrity.json`) with the evaluator modules pinned by SHA-256
(`metric.py 3d454119…`, `holdout.py f6706d78…`, `h57.py 729a7623…`).

Receipts: `evidence/h62_cotrain.json` (E1), `evidence/h62_validation.json` +
`evidence/h62_validation_extra.json` (E2), `evidence/h62_build.json` +
`evidence/h62_format_gate.json` + `evidence/h62_uniqueness.json` + `evidence/h62_lane_gate.json` +
`evidence/h62_run_card.json` (E3). Site: `docs/h62.html`.

**Artifact:** `gems52-h62-conc_soft-arm22000px.tif` — 114,669 bytes, sha256
`1bc5b50c014e70692919c1f604939c02ba6915fcf038f34327cd745e78de6ea7`, 22,000 px, values exactly
{0,1}, single-band float32, EPSG:32611, 3730×3292, all finite. Reproducible: the rebuild after the
H62-2/H62-3 corrections and the IR-H62-001 footprint fix reproduces the identical sha256 — the
build is a measured fixed point.

---

## 1. The premise held, and the leakage canary stayed clean

| statistic | value | bar |
|---|---|---|
| block negative-FPR Spearman (8,588 blocks, 18,048,996 negative predictions) | 0.1757 | 0.60 |
| block MSE Spearman | 0.1531 | 0.60 |
| pixel-level Pearson / Spearman (4,519,160 px) | 0.1561 / 0.1512 | — |
| worst single-layer holdout AUC (75 layers) | 0.7177 (`B_lidar_step_max_grad`) | 0.90 |

The Blum–Mitchell coupling is weak, so the concordance operator is licensed to be tested — and no
layer is a leakage channel.

The 2×2 confidence table reproduces the cover geology for the third independent time, now on a new
seed and a new fold set: **A-only median depth to basement 340.5 m vs B-only 108.1 m** (3.15×), with
the concordant cell in between at 227.7 m and the whole legal pool at 316.0 m.

## 2. The operator could not be delivered as a hard intersection — and that is a result

Two independent thinnings of `k` dots inside a pool of `n` intersect in `k²/n` dots: **185 px at
k = 30,000, n = 4,861,502**, even under perfect independence. Measured at the preregistered
`q_conf = 0.60` with `k = 60,000`: View A's confident set thins to **6,307** dots against View B's
**31,083**, and the intersection is **92 px** — a 2.28× lift over the 40.3-px independence null,
which is real corroboration, but two orders of magnitude below any budget this competition scores.
Registered as **correction H62-1** before the artifact shipped: the operator is delivered as a
*ranking* on the joint confidence `min(pA,pB)`, and `conc_corrob` is published as the measured
structural negative (Instrument-2 lift 0.97–0.99× — indistinguishable from random at every budget).

The reason View A thins so far below View B is not a tuning accident: at one absolute probability
bar the two views are not comparable, because View A is the weaker detector. That is itself the
asymmetry H62-C was written to test and could not be run.

## 3. Instrument 1 — pooled HOLDOUT-DTI (hide-and-recover, 25,000 px, 36,474 withheld positives)

| field | pooled HOLDOUT-DTI | 95 % CI | lift over matched random |
|---|---:|---|---:|
| view_A | 0.010332 | [0.008177, 0.012002] | +0.009056 |
| **conc_soft (shipped)** | **0.008467** | [0.003427, 0.011601] | +0.007191 |
| clf_union `max(pA,pB)` | 0.008390 | [0.004612, 0.010721] | +0.007114 |
| view_B | 0.007970 | [0.004481, 0.010627] | +0.006694 |
| conc_min | 0.004801 | [0.004049, 0.005529] | +0.003525 |
| dis_product | 0.003797 | [0.001795, 0.005335] | +0.002521 |
| conc_corrob | 0.003007 | [0.001398, 0.005507] | +0.001731 |
| dis_contrast | 0.003388 | [0.001761, 0.004660] | +0.002112 |
| cover_A_only (H62-A) | 0.002929 | [0.001470, 0.005349] | +0.001653 |
| random | 0.001276 | [0.001129, 0.001376] | 0 |

**The registered comparison the brief asks for — against a single-view baseline on
hide-and-recover segments — the concordance ranking wins.** `conc_soft` beats both `clf_union`
(+0.000077) and the surface view `view_B` (+0.000497) at 25,000 px, and at 15,000 px
(0.006846 vs 0.005919 vs 0.005713). `view_A` alone is higher still, so the concordance is not the
best single field on this instrument — it is the best *two-view* field, which is what the lane
tests.

Read with the defect attached: this instrument is **not** a board proxy
(Spearman(owner-reported, simulated) = −0.1045, p = 0.734, n = 13; the 0.2778 champion ranks 13/13
on it). It is reported because the lane requires it and because it is the only leakage detector
available.

## 4. Instrument 2 — revealed-preference co-location (lift over the matched random control)

Core atom `P1 = h33-2-b2 ∩ d1-5`, 25,517 px, measured credit density **[16.3 %, 20.5 %]**
(owner-reported scores; `knowledge/10` §3).

| field | 8k | 12k | 17k | 25k | 38k |
|---|---:|---:|---:|---:|---:|
| view_B | 3.49× | 3.21× | 2.94× | 2.53× | 1.99× |
| clf_union | 3.44× | 3.15× | 2.86× | 2.46× | 1.93× |
| **conc_soft (shipped)** | **2.04×** | **1.82×** | **1.62×** | **1.33×** | **1.10×** |
| conc_min | 1.89× | 1.57× | 1.40× | 1.25× | 1.16× |
| view_A | 1.24× | 1.24× | 1.11× | 1.07× | 1.06× |
| conc_corrob | 0.98× | 0.99× | 0.99× | 0.97× | 0.97× |
| cover_A_only | 0.86× | 0.91× | 0.93× | 0.93× | 0.95× |
| dis_product | 0.67× | 0.65× | 0.64× | 0.66× | 0.66× |
| dis_contrast | 0.64× | 0.62× | 0.60× | 0.60× | 0.62× |

**The finding of the round.** The lane's designated discovery signal — the disagreement cell —
measures **below the matched random control** at every budget on the only instrument tied to
measured credit: `dis_contrast` 0.60–0.64×, `dis_product` 0.64–0.67×, and the new
cover-conditioned variant `cover_A_only` 0.86–0.95×. H56, H59 and H60D each reached a negative for
the disagreement fields by a different route; this is the sharpest form of it, because the
comparison is against a pixel set whose credit density is *measured* rather than projected.
H62-A is therefore **refuted**: restricting the buried-fault cell to thick cover does not rescue
it — it moves it from 0.60× to 0.93×, i.e. from clearly anti-correlated to merely random.

Two honest readings of the top of that table: (a) the surface view is by far the strongest single
ranker of what the champion found, and (b) the union `max(pA,pB)` is statistically identical to
`view_B` — adding the geophysical view as a union changes nothing, and as a concordance it *loses*
on this instrument while winning on the other.

## 5. The instruments disagree in sign, and that is registered, not resolved

hide: `view_A > conc_soft > clf_union > view_B` · revealed: `view_B > clf_union > conc_soft >
view_A`. Almost inverses. Recorded as **IR-H62-003**. Neither is presented as a forecast; the
orderings are published side by side and the round's verdict is scoped explicitly to the
registered instrument. Closing this needs an organizer-authenticated label set, which the sandbox
cannot obtain.

## 6. The budget was derived, and the derivation disagreed with itself

`DTI(S) = T(S)/(0.2 S + 0.8|G|)`; with `T(S) = c S^γ` the argmax `S* = γ·0.8|G|/(0.2(1−γ))` is
independent of `c`, so field quality does not move it. γ fitted to this round's own field over
8k–38k px is **0.6453**, giving an unclamped `S*` of **102,519 px** — outside the measured range,
hence an extrapolation, and it rests on a mixture whose `ρ_novel` bound is a prior. The board's own
published record is a direct measurement and points the other way: **score is strictly decreasing
in emitted mass across the six off-catalogue scored priors (Spearman −1.000, n = 6)**.
Direct measurement governs, so the emission is **22,000 px** — the preregistered fallback, the
midpoint of the |G|-bracket solutions (21,300–22,870 px), inside the preregistered clamp
[15,000, 30,000]. Registered as **correction H62-2**, with the unclamped value published.

## 7. Field selection, and the union disqualifier

| field | dots | f | lift | overlap with `max(pA,pB)` top-k | decision |
|---|---:|---:|---:|---:|---|
| view_B | 22,000 | 0.3015 | 2.67× | **93.0 %** | disqualified — is the union |
| clf_union | 22,000 | 0.2937 | 2.60× | 100 % | disqualified — is the union |
| **conc_soft** | **22,000** | 0.1600 | **1.42×** | **2.4 %** | **shipped** |
| conc_min | 22,000 | 0.1475 | 1.31× | 2.0 % | eligible, lower lift |
| view_A | 22,000 | 0.1215 | 1.08× | 7.8 % | eligible, lower lift |
| conc_corrob | 22,000 | 0.1090 | 0.97× | 0.7 % | eligible, at random |
| cover_A_only | 22,000 | 0.1050 | 0.93× | 0.4 % | eligible, below random |
| dis_product | 22,000 | 0.0742 | 0.66× | 0.4 % | eligible, below random |
| dis_contrast | 22,000 | 0.0680 | 0.60× | 0.4 % | eligible, below random |

`view_B` and `clf_union` are the two best fields on Instrument 2 and they are the *same field*:
93–100 % of their dots coincide and their reads differ by 3 %. Shipping either would ship
`max(pA,pB)`, which the brief explicitly forbids ("confirm the output isn't merely the union of the
two views"). Any candidate overlapping the union's top-k by more than 70 % is therefore
disqualified mechanically — **correction H62-3** — and the winner is the highest-lift survivor.

## 8. Every gate on the shipped file

| gate | result |
|---|---|
| format | **PASS**, 0 problems — 1 band float32, EPSG:32611, 3730×3292, transform matches, values {0,1}, 0 NaN |
| mass outside the emission domain | 0 px |
| 200 m ring | **PASS** — nearest mapped catalogue pixel **223.6 m** |
| uniqueness | pattern-unique vs **71** accessible aligned priors; support novelty **61.4 %**; not a literal prior union |
| lane drift, ranking surface | max \|Spearman\| **0.1401** (bar 0.90) |
| lane drift, final dots | max \|Spearman\| **0.0263**; 3-px proximity **0.2781** excl. calibration (bar 0.70); raw 0.8416 incl. the calibration lattice (H60-6) |
| not merely the union | **21,474 / 22,000 px (97.6 %)** outside `max(pA,pB)`'s own top-k |
| reasoning | 22,000 per-pixel rows + 3,580 A-only candidate-segment dossiers (of 8,523 components; the rest are < 3 px and are counted, not written) |

## 9. Verdict, scoped

**`promote`, scoped to the registered instrument.** The concordance ranking beat both single-view
baselines and the union on pooled hide-and-recover HOLDOUT-DTI — the comparison the brief asks for.
It did **not** beat the surface view on the revealed-preference instrument, and no weekly slot is
allocated: promotion to a real slot is a separate selector step within the cap on the submission
page. No organizer-confirmed score exists for this file and none is claimed.

**Negative results this round, all deliverables:** H62-A (cover-conditioned buried disagreement)
refuted — below random; the hard corroboration intersection refuted — structurally unable to fill a
budget (IR-H62-002); the disagreement family as a whole measured below the matched random control
on the instrument tied to measured credit, which is the fourth independent confirmation of what
H56/H59/H60D found.

## 10. Incidents registered

| id | statement |
|---|---|
| IR-H62-001 | The all-19-band training footprint and the `sample_submission` domain are **not nested** (1,540 px one way, 3,073 px the other; intersection 5,164,300 px). The first build failed closed on it; the emission domain is now their intersection. Any future round emitting on the raw training footprint hits the same error. |
| IR-H62-002 | The corroboration operator is structurally unable to fill a usable budget (`k²/n` = 185 at k = 30,000). Registered as correction H62-1; do not try to rescue it by lowering `q_conf`. |
| IR-H62-003 | The two instruments disagree in sign on the best field. Both orderings published; neither is a forecast. |

## 11. Three passes

1. **Implement + verify:** E1/E2/E3 built and run; the run failed closed on IR-H62-001 rather than
   emitting on a wrong domain; all receipts written.
2. **Bug review + fix:** the footprint non-nesting (fixed at the source, domain = intersection),
   the self-exclusion over-reach (restricted to this build's own basenames so a parallel H62
   artifact stays a genuine prior), the holdout budget label (taken from the receipt key, not from
   an identity test on dicts), and the missing download copy of the reasoning CSV (caught by
   `scripts/check_site.py`) were all found by review or by the site checker and fixed.
3. **Full re-check:** the rebuilt artifact is byte-identical (`1bc5b50c…`), which establishes the
   build as a fixed point; `scripts/check_site.py` passes with 0 problems; `pytest -q` green.
