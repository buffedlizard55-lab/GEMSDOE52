"""H60 -- co-training with disagreement as the discovery signal (this session's lane).

Frozen by ``registry/h60_preregistration.json`` and
``knowledge/25_hypotheses_H60_preregistered.md`` before any scored execution.  The lane is the
brief's own method paragraph: two views (A = potential-field/subsurface, B = surface), the
Blum & Mitchell co-training premise tested empirically, pseudo-labels only where one view is
confident and the other abstains, and **disagreement as the discovery signal** — `pA*(1-pB)`
large is "A confident, B abstains", the buried-beneath-cover cell of the 2x2 confidence table.

What is here
------------
``dis_product`` / ``dis_contrast`` / ``dis_b_product``
    the disagreement ranking fields.  None of them is the union of the two views; the product
    is large exactly where the union is *small* (B abstains).
``pooled_dti`` / ``bootstrap_ci``
    the brief's "score pooled DTI" readout: per-fold metric components pooled across folds,
    plus a fold-bootstrap 95 % CI.  Every number this module emits is a HOLDOUT-DTI number.
``layer_auc_canary``
    the leakage canary: one cached layer alone against the holdout truth.  AUC > 0.90 means
    leakage until proven otherwise.
``lane_drift_report``
    the parallel-run lane gate: rank-correlation of a surface (or of the final dots) with
    EVERY registry raster must stay <= 0.90, and no more than 70 % of the final dots may fall
    within 3 px of one registry raster's dots.  Checked on the ranking surface before
    placement AND on the final dots.  Exceeding either means the run has drifted into another
    lane: log it as a duplicate and stop.
``run_card``
    the lane protocol's closing JSON card, with every number labelled.

Nothing here reads a leaderboard score.  A-only reasoning rows are hypotheses for Phase-2
review, never verified faults.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

# Registered lane thresholds (registry/h60_preregistration.json -> decision_rules).
LANE_MAX_RANK_CORR = 0.90      # Spearman rank correlation with any registry raster
LANE_MAX_DOTS_FRAC = 0.70      # fraction of final dots within 3 px of one raster's dots
LANE_PROXIMITY_PX = 3
LEAKAGE_AUC_MAX = 0.90         # per-layer holdout AUC above this = leakage
ABANDON_R = 0.60               # block OOF negative-error correlation abandonment threshold


# --------------------------------------------------------------------------------------------
# the disagreement fields (the discovery signal)
# --------------------------------------------------------------------------------------------
def dis_product(pa: np.ndarray, pb: np.ndarray) -> np.ndarray:
    """`pA * (1 - pB)`: large iff View A is confident AND View B abstains.

    The buried-beneath-cover candidate: the geophysical view fires where the surface view has
    nothing to say.  Deliberately NOT the union `max(pA,pB)` — the union is large where the
    two views agree, this is large where they *disagree* in one specific direction.
    """
    pa = np.asarray(pa, np.float32)
    pb = np.asarray(pb, np.float32)
    return (pa * (1.0 - pb)).astype(np.float32)


def dis_contrast(pa: np.ndarray, pb: np.ndarray) -> np.ndarray:
    """`max(pA - pB, 0)`: the additive form of the same disagreement cell."""
    pa = np.asarray(pa, np.float32)
    pb = np.asarray(pb, np.float32)
    return np.maximum(pa - pb, 0.0).astype(np.float32)


def dis_b_product(pa: np.ndarray, pb: np.ndarray) -> np.ndarray:
    """`pB * (1 - pA)`: the B-only stratum — suspect surface artifacts (roads, levees,
    erosion lines, quarry faces).  Characterization only; the registered promotion rule does
    not allow it to ship."""
    pa = np.asarray(pa, np.float32)
    pb = np.asarray(pb, np.float32)
    return (pb * (1.0 - pa)).astype(np.float32)


DISAGREEMENT_FIELDS = {
    "dis_product": dis_product,
    "dis_contrast": dis_contrast,
    "dis_B_product": dis_b_product,
}


# --------------------------------------------------------------------------------------------
# pooled DTI and the holdout CI
# --------------------------------------------------------------------------------------------
def pooled_dti(fold_results: list[dict]) -> dict:
    """Pool per-fold metric components into one DTI (alpha 0.2, beta 0.8).

    ``fold_results`` carries the dicts returned by ``gems52.metric.dti`` (keys ``tpw``,
    ``fpw``, ``fnw``, ``n_truth``).  Pooling the components — not averaging the ratios — is
    the honest pooled read: it weights folds by their truth mass instead of letting a
    small-truth fold dominate the mean of ratios.
    """
    tpw = float(sum(r["tpw"] for r in fold_results))
    fpw = float(sum(r["fpw"] for r in fold_results))
    fnw = float(sum(r["fnw"] for r in fold_results))
    n_truth = int(sum(r["n_truth"] for r in fold_results))
    den = tpw + 0.2 * fpw + 0.8 * fnw
    return dict(dti=tpw / den if den > 0 else 0.0, tpw=tpw, fpw=fpw, fnw=fnw,
                n_truth=n_truth, n_folds=len(fold_results))


def bootstrap_ci(values, n_boot: int = 10000, seed: int = 20261009, alpha: float = 0.05) -> dict:
    """Fold-bootstrap CI of the mean of per-fold DTIs.  With 4 folds this is a coarse
    interval; it is reported as exactly that, never as a significance claim."""
    v = np.asarray([float(x) for x in values], dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return dict(ci_lo=None, ci_hi=None, n=0)
    rng = np.random.default_rng(seed)
    means = rng.choice(v, size=(n_boot, v.size), replace=True).mean(axis=1)
    lo, hi = np.quantile(means, [alpha / 2.0, 1.0 - alpha / 2.0])
    return dict(ci_lo=float(lo), ci_hi=float(hi), n=int(v.size), mean=float(v.mean()))


# --------------------------------------------------------------------------------------------
# the leakage canary
# --------------------------------------------------------------------------------------------
def layer_auc_canary(score: np.ndarray, truth: np.ndarray, region: np.ndarray) -> float:
    """Tie-aware AUC of ONE feature against the holdout truth over one fold's region.

    ``score`` is the layer's full-grid values, ``truth`` the fold's truth mask, ``region``
    the pixels scored.  AUC > 0.90 on any layer means leakage until proven otherwise
    (registered threshold, ``LEAKAGE_AUC_MAX``).
    """
    t = truth & region
    if not t.any():
        return float("nan")
    inside = region & ~t
    if not inside.any():
        return float("nan")
    s_pos = np.asarray(score, np.float64)[t]
    s_neg = np.asarray(score, np.float64)[inside]
    # rank-based AUC with ties: P(score_pos > score_neg) + 0.5 P(equal).
    # searchsorted 'left' counts negatives strictly below s_pos, 'right' counts those at or
    # below, so (hi + lo)/2 = (#below) + 0.5*(#equal) — the same tie-aware AUC as
    # gems52.cotrain.view_auc.  (An earlier draft used n_neg - hi, which is 1 - AUC.)
    s_sorted = np.sort(s_neg)
    lo = np.searchsorted(s_sorted, s_pos, side="left")
    hi = np.searchsorted(s_sorted, s_pos, side="right")
    n_neg = s_neg.size
    return float(np.mean((hi + lo) / 2.0) / n_neg)


def canary_report(layer_iter, folds: list[dict]) -> dict:
    """Run the canary over every named layer and every fold.  Returns per-layer max AUC
    across folds and the registered verdict.

    ``layer_iter`` yields ``(name, full-grid array)`` ONE AT A TIME: 75 full-grid float32
    layers is ~3.7 GB on this grid and the box has 3 GB, so the caller must stream them
    (e.g. straight off the uint8 memmap) and this function must never hold more than one.
    """
    rows, worst = [], (None, -1.0)
    for name, arr in layer_iter:
        aucs = []
        for f in folds:
            region = f["region"] & np.isfinite(arr)
            a = layer_auc_canary(arr, f["truth"], region)
            if np.isfinite(a):
                aucs.append(a)
        del arr
        if aucs:
            mx = float(max(aucs))
            rows.append(dict(layer=name, max_auc_over_folds=round(mx, 4),
                             n_folds=int(len(aucs))))
            if mx > worst[1]:
                worst = (name, mx)
    leak = worst[1] > LEAKAGE_AUC_MAX
    return dict(threshold=LEAKAGE_AUC_MAX, n_layers=len(rows), rows=rows,
                worst_layer=worst[0], worst_auc=round(worst[1], 4),
                leakage_detected=bool(leak),
                verdict=("LEAKAGE: layer AUC > 0.90 — stop, report, trust nothing built on "
                         "that layer" if leak else
                         "no single layer exceeds AUC 0.90 on the holdout; no leakage detected "
                         "at this granularity"))


# --------------------------------------------------------------------------------------------
# the lane drift gate (parallel-run protocol, item 1)
# --------------------------------------------------------------------------------------------
def _read_prior_values(path) -> np.ndarray:
    with rasterio.open(str(path)) as src:
        a = src.read(1)
    return np.where(np.isfinite(a) & (a >= 0) & (a <= 1), a, 0).astype("<f4")


def _rank_once(a: np.ndarray) -> np.ndarray:
    """Average ranks of a full-grid array (float64).  Computed once per surface; every
    per-prior Spearman then reduces to a Pearson between two rank arrays."""
    from scipy.stats import rankdata
    return rankdata(a.ravel()).reshape(a.shape)


def _spearman_with_ranks(rank_a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rank correlation between a pre-ranked array and a raw array, tie-aware via
    average ranks on both sides (binary priors get their two average ranks in O(n))."""
    from scipy.stats import rankdata
    rb = rankdata(b.ravel()).reshape(b.shape)
    ra = rank_a.ravel()
    rb = rb.ravel()
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    denom = np.sqrt(float((ra * ra).sum()) * float((rb * rb).sum()))
    if denom <= 0:
        return float("nan")
    return float((ra * rb).sum() / denom)


def calibration_basenames(manifest_path) -> set:
    """Basenames of the rasters the repo's own data manifest classifies as CALIBRATION inputs.

    ``registry/data_manifest.json`` marks them by id prefix ``calib_`` or by a source path
    under ``inputs/calibration/`` (provenance: "calibration raster copied unchanged from the
    owner siblings").  These are owner-supplied metric-calibration rasters — e.g. the
    regular 5-px lattice used to measure the A/S ceiling (see ``registry/irregularities.json``)
    — not discovery lanes' placements.
    """
    try:
        manifest = json.loads(Path(manifest_path).read_text())
    except Exception:
        return set()
    files = manifest.get("files", manifest) if isinstance(manifest, dict) else manifest
    out = set()
    for entry in files:
        if not isinstance(entry, dict):
            continue
        eid = str(entry.get("id", ""))
        epath = str(entry.get("path", ""))
        dest = str(entry.get("dest", ""))
        if eid.startswith("calib") or "inputs/calibration" in epath:
            if dest:
                out.add(Path(dest).name)
            elif epath:
                out.add(Path(epath).name)
    return out


def lane_drift_report(surface: np.ndarray, dots: np.ndarray | None, priors,
                      valid: np.ndarray, *, max_rank_corr: float = LANE_MAX_RANK_CORR,
                      max_dots_frac: float = LANE_MAX_DOTS_FRAC,
                      proximity_px: int = LANE_PROXIMITY_PX,
                      calibration: set | None = None) -> dict:
    """The lane gate, on the surface before placement AND on the final dots.

    For every registry raster: Spearman rank correlation with ``surface`` (and with ``dots``
    when given), and — for the dots — the fraction of the run's dots within ``proximity_px``
    of that raster's dots.  Drift = any rank correlation > ``max_rank_corr`` OR any dots
    fraction > ``max_dots_frac``: the run has drifted into another lane; log it as a duplicate
    and stop.

    Registered correction H60-6: the 3-px proximity COMPONENT excludes calibration rasters
    (``calibration`` = :func:`calibration_basenames`; the manifest-driven classification,
    never a hand-picked list).  A calibration raster is an owner-supplied metric-calibration
    input — e.g. a dense regular lattice whose 3-px dilation covers about half the grid — so
    ANY budget-sized placement in the legal pool reads 70-84 % against it by pure geometry;
    that reading measures grid geometry, not duplication of another lane's discovery.  The
    raw proximity reading is still reported for every prior, calibration included, and BOTH
    Spearman components apply to every prior without exception.
    """
    surface = np.asarray(surface, np.float32)
    calibration = calibration or set()
    rows = []
    rank_surf = _rank_once(np.where(valid, surface, 0.0))
    rank_dots = _rank_once(np.asarray(dots, np.float32)) if dots is not None else None
    my_dots = np.asarray(dots, bool) if dots is not None else None
    n_dots = int(my_dots.sum()) if my_dots is not None else 0
    worst_corr, worst_frac = -1.0, 0.0
    worst_corr_prior = worst_frac_prior = None
    worst_frac_gate, worst_frac_gate_prior = 0.0, None
    for path in priors:
        try:
            v = _read_prior_values(path)
            if v.shape != surface.shape:
                rows.append(dict(path=str(path), error="shape mismatch"))
                continue
            is_calib = Path(str(path)).name in calibration
            prior_dots = v > 0
            sc = _spearman_with_ranks(rank_surf, np.where(valid, v, 0.0))
            row = dict(path=str(path), surface_spearman=round(float(sc), 4),
                       calibration_raster=bool(is_calib))
            if rank_dots is not None:
                dc = _spearman_with_ranks(rank_dots, v)
                row["dots_spearman"] = round(float(dc), 4)
                near = ndimage.binary_dilation(prior_dots, iterations=proximity_px)
                frac = float((my_dots & near).sum()) / max(n_dots, 1)
                row["dots_within_3px_frac"] = round(frac, 4)
                if frac > worst_frac:
                    worst_frac, worst_frac_prior = frac, str(path)
                if not is_calib and frac > worst_frac_gate:
                    worst_frac_gate, worst_frac_gate_prior = frac, str(path)
            if np.isfinite(sc) and abs(sc) > worst_corr:
                worst_corr, worst_corr_prior = abs(float(sc)), str(path)
            rows.append(row)
        except Exception as exc:
            rows.append(dict(path=str(path), error=f"{type(exc).__name__}: {str(exc)[:160]}"))
    surface_ok = all(abs(r.get("surface_spearman", 0.0)) <= max_rank_corr for r in rows
                     if "surface_spearman" in r)
    dots_ok = True
    if my_dots is not None:
        dots_ok = (all(abs(r.get("dots_spearman", 0.0)) <= max_rank_corr for r in rows
                       if "dots_spearman" in r)
                   and all(r.get("dots_within_3px_frac", 0.0) <= max_dots_frac
                           for r in rows
                           if "dots_within_3px_frac" in r and not r["calibration_raster"]))
    drift = bool(rows) and not (surface_ok and dots_ok)
    return dict(max_rank_corr=max_rank_corr, max_dots_frac=max_dots_frac,
                proximity_px=proximity_px, n_priors=len(rows),
                calibration_rasters_excluded_from_proximity=sorted(calibration),
                proximity_correction=("H60-6: calibration rasters (registry/data_manifest.json "
                                      "ids calib_* / inputs/calibration/*) are excluded from "
                                      "the 3-px proximity component only; their raw "
                                      "readings are reported and both Spearman components "
                                      "apply to every prior"),
                surface_max_abs_spearman=round(worst_corr, 4),
                surface_max_abs_spearman_prior=worst_corr_prior,
                dots_max_abs_spearman=round(max(
                    [abs(r.get("dots_spearman", 0.0)) for r in rows if "dots_spearman" in r]
                    or [0.0]), 4),
                dots_max_within_3px_frac=round(worst_frac, 4),
                dots_max_within_3px_prior=worst_frac_prior,
                dots_max_within_3px_frac_gate=round(worst_frac_gate, 4),
                dots_max_within_3px_gate_prior=worst_frac_gate_prior,
                surface_check_passed=bool(surface_ok),
                dots_check_passed=bool(dots_ok) if my_dots is not None else None,
                lane_drift_detected=drift,
                verdict=("DUPLICATE LANE: rank correlation or dot proximity exceeded the "
                         "registered thresholds — log as duplicate and stop" if drift else
                         "lane clean: no registry raster exceeds the rank-correlation or "
                         "dot-proximity thresholds, on the surface and on the final dots"),
                per_prior=rows,
                scope="Only the supplied, aligned accessible inventory; not a proof against "
                      "private/unlinked artifacts")


# --------------------------------------------------------------------------------------------
# the run card (lane protocol, item 5)
# --------------------------------------------------------------------------------------------
def evaluator_version() -> dict:
    """SHA-256 pins of the evaluator modules, so every HOLDOUT-DTI number names its
    evaluator version exactly."""
    out = {}
    for name in ("metric.py", "holdout.py", "h57.py", "h60.py", "emit.py"):
        p = Path(__file__).resolve().parent / name
        out[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def run_card(*, hypothesis: str, mechanism: str, mimic_processes: list[str],
             holdout: dict, registry_overlap: dict, raster_sha256: str,
             validator: dict, submission_name: str, submission_note: str,
             verdict: str, extra: dict | None = None) -> dict:
    """Assemble the lane protocol's closing JSON card.  ``holdout`` must already carry the
    HOLDOUT-DTI label, the evaluator version, the withheld positives and the 95 % CI."""
    card = dict(
        round="H60",
        lane="co-training, disagreement as the discovery signal (Blum & Mitchell COLT '98, "
             "doi:10.1145/279943.279962)",
        hypothesis=hypothesis,
        mechanism=mechanism,
        named_non_fault_processes_that_could_mimic_it=mimic_processes,
        holdout_dti=holdout,
        correlation_overlap_vs_registry=registry_overlap,
        raster_sha256=raster_sha256,
        validator_output=validator,
        submission_name=submission_name,
        submission_note=submission_note,
        submission_note_chars=len(submission_note),
        verdict=verdict,
        number_labels=("every holdout number is HOLDOUT-DTI (evaluator version, withheld "
                       "positives, 95% CI); every leaderboard number anywhere in this repo is "
                       "owner-reported; none is ORGANIZER-CONFIRMED (no submission-page "
                       "receipt exists); a projection is never written as a score"),
        evaluator_version=evaluator_version(),
    )
    if extra:
        card.update(extra)
    return card


def write_json(path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, allow_nan=False, default=str) + "\n")
