"""The brief's two-view co-training instrument, rebuilt on the R5 detector's own fields.

View A is potential-field and subsurface (magnetics, gravity, geodetic strain, seismicity, depth to
basement, conductivity).  View B is surface (detrended elevation and its slope, the named LiDAR scarp
channels, and the radiometric bands -- including organiser band 6, which is tagged magnetic but
measures as radiometric total count, IR-52-019/IR-52-034).  Both views see the detector's family
responses and the along-trace persistence of their own families, which is what makes this a
co-training of *trace detectors* rather than of two generic feature bags.

The brief's four requirements, and where each is implemented
-----------------------------------------------------------
1. *Test the independence assumption empirically: correlate each view's spatial-block out-of-fold
   errors on labeled negatives, and abandon the method if they are strongly correlated.*
   :func:`independence` -- per-block OOF false-positive rate on labelled negatives, Spearman and
   Pearson across blocks, verdict against the declared 0.60 threshold.  Reported at 20 km blocks
   (comparable with round 4's 0.7051) and at 50 px blocks (comparable with H59's 0.1071), because
   the two earlier rounds measured at different scales and got opposite verdicts.
2. *Pseudo-label only where one view is confident and the other abstains, using whole-segment
   spatial blocks and a buffer.*  :func:`pseudo_labels` -- donor = top 1 % of one view's OOF rank
   inside whole held-out-block segments where the other view is below its 10th percentile; the
   exchange is applied per fold, buffered, and its effect on fold AUC is measured, not assumed.
3. *The discovery signal is disagreement.*  :func:`disagreement_strata` -- A-only (confident A,
   abstaining B: candidate buried structure under cover) and B-only (confident B, abstaining A:
   candidate surface artefact -- road, erosion line, scarp of non-tectonic origin), each with the
   measured median depth-to-basement, slope and radiometric signature that make the geology
   checkable rather than rhetorical.
4. *Compare against a single-view baseline on hide-and-recover segments.*  :func:`baseline_fields`
   returns the single-view fields the localisation assay scores at matched budget, so the
   co-trained field has to beat A-only and B-only to be worth anything.

Memory discipline: the feature stacks are ``np.memmap`` on disk under ``work/r5/``.  A 3.9 GB box
cannot hold two 16-layer float32 stacks plus the detector's six family responses, and round 4 died
three times with exit 137 trying.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.stats import pearsonr, spearmanr

from gems52_r5 import layers as L

WORK = Path("work/r5")
SEED = 20261009
ABANDON_R = 0.60
BLOCK_M = 20_000.0

# view -> [(source, band)] raw layers.  Family responses and persistence are appended by name.
VIEW_A_RAW = [("features", 1), ("features", 3), ("features", 4), ("features", 5),
              ("features", 13), ("features", 15), ("features", 16), ("features", 17)]
VIEW_B_RAW = [("features", 6), ("features", 12), ("features", 19),
              ("lidar", 1), ("lidar", 3), ("lidar", 6), ("lidar", 7), ("lidar", 9),
              ("rad", 1), ("rad", 2), ("rad", 3)]
VIEW_A_FAMS = ("mag", "grav", "strain", "sub")
VIEW_B_FAMS = ("topo", "rad")


def feature_names(view: str) -> list[str]:
    raw = VIEW_A_RAW if view == "A" else VIEW_B_RAW
    fams = VIEW_A_FAMS if view == "A" else VIEW_B_FAMS
    return ([f"raw_{s}_{L.band_name(s, b)}" for s, b in raw]
            + [f"resp_{f}" for f in fams]
            + [f"corrob_{'A' if view == 'A' else 'B'}", f"persist_{'A' if view == 'A' else 'B'}"])


def block_ids(shape, valid: np.ndarray, block_m: float = BLOCK_M) -> np.ndarray:
    """Contiguous square blocks of ``block_m`` metres; -1 outside the footprint."""
    h, w = shape
    n = max(int(round(block_m / 100.0)), 1)          # metres -> pixels on the 100 m grid
    rs = np.arange(0, h + n, n)
    cs = np.arange(0, w + n, n)
    lab = np.full(shape, -1, np.int32)
    k = 0
    for i in range(len(rs) - 1):
        for j in range(len(cs) - 1):
            blk = np.zeros(shape, bool)
            blk[rs[i]:rs[i + 1], cs[j]:cs[j + 1]] = True
            lab[blk & valid] = k
            k += 1
    return lab


def block_buffer(bid: np.ndarray, buffer_px: int) -> np.ndarray:
    """True where the ``buffer_px`` neighbourhood crosses a block boundary."""
    size = 2 * buffer_px + 1
    pos = np.where(bid >= 0, bid + 1, 0)
    pmax = ndimage.maximum_filter(pos, size=size, mode="nearest")
    pmin = ndimage.minimum_filter(np.where(bid >= 0, bid + 1, -1), size=size, mode="nearest")
    return (pmax != pmin) & (bid >= 0)


def make_folds(bid: np.ndarray, k: int = 4, seed: int = SEED) -> np.ndarray:
    """Whole-block folds: every block goes to exactly one fold, so no trace is split."""
    nb = int(bid.max()) + 1
    rng = np.random.default_rng(seed)
    perm = rng.permutation(nb) % k
    fold = np.full(bid.shape, -1, np.int16)
    m = bid >= 0
    fold[m] = perm[bid[m]].astype(np.int16)
    return fold


def build_stack(view: str, valid: np.ndarray, corrob: np.ndarray, persist: dict[str, np.ndarray],
                log=print) -> np.memmap:
    """Write the view's feature stack to ``work/r5/feat<view>.dat`` as float32 memmap."""
    WORK.mkdir(parents=True, exist_ok=True)
    names = feature_names(view)
    path = WORK / f"feat{view}.dat"
    mm = np.memmap(path, dtype=np.float32, mode="w+", shape=(len(names),) + valid.shape)
    raw = VIEW_A_RAW if view == "A" else VIEW_B_RAW
    fams = VIEW_A_FAMS if view == "A" else VIEW_B_FAMS
    for i, (s, b) in enumerate(raw):
        t0 = time.time()
        mm[i] = L.read(s, b, valid=valid)
        mm.flush()
        log(f"    [feat{view}] {names[i]:28s} {time.time() - t0:.1f}s")
    j = len(raw)
    for f in fams:
        z = np.load(WORK / f"fam_{f}.npz")
        mm[j] = np.nan_to_num(z["resp"], nan=0.0)
        log(f"    [feat{view}] {names[j]:28s} from cache")
        j += 1
        del z
    if view == "A":
        a_corr = sum((ndimage.binary_dilation(
            np.load(WORK / f"trace_{f}_0.99.npy"), np.ones((3, 3), bool)).astype(np.int8)
            for f in fams))
        mm[j] = a_corr
        mm[j + 1] = np.max([persist[f] for f in fams], axis=0)
    else:
        b_corr = sum((ndimage.binary_dilation(
            np.load(WORK / f"trace_{f}_0.99.npy"), np.ones((3, 3), bool)).astype(np.int8)
            for f in fams))
        mm[j] = b_corr
        mm[j + 1] = np.max([persist[f] for f in fams], axis=0)
    mm.flush()
    del mm
    return np.memmap(path, dtype=np.float32, mode="r", shape=(len(names),) + valid.shape)


def gather(stack: np.memmap, rows: np.ndarray, cols: np.ndarray, chunk: int = 200_000) -> np.ndarray:
    """Feature matrix at (rows, cols), gathered in sorted row order so the memmap pages in order."""
    n, h, w = stack.shape
    order = np.lexsort((cols, rows))
    r, c = rows[order], cols[order]
    out = np.empty((r.size, n), np.float32)
    for i in range(0, r.size, chunk):
        sl = slice(i, min(i + chunk, r.size))
        out[sl] = stack[:, r[sl], c[sl]].T
    inv = np.empty_like(order)
    inv[order] = np.arange(order.size)
    return out[inv]


def sample_rows(pos: np.ndarray, neg: np.ndarray, allowed: np.ndarray, n_pos: int = 60_000,
                n_neg: int = 240_000, seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed)
    py, px = np.nonzero(pos)
    ny, nx = np.nonzero(neg & allowed)
    if py.size > n_pos:
        sel = rng.choice(py.size, n_pos, replace=False)
        py, px = py[sel], px[sel]
    if ny.size > n_neg:
        sel = rng.choice(ny.size, n_neg, replace=False)
        ny, nx = ny[sel], nx[sel]
    return dict(rows=np.concatenate([py, ny]), cols=np.concatenate([px, nx]),
                y=np.concatenate([np.ones(py.size, np.int8), np.zeros(ny.size, np.int8)]),
                n_pos=int(py.size), n_neg=int(ny.size))


def _model(seed: int = SEED):
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(
        max_iter=160, learning_rate=0.08, max_leaf_nodes=31, min_samples_leaf=40,
        l2_regularization=1.0, early_stopping=False, random_state=seed)


def fit_oof(stack: np.memmap, sample: dict, fold: np.ndarray, buffer: np.ndarray,
            valid: np.ndarray, log=print, tag: str = "") -> tuple[np.ndarray, list[dict]]:
    """Out-of-fold propensity over the whole footprint.

    Each fold's blocks are predicted by a model that never saw them (and never saw a pixel inside
    the fold-boundary buffer), and the union of the folds is the grid, so every emitted pixel is
    scored by a model that could not have memorised it.  Returns the field and per-fold receipts.
    """
    from sklearn.metrics import roc_auc_score
    oof = np.full(valid.shape, np.nan, np.float32)
    rows, cols, y = sample["rows"], sample["cols"], sample["y"]
    # fold[rows, cols], never fold[rows]: indexing a 2-D grid with one 1-D index array selects
    # whole *rows*, which here would silently build a (300k, 3292) int16 array -- 2 GB per view --
    # and then broadcast the fold test over the wrong axis.  Caught by the OOM killer, not by a
    # wrong answer, which is the worse of the two ways to find it.
    rf = fold[rows, cols]
    receipts = []
    for k in range(int(fold.max()) + 1):
        tr = (rf != k) & (~buffer[rows, cols])
        te_block = (fold == k) & valid
        t0 = time.time()
        m = _model()
        m.fit(gather(stack, rows[tr], cols[tr]), y[tr])
        ty, tc = np.nonzero(te_block)
        pr = np.empty(ty.size, np.float32)
        for i in range(0, ty.size, 400_000):
            sl = slice(i, min(i + 400_000, ty.size))
            pr[sl] = m.predict_proba(gather(stack, ty[sl], tc[sl]))[:, 1].astype(np.float32)
        oof[ty, tc] = pr
        held = rf == k
        auc = float(roc_auc_score(y[held], _lookup(oof, rows[held], cols[held])))
        receipts.append(dict(fold=k, train_rows=int(tr.sum()), predicted_px=int(ty.size),
                             held_sample_rows=int(held.sum()), auc=auc,
                             seconds=time.time() - t0))
        log(f"    [oof{tag}] fold {k}: {int(tr.sum())} train rows, {int(ty.size)} predicted px, "
            f"AUC {auc:.4f}, {time.time() - t0:.1f}s")
        del m, pr, ty, tc
    return oof, receipts


def _lookup(field: np.ndarray, rows: np.ndarray, cols: np.ndarray) -> np.ndarray:
    v = field[rows, cols]
    return np.nan_to_num(v, nan=0.5)


def rank_within(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Percentile rank in [0,1] over ``mask``; -1 elsewhere (so a cut cannot pick unmasked px)."""
    out = np.full(a.shape, -1.0, np.float32)
    v = np.asarray(a, np.float64)[mask & np.isfinite(a)]
    if v.size == 0:
        return out
    r = np.argsort(np.argsort(v, kind="stable"), kind="stable").astype(np.float64) / max(v.size - 1, 1)
    idx = np.flatnonzero((mask & np.isfinite(a)).ravel())
    order = np.argsort(np.asarray(a, np.float64).ravel()[idx], kind="stable")
    out.ravel()[idx[order]] = r
    return out


def topk_mask(r: np.ndarray, mask: np.ndarray, k: int) -> np.ndarray:
    """Exactly ``k`` highest-ranked pixels inside ``mask`` (ties broken by index, never by luck)."""
    m = np.asarray(mask, bool) & np.isfinite(r) & (r >= 0)
    idx = np.flatnonzero(m.ravel())
    if idx.size == 0 or k <= 0:
        return np.zeros(np.asarray(r).shape, bool)
    k = min(int(k), idx.size)
    vals = np.asarray(r).ravel()[idx]
    part = np.argpartition(vals, -k)[-k:]
    out = np.zeros(np.asarray(r).shape, bool)
    out.ravel()[idx[part]] = True
    return out


def independence(oof_a: np.ndarray, oof_b: np.ndarray, pos: np.ndarray, neg: np.ndarray,
                 bid: np.ndarray, min_blocks: int = 20, min_px: int = 200) -> dict:
    """The brief's test: correlate the two views' spatial-block OOF errors on labelled negatives.

    A block's *error* for one view is its false-positive rate at that view's own global top-1 %
    threshold, measured on labelled negatives only.  Two views bringing independent evidence make
    independent mistakes; the verdict is on the worst correlation, not the mean, and the threshold
    is the declared 0.60 rather than anything fitted here.
    """
    ra, rb = rank_within(oof_a, pos | neg), rank_within(oof_b, pos | neg)
    thr_a, thr_b = 0.99, 0.99
    fp_a = (ra >= thr_a) & neg
    fp_b = (rb >= thr_b) & neg
    out = {}
    nb = int(bid.max()) + 1
    ea, eb, sizes = [], [], []
    for i in range(nb):
        m = (bid == i) & neg
        n = int(m.sum())
        if n < min_px:
            continue
        ea.append(float(fp_a[m].sum()) / n)
        eb.append(float(fp_b[m].sum()) / n)
        sizes.append(n)
    if len(ea) < min_blocks:
        return dict(n_blocks=len(ea), verdict="insufficient_blocks")
    ea, eb = np.asarray(ea), np.asarray(eb)
    sp = float(spearmanr(ea, eb).statistic)
    pe = float(pearsonr(ea, eb)[0])
    mx = max(abs(sp), abs(pe))
    out = dict(n_blocks=int(ea.size), median_px_per_block=float(np.median(sizes)),
               spearman=sp, pearson=pe, max_abs=mx, threshold=ABANDON_R,
               independent=bool(mx < ABANDON_R),
               verdict="independent" if mx < ABANDON_R else "NOT independent",
               mean_error_a=float(ea.mean()), mean_error_b=float(eb.mean()),
               definition="per-block false-positive rate on labelled negatives at each view's own "
                          "global top-1% OOF rank threshold")
    return out


def disagreement_strata(oof_a: np.ndarray, oof_b: np.ndarray, allowed: np.ndarray,
                        depth: np.ndarray, slope: np.ndarray, hi_q: float = 0.99,
                        lo_q: float = 0.90) -> dict:
    """A-only (buried candidate) and B-only (surface-artefact candidate) populations, measured."""
    ra, rb = rank_within(oof_a, allowed), rank_within(oof_b, allowed)
    a_only = allowed & (ra >= hi_q) & (rb < lo_q)
    b_only = allowed & (rb >= hi_q) & (ra < lo_q)
    both = allowed & (ra >= hi_q) & (rb >= hi_q)

    def prof(m):
        if not m.any():
            return dict(px=0)
        d = depth[m] if depth is not None else np.array([np.nan])
        s = slope[m] if slope is not None else np.array([np.nan])
        return dict(px=int(m.sum()),
                    median_depth_to_basement_m=float(np.nanmedian(d)) if np.isfinite(d).any() else None,
                    median_slope=float(np.nanmedian(s)) if np.isfinite(s).any() else None)
    return dict(a_only=prof(a_only), b_only=prof(b_only), both=prof(both),
                a_only_mask=a_only, b_only_mask=b_only,
                thresholds=dict(hi_q=hi_q, lo_q=lo_q),
                reading="A-only = confident potential-field/subsurface, abstaining surface view: a "
                        "trace with no topographic expression, i.e. buried beneath cover. B-only = "
                        "confident surface, abstaining potential field: a linear feature with no "
                        "subsurface counterpart, i.e. suspect road, canal, erosion line or "
                        "non-tectonic scarp.")


def pseudo_labels(oof_a: np.ndarray, oof_b: np.ndarray, allowed: np.ndarray, fold: np.ndarray,
                  buffer: np.ndarray, hi_q: float = 0.99, lo_q: float = 0.10,
                  whole_segment: bool = True, unit: str = "component",
                  bid: np.ndarray | None = None, min_px: int = 9) -> dict:
    """Donor-confident / receiver-abstaining pseudo-labels, admitted in whole units.

    ``unit`` is the unit the brief's "whole-segment" rule is applied to, and the choice matters more
    than it looks:

    ``"component"`` -- a connected component of the donor-confident/receiver-abstaining set qualifies
      only if the *whole* component has >= ``min_px`` pixels.  This is the strictest reading and it is
      the one that cannot split a trace segment in half.
    ``"block"`` -- a whole 20 km spatial block (``bid``) qualifies if it contains >= ``min_px`` such
      pixels, and then every qualifying pixel inside it is admitted.  This is the literal reading of
      the brief's "whole-segment spatial blocks + buffer": the unit is the block, the buffer keeps a
      qualified block out of the fold that is being predicted.

    Measured on the r5 fields the component rule returns the **empty set in both directions**, and
    that is a result, not a failure: 4,992 px fell in the A-confident/B-abstaining cut, spread over
    4,531 components whose largest member is 5 px.  Independence predicts 0.01 x 0.10 x 4,861,502 =
    4,861 px, so the observed count is 1.03x the independent expectation -- the cut is a sprinkling
    precisely *because* the two views' errors are uncorrelated (spearman 0.150).  A dependent pair
    (r4: max|rho| 0.705) would have produced coherent blobs and a non-empty component rule.  Both
    numbers are reported so the empty set can never be mistaken for a code path that did not run.
    """
    ra, rb = rank_within(oof_a, allowed), rank_within(oof_b, allowed)
    a_to_b = allowed & (ra >= hi_q) & (rb <= lo_q)
    b_to_a = allowed & (rb >= hi_q) & (ra <= lo_q)
    n_allowed = int(allowed.sum())
    expected = (1.0 - hi_q) * lo_q * n_allowed
    out = dict(expected_px_under_independence=float(expected), n_allowed_px=n_allowed,
               unit=unit, min_px=min_px, hi_q=hi_q, lo_q=lo_q)
    for name, m in (("a_to_b", a_to_b), ("b_to_a", b_to_a)):
        raw_px = int(m.sum())
        if whole_segment and unit == "component":
            lab, n = ndimage.label(m, structure=np.ones((3, 3), bool))
            if n:
                sizes = np.bincount(lab.ravel(), minlength=n + 1)
                m = m & np.isin(lab, np.nonzero(sizes >= min_px)[0])
        elif whole_segment and unit == "block":
            if bid is None:
                raise ValueError("unit='block' needs the block-id grid")
            lab, n = ndimage.label(m, structure=np.ones((3, 3), bool))
            cnt = np.bincount(bid[m], minlength=int(bid.max()) + 1) if raw_px else np.array([])
            keep_blocks = np.nonzero(cnt >= min_px)[0] if cnt.size else np.array([], int)
            m = m & np.isin(bid, keep_blocks)
        lab, n = ndimage.label(m, structure=np.ones((3, 3), bool))
        leaks = int((m & buffer).sum())
        out[name] = dict(px=int(m.sum()), raw_px=raw_px, segments=int(n),
                         ratio_to_independence=(raw_px / expected if expected > 0 else None),
                         px_touching_fold_buffer=leaks, leak_free=bool(leaks == 0),
                         mask=m)
    return out


def apply_pseudo_labels(stack: np.memmap, sample: dict, fold: np.ndarray, buffer: np.ndarray,
                        valid: np.ndarray, pl_mask: np.ndarray, pl_label: int,
                        log=print, tag: str = "") -> np.ndarray:
    """Refit with the pseudo-labelled pixels added, and return the new OOF field."""
    from sklearn.metrics import roc_auc_score
    rows, cols, y = sample["rows"], sample["cols"], sample["y"]
    py, px = np.nonzero(pl_mask & valid)
    if py.size == 0:
        return None
    if py.size > 60_000:
        rng = np.random.default_rng(SEED)
        sel = rng.choice(py.size, 60_000, replace=False)
        py, px = py[sel], px[sel]
    rows2 = np.concatenate([rows, py])
    cols2 = np.concatenate([cols, px])
    y2 = np.concatenate([y, np.full(py.size, pl_label, np.int8)])
    f2 = fold[rows2, cols2]
    oof = np.full(valid.shape, np.nan, np.float32)
    for k in range(int(fold.max()) + 1):
        tr = (f2 != k) & (~buffer[rows2, cols2])
        m = _model()
        m.fit(gather(stack, rows2[tr], cols2[tr]), y2[tr])
        te = (fold == k) & valid
        ty, tc = np.nonzero(te)
        pr = np.empty(ty.size, np.float32)
        for i in range(0, ty.size, 400_000):
            sl = slice(i, min(i + 400_000, ty.size))
            pr[sl] = m.predict_proba(gather(stack, ty[sl], tc[sl]))[:, 1].astype(np.float32)
        oof[ty, tc] = pr
        del m, pr
    # comparable AUC: the ORIGINAL labelled rows in fold 0 only.  Scoring the pseudo-labels
    # themselves would measure how well the model reproduces its own donor's confidence, which is
    # the bias-amplification failure mode the brief warns about, not a gain.
    orig = np.arange(rows.size)
    f0 = orig[fold[rows, cols] == 0]
    auc = float(roc_auc_score(y[f0], _lookup(oof, rows[f0], cols[f0])))
    f0b = f2 == 0
    auc_incl = float(roc_auc_score(y2[f0b], _lookup(oof, rows2[f0b], cols2[f0b])))
    log(f"    [pseudo{tag}] {int(py.size)} px added, fold-0 AUC on the original labelled rows "
        f"{auc:.4f} (including pseudo-labels {auc_incl:.4f})")
    return dict(oof=oof, fold0_auc=auc, fold0_auc_including_pseudo=auc_incl,
                added_px=int(py.size))


def baseline_fields(oof_a: np.ndarray, oof_b: np.ndarray) -> dict:
    """The single-view and combined fields the localisation assay compares at matched budget."""
    return dict(A_only=oof_a, B_only=oof_b,
                union_max=np.nanmax(np.stack([oof_a, oof_b]), axis=0),
                mean=np.nanmean(np.stack([oof_a, oof_b]), axis=0),
                disagreement=np.abs(np.nan_to_num(oof_a, nan=0.5) - np.nan_to_num(oof_b, nan=0.5)))


def save_json(path, obj) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, allow_nan=False, default=_fb) + "\n")


def _fb(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)
