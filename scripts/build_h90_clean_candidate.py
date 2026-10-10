#!/usr/bin/env python3
"""H90-C: build the clean-sampler co-training disagreement candidate (research only).

Why this file is new (and why it is in-lane)
--------------------------------------------
The H60D artifact is built from out-of-fold (OOF) View A / View B fields. Those OOF fields come from
fold models whose negatives were sampled with the shipped sampler (see
``registry/h87_negclear_preregistration.json``). H87-L refits both views per fold with the CLEAN
sampler (fit region only, catalogue = fit catalogue only). The disagreement field
``dis_contrast = max(pA - pB, 0)`` on those clean OOF fields is a different full-grid field, so the
emitted pixels are different from every prior raster. Same lane, same emitter, same legal pool.

Everything is imported from shared code: ``run_h60d_cotrain`` (fit/predict), ``gems52.h57``
(emitter, disagreement), ``gems52.grid`` (writer), ``gems52.gates`` (format, uniqueness, priors) and
``gems52.h60d`` (lane drift, run card).

Protocol
--------
* Legal pool = footprint & not within 200 m (2 px) of any catalogue pixel & outside the support of
  every accessible prior raster (the H60D convention).
* Emitter = ``h57.iso_select(score, pool, 37654, min_px=3, nms_px=5)``, the H60D registered emitter.
* Writer = ``grid.write_geotiff_portal_exact(..., outside="zero")``: finite, in [0, 1], EPSG:32611,
  pinned grid.
* Gates recorded: format, uniqueness (decoded pixels), lane drift on surface and dots (<= 0.90),
  not-merely-union (vs ``iso_select(max(pA, pB))``), ring gate (>= 200 m), HOLDOUT-DTI copied from
  the H87-L audit receipt (never recomputed here as a score).
* Promotion: none. ``submit_ok`` is false by construction; the H60D-era holdout bar is not met.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_h60d_cotrain as R  # noqa: E402  (shared fit/predict, not a copy)
from gems52 import gates  # noqa: E402
from gems52 import grid as G  # noqa: E402
from gems52 import h57  # noqa: E402
from gems52 import h60d  # noqa: E402
from gems52 import holdout as HO  # noqa: E402

BUDGET = 37654
EV = ROOT / "evidence"
DL = ROOT / "docs/downloads"
SUB = ROOT / "submission"
WORK = ROOT / "work/h90"
STEM_RE = re.compile(r"^(gems52-h90-.*|h90-candidate)\.(tif|zip)$")  # own outputs only
NAME_BASE = "gems52-h90-cleanoof-disagree-37654px"
NOTE = ("H90 RESEARCH ONLY - DO NOT SUBMIT: clean-sampler co-training disagreement; 3px spaced; "
        "200m ring out; binary; holdout below best arm")


def log(m: str) -> None:
    print(f"[h90-C {time.strftime('%H:%M:%S')}] {m}", flush=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_oof(layers, idx_a, idx_b, cat, valid, folds):
    """OOF View A / View B with the clean sampler, cached to work/h90."""
    WORK.mkdir(parents=True, exist_ok=True)
    pa_p, pb_p = WORK / "pa_clean_oof.npy", WORK / "pb_clean_oof.npy"
    if pa_p.exists() and pb_p.exists():
        log("clean OOF cached")
        return np.load(pa_p), np.load(pb_p)
    pa_o = np.full(G.SHAPE, np.nan, np.float32)
    pb_o = np.full(G.SHAPE, np.nan, np.float32)
    for f in folds:
        fit, reg, fold = f["fit"], f["region"], f["fold"]
        cat_fit = cat & fit
        _, pa = R.fit_and_predict(layers, idx_a, cat_fit, valid & fit, fit, R.SEED + fold,
                                  f"A-clean/f{fold}")
        _, pb = R.fit_and_predict(layers, idx_b, cat_fit, valid & fit, fit, R.SEED + fold,
                                  f"B-clean/f{fold}")
        pa_o[reg] = pa[reg]
        pb_o[reg] = pb[reg]
    np.save(pa_p, pa_o)
    np.save(pb_p, pb_o)
    return pa_o, pb_o


def main() -> int:
    t0 = time.time()
    valid = G.footprint_from(R.DATA / "training_features.tif", bands="all")
    with rasterio.open(R.DATA / "labels.tif") as src:
        cat = src.read(1) == 1
    with rasterio.open(R.DATA / "sample_submission.tif") as src:
        valid_sub = np.isfinite(src.read(1))
    layers = h57.Layers(str(R.WORK))
    idx_a = layers.index([f"{n}_{s}" for n in h57.VIEW_A_LAYERS for s in ("val", "grad", "range")])
    idx_b = layers.index([f"{n}_{s}" for n in h57.VIEW_B_LAYERS for s in ("val", "grad", "range")])
    folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002, seed=R.SEED,
                          mode="hide")

    pa_o, pb_o = clean_oof(layers, idx_a, idx_b, cat, valid, folds)
    covered = np.isfinite(pa_o) & np.isfinite(pb_o)
    log(f"clean OOF covers {int(covered.sum())} px of footprint {int(valid.sum())} "
        f"(uncovered inside footprint: {int((valid & ~covered).sum())})")
    pa = np.nan_to_num(pa_o, nan=0.0).astype(np.float32)
    pb = np.nan_to_num(pb_o, nan=0.0).astype(np.float32)
    field = h60d.dis_contrast(pa, pb).astype(np.float32)

    # ---- legal pool: footprint & >=200 m from catalogue & outside every prior's support ------
    dcat = ndimage.distance_transform_edt(~cat) * 100.0
    corridor = ndimage.binary_dilation(cat, iterations=h57.CORRIDOR_PX)
    permitted = valid & valid_sub & ~corridor
    roots = [str(SUB), str(DL), str(ROOT / "docs"), str(R.DATA / "scored"), str(R.DATA / "reference")]
    priors = [p for p in gates.find_priors([r for r in roots if Path(r).exists()])
              if not STEM_RE.match(Path(p).name)]
    support = np.zeros(G.SHAPE, bool)
    for p in priors:
        try:
            support |= (np.nan_to_num(gates.read_raster(p), nan=0.0) > 0.5)
        except Exception:
            pass
    pool = permitted & ~support
    log(f"priors {len(priors)}; support {int(support.sum())} px; legal pool {int(pool.sum())} px")

    # ---- lane drift gate on the surface, before placement --------------------------------------
    calib = h60d.calibration_basenames(ROOT / "registry/data_manifest.json")
    lane_surface = h60d.lane_drift_report(field, None, priors, valid,
                                          sample=R.DATA / "sample_submission.tif", calibration=calib)
    log(f"surface lane gate: {lane_surface.get('surface_max_abs_spearman')} "
        f"drift={lane_surface.get('lane_drift_detected')}")

    # ---- emission (registered H60D emitter) ----------------------------------------------------
    score = np.where(pool, field, 0.0).astype(np.float32)
    nodes = h57.iso_select(score, pool, BUDGET, min_px=3.0, nms_px=5)
    arm = nodes & pool & valid_sub
    total = int(arm.sum())
    arr = np.zeros(G.SHAPE, np.float32)
    arr[arm] = 1.0
    log(f"emitted {total} px (budget {BUDGET}); min distance to catalogue "
        f"{float(dcat[arm].min()) if total else float('nan'):.1f} m")

    # ---- not merely the union --------------------------------------------------------------
    union_score = np.where(pool, np.maximum(pa, pb), 0.0).astype(np.float32)
    union_nodes = h57.iso_select(union_score, pool, BUDGET, min_px=3.0, nms_px=5)
    overlap_union = float((arm & union_nodes).sum() / max(total, 1))
    log(f"overlap with union-of-views emission: {overlap_union:.4f}")

    # ---- write + gates ------------------------------------------------------------------------
    stem = f"{NAME_BASE}"
    tmp_path = SUB / f"{stem}.tif"
    q = G.write_geotiff_portal_exact(tmp_path, arr, valid_sub,
                                     sample=R.DATA / "sample_submission.tif", outside="zero")
    sha = sha256(tmp_path)
    fmt = gates.format_report(tmp_path, R.DATA / "sample_submission.tif", footprint=valid_sub)
    uniq = gates.uniqueness_report(arr, priors)
    lane_dots = h60d.lane_drift_report(field, arm, priors, valid, calibration=calib,
                                       sample=R.DATA / "sample_submission.tif")
    dmin = float(dcat[arm].min()) if total else float("nan")
    with rasterio.open(tmp_path) as ds:
        back = ds.read(1)
        nodata = ds.nodata
    validator = dict(
        shape=list(back.shape), dtype=str(back.dtype), crs=str(rasterio.open(R.DATA / "sample_submission.tif").crs),
        transform_matches_sample=bool(rasterio.open(tmp_path).transform == rasterio.open(R.DATA / "sample_submission.tif").transform),
        finite_everywhere=bool(np.isfinite(back).all()),
        min=float(np.nanmin(back)), max=float(np.nanmax(back)),
        in_0_1=bool((back >= 0).all() and (back <= 1).all()),
        nan_inside_footprint=int((~np.isfinite(back) & valid_sub).sum()),
        positives=int((back > 0).sum()), nodata_tag=nodata,
        outside_footprint_positive=int(((back > 0) & ~valid_sub).sum()),
    )
    rec = dict(
        round="H90-C", status="research candidate; DOWNLOAD YES, SUBMIT NO",
        field="dis_contrast = max(pA_clean - pB_clean, 0) on clean-sampler OOF fields",
        emitter="gems52.h57.iso_select, 3 px, NMS 5 px (registered H60D emitter)",
        pool_px=int(pool.sum()), n_priors=len(priors), support_px=int(support.sum()),
        emitted_px=total, sha256=sha, bytes=tmp_path.stat().st_size,
        name=stem, note=NOTE, note_chars=len(NOTE),
        format_gate=fmt, uniqueness=uniq, lane_surface=lane_surface, lane_dots=lane_dots,
        validator=validator,
        overlap_with_union_emission=overlap_union,
        ring_gate_min_distance_m=dmin, ring_gate_pass=bool(total and dmin >= 200.0),
        holdout_source="evidence/h90_negclear_audit.json (HOLDOUT-DTI, H60D instrument, not a score)",
        submit_ok=False, slots_used=0,
        runtime_s=round(time.time() - t0, 1),
    )
    h60d.write_json(EV / "h90_build.json", rec)

    # downloads: one-click TIF + ZIP with paste-ready name and note
    DL.mkdir(parents=True, exist_ok=True)
    for ext in ("tif",):
        (DL / f"h90-candidate.{ext}").write_bytes(tmp_path.read_bytes())
    zip_path = DL / "h90-candidate.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(tmp_path, arcname=f"{stem}.tif")
        z.writestr("submission-name.txt", stem + "\n")
        z.writestr("submission-note.txt", NOTE + "\n")
        z.writestr("STATUS.txt", "H90 RESEARCH ONLY. DOWNLOAD YES. SUBMIT NO. Not holdout-approved.\n")
    log(f"wrote {tmp_path.name} sha256 {sha[:16]} ; {total} px ; zip {zip_path.name}")
    log(f"format problems: {fmt.get('problems')} ; pattern_unique={uniq.get('canonical_pattern_unique')} "
        f"novel_frac={uniq.get('novel_fraction')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
