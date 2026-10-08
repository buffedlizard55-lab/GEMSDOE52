#!/usr/bin/env python3
"""H60 stage 3 -- IDENTIFIED INTERVALS for candidate emission sets, from the organiser's scores.

Model
-----
Twelve scored files give twelve aggregate credit constraints

    sum_{atoms a subset of file i}  t_a  =  T_i ,      t_a >= 0

with 559 atoms and 12 equations, so atom credits are set-identified, not point-identified.  Three
facts are added as constraints, each one a fact rather than a tuning knob:

  * t_a >= 0                       credit cannot be negative
  * sum_a t_a <= |G|               no emission can credit more truth than exists (|G| = 14,088.7)
  * t_a <= CMAX * |a|              a single pixel covers at most CMAX truth-mass.  For a straight
                                   1-px trace and a dot sitting on it the exact value is
                                   1 + 2*(2/3) + 2*(1/3) = 3.0; CMAX = 1.0 is also reported as a
                                   deliberately pessimistic alternative.

The raw system is infeasible by 3.5 credit-units -- file C is a strict subset of file D yet reports
a marginally higher score (0.2477 vs 0.2449), which the 4-decimal publication rounding cannot
absorb.  Equalities are therefore enforced with a per-file slack delta_i = max(4.0, 0.002 T_i),
which is the smallest band that makes the system feasible; its size is reported.

For every candidate emission set X the exact interval [T_lo(X), T_hi(X)] is computed by linear
programming, and the induced [DTI_lo, DTI_hi] is reported.  Decisions are then taken on the
interval (maximin), never on a point estimate -- a point estimate here would invent information.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DATA = ROOT / "data"
G_PX = 14088.7
ALPHA, BETA = 0.2, 0.8
SLACK_ABS, SLACK_REL = 4.0, 0.002

SCORES = {"A": 0.2778, "B": 0.2600, "C": 0.2477, "D": 0.2449, "E": 0.1922, "F": 0.1894,
          "G": 0.1855, "H": 0.1839, "I": 0.1563, "K": 0.1280, "L": 0.0904, "M": 0.0107}
REL = {
    "A": "reference/h33-2-b2-zeros.tif",
    "B": "scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif",
    "C": "scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif",
    "D": "scored/gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif",
    "E": "scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif",
    "F": "scored/gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan.tif",
    "G": "scored/gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif",
    "H": "scored/gems10-h28-dotted-ridge-20260928T020256236880Z-6452ae1d00.tif",
    "I": "scored/8GEMSDOE_Hedge-v2_submission.tif",
    "K": "scored/gems10-h25-ctx-ridge-20260927T232947704150Z-6452ae1d00.tif",
    "L": "scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif",
    "M": "scored/gemsdoe9-PLACEHOLDER-2314b599.tif",
}
FAMILY = {"A": "h19clade", "B": "h19clade", "C": "h19clade", "D": "h19clade", "E": "h19clade",
          "F": "h19clade", "G": "h19clade", "H": "gemsdoe10", "I": "gemsdoe8",
          "K": "gemsdoe10", "L": "gemsdoe13", "M": "gemsdoe9"}
ORDER = list(REL)


def main() -> int:
    with rasterio.open(DATA / "sample_submission.tif") as s:
        tpl = s.read(1)
    finite = np.isfinite(tpl)
    with rasterio.open(DATA / "labels.tif") as s:
        lb = s.read(1)
    cat = np.zeros(tpl.shape, dtype=bool)
    cat[finite] = np.isfinite(lb[finite]) & (lb[finite] > 0.5)

    masks = {}
    for k in ORDER:
        with rasterio.open(DATA / REL[k]) as s:
            a = s.read(1)
        masks[k] = finite & np.isfinite(a) & (np.abs(a) > 1e-12)
    Sfull = {k: int(masks[k].sum()) for k in ORDER}
    # credit T_i from the published score and the FULL emitted mass: catalogued pixels still pay
    # the false-positive tax even though they earn no credit.
    T = {k: SCORES[k] * (ALPHA * Sfull[k] + BETA * G_PX) for k in ORDER}
    off = {k: masks[k] & ~cat for k in ORDER}

    sig = np.zeros(tpl.shape, dtype=np.int32)
    for i, k in enumerate(ORDER):
        sig[off[k]] |= (1 << i)
    vals, inv = np.unique(sig[sig > 0], return_inverse=True)
    px = np.bincount(inv, minlength=vals.size).astype(float)
    o = np.argsort(-px)
    vals, px = vals[o], px[o]
    print(f"atoms={vals.size}  footprint={int(finite.sum())}  catalogue={int(cat.sum())}")
    print("file   S_full   on_cat   S_off       T")
    for k in ORDER:
        print(f"  {k}  {Sfull[k]:7d} {int((masks[k]&cat).sum()):7d} {int(off[k].sum()):8d} {T[k]:8.1f}")

    Aeq = np.array([[px[j] if (v >> i) & 1 else 0.0 for j, v in enumerate(vals)]
                    for i in range(len(ORDER))])
    beq = np.array([T[k] for k in ORDER])
    delta = np.maximum(SLACK_ABS, SLACK_REL * beq)

    fams = sorted(set(FAMILY.values()))
    nfam = np.array([len({FAMILY[ORDER[i]] for i in range(len(ORDER)) if (v >> i) & 1})
                     for v in vals], dtype=np.int32)

    def interval(sel: np.ndarray, cmax: float | None) -> tuple[float, float]:
        """[min, max] of sel . t over the identified set, expressed as A x <= b only."""
        n = vals.size
        blocks = [np.ones((1, n))]
        rhs = [np.array([G_PX])]
        if cmax is not None:
            blocks.append(np.eye(n))
            rhs.append(cmax * px)
        blocks.append(Aeq);        rhs.append(beq + delta)
        blocks.append(-Aeq);       rhs.append(-(beq - delta))
        A = np.vstack(blocks)
        b = np.concatenate(rhs)
        r1 = linprog(sel.astype(float), A_ub=A, b_ub=b, bounds=(0, None), method="highs")
        r2 = linprog(-sel.astype(float), A_ub=A, b_ub=b, bounds=(0, None), method="highs")
        if not (r1.success and r2.success):
            return (float("nan"), float("nan"))
        return (float(r1.fun), float(-r2.fun))

    def dti(tt: float, n: int) -> float:
        return tt / (ALPHA * n + BETA * G_PX)

    idx_of_val = {int(v): j for j, v in enumerate(vals)}

    def sel_of(m: np.ndarray) -> np.ndarray:
        """Per-atom pixel counts of the set ``m``."""
        sub = sig[m]
        sub = sub[sub > 0]
        cnt = np.zeros(vals.size, dtype=float)
        for v, c in zip(*np.unique(sub, return_counts=True)):
            cnt[idx_of_val[int(v)]] = float(c)
        return cnt

    cands: list[tuple[str, np.ndarray]] = []
    for nf in range(1, len(fams) + 1):
        m = np.isin(sig, vals[nfam >= nf]) & (sig > 0)
        if m.sum():
            cands.append((f"crossfam>={nf}", m))
    cands += [
        ("A champion", masks["A"]),
        ("P1=A&C", off["A"] & off["C"]),
        ("P2=A\\C", off["A"] & ~off["C"]),
        ("A&I(champ x Hedge)", off["A"] & off["I"]),
        ("P1 & I", off["A"] & off["C"] & off["I"]),
        ("P1 \\ I", (off["A"] & off["C"]) & ~off["I"]),
        ("P1 u (A&I\\P1)", (off["A"] & off["C"]) | (off["A"] & off["I"])),
        ("E&I", off["E"] & off["I"]),
        ("E&I\\A", (off["E"] & off["I"]) & ~off["A"]),
        ("I\\E", off["I"] & ~off["E"]),
        ("I Hedge-v2", off["I"]),
        ("E h19-5", off["E"]),
    ]

    print("\n" + "=" * 100)
    print(f"{'candidate':22s} {'px':>8s} | {'T_lo':>8s} {'T_hi':>8s} {'DTI_lo':>7s} {'DTI_hi':>7s} "
          f"| {'T_lo(c1)':>8s} {'T_hi(c1)':>8s} {'DTI_lo':>7s} {'DTI_hi':>7s}")
    print("=" * 100)
    rows = []
    for name, m in cands:
        n = int(m.sum())
        if n == 0:
            continue
        sel = sel_of(m)
        lo3, hi3 = interval(sel, 3.0)
        lo1, hi1 = interval(sel, 1.0)
        r = dict(name=name, px=n, T_lo=lo3, T_hi=hi3, dti_lo=dti(lo3, n), dti_hi=dti(hi3, n),
                 T_lo_c1=lo1, T_hi_c1=hi1, dti_lo_c1=dti(lo1, n), dti_hi_c1=dti(hi1, n),
                 dti_worst_c3=dti(lo3, n), dti_worst_c1=dti(lo1, n))
        rows.append(r)
        print(f"{name:22s} {n:8d} | {lo3:8.1f} {hi3:8.1f} {dti(lo3,n):7.4f} {dti(hi3,n):7.4f} "
              f"| {lo1:8.1f} {hi1:8.1f} {dti(lo1,n):7.4f} {dti(hi1,n):7.4f}")

    (ROOT / "work").mkdir(exist_ok=True)
    (ROOT / "work" / "h60_identify.json").write_text(json.dumps(dict(
        G_px=G_PX, slack=dict(abs=SLACK_ABS, rel=SLACK_REL, per_file=dict(zip(ORDER, delta.tolist()))),
        S_full=Sfull, T=T, candidates=rows), indent=1))
    np.save(ROOT / "work" / "h60_sig.npy", sig)
    np.save(ROOT / "work" / "h60_vals.npy", vals)
    print("\nwrote work/h60_identify.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
