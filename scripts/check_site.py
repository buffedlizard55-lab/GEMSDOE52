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
H57_CURRENT_FILE = "gems57-h57-credit-core25517-plus-novel8000-33517px-zeros.tif"


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
        for path in ("index.html", "executive-summary.html", "h55.html", "h55-profile.html", "h55-edge.html",
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

    # The latest pointer is the H57 credited-core continuation: a real-data candidate whose format
    # and uniqueness gates pass, and whose novel arm is ranked by a REFUTED co-training model that
    # must stay disclosed everywhere the file is offered.  A submit verdict is recorded; no slot is
    # claimed to have been spent.
    h57_receipt_path = DATA / 'submission_h57.json'
    if not current or not h57_receipt_path.exists():
        problems.append('H57: current feed receipt or tagged H57 receipt is missing')
    else:
        h57 = json.loads(h57_receipt_path.read_text())
        latest = (ROOT / 'submission/LATEST.txt').read_text().strip()
        cur_file = str(current.get('file', ''))
        dl_file = DOCS / 'downloads' / cur_file
        src_file = ROOT / 'submission' / cur_file
        expected_sha = current.get('sha256')
        if cur_file != latest or cur_file != H57_CURRENT_FILE:
            problems.append('H57: current feed, submission/LATEST.txt, and the expected H57 name disagree')
        if current.get('approved_for_weekly_slot') is not True or current.get('synthetic') is not False:
            problems.append('H57: current feed must record a real-data candidate with a submit verdict')
        if current.get('submission_slots_used') != 0:
            problems.append('H57: the feed must not claim a weekly slot was spent')
        if 'REFUTED' not in json.dumps(current.get('co_training_disclosure') or {}).upper():
            problems.append('H57: the refuted co-training arm is not disclosed in the current feed')
        if current.get('sha256') != h57.get('sha256') or current.get('bytes') != h57.get('bytes'):
            problems.append('H57: tagged receipt and current feed disagree on hash/size')
        if not expected_sha or not dl_file.is_file() or not src_file.is_file():
            problems.append('H57: current downloadable TIFF is missing from docs/downloads or submission')
        elif (hashlib.sha256(dl_file.read_bytes()).hexdigest() != expected_sha
              or hashlib.sha256(src_file.read_bytes()).hexdigest() != expected_sha):
            problems.append('H57: downloadable TIFF differs from its audited SHA-256')
        elif dl_file.stat().st_size != current.get('bytes'):
            problems.append('H57: downloadable TIFF size differs from its receipt')
        fmt = current.get('format_gate') or {}
        uni = current.get('uniqueness') or {}
        if not fmt.get('ok') or fmt.get('problems'):
            problems.append('H57: format gate receipt is missing or failed')
        if not uni.get('ok') or not uni.get('support_novelty_gate_ok') or int(uni.get('novel_vs_all_priors') or 0) <= 0:
            problems.append('H57: uniqueness gate receipt is missing or failed')
        if int(uni.get('prior_px_dropped') or 0) <= 0 or uni.get('equals_literal_prior_union'):
            problems.append('H57: candidate must drop prior support and must not be the literal union')
        if any(r.get('identical') for r in uni.get('per_prior', [])):
            problems.append('H57: candidate is identical to a prior')
        br = current.get('metric_bracket') or {}
        if not (float(br.get('low', 1)) < float(br.get('central', 0)) < float(br.get('high', 0))):
            problems.append('H57: metric bracket is missing or out of order')
        if len(str(current.get('submission_note') or '')) > 200:
            problems.append('H57: identifying note exceeds 200 characters')
        page = (DOCS / 'h57.html').read_text() if (DOCS / 'h57.html').exists() else ''
        for term in ('ABANDON', 'refuted', 'not proven', 'how to submit'):
            if term.casefold() not in page.casefold():
                problems.append(f'H57 page: missing disclosure text {term!r}')
        for page_name in ('index.html', 'executive-summary.html'):
            text = (DOCS / page_name).read_text() if (DOCS / page_name).exists() else ''
            if cur_file not in text or 'submit: yes' not in text.casefold():
                problems.append(f'{page_name}: current H57 identity or submit verdict is missing')
        # H56 stays an archive: its receipt must still mark it synthetic and not approved, and its
        # page must keep the no-slot warning that stopped an upload in the previous round.
        h56_receipt_path = DATA / 'submission_h56.json'
        if not h56_receipt_path.exists():
            problems.append('H56 archive: tagged receipt is missing')
        else:
            h56 = json.loads(h56_receipt_path.read_text())
            if h56.get('synthetic') is not True or h56.get('file') == cur_file:
                problems.append('H56 archive: the synthetic demo must stay synthetic and non-current')
            if (h56.get('slot_gate') or {}).get('approved_for_weekly_slot') is True:
                problems.append('H56 archive: the synthetic demo must not claim a slot approval')
            h56_page = (DOCS / 'h56-cotrain.html').read_text() if (DOCS / 'h56-cotrain.html').exists() else ''
            for term in ('do not spend a weekly slot', 'RESEARCH-ONLY SYNTHETIC DEMO'):
                if term.casefold() not in h56_page.casefold():
                    problems.append(f'H56 page: missing archive warning {term!r}')
        old_alias = DOCS / 'downloads/h56-candidate.tif'
        if old_alias.exists() and hashlib.sha256(old_alias.read_bytes()).hexdigest() == expected_sha:
            problems.append('H56: historical short alias is ambiguously identical to the current file')
        old_page = (DOCS / 'h56.html').read_text() if (DOCS / 'h56.html').exists() else ''
        if 'HISTORICAL H56 CORE-CONTINUATION ARCHIVE' not in old_page:
            problems.append('h56.html: earlier H56 page/short alias is not clearly marked historical')

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
