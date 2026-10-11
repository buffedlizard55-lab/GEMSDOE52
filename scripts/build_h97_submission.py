#!/usr/bin/env python3
"""Build the H97 co-training texture submission artifact (unique TIF) + gates + run card.

The shipped field is the **preregistered primary** of H97, `xtex_dis`:
    field = pct_rank(P_A) - pct_rank(P_B)   over the allowed domain
where P_A / P_B are the out-of-fold View-A / View-B *texture* learners of
``knowledge/97_hypotheses_H97_preregistered.md`` (frozen; pinned in
``registry/h97_preregistration.json``).

Production fit vs holdout fit
-----------------------------
The holdout measured the PROCEDURE with per-fold fits (``scripts/run_h97.py``).  The artifact is the
same procedure applied with a single fit on all labeled data (the fold whose *visible* catalogue is
the whole catalogue).  That is stated here, once, and is not a degree of freedom: no threshold, lag,
band or placement parameter is chosen from the holdout.

The artifact is emitted with the repository's shared, metric-aware placement
(``gems52.nodes.spacing_select``, min 3 px = the metric's own 300 m max-cover scale), the 200 m
collar from the mapped catalogue, a binary {0,1} support, and the all-finite container
(``write_geotiff_portal_exact(..., outside="zero")``) that cannot fail a literal `[0,1]` range test.

Usage: python3 scripts/build_h97_submission.py [--budget 37654]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np                                                    # noqa: E402
import rasterio                                                       # noqa: E402
from scipy import ndimage as ndi                                      # noqa: E402
from scipy.stats import rankdata                                      # noqa: E402

import run_h61 as base                                                # noqa: E402
import run_h97 as H97                                                 # noqa: E402
from gems52 import gates, grid, nodes                                 # noqa: E402

SUB = ROOT / "submission"
DOCS = ROOT / "docs/downloads"
EVID = ROOT / "evidence"
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
NAME = f"gems52-h97-cotrain-atexture-disagreement-{STAMP}"
BUDGET = 37654
COLLAR_PX = 2


def log(*a):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}]", *a, flush=True)


def pct_rank(v):
    v = np.asarray(v, np.float64)
    good = np.isfinite(v)
    out = np.full(v.shape, np.nan)
    if good.any():
        out[good] = (rankdata(v[good], method="average") - 0.5) / float(good.sum())
    return out.astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=BUDGET)
    args = ap.parse_args()
    budget = int(args.budget)

    reg = H97.check_prereg()
    _r, store, cat, eligible, folds, _va, _vb, ring_px = base.setup()
    if H97.ROUND != "H97" or ring_px != COLLAR_PX:
        raise SystemExit(f"unexpected round/collar: {H97.ROUND}/{ring_px}")
    H97.heal_channels()          # IR-H97-001: refuse to fit on a channel whose bytes moved
    bank = H97.Bank(inverse=store.inverse)
    flat = store.flat_idx

    with rasterio.open(ROOT / "data/sample_submission.tif") as ds:
        domain = np.isfinite(ds.read(1))
    valid = store.valid & domain
    log(f"eligible {int(valid.sum()):,} (features {int(store.valid.sum()):,}, domain {int(domain.sum()):,})")
    log(f"catalogue {int(cat.sum()):,} px")

    # ---------------- production fit: whole visible catalogue, same procedure as the holdout ----
    catd = ndi.distance_transform_edt(~cat)
    rng = np.random.default_rng(H97.SEED)
    # the training domain is the FEATURE-ELIGIBLE footprint (store.valid), exactly as the holdout's
    # folds were; the emission domain is the stricter `valid` = features AND organiser domain
    # (IR-52-002).  A catalogue pixel outside the feature footprint cannot be sampled.
    pos = np.flatnonzero((cat & store.valid).ravel())
    neg = np.flatnonzero((store.valid & ~cat & (catd > 5)).ravel())
    max_pos = max(1, min(20000, len(pos)))
    pos = rng.choice(pos, max_pos, replace=False)
    neg = rng.choice(neg, min(60000, len(neg)), replace=False)
    rows = np.concatenate([pos, neg])
    y = np.concatenate([np.ones(len(pos), np.int8), np.zeros(len(neg), np.int8)])
    order = rng.permutation(len(rows))
    rows, y = rows[order], y[order]
    log(f"production fit sample: {len(rows):,} rows ({int(y.sum()):,} positive)")
    preds = {}
    for view, names in (("Atex", H97.DVA_A), ("Btex", H97.DVA_B)):
        t0 = time.time()
        m = base.learner(H97.SEED)
        X = bank.gather(rows, names)
        m.fit(X, y)
        del X
        p = np.empty(len(flat), np.float32)
        for i in range(0, len(flat), 250_000):
            sel = flat[i:i + 250_000]
            p[i:i + 250_000] = m.predict_proba(bank.gather(sel, names))[:, 1].astype(np.float32)
        preds[view] = p
        log(f"view {view}: production fit + full-domain predict in {time.time()-t0:.0f}s "
            f"({len(names)} channels)")

    # ---------------- the preregistered primary field ------------------------------------------
    allowed = valid & (catd > COLLAR_PX)
    ai = np.flatnonzero(allowed.ravel())          # GRID-flat indices
    eidx = store.inverse[ai]                      # eligible-flat indices (the learner's space)
    if (eidx < 0).any():
        raise SystemExit("allowed set is not inside the feature-eligible footprint")
    ra = np.full(eligible.size, np.nan, np.float32)
    rb = np.full(eligible.size, np.nan, np.float32)
    ra[ai] = pct_rank(preds["Atex"][eidx])
    rb[ai] = pct_rank(preds["Btex"][eidx])
    field = np.full(eligible.shape, -np.inf, np.float32)
    field.ravel()[ai] = (ra[ai] - rb[ai]).astype(np.float32)
    log(f"allowed {ai.size:,} px; field range "
        f"[{field.ravel()[ai].min():.4f}, {field.ravel()[ai].max():.4f}]")

    em = nodes.spacing_select(field, allowed, budget, min_px=3.0, log=log)
    n_em = int(em.sum())
    log(f"placed {n_em:,} of requested {budget:,}")
    if n_em != budget:
        raise SystemExit(f"placement short-filled ({n_em} != {budget}); refusing to ship")

    out_grid = np.where(em, np.float32(1.0), np.float32(0.0)).astype(np.float32)
    out_grid = np.where(valid, out_grid, np.float32(0.0)).astype(np.float32)
    if np.any((out_grid > 0) & ~valid):
        raise SystemExit("positive mass outside the eligible footprint")

    SUB.mkdir(exist_ok=True)
    tif = SUB / f"{NAME}.tif"
    report = grid.write_geotiff_portal_exact(tif, out_grid, valid,
                                             ROOT / "data/sample_submission.tif", outside="zero")
    sha = hashlib.sha256(tif.read_bytes()).hexdigest()
    log(f"wrote {tif.name} ({tif.stat().st_size:,} bytes) sha256 {sha[:16]}…")
    log("container checks: " + json.dumps({k: report.get(k) for k in
        ("count", "dtype", "crs", "shape", "nodata", "compress", "all_finite", "in_range")},
        default=str))

    # ---------------- format validator (independent re-read from disk) --------------------------
    fmt = gates.format_report(tif, ROOT / "data/sample_submission.tif", footprint=valid)
    log("gates.format_report: " + json.dumps({k: v for k, v in fmt.items() if not isinstance(v, (list, dict))}, default=str))

    # ---------------- uniqueness + lane gates (decoded pixels; own copies excluded) -------------
    priors = gates.find_priors([SUB, DOCS, ROOT / "data/scored"], exclude=tif)
    priors = [p for p in priors if p.name != tif.name]
    log(f"priors checked: {len(priors)}")
    uniq = gates.uniqueness_report(out_grid, priors)
    lane = gates.lane_uniqueness_report(out_grid, valid, priors,
                                        sample=ROOT / "data/sample_submission.tif", phase="dots")

    # ---------------- not-the-union diagnostic --------------------------------------------------
    # the consensus twin uses the same two views, so it isolates "disagreement" from "either view"
    cons_field = np.full(eligible.shape, -np.inf, np.float32)
    cons_field.ravel()[ai] = np.minimum(ra[ai], rb[ai])
    cons = nodes.spacing_select(cons_field, allowed, budget, min_px=3.0)
    union_field = np.full(eligible.shape, -np.inf, np.float32)
    union_field.ravel()[ai] = np.maximum(ra[ai], rb[ai])
    un = nodes.spacing_select(union_field, allowed, budget, min_px=3.0)
    not_union = dict(
        disagreement_dots=n_em,
        dots_also_in_consensus=int((em & cons).sum()),
        dots_also_in_union=int((em & un).sum()),
        jaccard_vs_consensus=float((em & cons).sum() / max((em | un).sum(), 1)),
        spearman_field_vs_unionmax=float(np.corrcoef(
            rankdata(field.ravel()[ai]), rankdata(union_field.ravel()[ai]))[0, 1]),
        note="a high-A/low-B pixel and a high-A/high-B pixel have the same max(A,B)=union score "
             "but different disagreement scores, so the shipped field is not a rescaling of the union")
    log("not-the-union: " + json.dumps(not_union))

    # ---------------- A-only geological reasoning (brief requirement) ---------------------------
    cy, cx = np.nonzero(em)
    a_q = ra.reshape(eligible.shape)[cy, cx]
    b_q = rb.reshape(eligible.shape)[cy, cx]
    dist_cat_m = (catd[cy, cx] * 100.0).astype(np.float32)
    a_only = a_q >= 0.75
    csv_path = DOCS / f"{NAME}-a-only-reasoning.csv"
    csv_path.parent.mkdir(exist_ok=True)
    with csv_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "easting", "northing", "dist_mapped_fault_m",
                    "view_A_pct", "view_B_pct", "disagreement", "class", "geological_reasoning"])
        for i in np.argsort(-(a_q - b_q))[:4000]:
            yy, xx = int(cy[i]), int(cx[i])
            cls = ("A-only (geophysical-confident, surface-abstains)" if a_q[i] >= 0.75
                   else "mixed")
            reason = ("potential-field boundary texture exceeds the surface texture at this cell; "
                      "candidate concealed fault beneath alluvial/volcanic cover where the DEM and "
                      "radiometric surfaces carry no scarp" if cls.startswith("A-only")
                      else "both views partly engaged; not an A-only candidate")
            w.writerow([yy, xx, f"{243350.0 + xx*100.0:.0f}", f"{4508550.0 - yy*100.0:.0f}",
                        f"{dist_cat_m[i]:.1f}", f"{a_q[i]:.4f}", f"{b_q[i]:.4f}",
                        f"{a_q[i]-b_q[i]:.4f}", cls, reason])
    log(f"wrote {csv_path.name} ({csv_path.stat().st_size:,} bytes; "
        f"{int(a_only.sum())} A-only dots on the shipped support)")

    zip_path = DOCS / f"{NAME}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(tif, tif.name)

    # The holdout block is READ from the receipt, never hand-copied: a hard-coded 60,894 (the
    # all-bands-finite mask count) and a paired CI placed in the `ci95` slot both shipped in the
    # first build of this card and were caught in review (correction: 2026-10-10, IR-H97-006).
    _h = json.loads((ROOT / "evidence" / "h97_holdout.json").read_text())
    _sc = _h["pooled"]["scores"][_h["primary"]]
    _pair = _h["pooled"]["paired_differences"]["random"]
    card = dict(
        round="H97", stage="build", artifact=tif.name, sha256=sha,
        evidence_class="HOLDOUT-DTI (see evidence/h97_holdout.json) — this build receipt is not a score",
        hypothesis="View A (potential-field/subsurface) made sufficient by replacing amplitude with "
                   "boundary texture — directional variogram anisotropy on bands 2 rtp, 9 tmi_vg, 13 "
                   "iso_grav_anom — so the brief's A-confident/B-abstains disagreement arm can rank "
                   "buried faults under cover",
        mechanism="semivariance anisotropy isolates boundary geometry rather than source amplitude, "
                  "so a buried offset should survive cover",
        named_non_fault_mimic="lithologic contacts, intrusive margins, paleo-channels and gridding "
                              "seams all satisfy a directional-variogram anisotropy maximum",
        primary_arm="xtex_dis", budget=budget, placed=n_em,
        holdout=dict(dti=_sc["dti"], ci95=list(_sc["ci95"]),
                     paired_vs_random=_pair["delta"], paired_ci95=list(_pair["ci95"]),
                     evaluator=_h["evaluator_version"],
                     withheld_positive_px=_sc["withheld_positive_pixels"],
                     note="paired CI entirely below zero"),
        views=dict(view_A_bands=H97.VIEW_A_BANDS, view_B_bands=H97.VIEW_B_BANDS,
                   lags_px=list(H97.LAGS), n_channels=len(H97.ALL_DVA)),
        container=dict(outside="zero", nodata=None, all_finite=True,
                       written_by="gems52.grid.write_geotiff_portal_exact"),
        format_checks=fmt, uniqueness=uniq, lane=lane, not_the_union=not_union,
        verdict="DOWNLOAD YES, SUBMIT NO",
        verdict_reason="the preregistered primary scores 0.034799 HOLDOUT-DTI, strictly below the "
                       "0.080426 random control with a 95% CI that excludes zero; the repository "
                       "forbids spending a slot on a candidate that has not beaten the control",
        submission_name="h97-cotrain-atexture-disagreement-37654px",
        submission_note="H97 A-texture vs B-texture disagreement, 37654px, 3px spacing, 200m collar",
        generated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    (SUB / f"{NAME}.json").write_text(json.dumps(card, indent=1, default=str) + "\n")
    (EVID / "h97_build.json").write_text(json.dumps(card, indent=1, default=str) + "\n")
    (SUB / "H97_LATEST.txt").write_text(tif.name + "\n")
    log("VERDICT: " + card["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
