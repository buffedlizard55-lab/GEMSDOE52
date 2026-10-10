#!/usr/bin/env python3
"""H88 -- the geological reasoning row for every A-only candidate in the emitted file.

The standing brief: "Because Phase 2 reviewers verify faults, write the geological reasoning for
every A-only candidate."  An A-only candidate is a pixel where the potential-field view is in its
confident tail and the surface view abstains (``gems52.cotrain.strata`` code 2).  Every emitted dot
that is A-only gets one row: what the structure would be if real, the named non-fault process that
mimics it, and the falsifier that distinguishes them.

Reads the shipped GeoTIFF and the fold predictions; writes ``docs/downloads/h88-a-only-reasoning.csv``
plus a machine-readable twin in ``evidence/``.  Writes nothing else.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
import rasterio as rio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_h61 as base                                                     # noqa: E402
from gems52 import cotrain as CT, grid as GR                               # noqa: E402

OUT = ROOT / "docs/downloads/h88-a-only-reasoning.csv"
EV = ROOT / "evidence/h88_a_only_reasoning.json"

HYPOTHESIS = ("concealed normal fault beneath alluvial cover: potential-field gradient step with no "
              "surface scarp; displacement dies upward into cover")
MIMIC = ("basement lithological step or intrusive margin under cover (no displacement), or an "
         "aeromagnetic flight-line/tie-line artefact in the supplied derivative bands")
FALSIFIER = ("depth-to-basement contour crosses the candidate without a step; no along-strike "
             "continuation beyond one 20 km block; or the feature vanishes in the upward-continued "
             "field (shallow artefact)")

HYPOTHESIS_B = ("surface artefact (road, canal, pipeline, erosion line) or a genuine scarp: the "
                "surface view is confident while the potential-field view abstains")
MIMIC_B = "anthropogenic linear feature, drainage/erosion line, or the edge of a mapped lithology"
FALSIFIER_B = ("ground-truth imagery shows a man-made corridor; or the potential-field view becomes "
               "confident when the 150 m upward-continued TMI replaces the raw field")


def main() -> int:
    reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    shipped = sorted((ROOT / "submission").glob("gems52-h88-*.tif"))
    shipped = [p for p in shipped if "-h88-" in p.name]
    if not shipped:
        raise SystemExit("no shipped H88 GeoTIFF found in submission/")
    tif = shipped[-1]
    with rio.open(tif) as s:
        em = s.read(1)
        tr = s.transform
        crs = s.crs
    log = print
    log(f"reading {tif.name}: {int((em > 0).sum())} emitted pixels")

    # assemble the fold strata + ranks exactly as the emission did (out-of-fold, no leakage)
    shape = em.shape
    ranks = {"pre_A": np.full(shape, np.nan, np.float32), "pre_B": np.full(shape, np.nan, np.float32)}
    strata = np.zeros(shape, np.int8)
    for fold in folds:
        f = fold["fold"]
        allowed = fold["region"] & ~fold["visible"] & (
            __import__("scipy.ndimage", fromlist=["ndimage"]).distance_transform_edt(~fold["visible"]) > ring_px)
        idx = np.flatnonzero(allowed.ravel())
        pre = {}
        for v in ("A", "B"):
            g = base.to_grid(store.flat_idx,
                             np.load(ROOT / "work/h61" / f"pred_pre_{v}_f{f}.npy"), shape)
            r = np.full(shape, np.nan, np.float32)
            r.ravel()[idx] = base.pct_rank(g.ravel()[idx])
            ranks[f"pre_{v}"] = np.where(np.isnan(ranks[f"pre_{v}"]), r, ranks[f"pre_{v}"])
            pre[v] = g
        st = CT.strata(np.nan_to_num(pre["A"], nan=-1.0).ravel(),
                       np.nan_to_num(pre["B"], nan=-1.0).ravel(),
                       eligible, q_conf=0.98, q_abstain_hi=0.60)["mask"]
        strata.ravel()[idx] = st.ravel()[idx]
        del pre

    ys, xs = np.nonzero(em > 0)
    codes = strata[ys, xs]
    ra = ranks["pre_A"][ys, xs]
    rb = ranks["pre_B"][ys, xs]
    east, north = rio.transform.xy(tr, ys, xs)
    counts = {int(c): int((codes == c).sum()) for c in np.unique(codes)}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "easting_epsg32611", "northing_epsg32611", "stratum_code",
                    "stratum", "view_A_rank", "view_B_rank", "hypothesis", "named_non_fault_mimic",
                    "falsifier"])
        for i in range(len(ys)):
            c = int(codes[i])
            name = {0: "silent", 1: "concordant", 2: "A-only", 3: "B-only"}[c]
            if c == 2:
                hyp, mim, fal = HYPOTHESIS, MIMIC, FALSIFIER
            elif c == 3:
                hyp, mim, fal = HYPOTHESIS_B, MIMIC_B, FALSIFIER_B
            elif c == 1:
                hyp, mim, fal = ("both views confident: strongest single candidate", MIMIC, FALSIFIER)
            else:
                hyp, mim, fal = ("emitted outside the disagreement stratum: lowest confidence "
                                 "in this file", MIMIC, FALSIFIER)
            w.writerow([int(ys[i]), int(xs[i]), f"{east[i]:.1f}", f"{north[i]:.1f}", c, name,
                        f"{ra[i]:.4f}", f"{rb[i]:.4f}", hyp, mim, fal])
    payload = dict(file=str(OUT.relative_to(ROOT)), rows=int(len(ys)), stratum_counts=counts,
                   stratum_legend={0: "silent", 1: "concordant", 2: "A-only", 3: "B-only"},
                   q_conf=0.98, abstain_hi=0.60,
                   shipped_tif=tif.name,
                   note=("strata are out-of-fold per the shared splitter; A-only means the "
                         "potential-field view is in its confident tail while the surface view "
                         "abstains - a hypothesis, not a fault"))
    EV.write_text(json.dumps(payload, indent=1) + "\n")
    print(json.dumps(payload, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
