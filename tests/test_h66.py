"""H66 runner guards: the local View-A rule, the pre-registration pin, and the refusal path."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# View A names exactly as written by the feature store (manifest view_A_with_external, 36 channels)
VIEW_A_WITH_EXTERNAL = [
    "A_RTP_grad_1", "A_RTP_grad_3", "A_cover_coherence", "A_cover_grad_1", "A_cover_grad_3",
    "A_cover_grad_8", "A_cover_persistence_1_3", "A_cover_persistence_3_8", "A_gravity_coherence",
    "A_gravity_cover_signed_1", "A_gravity_cover_signed_3", "A_gravity_cover_signed_8",
    "A_gravity_grad_1", "A_gravity_grad_3", "A_gravity_grad_8", "A_gravity_persistence_1_3",
    "A_gravity_persistence_3_8", "X_mag_TMI_up150_grad1", "X_mag_TMI_up150_grad3",
    "X_mag_TMI_up150_rank", "raw_band_01", "raw_band_02", "raw_band_03", "raw_band_04",
    "raw_band_05", "raw_band_07", "raw_band_08", "raw_band_09", "raw_band_10", "raw_band_11",
    "raw_band_13", "raw_band_14", "raw_band_15", "raw_band_16", "raw_band_17", "raw_band_18",
]


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_h66_under_test", SCRIPTS / "run_h66.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_local_rule_selects_exactly_the_preregistered_fourteen():
    run = _load_runner()
    sel = run.local_view_A(VIEW_A_WITH_EXTERNAL)
    assert len(sel) == 14
    assert sorted(sel) == sorted(run.EXPECTED_A_LOCAL)


def test_local_rule_excludes_regional_and_raw_channels():
    run = _load_runner()
    sel = set(run.local_view_A(VIEW_A_WITH_EXTERNAL))
    assert not any(n.startswith("raw_band_") for n in sel)
    assert not any(n.endswith("_8") or n.endswith("_3_8") or "rank" in n for n in sel)


def test_local_rule_refuses_a_drifted_feature_list():
    run = _load_runner()
    # a new channel that the suffix rule WOULD select (scale 1 px) must trip the pinned list
    with pytest.raises(SystemExit):
        run.local_view_A(VIEW_A_WITH_EXTERNAL + ["A_extra_grad_1"])
    # a channel the rule would not select (scale 5 px) leaves the pinned list unchanged
    assert sorted(run.local_view_A(VIEW_A_WITH_EXTERNAL + ["A_gravity_grad_5"])) == sorted(run.EXPECTED_A_LOCAL)


def test_registry_pins_the_current_document_and_inherited_thresholds():
    run = _load_runner()
    reg = run.guard()                       # raises SystemExit if either hash moved
    assert reg["hypothesis_sha256"] == run.sha256_file(run.DOC_PATH)
    assert reg["inherited_thresholds_from"]["sha256"] == run.sha256_file(
        ROOT / reg["inherited_thresholds_from"]["path"])
    assert reg["thresholds_inherited"]["budget_dots_per_fold_per_arm"] == 9400


def test_guard_refuses_when_the_document_moves(tmp_path, monkeypatch):
    run = _load_runner()
    doc = tmp_path / "doc.md"
    doc.write_text("changed after registration\n")
    reg = json.loads(run.REG_PATH.read_text())
    reg_copy = tmp_path / "reg.json"
    reg_copy.write_text(json.dumps(reg))
    monkeypatch.setattr(run, "DOC_PATH", doc)
    monkeypatch.setattr(run, "REG_PATH", reg_copy)
    with pytest.raises(SystemExit):
        run.guard()
