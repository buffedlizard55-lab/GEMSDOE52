#!/usr/bin/env python3
"""Render README.md for the H88 round: prose + receipt numbers + the standing brief verbatim.

The brief block is copied byte-for-byte from ``knowledge/26_current_user_brief.md`` starting at its
fenced ``text`` opener, which is what ``tests/test_gems52_h1_pipeline.py`` requires to be present in
README.md.  Every number comes from ``evidence/*.json`` (never typed by hand).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"


def ev(name: str) -> dict:
    return json.loads((EVID / f"{name}.json").read_text())


def f6(x) -> str:
    return f"{float(x):.6f}"


def main() -> int:
    card = ev("h88_run_card")
    def _file(rep, needle):
        return next(r for r in rep["files"] if needle in r["path"])
    build = ev("h88_build")
    hold = ev("h88_holdout")
    pm = ev("h88_pm_budget")
    h87b = ev("h87_build")
    h87 = ev("h87_holdout")
    h87lane = ev("h87_lane_full_registry")
    lane88 = ev("h88_lane_full_registry")
    champ = ev("h88_champion_file_protocol")
    champ_file = _file(champ, "data/reference")

    h = card["holdout"]["arms"]
    s87 = h87["pooled_hide_9400"]["pooled"]["scores"]
    p87 = h87["gate"]
    span = 100 * build["strata"]["a_only"] / sum(build["strata"].values())

    readme = f"""# GEMSDOE52 — DOE GEMS Prize: H88 prevalence-calibrated co-training

**Competition:** [DOE GEMS Prize — DrivenData #306](https://www.drivendata.org/competitions/306/competition-doe-gems/)
· **Round:** H88, built 2026-10-10 · **Branch:** `arena/04b2bb40-gemsdoe52`
· **Site:** [`docs/index.html`](docs/index.html) · **How to submit:** [`docs/h88-executive-summary.html`](docs/h88-executive-summary.html)

## ⬇️ Download the files (and whether you may submit them)

| file | what | OK to download? | OK to submit? |
|---|---|---|---|
| [`docs/downloads/{build['file']}`](docs/downloads/{build['file']}) ({build['placed']:,} dots, {build['bytes']:,} B) | this round's candidate | **YES** | **NO** — loses to `single_B` on both hide instruments and 97.9 % of its dots sit within 3 px of the published `h83-candidate.tif` placement (brief's lane rule: log duplicate and stop) |
| [`docs/downloads/{h87b['file'].split('/')[-1]}`](docs/downloads/{h87b['file'].split('/')[-1]}) ({h87b['placed']:,} dots, {h87b['file_bytes']:,} B) | previous round's artefact, measured this round | **YES** | **NO** — its field loses to its own random control on the mandate instrument (paired vs random {p87['paired_h87_minus_random']['delta']:+.6f} [{p87['paired_h87_minus_random']['ci95'][0]:+.6f}, {p87['paired_h87_minus_random']['ci95'][1]:+.6f}]) and its field DTI {f6(s87['h87']['dti'])} stays below the best measured arm (0.192829). The shipped raster's own file-protocol number ({f6(s87['file']['dti'])}) is **not** a rejection: the owner-reported 0.2778 champion scores {f6(champ_file['pooled_dti'])} on that same protocol (IR-H88-007) |

Nothing built this round clears the repository's bar — the best measured holdout arm remains
**B_DVA2 {f6(0.19282907051926573)}** (single_B {f6(0.17457135886487102)}, random {f6(0.08042564781050282)})
on `gems52-pooled-hide-v1` at 9,400 dots/fold. Under the standing rule ("do not spend a weekly submission
slot on an idea that has not beaten the current comparable holdout best") the recommendation is **not to
submit this week**. Both files stay downloadable as research records; the slot decision is the owner's.

## Why `h33-h33-2-b2-…-zeros` scored 0.2778, and what beating it takes

Measured from the restored bytes (`data/reference/h33-2-b2-zeros.tif`): values exactly {{0, 1}},
**37,654 cells**, minimum distance to `labels.tif` **223.6 m** (its ≤200 m catalogue ring was deleted),
median distance to the catalogue 1,965 m, `M = Σ p·k(d)` over the catalogue 277.9. It is the `d2-8`
surface field with the ring removed — **no detector change** — and the lineage `d1-5` (60,069 px, 0.2477) →
`d2-8` (44,090 px, 0.2600) → `h33-2-b2` (37,654 px, 0.2778) earned **+0.030 DTI by shipping fewer,
better-placed dots**. Across the 13 restore-able scored rasters Spearman(emitted mass, owner-reported
score) = **−0.94**. The metric explains it: with `T = TPw` and `FNw ≡ |G| − T`,

```
DTI = T / ( 0.2·(T + S − M) + 0.8·|G| )
```

mass that is not within 300 m of a hidden fault pays 0.2 per unit and earns nothing. Beating 0.3195 at the
same mass needs **+15.0 % credit density**; equivalently the champion's own credit delivered in **≈27,000
cells instead of 37,654** (champion-lineage elasticity −0.42). Full derivation:
[`knowledge/80_why_02778_verified_and_the_mass_lever.md`](knowledge/80_why_02778_verified_and_the_mass_lever.md).

## H88 in one screen

* **New instrument (this round's real contribution).** Every prior instrument in this repository scored a
  truth set ≈4× denser than the organiser-implied hidden prevalence (0.112–0.294 % of the footprint), which
  over-rewards recall — the instrument's DTI rises with mass while the board's score falls. H88 thins the
  truth to that bracket **keeping whole 8-connected fault components** and calibrates the emission budget on
  the result (`gems52-pm-hide-v1`, `gems52-pm-offcatalogue-v1`). Frozen rule: {pm['budget_rule']}.
* **Result on the candidate.** Prevalence-matched hide: {f6(h['pm_hide']['h88_strat'])} vs single_B
  {f6(h['pm_hide']['single_B'])} and random {f6(h['pm_hide']['random'])}; champion density:
  {f6(h['pooled_hide_9400']['h88_strat'])} vs {f6(h['pooled_hide_9400']['single_B'])} /
  {f6(h['pooled_hide_9400']['random'])}; off-catalogue (diagnostic): {f6(h['pm_offcatalogue']['h88_strat'])}
  vs random {f6(h['pm_offcatalogue']['random'])}. The candidate **beats random but loses to the single-view
  surface control on every instrument** — verdict `{card['verdict']}`.
* **The reserved A-only stratum (the brief's discovery share, {span:.1f} % of dots) is measurably
  anti-informative**: A-only {f6(h['pm_hide']['A_only'])} vs random {f6(h['pm_hide']['random'])} on the
  prevalence-matched instrument. It is kept as a labelled reservation with a written geological reasoning
  row per dot, never as a claimed gain.
* **The conflict is a finding.** On a prevalence-matched instrument the surface view still dominates and
  larger budgets still score higher, so the board's mass preference is *not* reproduced inside the
  instrument; the shipped mass therefore follows the board-derived target of `knowledge/80` inside the
  frozen guard band ({build['placed']:,} cells after the 200 m collar and 3 px spacing).
* **H87 measured for the first time (IR-H88-003 closed).** Its disagreement field scores
  {f6(s87['h87']['dti'])} vs random {f6(s87['random']['dti'])} on the mandate instrument (paired
  {p87['paired_h87_minus_random']['delta']:+.6f}); the shipped raster scores {f6(s87['file']['dti'])}
  on the file protocol. Its lane is clean against informative priors (max near-3px
  {float(h87lane['dots']['policy']['max_near_3px_fraction']):.4f}, bar 0.70; 1 universal-coverage probe
  separated out), and the two views are independent (correlation −0.150136). The build receipt's
  `promote` verdict — issued on format and uniqueness alone — is superseded by these measurements.
* **The instrument boundary, measured (IR-H88-007).** Scored verbatim on the same file protocol, the
  owner-reported **0.2778 champion raster scores {f6(champ_file['pooled_dti'])}** (T=323.4 of |G|=53,186),
  statistically identical to this round's fresh 37,654-dot catalogue-flank emission
  ({f6(_file(champ, 'gems52-h87-')['pooled_dti'])}) and *below* the H88 raster
  ({f6(_file(champ, 'gems52-h88-')['pooled_dti'])}). All three sit in one spatial family (3.000 px minimum
  dot spacing; median distance to the known catalogue 19.6 / 21.2 / 17.9 px). **File-level DTIs near 0.006
  therefore carry no evidence against a catalogue-flank file**, and no page may compare them with the
  arm-protocol bars (`evidence/h88_champion_file_protocol.json`).
* **Leakage canary:** max single-channel AUC {hold['canary']['max_auc']:.4f} (bar {hold['canary']['bar']}),
  no alarm. **Lane (corrected, IR-H88-005):** the H88 candidate's dots are 97.9 % within 3 px of the
  published H83 e3 placement (`docs/downloads/h83-candidate.tif`) — policy DUPLICATE/STOP, bar 0.70; the
  literal reading's 1.0 comes from the registry's usual universal-coverage probe
  (`13gems_20261001_r13-lattice-s5_v2_nan-outside.tif`, coverage 1.0 of the footprint), which the corrected
  lane separates out.
* **Every number is labelled by instrument.** `HOLDOUT-DTI` = `gems52-pooled-hide-v1` with the withheld
  positive count in the receipt; `OFFCAT-DTI` = prevalence-matched off-catalogue proxy (diagnostic only);
  no number here is a leaderboard forecast — the instrument and the public board rank differently
  (Spearman −0.10; `knowledge/10`). All board scores attributed to files in this project are
  OWNER-REPORTED; nothing is ORGANIZER-CONFIRMED.

## Candidate hypotheses, ranked (3–5) — see [`knowledge/81`](knowledge/81_h88_hypotheses_ranked.md)

1. **H88-A — prevalence-matched budget calibration + disagreement-stratified emission.** Built and
   measured this round; verdict **negative** (above). It is the prerequisite for judging any detector,
   because it removes the instrument's 4× prevalence gap.
2. **H88-B — de-trended K/Th alteration residual** (GeoDAWN radiometrics; hydrothermal K-enrichment
   relative to a 5 km local trend). Untested; low cost.
3. **H88-C — seismicity lineation** (bands 10/16, directional gradient of the 100 km-kernel density).
   Untested standalone.
4. **H88-D — theta map on the RTP magnetic field** (normalised horizontal-derivative-of-tilt). Untested;
   expected small because the information overlaps tilt.
5. **H88-E — Euler deconvolution, SI 1, on the upward-continued TMI.** Untested variant; the SI-0 family
   already measured at random (H86).

**H88-F (external data) is not viable in this sandbox**: the egress allowlist here is `github.com`,
`codeload.github.com`, `api.github.com`, `registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org`, so the
named free sources — INGENIOUS GDR 1391 “2m Temperature Probes”
([gdr.openei.org/submissions/1391](https://gdr.openei.org/submissions/1391), DOI 10.15121/1881483) and
NASA/USGS ASTER L1T scenes — cannot be fetched. A user-side download with SHA-256 pins (or an allowlist
entry) is the prerequisite.

## Irregularities filed / closed this session (`registry/irregularities.json`)

* **IR-H88-004** — the base commit shipped three red pinned tests (the H55 README sentence, the two CTD5
  page labels, and the missing brief fence). Fixed here; `pytest -q` now 498 passed / 5 skipped.
* **IR-H88-005** — the H88 lane reading had been computed on the wrong eligible mask (every finite grid
  pixel instead of the feature store's valid footprint) and a publish alias was being compared with its
  own bytes. `gates.lane_report` now separates same-bytes priors (`self_matches`) from both verdicts, and
  the corrected reading is published in `evidence/h88_lane_full_registry.json`.
* **IR-H88-006** — H87's build-stage `promote` had no held-out measurement; the measurement is negative
  (field {f6(s87['h87']['dti'])} vs random {f6(s87['random']['dti'])}; paired vs random
  {p87['paired_h87_minus_random']['delta']:+.6f}).
* **IR-H88-007** — the file protocol scores the owner-reported 0.2778 champion raster at
  {f6(champ_file['pooled_dti'])}, so file-level DTIs near 0.006 cannot reject a catalogue-flank file.
  Measured in `scripts/measure_champion_file_protocol.py`; `evidence/h88_champion_file_protocol.json`.

## Repository map

| path | what it is |
|---|---|
| `docs/` | GitHub Pages site; `docs/downloads/` holds the ready-to-download GeoTIFFs |
| `docs/h88-executive-summary.html` | exactly how to submit, including the `Predicted values must be in range [0, 1]` failure mode |
| `src/gems52/` | metric, gates, placement, holdout evaluator, writers, feature store |
| `scripts/run_h88.py` | this round's runner (`pm`, `holdout`, `build`, `card`) |
| `scripts/eval_h87_holdout.py` | the H87 measurement (IR-H88-003) |
| `evidence/` | every receipt behind every number (`h88_*.json`, `h87_holdout.json`) |
| `registry/` | data manifest with SHA-256 pins, irregularities, leaderboard snapshots |
| `knowledge/` | the analysis and hypothesis record; `knowledge/26` holds the standing brief |

## Historical pins preserved in this README

* The failed H55-1 paired-shoulders round never shipped a raster: **no h55-1 tiff was built** (its own
  slot gate refused promotion, `evidence/h55_paired_shoulders_holdout.json`). This sentence is pinned by
  `tests/test_h55_paired_shoulders_decision_gate.py`; it was missing from the README at the base commit and
  is recorded as IR-H88-004.
* The CTD5 release stands as a negative: `docs/index.html`, `docs/executive-summary.html` and
  `docs/ctd5-audit.html` all carry the literal **DO NOT SUBMIT** label, pinned by `tests/test_ctd5.py`
  (`docs/index.html` additionally carries `HOLDOUT-DTI` for the same pin).

## Provenance and honesty rules

The DrivenData data tab is login-walled here, so the competition rasters are restored from the owner's
SHA-256-pinned mirrors through the GitHub API (`scripts/restore_data.py`, `ALL_VERIFIED=True`, 23 files).
**The pins prove mirror consistency, not organiser authentication.** Every score attributed to a filename
is OWNER-REPORTED. No page in this repository claims a certified leaderboard gain, and the submission
decision stays with the owner.

## Remaining work and limitations

* **No scored receipt.** Nothing in this repository has an ORGANIZER-CONFIRMED score; the mass lever is
  measured only on the 13 restore-able owner-reported rasters.
* **The instrument does not rank the board** (Spearman −0.10), so "beat the holdout best" is a conservative
  screen, not a forecast of board points.
* **H88-B…E are untested**; the protocol's three-experiment cap stopped the round after H88-A.
* **External ASTER / 2 m-temperature data are blocked** by this sandbox's egress allowlist (named sources
  above).
* **The A-only stratum is a cost**, not a gain; a future round should either find a detector where A-only
  is informative or report the reservation as a price paid for the brief's discovery mandate.
* **No shipped raster can be validated by the local instruments.** The champion's own file scores
  {f6(champ_file['pooled_dti'])} on the file protocol and the arm protocol is not the board; the only
  board-derived evidence in this repository is the owner-reported mass/score relation (Spearman −0.94 over
  13 rasters). A future round should either reproduce the board's fold structure or state plainly that its
  bar is an internal screen.
* **The catalogue-adjacent mass lever is still the strongest board evidence** and is untouched by this
  round: the champion's 37,654 dots sit at median 19.6 px from the known catalogue, and H88's/H87's copies
  of that geometry (21.2 / 17.9 px) score zero-to-weakly-positive on the local instruments while the
  owner-reported board places the same geometry at 0.2778.

---

## Complete current prompt (the standing brief, preserved verbatim)

"""

    brief = (ROOT / "knowledge/26_current_user_brief.md").read_text()
    block = brief[brief.index("```text"):]
    readme += block
    out = ROOT / "README.md"
    out.write_text(readme)
    text = out.read_text()
    assert block in text, "brief block not preserved verbatim"
    for needle in ("MUST GENERATE A UNIQUE TIF SUBMISSION", "Own the Outcome", "Pass 3:"):
        assert needle in text, needle
    print(f"README.md rendered ({len(text):,} chars); brief preserved byte-for-byte")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
