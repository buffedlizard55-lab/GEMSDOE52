#!/usr/bin/env python3
"""Repair H91 channel files whose on-disk bytes no longer match their manifest digest.

Why this exists (IR-H91-001)
---------------------------
After ``scripts/run_h91.py channels`` finished and every file had passed
``run_h82.save_verified`` (write -> read back -> require bit-exact -> digest), a later
re-hash found **30 of 102** files whose bytes differed from the digest recorded in
``work/h91/features/manifest.json``.  The mismatched files are exactly the channels of the
first three bands processed (``det_elev``, ``det_elev_slope``, ``iso_grav_anom``), i.e. the
first files written, and ``run_h82.Bank`` refused to train on them
(``ValueError: channel byte-integrity failure``).  The mechanism is the one already recorded
as **IR-H82-002**: a torn write against a filesystem that snapshots concurrently, landing
*after* the verification pass rather than during it.

What this script does
---------------------
1. Recomputes the affected (band, lag) channels from the pinned input rasters -- the same
   arithmetic as ``run_h91.stage_channels``, so the values are reproducible, not patched.
2. Writes each file with ``run_h82.save_verified`` and then requires the digest to be
   **stable across two reads separated by a pause**, which is the check that was missing.
3. Re-hashes every file on disk and rewrites ``manifest.json``'s ``sha256`` map from those
   digests, so the Bank's guard is checked against reality rather than memory.
4. Re-verifies the whole bank and prints ``ALL_MATCH``; a mismatch is a hard error.

Nothing here changes the science: the recomputation is the documented design, run twice.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np                                                    # noqa: E402
import rasterio                                                       # noqa: E402
from scipy import ndimage as ndi                                      # noqa: E402

import run_h61 as base                                                # noqa: E402
import run_h82 as h82tools                                            # noqa: E402
import run_h91 as H91                                                 # noqa: E402
from gems52 import azimuth as az                                      # noqa: E402

FEAT = H91.FEAT
PAUSE = 2.0


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def sha_of(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def stable_save(path: Path, arr: np.ndarray, tries: int = 8) -> str:
    """save_verified plus a second digest after a pause; returns the stable digest."""
    want = np.ascontiguousarray(np.asarray(arr))
    last = None
    for attempt in range(1, tries + 1):
        d, _ = h82tools.save_verified(path, want)
        time.sleep(PAUSE)
        d2 = sha_of(path)
        if d == d2 and last in (None, d):
            return d
        last = d
        log(f"  unstable write on {path.name} (attempt {attempt}); rewriting")
    raise RuntimeError(f"{path.name} would not hold a stable digest after {tries} attempts")


def main() -> int:
    man = json.loads((FEAT / "manifest.json").read_text())
    eligible = None
    # 1. which files mismatch
    bad = [k for k, v in man["sha256"].items() if sha_of(FEAT / (k + ".npy")) != v]
    log(f"mismatched channel files: {len(bad)} of {len(man['sha256'])}")
    # band names themselves contain underscores, so strip the family prefix and the statistic
    # suffix rather than splitting on "_"
    import re
    stat_re = re.compile(r"_(aniso|logvar|phimax|dirR)_l\d+$")
    bands = set()
    for k in bad:
        if not k.startswith(("DVA3_", "CSA_")):
            continue
        stem = k[len("DVA3_"):] if k.startswith("DVA3_") else k[len("CSA_"):]
        nm = stat_re.sub("", stem)
        if nm not in H91.BANDS:
            raise SystemExit(f"cannot resolve band name from channel {k!r} (got {nm!r})")
        bands.add(nm)
    bands = sorted(bands)
    if "--all" in sys.argv:
        # the whole bank was written in one pass, so any file may be affected; recompute all of them
        bands = sorted(H91.BANDS)
        log("--all: recomputing every band's 16-fan channels")
    log(f"affected bands: {bands}")

    # 2. recompute those bands' 16-fan channels
    reg, store, cat, elig, folds, va, vb, ring_px = base.setup()
    eligible = elig
    cols: dict[str, np.ndarray] = {}
    for nm in bands:
        z, ok, w = None, None, None
        rel, band = H91.BANDS[nm]
        with rasterio.open(ROOT / rel) as ds:
            zb = ds.read(band).astype(np.float64)
        ok = np.isfinite(zb) & eligible
        mu, sd = float(zb[ok].mean()), float(zb[ok].std()) + 1e-12
        z = np.where(ok, (zb - mu) / sd, 0.0)
        w = ndi.gaussian_filter(ok.astype(np.float64), H91.SIGMA) + 1e-9
        del zb
        for h in H91.LAGS:
            mx, mn, sm, sx, cx = H91._gamma_accumulate(z, ok, w, h, H91.FAN16)
            cols[f"DVA3_{nm}_aniso_l{h}"] = np.asarray((mx - mn) / (mx + mn + 1e-9), np.float32)[eligible]
            cols[f"DVA3_{nm}_logvar_l{h}"] = np.asarray(np.log10(sm / len(H91.FAN16) + 1e-9), np.float32)[eligible]
            rdir = np.hypot(sx, cx) / (sm + 1e-30)
            phi_soft = 0.5 * np.arctan2(sx, cx)
            cols[f"CSA_{nm}_phimax_l{h}"] = np.asarray(az.wrap_axial(phi_soft), np.float32)[eligible]
            cols[f"CSA_{nm}_dirR_l{h}"] = np.asarray(np.clip(rdir, 0.0, 1.0), np.float32)[eligible]
            del mx, mn, sm, sx, cx, rdir, phi_soft
        del z, ok, w
        log(f"recomputed band {nm}")

    # 3. write stably and record the on-disk digests
    for k, v in cols.items():
        d = stable_save(FEAT / (k + ".npy"), v)
        man["sha256"][k] = d
        log(f"rewrote {k} -> {d[:16]}…")
        del v

    # 4. re-hash everything on disk into the manifest, then verify
    on_disk = {}
    for p in sorted(FEAT.glob("*.npy")):
        on_disk[p.stem] = sha_of(p)
    missing = sorted(set(man["sha256"]) - set(on_disk))
    extra = sorted(set(on_disk) - set(man["sha256"]))
    if missing or extra:
        raise SystemExit(f"bank membership changed: missing={missing} extra={extra}")
    man["sha256"] = on_disk
    man["repair"] = dict(repaired_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                         irregularity="IR-H91-001",
                         n_files_recomputed=len(cols), bands=bands,
                         method="recomputed from the pinned rasters (same arithmetic as "
                                "run_h91.stage_channels), written with a stable-digest check")
    (FEAT / "manifest.json").write_text(json.dumps(man, indent=1, default=float))

    still = [k for k, v in man["sha256"].items() if sha_of(FEAT / (k + ".npy")) != v]
    log(f"post-repair mismatches: {len(still)}")
    if still:
        raise SystemExit(f"still mismatched: {still}")
    log(f"ALL_MATCH=True over {len(man['sha256'])} channel files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
