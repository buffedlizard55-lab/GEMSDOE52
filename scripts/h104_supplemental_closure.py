#!/usr/bin/env python3
"""H104 supplemental closure — idempotent, shared tools only.  Three jobs:

1. **Bind the receipts to the code.** Records the SHA-256 of the round runner, of the shared tools the
   runner imports, and of every ``evidence/h104_*.json`` receipt, so a receipt can never be mistaken
   for the output of a different version of the script (IR-H104-004).

2. **Close uniqueness against the full sibling census of 526 blobs** (`evidence/ctd5_prior_inventory.json`,
   the frozen 2026-10-08 census of every aligned single-band prediction blob published in the owner's
   sibling repositories). This is metadata-only: the decoded SHA-256 of our raster is compared to the
   census's own ``sha256`` column for every entry. A match would be a *literal* duplicate; no match
   means the file is not any censused blob, but it does **not** by itself establish pixel-level
   novelty — that needs the pixels, which job 3 supplies when they are materialised.

3. **Pixel-level closure when the census pixels exist.** If ``--priors`` holds the materialised
   censused rasters (``scripts/fetch_prior_inventory.py --out work/h95/priors``), run the *shared*
   ``gems52.gates.uniqueness_report`` and ``gems52.gates.lane_report`` against them and store the
   result under ``supplemental_census_closure``. Nothing is forked; nothing is deleted.

Writes ``evidence/h104_gates.json``. Re-running replaces only this script's own keys.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import gates  # noqa: E402

EVID = ROOT / "evidence"
OUT = EVID / "h104_gates.json"
CARD = json.loads((EVID / "h104_run_card.json").read_text())
SAMPLE = ROOT / "data/sample_submission.tif"
TIF = ROOT / CARD["validator"]["path"]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def decoded_sha(array: np.ndarray) -> str:
    a = np.asarray(array, dtype=np.float32)
    a = np.where(np.isfinite(a), a, 0.0)
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--priors", default="work/h95/priors", help="materialised census rasters (optional)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--skip-disk", action="store_true", help="keep the census block only")
    ap.add_argument("--skip-census", action="store_true", help="keep the disk block only (fast)")
    args = ap.parse_args(argv)
    out_path = Path(args.out)

    code = {str(p.relative_to(ROOT)): sha256_of(p) for p in sorted(
        [ROOT / "scripts/run_h104_thermal_gap.py", ROOT / "scripts/publish_h104_site.py",
         ROOT / "scripts/h104_supplemental_closure.py", ROOT / "scripts/h104_irregularities.py"]
        + [p for p in (ROOT / "src/gems52").glob("*.py")])}
    receipts = {}
    for p in sorted(EVID.glob("h104_*.json")):
        receipts[p.name] = dict(sha256=sha256_of(p), bytes=p.stat().st_size)

    census = json.loads((EVID / "ctd5_prior_inventory.json").read_text())
    with rasterio.open(TIF) as src:
        our = src.read(1)
    ours_decoded = decoded_sha(our)
    our_file = sha256_of(TIF)
    census_shas = {e.get("sha256") for e in census["entries"] if e.get("sha256")}
    identity = dict(
        artifact_file_sha256=our_file,
        artifact_decoded_sha256=ours_decoded,
        census_entries=len(census["entries"]),
        census_eligible=census.get("eligible_count"),
        census_distinct_sha256=len(census_shas),
        matches_census_file_or_decoded_sha=(our_file in census_shas) or (ours_decoded in census_shas),
        note=("metadata-only: a False here proves the file is not any censused blob byte-for-byte "
              "(file or decoded band); it does not prove pixel-level novelty, which job 3 measures "
              "against the materialised pixels"),
    )

    result = dict(runner_and_receipt_hashes=code, receipts=receipts, census_identity=identity)

    # The on-disk lane closure (submission/, docs/downloads/, data/scored/, data/reference/) is the
    # one that can see this repository's own earlier artifacts; the census closure above sees the
    # sibling repositories.  Both are reported, and the candidate itself is excluded from the disk
    # set so the report cannot compare the file to itself.
    disk = []
    for d in ("submission", "docs/downloads", "data/scored", "data/reference"):
        disk += sorted((ROOT / d).glob("*.tif"))
    # Exclude every copy of the candidate itself (submission/ + docs/downloads/*.tif), not just the
    # receipted path: comparing a file with its own copies is a self-match, not a lane finding.
    ours_bytes = TIF.read_bytes()
    disk = [p for p in disk if p.resolve() != TIF.resolve() and p.read_bytes() != ours_bytes]
    if disk and not args.skip_disk:
        with rasterio.open(SAMPLE) as s2:
            dom2 = np.isfinite(s2.read(1))
        dl = gates.lane_report(our.astype(np.float32), dom2, disk, sample=SAMPLE, phase="dots")
        result["supplemental_disk_closure"] = dict(
            n_priors=len(disk),
            literal_verdict=dl["literal"]["verdict"], policy_verdict=dl["policy"]["verdict"],
            policy_max_near_3px=dl["policy"]["max_near_3px_fraction"],
            policy_max_near_source=dl["policy"]["max_near_source"],
            max_near_3px_lift=dl["literal"]["max_near_3px_lift"],
            max_lift_source=dl["literal"]["max_lift_source"],
            max_lift_near_fraction=dl["literal"]["max_lift_near_fraction"],
            max_lift_coverage=dl["literal"]["max_lift_coverage"],
            lift_offenders=[Path(p).name for p in dl["literal"]["lift_offenders"]],
            coverage_explained_near=[Path(p).name for p in dl["literal"]["coverage_explained_near"]],
            high_lift_low_overlap=dl["literal"]["high_lift_low_overlap"],
            top_lift=sorted(((r.get("near_3px_lift") or 0.0, Path(r["path"]).name,
                              r.get("near_3px_fraction"), r.get("coverage_3px_of_eligible"))
                             for r in dl.get("per_prior", []) if "error" not in r
                             and r.get("near_duplicate")), reverse=True)[:5],
        )
    priors = ([] if args.skip_census else
              (sorted((ROOT / args.priors).glob("*.tif")) if (ROOT / args.priors).is_dir() else []))
    if priors:
        with rasterio.open(SAMPLE) as s:
            dom = np.isfinite(s.read(1))
        u = gates.uniqueness_report(our, priors)
        ld = gates.lane_report(our.astype(np.float32), dom, priors, sample=SAMPLE, phase="dots")
        ls = gates.lane_report(our.astype(np.float32), dom, priors, sample=SAMPLE, phase="surface")
        srt = sorted(((r.get("near_3px_fraction") or 0.0, Path(r["path"]).name,
                       r.get("coverage_3px_of_eligible"))
                      for r in ld.get("per_prior", []) if "error" not in r), reverse=True)[:5]
        lifts = sorted(((r.get("near_3px_lift") or 0.0, Path(r["path"]).name,
                         r.get("near_3px_fraction"), r.get("coverage_3px_of_eligible"),
                         r.get("universal_coverage_probe"))
                        for r in ld.get("per_prior", []) if "error" not in r), reverse=True)[:5]
        result["supplemental_census_closure"] = dict(
            n_priors=len(priors),
            novel_fraction=u.get("novel_fraction"),
            identical_to_a_prior=u.get("identical_to_a_prior"),
            distinct_from_every_comparable_prior=u.get("distinct_from_every_comparable_prior"),
            incomparable=[Path(r["path"]).name for r in u.get("per_prior", []) if "error" in r][:5],
            max_jaccard=max(((r.get("jaccard") or 0.0), Path(r["path"]).name)
                            for r in u.get("per_prior", []) if "error" not in r) if u.get("per_prior") else None,
            lane_dots_literal=ld["literal"]["verdict"],
            lane_dots_policy=ld["policy"]["verdict"],
            lane_dots_policy_max_near_3px=ld["policy"]["max_near_3px_fraction"],
            lane_dots_policy_max_near_source=ld["policy"]["max_near_source"],
            lane_dots_probes=ld["policy"].get("probe_paths"),
            lane_surface_literal=ls["literal"]["verdict"],
            lane_surface_max_spearman=ls["literal"]["max_spearman"],
            top_near=srt,
            max_near_3px_lift=ld["literal"].get("max_near_3px_lift"),
            max_lift_source=ld["literal"].get("max_lift_source"),
            max_lift_coverage=ld["literal"].get("max_lift_coverage"),
            lift_offenders=[Path(p).name for p in ld["literal"].get("lift_offenders", [])],
            coverage_explained_near=[Path(p).name for p in
                                     ld["literal"].get("coverage_explained_near", [])],
            high_lift_low_overlap=ld["literal"].get("high_lift_low_overlap"),
            top_lift=lifts,
            coverage_normalization=ld.get("coverage_normalization"),
        )
    else:
        result["supplemental_census_closure"] = dict(
            n_priors=0,
            note=(f"census pixels not materialised at {args.priors}; run "
                  "`python3 scripts/fetch_prior_inventory.py --out work/h95/priors --receipt "
                  "work/h95/prior_fetch_receipt.json` first. The metadata-only identity check above "
                  "still ran."),
        )

    if out_path.exists():
        old = json.loads(out_path.read_text())
        old.update(result)
        result = old
    out_path.write_text(json.dumps(result, indent=1, allow_nan=False) + "\n")
    print(json.dumps(dict(priors=len(priors),
                          census_matches=identity["matches_census_file_or_decoded_sha"],
                          closure=result["supplemental_census_closure"].get("lane_dots_policy"),
                          out=str(out_path.relative_to(ROOT))), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
