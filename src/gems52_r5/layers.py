"""R5 raw-layer access and the six-family split used by the trace detector.

Everything in this module is *read*, never modelled: it opens the restored, SHA-pinned rasters
(``registry/data_manifest.json``, verified by ``scripts/restore_data.py``) and hands back one
float32 grid at a time with the nodata sentinel turned into NaN.  A 3.9 GB box cannot hold a
74-layer stack, and R5 does not need one -- the detector consumes one layer, reduces it to a
single family response, and frees it.

Family split
------------
The brief asks for two views: A = potential field and subsurface, B = surface.  R5 keeps that
split for the co-training instrument (``cotrain_r5``) but the *trace detector* needs finer
groupings, because corroboration only means something if the corroborating channels are
physically independent.  Six families, each with its own instrument and its own failure mode:

    mag     magnetics          band 1,2,3,9,14 + extensions band 4 (upward-continued TMI)
    grav    gravity            band 5,11,13,18
    strain  geodetic/seismic   band 4,7,8,16
    topo    topography+LiDAR   band 12,19 + LiDAR bands 1-11
    rad     radiometrics       band 6 + radiometric bands 1-4 + extension ratios 1-3
    sub     subsurface         band 15 (depth to basement), band 17 (conductivity)

Band 6 is tagged ``magnetic_data`` / "Tilt angle or total curvature" by the organiser but
measures as radiometric total count on the bytes (IR-52-019, IR-52-034); it sits in ``rad``
here for the same reason it sits in View B in round 4 -- a radiometric channel inside the
potential-field family would fake an independence the data does not have.

LiDAR bands 9-12 ARE described in the file
------------------------------------------
Round 4 excluded LiDAR bands 9-12 on the recorded grounds that they "carry no description in the
source file" (``knowledge/23_r4_rebuild_and_results.md`` §1).  That is false for the pinned bytes:
``rasterio`` reads band descriptions ``relief``, ``coh100``, ``strike``, ``valid`` straight out of
the TIFF tags, and this module asserts them at import of :func:`lidar_names`.  ``strike`` is the
only orientation channel in the whole input set, which makes it directly relevant to a detector
whose entire job is orientation.  Recorded as IR-R5-001.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

FEATURES = "data/training_features.tif"
LABELS = "data/labels.tif"
SAMPLE = "data/sample_submission.tif"
EXTERNAL = "data/external"

LIDAR = f"{EXTERNAL}/lidar_scarp_features_u8.tif"
RAD = f"{EXTERNAL}/geodawn_rad_u8.tif"
EXT = f"{EXTERNAL}/geodawn_extensions_u8.tif"
SGMC = f"{EXTERNAL}/derived_sgmc_faults_100m_u8.tif"
QFAULTS = f"{EXTERNAL}/gdr_qfaults_traces.csv"

SENTINEL_LIMIT = -1e38          # official nodata is -3.4028234663852886e+38

# 1-based index -> organiser band_name tag, transcribed from the file itself.
BANDS = {
    1: "mag_anom", 2: "rtp", 3: "tmi_hg", 4: "geod_2ndinv", 5: "iso_grav_anom_slope",
    6: "tc", 7: "geod_shearrate", 8: "geod_dilaterate", 9: "tmi_vg", 10: "deq_n100a15",
    11: "iso_grav_anom_vg", 12: "det_elev", 13: "iso_grav_anom", 14: "tmi",
    15: "depth_to_base_surf", 16: "ieq_n100a15", 17: "cond_surf", 18: "iso_grav_anom_hg",
    19: "det_elev_slope",
}

LIDAR_BANDS = {1: "ex_max", 2: "ex_mean", 3: "step_max", 4: "lapneg_max", 5: "lappos_max",
               6: "downface_max", 7: "upface_max", 8: "cross_max", 9: "relief", 10: "coh100",
               11: "strike", 12: "valid"}
RAD_BANDS = {1: "rad_K", 2: "rad_Th", 3: "rad_U", 4: "rad_TC"}
EXT_BANDS = {1: "ext_ThK", 2: "ext_UK", 3: "ext_UTh", 4: "ext_TMI_up150"}

# family -> list of (source, band) where source in {"features","lidar","rad","ext"}
FAMILIES: dict[str, list[tuple[str, int]]] = {
    "mag": [("features", 1), ("features", 2), ("features", 3), ("features", 9),
            ("features", 14), ("ext", 4)],
    "grav": [("features", 5), ("features", 11), ("features", 13), ("features", 18)],
    "strain": [("features", 4), ("features", 7), ("features", 8), ("features", 16)],
    "topo": [("features", 12), ("features", 19),
             ("lidar", 1), ("lidar", 3), ("lidar", 6), ("lidar", 7), ("lidar", 8),
             ("lidar", 9), ("lidar", 10)],
    "rad": [("features", 6), ("rad", 1), ("rad", 2), ("rad", 3), ("rad", 4),
            ("ext", 1), ("ext", 2), ("ext", 3)],
    "sub": [("features", 15), ("features", 17)],
}

# The brief's two co-training views, as family unions.  mag+grav+strain+sub is potential-field
# and subsurface (View A); topo+rad is surface (View B).
VIEW_A_FAMILIES = ("mag", "grav", "strain", "sub")
VIEW_B_FAMILIES = ("topo", "rad")

_PATHS = {"features": FEATURES, "lidar": LIDAR, "rad": RAD, "ext": EXT}


def band_name(source: str, band: int) -> str:
    table = {"features": BANDS, "lidar": LIDAR_BANDS, "rad": RAD_BANDS, "ext": EXT_BANDS}[source]
    return table[band]


def family_layers(family: str) -> list[str]:
    return [f"{s}:{band_name(s, b)}" for s, b in FAMILIES[family]]


def lidar_names(path: str = LIDAR) -> dict[int, str]:
    """Read the LiDAR file's own TIFF descriptions and assert they match :data:`LIDAR_BANDS`."""
    with rasterio.open(path) as ds:
        got = {i: (ds.descriptions[i - 1] or "") for i in range(1, ds.count + 1)}
    missing = [i for i, name in LIDAR_BANDS.items() if got.get(i, "") != name]
    if missing:
        raise AssertionError(f"LiDAR band descriptions changed for bands {missing}: {got}")
    return got


def read(source: str, band: int, valid: np.ndarray | None = None) -> np.ndarray:
    """One layer as float32 with the nodata sentinel and any non-finite value set to NaN."""
    with rasterio.open(_PATHS[source]) as ds:
        a = ds.read(band).astype(np.float32)
    a[~np.isfinite(a)] = np.nan
    a[a < SENTINEL_LIMIT] = np.nan
    if valid is not None:
        a[~valid] = np.nan
    return a


def footprint(features: str = FEATURES) -> np.ndarray:
    """Intersection of the finite-data masks of all 19 organiser bands (IR-52-002)."""
    with rasterio.open(features) as ds:
        acc = None
        for i in range(1, ds.count + 1):
            a = ds.read(i)
            ok = np.isfinite(a) & (a > SENTINEL_LIMIT)
            acc = ok if acc is None else (acc & ok)
    return acc


def catalogue(labels: str = LABELS) -> np.ndarray:
    with rasterio.open(labels) as ds:
        return ds.read(1) == 1


def shape_of(path: str = FEATURES) -> tuple[int, int]:
    with rasterio.open(path) as ds:
        return (ds.height, ds.width)


def rank_within(a: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Percentile rank in [0, 1] over the finite ``valid`` pixels; NaN everywhere else.

    Ranks, not z-scores: band 10 reaches 4.96e6 m inside a 492 km-diagonal grid (IR-R4-002) and
    several bands are heavy-tailed, so any moment-based normalisation lets a handful of pixels
    set the scale for the whole family.  A rank transform is monotone and tail-proof, which is
    all a ridge detector needs.  Ties average, so a quantised u8 band cannot produce a plateau
    of identical ranks that a top-K cut would then split arbitrarily.
    """
    from scipy.stats import rankdata

    out = np.full(a.shape, np.nan, np.float32)
    idx = np.flatnonzero(valid.ravel())
    vals = a.ravel()[idx].astype(np.float64)
    fin = np.isfinite(vals)
    if not fin.any():
        return out
    r = rankdata(vals[fin], method="average")
    r = (r - 1.0) / max(float(fin.sum()) - 1.0, 1.0)
    filled = np.full(idx.size, np.nan)
    filled[fin] = r
    out.ravel()[idx] = filled
    return out


def path_exists(*names: str) -> dict[str, bool]:
    return {n: Path(n).exists() for n in names}
