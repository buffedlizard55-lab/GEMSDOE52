"""Shared extension: add the H72 deformation-only View A2 columns to the template store.

Why this is a *shared* module and not a round-private fork
---------------------------------------------------------
The parallel-run protocol says: reuse the template's cached feature stack, and if a shared tool
is missing something, fix it once in the template.  H72 executes the deferred H70-E variant
(``knowledge/54``, RANK 5): a View A built **only** from the deformation bands of
``training_features.tif`` — geodetic second invariant (band 4), shear rate (7), dilatation rate
(8), distance to earthquake (10) and earthquake intensity/density (16).  Five consecutive View A
rebuilds that *mixed* potential-field and deformation channels all failed the Blum-Mitchell
sufficiency screen out of quadrant (H61 0.5163, H63 0.5362, H64 0.5230, H65 0.5202, H70 0.5166),
so the failure cannot be attributed to either half of View A; the deformation half alone has never
been tested.

Physical basis (stated, not implied): an active or recently active fault in a sedimentary basin
accumulates geodetic strain and concentrates micro-seismicity along its plane while its surface
expression can be absent (a blind fault), and the USGS/INGENIOUS catalogue is a surface-mapped
product that cannot contain it.  Strain and seismicity are *rate* fields: they respond to present
activity, not to erosional expression.

What the columns are: gradient magnitude of each deformation band at the shared scales
sigma in {1, 3, 8} px (the template's ``structural.normals``), plus structure coherence of the
second-invariant and shear-rate gradients at sigma = 3 px (the template's
``structural.coherence``, the same operator the store already uses for gravity and cover).  Rank
and gradient features are invariant to any monotone re-quantisation of the source bands.

Provenance and limits (stated, not implied)
------------------------------------------
* Bands are read from the SHA-256-pinned ``data/training_features.tif`` (owner mirror of a
  login-walled DrivenData file; pins prove mirror consistency, not organiser authentication).
* Band identities are the file's own descriptions, read from the restored bytes (see
  ``evidence/band_inventory.json``).
* A strain/seismicity lineament is a *deformation* hypothesis, not proof of a fault.  The named
  non-fault mimics are anthropogenic subsidence from groundwater withdrawal, irrigation-related
  aquifer compaction, volcanic inflation/deflation (magma movement without discrete faulting),
  post-seismic afterslip or viscoelastic relaxation, and seasonal hydrological loading.
* Nothing here touches labels.  Every column is a function of the feature raster alone.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio

from . import structural

# (1-based band index, physical description read from the restored file's own band descriptions)
DEF_BANDS = (
    (4, "geodetic second invariant - measure of strain rate tensor magnitude"),
    (7, "geodetic shear rate - rate of angular deformation from GPS/InSAR"),
    (8, "geodetic dilatation rate - rate of volumetric strain (expansion/contraction)"),
    (10, "distance to earthquake (n=100km radius, a=15 deg azimuth parameters)"),
    (16, "earthquake intensity or density (n=100km radius, a=15 deg parameters)"),
)
GRAD_SIGMAS = (1, 3, 8)           # the template's shared scales (structural.SCALES)
COHERENCE_BANDS = (4, 7)          # coherence of the two shear-strain gradients at sigma 3
COHERENCE_SIGMA = 3.0
VERSION_TAG = "+h72-deformation-v1"


def grad_feature_names() -> list[str]:
    """The 15 gradient-magnitude columns, in (band, sigma) order."""
    return [f"H72_def_grad_{b:02d}_{s}" for b, _d in DEF_BANDS for s in GRAD_SIGMAS]


def coherence_feature_names() -> list[str]:
    """The 2 structure-coherence columns."""
    return [f"H72_def_coherence_{b:02d}" for b in COHERENCE_BANDS]


def def_feature_names() -> list[str]:
    return grad_feature_names() + coherence_feature_names()


def view_A2_deformation_names(manifest: dict) -> list[str]:
    """H72's View A2: the five raw deformation bands + the 17 derived H72 columns (22 channels).

    The raw bands are already store columns tagged in the template's ``view_A``; the H72 columns
    are registered by :func:`register_columns`.  No View B name may appear (the caller asserts),
    and the canonical ``view_A_with_external`` / ``view_B_with_external`` are NOT modified: H72
    reads its View A list from ``manifest["view_A2_deformation"]`` through a setup wrapper, so
    the H61 setup checks keep running on the canonical lists.
    """
    raw = [f"raw_band_{b:02d}" for b, _d in DEF_BANDS]
    return sorted(raw + def_feature_names())


def deformation_columns(field: np.ndarray, valid: np.ndarray, band: int,
                        log=print) -> dict[str, np.ndarray]:
    """Derived columns for one deformation band, computed one scale at a time (memory-bounded)."""
    out: dict[str, np.ndarray] = {}
    for sigma in GRAD_SIGMAS:
        _gx, _gy, mag, _s = structural.normals(field, valid, float(sigma))
        out[f"H72_def_grad_{band:02d}_{sigma}"] = mag
        del _gx, _gy, _s
    if band in COHERENCE_BANDS:
        gx, gy, _mag, _s = structural.normals(field, valid, COHERENCE_SIGMA)
        out[f"H72_def_coherence_{band:02d}"] = structural.coherence(gx, gy, valid)
        del gx, gy, _mag, _s
    return out


def register_columns(store_dir: str | Path, columns: dict[str, np.ndarray], log=print) -> dict:
    """Write verified columns into the store and extend the manifest.  Idempotent.

    A column whose SHA-256 already matches the manifest is not recomputed.  Returns the summary
    the caller folds into its receipt.
    """
    store = Path(store_dir)
    manifest_path = store / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    valid = np.load(store / "valid.npy")
    flat_idx = np.load(store / "flat_idx.npy")
    if not np.array_equal(flat_idx, np.flatnonzero(valid.ravel())):
        raise ValueError("store index mapping corrupted; rebuild the feature stack")
    hashes = dict(manifest["feature_sha256"])
    names = list(manifest["feature_names"])
    added, skipped = [], []
    for name, values in columns.items():
        col = np.asarray(values, np.float32).ravel()[flat_idx]
        if not np.isfinite(col).all():
            raise ValueError(f"nonfinite H72 feature inside eligible footprint: {name}")
        dest = store / (name + ".npy")
        if dest.exists() and name in hashes and structural.digest(dest) == hashes[name]:
            skipped.append(name)
            continue
        structural.save_array(dest, col)
        hashes[name] = structural.digest(dest)
        if name not in names:
            names.append(name)
        added.append(name)
        log(f"h72 feature {name}")
    va2 = view_A2_deformation_names({**manifest, "feature_names": names, "feature_sha256": hashes})
    vb = set(manifest["view_B_with_external"])
    overlap = sorted(set(va2) & vb)
    if overlap:
        raise ValueError(f"H72 cross-view feature overlap: {overlap}")
    if not set(va2) <= set(names):
        raise ValueError("H72 View A2 references columns that are not in the store")
    manifest.update(
        version=(manifest["version"] + VERSION_TAG
                 if VERSION_TAG not in manifest["version"] else manifest["version"]),
        feature_names=names, feature_sha256=hashes,
        view_A2_deformation=va2,
        h72_deformation=dict(
            bands=[dict(band=b, description=d) for b, d in DEF_BANDS],
            grad_sigmas_px=list(GRAD_SIGMAS), coherence_bands=list(COHERENCE_BANDS),
            coherence_sigma=COHERENCE_SIGMA,
            transform="gems52.structural.normals (gradient magnitude) and "
                      "gems52.structural.coherence (structure coherence)",
            view_A2_channel_count=len(va2),
            caveat="a strain/seismicity lineament is a deformation hypothesis, not a fault "
                   "label; groundwater-withdrawal subsidence, irrigation-related aquifer "
                   "compaction, volcanic inflation/deflation, post-seismic afterslip and "
                   "seasonal hydrological loading produce similar strain/seismicity patterns"),
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return dict(added=added, skipped=skipped, n_features=len(names), view_A2_deformation=va2,
                view_A2_channel_count=len(va2))


def extend_store(store_dir: str | Path = "work/r2/features",
                 features: str | Path = "data/training_features.tif", log=print) -> dict:
    """Compute the deformation columns from the pinned feature raster and register them."""
    store = Path(store_dir)
    manifest = json.loads((store / "manifest.json").read_text())
    if "+external-geodawn-v1" not in manifest["version"]:
        raise SystemExit("the shared external extension has not run; "
                         "run: PYTHONPATH=src python -m gems52.external")
    if VERSION_TAG in manifest["version"] and "view_A2_deformation" in manifest:
        return dict(added=[], skipped=def_feature_names(),
                    n_features=len(manifest["feature_names"]),
                    view_A2_deformation=manifest["view_A2_deformation"],
                    view_A2_channel_count=len(manifest["view_A2_deformation"]),
                    already_extended=True)
    template = manifest["template"]
    valid = np.load(store / "valid.npy")
    columns: dict[str, np.ndarray] = {}
    with rasterio.open(features) as src:
        if (src.count != 19 or [src.height, src.width] != template["shape"]
                or str(src.crs) != template["crs"]
                or list(src.transform)[:6] != template["transform"]):
            raise ValueError("feature raster does not match the store template")
        for band, _desc in DEF_BANDS:
            a = src.read(band).astype(np.float32)
            a[~valid] = np.nan
            if not np.isfinite(a[valid]).all():
                raise ValueError(f"band {band} has nodata inside the eligible footprint")
            for name, values in deformation_columns(a, valid, band, log=log).items():
                columns[name] = values
            del a
            log(f"h72 deformation columns for band {band}")
    summary = register_columns(store, columns, log=log)
    summary["inputs"] = {"features_sha256": structural.digest(features)}
    return summary


if __name__ == "__main__":
    print(json.dumps(extend_store(log=lambda *a, **k: None), indent=1, default=str))
