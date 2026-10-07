"""Registered H57 training, routing, and OOF-independence helpers.

This module intentionally keeps the historical H52 feature lists separate from the corrected H57
views. Negative samples are catalogue-zero proxies, never verified fault absence; model scores are
relative rankings, not calibrated hidden-fault probabilities.
"""
from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from threadpoolctl import threadpool_limits

from gems52 import spatial


def training_rows(catalogue: np.ndarray, valid: np.ndarray, train: np.ndarray,
                  max_negatives: int, seed: int, collar_px: int = 3) -> tuple[np.ndarray, np.ndarray, dict]:
    """All training positives plus a deterministic negative-proxy sample outside a disk collar."""
    from scipy import ndimage

    catalogue = np.asarray(catalogue, bool)
    valid = np.asarray(valid, bool)
    train = np.asarray(train, bool)
    if catalogue.shape != valid.shape or train.shape != valid.shape:
        raise ValueError("catalogue, valid and train masks must have identical shapes")
    positive = np.flatnonzero((catalogue & train & valid).ravel())
    collar = ndimage.binary_dilation(catalogue, structure=spatial.disk(collar_px))
    negative_domain = train & valid & ~collar
    pool = np.flatnonzero(negative_domain.ravel())
    rng = np.random.default_rng(seed)
    n_negative = min(int(max_negatives), int(pool.size))
    negative = rng.choice(pool, size=n_negative, replace=False) if n_negative else np.empty(0, np.int64)
    rows = np.concatenate((positive, negative)).astype(np.int64, copy=False)
    y = np.concatenate((np.ones(positive.size, np.int8), np.zeros(negative.size, np.int8)))
    order = rng.permutation(rows.size)
    rows, y = rows[order], y[order]
    if not positive.size or not negative.size:
        raise ValueError(f"training split needs both proxy classes (positive={positive.size}, negative={negative.size})")
    receipt = dict(
        n_positive=int(positive.size), n_negative=int(negative.size),
        catalogue_prior=float((catalogue & train & valid).sum() / max(int((train & valid).sum()), 1)),
        positive_index_sha256=hashlib.sha256(np.sort(positive).astype("<i8").tobytes()).hexdigest(),
        negative_index_sha256=hashlib.sha256(np.sort(negative).astype("<i8").tobytes()).hexdigest(),
        negative_collar_px=int(collar_px), negative_collar_shape="Euclidean disk",
        max_sampled_negatives=int(max_negatives), seed=int(seed),
    )
    return rows, y, receipt


def fit_model(stack: np.ndarray, rows: np.ndarray, y: np.ndarray, columns: list[int],
              learner: dict[str, Any], seed: int, pseudo_positive: np.ndarray | None = None,
              pseudo_weight: float = 0.25) -> HistGradientBoostingClassifier:
    """Fit one registered HGB view; pseudo-positive rows receive their frozen sample weight."""
    if not rows.size or set(np.unique(y).tolist()) != {0, 1}:
        raise ValueError("base training rows must contain both proxy classes")
    params = {k: v for k, v in learner.items() if k != "class"}
    params["random_state"] = int(seed)
    model = HistGradientBoostingClassifier(**params)
    fit_rows = np.asarray(rows, dtype=np.int64)
    fit_y = np.asarray(y, dtype=np.int8)
    weights = np.ones(fit_y.size, dtype=np.float64)
    pseudo = np.asarray(pseudo_positive if pseudo_positive is not None else [], dtype=np.int64)
    if pseudo.size:
        if pseudo_weight <= 0 or not np.isfinite(pseudo_weight):
            raise ValueError("pseudo sample weight must be finite and positive")
        fit_rows = np.concatenate((fit_rows, pseudo))
        fit_y = np.concatenate((fit_y, np.ones(pseudo.size, np.int8)))
        weights = np.concatenate((weights, np.full(pseudo.size, pseudo_weight, np.float64)))
    flat = stack.reshape(-1, stack.shape[-1])
    X = flat[fit_rows][:, columns].astype(np.float32, copy=False)
    with threadpool_limits(limits=2):
        model.fit(X, fit_y, sample_weight=weights)
    return model


def predict_grid(stack: np.ndarray, model: HistGradientBoostingClassifier,
                 columns: list[int], domain: np.ndarray, chunk: int = 120_000) -> np.ndarray:
    """Predict only the named domain in chunks; outside it stays NaN, never a fake OOF zero."""
    domain = np.asarray(domain, bool)
    if domain.shape != stack.shape[:2]:
        raise ValueError("prediction domain shape differs from the stack")
    out = np.full(domain.size, np.nan, np.float32)
    ids = np.flatnonzero(domain.ravel())
    flat = stack.reshape(-1, stack.shape[-1])
    with threadpool_limits(limits=2):
        for start in range(0, ids.size, chunk):
            part = ids[start:start + chunk]
            X = flat[part][:, columns].astype(np.float32, copy=False)
            out[part] = model.predict_proba(X)[:, 1].astype(np.float32, copy=False)
    return out.reshape(domain.shape)


def training_thresholds(probability: np.ndarray, training_unlabelled: np.ndarray) -> dict:
    """Frozen q40/q80/q99 cutoffs over training-unlabelled pixels only."""
    p = np.asarray(probability, np.float32)
    m = np.asarray(training_unlabelled, bool)
    if p.shape != m.shape:
        raise ValueError("probability and threshold mask shapes differ")
    values = p[m & np.isfinite(p)]
    if values.size < 100:
        raise ValueError(f"too few finite training-unlabelled scores for thresholds: {values.size}")
    q40, q80, q99 = np.quantile(values, [0.40, 0.80, 0.99])
    return dict(q40=float(q40), q80=float(q80), q99=float(q99), n_reference=int(values.size),
                reference="training-unlabelled pixels only; relative confidence, not calibrated probability")


def compose_primary_field(p_a: np.ndarray, p_b: np.ndarray, thresholds: dict,
                          depth_rank: np.ndarray, domain: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
    """Apply the preregistered base/A-only/B-only/concordant field in a held-out region.

    For the rare degenerate case where tied quantiles make strata overlap, priority is concordant,
    then A-only, then B-only, as frozen in the H57 registration.
    """
    pa, pb = np.asarray(p_a, np.float32), np.asarray(p_b, np.float32)
    depth = np.asarray(depth_rank, np.float32)
    domain = np.asarray(domain, bool)
    if not (pa.shape == pb.shape == depth.shape == domain.shape):
        raise ValueError("H57 field input grids must have identical shapes")
    eligible = domain & np.isfinite(pa) & np.isfinite(pb) & np.isfinite(depth)
    ta, tb = thresholds["A"], thresholds["B"]
    concordant = eligible & (pa >= ta["q99"]) & (pb >= tb["q99"])
    a_only = eligible & (pa >= ta["q99"]) & (pb >= tb["q40"]) & (pb <= tb["q80"]) & ~concordant
    b_only = (eligible & (pb >= tb["q99"]) & (pa >= ta["q40"]) & (pa <= ta["q80"])
              & ~concordant & ~a_only)
    field = np.full(pa.shape, np.nan, np.float32)
    field[eligible] = 0.5 * pa[eligible] + 0.5 * pb[eligible]
    field[concordant] = np.minimum(pa[concordant], pb[concordant])
    field[a_only] = pa[a_only] * (0.35 + 0.40 * np.clip(depth[a_only], 0.0, 1.0))
    field[b_only] = 0.25 * pb[b_only]
    strata = np.zeros(pa.shape, np.uint8)
    strata[concordant] = 1
    strata[a_only] = 2
    strata[b_only] = 3
    counts = dict(
        domain_pixels=int(domain.sum()), scored_pixels=int(eligible.sum()),
        concordant_pixels=int(concordant.sum()), a_only_pixels=int(a_only.sum()),
        b_only_pixels=int(b_only.sum()), base_pixels=int((eligible & (strata == 0)).sum()),
        thresholds=thresholds,
    )
    return field, strata, counts


def independence_gate(rows_by_fold: dict[int, list[dict]], threshold: float = 0.6,
                      minimum_blocks: int = 20) -> dict:
    """Require non-degenerate block-error tests to pass in each fold and pooled."""
    from gems52.spatial import independence

    per_fold = {}
    all_rows = []
    for fold, rows in sorted(rows_by_fold.items()):
        all_rows.extend(rows)
        per_fold[str(fold)] = independence(rows, threshold=threshold, min_blocks=minimum_blocks)
    pooled = independence(all_rows, threshold=threshold, min_blocks=minimum_blocks)
    failures = []
    for fold, report in per_fold.items():
        if not report["allow_exchange"]:
            failures.append(f"fold {fold}: {report['reason']}")
    if not pooled["allow_exchange"]:
        failures.append(f"pooled: {pooled['reason']}")
    return dict(
        status="PASS" if not failures else "DISABLE_EXCHANGE",
        allow_exchange=not failures,
        threshold=float(threshold), minimum_blocks_per_fold=int(minimum_blocks),
        per_fold=per_fold, pooled=pooled, failures=failures,
        rule="both error metrics must be defined and max |Pearson|/|Spearman| < threshold in every fold and pooled; fail closed",
    )
