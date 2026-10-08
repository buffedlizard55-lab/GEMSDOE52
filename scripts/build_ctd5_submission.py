#!/usr/bin/env python3
"""Publish a newly inferred CTD5 research TIFF; stop on lane duplication, never retune.

Prior rasters first enter here for forensic/duplicate checks, not as features,
labels, a retained core or an exclusion mask. This is deliberately separate from
run_ctd5.py so the data-flow restriction is easy to audit.
"""
from __future__ import annotations
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'scripts'))
import numpy as np
import rasterio
from scipy import ndimage as ndi
from gems52 import gates, nodes, submission_writer
from run_ctd5 import setup, write, WORK, INPUT, EVID, log


def priors():
    inventory = json.loads((EVID/'ctd5_prior_inventory.json').read_text())
    paths = [ROOT/r['local_path'] for r in inventory['entries'] if r.get('eligible')]
    excluded = []
    with rasterio.open(INPUT/'sample_submission.tif') as ref:
        for p in sorted((ROOT/'submission').glob('*.tif')):
            if 'ctd5-' in p.name:  # fixed-point rebuild; never compare a candidate to its own output
                continue
            with rasterio.open(p) as ds:
                if ds.count == 1 and (ds.shape, ds.crs, ds.transform) == (ref.shape, ref.crs, ref.transform):
                    paths.append(p)
                else:
                    excluded.append(str(p.relative_to(ROOT)))
    return paths, excluded


def dossiers(store, cat, a, b, emission, stem):
    domain = store.valid & ~cat
    a_only = domain & (a >= .95) & (b >= .35) & (b <= .65)
    components, n = ndi.label(a_only, np.ones((3,3), bool))
    objects = ndi.find_objects(components)
    cover = store.feature_grid('raw_band_15')
    grav = store.feature_grid('A_gravity_grad_3')
    slope = store.feature_grid('raw_band_19')
    dossier = EVID/(stem+'-a-only-segments.csv')
    fields = ['candidate_id','pixels','emitted_pixels','row','col','easting_m','northing_m',
              'mean_A_operating_rank','mean_B_operating_rank','mean_band15_native',
              'mean_gravity_gradient_native_per_m','mean_band19_native',
              'hypothesis','non_fault_mimic','falsifier','status']
    with dossier.open('w',newline='') as fh:
        writer=csv.DictWriter(fh,fieldnames=fields);writer.writeheader()
        for i,sl in enumerate(objects,1):
            if sl is None: continue
            selected=components[sl]==i
            yy,xx=np.nonzero(selected); yy=yy+sl[0].start; xx=xx+sl[1].start
            cy,cx=float(yy.mean()),float(xx.mean())
            writer.writerow(dict(candidate_id=f'CTD5-A-{i:05d}',pixels=len(yy),emitted_pixels=int((emission[yy,xx]>0).sum()),
                row=round(cy,3),col=round(cx,3),easting_m=round(243350+(cx+.5)*100,1),northing_m=round(4508550-(cy+.5)*100,1),
                mean_A_operating_rank=round(float(a[yy,xx].mean()),5),mean_B_operating_rank=round(float(b[yy,xx].mean()),5),
                mean_band15_native=round(float(cover[yy,xx].mean()),4),
                mean_gravity_gradient_native_per_m=round(float(grav[yy,xx].mean()),8),mean_band19_native=round(float(slope[yy,xx].mean()),4),
                hypothesis='Geophysical donor high and surface receiver abstains. A buried structural boundary is one hypothesis; native cover/gradient/slope measurements above are context, not proof.',
                non_fault_mimic='Basin-fill density boundary or volcanic lithologic contact; gravity and modelled cover may not be independent.',
                falsifier='Compare both sides in official high-resolution terrain/geologic mapping and field offset observations. A continuous unfaulted contact would weaken the fault interpretation.',
                status='Unverified candidate; no slip, permeability, temperature or geothermal resource established.'))
    pixels=EVID/(stem+'-emitted-pixels.csv')
    count=0;only_count=0
    with pixels.open('w',newline='') as fh:
        writer=csv.writer(fh)
        writer.writerow(['row','col','easting_m','northing_m','A_operating_rank','B_operating_rank','A_only_candidate_id','band15_native','gravity_gradient_native_per_m','band19_native','geological_reasoning','non_fault_mimic','falsifier'])
        for y,x in zip(*np.nonzero(emission>0)):
            cid=int(components[y,x]);count+=1;only_count+=int(cid>0)
            writer.writerow([int(y),int(x),243350+(int(x)+.5)*100,4508550-(int(y)+.5)*100,
                round(float(a[y,x]),5),round(float(b[y,x]),5),f'CTD5-A-{cid:05d}' if cid else '',
                round(float(cover[y,x]),4),round(float(grav[y,x]),8),round(float(slope[y,x]),4),
                ('A-only donor/abstainer: possible burial, not verified.' if cid else 'Moderate asymmetric disagreement, below the strict A-only donor/abstainer criterion; not verified.'),
                'Non-fault basin-fill density/lithologic contact; model and survey artifacts.',
                'Inspect high-resolution terrain and mapped contacts, then independent field offsets; no new field observation was made.'])
    return dict(a_only_segments=int(n),a_only_pool_pixels=int(a_only.sum()),emitted_reasoning_rows=count,
                emitted_a_only_rows=only_count,segment_csv=dossier.name,pixel_csv=pixels.name,
                every_a_only_segment_documented=True,every_emitted_pixel_documented=count==int((emission>0).sum()),
                units_warning='Band 15/19 native units not independently authenticated; UTM coordinates are metres. Operating ranks are not probabilities.')


def main():
    t0=time.monotonic()
    reg,store,cat=setup()
    exchange=json.loads((EVID/'ctd5_pseudo_exchange.json').read_text())
    if exchange['executed']:
        prefix='post_mosaic_'
        holdout=json.loads((EVID/'ctd5_post_holdout.json').read_text())
    else:
        if json.loads((EVID/'ctd5_independence.json').read_text())['allow_exchange']:
            raise SystemExit('Conditional exchange is pending; do not skip the registered stage.')
        prefix='mosaic_'
        holdout=json.loads((EVID/'ctd5_holdout.json').read_text())
    a=np.load(WORK/(prefix+'matched_A.npy'))
    b=np.load(WORK/(prefix+'single_B.npy'))
    surface=np.load(WORK/(prefix+'disagreement.npy'))
    paths,excluded=priors()
    surface_receipt=gates.lane_uniqueness_report(surface,store.valid,paths,
        sample=INPUT/'sample_submission.tif',phase='surface',log=log)
    write('surface_uniqueness',surface_receipt)
    if not surface_receipt['ok']:
        write('lane_stop',dict(phase='before placement',duplicate=surface_receipt['duplicate'],verdict='negative',
            message='STOP: no placement or retuning; surface failed lane gate.'))
        raise SystemExit('STOP before placement: surface lane gate failed')
    allowed=store.valid & ~cat & (surface>0)
    emitted=nodes.emit_nodes(surface,allowed,reg['global_budget'],min_px=3,log=log)
    decoded=hashlib.sha256(emitted.astype('<f4').tobytes()).hexdigest()
    stem='gems52-ctd5-cover-disagreement-20261008-a24c35d1-'+decoded[:10]
    file=ROOT/'submission'/(stem+'.tif')
    name='CTD5-cover-matched-disagreement-'+decoded[:10]
    note=('CTD5: cover-matched geophysics to surface abstention; one pseudo-label round. Research only; no prior pixels reused.'
          if exchange['executed'] else 'CTD5: OOF cover-matched disagreement; exchange disabled at independence gate. Research only; no prior pixels reused.')
    receipt=submission_writer.write_submission(file,emitted,INPUT/'sample_submission.tif',
        np.load(WORK/'features/input_footprint.npy'),name=name,note=note,
        metadata=dict(new_model_inference=True,prior_prediction_inputs=False,hypothesis='CTD5-H1',
                      prediction_source='buffered spatial out-of-fold mosaic',pseudo_rounds=exchange['rounds']))
    dot_receipt=gates.lane_uniqueness_report(emitted,store.valid,paths,
        sample=INPUT/'sample_submission.tif',phase='dots',log=log)
    write('dot_uniqueness',dot_receipt)
    if dot_receipt['duplicate']:
        write('lane_stop',dict(phase='final dots',duplicate=True,verdict='negative',
            message='STOP: final dots fail strict parallel-lane proximity/rank gate. Preserve negative artifact; no altered rerun.'))
    # This is an equality audit, not a new hypothesis/selection experiment.
    controls={}
    for label,f in [('A',a),('B',b),('union',np.maximum(a,b))]:
        controls[label]=nodes.emit_nodes(f,store.valid & ~cat,reg['global_budget'],min_px=3)
    relations=dict(surface_equals_maximum=bool(np.array_equal(surface,np.maximum(a,b))),
        dots_equal_union_field=bool(np.array_equal(emitted,controls['union'])),
        dots_equal_set_union=bool(np.array_equal(emitted>0,(controls['A']>0)|(controls['B']>0))),
        dots_equal_view_A=bool(np.array_equal(emitted,controls['A'])),dots_equal_view_B=bool(np.array_equal(emitted,controls['B'])),
        candidate_vs_union_field_different_pixels=int(np.count_nonzero(emitted!=controls['union'])))
    del controls
    write('not_union',relations)
    reasoning=dossiers(store,cat,a,b,emitted,stem)
    write('reasoning',reasoning)
    best=holdout['best_comparable_control']
    delta=holdout['paired_differences'][best]
    model_gate=delta['delta']>=.005 and delta['ci95'][0]>0
    budget_complete=holdout.get('all_candidate_budgets_complete',holdout.get('all_budgets_complete',False))
    blockers=[]
    if not model_gate: blockers.append('candidate did not beat the strongest comparable control with registered lift and paired CI')
    if not budget_complete: blockers.append('one or more holdout candidate folds could not fill their fixed dot budget')
    if int((emitted>0).sum()) != reg['global_budget']: blockers.append('final positive-support capacity below registered budget')
    if not dot_receipt['ok']: blockers.append('strict parallel-lane duplicate/inventory gate failed')
    blockers += ['owner-mirror inputs are not organizer-authenticated','private/release/external registry coverage unknown','no separate selector decision or current weekly-cap receipt']
    card=dict(run_id=reg['run_id'],generated_utc=datetime.now(timezone.utc).isoformat(),
        hypothesis='CTD5-H1: cover-matched geophysical-to-surface-abstention transfer',
        mechanism='Training-only cover-stratified class weights; one whole-component confident-to-abstaining exchange; asymmetric OOF disagreement; 3px sparse placement.',
        named_non_fault_process='Non-fault basin-fill density boundary or volcanic lithologic contact.',
        holdout_dti=holdout['scores']['disagreement'],best_comparable_control=dict(name=best,**holdout['scores'][best]),
        paired_delta_vs_best=delta,holdout_budgets_complete=budget_complete,
        matched_budget_comparison_valid=budget_complete,
        comparison_warning='Descriptive HOLDOUT-DTI only: a candidate fold missed its budget. Best control means best evaluated control, not a valid matched-budget win.' if not budget_complete else None,
        correlation_overlap_vs_registry=dict(priors_checked=dot_receipt['priors_checked'],distinct_decoded_priors=dot_receipt['distinct_decoded_priors'],
            surface_max_spearman=surface_receipt['max_spearman'],final_max_spearman=dot_receipt['max_spearman'],
            final_max_near_3px_fraction=dot_receipt['max_near_3px_fraction'],lane_gate_pass=dot_receipt['ok'],
            decoded_identical_priors=sum(r.get('identical',False) for r in dot_receipt['per_prior']),
            scope=dot_receipt['scope']),
        raster_sha256=receipt['sha256'],raster_file=receipt['file'],validator_output=receipt['validator'],
        submission_name=name,note=note,note_chars=len(note),verdict='negative',
        download_ok=True,submit_ok=False,approved_for_weekly_slot=False,submission_slots_used=0,
        reasons=blockers,not_union=relations,reasoning=reasoning,
        experiment_count=2 if exchange['executed'] else 1,
        experiment_count_note='Conservative count: baseline and single predeclared exchange; one geological hypothesis, no post-result tuning.',
        independent_method_error_gate=json.loads((EVID/'ctd5_independence.json').read_text())['max_abs_correlation'],
        excluded_local_malformed_priors=excluded,post_build_seconds=time.monotonic()-t0)
    write('run_card',card)
    write('submission',receipt)
    downloads=ROOT/'docs/downloads';downloads.mkdir(exist_ok=True)
    for p in [file,file.with_suffix('.zip')]:
        shutil.copy2(p,downloads/p.name)
    shutil.copy2(file,downloads/'ctd5-research.tif')
    shutil.copy2(file.with_suffix('.zip'),downloads/'ctd5-research.zip')
    for key in ('segment_csv','pixel_csv'):
        shutil.copy2(EVID/reasoning[key],downloads/reasoning[key])
    (ROOT/'submission/CTD5_RESEARCH_LATEST.txt').write_text(file.name+'\n')
    # Do not move submission/LATEST.txt, a separate historical selector pointer.
    for p in EVID.glob('ctd5_*.json'):
        if p.stat().st_size<3_000_000:
            shutil.copy2(p,ROOT/'docs/data'/p.name)
    log('PUBLISHED',file.name,'sha256',receipt['sha256'],'VERDICT negative; DO NOT SUBMIT')

if __name__=='__main__': main()
