#!/usr/bin/env python3
"""Supplemental uniqueness/lane closure against rasters that reached main AFTER the H95 gates ran.

The gates stage (scripts/run_h95.py gates) checked 675 priors.  While it ran, parallel sessions merged
rounds H88 (other session), H90-H94 into main, adding the rasters listed in ``NEW`` (from
``git diff --name-only --diff-filter=AR 6745d1b 940971b -- '*.tif'``).  This script runs the SAME shared
tools (gems52.gates.uniqueness_report / lane_report, no fork) against exactly those files and appends the
result to evidence/h95_gates.json under ``supplemental_closure_after_merge``.  Idempotent.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import gates  # noqa: E402

G_PATH = ROOT / "evidence/h95_gates.json"
B = json.loads((ROOT / "evidence/h95_build.json").read_text())
SAMPLE = ROOT / "data/sample_submission.tif"
BASE, TIP = "6745d1b", "940971b"
NEW = subprocess.run(["git", "diff", "--name-only", "--diff-filter=AR", BASE, TIP, "--", "*.tif"],
                     cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
priors = [ROOT / p for p in NEW if (ROOT / p).exists()]
with rasterio.open(ROOT / B["path"]) as s:
    pred = s.read(1)
with rasterio.open(SAMPLE) as s:
    dom = np.isfinite(s.read(1))
u = gates.uniqueness_report(pred, priors)
ld = gates.lane_report(pred.astype(np.float32), dom, priors, sample=SAMPLE, phase="dots")
rows = [dict(path=Path(r["path"]).name, jaccard=r.get("jaccard"), identical=r.get("identical"), error=r.get("error"))
        for r in u["per_prior"]]
near = sorted(((x.get("near_3px_fraction") or 0.0, Path(x["path"]).name, x.get("coverage_3px_of_eligible"))
               for x in ld["per_prior"] if "error" not in x), key=lambda t: -t[0])
out = dict(commit_range=f"{BASE}..{TIP}", n_new_rasters=len(priors), identical_to_any=u["identical_to_a_prior"],
           distinct_from_every_comparable=u["distinct_from_every_comparable_prior"],
           max_jaccard=max((r["jaccard"] or 0) for r in rows), per_prior=rows,
           lane_dots_literal=ld["literal"]["verdict"], lane_dots_policy=ld["policy"]["verdict"],
           near_3px_top=near[:5], instrument="gems52.gates (shared, unmodified)")
g = json.loads(G_PATH.read_text())
g["supplemental_closure_after_merge"] = out
G_PATH.write_text(json.dumps(g, indent=1, default=str) + "\n")
print(json.dumps({k: v for k, v in out.items() if k != "per_prior"}, indent=1, default=str))
