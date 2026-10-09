# 45 · Why `h33-2-b2` scored 0.2778, and what it would actually take to beat 0.3195 / 0.3774

Written 2026-10-09 (round H66) in answer to the brief's question: *"Why and how did this get the
highest score and are we able to generate a submission that scores higher than 0.2778?"*

Every number in §§1–4 was **re-measured in this session** from bytes restored through
`scripts/restore_data.py` and verified against `registry/data_manifest.json` (23/23 SHA-256 pins,
0 mismatches — `evidence/h66_preflight.json`). The reproducing script is
**`scripts/h66_board_algebra.py`**; its receipt is **`evidence/h66_board_algebra.json`**. Nothing
here is quoted from a sibling website. Published scores are **OWNER-REPORTED** (the board prints a
team name and a number, never a filename), so every file↔score pairing carries that caveat.
Nothing in this document is ORGANIZER-CONFIRMED.

---

## 1. What the 0.2778 file is — measured, four ways

`data/reference/h33-2-b2-zeros.tif`, 219,065 bytes, SHA-256 `c55bafc470054e8271dcb89347a17e07fefe
50de6af6e6ba6c4b169ef7ab6fa9`, single-band float32, values exactly {0, 1}:

| measurement (this session) | value |
|---|---:|
| emitted pixels | **37,654** |
| pixels within 200 m of a mapped catalogue trace | **0** |
| pixels within 300 m of a mapped catalogue trace | 4.28 % |
| minimum distance to the catalogue | **223.6 m** |
| median distance to the catalogue | 1,964.7 m |
| pixels outside the organiser's domain (`labels.tif == -1`) | 0 |

Set relations to four other owner-scored files, all re-measured this session:

| relation | measurement |
|---|---|
| `ref \ d2_8` (0.2600, 44,090 px) | **0 px** — `ref` is a strict subset |
| `d2_8 \ ref` | **6,436 px**, every one **100.0 – 200.0 m** from the catalogue (median 100.0) |
| `ref \ h19_5` (0.1922, 121,131 px) | **0 px** |
| `d2_8 \ h19_5`, `d1_5 \ h19_5` | **0 px**, **0 px** |
| `d1_5 \ tgc` (0.2449, 61,328 px) | **0 px**; `tgc \ d1_5` = 1,259 px |
| `P1 = ref ∩ d1_5` | **25,517 px** |
| `P2 = ref \ d1_5` | **12,137 px** |

**So the answer to "why did it score highest" is one sentence, and it is arithmetic, not geology.**
`h33-2-b2` *is* the 0.2600 file with its 100–200 m catalogue ring deleted: 6,436 pixels removed,
all of them inside the ring, and the score rose from 0.2600 to 0.2778 (+6.8 % relative). Nothing
else about the file changed. Deleting 14.6 % of the file's mass bought +6.8 % of its score, which is
only possible if the deleted mass earned **zero** credit while still paying the false-positive tax.

## 2. The metric reduced to one usable equation

From the official page (fetched this session,
<https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>): α = 0.2, β = 0.8,
R = 300 m triangular kernel, `p(x) ∈ [0,1]`, single-band float32, EPSG:32611, 100 m, same bounds as
the training data, **null/NaN outside the bounds**. With the identity `FNw = |G| − TPw`
(pinned in `tests/test_metric.py`):

```
DTI = T / ( 0.2·T + 0.2·(S − M) + 0.8·|G| )          T = credited mass, S = emitted mass,
                                                      M = emitted mass within 300 m of truth
```

For a *dot* emission whose dots are separated by more than 200 m, two dots rarely compete for one
truth pixel, so `M ≈ T` and the equation collapses to the form this whole family is scored by:

```
DTI ≈ T / (0.2·S + 0.8·|G|)      and therefore      ρ ≡ T/S = DTI · (0.2 + 0.8·|G|/S)
```

Two consequences, both decisive:

1. **Binary {0,1} is optimal.** For one pixel of weight λ on a truth pixel, `DTI = λk/(0.2λ+0.8)`
   increases in λ ⇒ every accepted pixel should carry 1.0. Continuous "probability" rasters
   forfeit score.
2. **The marginal rule is `ρ_marginal > α·DTI`.** Adding ΔS pixels with ΔT credit raises DTI iff
   `ΔT/ΔS > 0.2·DTI`. At DTI = 0.2778 the bar is **0.0556**; at 0.3774 it is **0.0755**. Because the
   100 m grid makes the kernel take only the seven values 1.000 / 0.667 / 0.529 / 0.333 / 0.255 /
   0.057 / 0 at d = 0 / 1 / √2 / 2 / √5 / 2√2 / 3 px, that bar is a *distance*: emit a pixel iff it
   is within **2.24 px (224 m)** of a fault pixel the catalogue does not already have. The bar barely
   moves between 0.05 and 0.46, so **there is no score-dependent tuning knob — only the ranking
   matters.**

## 3. What each owner-scored file implies about its own credit density

`ρ = DTI·(0.2 + 0.8|G|/S)`, computed at the three |G| brackets this repo has derived
(`knowledge/10` §2 exact-nested-pair value 14,088.7; `knowledge/27` §3 bracket ≈18,000–27,400):

| file | S px | owner-reported DTI | ρ at \|G\|=14,088.7 | ρ at \|G\|=18,000 | ρ at \|G\|=27,400 |
|---|---:|---:|---:|---:|---:|
| **`h33-2-b2`** | **37,654** | **0.2778** | **0.1387** | 0.1618 | 0.2173 |
| `d2_8` | 44,090 | 0.2600 | 0.1185 | 0.1369 | 0.1813 |
| `d1_5` | 60,069 | 0.2477 | 0.0960 | 0.1089 | 0.1399 |
| `tgc` | 61,328 | 0.2449 | 0.0940 | 0.1065 | 0.1365 |
| `h19_5` | 121,131 | 0.1922 | 0.0563 | 0.0613 | 0.0732 |

Reference point: **uniform-random mass over the permitted set has ρ = 0.0279.** The champion is
therefore **5.0× random** — and that, not any geological insight, is what 0.2778 measures.

Applying the metric's own marginal rule to the family's measured ρ(S) curve (same field thinned to
different budgets, so this is one curve, not five points):

| step | ΔS | ΔT | marginal ρ | bar α·DTI | verdict |
|---|---:|---:|---:|---:|---|
| `ref` → `d2_8` | +6,436 | **+0.0** | 0.0000 | 0.0556 | do not add |
| `d2_8` → `d1_5` | +15,979 | +544.5 | 0.0341 | 0.0520 | do not add |
| `d1_5` → `tgc` | +1,259 | −3.5 | −0.0028 | 0.0495 | do not add |
| `tgc` → `h19_5` | +59,803 | +1,058.5 | 0.0177 | 0.0490 | do not add |

**The champion sits exactly at the point where its own field stops paying.** That is the whole
reason it is the family's best file: not a better detector, but the correct stopping point of a
worse one. Across the five files Spearman(mass, board) = **−1.0000** (p < 1e-4, n = 5), which is
this curve seen from the outside.

## 4. The number that answers "can we beat it"

Required credit density `ρ = DTI_target·(0.2 + 0.8|G|/S)` at |G| = 14,088.7:

| budget S | to reach 0.2778 | **to reach 0.3195** | **to reach 0.3774** |
|---:|---:|---:|---:|
| 25,517 | 0.1783 | **0.2050** | 0.2422 |
| 37,654 | 0.1387 | **0.1595** | 0.1884 |
| 44,090 | 0.1266 | **0.1456** | 0.1720 |
| 60,069 | 0.1077 | **0.1238** | 0.1463 |
| 100,000 | 0.0869 | **0.0999** | 0.1180 |
| 121,131 | 0.0814 | **0.0936** | 0.1106 |

(all four columns are read straight out of `evidence/h66_board_algebra.json` →
`required_rho.target_*_G_14088.7`; the 0.464 column is omitted because `knowledge/01`'s 0.464
"ceiling" rests on a |G| bracket that `knowledge/27` §3 superseded.)

Read against §3, three conclusions follow, and they are the answer to the brief's question.

**(a) Yes, 0.2778 is beatable, and the only sub-field with a measured ρ in the required range is
`P1`.** The exact nested-pair interval (`knowledge/10` §3, re-derived there from the same set
relations re-measured here) puts `P1`'s credit at [4,168, 5,223] on 25,517 px, i.e.
**ρ ∈ [0.163, 0.205]**, so `DTI(P1 emitted alone) ∈ [0.2546, 0.3190]`, central 0.3139.
**Its upper bound, 0.3190, is below 0.3195.** So even the best-accounted object in this family
cannot be *shown* to beat the brief's stated bar, and it is nowhere near 0.3774. This is a
measurement, not a mood.

**(b) The family's low-mass doctrine is not a law of the metric — it is a property of one field.**
The required ρ *falls* with budget (0.1595 at 37,654 px vs 0.0999 at 100,000 px). A detector that
could hold ρ ≈ 0.10 out to 100,000 px would score 0.3195, and that is a *lower* precision demand
than the champion's own 0.1387. The reason the family emits 37,654 px is that its ranker's marginal
ρ collapses to 0.018–0.034 beyond that (§3). **The binding constraint is the ranker's ρ(S) decay,
not the budget.** Anyone who treats "emit less" as the lesson of 0.2778 has read the wrong variable
out of it.

**(c) What would actually beat 0.3774.** Sustained ρ ≈ 0.19 at 37,654 px, or ρ ≈ 0.12 at 100,000 px,
or equivalently covering ≈ 84 % of |G| at 100,000 px. That is a **better detector**, and this repo
has measured, seven separate ways, that it does not have one: no point or local-differential feature
re-ranks inside the champion file (63 channels, best AUC 0.5453 — N-10); no structure-tensor feature
does either (108 channels, best 0.5122 — N-11); every potential-field transform sits at AUC ≈ 0.52
(N-6, N-22); every blend of the two views is ≤ View B alone (N-16); disagreement as a rank modulator
is worse than no modulation (N-17); SGMC off-catalogue lines score *below* uniform random
(0.0512 at 44k px ⇒ ρ = 0.0234 < 0.0279); and 13 public scores cannot be inverted for the truth
(IR-H60-004). The honest statement is that **0.3774 is not reachable from anything measured in this
repository today**, and the leader most plausibly holds either a 1 m-LiDAR-derived detector (aliased
away at the 100 m cell this competition scores on) or a manually curated trace set.

## 5. Two structural facts about the prize that change what to optimise

Both were read from the official problem page this session and are not in the earlier notes:

1. **The public board is not the scored set.** "The GeoDAWN region is chunked and split into a public
   test set and a private test set. Competitors' performance against the public test set is shown on
   the public leaderboard." The **Initial Prize Round ($50,000)** is scored on the **private** test
   set at close. Every number in the brief's score list — 0.3774, 0.3195, 0.2778 — is a *public-chunk*
   number. Optimising against them is optimising against a subset we cannot see, with n = 13
   observations that this repo has already shown cannot be inverted (IR-H60-004).
2. **The Final Prize Round ($250,000) rescores the same file against an EXPANDED label set:**
   "Initial Prize Round labels *plus* previously-unknown faults that experts verify after reviewing
   *every team's* submission. Predictions that helped experts identify previously-unmapped faults can
   score higher here than in the Initial Prize Round." Competitors must choose **one** submission for
   both rounds before the deadline, without knowing private performance.

Consequence for strategy, and it is the strongest argument in this document: **the $250k round pays
for expert-verifiable candidates, not only for DTI.** A file whose every emitted cluster carries
written geological reasoning and an explicit falsifier is worth more in round two than a file with a
marginally better public-chunk DTI and no reviewable rationale. That is why this repo writes an
A-only reasoning record per candidate even in rounds it does not promote, and it is where a
small team can compete with a large one.

## 6. What this means for the H66 candidate

`|G|` and the algebra above are the reason the H66 verdict is what it is. H66-A is a wholly novel
emission (the parallel-run lane rule forbids re-emitting `P1`: any subset of `P1` has 100 % of its
dots within 3 px of an existing registry raster, so it is a lane duplicate by construction). For a
novel field, §4 gives the expectation directly: at S = 24,907 and ρ ~ U[0.0279, 0.1387],

```
DTI = ρS / (0.2S + 0.8|G|),  S = 24,907:
      |G| = 14,088.7 → denominator 16,252 → DTI ∈ [0.0428, 0.2126]
      |G| = 18,000.0 → denominator 19,381 → DTI ∈ [0.0359, 0.1782]
      |G| = 27,400.0 → denominator 26,901 → DTI ∈ [0.0258, 0.1284]
```

**A fully novel file is expected to score below the 0.2778 champion, and the shortfall is the price
of the uniqueness rule, not a defect of the geology.** That is stated before the holdout, in the
frozen protocol (`knowledge/43` §1 rank 1, "Expected gain, and the honest bracket"), and the measured
holdout (`evidence/h66_holdout.json`) is worse than that again: H66-A is significantly below uniform
random on the shared instrument. Both facts point the same way — **do not spend a weekly slot on it.**

## 7. Ranked list of what would move the number, by measured evidence

| # | lever | evidence | expected effect |
|---|---|---|---|
| 1 | Never emit within 200 m of a mapped trace | measured on organiser-scored bytes: +6.8 % relative (§1) | free, already applied |
| 2 | Emit {0,1}, never a continuous probability | metric algebra, §2 | free, already applied |
| 3 | Stop where marginal ρ crosses α·DTI | §3, four consecutive steps | free, already applied |
| 4 | Raise the ranker's ρ(S) so the stop point moves right | §4(b): ρ 0.10 at 100k px = 0.3195 | **the only lever that reaches 0.32+** |
| 5 | Written, falsifiable reasoning per candidate | official Final-Round rule, §5 | $250k round, not the DTI |

Lever 4 needs data this sandbox cannot fetch: the competition's own `1m_DEM_links.csv` tiles
(USGS 3DEP, public domain, <https://www.usgs.gov/3d-elevation-program>). At a 100 m scoring cell the
1 m expression of a fault scarp is aliased into the `lidar_scarp_features_u8` product the owner's CI
already reduced (706 of 716 tiles), which is the reachable substitute and is already in View B. The
unreachable part is any *new* reduction at native resolution — named here as the specific free,
official source that would be required, and checked: **not obtainable from this sandbox** (bash egress
is limited to github.com / codeload / api.github.com / pypi.org; `www.usgs.gov` and
`www.drivendata.org` are reachable only through the agent's page-fetch tool, which cannot stream
gigabytes of tiles).
