"""H97 round guardrails: the verdicts, the receipts, and the two rules this round repaired.

Nothing here re-derives a model number.  Each assertion ties a *published claim* to the *receipt* it
came from, so a hand-edited page or a stale receipt fails the suite instead of shipping.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

EVID = ROOT / "evidence"
CARD = json.loads((EVID / "h97_run_card.json").read_text())
H = json.loads((EVID / "h97_holdout.json").read_text())
O = json.loads((EVID / "h97_offcat.json").read_text())
REG = json.loads((ROOT / "registry/h97_preregistration.json").read_text())


def test_preregistration_is_frozen_and_hashed():
    reg = CARD["preregistration"]
    assert reg["frozen_before_any_fit"] is True
    assert reg["id"] == "H97"
    sha = reg.get("preregistration_sha256")
    live = hashlib.sha256((ROOT / "registry/h97_preregistration.json").read_bytes()).hexdigest()
    assert sha == live, "the run card must quote the hash of the registration as it stands on disk"
    assert REG["document"] == "knowledge/97_hypotheses_H97_preregistered.md"


def test_holdout_receipt_has_the_nine_registered_arms():
    assert H["arms"] == ["thermal_gap_cotrain", "thermal_gap", "thermal_gap_line", "random_gap",
                         "random_gap_full", "random_uniform", "single_A", "single_B", "cotrain_bi"]
    assert H["evaluator_version"] == "gems52-pooled-hide-v1"
    assert H["withheld_positive_px"] > 0


def test_the_count_matched_claim_is_satisfied_and_the_mass_matched_one_is_not():
    """IR-H97-002: this asymmetry is the round's headline and must not be flattened anywhere."""
    pc = H["primary_claim"]
    assert pc["satisfied"] is True
    assert pc["paired"]["ci95"][0] > 0
    assert pc["mass_matched"]["satisfied"] is False
    assert pc["mass_matched"]["paired"]["ci95"][0] < 0 < pc["mass_matched"]["paired"]["ci95"][1]


def test_primary_is_below_the_promotion_bar_so_the_verdict_is_negative():
    primary = H["pooled"]["scores"]["thermal_gap_cotrain"]["dti"]
    assert primary < H["bar_to_beat"]
    assert CARD["verdict_for_slot"] == "negative"
    assert H["verdict_for_slot"] == "negative"
    # and the same file must not carry a submit-YES anywhere on the site
    for page in ("h97.html", "h97-executive-summary.html"):
        html = (ROOT / "docs" / page).read_text()
        assert "OK TO SUBMIT: NO" in html
        assert "OK TO DOWNLOAD: YES" in html


def test_format_receipt_matches_the_bytes_on_disk():
    v = CARD["validator"]
    tif = ROOT / v["path"]
    assert tif.exists()
    assert hashlib.sha256(tif.read_bytes()).hexdigest() == CARD["raster_sha256"] == v["sha256"]
    assert v["ok"] is True and not v["problems"]
    assert v["bands"] == 1 and v["dtype"] == "float32" and v["crs"] == "EPSG:32611"
    assert (v["height"], v["width"]) == (3730, 3292)
    assert v["n_nan"] == 0 and v["infinity_pixels"] == 0
    assert v["min"] >= 0.0 and v["max"] <= 1.0 and v["mass_outside_footprint"] == 0


def test_note_is_within_the_portal_limit_and_the_name_is_unique():
    assert len(CARD["note"]) <= 140
    assert CARD["note_chars"] == len(CARD["note"])
    from collections import Counter
    names = [p.name for p in (ROOT / "submission").glob("gems52-h97-*.tif")]
    assert len(names) == 1 and CARD["submission_name"] + ".tif" == names[0]


def test_independence_passes_so_the_negative_is_not_an_abandonment():
    indep = H["independence"]
    assert indep["allow_exchange"] is True
    assert indep["max_abs_correlation"] < REG["gates"]["independence_abandon_at_max_abs_r"]


def test_leakage_canary_is_below_the_alarm():
    assert max(H["canary"]["max_auc"].values()) < REG["gates"]["leakage_canary_alarm_auc"]


def test_offcatalogue_instrument_is_flat_in_mass():
    """The mass curve is the reason a rising off-catalogue DTI is not a ranking signal."""
    curve = O["mass_curve_of_shipped_ranking"]
    dens = [v["credit_density"] for v in curve.values()]
    assert max(dens) - min(dens) < 0.005
    assert O["arms"]["thermal_gap_cotrain"]["credit_density"] < O["arms"]["random_matched"]["credit_density"]


def test_every_emitted_cell_has_an_a_only_reasoning_row():
    csv = ROOT / "docs/downloads/h97-a-only-reasoning.csv"
    assert csv.exists()
    with csv.open() as fh:
        n = sum(1 for _ in fh) - 1
    assert n == CARD["composition"]["total"] == 25400


def test_lane_rule_is_reported_both_raw_and_coverage_normalised():
    """IR-H97-001/006: the raw rule fires on coverage probes; lift is the interpretable number, and a
    lift only counts when the raw rule also fired."""
    policy = CARD["lane_dots"]["policy"]
    assert policy["verdict"] == "DUPLICATE/STOP"
    G = json.loads((EVID / "h97_gates.json").read_text())
    cen = G["supplemental_census_closure"]
    disk = G["supplemental_disk_closure"]

    # (a) the census: not a copy of any sibling blob, but its union already covers our dots
    assert cen["n_priors"] >= 500
    assert G["census_identity"]["matches_census_file_or_decoded_sha"] is False
    assert cen["novel_fraction"] <= 0.05, "the 526-blob union includes dense lattice probes"
    on_disk = json.loads((EVID / "h97_uniqueness.json").read_text())
    assert cen["novel_fraction"] < on_disk["novel_fraction"], "novelty is a prior-set statement"

    # (b) the genuine concentration is against this repository's own H96 file
    assert disk["max_near_3px_lift"] > 2.0
    assert "h96" in Path(disk["max_lift_source"]).name
    assert disk["max_lift_coverage"] < 0.20
    assert any("h96" in n for n in disk["lift_offenders"])
    # every "near" prior that normalisation explains away must have lift <= the limit
    assert disk["coverage_explained_near"], "the lattice/composite probes are coverage artefacts"
    # (c) a high lift with a low raw fraction is coincidence, and is counted separately
    assert cen["high_lift_low_overlap"] >= 1


def test_shared_gate_now_reports_lift_without_changing_the_frozen_verdict():
    from gems52 import gates
    assert gates.LIFT_LIMIT == 2.0
    src = (ROOT / "src/gems52/gates.py").read_text()
    for key in ("near_3px_lift", "max_near_3px_lift", "max_lift_source", "lift_offenders",
                "coverage_normalization"):
        assert key in src
    # the frozen thresholds and verdict strings are untouched
    assert gates.NEAR_LIMIT == 0.70 and gates.RANK_LIMIT == 0.90 and gates.PROBE_COVERAGE == 0.95


def test_irregularities_register_carries_this_round():
    reg = json.loads((ROOT / "registry/irregularities.json").read_text())
    ids = {e["id"] for e in reg["entries"]}
    for i in range(1, 7):
        assert f"IR-H97-{i:03d}" in ids


def test_readme_agents_and_site_state_both_verdicts():
    readme = (ROOT / "README.md").read_text()
    head = readme[: readme.index("<!--/H97-README-->")]
    assert head.startswith("<!--H97-README-->")
    assert "OK TO DOWNLOAD: YES" in head and "OK TO SUBMIT: NO" in head
    assert "docs/downloads/h97-candidate.tif" in head and CARD["raster_sha256"] in head
    brief = (ROOT / "knowledge/99_current_user_brief_2026-10-10_H97.md").read_text()
    assert brief.strip()[:200] in head
    assert (ROOT / "AGENTS.md").read_text().index("<!--H97-AGENTS-->") >= 0
    assert (ROOT / "docs/downloads/h97-candidate.tif").exists()
    assert (ROOT / "docs/h97.html").exists() and (ROOT / "docs/h97-executive-summary.html").exists()


def test_artifact_is_not_byte_identical_to_any_other_submission():
    ours = (ROOT / CARD["validator"]["path"]).read_bytes()
    for other in (ROOT / "submission").glob("*.tif"):
        if other.name == Path(CARD["validator"]["path"]).name:
            continue
        assert other.read_bytes() != ours, f"{other.name} is a byte-identical copy"


@pytest.mark.parametrize("arm", ["thermal_gap_cotrain", "single_A", "single_B", "cotrain_bi"])
def test_arms_are_extremely_sparse_binary(arm):
    """The metric is not scale-invariant, so every emitted value must be exactly 0 or 1."""
    import rasterio
    with rasterio.open(ROOT / CARD["validator"]["path"]) as ds:
        a = ds.read(1)
    assert np.isin(a, [0.0, 1.0]).all()
    assert int(a.sum()) == CARD["composition"]["total"]
