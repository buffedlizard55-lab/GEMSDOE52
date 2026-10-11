"""H61 regressions: the repaired lane gate must mean what the receipts say it means.

Three things are pinned here, because each one silently changed a verdict in this project's
history:

1. ``registry_coverage`` really does classify a spacing-five lattice as a universal-coverage probe
   and a sparse detector as informative (IR-H61-005).
2. ``lane_report`` reports the literal rule and the saturation-aware policy *side by side*, but the
   literal all-prior result is authoritative: a policy PASS cannot waive a probe-triggered STOP.
3. The analytic binary Spearman equals scipy's tie-aware Spearman, so the fast path is exact and not
   an approximation.

Plus two receipt guards: the |G| interval must exclude the superseded point value (IR-H61-001), and
the shipped H61 artefact must be portal-safe if it exists.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from scipy.stats import spearmanr

from gems52 import gates

ROOT = Path(__file__).resolve().parents[1]


def write_tif(dirpath, name, arr):
    p = Path(dirpath) / name
    prof = dict(driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1, dtype="float32",
                crs="EPSG:32611", transform=from_origin(0.0, float(arr.shape[0]), 1.0, 1.0))
    with rasterio.open(p, "w", **prof) as d:
        d.write(arr, 1)
    return p


def lattice(shape, step):
    a = np.zeros(shape, np.float32)
    a[::step, ::step] = 1.0
    return a


def test_registry_coverage_separates_probes_from_informative_priors():
    eligible = np.ones((120, 120), bool)
    probe = gates.registry_coverage(lattice((120, 120), 5) > 0, eligible, 3.0)
    informative = gates.registry_coverage(lattice((120, 120), 20) > 0, eligible, 3.0)
    assert probe >= gates.PROBE_COVERAGE, probe
    assert informative < gates.PROBE_COVERAGE, informative
    # a spacing-5 square lattice has maximum interior distance sqrt(8) < 3 px, so coverage is total
    assert gates.registry_coverage(np.zeros((120, 120), bool), eligible, 3.0) == 0.0


def test_lane_report_keeps_literal_and_policy_verdicts_separate(tmp_path):
    shape = (120, 120)
    eligible = np.ones(shape, bool)
    sample = write_tif(tmp_path, "sample.tif", np.zeros(shape, np.float32))
    probe = write_tif(tmp_path, "probe.tif", lattice(shape, 5))
    cand = np.zeros(shape, np.float32)
    cand[10, 10] = cand[40, 70] = cand[95, 25] = 1.0
    rep = gates.lane_report(cand, eligible, [probe], sample=sample, phase="dots")
    row = rep["per_prior"][0]
    assert row["universal_coverage_probe"] is True
    assert row["near_3px_fraction"] == pytest.approx(1.0)
    # The literal rule fires on the probe; the sensitivity-only policy pass cannot waive it.
    assert rep["literal"]["verdict"] == "DUPLICATE/STOP"
    assert rep["policy"]["verdict"] == "PASS"
    assert rep["policy"]["universal_coverage_probes"] == 1
    assert rep["strict_ok"] is False and rep["ok"] is False
    assert rep["duplicate"] is True and rep["literal_stop"] is True
    assert rep["policy_ok"] is True and rep["policy_duplicate"] is False
    with pytest.raises(gates.LaneRuleStop, match="policy-only results cannot waive"):
        gates.require_literal_lane(rep, context="synthetic lattice test")


def test_lane_report_stops_on_an_informative_copy_and_on_an_identical_decode(tmp_path):
    shape = (120, 120)
    eligible = np.ones(shape, bool)
    sample = write_tif(tmp_path, "sample.tif", np.zeros(shape, np.float32))
    prior = np.zeros(shape, np.float32)
    prior[::20, ::20] = 1.0
    prior_path = write_tif(tmp_path, "prior.tif", prior)
    same = gates.lane_report(prior, eligible, [prior_path], sample=sample, phase="dots")
    assert same["per_prior"][0]["identical"] is True
    assert same["literal"]["verdict"] == "DUPLICATE/STOP"
    assert same["policy"]["verdict"] == "DUPLICATE/STOP"
    assert same["duplicate"] is True and same["ok"] is False
    shifted = prior.copy()
    shifted[:] = 0.0
    ys, xs = np.nonzero(prior > 0)
    shifted[ys + 1, xs] = 1.0            # every dot moved 1 px: still within 3 px
    rep = gates.lane_report(shifted, eligible, [prior_path], sample=sample, phase="dots")
    assert rep["per_prior"][0]["near_3px_fraction"] == pytest.approx(1.0)
    assert rep["policy"]["verdict"] == "DUPLICATE/STOP"


def test_require_literal_lane_accepts_an_actual_all_prior_pass(tmp_path):
    shape = (120, 120)
    eligible = np.ones(shape, bool)
    sample = write_tif(tmp_path, "sample.tif", np.zeros(shape, np.float32))
    prior = np.zeros(shape, np.float32)
    prior[::20, ::20] = 1.0
    candidate = np.zeros(shape, np.float32)
    candidate[10::20, 10::20] = 1.0
    prior_path = write_tif(tmp_path, "prior.tif", prior)

    rep = gates.lane_report(candidate, eligible, [prior_path], sample=sample, phase="dots")
    assert rep["literal"]["verdict"] == "PASS"
    assert rep["strict_ok"] is True and rep["policy_ok"] is True
    assert gates.require_literal_lane(rep, context="synthetic clear case") is True


def test_binary_spearman_is_exact_not_approximated(tmp_path):
    shape = (60, 60)
    eligible = np.ones(shape, bool)
    sample = write_tif(tmp_path, "sample.tif", np.zeros(shape, np.float32))
    rng = np.random.default_rng(61)
    prior = (rng.random(shape) < 0.05).astype(np.float32)
    prior_path = write_tif(tmp_path, "prior.tif", prior)
    cand = (rng.random(shape) < 0.05).astype(np.float32)
    rep = gates.lane_report(cand, eligible, [prior_path], sample=sample, phase="dots")
    got = rep["per_prior"][0]["spearman"]
    want = spearmanr(cand[eligible], prior[eligible]).statistic
    assert got == pytest.approx(want, abs=1e-9)


def test_g_interval_excludes_the_superseded_point_value():
    p = ROOT / "evidence/h61_forensics.json"
    if not p.exists():
        pytest.skip("forensics receipt not built in this checkout")
    d = json.loads(p.read_text())
    g = d["G_identification"]["masked"]
    assert g["G_lower_bound"] < g["G_upper_bound"]
    assert g["G_upper_bound"] < d["G_point_under_zero_ring_credit"]["G_px"], (
        "IR-H61-001: the published point |G| must stay outside the rigorous interval")
    assert d["masked_accounting_witness"]["off_catalogue_support_identical"] is True
    assert d["masked_accounting_witness"]["T_under_masked_accounting"][0] == pytest.approx(
        d["masked_accounting_witness"]["T_under_masked_accounting"][1], rel=1e-9)
    assert d["masked_accounting_witness"]["T_under_raw_accounting"][0] != pytest.approx(
        d["masked_accounting_witness"]["T_under_raw_accounting"][1], rel=1e-3)
    assert d["band6_identity"]["best_external_match"]["name"] == "TC"
    assert d["band6_identity"]["best_external_match"]["spearman"] > 0.999


def test_h61_artefact_is_portal_safe_if_present():
    sample = ROOT / "data/sample_submission.tif"
    cands = sorted((ROOT / "submission").glob("gems52-h61-*.tif"))
    if not cands or not sample.exists():
        pytest.skip("H61 artefact or pinned sample not present in this checkout")
    path = cands[-1]
    rep = gates.format_report(path, sample, footprint=None)
    assert rep["ok"], rep["problems"]
    assert rep["nan_pixels"] == 0 and rep["infinity_pixels"] == 0
    assert rep["min"] >= 0.0 and rep["max"] <= 1.0
    assert rep["bands"] == 1 and rep["dtype"] == "float32"
    with rasterio.open(path) as src:
        a = src.read(1)
    assert set(np.unique(a)).issubset({0.0, 1.0})
    zip_path = path.with_suffix(".zip")
    if zip_path.exists():
        import zipfile
        with zipfile.ZipFile(zip_path) as z:
            assert z.namelist() == [path.name]
            assert z.read(path.name) == path.read_bytes()
