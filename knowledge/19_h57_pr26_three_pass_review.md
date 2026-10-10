# PR #26 — three-pass integration and safety review

**Review date:** 2026-10-10 (America/Los_Angeles)
**Scope:** PR #26's H57 real-raster co-training archive and its integration with the latest upstream `main`. This review does not rerun the frozen H57 experiment, promote an artifact, spend a slot, or authorize a portal upload.

## Pass 1 — merge structure, path collisions, and pointers

- Reviewed PR head `ea8d4d31783e4afb71005fee56a15416b54df5a1`, the pre-H83 upstream reconciliation point `22091610117447c174b65d074d0df73d2a8b2e27`, and the later upstream main `ebb1d343f8f5a5a33a5835776add16b668f6fbea`.
- Kept main's distinct H57 code and records at `src/gems52/h57.py`, `registry/h57_preregistration.json`, and `knowledge/17_hypotheses_H57_preregistered.md`. PR #26's bytes remain separately namespaced as `src/gems52/h57_real.py`, `src/gems52/h57_real_spatial.py`, `registry/h57_cotrain_disagreement_preregistration.json`, and `knowledge/18_hypotheses_H57_cotrain_preregistered.md`. The frozen registration and hypothesis slate retain their recorded SHA-256 values.
- Confirmed `submission/LATEST.txt` and `docs/data/submission.json` still identify H60 and its weekly-slot gate is false. H57 is an archived experiment, not a pointer. The newer H83 page is explicitly labeled research-only; it is not silently promoted to the H60 pointer.
- Preserved the complete original task prompt in `README.md`; current status claims above it are reconciled against current evidence rather than copied from the historical prompt.

**Pass 1 result:** no path overwrite of main's H57 artifacts; pointer and frozen preregistration bytes preserved.

## Pass 2 — scientific result, bytes, score provenance, and approval

- H57's registered co-training result remains negative: mean HOLDOUT-DTI `0.110665` versus matched View B `0.151305`, paired lift `−0.040641`, and 0/4 folds improved. The published H57 archive says do not submit. No new holdout or scientific result was produced during this merge.
- H83's tracked run card states HOLDOUT-DTI `NOT_EVALUATED`, weekly-slot approval is unset, and its `promote` label describes a format-only run. Therefore H83 is downloadable for review but not approved to submit.
- Read both distinct H83 rasters. The linked 81,076-byte file has SHA-256 `d9cfccf0e1aa4e28094a6039fda9e65be5e8ff102e321b33745df149f477f378`, all 12,279,160 cells finite, 37,654 ones, no nodata tag. The separate 1,558,064-byte TIFF has SHA-256 `274db602ec8b91cb6a2793e9f512321f32326298aa8ed031ebd478e21426f5cd` and NaN nodata outside its finite footprint. `docs/downloads/h83-candidate.json` describes the latter, not the linked file. Restored the hash-pinned sample mirror in `registry/data_manifest.json` (SHA-256 `2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc`) from GEMSDOE24 and verified matching shape, CRS, and transform. All 37,654 linked-H83 positives fall within the mirror's finite-cell support; the distinct variant has 161 positives outside that support and 3,073 mirror-finite cells encoded as NaN. The mirror is owner-supplied and NOT organizer-authenticated, so it does not certify the official mask semantics or portal acceptance.
- A local positive-mask scan found no exact match among 124 other tracked same-grid TIFFs; the maximum Jaccard was 0.008739 (542 shared cells) against H67. This is local repository evidence only, not global novelty or a quality/score result.
- Integration adds the H57 co-training/disagreement raster to the current prior inventory. The post-integration R5 comparison finds 143 shared positives out of 16,681 against that H57 arm (0.991427 remain unshared against that arm); the full unfiltered inventory reports 0.822493 across 122 rasters. R5 remains exact-pattern unique and is not the literal union. Its frozen receipt's 1.000000 across 71 build-time priors is preserved as historical evidence, not relabeled as current novelty; the site checker now reports the changed current comparison separately while keeping the global duplicate and union checks fail-closed.
- The dated public leaderboard capture `registry/leaderboard_snapshot_2026-10-09.json` reports xiaofanhu 0.3774 at rank 1, DARD 0.3195 at rank 7, and extradr19 0.2778 at rank 17. It is an organizer-published, team-level snapshot, not a filename/hash/receipt mapping. The public `GEMSDOE32` H33 TIFF has SHA-256 `c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9`; no organizer receipt in this checkout binds that TIFF to extradr19's 0.2778 team score. The 0.3195 figure is not the snapshot's highest score.
- Added `evidence/h83_status_reconciliation.json` and the identical site-data copy to preserve the file mismatch, score scope, pointer state, and fail-closed disposition without changing the historical H83 run card or H57 preregistration.

**Pass 2 result:** H57 remains no-go; H83 remains no-go pending comparable spatial-block evidence and verified input provenance. The local template check uses an owner mirror, so organizer mask semantics and portal acceptance remain unverified. Neither result was submitted or promoted.

## Pass 3 — user-facing labels, regression tests, and site checks

- Removed H83 portal-upload instructions and unsupported expected-score projections from the front-page/summary paths. Pages now distinguish a download link from format observations, spatial validation, and organizer approval; H83's exact linked file and the distinct older variant are identified separately.
- Reconciled H54/H55/H56 and H57 archival notices to state that H60 is still the canonical pointer, H83 is the latest research page but not approved, and H57/H56 are historical archives. Corrected the stale H57-as-pointer text in the irregularities archive.
- Restored the browser TIFF parser in `docs/validator.html` and clearly state that it runs locally, uploads nothing, and cannot provide scientific or organizer approval.
- Added H83 safety/provenance regressions in `tests/test_h83_status_reconciliation.py`; retained H57 namespace/no-current-pointer coverage in `tests/test_h57_real.py`.
- Restored `sample_submission.tif` and `labels.tif` through `scripts/restore_data.py` using the manifest's SHA-pinned GEMSDOE24 mirror; those ignored local inputs were not added to Git and are not organizer-authenticated. The full suite passed with no data-dependent deselection: `488 passed, 8 skipped`. `scripts/check_ctd5_release.py` passed with `verdict: negative`, `submit_ok: false`, and `strict_holdout_valid: false`. `scripts/check_site.py` passed all 96 pages and 411 data files, including its R5 raster/duplicate/union closure and byte-serving checks. It now keeps R5's 1.000000 build-time receipt distinct from the current 0.991427 timestamp-filtered and 0.822493 unfiltered inventory comparisons; the exact-pattern and literal-union guards remain fail-closed.

**Pass 3 result:** the current public labels preserve H57/H83 research-only/no-go status and H60 as canonical. Local verification is complete against the integrity-pinned mirrors, but those mirrors do not substitute for organizer authentication. No portal upload or weekly-slot use occurred; CI is still required for the pushed commit.

## Final disposition

PR #26's requested merge is authorized. Push/PR merge actions are in scope. Competition-portal upload is not authorized. Do not spend a weekly slot unless a future candidate beats the comparable spatial-block holdout baseline under the frozen gate.
