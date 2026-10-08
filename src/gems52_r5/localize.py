"""The localisation assay: hold out whole real fault traces and measure *lateral error*.

Why this instrument exists
--------------------------
This repository has two prior instruments and both are on the record as unusable for promotion:

* the dispersed pseudo-truth instrument -- uniform random beats the 0.2778 champion on it at the
  same budget and at half of it (``knowledge/23`` §3, issue #31), because it measures emission
  size, not geology;
* the whole-component hide-and-recover *capture* assay -- Spearman -0.1045 (p = 0.734, n = 13)
  against the reported scores of the thirteen restored rasters, with the champion the worst of the
  thirteen locally and the best of them on the board (``knowledge/10`` §5, ``knowledge/03`` N-9).

R5 keeps the hide geometry of the second instrument -- whole catalogue components held out, a
buffer around them removed from anything that could see them, emission allowed inside the hidden
area -- and changes *what is measured*.  Capture answers "what fraction of the hidden truth did we
touch", which conflates kernel geometry with geology and is budget-dependent by construction.
Lateral error answers "when we touch a trace, how far are we from it", which is the only thing the
300 m triangular kernel pays for: a dot on a straight trace earns 2.25-3.0 truth-pixel-credits, the
same dot 1 px off earns 1.70, 2 px off earns 0.83, 3 px off earns nothing
(:func:`gems52_r5.traces.ribbon_credit`, checked against :func:`gems52.metric.dti` in
``tests/test_r5.py``).

The assay reports, for each candidate emission and each fold:

* the exact lattice-distance distribution from emitted dot to the nearest hidden truth pixel
  (the metric's own seven kernel values, no interpolation);
* ``q`` = the fraction of dots inside the kernel disc at all, and the credit-per-dot and
  cover-per-dot that the measured distribution implies through the ribbon model;
* the exact simulator DTI against the fold's own truth, for continuity with earlier rounds.

What it cannot do
-----------------
The hidden truth is *unmapped* faults; a held-out catalogue component is a *mapped* one, with the
surface expression that got it mapped.  Measured skill is therefore an upper bound, and
:func:`project` carries an explicit discount factor ``delta`` for exactly that gap, reporting the
projection at delta = 1, 0.5 and 0.25 instead of pretending to know it.  A high assay number is
evidence about mechanism, not a leaderboard forecast.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from gems52 import metric as M
from gems52_r5 import traces as T

STRUCT8 = np.ones((3, 3), bool)
BINS = 13                      # 0.00, 0.25, ... , 3.00 px lateral error


def component_folds(cat: np.ndarray, valid: np.ndarray, n_folds: int = 4,
                    seed: int = 20261009) -> np.ndarray:
    """Assign whole catalogue components to folds, size-balanced and spatially spread.

    A pixel-level split would put a trace in both train and test and the 300 m kernel would forgive
    it (``gems52.grid.block_labels`` makes the same point for blocks).  Components are labelled
    8-connected, given a spatial block id by their centroid, then dealt round-robin to folds in
    descending size order *within* each block, so every fold gets a similar mix of sizes and of
    positions.  Deterministic in ``seed``.
    """
    comp, n = ndimage.label(cat & valid, structure=STRUCT8)
    if n == 0:
        return np.full(cat.shape, -1, np.int16)
    rng = np.random.default_rng(seed)
    # bincount is indexed by component id, and ids run 1..n, so every per-component array here is
    # length n+1 with slot 0 unused; slicing [1:] *after* the division, never before, is what keeps
    # the two sides the same length (an earlier version sliced ``sizes`` first and then divided a
    # length-(n+1) centroid sum by a length-n size vector)
    sizes = np.bincount(comp.ravel(), minlength=n + 1)[1:]
    # centroid block, so the four folds are geographically interleaved rather than quartered
    ys, xs = np.nonzero(comp)
    cids = comp[ys, xs]
    cy = np.bincount(cids, weights=ys, minlength=n + 1)[1:] / np.maximum(sizes, 1)
    cx = np.bincount(cids, weights=xs, minlength=n + 1)[1:] / np.maximum(sizes, 1)
    h, w = cat.shape
    block = (np.clip(cy // max(h / n_folds, 1), 0, n_folds - 1) * n_folds
             + np.clip(cx // max(w / n_folds, 1), 0, n_folds - 1))
    jitter = rng.random(n)
    uniq_ids = np.arange(1, n + 1)
    fold_of = np.zeros(n + 1, np.int16)
    counts = np.zeros(n_folds, np.int64)
    # deal the largest components first to the currently lightest fold (greedy balance by pixels),
    # ties broken inside the component's own spatial block so folds stay geographically interleaved
    for cid in uniq_ids[np.lexsort((jitter, block, -sizes[uniq_ids - 1]))]:
        f = int(np.argmin(counts))
        fold_of[cid] = f
        counts[f] += sizes[cid - 1]
    out = np.full(cat.shape, -1, np.int16)
    m = comp > 0
    out[m] = fold_of[comp[m]]
    return out


def fold_masks(cat: np.ndarray, valid: np.ndarray, fold_id: np.ndarray, k: int,
               buffer_px: int = 4) -> dict:
    """One fold's truth, its visible catalogue, the training-exclusion buffer and the legal set.

    Two masks that earlier rounds conflated, kept separate on purpose (``knowledge/23`` §4): the
    *visible* catalogue is what the 200 m ring rule may use, and it must not contain the hidden
    truth, or the hidden truth becomes unplaceable; the *legal* emission set is the footprint minus
    the ring around the visible catalogue.
    """
    hidden = (fold_id == k) & cat
    visible = cat & ~hidden
    d_vis = ndimage.distance_transform_edt(~visible, sampling=100.0)
    legal = valid & (d_vis > 200.0)
    excl = ndimage.binary_dilation(hidden, STRUCT8, iterations=buffer_px)
    survival = float((hidden & legal).sum()) / max(float(hidden.sum()), 1.0)
    return dict(fold=k, hidden=hidden, visible=visible, dist_visible=d_vis, legal=legal,
                train_exclusion=excl, hidden_px=int(hidden.sum()), legal_px=int(legal.sum()),
                truth_survival_in_legal=survival)


def distance_bins(dots: np.ndarray, truth: np.ndarray) -> dict:
    """Lattice-distance distribution from each emitted dot to the nearest hidden truth pixel."""
    if not dots.any():
        return dict(n_dots=0, q=0.0, hist=[0.0] * BINS, mean_kernel=0.0)
    edt = ndimage.distance_transform_edt(~truth, sampling=1.0)     # sampling=1 -> distances in px
    d = edt[dots]
    idx = np.clip(np.floor(d / 0.25).astype(int), 0, BINS - 1)
    hist = np.bincount(idx, minlength=BINS).astype(float)
    hist /= max(hist.sum(), 1.0)
    k = M.kernel(d * 100.0)
    inside = d < 3.0 + 1e-9
    return dict(n_dots=int(dots.sum()),
                q=float(inside.mean()),
                q_within_1px=float((d <= 1.0 + 1e-9).mean()),
                q_within_2px=float((d <= 2.0 + 1e-9).mean()),
                mean_lattice_dist_px=float(d.mean()),
                median_lattice_dist_px=float(np.median(d)),
                mean_kernel_cover=float(k.mean()),
                hist=[float(x) for x in hist])


def assay(emitted: np.ndarray, fold: dict) -> dict:
    """Exact simulator score plus the lateral-error decomposition, for one emission on one fold."""
    truth = fold["hidden"]
    p = np.where(emitted > 0, np.minimum(np.maximum(emitted, 0.0), 1.0), 0.0).astype(np.float64)
    res = M.dti(p, truth)
    dots = emitted > 0
    db = distance_bins(dots, truth)
    proj_credit = T.expected_credit(np.array(db["hist"])) if db["n_dots"] else 0.0
    proj_cover = T.expected_cover(np.array(db["hist"])) if db["n_dots"] else 0.0
    res.update(q=db["q"], q_within_1px=db.get("q_within_1px"), mean_lattice_dist_px=db["mean_lattice_dist_px"],
               hist=db["hist"], ribbon_credit_per_dot=proj_credit, ribbon_cover_per_dot=proj_cover,
               emitted_px=int(dots.sum()), hidden_px=int(truth.sum()),
               capture=float((ndimage.binary_dilation(dots, STRUCT8, iterations=3) & truth).sum()
                             / max(int(truth.sum()), 1)))
    return res


def place_dots(score: np.ndarray, allowed: np.ndarray, budget: int, min_sep_px: float = 3.0,
               jitter_seed: int | None = None, prefilter: bool = True,
               scan_cap: int | None = None) -> np.ndarray:
    """Top-``budget`` dots by ``score`` inside ``allowed``, thinned to ``min_sep_px`` separation.

    Two modes, because they answer different questions and the localisation assay has to be able to
    compare them:

    ``prefilter=True`` (peak mode) -- a ``maximum_filter`` of radius ``ceil(min_sep)-1`` keeps only
      local maxima of the rank field first, which is vectorised and cheap, and then an exact greedy
      pass enforces the Euclidean separation.  Peaks of a smooth field are scattered, so this mode
      spends its budget on the *strongest places*, not on following a trace.
    ``prefilter=False`` (ridge mode) -- no peak test: the greedy walks the candidate pool in rank
      order and accepts a pixel whenever nothing accepted is within ``min_sep_px``.  On a one-pixel
      wide trace this walks *along* the trace and lands dots every ``min_sep_px`` pixels, which is
      what fills the kernel ribbon (:func:`gems52_r5.traces.ribbon_credit`).

    Ties break by row-major index, which is deterministic and needs no RNG stream; pass
    ``jitter_seed`` only to randomise them (the key is added at 1e-9, which needs the float64 score
    to be visible at all, so it cannot be combined with a float32 field).
    A shortfall is recorded on the function object rather than silently filled by relaxing the
    separation, and ``scan_cap`` bounds the greedy walk so a million-pixel pool cannot stall it.
    """
    # one float64 allocation, not three: ``np.where(...).astype(float64)`` on a float32 field
    # peaked at ~300 MB of temporaries per call, and stage 5 makes 280 of them.
    s = np.full(score.shape, -np.inf, np.float64)
    np.copyto(s, score, where=allowed)
    s[~np.isfinite(s)] = -np.inf
    if jitter_seed is not None:
        rng = np.random.default_rng(jitter_seed)
        s += rng.random(s.shape) * 1e-9
    if budget <= 0 or not np.isfinite(s).any():
        place_dots.last_shortfall = (0, int(budget), 0)
        return np.zeros(s.shape, bool)
    r = max(int(np.ceil(min_sep_px)), 1)
    r_pre = max(r - 1, 1) if prefilter else 0
    if r_pre:
        peaks = (s >= ndimage.maximum_filter(s, size=2 * r_pre + 1, mode="nearest")) & np.isfinite(s)
        idx = np.flatnonzero(peaks.ravel())
    else:
        idx = np.flatnonzero(np.isfinite(s).ravel())
    if idx.size == 0:
        place_dots.last_shortfall = (0, int(budget), 0)
        return np.zeros(s.shape, bool)
    vals = s.ravel()[idx]
    # The greedy walk rejects most of what it scans (a ranked field is spatially clustered, and
    # random-sequential adsorption accepts only ~1 pixel in 7 at a 3-px exclusion), so cutting the
    # candidate list to ``budget`` would cap the emission at ~budget/7.  Cut to ``scan_cap``
    # instead and let the greedy stop when the budget is actually reached.
    cap = int(scan_cap) if scan_cap else max(40 * budget, 300_000)
    if idx.size > cap:
        part = np.argpartition(vals, -cap)[-cap:]
        idx, vals = idx[part], vals[part]
    order = np.lexsort((idx, -vals))
    idx = idx[order]
    h, w = s.shape
    taken = np.zeros(s.shape, bool)
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    disc = (yy ** 2 + xx ** 2) <= (min_sep_px ** 2 + 1e-9)
    chosen = 0
    for k in idx:
        if chosen >= budget:
            break
        y, x = divmod(int(k), w)
        y0, y1 = max(0, y - r), min(h, y + r + 1)
        x0, x1 = max(0, x - r), min(w, x + r + 1)
        sub = disc[y0 - (y - r):y1 - (y - r), x0 - (x - r):x1 - (x - r)]
        if taken[y0:y1, x0:x1][sub].any():
            continue
        taken[y, x] = True
        chosen += 1
    place_dots.last_shortfall = (chosen, int(budget), int(idx.size))
    return taken


def project(assay_rows: list[dict], g_px: float, deltas: tuple[float, ...] = (1.0, 0.5, 0.25),
            target: float = 0.3195) -> dict:
    """Turn measured credit-per-dot and cover-per-dot into a projected DTI at the real ``|G|``.

    ``delta`` is the unmapped-vs-mapped discount: 1.0 says hidden truth is exactly as findable as a
    held-out mapped trace, 0.25 says it is four times harder.  Nothing here knows which is right, so
    all three are reported and the win probability is integrated over them with equal weight.
    """
    out = []
    for row in assay_rows:
        s = int(row["emitted_px"])
        rho = float(row.get("ribbon_credit_per_dot", 0.0))
        gamma = float(row.get("ribbon_cover_per_dot", 0.0))
        rec = dict(budget=s, measured_credit_per_dot=rho, measured_cover_per_dot=gamma,
                   q=row.get("q"), simulator_dti=row.get("dti"))
        wins = []
        for d in deltas:
            t = min(d * rho * s, g_px)
            m = d * gamma * s
            den = 0.2 * (t + s - m) + 0.8 * g_px
            dti = t / den if den > 0 else 0.0
            rec[f"projected_dti_delta{d:g}"] = dti
            wins.append(dti > target)
        rec["p_beat_target"] = float(np.mean(wins))
        rec["target"] = target
        out.append(rec)
    return dict(g_px=g_px, deltas=list(deltas), rows=out,
                best_by_delta={f"{d:g}": max((r[f"projected_dti_delta{d:g}"], r["budget"])
                                             for r in out)[1] if out else None for d in deltas})
