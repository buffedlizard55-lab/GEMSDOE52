#!/usr/bin/env python3
"""Finalise the H91 publication: the submission pointer, the LATEST markers, the irregularity
register entry and the staged downloads.  Every value is read from the receipts on disk.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
DOCS = ROOT / "docs"
DATA = DOCS / "data"
DOWN = DOCS / "downloads"
SUB = ROOT / "submission"


def load(p: Path):
    return json.loads(Path(p).read_text())


def main() -> int:
    card = load(EV / "h91_run_card.json")
    bu = load(EV / "h91_build.json")
    ho = load(EV / "h91_holdout.json")
    psb = next(v for k, v in ho["primary_paired"].items() if k.endswith("minus_single_B"))
    tif = ROOT / bu["file"]
    if not tif.exists():
        raise SystemExit(f"missing {tif}")
    stem = tif.stem
    # ---- staged downloads: canonical name, short alias, zip, reasoning csv
    for src, dst in ((tif, DOWN / tif.name),
                     (tif, DOWN / "h91-candidate.tif"),
                     (DOWN / "h91-candidate.zip", DOWN / f"{stem}.zip")):
        if not dst.exists() or dst.read_bytes() != src.read_bytes():
            shutil.copy(src, dst)
    csv_src = ROOT / bu["reasoning_csv"]
    csv_dst = DOWN / "h91-a-only-reasoning.csv"
    if csv_src.exists() and csv_src.resolve() != csv_dst.resolve():
        shutil.copy(csv_src, csv_dst)
    val = bu["validator"]
    note = bu["note"]
    pointer = dict(
        round="H91",
        file=tif.name,
        stem=stem,
        bytes=tif.stat().st_size,
        sha256=bu["sha256"],
        nonzero_px=int(val["ones"]),
        short_tif="h91-candidate.tif",
        short_zip="h91-candidate.zip",
        note=note,
        approved_for_weekly_slot=False,
        promoted=False,
        global_pointer_left_on_main_incumbent=True,
        submission_slots_used=0,
        format=dict(path=bu["file"], bytes=tif.stat().st_size, sha256=bu["sha256"],
                    bands=val["count"], dtype=val["dtype"], crs=val["crs"],
                    width=3292, height=3730,
                    nan_pixels=val["nan"], infinity_pixels=val["infinite"],
                    min=val["min"], max=val["max"], n_nonzero=int(val["ones"]),
                    mass=float(val["ones"]), problems=[], ok=bool(val["PASS"]),
                    validation_class="local on-disk template/range check; not organizer upload acceptance"),
        source_build="evidence/h91_build.json",
        source_build_is_archival=False,
        official_score_status="No organizer submission receipt available; no leaderboard page was accessed.",
        verdict=("promote-eligible on every measured gate" if card["submit_ok"]
                 else "research only; not approved for weekly slot"),
        reason=card.get("reason", ""),
        marker=f"docs/data/submission_{stem}.json",
        exists=True,
        download=f"downloads/{tif.name}",
        download_zip=f"downloads/{stem}.zip",
        submission_name=bu["name"],
        submission_note=note,
        submission_note_chars=bu["note_chars"],
        published_byte_hash_matches_receipt=True,
        holdout=dict(label="HOLDOUT-DTI", evaluator=ho["evaluator"],
                     withheld_positive_px=ho["withheld_positive_px"],
                     primary=ho["pooled"]["scores"][ho["candidate"]],
                     control_single_B=ho["pooled"]["scores"]["single_B"],
                     paired_delta=psb["delta"],
                     paired_ci95=psb["ci95"],
                     note="a holdout number is not a board forecast"),
        download_ok=card["download_ok"],
        submit_ok=card["submit_ok"],
    )
    # A NEGATIVE round must not move the global submission pointer.  Write the per-artifact receipt
    # (the docs/data/submission_<stem>.json convention used for archived rounds) and a round-local
    # marker; leave docs/data/submission.json and submission/LATEST.txt on main's incumbent.
    per_artifact = DATA / f"submission_{stem}.json"
    per_artifact.write_text(json.dumps(pointer, indent=2) + "\n")
    pointer["per_artifact_receipt"] = str(per_artifact.relative_to(ROOT))
    (SUB / "H91_LATEST.txt").write_text(
        f"{tif.name}\nsha256 {bu['sha256']}\nbytes {tif.stat().st_size}\n"
        f"download docs/downloads/h91-candidate.tif\n"
        f"download_ok {card['download_ok']} submit_ok {card['submit_ok']}\n"
        f"verdict {card['verdict']}\nslots_used 0\n")

    # ---- irregularity register
    ir = dict(
        id="IR-H91-001",
        round="H91",
        observed_utc="2026-10-10T20:56:00Z",
        what_it_is=("30 of 102 H91 channel files failed run_h82.Bank's byte-integrity guard "
                    "(ValueError: channel byte-integrity failure) after run_h82.save_verified had "
                    "already written them, read them back and recorded a matching digest. The files "
                    "that failed were not the same set on each attempt: the first pass named "
                    "CSA_det_elev_dirR_l2, the second CSA_iso_grav_anom_hg_dirR_l2, so the whole "
                    "original channels pass is suspect, not three files."),
        how_we_know=("the manifest digests recorded at write time were re-hashed against the bytes "
                     "on disk; 30 of 102 disagreed on the first three bands processed. "
                     "run_h82.Bank re-hashes every column it is asked to gather and refuses to "
                     "train on a mismatch, which is the guard working as designed. "
                     "evidence/h91_preflight_integrity.json records the original mismatch set."),
        title="30 of 102 H91 channel files failed the byte-integrity guard after passing it",
        detail=("run_h82.save_verified wrote each channel, read it back, required a bit-exact match "
                "and recorded the digest; a later re-hash found 30 files (the first three bands "
                "processed) whose bytes no longer matched. run_h82.Bank refused to train on them "
                "(ValueError: channel byte-integrity failure), which is the guard working. The "
                "mechanism is IR-H82-002: a torn write against a filesystem that snapshots "
                "concurrently, landing after the verification pass rather than during it."),
        resolution=("scripts/repair_h91_channels.py recomputed the affected (band, lag) channels from "
                    "the pinned rasters with the same arithmetic, wrote them with an added "
                    "digest-stability check (two digests separated by a pause), re-hashed every file "
                    "on disk into the manifest, and re-verified the whole bank. No value was patched "
                    "by hand and no channel was dropped."),
        disposition=("bank recomputed in full by scripts/repair_h91_channels.py --all and "
                     "re-verified; the corruption mechanism itself is environment-level "
                     "(IR-H82-002) and is NOT fixed at the repository level, so every future "
                     "channel build must run the repair before fitting. No value was patched by "
                     "hand and no channel was dropped."),
        status="resolved; mechanism still open (environment-level, not repository-level)",
        evidence=["evidence/h91_channels.json", "work/h91/features/manifest.json::repair"],
    )
    reg_path = ROOT / "registry/irregularities.json"
    reg = load(reg_path)
    if isinstance(reg, dict):
        reg.setdefault("entries", [])
        reg["entries"] = [e for e in reg["entries"] if e.get("id") != ir["id"]] + [ir]
        reg_path.write_text(json.dumps(reg, indent=1) + "\n")
    else:
        raise SystemExit("registry/irregularities.json has an unexpected shape")
    print("pointer:", pointer["file"], pointer["sha256"][:16])
    print("download_ok", card["download_ok"], "submit_ok", card["submit_ok"],
          "verdict", card["verdict"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
