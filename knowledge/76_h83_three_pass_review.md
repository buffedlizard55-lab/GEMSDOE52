# H83 preflight — three-pass review

**Date:** 2026-10-10 UTC
**Review status:** Three passes complete.
**Disposition:** **NEGATIVE — pre-fit stop.** This review did not fit a model, evaluate a new holdout, write a candidate TIFF, upload to DrivenData, or choose a slot.

This review covers the H83 continuation documented in `knowledge/74_current_user_brief_2026-10-10.md` and `knowledge/75_h83_preflight_and_hypotheses.md`. Earlier H82 measurements are cited only as historical `HOLDOUT-DTI` comparisons and are not H83 results.

## Pass 1 — scientific claims, provenance, and binding gates

**Scope reviewed:** H33 interpretation; dated public-board evidence; the H77cond co-training sufficiency result; the literal all-census lane gate; the three proposed new hypotheses and their source/coverage claims; the H83 run card.

**Checks and findings:**

- Re-read `knowledge/42b_h65halo_results_and_limits.md`, the correction banner in `knowledge/49_why_02778_phd_answer.md`, and the governing `IR-H65halo-007`. The H33 byte-set facts (conditional on the hash-pinned owner mirror) support a strict-subset/selective-thinning description; they do **not** establish zero private-truth credit for the removed 100–200 m cells. New fault truth may lie within the official 300 m triangular kernel. The H33 filename/score attribution remains **OWNER-REPORTED**, not a submission-page receipt.
- Parsed `registry/leaderboard_snapshot_2026-10-10.json`: 50 rows; observation date is recorded, exact server fetch time is null/unavailable, and the score class says **PUBLIC-BOARD** at team level. The rank-1, rank-8, and rank-22 values are not mapped to any TIFF/hash/receipt. The page-visible `extradr19` row does not authenticate the reported H33 file mapping.
- Rechecked `knowledge/68_h77cond_results_and_limits.md`, the H77cond run records, `evidence/h82_lane.json`, and `knowledge/73_h82_results_and_limits.md`. The conditional ordering puts View A least informative where View B is blind; the measured sufficiency margin is −0.0543 against the preregistered +0.05 requirement. The separate literal full-census near-3-pixel rule is recorded as DUPLICATE/STOP for every nonempty raster because universal-coverage probes saturate it. No restricted census or other workaround is treated as a literal pass.
- Reviewed the three hypotheses against the recorded prior-work inventory and the official-source review: native-resolution 3DEP channel displacement, raw GeoDAWN flight-line repeatability, and season-normalized Landsat surface-temperature residuals. Their mechanisms are distinct from existing implementations, with prior related ideas disclosed; each names plausible non-fault mimics. USGS source/licence availability is recorded, but the exact 3DEP tiles, GeoDAWN payload/coverage, and cloud/QA-qualified Landsat observations were not obtained. None is claimed runnable or scored.
- Checked `evidence/h83_preflight_run_card.json`: no H83 holdout-DTI, candidate raster/hash, validator result, registry comparison, submission name/note, portal receipt, or slot is represented as a pass or zero. The prior H82 comparator is separately labelled `HOLDOUT-DTI`, with evaluator, withheld-positive count, and CI.

**Pass-1 verdict:** Claims are bounded to the available evidence. The top hypothesis was not fit or evaluated because the method/release stops and missing verified inputs remain binding. H83 stays negative; no slot was used.

## Pass 2 — implementation, feed, and regression tests

**Scope reviewed:** `scripts/refresh_feed.py`, `scripts/publish_h82_site.py`, `docs/site.js`, the H83 status/feed pages, generated feed JSON, and the H83 regression tests.

**Checks and findings:**

- `refresh_feed.py` keeps automated DrivenData fetch disabled under the recorded source policy, byte-preserves dated board snapshots, publishes `latest_preflight` separately from the last completed H82 research artifact, verifies the H82 archive SHA, and labels the local submission marker as not an organizer receipt. Its download count is limited to Git-tracked public TIFFs, excluding the publisher's untracked feed-staging copies. The date-only board observation is not converted to a midnight timestamp for a false 24-hour age warning.
- The local refresh stages 11 pre-existing `submission/*.tif` files under `docs/downloads` for the established prior-raster census. Each untracked copy was SHA-256 checked against its same-name submission source; all 11 match byte-for-byte. They are historical artifacts, not H83 outputs, are not added to the PR, and are excluded from the public download count.
- The H82 publisher now identifies H83 as the current preflight stop and H82 as an archive; its H82 TIFF remains the same hash and its downloadable verdict remains **DOWNLOAD YES, SUBMIT NO**. ZIP publication reuses a valid byte-identical one-TIFF archive instead of changing only ZIP timestamps on every render.
- The H83 page, current feed page, and root/docs landing pages distinguish “no H83 file” from the downloadable H82 archive, and link to the public-board data, feed, and NOT-RUN card. The H83 card copy in `docs/data/` is byte-identical to the source evidence card.
- `.venv/bin/python -m py_compile scripts/refresh_feed.py scripts/publish_h82_site.py tests/test_h83_preflight.py tests/test_workflows.py` passed. The final targeted command `.venv/bin/python -m pytest tests/test_h83_preflight.py tests/test_workflows.py -q` passed (8 tests). The full suite passed after restoring only verification fixtures under ignored `data/`: **482 passed, 7 skipped**, with 56 existing Rasterio pending-deprecation warnings.
- `scripts/check_site.py` initially could not start its legacy grid checks because `data/sample_submission.tif` was absent; the full suite also showed missing `data/labels.tif`. The two small hash-pinned owner-mirror files were restored solely for site/archive and legacy-output regression tests, documented in the run card and H83 report, and were not used for an H83 fit or holdout. Their provenance remains **NOT organizer-authenticated**. The first site-check run then found only the not-yet-created H83 three-pass-review link; that target is this file and is checked again in Pass 3.

**Pass-2 verdict:** The feed and publisher produce the intended current status; regression tests pass. The two restored files are verification-only, not new candidate data. The final whole-site check remains for Pass 3.

## Pass 3 — independent final verification

**Scope reviewed:** all 95 static HTML pages, 397 static data JSON files, the H83 README/report/page/feed links and explicit faults-not-vents task framing, source/run-card copies, archived H82 bytes, local submission-pointer semantics, Git-tracked download count, and the final worktree diff.

**Checks and findings:**

- `.venv/bin/python scripts/check_site.py` passed: 95 pages and 397 data files checked, no broken local links or strict-JSON/receipt failures, and the site's audited TIFFs served byte-identically. The checker reported 1,517 literal four-decimal values in older archived HTML as **informational**; it did not block the build. The scientific slot gate remains closed for the local H60 marker.
- A separate Markdown link scan of `README.md` and the H83 brief/report/review checked four files; every local link resolved. `docs/site.js` passed Node syntax validation as part of `check_site.py`.
- `git diff --check` passed. Strict JSON parsing, the 50-row board snapshot and byte-identical site copy, and the H83 source/card copy were verified. The H83 card still has null candidate HOLDOUT-DTI/raster/validator/registry-comparison values, zero experiments, and zero slots.
- Recomputed the H82 archived TIFF SHA-256 from both `submission/` and `docs/downloads/`: `17c3f8325ac6f267b1b8cc58bc6fd9495c118c30de64d5f78293d19d7f20c907`, matching its H82 run card. Its ZIP contains exactly one TIFF with the same decoded payload/hash. H82 remains DOWNLOAD YES, SUBMIT NO.
- The static feed deliberately distinguishes three states: H83 is the current preflight stop; H82 is the latest completed research archive; and the legacy global `submission/LATEST.txt` / `docs/data/submission.json` marker remains H60. H82 has its own round marker. These are local repository pointers, not organizer receipts. H83 did not alter either pointer or upload/select anything.
- `docs/data/feed.json` reports 73 Git-tracked public GeoTIFFs; 84 happen to be present locally because of the 11 untracked staging copies described above. The Git-backed count was independently compared with `git ls-files`, and none of those 11 TIFFs is part of the diff.
- `submission/` contains no H83-named TIFF. The only restored files under ignored `data/` are the documented verification fixtures; no model cache, external proposal data, or 1 m tiles were restored.

**Pass-3 verdict:** Site, link, JSON, archive-hash, and no-candidate/no-slot checks are consistent. No H83 artifact or promotion is authorized.

## Corrections, limitations, and release boundary

- H83 was stopped before model fitting. A holdout result cannot be manufactured by borrowing H82 values; no projection is reported as a score.
- The official source metadata does not establish obtainability/coverage for the exact candidate tiles or scenes. No 3DEP, GeoDAWN, Landsat, or INGENIOUS binary data were downloaded for H83.
- The public leaderboard is a dated team-level observation only. It is neither private-round truth nor an organizer submission-page receipt.
- The only restored data files are the two integrity-pinned owner-mirror verification fixtures described above; they remain outside Git under the repository's ignored `data/` convention.
- No H83 TIFF exists. H82 may be downloaded for inspection, but its verdict remains **DOWNLOAD YES, SUBMIT NO**. Slots used: **0**.
- Arena values preserved: **Maximize P(Win)** and **Own the Outcome**. The README's H83 direction block is the starting point for future work.
