#!/usr/bin/env python3
"""H87-P frozen A-only upward-continuation persistence gate; research-only if gates fail.

Uses H61 shared cached view models/whole-segment exchange, not a private evaluator or writer.
Usage: PYTHONPATH=src .venv/bin/python scripts/run_h87.py
"""
from __future__ import annotations
import csv
import gzip
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi
from scipy.stats import rankdata
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
import run_h61 as base
from gems52 import evaluate_holdout as evaluator, nodes, gates, submission_writer

DOC = ROOT / 'knowledge/80_h87_hypotheses_preregistered.md'
PIN = '066acdc45201c2edf457c7f5f2849fe1eaa29cc831c5b279937007fd8982f97f'
EVID = ROOT / 'evidence'
DOWN = ROOT / 'docs/downloads'
SAMPLE = ROOT / 'data/sample_submission.tif'
NAME = 'gems52-h87-deepedge-Aonly-37600px-20261010'
NOTE = 'H87 deep magnetic edge A-only, surface abstention; research-only, negative holdout; no slot approved'
K_FOLD = 9400

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def rank(x):
    return ((rankdata(x, method='average') - 0.5) / len(x)).astype('float32')

def summary(report):
    rows = report['per_prior']
    def rel(path):
        return str(Path(path).relative_to(ROOT)) if Path(path).is_relative_to(ROOT) else str(path)
    ranks = sorted(((r['spearman'], rel(r['path'])) for r in rows if r.get('spearman') is not None), reverse=True)
    near = sorted(((r['near_3px_fraction'], rel(r['path'])) for r in rows if r.get('near_3px_fraction') is not None), reverse=True)
    offenders = []
    for r in rows:
        if r.get('rank_duplicate') or r.get('near_duplicate') or r.get('error'):
            row = {k:r.get(k) for k in ('path','spearman','near_3px_fraction','rank_duplicate','near_duplicate','error')}
            row['path'] = rel(row['path'])
            offenders.append(row)
    return {k: v for k, v in report.items() if k != 'per_prior'} | {'worst_rank': ranks[:3], 'worst_near': near[:3],
            'offenders': offenders}

def main():
    if sha(DOC) != PIN:
        raise SystemExit('preregistration changed: refuse to run')
    can = json.loads((EVID / 'h61_canary.json').read_text())
    ex = json.loads((EVID / 'h61_pseudo_exchange.json').read_text())
    if can['any_alarm'] or can['max_fitted_top5_heldout_auc'] > 0.90:
        raise SystemExit('single-feature leakage canary >0.90: STOP')
    if not ex['independence_pre']['allow_exchange'] or not ex['allowed_exchange']:
        raise SystemExit('negative-block independence not supported: STOP')
    reg, store, cat, eligible, folds, va, vb, collar = base.setup()
    if ex['independence_pre']['max_abs_correlation'] >= 0.60:
        raise SystemExit('strongly correlated error: STOP')
    mag = store.feature_grid('X_mag_TMI_up150_grad3')
    stitched = np.zeros(cat.shape, np.float32)
    stitched_a = np.zeros(cat.shape, np.float32)
    stitched_b = np.zeros(cat.shape, np.float32)
    st_deep = np.zeros(cat.shape, np.float32)
    terms = {a: None for a in ('h87_persistence', 'single_B', 'raw_disagreement', 'union_max')}
    fold_rows = []
    for fold in folds:
        f = fold['fold']
        allowed = fold['region'] & eligible & ~fold['visible'] & (ndi.distance_transform_edt(~fold['visible']) > collar)
        ids = np.flatnonzero(allowed.ravel())
        preds = {}
        for stage in ('pre', 'post'):
            for v in ('A','B'):
                p = np.load(base.WORK / f'pred_{stage}_{v}_f{f}.npy', allow_pickle=False)
                if p.shape != (len(store.flat_idx),) or not np.isfinite(p).all() or p.min() < 0 or p.max() > 1:
                    raise SystemExit(f'prediction cache invalid: {stage} {v} fold {f}')
                preds[stage, v] = p
        rr = {v: rank(preds['post',v][store.inverse[ids]]) for v in ('A','B')}
        deep = rank(mag.ravel()[ids])
        # Novel physically constrained A-only stratum, never the A/B union.
        score = np.maximum(0., rr['A'] - rr['B']) * (0.5 + 0.5 * deep)
        stitched.ravel()[ids] = score
        stitched_a.ravel()[ids] = rr['A']; stitched_b.ravel()[ids] = rr['B']
        st_deep.ravel()[ids] = deep
        fields = {'h87_persistence': score,
                  'single_B': rank(preds['pre','B'][store.inverse[ids]]),
                  'raw_disagreement': rr['A'] - rr['B'],
                  'union_max': np.maximum(rr['A'], rr['B'])}
        record = {'fold': f, 'allowed_px':len(ids), 'truth_px':int(fold['truth'].sum()), 'arms':{}}
        for arm, vec in fields.items():
            arr = np.zeros(cat.shape, np.float32)
            arr.ravel()[ids] = vec
            placed = nodes.spacing_select(arr, allowed, K_FOLD, min_px=3.)
            if placed.sum() != K_FOLD:
                raise SystemExit(f'budget short-filled: fold {f} {arm}')
            result, term = evaluator.evaluate(placed.astype('float32'), fold, eligible, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            record['arms'][arm] = result
            print(f'fold {f} {arm}: HOLDOUT-DTI {result["dti"]:.6f} ({K_FOLD} placed)', flush=True)
        fold_rows.append(record)
    pooled = evaluator.pooled_summary(terms, draws=1000, seed=61052, candidate='h87_persistence')
    (EVID / 'h87_holdout.json').write_text(json.dumps({'pooled':pooled, 'folds':fold_rows,
       'canary_max_single_feature_auc': can['max_alarm_across_folds'],
       'independence_max_abs_rho':ex['independence_pre']['max_abs_correlation'],
       'pseudo_pixels':ex['total_pseudo_pixels'], 'preregistration_sha256':PIN}, indent=2, allow_nan=False)+'\n')
    print('HOLDOUT-DTI pooled', json.dumps(pooled['scores']), flush=True)
    # Supply every restored census blob plus local predecessors. The census is fail-closed.
    receipt = json.loads((ROOT / 'work/h61/prior_fetch_receipt.json').read_text())
    if receipt['n_errors'] or receipt['n_entries'] != receipt['n_present'] + receipt['n_fetched']:
        raise SystemExit('prior census incomplete: STOP')
    priors = [ROOT / v['dest'] for v in receipt['files'].values() if v.get('eligible')]
    priors += gates.find_priors([ROOT/'docs/downloads',ROOT/'submission'], exclude=DOWN/(NAME+'.tif'))
    priors = sorted(set(priors))
    if not priors or any(not p.exists() for p in priors):
        raise SystemExit('prior inventory inaccessible: STOP')
    # Surface gate BEFORE metric-aware placement, not merely on the dotted product.
    surface = np.zeros_like(stitched)
    surface[eligible] = stitched[eligible]
    s_gate = gates.lane_uniqueness_report(surface, eligible, priors, sample=SAMPLE, phase='surface')
    (EVID/'h87_surface_gate.json').write_text(json.dumps(s_gate, indent=1, allow_nan=False)+'\n')
    print('surface gate', summary(s_gate)['max_spearman'], 'duplicate', s_gate['duplicate'], flush=True)
    if s_gate['duplicate'] or s_gate['error_count']:
        raise SystemExit('surface DUPLICATE/STOP; no placement or TIF')
    # Final placement is wholly blind to withheld labels. All visible labels are now excluded.
    allowed = eligible & ~cat & (ndi.distance_transform_edt(~cat) > collar)
    dots = nodes.spacing_select(stitched, allowed, 37600, min_px=3.).astype(np.float32)
    if int(dots.sum()) != 37600 or np.any(dots[cat]) or np.any(dots[~eligible]):
        raise SystemExit('invalid final dot placement')
    path = DOWN/(NAME+'.tif')
    DOWN.mkdir(parents=True, exist_ok=True)
    writer = submission_writer.write_submission(path, dots, SAMPLE, eligible, name=NAME, note=NOTE,
        metadata={'hypothesis':'H87-P upward-continued magnetic persistence in A-only disagreement',
                  'preregistration_sha256':PIN, 'no_competition_slot_used':True})
    d_gate = gates.lane_uniqueness_report(dots, eligible, priors, sample=SAMPLE, phase='dots')
    (EVID/'h87_dots_gate.json').write_text(json.dumps(d_gate, indent=1, allow_nan=False)+'\n')
    # Geological explanation is an *interpretation*, not individual geological confirmation.
    reasons = DOWN/'h87-a-only-reasoning.csv.gz'
    with gzip.open(reasons,'wt',newline='') as fh:
        w=csv.writer(fh)
        w.writerow(['row','col','A_rank','B_rank','up150_grad3_rank','reason','named_nonfault_mimic','verified_fault'])
        for y,x in np.argwhere(dots > 0):
            w.writerow([int(y),int(x),round(float(stitched_a[y,x]),6),round(float(stitched_b[y,x]),6),
                round(float(st_deep[y,x]),6),
                'Candidate buried structure: geophysical learner outranks surface learner; 150 m upward-continued magnetic gradient is a ranking weight (its percentile is recorded, not necessarily high). Field validation required.',
                'intrusive dike or non-fault lithologic contact', 'no'])
    idx=np.flatnonzero(allowed.ravel())
    not_union={'surface_differs_from_union_pixels':int(np.count_nonzero(
        stitched.ravel()[idx] != np.maximum(stitched_a.ravel()[idx], stitched_b.ravel()[idx]))),
        'A_only_dots':int(np.sum((dots>0)&(stitched_a>stitched_b))),
        'consensus_dots':int(np.sum((dots>0)&(stitched_a<=stitched_b)))}
    concise = {'hypothesis':'H87-P A-only deep magnetic-edge persistence under muted surface expression',
      'mechanism':'Visible-only segment co-training then upward-continued gradient gates A minus B rank; 3 px nodes',
      'non_fault_mimic':'intrusive dike or lithologic contact',
      'holdout_dti':pooled['scores']['h87_persistence'],
      'vs_single_B':pooled['paired_differences']['single_B'],
      'evaluator_version':evaluator.VERSION,
      'canary_max_auc':can['max_alarm_across_folds'],
      'independence_max_abs_rho':ex['independence_pre']['max_abs_correlation'],
      'pseudo_pixels':ex['total_pseudo_pixels'],
      'surface_gate':summary(s_gate), 'final_dots_gate':summary(d_gate),
      'not_union':not_union,
      'raster_sha256':sha(path), 'validator':writer['validator'],
      'submission_name':NAME, 'note':NOTE, 'reasoning_csv_gz':str(reasons.relative_to(ROOT)),
      'exact_unique_vs_accessible_registry':not any(r.get('identical') for r in d_gate['per_prior']),
      'verdict':'negative', 'download_ok':True, 'submit_ok':False, 'competition_slots_used':0,
      'reason':'No promotion until holdout exceeds comparable best and literal surface/dot lane gates pass; literal duplicate is STOP',
      'source_provenance':'SHA-pinned owner mirrors; not independently organizer authenticated'}
    (EVID/'h87_run_card.json').write_text(json.dumps(concise, indent=2, allow_nan=False)+'\n')
    print('final',path, 'sha256',sha(path),'dots duplicate',d_gate['duplicate'],'STOP',flush=True)

if __name__ == '__main__':
    main()
