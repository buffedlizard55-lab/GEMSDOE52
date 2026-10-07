> **Historical report — superseded where contradicted by R2.** See `09_r2_review.md` and `evidence/reference_forensics_r2.json`. In particular: known pixels do not pay penalties; H33 removed off-catalogue flanks; the old OOF independence report contained no negative predictions; hidden prevalence and a 0.464 ceiling are not established.

# 03 · Negative results, and what each one killed

Written so the next run does not repeat them. Every number below is reproducible from
`evidence/*.json` in this repo; nothing here is inferred from memory or from a sibling site.

Ordering is by how much compute each dead end cost us.

---

## N-1 · Co-training with pseudo-labels is refuted on both instruments (the largest one)

**The idea** (the brief's mechanism, and the one the group had never tried): train View A on the
geophysical bands and View B on the surface bands; wherever one view is confident and the other
abstains, harvest that disagreement as a pseudo-label, retrain, and emit the second-round model.
Blum & Mitchell's COLT'98 result (doi:10.1145/279943.279962) says this *can* work when each view is
individually sufficient and their errors are conditionally independent given the label.

**What happened.** Pre-registered gates, evaluated on the arm `cotrain|25000`, on both instruments:

| gate | tip (truncation) | hide (whole-component) |
|---|---|---|
| beats naive union at equal budget | −0.01582 → **FAIL** | −0.03027 → **FAIL** |
| beats the better single view | +0.00097 → pass | +0.00183 → pass |
| placement, not mass (vs identical-mass scramble) | −0.01667 → **FAIL** | −0.03183 → **FAIL** |
| fold support (≥3/4 folds beating random) | 0/4 → **FAIL** | 0/4 → **FAIL** |
| promoted | **false** | **false** |

Absolute DTI for the arm: `cotrain|37654` = 0.0084 (tip) / 0.0078 (hide) — the *worst* of every arm
we measured, including the random control at 0.0253 / 0.0396.

**The reading — and a retraction that matters more than the failure.** *This section used to assert that the
independence premise survived, quoting r = 0.4298 (tip, n = 11 blocks) and r = −0.1406 (hide). Those numbers
came from a pre-fix run of the diagnostic; `evidence/independence_*.json` was rewritten afterwards and no
longer contains them. Quoting them further would have been exactly the failure the register exists to catch.
What the files on disk say, re-read at 22:33 UTC:*

| reading | tip | hide |
|---|---|---|
| block-level false-alarm Pearson | **undefined** — both views' per-block false-alarm rate is constant (all zeros), so fewer than 3 usable blocks; Spearman degenerates to 1.0 on the ties | **undefined** — same |
| block-level miss-rate Pearson | −0.2235 (Spearman −0.1636) | **+0.8307** (Spearman 0.7727) |
| held-pixel logit Pearson | +0.1748 over 19,183 held px (negatives-only slice undefined) | +0.1316 over 36,375 held px |
| held strata | 0.62 % concordant, 2.42 % A-only, 9.13 % B-only | 0.12 % concordant, 1.19 % A-only, 10.74 % B-only |

The honest statement is narrower than the one we wrote. The pre-registered **abandonment test could not fire
at this grid size** — it is a block-level correlation, and the block-level false-alarm variance is
degenerate. Of the two readings that *are* available, they disagree with each other: the pixel-level logit is
weakly coupled (+0.17 tip, +0.13 hide, far below the 0.60 threshold), while the block-level *miss-rate*
correlation on `hide` is +0.83 — the views miss the same neighbourhoods, which is what a shared
interpolation grid and a shared geology would do. **Conditional independence is therefore neither established
nor refuted here: it is unmeasured at the granularity the pre-registration specified, and where a block-level
quantity can be measured it looks worse than the theorem would like.** The mechanism's own result is
unambiguous regardless: mean AUC Δ −0.0159 with 1/4 fold support, and the arm is worst-of-all on both
instruments (0.0084 tip / 0.0078 hide vs 0.0253 / 0.0396 for matched random), so the pseudo-label round is
dropped on its own measurement, not on the premise's. What the strata still show is physical and unaffected:
A-only pixels sit at median band-15 rank 455.0 against 296.7 for B-only and 251.2 for concordant
(`evidence/strata.json`) — deeper cover, exactly where a surface view must abstain.

**Rule we adopted:** the disagreement signal is used as a *stratification of the emission budget*, never
as a label source, in this competition and at this prevalence (~0.2 % of pixels).

**And the rule the retraction taught:** any number quoted in prose is re-read, in the same session, from the
file that publishes it — evidence JSONs are overwritten by every re-run of the script that makes them, and
prose is not.

---

## N-2 · A whole-footprint rank field's top-K is not a fault detector

Before the fold machinery existed we scored the top 40 k pixels of the blended rank field over the whole
footprint in hide mode and got essentially the random control. Cause: the top of a rank field is the
*regional anomaly* — a basement-high, a drainage-basin-scale gravity low — not a linear structure. Any
"take the most extreme values" rule spends its budget on 10 km blobs. This is the same failure mode that
killed GEMSDOE47's off-catalogue SGMC arm.

**Rule adopted:** ranking must always be applied *inside a permitted set* (footprint minus catalogue,
and for corridor mass, inside the corridor), and any arm whose field is unimodal-scaled must be checked
against `random` at the same budget in the same mask.

---

## N-3 · Hide mode is structurally blind to near-trace mass; tip mode is blind to isolated faults

`union_cor|37654` scores 0.0320 on tip and **0.0001** on hide. That is not a weakness of the arm, it is
arithmetic: the hide folds hold out whole components, so only 0.5 % of held-out truth lies within 5 px of
a *visible* trace, and a corridor arm is by construction looking next to visible traces. Conversely tip
folds truncate known traces, so an arm that finds an isolated, never-mapped fault gets no credit there.

Two consequences we now treat as design rules:

1. **Never select on one instrument.** Every arm is reported on both, and the shipped selection rule is a
   two-regime composite (corridor mass scored by the tip-winning ranking, far-field mass by the
   hide-winning ranking), *not* the minimum of the two.
2. **Max-min alone is a trap.** The best arm by max-min is `B_only|25000` (0.0296 / 0.0497) and it
   throws away the entire near-trace population, where the truth is densest (88.5 % of tip-fold truth
   lies within 5 px of a visible trace). Selecting by max-min would have discarded the corridor — the one
   regime the organiser's own statement says is *in scope* ("new-fault truth can lie within 300 m of a
   known trace, and those corrections are a competition goal", chrisk-dd, Sep 21).
3. Tip-mode prevalence is data-determined (4–8 k px per fold), so only *ranking* transfers between folds;
   absolute tip DTI must never be read as a score forecast.

---

## N-4 · The pre-registered blend weights were asserted, and backwards

`registry/preregistration.json` opened with w = (0.55 r_A + 0.20 r_B + 0.25 min) because co-training
theory says the two views are comparable in quality. On this data the surface view dominates: `B_only`
is the **only** arm that beats its random control on both instruments (0.0291 tip / 0.0518 hide at
37,654 px; +31 % over random on hide but winning only 2/4 folds, and +15 % on tip), while A-only is below
random on hide. Any re-weighting therefore has to be recorded as an *amendment* to the pre-registration
with the fitted numbers in it — never applied silently. The `wt_A20B80` family is exactly that amendment,
declared in the arm table rather than hidden in a config.

---

## N-5 · NaN outside the footprint is unwritable *and* unsubmittable

`grid.write_geotiff` refuses non-finite pixels, and the portal's own validator enforces `0 <= v <= 1`,
which NaN fails regardless of the comparison direction. That is the mechanism behind the historical
"Predicted values must be in range [0, 1]" rejection this lab hit before: it was never a scaling problem,
it was the no-data encoding. The page's "null or NaN where there is no data" sentence and the validator
contradict each other; scoring is identical either way (p = 0 contributes nothing to FPw), so the safe
encoding is 0.0 and `gates.format_report` now calls NaN a problem by name.

---

## N-6 · Inherited dead ends, re-listed so they stay dead

All of these were measured, in this family, and are not to be retried without new information:

| tried | result | why it fails |
|---|---|---|
| fit a truth model to published leaderboard scores | RMSE 0.1449 against scores of 0.25–0.38 | unusable; the board is too coarse and too few |
| supervised detectors trained to reproduce the catalogue | 0.1223, then 0.0286 | the metric rewards *new* faults only; a catalogue copy is max-penalised |
| external fault catalogues as positive priors | QFaults → 1 px in footprint, INGENIOUS → 0 px | nothing mapped there yet; as a *negative* filter they are still interesting |
| 1 m LiDAR acquisition | download volume exceeds this sandbox | licence is fine (public domain), bandwidth is not |
| potential-field transforms at 300 m cell size | magnetic transforms AUC ≈ 0.52; cross-strike magnetic braid 0.4987; strain-ratio Laplacian 0.4765; basement-depth signed step 0.5113; Laplacian of fine strain ≈ 0.5; drainage-azimuth asymmetry 0.4796 | the provided grids are already processed to the point where a second derivative amplifies nothing but noise |

---

## N-7 · Process failures worth recording (they cost hours, not model quality)

* `pkill -f <pattern>` inside a tool call kills the tool call itself whenever the pattern also matches
  the invoking shell's command line. It bit us twice (once silently dropping the command queued after it).
  Use the process tools, or `pgrep` then `kill <pid>`, and never put the target's name in the same compound
  command.
* A 12-arm × 6-budget × 4-fold × 2-mode sweep (`scripts/budget_sweep.py`) does not fit in a 2 CPU / 3 GB
  box: ~40 min of wall time for a table whose informative rows are readable in ~7 min from a named arm
  list. The script is left in the repo, correct but unrun; `scripts/composite_split.py` replaces it with
  an explicit `--far/--cor/--splits` grid.
* Bash heredoc patch scripts inside compound commands are unsafe (one unbalanced bracket swallows the
  rest of the command and writes nothing). Prefer editing files with a real edit tool and then verifying
  with `grep -n` + `ast.parse`. Both silent patch failures in this session were caught by that habit.
* This sandbox has no network egress except the agent's own page-fetching tool (`curl` to
  drivendata.org → `SSL_ERROR_SYSCALL`, `urllib` → TLS EOF). Anything that must be *live* belongs in the
  GitHub-hosted workflow, which is why `.github/workflows/feed.yml` exists instead of a cron in here.

---

## N-8 · Declaring something unrecoverable before fetching the remote

We wrote, in `knowledge/00` and on the site, that the brief's verbatim wording could not be recovered: the
checkout had one commit and no brief file. That was true of the *working tree* and false of the
*repository* — `origin/main` had two further merged PRs, and `git show origin/main:README.md` §8 contains the
prompt verbatim. Recovered at 22:35 UTC, and it corrected a real claim on the way in (the radiometric clause
is conditional in the original, absolute in our reconstruction).

**Rule:** before writing "not available anywhere", `git fetch && git ls-tree -r origin/main --name-only`, and
`grep` the merged branches. In a family of repos where siblings merge into the same `main`, the branch you
were cut from is not the repository.

---

## N-9 · A GitHub Actions workflow that has never run is not "done" (found 22:26 UTC)

`.github/workflows/feed.yml` — the thing the whole "you never have to check the site by hand" promise
rests on — failed twice in 0 seconds with **no log and no job**, because an inline `python - <<'PY'` block
inside a `run: |` scalar had lost its indentation when that block was edited. A block scalar ends at the
first non-indented line, so the file stopped being valid YAML, and Actions rejects it before any step
runs. Nothing in the repo noticed: `pytest` did not parse it, `check_site.py` did not read it, and the
site itself was fine, so the *absence* of the problem looked like its presence.

Fixed by re-indenting the step, and then by making the repo unable to forget: `tests/test_workflows.py`
now (a) `yaml.safe_load`s every workflow file, (b) asserts the feed workflow contains the refresh, commit
and "fail loudly" steps, (c) asserts the commit step touches only `docs/data/` — publishing a raster stays
a human act — and (d) asserts the fetcher stays stdlib-only so a package index cannot freeze the board.

Two things this exposed that are worth keeping as rules, not as fixes:

* **The runner has no scientific stack, so any verification that needs one must decline rather than
  degrade.** The generated `docs/downloads/index.html` re-runs the format gate on every staged raster,
  which needs `rasterio`; on a runner without it the page used to be rewritten with "gate not run" for
  every file — a safety table silently emptied. It now leaves the committed version alone and logs that it
  skipped (see `download_index`).
* **A lint that misfires is worse than no lint.** The first version of that test re-derived YAML's
  block-scalar indentation rule with a regex and failed on valid YAML; deleted. `yaml.safe_load` is the
  authority, and the test says so in a comment so nobody re-adds the clever version.
