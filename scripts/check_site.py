#!/usr/bin/env python3
"""Site verification pass — run it before publishing, and put its output in the PR.

Three things a static-but-data-driven site gets wrong silently:

1. **Broken links.** A nav entry to a page that does not exist is how "the site should be enough" dies.
2. **Data the JS asks for but the feed never wrote.** `fetch()` in a browser fails quietly and the page
   prints `–`, which reads like "no data yet" rather than "the generator is broken".
3. **Numbers typed into HTML.** Every figure must come from `docs/data/*.json`; a literal in the HTML is a
   number that goes stale the moment the evidence changes.

Run:  python3 scripts/check_site.py            (exit 1 on any breakage)
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATA = DOCS / "data"
H56_CURRENT_FILE = "gems52-h56-cotrain-disagreement-37654px-20261007T1630Z-zeros.tif"


class Scan(HTMLParser):
    """Collect anchors, script srcs, inline scripts, and fetch('data/x') targets."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []
        self.srcs: list[str] = []
        self.inline: list[str] = []
        self.stack: list[str] = []
        self.scratch: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.hrefs.append(a["href"])
        if tag in ("script", "link") and a.get("src"):
            self.srcs.append(a["src"])
        if tag in ("script", "link") and a.get("href"):
            self.srcs.append(a["href"])
        if tag == "script" and not a.get("src"):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == "script" and tag == "script":
            self.stack.pop()
            self.inline.append("\n".join(self.scratch))
            self.scratch = []

    def handle_data(self, data):
        if self.stack:
            self.scratch.append(data)


def main() -> int:
    problems: list[str] = []
    notes: list[str] = []
    node = shutil.which("node")
    notes.append(f"JS parser available: {bool(node)}" + ("" if node else " (falling back to balance checks)"))
    pages = sorted(DOCS.glob("*.html")) + [ROOT / "index.html"] + sorted((DOCS / "downloads").glob("*.html"))
    if not pages:
        print("no pages found", file=sys.stderr)
        return 1

    typed_numbers: list[str] = []
    js_checked: set[str] = set()
    for page in pages:
        text = page.read_text(encoding="utf-8", errors="replace")
        scan = Scan()
        scan.feed(text)
        rel = page.relative_to(ROOT)

        # 1. links resolve
        for h in scan.hrefs:
            if h.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            target = (page.parent / h.split("#")[0]).resolve()
            if not target.exists():
                problems.append(f"{rel}: dead link -> {h}")

        # 2. assets resolve
        for s in scan.srcs:
            if s.startswith(("http://", "https://", "data:")):
                continue
            if not (page.parent / s.split("#")[0]).resolve().exists():
                problems.append(f"{rel}: missing asset -> {s}")

        # 3. every fetch('data/x.json') has a file on disk
        wanted = set(re.findall(r"G52\.load\(['\"]([\w\-]+)['\"]\)", text))
        wanted |= set(re.findall(r"fetch\(['\"]data/([\w\-]+)\.json", text))
        for chunk in re.findall(r"Promise\.all\(\[([^\]]*)\]", text, re.S):
            wanted |= set(re.findall(r"['\"]([\w\-]+)['\"]", chunk))
        for name in sorted(x for x in wanted if x):
            if not (DATA / f"{name}.json").exists():
                problems.append(f"{rel}: JS asks for data/{name}.json, which the feed does not write")

        # 4. JS must parse.  A broken script tag on a data-driven page is invisible: the page loads, the
        #    numbers simply do not appear, and every reader blames the feed.  With node available we ask it
        #    directly; without it we fall back to a brace/paren balance check, which is weak but has already
        #    caught a real TDZ bug and an unbalanced row-array in tables.js.
        for i, blk in enumerate(s for s in scan.inline if s.strip()):
            if node:
                with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
                    fh.write(blk)
                    tmp = pathlib.Path(fh.name)
                rc = subprocess.run([node, "--check", str(tmp)], capture_output=True, text=True)
                tmp.unlink(missing_ok=True)
                if rc.returncode != 0:
                    problems.append(f"{rel}: inline script #{i} does not parse — "
                                    f"{rc.stderr.strip().splitlines()[0] if rc.stderr else 'node --check failed'}")
            else:
                for op, cl in (("{", "}"), ("(", ")")):
                    if blk.count(op) != blk.count(cl):
                        problems.append(f"{rel}: inline script #{i} is unbalanced on {op}{cl} "
                                        f"({blk.count(op)} vs {blk.count(cl)})")
                        break
        for js in (sorted(DOCS.glob("*.js")) if page.parent == DOCS and node else []):
            if str(js) in js_checked:
                continue
            js_checked.add(str(js))
            rc = subprocess.run([node, "--check", str(js)], capture_output=True, text=True)
            if rc.returncode != 0:
                problems.append(f"{js.relative_to(ROOT)}: does not parse — "
                                f"{rc.stderr.strip().splitlines()[0] if rc.stderr else 'node --check failed'}")

        # 5. no hard-coded scores in prose (they belong in the JSON the feed writes)
        if page.name != "index.html" or True:
            for m in re.finditer(r"\b0\.\d{4}\b", re.sub(r"<script.*?</script>", "", text, flags=re.S)):
                typed_numbers.append(f"{rel}: literal {m.group(0)} in HTML (should come from data/*.json)")

    # 6. the JSON itself must be valid and self-consistent where we can check it
    for f in sorted(DATA.glob("*.json")):
        try:
            # strict: Python's json accepts NaN/Infinity, JSON.parse does not.  A published file with a
            # bare NaN reads fine here and silently in the browser, which is how "not measured" appeared
            # on a page whose evidence file had a number in it.
            d = json.loads(f.read_text(), parse_constant=lambda x: (_ for _ in ()).throw(
                ValueError(f"non-JSON constant {x!r}; JSON.parse would reject this file")))
        except Exception as e:                                    # noqa: BLE001
            problems.append(f"data/{f.name}: invalid JSON ({e})")
            continue
        if f.name == "submission.json" and isinstance(d, dict) and d.get("exists"):
            fmt = d.get("format") or {}
            uni = d.get("uniqueness") or {}
            if fmt and not fmt.get("ok"):
                problems.append("submission.json: the staged file does NOT pass the format gate: "
                                + "; ".join(fmt.get("problems", [])[:3]))
            if uni and not uni.get('research_publication_ok', uni.get('ok')):
                problems.append('submission.json: canonical pattern uniqueness/literal non-union failed: ' + str(uni.get('relation_to_union')))
            if uni and not uni.get('ok'):
                if d.get('promoted') or (d.get('validation') or {}).get('approved_for_slot'):
                    problems.append('Scientific promotion despite failed original support-novelty diagnostic')
                else:
                    notes.append('Original >=20% support-novelty diagnostic FAIL is retained. Canonical-distinct research release only; no slot approval.')
            dl = DOCS / (d.get("download") or "")
            if not dl.exists():
                problems.append(f"submission.json: download path {d.get('download')} is not in docs/")
            elif dl.stat().st_size != d.get("bytes"):
                problems.append("submission.json: docs/ copy size != the size in the receipt")
            else:
                import hashlib
                got = hashlib.sha256(dl.read_bytes()).hexdigest()
                if got != d.get("sha256"):
                    problems.append(f"submission.json: sha256 mismatch ({got[:12]}… != {str(d.get('sha256'))[:12]}…)")
                else:
                    notes.append(f"download verified byte-for-byte against the receipt: {dl.name} "
                                 f"({d.get('bytes')} bytes, {got[:16]}…)")
        if f.name == "submission_r3.json" and isinstance(d, dict):
            if d.get("approved_for_weekly_slot") is not False or d.get("weekly_submission_slots_used") != 0:
                problems.append("submission_r3.json: R3 research artifact must remain non-approved with zero slots")
            if not str(d.get("artifact_status", "")).startswith("RESEARCH ONLY"):
                problems.append("submission_r3.json: missing explicit research-only status")
            if len(str(d.get("submission_note") or d.get("note") or "")) > 200:
                problems.append("submission_r3.json: note exceeds the 200-character limit")
            fmt = d.get("format") or {}
            uni = d.get("uniqueness") or {}
            if not fmt.get("ok") or not uni.get("research_publication_ok"):
                problems.append("submission_r3.json: research artifact failed its local format/canonical-pattern gate")
            if not (d.get("view_comparison") or {}).get("not_copied_or_literal_union"):
                problems.append("submission_r3.json: copy/union audit did not pass")
            dl = DOCS / "downloads" / str(d.get("file", ""))
            if not dl.exists():
                problems.append(f"submission_r3.json: research download missing: {dl.name}")
            elif dl.stat().st_size != d.get("bytes"):
                problems.append("submission_r3.json: research download size differs from its receipt")
            else:
                got = hashlib.sha256(dl.read_bytes()).hexdigest()
                if got != d.get("sha256"):
                    problems.append("submission_r3.json: research download hash differs from its receipt")
                else:
                    notes.append(f"R3 research TIFF verified against its independent receipt: {dl.name} ({got[:16]}…)")
        if f.name == "leaderboard.json" and d.get("rows"):
            top = d["rows"][0]["score"]
            if abs(float(d.get("top", top)) - float(top)) > 1e-9:
                problems.append("leaderboard.json: 'top' disagrees with row 1")

    # 7. the pages must actually serve, with the right content type for the .tif
    import http.server
    import socketserver

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(DOCS), **kw)

        def log_message(self, *a):
            pass

    class ThreadedTCPServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    httpd = ThreadedTCPServer(("127.0.0.1", 0), H)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        for path in ("index.html", "executive-summary.html", "h57.html", "h55.html", "h55-profile.html", "h55-edge.html",
                     "r3.html", "r3-hypotheses.html", "feed.html", "irregularities.html", "sources.html",
                     "downloads/index.html"):
            with urlopen(f"http://127.0.0.1:{port}/{path}", timeout=10) as r:
                body = r.read()
                if r.status != 200 or len(body) < 200:
                    problems.append(f"served {path}: status {r.status}, {len(body)} bytes")
        sub = json.loads((DATA / "submission.json").read_text())
        with urlopen(f"http://127.0.0.1:{port}/{sub['download']}", timeout=20) as r:
            n = len(r.read())
            ctype = r.headers.get("Content-Type", "")
            if n != sub["bytes"]:
                problems.append(f"served {sub['download']}: {n} bytes != {sub['bytes']} in the receipt")
            else:
                notes.append(f"the .tif serves through the site: {n:,} bytes, content-type {ctype}")

        # H55-PROFILE is a separate failed-gate follow-up; never conflate it with the main H55 incumbent.
        h55_path = DATA / "h55_profile.json"
        if h55_path.exists():
            import hashlib
            import zipfile
            import numpy as np
            import rasterio
            h55 = json.loads(h55_path.read_text())
            h55_file = DOCS / "downloads" / h55["file"]
            if not h55.get("research_only") or h55.get("weekly_slot_approved"):
                problems.append("h55_profile.json: research-only/failed-slot status is missing or unsafe")
            if len(h55.get("note", "")) > 200:
                problems.append("h55_profile.json: portal note exceeds 200 characters")
            if not h55_file.exists() or hashlib.sha256(h55_file.read_bytes()).hexdigest() != h55.get("sha256"):
                problems.append("h55_profile.json: published H55 TIFF missing or differs from SHA-256 receipt")
            else:
                with rasterio.open(h55_file) as ds:
                    a = ds.read(1)
                    if (ds.count != 1 or ds.dtypes[0] != "float32" or ds.crs is None or ds.crs.to_epsg() != 32611
                            or (ds.height, ds.width) != (3730, 3292)
                            or not np.isfinite(a).all() or float(a.min()) < 0 or float(a.max()) > 1):
                        problems.append("H55 TIFF: raster dimensions/CRS/dtype/finite [0,1] check failed")
                    elif int((a > 0).sum()) != h55["format"]["n_nonzero"]:
                        problems.append("H55 TIFF: nonzero count differs from the published summary")
                zpath = h55_file.with_suffix(".zip")
                if not zpath.exists():
                    problems.append("H55 single-TIFF ZIP is missing")
                else:
                    with zipfile.ZipFile(zpath) as z:
                        tiffs = [n for n in z.namelist() if n.lower().endswith((".tif", ".tiff"))]
                        if len(tiffs) != 1 or z.read(tiffs[0]) != h55_file.read_bytes():
                            problems.append("H55 ZIP must contain exactly one TIFF byte-identical to the direct download")
                with urlopen(f"http://127.0.0.1:{port}/downloads/{h55['file']}", timeout=20) as r:
                    if len(r.read()) != h55["bytes"]:
                        problems.append("served H55 TIFF byte count differs from receipt")
                notes.append(f"H55-PROFILE TIFF verified: {h55['bytes']:,} bytes, {h55['uniqueness']['n_priors_checked']} priors, research-only")
        edge_served_path = DATA / "h55_edge_submission.json"
        if edge_served_path.exists():
            edge_served = json.loads(edge_served_path.read_text())
            with urlopen(f"http://127.0.0.1:{port}/downloads/{edge_served['file']}", timeout=20) as r:
                n = len(r.read())
                if n != edge_served["bytes"]:
                    problems.append("served H55-EDGE TIFF byte count differs from receipt")
                else:
                    notes.append(f"H55-EDGE TIFF served byte-identically: {n:,} bytes")

        # R3-H1 is a separate failed-gate research release; it is not the submission.json incumbent.
        r3 = json.loads((DATA / "submission_r3.json").read_text())
        with urlopen(f"http://127.0.0.1:{port}/downloads/{r3['file']}", timeout=20) as r:
            body = r.read()
            if len(body) != r3["bytes"] or hashlib.sha256(body).hexdigest() != r3["sha256"]:
                problems.append("served R3 research TIFF differs from its audited bytes")
            else:
                notes.append(f"research-only R3 TIFF also serves byte-identically: {len(body):,} bytes")
    finally:
        httpd.shutdown()

    # Verify receipt-rendered measurements without conflating the H55 incumbent, H55-PROFILE,
    # and H55-EDGE. The latter is a separate failed-gate archive and must never become global latest.
    current = json.loads((DATA / 'submission.json').read_text()) if (DATA / 'submission.json').exists() else {}
    r2_holdout = DATA / 'holdout_r2.json'
    if r2_holdout.exists():
        h = json.loads(r2_holdout.read_text())
        text = (DOCS / 'validation.html').read_text()
        for arm, value in h['means'].items():
            if f'{value:.6f}' not in text:
                problems.append(f'validation.html: R2 {arm} mean is not rendered from its receipt')
        for page_name in ('index.html', 'executive-summary.html'):
            body = (DOCS / page_name).read_text()
            if 'Do not upload' not in body:
                problems.append(f'{page_name}: missing failed-gate warning')

    edge_path = DATA / 'h55_edge_submission.json'
    edge_hold_path = DATA / 'h55_edge_holdout.json'
    edge_deviation_path = DATA / 'h55_edge_protocol_deviation.json'
    if edge_path.exists():
        import csv
        import hashlib
        import zipfile
        import numpy as np
        import rasterio
        edge = json.loads(edge_path.read_text())
        if not edge_hold_path.exists() or not edge_deviation_path.exists():
            problems.append('H55-EDGE: missing independent holdout or protocol-deviation receipt')
        else:
            edge_hold = json.loads(edge_hold_path.read_text())
            edge_deviation = json.loads(edge_deviation_path.read_text())
            prereg_path = ROOT / 'registry/h55_edge_preregistration.json'
            prereg_sha = hashlib.sha256(prereg_path.read_bytes()).hexdigest() if prereg_path.exists() else None
            if not prereg_sha or prereg_sha != edge.get('preregistration_sha256'):
                problems.append('H55-EDGE: frozen preregistration hash does not match artifact receipt')
            if edge_deviation.get('preregistration_sha256_at_validation') != prereg_sha:
                problems.append('H55-EDGE: protocol-deviation receipt hash mismatch')
            if edge_hold.get('preregistration_sha256') != prereg_sha:
                problems.append('H55-EDGE: holdout receipt hash mismatch')
            if edge.get('approved_for_weekly_slot') is not False or edge.get('official_score') is not None or edge.get('submission_slots_used') != 0:
                problems.append('H55-EDGE: artifact must remain failed-gate, unscored, and zero-slot')
            if edge.get('uniqueness', {}).get('support_novelty_gate_ok') is not False:
                problems.append('H55-EDGE: strict support-novelty failure was not retained')
            if edge_deviation.get('holdout_result_for_implemented_subset', {}).get('gate_passed') is not False:
                problems.append('H55-EDGE: implemented-subset holdout failure was not retained')
            edge_name = edge.get('file') or ''
            edge_file = DOCS / 'downloads' / edge_name
            expected_sha = edge.get('sha256')
            if not edge_file.exists() or hashlib.sha256(edge_file.read_bytes()).hexdigest() != expected_sha:
                problems.append('H55-EDGE: published TIFF is missing or differs from the audited bytes')
            else:
                with rasterio.open(edge_file) as ds:
                    a = ds.read(1)
                    if (ds.count != 1 or ds.dtypes[0] != 'float32' or ds.crs is None or ds.crs.to_epsg() != 32611
                            or (ds.height, ds.width) != (3730, 3292) or not np.isfinite(a).all()
                            or float(a.min()) < 0 or float(a.max()) > 1
                            or int(np.count_nonzero(a)) != int(edge['format']['n_nonzero'])
                            or np.any((a > 0) & (ds.dataset_mask() == 0))):
                        problems.append('H55-EDGE: on-disk raster format/range/footprint check failed')
                zip_path = edge_file.with_suffix('.zip')
                if not zip_path.exists():
                    problems.append('H55-EDGE: single-TIFF ZIP is missing')
                else:
                    with zipfile.ZipFile(zip_path) as archive:
                        if archive.namelist() != [edge_name] or hashlib.sha256(archive.read(edge_name)).hexdigest() != expected_sha:
                            problems.append('H55-EDGE: ZIP must contain exactly one byte-identical TIFF')
            reasoning = edge.get('view_comparison', {}).get('a_only_reasoning', {})
            reasoning_path = DOCS / 'downloads' / reasoning.get('file', '')
            if not reasoning_path.exists() or hashlib.sha256(reasoning_path.read_bytes()).hexdigest() != reasoning.get('sha256'):
                problems.append('H55-EDGE: per-pixel reasoning CSV missing or hash-mismatched')
            elif reasoning_path.exists():
                with reasoning_path.open(newline='') as fh:
                    rows = list(csv.DictReader(fh))
                if len(rows) != reasoning.get('rows') or len(rows) != 816:
                    problems.append('H55-EDGE: reasoning CSV row count differs from its receipt')
            edge_page = (DOCS / 'h55-edge.html').read_text() if (DOCS / 'h55-edge.html').exists() else ''
            for term in ('h55_edge_protocol_deviation.json', 'H55-EDGE', 'do not upload', 'not the current H55 candidate'):
                if term.casefold() not in edge_page.casefold():
                    problems.append(f'H55-EDGE page: missing required disclosure/link text {term!r}')
            main_marker = (ROOT / 'submission/LATEST.txt').read_text().strip() if (ROOT / 'submission/LATEST.txt').exists() else ''
            edge_marker = (ROOT / 'submission/H55_EDGE_LATEST.txt').read_text().strip() if (ROOT / 'submission/H55_EDGE_LATEST.txt').exists() else ''
            if main_marker == edge_name or current.get('file') != main_marker:
                problems.append('H55-EDGE: global incumbent marker/current receipt was changed or conflated')
            if edge_marker != edge_name:
                problems.append('H55-EDGE: experiment-specific marker is missing or points to different bytes')
            for page_name in ('index.html', 'h55.html', 'downloads/index.html'):
                page_text = (DOCS / page_name).read_text()
                if 'h55-edge.html' not in page_text:
                    problems.append(f'{page_name}: missing separate H55-EDGE archive link')
            notes.append(f"H55-EDGE verified as a separate failed-gate archive: {edge['bytes']:,} bytes, {edge_hold['positive_folds']}/4 positive folds; main incumbent unchanged")

    # The latest pointer is the H56 co-training synthetic demonstration. Its download is
    # byte-verified, but neither synthetic holdout numbers nor a local format pass open a slot.
    h56_receipt_path = DATA / 'submission_h56.json'
    if not current or not h56_receipt_path.exists():
        problems.append('H56: current feed receipt or tagged H56 audit receipt is missing')
    else:
        h56_receipt = json.loads(h56_receipt_path.read_text())
        latest = (ROOT / 'submission/LATEST.txt').read_text().strip()
        h56_file = DOCS / 'downloads' / str(current.get('file', ''))
        h56_source = ROOT / 'submission' / str(current.get('file', ''))
        expected_sha = current.get('sha256')
        if current.get('file') != latest or current.get('file') != H56_CURRENT_FILE:
            problems.append('H56: current feed, submission/LATEST.txt, and expected synthetic-demo name disagree')
        if (current.get('approved_for_weekly_slot') is not False
                or current.get('synthetic') is not True
                or current.get('submission_slots_used') != 0
                or (current.get('slot_gate') or {}).get('approved_for_weekly_slot') is not False):
            problems.append('H56: the synthetic demonstration must remain explicitly not approved with zero slots')
        if 'SYNTHETIC' not in str(current.get('artifact_status', '')).upper():
            problems.append('H56: current artifact is missing its synthetic-demo status label')
        if (h56_receipt.get('sha256') != expected_sha
                or h56_receipt.get('bytes') != current.get('bytes')
                or h56_receipt.get('synthetic') is not True):
            problems.append('H56: tagged receipt, current feed hash/size, or synthetic status disagree')
        reasoning_name = Path(str((h56_receipt.get('reasoning') or {}).get('json') or '')).name
        reasoning_source = ROOT / 'evidence' / reasoning_name
        reasoning_public = DATA / reasoning_name
        if (not reasoning_name.startswith('h56_reasoning_') or not reasoning_name.endswith('.json')
                or not reasoning_source.is_file() or not reasoning_public.is_file()):
            problems.append('H56: tagged per-candidate reasoning record is missing from evidence or published data')
        elif reasoning_source.read_bytes() != reasoning_public.read_bytes():
            problems.append('H56: published per-candidate reasoning JSON differs from its evidence source')
        if not expected_sha or not h56_file.is_file() or hashlib.sha256(h56_file.read_bytes()).hexdigest() != expected_sha:
            problems.append('H56: current downloadable TIFF is missing or differs from its audited SHA-256')
        elif h56_file.stat().st_size != current.get('bytes'):
            problems.append('H56: current downloadable TIFF size differs from its receipt')
        if (not h56_source.is_file() or not h56_file.is_file()
                or hashlib.sha256(h56_source.read_bytes()).hexdigest() != expected_sha
                or hashlib.sha256(h56_file.read_bytes()).hexdigest() != expected_sha):
            problems.append('H56: submission/ and docs/downloads/ do not contain the same receipt-verified TIFF')
        fmt = h56_receipt.get('format_gate') or {}
        uni = h56_receipt.get('uniqueness') or {}
        holdout_note = str((h56_receipt.get('holdout') or {}).get('note', '')).lower()
        if not fmt.get('ok') or fmt.get('mass_outside_footprint') != 0 or fmt.get('valid_px') != 5167373:
            problems.append('H56: local format/true-footprint receipt did not pass')
        if not uni.get('canonical_pattern_unique') or not uni.get('research_publication_ok'):
            problems.append('H56: bounded canonical-pattern research check is missing or failed')
        if 'synthetic' not in holdout_note or 'real holdout requires' not in holdout_note:
            problems.append('H56: illustrative synthetic holdout is not distinguished from real-data validation')
        if len(str(current.get('submission_note') or '')) > 200:
            problems.append('H56: identifying note exceeds 200 characters')
        h56_page = (DOCS / 'h56-cotrain.html').read_text() if (DOCS / 'h56-cotrain.html').exists() else ''
        for term in ('RESEARCH-ONLY SYNTHETIC DEMO', 'do not spend a weekly slot',
                     'do not upload until you rerun on real data'):
            if term.casefold() not in h56_page.casefold():
                problems.append(f'H56 co-training page: missing synthetic/no-slot warning {term!r}')
        for page_name in ('index.html', 'executive-summary.html'):
            text = (DOCS / page_name).read_text() if (DOCS / page_name).exists() else ''
            if current.get('file') not in text or 'synthetic' not in text.casefold() or 'not approved' not in text.casefold():
                problems.append(f'{page_name}: current H56 identity/synthetic/no-approval status is missing')
        old_alias = DOCS / 'downloads/h56-candidate.tif'
        old_page = (DOCS / 'h56.html').read_text() if (DOCS / 'h56.html').exists() else ''
        if old_alias.exists() and old_alias.read_bytes() == h56_file.read_bytes():
            problems.append('H56: historical short alias is ambiguously identical to the current co-training demo')
        if 'HISTORICAL H56 CORE-CONTINUATION ARCHIVE' not in old_page:
            problems.append('h56.html: earlier H56 page/short alias is not clearly marked historical')

    # H57 is a distinct, real-data research release; its quality gate failed, so it must never
    # replace the protected synthetic H56 latest pointer or be presented as upload-approved.
    h57_receipt_path = DATA / 'h57_submission.json'
    h57_holdout_path = DATA / 'h57_holdout.json'
    h57_independence_path = DATA / 'h57_independence.json'
    h57_exchange_path = DATA / 'h57_pseudo_exchange.json'
    h57_integrity_path = DATA / 'h57_run_integrity.json'
    if not all(path.is_file() for path in (h57_receipt_path, h57_holdout_path,
                                            h57_independence_path, h57_exchange_path,
                                            h57_integrity_path)):
        problems.append('H57: published artifact, holdout, independence, exchange, or run receipt is missing')
    else:
        import numpy as np
        import rasterio
        import zipfile
        h57 = json.loads(h57_receipt_path.read_text())
        h57_hold = json.loads(h57_holdout_path.read_text())
        h57_ind = json.loads(h57_independence_path.read_text())
        h57_exchange = json.loads(h57_exchange_path.read_text())
        h57_integrity = json.loads(h57_integrity_path.read_text())
        h57_name = str(h57.get('file') or '')
        h57_zip_name = str(h57.get('zip') or '')
        h57_file = DOCS / 'downloads' / h57_name
        h57_source = ROOT / 'submission' / h57_name
        h57_zip = DOCS / 'downloads' / h57_zip_name
        h57_zip_source = ROOT / 'submission' / h57_zip_name
        h57_uni = h57.get('uniqueness') or {}
        h57_fmt = h57.get('format_gate') or {}
        h57_slot = h57_hold.get('slot_gate') or {}
        if (h57.get('safe_to_download_for_research') is not True
                or h57.get('approved_to_submit') is not False
                or h57.get('approved_for_weekly_slot') is not False
                or h57.get('slots_used') != 0
                or h57.get('portal_upload_performed') is not False):
            problems.append('H57: research-download/NOT-approved/zero-slot/zero-upload status is missing or unsafe')
        if (h57.get('candidate_arm') != 'view_B_corrected_fallback'
                or h57.get('candidate_arm_is_cotrain') is not False
                or h57_hold.get('primary', {}).get('arm') != 'view_B_corrected_fallback'):
            problems.append('H57: published fallback is misidentified as co-training or a different model arm')
        if (not h57_fmt.get('ok') or h57_fmt.get('validation_class', '').startswith('organizer')
                or h57_fmt.get('dtype') != 'float32' or h57_fmt.get('bands') != 1
                or h57_fmt.get('crs') != 'EPSG:32611'
                or (h57_fmt.get('height'), h57_fmt.get('width')) != (3730, 3292)
                or h57_fmt.get('n_nonzero') != h57.get('emitted_pixels')
                or h57_fmt.get('nan_pixels') != 0 or h57_fmt.get('infinity_pixels') != 0
                or h57_fmt.get('mass_outside_footprint') != 0):
            problems.append('H57: local TIFF format/range receipt is incomplete or inconsistent')
        if (not h57_uni.get('canonical_pattern_unique')
                or not h57_uni.get('research_publication_ok')
                or h57_uni.get('equals_literal_prior_union') is not False
                or h57_uni.get('n_priors_checked', 0) < 1
                or h57_uni.get('candidate_decoded_sha256') != h57.get('decoded_pixels_sha256')):
            problems.append('H57: bounded decoded-pattern uniqueness or literal prior-union audit failed')
        if (len(str(h57.get('submission_name') or '')) > 200
                or len(str(h57.get('submission_note') or '')) > 200
                or h57.get('submission_name_chars') != len(str(h57.get('submission_name') or ''))
                or h57.get('submission_note_chars') != len(str(h57.get('submission_note') or ''))):
            problems.append('H57: unique name or short note is missing or exceeds the 200-character portal limit')
        if (h57_hold.get('exchange', {}).get('enabled') is not False
                or h57_hold.get('submission_slots_used') != 0
                or h57_hold.get('portal_upload_performed') is not False
                or h57_slot.get('approved_for_weekly_slot') is not False
                or h57_exchange.get('enabled') is not False
                or h57_exchange.get('used_in_primary') is not False
                or h57_exchange.get('folds') != []):
            problems.append('H57: failed exchange/holdout gate must retain no pseudo-labels, no round-1 fit, and zero slots')
        fold1_fpr = (((h57_ind.get('per_fold') or {}).get('1') or {}).get('tests') or {}).get('negative_false_positive_rate') or {}
        if (h57_ind.get('allow_exchange') is not False
                or (h57_ind.get('per_fold') or {}).get('1', {}).get('allow_exchange') is not False
                or fold1_fpr.get('pearson') is not None or fold1_fpr.get('spearman') is not None):
            problems.append('H57: fold-1 constant/undefined negative-FPR errors did not fail the registered independence gate closed')
        comparison = h57_hold.get('comparisons') or {}
        if (h57_hold.get('primary', {}).get('mean_dti') is None
                or comparison.get('historical_best_comparable_mean_dti') is None
                or float(h57_hold['primary']['mean_dti']) >= float(comparison['historical_best_comparable_mean_dti'])
                or h57_slot.get('scientific_holdout_pass') is not False):
            problems.append('H57: failed local holdout must remain explicit and cannot imply slot approval')
        if h57_integrity.get('portal_upload_performed') is not False or h57_integrity.get('submission_slots_used') != 0:
            problems.append('H57: run-integrity receipt must retain no upload and zero slots')
        if h57.get('provenance', {}).get('owner_mirror_not_organizer_authenticated') is not True:
            problems.append('H57: owner-mirror inputs must not be described as organizer-authenticated')

        # Every public copy is checked against the same canonical bytes; uniqueness means decoded
        # predictions differ, not merely that the filename or compression differs.
        expected_sha = str(h57.get('sha256') or '')
        expected_zip_sha = str(h57.get('zip_sha256') or '')
        if (not h57_name.endswith('.tif') or not expected_sha or not h57_source.is_file()
                or not h57_file.is_file()
                or hashlib.sha256(h57_source.read_bytes()).hexdigest() != expected_sha
                or hashlib.sha256(h57_file.read_bytes()).hexdigest() != expected_sha
                or h57_source.read_bytes() != h57_file.read_bytes()
                or h57_file.stat().st_size != h57.get('bytes')):
            problems.append('H57: canonical and public TIFFs are missing or differ from the receipt bytes')
        else:
            try:
                with rasterio.open(h57_file) as ds:
                    a = ds.read(1)
                    decoded_sha = hashlib.sha256(a.astype('<f4').tobytes()).hexdigest()
                    if (ds.count != 1 or ds.dtypes[0] != 'float32' or ds.crs is None
                            or ds.crs.to_epsg() != 32611 or (ds.height, ds.width) != (3730, 3292)
                            or not np.isfinite(a).all() or float(a.min()) < 0 or float(a.max()) > 1
                            or int(np.count_nonzero(a)) != h57.get('emitted_pixels')
                            or decoded_sha != h57.get('decoded_pixels_sha256')):
                        problems.append('H57: re-opened TIFF pixels/CRS/dtype/range/count/hash differ from receipt')
            except Exception as exc:  # noqa: BLE001
                problems.append(f'H57: unable to reopen TIFF for decoded-pattern verification ({exc})')
        if (not expected_zip_sha or not h57_zip_source.is_file() or not h57_zip.is_file()
                or hashlib.sha256(h57_zip_source.read_bytes()).hexdigest() != expected_zip_sha
                or hashlib.sha256(h57_zip.read_bytes()).hexdigest() != expected_zip_sha
                or h57_zip_source.read_bytes() != h57_zip.read_bytes()):
            problems.append('H57: canonical and public single-TIFF ZIPs are missing or differ from their receipt')
        elif h57_file.is_file():
            try:
                with zipfile.ZipFile(h57_zip) as archive:
                    members = archive.namelist()
                    if (archive.testzip() is not None or members != [h57_name]
                            or archive.read(h57_name) != h57_file.read_bytes()):
                        problems.append('H57: ZIP must contain exactly one CRC-valid TIFF byte-identical to the direct download')
            except (OSError, zipfile.BadZipFile, KeyError) as exc:
                problems.append(f'H57: invalid single-TIFF ZIP ({exc})')

        # Published evidence and the short portal identification must be discoverable at the top.
        for published_name, source_path in (
                ('h57_submission.json', next(iter(sorted((ROOT / 'evidence').glob('submission_gems52-h57-*.json'))), None)),
                ('h57_holdout.json', ROOT / 'evidence/h57_holdout.json'),
                ('h57_independence.json', ROOT / 'evidence/h57_independence.json'),
                ('h57_pseudo_exchange.json', ROOT / 'evidence/h57_pseudo_exchange.json'),
                ('h57_prefit_lock.json', ROOT / 'evidence/h57_prefit_lock.json')):
            public_path = DATA / published_name
            if source_path is None or not source_path.is_file() or not public_path.is_file() or source_path.read_bytes() != public_path.read_bytes():
                problems.append(f'H57: published data/{published_name} differs from its evidence source')
        page_text = (DOCS / 'h57.html').read_text() if (DOCS / 'h57.html').is_file() else ''
        guide_text = (DOCS / 'executive-summary.html').read_text() if (DOCS / 'executive-summary.html').is_file() else ''
        home_text = (DOCS / 'index.html').read_text() if (DOCS / 'index.html').is_file() else ''
        downloads_text = (DOCS / 'downloads/index.html').read_text() if (DOCS / 'downloads/index.html').is_file() else ''
        readme_text = (ROOT / 'README.md').read_text()
        for label, text in (('H57 audit', page_text), ('H57 guide', guide_text),
                            ('home', home_text), ('downloads index', downloads_text),
                            ('README', readme_text)):
            if h57_name not in text:
                problems.append(f'H57 {label}: exact research filename/download identity is missing')
            if 'safe to download' not in text.casefold() or 'approved to submit' not in text.casefold():
                problems.append(f'H57 {label}: downloadability and submit approval are not stated separately')
        if ('owner-reported' not in page_text.casefold() or 'participant-level' not in page_text.casefold()
                or 'not independently authenticated' not in page_text.casefold()):
            problems.append('H57 audit: leaderboard attribution/input authentication limits are missing')
        if any(f'H57-{n}' not in page_text for n in range(1, 5)):
            problems.append('H57 audit: four ranked geological hypotheses are not present')
        if home_text.find('<!--H57-BAR-->') < 0 or home_text.find('<!--H57-BAR-->') > home_text.find('<!--H56BAR-->'):
            problems.append('H57: top-of-site H57 download card must precede the historical H56 banner')
        if readme_text.count('<!--H57-STATUS-->') != 1 or readme_text.count('<!--/H57-STATUS-->') != 1:
            problems.append('H57: README status insertion is missing or duplicated')
        if 'Do not upload' not in guide_text:
            problems.append('H57 guide: must explicitly say "Do not upload"')
        # The general site-server pass above has shut its socket down; use a fresh short-lived
        # loopback server here to verify both H57 download endpoints and their content types.
        h57_httpd = ThreadedTCPServer(("127.0.0.1", 0), H)
        h57_port = h57_httpd.server_address[1]
        threading.Thread(target=h57_httpd.serve_forever, daemon=True).start()
        try:
            with urlopen(f'http://127.0.0.1:{h57_port}/downloads/{h57_name}', timeout=20) as r:
                body = r.read()
                if (len(body) != h57.get('bytes') or hashlib.sha256(body).hexdigest() != expected_sha
                        or 'tiff' not in r.headers.get('Content-Type', '').casefold()):
                    problems.append('H57: published TIFF does not serve byte-identically through the local site')
            with urlopen(f'http://127.0.0.1:{h57_port}/downloads/{h57_zip_name}', timeout=20) as r:
                body = r.read()
                if len(body) != h57.get('zip_bytes') or hashlib.sha256(body).hexdigest() != expected_zip_sha:
                    problems.append('H57: published single-TIFF ZIP does not serve byte-identically through the local site')
        finally:
            h57_httpd.shutdown()
            h57_httpd.server_close()
        notes.append(f"H57 research TIFF verified: {h57.get('bytes'):,} bytes, {h57_uni.get('n_priors_checked')} accessible priors, holdout {h57_hold.get('primary', {}).get('mean_dti', float('nan')):.6f}, NOT approved/zero slots")

    # H55 is an archive: bind its corrected A-only promotion prose to the frozen sweep and keep it
    # distinct from the registered block-error-correlation result above.
    h55_receipt_path = ROOT / 'evidence/submission_gems52-h55-btherm-greedy-37654px-20261007T0150Z-zeros.json'
    h55_verification_path = ROOT / 'evidence/h55_verification_20261007T0150Z.json'
    h55_sweep_path = ROOT / 'evidence/h55_sweep_hardcore.json'
    if not h55_receipt_path.exists() or not h55_verification_path.exists() or not h55_sweep_path.exists():
        problems.append('H55 archive: pinned submission, verification, or frozen sweep receipt is missing')
    else:
        h55 = json.loads(h55_receipt_path.read_text())
        h55_verification = json.loads(h55_verification_path.read_text())
        h55_sweep = json.loads(h55_sweep_path.read_text())
        if h55.get('approved_for_weekly_slot') is not True:
            problems.append('H55 archive: historical local PASS receipt changed; do not silently rewrite it')
        if h55.get('file') == current.get('file'):
            problems.append('H55 archive: historical H55 is conflated with the current H56 artifact')
        if h55_verification.get('tag') != '20261007T0150Z' or h55_verification.get('all_ok') is not True:
            problems.append('H55 archive: text-review verification is not bound to the frozen run')
        def h55_row(mode, arm, emitter):
            return next((row for row in (h55_sweep.get(mode, {}).get('summary') or {}).get('ranked', [])
                         if row.get('arm') == arm and row.get('emitter') == emitter), None)
        ah, rh = h55_row('hide', 'A_only', 'hc4|37654'), h55_row('hide', 'random', 'hc|37654')
        at, rt = h55_row('tip', 'A_only', 'hc4|37654'), h55_row('tip', 'random', 'hc|37654')
        if not all((ah, rh, at, rt)):
            problems.append('H55 archive: A-only/matched-random rows are missing from the frozen sweep')
        else:
            if (abs(float(ah['mean_dti']) - 0.02979) > 1e-8
                    or abs(float(rh['mean_dti']) - 0.03948) > 1e-8
                    or abs(float(at['mean_dti']) - 0.02894) > 1e-8
                    or abs(float(rt['mean_dti']) - 0.02477) > 1e-8
                    or ah.get('fold_wins_vs_random') != 1
                    or at.get('fold_wins_vs_random') != 2):
                problems.append('H55 archive: A-only means/fold wins changed from the reviewed result')
        ind = h55_verification.get('independence_summary') or {}
        if (abs(float((ind.get('hide') or {}).get('max_abs_spearman_mean_overprediction', 0)) - 0.7625) > 1e-8
                or abs(float((ind.get('tip') or {}).get('max_abs_spearman_mean_overprediction', 0)) - 0.7107) > 1e-8):
            problems.append('H55 archive: registered block-error-correlation result changed')
        h55_file = DOCS / 'downloads' / str(h55.get('file', ''))
        if (not h55_file.is_file()
                or hashlib.sha256(h55_file.read_bytes()).hexdigest() != h55.get('sha256')):
            problems.append('H55 archive: historical TIFF is missing or differs from its local receipt')
        elif h55_file.stat().st_size != h55.get('bytes'):
            problems.append('H55 archive: TIFF size differs from the historical receipt')
        if h55_file.is_file():
            zip_path = h55_file.with_suffix('.zip')
            if not zip_path.is_file():
                problems.append('H55 archive: historical ZIP is missing')
            else:
                try:
                    with zipfile.ZipFile(zip_path) as archive:
                        members = [name for name in archive.namelist() if name.lower().endswith(('.tif', '.tiff'))]
                        if len(members) != 1 or archive.read(members[0]) != h55_file.read_bytes():
                            problems.append('H55 archive: ZIP must carry one TIFF byte-identical to the audit file')
                except (OSError, zipfile.BadZipFile, KeyError) as exc:
                    problems.append(f'H55 archive: invalid TIFF ZIP ({exc})')
        h55_page = (DOCS / 'h55.html').read_text() if (DOCS / 'h55.html').exists() else ''
        for phrase in ('H55 is historical; not the current artifact', '0.02979 vs 0.03948',
                       '0.02894 vs 0.02477', 'below matched random on <code>hide</code>',
                       'above matched random on <code>tip</code>', 'wins 1/4',
                       'failing the required &ge;3/4 wins on each instrument',
                       'not approved for upload'):
            if phrase.casefold() not in h55_page.casefold():
                problems.append(f'H55 archive page: missing status/correct A-only result {phrase!r}')
        if 'below matched random on both' in h55_page.casefold():
            problems.append('H55 archive page: stale claim says A-only is below random on both instruments')
        home = (DOCS / 'index.html').read_text() if (DOCS / 'index.html').exists() else ''
        if ('H55 historical archive' not in home or '0.02979' not in home or '0.02894' not in home
                or 'H55 local PASS is not H56 approval' not in home):
            problems.append('index.html: H55 home callout is not clearly historical or lacks corrected A-only values')
        review = (DOCS / 'irregularities.html').read_text() if (DOCS / 'irregularities.html').exists() else ''
        for phrase in ('<!--H55-ARCHIVE-REVIEW-->', 'Historical H55 evidence review', 'H55 is superseded',
                       '0.02979', '0.02894', 'above random on tip', 'H55-JUNCTION remains untested',
                       str(current.get('file'))):
            if phrase.casefold() not in review.casefold():
                problems.append(f'irregularities.html: missing H55 archive/current-H56 detail {phrase!r}')
        if 'No radiometric bands in the available stack' in review:
            problems.append('irregularities.html: obsolete H52-era radiometry statement contradicts H55 band-6 audit')
        readme = (ROOT / 'README.md').read_text()
        for phrase in ('H55 main candidate — historical archive', 'A-only promotion comparison',
                       '0.02979 vs matched random 0.03948', '0.02894 vs 0.02477',
                       '1/4 fold wins', 'Maximize P(Win)', 'Own the Outcome',
                       'H55\'s byte-level re-audit of band 6 as GeoDAWN total-count radiometry'):
            if phrase.casefold() not in readme.casefold():
                problems.append(f'README.md: missing current-status/H55 correction/brief content {phrase!r}')
        if 'resolves to none, as `knowledge/04`' in readme:
            problems.append('README.md: original prompt interpretation still incorrectly says band 6 resolves to none')
        latest_page = (DOCS / 'index.html').read_text() if (DOCS / 'index.html').exists() else ''
        if latest_page.find('<!--H56BAR-->') < 0 or latest_page.find('<!--H56BAR-->') > latest_page.find('<!--H55BAR-->'):
            problems.append('index.html: H56 current download must precede historical H55 archive')

    print(f"pages checked: {len(pages)}   data files: {len(list(DATA.glob('*.json')))}")
    for nse in notes:
        print("  note:", nse)
    if problems:
        print(f"\n{len(problems)} PROBLEM(S):")
        for p in problems[:40]:
            print("  ✗", p)
        return 1
    # The closing sentence used to assert "Scientific slot gate remains closed" unconditionally -- a
    # success message stating a condition the script never read, which is the exact failure mode this
    # script exists to catch in other files.  It became actively wrong the moment an artefact shipped
    # with approved_for_weekly_slot=True (IR-52-031).  Read it, or do not print it.
    sub_p = DATA / 'submission.json'
    sub = json.loads(sub_p.read_text()) if sub_p.exists() else {}
    gate = sub.get('approved_for_weekly_slot')
    if gate is True:
        slot = ('Scientific slot gate is OPEN for '
                f"{sub.get('file')} ({sub.get('promotion', 'no promotion reason recorded')})")
    elif gate is False:
        slot = f"Scientific slot gate remains CLOSED for {sub.get('file')}."
    else:
        slot = 'Scientific slot gate: not recorded in docs/data/submission.json (not assumed either way).'
    print('\n✓ local links/JSON/receipt values verified; format and canonical-pattern research release '
          f'verified; byte-identical TIFF serves through the site. {slot}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
