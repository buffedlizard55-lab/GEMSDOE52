#!/usr/bin/env python3
"""H62 — buried structural corridors (co-training lane): E1 baselines + E2 validation.

Preregistration: ``knowledge/32_hypotheses_H62_preregistered.md`` +
``registry/h62_buriedcorr_preregistration.json`` (SHA-256 ``e3a8cfd25a1dec233f3a5738a17055390dfc0003f87515d8d50f431d97976552``,
frozen before any H62 fit ran).

REUSE POLICY (parallel-run protocol, rule 2).  The scientific primitives are shared code and
are imported, never forked:

* ``scripts/run_h60d_cotrain.py`` — ``fit_and_predict``, ``_gather``, ``block_error_rows``,
  ``pixel_corr``, ``score_cell`` (imported as ``R`` via importlib).
* ``gems52.h57.build_layers`` — the cached 75-layer feature stack (shared spec).
* ``gems52.holdout.make_folds`` / ``mask_visible`` — hide-and-recover instrument.
* ``gems52.metric.dti`` — pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel).
* ``gems52.h60d`` — disagreement fields, pooled_dti, bootstrap_ci, canary_report, run_card.

This script only orchestrates and adds the H62-1 gate chain (cover -> edge -> persistence).
Receipts: ``evidence/h62_buriedcorr_preflight.json``, ``evidence/h62_buriedcorr_cotrain.json``,
``evidence/h62_buriedcorr_validation.json``.  Work cache: ``work/h62``.  Never uploads anything.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import grid as G                       # noqa: E402
from gems52 import h57                              # noqa: E402
from gems52 import h58                              # noqa: E402
from gems52 import h60d                              # noqa: E402
from gems52 import holdout as HO                    # noqa: E402
from gems52 import metric as M                      # noqa: E402
from gems52 import spatial                          # noqa: E402

DATA = ROOT / "work/pinned"
WORK = ROOT / "work/h62_buriedcorr"
EV = ROOT / "evidence"
PREREG_PATH = ROOT / "registry/h62_buriedcorr_preregistration.json"
PREREG = json.loads(PREREG_PATH.read_text())
PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
SEED = int(PREREG["protocol"]["seed"])
Q_CONF = float(PREREG["protocol"]["thresholds"]["q_conf"])
Q_ABSTAIN = float(PREREG["protocol"]["thresholds"]["q_abstain"])
BLOCK = int(PREREG["protocol"]["thresholds"]["block_px"])
MIN_NEG = int(PREREG["protocol"]["thresholds"]["min_negatives_per_block"])
N_NEG_TRAIN = int(PREREG["protocol"]["thresholds"]["neg_train"])
BUDGETS = tuple(PREREG["protocol"]["budgets_px"])
LEAK_AUC_MAX = float(PREREG["protocol"]["thresholds"]["leakage_canary_auc_max"])

# H62-1 gate chain constants (preregistered in the knowledge doc)
COVER_MIN_M = 200.0
EDGE_PCTL = 75.0
LINE_HALF_WIDTHS = (2, 3, 4)
MIN_SKELETON_PX = 15
MIN_ELONGATION = 3.0


def log(m: str) -> None:
    print(f"[h62 {time.strftime('%H:%M:%S')}] {m}", flush=True)


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=1, sort_keys=False, default=float) + "\n")


def _load_R():
    """Import the H60D runner as a module so fit primitives are shared code."""
    spec = importlib.util.spec_from_file_location("h60d_runner", ROOT / "scripts/run_h60d_cotrain.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ----------------------------------------------------------------------------------------------- preflight
def stage_preflight() -> None:
    out = EV / "h62_buriedcorr_preflight.json"
    if out.exists():
        log("preflight cached")
        return
    log("verifying pinned inputs against the manifest (fail closed)")
    receipts = h58.verify_manifest(ROOT / "registry/data_manifest.json", DATA)
    all_ok = len(receipts) == 23 and all(r["matches_pin"] for r in receipts)
    rec = dict(round="H62-preflight",
               observed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               preregistration_sha256=PREREG_SHA,
               manifest="registry/data_manifest.json", data_root=str(DATA.relative_to(ROOT)),
               pinned_files_verified=len(receipts), pinned_all_ok=bool(all_ok),
               qualification=("SHA/byte verification of owner-mirror pins proves mirror integrity, "
                              "NOT organizer authentication; the DrivenData data tab is login-walled"),
               files=receipts)
    if not all_ok:
        write_json(out, rec)
        raise SystemExit("preflight FAILED: a pinned input does not match its manifest entry")
    write_json(out, rec)
    log(f"preflight OK: {len(receipts)}/23 pins match")


# ----------------------------------------------------------------------------------------------- layers + OOF
def stage_oof(R) -> None:
    out = EV / "h62_buriedcorr_cotrain.json"
    if out.exists() and (WORK / "pa_oof.npy").exists() and (WORK / "pb_oof.npy").exists():
        log("cotrain cached")
        return
    t0 = time.time()
    WORK.mkdir(parents=True, exist_ok=True)
    valid = G.footprint_from(DATA / "training_features.tif", bands="all")
    with rasterio.open(DATA / "labels.tif") as src:
        cat = src.read(1) == 1
    log(f"footprint {int(valid.sum())} px, catalogue {int(cat.sum())} px (pinned bytes)")
    h57.build_layers(work=str(WORK), chunk=600, data_dir=str(DATA))
    layers = h57.Layers(str(WORK))
    idx_a = layers.index([f"{n}_{s}" for n in h57.VIEW_A_LAYERS for s in ("val", "grad", "range")])
    idx_b = layers.index([f"{n}_{s}" for n in h57.VIEW_B_LAYERS for s in ("val", "grad", "range")])
    folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002, seed=SEED,
                          mode="hide")
    cat_dil = ndimage.binary_dilation(cat, iterations=h57.NEG_CLEAR_PX)
    corridor = ndimage.binary_dilation(cat, iterations=h57.CORRIDOR_PX)
    permitted = valid & ~corridor
    pa_oof = np.full(G.SHAPE, np.nan, np.float32)
    pb_oof = np.full(G.SHAPE, np.nan, np.float32)
    neg_rows, fold_receipts = [], []
    for f in folds:
        fit, reg = f["fit"], f["region"]
        _, pa = R.fit_and_predict(layers, idx_a, cat, valid, fit, SEED + f["fold"], f"A/f{f['fold']}")
        _, pb = R.fit_and_predict(layers, idx_b, cat, valid, fit, SEED + f["fold"], f"B/f{f['fold']}")
        pa_oof[reg] = pa[reg]
        pb_oof[reg] = pb[reg]
        neg_mask = reg & ~cat_dil
        rows = R.block_error_rows(pa, pb, neg_mask, f["fold"])
        neg_rows.extend(rows)
        fold_receipts.append(dict(fold=f["fold"], n_fit=int(fit.sum()), n_region=int(reg.sum()),
                                  n_truth=int(f["n_truth"]), n_held_components_px=int(f["n_held"]),
                                  cat_in_fit=int((cat & fit).sum()),
                                  n_negatives=int(neg_mask.sum()), n_blocks=len(rows)))
        log(f"fold {f['fold']}: truth {f['n_truth']} px, fit {int(fit.sum())} px, {len(rows)} blocks")
    np.save(WORK / "pa_oof.npy", pa_oof)
    np.save(WORK / "pb_oof.npy", pb_oof)

    ind = spatial.independence(neg_rows, threshold=0.60, min_blocks=20)
    ind["pixel_level"] = R.pixel_corr(pa_oof, pb_oof, valid & ~cat_dil)
    ind.update(q_conf=Q_CONF, block_px=BLOCK, min_negatives_per_block=MIN_NEG)
    log(f"independence: max|r|={ind['max_abs_correlation']} allow_exchange={ind['allow_exchange']}")

    t1 = time.time()
    mm = layers.mm

    def layer_iter():
        for i, nm in enumerate(layers.names):
            yield nm, np.asarray(mm[i], dtype=np.float32) / 255.0

    canary = h60d.canary_report(layer_iter(), folds)
    log(f"canary: worst {canary['worst_layer']} AUC {canary['worst_auc']} ({time.time() - t1:.0f}s)")

    pa0 = np.nan_to_num(pa_oof, nan=0.0)
    pb0 = np.nan_to_num(pb_oof, nan=0.0)
    strata = h57.disagreement(pa0, pb0, permitted, q_conf=Q_CONF, q_abstain=Q_ABSTAIN)
    depth = G.read_band(DATA / "training_features.tif", 15)
    strata["median_depth_to_basement_m"] = {
        k: float(np.median(depth[strata["masks"][k]]))
        for k in ("a_only", "b_only", "concordant") if strata["masks"][k].any()}
    strata["median_depth_to_basement_m"]["permitted"] = float(np.median(depth[permitted]))
    for k in ("a_only", "b_only", "concordant", "neither"):
        np.save(WORK / f"stratum_{k}.npy", strata["masks"][k])

    abandon = bool(ind["measured"] and ind["max_abs_correlation"] is not None
                   and ind["max_abs_correlation"] >= 0.60)
    rep = dict(round="H62-cotrain-v1", seed=SEED, preregistration_sha256=PREREG_SHA,
               runtime_s=round(time.time() - t0, 1),
               lane="co-training, disagreement as the discovery signal (buried corridors gates)",
               data_root=str(DATA.relative_to(ROOT)),
               qualification="pinned owner-mirror bytes, SHA-verified; not organizer-authenticated",
               footprint_px=int(valid.sum()), catalogue_px=int(cat.sum()),
               folds=fold_receipts,
               withheld_positives_total=int(sum(f["n_truth"] for f in fold_receipts)),
               independence=ind,
               leakage_canary={k: v for k, v in canary.items()},
               strata={k: v for k, v in strata.items() if k != "masks"},
               abandonment=("co-training abandoned by the registered independence rule"
                            if abandon else None),
               evaluator=h60d.evaluator_version())
    write_json(out, rep)
    log(f"wrote {out.name} in {time.time() - t0:.0f}s")


# ----------------------------------------------------------------------------------------------- H62-1 field
def _line_elements() -> list[np.ndarray]:
    """Line structuring elements at 0/45/90/135 degrees, half-widths 2,3,4 px."""
    ses = []
    for half in LINE_HALF_WIDTHS:
        n = 2 * half + 1
        for ang in (0, 45, 90, 135):
            se = np.zeros((n, n), bool)
            if ang == 0:            # horizontal
                se[half, :] = True
            elif ang == 90:         # vertical
                se[:, half] = True
            elif ang == 135:        # main diagonal
                np.fill_diagonal(se, True)
            else:                   # 45: anti-diagonal
                for i in range(n):
                    se[i, n - 1 - i] = True
            ses.append(se)
    return ses


def h62_corridor_mask(d: np.ndarray, permitted: np.ndarray, depth: np.ndarray,
                      edge: np.ndarray, log=log) -> tuple[np.ndarray, dict]:
    """The H62-1 gate chain: disagreement -> cover >= 200 m -> edge >= P75 -> line persistence."""
    cover = np.isfinite(depth) & (depth >= COVER_MIN_M)
    e_ok = np.isfinite(edge)
    thr = float(np.percentile(edge[permitted & e_ok], EDGE_PCTL))
    edge_gate = edge >= thr
    mask0 = (d > 0.0) & cover & edge_gate & permitted
    opened = np.zeros_like(mask0)
    for se in _line_elements():
        opened |= ndimage.binary_opening(mask0, structure=se, border_value=0)
    lab, n = ndimage.label(opened, structure=np.ones((3, 3), bool))
    keep = np.zeros(n + 1, bool)
    stats = []
    if n:
        from skimage.morphology import thin as _thin
        sizes = np.bincount(lab.ravel())
        skel = _thin(opened)
        skel_count = np.bincount(lab[skel], minlength=n + 1)
        objs = ndimage.find_objects(lab)
        for i, sl in enumerate(objs, start=1):
            if sl is None:
                continue
            comp = lab[sl] == i
            area = int(sizes[i])
            ys, xs = np.nonzero(comp)
            ys = ys.astype(float)
            xs = xs.astype(float)
            if area < 5:
                continue
            cy, cx = ys.mean(), xs.mean()
            yy, xx = ys - cy, xs - cx
            cov = np.array([[yy @ yy, yy @ xx], [yy @ xx, xx @ xx]]) / max(area, 1)
            eig = np.linalg.eigvalsh(cov)
            elong = float(np.sqrt(max(eig[-1], 1e-9) / max(eig[0], 1e-9)))
            length_est = int(skel_count[i])
            if length_est >= MIN_SKELETON_PX and elong >= MIN_ELONGATION:
                keep[i] = True
                stats.append(dict(area=area, elongation=round(elong, 2),
                                  length_est_px=int(length_est)))
    out = (lab > 0) & keep[lab]
    info = dict(cover_min_m=COVER_MIN_M, edge_threshold=thr,
                edge_pctl=EDGE_PCTL, line_half_widths=list(LINE_HALF_WIDTHS),
                n_components_kept=int(keep.sum()), n_components_total=int(n),
                mask0_px=int(mask0.sum()), opened_px=int(opened.sum()), final_px=int(out.sum()),
                components=stats[:200])
    log(f"H62-1 gates: mask0 {info['mask0_px']} -> opened {info['opened_px']} -> "
        f"kept {info['n_components_kept']}/{n} comps, {info['final_px']} px")
    return out, info




def _compute_validation_rows(R, log):
    """Compute the main cell grid + weak-surface subgroup rows (IR-H62-008 memory-safe)."""
    valid = G.footprint_from(DATA / "training_features.tif", bands="all")
    with rasterio.open(DATA / "labels.tif") as src:
        cat = src.read(1) == 1
    pa = np.nan_to_num(np.load(WORK / "pa_oof.npy"), nan=0.0).astype(np.float32)
    pb = np.nan_to_num(np.load(WORK / "pb_oof.npy"), nan=0.0).astype(np.float32)
    corridor = ndimage.binary_dilation(cat, iterations=h57.CORRIDOR_PX)
    permitted = valid & ~corridor

    depth = G.read_band(DATA / "training_features.tif", 15)
    layers = h57.Layers(str(WORK))
    mm = layers.mm
    names = list(layers.names)

    def lay(nm):
        return np.asarray(mm[names.index(nm)], dtype=np.float32) / 255.0

    edge = np.maximum(np.maximum(lay("A_grav_anom_grad"), lay("A_rtp_grad")),
                      lay("A_tmi_hg_grad"))
    d_contrast = h60d.dis_contrast(pa, pb)
    corridor_mask, gate_info = h62_corridor_mask(d_contrast, permitted, depth, edge)
    np.save(WORK / "h62_buriedcorr_corridor_mask.npy", corridor_mask)
    field_h62 = np.where(corridor_mask, d_contrast, 0.0).astype(np.float32)
    np.save(WORK / "field_h62_1.npy", field_h62)

    fields = {
        "view_A": pa, "view_B": pb,
        "clf_union": np.maximum(pa, pb),
        "dis_contrast": d_contrast,
        "H62_1_corridors": field_h62,
    }

    results = []
    rng = np.random.default_rng(SEED)
    folds_by_mode = {}
    for mode in ("hide", "tip"):
        folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002,
                              seed=SEED, mode=mode)
        folds_by_mode[mode] = folds
        for f in folds:
            blocked = ndimage.binary_dilation(f["visible"] & valid, iterations=h57.CORRIDOR_PX)
            legal = f["region"] & permitted & ~blocked
            truth = f["truth"] & f["region"] & valid
            flat_pool = np.flatnonzero(legal.ravel())
            for k in BUDGETS:
                take = rng.choice(flat_pool, min(k, flat_pool.size), replace=False)
                rnd = np.zeros(G.SHAPE, bool)
                rnd.ravel()[take] = True
                p = np.where(f["region"], rnd.astype(np.float32), 0.0)
                p = HO.mask_visible(p, f["visible"] & valid)
                r = M.dti(p, truth)
                results.append(dict(mode=mode, fold=f["fold"], budget=int(k), arm="random",
                                    dti=round(float(r["dti"]), 6), tpw=float(r["tpw"]),
                                    fpw=float(r["fpw"]), fnw=float(r["fnw"]),
                                    n_truth=int(r["n_truth"]), emitted=int((p > 0).sum())))
                for name, fld in fields.items():
                    r = R.score_cell(fld, legal, truth, f["region"], valid, f["visible"], k)
                    results.append(dict(mode=mode, fold=f["fold"], budget=int(k),
                                        arm=f"RANK_{name}", dti=round(float(r["dti"]), 6),
                                        tpw=float(r["tpw"]), fpw=float(r["fpw"]),
                                        fnw=float(r["fnw"]), n_truth=int(r["n_truth"]),
                                        emitted=int(r["emitted"])))
            line = ", ".join(f"{r['arm'].replace('RANK_', '')}={r['dti']:.4f}"
                             for r in results if r["mode"] == mode and r["fold"] == f["fold"]
                             and r["budget"] == BUDGETS[-1])
            log(f"{mode} f{f['fold']} k={BUDGETS[-1]}: {line}")

    # ---- weak-surface subgroup (the lane claim, preregistered clause 3) -----------------------
    # Memory fix (IR-H62-008): segment means via bincount over labels; subgroup truth masks
    # built by label lookup -- never one full-grid array per segment (that OOMed the first run).
    subgroup_rows = []
    subgroup = {"definition": ("withheld whole segments, mean view-B OOF probability along "
                               "segment pixels; below-median = weak surface expression; "
                               "emissions unchanged, truth restricted to the subgroup")}
    for mode in ("hide", "tip"):
        folds = folds_by_mode[mode]
        lab_of_fold = []
        seg_means = []
        base = 0
        for f in folds:
            t = f["truth"] & f["region"] & valid
            lab, n = ndimage.label(t, structure=np.ones((3, 3), bool))
            if n == 0:
                lab_of_fold.append(None)
                continue
            lab_of_fold.append((lab, n, base))
            sums = np.bincount(lab.ravel(), weights=pb.ravel(), minlength=n + 1)
            sizes = np.bincount(lab.ravel(), minlength=n + 1)
            means = sums[1:] / np.maximum(sizes[1:], 1)
            seg_means.extend(float(m) for m in means)
            base += n
        if len(seg_means) >= 2:
            med = float(np.median(seg_means))
            idx = 0
            weak_keep, strong_keep = [], []
            for entry in lab_of_fold:
                if entry is None:
                    continue
                lab, n, base = entry
                for i in range(1, n + 1):
                    (weak_keep if seg_means[idx] < med else strong_keep).append(base + i)
                    idx += 1
            weak_ids = set(weak_keep)
            strong_ids = set(strong_keep)
            weak_truth = np.zeros(G.SHAPE, bool)
            strong_truth = np.zeros(G.SHAPE, bool)
            for entry in lab_of_fold:
                if entry is None:
                    continue
                lab, n, base = entry
                lut = np.zeros(n + 1, np.uint8)
                for i in range(1, n + 1):
                    gid = base + i
                    if gid in weak_ids:
                        lut[i] = 1
                    elif gid in strong_ids:
                        lut[i] = 2
                sel = lut[lab]
                weak_truth |= sel == 1
                strong_truth |= sel == 2
                del sel, lut
            subgroup[f"{mode}_segments"] = dict(
                n_segments=len(seg_means), median_pb=round(med, 6),
                n_weak=len(weak_keep), n_strong=len(strong_keep),
                weak_truth_px=int(weak_truth.sum()), strong_truth_px=int(strong_truth.sum()))
            for label, tmask in (("weak", weak_truth), ("strong", strong_truth)):
                for f in folds:
                    blocked = ndimage.binary_dilation(f["visible"] & valid,
                                                      iterations=h57.CORRIDOR_PX)
                    legal = f["region"] & permitted & ~blocked
                    truth = tmask & f["region"] & valid
                    if not truth.any():
                        continue
                    for k in BUDGETS:
                        for name, fld in fields.items():
                            r = R.score_cell(fld, legal, truth, f["region"], valid,
                                             f["visible"], k)
                            subgroup_rows.append(dict(
                                mode=mode, subgroup=label, fold=f["fold"], budget=int(k),
                                arm=f"RANK_{name}", dti=round(float(r["dti"]), 6),
                                tpw=float(r["tpw"]), fpw=float(r["fpw"]),
                                fnw=float(r["fnw"]), n_truth=int(r["n_truth"])))
            del weak_truth, strong_truth
        else:
            subgroup[f"{mode}_segments"] = dict(n_segments=len(seg_means),
                                                reason="too few segments for a split")
    subgroup["rows"] = subgroup_rows
    return results, gate_info, subgroup


def stage_validate(R) -> None:
    out = EV / "h62_buriedcorr_validation.json"
    if out.exists():
        log("validation cached")
        return
    t0 = time.time()
    rows_ckpt = WORK / "validation_rows.json"
    if rows_ckpt.exists():
        ck = json.loads(rows_ckpt.read_text())
        results = ck["results"]
        gate_info = ck["gate_info"]
        subgroup = ck["subgroup"]
        log(f"validation rows cached ({len(results)} main + {len(subgroup['rows'])} subgroup)")
    else:
        results, gate_info, subgroup = _compute_validation_rows(R, log)
        rows_ckpt.write_text(json.dumps(
            dict(results=results, gate_info=gate_info, subgroup=subgroup), default=float))
        log(f"validation rows checkpointed ({len(results)} main + "
            f"{len(subgroup['rows'])} subgroup rows)")

    field_names = ["view_A", "view_B", "clf_union", "dis_contrast", "H62_1_corridors"]

    # ---- pooled DTI + fold-bootstrap CI per arm/cell ------------------------------------------
    table, pooled = {}, {}
    for mode in ("hide", "tip"):
        for k in BUDGETS:
            cell = {}
            for n in field_names + ["random"]:
                arm = f"RANK_{n}" if n != "random" else "random"
                rs = [r for r in results if r["mode"] == mode and r["budget"] == k and r["arm"] == arm]
                if not rs:
                    continue
                cell[n] = round(float(np.mean([r["dti"] for r in rs])), 6)
                pooled[f"{mode}@{k}/{n}"] = {
                    **h60d.pooled_dti(rs),
                    "ci95": h60d.bootstrap_ci([r["dti"] for r in rs], n_boot=10000, seed=SEED),
                    "fold_dtis": [r["dti"] for r in rs],
                    "label": "HOLDOUT-DTI", "evaluator": h60d.evaluator_version(),
                    "withheld_positives": int(sum(r["n_truth"] for r in rs))}
            table[f"{mode}@{k}"] = dict(sorted(cell.items(), key=lambda kv: -kv[1]))

    sub_pooled = {}
    rows = subgroup["rows"]
    for mode in ("hide", "tip"):
        for label in ("weak", "strong"):
            for k in BUDGETS:
                for n in field_names:
                    arm = f"RANK_{n}"
                    rs = [r for r in rows if r["mode"] == mode and r["subgroup"] == label
                          and r["budget"] == k and r["arm"] == arm]
                    if not rs:
                        continue
                    sub_pooled[f"{mode}@{k}/{label}/{n}"] = {
                        **h60d.pooled_dti(rs),
                        "ci95": h60d.bootstrap_ci([r["dti"] for r in rs], n_boot=10000, seed=SEED),
                        "fold_dtis": [r["dti"] for r in rs],
                        "label": "HOLDOUT-DTI", "evaluator": h60d.evaluator_version(),
                        "withheld_positives": int(sum(r["n_truth"] for r in rs))}
    subgroup["pooled"] = sub_pooled

    # ---- registered promotion bar -------------------------------------------------------------
    cot = json.loads((EV / "h62_buriedcorr_cotrain.json").read_text())

    def pv(key):
        return pooled[key]["dti"]

    k = BUDGETS[-1]
    h62v = pv(f"hide@{k}/H62_1_corridors")
    disc = pv(f"hide@{k}/dis_contrast")
    rnd = pv(f"hide@{k}/random")
    clause_a = bool(h62v > disc and h62v > rnd)
    wk = sub_pooled.get(f"hide@{k}/weak/H62_1_corridors")
    wv = sub_pooled.get(f"hide@{k}/weak/view_B")
    fold_wins = 0
    if wk and wv:
        fold_wins = sum(1 for x, y in zip(wk["fold_dtis"], wv["fold_dtis"]) if x > y)
    clause_b = bool(wk and wv and wk["dti"] > wv["dti"] and fold_wins >= 3)
    clause_c = bool(h62v >= rnd)
    canary_ok = bool(not cot["leakage_canary"]["leakage_detected"])
    ind_ok = bool(cot["independence"]["max_abs_correlation"] is not None
                  and cot["independence"]["max_abs_correlation"] < 0.60)
    gates = dict(clause_a_gates_add_value=clause_a, clause_b_weak_surface_win=clause_b,
                 clause_c_sanity=clause_c, leakage_canary_clean=canary_ok,
                 independence_ok=ind_ok, weak_subgroup_fold_wins=fold_wins,
                 bars=dict(h62=h62v, dis_contrast=disc, random=rnd,
                           weak_h62=(wk or {}).get("dti"), weak_view_B=(wv or {}).get("dti")),
                 verdict_so_far=("pass" if (clause_a and clause_b and clause_c
                                            and canary_ok and ind_ok) else "fail"))
    log(f"promotion bar: {gates}")

    rep = dict(round="H62-validation-v1", seed=SEED, preregistration_sha256=PREREG_SHA,
               runtime_s=round(time.time() - t0, 1),
               gate_chain=gate_info,
               field_table=table, pooled_dti=pooled, subgroup=subgroup, gates=gates,
               evaluator=h60d.evaluator_version(),
               caveats=["catalogue-truth hide/tip instruments; the private board truth is "
                        "off-catalogue expert-drawn faults (IR-H60-003 of the H60 register: "
                        "the instrument is a defective board predictor)",
                        "pinned owner-mirror bytes, not organizer-authenticated"])
    write_json(out, rep)
    log(f"wrote {out.name} in {time.time() - t0:.0f}s")


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    EV.mkdir(exist_ok=True)
    stage_preflight()
    R = _load_R()
    stage_oof(R)
    stage_validate(R)
    log("H62 E1+E2 complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
