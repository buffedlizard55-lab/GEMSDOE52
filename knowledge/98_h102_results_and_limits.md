# 98 · H102 results and limits (2026-10-10) — co-training disagreement-state quota on the DVA2 base

**VERDICT: NEGATIVE (research candidate — OK TO DOWNLOAD: YES · OK TO SUBMIT: NO).**
Neither co-training arm beat the promotion bar; both are *below random placement*. The failure is
mechanistically attributed to **View A insufficiency** (measured mean OOF AUC 0.516, two of four folds
below a coin flip) while the views **are independent** (max |ρ| 0.134). Co-training requires both views
to be sufficiently informative (Blum & Mitchell 1998, doi:10.1145/279943.279962); here only one is.
Slots used: **0**. No ORGANIZER-CONFIRMED number exists for this round.

Preregistration: `knowledge/97_hypotheses_H102_preregistered.md` (SHA-256
`31f7c92c8fbe2be7880af3627eb7d09b483abb6b6a77e557f148b5dbce719b96`, frozen before any fit; pinned in
`registry/h102_preregistration.json`; the runner refuses to start if the hash moves).
Receipts: `evidence/h102_*.json` (channels, fit, fields, e1_graft_holdout, e2_quota_holdout,
e3_proxy_sgmc, independence, lane, lane_informative_uniqueness, write, run_card).

**Artifact** (research candidate — download yes, submit no):
`submission/gems52-h102-disagreement-quota-dva2-25400px-20261011T005958Z-9bd97e7c-zeros.tif` ·
753,675 bytes · SHA-256 `c49a07d15a5bb293c0f29f67d9d4931ed5f2f9ce48978da86af4e59a54f2523d` ·
25,400 binary dots, 0.0 outside footprint, no nodata · ZIP beside it · short alias
`docs/downloads/h102-candidate.tif` · A-only reasoning CSV
`docs/downloads/gems52-h102-disagreement-quota-dva2-25400px-20261011T005958Z-9bd97e7c-zeros-a-only-reasoning.csv`
(4,967 rows, one geological reasoning + named non-fault mimic + falsifier per A-only dot).
Irregularities this round: IR-H102-001 (quota/tie-fill), IR-H102-002 (probe-union novelty),
IR-H102-003 (doubled CSV prefix, fixed pre-publication).

## 1 · What was tested (preregistered)

Lane = the standing brief's co-training paragraph (View A = gravity/magnetics/strain/seismicity; View B =
DEM curvature/slope + radiometric). Two new in-lane mechanisms, never before measured on this fold set:

1. **E1 — soft-prior graft** (full budget 9,400 px/fold): B_DVA2 field blended with View A rank,
   `rB·(1 + w(rA − 0.5))`, w ∈ {0.25, 0.50} (primary g_025).
2. **E2 — disagreement-state quota emission** (sub-halo 6,350 px/fold = 25,400 total):
   state machine on stitched per-quadrant ranks (rB = DVA2 OOF field, rA = View A OOF field):
   - C (consensus): rB ≥ τB and rA ≥ 0.75 — both views fire;
   - A-only (buried): rA ≥ 0.99 and rB < τB — pseudo-label stratum, geological reasoning required per dot;
   - B-only (veto): rB ≥ τB and rA < 0.50 — road/erosion-line suspects, **never emitted**;
   - τB by frozen ladder {0.99, 0.98, 0.97, 0.95, 0.90} with |C| ≥ 18,000 (no peeking);
   - budget 25,400 = 18,000 C + 7,400 A-only via the `s` score (all C rank above all A-only);
   - placement by `run_h73.place_lane` (H73 amendment 61a per-prior quota cap 0.70·K, ≤ 8 rounds)
     against the 13 scored-only informative supports.
3. **E3 — PROXY-SGMC diagnostic** (never a score; H95 recipe): board-anchored sanity check against the
   SGMC geologic-map proxy (Spearman 0.567 vs 13 owner-reported board scores).

Gates (preregistration §4): 1 control reproduction (single_B 0.174517 / random 0.080426 ± 1e-3),
2 leakage canary (max channel AUC < 0.90), 3 view-A sufficiency (mean AUC ≥ 0.60, min fold ≥ 0.55 —
**bookkeeping only**, its expected FAIL does not block), 4 independence (max |ρ| < 0.60 on spatial-block
OOF errors), 5 holdout promotion (quota_primary > 0.192829 **and** paired vs B_DVA2 CI95 lower > 0),
6 lane surface (literal rule on 602-raster census), 7 uniqueness (no identical prior, novelty fraction ≥ 0.20,
not the literal prior union), 8 lane dots policy (informative priors only), 9 format (all-finite [0,1]
container, no nodata), 10 not-the-union (≥ 25 % of dots outside the equal-budget union-max placement).

## 2 · Measured results (all HOLDOUT-DTI unless labelled; evaluator `gems52-pooled-hide-v1`,
53,186 withheld positive px, 4 label-blind quadrant folds, α 0.2 / β 0.8, R 300 m, 1,000 block-cluster draws, SEED 61052)

### 2.1 Fit (out-of-quadrant AUC, per fold)

| arm | fold 0 | fold 1 | fold 2 | fold 3 | mean |
|---|---|---|---|---|---|
| single_A (View A) | 0.5062 | 0.6011 | 0.4668 | 0.4910 | **0.5163 → sufficiency FAIL** (bar 0.60/0.55) |
| single_B (View B) | 0.6625 | 0.7684 | 0.6112 | 0.6952 | 0.6843 |
| B_DVA2 | 0.6840 | 0.7867 | 0.6479 | 0.7284 | 0.7118 |

Leakage canary: max single-channel AUC **0.6689** (worst: `B_slope_grad_3`, fold 1) < 0.90 bar → **PASS, no alarm**.

State machine realised values: τB = **0.98** (ladder: |C|@0.99 = 16,474 < 18,000; |C|@0.98 = 31,490 ≥ 18,000).
|C| = 31,490 · |A-only| = 40,601 · |B-only vetoed| = 32,837 · |pool| = 4,325,298.

### 2.2 E1 — soft-prior graft @ 9,400/fold (37,654 total)

| arm | HOLDOUT-DTI [95 % CI] |
|---|---|
| **B_DVA2 (bar)** | **0.192831** (committed 0.192829; Δ 1.8e-6) |
| single_B | 0.174517 (committed 0.174517; Δ 2.9e-7 → **control reproduction PASS**) |
| random | 0.080426 (committed 0.080426; Δ 3.5e-7 → **control reproduction PASS**) |
| single_A | 0.071954 |
| **g_025 (graft w = 0.25)** | **0.019639 [0.016829, 0.022513] — below random** |
| g_050 (graft w = 0.5) | 0.018175 [0.015520, 0.021076] — below random |

Paired `g_025 − B_DVA2` = **−0.173192 [−0.192087, −0.154063]**. Grafting View A rank into the B_DVA2
field destroys its precision: blending a coin-flip-scale view into a strong field before ranking is
worse than discarding the blend (0.0196) — the graft adds A's noise on top of diluting B's signal.

### 2.3 E2 — disagreement-state quota @ 6,350/fold (25,400 total)

| arm | HOLDOUT-DTI [95 % CI] |
|---|---|
| **B_DVA2 (bar arm at this budget)** | **0.160893** |
| single_B | 0.146375 |
| random | 0.058228 |
| consensus_only (rB·rA on C only) | 0.029261 |
| **quota_primary (18,000 C + 7,400 A-only)** | **0.026348 [0.014089, 0.041360] — below random** |
| a_only_stratum (A-only only) | 0.025816 |

Paired `quota_primary − B_DVA2` = **−0.134545 [−0.157623, −0.112616]**; vs single_B −0.120027
[−0.142945, −0.097607]. **Promotion gate FAIL**: 0.026348 < bar 0.192829 and the paired CI is deeply
negative. Even the pure consensus stratum (no A-only, no veto logic) is below random (0.0293 vs 0.0582).

### 2.4 Independence test (lane instrument, H74 thresholds)

2,089 spatial blocks (50 px, min 32 negatives), 4,095,103 catalogue-zero proxy negatives.
max |correlation| over block-level (MSE, FPR) OOF errors of single_A vs single_B = **0.1337 < 0.60 → PASS
(exchangeable)**. Caveat (pre-registered): negatives are catalogue-zero proxies, not verified absence;
weak error correlation is necessary for co-training, not proof of conditional feature independence.

### 2.5 E3 — PROXY-SGMC diagnostic (never a score)

| field @ budget | PROXY-SGMC (mean over 5 seeds) |
|---|---|
| champion h33-h33-2-b2 (board 0.2778, OWNER-REPORTED) | 0.06060 |
| d2-8 (board 0.2600, OWNER-REPORTED) | 0.05713 |
| single_B @ 25,400 | 0.04507 |
| B_DVA2 @ 25,400 | 0.04249 |
| g_025 @ 25,400 | 0.03706 |
| single_A @ 25,400 | 0.03369 |
| state-machine s @ 25,400 | 0.02622 |

The low-informative proxy (Spearman 0.567 vs board) reproduces the ordering: the co-training fields sit
at/below the weak-view level, far below the single strong view and the champion. No gate reads E3.

### 2.6 Realised emission strata and the tie-fill decomposition (IR-H102-001)

Realised composition of the 25,400 emitted dots: **5,329 C · 4,967 A-only · 15,104 zero-score tie fill**
(154 of the tie-fill dots, 0.6 %, landed on B-only cells **by chance**, not by the state machine). The
frozen 18,000 C + 7,400 A-only quota is **not realised**: consensus cells cluster within 3 px of each
other along linear structures, and the pre-registered 3 px minimum spacing (part of the placement
instrument, `run_h73.place_lane` / `nodes.spacing_select min_px 3.0`) caps extractable C cells at
~5,329 per emission (|C| = 31,490 available). At the E2 budget (6,350/fold) the tie fill is ~60 % of
each fold's mass. Consequence for interpretation: the below-random E2 scores are driven by **both**
mechanisms — the A-gate (consensus_only 0.029261 is itself below random 0.058228) and the tie-fill mass
(zero-score cells ranked arbitrarily by the instrument). Both point the same way; neither is rescued by
the other. Logged as IR-H102-001 (reported, not waived; the verdict is negative on independent grounds).
A future quota design must budget against the **spaced extractable** count of each stratum, not the raw
stratum size.

## 3 · Mechanistic attribution (why it failed)

Blum & Mitchell's co-training convergence requires (i) sufficient feature independence and (ii) each
view to be **sufficiently informative** on its own. This round measured both, pre-registered:

- (i) holds: max |ρ| = 0.1337 on spatial-block OOF errors — the views carry distinct information;
- (ii) fails for View A: mean OOF AUC 0.516, folds 2 and 3 below 0.5 — on held-out quadrants View A is a
  coin flip or worse. Its top-quartile selection (`rA ≥ 0.75`, `rA ≥ 0.99`) therefore selects essentially
  at random (and in two folds anti-correlated) with the withheld truth.

Every way of combining the views — blending ranks (E1), AND-gating (consensus C), quota reallocation
(E2) — pays for that noise with the strong view's precision: B's top-1–2 % cells (rB ≥ 0.98) that a
single_B/DVA2 placement would emit are vetoed or outranked by A's coin-flip quartile. Result: below-random
placement. The single strong view B remains the best field at both budgets (0.1928 / 0.1609).

This is the first **measured holdout demonstration** in this repository of the sufficiency condition's
necessity, and it closes the co-training lane's remaining untried in-lane levers (graft, quota,
consensus-only attribution) — all three fail. A future positive co-training result would require a
View A whose OOF AUC clears ~0.60 mean (e.g., the blocked INGENIOUS thermal view, or a materially
better gravity/magnetics stack), not new combination machinery.

## 4 · Gates, as measured (see `evidence/h102_run_card.json`)

| # | gate | result |
|---|---|---|
| 1 | control reproduction (single_B, random ± 1e-3) | **PASS** (Δ 2.9e-7, 3.5e-7) |
| 2 | leakage canary (< 0.90) | **PASS** (max 0.6689, `B_slope_grad_3` fold 1) |
| 3 | view-A sufficiency (bookkeeping) | **FAIL as pre-registered** (mean 0.5163 / min 0.4668) |
| 4 | independence (max |ρ| < 0.60) | **PASS** (0.1337, 2,089 blocks) |
| 5 | holdout promotion (> 0.192829 and paired CI > 0) | **FAIL** (0.026348; paired −0.134545 [−0.157623, −0.112616]) |
| 6 | lane surface literal (602 priors) | **PASS** (max ρ 0.5417 < 0.90; no identical; no rank/near offenders) |
| 7 | uniqueness literal (novel fraction ≥ 0.20, no identical, not literal union) | **FAIL — standing registry condition** (novel 0.0 vs probe census; informative-only 0.8121, see §5; IR-H102-002) |
| 8 | lane dots (brief's literal rule, full census) | **DUPLICATE/STOP** (max near-3px 1.0 vs probe rasters; 0.8819 vs a dense census raster — both reported; scored-only policy reading PASS, max near 0.3285) |
| 9 | format (all-finite [0,1], no nodata) | **PASS** (re-read validator: problems none) |
| 10 | not-the-union (≥ 25 % dots outside union-max) | **PASS** (76.24 % outside; Jaccard 0.1348) |

**submit_ok = False** (gates 5, 7, 8 fail; the promotion failure alone is decisive). verdict =
**negative**. download_ok = True (the file is a research candidate with the all-finite container; the
portal's `[0,1]` rejection class cannot occur).

## 5 · Lane, format, uniqueness (from `evidence/h102_lane.json`, `evidence/h102_write.json`,
`evidence/h102_lane_informative_uniqueness.json`)

Lane population: **602 rasters** = 524 fetched census blobs (of 526; 2 skipped ineligible — off-grid)
+ 65 local `submission/` artifacts + 13 scored/reference extras (fetch 2026-10-10T00:1xZ, receipt
`work/h102/prior_fetch_receipt.json`). Scored-only restricted registry: 13 rasters.

| phase / population | literal verdict | max ρ | max near-3px | policy verdict |
|---|---|---|---|---|
| surface, full 602 | **PASS** | 0.5417 | n/a | PASS (ρ 0.1504) |
| surface, scored-only 13 | PASS | 0.0349 | n/a | PASS |
| dots, full 602 | **DUPLICATE/STOP** | 0.0430 | 1.0000 | **DUPLICATE/STOP** (near 0.8819) |
| dots, scored-only 13 | DUPLICATE/STOP | 0.0161 | 1.0000 (r13-lattice probe) | **PASS** (near 0.3285) |

- **Rank discipline is clean**: no prior exceeds ρ 0.043 on the dots (bar 0.90) and 0.542 on the surface
  (bar 0.90); nothing is a rank duplicate of anything in the census.
- The dots **near-3px** literal FAIL is the standing probe condition (IR-H87-001 / IR-H96-002 class):
  hash-named universal-coverage probe rasters in the census have 3 px halos covering the whole footprint,
  so a uniformly random same-budget emission would score near 1.0 against them too. Reported, not waived.
- Independently, one dense (informative-by-coverage) census raster catches 88.2 % of the dots within 3 px
  — the honest full-census policy reading. The scored-only policy reading is PASS (max near 0.3285, which
  is exactly the worst-prior overlap the quota placement reports: `worst 0.3285`, `quotas 0`, filled
  25,400/25,400 in round 0, 1.3 s).
- **Uniqueness (decoded pattern)**: vs full census — novel fraction **0.0** (probe union; IR-H102-002),
  no identical prior, max Jaccard 0.0225, not the literal prior union. Vs scored-only informative 13 —
  distinct from every comparable prior, novel fraction **0.8121** (20,627/25,400 dots), max Jaccard
  0.0097 (`gems19-h19-5-powerlaw-budget-multiline-corroborated`), not the literal prior union.
- **Format**: 1 band float32, EPSG:32611, 3730×3292, portal-exact transform, all-finite, values exactly
  {0, 1}, no nodata tag, 25,400 nonzero, 0 mass outside footprint; writer's fail-closed re-read asserts
  passed (problems: none).
- **Not-the-union**: equal-budget union-max placement (same quota machinery) shares only 13.5 % of cells
  (Jaccard 0.1348); 76.24 % of H102 dots lie outside it → the H102 file is confirmed **not merely the
  union** of the views (gate 10 PASS).

## 6 · Limitations

- HOLDOUT-DTI is conditional on the fitted folds, catalogue labels and fixed budgets; it is not a
  leaderboard interval, and no ORGANIZER-CONFIRMED score exists for any H102 file.
- The E2 budget (25,400) is a sub-halo bracketed by H92's instrument-prevalence bound (17,707) and the
  champion-mass elasticity estimate (≈ 26,982); the state machine's per-stratum quality was never given a
  chance because the *combination* itself is below random at any budget (E1 shows the same at 37,654).
- View A's weakness is measured on the label-blind quadrant folds only; on the training domain its AUC is
  higher (in-sample), so a stronger View A stack is not refuted — only this one is.
- E3's proxy is low-informative (Spearman 0.567); it is a diagnostic, never a score.
- The independence test's negatives are catalogue-zero proxies, not verified absence.
- The 526-blob census + 76 local rasters form the lane/uniqueness population; any prior published after
  the fetch time is not covered (fetched 2026-10-10T00:1xZ, receipt `work/h102/prior_fetch_receipt.json`).

## 7 · Suggested remaining work (next session)

1. **Do not spend a slot on any H102 file.** The mass lever (champion-field lane) remains the only
   demonstrated path toward 0.3195 (knowledge/76); it is out of this lane by the standing brief.
2. If co-training is revisited, gate any future round on a **pre-fit View A sufficiency screen**
   (mean OOF AUC ≥ 0.60, min fold ≥ 0.55 as *hard* gates, not bookkeeping): a view at 0.516 cannot be
   salvaged by combination machinery.
3. Blocked View A upgrades (free, official sources only): INGENIOUS 2 m temperature probes
   (DOI 10.15121/1881483, needs owner download — gdr.openei.org unreachable from this sandbox);
   3DEP (blocked previously). Revisit when obtainability is restored.
4. Keep the H95 file as the current download candidate until a round produces a promotable field.
