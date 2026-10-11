#!/usr/bin/env python3
"""H97b -- the same frozen H97 field emitted with the E4 coverage geometry, gated and packaged.

Only built if ``evidence/h97_e4_coverage.json`` says the geometry beats the same mass spent on more dots
(paired 95 % CI lower bound > 0).  Reuses, unmodified: ``run_h97.stitch`` / ``run_h97.arm_field`` /
``run_h97.rank_in`` / ``run_h97.local_registry``, ``run_h97_e4_coverage.bridge``,
``gems52.nodes.spacing_select``, ``gems52.evaluate_holdout``, ``gems52.gates``, ``gems52.submission_writer``.

Usage: python scripts/build_h97b_covered.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np                                                    # noqa: E402
import rasterio                                                        # noqa: E402
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import run_h61 as base                                                 # noqa: E402
import run_h97 as h97                                                  # noqa: E402
import run_h97_e4_coverage as e4                                       # noqa: E402
from gems52 import gates, nodes, submission_writer                     # noqa: E402

EVID = ROOT / "evidence"
WORK = ROOT / "work/h97"
SAMPLE = ROOT / "data/sample_submission.tif"
K_TOTAL = h97.K_TOTAL
RING_M = h97.RING_M


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def main() -> int:
    cov = json.loads((EVID / "h97_e4_coverage.json").read_text())
    g = cov["geometry_vs_mass"]["single_B2"]
    log("E4 geometry verdict: " + json.dumps({k: g[k] for k in ("verdict", "delta_matched_mass",
                                                                "ci95_matched_mass")}, default=float))
    if not g["GEOMETRY_BEATS_MASS_AT_MATCHED_MASS"]:
        log("E4 says the geometry does not beat matched mass; not building h97b (recorded, not forced).")
        (EVID / "h97b_skipped.json").write_text(json.dumps(
            dict(reason="E4 measured no geometry gain at matched mass", e4=g), indent=1, default=float) + "\n")
        return 0
    _reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    flat = store.flat_idx
    fA, fB = h97.stitch("single_A2", folds, eligible, flat), h97.stitch("single_B2", folds, eligible, flat)
    catd = ndi.distance_transform_edt(~cat)
    pool = eligible & np.isfinite(fA) & np.isfinite(fB) & (catd * 100.0 > RING_M)
    ai = np.flatnonzero(pool.ravel())
    ra = np.full(eligible.shape, np.nan, np.float32)
    rb = np.full(eligible.shape, np.nan, np.float32)
    ra.ravel()[ai] = base.pct_rank(fA.ravel()[ai])
    rb.ravel()[ai] = base.pct_rank(fB.ravel()[ai])
    field = np.full(pool.shape, -1.0, np.float32)
    field[pool] = base.pct_rank((ra.ravel()[ai] - rb.ravel()[ai]).astype(np.float64))
    dots = nodes.spacing_select(field, pool, K_TOTAL, min_px=3.0)
    covered, brec = e4.bridge(dots, field, pool, e4.Q_FLOOR, e4.R_BRIDGE_PX)
    log(f"dots {int(dots.sum())} -> covered {int(covered.sum())} ({brec})")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"h97b-pafdva-covered-{int(covered.sum())}px-{stamp}"
    note = ("H97b: same frozen H97 disagreement field, emitted as a covered trace (gap bridging <=1.2km) "
            "instead of 3px dots; 200m catalogue ring excluded")
    if len(note) > 140:
        note = f"H97b: H97 disagreement field emitted as a covered trace (gap bridging <=1.2km), 200m ring out, binary {int(covered.sum())}"
    assert len(name) <= 140 and len(note) <= 140, (len(name), len(note))
    out = ROOT / "submission" / f"gems52-{name}.tif"
    rec = submission_writer.write_submission(out, covered.astype(np.float32), SAMPLE, eligible, note=note,
                                             name=name, metadata=dict(round="H97b", primary_arm=h97.PRIMARY,
                                                                      geometry="covered trace, E4 bridging",
                                                                      bridge=brec,
                                                                      e4_verdict=g["verdict"]))
    with rasterio.open(out) as a, rasterio.open(SAMPLE) as s:
        v = a.read(1)
        val = dict(count=a.count, dtype=a.dtypes[0], crs=str(a.crs), shape=list(a.shape),
                   crs_match=a.crs == s.crs, shape_match=a.shape == s.shape,
                   transform_match=a.transform == s.transform, bounds_match=a.bounds == s.bounds,
                   nan=int(np.isnan(v).sum()), infinite=int(np.isinf(v).sum()),
                   min=float(np.nanmin(v)), max=float(np.nanmax(v)),
                   values=sorted(np.unique(v[np.isfinite(v)]).tolist())[:10],
                   ones=int((v == 1).sum()), zeros=int((v == 0).sum()), mass=float(np.nansum(v)))
    val["range_ok"] = bool(val["min"] >= 0.0 and val["max"] <= 1.0 and val["nan"] == 0 and val["infinite"] == 0)
    val["PASS"] = bool(val["count"] == 1 and val["dtype"] == "float32" and val["crs_match"]
                       and val["shape_match"] and val["transform_match"] and val["range_ok"])
    val["range_rule_source"] = ("official: single layer float32 with values between 0 and 1, EPSG:32611, 100 m, "
                                "same bounds as the training data "
                                "(https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)")
    reg = h97.local_registry()
    lane = dict(n=len(reg), surface=gates.lane_report(np.where(np.isfinite(field), np.nan_to_num(field, nan=0.0), 0.0),
                                                      eligible, reg, sample=SAMPLE, phase="surface"),
                dots=gates.lane_report(covered.astype(np.float32), eligible, reg, sample=SAMPLE, phase="dots"),
                uniqueness=gates.uniqueness_report(covered, reg))
    hold = json.loads((EVID / "h97_holdout.json").read_text())
    card = dict(round="H97b", generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                hypothesis="same field as H97; emission geometry changed from 3 px dots to a covered trace",
                geometry_evidence="evidence/h97_e4_coverage.json", e4=g,
                holdout_dti_h97_arm=hold["pooled"]["scores"][h97.PRIMARY],
                submission_name=name, note=note, note_chars=len(note), raster_sha256=rec["sha256"],
                raster_bytes=rec["bytes"], validator=val, lane_scope=h97.local_registry.__doc__,
                lane={k: (lane[k]["policy"] if k != "uniqueness" else {
                    kk: vv for kk, vv in lane["uniqueness"].items() if kk != "per_prior"}) for k in lane},
                bridge=brec, dots_before_bridge=int(dots.sum()), slots_used=0)
    card["verdict"] = "candidate with measured geometry gain" if val["PASS"] else "rejected by validator"
    card["submit_ok"] = bool(val["PASS"])
    (EVID / "h97b_run_card.json").write_text(json.dumps(card, indent=1, default=float) + "\n")
    log(json.dumps(dict(sha=rec["sha256"], ones=val["ones"], validator=val["PASS"],
                        lane_dots=lane["dots"]["policy"]["verdict"]), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
