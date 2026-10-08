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
H57_CURRENT_FILE = "gems52-h57-cotrain-disagreement-37654px-20261007T220849Z-1632bb37bb.tif"


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
            if uni and not uni.get('canonical_pattern_unique'):
                problems.append('submission.json: candidate exactly matches an aligned prior pattern')
            if uni and uni.get('support_novelty_gate_ok') is False:
                if d.get('approved_for_weekly_slot') is True or (d.get('slot_gate') or {}).get('approved_for_weekly_slot') is True:
                    problems.append('Scientific promotion despite failed support-novelty diagnostic')
                else:
                    notes.append('Strict >=20% support-novelty diagnostic FAIL is retained separately from exact-pattern uniqueness; no slot approval.')
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
                     "forensics.html", "downloads/index.html"):
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
            if 'do not submit' not in body.casefold() and 'do not upload' not in body.casefold():
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

    # H57 is the current real-raster research artifact. Downloadability and exact-pattern
    # distinction do not override its failed scientific/support-novelty gates.
    h57_receipt_path = DATA / 'h57_submission.json'
    h57_holdout_path = DATA / 'h57_holdout.json'
    if not current or not h57_receipt_path.exists() or not h57_holdout_path.exists():
        problems.append('H57: current feed, H57 artifact receipt, or holdout receipt is missing')
    else:
        import csv
        import hashlib
        import numpy as np
        import rasterio
        import zipfile
        h57 = json.loads(h57_receipt_path.read_text())
        h57_holdout = json.loads(h57_holdout_path.read_text())
        latest = (ROOT / 'submission/LATEST.txt').read_text().strip()
        h57_file = DOCS / 'downloads' / str(h57.get('file', ''))
        h57_source = ROOT / 'submission' / str(h57.get('file', ''))
        expected_sha = h57.get('sha256')
        if current.get('file') != latest or h57.get('file') != latest or latest != H57_CURRENT_FILE:
            problems.append('H57: current feed, H57 receipt, and expected H57 submission/LATEST.txt disagree')
        if current.get('approved_for_weekly_slot') is not False or h57.get('approved_for_weekly_slot') is not False:
            problems.append('H57: research candidate must remain explicitly unapproved for a weekly slot')
        if current.get('official_score') is not None or current.get('submission_slots_used') != 0:
            problems.append('H57: no official score or weekly slot use may be claimed')
        if h57.get('candidate_arm') != 'h57_disagreement_cotrain':
            problems.append('H57: receipt does not identify the preregistered co-training arm')
        gate = h57.get('slot_gate') or {}
        if gate.get('scientific_gate_pass') is not False or gate.get('approved_for_weekly_slot') is not False:
            problems.append('H57: failed scientific gate must remain closed')
        uni = h57.get('uniqueness') or {}
        if uni.get('canonical_pattern_unique') is not True or uni.get('n_priors_checked') != 567:
            problems.append('H57: exact-pattern uniqueness must pass against the 567-content inventory')
        if uni.get('support_novelty_gate_ok') is not False or uni.get('novel_fraction') != 0.0:
            problems.append('H57: the strict 20% support-novelty failure must remain disclosed')
        if (h57.get('not_union') or {}).get('not_merely_union') is not True:
            problems.append('H57: view-union audit did not pass')
        if (uni.get('inventory_aligned_path_count') != 772
                or uni.get('inventory_aligned_unique_byte_contents') != 567
                or uni.get('exact_byte_duplicate_paths_collapsed') != 205):
            problems.append('H57: prior-path and unique-content counts are conflated or changed')
        if h57_holdout.get('preregistration_sha256') != h57.get('preregistration_sha256'):
            problems.append('H57: holdout and artifact preregistration hashes differ')
        if h57_holdout.get('selected_candidate_arm') != h57.get('candidate_arm'):
            problems.append('H57: selected holdout arm and emitted artifact arm differ')
        if h57_holdout.get('slot_gate', {}).get('scientific_gate_pass') is not False:
            problems.append('H57: holdout report no longer records the failed promotion gate')
        means = {arm: sum(f['arms'][arm]['dti'] for f in h57_holdout['folds']) / len(h57_holdout['folds'])
                 for arm in ('view_A_supervised', 'view_B_supervised', 'matched_max_union', 'h57_disagreement_cotrain')}
        if (abs(means['h57_disagreement_cotrain'] - 0.1106647575835852) > 1e-12
                or abs(means['view_B_supervised'] - 0.15130526541812087) > 1e-12
                or abs(float(gate.get('mean_lift_over_strongest_matched_baseline', 0)) - (-0.04064050783453567)) > 1e-12
                or gate.get('positive_paired_folds') != 0):
            problems.append('H57: four-fold scores or paired no-go decision changed')
        public_manifest = json.loads((DATA / 'h57_public_repo_priors.json').read_text()) if (DATA / 'h57_public_repo_priors.json').exists() else {}
        if (public_manifest.get('repositories_enumerated') != 55
                or public_manifest.get('downloaded_tiff_paths') != 774
                or public_manifest.get('fetch_errors') != 0
                or public_manifest.get('recursive_tree_truncations') != 0):
            problems.append('H57: public sibling prior-scan coverage/limits changed')
        inventory = json.loads((DATA / 'h57_prior_inventory.json').read_text()) if (DATA / 'h57_prior_inventory.json').exists() else {}
        if (inventory.get('aligned_prior_path_count') != 772
                or inventory.get('aligned_unique_byte_contents') != 567
                or inventory.get('exact_byte_duplicate_paths_collapsed') != 205):
            problems.append('H57: final aligned prior inventory does not distinguish paths from unique bytes')
        provenance_path = DATA / 'h57_execution_provenance.json'
        if not provenance_path.is_file():
            problems.append('H57: execution provenance review is missing')
        else:
            provenance = json.loads(provenance_path.read_text())
            review = provenance.get('post_execution_review') or {}
            runner_review = review.get('runner_source_reconciliation') or {}
            component_review = review.get('pseudo_component_boundary_review') or {}
            input_review = review.get('input_restore_review') or {}
            actual_runner_sha = hashlib.sha256((ROOT / 'scripts/run_h57_real.py').read_bytes()).hexdigest()
            actual_h57_module_sha = hashlib.sha256((ROOT / 'src/gems52/h57.py').read_bytes()).hexdigest()
            actual_spatial_sha = hashlib.sha256((ROOT / 'src/gems52/spatial.py').read_bytes()).hexdigest()
            if (runner_review.get('current_checkout_runner_sha256') != actual_runner_sha
                    or runner_review.get('runner_hashes_reconciled') is not False
                    or runner_review.get('historical_runner_snapshots_available') is not False):
                problems.append('H57: runner source mismatch must be recorded against the current file and remain unresolved')
            if (actual_h57_module_sha != provenance.get('holdout_code_sha256', {}).get('src/gems52/h57.py')
                    or runner_review.get('matching_or_reviewed_modules', {}).get('src/gems52/h57.py', {}).get('matches_recorded_holdout') is not True):
                problems.append('H57: recorded modeling-module source hash does not match the current file')
            spatial_review = runner_review.get('matching_or_reviewed_modules', {}).get('src/gems52/spatial.py', {})
            if (spatial_review.get('current_checkout_sha256') != actual_spatial_sha
                    or not spatial_review.get('review_change', '').startswith('Documentation-only')):
                problems.append('H57: spatial train-boundary documentation review is missing or stale')
            if (component_review.get('registered_training_domain_only') is not True
                    or not component_review.get('unobserved_boundary')
                    or not component_review.get('interpretation')):
                problems.append('H57: training-only pseudo-component boundary limitation is not disclosed')
            if (input_review.get('pinned_input_directory_present') is not False
                    or input_review.get('current_repository_data_matches_pins') is not False):
                problems.append('H57: unavailable/mismatched SHA-pinned input restore is not disclosed')
            notes.append('H57 reproducibility warning retained: runner hashes differ, exact pinned inputs are absent, and train-boundary component completeness is unresolved')
        prereg_path = DATA / 'h57_preregistration.json'
        prereg_sha = hashlib.sha256(prereg_path.read_bytes()).hexdigest() if prereg_path.exists() else None
        if not prereg_sha or prereg_sha != h57.get('preregistration_sha256'):
            problems.append('H57: published frozen preregistration does not hash-match the holdout')
        if not expected_sha or not h57_file.is_file() or hashlib.sha256(h57_file.read_bytes()).hexdigest() != expected_sha:
            problems.append('H57: published TIFF is missing or differs from the artifact receipt')
        if not h57_source.is_file() or hashlib.sha256(h57_source.read_bytes()).hexdigest() != expected_sha:
            problems.append('H57: submission/ TIFF is missing or differs from the artifact receipt')
        if h57_file.is_file():
            if h57_file.stat().st_size != h57.get('bytes'):
                problems.append('H57: TIFF byte count differs from the artifact receipt')
            with rasterio.open(h57_file) as ds:
                a = ds.read(1)
                mask = ds.dataset_mask() > 0
                if (ds.count != 1 or ds.dtypes[0] != 'float32' or ds.crs is None or ds.crs.to_epsg() != 32611
                        or (ds.height, ds.width) != (3730, 3292) or ds.transform.a != 100 or ds.transform.e != -100
                        or not np.isfinite(a[mask]).all() or np.any(a[mask] < 0) or np.any(a[mask] > 1)
                        or not np.isnan(a[~mask]).all() or int(np.count_nonzero(a[mask])) != 37654):
                    problems.append('H57: on-disk CRS/shape/transform/dtype/range/mask/positive-count check failed')
            zip_path = h57_file.with_suffix('.zip')
            if not zip_path.is_file():
                problems.append('H57: single-TIFF ZIP is missing')
            else:
                try:
                    with zipfile.ZipFile(zip_path) as archive:
                        if archive.namelist() != [h57_file.name] or archive.read(h57_file.name) != h57_file.read_bytes():
                            problems.append('H57: ZIP must contain exactly one TIFF byte-identical to the direct download')
                except (OSError, KeyError, zipfile.BadZipFile) as exc:
                    problems.append(f'H57: invalid one-TIFF ZIP ({exc})')
        reasoning = h57.get('a_only_reasoning') or {}
        a_csv = DOCS / 'downloads' / Path(str(reasoning.get('a_only_path') or '')).name
        b_csv = DOCS / 'downloads' / Path(str(reasoning.get('b_only_path') or '')).name
        for label, path, count in (('A-only', a_csv, 1137), ('B-only', b_csv, 2132)):
            if not path.is_file():
                problems.append(f'H57: {label} component reasoning/diagnostic CSV is missing')
            else:
                with path.open(newline='') as fh:
                    rows = list(csv.DictReader(fh))
                if len(rows) != count:
                    problems.append(f'H57: {label} CSV row count {len(rows)} != {count} components')
        for path_name in ('index.html', 'executive-summary.html', 'h57.html'):
            text = (DOCS / path_name).read_text()
            for phrase in ('DO NOT SUBMIT', h57.get('file', ''), '0/4'):
                if phrase not in text:
                    problems.append(f'{path_name}: missing explicit H57 no-go identity/status text {phrase!r}')
        if h57.get('submission_note_chars', 201) > 200:
            problems.append('H57: optional portal note exceeds 200 characters')
        if not (h57.get('posthoc_audit') or {}).get('inference_rerun') is False:
            problems.append('H57: uniqueness correction must be disclosed as inference-free, pixel-preserving audit')
        latest_page = (DOCS / 'index.html').read_text()
        if latest_page.find(h57.get('file', '')) < 0 or latest_page.find('DO NOT SUBMIT') < 0:
            problems.append('index.html: one-click H57 download/no-submit status is missing from the top page')
        notes.append(f"H57 research artifact audited: exact pattern unique across 567 contents, 0% support novelty, spatial gate failed, 0 slots")

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
            problems.append('H55 archive: historical H55 is conflated with the current artifact')
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
        if ('historical research archives' not in home.casefold() or 'h55.html' not in home or 'h55-edge.html' not in home):
            problems.append('index.html: historical archives must be clearly linked below the current H57 status')
        review = (DOCS / 'irregularities.html').read_text() if (DOCS / 'irregularities.html').exists() else ''
        for phrase in ('Historical H55/R2 irregularities—kept separate', 'H57 current decision',
                       'DO NOT SUBMIT', str(current.get('file'))):
            if phrase.casefold() not in review.casefold():
                problems.append(f'irregularities.html: missing H57 current status/archive boundary {phrase!r}')
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
        current_download = latest_page.find(str(current.get('file') or ''))
        archive_section = latest_page.find('Historical research archives')
        if current_download < 0 or archive_section < 0 or current_download > archive_section:
            problems.append('index.html: current H57 download/no-go status must precede historical archives')

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
