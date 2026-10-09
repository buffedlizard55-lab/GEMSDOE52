#!/usr/bin/env python3
"""H61 -- two-view co-training with corroboration (not disagreement) as the discovery operator.

Runs strictly under ``registry/h61_preregistration.json``, frozen before this file executed; the
hypothesis text is ``knowledge/32_hypotheses_H61_preregistered.md`` whose SHA-256 is checked against
the registry at start-up.

Stages (each checkpointed, so an interrupted run resumes):

  preflight   verify all 23 manifest entries by SHA-256 and byte count against the pinned
              registry; fail closed on any mismatch.
  cotrain     E1: hide-and-recover whole-segment folds; per-fold OOF fits of View A and View B;
              the Blum-Mitchell independence test on 50 px block OOF negative errors; the
              per-layer leakage canary; the 2x2 confidence strata with cover-thickness depth
              statistics.  The pseudo-label exchange is NOT re-run (five prior independent
              nulls, H61-E).
  validate    E2: matched-budget arms scored on Instrument 1 (pooled HOLDOUT-DTI, fold-bootstrap
              95 % CI) and Instrument 2 (revealed-preference co-location with the atom of
              measured credit), plus the preregistered budget rule derived from the measured
              decay exponent gamma.

No leaderboard score enters any fit, field, fold or arm.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import grid as G                        # noqa: E402
from gems52 import h57                              # noqa: E402
from gems52 import h58                              # noqa: E402
from gems52 import h60d                             # noqa: E402
from gems52 import h61                              # noqa: E402
from gems52 import holdout as HO                    # noqa: E402
from gems52 import metric as M                      # noqa: E402
from gems52 import spatial                          # noqa: E402

DATA = ROOT / "data"
WORK = ROOT / "work/h61"
EV = ROOT / "evidence"
PREREG = json.loads((ROOT / "registry/h61_preregistration.json").read_text())
SEED = int(PREREG["protocol"]["seed"])
TH = PREREG["protocol"]["thresholds"]
Q_CONF = float(TH["q_conf"])
Q_ABSTAIN = float(TH["q_abstain"])
BLOCK = int(TH["block_px"])
MIN_NEG = int(TH["min_negatives_per_block"])
N_NEG_TRAIN = int(TH["neg_train"])
COVER_Q = float(TH["cover_depth_quantile"])
LIFT_BAR = float(TH["lift_bar_pooled"])
N_BOOT = 10000


def log(m: str) -> None:
    print(f"[h61 {time.strftime('%H:%M:%S')}] {m}", flush=True)


def done(path: Path) -> bool:
    return path.exists()


# --------------------------------------------------------------------------------- prereg check
def stage_registry_check() -> None:
    doc = ROOT / str(PREREG["hypothesis_document"])
    h = hashlib.sha256(doc.read_bytes()).hexdigest()
    if h != PREREG["hypothesis_document_sha256"]:
        raise SystemExit(f"hypothesis document changed after preregistration: {h}")
    for name, pinned in PREREG["evaluator_version"].items():
        if not name.endswith("_py_sha256") or name == "known_defect":
            continue
        mod = name[: -len("_py_sha256")] + ".py"
        p = ROOT / "src" / "gems52" / mod
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual != pinned:
            raise SystemExit(f"evaluator module {mod} changed: {actual} != pinned {pinned}")
    log(f"preregistration intact: {PREREG['round']} {PREREG['version']}")


# ----------------------------------------------------------------------------------- preflight
def stage_preflight() -> None:
    out = EV / "h61_preflight_integrity.json"
    if done(out):
        log("preflight cached")
        return
    log("verifying pinned inputs against the manifest (fail closed)")
    receipts = h58.verify_manifest(ROOT / "registry/data_manifest.json", DATA)
    all_ok = len(receipts) == 23 and all(r["matches_pin"] for r in receipts)
    tracked = {}
    for name in ("training_features.tif", "labels.tif", "sample_submission.tif"):
        p = DATA / name
        pin = next(r for r in receipts if r["dest"] == name)
        d = h58.sha256_file(p)
        tracked[name] = dict(local_bytes=p.stat().st_size, local_sha256=d,
                             local_matches_manifest=bool(d == pin["expected_sha256"]))
    rec = dict(round="H61-preflight",
               observed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               manifest="registry/data_manifest.json", data_root=str(DATA.relative_to(ROOT)),
               pinned_files_verified=len(receipts), pinned_all_ok=bool(all_ok),
               qualification=("SHA/byte verification of owner-mirror pins proves mirror integrity, "
                              "NOT organizer authentication; the DrivenData data tab is "
                              "login-walled"),
               tracked_data_comparison=tracked,
               files=[r for r in receipts])
    if not all_ok:
        raise SystemExit("preflight FAILED: a pinned input does not match its manifest entry")
    h61.write_json(out, rec)
    log(f"preflight OK: {len(receipts)}/23 pins match")


# ------------------------------------------------------------------------------------- cotrain
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


def fit_and_predict(layers, idx, cat, valid, fit, seed, tag):
    pos, neg = h57.labelled_pixels(cat, valid, fit, seed=seed, n_neg=N_NEG_TRAIN)
    if pos.size == 0 or neg.size == 0:
        raise RuntimeError(f"{tag}: empty training sample ({pos.size} pos, {neg.size} neg)")
    w = cat.shape[1]
    X = np.vstack([_gather(layers, idx, pos, w), _gather(layers, idx, neg, w)])
    y = np.concatenate([np.ones(pos.size, np.int8), np.zeros(neg.size, np.int8)])
    clf = h57.fit_view(X, y)
    grid = h57.predict_grid(clf, layers, idx)
    log(f"{tag}: {pos.size} pos / {neg.size} neg, {X.shape[1]} features, "
        f"|w|={np.linalg.norm(clf.coef_):.4f}")
    del X, y
    return clf, grid


def block_error_rows(pa, pb, neg_mask, fold):
    rows = []
    h, w = neg_mask.shape
    for y in range(0, h, BLOCK):
        for x in range(0, w, BLOCK):
            sl = np.s_[y:min(y + BLOCK, h), x:min(x + BLOCK, w)]
            good = neg_mask[sl]
            n = int(good.sum())
            if n < MIN_NEG:
                continue
            a = pa[sl][good].astype(float)
            b = pb[sl][good].astype(float)
            rows.append(dict(fold=int(fold), block_row=y // BLOCK, block_col=x // BLOCK,
                             n_negatives=n,
                             mse_A=float(np.mean(a * a)), mse_B=float(np.mean(b * b)),
                             fpr_A=float(np.mean(a >= Q_CONF)), fpr_B=float(np.mean(b >= Q_CONF))))
    return rows


def stage_cotrain() -> None:
    out = EV / "h61_cotrain.json"
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
                                  n_truth=int(f["n_truth"]),
                                  n_held_components_px=int(f["n_held"]),
                                  cat_in_fit=int((cat & fit).sum()),
                                  n_negatives=int(neg_mask.sum()), n_blocks=len(rows)))
        log(f"fold {f['fold']}: truth {f['n_truth']} px, fit {int(fit.sum())} px, "
            f"{len(rows)} blocks, {int((cat & fit).sum())} cat px in fit")
        del pa, pb
    np.save(WORK / "pa_oof.npy", pa_oof)
    np.save(WORK / "pb_oof.npy", pb_oof)
    log(f"OOF fields saved ({time.time() - t0:.0f}s)")

    # ---- the Blum-Mitchell premise, tested empirically -------------------------------------
    ind = spatial.independence(neg_rows, threshold=h61.ABANDON_R, min_blocks=20)
    pa_f = np.nan_to_num(pa_oof, nan=0.0)
    pb_f = np.nan_to_num(pb_oof, nan=0.0)
    m = valid & ~cat_dil & np.isfinite(pa_oof) & np.isfinite(pb_oof)
    a, b = pa_f[m].astype(float), pb_f[m].astype(float)
    ind["pixel_level"] = dict(n=int(m.sum()),
                              pearson=float(stats.pearsonr(a, b).statistic),
                              spearman=float(stats.spearmanr(a, b).statistic))
    ind.update(q_conf=Q_CONF, block_px=BLOCK, min_negatives_per_block=MIN_NEG)
    ind["blocks"] = None        # 8,000+ block rows are not published; the statistics are
    log(f"independence: measured={ind['measured']} allow={ind['allow_exchange']} "
        f"max|r|={ind['max_abs_correlation']}")

    # ---- leakage canary --------------------------------------------------------------------
    t1 = time.time()
    mm = layers.mm

    def layer_iter():
        for i, nm in enumerate(layers.names):
            yield nm, np.asarray(mm[i], dtype=np.float32) / 255.0

    canary = h60d.canary_report(layer_iter(), folds)
    log(f"leakage canary: {canary['n_layers']} layers, worst {canary['worst_layer']} "
        f"AUC {canary['worst_auc']} ({time.time() - t1:.0f}s)")

    # ---- the 2x2 confidence table, with cover thickness ------------------------------------
    strata = h57.disagreement(pa_f, pb_f, permitted, q_conf=Q_CONF, q_abstain=Q_ABSTAIN)
    depth = G.read_band(DATA / "training_features.tif", 15)
    med = {k: float(np.median(depth[strata["masks"][k]]))
           for k in ("a_only", "b_only", "concordant", "neither") if strata["masks"][k].any()}
    med["permitted"] = float(np.median(depth[permitted]))
    strata["median_depth_to_basement_m"] = med
    strata["evaluated_px"] = int(np.isfinite(pa_oof).sum())
    for k in ("a_only", "b_only", "concordant", "neither"):
        np.save(WORK / f"stratum_{k}.npy", strata["masks"][k])
    log(f"strata {strata['counts']}; depth medians {med}")

    # ---- the corroboration operator on the full grid ---------------------------------------
    k_probe = 60000
    th = h61.independent_thinning(pa_f, pb_f, permitted, Q_CONF, k_probe, h57.iso_select)
    log(f"independent thinning at k={k_probe}: A {th['n_thin_a']} dots, B {th['n_thin_b']} dots, "
        f"corroborated {th['n_corroborated']} (independence null "
        f"{th['expected_under_independence']:.1f}, lift "
        f"{th['corroboration_lift']:.3f})")
    np.save(WORK / "thin_a.npy", th["thin_a"])
    np.save(WORK / "thin_b.npy", th["thin_b"])
    np.save(WORK / "corroborated.npy", th["corroborated"])

    rep = dict(round="H61-cotrain-v1", seed=SEED, runtime_s=round(time.time() - t0, 1),
               lane=PREREG["lane"], data_root=str(DATA.relative_to(ROOT)),
               qualification=("pinned owner-mirror bytes, SHA-verified; not "
                              "organizer-authenticated"),
               footprint_px=int(valid.sum()), catalogue_px=int(cat.sum()),
               folds=fold_receipts,
               withheld_positives_total=int(sum(f["n_truth"] for f in fold_receipts)),
               independence=ind,
               leakage_canary={k: v for k, v in canary.items()},
               strata={k: v for k, v in strata.items() if k != "masks"},
               corroboration_probe={k: v for k, v in th.items()
                                    if not isinstance(v, np.ndarray)},
               cotraining_exchange=dict(
                   ran=False,
                   reason=("H61-E: not re-run. Five independent prior reproductions (H56, H57, "
                           "H59, H60D x2 directions) returned nulls; the premise test is still "
                           "run above because the concordance hypothesis rests on the same "
                           "conditional-independence premise.")),
               view_a_layers=h57.VIEW_A_LAYERS, view_b_layers=h57.VIEW_B_LAYERS)
    h61.write_json(out, rep)
    log(f"wrote {out.name} in {time.time() - t0:.0f}s")


# ------------------------------------------------------------------------------------ validate
def score_cell(field, legal, fold, valid, k):
    score = np.where(legal, field, 0.0).astype(np.float32)
    nodes = h57.iso_select(score, legal, k, min_px=3.0, nms_px=3)
    p = np.where(fold["region"], nodes.astype(np.float32), 0.0)
    p = HO.mask_visible(p, fold["visible"] & valid)
    r = M.dti(p, fold["truth"] & fold["region"] & valid)
    r["emitted"] = int((p > 0).sum())
    return r


def build_fields(pa, pb, depth, permitted) -> dict:
    corrob = np.load(WORK / "corroborated.npy")
    conc_cell = h61.concordant_cell(pa, pb, permitted, Q_CONF)
    fields = {
        "view_A": pa.astype(np.float32),
        "view_B": pb.astype(np.float32),
        "clf_union": np.maximum(pa, pb).astype(np.float32),
        "dis_contrast": h60d.dis_contrast(pa, pb),
        "dis_product": h60d.dis_product(pa, pb),
        "conc_min": np.where(conc_cell, h61.concordance_surface(pa, pb), 0.0).astype(np.float32),
        "conc_corrob": np.where(corrob, h61.concordance_surface(pa, pb), 0.0).astype(np.float32),
    }
    cc, thr = h61.cover_conditioned_disagreement(pa, pb, depth, permitted, Q_CONF, Q_ABSTAIN,
                                                 COVER_Q)
    fields["cover_A_only"] = cc
    return fields, thr


def stage_validate() -> None:
    out = EV / "h61_validation.json"
    if done(out):
        log("validation cached")
        return
    t0 = time.time()
    valid = G.footprint_from(DATA / "training_features.tif", bands="all")
    with rasterio.open(DATA / "labels.tif") as src:
        cat = src.read(1) == 1
    pa = np.nan_to_num(np.load(WORK / "pa_oof.npy"), nan=0.0).astype(np.float32)
    pb = np.nan_to_num(np.load(WORK / "pb_oof.npy"), nan=0.0).astype(np.float32)
    depth = G.read_band(DATA / "training_features.tif", 15)
    corridor = ndimage.binary_dilation(cat, iterations=h57.CORRIDOR_PX)
    permitted = valid & ~corridor
    fields, cover_thr = build_fields(pa, pb, depth, permitted)
    log("fields: " + ", ".join(fields) + f"; cover threshold {cover_thr:.1f} m")

    # ---------------- Instrument 2: revealed-preference co-location (whole grid) -------------
    with rasterio.open(DATA / "reference/h33-2-b2-zeros.tif") as src:
        ref = src.read(1) > 0
    with rasterio.open(DATA / "scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif"
                       ) as src:
        d15 = np.isfinite(src.read(1)) & (src.read(1) > 0)
    p1 = ref & d15
    log(f"measured-credit atom P1 = {int(p1.sum())} px (nested-pair algebra, "
        f"credit density [16.3%, 20.5%], owner-reported)")
    near_p1 = ndimage.binary_dilation(p1, iterations=3)

    rng = np.random.default_rng(SEED)
    flat_pool = np.flatnonzero(permitted.ravel())
    grid = list(h61.GAMMA_GRID)
    rev_rows = []
    for name, fld in fields.items():
        row = dict(field=name)
        for k in grid:
            nodes = h57.iso_select(np.where(permitted, fld, 0.0).astype(np.float32),
                                   permitted, k, min_px=3.0, nms_px=3)
            row[f"f_{k}"] = h61.revealed_colocation(nodes, p1, permitted)
        rev_rows.append(row)
    # matched random controls at the same budgets
    rev_rand = {}
    for k in grid:
        take = rng.choice(flat_pool, size=k, replace=False)
        rnd = np.zeros(G.SHAPE, bool)
        rnd.ravel()[take] = True
        rev_rand[f"f_{k}"] = h61.revealed_colocation(rnd, p1, permitted)
    log(f"instrument 2 done ({time.time() - t0:.0f}s)")

    # ---------------- Instrument 1: HOLDOUT-DTI, whole-segment hide folds --------------------
    folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002, seed=SEED,
                          mode="hide")
    budgets = [15000, 25000]
    cells = []
    rng2 = np.random.default_rng(SEED)
    for f in folds:
        blocked = ndimage.binary_dilation(f["visible"] & valid, iterations=h57.CORRIDOR_PX)
        legal = f["region"] & permitted & ~blocked
        for k in budgets:
            take = rng2.choice(np.flatnonzero(legal.ravel()), size=k, replace=False)
            rnd = np.zeros(G.SHAPE, bool)
            rnd.ravel()[take] = True
            p = np.where(f["region"], rnd.astype(np.float32), 0.0)
            p = HO.mask_visible(p, f["visible"] & valid)
            r = M.dti(p, f["truth"] & f["region"] & valid)
            cells.append(dict(fold=f["fold"], budget=k, arm="random", dti=float(r["dti"]),
                              tpw=float(r["tpw"]), fpw=float(r["fpw"]), fnw=float(r["fnw"]),
                              n_truth=int(r["n_truth"]), emitted=int((p > 0).sum())))
            for name, fld in fields.items():
                r = score_cell(fld, legal, f, valid, k)
                cells.append(dict(fold=f["fold"], budget=k, arm=name, dti=float(r["dti"]),
                                  tpw=float(r["tpw"]), fpw=float(r["fpw"]), fnw=float(r["fnw"]),
                                  n_truth=int(r["n_truth"]), emitted=int(r["emitted"])))
        log(f"instrument 1 fold {f['fold']} done ({time.time() - t0:.0f}s)")

    summary = {}
    for k in budgets:
        for arm in list(fields) + ["random"]:
            sub = [c for c in cells if c["arm"] == arm and c["budget"] == k]
            pooled = h60d.pooled_dti(sub)
            ci = h60d.bootstrap_ci([c["dti"] for c in sub], n_boot=N_BOOT, seed=SEED)
            summary[f"{arm}|{k}"] = dict(pooled_dti=round(pooled["dti"], 6),
                                         ci_lo=ci["ci_lo"], ci_hi=ci["ci_hi"],
                                         n_folds=len(sub),
                                         withheld_positives=int(pooled["n_truth"]),
                                         mean_emitted=round(float(np.mean(
                                             [c["emitted"] for c in sub])), 1))
    rand = {k: summary[f"random|{k}"]["pooled_dti"] for k in budgets}
    for k, v in summary.items():
        arm = k.split("|")[0]
        b = int(k.split("|")[1])
        v["lift_over_random"] = round(v["pooled_dti"] - rand[b], 6)

    # ---------------- the derived budget ----------------------------------------------------
    best = max(fields, key=lambda n: (summary[f"{n}|25000"]["pooled_dti"] if False else
                                      (rev_rows[[r["field"] for r in rev_rows].index(n)]
                                       ["f_25000"]["lift"] or 0.0)))
    pts = [(k, rev_rows[[r["field"] for r in rev_rows].index(best)][f"f_{k}"]["fraction"])
           for k in grid]
    budget = h61.budget_from_gamma(pts)
    log(f"instrument-2 leader: {best}; gamma fit -> budget {budget['budget_px']} px "
        f"({time.time() - t0:.0f}s)")

    rec = dict(round="H61-validate-v1", seed=SEED, runtime_s=round(time.time() - t0, 1),
               instrument1_holdout=dict(
                   label="HOLDOUT-DTI",
                   evaluator_version=PREREG["evaluator_version"],
                   mode="hide-and-recover, whole segments, 4 folds, buffer 4 px, prevalence 0.002",
                   withheld_positives=int(sum(c["n_truth"] for c in cells
                                              if c["arm"] == "random" and c["budget"] == 15000)),
                   ci="fold bootstrap, 10k resamples",
                   known_defect=PREREG["evaluator_version"]["known_defect"],
                   budgets_px=budgets, arms=summary),
               instrument2_revealed=dict(
                   label="revealed-preference co-location; NOT a holdout score",
                   core_atom="P1 = ref_h33_2_b2 & scored_d15_scored",
                   core_px=int(p1.sum()),
                   core_credit_density_bracket="[0.163, 0.205] (owner-reported, knowledge/10 s3)",
                   limits=("similarity statistic to one specific prior file; rho_P1 rests on "
                           "owner-reported scores; read only together with the uniqueness gate"),
                   budget_grid_px=grid, per_field=rev_rows, matched_random=rev_rand),
               cover_threshold_m=cover_thr,
               budget_rule=budget,
               instrument2_leader=best,
               promotion_lift_bar=LIFT_BAR)
    h61.write_json(out, rec)
    log(f"wrote {out.name} in {time.time() - t0:.0f}s")


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    EV.mkdir(parents=True, exist_ok=True)
    stage_registry_check()
    for stage in (stage_preflight, stage_cotrain, stage_validate):
        stage()
    log("ALL STAGES COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
