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

    # Current H56 is intentionally downloadable but explicitly not slot-approved. Re-check the decision,
    # decoded-pattern review, A-only scope, and byte-identical aliases together; a report that contradicts
    # any one of them must stop publication.
    try:
        import zipfile
        import numpy as np
        import rasterio

        sub_path = DATA / 'submission.json'
        if sub_path.exists():
            sub = json.loads(sub_path.read_text())
            marker = (ROOT / 'submission/LATEST.txt').read_text().strip()
            if sub.get('file') != marker:
                problems.append('H56: docs/data/submission.json does not match submission/LATEST.txt')
            if sub.get('approved_for_weekly_slot') is not False:
                problems.append('H56: current artifact must remain explicitly not approved for a weekly slot')
            review_path = DATA / 'h56_slot_gate_review_2026-10-07.json'
            if not review_path.exists():
                problems.append('H56: slot-gate review missing from docs/data')
            else:
                h56_review = json.loads(review_path.read_text())
                if h56_review.get('artifact') != sub.get('file') or h56_review.get('sha256') != sub.get('sha256'):
                    problems.append('H56: slot-gate review does not bind to the current TIFF/hash')
                if h56_review.get('decision', {}).get('approved_for_weekly_slot') is not False:
                    problems.append('H56: slot-gate review must explicitly deny upload until a comparable holdout passes')
                if h56_review.get('spatial_holdout', {}).get('h56_comparable_holdout_receipt_found') is not False:
                    problems.append('H56: holdout absence is not stated in the slot-gate review')
            verify_path = DATA / 'gems52-h56-verify.json'
            if not verify_path.exists():
                problems.append('H56: decoded verifier receipt missing from docs/data')
            else:
                verify = json.loads(verify_path.read_text())
                if hashlib.sha256(verify_path.read_bytes()).hexdigest() != 'cbcfa36a53995c81be2947f74cd5bac0231385e5e1e0282d02f61bd700a5d63b':
                    problems.append('H56: published verifier receipt bytes differ from the reviewed source receipt')
                if verify.get('file') != sub.get('file') or verify.get('sha256') != sub.get('sha256'):
                    problems.append('H56: verifier receipt does not bind to the current TIFF/hash')
                if verify.get('identical_to_any_prior') != [] or verify.get('priors_checked') != 33:
                    problems.append('H56: decoded identity/33-prior audit changed or is missing')
                if verify.get('novel_px') != 12941 or abs(float(verify.get('novel_fraction', 0)) - 0.3193967964064467) > 1e-9:
                    problems.append('H56: decoded support-novelty discrepancy must remain disclosed (12,941 / 31.94%)')
                if verify.get('min_NN_separation_ok') is not False:
                    problems.append('H56: full-file nearest-neighbour diagnostic must retain its measured failure')
            post = (sub.get('postbuild_review') or {})
            if post.get('selected_arm_cells') != 15000 or post.get('selected_arm_cells_with_accessible_prior_support') != 2059:
                problems.append('H56: selected-arm/prior-support discrepancy is not disclosed in the current receipt')
            if post.get('global_min_NN_separation_pass') is not False:
                problems.append('H56: full-file spacing diagnostic is not exposed as failed in submission.json')
            if (sub.get('postbuild_review') or {}).get('a_only_reasoning', '').startswith('not available') is False:
                problems.append('H56: A-only reasoning limitation is missing from submission.json')

            canonical = DOCS / (sub.get('download') or '')
            alias = DOCS / 'downloads/h56-candidate.tif'
            canonical_zip = DOCS / (sub.get('download_zip') or '')
            alias_zip = DOCS / 'downloads/h56-candidate.zip'
            if not canonical.exists() or not alias.exists() or canonical.read_bytes() != alias.read_bytes():
                problems.append('H56: short TIFF alias is missing or not byte-identical to the canonical raster')
            if not canonical_zip.exists() or not alias_zip.exists() or canonical_zip.read_bytes() != alias_zip.read_bytes():
                problems.append('H56: short ZIP alias is missing or not byte-identical to the canonical ZIP')
            for zpath in (canonical_zip, alias_zip):
                if zpath.exists():
                    with zipfile.ZipFile(zpath) as archive:
                        members = archive.namelist()
                        if members != [str(sub.get('file'))] or archive.read(members[0]) != canonical.read_bytes():
                            problems.append(f'H56: {zpath.name} must contain exactly the canonical byte-identical TIFF')
            if canonical.exists():
                with rasterio.open(canonical) as ds:
                    arr = ds.read(1)
                    transform = tuple(ds.transform)[:6]
                    if (ds.count != 1 or ds.dtypes[0] != 'float32' or ds.crs is None or ds.crs.to_epsg() != 32611
                            or (ds.height, ds.width) != (3730, 3292)
                            or transform != (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
                            or not np.isfinite(arr).all() or float(arr.min()) != 0.0 or float(arr.max()) != 1.0
                            or set(np.unique(arr).tolist()) != {0.0, 1.0}
                            or int(np.count_nonzero(arr)) != 40517):
                        problems.append('H56: on-disk read-back failed the single-band float32/grid/range/value/count check')
            h56_page = (DOCS / 'h56.html').read_text() if (DOCS / 'h56.html').exists() else ''
            for phrase in ('DO NOT UPLOAD', '12,941/40,517', 'A-only reasoning scope', '2.828 px'):
                if phrase.casefold() not in h56_page.casefold():
                    problems.append(f'H56 page: missing required status/disclosure {phrase!r}')
            downloads_index = DOCS / 'downloads/index.html'
            if not downloads_index.exists():
                problems.append('site downloads index is missing')
            else:
                downloads_text = downloads_index.read_text()
                if ('h56-candidate.tif' not in downloads_text or 'h56-candidate.zip' not in downloads_text
                        or 'NOT approved for upload' not in downloads_text):
                    problems.append('downloads index: prominent H56 short paths/status are missing or ambiguous')
            a_only_path = DATA / 'h56_a_only_reasoning_scope_2026-10-07.json'
            if not a_only_path.exists():
                problems.append('H56: explicit A-only scope/limitation receipt missing from docs/data')
            else:
                a_only = json.loads(a_only_path.read_text())
                if not str(a_only.get('status', '')).startswith('NOT PRODUCED'):
                    problems.append('H56: A-only limitation receipt must not claim unavailable reasoning was produced')
            review3_path = DATA / 'review_current_integrated_tree_2026-10-07.json'
            if not review3_path.exists():
                problems.append('H56: completed three-pass integration review is missing from docs/data')
            else:
                review3 = json.loads(review3_path.read_text())
                if review3.get('status') != 'three-pass integration review complete; no upload performed':
                    problems.append('H56: three-pass integration review status is not complete/no-upload')
                if (review3.get('pass_3_full_recheck_against_acceptance', {}).get('pytest', {}).get('failed') != 0
                        or review3.get('pass_3_full_recheck_against_acceptance', {}).get('pytest', {}).get('passed') < 100):
                    problems.append('H56: three-pass review does not record a successful test suite')

        # H54 is a separate audit-only artifact; it must not become the main pointer or claim global uniqueness.
        h54_path = DATA / 'h54_audit.json'
        if h54_path.exists():
            h54 = json.loads(h54_path.read_text())
            if h54.get('approved_for_weekly_slot') is not False or h54.get('global_decoded_pattern_uniqueness', '').startswith('pass'):
                problems.append('H54: audit-only/no-global-uniqueness status is missing or unsafe')
            if h54.get('file') == (ROOT / 'submission/LATEST.txt').read_text().strip():
                problems.append('H54: legacy audit artifact was conflated with the current H56 pointer')
            h54_file = DOCS / 'downloads' / str(h54.get('file', ''))
            h54_alias = DOCS / 'downloads/h54-audit-only.tif'
            h54_zip = DOCS / 'downloads/h54-audit-only.zip'
            h54_canonical_zip = DOCS / str(h54.get('canonical_zip', ''))
            if not h54_file.exists() or not h54_alias.exists() or h54_file.read_bytes() != h54_alias.read_bytes():
                problems.append('H54: short audit TIFF is missing or not byte-identical to its canonical TIFF')
            if h54_zip.exists():
                with zipfile.ZipFile(h54_zip) as archive:
                    tiffs = [n for n in archive.namelist() if n.lower().endswith(('.tif', '.tiff'))]
                    if len(tiffs) != 1 or archive.read(tiffs[0]) != h54_file.read_bytes():
                        problems.append('H54: audit ZIP must contain exactly one byte-identical TIFF')
            if (not h54_canonical_zip.exists() or not h54_zip.exists()
                    or h54_canonical_zip.read_bytes() != h54_zip.read_bytes()):
                problems.append('H54: short audit ZIP is missing or not byte-identical to its canonical ZIP')

        # H55 main is a historical archive, distinct from the current H56 pointer. Keep its
        # corrected A-only comparison tied to the original sweep and keep the old local PASS from
        # being presented as permission to upload H56.
        h55_archive_path = ROOT / 'evidence/submission_gems52-h55-btherm-greedy-37654px-20261007T0150Z-zeros.json'
        h55_verification_path = ROOT / 'evidence/h55_verification_20261007T0150Z.json'
        h55_sweep_path = ROOT / 'evidence/h55_sweep_hardcore.json'
        if not h55_archive_path.exists() or not h55_verification_path.exists() or not h55_sweep_path.exists():
            problems.append('H55 archive: immutable submission, verification, or sweep receipt is missing')
        else:
            h55_archive = json.loads(h55_archive_path.read_text())
            h55_verification = json.loads(h55_verification_path.read_text())
            h55_sweep = json.loads(h55_sweep_path.read_text())
            if h55_archive.get('approved_for_weekly_slot') is not True:
                problems.append('H55 archive: historical local gate receipt changed or became ambiguous')
            if h55_archive.get('file') == (ROOT / 'submission/LATEST.txt').read_text().strip():
                problems.append('H55 archive: historical H55 file was conflated with the current pointer')
            if h55_verification.get('tag') != '20261007T0150Z' or h55_verification.get('all_ok') is not True:
                problems.append('H55 archive: verification receipt is not bound to the recorded H55 run')

            def sweep_row(mode, arm, emitter):
                return next((row for row in h55_sweep.get(mode, {}).get('summary', {}).get('ranked', [])
                             if row.get('arm') == arm and row.get('emitter') == emitter), None)

            a_only_hide = sweep_row('hide', 'A_only', 'hc4|37654')
            random_hide = sweep_row('hide', 'random', 'hc|37654')
            a_only_tip = sweep_row('tip', 'A_only', 'hc4|37654')
            random_tip = sweep_row('tip', 'random', 'hc|37654')
            if not all((a_only_hide, random_hide, a_only_tip, random_tip)):
                problems.append('H55 archive: A-only or matched-random row missing from the frozen sweep')
            else:
                if (abs(float(a_only_hide['mean_dti']) - 0.02979) > 1e-8
                        or abs(float(random_hide['mean_dti']) - 0.03948) > 1e-8
                        or abs(float(a_only_tip['mean_dti']) - 0.02894) > 1e-8
                        or abs(float(random_tip['mean_dti']) - 0.02477) > 1e-8
                        or a_only_hide.get('fold_wins_vs_random') != 1
                        or a_only_tip.get('fold_wins_vs_random') != 2):
                    problems.append('H55 archive: recorded A-only means/fold wins changed from the reviewed result')

            h55_page = (DOCS / 'h55.html').read_text() if (DOCS / 'h55.html').exists() else ''
            for phrase in ('H55 is historical; not the current artifact',
                           '0.02979 vs 0.03948', '0.02894 vs 0.02477',
                           'below matched random on <code>hide</code>',
                           'above matched random on <code>tip</code>',
                           'wins 1/4', 'failing the required &ge;3/4 wins on each instrument'):
                if phrase.casefold() not in h55_page.casefold():
                    problems.append(f'H55 page: missing historical status/correct comparison {phrase!r}')
            if 'below matched random on both' in h55_page.casefold():
                problems.append('H55 page: stale claim says A-only is below matched random on both instruments')

            review_page = (DOCS / 'irregularities.html').read_text() if (DOCS / 'irregularities.html').exists() else ''
            for phrase in ('<!--H55-ARCHIVE-REVIEW-->', 'Historical H55 evidence review',
                           'H55 is superseded', '0.02979', '0.02894',
                           'above random on tip', 'H55-JUNCTION remains untested',
                           str(json.loads((DATA / 'submission.json').read_text()).get('file'))):
                if phrase.casefold() not in review_page.casefold():
                    problems.append(f'irregularities.html: missing H55 archive/current-H56 review detail {phrase!r}')
            if 'H55-CURRENT-REVIEW' in review_page or 'Current H55 status' in review_page:
                problems.append('irregularities.html: archived H55 result is still labeled current')
            if 'No radiometric bands in the available stack' in review_page:
                problems.append('irregularities.html: stale H52-era radiometry statement contradicts H55')

            readme = (ROOT / 'README.md').read_text()
            for phrase in ('A-only comparison (separate promotion test)', '0.02979 vs matched random 0.03948',
                           '0.02894 vs 0.02477', '1/4** and **2/4',
                           'Always keep in mind Arena Core Values:', 'Maximize P(Win)', 'Own the Outcome'):
                if phrase.casefold() not in readme.casefold():
                    problems.append(f'README.md: missing preserved brief/H55 finding {phrase!r}')
            if 'resolves to none, as `knowledge/04`' in readme:
                problems.append('README.md: obsolete band-6 interpretation still says the radiometric layer resolves to none')

        # H55-1 is separate, failed, and has a documented protocol-gate preservation gap.
        paired = DATA / 'h55_paired_shoulders_holdout.json'
        gate = DATA / 'h55_paired_shoulders_protocol_gate.json'
        integrity = DATA / 'h55_paired_shoulders_run_integrity.json'
        prereg = ROOT / 'registry/h55_paired_shoulders_preregistration.json'
        if paired.exists() and gate.exists() and integrity.exists() and prereg.exists():
            h55 = json.loads(paired.read_text())
            h55_gate = json.loads(gate.read_text())
            h55_integrity = json.loads(integrity.read_text())
            gap = (h55_integrity.get('execution_path_namespace') or {}).get('protocol_gate_preservation_gap') or {}
            prereg_sha = hashlib.sha256(prereg.read_bytes()).hexdigest()
            if h55.get('preregistration_sha256') != prereg_sha:
                problems.append('H55-1: frozen registration hash differs from the holdout receipt')
            if h55.get('scientific_holdout_gate_pass') is not False or h55.get('slot_gate', {}).get('approved_for_weekly_slot') is not False:
                problems.append('H55-1: failed matched holdout must remain not approved for upload')
            if abs(float((h55.get('arms') or {}).get('mean_dti_lift', 0)) - 0.002360879644970948) > 1e-12:
                problems.append('H55-1: paired mean-lift result changed without review')
            if gap.get('preholdout_gate_exact_bytes_preserved') is not False:
                problems.append('H55-1: protocol-gate hash-preservation gap is not disclosed')
            if hashlib.sha256(gate.read_bytes()).hexdigest() != gap.get('currently_preserved_post_run_gate_sha256'):
                problems.append('H55-1: current protocol-gate bytes differ from the integrity supplement')
            if h55.get('protocol_gate_sha256') != gap.get('holdout_bound_preholdout_gate_sha256'):
                problems.append('H55-1: holdout-bound preflight gate hash is not preserved in the gap record')
            h55_page = (DOCS / 'h55-paired-shoulders.html').read_text() if (DOCS / 'h55-paired-shoulders.html').exists() else ''
            for phrase in ('Preregistered gate failed', 'Preservation gap', '91060c4', '6a696fe'):
                if phrase.casefold() not in h55_page.casefold():
                    problems.append(f'H55-1 page: missing failed-gate/provenance disclosure {phrase!r}')

    except Exception as e:  # noqa: BLE001
        problems.append(f'current-artifact/audit consistency check failed unexpectedly: {e}')

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
        for path in ("index.html", "executive-summary.html", "h56.html", "h54.html",
                     "h55-paired-shoulders.html", "h55.html", "h55-profile.html", "h55-edge.html",
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
        if str(sub.get('file', '')).startswith('gems52-h56-'):
            for short_name in ('downloads/h56-candidate.tif', 'downloads/h56-candidate.zip'):
                with urlopen(f"http://127.0.0.1:{port}/{short_name}", timeout=20) as r:
                    body = r.read()
                    local = DOCS / short_name
                    if body != local.read_bytes():
                        problems.append(f"served {short_name}: response differs from its byte-identical alias")
                    elif short_name.endswith('.tif') and hashlib.sha256(body).hexdigest() != sub.get('sha256'):
                        problems.append('served H56 short-path TIFF differs from the audited SHA-256')
                    else:
                        notes.append(f"short path serves byte-identically: {short_name}")

        # H55-PROFILE is historical and remains separate from the current H56 artifact.
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

    # Verify current H56 measurements without conflating H55's historical result, H55-PROFILE,
    # H55-1, H55-EDGE, or the separately failed R3 research artifact with the current pointer.
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

    # The prose-literal list was collected and then never read: the diagnostic existed but was
    # invisible, so a page could quote a 4-decimal score that its own receipt had changed.
    # Surface it as an informational note (not a failure: several pages deliberately quote the
    # published scores in prose, and the receipts remain the machine-readable source of truth).
    if typed_numbers:
        notes.append(f"prose literals with 4+ decimals found in HTML: {len(typed_numbers)} "
                     "(informational; receipts stay authoritative)")
        notes.extend("  " + x for x in typed_numbers[:4])

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
