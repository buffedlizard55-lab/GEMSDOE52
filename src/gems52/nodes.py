"""Sparse node placement using a fixed, testable spacing heuristic.

The distance kernel is inside the metric, so spreading a prediction over a wide
area can add false-positive mass without useful marginal coverage. It does NOT
follow that every disc is dominated by its centroid, or that 3 px is a universal
optimum: a new dot can increase the maximum cover of a different truth pixel.
This module implements a registered spacing rule; holdout evidence must decide
whether that rule helps at the chosen budget. It never knows the hidden truth.

``gems52.metric.dti`` remains the scoring authority. The independent binary-node
expression below is regression-tested against it, including the empty-set case.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

R_PX = 3.0
OFFSET_WEIGHTS = tuple(
    (dy, dx, 1.0 - (dy * dy + dx * dx) ** 0.5 / R_PX)
    for dy in range(-3, 4) for dx in range(-3, 4)
    if (dy * dy + dx * dx) ** 0.5 <= R_PX + 1e-12
)


def top_k_mask(field: np.ndarray, allowed: np.ndarray, k: int) -> np.ndarray:
    """Boolean mask of the k highest-valued allowed pixels (ties broken by flat index)."""
    f = np.where(allowed, np.nan_to_num(field, nan=0.0, neginf=0.0, posinf=0.0), -np.inf)
    flat = f.ravel()
    k = int(min(max(k, 0), int(allowed.sum())))
    m = np.zeros(flat.size, dtype=bool)
    if k == 0:
        return m.reshape(field.shape)
    idx = np.argpartition(-flat, k - 1)[:k]
    idx = idx[flat[idx] > -np.inf]
    m[idx] = True
    return m.reshape(field.shape)


def local_maxima(field: np.ndarray, allowed: np.ndarray, radius_px: int = 1) -> np.ndarray:
    """Non-maximum suppression: a pixel survives iff it wins its own neighbourhood.

    The winner is decided **lexicographically** -- higher score first, earlier raster index to break
    ties -- which makes the operation deterministic on plateaus (a flat background is one big plateau
    and contributes exactly one survivor, not millions).  A version that tested only
    ``f >= maximum_filter(f)`` was written first and failed ``tests/test_nodes.py`` on a flat field,
    because every background pixel is trivially its own maximum; the tie-break is what fixes it.
    """
    r = int(radius_px)
    f = np.where(allowed, np.nan_to_num(field, nan=0.0, neginf=0.0, posinf=0.0),
                 -np.inf).astype(np.float64)
    idx = np.arange(f.size, dtype=np.int64).reshape(f.shape)
    best = f.copy()
    best_idx = idx.copy()
    big = np.iinfo(np.int64).max
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dy == 0 and dx == 0:
                continue
            sh_f = np.roll(f, shift=(-dy, -dx), axis=(0, 1))
            sh_i = np.roll(idx, shift=(-dy, -dx), axis=(0, 1))
            if dy > 0:
                sh_f[:dy, :] = -np.inf
                sh_i[:dy, :] = big
            elif dy < 0:
                sh_f[dy:, :] = -np.inf
                sh_i[dy:, :] = big
            if dx > 0:
                sh_f[:, :dx] = -np.inf
                sh_i[:, :dx] = big
            elif dx < 0:
                sh_f[:, dx:] = -np.inf
                sh_i[:, dx:] = big
            better = (sh_f > best) | ((sh_f == best) & (sh_i < best_idx))
            best = np.where(better, sh_f, best)
            best_idx = np.where(better, sh_i, best_idx)
    return allowed & np.isfinite(f) & (best_idx == idx) & (f > 0.0)


def thin_plateau(field: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Keep, in every 8-connected plateau of ``mask``, the single raster-first pixel."""
    lab, n = ndimage.label(mask, structure=np.ones((3, 3), dtype=bool))
    if n == 0:
        return mask
    order = np.arange(field.size).reshape(field.shape)
    first = np.full(n + 1, np.iinfo(np.int64).max, dtype=np.int64)
    ids = lab.ravel()
    sel = ids > 0
    np.minimum.at(first, ids[sel], order.ravel()[sel].astype(np.int64))
    return mask & (first[lab] == order)


def tax_of_nodes(nodes: np.ndarray, truth: np.ndarray, r_px: float = R_PX,
                 within: np.ndarray | None = None) -> float:
    """Exact false-positive weight ``FPw`` of a binary node set: ``sum over emitted x of (1 - q_x)``.

    ``q_x = max_g k(d(x, g))`` is the distance from the pixel **x to the nearest TRUTH pixel g** --
    not to the nearest emitted pixel.  (A first version of this function used the distance to the
    emitted set, which makes every node its own neighbour at distance 0, hence ``q = 1``, hence a tax
    of identically zero; ``tests/test_nodes.py::test_tax_identity_matches_the_metric_definition``
    caught it by comparing against the published ``FPw`` on random fields.)  A pixel exactly on a
    truth pixel therefore pays nothing, a pixel one cell away pays ``0.2/3``, and a pixel beyond
    300 m pays the full ``0.2``.

    ``within`` optionally restricts the sum to the scored region (a fold's region, say).
    """
    t = truth.astype(bool)
    n = nodes.astype(bool)
    if within is not None:
        n = n & within
    if not n.any():
        return 0.0
    d = ndimage.distance_transform_edt(~t) if t.any() else np.full(n.shape, np.inf)
    q = np.maximum(1.0 - d / r_px, 0.0)
    return float((1.0 - q)[n].sum())


def node_credit(nodes: np.ndarray, truth: np.ndarray, r_px: float = R_PX) -> tuple[float, float]:
    """(T, |G|) of a binary node set against a truth mask, using the official kernel exactly."""
    t = truth.astype(bool)
    n = nodes.astype(bool)
    if not t.any():
        return 0.0, 0.0
    # max over emitted nodes of p*k(d): EDT to the node set, kernel applied
    d = ndimage.distance_transform_edt(~n)
    k = np.maximum(1.0 - d / r_px, 0.0)
    T = float(k[t].sum())
    return T, float(t.sum())


def node_dti(nodes: np.ndarray, truth: np.ndarray, valid: np.ndarray | None = None,
             r_px: float = R_PX, alpha: float = 0.2, beta: float = 0.8) -> dict:
    """Official DTI of a binary node emission (independent of ``gems52.metric`` on purpose).

    ``gems52.metric.dti`` remains the authority for scoring submissions and folds; this function is
    the *node-space* expression of the same formula (``FNw = |G| - T`` identically) and the two are
    asserted equal in ``tests/test_nodes.py`` on random small fields, so a divergence cannot pass
    silently.

    One deliberate difference: with an empty truth mask ``gems52.metric.dti`` returns ``0.0`` by
    convention, while this returns ``NaN``, so a caller cannot mistake "there was nothing to score"
    for "the score is zero".
    """
    n = nodes.astype(bool)
    t = truth.astype(bool) if valid is None else (truth & valid)
    if not t.any():
        return {"dti": float("nan"), "T": 0.0, "G": 0.0, "nodes": int(n.sum())}
    T, G = node_credit(n, t, r_px)
    tax = tax_of_nodes(n, t, r_px, within=valid)
    den = alpha * tax + beta * G + alpha * T
    return {"dti": float(T / den) if den > 0 else 0.0, "T": T, "G": G, "tax": tax,
            "nodes": int(n.sum())}


def nodes_to_grid(rows: np.ndarray, cols: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    out = np.zeros(shape, dtype=np.float32)
    out[rows, cols] = 1.0
    return out


def grid_to_nodes(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ys, xs = np.nonzero(mask)
    return ys.astype(np.int64), xs.astype(np.int64)


def spacing_stats(nodes: np.ndarray, sample: int = 200_000, seed: int = 0) -> dict:
    """Nearest-neighbour spacing of a node set, in pixels -- the price of the emission, measured."""
    ys, xs = np.nonzero(nodes)
    n = ys.size
    if n < 2:
        return {"n": int(n), "median_px": None}
    if n > sample:
        rng = np.random.default_rng(seed)
        sel = rng.choice(n, sample, replace=False)
        ys, xs = ys[sel], xs[sel]
    pts = np.stack([ys.astype(np.float64), xs.astype(np.float64)], axis=1)
    from scipy.spatial import cKDTree
    tree = cKDTree(pts)
    d, _ = tree.query(pts, k=2)
    nn = d[:, 1]
    return {"n": int(n), "median_px": float(np.median(nn)),
            "p10_px": float(np.percentile(nn, 10)), "p90_px": float(np.percentile(nn, 90)),
            "share_within_1px": float((nn <= 1.0 + 1e-9).mean()),
            "share_within_2px": float((nn <= 2.0 + 1e-9).mean())}


def spacing_select(score: np.ndarray, allowed: np.ndarray, k: int, min_px: float = 3.0,
                   log=None) -> np.ndarray:
    """Greedy top-k with fixed minimum separation, a metric-motivated heuristic.

    Separation reduces redundant local coverage but can also reduce useful recall;
    3 px is not a proven optimum. Scores and spacing are fixed before evaluation.
    A bucket grid checks all neighbouring buckets exactly; ties use flat index.
    """
    idx = np.flatnonzero(allowed.ravel())
    if idx.size == 0 or k <= 0:
        return np.zeros(score.shape, dtype=bool)
    val = np.nan_to_num(score.ravel()[idx], nan=-np.inf, neginf=-np.inf, posinf=np.inf)
    order = np.lexsort((idx, -val))
    h, w = score.shape
    cell = max(1.0, float(min_px))
    keep = np.zeros(score.shape, dtype=bool)
    buckets: dict[tuple[int, int], list[tuple[float, float]]] = {}
    taken = 0
    r_ceil = int(np.ceil(cell))
    d2 = cell * cell
    for pos in order:
        if val[pos] == -np.inf:
            break
        flat = int(idx[pos])
        y, x = divmod(flat, w)
        cy, cx = int(y // cell), int(x // cell)
        ok = True
        for gy in range(cy - 1, cy + 2):
            for gx in range(cx - 1, cx + 2):
                for (py, px) in buckets.get((gy, gx), ()):      # noqa: E501
                    if (py - y) ** 2 + (px - x) ** 2 < d2:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if not ok:
            continue
        keep[y, x] = True
        buckets.setdefault((cy, cx), []).append((y, x))
        taken += 1
        if taken >= k:
            break
    if log:
        log(f"spacing_select: kept {taken} of a requested {k} at min separation {min_px} px")
    return keep


def emit_nodes(score: np.ndarray, allowed: np.ndarray, k: int, min_px: float = 3.0,
               log=None) -> np.ndarray:
    """Binary {0,1} node emission: greedy top-k under a minimum separation (see :func:`spacing_select`)."""
    return spacing_select(score, allowed, k, min_px=min_px, log=log).astype(np.float32)


# ---------------------------------------------------------------------------------------------
# H87: emission placed by the metric's OWN marginal acceptance rule, with no hand-chosen budget.
# ---------------------------------------------------------------------------------------------
def kernel7() -> np.ndarray:
    """7x7 array ``W`` with ``W[3+dy, 3+dx] = k(|offset|)``: the metric's exact lattice weights."""
    W = np.zeros((7, 7), np.float64)
    for dy, dx, w in OFFSET_WEIGHTS:
        W[3 + dy, 3 + dx] = w
    return W


def cover_of(dots: np.ndarray) -> np.ndarray:
    """C(x) = max over chosen dots of k(d(x,p)), the cover field of an emitted set (exact, by EDT)."""
    d = ndimage.distance_transform_edt(~dots.astype(bool))
    return np.maximum(1.0 - d / R_PX, 0.0)


def hexagonal_tiebreak(shape: tuple[int, int], spacing_px: float = 6.0) -> np.ndarray:
    """Distance to the nearest node of a hexagonal (triangular) lattice, for gain tie-breaking.

    Measured reason this exists: the organiser-side calibration raster
    ``data/scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif`` (206,895 dots, nearest-
    neighbour median 5.00 px, 99.85 % of the footprint inside 300 m of a dot, mean cover 0.3748,
    owner-reported board score 0.0904) is a *staggered* packing.  A square packing at the same
    nearest-neighbour distance covers strictly less per dot: its cell centre sits at 0.707*a* from
    the four corners, so a 5 px square lattice leaves ~5 % of the area outside the 300 m kernel and
    averages ~0.32 cover, where the staggered packing reaches 0.3748.  Greedy selection over a
    uniform density breaks ties by raster index, which produces rows -- a square packing -- and
    therefore loses ~8 % of the achievable DTI.  Adding ``-eps * d_hex`` to the gain field resolves
    ties toward the staggered packing without reordering genuinely different gains.
    """
    h, w = shape
    a = max(1.0, float(spacing_px))
    row_step = max(1, int(round(a * np.sqrt(3.0) / 2.0)))
    lat = np.zeros(shape, bool)
    r = 0
    y = 0
    while y < h:
        offset = (r % 2) * int(round(a / 2.0))
        x = offset % max(1, int(round(a)))
        while x < w:
            lat[y, x] = True
            x += int(round(a))
        y += row_step
        r += 1
    if not lat.any():
        return np.zeros(shape, np.float64)
    return ndimage.distance_transform_edt(~lat).astype(np.float64)


def marginal_gain_field(g: np.ndarray, cover: np.ndarray) -> np.ndarray:
    """Marginal credit of adding one dot at every pixel, exactly, under the current cover.

    ``gain(p) = sum_x g(x) * max(0, k(d(x,p)) - C(x))``.  Only the 29 lattice offsets inside the
    300 m disc can contribute, so this is 29 shifted elementwise products -- no approximation and
    no separable shortcut.  ``g`` must carry truth MASS (sum(g) = |G| in truth-pixel units), not a
    normalised density, because the acceptance bar ``alpha*DTI`` is scale-dependent.
    """
    W = kernel7()
    out = np.zeros(g.shape, np.float64)
    for dy, dx, w in OFFSET_WEIGHTS:
        if w <= 0.0:
            continue
        # room(p) = max(0, w - C(p+o)) weighted by g(p+o); shift g*room back by -o
        room = np.maximum(0.0, w - cover)
        term = g * room
        out += np.roll(np.roll(term, dy, axis=0), dx, axis=1)
    # zero the wrap-around border that np.roll introduces
    out[:3, :] = out[-3:, :] = 0.0
    out[:, :3] = out[:, -3:] = 0.0
    del W
    return out


def marginal_greedy(g: np.ndarray, allowed: np.ndarray, *, max_dots: int = 400_000,
                    min_sep_px: float = 3.0, alpha: float = 0.2, beta: float = 0.8,
                    round_cap: int = 40_000, max_cycles: int = 60, hexagonal_packing: bool = True,
                    tiebreak_eps: float = 1e-6, mass_outside_allowed: float = 0.0,
                    log=None) -> dict:
    """Greedy emission that stops where the metric stops paying: add a dot iff its marginal credit
    ``c`` satisfies ``c > alpha * DTI`` (``gems52.metric`` docstring part (ii) with the identity
    ``DTI = T / (alpha*S + beta*|G|)``).  The budget is *derived*, never chosen by hand.

    ``T(X) = sum_x g(x) max_{p in X} k(d(x,p))`` is monotone submodular, so greedy is the standard
    near-optimal rule.  Exactness of the marginal accounting is the whole difficulty: a gain field
    computed once per round is stale for every dot added later *in that round*, and a round that
    adds a maximal 3-px-separated set at a stale zero cover over-fills by ~2.6x (measured: the
    first version of this function stopped at a 3.07 px lattice with DTI 0.0643 where the metric's
    own optimum for the same uniform density is a ~5 px lattice at DTI 0.0904 -- the spacing of the
    pinned organiser-side ``r13-lattice-s5`` calibration raster, which scored 0.0904 on the board).

    The fix is a multi-scale separation schedule.  Two dots at least ``2*R_PX = 6`` px apart have
    *disjoint* kernel discs, so their marginal gains are exactly additive and the within-round
    prefix test ``gain_(k) > alpha*DTI_k`` is exact rather than stale.  The schedule therefore runs
    wide rounds (6 px) first and then tight rounds (``min_sep_px``), cycling until a full cycle adds
    nothing.  ``T``, ``DTI`` and the cover are recomputed exactly from the emitted set after every
    round and re-derived from the final mask at the end, so no reported number is a batch
    approximation -- only the insertion *order* inside a tight round is.

    ``g`` must carry truth MASS (``sum(g) = |G|`` in truth-pixel units), not a normalised density:
    the bar ``alpha*DTI`` is scale-dependent through DTI's denominator.
    """
    g = np.asarray(g, np.float64)
    allowed = np.asarray(allowed, bool)
    if g.shape != allowed.shape:
        raise ValueError("g and allowed must share a shape")
    gA = np.where(allowed, g, 0.0)
    if mass_outside_allowed < 0:
        raise ValueError("mass_outside_allowed cannot be negative")
    # Truth mass that exists but cannot be emitted (e.g. density fitted onto catalogue pixels while
    # the emission domain is the off-catalogue collar).  It contributes nothing to T but it does
    # contribute to FNw, so it belongs in DTI's denominator and therefore in the acceptance bar.
    # Leaving it out would silently lower the bar and over-emit.
    Gtot = float(gA.sum()) + float(mass_outside_allowed)
    if Gtot <= 0:
        raise ValueError("no truth mass at all")
    if float(gA.sum()) <= 0:
        raise ValueError("no allowed pixel carries truth mass")
    # 6 px = disjoint kernel discs (gains exactly additive); 5 px and min_sep are tighter infills
    # whose within-round prefix test is mildly optimistic, which is why every round is rolled back
    # if the EXACT recomputed DTI fell.  The objective is therefore monotone by construction.
    schedule = sorted({max(float(2 * R_PX), float(min_sep_px)), 5.0, float(min_sep_px)}, reverse=True)
    schedule = [s for s in schedule if s >= float(min_sep_px)]
    # The keep-out ring is the HARD separation constraint (min_sep_px), identical for every round.
    # A per-round keep-out sized to the round's own wider separation was the first version here and
    # it silently blocked all infill: after a 6 px round an 11x11 keep-out left no candidate at all,
    # so the schedule degenerated to one round.
    r = int(np.ceil(min_sep_px))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    keepout = (yy * yy + xx * xx) <= float(min_sep_px) ** 2 + 1e-9   # EUCLIDEAN disc, not a square
    dots = np.zeros(g.shape, bool)
    C = np.zeros(g.shape, np.float64)
    T = 0.0
    added = 0
    history = []
    stop = "max_cycles"
    rnd = 0
    for cycle in range(max_cycles):
        added_this_cycle = 0
        for si, sep in enumerate(schedule):
            gain = marginal_gain_field(gA, C)
            if hexagonal_packing and gain.max() > 0:
                # ties only: eps * max_gain * d_hex is far below any real gain difference
                if "hex_tb" not in locals():
                    hex_tb = hexagonal_tiebreak(g.shape, spacing_px=schedule[0])
                gain = gain - tiebreak_eps * float(gain.max()) * hex_tb
            dti = T / (alpha * added + beta * Gtot) if added else 0.0
            bar = alpha * dti
            cand = (gain > bar) & allowed & ~dots
            if dots.any():
                cand &= ~ndimage.binary_dilation(dots, structure=keepout)
            if not cand.any():
                history.append(dict(round=rnd, sep_px=sep, new_dots=0, added_total=added,
                                    T=round(T, 4), dti=round(dti, 6), bar=round(bar, 8),
                                    best_gain=round(float(gain.max()), 8), note="no candidate"))
                rnd += 1
                continue
            k_round = int(min(round_cap, max_dots - added))
            if k_round <= 0:
                stop = "max_dots"
                break
            peaks = spacing_select(gain, cand, k_round, min_px=sep)
            idx = np.flatnonzero(peaks.ravel())
            if idx.size == 0:
                history.append(dict(round=rnd, sep_px=sep, new_dots=0, added_total=added,
                                    T=round(T, 4), dti=round(dti, 6), bar=round(bar, 8),
                                    best_gain=round(float(gain.max()), 8), note="no separated peak"))
                rnd += 1
                continue
            order = idx[np.argsort(-gain.ravel()[idx])]
            gains = gain.ravel()[order]
            # exact prefix test: at 6 px separation the gains are additive, so DTI_k is exact
            cumT = T + np.cumsum(gains)
            kk = np.arange(1, order.size + 1, dtype=np.float64)
            dti_k = cumT / (alpha * (added + kk) + beta * Gtot)
            ok = gains > alpha * dti_k
            if not ok[0]:
                history.append(dict(round=rnd, sep_px=sep, new_dots=0, added_total=added,
                                    T=round(T, 4), dti=round(dti, 6), bar=round(bar, 8),
                                    best_gain=round(float(gains[0]), 8),
                                    note="best marginal credit did not clear alpha*DTI"))
                rnd += 1
                continue
            n_take = int(np.argmin(ok)) if (~ok).any() else int(ok.size)
            sel = order[:n_take]
            batch = np.zeros(g.shape, bool)
            batch.ravel()[sel] = True
            prev = (dots.copy(), C.copy(), T, added)
            dots |= batch
            C = np.maximum(C, _stamp_cover(batch))
            added += n_take
            T = float((gA * C).sum())                     # exact, from the emitted set
            dti_new = T / (alpha * added + beta * Gtot)
            dti_old = prev[2] / (alpha * prev[3] + beta * Gtot) if prev[3] else 0.0
            if dti_new < dti_old:                          # tighter round over-filled: revert
                dots, C, T, added = prev
                history.append(dict(round=rnd, sep_px=sep, new_dots=0, added_total=added,
                                    T=round(T, 4), dti=round(dti_old, 6),
                                    note="rolled back: exact DTI fell from "
                                         f"{dti_old:.6f} to {dti_new:.6f}"))
                rnd += 1
                continue
            dti = dti_new
            added_this_cycle += n_take
            history.append(dict(round=rnd, sep_px=sep, new_dots=n_take, added_total=added,
                                T=round(T, 4), dti=round(dti, 6), bar=round(alpha * dti, 8),
                                best_gain=round(float(gains[0]), 8),
                                worst_taken_gain=round(float(gains[n_take - 1]), 8)))
            if log:
                log(f"  marginal_greedy r{rnd} sep={sep}: +{n_take} -> {added} dots, "
                    f"T={T:.1f}, DTI={dti:.5f}, bar={alpha * dti:.6f}")
            rnd += 1
            if added >= max_dots:
                stop = "max_dots"
                break
        if stop == "max_dots":
            break
        if added_this_cycle == 0:
            stop = "marginal_rule"
            break
    C = cover_of(dots)                                    # exact cover re-derived from the mask
    T = float((gA * C).sum())
    dti = T / (alpha * added + beta * Gtot) if added else 0.0
    return dict(dots=dots, n_added=int(added), T=T, G=Gtot, predicted_dti=float(dti),
                stop_reason=stop, rounds=history, min_sep_px=float(min_sep_px),
                separation_schedule_px=schedule, kernel_radius_px=R_PX,
                mass_outside_allowed=float(mass_outside_allowed),
                rule="add a dot iff its marginal credit exceeds alpha*DTI; budget is derived",
                evidence_class="PREDICTED-BOARD under the supplied density g (a model projection, "
                               "never a score)")


def _stamp_cover(peaks: np.ndarray) -> np.ndarray:
    """Cover field contributed by a batch of new dots, built from the exact 29-offset kernel."""
    out = np.zeros(peaks.shape, np.float64)
    p = peaks.astype(np.float64)
    for dy, dx, w in OFFSET_WEIGHTS:
        if w <= 0.0:
            continue
        out = np.maximum(out, np.roll(np.roll(p, dy, axis=0), dx, axis=1) * w)
    out[:3, :] = np.maximum(out[:3, :], 0.0)
    return out
