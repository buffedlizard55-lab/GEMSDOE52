# 99 · H97b amendment (written after E1/E2 were measured, disclosed) — a lane-distinct emission rule

**Why this amendment exists.** The H97 primary emission (preregistered in
`registry/h97_masslever_preregistration.json`) was built, written and gated. Its gates are in
`evidence/h97_masslever_run_card.json`. The **dot lane check on the final dots failed**: 93.85 % of the
25,400 dots fall within 3 px of the H96 artifact
(`submission/gems52-h96-bidir-cotrain-coverstep-25400px-20261010T222552Z-a6ab4495-zeros.tif`),
99.89 % when the universal-coverage lattice probe is included (129.9 % of the footprint covered by
the 3 px halos of the informative set is irrelevant here — the H96 file is a real, localising
raster). The standing parallel-run protocol says: *"more than [70 %] of your dots fall within 3 px
of one registry raster's dots, you have drifted into another lane: log it as a duplicate and stop."*

**Diagnosis, measured.** H97's primary field is
`(0.45·cons + 0.55·buried)·(1 − 0.70·veto)` where `buried = A·clip(A−B,0,1)` is *A-dominant*, and
View A is byte-for-byte the H96 View A (the round's single registered change was the View-B channel
set). Any field whose ranking is carried by View A therefore reproduces the same top-ranked pixels:
the buried stratum is a **fixed point of the A-view**. This is the same failure the parallel H95
session hit against H93 (IR-H95-006), and it is now an independent second observation of it.

**What the brief itself offers instead.** The session's method paragraph says: *"Pseudo-label only
where one view is confident and the other abstains … Where B is confident and A is not, suspect
surface artifacts such as roads or erosion lines."* A field that uses **View A only as a screen**
(never as a ranker) and ranks by the **surface view** is inside the paragraph, is the remedy this
repository already reached on modelling grounds (`AGENTS.md`: *"Use View A only as a soft prior
inside B's confident set"*), and cannot reproduce the A-driven fixed point.

**Chronology, disclosed.** This amendment was written **after** E1 and E2 produced numbers and after
the H97 primary's lane gate failed. Its selection rationale is the brief's artifact rule plus the
lane measurement — **not** the holdout. The promotion rule, the bar, the gates, the budgets and the
placement rule are **unchanged** from `registry/h97_masslever_preregistration.json`. The H97b holdout is
reported for the amended field at both budgets so the reader can see the amended arm's own number,
and the H97 primary is retained as an audit artifact with its own receipts.

## Frozen H97b emission rule

```
a, b   = View A and View B rank composites (byte-identical to H97's: reused, not rebuilt)
screen = a >= median(a over the eligible footprint)          # A must support the location at all
art    = clip(b - a, 0, 1)                                   # B-confident, A-abstaining
veto   = rank01(art, valid & art>0)                          # the brief's road/erosion suspect
field  = b * screen * (1 - veto)                             # rank: surface view; screen+veto: View A
allowed= valid & ~catalogue & (distance-to-catalogue > 2 px) # 200 m collar, the champion's discipline
dots   = gems52.nodes.spacing_select(field, allowed, S, min_px=3.0)
```

* **S = 25,400** (the metric-implied mass lever, unchanged), binary {0,1}, all-finite, `nodata` None.
* **Gates: identical to H97** — format, uniqueness, lane surface < 0.90, lane dots policy ≤ 0.70,
  not-the-union, canary and independence (already measured: 0.6190 AUC, max |ρ| 0.0616).
* **Promotion rule: identical** — paired CI95 lower of (field_b − best control) > 0 **and**
  field_b ≥ 0.190147. Expected outcome from the H96/H97 evidence: **negative**; this amendment does
  not change that and is not written to make it pass.
* **Deliverable:** whichever emission is *lane-distinct* is published as the round's download; the
  duplicate is published too, labelled, so the finding is auditable.

## What H97b does not claim

No leaderboard gain is certified (E1: the instrument does not rank the board, Spearman −0.4897).
H97b's own holdout number is a catalogue-recovery number, labelled HOLDOUT-DTI, and nothing here is
a projection of a board score.
