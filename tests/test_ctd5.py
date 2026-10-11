"""CTD5 regressions: pooled metric, strict lane gates, shared cache split and exports."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import zipfile
import numpy as np
import pytest
import rasterio
from affine import Affine
from scipy.stats import spearmanr
from gems52 import evaluate_holdout as E, metric, gates, grid, spatial, submission_writer
from gems52.structural import A_BANDS, B_BANDS

ROOT = Path(__file__).resolve().parents[1]


def tif(path, a, transform=None):
    with rasterio.open(path, 'w', driver='GTiff', width=a.shape[1], height=a.shape[0],
                       count=1, dtype='float32', crs='EPSG:32611',
                       transform=transform or Affine(100, 0, 243350, 0, -100, 4508550)) as ds:
        ds.write(a.astype('float32'), 1)
    return path


def test_metric_bookkeeping_matches_exact_metric_and_masks_visible():
    p = np.zeros((30, 30), np.float32); t = np.zeros_like(p, bool)
    p[4, 5] = 1; p[17, 19] = .7; p[1, 1] = 1; t[5, 5] = True; t[17, 20] = True
    vis = np.zeros_like(t); vis[1, 1] = True
    fold = dict(region=np.ones_like(t), truth=t, visible=vis)
    result, terms = E.evaluate(p, fold, np.ones_like(t), block_side=10)
    masked = p.copy(); masked[vis] = 0
    assert result['dti'] == pytest.approx(metric.dti(masked, t)['dti'], abs=1e-12)
    assert float(E.from_terms(terms.sum(axis=0))) == pytest.approx(result['dti'], abs=1e-12)
    assert terms[:, 3].sum() == 2
    assert result['mass'] == pytest.approx(1.7)


def test_pooled_dti_is_not_mean_fold_dti_and_paired_ci_is_zero_for_same_arm():
    x = np.array([[1., 3., 8., 9.], [10., 20., 20., 30.], [4., 1., 7., 11.]])
    out = E.pooled_summary({'control': x, 'disagreement': x.copy()}, draws=50)
    expected = E.from_terms(x.sum(axis=0))
    assert out['scores']['disagreement']['dti'] == pytest.approx(expected)
    assert expected != pytest.approx(E.from_terms(x).mean())
    assert out['paired_differences']['control']['ci95'] == [0., 0.]
    assert out['scores']['disagreement']['withheld_positive_pixels'] == 50


def test_evaluator_rejects_nan_even_if_it_would_be_masked():
    p = np.zeros((8, 8)); p[0, 0] = np.nan
    with pytest.raises(ValueError, match='finite'):
        E.evaluate(p, dict(region=np.zeros((8, 8), bool), truth=np.zeros((8, 8), bool), visible=np.ones((8, 8), bool)), np.ones((8, 8), bool))


def test_disputed_band_six_is_in_surface_view_only():
    assert set(A_BANDS).isdisjoint(B_BANDS)
    assert set(A_BANDS) | set(B_BANDS) == set(range(1, 20))
    assert 6 in B_BANDS and 6 not in A_BANDS


def test_exact_rank_gate_and_near_dot_gate_are_distinct(tmp_path):
    rng = np.random.default_rng(2)
    field = rng.random((35, 35), dtype=np.float32)
    prior = (field > .90).astype(np.float32)
    reference = tif(tmp_path/'sample.tif', np.zeros_like(field))
    path = tif(tmp_path/'prior.tif', prior)
    fp = np.ones_like(prior, bool)
    out = gates.lane_uniqueness_report(field, fp, [path], sample=reference, phase='surface')
    assert out['per_prior'][0]['spearman'] == pytest.approx(spearmanr(field.ravel(), prior.ravel()).statistic, abs=1e-12)
    # A distinct near-shifted dot pattern fails the >70% rule even with low Jaccard.
    p = np.zeros((35, 35), np.float32); p[::6, ::6] = 1
    old = np.zeros_like(p); old[::6, 1::6] = 1
    path = tif(path, old)
    out = gates.lane_uniqueness_report(p, fp, [path], sample=reference, phase='dots')
    assert out['duplicate'] and out['max_near_3px_fraction'] == 1
    assert not out['per_prior'][0]['identical']


def test_rank_gate_detects_monotone_surface_duplicate(tmp_path):
    x = np.linspace(0, 1, 400, dtype=np.float32).reshape(20, 20)
    ref = tif(tmp_path/'ref.tif', x)
    old = tif(tmp_path/'old.tif', x*x)
    r = gates.lane_uniqueness_report(x, np.ones_like(x, bool), [old], sample=ref, phase='surface')
    assert r['duplicate'] and r['max_spearman'] == pytest.approx(1)


def test_lane_gate_rejects_transform_mismatch_and_checks_all_priors(tmp_path):
    x = np.arange(400, dtype=np.float32).reshape(20, 20)/400
    ref = tif(tmp_path/'ref.tif', x)
    priors = [tif(tmp_path/f'old{i}.tif', np.flipud(x)) for i in range(9)]
    priors.append(tif(tmp_path/'last.tif', x))
    r = gates.lane_uniqueness_report(x, np.ones_like(x, bool), priors, sample=ref, phase='surface')
    assert r['priors_checked'] == 10 and r['duplicate']
    shifted = tif(tmp_path/'shift.tif', x, Affine(100, 0, 243450, 0, -100, 4508550))
    r = gates.lane_uniqueness_report(x, np.ones_like(x, bool), [shifted], sample=ref, phase='surface')
    assert not r['ok'] and r['error_count'] == 1


def test_submission_zip_contains_only_one_tif_and_note_limit(tmp_path, monkeypatch):
    shape = (20, 20); a = np.zeros(shape, np.float32); a[5, 5] = 1
    monkeypatch.setattr(grid, 'SHAPE', shape)
    ref = tif(tmp_path/'ref.tif', a)
    r = submission_writer.write_submission(tmp_path/'candidate.tif', a, ref, np.ones(shape, bool), name='unique', note='Research only.')
    assert r['validator']['ok'] and not r['approved_for_weekly_slot']
    with zipfile.ZipFile(tmp_path/'candidate.zip') as z:
        assert z.namelist() == ['candidate.tif']
    with pytest.raises(ValueError, match='140'):
        submission_writer.write_submission(tmp_path/'bad.tif', a, ref, np.ones(shape, bool), name='name', note='x'*141)
    a[1, 1] = np.inf
    with pytest.raises(ValueError, match='normalized'):
        submission_writer.write_submission(tmp_path/'bad.tif', a, ref, np.ones(shape, bool), name='name', note='note')


def test_whole_component_and_euclidean_buffer_never_leak():
    cat = np.zeros((180, 180), bool)
    cat[20:160, 80] = True  # a trace crossing a quadrant boundary stays whole
    cat[20:60, 140] = True
    valid = np.ones_like(cat)
    seen = np.zeros(cat.shape, np.int8)
    for f in spatial.folds(cat, valid, buffer_px=8):
        assert not (f['train'] & f['held_all']).any()
        assert not (f['train'] & f['region']).any()
        assert f['receipt']['shared_train_truth_components'] == 0
        assert f['receipt']['nearest_training_to_region_px'] > 8
        seen += f['truth']
    assert np.all(seen[cat] == 1)


def test_registered_budget_no_external_features_or_prior_training():
    reg = json.loads((ROOT/'registry/ctd5_preregistration.json').read_text())
    assert reg['global_budget'] == 12000 and reg['buffer_px'] == 80
    source = (ROOT/'scripts/run_ctd5.py').read_text()
    # Inventory access is deliberately outside the training driver.
    assert 'prior_inventory' not in source and 'scored/' not in source
    assert 'whole_pseudo_segments' in source
    assert "model.fit(store.gather(ids,names), labels, sample_weight=weights)" in source


def load_driver():
    spec=importlib.util.spec_from_file_location('ctd5_driver_test', ROOT/'scripts/run_ctd5.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_disagreement_cannot_be_a_monotone_rescale_of_the_union():
    d=load_driver()
    a=np.array([1.,1.],np.float32);b=np.array([.5,1.],np.float32)
    assert np.array_equal(np.maximum(a,b),[1.,1.])
    np.testing.assert_allclose(d.disagreement(a,b), [1.,0.], rtol=1e-6, atol=1e-7)


def test_cover_balancing_matches_class_mass_within_each_training_bin():
    d=load_driver()
    cover=np.arange(40,dtype=float)
    y=np.tile(np.array([1,0,0,0,0,1,1,0,0,0]),4)
    w,rec=d.balance_weights(y,cover)
    bins=np.searchsorted(rec['training_only_cover_cuts'],cover,side='right')
    for b in range(4):
        assert w[(bins==b)&(y==0)].sum()==pytest.approx(w[(bins==b)&(y==1)].sum())


def test_operating_rank_ties_and_missing_values():
    d=load_driver()
    r=d.operating_rank(np.array([0.,1.,2.,3.,np.nan]),np.array([0.,1.,1.,2.]))
    assert r[:4].tolist()==[.125,.5,.875,1.]
    assert np.isnan(r[-1])


def test_feed_strips_portal_identity_and_notes_from_public_report(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('ctd5_feed_test',ROOT/'scripts/refresh_feed.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    root=tmp_path; ev=root/'evidence'; dl=root/'docs'/'downloads'; sub=root/'submission'
    ev.mkdir();dl.mkdir(parents=True);sub.mkdir()
    name='current-research.tif';payload=b'fixture research raster'
    (sub/name).write_bytes(payload);(dl/name).write_bytes(payload)
    (sub/'LATEST.txt').write_text(name)
    (ev/f'submission_{name[:-4]}.json').write_text(json.dumps({
        'file':name,'note':'Current note','submission_note':'Stale note',
        'submission_name':'Old portal name','portal':{'note':'Portal note'},
        'bytes':len(payload),'sha256':__import__('hashlib').sha256(payload).hexdigest()}))
    monkeypatch.setattr(mod,'ROOT',root);monkeypatch.setattr(mod,'EV',ev);monkeypatch.setattr(mod,'DL',dl)
    report=mod.latest_submission()
    assert report['artifact_status']=='RESEARCH ONLY · NOT FOR SUBMISSION'
    assert report['approved_for_submission'] is False
    assert not {'submission_name','submission_note','submission_note_long','portal'} & report.keys()


def test_download_wrapper_preserves_comma_separated_ids(tmp_path):
    import subprocess, os
    fake=tmp_path/'python3'
    fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$CTD5_ARGV_LOG"\n')
    fake.chmod(0o755)
    env=dict(os.environ,PATH=str(tmp_path)+os.pathsep+os.environ['PATH'],GEMS_ONLY='labels,sample_submission',
             GEMS_DATA_DIR=str(tmp_path/'data'),CTD5_ARGV_LOG=str(tmp_path/'argv'))
    p=subprocess.run(['bash',str(ROOT/'scripts/download_competition_data.sh')],env=env,capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    argv=(tmp_path/'argv').read_text().splitlines()
    assert argv[argv.index('--only')+1]=='labels,sample_submission'


def test_full_published_ctd5_release_from_actual_bytes():
    spec=importlib.util.spec_from_file_location('ctd5_release_test',ROOT/'scripts/check_ctd5_release.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    r=mod.check()
    assert r['ok'] and r['verdict']=='negative' and r['submit_ok'] is False


def test_current_readme_contains_the_complete_preserved_brief():
    brief=(ROOT/'knowledge/26_current_user_brief.md').read_text()
    normalized=lambda text:'\n'.join(line.rstrip(' \t') for line in text.splitlines())
    assert normalized(brief[brief.index('```text'):]) in normalized((ROOT/'README.md').read_text())
    assert 'PARALLEL-RUN PROTOCOL' in brief and '0.3774' in brief and '0.3195' in brief


def test_feed_rewrites_legacy_archive_as_one_tiff_and_then_is_stable(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('ctd5_feed_preserve',ROOT/'scripts/refresh_feed.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    (tmp_path/'submission').mkdir();dl=tmp_path/'downloads';dl.mkdir()
    name='historical-candidate.tif';payload=b'fixture raster'
    (tmp_path/'submission'/name).write_bytes(payload)
    archive=dl/'historical-candidate.zip'
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr(name,payload);z.writestr('old-note.txt','Do not republish portal metadata.')
    monkeypatch.setattr(mod,'ROOT',tmp_path);monkeypatch.setattr(mod,'DL',dl)
    assert mod.make_zip(name)==str(archive)
    with zipfile.ZipFile(archive) as z:
        assert z.namelist()==[name] and z.read(name)==payload and z.testzip() is None
    scrubbed=archive.read_bytes()
    assert mod.make_zip(name)==str(archive)
    assert archive.read_bytes()==scrubbed


def test_concurrent_h60_missing_correlations_not_zero_or_approval():
    def reject(value): raise ValueError(value)
    old=json.loads((ROOT/'docs/data/submission_h60.json').read_text(),parse_constant=reject)
    assert old['independence_test']['n_blocks']==2
    assert old['independence_test']['pearson_r'] is None
    assert old['independence_test']['spearman_rho'] is None
    current=json.loads((ROOT/'docs/data/submission.json').read_text())
    assert current['approved_for_weekly_slot'] is False and current['promoted'] is False
    assert current['file']==(ROOT/'submission/LATEST.txt').read_text().strip()


def test_source_commit_references_all_resolve_but_no_scores_are_authenticated():
    r=json.loads((ROOT/'evidence/ctd5_source_commit_resolution.json').read_text())
    assert r['all_commit_refs_resolved'] and len(r['entries'])==53
    assert all(x['ok'] and x['requested']==x['returned_commit'] for x in r['entries'])
    s=json.loads((ROOT/'evidence/ctd5_sources.json').read_text())
    assert s['organizer_confirmed_scores']==[]


def test_corrected_shared_evaluation_geometry_cannot_reveal_hidden_tails():
    eligible=np.ones((120,120),bool)
    a=np.zeros_like(eligible);a[10:105,58]=True;a[20:40,90]=True
    b=np.zeros_like(eligible);b[12:95,62]=True;b[80:110,30]=True
    fa=list(spatial.folds(a,eligible,buffer_px=5));fb=list(spatial.folds(b,eligible,buffer_px=5))
    for x,y in zip(fa,fb):
        assert np.array_equal(x['region'],y['region'])
        assert np.array_equal(x['region'],x['quadrant']&eligible)
        assert x['receipt']['evaluation_region_label_blind']
        assert not (x['train']&x['held_all']).any()
    # A crossing component is fully hidden in both intersected quadrants.
    assert fa[0]['held_all'][90,58] and fa[2]['held_all'][20,58]
    counts=sum(f['truth'].astype(int) for f in fa)
    assert np.all(counts[a]==1)


def test_ctd5_legacy_assay_cannot_be_mistaken_for_validated_promotion():
    c=json.loads((ROOT/'evidence/ctd5_run_card.json').read_text())
    assert c['strict_holdout_valid'] is False
    assert 'withheld labels' in c['validation_warning']
    assert not c['submit_ok'] and c['verdict']=='negative'
