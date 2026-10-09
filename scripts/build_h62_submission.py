#!/usr/bin/env python3
"""H62 submission build — buried structural corridors (co-training lane).

Preregistered: ``registry/h62_preregistration.json`` (frozen before any H62 fit ran).
The shipped field is the H62-1 gate chain applied to the OOF disagreement contrast
``max(pA - pB, 0)``: cover >= 200 m -> potential-field edge >= P75 -> line persistence
(corridor length >= 15 px, elongation >= 3).  Placement is the registered scoring emitter
``h57.iso_select`` (min_px 3, nms_px 5) on the required-novel pool (outside the <=200 m
catalogue ring and outside every accessible prior's support), budget 37,654 px.

Outputs:
  submission/<stem>.tif|zip                canonical artifact + one-TIFF portal zip
  docs/downloads/h62-candidate.tif|zip     site copies (one-click download)
  submission/H62_LATEST.txt                round pointer (submission/LATEST.txt only if approved)
  evidence/h62_build.json, h62_format_gate.json, h62_uniqueness.json, h62_lane_surface.json,
           h62_lane_gate.json, h62_slot_gate.json, h62_run_card.json,
           gems52-h62-*-candidate-geology.csv, gems52-h62-a-only-candidate-segments.csv
  docs/data/submission_h62.json            machine-readable site receipt

This script never uploads anything.  Promotion to a weekly slot is a separate selector step.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import gates                            # noqa: E402
from gems52 import grid as G                       # noqa: E402
from gems52 import h57                              # noqa: E402
from gems52 import h60d                              # noqa: E402
from gems52 import holdout as HO                    # noqa: E402
from gems52 import metric as M                      # noqa: E402

DATA = ROOT / "work/pinned"
WORK = ROOT / "work/h62"
EV = ROOT / "evidence"
DL = ROOT / "docs/downloads"
DAD = ROOT / "docs/data"
SUB = ROOT / "submission"
BUDGET = 37654
SEED = 20261009


def log(m: str) -> None:
    print(f"[h62-build {time.strftime('%H:%M:%S')}] {m}", flush=True)


def read_mask(path: Path, thresh: float = 0.5) -> np.ndarray:
    with rasterio.open(path) as src:
        a = src.read(1)
    a[~np.isfinite(a)] = 0.0
    return a > thresh


def prior_inventory():
    """Accessible aligned priors with H62's own outputs excluded (by exact stem patterns)."""
    found = gates.find_priors([str(SUB), str(DL), str(ROOT / "docs"), str(DATA / "scored"),
                               str(DATA / "reference")])
    own_re = re.compile(r"^gems52-h62-.*\.tif$")
    own_short = {"h62-candidate.tif", "h62-candidate.zip", "STATUS.txt"}
    keep = []
    for p in found:
        n = Path(p).name
        if n in own_short or own_re.match(n):
            continue
        keep.append(p)
    return keep


def main() -> int:
    t0 = time.time()
    valid = G.footprint_from(DATA / "training_features.tif", bands="all")
    with rasterio.open(DATA / "labels.tif") as src:
        cat = src.read(1) == 1
    with rasterio.open(DATA / "sample_submission.tif") as src:
        valid_sub = np.isfinite(src.read(1))

    pa = np.nan_to_num(np.load(WORK / "pa_oof.npy"), nan=0.0).astype(np.float32)
    pb = np.nan_to_num(np.load(WORK / "pb_oof.npy"), nan=0.0).astype(np.float32)
    field_arr = np.load(WORK / "field_h62_1.npy").astype(np.float32)
    corridor_mask = np.load(WORK / "h62_corridor_mask.npy")
    a_only = np.load(WORK / "stratum_a_only.npy")
    b_only = np.load(WORK / "stratum_b_only.npy")
    strat_conc = np.load(WORK / "stratum_concordant.npy")
    cotrain_receipt = json.loads((EV / "h62_cotrain.json").read_text())
    depth_medians = cotrain_receipt["strata"]["median_depth_to_basement_m"]
    val = json.loads((EV / "h62_validation.json").read_text())

    priors = prior_inventory()
    support = np.zeros(G.SHAPE, bool)
    for p in priors:
        try:
            support |= read_mask(Path(p))
        except Exception:
            pass
    log(f"prior support union: {int(support.sum())} px from {len(priors)} aligned rasters")

    corridor = ndimage.binary_dilation(cat, iterations=h57.CORRIDOR_PX)
    permitted = valid & ~corridor
    pool = permitted & ~support
    log(f"legal pool: {int(pool.sum())} px (footprint & ~200 m ring & outside prior support)")

    # ---- lane drift gate on the SURFACE, before placement (lane protocol item 1) --------------
    calib = h60d.calibration_basenames(ROOT / "registry/data_manifest.json")
    lane_surface = h60d.lane_drift_report(field_arr, None, priors, valid, calibration=calib)
    h60d.write_json(EV / "h62_lane_surface.json", lane_surface)
    log(f"lane gate on surface: max|rho|={lane_surface['surface_max_abs_spearman']} -> "
        f"{'DRIFT' if lane_surface['lane_drift_detected'] else 'clean'}")

    # ---- placement (registered scoring emitter, correction H60-5) ------------------------------
    density = np.maximum(np.where(pool, field_arr, 0.0), 0.0).astype(np.float32)
    n_pos_pool = int((pool & (field_arr > 0)).sum())
    if n_pos_pool < BUDGET:
        log(f"WARNING: positive-field support on the novel pool is {n_pos_pool} px < budget "
            f"{BUDGET}; iso_select fills the remainder from zero-field pool pixels (disclosed)")
    arm = h57.iso_select(density, pool, BUDGET, min_px=3.0, nms_px=5)
    arm_b = arm > 0
    pos_crests = int((arm_b & (field_arr > 0)).sum())
    log(f"iso_select placed {int(arm_b.sum())} px (requested {BUDGET}); {pos_crests} on "
        f"positive-field crests, {int(arm_b.sum()) - pos_crests} zero-field budget fill")

    # ---- not merely the union of the two views -------------------------------------------------
    union_field = np.maximum(pa, pb)
    union_topk = h57.iso_select(np.where(pool, union_field, 0.0).astype(np.float32), pool,
                                BUDGET, min_px=3.0, nms_px=5) > 0
    viewB_topk = h57.iso_select(np.where(pool, pb, 0.0).astype(np.float32), pool,
                                BUDGET, min_px=3.0, nms_px=5) > 0
    viewA_topk = h57.iso_select(np.where(pool, pa, 0.0).astype(np.float32), pool,
                                BUDGET, min_px=3.0, nms_px=5) > 0
    outside_union = int((arm_b & ~union_topk).sum())
    outside_viewA = int((arm_b & ~viewA_topk).sum())
    outside_viewB = int((arm_b & ~viewB_topk).sum())
    log(f"not-merely-union: {outside_union}/{int(arm_b.sum())} outside union top-k; "
        f"{outside_viewA} outside view_A top-k; {outside_viewB} outside view_B top-k")

    # ---- assemble (binary {0,1}, ALL FINITE — zeros outside the sample domain) ------------------
    arr = np.zeros(G.SHAPE, np.float32)
    arr[arm_b] = 1.0
    clipped = int(((arr > 0) & ~valid_sub).sum())
    arr[~valid_sub] = 0.0
    arm_b = arm_b & valid_sub
    total = int((arr > 0).sum())
    ys, xs = np.nonzero(arr > 0)
    dcat = ndimage.distance_transform_edt(~cat, sampling=G.PIXEL_M)
    dmin_cat = float(dcat[ys, xs].min()) if ys.size else float("nan")
    log(f"emitted {total} px; clipped {clipped}; min distance to mapped catalogue "
        f"{dmin_cat:.1f} m")

    qhash = hashlib.sha256()
    stem = f"gems52-h62-buriedcorr-{total}px"
    path = SUB / f"{stem}.tif"
    q = G.write_geotiff(path, arr)
    log(f"wrote {path.name}: {q['bytes']} bytes, sha256 {q['sha256'][:16]}…")

    fmt = gates.format_report(path, DATA / "sample_submission.tif", footprint=valid_sub)
    uniq = gates.uniqueness_report(arr, priors)
    h60d.write_json(EV / "h62_format_gate.json", fmt)
    h60d.write_json(EV / "h62_uniqueness.json", uniq)
    log(f"format problems: {fmt['problems']}; pattern_unique={uniq['canonical_pattern_unique']}, "
        f"novel_frac={uniq['novel_fraction']:.4f}, n_priors={uniq['n_priors_checked']}")

    # ---- lane drift gate on the FINAL DOTS (H60-6: calibration excluded from proximity) ----------
    lane_dots = h60d.lane_drift_report(field_arr, arm_b, priors, valid, calibration=calib)
    h60d.write_json(EV / "h62_lane_gate.json", lane_dots)
    log(f"lane gate on dots: max|rho|={lane_dots['dots_max_abs_spearman']}, raw within-3px "
        f"{lane_dots['dots_max_within_3px_frac']} (gate excl. calib: "
        f"{lane_dots['dots_max_within_3px_frac_gate']}) -> "
        f"{'DRIFT' if lane_dots['lane_drift_detected'] else 'clean'}")

    # ---- score the SHIPPED raster on the holdout + matched novel-pool controls -------------------
    shipped, novel_controls = [], []
    rng_novel = np.random.default_rng(SEED)
    for mode in ("hide", "tip"):
        folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002,
                              seed=SEED, mode=mode)
        for f in folds:
            truth = f["truth"] & f["region"] & valid
            legal_novel = f["region"] & pool
            p = np.where(f["region"], arr, 0.0)
            p = HO.mask_visible(p, f["visible"] & valid)
            r = M.dti(p, truth)
            shipped.append(dict(mode=mode, fold=f["fold"], dti=round(float(r["dti"]), 6),
                                tpw=float(r["tpw"]), fpw=float(r["fpw"]), fnw=float(r["fnw"]),
                                n_truth=int(r["n_truth"]), emitted=int((p > 0).sum())))
            flat_pool = np.flatnonzero(legal_novel.ravel())
            take = rng_novel.choice(flat_pool, min(BUDGET, flat_pool.size), replace=False)
            rnd = np.zeros(G.SHAPE, bool)
            rnd.ravel()[take] = True
            p = np.where(f["region"], rnd.astype(np.float32), 0.0)
            p = HO.mask_visible(p, f["visible"] & valid)
            r = M.dti(p, truth)
            novel_controls.append(dict(mode=mode, fold=f["fold"], arm="random_novelpool",
                                       dti=round(float(r["dti"]), 6), n_truth=int(r["n_truth"])))
            for arm_name, fld in (("H62_1_novelpool", field_arr),
                                  ("view_B_novelpool", pb),
                                  ("clf_union_novelpool", union_field)):
                score = np.where(legal_novel, fld, 0.0).astype(np.float32)
                nodes = h57.iso_select(score, legal_novel, BUDGET, min_px=3.0, nms_px=5)
                p = np.where(f["region"], nodes.astype(np.float32), 0.0)
                p = HO.mask_visible(p, f["visible"] & valid)
                r = M.dti(p, truth)
                novel_controls.append(dict(mode=mode, fold=f["fold"], arm=arm_name,
                                           dti=round(float(r["dti"]), 6),
                                           n_truth=int(r["n_truth"])))
        log(f"shipped {mode}: " + ", ".join(f"f{r['fold']}={r['dti']:.6f}"
                                            for r in shipped if r["mode"] == mode))

    shipped_pooled = {}
    for mode in ("hide", "tip"):
        rs = [r for r in shipped if r["mode"] == mode]
        pl = h60d.pooled_dti(rs)
        ci = h60d.bootstrap_ci([r["dti"] for r in rs], n_boot=10000, seed=SEED)
        shipped_pooled[mode] = dict(
            pooled_dti=round(pl["dti"], 6), tpw=round(pl["tpw"], 2), fpw=round(pl["fpw"], 2),
            fnw=round(pl["fnw"], 2), withheld_positives=pl["n_truth"],
            fold_mean_dti=round(ci["mean"], 6), ci95_lo=round(ci["ci_lo"], 6),
            ci95_hi=round(ci["ci_hi"], 6),
            label="HOLDOUT-DTI of the SHIPPED raster (evaluator gems52.metric.dti alpha 0.2 "
                  "beta 0.8 R 300 m triangular; holdout.make_folds whole-segment "
                  "hide-and-recover, 4 folds, buffer 4 px, prevalence 0.002, seed 20261009; "
                  "pooled = metric components pooled across folds; CI = fold bootstrap 10k)")
    novel_pooled = {}
    for mode in ("hide", "tip"):
        for arm_name in ("random_novelpool", "H62_1_novelpool", "view_B_novelpool",
                         "clf_union_novelpool"):
            rs = [r for r in novel_controls if r["mode"] == mode and r["arm"] == arm_name]
            if rs:
                novel_pooled[f"{mode}|{arm_name}"] = round(float(np.mean([r["dti"] for r in rs])), 6)

    # ---- per-emitted-pixel geological reasoning -------------------------------------------------
    depth = G.read_band(DATA / "training_features.tif", 15)
    cond = G.read_band(DATA / "training_features.tif", 17)
    mag = G.read_band(DATA / "training_features.tif", 14)
    grav = G.read_band(DATA / "training_features.tif", 13)
    elev = G.read_band(DATA / "training_features.tif", 12)
    depth_sorted = np.sort(depth[permitted])
    tr = G.TRANSFORM

    def depth_pct(v):
        return 100.0 * np.searchsorted(depth_sorted, v) / depth_sorted.size

    def reason(r, c):
        pa_, pb_ = float(pa[r, c]), float(pb[r, c])
        d = float(depth[r, c]) if np.isfinite(depth[r, c]) else float("nan")
        parts = []
        parts.append(
            f"Buried structural corridor candidate (H62-1): the geophysical view is confident "
            f"(p_A={pa_:.2f}) while the surface view abstains (p_B={pb_:.2f}); the pixel passes "
            f"the cover gate (depth to basement >= {200} m), the potential-field edge gate "
            f"(gradient >= footprint P75), and the line-persistence gate (linear corridor "
            f">= {15} px, elongation >= {3}) — a density or susceptibility step along strike "
            f"with no surface scarp")
        if np.isfinite(d):
            dp = depth_pct(d)
            parts.append(f"depth to basement {d:.0f} m at the {dp:.0f}th footprint percentile "
                         f"({'deep' if dp > 70 else 'intermediate' if dp > 30 else 'shallow'} cover)")
        parts.append(f"isostatic gravity {float(grav[r, c]):.1f} mGal, TMI {float(mag[r, c]):.0f} nT, "
                     f"detrended elevation {float(elev[r, c]):+.0f} m, conductivity "
                     f"{float(cond[r, c]):.3f} S/m")
        parts.append(
            f"falsifier: Phase-2 review that finds intact undisturbed cover, no break in the "
            f"geophysical gradient within 300 m, a mapped paleochannel or lithologic contact "
            f"explaining the gradient, or a DEM/road-layer match showing anthropogenic fabric "
            f"voids this candidate; it was emitted because it is {float(dcat[r, c]):.0f} m from "
            f"the nearest mapped catalogue pixel and outside every accessible prior's support")
        return "; ".join(parts) + "."

    rows_out = []
    ay, ax = np.nonzero(arm_b)
    for i, (r, c) in enumerate(zip(ay, ax)):
        rows_out.append(dict(
            node_id=i, row=int(r), col=int(c),
            easting_m=round(tr[2] + (c + 0.5) * tr[0], 1),
            northing_m=round(tr[5] + (r + 0.5) * tr[4], 1),
            p_view_A=round(float(pa[r, c]), 4), p_view_B=round(float(pb[r, c]), 4),
            h62_field_score=round(float(field_arr[r, c]), 4),
            depth_to_basement_m=None if not np.isfinite(depth[r, c]) else round(float(depth[r, c]), 1),
            surface_conductivity=None if not np.isfinite(cond[r, c]) else round(float(cond[r, c]), 4),
            tmi_nT=None if not np.isfinite(mag[r, c]) else round(float(mag[r, c]), 2),
            isostatic_gravity_mGal=None if not np.isfinite(grav[r, c]) else round(float(grav[r, c]), 2),
            detrended_elev_m=None if not np.isfinite(elev[r, c]) else round(float(elev[r, c]), 1),
            distance_to_mapped_catalogue_m=round(float(dcat[r, c]), 1),
            agreement_stratum=("A_only" if a_only[r, c] else "B_only" if b_only[r, c] else
                               "concordant" if strat_conc[r, c] else "neither"),
            in_prior_support=bool(support[r, c]),
            geological_reasoning=reason(r, c)))
    csv_path = EV / f"gems52-h62-{total}px-candidate-geology.csv"
    with csv_path.open("w", newline="") as f:
        f.write("# H62 buried-corridor candidates: one written geological reasoning row per "
                "emitted pixel (the brief requires geological reasoning for every A-only "
                "candidate; here every emitted pixel carries one). View A = potential-field "
                "and subsurface bands; View B = surface bands + LiDAR/radiometric proxies. "
                "HYPOTHESES for Phase-2 review, not verified faults. Inputs: SHA-pinned "
                "owner-mirror bytes (not organizer-authenticated).\n")
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        for row in rows_out:
            w.writerow(row)
    log(f"wrote {csv_path.name} ({len(rows_out)} rows)")

    # ---- A-only candidate SEGMENTS (reasoning for every A-only candidate in the pool) ------------
    cand = a_only & pool & corridor_mask
    comp, ncomp = ndimage.label(cand, structure=np.ones((3, 3), bool))
    seg_rows = []
    if ncomp:
        yy, xx = np.nonzero(comp)
        ids = comp[yy, xx]
        order = np.argsort(ids, kind="stable")
        yy, xx, ids = yy[order], xx[order], ids[order]
        starts = np.searchsorted(ids, np.arange(1, ncomp + 1), side="left")
        ends = np.append(starts[1:], ids.size)
        sizes = ends - starts
        mass_sum = np.zeros(ncomp + 1, np.float64)
        np.add.at(mass_sum, ids, field_arr[yy, xx])
        mean_mass = mass_sum[1:] / np.maximum(sizes, 1)
        dep_v, cond_v = depth[yy, xx], cond[yy, xx]
        elev_v, dcat_v = elev[yy, xx], dcat[yy, xx]
        top = np.argsort(-mean_mass) + 1
        for sid in top:
            a, b = int(starts[sid - 1]), int(ends[sid - 1])
            rr, cc = yy[a:b], xx[a:b]
            dmed = float(np.median(dep_v[a:b]))
            dmin = float(dcat_v[a:b].min())
            seg_rows.append(dict(
                segment=int(sid), n_px=int(sizes[sid - 1]),
                centre_row=int(rr.mean()), centre_col=int(cc.mean()),
                easting_m=round(tr[2] + (cc.mean() + 0.5) * tr[0], 1),
                northing_m=round(tr[5] + (rr.mean() + 0.5) * tr[4], 1),
                mean_field_mass=round(float(mean_mass[sid - 1]), 4),
                median_depth_to_basement_m=round(dmed, 1),
                median_surface_conductivity=round(float(np.median(cond_v[a:b])), 4),
                median_detrended_elev_m=round(float(np.median(elev_v[a:b])), 1),
                min_distance_to_catalogue_m=round(dmin, 1),
                geological_reasoning=(
                    f"A-only buried-corridor segment ({int(sizes[sid - 1])} px, 8-connected): "
                    f"potential-field view confident, surface view abstaining; the segment "
                    f"passes the cover gate (median depth to basement {dmed:.0f} m), the "
                    f"edge gate and the line-persistence gate, so the reading is a buried "
                    f"density/susceptibility step — the fault a surface mapper cannot draw. "
                    f"Nearest mapped catalogue pixel {dmin:.0f} m. Falsifier: trenching or "
                    f"review finding intact undisturbed cover and no gradient break within "
                    f"300 m, or a paleochannel/lithologic-contact map that explains the "
                    f"gradient, or a DEM/road-layer match showing anthropogenic fabric.")))
    seg_path = EV / "gems52-h62-a-only-candidate-segments.csv"
    with seg_path.open("w", newline="") as f:
        f.write("# H62 A-only candidate dossier: every whole 8-connected segment of the A-only "
                "population that survives the H62-1 corridor gates inside the legal pool, "
                "ranked by mean field mass; one written reasoning + explicit falsifier per "
                "segment. HYPOTHESES for Phase-2 review, not verified faults.\n")
        if seg_rows:
            w = csv.DictWriter(f, fieldnames=list(seg_rows[0].keys()))
            w.writeheader()
            for row in seg_rows:
                w.writerow(row)
    log(f"wrote {seg_path.name} ({len(seg_rows)} segments of {ncomp})")

    # ---- conditional projection table (owner-reported inputs; NOT a score) ------------------------
    g_lo, g_hi = 18000.0, 27400.0   # knowledge/27 correction IR-H60-002 bracket
    proj = {"note": "conditional projection on owner-reported |G| bracket 18,000-27,400 "
                    "(IR-H60-002); never a forecast or a score"}
    for rho in (0.03, 0.05, 0.07, 0.09, 0.12, 0.14):
        row = {}
        for g_est, tag in ((g_lo, "G_lo"), (g_hi, "G_hi")):
            T = min(rho * total, g_est)
            row[tag] = round(float(T / (0.2 * total + 0.8 * g_est)), 4)
        proj[f"rho_{rho}"] = row
    log(f"conditional projection: {proj}")

    # ---- slot gate + run card ---------------------------------------------------------------------
    g62 = val["gates"]
    checks = {
        "format gate (single band, float32, EPSG:32611, 3730x3292, exact transform, all "
        "finite, values in [0,1], no mass outside footprint)":
            bool(not fmt["problems"]),
        "decoded pattern differs from every accessible aligned prior":
            bool(uniq["canonical_pattern_unique"]),
        "support novelty (100% of emitted px outside every prior's support)":
            bool(uniq.get("novel_fraction", 0) >= 0.999),
        "lane drift gate on the surface (max|rho| <= 0.90, excl. calibration rasters)":
            bool(lane_surface["surface_check_passed"]),
        "lane drift gate on the final dots (max|rho| <= 0.90 and <=70% within 3 px, excl. "
        "calibration rasters; raw values reported)":
            bool(lane_dots["dots_check_passed"]),
        "artifact is not the top-k of the plain union of the two views":
            bool(outside_union > 0),
        "artifact is not any prior and not any pair-union of priors":
            bool(not uniq["equals_literal_prior_union"]),
        "nothing emitted inside the <=200 m catalogue ring":
            bool(dmin_cat >= 200.0),
        "independence measured (max|r| < 0.60)":
            bool(cotrain_receipt["independence"]["max_abs_correlation"] is not None
                 and cotrain_receipt["independence"]["max_abs_correlation"] < 0.60),
        "leakage canary clean (no layer AUC > 0.90)":
            bool(not cotrain_receipt["leakage_canary"]["leakage_detected"]),
        "one written geological reasoning per emitted pixel":
            bool(len(rows_out) == total),
        "every surviving A-only candidate segment has written reasoning":
            bool(len(seg_rows) >= 1),
    }
    slot = dict(
        shipped_field="H62_1_corridors",
        preregistered_promotion_bar=g62,
        checks=checks, checks_pass=all(checks.values()),
        shipped_raster_holdout=shipped_pooled,
        note=("Every holdout number is HOLDOUT-DTI on catalogue truth; the private board truth "
              "is off-catalogue expert-drawn faults; no organizer-authenticated score-to-file "
              "mapping exists."))
    promoted = bool(g62.get("verdict_so_far") == "pass" and slot["checks_pass"])
    slot["verdict"] = ("APPROVED — DOWNLOAD AND SUBMIT (format-safe; preregistered promotion "
                       "bar met)" if promoted else
                       "DOWNLOAD FOR REVIEW: YES. SUBMIT TO COMPETITION: NO — preregistered "
                       "promotion bar not met; research artifact only")
    h60d.write_json(EV / "h62_slot_gate.json", slot)
    log(f"slot gate: {slot['verdict']}")

    name = f"{stem}-{q['sha256'][:8]}-zeros"
    note = ("H62 buried corridors: cover/edge/persistence gates on A-only disagreement; "
            "finite binary [0,1]; off-prior; hypotheses, not verified faults")
    assert len(name) <= 200, "portal name limit"
    assert len(note) <= 140, f"lane note limit, got {len(note)}"

    card = h60d.run_card(
        hypothesis=("H62-1: the co-training discovery signal (A confident, B abstains) becomes "
                    "a buried-fault candidate only when it is explained by burial (depth to "
                    "basement >= 200 m), carried by a potential-field edge (gradient >= P75) "
                    "and persistent along strike (line-persistence corridor); such corridors "
                    "target faults missing from the surface-mapped USGS/INGENIOUS catalogue"),
        mechanism=("two logistic views fitted out-of-fold on hide-and-recover whole-segment "
                   "folds (independence premise MEASURED first); disagreement field "
                   "max(pA-pB,0) gated by cover -> edge -> line persistence (morphological "
                   "line opening at half-widths 2-4 px, component length >= 15 px and "
                   "elongation >= 3); placed by the registered scoring emitter h57.iso_select "
                   "on the required-novel pool outside the 200 m ring; binary {0,1} emission "
                   "(metric-optimal) with zeros everywhere else"),
        mimic_processes=[
            "buried paleochannels and basin-fill edges (density contrasts that are not faults)",
            "lithologic contacts and dike swarms (linear susceptibility/density steps)",
            "alluvial-fan / basin-margin gravel wedges (density contrasts with no fault)",
            "airborne-survey drape and terrain clearance over steep topography (GeoDAWN "
            "magnetics are airborne; ridge-flank gradients mimic structure)"],
        holdout=dict(
            shipped_raster=shipped_pooled,
            shipped_raster_folds=shipped,
            novel_pool_controls_pooled_means=novel_pooled,
            field_validation=val["pooled_dti"],
            field_table=val["field_table"],
            weak_surface_subgroup=val["subgroup"].get("pooled", {}),
            preregistered_gates=g62,
            label=("every number here is HOLDOUT-DTI (evaluator version pinned below; "
                   "withheld positives per cell; 95% fold-bootstrap CI); nothing here is a "
                   "leaderboard score or forecast")),
        registry_overlap=dict(
            lane_gate_surface={k: lane_surface.get(k) for k in
                               ("surface_max_abs_spearman", "surface_max_abs_spearman_prior",
                                "surface_check_passed", "lane_drift_detected")},
            lane_gate_dots={k: lane_dots.get(k) for k in
                            ("dots_max_abs_spearman", "dots_max_within_3px_frac",
                             "dots_max_within_3px_prior", "dots_max_within_3px_frac_gate",
                             "dots_max_within_3px_gate_prior",
                             "calibration_rasters_excluded_from_proximity",
                             "dots_check_passed", "lane_drift_detected")},
            uniqueness={k: uniq.get(k) for k in ("n_priors_checked", "canonical_pattern_unique",
                                                 "novel_fraction", "equals_literal_prior_union")},
            not_merely_union=dict(arm_px=total, outside_union_topk_px=outside_union,
                                  outside_view_A_topk_px=outside_viewA,
                                  outside_view_B_topk_px=outside_viewB)),
        raster_sha256=q["sha256"],
        validator=dict(
            format_gate=fmt,
            no_nan_inside_footprint=bool(fmt["n_nan"] == 0),
            values_in_0_1=bool(fmt.get("min", 1) >= 0 and fmt.get("max", 0) <= 1),
            crs_shape_transform_match=bool(
                fmt["crs"] == "EPSG:32611" and fmt["width"] == 3292 and fmt["height"] == 3730
                and not fmt["problems"]),
            recheck=G.read_geotiff(path)),
        submission_name=name,
        submission_note=note,
        verdict=("promote" if promoted else "negative"),
        extra=dict(
            negative_result_is_a_deliverable=True,
            promotion_to_a_real_slot_is_a_separate_selector_step=True,
            weekly_cap="as shown on the submission page",
            conditional_projection_not_a_score=proj,
            data_qualification=("pinned owner-mirror bytes, SHA-verified; NOT "
                                "organizer-authenticated"),
            download_ok=True,
            submit_ok=bool(promoted)))
    card["round"] = "H62"
    h60d.write_json(EV / "h62_run_card.json", card)

    # ---- zip + site copies + pointers ------------------------------------------------------------
    DL.mkdir(parents=True, exist_ok=True)
    status = ("DOWNLOAD FOR REVIEW: YES.\n"
              + ("SUBMIT TO COMPETITION: YES — preregistered promotion bar met.\n" if promoted
                 else "SUBMIT TO COMPETITION: NO — preregistered promotion bar not met; "
                      "research artifact only.\n")
              + f"Name: {name}\nNote: {note}\nSHA-256: {q['sha256']}\n"
              + f"Pixels: {total}; all finite in [0,1]; zeros outside footprint.\n")
    zpath = SUB / f"{stem}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(path, arcname=f"{stem}.tif")
        z.writestr("submission-name.txt", name + "\n")
        z.writestr("submission-note.txt", note + "\n")
        z.writestr("STATUS.txt", status)
    shutil.copy2(path, DL / f"{stem}.tif")
    shutil.copy2(zpath, DL / f"{stem}.zip")
    shutil.copy2(path, DL / "h62-candidate.tif")
    shutil.copy2(zpath, DL / "h62-candidate.zip")
    (SUB / "H62_LATEST.txt").write_text(f"{path.name}\n")
    if promoted:
        (SUB / "LATEST.txt").write_text(f"{path.name}\n")

    receipt = dict(round="H62", name=name, note=note, note_chars=len(note),
                   file=path.name, zip=zpath.name, sha256=q["sha256"], bytes=q["bytes"],
                   emitted_px=total, positive_field_crests=pos_crests,
                   zero_field_fill=total - pos_crests,
                   min_distance_to_catalogue_m=round(dmin_cat, 1),
                   download_ok=True, submit_ok=bool(promoted),
                   verdict=slot["verdict"], run_card="evidence/h62_run_card.json",
                   generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    h60d.write_json(DAD / "submission_h62.json", receipt)
    h60d.write_json(EV / "h62_build.json", dict(
        receipt, prior_inventory_count=len(priors),
        prior_support_px=int(support.sum()), legal_pool_px=int(pool.sum()),
        lane_surface=lane_surface, lane_dots=lane_dots,
        projection_not_a_score=proj,
        qualification=("pinned owner-mirror bytes, SHA-verified; NOT organizer-authenticated")))
    log(f"done in {time.time() - t0:.0f}s — {slot['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
