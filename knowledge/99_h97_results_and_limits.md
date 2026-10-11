# 99 · H97 results and limits — potential-field directional anisotropy (PAF-DVA) as View A

Round **H97**, executed 2026-10-11 UTC. Preregistration `registry/h97_preregistration.json`
(SHA-256 `b2eb593fe5ebed40…`, amendment **h97a** included) + `knowledge/97_hypotheses_H97_preregistered.md`
(SHA-256 `d603fe73580af36b…`), both frozen before any fit; the runner refuses to start if either hash moves.
Every number below is read from `evidence/h97_*.json` or from the official page named beside it.

**Verdict: NEGATIVE · download YES · submit NO (research candidate) · submission slots used 0.**

---

## 1 · The one-sentence result

The H82 directional-semivariance operator, moved onto the **potential-field / subsurface** bands, does not
give View A any usable signal on the hide-and-recover instrument (mean out-of-quadrant AUC **0.5206**, fold 2
**0.4578** — anti-informative), so the co-training **disagreement** field built from it scores **below
random** on held-out catalogue faults; the same operator on the **surface** bands reproduces the family's
best-known single-view number (0.185968 against H82's 0.189200).

## 2 · Channels (reused operator, new band assignment)

| | bands | channels |
|---|---|---|
| **View A** (potential field / subsurface) | 13 `iso_grav_anom`, 18 `iso_grav_anom_hg`, 2 `rtp`, 15 `depth_to_base_surf` | 4 × 5 lags × 2 stats = **40** |
| **View B** (surface) | 12 `det_elev`, 19 `det_elev_slope` | 2 × 5 lags × 2 stats = **20** |

Operator `run_h82._gamma_stats`, **imported, not forked**: 8-direction integer fan, σ = 3.0 px,
lags 1/2/3/4/6 px (100–600 m), `aniso = (max−min)/(max+min)`, `logvar = log10(mean)` of the Gaussian-smoothed
semivariance. Band 6 (radiometric total count) was excluded from the operator **in advance**
(`excluded_by_design` in the preregistration) because an airborne gamma-ray count grid carries
flight-line striping that is directional by construction. Built in 181 s; 60 columns; the byte-integrity
`save_verified` guard reported **0 torn writes** (`evidence/h97_channels.json`).

## 3 · HOLDOUT-DTI (`gems52-pooled-hide-v1`, 53,186 withheld positive px, 9,400 dots per fold per arm)

| arm | HOLDOUT-DTI | 95 % CI |
|---|---:|---|
| `single_B2` (surface anisotropy) | **0.185968** | [0.164050, 0.207066] |
| `union_max` | 0.156667 | [0.136724, 0.177147] |
| `consensus` | 0.130332 | [0.112807, 0.148948] |
| `random` (same budget, same allowed set) | 0.081592 | [0.071379, 0.092512] |
| `single_A2` (potential-field anisotropy) | 0.076396 | [0.061925, 0.091881] |
| `buried_only` (A confident, B abstains) | 0.035883 | [0.027300, 0.045060] |
| `cotrain_disagree` — **pre-registered primary** | **0.029460** | [0.021158, 0.039756] |

Paired differences (primary − arm, 1,000 paired physical-cluster bootstrap draws):

| comparison | Δ | 95 % CI |
|---|---:|---|
| − `single_B2` | −0.156508 | [−0.179085, −0.134737] |
| − `union_max` | −0.127207 | [−0.146727, −0.107592] |
| − `consensus` | −0.100872 | [−0.117495, −0.084996] |
| − `random` | **−0.052132** | [−0.061283, −0.043039] |
| − `single_A2` | −0.046936 | [−0.059079, −0.034508] |
| − `buried_only` | −0.006423 | [−0.010717, −0.001630] |

Frozen promotion test: paired CI lower bound above zero against the best comparable control → **FAIL**
(−0.179085), and the pooled value is far below the standing bar 0.190147 → **not promoted**.

**Three honest readings.**

1. **The disagreement arm is worse than random, and the CI excludes zero.** Averaging two views' percentile
   ranks when one of them (View A) carries anti-information is not neutral: it actively drags the field
   *below* a uniform draw. This is the sharpest version of the warning in the brief — "co-training can also
   amplify bias" — measured rather than asserted.
2. **`single_B2` (0.185968) is within the H82 control tolerance of the best single-view field this repository
   has measured** (`B_DVA2` 0.189200; `single_B` control target 0.174517). The operator, the store columns
   and this runner therefore reproduce the family's best-known surface performance **with 2 bands instead of
   5** — a useful positive control for the pipeline, and a *negative* control for View A.
3. **View A fails the sufficiency gate for the eighth consecutive time.** Mean out-of-quadrant AUC per fold:
   0.5011, 0.5995, 0.4578, 0.5238 (mean 0.5206; gate mean ≥ 0.60, min fold ≥ 0.55). Directional texture was
   the last untried operator family on the potential field; it does not rescue it. This is now strong enough
   evidence to stop spending rounds on View A as a *learner input* and to treat it only as a veto/context
   layer.

## 4 · Leakage canary, independence, and the two registered diagnostics

* **Canary** (every channel alone, direction-insensitive AUC on the held-out region): maximum **0.6217**
  (fold 2, `DVA2_det_elev_slope_logvar_l3`); worst per fold 0.5666 / 0.5976 / 0.6217 / 0.5801; alarm bar
  0.90 → **no alarm**.
* **Independence** (the brief's mandated test — spatial-block correlation of the two views' out-of-fold
  errors on labelled negatives; thresholds inherited verbatim from `registry/h74_preregistration.json`,
  not re-tuned): **max |ρ| = 0.1732 over 2,089 blocks** (4,095,103 labelled-negative predictions), abandon bar
  0.60 → **method not abandoned on this test**. The instrument's own caveat stands: the negatives are
  held-out *catalogue-zero proxies*, not verified absence, so this is not proof of conditional independence.
* **Budget diagnostic (does not select the budget — amendment h97a)**: primary-arm DTI per fold rises
  monotonically with the per-fold budget — fold 0: 0.0124 → 0.0242 → 0.0387 for 9,400 → 16,000 → 25,400;
  fold 3: 0.0513 → 0.0808 → 0.1188. It also rises for the **random** control (0.0816 pooled at 9,400 vs the
  primary's 0.0295), which is the cleanest demonstration yet that this instrument rewards *coverage* rather
  than skill and must not be used to choose emitted mass. Amendment h97a froze the artifact at 37,600 dots
  (= 4 × 9,400), the family standard, for exactly this reason.

## 5 · The artifact

`submission/gems52-h97-pafdva-disagree-37600px-20261011T002233Z.tif` — 132,324 bytes, SHA-256
`cf035c83a651d90b0b920c52ce0e894b8666839d73b6f53f41a7a995f57bf326`. Submission name
`h97-pafdva-disagree-37600px-20261011T002233Z`; note (118/140)
`H97 co-training: View-A potential-field anisotropy x View-B DEM anisotropy; disagreement field, 200m ring excluded, binary 37600 dots`.

| gate | result |
|---|---|
| on-disk validator (`gems52.gates.format_report`, independent re-read) | **PASS** — 1 band float32, EPSG:32611, 3730×3292, transform/bounds = `sample_submission.tif`, **0 NaN, 0 inf**, values exactly {0.0, 1.0}, 37,600 cells = 1, no nodata tag |
| lane, surface | **PASS** — max Spearman 0.1207 (bar 0.90), 81 informative priors, 1 universal-coverage probe |
| lane, dots | **PASS, but close** — max near-3px fraction **0.6595** against `submission/gems52-h61-deepsharp-cotrain-37600px.tif` (bar 0.70); max Spearman 0.0677. Flagged as IR-H97-005 |
| uniqueness (`gems52.gates.uniqueness_report`) | **PASS** — 82 priors checked, canonical pattern unique, identical to none |
| not merely the union of the two views | **PASS** — Jaccard vs the union-max placement 0.0159; 0 cells shared with `single_B2`; 2,938 shared with `single_A2`; not a subset of the union |
| placement | 37,600 cells at 3 px minimum spacing inside 4,325,298 px of pool; nearest cell to the mapped catalogue **223.6 m**; median **2,816 m**; only **2.15 %** of the mass within 300 m of a mapped fault (the 0.2778 champion: 5.77 %) |
| A-only geological reasoning | one row per emitted cell: `submission/gems52-h97-pafdva-disagree-37600px-20261011T002233Z-a-only-reasoning.csv` (37,600 rows, 20.3 MB), naming the fired components, the alternative non-fault processes and the falsifier for each |
| **submit_ok** | **false** — the frozen promotion rule failed |

## 6 · What this round adds to the knowledge base

1. **The last untried View-A operator family is now measured and closed.** Eight rounds, eight sufficiency
   failures. View A should be demoted to a context/veto layer in future rounds, which is a *saving*, not a
   defeat: every co-training round so far has spent most of its budget on a view that cannot clear the gate.
2. **A disagreement field built on an at-chance view is worse than random** (Δ −0.052, CI excludes 0). The
   brief's bias-amplification warning is now quantified on this instrument.
3. **The surface anisotropy operator reproduces the family's best number with 40 % of the channels**
   (0.185968 with 20 channels vs 0.189200 with 50). If a future round needs a cheap strong baseline, this is it.
4. **The instrument rewards coverage, not skill** — the random control improves with budget exactly as the
   primary arm does.
5. **`knowledge/98` is the strategic deliverable of this session**: the organiser's metric is a *coverage*
   metric (a swath covering a trace scores 0.88 where sparse dots score far less; the marginal bar at
   DTI 0.2778 is 0.0556, so any cell within ~283 m of an uncovered truth pixel pays for itself), and the
   family has spent eight rounds optimising the ranking while its *emission geometry* — dots at 3 px spacing —
   was inherited by convention and never measured. Round **H97-E4** measures it.

## 7 · H97-E4 / E4b — the emission-geometry question, answered twice

Every round to date emits `nodes.spacing_select` dots at 3 px minimum separation. E4 and E4b are the first
measurements in this repository of the *other* axis of a submission: not which cells the field likes, but what
shape the emitted mass has. Both run on the same shared instrument (`gems52-pooled-hide-v1`, 4 folds,
53,186 withheld positive px) and both compare the geometry against **dots at the same emitted mass** *and*
against **random placement at the same mass** — the second control is mandatory because §4 of the coverage
note shows this instrument pays for mass almost regardless of where it lands.

E4 (`scripts/run_h97_e4_coverage.py`, `evidence/h97_e4_coverage.json`) — *naive bridging*: connect
neighbouring confident cells with straight segments, then resample to the matched budget.

| field | dots @ 9,400 | bridged @ matched mass | dots @ matched mass | random @ matched mass | Δ (bridged − dots@S) |
|---|---:|---:|---:|---:|---:|
| `cotrain_disagree` (primary) | 0.029460 | 0.024497 | **0.201789** | 0.178690 | −0.1773 [−0.1932, −0.1611] |
| `single_B2` | 0.185968 | 0.153403 | **0.254062** | 0.176328 | −0.1007 [−0.1149, −0.0853] |

E4b (`scripts/run_h97_e4b_hysteresis.py`, `evidence/h97_e4b_hysteresis.json`) — *hysteresis growth*: seed at
the top 2 % of the field, then grow the region geodesically (3×3) while the local field rank stays above the
0.85 quantile, at most 12 dilate steps, so the trace only follows ground the field still likes.

| field | dots @ 9,400 | hysteresis @ S | dots @ matched mass | random @ matched mass | Δ (hyst − dots@S) | Δ (hyst − random@S) |
|---|---:|---:|---:|---:|---:|---:|
| `single_B2` | 0.185968 | 0.144522 (449,433 px) | **0.248644** | 0.196093 | −0.1041 [−0.1212, −0.0885] | −0.0516 [−0.0686, −0.0359] |
| `cotrain_disagree` | 0.029460 | 0.021537 (416,560 px) | **0.238451** | 0.196837 | −0.2169 [−0.2319, −0.2016] | −0.1753 [−0.1890, −0.1617] |

**Answer: no measured geometry gain, by either construction, on either field.** The two independent
constructions agree, so this is not an artefact of one operator: on this instrument, emitted mass spent as
*more well-separated dots* beats the same mass spent as *connected traces*, and it also beats random
placement by only ~0.05 DTI on the best field. Both registered falsifier branches triggered.

What that does **not** say: it says nothing about the real leaderboard, where the truth set is off-catalogue
and the 200 m collar around the mapped catalogue is *not* excluded from the scoring region. A trace that
follows a mapped fault's strike into unmapped ground is exactly the shape a real submission might want, and
this instrument cannot see it: its truth *is* the catalogue, so a cell placed on a mapped fault is already
near-truth, and its mass is 4× the competition's prevalence (`knowledge/76` §6). The geometry question is
therefore **closed on the instrument and open on the board**, and the only way to reopen it here is a
prevalence-matched off-catalogue instrument (`knowledge/100` §2).

Consequences recorded in `knowledge/100_next_round_proposals.md`: the "coverage emission / hysteresis trace"
candidate is **falsified as ranked** and demoted; the prevalence-matched instrument moves up to rank 1
because it is the prerequisite for testing emitted mass and emission geometry at all.

## 8 · Limits

* The hide-and-recover instrument withholds **catalogue** faults, which were mapped from surface expression;
  the competition scores faults the catalogue lacks. This repository has measured that the instrument does
  not rank leaderboard performance (Spearman ≈ −0.10 over R4), so a holdout number is never a board forecast.
* The lane census covers the **locally available** registry (82 unique rasters, 70 before this round's file):
  `data/scored` (12 restored scored priors), `data/reference`, this repository's `submission/` artefacts and
  `docs/downloads/*.tif`. The full 526-blob cross-repository census lives in a git-ignored receipt and was
  not re-fetched inside this round's time box (**IR-H97-003**).
* **IR-H97-005**: 65.95 % of this file's cells lie within 3 px of the H61 deepsharp co-training file
  (bar 0.70). Both are disagreement fields over the same feature store, so overlap is expected; it is
  reported because it is within 4 points of the lane rule. A quota placement (`run_h73.place_lane`) is the
  standard remedy and is listed for the next round.
* **§7's geometry answer is instrument-bound.** Both E4 and E4b place *mapped* catalogue faults as truth and
  exclude the ≤200 m collar around them, which removes precisely the cells a trace-shaped submission is
  supposed to reach (unmapped ground along a mapped fault's strike). The finding "dots beat traces at equal
  mass" is therefore a statement about this instrument, and must not be quoted as a statement about the
  competition. Until the prevalence-matched off-catalogue instrument exists, emitted mass and emission shape
  remain **unmeasurable here**, which is why no submission slot was spent and why the site says NOT OK TO SUBMIT.
* No new external data was used. **GDR 1391 two-metre temperature probes** (DOI 10.15121/1881483, CC BY 4.0)
  remain the highest-ranked unexplored channel and are **not reachable from this sandbox**
  (`gdr.openei.org` is not on the egress allowlist): the owner must download that file once into
  `data/external/` with a SHA pin before it can be used.

## 9 · Sources verified this round

* Metric, scoring example, submission format, round structure —
  <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/> (fetched 2026-10-10)
* Public leaderboard (rank 1 = 0.3774; rank 8 = 0.3195; rank 22 = 0.2778) —
  <https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/> (fetched 2026-10-10)
* Blum & Mitchell, COLT 1998 — <https://doi.org/10.1145/279943.279962>
* Reference solution — <https://github.com/drivendataorg/gems-prize-reference-solution>
* USGS GeoDAWN (DOI 10.5066/P93LGLVQ) —
  <https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and>
* INGENIOUS / GDR 1391 (DOI 10.15121/1881483) — <https://gdr.openei.org/submissions/1391>
* EPSG:32611 — <https://epsg.io/32611>; Tversky index — <https://en.wikipedia.org/wiki/Tversky_index>
