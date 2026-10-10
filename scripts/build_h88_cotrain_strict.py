#!/usr/bin/env python3
"""H88 shipping builder: the PRE-REGISTERED primary rule on the full footprint, written as a downloadable GeoTIFF.

Preconditions (checked, not assumed)
------------------------------------
* ``knowledge/90_h94_protocol_frozen_bytes_from_h88.md`` still matches its pin in ``registry/h94_preregistration.json``.
* ``evidence/h94_holdout.json`` exists and was produced from that protocol (its ``protocol_sha256`` must match).

Output policy (protocol §6)
---------------------------
The file is written regardless of the holdout verdict so that it can be downloaded and audited. The verdict is
copied into the receipt and into the site. A file with a NEGATIVE verdict is never labelled submit-ready.

Container: ``gems52.grid.write_geotiff_portal_exact(..., outside="zero")`` (the only container with every pixel finite
in [0, 1]; IR-H85-004). Placement: ``gems52.nodes.spacing_select`` at 3 px, budget 37,654, 200 m collar on the FULL
catalogue (2 px), the same collar H87 used.

Lane: the protocol's surface check runs on the pre-placement field, and the dot checks run on the final dots, both via
``scripts/audit_uniqueness.py`` (shared ``gems52.gates``).
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import rasterio  # noqa: E402

import run_h88_holdout as H88  # noqa: E402  (same fields, same rank rule, same pin check)
from gems52 import grid, nodes  # noqa: E402
from gems52.gates import lane_uniqueness_report  # noqa: E402

BUDGET = 37654
COLLAR_PX = 2
SAMPLE = H88.SAMPLE
NAME = "h88-cotrain-strict-AB-37654px"
NOTE = "H88 cotrain A-conf/B-abstain stratum, 3px spacing, 200m collar, zeros outside"
SUBMISSION_DIR = ROOT / "submission"
DOWNLOAD_DIR = ROOT / "docs" / "downloads"
EVIDENCE = ROOT / "evidence"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def prior_list() -> list[Path]:
    """Every registry raster, assembled exactly as scripts/audit_uniqueness.py does (census + local globs, byte-deduped)."""
    import glob
    import audit_uniqueness as AU
    import build_h61_submission as B61
    paths, _ = B61.prior_paths(ROOT / "work/h61/prior_fetch_receipt.json", ())
    cands = [Path(p).resolve() for p in paths]
    for pat in AU.PRIOR_GLOBS:
        cands += [Path(p).resolve() for p in sorted(glob.glob(str(ROOT / pat), recursive=True))]
    seen, out = set(), []
    for p in cands:
        if not p.exists():
            continue
        h = sha256_file(p)
        if h in seen:
            continue
        seen.add(h)
        out.append(p)
    return out


def main() -> None:
    t0 = time.time()
    pin = H88.check_pin()
    holdout_path = EVIDENCE / "h94_holdout.json"
    holdout = json.loads(holdout_path.read_text())
    if holdout.get("protocol_sha256") != pin["sha256"]:
        raise SystemExit("evidence/h94_holdout.json was not produced from the pinned protocol")

    with rasterio.open(H88.LABELS) as ds, rasterio.open(SAMPLE) as ref:
        labels = ds.read(1)
        domain = np.isfinite(ref.read(1))
    cat = labels == 1
    valid = H88.H87.footprint_all_bands(str(H88.FEATURES)) & domain

    fields, rA, rB, strata, _ = H88.build_fields(valid)
    P = fields[H88.PRIMARY]
    P_unit = (P / 2.0).astype(np.float32)          # score in [0, 2] -> [0, 1]; rank-invariant
    assert P_unit.min() >= 0.0 and P_unit.max() <= 1.0

    # ---- surface check BEFORE placement (protocol §1) -------------------------------------------------
    priors = prior_list()
    surface = lane_uniqueness_report(P_unit, valid, [str(p) for p in priors], sample=str(SAMPLE), phase="surface")
    rows = surface.pop("per_prior", [])
    log_surface = dict(priors=len(priors), report={k: v for k, v in surface.items() if not isinstance(v, (list, dict))},
                       offenders=[str(r["path"]) for r in rows if r.get("rank_duplicate") or r.get("near_duplicate")])
    print("surface (pre-placement):", json.dumps(log_surface, default=float)[:800], flush=True)

    # ---- placement on the full footprint ------------------------------------------------------------
    vd = ndi.distance_transform_edt(~cat)
    allowed = valid & ~cat & (vd > COLLAR_PX)
    em = nodes.spacing_select(P, allowed, BUDGET, min_px=3.0)
    n_spaced = int(em.sum())
    fallback = 0
    if n_spaced < BUDGET:
        fallback = BUDGET - n_spaced
        extra = nodes.top_k_mask(P, allowed & ~em, fallback)
        em = em | extra
    emission = em.astype(np.float32)
    assert int(emission.sum()) == BUDGET, int(emission.sum())
    assert not np.any((emission > 0) & ~valid)
    assert not np.any((emission > 0) & cat)

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    fname = f"gems52-{NAME}-{ts}.tif"
    out_docs = DOWNLOAD_DIR / fname
    out_sub = SUBMISSION_DIR / fname
    rec = grid.write_geotiff_portal_exact(out_docs, emission, valid, SAMPLE, outside="zero")
    out_sub.write_bytes(out_docs.read_bytes())

    zp = out_docs.with_suffix(".zip")
    with zipfile.ZipFile(zp, "w", compression=zipfile.ZIP_DEFLATED) as z:
        zi = zipfile.ZipInfo(out_docs.name, date_time=(2026, 10, 10, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, out_docs.read_bytes())
    with zipfile.ZipFile(zp) as z:
        if z.namelist() != [out_docs.name] or z.read(out_docs.name) != out_docs.read_bytes():
            raise IOError("single-TIFF ZIP round-trip failed")

    with rasterio.open(out_docs) as src:
        arr = src.read(1)
        meta = dict(count=src.count, dtype=src.dtypes[0], crs=str(src.crs), shape=list(src.shape),
                    transform=[float(v) for v in src.transform][:6], nodata=src.nodata)
    receipt = dict(
        round="H88", file=out_docs.name, submission_name=NAME, note=NOTE, note_chars=len(NOTE),
        file_sha256=sha256_file(out_docs), bytes=out_docs.stat().st_size,
        zip_file=zp.name, zip_sha256=sha256_file(zp),
        mirror_submission_copy=str(out_sub.relative_to(ROOT)),
        holdout_verdict=holdout["decision"]["verdict"], holdout_reason=holdout["decision"]["reason"],
        primary_rule="P = rank_A + 1.0*[rank_A>=0.75 & rank_B<=0.25] (protocol §3)",
        strata_px=strata, placed=int(emission.sum()), placed_by_spacing=n_spaced, fallback_dots=fallback,
        spacing_stats=nodes.spacing_stats(em.astype(bool)),
        values=dict(unique=[0.0, 1.0] if np.unique(arr).size == 2 else [float(v) for v in np.unique(arr)],
                    finite_all=bool(np.isfinite(arr).all()), min=float(arr.min()), max=float(arr.max()),
                    in_0_1=bool(arr.min() >= 0.0 and arr.max() <= 1.0)),
        container=dict(meta, outside="zero", portal_exact=rec.get("portal_exact", True)),
        surface_pre_placement=log_surface,
        status="research-only; local format validation is not organiser acceptance; "
               "HOLDOUT verdict decides SUBMIT (see knowledge/81)",
        approved_for_weekly_slot=False, submission_slots_used=0,
        elapsed_seconds=round(time.time() - t0, 1),
    )
    (EVIDENCE / "h94_build.json").write_text(json.dumps(receipt, indent=2, default=float) + "\n")
    print(json.dumps({k: receipt[k] for k in ("file", "file_sha256", "placed", "fallback_dots", "holdout_verdict")}),
          flush=True)


if __name__ == "__main__":
    main()
