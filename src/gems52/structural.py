"""R2 signed normal persistence: core-data-only, label-free feature construction.

New mechanism: signed gravity/cover gradient anti-alignment across scales, and
cover-conditioned orientation disagreement with the surface. These features are
NOT independent measurements: the basement model may incorporate gravity.
All numerical units of derivatives are per metre on the template's 100 m grid;
the raw band's units are those of the provided data (not invented here).

Gaussian filters use normalized convolution, not zero-filled derivatives at a
footprint boundary. Maximum support is 36 pixels, recorded in the manifest.
Training statistics and histogram bins are fitted inside each training fold by
sklearn; no labels or test normalization are consulted in these transforms.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

A_BANDS = [i for i in range(1, 20) if i not in (12, 19)]
B_BANDS = [12, 19]
SCALES = (1, 3, 8)
SUPPORT_PX = 36


def smooth(a, valid, sigma):
    """Normalized Gaussian smoothing. A constant field stays constant at holes."""
    a = np.asarray(a, np.float32)
    good = np.asarray(valid, bool) & np.isfinite(a) & (a > -1e38)
    num = ndi.gaussian_filter(np.where(good, a, 0), sigma, mode="reflect", truncate=4.0)
    den = ndi.gaussian_filter(good.astype(np.float32), sigma, mode="reflect", truncate=4.0)
    return np.divide(num, den, out=np.zeros_like(num), where=den > 1e-8)


def normals(a, valid, sigma):
    s = smooth(a, valid, sigma)
    gy, gx = np.gradient(s, 100.0, 100.0)
    mag = np.hypot(gx, gy)
    return gx, gy, mag, s


def cosine(ax, ay, bx, by):
    """Signed normal dot product; undefined flat-field direction maps to 0."""
    den = np.hypot(ax, ay) * np.hypot(bx, by)
    return np.clip(np.divide(ax * bx + ay * by, den, out=np.zeros_like(den), where=den > 1e-12), -1, 1)


def coherence(gx, gy, valid, sigma=3):
    xx = smooth(gx * gx, valid, sigma)
    yy = smooth(gy * gy, valid, sigma)
    xy = smooth(gx * gy, valid, sigma)
    return np.clip(np.sqrt((xx - yy) ** 2 + 4 * xy ** 2) / (xx + yy + 1e-12), 0, 1)


def hessian(s):
    """Signed principal curvatures of a smoothed DEM, not absolute ridge scores."""
    gy, gx = np.gradient(s, 100.0, 100.0)
    yy, yx = np.gradient(gy, 100.0, 100.0)
    xy, xx = np.gradient(gx, 100.0, 100.0)
    off = (xy + yx) * 0.5
    root = np.sqrt((xx - yy) ** 2 + 4 * off ** 2)
    return (xx + yy + root) * 0.5, (xx + yy - root) * 0.5


def normal_profile(elevation, valid, sigma=3.0, offset_px=3.0, tangent_px=3.0, offsets_px=None):
    """Local-normal DEM profile features for a paired-shoulder hypothesis.

    The smoothed DEM gradient defines an unoriented local normal (its sign is fixed by
    increasing elevation). Elevations at +/- offset are bilinearly sampled along it. We
    retain the signed cross-normal step, balance of the two center-to-flank changes, and
    persistence of the step while sampling the local tangent. This is a profile transform,
    not a fault probability; roads, drainage and lithologic edges remain confounders.
    """
    from scipy.ndimage import map_coordinates

    gx, gy, magnitude, smooth_dem = normals(elevation, valid, sigma)
    ux = np.divide(gx, magnitude, out=np.zeros_like(gx), where=magnitude > 1e-8)
    uy = np.divide(gy, magnitude, out=np.zeros_like(gy), where=magnitude > 1e-8)
    h, w = elevation.shape
    yy, xx = np.indices((h, w), dtype=np.float32)

    def sample(source, y, x):
        coords = np.stack((y.astype(np.float32, copy=False), x.astype(np.float32, copy=False)))
        return map_coordinates(source, coords, order=1, mode="nearest", prefilter=False)

    offsets = tuple(float(x) for x in (offsets_px if offsets_px is not None else (offset_px,)))
    if not offsets or any(x <= 0 for x in offsets):
        raise ValueError("normal profile offsets must be positive")
    tx, ty = -uy, ux
    result = []
    for distance_px in offsets:
        z_plus = sample(smooth_dem, yy + distance_px * uy, xx + distance_px * ux)
        z_minus = sample(smooth_dem, yy - distance_px * uy, xx - distance_px * ux)
        # Remove the local first-order plane so a uniform hillslope does not score as a break.
        linear_change = distance_px * 100.0 * magnitude
        signed_step = z_plus - z_minus - 2.0 * linear_change
        plus_flank = z_plus - smooth_dem - linear_change
        minus_flank = smooth_dem - z_minus - linear_change
        pair_denominator = np.abs(plus_flank) + np.abs(minus_flank)
        pair_balance = np.divide(np.abs(plus_flank - minus_flank), pair_denominator,
                                 out=np.zeros_like(pair_denominator), where=pair_denominator > 1e-3)
        paired_flank = np.minimum(np.abs(plus_flank), np.abs(minus_flank))

        # A single isolated break is downweighted by averaging its detrended step along strike.
        persistence = np.abs(signed_step).astype(np.float32)
        for tangent_distance in (1.0, tangent_px):
            persistence += (np.abs(sample(signed_step, yy + tangent_distance * ty, xx + tangent_distance * tx)) +
                            np.abs(sample(signed_step, yy - tangent_distance * ty, xx - tangent_distance * tx))) * 0.5
        persistence /= 3.0
        result.extend((signed_step, paired_flank, pair_balance, persistence))
    for array in result:
        array[~valid] = 0.0
    return result


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save_array(path, a):
    """Atomic, flushed array write with an independent numerical reread.

    Avoid unverified array.tofile/mmap assumptions in a virtualized filesystem.
    Filesystem defects must be caught before model training, not normalized away.
    """
    path = Path(path)
    tmp = path.with_suffix('.partial')
    with tmp.open('wb') as fh:
        np.lib.format.write_array_header_1_0(fh, dict(descr=np.lib.format.dtype_to_descr(a.dtype), fortran_order=False, shape=a.shape))
        data = memoryview(np.ascontiguousarray(a)).cast('B')
        for start in range(0, len(data), 1 << 20):
            fh.write(data[start:start + (1 << 20)])
        fh.flush()
        import os
        os.fsync(fh.fileno())
    if not np.array_equal(np.load(tmp), a, equal_nan=True):
        raise IOError(f'array write/reread mismatch: {path}')
    tmp.replace(path)


def build(features="data/training_features.tif", sample="data/sample_submission.tif", dest="work/r2/features", log=print):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with rasterio.open(sample) as ref:
        a = ref.read(1, masked=True)
        valid = ~np.ma.getmaskarray(a) & np.isfinite(a.data) & (a.data > -1e38)
        template = dict(shape=[ref.height, ref.width], crs=str(ref.crs), transform=list(ref.transform)[:6])
    with rasterio.open(features) as src:
        if src.count != 19 or [src.height, src.width] != template["shape"] or str(src.crs) != template["crs"] or list(src.transform)[:6] != template["transform"]:
            raise ValueError("training raster does not match the measured 19-band template")
        for i in range(1, src.count + 1):
            a = src.read(i)
            valid &= np.isfinite(a) & (a > -1e38)
        # Keep a separate input footprint; eroding by full support avoids boundary-only detections.
        save_array(dest / "input_footprint.npy", valid)
        eligible = ndi.distance_transform_edt(np.pad(valid, 1, constant_values=False))[1:-1, 1:-1] > SUPPORT_PX
        flat_idx = np.flatnonzero(eligible.ravel())
        save_array(dest / "valid.npy", eligible)
        save_array(dest / "flat_idx.npy", flat_idx)
        names, view_a, view_b, raw, cross, profile = [], [], [], [], [], []
        file_hashes = {}

        def put(name, values, view):
            v = np.asarray(values, np.float32).ravel()[flat_idx]
            if not np.isfinite(v).all():
                raise ValueError(f"nonfinite feature inside eligible footprint: {name}")
            save_array(dest / (name + ".npy"), v)
            file_hashes[name] = digest(dest / (name + ".npy"))
            names.append(name)
            (view_a if view == "A" else view_b if view == "B" else profile if view == "H55" else cross).append(name)
            log(f"feature {len(names):02d} {name}", flush=True)

        def read(i):
            a = src.read(i).astype(np.float32)
            a[~valid] = np.nan
            return a

        for i in range(1, src.count + 1):
            name = f"raw_band_{i:02d}"
            put(name, read(i), "A" if i in A_BANDS else "B")
            raw.append(name)

        grav, cover, rtp = read(13), read(15), read(2)
        saved = {}
        for sigma in SCALES:
            gx, gy, gm, _ = normals(grav, valid, sigma)
            dx, dy, dm, _ = normals(cover, valid, sigma)
            put(f"A_gravity_grad_{sigma}", gm, "A")
            put(f"A_cover_grad_{sigma}", dm, "A")
            anti = -cosine(gx, gy, dx, dy)
            put(f"A_gravity_cover_signed_{sigma}", anti, "A")
            saved[sigma] = (gx, gy, dx, dy)
        for a, b in ((1, 3), (3, 8)):
            ax, ay, adx, ady = saved[a]
            bx, by, bdx, bdy = saved[b]
            put(f"A_gravity_persistence_{a}_{b}", cosine(ax, ay, bx, by), "A")
            put(f"A_cover_persistence_{a}_{b}", cosine(adx, ady, bdx, bdy), "A")
        gx, gy, dx, dy = saved[3]
        gcoh = coherence(gx, gy, valid)
        put("A_gravity_coherence", gcoh, "A")
        put("A_cover_coherence", coherence(dx, dy, valid), "A")
        anti3 = -cosine(gx, gy, dx, dy)
        # Copy the few channels used after clearing the large scale cache.
        gx, gy, dx, dy = (x.copy() for x in (gx, gy, dx, dy))
        saved.clear()
        for sigma in (1, 3):
            mx, my, mm, _ = normals(rtp, valid, sigma)
            put(f"A_RTP_grad_{sigma}", mm, "A")
        mx, my = mx.copy(), my.copy()
        del grav, rtp

        elev, slope = read(12), read(19)
        for sigma in SCALES:
            zx, zy, zm, zs = normals(elev, valid, sigma)
            put(f"B_elevation_grad_{sigma}", zm, "B")
            if sigma in (1, 3):
                ep, em = hessian(zs)
                put(f"B_curvature_plus_{sigma}", ep, "B")
                put(f"B_curvature_minus_{sigma}", em, "B")
                put(f"B_curvature_trace_{sigma}", ep + em, "B")
            if sigma == 3:
                surf_x, surf_y = zx.copy(), zy.copy()
                put("B_surface_coherence", coherence(zx, zy, valid), "B")
        for sigma in (1, 3):
            sx, sy, sm, _ = normals(slope, valid, sigma)
            put(f"B_slope_grad_{sigma}", sm, "B")
        for a, name, floor in ((elev, "elevation", 1.0), (slope, "slope", 0.1)):
            mu = smooth(a, valid, 8)
            # The variance support is the same 32-pixel Gaussian; no smoothing of an already smoothed residual.
            second = smooth(a * a, valid, 8)
            sd = np.sqrt(np.maximum(second - mu * mu, 0))
            residual = np.divide(a - mu, sd + floor)
            put(f"B_{name}_local_residual", residual, "B")
            put(f"B_{name}_local_sd", sd, "B")
        profile = []
        suffixes = ("normal_signed_step", "paired_flank_contrast",
                    "paired_flank_asymmetry", "tangent_step_persistence")
        # Persist and release one scale at a time: holding 20 full-grid arrays in memory is
        # unnecessary on a small runner and made the feature stage vulnerable to OOM.
        for offset in (1, 2, 3, 4, 6):
            for suffix, values in zip(suffixes, normal_profile(elev, valid, offset_px=offset)):
                feature_name = f"H55_{suffix}_{offset}px"
                put(feature_name, values, "H55")
            del values
        put("C_gravity_surface_direction", cosine(gx, gy, surf_x, surf_y), "C")
        put("C_cover_surface_direction", cosine(dx, dy, surf_x, surf_y), "C")
        put("C_magnetic_surface_direction", np.abs(cosine(mx, my, surf_x, surf_y)), "C")
        logcover = np.log1p(np.maximum(cover, 0))
        put("C_signed_cover_surface_silence", np.maximum(anti3, 0) * logcover / (1 + np.abs(slope)), "C")
        put("C_cover_persistent_gravity", gcoh * logcover, "C")
        baseline_contrast = [name for name in names if name not in profile]

    manifest = dict(version="h55-profile-v1", template=template,
                    feature_names=names, view_A=view_a, view_B=view_b,
                    view_B_h55=view_b + profile, raw_fusion=raw,
                    structural_contrast=baseline_contrast,
                    structural_contrast_h55=baseline_contrast + profile,
                    cross_features=cross, h55_profile_features=profile,
                    feature_sha256=file_hashes,
                    input_footprint_px=int(valid.sum()), eligible_px=int(eligible.sum()),
                    support_px=SUPPORT_PX, feature_scales_px=list(SCALES),
                    inputs={"features_sha256": digest(features), "sample_sha256": digest(sample)},
                    external_data_used=False, radiometric_bands_present=False,
                    caveat="Catalogue-zero is not verified fault absence; gravity and modelled depth are not independent evidence.")
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


class FeatureStore:
    """Verified read-only column arrays; gather one model chunk at a time.

    The 57 eligible-domain columns fit in memory (~1.05 GB). Ordinary array
    loads avoid unverified memmap behavior on the sandbox filesystem.
    """
    def __init__(self, directory="work/r2/features"):
        self.directory = Path(directory)
        self.manifest = json.loads((self.directory / "manifest.json").read_text())
        self.flat_idx = np.load(self.directory / "flat_idx.npy", allow_pickle=False)
        self.valid = np.load(self.directory / "valid.npy")
        if not np.array_equal(self.flat_idx, np.flatnonzero(self.valid.ravel())):
            raise ValueError("feature index mapping corrupted; rebuild features")
        self.inverse = np.full(self.valid.size, -1, dtype=np.int32)
        self.inverse[self.flat_idx] = np.arange(self.flat_idx.size)
        self.columns = {}

    def gather(self, flat_rows, names):
        rows = self.inverse[np.asarray(flat_rows)]
        if (rows < 0).any():
            raise ValueError("requested row outside eligible feature footprint")
        out = np.empty((len(rows), len(names)), np.float32)
        for j, name in enumerate(names):
            if name not in self.columns:
                path = self.directory / (name + ".npy")
                if digest(path) != self.manifest["feature_sha256"][name]:
                    raise ValueError(f"feature byte-integrity failure: {name}")
                self.columns[name] = np.load(path, allow_pickle=False)
            out[:, j] = self.columns[name][rows]
        return out

    def feature_grid(self, name):
        if name not in self.columns:
            path = self.directory / (name + ".npy")
            if digest(path) != self.manifest["feature_sha256"][name]:
                raise ValueError(f"feature byte-integrity failure: {name}")
            self.columns[name] = np.load(path, allow_pickle=False)
        out = np.zeros(self.valid.size, np.float32)
        out[self.flat_idx] = self.columns[name]
        return out.reshape(self.valid.shape)
