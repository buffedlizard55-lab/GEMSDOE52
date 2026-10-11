#!/usr/bin/env python3
"""H87 uniform-truth control, as its own stage.

The board-inversion script originally ran this control at the end of a process that was already holding
sixteen bases and thirteen cover fields, and the 3.9 GB sandbox killed it. Splitting it out costs a
reload of two arrays and nothing else.

The control asks the one question that can be checked against an owner-reported number: if the hidden
truth were spatially UNIFORM at the fitted total mass, what spacing would the metric's marginal rule
self-terminate at, and what DTI would it report there? The organiser-side raster
``data/scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif`` is exactly that regime -- a near
uniform lattice, 206,895 dots, nearest-neighbour median 5.00 px, 99.85% of the footprint within 300 m of
a dot, mean cover 0.3748 -- and its owner-reported public score is 0.0904. If the control lands near
0.0904 the placement model is calibrated where it can be checked.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import nodes as shared_nodes          # noqa: E402

WORK = ROOT / "work" / "h87"
EVID = ROOT / "evidence"


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def main() -> int:
    allowed_ring = np.load(WORK / "allowed_ring.npy")
    lab = np.load(WORK / "catalogue.npy")
    out = json.loads((EVID / "h87_board_inversion.json").read_text())
    fit = out["fits"]["primary8"]
    files = out["files"]
    pinned = "calib_13gems_20261001_r13-lattice-s5_v2_nan-ou"
    G_fit = float(fit["G_fit"])
    sane = 5_000.0 <= G_fit <= 40_000.0
    G_ref = G_fit if sane else 12367.0
    ys, xs = np.nonzero(lab)
    cy, cx = int(ys.mean()), int(xs.mean())
    y0, y1 = max(0, cy - 500), min(lab.shape[0], cy + 500)
    x0, x1 = max(0, cx - 500), min(lab.shape[1], cx + 500)
    aw = allowed_ring[y0:y1, x0:x1]
    rho = G_ref / float(allowed_ring.sum())
    Uw = np.where(aw, rho, 0.0)
    log(f"uniform rho={rho:.10f} on rows {y0}:{y1} cols {x0}:{x1}, {int(aw.sum())} allowed px, "
        f"mass {Uw.sum():.1f}")
    gu = shared_nodes.marginal_greedy(Uw, aw, max_dots=400_000, min_sep_px=3.0, round_cap=20_000,
                                      log=lambda *a: log(*a))
    C = shared_nodes.cover_of(gu["dots"])
    win = dict(rows=[y0, y1], cols=[x0, x1], allowed_px=int(aw.sum()), rho_per_px=round(rho, 12),
               mass=round(float(Uw.sum()), 1),
               equivalent_spacing_px=round(float(np.sqrt(aw.sum() / max(gu["n_added"], 1))), 3),
               mean_cover=round(float(C.mean()), 4),
               cover_fraction=round(float((C > 0).mean()), 4))
    out["uniform_control"] = dict(
        basis="uniform density of the fitted total mass over allowed_ring", window=win,
        G=round(gu["G"], 1), G_source=("primary8 fit" if sane else "pinned lattice estimate"),
        dots=gu["n_added"], T=round(gu["T"], 2), predicted_dti=round(gu["predicted_dti"], 5),
        stop_reason=gu["stop_reason"], rounds=gu["rounds"],
        separation_schedule_px=gu["separation_schedule_px"],
        evidence_class="PREDICTED-BOARD (model projection, never a score)",
        pinned_reference=dict(raster=f"data/scored/{pinned}.tif" if False else
                              "data/scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif",
                              S=files[pinned]["S_inside"], owner_reported_score=0.0904,
                              cover_frac=files[pinned]["cover_frac"],
                              M_mean=files[pinned]["M_mean_fp"], nn_median_px=5.0),
        relative_error_vs_pinned=round(
            abs(gu["predicted_dti"] - 0.0904) / 0.0904, 4),
        reading="if the predicted uniform-truth DTI lands near the pinned lattice's owner-reported "
                "0.0904 the placement model is calibrated in the one regime an owner score pins")
    (EVID / "h87_board_inversion.json").write_text(
        json.dumps(out, indent=1, allow_nan=False) + "\n")
    log(f"control: {gu['n_added']} dots, spacing {win['equivalent_spacing_px']} px, mean cover "
        f"{win['mean_cover']}, predicted DTI {gu['predicted_dti']:.4f} vs pinned 0.0904 "
        f"(relative error {out['uniform_control']['relative_error_vs_pinned']:.1%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
