#!/usr/bin/env python3
"""H34: positional-error-calibrated emission (the emission-side lever), measured on the holdout.

Theory (derived in ``docs/research/h34-positional-error-emission.md``)
--------------------------------------------------------------------
With ``p(x)`` the emitted mass and ``k`` the official triangular kernel (R = 3 px),

    DTI = T / (alpha * S + beta * K),   T = sum_x P(x) C_M(x),   S = sum_x p(x),

where ``P(x)`` is the *probability that a truth pixel sits at x* and ``C_M(x) = max_{m in M} k(|x-m|)``
is the credit the dot set ``M`` delivers to a truth pixel at ``x``.  Two consequences matter:

1. emission is a **maximum-expected-coverage** problem in ``P`` (the repository's ``emitter``);
2. ``P`` must be the probability of the truth *location*, not a belief about where the trace is
   drawn.  A binary ridge field asserts "the truth is exactly on this ridge, with probability 1",
   which is false: the median distance from a withheld catalogue component to the incumbent ridge is
   measured here in pixels.  Convolving the belief with the *measured* localisation error,
   ``P_tilde = P * G(sigma_e)``, is the calibrated version of the same rule, and it is the reason
   the group's 2.4 px raster thinning beat a max-coverage sweep on the *sharp* field.

This script measures the localisation error of each belief field against the *withheld* holdout
components, then sweeps ``sigma`` and the budget through the unchanged exact-greedy emitter and
reports the holdout instruments for every cell -- submitted or not.

Usage
-----
    PYTHONPATH=src python3 scripts/run_h34.py --sigmas 0,0.75,1.25,1.75,2.25,3.0 --budget 44090
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt, gaussian_filter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from gems52.bo import Observation, append_observation                       # noqa: E402
from gems52.emitter import emit                                              # noqa: E402
from gems52.holdout import evaluate_candidate_holdout, load_holdout_context, read_binary  # noqa: E402
from gems52.paths import data_dir, docs_dir, evidence_dir, work_dir          # noqa: E402

FIELDS = {
    "H19-5-binary": "scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif",
    "CV-heatfield": "gems52-heatfield-44090-cv-supconfined-zeros.tif",
}


def localisation_error(mask: np.ndarray, ctx) -> dict:
    """Distribution of distances from withheld truth pixels to the nearest ``mask`` pixel.

    The withheld truth is the holdout's own hidden catalogue components (bbox-local coordinates in
    ``ctx.cells``); the distance is measured against the *full-grid* mask, which is the correct
    comparison because emission is allowed anywhere in the footprint.
    """
    d = distance_transform_edt(~mask)
    vals, per_cell = [], {}
    for cell in ctx.cells:
        if cell.n_truth == 0:
            continue
        sl, (ty, tx) = cell.bbox, cell.truth_coords
        sub = d[sl][ty, tx]
        vals.append(sub)
        per_cell[cell.key] = {"n": int(sub.size), "median_px": float(np.median(sub)),
                              "mean_px": float(np.mean(sub)), "p10": float(np.percentile(sub, 10)),
                              "p90": float(np.percentile(sub, 90))}
    v = np.concatenate(vals) if vals else np.array([np.nan])
    within = {str(r): float((v <= r).mean()) for r in (0.0, 1.0, 2.0, 3.0)}
    return {
        "n_withheld_truth_px": int(v.size),
        "median_px": float(np.median(v)), "mean_px": float(np.mean(v)),
        "p10_px": float(np.percentile(v, 10)), "p90_px": float(np.percentile(v, 90)),
        "fraction_within_px": within,
        "implied_sigma_e_px": float(np.sqrt(np.mean(v ** 2))),
        "per_cell": per_cell,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sigmas", default="0,0.75,1.25,1.75,2.25,3.0")
    ap.add_argument("--budget", type=int, default=44090)
    ap.add_argument("--budget-sweep", default="")
    ap.add_argument("--prior-dti", type=float, default=0.26)
    ap.add_argument("--out", default=str(ROOT / "evidence" / "h34_positional_error.json"))
    ap.add_argument("--no-log", action="store_true")
    args = ap.parse_args()

    ddir, dl = data_dir(), docs_dir() / "downloads"
    sigmas = [float(s) for s in args.sigmas.split(",") if s]
    t0 = time.time()
    print(f"[1/4] holdout context (data_dir={ddir})", flush=True)
    ctx = load_holdout_context(ddir)
    foot = ctx.foot

    fields: dict[str, np.ndarray] = {}
    for name, rel in FIELDS.items():
        p = ddir / rel
        if not p.exists():
            p = dl / Path(rel).name
        if not p.exists():
            print(f"   skip {name}: {p} missing", flush=True)
            continue
        m = read_binary(p)
        fields[name] = m.astype(np.float64)

    print("[2/4] measured localisation error of each belief field vs withheld truth", flush=True)
    out: dict = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "prior_dti": args.prior_dti,
        "localisation_error": {},
        "sweep": {},
    }
    for name, m in fields.items():
        res = localisation_error(m > 0, ctx)
        out["localisation_error"][name] = res
        print(f"   {name:14s} median={res['median_px']:.3f} px  mean={res['mean_px']:.3f}  "
              f"rms={res['implied_sigma_e_px']:.3f}  within3px={res['fraction_within_px']['3.0']:.3f}",
              flush=True)

    print(f"[3/4] sigma x field sweep at budget {args.budget} (exact greedy emitter, unchanged)", flush=True)
    for name, m in fields.items():
        out["sweep"][name] = {}
        for s in sigmas:
            f = m if s == 0 else gaussian_filter(m, s, mode="nearest")
            t = time.time()
            mask, log = emit(f, budget=args.budget, prior_dti=args.prior_dti)
            ev = evaluate_candidate_holdout(mask, ctx, f"{name}_sigma{s}")
            out["sweep"][name][str(s)] = {
                "emitted_pixels": int(mask.sum()), "off_support": int(log.off_support_px),
                "stopped_by": log.stopped_by,
                "first_marginal_gain": float(log.first_marginal_gain),
                "last_marginal_gain": float(log.last_marginal_gain),
                "catalogue_hidden_mean": float(ev["catalogue_hidden_mean"]),
                "sgmc_prevalence_calibrated_dti": float(ev["sgmc_prevalence_calibrated_dti"]),
                "drift_corrected_holdout_mean": float(ev["drift_corrected_holdout_mean"]),
                "drift_corrected_holdout_std": float(ev["drift_corrected_holdout_std"]),
                "per_draw": {k: float(v) for k, v in ev["catalogue_hidden_per_draw"].items()},
                "per_quadrant_cat": {k: float(v) for k, v in ev["catalogue_hidden_per_quadrant"].items()},
                "on_catalogue_pixels": int(ev["on_catalogue_pixels"]),
                "emit_s": round(time.time() - t, 1),
            }
            print(f"   {name:14s} sigma={s:<5} px={mask.sum():6d} cat={ev['catalogue_hidden_mean']:.5f} "
                  f"sgmc={ev['sgmc_prevalence_calibrated_dti']:.5f} drift={ev['drift_corrected_holdout_mean']:.5f}"
                  f"  ({round(time.time() - t, 1)}s)", flush=True)

    if args.budget_sweep:
        budgets = [int(b) for b in args.budget_sweep.split(",")]
        best = None
        for name, h in out["sweep"].items():
            s = max(h, key=lambda k: h[k]["drift_corrected_holdout_mean"])
            if best is None or h[s]["drift_corrected_holdout_mean"] > best[2]:
                best = (name, float(s), h[s]["drift_corrected_holdout_mean"])
        assert best is not None
        name, sigma, _ = best
        print(f"[3b] budget sweep on {name} at sigma={sigma}: {budgets}", flush=True)
        out["budget_sweep"] = {"field": name, "sigma": sigma, "cells": {}}
        for b in budgets:
            f = fields[name] if sigma == 0 else gaussian_filter(fields[name], sigma, mode="nearest")
            t = time.time()
            mask, log = emit(f, budget=b, prior_dti=args.prior_dti)
            ev = evaluate_candidate_holdout(mask, ctx, f"{name}_sigma{sigma}_{b}")
            out["budget_sweep"]["cells"][str(b)] = {
                "emitted_pixels": int(mask.sum()), "stopped_by": log.stopped_by,
                "last_marginal_gain": float(log.last_marginal_gain),
                "catalogue_hidden_mean": float(ev["catalogue_hidden_mean"]),
                "sgmc_prevalence_calibrated_dti": float(ev["sgmc_prevalence_calibrated_dti"]),
                "drift_corrected_holdout_mean": float(ev["drift_corrected_holdout_mean"]),
                "per_draw": {k: float(v) for k, v in ev["catalogue_hidden_per_draw"].items()},
            }
            print(f"   {name} sigma={sigma} budget={b:6d} cat={ev['catalogue_hidden_mean']:.5f} "
                  f"drift={ev['drift_corrected_holdout_mean']:.5f} ({round(time.time() - t, 1)}s)", flush=True)

    out["elapsed_s"] = round(time.time() - t0, 1)
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[4/4] wrote {args.out} in {out['elapsed_s']}s", flush=True)

    if not args.no_log:
        for name, h in out["sweep"].items():
            for s, cell in h.items():
                append_observation(Observation(
                    kind="holdout", name=f"H34:{name}@sigma{s}", design_id=f"H34-{name}-s{s}",
                    score=float(cell["drift_corrected_holdout_mean"]),
                    n_px=float(cell["emitted_pixels"]), source="run_h34",
                    note="H34 positional-error-calibrated emission sweep",
                    meta={"sigma": float(s), "catalogue_hidden_mean": cell["catalogue_hidden_mean"],
                          "sgmc": cell["sgmc_prevalence_calibrated_dti"],
                          "instrument": "GEMSDOE32-H33"}))
        for b, cell in out.get("budget_sweep", {}).get("cells", {}).items():
            append_observation(Observation(
                kind="holdout", name=f"H34:budget{b}", design_id=f"H34-budget-{b}",
                score=float(cell["drift_corrected_holdout_mean"]), n_px=float(cell["emitted_pixels"]),
                source="run_h34", note="H34 budget sweep at the swept-best sigma",
                meta={"budget": int(b), "catalogue_hidden_mean": cell["catalogue_hidden_mean"],
                      "instrument": "GEMSDOE32-H33"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
