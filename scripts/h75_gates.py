#!/usr/bin/env python3
"""H75 lane gates (surface + dots) and uniqueness against the full census registry + local scored files."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
import numpy as np
from build_h61_submission import prior_paths
from gems52 import gates, structural
store = structural.FeatureStore(ROOT / "work/r2/features")
elig = store.valid
priors, meta = prior_paths(ROOT / "work/h61/prior_fetch_receipt.json", ("submission",))
priors = [p for p in priors if p.exists() and "h75" not in p.name]
dots = np.load(ROOT / "work/h75/dots.npy").astype(np.float32)
surf = np.load(ROOT / "work/h75/surface.npy")
S = ROOT / "data/sample_submission.tif"
out = dict(registry=meta, n_priors=len(priors))
out["lane_surface"] = gates.lane_report(surf, elig, priors, sample=S, phase="surface")
out["lane_dots"] = gates.lane_report(dots, elig, priors, sample=S, phase="dots")
out["uniqueness"] = gates.uniqueness_report(dots, priors)
(ROOT / "evidence/h75_gates.json").write_text(json.dumps(out, indent=1, default=float))
for k in ("lane_surface", "lane_dots"):
    r = out[k]; print(k, json.dumps({x: r[x] for x in r if x in ("literal", "policy")}, default=float)[:900])
u = out["uniqueness"]; print({k: v for k, v in u.items() if not isinstance(v, list)})
