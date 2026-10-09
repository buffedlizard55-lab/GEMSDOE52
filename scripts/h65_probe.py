#!/usr/bin/env python3
"""H65 feasibility probe: measure the legal set, the credited core, the lane caps and the novel pool.

Everything here is measured from restored, SHA-256-verified bytes. No model is fitted, so this is a
measurement pass, not one of the brief's three experiments.
"""
from __future__ import annotations
import json, sys, hashlib, time
from pathlib import Path
import numpy as np, rasterio
from scipy import ndimage as ndi

ROOT = Path("/home/user/GEMSDOE52")
sys.path.insert(0, str(ROOT / "src"))
from gems52 import gates
from gems52.grid import SHAPE, TRANSFORM, CRS_EPSG

W = ROOT / "work/h65"
W.mkdir(parents=True, exist_ok=True)
t0 = time.time()
def log(*a): print(f"[{time.time()-t0:7.1f}s]", *a, flush=True)

# ---------- grid, catalogue, legal set -----------------------------------------------------------
with rasterio.open(ROOT/"data/labels.tif") as s:
    cat = s.read(1) > 0
with rasterio.open(ROOT/"data/sample_submission.tif") as s:
    sample_finite = np.isfinite(s.read(1))
log("catalogue px", int(cat.sum()), "sample finite", int(sample_finite.sum()))

vp = W/"valid.npy"
if vp.exists():
    valid = np.load(vp)
else:
    valid = None
    with rasterio.open(ROOT/"data/training_features.tif") as s:
        for i in range(1, s.count+1):
            a = s.read(i)
            ok = np.isfinite(a) & (a > -1e38)
            valid = ok if valid is None else (valid & ok)
            del a, ok
    valid = valid & sample_finite
    np.save(vp, valid)
log("valid (all 19 bands finite AND sample finite)", int(valid.sum()))

ed = ndi.distance_transform_edt(~cat, sampling=100.0)
legal = valid & (~cat) & (ed > 200.0 + 1e-6)          # off-catalogue and >200 m from any mapped trace
log("eligible/off-catalogue", int((valid & ~cat).sum()), " legal (>200 m ring excluded)", int(legal.sum()))

# ---------- the measured credited core P1 = A & C ------------------------------------------------
def load(p):
    with rasterio.open(str(p)) as s:
        a = s.read(1)
    return np.isfinite(a) & (a > 0)
A = load(ROOT/"data/reference/h33-2-b2-zeros.tif")
C = load(ROOT/"data/scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif")
B = load(ROOT/"data/scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif")
E = load(ROOT/"data/scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif")
core = A & C
log("|A|",int(A.sum()),"|C|",int(C.sum()),"|B|",int(B.sum()),"|E|",int(E.sum()),"|core=A&C|",int(core.sum()))
log("core inside legal:", int((core & legal).sum()), "of", int(core.sum()),
    " core outside legal:", int((core & ~legal).sum()))
core = core & legal
np.save(W/"core.npy", core); np.save(W/"legal.npy", legal); np.save(W/"valid.npy", valid)
# internal spacing of the core
yy, xx = np.nonzero(core)
d_core = ndi.distance_transform_edt(~core, sampling=1.0)
log("core min separation probe: pixels whose nearest other core pixel is <=1px:",
    int((ndi.grey_dilation(core.astype(np.uint8), size=(3,3)) & core).sum()))

# ---------- prior census -------------------------------------------------------------------------
disk = gates._disk(gates.NEAR_RADIUS_PX)
paths = sorted((W/"priors").glob("*.tif"))
for extra in ("submission", "data/scored", "data/reference"):
    paths += sorted((ROOT/extra).glob("*.tif"))
log("prior paths found:", len(paths))
seen, priors = set(), []
for p in paths:
    if p.stat().st_size < 1000: continue
    if p.name in ("labels.tif",) or p.name.startswith("sample_submission") or "training_features" in p.name: continue
    priors.append(p)
log("prior candidates:", len(priors))

rows = []
union_binding = np.zeros(SHAPE, bool)
consensus = np.zeros(SHAPE, np.uint16)
n_probe = 0
MARGIN = 0.67                      # safety buffer below the brief's literal 0.70
for i, p in enumerate(priors):
    try:
        with rasterio.open(p) as ds:
            if ds.count != 1 or (ds.shape, ds.crs, ds.transform) != (SHAPE, rasterio.crs.CRS.from_string(CRS_EPSG), None):
                pass
            if ds.shape != SHAPE or str(ds.crs) != CRS_EPSG or tuple(ds.transform)[:6] != TRANSFORM:
                continue
            old = gates.canonical(ds.read(1))
    except Exception as exc:
        rows.append(dict(path=str(p), error=f"{type(exc).__name__}: {exc}")); continue
    dig = hashlib.sha256(old.tobytes()).hexdigest()
    if dig in seen: continue
    seen.add(dig)
    binary = bool(np.all((old == 0) | (old == 1)))
    proposal = (old > 0) if binary else (old >= 0.5)
    npos = int(proposal.sum())
    if npos == 0: continue
    halo = ndi.binary_dilation(proposal, structure=disk)
    cov = float((halo & legal).sum()) / float(max(int(legal.sum()), 1))
    probe = cov >= gates.PROBE_COVERAGE
    n_probe += int(probe)
    base = int((halo & core).sum())
    consensus += (halo & legal).astype(np.uint16)
    rows.append(dict(path=str(p), decoded_sha256=dig, prior_proposals=npos, binary=bool(binary),
                     coverage_3px_of_legal=round(cov, 5), universal_coverage_probe=bool(probe),
                     core_near_fraction=round(base / max(int(core.sum()), 1), 5), core_near=base))
    if i % 50 == 0: log(f"  prior {i+1}/{len(priors)} distinct={len(seen)} probes={n_probe}")
log("distinct priors:", len(seen), "universal-coverage probes:", n_probe,
    "informative:", len(seen) - n_probe)
np.save(W/"consensus.npy", consensus)

info = [r for r in rows if "error" not in r and not r["universal_coverage_probe"]]
info.sort(key=lambda r: -r["core_near_fraction"])
log("top 18 informative priors by core-near fraction:")
for r in info[:18]:
    log(f"   {r['core_near_fraction']:.4f} core_near={r['core_near']:6d} cov={r['coverage_3px_of_legal']:.3f} "
        f"npos={r['prior_proposals']:7d} {Path(r['path']).name[:66]}")

# ---------- lane arithmetic ----------------------------------------------------------------------
n_core = int(core.sum())
out = dict(n_core=n_core, n_distinct_priors=len(seen), n_probes=n_probe, n_informative=len(seen)-n_probe)
for margin in (0.70, 0.67, 0.65, 0.62, 0.60):
    Smin = n_core / margin
    out[f"S_min_at_margin_{margin}"] = int(np.ceil(Smin))
    out[f"n_novel_min_at_margin_{margin}"] = int(np.ceil(Smin)) - n_core
    binding = [r for r in info if r["core_near"] > margin * Smin * 0.999]
    out[f"n_binding_at_margin_{margin}"] = len(binding)
log(json.dumps({k: v for k, v in out.items()}, indent=1))

# ---------- novel pools --------------------------------------------------------------------------
for margin in (0.67, 0.62):
    Smin = int(np.ceil(n_core / margin))
    cap = margin * Smin
    binding = [r for r in info if r["core_near"] >= cap - 1]
    ub = np.zeros(SHAPE, bool)
    for r in binding:
        with rasterio.open(r["path"]) as ds:
            old = gates.canonical(ds.read(1))
        prop = (old > 0) if bool(np.all((old == 0) | (old == 1))) else (old >= 0.5)
        ub |= ndi.binary_dilation(prop, structure=disk)
    pool_bind = legal & ~ub & ~ndi.binary_dilation(core, structure=disk)
    allinfo_halo = np.zeros(SHAPE, bool)
    for r in info:
        with rasterio.open(r["path"]) as ds:
            old = gates.canonical(ds.read(1))
        prop = (old > 0) if bool(np.all((old == 0) | (old == 1))) else (old >= 0.5)
        allinfo_halo |= ndi.binary_dilation(prop, structure=disk)
    pool_exact = legal & ~allinfo_halo
    out[f"margin_{margin}"] = dict(S_min=Smin, cap=cap, n_binding=len(binding),
        binding_paths=[Path(r["path"]).name for r in binding],
        novel_pool_avoiding_binding=int(pool_bind.sum()),
        novel_pool_exactly_novel_vs_all_informative=int(pool_exact.sum()))
    log(f"margin {margin}: S_min={Smin} cap={cap:.0f} binding={len(binding)} "
        f"pool_avoid_binding={int(pool_bind.sum())} pool_exact_novel={int(pool_exact.sum())}")
    np.save(W/f"pool_bind_{int(margin*100)}.npy", pool_bind)
np.save(W/f"pool_exact.npy", pool_exact)

(W/"probe.json").write_text(json.dumps(out, indent=1, default=str))
(W/"prior_rows.json").write_text(json.dumps(rows, indent=1, default=str))
log("PROBE_DONE")
