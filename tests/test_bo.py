"""The slot gate: only a candidate that beats the incumbent, clears its expected improvement over
the cost of a slot, and is not a repeat may spend one of the three weekly submissions."""
import numpy as np
import pytest

from gems52 import bo


def test_gp_surrogate_learns_a_smooth_function_and_reports_uncertainty():
    rng = np.random.default_rng(0)
    X = rng.random((40, 2))
    y = np.sin(3 * X[:, 0]) + X[:, 1] ** 2
    gp = bo.GPSurrogate().fit(X, y)
    mu, sd = gp.predict(X)
    assert np.mean((mu - y) ** 2) < 1e-3              # interpolates the design points
    mu2, sd2 = gp.predict(np.array([[0.5, 0.5], [5.0, 5.0]]))
    assert sd2[1] > sd2[0]                             # far from the data -> more uncertainty


def test_expected_improvement_ranks_the_promising_point_first():
    mu = np.array([0.10, 0.30])
    sd = np.array([0.05, 0.05])
    ei = bo.expected_improvement(mu, sd, best=0.12)
    assert ei[1] > ei[0]


def test_slot_gate_refuses_a_candidate_that_has_not_beaten_the_incumbent():
    d = bo.slot_gate([{"design_id": "x", "holdout": 0.0990, "ei": 0.02}], incumbent=0.0992)
    assert not d.approved and "holdout" in " ".join(d.reasons)


def test_slot_gate_refuses_when_expected_improvement_is_below_the_slot_cost():
    d = bo.slot_gate([{"design_id": "x", "holdout": 0.20, "ei": 1e-6}], incumbent=0.10)
    assert not d.approved and any("improvement" in r for r in d.reasons)


def test_slot_gate_refuses_a_repeat_and_a_broken_file():
    base = {"design_id": "x", "holdout": 0.20, "ei": 0.05}
    assert not bo.slot_gate([{**base, "already_live": True}], incumbent=0.10).approved
    assert not bo.slot_gate([{**base, "format_ok": False}], incumbent=0.10).approved


def test_slot_gate_approves_a_clean_winner_and_rho_lowers_the_bar_for_discovery():
    cand = {"design_id": "y", "holdout": 0.1010, "ei": 0.05}
    assert bo.slot_gate([cand], incumbent=0.0992).approved
    marginal = {"design_id": "z", "holdout": 0.09950, "ei": 0.05}
    assert not bo.slot_gate([marginal], incumbent=0.0992).approved
    assert bo.slot_gate([{**marginal, "discovery": True}], incumbent=0.0992, rho=3.0).approved


def test_observation_log_round_trips(tmp_path):
    p = tmp_path / "obs.jsonl"
    obs = bo.Observation(kind="holdout", name="A1", score=0.0983, n_px=8000, source="test")
    bo.append_observation(obs, p)
    bo.append_observation(bo.Observation(kind="live", name="d28", score=0.26, source="owner claim"), p)
    back = bo.load_observations(p)
    assert len(back) == 2 and back[0].score == pytest.approx(0.0983)
    assert back[1].kind == "live" and back[1].score == pytest.approx(0.26)
