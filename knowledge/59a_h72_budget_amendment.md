# H72 amendment A — freeze the final raster budget before fitting

Registered 2026-10-09, before any H72 model fit or holdout placement.

The H72-A matched holdout budget remains **1,264 dots per fold per arm**. The final research TIFF target is now fixed at **5,056 dots total** (four folds × the same per-fold budget), placed once with the shared `nodes.spacing_select` over the strict A-only stratum, minimum separation **3 px**, and the registered full-grid, off-catalogue metric-aware domain. `nodes.spacing_select` may return fewer than the target only if the fixed stratum is exhausted; such an underfilled output is reported as a failed fill and cannot be selector-eligible. No post-fit budget adjustment, alternative placement, or second TIFF is permitted.

Reason: bind the final file's support to the already frozen matched-holdout budget, rather than choosing a support after observing a score. This is a budget definition, not a leaderboard projection or score.
