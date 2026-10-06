#!/usr/bin/env python3
"""H33 programme: measure five untried geological hypotheses on the spatially-blocked holdout.

Additive by design: it never touches the H32 pipeline.  It

  1. loads the preregistered, spatially-blocked 4-quadrant holdout context (``gems52.holdout``);
  2. scores the incumbent artifacts on the same instrument in the same run (contemporaneous control);
  3. computes the H33-A..D *label-free* physical surfaces (``gems52.h33``);
  4. measures each surface alone and their equal-weight union, at matched emitted mass, with a
     uniform-random control;
  5. writes ``evidence/h33_holdout.json`` and appends every evaluation -- promoted or not -- to
     ``registry/observations.jsonl`` for the GP surrogate.

Usage
-----
    PYTHONPATH=src python3 scripts/run_h33.py [--budgets 44090,46090]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from gems52.bo import Observation, append_observation                     # noqa: E402
from gems52.h33 import H33_BUILDERS, H33_SPECS, rank_surface, top_n_mask  # noqa: E402
from gems52.holdout import evaluate_candidate_holdout, load_holdout_context, read_binary  # noqa: E402
from gems52.paths import data_dir, docs_dir, evidence_dir, work_dir       # noqa: E402

CONTROLS = {
    "D2.8-Poisson300m-Ref": "scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif",
    "H32-D-Submodular": "gemsdoe32-h32d-submodular-multipysics-46090-20261004T183200Z-4de30601-zeros.tif",
}
SCALARS = ("catalogue_hidden_mean", "sgmc_prevalence_calibrated_dti",
           "drift_corrected_holdout_mean", "drift_corrected_holdout_std",
           "on_catalogue_pixels", "emitted_pixels", "debiased_catalogue_hidden_mean")


def slim(ev: dict) -> dict:
    d = {k: ev[k] for k in SCALARS if k in ev}
    d["per_draw"] = {k: round(float(v), 6) for k, v in ev["catalogue_hidden_per_draw"].items()}
    d["per_quadrant_cat"] = {k: round(float(v), 6) for k, v in ev["catalogue_hidden_per_quadrant"].items()}
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "evidence" / "h33_holdout.json"))
    ap.add_argument("--budgets", default="44090,46090")
    ap.add_argument("--seed", type=int, default=32)
    ap.add_argument("--no-log", action="store_true", help="do not append to registry/observations.jsonl")
    args = ap.parse_args()
    budgets = [int(b) for b in args.budgets.split(",")]
    t0 = time.time()

    ddir, dl = data_dir(), docs_dir() / "downloads"
    print(f"[1/5] holdout context (data_dir={ddir})", flush=True)
    ctx = load_holdout_context(ddir)

    print("[2/5] controls on the same instrument", flush=True)
    out: dict = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "instrument": ("gems52.holdout: 4 quadrants x draws 20/21, 20% of catalogue components "
                       "hidden, 30 px collar, 20 px domain erosion; catalogue-hidden truth, SGMC "
                       "off-catalogue truth with prevalence calibration"),
        "controls": {}, "hypotheses": {}, "budgets": budgets,
        "surface_specs": H33_SPECS,
    }
    for name, rel in CONTROLS.items():
        p = ddir / rel
        if not p.exists():
            p = dl / Path(rel).name
        ev = evaluate_candidate_holdout(read_binary(p), ctx, name)
        out["controls"][name] = slim(ev)
        print(f"   {name:22s} cat={ev['catalogue_hidden_mean']:.5f} drift={ev['drift_corrected_holdout_mean']:.5f}", flush=True)

    print("[3/5] computing H33 surfaces (label-free)", flush=True)
    foot, bands_dir = ctx.foot, work_dir() / "bands"
    surfaces: dict[str, np.ndarray] = {}
    for hid, builder in H33_BUILDERS.items():
        t = time.time()
        surfaces[hid] = builder(bands_dir, ddir, foot)
        print(f"   {hid:6s} {time.time() - t:5.1f}s  p50={float(np.median(surfaces[hid][foot])):.4f} "
              f"p99={float(np.percentile(surfaces[hid][foot], 99)):.4f}", flush=True)
    ranks = {k: rank_surface(v, foot) for k, v in surfaces.items()}
    union = np.mean(list(ranks.values()), axis=0).astype(np.float32)
    union[~foot] = 0.0
    out["surfaces"] = {k: {"mean": float(v[foot].mean()), "p99": float(np.percentile(v[foot], 99))}
                       for k, v in surfaces.items()}
    out["surfaces"]["H33-U"] = {"mean": float(union[foot].mean()),
                                "p99": float(np.percentile(union[foot], 99)),
                                "spec": {"name": "equal-weight rank union of H33-A..D (no tuned weight)"}}

    print("[4/5] matched-budget evaluation", flush=True)
    rng = np.random.default_rng(args.seed)
    for hid, surf in list(surfaces.items()) + [("H33-U", union)]:
        out["hypotheses"][hid] = {"budgets": {}}
        for b in budgets:
            ev = evaluate_candidate_holdout(top_n_mask(surf, foot, b), ctx, f"{hid}_{b}")
            out["hypotheses"][hid]["budgets"][str(b)] = slim(ev)
            print(f"   {hid:6s} @{b:6d} cat={ev['catalogue_hidden_mean']:.5f} "
                  f"sgmc={ev['sgmc_prevalence_calibrated_dti']:.5f} "
                  f"drift={ev['drift_corrected_holdout_mean']:.5f}", flush=True)

    rand = {}
    for b in budgets:
        vals = []
        for k in range(3):
            rr = np.zeros_like(foot)
            rr.ravel()[rng.choice(foot.sum(), size=b, replace=False)] = True
            vals.append(evaluate_candidate_holdout(rr, ctx, f"rand_{b}_{k}")["catalogue_hidden_mean"])
        rand[str(b)] = {"mean_catalogue_hidden": float(np.mean(vals)), "samples": [float(v) for v in vals]}
    out["uniform_random_catalogue_hidden_control"] = rand
    out["elapsed_s"] = round(time.time() - t0, 1)
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[5/5] wrote {args.out} in {out['elapsed_s']}s  (random={rand})", flush=True)

    if not args.no_log:
        for hid, h in out["hypotheses"].items():
            for b, ev in h["budgets"].items():
                append_observation(Observation(
                    kind="holdout", name=f"H33:{hid}@{b}", design_id=f"H33-{hid}-{b}",
                    score=float(ev["drift_corrected_holdout_mean"]),
                    n_px=float(ev["emitted_pixels"]), source="run_h33",
                    note="H33 hypothesis; drift-corrected holdout mean; instrument GEMSDOE32-H33",
                    meta={"catalogue_hidden_mean": ev["catalogue_hidden_mean"],
                          "sgmc_prevalence_calibrated_dti": ev["sgmc_prevalence_calibrated_dti"],
                          "per_draw": ev["per_draw"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
