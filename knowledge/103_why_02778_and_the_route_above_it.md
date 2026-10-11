# 103 · Why `h33-h33-2-b2` scored 0.2778, and whether this project can beat 0.3195

Written 2026-10-10 (session H99/H100, branch `arena/f57253db-gemsdoe52`). **Every number in §1 was
re-measured by this session from the bytes on disk in `data/reference/h33-2-b2-zeros.tif`** — not
copied from an earlier note. §2–§3 are closed-form algebra on the organiser's published metric. §4–§5
are this session's own HOLDOUT-DTI measurements. Nothing here is a leaderboard forecast, and nothing
here is a model of the hidden labels.

---

## 0 · The answer in one paragraph

`h33-2-b2` is not a better *detector* than its siblings; it is the same dotted-ridge field with a
**200 m annulus around every mapped fault deleted**, emitted as 37,654 binary dots on a
**3 px-spaced lattice** (the metric's own max-cover scale) in an **all-finite container**. Under the
published metric that combination maximises *credited mass per unit emitted mass*: the dots earn
`T ≈ 5,223` of credit from `S = 37,654` emitted pixels, a **credit density of 13.87 %**. Its two
siblings in the same family that emitted more mass scored *lower* (44,090 px → 0.2600; 60,069 px →
0.2477). The discovery is not a new geological signal — it is **precision under the metric's own
marginal rule**, plus the removal of the ring where the false-positive tax is highest.

**Can we beat 0.3195?** Only by raising credit density by 15 % or cutting mass by 33 % at fixed
credit (§3). This session measured the best available lever in the mandated co-training lane and it
did **not** raise credit density (§4–§5). The honest answer is: **not demonstrated, and this
repository's own instruments cannot demonstrate it, because they score a different population than
the competition does** (§6).

---

## 1 · The champion file, re-measured this session

Source: `data/reference/h33-2-b2-zeros.tif`, restored from the owner's mirror
`buffedlizard55-lab/GEMSDOE32` and SHA-256-pinned in `registry/data_manifest.json`
(`c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9`, 219,065 bytes).
Integrity-pinned, **not organiser-authenticated** (the portal is login-walled).

| Property | This session's measurement |
|---|---|
| SHA-256 | `c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9` — matches the manifest pin |
| Container | single-band float32, `deflate`, **tiled 256**, `nodata = None` |
| Grid | shape (3730, 3292), EPSG:32611, transform origin (243350.0, 4508550.0), 100 m cells |
| Finite / non-finite | **12,279,160 finite, 0 non-finite** |
| Distinct values | **exactly two: {0.0, 1.0}** |
| Emitted mass `S` | **37,654** (every positive pixel is 1.0) |
| Nearest mapped catalogue trace | **223.6 m** minimum; **0** pixels within 200 m |
| Mass within 300 m of the mapped catalogue | **5.77 %** (2,171 pixels) |
| Median distance to the mapped catalogue | **1,964.7 m** |
| `M = Σ p·max_g k(d)` against `labels.tif` | **277.9** = 0.74 % of its mass |
| Nearest-neighbour dot spacing | **median 3.0 px, minimum 2.828 px** |

Every one of those rows agrees with the repository's earlier records (`knowledge/76` §1). Two
consequences matter:

1. It is a **`-zeros` file**: all-finite, no NaN, no nodata declaration. The all-finite container
   therefore cannot fail a literal `[0,1]` range test on the portal — which is exactly the error the
   owner hit ("Predicted values must be in range [0, 1]") when a NaN-outside file was uploaded.
2. It emits **almost entirely away from every mapped fault** (0.74 % of its mass inside a mapped
   fault's kernel). Whatever credit it earns, it earns on structure the catalogue does not show.

## 2 · The metric, reduced to the two quantities that decide the ranking

From the organiser's *Problem description → Performance metric*
(<https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric>),
transcribed literally in `src/gems52/metric.py` and pinned by `tests/test_metric.py` against the
organiser's own worked example (which evaluates to **0.6026516673**, printed as 0.60):

```
k(d) = max(1 − d/300 m, 0)                       (triangular, R = 300 m)
TPw = Σ_g max_{x: d≤R} p(x)·k(d)      FPw = Σ_{x: p>0} p(x)·[1 − max_g k(d)]
FNw = |G| − TPw   (identically)
DTI = TPw / (TPw + 0.2·FPw + 0.8·FNw)
```

With `T = TPw`, `S = Σ p`, `M = Σ p·max_g k(d)`:

```
DTI = T / ( 0.2·(T + S − M) + 0.8·|G| )            and if M = T:   DTI = T / (0.2·S + 0.8·|G|)
```

The **marginal** rule (from the same module's docstring) is what makes the champion beat its
siblings: an added pixel helps only if

```
c·(1 − 0.2·DTI) > 0.2·DTI·f
```

For a *fully* false-positive pixel (`f = 1`) at DTI 0.2778 the required credit is
`0.2·0.2778 / (1 − 0.2·0.2778) = 0.05882`; with `k` triangular that is a distance of
`300 × (1 − 0.05882) ≈ 282 m`. **Every emitted pixel further than ≈ 282 m from a hidden fault pays
the false-positive tax and earns nothing.** That single inequality explains the whole leaderboard
pattern: mass beyond 282 m is pure cost.

## 3 · What 0.2778 implies, and what 0.3195 requires — re-derived this session

Two owner-reported scores with two unknowns. Identifying assumption, stated: the 6,436 pixels deleted
between `d2-8` (44,090 px, 0.2600) and `h33-2-b2` (37,654 px, 0.2778) earned **zero** credit, so `T`
is the same for both and only `S` changes. Solving:

```
0.2778·(0.2·37654 + 0.8·|G|) = 0.2600·(0.2·44090 + 0.8·|G|)
→ |G| = 14,088.7 px          T = 0.2778·(0.2·37654 + 0.8·14088.7) = 5,223.1 px
```

Rounding both scores to four decimals brackets this: **|G| ∈ [13,953, 14,226]**, `T ∈ [5,192, 5,255]`.
The published page says the hidden set is faults *not contained within the current public USGS
database*, so `|G|` cannot be read off `labels.tif`; the solver is not a test, and only one of its
assumptions has independent support (`|G| = 14,088.7` agrees with the value `knowledge/10` reached by
a different route).

The ratio that matters is **independent of the unknown**:

| `|G|` assumed | `T` implied by 0.2778 | `T` required for 0.3195 | ratio |
|---|---:|---:|---:|
| 5,949 (lower bound) | 3,414.2 | 3,926.7 | **1.1501** |
| 8,000 | 3,870.0 | 4,450.9 | **1.1501** |
| 10,000 | 4,314.5 | 4,962.1 | **1.1501** |
| 12,512 (monotone-credit upper bound) | 4,872.7 | 5,604.2 | **1.1501** |
| 14,088.7 (two-score solve) | 5,223.1 | 6,007.2 | **1.1501** |

Two equivalent routes to 0.3195:

* **credit density.** At `|G| = 14,089`: champion `T/S = 5,223/37,654 = 13.87 %`; the bar needs
  6,007/37,654 = **15.95 %** — **+15.0 % credit per emitted pixel**.
* **mass discipline.** Holding `T = 5,223` and `|G| = 14,089`: `DTI = 0.3195` requires
  `S = (T/0.3195 − 0.8·|G|)/0.2 = ` **25,384 px** — that is **32.6 % less mass** for the same credit.

Both routes require the same thing: *more credit per unit of mass*. Placement alone cannot supply it,
because the repository has already measured that the thinning ladder `h19_5 → d1_5 → d2_8 → h33-2-b2`
retains 0.766 of credit where the geometric optimum is 0.798 — within 4 % of the best any placement
of that field can do. **Beating 0.3195 needs a detector whose top-ranked pixels are closer to the
hidden faults than the current field's are. That is a detector problem.**

## 4 · What this session measured on the mandated co-training lane (H99)

The brief's method paragraph mandates: View A = potential-field/subsurface; View B = surface DEM
curvature/slope plus any radiometric bands in `training_features.tif`; the discovery signal is
**disagreement**. The repository's own history is that its View A has failed *sufficiency* eight
times (mean spatial-block OOF AUC 0.5163) while its View B sits at 0.684 — i.e. the Blum & Mitchell
precondition ("each sufficient") is violated on the geophysical side, and independence (which keeps
passing, max |ρ| 0.13–0.15) has nothing to donate.

H99 therefore asked the only actionable question: **can View A be made sufficient by changing its
representation from amplitude to boundary texture?** It computed directional variogram anisotropy
(DVA) on bands never used for DVA in this repository — **2 `rtp`, 9 `tmi_vg`, and 6 (radiometric
total count by bytes, IR-H85-005)** — preregistered as `knowledge/101` and pinned in
`registry/h99_preregistration.json` *before the first fit*.

**Result — HOLDOUT-DTI, evaluator `gems52-pooled-hide-v1`, 53,186 withheld positive pixels, 1,000-draw
paired physical 20 km spatial-cluster bootstrap (153 resampled clusters)** (`evidence/h99_holdout.json`):

| arm | HOLDOUT-DTI | 95 % CI | paired difference vs the primary [95 % CI] |
|---|---:|---|---|
| `xtex_dis` — **primary**, A-confident ∧ B-abstains | **0.034799** | [0.026938, 0.044011] | 0 (reference) |
| `xtex_agree` — consensus `min(A,B)` | 0.128009 | [0.112310, 0.143335] | −0.093211 [−0.107202, −0.078695] |
| `single_Atex` — View A texture alone | 0.081910 | [0.069143, 0.095862] | −0.047111 [−0.056514, −0.037718] |
| `single_Btex` — View B texture alone | 0.164883 | [0.145264, 0.183945] | −0.130084 [−0.149840, −0.110301] |
| `random` — floor, same allowed set | **0.080426** | [0.070223, 0.090973] | **−0.045627 [−0.054106, −0.037194]** |

(The paired column is `primary − that arm`, so the last row is the primary against the random floor.)
The random control reproduces the committed H82/H85 receipt **0.080426 exactly**.

* View A sufficiency, held-out-region AUC per fold: **0.5275, 0.5339, 0.4929, 0.5724** (mean
  **0.5317**) — **the ninth consecutive failure**, one fold below chance.
* View B sufficiency: **0.6812, 0.7500, 0.6713, 0.6848** (mean **0.6968**).
* Independence (the brief's own test: spatial-block mean errors on labelled negatives, 200 px = 20 km
  blocks): ρ = **+0.4285, +0.3464, −0.0950, +0.4510**; **max |ρ| = 0.4510** — below the brief's 0.90
  abandon bar and below the repository's stricter 0.60 bar. **The views are not strongly correlated.**
* Leakage canary: max single-channel AUC **0.5977**, bar 0.90 — no alarm.

**Reading, and this is the answer to "can we beat it":** the disagreement arm is *strictly worse than
random* — the 95 % CI of the paired difference lies entirely below zero, which is the strongest form
of negative this repository has produced. That is not a surprise once the AUCs are on the table: an
emission that ranks `A − B` is dominated by `B`'s complement, and `B` is the only view carrying
signal. Co-training amplifies bias exactly as the brief warns it can.

## 5 · H100 — is it the scale rather than the view?

H99's lags were 1–3 px = **100–300 m**. A fault buried under cover is a *deep* boundary, and the
sensitivity of a potential-field boundary texture to source depth grows with the lag. H100
(`knowledge/102`, preregistered before its first fit) re-ran the identical instrument with
`lags_px = [4, 6, 8]` = **400–800 m** and View A extended to the brief's own ingredients — adding
band 11 `iso_grav_anom_vg`, band 15 `depth_to_base_surf`, band 17 `cond_surf` — while View B was held
unchanged in composition. Frozen decision rule: H100-L is supported only if `xtex_dis`'s paired
difference against `random` has a CI whose lower bound is above zero.

**Result — same instrument, 53,186 withheld positive pixels** (`evidence/h100_holdout.json`):

| arm (H100) | HOLDOUT-DTI | 95 % CI | paired vs primary [95 % CI] |
|---|---:|---|---|
| `xtex_dis` — **primary** | **0.034697** | [0.026536, 0.043153] | 0 (reference) |
| `xtex_agree` | 0.121582 | [0.107204, 0.137463] | −0.086884 [−0.101257, −0.074418] |
| `single_Atex` | 0.074913 | [0.061878, 0.087712] | −0.040215 [−0.050002, −0.030530] |
| `single_Btex` | 0.152616 | [0.133818, 0.170412] | −0.117918 [−0.135790, −0.099863] |
| `random` | 0.080426 | [0.070223, 0.090973] | **−0.045728 [−0.052841, −0.038856]** |

View A sufficiency at 400–800 m lags: held-out-region AUC **0.5368, 0.5529, 0.4913, 0.5327** (mean
**0.5284**) — statistically indistinguishable from H99's short-lag **0.5317**. Independence
max |ρ| **0.4455**; leakage canary max **0.5950**.

**H100-L is therefore NOT supported**, and the frozen decision rule closes the "wrong scale"
explanation. Together the two rounds establish, on this footprint and this instrument, that the
potential-field/subsurface view carries **no measurable catalogue-fault signal in either of the two
representations tested** (amplitude — the repository's nine prior failures — or directional-variogram
boundary texture) **at either lag family** (100–300 m or 400–800 m). The brief's disagreement arm
cannot donate from a donor that is not sufficient, and it does not: both rounds put the primary
strictly below the random floor with a CI that excludes zero.

## 6 · Why this repository's instruments cannot certify a board-beating candidate

The holdout hides **catalogue components** and asks the model to recover them. The competition scores
faults the catalogue **lacks**: the organiser masks known USGS/INGENIOUS pixels (DrivenData staff,
thread 11516 posts #2 and #4: the mask is pixel-exact, no buffer), and the truth set is exactly the
faults *not contained within the current public USGS database*. These are different populations, and
this repository has already measured that its holdout DTI and the public board are **not correlated**
(Spearman −0.10, IR-H77-005). The champion is the proof: 99.26 % of its mass sits outside every
mapped fault's kernel, i.e. it wins on the population the holdout cannot see.

An off-catalogue instrument was built for precisely this (`gems52-offcatalogue-v1`: truth = SGMC
pixels ≥ 3 px from `labels.tif`, 55,562 pooled px). On it, **every** arm this repository has tried
collapses to ≈ 0.0657. So the honest statement is not "the file would score zero on the board"; it is
**"this project currently has no instrument that can rank two candidates against the population it
is actually scored on, and no detector that measurably locates that population."**

## 7 · The route above 0.3195, stated as three falsifiable requirements

Ranked by expected value, with the measured blocker for each:

1. **A detector that ranks off-catalogue faults above the catalogue-free fields** (the only route to
   +15 % credit density). *Blocker:* no such detector exists here; every unsupervised structural field
   measured at or below random on both instruments. Highest-value specific candidates, none yet
   tested: (a) the **INGENIOUS GDR 1391 2-m temperature survey** (DOI 10.15121/1881483, CC BY 4.0) —
   an *independent, non-geophysical* layer that no round has ever loaded, blocked only by the sandbox
   egress allowlist and obtainable by an operator-side download with a SHA pin; (b) **seismicity
   lineation texture** on bands 10/16; (c) a **cover-step detector** on band 15.
2. **An instrument tied to the scored population** — the off-catalogue instrument needs to be
   sharpened beyond "everything ≈ 0.0657", or a fresh, independently mapped fault set (e.g. a
   published Quaternary-fault compilation that post-dates the organiser's public snapshot) needs to
   be brought in as an external truth proxy. Without this, any promotion decision is blind.
3. **Mass discipline at fixed credit** (the −33 % route). *Measured blocker:* placement headroom is
   already within 4 % of the geometric optimum for the current field, and the metric's marginal rule
   caps the useful radius at ≈ 282 m — so this route cannot pay unless requirement 1 is met first.

**Bottom line, honestly:** the unique TIF this session ships is **research-grade, format-valid and
lane-clean, and its preregistered primary is a strict negative**. It is *not* approved for a
competition slot, and the site says so in the first screen. Beating 0.3195 requires requirement 1 or
2 above; nothing already in this repository satisfies either.
