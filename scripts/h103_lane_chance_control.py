"""H103 dot-lane chance control: same-count random dots vs the H103 dots on the four non-probe rasters
that drove the literal dots DUPLICATE. Writes evidence/h103_lane_chance_control.json."""
import json, sys
from pathlib import Path
ROOT0 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT0 / "scripts")); sys.path.insert(0, str(ROOT0 / "src"))
import numpy as np
import run_h103 as R
from gems52 import gates
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
_r, store, cat, eligible, folds, va, vb, ring_px = R.base.setup()
full, meta = R.h84.full_registry()
keys = ["gems-cleanup-a-20260928T195952Z-curv_scarp", "13gems-composite-20260929T183221Z.tif", "13gems-composite-plus-20260929T183249Z.tif", "13gems_20261001_r14-union-tips10-lat6"]
import os
rec = json.load(open(ROOT / "work/h61/prior_fetch_receipt.json"))["files"]
def orig(p):
    b = os.path.basename(str(p)).replace(".tif", "")
    return (rec.get(b) or {}).get("path", "") or str(p)
sub = [p for p in full if any(k in orig(p) for k in keys)]
print("matched", len(sub), [str(p)[-60:] for p in sub], flush=True)
pool = np.load(R.WORK / "pool.npy")
dots = np.load(R.WORK / "dots.npy").astype(bool)
rng = np.random.default_rng(97)
ys = np.flatnonzero(pool.ravel())
rnd = np.zeros(pool.shape, np.float32)
rnd.ravel()[rng.choice(ys, size=int(dots.sum()), replace=False)] = 1.0
out = {}
for name, grid in (("h103_dots", dots.astype(np.float32)), ("random_same_count", rnd)):
    rep = gates.lane_report(grid, eligible, sub, sample=R.SAMPLE, phase="dots")
    out[name] = {k: rep["literal"][k] for k in ("max_near_3px_fraction", "verdict")}
    out[name]["per_prior_near"] = {Path(x["path"]).name: round(x["near_3px_fraction"], 4) for x in rep["per_prior"]}
    print(name, out[name], flush=True)
json.dump(dict(stage="chance_control", note="same 3px-disk near rule as gates.lane_report, applied to the four non-probe rasters that drove the literal dots DUPLICATE; random comparator = same count, uniform over emission pool, seed 97; restricted to these 4 rasters only, not a full re-run", result=out), open(ROOT / "evidence/h103_lane_chance_control.json", "w"), indent=1, default=str)
print("WROTE", flush=True)
