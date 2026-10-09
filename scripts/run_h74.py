#!/usr/bin/env python3
"""H74 — conditional-sufficiency co-training ("B-core + A-rescue swap"), lane-feasible build.

Read ``knowledge/63_hypotheses_H74_preregistered.md`` first.  This runner recomputes that file's
SHA-256 against ``registry/h74_preregistration.json`` at start-up and refuses to run if it moved,
which is what "frozen before any fit" has to mean mechanically.

Lane: the brief's co-training paragraph (Blum & Mitchell, COLT '98, doi:10.1145/279943.279962).
View A = potential field / subsurface, View B = surface (DEM curvature + slope + radiometric),
disagreement = the discovery signal.

What is REUSED (not forked)
---------------------------
``scripts/run_h61.py``      setup (preregistration + data-pin verification, shared feature store,
                            label-blind quadrant folds, buffer 80 px), sample_train, learner,
                            predict_flat, to_grid, pct_rank
``gems52.spatial``          folds, negative_block_errors, independence, whole_pseudo_segments
``gems52.evaluate_holdout`` gems52-pooled-hide-v1 pooled DTI + paired 20 km cluster bootstrap
``gems52.nodes``            spacing_select (metric-aware placement, 3 px separation)
``gems52.gates``            format_report, uniqueness_report, lane_report (saturation policy)
``gems52.submission_writer``fail-closed GeoTIFF + single-TIFF ZIP + receipt

What is ROUND-SPECIFIC
----------------------
the conditional sufficiency test S1', the swap arms, the line-support arm, the registry consensus
pass, the lane-feasible placement, the reasoning CSV and the run card.

Stages (checkpointed under ``work/h74``; receipts under ``evidence/h74_*.json``)
    diag       E1  canary + fit + S1 + S1' + independence screen
    exchange   E2a one whole-segment confident-to-abstaining pseudo-label round, then refit
    holdout    E2b matched-budget hide-and-recover: 6 controls + 3 swap arms + line-support arm
    registry        one pass over the prior census: coverage, universal-probe class, consensus map
    build      E3  stitch OOF -> shipped field -> lane-feasible placement -> gates -> GeoTIFF
    card            run card + reasoning CSV + site data

Usage:  python scripts/run_h74.py [diag|exchange|holdout|registry|build|all]

Nothing here produces an ORGANIZER-CONFIRMED number.  Every DTI printed is HOLDOUT-DTI.
"""
from __future__ import annotations

import argparse
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
from sklearn.metrics import roc_auc_score                             # noqa: E402

import run_h61 as base                                                # noqa: E402
from gems52 import evaluate_holdout as evaluator                      # noqa: E402
from gems52 import gates, nodes, spatial, submission_writer           # noqa: E402

WORK = ROOT / "work/h74"
EVID = ROOT / "evidence"
DOCS = ROOT / "docs/data"
SUBM = ROOT / "submission"
DOWN = ROOT / "docs/downloads"
PRIORS = WORK / "priors"
REG_PATH = ROOT / "registry/h74_preregistration.json"
PREFIX = "gems52-h74-"
SEED = base.SEED
T0 = time.time()

CONTROL_ARMS = ("single_A", "single_B", "union_max", "disagreement_pre", "disagreement_post", "random")
SWAP_FRACTIONS = (0.10, 0.25, 0.50)


def log(*a):
    print(f"[{time.time() - T0:8.1f}s]", *a, flush=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    return str(o)


def write_ev(name: str, obj) -> Path:
    EVID.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    p = EVID / f"h74_{name}.json"
    p.write_text(json.dumps(obj, indent=1, allow_nan=False, default=_json_default) + "\n")
    (DOCS / f"h74_{name}.json").write_text(p.read_text())
    return p


def sha_file(p) -> str:
    h = hashlib.sha256()
    with Path(p).open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def check_prereg() -> dict:
    reg = json.loads(REG_PATH.read_text())
    doc = ROOT / reg["hypothesis_document"]
    got = sha_file(doc)
    if got != reg["hypothesis_sha256"]:
        raise SystemExit(f"FROZEN PREREGISTRATION MOVED: {doc}\n  pinned {reg['hypothesis_sha256']}\n"
                         f"  actual {got}\nRefusing to run.")
    log(f"preregistration verified: {doc.name} sha256 {got[:16]}…")
    return reg


# =================================================================================================
# shared setup
# =================================================================================================
def setup():
    """Shared H61 setup: verifies the H61 preregistration, the three data pins, the feature store
    version and the disjointness of the two views, then builds the label-blind quadrant folds."""
    h61_reg, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    log(f"store {store.manifest['version']} | eligible {int(eligible.sum())} px | "
        f"View A {len(va)} ch | View B {len(vb)} ch | catalogue {int(cat.sum())} px | ring {ring_px} px")
    return h61_reg, store, cat, eligible, folds, va, vb, ring_px


def allowed_domain(fold, ring_px):
    """Label-blind emission domain: the fold's own region, off the VISIBLE catalogue, outside the
    200 m visible-catalogue ring.  Hidden component geometry is never used here."""
    vis_dist = ndi.distance_transform_edt(~fold["visible"])
    out = fold["region"] & ~fold["visible"] & (vis_dist > ring_px)
    del vis_dist
    return out


# =================================================================================================
# E1 — canary, fit, sufficiency (S1 and the new conditional S1'), independence
# =================================================================================================
def stage_diag(reg):
    th = reg["thresholds"]
    h61_reg, store, cat, eligible, folds, va, vb, ring_px = setup()
    WORK.mkdir(parents=True, exist_ok=True)
    flat, inv = store.flat_idx, store.inverse
    rng = np.random.default_rng(SEED)
    names = list(va) + list(vb)

    # ---------- leakage canary: every feature alone, per fold -------------------------------------
    canary = dict(stage="canary", started_utc=now(), alarm_auc=th["canary_auc_alarm"],
                  evidence_class="LEAKAGE-CANARY AUC (diagnostic, not a DTI score)",
                  n_features=len(names), folds=[])
    worst = []
    catd_all = ndi.distance_transform_edt(~cat)
    for fold in folds:
        pos_grid = np.flatnonzero((fold["truth"] & fold["region"]).ravel())
        neg_grid = np.flatnonzero((fold["region"] & ~cat & (catd_all > 5)).ravel())
        pos = inv[pos_grid]
        neg = inv[neg_grid]
        pos = pos[pos >= 0]
        neg = neg[neg >= 0]
        neg = rng.choice(neg, size=min(200_000, neg.size), replace=False)
        rows = np.concatenate([flat[pos], flat[neg]])
        y = np.concatenate([np.ones(pos.size, np.int8), np.zeros(neg.size, np.int8)])
        rec = dict(fold=fold["fold"], n_pos=int(pos.size), n_neg=int(neg.size), features={})
        for nm in names:
            x = store.gather(rows, [nm])[:, 0]
            a = float(roc_auc_score(y, x))
            a = max(a, 1.0 - a)            # direction-insensitive: a perfectly inverted leak still leaks
            rec["features"][nm] = round(a, 6)
            worst.append((a, nm, fold["fold"]))
        canary["folds"].append(rec)
        log(f"canary fold {fold['fold']}: max {max(rec['features'].values()):.4f}")
    worst.sort(reverse=True)
    canary.update(finished_utc=now(), max_auc=worst[0][0], max_feature=worst[0][1],
                  max_fold=worst[0][2], top10=[dict(auc=round(a, 6), feature=n, fold=f)
                                               for a, n, f in worst[:10]],
                  any_alarm=bool(worst[0][0] > th["canary_auc_alarm"]),
                  rule="a single raw feature above the alarm AUC means leakage until proven otherwise")
    write_ev("canary", canary)
    log(f"CANARY max {worst[0][0]:.4f} ({worst[0][1]}) alarm={canary['any_alarm']}")
    if canary["any_alarm"]:
        raise SystemExit("leakage canary fired; stop and investigate before any holdout number")

    # ---------- fit both views per fold -----------------------------------------------------------
    fitrec = dict(stage="fit", started_utc=now(), folds=[],
                  learner="HistGradientBoostingClassifier(max_iter=250, lr=0.08, leaves=15, "
                          "min_samples_leaf=40, l2=1.0) — shared run_h61.learner")
    for fold in folds:
        f = fold["fold"]
        r = np.random.default_rng(SEED + f)
        rows, y = base.sample_train(fold, cat, r)
        rec = dict(fold=f, n_train=int(len(rows)), n_pos=int(y.sum()), views={})
        for view, cols in (("A", va), ("B", vb)):
            t = time.time()
            m = base.learner_for(view, SEED)
            m.fit(store.gather(rows, cols), y)
            p = base.predict_flat(store, m, cols, flat)
            np.save(WORK / f"pred_pre_{view}_f{f}.npy", p)
            # out-of-quadrant AUC on this fold's held truth vs its own catalogue-zero negatives
            pos_idx = inv[np.flatnonzero((fold["truth"] & fold["region"]).ravel())]
            neg_idx = inv[np.flatnonzero((fold["region"] & ~cat & (catd_all > 5)).ravel())]
            pos_idx, neg_idx = pos_idx[pos_idx >= 0], neg_idx[neg_idx >= 0]
            auc = float(roc_auc_score(np.r_[np.ones(len(pos_idx)), np.zeros(len(neg_idx))],
                                      np.r_[p[pos_idx], p[neg_idx]]))
            rec["views"][view] = dict(out_of_quadrant_auc=round(auc, 6),
                                      seconds=round(time.time() - t, 1), n_features=len(cols))
            log(f"fit fold {f} view {view}: out-of-quadrant AUC {auc:.4f} ({time.time()-t:.0f}s)")
        fitrec["folds"].append(rec)
    fitrec["finished_utc"] = now()
    write_ev("fit", fitrec)

    # ---------- S1 (global) and S1' (conditional on View B's blind band) --------------------------
    lo, hi = th["receiver_rank_interval"]
    s1 = dict(stage="sufficiency", started_utc=now(),
              evidence_class="PREMISE-AUC (diagnostic, not a DTI score)",
              bar_mean=0.60, bar_fold=0.55, blind_band=[lo, hi],
              bar_conditional=th["S1_conditional_blind_auc_min"],
              margin_required=th["S1_conditional_margin_min"], folds=[])
    for fold in folds:
        f = fold["fold"]
        pa = np.load(WORK / f"pred_pre_A_f{f}.npy")
        pb = np.load(WORK / f"pred_pre_B_f{f}.npy")
        reg_rows = inv[np.flatnonzero(fold["region"].ravel())]
        reg_rows = reg_rows[reg_rows >= 0]
        rb_region = base.pct_rank(pb[reg_rows])
        rb = np.full(pb.shape, np.nan, np.float32)
        rb[reg_rows] = rb_region
        pos_idx = inv[np.flatnonzero((fold["truth"] & fold["region"]).ravel())]
        neg_idx = inv[np.flatnonzero((fold["region"] & ~cat & (catd_all > 5)).ravel())]
        pos_idx, neg_idx = pos_idx[pos_idx >= 0], neg_idx[neg_idx >= 0]
        yy = np.r_[np.ones(len(pos_idx)), np.zeros(len(neg_idx))]
        auc_a = float(roc_auc_score(yy, np.r_[pa[pos_idx], pa[neg_idx]]))
        auc_b = float(roc_auc_score(yy, np.r_[pb[pos_idx], pb[neg_idx]]))
        # the conditional slice: truth pixels where the SURFACE view is blind (rank_B in [lo,hi])
        # or outright negative about them (rank_B < lo), measured against the SAME negatives.
        blind = (rb[pos_idx] >= lo) & (rb[pos_idx] <= hi)
        dark = rb[pos_idx] < lo
        bright = rb[pos_idx] > hi
        out = dict(fold=f, n_truth=int(len(pos_idx)), n_neg=int(len(neg_idx)),
                   auc_A_all=round(auc_a, 6), auc_B_all=round(auc_b, 6),
                   n_truth_blind=int(blind.sum()), n_truth_darkB=int(dark.sum()),
                   n_truth_brightB=int(bright.sum()))
        for tag, sel in (("blind", blind), ("darkB", dark), ("brightB", bright)):
            if sel.sum() < 50:
                out[f"auc_A_{tag}"] = None
                continue
            out[f"auc_A_{tag}"] = round(float(roc_auc_score(
                np.r_[np.ones(int(sel.sum())), np.zeros(len(neg_idx))],
                np.r_[pa[pos_idx[sel]], pa[neg_idx]])), 6)
        s1["folds"].append(out)
        log(f"S1 fold {f}: A {auc_a:.4f} B {auc_b:.4f} | A|blind {out.get('auc_A_blind')} "
            f"A|darkB {out.get('auc_A_darkB')} A|brightB {out.get('auc_A_brightB')}")
        del pa, pb, rb

    def _mean(key):
        v = [r[key] for r in s1["folds"] if r.get(key) is not None]
        return float(np.mean(v)) if v else None

    mean_all = _mean("auc_A_all")
    mean_blind = _mean("auc_A_blind")
    mean_bright = _mean("auc_A_brightB")
    mins = [r["auc_A_all"] for r in s1["folds"]]
    margin = (mean_blind - mean_bright) if (mean_blind is not None and mean_bright is not None) else None
    s1.update(finished_utc=now(),
              mean_auc_A=mean_all, min_fold_auc_A=float(np.min(mins)),
              mean_auc_B=_mean("auc_B_all"),
              mean_auc_A_blind=mean_blind, mean_auc_A_brightB=mean_bright,
              mean_auc_A_darkB=_mean("auc_A_darkB"),
              conditional_margin=margin,
              S1_global_pass=bool(mean_all is not None and mean_all >= 0.60
                                  and float(np.min(mins)) >= 0.55),
              S1_conditional_pass=bool(mean_blind is not None
                                       and mean_blind >= th["S1_conditional_blind_auc_min"]
                                       and margin is not None
                                       and margin >= th["S1_conditional_margin_min"]),
              interpretation=(
                  "S1_global repeats the gate that failed in H61/H63/H64/H65/H70. S1_conditional is "
                  "the new test: if View A is informative about mapped faults that the surface view "
                  "cannot see, its AUC restricted to blind-band truth must exceed both the bar and "
                  "its AUC on surface-expressed truth. Conditional AUCs are computed on a "
                  "label-selected subset and are a diagnostic, not an unbiased population estimate."))
    write_ev("sufficiency", s1)
    log(f"S1 global pass={s1['S1_global_pass']} (mean {mean_all}); "
        f"S1' conditional pass={s1['S1_conditional_pass']} (blind {mean_blind} vs bright {mean_bright})")

    # ---------- independence screen on held-out labelled negatives --------------------------------
    rows_blocks = []
    detail = []
    for fold in folds:
        f = fold["fold"]
        pa = base.to_grid(flat, np.load(WORK / f"pred_pre_A_f{f}.npy"), eligible.shape)
        pb = base.to_grid(flat, np.load(WORK / f"pred_pre_B_f{f}.npy"), eligible.shape)
        neg = fold["region"] & ~cat & (catd_all > 4) & np.isfinite(pa) & np.isfinite(pb)
        thresholds = (float(np.quantile(pa[neg], th["donor_rank_min"])),
                      float(np.quantile(pb[neg], th["donor_rank_min"])))
        blocks = spatial.negative_block_errors(np.nan_to_num(pa, nan=0.0), np.nan_to_num(pb, nan=0.0),
                                               neg, f, thresholds, side=th["block_side_px"], minimum=32)
        rows_blocks += blocks
        detail.append(dict(fold=f, n_negatives=int(neg.sum()), thresholds=list(thresholds),
                           n_blocks=len(blocks)))
        del pa, pb, neg
    indep = spatial.independence(rows_blocks, threshold=th["independence_abandon_max_abs_rho"],
                                 min_blocks=20)
    slim = {k: v for k, v in indep.items() if k != "blocks"}
    slim["per_fold"] = detail
    slim["evidence_class"] = "independence diagnostic on catalogue-zero proxy negatives"
    write_ev("independence", slim)
    log(f"INDEPENDENCE max|rho| {indep['max_abs_correlation']} over {indep['n_blocks']} blocks -> "
        f"allow_exchange={indep['allow_exchange']}")
    (WORK / "diag_done.json").write_text(json.dumps(
        dict(allow_exchange=bool(indep["allow_exchange"]), finished=now()), indent=1))
    return indep


# =================================================================================================
# E2a — exactly one whole-segment pseudo-label exchange, then refit
# =================================================================================================
def stage_exchange(reg):
    th = reg["thresholds"]
    h61_reg, store, cat, eligible, folds, va, vb, ring_px = setup()
    flat, inv = store.flat_idx, store.inverse
    indep = json.loads((EVID / "h74_independence.json").read_text())
    allowed_exchange = bool(indep["allow_exchange"])
    ex = dict(stage="exchange", started_utc=now(), allowed_exchange=allowed_exchange,
              independence_max_abs_rho=indep["max_abs_correlation"],
              donor_rank_min=th["donor_rank_min"], receiver_rank_interval=th["receiver_rank_interval"],
              cap_per_fold=th["pseudo_cap_per_fold"], min_pixels=th["min_pseudo_pixels"], folds=[])
    for fold in folds:
        f = fold["fold"]
        preds = {v: np.load(WORK / f"pred_pre_{v}_f{f}.npy") for v in ("A", "B")}
        train_rows = inv[np.flatnonzero((fold["train"] & eligible).ravel())]
        train_rows = train_rows[train_rows >= 0]
        rank_grid = {}
        for v in ("A", "B"):
            r = np.full(preds[v].shape, np.nan, np.float32)
            r[train_rows] = base.pct_rank(preds[v][train_rows])
            rank_grid[v] = base.to_grid(flat, np.nan_to_num(r, nan=-1.0), eligible.shape)
        visd = ndi.distance_transform_edt(~fold["visible"])
        forbidden = fold["region"] | fold["held_all"] | (visd <= 4)
        del visd
        rec = dict(fold=f, train_rows=int(len(train_rows)), forbidden_px=int(forbidden.sum()),
                   directions={})
        pseudo_pos = {}
        for donor, receiver in (("A", "B"), ("B", "A")):
            if not allowed_exchange:
                rec["directions"][f"{donor}->{receiver}"] = dict(
                    skipped=True, reason="independence screen fired: abandon co-training")
                continue
            idx, receipts = spatial.whole_pseudo_segments(
                rank_grid[donor], rank_grid[receiver], fold["train"], forbidden,
                th["donor_rank_min"], th["receiver_rank_interval"][0], th["receiver_rank_interval"][1],
                side=th["block_side_px"], min_pixels=th["min_pseudo_pixels"],
                cap=th["pseudo_cap_per_fold"])
            if len(idx):
                yy, xx = np.unravel_index(idx, eligible.shape)
                assert not fold["region"][yy, xx].any(), "pseudo-label reached the evaluation region"
                assert not fold["held_all"][yy, xx].any(), "pseudo-label reached a hidden component"
                assert not cat[yy, xx].any(), "pseudo-label reached a catalogue pixel"
            pseudo_pos[receiver] = idx
            rec["directions"][f"{donor}->{receiver}"] = dict(
                n_pixels=int(len(idx)), n_segments=len(receipts), segments=receipts[:25])
            log(f"fold {f} {donor}->{receiver}: {len(idx)} pseudo px in {len(receipts)} segments")
        rng = np.random.default_rng(SEED + 100 + f)
        rows, y = base.sample_train(fold, cat, rng)
        catd = ndi.distance_transform_edt(~cat)
        for view, cols in (("A", va), ("B", vb)):
            extra = pseudo_pos.get(view, np.empty(0, np.int64))
            extra_rows = extra[inv[extra] >= 0] if len(extra) else np.empty(0, np.int64)
            r2 = np.concatenate([rows, extra_rows]) if len(extra_rows) else rows
            y2 = np.concatenate([y, np.ones(len(extra_rows), np.int8)]) if len(extra_rows) else y
            m = base.learner_for(view, SEED + 7)
            m.fit(store.gather(r2, cols), y2)
            p = base.predict_flat(store, m, cols, flat)
            np.save(WORK / f"pred_post_{view}_f{f}.npy", p)
            pos_idx = inv[np.flatnonzero((fold["truth"] & fold["region"]).ravel())]
            neg_idx = inv[np.flatnonzero((fold["region"] & ~cat & (catd > 5)).ravel())]
            pos_idx, neg_idx = pos_idx[pos_idx >= 0], neg_idx[neg_idx >= 0]
            auc = float(roc_auc_score(np.r_[np.ones(len(pos_idx)), np.zeros(len(neg_idx))],
                                      np.r_[p[pos_idx], p[neg_idx]]))
            rec["directions"][f"refit_{view}"] = dict(n_pseudo_added=int(len(extra_rows)),
                                                      n_train_total=int(len(r2)),
                                                      heldout_region_auc=round(auc, 6))
            log(f"fold {f} refit {view}: +{len(extra_rows)} pseudo, OOF-region AUC {auc:.4f}")
        del catd
        ex["folds"].append(rec)
    ex.update(finished_utc=now(),
              total_pseudo_pixels=int(sum(d.get("n_pixels", 0) for r in ex["folds"]
                                          for d in r["directions"].values())),
              rule="exactly one exchange per direction per fold; no second round; no post-hoc search")
    write_ev("pseudo_exchange", ex)
    log(f"EXCHANGE total pseudo pixels {ex['total_pseudo_pixels']}")
    return ex


# =================================================================================================
# E2b — matched-budget hide-and-recover holdout
# =================================================================================================
def _shift0(a: np.ndarray, oy: int, ox: int) -> np.ndarray:
    """Shift by (oy, ox) with ZERO fill -- never np.roll, which would wrap the grid edge."""
    out = np.zeros_like(a)
    h, w = a.shape
    ys_dst = slice(max(oy, 0), h + min(oy, 0))
    ys_src = slice(max(-oy, 0), h + min(-oy, 0))
    xs_dst = slice(max(ox, 0), w + min(ox, 0))
    xs_src = slice(max(-ox, 0), w + min(-ox, 0))
    out[ys_dst, xs_dst] = a[ys_src, xs_src]
    return out


def line_support(field: np.ndarray, allowed: np.ndarray, n_orient: int = 12,
                 chord_px: int = 7) -> np.ndarray:
    """H74-B: max over orientations of the mean field value along a chord through the pixel.

    The metric credits a truth TRACE, so a dot's expected credit scales with the expected trace
    length inside its 300 m disc, not with the point probability.  Exact integer-offset sampling
    along each orientation; zero-filled shifts (never wrapped) so a grid edge cannot invent support.
    """
    f = np.where(allowed, np.nan_to_num(field, nan=0.0), 0.0).astype(np.float32)
    half = int(chord_px) // 2
    best = np.zeros_like(f)
    for k in range(int(n_orient)):
        theta = np.pi * k / float(n_orient)
        dy, dx = np.sin(theta), np.cos(theta)
        acc = np.zeros_like(f)
        seen = set()
        for t in range(-half, half + 1):
            oy, ox = int(round(dy * t)), int(round(dx * t))
            if (oy, ox) in seen:               # two t values can land on the same lattice cell
                continue
            seen.add((oy, ox))
            acc += f if (oy == 0 and ox == 0) else _shift0(f, oy, ox)
        np.maximum(best, acc / float(len(seen)), out=best)
    best[~allowed] = 0.0
    return best


def _swap_field(rank_b, rank_a, allowed, k, phi, donor_min, blind_lo, blind_hi, min_px=3.0):
    """Nested 'B-core + A-rescue swap' field.

    phi = 0 reproduces single_B exactly.  Otherwise: keep the strongest (1-phi)*k dots of the
    single_B placement as a protected core, then let the placer fill the remaining budget first
    from the A-rescue set (View A confident AND View B inside its blind band), and only then from
    the remaining View B order.  Priority is encoded as an additive offset so the SHARED placer
    (gems52.nodes.spacing_select) is used unchanged and 3 px separation is enforced globally.
    """
    em_b = nodes.spacing_select(np.nan_to_num(rank_b, nan=-1.0), allowed, k, min_px=min_px)
    n_core = int(round((1.0 - phi) * k))
    core = np.zeros_like(em_b)
    idx = np.flatnonzero(em_b.ravel())
    if n_core > 0 and idx.size:
        # keep the strongest n_core of the single_B dots; ties broken deterministically by index
        vals = np.nan_to_num(rank_b.ravel()[idx], nan=-1.0)
        order = idx[np.lexsort((idx, -vals))][:n_core]
        flatcore = np.zeros(em_b.size, bool)
        flatcore[order] = True
        core = flatcore.reshape(em_b.shape)
    rescue = allowed & (rank_a >= donor_min) & (rank_b >= blind_lo) & (rank_b <= blind_hi) & ~core
    field = np.where(allowed, np.nan_to_num(rank_b, nan=0.0), -1.0).astype(np.float32)
    field[rescue] = 1.0 + np.nan_to_num(rank_a[rescue], nan=0.0)        # second priority
    field[core] = 10.0 + np.nan_to_num(rank_b[core], nan=0.0)           # first priority
    return field, core, rescue


def stage_holdout(reg):
    th = reg["thresholds"]
    h61_reg, store, cat, eligible, folds, va, vb, ring_px = setup()
    flat, inv = store.flat_idx, store.inverse
    K = int(th["budget_dots_per_fold_per_arm"])
    min_px = float(th["min_dot_separation_px"])
    lo, hi = th["receiver_rank_interval"]
    donor_min = float(th["donor_rank_min"])
    arms = list(CONTROL_ARMS) + [f"swap_{int(p*100):03d}" for p in SWAP_FRACTIONS] + ["line_support_B"]
    out = dict(stage="holdout", started_utc=now(), budget_per_arm_per_fold=K,
               min_separation_px=min_px, arms=arms, folds=[],
               evidence_class="HOLDOUT-DTI (gems52-pooled-hide-v1); not a leaderboard score")
    terms = {a: None for a in arms}
    swap_audit = []
    for fold in folds:
        f = fold["fold"]
        allowed = allowed_domain(fold, ring_px)
        aidx = np.flatnonzero(allowed.ravel())
        g = {}
        for v in ("A", "B"):
            for tag in ("pre", "post"):
                g[f"{tag}_{v}"] = base.to_grid(flat, np.load(WORK / f"pred_{tag}_{v}_f{f}.npy"),
                                               eligible.shape)
        r = {}
        for key, arr in g.items():
            rr = np.full(arr.shape, np.nan, np.float32)
            rr.ravel()[aidx] = base.pct_rank(arr.ravel()[aidx])
            r[key] = rr
        del g
        rng = np.random.default_rng(SEED + 500 + f)
        rnd = np.zeros(eligible.shape, np.float32)
        rnd.ravel()[aidx] = rng.random(len(aidx), dtype=np.float32)
        fields = {
            "single_A": np.nan_to_num(r["pre_A"], nan=-1.0),
            "single_B": np.nan_to_num(r["pre_B"], nan=-1.0),
            "union_max": np.nan_to_num(np.maximum(r["pre_A"], r["pre_B"]), nan=-1.0),
            "disagreement_pre": np.nan_to_num(r["pre_A"] - r["pre_B"], nan=-1.0),
            "disagreement_post": np.nan_to_num(r["post_A"] - r["post_B"], nan=-1.0),
            "random": rnd,
        }
        for phi in SWAP_FRACTIONS:
            fld, core, rescue = _swap_field(r["post_B"], r["post_A"], allowed, K, phi,
                                            donor_min, lo, hi, min_px)
            fields[f"swap_{int(phi*100):03d}"] = fld
            swap_audit.append(dict(fold=f, phi=phi, core_px=int(core.sum()),
                                   rescue_pool_px=int(rescue.sum())))
        fields["line_support_B"] = line_support(np.nan_to_num(r["post_B"], nan=0.0), allowed,
                                                n_orient=int(th["line_support_orientations"]),
                                                chord_px=int(round(th["line_support_chord_m"] / 100.0)) + 1)
        rec = dict(fold=f, allowed_px=int(allowed.sum()), truth_px=int(fold["truth"].sum()),
                   region_px=int(fold["region"].sum()), arms={})
        em_by_arm = {}
        for arm in arms:
            t = time.time()
            em = nodes.spacing_select(fields[arm], allowed, K, min_px=min_px)
            em_by_arm[arm] = em
            n = int(em.sum())
            result, term = evaluator.evaluate(em.astype(np.float32), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            row = dict(result)
            row.update(placed=n, requested=K, filled=bool(n == K), seconds=round(time.time() - t, 1))
            rec["arms"][arm] = row
            log(f"fold {f} {arm}: {n}/{K} dots  HOLDOUT-DTI {result['dti']:.6f}")
        # how much of each swap arm actually differs from single_B (the nesting audit)
        b_em = em_by_arm["single_B"]
        for phi in SWAP_FRACTIONS:
            a = f"swap_{int(phi*100):03d}"
            e = em_by_arm[a]
            rec["arms"][a].update(dots_shared_with_single_B=int((e & b_em).sum()),
                                  dots_not_in_single_B=int((e & ~b_em).sum()))
        u_em = em_by_arm["union_max"]
        d_em = em_by_arm["disagreement_post"]
        rec["not_the_union"] = dict(
            disagreement_dots_also_in_union=int((d_em & u_em).sum()),
            swap050_dots_also_in_union=int((em_by_arm["swap_050"] & u_em).sum()),
            swap050_vs_single_B_jaccard=float((em_by_arm["swap_050"] & b_em).sum() /
                                              max(int((em_by_arm["swap_050"] | b_em).sum()), 1)))
        out["folds"].append(rec)
        del fields, r, em_by_arm
    pooled_all = {}
    for cand in [f"swap_{int(p*100):03d}" for p in SWAP_FRACTIONS] + ["line_support_B",
                                                                     "disagreement_post"]:
        pooled_all[cand] = evaluator.pooled_summary(terms, draws=int(th["bootstrap_draws"]),
                                                    seed=SEED, candidate=cand)
    scores = pooled_all[list(pooled_all)[0]]["scores"]
    control = scores["single_B"]["dti"]
    ok_control = abs(control - th["single_B_control"]) <= th["control_tolerance_abs"]
    best_cand, best_delta = None, None
    for cand, summ in pooled_all.items():
        d = summ["paired_differences"]["single_B"]
        if best_delta is None or d["delta"] > best_delta["delta"]:
            best_cand, best_delta = cand, d
    out.update(finished_utc=now(), swap_audit=swap_audit,
               pooled=dict(scores=scores,
                           paired_vs_single_B={c: s["paired_differences"]["single_B"]
                                               for c, s in pooled_all.items()},
                           bootstrap=pooled_all[list(pooled_all)[0]]["bootstrap"],
                           implementation_sha256=pooled_all[list(pooled_all)[0]]["implementation_sha256"]),
               withheld_positive_pixels=scores["single_B"]["withheld_positive_pixels"],
               all_arms_filled=bool(all(a["arms"][arm]["filled"] for a in out["folds"] for arm in arms)),
               control_reproduction=dict(measured=control, committed=th["single_B_control"],
                                         abs_delta=abs(control - th["single_B_control"]),
                                         tolerance=th["control_tolerance_abs"], pass_=bool(ok_control)),
               best_candidate=best_cand, best_candidate_vs_single_B=best_delta,
               beats_single_B=bool(best_delta is not None and best_delta["ci95"][0] > 0),
               caveat=("HOLDOUT-DTI on the label-blind-quadrants-v2 splitter. This simulator measured "
                       "Spearman -0.10 against the owner-reported board in round R4, so it screens "
                       "procedures; it does not by itself promote anything. Holdout prevalence is "
                       "~1% of the footprint against a competition truth near 0.12-0.25%."))
    write_ev("holdout", out)
    log(f"HOLDOUT control single_B {control:.6f} (pass={ok_control}); best candidate {best_cand} "
        f"delta {best_delta['delta']:.6f} CI {best_delta['ci95']} -> beats_single_B={out['beats_single_B']}")
    if not ok_control:
        raise SystemExit("control reproduction failed: the round is void (knowledge/63 section 2)")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", nargs="?", default="all",
                    choices=["diag", "exchange", "holdout", "registry", "build", "card", "all"])
    ap.add_argument("--stamp", default="")
    args = ap.parse_args()
    reg = check_prereg()
    WORK.mkdir(parents=True, exist_ok=True)
    order = (["diag", "exchange", "holdout", "registry", "build", "card"]
             if args.stage == "all" else [args.stage])
    for s in order:
        log(f"=== stage {s} ===")
        if s == "diag":
            if (EVID / "h74_independence.json").exists():
                log("diag already complete; skipping")
                continue
            stage_diag(reg)
        elif s == "exchange":
            if (EVID / "h74_pseudo_exchange.json").exists():
                log("exchange already complete; skipping")
                continue
            stage_exchange(reg)
        elif s == "holdout":
            if (EVID / "h74_holdout.json").exists():
                log("holdout already complete; skipping")
                continue
            stage_holdout(reg)
        elif s in ("registry", "build", "card"):
            import h74_build
            getattr(h74_build, f"stage_{s}")(reg, args)
    log("ALL STAGES DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
