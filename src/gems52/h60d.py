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
                      calibration: set | None = None, sample=None) -> dict:
    """Compatibility adapter to the shared strict gate; calibration grants no exemption.

    Production callers supply the competition sample. For older synthetic callers,
    the first prior defines the reference grid. Missing/unaligned inputs fail closed.
    Diagnostics are never rounded before a threshold decision.
    """
    from .gates import lane_uniqueness_report

    if proximity_px != 3:
        raise ValueError("the registered shared gate requires Euclidean radius 3 px")
    priors = list(priors)
    reference = sample if sample is not None else (priors[0] if priors else None)
    reports = {}
    for phase, arr in (("surface", surface), ("dots", dots)):
        if arr is None:
            continue
        try:
            if reference is None:
                raise ValueError("no registry/reference supplied")
            reports[phase] = lane_uniqueness_report(
                arr, valid, priors, sample=reference, phase=phase,
                rank_limit=max_rank_corr, near_limit=max_dots_frac)
        except (ValueError, OSError, rasterio.errors.RasterioError) as exc:
            reports[phase] = dict(ok=False, duplicate=False, per_prior=[],
                                  error=f"{type(exc).__name__}: {exc}")
    rows = []
    dot_rows = {r['path']: r for r in reports.get('dots', {}).get('per_prior', [])}
    for r in reports['surface']['per_prior']:
        row = dict(path=r['path'], calibration_raster=Path(r['path']).name in (calibration or set()))
        if r.get('spearman') is not None:
            row['surface_spearman'] = r['spearman']
        d = dot_rows.get(r['path'], {})
        if d.get('spearman') is not None:
            row['dots_spearman'] = d['spearman']
        if d.get('near_3px_fraction') is not None:
            row['dots_within_3px_frac'] = d['near_3px_fraction']
        if r.get('error') or d.get('error'):
            row['error'] = r.get('error') or d['error']
        rows.append(row)

    def maximum(key, absolute=False):
        available = [r for r in rows if key in r]
        if not available:
            return None, None
        row = max(available, key=lambda r: abs(r[key]) if absolute else r[key])
        return (abs(row[key]) if absolute else row[key]), row['path']

    sc, sp = maximum('surface_spearman', True)
    dc, _ = maximum('dots_spearman', True)
    near, np_ = maximum('dots_within_3px_frac')
    ok = all(r['ok'] for r in reports.values())
    duplicate = any(r['duplicate'] for r in reports.values())
    return dict(max_rank_corr=max_rank_corr, max_dots_frac=max_dots_frac,
                proximity_px=3, n_priors=len(priors),
                calibration_rasters_excluded_from_proximity=[],
                proximity_correction="H60-6 withdrawn: shared strict gate includes EVERY supplied registry raster; Euclidean <=3 px on the valid footprint",
                surface_max_abs_spearman=sc, surface_max_abs_spearman_prior=sp,
                dots_max_abs_spearman=dc, dots_max_within_3px_frac=near,
                dots_max_within_3px_prior=np_, dots_max_within_3px_frac_gate=near,
                dots_max_within_3px_gate_prior=np_,
                surface_check_passed=reports['surface']['ok'],
                dots_check_passed=reports['dots']['ok'] if dots is not None else None,
                lane_drift_detected=not ok, duplicate=duplicate,
                verdict=("DUPLICATE LANE: stop" if duplicate else
                         "INCOMPLETE AUDIT: stop" if not ok else "lane clean within supplied registry"),
                per_prior=rows, shared_reports=reports,
                scope="Supplied aligned inventory only; no proof against unavailable priors")


# --------------------------------------------------------------------------------------------
# the run card (lane protocol, item 5)
# --------------------------------------------------------------------------------------------
def evaluator_version() -> dict:
    """SHA-256 pins of the evaluator modules, so every HOLDOUT-DTI number names its
    evaluator version exactly."""
    out = {}
    for name in ("metric.py", "holdout.py", "h57.py", "h60d.py", "emit.py"):
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
        round="H60D",
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
