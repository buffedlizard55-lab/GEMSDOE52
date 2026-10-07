from __future__ import annotations

import json
from pathlib import Path

from scripts import publish_h57

ROOT = Path(__file__).resolve().parents[1]


def test_h57_publication_status_matches_receipts_and_preserves_latest_pointer() -> None:
    receipt = json.loads((ROOT / "docs/data/h57_submission.json").read_text())
    holdout = json.loads((ROOT / "docs/data/h57_holdout.json").read_text())
    independence = json.loads((ROOT / "docs/data/h57_independence.json").read_text())
    page = (ROOT / "docs/h57.html").read_text()
    guide = (ROOT / "docs/executive-summary.html").read_text()
    home = (ROOT / "docs/index.html").read_text()

    assert receipt["safe_to_download_for_research"] is True
    assert receipt["approved_to_submit"] is False
    assert receipt["candidate_arm"] == "view_B_corrected_fallback"
    assert receipt["candidate_arm_is_cotrain"] is False
    assert receipt["submission_name_chars"] <= 200
    assert receipt["submission_note_chars"] <= 200
    assert holdout["exchange"]["enabled"] is False
    assert holdout["submission_slots_used"] == 0
    assert holdout["portal_upload_performed"] is False
    assert independence["allow_exchange"] is False
    assert holdout["primary"]["mean_dti"] < holdout["comparisons"]["historical_best_comparable_mean_dti"]
    assert (ROOT / "submission/LATEST.txt").read_text().strip() == publish_h57.H56_CURRENT_FILE
    assert receipt["file"] in page and receipt["file"] in guide and receipt["file"] in home
    assert "Safe to download for research?" in page
    assert "Approved to submit?" in page
    assert "Do not upload" in guide
    assert all(f"H57-{rank}" in page for rank in range(1, 5))


def test_publication_marker_is_idempotent_and_remains_above_historical_card(tmp_path: Path) -> None:
    target = tmp_path / "index.html"
    target.write_text("<main><!--OLD--><section id=\"h56\">H56</section></main>")
    markup = "<!--H57--><section id=\"h57\">H57</section><!--/H57-->"
    for _ in range(2):
        publish_h57.insert_marker(target, "<!--H57-->", "<!--/H57-->", markup,
                                  before='<section id="h56">')
    result = target.read_text()
    assert result.count("<!--H57-->") == 1
    assert result.index("id=\"h57\"") < result.index("id=\"h56\"")
