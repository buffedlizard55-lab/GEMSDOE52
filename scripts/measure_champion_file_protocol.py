#!/usr/bin/env python3
"""Score shipped rasters *verbatim* on the shared hide-and-recover instrument (file protocol).

The arm protocol used by the round runners places a per-fold top-k quota inside each fold's fair
region.  A shipped raster is a different object: one global emission.  This script measures what the
shared evaluator says about the files themselves -- including the owner-reported 0.2778 champion --
so no page can confuse "arm DTI" with "file DTI", and so the file protocol's blind spot is measured
rather than assumed.

Writes evidence/h88_champion_file_protocol.json.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_h83 as h83                                                          # noqa: E402
from gems52 import evaluate_holdout as evaluator                               # noqa: E402

FILES = (
    ("champion h33-2-b2-zeros (owner-reported board 0.2778)", "data/reference/h33-2-b2-zeros.tif"),
    ("H87 shipped raster", "submission/gems52-h87-cotrain-wavelength-thk-37654px-20261010T213656Z.tif"),
    ("H88 shipped raster", "submission/gems52-h88-cotrain-strat-pmcal-27000px-20261010T222229Z.tif"),
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    reg, store, cat, eligible, folds, va, vb, ring_px, offcat, offcat_b = h83.setup()
    with rasterio.open(ROOT / "data/labels.tif") as ds:
        dist_to_catalogue = ndi.distance_transform_edt(ds.read(1) != 1)

    rows = []
    for label, rel in FILES:
        path = ROOT / rel
        with rasterio.open(path) as ds:
            a = ds.read(1).astype(np.float32)
        terms = np.zeros(4)
        per_fold = []
        for fold in folds:
            res, t = evaluator.evaluate(a, fold, eligible, block_side=200)
            terms += t.sum(axis=0)
            per_fold.append(dict(fold=int(fold["receipt"]["fold"]), dti=float(res["dti"]),
                                 tpw=float(t[:, 0].sum()), fpw=float(t[:, 1].sum()),
                                 fnw=float(t[:, 2].sum()), n_truth=float(t[:, 3].sum())))
        rr, cc = np.nonzero(a > 0)
        pts = np.c_[rr, cc].astype(np.float64)
        nn = cKDTree(pts).query(pts, k=2)[0][:, 1]
        dc = dist_to_catalogue[rr, cc]
        rows.append(dict(
            label=label, path=rel, sha256=sha256(path), bytes=path.stat().st_size,
            n_dots=int(len(pts)),
            min_nearest_neighbour_px=float(nn.min()), median_nearest_neighbour_px=float(np.median(nn)),
            dots_within_3px_of_another=int((nn < 3).sum()),
            catalogue_distance_px=dict(min=float(dc.min()), p10=float(np.percentile(dc, 10)),
                                       median=float(np.median(dc)), p90=float(np.percentile(dc, 90))),
            pooled_dti=float(evaluator.from_terms(terms)),
            per_fold=per_fold,
            pooled_terms=dict(tpw=float(terms[0]), fpw=float(terms[1]), fnw=float(terms[2]),
                              n_truth=float(terms[3])),
        ))
        print(f"{label:52s} pooled DTI {rows[-1]['pooled_dti']:.6f}  "
              f"T={terms[0]:.1f}  S={terms[1]:.1f}  |G|={terms[3]:.1f}", flush=True)

    out = dict(
        stage="file_protocol",
        round="H88",
        finished_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        evaluator=evaluator.VERSION,
        instrument="gems52.evaluate_holdout.evaluate(file_verbatim, fold, eligible) pooled over the "
                   "four label-blind quadrant folds; predictions on visible-catalogue pixels are zeroed",
        implementation_hashes=evaluator.implementation_hashes(),
        note=("File protocol, not the arm protocol: nothing is re-placed per fold. On this instrument the "
              "owner-reported 0.2778 champion raster scores ~0.0066 -- the same as a fresh 37,654-dot "
              "catalogue-flank emission -- so a file-level DTI near 0.006 carries no evidence against a "
              "candidate, and no page may present it as one. Field/arm numbers keep their own label."),
        files=rows,
    )
    p = ROOT / "evidence/h88_champion_file_protocol.json"
    p.write_text(json.dumps(out, indent=1) + "\n")
    print("wrote", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
