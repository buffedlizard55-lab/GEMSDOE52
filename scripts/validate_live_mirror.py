#!/usr/bin/env python3
"""Validate the live-mirror (LM) holdout instrument against the group's live-scored record.

An instrument may only be used to rank emission rules if it reproduces every known live ordering.
Run:  PYTHONPATH=src python3 scripts/validate_live_mirror.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from gems52.holdout import read_binary
from gems52.live_mirror import evaluate_live_mirror, load_live_mirror_context, validate_live_mirror
from gems52.paths import data_dir, evidence_dir


def main() -> int:
    ddir = data_dir()
    ev = evidence_dir()
    ev.mkdir(parents=True, exist_ok=True)

    import rasterio
    with rasterio.open(ddir / "sample_submission.tif") as ds:
        foot = np.isfinite(ds.read(1))
    labels = read_binary(ddir / "labels.tif") & foot

    ctx = load_live_mirror_context(ddir, foot, labels)
    print(f"[LM] SGMC off-catalogue truth pixels (>300 m from catalogue): {int(ctx.sgmc_off.sum()):,}")
    for c in ctx.cells:
        print(f"     {c.key}: {c.n_truth:,} truth px in the eroded domain")

    report = validate_live_mirror(ddir, ctx)
    print(f"\n[LM] instrument reproduced {report['n_orderings_reproduced']}/{report['n_orderings_checked']} "
          f"known live orderings -> all_reproduced={report['all_reproduced']}")
    for c in report["orderings"]:
        print(f"     {'PASS' if c['reproduced'] else 'FAIL'}  {c['ordering']:34s} live {c['live']:24s} "
              f"LM {c['lm']}")
    (ev / "live_mirror_validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {ev / 'live_mirror_validation.json'}")

    # --- the catalogue-flank exclusion policy under LM -------------------------------
    d28 = read_binary(ddir / "scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif")
    print("\n[LM] catalogue-flank exclusion sweep on the 0.2600 emission (D2.8, 44,090 dots):")
    sweep = {}
    for b in (None, 1, 2, 3):
        r = evaluate_live_mirror(d28, ctx, f"D2.8-flank{'-' if b is None else b}", flank_charge_px=b)
        sweep[str(b)] = r
        print(f"     B={str(b):>4}: {r['emitted_pixels']:6,d} dots  LM={r['lm_mean']:.6f}  "
              f"min_fold={r['lm_min_fold']:.6f}")
    (ev / "live_mirror_flank_sweep.json").write_text(json.dumps(sweep, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
