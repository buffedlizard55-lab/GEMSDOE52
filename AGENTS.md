# Working agreement

Before every work session, read `README.md`, its full current user brief, `knowledge/07_r2_hypotheses_preregistered.md`, and the newest review/irregularities record. Read previous failed experiments before proposing another.

Maximize P(Win): prioritize geological signal and trustworthy spatial validation. Never spend a competition upload slot unless the new candidate has beaten the current comparable holdout best. Own the Outcome: verify written files, served downloads, reproducibility, provenance and failure cases end to end.

Keep known-catalogue labels separate from verified fault absence, public participant scores separate from filename attribution, hypotheses separate from discoveries, and format-valid artifacts separate from promotion-approved ones. Do not invent organizer validation or claim a guaranteed leaderboard gain. A GeoTIFF with a new name or compression is not a unique prediction; compare decoded pixels.

This session's working branch is fixed by Arena. Do not change branches. Keep raw competition data and large intermediate arrays under ignored `data/` and `work/`. Publish small audit receipts, the unique compressed prediction raster and its review table.

<!--H83-AGENTS-->
## Current H83 continuation (2026-10-10) — READ FIRST

Read the H83 block at the very top of `README.md`, `knowledge/74_current_user_brief_2026-10-10.md`,
`knowledge/75_h83_preflight_and_hypotheses.md`, `knowledge/76_h83_three_pass_review.md`,
`evidence/h83_preflight_run_card.json`, and `registry/leaderboard_snapshot_2026-10-10.json`.

H83 is a **pre-fit stop**, not a model run: no experiment, no new holdout, no H83 TIFF, no portal upload,
no slot. The candidate-ranked slate is research-only. The H77cond conditional sufficiency result closes the
ordinary co-training lane; the literal full-census near-3-pixel rule is DUPLICATE/STOP for every nonempty raster
because of universal-coverage probes. Do not work around either gate or present a restricted-census pass as a
literal pass. The H33 pruning interpretation is corrected in `knowledge/42b_h65halo_results_and_limits.md`
and `IR-H65halo-007`: exact zero credit for the deleted 100–200 m ring is **not established**.

The official 3DEP, GeoDAWN and Landsat source pages were checked, but exact H83 coverage/files were not downloaded.
The workspace had no `data/`, `work/r2/features`, or `work/h82` at preflight. Afterward only two small
owner-mirror fixtures were restored for verification: `sample_submission.tif` for `scripts/check_site.py` and
`labels.tif` for regression checks of historical outputs. Both are integrity-pinned, not organizer-authenticated,
and neither was used for an H83 fit or holdout. Do not claim the top 1 m drainage hypothesis was tested. Do not use the archived H82 TIFF as an H83 submission; its verdict remains DOWNLOAD YES,
SUBMIT NO. The public board snapshot is dated and team-level; no filename/score receipt exists.

<!--/H83-AGENTS-->

<!--H82-AGENTS-->
## H82 completed-run archive (2026-10-09)
Read README's H82 block, `knowledge/72` (frozen preregistration, amendment 72a included, SHA-256
`fe7050eb…`) and `knowledge/73` (results and limits). H82 executed H75's own "next" item — a scored-only
lane registry — and one frozen experiment with six arms. Verdict **NEGATIVE**, experiments 1/3, slots 0.

What is now settled, and must not be re-litigated:

- **Do not re-run the 8-direction fan plus a strike-alignment channel as one arm.** The attribution is
  clean and in all four folds: `B_DVA2` (fan only) mean AUC 0.7124 and HOLDOUT-DTI 0.189200 — the best
  number this repository has measured; `B_VSA` (alignment only) 0.6511 / 0.142148, *below* `single_B`
  0.6849 / 0.174910; the frozen primary `B_DVA2_VSA` 0.6720 / 0.150591, paired −0.024319
  [−0.039025, −0.006869] against `single_B`. Adding VSA to DVA2 costs 0.038609 DTI.
- **Why VSA failed is measured, not guessed.** θ_max is an argmax over 8 discrete directions, so
  `cos2reg` against a scalar strike takes only **4 distinct values** (middle histogram bin exactly empty
  on a 100k sample); and `cos2loc` is exactly 0 on 46.7–69.9% of eligible pixels where the local tensor is
  degenerate. Both are low-entropy channels pooled with 50 informative floats.
- **`B_DVA2` may not be promoted post hoc.** `registry/h82_preregistration.json →
  attribution_arms_not_promotable` forbids it. It must be pre-registered fresh as H77's primary *before
  any fit*, together with the fix for the quantisation above (a 16/32-direction fan, or a continuous
  sub-pixel θ_max by parabolic interpolation across the fan or a structure tensor on the γ field).
- **The strike in this area is N10°W–SSE (166.7–171.8° compass) with R only 0.37–0.45**, measured per fold
  from visible catalogue. Do not write "regional NNE" into a hypothesis for this footprint again.
- **View A sufficiency has now failed seven times** (mean 0.5113, min fold 0.4309 — anti-informative).
  Independence *passes* (max |ρ| 0.1317 over 2,089 blocks, bar 0.60) but independence without sufficiency
  gives co-training nothing to donate, and H71 already measured that exchange lowers A2's OOF AUC
  (0.5019 → 0.4759). Stop proposing plain pseudo-label exchange on this View A.
- **The lane is satisfiable at full budget against the scored-only registry.** `run_h73.place_lane` filled
  37,654/37,654 dots at worst near-dot share 0.4445 (bar 0.70), where H75 short-filled at 35,858/0.7350.
  The full-census literal rule still returns DUPLICATE/STOP because the census contains
  universal-coverage lattice probes (near-3px 1.0 for *every* nonempty raster), and a restricted PASS never
  waives it. H77 should pre-register the quota-placed emission as its E3 output rather than the
  unconstrained one.
- **Every `np.save` in a runner must go through a verified writer.** H82's first build produced 8 files of
  79 with one 4 KiB page of zeros after the .npy header (IR-H82-002); `save_verified()` in
  `scripts/run_h82.py` re-reads each file and rewrites until bit-exact, and `Bank.col` refuses a column
  whose bytes do not match its manifest digest. Copy this pattern; do not write channels with a bare
  `np.save`.
- **`gems52.azimuth.axial_resultant` returns `(mean, R, n)`** — the third value is a weighted pixel count,
  not a circular SD. The axial circular SD is `sqrt(−2 ln R)` (Mardia–Jupp), undefined as R → 0.
- **The H75 control does not reproduce inside 1e−3 from a re-implementation** (B_DVA 0.187587 vs committed
  0.186352, |Δ| 1.23e−3; IR-H82-004). If a round needs an exact replay of an earlier round's channels,
  persist those channels as an artifact instead of re-deriving them; `single_B` still reproduces at 3.9e−4.
- **Site:** `docs/index.html` is current-first with every previous round preserved verbatim inside one
  collapsed `<details>` (`<!--ARCHIVE-START-->`/`<!--ARCHIVE-END-->`). `scripts/check_site.py` asserts a
  dozen historical strings on that page, so never rewrite it from scratch — `legacy_index_body()` in
  `scripts/publish_h82_site.py` carries them forward and is idempotent. `docs/validator.html` +
  `docs/assets/tifcheck.js` decode a candidate in the browser (TIFF none/LZW/DEFLATE, predictor 1/2,
  strips/tiles, ZIP) and are pinned by test against rasterio-measured pixel counts. `check_site._stamp`
  now reads `<alias>-receipt.json` sidecars and date-only filenames; that repaired a pre-existing
  "R5 novelty recomputed 0.992087 != receipt 1.0" failure, now 1.0000 over 71 rasters.

File `docs/downloads/h82-candidate.tif` (`gems52-h82-dva2vsa-B-37654px-20261009T213414Z.tif`, 140,555 bytes,
SHA-256 `17c3f8325ac6f267b1b8cc58bc6fd9495c118c30de64d5f78293d19d7f20c907`) is **DOWNLOAD YES, SUBMIT NO**.

<!--/H82-AGENTS-->
<!--H77-AGENTS-->
## Current H77 continuation (2026-10-09)

Read `README.md`'s H77 block first, then `evidence/h77_build.json` (build, gates, run card),
`evidence/h77_holdout.json` (all eight arms with CIs) and `evidence/h77_budget_sweep.json`.

H77 is **negative at the holdout gate and positive at the format/uniqueness/lane gates**. Verdict:
**DOWNLOAD YES, SUBMIT NO**, slots used 0. The shipped artefact is
`gems52-h77-viewb-boardplaced-37654px-20261009T194504Z.tif` (SHA-256 `f7f234af…02452f49`), published
one-click at `docs/downloads/h77-candidate.tif` with the verdict on the root `index.html` and
`docs/h77-executive-summary.html`. Experiments used: 3 of 3.

Facts the next round must respect:

- **Data placement is not a blocker any more.** `scripts/restore_data.py` restores all 23 manifest
  entries from the owner's hash-pinned sibling repos through the GitHub Contents API and verifies
  every SHA-256 (`ALL_VERIFIED=True`), including the 419 MB feature raster in five parts.
  `api.github.com` is inside the sandbox egress allowlist. Do not repeat the claim that this needs
  an unrestricted machine.
- **Use `gems52.grid.write_geotiff_portal_exact`.** It writes the organiser template's own container
  (LZW, stripped, `nodata=nan` outside the footprint) and re-reads its output, refusing anything the
  portal's stated rule could reject. Do not add another packaging variant (IR-H77-004).
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
  likeliest cause of the measured Spearman −0.10 between holdout DTI and board score (IR-H77-005).
  An off-catalogue instrument is the highest-value unbuilt tool in this repository.
<!--/H77-AGENTS-->
<!--H81-AGENTS-->
## Current H81 continuation (2026-10-09)
Read README's H81 block first, then `knowledge/69_h81_hypotheses_ranked.md` (ranked candidates), `knowledge/70_h81_preregistered.md` (frozen; SHA-256 pinned in `registry/h81_preregistration.json`) and `knowledge/71_h81_results_and_limits.md`.
Verdicts: H81-1 (band-18 DVA) **NEGATIVE** (paired +0.0020, CI [−0.0015, +0.0052]); experiments used 1 of 3; slots 0. The H75 file is **research-only: do not submit**. It fails the lane gate (literal 1.000, policy 0.922) AND the support-novelty gate (novel fraction 0.0, subset of the 566-prior union). "Unique" in older blocks means canonical decoded pattern only.
Corrections: the committed H75 single_B holdout is replaced by a fresh-process run (0.174571; IR-H81-003). Run each stage in its own process. Use `scripts/run_h81.py`, which reuses H75 predictions and fits only B_DVA18.
Next: lane-rule decision by the owner (H81-4) before any further holdout work; then H81-2 (antithetic band-15 step, untested), and H81-3 (magnetic-gradient DVA) only after a flight-line artefact check.
<!--/H81-AGENTS-->

<!--H75-AGENTS-->
## Current H75 continuation (2026-10-09)
Read README's H75 block, `knowledge/65` (+65a/65b) and `knowledge/66`. H75: B_DVA (View B + directional variogram
anisotropy) beats single_B on the holdout (+0.0118, CI [0.0068, 0.0174]); the near-dot lane gate fails (0.922). Experiments 3/3,
slots 0. File `docs/downloads/h75-candidate.tif` is DOWNLOAD YES, SUBMIT research-only (owner override of lane rule required).
Next: preregister a registry restricted to scored submissions, then retest the lane.

<!--H67-AGENTS-->
## Current H77cond continuation (2026-10-09) — READ THIS FIRST

> **Identifier note.** This round was executed as "H74" and renamed to **H77cond** at merge time: a
> parallel session running the same brief merged its own H74 into `main` first (directional
> variogram anisotropy), and H75 was taken by a third. The rename is identifier-only — the
> preregistration document's bytes are unchanged and its pinned SHA-256
> `d117b265…e3b55` still validates, so the "frozen before any fit" claim is intact.
> Same remedy as IR-H66-015 / commit `9d891a6`. See `registry/h77cond_preregistration.json`
> → `identifier_rename`.

Read `README.md`'s H77cond block, then `knowledge/67_hypotheses_H77cond_preregistered.md` (frozen, SHA-256
`d117b265…e3b55`, pinned in `registry/h77cond_preregistration.json`), its dated amendment
`knowledge/67a_h77cond_amendment_shipped_arm_rule.md` (shipped-arm rule, written before any holdout number
existed), and `knowledge/68_h77cond_results_and_limits.md`.

**The co-training lane is now closed with a mechanism, not just a failed threshold. Stop re-opening it.**

1. **The rescue argument is dead.** Every earlier round closed the lane on S1 — View A's out-of-quadrant
   AUC on *all* held-out truth is ~0.52. The standing rescue was "the catalogue only contains
   surface-expressed faults, so S1 measures the wrong population". H77cond tested that directly (S1′: View A's
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
   70 % near-dot rule without paying DTI.** `H.line_support` in `scripts/run_h77cond.py` is unit-tested
   (`_shift0` is zero-filled, never wrapped).
5. **Controls reproduced exactly**, so the instrument is sound and these numbers are comparable to H70:
   `single_B` 0.1745172876 vs the committed 0.174517 (|Δ| **2.9e-07**), `single_A` 0.071954,
   `disagreement_pre` 0.033293, `random` 0.080426 — all identical to H70 to six decimals.
6. **Reusable tooling added this round.** `scripts/h77cond_build.py` has `_place` (greedy + 3 px hard core +
   exact per-prior near-dot quota) which is **verified bit-identical to `gems52.nodes.spacing_select`**
   when the quota is off, `_bit_transpose` (per-pixel prior bitmap; turns the quota lookup from a
   cache-hostile strided gather into a 19-byte contiguous read), `_exclusion_stamp` (matches
   `spacing_select`'s strict `<` rule, unlike `gates._disk`'s `<=`), and `_disagreement_audit`
   (cardinal-orientation falsifier for the brief's B-only "roads/erosion" reading).
7. **Band labels: check `src/gems52_h1/spec.py` `OFFICIAL_BANDS` before naming any band.** IR-52-01 bit
   this round: band 6 `tc` is a **magnetic** tilt/total-curvature derivative, *not* radiometric total
   count. True gamma-ray channels exist only in the external GeoDAWN layers (`X_rad_*`).

Experiments used: 3 of 3. Slots used: 0. Verdict: **negative, research-only** — see the README H77cond block
for the DOWNLOAD/SUBMIT decision on the emitted file.

## Current H74 continuation (2026-10-09)

Read `README.md`'s H74 block first, then `knowledge/63_hypotheses_H74_preregistered.md` (frozen,
SHA-256 pinned in `registry/h74_preregistration.json`) and `knowledge/64_h74_results_and_limits.md`.
H74 executed the deferred **H70-E** variant — a **deformation-only View A2** (geodetic strain bands
4/7/8 + seismicity bands 10/16, 22 channels) with View B unchanged — the lane's only untested View A
half. **Verdict: NEGATIVE, research-only. DOWNLOAD YES; SUBMIT NO. Slots used: 0. Experiments used:
3 of 3.** The lane's attribution question is now closed: View A2 out-of-quadrant AUC mean **0.5194**,
min fold **0.5011** → S1 sufficiency **FAIL** (sixth consecutive failure; the deformation half alone
is as non-transferable as the mixed View A, so the failure is common to both halves of the
subsurface stack on this grid, not attributable to the potential-field channels). Independence on the
A2/B pair held with the lane's lowest measured correlation (max |ρ| **0.0765** < 0.60 → exchange
allowed); the exchange moved 15,986 whole-segment pseudo pixels and **dropped** View A2's OOF AUC
(0.5019→0.4759, 0.5011→0.4741, 0.5234→0.4796, 0.5513→~0.48) — the donor labels amplify the
deformation view's bias, the brief's own warning. HOLDOUT-DTI (gems52-pooled-hide-v1, 9,400
dots/fold/arm, 53,186 withheld positives): `a_only` **0.050048** [0.035285, 0.065611] vs `single_B`
**0.174517** [0.152316, 0.196299] (control reproduced to 2.9e-07), paired Δ **−0.124469**
[−0.149150, −0.099436] — the strict A2-only stratum is again anti-informative (below random
0.080426); `single_B_veto_Bonly` 0.167026 and `concordant` 0.118511 both lose to `single_B` again.
Leakage canary max alarm AUC **0.6687**, no alarm. The build emitted the strict A2-only stratum
(1,965 candidate cells after exact novelty) at **721 dots** (candidate exhaustion; every budget probe
placed 721) with the measured worst informative near-dot share **0.9945** → **no lane-valid emission
exists**; dots lane literal **DUPLICATE/STOP** (lattice probe), policy **DUPLICATE/STOP** (max near
**0.8835**); surface lane PASS/PASS (max ρ 0.0110). The file is format-valid, canonical-pattern
unique, tier-2 novel_fraction **1.0**, not the prior union, and every one of its 721 cells is a
strict A2-only candidate with a written geological reasoning row
(`docs/downloads/h74-a-only-reasoning.csv`). Do **not** re-run the co-training lane with another View
A rebuild — both halves are now measured (potential-field: H61/H63/H64/H65/H70; deformation-only:
H74). H74-D (radiometric-cover gating) and H74-E (H65 operator on the strain bands) remain deferred.
IR-H74-001 (build CSR orientation crash, fixed, regression-tested) is in
`registry/irregularities.json`.

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
