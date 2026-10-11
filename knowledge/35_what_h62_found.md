# 33 — What H62 actually found (session 2026-10-09)

> **Current correction (2026-10-10):** the historical score inversion below is conditional algebra, not a measurement or explanation of why an organizer score changed. The 0.2778 row is rank 17 in the later saved public-board observation; no file/hash receipt maps it to the reported raster. The local removed-cell credit is unknown because new-fault truth may occur within 300 m of known traces. See [`knowledge/49`](49_why_02778_phd_answer.md).

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

### 6b. …and the |G| the budget rests on turned out to be wrong (**correction H62-4**, `IR-H62-005`)

Those |G|-bracket solutions were computed over a |G| bracket of **18,000–19,300 px**. That bracket is
**disjoint** from the interval |G| is actually identified to live in. |G| is bounded by two
assumption-free constraints on the pinned bytes:

* **lower:** `T ≤ |G|` (credit cannot exceed the number of positives) applied to the largest
  off-catalogue support — `calib_8GEMSDOE_Hedge-v2`, 166,519 px at score 0.1563 — gives
  **|G| ≥ 5,949.3 px**;
* **upper:** credit is monotone in support, so on the nested pair `d15` (60,069 px, 0.2477) ⊂
  `gems27_tgc_v2_d15` (61,328 px, 0.2449) the inequality `T_sub ≤ T_sup` gives **|G| ≤ 12,512.1 px**.

Both were re-derived in this checkout from the manifest-pinned bytes; the subset relation and the
166,519-px support were recomputed directly and both bounds reproduce `evidence/h61_forensics.json`
(main's H61) to four decimals. The value this round carried in, **|G| = 14,088.7 px** (`knowledge/10`
§2), is a *valid but non-binding* upper bound — it comes from the weaker nested pair
`h33-2-b2 ⊂ d28` — and using it as a point value additionally assumes the champion's 6,436 deleted
ring pixels earn exactly zero credit; it falls to 7,066 px if they earn 100 px.

Because `S*` is **linear in |G|**, the consequence is exact:

| γ | \|G\| = 5,949.3 | \|G\| = 12,512.1 | \|G\| = 14,088.7 |
|---|---:|---:|---:|
| 0.6453 (this round's own field) | 43,294 → clamp **30,000** | 91,052 → clamp **30,000** | 102,525 → clamp **30,000** |
| 0.2284 (champion family) | 7,044 → clamp **15,000** | 14,815 → clamp **15,000** | 16,681 |

**The two γ rules now disagree, and the direct measurement breaks the tie toward the low end.**
The emission is **not** changed: 22,000 px is the preregistered fallback, it sits between the two
model answers, and churning the file a second time after review would replace one unmeasured
judgement with another. But the budget's *derivational* support is now the weakest link in this
round, and **15,000 px is the value the assembled evidence favours**. That is the first item for the
next session, not a silent footnote.

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
| uniqueness | pattern-unique vs **77** accessible aligned priors; support novelty **60.5 %**; not a literal prior union |
| leakage canary | worst of 75 layers, AUC **0.7177** |
| Blum–Mitchell independence premise | max \|r\| **0.1757** (abandonment bar 0.60) |
| not merely the union | **21,474 / 22,000 px (97.6 %)** outside `max(pA,pB)`'s own top-k |
| lane drift, ranking surface | max \|Spearman\| **0.0785** (bar 0.90) |
| lane drift, final dots, Spearman | max \|Spearman\| **0.0232** (bar 0.90) |
| **lane drift, dots within 3 px — STRICT GATE** | **FAIL / DUPLICATE-STOP — 99.99 %** |
| lane drift, dots within 3 px — coverage-aware repair (`gates.lane_report`) | **PASS — 45.3 %** on the 76 priors that localise something |

**Why the strict gate fails, and why that is a fact about the registry.** After the H60D strict
recheck, `h60d.lane_drift_report` counts *every* supplied registry raster — the calibration
exemption (H60-6) was withdrawn. The binding raster is
`data/scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif`, a spacing-5 square lattice. Its
maximum interior distance is √8 = 2.83 px < 3 px, so its 3 px halo covers **99.90 %** of the
eligible footprint and the "70 % of your dots within 3 px" statistic reads ≈1.0 for *every*
nonempty candidate, including pure noise. `gates.lane_report` — the repair main's H61 added to the
shared template — measures that coverage, classifies the lattice as the one universal-coverage
probe, and re-runs the identical rule on the 76 priors that do localise something: max |Spearman|
0.023, max 3 px proximity **0.453**.

Both readings are published, neither is suppressed, and the strict one governs the submit decision
because that is this repository's settled convention: CTD5 and H60D were stopped on the same
statistic, and main's H61 prints FAIL/STOP on its own front page rather than letting the repair
overturn it.

**Reproducibility.** The round was rebuilt from scratch after the merge — the layer stack, all four
folds, both instruments — and every measured statistic reproduced exactly: max |r| 0.1757144177181826,
canary 0.7177, the 2×2 strata, the 92-px corroboration intersection, all eight candidate lifts, the
winner. The emitted raster is stable to **21,998 of 22,000 dots**; two dots at the top grid edge
(columns 661 and 721) moved down by exactly one row, which is a tie-break at the resolution of the
ranking. The shipped sha256 is `de47952fe9c0fc15c1aaacd63a04f6c0a6aa15b094f2367ed631c6920e91c1fd`.

## 9. Verdict: negative — OK to download for research, do not submit

**The one positive measurement stands.** The concordance ranking beat both single-view baselines and
the union on pooled hide-and-recover HOLDOUT-DTI — the comparison the brief asks for — and the lane's
designated discovery signal measured below a matched random control on the instrument tied to measured
credit, which is the fourth independent confirmation of what H56/H59/H60D found.

**But the file does not clear the gate that decides whether a slot may be spent.** The strict lane gate
returns DUPLICATE/STOP at 99.99 % near-dot proximity to a lattice that saturates the registry (§8).
So: **research review copy; no weekly slot allocated and none recommended.** No organizer-confirmed
score exists for this file and none is claimed.

## 10. Incidents registered

| id | statement |
|---|---|
| IR-H62-001 | The all-19-band training footprint and the `sample_submission` domain are **not nested** (1,540 px one way, 3,073 px the other; intersection 5,164,300 px). The first build failed closed on it; the emission domain is now their intersection. Any future round emitting on the raw training footprint hits the same error. |
| IR-H62-002 | The corroboration operator is structurally unable to fill a usable budget (`k²/n` = 185 at k = 30,000). Registered as correction H62-1; do not try to rescue it by lowering `q_conf`. |
| IR-H62-003 | The two instruments disagree in sign on the best field. Both orderings published; neither is a forecast. |
| IR-H62-005 | This round's emission budget was derived from a \|G\| bracket (18,000–19,300 px) that is **disjoint** from the measured one ([5,949.3, 12,512.1] px). Registered as correction H62-4; the emission is unchanged but its derivational support is gone and 15,000 px is what the evidence favours. |

## 11. Three passes

1. **Implement + verify:** E1/E2/E3 built and run; the run failed closed on IR-H62-001 rather than
   emitting on a wrong domain; all receipts written.
2. **Bug review + fix:** the footprint non-nesting (fixed at the source, domain = intersection);
   the self-exclusion over-reach (restricted to this build's own basenames so a parallel artifact
   stays a genuine prior); the holdout budget label (taken from the receipt key, not from an
   identity test on dicts); the missing download copy of the reasoning CSV (caught by
   `scripts/check_site.py`); the layer-stack stage that was being run by hand and is now
   `stage_layers` inside `scripts/run_h62.py` so the round is reproducible from the committed
   scripts alone.
3. **Full re-check against the merged repository.** This is where the round changed verdict. Merging
   main brought (a) a **second, independently developed round also called H61**, which this round was
   renamed H62 to coexist with, following the repository's own H60 → H60C → H60D precedent;
   (b) main's H61 measurement that `|G|` is identified only as the interval [5,949.3, 12,512.1] px,
   which invalidates the bracket this round's budget was derived from (correction H62-4, IR-H62-005);
   (c) two new prior rasters; and (d) the withdrawal of the calibration exemption (H60-6) in
   `h60d.lane_drift_report`, which is what turns the strict lane gate from 0.2781 into 0.99986 and
   the verdict from promote into DUPLICATE/STOP. Every stage was re-run from an empty `work/h62`
   afterwards: all measured statistics reproduced exactly and the emitted raster reproduced to
   21,998 of 22,000 dots. `scripts/check_site.py` passes with 0 problems; `pytest -q` green.
