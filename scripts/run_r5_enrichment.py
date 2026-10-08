#!/usr/bin/env python3
"""R5 -- does the new six-family ridge pool concentrate the *credited* mass?  Receipt, not prose.

``knowledge/27`` §5 and ``knowledge/26`` both quote an enrichment measurement: the champion's emission
and every one of its credit atoms sit inside the R5 corroborated-ridge pool at about 1.5x the rate a
uniform off-ring pixel does, and -- the part that matters -- at the *same* rate whatever their credit
density.  A claim like that has to be reproducible from a receipt, so this script recomputes it from
the restored bytes and the atom algebra of ``knowledge/10`` §3 and writes
``evidence/r5_pool_enrichment.json``.

The reading it supports is a negative one and it is stated as such: the pool captures where this
family *emits* (habitat) and says nothing about which emissions were *right* (credit), which is
``knowledge/10`` §6's finding reproduced with a detector that did not exist when §6 was written.

Usage:  python scripts/run_r5_enrichment.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52_r5 import layers as L                # noqa: E402
from gems52_r5 import revealed_r5 as R           # noqa: E402

WORK = ROOT / "work" / "r5"
EVID = ROOT / "evidence"
CORRIDOR_M = 200.0

# the atom credit bounds of knowledge/10 §3, in px of credit; densities are bounds / atom size
BOUNDS = {
    "P1": (4168.0, 5223.0),
    "P2": (0.0, 1055.0),
    "P3": (0.0, 0.0),
    "P4": (0.0, 0.0),
    "P5": (544.0, 1599.0),
    "P6": (0.0, 1055.0),
}


def main() -> int:
    t0 = time.time()
    valid = np.load(WORK / "valid.npy")
    cat = L.catalogue()
    edt = ndimage.distance_transform_edt(~cat, sampling=100.0)
    legal = valid & (edt > CORRIDOR_M)

    corr = np.load(WORK / f"corrobor_{0.99:g}.npy")
    st = np.ones((3, 3), bool)
    pools = {
        "pool_C2": ndimage.binary_dilation(corr >= 2, st) & legal,
        "pool_C3": ndimage.binary_dilation(corr >= 3, st) & legal,
    }

    supp = R.load_supports(ROOT / "data")          # p > 0 and off the catalogue mask, per file
    champ_name = "h33-2-b2-zeros.tif"
    A = supp[champ_name] & valid
    B = supp["gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif"] & valid
    C = supp["gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif"] & valid
    E = supp["gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif"] & valid
    atoms = dict(P1=A & C, P2=A & ~C, P3=(B & ~A) & C, P4=(B & ~A) & ~C,
                 P5=(E & ~B) & C, P6=(E & ~B) & ~C)
    extra = dict(A_champion=A, B=B, C=C, E=E, E_tail=E & ~B)

    out = dict(
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        inputs=dict(footprint_px=int(valid.sum()), legal_off_ring_px=int(legal.sum()),
                    catalogue_px=int(cat.sum()),
                    champion_name=champ_name,
                    n_scored_files=len(supp),
                    note=("supports are masked to the footprint here, so the atom sizes are a few px "
                          "smaller than knowledge/10 §3, which counted the whole raster; both are "
                          "reported")),
        pools={k: dict(px=int(v.sum()), fraction_of_legal=float(v.sum() / legal.sum()))
               for k, v in pools.items()},
        atoms={}, extra_sets={}, pool_credit_density_bounds={},
        reading=(
            "Every atom is enriched inside the pool by about the same factor (1.5-1.8x) whatever its "
            "credit density, from P1 at 0.163-0.205 down to P6 at 0-0.023. The pool therefore "
            "identifies where this family emits, not which emissions were right: knowledge/10 §6's "
            "'habitat is not credit', reproduced with a detector that did not exist when §6 was "
            "written. The lower bound on the pool's own credit density is trivial (0.0014-0.0030) "
            "because only 3.4% of pool pixels are inside the family's emission at all, so the "
            "remaining 96.6% is novel mass with an unmeasured density -- which is why nothing in R5 "
            "claims a measured rho for the shipped file and the projection is a prior instead."),
        seconds=time.time() - t0)

    for name, mask in list(atoms.items()) + list(extra.items()):
        row = dict(px_in_raster=int(mask.sum()), px_off_ring=int((mask & legal).sum()))
        for pname, pmask in pools.items():
            inside = int((mask & legal & pmask).sum())
            denom = max(row["px_off_ring"], 1)
            row[pname] = dict(px=inside, fraction=inside / denom,
                              enrichment=(inside / denom) / (pmask.sum() / legal.sum()))
        if name in atoms:
            lo, hi = BOUNDS[name]
            row["credit_bounds_px"] = [lo, hi]
            row["credit_density_bounds"] = [lo / max(int(mask.sum()), 1), hi / max(int(mask.sum()), 1)]
        out["atoms" if name in atoms else "extra_sets"][name] = row

    for pname, pmask in pools.items():
        lo = sum(BOUNDS[k][0] / max(int(atoms[k].sum()), 1) * int((atoms[k] & legal & pmask).sum())
                 for k in atoms)
        hi = sum(BOUNDS[k][1] / max(int(atoms[k].sum()), 1) * int((atoms[k] & legal & pmask).sum())
                 for k in atoms)
        out["pool_credit_density_bounds"][pname] = dict(
            credit_from_family_atoms_lower=lo, credit_from_family_atoms_upper=hi,
            pool_px=int(pmask.sum()),
            rho_lower=lo / int(pmask.sum()), rho_upper=hi / int(pmask.sum()),
            fraction_of_pool_inside_family_emission=float((pmask & E).sum() / pmask.sum()),
            reference_rho_uniform_random=0.0279)

    EVID.mkdir(exist_ok=True)
    (EVID / "r5_pool_enrichment.json").write_text(json.dumps(out, indent=1))
    (ROOT / "docs/data/r5_pool_enrichment.json").write_text(json.dumps(out, indent=1))
    for name in ("P1", "P6", "A_champion", "E_tail"):
        row = out["atoms"].get(name) or out["extra_sets"].get(name)
        print(f"{name:12s} off-ring {row['px_off_ring']:7,d}  pool_C2 {row['pool_C2']['fraction']:.4f} "
              f"(x{row['pool_C2']['enrichment']:.2f})  pool_C3 {row['pool_C3']['fraction']:.4f} "
              f"(x{row['pool_C3']['enrichment']:.2f})")
    print(f"pool credit-density bounds: {json.dumps({k: (round(v['rho_lower'], 4), round(v['rho_upper'], 4)) for k, v in out['pool_credit_density_bounds'].items()})}")
    print(f"wrote evidence/r5_pool_enrichment.json in {out['seconds']:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
