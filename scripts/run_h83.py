#!/usr/bin/env python3
"""H83 -- co-training on two instruments: the mandated hide-and-recover, and a new
off-catalogue recovery instrument built from a fault compilation the competition catalogue
does not contain.

Lane: the brief's co-training paragraph.  View A is potential-field/subsurface, View B is
surface (DEM curvature and slope plus the radiometric channels), and disagreement is the
discovery signal (Blum & Mitchell, COLT '98, doi:10.1145/279943.279962).

Preregistered in ``knowledge/74_hypotheses_H83_preregistered.md`` and pinned by
``registry/h83_preregistration.json``; this runner refuses to start if either hash has moved.

Shared tools are reused, never forked:
    run_h61.setup / sample_train / learner_for / predict_flat / to_grid / pct_rank
    gems52.spatial.folds            (label-blind-quadrants-v2)
    gems52.spatial.independence     (the lane's mandated conditional-independence screen)
    gems52.spatial.whole_pseudo_segments (whole-segment, block-confined pseudo-labels)
    gems52.evaluate_holdout         (gems52-pooled-hide-v1 -- the mandated instrument)
    gems52.metric                   (alpha 0.2, beta 0.8, 300 m triangular kernel)
    gems52.nodes.spacing_select     (metric-aware placement)
    gems52.gates, gems52.submission_writer, gems52.grid

New shared tool added this round (in the template, not a private fork):
    gems52.offcatalogue -- instrument I2.  Truth = SGMC fault pixels at >= 300 m from
    labels.tif; training positives are catalogue pixels from the OTHER three quadrants only
    (which is already what gems52.spatial.folds' ``train`` domain is), so one fit serves both
    instruments.  1,000 paired 200 px physical-cluster bootstrap draws, same alpha/beta/kernel.

Stages:
    canary    single-channel leakage canary on every fold's held-out region sample
    fit       both views per fold, out-of-fold prediction over the whole eligible domain
    exchange  independence screen, then exactly one whole-segment pseudo-label round, then refit
    holdout   matched-budget comparison of seven arms on BOTH instruments, pooled DTI + 95% CI
    build     stitched out-of-fold mosaic, placement, authoritative gates, GeoTIFF
    lane      lane/uniqueness gate on the surface and on the final dots
    card      machine-readable run card

Usage: python scripts/run_h83.py [canary|fit|exchange|holdout|build|lane|card|all]
"""
from __future__ import annotations

import argparse
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

import numpy as np                                                   # noqa: E402
import rasterio                                                      # noqa: E402
from scipy import ndimage as ndi                                     # noqa: E402
from scipy.stats import rankdata                                     # noqa: E402
from sklearn.metrics import roc_auc_score                            # noqa: E402

import run_h61 as base                                               # noqa: E402
from build_h61_submission import prior_paths                         # noqa: E402
from gems52 import evaluate_holdout as evaluator                     # noqa: E402
from gems52 import gates, grid, nodes, spatial, structural           # noqa: E402
from gems52 import submission_writer                                 # noqa: E402

SEED = base.SEED
PREREG = ROOT / "registry/h83_preregistration.json"
WORK = ROOT / "work/h83"
EVID = ROOT / "evidence"
DOCS = ROOT / "docs/data"
DOWN = ROOT / "docs/downloads"
SUBM = ROOT / "submission"
SAMPLE = ROOT / "data/sample_submission.tif"
CENSUS = ROOT / "work/h61/prior_fetch_receipt.json"
PREFIX = "gems52-h83-"

ARMS = ("single_A", "single_B", "union_max", "A_only", "B_only", "disagreement_post", "random",
        "E3_single_B_quota")


def log(*a, **k):
    print(*a, flush=True, **k)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write(name: str, obj) -> Path:
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"h83_{name}.json"
    p.write_text(json.dumps(obj, indent=1, allow_nan=False, default=str) + "\n")
    (DOCS / f"h83_{name}.json").write_text(p.read_text())
    return p


def digest(path) -> str:
    return structural.digest(Path(path))


# --------------------------------------------------------------------------------------------
# setup: pins, preregistration, cached feature store, folds, off-catalogue truth
# --------------------------------------------------------------------------------------------
def setup():
    reg = json.loads(PREREG.read_text())
    doc = ROOT / reg["hypothesis_document"]
    if digest(doc) != reg["hypothesis_sha256"]:
        raise SystemExit("preregistered hypothesis document changed after registration")
    pins = {f["id"]: f for f in json.loads((ROOT / "registry/data_manifest.json").read_text())["files"]}
    for key in ("training_features", "labels", "sample_submission"):
        if digest(ROOT / "data" / pins[key]["dest"]) != pins[key]["sha256"]:
            raise SystemExit(f"input pin mismatch: {key}")
    reg61, store, cat, eligible, folds, va, vb, ring_px = base.setup()
    th = reg["thresholds"]
    # ---- instrument I2 truth: SGMC faults the competition catalogue does not have
    sgmc_path = ROOT / "data/external/derived_sgmc_faults_100m_u8.tif"
    pin = next((f for f in json.loads((ROOT / "registry/data_manifest.json").read_text())["files"]
                if f["dest"].endswith("derived_sgmc_faults_100m_u8.tif")), None)
    if pin is not None and digest(sgmc_path) != pin["sha256"]:
        raise SystemExit("sgmc pin mismatch")
    with rasterio.open(sgmc_path) as ds:
        sgmc = ds.read(1) > 0
        if (ds.height, ds.width) != grid.SHAPE:
            raise SystemExit(f"sgmc shape {(ds.height, ds.width)} != pinned {grid.SHAPE}")
        if str(ds.crs) != grid.CRS_EPSG:
            raise SystemExit(f"sgmc crs {ds.crs} != {grid.CRS_EPSG}")
        if tuple(float(v) for v in ds.transform)[:6] != tuple(float(v) for v in grid.TRANSFORM):
            raise SystemExit("sgmc transform != pinned competition transform")
    catd = ndi.distance_transform_edt(~cat)
    offcat = sgmc & eligible & (catd > float(th["offcatalogue_min_distance_to_catalogue_px"]))
    del catd
    offcat_b = sgmc & eligible & ~cat          # amendment 74a: extensions included, cut 0 px
    for fold in folds:
        fold["offcat_truth"] = offcat & fold["region"]
    log(f"off-catalogue truth (cut 0 px): {int(offcat_b.sum())} px; "
        f"(cut >= {th['offcatalogue_min_distance_to_catalogue_px']:g} px): {int(offcat.sum())} px "
        f"(>= {th['offcatalogue_min_distance_to_catalogue_px']:g} px from labels.tif); "
        f"per fold {[int(f['offcat_truth'].sum()) for f in folds]}")
    return reg, store, cat, eligible, folds, va, vb, ring_px, offcat, offcat_b


# --------------------------------------------------------------------------------------------
# stage: canary
# --------------------------------------------------------------------------------------------
def stage_canary():
    reg, store, cat, eligible, folds, va, vb, ring_px, offcat, offcat_b = setup()
    th = reg["thresholds"]
    rng = np.random.default_rng(SEED)
    out = dict(stage="canary", round="H83", started_utc=now(),
               alarm_auc=th["canary_auc_alarm"],
               evidence_class="LEAKAGE-CANARY AUC (diagnostic, not a DTI score)", folds=[])
    worst = []
    for fold in folds:
        region = fold["region"]
        pos = np.flatnonzero((fold["truth"] & region).ravel())
        catd = ndi.distance_transform_edt(~cat)
        neg_pool = region & ~cat & (catd > 5)
        # an off-catalogue truth pixel must never be used as a proxy negative
        neg_pool &= ~offcat
        neg = np.flatnonzero(neg_pool.ravel())
        del catd, neg_pool
        pos = rng.choice(pos, min(20000, len(pos)), replace=False)
        neg = rng.choice(neg, min(40000, len(neg)), replace=False)
        rows = np.concatenate([pos, neg])
        y = np.concatenate([np.ones(len(pos), np.int8), np.zeros(len(neg), np.int8)])
        per = {}
        for name in va + vb:
            x = store.gather(rows, [name])[:, 0]
            auc = float(roc_auc_score(y, x))
            per[name] = dict(auc=auc, direction_insensitive=max(auc, 1 - auc),
                             view="A" if name in va else "B")
        ranked = sorted(per.items(), key=lambda kv: -kv[1]["direction_insensitive"])
        alarms = [n for n, r in per.items() if r["direction_insensitive"] > th["canary_auc_alarm"]]
        out["folds"].append(dict(fold=fold["fold"], n_pos=int(len(pos)), n_neg=int(len(neg)),
                                 max_direction_insensitive_auc=ranked[0][1]["direction_insensitive"],
                                 top5=[(n, r["direction_insensitive"]) for n, r in ranked[:5]],
                                 alarms=alarms, per_feature=per))
        worst += [(fold["fold"], n, r["direction_insensitive"]) for n, r in ranked[:3]]
        log(f"fold {fold['fold']} canary max AUC {ranked[0][1]['direction_insensitive']:.6f} "
            f"({ranked[0][0]}) alarms={alarms}")
    out.update(finished_utc=now(), max_alarm_across_folds=max(w[2] for w in worst),
               any_alarm=bool(any(r["alarms"] for r in out["folds"])),
               dropped_features=sorted({n for r in out["folds"] for n in r["alarms"]}),
               interpretation="AUC above the alarm means leakage until proven otherwise; "
                              "catalogue-zero negatives are proxies, not verified fault absence.")
    write("canary", out)
    return out


# --------------------------------------------------------------------------------------------
# stage: fit
# --------------------------------------------------------------------------------------------
def stage_fit():
    reg, store, cat, eligible, folds, va, vb, ring_px, offcat, offcat_b = setup()
    flat = store.flat_idx
    WORK.mkdir(parents=True, exist_ok=True)
    out = dict(stage="fit", round="H83", started_utc=now(), view_A_features=va, view_B_features=vb,
               n_A=len(va), n_B=len(vb), seed=SEED, folds=[])
    for fold in folds:
        rng = np.random.default_rng(SEED + fold["fold"])
        rows, y, w = base.sample_for_fit(fold, cat, rng)
        rec = dict(fold=fold["fold"], n_train=int(len(rows)), n_pos=int(y.sum()),
                   train_domain_px=int(fold["train"].sum()), region_px=int(fold["region"].sum()),
                   truth_px=int(fold["truth"].sum()), offcat_truth_px=int(fold["offcat_truth"].sum()))
        for view, names in (("A", va), ("B", vb)):
            t0 = time.time()
            X = store.gather(rows, names)
            m = base.learner_for(view, SEED)
            if w is None:
                m.fit(X, y)
            else:
                m.fit(X, y, sample_weight=w)
            in_auc = float(roc_auc_score(y, m.predict_proba(X)[:, 1]))
            del X
            t1 = time.time()
            p = base.predict_flat(store, m, names, flat)
            np.save(WORK / f"pred_pre_{view}_f{fold['fold']}.npy", p)
            inv = store.inverse
            pos_idx = inv[np.flatnonzero((fold["truth"] & fold["region"]).ravel())]
            catd = ndi.distance_transform_edt(~cat)
            neg_idx = inv[np.flatnonzero((fold["region"] & ~cat & ~offcat & (catd > 5)).ravel())]
            # instrument I2 read: same model, off-catalogue truth
            op_idx = inv[np.flatnonzero(fold["offcat_truth"].ravel())]
            del catd
            oof_auc = float(roc_auc_score(
                np.r_[np.ones(len(pos_idx)), np.zeros(len(neg_idx))],
                np.r_[p[pos_idx], p[neg_idx]]))
            off_auc = float(roc_auc_score(
                np.r_[np.ones(len(op_idx)), np.zeros(len(neg_idx))],
                np.r_[p[op_idx], p[neg_idx]])) if len(op_idx) > 50 else None
            rec[f"view_{view}"] = dict(fit_seconds=round(t1 - t0, 1),
                                       predict_seconds=round(time.time() - t1, 1),
                                       in_sample_auc=in_auc,
                                       heldout_region_auc=oof_auc,
                                       offcatalogue_auc=off_auc,
                                       n_region_pos=int(len(pos_idx)), n_region_neg=int(len(neg_idx)),
                                       n_offcat_pos=int(len(op_idx)))
            log(f"fold {fold['fold']} view {view}: in-AUC {in_auc:.4f} "
                f"I1-AUC {oof_auc:.4f} I2-AUC {off_auc}")
        out["folds"].append(rec)
    out.update(finished_utc=now(), evaluator_hashes=evaluator.implementation_hashes())
    write("fit_checkpoint", out)
    return out


# --------------------------------------------------------------------------------------------
# stage: exchange
# --------------------------------------------------------------------------------------------
def stage_exchange():
    reg, store, cat, eligible, folds, va, vb, ring_px, offcat, offcat_b = setup()
    th = reg["thresholds"]
    flat, inv = store.flat_idx, store.inverse
    block_rows = []
    indep = dict(stage="independence", round="H83", folds=[])
    for fold in folds:
        pa = base.to_grid(flat, np.load(WORK / f"pred_pre_A_f{fold['fold']}.npy"), eligible.shape)
        pb = base.to_grid(flat, np.load(WORK / f"pred_pre_B_f{fold['fold']}.npy"), eligible.shape)
        catd = ndi.distance_transform_edt(~cat)
        neg = fold["region"] & ~cat & ~offcat & (catd > 4) & np.isfinite(pa) & np.isfinite(pb)
        del catd
        qa, qb = pa[neg], pb[neg]
        thresholds = (float(np.quantile(qa, th["donor_rank_min"])),
                      float(np.quantile(qb, th["donor_rank_min"])))
        blocks = spatial.negative_block_errors(np.nan_to_num(pa, nan=0.0), np.nan_to_num(pb, nan=0.0),
                                               neg, fold["fold"], thresholds,
                                               side=th["block_side_px"], minimum=32)
        block_rows += blocks
        indep["folds"].append(dict(fold=fold["fold"], n_negatives=int(neg.sum()),
                                   thresholds=list(thresholds), n_blocks=len(blocks)))
        del pa, pb
    pre = spatial.independence(block_rows, threshold=th["independence_abandon_max_abs_rho"],
                               min_blocks=th["min_independence_blocks"])
    log(f"independence pre-exchange: max|rho| {pre['max_abs_correlation']} "
        f"allow_exchange={pre['allow_exchange']} blocks={pre['n_blocks']}")
    del pre["blocks"]

    ex = dict(stage="exchange", round="H83", started_utc=now(), independence_pre=pre, folds=[],
              donor_rank_min=th["donor_rank_min"],
              receiver_rank_interval=th["receiver_rank_interval"],
              cap_per_fold=th["pseudo_cap_per_fold"], min_pixels=th["min_pseudo_pixels"])
    allow = bool(pre["allow_exchange"])
    ex["allowed_exchange"] = allow
    for fold in folds:
        f = fold["fold"]
        preds = {v: np.load(WORK / f"pred_pre_{v}_f{f}.npy") for v in ("A", "B")}
        train_rows = inv[np.flatnonzero((fold["train"] & eligible).ravel())]
        rank_grid = {}
        for v in ("A", "B"):
            r = np.full(preds[v].shape, np.nan, np.float32)
            r[train_rows] = base.pct_rank(preds[v][train_rows])
            rank_grid[v] = base.to_grid(flat, np.nan_to_num(r, nan=-1.0), eligible.shape)
        catd = ndi.distance_transform_edt(~fold["visible"])
        forbidden = fold["region"] | fold["held_all"] | (catd <= 4)
        del catd
        rec = dict(fold=f, train_rows=int(len(train_rows)), forbidden_px=int(forbidden.sum()),
                   directions={})
        pseudo_pos = {}
        for donor, receiver in (("A", "B"), ("B", "A")):
            if not allow:
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
                n_pixels=int(len(idx)), n_segments=len(receipts), segments=receipts[:40],
                mean_donor_rank=float(np.mean([r["mean_donor"] for r in receipts])) if receipts else None,
                mean_receiver_rank=(float(np.mean([r["mean_receiver"] for r in receipts]))
                                    if receipts else None))
            log(f"fold {f} {donor}->{receiver}: {len(idx)} pseudo px in {len(receipts)} segments")
        ex["folds"].append(rec)
        rng = np.random.default_rng(SEED + 100 + f)
        rows, y = base.sample_train(fold, cat, rng)
        for view, names in (("A", va), ("B", vb)):
            extra = pseudo_pos.get(view, np.empty(0, np.int64))
            extra_rows = extra[inv[extra] >= 0] if len(extra) else np.empty(0, np.int64)
            r2 = np.concatenate([rows, extra_rows]) if len(extra_rows) else rows
            y2 = (np.concatenate([y, np.ones(len(extra_rows), np.int8)])
                  if len(extra_rows) else y)
            X = store.gather(r2, names)
            m = base.learner_for(view, SEED + 7)
            m.fit(X, y2)
            del X
            p = base.predict_flat(store, m, names, flat)
            np.save(WORK / f"pred_post_{view}_f{f}.npy", p)
            pos_idx = inv[np.flatnonzero((fold["truth"] & fold["region"]).ravel())]
            catd = ndi.distance_transform_edt(~cat)
            neg_idx = inv[np.flatnonzero((fold["region"] & ~cat & ~offcat & (catd > 5)).ravel())]
            op_idx = inv[np.flatnonzero(fold["offcat_truth"].ravel())]
            del catd
            auc = float(roc_auc_score(np.r_[np.ones(len(pos_idx)), np.zeros(len(neg_idx))],
                                      np.r_[p[pos_idx], p[neg_idx]]))
            oauc = (float(roc_auc_score(np.r_[np.ones(len(op_idx)), np.zeros(len(neg_idx))],
                                        np.r_[p[op_idx], p[neg_idx]]))
                    if len(op_idx) > 50 else None)
            rec["directions"][f"refit_{view}"] = dict(
                n_pseudo_added=int(len(extra_rows)), n_train_total=int(len(r2)),
                heldout_region_auc=auc, offcatalogue_auc=oauc)
            log(f"fold {f} refit {view}: +{len(extra_rows)} pseudo, I1-AUC {auc:.4f} I2-AUC {oauc}")
    ex.update(finished_utc=now(),
              total_pseudo_pixels=int(sum(d.get("n_pixels", 0) for r in ex["folds"]
                                          for d in r["directions"].values())),
              rule="exactly one exchange; no second round; no post-result hyperparameter search")
    write("pseudo_exchange", ex)
    write("independence", dict(round="H83", pre=pre, allow_exchange=allow,
                               block_statistics=f"{th['block_side_px']}x{th['block_side_px']} px blocks "
                                                "of held-out catalogue-zero proxies",
                               negative_class="held-out catalogue-zero proxies, not verified absence"))
    return ex


# --------------------------------------------------------------------------------------------
# stage: holdout -- both instruments
# --------------------------------------------------------------------------------------------
def _arm_fields(r_pre_A, r_pre_B, r_post_A, r_post_B, allowed_idx, shape, rng):
    out = {
        "single_A": np.full(shape, -1.0, np.float32),
        "single_B": np.full(shape, -1.0, np.float32),
        "union_max": np.full(shape, -1.0, np.float32),
        "A_only": np.full(shape, -1.0, np.float32),
        "B_only": np.full(shape, -1.0, np.float32),
        "disagreement_post": np.full(shape, -1.0, np.float32),
    }
    rpA = base.pct_rank(r_pre_A.ravel()[allowed_idx])
    rpB = base.pct_rank(r_pre_B.ravel()[allowed_idx])
    rqA = base.pct_rank(r_post_A.ravel()[allowed_idx])
    rqB = base.pct_rank(r_post_B.ravel()[allowed_idx])
    for name, vals in (("single_A", rpA), ("single_B", rpB),
                       ("union_max", np.maximum(rpA, rpB)),
                       ("A_only", rpA - rpB), ("B_only", rpB - rpA),
                       ("disagreement_post", rqA - rqB)):
        out[name].ravel()[allowed_idx] = vals
    rnd = np.full(shape, -1.0, np.float32)
    rnd.ravel()[allowed_idx] = rng.random(len(allowed_idx), dtype=np.float32)
    out["random"] = rnd
    return out


def place_arm(arm, fields, pool_mask, K, min_px, quota_fraction=0.25):
    """Matched-budget placement for one arm.

    Every ordinary arm is a plain hard-core top-k at ``K`` dots.  ``E3_single_B_quota`` reserves
    ``quota_fraction`` of the budget for the disagreement (A-only) field *before* ranking, because at
    a fixed budget the pure-disagreement pixels are otherwise always outranked by consensus pixels
    and the discovery signal can never appear in an emission at all.
    """
    if arm != "E3_single_B_quota":
        return nodes.spacing_select(fields[arm], pool_mask, K, min_px=min_px)
    q = int(round(quota_fraction * K))
    quota = nodes.spacing_select(fields["A_only"], pool_mask, q, min_px=min_px)
    from gems52 import gates as _g
    halo = ndi.binary_dilation(quota, structure=_g._disk(min_px))
    rest = nodes.spacing_select(fields["single_B"], pool_mask & ~halo, K - q, min_px=min_px)
    return quota | rest


def _score_instrument(name, folds, fields_for_fold, pool, K, min_px, eligible, block_side=200,
                      draws=1000, seed=SEED, truth_key="truth", visible_key="visible",
                      quota_fraction=0.25, evidence_class="HOLDOUT-DTI"):
    """fields_for_fold(fold) -> dict arm->field grid; pool maps fold id -> allowed mask."""
    terms = {a: None for a in ARMS}
    recs = []
    for fold in folds:
        f = fold["fold"]
        fields = fields_for_fold(fold)
        ifold = dict(fold=f, region=fold["region"], truth=fold[truth_key],
                     visible=fold[visible_key])
        rec = dict(fold=f, arms={}, truth_px=int(fold[truth_key].sum()),
                   region_px=int(fold["region"].sum()), allowed_px=int(pool[f].sum()))
        for arm in ARMS:
            t0 = time.time()
            em = place_arm(arm, fields, pool[f], K, min_px, quota_fraction)
            n = int(em.sum())
            result, term = evaluator.evaluate(em.astype(np.float32), ifold, eligible,
                                              block_side=block_side)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            row = dict(result)
            row.update(placed=n, requested=K, filled=bool(n == K), seconds=round(time.time() - t0, 1))
            rec["arms"][arm] = row
            log(f"  [{name}] fold {f} {arm}: {n}/{K} DTI {result['dti']:.6f} tpw {result['tpw']:.1f}")
        recs.append(rec)
    pooled = evaluator.pooled_summary(terms, draws=draws, seed=seed, candidate="disagreement_post",
                                      evidence_class=evidence_class)
    return dict(instrument=name, folds=recs, pooled=pooled,
                all_arms_filled=bool(all(a["arms"][arm]["filled"] for a in recs for arm in ARMS)))


def stage_holdout():
    reg, store, cat, eligible, folds, va, vb, ring_px, offcat, offcat_b = setup()
    th = reg["thresholds"]
    flat = store.flat_idx
    K = int(th["budget_dots_per_fold_per_arm"])
    min_px = float(th["min_dot_separation_px"])
    ex = json.loads((EVID / "h83_pseudo_exchange.json").read_text())
    cat_dist_all = ndi.distance_transform_edt(~cat)

    # pools: I1 uses the fold's VISIBLE catalogue; I2 masks the WHOLE catalogue, because the
    # organiser's mask is the whole catalogue and I2's truth is a different compilation.
    pool1, pool2 = {}, {}
    for fold in folds:
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        pool1[fold["fold"]] = fold["region"] & ~fold["visible"] & (vis_dist > ring_px)
        pool2[fold["fold"]] = fold["region"] & ~cat & (cat_dist_all > ring_px)
        del vis_dist
    del cat_dist_all

    pre = {f["fold"]: {v: base.to_grid(flat, np.load(WORK / f"pred_pre_{v}_f{f['fold']}.npy"),
                                       eligible.shape) for v in ("A", "B")} for f in folds}
    post = {f["fold"]: {v: base.to_grid(flat, np.load(WORK / f"pred_post_{v}_f{f['fold']}.npy"),
                                        eligible.shape) for v in ("A", "B")} for f in folds}

    out = dict(stage="holdout", round="H83", started_utc=now(), budget_per_arm_per_fold=K,
               min_separation_px=min_px, arms=list(ARMS),
               exchange_pseudo_pixels=ex.get("total_pseudo_pixels"),
               exchange_allowed=ex.get("allowed_exchange"),
               independence_max_abs_rho=(ex.get("independence_pre") or {}).get("max_abs_correlation"),
               caveat="HOLDOUT-DTI on gems52-pooled-hide-v1 screens procedures; it does not rank "
                      "the leaderboard (Spearman -0.10, knowledge/10). OFFCAT-DTI on "
                      "gems52-offcatalogue-v1 is a second, differently-biased proxy and is "
                      "reported separately; it can demote but never promote.")

    # I2b: the same instrument with the catalogue-distance cut at 0 px, so the two bracket the
    # extension population the organiser says the new-fault truth contains (amendment 74a).
    for fold in folds:
        fold["offcat_truth_b"] = offcat_b & fold["region"]

    for instr, pool, truth_key, visible_key, key in (
            ("gems52-pooled-hide-v1", pool1, "truth", "visible", "pooled"),
            ("gems52-offcatalogue-v1", pool2, "offcat_truth", "catalogue_full", "offcatalogue"),
            ("gems52-offcatalogue-b-v1", pool2, "offcat_truth_b", "catalogue_full",
             "offcatalogue_b")):
        for fold in folds:
            fold["catalogue_full"] = cat
        log(f"=== instrument {instr} ===")

        def fields_for_fold(fold, pool=pool):
            idx = np.flatnonzero(pool[fold["fold"]].ravel())
            rng = np.random.default_rng(SEED + 500 + fold["fold"])
            return _arm_fields(pre[fold["fold"]]["A"], pre[fold["fold"]]["B"],
                               post[fold["fold"]]["A"], post[fold["fold"]]["B"],
                               idx, eligible.shape, rng)

        res = _score_instrument(instr, folds, fields_for_fold, pool, K, min_px, eligible,
                                block_side=200, draws=int(th["bootstrap_draws"]), seed=SEED,
                                truth_key=truth_key, visible_key=visible_key,
                                evidence_class=("HOLDOUT-DTI" if key == "pooled" else "OFFCAT-DTI"))
        out[key] = res
        out[f"{key}_evidence_class"] = ("HOLDOUT-DTI" if key == "pooled" else "OFFCAT-DTI")

    write("holdout", out)
    return out


# --------------------------------------------------------------------------------------------
# stage: build -- stitch, place, gate, write
# --------------------------------------------------------------------------------------------
def stage_build():
    reg, store, cat, eligible, folds, va, vb, ring_px, offcat, offcat_b = setup()
    th = reg["thresholds"]
    flat, inv = store.flat_idx, store.inverse
    WORK.mkdir(parents=True, exist_ok=True)
    hold = json.loads((EVID / "h83_holdout.json").read_text())
    shape = eligible.shape

    with rasterio.open(SAMPLE) as ref:
        sub = ref.read(1)
    sub_finite = np.isfinite(sub) & (sub > -1e38)
    del sub

    mos = {}
    for tag, v in (("pre", "A"), ("pre", "B"), ("post", "A"), ("post", "B")):
        g = np.full(int(np.prod(shape)), np.nan, np.float32)
        for fold in folds:
            rows = inv[np.flatnonzero(fold["region"].ravel())]
            rows = rows[rows >= 0]
            p = np.load(WORK / f"pred_{tag}_{v}_f{fold['fold']}.npy")
            g[np.flatnonzero(fold["region"].ravel())] = p[rows]
        mos[f"{tag}_{v}"] = g.reshape(shape)
        del g
    covered = np.isfinite(mos["post_A"]) & np.isfinite(mos["post_B"])
    if not (covered == eligible).all():
        raise SystemExit(f"OOF mosaic covers {int(covered.sum())} px, eligible {int(eligible.sum())}")

    cat_dist = ndi.distance_transform_edt(~cat, sampling=100.0)
    allowed = eligible & sub_finite & ~cat & (cat_dist > th["catalogue_exclusion_m"])
    allowed_idx = np.flatnonzero(allowed.ravel())
    log(f"emission domain: eligible {int(eligible.sum())} -> allowed {int(allowed.sum())}")

    rk = {}
    for tag in ("pre", "post"):
        for v in ("A", "B"):
            r = np.zeros(shape, np.float32)
            r.ravel()[allowed_idx] = base.pct_rank(mos[f"{tag}_{v}"].ravel()[allowed_idx])
            rk[f"{tag}_{v}"] = r

    # ---- E1: the lane's literal discovery field;  E2: union_post with a reserved A-only quota
    e1 = np.where(allowed, rk["post_A"] - rk["post_B"], -1.0).astype(np.float32)
    union_post = np.where(allowed, np.maximum(rk["post_A"], rk["post_B"]), -1.0).astype(np.float32)
    a_only_field = np.where(allowed, rk["post_A"] - rk["post_B"], -1.0).astype(np.float32)

    K = int(th["budget_dots_total"])
    min_px = float(th["min_dot_separation_px"])
    q = int(round(th["discovery_quota_fraction"] * K))

    single_b_field = np.where(allowed, rk["pre_B"], -1.0).astype(np.float32)
    fields_all = dict(single_A=np.where(allowed, rk["pre_A"], -1.0).astype(np.float32),
                      single_B=single_b_field, union_max=union_post,
                      A_only=a_only_field, B_only=np.where(allowed, rk["pre_B"] - rk["pre_A"],
                                                           -1.0).astype(np.float32),
                      disagreement_post=e1)

    q_frac = float(th["discovery_quota_fraction"])

    def _quota(base_field):
        qn = int(round(q_frac * K))
        quota = nodes.spacing_select(a_only_field, allowed, qn, min_px=min_px)
        halo = ndi.binary_dilation(quota, structure=gates._disk(min_px))
        rest = nodes.spacing_select(base_field, allowed & ~halo, K - qn, min_px=min_px)
        return (quota | rest), dict(quota_dots=int(quota.sum()), consensus_dots=int(rest.sum()),
                                    reserved_fraction=q_frac)

    e1_dots = nodes.spacing_select(e1, allowed, K, min_px=min_px, log=log)
    e2_dots, e2_meta = _quota(union_post)
    e3_dots, e3_meta = _quota(single_b_field)

    # ---- shipment rule (amendment 74a): ship whichever of E1/E2/E3 has the highest MEASURED
    #      pooled gems52-pooled-hide-v1 DTI.  E2's and E3's measured surrogates are the union_max
    #      and E3_single_B_quota arms, which are the same fields under the same budget and spacing.
    p = hold["pooled"]["pooled"]
    for arm in ("disagreement_post", "union_max", "E3_single_B_quota"):
        if arm not in p["scores"]:
            raise SystemExit(f"holdout receipt is missing the arm {arm}")
    d_e1 = float(p["scores"]["disagreement_post"]["dti"])
    d_e2 = float(p["scores"]["union_max"]["dti"])
    d_e3 = float(p["scores"]["E3_single_B_quota"]["dti"])
    chosen = max((("E1", d_e1), ("E2", d_e2), ("E3", d_e3)), key=lambda kv: kv[1])[0]
    dots = {"E1": e1_dots, "E2": e2_dots, "E3": e3_dots}[chosen]
    field_for_lane = {"E1": e1, "E2": union_post, "E3": single_b_field}[chosen]
    log(f"shipment selection: E1 {d_e1:.6f} / E2 {d_e2:.6f} / E3 {d_e3:.6f} -> {chosen}")

    n_dots = int(dots.sum())
    pred = dots.astype(np.float32)
    if not np.isfinite(pred).all() or pred.min() < 0 or pred.max() > 1:
        raise SystemExit("emission is not finite [0,1]")
    if (pred > 0).any() and not ((pred > 0) <= allowed).all():
        raise SystemExit("mass outside the allowed domain")

    # ---- not merely the union of the two views
    a_em = nodes.spacing_select(np.where(allowed, rk["post_A"], -1.0).astype(np.float32),
                                allowed, n_dots, min_px=min_px)
    b_em = nodes.spacing_select(np.where(allowed, rk["post_B"], -1.0).astype(np.float32),
                                allowed, n_dots, min_px=min_px)
    u_em = nodes.spacing_select(union_post, allowed, n_dots, min_px=min_px)
    not_union = dict(
        dots_shared_with_view_A=int((dots & a_em).sum()),
        dots_shared_with_view_B=int((dots & b_em).sum()),
        dots_shared_with_union_max=int((dots & u_em).sum()),
        jaccard_with_union_max=float((dots & u_em).sum() / max(1, int((dots | u_em).sum()))),
        spearman_field_vs_unionmax=float(np.corrcoef(
            rankdata(np.where(allowed, field_for_lane, 0).ravel()[allowed_idx]),
            rankdata(union_post.ravel()[allowed_idx]))[0, 1]),
        verdict="PASS" if int((dots & u_em).sum()) != n_dots else "FAIL: identical to union_max")

    stem = f"gems52-h83-offcatalogue-cotrain-{n_dots}px-{chosen.lower()}"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"h83-offcatalogue-cotrain-{n_dots}px-{chosen.lower()}-{stamp}"
    note = (f"H83 cotrain: geophysical vs surface disagreement, off-catalogue instrument, "
            f"{chosen}, {n_dots} dots 3px, >200m off catalogue; research-only")
    if len(note) > 140:
        note = (f"H83 cotrain disagreement ({chosen}), off-catalogue instrument, {n_dots} dots "
                f"3px, >200m off catalogue; research-only")
    SUBM.mkdir(exist_ok=True)
    path = SUBM / f"{stem}-{stamp}.tif"
    receipt = submission_writer.write_submission(
        path, pred, SAMPLE, sub_finite, note=note, name=name[:140],
        metadata=dict(round="H83", seed=SEED, budget=K, placed=n_dots, chosen_arm=chosen,
                      e1=dict(dti_i1=d_e1), e2=dict(dti_i1=d_e2, **e2_meta),
                      e3=dict(dti_i1=d_e3, **e3_meta),
                      min_separation_px=min_px,
                      catalogue_exclusion_m=th["catalogue_exclusion_m"],
                      not_union=not_union,
                      instruments=["gems52-pooled-hide-v1", "gems52-offcatalogue-v1"]))
    log(f"wrote {path} sha256 {receipt['sha256']} bytes {receipt['bytes']} dots {n_dots}")

    # a portal-exact NaN-outside twin, byte-structurally identical to the organiser template
    twin = SUBM / f"{stem}-{stamp}-template-nan.tif"
    twin_receipt = grid.write_geotiff_portal_exact(
        twin, np.where(eligible & sub_finite, pred, 0.0).astype(np.float32),
        eligible & sub_finite, SAMPLE)
    log(f"wrote template-exact twin {twin.name} sha256 {twin_receipt['sha256']}")

    out = dict(stage="build", round="H83", finished_utc=now(),
               chosen=chosen, e1_i1_dti=d_e1, e2_i1_dti=d_e2, e3_i1_dti=d_e3,
               placed=n_dots, budget=K, quota=e2_meta, not_union=not_union,
               receipt=receipt, twin=dict(file=twin.name, sha256=twin_receipt["sha256"],
                                          bytes=twin_receipt["bytes"]),
               allowed_px=int(allowed.sum()))
    write("submission", out)
    (SUBM / "H83_LATEST.txt").write_text(path.name + "\n")
    return out


# --------------------------------------------------------------------------------------------
# stage: lane -- uniqueness / lane-drift gate on the surface and on the dots
# --------------------------------------------------------------------------------------------
def stage_lane():
    reg, store, cat, eligible, folds, va, vb, ring_px, offcat, offcat_b = setup()
    th = reg["thresholds"]
    b = json.loads((EVID / "h83_submission.json").read_text())
    path = SUBM / b["receipt"]["file"]
    with rasterio.open(path) as ds:
        cand = ds.read(1)
    with rasterio.open(SAMPLE) as ref:
        sub = ref.read(1)
    sub_finite = np.isfinite(sub) & (sub > -1e38)
    del sub
    cat_dist = ndi.distance_transform_edt(~cat, sampling=100.0)
    allowed = eligible & sub_finite & ~cat & (cat_dist > th["catalogue_exclusion_m"])

    priors, pmeta = prior_paths(CENSUS, ("submission",))
    priors = [p for p in priors if not p.name.startswith(PREFIX) and p.exists()]
    log(f"registry: {len(priors)} rasters {pmeta}")

    surf = np.where(allowed, cand, 0.0).astype(np.float32)
    if np.ptp(surf[allowed]) == 0:
        raise SystemExit("constant surface: no rank-uniqueness evidence")
    lane_surface = gates.lane_report(surf, allowed, priors, sample=SAMPLE, phase="surface", log=log)
    lane_dots = gates.lane_report(cand.astype(np.float32), allowed, priors, sample=SAMPLE,
                                  phase="dots", log=log)
    write("lane_surface", lane_surface)
    write("lane_dots", lane_dots)

    # ---- three readings, published side by side, none of them waives another
    def reading(rep):
        return dict(literal=rep["literal"]["verdict"], policy=rep["policy"]["verdict"],
                    max_spearman=rep["literal"]["max_spearman"],
                    max_near_3px_fraction=rep["literal"]["max_near_3px_fraction"],
                    policy_max_near_3px_fraction=rep["policy"]["max_near_3px_fraction"],
                    probes=rep["policy"]["universal_coverage_probes"],
                    identical_to_a_prior=bool(rep["literal"]["identical"]))

    # Scored-only registry: the restored rasters that the organiser actually scored.  These live in
    # data/scored and data/reference, not in the frozen census, so they are added explicitly.
    scored = sorted((ROOT / "data/scored").glob("*.tif"))
    ref = ROOT / "data/reference/h33-2-b2-zeros.tif"
    if ref.exists():
        scored = scored + [ref]
    scored_only = None
    if scored:
        scored_only = dict(registry="data/scored/*.tif + data/reference/h33-2-b2-zeros.tif",
                           n_priors=len(scored),
                           surface=reading(gates.lane_report(surf, allowed, scored, sample=SAMPLE,
                                                             phase="surface", log=log)),
                           dots=reading(gates.lane_report(cand.astype(np.float32), allowed, scored,
                                                          sample=SAMPLE, phase="dots", log=log)))
        write("lane_scored_only", scored_only)

    out = dict(stage="lane", round="H83", finished_utc=now(),
               registry=dict(n_priors=len(priors), n_scored=len(scored), meta=pmeta),
               surface=reading(lane_surface), dots=reading(lane_dots),
               scored_only=scored_only,
               note="The literal full-census dots rule is unsatisfiable for every nonempty raster "
                    "because the census contains universal-coverage lattice probes; a policy or "
                    "scored-only PASS is reported as a third reading and never waives it.")
    write("lane_summary", out)
    return out


# --------------------------------------------------------------------------------------------
# stage: card
# --------------------------------------------------------------------------------------------

def composition_card() -> dict:
    """What the shipped 3 px lattice is actually made of.

    The publisher re-scores every emitted cell against both views' out-of-fold ranks at the
    preregistered donor/abstention thresholds and writes evidence/h83_emission_composition.json.
    The card carries that split next to the verdict so the number is auditable: how much of the
    raster is the discovery branch this lane exists to test, and how much is density filler.
    """
    path = EVID / "h83_emission_composition.json"
    if not path.exists():
        return dict(available=False,
                    note=("not measured; run scripts/publish_h83_site.py to classify every emitted "
                          "cell against both views' out-of-fold ranks"))
    c = json.loads(path.read_text())
    cls = c["emitted_by_class"]
    n = max(int(c.get("rows", 0)), 1)
    return dict(available=True, evidence_class="MEASURED", rows=int(c["rows"]),
                donor_rank_min=c["donor_rank_min"],
                receiver_rank_interval=c["receiver_rank_interval"],
                emitted_by_class=cls,
                share_of_emission={k: v / n for k, v in cls.items()},
                a_only_cells=cls.get("A-only: A confident, B abstains "
                                     "(candidate buried structure)", 0),
                b_only_cells=cls.get("B-only: B confident, A abstains "
                                     "(suspect surface artefact)", 0),
                note=("classification measured on the shipped raster, not projected; "
                      "'neither view confident' cells are there because the 3 px lattice has to be "
                      "filled to the budget, not because either view selected them"))


def stage_card():
    reg = json.loads(PREREG.read_text())
    hold = json.loads((EVID / "h83_holdout.json").read_text())
    fit = json.loads((EVID / "h83_fit_checkpoint.json").read_text())
    can = json.loads((EVID / "h83_canary.json").read_text())
    ind = json.loads((EVID / "h83_independence.json").read_text())
    ex = json.loads((EVID / "h83_pseudo_exchange.json").read_text())
    sub = json.loads((EVID / "h83_submission.json").read_text())
    lane = json.loads((EVID / "h83_lane_summary.json").read_text())
    p = hold["pooled"]["pooled"]
    o = hold["offcatalogue"]["pooled"]
    o_b = hold["offcatalogue_b"]["pooled"]
    cand = "disagreement_post"
    d = p["paired_differences"]["single_B"]
    verdict = "promote" if d["ci95"][0] > 0 else "negative"
    card = dict(
        round="H83",
        hypothesis=("Two-view co-training disagreement, evaluated on two instruments: the mandated "
                    "hide-and-recover and a new off-catalogue instrument whose truth is a fault "
                    "compilation the competition catalogue does not contain (SGMC at >= 300 m from "
                    "labels.tif)."),
        mechanism=("View A (potential-field/subsurface, 36 ch) and View B (surface DEM curvature "
                   "+ slope + radiometric band 6, 37 ch) are fitted per label-blind quadrant; "
                   "independence is screened on 50 px blocks of held-out proxy negatives; one "
                   "whole-segment, block-confined pseudo-label round follows; the discovery field "
                   "is the rank difference A-B (A confident, B abstains = candidate buried "
                   "structure)."),
        named_non_fault_mimic=("A lithologic contact or a basin-fill thickness change: both make "
                               "gravity/conductivity steps and basement-depth gradients with no "
                               "fault. Second mimic: flight-line/grid seams in the airborne "
                               "magnetic and radiometric grids. Surface branch: roads, canals and "
                               "erosion lines, which is what B-only disagreement flags."),
        holdout=dict(evidence_class="HOLDOUT-DTI", evaluator="gems52-pooled-hide-v1",
                     withheld_positive_pixels=p["scores"][cand]["withheld_positive_pixels"],
                     dti=p["scores"][cand]["dti"], ci95=p["scores"][cand]["ci95"],
                     paired_vs_single_B=dict(delta=d["delta"], ci95=d["ci95"]),
                     shipped_arm_dti={k: p["scores"][k]["dti"]
                                      for k in ("disagreement_post", "union_max",
                                                "E3_single_B_quota")},
                     all_arms={k: dict(dti=v["dti"], ci95=v["ci95"])
                               for k, v in p["scores"].items()},
                     all_arms_filled=hold["pooled"]["all_arms_filled"]),
        offcatalogue=dict(evidence_class="OFFCAT-DTI", evaluator="gems52-offcatalogue-v1",
                          note="diagnostic proxy only; cannot promote",
                          all_arms={k: dict(dti=v["dti"], ci95=v["ci95"])
                                    for k, v in o["scores"].items()},
                          all_arms_filled=hold["offcatalogue"]["all_arms_filled"]),
        offcatalogue_b=dict(evidence_class="OFFCAT-DTI", evaluator="gems52-offcatalogue-b-v1",
                            note="amendment 74a: catalogue-distance cut 0 px, so trace extensions are "
                                 "included. Diagnostic proxy only; cannot promote.",
                            all_arms={k: dict(dti=v["dti"], ci95=v["ci95"])
                                      for k, v in o_b["scores"].items()},
                            all_arms_filled=hold["offcatalogue_b"]["all_arms_filled"]),
        independence=dict(max_abs_rho=ind["pre"]["max_abs_correlation"],
                          allow_exchange=ind["allow_exchange"],
                          blocks=ind["pre"]["n_blocks"],
                          negative_class=ind["pre"]["negative_class"]),
        canary=dict(max_alarm_across_folds=can["max_alarm_across_folds"],
                    any_alarm=can["any_alarm"]),
        exchange=dict(total_pseudo_pixels=ex["total_pseudo_pixels"],
                      allowed=ex["allowed_exchange"],
                      pixels_a_to_b=sum(int(f["directions"].get("A->B", {}).get("n_pixels", 0))
                                        for f in ex["folds"]),
                      pixels_b_to_a=sum(int(f["directions"].get("B->A", {}).get("n_pixels", 0))
                                        for f in ex["folds"])),
        view_a_heldout_auc=[f["view_A"]["heldout_region_auc"] for f in fit["folds"]],
        view_b_heldout_auc=[f["view_B"]["heldout_region_auc"] for f in fit["folds"]],
        view_a_offcatalogue_auc=[f["view_A"]["offcatalogue_auc"] for f in fit["folds"]],
        view_b_offcatalogue_auc=[f["view_B"]["offcatalogue_auc"] for f in fit["folds"]],
        lane=dict(surface=lane["surface"], dots=lane["dots"], scored_only=lane["scored_only"]),
        not_union=sub["not_union"],
        raster=dict(file=sub["receipt"]["file"], sha256=sub["receipt"]["sha256"],
                    bytes=sub["receipt"]["bytes"], dots=sub["placed"],
                    validator=sub["receipt"]["validator"]),
        template_exact_twin=sub["twin"],
        emission=composition_card(),
        submission_name=sub["receipt"]["submission_name"],
        note=sub["receipt"]["note"],
        submission_slots_used=0,
        verdict=verdict,
        verdict_reason=("paired CI lower bound against single_B on gems52-pooled-hide-v1 is "
                        f"{d['ci95'][0]:.6f}; the frozen rule requires > 0")
        if verdict == "negative" else "frozen promotion rule met",
        download="YES",
        submit=("YES (eligible)" if verdict == "promote" else "NO - research artefact only"),
    )
    write("run_card", card)
    log(json.dumps({k: card[k] for k in ("round", "verdict", "download", "submit")}, indent=1))
    return card


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["canary", "fit", "exchange", "holdout", "build", "lane",
                                      "card", "all"])
    args = ap.parse_args()
    stages = ["canary", "fit", "exchange", "holdout", "build", "lane", "card"] \
        if args.stage == "all" else [args.stage]
    fn = {"canary": stage_canary, "fit": stage_fit, "exchange": stage_exchange,
          "holdout": stage_holdout, "build": stage_build, "lane": stage_lane, "card": stage_card}
    for s in stages:
        t0 = time.time()
        log(f"=== H83 stage {s} ===")
        fn[s]()
        log(f"--- stage {s} done in {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
