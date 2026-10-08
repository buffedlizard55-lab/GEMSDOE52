#!/usr/bin/env python3
"""Uniqueness audit for one candidate GeoTIFF, using the repo's shared lane gate.

Runs ``gems52.gates.lane_uniqueness_report`` in both phases (surface rank, dot proximity) against
every accessible prior raster, and adds decoded-pixel overlap statistics.  Byte-identical copies of
the candidate itself (e.g. the same file published in docs/downloads) are excluded and listed, so a
file is never compared against itself.  Output is a JSON receipt; it is a uniqueness diagnostic, not
a score.  Requires ``data/sample_submission.tif`` (run scripts/restore_data.py --only sample_submission).

    .venv/bin/python scripts/audit_uniqueness.py submission/<file>.tif evidence/<receipt>.json
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52.gates import lane_uniqueness_report  # noqa: E402

SAMPLE = ROOT / "data" / "sample_submission.tif"
PRIOR_GLOBS = ["submission/**/*.tif", "docs/downloads/*.tif", "data/scored/*.tif",
               "data/reference/*.tif", "data/calibration/*.tif"]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(cand_arg: str, out_arg: str) -> int:
    cand_path = (ROOT / cand_arg).resolve()
    out_path = (ROOT / out_arg).resolve()
    with rasterio.open(SAMPLE) as ds:
        footprint = np.isfinite(ds.read(1))
    with rasterio.open(cand_path) as ds:
        cand = ds.read(1).astype(np.float32)
    cand_sha = sha256_file(cand_path)

    priors, excluded = [], []
    for pat in PRIOR_GLOBS:
        for p in sorted(glob.glob(str(ROOT / pat), recursive=True)):
            p = Path(p).resolve()
            if p == cand_path:
                continue
            if sha256_file(p) == cand_sha:
                excluded.append(str(p.relative_to(ROOT)))
                continue
            if str(p) not in [str(q) for q in priors]:
                priors.append(p)
    # Drop duplicate paths that resolve to the same bytes (keeps the first spelling).
    seen_bytes, unique_priors = {}, []
    for p in priors:
        h = sha256_file(p)
        if h in seen_bytes:
            continue
        seen_bytes[h] = str(p.relative_to(ROOT))
        unique_priors.append(p)

    receipt = dict(
        evidence_class="uniqueness diagnostic, not a score",
        candidate=str(cand_path.relative_to(ROOT)), candidate_file_sha256=cand_sha,
        candidate_nonzero=int((cand > 0).sum()), sample=str(SAMPLE.relative_to(ROOT)),
        footprint_px=int(footprint.sum()), priors_offered=len(priors) + len(excluded),
        self_copies_excluded=excluded, priors_after_byte_dedupe=len(unique_priors),
        phases={},
    )
    for phase in ("surface", "dots"):
        rep = lane_uniqueness_report(cand, footprint, [str(p) for p in unique_priors],
                                     sample=str(SAMPLE), phase=phase)
        rows = rep.pop("per_prior")
        rep["top_spearman"] = sorted(
            [dict(path=os.path.relpath(r["path"], ROOT), spearman=round(r["spearman"], 6))
             for r in rows if r.get("spearman") is not None], key=lambda d: -d["spearman"])[:5]
        rep["top_near_3px"] = sorted(
            [dict(path=os.path.relpath(r["path"], ROOT), near_3px_fraction=round(r["near_3px_fraction"], 6))
             for r in rows if r.get("near_3px_fraction") is not None],
            key=lambda d: -d["near_3px_fraction"])[:5]
        rep["offenders"] = [os.path.relpath(r["path"], ROOT) for r in rows
                            if r.get("rank_duplicate") or r.get("near_duplicate") or r.get("identical")]
        receipt["phases"][phase] = rep

    # Decoded-pixel overlap (binary support > 0) against every same-grid prior.
    support = cand > 0
    overlaps = []
    union = np.zeros_like(support)
    for p in unique_priors:
        with rasterio.open(p) as ds:
            if ds.count != 1 or ds.shape != cand.shape:
                continue
            a = np.nan_to_num(ds.read(1), nan=0.0) > 0
        inter = int((a & support).sum())
        uni = int((a | support).sum())
        overlaps.append(dict(path=str(p.relative_to(ROOT)), prior_support=int(a.sum()),
                             intersection=inter, jaccard=round(inter / max(uni, 1), 6),
                             share_of_candidate_in_prior=round(inter / max(int(support.sum()), 1), 6)))
        union |= a
    overlaps.sort(key=lambda d: -d["jaccard"])
    receipt["max_jaccard"] = overlaps[0]["jaccard"] if overlaps else None
    receipt["max_jaccard_prior"] = overlaps[0]["path"] if overlaps else None
    receipt["candidate_px_inside_any_prior_support"] = int((support & union).sum())
    receipt["share_of_candidate_px_inside_any_prior_support"] = round(
        float((support & union).sum()) / max(int(support.sum()), 1), 6)
    receipt["top_overlaps"] = overlaps[:5]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: receipt[k] for k in ["candidate", "priors_after_byte_dedupe",
                                              "max_jaccard", "share_of_candidate_px_inside_any_prior_support"]}, indent=1))
    for ph in ("surface", "dots"):
        r = receipt["phases"][ph]
        print(ph, "max_spearman", r["max_spearman"], "max_near_3px", r["max_near_3px_fraction"],
              "ok", r["ok"], "offenders", len(r["offenders"]))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
