#!/usr/bin/env python3
"""H88 review tables for the shipped file (not a score).

1. Not-the-union check. The protocol asks whether the output is merely the union of the two views. We measure
   how much of the shipped dot set lies in the union of each single view's top-K (K = 37,654, no spacing), and
   how much of it lies in the strict stratum S_AB.
2. A-only reasoning table. Every shipped dot is A-confident and B-abstaining by construction. Per-dot prose is not
   produced; dots are grouped into clusters (dilated 3 px, 8-connected) and each cluster gets measured attributes, a
   templated mechanism for its dominant View-A channel, a named non-fault mimic, and an UNREVIEWED status.

Writes: evidence/h88_union_check.json, docs/downloads/h88-a-only-reasoning.csv
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_h88_holdout as H88  # noqa: E402
from gems52 import nodes  # noqa: E402

BUDGET = 37654
SHIPPED = sorted((ROOT / "docs/downloads").glob("gems52-h88-cotrain-strict-AB-37654px-*.tif"))[-1]
WELLS = ROOT / "data/external/gdr_wellspring_in_footprint.csv"
OUT_JSON = ROOT / "evidence/h88_union_check.json"
OUT_CSV = ROOT / "docs/downloads/h88-a-only-reasoning.csv"

GROUPS = {
    "gravity": [5, 11, 18],   # iso_grav_anom_slope, iso_grav_anom_vg, iso_grav_anom_hg
    "magnetic": [3, 9],       # tmi_hg, tmi_vg
    "strain": [4, 7],         # geod_2ndinv, geod_shearrate (the View A strain bands; band 8 is not in View A)
}
MECH = {
    "gravity": ("isostatic-gravity gradient maximum: a lateral density contrast consistent with a fault-bounded basement "
                "block or basement step under alluvial cover"),
    "magnetic": ("magnetic horizontal-gradient / vertical-gradient maximum: a susceptibility contrast consistent with a "
                 "faulted magnetic contact under cover"),
    "strain": ("geodetic strain-rate maximum: a deformation gradient consistent with active slip on a structure "
               "that has no surface scarp"),
}
MIMIC = {
    "gravity": "lithologic density contrast or sediment-thickness change without faulting (intrusive or altered "
               "basement margin, paleo-channel)",
    "magnetic": "dike or intrusive margin, or basement susceptibility contrast without displacement",
    "strain": "GNSS/InSAR velocity-field artefact or regional deformation gradient not tied to a fault",
}


def main() -> None:
    with rasterio.open(H88.LABELS) as ds, rasterio.open(H88.SAMPLE) as ref:
        labels = ds.read(1)
        domain = np.isfinite(ref.read(1))
        transform = ref.transform
    cat = labels == 1
    valid = H88.H87.footprint_all_bands(str(H88.FEATURES)) & domain
    vd = ndi.distance_transform_edt(~cat)
    allowed = valid & ~cat & (vd > 2)

    with rasterio.open(SHIPPED) as src:
        E = src.read(1) > 0
    assert int(E.sum()) == BUDGET, int(E.sum())

    fields, rA, rB, strata, _ = H88.build_fields(valid)
    topA = nodes.top_k_mask(rA, allowed, BUDGET)
    topB = nodes.top_k_mask(rB, allowed, BUDGET)
    U = topA | topB
    S_AB = fields["P_strict_cotrain"] > 1.0       # stratum membership (the +1.0 term)
    inter_A = int((E & topA).sum())
    inter_B = int((E & topB).sum())
    inter_U = int((E & U).sum())
    jacc = inter_U / max(int((E | U).sum()), 1)
    union_check = dict(
        shipped=SHIPPED.name, dots=int(E.sum()),
        share_in_topA=round(inter_A / BUDGET, 6), share_in_topB=round(inter_B / BUDGET, 6),
        share_in_union_topA_topB=round(inter_U / BUDGET, 6), share_in_S_AB=round(int((E & S_AB).sum()) / BUDGET, 6),
        jaccard_vs_union_topA_topB=round(jacc, 6),
        share_of_dots_outside_union=round(1 - inter_U / BUDGET, 6),
        verdict_not_union=bool((1 - inter_U / BUDGET) > 0.5),
        note="share_of_dots_outside_union > 0.5 means the output is not mainly the union of the two single-view top-K sets",
        evidence_class="diagnostic, not a score",
    )
    OUT_JSON.write_text(json.dumps(union_check, indent=2) + "\n")
    print(json.dumps(union_check, indent=2))

    # ---- A-only reasoning table, one row per 3 px cluster --------------------------------------------
    rr = np.arange(-3, 4)
    disk = (rr[:, None] ** 2 + rr[None, :] ** 2) <= 9
    lab, n = ndi.label(ndi.binary_dilation(E, structure=disk), structure=np.ones((3, 3), bool))
    ranks = {}
    with rasterio.open(H88.FEATURES) as src:
        for g, bands in GROUPS.items():
            acc = np.zeros(valid.shape, np.float32)
            for b in bands:
                arr = src.read(b).astype(np.float64)
                arr[~np.isfinite(arr)] = 0.0
                arr[arr < -1e38] = 0.0
                acc += H88.rank01(arr.astype(np.float32), valid)
            ranks[g] = acc / len(bands)
    depth = None
    with rasterio.open(H88.FEATURES) as src:
        depth = src.read(15).astype(np.float64)
    wells = []
    with open(WELLS) as fh:
        for row in csv.DictReader(fh):
            try:
                wells.append((float(row["utm_x"]), float(row["utm_y"])))
            except (ValueError, KeyError):
                continue
    tree = cKDTree(np.array(wells)) if wells else None
    ys, xs = np.nonzero(E)
    dot_ids = lab[ys, xs]
    rows_out = []
    order = np.argsort(dot_ids, kind="stable")
    dot_ids_sorted = dot_ids[order]
    bounds = np.searchsorted(dot_ids_sorted, np.arange(1, n + 1))
    bounds_end = np.searchsorted(dot_ids_sorted, np.arange(1, n + 1), side="right")
    for cid in range(1, n + 1):
        idx = order[bounds[cid - 1]:bounds_end[cid - 1]]
        if idx.size == 0:
            continue
        yy, xx = ys[idx], xs[idx]
        gmeans = {g: float(ranks[g][yy, xx].mean()) for g in GROUPS}
        dom = max(gmeans, key=gmeans.get)
        cx = float(transform.c + transform.a * (xx.mean() + 0.5))
        cy = float(transform.f + transform.e * (yy.mean() + 0.5))
        x0, x1 = float(transform.c + transform.a * xx.min()), float(transform.c + transform.a * (xx.max() + 1))
        y0, y1 = float(transform.f + transform.e * (yy.max() + 1)), float(transform.f + transform.e * yy.min())
        dist_cat_m = float(vd[yy, xx].min() * 100.0)
        well_m = float(tree.query([cx, cy])[0]) if tree is not None else None
        rows_out.append(dict(
            cluster_id=f"H88-C{cid:05d}", n_dots=int(idx.size), centroid_utm_x=round(cx, 1), centroid_utm_y=round(cy, 1),
            bbox_utm=f"{x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f}",
            mean_rank_A=round(float(rA[yy, xx].mean()), 4), mean_rank_B=round(float(rB[yy, xx].mean()), 4),
            dominant_A_group=dom, group_ranks=";".join(f"{g}={gmeans[g]:.3f}" for g in GROUPS),
            min_dist_known_trace_m=round(dist_cat_m, 1), nearest_well_or_spring_m=round(well_m, 1) if well_m is not None else "",
            median_depth_to_basement_raw=round(float(np.median(depth[yy, xx])), 2),
            mechanism_templated=MECH[dom], named_non_fault_mimic=MIMIC[dom],
            status="UNREVIEWED: templated mechanism from measured ranks; requires geologist review before any claim",
        ))
    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        w.writerows(rows_out)
    summary = dict(clusters=len(rows_out), dots=int(E.sum()),
                   dominant_counts={g: sum(1 for r in rows_out if r["dominant_A_group"] == g) for g in GROUPS},
                   min_dist_known_trace_m_min=min(r["min_dist_known_trace_m"] for r in rows_out))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
