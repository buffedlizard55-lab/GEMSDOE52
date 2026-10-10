import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _json(path):
    return json.loads((ROOT / path).read_text())


def test_h83_is_downloadable_but_closed_to_submission():
    receipt = _json("evidence/h83_status_reconciliation.json")
    run_card = _json("evidence/h83_run_card.json")
    submission = _json("docs/data/submission.json")
    download = ROOT / "docs/downloads/h83-candidate.tif"

    assert receipt["disposition"]["downloadable"] is True
    assert receipt["disposition"]["approved_for_weekly_slot"] is False
    assert receipt["disposition"]["portal_upload_performed"] is False
    assert run_card["holdout_dti"]["value"] == "NOT_EVALUATED"
    assert run_card.get("approved_for_weekly_slot") is None
    board = receipt["public_leaderboard_snapshot"]
    assert board["dard"] == {"rank": 7, "team": "DARD", "score": 0.3195}
    assert board["extradr19"] == {"rank": 17, "team": "extradr19", "score": 0.2778}
    assert "team-level only" in board["score_class"]
    captured_board = _json(board["path"])
    observed = {(row["team"], row["rank"]): row["score"] for row in captured_board["rows"]}
    assert observed[("DARD", 7)] == 0.3195
    assert observed[("extradr19", 17)] == 0.2778
    assert observed[("xiaofanhu", 1)] == 0.3774
    assert submission["round"] == "H60"
    assert submission["approved_for_weekly_slot"] is False
    assert (ROOT / "submission/LATEST.txt").read_text().strip() == submission["file"]

    linked = receipt["linked_h83_download"]
    assert download.stat().st_size == linked["bytes"]
    assert hashlib.sha256(download.read_bytes()).hexdigest() == linked["sha256"]
    assert hashlib.sha256((ROOT / linked["same_bytes_as"]).read_bytes()).hexdigest() == linked["sha256"]


def test_h83_status_pages_do_not_invite_portal_upload():
    receipt = _json("evidence/h83_status_reconciliation.json")
    docs_receipt = _json("docs/data/h83_status_reconciliation.json")
    assert receipt == docs_receipt

    readme = (ROOT / "README.md").read_text()
    index = (ROOT / "docs/index.html").read_text()
    guide = (ROOT / "docs/executive-summary.html").read_text()
    short_guide = (ROOT / "docs/h83-executive-summary.html").read_text()
    downloads = (ROOT / "docs/downloads/index.html").read_text()

    assert "DOWNLOADABLE; DO NOT SUBMIT" in readme
    assert "SUBMIT: NO" in readme
    assert "How to Submit" not in index
    assert "Click</strong> \"Submit\"" not in index
    assert "Do not upload" in index
    assert "Step-by-Step Submission Instructions" not in guide
    assert "Click \"Submit\"" not in guide
    assert "Do not upload this file" in guide
    assert "Click <strong>Submit</strong>" not in short_guide
    assert "DO NOT UPLOAD" in short_guide
    assert "DOWNLOAD YES; SUBMIT NO" in downloads
