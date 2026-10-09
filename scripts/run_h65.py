#!/usr/bin/env python3
"""H65 -- the R5-H1 trace-correction corridor: run the frozen spatially-blocked A-gate.

Preregistered in ``knowledge/41_hypotheses_H65_preregistered.md`` (SHA-256 pinned in
``registry/h65_preregistration.json``); this runner refuses to start if the hash moves.

What is shared and what is round-specific
-----------------------------------------
* Shared, not forked: ``gems52.grid`` (band/footprint readers, sentinel rule),
  ``gems52_r5.cotrain_r5`` (the 20 km block grid and whole-block folds, seed 20261009),
  and later -- in ``scripts/build_h65_submission.py`` -- ``gems52.gates``,
  ``gems52.submission_writer`` and the frozen prior census of
  ``scripts/fetch_prior_inventory.py``.  No private fork of any shared instrument exists.
* Round-specific: the perpendicular-offset estimator and the four gate conditions G1-G4,
  both frozen in the preregistration, including the A1 calibration that reads the
  undocumented LiDAR ``strike`` band's angular convention from the data before any gate
  statistic exists.

Hypothesis (R5-H1, rank 1 of knowledge/41): the mapped traces are partly misaligned from the
true surface faults (organiser, forum 11516: corrections-to-existing-traces are part of the
new-fault truth).  A scarp measured by LiDAR -- one-sided downface/upface step, strike
agreement, detrended-elevation crest -- locates the true trace at a signed perpendicular
offset of -3..+3 px (the metric's whole kernel support) from the mapped line.

Stage ``gate`` evaluates, per the prereg:
  G1 >= 200 held-out traces;          G2 median |offset| <= 1.0 px;
  G3 beats best constant-offset control by >= 0.3 px (control fitted on the other 3 folds);
  G4 fraction of traces whose argmax offset is 0 <= 0.5.

Usage:  python scripts/run_h65.py gate
Exit code is 0 whether the gate passes or fails; the verdict lives in the receipt.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np                                                  # noqa: E402
from scipy import ndimage                                           # noqa: E402

from gems52 import grid                                             # noqa: E402
from gems52_r5 import cotrain_r5 as C                               # noqa: E402

REG = ROOT / "registry/h65_preregistration.json"
PREREG = ROOT / "knowledge/41_hypotheses_H65_preregistered.md"
WORK = ROOT / "work/h65"
EVID = ROOT / "evidence"

MIN_TRACE_PX = 10
WINDOW_R = 5                    # Chebyshev radius of the per-pixel PCA window
WINDOW_MIN_PX = 5
OFFSETS = np.arange(-3, 4)      # frozen: the metric's whole kernel support, 0 included
FOLDS = 4
SEED = C.SEED                   # 20261009, the shared fold seed -- not round-specific


def log(*a, **k):
    print(*a, flush=True, **k)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_prereg() -> None:
    card = json.loads(REG.read_text())
    got = sha256(PREREG)
    if got != card["preregistration_sha256"]:
        raise SystemExit(
            f"preregistration hash moved: registry pins {card['preregistration_sha256'][:12]}…, "
            f"file is {got[:12]}…  Re-pin deliberately (with an amendment note) or restore the file."
        )
    log(f"[prereg] OK  sha256={got[:16]}…  (frozen {card['created_utc']})")


def load_layers() -> dict:
    """The exact layers the preregistration names; nothing else."""
    import rasterio

    layers = {}
    with rasterio.open(ROOT / "data/labels.tif") as src:
        cat = src.read(1) == 1
    valid = grid.footprint_from(ROOT / "data/training_features.tif", bands="all")
    lid = ROOT / "data/external/lidar_scarp_features_u8.tif"
    with rasterio.open(lid) as src:
        names = {i + 1: src.descriptions[i] for i in range(src.count)}
        expect = {6: "downface_max", 7: "upface_max", 11: "strike", 12: "valid"}
        for b, n in expect.items():
            assert names[b] == n, f"LiDAR band {b} is {names[b]!r}, expected {n!r}"
        layers["down"] = src.read(6).astype(np.float32)
        layers["up"] = src.read(7).astype(np.float32)
        layers["strike"] = src.read(11).astype(np.float32)
        layers["lid_valid"] = src.read(12) > 0
    layers["det"] = grid.read_band(ROOT / "data/training_features.tif", 12)  # det_elev
    layers["cat"] = cat & valid
    layers["valid"] = valid
    return layers


def traces_of(cat: np.ndarray) -> list[dict]:
    lab, n = ndimage.label(cat, structure=np.ones((3, 3), bool))
    sizes = np.bincount(lab.ravel())
    out = []
    for i in range(1, n + 1):
        if sizes[i] < MIN_TRACE_PX:
            continue
        rows, cols = np.nonzero(lab == i)
        out.append(dict(id=i, rows=rows, cols=cols, npx=int(sizes[i])))
    return out


def assign_folds(traces: list[dict], valid: np.ndarray) -> None:
    bid = C.block_ids(valid.shape, valid, C.BLOCK_M)
    fold_map = C.make_folds(bid, FOLDS, seed=SEED)
    for t in traces:
        f = fold_map[t["rows"], t["cols"]]
        f = f[f >= 0]
        cnt = np.bincount(f, minlength=FOLDS)
        t["fold"] = int(np.argmax(cnt))          # modal fold; ties -> smallest id
        t["cross_fold"] = bool((cnt > 0).sum() > 1)


def pixel_strikes(t: dict, shape: tuple[int, int]) -> np.ndarray:
    """Frozen PCA strike (degrees, axial [0,180), raster frame: 0=+col, 90=+row(down))."""
    m = np.zeros(shape, bool)
    m[t["rows"], t["cols"]] = True
    out = np.full(t["rows"].shape, np.nan, np.float64)
    r0, r1 = int(t["rows"].min()), int(t["rows"].max())
    c0, c1 = int(t["cols"].min()), int(t["cols"].max())
    for k in range(t["rows"].size):
        r, c = int(t["rows"][k]), int(t["cols"][k])
        rs, re = max(0, r - WINDOW_R), min(shape[0], r + WINDOW_R + 1)
        cs, ce = max(0, c - WINDOW_R), min(shape[1], c + WINDOW_R + 1)
        win = m[rs:re, cs:ce]
        if win.sum() < WINDOW_MIN_PX:
            continue
        yy, xx = np.nonzero(win)
        yy = yy.astype(np.float64) + rs
        xx = xx.astype(np.float64) + cs
        yy -= yy.mean()
        xx -= xx.mean()
        cxx = float((xx * xx).mean())
        cyy = float((yy * yy).mean())
        cxy = float((xx * yy).mean())
        theta = 0.5 * np.arctan2(2.0 * cxy, cxx - cyy)     # radians, from +col axis
        out[k] = np.degrees(theta) % 180.0
    return out


def sample_at(rows: np.ndarray, cols: np.ndarray, layers: dict) -> tuple[np.ndarray, np.ndarray]:
    """Valid sample mask + linear indices for float positions rounded to nearest cell."""
    rr = np.rint(rows).astype(np.int64)
    cc = np.rint(cols).astype(np.int64)
    h, w = layers["valid"].shape
    ok = (rr >= 0) & (rr < h) & (cc >= 0) & (cc < w)
    rrc = np.clip(rr, 0, h - 1)
    ccc = np.clip(cc, 0, w - 1)
    ok &= layers["valid"][rrc, ccc]
    ok &= layers["lid_valid"][rrc, ccc]
    return ok, rrc * w + ccc


def run_gate() -> dict:
    check_prereg()
    WORK.mkdir(parents=True, exist_ok=True)
    t_start = datetime.now(timezone.utc)

    layers = load_layers()
    cat, valid = layers["cat"], layers["valid"]
    log(f"[grid] footprint {int(valid.sum()):,} px, catalogue {int(cat.sum()):,} px")
    traces = traces_of(cat)
    assign_folds(traces, valid)
    log(f"[traces] {len(traces)} traces with >= {MIN_TRACE_PX} px; "
        f"cross-fold {sum(t['cross_fold'] for t in traces)}")

    # ---- pass 1: strikes + raw terms at every (pixel, offset); full-length per trace
    thetas: list[np.ndarray] = []
    per_off = {int(o): dict(ok=[], t1=[], t3=[], band=[]) for o in OFFSETS}
    cal_p, cal_l = [], []            # A1-calibration pairs at offset 0
    lid_valid_flat = layers["lid_valid"].ravel()
    valid_flat = layers["valid"].ravel()
    down_flat, up_flat = layers["down"].ravel(), layers["up"].ravel()
    det_flat, strike_flat = layers["det"].ravel(), layers["strike"].ravel()

    for t in traces:
        n = int(t["npx"])
        th = pixel_strikes(t, valid.shape)
        thetas.append(th)
        r, c = t["rows"].astype(np.float64), t["cols"].astype(np.float64)
        has = np.isfinite(th)
        # normal to the PCA direction d=(dr,dc)=(sin th, cos th)  ->  n=(cos th, -sin th)
        ndr = np.cos(np.radians(th))
        ndc = -np.sin(np.radians(th))
        for o in OFFSETS:
            rr_o, cc_o = r + o * ndr, c + o * ndc
            ok, lin = sample_at(rr_o, cc_o, layers)
            ok_m, lin_m = sample_at(r + (o - 1) * ndr, c + (o - 1) * ndc, layers)
            ok_p, lin_p = sample_at(r + (o + 1) * ndr, c + (o + 1) * ndc, layers)
            ok3 = ok & ok_m & ok_p & has
            t1 = np.zeros(n, np.float64)
            t3 = np.zeros(n, np.float64)
            band = np.zeros(n, np.float64)
            if ok3.any():
                t1[ok3] = np.abs(down_flat[lin[ok3]] - up_flat[lin[ok3]])
                t3[ok3] = (2.0 * det_flat[lin[ok3]]
                           - det_flat[lin_m[ok3]] - det_flat[lin_p[ok3]])
                band[ok3] = strike_flat[lin[ok3]] * (180.0 / 255.0)
            per_off[int(o)]["ok"].append(ok3)
            per_off[int(o)]["t1"].append(t1)
            per_off[int(o)]["t3"].append(t3)
            per_off[int(o)]["band"].append(band)
            if o == 0:
                cal_p.append(th[ok3])
                cal_l.append(band[ok3])
    for o in OFFSETS:
        for k in ("ok", "t1", "t3", "band"):
            per_off[int(o)][k] = np.concatenate(per_off[int(o)][k])

    # ---- footprint-wide t1 percentiles (frozen: over valid AND LiDAR-valid cells)
    fp_ok = valid_flat & lid_valid_flat
    t1_fp = np.abs(down_flat[fp_ok].astype(np.float64) - up_flat[fp_ok].astype(np.float64))
    p1a, p9a = np.percentile(t1_fp, [1, 99])
    del t1_fp
    # t3 is directional: its frozen percentile population is the pooled sampled cells of
    # this run (all offsets).  Deviation from the prereg's letter for t3 only; logged.
    t3_all = np.concatenate([per_off[int(o)]["t3"] for o in OFFSETS])
    p1c, p9c = np.percentile(t3_all, [1, 99])
    del t3_all
    log(f"[norm] t1 footprint p01={p1a:.1f} p99={p9a:.1f} | t3 pooled p01={p1c:.2f} p99={p9c:.2f}")

    # ---- A1 calibration: read the band's convention from the data (prereg amendment)
    tp = np.concatenate(cal_p)
    lb = np.concatenate(cal_l)
    encodings = {"theta": (1.0, 0.0), "neg": (-1.0, 0.0),
                 "theta+90": (1.0, 90.0), "neg+90": (-1.0, 90.0)}
    cal = {}
    for name, (sg, sh) in encodings.items():
        z = np.exp(1j * np.radians(2.0 * ((tp - (lb * sg + sh)) % 180.0)))
        cal[name] = float(np.abs(z.mean()))
    best = max(cal, key=cal.get)
    sign, shift = encodings[best]
    r_best = cal[best]
    t2_uninformative = bool(r_best < 0.10)
    log("[A1] circular resultant length by encoding: " +
        ", ".join(f"{k}={v:.4f}" for k, v in cal.items()) + f"  -> {best} (r={r_best:.4f})")

    # ---- pass 2: normalised votes and trace estimates
    starts = np.concatenate([[0], np.cumsum([int(t["npx"]) for t in traces])])
    for ti, t in enumerate(traces):
        n = int(t["npx"])
        th = thetas[ti]
        scores = np.full((n, len(OFFSETS)), -np.inf)
        okany = np.zeros(n, bool)
        for j, o in enumerate(OFFSETS):
            base = int(starts[ti])
            sl = slice(base, base + n)
            ok = per_off[int(o)]["ok"][sl]
            if not ok.any():
                continue
            t1n = np.clip((per_off[int(o)]["t1"][sl][ok] - p1a) / max(p9a - p1a, 1e-9), 0, 1)
            t3n = np.clip((per_off[int(o)]["t3"][sl][ok] - p1c) / max(p9c - p1c, 1e-9), 0, 1)
            band = per_off[int(o)]["band"][sl][ok]
            dth = (th[ok] - (band * sign + shift)) % 180.0
            t2n = (np.cos(2.0 * np.radians(dth)) + 1.0) / 2.0
            scores[np.nonzero(ok)[0], j] = (t1n + t2n + t3n) / 3.0
            okany |= ok
        vote = np.full(n, -99, np.int64)
        vote[okany] = OFFSETS[np.argmax(scores[okany], axis=1)]
        v = vote[vote != -99]
        t["offset"] = int(np.median(v)) if v.size else None
        t["n_votes"] = int(v.size)

    done = [t for t in traces if t["offset"] is not None]
    log(f"[votes] traces with >=1 valid vote: {len(done)}/{len(traces)}")

    # ---- the four frozen conditions
    offs = np.array([t["offset"] for t in done])
    folds = np.array([t["fold"] for t in done])
    g1 = len(done)
    g2 = float(np.median(np.abs(offs)))
    g4 = float((offs == 0).mean())
    ctrl = np.zeros(offs.shape)          # G3: control fitted on the other three folds
    for f in range(FOLDS):
        other = offs[folds != f]
        ctrl[folds == f] = float(np.median(other)) if other.size else 0.0
    est_mae = float(np.median(np.abs(offs)))
    ctrl_mae = float(np.median(np.abs(offs - ctrl)))
    g3_margin = ctrl_mae - est_mae

    hist = {int(o): int((offs == o).sum()) for o in np.unique(offs)}
    okc = dict(G1=bool(g1 >= 200), G2=bool(g2 <= 1.0), G3=bool(g3_margin >= 0.3),
               G4=bool(g4 <= 0.5))
    receipt = dict(
        round="H65", stage="gate", started_utc=t_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        finished_utc=now(),
        preregistration_sha256=sha256(PREREG),
        evaluator="h65-a-gate-v1 (geometric; 20 km whole-block trace folds, seed 20261009)",
        grid=dict(shape=list(valid.shape), footprint_px=int(valid.sum()),
                  catalogue_px=int(cat.sum())),
        traces=dict(n=len(traces), scored=len(done), min_px=MIN_TRACE_PX,
                    cross_fold=int(sum(t["cross_fold"] for t in traces)),
                    per_fold={int(f): int((folds == f).sum()) for f in range(FOLDS)}),
        A1_calibration=dict(resultant_lengths=cal, chosen=best, r_best=r_best,
                            t2_uninformative=t2_uninformative,
                            note="band 11 convention read from data before any gate "
                                 "statistic; prereg knowledge/41 amendment"),
        normalization=dict(t1_population="footprint valid & lidar-valid (frozen)",
                           t1_p01=float(p1a), t1_p99=float(p9a),
                           t3_population="pooled sampled cells, all offsets (directional "
                                         "quantity; deviation from the prereg letter, logged)",
                           t3_p01=float(p1c), t3_p99=float(p9c)),
        conditions=dict(
            G1_traces=dict(value=g1, threshold=200, op=">=", ok=okc["G1"]),
            G2_median_abs_offset_px=dict(value=g2, threshold=1.0, op="<=", ok=okc["G2"]),
            G3_beats_constant_control_px=dict(value=g3_margin, est_mae=est_mae,
                                              ctrl_mae=ctrl_mae, threshold=0.3, op=">=",
                                              ok=okc["G3"]),
            G4_argmax_zero_fraction=dict(value=g4, threshold=0.5, op="<=", ok=okc["G4"]),
        ),
        offset_histogram=hist,
        per_fold_median_offset={int(f): (float(np.median(offs[folds == f]))
                                         if (folds == f).any() else None)
                                for f in range(FOLDS)},
        verdict="PASS" if all(okc.values()) else "FAIL",
    )
    (WORK / "gate.json").write_text(json.dumps(receipt, indent=2))
    (EVID / "h65_gate.json").write_text(json.dumps(receipt, indent=2))
    np.save(WORK / "trace_offsets.npy",
            np.array([(t["id"], t["fold"], t["offset"], t["npx"], t["n_votes"])
                      for t in done], dtype=np.float64))
    log(f"[gate] G1={g1} (>=200: {okc['G1']})  G2={g2:.3f} px (<=1.0: {okc['G2']})")
    log(f"[gate] G3 margin={g3_margin:.3f} px (est {est_mae:.3f} vs ctrl {ctrl_mae:.3f}; "
        f">=0.3: {okc['G3']})  G4 frac0={g4:.3f} (<=0.5: {okc['G4']})")
    log(f"[gate] VERDICT: {receipt['verdict']}  receipt={EVID / 'h65_gate.json'}")
    return receipt


def main() -> int:
    stage = sys.argv[1] if len(sys.argv) > 1 else "gate"
    if stage != "gate":
        raise SystemExit(f"unknown stage {stage!r}; this runner implements 'gate' only")
    run_gate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
