#!/usr/bin/env python3
"""H76 exploratory subsurface/surface disagreement; NOT co-training or slot-approved.

This fail-closed research artifact tests whether a gravimetric edge with muted topography
can be emitted without copying a prior. It does not claim a learned classifier or holdout DTI.
"""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from gems52 import grid, nodes, gates, submission_writer

src = ROOT / 'data/training_features.tif'
sample = ROOT / 'data/sample_submission.tif'
if not src.exists() or not sample.exists() or not (ROOT / 'data/labels.tif').exists():
    raise SystemExit('restore training_features, labels and sample_submission first')
valid = grid.footprint_from(src)
g = grid.read_band(src, 18)  # isostatic gravity horizontal gradient
b = grid.read_band(src, 19)  # detrended topographic slope
cat = grid.read_band(ROOT / 'data/labels.tif', 1) == 1
# Fill nodata before smoothing; forbid emitting in a two-pixel boundary guard.
inner = ndi.binary_erosion(valid, iterations=2)
from scipy.ndimage import distance_transform_edt
ix = distance_transform_edt(valid == 0, return_distances=False, return_indices=True)
g = g[tuple(ix)] if not valid.all() else g
b = b[tuple(ix)] if not valid.all() else b
# Within-field percentile ranks: geophysical confidence and surface abstention are
# UNSUPERVISED proxies, not calibrated posterior probabilities.
def rank(a):
    from scipy.stats import rankdata
    z = a[valid]
    out = np.zeros(a.shape, np.float32)
    out[valid] = (rankdata(z, method='average') / len(z)).astype(np.float32)
    return out
A = rank(ndi.gaussian_filter(g, 2))
B = rank(ndi.gaussian_filter(b, 2))
allowed = inner & (distance_transform_edt(~cat) > 2) & (A > .95) & (B < .30)
score = (A * (1 - B)).astype(np.float32)
# Local accessible inventory; not a claim about the full 565-raster census.
priors = sorted((ROOT / 'submission').glob('*.tif'))
priors = [p for p in priors if 'h76-' not in p.name]
pre = gates.lane_report(score, valid, priors, sample=sample, phase='surface')
receipt = {'method': 'unsupervised gravity-gradient-only / slope-abstaining proxy, NOT co-training',
           'surface_gate': pre, 'registry_scope': 'locally tracked submission/*.tif only',
           'holdout': None, 'holdout_status': 'not measured; no promotion',
           'eligible': int(allowed.sum()), 'prior_count': len(priors)}
if pre['literal']['verdict'] != 'PASS':
    receipt['verdict'] = 'DUPLICATE/STOP before placement'
else:
    dots = nodes.spacing_select(score, allowed, 3000, min_px=3)
    post = gates.lane_report(dots.astype(np.float32), valid, priors, sample=sample, phase='dots')
    receipt['dots_gate'] = post
    receipt['dots'] = int(dots.sum())
    receipt['union_check'] = {'all_dots_A_confident_B_abstains': bool((allowed[dots]).all()),
                              'note': 'No two trained views; not a co-training union test'}
    if post['literal']['verdict'] != 'PASS':
        receipt['verdict'] = 'DUPLICATE/STOP on dots; no emission'
    elif not dots.any():
        receipt['verdict'] = 'NEGATIVE: no eligible dots'
    else:
        out = ROOT / 'submission/gems52-h76-gravity-surface-abstention-research-only.tif'
        note = 'H76 exploratory gravity edge with quiet slope; unvalidated, research-only; do not spend competition slot'
        rec = submission_writer.write_submission(out, dots.astype(np.float32), sample, valid,
            note=note, name='h76-gravity-surface-abstention-research-only', metadata={'holdout': 'not measured'})
        receipt['raster'] = str(out.relative_to(ROOT))
        receipt['sha256'] = hashlib.sha256(out.read_bytes()).hexdigest()
        receipt['validator'] = rec['validator']
        receipt['verdict'] = 'NEGATIVE: unique local proxy, no holdout or full-census gate; DOWNLOAD YES, SUBMIT NO'
        import shutil
        shutil.copyfile(out, ROOT / 'docs/downloads/h76-candidate.tif')
(ROOT / 'evidence/h76_exploratory.json').write_text(json.dumps(receipt, indent=2, default=str) + '\n')
print(receipt['verdict'])
print('eligible', receipt['eligible'], 'priors', len(priors))
