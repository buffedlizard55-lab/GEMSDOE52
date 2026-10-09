# Working agreement

Before every work session, read `README.md`, its full current user brief, `knowledge/07_r2_hypotheses_preregistered.md`, and the newest review/irregularities record. Read previous failed experiments before proposing another.

Maximize P(Win): prioritize geological signal and trustworthy spatial validation. Never spend a competition upload slot unless the new candidate has beaten the current comparable holdout best. Own the Outcome: verify written files, served downloads, reproducibility, provenance and failure cases end to end.

Keep known-catalogue labels separate from verified fault absence, public participant scores separate from filename attribution, hypotheses separate from discoveries, and format-valid artifacts separate from promotion-approved ones. Do not invent organizer validation or claim a guaranteed leaderboard gain. A GeoTIFF with a new name or compression is not a unique prediction; compare decoded pixels.

This session's working branch is fixed by Arena. Do not change branches. Keep raw competition data and large intermediate arrays under ignored `data/` and `work/`. Publish small audit receipts, the unique compressed prediction raster and its review table.

<!--H74-AGENTS-->
## Current H74 continuation (2026-10-09)

Read `README.md`'s H74 block first, then `evidence/h74_build.json` (build, gates, run card),
`evidence/h74_holdout.json` (all eight arms with CIs) and `evidence/h74_budget_sweep.json`.

H74 is **negative at the holdout gate and positive at the format/uniqueness/lane gates**. Verdict:
**DOWNLOAD YES, SUBMIT NO**, slots used 0. The shipped artefact is
`gems52-h74-viewb-boardplaced-37654px-20261009T194504Z.tif` (SHA-256 `f7f234af…02452f49`), published
one-click at `docs/downloads/h74-candidate.tif` with the verdict on the root `index.html` and
`docs/h74-executive-summary.html`. Experiments used: 3 of 3.

Facts the next round must respect:

- **Data placement is not a blocker any more.** `scripts/restore_data.py` restores all 23 manifest
  entries from the owner's hash-pinned sibling repos through the GitHub Contents API and verifies
  every SHA-256 (`ALL_VERIFIED=True`), including the 419 MB feature raster in five parts.
  `api.github.com` is inside the sandbox egress allowlist. Do not repeat the claim that this needs
  an unrestricted machine.
- **Use `gems52.grid.write_geotiff_portal_exact`.** It writes the organiser template's own container
  (LZW, stripped, `nodata=nan` outside the footprint) and re-reads its output, refusing anything the
  portal's stated rule could reject. Do not add another packaging variant (IR-H74-004).
- **All five new detectors are measured negative** (basement curvature × thin cover 0.078442,
  geodetic dilatation gradient 0.068369, conductivity × basement-step 0.061497, antithetic basin
  margin 0.043613, LiDAR × radiometric-K 0.086684, rank fusion 0.069808) against `single_B`
  **0.174571** [0.153568, 0.194531] and random 0.082399. Do not re-tune them on this protocol.
  `run_h61.py fit` reproduces View A 0.5163 / View B 0.6843 exactly, so the instrument is sound.
- **Placement headroom is closed.** The family's thinning ladder (`h19_5` → `d1_5` → `d2_8` →
  `h33-2-b2`) retains 0.766 of its credit where the geometric optimum is 0.798 — within 4 %.
  `|G|` is pinned at 14,088.7 px from the exact nested pair, and beating 0.3195 at 37,654 px needs
  `T ≥ 6,007` against the champion's measured 5,223. That is a detector problem, not a placement one.
- **The lane gate only passes on a consensus ≤ 1 pool** (856,910 of 4,930,382 legal px), which is
  also why the file's expected board score is low: consensus ≤ 1 means no prior submission in the
  family emitted there. Do not present the unrestricted field's 0.253693 as a projection for it.
- **The holdout instrument hides CATALOGUE faults; the competition scores faults the catalogue
  lacks.** SGMC is 95 % disjoint from `labels.tif` (79,615 off-catalogue px). That mismatch is the
  likeliest cause of the measured Spearman −0.10 between holdout DTI and board score (IR-H74-005).
  An off-catalogue instrument is the highest-value unbuilt tool in this repository.
<!--/H74-AGENTS-->

<!--H67-AGENTS-->
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
