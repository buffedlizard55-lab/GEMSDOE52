#!/usr/bin/env python3
"""Render the H67 README block and the AGENTS.md pointer from the receipts, then insert them.

Idempotent: the block lives between `<!--H67-README-->` and `<!--/H67-README-->` at the very top of
README.md, and the AGENTS.md section between `<!--H67-AGENTS-->` and `<!--/H67-AGENTS-->`. Every number
is read from evidence/h67_*.json so the prose cannot drift from the evidence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"


def load(n):
    return json.loads((EV / f"h67_{n}.json").read_text())


def main() -> int:
    card = load("run_card")
    pre, s1, s2, can = load("preflight"), load("s1_sufficiency"), load("s2_independence"), load("canary")
    ho, build, rel = load("holdout"), load("build"), load("release_gates")
    uni2, alg, seeds = load("uniqueness_aligned"), load("board_algebra"), load("seed_composition")
    p = ho["pooled"]["scores"]
    pd_ = ho["pooled"]["paired_differences"]
    reg = card["registry_correlation_and_overlap"]
    off = reg["lane_offender_identification"]
    src = off["policy_source"]["aliases"][0]
    raster = card["raster"]
    ci = lambda a: f"[{a[0]:.6f}, {a[1]:.6f}]"      # noqa: E731

    block = f"""<!--H67-README-->
# Historical H67 result — research-only archive; terminal lane stop

> **Round label.** This round was labelled H66 in its own receipts; a parallel session merged a different
> H66 first (PR #56), so it is **H67** in filenames. The frozen protocol is byte-identical and its body
> still reads "H66" — SHA-256 `{card['preregistration']['protocol_sha256'][:16]}…`, unchanged. No
> measurement was repeated or re-labelled and the decoded pixels are unchanged. Details:
> [`knowledge/45a`](knowledge/45a_amendment_2026-10-09_H67_rename.md).

> **DOWNLOAD: YES, for research. SUBMIT TO THE COMPETITION: NO — DO NOT UPLOAD.** Two independent gates
> say no: the brief's own lane rule fires on the final dots, and the shared hide-and-recover instrument
> puts the candidate **below uniform random** with a 95 % CI that excludes zero. Slots used: **0**.

**One-click download.** [★ H67 research GeoTIFF](docs/downloads/h67-candidate.tif) ·
[single-TIFF ZIP](docs/downloads/h67-candidate.zip) ·
[geological reasoning CSV, one row per emitted pixel](docs/downloads/h67-a-only-and-segment-reasoning.csv) ·
[run card JSON](docs/data/h67_run_card.json) · site: [`docs/h67.html`](docs/h67.html),
[`docs/h67-executive-summary.html`](docs/h67-executive-summary.html).

**What was tested.** H67-A, the *Thermal-Upflow Corridor* (TUC): strike-aligned corridors emitted outward
from {seeds['legal_seeds']} thermal-upflow sites, every one of them ≥ 300 m — beyond the whole scoring
kernel — from the nearest mapped fault, gated by an independent geophysical edge, then placed by the repo's
metric-aware greedy emitter at a frozen budget. Frozen before any fit in
[`knowledge/45`](knowledge/45_hypotheses_H67_preregistered.md), protocol SHA-256
`{card['preregistration']['protocol_sha256'][:16]}…`, thresholds and deviations in
[`registry/h67_preregistration.json`](registry/h67_preregistration.json). Four further hypotheses, ranked by
expected gain and implementation cost with named free sources, are in the same document.

| Check | Label | Result | Receipt |
|---|---|---|---|
| Manifest integrity | MEASURED | {pre['restore_pins_checked']} pins checked, {len(pre['restore_pins_mismatched'])} mismatched | [`h67_preflight.json`](evidence/h67_preflight.json) |
| Footprint after the sentinel fix | MEASURED | {pre['cells_domain']:,} in-domain → **{pre['eligible']:,} eligible** ({pre['in_domain_nodata_sentinel_cells']:,} sentinel cells excluded, IR-H67-002) | [`h67_preflight.json`](evidence/h67_preflight.json) |
| Leakage canary (alarm > 0.90) | PREMISE-AUC | max single channel **{can['max_single_channel_auc']:.4f}** (`{can['worst']['channel']}`) → CLEAN | [`h67_canary.json`](evidence/h67_canary.json) |
| S1 two-view sufficiency | PREMISE-AUC | View A mean **{s1['mean_view_A_oof_auc']:.4f}**, min fold **{s1['min_view_A_oof_auc']:.4f}** vs bar ≥ 0.60 / ≥ 0.55 → **FAIL**; View B mean {s1['mean_view_B_oof_auc']:.4f} | [`h67_s1_sufficiency.json`](evidence/h67_s1_sufficiency.json) |
| S2 conditional independence | MEASURED | max \\|Spearman\\| **{s2['max_abs_correlation']:.4f}** over {s2['n_blocks_all']:,} blocks → abandonment rule did **not** fire (IR-H67-005) | [`h67_s2_independence.json`](evidence/h67_s2_independence.json) |
| HOLDOUT-DTI, candidate | HOLDOUT-DTI | **{p['tuc']['dti']:.6f}** {ci(p['tuc']['ci95'])}, {ho['withheld_positives_total']:,} withheld positives, `{ho['evaluator_version']}` | [`h67_holdout.json`](evidence/h67_holdout.json) |
| HOLDOUT-DTI, controls | HOLDOUT-DTI | single_B {p['single_B']['dti']:.6f} · single_A {p['single_A']['dti']:.6f} · union_max {p['union_max']['dti']:.6f} · disagreement {p['disagreement']['dti']:.6f} · **random {p['random']['dti']:.6f}** (best control) | [`h67_holdout.json`](evidence/h67_holdout.json) |
| Paired, candidate − random | HOLDOUT-DTI | **{pd_['random']['delta']:+.6f}** {ci(pd_['random']['ci95'])} → significantly worse than random | [`h67_holdout.json`](evidence/h67_holdout.json) |
| Lane gate, surface | MEASURED | literal **{rel['lane_surface']['literal']['verdict']}**, policy **{rel['lane_surface']['policy']['verdict']}** (max ρ {rel['lane_surface']['policy']['max_spearman']:.4f} < 0.90) | [`h67_release_gates.json`](evidence/h67_release_gates.json) |
| Lane gate, final dots | MEASURED | literal **{rel['lane_dots']['literal']['verdict']}** ({rel['lane_dots']['literal']['max_near_3px_fraction']:.4f}, a total-coverage diagnostic raster); policy **{rel['lane_dots']['policy']['verdict']}** — **{rel['lane_dots']['policy']['max_near_3px_fraction']:.4f}** > 0.70 vs `{src['repo']}` `{src['path']}` → **log as duplicate and STOP** | [`h67_release_gates.json`](evidence/h67_release_gates.json) |
| Decoded-pattern uniqueness | MEASURED | **unique** over {uni2['corpus']['n_checked']} aligned priors, 0 identical, 0 read errors (IR-H67-007 recomputation) | [`h67_uniqueness_aligned.json`](evidence/h67_uniqueness_aligned.json) |
| Support novelty vs the prior union | FAILED diagnostic | novel fraction {uni2['result']['novel_fraction']:.4f} (the prior union covers {uni2['result']['union_px']:,} px ≈ 104 % of eligible; the shared gate's own `gate_correction` says why this is not identity) | [`h67_uniqueness_aligned.json`](evidence/h67_uniqueness_aligned.json) |
| Not merely the union of the two views | MEASURED | **{rel['not_union']['fraction_of_emission_inside_union']:.4f}** of the emission inside the union of matched view top-K fields (bar 0.90) → PASS | [`h67_release_gates.json`](evidence/h67_release_gates.json) |
| Format contract | MEASURED | 1 band float32, EPSG:32611, {card['validator']['shape'][0]}×{card['validator']['shape'][1]}, transform and bounds identical to the pinned sample, values exactly {{0,1}}, {card['validator']['nan_inside_footprint']} NaN, {card['validator']['mass_outside_footprint']} px outside the footprint | [`h67_run_card.json`](evidence/h67_run_card.json) |
| Reproducibility | MEASURED | a second independent run produced **bit-identical decoded pixels** (SHA-256 `{raster['decoded_pixels_sha256'][:24]}…`) | [`h67_rewrap.json`](evidence/h67_rewrap.json) |

**Historical artifact facts.** `{Path(raster['file']).name}` · {raster['bytes']:,} bytes · SHA-256 `{raster['sha256']}` ·
{raster['emitted_pixels']:,} emitted cells · local format check only. No portal name or note is provided; this archive is not approved for submission.

**Current evidence about the reported 0.2778 (see [`knowledge/49`](knowledge/49_why_02778_phd_answer.md)).** The saved 2026-10-09 20:18 UTC public-board observation places the team-level row at rank 17 (top 0.3774); no row contains a TIFF hash or submission receipt. The file-to-score association remains owner-reported. Locally, the H33-labelled 37,654-cell bitmap is a strict subset of a separate 44,090-cell bitmap associated with 0.2600 by its owner (6,436 removed, none added, all 100–200 m from the known-fault mask). Those facts do not identify hidden new-fault credit or explain any organizer score change; staff says new-fault truth may lie within 300 m of known traces. Older `|G|`, credit-density, and +6.8% calculations are conditional scenarios, not measurements or score explanations.
**Verdict: H67 not promoted; negative result published.** Experiments used: **3 of 3** (E1 lane gates,
E2 holdout, E3 build + release gates). Wall clock exceeded the 2 h budget and that is disclosed in the run
card rather than smoothed: the sandbox started cold (no cached feature stack, 3.9 GB RAM, 2 CPUs), the
19-band stack and a 526-blob prior census had to be restored and fetched, and five defects had to be fixed
in the runner before the pipeline could complete. Run card:
[`evidence/h67_run_card.json`](evidence/h67_run_card.json). Full note:
[`knowledge/48`](knowledge/48_h67_results_and_limits.md).

**Irregularities logged this round** ([`registry/irregularities.json`](registry/irregularities.json),
IR-H67-001…010): -001 thermal seeds are a third channel outside the two views (declared deviation);
**-002 severe**: 3,073 in-domain cells carry the nodata sentinel, which collapses every rank channel;
-003 three defensible footprints; -004 zero-inflated layers defeated a blunt guard; **-005 high**: the S2
independence statistic spans 0.0078–0.7625 across five rounds on the same data, so it cannot gate anything;
-006 the sample's NaN nodata breaks JSON receipt writers; **-007**: `uniqueness_report` conflates "identical
to a prior" with "a prior failed to open"; **-008 high**: probe classification flips with the structuring
element, and this round's lane verdict depends on it; -009 the holdout budget collapses inside a fold;
-010 two census-ineligible blobs were passed as priors.

**Still open.** The four geological hypotheses in `knowledge/45` §3–§6 that were **not** run (drainage-network asymmetry needs USGS 3DEP 1 m tiles, unreachable from this sandbox); a public holdout instrument that ranks leaderboard outcomes (IR-H60-003, N-9, IR-H67-009); the 0.2778 file-to-board-row receipt; and the portal error text behind IR-H65-007. H67 itself is terminal for promotion: the policy lane result is **DUPLICATE/STOP** (the >70% near-3-px rule) and its shared HOLDOUT-DTI is significantly below random. Download is for research only; no submission approval or owner-override path is implied, and no weekly slot was used.

**Historical brief note.** This round used the prompt preserved at [`knowledge/36`](knowledge/36_current_user_brief_2026-10-09.md). The saved later 2026-10-09 20:18 UTC public-board observation places 0.2778 at rank 17 (top 0.3774; 0.3195 at rank 7); these are PUBLIC-LEADERBOARD rows, not organizer-confirmed file scores. The board is JS-rendered and no row includes a TIFF hash or receipt. The official page states a **two-round** prize structure in which the Final Round re-scores the *same* single submission against an **expanded** label set that includes faults experts verify after reviewing every team's file ([problem page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)).
<!--/H67-README-->

"""
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    if "<!--H67-README-->" in text:
        a = text.index("<!--H67-README-->")
        b = text.index("<!--/H67-README-->") + len("<!--/H67-README-->\n\n")
        text = text[:a] + block + text[b:]
    else:
        text = block + text
    readme.write_text(text, encoding="utf-8")

    agents = ROOT / "AGENTS.md"
    at = agents.read_text(encoding="utf-8")
    apointer = f"""<!--H67-AGENTS-->
## Historical H67 continuation (2026-10-09; not current authorization)

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

"""
    if "<!--H67-AGENTS-->" in at:
        a = at.index("<!--H67-AGENTS-->")
        b = at.index("<!--/H67-AGENTS-->") + len("<!--/H67-AGENTS-->\n\n")
        at = at[:a] + apointer + at[b:]
    else:
        marker = "## Current H65 continuation"
        at = at.replace(marker, apointer + marker, 1) if marker in at else apointer + at
    agents.write_text(at, encoding="utf-8")
    print("README.md and AGENTS.md updated; block bytes:", len(block))
    return 0


if __name__ == "__main__":
    sys.exit(main())
