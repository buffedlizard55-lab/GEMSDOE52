# H97-A three-pass review

**Review scope:** the single registered H97-A experiment only. H97-B/C/D are not runs. This review cannot authorize a TIFF after the registered stop, select a submission slot, or convert HOLDOUT-DTI into a board score.

## Pass 1 — preregistration, hypothesis ranking, sources, and provenance

**Status: complete; no pre-fit gate breach found.**

- Re-read the H97 registration and hypothesis document. `registry/h97_preregistration.json` pins `knowledge/97_hypotheses_H97_preregistered.md` at SHA-256 `47f8ce6e87913ae6e67a304a16ece786f941a8d5f8cd3a6962258e7b405cdee0`; the runner's `check_prereg()` verifies the pin. The registration predates the supervised fit/canary/holdout; H97-A is the only selected proposal. H97-B/C/D remain unrun. All expected score-change ranges are planning priors, never evidence.
- Confirmed the views are genuinely separate. The fit records 38 View-A inputs (36 FeatureStore inputs plus two tilt-depth channels), 69 strict View-B inputs (37 FeatureStore inputs plus 32 H84 elevation/elevation-slope DVA2/HVA/COH channels), and 87 historical H84 control inputs. The intersection between the named A and strict-B inputs is empty. The 81-column H84 channel bank is hash-verified. The H84 `B_DVA2` control includes gravity/depth channel content and is not described as a pure-B H97 feature set.
- Checked the external-source policy. No new external layer was needed; local GeoDAWN-derived radiometric/magnetic bytes are owner-mirrored cache content, integrity-pinned but not organizer-authenticated. The official USGS GeoDAWN record is linked in the preregistration. Salem et al.'s official SEG DOI for tilt-depth is `10.1190/1.2821934`; the prior H92 DOI typo is corrected in the H97 source note. Blum & Mitchell is a method reference, not proof that the data satisfy co-training assumptions.
- Checked the H33-2-B2 score caveat against the owner page and team-level public board. H33's project-page 0.2747 is a projection and the page says no organizer score exists. The board does not identify filenames or hashes, so the 0.2778 `extradr19` row is not attributed to H33-2-B2.
- Confirmed the four ranked proposals are all in the single co-training/disagreement lane and that only H97-A consumed an experiment. No external-data-dependent proposal was called viable without an official source/availability check.

**Pass-1 disposition:** protocol, source discipline, preregistration hash, and scope all match the frozen record. No amendment to the hypothesis or outcome gates was made.

## Pass 2 — inputs, fold mask, leakage, views, independence, and holdout arithmetic

**Status: complete; the negative result is supported by the registered receipts.**

- Recomputed from the receipts that fold truth counts `[27,309, 10,677, 6,813, 8,387]` sum to **53,186** on **4,593,171** eligible pixels. This matches H82/H84; the H96 60,894-positive mask is not compared as if identical.
- Independently cross-checked the feature counts and disjoint names: `n_A=38`, `n_B_strict=69`, `n_H84_control=87`, no A/B name intersection, 81 channel files with recorded hash verification, 32 selected surface DVA2/HVA/COH channels limited to elevation and elevation-slope bands.
- Rechecked the 157-feature leakage canary: maximum direction-insensitive AUC **0.6707506**, below the 0.90 alarm.
- Rechecked View-A OOF AUC values `[0.50844, 0.59659, 0.44470, 0.49056]`, mean **0.51007**, minimum **0.44470**. The registered mean/min-fold requirements fail. The negative-proxy error-correlation measurement has 2,089 blocks and max absolute correlation **0.09666**, but catalogue-zero labels are not verified absences and weak correlation does not establish conditional independence. The failed sufficiency gate correctly blocks exchange; pseudo-label training is false.
- Rechecked that every pooled score row in `evidence/h97_holdout.json` is labelled HOLDOUT-DTI, uses `gems52-pooled-hide-v1`, reports 53,186 withheld positives, and includes a 95% CI. H97-A is **0.1862646 [0.1648063, 0.2075371]**; same-run H84 control is **0.1928308 [0.1707905, 0.2136956]**. The paired difference is **−0.0065662 [−0.0151041, +0.0002708]**. The historical project-reported H84 control **0.1928291** reproduces within the registered 0.001 tolerance (absolute delta 1.73×10⁻⁶). The primary promotion gate fails.
- Re-read `evidence/h97_tilt_depth.json`: there are 5 +45° and 5 −45° threshold cells, not connected contours, and p50/p95/p99/max depth proxy values all saturate at 5,000 m. This is explicitly disclosed as a diagnostic limitation, not a validated depth solution.

**Pass-2 disposition:** matched-mask and same-run control requirements are met; the leakage canary and negative-correlation diagnostic pass, but View-A sufficiency does not. No pseudo-label exchange was used. HOLDOUT-DTI is negative versus the registered H84 control.

## Pass 3 — placement, prior registry, no-artifact writer, docs, tests, and changeset review

**Status: complete after final repository checks below.**

- Confirmed the frozen prior inventory restore was complete before lane checks: 526/526 Git blobs, 524/524 eligible aligned-raster byte hashes/shape/CRS, zero restore errors. The full surface and dot checks covered 703 aligned/registered paths.
- Rechecked ordering and thresholds: surface-before-placement passed at maximum Spearman **0.4725123**; final-dot literal gate stopped at **1.0000** within-3-pixel fraction, and the informative-prior diagnostic also failed at **0.9229**. This is not waived by the surface pass or by probe exclusions.
- Rechecked the candidate-vs-union definition separately from single-view identity. Candidate-vs-union passes (not identical and not a subset; Jaccard 0.4012); the selected placement is nevertheless identical to strict single View B (Jaccard 1.0). The initial receipt conflated those tests; its stored boolean was corrected from the already-recorded comparison facts. No model refit, re-placement, score change, or gate waiver resulted from that correction.
- Re-read the writer receipt and filesystem. `artifact_written=false`, `download_ok=false`, `submit_ok=false`; no H97 `.tif` or `.zip` exists under `submission/` or `docs/downloads/`. The A-only reasoning CSV has a header and zero data rows. No slot is selected or spent.
- Reviewed README, `docs/index.html`, the new `docs/h97.html`, `docs/irregularities.html`, the H97 result document, the H97 preregistration, the machine-readable irregularities, and the run card for the correct negative verdict, full score class, evaluator, withheld-positive count, 95% CIs, H33 caveat, official links, and explicit no-download/no-submit status. The feed-owned `docs/data/submission.json` was not rewritten to imply an H97 artifact or selection when none exists.
- Code-review corrections: no-artifact write receipts omit `note_chars`; `submission_card_fields()` now normalizes blocked/successful receipts. The not-union comparison is kept separate from single-view identity. The zero-row A-only CSV is emitted with LF line endings; regression tests cover all three behaviors.
- Final automated checks: `python scripts/check_site.py` passed (124 pages, 437 data files; no dead links or receipt errors). `git diff --check` and `git diff --cached --check` passed after intent-to-add. The H97/H95 focused checks passed **15/15**. The final full `pytest -q`, run after the CSV LF-writer/test change, final run-card generation, and all substantive README/site/result-document edits, passed **534 tests**, with **7 skipped** and **56 PendingDeprecationWarnings**, in **121.65 s**. The test result itself was then copied into this review log and the machine-readable check record. Earlier transient validation findings are recorded in `evidence/h97_review_passes.json`; none remain. The separate PR/merge outcome will be reported after GitHub confirms it.

**Pass-3 disposition:** preserve the strict final-dot stop; no TIFF, no download, no submit, no slot, and no organizer score. The active branch remains `arena/d1a45c4e-gemsdoe52`.

## Review record paths

- Machine-readable gate receipts: `evidence/h97_run_card.json`, `evidence/h97_holdout.json`, `evidence/h97_fit.json`, `evidence/h97_build.json`, `evidence/h97_lane_surface.json`, `evidence/h97_lane_dots.json`, `evidence/h97_write.json`.
- Frozen protocol/source record: `knowledge/97_hypotheses_H97_preregistered.md` and `registry/h97_preregistration.json`.
- Result summary: `knowledge/98_h97_results_and_limits.md` and `docs/h97.html`.
