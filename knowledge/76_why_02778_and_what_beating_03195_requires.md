# 76 — Why `h33-h33-2-b2` scores 0.2778, and what beating 0.3195 actually requires

Every number below is **measured from bytes on disk** or **derived from the organiser's published
metric**. Nothing here is a model of the hidden labels, and nothing here is a leaderboard
forecast. Where an assumption is needed it is named, bounded, and the answer is given across the
whole assumption interval.

Sources: the metric transcription in `src/gems52/metric.py` (pinned by
`tests/test_metric.py` against the organiser's own worked example) from
https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric ;
the champion raster `data/reference/h33-2-b2-zeros.tif` (SHA-256 pinned in
`registry/data_manifest.json`, integrity-pinned not organiser-authenticated); the twelve
owner-reported scores in `knowledge/75_current_user_brief_2026-10-10_H83.md`.

---

## 1. What the champion file is, measured

| Property | Measured value |
|---|---|
| Container | single-band float32, `deflate`, **tiled 256**, `nodata = None` |
| Finite / non-finite | 12,279,160 finite, **0 non-finite** |
| Distinct values | **2** — exactly {0, 1} |
| Emitted mass `S` | **37,654** (all 37,654 positive pixels carry value 1.0) |
| Minimum distance from an emitted pixel to the mapped catalogue | **223.6 m** (= √(200² + 100²), i.e. the ≤ 200 m ring is deleted) |
| Share of mass within 300 m of the mapped catalogue | **5.77 %** |
| Median distance to the mapped catalogue | 1,965 m |
| `M` = Σ p·q against `labels.tif` | 277.9, i.e. **0.74 %** of its mass is inside the kernel of a *mapped* fault |

Two consequences, both important:

* The champion is a **`-zeros` file** — all-finite, no NaN, no nodata declaration. That settles the
  packaging argument empirically: the all-finite container `gems52.grid.write_geotiff` produces
  **is the container the current champion itself used**. The NaN-outside template container also
  scores (eleven of the twelve scored priors use it), so both are accepted; only the all-finite one
  cannot fail a literal `[0, 1]` range test under a reader that ignores nodata.
* The champion emits **almost entirely far from every mapped fault** (0.74 % of its mass inside the
  300 m kernel of `labels.tif`). It is not rediscovering the catalogue. Whatever credit it earns, it
  earns on structure the catalogue does not have.

## 2. The metric, reduced to the two quantities that matter

With `T = TPw`, `S = Σ p`, `M = Σ p·max_g k(d)` and `FNw = |G| − T` identically,

```
DTI = T / ( 0.2·(T + S − M) + 0.8·|G| )
```

In the "clean" case where each emitted pixel's best truth weight is the same weight that truth pixel
credits back (`M = T`), this collapses to

```
DTI = T / ( 0.2·S + 0.8·|G| )
```

`|G|` is not identifiable as a point from public bytes. It is bracketed: `T ≤ |G|` gives
`|G| ≥ 5,949` px, monotone credit on the nested pair `d15 ⊂ gems27_tgc_v2_d15` gives
`|G| ≤ 12,512` px, and a weaker nested pair gives the non-binding upper bound 14,088.7 px used by
earlier rounds in this repository (correction H62-4 / IR-H62-005). Everything below is stated across
that whole interval.

## 3. What 0.2778 implies, and what 0.3195 requires

Assuming `M = T` (stated assumption; if `M > T` the required `T` rises, if `M < T` it falls):

| `|G|` assumed | `T` implied by the champion's 0.2778 | `T` required for 0.3195 | required ÷ implied | champion density | required density |
|---|---|---|---|---|---|
| 5,949 px (lower bound) | 3,414.2 | 3,926.7 | **1.1501** | 9.07 % | 10.43 % |
| 8,000 px | 3,870.0 | 4,450.9 | **1.1501** | 10.28 % | 11.82 % |
| 10,000 px | 4,314.5 | 4,962.1 | **1.1501** | 11.46 % | 13.18 % |
| 12,512 px (upper bound) | 4,872.7 | 5,604.2 | **1.1501** | 12.94 % | 14.88 % |
| 14,089 px (incumbent bracket) | 5,223.2 | 6,007.2 | **1.1501** | 13.87 % | 15.95 % |

The ratio is **1.1501 at every `|G|`** — it is independent of the unknown, which is the useful part.
Read two ways:

* **Credit density.** At `|G| = 14,089` the champion earns `T = 5,223` from 37,654 emitted pixels, a
  credit density of **13.87 %**. Beating 0.3195 at the same budget needs **15.95 %** — **+15.0 %
  more credit per emitted pixel**.
* **Budget discipline.** Holding `T = 5,223` and `|G| = 14,089` fixed, `DTI = 0.3195` requires
  `S = 25,384` px. The same credit delivered with **32.6 % less mass** reaches the bar.

The second reading is not a trick: the marginal rule derived in `src/gems52/metric.py` says an
emitted pixel pays for itself only if its incremental credit beats `0.2·DTI·(1 − q) / (1 − 0.2·DTI)`,
which at `DTI = 0.2778` and `q ≈ 0` is **≈ 0.0589**, i.e. the pixel must lie within
`300 × (1 − 0.0589) ≈ 282 m` of a hidden fault. Every pixel emitted beyond that is paying the
false-positive tax and earning nothing.

## 4. The board already says mass hurts — measured

Across the twelve owner-reported scores whose rasters are restored here:

| Emitted mass `S` | Score |
|---|---|
| 37,654 (champion `h33-2-b2`) | 0.2778 |
| 44,090 (`d2-8`) | 0.2600 |
| 60,069 (`d1-5`) | 0.2477 |
| 61,328 (`topo-gap-closure`) | 0.2449 |
| 69,281 (`h28-dotted-ridge`) | 0.1839 |
| 121,131 (`h19-5`) | 0.1922 |
| 123,779 (`h19-4`) | 0.1894 |
| 123,939 (`h16-1`) | 0.1855 |
| 172,974 (`ens12-adopted`) | 0.1563 |
| 174,232 (`h25-ctx-ridge`) | 0.1280 |
| 206,895 (`r13-lattice-s5`) | 0.0904 |
| 227,507 (`Hedge-v2`) | 0.1563 |
| 343,816 (`2314b599`) | 0.0107 |

**Spearman(mass, score) = −0.928** over twelve files; log–log elasticity
`d ln score / d ln S = −0.37`. Mass is the single strongest measured predictor of score in this
family — stronger than any detector choice this repository has made. Along the champion → `d2-8`
link specifically, the local elasticity is **−0.42**, so extending that line to 0.3195 implies
`S ≈ 26,982` px: **the champion is very likely over-emitting by 28–33 %.**

That is the highest-value untested lever in this project, and it is cheap: it needs no new data and
no new detector, only a willingness to ship a smaller file. The reason it has not been done is that
nobody can certify that the champion's ranking concentrates credit at the top — which is exactly the
kind of thing an off-catalogue instrument could test if its prevalence matched the real one.

## 5. Why the champion's edge does not obviously generalise — this round's measurement

Round H83 built `gems52-offcatalogue-v1` (SGMC fault pixels ≥ 300 m from `labels.tif`) and the
amended `gems52-offcatalogue-b-v1` (cut 0 px, extensions included), and scored seven arms on both
at a matched budget of 9,400 dots per fold. Lift over the random control at the same budget:

| Instrument | `single_B` | `random` | **lift** |
|---|---|---|---|
| `gems52-pooled-hide-v1` (catalogue faults) | 0.174571 | 0.080426 | **+0.0941** |
| `gems52-offcatalogue-b-v1` (off-catalogue, cut 0 px) | 0.107456 | 0.073864 | **+0.0336** |
| `gems52-offcatalogue-v1` (off-catalogue, cut 300 m) | 0.090632 | 0.083641 | **+0.0070** |

The surface detector — the same view that every file in the champion family is built from — retains
**7 % of its skill** when the faults it must find are ones the competition catalogue does not have
and are more than 300 m from anything it does have. Including the near-catalogue extension
population (cut 0 px) recovers some of it, but still only a third.

So the honest answer to "can we generate a submission that scores higher?" is: **the arithmetic is
known and it is not a detector problem alone.** The 0.04 gap is reachable either by +15 % credit
density or by −33 % mass, and the board's own history says the mass lever is the stronger of the
two. But the detector side is where the project is stuck, because the population the board rewards
is the one this repository's best view is nearly blind to.

## 6. A limit of the new instrument, stated against it

`gems52-offcatalogue-v1`'s truth is 55,562 px and `…-b-v1`'s is 70,629 px, against an estimated
`|G| ≈ 14,000` px — roughly **4× the real prevalence**. Prevalence moves the optimal budget, so the
instrument over-rewards recall. Measured: on `gems52-offcatalogue-v1` the DTI of the stitched
out-of-fold View-B field rises monotonically from 0.0193 at 5,000 dots to **0.2123 at 150,000 dots**
(`evidence/h83_budget_curve.json`), which contradicts the board's monotone *decrease* of score with
mass. Therefore:

* the off-catalogue instruments are valid for **ranking detectors at a matched budget** (which is
  how round H83 used them), and
* they are **not valid for choosing the budget**, and no budget in H83 was chosen with them.

Fixing this — thinning the off-catalogue truth to the estimated prevalence, or reweighting it — is
the first thing the next round should do, because a prevalence-matched off-catalogue instrument
would be the first tool in this repository able to test the mass lever in §4 without spending a
submission slot to do it.

## 7. One-paragraph answer

`h33-h33-2-b2` scores 0.2778 because it is the 0.2600 surface field with the ≤ 200 m ring around the
mapped catalogue deleted: 6.3 % of the mass removed for +6.8 % score, which is free precision,
because a masked pixel can never earn credit and always pays the false-positive tax. It is not a
better detector — the same 37,654 px emitted incoherently scores 0.0778, 3.6× worse. Beating 0.3195
needs, at that budget, a credit density of 15.95 % instead of the champion's 13.87 %; equivalently,
the champion's own credit delivered in 25,383 px instead of 37,654. Across the twelve scored priors
in this family, Spearman(mass, score) = −0.93, so the cheapest unspent lever is **shipping less**,
and the reason it is unspent is that no instrument here could certify that the champion's ranking
concentrates credit at the top. This round built the first instrument that measures the *right
population* and used it to show that the surface view retains only 7 % of its skill there — which is
why the detector lever is hard, and why the mass lever is where the next gain most likely lives.
