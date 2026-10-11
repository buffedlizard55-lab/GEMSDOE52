#!/usr/bin/env python3
"""Restore the frozen 526-blob prior census from its pinned Git commits.

This is a transport fallback for ``scripts/fetch_prior_inventory.py`` when the Git Data REST API
is rate-limited. It does not discover, edit, or filter the census: every source is a frozen
(repo, commit, path, Git blob SHA) alias. Each materialized file is checked against its Git blob
SHA-1 and census byte count. Run the shared fetcher afterwards to produce its standard receipt
and verify decoded raster SHA-256, shape, and CRS before any registry gate.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = ROOT / "evidence/ctd5_prior_inventory.json"
DEFAULT_OUT = ROOT / "work/h61/priors"
DEFAULT_GIT = ROOT / "work/ctd5/gitrepos"


def git(args: list[str], *, cwd: Path | None = None, stdout=None) -> str:
    p = subprocess.run(["git", *args], cwd=cwd, stdout=stdout or subprocess.PIPE,
                       stderr=subprocess.PIPE, text=stdout is None)
    if p.returncode:
        err = p.stderr if isinstance(p.stderr, str) else p.stderr.decode("utf-8", "replace")
        raise RuntimeError(f"git {' '.join(args[:5])}: {err.strip()[:300]}")
    return p.stdout.strip() if isinstance(p.stdout, str) else ""


def prepare(repo: str, commit: str, root: Path) -> Path:
    owner, name = repo.split("/", 1)
    dest = root / owner / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/{repo}.git"
    if not (dest / ".git").exists():
        subprocess.run(["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout",
                        "--depth=1", url, str(dest)], check=True, cwd=ROOT)
    else:
        remote = git(["-C", str(dest), "remote", "get-url", "origin"])
        if remote.rstrip("/") != url.rstrip("/"):
            raise RuntimeError(f"cached clone origin mismatch for {repo}: {remote}")
    # Fetch only the pinned commit/tree; individual TIFF blobs arrive lazily from the same commit.
    if subprocess.run(["git", "-C", str(dest), "cat-file", "-e", f"{commit}^{{commit}}"],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        git(["-C", str(dest), "fetch", "--quiet", "--filter=blob:none", "--depth=1", "origin", commit])
    return dest


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--git-dir", type=Path, default=DEFAULT_GIT)
    args = ap.parse_args()
    inventory = json.loads(args.inventory.read_text())
    entries = inventory["entries"]
    args.out.mkdir(parents=True, exist_ok=True)
    args.git_dir.mkdir(parents=True, exist_ok=True)
    prepared: dict[tuple[str, str], Path] = {}
    n_restored = n_cached = n_alias_fallback = 0
    failures: list[dict] = []
    for i, entry in enumerate(entries, 1):
        blob = entry["blob"]
        want_bytes = int(entry["aliases"][0]["bytes"])
        dest = args.out / f"{blob}.tif"
        if dest.exists() and dest.stat().st_size == want_bytes:
            # Recompute the Git object ID below as well; size alone is not evidence.
            aliases = entry["aliases"]
        else:
            aliases = entry["aliases"]
        restored = False
        last_error = None
        for ai, alias in enumerate(aliases):
            key = (alias["repo"], alias["commit"])
            try:
                repo_dir = prepared.get(key)
                if repo_dir is None:
                    repo_dir = prepare(alias["repo"], alias["commit"], args.git_dir)
                    prepared[key] = repo_dir
                spec = f"{alias['commit']}:{alias['path']}"
                source_blob = git(["-C", str(repo_dir), "rev-parse", spec])
                if source_blob != blob:
                    last_error = f"pinned path resolved to blob {source_blob}, expected {blob}"
                    continue
                if dest.exists() and dest.stat().st_size == want_bytes:
                    got = git(["-C", str(repo_dir), "hash-object", "--no-filters", str(dest.resolve())])
                    if got == blob:
                        n_cached += 1
                        restored = True
                        break
                    dest.unlink()
                tmp = dest.with_suffix(".tif.partial")
                with tmp.open("wb") as fh:
                    git(["-C", str(repo_dir), "show", spec], stdout=fh)
                got_bytes = tmp.stat().st_size
                if got_bytes != want_bytes:
                    tmp.unlink(missing_ok=True)
                    last_error = f"byte count {got_bytes} != census {want_bytes}"
                    continue
                got = git(["-C", str(repo_dir), "hash-object", "--no-filters", str(tmp.resolve())])
                if got != blob:
                    tmp.unlink(missing_ok=True)
                    last_error = f"Git blob SHA {got} != census {blob}"
                    continue
                tmp.replace(dest)
                n_restored += 1
                n_alias_fallback += int(ai > 0)
                restored = True
                break
            except Exception as exc:  # preserve every alias attempt; another frozen alias may work
                last_error = f"{type(exc).__name__}: {exc}"
        if not restored:
            failures.append(dict(blob=blob, error=last_error, aliases=len(aliases)))
        if i % 25 == 0 or i == len(entries):
            print(f"[{i}/{len(entries)}] restored={n_restored} cached={n_cached} "
                  f"alias_fallbacks={n_alias_fallback} failures={len(failures)}", flush=True)
    receipt = dict(inventory=str(args.inventory.relative_to(ROOT) if args.inventory.is_relative_to(ROOT) else args.inventory),
                   entries=len(entries), restored=n_restored, verified_cached=n_cached,
                   alias_fallbacks=n_alias_fallback, failures=failures,
                   transport="git smart HTTP to github.com; pinned commit/path and Git blob SHA-1 verified",
                   next_step="Run scripts/fetch_prior_inventory.py to decode and verify census SHA-256, shape, and CRS.")
    path = ROOT / "work/ctd5/git_restore_receipt.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return 0 if not failures and n_restored + n_cached == len(entries) else 1


if __name__ == "__main__":
    sys.exit(main())
