from __future__ import annotations

import numpy as np
import rasterio
from rasterio.transform import from_origin

from scripts import run_h57_real as runner


def _write_grid(path, arr):
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1],
                       count=1, dtype="float32", crs="EPSG:32611",
                       transform=from_origin(243350, 4508550, 100, 100)) as dst:
        dst.write(arr.astype(np.float32), 1)
    return path


def test_prior_scan_passes_candidate_path_not_inventory_json(tmp_path, monkeypatch):
    """A freshly written submission must not be compared with itself as a prior."""
    root = tmp_path / "repo"
    evidence = root / "evidence"
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "EVIDENCE", evidence)
    template = _write_grid(root / "sample_submission.tif", np.ones((8, 8), np.float32))
    candidate = _write_grid(root / "submission" / "candidate.tif", np.eye(8, dtype=np.float32))
    prior = _write_grid(root / "data" / "prior.tif", np.fliplr(np.eye(8, dtype=np.float32)))
    seen = {}

    def find_priors(roots, exclude=None):
        seen["exclude"] = exclude
        return [prior]

    monkeypatch.setattr(runner.gates, "find_priors", find_priors)
    inventory_path = evidence / "inventory.json"
    paths, inventory = runner.scan_aligned_priors(
        template, inventory_path, exclude_candidate=candidate)

    assert paths == [prior]
    assert seen["exclude"] == candidate
    assert inventory_path.is_file()
    assert inventory["aligned_prior_path_count"] == 1
    assert all(str(row["path"]) != str(candidate) for row in inventory["aligned_files"])
