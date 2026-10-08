# CTD5 three-pass implementation review

## Pass 1 — implement and measure

- Read the current task and the H55–H59/R4 history before proposing hypotheses; stored four ranked hypotheses and a hash-frozen protocol before the first fit.
- Restored all 23 pinned mirror inputs, quarantined the smaller tracked placeholders, ran the download/preparation commands and rebuilt the shared cache once. The CPU run completed without a GPU or user input.
- Implemented the named shared evaluator/writer adapters, exact pooled DTI bookkeeping and spatial CI, every-feature canaries, whole-component buffered models, one conditional pseudo-label exchange, and strict full-footprint registry gates.
- Generated the new TIFF from OOF inference; no prior prediction input, retained core or A/B union. The final lane proximity gate failed; scientific experimentation stopped at 18:31 UTC. No retuning or slot spending followed.
- Focused numerical/shared-tool checks: **50 passed**. Result and all failed gates recorded, not overridden.

## Pass 2 — bugs, assumptions and edge cases

- Shared band 6 was in the wrong view for the provisional mirror identity. It is now B-only, with an explicit identity caveat; memory-mapped columns and optional-profile skipping make CPU cache reuse feasible.
- Added canary, exact Spearman/binary-rank, all-prior iteration, misaligned-prior rejection, whole-segment buffer, empty/non-finite input, note-length, single-TIFF ZIP and paired-bootstrap tests.
- Found and fixed the download wrapper's comma-separated `--only` handling, swallowed legacy band mapping keys 7–9, incorrect Affine/GDAL wording, and the feed's hard-coded H54 note fallback.
- Removed unsupported globally optimal spacing / centroid-domination claims from shared placement documentation. Current guides no longer guarantee portal acceptance or assert NaNs caused the user's historical error. Old material remains an explicitly labelled archive.
- Disclosed the candidate's fold-1 capacity shortfall; the nominal-budget comparison cannot be promoted as a matched-budget win. Added a separate registry-saturation audit: the spacing-five prior covers every eligible pixel within three pixels.
- Full pre-publication regression run: **239 passed**. A newly added floating-point assertion initially demanded bit-exact equality for 0.99999994 versus 1; changed that test to an appropriate float32 tolerance, without changing the field or any emitted dot.

## Pass 3 — original-request recheck and release verification

- Preserved the complete current prompt in README and a dedicated brief. Archived the former README instead of discarding historical results. Updated the old prompt-preservation test to assert both the current brief and the old archive, and retained the explicit “No H55-1 TIFF was built” guard.
- Built a receipt-driven landing page, executive submission guide, method/negative-result page, all-site source table, actual-data preview, local-only feed and optional research reproduction workflow. Download OK and Submit NO are separate and visible at the top.
- The first site check exposed missing H55/H57/H58 archival links after replacing the landing page. Restored them in a collapsed research-only history section; did not delete or weaken their integrity checks.
- Independent release checker reopens the TIFF, compares all copies/ZIP members and compact footprint masks, verifies note length, minimum spacing, catalogue exclusion, every emitted CSV row and the closed gate. It also fetches the real local HTTP download and verifies its SHA-256 and MIME type.
- Final local suite before concurrent-main integration: **246 passed**, 42 upstream rasterio/Affine deprecation warnings. Static site checker passed. HTTP TIFF/ZIP/card downloads were byte-identical to the audited files.
- No more geological experiments are authorized by this review. Source/registry reconciliation and software checks are verification, not new fits or alternate placements.

## Concurrent-main integration and remote checks

Main advanced via PR #34 (`647ac2f`) while CTD5 was running. Integration preserved H60's code, TIFF, ZIP and raw build receipt, archived its README/landing/guide, and retained its upstream **unapproved** marker without selecting CTD5 for a slot. H60's public JSON NaN correlations became null (not zero); the raw receipt remains unchanged. A per-artifact closed-gate receipt prevents the feed from inventing approval or falling back to an unrelated round. Historical H57 integrity checks now read the H57 receipt even when a later round owns the pointer.

A supplemental comparison against the already-fixed CTD5 surface and final dots found H60 Spearman 0.014561 / 0.004101 and directed proximity 0.271917. There was no refit, new hypothesis or new placement. The original lattice duplicate STOP remains. Closure scope: **542 files / 361 decoded patterns**. See `evidence/ctd5_parallel_reconciliation.json` and IR-CTD5-011.

Final post-integration local validation: **249 tests passed**, 42 deprecation warnings, no failures; static site and independent CTD5 checks passed. All **53** stored owner/official-reference source commit IDs were separately resolved through the GitHub commit API. The H60 supplemental array was verified distinct from the 360 original decoded priors.

Remote CI/PR status is reported from the actual GitHub check and merge receipts, not predicted in this document. The optional full reproduction workflow was added but **not** launched for another scientific run after the stop.

## Remaining limitations

CTD5 is a **negative** deliverable. It does not meet the requested strict unique-lane submission condition, and no matched-budget improvement is established. Organizer-authenticated inputs, score receipts, current weekly allowance, band identity and geological field validation remain unresolved. The default feature footprint and OOF model seams limit generalization. Prior source summaries from non-GitHub hosts remain dated; they are not fresh official verification. See `knowledge/27_ctd5_results_and_limits.md` and the single `evidence/ctd5_run_card.json` for the scientific verdict.

## Final scope correction — no post-stop rerun

A final inspection found that the inherited v1 split extends evaluation/placement masks along withheld fault tails. This exposes label-informed geometry even though no training component overlaps truth. The affected geometry is recorded in `ctd5_validation_scope_correction.json`: 2,381 extra eligible pixels and 217 withheld positives across the four folds. No effect size or corrected DTI is claimed.

The shared `spatial.folds` now has label-blind fixed quadrants, hides every intersecting original component in full, and buffers the full hidden extent. A synthetic regression proves that moving hidden traces cannot change the evaluation region. The old helper is explicitly reproduction-only for the rejected CTD5 receipt. The TIFF and its hash did not change; no model was fitted or new placement made. `strict_holdout_valid=false` is explicit in the run card and on the current pages.

Post-correction validation: **264 tests passed**, no failures; site checker and unchanged-TIFF release checker passed. Second concurrent H60 result preserved and audited separately, bringing closure scope to 543 files / 362 decoded patterns. Corrected v2 full-data scientific evaluation was deliberately NOT run after STOP.
