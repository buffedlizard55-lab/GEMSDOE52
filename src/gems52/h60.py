"""H60 — two-view co-training round on the manifest-pinned competition bytes.

Design contract (everything here is measured, never asserted)
-------------------------------------------------------------
View A = potential-field / subsurface: magnetics (bands 1, 2, 3, 9, 14), gravity
(5, 11, 13, 18), geodetic strain (4, 7, 8), seismicity (10, 16), depth to basement
(15), conductivity (17).

View B = surface: detrended elevation (12) and its slope (19), plus band 6.  Band 6's
TIFF tag claims a magnetic tilt derivative; the repository measured Spearman +1.0000
against the independently reduced USGS GeoDAWN total-count grid (IR-52-019), so it is
an aeroradiometric channel and belongs in the surface view.  Putting a radiometric
band inside the potential-field view inflates every A/B correlation this project has
ever taken.

Both views also get the *derived* layers that this round preregisters
(``knowledge/25_hypotheses_H60_preregistered.md``): oriented ridge energies for the two
Basin-and-Range strike sets, strike-projected basement steps, and intersection nodes of
the two lineament sets.  Those are new layers, not re-used ones.

Nothing in this module reads a prior submission raster or a distance-to-prior field.
The only labels used are ``data/labels.tif`` (the published catalogue).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

PIX = 100.0
R_M = 300.0
NODATA = -3.4028234663852886e+38

# --------------------------------------------------------------------------- band plan
# (1-based band index, view, role)  -- the organiser's own TIFF tags, read by
# scripts/prepare_data.py into evidence/band_inventory.json.
BAND_VIEW = {
    1: "A", 2: "A", 3: "A", 4: "A", 5: "A",
    6: "B",                       # radiometric total count (IR-52-019), not a magnetic tilt
    7: "A", 8: "A", 9: "A", 10: "A", 11: "A",
    12: "B",
    13: "A", 14: "A", 15: "A", 16: "A", 17: "A", 18: "A",
    19: "B",
}

# Two strike sets of the northwestern Great Basin.  Azimuth is compass bearing of the
# lineament; the repository recovered 010-020 deg from the credited node cloud
# (knowledge/10 s7) and the transfer set is the classical NW set of the Walker Lane /
# northern Basin and Range boundary.
STRIKE_SETS = {"nne": 15.0, "nw": 315.0}


# --------------------------------------------------------------------------- primitives
def _rank(a: np.ndarray) -> np.ndarray:
    """Rank-encode a band to [0,1] over its finite pixels; NaN stays NaN.

    Band 10 reaches 4.96e6 m inside a 492 km diagonal grid (IR-R4-002), so any layer
    that used it as metres would silently mishandle those pixels.  Rank encoding is
    monotone and bounded, and it is what every learner here sees.
    """
    out = np.full(a.shape, np.nan, np.float32)
    ok = np.isfinite(a)
    if ok.sum() == 0:
        return out
    v = a[ok]
    order = np.argsort(v, kind="stable")
    r = np.empty(v.size, np.float64)
    r[order] = np.arange(v.size, dtype=np.float64)
    # average ranks for ties, so a constant band does not become a spatial pattern
    sv = v[order]
    i = 0
    while i < sv.size:
        j = i
        while j + 1 < sv.size and sv[j + 1] == sv[i]:
            j += 1
        if j > i:
            r[order[i:j + 1]] = 0.5 * (i + j)
        i = j + 1
    out[ok] = (r / max(v.size - 1, 1)).astype(np.float32)
    return out


def _z(a: np.ndarray) -> np.ndarray:
    """Regional standardisation: (x - median) / IQR-scale, over finite pixels."""
    ok = np.isfinite(a)
    if ok.sum() < 100:
        return np.zeros_like(a, dtype=np.float32)
    v = a[ok]
    med = float(np.median(v))
    lo, hi = np.percentile(v, [2, 98])
    scale = max(float(hi - lo) / 4.0, 1e-9)
    return np.clip((a - med) / scale, -8.0, 8.0).astype(np.float32)


def _grad(a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    gy, gx = np.gradient(np.nan_to_num(a, nan=0.0), PIX)
    return gy.astype(np.float32), gx.astype(np.float32)


def _oriented_energy(a: np.ndarray, azimuth_deg: float, sigmas=(1.0, 2.0, 4.0)) -> np.ndarray:
    """Ridge/edge energy *perpendicular* to a lineament of given compass azimuth.

    A lineament striking at compass azimuth ``theta`` has its normal at ``theta + 90``.
    The directional derivative along that normal is the response; the maximum over a
    small scale bank is what survives the 100 m resampling of an airborne survey.
    Returned as the multi-scale maximum of |directional derivative| after regional
    centring, which is scale-free and comparable between bands.
    """
    th = np.deg2rad(azimuth_deg + 90.0)
    ny, nx = np.cos(th), np.sin(th)      # image y is north-up (row index increases south)
    out = np.full(a.shape, np.nan, np.float32)
    finite = np.isfinite(a)
    b = np.where(finite, a, np.nan)
    acc = np.zeros(a.shape, np.float32)
    any_ok = np.zeros(a.shape, bool)
    for s in sigmas:
        sm = ndimage.gaussian_filter(np.nan_to_num(b, nan=0.0), s)
        w = ndimage.gaussian_filter(finite.astype(np.float32), s)
        sm = np.where(w > 0.2, sm / np.maximum(w, 1e-3), 0.0)
        gy, gx = np.gradient(sm, PIX)
        d = (gy * (-ny) + gx * nx)       # -ny: row axis points south
        acc = np.maximum(acc, np.abs(d).astype(np.float32))
        any_ok |= finite
    out[any_ok] = acc[any_ok]
    return out


def _curvatures(dem: np.ndarray) -> dict[str, np.ndarray]:
    """Profile / plan / mean curvature of the detrended elevation, in 1/m units."""
    z = np.nan_to_num(dem, nan=0.0)
    zy, zx = np.gradient(z, PIX)
    zyy, zyx = np.gradient(zy, PIX)
    zxy, zxx = np.gradient(zx, PIX)
    p = 1.0 + zx ** 2
    q = 1.0 + zy ** 2
    prof = -(p * zyy - 2 * zx * zy * zxy + q * zxx) / (p + q) ** 1.5
    plan = -(q * zyy - 2 * zx * zy * zxy + p * zxx) / (p + q) ** 1.5
    mean = -(p * zyy + q * zxx) / (2 * (p + q) ** 1.5)
    return dict(profile=prof.astype(np.float32), plan=plan.astype(np.float32),
                mean=mean.astype(np.float32))


# --------------------------------------------------------------------------- layer plan
def layer_plan() -> list[dict]:
    """The full, ordered layer plan.  Asserted counts keep a future edit honest."""
    L: list[dict] = []

    def add(name, view, kind, band=None, note=""):
        L.append(dict(name=name, view=view, kind=kind, band=band, note=note))

    # --- raw bands, rank-encoded (band 10 needs it, the rest are unaffected) -----
    for b in sorted(BAND_VIEW):
        add(f"b{b:02d}_rank", BAND_VIEW[b], "raw", b)
    # --- potential-field edges (View A) ------------------------------------------
    for b in (2, 13, 14, 15, 17):
        add(f"b{b:02d}_gradmag", "A", "edge", b, "isotropic horizontal-gradient magnitude")
    add("b15_step_nne", "A", "H60-3", 15, "strike-projected basement step, NNE set")
    add("b15_step_nw", "A", "H60-3", 15, "strike-projected basement step, NW set")
    add("b13_step_nne", "A", "H60-3", 13, "strike-projected gravity step, NNE set")
    add("b02_ridge_nne", "A", "H60-2", 2, "RTP ridge energy along the NNE set")
    add("b02_ridge_nw", "A", "H60-2", 2, "RTP ridge energy along the NW set")
    add("b14_ridge_nne", "A", "H60-2", 14, "TMI ridge energy along the NNE set")
    add("b05_ridge_nne", "A", "H60-2", 5, "gravity-slope ridge energy along the NNE set")
    add("b17_ridge_nne", "A", "H60-2", 17, "conductivity ridge energy along the NNE set")
    # --- surface layers (View B) -------------------------------------------------
    add("b12_slope", "B", "surface", 12)
    add("b12_aspect_sin", "B", "surface", 12)
    add("b12_aspect_cos", "B", "surface", 12)
    add("b12_curv_profile", "B", "surface", 12)
    add("b12_curv_plan", "B", "surface", 12)
    add("b12_curv_mean", "B", "surface", 12)
    add("b12_openness", "B", "surface", 12, "8-ray positive openness, 5 px horizon")
    add("b06_gradmag", "B", "edge", 6, "aeroradiometric total-count gradient magnitude")
    add("b06_ridge_nne", "B", "H60-2", 6, "TC ridge energy along the NNE set")
    add("b06_ridge_nw", "B", "H60-2", 6, "TC ridge energy along the NW set")
    add("b19_ridge_nne", "B", "H60-2", 19, "detrended-slope ridge energy along the NNE set")
    add("b12_ridge_nne", "B", "H60-2", 12, "detrended-elevation ridge energy along the NNE set")
    add("b12_ridge_nw", "B", "H60-2", 12, "detrended-elevation ridge energy along the NW set")
    # --- H60-4: intersection of the two lineament sets ---------------------------
    add("node_nne_x_nw", "B", "H60-4", None,
        "product of the two strike-set lineament densities (dilational node proxy)")
    add("node_nne_x_nw_A", "A", "H60-4", None,
        "same node proxy built from the potential-field ridge energies")
    # NOTE: distance-to-catalogue is deliberately NOT a model layer.  It is legitimate
    # at inference time, but a hide-and-recover fold cannot make it fold-safe without
    # rebuilding it per fold, and a leaky context feature would inflate View A's blocked
    # AUC and destroy the A/B comparison.  The runner uses it only for the emission mask
    # and the 200 m ring gate, never as a predictor.
    return L


def assert_plan(L: list[dict]) -> tuple[int, int]:
    na = sum(1 for x in L if x["view"] == "A")
    nb = sum(1 for x in L if x["view"] == "B")
    names = [x["name"] for x in L]
    if len(names) != len(set(names)):
        raise ValueError("duplicate layer names in the plan")
    if na < 20 or nb < 12:
        raise ValueError(f"plan collapsed: {na} A / {nb} B layers")
    return na, nb


# --------------------------------------------------------------------------- build
def build_stack(features: str | Path, out_dir: str | Path, log=print) -> dict:
    """Compute every layer once into a float16 memmap; returns the manifest."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = layer_plan()
    na, nb = assert_plan(plan)
    L = len(plan)
    with rasterio.open(features) as src:
        H, W = src.height, src.width
        nband = src.count
        bands = {i: src.read(i).astype(np.float32) for i in range(1, nband + 1)}
    for i in range(1, nband + 1):
        b = bands[i]
        b[~np.isfinite(b)] = np.nan
        b[b < -1e38] = np.nan
    log(f"[layers] {H}x{W}, {nband} bands read; plan = {L} layers ({na} A / {nb} B)")

    fp = np.memmap(out_dir / "stack.f16", dtype=np.float16, mode="w+", shape=(L, H, W))
    idx = {p["name"]: i for i, p in enumerate(plan)}
    written: set[str] = set()

    def put(name, arr):
        # A memmap is zero-filled on creation, so a layer nobody writes reads back as a
        # perfectly finite, perfectly useless field of zeros.  b06_gradmag did exactly
        # that on the first build.  Track every write and fail loudly at the end.
        if name not in idx:
            raise KeyError(f"{name} is written but not in the layer plan")
        fp[idx[name]] = np.asarray(arr, np.float32)
        written.add(name)

    for b in sorted(BAND_VIEW):
        put(f"b{b:02d}_rank", _rank(bands[b]))

    dem = bands[12]
    curv = _curvatures(dem)
    for k, v in curv.items():
        put(f"b12_curv_{k}", _z(v))
    zy, zx = np.gradient(np.nan_to_num(dem, nan=0.0), PIX)
    put("b12_slope", _z(np.hypot(zy, zx)))
    put("b12_aspect_sin", np.sin(np.arctan2(zx, -zy)).astype(np.float32))
    put("b12_aspect_cos", np.cos(np.arctan2(zx, -zy)).astype(np.float32))

    # positive openness over a 5 px horizon (a scarp faces away from the local horizon)
    z = np.nan_to_num(dem, nan=0.0)
    best = np.full(z.shape, -np.inf, np.float32)
    for dy in range(-5, 6):
        for dx in range(-5, 6):
            d = np.hypot(dy, dx)
            if d < 1 or d > 5.001:
                continue
            sh = ndimage.shift(z, (dy, dx), order=1, mode="nearest")
            best = np.maximum(best, (sh - z) / (d * PIX))
    put("b12_openness", _z(best))

    for b in (2, 6, 13, 14, 15, 17):
        gy, gx = np.gradient(np.nan_to_num(bands[b], nan=0.0), PIX)
        put(f"b{b:02d}_gradmag", _z(np.hypot(gy, gx)))

    # oriented ridge energies
    ridge_src = {("A", 2): bands[2], ("A", 14): bands[14], ("A", 5): bands[5],
                 ("A", 17): bands[17], ("B", 6): bands[6], ("B", 19): bands[19],
                 ("B", 12): dem}
    ridge_store: dict[tuple, np.ndarray] = {}
    for (view, b), arr in ridge_src.items():
        for tag, az in STRIKE_SETS.items():
            nm = f"b{b:02d}_ridge_{tag}"
            if any(p["name"] == nm for p in plan):
                e = _z(_oriented_energy(arr, az))
                put(nm, e)
                ridge_store[(view, tag)] = e if (view, tag) not in ridge_store \
                    else np.maximum(ridge_store[(view, tag)], np.nan_to_num(e, nan=0.0))

    # strike-projected basement / gravity steps (H60-3): second difference *along* the
    # strike direction, which cancels a regional dip that swamps the isotropic version.
    for b, tag_out in ((15, "b15_step"), (13, "b13_step")):
        arr = np.nan_to_num(bands[b], nan=0.0)
        for tag, az in (("nne", STRIKE_SETS["nne"]), ("nw", STRIKE_SETS["nw"])):
            if not any(p["name"] == f"{tag_out}_{tag}" for p in plan):
                continue
            th = np.deg2rad(az)
            sy, sx = -np.cos(th), np.sin(th)          # unit vector along strike, row=south
            d1 = ndimage.shift(arr, (sy, sx), order=1, mode="nearest")
            d2 = ndimage.shift(arr, (-sy, -sx), order=1, mode="nearest")
            step = np.abs(d1 + d2 - 2 * arr) / (PIX ** 2)
            put(f"{tag_out}_{tag}", _z(step))

    # H60-4: intersection nodes = product of the two strike-set ridge fields
    def _unit(v):
        v = np.nan_to_num(np.asarray(v, np.float32), nan=0.0)
        v = np.clip(v, 0, None)
        m = np.percentile(v[v > 0], 99) if (v > 0).any() else 1.0
        return np.clip(v / max(m, 1e-9), 0, 1).astype(np.float32)

    for view, nm in (("B", "node_nne_x_nw"), ("A", "node_nne_x_nw_A")):
        a = ridge_store.get((view, "nne"))
        b = ridge_store.get((view, "nw"))
        if a is None:
            a = np.zeros((H, W), np.float32)
        if b is None:
            # the A set only carries an NNE ridge in the plan; fall back to the
            # isotropic gradient magnitude so the layer is defined, and say so.
            gy, gx = np.gradient(np.nan_to_num(bands[14], nan=0.0), PIX)
            b = _z(np.hypot(gy, gx))
        prod = _unit(a) * _unit(b)
        put(nm, _z(ndimage.gaussian_filter(prod, 2.0)))

    missing = [p["name"] for p in plan if p["name"] not in written]
    if missing:
        raise RuntimeError(f"{len(missing)} planned layers were never written: {missing}")
    fp.flush()
    del bands
    man = dict(height=H, width=W, layers=[p["name"] for p in plan],
               views={p["name"]: p["view"] for p in plan},
               kinds={p["name"]: p["kind"] for p in plan},
               n_A=na, n_B=nb, dtype="float16", path=str(out_dir / "stack.f16"))
    (Path(out_dir) / "manifest.json").write_text(json.dumps(man, indent=1))
    log(f"[layers] wrote {man['path']}")
    return man


class Stack:
    """Row-window reader over the float16 layer memmap."""

    def __init__(self, work_dir: str | Path):
        self.man = json.loads((Path(work_dir) / "manifest.json").read_text())
        self.H, self.W = self.man["height"], self.man["width"]
        self.names = self.man["layers"]
        self.views = self.man["views"]
        self.fp = np.memmap(Path(work_dir) / "stack.f16", dtype=np.float16, mode="r",
                            shape=(len(self.names), self.H, self.W))

    def view_names(self, view: str) -> list[str]:
        return [n for n in self.names if self.views[n] == view]

    def rows(self, view: str, rr: np.ndarray, cc: np.ndarray) -> np.ndarray:
        ns = self.view_names(view)
        flat = rr.astype(np.int64) * self.W + cc.astype(np.int64)
        out = np.empty((rr.size, len(ns)), np.float32)
        for j, n in enumerate(ns):
            out[:, j] = np.asarray(self.fp[self.names.index(n)].ravel()[flat], np.float32)
        return out

    def block(self, view: str, r0: int, r1: int) -> np.ndarray:
        ns = self.view_names(view)
        idx = [self.names.index(n) for n in ns]
        return np.asarray(self.fp[idx][:, r0:r1, :], np.float32)
