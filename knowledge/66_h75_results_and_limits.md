# 66 · H75 — results and limits (2026-10-09; terminal amendment 2026-10-10)
> Identifier note: first run as H74 in this session; renamed H75 at merge because a parallel session merged its own H74 to `main` first. Pixels, SHA-256 and every number unchanged.
>
> **Current terminal status (2026-10-10): DUPLICATE/STOP · RESEARCH ONLY · NOT FOR SUBMISSION.** H75 exhausted its authorized experiment budget; the final-dot near-duplicate gate failed and support novelty is 0.0. No owner override, waiver, rerun, placement, build, new run card, or weekly slot is authorized. The historical experiment table below is an audit record, not current permission. The old “Next steps” are superseded. See [`knowledge/49_why_02778_phd_answer.md`](49_why_02778_phd_answer.md) for the corrected 0.2778 evidence classes and non-causal pixel comparison.


Preregistration: `knowledge/65` (+ amendments 65a, 65b, each written before the experiment it governs; the registry
pin `registry/h75_preregistration.json` hashes the ORIGINAL text — the amendments are appended below it, so re-hash
before re-running: IR-H75-002). Runner: `scripts/run_h75.py` (fit/holdout/build), `scripts/h75_gates.py`,
`scripts/h75_lane_place.py`, `scripts/h75_write.py`. Run card: `evidence/h75_run_card.json`.

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
- IR-H75-001: README/landing page promoted H72-v3 as "recommended" although its own holdout (0.031) is **below random
  (0.080)**. Superseded; H72-v3 should not be preferred over H75.
- IR-H75-002: amendments appended to the pinned document change its hash; `run_h75.py` will refuse to run until the pin
  is refreshed (pin refreshed at the end of the round, old hash kept in the registry JSON).
- IR-H75-003: the brief's co-training steps (independence test, A-only reasoning, pseudo-labels) were not re-run: lane
  closed after 5 measured View-A sufficiency failures. There are therefore no A-only candidates to write reasoning for.
- IR-H75-004: single_B differs from the H71 receipt by 5.4e-5 (float/library-level); random reproduces exactly.

## Superseded follow-up ideas — not authorized

The three items that followed the 2026-10-09 run were exploratory suggestions, not registered approvals. They are **not current next steps** and must not be used to reopen H75, alter the duplicate rule, or justify a submission. In particular, excluding registry priors based on owner-reported scores would be an unauthorized rule change. The terminal `DUPLICATE/STOP` stands.

Any scientifically separate future work would require a newly authorized round, a frozen preregistration, restored shared cache support, and the shared holdout protocol before fitting. The 2026-10-10 pre-fit shortlist in [`knowledge/67_cotraining_candidate_shortlist_20261010.md`](67_cotraining_candidate_shortlist_20261010.md) is not authorization and does not make its three proposals distinct or viable. H72-A remains terminal, H72-D data-blocked; G1 cache support and H72-C/H74 distinctness remain unresolved.
