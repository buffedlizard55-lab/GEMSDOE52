"""Shared extension: add the pinned external GeoDAWN layers to the template feature store.

Why this is a *shared* module and not a round-private fork
----------------------------------------------------------
The parallel-run protocol says: reuse the template's cached feature stack, and if a shared
tool is missing something, fix it once in the template.  Every co-training round so far
(H55-H60, CTD5) built View A and View B from ``training_features.tif`` alone, so the two
views were not as physically separated as the method needs:

* View A ("potential field / subsurface") mixed *shallow* magnetic anomalies with deep ones.
  The upward-continued TMI (150 m) in the pinned external layer suppresses near-surface
  sources and is the cleanest "deep" channel available.
* View B ("surface") had exactly one radiometric channel, band 6, whose identity was disputed
  for three rounds.  ``scripts/h61_forensics.py`` settles it on the bytes: band 6 is
  rank-identical (Spearman rho = 1.0000) to the external GeoDAWN **TC** grid and essentially
  uncorrelated with the tilt angle of TMI (rho = 0.0175) or TMI horizontal gradient
  (rho = -0.1512).  So band 6 is radiometric total count and belongs in View B, and the
  remaining radiometric channels (K, Th, U and the Th/K, U/K, U/Th ratios) are the surface
  alteration channels that View B was missing.

Provenance (stated, not implied)
--------------------------------
The external rasters are ``registry/data_manifest.json`` entries restored by
``scripts/restore_data.py`` and verified by SHA-256 and byte count.  They were derived by the
owner's CI from the USGS GeoDAWN data release (DOI 10.5066/P93LGLVQ,
https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and)
and are uint8 1st-99th-percentile quantisations.  They are integrity-pinned mirror bytes, NOT
bytes fetched from USGS in this session, and their absolute units are therefore unauthenticated.
Rank/gradient features are invariant to any monotone re-quantisation, which is why they are used.

Nothing here touches labels.  Every column is a function of the external raster alone.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

from . import structural

# (column prefix, external file, band index, view, physical description)
LAYERS = (
    ("X_rad_K", "geodawn_rad_u8.tif", 1, "BX", "potassium, airborne gamma-ray spectrometry"),
    ("X_rad_Th", "geodawn_rad_u8.tif", 2, "BX", "thorium, airborne gamma-ray spectrometry"),
    ("X_rad_U", "geodawn_rad_u8.tif", 3, "BX", "uranium, airborne gamma-ray spectrometry"),
    ("X_rad_ThK", "geodawn_extensions_u8.tif", 1, "BX", "Th/K ratio (alteration index)"),
    ("X_rad_UK", "geodawn_extensions_u8.tif", 2, "BX", "U/K ratio (alteration index)"),
    ("X_rad_UTh", "geodawn_extensions_u8.tif", 3, "BX", "U/Th ratio (alteration index)"),
    ("X_mag_TMI_up150", "geodawn_extensions_u8.tif", 4, "AX",
     "total magnetic intensity upward continued 150 m (deep sources)"),
)
# external TC (geodawn_rad_u8 band 4) is deliberately NOT added: it is rank-identical to
# training_features band 6 (Spearman 1.0000, measured by scripts/h61_forensics.py), so adding
# it would double-weight one channel and inflate View B without adding information.
EXCLUDED = {"geodawn_rad_u8.tif:TC": "rank-identical to training_features band 6 (rho=1.0000)"}
GRAD_SIGMAS = (1.0, 3.0)


def extend_store(store_dir: str | Path = "work/r2/features",
                 external_dir: str | Path = "data/external",
                 log=print) -> dict:
    """Append external-layer columns to an existing structural feature store.

    Idempotent: a column whose SHA-256 already matches the manifest is not recomputed.
    Returns the updated manifest.
    """
    store = Path(store_dir)
    external_dir = Path(external_dir)
    manifest_path = store / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    valid = np.load(store / "valid.npy")
    flat_idx = np.load(store / "flat_idx.npy")
    if not np.array_equal(flat_idx, np.flatnonzero(valid.ravel())):
        raise ValueError("store index mapping corrupted; rebuild the feature stack")
    template = manifest["template"]
    hashes = dict(manifest["feature_sha256"])
    names = list(manifest["feature_names"])
    view_ax = list(manifest.get("view_A_external", []))
    view_bx = list(manifest.get("view_B_external", []))
    added, skipped, coverage = [], [], {}

    for prefix, fname, band, view, meaning in LAYERS:
        path = external_dir / fname
        if not path.exists():
            raise FileNotFoundError(
                f"external layer {path} missing; run scripts/restore_data.py --only "
                f"ext_geodawn_rad_u8,ext_geodawn_extensions_u8")
        with rasterio.open(path) as src:
            if src.shape != tuple(template["shape"]) or str(src.crs) != template["crs"] \
                    or list(src.transform)[:6] != template["transform"]:
                raise ValueError(f"{fname} is not on the competition grid {template}")
            raw = src.read(band).astype(np.float32)
            descr = src.descriptions[band - 1]
        if descr and not prefix.endswith(descr):
            # the band description must agree with the pinned layer table, else the table is wrong
            raise ValueError(f"band {band} of {fname} is '{descr}', not the expected "
                             f"'{prefix.rsplit('_', 1)[-1]}'")
        nodata = raw == 0
        a = np.where(nodata, np.nan, raw)
        # every column must be finite on the *eligible* (support-eroded) domain
        if not np.isfinite(a[valid]).all():
            raise ValueError(f"{prefix}: external nodata inside the eligible footprint")
        coverage[prefix] = dict(
            nodata_px_all=int(nodata.sum()), nodata_px_in_eligible=int((nodata & valid).sum()),
            finite_px_in_eligible=int((~nodata & valid).sum()),
            min_in_eligible=float(np.nanmin(a[valid])), max_in_eligible=float(np.nanmax(a[valid])),
            mean_in_eligible=float(np.nanmean(a[valid])), description=descr, meaning=meaning)

        def put(name: str, values: np.ndarray) -> None:
            col = np.asarray(values, np.float32).ravel()[flat_idx]
            if not np.isfinite(col).all():
                raise ValueError(f"nonfinite external feature inside eligible footprint: {name}")
            dest = store / (name + ".npy")
            if dest.exists() and name in hashes and structural.digest(dest) == hashes[name]:
                skipped.append(name)
                return
            structural.save_array(dest, col)
            hashes[name] = structural.digest(dest)
            if name not in names:
                names.append(name)
            bucket = view_ax if view == "AX" else view_bx
            if name not in bucket:
                bucket.append(name)
            added.append(name)
            log(f"external feature {name}")

        scaled = (a - np.nanmin(a[valid])) / max(1e-9, float(np.nanmax(a[valid]) - np.nanmin(a[valid])))
        put(f"{prefix}_rank", np.clip(np.nan_to_num(scaled, nan=0.0), 0.0, 1.0))
        for sigma in GRAD_SIGMAS:
            _, _, mag, _ = structural.normals(a, valid, sigma)
            put(f"{prefix}_grad{int(sigma)}", mag)
        del raw, a, nodata, scaled

    manifest.update(
        version=manifest["version"] + "+external-geodawn-v1"
        if "+external-geodawn-v1" not in manifest["version"] else manifest["version"],
        feature_names=names, feature_sha256=hashes,
        view_A_external=sorted(set(view_ax)), view_B_external=sorted(set(view_bx)),
        view_A_with_external=sorted(set(manifest["view_A"]) | set(view_ax)),
        view_B_with_external=sorted(set(manifest["view_B"]) | set(view_bx)),
        external_data_used=True,
        external_layers=coverage,
        external_excluded=EXCLUDED,
        external_provenance=(
            "uint8 1st-99th percentile quantisations derived by the owner's CI from the USGS "
            "GeoDAWN release DOI 10.5066/P93LGLVQ; restored from SHA-256-pinned mirrors by "
            "scripts/restore_data.py, NOT fetched from USGS in this session; absolute units "
            "unauthenticated, so only rank and gradient transforms are used."),
        radiometric_bands_present=("training_features band 6 (rank-identical to external TC, "
                                   "Spearman 1.0000) plus external K, Th, U, Th/K, U/K, U/Th"),
        band6_policy=("B only. Identity resolved on the bytes by scripts/h61_forensics.py: "
                      "radiometric total count, not a magnetic tilt angle."),
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return dict(added=added, skipped=skipped, n_features=len(names),
                view_A_external=manifest["view_A_external"],
                view_B_external=manifest["view_B_external"], coverage=coverage)


if __name__ == "__main__":
    print(json.dumps(extend_store(log=lambda *a, **k: None), indent=1, default=str))
