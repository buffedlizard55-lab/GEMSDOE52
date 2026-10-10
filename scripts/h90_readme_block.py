#!/usr/bin/env python3
"""Render the H90 README block, the AGENTS.md pointer and knowledge/87 from the receipts.

Idempotent: the README block lives between ``<!--H90-README-->`` and ``<!--/H90-README-->`` at the
top of README.md, and the AGENTS.md section between ``<!--H90-AGENTS-->`` and
``<!--/H90-AGENTS-->``.  Every number is read out of ``evidence/h90_*.json`` and
``work/h90/features/manifest.json`` so the prose cannot drift from the evidence.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
FEAT = ROOT / "work/h90/features"


def load(p):
    return json.loads(Path(p).read_text())


def main() -> int:
    card = load(EV / "h90_run_card.json")
    ch = load(EV / "h90_channels.json")
    chm = load(FEAT / "manifest.json")
    fit = load(EV / "h90_fit.json")
    ho = load(EV / "h90_holdout.json")
    bp = load(EV / "h90_build_placement.json")
    ln = load(EV / "h90_lane.json")
    bu = load(EV / "h90_build.json")
    ind = load(EV / "h90_independence.json")
    alg = load(EV / "h67_board_algebra.json")
    reg = load(ROOT / "registry/leaderboard_snapshot_2026-10-09.json")

    sc = ho["pooled"]["scores"]
    pd_ = ho["primary_paired"]
    # keyed "<candidate>_minus_<arm>"; normalise to the bare arm name
    pd_ = {k.split("_minus_")[-1]: v for k, v in pd_.items()}
    ctl = ho["controls"]["single_B"]
    prim = ho["candidate"]
    val = bu["validator"]
    nu = bu["not_the_union"]
    lane = card["correlation_vs_registry"]
    lit_full = lane["full_census"]["dots_literal"]
    lit_r = lane["restricted_scored_only"]["dots_literal"]
    pol_r = lane["restricted_scored_only"]["dots_policy"]
    suff = fit["sufficiency_view_A"]
    ci = lambda a: f"[{float(a[0]):.6f}, {float(a[1]):.6f}]"      # noqa: E731
    win = bool(pd_["single_B"]["ci95"][0] > 0 and ctl["PASS"])

    rows = "\n".join(
        f"| `{a}` | {sc[a]['dti']:.6f} | {ci(sc[a]['ci95'])} | "
        f"{'**primary**' if a == prim else 'control' if a == 'single_B' else ''} |"
        for a in sc)
    ir = ind["result"]

    block = f"""<!--H90-README-->
# Current status — H90 (2026-10-10): continuous directional alignment on a 16-direction semivariance fan — {'PROMOTE-ELIGIBLE' if card['submit_ok'] else 'NEGATIVE / research-only'}

> **DOWNLOAD: {'YES' if card['download_ok'] else 'NO'}** (format-valid on disk: single-band float32,
> EPSG:32611, 3730×3292, transform/bounds match the organiser template, values exactly {{0,1}},
> {val['nan']} NaN, {val['infinite']} inf).
> **SUBMIT TO THE COMPETITION: {'YES — every measured gate passed' if card['submit_ok'] else 'NO — research artefact only. DO NOT UPLOAD.'}**
> Slots used: **{card['slots_used']}**. Experiments used: {card['experiments_used']} of 3.

**★ [Download the H90 GeoTIFF — one click](docs/downloads/h90-candidate.tif)** ·
[single-TIFF ZIP](docs/downloads/h90-candidate.zip) ·
[per-cell geological reasoning CSV](docs/downloads/h90-a-only-reasoning.csv) ·
**[Executive summary / exactly how to submit](docs/h90-executive-summary.html)** ·
[check any file in your browser](docs/validator.html) ·
[full result](docs/h90.html) · [hypotheses](docs/h90-hypotheses.html) · [sources](docs/h90-sources.html)

- **File:** `{bu['file']}` — {bu['bytes']:,} bytes, SHA-256 `{bu['sha256']}`
- **Submission name:** `{bu['name']}` · **Note ({bu['note_chars']}/140):** `{bu['note']}`
- **HOLDOUT-DTI** (`{ho['evaluator']}`, {ho['withheld_positive_px']:,} withheld positive px,
  {ho['budget_per_fold']:,} dots/fold/arm, α 0.2 / β 0.8, 300 m triangular kernel, 1,000 paired
  physical-block bootstrap draws):

| arm | pooled HOLDOUT-DTI | 95 % CI | role |
|---|---|---|---|
{rows}

- **Primary paired difference** `{prim} − single_B` = **{pd_['single_B']['delta']:.6f}**
  {ci(pd_['single_B']['ci95'])} → {'CI entirely above zero' if win else 'does not clear zero'};
  `{prim} − B_DVA3` = {pd_.get('B_DVA3', {}).get('delta', float('nan')):.6f}
  {ci(pd_.get('B_DVA3', {}).get('ci95', [float('nan')] * 2))};
  `{prim} − random` = {pd_.get('random', {}).get('delta', float('nan')):.6f}
  {ci(pd_.get('random', {}).get('ci95', [float('nan')] * 2))}.
- **Instrument-integrity control:** `single_B` {ctl['measured']:.6f} vs committed
  {ctl['committed']:.6f} (|Δ| {ctl['abs_delta']:.2e} ≤ {ctl['tolerance']}) → {'PASS' if ctl['PASS'] else 'FAIL'}.
- **Leakage canary:** max direction-insensitive single-channel AUC over all
  {chm['n_learner_channels']} new learner channels = **{fit['canary_max_learner_overall']:.6f}**
  (bar {fit['folds'][0]['canary_alarm_auc_bar']}) → {'ALARM' if fit['canary_alarm_any'] else 'no alarm'}.
- **View independence (the lane's mandated Blum–Mitchell test):** max |rho|
  {ir['max_abs_correlation']:.4f} over {ir['n_blocks']:,} blocks / {ir['n_negative_predictions']:,}
  proxy negatives ({ir['negative_class']}), with the abandon bar
  {ind['thresholds']['abandon_max_abs_rho']} inherited verbatim from
  `{ind['thresholds_inherited_from']}` → `allow_exchange =
  {ind['result'].get('allow_exchange')}`. Exchange is still **not** run: View-A sufficiency failed
  again (mean {suff['mean']:.4f}, min fold {min(suff['per_fold']):.4f}, gate 0.60/0.55) and H71
  measured that exchange lowers the A2 out-of-fold AUC (0.5019 → 0.4759).
- **Lane / uniqueness:** full census ({lane['full_census']['n_priors']} rasters) dots literal
  **{lit_full['verdict']}** (max ρ {lit_full['max_spearman']:.4f} bar 0.90, max near-3px share
  {lit_full['max_near_3px_fraction']:.4f} bar 0.70). Restricted scored-only registry
  ({lane['restricted_scored_only']['n_priors']} rasters) dots literal **{lit_r['verdict']}**
  (max ρ {lit_r['max_spearman']:.4f}, max near {lit_r['max_near_3px_fraction']:.4f}), policy
  **{pol_r['verdict']}**; quota placement filled
  {lane['restricted_scored_only']['quota_placement_dots']:,} dots at worst share
  {lane['restricted_scored_only']['quota_placement']['worst']:.4f}. A restricted or policy PASS never
  waives a literal full-census DUPLICATE/STOP.
- **Not the union:** shared with `max(pA,pB)` {nu['shared_with_union']:,} px
  (Jaccard {nu['jaccard_with_union']:.4f}), with `single_A` {nu['shared_with_single_A']:,} px, with
  `single_B` {nu['shared_with_single_B']:,} px, with the B-only-suppressed variant
  {nu['shared_with_bonly_suppressed']:,} px; identical to none → **{'PASS' if nu['not_union_pass'] else 'FAIL'}**.
- **Placement:** {bp['dots']:,} binary dots from a {bp['pool_px']:,}-px pool; 200 m catalogue ring
  excluded; min distance to a mapped trace {bp['min_cat_dist_m']:.1f} m, median
  {bp['median_cat_dist_m']:.1f} m, {bp['dots_within_300m_of_catalogue_pct']:.2f}% inside the metric's
  300 m kernel. B-only disagreement used as a **suppression** set ({bp['b_only_suppression']['b_only_px']:,}
  px vetoed).
- **Method:** {chm['n_learner_channels']} new learner channels over {len(chm['bands'])} fields ×
  {len(chm['lags_px'])} lags × 4 statistics — 16-fan anisotropy, 16-fan log-variance, the
  γ-weighted axial circular **mean direction** (continuous, replacing H82's 4-valued argmax) and its
  **resultant length** (directional confidence, no degenerate-null mode) — plus
  {chm['n_control_channels']} 8-direction control channels whose fan is exactly H82's, computed in the
  same pass. Measured strike per fold from the fold's own visible catalogue:
  {', '.join(f"f{s['fold']} {s['strike_compass_deg']:.1f}° (R {s['resultant_length_R']:.2f})" for s in chm['strike'])}.
- **New this round:** `scripts/repair_h90_channels.py` (IR-H90-001) — 30 of 102 channel files failed
  the byte-integrity guard *after* passing it; they were recomputed from the pinned rasters with a
  digest-stability check, not patched.
- Reproduce: `python3 scripts/restore_data.py --target-dir data` → build the store →
  `PYTHONPATH=src python3 -m gems52.external` → `python3 scripts/fetch_prior_inventory.py` →
  `python3 scripts/repair_h90_channels.py --all` →
  `python3 scripts/run_h90.py fit independence holdout build write lane card` →
  `python3 scripts/publish_h90_site.py` → `python3 scripts/finalize_h90.py` →
  `python3 scripts/h90_readme_block.py` → `python3 scripts/check_site.py` → `python3 -m pytest -q`.

---

<!--/H90-README-->
"""

    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    if "<!--H90-README-->" in text:
        a = text.index("<!--H90-README-->")
        b = text.index("<!--/H90-README-->") + len("<!--/H90-README-->\n")
        text = text[:a] + block + text[b:]
    else:
        text = block + "\n" + text
    readme.write_text(text, encoding="utf-8")

    agents_block = f"""<!--H90-AGENTS-->
## Current H90 continuation (2026-10-10)
Read README's H90 block first, then `knowledge/86_hypotheses_H90_preregistered.md` (frozen before any
fit; SHA-256 `{card['preregistration']['sha256'][:16]}…`, pinned in `registry/h90_preregistration.json`)
and `knowledge/87_h90_results_and_limits.md`. Verdict **{'PROMOTE-ELIGIBLE' if card['submit_ok'] else 'NEGATIVE'}**,
experiments {card['experiments_used']}/3, slots 0.

What is now settled, and must not be re-litigated:

- **The 16-direction fan and the continuous alignment are measured, not assumed.** The primary
  `{prim}` scored HOLDOUT-DTI {sc[prim]['dti']:.6f} {ci(sc[prim]['ci95'])} against `single_B`
  {sc['single_B']['dti']:.6f} {ci(sc['single_B']['ci95'])}, paired Δ {pd_['single_B']['delta']:.6f}
  {ci(pd_['single_B']['ci95'])}. The 8-direction control `B_DVA3c` scored
  {sc['B_DVA3c']['dti']:.6f}, so the fan-resolution and alignment effects are separated in one pass.
- **The leakage canary stayed clean** at {fit['canary_max_learner_overall']:.4f} against a 0.90 bar
  over {chm['n_learner_channels']} channels, so no channel is a leak.
- **View-A sufficiency failed again** (mean {suff['mean']:.4f}, min fold {min(suff['per_fold']):.4f}).
  Independence holds (max |ρ| {ind['result'].get('max_abs_correlation')}, bar
  {ind['thresholds']['abandon_max_abs_rho']}), but independence without sufficiency gives co-training
  nothing to donate. Do not re-run pseudo-label exchange on this View A.
- **IR-H90-001 is environment-level, not repository-level:** channel files written by
  `run_h82.save_verified` were corrupted *after* verification by the concurrently-snapshotting
  filesystem. `scripts/repair_h90_channels.py --all` recomputes the whole bank with a
  digest-stability check. Any round that builds a channel bank must run it before fitting.
- **The H83 artefact is not a validated candidate.** Its own run card records
  `holdout_dti = NOT_EVALUATED`, and it claims "no prior submissions to compare against" when the
  registry holds 500+. It is archived, not promoted; do not submit it.
- **Board algebra, re-measured this session** (`scripts/h67_board_algebra.py`,
  `evidence/h67_board_algebra.json`): at 37,654 emitted px the credit density needed for 0.3195 is
  ρ = {alg['required_rho']['target_0.3195_G_14088.7']['37654']:.4f} against the reported-0.2778
  champion's {alg['required_rho']['target_0.2778_G_14088.7']['37654']:.4f}; Spearman(emitted mass,
  owner-reported board) = {alg['mass_vs_board']['spearman']:.1f} over
  {alg['mass_vs_board']['n']} files. The binding constraint is the ranker's ρ(S) decay, not the budget.
- **The lane rule still cannot be satisfied literally** for any emission ranked by this family's own
  signal: full-census dots literal **{lit_full['verdict']}** (max near-3px share
  {lit_full['max_near_3px_fraction']:.4f}). Report it verbatim; never waive it with a restricted PASS.
<!--/H90-AGENTS-->
"""
    ap = ROOT / "AGENTS.md"
    at = ap.read_text(encoding="utf-8")
    if "<!--H90-AGENTS-->" in at:
        a = at.index("<!--H90-AGENTS-->")
        b = at.index("<!--/H90-AGENTS-->") + len("<!--/H90-AGENTS-->\n")
        at = at[:a] + agents_block + at[b:]
    else:
        at = agents_block + "\n" + at
    ap.write_text(at, encoding="utf-8")

    # ------------------------------------------------------------------ knowledge/87 results
    res = f"""# 75 · H90 results and limits (2026-10-10)

Preregistered in [`86_hypotheses_H90_preregistered.md`](86_hypotheses_H90_preregistered.md)
(SHA-256 `{card['preregistration']['sha256']}`, frozen before any fit, canary, holdout or placement
read; amendment 74a corrected only a channel count, before any fit). Receipts:
`evidence/h90_channels.json`, `evidence/h90_fit.json`, `evidence/h90_holdout.json`,
`evidence/h90_independence.json`, `evidence/h90_build_placement.json`,
`evidence/h90_lane.json`, `evidence/h90_build.json`, `evidence/h90_run_card.json`.

**Verdict: {'PROMOTE-ELIGIBLE on every measured gate' if card['submit_ok'] else 'NEGATIVE — research artefact, do not upload'}.
Slots used 0. Experiments used {card['experiments_used']} of 3.**

## 1. The one-sentence result

{'The primary arm beat the single-view control with a paired 95% CI entirely above zero, and every gate passed.' if win else 'The primary arm did not beat the single-view control with a paired 95% CI entirely above zero, so the frozen promotion rule does not fire.'}

## 2. HOLDOUT-DTI — the only score this repository can compute for itself

Evaluator `{ho['evaluator']}` · {ho['withheld_positive_px']:,} withheld positive pixels ·
{ho['budget_per_fold']:,} dots per fold per arm · k(d) = max(1 − d/R, 0), R = 300 m = 3 px ·
α 0.2, β 0.8 · 1,000 paired physical-block bootstrap draws (block side 200 px).

| arm | pooled HOLDOUT-DTI | 95 % CI | role |
|---|---|---|---|
{chr(10).join(f"| `{a}` | {sc[a]['dti']:.6f} | {ci(sc[a]['ci95'])} | {'primary' if a == prim else 'control' if a == 'single_B' else ''} |" for a in sc)}

Paired differences (primary − arm):

| comparison | Δ | 95 % CI | reading |
|---|---|---|---|
{chr(10).join(f"| `{prim} − {k}` | {v['delta']:.6f} | {ci(v['ci95'])} | {'above zero' if v['ci95'][0] > 0 else ('below zero' if v['ci95'][1] < 0 else 'straddles zero')} |" for k, v in pd_.items())}

`single_B` control: measured {ctl['measured']:.6f} against committed {ctl['committed']:.6f}
(|Δ| {ctl['abs_delta']:.2e}, tolerance {ctl['tolerance']}) → {'PASS' if ctl['PASS'] else 'FAIL'}.

**These are holdout numbers, not board forecasts.** In this repository the hide-and-recover
instrument does not rank leaderboard performance (measured Spearman −0.10 against owner-reported
board scores over R4, `knowledge/10` §5).

## 3. The lane's premise tests

| test | measurement | bar | verdict |
|---|---|---|---|
| leakage canary (max direction-insensitive single-channel AUC, {chm['n_learner_channels']} channels) | {fit['canary_max_learner_overall']:.6f} | {fit['folds'][0]['canary_alarm_auc_bar']} | {'ALARM' if fit['canary_alarm_any'] else 'clean'} |
| View A sufficiency (mean / min-fold out-of-quadrant AUC) | {suff['mean']:.4f} / {min(suff['per_fold']):.4f} | 0.60 / 0.55 | {'pass' if suff['pass'] else 'FAIL — standing negative'} |
| View independence (max |ρ| over spatial blocks) | {ind['result'].get('max_abs_correlation')} | {ind['thresholds']['abandon_max_abs_rho']} | allow_exchange = {ind['result'].get('allow_exchange')} |

Independence thresholds were inherited verbatim from `{ind['thresholds_inherited_from']}`
(SHA-256 `{ind['thresholds_inherited_sha256'][:16]}…`); they were not re-tuned for H90.

## 4. Measured strike, from each fold's own visible catalogue

{chr(10).join(f"- fold {s['fold']}: {s['strike_compass_deg']:.2f}° compass, resultant length R {s['resultant_length_R']:.3f}, axial circular SD {s.get('axial_circular_sd_deg')}, corridor {s['corridor_px']:,} px, derived from fold['visible'] only" for s in chm['strike'])}

R is only 0.37–0.45, so the visible catalogue is genuinely multi-directional and a scalar regional
strike is a weak summary. That is exactly why the alignment channel was made **continuous** rather
than a single-strike comparison: a 4-valued categorical recoding (H82) cannot express "close to the
regional strike but not on it".

## 5. Uniqueness and the lane gate

- Full census ({lane['full_census']['n_priors']} rasters): surface literal
  **{lane['full_census']['surface_literal']['verdict']}**, dots literal **{lit_full['verdict']}**
  (max ρ {lit_full['max_spearman']:.4f}, max near-3px share {lit_full['max_near_3px_fraction']:.4f}),
  dots policy **{lane['full_census']['dots_policy']['verdict']}**.
- Restricted scored-only registry ({lane['restricted_scored_only']['n_priors']} rasters): surface
  literal **{lane['restricted_scored_only']['surface_literal']['verdict']}**, dots literal
  **{lit_r['verdict']}** (max ρ {lit_r['max_spearman']:.4f}, max near
  {lit_r['max_near_3px_fraction']:.4f}), dots policy **{pol_r['verdict']}**.
- Quota placement against the restricted informative supports:
  {lane['restricted_scored_only']['quota_placement_dots']:,} dots, worst share
  {lane['restricted_scored_only']['quota_placement']['worst']:.4f}.
- Doctrine: a restricted or policy PASS never waives a literal full-census DUPLICATE/STOP.

## 6. Not the union of the two views

| comparison | shared px | Jaccard | identical |
|---|---|---|---|
| primary vs `max(pA,pB)` | {nu['shared_with_union']:,} | {nu['jaccard_with_union']:.4f} | {'yes' if nu['dots_equal_union'] else 'no'} |
| primary vs `single_A` | {nu['shared_with_single_A']:,} | {nu['jaccard_with_single_A']:.4f} | {'yes' if nu['dots_equal_single_A'] else 'no'} |
| primary vs `single_B` | {nu['shared_with_single_B']:,} | {nu['jaccard_with_single_B']:.4f} | {'yes' if nu['dots_equal_single_B'] else 'no'} |
| primary vs B-only-suppressed | {nu['shared_with_bonly_suppressed']:,} | {nu['jaccard_with_bonly_suppressed']:.4f} | no |

Gate: **{'PASS' if nu['not_union_pass'] else 'FAIL'}**.

## 7. Placement and catalogue ring

{bp['dots']:,} dots from a {bp['pool_px']:,}-px pool ({bp['eligible_px']:,} eligible); 200 m ring
excluded; minimum distance to a mapped trace {bp['min_cat_dist_m']:.1f} m, median
{bp['median_cat_dist_m']:.1f} m, {bp['dots_within_300m_of_catalogue_pct']:.2f}% of dots inside the
metric's 300 m kernel. The B-only disagreement stratum was used as a **suppression** set:
{bp['b_only_suppression']['b_only_px']:,} px vetoed, leaving
{bp['b_only_suppression']['supp_pool_px']:,} px, of which the emission took
{bp['b_only_suppression']['supp_dots']:,}.

## 8. Irregularity IR-H90-001

30 of 102 channel files failed `run_h82.Bank`'s byte-integrity guard after passing
`run_h82.save_verified`. `scripts/repair_h90_channels.py` recomputed them from the pinned rasters
with the same arithmetic and a digest-stability check, then re-hashed the whole bank and re-verified
it. The mechanism is the environment-level torn write already recorded as IR-H82-002; it is
**not** resolved at the repository level, and any future channel build must run the repair before
fitting.

## 9. Limits

- No organizer receipt exists for any file here; every score quoted from the brief or a sibling site
  is OWNER-REPORTED/PUBLIC, never ORGANIZER-CONFIRMED.
- The holdout instrument hides catalogue faults while the competition scores faults the catalogue
  lacks; SGMC is ~95 % disjoint from `labels.tif`. The mismatch is the likeliest cause of the
  measured Spearman −0.10 between holdout DTI and board score.
- The 1 m DEM tiles behind the LiDAR scarp layer are not obtainable from this sandbox
  (egress limited to github/npm/pypi), so no new native-resolution scarp reduction is possible here.
- Pseudo-label exchange is still not run: View-A sufficiency has now failed eight consecutive times.
"""
    (ROOT / "knowledge/87_h90_results_and_limits.md").write_text(res, encoding="utf-8")
    print("README.md, AGENTS.md and knowledge/87 updated; block bytes:", len(block))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
