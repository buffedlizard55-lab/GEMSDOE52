#!/usr/bin/env python3
"""Frozen cover-matched disagreement experiment. Never uploads or selects a slot."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault('OMP_NUM_THREADS', '2')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import numpy as np
import rasterio
from scipy import ndimage as ndi
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from threadpoolctl import threadpool_limits
from gems52 import spatial, nodes, gates, evaluate_holdout as evaluator
from gems52.structural import FeatureStore, digest

WORK = ROOT / 'work/ctd5'
INPUT = WORK / 'input'
EVID = ROOT / 'evidence'
SEED = 520810
ARMS = ['single_A', 'matched_A', 'single_B', 'union', 'disagreement']


def log(*args, **kwargs):
    print(*args, flush=True)


def write(name, obj):
    p = EVID / ('ctd5_' + name + '.json')
    p.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')
    return p


def setup():
    reg = json.loads((ROOT / 'registry/ctd5_preregistration.json').read_text())
    if digest(ROOT / reg['hypothesis_document']) != reg['hypothesis_sha256']:
        raise ValueError('preregistered hypothesis document changed')
    pins = {f['id']: f for f in json.loads((ROOT / 'registry/data_manifest.json').read_text())['files']}
    for key in ('training_features', 'labels', 'sample_submission'):
        f = pins[key]
        if digest(INPUT / f['dest']) != f['sha256']:
            raise ValueError('input pin mismatch: ' + f['id'])
    store = FeatureStore(WORK / 'features')
    if store.manifest['inputs']['features_sha256'] != digest(INPUT / 'training_features.tif'):
        raise ValueError('stale feature cache')
    if store.manifest['version'] != 'structural-core-v2-band6-B':
        raise ValueError('uncorrected band-6 view split')
    with rasterio.open(INPUT / 'labels.tif') as ds, rasterio.open(INPUT / 'sample_submission.tif') as ref:
        if (ds.shape, ds.crs, ds.transform) != (ref.shape, ref.crs, ref.transform):
            raise ValueError('labels grid mismatch')
        cat = ds.read(1) == 1
    if not set(store.manifest['view_A']).isdisjoint(store.manifest['view_B']):
        raise ValueError('cross-view feature overlap')
    if 'raw_band_06' not in store.manifest['view_B']:
        raise ValueError('band 6 is not isolated in B')
    return reg, store, cat


def sample_train(fold, cat, seed, max_pos=20000, max_neg=60000):
    rng = np.random.default_rng(seed)
    pos = np.flatnonzero((fold['train'] & fold['visible']).ravel())
    # ONLY the visible catalogue controls training negative clearance.
    visible_distance = ndi.distance_transform_edt(~fold['visible'])
    neg = np.flatnonzero((fold['train'] & ~fold['visible'] & (visible_distance > 5)).ravel())
    del visible_distance
    pos = rng.choice(pos, min(max_pos, len(pos)), replace=False)
    neg = rng.choice(neg, min(max_neg, len(neg)), replace=False)
    if min(len(pos), len(neg)) < 100:
        raise ValueError('insufficient training classes')
    rows = np.concatenate([pos, neg])
    y = np.concatenate([np.ones(len(pos), np.int8), np.zeros(len(neg), np.int8)])
    order = rng.permutation(len(rows))
    return rows[order], y[order]


def sample_test(fold, cat, seed, max_neg=40000):
    rng = np.random.default_rng(seed)
    pos = np.flatnonzero(fold['truth'].ravel())
    distance = ndi.distance_transform_edt(~cat)
    neg = np.flatnonzero((fold['region'] & ~cat & (distance > 5)).ravel())
    del distance
    neg = rng.choice(neg, min(max_neg, len(neg)), replace=False)
    return np.concatenate([pos, neg]), np.concatenate([np.ones(len(pos), np.int8), np.zeros(len(neg), np.int8)])


def learner(seed, canary=False):
    return HistGradientBoostingClassifier(max_iter=30 if canary else 90, learning_rate=.08,
        max_leaf_nodes=4 if canary else 15, min_samples_leaf=40, l2_regularization=2,
        early_stopping=False, random_state=seed)


def balance_weights(y, cover=None):
    if cover is None:
        strata = np.zeros(len(y), np.int8)
        cuts = []
    else:
        cuts = np.unique(np.quantile(cover, [.25, .5, .75])).tolist()
        strata = np.searchsorted(cuts, cover, side='right')
    w = np.zeros(len(y), float)
    rows = []
    for b in np.unique(strata):
        for cls in (0, 1):
            m = (strata == b) & (y == cls)
            if not m.any():
                raise ValueError('cover stratum is missing one class')
            w[m] = len(y) / (2 * len(np.unique(strata)) * int(m.sum()))
            rows.append(dict(stratum=int(b), label=cls, pixels=int(m.sum()), weight=float(w[m][0])))
    # No clipping: preserve exact equal class mass per stratum as preregistered.
    return w, dict(training_only_cover_cuts=cuts, rows=rows, weight_min=float(w.min()), weight_max=float(w.max()))


def stage_canary():
    t0 = time.monotonic()
    reg, store, cat = setup()
    names = store.manifest['view_A'] + store.manifest['view_B']
    all_rows, fold_receipts = [], []
    for fold in spatial.folds(cat, store.valid, buffer_px=reg['buffer_px']):
        f = fold['fold']; log('canary fold', f, fold['receipt'])
        train_rows, train_y = sample_train(fold, cat, SEED + f)
        rng = np.random.default_rng(SEED + 50 + f)
        if len(train_rows) > 20000:
            take = rng.choice(len(train_rows), 20000, replace=False)
            train_rows, train_y = train_rows[take], train_y[take]
        test_rows, test_y = sample_test(fold, cat, SEED + 100 + f)
        weights, _ = balance_weights(train_y)
        fold_receipts.append(dict(**fold['receipt'], canary_test_positive_pixels=int(test_y.sum()), canary_test_proxy_negatives=int((test_y == 0).sum())))
        for i, name in enumerate(names):
            x = store.gather(train_rows, [name])
            xt = store.gather(test_rows, [name])
            training_auc = roc_auc_score(train_y, x[:, 0])
            raw_auc = roc_auc_score(test_y, xt[:, 0] * (1 if training_auc >= .5 else -1))
            model = learner(SEED + f, canary=True)
            with threadpool_limits(limits=2):
                model.fit(x, train_y, sample_weight=weights)
                yp = model.predict_proba(xt)[:, 1]
            auc = float(roc_auc_score(test_y, yp))
            alarm_value = max(auc, 1-auc, raw_auc, 1-raw_auc)
            all_rows.append(dict(fold=f, feature=name, training_oriented_raw_auc=float(raw_auc), univariate_boosting_auc=auc,
                direction_insensitive_max=float(alarm_value), alarm=bool(alarm_value > reg['canary_auc_alarm_above'])))
            if i % 10 == 0:
                log('canary', f, i, name, round(auc, 4))
        write('canary_checkpoint', dict(evidence_class='HOLDOUT-DTI diagnostic: feature-alone AUC, not DTI', folds=fold_receipts, rows=all_rows))
    result = dict(evidence_class='HOLDOUT-DTI diagnostic: feature-alone AUC, not DTI',
        evaluator_version=evaluator.VERSION, withheld_positive_pixels=sum(r['truth_px'] for r in fold_receipts),
        folds=fold_receipts, rows=all_rows, maximum_auc=max(r['direction_insensitive_max'] for r in all_rows),
        alarms=[r for r in all_rows if r['alarm']], ok=not any(r['alarm'] for r in all_rows),
        uncertainty='Canary threshold is a conservative alarm; zero alarms do not prove absence of leakage.',
        hypothesis_sha256=reg['hypothesis_sha256'], seconds=time.monotonic()-t0)
    write('canary', result)
    log('CANARY', result['ok'], 'max AUC', result['maximum_auc'])


def predict(store, model, names, domain, chunk=100000):
    out = np.full(store.valid.shape, np.nan, np.float32)
    ids = np.flatnonzero(domain.ravel())
    with threadpool_limits(limits=2):
        for start in range(0, len(ids), chunk):
            rows = ids[start:start+chunk]
            out.ravel()[rows] = model.predict_proba(store.gather(rows, names))[:, 1]
    return out


def operating_rank(prediction, reference):
    ref = np.sort(np.asarray(reference).ravel())
    if not np.isfinite(ref).all() or len(ref) < 3 or np.ptp(ref) == 0:
        raise ValueError('degenerate training-only rank reference')
    p = np.asarray(prediction)
    lo = np.searchsorted(ref, p, side='left')
    hi = np.searchsorted(ref, p, side='right')
    q = ((lo + hi) / (2.0 * len(ref))).astype(np.float32)
    q[~np.isfinite(p)] = np.nan
    return q


def disagreement(a, b):
    return (np.clip((a-.80)/.20, 0, 1) * np.clip(1-np.abs(b-.50)/.35, 0, 1)).astype(np.float32)


def save_np(name, arr):
    np.save(WORK / (name + '.npy'), arr, allow_pickle=False)


def stage_fit():
    t0 = time.monotonic()
    reg, store, cat = setup()
    canary = json.loads((EVID / 'ctd5_canary.json').read_text())
    if not canary['ok']:
        write('stop', dict(reason='feature-alone AUC canary fired; leakage until disproven', stage='before multivariate fit', verdict='negative'))
        raise SystemExit('STOP: leakage canary')
    terms, scores, fold_receipts, error_rows = {}, [], [], []
    mosaics = {arm: np.zeros(store.valid.shape, np.float32) for arm in ARMS}
    full_distance = ndi.distance_transform_edt(~cat).astype(np.float32)
    # Teachers are predicted only on these outer OOF regions unless exchange later passes.
    import joblib
    for fold in spatial.folds(cat, store.valid, buffer_px=reg['buffer_px']):
        f = fold['fold']; log('fit fold', f, fold['receipt'])
        rows, y = sample_train(fold, cat, SEED + f)
        rng = np.random.default_rng(SEED + 500 + f)
        reference_rows = np.flatnonzero(fold['train'].ravel())
        reference_rows = rng.choice(reference_rows, min(30000, len(reference_rows)), replace=False)
        cover = store.gather(rows, ['raw_band_15'])[:, 0]
        standard_weights, standard_receipt = balance_weights(y)
        cover_weights, cover_receipt = balance_weights(y, cover)
        fields, raw_pred, qrefs = {}, {}, {}
        for arm, view, weights in [('single_A', 'view_A', standard_weights), ('matched_A', 'view_A', cover_weights), ('single_B', 'view_B', standard_weights)]:
            model = learner(SEED + f)
            names = store.manifest[view]
            with threadpool_limits(limits=2):
                model.fit(store.gather(rows, names), y, sample_weight=weights)
                reference = model.predict_proba(store.gather(reference_rows, names))[:, 1]
            pred = predict(store, model, names, fold['region'])
            q = operating_rank(pred, reference)
            fields[arm], raw_pred[arm], qrefs[arm] = q, pred, dict(q95=float(np.quantile(reference, .95)))
            joblib.dump(model, WORK / f'fold{f}_{arm}.joblib')
            save_np(f'fold{f}_{arm}_reference', reference.astype(np.float32))
            save_np(f'fold{f}_{arm}_rank', q)
            log('predicted', f, arm)
        fields['union'] = np.maximum(fields['matched_A'], fields['single_B'])
        fields['disagreement'] = disagreement(fields['matched_A'], fields['single_B'])
        neg = fold['region'] & ~cat & (full_distance > 5)
        error_rows.extend(spatial.negative_block_errors(raw_pred['matched_A'], raw_pred['single_B'], neg, f,
            [qrefs['matched_A']['q95'], qrefs['single_B']['q95']], side=50, minimum=32))
        del raw_pred
        target = int(round(reg['global_budget'] * fold['region'].sum() / store.valid.sum()))
        per_fold = dict(fold=f, target_budget=target, receipt=fold['receipt'], scores={},
                        train_positive=int(y.sum()), train_proxy_negative=int((y==0).sum()), cover_balance=cover_receipt)
        for arm in ARMS:
            field = np.nan_to_num(fields[arm], nan=0.0)
            allowed = store.valid & fold['region'] & ~fold['visible']
            if arm == 'disagreement':
                allowed &= field > 0
            pred = nodes.emit_nodes(field, allowed, target, min_px=3)
            score, block_terms = evaluator.evaluate(pred, fold, store.valid, block_side=200)
            score['target_budget'] = target
            score['budget_complete'] = score['emitted'] == target
            per_fold['scores'][arm] = score
            terms[arm] = terms.get(arm, np.zeros_like(block_terms)) + block_terms
            # Mosaic predictions belong to the quadrant's OOF learner, never a full-data fit.
            own = store.valid & fold['quadrant']
            mosaics[arm][own] = field[own]
            log('HOLDOUT-DTI', evaluator.VERSION, 'fold', f, arm, 'n=', score['n_truth'], 'dti=', round(score['dti'], 6), 'emitted=', score['emitted'])
        scores.append(per_fold); fold_receipts.append(fold['receipt'])
        for arm in ARMS:
            save_np('terms_' + arm, terms[arm])
            save_np('mosaic_' + arm, mosaics[arm])
        write('fit_checkpoint', dict(folds=scores, completed_outer_folds=f+1))
        del fields
    independence = spatial.independence(error_rows, threshold=reg['independence_abandon_at'], min_blocks=20)
    independence['evidence_class'] = 'HOLDOUT-DTI diagnostic: OOF negative errors; not a DTI score'
    independence['evaluator_version'] = evaluator.VERSION
    independence['withheld_positive_pixels'] = sum(r['truth_px'] for r in fold_receipts)
    write('independence', independence)
    summary = evaluator.pooled_summary(terms, draws=1000, seed=SEED, candidate='disagreement')
    summary['folds'] = scores
    summary['all_budgets_complete'] = all(s['budget_complete'] for f in scores for s in f['scores'].values())
    summary['independence_allows_exchange'] = independence['allow_exchange']
    summary['seconds'] = time.monotonic()-t0
    summary['historical_comparability'] = 'Historical mean-DTI/tip/translated-truth/capture assays are not pooled-DTI comparators; single views and union re-fit on identical inputs/folds here.'
    summary['organizer_authenticated_inputs'] = False
    write('holdout', summary)
    write('pseudo_exchange', dict(executed=False, rounds=0,
        status='abandoned at empirical independence gate' if not independence['allow_exchange'] else 'eligible, pending conditional stage',
        reason=independence['reason'], pseudo_pixels=0, post_failure_fits=0))
    log('INDEPENDENCE', independence['reason'], independence['max_abs_correlation'])
    log('HOLDOUT-DTI pooled', json.dumps(summary['scores'], indent=1))



def stage_exchange():
    t0 = time.monotonic()
    reg, store, cat = setup()
    independence = json.loads((EVID / 'ctd5_independence.json').read_text())
    if not independence['allow_exchange']:
        raise SystemExit('STOP: independence gate does not permit pseudo-label exchange')
    import joblib
    mosaics = {'matched_A': np.zeros(store.valid.shape, np.float32),
               'single_B': np.zeros(store.valid.shape, np.float32),
               'disagreement': np.zeros(store.valid.shape, np.float32)}
    all_receipts, scores, errors, accumulated = [], [], [], None
    full_distance = ndi.distance_transform_edt(~cat).astype(np.float32)
    for fold in spatial.folds(cat, store.valid, buffer_px=reg['buffer_px']):
        f = fold['fold']; log('exchange fold', f)
        rows, y = sample_train(fold, cat, SEED+f)
        rng = np.random.default_rng(SEED+500+f)
        ref_rows = np.flatnonzero(fold['train'].ravel())
        ref_rows = rng.choice(ref_rows, min(30000, len(ref_rows)), replace=False)
        cover_weights, _ = balance_weights(y, store.gather(rows, ['raw_band_15'])[:, 0])
        standard_weights, _ = balance_weights(y)
        fields = {}
        old_models = {}
        for arm, view in [('matched_A','view_A'),('single_B','view_B')]:
            model = joblib.load(WORK / f'fold{f}_{arm}.joblib')
            old_models[arm] = model
            reference = np.load(WORK / f'fold{f}_{arm}_reference.npy')
            # Full eligible-domain predictions allow rejection of ENTIRE components
            # crossing a training/buffer boundary; no pre-clipping into safe fragments.
            pred = predict(store, model, store.manifest[view], store.valid)
            fields[arm] = operating_rank(pred, reference)
            del pred
        forbidden = ndi.distance_transform_edt(~fold['visible']) <= 5
        forbidden.ravel()[rows] = True
        to_b, rb = spatial.whole_pseudo_segments(fields['matched_A'], fields['single_B'],
            fold['train'], forbidden, .95, .35, .65, side=50, min_pixels=5, cap=2000)
        to_a, ra = spatial.whole_pseudo_segments(fields['single_B'], fields['matched_A'],
            fold['train'], forbidden, .95, .35, .65, side=50, min_pixels=5, cap=2000)
        del fields, forbidden
        def audited_pseudo(ids, receipts):
            if len(ids) and (not fold['train'].ravel()[ids].all() or fold['region'].ravel()[ids].any()):
                raise AssertionError('pseudo-label reached evaluation')
            return dict(pixels=len(ids), segments=len(receipts), components=receipts,
                selected_index_sha256=hashlib.sha256(ids.astype('<i8').tobytes()).hexdigest(),
                all_inside_training=bool(fold['train'].ravel()[ids].all()),
                overlap_evaluation=int(fold['region'].ravel()[ids].sum()),
                min_train_evaluation_buffer_px=fold['receipt']['nearest_training_to_region_px'])
        receipt = dict(fold=f, A_to_B=audited_pseudo(to_b,rb), B_to_A=audited_pseudo(to_a,ra))
        fields, raw = {}, {}
        thresholds = []
        for arm, view, pseudo, weights in [('matched_A','view_A',to_a,cover_weights),
                                           ('single_B','view_B',to_b,standard_weights)]:
            names = store.manifest[view]
            model = learner(SEED+f)
            if len(pseudo):
                ids = np.concatenate([rows,pseudo])
                labels = np.concatenate([y,np.ones(len(pseudo),np.int8)])
                weights = np.concatenate([weights,np.full(len(pseudo),.25)])
                with threadpool_limits(limits=2):
                    model.fit(store.gather(ids,names), labels, sample_weight=weights)
            else:
                model = old_models[arm]
            with threadpool_limits(limits=2):
                reference = model.predict_proba(store.gather(ref_rows,names))[:,1]
            raw[arm] = predict(store,model,names,fold['region'])
            fields[arm] = operating_rank(raw[arm],reference)
            thresholds.append(float(np.quantile(reference,.95)))
            joblib.dump(model, WORK / f'fold{f}_{arm}_post.joblib')
            log('refit/predict',f,arm,'pseudo',len(pseudo))
        errors.extend(spatial.negative_block_errors(raw['matched_A'],raw['single_B'],
            fold['region'] & ~cat & (full_distance>5),f,thresholds,side=50,minimum=32))
        del raw
        fields['disagreement'] = disagreement(fields['matched_A'],fields['single_B'])
        target=int(round(reg['global_budget']*fold['region'].sum()/store.valid.sum()))
        pred=nodes.emit_nodes(np.nan_to_num(fields['disagreement'],nan=0),
            store.valid & fold['region'] & ~fold['visible'] & (fields['disagreement']>0),target,min_px=3)
        score,terms=evaluator.evaluate(pred,fold,store.valid,block_side=200)
        score.update(fold=f,target_budget=target,budget_complete=score['emitted']==target)
        scores.append(score)
        accumulated=terms if accumulated is None else accumulated+terms
        for arm,field in fields.items():
            own=store.valid & fold['quadrant']
            mosaics[arm][own]=np.nan_to_num(field[own],nan=0)
            save_np('post_mosaic_'+arm,mosaics[arm])
        save_np('terms_post_disagreement',accumulated)
        all_receipts.append(receipt)
        write('pseudo_checkpoint',dict(completed_folds=f+1,folds=all_receipts,scores=scores))
        log('HOLDOUT-DTI post-exchange',evaluator.VERSION,score['dti'],'n',score['n_truth'])
    terms={a:np.load(WORK/('terms_'+a+'.npy')) for a in ARMS if a!='disagreement'}
    terms['pre_exchange']=np.load(WORK/'terms_disagreement.npy')
    terms['disagreement']=accumulated
    result=evaluator.pooled_summary(terms,draws=1000,seed=SEED,candidate='disagreement')
    result.update(folds=scores,all_candidate_budgets_complete=all(s['budget_complete'] for s in scores),
                  artifact_field='post_mosaic_disagreement', seconds=time.monotonic()-t0)
    write('post_holdout',result)
    post_independence=spatial.independence(errors,threshold=.6,min_blocks=20)
    write('post_independence',post_independence)
    write('pseudo_exchange',dict(executed=True,rounds=1,status='one registered confident-to-abstaining whole-segment exchange completed',
        folds=all_receipts, pseudo_pixels=sum(r[d]['pixels'] for r in all_receipts for d in ('A_to_B','B_to_A')),
        parent_independence_max_abs=independence['max_abs_correlation'],
        post_independence_max_abs=post_independence['max_abs_correlation'],
        post_independence_allows_further_exchange=post_independence['allow_exchange'],
        further_rounds=0, post_failure_fits=0, seconds=time.monotonic()-t0))
    log('POST EXCHANGE POOLED', json.dumps(result['scores']['disagreement']))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('stage', choices=['canary', 'fit', 'exchange'])
    args = p.parse_args()
    if args.stage == 'canary': stage_canary()
    elif args.stage == 'fit': stage_fit()
    else: stage_exchange()

if __name__ == '__main__': main()
