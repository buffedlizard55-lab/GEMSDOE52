#!/usr/bin/env python3
"""Render the H66cover header block of README.md from the receipts and splice it in below the current top block.

The README is the first thing the next session reads, so its numbers must be the receipts' numbers.
Namespacing (IR-H66-015): this round is the cover-gated co-training H66; a parallel session merged a
different round under the "H66" label first (PR #56), so this round's block, files and links carry the
``h66cover`` prefix and main's blocks stay verbatim.  The block is inserted directly below the current
top block (main's H67) and never displaces it.  Running it twice is a byte-for-byte no-op.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
START, END = "<!--H66COVER-README-->", "<!--/H66COVER-README-->"


def load(n: str) -> dict:
    return json.loads((EVID / f"h66cover_{n}.json").read_text())


def f(x, nd=4):
    return "n/a" if x is None else f"{float(x):.{nd}f}"


def block() -> str:
    card = load("run_card")
    hold = load("holdout")
    exch = load("pseudo_exchange")
    can = load("canary")
    lane_d = load("lane_dots")
    lane_s = load("lane_surface")
    uniq = load("uniqueness")
    proj = card["projection"]
    sc = hold["pooled"]["scores"]
    paired = card["holdout_dti"]["paired_h66a_minus_single_B"]
    cand = sc["h66a_cover_gated_a_only"]
    sB = sc["single_B"]
    verdict = card["verdict"]
    negative = verdict.startswith("NEGATIVE")
    stem = card["raster"]["file"][:-4]
    arms = ["h66a_cover_gated_a_only", "single_A", "single_B", "union_max",
            "disagreement_pre", "disagreement_post", "random"]
    rows = "".join(
        f"| {a} | {sc[a]['dti']:.6f} | [{sc[a]['ci95'][0]:.6f}, {sc[a]['ci95'][1]:.6f}] |\n"
        for a in arms)
    return f"""{START}
# Current status — H66cover (2026-10-09): co-training lane, cover-gated A-only emission — {"NEGATIVE, research-only" if negative else "eligible for selector, not promoted"}

> **SUBMIT TO THE COMPETITION: {"NO." if negative else "NOT HERE — promotion is a separate selector step."}**
> The one-click file below is the H66cover research GeoTIFF. Verdict: `{verdict}`

*Namespacing (IR-H66-015): a parallel session merged a different round under the "H66" label first
(PR #56, structural coherence — the site's `h66-*` pages are that round's), and another merged H65halo
and a thermal-upflow round renamed H67 (PR #58). This round is the cover-gated co-training H66, so its
block, files and links carry the `h66cover` prefix; main's blocks above and below stay verbatim.*

**What was tested.** H66-A, the only hypothesis run this round: the brief's co-training protocol executed in
full — empirical independence screen on spatial-block out-of-fold errors of the two views over labelled
negatives, one confident-to-abstaining whole-segment pseudo-label round, then a new placement field
`(rankA − rankB) × log1p(cover)` restricted to the A-only stratum (View A confident, View B abstaining),
which is the brief's "buried beneath cover" reading of the disagreement signal. Preregistered in
[`knowledge/43_h66cover`](knowledge/43_h66cover_hypotheses_preregistered.md) (SHA-256 pinned in
`registry/h66cover_preregistration.json`, with the dated amendment
`knowledge/43_h66cover_amendment_2026-10-09_budget.md`); the H61 views, learner, seed and stages are
reused unchanged, so H61's fits are reproduced, not re-tuned. Four further hypotheses (H66-B two-round
exchange, H66-C strain–seismicity View A, H66-D long-wavelength deep-edge View A, H66-E B-only artifact
control) are registered and deferred — see the preregistration §2.

| Check | Label | Result | Receipt |
|---|---|---|---|
| Leakage canary (alarm > 0.90) | PREMISE-AUC | max single-feature raw AUC **{f(can['max_alarm_across_folds'])}**; any alarm: {can['any_alarm']} | [`evidence/h66cover_canary.json`](evidence/h66cover_canary.json) |
| Independence screen (mandated) | PREMISE-AUC | max abs Spearman rho **{f(exch['independence_pre']['max_abs_correlation'])}** over {exch['independence_pre']['n_blocks']} blocks (abandon >= 0.60) → exchange {'allowed' if exch.get('allowed_exchange') else 'REFUSED'}; {exch.get('total_pseudo_pixels') or 0} pseudo-label px | [`evidence/h66cover_pseudo_exchange.json`](evidence/h66cover_pseudo_exchange.json) |
| HOLDOUT-DTI, H66-A vs single_B | HOLDOUT-DTI | h66a **{cand['dti']:.6f}** [{cand['ci95'][0]:.6f}, {cand['ci95'][1]:.6f}] vs single_B **{sB['dti']:.6f}**; paired delta **{paired['delta']:+.6f}** [{paired['ci95'][0]:+.6f}, {paired['ci95'][1]:+.6f}] → {'BEATS' if paired['delta'] > 0 and paired['ci95'][0] > 0 else 'does not beat'} the single-view baseline | [`evidence/h66cover_holdout.json`](evidence/h66cover_holdout.json) |
| Lane gate, surface / dots | diagnostic | surface {lane_s['policy']['verdict']} (literal {lane_s['literal']['verdict']}) · dots {lane_d['policy']['verdict']} (literal {lane_d['literal']['verdict']}) — 100% of dots within 3 px of the H64 raster (IR-H66-014) | [`evidence/h66cover_lane_dots.json`](evidence/h66cover_lane_dots.json) |
| Decoded-pattern uniqueness | diagnostic | tier 1 (all {uniq['tier1_all_priors']['n_priors']} priors): {'unique' if uniq['tier1_all_priors']['canonical_pattern_unique'] else 'IDENTICAL'}; tier 2 novelty vs {card['counts']['informative_rasters']} informative priors: **{uniq['tier2_informative_priors']['novel_fraction']:.4f}** | [`evidence/h66cover_uniqueness.json`](evidence/h66cover_uniqueness.json) |
| Not the union of the two views | diagnostic | {'PASS' if card['not_the_union']['not_union_pass'] else 'FAIL'}; every emitted cell inside the A-only gate ({card['not_the_union']['emitted_cells_inside_a_only_gate']}/{card['counts']['placed']}) | [`evidence/h66cover_not_union.json`](evidence/h66cover_not_union.json) |
| Format gate (local) | diagnostic | {'PASS' if card['validator']['ok'] else 'FAIL'}: single-band float32, values exactly {{0,1}}, 0 NaN, EPSG:32611, shape/transform identical to `data/sample_submission.tif` | [`submission/{stem}.json`](submission/{stem}.json) |

**HOLDOUT-DTI, all seven arms** (evaluator `gems52-pooled-hide-v1`, α 0.2, β 0.8, 300 m triangular kernel,
{f"{int(cand['withheld_positive_pixels']):,}"} withheld positives, 95% paired physical-cluster bootstrap,
{hold['pooled']['bootstrap']['clusters']} clusters, {hold['pooled']['bootstrap']['draws']} draws; 9,400 dots per arm per fold at 3 px):

| arm | HOLDOUT-DTI | 95% CI |
|---|---:|---:|
{rows}
**Verdict: {"H66cover not promoted." if negative else "H66cover eligible for the selector; not promoted."}** Experiments used: 3 of 3 (E1 canary+fit+independence, E2 exchange+holdout, E3 build+gates+GeoTIFF). Run card:
[`evidence/h66cover_run_card.json`](evidence/h66cover_run_card.json). Full note: [`knowledge/44_h66cover`](knowledge/44_h66cover_results_and_limits.md).
Site: **[download the H66cover GeoTIFF](docs/downloads/h66cover-candidate.tif)** · [ZIP](docs/downloads/h66cover-candidate.zip) ·
[reasoning CSV](docs/downloads/h66cover-a-only-reasoning.csv) ·
[executive summary / exact submission steps](docs/h66cover-executive-summary.html) · [landing page](docs/h66cover.html).

- **File:** `{card['raster']['file']}` — {card['raster']['bytes']:,} bytes, {card['counts']['placed']:,} emitted cells
  (the frozen A-only gate has {card['counts']['gate_cells']:,} exact-novel cells, so the template budget
  {card['counts']['budget_template']:,} is a cap — IR-H66-013)
- **SHA-256:** `{card['raster']['sha256']}`
- **Name ({len(card['submission_name'])} characters):** `{card['submission_name']}`
- **Note ({card['note_chars']} characters):** `{card['note']}`
- **Projection (never a score):** break-even credit density to match the owner-reported 0.2778 at this budget:
  {proj['G_lower']['breakeven_credit_density_to_match_champion']:.4f} at |G| = {proj['G_lower']['G_px']:.1f} and
  {proj['G_upper']['breakeven_credit_density_to_match_champion']:.4f} at |G| = {proj['G_upper']['G_px']:.1f}
  (measured interval [5,949.3, 12,512.1] px). DTI if this arm's holdout density held:
  {proj['G_lower']['dti_if_density_equals_holdout_arm']:.4f} / {proj['G_upper']['dti_if_density_equals_holdout_arm']:.4f}.

**Leaderboard (PUBLIC BOARD, not ORGANIZER-CONFIRMED).** Live DrivenData board 2026-10-09: top **0.3774**
(xiaofanhu), 0.3195 is rank 7 (DARD), 0.2778 is rank 13 (extradr19):
[leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/). The brief's
"0.3195 is the highest score" is wrong (IR-H65-002, IR-H66-012). ORGANIZER-CONFIRMED: none — no submission-page
receipt exists for any file in this repository. Competition slots used: **0**.

**Why 0.2778 won, in one paragraph (measured, `knowledge/27`).** The reported-0.2778 file is the
reported-0.2600 file with 6,436 pixels deleted — every one 100–200 m from a mapped trace — and zero pixels
added. Because `DTI = T / (0.2·(T+S−M) + 0.8·(|G|−T))`, deleting zero-credit pixels raises the ratio +6.8 %
without detecting anything new: it is a precision edit, not a better detector. Beating it needs credit
density above the break-even bar on novel mass, and no instrument in this repository can certify that —
the hide-and-recover simulator measured Spearman −0.10 against the owner-reported board (R4).

**Still open:** a lane-valid candidate that beats single_B on the holdout (the A-only stratum sits inside the
H64 raster's 3 px halo, IR-H66-014); the H66-B/C/D hypotheses; the 0.2778 file-to-row receipt; the portal
error text (IR-H65-007).
{END}
"""


def main() -> int:
    readme = ROOT / "README.md"
    text = readme.read_text()
    new = block().rstrip("\n")
    if START in text and END in text:
        # replace this round's block in place, normalised, so re-running is a byte-for-byte no-op
        head, rest = text.split(START, 1)
        _, rest = rest.split(END, 1)
        text = head + new + "\n\n" + rest.lstrip("\n")
    else:
        # insert directly below the current top block (main's), never displacing it
        m = re.search(r"<!--/[A-Z0-9]+-README-->", text)
        if m:
            cut = m.end()
            text = text[:cut] + "\n\n" + new + text[cut:]
        else:
            text = new + "\n\n" + text
    readme.write_text(text)
    print(f"README.md updated: {len(text.splitlines())} lines, {readme.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
