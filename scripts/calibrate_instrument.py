#!/usr/bin/env python3
"""Which local instrument actually tracks the leaderboard?  A 12-artifact calibration.

The brief's decision rule ("do not spend a slot on an idea that has not beaten the local holdout")
is only as good as the local holdout's rank correlation with the live board.  This script measures
that correlation, without fitting anything to the answer: it scores every stored artifact whose
owner-reported live score is recorded in ``docs/score-ledger.csv`` under four instruments and
reports Spearman's rho against the live scores.

Instruments compared
--------------------
``cat_hidden``       catalogue components withheld (20%), dots on the *visible* catalogue excluded
                     from both credit and penalty -- the repository's historical primary.
``cat_hidden_strict``the same geometry, but a dot sitting on the visible catalogue is scored as the
                     real competition scores it: it earns credit only within 300 m of a withheld
                     truth pixel and otherwise adds 0.2 of false-positive mass.
``sgmc_cal``         off-catalogue truth from the state geological map compilation, prevalence
                     calibrated to the estimated hidden-set size.
``drift``            the repository's 0.65/0.35 combination of the debiased catalogue term and the
                     calibrated SGMC term.

Outputs ``evidence/instrument_calibration.json``.

Usage:  PYTHONPATH=src python3 scripts/calibrate_instrument.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from gems52.holdout import evaluate_candidate_holdout, load_holdout_context, read_binary  # noqa: E402
from gems52.metric import ALPHA, BETA, EPS, kernel  # noqa: E402
from gems52.paths import data_dir, evidence_dir  # noqa: E402

# (file, owner-reported live score, provenance of the score)
SCORED = [
    ("scored/gemsdoe9-PLACEHOLDER-2314b599.tif", 0.0107, "GEMSDOE9 site"),
    ("scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif", 0.0904, "13GEMSDOE site"),
    ("scored/gems10-h25-ctx-ridge-20260927T232947704150Z-6452ae1d00.tif", 0.1280, "GEMSDOE10 site"),
    ("scored/8GEMSDOE_Hedge-v2_submission.tif", 0.1563, "8GEMSDOE site"),
    ("scored/gemsdoe-ens12-adopted-7f00890a.tif", 0.1563, "GEMSDOE/5GEMSDOE site"),
    ("scored/gems10-h28-dotted-ridge-20260928T020256236880Z-6452ae1d00.tif", 0.1839, "GEMSDOE10 site"),
    ("scored/gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif", 0.1855, "16GEMSDOE site"),
    ("scored/gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan.tif", 0.1894, "19/21GEMSDOE site"),
    ("scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif", 0.1922, "19GEMSDOE site"),
    ("scored/gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif", 0.2449, "27GEMSDOE site"),
    ("scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif", 0.2477, "24GEMSDOE site"),
    ("scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif", 0.2600, "25/29/30GEMSDOE site"),
]


def strict_catalogue_hidden(mask: np.ndarray, ctx) -> dict:
    """Catalogue-hidden DTI with *all* in-domain dots scored (no free mass on known faults).

    ``cell.active_sub`` is ``domain & ~visible`` and therefore excludes every visible catalogue
    pixel, so the historical instrument can never charge for a dot placed on a mapped fault.  The
    live scorer has no such exemption, so this variant rebuilds the eroded quadrant domain
    (``binary_erosion(quad == fold, 20)``, the same construction ``load_holdout_context`` uses) and
    scores every dot inside it.
    """
    from scipy.ndimage import binary_erosion
    domains = {f: binary_erosion(ctx.quad == f, iterations=20) for f in (0, 1, 2, 3)}
    vals, per_cell = [], {}
    for cell in ctx.cells:
        sl = cell.bbox
        p_sub = mask[sl] & domains[cell.fold][sl]
        n_emit, n_t = int(p_sub.sum()), cell.n_truth
        if n_t == 0 or n_emit == 0:
            vals.append(0.0)
            per_cell[cell.key] = 0.0
            continue
        dp = distance_transform_edt(~p_sub)
        tp = float(kernel(dp[cell.truth_coords]).sum())
        fn = float(n_t) - tp
        fp = float((1.0 - cell.k_dg_sub[p_sub]).sum())
        d = float(tp / (tp + ALPHA * fp + BETA * fn + EPS))
        vals.append(d)
        per_cell[cell.key] = d
    return {"mean": float(np.mean(vals)),
            "per_draw": {f"draw{ds}": float(np.mean([v for k, v in per_cell.items() if k.startswith(f"draw{ds}")]))
                         for ds in (20, 21)},
            "per_quadrant": {q: float(np.mean([v for k, v in per_cell.items() if k.endswith(q)]))
                             for q in ("NW", "NE", "SW", "SE")}}


def spearman(a: list[float], b: list[float]) -> float:
    from scipy.stats import spearmanr
    return float(spearmanr(a, b).statistic)


def pearson(a, b) -> float:
    from scipy.stats import pearsonr
    return float(pearsonr(a, b)[0])


def main() -> int:
    ddir = data_dir()
    ctx = load_holdout_context(ddir)
    rows = []
    for rel, live, src in SCORED:
        p = ddir / rel
        if not p.exists():
            print(f"  MISSING {rel}")
            continue
        m = read_binary(p)
        ev = evaluate_candidate_holdout(m, ctx, Path(rel).stem)
        st = strict_catalogue_hidden(m, ctx)
        rows.append({
            "artifact": Path(rel).name, "live_owner_report": live, "live_source": src,
            "emitted_pixels": ev["emitted_pixels"], "on_catalogue_pixels": ev["on_catalogue_pixels"],
            "cat_hidden": ev["catalogue_hidden_mean"],
            "cat_hidden_debiased": ev["debiased_catalogue_hidden_mean"],
            "cat_hidden_strict": st["mean"],
            "sgmc_cal": ev["sgmc_prevalence_calibrated_dti"],
            "drift": ev["drift_corrected_holdout_mean"],
            "per_draw_cat": ev["catalogue_hidden_per_draw"],
            "per_draw_strict": st["per_draw"],
        })
        print(f"  {Path(rel).name[:52]:52s} live={live:.4f} cat={ev['catalogue_hidden_mean']:.5f} "
              f"strict={st['mean']:.5f} sgmc={ev['sgmc_prevalence_calibrated_dti']:.5f} "
              f"drift={ev['drift_corrected_holdout_mean']:.5f}")

    live = [r["live_owner_report"] for r in rows]
    out = {"n_artifacts": len(rows), "rows": rows, "spearman_vs_live": {}, "pearson_vs_live": {}}
    for key in ("cat_hidden", "cat_hidden_debiased", "cat_hidden_strict", "sgmc_cal", "drift"):
        v = [r[key] for r in rows]
        out["spearman_vs_live"][key] = round(spearman(v, live), 4)
        out["pearson_vs_live"][key] = round(pearson(v, live), 4)
        print(f"  rho(live, {key:20s}) = {out['spearman_vs_live'][key]:+.4f}   r = {out['pearson_vs_live'][key]:+.4f}")

    # leave-one-out linear calibration of the best two instruments
    out["loo"] = {}
    for key in ("cat_hidden", "cat_hidden_strict", "drift"):
        x = np.array([r[key] for r in rows])
        y = np.array(live)
        errs = []
        for i in range(len(x)):
            keep = np.arange(len(x)) != i
            a, b = np.polyfit(x[keep], y[keep], 1)
            errs.append(abs(a * x[i] + b - y[i]))
        out["loo"][key] = {"mae": round(float(np.mean(errs)), 4), "max_abs_err": round(float(np.max(errs)), 4)}
        print(f"  LOO MAE  {key:20s} = {out['loo'][key]['mae']}  (max {out['loo'][key]['max_abs_err']})")

    p = evidence_dir() / "instrument_calibration.json"
    p.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
