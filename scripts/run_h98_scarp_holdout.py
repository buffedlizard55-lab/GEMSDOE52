#!/usr/bin/env python3
"""H98: validate the lane's second disagreement case on the shared hide-and-recover instrument.

Frozen in ``registry/h98_preregistration.json`` before this script was written to disk for a fit:
primary ``h98_bonly = B_rank * (1 - A_rank)`` (View B confident, View A abstains).  The arm was chosen
from H97's screening on the prevalence-matched off-catalogue instrument and is therefore validated
here on a DIFFERENT instrument (``gems52-pooled-hide-v1``), which is what keeps the check independent
of the selection.

The runner refuses to score anything unless ``scripts/check_h98_lane.py`` recorded
``decision = proceed-to-validation``: the parallel-run protocol says a candidate that reproduces
another lane's support must be logged as a duplicate and stopped, not validated.

Writes ``evidence/h98_holdout.json``.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import evaluate_holdout as evaluator, grid, h97, nodes, spatial  # noqa: E402

SEED = 89001
K_FOLD = 9400
BUFFER_PX = 80
CANARY_ALARM = 0.90
FEATURES = ROOT / "data/training_features.tif"
LABELS = ROOT / "data/labels.tif"
SAMPLE = ROOT / "data/sample_submission.tif"
PRECHECK = ROOT / "evidence/h98_lane_precheck.json"
OUT = ROOT / "evidence/h98_holdout.json"


def log(m):
    print(f"[h98 {time.strftime('%H:%M:%S')}] {m}", flush=True)


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main() -> int:
    t0 = time.time()
    if not PRECHECK.exists():
        raise SystemExit("run scripts/check_h98_lane.py first (lane gate before validation)")
    pre = json.loads(PRECHECK.read_text())
    if pre["decision"] != "proceed-to-validation":
        raise SystemExit(f"lane pre-check says {pre['decision']}; the protocol says stop, not validate")
    log(f"lane pre-check ok: policy {pre['lane']['policy']}, max_spearman {pre['lane']['max_spearman']}, "
        f"max_near3px {pre['lane']['max_near_3px_fraction']}")

    with rasterio.open(LABELS) as ds:
        labels = ds.read(1)
    with rasterio.open(SAMPLE) as ds:
        domain = np.isfinite(ds.read(1))
    valid = grid.footprint_from(FEATURES, "all") & domain
    cat = labels == 1
    a_rank = h97.view_a(str(FEATURES), valid)
    b_rank = h97.view_b(str(FEATURES), valid)
    field = (b_rank * (1.0 - a_rank)).astype(np.float32)

    folds = list(spatial.folds(cat, valid, buffer_px=BUFFER_PX))
    withheld = int(sum((f["truth"] & f["region"]).sum() for f in folds))
    log(f"folds {len(folds)}; withheld positive px {withheld:,}")
    arms = ("h98_bonly", "single_B", "random")
    terms = {a: None for a in arms}
    canary, per_fold = {a: [] for a in arms}, []
    for fold in folds:
        vd = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & valid & ~fold["visible"] & (vd > h97.RING_PX)
        rng = np.random.default_rng(SEED + fold["fold"])
        noise = np.full(valid.shape, -1.0, np.float32)
        flat = np.flatnonzero(allowed.ravel())
        noise.ravel()[flat] = rng.random(len(flat), dtype=np.float32)
        for arm, fl in (("h98_bonly", field), ("single_B", b_rank), ("random", noise)):
            em = nodes.spacing_select(fl, allowed, K_FOLD, min_px=3.0).astype(np.float32)
            res, term = evaluator.evaluate(em, fold, valid, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            truth_in = (fold["truth"] & fold["region"])[allowed]
            if truth_in.any() and (~truth_in).any():
                canary[arm].append(dict(fold=fold["fold"],
                                        auc=float(roc_auc_score(truth_in.astype(int), fl[allowed]))))
            log(f"fold {fold['fold']} {arm}: DTI {res['dti']:.6f} placed {int(em.sum()):,}")
            del em
        per_fold.append(dict(fold=fold["fold"], allowed_px=int(allowed.sum()),
                             withheld_positive_px=int((fold["truth"] & fold["region"]).sum())))
        del noise
    summary = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate="h98_bonly")
    canary_max = {a: max(x["auc"] for x in v) for a, v in canary.items()}
    paired = summary["paired_differences"]["random"]
    promote = bool(paired["ci95"][0] > 0 and pre["lane"]["policy"] == "PASS")
    out = dict(
        round="H98", stage="holdout", evidence_class="HOLDOUT-DTI",
        evaluator_version=evaluator.VERSION, primary="h98_bonly",
        hypothesis_document="knowledge/99_h98_hypotheses_preregistered.md",
        preregistration="registry/h98_preregistration.json",
        selection_basis="evidence/h97_channel_screen.json (prior belief; this instrument was not used to choose the arm)",
        budget_per_fold=K_FOLD, buffer_px=BUFFER_PX, withheld_positive_px=withheld,
        pooled=summary, per_fold=per_fold,
        canary=dict(alarm_threshold=CANARY_ALARM, max_auc=canary_max,
                    alarm={k: v > CANARY_ALARM for k, v in canary_max.items()}, per_fold=canary),
        lane_precheck=dict(policy=pre["lane"]["policy"], max_spearman=pre["lane"]["max_spearman"],
                           max_near_3px_fraction=pre["lane"]["max_near_3px_fraction"],
                           uniqueness=pre["uniqueness"]),
        promotion_rule="paired 95% CI lower bound of (h98_bonly - random) > 0 AND lane policy PASS",
        verdict="promote" if promote else "negative",
        inputs=dict(features_sha256=sha256(FEATURES), labels_sha256=sha256(LABELS)),
        implementation_hashes=evaluator.implementation_hashes(),
        elapsed_seconds=round(time.time() - t0, 1),
    )
    OUT.write_text(json.dumps(out, indent=2, default=float) + "\n")
    log("pooled: " + json.dumps({a: round(summary["scores"][a]["dti"], 6) for a in arms}))
    log("paired vs random: " + json.dumps([round(paired["delta"], 6),
                                           [round(x, 6) for x in paired["ci95"]]]))
    log(f"verdict {out['verdict']}; wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
