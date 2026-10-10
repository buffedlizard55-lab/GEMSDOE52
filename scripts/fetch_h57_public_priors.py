#!/usr/bin/env python3
"""Fetch publicly committed prediction TIFFs from the listed sibling GEMS sites.

Read-only GitHub API use via the authenticated ``gh`` CLI. Files are written to
an external/ignored directory (default /tmp/gems52-competitor-priors), never to
the repository. Every source tree and skipped/downloaded path is recorded in a
small evidence JSON. Competition inputs and external feature rasters are excluded.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OWNER = "buffedlizard55-lab"
MAX_BYTES_DEFAULT = 100 * 1024 * 1024


def gh_json(endpoint: str):
    result = subprocess.run(["gh", "api", endpoint], cwd=ROOT, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace")[:500])
    return json.loads(result.stdout)


def gh_blob(repo: str, blob_sha: str) -> bytes:
    result = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw+json",
                             f"repos/{OWNER}/{repo}/git/blobs/{blob_sha}"],
                            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace")[:500])
    return result.stdout


def excluded_input_path(path: str) -> bool:
    low = "/" + path.lower().lstrip("/")
    name = Path(path).name.lower()
    if name.startswith("training_features") or name in {"labels.tif", "labels.tiff", "sample_submission.tif", "sample_submission.tiff"}:
        return True
    return any(part in low for part in ("/data/raw/", "/external/", "/inputs/", "/input/"))


def source_list(repo_payload: list[dict]) -> list[dict]:
    wanted = set(re.findall(r"buffedlizard55-lab\.github\.io/([^/\s)\]]+)",
                            (ROOT / "README.md").read_text(encoding="utf-8")))
    wanted.update({"GEMSDOE53", "GEMSDOE54", "LEARNGEMSDOE", "GEMSDOE52"})
    indexed = {row["name"].lower(): row for row in repo_payload}
    selected = []
    for name in sorted(wanted, key=str.lower):
        row = indexed.get(name.lower())
        if row:
            selected.append(row)
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="/tmp/gems52-competitor-priors")
    parser.add_argument("--max-bytes", type=int, default=MAX_BYTES_DEFAULT,
                        help="skip individual blobs above this cap; default 100 MiB")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--receipt", default="evidence/h57_public_repo_priors.json")
    args = parser.parse_args()
    output = Path(args.output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    repo_payload = gh_json(f"users/{OWNER}/repos?per_page=100")
    if isinstance(repo_payload, dict):
        repo_payload = [repo_payload]
    repositories = source_list(repo_payload)
    inventories = []
    downloads = []
    for repo in repositories:
        name, branch = repo["name"], repo["default_branch"]
        result = dict(repository=name, default_branch=branch, pushed_at=repo.get("pushed_at"),
                      repository_url=repo.get("html_url"), tree_sha=None,
                      tree_truncated=None, tiff_paths=0, eligible_prediction_tiffs=0,
                      skipped=[], errors=[])
        try:
            tree_data = gh_json(f"repos/{OWNER}/{name}/git/trees/{branch}?recursive=1")
            result["tree_sha"] = tree_data.get("sha")
            result["tree_truncated"] = bool(tree_data.get("truncated"))
            if result["tree_truncated"]:
                result["errors"].append("GitHub recursive tree is truncated; this repository is only partially enumerated.")
            for item in tree_data.get("tree", []):
                path = item.get("path", "")
                if not path.lower().endswith((".tif", ".tiff")):
                    continue
                result["tiff_paths"] += 1
                size = int(item.get("size", 0))
                reason = None
                if excluded_input_path(path):
                    reason = "competition input or external feature source"
                elif size < 1000:
                    reason = "below 1,000-byte raster-prior scan minimum (likely a pointer/placeholder)"
                elif size > args.max_bytes:
                    reason = f"exceeds configured {args.max_bytes}-byte fetch cap"
                if reason:
                    result["skipped"].append(dict(path=path, size=size, reason=reason))
                    continue
                item_row = dict(repository=name, branch=branch, tree_sha=result["tree_sha"],
                                path=path, size=size, blob_sha=item["sha"],
                                source_url=f"https://github.com/{OWNER}/{name}/blob/{branch}/{path}")
                downloads.append(item_row)
                result["eligible_prediction_tiffs"] += 1
        except Exception as exc:
            result["errors"].append(f"tree enumeration failed: {type(exc).__name__}: {str(exc)[:350]}")
        inventories.append(result)
        print(f"{name}: {result['eligible_prediction_tiffs']} candidate TIFFs "
              f"({result['tiff_paths']} total paths)", flush=True)

    def fetch_one(item):
        target = output / item["repository"] / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if target.is_file() and target.stat().st_size == item["size"]:
                data = target.read_bytes()
                reused = True
            else:
                data = gh_blob(item["repository"], item["blob_sha"])
                target.write_bytes(data)
                reused = False
            row = dict(**item, fetched_path=str(target), downloaded_bytes=len(data),
                       sha256=hashlib.sha256(data).hexdigest(), reused=reused)
            if len(data) != item["size"]:
                row["error"] = f"download byte count {len(data)} != GitHub tree size {item['size']}"
            return row
        except Exception as exc:
            return dict(**item, error=f"{type(exc).__name__}: {str(exc)[:400]}")

    fetched = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(fetch_one, item) for item in downloads]
        for future in as_completed(futures):
            row = future.result()
            fetched.append(row)
            if row.get("error"):
                print(f"ERROR {row['repository']}:{row['path']}: {row['error']}", file=sys.stderr, flush=True)
    fetched.sort(key=lambda row: (row["repository"].lower(), row["path"].lower()))
    for row in fetched:
        repo = next((r for r in inventories if r["repository"] == row["repository"]), None)
        if repo is not None and row.get("error"):
            repo["errors"].append(dict(path=row["path"], error=row["error"]))
    record = dict(
        generated_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        method="GitHub REST Trees and Blobs API via gh; public repository only; no portal/site login; read-only",
        owner=OWNER, repositories_requested=[r["name"] for r in repositories],
        repositories_enumerated=len(inventories), recursive_tree_truncations=sum(bool(r["tree_truncated"]) for r in inventories),
        candidate_tiff_paths=len(downloads), downloaded_tiff_paths=sum(not bool(r.get("error")) for r in fetched),
        fetch_errors=sum(bool(r.get("error")) for r in fetched), output_directory=str(output),
        max_blob_bytes=args.max_bytes,
        scope="Prediction-like TIFF paths in these public repositories only. Private, uncommitted, unlinked, inaccessible, or over-cap files are not checked.",
        repositories=inventories, files=fetched)
    receipt_path = ROOT / args.receipt
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
    print(f"Fetched {record['downloaded_tiff_paths']}/{record['candidate_tiff_paths']} TIFFs; "
          f"{record['fetch_errors']} errors. Receipt: {receipt_path.relative_to(ROOT)}", flush=True)
    return 1 if record["fetch_errors"] or record["recursive_tree_truncations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
