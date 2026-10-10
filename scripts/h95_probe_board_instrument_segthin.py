import sys, json, numpy as np, rasterio
from scipy import ndimage as ndi
from scipy.stats import spearmanr, kendalltau
sys.path.insert(0,'/home/user/GEMSDOE52/src'); sys.path.insert(0,'/home/user/GEMSDOE52/work/h95')
from gems52 import metric
exec(open('/home/user/GEMSDOE52/scripts/h95_probe_board_instrument.py').read().split('with rasterio.open(D+\'sample')[0])  # BOARD, D
with rasterio.open(D+'sample_submission.tif') as s: dom=np.isfinite(s.read(1))
with rasterio.open(D+'labels.tif') as s: cat=s.read(1)==1
with rasterio.open(D+'external/derived_sgmc_faults_100m_u8.tif') as s: sg=s.read(1)>0
dcat=ndi.distance_transform_edt(~cat)
off=sg&dom&(dcat>=3)
comp,n=ndi.label(off,np.ones((3,3),bool)); sizes=np.bincount(comp.ravel())[1:]
print('off-catalogue SGMC components',n,'px',int(off.sum()))
preds={}
for k in BOARD:
    with rasterio.open(D+k) as s: a=s.read(1)
    preds[k]=np.where(np.isfinite(a)&dom,a,0).astype(np.float32)
y=np.array(list(BOARD.values())); names=[k.split('/')[-1][:44] for k in BOARD]
out={}
for G in (6000,10000,12500):
    allsc=[]
    for seed in range(5):
        rng=np.random.default_rng(1000*G+seed); order=rng.permutation(n)+1
        cum=np.cumsum(sizes[order-1]); chosen=order[:int(np.searchsorted(cum,G))+1]
        g=np.isin(comp,chosen)
        sc=[metric.dti(preds[k],g)['dti'] for k in BOARD]; allsc.append(sc)
    allsc=np.array(allsc); m=allsc.mean(0)
    rho=spearmanr(m,y).statistic; tau=kendalltau(m,y).statistic
    per_seed=[float(spearmanr(r,y).statistic) for r in allsc]
    nolat=[i for i,k in enumerate(BOARD) if 'lattice' not in k]
    rho_nl=spearmanr(m[nolat],y[nolat]).statistic
    out[G]=dict(mean_scores=dict(zip(names,map(float,m))),spearman=float(rho),kendall=float(tau),per_seed_spearman=per_seed,spearman_excl_lattice=float(rho_nl))
    print(G,'spearman',round(rho,3),'kendall',round(tau,3),'per-seed',[round(x,3) for x in per_seed],'excl-lattice',round(rho_nl,3))
    print('   ',[round(float(v),4) for v in m])
json.dump(out,open('/home/user/GEMSDOE52/work/h95/board_instrument2.json','w'),indent=1)
