"""H57 corrected-view feature cache and small, testable modeling helpers.

This module deliberately does not import the synthetic H56 builder or the historical
R2/R3 feature split. Band 6 is treated as a radiometric total-count-like channel in
View B, with the conflict between its TIFF tag and the measured GeoDAWN comparison
kept in the caller's evidence. No external rasters or prior predictions are model inputs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

import numpy as np
import rasterio
from affine import Affine
from scipy import ndimage as ndi
from sklearn.ensemble import HistGradientBoostingClassifier
from threadpoolctl import threadpool_limits

from . import spatial

VIEW_A_BANDS = (1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18)
VIEW_B_BANDS = (6, 12, 19)
EDGE_BANDS_A = (2, 13, 14, 17)
EDGE_BANDS_B = (6, 12)
SIGMAS = (1.0, 3.0, 8.0)
PIXEL_M = 100.0
MAX_SUPPORT_PX = 36

BAND_NAMES = {
    1: "mag_anom", 2: "rtp", 3: "tmi_horizontal_gradient", 4: "geodetic_second_invariant",
    5: "isostatic_gravity_anomaly_slope", 6: "radiometric_tc_like_mistagged",
    7: "geodetic_shear_rate", 8: "geodetic_dilatation_rate", 9: "tmi_vertical_gradient",
    10: "distance_to_earthquake", 11: "isostatic_gravity_vertical_gradient", 12: "detrended_elevation",
    13: "isostatic_gravity_anomaly", 14: "tmi", 15: "depth_to_basement", 16: "earthquake_density",
    17: "conductivity_surface", 18: "isostatic_gravity_horizontal_gradient", 19: "detrended_elevation_slope",
}


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def normalized_gaussian(a: np.ndarray, valid: np.ndarray, sigma_px: float) -> np.ndarray:
    """Normalized-convolution Gaussian; invalid nodata never smears into valid cells."""
    if sigma_px <= 0 or not np.isfinite(sigma_px):
        raise ValueError("sigma_px must be finite and positive")
    values = np.asarray(a, dtype=np.float32)
    mask = np.asarray(valid, dtype=bool)
    if values.ndim != 2 or values.shape != mask.shape:
        raise ValueError("a and valid must be same-shaped 2D arrays")
    good = mask & np.isfinite(values) & (values > -1e30)
    numerator = ndi.gaussian_filter(np.where(good, values, 0.0), sigma_px,
                                    mode="reflect", truncate=4.0)
    denominator = ndi.gaussian_filter(good.astype(np.float32), sigma_px,
                                      mode="reflect", truncate=4.0)
    out = np.divide(numerator, denominator, out=np.zeros_like(numerator), where=denominator > 1e-8)
    return out.astype(np.float32, copy=False)


def edge_magnitude(a: np.ndarray, valid: np.ndarray, sigma_px: float) -> np.ndarray:
    """Metric-scaled gradient magnitude of normalized-smoothed input."""
    smooth = normalized_gaussian(a, valid, sigma_px)
    gy, gx = np.gradient(smooth, PIXEL_M, PIXEL_M, edge_order=1)
    edge = np.hypot(gx, gy).astype(np.float32, copy=False)
    edge[~np.asarray(valid, bool)] = 0.0
    if not np.isfinite(edge[valid]).all():
        raise ValueError("edge transform produced non-finite values inside the footprint")
    return edge


def dem_curvature_magnitude(a: np.ndarray, valid: np.ndarray, sigma_px: float) -> np.ndarray:
    """Absolute Laplacian of normalized-smoothed DEM, in inverse square metres."""
    smooth = normalized_gaussian(a, valid, sigma_px)
    lap = ndi.laplace(smooth, mode="nearest") / (PIXEL_M * PIXEL_M)
    out = np.abs(lap).astype(np.float32, copy=False)
    out[~np.asarray(valid, bool)] = 0.0
    if not np.isfinite(out[valid]).all():
        raise ValueError("curvature transform produced non-finite values inside the footprint")
    return out


def _assert_aligned(reference, source, name: str) -> None:
    if (source.shape != reference.shape or source.crs != reference.crs
            or source.transform != reference.transform or source.bounds != reference.bounds):
        raise ValueError(f"{name} does not exactly match the sample-submission grid")


def _feature_names() -> tuple[list[str], list[str]]:
    a = [f"A_band{b:02d}_{BAND_NAMES[b]}" for b in VIEW_A_BANDS]
    for b in EDGE_BANDS_A:
        a.extend(f"A_band{b:02d}_edge_sigma{int(s)}" for s in SIGMAS)
    b_names = [f"B_band{b:02d}_{BAND_NAMES[b]}" for b in VIEW_B_BANDS]
    for b in EDGE_BANDS_B:
        b_names.extend(f"B_band{b:02d}_edge_sigma{int(s)}" for s in SIGMAS)
    for s in SIGMAS:
        b_names.append(f"B_band12_dem_abs_laplacian_sigma{int(s)}")
    return a, b_names


def build_feature_cache(features_path: str | Path, labels_path: str | Path,
                        template_path: str | Path, cache_dir: str | Path,
                        preregistration_sha256: str | None = None,
                        log: Callable[[str], None] = print) -> dict:
    """Build the label-free H57 feature memmaps and exact masks; reuse only a pinned cache."""
    features_path, labels_path, template_path = map(Path, (features_path, labels_path, template_path))
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    paths = {"features": features_path, "labels": labels_path, "template": template_path}
    input_hashes = {key: sha256_file(path) for key, path in paths.items()}
    names_a, names_b = _feature_names()
    builder_hash = sha256_file(Path(__file__))
    manifest_path = cache / "manifest.json"
    if manifest_path.exists():
        try:
            old = json.loads(manifest_path.read_text())
            if (old.get("input_sha256") == input_hashes
                    and old.get("builder_sha256") == builder_hash
                    and old.get("preregistration_sha256") == preregistration_sha256
                    and (cache / "features_A.npy").exists()
                    and (cache / "features_B.npy").exists()
                    and (cache / "valid.npy").exists()
                    and (cache / "template_valid.npy").exists()
                    and (cache / "catalogue.npy").exists()):
                log("H57 feature cache hit: input, preregistration and builder hashes match")
                return old
        except (OSError, json.JSONDecodeError):
            pass

    with rasterio.open(template_path) as template, rasterio.open(labels_path) as labels, \
            rasterio.open(features_path) as source:
        _assert_aligned(template, labels, "labels")
        _assert_aligned(template, source, "training_features")
        if template.count != 1 or labels.count != 1 or source.count != 19:
            raise ValueError("expected a one-band template/label and 19-band training stack")
        shape = template.shape
        template_values = template.read(1)
        template_valid = np.isfinite(template_values) & (template.dataset_mask() > 0)
        label_values = labels.read(1)
        label_valid = (label_values == 0) | (label_values == 1)
        catalogue = label_values == 1
        if not np.array_equal(template_valid, label_valid):
            log("WARNING: sample footprint and label validity differ; using their intersection for fit/evaluation")
        eligible = template_valid & label_valid
        band_valid_counts = {}
        for band in sorted(set(VIEW_A_BANDS) | set(VIEW_B_BANDS)):
            values = source.read(band)
            ok = np.isfinite(values) & (values > -1e30)
            eligible &= ok
            band_valid_counts[str(band)] = int(ok.sum())
        if not eligible.any() or not catalogue[eligible].any():
            raise ValueError("empty H57 eligible footprint or catalogue")
        # A public training label may exist in the sample template but lack a feature in one band;
        # it must not become a training/evaluation example for a view that cannot be scored.
        catalogue &= eligible
        height, width = shape
        transform, crs = template.transform, template.crs
        template_count = int(template_valid.sum())
        eligible_count = int(eligible.sum())
        catalogue_count = int(catalogue.sum())
        # Persist small masks before allocating the multi-gigabyte, disk-backed feature arrays.
        np.save(cache / "valid.npy", eligible)
        np.save(cache / "template_valid.npy", template_valid)
        np.save(cache / "catalogue.npy", catalogue)
        del template_values, label_values, label_valid

        a_map = np.lib.format.open_memmap(cache / "features_A.npy", mode="w+", dtype=np.float32,
                                         shape=(len(names_a), height, width))
        b_map = np.lib.format.open_memmap(cache / "features_B.npy", mode="w+", dtype=np.float32,
                                         shape=(len(names_b), height, width))
        a_index = {name: i for i, name in enumerate(names_a)}
        b_index = {name: i for i, name in enumerate(names_b)}
        band_descriptions = {str(i): source.descriptions[i - 1] for i in range(1, 20)}

        def put(target, lookup, name, values):
            arr = np.asarray(values, dtype=np.float32)
            if arr.shape != shape:
                raise ValueError(f"feature {name} has shape {arr.shape}, expected {shape}")
            if not np.isfinite(arr[eligible]).all():
                raise ValueError(f"feature {name} contains non-finite values in the fit footprint")
            arr[~eligible] = 0.0
            target[lookup[name], :, :] = arr

        for band in VIEW_A_BANDS:
            raw = source.read(band).astype(np.float32, copy=False)
            raw[~eligible] = 0.0
            name = f"A_band{band:02d}_{BAND_NAMES[band]}"
            put(a_map, a_index, name, raw)
            log(f"  H57 raw A band {band}: {BAND_NAMES[band]}")
            if band in EDGE_BANDS_A:
                for sigma in SIGMAS:
                    edge = edge_magnitude(raw, eligible, sigma)
                    put(a_map, a_index, f"A_band{band:02d}_edge_sigma{int(sigma)}", edge)
                    del edge
            del raw

        for band in VIEW_B_BANDS:
            raw = source.read(band).astype(np.float32, copy=False)
            raw[~eligible] = 0.0
            name = f"B_band{band:02d}_{BAND_NAMES[band]}"
            put(b_map, b_index, name, raw)
            log(f"  H57 raw B band {band}: {BAND_NAMES[band]}")
            if band in EDGE_BANDS_B:
                for sigma in SIGMAS:
                    edge = edge_magnitude(raw, eligible, sigma)
                    put(b_map, b_index, f"B_band{band:02d}_edge_sigma{int(sigma)}", edge)
                    del edge
            if band == 12:
                for sigma in SIGMAS:
                    curvature = dem_curvature_magnitude(raw, eligible, sigma)
                    put(b_map, b_index, f"B_band12_dem_abs_laplacian_sigma{int(sigma)}", curvature)
                    del curvature
            del raw
        a_map.flush()
        b_map.flush()
        del a_map, b_map

        manifest = dict(
            version="gems52-h57-features-v1", input_sha256=input_hashes,
            builder_sha256=builder_hash, preregistration_sha256=preregistration_sha256,
            shape=[height, width], crs=str(crs), transform=list(transform)[:6],
            template_footprint_px=template_count, eligible_feature_footprint_px=eligible_count,
            catalogue_px=catalogue_count, feature_support_px=MAX_SUPPORT_PX,
            band_valid_counts=band_valid_counts, band_descriptions=band_descriptions,
            view_A_bands=list(VIEW_A_BANDS), view_B_bands=list(VIEW_B_BANDS),
            band6_identity="radiometric TC-like working assignment; TIFF metadata conflict; see evidence/h55_band6_identity.json",
            view_A_features=names_a, view_B_features=names_b,
            feature_dtype="float32 disk-backed memmap", external_data_used=False,
            normalizer="none; raw physical units retained; HistGradientBoosting bins fit on each training fold only",
            invalid_template_cells_with_missing_model_features=int(template_count - eligible_count),
            nodata_policy="only finite, non-sentinel, eligible training pixels are used; output mask is the sample-template mask")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    log(f"H57 feature cache written: {len(names_a)} A and {len(names_b)} B channels; "
        f"{eligible_count:,} eligible pixels; {template_count - eligible_count:,} template cells lack model inputs")
    return manifest


class FeatureStore:
    """Read-only memory maps for the two H57 views."""
    def __init__(self, cache_dir: str | Path):
        self.directory = Path(cache_dir)
        self.manifest = json.loads((self.directory / "manifest.json").read_text())
        self.valid = np.load(self.directory / "valid.npy", mmap_mode="r")
        self.template_valid = np.load(self.directory / "template_valid.npy", mmap_mode="r")
        self.catalogue = np.load(self.directory / "catalogue.npy", mmap_mode="r")
        self.A = np.load(self.directory / "features_A.npy", mmap_mode="r")
        self.B = np.load(self.directory / "features_B.npy", mmap_mode="r")
        if self.A.shape[1:] != self.valid.shape or self.B.shape[1:] != self.valid.shape:
            raise ValueError("H57 feature cache arrays do not align with the validity mask")
        self.shape = tuple(self.valid.shape)

    def _feature_array(self, view: str):
        if view == "A":
            return self.A
        if view == "B":
            return self.B
        raise ValueError(f"view must be A or B, got {view!r}")

    def names(self, view: str) -> list[str]:
        return list(self.manifest[f"view_{view}_features"])

    def gather(self, rows: np.ndarray, view: str) -> np.ndarray:
        ids = np.asarray(rows, dtype=np.int64).reshape(-1)
        if ids.size and ((ids < 0).any() or (ids >= self.valid.size).any()):
            raise ValueError("training/prediction row index is out of bounds")
        a = self._feature_array(view).reshape(self._feature_array(view).shape[0], -1)
        return np.asarray(a[:, ids].T, dtype=np.float32, order="C")


def make_classifier(seed: int, config: dict | None = None) -> HistGradientBoostingClassifier:
    settings = config or dict(max_iter=120, max_leaf_nodes=15, learning_rate=0.08,
                              l2_regularization=2.0, min_samples_leaf=80,
                              early_stopping=False, class_weight="balanced")
    return HistGradientBoostingClassifier(random_state=int(seed), **settings)


def fit_classifier(store: FeatureStore, view: str, rows: np.ndarray, y: np.ndarray,
                   seed: int, pseudo_rows: np.ndarray | None = None,
                   pseudo_weight: float = 0.25, learner_config: dict | None = None):
    rows = np.asarray(rows, dtype=np.int64)
    y = np.asarray(y, dtype=np.int8)
    if len(rows) != len(y) or len(np.unique(y)) != 2:
        raise ValueError("model fit needs aligned rows with both classes")
    x = store.gather(rows, view)
    weights = np.ones(len(rows), dtype=np.float32)
    if pseudo_rows is not None and len(pseudo_rows):
        p = np.asarray(pseudo_rows, dtype=np.int64)
        x = np.vstack((x, store.gather(p, view)))
        y = np.concatenate((y, np.ones(len(p), dtype=np.int8)))
        weights = np.concatenate((weights, np.full(len(p), pseudo_weight, dtype=np.float32)))
    if not np.isfinite(x).all():
        raise ValueError(f"non-finite training values in View {view}")
    model = make_classifier(seed, learner_config)
    with threadpool_limits(limits=2):
        model.fit(x, y, sample_weight=weights)
    return model


def predict_domain(store: FeatureStore, model, view: str, domain: np.ndarray,
                   chunk_size: int = 100_000) -> np.ndarray:
    domain = np.asarray(domain, dtype=bool)
    if domain.shape != store.shape:
        raise ValueError("prediction domain does not match feature grid")
    ids = np.flatnonzero(domain & store.valid)
    out = np.full(store.valid.size, np.nan, dtype=np.float32)
    with threadpool_limits(limits=2):
        for start in range(0, len(ids), chunk_size):
            part = ids[start:start + chunk_size]
            x = store.gather(part, view)
            out[part] = model.predict_proba(x)[:, 1].astype(np.float32)
    return out.reshape(store.shape)


def sample_training_rows(catalogue: np.ndarray, valid: np.ndarray, train: np.ndarray,
                         seed: int, positive_cap: int = 40_000,
                         negative_cap: int = 160_000, collar_px: int = 3) -> tuple[np.ndarray, np.ndarray, dict]:
    """Seeded pixel sample; zeros are catalogue-zero proxies, not verified fault absence."""
    cat, valid, train = map(lambda x: np.asarray(x, bool), (catalogue, valid, train))
    if cat.shape != valid.shape or train.shape != valid.shape:
        raise ValueError("catalogue, valid and train masks must have the same shape")
    near = ndi.distance_transform_edt(~cat) <= float(collar_px)
    pos_pool = np.flatnonzero(cat & valid & train)
    neg_pool = np.flatnonzero(~cat & valid & train & ~near)
    if not len(pos_pool) or not len(neg_pool):
        raise ValueError("training fold has no positive or catalogue-zero proxy examples")
    rng = np.random.default_rng(seed)
    n_pos = min(len(pos_pool), int(positive_cap))
    n_neg = min(len(neg_pool), int(negative_cap))
    pos = rng.choice(pos_pool, size=n_pos, replace=False)
    neg = rng.choice(neg_pool, size=n_neg, replace=False)
    rows = np.concatenate((pos, neg)).astype(np.int64)
    y = np.concatenate((np.ones(n_pos, np.int8), np.zeros(n_neg, np.int8)))
    order = rng.permutation(len(rows))
    rows, y = rows[order], y[order]
    receipt = dict(n_positive_pool=int(len(pos_pool)), n_negative_proxy_pool=int(len(neg_pool)),
                   n_positive_sample=int(n_pos), n_negative_proxy_sample=int(n_neg),
                   positive_rows_sha256=hashlib.sha256(np.sort(pos).astype('<i8').tobytes()).hexdigest(),
                   negative_rows_sha256=hashlib.sha256(np.sort(neg).astype('<i8').tobytes()).hexdigest(),
                   negative_definition="training catalogue-zero proxy at Euclidean distance > 3 px from every mapped label; not verified absence")
    return rows, y, receipt


def empirical_rank(score: np.ndarray, reference_scores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Tie-aware training-reference empirical CDF rank; output lies in [0,1]."""
    ref = np.asarray(reference_scores, dtype=np.float32).ravel()
    values = np.asarray(score, dtype=np.float32)
    ref = ref[np.isfinite(ref)]
    if not ref.size:
        raise ValueError("rank reference has no finite predictions")
    ordered = np.sort(ref)
    finite = np.isfinite(values)
    flat_values = values[finite]
    lower = np.searchsorted(ordered, flat_values, side="left")
    upper = np.searchsorted(ordered, flat_values, side="right")
    flat_rank = ((lower + upper).astype(np.float64) / (2.0 * len(ordered))).astype(np.float32)
    out = np.zeros(values.shape, dtype=np.float32)
    out[finite] = flat_rank
    return out, np.asarray([len(ordered)], dtype=np.int64)


def disagreement_field(p_a: np.ndarray, p_b: np.ndarray,
                       reference_a: np.ndarray, reference_b: np.ndarray,
                       domain: np.ndarray) -> tuple[dict[str, np.ndarray], dict]:
    """Fixed H57 rank/strata rule; quantiles are estimated from training-only predictions."""
    pa, pb = np.asarray(p_a, np.float32), np.asarray(p_b, np.float32)
    domain = np.asarray(domain, bool)
    if pa.shape != pb.shape or pa.shape != domain.shape:
        raise ValueError("A, B and domain maps must have the same shape")
    ref_a, ref_b = np.asarray(reference_a, np.float32), np.asarray(reference_b, np.float32)
    ref_a, ref_b = ref_a[np.isfinite(ref_a)], ref_b[np.isfinite(ref_b)]
    if not len(ref_a) or not len(ref_b):
        raise ValueError("training-only view reference is empty")
    q_a = np.quantile(ref_a, [0.4, 0.8, 0.99]).astype(float)
    q_b = np.quantile(ref_b, [0.4, 0.8, 0.99]).astype(float)
    rank_a, edges_a = empirical_rank(pa, ref_a)
    rank_b, edges_b = empirical_rank(pb, ref_b)
    conf_a = pa >= q_a[2]
    conf_b = pb >= q_b[2]
    abst_a = (pa >= q_a[0]) & (pa <= q_a[1])
    abst_b = (pb >= q_b[0]) & (pb <= q_b[1])
    strata = np.zeros(pa.shape, dtype=np.uint8)
    strata[conf_a & conf_b & domain] = 1
    strata[conf_a & ~conf_b & abst_b & domain] = 2
    strata[conf_b & ~conf_a & abst_a & domain] = 3
    rho = (0.55 * rank_a + 0.20 * rank_b + 0.25 * np.minimum(rank_a, rank_b)
           + 0.30 * (strata == 2) * rank_a - 0.75 * (strata == 3) * rank_b)
    rho = np.where(domain, np.clip(rho, 0.0, None), 0.0).astype(np.float32)
    fields = dict(view_A=np.where(domain, rank_a, 0.0).astype(np.float32),
                  view_B=np.where(domain, rank_b, 0.0).astype(np.float32),
                  matched_max_union=np.where(domain, np.maximum(rank_a, rank_b), 0.0).astype(np.float32),
                  h57_disagreement=rho)
    summary = dict(quantile_a={"q40": float(q_a[0]), "q80": float(q_a[1]), "q99": float(q_a[2])},
                   quantile_b={"q40": float(q_b[0]), "q80": float(q_b[1]), "q99": float(q_b[2])},
                   rank_reference_n_a=int(edges_a[0]), rank_reference_n_b=int(edges_b[0]),
                   stratum_counts={"concordant": int(((strata == 1) & domain).sum()),
                                   "A_only": int(((strata == 2) & domain).sum()),
                                   "B_only": int(((strata == 3) & domain).sum()),
                                   "silent": int(((strata == 0) & domain).sum())},
                   formula="clip(0.55*rA + 0.20*rB + 0.25*min(rA,rB) + 0.30*I(A-only)*rA - 0.75*I(B-only)*rB, 0, infinity)",
                   thresholds_source="training-domain predictions only; not calibrated fault probabilities")
    return fields, {"strata": strata, **summary}


def write_submission_tiff(path: str | Path, values: np.ndarray, template_path: str | Path,
                          template_valid: np.ndarray, *, status: str) -> dict:
    """Write float32 GeoTIFF with [0,1] finite inside, NaN only outside template validity."""
    output = Path(path)
    grid = np.asarray(values, dtype=np.float32)
    valid = np.asarray(template_valid, bool)
    if grid.ndim != 2 or grid.shape != valid.shape:
        raise ValueError("submission and template-valid masks must be same-shaped 2D arrays")
    if not np.isfinite(grid[valid]).all() or (grid[valid] < 0).any() or (grid[valid] > 1).any():
        raise ValueError("every in-footprint prediction must be finite and in [0,1]")
    if np.isfinite(grid[~valid]).any():
        raise ValueError("outside-template cells must be NaN/nodata, not finite predictions")
    output.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(template_path) as template:
        profile = dict(driver="GTiff", width=template.width, height=template.height, count=1,
                       dtype="float32", crs=template.crs, transform=template.transform,
                       tiled=True, blockxsize=256, blockysize=256, compress="deflate",
                       zlevel=9, predictor=2, nodata=np.nan)
        with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=True):
            with rasterio.open(output, "w", **profile) as dst:
                dst.write(grid, 1)
                dst.write_mask(valid.astype(np.uint8) * 255)
                dst.update_tags(model="GEMSDOE52 H57 measured-data research inference",
                                artifact_status=status,
                                nodata_policy="NaN only outside sample-template validity; finite [0,1] inside")
    with rasterio.open(output) as written, rasterio.open(template_path) as template:
        got = written.read(1)
        got_mask = (written.dataset_mask() > 0)
        exact = (np.array_equal(got[valid], grid[valid])
                 and np.isnan(got[~valid]).all()
                 and np.array_equal(got_mask, valid)
                 and written.count == 1 and written.dtypes[0] == "float32"
                 and written.crs == template.crs and written.transform == template.transform
                 and written.bounds == template.bounds)
        if not exact:
            raise ValueError("independent GeoTIFF read-back failed pixel, mask or geometry equality")
        in_values = got[valid]
        receipt = dict(path=str(output), bytes=output.stat().st_size, sha256=sha256_file(output),
                       decoded_in_footprint_sha256=hashlib.sha256(got[valid].astype('<f4').tobytes()).hexdigest(),
                       count=written.count, dtype=written.dtypes[0], crs=str(written.crs),
                       shape=list(written.shape), width=written.width, height=written.height,
                       transform=list(written.transform)[:6], bounds=list(written.bounds), nodata=str(written.nodata),
                       template_valid_px=int(valid.sum()), in_footprint_finite=bool(np.isfinite(in_values).all()),
                       in_footprint_min=float(in_values.min()) if in_values.size else None,
                       in_footprint_max=float(in_values.max()) if in_values.size else None,
                       in_footprint_nonzero=int((in_values > 0).sum()),
                       outside_footprint_nan=int(np.isnan(got[~valid]).sum()),
                       outside_footprint_finite=int(np.isfinite(got[~valid]).sum()),
                       internal_mask_matches_template=bool(np.array_equal(got_mask, valid)),
                       on_disk_readback_exact=exact,
                       validation_class="local read-back against the owner-mirrored sample template; not organizer portal acceptance")
    return receipt


def export_mask(prediction: np.ndarray, template_valid: np.ndarray) -> np.ndarray:
    """Apply outside-template NaNs without mutating the caller's prediction grid."""
    p = np.asarray(prediction, dtype=np.float32)
    valid = np.asarray(template_valid, dtype=bool)
    if p.shape != valid.shape:
        raise ValueError("prediction and template mask shape mismatch")
    out = p.copy()
    out[~valid] = np.nan
    return out
