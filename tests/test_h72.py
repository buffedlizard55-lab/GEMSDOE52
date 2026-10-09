"""Tests for the H72 round: frozen protocol, deformation-only View A2, gate logic.

These tests need no competition raster. The feature-store checks skip cleanly when work/ is absent.
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

REG = ROOT / "registry/h72_preregistration.json"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_protocol_hash_matches_registration():
    reg = json.loads(REG.read_text())
    assert _sha(ROOT / reg["hypothesis_document"]) == reg["hypothesis_sha256"]


def test_protocol_is_a_submission_round_with_a_spend_no_slot_verdict():
    reg = json.loads(REG.read_text())
    assert reg["runner_refuses_if_hash_moves"] is True
    assert "spends no weekly slot" in reg["verdict_rule"]
    assert reg["budget"]["max_experiments"] == 3
    assert reg["executes"].startswith("H70-E")


def test_thresholds_are_the_preregistered_values():
    th = json.loads(REG.read_text())["thresholds"]
    assert th["canary_auc_alarm"] == 0.90
    assert th["independence_abandon_max_abs_rho"] == 0.60
    assert th["donor_rank_min"] == 0.95
    assert th["receiver_rank_interval"] == [0.35, 0.65]
    assert th["buffer_px"] == 80
    assert th["budget_dots_per_fold_per_arm"] == 9400
    assert th["min_dot_separation_px"] == 3.0
    assert th["catalogue_exclusion_m"] == 200.0
    assert th["lane_near_dot_fraction"] == 0.70
    assert th["lane_rank_correlation"] == 0.90
    assert th["S1_sufficiency_mean_oof_auc_min"] == 0.60
    assert th["S1_sufficiency_min_fold_oof_auc"] == 0.55
    # the control reproduction bar is the H61 committed value and tolerance
    assert th["single_B_control_holdout_dti"] == 0.174517
    assert th["single_B_control_abs_tolerance"] == 0.001


def test_runner_refuses_if_preregistration_moves(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_h72", ROOT / "scripts/run_h72.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    reg = json.loads(REG.read_text())
    assert mod.check_prereg()["round"] == "H72"
    # a moved document must be refused
    bad = json.loads(REG.read_text())
    bad["hypothesis_sha256"] = "0" * 64
    p = tmp_path / "h72_preregistration.json"
    p.write_text(json.dumps(bad))
    old = mod.REG_PATH
    mod.REG_PATH = p
    try:
        with pytest.raises(SystemExit):
            mod.check_prereg()
    finally:
        mod.REG_PATH = old
    assert reg["hypothesis_sha256"] == _sha(ROOT / reg["hypothesis_document"])


def test_view_a2_is_deformation_only_and_disjoint_from_view_b():
    """The H72 View A2 list: the five deformation raw bands + the 17 derived columns, no View B name."""
    from gems52 import h72
    raw = {f"raw_band_{b:02d}" for b, _d in h72.DEF_BANDS}
    derived = set(h72.def_feature_names())
    va2 = set(h72.view_A2_deformation_names({"feature_names": sorted(raw | derived),
                                             "feature_sha256": {}}))
    assert raw <= va2 and derived <= va2
    assert len(va2) == 22
    # deformation bands only: 4/7/8 (strain) and 10/16 (seismicity); no potential-field band
    assert raw == {"raw_band_04", "raw_band_07", "raw_band_08", "raw_band_10", "raw_band_16"}
    # no surface/radiometric channel may appear in View A2
    for bad in ("raw_band_06", "raw_band_12", "raw_band_19", "raw_band_13", "raw_band_15"):
        assert bad not in va2
    assert not any(n.startswith(("B_", "X_rad_")) for n in va2)


def test_store_extension_is_registered_and_idempotent_when_present():
    store = ROOT / "work/r2/features/manifest.json"
    if not store.exists():
        pytest.skip("feature store not built in this sandbox")
    m = json.loads(store.read_text())
    if "view_A2_deformation" not in m:
        pytest.skip("H72 store extension not run in this sandbox")
    va2 = m["view_A2_deformation"]
    assert len(va2) == 22
    vb = set(m["view_B_with_external"])
    assert not (set(va2) & vb)
    # the canonical views are untouched by the H72 extension
    assert len(m["view_A_with_external"]) == 36
    assert len(m["view_B_with_external"]) == 37
    assert "+h72-deformation-v1" in m["version"]
    assert "+external-geodawn-v1" in m["version"]
    # every View A2 column exists on disk with a manifest hash
    for n in va2:
        p = ROOT / "work/r2/features" / f"{n}.npy"
        assert p.exists(), n
        assert n in m["feature_sha256"]


def test_candidate_field_is_finite_only_on_the_a2_only_stratum():
    """The H72 build field: rankA2 - rankB on the strict A2-only stratum, -1.0 elsewhere.

    The build's candidate cells are ``field > -1.0`` — exactly the stratum, because on the
    stratum rankA2 >= 0.95 and rankB <= 0.65, so the difference is >= 0.30 > -1.  Placement is
    restricted to those candidates, so every emitted cell is a strict A2-only candidate (the
    not-the-union invariant the run card asserts)."""
    rng = np.random.default_rng(0)
    shape = (64, 48)
    rankA = rng.random(shape, dtype=np.float32)
    rankB = rng.random(shape, dtype=np.float32)
    allowed = np.ones(shape, bool)
    lo, hi, dmin = 0.35, 0.65, 0.95
    stratum = (rankA >= dmin) & (rankB >= lo) & (rankB <= hi) & allowed
    field = np.where(stratum, rankA - rankB, -1.0).astype(np.float32)
    # the candidate mask is exactly the strict stratum
    cand = field > -1.0
    assert np.array_equal(cand, stratum)
    assert np.all(field[stratum] >= 0.95 - 0.65 - 1e-6)
    # a placement over the -inf convention can only ever take stratum cells
    from gems52 import nodes
    field_inf = np.where(stratum, rankA - rankB, -np.inf).astype(np.float32)
    em = nodes.spacing_select(field_inf, allowed, 10_000, min_px=3.0)
    assert np.all(em <= stratum)
    assert 0 < int(em.sum()) <= int(stratum.sum())
    # and the emitted cells are exactly stratum cells (the not-the-union invariant)
    assert int((em & stratum).sum()) == int(em.sum())


def test_lane_constraint_csr_orientation_matches_brute_force():
    """Regression (IR-H72-001): the candidate x prior CSR must be oriented so that row j lists the
    priors whose 3 px halo contains candidate j — the orientation run_h70.lane_valid_greedy expects.
    A transposed build crashed the first H72 build with an IndexError inside the greedy."""
    import scipy.sparse as sp
    from scipy import ndimage as ndi
    from gems52 import gates
    import run_h70 as h70mod
    rng = np.random.default_rng(7)
    shape = (120, 110)
    eligible = np.ones(shape, bool)
    # two informative priors with sparse supports
    priors = []
    for seed in (11, 12):
        r = np.random.default_rng(seed)
        sup = np.zeros(shape, bool)
        ys = r.integers(10, 110, size=40)
        xs = r.integers(10, 100, size=40)
        sup[ys, xs] = True
        priors.append(sup)
    assert all(gates.registry_coverage(s, eligible, gates.NEAR_RADIUS_PX) < gates.PROBE_COVERAGE
               for s in priors)
    # candidate cells: a coarse grid over the footprint
    cys, cxs = np.mgrid[5:115:7, 5:105:7]
    cand = (cys * shape[1] + cxs).ravel()
    W_ = shape[1]
    # H72 construction: one sparse row per prior over the candidates, vstacked, transposed
    rows_sp = [sp.csr_matrix(ndi.binary_dilation(s, structure=gates._disk(gates.NEAR_RADIUS_PX))
                             .ravel()[cand].astype(np.float32)) for s in priors]
    HITS = sp.vstack(rows_sp, format="csr").T.tocsr()
    assert HITS.shape == (cand.size, len(priors))
    indptr, indices = HITS.indptr, HITS.indices
    # the greedy must run without IndexError and place within the candidate set
    keep, counts = h70mod.lane_valid_greedy(cand, indptr, indices, len(priors), W_, 500)
    assert 0 < len(keep) <= 500
    # brute-force check: the greedy's per-prior counts equal direct halo counts over its keep list
    em_flat = cand[np.asarray(keep[:100], dtype=np.int64)]
    for i, s in enumerate(priors):
        halo = ndi.binary_dilation(s, structure=gates._disk(gates.NEAR_RADIUS_PX))
        brute = int(halo.ravel()[em_flat].sum())
        v = np.zeros(cand.size, np.float32)
        v[np.asarray(keep[:100], dtype=np.int64)] = 1.0
        csr_count = int(np.asarray(HITS.T @ v, dtype=np.int64).ravel()[i])
        assert csr_count == brute
    # and every kept candidate's prior list matches the brute-force halo membership
    for j in keep[:50]:
        y, x = divmod(int(cand[j]), W_)
        expect = [i for i, s in enumerate(priors)
                  if ndi.binary_dilation(s, structure=gates._disk(gates.NEAR_RADIUS_PX))[y, x]]
        got = sorted(int(v) for v in indices[indptr[j]:indptr[j + 1]])
        assert got == sorted(expect)


def test_holdout_receipt_is_consistent_when_present():
    p = ROOT / "evidence/h72_holdout.json"
    if not p.exists():
        pytest.skip("holdout receipt not produced yet")
    h = json.loads(p.read_text())
    assert h["stage"] == "holdout"
    assert h["budget_per_arm_per_fold"] == 9400
    assert set(h["arms"]) == {"single_A2", "single_B", "union_max", "disagreement_pre",
                              "disagreement_post", "a_only", "single_B_veto_Bonly", "concordant",
                              "random"}
    pooled = h["pooled"]["a_only"]
    assert pooled["evaluator_version"] == "gems52-pooled-hide-v1"
    assert pooled["scores"]["a_only"]["withheld_positive_pixels"] == h["withheld_positive_pixels"]
    # the control reproduction bar
    assert h["control"]["pass_"] is True
    # the standard arms filled their budgets on every fold
    assert h["all_standard_arms_filled"] is True
    # the verdict comparison is the paired bootstrap delta vs single_B
    pd = pooled["paired_differences"]["single_B"]
    assert h["holdout_eligible"] == bool(pooled["scores"]["a_only"]["dti"]
                                         > pooled["scores"]["single_B"]["dti"]
                                         and float(pd["ci95"][0]) > 0.0)


def test_sufficiency_receipt_is_consistent_when_present():
    p = ROOT / "evidence/h72_sufficiency.json"
    if not p.exists():
        pytest.skip("sufficiency receipt not produced yet")
    s = json.loads(p.read_text())
    assert len(s["view_A2_oof_auc_per_fold"]) == 4
    assert s["mean_view_A2_oof_auc"] == pytest.approx(float(np.mean(s["view_A2_oof_auc_per_fold"])))
    assert s["S1_pass"] == bool(s["mean_view_A2_oof_auc"] >= 0.60
                               and s["min_fold_view_A2_oof_auc"] >= 0.55)


def test_build_receipts_are_consistent_when_present():
    b = ROOT / "evidence/h72_build.json"
    nu = ROOT / "evidence/h72_not_union.json"
    if not (b.exists() and nu.exists()):
        pytest.skip("build receipts not produced yet")
    build, not_union = json.loads(b.read_text()), json.loads(nu.read_text())
    assert build["budget"] > 0
    assert build["lane_dots_policy_max_near_3px"] is not None
    if build["lane_valid_emission_exists"]:
        # lane-valid mode guarantees the built file satisfies the lane's own <= 0.70 rule
        assert build["lane_dots_policy_max_near_3px"] <= 0.70 + 1e-12
        assert build["lane_dots_policy"] == "PASS"
    else:
        # fallback mode: the lane verdict is reported verbatim, whatever it measures
        assert build["placement_mode"] == "fallback-duplicate"
    assert not_union["emitted_cells_that_are_strict_a2_only"] == build["budget"]
    assert not_union["not_union_pass"] is True
    assert build["validator"]["ok"] is True
    assert build["uniqueness_tier1"]["canonical_pattern_unique"] is True
    assert (build["uniqueness_tier2"]["novel_fraction"] or 0.0) >= 1.0


def test_run_card_verdict_rule_when_present():
    p = ROOT / "evidence/h72_run_card.json"
    if not p.exists():
        pytest.skip("run card not produced yet")
    card = json.loads(p.read_text())
    assert card["round"] == "H72"
    assert card["submission_slots_used"] == 0
    assert card["experiments_used"].startswith("3 of 3")
    assert len(card["note"]) == card["note_chars"] <= 140
    assert "deformation" in card["hypothesis"].lower()
    promote = card["verdict_promote"]
    reg = card["correlation_overlap_vs_registry"]
    uniq_ok = bool(reg["uniqueness_tier1"]["canonical_pattern_unique"]
                   and (reg["uniqueness_tier2"]["novel_fraction"] or 0.0) >= 1.0
                   and not reg["uniqueness_tier1"]["equals_literal_prior_union"]
                   and not reg["uniqueness_tier2"]["equals_literal_prior_union"])
    gates_ok = (card["validator"]["ok"] and uniq_ok
                and reg["lane_dots_policy"] == "PASS"
                and reg["lane_surface_policy"] == "PASS"
                and reg["lane_valid_emission_exists"]
                and card["not_the_union"]["not_union_pass"]
                and card["sufficiency_S1"]["S1_pass"]
                and card["holdout_dti"]["paired_candidate_minus_single_B"]["ci95"][0] > 0)
    assert promote == gates_ok
    if not promote:
        assert card["verdict"].startswith("NEGATIVE")
        assert "DOWNLOAD YES" in card["verdict"]
        assert "SUBMIT NO" in card["verdict"]
    # every holdout number is labelled HOLDOUT-DTI with the evaluator version
    hd = card["holdout_dti"]
    assert hd["evidence_class"] == "HOLDOUT-DTI"
    assert hd["evaluator_version"] == "gems52-pooled-hide-v1"
    assert hd["withheld_positive_pixels"] > 0


def test_submission_writer_rejects_out_of_range_and_nan(tmp_path):
    """The portal error 'Predicted values must be in range [0, 1]' must be unreachable."""
    from gems52 import submission_writer
    sample = ROOT / "data/sample_submission.tif"
    if not sample.exists():
        pytest.skip("sample_submission.tif not restored")
    import rasterio
    with rasterio.open(sample) as ds:
        footprint = np.isfinite(ds.read(1))
    good = np.zeros(footprint.shape, np.float32)
    r = submission_writer.write_submission(tmp_path / "ok.tif", good, sample, footprint,
                                           note="n", name="n")
    assert r["validator"]["ok"]
    bad = good.copy()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError):
        submission_writer.write_submission(tmp_path / "nan.tif", bad, sample, footprint,
                                           note="n", name="n")
    bad2 = good.copy()
    bad2[0, 0] = 1.5
    with pytest.raises(ValueError):
        submission_writer.write_submission(tmp_path / "range.tif", bad2, sample, footprint,
                                           note="n", name="n")
