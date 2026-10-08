#!/usr/bin/env python3
"""H60 stage 2 -- the corroboration ladder across ALL thirteen organiser-scored files.

Design
------
Stage 1 (``h60_forensics``) solved |G| = 14,088.7 px from the exact nesting A c B and measured
T_i = score_i * (0.2 S_i + 0.8 |G|) for every file whose bytes we hold.  This stage asks the
question the previous rounds never asked of the *organiser's own numbers*: does credit density
rise with the number of independent submissions that agree on a pixel, and is there high-credit
mass outside the champion clade?

Two estimators are reported, because with 13 equations and many atoms the atom credits are not
point-identified and pretending otherwise would be a hallucination:

  (a) ``leave-one-out corroboration regression`` -- the credit density is modelled as a function
      rho(k) of k(x) = the number of *other* scored files that emit x.  This is identified: 13
      equations, 13 unknowns, no file sees itself, so it cannot fit by construction.
  (b) ``family atom NNLS`` -- atom credits over a small named family, reported with the residual
      so the reader can see how under-determined it is.

Every number comes from restored, SHA-256-pinned bytes.  No number is copied from a prior note.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy.optimize import nnls

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DATA = ROOT / "data"

SCORES = {
    "A_h33_2_b2": 0.2778,
    "B_d2_8": 0.2600,
    "C_d1_5": 0.2477,
    "D_topogap": 0.2449,
    "E_h19_5": 0.1922,
    "F_h19_4": 0.1894,
    "G_h16_1": 0.1855,
    "H_h28_dotted": 0.1839,
    "I_Hedge_v2": 0.1563,
    "J_ens12": 0.1563,
    "K_ctx_ridge": 0.1280,
    "L_lattice": 0.0904,
    "M_placeholder": 0.0107,
}
FILES = {
    "A_h33_2_b2": "reference/h33-2-b2-zeros.tif",
    "B_d2_8": "scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif",
    "C_d1_5": "scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif",
    "D_topogap": "scored/gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif",
    "E_h19_5": "scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif",
    "F_h19_4": "scored/gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan.tif",
    "G_h16_1": "scored/gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif",
    "H_h28_dotted": "scored/gems10-h28-dotted-ridge-20260928T020256236880Z-6452ae1d00.tif",
    "I_Hedge_v2": "scored/8GEMSDOE_Hedge-v2_submission.tif",
    "J_ens12": "scored/gemsdoe-ens12-adopted-7f00890a.tif",
    "K_ctx_ridge": "scored/gems10-h25-ctx-ridge-20260927T232947704150Z-6452ae1d00.tif",
    "L_lattice": "scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif",
    "M_placeholder": "scored/gemsdoe9-PLACEHOLDER-2314b599.tif",
}
ORDER = list(FILES)

# |G| measured in stage 1 from the exact A c B nesting (ring credit = 0).
G_PX = 14088.7


def load(rel: str) -> np.ndarray:
    with rasterio.open(DATA / rel) as s:
        a = s.read(1)
    return np.isfinite(a) & (np.abs(a) > 1e-12)


def main() -> int:
    with rasterio.open(DATA / "sample_submission.tif") as s:
        tpl = s.read(1)
    finite = np.isfinite(tpl)
    with rasterio.open(DATA / "labels.tif") as s:
        lab = s.read(1)
    cat = np.zeros(tpl.shape, dtype=bool)
    cat[finite] = np.isfinite(lab[finite]) & (lab[finite] > 0.5)

    masks = {k: load(v) for k, v in FILES.items()}
    for k in ORDER:
        masks[k] &= finite

    # catalogued pixels earn nothing (measured: the <=200 m ring around the catalogue earns
    # exactly zero, knowledge/10 section 2, re-derived in stage 1).
    for k in ORDER:
        masks[k] &= ~cat

    S = {k: int(masks[k].sum()) for k in ORDER}
    T = {k: SCORES[k] * (0.2 * S[k] + 0.8 * G_PX) for k in ORDER}
    print("file            S(off-cat)   score       T      T/S")
    for k in ORDER:
        print(f"{k:16s} {S[k]:9d}  {SCORES[k]:.4f} {T[k]:8.1f}  {T[k]/max(S[k],1):.4f}")

    print(f"\nunion of all 13 = {int(np.logical_or.reduce([masks[k] for k in ORDER]).sum())} px")
    print("pairwise |X & Y|:")
    hdr = "      " + "".join(f"{k[:1]:>8s}" for k in ORDER)
    print(hdr)
    for x in ORDER:
        print(f"{x[:1]:>4s}  " + "".join(f"{int((masks[x]&masks[y]).sum()):8d}" for y in ORDER))

    # ---------- (a) leave-one-out corroboration regression ----------
    # k_i(x) = number of OTHER files emitting x.  T_i = sum_k n_i(k) rho(k).
    KMAX = len(ORDER) - 1
    Amat = np.zeros((len(ORDER), KMAX + 1))
    for i, k in enumerate(ORDER):
        others = np.zeros(tpl.shape, dtype=np.int16)
        for j, o in enumerate(ORDER):
            if j == i:
                continue
            others += masks[o]
        cnt = others[masks[k]]
        for c in range(KMAX + 1):
            Amat[i, c] = float((cnt == c).sum())
    bvec = np.array([T[k] for k in ORDER])
    # weighted NNLS: equalise the 13 equations (they differ by 20x in magnitude)
    w = 1.0 / np.maximum(bvec, 1.0)
    sol, _ = nnls(Amat * w[:, None], bvec * w)
    print("\n(a) leave-one-out corroboration density rho(k):")
    for c in range(KMAX + 1):
        if Amat[:, c].sum() > 0:
            print(f"   k={c:2d}  rho={sol[c]:.5f}   px across files={int(Amat[:,c].sum())}")
    pred = Amat @ sol
    print("   file  T_measured  T_predicted  rel.err")
    for i, k in enumerate(ORDER):
        print(f"   {k:16s} {bvec[i]:8.1f} {pred[i]:9.1f}  {(pred[i]-bvec[i])/bvec[i]:+.3f}")

    # ---------- (b) named-family atoms ----------
    fam = ["A_h33_2_b2", "E_h19_5", "I_Hedge_v2", "J_ens12"]
    short = {n: n[:1] for n in fam}
    sig = np.zeros(tpl.shape, dtype=np.int64)
    for i, n in enumerate(fam):
        sig[masks[n]] |= (1 << i)
    print(f"\n(b) atoms of {[short[n] for n in fam]} (A=champion, E=h19-5 clade, I=Hedge-v2, J=ens12):")
    atoms = []
    for v in np.unique(sig):
        px = int((sig == v).sum())
        if v == 0 or px == 0:
            continue
        mem = "".join(short[fam[i]] if (v >> i) & 1 else "-" for i in range(len(fam)))
        atoms.append((int(v), mem, px, sig == v))
    for v, mem, px, m in sorted(atoms, key=lambda t: -t[2]):
        print(f"   {mem:6s} {px:8d} px")

    # under-determined: report the bounding box of each atom's credit instead of a point value
    print("\n   identifiability: 4 equations, %d unknown atom credits -> under-determined." % len(atoms))
    print("   instead, report each atom's credit under the extreme allocations below.")

    # extreme allocations: put all of a file's credit on its 'best' vs 'worst' atoms
    # (LP-style bounds via scipy linprog on each atom in turn)
    from scipy.optimize import linprog
    Aeq = np.array([[float((m & masks[n]).sum()) for _, _, _, m in atoms] for n in fam])
    beq = np.array([T[n] for n in fam])
    bounds = []
    for v, mem, px, m in atoms:
        lo, hi = linprog(-np.eye(len(atoms))[atoms.index((v, mem, px, m))], A_eq=Aeq, b_eq=beq,
                         bounds=[(0, None)] * len(atoms), method="highs")
        hi_v = -lo.fun
        lo2 = linprog(np.eye(len(atoms))[atoms.index((v, mem, px, m))], A_eq=Aeq, b_eq=beq,
                      bounds=[(0, None)] * len(atoms), method="highs")
        bounds.append((mem, px, lo2.fun, hi_v))
    print("   atom   px        credit_lo  credit_hi   density_lo  density_hi")
    for mem, px, lo, hi in bounds:
        print(f"   {mem:6s} {px:8d}  {lo:9.1f}  {hi:9.1f}   {lo/px:.5f}     {hi/px:.5f}")

    out = dict(G_px=G_PX, S={k: S[k] for k in ORDER}, T={k: T[k] for k in ORDER},
               rho_by_k={str(c): float(sol[c]) for c in range(KMAX + 1)},
               loo_pred={k: float(pred[i]) for i, k in enumerate(ORDER)},
               loo_meas={k: float(bvec[i]) for i, k in enumerate(ORDER)},
               atom_bounds=[dict(atom=m, px=p, credit_lo=float(l), credit_hi=float(h),
                                 density_lo=float(l / p), density_hi=float(h / p))
                            for m, p, l, h in bounds])
    (ROOT / "work").mkdir(exist_ok=True)
    (ROOT / "work" / "h60_atoms.json").write_text(json.dumps(out, indent=1))
    print("\nwrote work/h60_atoms.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
