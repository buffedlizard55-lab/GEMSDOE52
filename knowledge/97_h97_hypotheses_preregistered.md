# 80 · H97 candidate hypotheses, ranked (written before any H97 fit)

Round contract: [`registry/h97_preregistration.json`](../registry/h97_preregistration.json). Read with
[`knowledge/76`](76_why_02778_and_what_beating_03195_requires.md) (why the 0.2778 file scores what it
does and what 0.3195 requires) and [`knowledge/78`](78_sources_and_open_questions.md) (verified sources).

**Ranking key:** *expected gain* = how much the published metric can move if the hypothesis is true
(derived from the identity in `src/gems52/metric.py`), *cost* = how much of a single core and an hour it
needs. Everything below is arithmetic on the organizer's published scoring rule plus measurements
already in this repository; nothing is a forecast of a board score.

Ranked list, best expected gain per unit of cost first:

| # | hypothesis | layers touched | expected gain | cost | ran this round? |
|---|---|---|---|---|---|
| H97-1 | Budget (mass) lever on a fixed field, with the champion's 200 m ring | none — placement only | **highest available**: at the champion's credited mass, S ≤ 25,384 is the arithmetic requirement for 0.3195 (knowledge/76 §3) | low | **yes — primary** |
| H97-5 | Cross-round corroboration of two independent disagreement fields | none — selection only | moderate: `h19-5`'s own name is *multiline-corroborated*; corroboration is the best-scoring family's recipe | low | no (next round) |
| H97-2 | Strike-directed View-A edges instead of isotropic magnitude | A: 18, 11, 5, 3, 9, 2 | moderate: H97's own failure analysis says magnitude ranking is the defect (knowledge/82 §3) | medium | no |
| H97-3 | Ring width (100 m vs 200 m) and dot spacing (2.8 vs 3.0 px) schedule | none — placement only | small but board-verified: the champion's ring removal alone is +0.0180 on the board | low | partly (3 px and 200 m are frozen) |
| H97-4 | Radiometric-only View B (band 6 = GeoDAWN total count by bytes) | B: 6 alone | small: an ablation of the brief's own radiometric clause | low | no |

## H97-1 (PRIMARY) · the mass lever on the lane's own field

* **Method.** Keep the lane's field fixed — View A confident, View B abstains (`A_rank * (1 - B_rank)`)
  over the frozen views in the preregistration — and change only *how much of it is emitted*, with the
  champion's own 200 m catalogue ring removed.
* **Mechanism / physical signature.** Density and susceptibility edges with no surface expression:
  structure buried under cover, which is the population a surface-mapped catalogue is least likely to
  contain. Named non-fault mimics: lithologic contacts and intrusive margins, palaeo-channel thalwegs,
  playa and salina edges, anthropogenic linears (roads, canals, pipelines, fence lines).
* **Why it could catch a fault the catalogue misses.** USGS/INGENIOUS compilation is field-verified and
  line-based; a fault with no surface trace in young cover has no lines to digitise. A subsurface-edge
  detector is not limited by that.
* **How it differs from everything already in the repository.** Every prior round emitted to the full
  budget and asked the *detector* to improve. This round holds the detector fixed and moves the
  *stopping point*, which the recorded board evidence says is what separates this family's 0.2477 →
  0.2778 (knowledge/76 §3). The budget is not chosen by taste: it is chosen by a prevalence-matched
  off-catalogue instrument (SGMC faults ≥ 300 m from the catalogue, thinned to 14,089 px with a fixed
  seed) at five budgets against a matched random control, with a frozen rule that may only *lower* the
  budget and only if the matched control is beaten as well.
* **Free, obtainable data.** No new external data is required: everything comes from
  `data/training_features.tif` (19 bands, integrity-pinned). If a future round wants the GeoDAWN
  survey products directly, the official free releases are USGS GeoDAWN, DOI
  [10.5066/P93LGLVQ](https://doi.org/10.5066/P93LGLVQ) (public domain) and INGENIOUS GDR 1391, DOI
  [10.15121/1881483](https://doi.org/10.15121/1881483) (CC BY 4.0). Obtainability in this sandbox: the
  USGS and GDR hosts are unreachable from here (network is restricted to GitHub/PyPI hosts); the
  repository's copies arrive through the integrity-pinned mirror in `scripts/restore_data.py`, which
  reported `ALL_VERIFIED=True` for 23/23 pins this session. A round that needs the *original* bytes must
  be run somewhere with open network, and that is recorded as a limit, not assumed away.
* **Falsifiers.** (i) the five-budget ladder is monotone *increasing* to the full budget, or the matched
  control is not beaten at any rung; (ii) the paired holdout CI lower bound on
  (`h97_disagree` − `random`) ≤ 0; (iii) the lane gate flags the emitted dots as another lane's
  support. Any one of them ⇒ the round is negative and the file is download-only.

## H97-5 · cross-round corroboration of two independent disagreement fields

* **Method.** Keep each round's disagreement field separate, then emit only the cells where *two*
  independent rounds' dot fields fall within 3 px of each other, spacing-selected as usual. The
  best-scoring family on the board is literally named *multiline corroborated*; this is that idea with
  co-training fields instead of line detectors.
* **Why it differs.** The repository's corroboration experiments corroborated *line detectors on one
  instrument*; H87 and H97's fields are independent in their View A (9 potential-field channels with
  different weights vs the wavelength/Th-K pair) and were fitted to different objectives. Corroboration
  across two rounds is a new selection rule here.
* **Cost/gain.** Low cost, moderate gain — it removes dots that only one field likes, which is exactly
  the low-credit tail the marginal rule says to drop, without inventing new physics.
* **Status.** Not run this session (budget of three experiments), preregistered here for the next one.

## H97-2 · strike-directed View A

* **Method.** Replace the isotropic gradient *magnitude* rank with a directed ridge response along the
  measured regional strike (this repository measured 166.7–171.8° compass with R 0.37–0.45 in H82), then
  keep the same disagreement rule.
* **Why.** H97's screening measured the isotropic magnitude ranking as *anti-informative*
  (view_A_rank 0.0438 against 0.0519 random, knowledge/82 §3): magnitude is largest over outcrops and
  range fronts, where a surface-mapped catalogue already has everything.
* **Cost/gain.** Medium cost (an oriented filter per fold, with the strike taken from the visible
  catalogue only), moderate gain.

## H97-3 · ring width and dot spacing schedule

* **Method.** Re-emit the same field at 100 m and 200 m rings and at 2.8/3.0 px spacing and compare on
  the board (not on a holdout — the instrument does not resolve placement, knowledge/76 §5).
* **Why.** The one *board-verified* placement gain in this family is the ring removal itself: the same
  44,090-px file scores 0.2600 with the ring and 0.2778 without it (knowledge/76 §1). The ring is
  currently a frozen 200 m because that is the only value with board evidence behind it.

## H97-4 · radiometric-only View B

* **Method.** Ablate: View B = in-stack band 6 (radiometric total count, confirmed by bytes at Spearman
  0.9989 against GeoDAWN TC, `evidence/h97_holdout.json` `band6_recheck`) alone, versus the
  curvature/slope composite.
* **Why.** The brief names radiometric bands explicitly; this isolates how much of the disagreement
  surface is driven by radiochemistry rather than topography.
