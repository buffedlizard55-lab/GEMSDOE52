#!/usr/bin/env python3
"""Register one extra ranking field into the H62 validation receipt (both instruments).

Why this exists
---------------
``evidence/h62_cotrain.json`` measured that View A's confident set at the *absolute* bar
``q_conf = 0.60`` thins to only 6,307 dots against View B's 31,083 at the same bar, and the
independently-thinned intersection is 92 px -- two orders of magnitude below any usable budget.
That is a structural property of the operator, not a tuning accident: two independent thinnings of
size ``k`` inside a pool of ``n`` intersect in ``k^2/n`` dots, which at ``k`` = 30,000 and
``n`` = 4,861,502 is 185 even under perfect independence.

So the corroboration operator cannot be *delivered* as a hard intersection at this budget.  It can
still be delivered as a **ranking** on the joint confidence ``min(pA, pB)``, which is high only
where both views vouch for the pixel and is therefore not the union.  This script registers that
soft form -- ``conc_soft`` -- on exactly the same two instruments as the preregistered fields, so
the round's promotion decision compares like with like.

The hard intersection (``conc_corrob``) and the thresholded cell (``conc_min``) remain in the
receipt as the measured structural negative.
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

from gems52 import grid as G                        # noqa: E402
from gems52 import h57                              # noqa: E402
from gems52 import h60d                             # noqa: E402
from gems52 import h62                              # noqa: E402
from gems52 import holdout as HO                    # noqa: E402
from gems52 import metric as M                      # noqa: E402

DATA = ROOT / "data"
WORK = ROOT / "work/h62"
EV = ROOT / "evidence"
PREREG = json.loads((ROOT / "registry/h62_preregistration.json").read_text())
SEED = int(PREREG["protocol"]["seed"])
TH = PREREG["protocol"]["thresholds"]
Q_CONF = float(TH["q_conf"])
N_BOOT = 10000


def log(m: str) -> None:
    print(f"[h62-extra {time.strftime('%H:%M:%S')}] {m}", flush=True)


def main() -> int:
    t0 = time.time()
    val = json.loads((EV / "h62_validation.json").read_text())
    valid = G.footprint_from(DATA / "training_features.tif", bands="all")
    with rasterio.open(DATA / "labels.tif") as src:
        cat = src.read(1) == 1
    pa = np.nan_to_num(np.load(WORK / "pa_oof.npy"), nan=0.0).astype(np.float32)
    pb = np.nan_to_num(np.load(WORK / "pb_oof.npy"), nan=0.0).astype(np.float32)
    corridor = ndimage.binary_dilation(cat, iterations=h57.CORRIDOR_PX)
    permitted = valid & ~corridor

    extra = {"conc_soft": h62.concordance_surface(pa, pb)}

    with rasterio.open(DATA / "reference/h33-2-b2-zeros.tif") as src:
        ref = src.read(1) > 0
    with rasterio.open(DATA / "scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif"
                       ) as src:
        p1 = ref & (np.isfinite(src.read(1)) & (src.read(1) > 0))

    rows = []
    for name, fld in extra.items():
        row = dict(field=name)
        for k in h62.GAMMA_GRID:
            nodes = h57.iso_select(np.where(permitted, fld, 0.0).astype(np.float32),
                                   permitted, k, min_px=3.0, nms_px=3)
            row[f"f_{k}"] = h62.revealed_colocation(nodes, p1, permitted)
        rows.append(row)
        log(f"{name}: " + ", ".join(
            f"{k//1000}k={row[f'f_{k}']['lift']:.2f}x" for k in h62.GAMMA_GRID))

    budgets = [int(k.split("|")[1]) for k in val["instrument1_holdout"]["arms"]]
    budgets = sorted({int(b) for b in budgets if True})
    if not budgets:
        budgets = [15000, 25000]
    folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002, seed=SEED,
                          mode="hide")
    cells = []
    for f in folds:
        blocked = ndimage.binary_dilation(f["visible"] & valid, iterations=h57.CORRIDOR_PX)
        legal = f["region"] & permitted & ~blocked
        for k in budgets:
            for name, fld in extra.items():
                sc = np.where(legal, fld, 0.0).astype(np.float32)
                nodes = h57.iso_select(sc, legal, k, min_px=3.0, nms_px=3)
                p = np.where(f["region"], nodes.astype(np.float32), 0.0)
                p = HO.mask_visible(p, f["visible"] & valid)
                r = M.dti(p, f["truth"] & f["region"] & valid)
                cells.append(dict(fold=f["fold"], budget=k, arm=name, dti=float(r["dti"]),
                                  tpw=float(r["tpw"]), fpw=float(r["fpw"]), fnw=float(r["fnw"]),
                                  n_truth=int(r["n_truth"]), emitted=int((p > 0).sum())))
        log(f"holdout fold {f['fold']} done ({time.time() - t0:.0f}s)")

    arms = {}
    for k in budgets:
        for name in extra:
            sub = [c for c in cells if c["arm"] == name and c["budget"] == k]
            pooled = h60d.pooled_dti(sub)
            ci = h60d.bootstrap_ci([c["dti"] for c in sub], n_boot=N_BOOT, seed=SEED)
            rnd = val["instrument1_holdout"]["arms"][f"random|{k}"]["pooled_dti"]
            arms[f"{name}|{k}"] = dict(pooled_dti=round(pooled["dti"], 6),
                                       ci_lo=ci["ci_lo"], ci_hi=ci["ci_hi"], n_folds=len(sub),
                                       withheld_positives=int(pooled["n_truth"]),
                                       mean_emitted=round(float(np.mean(
                                           [c["emitted"] for c in sub])), 1),
                                       lift_over_random=round(pooled["dti"] - rnd, 6))

    out = dict(round="H62-validate-extra-fields", seed=SEED,
               runtime_s=round(time.time() - t0, 1),
               reason=("the hard corroboration intersection is structurally unusable at this "
                       "budget (k^2/n = 185 at k=30,000, n=4,861,502); the joint-confidence "
                       "ranking min(pA,pB) is registered on the same two instruments so the "
                       "promotion decision compares like with like"),
               instrument1_holdout=dict(arms=arms),
               instrument2_revealed=dict(per_field=rows))
    h62.write_json(EV / "h62_validation_extra.json", out)

    # merge into the main receipt so every downstream reader sees one table
    for r in rows:
        names = [x["field"] for x in val["instrument2_revealed"]["per_field"]]
        if r["field"] in names:
            val["instrument2_revealed"]["per_field"][names.index(r["field"])] = r
        else:
            val["instrument2_revealed"]["per_field"].append(r)
    val["instrument1_holdout"]["arms"].update(arms)
    val["registered_corrections"] = [
        dict(id="H62-1",
             registered_utc_date="2026-10-09",
             summary=("The corroboration operator cannot be delivered as a hard intersection: "
                      "two independent thinnings of k dots in a pool of n intersect in k^2/n, "
                      "which is 185 px at k=30,000 and n=4,861,502, and the measured "
                      "intersection at q_conf=0.60 is 92 px. The soft form, ranking on the joint "
                      "confidence min(pA,pB), is registered on both instruments and can promote; "
                      "the hard form is reported as the measured structural negative."))]
    h62.write_json(EV / "h62_validation.json", val)
    log(f"wrote h62_validation_extra.json and merged into h62_validation.json "
        f"({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
