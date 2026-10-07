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
            fmt = d.get("format_gate") or d.get("format") or {}
            uni = d.get("uniqueness") or {}
            format_ok = d.get("format_ok", fmt.get("ok"))
            uniqueness_ok = d.get("uniqueness_ok", uni.get("research_publication_ok", uni.get("ok")))
            if fmt and (not fmt.get("ok") or format_ok is False):
                problems.append("submission.json: the staged file does NOT pass the format gate: "
                                + "; ".join(fmt.get("problems", [])[:3]))
            if uni and not uniqueness_ok:
                problems.append('submission.json: canonical pattern uniqueness/literal non-union failed: ' + str(uni.get('relation_to_union')))
            if d.get("approved_for_weekly_slot") is True and (format_ok is not True or uniqueness_ok is not True):
                problems.append('submission.json: local slot approval conflicts with a failed or missing format/uniqueness gate')
            if d.get("submission_note") and len(str(d["submission_note"])) > 200:
                problems.append('submission.json: identifying note exceeds the documented 200-character limit')
            if uni and not uni.get('ok'):
                if d.get('promoted') or d.get('approved_for_weekly_slot') is True or (d.get('validation') or {}).get('approved_for_slot'):
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
                    if f.name == "submission.json":
                        import zipfile
                        import numpy as np
                        import rasterio
                        try:
                            with rasterio.open(dl) as ds:
                                a = ds.read(1)
                                actual_transform = np.asarray(tuple(ds.transform)[:6], dtype=float)
                                actual_bounds = np.asarray(tuple(ds.bounds), dtype=float)
                                expected_transform = np.asarray(fmt.get("transform"), dtype=float)
                                expected_bounds = np.asarray(fmt.get("bounds"), dtype=float)
                                reference_bounds = np.asarray(fmt.get("ref_bounds"), dtype=float)
                                raster_ok = (
                                    ds.count == fmt.get("bands") == 1
                                    and ds.dtypes[0] == fmt.get("dtype") == "float32"
                                    and ds.crs is not None and ds.crs.to_epsg() == 32611
                                    and ds.width == fmt.get("width") and ds.height == fmt.get("height")
                                    and np.isfinite(a).all()
                                    and float(a.min()) >= 0 and float(a.max()) <= 1
                                    and int(np.count_nonzero(a)) == fmt.get("n_nonzero")
                                    and expected_transform.shape == (6,)
                                    and expected_bounds.shape == (4,)
                                    and reference_bounds.shape == (4,)
                                    and np.allclose(actual_transform, expected_transform, rtol=0, atol=1e-9)
                                    and np.allclose(actual_bounds, expected_bounds, rtol=0, atol=1e-6)
                                    and np.allclose(actual_bounds, reference_bounds, rtol=0, atol=1e-6)
                                )
                            if not raster_ok:
                                problems.append("submission.json: on-disk H55 band/dtype/CRS/shape/range/transform/bounds checks failed")
                            zip_path = dl.with_suffix(".zip")
                            if not zip_path.exists():
                                problems.append("submission.json: single-TIFF ZIP is missing")
                            else:
                                with zipfile.ZipFile(zip_path) as archive:
                                    tiffs = [name for name in archive.namelist()
                                             if name.lower().endswith((".tif", ".tiff"))]
                                    if len(tiffs) != 1 or hashlib.sha256(archive.read(tiffs[0])).hexdigest() != d.get("sha256"):
                                        problems.append("submission.json: ZIP must contain exactly one byte-identical TIFF")
                        except Exception as error:  # noqa: BLE001
                            problems.append(f"submission.json: on-disk GeoTIFF/ZIP verification failed ({error})")
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
            served = r.read()
            n = len(served)
            ctype = r.headers.get("Content-Type", "")
            served_sha = hashlib.sha256(served).hexdigest()
            if n != sub["bytes"]:
                problems.append(f"served {sub['download']}: {n} bytes != {sub['bytes']} in the receipt")
            elif served_sha != sub.get("sha256"):
                problems.append(f"served {sub['download']}: SHA-256 differs from the H55 receipt")
            else:
                notes.append(f"the .tif serves byte-identically through the site: {n:,} bytes, content-type {ctype}")

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

    # The executive guide describes the current H55 receipt. Do not require the historical R2/R3
    # "Do not upload" sentence there: those are separate artifacts with separate gate statuses.
    if current:
        guide = (DOCS / 'executive-summary.html').read_text() if (DOCS / 'executive-summary.html').exists() else ''
        for value, label in ((current.get('file'), 'filename'),
                             (current.get('submission_name'), 'submission name'),
                             (current.get('submission_note'), 'portal note'),
                             (current.get('sha256'), 'SHA-256')):
            if value and str(value) not in guide:
                problems.append(f'executive-summary.html: current H55 {label} is not rendered from submission.json')
        if current.get('approved_for_weekly_slot') is True:
            for phrase in ('Current H55 artifact', 'Local scientific slot gate: PASS',
                           'not organizer approval', 'not a public-score forecast',
                           'No organizer submission receipt or official score is recorded'):
                if phrase.casefold() not in guide.casefold():
                    problems.append(f'executive-summary.html: missing current H55 status disclosure {phrase!r}')
            if 'R3-H1 submission guide · research-only' in guide:
                problems.append('executive-summary.html: R3 research-only guide was rendered in place of current H55 status')
        elif current.get('approved_for_weekly_slot') is False:
            if 'research only' not in guide.casefold() or 'do not upload' not in guide.casefold():
                problems.append('executive-summary.html: current H55 failed-gate status is not explicit')
        review_page = (DOCS / 'irregularities.html').read_text() if (DOCS / 'irregularities.html').exists() else ''
        for phrase in ('Current H55 status', 'band 6 is measured as GeoDAWN total-count radiometry',
                       '0.02979', '0.02894', 'H55-JUNCTION remains untested'):
            if phrase.casefold() not in review_page.casefold():
                problems.append(f'irregularities.html: missing current H55 review detail {phrase!r}')
        if 'No radiometric bands in the available stack' in review_page:
            problems.append('irregularities.html: stale H52-era radiometry statement contradicts H55')

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
    print('\n✓ local links/JSON/receipt values verified; current artifact format and bounded prior-comparison '
          f'gates verified; byte-identical TIFF serves through the site. {slot}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
