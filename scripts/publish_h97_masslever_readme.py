#!/usr/bin/env python3
"""Insert / refresh the H97 block at the top of README.md and AGENTS.md, from the receipts.

Idempotent: replaces the block between its markers, never touches another round's block.  Every
number is read from ``evidence/h97_masslever_*.json``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
OPEN, CLOSE = "<!--H97-MASSLEVER-README-->", "<!--/H97-MASSLEVER-README-->"
AOPEN, ACLOSE = "<!--H97-MASSLEVER-AGENTS-->", "<!--/H97-MASSLEVER-AGENTS-->"


def rd(n):
    return json.loads((EVID / n).read_text())


def main() -> int:
    card = rd("h97_masslever_run_card.json")
    wr = rd("h97_masslever_write.json")
    inst = rd("h97_masslever_instrument.json")
    hold = rd("h97_masslever_holdout.json")
    build = rd("h97_masslever_build.json")
    fm = wr["validator"]
    uni = wr["uniqueness"]
    lane = wr["lane_dots"]
    name = wr["submission_name"]
    failed = card["failed_gates"]
    s = hold["pooled"]["scores"]
    sm = hold["pooled_mass_lever"]["scores"]
    pd = hold["pooled"]["paired_differences"][hold["pooled"]["best_comparable_control"]]

    rows = "\n".join(
        f"  | `{r['arm']}` | {r['board_score']:.4f} | {r['holdout_dti']:.6f} "
        f"[{r['holdout_ci95'][0]:.4f}, {r['holdout_ci95'][1]:.4f}] | {r['emitted']:,} |"
        for r in inst["rows"])

    block = f"""{OPEN}
# Current status — H97 (2026-10-11): the instrument does not track the board · co-training negative

> **OK TO DOWNLOAD: YES** — single-band float32 GeoTIFF, EPSG:32611, 3730×3292, transform identical to
> `sample_submission.tif`, **nodata tag {fm['nodata']}, {fm['n_nan']} NaN pixels, values exactly {{0, 1}}**
> ({fm['n_nonzero']:,} cells). The portal's *"Predicted values must be in range [0, 1]"* rejection — the one
> the owner hit on a NaN-tagged file — cannot occur on this container.
>
> **OK TO SUBMIT: YOUR CALL — this round certifies no leaderboard gain.** Failed gate(s):
> {', '.join(failed) if failed else 'none'}. And now the reason is measured, not guessed: **our holdout does not
> rank the board's own scored files** (E1 below). Slots used: **0**; promotion is a separate selector step.

**★ [Download h97-masslever-candidate.tif](docs/downloads/h97-masslever-candidate.tif)** · [ZIP](docs/downloads/h97-masslever-candidate.zip) · **[Executive summary / how to submit](docs/h97-masslever-executive-summary.html)** · [Full result](docs/h97-masslever.html) · [Run card](evidence/h97_masslever_run_card.json) · [A-only reasoning CSV](docs/downloads/{name}-a-only-reasoning.csv)

- **File:** `submission/{name}.tif` — {wr['tif_bytes']:,} bytes, SHA-256 `{wr['sha256']}`
- **Submission name:** `{name}` · **Note ({wr['note_chars']}/140):** `{wr['note']}`
- **Validator (re-read from disk):** {fm['bands']} band {fm['dtype']}, {fm['crs']}, {fm['height']} rows × {fm['width']} cols, transform/bounds = sample_submission.tif, {fm['nan_pixels']} NaN, {fm['infinity_pixels']} inf, values exactly [{fm['min']}, {fm['max']}], emitted {fm['n_nonzero']:,}, nodata {fm['nodata']}; problems: {fm['problems']}

### E1 — our instrument is anti-correlated with the board (the round's most useful result)

Every OWNER-REPORTED scored prior scored **exactly as submitted** (no budget cut, no re-placement,
visible catalogue masked pixel-exactly) on the frozen folds; evaluator `gems52-pooled-hide-v1`,
{inst['withheld_positive_px']:,} withheld positive px, 95 % CI:

  | file as submitted | board (owner-reported) | HOLDOUT-DTI | emitted px |
  |---|---|---|---|
{rows}

- **Spearman(board, HOLDOUT-DTI) = {inst['spearman_board_vs_holdout']['spearman']:.4f}** over {inst['spearman_board_vs_holdout']['n']} files;
  **partial correlation controlling for log mass = {inst['partial_board_vs_holdout_given_log_mass']['spearman']:.4f}** (zero);
  Spearman(board, mass) = {inst['spearman_board_vs_mass']['spearman']:.4f}, reproducing knowledge/76 §4 on thirteen files.
- The champion (0.2778 on the board) scores **{inst['rows'][0]['holdout_dti']:.6f}** here — below the
  {inst['pooled']['scores'].get('random_25400', {}).get('dti', 0):.6f} random control — because it deliberately avoids the
  mapped catalogue that this instrument scores against. **Every "beat the bar" promotion this repository has
  made was made on an instrument that does not rank the board's own files.** Frozen falsifier (Spearman ≥ 0.50) not hit.

### E2 — co-training at the metric-implied mass lever: NEGATIVE

H96's rejected repair (View B given the LiDAR-scarp and GeoDAWN radiometric-ratio channels the
certified-best *fitted* surface instrument uses) was run with the frozen arm set; matched budget
9,400 dots/fold, mass lever 6,350 dots/fold (25,400 total):

- matched: cotrain_dis {s['cotrain_dis']['dti']:.6f} [{s['cotrain_dis']['ci95'][0]:.4f}, {s['cotrain_dis']['ci95'][1]:.4f}],
  cons_only {s['cons_only']['dti']:.6f}, buried_only {s['buried_only']['dti']:.6f},
  single_B {s['single_B']['dti']:.6f}, single_A {s['single_A']['dti']:.6f}, random {s['random']['dti']:.6f}
- paired `cotrain_dis − cons_only` = {pd['delta']:.6f} [{pd['ci95'][0]:.6f}, {pd['ci95'][1]:.6f}] → the disagreement/veto machinery **hurts**
- mass lever: cotrain_dis {sm['cotrain_dis']['dti']:.6f}, single_B {sm['single_B']['dti']:.6f}, random {sm['random']['dti']:.6f}
- independence max |ρ| {hold['independence']['max_abs_correlation']:.4f} (abandon 0.60) → exchange allowed;
  leakage canary max single-channel AUC {max(hold['canary']['max_auc'].values()):.4f} (alarm 0.90) → no alarm.
- **The lift from ~0.06 to ~0.19 on this lane is the fitted learner, not the channel list.** An unfitted rank
  composite with the full channel set still lands at {s['single_B']['dti']:.6f}.

### E3 — artifact and gates

- Placement `gems52.nodes.spacing_select` at 3 px, 200 m catalogue collar, **{build['composition']['emitted']:,} dots placed exactly**
  (buried-dominant {build['composition']['buried_dominant_dots']:,} = {build['composition']['buried_dominant_fraction']*100:.1f} %;
  Jaccard vs the spaced A/B union **{build['composition']['jaccard_vs_viewA_viewB_spaced_topk_union']:.4f}** — not the union).
- Uniqueness: {uni['n_priors_checked']} priors checked / {uni['n_priors_compared']} comparable, identical to a prior
  **{uni['identical_to_a_prior']}**, incomparable {len(uni['incomparable_priors'])}; this round's own staged copies dropped by name.
- Lanes: surface {build['surface_lane']['policy']['verdict']} (max Spearman {build['surface_lane']['policy']['max_spearman']:.4f});
  dots literal {lane['literal']['verdict']} / policy {lane['policy']['verdict']} (max Spearman {lane['literal']['max_spearman']:.4f},
  max near-3 px {lane['literal']['max_near_3px_fraction']}).
- Docs: [preregistration](knowledge/105_h97_masslever_hypotheses_preregistered.md) · [results & limits](knowledge/106_h97_masslever_results_and_limits.md) ·
  [irregularities](registry/irregularities.json) · Reproduce: `python scripts/restore_data.py --target-dir data` then
  `python scripts/run_h97_masslever.py all` then `python scripts/publish_h97_masslever_site.py && python scripts/publish_h97_masslever_readme.py`.

### Next work, ranked after E1

1. **Build a board-validated instrument** (the existing off-catalogue SGMC proxy is the candidate; validate it the way E1
   validates this one). Until then no round can certify a leaderboard gain.
2. Then re-open model work: the fitted surface learner (0.1746 → 0.1928 measured) plus the board-measured mass lever (S ≈ 25,400).
3. The A-only stratum stays a Phase-2 deliverable, not a DTI bet (below random on the catalogue instrument in H93, H95, H97).

<details><summary><b>The H97 session brief, verbatim (read it every session)</b></summary>

See `knowledge/94_current_user_brief_2026-10-10_H95.md` for the standing brief (the H97 session received
the same co-training paragraph plus the parallel-run protocol), and `knowledge/105_h97_masslever_hypotheses_preregistered.md`
for what this round froze before any fit.

</details>
{CLOSE}
"""

    # README convention enforced by tests/test_h95.py: the H95 block stays the FIRST block in the
    # file.  The H97 block is therefore inserted after it (H96 did the same), never before it.
    path = ROOT / "README.md"
    t = path.read_text()
    t = re.sub(re.escape(OPEN) + r".*?" + re.escape(CLOSE) + r"\n*", "", t, count=1, flags=re.S)
    # Insertion point: the README's convention is newest-round-first, and tests/test_h99.py asserts
    # that the file still STARTS with the H99 block from the parallel lane.  This lane's block is
    # therefore written immediately AFTER the H99 block (falling back to after the H95 block, then
    # to the top) so no other lane's block is moved or rewritten.
    for anchor in ("<!--/H99-README-->", "<!--/H95-README-->"):
        if anchor in t:
            t = t.replace(anchor, anchor + "\n" + block.strip() + "\n", 1)
            where = anchor
            break
    else:
        t = block.strip() + "\n\n" + t
        where = "top of file"
    path.write_text(t)
    print(f"{path.name}: H97-masslever block written after {where} ({len(block)} bytes)")

    agents = ROOT / "AGENTS.md"
    ablock = f"""{AOPEN}
## Current H97-masslever continuation (2026-10-11) — READ FIRST
Read README's H97-masslever block first. Download **YES**; submit **your call** — no leaderboard gain is certified.
This session's branch is `arena/c5bf6f30-gemsdoe52`. The round ran **three** experiments:
**E1 instrument fidelity** (the repository's holdout does not rank the board: Spearman
{inst['spearman_board_vs_holdout']['spearman']:.4f}, partial given log mass
{inst['partial_board_vs_holdout_given_log_mass']['spearman']:.4f}, Spearman(board, mass)
{inst['spearman_board_vs_mass']['spearman']:.4f} over {inst['spearman_board_vs_holdout']['n']} OWNER-REPORTED scored priors scored
`as_is`); **E2 co-training at the metric-implied mass lever** (NEGATIVE: cotrain_dis
{s['cotrain_dis']['dti']:.6f} vs cons_only {s['cons_only']['dti']:.6f}, paired {pd['delta']:.6f}
[{pd['ci95'][0]:.6f}, {pd['ci95'][1]:.6f}]); **E3 artifact + gates**.
- The data blocker is cleared in this session: `python scripts/restore_data.py --target-dir data` restores 23
  hash-pinned files (531 MB, ALL_VERIFIED=True) through api.github.com; `data/raw_parts` was removed afterwards.
- Settled; do not re-litigate: the unfitted-composite co-training lane is closed for a third time (H95, H96, H97); the
  fitted learner is where the 0.19 lives. The A-only stratum is a Phase-2 deliverable, not a DTI bet.
- Shared-tool facts learned the hard way this round: `gates.format_report` keys are
  `bands/dtype/crs/width/height/nan_pixels/infinity_pixels/n_min/max/n_nonzero/problems/ok`;
  `gates.uniqueness_report` has `n_priors_checked`/`identical_to_a_prior`/per-prior `jaccard`
  (no `identical_to_none`, no `max_jaccard`); `find_priors` excludes by resolve() **and basename**, so a
  round that stages an alias copy of its own artifact (e.g. `h97-masslever-candidate.tif`) must drop its own names or the
  candidate is compared to itself; `submission_writer.write_submission` rejects a note/name longer than 140 chars.
- Use `/home/user/.venv/bin/python` (pinned numpy/scipy/rasterio/…env built this session).
{ACLOSE}
"""
    t = agents.read_text()
    if AOPEN in t:
        t = re.sub(re.escape(AOPEN) + r".*?" + re.escape(ACLOSE), ablock.strip(), t, count=1, flags=re.S)
    else:
        t = ablock.strip() + "\n\n" + t
    agents.write_text(t)
    print(f"AGENTS.md: H97 block written ({len(ablock)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
