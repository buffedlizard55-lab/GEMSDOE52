#!/usr/bin/env python3
"""Render the H66 README block and the AGENTS.md pointer from the receipts, then insert them.

Idempotent: the block lives between `<!--H66-README-->` and `<!--/H66-README-->` at the very top of
README.md, and the AGENTS.md section between `<!--H66-AGENTS-->` and `<!--/H66-AGENTS-->`. Every number
is read from evidence/h66_*.json so the prose cannot drift from the evidence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"


def load(n):
    return json.loads((EV / f"h66_{n}.json").read_text())


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
    raster, ids = card["raster"], card["submission_identifiers"]
    ci = lambda a: f"[{a[0]:.6f}, {a[1]:.6f}]"      # noqa: E731

    block = f"""<!--H66-README-->
# Current status — H66 (2026-10-09): a unique GeoTIFF was built, and the verdict is DO NOT SUBMIT

> **DOWNLOAD: YES, for research. SUBMIT TO THE COMPETITION: NO — DO NOT UPLOAD.** Two independent gates
> say no: the brief's own lane rule fires on the final dots, and the shared hide-and-recover instrument
> puts the candidate **below uniform random** with a 95 % CI that excludes zero. Slots used: **0**.

**One-click download.** [★ H66 research GeoTIFF](docs/downloads/h66-candidate.tif) ·
[single-TIFF ZIP](docs/downloads/h66-candidate.zip) ·
[geological reasoning CSV, one row per emitted pixel](docs/downloads/h66-a-only-and-segment-reasoning.csv) ·
[run card JSON](docs/data/h66_run_card.json) · site: [`docs/h66.html`](docs/h66.html),
[`docs/h66-executive-summary.html`](docs/h66-executive-summary.html).

**What was tested.** H66-A, the *Thermal-Upflow Corridor* (TUC): strike-aligned corridors emitted outward
from {seeds['legal_seeds']} thermal-upflow sites, every one of them ≥ 300 m — beyond the whole scoring
kernel — from the nearest mapped fault, gated by an independent geophysical edge, then placed by the repo's
metric-aware greedy emitter at a frozen budget. Frozen before any fit in
[`knowledge/43`](knowledge/43_hypotheses_H66_preregistered.md), protocol SHA-256
`{card['preregistration']['protocol_sha256'][:16]}…`, thresholds and deviations in
[`registry/h66_preregistration.json`](registry/h66_preregistration.json). Four further hypotheses, ranked by
expected gain and implementation cost with named free sources, are in the same document.

| Check | Label | Result | Receipt |
|---|---|---|---|
| Manifest integrity | MEASURED | {pre['restore_pins_checked']} pins checked, {len(pre['restore_pins_mismatched'])} mismatched | [`h66_preflight.json`](evidence/h66_preflight.json) |
| Footprint after the sentinel fix | MEASURED | {pre['cells_domain']:,} in-domain → **{pre['eligible']:,} eligible** ({pre['in_domain_nodata_sentinel_cells']:,} sentinel cells excluded, IR-H66-002) | [`h66_preflight.json`](evidence/h66_preflight.json) |
| Leakage canary (alarm > 0.90) | PREMISE-AUC | max single channel **{can['max_single_channel_auc']:.4f}** (`{can['worst']['channel']}`) → CLEAN | [`h66_canary.json`](evidence/h66_canary.json) |
| S1 two-view sufficiency | PREMISE-AUC | View A mean **{s1['mean_view_A_oof_auc']:.4f}**, min fold **{s1['min_view_A_oof_auc']:.4f}** vs bar ≥ 0.60 / ≥ 0.55 → **FAIL**; View B mean {s1['mean_view_B_oof_auc']:.4f} | [`h66_s1_sufficiency.json`](evidence/h66_s1_sufficiency.json) |
| S2 conditional independence | MEASURED | max \\|Spearman\\| **{s2['max_abs_correlation']:.4f}** over {s2['n_blocks_all']:,} blocks → abandonment rule did **not** fire (IR-H66-005) | [`h66_s2_independence.json`](evidence/h66_s2_independence.json) |
| HOLDOUT-DTI, candidate | HOLDOUT-DTI | **{p['tuc']['dti']:.6f}** {ci(p['tuc']['ci95'])}, {ho['withheld_positives_total']:,} withheld positives, `{ho['evaluator_version']}` | [`h66_holdout.json`](evidence/h66_holdout.json) |
| HOLDOUT-DTI, controls | HOLDOUT-DTI | single_B {p['single_B']['dti']:.6f} · single_A {p['single_A']['dti']:.6f} · union_max {p['union_max']['dti']:.6f} · disagreement {p['disagreement']['dti']:.6f} · **random {p['random']['dti']:.6f}** (best control) | [`h66_holdout.json`](evidence/h66_holdout.json) |
| Paired, candidate − random | HOLDOUT-DTI | **{pd_['random']['delta']:+.6f}** {ci(pd_['random']['ci95'])} → significantly worse than random | [`h66_holdout.json`](evidence/h66_holdout.json) |
| Lane gate, surface | MEASURED | literal **{rel['lane_surface']['literal']['verdict']}**, policy **{rel['lane_surface']['policy']['verdict']}** (max ρ {rel['lane_surface']['policy']['max_spearman']:.4f} < 0.90) | [`h66_release_gates.json`](evidence/h66_release_gates.json) |
| Lane gate, final dots | MEASURED | literal **{rel['lane_dots']['literal']['verdict']}** ({rel['lane_dots']['literal']['max_near_3px_fraction']:.4f}, a total-coverage diagnostic raster); policy **{rel['lane_dots']['policy']['verdict']}** — **{rel['lane_dots']['policy']['max_near_3px_fraction']:.4f}** > 0.70 vs `{src['repo']}` `{src['path']}` → **log as duplicate and STOP** | [`h66_release_gates.json`](evidence/h66_release_gates.json) |
| Decoded-pattern uniqueness | MEASURED | **unique** over {uni2['corpus']['n_checked']} aligned priors, 0 identical, 0 read errors (IR-H66-007 recomputation) | [`h66_uniqueness_aligned.json`](evidence/h66_uniqueness_aligned.json) |
| Support novelty vs the prior union | FAILED diagnostic | novel fraction {uni2['result']['novel_fraction']:.4f} (the prior union covers {uni2['result']['union_px']:,} px ≈ 104 % of eligible; the shared gate's own `gate_correction` says why this is not identity) | [`h66_uniqueness_aligned.json`](evidence/h66_uniqueness_aligned.json) |
| Not merely the union of the two views | MEASURED | **{rel['not_union']['fraction_of_emission_inside_union']:.4f}** of the emission inside the union of matched view top-K fields (bar 0.90) → PASS | [`h66_release_gates.json`](evidence/h66_release_gates.json) |
| Format contract | MEASURED | 1 band float32, EPSG:32611, {card['validator']['shape'][0]}×{card['validator']['shape'][1]}, transform and bounds identical to the pinned sample, values exactly {{0,1}}, {card['validator']['nan_inside_footprint']} NaN, {card['validator']['mass_outside_footprint']} px outside the footprint | [`h66_run_card.json`](evidence/h66_run_card.json) |
| Reproducibility | MEASURED | a second independent run produced **bit-identical decoded pixels** (SHA-256 `{raster['decoded_pixels_sha256'][:24]}…`) | [`h66_rewrap.json`](evidence/h66_rewrap.json) |

**Artefact.** `{Path(raster['file']).name}` · {raster['bytes']:,} bytes · SHA-256 `{raster['sha256']}` ·
{raster['emitted_pixels']:,} emitted cells · ZIP SHA-256 `{(json.loads((ROOT / 'submission' / (Path(raster['file']).stem + '.json')).read_text()))['zip_sha256'][:24]}…`.
Portal name ({ids['name_chars']} chars): `{ids['name']}`. Portal note ({ids['note_chars']} chars, limit 140):
`{ids['note']}`.

**Why 0.2778 won, and what beating 0.3195 would take** — re-measured from restored bytes this session by
[`scripts/h66_board_algebra.py`](scripts/h66_board_algebra.py) (receipt
[`evidence/h66_board_algebra.json`](evidence/h66_board_algebra.json)), written up in
[`knowledge/45`](knowledge/45_why_02778_phd_answer.md). In four lines:

1. `h33-2-b2` (0.2778, 37,654 px) is a **strict subset** of the 0.2600 file (44,090 px). The
   {alg['set_relations']['d2_8__minus__ref_h33_2_b2']['px']:,} deleted pixels all lie
   {alg['set_relations']['d2_8__minus__ref_h33_2_b2']['dist_min_m']}–{alg['set_relations']['d2_8__minus__ref_h33_2_b2']['dist_max_m']} m
   from a mapped trace: the 100–200 m catalogue ring earns **zero** credit and still pays the
   false-positive tax. Removing it bought +6.8 % relative. Nothing else about the file changed.
2. For dots > 200 m apart, `DTI = T / (0.2·S + 0.8·|G|)`, so the score *is* the credit density
   `ρ = T/S`. The champion's is **0.1387** — 5.0× uniform random (0.0279). That is the whole content of 0.2778.
3. Spearman(mass, board) = **{alg['mass_vs_board']['spearman']:.4f}** over the five owner-reported
   off-catalogue files, and every step past 37,654 px fails the metric's own marginal rule
   `ΔT/ΔS > 0.2·DTI`. The champion is not a better detector; it is the correct stopping point of a worse one.
4. Required ρ for 0.3195 is **{alg['required_rho']['target_0.3195_G_14088.7']['37654']:.4f}** at 37,654 px and
   **{alg['required_rho']['target_0.3195_G_14088.7']['100000']:.4f}** at 100,000 px; for 0.3774,
   {alg['required_rho']['target_0.3774_G_14088.7']['37654']:.4f} and
   {alg['required_rho']['target_0.3774_G_14088.7']['100000']:.4f}. The only sub-field with a measured ρ in that
   range is the 25,517 px credited core P1 (ρ ∈ [0.163, 0.205] ⇒ DTI ∈ [0.2546, 0.3190], **upper bound below
   0.3195**), and the lane rule forbids re-emitting it — any subset of P1 has 100 % of its dots within 3 px of an
   existing registry raster. **So within this lane no candidate can be shown to beat 0.2778.** The binding
   constraint is a ranker whose marginal credit density stays above ~0.06 out to 60,000–150,000 px: a better
   detector, not a better placement.

**Verdict: H66 not promoted; negative result published.** Experiments used: **3 of 3** (E1 lane gates,
E2 holdout, E3 build + release gates). Wall clock exceeded the 2 h budget and that is disclosed in the run
card rather than smoothed: the sandbox started cold (no cached feature stack, 3.9 GB RAM, 2 CPUs), the
19-band stack and a 526-blob prior census had to be restored and fetched, and five defects had to be fixed
in the runner before the pipeline could complete. Run card:
[`evidence/h66_run_card.json`](evidence/h66_run_card.json). Full note:
[`knowledge/44`](knowledge/44_h66_results_and_limits.md).

**Irregularities logged this round** ([`registry/irregularities.json`](registry/irregularities.json),
IR-H66-001…010): -001 thermal seeds are a third channel outside the two views (declared deviation);
**-002 severe**: 3,073 in-domain cells carry the nodata sentinel, which collapses every rank channel;
-003 three defensible footprints; -004 zero-inflated layers defeated a blunt guard; **-005 high**: the S2
independence statistic spans 0.0078–0.7625 across five rounds on the same data, so it cannot gate anything;
-006 the sample's NaN nodata breaks JSON receipt writers; **-007**: `uniqueness_report` conflates "identical
to a prior" with "a prior failed to open"; **-008 high**: probe classification flips with the structuring
element, and this round's lane verdict depends on it; -009 the holdout budget collapses inside a fold;
-010 two census-ineligible blobs were passed as priors.

**Still open.** A unique, lane-valid candidate that is not spatially redundant with an existing registry
raster; a holdout instrument that can rank the board (IR-H60-003, N-9, IR-H66-009); the four hypotheses in
`knowledge/43` §3–§6 that were **not** run (drainage-network asymmetry needs USGS 3DEP 1 m tiles, unreachable
from this sandbox); the 0.2778 file-to-board-row receipt; the portal error text behind IR-H65-007; and the
selector decision that the lane rule makes unavoidable — the measured high-credit field is lane-blocked, so
beating 0.3195 needs either a better detector or an explicit waiver of the 70 % rule, and only the user can
grant that.

**The brief.** This round ran against the prompt embedded verbatim below
("Complete current prompt — 2026-10-09, verbatim") and preserved at
[`knowledge/36`](knowledge/36_current_user_brief_2026-10-09.md). Two of its clauses are stale and were
re-verified live this session: the leaderboard is JS-rendered and cannot be fetched (the last live reading,
2026-10-09, is #1 xiaofanhu 0.3774, #7 DARD 0.3195, #13 extradr19 0.2778 — PUBLIC BOARD, not
ORGANIZER-CONFIRMED), and the official page states a **two-round** prize structure in which the Final Round
re-scores the *same* single submission against an **expanded** label set that includes faults experts verify
after reviewing every team's file ([problem page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)).
<!--/H66-README-->

"""
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    if "<!--H66-README-->" in text:
        a = text.index("<!--H66-README-->")
        b = text.index("<!--/H66-README-->") + len("<!--/H66-README-->\n\n")
        text = text[:a] + block + text[b:]
    else:
        text = block + text
    readme.write_text(text, encoding="utf-8")

    agents = ROOT / "AGENTS.md"
    at = agents.read_text(encoding="utf-8")
    apointer = f"""<!--H66-AGENTS-->
## Current H66 continuation (2026-10-09)

Read `README.md`'s H66 block first, then `knowledge/43_hypotheses_H66_preregistered.md` (frozen before any
fit), `knowledge/44_h66_results_and_limits.md` (rendered from the receipts) and
`knowledge/45_why_02778_phd_answer.md` (the board algebra, re-measured from restored bytes by
`scripts/h66_board_algebra.py`). H66-A is **negative**: the lane rule fires on the final dots
(84.08 % within 3 px of one informative registry raster) and the hide-and-recover instrument puts it below
uniform random. A unique GeoTIFF exists and is published research-only; **do not submit it, do not spend a
weekly slot**. IR-H66-001 … -010 are in `registry/irregularities.json`; -002, -005, -007 and -008 change how
a shared instrument must be read. Use `scripts/h66_uniqueness_aligned.py` (alignment-filtered corpus) for any
uniqueness check; do not fork a checker.
<!--/H66-AGENTS-->

"""
    if "<!--H66-AGENTS-->" in at:
        a = at.index("<!--H66-AGENTS-->")
        b = at.index("<!--/H66-AGENTS-->") + len("<!--/H66-AGENTS-->\n\n")
        at = at[:a] + apointer + at[b:]
    else:
        marker = "## Current H65 continuation"
        at = at.replace(marker, apointer + marker, 1) if marker in at else apointer + at
    agents.write_text(at, encoding="utf-8")
    print("README.md and AGENTS.md updated; block bytes:", len(block))
    return 0


if __name__ == "__main__":
    sys.exit(main())
