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
    for path in sorted(EV.glob('*_r[23]*.json')):
        write(path.name, safe(json.loads(path.read_text())))
        copied.append(path.name)
    for name in ('r2_preregistration', 'r3_preregistration', 'h55_preregistration',
                 'h55_edge_preregistration', 'h58_preregistration', 'h59_preregistration',
                 'source_policy', 'data_manifest', 'irregularities',
                 'leaderboard_snapshot_2026-10-07'):
        path = ROOT / 'registry' / (name + '.json')
        if path.exists():
            if name in ('h55_preregistration', 'h55_edge_preregistration',
                        'h58_preregistration', 'h59_preregistration'):
                # A frozen registration's bytes are part of its audit trail; preserve them in the
                # static site rather than semantically reserializing its JSON.
                target = DATA / (name + '.json')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
            else:
                write(name + '.json', safe(json.loads(path.read_text())))
            copied.append(name + '.json')
    for name in ('leaderboard_observation_2026-10-09T201800Z.json',
                 'revealed_submission_audit.json'):
        path = EV / name
        if path.is_file():
            write(name, safe(json.loads(path.read_text())))
            copied.append(name)
    # H55 publishes its own evidence the same way the R2 round publishes *_r2.json: copied on every
    # run so the page cannot drift from the artefact, and named by round so it is never mistaken for
    # another round's numbers.  The Phase-2 reasoning record is staged next to the raster it explains.
    for pat in ('ctd5_*.json', 'h55_*.json', 'h58_*.json', 'h59_*.json', 'submission_gems52-h55-*.json',
                'submission_gems52-h58-*.json', 'submission_gems52-h59-*.json'):
        for path in sorted(EV.glob(pat)):
            write(path.name, safe(json.loads(path.read_text())))
            copied.append(path.name)
    marker = ROOT / 'submission/LATEST.txt'
    if marker.exists():
        current_name = marker.read_text().strip()
        current_stem = current_name[:-4] if current_name.endswith('.tif') else current_name
        current_receipt = EV / f'submission_{current_stem}.json'
        if current_receipt.exists() and current_stem.startswith('gems52-h56-cotrain-'):
            receipt = json.loads(current_receipt.read_text())
            write('submission_h56.json', safe(receipt))
            copied.append('submission_h56.json')
            # The audit page links the per-candidate reasoning record from the tagged receipt.
            # Publish only a basename under the evidence directory; never follow an arbitrary
            # receipt path outside the repository into the static site.
            reasoning_name = Path(str((receipt.get('reasoning') or {}).get('json') or '')).name
            if reasoning_name.startswith('h56_reasoning_') and reasoning_name.endswith('.json'):
                reasoning_source = EV / reasoning_name
                if reasoning_source.is_file():
                    DATA.mkdir(parents=True, exist_ok=True)
                    (DATA / reasoning_name).write_bytes(reasoning_source.read_bytes())
                    copied.append(reasoning_name)
    for path in sorted(EV.glob('h55_reasoning_*.json')):
        (DL / path.name).write_text(path.read_text())
    reasoning = EV / 'a_only_reasoning_r3.csv'
    if reasoning.exists():
        target = DL / reasoning.name
        DL.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_bytes() != reasoning.read_bytes():
            target.write_bytes(reasoning.read_bytes())
        copied.append(reasoning.name)
    # These historical inventories preserve verbatim owner/source excerpts, including earlier
    # unsupported public-high-score and score-causality claims. Keep the evidence originals intact,
    # but annotate the public copies every time the scheduled feed refreshes them.
    notice = (
        'Historical owner-controlled/source-review excerpts, not current verified competition evidence. '
        'Any older text calling 0.2778 the highest public score or attributing a score change to the '
        '0.2600-to-0.2778 pixel difference is superseded. The saved 2026-10-09 20:18 UTC public board '
        'places 0.2778 at rank 17 (top 0.3774); no organizer TIFF-hash receipt or causal explanation is '
        'established. See knowledge/49_why_02778_phd_answer.md.'
    )
    for name in ('ctd5_sources.json', 'source_review_r2.json'):
        target = DATA / name
        if target.exists():
            snapshot = json.loads(target.read_text())
            snapshot['interpretation_notice'] = notice
            snapshot['current_correction'] = '../../knowledge/49_why_02778_phd_answer.md'
            write(name, safe(snapshot))
    return copied


def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def make_zip(name):
    """Create or verify a research-only ZIP containing exactly one TIFF.

    Portal identifiers, notes, status files and evidence sidecars are never placed in archive ZIPs.
    Downloading an archive is not submission approval.
    """
    import zipfile
    src = ROOT / 'submission' / name
    if not src.is_file():
        return None
    stem = name[:-4] if name.lower().endswith(('.tif', '.tiff')) else name
    zp = DL / f'{stem}.zip'
    payload = src.read_bytes()
    if zp.is_file():
        try:
            with zipfile.ZipFile(zp) as existing:
                valid = (existing.namelist() == [name]
                         and existing.read(name) == payload
                         and existing.testzip() is None)
            if valid:
                return str(zp)
        except (OSError, KeyError, zipfile.BadZipFile):
            pass
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, payload)
    with zipfile.ZipFile(zp) as check:
        if check.namelist() != [name] or check.read(name) != payload or check.testzip() is not None:
            raise ValueError(f'Research ZIP failed single-TIFF verification: {zp}')
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
    # A missing per-artefact receipt must NOT promote a different round's archive as "current".
    # This used to fall through to the next marker, so when H57 shipped without
    # evidence/submission_<h57 stem>.json the scheduled feed published the R2 archive's full report
    # under docs/data/submission.json -- pointing the whole site back at a two-year-old artefact.
    # The current marker wins whatever receipts exist; only its OWN receipt may be used.
    name, marker, own = order[0]
    stem = name[:-4] if name.endswith('.tif') else name
    path = DL / name
    r2 = EV / 'submission_r2.json'
    if own.exists():
        candidate = json.loads(own.read_text())
        if candidate.get('file') == name or candidate.get('stem') == stem:
            report = candidate
            report['file'] = name
        else:
            report = dict(file=name, approved_for_weekly_slot=False,
                          promotion='current round; no per-artefact receipt at '
                                    f'evidence/submission_{stem}.json, so no gate report is shown')
    elif r2.exists() and name == json.loads(r2.read_text()).get('file'):
        report = json.loads(r2.read_text())
    else:
        report = dict(file=name, approved_for_weekly_slot=False,
                      promotion='current round; no per-artefact receipt at '
                                f'evidence/submission_{stem}.json, so no gate report is shown')
    if report.get('synthetic') is True:
        report.update(
            approved_for_weekly_slot=False,
            promotion='synthetic methodology demo; not approved for portal upload',
            artifact_status='RESEARCH ONLY — SYNTHETIC METHODOLOGY DEMO',
            official_score_status='no portal upload or organizer score is recorded',
            submission_slots_used=0,
            slot_gate=dict(approved_for_weekly_slot=False,
                           reason='Synthetic inputs are not competition data; real-data holdout has not been run. Do not upload or spend a slot.'),
        )
    if report.get('format_gate') and not report.get('format'):
        report['format'] = report['format_gate']
    report['marker'] = str(marker.relative_to(ROOT))
    report['exists'] = path.exists()
    report['download'] = 'downloads/' + name
    report['download_zip'] = 'downloads/' + name.replace('.tif', '') + '.zip'
    if stem.startswith('gems52-h58-'):
        report.setdefault('short_tif', 'h58-candidate.tif')
        report.setdefault('short_zip', 'h58-candidate.zip')
        report.setdefault('promoted', False)
        report.setdefault('nonzero_px', report.get('emitted_pixels'))
    for key in ('submission_name', 'submission_note', 'submission_note_long', 'portal'):
        report.pop(key, None)
    report['artifact_status'] = 'RESEARCH ONLY · NOT FOR SUBMISSION'
    report['approved_for_submission'] = False
    report['approved_for_weekly_slot'] = False
    if path.exists():
        actual_bytes = path.stat().st_size
        actual = file_hash(path)
        if report.get('bytes') is not None and int(report['bytes']) != actual_bytes:
            raise ValueError('Published TIFF byte count differs from the audited receipt. Do not publish it.')
        if report.get('sha256') and report['sha256'] != actual:
            raise ValueError('Published TIFF differs from the audited TIFF. Do not upload it.')
        report['bytes'] = actual_bytes
        report['published_byte_hash_matches_receipt'] = report.get('sha256') == actual
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
    prior_observation = json.loads(snap.read_text()) if snap and snap.exists() else dict(rows=[])
    observation_path = EV / 'leaderboard_observation_2026-10-09T201800Z.json'
    observation = json.loads(observation_path.read_text()) if observation_path.is_file() else None
    if observation:
        rows = [{'rank': row['rank'], 'team': row['participant'],
                 'score': row['best_public_dw_tversky']}
                for row in observation.get('rows', [])]
        subject = next((row for row in rows if row['team'] == 'extradr19'), None)
        top = max((row['score'] for row in rows if row['rank'] == 1), default=None)
        out = dict(
            status='partial dated public-board observation; automated DrivenData access disabled by Terms-of-Use policy',
            observed_date_utc=observation.get('observed_utc', '')[:10],
            observed_at_utc=observation.get('observed_utc'),
            source=BOARD,
            retrieved_by=observation.get('observation_method'),
            evidence_class=observation.get('evidence_class', 'PUBLIC-LEADERBOARD OBSERVATION'),
            rows=rows,
            rows_complete=False,
            top=top,
            observed_subject=subject,
            prior_snapshot_file=snap.name if snap else None,
            prior_snapshot_status='historical; not the later observation',
            owner_best_reported=OUR_BEST,
            artifact_score_authenticated=False,
            note='Selected team-level board rows are transcribed from the saved observation; participant identity is not authenticated as the repository owner, and no row binds a TIFF hash or organizer receipt.',
            current_observation_correction={
                'observed_utc': observation.get('observed_utc'),
                'participant': subject,
                'top_public_score': top,
                'evidence': 'leaderboard_observation_2026-10-09T201800Z.json',
                'rows_complete': False,
                'scope_and_limits': observation.get('scope_and_limits', []),
                'interpretation': 'Later dated public-board observation supersedes earlier rank snapshots. It is team-level and does not identify a TIFF or authenticate a score-to-file mapping.'})
    else:
        out = prior_observation
        out.update(source=BOARD, owner_best_reported=OUR_BEST,
                   artifact_score_authenticated=False,
                   note='Dated participant-level observation; no filename/hash/receipt attribution. Participant identity is not authenticated as the user\'s team.')
    policy = json.loads((ROOT / 'registry/source_policy.json').read_text())['drivendata']
    allowed = bool(policy.get('automated_fetch_allowed') and policy.get('written_permission_reference'))
    out['automated_fetch_allowed'] = allowed
    if not allowed:
        out['status'] = ('saved partial dated public-board observation; automated DrivenData access '
                        'disabled by Terms-of-Use policy')
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


def research_status():
    """Read the research card, not LATEST, and verify its exact published bytes.

    Hash identity preserves the previous on-disk validator result without importing
    scientific dependencies into the scheduled stdlib-only feed. Never promotes.
    """
    p = EV / 'ctd5_run_card.json'
    if not p.exists():
        return None
    card = json.loads(p.read_text())
    path = DL / card['raster_file']
    matches = path.is_file() and file_hash(path) == card['raster_sha256']
    if not matches:
        raise ValueError('CTD5 research download differs from its audited bytes')
    return dict(run_id=card['run_id'], file=card['raster_file'],
                download='downloads/ctd5-research.tif', sha256=card['raster_sha256'],
                hash_verified=matches, verdict=card['verdict'],
                approved_for_weekly_slot=False, submit_ok=False,
                measurement_utc=card['generated_utc'],
                note='Research only; local evidence refresh is not a fresh organizer or leaderboard observation.')


def h75_stop_is_current():
    """Fail closed when shared pages show the terminal H75 stop."""
    index = DOCS / 'index.html'
    status = DOCS / 'h75-executive-summary.html'
    if not index.is_file() or not status.is_file():
        return False
    home = index.read_text(errors='replace')
    page = status.read_text(errors='replace')
    return ('H75: DUPLICATE/STOP' in home
            and 'DUPLICATE/STOP · RESEARCH ONLY · NOT FOR SUBMISSION' in page
            and 'no owner override' in page.lower())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true', help='Only honored with recorded written permission; otherwise no DrivenData request.')
    parser.add_argument('--branch', help='Actual Actions ref, if Git is checked out detached.')
    args = parser.parse_args()
    copied = copy_evidence()
    DL.mkdir(parents=True, exist_ok=True)
    if h75_stop_is_current():
        board = fetch_board(args.fetch)
        write('leaderboard.json', board)
        inv = EV / 'prior_inventory_r2.json'
        entries = json.loads(inv.read_text()).get('entries', []) if inv.exists() else []
        latest_status = dict(
            round='H75', verdict='DUPLICATE/STOP · RESEARCH ONLY · NOT FOR SUBMISSION',
            status_page='h75-executive-summary.html',
            approved_for_submission=False, approved_for_weekly_slot=False,
            owner_override=False, rerun_allowed=False,
            note='H75 terminal stop is current; this feed run did not stage an artifact, create a ZIP, or change a submission pointer.')
        write('feed.json', dict(
            generated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            branch=current_branch(args.branch), repo='buffedlizard55-lab/GEMSDOE52',
            evidence_copied=copied, submission=None,
            downloads=len(list(DL.glob('*.tif'))),
            leaderboard_status=board['status'],
            leaderboard_last_observed_utc=board.get('fetched_utc') or board.get('observed_date_utc'),
            prior_entries=len(entries),
            eligible_prior_rasters=sum(bool(r.get('eligible_prior')) for r in entries),
            scientific_gate=False, slots_used=0, latest_research=latest_status,
            freshness_note='Local evidence refresh is automatic; the board is a dated observation, not a live feed. No portal upload or submission-pointer change.'))
        log('H75 terminal stop remains current; refreshed only local evidence/feed metadata. No TIFF, ZIP, pointer, or page was changed.')
        return 1 if board.get('fetch_error') else 0
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
    # H58 is an explicitly named research result, not the global incumbent unless a later
    # independent gate approves it. Publish its one-TIFF package and stable review aliases from
    # the H58 receipt without changing submission/LATEST.txt or docs/data/submission.json.
    h58_result_path = EV / 'h58_result.json'
    if h58_result_path.is_file():
        try:
            h58_name = str(json.loads(h58_result_path.read_text())['artifact']['file'])
        except (KeyError, ValueError, OSError):
            h58_name = ''
        if h58_name.startswith('gems52-h58-') and (ROOT / 'submission' / h58_name).is_file():
            archive_path = make_zip(h58_name)
            alias_pairs = [(DL / h58_name, DL / 'h58-candidate.tif')]
            if archive_path:
                alias_pairs.append((Path(archive_path), DL / 'h58-candidate.zip'))
            for source, alias in alias_pairs:
                if source.is_file() and (not alias.exists() or file_hash(source) != file_hash(alias)):
                    alias.write_bytes(source.read_bytes())
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
    board = fetch_board(args.fetch)
    write('submission.json', sub)
    write('leaderboard.json', board)
    inv = EV / 'prior_inventory_r2.json'
    entries = json.loads(inv.read_text()).get('entries', []) if inv.exists() else []
    write('feed.json', dict(
        generated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        branch=current_branch(args.branch), repo='buffedlizard55-lab/GEMSDOE52',
        evidence_copied=copied,
        files=sorted({p.name for pat in ('*_r[23]*.json', 'h55_*.json', 'h58_*.json',
                                         'submission_gems52-h55-*.json', 'submission_gems52-h58-*.json')
                      for p in DATA.glob(pat)}),
        submission=sub.get('file'), downloads=len(list(DL.glob('*.tif'))),
        leaderboard_status=board['status'],
        leaderboard_last_observed_utc=board.get('fetched_utc') or board.get('observed_date_utc'),
        prior_entries=len(entries), eligible_prior_rasters=sum(bool(r.get('eligible_prior')) for r in entries),
        scientific_gate=sub.get('approved_for_weekly_slot', False), slots_used=0,
        latest_research=research_status(),
        freshness_note='Local evidence refresh is automatic; the board is a dated snapshot. No automatic portal submission.'))
    log('Feed updated. ' + board['status'])
    return 1 if board.get('fetch_error') else 0


if __name__ == '__main__':
    sys.exit(main())
