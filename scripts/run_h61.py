#!/usr/bin/env python3
"""H61 -- deep-sharp two-view co-training, matched-budget, on the corrected label-blind folds.

Lane: the brief's co-training paragraph.  View A is potential-field/subsurface, View B is surface
(DEM curvature and slope plus the radiometric channels), and disagreement is the discovery signal.
Preregistered in ``knowledge/30_hypotheses_H61_preregistered.md`` and pinned by
``registry/h61_preregistration.json``; this runner refuses to start if either hash has moved.

Shared tools are used, not forked: ``gems52.structural`` feature store (extended once, in the
template, by ``gems52.external``), ``gems52.spatial.folds`` label-blind-quadrants-v2,
``gems52.nodes.spacing_select`` metric-aware placement, ``gems52.evaluate_holdout``
(gems52-pooled-hide-v1), ``gems52.metric``, ``gems52.submission_writer``, ``gems52.gates``.

Stages (checkpointed, resumable, never silently re-tuned):
    canary    raw single-feature leakage canary on every fold's held-out sample
    fit       fit both views per fold, predict on the whole eligible domain
    exchange  exactly one confident-to-abstaining whole-segment pseudo-label round, then refit
    holdout   matched-budget hide-and-recover comparison of six arms, pooled DTI + 95% CI

Nothing here writes a submission; ``scripts/build_h61_submission.py`` does that.
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

import numpy as np                                                   # noqa: E402
import rasterio                                                      # noqa: E402
from scipy import ndimage as ndi                                     # noqa: E402
from scipy.stats import rankdata                                     # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier          # noqa: E402
from sklearn.metrics import roc_auc_score                            # noqa: E402

from gems52 import evaluate_holdout as evaluator                     # noqa: E402
from gems52 import nodes, spatial, structural                        # noqa: E402

WORK = ROOT / "work/h61"
EVID = ROOT / "evidence"
DOCS = ROOT / "docs/data"
SEED = 61052
STORE = "work/r2/features"
ARMS = ("single_A", "single_B", "union_max", "disagreement_pre", "disagreement_post", "random")
PRED = ("pre_A", "pre_B", "post_A", "post_B")


def log(*a, **k):
    print(*a, flush=True, **k)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write(name: str, obj) -> Path:
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"h61_{name}.json"
    p.write_text(json.dumps(obj, indent=1, allow_nan=False, default=str) + "\n")
    (DOCS / f"h61_{name}.json").write_text(p.read_text())
    return p


def digest(path) -> str:
    return structural.digest(Path(path))


# --------------------------------------------------------------------------------------------
# setup
# --------------------------------------------------------------------------------------------
def setup():
    reg = json.loads((ROOT / "registry/h61_preregistration.json").read_text())
    doc = ROOT / reg["hypothesis_document"]
    if digest(doc) != reg["hypothesis_sha256"]:
        raise SystemExit("preregistered hypothesis document changed after registration")
    pins = {f["id"]: f for f in json.loads((ROOT / "registry/data_manifest.json").read_text())["files"]}
    for key in ("training_features", "labels", "sample_submission"):
        if digest(ROOT / "data" / pins[key]["dest"]) != pins[key]["sha256"]:
            raise SystemExit(f"input pin mismatch: {key}")
    store = structural.FeatureStore(ROOT / STORE)
    if not store.manifest["version"].endswith("+external-geodawn-v1"):
        raise SystemExit("feature store has not been extended with the shared external layers; "
                         "run: PYTHONPATH=src python -m gems52.external")
    if store.manifest["inputs"]["features_sha256"] != pins["training_features"]["sha256"]:
        raise SystemExit("stale feature cache: built from different bytes")
    va = store.manifest["view_A_with_external"]
    vb = store.manifest["view_B_with_external"]
    if set(va) & set(vb):
        raise SystemExit(f"cross-view feature overlap: {sorted(set(va) & set(vb))}")
    if "raw_band_06" not in vb:
        raise SystemExit("band 6 (radiometric total count) is not isolated in View B")
    if not any(n.startswith("X_mag_TMI_up150") for n in va):
        raise SystemExit("View A is missing the upward-continued TMI channels")
    if not any(n.startswith("X_rad_") for n in vb):
        raise SystemExit("View B is missing the external radiometric channels")
    with rasterio.open(ROOT / "data/labels.tif") as ds, \
            rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        if (ds.shape, ds.crs, ds.transform) != (ref.shape, ref.crs, ref.transform):
            raise SystemExit("labels grid mismatch")
        cat = ds.read(1) == 1
    eligible = store.valid
    t0 = time.time()
    folds = list(spatial.folds(cat, eligible, buffer_px=reg["thresholds"]["buffer_px"]))
    log(f"folds built in {time.time()-t0:.1f}s: " +
        json.dumps([f["receipt"] for f in folds], default=str)[:400])
    # label-blind visible-catalogue collar, in metres -> pixels at 100 m
    ring_px = int(round(reg["thresholds"]["catalogue_exclusion_m"] / 100.0))
    return reg, store, cat, eligible, folds, va, vb, ring_px


def sample_train(fold, cat, rng, max_pos=20000, max_neg=60000):
    """Training sample from the fold's own domain only, using the fold's visible catalogue."""
    pos = np.flatnonzero((fold["train"] & fold["visible"]).ravel())
    vis_dist = ndi.distance_transform_edt(~fold["visible"])
    neg = np.flatnonzero((fold["train"] & ~cat & (vis_dist > 5)).ravel())
    del vis_dist
    if len(pos) < 100 or len(neg) < 100:
        raise SystemExit("insufficient training classes")
    pos = rng.choice(pos, min(max_pos, len(pos)), replace=False)
    neg = rng.choice(neg, min(max_neg, len(neg)), replace=False)
    rows = np.concatenate([pos, neg])
    y = np.concatenate([np.ones(len(pos), np.int8), np.zeros(len(neg), np.int8)])
    order = rng.permutation(len(rows))
    return rows[order], y[order]


def learner(seed=SEED):
    return HistGradientBoostingClassifier(max_iter=250, learning_rate=0.08, max_leaf_nodes=15,
                                          min_samples_leaf=40, l2_regularization=1.0,
                                          early_stopping=False, random_state=seed)


def predict_flat(store, model, names, rows, chunk=250_000) -> np.ndarray:
    """Chunked prediction over flat grid indices; bounds peak memory on a 3 GB box."""
    out = np.empty(len(rows), np.float32)
    for i in range(0, len(rows), chunk):
        sel = rows[i:i + chunk]
        X = store.gather(sel, names)
        out[i:i + chunk] = model.predict_proba(X)[:, 1].astype(np.float32)
    return out


def to_grid(flat_idx, values, shape) -> np.ndarray:
    g = np.full(int(np.prod(shape)), np.nan, np.float32)
    g[flat_idx] = values
    return g.reshape(shape)


def pct_rank(values: np.ndarray) -> np.ndarray:
    """Operating percentile rank in [0,1] over the finite entries, ties averaged."""
    v = np.asarray(values, np.float64)
    good = np.isfinite(v)
    out = np.full(v.shape, np.nan)
    if good.any():
        out[good] = (rankdata(v[good], method="average") - 0.5) / float(good.sum())
    return out.astype(np.float32)


# --------------------------------------------------------------------------------------------
# stage: canary
# --------------------------------------------------------------------------------------------
def stage_canary():
    reg, store, cat, eligible, folds, va, vb, ring_px = setup()
    th = reg["thresholds"]
    rng = np.random.default_rng(SEED)
    out = dict(stage="canary", started_utc=now(), alarm_auc=th["canary_auc_alarm"],
               evidence_class="HOLDOUT-DTI diagnostic AUC (not a DTI score)", folds=[])
    worst = []
    for fold in folds:
        region = fold["region"]
        pos = np.flatnonzero((fold["truth"] & region).ravel())
        catd = ndi.distance_transform_edt(~cat)
        neg = np.flatnonzero((region & ~cat & (catd > 5)).ravel())
        del catd
        pos = rng.choice(pos, min(20000, len(pos)), replace=False)
        neg = rng.choice(neg, min(40000, len(neg)), replace=False)
        rows = np.concatenate([pos, neg])
        y = np.concatenate([np.ones(len(pos), np.int8), np.zeros(len(neg), np.int8)])
        per_feature = {}
        for name in va + vb:
            x = store.gather(rows, [name])[:, 0]
            auc = float(roc_auc_score(y, x))
            per_feature[name] = dict(auc=auc, direction_insensitive=max(auc, 1 - auc),
                                     view="A" if name in va else "B")
        ranked = sorted(per_feature.items(), key=lambda kv: -kv[1]["direction_insensitive"])
        # Fitted single-feature canary on the five strongest: fit on the fold's TRAINING sample,
        # score the HELD-OUT region sample.  A raw AUC only sees monotone signal; this catches a
        # non-monotone single-feature leak as well.
        tr_rows, tr_y = sample_train(fold, cat, np.random.default_rng(SEED + 900 + fold["fold"]))
        fitted = {}
        for name, _rec in ranked[:5]:
            m = learner(SEED + 1)
            m.fit(store.gather(tr_rows, [name]), tr_y)
            fitted[name] = float(roc_auc_score(
                y, m.predict_proba(store.gather(rows, [name]))[:, 1]))
        alarms = [n for n, r in per_feature.items() if r["direction_insensitive"] > th["canary_auc_alarm"]]
        out["folds"].append(dict(fold=fold["fold"], n_pos=int(len(pos)), n_neg=int(len(neg)),
                                 max_direction_insensitive_auc=ranked[0][1]["direction_insensitive"],
                                 top5=[(n, r["direction_insensitive"]) for n, r in ranked[:5]],
                                 fitted_top5_heldout=fitted, alarms=alarms,
                                 per_feature=per_feature))
        worst += [(fold["fold"], n, r["direction_insensitive"]) for n, r in ranked[:3]]
        log(f"fold {fold['fold']} canary max AUC {ranked[0][1]['direction_insensitive']:.6f} "
            f"({ranked[0][0]}) alarms={alarms}")
    out.update(finished_utc=now(),
               max_alarm_across_folds=max(w[2] for w in worst),
               max_fitted_top5_heldout_auc=max(
                   max(r["fitted_top5_heldout"].values()) for r in out["folds"]),
               any_alarm=bool(any(r["alarms"] for r in out["folds"])),
               dropped_features=sorted({n for r in out["folds"] for n in r["alarms"]}),
               interpretation="AUC above the alarm means leakage until proven otherwise; catalogue-zero "
                              "negatives are proxies, not verified fault absence.")
    write("canary", out)
    return out


# --------------------------------------------------------------------------------------------
# stage: fit
# --------------------------------------------------------------------------------------------
def stage_fit():
    reg, store, cat, eligible, folds, va, vb, ring_px = setup()
    flat = store.flat_idx
    WORK.mkdir(parents=True, exist_ok=True)
    out = dict(stage="fit", started_utc=now(), view_A_features=va, view_B_features=vb,
               n_A=len(va), n_B=len(vb), seed=SEED, folds=[])
    for fold in folds:
        rng = np.random.default_rng(SEED + fold["fold"])
        rows, y = sample_train(fold, cat, rng)
        rec = dict(fold=fold["fold"], n_train=int(len(rows)), n_pos=int(y.sum()),
                   train_domain_px=int(fold["train"].sum()), region_px=int(fold["region"].sum()),
                   truth_px=int(fold["truth"].sum()))
        for view, names in (("A", va), ("B", vb)):
            t0 = time.time()
            X = store.gather(rows, names)
            m = learner(SEED)
            m.fit(X, y)
            in_auc = float(roc_auc_score(y, m.predict_proba(X)[:, 1]))
            del X
            t1 = time.time()
            p = predict_flat(store, m, names, flat)
            np.save(WORK / f"pred_pre_{view}_f{fold['fold']}.npy", p)
            # held-out read inside the evaluation region only
            inv = store.inverse
            pos_idx = inv[np.flatnonzero((fold["truth"] & fold["region"]).ravel())]
            catd = ndi.distance_transform_edt(~cat)
            neg_idx = inv[np.flatnonzero((fold["region"] & ~cat & (catd > 5)).ravel())]
            del catd
            oof_auc = float(roc_auc_score(
                np.r_[np.ones(len(pos_idx)), np.zeros(len(neg_idx))],
                np.r_[p[pos_idx], p[neg_idx]]))
            rec[f"view_{view}"] = dict(fit_seconds=round(t1 - t0, 1),
                                       predict_seconds=round(time.time() - t1, 1),
                                       in_sample_auc=in_auc,
                                       heldout_region_auc=oof_auc,
                                       n_region_pos=int(len(pos_idx)), n_region_neg=int(len(neg_idx)))
            log(f"fold {fold['fold']} view {view}: in-AUC {in_auc:.4f} OOF-region-AUC {oof_auc:.4f} "
                f"({rec[f'view_{view}']['fit_seconds']}s fit)")
        out["folds"].append(rec)
    out.update(finished_utc=now(), evaluator_hashes=evaluator.implementation_hashes())
    write("fit_checkpoint", out)
    return out


# --------------------------------------------------------------------------------------------
# stage: exchange
# --------------------------------------------------------------------------------------------
def stage_exchange():
    reg, store, cat, eligible, folds, va, vb, ring_px = setup()
    th = reg["thresholds"]
    flat = store.flat_idx
    inv = store.inverse
    # ---- independence screen on held-out labelled negatives, before any transfer
    rows_blocks = []
    indep_raw = dict(stage="independence", folds=[])
    for fold in folds:
        pa = to_grid(flat, np.load(WORK / f"pred_pre_A_f{fold['fold']}.npy"), eligible.shape)
        pb = to_grid(flat, np.load(WORK / f"pred_pre_B_f{fold['fold']}.npy"), eligible.shape)
        catd = ndi.distance_transform_edt(~cat)
        neg = fold["region"] & ~cat & (catd > 4) & np.isfinite(pa) & np.isfinite(pb)
        del catd
        qa, qb = pa[neg], pb[neg]
        thresholds = (float(np.quantile(qa, th["donor_rank_min"])),
                      float(np.quantile(qb, th["donor_rank_min"])))
        blocks = spatial.negative_block_errors(np.nan_to_num(pa, nan=0.0), np.nan_to_num(pb, nan=0.0),
                                               neg, fold["fold"], thresholds,
                                               side=th["block_side_px"], minimum=32)
        rows_blocks += blocks
        indep_raw["folds"].append(dict(fold=fold["fold"], n_negatives=int(neg.sum()),
                                       thresholds=list(thresholds), n_blocks=len(blocks)))
        del pa, pb
    pre = spatial.independence(rows_blocks, threshold=th["independence_abandon_max_abs_rho"],
                               min_blocks=20)
    log(f"independence pre-exchange: max|rho| {pre['max_abs_correlation']} "
        f"allow_exchange={pre['allow_exchange']} blocks={pre['n_blocks']}")

    # ---- exactly one confident-to-abstaining whole-segment exchange per direction per fold
    ex = dict(stage="exchange", started_utc=now(), independence_pre=pre, folds=[],
              donor_rank_min=th["donor_rank_min"], receiver_rank_interval=th["receiver_rank_interval"],
              cap_per_fold=th["pseudo_cap_per_fold"], min_pixels=th["min_pseudo_pixels"])
    allowed_exchange = bool(pre["allow_exchange"])
    ex["allowed_exchange"] = allowed_exchange
    for fold in folds:
        f = fold["fold"]
        preds = {v: np.load(WORK / f"pred_pre_{v}_f{f}.npy") for v in ("A", "B")}
        train_rows = inv[np.flatnonzero((fold["train"] & eligible).ravel())]
        rank = {v: np.full(preds[v].shape, np.nan, np.float32) for v in ("A", "B")}
        for v in ("A", "B"):
            r = pct_rank(preds[v][train_rows])
            rank[v][train_rows] = r
        rank_grid = {v: to_grid(flat, np.nan_to_num(rank[v], nan=-1.0), eligible.shape) for v in ("A", "B")}
        catd = ndi.distance_transform_edt(~fold["visible"])
        forbidden = fold["region"] | fold["held_all"] | (catd <= 4)
        del catd
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
            # segments must never touch an evaluation pixel, a hidden component or a sampled label
            if len(idx):
                yy, xx = np.unravel_index(idx, eligible.shape)
                assert not fold["region"][yy, xx].any(), "pseudo-label reached the evaluation region"
                assert not fold["held_all"][yy, xx].any(), "pseudo-label reached a hidden component"
                assert not cat[yy, xx].any(), "pseudo-label reached a catalogue pixel"
            pseudo_pos[receiver] = idx
            rec["directions"][f"{donor}->{receiver}"] = dict(
                n_pixels=int(len(idx)), n_segments=len(receipts),
                segments=receipts[:40],
                mean_donor_rank=float(np.mean([r["mean_donor"] for r in receipts])) if receipts else None,
                mean_receiver_rank=float(np.mean([r["mean_receiver"] for r in receipts])) if receipts else None)
            log(f"fold {f} {donor}->{receiver}: {len(idx)} pseudo px in {len(receipts)} segments")
        ex["folds"].append(rec)
        # ---- refit each receiver with the donor's confident segments appended as positives
        rng = np.random.default_rng(SEED + 100 + f)
        rows, y = sample_train(fold, cat, rng)
        for view, names in (("A", va), ("B", vb)):
            # `pseudo_pos` holds GRID-flat indices, which is exactly what store.gather wants;
            # converting them to store rows first (the original bug) made gather raise
            # "requested row outside eligible feature footprint".
            extra = pseudo_pos.get(view, np.empty(0, np.int64))
            extra_rows = extra[inv[extra] >= 0] if len(extra) else np.empty(0, np.int64)
            r2 = np.concatenate([rows, extra_rows]) if len(extra_rows) else rows
            y2 = np.concatenate([y, np.ones(len(extra_rows), np.int8)]) if len(extra_rows) else y
            X = store.gather(r2, names)
            m = learner(SEED + 7)
            m.fit(X, y2)
            del X
            p = predict_flat(store, m, names, flat)
            np.save(WORK / f"pred_post_{view}_f{f}.npy", p)
            pos_idx = inv[np.flatnonzero((fold["truth"] & fold["region"]).ravel())]
            catd = ndi.distance_transform_edt(~cat)
            neg_idx = inv[np.flatnonzero((fold["region"] & ~cat & (catd > 5)).ravel())]
            del catd
            auc = float(roc_auc_score(np.r_[np.ones(len(pos_idx)), np.zeros(len(neg_idx))],
                                      np.r_[p[pos_idx], p[neg_idx]]))
            rec["directions"][f"refit_{view}"] = dict(
                n_pseudo_added=int(len(extra_rows)), n_train_total=int(len(r2)),
                heldout_region_auc=auc)
            log(f"fold {f} refit {view}: +{len(extra_rows)} pseudo, OOF-region-AUC {auc:.4f}")
    ex.update(finished_utc=now(),
              total_pseudo_pixels=int(sum(d.get("n_pixels", 0) for r in ex["folds"]
                                          for d in r["directions"].values())),
              rule="exactly one exchange; no second round; no post-result hyperparameter search")
    write("pseudo_exchange", ex)
    write("independence", dict(pre=pre, allow_exchange=allowed_exchange,
                               block_statistics="50x50 px blocks of held-out catalogue-zero proxies",
                               negative_class="held-out catalogue-zero proxies, not verified absence"))
    return ex


# --------------------------------------------------------------------------------------------
# stage: holdout
# --------------------------------------------------------------------------------------------
def stage_holdout():
    reg, store, cat, eligible, folds, va, vb, ring_px = setup()
    th = reg["thresholds"]
    flat, inv = store.flat_idx, store.inverse
    K = int(th["budget_dots_per_fold_per_arm"])
    min_px = float(th["min_dot_separation_px"])
    ex = json.loads((EVID / "h61_pseudo_exchange.json").read_text())
    if not ex.get("allowed_exchange", False):
        log("NOTE: the independence screen fired; post-exchange arms are refits without transfer")
    out = dict(stage="holdout", started_utc=now(), budget_per_arm_per_fold=K, min_separation_px=min_px,
               arms=list(ARMS), folds=[],
               exchange_pseudo_pixels=ex.get("total_pseudo_pixels"),
               exchange_allowed=ex.get("allowed_exchange"),
               independence_max_abs_rho=(ex.get("independence_pre") or {}).get("max_abs_correlation"),
               capacity_note=(
                   "every arm is placed by nodes.spacing_select on a field that is finite over the whole "
                   "allowed domain, so each arm fills exactly K dots; an arm that cannot fill K "
                   "invalidates the comparison and is reported, not rescued"))
    terms = {a: None for a in ARMS}
    for fold in folds:
        f = fold["fold"]
        # LABEL-BLIND emission domain: the 200 m exclusion ring is built from the fold's VISIBLE
        # catalogue only.  Using the hidden components' geometry here is exactly the defect that
        # invalidated CTD5's evaluation domain.
        vis_dist = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & ~fold["visible"] & (vis_dist > ring_px)
        del vis_dist
        g = {}
        for v in ("A", "B"):
            g[f"pre_{v}"] = to_grid(flat, np.load(WORK / f"pred_pre_{v}_f{f}.npy"), eligible.shape)
            g[f"post_{v}"] = to_grid(flat, np.load(WORK / f"pred_post_{v}_f{f}.npy"), eligible.shape)
        allowed_idx = np.flatnonzero(allowed.ravel())
        r_pre = {v: np.full(g[f"pre_{v}"].shape, np.nan, np.float32) for v in ("A", "B")}
        r_post = {v: np.full(g[f"post_{v}"].shape, np.nan, np.float32) for v in ("A", "B")}
        for v in ("A", "B"):
            r_pre[v].ravel()[allowed_idx] = pct_rank(g[f"pre_{v}"].ravel()[allowed_idx])
            r_post[v].ravel()[allowed_idx] = pct_rank(g[f"post_{v}"].ravel()[allowed_idx])
        rng = np.random.default_rng(SEED + 500 + f)
        rnd = np.zeros(eligible.shape, np.float32)
        rnd.ravel()[allowed_idx] = rng.random(len(allowed_idx), dtype=np.float32)
        fields = {
            "single_A": np.nan_to_num(r_pre["A"], nan=-1.0),
            "single_B": np.nan_to_num(r_pre["B"], nan=-1.0),
            "union_max": np.nan_to_num(np.maximum(r_pre["A"], r_pre["B"]), nan=-1.0),
            "disagreement_pre": np.nan_to_num(r_pre["A"] - r_pre["B"], nan=-1.0),
            "disagreement_post": np.nan_to_num(r_post["A"] - r_post["B"], nan=-1.0),
            "random": rnd,
        }
        rec = dict(fold=f, allowed_px=int(allowed.sum()), truth_px=int(fold["truth"].sum()),
                   region_px=int(fold["region"].sum()), arms={})
        em_by_arm = {}
        for arm, field in fields.items():
            t0 = time.time()
            em = nodes.spacing_select(field, allowed, K, min_px=min_px)
            em_by_arm[arm] = em
            n = int(em.sum())
            pred = em.astype(np.float32)
            result, term = evaluator.evaluate(pred, fold, eligible, block_side=200)
            # merge the same physical block across folds BEFORE resampling (evaluator contract)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            row = dict(result)          # result already carries `emitted` (post-mask count)
            row.update(placed=n, requested=K, filled=bool(n == K),
                       seconds=round(time.time() - t0, 1))
            rec["arms"][arm] = row
            log(f"fold {f} arm {arm}: emitted {n}/{K} DTI {result['dti']:.6f} tpw {result['tpw']:.1f}")
        dis_allowed = np.asarray(fields["disagreement_post"][allowed], dtype=np.float64)
        union_field = fields["union_max"]
        del g, r_pre, r_post, fields
        # not-the-union diagnostics on the shipped field, reusing the already-placed arms
        d_em = em_by_arm["disagreement_post"] > 0
        a_em, b_em, u_em = (em_by_arm["single_A"], em_by_arm["single_B"], em_by_arm["union_max"])
        for k in ("random", "disagreement_pre"):
            em_by_arm.pop(k, None)
        rec["not_the_union"] = dict(
            disagreement_cells_vs_A=int((d_em != a_em).sum()), disagreement_cells_vs_B=int((d_em != b_em).sum()),
            disagreement_cells_vs_union=int((d_em != u_em).sum()),
            disagreement_dots_also_in_A=int((d_em & a_em).sum()),
            disagreement_dots_also_in_B=int((d_em & b_em).sum()),
            spearman_disagreement_vs_unionmax=float(np.corrcoef(
                rankdata(dis_allowed), rankdata(union_field[allowed]))[0, 1]),
            note="a high-A/middle-B pixel and a high-A/high-B pixel have the same union score but "
                 "different disagreement scores, so the field is not a rescaling of max(A,B)")
        out["folds"].append(rec)
    out["pooled"] = evaluator.pooled_summary(terms, draws=int(th["bootstrap_draws"]), seed=SEED,
                                             candidate="disagreement_post")
    out.update(finished_utc=now(),
               withheld_positive_pixels=out["pooled"]["scores"]["disagreement_post"]["withheld_positive_pixels"],
               all_arms_filled=bool(all(a["arms"][arm]["filled"] for a in out["folds"] for arm in ARMS)),
               caveat="HOLDOUT-DTI on the corrected label-blind-quadrants-v2 splitter. This simulator "
                      "measured Spearman -0.10 against the owner-reported board in round R4, so it "
                      "screens procedures; it does not by itself promote anything.")
    write("holdout", out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["canary", "fit", "exchange", "holdout", "all"])
    args = ap.parse_args()
    stages = ["canary", "fit", "exchange", "holdout"] if args.stage == "all" else [args.stage]
    for s in stages:
        t0 = time.time()
        log(f"=== H61 stage {s} ===")
        {"canary": stage_canary, "fit": stage_fit,
         "exchange": stage_exchange, "holdout": stage_holdout}[s]()
        log(f"--- stage {s} done in {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
