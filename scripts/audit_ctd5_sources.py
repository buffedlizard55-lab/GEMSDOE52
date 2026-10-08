#!/usr/bin/env python3
"""Bounded GitHub-source audit of every supplied owner site; never scrape the portal.

Reuses the template's site list/parser. Prediction rasters are learning/duplicate
comparators ONLY. Immutable source blobs are not evidence of deployed HTTP behavior,
and owner prose is not an ORGANIZER-CONFIRMED submission receipt.
"""
from __future__ import annotations
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from review_sources import SITE_PATHS, Extract

WORK = ROOT / 'work/ctd5/sources'
PRIORS = ROOT / 'work/ctd5/priors'

def gh_json(endpoint):
    p = subprocess.run(['gh', 'api', endpoint], capture_output=True, timeout=90)
    if p.returncode:
        raise RuntimeError(p.stderr.decode()[:350])
    return json.loads(p.stdout)

def blob(repo, sha, dest, expected=None):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        tmp = dest.with_suffix(dest.suffix + '.partial')
        with tmp.open('wb') as f:
            p = subprocess.run(['gh', 'api', f'repos/{repo}/git/blobs/{sha}',
                                '-H', 'Accept: application/vnd.github.raw'],
                               stdout=f, stderr=subprocess.PIPE, timeout=180)
        if p.returncode:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(p.stderr.decode()[:350])
        tmp.replace(dest)
    b = dest.read_bytes()
    if expected is not None and len(b) != expected:
        raise ValueError(f'blob size mismatch: {dest}')
    measured = hashlib.sha1(b'blob ' + str(len(b)).encode() + b'\0' + b).hexdigest()
    if measured != sha:
        raise ValueError(f'immutable Git blob hash mismatch: {dest}')
    return b

def site(pair):
    short, page = pair
    repo = 'buffedlizard55-lab/' + short
    row = dict(repository=repo, supplied_url=f'https://buffedlizard55-lab.github.io/{short}/{page}',
               source_class='owner source, NOT organizer-confirmed', deployed_http_verified=False)
    try:
        cache = WORK / (short + '-tree.json')
        if cache.exists():
            tree = json.loads(cache.read_text())
        else:
            tree = gh_json(f'repos/{repo}/git/trees/main?recursive=1')
            cache.write_text(json.dumps(tree))
        if tree.get('truncated'):
            raise ValueError('truncated Git tree')
        row['commit'] = tree['sha']
        entries = {x['path']: x for x in tree['tree'] if x['type'] == 'blob'}
        requested = page or 'index.html'
        if requested.endswith('/'):
            requested += 'index.html'
        page_paths = [p for p in [requested, 'index.html', 'docs/index.html'] if p in entries]
        row['pages'] = []
        for path in dict.fromkeys(page_paths):
            x = entries[path]
            text = blob(repo, x['sha'], WORK / (short + '-' + path.replace('/', '_')), x['size']).decode('utf8', 'replace')
            parser = Extract(); parser.feed(text)
            plain = '\n'.join(''.join(parser.parts).splitlines())
            import re
            row['pages'].append(dict(path=path, blob=x['sha'],
                source_url=f'https://github.com/{repo}/blob/{tree["sha"]}/{path}',
                title=(re.search(r'<title[^>]*>(.*?)</title>', text, re.I | re.S).group(1)
                       if re.search(r'<title[^>]*>(.*?)</title>', text, re.I | re.S) else ''),
                score_excerpts=[s.strip()[:500] for s in plain.splitlines() if re.search(r'0\.\d{4}\b', s)][:8]))
        priors = []
        for p, x in entries.items():
            if p.lower().endswith(('.tif', '.tiff')) and (
                p.startswith(('docs/', 'submission/', 'artifacts/', 'outputs/', 'predictions/',
                              'downloads/', 'results/', 'releases/', 'deliverables/'))
                or ('/' not in p and any(t in p.lower() for t in ('gems', 'submission', 'prediction', 'candidate', 'ensemble')))):
                priors.append(dict(repo=repo, commit=tree['sha'], path=p, blob=x['sha'], bytes=x['size']))
        row['prediction_paths'] = len(priors)
        row['status'] = 'source_read'
        print(short, len(priors), 'candidate TIFF paths', flush=True)
        return row, priors
    except Exception as exc:
        row.update(status='unavailable', error=str(exc))
        print(short, row['error'], flush=True)
        return row, []

def download(group):
    import rasterio
    sha, aliases = group
    r = aliases[0]
    result = dict(blob=sha, aliases=aliases)
    dest = PRIORS / (sha + '.tif')
    try:
        if r['bytes'] > 60_000_000:
            raise ValueError('over 60 MB per-file audit bound; not silently considered checked')
        body = blob(r['repo'], sha, dest, r['bytes'])
        result.update(local_path=str(dest.relative_to(ROOT)), sha256=hashlib.sha256(body).hexdigest())
        with rasterio.open(dest) as ds:
            result.update(shape=list(ds.shape), crs=str(ds.crs), transform=list(ds.transform)[:6], bands=ds.count)
            result['eligible'] = (ds.count == 1 and ds.shape == (3730, 3292)
                and ds.crs is not None and ds.crs.to_epsg() == 32611
                and tuple(ds.transform)[:6] == (100., 0., 243350., 0., -100., 4508550.))
            if not result['eligible']:
                result['exclusion'] = 'not an aligned single-band prediction'
    except Exception as exc:
        result.update(eligible=False, error=str(exc))
    return result

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--restore-frozen', action='store_true', help='restore immutable inventory blobs, without discovering new priors or changing evidence')
    args = parser.parse_args()
    if args.restore_frozen:
        original = json.loads((ROOT/'evidence/ctd5_prior_inventory.json').read_text())
        groups = [(r['blob'], r['aliases']) for r in original['entries']]
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(download, groups))
        expected = {r['blob']: r for r in original['entries']}
        errors = [r for r in rows if r.get('error') or r.get('sha256') != expected[r['blob']].get('sha256')]
        print('Frozen registry restore:', len(rows), 'blobs;', len(errors), 'errors', flush=True)
        if errors:
            raise SystemExit('Frozen inventory byte verification failed')
        return
    WORK.mkdir(parents=True, exist_ok=True)
    PRIORS.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(site, SITE_PATHS))
    groups = {}
    for _, rows in results:
        for r in rows:
            groups.setdefault(r['blob'], []).append(r)
    report = dict(generated_utc=datetime.now(timezone.utc).isoformat(),
        scope='All supplied owner repository main trees; source not deployed HTTP; no release/private/unlinked external storage audit.',
        unavailable_unspecified_sites=['53GEMSDOE (no supplied URL)', '54GEMSDOE (no supplied URL)'],
        sites=[r for r, _ in results], unique_git_blobs=len(groups),
        organizer_confirmed_scores=[], network_policy='Only allowed GitHub API; no automated DrivenData access.')
    out = ROOT / 'evidence/ctd5_sources.json'
    out.write_text(json.dumps(report, indent=2) + '\n')
    print('Downloading', len(groups), 'distinct Git blobs', flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(download, groups.items()))
    inventory = dict(generated_utc=datetime.now(timezone.utc).isoformat(),
        scope=report['scope'], entries=rows,
        eligible_count=sum(r.get('eligible', False) for r in rows),
        errors=sum('error' in r for r in rows))
    (ROOT / 'evidence/ctd5_prior_inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
    print('DONE:', inventory['eligible_count'], 'aligned priors;', inventory['errors'], 'errors', flush=True)

if __name__ == '__main__':
    main()
