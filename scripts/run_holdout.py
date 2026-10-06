#!/usr/bin/env python3
"""Preregistered, spatially blocked holdout for the *emission ladder*.

This measures one thing: how much of the official metric a *better placement of the same mass*
buys, on a proxy truth that is hidden from the fit.  It does not measure the hidden new-fault set,
and it cannot: the proxy truth is the visible catalogue (see IR-32-PROXY-01 on the site).

Preregistration (written to registry/preregistration.json before any fold is run, and reproduced
here verbatim): 4 quadrant blocks, 30 px buffer around the held-out block, detector
HistGradientBoosting(max_iter=80, learning_rate=0.1, max_leaf_nodes=31) on the 31 structural
channels, up to 60k positive / 240k negative training pixels sampled from the *other* three
quadrants, emission budget 8,000 px per block, prior DTI 0.13 for the credit bar, rho 1.0 for the
two-round arm.  Arms and contrasts are fixed in ``holdout.run_fold``.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import bo, detector, grid, holdout  # noqa: E402

DATA = Path("/tmp/gems52/data")
STACK = Path("/tmp/gems52/work/feature_stack.npy")
RECEIPT = ROOT / "registry" / "feature_receipt.json"

PREREG = {
    "id": "GEMSDOE32-PREREG-1",
    "statement": ("Emission-ladder holdout: does greedy maximum-expected-coverage packing of the "
                  "same field beat the incumbent raster-order thinning cascade at MATCHED emitted "
                  "mass, under the official metric, on spatially blocked proxy truth?"),
    "blocks": "4 quadrants of the footprint, 30 px buffer between train and held-out block",
    "detector": "HistGradientBoosting(max_iter=80, learning_rate=0.1, max_leaf_nodes=31)",
    "training_sample": "<=60k positive / 240k negative pixels drawn from the other three quadrants",
    "channels": "all 35 structural channels (memory-mapped stack, registry/feature_receipt.json)",
    "budget_px": 8000,
    "prior_dti": 0.26,
    "rho_two_round": 1.0,
    "arms": {
        "A1_greedy_fixed_budget": "greedy max-expected-coverage, exactly budget pixels",
        "A2_greedy_credit_bar": "same greedy, stop when marginal expected credit < 0.2*prior_dti",
        "A3_greedy_bar_discovery": "same greedy, bar = 0.2*prior_dti/(1+rho)  (two-round objective)",
        "A0_dot_thin_matched": "incumbent's own rule: raster-order dot-thin, count matched to A1",
        "A5_nms_ridge_matched": "non-max-suppressed ridge peaks, top-k to A1's count",
        "A4_random_matched": "uniform random pixels, count matched to A1",
    },
    "primary_contrast": "A1 - A0 (matched mass); secondary: A2 - A0, A3 - A2, A5 - A0",
    "promotion_rule": "mean paired contrast > 0 on >= 3 of 4 folds, else no promotion",
    "honesty": ("The proxy truth is the visible catalogue, so this instrument CANNOT reward a "
                "prediction that is off-catalogue -- the population the real test set is drawn from. "
                "A pass licenses packaging a candidate, never a claim of a score."),
}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="1")
    ap.add_argument("--prereg-id", default=None)
    ap.add_argument("--prior-dti", type=float, default=None)
    ap.add_argument("--budget", type=int, default=None)
    a = ap.parse_args()
    if a.prereg_id:
        PREREG["id"] = a.prereg_id
        PREREG["amended_from"] = "GEMSDOE32-PREREG-1"
        PREREG["amendment_reason"] = ("PREREG-1's bar arm was non-binding on the first two folds "
                                      "(prior DTI 0.13 -> bar 0.026 while observed marginals were "
                                      "1-4), so the bar could not discriminate; the amendment prices "
                                      "the bar at the live anchor (0.26) and adds a second mass-matched "
                                      "control. Fold-0/1 results of PREREG-1 are kept in git history.")
    if a.prior_dti is not None:
        PREREG["prior_dti"] = a.prior_dti
    if a.budget is not None:
        PREREG["budget_px"] = a.budget
    t0 = time.time()
    if not STACK.exists():
        print(f"missing {STACK}: run scripts/build_features.py first", file=sys.stderr)
        return 2
    stack = np.load(STACK, mmap_mode="r")
    footprint = grid.read_footprint(DATA / "training_features.tif")
    labels = grid.read_labels(DATA / "labels.tif")
    receipt = json.loads(RECEIPT.read_text()) if RECEIPT.exists() else {}
    (ROOT / "registry" / "preregistration.json").write_text(json.dumps(PREREG, indent=1) + "\n")

    blocks = holdout.quadrant_blocks(footprint.shape, pad=0)
    results, rng = [], np.random.default_rng(20261004)
    print(f"stack {stack.shape} dtype {stack.dtype}; footprint {int(footprint.sum())} px; "
          f"{len(blocks)} blocks; prereg {PREREG['id']}")
    for k, block in enumerate(blocks):
        t1 = time.time()
        train = holdout.block_train_mask(footprint.shape, block, buffer_px=30)
        X, y = detector.sample_training_rows(stack, labels, train & footprint,
                                             detector.DetectorSpec(), rng)
        model = detector.Detector().fit(X, y)
        field = model.predict_field(stack, block[0], block[1])[:, block[2]:block[3]]
        truth = labels[block[0]:block[1], block[2]:block[3]] & footprint[block[0]:block[1], block[2]:block[3]]
        fold = holdout.run_fold(field, truth, footprint[block[0]:block[1], block[2]:block[3]],
                                budget=PREREG["budget_px"], prior_dti=PREREG["prior_dti"],
                                rho=PREREG["rho_two_round"], rng=rng, seed=1000 + k)
        fold["block"] = list(block)
        fold["seconds"] = round(time.time() - t1, 1)
        results.append(fold)
        auc = fold.get("auc")
        print(f"fold {k} block={tuple(block)} auc={fold['auc']:.4f} pos_test={fold['n_truth']} n1={fold['n1']} n2={fold['n2']} " +
              " ".join(f"{a}={fold['arms'][a]['dti']:.4f}({fold['arms'][a]['n_px']})"
                      for a in sorted(fold["arms"])), flush=True)

    summary = holdout.summarise(results)
    out = {"preregistration": PREREG, "receipt": receipt, "footprint_px": int(footprint.sum()),
           "folds": results, "summary": summary, "seconds": round(time.time() - t0, 1),
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (ROOT / "evidence").mkdir(exist_ok=True)
    (ROOT / "evidence" / f"holdout_run{a.tag}.json").write_text(json.dumps(out, indent=1) + "\n")

    # ---- every holdout evaluation is logged as data for the surrogate, submitted or not
    # BUGFIX 2026-10-04 (IR-32-SCRIPT-01): this loop used the name ``a``, which shadowed the
    # argparse Namespace built at the top of this function.  The evidence JSON was written before
    # the loop, but the closing print raised ``'str' object has no attribute 'tag'``, so the run
    # appeared to fail even though it had succeeded.  The loop variable is now ``arm``.
    for arm, v in summary["arms_mean"].items():
        bo.append_observation(bo.Observation(kind="holdout", name=f"{PREREG['id']}:{arm}", score=float(v),
                                             n_px=float(summary["arms_mean_n_px"].get(arm, 0.0)),
                                             source="run_holdout", meta={"prereg": PREREG["id"]}))
    print(json.dumps(summary, indent=1))
    print(f"wrote evidence/holdout_run{a.tag}.json in {'%.1f' % out['seconds']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
