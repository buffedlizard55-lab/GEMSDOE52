#!/usr/bin/env python3
"""H61 concurrent-closure check: re-run the lane gate against rasters merged after the census.

The frozen 526-blob census and the local ``submission/`` tree were materialised before the parallel
rounds R5 and H60D landed on ``main``.  The H61 lane verdict was computed against 545 rasters; this
script re-checks the *unchanged* H61 emission against every aligned raster that the merge added, and
records the result beside the original receipt instead of quietly editing it.  The artefact is not
rebuilt, re-placed or re-tuned here: closure means checking the same bytes against a larger registry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import gates                                    # noqa: E402


def merged_rasters(base: str) -> list[Path]:
    """Every *.tif the merge brought in that is not part of the already-gated set."""
    out = subprocess.run(["git", "diff", "--name-only", "--diff-filter=A", base, "HEAD"],
                         capture_output=True, text=True, cwd=ROOT)
    paths = [ROOT / p for p in out.stdout.split() if p.endswith(".tif")]
    return [p for p in paths if p.exists()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="57c7673", help="commit the H61 branch started from")
    ap.add_argument("--artifact", default="")
    ap.add_argument("--out", default="evidence/h61_concurrent_closure.json")
    args = ap.parse_args()

    art = Path(args.artifact) if args.artifact else sorted((ROOT / "submission").glob("gems52-h61-*.tif"))[-1]
    with rasterio.open(art) as ds:
        cand = ds.read(1).astype(np.float32)
    eligible = np.load(ROOT / "work/r2/features/valid.npy")
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        sub = ref.read(1)
    eligible = eligible & (np.isfinite(sub) & (sub > -1e38))

    # the already-gated set: the frozen census plus whatever submission/ held at census time
    gated = set()
    rec = ROOT / "work/h61/prior_fetch_receipt.json"
    if rec.exists():
        for st in json.loads(rec.read_text())["files"].values():
            gated.add(hashlib.sha256((ROOT / st["dest"]).read_bytes()).hexdigest()
                      if (ROOT / st["dest"]).exists() else "")
    lane = json.loads((ROOT / "evidence/h61_lane_dots.json").read_text())
    gated |= {r.get("decoded_sha256") for r in lane["per_prior"]}

    fresh = []
    cand_decoded = hashlib.sha256(gates.canonical(cand).tobytes()).hexdigest()
    for p in merged_rasters(args.base) + sorted((ROOT / "submission").glob("*.tif")) \
            + sorted((ROOT / "docs/downloads").glob("*.tif")):
        if p.name.startswith("gems52-h61-") or p.name.startswith("h61-") or p == art:
            continue
        try:
            with rasterio.open(p) as ds:
                if ds.count != 1 or ds.shape != cand.shape:
                    continue
                a = gates.canonical(ds.read(1))
        except Exception:                                        # noqa: BLE001
            continue
        dig = hashlib.sha256(a.tobytes()).hexdigest()
        # IR-52-026: a byte-identical copy of the candidate under another basename reports
        # "identical-to-a-prior, novel = 0", which is the one verdict that would stop a legitimate
        # submission.  Exclude by decoded hash, not by name.
        if dig == cand_decoded or dig in gated or any(dig == f["decoded_sha256"] for f in fresh):
            continue
        fresh.append(dict(path=str(p), decoded_sha256=dig, array=a))

    rows = []
    for f in fresh:
        tmp = ROOT / "work/h61/closure" / (f["decoded_sha256"][:16] + ".tif")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        if not tmp.exists():
            with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
                prof = dict(driver="GTiff", height=cand.shape[0], width=cand.shape[1], count=1,
                            dtype="float32", crs=str(ref.crs), transform=ref.transform,
                            tiled=True, blockxsize=256, blockysize=256, compress="deflate")
            with rasterio.open(tmp, "w", **prof) as dst:
                dst.write(f["array"], 1)
        rep = gates.lane_report(cand, eligible, [tmp], sample=ROOT / "data/sample_submission.tif",
                                phase="dots")
        r = rep["per_prior"][0]
        rows.append(dict(source_path=f["path"], decoded_sha256=f["decoded_sha256"],
                         prior_proposals=r.get("prior_proposals"),
                         coverage_3px_of_eligible=r.get("coverage_3px_of_eligible"),
                         universal_coverage_probe=r.get("universal_coverage_probe"),
                         near_3px_fraction=r.get("near_3px_fraction"),
                         excess_over_chance=(r.get("near_3px_fraction") - r.get("coverage_3px_of_eligible"))
                         if r.get("near_3px_fraction") is not None else None,
                         spearman=r.get("spearman"),
                         identical=r.get("identical"),
                         rank_duplicate=r.get("rank_duplicate"), near_duplicate=r.get("near_duplicate")))
        del f["array"]

    verdict = ("DUPLICATE/STOP" if any(r["near_duplicate"] or r["rank_duplicate"] or r["identical"]
                                       for r in rows) else "PASS")
    out = dict(
        generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        instrument="scripts/h61_concurrent_closure.py",
        evidence_class="lane diagnostic on unchanged bytes against a larger registry; not a score",
        artifact=str(art), artifact_sha256=hashlib.sha256(art.read_bytes()).hexdigest(),
        base_commit=args.base,
        original_receipt="evidence/h61_lane_dots.json",
        original_priors_checked=lane["priors_checked"],
        new_decoded_patterns_checked=len(rows),
        rows=rows,
        max_near_3px_fraction=max((r["near_3px_fraction"] for r in rows
                                   if r["near_3px_fraction"] is not None), default=None),
        max_spearman=max((r["spearman"] for r in rows if r["spearman"] is not None), default=None),
        verdict_on_new_rasters=verdict,
        unchanged_artifact=True,
        note=("The H61 emission was not rebuilt, re-placed or re-tuned for this check. A DUPLICATE/STOP "
              "here would add to, not replace, the recorded verdict; a PASS does not overturn the "
              "original lane STOP recorded in evidence/h61_lane_dots.json."))
    dest = ROOT / args.out
    dest.write_text(json.dumps(out, indent=1, allow_nan=False, default=str) + "\n")
    (ROOT / "docs/data/h61_concurrent_closure.json").write_text(dest.read_text())
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))
    for r in rows:
        print("  ", Path(r["source_path"]).name[:56], "cov=%.4f" % r["coverage_3px_of_eligible"],
              "near=%.4f" % (r["near_3px_fraction"] or -1), "rho=%.4f" % (r["spearman"] or 0),
              "probe=", r["universal_coverage_probe"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
