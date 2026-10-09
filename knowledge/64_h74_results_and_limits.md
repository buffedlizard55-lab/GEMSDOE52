# 64 · H74 — results, irregularities, next steps (2026-10-09)

Preregistration: `knowledge/63` (+ amendments 63a, 63b, each written before the experiment it governs; the registry
pin `registry/h74_preregistration.json` hashes the ORIGINAL text — the amendments are appended below it, so re-hash
before re-running: IR-H74-002). Runner: `scripts/run_h74.py` (fit/holdout/build), `scripts/h74_gates.py`,
`scripts/h74_lane_place.py`, `scripts/h74_write.py`. Run card: `evidence/h74_run_card.json`.

## Measured
| Step | Label | Result |
|---|---|---|
| Inputs restored | MEASURED | `scripts/download_competition_data.sh` → ALL_VERIFIED=True (SHA-256 pins) |
| Tests | MEASURED | 435 passed, 1 skipped |
| View-B AUC per fold (single_B) | MEASURED | 0.6625 / 0.7684 / 0.6112 / 0.6952 — identical to H73 receipt |
| B_DVA AUC per fold | MEASURED | 0.6798 / 0.7818 / 0.6445 / 0.7141 (higher in 4/4) |
| Leakage canary (12 DVA channels alone) | MEASURED | max 0.623 < 0.90 → no alarm |
| single_B | HOLDOUT-DTI (v1, 53,186 withheld, 9,400/fold) | 0.174517 [0.152316, 0.196299]; H71 receipt 0.174571, Δ 5.4e-5 |
| **B_DVA** | HOLDOUT-DTI (same) | **0.186352 [0.164675, 0.207868]** — wins 4/4 folds |
| B_DVA − single_B | HOLDOUT-DTI paired | **+0.011835 [0.006791, 0.017362]** → promote rule met |
| DVA_only | HOLDOUT-DTI | 0.165885 [0.147960, 0.184418] |
| random | HOLDOUT-DTI | 0.080426 [0.070223, 0.090973] |
| Surface lane (max Spearman vs 565 priors) | MEASURED | 0.466 → PASS |
| Dots lane, rank | MEASURED | max Spearman 0.108 → PASS |
| Dots lane, near-dot (3 px) | MEASURED | **0.922 > 0.70 → DUPLICATE/STOP** (38 informative offenders) |
| Quota placement K=37,654 / K=30,000 | MEASURED | short fill 35,858 / 28,745; worst 0.735 / 0.731 → infeasible |
| Uniqueness | MEASURED | decoded pattern unique; not equal to the union of priors |
| vs 0.2778 reference | MEASURED | 1,742 shared px of 37,654; Spearman 0.044; 64.2 % of dots within a 7×7 box of a ref dot |

## Verdict
Holdout: first arm in this repo to beat `single_B` with a CI excluding zero. Lane: the literal near-dot rule fails, as it
has for every surface emission since H69 — the registry contains dense priors whose 3 px halos cover most of the
plausible area (a property of the registry, measured twice more here). Per the protocol the file is **research-only**.
Holdout DTI is not a board forecast (repo measured Spearman −0.10 between holdout and board, R4).

## Irregularities
- IR-H74-001: README/landing page promoted H72-v3 as "recommended" although its own holdout (0.031) is **below random
  (0.080)**. Superseded; H72-v3 should not be preferred over H74.
- IR-H74-002: amendments appended to the pinned document change its hash; `run_h74.py` will refuse to run until the pin
  is refreshed (pin refreshed at the end of the round, old hash kept in the registry JSON).
- IR-H74-003: the brief's co-training steps (independence test, A-only reasoning, pseudo-labels) were not re-run: lane
  closed after 5 measured View-A sufficiency failures. There are therefore no A-only candidates to write reasoning for.
- IR-H74-004: single_B differs from the H71 receipt by 5.4e-5 (float/library-level); random reproduces exactly.

## Next steps (ranked)
1. Decide the lane rule: the near-dot gate against 350+ dense priors makes **every** surface emission a "duplicate".
   Restrict the registry to *scored submissions* (owner-reported scores) rather than all 524 published blobs, preregistered.
2. DVA at more lags/bands (bands 15 depth-to-basement, 18 grav HG) and DVA azimuth vs regional NNE Basin-and-Range strike.
3. H67-B antithetic margin asymmetry (band 15).
