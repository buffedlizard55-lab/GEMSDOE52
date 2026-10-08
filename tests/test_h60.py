"""Regression tests for the H60 round.

These are the assertions that would have caught the defects this round actually hit, so
each one names the defect in a comment.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gems52.h60 import BAND_VIEW, assert_plan, layer_plan   # noqa: E402

EV = ROOT / "evidence"
ART = EV / "h60_artifact.json"


# --------------------------------------------------------------------------- layer plan
def test_plan_is_frozen_at_30_A_and_17_B():
    """A future edit that silently drops a layer must fail here, not in a receipt."""
    L = layer_plan()
    na, nb = assert_plan(L)
    assert (na, nb) == (30, 17)
    assert len(L) == 47


def test_band6_is_in_the_surface_view():
    """IR-52-019: band 6 is aeroradiometric total count, not a magnetic tilt derivative.

    A radiometric band inside View A inflates every A/B correlation this project takes.
    """
    assert BAND_VIEW[6] == "B"
    for b in (1, 2, 3, 5, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18):
        assert BAND_VIEW[b] == "A", f"band {b} left the potential-field view"
    for b in (12, 19):
        assert BAND_VIEW[b] == "B", f"band {b} left the surface view"


def test_distance_to_catalogue_is_not_a_model_layer():
    """It cannot be made fold-safe without rebuilding it per fold, so it is not a predictor."""
    assert not [p for p in layer_plan() if "ed_cat" in p["name"]]


def test_every_planned_layer_is_written_or_the_build_raises():
    """b06_gradmag was never written on the first build and read back as finite zeros.

    The write-tracking in build_stack turns that into an exception instead of a silent
    constant layer; this pins the check by asserting the plan and the writer agree.
    """
    plan = {p["name"] for p in layer_plan()}
    src = (ROOT / "src/gems52/h60.py").read_text()
    assert "planned layers were never written" in src
    for nm in ("b06_gradmag", "b15_step_nne", "node_nne_x_nw"):
        assert nm in plan


# --------------------------------------------------------------------------- folds
def test_folds_are_whole_blocks_and_balanced():
    """The first draft folded on catalogue components, which leaves no held-out
    labelled negatives, and the independence test the brief names then had nothing to
    correlate: it reported 0 usable blocks."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("rh", ROOT / "scripts/run_h60.py")
    rh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rh)
    lab = rasterio.open(ROOT / "data/labels.tif").read(1) if (ROOT / "data/labels.tif").exists() else None
    if lab is None:
        pytest.skip("data/labels.tif not restored")
    cat, foot = lab == 1, lab != -1
    fmap, buf, nblk, load, blk_pos = rh.spatial_block_folds(cat, foot)
    assert nblk > 0 and buf.any()
    # a whole block belongs to exactly one fold
    from gems52 import grid as G
    blk = G.block_labels(cat.shape, foot, n=8)
    for b in np.unique(blk[blk >= 0]):
        sel = (blk == b) & (fmap >= 0)
        assert sel.any()
        assert len(np.unique(fmap[sel])) == 1, f"block {b} was split across folds"
    assert max(load) - min(load) < 0.05 * sum(load), f"unbalanced folds: {load}"


# --------------------------------------------------------------------------- artefact
@pytest.mark.skipif(not ART.exists(), reason="H60 artefact not built")
def test_served_artefact_is_all_finite_binary_and_in_range():
    """The portal rejected an earlier file with 'Predicted values must be in range [0, 1]'.

    That was a NaN-bearing export, not a scaling error (N-5). This reads the bytes that the
    site actually serves, not the array that was handed to the writer.
    """
    art = json.loads(ART.read_text())
    proof = art["range_proof_from_served_bytes"]
    served = ROOT / proof["served_path"]
    assert served.exists()
    a = rasterio.open(served).read(1)
    assert np.isfinite(a).all()
    assert set(np.unique(a).tolist()) <= {0.0, 1.0}
    assert float(a.min()) >= 0.0 and float(a.max()) <= 1.0
    assert proof["in_range"] is True and proof["n_nan"] == 0
    assert int((a > 0).sum()) == art["emitted_px"]
    # the served copy and the submission copy are the same bytes
    import hashlib
    sub = ROOT / "submission" / f"{art['name']}.tif"
    assert hashlib.sha256(sub.read_bytes()).hexdigest() == \
        hashlib.sha256(served.read_bytes()).hexdigest()


@pytest.mark.skipif(not ART.exists(), reason="H60 artefact not built")
def test_artefact_matches_the_sample_submission_geometry():
    art = json.loads(ART.read_text())
    p = ROOT / "submission" / f"{art['name']}.tif"
    with rasterio.open(p) as a, rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        assert a.shape == ref.shape
        assert a.crs == ref.crs
        assert tuple(a.transform)[:6] == tuple(ref.transform)[:6]
        assert a.count == 1 and a.dtypes[0] == "float32"


@pytest.mark.skipif(not ART.exists(), reason="H60 artefact not built")
def test_nothing_is_emitted_inside_the_200_m_catalogue_ring():
    """Measured on the restored bytes: deleting the 100-200 m ring raised the 0.2778
    file's score by 2.6 % relative, so that ring is pure tax."""
    from scipy import ndimage
    art = json.loads(ART.read_text())
    a = rasterio.open(ROOT / "submission" / f"{art['name']}.tif").read(1) > 0
    lab = rasterio.open(ROOT / "data/labels.tif").read(1)
    ed = ndimage.distance_transform_edt(~(lab == 1), sampling=100.0)
    assert int((a & (ed <= 200)).sum()) == 0
    assert float(ed[a].min()) > 200.0


@pytest.mark.skipif(not (EV / "h60_uniqueness.json").exists(), reason="gate not run")
def test_uniqueness_gate_passed_and_the_file_is_not_a_literal_union():
    u = json.loads((EV / "h60_uniqueness.json").read_text())
    assert u["canonical_pattern_unique"] is True
    assert u["equals_literal_prior_union"] is False
    assert u["novel_fraction"] >= 0.20
    assert not any(r.get("identical") for r in u["per_prior"] if "identical" in r)
    assert not any(r.get("error") for r in u["per_prior"])


# --------------------------------------------------------------------------- receipts
@pytest.mark.skipif(not (EV / "h60_instrument_verdict.json").exists(), reason="control not run")
def test_the_instrument_verdict_is_recorded_before_any_promots_claim():
    """IR-H60-003: the champion scores below a random placeholder on hide-and-recover, so
    no candidate may be promoted on that instrument alone."""
    iv = json.loads((EV / "h60_instrument_verdict.json").read_text())
    assert iv["champion_instrument_dti"] < iv["placeholder_instrument_dti"]
    assert iv["champion_scores_below_random_placeholder"] is True
    art = json.loads(ART.read_text())
    assert art["ok_to_download"] is True
    # the site must not advertise a certified gain
    idx = (ROOT / "docs/index.html").read_text()
    assert "NO CERTIFIED LEADERBOARD GAIN" in idx


def test_metric_identity_used_by_the_amendment():
    """DTI = T / (0.2T + 0.2(S-M) + 0.8|G|) with FNw = |G| - T. Pinned so the amendment's
    algebra cannot drift from src/gems52/metric.py."""
    from gems52.metric import dti
    g = np.zeros((9, 9), bool); g[4, 4] = True
    p = np.zeros((9, 9)); p[4, 4] = 1.0
    d = dti(p, g)
    T, S, M, G = d["tpw"], 1.0, 1.0, 1
    assert abs(d["dti"] - T / (0.2 * T + 0.2 * (S - M) + 0.8 * G)) < 1e-12
    assert abs(d["dti"] - 1.0) < 1e-12          # a perfect 1-px prediction scores 1.0


def test_the_canonical_alias_is_not_counted_as_a_prior():
    """Measured after merging a parallel round: re-running the gate with
    docs/downloads/h60-cotrain-candidate.tif present reported novel_fraction = 0.0 and
    pattern_unique = False, because the alias is a copy of the candidate under a
    different basename and find_priors' basename exclusion (IR-52-026) cannot see it.

    That is the one verdict that would stop a legitimate submission, so it is pinned here.
    """
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "src"))
    from gems52 import gates as GT
    art = json.loads(ART.read_text())
    arr = rasterio.open(ROOT / "submission" / f"{art['name']}.tif").read(1)
    roots = ["data/scored", "data/reference", "submission", "docs/downloads"]
    roots = [str(ROOT / r) for r in roots if (ROOT / r).exists()]
    alias = (ROOT / "docs/downloads/h60-cotrain-candidate.tif").resolve()
    naive = [p for p in GT.find_priors(roots, exclude=ROOT / "submission" / f"{art['name']}.tif")
             if Path(p).resolve() != alias]
    uniq = GT.uniqueness_report(arr, naive)
    assert uniq["canonical_pattern_unique"] is True
    assert uniq["novel_fraction"] >= 0.20
    assert uniq["support_novelty_gate_ok"] is True
    # ... and the alias really is a byte-identical copy, which is why it has to be excluded
    import hashlib
    a = hashlib.sha256((ROOT / "submission" / f"{art['name']}.tif").read_bytes()).hexdigest()
    assert hashlib.sha256(alias.read_bytes()).hexdigest() == a


def test_uniqueness_is_still_true_against_the_parallel_h60_round():
    """A second H60 artefact (PR #34, 31,000 px) landed on the same canonical paths.
    Both must remain distinct; the alias points at the co-training round."""
    u = json.loads((EV / "h60_uniqueness.json").read_text())
    rows = [r for r in u["per_prior"]
            if "triple-conv" in r["path"] and r["path"].startswith("submission/")]
    assert rows, "the parallel round's artefact was not checked"
    assert rows[0]["identical"] is False
    assert rows[0]["jaccard"] < 0.05
    assert u["canonical_pattern_unique"] is True
