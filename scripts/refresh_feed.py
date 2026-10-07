#!/usr/bin/env python3
"""Regenerate the site's data feed from the evidence directory (and, when reachable, the live board).

The site renders from ``docs/data/*.json`` only - no number is typed into the HTML - so a refresh is
the whole of "keeping the page current".  This script is what the committed GitHub Actions workflow
runs on a schedule and on every push, and it is also runnable by hand:

    python3 scripts/refresh_feed.py            # offline: evidence -> JSON, leaderboard left as-is
    python3 scripts/refresh_feed.py --fetch    # also try to re-scrape the public leaderboard

Network failures are recorded in ``feed.json`` as ``leaderboard_status`` rather than swallowed, so
the page can show "last fetched N hours ago" honestly instead of pretending to be live.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
DOCS = ROOT / "docs"
DATA = DOCS / "data"
DL = DOCS / "downloads"
BOARD = "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"
OUR_TEAM = "extradr19"
OUR_BEST = 0.2778          # owner-reported best for this group, see knowledge/06


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def write(name: str, obj) -> Path:
    DATA.mkdir(parents=True, exist_ok=True)
    p = DATA / name
    p.write_text(json.dumps(obj, indent=1) + "\n")
    return p


def _json_safe(text: str) -> tuple[str, int]:
    """Turn `NaN` / `Infinity` into `null`, and report how many times.

    Python's ``json.dumps`` emits bare ``NaN`` for a missing correlation, which ``json.loads`` reads back
    happily and ``JSON.parse`` -- the browser -- rejects outright. Every page that renders that file then
    shows "not measured" for a number the repo actually has an opinion about, silently, and the failure is
    indistinguishable from "we never ran the test". The evidence keeps its NaN (it is the honest value:
    undefined, not zero); the published copy says ``null``, which is what ``render.js`` already prints as
    "--". Found by reading the live page, not the local files.
    """
    pat = re.compile(r"(?<=[\[:,\[])\s*(?:NaN|-?Infinity)\b")
    n = len(pat.findall(text))
    return pat.sub("null", text), n


def copy_evidence() -> list[str]:
    """Every evidence JSON is published, with NaN normalised to null so a browser can parse it."""
    out = []
    DATA.mkdir(parents=True, exist_ok=True)
    for src in sorted(EV.glob("*.json")):
        body, n_fix = _json_safe(src.read_text())
        (DATA / src.name).write_text(body)
        out.append(src.name + (f" (+{n_fix} NaN->null)" if n_fix else ""))
    return out


def download_index() -> int:
    """Write docs/downloads/index.html: every shippable raster, the current one first, with its hash,
    size and — this is the part that matters — the format gate re-run on the bytes as served.

    Two reasons this is generated and not hand-written:

    * A Pages build serves a directory only if an index.html exists, so without this the "click the file
      to submit" promise dies on a 404 instead of a download.
    * `docs/downloads/` accumulates rasters from *other* sessions of this family once their PRs merge.
      One of those is a NaN-outside-the-footprint variant, which the portal's `0 <= v <= 1` check
      rejects (see knowledge/06 IR-52-006). A download page that lists it next to ours, unlabelled, is
      a way to lose a weekly submission slot. So every file is re-checked here and judged on its bytes,
      and a file that fails is marked failed.
    """
    import hashlib
    import html
    import importlib.util

    # Reading a GeoTIFF needs rasterio, which the CI runner deliberately does not have (see
    # tests/test_workflows.py: the scheduled feed must not depend on a package index).  Without it we do
    # NOT rewrite the page - the committed version, generated where the toolchain exists, keeps the
    # verdicts.  A feed that silently degrades a safety table is worse than one that leaves it alone.
    if importlib.util.find_spec("rasterio") is None:
        log("downloads: rasterio absent, leaving the committed verdict table as it is")
        return -1

    sample = ROOT / "data" / "sample_submission.tif"
    cur = None
    latest = DL.parent.parent / "submission" / "LATEST.txt"
    if latest.exists():
        cur = latest.read_text().strip()

    entries = []
    for f in sorted(DL.glob("*.tif")):
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        verdict, note = "unknown", ""
        try:
            sys.path.insert(0, str(ROOT / "src"))
            from gems52 import gates as _g  # noqa: E402
            rep = _g.format_report(f, sample) if sample.exists() else None
            if rep is None:
                note = "no sample_submission.tif to compare against"
            elif rep["ok"]:
                verdict, note = "ok", (f"{rep['n_nonzero']:,} positive px · max {rep['max']:.3g} · "
                                       f"{rep['crs']} · {rep['height']}×{rep['width']}")
            else:
                verdict, note = "fail", "; ".join(rep["problems"])[:300]
        except Exception as e:                                    # noqa: BLE001
            note = f"gate not run: {type(e).__name__}: {str(e)[:120]}"
        entries.append(dict(name=f.name, bytes=f.stat().st_size, sha=h, verdict=verdict, note=note,
                            mtime=f.stat().st_mtime, current=(f.name == cur)))
    entries.sort(key=lambda e: (not e["current"], e["verdict"] != "ok", -e["mtime"]))

    def row(e):
        badge = {"ok": '<span class="tag ok">passes format gate</span>',
                 "fail": '<span class="tag no">WILL BE REJECTED by the portal</span>',
                 "unknown": '<span class="tag warn">gate not run</span>'}[e["verdict"]]
        first = '<b>current build</b> · ' if e["current"] else ""
        return (f'<tr><td>{first}<a href="{html.escape(e["name"])}">{html.escape(e["name"])}</a><br>'
                f'<span class="small muted">{badge} — {html.escape(e["note"])}</span></td>'
                f'<td>{e["bytes"]:,}</td><td><code>{e["sha"][:16]}…</code></td>'
                f'<td>{time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(e["mtime"]))}</td></tr>')

    csv = [f for f in sorted(DL.glob("*.csv"), key=lambda x: x.stat().st_mtime, reverse=True)]
    extra = "".join(f'<li><a href="{html.escape(f.name)}">{html.escape(f.name)}</a> '
                    f'({f.stat().st_size:,} bytes)</li>' for f in csv)
    n_ok = sum(1 for e in entries if e["verdict"] == "ok")
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Downloads - GEMSDOE52</title>
<link rel="stylesheet" href="../style.css"></head>
<body><main class="wrap">
<p><a href="../index.html">&larr; GEMSDOE52</a></p>
<h1>Downloads</h1>
<p class="lede">Files from every session of this family land here, so the table re-checks each one
against the portal rules on its own bytes rather than trusting the filename.
<strong>Only the {n_ok} row(s) marked "passes format gate" are submittable.</strong> Download one, then
follow <a href="../executive-summary.html">the submission steps</a> - no renaming, no reprojecting,
nothing to open in a GIS.</p>
<table class="data"><thead><tr><th>file</th><th>bytes</th><th>sha256 (first 16)</th><th>built</th></tr>
</thead><tbody>
{chr(10).join(row(e) for e in entries) if entries else '<tr><td colspan="4">no raster staged yet</td></tr>'}
</tbody></table>
{f'<h2>Companion tables</h2><ul>{extra}</ul>' if extra else ''}
<p class="note">Generated by <code>scripts/refresh_feed.py</code> from the contents of this
directory; hashes are computed from the bytes on disk, and the verdict column is
<code>gems52.gates.format_report</code> run on the same bytes a browser would receive.</p>
</main></body></html>
"""
    (DL / "index.html").write_text(body)
    return len(entries)


def make_zip(name: str) -> str | None:
    """Write docs/downloads/<stem>.zip: the raster plus the note the portal's notes box wants.

    One click should hand over everything the submission step needs, so the ZIP carries the exact
    text to paste and the hash to check the download against.
    """
    import zipfile
    src = ROOT / "submission" / name
    if not src.exists():
        return None
    ev = EV / f"submission_{name.replace('.tif', '')}.json"
    d = json.loads(ev.read_text()) if ev.exists() else {}
    stem = name.replace(".tif", "")
    note = (
        f"{name}\n"
        f"sha256 {d.get('sha256')}\n"
        f"{d.get('bytes')} bytes, 1 band, float32, EPSG:32611, values in [0,1], no NaN.\n\n"
        f"SUBMISSION NOTE (<=200 chars, paste into the portal's notes box):\n"
        f"{submission_note(d)}\n\n"
        f"What it is: {d.get('budget')} emitted pixels = {d.get('retained_core_px')} px retained "
        f"core (the double-corroborated atom A&C, whose credit the organiser's own published scores "
        f"bound exactly) + {d.get('novel_px')} px strictly novel "
        f"({d.get('novel_along_strike_px')} along the recovered strike of that structure, "
        f"{d.get('novel_far_px')} free candidates on the same fabric).\n"
        f"Nothing is emitted within {d.get('corridor_excluded_m')} m of a mapped trace, because that "
        f"ring's credit is exactly zero in the organiser's own scores (knowledge/07 s2).\n"
        f"Projected DTI {d.get('projected_dti', {}).get('mean_dti')} "
        f"(P(win over 0.2778) {d.get('projected_dti', {}).get('p_win')}); the projection is an "
        f"integral over a stated prior, not a forecast - see evidence/revealed_budget.json.\n"
    )
    zp = DL / f"{stem}.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(src, arcname=name)
        z.writestr("SUBMISSION_NOTE.txt", note)
        if ev.exists():
            z.write(ev, arcname="evidence.json")
    return str(zp)


def submission_note(d: dict) -> str:
    """The <=200-character note that distinguishes this submission later."""
    n = (f"H53 revealed-core {d.get('retained_core_px', 0)}px + {d.get('novel_px', 0)}px novel "
         f"strike-continuation; 200m corridor excluded; |G|=14089")
    return n[:200]


def latest_submission() -> dict:
    sub = ROOT / "submission"
    latest = sub / "LATEST.txt"
    if not latest.exists():
        return {"exists": False, "file": None, "note": "no submission built yet in this checkout"}
    name = latest.read_text().strip()
    ev = EV / f"submission_{name.replace('.tif', '')}.json"
    if not ev.exists():
        cands = sorted(EV.glob(f"submission_{name.replace('.tif', '')}*.json"))
        if not cands:
            return {"exists": True, "file": name, "evidence": None}
        ev = cands[-1]
    d = json.loads(ev.read_text())
    d["exists"] = True
    d["download"] = f"downloads/{name}"
    d["download_zip"] = f"downloads/{name.replace('.tif', '')}.zip"
    d["submission_note"] = submission_note(d)
    d["submission_note_chars"] = len(submission_note(d))
    d["size_bytes_local"] = (sub / name).stat().st_size if (sub / name).exists() else None
    return d


def parse_board(html: str) -> list[dict]:
    """Rows of the public leaderboard table: rank, team, score."""
    rows: list[dict] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        tds = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(tds) < 2:
            continue
        num = [t for t in tds if re.fullmatch(r"0\.\d{3,6}", t)]
        if not num:
            continue
        rows.append(dict(rank=tds[0], team=tds[1] if len(tds) > 1 else "",
                         score=float(num[0]), extra=[t for t in tds[2:] if t][:2]))
    return rows


def fetch_board(do_fetch: bool) -> dict:
    out = dict(source=BOARD, our_team=OUR_TEAM, our_best_reported=OUR_BEST,
               note=("participant-level public board; it carries no filename, hash or upload "
                     "receipt, so no file-to-score mapping on this site is organiser-authenticated"))
    snap = ROOT / "registry/leaderboard_snapshot_2026-10-06.json"
    if not do_fetch:
        if snap.exists():
            out.update(json.loads(snap.read_text()))
            out["status"] = "offline snapshot (feed run without --fetch)"
            return out
        out["status"] = "not fetched, and no snapshot on disk"
        return out
    try:
        req = urllib.request.Request(BOARD, headers={"User-Agent": "Mozilla/5.0 (research)"})
        html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
        rows = parse_board(html)
        if not rows:
            raise ValueError("leaderboard table parsed empty - page layout changed")
        rows = rows[:60]
        ours = [r for r in rows if r["team"].lower().startswith(OUR_TEAM.lower())]
        out.update(status="fetched", fetched_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   rows=rows, n_rows=len(rows), top=rows[0]["score"] if rows else None,
                   our_rows=ours,
                   gap_to_top=round((rows[0]["score"] - OUR_BEST), 4) if rows else None)
    except Exception as e:                                    # noqa: BLE001
        out["status"] = f"unreachable: {type(e).__name__}: {str(e)[:160]}"
        if snap.exists():
            # fall back to the last verified snapshot rather than showing an empty board, and say so
            out.update({k: v for k, v in json.loads(snap.read_text()).items()
                        if k in ("rows", "top", "fetched_utc", "column_header_on_board", "gap_to_top")})
            out["status"] += " — serving the last verified snapshot instead"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="also re-scrape the public leaderboard")
    a = ap.parse_args()
    DL.mkdir(parents=True, exist_ok=True)
    copied = copy_evidence()
    # Stage the rasters BEFORE building the index. The index re-runs the format gate on whatever is
    # in docs/downloads/, so copying afterwards left it permanently one run behind: the current
    # submission was on disk but absent from the table, and the "download the file and submit it"
    # promise pointed at last round's artefact.
    sub_name = (ROOT / "submission" / "LATEST.txt").read_text().strip() \
        if (ROOT / "submission" / "LATEST.txt").exists() else None
    for f in sorted((ROOT / "submission").glob("*.tif")):
        tgt = DL / f.name
        if not tgt.exists() or tgt.stat().st_size != f.stat().st_size:
            tgt.write_bytes(f.read_bytes())
    # a one-click ZIP beside the TIF: the raster plus the submission note the portal asks for
    if sub_name:
        make_zip(sub_name)
    n_dl = download_index()      # -1 when the verdicts could not be recomputed here
    sub = latest_submission()
    board = fetch_board(a.fetch)
    write("leaderboard.json", board)
    write("submission.json", sub)
    for pat in ("*-candidates.csv",):
        for f in sorted((EV).glob(pat))[-1:]:
            (DL / f.name).write_text(f.read_text())
    # the reasoning table is published next to the raster it explains
    write("feed.json", dict(
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        repo="buffedlizard55-lab/GEMSDOE52", branch="arena/4ab47a80-gemsdoe52",
        files=sorted(p.name for p in DATA.glob("*.json")), evidence_copied=copied,
        leaderboard_status=board.get("status"), submission=sub.get("file"),
        downloads=n_dl,
        pipeline=dict(
            footprint=5167373, catalogue=60988,
            g_bracket=[8128, 14089], g_point_estimate=14088.7,
            g_note="bracket from T<=|G| over 13 scored files; point estimate from T(B)-T(A)=0 on "
                   "the exactly-nested pair, i.e. from the <=200 m ring around the mapped catalogue "
                   "carrying no credit (knowledge/07 s2)",
            accept_bar_at_our_best=round(0.2 * OUR_BEST / (1 - 0.2 * OUR_BEST), 5),
            rule="emit a pixel iff its expected kernel credit clears "
                 "alpha*DTI/(1-alpha*DTI); across DTI 0.28-0.46 that is 'within 224 m of an "
                 "uncatalogued fault pixel'"),
    ))
    log(f"feed: {len(list(DATA.glob('*.json')))} json files, leaderboard {board.get('status')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
