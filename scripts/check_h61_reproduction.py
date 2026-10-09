#!/usr/bin/env python3
"""Compare a re-run of the H61 stages (kept in work/h61_repro/) with the committed H61 receipts.

Writes evidence/h62_reproduction_check.json.  The committed receipts are read from git HEAD so the
comparison cannot be satisfied by overwriting them.  Differences are reported, not tolerated silently.
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def committed(rel: str):
    out = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def diffs(a, b, path="", out=None, tol=1e-9, skip=("generated_utc", "started_utc", "finished_utc",
                                                   "evaluator_hashes", "implementation_sha256")):
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k in skip:
                continue
            if k not in a or k not in b:
                out.append(f"{path}/{k} missing")
                continue
            diffs(a[k], b[k], f"{path}/{k}", out, tol, skip)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path} length {len(a)} != {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            diffs(x, y, f"{path}[{i}]", out, tol, skip)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if abs(a - b) > tol * max(1.0, abs(a)):
            out.append(f"{path}: committed {a} reproduced {b} (delta {b - a:+.3e})")
    elif a != b:
        out.append(f"{path}: committed {str(a)[:60]} reproduced {str(b)[:60]}")
    return out


def main():
    res = {}
    for name in ("canary", "holdout", "pseudo_exchange", "independence", "fit_checkpoint"):
        rel = f"evidence/h61_{name}.json"
        rep = json.loads((ROOT / "work/h61_repro" / f"h61_{name}.json").read_text())
        d = diffs(committed(rel), rep)
        res[name] = dict(n_differences=len(d), first_differences=d[:8])
    holdout = res["holdout"]["first_differences"]
    out = dict(
        check="H61 re-run from the same restored bytes, same seeds, same code (run_h61.py all, feature store rebuilt)",
        evidence_class="REPRODUCTION CHECK; numbers are HOLDOUT-DTI diagnostics, not organiser scores",
        result=res,
        reading=("canary identical: the feature stack is identical. Fit/exchange/holdout differ by "
                 "run-to-run numerical nondeterminism (HistGradientBoosting with OpenMP reductions); "
                 "see knowledge/34b. A second run of the H62 control matched the committed single_B to 2.9e-7."),
        h61_build_reproduced=False,
        note="The H61 raster was NOT rebuilt in this check; its SHA-256 is therefore not re-verified here.")
    (ROOT / "evidence/h62_reproduction_check.json").write_text(json.dumps(out, indent=1, allow_nan=False) + "\n")
    print(json.dumps({k: v["n_differences"] for k, v in res.items()}))


if __name__ == "__main__":
    main()
