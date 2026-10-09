#!/usr/bin/env python3
"""R5 stage 1 -- build the six-family lineament detector on the restored, SHA-pinned bytes.

Usage
-----
    python scripts/run_r5_traces.py [--families mag,grav,...] [--tau 0.90,0.95,0.99]

Writes, under ``work/r5/`` (git-ignored):

    valid.npy                     footprint intersection of the 19 organiser bands
    fam_<name>.npz                resp / theta / agree per family (float32 / float32 / int8)
    trace_<name>_<tau>.npy        one-pixel thinned trace mask per family and threshold
    corrobor_<tau>.npy            how many families put a trace within 1 px of each pixel
    strike_<tau>.npy              array-convention strike at each corroborated trace pixel
    traces_receipt.json           sizes, timings, per-family pixel counts, azimuth histogram

Every number printed here is recomputed from the arrays on disk at the end and written into the
receipt; the log is not the record.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52_r5 import layers as L          # noqa: E402
from gems52_r5 import traces as T          # noqa: E402

WORK = ROOT / "work" / "r5"


def build_families(valid: np.ndarray, families: list[str], log) -> dict:
    cache: dict = {}
    out = {}
    for fam in families:
        t0 = time.time()
        log(f"[family] {fam}: layers {L.family_layers(fam)}")
        f = T.family_response(fam, valid, cache=cache, log=log)
        np.savez_compressed(WORK / f"fam_{fam}.npz", resp=f["resp"], theta=f["theta"],
                            agree=f["agree"])
        log(f"[family] {fam} done in {time.time() - t0:.1f}s; "
            f"resp p99={np.percentile(f['resp'][valid], 99):.4f}")
        out[fam] = f
        # a 3.9 GB box: keep at most two families of float32 alive, the rest live on disk
        if len(cache) > 8:
            cache.clear()
    return out


def reload_families(families: list[str]) -> dict:
    out = {}
    for fam in families:
        z = np.load(WORK / f"fam_{fam}.npz")
        out[fam] = dict(family=fam, resp=z["resp"], theta=z["theta"], agree=z["agree"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--families", default=",".join(L.FAMILIES))
    ap.add_argument("--tau", default="0.90,0.95,0.99")
    ap.add_argument("--tol-px", type=int, default=1)
    ap.add_argument("--reuse", action="store_true",
                    help="reload cached family npz instead of recomputing them")
    args = ap.parse_args()
    families = [f for f in args.families.split(",") if f]
    taus = [float(t) for t in args.tau.split(",")]
    WORK.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)          # noqa: E731

    t0 = time.time()
    vpath = WORK / "valid.npy"
    if vpath.exists():
        valid = np.load(vpath)
        log(f"[footprint] cached {int(valid.sum())} px")
    else:
        valid = L.footprint()
        np.save(vpath, valid)
        log(f"[footprint] {int(valid.sum())} px in {time.time() - t0:.1f}s")

    if args.reuse and all((WORK / f"fam_{f}.npz").exists() for f in families):
        fams = reload_families(families)
        log(f"[families] reused {len(fams)} cached family responses")
    else:
        fams = build_families(valid, families, log)
    receipt = dict(footprint_px=int(valid.sum()), families=families, taus=taus,
                   tol_px=args.tol_px, seconds=time.time() - t0, per_family={}, per_tau={})
    for name, f in fams.items():
        receipt["per_family"][name] = dict(
            layers=L.family_layers(name),
            resp_p50=float(np.percentile(f["resp"][valid], 50)),
            resp_p99=float(np.percentile(f["resp"][valid], 99)),
            resp_p999=float(np.percentile(f["resp"][valid], 99.9)),
            agree_ge2_px=int((f["agree"] >= 2).sum()))

    for tau in taus:
        tr = {}
        for name, f in fams.items():
            m = T.thinned_trace(f, valid, tau=tau)
            np.save(WORK / f"trace_{name}_{tau:g}.npy", m)
            tr[name] = m
            receipt["per_family"][name][f"trace_px_tau{tau:g}"] = int(m.sum())
        corr = T.corroboration(tr, tol_px=args.tol_px)
        np.save(WORK / f"corrobor_{tau:g}.npy", corr)
        strike = T.strike_map(fams, tr)
        np.save(WORK / f"strike_{tau:g}.npy", strike)
        hist = np.bincount(corr[valid].ravel(), minlength=len(families) + 1)
        az = np.degrees(strike[(corr >= 2) & valid])
        az_geo = np.mod(90.0 - az, 180.0) if az.size else np.array([])
        receipt["per_tau"][f"{tau:g}"] = dict(
            corroborated_px_by_family_count=[int(x) for x in hist],
            corroborated_ge2_px=int((corr >= 2).sum()),
            corroborated_ge3_px=int((corr >= 3).sum()),
            azimuth_hist_geo_10deg=[int(x) for x in np.histogram(
                az_geo, bins=np.arange(0, 181, 10))[0]] if az_geo.size else [],
            azimuth_median_geo=float(np.median(az_geo)) if az_geo.size else None,
        )
        log(f"[tau {tau:g}] by #families: {[int(x) for x in hist]}  "
            f"(>=2: {int((corr >= 2).sum())}, >=3: {int((corr >= 3).sum())})")
    # re-read everything we claim, then write the receipt
    for tau in taus:
        c = np.load(WORK / f"corrobor_{tau:g}.npy")
        assert c.shape == valid.shape, "corroboration shape drifted"
        receipt["per_tau"][f"{tau:g}"]["reread_ge2_px"] = int((c >= 2).sum())
    receipt["total_seconds"] = time.time() - t0
    (WORK / "traces_receipt.json").write_text(json.dumps(receipt, indent=1))
    log(f"[receipt] work/r5/traces_receipt.json  total {receipt['total_seconds']:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
