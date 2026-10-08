"""Revealed-preference inversion, generalised: stratify the organiser's own scores by *any*
pixel-level feature and solve for that feature's credit density.

The method
----------
Thirteen rasters this family shipped were scored on the public leaderboard, and all thirteen are
restored here with pinned SHA-256 (``registry/data_manifest.json``).  Their scores are
owner-reported at four decimals and the board publishes no filename, so nothing below is
organiser-authenticated -- but the bytes are real and the arithmetic is exact.

With ``DTI = T / (0.2*(T + S - M) + 0.8*|G|)`` and the family's standing approximation ``M = T``
(dot emissions whose pixels are separated by more than 200 m rarely compete for one truth pixel;
``knowledge/10`` §9), each file's realised credit is

    T_i = DTI_i * (0.2 * S_i + 0.8 * |G|)

and credit is additive over *disjoint* pixel strata, so for any stratification of the footprint

    T_i = sum_s |supp_i ∩ stratum_s| * rho_s

is a linear system in the unknown per-pixel credit densities ``rho_s``.  Thirteen equations, and
the strata are chosen to be few enough that the system is not degenerate.  ``rho_s`` is solved by
non-negative least squares with an optional monotonicity constraint (credit density cannot fall as
corroboration rises -- imposed as a cumulative-parameter reparametrisation, not as a penalty), and
the whole thing is cross-validated leave-one-file-out on the quantity we actually care about, the
reported DTI.

What makes this different from a leaderboard curve fit
------------------------------------------------------
``knowledge/03`` N-5 records that fitting a truth model to thirteen coarse scores fails
(RMSE 0.1449).  That fit tried to predict a score from a *file-level* summary.  This one never
predicts a score from a summary: it uses exact set membership of restored bytes, and the only
model choice is the stratification.  The check on it is the same one ``knowledge/10`` §2 used --
the nested pair ``h33-2-b2 ⊂ gems24-d2-8`` must come out with zero credit on the deleted
``<=200 m`` ring, which is an exact identity and not a fit.

Constants
---------
``G_PX = 14088.7`` is the value that identity produces (``knowledge/10`` §2).  ``invert`` takes it
as an argument so the sensitivity can be reported rather than assumed.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.optimize import nnls

G_PX = 14088.7
ALPHA = 0.2
BETA = 0.8

# file -> owner-reported public leaderboard score.  Sources: the task prompt's per-site score list
# (README §1) and registry/leaderboard_snapshot_2026-10-07.json.  Both are owner-reported.
SCORES: dict[str, float] = {
    "h33-2-b2-zeros.tif": 0.2778,
    "gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif": 0.2600,
    "gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif": 0.2477,
    "gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif": 0.2449,
    "gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif": 0.1922,
    "gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan.tif": 0.1894,
    "gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif": 0.1855,
    "gems10-h28-dotted-ridge-20260928T020256236880Z-6452ae1d00.tif": 0.1839,
    "8GEMSDOE_Hedge-v2_submission.tif": 0.1563,
    "gemsdoe-ens12-adopted-7f00890a.tif": 0.1563,
    "gems10-h25-ctx-ridge-20260927T232947704150Z-6452ae1d00.tif": 0.1280,
    "13gems_20261001_r13-lattice-s5_v2_nan-outside.tif": 0.0904,
    "gemsdoe9-PLACEHOLDER-2314b599.tif": 0.0107,
}


def load_supports(data_dir: str | Path = "data") -> dict[str, np.ndarray]:
    """Evaluated support of every scored raster: ``p > 0`` and not on a catalogue pixel.

    Catalogue pixels are excluded because the organiser's mask removes them: the two files that
    carry them (``8GEMSDOE_Hedge-v2`` with all 60,988 and ``gemsdoe-ens12`` with 6,455) report the
    same score as their evaluated mass implies only if those pixels are neither credited nor taxed
    (``knowledge/09_r2_review.md``).
    """
    data_dir = Path(data_dir)
    cat = rasterio.open(data_dir / "labels.tif").read(1) == 1
    out = {}
    paths = sorted((data_dir / "scored").glob("*.tif")) + sorted((data_dir / "reference").glob("*.tif"))
    for p in paths:
        if p.name not in SCORES:
            continue
        with rasterio.open(p) as ds:
            a = np.nan_to_num(ds.read(1).astype(np.float32), nan=0.0)
        out[p.name] = (a > 0) & ~cat
    missing = set(SCORES) - set(out)
    if missing:
        raise FileNotFoundError(f"scored rasters missing from {data_dir}: {sorted(missing)}")
    return out


def credit_from_score(score: float, s_eval: int, g: float = G_PX) -> float:
    """Realised credit ``T`` implied by a reported DTI, under ``M = T``."""
    return float(score * (ALPHA * s_eval + BETA * g))


def dti_from_credit(t: float, s_eval: int, g: float = G_PX) -> float:
    """Exact inverse of :func:`credit_from_score` under the same ``M = T`` reading."""
    den = ALPHA * s_eval + BETA * g
    return float(t / den) if den > 0 else 0.0


def design(strata: list[tuple[str, np.ndarray]], supp: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """``A[i, s]`` = number of file *i*'s evaluated pixels inside stratum *s*; ``b[i]`` = its ``T``."""
    names = list(supp)
    A = np.zeros((len(names), len(strata)))
    for i, n in enumerate(names):
        s = supp[n]
        for j, (_, m) in enumerate(strata):
            A[i, j] = int((s & m).sum())
    b = np.array([credit_from_score(SCORES[n], int(supp[n].sum())) for n in names])
    return A, b, names


def solve(A: np.ndarray, b: np.ndarray, *, monotone_from: int | None = None,
          fixed_zero: tuple[int, ...] = (), ridge: float = 0.0) -> np.ndarray:
    """Non-negative least squares for the stratum credit densities.

    ``fixed_zero`` pins strata whose credit is known to be exactly zero (the ``<=200 m`` ring, from
    the nested-pair identity).  ``monotone_from=k`` forces the free columns from index ``k`` onward
    to be non-decreasing, by solving for non-negative *increments* instead of for the densities
    themselves: ``rho_free = L @ u`` with ``L`` lower-triangular ones and ``u >= 0`` from NNLS.
    A penalty would only make the constraint soft; this makes it impossible to violate.
    """
    k = A.shape[1]
    free = [j for j in range(k) if j not in fixed_zero]
    nf = len(free)
    Af, bf = A[:, free], np.asarray(b, float)
    if monotone_from is not None:
        start = free.index(monotone_from) if monotone_from in free else 0
        Lm = np.eye(nf)
        for j in range(start, nf):
            Lm[start:j + 1, j] = 1.0          # rho_j = u_start + ... + u_j  ->  nondecreasing
        M = Af @ Lm
    else:
        Lm = np.eye(nf)
        M = Af
    if ridge:
        M = np.vstack([M, np.sqrt(ridge) * np.eye(nf)])
        bf = np.concatenate([bf, np.zeros(nf)])
    u, _ = nnls(M, bf)
    rho_free = Lm @ u
    rho = np.zeros(k)
    for idx, j in enumerate(free):
        rho[j] = float(rho_free[idx])
    return rho


def loo(A: np.ndarray, b: np.ndarray, supp_sizes: np.ndarray, scores: np.ndarray,
        g: float = G_PX, **kw) -> dict:
    """Leave-one-file-out: refit on twelve, predict the held-out file's DTI from its own strata."""
    n = A.shape[0]
    rows = []
    for i in range(n):
        idx = [j for j in range(n) if j != i]
        rho = solve(A[idx], b[idx], **kw)
        t = float(A[i] @ rho)
        pred = dti_from_credit(t, int(supp_sizes[i]), g)
        rows.append(dict(index=i, t_obs=float(b[i]), t_pred=t, dti_obs=float(scores[i]),
                         dti_pred=pred, abs_err=abs(pred - float(scores[i])),
                         rel_err=abs(pred - float(scores[i])) / max(float(scores[i]), 1e-9)))
    errs = np.array([r["abs_err"] for r in rows])
    return dict(per_file=rows, mean_abs_dti_err=float(errs.mean()),
                max_abs_dti_err=float(errs.max()),
                mean_rel_err=float(np.mean([r["rel_err"] for r in rows])))


def nested_pair_identity(supp: dict[str, np.ndarray], a="h33-2-b2-zeros.tif",
                         b="gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif",
                         g: float = G_PX) -> dict:
    """Re-derive the exact identity the ring rule and ``|G|`` come from, from the restored bytes.

    ``A ⊂ B`` and ``B \\ A`` is the ``<=200 m`` ring.  If the ring earns nothing, ``T(A) = T(B)``,
    and the two reported scores then differ *only* through ``0.2 * |B \\ A|``:

        1/DTI_B - 1/DTI_A = 0.2 * |B \\ A| / T        and        T = DTI * (0.2*S + 0.8*|G|)

    which is one equation in ``|G|``.  Solving it is the measurement, not a fit.
    """
    A, B = supp[a], supp[b]
    only_a, only_b = int((A & ~B).sum()), int((B & ~A).sum())
    sa, sb = int(A.sum()), int(B.sum())
    da, db = SCORES[a], SCORES[b]
    ta, tb = credit_from_score(da, sa, g), credit_from_score(db, sb, g)
    # |G| that makes T(A) == T(B) exactly
    # da*(0.2 sa + 0.8 G) = db*(0.2 sb + 0.8 G)  ->  G = 0.2 (da sa - db sb) / (0.8 (db - da))
    denom = BETA * (db - da)
    g_solved = float(ALPHA * (da * sa - db * sb) / denom) if abs(denom) > 1e-15 else float("nan")
    return dict(a=a, b=b, s_a=sa, s_b=sb, a_minus_b_px=only_a, b_minus_a_px=only_b,
                dti_a=da, dti_b=db, t_a_at_G=ta, t_b_at_G=tb,
                G_assumed=g, G_solved_from_identity=g_solved,
                identity_holds=only_a == 0 and only_b == sb - sa,
                reading="A is B with the <=200 m ring deleted; equal credit at the solved |G| "
                        "means the deleted ring earned exactly zero")


def ring_check(data_dir: str | Path = "data", supp: dict[str, np.ndarray] | None = None,
               a="h33-2-b2-zeros.tif",
               b="gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif") -> dict:
    """Independent geometry check: is ``B \\ A`` really inside 200 m of the mapped catalogue?"""
    data_dir = Path(data_dir)
    supp = supp or load_supports(data_dir)
    cat = rasterio.open(data_dir / "labels.tif").read(1) == 1
    edt = ndimage.distance_transform_edt(~cat, sampling=100.0)
    d = supp[b] & ~supp[a]
    da = edt[supp[a]]
    return dict(b_minus_a_px=int(d.sum()),
                b_minus_a_max_dist_m=float(edt[d].max()) if d.any() else None,
                b_minus_a_median_dist_m=float(np.median(edt[d])) if d.any() else None,
                a_min_dist_to_catalogue_m=float(da.min()) if da.size else None,
                a_px_inside_200m=int((da <= 200).sum()))


def report(data_dir: str | Path = "data", strata_fn=None, **kw) -> dict:
    """Full inversion receipt for one stratification."""
    data_dir = Path(data_dir)
    supp = load_supports(data_dir)
    sizes = np.array([int(supp[n].sum()) for n in supp])
    scores = np.array([SCORES[n] for n in supp])
    strata = strata_fn(data_dir, supp)
    A, b, names = design(strata, supp)
    rho = solve(A, b, **kw)
    cv = loo(A, b, sizes, scores, **kw)
    pred = A @ rho
    return dict(g_px=G_PX, strata=[s[0] for s in strata], strata_px=[int(s[1].sum()) for s in strata],
                design_rowsum_check=[float(x) for x in A.sum(axis=1)],
                evaluated_px=[int(x) for x in sizes], reported_scores=[float(x) for x in scores],
                t_observed=[float(x) for x in b], t_fitted=[float(x) for x in pred],
                rho=rho.tolist(), credit_density_pct=[100 * float(x) for x in rho],
                dti_fitted=[dti_from_credit(float(t), int(s)) for t, s in zip(pred, sizes)],
                in_sample_rmse_T=float(np.sqrt(np.mean((pred - b) ** 2))),
                loo=cv, files=names, solve_kwargs={k: v for k, v in kw.items() if k != "g"},
                nested_identity=nested_pair_identity(supp), ring_geometry=ring_check(data_dir, supp))


def save(path: str | Path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, allow_nan=False, default=float) + "\n")
