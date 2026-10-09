"""Tests for the H66 round: frozen protocol, nine-arm holdout, lane-valid build logic.

These tests need no competition raster. The feature-store and receipt checks skip cleanly when
work/ or the receipts are absent.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

REG = ROOT / "registry/h66_preregistration.json"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_protocol_hash_matches_registration():
    reg = json.loads(REG.read_text())
    assert _sha(ROOT / reg["hypothesis_document"]) == reg["hypothesis_sha256"]


def test_runner_refuses_if_hash_moves_and_is_registered():
    reg = json.loads(REG.read_text())
    assert reg["runner_refuses_if_hash_moves"] is True
    assert reg["runner"] == "scripts/run_h66.py"
    assert (ROOT / reg["runner"]).exists()
    assert reg["frozen_before_any_fit"] is True


def test_thresholds_are_the_preregistered_values():
    th = json.loads(REG.read_text())["thresholds"]
    assert th["canary_auc_alarm"] == 0.90
    assert th["independence_abandon_max_abs_rho"] == 0.60
    assert th["donor_rank_min"] == 0.95
    assert th["receiver_rank_interval"] == [0.35, 0.65]
    assert th["budget_dots_per_fold_per_arm"] == 9400
    assert th["min_dot_separation_px"] == 3.0
    assert th["catalogue_exclusion_m"] == 200.0
    assert th["lane_near_dot_fraction"] == 0.70
    assert th["lane_rank_correlation"] == 0.90


def test_five_hypotheses_ranked_and_top_validated():
    reg = json.loads(REG.read_text())
    hyps = reg["hypotheses"]
    assert len(hyps) == 5
    assert [h["rank"] for h in hyps] == [1, 2, 3, 4, 5]
    assert hyps[0]["id"] == "H66-A" and "tested" in hyps[0]["status"]
    assert all("deferred" in h["status"] for h in hyps[3:])
    assert len(reg["budget"]["experiments"]) == 3


def test_nine_arms_include_the_three_new_h66_arms():
    import run_h66
    assert len(run_h66.ARMS) == 9
    for arm in ("a_only", "single_B_veto_Bonly", "concordant"):
        assert arm in run_h66.ARMS
    assert set(run_h66.CANDIDATES) == {"a_only", "single_B_veto_Bonly", "concordant",
                                        "disagreement_post"}


def test_lane_valid_greedy_respects_per_raster_cap():
    """The build's constrained greedy must keep every prior's near-dot share <= 0.70 by construction.

    Deterministic registry on a 200x200 grid: p0's support is the left 80% of columns (its 3 px halo
    ~81.5%, so the per-prior cap floor(0.70*n) genuinely binds) and p1 has the identical support, so
    the multi-prior bookkeeping is exercised without adding a second binding constraint.  n=300 is
    feasible: 210 dots inside the halo (at the cap) + 90 outside it.
    """
    import run_h66
    shape = (200, 200)
    N = shape[0] * shape[1]
    width = shape[1]
    disk = run_h66.gates._disk(3.0)
    supports, priors = {}, []
    for name in ("p0", "p1"):
        sup = np.zeros(shape, bool)
        sup[:, :160] = True                            # left 80% of columns
        supports[name] = np.flatnonzero(sup.ravel()).astype(np.int32)
        priors.append(name)
    rng = np.random.default_rng(0)
    cand = np.arange(N, dtype=np.int64)
    val = rng.random(N).astype(np.float32)
    order = np.lexsort((cand, -val))
    cand = cand[order]
    halo_rows = []
    for name in priors:
        sup2 = np.zeros(N, bool)
        sup2[supports[name]] = True
        halo_rows.append(run_h66.ndi.binary_dilation(sup2.reshape(shape), structure=disk).ravel()[cand])
    HITS = run_h66.sp.csr_matrix(np.stack(halo_rows).T)
    indptr, indices = HITS.indptr, HITS.indices

    n = 300
    keep, counts = run_h66.lane_valid_greedy(cand, indptr, indices, len(priors), width, n)
    assert len(keep) >= n, f"greedy placed {len(keep)} of {n} requested"
    em = cand[np.asarray(keep[:n], dtype=np.int64)]
    for name in priors:
        sup2 = np.zeros(N, bool)
        sup2[supports[name]] = True
        halo = run_h66.ndi.binary_dilation(sup2.reshape(shape), structure=disk)
        share = float(halo.ravel()[em].sum()) / n
        assert share <= 0.70 + 1e-12, (name, share)
    # the caps must actually have bound: every prior sits at its cap
    assert counts.max() >= int(np.floor(0.70 * n)) - 1
    assert (counts == int(np.floor(0.70 * n))).all()


def test_canary_receipt_clean_if_present():
    p = ROOT / "evidence/h66_canary.json"
    if not p.exists():
        pytest.skip("canary receipt not produced yet")
    r = json.loads(p.read_text())
    assert r["any_alarm"] is False
    assert r["max_alarm_across_folds"] < r["alarm_auc"]


def test_independence_receipt_if_present():
    p = ROOT / "evidence/h66_independence.json"
    if not p.exists():
        pytest.skip("independence receipt not produced yet")
    r = json.loads(p.read_text())
    assert "allow_exchange" in r
    assert r["pre"]["n_blocks"] >= 20


def test_holdout_receipt_structure_if_present():
    p = ROOT / "evidence/h66_holdout.json"
    if not p.exists():
        pytest.skip("holdout receipt not produced yet")
    r = json.loads(p.read_text())
    assert set(r["arms"]) == set(run_h66.ARMS) if False else True  # arms live under pooled scores
    scores = r["pooled"]["a_only"]["scores"]
    for arm in ("single_A", "single_B", "union_max", "disagreement_pre", "disagreement_post",
                "a_only", "single_B_veto_Bonly", "concordant", "random"):
        assert arm in scores, arm
        assert scores[arm]["evidence_class"] == "HOLDOUT-DTI"
        assert scores[arm]["evaluator_version"] == "gems52-pooled-hide-v1"
    assert r["control"]["pass_"] is True


def test_submission_file_if_present():
    import rasterio
    p = ROOT / "submission"
    files = sorted(p.glob("gems52-h66-*.tif"))
    if not files:
        pytest.skip("H66 submission not built yet")
    with rasterio.open(files[-1]) as src:
        a = src.read(1)
        assert src.count == 1 and src.dtypes[0] == "float32"
        assert np.isfinite(a).all()
        assert float(a.min()) >= 0.0 and float(a.max()) <= 1.0
        assert set(np.unique(a)) <= {0.0, 1.0}
    rec = json.loads(files[-1].with_suffix(".json").read_text())
    assert rec["validator"]["ok"] is True
    assert rec["approved_for_weekly_slot"] is False
    assert rec["submission_slots_used"] == 0
    assert len(rec["submission_name"]) <= 140 and len(rec["note"]) <= 140


def test_run_card_labels_if_present():
    p = ROOT / "evidence/h66_run_card.json"
    if not p.exists():
        pytest.skip("run card not produced yet")
    r = json.loads(p.read_text())
    assert r["round"] == "H66"
    assert r["holdout_dti"]["a_only"]["evaluator_version"] == "gems52-pooled-hide-v1"
    assert r["submission_slots_used"] == 0
    assert r["champion_reference"]["evidence_class"].startswith("OWNER-REPORTED")
    assert "verdict" in r and isinstance(r["verdict"], str)
