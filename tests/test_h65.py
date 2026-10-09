"""H65 regressions: the shared-template changes and the new halo sampler must mean what they say.

Pinned here, because each one could silently change a receipt or a verdict:

1. ``run_h61.external_applied`` accepts a store that the H63 step extension has also extended
   (IR-H65-001).  Before the fix, H61/H64 rejected the store that H63 had extended.
2. ``run_h61.sample_for_fit`` default is the H61 hard sample with unit weights, so the H61/H63/H64
   fit path is unchanged.
3. ``run_h65.sample_soft_halo``: the hard part equals H61's draw, every halo pixel is outside the
   full catalogue and strictly within 300 m of the visible catalogue, and each halo pixel's two
   weighted copies (label 1 with t, label 0 with 1 - t) carry total mass 1.
4. The H65 preregistration hash matches the frozen document.
5. The marginal acceptance bar is alpha * DTI (IR-H65-002): at the H64 baseline DTI 0.2778 a dot of
   credit 0.0572 raises DTI, and at DTI 0.2941 the same dot does not.  The prose form
   alpha*DTI/(1-alpha*DTI) predicts the opposite at 0.2778, so this test pins the code, not the prose.
6. The H64 build defaults still write H64 names and the original H64 card wording.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems52 import metric as M  # noqa: E402


# ---------------------------------------------------------------- 1. external guard (IR-H65-001)
def test_external_guard_accepts_a_store_extended_by_the_h63_step_layer():
    import run_h61 as base
    extended = "structural-core-v2-band6-B+external-geodawn-v1+h63-step-v1"
    assert base.external_applied(extended)
    assert base.external_applied("structural-core-v2-band6-B+external-geodawn-v1")
    assert not base.external_applied("structural-core-v2-band6-B")


def test_h63_check_still_requires_its_own_tag():
    """The H63 guard is unchanged: it still requires the H63 tag, so the two guards stay distinct."""
    text = (ROOT / "scripts/run_h63.py").read_text()
    assert 'endswith("+h63-step-v1")' in text


# ---------------------------------------------------------------- synthetic fold for the sampler tests
def _synthetic_fold():
    H = W = 200
    cat = np.zeros((H, W), bool)
    visible = np.zeros((H, W), bool)
    visible[100, 20:180] = True                    # the visible (known) trace
    cat |= visible
    cat[40, 20:180] = True                         # a hidden catalogue trace, withheld from training
    train = np.ones((H, W), bool)
    train[150:, :] = False                         # held-out region and buffer are not training domain
    truth = np.zeros((H, W), bool)
    truth[40, 20:180] = True
    region = np.zeros((H, W), bool)
    region[150:, :] = True
    fold = dict(fold=0, train=train, visible=visible, truth=truth, region=region)
    return fold, cat


# ---------------------------------------------------------------- 2. default hook is the H61 sample
def test_default_sample_for_fit_is_the_h61_hard_sample_with_unit_weights():
    import run_h61 as base
    fold, cat = _synthetic_fold()
    rows0, y0 = base.sample_train(fold, cat, np.random.default_rng(61052))
    rows, y, w = base.sample_for_fit(fold, cat, np.random.default_rng(61052))
    assert w is None
    assert np.array_equal(rows, rows0) and np.array_equal(y, y0)


# ---------------------------------------------------------------- 3. soft halo invariants
def test_soft_halo_hard_part_is_identical_and_halo_is_metric_weighted():
    import run_h61 as base
    import run_h65 as h65
    fold, cat = _synthetic_fold()
    rows0, y0 = base.sample_train(fold, cat, np.random.default_rng(61052))
    rows, y, w = h65.sample_soft_halo(fold, cat, np.random.default_rng(61052))
    n_hard = len(rows0)
    assert np.array_equal(rows[:n_hard], rows0) and np.array_equal(y[:n_hard], y0)
    assert np.all(w[:n_hard] == 1.0)
    halo_rows = rows[n_hard:]
    halo_w = w[n_hard:]
    take = len(halo_rows) // 2
    assert take > 0
    pick_a, pick_b = halo_rows[:take], halo_rows[take:]
    assert np.array_equal(pick_a, pick_b)                       # each halo pixel appears twice
    yh = y[n_hard:]
    assert np.all(yh[:take] == 1) and np.all(yh[take:] == 0)    # label 1 copy, then label 0 copy
    wa, wb = halo_w[:take], halo_w[take:]
    assert np.allclose(wa + wb, 1.0)                            # t + (1 - t) = 1 per halo pixel
    assert np.all((wa > 0) & (wa < 1))
    # halo pixels: never hidden truth, strictly inside the kernel support of the visible trace
    flat_cat = cat.ravel()
    assert not flat_cat[pick_a].any()
    d_m = _distance_m(fold["visible"])
    assert np.all(d_m.ravel()[pick_a] > 0) and np.all(d_m.ravel()[pick_a] < M.R_M)
    # the weight is exactly the metric kernel of the distance to the visible catalogue
    assert np.allclose(wa, np.clip(1.0 - d_m.ravel()[pick_a] / M.R_M, 0, 1))


def _distance_m(mask):
    from scipy import ndimage as ndi
    return ndi.distance_transform_edt(~mask) * M.PIXEL_M


# ---------------------------------------------------------------- 4. prereg pinned
def test_h65_preregistration_hash_is_pinned():
    reg = json.loads((ROOT / "registry/h65_preregistration.json").read_text())
    doc = ROOT / reg["hypothesis_document"]
    assert hashlib.sha256(doc.read_bytes()).hexdigest() == reg["hypothesis_sha256"]
    assert reg["budget"]["max_experiments"] == 1
    assert reg["thresholds"]["halo_radius_m"] == M.R_M


# ---------------------------------------------------------------- 5. acceptance bar is alpha * DTI
def _grid_with_two_truths(m_zero_dots: int):
    H = W = 60
    g = np.zeros((H, W), bool)
    g[5, 5] = True                 # g1: covered exactly by the baseline dot
    g[5, 55] = True                # g2: uncovered in the baseline; the candidate sits sqrt(8) px from it
    p0 = np.zeros((H, W), np.float32)
    p0[5, 5] = 1.0
    far = [(r, c) for r in range(20, 58, 4) for c in range(10, 50, 4)]
    for (r, c) in far[:m_zero_dots]:
        p0[r, c] = 1.0             # zero-credit dots, far from every truth pixel
    return p0, g


def test_acceptance_bar_is_alpha_times_dti_not_the_prose_form():
    k = max(0.0, 1.0 - np.sqrt(8.0) * M.PIXEL_M / M.R_M)          # 0.0572
    p0, g = _grid_with_two_truths(9)                               # DTI = 0.277778
    d0 = M.dti(p0, g)["dti"]
    assert abs(d0 - 0.2777778) < 1e-6
    p1 = p0.copy()
    p1[7, 57] = 1.0                                                # distance sqrt(8) px from g2
    assert M.dti(p1, g)["dti"] > d0                                # improves: k > alpha*DTI = 0.0556
    assert k > M.credit_bar(d0)
    prose = M.ALPHA * d0 / (1 - M.ALPHA * d0)                      # 0.0588: would predict no gain
    assert k > M.credit_bar(d0) and k < prose
    # the opposite side: at DTI 0.2941 the same dot does not raise DTI
    p0b, g2 = _grid_with_two_truths(8)
    d0b = M.dti(p0b, g2)["dti"]
    p1b = p0b.copy()
    p1b[7, 57] = 1.0
    assert M.dti(p1b, g2)["dti"] < d0b
    assert k < M.credit_bar(d0b)


# ---------------------------------------------------------------- 6. H64 defaults unchanged
def test_h64_build_defaults_keep_h64_names_and_wording():
    import run_h64 as h64
    assert h64.TAG == "h64" and h64.ROUND_NAME == "H64" and h64.PREFIX == "gems52-h64-"
    assert h64.CARD_TEXT["hypothesis"] == (
        "Sufficiency-gated co-training: a lower-capacity View A that generalises out of quadrant "
        "makes the exchange licensed; then disagreement ranks buried-cover candidates.")
    assert h64.CARD_TEXT["note_body"] == "co-train, A capacity cut, 3px dots, >200m off catalogue"
    assert h64.CARD_TEXT["note_exact_only"] == "exact-novel vs registry; lane DUPLICATE (70% rule)"
