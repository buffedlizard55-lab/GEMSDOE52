# Working agreement

Before every work session, read `README.md`, its full current user brief, `knowledge/07_r2_hypotheses_preregistered.md`, and the newest review/irregularities record. Read previous failed experiments before proposing another.

Maximize P(Win): prioritize geological signal and trustworthy spatial validation. Never spend a competition upload slot unless the new candidate has beaten the current comparable holdout best. Own the Outcome: verify written files, served downloads, reproducibility, provenance and failure cases end to end.

Keep known-catalogue labels separate from verified fault absence, public participant scores separate from filename attribution, hypotheses separate from discoveries, and format-valid artifacts separate from promotion-approved ones. Do not invent organizer validation or claim a guaranteed leaderboard gain. A GeoTIFF with a new name or compression is not a unique prediction; compare decoded pixels.

This session's working branch is fixed by Arena. Do not change branches. Keep raw competition data and large intermediate arrays under ignored `data/` and `work/`. Publish small audit receipts, the unique compressed prediction raster and its review table.

<!--H67-AGENTS-->
## Current H74 continuation (2026-10-09) — READ THIS FIRST

Read `README.md`'s H74 block, then `knowledge/63_hypotheses_H74_preregistered.md` (frozen, SHA-256
`d117b265…e3b55`, pinned in `registry/h74_preregistration.json`), its dated amendment
`knowledge/63a_h74_amendment_shipped_arm_rule.md` (shipped-arm rule, written before any holdout number
existed), and `knowledge/64_h74_results_and_limits.md`.

**The co-training lane is now closed with a mechanism, not just a failed threshold. Stop re-opening it.**

1. **The rescue argument is dead.** Every earlier round closed the lane on S1 — View A's out-of-quadrant
   AUC on *all* held-out truth is ~0.52. The standing rescue was "the catalogue only contains
   surface-expressed faults, so S1 measures the wrong population". H74 tested that directly (S1′: View A's
   AUC restricted to truth inside View B's blind band `rank_B ∈ [0.35, 0.65]`). Result, in **all four folds
   without exception**: `AUC(A | B-dark) < AUC(A | B-blind) < AUC(A | B-bright)` —
   0.4685 < 0.4893 < 0.5436 pooled, margin **−0.0543** against a required **+0.05**. View A is *least*
   informative exactly where View B is blind. A buried-fault population visible only to potential fields
   would have produced the reverse ordering. View A's apparent skill is a shadow of the same
   surface-expressed structures View B reads directly.
2. **Independence was never the problem.** Spatial-block OOF error correlation on labelled negatives:
   max |ρ| **0.1333** over 2,089 blocks, far inside the 0.60 abandon bar. Co-training's *independence*
   precondition holds on this data; its *sufficiency* precondition is refuted, now conditionally as well
   as globally. Do not re-run the independence screen expecting it to be the blocker.
3. **Dose-response, measured.** Handing φ of the budget from View B to View A costs DTI linearly:
   swap_010 0.168343 (Δ −0.006175, CI [−0.009869, −0.002305]), swap_025 0.160427 (Δ −0.014091),
   swap_050 0.152317 (Δ −0.022201) against `single_B` 0.174517. Roughly **−0.00083 DTI per 1 %** of budget
   transferred. There is no φ > 0 worth paying for.
4. **`line_support_B` is a free null and is reusable.** Replacing a rank field by the max over 12
   orientations of its mean along a 7 px (600 m) chord measured 0.172426, paired Δ −0.002091 with CI
   **[−0.005873, +0.001289]** — straddles zero, i.e. no measurable cost — while moving the spatial pattern
   substantially. **Use it as a near-free degree of freedom when a future round needs to dodge the lane's
   70 % near-dot rule without paying DTI.** `H.line_support` in `scripts/run_h74.py` is unit-tested
   (`_shift0` is zero-filled, never wrapped).
5. **Controls reproduced exactly**, so the instrument is sound and these numbers are comparable to H70:
   `single_B` 0.1745172876 vs the committed 0.174517 (|Δ| **2.9e-07**), `single_A` 0.071954,
   `disagreement_pre` 0.033293, `random` 0.080426 — all identical to H70 to six decimals.
6. **Reusable tooling added this round.** `scripts/h74_build.py` has `_place` (greedy + 3 px hard core +
   exact per-prior near-dot quota) which is **verified bit-identical to `gems52.nodes.spacing_select`**
   when the quota is off, `_bit_transpose` (per-pixel prior bitmap; turns the quota lookup from a
   cache-hostile strided gather into a 19-byte contiguous read), `_exclusion_stamp` (matches
   `spacing_select`'s strict `<` rule, unlike `gates._disk`'s `<=`), and `_disagreement_audit`
   (cardinal-orientation falsifier for the brief's B-only "roads/erosion" reading).
7. **Band labels: check `src/gems52_h1/spec.py` `OFFICIAL_BANDS` before naming any band.** IR-52-01 bit
   this round: band 6 `tc` is a **magnetic** tilt/total-curvature derivative, *not* radiometric total
   count. True gamma-ray channels exist only in the external GeoDAWN layers (`X_rad_*`).

Experiments used: 3 of 3. Slots used: 0. Verdict: **negative, research-only** — see the README H74 block
for the DOWNLOAD/SUBMIT decision on the emitted file.

## Current H73 continuation (2026-10-09)

- **H69 file verdict (H73 audit):** DOWNLOAD NO, SUBMIT NO. The literal lane rule returns DUPLICATE/STOP (14 universal-coverage probes), and a policy PASS does not waive it. This file is a research copy only.


Read `README.md`'s H73 block first, then `knowledge/61_hypotheses_H73_preregistered.md` (frozen), its dated amendment
`knowledge/61a_h73_preregistration_amendment_quota_placement.md` (quota placement adopted BEFORE any holdout or shipped
placement), and `knowledge/62_h73_results_and_limits.md`. H73 is **negative at the lane gate**: a surface-only emission
cannot be made lane-feasible on this 350-distinct-prior registry with plain greedy (best 0.8916) or with per-prior quotas
(best 0.7043, short fill). No H73 file was emitted. The instrument control reproduces (`single_B` 0.174571, |Δ| 3.6e-07).
Experiments used: 1 of 3. Slots used: 0. Do not re-run the quota placement at the same budget expecting a different result;
the denominator effect is the finding. The `scripts/run_h73.py` runner refuses to run if `knowledge/61` or `61a` moved.
The DOWNLOAD/SUBMIT decision for the repo's existing lane-feasible file is in the README H73 block; it is still NO for submission.

## Current H71 continuation (2026-10-09)

Read `README.md`'s H71 block first, then `knowledge/57_hypotheses_H71_preregistered.md` (frozen, SHA-256
`315c4e47…18b4286`, pinned in `registry/h71_preregistration.json`) plus its two dated amendments
`knowledge/57a` (lane-quiet domain measured EMPTY: 0 px) and `knowledge/57b` (novel-first placement,
cap searched against the filled count), and `knowledge/58_h71_results_and_limits.md`. H71 is
**NEGATIVE**: the A-only stratum does not beat single_B on the holdout (matched budget 1,264 dots/fold,
paired delta -0.050144, CI [-0.064233, -0.036779]) and the policy lane reads DUPLICATE/STOP on the
final dots (max near 0.8903, 17 informative offenders) — both measured, both published verbatim. The
downloadable file `submission/gems52-h71-aonly-stratum-fallback-uncapped-3080px-20261009T073227Z.tif`
(SHA-256 `369b844e…111ea95c`) is format-valid, decoded-unique and support-novel 0.3104; it is
research-only. Experiments used: 3 of 3. Slots used: 0. Do not re-run H71, do not promote it, and do
not present the H71 file as lane-valid. The two measured placement walls (quiet domain 0 px; every cap
probe stopped at max_near = cap) are the round's main deliverable — a third placement attempt needs a
new preregistration.

## Current H70 continuation (2026-10-09)

Read `README.md`'s H70 block first, then `knowledge/54_hypotheses_H70_preregistered.md` (frozen; SHA-256
`25b6ee74…b92151`, pinned in `registry/h70_preregistration.json`) and `knowledge/55_h70_results_and_limits.md`.
H70 is **negative**: the strict A-only discovery stratum measured purely scores HOLDOUT-DTI 0.0174, below
uniform random; the B-only veto and concordant variants both lose to single_B; independence held (max |rho|
0.1337); View A sufficiency failed for the fifth consecutive round (0.5166); and no lane-valid emission exists
from the stratum (610 placeable cells, worst informative near-dot share 1.0; IR-H70-001). Experiments used: 3 of 3.
Do not re-run the co-training lane with another View A rebuild; H70-E (deformation-only View A2) is the only
untested variant and needs its own round. The shared H61 stages were reused, not forked; use
`scripts/audit_uniqueness.py` for uniqueness checks. `docs/downloads/h70-candidate.tif` is research-only:
DOWNLOAD YES, SUBMIT NO, slots used 0. `knowledge/26_current_user_brief.md` must carry the current prompt
verbatim (two tests enforce it).

## Current H67 continuation (2026-10-09)

Read `README.md`'s H67 block first, then `knowledge/45_hypotheses_H67_preregistered.md` (frozen before any
fit), `knowledge/48_h67_results_and_limits.md` (rendered from the receipts) and
`knowledge/49_why_02778_phd_answer.md` (the board algebra, re-measured from restored bytes by
`scripts/h67_board_algebra.py`). H67-A is **negative**: the lane rule fires on the final dots
(84.08 % within 3 px of one informative registry raster) and the hide-and-recover instrument puts it below
uniform random. A unique GeoTIFF exists and is published research-only; **do not submit it, do not spend a
weekly slot**. IR-H67-001 … -010 are in `registry/irregularities.json`; -002, -005, -007 and -008 change how
a shared instrument must be read. Use `scripts/h67_uniqueness_aligned.py` (alignment-filtered corpus) for any
uniqueness check; do not fork a checker.
<!--/H67-AGENTS-->

## Current H66cover continuation (2026-10-09; namespaced after the parallel-session H66 label collision, IR-H66-015)

Read `README.md`'s H66cover block first (it sits directly below the H71 block), then
`knowledge/43_h66cover_hypotheses_preregistered.md` (frozen; SHA-256 pinned in
`registry/h66cover_preregistration.json` together with the dated amendment
`knowledge/43_h66cover_amendment_2026-10-09_budget.md`) and `knowledge/44_h66cover_results_and_limits.md`.
**H66cover is COMPLETE and NEGATIVE, research-only.** Verdict: DOWNLOAD YES (format-valid, unique on
decoded pixels), SUBMIT NO (lane policy DUPLICATE/STOP on the dots phase, and the holdout does not beat
single_B). The shipped artefact is `gems52-h66-covergate-cotrain-633px.tif` (633 dots, SHA-256
`0ce05c52…7629`), published one-click at `docs/downloads/h66cover-candidate.tif` with the explicit
DO-NOT-SUBMIT status on its own pages (`docs/h66cover.html`, `docs/h66cover-executive-summary.html`).
Experiments used: 3 of 3 (E1 canary+fit+independence, E2 exchange+holdout, E3 build+gates+GeoTIFF);
the round is closed — do not re-tune it.

Namespacing (IR-H66-015): parallel sessions merged other rounds under the "H66" label first
(PR #56, structural coherence — the site's bare `h66-*` pages and `docs/downloads/h66-candidate.*`
are that round's; PR #58 added H65halo and the thermal-upflow H67; a later round renamed itself H71
the same way). This round's shared file names therefore carry the `h66cover` prefix and its
irregularity IDs are IR-H66-011 … -015. Before taking a round label, check
`registry/*_preregistration.json` and the `IR-H66-*` ID space.

Facts the next round must respect:

- The cover gate lifted the A-only arm from 0.0315 to 0.0457 (+45% relative) but it remains far below
  single_B 0.1745; the paired CI excludes 0. The co-training/disagreement lane has now failed in every
  variant (H61, H63, H64, H65, H66 structural, H66cover): **View A cannot be repaired by gating,
  capacity cuts, or cross-strike features — stop proposing View A repairs.**
- The H66cover emission is 633 dots because the frozen A-only gate has only 1,657 exact-novel cells
  (IR-H66-013); the template budget is a cap, not a target (amendment `knowledge/43_h66cover_…`).
- 100% of the H66cover dots fall within 3 px of the H64 raster's dots (IR-H66-014): the A-only stratum
  sits inside the H64 disagreement emission's 3 px halo, so **no lane-valid A-only candidate exists in
  this field** — a lane-valid candidate needs a stratum outside every informative prior's halo.
- The surface lane passes for H66cover (literal 0.0336 / policy 0.0126) — rank-unique vs the registry;
  the DOTS lane is what fails.
- H66-B/C/D/E are registered and deferred (`knowledge/43_h66cover` §2). H66-C needs bulk ComCat
  seismicity, which is not ingestible from the sandbox.
- The global pointers `docs/data/submission.json` and `submission/LATEST.txt` stay at main's H60
  artefact; this round's pointer is `submission/H66COVER_LATEST.txt`.
- Slots used: 0. No organizer receipt exists for any file in this repository; every score is
  OWNER-REPORTED.
<!--/H66COVER-AGENTS-->

## Current H65 continuation (2026-10-09; the protocol body keeps the H62 label, see knowledge/41a)

Read `README.md`'s H65 block first, then `knowledge/41_hypotheses_H65_preregistered.md` (frozen;
SHA-256 `4d9d559f…2bef71`, pinned in `registry/h65_preregistration.json`), its dated source amendment
`knowledge/41a_…`, and `knowledge/42_h65_results_and_limits.md`. H65-A is **negative at the premise gate**
(mean 0.5202, min fold 0.4706). Do not re-tune it, do not re-run it on this protocol, and do not run a holdout
arm on it. Experiments used: 2 of 3. E3 is not authorised. Use `scripts/audit_uniqueness.py` (with the census
receipt as its third argument) for any uniqueness check; do not fork a checker. IR-H65-001 … -007 are open.
The H61 file is a measured lane duplicate; do not present it as lane-valid.

## Current H61 continuation

Read `README.md`'s H61 block, `knowledge/30_hypotheses_H61_preregistered.md` (frozen before any fit;
`scripts/run_h61.py` refuses to run if its hash moves) and
`knowledge/31_h61_results_and_limits.md`. H61 is **negative**: View A (potential field / subsurface)
reaches out-of-quadrant AUC ~0.52 while fitting its own quadrant at ~0.93, so the Blum–Mitchell
sufficiency premise fails and the disagreement arm is noise-dominated. Do not re-tune it into a
positive result, do not promote it, and do not treat a valid file as an approved entry.

Three shared-instrument repairs are now authoritative and must not be reverted or forked: masked
support `S` (off-catalogue pixels only), `|G|` as the measured interval [5,949.3, 12,512.1] px rather
than the superseded point 14,088.7, and `gems52.gates.lane_report`'s measured universal-coverage-probe
classification (a prior whose 3 px halo covers >=95% of the eligible footprint cannot localise a lane;
its literal statistic is still reported). Band 6 is radiometric total count (Spearman 1.0000 against
the external GeoDAWN TC grid), so it belongs in View B. See `registry/irregularities.json`
IR-H61-001 … IR-H61-008.

## Previous CTD5 continuation

Read the entire current prompt in `README.md` (also `knowledge/26_current_user_brief.md`),
`knowledge/25_ctd5_preregistered.md`, `knowledge/27_ctd5_results_and_limits.md`, and the
three-pass review. CTD5 is negative and stopped: a registered survey-wide lattice makes
the >70% near-dot gate impossible on this footprint. Do not quietly exclude it, tune a
new placement, promote CTD5, or treat the archival H57 LATEST pointer as upload approval.
Raw input pins authenticate mirror bytes only. Preserve dated source and score caveats.

### H69 (2026-10-09) — the lane rule is satisfiable, and the lever is cross-family consensus

Measured this round, all reproducible from `evidence/h69_placement.json` and `scripts/run_h69.py`:

* **`gems52.gates.lane_report`'s probe classification was not the whole story.** H61 concluded the
  literal 70 % rule was unsatisfiable because of universal-coverage probes. It is also unsatisfiable for
  any emission ranked by this family's own habitat signal: an unconstrained greedy over the legal set puts
  **96.14 %** of its dots within 3 px of one informative raster, with **84 of 343** informative priors above
  the limit.
* **A per-prior quota does not converge.** `S/quota` is structurally ≈ 1.34, so the achieved share is
  pinned near **0.745 at every budget** (24,500 → 32,871; 22,960 → 30,864; 21,558 → 29,069). A quota
  computed against a *target* budget is also the wrong denominator: at quota 26,263 only 35,149 dots were
  placeable, an achieved share of 0.7472.
* **Excluding offenders' halos is not available:** the union of the 84 offenders' 3 px halos leaves
  **361 px** of the 4,859,987 px legal set.
* **What works:** restrict the pool to pixels of low **cross-family consensus** — the count of distinct
  decoded prior patterns whose 3 px halo covers the pixel. At `consensus ≤ 60` (2,741,649 px pool) the
  greedy fills the whole 37,600-dot budget at a worst informative near-dot share of **0.6985**, verified
  exactly against all 343 informative priors. Search the threshold from the loosest end and take the
  largest feasible one, so the field keeps as much signal as the lane allows.
* **`eligible` in the committed instrument is the valid footprint *including* catalogue pixels.** Passing
  the off-catalogue set empties both training classes (`spatial.folds` builds `truth = held_all & region`
  from the catalogue) and surfaces as "insufficient training classes", or, on a screen that only computes
  an AUC, as a silently wrong sufficiency number. This round produced View A mean AUC 0.6636 that way
  before the mistake was caught; the committed instrument gives **0.5281**. The wrong number is recorded in
  `knowledge/53` §2.1 so nobody resurrects it.
* **`spatial.whole_pseudo_segments` can return zero labels.** With H69's views it returned **0 pixels in
  all four folds**, so `disagreement_post` is bit-identical to `disagreement_pre` and the paired CI is
  exactly [0, 0]. Same class as `IR-H58-002`; check the count before interpreting a "post-exchange" arm.
* **A round must exclude its own artefacts from its registry.** `gates.find_priors` sweeps `submission/`,
  so a second attempt at the same stage finds the first attempt's GeoTIFF as a "prior" and reports
  identical-to-a-prior. `scripts/run_h69.py` filters `gems52-h69-*` and says so.
* **Cache the lane reports.** Two `lane_report` phases over 566 rasters cost ~13 min; they are now cached
  against the SHA-256 of the emission plus the prior count, which is the difference between a fixable
  crash and a lost quarter-hour.
