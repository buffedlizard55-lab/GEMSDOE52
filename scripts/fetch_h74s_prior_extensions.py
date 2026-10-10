#!/usr/bin/env python3
"""Fetch the current public prediction rasters from the user's listed GEMSDOE53–57 repos.

The frozen ctd5 owner-repository census in this checkout ends at 2026-10-08 and does not include
all H53–H57 commits. This extension uses only api.github.com for the user's named public GitHub
repos, pins each retrieved branch commit/blob in a compact evidence receipt, and stores decoded
GeoTIFFs under ignored work/. It is a uniqueness registry extension, never model input.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("restore_data", ROOT / "scripts" / "restore_data.py")
restore_data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore_data)

REPOS = (
    "buffedlizard55-lab/GEMSDOE53",
    "buffedlizard55-lab/GEMSDOE54",
    "buffedlizard55-lab/55GEMSDOE",
    "buffedlizard55-lab/56GEMSDOE",
    "buffedlizard55-lab/57GEMSDOE",
)
INCLUDE_PREFIXES = (
    "docs/downloads/", "docs/submissions/", "submissions/", "submission/", "downloads/",
    "evidence/historical_artifacts/", "registry/registry_rasters/", "registry/rasters/", "archive/",
)
EXCLUDED_NAMES = {
    "labels.tif", "existing_faults.tif", "sample_submission.tif",
    "example_submission.tif", "mirror_sample_submission_template.tif",
}


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def decoded_sha(path: Path) -> str:
    """Fingerprint the exact float32 pattern used by the shared registry canonicalizer."""
    with rasterio.open(path) as src:
        a = np.asarray(src.read(1), dtype="<f4")
    a = np.where(np.isfinite(a) & (a >= 0) & (a <= 1), a, 0).astype("<f4")
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def git_blob_sha(path: Path) -> str:
    """Verify the fetched bytes against the Git tree's content-addressed blob SHA-1."""
    size = path.stat().st_size
    h = hashlib.sha1()
    h.update(("blob " + str(size) + chr(0)).encode("ascii"))
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def candidate_path(path: str) -> bool:
    p = path.lower()
    if not p.endswith((".tif", ".tiff")) or Path(p).name in EXCLUDED_NAMES:
        return False
    if p.startswith("data/") or "/data/" in p:
        return False
    return any(p.startswith(prefix) for prefix in INCLUDE_PREFIXES)


def main() -> int:
    sample = ROOT / "data/sample_submission.tif"
    if not sample.is_file():
        raise SystemExit("missing data/sample_submission.tif; restore the hash-pinned core data first")
    with rasterio.open(sample) as ref:
        ref_meta = (ref.shape, ref.crs, ref.transform)

    out_dir = ROOT / "work/h74s/extra_priors"
    out_dir.mkdir(parents=True, exist_ok=True)
    records, errors = [], []
    for repo in REPOS:
        repo_info = restore_data.api_json(f"https://api.github.com/repos/{repo}")
        branch = repo_info["default_branch"]
        commit = restore_data.api_json(f"https://api.github.com/repos/{repo}/commits/{branch}")["sha"]
        tree = restore_data.api_json(f"https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1")
        if tree.get("truncated"):
            errors.append({"repo": repo, "error": "GitHub returned a truncated tree"})
            continue
        files = [entry for entry in tree.get("tree", [])
                 if entry.get("type") == "blob" and candidate_path(entry.get("path", ""))]
        print(f"{repo}@{commit[:10]}: {len(files)} prediction-raster paths")
        for entry in files:
            dest = out_dir / repo.split("/")[-1] / f"{entry['sha']}.tif"
            try:
                if not dest.is_file() or dest.stat().st_size != entry.get("size", 0):
                    restore_data.stream_blob(repo, entry["sha"], dest, int(entry["size"]))
                actual_blob_sha = git_blob_sha(dest)
                if actual_blob_sha != entry["sha"]:
                    raise ValueError(f"Git blob SHA mismatch: {actual_blob_sha} != {entry['sha']}")
                with rasterio.open(dest) as src:
                    meta = (src.shape, src.crs, src.transform)
                    count = src.count
                aligned = bool(count == 1 and meta == ref_meta)
                rec = {
                    "repo": repo,
                    "branch": branch,
                    "commit": commit,
                    "path": entry["path"],
                    "blob_sha": entry["sha"],
                    "git_blob_sha_matches": True,
                    "bytes": int(entry["size"]),
                    "file_sha256": file_sha(dest),
                    "decoded_sha256": decoded_sha(dest),
                    "bands": int(count),
                    "shape": list(meta[0]),
                    "crs": str(meta[1]) if meta[1] is not None else None,
                    "transform": list(meta[2])[:6],
                    "aligned_single_band": aligned,
                    "local_path": str(dest.relative_to(ROOT)),
                    "evidence_class": "PUBLIC OWNER-GITHUB RASTER; not organizer-authenticated",
                }
                records.append(rec)
            except Exception as exc:  # one inaccessible/bad public object must be visible
                errors.append({"repo": repo, "path": entry.get("path"),
                               "blob_sha": entry.get("sha"),
                               "error": f"{type(exc).__name__}: {str(exc)[:240]}"})
                print(f"  ERROR {entry.get('path')}: {type(exc).__name__}: {str(exc)[:120]}")

    eligible = [r for r in records if r["aligned_single_band"]]
    receipt = {
        "generated_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(timespec="seconds"),
        "source": "api.github.com; public owner repositories listed by the user; exact branch commits and Git blob SHAs recorded",
        "scope": "H53–H57 named repositories, submission/download/archive/registry-raster paths only; competition data paths excluded",
        "organizer_authenticated": False,
        "n_repos": len(REPOS),
        "n_prediction_raster_paths": len(records) + len(errors),
        "n_downloaded_and_decoded": len(records),
        "n_aligned_single_band": len(eligible),
        "n_errors": len(errors),
        "errors": errors,
        "files": records,
    }
    p = ROOT / "evidence/h74s_prior_extension.json"
    p.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: receipt[k] for k in (
        "generated_utc", "n_repos", "n_prediction_raster_paths", "n_downloaded_and_decoded",
        "n_aligned_single_band", "n_errors")}, indent=2))
    print(f"receipt={p.relative_to(ROOT)}")
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
