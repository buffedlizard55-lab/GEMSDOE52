#!/usr/bin/env python3
"""Audit every shipped artifact in ``docs/downloads/`` against the real competition rasters.

Produces the table in ``knowledge/02_the_ceiling_and_the_instrument.md`` §7 and the
``docs/research/shipped_audit.json`` receipt.  Three independent things are measured:

1. **Portal legality** — CRS, grid, dtype, band count, and every finite value in ``[0, 1]``.
   This is the check that answers the DrivenData error *"Predicted values must be in range
   [0, 1]"*; it is run on the bytes on disk, not on the array that produced them.
2. **Internal consistency** — how many emitted pixels sit *off* the belief field's own support.
   Mass outside a belief field's support cannot earn credit from any truth consistent with that
   belief, so this is a truth-frame-free defect measure.
3. **Catalogue-proxy accounting** — `T`, `F`, credit per unit mass and DTI against
   ``labels.tif``.  This frame is *leak-contaminated* (the organizers mask known USGS/INGENIOUS
   pixels out of scoring), so it screens artifacts against each other and is **never** a score.

Requires ``data/raw/{sample_submission,labels}.tif``; run ``bash scripts/fetch_mirrors.sh`` first.
"""
from __future__ import annotations

import hashlib
import json
import time
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import metric as M  # noqa: E402

TPL = ROOT / "data" / "raw" / "sample_submission.tif"
LAB = ROOT / "data" / "raw" / "labels.tif"
DOWN = ROOT / "docs" / "downloads"

# belief fields an artifact can be packed from, for the off-support measure
FIELDS = {
    "h19_5": ROOT / "data" / "raw" / "h19_5.tif",
}


def main() -> int:
    if not TPL.exists() or not LAB.exists():
        print(f"missing {TPL} or {LAB}; run: bash scripts/fetch_mirrors.sh", file=sys.stderr)
        return 2

    with rasterio.open(TPL) as s:
        tpl = s.read(1)
        tpl_prof = dict(crs=str(s.crs), transform=list(s.transform)[:6],
                        shape=[s.height, s.width], res=list(s.res), dtype=s.dtypes[0])
    fp = np.isfinite(tpl)
    with rasterio.open(LAB) as s:
        cat = (s.read(1) == 1) & fp

    fields = {}
    for k, p in FIELDS.items():
        if p.exists():
            with rasterio.open(p) as s:
                a = s.read(1)
            fields[k] = np.where(np.isfinite(a), a, 0.0) > 0

    rows = []
    for tif in sorted(DOWN.glob("*.tif")):
        with rasterio.open(tif) as s:
            prof = dict(crs=str(s.crs), transform=list(s.transform)[:6],
                        shape=[s.height, s.width], res=list(s.res),
                        dtype=s.dtypes[0], count=s.count, nodata=s.nodata)
            a = s.read(1)
        finite = np.isfinite(a)
        vals = a[finite]
        legal = (
            prof["crs"] == tpl_prof["crs"]
            and prof["transform"] == tpl_prof["transform"]
            and prof["shape"] == tpl_prof["shape"]
            and prof["res"] == tpl_prof["res"]
            and prof["dtype"] == "float32"
            and prof["count"] == 1
            and vals.size > 0
            and float(vals.min()) >= 0.0
            and float(vals.max()) <= 1.0
        )
        pos = a > 0
        c = M.components(np.where(finite, a, 0.0), cat)
        s_dti = M.dti(c["TP_w"], c["FP_w"], c["FN_w"])
        row = {
            "file": tif.name,
            "bytes": tif.stat().st_size,
            "sha256": hashlib.sha256(tif.read_bytes()).hexdigest(),
            "profile": prof,
            "portal_legal": bool(legal),
            "finite_cells": int(finite.sum()),
            "nan_cells": int((~finite).sum()),
            "min": float(vals.min()) if vals.size else None,
            "max": float(vals.max()) if vals.size else None,
            "range_violations": int(((vals < 0) | (vals > 1)).sum()),
            "positive_px": int(pos.sum()),
            "total_mass": float(vals.sum()),
        }
        for fname, f in fields.items():
            row[f"off_{fname}_px"] = int((pos & ~f).sum())
            row[f"off_{fname}_frac"] = float((pos & ~f).sum()) / max(1, int(pos.sum()))
        row.update({
            "catalogue_proxy_T": c["TP_w"],
            "catalogue_proxy_F": c["FP_w"],
            "credit_per_unit_mass": c["credit_per_unit_mass"],
            "catalogue_proxy_DTI": s_dti,
            "dots_on_catalogue": int((pos & cat).sum()),
        })
        rows.append(row)

    out = {
        "generated_by": "scripts/audit_shipped.py",
        "template": tpl_prof,
        "footprint_px": int(fp.sum()),
        "catalogue_px": int(cat.sum()),
        "evidence_class": ("catalogue-proxy columns are [MEASURED, leak-contaminated]: the "
                           "organizers mask known USGS/INGENIOUS pixels out of scoring, so this "
                           "frame screens artifacts against each other and is never a score"),
        "artifacts": rows,
    }
    (ROOT / "docs" / "research").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs" / "research" / "shipped_audit.json").write_text(json.dumps(out, indent=1) + "\n")

    # ---- refresh the site's manifest so it lists EVERY artifact on disk, not only the ones the
    # pipeline's own step 6 wrote (the H33 pair was emitted by scripts/run_h33_validation.py).
    sub = json.loads((ROOT / "registry" / "submission_build.json").read_text()) \
        if (ROOT / "registry" / "submission_build.json").exists() else {}
    primary = (sub.get("file") or {}).get("path", "")
    bundles = []
    for r in rows:
        fn = r["file"]
        stem = fn[:-4] if fn.endswith(".tif") else fn
        role = "PRIMARY" if fn == Path(primary).name else "AVAILABLE"
        if fn == Path((sub.get("anchor") or {}).get("path", "")).name:
            role = "ANCHOR (already-scored base)"
        bundles.append({
            "role": role,
            "file": fn,
            "sha256": r["sha256"],
            "bytes": r["bytes"],
            "emitted_px": r["positive_px"],
            "portal_legal": bool(r["portal_legal"]),
            "finite_cells": r["finite_cells"],
            "range_violations": r["range_violations"],
            "nan_cells": r["nan_cells"],
            "min": r["min"], "max": r["max"],
            "nodata": r["profile"]["nodata"],
            "crs": r["profile"]["crs"],
            "dtype": r["profile"]["dtype"],
            "credit_per_unit_mass": r["credit_per_unit_mass"],
            "catalogue_proxy_DTI": r["catalogue_proxy_DTI"],
            "dots_on_catalogue": r["dots_on_catalogue"],
            "receipt": f"downloads/{stem}-audit.json" if (ROOT / "docs" / "downloads" / f"{stem}-audit.json").exists() else None,
        })
    man = {"generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "generated_by": "scripts/audit_shipped.py (refreshed from the files on disk)",
           "validator_range_fix_verified": all(r["range_violations"] == 0 for r in rows),
           "portal_illegal": [r["file"] for r in rows if not r["portal_legal"]],
           "primary": sub.get("name"),
           "note": sub.get("note"),
           "submissions": bundles}
    (ROOT / "docs" / "downloads" / "submissions_manifest.json").write_text(
        json.dumps(man, indent=2) + "\n", encoding="utf-8")
    (ROOT / "evidence" / "submissions_manifest.json").write_text(
        json.dumps(man, indent=2) + "\n", encoding="utf-8")

    hdr = (f"{'artifact':52s} {'dots':>7} {'off-field':>10} {'credit/mass':>11} "
           f"{'proxyDTI':>11}  legal")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        off = r.get("off_h19_5_px", 0)
        print(f"{r['file'][:52]:52s} {r['positive_px']:>7} {off:>10} "
              f"{r['credit_per_unit_mass']:>11.4f} {r['catalogue_proxy_DTI']:>11.7f}  "
              f"{'yes' if r['portal_legal'] else 'NO'}")
    print()
    bad = [r["file"] for r in rows if not r["portal_legal"]]
    print(f"portal-illegal artifacts: {bad if bad else 'none'}")
    print(f"wrote docs/research/shipped_audit.json")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
