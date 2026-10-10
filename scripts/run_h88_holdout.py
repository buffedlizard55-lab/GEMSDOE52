#!/usr/bin/env python3
"""H88: hide-and-recover HOLDOUT-DTI for co-training with a disagreement-gated A-only stratum.

Frozen protocol: knowledge/80_h88_preregistered.md (SHA-256 pinned in registry/h88_preregistration.json).
This runner refuses to start if the protocol file no longer matches its pin.

Reuse, not forks
----------------
* View A and View B are imported from ``scripts/build_h87_cotrain_wavelength.py`` (H87's own functions).
* The H87 disagreement field is imported too (``compute_disagreement_field``), so the as-built rule is measured,
  not re-described.
* Folds, allowed sets, placement, scoring and bootstrap come from the shared ``gems52`` modules and are the same
  calls ``scripts/run_h86_holdout.py`` makes.

Catalogue use
-------------
The two views and their ranks are catalogue-free. The catalogue enters only through the fold construction
(``spatial.folds``: truth and visible traces) and the 200 m collar, which is taken from the VISIBLE catalogue only.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import rasterio  # noqa: E402

import build_h87_cotrain_wavelength as H87  # noqa: E402  (shared H87 view functions, not a copy)
from gems52 import evaluate_holdout as evaluator  # noqa: E402
from gems52 import nodes, spatial  # noqa: E402

PROTOCOL = ROOT / "knowledge" / "80_h88_preregistered.md"
PIN = ROOT / "registry" / "h88_preregistration.json"
FEATURES = ROOT / "data" / "training_features.tif"
LABELS = ROOT / "data" / "labels.tif"
SAMPLE = ROOT / "data" / "sample_submission.tif"
GEODAWN_RAD = ROOT / "data" / "external" / "geodawn_rad_u8.tif"
GEODAWN_EXT = ROOT / "data" / "external" / "geodawn_extensions_u8.tif"
OUT = ROOT / "evidence" / "h88_holdout.json"

K_FOLD = 9400
BUFFER_PX = 80
RING_PX = 2
SEED = 88001
CANARY_ALARM = 0.90
INDEP_ABANDON = 0.60
DRAWS = 1000
PRIMARY = "P_strict_cotrain"
BAR = 0.192829           # pre-registered: best measured arm on gems52-pooled-hide-v1 (evidence/h84_holdout.json)
Q_HI, Q_LO = 0.75, 0.25  # pre-registered stratum thresholds


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_pin() -> dict:
    pin = json.loads(PIN.read_text())
    actual = sha256_file(PROTOCOL)
    if actual != pin["sha256"]:
        raise SystemExit(f"protocol hash moved: pinned {pin['sha256']} actual {actual}; refusing to run")
    return pin


def rank01(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Rank within ``mask`` scaled to [0, 1]; zero outside. Ties are broken by flat order (as in H86)."""
    out = np.zeros(a.shape, np.float32)
    v = a[mask]
    order = np.argsort(v, kind="stable")
    r = np.empty(len(v), np.float32)
    r[order] = np.arange(len(v), dtype=np.float32) / max(len(v) - 1, 1)
    out[mask] = r
    return out


def allowed_for(fold: dict, valid: np.ndarray) -> np.ndarray:
    """Region, not visible, and outside the 200 m collar of the VISIBLE catalogue only (as H86)."""
    vd = ndi.distance_transform_edt(~fold["visible"])
    return fold["region"] & valid & ~fold["visible"] & (vd > RING_PX)


def place(field: np.ndarray, allowed: np.ndarray, k: int) -> np.ndarray:
    return nodes.spacing_select(field, allowed, k, min_px=3.0).astype(np.float32)


def build_fields(valid: np.ndarray):
    """All catalogue-free fields, computed once."""
    view_a = H87.compute_view_a(str(FEATURES), valid)
    view_b = H87.compute_view_b(str(FEATURES), str(GEODAWN_RAD), str(GEODAWN_EXT), valid)
    rA = rank01(view_a, valid)
    rB = rank01(view_b, valid)
    s_ab = valid & (rA >= Q_HI) & (rB <= Q_LO)   # A confident, B abstains
    s_ba = valid & (rB >= Q_HI) & (rA <= Q_LO)   # B confident, A abstains (control only)
    fields = {
        PRIMARY: (rA + 1.0 * s_ab).astype(np.float32),
        "h87_asbuilt": H87.compute_disagreement_field(view_a, view_b, valid,
                                                      np.zeros(valid.shape, bool)),  # no catalogue input
        "single_A": rA.astype(np.float32),
        "single_B": rB.astype(np.float32),
        "S_BA_control": (rB + 1.0 * s_ba).astype(np.float32),
    }
    strata = dict(S_AB_px=int(s_ab.sum()), S_BA_px=int(s_ba.sum()), eligible_px=int(valid.sum()))
    return fields, rA, rB, strata, (view_a, view_b)


def main() -> None:
    t0 = time.time()
    pin = check_pin()
    log(f"protocol pin verified ({pin['sha256'][:12]}…)")

    with rasterio.open(LABELS) as ds, rasterio.open(SAMPLE) as ref:
        if (ds.shape, ds.crs, ds.transform) != (ref.shape, ref.crs, ref.transform):
            raise SystemExit("labels grid != sample grid")
        labels = ds.read(1)
        domain = np.isfinite(ref.read(1))
    cat = labels == 1
    feat_valid = H87.footprint_all_bands(str(FEATURES))
    valid = feat_valid & domain
    log(f"eligible {int(valid.sum()):,} px; catalogue {int(cat.sum()):,} px")

    folds = list(spatial.folds(cat, valid, buffer_px=BUFFER_PX))
    withheld = int(sum((f["truth"] & f["region"]).sum() for f in folds))
    log(f"folds {len(folds)}; withheld positive px {withheld:,}")

    fields, rA, rB, strata, (view_a, view_b) = build_fields(valid)
    log(f"views built; strata {strata}")
    corr_views = float(np.corrcoef(view_a[valid], view_b[valid])[0, 1])
    log(f"view A vs view B Pearson over eligible footprint: {corr_views:.4f}")

    arms = ["P_strict_cotrain", "h87_asbuilt", "single_A", "single_B", "S_BA_control", "random"]
    terms = {a: None for a in arms}
    per_fold = []
    canary = {k: [] for k in ("rank_A", "rank_B", PRIMARY, "h87_asbuilt")}
    indep_rows = []
    q_thr = (float(np.quantile(rA[valid], Q_HI)), float(np.quantile(rB[valid], Q_HI)))

    for fold in folds:
        f = fold["fold"]
        allowed = allowed_for(fold, valid)
        rng = np.random.default_rng(SEED + f)
        rnd = np.full(valid.shape, -1.0, np.float32)
        ai = np.flatnonzero(allowed.ravel())
        rnd.ravel()[ai] = rng.random(len(ai), dtype=np.float32)

        emissions = {
            "P_strict_cotrain": place(fields[PRIMARY], allowed, K_FOLD),
            "h87_asbuilt": place(fields["h87_asbuilt"], allowed, K_FOLD),
            "single_A": place(fields["single_A"], allowed, K_FOLD),
            "single_B": place(fields["single_B"], allowed, K_FOLD),
            "S_BA_control": place(fields["S_BA_control"], allowed, K_FOLD),
            "random": place(rnd, allowed, K_FOLD),
        }
        rec = dict(fold=f, withheld_positive_px=int((fold["truth"] & fold["region"]).sum()),
                   allowed_px=int(allowed.sum()), arms={})
        for arm, em in emissions.items():
            res, term = evaluator.evaluate(em, fold, valid, block_side=200)
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            rec["arms"][arm] = dict(dti=res["dti"], placed=int(em.sum()), tpw=res["tpw"], fpw=res["fpw"], fnw=res["fnw"])
            log(f"fold {f} {arm}: DTI {res['dti']:.6f} placed {int(em.sum())}")

        truth_in = (fold["truth"] & fold["region"])[allowed]
        if truth_in.any() and (~truth_in).any():
            for name, arr in (("rank_A", rA), ("rank_B", rB), (PRIMARY, fields[PRIMARY]),
                              ("h87_asbuilt", fields["h87_asbuilt"])):
                auc = float(roc_auc_score(truth_in.astype(int), arr[allowed]))
                canary[name].append(dict(fold=f, auc=auc))

        negatives = fold["region"] & valid & ~fold["truth"]
        indep_rows += spatial.negative_block_errors(rA, rB, negatives, f, q_thr)

        rec["canary_done"] = True
        per_fold.append(rec)
        del emissions, rnd

    summary = evaluator.pooled_summary(terms, draws=DRAWS, seed=SEED, candidate=PRIMARY)
    indep = spatial.independence(indep_rows, threshold=INDEP_ABANDON)
    canary_max = {k: max(x["auc"] for x in v) for k, v in canary.items()}
    canary_alarm = any(v > CANARY_ALARM for v in canary_max.values())

    scores = summary["scores"]
    pdiff = summary["paired_differences"]
    p_dti = scores[PRIMARY]["dti"]
    if canary_alarm:
        verdict, why = "NEGATIVE", "leakage canary alarm (AUC > 0.90); round void"
    elif indep.get("max_abs_correlation") is not None and indep["max_abs_correlation"] >= INDEP_ABANDON:
        verdict, why = "NEGATIVE", "views strongly correlated on negatives; co-training abandoned (protocol §5)"
    else:
        gate_bar = p_dti >= BAR
        gate_single = pdiff["single_B"]["ci95"][0] > 0
        gate_random = pdiff["random"]["ci95"][0] > 0
        ok = gate_bar and gate_single and gate_random
        verdict = "POSITIVE" if ok else "NEGATIVE"
        why = (f"bar {p_dti:.6f} vs {BAR}: {'pass' if gate_bar else 'fail'}; "
               f"P-single_B lower CI {pdiff['single_B']['ci95'][0]:.6f}: {'pass' if gate_single else 'fail'}; "
               f"P-random lower CI {pdiff['random']['ci95'][0]:.6f}: {'pass' if gate_random else 'fail'}")

    out = dict(
        round="H88", stage="holdout", evidence_class="HOLDOUT-DTI",
        evaluator_version=evaluator.VERSION, protocol=str(PROTOCOL.relative_to(ROOT)),
        protocol_sha256=pin["sha256"], primary=PRIMARY, budget_per_fold=K_FOLD, folds=len(folds),
        buffer_px=BUFFER_PX, ring_px=RING_PX, withheld_positive_px=withheld,
        eligible_px=int(valid.sum()), strata=strata, view_pearson_eligible=corr_views,
        scores={a: dict(dti=scores[a]["dti"], ci95=scores[a]["ci95"]) for a in arms},
        paired_differences={k: dict(delta=v["delta"], ci95=v["ci95"]) for k, v in pdiff.items()},
        canary=dict(alarm_threshold=CANARY_ALARM, max_auc=canary_max, alarm=canary_alarm, per_fold=canary),
        independence=dict({k: v for k, v in indep.items() if k != "blocks"}, n_blocks=len(indep_rows),
                          proxy_note="unsupervised scores: 'errors' are score values on held-out negatives"),
        per_fold=per_fold,
        decision=dict(verdict=verdict, reason=why, bar=BAR, bar_source=pin["decision_bar_source"]),
        inputs=dict(features_sha256=sha256_file(FEATURES), labels_sha256=sha256_file(LABELS),
                    sample_sha256=sha256_file(SAMPLE), geodawn_rad_sha256=sha256_file(GEODAWN_RAD),
                    geodawn_ext_sha256=sha256_file(GEODAWN_EXT)),
        implementation_hashes=evaluator.implementation_hashes(),
        elapsed_seconds=round(time.time() - t0, 1),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=float) + "\n")
    log("HOLDOUT-DTI: " + json.dumps({a: round(scores[a]["dti"], 6) for a in arms}))
    log("CI95: " + json.dumps({a: [round(x, 6) for x in scores[a]["ci95"]] for a in arms}))
    log("paired (P - arm): " + json.dumps({k: [round(v["delta"], 6), [round(x, 6) for x in v["ci95"]]]
                                             for k, v in pdiff.items()}))
    log("canary max AUC: " + json.dumps({k: round(v, 4) for k, v in canary_max.items()}))
    log(f"independence max |rho| {indep.get('max_abs_correlation')}; measured={indep.get('measured')}")
    log(f"VERDICT {verdict}: {why}")
    log(f"wrote {OUT}")


if __name__ == "__main__":
    main()
