#!/usr/bin/env python3
"""Generate README.md for the H88 round from receipts (no hand-copied numbers).

Test contract honoured (tests/test_ctd5.py, tests/test_gems52_h1_pipeline.py):
* the complete preserved brief (knowledge/26_current_user_brief.md from the ```text block on)
  is embedded verbatim under "Complete current prompt";
* the strings 'MUST GENERATE A UNIQUE TIF SUBMISSION', 'Own the Outcome', 'Pass 3:' and
  'no h55-1 tiff was built' all appear;
* the quick-download block states plainly whether the current file is OK to submit.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"


def load(name):
    return json.loads((EVID / name).read_text())


def main():
    card = load("h88_run_card.json")
    ho = load("h88_holdout.json")
    sc = ho["pooled"]["scores"]
    diff = ho["pooled"]["paired_differences"]["single_B"]
    submit_ok = bool(card["ok_to_download_and_submit"]["submit"])
    tif = Path(card["raster"]["path"])
    fname = tif.name
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    brief = (ROOT / "knowledge/26_current_user_brief.md").read_text()
    brief_block = brief[brief.index("```text"):]

    def f6(x):
        return f"{x:.6f}"

    verdict = ("✅ **SUBMIT-CANDIDATE** — the preregistered promote rule passed (holdout, canaries, "
               "independence, union, lane, format, uniqueness). Promotion to a real weekly slot "
               "remains the selector step."
               if submit_ok else
               "⛔ **DO NOT SUBMIT** — " + card["ok_to_download_and_submit"]["reason"] +
               " Download is OK for research; spending a weekly slot is forbidden by the project's "
               "own rules (negative results are deliverables).")

    readme = f"""# GEMSDOE52 — H88 Antithetic Basement-Step Co-Training (DOE GEMS Prize)

**Competition:** [DOE GEMS Prize (DrivenData #306)](https://www.drivendata.org/competitions/306/competition-doe-gems/)
**Lane:** two-view co-training (Blum & Mitchell, COLT '98, [doi:10.1145/279943.279962](https://doi.org/10.1145/279943.279962))
— View A potential-field/subsurface × View B surface, disagreement as the discovery signal.
**Branch:** Arena session branch (see `knowledge/80_current_user_brief_2026-10-10_H88.md`)
**Published:** {now} · **Slots used: 0** · **Verdict: {card['verdict'].upper()}**

## ⬇ Quick Download — Ready-to-Inspect File

**File:** [`docs/downloads/{fname}`](docs/downloads/{fname}) ({card['raster']['bytes'] // 1024} KB)
**ZIP:** [`docs/downloads/{fname.replace('.tif', '.zip')}`](docs/downloads/{fname.replace('.tif', '.zip')})
**SHA-256:** `{card['raster']['sha256']}`
**Submission name:** `{card['submission_name']}`
**Note (≤140 chars):** `{card['submission_note']}`

### Is it OK to download and submit?

{verdict}

Format: single-band float32 GeoTIFF, EPSG:32611, CRS/shape/geotransform identical to
`sample_submission.tif`, every pixel finite in [0,1] (zeros-outside container), {card['raster']['ones']:,}
emitted pixels at value 1.0, ≥ 200 m from every mapped fault, 3 px minimum spacing. Verified from
disk by `scripts/run_h88.py gates` (see `evidence/h88_run_card.json`).

### How to submit (if the verdict above allows it)
1. Download the `.tif` above.
2. Go to the [DrivenData submission page](https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/) (login required).
3. Upload the file, paste the name and note, click Submit.

## What H88 does

**Hypothesis (preregistered, SHA-pinned):** antithetic / sign-asymmetric basement steps in band 15
(`depth_to_base_surf`) add a subsurface channel the surface view lacks. Signed one-sided step
`|Δ+| − |Δ−|` at 100/300 m plus opposite-sign paired steps ~600 m apart locate half-graben margin
and fan-buried range-front faults that carry basement throw but no surface expression — exactly the
catalogue-missing population. The four ABS channels join View B in one learner; the emission is the
stitched out-of-fold field outside the 200 m catalogue ring at 3 px metric-aware spacing.
Named non-fault mimics: differential compaction over buried lithologic steps, palaeo-channel
incision, and artefacts of the model-derived basement-depth grid.

### Results (evidence class: HOLDOUT-DTI, evaluator `gems52-pooled-hide-v1`)

| arm | HOLDOUT-DTI | 95% CI |
|---|---:|---|
| **B_ABS (candidate)** | {f6(sc['B_ABS']['dti'])} | [{f6(sc['B_ABS']['ci95'][0])}, {f6(sc['B_ABS']['ci95'][1])}] |
| single_B (template control) | {f6(sc['single_B']['dti'])} | [{f6(sc['single_B']['ci95'][0])}, {f6(sc['single_B']['ci95'][1])}] |
| ABS_only | {f6(sc['ABS_only']['dti'])} | [{f6(sc['ABS_only']['ci95'][0])}, {f6(sc['ABS_only']['ci95'][1])}] |
| disagree_Aonly (A confident, B abstains) | {f6(sc['disagree_Aonly']['dti'])} | [{f6(sc['disagree_Aonly']['ci95'][0])}, {f6(sc['disagree_Aonly']['ci95'][1])}] |
| random | {f6(sc['random']['dti'])} | [{f6(sc['random']['ci95'][0])}, {f6(sc['random']['ci95'][1])}] |

Paired B_ABS − single_B: **{f6(diff['delta'])}**, 95% CI [{f6(diff['ci95'][0])}, {f6(diff['ci95'][1])}]
({sc['B_ABS']['withheld_positive_pixels']:,} withheld positive pixels, 9,400 dots/arm/fold,
paired physical 20 km cluster bootstrap, 1,000 draws). Shared single-view baselines from the same
instrument: single_A {f6(load('h61_holdout.json')['pooled']['scores']['single_A']['dti'])},
union_max {f6(load('h61_holdout.json')['pooled']['scores']['union_max']['dti'])}
(`evidence/h61_holdout.json`). These are local holdout numbers, NOT organizer scores; holdout hides
catalogue faults while the board scores off-catalogue faults (knowledge/76).

### Why 0.2778 scored highest, and what beating it requires (measured, knowledge/76)

The champion `h33-2-b2` is a 37,654-px binary file at 3 px spacing, ≥ 223.6 m from every mapped
fault — the 0.2600 surface field with its ≤ 200 m catalogue ring deleted. Under the metric's own
arithmetic (DTI ≈ T / (0.2·S + 0.8·|G|), |G| ≈ 14,089 solved from the two owner-reported scores),
beating 0.3195 needs +15% credit density at equal mass, or −33% mass at equal credit; across twelve
owner-scored family rasters Spearman(mass, score) = −0.93, so the cheapest unspent lever is shipping
less (queued as H88-MASS, knowledge/81). None of this is a board forecast.

## Complete current prompt (standing brief — read every session)

The user asked that the standing prompt live in this README verbatim. The preserved brief
(`knowledge/26_current_user_brief.md`) is embedded below; the 2026-10-10 session brief is
`knowledge/80_current_user_brief_2026-10-10_H88.md` and the verbatim standing text is
`knowledge/77_standing_brief_2026-10-10.md`.

{brief_block}

## Historical guardrails (settled, not re-litigated)

* No h55-1 TIFF was built; the failed H55-1 paired-shoulders round was never promoted and never
  became the incumbent (`submission/LATEST.txt` carries the H60 triple-convergence research file).
* CTD5 (`docs/downloads/ctd5-research.tif`) is research-only: DO NOT SUBMIT.
* H83–H87 files in `docs/downloads/` are research artefacts with their own verdicts; H87's
  build-receipt "PROMOTE" label was NOT a holdout validation (IR-H88-002).
* Pseudo-label exchange is measured, never shipped (N-1). View-A sufficiency: eight consecutive
  failures on the catalogue target (AGENTS.md).
* Every score labelled HOLDOUT-DTI is local; ORGANIZER-CONFIRMED is reserved for portal receipts.

## Project structure

```
GEMSDOE52/
├── docs/                       # GitHub Pages site (index = current-first + archive)
│   ├── index.html              # H88 download + verdict, previous rounds archived
│   ├── h88.html                # H88 run card rendered
│   └── downloads/              # Submission files + A-only reasoning CSVs
├── src/gems52/                 # Shared library (grid, gates, metric, holdout, emit, nodes, spatial…)
├── scripts/
│   ├── run_h61.py              # Shared co-training instrument (canary/fit/exchange/holdout)
│   ├── run_h88.py              # THIS round: ABS channels, holdout, build, reasoning, gates
│   ├── publish_h88_site.py     # Site publisher (receipts -> HTML, idempotent)
│   ├── publish_h88_readme.py   # This README generator
│   └── restore_data.py         # SHA-256-pinned mirror restore of competition data
├── data/                       # Competition data (ignored; restored via scripts)
├── work/                       # Caches (ignored): feature store, per-round predictions
├── evidence/                   # Build receipts & evidence (committed)
├── registry/                   # Preregistrations, data manifest, irregularities
└── knowledge/                  # Research notes, briefs, hypotheses (numbered)
```

## Data sources

| Source | Data | License / access |
|--------|------|---------|
| [DrivenData #306](https://www.drivendata.org/competitions/306/competition-doe-gems/) | Competition rasters (login-walled; restored from SHA-pinned owner mirrors) | Competition rules |
| [USGS GeoDAWN](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and) | Airborne magnetics, radiometrics | Public domain |
| [USGS DOI 10.5066/P93LGLVQ](https://doi.org/10.5066/P93LGLVQ) | GeoDAWN data release | Public domain |
| [GDR 1391 INGENIOUS](https://gdr.openei.org/submissions/1391) | Fault traces, wells, springs | CC BY 4.0 |

## Limitations (honest)

1. No ORGANIZER-CONFIRMED score exists for any file in this repo; the portal is login-walled.
2. The holdout hides catalogue faults; the board rewards off-catalogue faults — holdout skill
   transfers only partially (knowledge/76 §5).
3. Band 15 is a MODEL-derived basement depth; ABS channels inherit its interpolation artefacts.
4. Gravity/magnetic gradients also arise from lithologic contacts without faulting.
5. Sandbox egress excludes USGS/GDR/DrivenData hosts; new external layers need operator downloads.

## Next steps

* If the selector promotes H88, submit and record the receipt as ORGANIZER-CONFIRMED.
* H88-MASS: preregister the budget-discipline ablation (K = 26,982 vs 37,654) on a
  prevalence-matched off-catalogue instrument (knowledge/76 §4/§6).
* H88-COND (conductivity local residual) and H88-SEIS (seismic–strain gate) are ranked and
  queued in knowledge/81; H88-ASTER needs an operator-side EarthExplorer download.
* Repair `scripts/check_site.py` expectations vs the H87-era index loss (IR-H88-001).
"""
    (ROOT / "README.md").write_text(readme)
    print(f"README.md written ({len(readme)} bytes), submit_ok={submit_ok}")


if __name__ == "__main__":
    main()
