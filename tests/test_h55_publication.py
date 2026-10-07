"""Publication regressions for the current H55 artifact and archived parallel rounds."""
from __future__ import annotations

import json
from pathlib import Path

from scripts import make_h55_page, make_site_pages, publish_site_r3, verify_h55

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs/data"


def _json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_h55_a_only_prose_compares_each_instrument_to_its_matched_random_control() -> None:
    make_h55_page.main()
    page = (ROOT / "docs/h55.html").read_text()
    sweep = _json(ROOT / "evidence/h55_sweep_hardcore.json")

    def mean(mode: str, arm: str, emitter: str) -> float:
        row = next(r for r in sweep[mode]["summary"]["ranked"]
                   if r["arm"] == arm and r["emitter"] == emitter)
        return float(row["mean_dti"])

    expected_hide = f"{mean('hide', 'A_only', 'hc4|37654'):.5f} (below matched random, {mean('hide', 'random', 'hc|37654'):.5f})"
    expected_tip = f"{mean('tip', 'A_only', 'hc4|37654'):.5f} (above matched random, {mean('tip', 'random', 'hc|37654'):.5f})"
    assert expected_hide in page
    assert expected_tip in page
    assert "below matched random on both" not in page
    assert "does not pass the pre-registered" in page


def test_verification_verdict_uses_the_separate_a_only_promotion_gate() -> None:
    summary = verify_h55.a_only_promotion_summary()
    assert "0.02979 vs matched random 0.03948 on hide" in summary
    assert "0.02894 vs 0.02477 on tip" in summary
    assert "1/4 and 2/4" in summary
    assert "does not pass" in summary
    assert "below matched random on both" not in summary


def test_executive_summary_is_rendered_from_current_h55_receipts() -> None:
    sub = _json(DATA / "submission.json")
    verification = _json(DATA / f"h55_verification_{sub['tag']}.json")
    sweep = _json(DATA / "h55_sweep_hardcore.json")
    summary = publish_site_r3.render_summary(sub, verification, sweep)

    assert sub["file"] in summary
    assert sub["submission_name"] in summary
    assert sub["submission_note"] in summary
    assert f"{sub['submission_note_short_chars']} characters" in summary
    assert "Local scientific slot gate: PASS" in summary
    assert "not organizer approval" in summary
    assert "not a public-score forecast" in summary
    assert "generative-AI disclosure" in summary
    assert "extent, and manner" in summary
    assert "5.6%" in summary and "18.3%" in summary
    assert "H55-JUNCTION hypothesis remains untested" in summary
    assert "R3-H1 submission guide · research-only" not in summary
    assert "submission_r3.json" not in summary
    assert "data/submission.json" in summary


def test_h55_irregularity_review_callout_is_idempotent_and_receipt_backed(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(publish_site_r3, "DOCS", tmp_path)
    page = tmp_path / "irregularities.html"
    page.write_text(
        '<main id="main"><li><strong>No radiometric bands in the available stack.</strong> '
        'No invented data layers, LiDAR-only hidden-label claims or local microseismic locations.</li>'
        '<li><strong>Geophysical view is weaker here.</strong> Low negative-error correlation did not make co-training win. '
        'Strong surface-only control prevented a false promotion.</li><h2>Next session, in order</h2></main>'
    )
    sub = _json(DATA / "submission.json")
    verification = _json(DATA / f"h55_verification_{sub['tag']}.json")
    sweep = _json(DATA / "h55_sweep_hardcore.json")

    publish_site_r3.insert_h55_review(sub, verification, sweep)
    publish_site_r3.insert_h55_review(sub, verification, sweep)
    result = page.read_text()

    assert result.count("<!--H55-CURRENT-REVIEW-->") == 1
    assert sub["file"] in result
    assert "not organizer approval" in result
    assert "0.02979" in result and "0.02894" in result
    assert "H55-JUNCTION remains untested" in result
    assert "No radiometric bands in the available stack" not in result
    assert "Historical R2 next-session plan" in result


def test_disabled_h54_publisher_leaves_current_pages_untouched(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(make_site_pages, "DOCS", tmp_path)
    (tmp_path / "index.html").write_text("current H55 home")
    (tmp_path / "executive-summary.html").write_text("current H55 guide")
    assert make_site_pages.main() == 0
    assert (tmp_path / "index.html").read_text() == "current H55 home"
    assert (tmp_path / "executive-summary.html").read_text() == "current H55 guide"
    assert not (tmp_path / "h54.html").exists()
