"""H95 probe: does any catalogue-free proxy truth rank the board-scored files in board order?"""
import sys, json, glob, numpy as np, rasterio
from scipy import ndimage as ndi
from scipy.stats import spearmanr
sys.path.insert(0,'/home/user/GEMSDOE52/src')
from gems52 import metric
D='/home/user/GEMSDOE52/data/'
# owner-reported public-board scores, as listed in the brief (OWNER-REPORTED, not organiser receipts)
BOARD={'reference/h33-2-b2-zeros.tif':0.2778,
 'scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif':0.2600,
 'scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif':0.2477,
 'scored/gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif':0.2449,
 'scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif':0.1922,
 'scored/gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan.tif':0.1894,
 'scored/gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif':0.1855,
 'scored/gems10-h28-dotted-ridge-20260928T020256236880Z-6452ae1d00.tif':0.1839,
 'scored/gems10-h25-ctx-ridge-20260927T232947704150Z-6452ae1d00.tif':0.1280,
 'scored/gemsdoe-ens12-adopted-7f00890a.tif':0.1563,
 'scored/8GEMSDOE_Hedge-v2_submission.tif':0.1563,
 'scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif':0.0904,
 'scored/gemsdoe9-PLACEHOLDER-2314b599.tif':0.0107}
with rasterio.open(D+'sample_submission.tif') as s: dom=np.isfinite(s.read(1))
with rasterio.open(D+'labels.tif') as s: cat=s.read(1)==1
with rasterio.open(D+'external/derived_sgmc_faults_100m_u8.tif') as s: sg=s.read(1)>0
dcat=ndi.distance_transform_edt(~cat)
preds={}
for k in BOARD:
    with rasterio.open(D+k) as s: a=s.read(1)
    preds[k]=np.where(np.isfinite(a)&dom,a,0).astype(np.float32)
truths={'catalogue':cat&dom,
        'sgmc_all':sg&dom,
        'sgmc_off_ge3px':sg&dom&(dcat>=3),
        'sgmc_off_ge5px':sg&dom&(dcat>=5)}
# thinned to plausible prevalence (|G|~10k): deterministic 1-in-k subsample of sgmc_off
rng=np.random.default_rng(88)
t=truths['sgmc_off_ge3px']; idx=np.flatnonzero(t.ravel()); keep=rng.choice(idx,10000,replace=False)
th=np.zeros(t.size,bool); th[keep]=True; truths['sgmc_off_ge3px_thin10k']=th.reshape(t.shape)
res={}
y=np.array(list(BOARD.values()))
for tn,g in truths.items():
    scores=[metric.dti(preds[k],g)['dti'] for k in BOARD]
    rho=spearmanr(scores,y).statistic
    res[tn]=dict(truth_px=int(g.sum()),spearman_vs_board=float(rho),scores=dict(zip([k.split('/')[-1][:40] for k in BOARD],map(float,scores))))
    print(tn,int(g.sum()),'spearman',round(float(rho),3),[round(float(s),4) for s in scores])
json.dump(res,open('/home/user/GEMSDOE52/work/h95/board_instrument.json','w'),indent=1)
