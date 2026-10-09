"""Shared extension: add the H62 step-normalised potential-field columns to the template store.

Why this is a *shared* module and not a round-private fork
---------------------------------------------------------
The parallel-run protocol says: reuse the template's cached feature stack, and if a shared tool
is missing something, fix it once in the template.  H61 measured the reason this extension
exists: a View A built from **raw** potential-field band values does not transfer between
quadrants (mean out-of-fold AUC 0.5163 against View B's 0.6843; in-sample 0.948), so the
Blum-Mitchell sufficiency premise failed and the A->B pseudo-label transfer handed over noise
(`evidence/h61_holdout.json`, `evidence/h61_fit_checkpoint.json`).  Raw band values are dominated
by regional trends and survey geometry; a learner keyed on them memorises the quadrant it was
fitted in.

What a buried fault actually produces in these fields is a **localised cross-strike step that
persists along strike**: a basement-depth offset (band 15 `depth_to_base_surf`), an isostatic
gravity step (band 13 `iso_grav_anom`) and a magnetic-fabric step (band 2 `rtp`).  The template
already owns a matched step filter for exactly this geometry -- ``structural.normal_profile``,
the paired-normal profile transform (detrended cross-normal step, flank balance, and along-tangent
persistence of |step|) -- but it was applied only to the DEM and tagged as a separate "H55"
view.  This module applies the same transform to the three subsurface fields and tags the result
View A, so H62's View A is a physically parameterised view with **no raw band values**.

Provenance and limits (stated, not implied)
------------------------------------------
* Bands are read from the SHA-256-pinned `data/training_features.tif` (owner mirror of a
  login-walled DrivenData file; pins prove mirror consistency, not organiser authentication).
* Band identities are the file's own descriptions, read from the restored bytes on 2026-10-09:
  13 `iso_grav_anom - Isostatic gravity anomaly`, 15 `depth_to_base_surf - Depth to basement
  surface - thickness of sedimentary cover`, 2 `rtp - Reduced to pole magnetic data`.
* The step transform is a geomorphic/geophysical hypothesis, not proof of a fault: a non-fault
  basin-fill density boundary or volcanic lithologic contact produces the same signature, and
  flight-line artefacts in the airborne survey appear as parallel linear steps that the
  persistence term only partially suppresses.
* Nothing here touches labels.  Every column is a function of the feature raster alone.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio

from . import structural

# (column tag, 1-based band index, physical description read from the file)
STEP_FIELDS = (
    ("grav", 13, "iso_grav_anom - isostatic gravity anomaly (subsurface density contrast)"),
    ("cover", 15, "depth_to_base_surf - depth to basement = sedimentary cover thickness"),
    ("rtp", 2, "rtp - reduced-to-pole magnetic (subsurface magnetic fabric)"),
)
STEP_OFFSETS_PX = (2, 4)          # 200 m and 400 m cross-normal sampling offsets
STEP_SIGMA = 3.0                  # smoothing scale of the template's normal_profile
VERSION_TAG = "+h62-step-v1"


def step_columns(field: np.ndarray, valid: np.ndarray, tag: str,
                 sigma: float = STEP_SIGMA, offsets=STEP_OFFSETS_PX) -> dict[str, np.ndarray]:
    """Matched step-filter columns for one subsurface field, via the template transform.

    For each offset this emits the detrended cross-normal signed step, its direction-insensitive
    magnitude, and the along-tangent persistence of |step| (faults are along-strike continuous;
    isolated noise is not).  One offset is processed at a time to bound peak memory on the
    12.28 Mpx competition grid.
    """
    out: dict[str, np.ndarray] = {}
    for off in offsets:
        signed_step, paired_flank, pair_balance, persistence = structural.normal_profile(
            field, valid, sigma=sigma, offsets_px=(float(off),))
        del paired_flank, pair_balance
        out[f"A_step_{tag}_signed_{off}px"] = signed_step
        out[f"A_step_{tag}_abs_{off}px"] = np.abs(signed_step).astype(np.float32)
        out[f"A_step_{tag}_persist_{off}px"] = persistence
        del signed_step, persistence
    return out


def step_feature_names() -> list[str]:
    """The 18 step columns, in (field, offset, kind) order."""
    return [f"A_step_{tag}_{kind}_{off}px"
            for tag, _b, _d in STEP_FIELDS
            for off in STEP_OFFSETS_PX
            for kind in ("signed", "abs", "persist")]


def view_A_h62_names(manifest: dict) -> list[str]:
    """H62's View A: step columns + template local-contrast A channels + external deep TMI.

    ``manifest["view_A"]`` holds the template's raw A bands *and* its derived A_* contrast
    channels; only the derived ones are retained (the raw bands are the channels H61 measured as
    non-transferring).  No ``raw_band_*`` name may appear — the caller asserts that.
    """
    step = set(step_feature_names())
    retained = {n for n in manifest["view_A"] if n.startswith("A_")}
    external = set(manifest.get("view_A_external", []))
    names = sorted(step | retained | external)
    if any(n.startswith("raw_band_") for n in names):
        raise ValueError("H62 View A must not contain raw band values")
    return names


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
            raise ValueError(f"nonfinite H62 feature inside eligible footprint: {name}")
        dest = store / (name + ".npy")
        if dest.exists() and name in hashes and structural.digest(dest) == hashes[name]:
            skipped.append(name)
            continue
        structural.save_array(dest, col)
        hashes[name] = structural.digest(dest)
        if name not in names:
            names.append(name)
        added.append(name)
        log(f"h62 feature {name}")
    va = view_A_h62_names({**manifest, "feature_names": names, "feature_sha256": hashes})
    vb = set(manifest["view_B_with_external"])
    overlap = sorted(set(va) & vb)
    if overlap:
        raise ValueError(f"H62 cross-view feature overlap: {overlap}")
    if any(n.startswith("raw_band_") for n in va):
        raise ValueError("H62 View A must not contain raw band values")
    manifest.update(
        version=(manifest["version"] + VERSION_TAG
                 if VERSION_TAG not in manifest["version"] else manifest["version"]),
        feature_names=names, feature_sha256=hashes,
        view_A_h62=va,
        h62_step=dict(fields=[dict(tag=t, band=b, description=d) for t, b, d in STEP_FIELDS],
                      offsets_px=list(STEP_OFFSETS_PX), sigma=STEP_SIGMA,
                      transform="gems52.structural.normal_profile (detrended cross-normal step, "
                                "|step| magnitude, along-tangent persistence of |step|)",
                      view_A_channel_count=len(va),
                      raw_bands_in_view_A=0,
                      caveat="step/persistence of a potential-field channel is a structural "
                             "hypothesis, not a fault label; a basin-fill density boundary or "
                             "volcanic lithologic contact produces the same signature"),
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return dict(added=added, skipped=skipped, n_features=len(names), view_A_h62=va,
                view_A_channel_count=len(va))


def extend_store(store_dir: str | Path = "work/r2/features",
                 features: str | Path = "data/training_features.tif", log=print) -> dict:
    """Compute the step columns from the pinned feature raster and register them."""
    store = Path(store_dir)
    manifest = json.loads((store / "manifest.json").read_text())
    if not manifest["version"].endswith("+external-geodawn-v1"):
        raise SystemExit("the shared external extension has not run; "
                         "run: PYTHONPATH=src python -m gems52.external")
    if VERSION_TAG in manifest["version"] and "view_A_h62" in manifest:
        return dict(added=[], skipped=step_feature_names(), n_features=len(manifest["feature_names"]),
                    view_A_h62=manifest["view_A_h62"],
                    view_A_channel_count=len(manifest["view_A_h62"]), already_extended=True)
    template = manifest["template"]
    valid = np.load(store / "valid.npy")
    columns: dict[str, np.ndarray] = {}
    with rasterio.open(features) as src:
        if (src.count != 19 or [src.height, src.width] != template["shape"]
                or str(src.crs) != template["crs"]
                or list(src.transform)[:6] != template["transform"]):
            raise ValueError("feature raster does not match the store template")
        for tag, band, _desc in STEP_FIELDS:
            a = src.read(band).astype(np.float32)
            a[~valid] = np.nan
            if not np.isfinite(a[valid]).all():
                raise ValueError(f"band {band} has nodata inside the eligible footprint")
            for name, values in step_columns(a, valid, tag).items():
                columns[name] = values
            del a
            log(f"h62 step columns for {tag} (band {band})")
    summary = register_columns(store, columns, log=log)
    summary["inputs"] = {"features_sha256": structural.digest(features)}
    return summary


if __name__ == "__main__":
    print(json.dumps(extend_store(log=lambda *a, **k: None), indent=1, default=str))
