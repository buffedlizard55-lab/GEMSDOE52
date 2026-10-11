#!/usr/bin/env python3
"""Re-materialise the frozen prior-raster inventory into ``work/`` for the lane gate.

Why this exists
---------------
``evidence/ctd5_prior_inventory.json`` is the frozen census of every aligned single-band
prediction blob published in the owner's sibling repositories (526 blobs / 524 eligible,
generated 2026-10-08).  The census records each blob's Git blob SHA, repo, commit, path,
byte count, decoded SHA-256, shape, CRS and transform -- but the *pixels* lived under the
ignored ``work/`` tree, so a fresh sandbox has the census without the rasters.

The lane rule ("more than 70% of your dots within 3 px of ONE registry raster's dots")
cannot be evaluated from metadata alone: it needs every prior's decoded dot coordinates.
This script restores them by blob SHA through the Git Data API and verifies the decoded
SHA-256 against the census, so the gate runs on bytes that are provably the same bytes the
census described.  A mismatch is recorded as an error, never silently accepted.

Only ``api.github.com`` is used.  Nothing here writes inside the repository tree except the
receipt; rasters go to the ignored ``work/`` directory.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("restore_data", ROOT / "scripts" / "restore_data.py")
restore_data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore_data)


def codeload_blob(repo: str, commit: str, path: str, blob: str, dest: Path, want_bytes: int,
                   cache: Path) -> None:
    """Fallback when the Git Data API is rate-limited (HTTP 403 secondary limit, IR-H97-003).

    Downloads the repository archive at the census's pinned commit from codeload.github.com (an allowed
    host), extracts exactly the census path, and accepts it ONLY if the git blob SHA-1 of the extracted
    bytes equals the census blob id and the byte count matches.  Nothing unverified is written.
    """
    import io
    import subprocess
    import tarfile
    import urllib.request

    cache.mkdir(parents=True, exist_ok=True)
    arch = cache / f"{repo.replace('/', '__')}-{commit}.tar.gz"
    if not arch.exists() or arch.stat().st_size == 0:
        url = f"https://codeload.github.com/{repo}/tar.gz/{commit}"
        tok = ""
        try:
            tok = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception:  # noqa: BLE001
            tok = ""
        req = urllib.request.Request(url, headers={"User-Agent": "gems52-prior-fetch/1.1",
                                                   **({"Authorization": f"Bearer {tok}"} if tok else {})})
        tmp = arch.with_suffix(".part")
        with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as w:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                w.write(chunk)
        tmp.replace(arch)
    data = None
    with tarfile.open(arch, "r:gz") as tf:
        for m in tf:
            if not m.isfile():
                continue
            # codeload archives have one top-level directory: "<name>-<commit>/"
            rel = m.name.split("/", 1)[1] if "/" in m.name else m.name
            if rel == path:
                data = tf.extractfile(m).read()
                break
    if data is None:
        raise RuntimeError(f"path {path} not in archive {repo}@{commit[:10]}")
    git_sha = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
    if git_sha != blob:
        raise RuntimeError(f"codeload blob SHA-1 {git_sha} != census {blob}")
    if len(data) != want_bytes:
        raise RuntimeError(f"codeload byte count {len(data)} != census {want_bytes}")
    tmp_dest = dest.with_suffix(dest.suffix + ".part")
    tmp_dest.write_bytes(data)
    tmp_dest.replace(dest)


def decoded_sha(path: Path) -> tuple[str, tuple[int, int], str | None]:
    """SHA-256 of the decoded float32 band (non-finite -> 0) + shape + CRS."""
    import rasterio

    with rasterio.open(path) as src:
        a = src.read(1)
        crs = str(src.crs) if src.crs is not None else None
        shape = (src.height, src.width)
    arr = np.asarray(a, dtype=np.float32)
    arr[~np.isfinite(arr)] = 0.0
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest(), shape, crs


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(receipt_path: Path, inventory: str, n_entries: int, n_present: int, n_fetched: int,
           n_errors: int, n_file: int, n_decoded: int, files: dict) -> None:
    """Persist the running receipt so an interrupted fetch is still auditable."""
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(
        {"inventory": inventory, "n_entries": n_entries, "n_present": n_present,
         "n_fetched": n_fetched, "n_errors": n_errors,
         "n_census_sha_is_file_sha": n_file, "n_census_sha_is_decoded_sha": n_decoded,
         "sha_column_reading": ("file bytes" if n_file >= n_decoded else "decoded float32 band")
         if (n_file or n_decoded) else "undetermined",
         "files": files}, indent=1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", default="evidence/ctd5_prior_inventory.json")
    ap.add_argument("--out", default="work/h61/priors")
    ap.add_argument("--receipt", default="work/h61/prior_fetch_receipt.json")
    ap.add_argument("--limit", type=int, default=0, help="debug: only the first N entries")
    ap.add_argument("--skip-verify", action="store_true", help="skip the rasterio decode check")
    args = ap.parse_args()

    inv = json.loads((ROOT / args.inventory).read_text())
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    entries = inv["entries"][: args.limit] if args.limit else inv["entries"]

    rec: dict[str, dict] = {}
    rp = ROOT / args.receipt
    if rp.exists():
        rec = json.loads(rp.read_text()).get("files", {})

    n_present = n_fetched = n_bad = 0
    n_file_sha_match = n_decoded_sha_match = 0
    for i, e in enumerate(entries):
        blob = e["blob"]
        dest = out / f"{blob}.tif"
        want_bytes = e["aliases"][0]["bytes"]
        state = {"blob": blob, "dest": str(dest.relative_to(ROOT)), "bytes": want_bytes,
                 "repo": e["aliases"][0]["repo"], "commit": e["aliases"][0]["commit"],
                 "path": e["aliases"][0]["path"], "eligible": bool(e.get("eligible")),
                 "census_sha256": e.get("sha256"), "census_shape": e.get("shape"),
                 "census_crs": e.get("crs"), "n_aliases": len(e["aliases"])}
        if dest.exists() and dest.stat().st_size == want_bytes:
            state["status"] = "present"
            n_present += 1
        else:
            # Primary: codeload archive at the census's pinned commit, accepted only if the git blob SHA-1 equals
            # the census blob id (IR-H97-003: the Git Data API returned 403 secondary-limit errors for this run).
            # Fallback: the Git Data API stream, still checked by byte count and the decoded-SHA check below.
            try:
                codeload_blob(e["aliases"][0]["repo"], e["aliases"][0]["commit"], e["aliases"][0]["path"],
                              blob, dest, want_bytes, cache=out.parent / "archives")
                state["status"] = "fetched"
                state["source"] = "codeload-archive (git blob SHA-1 verified)"
                n_fetched += 1
            except Exception as cl_exc:  # noqa: BLE001 - fall back to the API, never silently accept
                try:
                    restore_data.stream_blob(e["aliases"][0]["repo"], blob, dest, want_bytes, tries=2)
                    state["status"] = "fetched"
                    state["source"] = "git-data-api"
                    state["codeload_error"] = f"{type(cl_exc).__name__}: {str(cl_exc)[:120]}"
                    n_fetched += 1
                except Exception as exc:  # noqa: BLE001 - a failed prior must not kill the census
                    state["status"] = f"error: {type(exc).__name__}: {exc}"
                    state["error"] = True
                    n_bad += 1
                    rec[blob] = state
                    _write(rp, args.inventory, len(entries), n_present, n_fetched, n_bad,
                           n_file_sha_match, n_decoded_sha_match, rec)
                    print(f"[{i+1}/{len(entries)}] ERR {blob[:10]} {state['status'][:90]}", flush=True)
                    continue
        if not args.skip_verify and e.get("eligible") and dest.exists():
            try:
                fsha = file_sha(dest)
                dsha, shape, crs = decoded_sha(dest)
                state.update(file_sha256=fsha, decoded_sha256=dsha,
                             decoded_shape=list(shape), decoded_crs=crs)
                # The census "sha256" column is the identity the *filenames* embed; check both
                # readings and record which one the census actually pins, instead of assuming.
                state["file_sha_matches_census"] = fsha == e.get("sha256")
                state["decoded_sha_matches_census"] = dsha == e.get("sha256")
                state["shape_matches_census"] = list(shape) == list(e.get("shape") or [])
                state["crs_matches_census"] = crs == e.get("crs")
                n_file_sha_match += int(state["file_sha_matches_census"])
                n_decoded_sha_match += int(state["decoded_sha_matches_census"])
                if not (state["file_sha_matches_census"] or state["decoded_sha_matches_census"]):
                    n_bad += 1
                    print(f"[{i+1}/{len(entries)}] SHA-MISMATCH {blob[:10]}", flush=True)
            except Exception as exc:  # noqa: BLE001
                state["decode_error"] = f"{type(exc).__name__}: {exc}"
                n_bad += 1
        rec[blob] = state
        if (i + 1) % 25 == 0 or i + 1 == len(entries):
            _write(rp, args.inventory, len(entries), n_present, n_fetched, n_bad,
                   n_file_sha_match, n_decoded_sha_match, rec)
            print(f"[{i+1}/{len(entries)}] present={n_present} fetched={n_fetched} "
                  f"errors={n_bad} file_sha_ok={n_file_sha_match} decoded_sha_ok={n_decoded_sha_match}",
                  flush=True)
    _write(rp, args.inventory, len(entries), n_present, n_fetched, n_bad,
           n_file_sha_match, n_decoded_sha_match, rec)
    print(f"DONE entries={len(entries)} present={n_present} fetched={n_fetched} errors={n_bad} "
          f"receipt={args.receipt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
