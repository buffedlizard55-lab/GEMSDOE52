#!/usr/bin/env python3
"""Probe the shipped artifacts on the blocked holdout: what is the bar a new candidate must clear?

Reads only hash-pinned bytes (docs/downloads/*.tif are committed deliverables) and prints the
three instrument read-outs used everywhere in this repository:

  catalogue_hidden_mean          4 quadrants x 2 draws, 20% of catalogue components hidden
  sgmc_prevalence_calibrated_dti off-catalogue truth (state geological map faults), calibrated
  drift_corrected_holdout_mean   0.65 * debiased catalogue-hidden + 0.35 * SGMC-calibrated

Usage:  PYTHONPATH=src python3 scripts/h33_probe.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from gems52.holdout import evaluate_candidate_holdout, load_holdout_context, read_binary  # noqa: E402
from gems52.paths import data_dir, docs_dir  # noqa: E402

ARTIFACTS = [
    ("H19-5-solid-121131", "scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif"),
    ("D1.5-thinned-60069", "scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif"),
    ("D2.8-thinned-44090", "scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif"),
    ("GEMS32-CV-heatfield-44090", "gems52-heatfield-44090-cv-supconfined-zeros.tif"),
    ("GEMS32-lazygreedy-maxcov-44090", "gems52-lazygreedy-maxcov-44090-supconfined-zeros.tif"),
    ("GEMS32-H32-D-46090", "gemsdoe32-h32d-submodular-multipysics-46090-20261004T183200Z-4de30601-zeros.tif"),
    ("GEMS32-H32-D-Eq44090", "gemsdoe32-h32d-equalbudget-44090-20261004T183200Z-350cdc3f-zeros.tif"),
    ("GEMS32-H32-A-46090", "gemsdoe32-h32a-dip-projected-step-46090-20261004T183200Z-838fcd84-zeros.tif"),
    ("GEMS32-H32-C-45890", "gemsdoe32-h32c-mt-claycap-breach-45890-20261004T183200Z-a5963d0a-zeros.tif"),
]


def main() -> int:
    ddir = data_dir()
    dl = docs_dir() / "downloads"
    ctx = load_holdout_context(ddir)
    rows = []
    print(f"{'artifact':34s} {'px':>7s} {'oncat':>6s} {'cat_hid':>9s} {'sgmc_cal':>9s} {'drift':>9s} {'drift_std':>9s}")
    for name, rel in ARTIFACTS:
        p = ddir / rel
        if not p.exists():
            p = dl / Path(rel).name
        if not p.exists():
            print(f"{name:34s}   MISSING {p}")
            continue
        m = read_binary(p)
        ev = evaluate_candidate_holdout(m, ctx, name)
        rows.append({k: v for k, v in ev.items() if not isinstance(v, dict)} | {"file": str(p.name)})
        print(f"{name:34s} {ev['emitted_pixels']:7d} {ev['on_catalogue_pixels']:6d} "
              f"{ev['catalogue_hidden_mean']:9.5f} {ev['sgmc_prevalence_calibrated_dti']:9.5f} "
              f"{ev['drift_corrected_holdout_mean']:9.5f} {ev['drift_corrected_holdout_std']:9.5f}")
    out = ROOT / "evidence" / "h33_probe_controls.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nwrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
