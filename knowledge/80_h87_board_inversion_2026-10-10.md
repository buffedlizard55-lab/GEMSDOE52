# H87 — Inverting thirteen owner-reported board scores for the hidden truth density, and placing dots by the metric's own marginal rule

Date 2026-10-10. Round H87. Branch `arena/e0990020-gemsdoe52`. Budget: 3 experiments / 2 hours; this
round overran the wall-clock budget (≈2 h 05 m) because two defects in the placement tool and one
sandbox OOM had to be found and fixed before the emission was trustworthy. The overrun is recorded
here rather than hidden.

Receipts: `evidence/h87_board_inversion.json`, `evidence/h87_emit.json`,
`evidence/h87_realisation_scores.json`, `evidence/h87_holdout.json`,
`evidence/h87_gates.json`, `evidence/h87_write_receipt.json`,
`evidence/h87_reasoning_receipt.json`, `evidence/h87_run_card.json`.
Code: `scripts/run_h87_board_inversion.py`, `scripts/run_h87_uniform_control.py`,
`scripts/run_h87_build.py`, `scripts/publish_h87_site.py`, and the shared tool
`gems52.nodes.marginal_greedy` (+ `tests/test_nodes.py`).

## 1. The question

Every previous round in this repository chose a hypothesis, chose a budget, and scored the result on a
hide-and-recover instrument that does not rank board scores here (Spearman ≈ −0.10, IR-H77-005). H87
asked the inverse question: **what must the organiser's hidden truth look like for the thirteen
owner-reported public-board scores in `registry/h82_scored_registry.json` to be what they are?**

The metric is exactly linear in the truth density once each file's cover field is known:

    s_i = <g, M_i> / (0.2*S_i + 0.8*|G|),   M_i(x) = k(EDT to file i's dots),   k(d) = max(1 - d/300 m, 0)

Thirteen scores are thirteen equations in `g`, and `|G|` — the number of hidden truth pixels, which
this repository has never been able to measure directly — is one of the unknowns. With
`g = sum_j w_j B_j` over mass-normalised bases (`|B_j| = 1`, so `|G| = sum_j w_j`) the equations are
linear in `w`:

    sum_j w_j (<B_j, M_i> - 0.8 s_i) = 0.2 s_i S_i

solved by non-negative least squares, reweighted into score space (each row divided by
`0.2 S_i + 0.8 |G|`, iterated, because `|G|` appears on both sides).

## 2. Result 1 — a third independent pin on |G|, the hidden truth mass

**BOARD-CALIBRATED: |G| = 14,333.8 truth pixels.**

| method | |G| | class |
|---|---|---|
| H67 two-score ring-deletion fit | 14,088.7 [13,953–14,226] | BOARD-CALIBRATED |
| lattice near-full-coverage inversion | 12,367 | BOARD-CALIBRATED |
| **H87 NNLS on 13 scores** | **14,333.8** | BOARD-CALIBRATED |

Three independent routes now agree that the hidden truth is a **low-mass** set: 14,334 pixels out of
5,167,373 footprint pixels (0.28%), not the 60,988 catalogue pixels and not the 22,820-pixel
`T_cat` of any single submission. Leave-one-out over the 13 files: **MAE 0.02007, RMSE 0.02843,
max |error| 0.07114, Spearman 0.9436** (all in board-score units).

Leave-one-out per file (observed → predicted, error):

    0.0107 -> 0.01832 (+0.00762)  PLACEHOLDER (196,132 of its dots are outside the footprint)
    0.0904 -> 0.10247 (+0.01207)  r13-lattice-s5  (the geometry-known calibration raster)
    0.1280 -> 0.12504 (-0.00296)  h25-ctx-ridge
    0.1563 -> 0.12776 (-0.02854)  8GEMSDOE_Hedge-v2
    0.1563 -> 0.09949 (-0.05681)  gemsdoe-ens12-adopted
    0.1839 -> 0.17310 (-0.01080)  h28-dotted-ridge
    0.1855 -> 0.18872 (+0.00322)  h16_1
    0.1894 -> 0.19624 (+0.00684)  h19_4
    0.1922 -> 0.19965 (+0.00745)  h19_5
    0.2449 -> 0.26445 (+0.01955)  gems27_tgc_v2_d15
    0.2477 -> 0.26575 (+0.01805)  d15_scored
    0.2600 -> 0.27586 (+0.01586)  d28_unscored
    0.2778 -> 0.20666 (-0.07114)  h33-2-b2 champion   <-- the largest error, and the worst file to miss

**The model cannot predict the best file.** When the 0.2778 champion is held out, the family-consensus
basis rebuilt from the other six members under-predicts it by 0.071 — 26% of its score. Any claim
built on "the fitted density knows where the truth is" must be read against that number.

## 3. Result 2 — a negative, and the important one

Fitted mass by basis (primary8 = uniform, catalogue, 100–300 m ring, SGMC-off, LiDAR step+coherence,
radiometric K-high, A-confident/B-abstains disagreement, gravity step, plus the family consensus):

    FAM_family_consensus  9,937.8   (69.3%)
    CAT_catalogue         4,396.0   (30.7%)
    everything else           0.0

**Weight zero:** `U_uniform_offcat`, `RING_100_300m`, `SGMC_offcat`, `LIDAR_step_coh`, `RAD_K_high`,
`DIS_A_confident_B_abstains`, `GRAV_step`. A thirteen-basis fit (adding `LIDAR_ex_lapneg`,
`RAD_ThK_low`, `DIS_B_confident_A_abstains`, `VIEWA_top`, `COVER_step_basement`) returned an
**identical** solution — same `G_fit`, same LOO MAE, same two non-zero weights (log line quoted
verbatim under `extended13_omitted` in the receipt; it is not re-run in the final execution because
13 bases + 13 leave-one-out family bases exceeded the 3.9 GB sandbox and were OOM-killed before the
receipt could be written).

So: **the board evidence contains no measurable preference for any physical layer** — not gravity
steps, not LiDAR scarps, not radiometrics, not seismicity, not basement depth, not conductivity, and
not either co-training disagreement mask. What it prefers is *where the owner's own earlier files
were*, plus a modest catalogue component. This is a negative result about the hypothesis class this
repository has been mining for eighty-odd rounds, obtained from the organiser's own scoring function
rather than from a proxy instrument.

## 4. Result 3 — the budget is derived, not chosen

`gems52.metric` part (ii): adding a dot of exact marginal credit `c` raises DTI iff `c > 0.2*DTI`.
That is now a shared tool, `gems52.nodes.marginal_greedy`, with tests — not a private script:

* exact marginal gain field, `gain(p) = sum_x g(x) max(0, k(d(x,p)) - C(x))`, over the 29 lattice
  offsets inside the 300 m disc (no separable shortcut, no approximation);
* a multi-scale separation schedule (6 px → 5 px → 3 px). At 6 px two dots' kernel discs are
  disjoint, so their gains are exactly additive and the within-round prefix test is exact rather than
  stale;
* per-round rollback whenever the exact recomputed DTI falls, so the objective is monotone by
  construction;
* `mass_outside_allowed`, for truth mass that exists but cannot be emitted (here the 4,396 units on
  catalogue pixels): it contributes nothing to `T` but does contribute to `FNw`, so it belongs in the
  acceptance bar. Leaving it out silently lowers the bar and over-emits.

Two real defects were found by calibration and are now regression tests:

1. **A stale within-round gain field saturates the minimum separation.** The first version added a
   maximal 3 px-separated set per round, every gain computed against the pre-round cover. On a uniform
   density it stopped at a 3.07 px lattice with DTI 0.0643 where the metric's own optimum is ≈5 px at
   ≈0.09.
2. **Raster-order tie-breaking builds a square packing.** The one board score whose geometry is fully
   known — `data/scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif`, 206,895 dots, NN median
   5.00 px, 99.85% of the footprint within 300 m of a dot, mean cover 0.3748, OWNER-REPORTED 0.0904 —
   is a *staggered* packing. A square packing at the same NN distance leaves ≈5% of the area outside
   the kernel and averages ≈0.32 cover. A hexagonal tie-break (`nodes.hexagonal_tiebreak`) recovered
   ≈8% of achievable DTI in the uniform control.

**Uniform-truth control** (`scripts/run_h87_uniform_control.py`, a 1000×1000 window around the
catalogue centroid, 709,005 allowed px, ρ = 0.00290894/px): the rule self-terminates at **24,557
dots, 5.373 px equivalent spacing, mean cover 0.2278**, predicted DTI **0.10010** against the pinned
raster's OWNER-REPORTED **0.0904** — a **+10.7%** relative error, same regime, correct order of
magnitude. The residual is disclosed rather than tuned away: the greedy's irregular packing reaches
mean cover 0.2278 where the pinned staggered lattice reaches 0.3748, so the control is *sparser and
less efficient per dot* than the raster it is checked against, and the two errors partly cancel. A
perfect-lattice emitter would be the clean next step.

## 5. The emission, and the saturated registry

Arms, all under the same fitted density, the same 200 m catalogue-ring cut and the same marginal rule:

| arm | density | dots | PREDICTED-BOARD DTI | lane, literal / policy (max near-3px) |
|---|---|---|---|---|
| A | fitted `g` directly | 42,746 | 0.22517 | 0.99939 / 0.99020 → DUPLICATE/STOP |
| B | fitted region × physical within-region rank | 61,427 | 0.17898 | 0.99920 / 0.90439 → DUPLICATE/STOP |
| C | fitted `g` under a 3 px registry keep-out | — | infeasible | see below |

Arm B is emitted: it is decoded-unique against every local prior and it is the arm measured on the
shared instrument. Its PREDICTED-BOARD value is 0.046 below arm A's — that difference **is** the
measurement of what the physical re-ranking is worth inside the board-revealed region, and it is
negative, consistent with §3's zero weights.

**Irregularity IR-H87-001 — the literal lane rule is unsatisfiable for any non-empty emission in this
study area.** The 13 owner-scored rasters carry 1,008,050 dots between them; their 3 px halos cover
**5,612,293 px = 108.6% of the footprint**, leaving **1,983 px of the 4,927,499 px allowed ring
(0.04%)**. So ">70% of dots within 3 px of one registry raster ⇒ duplicate, STOP" fires against every
hypothesis, including a random one, and arm C cannot be built. This is the H61 saturated-registry
situation and IR-H85-009 measured on the scored registry specifically. It is reported with its numbers
and a random-emission control on the same priors (`evidence/h87_gates.json →
lane_dots.random_control`, `lane_dots.probe_controls`); it is **not** waived, and it is not used as a
licence to re-place a lane. Submission stays NO.

## 6. HOLDOUT-DTI on the shared instrument

Evaluator `gems52-pooled-hide-v1`, **60,894 withheld positive pixels**, 9,400 dots per fold per arm,
3 px spacing, 80 m buffer, label-blind quadrants, 1,000 paired cluster-bootstrap draws, seed 8701.
Implementation hashes are in `evidence/h87_holdout.json`.

| arm | HOLDOUT-DTI | 95% CI |
|---|---|---|
| candidate (board-fitted density) | **0.104228** | [0.084119, 0.124875] |
| random, same budget and spacing | 0.075375 | [0.067081, 0.083962] |
| **paired difference** | **+0.028853** | **[+0.014804, +0.043810]** — excludes zero |

Per fold: 0.003118 / 0.151246 / 0.218554 / 0.194599 against random 0.041666 / 0.064025 / 0.148026 /
0.106023. **Fold 0 loses** (29,297 of the 60,894 withheld positives sit there) and folds 1–3 win
large; the pooled win is driven by three of four folds and is not uniform. Comparable to H86 (same
60,894 withheld, random 0.0754, candidate 0.0694) and to H85's random 0.080426; **not** directly
comparable to H84/H82's 0.190147/0.189200, which used an eligible mask that withheld 53,186 positives.

Leakage caveat, stated before the number is used: the mixture weights were fitted from owner-reported
board scores of files that were themselves built with full-catalogue knowledge, and the non-label bases
were masked with the global catalogue. Inside a fold the two explicitly label-derived populations
(`CAT`, `RING`) are removed, the emission is restricted to the fold's own region and visible-catalogue
collar, and the budget and spacing are fixed — so no held-out truth pixel is readable at placement
time — but the weights themselves are global. This HOLDOUT-DTI is descriptive, not a clean
generalisation estimate.

## 7. PREDICTED-BOARD cross-check (a consistency test, never a forecast)

Exact `metric.dti` of each pattern against three binary truth realisations drawn from the fitted
density (Gumbel top-k, |G| pixels, probability ∝ g), same draws for every pattern:

| pattern | emitted | PREDICTED-BOARD | owner-reported |
|---|---|---|---|
| **H87 candidate** | 61,427 | **0.19841** [0.19795, 0.19890] | — |
| `h33-2-b2` champion | 37,654 | 0.23948 [0.23580, 0.24308] | 0.2778 |
| `d28_unscored` | 44,090 | 0.28080 [0.27738, 0.28350] | 0.2600 |
| `h19_5` | 121,131 | 0.21251 [0.21024, 0.21396] | 0.1922 |
| `r13-lattice-s5` | 206,895 | 0.10122 [0.10111, 0.10140] | 0.0904 |
| `PLACEHOLDER` | 343,816 | 0.00919 [0.00902, 0.00937] | 0.0107 |

The realisation check reproduces the two files whose behaviour is geometrically simple (lattice +0.011,
PLACEHOLDER −0.0015) and **inverts the top of the ladder** (it ranks `d28` 0.2808 above the champion
0.2395, where the board ranks the champion 0.2778 above `d28` 0.2600). Paired against the champion on
the same draws the candidate is **−0.04107**. So on the model's own terms this candidate is *worse
than the file that already scored 0.2778*, and the model itself is not reliable at the top of the
range. Both facts are reasons not to submit; neither is a reason to doubt the |G| pin, which is a
scale and agrees with two independent methods.

## 8. Why `h33-h33-2-b2-…-zeros` scored 0.2778, and can it be beaten (updated)

Unchanged from `knowledge/49` and H85/H86, plus one new number: the 0.2778 file is 37,654 binary
cells, no NaN, EPSG:32611, a jittered/thinned ≈3 px lattice whose nearest catalogue trace is 223.6 m,
a strict subset of the 44,090-cell 0.2600 file; the 6,436 deleted 100–200 m ring cells earned zero
marginal credit. H87 adds the mechanism-level reading: at |G| = 14,334 the champion's implied credit
density is ≈8× uniform at its own coverage, and the fitted density says the remaining headroom is not
in any physical layer we have measured but in *being in the same region more efficiently* — i.e. in
packing quality (staggered vs square, §4) and in the budget, not in a new detector. The thinning
ladder has not converged (Spearman(S, score) = −1.000 over the five nested files), and the arithmetic
still says S ≈ 15–28 k is the open lever. Beating 0.2778 needs a *denser-credit* region, and the only
region the board supports is the one the registry already saturates (§5).

## 9. What is new relative to the repository

* the first inversion of owner-reported board scores for the hidden truth **density** (H67 inverted
  two scores for two scalars; H87 inverts thirteen for a spatial field and for |G| jointly);
* the metric's marginal acceptance rule as a **shared, tested placement tool** with a derived budget,
  replacing hand-chosen `S` (37,654 / 9,400 / 141,678 px in previous rounds);
* the measured proof that the literal lane rule is unsatisfiable on the scored registry (108.6% halo
  coverage), which settles IR-H85-009 with a number instead of an argument;
* a board-scale negative for the entire physical-layer hypothesis class (§3), obtained from the
  organiser's scoring function rather than from the holdout proxy.

## 10. Limitations and next steps

1. **The density is mostly a mirror.** 69.3% of the mass is the mean cover of the owner's own scored
   ladder, and that ladder is nested (0.2778 ⊂ 0.2600 ⊂ 0.2477 ⊂ 0.1922). A leave-one-out basis
   rebuilt from the other six members of a nested family is strongly collinear with the target it must
   predict, so LOO MAE 0.02007 overstates how much the model would know about an unseen file. The
   |G| pin is robust (three methods agree); the *shape* of the density is not.
2. **Not run:** a fit with the family basis excluded (the ablation that would separate "geology" from
   "submission history"); a |G| sweep of the emission over the pinned interval [12,300, 14,100] — the
   bar `0.2*DTI` moves with |G|, so the self-terminated budget moves with it; a perfect-lattice
   emitter to close the 10.7% control gap; any organiser upload.
3. **The co-training lane stays closed.** View independence passes (max |ρ| 0.1333 over 2,089 blocks
   against a 0.60 bar) but View A sufficiency is refuted seven times (mean OOF AUC 0.5113). H87 ships
   transparent rank composites and their disagreement masks as ranking and reasoning inputs, and does
   not re-open a pseudo-label exchange. `registry/h77cond_preregistration.json`,
   IR-H85-010 (owner decision).
4. **Instrument mismatch stands** (IR-H77-005): the holdout hides catalogue faults, the board scores
   faults the catalogue lacks. The +0.0289 paired win over random is real on the instrument and says
   nothing about the board.
5. **Attribution is not organiser-confirmed anywhere**: two different byte patterns share the score
   0.1563 in the owner-reported registry, and this repository has never uploaded a file.
