# 42 · H65 results and limits — one gate refuted, one holdout negative, one unique research GeoTIFF

Rendered from the receipts by the round's own scripts; every number below lives in a JSON receipt in
`evidence/` and every gate label is frozen in `knowledge/41_hypotheses_H65_preregistered.md`
(SHA-256 pinned in `registry/h65_preregistration.json`, runner refuses on hash drift).

**Verdict: `NEGATIVE (DOWNLOAD YES for research; SUBMIT NO)`.** Gates: format **PASS** · decoded
identity vs all 603 aligned priors **0 identical** · lane surface **PASS (both readings)** · lane
dots **DUPLICATE/STOP (literal and policy)** · holdout beats single_B **NO**. Competition slots
used: **0**. No certified leaderboard gain exists or is claimed.

## 1 · What the three experiments measured

**E1 — R5-H1 trace-correction corridor gate: FAIL.** Evaluator `h65-a-gate-v1` (geometric,
20 km whole-block trace folds, seed 20261009): G1 1,584 held-out traces (≥200 — pass); G2 median
|ô| 1.000 px (≤1.0 — pass at the boundary); **G3 margin 0.000 px vs the 0.300 px requirement
(estimator median MAE 1.000 = constant-offset control 1.000) — FAIL**; G4 argmax-zero fraction
0.356 (≤0.5 — pass). The A1 calibration read the undocumented LiDAR `strike` band's convention
from the data before any gate statistic: best circular resultant length 0.086 < 0.10, so t2 was
carried at its honest ≈0.5 level (uninformative) exactly as the frozen amendment prescribes.
Reading: the frozen scarp terms carry no locally-localizable trace-offset signal; the
organiser-confirmed corridor population stays real, but this estimator cannot place it. Receipt:
`evidence/h65b_gate.json`.

**E2 — R5-H2a band-10 valley lines: HOLDOUT-DTI negative.** Evaluator `gems52-pooled-hide-v1`
(this run's config: 4 hide folds, buffer 4 px, prevalence 0.002, seed 0; **36,439 withheld
positives**; pooled DTI α 0.2, β 0.8, R 300 m; 95% cluster bootstrap, 1,000 draws):

| arm | HOLDOUT-DTI | 95% CI |
|---|---:|---|
| candidate (band-10 valley lines) | 0.00446 | [0.00000, 0.00909] |
| single_B (3-band logistic control) | 0.01890 | [0.01211, 0.02703] |
| random (matched budget) | 0.02577 | [0.02325, 0.02817] |

Paired candidate − single_B: **−0.01444 [−0.02491, −0.00620]**. Leakage canary clean: max
fold-level AUC of the field alone 0.495 (alarm 0.90). The candidate is below random because its
15,000 dots clump on a few ridge systems — with no recoverable signal, clumping only concentrates
the placement tax. Committed comparable bar for reference (different fold draw, 53,186 withheld
positives): single_B 0.174517, H61/H64 receipt. Receipt: `evidence/h65b_e2_holdout.json`; the void
first run is kept at `evidence/h65b_e2_holdout_invalid_run1.json`.

**E3 — artefact and gates.** `submission/gems52-h65-band10-valley-15000px-20261009T050550Z.tif`,
82,253 bytes, SHA-256 `eefc7b1210f71872024d057cb09ec88341628bb7d70d7e71c99425c44714fc1e`,
15,000 emitted cells, values exactly {0,1}, 0 NaN, float32, EPSG:32611, shape/transform identical
to the pinned sample. Emission: field-descending greedy, ≥3 px spacing, off-catalogue
(pixel-exact), tier-2 novelty cells skipped (88,946 skips vs the frozen census union);
**13,055 of 15,000 cells (87.0%) are not positive in any of the 593 informative priors of the
full set** (late-collision report: 1,945; the rebuilt prior set includes the parallel rounds
merged to main in the meantime). Run card: `evidence/h65b_run_card.json`.

## 2 · The lane verdict, read honestly

* Surface phase: literal **PASS**, policy **PASS** (max Spearman 0.0416 — the band-10 field
  correlates with no published raster's rank; the drift rule's 0.90 is nowhere near).
* Dots phase: Spearman max 0.0300 (clean) but the near-dot rule fires: the largest informative
  raster has a 3 px halo over 99.2% of the eligible footprint (just under the 0.95 probe bar), so
  0.9005 of this file's dots sit within 3 px of *its* dots regardless of where a candidate emits.
  This is the registry saturation documented in `knowledge/31`; per the parallel-run protocol it
  is logged as DUPLICATE and stopped — **no placement re-tuning was attempted**.
* Two earlier H65 drafts (from crashed builds) initially polluted the prior set; they are parked
  in `work/h65/superseded/` and the build now excludes any prior that is byte- or
  decoded-identical to the candidate. Logged as IR-H65-001 in `registry/irregularities.json`.

## 3 · Limits

* The hide-and-recover instrument cannot rank novel fields (`knowledge/10` §5); every HOLDOUT-DTI
  here is a necessary-not-sufficient gate, never a projected score.
* Holdout prevalence ≈ 1.04% of the footprint vs an estimated 0.12–0.25% true prevalence.
* Band 10's 15° sector azimuth convention is undocumented in any sandbox-obtainable source
  (INGENIOUS `eq_rate_density_details.docx`, GDR 1391 — host not reachable from this sandbox); the
  convention-free valley-line form was frozen for that reason (`knowledge/41` §5).
* E1 refutes the frozen estimator on the named layers only — not the organiser-confirmed
  corrections population, and not better LiDAR parameterisations; those would be new
  pre-registrations.
* The session's 2-hour wall-clock budget was exceeded by gate hygiene (the self-copy fix and the
  site-QA phrase contract), not by extra experiments; three experiments were run in total.
* Local validation is not organiser acceptance. The submit decision belongs to the selector,
  within the weekly cap shown on the submission page.
