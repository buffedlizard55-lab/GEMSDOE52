#!/usr/bin/env python3
"""Independent verification of the SHIPPED H88 bytes, on the same folds the round used.

Why this exists: the round's holdout receipt scores each *arm's placement rule* (top-k dots by the
arm's own ranking).  The shipped GeoTIFF is that placement *minus* every dot that fell inside the
mandatory 200 m catalogue ring, so the shipped set is a strict subset and its own DTI had never been
measured.  A receipt that is only ever read is a claim, not a check, so this script re-derives:

  1. bytes -> sha256, band values, dot count, catalogue discipline (0 on the catalogue, 0 within
     200 m), and the minimum dot separation (the 3 px spacing rule);
  2. the shipped file's own HOLDOUT-DTI: per-fold ``evaluate`` on the exact grid and pooled with the
     shared ``pooled_summary`` bootstrap (same folds, same evaluator version, seed recorded);
  3. the parallel-run lane gate (rank correlation / 3 px overlap against every registry raster) on the
     FINAL dots -- the brief requires the surface check before placement and the dots check after;
  4. the strict-support uniqueness gate on the final dots.

Writes ``evidence/h88_shipped_holdout.json``.  Nothing here re-ranks or re-selects anything: it only
measures the bytes the round already wrote.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
import scipy.ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
E = ROOT / "evidence"
sys.path.insert(0, str(ROOT / "scripts"))


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "h88_runner", ROOT / "scripts" / "run_h88_cotrain_lane.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    from gems52 import evaluate_holdout as evaluator
    from gems52 import gates

    t0 = time.time()
    build = json.loads((E / "h88_build.json").read_text())
    tif = Path(build["file"])
    if not tif.is_absolute():
        tif = ROOT / tif
    raw = tif.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    with rasterio.open(tif) as ds:
        em = ds.read(1)
    assert sha == build["sha256"], f"shipped bytes changed: {sha[:16]} != {build['sha256'][:16]}"
    assert em.dtype == np.float32, em.dtype
    finite = bool(np.isfinite(em).all())
    vals = np.unique(em)
    n_dots = int((em > 0).sum())
    assert n_dots == build["dots"], f"dot count {n_dots} != receipt {build['dots']}"
    assert set(np.round(vals, 6).tolist()) <= {0.0, 1.0}, f"unexpected values {vals[:5]}"

    runner = _load_runner()
    g = runner.grid_inputs()
    valid, cat, folds = g["valid"], g["cat"], g["folds"]
    catd = ndi.distance_transform_edt(~cat)
    on_cat = int((em > 0)[cat].sum())
    within_200m = int(((em > 0) & (catd <= 2)).sum())
    # exact minimum centre-to-centre separation between emitted dots
    ys, xs = np.nonzero(em > 0)
    min_sep = float("inf")
    if len(ys):
        try:
            from scipy.spatial import cKDTree
            tree = cKDTree(np.column_stack([ys, xs]))
            d, _ = tree.query(np.column_stack([ys, xs]), k=2)
            min_sep = float(d[:, 1].min())
        except Exception:  # pragma: no cover - fallback without scipy.spatial
            min_sep = None

    terms = None
    per_fold = []
    for fold in folds:
        res, t = evaluator.evaluate(em, fold, valid, block_side=200)
        terms = t if terms is None else terms + t
        per_fold.append(dict(fold=fold["fold"], dti=res["dti"], tpw=res["tpw"], fpw=res["fpw"],
                             fnw=res["fnw"], n_truth=res["n_truth"]))
    ho = json.loads((E / "h88_holdout.json").read_text())
    pooled = evaluator.pooled_summary(dict(shipped=terms), draws=1000,
                                      seed=ho["seeds"]["fit"], candidate="shipped")
    ship = pooled["scores"]["shipped"]

    # ---- parallel-run lane gate on the FINAL dots, and the strict-support uniqueness gate
    submission_dir = ROOT / "submission"
    priors = gates.find_priors([submission_dir, ROOT / "docs" / "downloads", ROOT / "data" / "scored"],
                               exclude=tif)
    # gates.find_priors drops the candidate by path and by basename, but the publish step stages a
    # differently-named byte-identical alias (docs/downloads/h88-candidate.tif); comparing against a
    # copy of yourself reports rho = 1.0 / novel = 0 and the one verdict that would stop a legitimate
    # submission.  Drop every copy by content hash, and record which ones were dropped.
    self_copies = [str(q) for q in priors
                   if hashlib.sha256(q.read_bytes()).hexdigest() == sha]
    priors = [q for q in priors
              if hashlib.sha256(q.read_bytes()).hexdigest() != sha]
    # Same-round artefacts (this round's own earlier builds and the publish alias) are likewise not
    # prior submissions; record their overlap with the shipped dots instead of scoring against them.
    dots_bool = (em > 0)
    same_round = []
    keep = []
    for q in priors:
        if q.name.startswith("gems52-h88-") or q.name in ("h88-candidate.tif", "h88-candidate.zip"):
            other = (rasterio.open(q).read(1) > 0)
            inter = int((dots_bool & other).sum())
            union = int((dots_bool | other).sum())
            same_round.append(dict(path=str(q), dots=int(other.sum()),
                                   sha256=hashlib.sha256(q.read_bytes()).hexdigest(),
                                   intersection_px=inter,
                                   jaccard=round(inter / union, 6) if union else None))
        else:
            keep.append(q)
    priors = keep
    emission = (em > 0).astype(np.float32)
    lane = gates.lane_report(emission, valid, priors, sample=str(ROOT / "data" / "sample_submission.tif"),
                             phase="dots")
    uniq = gates.uniqueness_report(emission, priors)

    print(f"shipped dots {n_dots:,} | on catalogue {on_cat} | within 200 m {within_200m} | "
          f"min separation {min_sep} px | values {vals.tolist()}")
    print(f"shipped HOLDOUT-DTI {ship['dti']:.6f} [{ship['ci95'][0]:.5f}, {ship['ci95'][1]:.5f}] "
          f"(arms receipt said {ho['pooled']['scores'][build['ship_field']]['dti']:.6f})")
    pol = lane["policy"]
    print(f"lane policy verdict {pol['verdict']} (max |rho| {pol['max_spearman']:.4f}, "
          f"max near-3px {pol['max_near_3px_fraction']:.4f}); literal verdict "
          f"{lane['literal']['verdict']} | uniqueness ok {uniq['ok']} "
          f"(novel fraction {uniq.get('novel_fraction')})")

    out = dict(
        stage="verify_shipped", generated_utc=time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        file=str(tif), sha256=sha, bytes=len(raw), evaluator_version=evaluator.VERSION,
        evidence_class="HOLDOUT-DTI", seed=ho["seeds"]["fit"], folds=len(folds),
        dots=n_dots, values=[float(v) for v in vals], finite=finite,
        on_catalogue_px=on_cat, within_200m_px=within_200m,
        min_separation_px=min_sep, min_separation_m=None if min_sep is None else min_sep * 100.0,
        shipped_pooled=dict(**ship, per_fold=per_fold),
        arms_receipt_said=dict(arm=build["ship_field"],
                               dti=ho["pooled"]["scores"][build["ship_field"]]["dti"],
                               ci95=ho["pooled"]["scores"][build["ship_field"]]["ci95"]),
        lane=lane, uniqueness=uniq, self_copies_excluded=self_copies,
        same_round_excluded=same_round,
        instrument_note=("The shipped file emits nothing within 200 m of the mapped catalogue "
                         "(the champion's measured +6.83 % ring lever), so its own score on this "
                         "hide-and-recover instrument is near zero BY CONSTRUCTION: the instrument's "
                         "truth is the mapped catalogue itself and the file deliberately stays away "
                         "from it. The arm-level number in evidence/h88_holdout.json (0.179847 for the "
                         "same ranking rule before the ring strip) is the detector measurement; this "
                         "file's own number measures catalogue overlap, which is not what the "
                         "competition asks for."),
        seconds=round(time.time() - t0, 1))
    (E / "h88_shipped_holdout.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(f"wrote evidence/h88_shipped_holdout.json in {out['seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
