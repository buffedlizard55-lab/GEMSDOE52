# Working agreement

Before every work session, read `README.md`, its full current user brief, `knowledge/07_r2_hypotheses_preregistered.md`, and the newest review/irregularities record. Read previous failed experiments before proposing another.

Maximize P(Win): prioritize geological signal and trustworthy spatial validation. Never spend a competition upload slot unless the new candidate has beaten the current comparable holdout best. Own the Outcome: verify written files, served downloads, reproducibility, provenance and failure cases end to end.

Keep known-catalogue labels separate from verified fault absence, public participant scores separate from filename attribution, hypotheses separate from discoveries, and format-valid artifacts separate from promotion-approved ones. Do not invent organizer validation or claim a guaranteed leaderboard gain. A GeoTIFF with a new name or compression is not a unique prediction; compare decoded pixels.

This session's working branch is fixed by Arena. Do not change branches. Keep raw competition data and large intermediate arrays under ignored `data/` and `work/`. Publish small audit receipts, the unique compressed prediction raster and its review table.

<!--H67-AGENTS-->
## Current H72 continuation (2026-10-09)

Read `README.md`'s H72 block first, then `knowledge/59_hypotheses_H72_preregistered.md` (frozen,
SHA-256 pinned in `registry/h72_preregistration.json`) and `knowledge/60_h72_results_and_limits.md`.
H72 executed the deferred **H70-E** variant — a **deformation-only View A2** (geodetic strain bands
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
(`docs/downloads/h72-a-only-reasoning.csv`). Do **not** re-run the co-training lane with another View
A rebuild — both halves are now measured (potential-field: H61/H63/H64/H65/H70; deformation-only:
H72). H72-D (radiometric-cover gating) and H72-E (H65 operator on the strain bands) remain deferred.
IR-H72-001 (build CSR orientation crash, fixed, regression-tested) is in
`registry/irregularities.json`.

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
