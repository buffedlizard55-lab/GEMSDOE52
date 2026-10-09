#!/usr/bin/env python3
"""Render the H61 header block of README.md from the receipts.

The README is the first thing the next session reads, so its numbers must be the receipts' numbers.
This script splices a rendered H61 block into README.md between explicit markers, preserves the CTD5
block verbatim under its own heading (a negative result stays a deliverable), and rewrites the four
session-facing sections.  Running it twice is a no-op.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
START, END = "<!--H61-README-->", "<!--/H61-README-->"


def load(n: str) -> dict:
    return json.loads((EVID / f"h61_{n}.json").read_text())


def f(x, nd=4):
    return "n/a" if x is None else f"{float(x):.{nd}f}"


def block() -> str:
    card, sub, foren = load("run_card"), load("submission"), load("forensics")
    card["validator"] = {**sub["receipt"]["validator"], **card["validator"]}
    hold, exch, can = load("holdout"), load("pseudo_exchange"), load("canary")
    proj, lane, lanes = load("projection"), load("lane_dots"), load("lane_surface")
    try:
        closure = load("concurrent_closure")
    except Exception:                                            # noqa: BLE001
        closure = None
    fit = load("fit_checkpoint")
    G = foren["G_identification"]["masked"]
    sc = hold["pooled"]["scores"]
    cand = sc["disagreement_post"]
    lit, pol = lane["literal"], lane["policy"]
    aucs = {r["fold"]: (r["view_A"]["heldout_region_auc"], r["view_B"]["heldout_region_auc"])
            for r in fit["folds"]}
    mA = sum(v[0] for v in aucs.values()) / len(aucs)
    mB = sum(v[1] for v in aucs.values()) / len(aucs)
    ok = bool(card["submit_ok"])
    rows = "".join(f"| {k} | {f(v['dti'], 6)} | [{f(v['ci95'][0], 6)}, {f(v['ci95'][1], 6)}] |\n"
                   for k, v in sc.items())
    return f"""{START}
# GEMSDOE52 — a new research GeoTIFF and an explicit submit verdict

**[★ Download the H61 GeoTIFF — one click](docs/downloads/h61-candidate.tif)** ·
[single-TIFF ZIP](docs/downloads/h61-candidate.zip) ·
[geological reasoning CSV](docs/downloads/h61-a-only-reasoning.csv) ·
**[Executive summary / exact submission guide](docs/executive-summary.html)** ·
[Run &amp; evidence](docs/h61-audit.html) · [Sources](docs/h61-sources.html) ·
[Run card](evidence/h61_run_card.json)

> **DOWNLOAD: {"YES" if card["download_ok"] else "NO"} · SUBMIT TO THE COMPETITION: {"YES" if ok else "NO"}.**
> Verdict `{card["verdict"]}`. The file is newly inferred, portal-safe by construction and different
> from every checked prior's decoded predictions, but it does **not** beat the reported champion at
> either end of the measured `|G|` interval, and its own view-A premise failed on the holdout.
> **Competition slots used: {card["slots_used"]}.**

- **File:** `{card["raster_file"]}` — {card["raster_bytes"]:,} bytes, {card["emitted_px"]:,} emitted cells
- **SHA-256:** `{card["raster_sha256"]}`
- **Name:** `{card["submission_name"]}`
- **Note ({card["note_chars"]} / 140 chars):** `{card["note"]}`
- **Local validator:** one float32 band; values exactly {{0, 1}}; {card["validator"]["nan_pixels"]} NaN and
  {card["validator"]["infinity_pixels"]} Inf; {card["validator"]["crs"]};
  {card["validator"]["height"]:,} × {card["validator"]["width"]:,}; transform identical to the pinned
  `sample_submission.tif`; nothing within 200 m of a mapped trace. *Not an organizer acceptance receipt.*
- **HOLDOUT-DTI** (`{hold["pooled"]["evaluator_version"]}`, {int(cand["withheld_positive_pixels"]):,} withheld
  positives, 95% paired 20 km cluster bootstrap): candidate **{f(cand["dti"], 6)}**
  [{f(cand["ci95"][0], 6)}, {f(cand["ci95"][1], 6)}]; best comparable control
  `{hold["pooled"]["best_comparable_control"]}`. Every arm filled its
  {hold["budget_per_arm_per_fold"]:,}-dot budget at {hold["min_separation_px"]:g} px spacing
  ({"matched — comparison eligible" if hold["all_arms_filled"] else "NOT matched — comparison ineligible"}).

| arm | HOLDOUT-DTI | 95% CI |
|---|---:|---:|
{rows}
- **Why this lane failed, measured:** View A (potential field / subsurface, {len(fit["view_A_features"])}
  channels incl. upward-continued TMI) reaches in-sample AUC
  {f(max(r["view_A"]["in_sample_auc"] for r in fit["folds"]), 3)} and out-of-quadrant AUC
  **{f(mA, 3)}** — chance. View B (DEM curvature/slope + band 6 + external K, Th, U, Th/K, U/K, U/Th)
  reaches **{f(mB, 3)}**. A sufficient view cannot be at chance out of sample, so the A→B transfer hands
  over noise. Independence held (max |ρ| {f(exch["independence_pre"]["max_abs_correlation"])} over
  {exch["independence_pre"]["n_blocks"]} blocks, abandon at
  {exch["independence_pre"]["threshold"]}); the canary was clean (max single-feature held-out AUC
  {f(can["max_alarm_across_folds"])} vs alarm {can["alarm_auc"]}). One exchange,
  {exch["total_pseudo_pixels"]:,} pseudo pixels. [IR-H61-006](registry/irregularities.json).
- **Lane gate:** {lane["priors_checked"]} registry rasters ({lane["distinct_decoded_priors"]} distinct decoded
  patterns), the full 526-blob census re-materialised and SHA-verified. Literal rule (all priors):
  **{lit["verdict"]}**, max near-dot {f(lit["max_near_3px_fraction"])}, max Spearman
  {f(lit["max_spearman"])}. Saturation-aware policy (informative priors only):
  **{pol["verdict"]}**, max near-dot {f(pol["max_near_3px_fraction"])}, max Spearman
  {f(pol["max_spearman"])}. Surface phase before placement: literal `{lanes["literal"]["verdict"]}`,
  policy `{lanes["policy"]["verdict"]}`. Decoded-pattern uniqueness
  {"PASS" if sub["uniqueness_summary"]["canonical_pattern_unique"] else "FAIL"}; literal union of priors
  {"YES" if sub["uniqueness_summary"]["equals_literal_prior_union"] else "NO"}.
- **Concurrent closure:** after the parallel R5 and H60D rounds merged into `main`, the *unchanged*
  emission was re-checked against the {closure["new_decoded_patterns_checked"] if closure else 0} newly added
  decoded patterns: verdict **{closure["verdict_on_new_rasters"] if closure else "n/a"}**, max near-dot
  {f(closure["max_near_3px_fraction"]) if closure else "n/a"}, max Spearman
  {f(closure["max_spearman"]) if closure else "n/a"} ([receipt](evidence/h61_concurrent_closure.json)).
  A pass here does not overturn the original lane STOP; the artefact was not rebuilt or re-tuned for it.
- **PROJECTION, never a score:** at {int(proj["G_lower"]["emitted_px"]):,} dots the break-even credit
  density to match the reported champion is
  {f(proj["G_lower"]["breakeven_credit_density_to_match_champion"])}–{f(proj["G_upper"]["breakeven_credit_density_to_match_champion"])}
  per pixel ({f(proj["G_lower"]["breakeven_multiple_of_random"], 1)}–{f(proj["G_upper"]["breakeven_multiple_of_random"], 1)}×
  uniform random). Novel mass belongs to no identified atom, so organiser-tied evidence bounds its
  credit only by [0, |G|]. **No leaderboard gain is claimed or projected.**

## What H61 repaired in the shared instruments, before fitting anything

1. **`|G|` is an interval, not a measurement: [{G["G_lower_bound"]:,.1f}, {G["G_upper_bound"]:,.1f}] px.**
   Thirteen owner-reported scores are thirteen equations in fourteen unknowns. The previously published
   point value {foren["G_point_under_zero_ring_credit"]["G_px"]:,.1f} px is **outside** that interval; it
   requires the 6,436 px the champion deleted to earn exactly zero credit, and 25 credit of ring income
   alone moves it to {f(foren["G_point_under_zero_ring_credit"]["sensitivity_to_ring_credit"][1]["G_px"], 0)} px.
   [IR-H61-001](registry/irregularities.json) · [receipt](evidence/h61_forensics.json)
2. **Masked support `S`.** Known catalogue pixels are masked out of evaluation, so `S` counts
   off-catalogue pixels. Witness: `Hedge-v2` and `ens12-7f00890a` have identical off-catalogue support
   (Jaccard 1.000) and identical reported scores, yet raw-`S` accounting gave them credit
   {f(foren["masked_accounting_witness"]["T_under_raw_accounting"][0], 1)} vs
   {f(foren["masked_accounting_witness"]["T_under_raw_accounting"][1], 1)}; masked gives both
   {f(foren["masked_accounting_witness"]["T_under_masked_accounting"][0], 1)}. [IR-H61-002]
3. **Band 6 is radiometric total count**, not the magnetic tilt derivative its own description claims:
   Spearman {f(foren["band6_identity"]["best_external_match"]["spearman"])} against the independently
   derived external GeoDAWN TC grid, {f(foren["band6_identity"]["spearman_vs_tilt_deg_of_TMI"])} against
   the tilt angle of TMI from bands 9/3, {f(foren["band6_identity"]["spearman_vs_tmi_hg"])} against
   `tmi_hg`, on {foren["band6_identity"]["n_sampled"]:,} eligible pixels. It stays in View B, and that is
   now measured rather than provisional. [IR-H61-003]
4. **Attribution strength is not uniform.** Only
   {sum(1 for x in foren["files"].values() if x["attribution_class"].startswith("HASH"))} of
   {len(foren["files"])} owner-reported scores hash-link to the bytes held; the champion's token
   `e5eb6e7e` matches none of six hash conventions of the file we hold, and GEMSDOE32's own page says no
   organizer score exists. Every score here is **OWNER-REPORTED, NOT ORGANIZER-CONFIRMED**. [IR-H61-004]
5. **The literal 3 px lane rule was unsatisfiable, and now says why.** The 13GEMSDOE spacing-five
   lattice's 3 px halo covers 1.0000 of the eligible footprint (a spacing-5 square lattice has maximum
   interior distance √8 = 2.83 px), so it returns DUPLICATE for *every* nonempty raster — that is why
   CTD5 stopped. `gems52.gates.lane_report` now classifies a prior with measured coverage ≥ 0.95 as a
   **universal-coverage probe**, applies the literal rule to informative priors, and still reports the
   literal statistic for every prior. Probes are not deleted and no threshold was relaxed. [IR-H61-005]
6. **H60C would fail the brief's own lane rule**: near-dot 0.7929 against the champion and 0.8087
   against `h19-5`, Spearman 0.7083 — DUPLICATE/STOP under the literal rule *and* under the policy,
   because those priors are informative. Its published gate used support-novelty and Jaccard instead.
   Flagged for the selector, neither promoted nor deleted. [IR-H61-007]
7. **CTD5's own diagnosis is vindicated by the same instrument**: its informative-prior near-dot
   fractions are 0.1063–0.1368 with |ρ| ≤ 0.0046, i.e. its STOP was entirely the probe.

## Why 0.2778 won, measured from the bytes

The reported-0.2778 champion `h33-2-b2` is a **strict subset** of the reported-0.2600 file
(37,654 ⊂ 44,090 off-catalogue px), which is itself a strict subset of the reported-0.1922 parent field
(⊂ 121,131 px). The champion added **zero** pixels and deleted
{foren["catalogue_rings"]["base_only_px"]:,}, every one of them between
{f(foren["catalogue_rings"]["base_only_distance_to_catalogue_m"]["min"], 0)} m and
{f(foren["catalogue_rings"]["base_only_distance_to_catalogue_m"]["max"], 0)} m from a mapped trace; its own
nearest dot is {f(foren["catalogue_rings"]["champion_distance_to_catalogue_m_min"], 1)} m away. Since
`DTI = T / (0.2·(T + S − M) + 0.8·(|G| − T))` carries a fixed `0.8·|G|` floor in the denominator, pruning
zero-credit mass raises the ratio without finding anything new. **It is precision, not detection.**
Beating it therefore needs either a recombination of existing public mass — which is a duplicate by
construction and outside this lane — or a detector above
{f(proj["G_upper"]["breakeven_credit_density_to_match_champion"])} credit density on *novel* mass, which
no instrument in this repository can certify: the local simulator measured Spearman −0.10 against the
owner-reported board in R4.
<!--/H61-README-->"""


SECTIONS = {
    "## Start here every session": """## Start here every session

Read the **complete current prompt below**, the [working agreement](AGENTS.md), the frozen H61
protocol [knowledge/30_hypotheses_H61_preregistered.md](knowledge/30_hypotheses_H61_preregistered.md),
its results [knowledge/31_h61_results_and_limits.md](knowledge/31_h61_results_and_limits.md), and the
[irregularity registry](registry/irregularities.json) entries `IR-H61-001` … `IR-H61-008`. Read the
previous failed experiments (H55–H60C, CTD5) before proposing another.

**Maximize P(Win):** do not consume a scarce weekly slot on an arm whose only density estimate comes
from a simulator that does not predict the board. **Own the Outcome:** publish the real file, the
failed premise, the repaired instruments, the provenance gaps and a working reproduction.
""",
    "## What this session completed": """## What this session completed

1. Restored every pinned input autonomously (`scripts/restore_data.py`: 419 MB feature stack, labels,
   sample submission, four external layers, thirteen scored priors — all SHA-256 and byte-count
   verified) and re-materialised the whole **526-blob prior census** with
   `scripts/fetch_prior_inventory.py` (524/526 census-hash matches; the two exceptions are the census'
   own ineligible fixture and format-test files).
2. Repaired the shared forensic accounting **before** fitting anything: masked support `S`, `|G|` as a
   rigorous interval, band-6 identity resolved on the bytes, attribution hash-links measured
   (`scripts/h61_forensics.py`).
3. Extended the shared feature store once, in the template, with the external GeoDAWN radiometrics in
   View B and the upward-continued TMI in View A (`src/gems52/external.py`) — no private fork, and the
   manifest records provenance and the units caveat.
4. Preregistered H61 (`knowledge/30`, `registry/h61_preregistration.json`) and ran it on the corrected
   label-blind-quadrants-v2 splitter: per-feature leakage canary, block independence screen, exactly
   one whole-segment pseudo-label exchange, and a **matched-budget** six-arm hide-and-recover
   comparison — the capacity defect that made CTD5's comparison ineligible is fixed by ranking a field
   that is finite over the whole allowed domain.
5. Added the registry-saturation policy to the shared lane gate (`gems52.gates.lane_report`,
   `registry_coverage`), pinned by `tests/test_h61.py`, and used it to place two inherited artefacts
   correctly: CTD5 (its STOP was entirely the probe) and H60C (a genuine duplicate of the champion
   lane).
6. Built the unique research GeoTIFF, ran every gate, wrote the reasoning CSV for all emitted cells,
   published the site with an unambiguous download/submit verdict, and recorded eight irregularities.
   Full test suite: `python -m pytest -q`.
""",
    "## Reproduce the research file": """## Reproduce the research file

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-r2.txt
bash scripts/download_competition_data.sh                 # restore + SHA-256 verify the pinned inputs
PYTHONPATH=src .venv/bin/python -c "from gems52 import structural; structural.build(dest='work/r2/features', include_optional_profiles=False, log=lambda *a, **k: None)"
PYTHONPATH=src .venv/bin/python -m gems52.external        # add the shared external GeoDAWN columns
.venv/bin/python scripts/fetch_prior_inventory.py         # re-materialise the 526-blob registry
.venv/bin/python scripts/h61_forensics.py                 # repaired organiser-score algebra
.venv/bin/python scripts/run_h61.py all                   # canary -> fit -> exchange -> holdout
.venv/bin/python scripts/build_h61_submission.py          # place, gate, write, publish receipts
.venv/bin/python scripts/publish_h61_site.py              # render the pages from the receipts
.venv/bin/python scripts/h61_knowledge.py && .venv/bin/python scripts/h61_readme.py
.venv/bin/python scripts/check_site.py && .venv/bin/python -m pytest -q
```

Raw data, arrays, model caches and downloaded comparators stay ignored (`data/`, `work/`). Nothing
here uploads, promotes or spends a slot. The historical CTD5 reproduction
(`scripts/reproduce_ctd5.sh`, `scripts/run_ctd5.py`) is unchanged and still reproduces its rejected
legacy-v1 assay for audit only.
""",
    "## Evidence and next steps": """## Evidence and next steps

- [Frozen H61 protocol](knowledge/30_hypotheses_H61_preregistered.md) ·
  [results and limits](knowledge/31_h61_results_and_limits.md) ·
  [run card](evidence/h61_run_card.json) · [forensics](evidence/h61_forensics.json) ·
  [canary](evidence/h61_canary.json) · [fit](evidence/h61_fit_checkpoint.json) ·
  [independence](evidence/h61_independence.json) · [pseudo exchange](evidence/h61_pseudo_exchange.json) ·
  [pooled holdout](evidence/h61_holdout.json) · [projection](evidence/h61_projection.json) ·
  [lane gate on dots](evidence/h61_lane_dots.json) · [lane gate on surface](evidence/h61_lane_surface.json)
- [Site](docs/index.html) · [submission guide](docs/executive-summary.html) ·
  [run &amp; evidence](docs/h61-audit.html) · [sources](docs/h61-sources.html) ·
  [reasoning CSV](docs/downloads/h61-a-only-reasoning.csv) · [irregularities](registry/irregularities.json)

**Next, in priority order.**

1. **Change what View A is.** Raw potential-field channels do not transfer between quadrants
   (out-of-fold AUC ≈ 0.52). The next candidate is a *physically parameterised* View A — a modelled
   basement-depth step across a candidate trace, a strike-continuity score along an interpreted
   lineament, an isostatic-residual discontinuity — and its out-of-quadrant AUC must be measured
   **before** any emission is built.
2. **Run H61-D: cross-file credit localisation by terrain stratum.** Cross the LP atoms with slope,
   modelled cover thickness and radiometric alteration and bound credit per stratum, so the organizer's
   own scores say *where* hidden truth sits rather than *which prior* found it. Needs no new data; it
   was deferred only by this round's three-experiment budget.
3. **Give the selector a priced option, not a lane violation.** The only mass measured above the
   break-even density is inside the champion family, and emitting it is a duplicate by construction.
   That trade belongs to the selector with the weekly cap in front of it.
4. **Authenticate one receipt.** A single submission-page receipt tying a file SHA-256 to a score would
   turn IR-H61-004 from a caveat into a calibration and settle whether 0.2778 exists at all. No
   credentials may be requested or stored in chat.
5. **Reconcile `registry/data_manifest.json` provenance text** with the owner's score list (IR-H61-008)
   without touching the pins, and resolve the upstream `submission/LATEST.txt` pointer question in the
   shared selector rather than per round.

**Unresolved by sandbox limits, not by choice:** the DrivenData data tab and submission page are
login-walled; USGS, GDR and DOI hosts are unreachable (egress is limited to github.com,
codeload.github.com, api.github.com, registry.npmjs.org, pypi.org, files.pythonhosted.org). So no
fresh leaderboard top, no current weekly allowance, no organizer-authenticated input provenance, and
no official-host download is claimed anywhere in this round.
""",
}


def main() -> int:
    readme = ROOT / "README.md"
    text = readme.read_text()
    new = block()
    if START in text and END in text:
        head, rest = text.split(START, 1)
        _, rest = rest.split(END, 1)
        text = head + new + rest
    else:
        # first run: replace the CTD5 header block, keep it verbatim under its own heading
        marker = "## H60C —"
        idx = text.index(marker)
        header, tail = text[:idx], text[idx:]
        lines = header.splitlines(keepends=True)
        title_end = next(i for i, l in enumerate(lines) if l.startswith("# "))
        ctd5 = "".join(lines[title_end + 1:]).strip()
        text = (new + "\n\n## CTD5 — previous round, preserved verbatim (negative, lane-saturated)\n\n"
                "> Retained as a deliverable. Its `submission/CTD5_RESEARCH_LATEST.txt` marker, run card\n"
                "> and archive page are unchanged; nothing below is current authority.\n\n"
                + ctd5 + "\n\n" + tail)
    for anchor, replacement in SECTIONS.items():
        if anchor not in text:
            raise SystemExit(f"README anchor missing: {anchor}")
        start = text.index(anchor)
        # bound the replacement at the NEXT top-level heading of any kind, so unrelated sections
        # ("Why H33 may have improved", "Historical negative-result guards") are never swallowed
        nxt = text.find("\n## ", start + len(anchor))
        if nxt < 0:
            raise SystemExit(f"no heading after {anchor}")
        text = text[:start] + replacement.rstrip("\n") + "\n" + text[nxt + 1:]
    readme.write_text(text)
    print(f"README.md updated: {len(text.splitlines())} lines, {readme.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
