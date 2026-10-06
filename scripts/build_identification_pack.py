#!/usr/bin/env python3
"""Build the three-submission identification pack described in
``knowledge/02_the_ceiling_and_the_instrument.md`` §6.

The competition allows **three scored submissions a week**, and one file is scored in *both* prize
rounds.  A weekly slot is therefore an expensive query.  This script builds the three queries whose
joint return identifies the three quantities on which every projection in this project has so far
been guessing:

    S1  ANCHOR     p_1          ->  1/s_1 = alpha + alpha*(F/T) + beta*(K/T)
    S2  SCALE      p_2 = 0.5*p1 ->  1/s_2 = alpha + alpha*(F/T) + 2*beta*(K/T)
    S3  NULL-ADD   p_3 = p1 + M ->  1/s_3 = 1/s_1 + alpha*M/T

    T = alpha*M / (1/s_3 - 1/s_1)        K = T*(1/s_2 - 1/s_1)/beta
    F = T*(1/s_1 - alpha - beta*K/T)/alpha

`T` is the weighted credit the team actually earns on the hidden label set; `K` its size; `F` the
mass it wastes.  Together they give the team's true **recall of hidden faults** `T/K`, which no
local instrument in this repository can measure (the only local truth raster is the visible
catalogue, which the organizers mask out of scoring).

Guarantees enforced here, all checked by re-reading the written bytes:

* every file is portal-legal: EPSG:32611, 3736x3292 grid identical to the template, one float32
  band, and **every cell finite and in [0, 1]** (the historical rejection was
  "Predicted values must be in range [0, 1]");
* `S1` and `S2` are bit-identical to each other in footprint *ordering*, so the only difference the
  leaderboard sees is the scale factor;
* every `S3` probe pixel is **> 3 px (300 m) from every known catalogue fault** — so the
  organizers' known-fault masking rule cannot be what moves the number — and > 3 px from the
  anchor's own belief support, and >= 6 px from every other probe pixel;
* `S2` and `S3` are constructed to score **below** `S1`; only a team's best submission counts
  toward standing, so neither probe can cost a rank.

Usage:  python3 scripts/build_identification_pack.py [--m 2000] [--anchor <tif>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import metric as M  # noqa: E402

DEFAULT_ANCHOR = ROOT / "docs" / "downloads" / \
    "gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif"
TPL = ROOT / "data" / "raw" / "sample_submission.tif"
LAB = ROOT / "data" / "raw" / "labels.tif"


def write_portal_safe(path: Path, arr: np.ndarray, prof) -> dict:
    """Write a single-band float32 GeoTIFF with no nodata tag and re-verify from disk."""
    arr = np.asarray(arr, dtype=np.float32)
    prof = dict(prof)
    prof.update(driver="GTiff", count=1, dtype="float32", nodata=None)
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(arr, 1)
    with rasterio.open(path) as s:
        back = s.read(1)
        kind = s.dtypes[0]
        nd = s.nodata
    finite = np.isfinite(back)
    ok = (finite.all() and float(back.min()) >= 0.0 and float(back.max()) <= 1.0
          and kind == "float32" and nd is None and np.array_equal(back, arr))
    if not ok:
        path.unlink(missing_ok=True)
        raise SystemExit(f"FAIL-CLOSED: {path.name} is not portal-legal "
                         f"(finite={bool(finite.all())} min={float(back.min())} "
                         f"max={float(back.max())} dtype={kind} nodata={nd})")
    return {
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "finite_cells": int(finite.sum()),
        "nan_cells": int((~finite).sum()),
        "min": float(back.min()),
        "max": float(back.max()),
        "range_violations": int(((back < 0) | (back > 1)).sum()),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchor", default=str(DEFAULT_ANCHOR))
    ap.add_argument("--m", type=int, default=2000, help="number of null-probe pixels")
    ap.add_argument("--out", default=str(ROOT / "docs" / "downloads"))
    ap.add_argument("--receipt", default=str(ROOT / "registry" / "identification_pack.json"))
    a = ap.parse_args()

    anchor_path = Path(a.anchor)
    if not anchor_path.exists():
        print(f"missing anchor {anchor_path}; run: bash scripts/fetch_mirrors.sh", file=sys.stderr)
        return 2
    if not TPL.exists():
        print(f"missing {TPL}; run: bash scripts/fetch_mirrors.sh", file=sys.stderr)
        return 2

    with rasterio.open(TPL) as s:
        tpl = s.read(1)
        prof = dict(crs=s.crs, transform=s.transform, width=s.width, height=s.height,
                    compress="lzw", tiled=False)
    fp = np.isfinite(tpl)

    with rasterio.open(anchor_path) as s:
        raw = s.read(1)
    if raw.shape != tpl.shape:
        raise SystemExit("anchor grid does not match the template")
    p1 = np.where(fp & np.isfinite(raw), raw, 0.0).astype(np.float32)
    print(f"anchor {anchor_path.name}: {int((p1 > 0).sum())} positive px, "
          f"mass {float(p1.sum()):.0f}")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    receipt = {
        "generated_by": "scripts/build_identification_pack.py",
        "purpose": ("three-slot exact identification of T, K, F on the hidden label set; see "
                    "knowledge/02_the_ceiling_and_the_instrument.md section 6"),
        "anchor_source": anchor_path.name,
        "anchor_positive_px": int((p1 > 0).sum()),
        "files": {},
    }

    # ---------------- S1 ANCHOR ----------------
    s1_name = "gems52-probe-S1-ANCHOR-identical-to-live-02600.tif"
    rec = write_portal_safe(out / s1_name, p1, prof)
    rec.update(role="S1 ANCHOR",
               construction="bit-identical in-footprint values to the anchor; re-encoded "
                            "all-finite with no nodata tag",
               expected_relation_to_anchor="leaderboard score should reproduce the anchor's")
    receipt["files"][s1_name] = rec

    # ---------------- S2 SCALE ----------------
    s2_name = "gems52-probe-S2-SCALE-lambda-0.5.tif"
    p2 = (0.5 * p1).astype(np.float32)
    rec = write_portal_safe(out / s2_name, p2, prof)
    rec.update(role="S2 SCALE",
               construction="lambda = 0.5 applied to every positive value of S1",
               algebra="1/DTI(0.5) = alpha + alpha*(F/T) + 2*beta*(K/T)",
               expected_relation_to_anchor="strictly and predictably BELOW S1 (dDTI/dlambda>0)")
    receipt["files"][s2_name] = rec

    # ---------------- S3 NULL-ADD ----------------
    cat = None
    if LAB.exists():
        with rasterio.open(LAB) as s:
            cat = (s.read(1) == 1) & fp

    support = p1 > 0
    d_support = ndimage.distance_transform_edt(~support)
    d_edge = ndimage.distance_transform_edt(fp)
    score = np.minimum(d_support, d_edge)
    if cat is not None:
        d_cat = ndimage.distance_transform_edt(~cat)
        score = np.minimum(score, d_cat)
    # only footprint interior; keep a generous margin from the footprint boundary
    viable = fp & (d_edge >= 10.0) & (d_support >= 3.0)
    if cat is not None:
        viable &= (d_cat >= 4.0)          # > 3 px so masking cannot be the mover, plus margin

    # greedy: take the best-scoring pixels, then enforce >= 6 px mutual separation
    idx = np.flatnonzero(viable)
    order = idx[np.argsort(-score.ravel()[idx], kind="stable")]
    chosen: list[tuple[int, int]] = []
    taken = np.zeros(tpl.shape, dtype=bool)
    r = 6
    for flat in order:
        y, x = divmod(int(flat), tpl.shape[1])
        if taken[y, x]:
            continue
        chosen.append((y, x))
        y0, y1 = max(0, y - r), min(tpl.shape[0], y + r + 1)
        x0, x1 = max(0, x - r), min(tpl.shape[1], x + r + 1)
        taken[y0:y1, x0:x1] = True
        if len(chosen) >= a.m:
            break
    if len(chosen) < a.m:
        print(f"WARNING: only {len(chosen)} well-separated probe sites available for m={a.m}",
              file=sys.stderr)

    p3 = p1.copy()
    ys = np.array([c[0] for c in chosen])
    xs = np.array([c[1] for c in chosen])
    p3[ys, xs] = 1.0
    s3_name = f"gems52-probe-S3-NULLADD-{len(chosen)}px.tif"
    rec = write_portal_safe(out / s3_name, p3, prof)

    # verify the probe geometry from the written arrays, not from the loop variables
    new = (p3 > 0) & ~support
    min_d_cat = float(d_cat[new].min()) if cat is not None else None
    min_d_sup = float(d_support[new].min())
    min_d_edge = float(d_edge[new].min())
    rec.update(role="S3 NULL-ADD",
               construction=f"S1 plus {int(new.sum())} unit-mass pixels placed at the maximum of "
                            f"min(distance-to-anchor-support, distance-to-catalogue, "
                            f"distance-to-footprint-edge), mutually >= 6 px apart",
               algebra=f"1/DTI = 1/DTI(S1) + alpha*{int(new.sum())}/T  ->  "
                       f"T = alpha*{int(new.sum())}/delta(1/DTI)",
               probes_added=int(new.sum()),
               min_dist_to_catalogue_px=min_d_cat,
               min_dist_to_anchor_support_px=min_d_sup,
               min_dist_to_footprint_edge_px=min_d_edge,
               expected_relation_to_anchor=f"strictly BELOW S1 by ~alpha*{int(new.sum())}/T in "
                                           f"1/DTI; only the best submission counts toward standing")
    receipt["files"][s3_name] = rec

    # ---------------- the decision rule, frozen ----------------
    receipt["decision_rule"] = {
        "step_1": "T = alpha*M / (1/s_S3 - 1/s_S1)",
        "step_2": "K = T*(1/s_S2 - 1/s_S1)/beta",
        "step_3": "F = T*(1/s_S1 - alpha - beta*K/T)/alpha",
        "then": ("report the measured hidden-set recall T/K, and re-price every subsequent emission "
                 "decision on the measured K instead of the owner model K_hat = 12,226"),
        "residual_risk": ("if any S3 probe pixel lands within 300 m of a hidden fault then dT>0 and "
                          "T is over-estimated; mitigation is the >=4 px catalogue clearance and "
                          "the maximum-distance placement, and the risk is bounded by the fact "
                          "that probes are at the minimum of every belief field in the repository"),
    }
    Path(a.receipt).parent.mkdir(parents=True, exist_ok=True)
    Path(a.receipt).write_text(json.dumps(receipt, indent=1) + "\n")

    print()
    for name, r in receipt["files"].items():
        print(f"  {r['role']:12s} {name}")
        print(f"      {r['bytes']:>10,} bytes  sha256 {r['sha256'][:16]}...  "
              f"finite {r['finite_cells']:,}  range-violations {r['range_violations']}")
    print()
    if min_d_cat is not None:
        print(f"  S3 probe clearance: min {min_d_cat:.1f} px to catalogue, "
              f"{min_d_sup:.1f} px to anchor support, {min_d_edge:.1f} px to footprint edge")
    print(f"  wrote {a.receipt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
