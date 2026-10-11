#!/usr/bin/env python3
"""Historical H60D research builder, disabled under the terminal H75 stop.

H75 is the current DUPLICATE/STOP. This legacy builder is fail-closed while H75 is
published; it cannot be used to fit, rebuild, create a current run card, move any submission
pointer, authorize a slot, or provide portal instructions. Its archival ZIP format, if the
historical code path is ever reviewed in a separate authorized context, is a single TIFF only.

The frozen H60D receipts remain historical evidence; this module is not a current experiment
authorization. It must never change submission/LATEST.txt or any H60 pointer.
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

from gems52 import emit as E                       # noqa: E402
from gems52 import gates                            # noqa: E402
from gems52 import grid as G                       # noqa: E402
from gems52 import h57                              # noqa: E402
from gems52 import h60d                              # noqa: E402
from gems52 import holdout as HO                    # noqa: E402
from gems52 import metric as M                      # noqa: E402

DATA = ROOT / "work/pinned"
WORK = ROOT / "work/h60"
EV = ROOT / "evidence"
DL = ROOT / "docs/downloads"
DAD = ROOT / "docs/data"
BUDGET = 37654            # registered decision budget (matched across every arm)
DTI_PROJECTED = 0.0       # fixed matched budget, identical to the validation emitter
CHAMPION_OWNER_REPORTED = 0.2778   # owner-reported h33-2-b2 score; used ONLY to report the
                                   # marginal acceptance radius, never as a fit input


def log(m: str) -> None:
    print(f"[h60d-build {time.strftime('%H:%M:%S')}] {m}", flush=True)


def read_mask(path: Path, thresh: float = 0.5) -> np.ndarray:
    with rasterio.open(path) as src:
        a = src.read(1)
    a[~np.isfinite(a)] = 0.0
    return a > thresh


def prior_inventory(field: str, extra_roots=()):
    """Accessible aligned priors with this round's OWN outputs excluded.

    Self-exclusion is by the round's exact artifact pattern — BOTH published names of the
    round's own artifact: the portal name ``gems52-h60d-<field>-arm<N>px-<hash8>-zeros.tif``
    AND the canonical stem name ``gems52-h60d-<field>-arm<N>px.tif`` that `submission/` and
    `docs/downloads/` carry — plus the short-path copies.  Never a bare ``gems52-h60d-``
    prefix, because a parallel session's same-round artifact is a genuine prior (the H59
    lesson, IR-H59-004).  Without self-exclusion of BOTH names a rebuild sees its own
    previous TIFF in the support union and the arm drifts run-to-run (IR-H59-001; the
    stem-name miss is IR-H60D-002 — the lane gate fired on the round's own previous build
    at 90.4 % within-3px before the pattern was widened).
    """
    roots = [r for r in extra_roots if Path(r).exists()]
    found = gates.find_priors(roots)
    own_re = re.compile(
        rf"^gems52-h60d-{re.escape(field)}-arm\d+px(-[0-9a-f]{{8}}-zeros)?\.tif$")
    keep = []
    for p in found:
        n = Path(p).name
        if n in ("h60d-candidate.tif", "h60d-candidate.zip", "STATUS.txt"):
            continue
        if own_re.match(n):
            continue
        keep.append(p)
    return keep


def h75_stop_is_current() -> bool:
    home = ROOT / "docs" / "index.html"
    status = ROOT / "docs" / "h75-executive-summary.html"
    return (home.is_file() and status.is_file()
            and "H75: DUPLICATE/STOP" in home.read_text(errors="replace")
            and "DUPLICATE/STOP · RESEARCH ONLY · NOT FOR SUBMISSION" in status.read_text(errors="replace"))


def main() -> int:
    if h75_stop_is_current():
        print("H75 terminal DUPLICATE/STOP is current; H60D historical builder exited before any fit, output, ZIP, or pointer write")
        return 0
    t0 = time.time()
    valid = G.footprint_from(DATA / "training_features.tif", bands="all")
    with rasterio.open(DATA / "labels.tif") as src:
        cat = src.read(1) == 1
    with rasterio.open(DATA / "sample_submission.tif") as src:
        valid_sub = np.isfinite(src.read(1))

    pa = np.nan_to_num(np.load(WORK / "pa_oof.npy"), nan=0.0).astype(np.float32)
    pb = np.nan_to_num(np.load(WORK / "pb_oof.npy"), nan=0.0).astype(np.float32)
    cotrain_receipt = json.loads((EV / "h60d_cotrain.json").read_text())
    strata_counts = cotrain_receipt["strata"]["counts"]
    depth_medians = cotrain_receipt["strata"]["median_depth_to_basement_m"]
    a_only = np.load(WORK / "stratum_a_only.npy")
    b_only = np.load(WORK / "stratum_b_only.npy")
    strat_conc = np.load(WORK / "stratum_concordant.npy")

    promoted = (WORK / "promoted_field.txt").read_text().strip()
    fields = {
        "view_A": pa,
        "view_B": pb,
        "clf_union": np.maximum(pa, pb),
        "dis_product": h60d.dis_product(pa, pb),
        "dis_contrast": h60d.dis_contrast(pa, pb),
        "dis_B_product": h60d.dis_b_product(pa, pb),
    }
    if promoted not in fields:
        raise SystemExit(f"unexpected promoted field {promoted!r}")
    field_arr = fields[promoted]
    saved = WORK / f"field_{promoted}.npy"
    if saved.exists():
        agree = float(np.corrcoef(np.load(saved).ravel(), field_arr.ravel())[0, 1])
        log(f"shipped field recomputed from the OOF bytes; agreement with the validated "
            f"cache pearson {agree:.6f}")

    val = json.loads((EV / "h60d_validation.json").read_text())
    promoted_any = bool(val["promoted_any"])

    priors = prior_inventory(promoted, [str(ROOT / "submission"), str(DL), str(ROOT / "docs"),
                                       str(DATA / "scored"), str(DATA / "reference")])
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
    lane_surface = h60d.lane_drift_report(field_arr, None, priors, valid,
                                         sample=DATA / "sample_submission.tif",
                                         calibration=h60d.calibration_basenames(
                                             ROOT / "registry/data_manifest.json"))
    h60d.write_json(EV / "h60d_lane_surface.json", lane_surface)
    log(f"lane gate on surface: max|rho|={lane_surface['surface_max_abs_spearman']} "
        f"(bar {lane_surface['max_rank_corr']}) -> "
        f"{'DRIFT' if lane_surface['lane_drift_detected'] else 'clean'}")
    if lane_surface["lane_drift_detected"]:
        h60d.write_json(EV / "h60d_run_card.json", h60d.run_card(
            hypothesis="co-training disagreement discovery (H60-1/2)",
            mechanism="pA*(1-pB) / max(pA-pB,0) ranking of buried-under-cover candidates",
            mimic_processes=["alluvial-fan gravel wedges", "airborne drape over steep terrain",
                             "anthropogenic compaction", "salinity boundaries"],
            holdout=val["pooled_dti"].get(f"hide@{BUDGET}|{promoted}", {}),
            registry_overlap=lane_surface,
            raster_sha256="", validator={},
            verdict="negative — DUPLICATE LANE: surface rank correlation exceeded the "
                    "registered 0.90 bar; logged as duplicate and stopped before placement"))
        raise SystemExit("lane drift on the ranking surface: logged as duplicate and stopped")

    # ---- placement (registered correction H60-5) ----------------------------------------------
    # SHIPPED emitter = the registered SCORING emitter h57.iso_select (top-k, min_px 3.0
    # inclusive, nms_px 5) — the same emitter that produced every registered field read and
    # the H57 champion artifact — so the shipped raster externalizes the MEASURED field.
    # The originally preregistered greedy_emit coverage surrogate is retained as a DISCLOSED
    # DIAGNOSTIC: this round's placement measurement showed it selects the field's
    # broad-plateau mass on the required-novel pool, which is anti-correlated with the
    # holdout truth (see knowledge/30, correction H60-5).  Both placements are emitted and scored.
    density = np.where(pool, field_arr, 0.0).astype(np.float32)
    density = np.maximum(density, 0.0)
    arm = h57.iso_select(density, pool, BUDGET, min_px=3.0, nms_px=5)
    arm_b = arm > 0
    n_pos = int((pool & (field_arr > 0)).sum())
    pos_crests = int((arm_b & (field_arr > 0)).sum())
    greedy, stats = E.greedy_emit(density.ravel(), pool, DTI_PROJECTED, BUDGET,
                                  pool=400_000, log=lambda *a: None)
    greedy = (greedy.reshape(G.SHAPE) > 0)
    log(f"iso_select placed {int(arm_b.sum())} px (requested {BUDGET}); "
        f"{pos_crests} on positive-field crests, {int(arm_b.sum()) - pos_crests} zero-field "
        f"budget fill (pool positive-field px: {n_pos})")
    log(f"greedy_emit diagnostic placed {int(greedy.sum())} px; "
        f"marginal first {stats['marginal_first']:.5g} last {stats['marginal_last']:.5g}; "
        f"rejects_at_stop {stats['rejects_at_stop']}")

    # ---- not merely the union of the two views -------------------------------------------------
    union_field = np.maximum(pa, pb)
    u_density = np.maximum(np.where(pool, union_field, 0.0), 0.0).astype(np.float32)
    union_arm, _ = E.greedy_emit(u_density.ravel(), pool, DTI_PROJECTED, BUDGET,
                                 pool=400_000, log=lambda *a: None)
    union_arm = union_arm.reshape(G.SHAPE) > 0
    union_topk = h57.iso_select(np.where(pool, union_field, 0.0).astype(np.float32), pool,
                                BUDGET, min_px=3.0, nms_px=5)
    outside_union_greedy = int((arm_b & ~union_arm).sum())
    outside_union_topk = int((arm_b & ~union_topk).sum())
    log(f"not-merely-union: {outside_union_greedy}/{int(arm_b.sum())} px outside the union "
        f"field's greedy emission; {outside_union_topk} outside its iso top-k")

    # ---- assemble, clip, write ------------------------------------------------------------------
    arr = np.zeros(G.SHAPE, np.float32)
    arr[arm_b] = 1.0
    clipped = int(((arr > 0) & ~valid_sub).sum())
    arr[~valid_sub] = 0.0
    arm_b = arm_b & valid_sub
    total = int((arr > 0).sum())
    ys, xs = np.nonzero(arr > 0)
    dcat = ndimage.distance_transform_edt(~cat, sampling=G.PIXEL_M)
    dmin_cat = float(dcat[ys, xs].min()) if ys.size else float("nan")
    log(f"emitted {total} px; clipped {clipped} px to the sample-submission domain; "
        f"min distance to a mapped catalogue pixel {dmin_cat:.1f} m")

    stem = f"gems52-h60d-{promoted}-arm{total}px"
    path = ROOT / "submission" / f"{stem}.tif"
    q = G.write_geotiff(path, arr)
    log(f"wrote {path.name}: {q['bytes']} bytes, sha256 {q['sha256'][:16]}…")

    fmt = gates.format_report(path, DATA / "sample_submission.tif", footprint=valid_sub)
    uniq = gates.uniqueness_report(arr, priors)
    h60d.write_json(EV / "h60d_format_gate.json", fmt)
    h60d.write_json(EV / "h60d_uniqueness.json", uniq)
    log(f"format problems: {fmt['problems']}; pattern_unique={uniq['canonical_pattern_unique']}, "
        f"novel_frac={uniq['novel_fraction']:.4f}, n_priors={uniq['n_priors_checked']}")

    # ---- lane drift gate on the FINAL DOTS (lane protocol item 1) -------------------------------
    # H60-6 withdrawn: calibration classification is metadata, never a gate exemption
    # (manifest-driven; raw readings still reported; both Spearman components apply to all).
    calib = h60d.calibration_basenames(ROOT / "registry/data_manifest.json")
    lane_dots = h60d.lane_drift_report(field_arr, arm_b, priors, valid, calibration=calib,
                                        sample=DATA / "sample_submission.tif")
    h60d.write_json(EV / "h60d_lane_gate.json", lane_dots)
    log(f"lane gate on dots: max|rho|={lane_dots['dots_max_abs_spearman']}, "
        f"raw max within-3px frac={lane_dots['dots_max_within_3px_frac']} "
        f"(strict all-prior gate value: {lane_dots['dots_max_within_3px_frac_gate']}) -> "
        f"{'DRIFT' if lane_dots['lane_drift_detected'] else 'clean'}")
    if lane_dots["lane_drift_detected"]:
        h60d.write_json(EV / "h60d_run_card.json", h60d.run_card(
            hypothesis="co-training disagreement discovery (H60-1/2)",
            mechanism="pA*(1-pB) / max(pA-pB,0) ranking of buried-under-cover candidates",
            mimic_processes=["alluvial-fan gravel wedges", "airborne drape over steep terrain",
                             "anthropogenic compaction", "salinity boundaries"],
            holdout=val["pooled_dti"].get(f"hide@{BUDGET}|{promoted}", {}),
            registry_overlap=lane_dots,
            raster_sha256=q["sha256"], validator={},
            verdict="negative — DUPLICATE LANE: the lane-drift gate on the final dots "
                    "exceeded the registered thresholds; logged as duplicate and stopped "
                    "before shipping"))
        h60d.write_json(EV / "h60d_format_gate.json", fmt)
        h60d.write_json(EV / "h60d_uniqueness.json", uniq)
        raise SystemExit("lane drift on the final dots: logged as duplicate and stopped")

    # ---- score the SHIPPED raster on the holdout (the field is OOF, so this is proper) -----------
    # plus the matched novel-pool controls AND the greedy_emit diagnostic placement: the
    # shipped raster is restricted to pixels OUTSIDE every prior's support, while the
    # validation fields were scored on the full legal pool.  A random/union/view_B control
    # drawn from the SAME novel pool is the only honest reference for the shipped raster's
    # read — without it the number is uninterpretable (the simulator's structural blindness
    # to required-novel arms is documented in knowledge/18 s6, but the matched control
    # quantifies it for this pool).  The greedy diagnostic quantifies correction H60-5.
    shipped = []
    greedy_diag = []
    novel_controls = []
    rng_novel = np.random.default_rng(20261009)
    for mode in ("hide", "tip"):
        folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002,
                              seed=20261009, mode=mode)
        for f in folds:
            truth = f["truth"] & f["region"] & valid
            legal_novel = f["region"] & pool
            p = np.where(f["region"], arr, 0.0)
            p = HO.mask_visible(p, f["visible"] & valid)
            r = M.dti(p, truth)
            shipped.append(dict(mode=mode, fold=f["fold"], dti=round(float(r["dti"]), 6),
                                tpw=float(r["tpw"]), fpw=float(r["fpw"]), fnw=float(r["fnw"]),
                                n_truth=int(r["n_truth"]), emitted=int((p > 0).sum())))
            p = np.where(f["region"], greedy.astype(np.float32), 0.0)
            p = HO.mask_visible(p, f["visible"] & valid)
            r = M.dti(p, truth)
            greedy_diag.append(dict(mode=mode, fold=f["fold"],
                                    dti=round(float(r["dti"]), 6),
                                    n_truth=int(r["n_truth"]), emitted=int(greedy.sum())))
            flat_pool = np.flatnonzero(legal_novel.ravel())
            take = rng_novel.choice(flat_pool, min(BUDGET, flat_pool.size), replace=False)
            rnd = np.zeros(G.SHAPE, bool)
            rnd.ravel()[take] = True
            p = np.where(f["region"], rnd.astype(np.float32), 0.0)
            p = HO.mask_visible(p, f["visible"] & valid)
            r = M.dti(p, truth)
            novel_controls.append(dict(mode=mode, fold=f["fold"], arm="random_novelpool",
                                       dti=round(float(r["dti"]), 6), n_truth=int(r["n_truth"]),
                                       pool_px=int(legal_novel.sum())))
            for arm_name, fld in (("clf_union_novelpool", np.maximum(pa, pb)),
                                  ("view_B_novelpool", pb),
                                  ("dis_contrast_novelpool", field_arr)):
                score = np.where(legal_novel, fld, 0.0).astype(np.float32)
                nodes = h57.iso_select(score, legal_novel, BUDGET, min_px=3.0, nms_px=5)
                p = np.where(f["region"], nodes.astype(np.float32), 0.0)
                p = HO.mask_visible(p, f["visible"] & valid)
                r = M.dti(p, truth)
                novel_controls.append(dict(mode=mode, fold=f["fold"], arm=arm_name,
                                           dti=round(float(r["dti"]), 6),
                                           n_truth=int(r["n_truth"]),
                                           pool_px=int(legal_novel.sum())))
        log(f"shipped raster {mode}: " + ", ".join(
            f"f{r['fold']}={r['dti']:.6f}" for r in shipped if r["mode"] == mode))
        log(f"novel-pool controls {mode}: " + ", ".join(
            f"{r['arm']}={r['dti']:.6f}" for r in novel_controls
            if r["mode"] == mode and r["fold"] == folds[-1]["fold"]))
    novel_pooled = {}
    for mode in ("hide", "tip"):
        for arm_name in ("random_novelpool", "clf_union_novelpool", "view_B_novelpool",
                          "dis_contrast_novelpool"):
            rs = [r for r in novel_controls if r["mode"] == mode and r["arm"] == arm_name]
            if rs:
                novel_pooled[f"{mode}|{arm_name}"] = round(
                    float(np.mean([r["dti"] for r in rs])), 6)
    shipped_pooled, shipped_ci = {}, {}
    for mode in ("hide", "tip"):
        rs = [r for r in shipped if r["mode"] == mode]
        pl = h60d.pooled_dti(rs)
        ci = h60d.bootstrap_ci([r["dti"] for r in rs], n_boot=10000, seed=20261009)
        shipped_pooled[mode] = dict(
            pooled_dti=round(pl["dti"], 6), tpw=round(pl["tpw"], 2), fpw=round(pl["fpw"], 2),
            fnw=round(pl["fnw"], 2), n_truth=pl["n_truth"], fold_mean_dti=round(ci["mean"], 6),
            ci95_lo=round(ci["ci_lo"], 6), ci95_hi=round(ci["ci_hi"], 6),
            withheld_positives=pl["n_truth"],
            label="HOLDOUT-DTI of the SHIPPED raster (evaluator gems52.metric.dti alpha 0.2 "
                  "beta 0.8 R 300 m triangular lattice-exact; holdout.make_folds "
                  "whole-segment hide-and-recover, 4 folds, buffer 4 px, prevalence 0.002, "
                  "seed 20261009; pooled = metric components pooled across folds; CI = fold "
                  "bootstrap 10k resamples)")
    greedy_pooled = {}
    for mode in ("hide", "tip"):
        rs = [r["dti"] for r in greedy_diag if r["mode"] == mode]
        greedy_pooled[mode] = dict(
            fold_mean_dti=round(float(np.mean(rs)), 6),
            folds=[round(float(x), 6) for x in rs],
            label="HOLDOUT-DTI of the greedy_emit DIAGNOSTIC placement of the same field on "
                  "the same pool (correction H60-5: retained as a disclosed diagnostic; the "
                  "coverage surrogate selects the field's broad-plateau mass, which is "
                  "anti-correlated with the holdout truth on the required-novel pool)")

    # ---- per-emitted-pixel geological reasoning ---------------------------------------------------
    depth = G.read_band(DATA / "training_features.tif", 15)
    cond = G.read_band(DATA / "training_features.tif", 17)
    mag = G.read_band(DATA / "training_features.tif", 14)
    grav = G.read_band(DATA / "training_features.tif", 13)
    elev = G.read_band(DATA / "training_features.tif", 12)
    depth_sorted = np.sort(depth[permitted])
    tr = G.TRANSFORM

    def depth_pct(v):
        return 100.0 * np.searchsorted(depth_sorted, v) / depth_sorted.size

    field_note = {"dis_product": "pA*(1-pB) disagreement product",
                  "dis_contrast": "max(pA-pB,0) disagreement contrast",
                  "dis_B_product": "pB*(1-pA) B-only product",
                  "view_A": "View A alone", "view_B": "View B alone",
                  "clf_union": "max(pA,pB) union"}[promoted]

    def reason(r, c):
        pa_, pb_ = float(pa[r, c]), float(pb[r, c])
        d = float(depth[r, c]) if np.isfinite(depth[r, c]) else float("nan")
        parts = []
        if a_only[r, c]:
            parts.append(
                f"Buried-structure candidate (the lane's A-only disagreement): the geophysical "
                f"view is confident (p_A={pa_:.2f}) while the surface view abstains "
                f"(p_B={pb_:.2f}); the A-only stratum's median depth to basement is "
                f"{depth_medians['a_only']:.0f} m against {depth_medians['b_only']:.0f} m "
                f"for B-only (evidence/h60d_cotrain.json), so the reading is a fault trace masked "
                f"at the surface rather than absent")
        elif b_only[r, c]:
            parts.append(
                f"Surface-only candidate: p_B={pb_:.2f} with no geophysical support "
                f"(p_A={pa_:.2f}) — the lane's suspect population (road, canal levee, erosion "
                f"line, quarry face); emitted only because the shipped field still ranks it")
        elif strat_conc[r, c]:
            parts.append(f"Both views agree (p_A={pa_:.2f}, p_B={pb_:.2f}): independent "
                         f"surface and geophysical expression")
        else:
            parts.append(f"Sub-threshold shoulder (p_A={pa_:.2f}, p_B={pb_:.2f}): the strongest "
                         f"remaining part of the {field_note} field")
        if np.isfinite(d):
            dp = depth_pct(d)
            parts.append(f"depth to basement {d:.0f} m at the {dp:.0f}th footprint percentile "
                         f"({'deep' if dp > 70 else 'intermediate' if dp > 30 else 'shallow'} cover)")
        parts.append(f"isostatic gravity {float(grav[r, c]):.1f} mGal, TMI {float(mag[r, c]):.0f} nT, "
                     f"detrended elevation {float(elev[r, c]):+.0f} m, conductivity "
                     f"{float(cond[r, c]):.3f} S/m")
        parts.append(
            f"falsifier: Phase-2 review that finds intact undisturbed cover, no break in the "
            f"geophysical gradient within 300 m, or a DEM/road-layer match showing anthropogenic "
            f"fabric voids this candidate; it was emitted because it is "
            f"{float(dcat[r, c]):.0f} m from the nearest mapped catalogue pixel and outside "
            f"every accessible prior's support")
        return "; ".join(parts) + "."

    rows_out = []
    ay, ax = np.nonzero(arm_b)
    for i, (r, c) in enumerate(zip(ay, ax)):
        rows_out.append(dict(
            node_id=i, row=int(r), col=int(c),
            easting_m=round(tr[2] + (c + 0.5) * tr[0], 1),
            northing_m=round(tr[5] + (r + 0.5) * tr[4], 1),
            p_view_A=round(float(pa[r, c]), 4), p_view_B=round(float(pb[r, c]), 4),
            shipped_field_score=round(float(field_arr[r, c]), 4),
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
    csv_path = EV / f"gems52-h60d-{total}px-candidate-geology.csv"
    with csv_path.open("w", newline="") as f:
        f.write("# H60 disagreement-arm candidates, one written geological reasoning row per "
                "emitted pixel. View A = potential-field and subsurface bands; View B = surface "
                "bands + restored LiDAR/radiometric proxies. Every row is a HYPOTHESIS for "
                "Phase-2 geological review — an unverified fault candidate, not a discovery. "
                "Inputs: SHA-pinned owner-mirror bytes (not organizer-authenticated).\n")
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        for row in rows_out:
            w.writerow(row)
    log(f"wrote {csv_path.name} ({len(rows_out)} rows)")

    # ---- A-only candidate SEGMENTS (the brief: reasoning for EVERY A-only candidate) ------------
    # Vectorised per-segment statistics: pixels are grouped once (argsort + searchsorted over
    # the candidate pixels only) and every segment's stats are slices of those grouped
    # arrays.  A per-segment ``comp == sid`` full-grid scan would cost ncomp x 12.28M cell
    # visits — measured at 11,695 segments x 12.28M = 143.6 G visits for this round, which
    # is what hung the first build attempt (IR-H60-001).
    cand = a_only & pool
    comp, ncomp = ndimage.label(cand, structure=np.ones((3, 3), bool))
    seg_rows = []
    if ncomp:
        yy, xx = np.nonzero(comp)                      # candidate pixels, row-major
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
                    f"A-only whole-segment candidate ({int(sizes[sid - 1])} px, 8-connected): "
                    f"the potential-field view supports structure here (p_A>=0.60) while the "
                    f"surface view abstains (p_B<=0.40); median depth to basement {dmed:.0f} m "
                    f"means the trace is plausibly masked by cover — exactly the disagreement "
                    f"regime the lane defines as the discovery signal. Nearest mapped catalogue "
                    f"pixel is {dmin:.0f} m away, so this is off-catalogue by construction. "
                    f"Falsifier: trenching or review that finds intact, undisturbed cover and "
                    f"no gradient break within 300 m; or a DEM/road-layer match that shows the "
                    f"linear fabric is anthropogenic."),
            ))
    seg_path = EV / "gems52-h60d-a-only-candidate-segments.csv"
    with seg_path.open("w", newline="") as f:
        f.write("# H60 A-only candidate dossier: every whole 8-connected segment of the A-only "
                "population inside the legal pool, ranked by mean shipped-field mass; one "
                "written reasoning + explicit falsifier per segment. HYPOTHESES for Phase-2 "
                "review, not verified faults.\n")
        if seg_rows:
            w = csv.DictWriter(f, fieldnames=list(seg_rows[0].keys()))
            w.writeheader()
            for row in seg_rows:
                w.writerow(row)
    log(f"wrote {seg_path.name} ({len(seg_rows)} segment rows of {ncomp} A-only segments)")

    # ---- conditional projection (owner-reported inputs; NOT a forecast) --------------------------
    g_est = 14088.7
    proj = {}
    for rho in (0.03, 0.05, 0.07, 0.09, 0.12, 0.14):
        T = min(rho * total, g_est)
        proj[f"rho_{rho}"] = round(float(5.0 * T / (total + 4 * g_est)), 4)
    bar = M.credit_bar(CHAMPION_OWNER_REPORTED)
    # bar_to_max_distance_px returns PIXELS (R_PX = 3.0); the metre radius is that x 100 m.
    # (The first build logged the pixel value under a metre label — unit bug, fixed here.)
    accept_radius_m = float(M.bar_to_max_distance_px(bar)) * G.PIXEL_M
    log(f"projection by rho (conditional, owner-reported inputs): {proj}; "
        f"marginal acceptance radius at the owner-reported 0.2778: "
        f"{accept_radius_m:.1f} m")

    # ---- slot gate + run card ---------------------------------------------------------------------
    g = val["gates"].get(promoted, {})
    checks = {
        "R4 format gate (single band, float32, EPSG:32611, 3730x3292, transform, all finite, "
        "[0,1], no nodata, no mass outside footprint)": bool(not fmt["problems"]),
        "R5 decoded pattern differs from every accessible aligned prior":
            bool(uniq["canonical_pattern_unique"]),
        "R5 support novelty gate (>=20%)": bool(uniq["support_novelty_gate_ok"]),
        "lane drift gate on the surface (max|rho| <= 0.90)":
            bool(lane_surface["surface_check_passed"]),
        "lane drift gate on the final dots (max|rho| <= 0.90 and <=70% within 3 px)":
            bool(lane_dots["dots_check_passed"]),
        "R6 artifact is not the top-k of the plain union of the two views":
            bool(outside_union_greedy > 0 or outside_union_topk > 0),
        "R6 artifact is not any prior and not any pair-union of priors":
            bool(not uniq["equals_literal_prior_union"]),
        "R3 nothing emitted inside the <=200 m catalogue ring": bool(dmin_cat >= 200.0),
        "R2 independence measured and non-degenerate (exchange licensed)": bool(
            json.loads((EV / "h60d_cotrain.json").read_text())["independence"]["measured"]),
        "leakage canary clean (no layer AUC > 0.90)": bool(
            not json.loads((EV / "h60d_cotrain.json").read_text())["leakage_canary"]["leakage_detected"]),
        "R7 one written geological reasoning per emitted pixel": bool(len(rows_out) == total),
        "R7b every A-only candidate segment in the legal pool has written reasoning":
            bool(len(seg_rows) >= 1),
    }
    slot = dict(
        shipped_field=promoted, promotion_met=promoted_any, gates={promoted: g},
        slot_bar_met=bool(g.get("slot_bar_met")),
        checks=checks, checks_pass=all(checks.values()),
        shipped_raster_holdout=shipped_pooled,
        note=("No organizer-authenticated score-to-file mapping exists; every leaderboard "
              "number quoted in this repository is owner-reported; the holdout simulator is "
              "a relative instrument, not a leaderboard proxy."))
    slot["verdict"] = "HISTORICAL RESEARCH ONLY · NOT FOR SUBMISSION · H75 TERMINAL STOP"
    slot["approved_for_submission"] = False
    slot["approved_for_weekly_slot"] = False
    slot["historical_gate_result_only"] = True
    h60d.write_json(EV / "h60d_slot_gate.json", slot)
    approved = False
    log(f"slot gate: {slot['verdict']}")

    name = f"{stem}-{q['sha256'][:8]}-zeros"

    # ---- run card (lane protocol item 5) -----------------------------------------------------------
    card = h60d.run_card(
        hypothesis=("H60-1/H60-2: the disagreement between the geophysical view (A) and the "
                    "surface view (B) is the discovery signal — where A is confident and B "
                    "abstains, a fault may be buried beneath cover and absent from the "
                    "USGS/INGENIOUS catalogue; the shipped field is the disagreement "
                    f"'{promoted}'"),
        mechanism=("two logistic views fitted out-of-fold on hide-and-recover whole-segment "
                   "folds (independence premise measured, exchange licensed); the ranking "
                   "field is the disagreement product/contrast, NOT the union; the artifact "
                   "is the top-k of that field (registered scoring emitter h57.iso_select, "
                   "correction H60-5) outside the 200 m ring and all prior support — the "
                   "preregistered greedy_emit coverage placement is retained as a scored "
                   "diagnostic and was anti-correlated with the holdout truth on this pool"),
        mimic_processes=[
            "alluvial-fan / basin-margin gravel wedges (density and susceptibility contrasts "
            "with no fault)",
            "airborne-survey drape and terrain clearance over steep topography (GeoDAWN "
            "magnetics are airborne; ridge-flank gradients mimic structure)",
            "anthropogenic compaction (roads, canal levees) — conductivity/strain anomalies "
            "with no fault",
            "groundwater salinity boundaries — surface-conductivity steps unrelated to "
            "faulting"],
        holdout=dict(
            shipped_raster=shipped_pooled,
            shipped_raster_folds=shipped,
            greedy_diagnostic_holdout=greedy_pooled,
            novel_pool_controls_pooled_means=novel_pooled,
            field_validation=val["pooled_dti"].get(f"hide@{BUDGET}|{promoted}"),
            field_table_hide=val["field_table"].get(f"hide@{BUDGET}"),
            field_table_tip=val["field_table"].get(f"tip@{BUDGET}"),
            gates={promoted: g},
            cotreatment=val.get("cotreatment"),
            cotreatment_control=json.loads((EV / "h60d_cotrain_control.json").read_text())["readout"],
            label=("every number here is HOLDOUT-DTI (evaluator version pinned below; "
                   "withheld positives per cell; 95% fold-bootstrap CI); nothing here is a "
                   "leaderboard score or forecast")),
        registry_overlap=dict(
            lane_gate_surface={k: lane_surface[k] for k in
                               ("surface_max_abs_spearman", "surface_max_abs_spearman_prior",
                                "surface_check_passed", "lane_drift_detected")},
            lane_gate_dots={k: lane_dots[k] for k in
                            ("dots_max_abs_spearman", "dots_max_within_3px_frac",
                             "dots_max_within_3px_prior", "dots_max_within_3px_frac_gate",
                             "dots_max_within_3px_gate_prior",
                             "calibration_rasters_excluded_from_proximity",
                             "dots_check_passed", "lane_drift_detected")},
            uniqueness={k: uniq[k] for k in ("n_priors_checked", "canonical_pattern_unique",
                                             "support_novelty_gate_ok", "novel_fraction",
                                             "equals_literal_prior_union")},
            not_merely_union=dict(
                outside_union_greedy_px=outside_union_greedy,
                outside_union_topk_px=outside_union_topk,
                arm_px=total)),
        raster_sha256=q["sha256"],
        validator=dict(
            format_gate=fmt,
            no_nan_inside_footprint=bool(fmt["n_nan"] == 0),
            values_in_0_1=bool(fmt.get("min", 1) >= 0 and fmt.get("max", 0) <= 1),
            crs_shape_transform_match=bool(
                fmt["crs"] == "EPSG:32611" and fmt["width"] == 3292 and fmt["height"] == 3730
                and not fmt["problems"]),
            recheck=G.read_geotiff(path)),
        verdict="historical research only — H75 terminal stop; NOT FOR SUBMISSION",
        extra=dict(
            negative_result_is_a_deliverable=True,
            promotion_to_a_real_slot_is_a_separate_selector_step=True,
            weekly_cap="as shown on the submission page",
            projection_by_rho_conditional=proj,
            champion_owner_reported=CHAMPION_OWNER_REPORTED,
            board_observation=dict(
                evidence_class="PUBLIC-LEADERBOARD observation",
                observed_utc="2026-10-09T20:18:00Z",
                observed_top_score=0.3774,
                observed_top_rank=1,
                observed_subject_score=0.2778,
                observed_subject_rank=17,
                subject="extradr19",
                rows_complete=False,
                no_tiff_hash_or_organizer_receipt=True,
                note="Team-level observation only; file association remains owner-reported."),
            preregistration=dict(
                document="knowledge/30_hypotheses_H60D_preregistered.md",
                sha256_frozen=("6ce875d384d4344bdd8a668bd7670fc5259b74f19059fb3b8b05c16"
                               "ca5257d60"),
                sha256_amended=(json.loads((ROOT / "registry/h60d_preregistration.json")
                                           .read_text())
                                ["hypothesis_document_sha256_amended"]),
                registered_corrections=[
                    "H60-5: artifact placed by the registered scoring emitter "
                    "h57.iso_select instead of greedy_emit (placement diagnostic "
                    "falsified the coverage surrogate on the required-novel pool); "
                    "no gate outcome changes",
                    "H60-6: the lane-drift 3-px proximity component excludes "
                    "calibration rasters (registry/data_manifest.json ids calib_* / "
                    "inputs/calibration/* — owner-supplied metric-calibration inputs "
                    "such as the dense regular 5-px lattice whose dilation covers "
                    "about half the grid, so any pool placement reads 70-84% against "
                    "it by geometry, not duplication); raw readings still reported; "
                    "both Spearman components apply to every prior"]),
            score_evidence_limit=("0.2778 is a dated team-level public-board observation, not the highest public score or an organizer-confirmed TIFF score; the file association is owner-reported. The 0.2600-to-0.2778 byte comparison is not causal. Projections are conditional arithmetic, never scores.")))
    h60d.write_json(EV / "h60d_run_card.json", card)
    log(f"run card verdict: {card['verdict']}")

    # ---- identifiers, copies, one-click zip, pointers, receipts ----------------------------------
    DL.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, DL / path.name)
    zf = ROOT / "submission" / f"{stem}.zip"
    with zipfile.ZipFile(zf, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(path, path.name)
    shutil.copy2(zf, DL / zf.name)
    shutil.copy2(path, DL / "h60d-candidate.tif")
    shutil.copy2(zf, DL / "h60d-candidate.zip")
    shutil.copy2(csv_path, DL / csv_path.name)
    shutil.copy2(seg_path, DL / seg_path.name)
    zip_stats = dict(bytes=zf.stat().st_size, sha256=hashlib.sha256(zf.read_bytes()).hexdigest(),
                     contents=[i.filename for i in zipfile.ZipFile(zf).infolist()])
    log("historical artifact only; no H60D or global submission pointer is changed")

    receipt = dict(
        round="H60D", lane="co-training, disagreement as the discovery signal",
        file=path.name, stem=stem,
        bytes=int(q["bytes"]), sha256=q["sha256"], nonzero_px=total, verdict=slot["verdict"],
        artifact_status="HISTORICAL RESEARCH ONLY · NOT FOR SUBMISSION",
        approved_for_submission=False, approved_for_weekly_slot=False,
        historical_gate_result=dict(slot_bar_met=bool(slot["slot_bar_met"]), checks_pass=bool(slot["checks_pass"])),
        promoted_field=promoted,
        promotion_met=promoted_any, submission_slots_used=0,
        placement=("h57.iso_select top-k (min_px 3.0 inclusive, nms_px 5) — the registered "
                   "scoring emitter (registered correction H60-5: the preregistered "
                   "greedy_emit coverage surrogate selects the field's broad-plateau mass, "
                   "which is anti-correlated with the holdout truth on the required-novel "
                   "pool); greedy_emit retained as a scored diagnostic"),
        emitter=("h57.iso_select", dict(min_px=3.0, nms_px=5, budget=BUDGET,
                                        positive_field_crests=pos_crests,
                                        zero_field_budget_fill=int(arm_b.sum()) - pos_crests,
                                        pool_positive_field_px=n_pos)),
        greedy_diagnostic=dict(emitter="gems52.emit.greedy_emit", stats=stats,
                               holdout=greedy_pooled,
                               greedy_dots=int(greedy.sum())),
        not_merely_union=dict(outside_union_greedy_px=outside_union_greedy,
                              outside_union_topk_px=outside_union_topk),
        format=fmt, uniqueness=dict(n_priors_checked=uniq["n_priors_checked"],
                                    canonical_pattern_unique=uniq["canonical_pattern_unique"],
                                    support_novelty_gate_ok=uniq["support_novelty_gate_ok"],
                                    novel_fraction=uniq["novel_fraction"],
                                    equals_literal_prior_union=uniq["equals_literal_prior_union"]),
        lane_gate=dict(surface=lane_surface, dots=lane_dots),
        shipped_raster_holdout=shipped_pooled, shipped_raster_folds=shipped,
        novel_pool_controls=novel_controls, novel_pool_pooled_means=novel_pooled,
        projection_by_rho_conditional=proj,
        marginal_acceptance_radius_at_owner_reported_0278_m=round(accept_radius_m, 1),
        receipts=["h60d_preflight_integrity.json", "h60d_cotrain.json", "h60d_cotrain_control.json",
                  "h60d_validation.json", "h60d_build.json", "h60d_format_gate.json",
                  "h60d_uniqueness.json", "h60d_lane_gate.json", "h60d_slot_gate.json",
                  "h60d_run_card.json"],
        candidate_geology_dossier=f"evidence/{csv_path.name}",
        a_only_segment_dossier=f"evidence/{seg_path.name}",
        official_score_status="no portal upload or organizer score is recorded",
        download=f"downloads/{path.name}", download_zip=f"downloads/{zf.name}", zip=zip_stats,
        runtime_s=round(time.time() - t0, 1),
        min_distance_to_catalogue_m=round(dmin_cat, 1),
        clipping_to_sample_domain_px=clipped,
        strata_counts_recomputed=strata_counts)
    h60d.write_json(EV / "h60d_build.json", receipt)
    (DAD / "submission_h60d.json").write_text(json.dumps(
        {**{k: v for k, v in receipt.items() if k not in ("format", "runtime_s")},
         "download": f"downloads/{path.name}", "approved_for_submission": False,
         "approved_for_weekly_slot": False},
        indent=2, allow_nan=False, default=str) + "\n")
    for nm in ("h60d_build", "h60d_format_gate", "h60d_uniqueness", "h60d_lane_gate",
               "h60d_slot_gate", "h60d_run_card", "h60d_cotrain", "h60d_cotrain_control",
               "h60d_validation", "h60d_preflight_integrity", "h60d_lane_surface"):
        shutil.copy2(EV / f"{nm}.json", DAD / f"{nm}.json")
    shutil.copy2(ROOT / "registry/h60d_preregistration.json", DAD / "h60d_preregistration.json")
    log("receipts written; publication of H60 pages is scripts/publish_site_h60d.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
