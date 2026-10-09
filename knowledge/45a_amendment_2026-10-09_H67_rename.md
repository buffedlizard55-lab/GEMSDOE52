# 45a · Amendment: this round is **H67** in filenames; the frozen protocol body keeps its **H66** label

Dated 2026-10-09, written after the round's measurements and before its merge. This amendment does **not**
edit the frozen protocol; it records a rename and exactly what did and did not change.

## 1 · Why

Two sessions ran from the same prompt on the same day and both labelled their round **H66**. The other
session's H66 (*"local-scale View A co-training"*, pre-registration SHA-256 `e2118738…`) merged to `main`
first, in PR #56, and it occupies:

`knowledge/43_hypotheses_H66_preregistered.md`, `knowledge/43_h66_summary.md`,
`knowledge/44_h66_results_and_limits.md`, `evidence/h66_{canary,holdout,run_card,independence,
lane_surface,lane_dots,pseudo_exchange,fit_checkpoint,format_validator,stage_summary,
submission_receipt,uniqueness_audit,diagnostic_hgb_local}.json`, `registry/h66_preregistration.json`,
`scripts/{run_h66,publish_h66_site,generate_h66_submission}.py`, `tests/test_h66.py`,
`docs/h66-audit.html`, `docs/h66-executive-summary.html`, `docs/h66cotrain*.html`,
`docs/downloads/h66-candidate.*`, `docs/data/h66_run_card.json`, and irregularity IDs
**IR-H66-001 … IR-H66-010**.

This repository already settled the same collision twice before — H62 → H64 (`scripts/rewrap_h64.py`,
`knowledge/39*`) and H65 → H65halo (`knowledge/41b`, `42b`) — and the rule both times was: **the round
that merged first keeps the label; the later round is renamed in filenames only, and its frozen protocol
text is not touched.** The same rule is applied here.

## 2 · What changed

**This round is H67** (Thermal-Upflow Corridor, TUC). Renamed: `knowledge/45` (protocol),
`knowledge/48` (results), `knowledge/49` (board algebra), `knowledge/50` (brief staleness),
`knowledge/51` (next session), `registry/h67_preregistration.json`, `evidence/h67_*.json` (14 receipts),
`scripts/{run_h67,publish_h67_site,h67_board_algebra,h67_reasoning,h67_run_card,
h67_uniqueness_aligned,h67_readme_block,rewrap_h67}.py`, `tests/test_h67.py`,
`submission/gems52-h67-thermal-upflow-corridor-24907px-20261009T050704Z.{tif,zip,json}`,
`submission/gems52-h67-a-only-and-segment-reasoning.csv`, `submission/H67_LATEST.txt`,
`docs/h67.html`, `docs/h67-executive-summary.html`, `docs/downloads/h67-candidate.{tif,zip}`,
`docs/downloads/h67-a-only-and-segment-reasoning.csv`, `docs/data/h67_run_card.json`,
and irregularity IDs **IR-H67-001 … IR-H67-011**.

## 3 · What did NOT change — and these are the things that matter

* **The frozen protocol is byte-identical.** `knowledge/45_hypotheses_H67_preregistered.md` still begins
  *"# 43 · H66 pre-registration — frozen before any fit"* and still says H66-A throughout its body. Its
  SHA-256 is unchanged and still equals the value registered before any fit:
  `9fa87ab6ca46369304044357a0c00227b888a305fc7f585faef842e65c7712bd`. `registry/h67_preregistration.json`
  points at the new path and carries the same hash, so `scripts/run_h67.py`'s startup check still passes
  and `tests/test_h67.py::test_protocol_hash_is_frozen_and_still_matches` still pins it.
* **No measurement was repeated, altered or re-labelled.** Every number in `evidence/h67_*.json` is the
  number the H66-labelled run produced; the rename is a textual substitution in receipts plus a `git mv`.
  Nothing was re-fitted and no threshold moved.
* **The decoded pixels are unchanged.** SHA-256 of the decoded raster is
  `969bb11b7403d9c7506ad609084bcdfe6690993cd6dac459cf8de19a913d6d11`, the fixed point measured from two
  independent runs. The container file was re-written under its new name by `scripts/rewrap_h67.py`, which
  asserts pixel identity, so the container SHA-256 is recorded before and after in
  `evidence/h67_rewrap.json`.
* **The fetched prior census stays at `work/h66/priors/`** (526 blobs, > 227 MB, gitignored). Renaming a
  gitignored cache directory would have forced a re-fetch of half a gigabyte for no evidential gain, so
  every receipt that quotes those paths quotes them as `work/h66/priors/…`. That is deliberate and it is
  the only place where an H66 string survives in this round's artefacts.
* **IR-H67-001 … 011 are this round's findings and are unrelated to main's IR-H66-001 … 010.** They were
  renumbered wholesale rather than interleaved, so no ID carries two meanings. Where this round's prose
  previously cross-referenced an IR-H66 number, it now references the IR-H67 number with the same suffix.

## 4 · The one substantive collision that a rename cannot fix

Both rounds independently measured that the **hide-and-recover instrument cannot rank the board**, and
both rounds independently found a **lane DUPLICATE/STOP on the final dots** against a dense registry
raster. Two sessions, two different hypotheses, same two conclusions. That is evidence about the
instruments, not about either hypothesis, and it is why `knowledge/51` §4 puts instrument repair ahead of
any new hypothesis for the next session.
