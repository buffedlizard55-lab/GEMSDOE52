#!/usr/bin/env python3
"""Diagnostic (not a score): per-dot credit of the dots the H97 veto removed vs the dots that replaced them."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import numpy as np                       # noqa: E402
from scipy import ndimage as ndi         # noqa: E402
import run_h97 as h                      # noqa: E402

_r, store, cat, eligible, folds, va, vb, ring_px = h.base.setup()
fl, dcard, defined, lowslope = h.load_orient()
out = dict(stage="swap_diagnostic", evidence_class="diagnostic per-dot kernel credit, not a score", folds=[])
for fold in folds:
    f = fold["fold"]
    allowed = h.allowed_of(fold, ring_px)
    ai = np.flatnonzero(allowed.ravel())
    ranks = {}
    for arm in ("single_A", "B_DVA2", "B_DVA2s"):
        g = h.base.to_grid(store.flat_idx, np.load(h.WORK / f"pred_{arm}_f{f}.npy"), eligible.shape)
        r = np.full(eligible.shape, np.nan, np.float32)
        r.ravel()[ai] = h.base.pct_rank(g.ravel()[ai])
        ranks[arm] = r
    derived, flags, erosion, road = h.arm_fields(ranks["single_A"], ranks["B_DVA2"], ranks["B_DVA2s"], fl, dcard, lowslope)
    credit = np.clip(1.0 - ndi.distance_transform_edt(~fold["truth"]) / 3.0, 0.0, None)
    em = {}
    for arm, src in (("B_DVA2", ranks["B_DVA2"]), ("H97_veto", derived["H97_veto"])):
        fld = np.full(eligible.shape, -9.0, np.float32)
        fld.ravel()[ai] = np.nan_to_num(src.ravel()[ai], nan=-9.0)
        em[arm] = h.nodes.spacing_select(fld, allowed, h.K_FOLD, min_px=3.0)
    removed = em["B_DVA2"] & ~em["H97_veto"]
    added = em["H97_veto"] & ~em["B_DVA2"]
    rec = dict(fold=f, removed=int(removed.sum()), added=int(added.sum()),
               removed_mean_credit=float(credit[removed].mean()) if removed.any() else None,
               added_mean_credit=float(credit[added].mean()) if added.any() else None,
               removed_flagged=int((removed & flags["H97_veto"]).sum()))
    out["folds"].append(rec)
    print(rec, flush=True)
(ROOT / "evidence/h97_swap_diagnostic.json").write_text(json.dumps(out, indent=1) + "\n")
