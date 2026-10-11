# 07 · Historical revealed-preference reconstruction — conditional, not score authentication

> **Superseded 2026-10-10:** this dated algebra combines restored local bytes with owner-reported scores; it does not recover the hidden truth or establish why an organizer score changed. In particular, the local 0.2600/0.2778-labelled subset relation does not prove that removed pixels had zero credit. DrivenData staff says new-fault truth may occur within 300 m of known traces. The public 0.2778 row is rank 17 in the saved 2026-10-09 20:18 UTC observation, not the board high score, and no file/hash receipt maps it to a score. Use [`knowledge/49`](49_why_02778_phd_answer.md) for current evidence classes and limits.

Recorded 2026-10-06/07. Every number here is reproducible from restored bytes whose SHA-256 is
pinned in `registry/data_manifest.json`, plus owner-reported published scores. Scripts: `work/a3`,
`work/a6`, `work/a9`, `work/a10`, `work/a12`, `work/a13`, `work/a14`; production code in
`src/gems52/revealed.py`.

The local byte sets can be compared exactly, but their score labels remain owner-reported and are not authenticated to the local TIFF hashes. The algebra below is therefore a conditional scenario analysis—not a fit that recovers hidden truth, an organizer-confirmed calibration, or an explanation of why any score changed. The official public board is team-level and does not expose a submission hash or receipt.

---

## 1. The nesting, measured

| relation | measurement |
| --- | --- |
| `A = h33-2-b2` (reported 0.2778) vs `B = gems24-d2-8` (0.2600) | `A \ B` = **0 px**. `A` is a strict subset of `B`. |
| `B \ A` | **6,436 px**, every one of them within **100–200 m** of the mapped catalogue; `min` distance-to-catalogue inside `A` is **223.6 m** |
| `A` vs `E = h19-5` (0.1922) | `A \ E` = **0 px** |
| `B` vs `E` | `B \ E` = **0 px** |
| `C = gems24-d1-5` (0.2477) vs `E` | `C \ E` = **0 px** |
| `C` vs `D = topogap` (0.2449) | `C \ D` = 0, `D \ C` = 1,259 |
| `A` vs `C` | `A \ C` = 12,137, `C \ A` = 34,552 — **not** nested |

The local H33-labelled bitmap is a strict subset of the separate d2-8-labelled bitmap; both are also subsets of a larger local h19-5-labelled emission. These are byte-set relations only. The score/file associations are owner-reported, so do not call the first bitmap “the 0.2600 file” or infer that the set subtraction caused a score change.

## 2. `|G|` is not recovered; the zero-credit ring was an unsupported assumption

The official formula is `DTI = T / (0.2 (T + S − M) + 0.8 |G|)`. The earlier simplification `M = T` and any use of owner-reported score values to solve for `|G|` depend on unverified score-to-file mappings and overlap/hidden-truth assumptions. The local raster and known-fault mask do not provide the hidden new-fault set or the required `M` term:

The historical equations that inverted those owner-reported values are not reproduced as measurements here. They require a correct file-to-score match and assumptions about `M`, hidden-truth overlap, and the evaluation set; those inputs are unavailable. `B \ A` is the locally measured 6,436-cell set at 100–200 m from the known-fault mask. A 200 m catalogue distance does not determine credit: staff confirms new-fault truth may occur within the 300 m scoring kernel. The former `|G| = 14,088.7` value is a conditional algebra result under an unsupported zero-credit assumption and is withdrawn as a measurement or score explanation.

Any purported lower bound derived from leaderboard values also inherits their owner-reported, unauthenticated status and the assumptions of the inversion. It is not an organizer-confirmed interval for hidden `|G|`; this repository does not recover that count from the public board.

The official clarification says the known-fault mask is pixel-exact and only new-fault truth is scored; staff also says new truth may lie within 300 m of a known trace. Therefore, do not treat a 200 m exclusion as universally score-free or describe this pair as a measured +6.8% organizer gain. The exact local bitmap relation is not a score receipt.

## 3. Local atom sizes; hidden-truth credit is unknown

The atoms of `{A, B, C, E}` partition `E` exactly (verified: the six sizes sum to 121,131):

| atom | locally measured cells | organizer-confirmed hidden-truth credit |
| --- | ---: | --- |
| `P1 = A & C` | 25,517 | unknown |
| `P2 = A \ C` | 12,137 | unknown |
| `P3 = (B\A) & C` | 4,332 | unknown |
| `P4 = (B\A) \ C` | 2,104 | unknown |
| `P5 = (E\B) & C` | 30,220 | unknown |
| `P6 = (E\B) \ C` | 46,821 | unknown |

The table records local set sizes only; no per-atom hidden-truth credits, densities, random baseline, or score changes are identified by these pixels. The earlier credit hierarchy and “P1 alone” projection depended on the owner-reported score mapping and assumed hidden-truth/overlap terms. They are retained only as historical conditional arithmetic and are not measured findings.

## 4. Historical score-curve fit (not an independent validation)

`T(S) = 471.6 · S^0.2284` fitted to three family members predicts the other published scores:

| file | S | predicted DTI | reported | error |
| --- | --- | --- | --- | --- |
| `h33-2-b2` | 37,654 | 0.2783 | 0.2778 | +0.2 % |
| `d1-5` | 60,069 | 0.2500 | 0.2477 | +0.9 % |
| `topo-gap-closure` | 61,328 | 0.2484 | 0.2449 | +1.4 % |
| `h19-5` | 121,131 | 0.1925 | 0.1922 | +0.2 % |
| `h19-4` | 123,779 | 0.1901 | 0.1894 | +0.4 % |
| `h16-1` | 123,939 | 0.1900 | 0.1855 | +2.4 % |
| `d2-8` | 44,090 | 0.2700 | 0.2600 | +3.8 % (owner-reported association; includes the additional 6,436 local cells) |
| **`anderson-geothermal-pinn`** (a *different* family) | 38,854 | **0.2767** | **0.2750** | **+0.6 %** |

Those residuals measure agreement with the owner-reported values used for the historical fit, not hidden truth or organizer score authentication. The fit and the atom calculation share the same unverified inputs and assumptions, so their agreement is not independent validation. No value in the table should be treated as an organizer-confirmed score-to-file match.

## 5. What is *not* true: the hide simulator does not predict the organiser's score

`src/gems52/holdout.py` scores a candidate by hiding whole catalogue components and recovering them.
Run over the 13 restored scored files (4 folds each, emission restricted to each fold's legal set,
budget matched):

* Spearman ρ(reported score, simulated DTI) = **−0.1045**, p = **0.734**, n = 13.
* Spearman ρ(reported score, simulated lift over random) = −0.1265, p = 0.680.
* The local H33-labelled raster scores **0.0046** on this internal simulator against **0.0496** for
  mass-matched uniform random: lift **0.09×**. The comparison is HOLDOUT-DTI; the corresponding 0.2778 association is owner-reported, not an organizer-confirmed score-to-file match.
* Ranking by simulated DTI puts `8GEMSDOE_Hedge-v2` first (0.316); its 0.1563 board association is owner-reported and not a hash-linked receipt.

A historical sensitivity check changing the holdout’s 200 m exclusion changed the internal lift from 0.10 to 0.09 (ρ unchanged). This is a holdout-design sensitivity, not evidence about the organizer's hidden set or the near-catalogue cells' public-score contribution.

**Scope:** this internal holdout measures recovery of withheld mapped-catalogue components, not the competition's hidden new-fault truth and not public-board performance. It cannot authenticate or causally explain the 0.2778 report. Any workflow conclusion about a specific promoted artifact must be checked against that artifact's own receipt and preregistration.

## 6. What is *not* true: no feature I can compute re-ranks inside the champion file

Two historical screens, both spatially blocked (10–11 blocks of 4×4 that contain both classes), compared local set partitions from §3; these partitions are not known credit labels:

* **63 point and local-differential features** — the 19 competition bands, their horizontal
  gradients, Laplacians and 5×5 ranges, linearity ratios, all 12 LiDAR scarp bands, the 4
  radiometric bands and 4 ratio bands, and the SGMC layer. Best AUC(`A ∩ C` vs `A \ C`) = **0.5453**
  (`lin_detelev`), sd 0.008; this distinguishes two local bitmap partitions, not credited vs uncredited cells.
* **108 structure-tensor features** — coherence and gradient magnitude at σ = 2, 4, 8 px on 12
  bands. Best AUC(`A ∩ C` vs `A \ C`) = **0.5122**, se 0.0032; again, these are local mask partitions.

The habitat AUCs describe how the local rasters align with surface/geophysical features; without hidden-truth labels, they do not identify which pixels are faults or carry credit. The older “20× less credit” and “exactly-accounted core” interpretations depend on the withdrawn atom-credit model and are not current conclusions. See `knowledge/49` for the score evidence limits.

## 7. What is measurable: strike coherence of the local bitmap

The local raster's emitted-cell arrangement can be measured with a structure tensor, but this geometric statistic does not reveal whether any cell overlaps hidden new-fault truth or earned metric credit. The following coherence values are local morphology diagnostics only.

The dominant orientation of the emitted pixels is measurable from the local bitmap using the structure tensor of its smoothed density:

| smoothing | mean coherence, H33-labelled bitmap | mean coherence, matched uniform-random cloud | lift |
| --- | --- | --- | --- |
| σ = 4 px | 0.531 | 0.362 | 1.47× |
| σ = 6 px | 0.549 | 0.412 | 1.33× |
| σ = 10 px | 0.566 | 0.443 | 1.28× |

and the fraction of dots above coherence 0.8 is **16.8 %** against **2.2 %** for the matched random
cloud — a 7.6× contrast. The local sets `A` and `C` agree on the orientation histogram to cosine **0.9952**, while the random control is flat. This describes geometric pattern similarity only; it does not establish that the pixels are credited.

The measured dominant orientation is **100–110° in array convention** (+x east, +y south), i.e. about
**010–020°** azimuth (NNE–SSW). This is consistent with a regional Basin-and-Range structural
hypothesis, but does not validate the local pixels as faults or establish score credit.

## 8. Withdrawn historical budget projection

The former budget rule assigned priors to `t_core`, `ρ_novel`, and `|G|` using the conditional score inversion above. Its reported `P(DTI > 0.2778)` values in `evidence/revealed_budget.json` are outputs of those assumptions, not empirical probabilities, HOLDOUT-DTI, leaderboard scores, or calibrated forecasts. They are superseded and must not be used to explain 0.2778 or select a competition submission.

## 9. Current limits and acceptance rule

1. The public board is a team-level observation; no organizer-confirmed receipt in this checkout binds a TIFF hash to 0.2778.
2. The local 37,654/44,090 subset and its 100–200 m distance relation do not identify hidden new-fault credit. Official staff says the known-fault mask is pixel-exact, only new-fault truth is scored, and new truth may lie within 300 m of known traces.
3. Any score-derived `|G|`, credit-density, atom-credit, break-even, or budget value in this historical analysis is conditional arithmetic only. It is not hidden-truth measurement or an explanation of an organizer score change.
4. Internal HOLDOUT-DTI must be reported with the evaluator, withheld-positive count, and 95% CI. It is not interchangeable with PUBLIC-LEADERBOARD observation or ORGANIZER-CONFIRMED receipt.
5. Current evidence-classification reference: [`knowledge/49`](49_why_02778_phd_answer.md); irregularity: `IR-R5-011`.
