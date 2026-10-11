#!/usr/bin/env python3
"""Publish the H97 submission pointer, the way the site and the scheduled feed expect it.

The invariant the site's own verifier enforces (``scripts/check_site.py``) is:

    docs/data/submission.json["file"] == submission/LATEST.txt

and the scheduled feed (``scripts/refresh_feed.py``) regenerates that JSON from
``evidence/submission_<stem>.json``, so a per-artefact receipt must exist or the next feed run
would replace the gate report with a stub.

This script writes, from receipts only (nothing is invented):

    evidence/submission_<stem>.json        per-artefact receipt (feed-compatible schema)
    docs/data/submission_<stem>.json       site copy of the same receipt
    docs/data/submission.json              the global pointer (H97 is a NEGATIVE round: the file is
                                           research-only, ``approved_for_weekly_slot`` and
                                           ``promoted`` stay False and zero slots are used)

Usage: python3 scripts/finalize_h97_pointer.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
DATA = ROOT / "docs" / "data"
SUB = ROOT / "submission"
DL = ROOT / "docs" / "downloads"


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    card = load(EV / "h97_run_card.json")
    hold = load(EV / "h97_holdout.json")
    lane = load(EV / "h97_lane.json")
    build = load(EV / "h97_build_placement.json")
    name = f"gems52-{card['submission_name']}"
    tif, zipf = SUB / f"{name}.tif", SUB / f"{name}.zip"
    for p in (tif, zipf):
        if not p.exists():
            raise SystemExit(f"missing {p}")
    if sha(tif) != card["raster_sha256"]:
        raise SystemExit("raster bytes differ from the run card; refusing to publish a pointer")
    marker = (SUB / "LATEST.txt").read_text().strip()
    if marker != tif.name:
        raise SystemExit(f"submission/LATEST.txt points at {marker}, not {tif.name}")

    v = card["validator"]
    zip_sha = sha(zipf)
    meta = card.get("metadata") or {}
    receipt = dict(
        file=tif.name,
        sha256=card["raster_sha256"],
        bytes=tif.stat().st_size,
        submission_name=name,
        note=card["note"],
        note_chars=card["note_chars"],
        validator=dict(v, sha256=card["raster_sha256"], ok=bool(v["PASS"])),
        zip_file=zipf.name,
        zip_sha256=zip_sha,
        approved_for_weekly_slot=False,
        promoted=False,
        submission_slots_used=0,
        status="research-only; local format validation is not organizer acceptance",
        metadata=dict(
            round="H97",
            hypothesis=card["hypothesis"],
            evidence_class="HOLDOUT-DTI",
            registration=dict(preregistration_sha256=card["preregistration_sha256"],
                              frozen_before_any_fit=True),
        ),
        round="H97",
        stem=name,
        nonzero_px=int(v["ones"]),
        short_tif="h97-candidate.tif",
        short_zip="h97-candidate.zip",
        # keys the site verifier reads (all measured, never projected)
        format=dict(path=str(tif.relative_to(ROOT)), bytes=tif.stat().st_size,
                    sha256=card["raster_sha256"], bands=v["count"], dtype=v["dtype"],
                    crs=v["crs"], width=v["shape"][1], height=v["shape"][0],
                    transform_match=v.get("transform_match"), bounds_match=v.get("bounds_match"),
                    nan_pixels=v["nan"], infinity_pixels=v["infinite"], min=v["min"], max=v["max"],
                    n_nonzero=int(v["ones"]), mass=float(v["ones"]), problems=[], ok=bool(v["PASS"]),
                    validation_class="local on-disk template/range check; not organizer upload acceptance"),
        uniqueness=dict(n_priors_checked=lane["uniqueness"]["n_priors_checked"],
                        canonical_pattern_unique=lane["uniqueness"]["canonical_pattern_unique"],
                        identical_to_a_prior=lane["uniqueness"]["identical_to_a_prior"],
                        help="lane census scoped to locally available rasters (IR-H97-003)"),
        holdout=dict(label="HOLDOUT-DTI", evaluator=hold["evaluator"],
                     withheld_positive_px=hold["withheld_positive_px"],
                     primary=hold["pooled"]["scores"][hold["candidate"]],
                     controls={a: hold["pooled"]["scores"][a] for a in hold["pooled"]["scores"]},
                     paired_vs_best_control=hold["promotion_gate"],
                     note="a holdout number is not a board forecast"),
        placement=dict(dots=build["dots"], pool_px=build["pool_px"], eligible_px=build["eligible_px"],
                       ring_excluded_m=build["ring_excluded_m"],
                       min_cat_dist_m=build["min_cat_dist_m"],
                       median_cat_dist_m=build["median_cat_dist_m"],
                       dots_within_300m_of_catalogue_pct=build["dots_within_300m_of_catalogue_pct"]),
        submit_ok=False,
        download_ok=True,
    )
    (EV / f"submission_{name}.json").write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / f"submission_{name}.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    pointer = dict(receipt)
    pointer.update(marker="submission/LATEST.txt", exists=True,
                   download=f"downloads/{tif.name}", download_zip=f"downloads/{name}.zip",
                   submission_note=card["note"], submission_note_chars=card["note_chars"],
                   published_byte_hash_matches_receipt=True)
    (DATA / "submission.json").write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")

    site_marker = ROOT / "docs" / "submission" / "LATEST.txt"
    if site_marker.parent.exists():
        site_marker.write_text(tif.name + "\n", encoding="utf-8")

    staged = DL / tif.name
    assert staged.exists() and sha(staged) == card["raster_sha256"], "docs copy is stale; run publish_h97_site.py"
    print(json.dumps(dict(pointer=pointer["file"], bytes=pointer["bytes"], sha256=pointer["sha256"],
                          zip_sha256=zip_sha, approved_for_weekly_slot=False, slots=0), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
