#!/usr/bin/env python3
"""Historical H60 research builder, disabled under the terminal H75 stop.

H75 is the current DUPLICATE/STOP. This legacy builder is fail-closed while H75 is
published; it cannot rebuild an artifact, create a current run card, move any H60 pointer,
authorize a slot, or provide portal instructions. Its old research ZIP format, if ever
reviewed in a separately authorized context, is a single TIFF only.

The frozen H60 receipts remain historical evidence. This module must never change
submission/LATEST.txt or submission/H60_LATEST.txt.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gems52 import grid as G          # noqa: E402
from gems52 import gates as GT        # noqa: E402
from gems52.emit import greedy_emit   # noqa: E402
from gems52.h60 import Stack          # noqa: E402
from gems52.metric import dti         # noqa: E402

EV = ROOT / "evidence"
SUB = ROOT / "submission"
DL = ROOT / "docs/downloads"
WORK = Path("/tmp/gemswork/layers")
SEED = 20261009
RING_M = 200.0
BAND_OF = {1: "magnetic anomaly", 2: "reduced-to-pole magnetics", 3: "TMI horizontal gradient",
           4: "strain second invariant", 5: "isostatic gravity slope",
           6: "aeroradiometric total count (tag says magnetic tilt; IR-52-019)",
           7: "geodetic shear rate", 8: "geodetic dilatation rate", 9: "TMI vertical gradient",
           10: "distance to earthquake", 11: "isostatic gravity vertical gradient",
           12: "detrended elevation", 13: "isostatic gravity anomaly", 14: "total magnetic intensity",
           15: "depth to basement surface", 16: "earthquake density", 17: "surface conductivity",
           18: "isostatic gravity horizontal gradient", 19: "detrended elevation slope"}


def log(*a):
    print(*a, flush=True)


def save(name, obj):
    (EV / name).write_text(json.dumps(obj, indent=1, default=_fb) + "\n")


def _fb(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)


def h75_stop_is_current() -> bool:
    home = ROOT / "docs" / "index.html"
    status = ROOT / "docs" / "h75-executive-summary.html"
    return (home.is_file() and status.is_file()
            and "H75: DUPLICATE/STOP" in home.read_text(errors="replace")
            and "DUPLICATE/STOP · RESEARCH ONLY · NOT FOR SUBMISSION" in status.read_text(errors="replace"))


def main() -> int:
    if h75_stop_is_current():
        print("H75 terminal DUPLICATE/STOP is current; H60 historical builder exited before any fit, artifact, ZIP, or pointer write")
        return 0
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    st = Stack(WORK)
    lab = rasterio.open(ROOT / "data/labels.tif").read(1)
    cat = lab == 1
    foot = lab != -1
    with rasterio.open(ROOT / "data/sample_submission.tif") as s:
        sub_ok = np.isfinite(s.read(1))
    H, W = lab.shape

    sel = json.loads((EV / "h60_selection.json").read_text())
    arm = sel["selected"]["arm"]
    budget = int(sel["selected"]["budget"])
    log(f"[build] registered choice arm={arm} budget={budget} (mean holdout DTI "
        f"{sel['selected']['mean_dti']:.5f}, {sel['selected']['fold_wins']}/4 folds vs random)")
    # The recorded amendment (scripts/h60_budget_amendment.py) overrides the budget only,
    # with the measurement that justifies it attached.  Never applied silently: N-4.
    amend_path = EV / "h60_budget_amendment.json"
    amendment = json.loads(amend_path.read_text()) if amend_path.exists() else None
    if amendment:
        budget = int(amendment["amended_budget"])
        log(f"[build] AMENDED budget={budget} — {amendment['decision'][:160]}…")

    # ------------------------------------------------------- final fit on all labels
    pos = foot & cat
    neg = foot & ~cat
    ys, xs = np.nonzero(pos)
    rng = np.random.default_rng(SEED)
    ny, nx = np.nonzero(neg)
    k = min(4 * ys.size, ny.size)
    pick = rng.choice(ny.size, size=k, replace=False)
    ny, nx = ny[pick], nx[pick]
    ty = np.concatenate([ys, ny]); tx = np.concatenate([xs, nx])
    yy = np.concatenate([np.ones(ys.size, np.int8), np.zeros(ny.size, np.int8)])
    log(f"[build] final fit: {ys.size} positives, {ny.size} negatives")

    pA = np.zeros((H, W), np.float32)
    pB = np.zeros((H, W), np.float32)
    for view, out in (("A", pA), ("B", pB)):
        nl = len(st.view_names(view))
        X = st.rows(view, ty, tx)
        m = HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.08, max_leaf_nodes=31, min_samples_leaf=60,
            l2_regularization=1.0, early_stopping=False, random_state=SEED)
        m.fit(X, yy)
        for b0 in range(0, H, 256):
            b1 = min(H, b0 + 256)
            Xb = np.transpose(st.block(view, b0, b1), (1, 2, 0)).reshape(-1, nl)
            out[b0:b1] = m.predict_proba(Xb)[:, 1].astype(np.float32).reshape(b1 - b0, W)
        log(f"[build] final View {view} predicted")

    # ------------------------------------------------------------------ ranking field
    def combine(a, b, how):
        a = np.nan_to_num(a, nan=0.0); b = np.nan_to_num(b, nan=0.0)
        if how == "A_only":
            return a
        if how == "B_only":
            return b
        if how == "union_max":
            return np.maximum(a, b)
        if how == "A_where_B_abstains":
            return np.where(b <= 0.5, a, 0.0)
        if how == "B_where_A_abstains":
            return np.where(a <= 0.5, b, 0.0)
        if how == "disagreement_sum":
            return np.abs(a - b)
        raise ValueError(how)

    field = combine(pA, pB, arm)

    # --------------------------------------------------------------- emission domain
    ed_cat = ndimage.distance_transform_edt(~cat, sampling=100.0)
    allow = foot & sub_ok & (ed_cat > RING_M)
    log(f"[build] allowed emission domain: {int(allow.sum())} px "
        f"(footprint {int(foot.sum())}, >200 m from catalogue)")

    emitted, estats = greedy_emit(field, allow, dti_projected=0.0, budget=budget,
                                  pool=400_000, log=lambda *a: None)
    n_px = int((emitted > 0).sum())
    log(f"[build] emitted {n_px} px; expected credit {estats['total_expected_credit']:.1f}")

    # not merely the union of the two views, at the same budget
    def topk(f, k):
        v = np.where(allow, np.nan_to_num(f, nan=-1.0), -2.0).ravel()
        o = np.argpartition(-v, k)[:k]
        m = np.zeros(H * W, bool); m[o] = True
        return m.reshape(H, W)

    uA, uB = topk(pA, n_px), topk(pB, n_px)
    em = emitted > 0
    union_views = uA | uB
    build = dict(
        round="H60", generated_utc=ts, arm=arm, budget=budget, emitted_px=n_px,
        selection=sel["selected"], emit_stats=estats,
        not_merely_union_of_the_two_views=dict(
            fraction_inside_topk_viewA=float((em & uA).sum() / max(n_px, 1)),
            fraction_inside_topk_viewB=float((em & uB).sum() / max(n_px, 1)),
            fraction_inside_topk_union_of_views=float((em & union_views).sum() / max(n_px, 1)),
            fraction_outside_both_topk=float((em & ~union_views).sum() / max(n_px, 1)),
            note="the emitter maximises expected triangular max-coverage of the selected "
                 "field, so it spreads a hard-core pattern rather than taking a top-K; "
                 "the fraction outside both views' own top-K is the honest measure"),
        nearest_emitted_to_catalogue_m=float(ed_cat[em].min()) if em.any() else None,
        emitted_outside_footprint=int((em & ~foot).sum()),
        emitted_outside_submission_domain=int((em & ~sub_ok).sum()))
    save("h60_build.json", build)

    # ------------------------------------------------------------------ write raster
    short = "h60-" + arm.lower().replace("_", "") + f"-{n_px}px"
    name = f"gems52-{short}-{ts}-{hashlib.sha256(emitted.tobytes()).hexdigest()[:12]}-zeros"
    if len(name) > 200:
        name = name[:200]
    arr = emitted.astype(np.float32)
    info = G.write_geotiff(SUB / f"{name}.tif", arr, nodata=None)
    log(f"[build] wrote submission/{name}.tif  {info['bytes']} bytes  "
        f"min={info['min']} max={info['max']} nan={info['n_nan'] if 'n_nan' in info else 0}")

    # ---------------------------------------------------------------------- receipts
    prior_roots = ["data/scored", "data/reference", "submission", "docs/downloads"]
    # find_priors already excludes copies by *basename* (IR-52-026), which covers
    # docs/downloads/<name>.tif.  It cannot cover the canonical alias
    # docs/downloads/h60-cotrain-candidate.tif, whose basename differs from the artefact's; without
    # this exclusion a second run of the builder compares the artefact against its own
    # served alias and reports novel_fraction = 0.0 and pattern_unique = False, the one
    # verdict that would stop a legitimate submission.  Measured, not reasoned about.
    alias = (DL / "h60-cotrain-candidate.tif").resolve()
    priors = [p for p in GT.find_priors(prior_roots, exclude=SUB / f"{name}.tif")
              if Path(p).resolve() != alias]
    uniq = GT.uniqueness_report(arr, priors)
    fmt = GT.format_report(SUB / f"{name}.tif", ROOT / "data/sample_submission.tif",
                           footprint=foot)
    save("h60_format_gate.json", fmt)
    save("h60_uniqueness.json", uniq)
    log(f"[gate] format ok={fmt['ok']} problems={fmt['problems']}")
    log(f"[gate] uniqueness pattern_unique={uniq['canonical_pattern_unique']} "
        f"novel_fraction={uniq['novel_fraction']:.4f} literal_union={uniq['equals_literal_prior_union']} "
        f"priors={uniq['n_priors_checked']}")

    # sanity: DTI is only computable against a truth we do not have; report the metric
    # identity instead so nobody mistakes a projection for a score
    metric_note = dict(
        dti_identity="DTI = T / (0.2*T + 0.2*(S - M) + 0.8*|G|) with S = emitted mass",
        S=n_px,
        note="T, M and |G| are properties of the hidden truth and are NOT known here; no "
             "score is projected in this receipt")

    # --------------------------------------------------------------------- reasoning
    b15 = rasterio.open(ROOT / "data/training_features.tif").read(15).astype(np.float32)
    b17 = rasterio.open(ROOT / "data/training_features.tif").read(17).astype(np.float32)
    b12 = rasterio.open(ROOT / "data/training_features.tif").read(12).astype(np.float32)
    b06 = rasterio.open(ROOT / "data/training_features.tif").read(6).astype(np.float32)
    b14 = rasterio.open(ROOT / "data/training_features.tif").read(14).astype(np.float32)
    fin15 = np.isfinite(b15)
    q = lambda a, v: (float((a[fin15] < v).mean()) if np.isfinite(v) else None)  # noqa: E731

    strat_thr = (json.loads((EV / "h60_strata.json").read_text()) or {}).get("thresholds", {})
    cA = float(strat_thr.get("confident_A", 0.90)); cB = float(strat_thr.get("confident_B", 0.90))
    aA = float(strat_thr.get("abstain_A", 0.50)); aB = float(strat_thr.get("abstain_B", 0.50))
    log(f"[reasoning] stratum cut points read from the receipt: confident A>={cA:.4f} B>={cB:.4f}, "
        f"abstain A<={aA:.4f} B<={aB:.4f}")
    ey, ex = np.nonzero(em)
    csv_path = EV / f"h60-{n_px}px-candidate-geology.csv"
    n_a_only = 0
    with csv_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "utm_easting_m", "utm_northing_m", "p_view_A", "p_view_B",
                    "agreement_stratum", "depth_to_basement_m", "depth_percentile_in_footprint",
                    "surface_conductivity", "detrended_elevation_m", "radiometric_total_count",
                    "total_magnetic_intensity", "dist_to_nearest_mapped_trace_m",
                    "geological_reasoning", "explicit_falsifier"])
        for i, (r, c) in enumerate(zip(ey, ex)):
            pa, pb = float(pA[r, c]), float(pB[r, c])
            if pa >= cA and pb <= aB:
                strat = "A_only (geophysics confident, surface abstains)"
                n_a_only += 1
            elif pb >= cB and pa <= aA:
                strat = "B_only (surface confident, geophysics abstains)"
            elif pa >= cA and pb >= cB:
                strat = "concordant"
            else:
                strat = "neither view confident"
            d = float(b15[r, c]) if np.isfinite(b15[r, c]) else None
            dp = q(b15, b15[r, c]) if d is not None else None
            east = 243350.0 + 100.0 * (c + 0.5)
            north = 4508550.0 - 100.0 * (r + 0.5)
            if strat.startswith("A_only"):
                reason = (f"Potential-field/subsurface view is confident (p_A={pa:.3f}) while the "
                          f"surface view abstains (p_B={pb:.3f}); the cell sits at "
                          f"{d if d is None else round(d, 1)} m to basement "
                          f"({None if dp is None else round(dp * 100, 1)} pctile of the footprint), "
                          f"{ed_cat[r, c]:.0f} m from the nearest mapped trace. Buried "
                          f"basin-margin normal fault beneath alluvial cover: a basement-depth "
                          f"offset with no surface scarp is exactly what the Quaternary "
                          f"compilation cannot contain.")
                fals = ("Refuted if a 1 km profile across this cell shows a monotonic basement "
                        "ramp with no offset, or if the gravity/conductivity step is explained "
                        "by a mapped lithologic contact.")
            elif strat.startswith("B_only"):
                reason = (f"Surface view is confident (p_B={pb:.3f}) while the geophysical view "
                          f"abstains (p_A={pa:.3f}) at {ed_cat[r, c]:.0f} m from the nearest "
                          f"mapped trace. A topographic lineament with no subsurface expression "
                          f"is more often an erosion line, a road or a bedding-plane scarp than "
                          f"a fault; retained only because the surface evidence is linear and "
                          f"the cell clears the 200 m ring gate.")
                fals = ("Refuted if the lineament is discontinuous over <500 m, parallels "
                        "modern drainage, or follows a mapped road or alluvial-fan edge.")
            else:
                reason = (f"Both views weak-to-moderate (p_A={pa:.3f}, p_B={pb:.3f}); placed by "
                          f"the metric-aware coverage greedy at {ed_cat[r, c]:.0f} m from the "
                          f"nearest mapped trace, so it contributes expected kernel coverage "
                          f"rather than a specific structural claim.")
                fals = "Refuted if no lineament of any orientation can be traced through the cell."
            w.writerow([int(r), int(c), round(east, 1), round(north, 1), round(pa, 5), round(pb, 5),
                        strat, None if d is None else round(d, 2),
                        None if dp is None else round(dp, 5),
                        None if not np.isfinite(b17[r, c]) else round(float(b17[r, c]), 5),
                        None if not np.isfinite(b12[r, c]) else round(float(b12[r, c]), 3),
                        None if not np.isfinite(b06[r, c]) else round(float(b06[r, c]), 4),
                        None if not np.isfinite(b14[r, c]) else round(float(b14[r, c]), 4),
                        round(float(ed_cat[r, c]), 1), reason, fals])
    save("h60_reasoning.json", dict(csv=str(csv_path), rows=int(n_px), a_only_rows=int(n_a_only),
                                    stratum_cut_points=dict(confident_A=cA, confident_B=cB,
                                                            abstain_A=aA, abstain_B=aB),
                                    budget_amendment=amendment,
                                    scope="one row per emitted pixel; these are hypotheses for "
                                          "Phase-2 geological review, not verified faults",
                                    metric_note=metric_note))
    log(f"[reasoning] {n_px} rows ({n_a_only} A-only) -> {csv_path}")

    # --------------------------------------------------------------- zip + short path
    SUB.mkdir(exist_ok=True); DL.mkdir(parents=True, exist_ok=True)
    zpath = SUB / f"{name}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(SUB / f"{name}.tif", f"{name}.tif")
    for dst in (DL / f"{name}.tif", DL / f"{name}.zip", DL / "h60-cotrain-candidate.tif",
                DL / "h60-cotrain-candidate.zip"):
        shutil.copy2(zpath if dst.suffix == ".zip" else SUB / f"{name}.tif", dst)
    shutil.copy2(csv_path, DL / f"{name}-geology.csv")

    # re-read what is actually served, and prove the range from those bytes
    served = GT.read_raster(DL / f"{name}.tif")
    proof = dict(served_path=str(DL / f"{name}.tif"),
                 min=float(np.nanmin(served)), max=float(np.nanmax(served)),
                 n_nan=int(np.isnan(served).sum()), all_finite=bool(np.isfinite(served).all()),
                 values_set=sorted({float(v) for v in np.unique(served)})[:8],
                 in_range=bool(np.nanmin(served) >= 0.0 and np.nanmax(served) <= 1.0))
    final = dict(name=name, artifact_status="HISTORICAL RESEARCH ONLY · NOT FOR SUBMISSION",
                 approved_for_submission=False, approved_for_weekly_slot=False,
                 tif_sha256=info["sha256"], bytes=info["bytes"],
                 emitted_px=n_px, zip_bytes=zpath.stat().st_size,
                 range_proof_from_served_bytes=proof,
                 format_gate_ok=fmt["ok"], format_problems=fmt["problems"],
                 uniqueness=dict(pattern_unique=uniq["canonical_pattern_unique"],
                                 novel_fraction=uniq["novel_fraction"],
                                 literal_union=uniq["equals_literal_prior_union"],
                                 support_gate_ok=uniq["support_novelty_gate_ok"],
                                 priors_checked=uniq["n_priors_checked"]),
                 ok_to_download=True,
                 generated_utc=ts)
    save("h60_artifact.json", final)
    log("historical artifact only; no H60 or global submission pointer is changed")
    log(f"[build] artefact {name}  range {proof['min']}..{proof['max']} "
        f"nan={proof['n_nan']} in_range={proof['in_range']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
