#!/usr/bin/env python3
"""Apply the identifier-only rename H97 -> H102 to this round's receipts.

Why this exists
---------------
This round was frozen, run and receipted as **H97** on branch
``arena/604a9c54-gemsdoe52`` (commit ``1f542d4``, base ``7eb226d``).  While the branch was open,
``main`` merged other sessions' rounds that already own the H97 label — the co-training
disagreement round (``knowledge/97_h97_hypotheses_preregistered.md``, ``docs/h97.html``,
``registry/h97_preregistration.json``) and the H97 mass-lever round (``h97_masslever_*``,
``h97b_*``) — so the label collides on the merge.  The repository has renumbered rounds for this
exact reason before (H88/H89 -> H92/H93 -> H97/H98 -> H99/H100, then H97 -> H101; see
``evidence/h101_identifier_rename.diff`` and the ``identifier_rename`` block inside
``registry/h101_preregistration.json``).  This script does the same job for this round:

    H97  -> H102          knowledge/97 -> 108, 98 -> 109, 99 -> 110, 100 -> 111
    h97  -> h102          every artefact, receipt and script name of this round

It is **identifier-only**.  No threshold, arm, budget, number or measured value changes:

* the TIFF bytes are untouched (sha256 ``cf035c83...f57bf326`` before and after);
* the only byte-level change to any artefact is the *member name* inside the single-TIFF ZIP,
  which is the artefact file name, rebuilt with the same shared packer
  (``gems52.submission_writer.repackage_zip``, identical parameters to ``write_submission``);
* the hypothesis document and the preregistration JSON each carry the round label in their text,
  so their SHA-256 pins move, and this script re-pins them and records both hashes
  (``document_sha256_before`` / ``document_sha256_after``) in the registry's
  ``identifier_rename`` block, exactly as the H101 rename did.

Writes:
    registry/h102_preregistration.json     re-pinned + identifier_rename block
    evidence/h102_run_card.json            re-pinned, feed-compatible raster/holdout blocks,
                                           identifier_history appended
    evidence/submission_<stem>.json etc.   hash/name references refreshed
    evidence/h102_identifier_rename.diff   the text diff of the rename (evidence)

Usage: python3 scripts/apply_h102_identifier_rename.py   (idempotent: refuses to run twice)
"""
from __future__ import annotations

import difflib
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
REG = ROOT / "registry" / "h102_preregistration.json"
DOC = ROOT / "knowledge" / "108_hypotheses_H102_preregistered.md"
CARD = EV / "h102_run_card.json"
STEM = "gems52-h102-pafdva-disagree-37600px-20261011T002233Z"
OLD_STEM = "gems52-h97-pafdva-disagree-37600px-20261011T002233Z"
BASELINE = "1f542d4"          # the branch commit that carried the frozen H97 name
OLD_DOC_SHA = "d603fe73580af36bc3673d3acaf2a41c4b64604134977782a5d077163e60db60"
OLD_REG_SHA = "b2eb593fe5ebed4005574402769305b9805c2ffdd57d760ecd3d0c90bd359181"
OLD_ZIP_SHA = "f1c4472f11caadb1adbe9e257fbb4af3cdb26be8011e47dbdb3a17fe0f45c304"
TIF_SHA = "cf035c83a651d90b0b920c52ce0e894b8666839d73b6f53f41a7a995f57bf326"

TOKEN_MAP = {
    "h97": "h102", "H97": "H102",
    "knowledge/97": "knowledge/108", "knowledge/98": "knowledge/109",
    "knowledge/99": "knowledge/110", "knowledge/100": "knowledge/111",
}

# text files of the round whose bytes move with the label (binaries are handled separately)
TEXT_MOVES = [
    ("knowledge/97_hypotheses_H97_preregistered.md", "knowledge/108_hypotheses_H102_preregistered.md"),
    ("knowledge/98_the_metric_is_a_coverage_metric.md", "knowledge/109_the_metric_is_a_coverage_metric.md"),
    ("knowledge/99_h97_results_and_limits.md", "knowledge/110_h102_results_and_limits.md"),
    ("knowledge/100_next_round_proposals.md", "knowledge/111_next_round_proposals.md"),
    ("registry/h97_preregistration.json", "registry/h102_preregistration.json"),
    ("docs/h97.html", "docs/h102.html"),
    ("scripts/run_h97.py", "scripts/run_h102.py"),
    ("scripts/run_h97_e4_coverage.py", "scripts/run_h102_e4_coverage.py"),
    ("scripts/run_h97_e4b_hysteresis.py", "scripts/run_h102_e4b_hysteresis.py"),
    ("scripts/build_h97b_covered.py", "scripts/build_h102b_covered.py"),
    ("scripts/publish_h97_site.py", "scripts/publish_h102_site.py"),
    ("scripts/publish_h97_readme.py", "scripts/publish_h102_readme.py"),
    ("scripts/finalize_h97_pointer.py", "scripts/finalize_h102_receipts.py"),
    ("submission/H97_LATEST.txt", "submission/H102_LATEST.txt"),
    ("docs/downloads/h97-candidate.json", "docs/downloads/h102-candidate.json"),
    ("tests/test_current_submission_gate.py", "tests/test_current_submission_gate.py"),
    ("tests/test_h95.py", "tests/test_h95.py"),
]
for n in ("build_placement", "channels", "e4_coverage", "e4b_hysteresis", "fit", "holdout",
          "independence", "lane", "not_union", "run_card"):
    TEXT_MOVES.append((f"evidence/h97_{n}.json", f"evidence/h102_{n}.json"))
TEXT_MOVES.append((f"evidence/submission_{OLD_STEM}.json", f"evidence/submission_{STEM}.json"))
TEXT_MOVES.append((f"docs/data/submission_{OLD_STEM}.json", f"docs/data/submission_{STEM}.json"))
TEXT_MOVES.append((f"submission/{OLD_STEM}.json", f"submission/{STEM}.json"))
TEXT_MOVES.append((f"docs/downloads/{OLD_STEM}.json", f"docs/downloads/{STEM}.json"))

BINARY_MOVES = [
    (f"submission/{OLD_STEM}.tif", f"submission/{STEM}.tif"),
    (f"submission/{OLD_STEM}.zip", f"submission/{STEM}.zip"),
    (f"submission/{OLD_STEM}-a-only-reasoning.csv", f"submission/{STEM}-a-only-reasoning.csv"),
    (f"docs/downloads/{OLD_STEM}.tif", f"docs/downloads/{STEM}.tif"),
    (f"docs/downloads/{OLD_STEM}.zip", f"docs/downloads/{STEM}.zip"),
    (f"docs/downloads/{OLD_STEM}-a-only-reasoning.csv", f"docs/downloads/{STEM}-a-only-reasoning.csv"),
    ("docs/downloads/h97-candidate.tif", "docs/downloads/h102-candidate.tif"),
    ("docs/downloads/h97-candidate.zip", "docs/downloads/h102-candidate.zip"),
    ("docs/downloads/h97-a-only-reasoning.csv", "docs/downloads/h102-a-only-reasoning.csv"),
]


def sha_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git_show(rev_path: str) -> bytes:
    out = subprocess.run(["git", "show", rev_path], cwd=ROOT, capture_output=True, check=True)
    return out.stdout


def main() -> int:
    doc_sha = sha_file(DOC)
    reg = json.loads(REG.read_text(encoding="utf-8"))
    if reg.get("identifier_rename"):
        print("identifier_rename already applied; nothing to do")
        return 0
    if sha_file(ROOT / "submission" / f"{STEM}.tif") != TIF_SHA:
        raise SystemExit("artefact bytes moved; an identifier rename must not change the TIFF")

    # 1 - the registry: re-pin the renamed document and record the rename
    reg["hypothesis_sha256"] = doc_sha
    reg["identifier_rename"] = dict(
        done_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        reason=("identifier collision: this round was frozen, run and receipted as H97 "
                f"(commit {BASELINE}, base 7eb226d); main meanwhile merged other sessions' H97 "
                "(co-training disagreement) and H97b/H97-masslever rounds, so the label is taken. "
                "Renumbered H102. Identifier-only edit: no constant, threshold, arm, budget or "
                "measured number changed; every stage ran under the H97 name with the pre-rename "
                "hashes, and the TIFF bytes are identical before and after."),
        frm="H97", to="H102",
        document_sha256_before=OLD_DOC_SHA, document_sha256_after=doc_sha,
        registry_sha256_before=OLD_REG_SHA,
        registry_sha256_after="recorded in evidence/h102_run_card.json identifier_history "
                             "(this file cannot contain its own hash)",
        token_map=TOKEN_MAP,
        evidence_diff="evidence/h102_identifier_rename.diff",
        artefact_bytes_unchanged=True, artefact_sha256=TIF_SHA,
        zip_rebuilt=dict(reason="the single member of the ZIP is named after the TIFF",
                         sha256_before=OLD_ZIP_SHA),
        moves=[dict(old=o, new=n) for o, n in TEXT_MOVES + BINARY_MOVES],
    )
    REG.write_text(json.dumps(reg, indent=1) + "\n", encoding="utf-8")
    reg_sha = sha_file(REG)

    # 2 - the ZIP: same bytes, member renamed by the shared packer
    sys.path.insert(0, str(ROOT / "src"))
    from gems52 import submission_writer as sw                       # noqa: E402
    zip_info = sw.repackage_zip(ROOT / "submission" / f"{STEM}.tif")
    assert sha_file(ROOT / "submission" / f"{STEM}.tif") == TIF_SHA

    # 3 - the run card: re-pin, refresh the identifier, add the feed-compatible blocks
    card = json.loads(CARD.read_text(encoding="utf-8"))
    card["preregistration_sha256"] = reg_sha
    card["hypothesis_document"] = str(DOC.relative_to(ROOT))
    card["hypothesis_sha256"] = doc_sha
    card["note_chars"] = len(card["note"])
    arms = card["holdout_dti"]
    gate = card["holdout_promotion_gate"]
    card["holdout"] = dict(
        {a: dict(arms[a]) for a in arms},
        instrument=arms["random"]["evaluator_version"],
        withheld_positive_px=arms["random"]["withheld_positive_pixels"],
        primary=card["round"] and "cotrain_disagree",
        primary_dti=gate["candidate_dti"],
        primary_ci95=arms["cotrain_disagree"]["ci95"],
        random_dti=arms["random"]["dti"],
        random_ci95=arms["random"]["ci95"],
        paired_primary_minus_random=dict(
            delta=gate["candidate_dti"] - arms["random"]["dti"],
            ci95=None,
            vs="random",
            note=("the registered paired test is the one in holdout_promotion_gate (vs the best "
                  "comparable control single_B2); the random arm is reported for scale")),
    )
    card["raster"] = dict(
        file=f"{STEM}.tif", bytes=int(card["raster_bytes"]), sha256=TIF_SHA,
        download=dict(tif="docs/downloads/h102-candidate.tif",
                      zip="docs/downloads/h102-candidate.zip",
                      tif_sha256=TIF_SHA, zip_sha256=zip_info["zip_sha256"]),
    )
    card["identifier_history"] = [
        dict(name="H97", commit=BASELINE, base="7eb226d", frozen_before_any_fit=True,
             document_sha256=OLD_DOC_SHA, registry_sha256=OLD_REG_SHA,
             note="the round ran and produced every receipt under this name"),
        dict(name="H102", commit=None, base="7eb226d",
             reason="identifier collision with main's H97/H97b rounds; identifier-only rename",
             document_sha256=doc_sha, registry_sha256=reg_sha,
             artefact_sha256=TIF_SHA, zip_sha256=zip_info["zip_sha256"],
             evidence_diff="evidence/h102_identifier_rename.diff"),
    ]
    card["verdict_note"] = ("identifier-only rename H97 -> H102 applied after the round closed; "
                            "no measured value changed")
    CARD.write_text(json.dumps(card, indent=1) + "\n", encoding="utf-8")

    # 4 - every other receipt of the round: refresh the hashes and the note length
    subs = {"b2eb593fe5ebed4005574402769305b9805c2ffdd57d760ecd3d0c90bd359181": reg_sha,
            OLD_DOC_SHA: doc_sha, OLD_ZIP_SHA: zip_info["zip_sha256"]}
    touched = []
    for pat in ("evidence/h102_*.json", f"evidence/submission_{STEM}.json",
                f"docs/data/submission_{STEM}.json",
                "docs/downloads/h102-candidate.json", "docs/downloads/gems52-h102-*.json",
                "submission/gems52-h102-*.json"):
        for f in sorted(ROOT.glob(pat)):
            t = f.read_text(encoding="utf-8")
            o = t
            for a, b in subs.items():
                t = t.replace(a, b)
            t = t.replace('"zip_bytes": 94747', '"zip_bytes": 94749')
            d = json.loads(t)
            if isinstance(d, dict):
                if isinstance(d.get("note"), str) and "note_chars" in d:
                    d["note_chars"] = len(d["note"])
                if "submission_name" in d or "validator" in d or d.get("round") == "H102":
                    d.setdefault("identifier_rename", dict(
                        frm="H97", to="H102", artefact_bytes_unchanged=True,
                        artefact_sha256=TIF_SHA,
                        document_sha256_before=OLD_DOC_SHA, document_sha256_after=doc_sha,
                        registry_sha256_before=OLD_REG_SHA, registry_sha256_after=reg_sha,
                        note="identifier-only rename after the round closed; no measured value changed"))
                t = json.dumps(d, indent=(2 if f.parent.name in ("submission", "downloads") else 1)) + "\n"
            if t != o:
                f.write_text(t, encoding="utf-8")
                touched.append(str(f.relative_to(ROOT)))

    # 5 - the human-readable results document: re-pin the two hashes it quotes
    rdoc = ROOT / "knowledge" / "110_h102_results_and_limits.md"
    t = rdoc.read_text(encoding="utf-8")
    t = t.replace(f"(SHA-256 `{OLD_REG_SHA[:16]}…`", f"(SHA-256 `{reg_sha[:16]}…`")
    t = t.replace(f"(SHA-256 `{OLD_DOC_SHA[:16]}…`", f"(SHA-256 `{doc_sha[:16]}…`")
    rdoc.write_text(t, encoding="utf-8")

    # 6 - the evidence diff of the rename itself
    lines = []
    for o, n in TEXT_MOVES:
        before = git_show(f"{BASELINE}:{o}").decode("utf-8", "replace").splitlines()
        after = (ROOT / n).read_text(encoding="utf-8").splitlines()
        d = list(difflib.unified_diff(before, after, fromfile=f"{BASELINE}:{o}", tofile=n, lineterm=""))
        if d:
            lines += d + [""]
    (EV / "h102_identifier_rename.diff").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(dict(round="H102", from_="H97", document_sha256=doc_sha,
                          registry_sha256=reg_sha, artefact_sha256=TIF_SHA,
                          zip_sha256=zip_info["zip_sha256"], note_chars=card["note_chars"],
                          receipts_touched=len(touched), diff_lines=len(lines)), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
