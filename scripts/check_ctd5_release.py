#!/usr/bin/env python3
"""Independent CTD5 release checks from committed bytes; never fits or selects."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import rasterio
from scipy.spatial import cKDTree
from gems52 import evaluate_holdout as evaluator


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def check(base_url=None):
    card=json.loads((ROOT/'evidence/ctd5_run_card.json').read_text())
    public=json.loads((ROOT/'docs/data/ctd5_run_card.json').read_text())
    assert card==public,'public run card differs from evidence'
    assert card['download_ok'] and not card['submit_ok'] and card['verdict']=='negative'
    assert card['approved_for_weekly_slot'] is False and card['submission_slots_used']==0
    assert card['experiment_count']<=3
    assert len(card['note'])==card['note_chars']<=140
    assert not card['matched_budget_comparison_valid']
    canonical=ROOT/'submission'/card['raster_file']
    paths=[canonical,ROOT/'docs/downloads'/card['raster_file'],ROOT/'docs/downloads/ctd5-research.tif']
    for p in paths: assert sha(p)==card['raster_sha256'],str(p)
    for p in [canonical.with_suffix('.zip'),paths[1].with_suffix('.zip'),ROOT/'docs/downloads/ctd5-research.zip']:
        with zipfile.ZipFile(p) as z:
            assert z.namelist()==[canonical.name] and z.read(canonical.name)==canonical.read_bytes()
            assert z.testzip() is None
    with rasterio.open(canonical) as ds:
        a=ds.read(1)
        assert ds.count==1 and ds.dtypes==('float32',) and ds.nodata is None
        assert ds.crs.to_epsg()==32611 and ds.shape==(3730,3292)
        assert tuple(ds.transform)[:6]==(100.,0.,243350.,0.,-100.,4508550.)
        grid=(ds.shape,ds.crs,ds.transform)
    assert np.isfinite(a).all() and np.all((a==0)|(a==1))
    assert np.count_nonzero(a)==12000
    meta=json.loads((ROOT/'evidence/ctd5_masks.json').read_text())
    maskfile=ROOT/meta['path'];assert sha(maskfile)==meta['sha256']
    with np.load(maskfile,allow_pickle=False) as masks:
        shape=tuple(masks['shape']);n=int(np.prod(shape))
        footprint=np.unpackbits(masks['footprint'],count=n).reshape(shape).astype(bool)
        eligible=np.unpackbits(masks['eligible'],count=n).reshape(shape).astype(bool)
    assert shape==a.shape and not np.any((a>0)&~footprint) and not np.any((a>0)&~eligible)
    xy=np.column_stack(np.nonzero(a>0))
    dist,_=cKDTree(xy).query(xy,k=2)
    assert dist[:,1].min()>=3
    sample=ROOT/'data/sample_submission.tif'
    if sample.exists():
        with rasterio.open(sample) as ds: assert (ds.shape,ds.crs,ds.transform)==grid
    labels=ROOT/'data/labels.tif'
    if labels.exists():
        with rasterio.open(labels) as ds: assert not np.any((a>0)&(ds.read(1)==1))
    counts={}
    for key in ('segment_csv','pixel_csv'):
        path=ROOT/'evidence'/card['reasoning'][key]
        assert path.read_bytes()==(ROOT/'docs/downloads'/path.name).read_bytes()
        with path.open(newline='') as f:
            rows=list(csv.DictReader(f))
        counts[key]=len(rows)
        for row in rows:
            assert row['non_fault_mimic'] and row['falsifier']
            assert row.get('hypothesis') or row.get('geological_reasoning')
        if key=='pixel_csv':
            coords={(int(r['row']),int(r['col'])) for r in rows}
            assert len(coords)==12000 and coords==set(map(tuple,xy.tolist()))
            assert sum(bool(r['A_only_candidate_id']) for r in rows)==card['reasoning']['emitted_a_only_rows']
    assert counts['segment_csv']==card['reasoning']['a_only_segments']
    assert counts['pixel_csv']==card['reasoning']['emitted_reasoning_rows']
    reg=json.loads((ROOT/'registry/ctd5_preregistration.json').read_text())
    assert sha(ROOT/reg['hypothesis_document'])==reg['hypothesis_sha256']
    assert card['raster_file']!=(ROOT/'submission/LATEST.txt').read_text().strip()
    assert (ROOT/'submission/CTD5_RESEARCH_LATEST.txt').read_text().strip()==card['raster_file']
    for phase in ('surface','dot'):
        gate=json.loads((ROOT/f'evidence/ctd5_{phase}_uniqueness.json').read_text())
        assert gate['priors_checked']==len(gate['per_prior']) and gate['priors_checked']>=524 and gate['error_count']==0
        assert gate['exact_full_eligible_rank'] and gate['rank_pixels']==int(eligible.sum())
        offenders=[r for r in gate['per_prior'] if r.get('spearman') is not None and r['spearman']>.90 or r.get('near_3px_fraction',0)>.70 or r.get('identical')]
        assert gate['duplicate']==bool(offenders)
        if phase=='dot': assert offenders and not gate['ok']
        else: assert not offenders and gate['ok']
    if card.get('supplemental_upstream_registry_check'):
        extra=json.loads((ROOT/card['supplemental_upstream_registry_check']['receipt']).read_text())
        assert extra['candidate_sha256']==card['raster_sha256']
        assert extra['no_refit'] and extra['no_new_placement'] and extra['original_duplicate_stop_retained']
        old=json.loads((ROOT/'evidence/ctd5_dot_uniqueness.json').read_text())
        new_hash=extra['dots']['per_prior'][0]['decoded_sha256']
        assert new_hash not in {r['decoded_sha256'] for r in old['per_prior']}
        assert card['supplemental_upstream_registry_check']['total_files_checked_at_closure']==old['priors_checked']+1
    for key,value in card['not_union'].items():
        if key!='candidate_vs_union_field_different_pixels': assert value is False
    post=json.loads((ROOT/'evidence/ctd5_post_holdout.json').read_text())
    assert post['scores']['disagreement']==card['holdout_dti']
    total=np.zeros(4)
    for f in post['folds']:
        total+=np.array([f['tpw'],f['fpw'],f['fnw'],f['n_truth']])
        assert f['budget_complete']==(f['target_budget']==f['emitted'])
    assert np.isclose(float(evaluator.from_terms(total)),post['scores']['disagreement']['dti'],rtol=1e-12,atol=1e-14)
    assert total[3]==card['holdout_dti']['withheld_positive_pixels']==53186
    assert not all(f['budget_complete'] for f in post['folds'])
    for name in ('index.html','executive-summary.html','ctd5-audit.html'):
        text=(ROOT/'docs'/name).read_text()
        assert 'DO NOT SUBMIT' in text
        if name!='executive-summary.html':
            assert 'HOLDOUT-DTI' in text
    served=[]
    if base_url:
        for rel,local in [('downloads/ctd5-research.tif',paths[-1]),('downloads/ctd5-research.zip',ROOT/'docs/downloads/ctd5-research.zip'),('data/ctd5_run_card.json',ROOT/'docs/data/ctd5_run_card.json')]:
            with urllib.request.urlopen(base_url.rstrip('/')+'/'+rel,timeout=20) as r:
                payload=r.read();ctype=r.headers.get('Content-Type')
            assert payload==local.read_bytes(),rel
            served.append(dict(path=rel,bytes=len(payload),content_type=ctype,sha256=hashlib.sha256(payload).hexdigest()))
    return dict(ok=True,sha256=card['raster_sha256'],rows=counts,
        bands=1,crs='EPSG:32611',shape=[3730,3292],transform=[100,0,243350,0,-100,4508550],
        finite_inside_footprint=True,finite_everywhere=True,min=0.,max=1.,grid_matches_template=True,
        positive_pixels=12000,positive_outside_footprint=0,min_dot_spacing_px=float(dist[:,1].min()),
        served=served,verdict='negative',submit_ok=False,
        note='Local independent byte/receipt checks; no organizer or geological acceptance inferred.')


def main():
    p=argparse.ArgumentParser();p.add_argument('--base-url');p.add_argument('--receipt');a=p.parse_args()
    r=check(a.base_url)
    if a.receipt: Path(a.receipt).write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(r,indent=2))

if __name__=='__main__': main()
