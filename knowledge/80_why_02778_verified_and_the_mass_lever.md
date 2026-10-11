# 80 · Why `h33-h33-2-b2` scored 0.2778, and the arithmetic of beating it — re-measured from the restored bytes

Written in the H88 session (2026-10-10). Every number in §1–§3 is **measured this session from the
restored raster bytes** with `rasterio`/`numpy` (script: the inline block recorded in
`evidence/h88_prior_measurements.json`). The score→file mapping is **owner-reported** (the public
board prints team names, not filenames — `registry/leaderboard_snapshot_2026-10-10.json`), so every
score below is labelled `OWNER-REPORTED`, never `ORGANIZER-CONFIRMED`.

Sources (all official / primary):

* Metric definition and submission format:
  https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
* Public leaderboard (team-level, retrieved 2026-10-10): #1 0.3774, #8 0.3195, #22 0.2778
  https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/
* Champion raster, restored SHA-256-pinned from the owner's mirror
  (https://github.com/buffedlizard55-lab/GEMSDOE32 → `docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif`),
  SHA-256 `c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9`, 219,065 bytes.
  **Integrity-pinned, not organiser-authenticated** (`registry/data_manifest.json`).
* Blum & Mitchell (COLT 1998), the co-training premise: https://doi.org/10.1145/279943.279962

---

## 1. What the champion raster *is*, measured

| property | measured value (this session) |
|---|---|
| shape / CRS / transform | 3730 × 3292, EPSG:32611, 100 m — matches `sample_submission.tif` |
| distinct values | **2** — exactly {0.0, 1.0}; binary emission is optimal, see §2(ii) |
| emitted mass `S` | **37,654** cells |
| minimum distance to `labels.tif` | **223.6 m** (2.236 px) → the ≤ 200 m ring is genuinely deleted |
| share of mass within 300 m of the mapped catalogue | 5.77 % |
| median distance to the mapped catalogue | 1,965 m |
| `M` = Σ p·max_g k(d) against `labels.tif` | **277.9** cells (0.74 % of its mass inside the kernel of a *mapped* fault) |

Read together: the highest-scoring file in this family is **almost entirely off-catalogue**. Whatever
credit it earns, it earns on structure the current public USGS/INGENIOUS catalogue does not contain —
which is exactly the population the organiser says is scored ("faults not contained within the current
public USGS database", problem-description page).

## 2. The metric, and the three consequences that decide this project

With `R = 300 m`, `α = 0.2`, `β = 0.8`, `k(d) = max(1 − d/R, 0)`, and `T = TPw`, `S = Σ p`,
`M = Σ p·max_g k(d)`:

```
DTI = T / ( 0.2·(T + S − M) + 0.8·|G| )      because FNw ≡ |G| − T
```

(i) **Placement is a first-order term, not a detail.** `S − M` is a tax: mass farther than 300 m from
any hidden-fault pixel, *or* mass whose nearest truth pixel is already better covered by another
emission, pays `0.2` per unit and earns nothing.

(ii) **Binary emission is optimal.** For a single pixel of weight λ at kernel weight k,
`DTI = λk/(0.2λ + 0.8)`, which is increasing in λ, so the optimum on any accepted pixel is λ = 1.
The champion's `{0,1}` container is not a quirk; it is the optimum of the published formula.

(iii) **The marginal acceptance rule is `credit > α·DTI`** (`metric.credit_bar`, test-pinned). At
`DTI = 0.2778` the bar is **0.0556**; on the 100 m grid the kernel takes the seven values
1.000, 0.667, 0.529, 0.333, 0.255, 0.057, 0.0, so six of seven weights clear the bar and the largest
accepting distance is 2√2 px = **283 m**. Every emitted dot must therefore sit within ≈ 283 m of a
hidden fault to be worth emitting, and within ≈ 224 m to be comfortable at a higher score.

## 3. The mass lever, measured over every scored raster this repository can restore

Thirteen rasters (the champion + the 12 scored owner files) with their owner-reported scores. Mass
`S` is re-measured from bytes; the scores are the ones the owner reported on submission pages
(`knowledge/75`, `knowledge/76`).

| file (this repo / mirror) | emitted mass `S` (measured) | OWNER-REPORTED score |
|---|---:|---:|
| `h33-2-b2-zeros` (champion) | 37,654 | **0.2778** |
| `d2-8` | 44,090 | 0.2600 |
| `d1-5` | 60,069 | 0.2477 |
| `topo-gap-closure-t-v2-on-d1-5` | 61,328 | 0.2449 |
| `h28-dotted-ridge` | 69,281 | 0.1839 |
| `h19-5` | 121,131 | 0.1922 |
| `h19-4` | 123,779 | 0.1894 |
| `h16-1` | 123,939 | 0.1855 |
| `ens12-adopted` | 172,974 | 0.1563 |
| `h25-ctx-ridge` | 174,232 | 0.1280 |
| `r13-lattice-s5` | 206,895 | 0.0904 |
| `Hedge-v2` | 227,507 | 0.1563 |
| `2314b599` | 343,816 | 0.0107 |

* **Spearman(mass, score) = −0.9436** over these 13 (re-measured this session).
* Log–log elasticity over the same 13: **d ln score / d ln S = −0.917**.
  (The inventory file `knowledge/76` reports −0.37; the two differ because they are fitted over
  different subsets. Flagged as **IR-H88-002** for review; both are negative, which is the part that
  matters.)
* Local elasticity along the champion lineage (d2-8 → h33-2-b2, the only pair known to be the same
  field with 2,545 masked cells deleted): **−0.42**.

The champion lineage in one line: `d1-5` (60,069 px, 0.2477) → `d2-8` (44,090 px, 0.2600) →
`h33-2-b2` (37,654 px, 0.2778). **Three filings, no change of detector, +0.030 DTI earned by shipping
fewer, better-placed dots.** The last step deleted exactly the 2,545 cells that sat on catalogue
pixels — cells that can never earn credit and always pay the tax. That is free precision, and it is
the single most reproducible effect in this project's board history.

## 4. What beating 0.3195 (and 0.2778) requires — arithmetic, not projection

Inverting the metric at the incumbent `|G|` bracket (`knowledge/01`, `knowledge/76`; `|G|` is not
published and is not identifiable from public bytes, so the answer is given across the bracket):

| `|G|` assumed | champion implies `T` | `T` required for 0.3195 at S = 37,654 | ratio |
|---|---:|---:|---:|
| 5,949.3 px | 3,414.2 | 3,926.7 | 1.1501 |
| 10,000 px | 4,314.5 | 4,962.1 | 1.1501 |
| 14,088.7 px | 5,223.1 | 6,007.2 | 1.1501 |

Two equivalent ways to close the 0.04 gap, both measured-consistent:

1. **Credit density**: +15.0 % more credited truth per emitted cell (13.87 % → 15.95 % at 37,654 px).
2. **Mass discipline**: keep the same credit and ship **S ≈ 26,986 px** (elasticity −0.42), i.e.
   −28 % mass. At that mass, the same `T = 5,223` gives `DTI = 0.313`; reaching 0.3195 exactly needs
   `T = 5,325` (+2 % credit).

The same unit trick that produced 0.2778 from 0.2600 is what (2) is: **delete mass that cannot earn
credit, and concentrate the budget where the kernel can be filled.**

## 5. So why doesn't everyone just ship 27,000 dots?

Because the budget choice and the ranking are entangled, and this repository's holdout instrument does
not reward sparsity:

* On the shared hide-and-recover instrument (`gems52-pooled-hide-v1`, 9,400 dots/fold,
  `evidence/h77_budget_sweep.json`) the same View-B field's DTI **rises monotonically with budget**
  (fold 0: 0.0716 at 4,000 → 0.1130 at 9,400 → 0.2134 at 37,654 dots).
* On the board, the same family's score **falls** with mass (Spearman −0.94).

The reason is measured, not mysterious: the instrument's withheld truth is ~53,000 px
(≈ 1.0 % of the footprint) against the organiser-implied hidden prevalence of 0.112–0.294 %
(`knowledge/01`). **The instrument's truth is ~4× too dense, so it over-rewards recall and cannot
choose a budget.** Every "ship less" decision in this project has therefore been made blind. Making the
instrument prevalence-matched is the highest-value unbuilt tool in this repository — it is exactly
what the H88 round builds (stage `pm`) and uses to pick the emission budget on evidence rather than by
taste.

## 6. One-paragraph answer to "why did it get 0.2778, and can we beat it?"

`h33-h33-2-b2` scores 0.2778 because it is the `d2-8` surface field with every cell within 200 m of the
mapped catalogue deleted: 6.3 % of the mass removed, +6.8 % of score, and no detector change — free
precision, because a masked cell can never earn credit and always pays the false-positive tax, and
because the scored population is faults the catalogue does *not* contain, which is why the file's mass
sits a median 1,965 m from every mapped trace. Beating it is arithmetic, not luck: at the same budget
you need +15 % credit density, or — much cheaper and already demonstrated three times in this family's
own filings — the same credit delivered in ~72 % of the mass. What has blocked that second path is that
no instrument in the repository could see it; the holdout hides *catalogue* faults at four times the
real prevalence and therefore rewards exactly the over-emission the board punishes. H88 fixes the
instrument first, calibrates the budget against it, and only then emits.

## 7. Irregularities flagged in this document

* **IR-H88-001** — File→score mapping is owner-reported for every one of the 13 rasters; the public
  board is team-level only. No ORGANIZER-CONFIRMED number exists in this repository.
* **IR-H88-002** — Elasticity disagreement: −0.917 (this session, 13 points) vs −0.37
  (`knowledge/76`, 12 points, method unspecified). Both negative; the extrapolated 27 k budget follows
  from −0.42 measured directly on the champion lineage and is robust to the global slope.
* **IR-H88-003** — `evidence/h87_build.json` carries `verdict: "promote"` while its own
  `evidence_class` reads "HOLDOUT-DTI (not yet run)". Precedent IR-H85-003: a promote verdict without
  a measured holdout is withdrawn. The H87 file is **download-only** until this round evaluates its
  field on the shared instrument (H88 does this and reports separately).
