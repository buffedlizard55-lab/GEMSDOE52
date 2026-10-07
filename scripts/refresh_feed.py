#!/usr/bin/env python3
"""Regenerate a dated, stdlib-only local-evidence feed. No portal interaction.

DrivenData automation is disabled by default: review registry/source_policy.json
and the site's disclosed limitation. A fresh local timestamp is NOT a fresh
leaderboard observation. Run this before scripts/publish_site_r2.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / 'evidence'
DOCS = ROOT / 'docs'
DATA = DOCS / 'data'
DL = DOCS / 'downloads'
BOARD = 'https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/'
OUR_BEST = 0.2778  # brief/owner attribution, NOT an authenticated artifact score
H54_FILE = 'gems52-h54-revealed-core-strike-continuation-50517px-r1.tif'
H54_STEM = H54_FILE[:-4]
H54_AUDIT_NOTE = 'H54 legacy research/audit only; no comparable spatial holdout; not approved for submission.'
H56_SHORT_NAME = 'h56-candidate'
H56_SLOT_REVIEW = 'evidence/h56_slot_gate_review_2026-10-07.json'


def log(message):
    print(message, flush=True)


def write(name, obj):
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / name
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')
    return path


def safe(value):
    if isinstance(value, float) and not (-float('inf') < value < float('inf')):
        return None
    if isinstance(value, dict):
        return {k: safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [safe(v) for v in value]
    return value


def copy_evidence():
    # Historical evidence remains in Git for audit, but is not silently promoted
    # as current just because this scheduled publisher ran.
    copied = []
    for path in sorted(EV.glob('*_r[23]*.json')):
        write(path.name, safe(json.loads(path.read_text())))
        copied.append(path.name)
    h54_names = (
        'revealed_calibration.json', 'revealed_budget.json', 'independence_revealed.json',
        'cotraining_views54.json', 'revealed_submission_audit.json', 'revealed_format_gate.json',
        'revealed_uniqueness_gate.json', 'a_only_geological_reasoning54.json',
        'h54_prior_inventory_availability.json', 'h54_artifact_review_2026-10-07.json',
        'h56_slot_gate_review_2026-10-07.json', f'submission_{H54_STEM}.json',
    )
    for name in h54_names:
        path = EV / name
        if path.exists():
            write(name, safe(json.loads(path.read_text())))
            copied.append(name)
    for name in ('r2_preregistration', 'r3_preregistration', 'h55_preregistration',
                 'h55_paired_shoulders_preregistration', 'h55_edge_preregistration',
                 'source_policy', 'data_manifest', 'irregularities', 'leaderboard_snapshot_2026-10-07'):
        path = ROOT / 'registry' / (name + '.json')
        if path.exists():
            if name in ('h55_preregistration', 'h55_paired_shoulders_preregistration', 'h55_edge_preregistration'):
                # The frozen registration's byte hash is a preregistration receipt; preserve its exact
                # bytes in the static site rather than semantically reserializing the JSON.
                target = DATA / (name + '.json')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
            else:
                write(name + '.json', safe(json.loads(path.read_text())))
            copied.append(name + '.json')
    # H55 publishes its own evidence the same way the R2 round publishes *_r2.json: copied on every
    # run so the page cannot drift from the artefact, and named by round so it is never mistaken for
    # another round's numbers.  The Phase-2 reasoning record is staged next to the raster it explains.
    for pat in ('h55_*.json', 'submission_gems52-h55-*.json'):
        for path in sorted(EV.glob(pat)):
            write(path.name, safe(json.loads(path.read_text())))
            copied.append(path.name)
    for path in sorted(EV.glob('h55_reasoning_*.json')):
        (DL / path.name).write_text(path.read_text())
    reasoning = EV / 'a_only_reasoning_r3.csv'
    if reasoning.exists():
        target = DL / reasoning.name
        DL.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_bytes() != reasoning.read_bytes():
            target.write_bytes(reasoning.read_bytes())
        copied.append(reasoning.name)
    h54_reasoning = EV / 'a_only_reasoning54.csv'
    if h54_reasoning.exists():
        target = DL / h54_reasoning.name
        DL.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_bytes() != h54_reasoning.read_bytes():
            target.write_bytes(h54_reasoning.read_bytes())
        copied.append(h54_reasoning.name)
    paired_note = ROOT / 'knowledge/11_h55_paired_shoulders.md'
    if paired_note.exists():
        target = DATA / 'h55_paired_shoulders_hypotheses.md'
        if not target.exists() or target.read_bytes() != paired_note.read_bytes():
            target.write_bytes(paired_note.read_bytes())
        copied.append(target.name)
    paired_review = EV / 'review_execution_h55_paired_shoulders.json'
    if paired_review.exists():
        write(paired_review.name, safe(json.loads(paired_review.read_text())))
        copied.append(paired_review.name)
    # H56's build/verification/review receipts are linked from its candidate and guide pages.
    # Preserve their exact bytes: the slot-gate supplement pins the build and verifier hashes.
    for name in ('gems52-h56-build.json', 'gems52-h56-verify.json',
                 'gems52-h56_review_receipt.json', 'h56_a_only_reasoning_scope_2026-10-07.json',
                 'review_current_integrated_tree_2026-10-07.json'):
        path = EV / name
        if path.exists():
            target = DATA / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or target.read_bytes() != path.read_bytes():
                target.write_bytes(path.read_bytes())
            copied.append(name)
    return copied


def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def h54_audit_record():
    """Return an explicit audit-only record without replacing the current H55 pointer."""
    path = DL / H54_FILE
    receipt_path = EV / f'submission_{H54_STEM}.json'
    if not path.exists() or not receipt_path.exists():
        return None
    receipt = json.loads(receipt_path.read_text())
    actual = file_hash(path)
    if actual != receipt.get('sha256'):
        raise ValueError('H54 audit TIFF differs from its recorded bytes')
    marker = ROOT / 'submission/H54_RESEARCH_LATEST.txt'
    if marker.exists() and marker.read_text().strip() != H54_FILE:
        raise ValueError('H54 research marker points to a different TIFF')
    return {
        'status': 'legacy-audit-only',
        'exists': True,
        'file': H54_FILE,
        'submission_name': 'GEMSDOE52-H54-Research-AuditOnly',
        'submission_note': H54_AUDIT_NOTE,
        'submission_note_chars': len(H54_AUDIT_NOTE),
        'sha256': actual,
        'bytes': path.stat().st_size,
        'format_ok': bool(receipt.get('format', {}).get('ok')),
        'format': receipt.get('format', {}),
        'uniqueness': receipt.get('uniqueness', {}),
        'writer_receipt': receipt.get('writer_receipt', {}),
        'canonical_download': 'downloads/' + H54_FILE,
        'canonical_zip': 'downloads/' + H54_STEM + '.zip',
        'short_download': 'downloads/h54-audit-only.tif',
        'short_zip': 'downloads/h54-audit-only.zip',
        'short_download_zip': 'downloads/h54-audit-only.zip',
        'download': 'downloads/h54-audit-only.tif',
        'download_zip': 'downloads/h54-audit-only.zip',
        'approved_for_weekly_slot': False,
        'comparable_spatial_holdout': 'not demonstrated',
        'official_score': None,
        'official_score_file_mapping_authenticated': False,
        'global_decoded_pattern_uniqueness': 'unknown; bounded local prior audit only',
        'receipt': 'data/submission_' + H54_STEM + '.json',
        'review': 'data/h54_artifact_review_2026-10-07.json',
        'prior_inventory': 'data/h54_prior_inventory_availability.json',
        'a_only_reasoning_csv': 'downloads/a_only_reasoning54.csv',
    }


def make_h54_audit_zip():
    """Build a single-TIFF archive whose note cannot be mistaken for slot approval."""
    import zipfile
    src = DL / H54_FILE
    receipt = EV / f'submission_{H54_STEM}.json'
    if not src.exists() or not receipt.exists():
        return None
    audit = json.loads(receipt.read_text())
    expected_sha = audit.get('sha256')
    if file_hash(src) != expected_sha:
        raise ValueError('H54 TIFF SHA-256 does not match its frozen receipt')
    body = '\n'.join((
        H54_FILE,
        f'sha256 {expected_sha}',
        f"{src.stat().st_size} bytes; one-band float32 GeoTIFF; audit/research only.",
        '',
        'STATUS: ' + H54_AUDIT_NOTE,
        'No comparable spatially blocked holdout is demonstrated. Do not spend an upload slot on this file.',
        'The public leaderboard score-to-filename mapping is not authenticated.',
        '',
    ))
    target = DL / (H54_STEM + '.zip')
    members = [H54_FILE, 'SUBMISSION_NOTE.txt', 'evidence.json']
    if target.exists():
        try:
            with zipfile.ZipFile(target) as old:
                valid = (old.namelist() == members and old.read(H54_FILE) == src.read_bytes()
                         and old.read('SUBMISSION_NOTE.txt') == body.encode()
                         and old.read('evidence.json') == receipt.read_bytes() and old.testzip() is None)
            if valid:
                return str(target)
        except (OSError, KeyError, zipfile.BadZipFile):
            pass
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(src, arcname=H54_FILE)
        archive.writestr('SUBMISSION_NOTE.txt', body)
        archive.write(receipt, arcname='evidence.json')
    return str(target)


def stage_h54_short_aliases():
    """Short links are byte-identical aliases, never rewritten prediction rasters."""
    import shutil
    pairs = ((DL / H54_FILE, DL / 'h54-audit-only.tif'),
             (DL / (H54_STEM + '.zip'), DL / 'h54-audit-only.zip'))
    for source, alias in pairs:
        if not source.exists():
            raise FileNotFoundError(source)
        if not alias.exists() or alias.read_bytes() != source.read_bytes():
            alias.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, alias)
        if file_hash(source) != file_hash(alias):
            raise ValueError(f'H54 short alias is not byte-identical: {alias.name}')


def stage_h56_short_aliases(name: str) -> None:
    """Publish short links as byte-identical aliases of the current H56 candidate."""
    import shutil
    if not name.startswith('gems52-h56-') or not name.endswith('.tif'):
        raise ValueError('H56 alias helper received a non-H56 TIFF')
    stem = name[:-4]
    pairs = ((DL / name, DL / (H56_SHORT_NAME + '.tif')),
             (DL / (stem + '.zip'), DL / (H56_SHORT_NAME + '.zip')))
    for source, alias in pairs:
        if not source.exists():
            raise FileNotFoundError(source)
        if not alias.exists() or alias.read_bytes() != source.read_bytes():
            shutil.copyfile(source, alias)
        if file_hash(source) != file_hash(alias):
            raise ValueError(f'H56 short alias is not byte-identical: {alias.name}')


def submission_note(d):
    """The <=200-character note that distinguishes this submission later.

    A record may carry both a short ``submission_note`` (what actually goes in the portal's box, which
    is length-limited) and a ``submission_note_long`` (the full reasoning, published on the site and in
    the evidence file).  Truncating the long one is what produced a note that ended mid-sentence, so
    the long form is never truncated into the short field: it is offered separately.
    """
    if d.get('submission_note'):
        return str(d['submission_note'])[:200]
    n = (f"H54 revealed-core {d.get('retained_core_px', 0)}px + {d.get('novel_px', 0)}px novel "
         f"strike-continuation; 200m corridor excluded; |G|=14089")
    return n[:200]


def make_single_tiff_zip(name: str):
    """Preserve the current H56 package contract: ZIP contains exactly its TIFF."""
    import zipfile
    src = ROOT / 'submission' / name
    report_path = DATA / 'submission.json'
    target = DL / (name[:-4] + '.zip') if name.endswith('.tif') else DL / (name + '.zip')
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    if report.get('file') != name or not src.exists():
        return None
    expected_sha = report.get('sha256')
    if expected_sha and file_hash(src) != expected_sha:
        raise ValueError('Current H56 TIFF differs from docs/data/submission.json')
    if target.exists():
        try:
            with zipfile.ZipFile(target) as old:
                if (old.namelist() == [name] and old.read(name) == src.read_bytes()
                        and old.testzip() is None):
                    return str(target)
        except (OSError, KeyError, zipfile.BadZipFile):
            pass
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(src, arcname=name)
    return str(target)


def make_zip(name):
    """One-click ZIP beside the TIF: the raster, the note to paste, and the evidence behind it.

    Round-agnostic on purpose.  Two rounds have shipped records with different shapes (H54 carries
    ``retained_core_px`` / ``novel_along_strike_px`` / ``corridor_excluded_m``; H55 carries
    ``geometry`` / ``selection`` / ``uniqueness``), and a zip that prints ``None px retained core``
    for a round it was not written against is worse than a generic one.  So the body is assembled
    from the keys the record actually has, and says which round it came from.
    """
    if name == H54_FILE:
        return make_h54_audit_zip()
    current_receipt = DATA / 'submission.json'
    if (name.startswith('gems52-h56-') and current_receipt.exists()
            and json.loads(current_receipt.read_text()).get('file') == name):
        return make_single_tiff_zip(name)
    import zipfile
    src = ROOT / 'submission' / name
    if not src.exists():
        return None
    stem = name[:-4] if name.endswith('.tif') else name
    ev = EV / f'submission_{stem}.json'
    d = json.loads(ev.read_text()) if ev.exists() else {}
    proj = d.get('projected_dti') or {}
    lines = [
        name,
        f"sha256 {d.get('sha256')}",
        f"{d.get('bytes')} bytes, 1 band, float32, EPSG:32611, values in [0,1], no NaN.",
        '',
        "SUBMISSION NOTE (<=200 chars, paste into the portal's notes box):",
        submission_note(d),
        '',
    ]
    if d.get('submission_name'):
        lines += [f"SUBMISSION NAME: {d['submission_name']}", '']
    if d.get('retained_core_px') is not None:
        lines += [
            f"What it is: {d.get('budget')} emitted pixels = {d.get('retained_core_px')} px retained "
            f"core (the double-corroborated atom A&C, whose credit the organiser's own published "
            f"scores bound exactly) + {d.get('novel_px')} px strictly novel "
            f"({d.get('novel_along_strike_px')} along the recovered strike of that structure, "
            f"{d.get('novel_far_px')} free candidates on the same fabric).",
            f"Nothing is emitted within {d.get('corridor_excluded_m')} m of a mapped trace, because "
            f"that ring's credit is exactly zero in the organiser's own scores (knowledge/10 s2).",
            f"Projected DTI {proj.get('mean_dti')} (P(win over 0.2778) {proj.get('p_win')}); the "
            f"projection is an integral over a stated prior, not a forecast - see "
            f"evidence/revealed_budget.json.",
            '',
        ]
    geo, sel, uni = d.get('geometry') or {}, d.get('selection') or {}, d.get('uniqueness') or {}
    if geo:
        lines += [
            f"What it is: {geo.get('S')} emitted pixels, every one 8-isolated "
            f"(largest component {geo.get('max_component')}), placed by a coverage-greedy on the "
            f"metric's own numerator.",
            f"Placement efficiency A/S = {geo.get('A_per_S')} = "
            f"{(geo.get('spacing_efficiency') or 0):.2%} of the exact 9.380298 kernel-disc ceiling; "
            f"the file that scored 0.2778 reached 8.044 (85.75%).",
        ]
    if sel:
        lines += [
            f"Selected by the pre-registered rule from {sel.get('source')}: "
            f"{sel.get('arm')}|{sel.get('emitter')}. Blocked whole-segment holdout, 4 folds x 2 "
            f"instruments, matched-budget random control: hide {sel.get('hide')} "
            f"({sel.get('hide_wins')}/4 folds) vs random; tip {sel.get('tip')} "
            f"({sel.get('tip_wins')}/4). Those are recovery numbers on hidden catalogue segments, "
            f"NOT a forecast of the portal score.",
            f"|G| = {sel.get('n_g')} calibrated by inverting DTI = T/(0.2*S + 0.8*|G|) on 13 "
            f"SHA-256-verified scored rasters (evidence/h55_g_calibration.json).",
        ]
    if uni:
        lines += [
            f"Uniqueness gate: {uni.get('relation_to_union')}; "
            f"{(uni.get('novel_fraction') or 0):.1%} of this file's pixels touch none of the "
            f"{uni.get('n_priors_checked')} priors scanned, and {uni.get('prior_px_dropped')} prior "
            f"pixels are deliberately not re-emitted.",
        ]
    if d.get('projection'):
        lines += [
            f"Placement gain in isolation (the 0.2778 file's own rho_A = 0.01287 applied to this "
            f"file's measured coverage, nothing else changed): DTI ~ "
            f"{d['projection'].get('geometry_only_dti')}. Arithmetic given its assumption, and the "
            f"assumption is stated in the evidence file.",
        ]
    if d.get('submission_note_long'):
        lines += ['', 'FULL REASONING (too long for the portal box; published on the site):',
                  str(d['submission_note_long']), '']
    body = "\n".join(lines)
    zp = DL / f'{stem}.zip'
    expected_members = [name, 'SUBMISSION_NOTE.txt'] + (['evidence.json'] if ev.exists() else [])
    # Preserve a byte-identical, already-valid archive rather than changing ZIP timestamps on every
    # scheduled refresh. Rebuild only when a member, note, or receipt actually changes.
    if zp.exists():
        try:
            with zipfile.ZipFile(zp) as existing:
                valid = (existing.namelist() == expected_members
                         and existing.read(name) == src.read_bytes()
                         and existing.read('SUBMISSION_NOTE.txt') == body.encode())
                if ev.exists():
                    valid = valid and existing.read('evidence.json') == ev.read_bytes()
                valid = valid and existing.testzip() is None
            if valid:
                return str(zp)
        except (OSError, KeyError, zipfile.BadZipFile):
            pass
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(src, arcname=name)
        z.writestr('SUBMISSION_NOTE.txt', body)
        if ev.exists():
            z.write(ev, arcname='evidence.json')
    return str(zp)


def latest_submission():
    """Resolve the current marker without allowing an older round to outrank H56 by receipt shape."""
    order = []
    for marker in (ROOT / 'submission/LATEST.txt', ROOT / 'submission/R2_LATEST.txt'):
        if marker.exists():
            nm = marker.read_text().strip()
            stem = nm[:-4] if nm.endswith('.tif') else nm
            own = EV / f'submission_{stem}.json'
            order.append((nm, marker, own))
    if not order:
        return dict(exists=False, file=None, note='No artifact has been built.')

    # H56's complete receipt is the maintained docs/data/submission.json record rather than an
    # evidence/submission_<stem>.json file. When it matches the primary marker, preserve it as the
    # current report instead of falling back to a historical R2 receipt.
    name, marker, own = order[0]
    published = DATA / 'submission.json'
    report = {}
    if published.exists():
        candidate = json.loads(published.read_text())
        if candidate.get('file') == name:
            report = candidate
    if not report:
        audited = [c for c in order if c[2].exists()]
        name, marker, own = (audited[0] if audited else order[0])
        r2 = EV / 'submission_r2.json'
        if own.exists() and json.loads(own.read_text()).get('file') == name:
            report = json.loads(own.read_text())
        elif r2.exists() and json.loads(r2.read_text()).get('file') == name:
            report = json.loads(r2.read_text())
        else:
            report = dict(file=name, approved_for_weekly_slot=False,
                          promotion='historical research artifact; consult its original audit')

    path = DL / name
    report['marker'] = str(marker.relative_to(ROOT))
    report['exists'] = path.exists()
    report['download'] = 'downloads/' + name
    report['download_zip'] = 'downloads/' + name.replace('.tif', '') + '.zip'
    if name.startswith('gems52-h56-') and name.endswith('.tif'):
        report['short_download'] = 'downloads/' + H56_SHORT_NAME + '.tif'
        report['short_download_zip'] = 'downloads/' + H56_SHORT_NAME + '.zip'
        report['short_aliases_are_canonical_byte_copies'] = True
    report['submission_note'] = submission_note(report)
    report['submission_note_chars'] = len(report['submission_note'])
    if path.exists():
        report['bytes'] = path.stat().st_size
        actual = file_hash(path)
        report['published_byte_hash_matches_receipt'] = report.get('sha256') == actual
        if report.get('sha256') and report['sha256'] != actual:
            raise ValueError('Published TIFF differs from the audited TIFF. Do not upload it.')
    return report


def parse_board(text):
    """Conservative optional parser. It is never called without recorded permission."""
    import html
    rows = []
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', text, re.S):
        cells = [html.unescape(re.sub(r'<[^>]+>', ' ', x)).strip()
                 for x in re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)]
        scores = [float(t) for t in cells if re.fullmatch(r'0\.\d{3,6}', t)]
        if scores and cells and re.fullmatch(r'\d+', cells[0]):
            names = [t for t in cells[1:] if t and not re.fullmatch(r'[\d.]+', t)]
            rows.append(dict(rank=cells[0], team=names[0] if names else 'not parsed', score=scores[0]))
    return rows


def fetch_board(do_fetch=False):
    snapshots = sorted((ROOT / 'registry').glob('leaderboard_snapshot_*.json'))
    snap = snapshots[-1] if snapshots else None
    out = json.loads(snap.read_text()) if snap and snap.exists() else dict(rows=[])
    out.update(source=BOARD, owner_best_reported=OUR_BEST,
               artifact_score_authenticated=False,
               note='Dated participant-level observation; no filename/hash/receipt attribution. Participant identity is not authenticated as the user\'s team.')
    policy = json.loads((ROOT / 'registry/source_policy.json').read_text())['drivendata']
    allowed = bool(policy.get('automated_fetch_allowed') and policy.get('written_permission_reference'))
    out['automated_fetch_allowed'] = allowed
    if not allowed:
        out['status'] = 'dated snapshot; automated DrivenData access disabled by Terms-of-Use policy'
        out['fetch_requested_but_disabled'] = bool(do_fetch)
        # Crucially, fetched_utc is retained unchanged.
        return out
    if not do_fetch:
        out['status'] = 'dated snapshot; this run did not fetch external data'
        return out
    try:
        request = urllib.request.Request(BOARD, headers={'User-Agent': 'GEMSDOE52 permitted source refresh'})
        text = urllib.request.urlopen(request, timeout=25).read().decode('utf-8', 'replace')
        rows = parse_board(text)
        if not rows:
            raise ValueError('No verified table rows parsed; retaining prior snapshot')
        out.update(status='fetched under recorded permission', rows=rows, top=rows[0]['score'],
                   fetched_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    except Exception as error:
        out['status'] = 'external fetch failed; prior snapshot retained: ' + str(error)[:180]
        out['fetch_error'] = True
    return out


def current_branch(explicit=None):
    if explicit:
        return explicit
    head = ROOT / '.git/HEAD'
    if head.exists():
        value = head.read_text().strip()
        if value.startswith('ref: refs/heads/'):
            return value.removeprefix('ref: refs/heads/')
    return 'detached or unknown (not assumed)'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true', help='Only honored with recorded written permission; otherwise no DrivenData request.')
    parser.add_argument('--branch', help='Actual Actions ref, if Git is checked out detached.')
    args = parser.parse_args()
    copied = copy_evidence()
    DL.mkdir(parents=True, exist_ok=True)
    # Stage the rasters and the one-click ZIP BEFORE the report is written: the report points into
    # docs/downloads/, so publishing after it left the site offering a file that was not there yet
    # (IR-52-028).
    for f in sorted((ROOT / 'submission').glob('*.tif')):
        tgt = DL / f.name
        if not tgt.exists() or file_hash(tgt) != file_hash(f):
            tgt.write_bytes(f.read_bytes())
    for mk in ('LATEST.txt', 'R2_LATEST.txt'):
        mp = ROOT / 'submission' / mk
        if mp.exists():
            make_zip(mp.read_text().strip())
    current_marker = ROOT / 'submission/LATEST.txt'
    if current_marker.exists():
        current_name = current_marker.read_text().strip()
        if current_name.startswith('gems52-h56-'):
            stage_h56_short_aliases(current_name)
    h54_marker = ROOT / 'submission/H54_RESEARCH_LATEST.txt'
    if h54_marker.exists():
        if h54_marker.read_text().strip() != H54_FILE:
            raise ValueError('H54 research-only marker does not match the audited H54 artifact')
        make_h54_audit_zip()
        stage_h54_short_aliases()
    # Also publish explicitly named research-only ZIPs without promoting them
    # through either global pointer. Their package receipts remain per-artifact.
    edge_marker = ROOT / 'submission/H55_EDGE_LATEST.txt'
    if edge_marker.exists():
        edge_name = edge_marker.read_text().strip()
        edge_zip = ROOT / 'submission' / Path(edge_name).with_suffix('.zip').name
        if edge_zip.exists():
            target_zip = DL / edge_zip.name
            if not target_zip.exists() or file_hash(target_zip) != file_hash(edge_zip):
                target_zip.write_bytes(edge_zip.read_bytes())
    sub = latest_submission()
    h54 = h54_audit_record()
    board = fetch_board(args.fetch)
    write('submission.json', sub)
    if h54 is not None:
        write('h54_audit.json', h54)
    write('leaderboard.json', board)
    inv = EV / 'prior_inventory_r2.json'
    entries = json.loads(inv.read_text()).get('entries', []) if inv.exists() else []
    write('feed.json', dict(
        generated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        branch=current_branch(args.branch), repo='buffedlizard55-lab/GEMSDOE52',
        evidence_copied=copied,
        files=sorted({p.name for pat in ('*_r[23]*.json', 'h55_*.json', 'h56_*.json', 'submission_gems52-h55-*.json')
                      for p in DATA.glob(pat)}),
        submission=sub.get('file'), downloads=len(list(DL.glob('*.tif'))),
        h54_audit_only=(h54 or {}).get('file'),
        h55_paired_shoulders='separate failed-gate experiment; no TIFF or slot use',
        leaderboard_status=board['status'],
        leaderboard_last_observed_utc=board.get('fetched_utc') or board.get('observed_date_utc'),
        prior_entries=len(entries), eligible_prior_rasters=sum(bool(r.get('eligible_prior')) for r in entries),
        scientific_gate=sub.get('approved_for_weekly_slot', False), slots_used=0,
        freshness_note='Local evidence refresh is automatic; the board is a dated snapshot. No automatic portal submission.'))
    log('Feed updated. ' + board['status'])
    return 1 if board.get('fetch_error') else 0


if __name__ == '__main__':
    sys.exit(main())
