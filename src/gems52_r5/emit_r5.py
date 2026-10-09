"""R5 emission: rank the trace candidates, then let the metric itself choose the budget.

Two ideas, both from the metric's own algebra and neither used by any prior round in this
repository:

1. **Ribbon spacing.** ``TPw = sum_g max_x p(x) k(d(x,g))`` credits each truth pixel once, at its
   best covering weight.  Two dots one pixel apart on the same trace therefore split one credit
   between them and one of them is pure false-positive tax, while dots three pixels apart along a
   straight trace each integrate their own ribbon and earn up to 2.25-3.0
   (:func:`gems52_r5.traces.ribbon_credit`, checked against :func:`gems52.metric.dti`).  So the
   emission is thinned to a minimum separation of three pixels -- the kernel's own radius -- and
   never to an arbitrary dot budget.

2. **The budget is a measured optimum, not a taste.** :func:`improves` is the exact incremental
   test: adding a dot with expected credit ``c`` and expected cover ``m`` to a field carrying
   ``(T, S, M)`` raises DTI iff ``(T + c) / (0.2*(T + c + S + 1 - M - m) + 0.8*|G|)`` beats
   ``T / (0.2*(T + S - M) + 0.8*|G|)``.  ``c`` and ``m`` are not guessed: they are read off the
   localisation assay's measured lateral-error distribution at that rank depth
   (:func:`gems52_r5.localize.assay`).  :func:`budget_from_curve` walks the budget grid and stops
   where the test first fails.

Everything here is deterministic given its inputs and a seed.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from gems52_r5 import traces as T

ALPHA, BETA = 0.2, 0.8
STRUCT8 = np.ones((3, 3), bool)


def dti_of(t: float, s: float, m: float, g: float) -> float:
    den = ALPHA * (t + s - m) + BETA * g
    return float(t / den) if den > 0 else 0.0


def improves(t: float, s: float, m: float, c: float, mm: float, g: float) -> bool:
    """Exact incremental DTI test for adding one dot with expected credit ``c`` and cover ``mm``."""
    return dti_of(t + c, s + 1, m + mm, g) > dti_of(t, s, m, g) + 1e-15


def marginal_credit_bar(t: float, s: float, m: float, g: float, cover: float) -> float:
    """Credit a marginal dot must exceed to raise DTI, given the cover it will also add.

    Solved in closed form from :func:`improves`: with ``D = 0.2*(T+S-M) + 0.8*|G|`` and
    ``den2 = D - 0.2*T``, a dot improves iff ``c > 0.2*T*(1 - cover) / den2``.
    """
    d = ALPHA * (t + s - m) + BETA * g
    den2 = d - ALPHA * t
    if den2 <= 0:
        return float("inf")
    return float(ALPHA * t * (1.0 - cover) / den2)


def persistence_length(trace: np.ndarray) -> np.ndarray:
    """Along-trace run length in pixels: the 8-connected component size of the thinned trace.

    A mapped-scale fault trace in this grid runs tens to hundreds of pixels; a noise ridge runs a
    handful.  This is the cheapest available discriminator between the two, it uses no labels, and
    it is the reason the detector is allowed to prefer a long weak ridge over a short strong one.
    """
    lab, n = ndimage.label(trace, structure=STRUCT8)
    if n == 0:
        return np.zeros(trace.shape, np.float32)
    sizes = np.bincount(lab.ravel(), minlength=n + 1).astype(np.float32)
    return sizes[lab]


def candidate_field(corrob: np.ndarray, resp: np.ndarray, persist: np.ndarray,
                    valid: np.ndarray, habitat: np.ndarray | None = None,
                    w_corrob: float = 1.0, w_resp: float = 0.35, w_persist: float = 0.35,
                    w_habitat: float = 0.0) -> np.ndarray:
    """Rank field for trace candidates, on [0, 1]-scaled components, -inf where not allowed.

    ``corrob``  how many physically independent data families put a trace here (0..6).  This is the
        component with organiser-score support: ``revealed_r5.invert`` measures the credit density
        of corroboration strata inside the thirteen scored rasters.
    ``resp``    the winning family's ridge response percentile.
    ``persist`` log-scaled along-trace run length.
    ``habitat`` optional co-training view score (``cotrain_r5``); weight 0 by default, because
        ``knowledge/10`` §6 measured habitat as unable to separate credited from uncredited mass.
    """
    if w_habitat and habitat is None:
        raise ValueError("w_habitat > 0 requires a habitat field")
    out = np.full(resp.shape, -np.inf, np.float64)
    c = np.nan_to_num(corrob.astype(np.float64)) / 6.0
    r = np.nan_to_num(resp.astype(np.float64), nan=0.0)
    p = np.log1p(np.nan_to_num(persist.astype(np.float64), nan=0.0))
    p = p / max(float(np.percentile(p[valid], 99.9)) if valid.any() else 1.0, 1e-9)
    score = w_corrob * c + w_resp * r + w_persist * np.clip(p, 0, 1)
    if habitat is not None and w_habitat:
        h = np.nan_to_num(habitat.astype(np.float64), nan=0.0)
        score = score + w_habitat * h
    ok = valid & (corrob >= 1)
    out[ok] = score[ok]
    return out


def budget_from_curve(budgets: list[int], credit_per_dot: list[float], cover_per_dot: list[float],
                      g_px: float, delta: float = 1.0) -> dict:
    """Pick the budget that maximises projected DTI, and report the marginal test that stopped it.

    ``credit_per_dot[i]`` / ``cover_per_dot[i]`` are the assay's measurements at ``budgets[i]``.
    They are treated as the *average* over the whole emission at that depth, which is what the assay
    actually measures; the marginal value of the last block is the finite difference between
    consecutive budgets, and that is what the stopping test uses.
    """
    rows, best = [], None
    for i, s in enumerate(budgets):
        t = min(delta * credit_per_dot[i] * s, g_px)
        m = delta * cover_per_dot[i] * s
        dti = dti_of(t, s, m, g_px)
        if i > 0:
            s0, t0, m0 = budgets[i - 1], min(delta * credit_per_dot[i - 1] * budgets[i - 1], g_px), \
                delta * cover_per_dot[i - 1] * budgets[i - 1]
            ds = s - s0
            dc = max(t - t0, 0.0)
            dm = max(m - m0, 0.0)
            marg_c = dc / ds if ds else 0.0
            marg_m = dm / ds if ds else 0.0
            bar = marginal_credit_bar(t0, s0, m0, g_px, marg_m)
            ok = marg_c > bar
        else:
            marg_c = credit_per_dot[i]
            marg_m = cover_per_dot[i]
            bar = marginal_credit_bar(0.0, 0.0, 0.0, g_px, marg_m)
            ok = True
        rows.append(dict(budget=int(s), credit_per_dot=float(credit_per_dot[i]),
                         cover_per_dot=float(cover_per_dot[i]), projected_t=float(t),
                         projected_m=float(m), projected_dti=float(dti),
                         marginal_credit=float(marg_c), marginal_cover=float(marg_m),
                         marginal_bar=float(bar), marginal_test_passes=bool(ok)))
        if best is None or dti > best["projected_dti"]:
            best = rows[-1]
    first_fail = next((r for r in rows if not r["marginal_test_passes"]), None)
    return dict(rows=rows, best=best, first_failing_budget=first_fail["budget"] if first_fail else None,
                g_px=g_px, delta=delta)


def ribbon_spacing_px(lateral_px: float = 0.0) -> float:
    """Spacing that maximises credit per dot for a given localisation error.

    Credit per dot is ``integral of k(sqrt(e^2 + a^2)) da`` over one spacing window, so it grows
    with spacing until the window's ends fall outside the kernel, and the *fraction* of truth
    covered per dot falls.  For the metric's own kernel on the lattice the answer is flat over
    2-4 px and 3 px (the kernel radius) is the choice that keeps every dot's ribbon inside the
    disc, so it is the default everywhere in this round.
    """
    best, arg = -1.0, 3.0
    for s in (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0):
        c = T.ribbon_credit(lateral_px, s)["credit_per_dot"] / s     # credit per truth px covered
        if c > best:
            best, arg = c, s
    return float(arg)


def allowed_set(valid: np.ndarray, dist_to_visible_catalogue: np.ndarray, corridor_m: float = 200.0,
                train_exclusion: np.ndarray | None = None) -> np.ndarray:
    """Footprint, outside the ring that measured exactly zero credit, minus any assay exclusion."""
    out = valid & (dist_to_visible_catalogue > corridor_m)
    if train_exclusion is not None:
        out &= ~train_exclusion
    return out
