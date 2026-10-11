# 98 — Why `h33-2-b2` scored 0.2778, what 0.3195 and 0.3774 actually are, and the measured lever that is still unspent

**Every number here is either read from bytes on disk, computed with the repository's own transcription of
the organiser's metric (`src/gems52/metric.py`, pinned by `tests/test_metric.py` against the organiser's
worked example), or copied from the official page.** Nothing is a leaderboard forecast. Where a quantity
is not identifiable from public bytes it is named as such.

Sources fetched and read in this session (2026-10-10 / 2026-10-11 UTC):

* Metric, scoring example and submission format — <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>
* Public leaderboard — <https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/>
* Reference solution (U-Net, Monte-Carlo CV, Tversky loss weighted to penalise false negatives) —
  <https://github.com/drivendataorg/gems-prize-reference-solution>
* Tversky index — <https://en.wikipedia.org/wiki/Tversky_index>
* EPSG:32611 — <https://epsg.io/32611>

---

## 1 · First, a correction the brief needs

The brief states two different "highest scores". The public board on 2026-10-10 shows:

| rank | team | public DW-Tversky |
|---:|---|---:|
| 1 | xiaofanhu | **0.3774** |
| 8 | DARD | 0.3195 |
| 22 | extradr19 | 0.2778 |

`0.3774` is **not** this project family's score: it is the current global leader. `0.3195` is **not** "the
highest score right now": it is rank 8. The family's own best is **0.2778 at rank 22**
(`extradr19`, last active ~2026-10-04, which matches the owner-reported `h33-2-b2` value and date — that is
consistent with, and not proof of, that team being the owner's account). The bar to enter the top 5 is
currently **0.3262**, and to lead, **0.3774**. This is logged as IR-H97-001 and IR-H97-002. The number in
the brief that a *target* has to beat is therefore 0.3262, not 0.3195.

## 2 · Why `h33-2-b2` scored 0.2778 (re-verified from its bytes this session)

Measured again from `data/reference/h33-2-b2-zeros.tif` (SHA-256 `c55bafc4…`, integrity-pinned):

| property | measured |
|---|---|
| container | single-band float32, all finite, 0 non-finite, `nodata = None` (a `-zeros` file) |
| values | exactly {0, 1} |
| emitted mass `S` | **37,654** |
| nearest emitted cell to the mapped catalogue | **223.6 m** (= √(200² + 100²): the ≤ 200 m ring is deleted) |
| median distance to the mapped catalogue | **1,964.7 m** |
| fraction of mass within 300 m of a mapped fault | **5.77 %** |

So the champion is **the 0.2600 H19-5-family surface field with the catalogue collar pruned**. It earns
almost nothing from the mapped catalogue (0.74 % of its mass sits inside a mapped fault's kernel) and
whatever it earns, it earns on structure the catalogue does not have. That is the whole answer to "why
does it score highest in this family": not a better detector, but *free precision* — a masked cell can
never earn credit and always pays the false-positive tax, so deleting the collar is a strict gain.

Two consequences, both already in `knowledge/76` and both unchanged by this session: the family's score
across its twelve scored files is dominated by emitted mass (Spearman −0.928), and the arithmetic to beat
the then-current bar is +15 % credit density at the same mass, or the same credit in ~25,400 px.

## 3 · The metric, reduced exactly

With `p ∈ [0,1]` the prediction, `g` the truth mask, `|G| = Σg`, `M = Σ_x p(x)·max_g k`, `S = Σp`:

```
FPw = S − M          (metric.py line 118: fpw = mass - m_covers)
FNw = |G| − TPw      (metric.py line 119: fnw = ng - tpw)
DTI = TPw / (TPw + 0.2·FPw + 0.8·FNw)
    = TPw / ( 0.2·TPw + 0.2·(S − M) + 0.8·|G| )        [exact, no assumption]
```

For **binary** predictions in the common case where every emitted cell's best truth weight equals the
weight the truth credits back (`M = TPw`), this collapses to the form used in `knowledge/76`:

```
DTI = TPw / ( 0.2·S + 0.8·|G| )
```

**Which means the score is set by exactly two things: how much weighted truth you recover (`TPw`), and how
much mass you spent doing it (`S`).** Precision enters only through the 0.2 weight.

## 4 · The measurement that matters: this is a *coverage* metric

Computed with the repository's own `metric.dti` on a synthetic 100-px straight fault, predicting a
continuous swath of the stated width exactly on the trace:

| prediction | S | TPw | FPw | FNw | DTI |
|---|---:|---:|---:|---:|---:|
| 100 m wide (1 px) | 101 | 101.0 | 0.0 | 0.0 | **1.0000** |
| 300 m wide (3 px, = the kernel's full support) | 303 | 101.0 | 67.3 | 0.0 | **0.8824** |
| 500 m wide (5 px) | 505 | 101.0 | 202.0 | 0.0 | 0.7143 |
| 700 m wide (7 px) | 707 | 101.0 | 404.0 | 0.0 | 0.5556 |

A prediction that **covers** the fault line — even three pixels wide — scores 0.88. The family has been
shipping **dots at 3 px minimum separation**, i.e. a *sampled* trace, not a covered trace. The metric's own
marginal rule (`metric.credit_bar`) says an added cell raises DTI whenever its realised kernel weight beats
`0.2·DTI`; at `DTI = 0.2778` that bar is **0.0556**, and a cell 200 m from a truth pixel has weight
0.3333 — six times the bar. **Sparse sampling is the expensive choice on this metric, and it was chosen by
convention, not by measurement.**

The one thing this does *not* license is thickening an already-correct dot (a dot that already gives some
truth pixel `k = 1` adds mass and `FPw` without adding `TPw`). The gain has to come from **covering truth
pixels that are not yet covered**, i.e. from *extending along strike*, not from *widening across strike*.

## 5 · What that implies for the 0.3262 / 0.3774 target

Holding the family's current ranking quality (its measured credit density at the top of the field) and
solving `TPw = DTI·(0.2·S + 0.8·|G|)` for the truth-recovery a leader-class score needs, at the champion's
own mass and at the `|G|` bracket this repository has pinned:

| |G| assumed | TPw needed for 0.2778 | TPw needed for 0.3262 | TPw needed for 0.3774 |
|---|---:|---:|---:|---:|
| 5,949 | 2,365 | 2,777 | 3,213 |
| 12,512 | 4,873 | 5,722 | 6,620 |
| 14,089 | 5,223 | 6,133 | 7,096 |

At `|G| = 14,089` and `S = 37,654`: reaching rank 1 requires recovering **7,096 truth pixels instead of
5,223 — 36 % more, at the same mass**. Recovering *all* of `|G|` at that mass would score
`14,089/(0.2·37,654 + 0.8·14,089) = 0.749`. **The head-room is in `TPw`, and `TPw` is bought by coverage,
not by precision.**

This is why the two levers the family has been arguing about are actually the same lever seen from two
sides: *ship less mass* and *cover more of the truth trace* both act on `0.2·S` and `0.8·|G|`, and coverage
is the one nobody has spent.

## 6 · What is still untested, ranked by expected board gain per unit of work

1. **Along-strike gap closing between confident cells** (coverage of the trace, not thickening). Mechanism:
   a fault trace is continuous; a detector that finds two confident cells 20 px apart on the same structure
   has, on the metric, found one fault and reported two cells. Filling the gap adds `TPw` at ~1/3 the
   marginal cost of the same mass placed randomly. Cost: low (a line-following pass over the existing
   field). Evidence needed: does the filled field's `TPw` rise faster than its `0.2·S`? That is a
   same-instrument, same-fold measurement, and it is exactly what the H97 budget curve and the H97 holdout
   give the first data point for.
2. **The mass lever at the family's own density** (`knowledge/76` §4): re-emit the champion family's field
   at 32 % less mass. Blocked by the lane rule for the champion's own file (a subset of a registry raster's
   cells is by construction ≥ 70 % within 3 px of it), so it must be done on a *new* field.
3. **Coverage on a co-training discovery field** (this round's artifact): the A-only buried candidates are
   exactly the population the Final Prize Round rewards, and the brief explicitly asks for them.
4. **A prevalence-matched off-catalogue instrument** (`knowledge/76` §6, H89-P): the only way to certify any
   of the above without spending a weekly slot. Still not built.

## 7 · One-paragraph answer

`h33-h33-2-b2` scores 0.2778 because it is the family's best surface field with the ≤ 200 m collar around
the mapped catalogue deleted — free precision, 6.3 % of the mass removed for +6.8 % score. It is rank 22 of
the public board; the top of the board is 0.3774 and the top-5 cut is 0.3262, so the brief's "0.3195 is the
highest score" is out of date by eight ranks. Beating a leader-class score needs, at the champion's own
mass and the repository's own bracket for `|G|`, **36 % more recovered truth — 7,096 px instead of 5,223**
— and the metric's arithmetic says that truth is bought by **coverage**: a swath covering a fault trace
scores 0.88 where a sparse sampling of the same trace scores far less, and the marginal rule admits any
cell within ~283 m of an uncovered truth pixel. The family has spent eight rounds optimising the ranking
and zero rounds optimising the *geometry of emission*, which is the one assumption every round has
inherited without measuring.
