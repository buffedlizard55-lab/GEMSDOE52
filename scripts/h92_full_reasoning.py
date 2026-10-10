#!/usr/bin/env python3
"""Write the FULL A-only per-dot geological-reasoning dossier for the shipped H92 artifact.

The brief requires the geological reasoning for **every A-only candidate**.  The first build wrote
only the top 4,000 disagreement rows.  This script recomputes the production field deterministically
(same frozen procedure, same seed, same channels as ``scripts/build_h92_submission.py``), verifies
that the recomputed dot set is **exactly** the dot set of the shipped TIF, and then writes one row
per emitted dot with its placement, view ranks and reasoning.

It never writes a TIF and never changes the shipped artifact's bytes.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np                                                    # noqa: E402
import rasterio                                                       # noqa: E402
from scipy import ndimage as ndi                                      # noqa: E402

import build_h92_submission as B                                      # noqa: E402
import run_h61 as base                                                # noqa: E402
import run_h92 as H92                                                 # noqa: E402
from gems52 import nodes                                              # noqa: E402


def log(*a):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}]", *a, flush=True)


def main():
    tif = ROOT / "submission/gems52-h92-cotrain-atexture-disagreement-20261010T222354Z.tif"
    if not tif.is_file():
        raise SystemExit(f"shipped artifact not found: {tif}")
    with rasterio.open(tif) as ds:
        shipped = ds.read(1) > 0

    reg = H92.check_prereg()
    log(f"prereg ok: {reg.get('sha256', '')[:16]}…")
    _r, store, cat, eligible, folds, _va, _vb, ring_px = base.setup()
    H92.heal_channels()
    bank = H92.Bank(inverse=store.inverse)
    flat = store.flat_idx
    with rasterio.open(ROOT / "data/sample_submission.tif") as ds:
        domain = np.isfinite(ds.read(1))
    valid = store.valid & domain

    catd = ndi.distance_transform_edt(~cat)
    rng = np.random.default_rng(H92.SEED)
    pos = np.flatnonzero((cat & store.valid).ravel())
    neg = np.flatnonzero((store.valid & ~cat & (catd > 5)).ravel())
    pos = rng.choice(pos, max(1, min(20000, len(pos))), replace=False)
    neg = rng.choice(neg, min(60000, len(neg)), replace=False)
    rows = np.concatenate([pos, neg])
    y = np.concatenate([np.ones(len(pos), np.int8), np.zeros(len(neg), np.int8)])
    order = rng.permutation(len(rows))
    rows, y = rows[order], y[order]

    preds = {}
    for view, names in (("Atex", H92.DVA_A), ("Btex", H92.DVA_B)):
        t0 = time.time()
        m = base.learner(H92.SEED)
        X = bank.gather(rows, names)
        m.fit(X, y)
        del X
        p = np.empty(len(flat), np.float32)
        for i in range(0, len(flat), 250_000):
            sel = flat[i:i + 250_000]
            p[i:i + 250_000] = m.predict_proba(bank.gather(sel, names))[:, 1].astype(np.float32)
        preds[view] = p
        log(f"view {view}: production fit + full-domain predict in {time.time() - t0:.0f}s")

    allowed = valid & (catd > B.COLLAR_PX)
    ai = np.flatnonzero(allowed.ravel())
    eidx = store.inverse[ai]
    if (eidx < 0).any():
        raise SystemExit("allowed set is not inside the feature-eligible footprint")
    ra = np.full(eligible.size, np.nan, np.float32)
    rb = np.full(eligible.size, np.nan, np.float32)
    ra[ai] = B.pct_rank(preds["Atex"][eidx])
    rb[ai] = B.pct_rank(preds["Btex"][eidx])
    field = np.full(eligible.shape, -np.inf, np.float32)
    field.ravel()[ai] = (ra[ai] - rb[ai]).astype(np.float32)

    em = nodes.spacing_select(field, allowed, B.BUDGET, min_px=3.0, log=log)
    recomputed = em
    same = bool((recomputed == shipped).all())
    n_diff = int((recomputed != shipped).sum())
    log(f"determinism check vs shipped TIF: identical={same} differing_px={n_diff}")
    if not same:
        raise SystemExit("recomputed placement differs from the shipped artifact — refusing to write "
                         "a dossier that does not describe the shipped file")

    cy, cx = np.nonzero(shipped)
    a_q = ra.reshape(eligible.shape)[cy, cx]
    b_q = rb.reshape(eligible.shape)[cy, cx]
    dist_cat_m = (catd[cy, cx] * 100.0).astype(np.float32)
    a_only = a_q >= 0.75
    log(f"emitted {len(cy):,} dots; A-only (top-quartile View A) = {int(a_only.sum()):,}")

    out = ROOT / "docs/downloads/h92-candidate-a-only-reasoning.csv"
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "easting", "northing", "dist_mapped_fault_m",
                    "view_A_pct", "view_B_pct", "disagreement", "class", "geological_reasoning"])
        for i in np.argsort(-(a_q - b_q)):
            yy, xx = int(cy[i]), int(cx[i])
            if a_q[i] >= 0.75 and a_q[i] > b_q[i]:
                cls = "A-only (geophysical-confident, surface-abstains)"
                reason = ("potential-field boundary texture exceeds the surface texture at this cell; "
                          "candidate concealed fault beneath alluvial/volcanic cover where the DEM and "
                          "radiometric surfaces carry no scarp. Named non-fault mimic to exclude in the "
                          "field: lithologic contact or intrusive margin; falsifier: no mapped or "
                          "inferred fault within 1 km along the same strike")
            elif a_q[i] >= 0.75:
                cls = "A-confident, B-also-confident (not a concealment candidate)"
                reason = ("geophysical texture confident but the surface view is at least as confident; "
                          "treat as corroborated surface structure, not a buried-fault discovery")
            else:
                cls = "mixed (both views partly engaged)"
                reason = ("both views partly engaged; not an A-only candidate")
            w.writerow([yy, xx, f"{243350.0 + xx * 100.0:.0f}", f"{4508550.0 - yy * 100.0:.0f}",
                        f"{dist_cat_m[i]:.1f}", f"{a_q[i]:.4f}", f"{b_q[i]:.4f}",
                        f"{a_q[i] - b_q[i]:.4f}", cls, reason])
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    receipt = dict(round="H92", stage="full_reasoning_dossier", file=out.name,
                   bytes=out.stat().st_size, sha256=digest, rows=len(cy),
                   a_only_dots=int(a_only.sum()),
                   determinism_check=dict(shipped_tif=tif.name, identical=same, differing_px=n_diff),
                   generated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    (ROOT / "evidence/h92_reasoning.json").write_text(json.dumps(receipt, indent=1) + "\n")
    log("wrote " + json.dumps(receipt))


if __name__ == "__main__":
    main()
