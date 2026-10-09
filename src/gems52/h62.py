"""H62 -- two-view co-training, corroboration instead of disagreement.

Preregistered in ``knowledge/32_hypotheses_H62_preregistered.md`` and frozen in
``registry/h62_preregistration.json`` (sha256 of the document is checked against the registry by
``scripts/run_h62.py`` before any fit runs).

Why this round exists
---------------------
Every prior round in this lane shipped a **disagreement** field -- ``pA(1-pB)`` (H56, H59),
``max(pA-pB,0)`` (H60D, shipped, verdict negative).  This round keeps the same two views, the same
independence premise and the same whole-segment buffered folds, but tests the **opposite cell** of
the same 2x2 confidence table, for one measured reason:

``knowledge/10`` §3 measures a corroboration law.  Two *independent thinnings of one field*
(``d1-5``, ``d2-8``) intersect in an atom ``P1`` of 25,517 px carrying **16.3-20.5 %** credit
density, while the atoms selected by only one thinning carry 0-8.7 %.  Corroboration is the largest
effect measured anywhere in this repository after the 200 m ring rule.

Blum & Mitchell's premise is stronger than "two thinnings of one detector": it is conditional
independence *given the class*, and it is empirically supported here (block OOF negative-error
correlation <= 0.176 against an abandonment bar of 0.60).  Two views that err independently should
corroborate more than two thinnings of one view, which share every systematic error of that view.

What is here
------------
``concordance_surface`` / ``independent_thinning`` / ``concordance_corroboration``
    the H62-B field: each view's confident set is thinned to the metric's own 3 px lattice
    *independently*, the two thinnings are intersected, and the survivors are ranked by the joint
    confidence ``min(pA,pB)``.  Not the union ``max(pA,pB)``: the union is large wherever either
    view fires, this is large only where both fired and neither view's own thinning dropped it.
``cover_conditioned_disagreement``
    H62-A: the lane's own discovery cell ``max(pA-pB,0)`` restricted to the thick-cover regime
    (depth to basement above a preregistered quantile of the legal pool).
``revealed_colocation``
    Instrument 2: the fraction of a dot set inside the metric's acceptance radius of ``P1``, the
    only subset of this footprint whose credit density is *measured* (16.3-20.5 %) rather than
    projected.  A similarity statistic, disclosed as such, read together with the uniqueness gate.
``budget_from_gamma``
    the derived emission budget: with ``T(S) = c S^gamma`` the argmax
    ``S* = gamma*0.8|G|/(0.2(1-gamma))`` is independent of ``c``, so it is a property of the
    ranked field's *decay*, not of its quality.  ``gamma`` is measured on this round's own field.

Nothing here reads a leaderboard score.  Nothing here certifies an organizer score.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

# Registered lane thresholds (registry/h62_preregistration.json -> decision_rules).
LANE_MAX_RANK_CORR = 0.90
LANE_MAX_DOTS_FRAC = 0.70
LANE_PROXIMITY_PX = 3
LEAKAGE_AUC_MAX = 0.90
ABANDON_R = 0.60
G_ANCHOR_PX = 14088.7          # registered |G| (knowledge/10 s2); the bracket is disclosed
BUDGET_CLAMP = (15000, 30000)
BUDGET_FALLBACK = 22000
GAMMA_GRID = (8000, 12000, 17000, 25000, 38000)


# --------------------------------------------------------------------------------------------
# H62-B: concordance under independent thinning
# --------------------------------------------------------------------------------------------
def concordance_surface(pa: np.ndarray, pb: np.ndarray) -> np.ndarray:
    """``min(pA, pB)``: the joint-confidence surface, before any cell restriction.

    Deliberately not ``max`` (the union) and not the product: ``min`` is the largest value both
    views can vouch for, which is the quantity a corroboration operator should rank on.
    """
    pa = np.asarray(pa, np.float32)
    pb = np.asarray(pb, np.float32)
    return np.minimum(pa, pb).astype(np.float32)


def concordant_cell(pa: np.ndarray, pb: np.ndarray, allowed: np.ndarray,
                    q_conf: float) -> np.ndarray:
    """Both views confident: ``pA >= q_conf AND pB >= q_conf``."""
    return (np.asarray(allowed, bool) & (np.asarray(pa, np.float32) >= q_conf)
            & (np.asarray(pb, np.float32) >= q_conf))


def independent_thinning(pa: np.ndarray, pb: np.ndarray, allowed: np.ndarray,
                         q_conf: float, k: int, select) -> dict:
    """Thin each view's confident set to the metric's lattice *independently*, then intersect.

    ``select(score, allowed, k)`` is the registered emitter (``h57.iso_select``).  The two calls
    never see the other view's scores, so a pixel survives only if **each view on its own** would
    have spent one of its ``k`` dots there.  That is the corroboration operator: it is what
    distinguishes two independent detectors agreeing from one detector being asked twice.
    """
    a_pool = np.asarray(allowed, bool) & (np.asarray(pa, np.float32) >= q_conf)
    b_pool = np.asarray(allowed, bool) & (np.asarray(pb, np.float32) >= q_conf)
    thin_a = select(np.asarray(pa, np.float32), a_pool, k)
    thin_b = select(np.asarray(pb, np.float32), b_pool, k)
    both = np.asarray(thin_a, bool) & np.asarray(thin_b, bool)
    expected = None
    na, nb = int(thin_a.sum()), int(thin_b.sum())
    n = int(np.asarray(allowed, bool).sum())
    if n > 0 and na > 0 and nb > 0:
        # Independence null: two independent thinnings of sizes na and nb inside a pool of n.
        expected = float(na) * float(nb) / float(n)
    return dict(thin_a=thin_a, thin_b=thin_b, corroborated=both,
                n_thin_a=na, n_thin_b=nb, n_corroborated=int(both.sum()),
                expected_under_independence=expected,
                corroboration_lift=(float(both.sum()) / expected) if expected else None)


def concordance_corroboration(pa: np.ndarray, pb: np.ndarray, allowed: np.ndarray,
                              q_conf: float, k: int, select) -> np.ndarray:
    """The H62-B ranking surface: joint confidence, supported only on the corroborated set.

    Zero outside the independently-corroborated pixels, ``min(pA,pB)`` on them.  Emitting top-k of
    this field is *not* the union of the two views: the union's confident mass is exactly the set
    this field is defined to shrink.
    """
    th = independent_thinning(pa, pb, allowed, q_conf, k, select)
    surf = np.where(th["corroborated"], concordance_surface(pa, pb), 0.0).astype(np.float32)
    return surf


# --------------------------------------------------------------------------------------------
# H62-A: cover-thickness-conditioned buried disagreement
# --------------------------------------------------------------------------------------------
def cover_conditioned_disagreement(pa: np.ndarray, pb: np.ndarray, depth: np.ndarray,
                                   allowed: np.ndarray, q_conf: float, q_abstain: float,
                                   depth_quantile: float = 0.70) -> tuple[np.ndarray, float]:
    """``max(pA-pB,0)`` restricted to the thick-cover regime.

    The brief's buried-beneath-cover cell is only licensed where cover is actually thick: under
    thin cover the absence of a scarp falsifies the fault, so the A-side lineament there is a
    lithologic contact, a dike or the basin-margin gravity gradient.  H60D measured the depth
    contrast between the strata (A-only median 341.7 m vs B-only 106.5 m) and never used it as a
    restriction.  The threshold is a *quantile of the legal pool*, measured on the run's own bytes,
    so it cannot be tuned to a result.
    """
    pa = np.asarray(pa, np.float32)
    pb = np.asarray(pb, np.float32)
    depth = np.asarray(depth, np.float32)
    allowed = np.asarray(allowed, bool)
    d = depth[allowed & np.isfinite(depth)]
    thr = float(np.quantile(d, depth_quantile)) if d.size else float("nan")
    dis = np.maximum(pa - pb, 0.0)
    cell = allowed & (pa >= q_conf) & (pb <= q_abstain)
    out = np.where(cell & (depth >= thr), dis, 0.0).astype(np.float32)
    return out, thr


# --------------------------------------------------------------------------------------------
# Instrument 2: revealed-preference co-location with the atom of measured credit
# --------------------------------------------------------------------------------------------
def revealed_colocation(dots: np.ndarray, core: np.ndarray, pool: np.ndarray,
                        radius: int = 3) -> dict:
    """Fraction of ``dots`` inside the metric's acceptance radius of the measured-credit atom.

    ``core`` is ``P1 = h33-2-b2 & scored_d15_scored``: 25,517 px whose credit density is bounded
    to [16.3 %, 20.5 %] by the exact nested-pair algebra on owner-reported scores.  It is the only
    subset of this footprint with a *measured* density rather than a projected one.

    Returns the co-location fraction, the matched random baseline
    ``|dilate(core, r)| / |pool|`` and the lift over it.  Disclosed limits (hypothesis document,
    Instruments): this is a similarity statistic to one specific prior file, ``rho_P1`` itself
    rests on owner-reported scores, and the statistic is read only together with the uniqueness
    gate -- a field can maximize it by reproducing the champion, which the lane gate forbids.
    """
    dots = np.asarray(dots, bool)
    pool = np.asarray(pool, bool)
    core = np.asarray(core, bool)
    near = ndimage.binary_dilation(core, iterations=int(radius))
    nd = int(dots.sum())
    if nd == 0:
        return dict(n_dots=0, colocated=0, fraction=None, random_baseline=None, lift=None)
    hit = int((dots & near).sum())
    n_pool = int(pool.sum())
    base = float((near & pool).sum()) / n_pool if n_pool else None
    frac = hit / nd
    return dict(n_dots=nd, colocated=hit, fraction=float(frac),
                random_baseline=base, lift=(frac / base) if base else None,
                radius_px=int(radius))


def implied_credit_density(fraction: float, rho_core: float = 0.184,
                           rho_novel_lo: float = 0.0279,
                           rho_novel_hi: float = 0.1387) -> dict:
    """Two-component mixture read of a co-location fraction.

    ``rho(X) = f*rho_core + (1-f)*rho_novel``.  ``rho_core`` = 0.184 is the midpoint of the
    measured [0.163, 0.205] interval for ``P1``; ``rho_novel`` is bracketed by the measured
    uniform-random density (0.0279) and the champion file's own average (0.1387).  Both inputs are
    owner-reported; the output is a bracket, never a score.
    """
    f = float(fraction)
    return dict(rho_core=rho_core, rho_novel_bracket=[rho_novel_lo, rho_novel_hi],
                rho_lo=f * rho_core + (1 - f) * rho_novel_lo,
                rho_hi=f * rho_core + (1 - f) * rho_novel_hi)


# --------------------------------------------------------------------------------------------
# the derived emission budget
# --------------------------------------------------------------------------------------------
def budget_from_gamma(points: list[tuple[int, float]], g_anchor: float = G_ANCHOR_PX,
                      clamp=BUDGET_CLAMP, fallback: int = BUDGET_FALLBACK) -> dict:
    """Fit ``f(S) ∝ S^(gamma-1)`` and return ``S* = gamma*0.8|G|/(0.2(1-gamma))``.

    With ``FNw = |G| - TPw``, binary mass and ``M ≈ T``, ``DTI(S) = T(S)/(0.2 S + 0.8|G|)``; if
    ``T(S) = c S^gamma`` the argmax in ``S`` is independent of ``c``, so **field quality does not
    move it** -- only the rate at which the ranked field's credit density decays does.  That is
    what makes the budget derivable instead of inherited from the champion's 37,654 px.
    """
    pts = [(int(s), float(f)) for s, f in points if s > 0 and f is not None and f > 0]
    out = dict(points=pts, g_anchor_px=g_anchor, clamp_px=list(clamp))
    if len(pts) < 3:
        out.update(ok=False, reason="fewer than 3 usable budget points", budget_px=fallback,
                   clamped=False)
        return out
    xs = np.log(np.array([p[0] for p in pts], np.float64))
    ys = np.log(np.array([p[1] for p in pts], np.float64))
    slope, intercept = np.polyfit(xs, ys, 1)
    gamma = float(slope + 1.0)
    out.update(ok=True, slope=float(slope), intercept=float(intercept), gamma=gamma)
    if not (0.0 < gamma < 1.0):
        out.update(budget_px=fallback, clamped=False,
                   reason=f"gamma {gamma:.4f} outside (0,1); the ranked field's density does not "
                          f"decay as a power law -- falling back to the |G|-bracket midpoint")
        return out
    s_star = gamma * 0.8 * g_anchor / (0.2 * (1.0 - gamma))
    clamped = int(min(max(int(round(s_star)), int(clamp[0])), int(clamp[1])))
    out.update(s_star_unclamped=float(s_star), budget_px=clamped,
               clamped=bool(clamped != int(round(s_star))),
               reason=("argmax of DTI(S) = c S^gamma / (0.2 S + 0.8 |G|); independent of c"))
    return out


# --------------------------------------------------------------------------------------------
# geological reasoning rows (Phase-2 review input, never a verified fault)
# --------------------------------------------------------------------------------------------
def reasoning_row(*, row: int, col: int, easting: float, northing: float,
                  pa: float, pb: float, depth_m: float, cell: str,
                  corroborated: bool, notes: str) -> dict:
    return dict(row=int(row), col=int(col), easting=round(float(easting), 1),
                northing=round(float(northing), 1),
                p_view_A=round(float(pa), 4), p_view_B=round(float(pb), 4),
                depth_to_basement_m=round(float(depth_m), 1), confidence_cell=cell,
                independently_corroborated=bool(corroborated),
                interpretation=notes,
                status="HYPOTHESIS FOR PHASE-2 REVIEW; not a verified fault")


def cell_of(pa: float, pb: float, q_conf: float, q_abstain: float) -> str:
    if pa >= q_conf and pb >= q_conf:
        return "concordant"
    if pa >= q_conf and pb <= q_abstain:
        return "A-only (buried candidate)"
    if pb >= q_conf and pa <= q_abstain:
        return "B-only (surface-only; artefact-suspect)"
    return "neither"


def a_only_note(depth_m: float, cover_threshold: float) -> str:
    if not np.isfinite(depth_m):
        return ("View A (potential-field/subsurface) confident, View B (surface) abstains. "
                "Interpretation: a geophysical lineament with no topographic expression.")
    if depth_m >= cover_threshold:
        return (f"View A confident, View B abstains, depth to basement {depth_m:.0f} m "
                f"(above the pool's {cover_threshold:.0f} m cover threshold). Interpretation: a "
                f"potential-field lineament beneath thick basin fill where a surface scarp is not "
                f"expected to survive -- a buried-structure candidate. Named non-fault "
                f"alternatives: the basin-bounding gravity gradient at the fill/bedrock contact, "
                f"or a basement lithologic contact beneath fill.")
    return (f"View A confident, View B abstains, depth to basement {depth_m:.0f} m (below the "
            f"pool's {cover_threshold:.0f} m cover threshold). Interpretation: under thin cover "
            f"the absence of a scarp is falsifying, so this is more likely a lithologic contact, "
            f"a dike or the basin-margin gravity gradient than a buried fault.")


def concordant_note(depth_m: float) -> str:
    d = "unknown" if not np.isfinite(depth_m) else f"{depth_m:.0f} m"
    return (f"Both views confident (depth to basement {d}). Interpretation: a structure that "
            f"carries both a potential-field/subsurface signature and a surface lineament, "
            f"independently corroborated by two detectors whose errors are near-independent. "
            f"Named non-fault alternative: a resistant lithologic contact (welded tuff or "
            f"carbonate) that stands up as a ridge AND carries a magnetic susceptibility "
            f"contrast; or a fluvial/glacial escarpment along a stratigraphic contact.")


# --------------------------------------------------------------------------------------------
# the run card (lane protocol item 5)
# --------------------------------------------------------------------------------------------
def evaluator_version() -> dict:
    out = {}
    for name in ("metric.py", "holdout.py", "h57.py", "h62.py", "emit.py"):
        p = Path(__file__).resolve().parent / name
        out[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def run_card(*, hypothesis: str, mechanism: str, mimic_processes: list[str],
             holdout: dict, instruments: dict, registry_overlap: dict,
             raster_sha256: str, validator: dict, submission_name: str,
             submission_note: str, verdict: str, extra: dict | None = None,
             promotion_scope: str | None = None) -> dict:
    card = dict(
        round="H62",
        lane=("co-training between a geophysical view and a surface view; Blum & Mitchell "
              "COLT '98, doi:10.1145/279943.279962"),
        hypothesis=hypothesis,
        mechanism=mechanism,
        named_non_fault_processes_that_could_mimic_it=mimic_processes,
        holdout_dti=holdout,
        instruments=instruments,
        correlation_overlap_vs_registry=registry_overlap,
        raster_sha256=raster_sha256,
        validator_output=validator,
        submission_name=submission_name,
        submission_note=submission_note,
        submission_note_chars=len(submission_note),
        verdict=verdict,
        promotion_scope=promotion_scope,
        number_labels=("every holdout number is HOLDOUT-DTI (evaluator version, withheld "
                       "positives, 95% CI); every leaderboard number anywhere in this repo is "
                       "owner-reported; none is ORGANIZER-CONFIRMED (no submission-page receipt "
                       "exists); a projection is never written as a score"),
        evaluator_version=evaluator_version(),
    )
    if extra:
        card.update(extra)
    return card


def write_json(path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, allow_nan=False, default=str) + "\n")
