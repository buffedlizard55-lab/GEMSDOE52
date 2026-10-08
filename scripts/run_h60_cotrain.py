#!/usr/bin/env python3
"""H60 — co-training with disagreement as the discovery signal (this session's lane).

Runs strictly under ``registry/h60_preregistration.json`` (frozen before this file executed);
the hypothesis text is ``knowledge/25_hypotheses_H60_preregistered.md``.

Stages (each checkpointed under work/h60 / evidence so an interrupted run resumes):

  preflight   verify every input against the registry/data_manifest.json pins; measure the
              tracked data/*.tif stubs and record that they are NOT the pinned bytes (fail
              closed on any pinned mismatch; the tracked-stub inequality is recorded fact).
  layers      the template's cached feature stack (h57.build_layers, 75 uint8 rank layers);
              REUSED, not rebuilt — a cache hit is the expected path.
  cotrain     E1: hide-and-recover whole-segment folds; per-fold OOF fits of View A and
              View B; the brief's independence test on block OOF negative errors; the
              per-layer leakage canary; the disagreement strata; one co-training round in
              BOTH directions (A labels B, B labels A — the H59 exchange refit the donor view,
              which is self-training; H60-3 corrects the direction and registers it).
  validate    E2: matched-budget arms on the hide and tip instruments — the two single-view
              baselines, the union incumbent, the three disagreement fields, the matched
              random control — scored with the exact DTI (alpha 0.2, beta 0.8, 300 m
              triangular kernel), visible catalogue masked pixel-exactly, per-fold and pooled,
              with fold-bootstrap 95 % CIs; the registered promotion gate is decided here,
              mechanically.  The co-training treatment is read out on the treated fold as a
              paired comparison against its round-0 fields.

No leaderboard score enters any fit, field, fold, or arm here.
"""
from __future__ import annotations

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
from gems52 import h60                              # noqa: E402
from gems52 import holdout as HO                    # noqa: E402
from gems52 import metric as M                      # noqa: E402
from gems52 import spatial                          # noqa: E402

DATA = ROOT / "work/pinned"
WORK = ROOT / "work/h60"
EV = ROOT / "evidence"
PREREG = json.loads((ROOT / "registry/h60_preregistration.json").read_text())
SEED = int(PREREG["protocol"]["seed"])
Q_CONF = float(PREREG["protocol"]["thresholds"]["q_conf"])
Q_ABSTAIN = float(PREREG["protocol"]["thresholds"]["q_abstain"])
BLOCK = int(PREREG["protocol"]["thresholds"]["block_px"])
MIN_NEG = int(PREREG["protocol"]["thresholds"]["min_negatives_per_block"])
N_NEG_TRAIN = int(PREREG["protocol"]["thresholds"]["neg_train"])
BUDGETS = tuple(PREREG["protocol"]["budgets_px"])
LIFT_BAR = 0.005
FOLD_BAR = 3
N_BOOT = 10000


def log(m: str) -> None:
    print(f"[h60 {time.strftime('%H:%M:%S')}] {m}", flush=True)


def done(path: Path) -> bool:
    return path.exists()


# ----------------------------------------------------------------------------------------------- preflight
def stage_preflight() -> None:
    out = EV / "h60_preflight_integrity.json"
    if done(out):
        log("preflight cached")
        return
    log("verifying pinned inputs against the manifest (fail closed)")
    try:
        receipts = h58.verify_manifest(ROOT / "registry/data_manifest.json", DATA)
        all_ok = len(receipts) == 23 and all(r["matches_pin"] for r in receipts)
    except Exception as exc:
        h60.write_json(EV / "h60_preflight_integrity.json",
                       dict(round="H60-preflight", pinned_all_ok=False, error=str(exc)[:400]))
        raise
    tracked = {}
    for name in ("training_features.tif", "labels.tif", "sample_submission.tif"):
        p = ROOT / "data" / name
        pin = next(r for r in receipts if r["dest"] == name)
        d = h58.sha256_file(p)
        tracked[name] = dict(local_bytes=p.stat().st_size, local_sha256=d,
                             local_matches_manifest=bool(d == pin["expected_sha256"]))
    rec = dict(round="H60-preflight",
               observed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               manifest="registry/data_manifest.json", data_root=str(DATA.relative_to(ROOT)),
               pinned_files_verified=len(receipts), pinned_all_ok=bool(all_ok),
               qualification=("SHA/byte verification of owner-mirror pins proves mirror integrity, "
                              "NOT organizer authentication; the DrivenData data tab is "
                              "login-walled"),
               tracked_data_comparison=tracked,
               tracked_policy=("No H60 number is computed from tracked data/*.tif; the tracked "
                               "training_features.tif is a 19-band all-zero grid stub"),
               files=[r for r in receipts])
    if not all_ok:
        raise SystemExit("preflight FAILED: a pinned input does not match its manifest entry")
    h60.write_json(out, rec)
    log(f"preflight OK: {len(receipts)}/23 pins match; tracked stubs recorded as not pinned")


# ----------------------------------------------------------------------------------------------- layers
def stage_layers() -> None:
    t0 = time.time()
    meta = h57.build_layers(work=str(WORK), chunk=600, data_dir=DATA)
    log(f"layer stack ready: {len(meta['names'])} cached layers "
        f"(footprint {meta['footprint_px']} px) in {time.time() - t0:.0f}s")


# ----------------------------------------------------------------------------------------------- cotrain
def _gather(layers, idx, flat_idx, width):
    flat_idx = np.asarray(flat_idx, np.int64)
    rows = flat_idx // width
    order = np.argsort(rows, kind="stable")
    rows_sorted = rows[order]
    out = np.empty((flat_idx.size, len(idx)), np.float32)
    mm = layers.mm
    uniq = np.unique(rows_sorted)
    for r, s0, e0 in zip(uniq, np.searchsorted(rows_sorted, uniq, side="left"),
                         np.searchsorted(rows_sorted, uniq, side="right")):
        sel = order[s0:e0]
        cols = flat_idx[sel] - int(r) * width
        block = np.asarray(mm[idx, int(r), :], dtype=np.uint8)
        out[sel] = block[:, cols].T.astype(np.float32) / 255.0
    return out


def fit_and_predict(layers, idx, cat, valid, fit, seed, tag, extra_pos=()):
    pos, neg = h57.labelled_pixels(cat, valid, fit, seed=seed, n_neg=N_NEG_TRAIN)
    if pos.size == 0 or neg.size == 0:
        raise RuntimeError(f"{tag}: empty training sample ({pos.size} pos, {neg.size} neg)")
    w = cat.shape[1]
    X = np.vstack([_gather(layers, idx, pos, w), _gather(layers, idx, neg, w)]
                  + ([_gather(layers, idx, np.asarray(extra_pos, np.int64), w)]
                     if len(extra_pos) else []))
    y = np.concatenate([np.ones(pos.size, np.int8), np.zeros(neg.size, np.int8)]
                       + ([np.ones(len(extra_pos), np.int8)] if len(extra_pos) else []))
    clf = h57.fit_view(X, y)
    grid = h57.predict_grid(clf, layers, idx)
    log(f"{tag}: {pos.size} pos / {neg.size} neg"
        + (f" / {len(extra_pos)} pseudo" if len(extra_pos) else "")
        + f", {X.shape[1]} features, |w|={np.linalg.norm(clf.coef_):.4f}")
    del X, y
    return clf, grid


def block_error_rows(pa, pb, neg_mask, fold):
    rows = []
    h, w = neg_mask.shape
    for y in range(0, h, BLOCK):
        for x in range(0, w, BLOCK):
            sl = np.s_[y:min(y + BLOCK, h), x:min(x + BLOCK, w)]
            good = neg_mask[sl]
            if int(good.sum()) < MIN_NEG:
                continue
            a = pa[sl][good].astype(float)
            b = pb[sl][good].astype(float)
            rows.append(dict(fold=int(fold), block_row=y // BLOCK, block_col=x // BLOCK,
                             n_negatives=int(good.sum()),
                             mse_A=float(np.mean(a * a)), mse_B=float(np.mean(b * b)),
                             fpr_A=float(np.mean(a >= Q_CONF)), fpr_B=float(np.mean(b >= Q_CONF))))
    return rows


def pixel_corr(pa, pb, mask):
    from scipy import stats
    good = mask & np.isfinite(pa) & np.isfinite(pb)
    a, b = pa[good].astype(float), pb[good].astype(float)
    out = dict(n=int(good.sum()))
    if out["n"] >= 3 and np.ptp(a) > 1e-12 and np.ptp(b) > 1e-12:
        out["pearson"] = float(stats.pearsonr(a, b).statistic)
        out["spearman"] = float(stats.spearmanr(a, b).statistic)
    else:
        out.update(pearson=None, spearman=None, reason="too few observations or a constant column")
    return out


def stage_cotrain() -> None:
    out = EV / "h60_cotrain.json"
    if done(out):
        log("cotrain cached")
        return
    t0 = time.time()
    valid = G.footprint_from(DATA / "training_features.tif", bands="all")
    with rasterio.open(DATA / "labels.tif") as src:
        cat = src.read(1) == 1
    log(f"footprint {int(valid.sum())} px, catalogue {int(cat.sum())} px (pinned bytes)")
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
        _, pa = fit_and_predict(layers, idx_a, cat, valid, fit, SEED + f["fold"], f"A/f{f['fold']}")
        _, pb = fit_and_predict(layers, idx_b, cat, valid, fit, SEED + f["fold"], f"B/f{f['fold']}")
        pa_oof[reg] = pa[reg]
        pb_oof[reg] = pb[reg]
        neg_mask = reg & ~cat_dil
        rows = block_error_rows(pa, pb, neg_mask, f["fold"])
        neg_rows.extend(rows)
        fold_receipts.append(dict(fold=f["fold"], n_fit=int(fit.sum()), n_region=int(reg.sum()),
                                  n_boundary=int(f["boundary"].sum()), n_truth=int(f["n_truth"]),
                                  n_held_components_px=int(f["n_held"]),
                                  cat_in_fit=int((cat & fit).sum()),
                                  n_negatives=int(neg_mask.sum()), n_blocks=len(rows)))
        log(f"fold {f['fold']}: truth {f['n_truth']} px, fit {int(fit.sum())} px, "
            f"{len(rows)} blocks, {int((cat & fit).sum())} cat px in fit")
    np.save(WORK / "pa_oof.npy", pa_oof)
    np.save(WORK / "pb_oof.npy", pb_oof)
    log(f"OOF fields saved ({time.time() - t0:.0f}s)")

    # ---- the brief's independence test -------------------------------------------------------
    ind = spatial.independence(neg_rows, threshold=0.60, min_blocks=20)
    ind["pixel_level"] = pixel_corr(pa_oof, pb_oof, valid & ~cat_dil)
    ind.update(q_conf=Q_CONF, block_px=BLOCK, min_negatives_per_block=MIN_NEG)
    log(f"independence: measured={ind['measured']} allow_exchange={ind['allow_exchange']} "
        f"max|r|={ind['max_abs_correlation']}")

    # ---- the leakage canary: every cached layer alone vs the holdout truth --------------------
    # Streamed one layer at a time off the uint8 memmap: 75 full-grid float32 layers is
    # ~3.7 GB and the box has 3 GB, so nothing here may hold the stack.
    t1 = time.time()
    mm = layers.mm

    def layer_iter():
        for i, nm in enumerate(layers.names):
            yield nm, np.asarray(mm[i], dtype=np.float32) / 255.0

    canary = h60.canary_report(layer_iter(), folds)
    log(f"leakage canary: {canary['n_layers']} layers, worst {canary['worst_layer']} "
        f"AUC {canary['worst_auc']} -> {canary['verdict'][:60]} ({time.time() - t1:.0f}s)")

    # ---- disagreement strata (the discovery signal) -------------------------------------------
    pa0 = np.nan_to_num(pa_oof, nan=0.0)
    pb0 = np.nan_to_num(pb_oof, nan=0.0)
    strata = h57.disagreement(pa0, pb0, permitted, q_conf=Q_CONF, q_abstain=Q_ABSTAIN)
    depth = G.read_band(DATA / "training_features.tif", 15)
    strata["median_depth_to_basement_m"] = {
        k: float(np.median(depth[strata["masks"][k]]))
        for k in ("a_only", "b_only", "concordant") if strata["masks"][k].any()}
    strata["median_depth_to_basement_m"]["permitted"] = float(np.median(depth[permitted]))
    strata["evaluated_px"] = int(np.isfinite(pa_oof).sum())
    for k in ("a_only", "b_only", "concordant", "neither"):
        np.save(WORK / f"stratum_{k}.npy", strata["masks"][k])
    log(f"strata {strata['counts']}")

    # ---- H60-3: one co-training round, BOTH directions, on the fold-0 fit region --------------
    # Registered correction of the H59 exchange: the donor view's confident predictions label
    # the OTHER view (Blum-Mitchell), not the donor itself (self-training).  Whole segments,
    # one 50x50 block each, inside fit0 (which carries the >=400 m buffer around every held
    # segment), never on a catalogue/corridor/boundary pixel.
    pseudo = {"ran": False}
    if ind["allow_exchange"]:
        from sklearn.metrics import roc_auc_score
        f0 = folds[0]
        reg0, fit0 = f0["region"], f0["fit"]
        forbidden = cat | corridor | ~reg0 | f0["boundary"]
        m = reg0 & ~f0["boundary"]
        exchange = {}
        for side, donor, receiver, idx_fit, tag in (
                ("A_labels_B", pa0, pb0, idx_b, "B"), ("B_labels_A", pb0, pa0, idx_a, "A")):
            idx, receipt = spatial.whole_pseudo_segments(
                donor, receiver, fit0, forbidden, Q_CONF, Q_ABSTAIN, Q_CONF, side=BLOCK)
            if idx.size == 0:
                exchange[side] = dict(ran=False, reason="no whole segment satisfied "
                                      "donor-confident / receiver-abstains inside fit0")
                continue
            pos, neg = h57.labelled_pixels(cat, valid, fit0, seed=SEED + 99, n_neg=N_NEG_TRAIN)
            _, p_after = fit_and_predict(layers, idx_fit, cat, valid, fit0, SEED + 7,
                                         f"{tag}-refit/{side}", extra_pos=idx)
            before = float(roc_auc_score(cat[m], (pa0 if tag == "A" else pb0)[m]))
            after = float(roc_auc_score(cat[m], p_after[m]))
            np.save(WORK / f"p{tag.lower()}_cotrain.npy", p_after)
            exchange[side] = dict(ran=True, n_pseudo_px=int(idx.size), n_segments=len(receipt),
                                  donor_threshold=Q_CONF, receiver_band=[Q_ABSTAIN, Q_CONF],
                                  n_eval_px=int(m.sum()),
                                  auc_before=before, auc_after=after,
                                  delta_auc=after - before,
                                  rule="whole 8-connected segments inside one 50x50 block, "
                                       "entirely inside the fold-0 fit region (>=400 m buffer "
                                       "around every held segment), never on a catalogue or "
                                       "corridor pixel; donor confident, receiver in the "
                                       "abstention band; donor labels the OTHER view")
            log(f"{side}: {int(idx.size)} px / {len(receipt)} segments, "
                f"AUC {before:.4f} -> {after:.4f} (d={after - before:+.4f})")
        pseudo = dict(ran=any(e.get("ran") for e in exchange.values()), exchange=exchange)
    else:
        pseudo["reason"] = ("independence test did not license the exchange: "
                            + str(ind.get("reason")))
    if not pseudo.get("ran"):
        log("co-training exchange NOT run: " + str(pseudo.get("reason")))

    abandon = bool(ind["measured"] and ind["max_abs_correlation"] is not None
                  and ind["max_abs_correlation"] >= 0.60)
    rep = dict(round="H60-cotrain-v1", seed=SEED, runtime_s=round(time.time() - t0, 1),
               lane="co-training, disagreement as the discovery signal",
               data_root=str(DATA.relative_to(ROOT)),
               qualification=("pinned owner-mirror bytes, SHA-verified; not "
                              "organizer-authenticated"),
               footprint_px=int(valid.sum()), catalogue_px=int(cat.sum()),
               folds=fold_receipts,
               withheld_positives_total=int(sum(f["n_truth"] for f in fold_receipts)),
               independence=ind,
               leakage_canary={k: v for k, v in canary.items()},
               strata={k: v for k, v in strata.items() if k != "masks"},
               cotraining_round=pseudo,
               abandonment=("co-training abandoned by the registered independence rule"
                            if abandon else None),
               disagreement_fields={k: str(v.__doc__ or "").strip().splitlines()[0]
                                    for k, v in h60.DISAGREEMENT_FIELDS.items()})
    h60.write_json(out, rep)
    log(f"wrote {out.name} in {time.time() - t0:.0f}s")


# ----------------------------------------------------------------------------------------------- validate
def score_cell(field, legal, truth, region, valid, visible, k):
    """One matched-budget cell: isotropic 3 px emitter, exact DTI, visible masked exactly."""
    score = np.where(legal, field, 0.0).astype(np.float32)
    nodes = h57.iso_select(score, legal, k, min_px=3.0, nms_px=5)
    p = np.where(region, nodes.astype(np.float32), 0.0)
    p = HO.mask_visible(p, visible & valid)
    r = M.dti(p, truth & region & valid)
    r["emitted"] = int((p > 0).sum())
    return r


def stage_validate() -> None:
    out = EV / "h60_validation.json"
    if done(out):
        log("validation cached")
        return
    t0 = time.time()
    valid = G.footprint_from(DATA / "training_features.tif", bands="all")
    with rasterio.open(DATA / "labels.tif") as src:
        cat = src.read(1) == 1
    pa = np.nan_to_num(np.load(WORK / "pa_oof.npy"), nan=0.0).astype(np.float32)
    pb = np.nan_to_num(np.load(WORK / "pb_oof.npy"), nan=0.0).astype(np.float32)
    pa_ct_path = WORK / "pa_cotrain.npy"
    pb_ct_path = WORK / "pb_cotrain.npy"
    pa_ct = np.load(pa_ct_path).astype(np.float32) if pa_ct_path.exists() else None
    pb_ct = np.load(pb_ct_path).astype(np.float32) if pb_ct_path.exists() else None
    corridor = ndimage.binary_dilation(cat, iterations=h57.CORRIDOR_PX)
    permitted = valid & ~corridor

    fields = {
        "view_A": pa,
        "view_B": pb,
        "clf_union": np.maximum(pa, pb),
        "dis_product": h60.dis_product(pa, pb),
        "dis_contrast": h60.dis_contrast(pa, pb),
        "dis_B_product": h60.dis_b_product(pa, pb),
    }
    for nm, fv in fields.items():
        np.save(WORK / f"field_{nm}.npy", fv.astype(np.float32))
    log("fields built: " + ", ".join(fields))

    # One pass, storing the full metric components per cell (needed for the pooled read);
    # the summary view is derived from the same rows, so nothing is scored twice.
    results = []
    rng = np.random.default_rng(SEED)
    for mode in ("hide", "tip"):
        folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002,
                              seed=SEED, mode=mode)
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
                                    dti=round(float(r["dti"]), 6),
                                    tpw=float(r["tpw"]), fpw=float(r["fpw"]),
                                    fnw=float(r["fnw"]), n_truth=int(r["n_truth"]),
                                    emitted=int((p > 0).sum())))
                for name, fld in fields.items():
                    r = score_cell(fld, legal, truth, f["region"], valid, f["visible"], k)
                    results.append(dict(mode=mode, fold=f["fold"], budget=int(k),
                                        arm=f"RANK_{name}",
                                        dti=round(float(r["dti"]), 6),
                                        tpw=float(r["tpw"]), fpw=float(r["fpw"]),
                                        fnw=float(r["fnw"]), n_truth=int(r["n_truth"]),
                                        emitted=int(r["emitted"])))
            line = ", ".join(
                f"{r['arm'].replace('RANK_', '')}={r['dti']:.4f}"
                for r in results if r["mode"] == mode and r["fold"] == f["fold"]
                and r["budget"] == BUDGETS[-1])
            log(f"{mode} f{f['fold']} k={BUDGETS[-1]}: {line}")

    # ---- the co-training treatment: paired read on the treated fold (fold 0), both instruments
    cotrain = {"arms": [], "note": ("paired read on fold 0 only: the round-1 fields are the "
                                    "treated models; the round-0 fields on the same rows are "
                                    "the control; both are out-of-fold for fold 0's segments")}
    if pa_ct is not None and pb_ct is not None:
        ct_fields = {
            "view_A_round0": pa, "view_B_round0": pb,
            "clf_union_round0": np.maximum(pa, pb),
            "cotrain_A_round1": pa_ct, "cotrain_B_round1": pb_ct,
            "cotrain_union_round1": np.maximum(pa_ct, pb_ct),
        }
        for mode in ("hide", "tip"):
            folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002,
                                  seed=SEED, mode=mode)
            f = folds[0]
            blocked = ndimage.binary_dilation(f["visible"] & valid, iterations=h57.CORRIDOR_PX)
            legal = f["region"] & permitted & ~blocked
            truth = f["truth"] & f["region"] & valid
            flat_pool = np.flatnonzero(legal.ravel())
            k = BUDGETS[-1]
            take = rng.choice(flat_pool, min(k, flat_pool.size), replace=False)
            rnd = np.zeros(G.SHAPE, bool)
            rnd.ravel()[take] = True
            p = np.where(f["region"], rnd.astype(np.float32), 0.0)
            p = HO.mask_visible(p, f["visible"] & valid)
            r = M.dti(p, truth)
            cotrain["arms"].append(dict(mode=mode, fold=0, budget=int(k), arm="random",
                                        dti=round(float(r["dti"]), 6),
                                        n_truth=int(r["n_truth"])))
            for name, fld in ct_fields.items():
                r = score_cell(fld, legal, truth, f["region"], valid, f["visible"], k)
                cotrain["arms"].append(dict(mode=mode, fold=0, budget=int(k), arm=name,
                                            dti=round(float(r["dti"]), 6),
                                            emitted=int(r["emitted"]),
                                            n_truth=int(r["n_truth"])))
            log(f"cotreatment {mode} f0 k={k}: " + ", ".join(
                f"{a['arm']}={a['dti']:.4f}" for a in cotrain["arms"]
                if a["mode"] == mode))

    # ---- pooled DTI + fold-bootstrap CI per arm/cell ------------------------------------------
    def cells(mode, k, arm):
        return [r for r in results if r["mode"] == mode and r["budget"] == k and r["arm"] == arm]

    table, pooled = {}, {}
    names = list(fields)
    for mode in ("hide", "tip"):
        for k in BUDGETS:
            cell = {}
            for n in names + ["random"]:
                rs = cells(mode, k, f"RANK_{n}" if n != "random" else "random")
                if not rs:
                    continue
                cell[n] = round(float(np.mean([r["dti"] for r in rs])), 6)
            table[f"{mode}@{k}"] = dict(sorted(cell.items(), key=lambda kv: -kv[1]))
            for n in names + ["random"]:
                rs = cells(mode, k, f"RANK_{n}" if n != "random" else "random")
                if not rs:
                    continue
                pl = h60.pooled_dti(rs)
                ci = h60.bootstrap_ci([r["dti"] for r in rs], n_boot=N_BOOT, seed=SEED)
                pooled[f"{mode}@{k}|{n}"] = dict(
                    pooled_dti=round(pl["dti"], 6), tpw=round(pl["tpw"], 2),
                    fpw=round(pl["fpw"], 2), fnw=round(pl["fnw"], 2), n_truth=pl["n_truth"],
                    n_folds=pl["n_folds"], fold_mean_dti=round(ci["mean"], 6),
                    ci95_lo=round(ci["ci_lo"], 6), ci95_hi=round(ci["ci_hi"], 6),
                    withheld_positives=pl["n_truth"],
                    label="HOLDOUT-DTI (gems52.metric.dti alpha 0.2 beta 0.8 R 300 m "
                          "triangular, lattice-exact; holdout.make_folds whole-segment "
                          "hide-and-recover, 4 folds, buffer 4 px, prevalence 0.002, "
                          "seed 20261009; pooled = metric components pooled across folds; "
                          "CI = fold bootstrap, 10k resamples)")

    # ---- the registered promotion gate ----------------------------------------------------------
    def fold_mean(mode, k, arm):
        rs = cells(mode, k, arm)
        return float(np.mean([r["dti"] for r in rs])) if rs else float("nan")

    def folds_won(mode, k, arm, ref):
        w = 0
        for fo in range(4):
            a = [r["dti"] for r in cells(mode, k, arm) if r["fold"] == fo]
            b = [r["dti"] for r in cells(mode, k, ref) if r["fold"] == fo]
            w += bool(a and b and a[0] > b[0])
        return w

    gates = {}
    for n in names:
        arm = f"RANK_{n}"
        beats_union = fold_mean("hide", BUDGETS[-1], arm) > fold_mean("hide", BUDGETS[-1], "RANK_clf_union")
        beats_A = fold_mean("hide", BUDGETS[-1], arm) > fold_mean("hide", BUDGETS[-1], "RANK_view_A")
        beats_B = fold_mean("hide", BUDGETS[-1], arm) > fold_mean("hide", BUDGETS[-1], "RANK_view_B")
        wins_union = folds_won("hide", BUDGETS[-1], arm, "RANK_clf_union")
        wins_A = folds_won("hide", BUDGETS[-1], arm, "RANK_view_A")
        wins_B = folds_won("hide", BUDGETS[-1], arm, "RANK_view_B")
        lifts = {mo: round(fold_mean(mo, BUDGETS[-1], arm) - fold_mean(mo, BUDGETS[-1], "random"), 6)
                 for mo in ("hide", "tip")}
        wins_rand = {mo: folds_won(mo, BUDGETS[-1], arm, "random") for mo in ("hide", "tip")}
        # H60-4 is characterization only: the B-only product is the suspect-artifact
        # population, so the registered rule never lets it ship, whatever it scores.
        shippable = n != "dis_B_product"
        gates[n] = dict(
            hide37654_fold_mean=round(fold_mean("hide", BUDGETS[-1], arm), 6),
            beats_union_hide=bool(beats_union), beats_view_A_hide=bool(beats_A),
            beats_view_B_hide=bool(beats_B),
            folds_won_vs_union=int(wins_union), folds_won_vs_view_A=int(wins_A),
            folds_won_vs_view_B=int(wins_B),
            mean_lift_vs_random_at_37654=lifts,
            folds_won_vs_random_at_37654=wins_rand,
            slot_bar_met=bool(shippable and min(lifts.values()) >= LIFT_BAR
                             and min(wins_rand.values()) >= FOLD_BAR),
            characterization_only=not shippable,
            promotion_rule=("promotes iff hide@37654 fold-mean beats union AND view_A AND "
                            "view_B, wins >=3/4 folds against each, and mean lift vs random "
                            ">= +0.005 on BOTH instruments; H60-4 (B-only) is scored for the "
                            "record and never ships"),
            promotes=bool(shippable and beats_union and beats_A and beats_B
                          and min(wins_union, wins_A, wins_B) >= FOLD_BAR
                          and min(lifts.values()) >= LIFT_BAR
                          and min(wins_rand.values()) >= FOLD_BAR))
    # the lane's discovery signal is the A-side disagreement (buried beneath cover);
    # the B-only product is the suspect-artifact population and is never the artifact
    dis_names = [n for n in names if n.startswith("dis_") and n != "dis_B_product"]
    promoted = [n for n in dis_names if gates[n]["promotes"]]
    if promoted:
        best = max(promoted, key=lambda n: fold_mean("hide", BUDGETS[-1], f"RANK_{n}"))
    else:
        # negative result is a deliverable: ship the best measured A-side disagreement field
        best = max(dis_names, key=lambda n: fold_mean("hide", BUDGETS[-1], f"RANK_{n}"))
    (WORK / "promoted_field.txt").write_text(best)
    log(f"promotion: {promoted or 'none'}; shipped field: {best} "
        f"(verdict {'promote' if promoted else 'negative'})")

    rep = dict(round="H60-validation-v1", seed=SEED, runtime_s=round(time.time() - t0, 1),
               protocol="registry/h60_preregistration.json -> protocol",
               field_table=table, pooled_dti=pooled, gates=gates,
               promoted_field=best, promoted_any=bool(promoted),
               cotreatment=cotrain, results=results,
               evaluator_version=h60.evaluator_version(),
               caveats=[
                   "Simulator truth is the mapped catalogue minus visible; relative instrument "
                   "only (Spearman(reported, simulated DTI) = -0.1045, knowledge/10 s5).",
                   "The pinned inputs are owner-mirror SHA-verified, not organizer-authenticated.",
                   "The hide-mode OOF fields never saw the held whole segments; on the tip "
                   "instrument the same fields are conservative (fold components hidden at fit).",
                   "A required-novel arm cannot be scored by this simulator at all "
                   "(knowledge/18 s6); pooled DTI here measures the field's ranking on "
                   "catalogue truth, not the hidden competition truth."])
    h60.write_json(out, rep)
    log(f"wrote {out.name} in {time.time() - t0:.0f}s")


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    EV.mkdir(exist_ok=True)
    stage_preflight()
    stage_layers()
    stage_cotrain()
    stage_validate()
    log("H60 fit/validation complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
