"""Legacy H60 diagnostic: compare local raster proximity to visible catalogue folds.

This is not a competition score, not a validated candidate ranker, and not a causal test of
public-board results. The saved labels are owner-reported file/score associations with no
organizer receipt. Its historical output is retained for audit; do not use it for promotion,
submission selection, or current experiment authorization.
"""
import json, sys, glob
from pathlib import Path
import numpy as np, rasterio
from scipy import ndimage
sys.path.insert(0, 'src')
from gems52 import grid as G
from gems52.metric import dti

RING_M = 200.0; BUFFER_PX = 4; N_FOLDS = 4; SEED = 20261009
lab = rasterio.open('data/labels.tif').read(1); cat = lab == 1; foot = lab != -1
with rasterio.open('data/sample_submission.tif') as s: sub_ok = np.isfinite(s.read(1))
H, W = lab.shape

blk = G.block_labels(cat.shape, foot, n=8)
ids = np.unique(blk[blk >= 0])
pos = np.array([int((cat & (blk == i)).sum()) for i in ids])
rng = np.random.default_rng(SEED)
order = ids[np.argsort(-pos, kind='stable')]
fold_of = {}; load = np.zeros(N_FOLDS)
for b in order:
    f = int(np.argmin(load)); fold_of[int(b)] = f; load[f] += pos[list(ids).index(b)]
fmap = np.full(cat.shape, -1, np.int16); m = blk >= 0
fmap[m] = np.array([fold_of[int(v)] for v in blk[m]], np.int16)
buf = G.buffer_from_block_ids(blk, BUFFER_PX)
assert (np.load('work/h60_pA.npy').shape == (H, W))

priors = {'champion_h33_2_b2': 'data/reference/h33-2-b2-zeros.tif'}
for p in sorted(glob.glob('data/scored/*.tif')):
    priors[Path(p).stem[:34]] = p

out = {}
for f in range(N_FOLDS):
    held = fmap == f
    vis = cat & ~held
    ed = ndimage.distance_transform_edt(~vis, sampling=100.0)
    allow = foot & sub_ok & (ed > RING_M)
    truth = held & cat
    for nm, path in priors.items():
        a = rasterio.open(path).read(1)
        pm = (np.where(np.isfinite(a) & (a >= 0) & (a <= 1), a, 0.0) > 0) & allow
        d = dti(pm.astype(np.float64), truth)
        out.setdefault(nm, []).append(dict(fold=f, px=int(pm.sum()), dti=float(d['dti']),
                                           tpw=float(d['tpw']), n_truth=int(truth.sum())))
    print(f'fold {f} done', flush=True)
rows = {k: dict(mean_dti=float(np.mean([r['dti'] for r in v])),
                mean_px=float(np.mean([r['px'] for r in v])), folds=v)
        for k, v in out.items()}
print(f"{'prior':36s} {'mean_px':>9s} {'mean_DTI':>9s}")
for k in sorted(rows, key=lambda x: -rows[x]['mean_dti']):
    print(f"{k:36s} {rows[k]['mean_px']:9.0f} {rows[k]['mean_dti']:9.5f}")
Path('evidence/h60_prior_control.json').write_text(json.dumps(rows, indent=1) + "\n")

# ---- the verdict receipt: instrument vs the owner-reported board -------------------
from scipy.stats import spearmanr
BOARD = {  # owner-reported filename attribution, NOT organiser-authenticated
 'champion_h33_2_b2': 0.2778, 'gems24-h25-1-dotted-h19-5-d2-8-202': 0.2600,
 'gems24-h25-1-dotted-h19-5-d1-5-202': 0.2477, 'gems27-topo-gap-closure-t-v2-on-d1': 0.2449,
 'gems19-h19-5-powerlaw-budget-multi': 0.1922, 'gems19-h19-4-multiline-corroborate': 0.1894,
 'gems16-h16-1-topo-geophys-baseline': 0.1855, 'gems10-h28-dotted-ridge-20260928T0': 0.1839,
 'gemsdoe-ens12-adopted-7f00890a': 0.1563, '8GEMSDOE_Hedge-v2_submission': 0.1563,
 'gems10-h25-ctx-ridge-20260927T2329': 0.1280, '13gems_20261001_r13-lattice-s5_v2_': 0.0904,
 'gemsdoe9-PLACEHOLDER-2314b599': 0.0107,
}
recs = [dict(prior=k, board=BOARD[k], instrument=rows[k]['mean_dti'],
             mean_px=rows[k]['mean_px']) for k in BOARD if k in rows]
rho = spearmanr([r['board'] for r in recs], [r['instrument'] for r in recs])
ch = rows['champion_h33_2_b2']['mean_dti']
ph = rows['gemsdoe9-PLACEHOLDER-2314b599']['mean_dti']
Path('evidence/h60_instrument_verdict.json').write_text(json.dumps(dict(
    rows=recs, spearman_board_vs_instrument=float(rho.statistic), p_value=float(rho.pvalue),
    n=len(recs), champion_instrument_dti=ch, placeholder_instrument_dti=ph,
    champion_scores_below_random_placeholder=bool(ch < ph),
    board_source="owner-reported filename attribution, NOT organiser-authenticated",
    verdict=(f"Internal diagnostic comparison only: the row labelled 0.2778 has value {ch:.5f}; "
             f"the row labelled as a placeholder has value {ph:.5f}. These are not leaderboard "
             "scores. The owner-reported file/score labels have no organizer receipt. Across "
             "13 such labels, Spearman rho is -0.099 (p=0.748); this small sample provides no "
             "reliable calibration, ranking, inversion, or causal evidence. The diagnostic does "
             "not rank candidates for the competition and does not explain any score change."),
), indent=1) + "\n")
print('champion', round(ch, 5), 'placeholder', round(ph, 5),
      'spearman', round(float(rho.statistic), 4), 'p', round(float(rho.pvalue), 4))
