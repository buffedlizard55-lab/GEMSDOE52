"""Metric-aware emission: choose *which* pixels to emit, not what to call them.

Why this is the whole game here (and it is proved, not asserted -- ``tests/test_metric.py``):

    DTI = T / (0.2*(T + S - M) + 0.8*|G|),  T = sum_g max_x p(x) k(d(x,g))

so with p in {0,1} the score depends only on the emitted *set*, one truth pixel is credited once
per covering pixel (a single dot can be the best cover of several truth pixels, which is why
step-overs and parallel-strand corridors are cheap and wide ridgelines are expensive), and
redundant mass is free at best and costly otherwise.

The rule used to stop adding pixels is the exact marginal condition of that DTI:

    accept x  <=>  gain(x) > [alpha*DTI / (1 - alpha*DTI)] * (1 - wmax(x))

with ``gain(x) = sum_g rho_g * max(0, k(d(x,g)) - m_g)`` the incremental expected credit and
``wmax(x) = max_g k(d(x,g))`` the pixel's own false-positive discount.  For a pixel covering one
uncovered truth pixel at weight w this collapses to ``w > alpha*DTI``, the credit bar.

Greedy on a monotone submodular coverage function carries the standard 1 - 1/e guarantee; it is
used here because the objective *is* the metric's own numerator.
"""

from __future__ import annotations

import numpy as np

R_PX = 3
OFFSETS = [(dy, dx, 1.0 - (dy * dy + dx * dx) ** 0.5 / R_PX)
           for dy in range(-R_PX, R_PX + 1) for dx in range(-R_PX, R_PX + 1)
           if (dy * dy + dx * dx) ** 0.5 <= R_PX + 1e-12]


def accept_bar(dti: float, alpha: float = 0.2) -> float:
    """The ``alpha*DTI / (1 - alpha*DTI)`` multiplier in the marginal rule (see module docstring)."""
    d = 1.0 - alpha * dti
    return float(alpha * dti / d) if d > 0 else float("inf")


def _neighbour_tables(cands: np.ndarray, shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """(flat neighbour indices, kernel weights) for each candidate; -1 where out of bounds."""
    h, w = shape
    r, c = cands // w, cands % w
    nb = np.full((cands.size, len(OFFSETS)), -1, dtype=np.int64)
    kk = np.zeros((cands.size, len(OFFSETS)), dtype=np.float32)
    for j, (dy, dx, k) in enumerate(OFFSETS):
        yy = r + dy
        xx = c + dx
        ok = (yy >= 0) & (yy < h) & (xx >= 0) & (xx < w)
        nb[ok, j] = (yy[ok] * w + xx[ok]).astype(np.int64)
        kk[ok, j] = k
    return nb, kk


def gain_field(density: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """First-pass expected credit of every pixel: (density * kernel) summed over the disc."""
    h, w = shape
    d = density.reshape(h, w)
    out = np.zeros((h, w), dtype=np.float32)
    for dy, dx, k in OFFSETS:
        s = np.roll(np.roll(d, -dy, axis=0), -dx, axis=1) * k
        # kill the wrapped band on every shift: a fault 40 m from the east edge is not adjacent
        # to one 40 m from the west edge
        if dy:
            s[:max(0, dy)] = 0.0
            s[h + min(0, dy):] = 0.0
        if dx:
            s[:, :max(0, dx)] = 0.0
            s[:, w + min(0, dx):] = 0.0
        out += s
    return out


def greedy_emit(density: np.ndarray, allowed: np.ndarray, dti_projected: float,
                budget: int, pool: int = 400_000, hard_max: int | None = None,
                log=print) -> tuple[np.ndarray, dict]:
    """Lazy-greedy maximum expected coverage under the metric's own acceptance rule.

    Parameters
    ----------
    density : float32 (H*W,) expected truth mass per pixel (calibrated: sum ~= |G| estimate).
    allowed : bool (H*W,) pixels this emitter may use (footprint, off-catalogue, gates).
    dti_projected : the DTI to beat; it sets the credit bar via ``accept_bar``.
    budget : maximum number of emitted pixels.
    pool : candidate pool size taken by initial gain (gains are non-increasing, so a top-K pool is
        a valid superset for a greedy that stops when the bar is not cleared).

    Two documented approximations, both flagged in the returned stats:

    * A candidate whose gain no longer clears *its own* threshold is not deleted from the heap;
      the scan gives up after ``MAX_REJECTS`` consecutive failures.  Because a rejected pixel can
      only have been beaten by pixels with larger gains, and thresholds differ by at most a factor
      ``1/(1-w)``, the objective loss is bounded and small; the stop is reported so it can be
      audited rather than assumed away.
    * Gains are expectations under ``density``, i.e. under the assumption that expected credit is
      the right thing to maximise.  It is: DTI is linear in ``p`` for a fixed support, so the
      Bayes-optimal decision at a fixed bar is the expectation.
    """
    import heapq
    h, w = int(allowed.shape[0]), int(allowed.shape[1])
    g0 = gain_field(density, (h, w)).ravel()
    allow = allowed.ravel()
    g0 = np.where(allow, g0, -np.inf)
    n_pool = int(min(pool, max(int(allow.sum()) - 1, 0)))
    if n_pool <= 0:
        return np.zeros((h, w), dtype=np.float32), {"emitted": 0, "reason": "no candidates"}
    cand = np.argpartition(-g0, n_pool - 1)[:n_pool]
    cand = cand[np.argsort(-g0[cand])]
    dens = density.ravel()
    nb, kk = _neighbour_tables(cand, (h, w))
    rho_nb = np.take(dens, nb) * (nb >= 0)
    m = np.zeros(h * w, dtype=np.float32)      # current best cover at each truth pixel
    bar = accept_bar(dti_projected)

    def gain_of(i: int) -> tuple[float, float]:
        nbi = nb[i]
        ok = nbi >= 0
        g = float(np.sum(rho_nb[i][ok] * np.maximum(0.0, kk[i][ok] - m[nbi[ok]])))
        wx = float(np.max(kk[i][ok])) if ok.any() else 0.0
        return g, wx

    heap = [(-float(g0[c]), idx) for idx, c in enumerate(cand)]
    heapq.heapify(heap)
    dead = np.zeros(cand.size, dtype=bool)
    chosen: list[int] = []
    gains: list[float] = []
    first_gain = last_gain = None
    rejects = 0
    MAX_REJECTS = 1000      # documented approximation, see the note in the docstring
    repush = np.zeros(cand.size, dtype=np.int16)
    MAX_REPUSH = 8          # a candidate can only be beaten by pixels within its 3 px disc, so a
                            # handful of recomputations covers it; beyond that we keep the stale key
    while heap and len(chosen) < budget and rejects < MAX_REJECTS:
        neg, i = heapq.heappop(heap)
        key = -neg
        g, wx = gain_of(i)
        if g <= 0.0:
            dead[i] = True
            rejects += 1
            continue
        if g < key - 1e-9 and repush[i] < MAX_REPUSH:   # stale key: true gain lower, re-queue
            repush[i] += 1
            heapq.heappush(heap, (-g, i))
            continue
        if g <= bar * (1.0 - wx) + 1e-12:
            dead[i] = True
            rejects += 1
            continue
        rejects = 0
        px = int(cand[i])
        chosen.append(px)
        gains.append(g)
        if first_gain is None:
            first_gain = g
        last_gain = g
        nbi = nb[i]
        ok = nbi >= 0
        upd = np.maximum(m[nbi[ok]], kk[i][ok])
        changed = upd > m[nbi[ok]]
        m[nbi[ok][changed]] = upd[changed]
        if len(chosen) % 5000 == 0:
            log(f"    emitted {len(chosen)}  gain_last={g:.4f}  bar={bar:.4f}")
    out = np.zeros(h * w, dtype=np.float32)
    if chosen:
        out[np.array(chosen, dtype=np.int64)] = 1.0
    stats = dict(emitted=int(out.sum()), pool=n_pool, bar=bar, dti_projected=dti_projected,
                 marginal_first=float(first_gain or 0.0), marginal_last=float(last_gain or 0.0),
                 total_expected_credit=float(sum(gains)), rejects_at_stop=int(rejects),
                 density_sum=float(dens[allow].sum()))
    return out.reshape(h, w), stats
