#!/usr/bin/env python3
"""H71 measurement: per-informative-prior 3 px halo coverage of the A-only stratum.

Why: the lane-capped placement stopped at exactly fill = floor(0.70*B) for every budget B,
which happens iff at least one informative prior's 3 px proposal-halo covers (essentially) every
candidate.  This script rebuilds the stratum and measures, per informative prior, the fraction of
(1) the full stratum and (2) the exact-novel stratum subset inside its halo, so the binding
prior(s) are named before any placement decision is amended.
Receipt: evidence/h71_halostats.json.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np                                             # noqa: E402
import rasterio                                                # noqa: E402
from scipy import ndimage as ndi                               # noqa: E402

import run_h61 as base                                         # noqa: E402
import build_h61_submission as b61                             # noqa: E402
from gems52 import gates, structural                           # noqa: E402

WORK = ROOT / "work/h71"
CENSUS = ROOT / "work/h61/prior_fetch_receipt.json"


def log(*a):
    print(*a, flush=True)


def main() -> int:
    store = structural.FeatureStore(ROOT / "work/r2/features")
    eligible = store.valid
    flat, inv, shape = store.flat_idx, store.inverse, eligible.shape
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        sub = ref.read(1)
    sub_finite = np.isfinite(sub) & (sub > -1e38)
    del sub
    with rasterio.open(ROOT / "data/labels.tif") as ds:
        cat = ds.read(1) == 1
    cat_dist = ndi.distance_transform_edt(~cat, sampling=100.0)
    del cat
    h61_th = json.loads((ROOT / "registry/h61_preregistration.json").read_text())["thresholds"]
    folds = list(base.spatial.folds(cat_dist > -1, eligible, buffer_px=81) ) if False else None
    # rebuild exactly as the build does
    with rasterio.open(ROOT / "data/labels.tif") as ds:
        cat = ds.read(1) == 1
    folds = list(base.spatial.folds(cat, eligible, buffer_px=int(h61_th["buffer_px"])))
    mos = {}
    for v in ("A", "B"):
        g = np.full(int(np.prod(shape)), np.nan, np.float32)
        for fold in folds:
            rows = inv[np.flatnonzero(fold["region"].ravel())]
            rows = rows[rows >= 0]
            p = np.load(WORK / f"pred_post_{v}_f{fold['fold']}.npy")
            g[np.flatnonzero(fold["region"].ravel())] = p[rows]
        mos[v] = g.reshape(shape)
        del g
    allowed = eligible & sub_finite & ~cat & (cat_dist > float(json.loads(
        (ROOT / "registry/h71_preregistration.json").read_text())["thresholds"]["catalogue_exclusion_m"]))
    idx = np.flatnonzero(allowed.ravel())
    rankA = np.zeros(shape, np.float32)
    rankB = np.zeros(shape, np.float32)
    rankA.ravel()[idx] = base.pct_rank(mos["A"].ravel()[idx])
    rankB.ravel()[idx] = base.pct_rank(mos["B"].ravel()[idx])
    del mos
    th = json.loads((ROOT / "registry/h71_preregistration.json").read_text())["thresholds"]
    stratum = (rankA >= th["donor_rank_min"]) & (rankB >= th["receiver_rank_interval"][0]) \
        & (rankB <= th["receiver_rank_interval"][1]) & allowed
    log(f"stratum px: {int(stratum.sum())}")

    priors, _pmeta = b61.prior_paths(CENSUS, ("submission",))
    informative, probes = [], []
    union_sup = np.zeros(shape, bool)
    for pp in priors:
        with rasterio.open(pp) as ds_p:
            if ds_p.shape != shape:
                continue
            a = ds_p.read(1)
        sup = np.isfinite(a) & (a > -1e38) & (a > 0)
        del a
        if not sup.any():
            continue
        cov = gates.registry_coverage(sup, eligible, gates.NEAR_RADIUS_PX)
        if cov >= gates.PROBE_COVERAGE:
            probes.append(pp.name)
            continue
        informative.append(pp)
        union_sup |= sup
    novel = stratum & ~union_sup
    log(f"informative {len(informative)}, probes {len(probes)}, exact-novel stratum px {int(novel.sum())}")

    ys_s, xs_s = np.nonzero(stratum)
    ys_n, xs_n = np.nonzero(novel)
    rows = []
    for pp in informative:
        with rasterio.open(pp) as ds_p:
            a = ds_p.read(1)
        sup = np.isfinite(a) & (a > -1e38) & (a > 0)
        del a
        halo = ndi.binary_dilation(sup, structure=gates._disk(gates.NEAR_RADIUS_PX))
        cov_elig = gates.registry_coverage(sup, eligible, gates.NEAR_RADIUS_PX)
        frac_str = float(halo[ys_s, xs_s].mean()) if ys_s.size else 0.0
        frac_nov = float(halo[ys_n, xs_n].mean()) if ys_n.size else 0.0
        rows.append(dict(path=str(pp.name), coverage_3px_eligible=round(cov_elig, 6),
                         halo_frac_of_stratum=round(frac_str, 6),
                         halo_frac_of_exact_novel=round(frac_nov, 6)))
        del sup, halo
    rows.sort(key=lambda r: -r["halo_frac_of_stratum"])
    rec = dict(evidence_class="uniqueness/lane diagnostic, not a score",
               stratum_px=int(stratum.sum()), exact_novel_px=int(novel.sum()),
               n_informative=len(informative), n_probes=len(probes),
               max_halo_frac_stratum=rows[0]["halo_frac_of_stratum"],
               max_halo_frac_exact_novel=max(r["halo_frac_of_exact_novel"] for r in rows),
               n_stratum_blanket_over_070=sum(1 for r in rows if r["halo_frac_of_stratum"] > 0.70),
               n_novel_blanket_over_070=sum(1 for r in rows if r["halo_frac_of_exact_novel"] > 0.70),
               top20_by_stratum=rows[:20], top10_by_exact_novel=sorted(
                   rows, key=lambda r: -r["halo_frac_of_exact_novel"])[:10])
    out = ROOT / "evidence/h71_halostats.json"
    out.write_text(json.dumps(rec, indent=1) + "\n")
    (ROOT / "docs/data/h71_halostats.json").write_text(out.read_text())
    log(json.dumps({k: v for k, v in rec.items() if not isinstance(v, list)}, indent=1))
    for r in rows[:10]:
        log(f"  {r['path'][:60]} elig={r['coverage_3px_eligible']:.4f} "
            f"stratum={r['halo_frac_of_stratum']:.4f} novel={r['halo_frac_of_exact_novel']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
