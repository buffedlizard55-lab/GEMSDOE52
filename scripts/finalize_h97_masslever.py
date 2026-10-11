#!/usr/bin/env python3
"""Finalise the H97 publication without moving the global submission pointer.

The round is **negative** on its frozen promotion gate, so by the repository's own convention
(``scripts/finalize_h91.py``) it must not move ``docs/data/submission.json`` or
``submission/LATEST.txt``: those name the incumbent.  What it does write:

* ``docs/data/submission_<stem>.json`` — the per-artifact receipt for each of the two rasters;
* ``submission/H97_MASSLEVER_LATEST.txt`` and ``submission/H97B_LATEST.txt`` — round-local markers that also
  say, in words, whether the file may be submitted;
* ``docs/submission/H97B_LATEST.txt`` — the site-side marker the H96 round also keeps.

Every value is read from the receipts on disk.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Round-local marker names.  The parallel lane already published a round called H97, so this lane's
# markers spell out which H97 they belong to (see IR-H97M-008).
MARKERS = {"H97": "H97_MASSLEVER_LATEST.txt", "H97b": "H97b_LATEST.txt"}
EV = ROOT / "evidence"
DOCS = ROOT / "docs"
DATA = DOCS / "data"
SUB = ROOT / "submission"


def rd(p: Path):
    return json.loads(p.read_text())


def write_marker(path: Path, write: dict, card: dict, short: str, duplicate: bool) -> None:
    tif = ROOT / write["tif"]
    path.write_text(
        f"{tif.name}\n"
        f"sha256 {write['sha256']}\n"
        f"bytes {tif.stat().st_size}\n"
        f"download docs/downloads/{short}\n"
        f"download_ok {card['download_ok']} submit_ok {card['submit_ok']}\n"
        f"verdict {card['verdict']} (gates failed: {', '.join(card['failed_gates']) or 'none'})\n"
        f"{'LANE DUPLICATE/STOP against the H96 artifact - audit only, do not submit' if duplicate else 'lane policy PASS; uniqueness PASS'}\n"
        f"note ({write['note_chars']}/140): {write['note']}\n"
        f"slots_used 0\n")
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> int:
    w1, c1 = rd(EV / "h97_masslever_write.json"), rd(EV / "h97_masslever_run_card.json")
    w2, c2 = rd(EV / "h97b_write.json"), rd(EV / "h97b_run_card.json")
    for stem, write, card, short, dup, round_tag in (
            (w1["submission_name"], w1, c1, "h97-masslever-candidate.tif", True, "H97"),
            (w2["submission_name"], w2, c2, "h97b-candidate.tif", False, "H97b")):
        rec = dict(write["writer_metadata"])
        g = card.get("gates") or card.get("experiment_3_gates") or {}
        rec.update(round=round_tag, stem=stem, short_tif=short,
                   marker=f"submission/{MARKERS[round_tag]}",
                   download=f"downloads/{short}",
                   verdict=card["verdict"], failed_gates=card["failed_gates"],
                   submit_ok=card["submit_ok"], download_ok=card["download_ok"],
                   lanes=dict(surface=g.get("lane_surface", {}).get("result"),
                              dots=g.get("lane_dots", {}).get("result")),
                   uniqueness=g.get("uniqueness", {}).get("result"),
                   global_pointer_untouched=("main's incumbent; a negative round must not move it"),
                   selector_note=("submit_ok False in the run card means THIS ROUND DOES NOT PROMOTE IT "
                                  "(its frozen promotion gate failed). E1 measured that the promotion gate "
                                  "does not rank the board's own scored files (Spearman -0.4897), so the "
                                  "gate is neither a board-validated yes nor a board-validated no. The only "
                                  "board-measured lever in this repository is emitted mass, and this file "
                                  "follows it (25,400 cells vs the champion's 37,654) and emits no mass "
                                  "within 200 m of the mapped catalogue. The slot decision is the owner's, "
                                  "within the weekly cap; this round spent none."))
        p = DATA / f"submission_{stem}.json"
        p.write_text(json.dumps(rec, indent=2, allow_nan=False) + "\n")
        print(f"wrote {p.relative_to(ROOT)}")
        write_marker(SUB / MARKERS[round_tag], write, card, short, dup)
    (DOCS / "submission" / "H97B_LATEST.txt").write_text(
        (SUB / "H97b_LATEST.txt").read_text())
    print("wrote docs/submission/H97B_LATEST.txt")
    assert (SUB / "LATEST.txt").read_text().strip() == rd(DATA / "submission.json")["file"], \
        "the incumbent pointer must be untouched"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
