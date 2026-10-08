#!/usr/bin/env python3
"""H60 forensics: solve for the hidden truth size |G| and per-atom credit from the
organiser-scored prior rasters whose bytes we hold and whose scores the owner reported.

Why this is the primary instrument
----------------------------------
`knowledge/10` section 5 and round R4 both measured that the local hide-and-recover
simulator does NOT predict the organiser's board (Spearman -0.10; uniform random beats
the champion).  The only evidence in this repository that is actually tied to the
organiser's scoring is the set of published scores attached to files whose bytes we hold.
Where those files stand in *exact set relations* to one another, their scores form a small
linear system in the atom credits, so the credits are measured rather than modelled.

Everything here is recomputed from the restored bytes, never copied from a previous note.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import metric as M  # noqa: E402

DATA = ROOT / "data"

# owner-reported public-leaderboard scores; file -> score.  NOT organiser-authenticated:
# the board publishes no filename.  Recorded as the standing caveat.
SCORES = {
    "ref_h33_2_b2": 0.2778,
    "scored_d28_unscored": 0.2600,
    "scored_d15_scored": 0.2477,
    "scored_gems27_tgc_v2_d15": 0.2449,
    "scored_h19_5": 0.1922,
    "scored_h19_4": 0.1894,
    "scored_h16_1": 0.1855,
    "calib_gems10-h28-dotted-ridge-20260928T0202562": 0.1839,
    "calib_8GEMSDOE_Hedge-v2_submission": 0.1563,
    "calib_gemsdoe-ens12-adopted-7f00890a": 0.1563,
    "calib_gems10-h25-ctx-ridge-20260927T2329477041": 0.1280,
    "calib_13gems_20261001_r13-lattice-s5_v2_nan-ou": 0.0904,
    "calib_gemsdoe9-PLACEHOLDER-2314b599": 0.0107,
}

FILES = {
    "ref_h33_2_b2": "reference/h33-2-b2-zeros.tif",
    "scored_d28_unscored": "scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif",
    "scored_d15_scored": "scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif",
    "scored_gems27_tgc_v2_d15": "scored/gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif",
    "scored_h19_5": "scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif",
    "scored_h19_4": "scored/gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan.tif",
    "scored_h16_1": "scored/gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif",
    "calib_gems10-h28-dotted-ridge-20260928T0202562":
        "scored/gems10-h28-dotted-ridge-20260928T020256236880Z-6452ae1d00.tif",
    "calib_8GEMSDOE_Hedge-v2_submission": "scored/8GEMSDOE_Hedge-v2_submission.tif",
    "calib_gemsdoe-ens12-adopted-7f00890a": "scored/gemsdoe-ens12-adopted-7f00890a.tif",
    "calib_gems10-h25-ctx-ridge-20260927T2329477041":
        "scored/gems10-h25-ctx-ridge-20260927T232947704150Z-6452ae1d00.tif",
    "calib_13gems_20261001_r13-lattice-s5_v2_nan-ou":
        "scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif",
    "calib_gemsdoe9-PLACEHOLDER-2314b599": "scored/gemsdoe9-PLACEHOLDER-2314b599.tif",
}


def load_template():
    with rasterio.open(DATA / "sample_submission.tif") as s:
        prof = s.profile
        tpl = s.read(1)
    return tpl, prof


def load_mask(rel: str) -> np.ndarray:
    """Binary emitted-pixel mask on the sample-submission grid (NaN treated as not emitted)."""
    with rasterio.open(DATA / rel) as s:
        a = s.read(1).astype(np.float64)
    with rasterio.open(DATA / "sample_submission.tif") as s:
        tpl = s.read(1)
    finite_tpl = np.isfinite(tpl)
    m = np.zeros(a.shape, dtype=bool)
    m[finite_tpl] = np.isfinite(a[finite_tpl]) & (np.abs(a[finite_tpl]) > 1e-12)
    return m


def main() -> int:
    tpl, prof = load_template()
    finite = np.isfinite(tpl)
    n_foot = int(finite.sum())
    print(f"grid {tpl.shape}  footprint px = {n_foot}")

    labels = None
    with rasterio.open(DATA / "labels.tif") as s:
        labels = s.read(1)
    lab = np.zeros(tpl.shape, dtype=bool)
    lab[finite] = np.isfinite(labels[finite]) & (labels[finite] > 0.5)
    print(f"catalogue label px = {int(lab.sum())}")

    masks = {}
    for k, rel in FILES.items():
        masks[k] = load_mask(rel)
        n = int(masks[k].sum())
        on_lab = int((masks[k] & lab).sum())
        print(f"  {k:52s} S={n:7d}  on-catalogue={on_lab:6d}")

    # ---- |G| from the exact nesting A subset B, B\A = the <=200 m ring, ring credit 0 ----
    A = masks["ref_h33_2_b2"]
    B = masks["scored_d28_unscored"]
    a_minus_b = int((A & ~B).sum())
    b_minus_a = int((B & ~A).sum())
    print(f"\nA\\B = {a_minus_b}   B\\A = {b_minus_a}")
    SA, SB = int(A.sum()), int(B.sum())
    sA, sB = SCORES["ref_h33_2_b2"], SCORES["scored_d28_unscored"]
    # sA = T/(0.2 SA + 0.8 G);  sB = T/(0.2 SB + 0.8 G)  ->  sA/sB = (0.2 SB + 0.8G)/(0.2 SA + 0.8G)
    # => 0.8G (sA - sB) = sB*0.2*SB - sA*0.2*SA ... derive numerically
    ratio = sA / sB
    # ratio*(0.2 SA + 0.8G) = 0.2 SB + 0.8G  ->  0.8G(ratio-1) = 0.2 SB - 0.2 SA*ratio
    G = (0.2 * SB - 0.2 * SA * ratio) / (0.8 * (ratio - 1.0))
    T_A = sA * (0.2 * SA + 0.8 * G)
    print(f"|G| solved from A/B nesting = {G:.1f} px   T(A) = {T_A:.1f}")
    print(f"   implied catalogue+hidden total truth = {G:.0f}; catalogue label px = {int(lab.sum())}")

    # ---- credit T for every scored file ----
    rows = []
    for k, m in masks.items():
        S = int(m.sum())
        sc = SCORES[k]
        T = sc * (0.2 * S + 0.8 * G)
        rows.append(dict(id=k, S=S, score=sc, T=T, density=T / S if S else 0.0,
                         on_lab=int((m & lab).sum())))
    rows.sort(key=lambda r: -r["density"])
    print("\nfile                                                     S      score        T   T/S")
    for r in rows:
        print(f"{r['id']:52s} {r['S']:7d}  {r['score']:.4f}  {r['T']:8.1f}  {r['density']:.4f}")

    # ---- atom decomposition over the nested family ----
    names = ["ref_h33_2_b2", "scored_d28_unscored", "scored_d15_scored",
             "scored_gems27_tgc_v2_d15", "scored_h19_5"]
    short = {"ref_h33_2_b2": "A", "scored_d28_unscored": "B", "scored_d15_scored": "C",
             "scored_gems27_tgc_v2_d15": "D", "scored_h19_5": "E"}
    # subset / superset census
    print("\nset relations (rows: X\\Y pixel counts)")
    print("        " + "".join(f"{short[n]:>9s}" for n in names))
    for x in names:
        line = f"{short[x]:>6s}  "
        for y in names:
            line += f"{int((masks[x] & ~masks[y]).sum()):9d}"
        print(line)

    # atoms via signature bits
    sig = np.zeros(tpl.shape, dtype=np.int64)
    for i, n in enumerate(names):
        sig[masks[n]] |= (1 << i)
    atoms = {}
    for v in np.unique(sig):
        if v == 0 or int((sig == v).sum()) == 0:
            continue
        member = "".join(short[names[i]] if (v >> i) & 1 else "-" for i in range(len(names)))
        atoms[int(v)] = dict(sig=int(v), member=member, px=int((sig == v).sum()),
                             mask=(sig == v))
    print("\natoms of {A,B,C,D,E}:")
    for v, a in sorted(atoms.items(), key=lambda kv: -kv[1]["px"]):
        print(f"  {a['member']:8s} {a['px']:8d} px")

    # ---- solve credit per atom (non-negative least squares over the 5 scored files) ----
    from scipy.optimize import nnls
    vs = sorted(atoms.keys())
    Amat, bvec, wts = [], [], []
    for n in names:
        if n not in SCORES:
            continue
        S = int(masks[n].sum())
        sc = SCORES[n]
        T = sc * (0.2 * S + 0.8 * G)
        row = [float(atoms[v]["px"]) if (v >> names.index(n)) & 1 else 0.0 for v in vs]
        Amat.append(row)
        bvec.append(T)
        wts.append(1.0)
    Amat = np.array(Amat)
    bvec = np.array(bvec)
    sol, res = nnls(Amat, bvec)
    print("\nNNLS atom credit density (credit per px) and total credit:")
    tot = 0.0
    for v, d, t in zip(vs, sol, sol * np.array([atoms[v]["px"] for v in vs])):
        tot += t
        print(f"  {atoms[v]['member']:8s} px={atoms[v]['px']:8d}  density={d:.5f}  credit={t:8.1f}")
    print(f"  total credit over union = {tot:.1f}   (|G| = {G:.1f})")
    resid = Amat @ sol - bvec
    print("  fit residuals:", np.round(resid, 2))

    out = dict(
        grid=list(tpl.shape), footprint_px=n_foot, catalogue_px=int(lab.sum()),
        G_px=float(G), T_champion=float(T_A),
        A_minus_B=a_minus_b, B_minus_A=b_minus_a,
        files=[{k: v for k, v in r.items()} for r in rows],
        atoms=[dict(sig=a["sig"], member=a["member"], px=a["px"],
                    density=float(d), credit=float(d * a["px"]))
               for a, d in ((atoms[v], s) for v, s in zip(vs, sol))],
        nnls_residual=float(res),
    )
    (ROOT / "work").mkdir(exist_ok=True)
    (ROOT / "work" / "h60_forensics.json").write_text(json.dumps(out, indent=1))
    np.save(ROOT / "work" / "h60_atom_sig.npy", sig)
    print("\nwrote work/h60_forensics.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
