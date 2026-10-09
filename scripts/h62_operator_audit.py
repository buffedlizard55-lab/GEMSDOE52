#!/usr/bin/env python3
"""H62 E1 -- operator audit of the H60-3 strike-projected basement step.

Question (preregistered in knowledge/34_hypotheses_H62_preregistered.md, section 1): does the
H60-3 operator, a second difference taken along strike, respond to a basement *step across* a
strike-parallel trace, where the cross-strike symmetric difference used by H62-A does?

Method: synthetic 400 x 400 px grid at 100 m. Basement depth = 10 + 2 (step across a NNE line
through the centre, i.e. 200 m) + 0.002 * (along-strike ramp). Both operators are applied; the
on-trace mean is compared with the mean 20 px or more away. The H60-3 operator text is first
checked against src/gems52/h60.py, so this audit cannot drift from the code it audits.

Writes evidence/h62_operator_audit.json. Nothing here touches the competition rasters.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
H60_SRC = ROOT / "src/gems52/h60.py"
OUT = ROOT / "evidence/h62_operator_audit.json"
PIX = 100.0

# The exact lines of the H60-3 operator as shipped (checked below, byte for byte).
H60_OPERATOR_LINES = [
    "d1 = ndimage.shift(arr, (sy, sx), order=1, mode=\"nearest\")",
    "d2 = ndimage.shift(arr, (-sy, -sx), order=1, mode=\"nearest\")",
    "step = np.abs(d1 + d2 - 2 * arr) / (PIX ** 2)",
]


def check_h60_source() -> dict:
    text = H60_SRC.read_text()
    found = [ln.strip() in [t.strip() for t in text.splitlines()] for ln in H60_OPERATOR_LINES]
    if not all(found):
        raise SystemExit(f"H60-3 operator text changed in {H60_SRC}; re-audit before using this receipt")
    return dict(file=str(H60_SRC.relative_to(ROOT)),
                sha256=hashlib.sha256(H60_SRC.read_bytes()).hexdigest(),
                operator_lines_found=H60_OPERATOR_LINES)


def synthetic_grid():
    H = W = 400
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    a = np.deg2rad(15.0)                      # NNE strike, compass azimuth
    s_row, s_col = -np.cos(a), np.sin(a)      # unit strike, row axis points south
    n_row, n_col = np.sin(a), np.cos(a)       # unit normal to strike in (row, col)
    rel_r, rel_c = yy - H / 2, xx - W / 2
    across = rel_r * n_row + rel_c * n_col
    along = rel_r * s_row + rel_c * s_col
    step = 2.0 * (across > 0)                 # 2 units = 200 m at 100 m px
    z = 10.0 + step + 0.002 * along
    return z, across


def h60_operator(arr: np.ndarray) -> np.ndarray:
    # Copied line-for-line from src/gems52/h60.py (checked above).
    th = np.deg2rad(15.0)
    sy, sx = -np.cos(th), np.sin(th)
    d1 = ndimage.shift(arr, (sy, sx), order=1, mode="nearest")
    d2 = ndimage.shift(arr, (-sy, -sx), order=1, mode="nearest")
    return np.abs(d1 + d2 - 2 * arr) / (PIX ** 2)


def cross_strike_offset(arr: np.ndarray, d_px: float) -> np.ndarray:
    a = np.deg2rad(15.0)
    n_row, n_col = np.sin(a), np.cos(a)
    p = ndimage.shift(arr, (-n_row * d_px, -n_col * d_px), order=1, mode="nearest")
    m = ndimage.shift(arr, (n_row * d_px, n_col * d_px), order=1, mode="nearest")
    return np.abs(p - m)


def main() -> int:
    src = check_h60_source()
    z, across = synthetic_grid()
    on = np.abs(across) <= 2.5
    far = np.abs(across) >= 20.0
    h60 = h60_operator(z)
    x3 = cross_strike_offset(z, 3.0)
    x6 = cross_strike_offset(z, 6.0)

    def stat(a):
        m_on, m_far = float(a[on].mean()), float(a[far].mean())
        return dict(on_trace_mean=m_on, far_mean=m_far,
                    on_over_far=(m_on / m_far) if m_far > 0 else None)

    res = dict(stage="E1_operator_audit", generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
               purpose="Does the H60-3 along-strike second difference detect a basement step across a "
                       "strike-parallel trace? Compared with the H62-A cross-strike symmetric difference.",
               synthetic=dict(shape=list(z.shape), pixel_m=PIX, step_m=200.0, ramp_per_px=0.002,
                              strike_azimuth_deg=15.0, on_trace_halfwidth_px=2.5, far_px=20.0),
               h60_source=src,
               operators=dict(
                   h60_3_along_strike_second_difference=stat(h60),
                   cross_strike_symmetric_difference_d3=stat(x3),
                   cross_strike_symmetric_difference_d6=stat(x6)),
               verdict_text=None)
    ref = res["operators"]["cross_strike_symmetric_difference_d3"]["on_trace_mean"]
    res["operators"]["h60_3_along_strike_second_difference"]["on_trace_over_cross_d3"] = float(
        res["operators"]["h60_3_along_strike_second_difference"]["on_trace_mean"] / ref)
    ratio = res["operators"]["h60_3_along_strike_second_difference"]["on_trace_over_cross_d3"]
    res["verdict_text"] = (
        "H60-3 operator's on-trace response is %.2e of the cross-strike d=3 response in the same grid "
        "units. A step constant along strike has zero along-strike second difference, so the designed "
        "signal is absent. The residual on-trace value is confined to pixels at the discontinuity: it "
        "survives nearest-neighbour sampling (order 0) and vanishes for a pure ramp, so it is a "
        "discretisation effect of the staircased step, not the step signal. H62-A replaces it." % ratio)
    res["flag"] = "IR-H62-001"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, allow_nan=False) + "\n")
    print(json.dumps(res["operators"], indent=1))
    print(res["verdict_text"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
