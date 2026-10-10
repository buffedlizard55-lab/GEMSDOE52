# 81 · H96 results and limits — bidirectional co-training disagreement (2026-10-10)

Session branch `arena/90369109-gemsdoe52`. Lane: the standing brief's co-training paragraph
(Blum & Mitchell, COLT '98, doi:10.1145/279943.279962). Pre-registration frozen before any fit:
`registry/h96_preregistration.json` (SHA-256 `0f664c43…`) + pre-fit amendment
`registry/h96_amendment_veto.json` (`91f74c5a…`), specification prose in
`knowledge/80_hypotheses_H96_preregistered.md` and `knowledge/80a_amendment_H96_veto_positive_support.md`.

## 1 · Run card (summary; machine-readable twin `evidence/h96_run_card.json`)

* **Hypothesis.** Bidirectional co-training disagreement: a sustained cover-thickness step and
  strain/seismicity lineation coincident with potential-field edges where the surface view abstains
  marks buried faults the surface-trace catalogue lacks; the reverse disagreement marks surface
  artifacts and is vetoed.
* **Mechanism.** Concealed normal faults offset the basement beneath alluvial cover: `depth_to_base_surf`
  steps (band 15 gradient, σ=2 px), `geod_shearrate` steps (band 7), `deq_n100a15` lineations (band 10)
  register in View A while DEM curvature/slope (View B) sees no scarp; B-only cells are road/erosion
  suspects and are vetoed (0.70 weight).
* **Named non-fault mimics.** Lithologic contacts and intrusive margins; basin-margin facies steps;
  paleo-channels; aftershock/induced seismicity clusters; road cuts; erosion lines. Each of the
  20,050 A-only (buried-dominant) dots carries a reasoning row naming fired components and these
  alternatives: `docs/downloads/gems52-h88-…-a-only-reasoning.csv`.
* **HOLDOUT-DTI** (gems52-pooled-hide-v1; 60,894 withheld positive px — see IR-H96-004 for the
  cross-round tally caveat; 9,400 dots/fold/arm; 95 % paired 20 km cluster bootstrap, 1,000 draws):

  | arm | HOLDOUT-DTI | 95 % CI |
  |---|---:|---|
  | cotrain_bi (primary) | 0.072502 | [0.058139, 0.087161] |
  | consensus_only | 0.082374 | [0.066971, 0.096078] |
  | buried_only | 0.058146 | [0.044010, 0.072841] |
  | single_A | 0.074518 | [0.061701, 0.088090] |
  | single_B | 0.052679 | [0.041881, 0.063415] |
  | random | 0.076551 | [0.068175, 0.084557] |

  Paired (primary − random): −0.004049 [−0.016264, +0.009526]. Primary − buried_only:
  +0.014356 [+0.009258, +0.019673]. Primary − single_B: +0.019823 [+0.003582, +0.038363].
  Mass-lever arm (6,350/fold = 25,400 total): primary 0.053072 [0.041960, 0.064827] — lower, as
  expected on a prevalence-matched catalogue instrument; the mass lever is a board lever
  (knowledge/76), not a holdout lever.
  **Bar 0.192829 (H82 B_DVA2) not reached → verdict for slot: negative.**
* **Independence gate (Blum–Mitchell assumption).** Max |r| of spatial-block (50 px) OOF negative
  errors between views: **0.0965** < 0.60 → not abandoned. Weak proxy-negative correlation is not
  proof of conditional independence. Iterative pseudo-label exchange was not run (closed negative
  N-1, knowledge/03); the whole-segment diagnostic found 114 segments / 1,997 px of
  A-confident/B-abstain candidates and used none of them for training.
* **Leakage canaries.** Max single-channel AUC on held-out truth inside the allowed set:
  0.5958 (topo_edge) — no alarm (bar 0.90). Full per-channel table in `evidence/h96_holdout.json`.
* **Correlation/overlap vs registry.** Surface: max Spearman 0.0914 (PASS). Dots: max Spearman
  0.0356; max near-3px fraction 0.9993 vs the universal-coverage probe `13gems…r13-lattice…`
  (literal DUPLICATE/STOP, IR-H96-002 — random dots score 0.9991 against the same probe);
  excluding probes: max near 0.5233 (vs the H87 sibling raster), inside the 0.70 bar → policy PASS.
* **Raster.** `submission/gems52-h96-bidir-cotrain-coverstep-25400px-20261010T222552Z-a6ab4495-zeros.tif`,
  SHA-256 `ba2dae7db2b919bb53c147cae0d5f9663b368b059fc1b26c69d8dbfc35948ade`. Independent
  re-read: single-band float32, nodata None, EPSG:32611, 3730×3292, transform (100, 0, 243350,
  0, −100, 4508550), all finite, values in [0,1], exactly {0,1}, 25,400 ones, min dot spacing
  3.0 px, 0 dots on catalogue, 0 within the 200 m collar, 0 outside the organiser domain.
  Validator (`gems52.gates.format_report`) ok with no problems. ZIP contains exactly the one TIFF.
* **Not the union.** 21,849 / 25,400 dots (86 %) lie outside the two views' spaced top-k union
  (Jaccard 0.049); 78.9 % are disagreement-driven (buried-dominant).
* **Uniqueness.** 147 registry rasters checked; decoded pattern unique; not identical to any prior;
  novel fraction 0.5703; not the literal prior union (`evidence/h96_uniqueness.json`).
* **Submission name + note.** `h88-bidir-cotrain-coverstep-25400px` /
  `H96 bidir co-train A/B disagreement, cover-step ViewA, 25400px mass lever, 3px, 200m collar; HOLDOUT-DTI below bar, research candidate` (134 chars).
* **Verdict: negative** (download ok; `submit_ok: false`; no submission slot used).

## 2 · What this round adds to the knowledge base

1. **The co-training disagreement field, tested honestly on hide-and-recover, does not beat random.**
   Primary − random = −0.0040 [−0.0163, +0.0095]. This is the completed test the brief asked for
   ("compare against a single-view baseline on hide-and-recover segments"): the bidirectional field
   does beat single_B (surface alone, +0.0198 [0.0036, 0.0384]) and buried_only (+0.0144), but not
   the floor.
2. **First holdout receipts for the H85-next-B/C/D channels.** Cover-step alone reaches AUC 0.5670,
   seismicity lineation 0.5111, strain step 0.5267 on held-out truth — all near-chance on this
   instrument. These were the top-ranked untested mechanisms from the H85 review; they are now
   measured and weak for catalogue recovery. (They say nothing direct about off-catalogue faults.)
3. **consensus_only (0.0824) is the best arm of this family** — but it is still at the random
   floor's CI. The interesting reading: within a co-training structure, the *intersection* of the
   views carries whatever weak signal exists; pure disagreement dilutes it on catalogue faults.
4. **The channel gap is confirmed.** My View B (slope/curvature/edge/K-Th/tc) scores 0.0527 where
   the H82 surface channels (DVA2/HVA) score 0.17–0.19 on their instrument. The champion family's
   skill lives in those specific surface transforms, not in generic DEM/radiometric ranks.
   The next co-training round must graft the disagreement arm onto DVA2/HVA, not replace them.
5. **The mass lever is measured on the holdout too** (0.0725 → 0.0531 when the budget drops from
   9,400 to 6,350/fold): on a prevalence-matched catalogue instrument, fewer dots cost recall.
   The board's mass-score anticorrelation (Spearman −0.93, knowledge/76) is about the *hidden*
   population and remains untested here — that is what H89-P (prevalence-matched off-catalogue
   instrument) is for.

## 3 · The 0.2778 question, re-verified from bytes this session

The champion `data/reference/h33-2-b2-zeros.tif` (SHA-256 `c55bafc4…`, integrity-pinned): binary
{0,1}, S = 37,654, all-finite zeros container, nearest dot 223.6 m from `labels.tif` (= √(200²+100²)
— the ≤ 200 m ring deleted), median distance 1,964.7 m, 5.77 % of mass within 300 m of the mapped
catalogue. All knowledge/76 §1 numbers reproduced exactly. The answer to "why did it score highest"
stands: it is the 0.2600 surface field with the catalogue ring pruned (free precision), and the
family's score is dominated by emitted mass (Spearman(mass, score) = −0.928 over 12 files).
"Can we score higher?" — the arithmetic: +15 % credit density at S = 37,654, or the same credit at
S ≈ 25,400. H96 spent the mass lever on a novel ranking and measured the cost honestly.

## 4 · Site and shared-tool repairs (Own the Outcome)

* README.md rebuilt with the byte-exact preserved brief (knowledge/26_current_user_brief.md
  ```text block, assembled programmatically) + H96 status; six broken test invariants from the
  H87-session rewrite repaired (IR-H96-001).
* docs/index.html and docs/executive-summary.html rewritten: explicit **OK to download? / OK to
  submit?** verdict box at the top, one-click downloads, exact submission name and note, the
  "Predicted values must be in range [0, 1]" troubleshooting table, and a research-files status
  table that keeps DO NOT SUBMIT labels on the negative-verdict files (ctd5, h83, h85, h86).
* The H87 "VERDICT: PROMOTE / Ready-to-Submit" claim without a holdout receipt is retracted
  (IR-H96-005).

## 5 · Limits and next steps

* **Cross-run caveat (IR-H96-004):** the 0.192829 bar comes from a different eligible mask
  (53,186 vs 60,894 withheld). Within-round comparisons are the valid ones; the bar is still the
  standing promotion gate.
* **The holdout is the wrong population for the board** (family Spearman ≈ −0.10). A negative
  holdout verdict blocks a slot under the standing rule, but it is not evidence the file would
  score zero on the board. The selector step owns that trade-off.
* **Next round (pre-registered before fitting):** graft the H96 cover-step/strain/seismicity
  disagreement arm onto the H82/H84 DVA2+HVA surface channels at the same 9,400/fold budget and
  test whether the disagreement arm adds anything to 0.19. Second: H89-P, the prevalence-matched
  off-catalogue instrument (thinned to |G| ≈ 5,949–12,512 px), which is the only tool that can
  certify the mass lever without spending a slot.
* **Blocked by sandbox egress:** GDR 1391 "2 m Temperature Probes" (H85-next-A, the top-ranked
  untested thermal channel; DOI 10.15121/1881483, CC BY 4.0) needs a user-side download into
  `data/external/` with a SHA pin — gdr.openei.org is not on the allowlist.

## 6 · Sources (verified this session)

* DrivenData problem/metric: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
* DrivenData leaderboard (public): https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/
* Blum & Mitchell, COLT 1998: https://doi.org/10.1145/279943.279962
* GeoDAWN USGS release (DOI 10.5066/P93LGLVQ): https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and
* INGENIOUS GDR 1391 (DOI 10.15121/1881483): https://gdr.openei.org/submissions/1391
* EPSG:32611: https://epsg.io/32611
* Repo receipts: `evidence/h96_views.json`, `evidence/h96_holdout.json`, `evidence/h96_build.json`,
  `evidence/h96_uniqueness.json`, `evidence/h96_lane_dots.json`, `evidence/h96_lane_surface.json`,
  `evidence/h96_run_card.json`, `registry/h96_preregistration.json`, `registry/h96_amendment_veto.json`.
