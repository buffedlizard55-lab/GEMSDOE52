# 83 · H98 hypothesis, frozen before any H98 fit (2026-10-10)

Read with `knowledge/80` (H97 preregistration), `knowledge/82` (H97 results: the screening that
produced this arm), `knowledge/76` (the metric arithmetic and the mass lever) and
`registry/h98_preregistration.json` (the frozen contract this file accompanies).

**Slots used: 0. Uploads: 0.** No board number is claimed anywhere in this document.

## 1 · The hypothesis

**H98-1 (the only arm this round runs).** The lane's second disagreement case is the one that carries
off-catalogue signal, not the first:

```
h98_bonly = B_rank * (1 - A_rank)
```

* **View B (confident):** detrended-elevation curvature at σ2 and σ6, its gradient at σ2,
  detrended-slope curvature at σ2, and the in-stack radiometric band 6 (measured this session at
  Spearman 0.9989 against the GeoDAWN total count, so band 6 *is* the radiometric channel the brief
  asks for by bytes, not by tag).
* **View A (abstains):** the potential-field edge family (bands 18, 11, 5, 3, 9, 2), whose gradient
  *magnitude* ranking is now measured as the defect (knowledge/82 §3).

**Physical signature targeted:** youthful topographic scarps and ridge breaks — the geomorphic
expression of Quaternary faulting. **Why it might catch a fault the catalogue lacks:** faults enter
USGS/INGENIOUS catalogues through field verification and compilation; a scarp that no compilation has
visited is exactly a fault with surface expression and no catalogue entry, and lidar-era mapping
programmes keep finding them. **Named non-fault mimics:** roads, canals, field boundaries, stream banks,
terrace edges, and playa margins.

## 2 · Why this is a fresh round and not post-hoc promotion

`registry/h82_preregistration.json` (`attribution_arms_not_promotable`) and `AGENTS.md` forbid promoting
an arm that was picked after seeing a holdout number. So:

* the arm was measured in the **H97 screening** on the prevalence-matched off-catalogue instrument
  (`evidence/h97_channel_screen.json`, `b_only` 0.109480 against random mean 0.051925, lift +0.057555);
* it is frozen here as H98's **primary before any H98 fit**;
* its validation runs on the **other** instrument (`gems52-pooled-hide-v1`, hide-and-recover with
  catalogue truth), which was not used to choose it.

That is the strongest independence the repository's own rules allow short of new external truth, and it
is stated rather than assumed.

## 3 · What the lane protocol requires first, and why it may kill the round

The parallel-run protocol's first rule is a **lane check on the exact support that would ship**: stop if
the raster's rank correlation with any registry raster exceeds 0.90, or if more than 70 % of its dots
fall within 3 px of any one registry raster's dots. This matters more for H98 than for any previous
round, because the DEM/scarp "dotted ridge" family is the best-scoring family on the board:
`gems10-h28-dotted-ridge` (0.1839), `gems24-h25-1-dotted-h19-5-d1-5` (0.2477), `…-d2-8` (0.2600) and
`h33-2-b2` (0.2778, owner-reported). If a B-only emanation reproduces that family, this round must log a
duplicate and stop — which is why `scripts/check_h98_lane.py` runs before any validation and its
decision gates the runner.

## 4 · Falsifiers

* Lane pre-check STOP → no H98 file at all; the deliverable is the H97 round's negative plus this record.
* Hide-and-recover paired 95 % CI lower bound of (`h98_bonly` − `random`) ≤ 0 → negative; nothing ships.
* Leakage canary above 0.90 for any arm → the arm is a leakage channel and is not reported as a result.
* Uniqueness gate fails (byte-identical to a prior, or not canonically distinct) → nothing ships.

## 5 · Honest limits stated before the numbers

The screening is a single instrument at a single budget, its truth (SGMC faults ≥ 300 m from the
competition catalogue) is a proxy for the organizer's scored faults, and the B-only reading contradicts
the brief's own prior for that case (recorded as IR-H97-003, neither deleted). The hide-and-recover
instrument that validates H98 measures *catalogue* truth, which the repository has already shown is not
the board's population. A positive CI here therefore licenses "worth a slot at the owner's discretion",
never "will score above 0.2778".
