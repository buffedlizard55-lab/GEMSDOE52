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
    for path in sorted(EV.glob('*_r2.json')):
        write(path.name, safe(json.loads(path.read_text())))
        copied.append(path.name)
    for name in ('r2_preregistration', 'source_policy', 'data_manifest'):
        path = ROOT / 'registry' / (name + '.json')
        if path.exists():
            write(name + '.json', safe(json.loads(path.read_text())))
    return copied


def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def submission_note(d):
    """The <=200-character note that distinguishes this submission later."""
    if d.get('submission_note'):
        return str(d['submission_note'])[:200]
    n = (f"H54 revealed-core {d.get('retained_core_px', 0)}px + {d.get('novel_px', 0)}px novel "
         f"strike-continuation; 200m corridor excluded; |G|=14089")
    return n[:200]


def make_zip(name):
    """One-click ZIP beside the TIF: the raster, the note to paste, and the evidence behind it."""
    import zipfile
    src = ROOT / 'submission' / name
    if not src.exists():
        return None
    stem = name[:-4] if name.endswith('.tif') else name
    ev = EV / f'submission_{stem}.json'
    d = json.loads(ev.read_text()) if ev.exists() else {}
    proj = d.get('projected_dti') or {}
    body = (
        f"{name}\n"
        f"sha256 {d.get('sha256')}\n"
        f"{d.get('bytes')} bytes, 1 band, float32, EPSG:32611, values in [0,1], no NaN.\n\n"
        f"SUBMISSION NOTE (<=200 chars, paste into the portal's notes box):\n"
        f"{submission_note(d)}\n\n"
        f"What it is: {d.get('budget')} emitted pixels = {d.get('retained_core_px')} px retained core "
        f"(the double-corroborated atom A&C, whose credit the organiser's own published scores bound "
        f"exactly) + {d.get('novel_px')} px strictly novel ({d.get('novel_along_strike_px')} along the "
        f"recovered strike of that structure, {d.get('novel_far_px')} free candidates on the same "
        f"fabric).\n"
        f"Nothing is emitted within {d.get('corridor_excluded_m')} m of a mapped trace, because that "
        f"ring's credit is exactly zero in the organiser's own scores (knowledge/10 s2).\n"
        f"Projected DTI {proj.get('mean_dti')} (P(win over 0.2778) {proj.get('p_win')}); the "
        f"projection is an integral over a stated prior, not a forecast - see "
        f"evidence/revealed_budget.json.\n")
    zp = DL / f'{stem}.zip'
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(src, arcname=name)
        z.writestr('SUBMISSION_NOTE.txt', body)
        if ev.exists():
            z.write(ev, arcname='evidence.json')
    return str(zp)


def latest_submission():
    # Two rounds ship artefacts and each keeps its own marker.  Prefer the one that carries a complete
    # gate report of its own, so the site never offers a file whose audit it cannot show; IR-52-029
    # records the choice, the reason, and that reverting is one line in submission/LATEST.txt.
    order = []
    for marker in (ROOT / 'submission/LATEST.txt', ROOT / 'submission/R2_LATEST.txt'):
        if marker.exists():
            nm = marker.read_text().strip()
            stem = nm[:-4] if nm.endswith('.tif') else nm
            own = EV / f'submission_{stem}.json'
            order.append((nm, marker, own))
    if not order:
        return dict(exists=False, file=None, note='No artifact has been built.')
    audited = [c for c in order if c[2].exists()]
    name, marker, own = (audited[0] if audited else order[0])
    path = DL / name
    r2 = EV / 'submission_r2.json'
    if own.exists() and json.loads(own.read_text()).get('file') == name:
        report = json.loads(own.read_text())
    elif r2.exists() and json.loads(r2.read_text()).get('file') == name:
        report = json.loads(r2.read_text())
    else:
        report = dict(file=name, approved_for_weekly_slot=False,
                      promotion='historical research artifact; consult its original audit')
    report['marker'] = str(marker.relative_to(ROOT))
    report['exists'] = path.exists()
    report['download'] = 'downloads/' + name
    report['download_zip'] = 'downloads/' + name.replace('.tif', '') + '.zip'
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
    snap = ROOT / 'registry/leaderboard_snapshot_2026-10-06.json'
    out = json.loads(snap.read_text()) if snap.exists() else dict(rows=[])
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
        if not tgt.exists() or tgt.stat().st_size != f.stat().st_size:
            tgt.write_bytes(f.read_bytes())
    for mk in ('LATEST.txt', 'R2_LATEST.txt'):
        mp = ROOT / 'submission' / mk
        if mp.exists():
            make_zip(mp.read_text().strip())
    sub = latest_submission()
    board = fetch_board(args.fetch)
    write('submission.json', sub)
    write('leaderboard.json', board)
    inv = EV / 'prior_inventory_r2.json'
    entries = json.loads(inv.read_text()).get('entries', []) if inv.exists() else []
    write('feed.json', dict(
        generated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        branch=current_branch(args.branch), repo='buffedlizard55-lab/GEMSDOE52',
        evidence_copied=copied, files=sorted(p.name for p in DATA.glob('*_r2.json')),
        submission=sub.get('file'), downloads=len(list(DL.glob('*.tif'))),
        leaderboard_status=board['status'], leaderboard_last_observed_utc=board.get('fetched_utc'),
        prior_entries=len(entries), eligible_prior_rasters=sum(bool(r.get('eligible_prior')) for r in entries),
        scientific_gate=sub.get('approved_for_weekly_slot', False), slots_used=0,
        freshness_note='Local evidence refresh is automatic; the board is a dated snapshot. No automatic portal submission.'))
    log('Feed updated. ' + board['status'])
    return 1 if board.get('fetch_error') else 0


if __name__ == '__main__':
    sys.exit(main())
