#!/usr/bin/env python3
"""H77cond build stages: registry census, lane-feasible placement, gates, GeoTIFF, reasoning, run card.

Imported by ``scripts/run_h77cond.py``; not meant to be run on its own (it needs that runner's
preregistration check).  Everything here uses the shared gates/placer/writer, never a private fork.
"""
from __future__ import annotations

import csv
import hashlib
import json
import time
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

import run_h77cond as H                      # the runner: constants, logging, receipts
from gems52 import gates, nodes, submission_writer

ROOT = H.ROOT
WORK = H.WORK
EVID = H.EVID
DOCS = H.DOCS
SUBM = H.SUBM
DOWN = H.DOWN
log = H.log

CANDIDATE_ARMS = ("swap_010", "swap_025", "swap_050", "line_support_B")
N_QUOTA_PRIORS = 262                      # every informative prior with 3 px coverage >= 0.10
CONSENSUS_GRID = (400, 300, 240, 200, 160, 120, 100, 80, 60, 50, 40, 30, 25, 20, 15, 10)
NEAR_TARGET = 0.6985                      # enforced margin strictly below the brief's literal 0.70


# =================================================================================================
# registry census: coverage, universal-probe classification, cross-family consensus
# =================================================================================================
ROUND_TOKENS = ("h77cond", "gems74")


def prior_paths() -> list[Path]:
    """Every aligned single-band prediction raster we can see, minus this round's own artefacts.

    ``gates.find_priors`` sweeps ``submission/`` and ``docs/downloads/``, which is exactly where this
    round writes its own candidate -- so without this filter the uniqueness gate would compare the
    file against itself, report ``identical``, and fail for the wrong reason.  Filtering on the
    round token is checked by an assertion in ``stage_card`` against the real written path.
    """
    found = gates.find_priors([WORK / "priors", ROOT / "submission", ROOT / "data/scored",
                               ROOT / "data/reference", ROOT / "docs/downloads"])
    return [p for p in found
            if H.PREFIX not in p.name and not any(tok in p.name.lower() for tok in ROUND_TOKENS)]


def stage_registry(reg, args):
    th = reg["thresholds"]
    t0 = time.time()
    with rasterio.open(ROOT / "data/labels.tif") as s:
        cat = s.read(1) == 1
    valid = np.load(ROOT / "work/r2/features/valid.npy")
    ed = ndi.distance_transform_edt(~cat, sampling=100.0)
    legal = valid & ~cat & (ed > th["catalogue_exclusion_m"] + 1e-6)
    del ed
    np.save(WORK / "valid.npy", valid)
    np.save(WORK / "legal.npy", legal)
    log(f"valid {int(valid.sum())} px | off-catalogue {int((valid & ~cat).sum())} px | "
        f"legal (>{th['catalogue_exclusion_m']:.0f} m from a mapped trace) {int(legal.sum())} px")

    paths = prior_paths()
    log(f"registry rasters found: {len(paths)}")
    disk = gates._disk(th["lane_near_dot_radius_px"])
    n_legal = float(max(int(legal.sum()), 1))
    consensus = np.zeros(valid.shape, np.uint16)
    rows, seen = [], {}
    halo_store: list[tuple[float, str, np.ndarray]] = []
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        grid_meta = (ref.shape, ref.crs, ref.transform)
    for i, p in enumerate(paths):
        try:
            with rasterio.open(p) as ds:
                if ds.count != 1 or (ds.shape, ds.crs, ds.transform) != grid_meta:
                    rows.append(dict(path=str(p), error="unaligned or multiband"))
                    continue
                old = gates.canonical(ds.read(1))
        except Exception as exc:                                  # noqa: BLE001
            rows.append(dict(path=str(p), error=f"{type(exc).__name__}: {exc}"))
            continue
        digest = hashlib.sha256(old.tobytes()).hexdigest()
        if digest in seen:
            rows.append(dict(path=str(p), decoded_sha256=digest, duplicate_of=seen[digest]))
            continue
        seen[digest] = str(p)
        v = old[legal]
        binary = bool(np.all((v == 0) | (v == 1)))
        proposal = (old > 0) if binary else (old >= 0.5)
        if not proposal.any():
            rows.append(dict(path=str(p), decoded_sha256=digest, prior_proposals=0, empty=True))
            continue
        halo = ndi.binary_dilation(proposal, structure=disk)
        cov = float((halo & legal).sum()) / n_legal
        probe = bool(cov >= th["universal_coverage_probe_threshold"])
        consensus += (halo & legal).astype(np.uint16)
        rows.append(dict(path=str(p), decoded_sha256=digest, binary=binary,
                         prior_proposals=int(proposal.sum()),
                         coverage_3px_of_legal=round(cov, 6), universal_coverage_probe=probe))
        if not probe:
            halo_store.append((cov, str(p), np.packbits(halo.ravel())))
        del old, proposal, halo
        if (i + 1) % 50 == 0:
            log(f"  registry {i+1}/{len(paths)} distinct={len(seen)} ({time.time()-t0:.0f}s)")
    halo_store.sort(key=lambda t: -t[0])
    keep = halo_store[:N_QUOTA_PRIORS]
    np.savez(WORK / "quota_halos.npz", paths=np.array([k[1] for k in keep], dtype=object),
             **{f"h{i}": k[2] for i, k in enumerate(keep)})
    np.save(WORK / "consensus.npy", consensus)
    measured = [r for r in rows if "error" not in r and "duplicate_of" not in r and not r.get("empty")]
    probes = [r for r in measured if r["universal_coverage_probe"]]
    out = dict(stage="registry", rasters_found=len(paths), distinct_decoded=len(seen),
               measured=len(measured), universal_coverage_probes=len(probes),
               informative=len(measured) - len(probes),
               probe_threshold=th["universal_coverage_probe_threshold"],
               quota_priors_packed=len(keep), legal_px=int(legal.sum()), valid_px=int(valid.sum()),
               consensus_max=int(consensus[legal].max()) if legal.any() else 0,
               consensus_median=float(np.median(consensus[legal])) if legal.any() else 0.0,
               errors=[r for r in rows if "error" in r][:20],
               scope=("Supplied, aligned, publicly mirrored inventory only; private/unlinked "
                      "artefacts are not proven absent."),
               seconds=round(time.time() - t0, 1), per_prior=rows)
    H.write_ev("registry", {k: v for k, v in out.items() if k != "per_prior"})
    (WORK / "registry_rows.json").write_text(json.dumps(rows, indent=1, default=H._json_default))
    log(f"REGISTRY distinct {len(seen)} | informative {out['informative']} | probes {len(probes)} | "
        f"consensus max {out['consensus_max']} median {out['consensus_median']}")
    return out


# =================================================================================================
# build: stitched OOF field -> lane-feasible placement -> gates -> GeoTIFF
# =================================================================================================
def _stitch_oof(store, folds, eligible):
    """Per-fold out-of-quadrant predictions, percentile-ranked inside each quadrant and stitched.

    Quadrant regions are disjoint and their union is the eligible footprint, so the stitched field
    is an out-of-fold field everywhere: no pixel is ranked by a model that saw its own quadrant.
    """
    flat = store.flat_idx
    rA = np.full(eligible.shape, np.nan, np.float32)
    rB = np.full(eligible.shape, np.nan, np.float32)
    for fold in folds:
        f = fold["fold"]
        idx = np.flatnonzero(fold["region"].ravel())
        for tag, dst in (("A", rA), ("B", rB)):
            g = H.base.to_grid(flat, np.load(WORK / f"pred_post_{tag}_f{f}.npy"), eligible.shape)
            dst.ravel()[idx] = H.base.pct_rank(g.ravel()[idx])
            del g
    return rA, rB


def _composite_field(arm, rA, rB, pool, budget, th):
    """The shipped field for the measured winning arm, restricted to ``pool``."""
    lo, hi = th["receiver_rank_interval"]
    donor = float(th["donor_rank_min"])
    if arm == "line_support_B":
        f = H.line_support(np.nan_to_num(rB, nan=0.0), pool,
                           n_orient=int(th["line_support_orientations"]),
                           chord_px=int(round(th["line_support_chord_m"] / 100.0)) + 1)
        f = np.where(pool, f, -1.0).astype(np.float32)
        return f, np.zeros(pool.shape, bool), np.zeros(pool.shape, bool)
    phi = int(arm.split("_")[1]) / 100.0
    field, core, rescue = H._swap_field(rB, rA, pool, budget, phi, donor, lo, hi,
                                        min_px=float(th["min_dot_separation_px"]))
    return field, core, rescue


def _exclusion_stamp(min_px: float) -> np.ndarray:
    """Neighbourhood a placed dot forbids.

    It must match ``gems52.nodes.spacing_select`` EXACTLY, otherwise the shipped raster would obey a
    different spacing rule from the arms measured on the holdout.  That placer rejects a candidate
    when squared distance is STRICTLY LESS than min_px**2, so a pair exactly min_px apart is legal;
    ``gates._disk`` uses <=, which is one ring stricter.  Hence the explicit stamp here.
    """
    r = int(np.ceil(min_px))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    return (yy * yy + xx * xx) < (min_px * min_px - 1e-12)


def _bit_transpose(packed, ncell, chunk=262_144):
    """Re-pack per-prior halo bitmaps into one per-PIXEL bitmap: PT[flat_index] -> ceil(n/8) bytes.

    The greedy loop asks "which priors cover this one pixel?" up to a million times.  Against a
    (n_priors, ncell) layout that is a strided gather with a 1.5 MB stride -- a cache miss per
    prior, per pixel.  Transposed, the same question is a contiguous read of ~19 bytes.
    """
    n = len(packed)
    if not n:
        return np.zeros((0, 0), np.uint8), 0
    nb = (n + 7) // 8
    pt = np.zeros((ncell, nb), np.uint8)
    for s in range(0, ncell, chunk):                      # chunk is a multiple of 8 by construction
        e = min(s + chunk, ncell)
        blk = np.empty((e - s, n), np.uint8)
        b0, b1 = s // 8, (e + 7) // 8
        for j, pk in enumerate(packed):
            blk[:, j] = np.unpackbits(pk[b0:b1])[:e - s]
        pt[s:e] = np.packbits(blk, axis=1)
        del blk
    return pt, n


def _place(field, pool, budget, min_px, pt, n_priors, quota, shape):
    """Greedy top-S with a hard-core spacing stamp and an exact per-prior near-dot quota.

    Identical in design to the H69 placer -- the only construction measured lane-feasible on this
    saturated registry.  When a prior reaches ``quota`` dots inside its 3 px halo, every remaining
    pixel of that halo is struck from the pool, so the brief's "more than 70% of dots within 3 px of
    one registry raster" condition cannot be reached by any later dot either.
    """
    h, w = shape
    ncell = h * w
    idx = np.flatnonzero(pool.ravel())
    order = idx[np.lexsort((idx, -np.nan_to_num(field.ravel()[idx], nan=-1.0)))]
    stamp = _exclusion_stamp(min_px)
    r = stamp.shape[0] // 2
    taken = np.zeros(shape, bool)
    forbidden = np.zeros(ncell, bool)
    counts = np.zeros(n_priors, np.int64)
    cy, cx, scanned, blocked = [], [], 0, 0
    use_quota = n_priors > 0 and quota > 0
    for fi in order:
        if len(cy) >= budget:
            break
        scanned += 1
        y, x = divmod(int(fi), w)
        if taken[y, x]:
            continue
        if use_quota and forbidden[fi]:
            blocked += 1
            continue
        cy.append(y)
        cx.append(x)
        y0, y1 = max(0, y - r), min(h, y + r + 1)
        x0, x1 = max(0, x - r), min(w, x + r + 1)
        taken[y0:y1, x0:x1] |= stamp[y0 - y + r:y1 - y + r, x0 - x + r:x1 - x + r]
        if use_quota:
            hits = np.flatnonzero(np.unpackbits(pt[fi])[:n_priors])
            if hits.size:
                counts[hits] += 1
                for k in hits[counts[hits] == quota]:
                    forbidden |= _halo_bool(pt, int(k))
    em = np.zeros(shape, bool)
    if cy:
        em[np.asarray(cy, np.int64), np.asarray(cx, np.int64)] = True
    return em, dict(requested=budget, placed=int(em.sum()), scanned=int(scanned),
                    blocked_by_quota=int(blocked))


def _halo_bool(pt, k):
    """Flat boolean halo of prior ``k``, recovered from the per-pixel bit-transposed table."""
    return (pt[:, k >> 3] & np.uint8(0x80 >> (k & 7))) != 0


def _near_counts(em, packed):
    """Exact directed 3 px near-dot count of every packed prior over the placed dots."""
    if not len(packed):
        return np.zeros(0, np.int64)
    idxd = np.flatnonzero(em.ravel())
    masks8 = np.array([0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01], np.uint8)
    bi = idxd >> 3
    bm = masks8[idxd & 7]
    return np.stack([((p[bi] & bm) != 0).sum() for p in packed]).astype(np.int64)


def stage_build(reg, args):
    th = reg["thresholds"]
    t0 = time.time()
    h61_reg, store, cat, eligible, folds, va, vb, ring_px = H.setup()
    hold = json.loads((EVID / "h77cond_holdout.json").read_text())
    scores = hold["pooled"]["scores"]
    pairs = hold["pooled"]["paired_vs_single_B"]
    arm = max(CANDIDATE_ARMS, key=lambda a: scores[a]["dti"])
    beats = bool(pairs[arm]["ci95"][0] > 0)
    log(f"shipped arm (best measured new arm by point HOLDOUT-DTI): {arm} "
        f"{scores[arm]['dti']:.6f}; beats single_B = {beats}")

    valid = np.load(WORK / "valid.npy")
    legal = np.load(WORK / "legal.npy")
    consensus = np.load(WORK / "consensus.npy").astype(np.int32)
    z = np.load(WORK / "quota_halos.npz", allow_pickle=True)
    quota_paths = [str(x) for x in z["paths"]]
    packed = [z[f"h{i}"] for i in range(len(quota_paths))]
    ncell = int(valid.size)
    pt, n_priors = _bit_transpose(packed, ncell)
    log(f"quota priors: {n_priors} packed ({sum(p.nbytes for p in packed)/1e6:.0f} MB) "
        f"+ per-pixel transpose ({pt.nbytes/1e6:.0f} MB)")

    rA, rB = _stitch_oof(store, folds, eligible)
    np.save(WORK / "rA_oof.npy", rA)
    np.save(WORK / "rB_oof.npy", rB)
    base_pool = legal & np.isfinite(rA) & np.isfinite(rB)
    S = int(th["shipped_budget_cells"])
    quota = int(np.floor(NEAR_TARGET * S))
    log(f"base pool {int(base_pool.sum())} px; budget {S}; per-prior near-dot quota {quota}")

    search = []
    chosen = None
    for c in CONSENSUS_GRID:
        pool_c = base_pool & (consensus <= c)
        npc = int(pool_c.sum())
        if npc < S * 3:                       # a pool barely larger than the budget cannot be spaced
            search.append(dict(consensus_le=c, pool_px=npc, skipped="pool too small for 3 px spacing"))
            log(f"  consensus<={c}: pool {npc} too small, skipped")
            continue
        field, core, rescue = _composite_field(arm, rA, rB, pool_c, S, th)
        em, st = _place(field, pool_c, S, float(th["min_dot_separation_px"]), pt, n_priors, quota,
                        eligible.shape)
        n = int(em.sum())
        cnt = _near_counts(em, packed)
        worst = int(cnt.max()) if cnt.size else 0
        allowed_at = int(np.floor(NEAR_TARGET * max(n, 1)))
        ok = bool(n == S and worst <= allowed_at)
        search.append(dict(consensus_le=c, pool_px=npc, placed=n, scanned=st["scanned"],
                           blocked_by_quota=st["blocked_by_quota"], worst_near=worst,
                           worst_share=round(worst / max(n, 1), 6),
                           allowed_at_achieved_budget=allowed_at, feasible=ok,
                           worst_prior=Path(quota_paths[int(cnt.argmax())]).name if cnt.size else None))
        log(f"  consensus<={c}: pool {npc} placed {n} worst {worst} "
            f"({worst/max(n,1):.4f}) allowed {allowed_at} -> {'FEASIBLE' if ok else 'no'}")
        if ok:
            chosen = (c, em, core, rescue, field)
            break
    if chosen is None:
        raise SystemExit("no consensus threshold produced a lane-feasible full budget; "
                         "search table in evidence/h77cond_placement.json")
    c_best, em, core, rescue, field = chosen
    pool_best = base_pool & (consensus <= c_best)
    # The brief requires written geological reasoning for EVERY A-only candidate.  That list is a
    # property of the lane (View A confident AND View B abstaining), not of whichever arm happened
    # to win the holdout, so it is computed unconditionally here.  swap_010 is the lane's
    # least-harmful rescue arm and defines which stratum cells the lane would actually emit.
    lo_r, hi_r = th["receiver_rank_interval"]
    donor_q = float(np.nanquantile(rA[pool_best], float(th["donor_rank_min"])))
    stratum = pool_best & (rA >= donor_q) & (rB >= lo_r) & (rB <= hi_r)
    f10, _c10, _r10 = _composite_field("swap_010", rA, rB, pool_best, S, th)
    em10, _st10 = _place(f10, pool_best, S, float(th["min_dot_separation_px"]), pt, n_priors, quota,
                         eligible.shape)
    a_only = em10 & stratum
    log(f"A-only stratum {int(stratum.sum())} px; lane candidate list (swap_010 emission within it) "
        f"{int(a_only.sum())} cells; shipped raster emits {int((em & stratum).sum())} of them")
    np.save(WORK / "pred.npy", em.astype(np.float32))
    np.save(WORK / "rescue.npy", rescue)
    np.save(WORK / "stratum.npy", stratum)
    np.save(WORK / "a_only_candidates.npy", a_only)
    del f10, em10
    place = dict(stage="placement", shipped_arm=arm, beats_single_B=beats,
                 budget=S, placed=int(em.sum()), consensus_threshold=c_best,
                 near_target=NEAR_TARGET, literal_limit=th["lane_near_dot_fraction"],
                 quota=quota, quota_priors=len(packed), search=search,
                 core_px=int(core.sum()), rescue_pool_px=int(rescue.sum()),
                 rescue_dots=int((em & rescue).sum()), core_dots=int((em & core).sum()),
                 a_only_stratum_px=int(stratum.sum()),
                 a_only_candidate_cells=int(a_only.sum()),
                 a_only_cells_in_shipped_raster=int((em & stratum).sum()),
                 a_only_note=("the A-only candidate list is the lane's, defined by swap_010's "
                              "emission inside the stratum; the shipped arm is chosen separately by "
                              "the frozen rule in knowledge/67a"),
                 pool_px=int((base_pool & (consensus <= c_best)).sum()),
                 base_pool_px=int(base_pool.sum()),
                 ranking=("stitched out-of-fold View B rank as the backbone; the weakest phi of the "
                          "budget swapped for View A's confident cells inside View B's blind band "
                          "(the brief's A-confident / B-abstaining discovery stratum)"
                          if arm.startswith("swap") else
                          "trace-integrated (line-support) transform of the stitched out-of-fold "
                          "View B operating field"),
                 placement=("greedy top-S, 3 px hard-core spacing, pool restricted to pixels of low "
                            "cross-family consensus, per-prior near-dot quota on the achieved budget"),
                 seconds=round(time.time() - t0, 1))
    H.write_ev("placement", place)
    log(f"PLACED {int(em.sum())} dots at consensus<={c_best} "
        f"({place['rescue_dots']} A-rescue, {place['core_dots']} B-core)")
    return place


# =================================================================================================
# gates, GeoTIFF, reasoning CSV, run card
# =================================================================================================
def _orientation_index(field, allowed, n_orient=12, chord_px=7):
    """Index of the orientation whose 600 m chord best supports each pixel (same chords as
    ``line_support``).  Used to apply the preregistered cultural-lineament falsifier: a road, canal
    or powerline is straight and overwhelmingly cardinal, so an emitted stratum whose best-supported
    orientations pile up within 10 deg of N-S or E-W is carrying infrastructure, not structure."""
    f = np.where(allowed, np.nan_to_num(field, nan=0.0), 0.0).astype(np.float32)
    half = int(chord_px) // 2
    best = np.full(f.shape, -np.inf, np.float32)
    arg = np.zeros(f.shape, np.int8)
    for k in range(int(n_orient)):
        theta = np.pi * k / float(n_orient)
        dy, dx = np.sin(theta), np.cos(theta)
        acc = np.zeros_like(f)
        seen = set()
        for tt in range(-half, half + 1):
            oy, ox = int(round(dy * tt)), int(round(dx * tt))
            if (oy, ox) in seen:
                continue
            seen.add((oy, ox))
            acc += f if (oy == 0 and ox == 0) else H._shift0(f, oy, ox)
        acc /= float(len(seen))
        upd = acc > best
        best[upd] = acc[upd]
        arg[upd] = k
        del acc, upd
    return arg


def _disagreement_audit(pred, stratum, a_only, rA, rB, pool, th):
    """The brief's two disagreement readings, measured rather than asserted.

    A-only (View A confident, View B abstaining) -> candidate fault concealed beneath cover.
    B-only (View B confident, View A abstaining) -> suspect roads, canals, powerlines, erosion lines.
    The cardinal-orientation share is the falsifier for the second reading; it is reported for both
    strata and for a matched random control so the number means something.
    """
    lo, hi = th["receiver_rank_interval"]
    donor = float(th["donor_rank_min"])
    b_only = pool & (rB >= np.nanquantile(rB[pool], donor)) & (rA >= lo) & (rA <= hi)
    d = pred > 0
    arg = _orientation_index(np.nan_to_num(rB, nan=0.0), pool)
    n_or = 12
    # orientation k spans theta = pi*k/12; cardinal = within 10 deg of 0 (E-W) or 90 deg (N-S)
    cardinal = {k for k in range(n_or) if min(abs(180.0 * k / n_or - 0.0),
                                              abs(180.0 * k / n_or - 90.0),
                                              abs(180.0 * k / n_or - 180.0)) <= 10.0}
    rng = np.random.default_rng(H.SEED + 909)
    pidx = np.flatnonzero(pool.ravel())
    ctrl = np.zeros(pool.shape, bool)
    ctrl.ravel()[rng.choice(pidx, size=min(int(d.sum()), pidx.size), replace=False)] = True

    def share(mask):
        v = arg[mask]
        return (float(np.isin(v, list(cardinal)).mean()) if v.size else None), int(v.size)

    a_sh, a_n = share(a_only)
    b_sh, b_n = share(d & b_only)
    all_sh, all_n = share(d)
    c_sh, c_n = share(ctrl)
    return dict(
        a_only_candidates=a_n, b_only_dots=b_n, emitted_dots=all_n,
        a_only_cells_in_shipped_raster=int((d & stratum).sum()),
        b_only_pool_px=int(b_only.sum()), a_only_pool_px=int(stratum.sum()),
        cardinal_orientation_share=dict(a_only=a_sh, b_only=b_sh, all_emitted=all_sh,
                                        matched_random_control=c_sh, control_dots=c_n),
        cardinal_definition="best 600 m chord orientation within 10 deg of due N-S or due E-W",
        a_only_reading="View A confident, View B abstaining -> fault possibly concealed beneath cover",
        b_only_reading=("View B confident, View A abstaining -> suspect roads, canals, powerlines or "
                        "erosion lines; a cardinal share materially above the random control is "
                        "evidence of cultural infrastructure rather than structure"),
        evidence_class="disagreement diagnostic on out-of-fold ranks; not field-verified geology")


def stage_card(reg, args):
    th = reg["thresholds"]
    t0 = time.time()
    h61_reg, store, cat, eligible, folds, va, vb, ring_px = H.setup()
    valid = np.load(WORK / "valid.npy")
    legal = np.load(WORK / "legal.npy")
    pred = np.load(WORK / "pred.npy")
    rescue = np.load(WORK / "rescue.npy")
    stratum = np.load(WORK / "stratum.npy")
    a_only = np.load(WORK / "a_only_candidates.npy")
    rA = np.load(WORK / "rA_oof.npy")
    rB = np.load(WORK / "rB_oof.npy")
    place = json.loads((EVID / "h77cond_placement.json").read_text())
    hold = json.loads((EVID / "h77cond_holdout.json").read_text())
    s1 = json.loads((EVID / "h77cond_sufficiency.json").read_text())
    indep = json.loads((EVID / "h77cond_independence.json").read_text())
    canary = json.loads((EVID / "h77cond_canary.json").read_text())
    arm = place["shipped_arm"]
    S = int(pred.sum())
    sample = ROOT / "data/sample_submission.tif"
    st = (args.stamp or "").strip() or H.stamp()

    name = f"gems77cond-{arm.replace('_','-')}-cotrain-{S}px-{st}"
    tif = SUBM / f"{name}.tif"
    what = ("trace-integrated View B 600m chord" if arm == "line_support_B"
            else f"B-core+A-rescue swap phi={int(arm.split('_')[1])/100:g}")
    verdict_tag = "RESEARCH ONLY-DO NOT SUBMIT" if not beats else "selector-eligible"
    # The note must never be truncated: a [:140] slice once silently cut the words "do not
    # submit" off a research-only file.  It must also survive a round-label rename -- "H77cond"
    # is 4 characters longer than "H77cond" and pushed the full form to 141.  So instead of either
    # truncating or hard-failing, step through progressively more compact VARIANTS that all keep
    # the verdict first and every fact intact, and only give up if even the shortest overflows.
    c = place["consensus_threshold"]
    variants = [
        f"H77cond {verdict_tag}: co-training {what}; {S}px binary; >200m off catalogue; "
        f"lane-feasible c<={c}",
        f"H77cond {verdict_tag}: co-training {what}; {S}px binary; >200m off catalogue; lane c<={c}",
        f"H77cond {verdict_tag}: cotrain {what}; {S}px binary; >200m off catalogue; lane c<={c}",
        f"H77cond {verdict_tag}: cotrain {what}; {S}px binary; lane c<={c}",
    ]
    note = next((v for v in variants if len(v) <= 140), "")
    if not note:                              # must never truncate away the verdict word
        raise SystemExit(f"submission note is {len(variants[-1])} chars even at its most "
                         f"compact: {variants[-1]}")
    if note != variants[0]:
        log(f"NOTE: full form was {len(variants[0])} chars (>140); used compact variant "
            f"{variants.index(note)} at {len(note)} chars")

    # ---- 1. format + packaging (shared fail-closed writer) --------------------------------------
    receipt = submission_writer.write_submission(
        tif, pred.astype(np.float32), sample, valid, note=note, name=name,
        metadata=dict(round="H77cond", arm=arm, consensus_threshold=place["consensus_threshold"],
                      dots=S, holdout_evaluator=hold["pooled"]["implementation_sha256"]))
    fmt = receipt["validator"]
    log(f"FORMAT gate ok={fmt['ok']} sha256 {receipt['sha256'][:16]}…")

    # ---- 2. uniqueness + lane, against the whole accessible registry ----------------------------
    priors = prior_paths()
    own = {tif.resolve(), (DOWN / "h77cond-candidate.tif").resolve(),
           (DOWN / f"{name}.tif").resolve()}
    clash = [str(p) for p in priors if p.resolve() in own or p.name == tif.name]
    if clash:
        raise SystemExit(f"the candidate leaked into its own prior list: {clash}")
    log(f"registry for the gates: {len(priors)} rasters, candidate excluded by round token")
    uniq = gates.uniqueness_report(pred, priors)
    log(f"UNIQUENESS: distinct_from_every_comparable_prior="
        f"{uniq['distinct_from_every_comparable_prior']} (identical={uniq['identical_prior_paths']}) "
        f"audit_complete={uniq['audit_complete']} incomparable={len(uniq['incomparable_priors'])} "
        f"novel_fraction={uniq['novel_fraction']:.4f} union={uniq['equals_literal_prior_union']}")

    surface = np.where(legal, np.nan_to_num(rB, nan=0.0), 0.0).astype(np.float32)
    lo_s, hi_s = float(surface[legal].min()), float(surface[legal].max())
    if hi_s > lo_s:
        surface[legal] = (surface[legal] - lo_s) / (hi_s - lo_s)
    cov_cache = {}
    for r in json.loads((WORK / "registry_rows.json").read_text()):
        if r.get("decoded_sha256") and r.get("coverage_3px_of_legal") is not None:
            cov_cache[r["decoded_sha256"]] = r["coverage_3px_of_legal"]
    lane_surface = gates.lane_report(surface, legal, priors, sample=sample, phase="surface",
                                     coverage_cache=cov_cache, log=log)
    lane_dots = gates.lane_report(pred, legal, priors, sample=sample, phase="dots",
                                  coverage_cache=cov_cache, log=log)
    log(f"LANE surface literal={lane_surface['literal']['verdict']} "
        f"policy={lane_surface['policy']['verdict']}; dots literal={lane_dots['literal']['verdict']} "
        f"policy={lane_dots['policy']['verdict']} max_near={lane_dots['policy']['max_near_3px_fraction']}")

    # ---- 3. not the union of the two views ------------------------------------------------------
    pool = legal & np.isfinite(rA) & np.isfinite(rB)
    um = nodes.spacing_select(np.nan_to_num(np.maximum(rA, rB), nan=-1.0), pool, S,
                              min_px=float(th["min_dot_separation_px"]))
    bm = nodes.spacing_select(np.nan_to_num(rB, nan=-1.0), pool, S,
                              min_px=float(th["min_dot_separation_px"]))
    am = nodes.spacing_select(np.nan_to_num(rA, nan=-1.0), pool, S,
                              min_px=float(th["min_dot_separation_px"]))
    d = pred > 0
    not_union = dict(
        jaccard_vs_union_max=float((d & um).sum() / max(int((d | um).sum()), 1)),
        jaccard_vs_single_B=float((d & bm).sum() / max(int((d | bm).sum()), 1)),
        jaccard_vs_single_A=float((d & am).sum() / max(int((d | am).sum()), 1)),
        dots_in_A_only_stratum=int((d & stratum).sum()),
        rule="PASS if the emission is not the union placement and not a relabelled single view",
        pass_=bool(float((d & um).sum() / max(int((d | um).sum()), 1)) < 0.5
                   and not np.array_equal(d, um) and not np.array_equal(d, bm)
                   and not np.array_equal(d, am)))
    H.write_ev("not_union", not_union)
    log(f"NOT-UNION pass={not_union['pass_']} J(union)={not_union['jaccard_vs_union_max']:.4f} "
        f"J(B)={not_union['jaccard_vs_single_B']:.4f}")

    dis = _disagreement_audit(pred, stratum, a_only, rA, rB, pool, th)
    H.write_ev("disagreement", dis)
    log(f"DISAGREEMENT a_only {dis['a_only_candidates']} candidates (cardinal {dis['cardinal_orientation_share']['a_only']}) | "
        f"b_only {dis['b_only_dots']} dots (cardinal {dis['cardinal_orientation_share']['b_only']}) | "
        f"random control {dis['cardinal_orientation_share']['matched_random_control']}")

    # ---- 4. per-dot geological reasoning for every A-only candidate ------------------------------
    reasoning_rows, reasoning_summary = _reasoning(a_only, pred, rA, rB, cat, store, eligible)
    csv_path = DOWN / "h77cond-a-only-reasoning.csv"
    DOWN.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(reasoning_rows[0].keys()) if reasoning_rows else
                           ["note"])
        w.writeheader()
        for row in reasoning_rows:
            w.writerow(row)
    log(f"REASONING rows {len(reasoning_rows)} -> {csv_path.name}")

    # ---- 5. verdict: the six frozen clauses -----------------------------------------------------
    scores = hold["pooled"]["scores"]
    pairs = hold["pooled"]["paired_vs_single_B"]
    clauses = dict(
        c1_format=bool(fmt["ok"]),
        c2_unique=bool(uniq["distinct_from_every_comparable_prior"]
                       and not uniq["equals_literal_prior_union"]),
        c3_lane_dots_policy=bool(lane_dots["policy"]["verdict"] == "PASS"),
        c4_not_union=bool(not_union["pass_"]),
        c5_S1_conditional=bool(s1["S1_conditional_pass"]),
        c6_beats_single_B=bool(pairs[arm]["ci95"][0] > 0))
    promote = all(clauses.values())
    verdict = "PROMOTE (all six frozen clauses pass)" if promote else "NEGATIVE, research-only"
    failing = [k for k, v in clauses.items() if not v]

    card = dict(
        round="H77cond", generated_utc=H.now(), runner="scripts/run_h77cond.py",
        preregistration=dict(document=reg["hypothesis_document"], sha256=reg["hypothesis_sha256"],
                             frozen_before_any_fit=True),
        hypothesis=("The co-training sufficiency gate that closed this lane five times is measured "
                    "against a target the catalogue systematically under-samples: mapped faults are "
                    "surface-expressed by selection, which is View B's domain. H77cond tests sufficiency "
                    "CONDITIONALLY (View A's AUC restricted to truth pixels inside View B's blind "
                    "band) and emits the first nested arm: View B's ranking with the weakest phi of "
                    "its budget swapped for View A's confident cells where View B abstains."),
        mechanism=("A density/susceptibility/strain discontinuity with no co-located topographic or "
                   "radiometric step: a fault that offsets basement and basin fill but whose scarp is "
                   "buried under Quaternary alluvium, so a 100 m DEM sees nothing."),
        named_non_fault_process=("A buried lithologic contact (Tertiary volcanics against basin fill) "
                                 "makes the same potential-field edge with no surface step and is not "
                                 "a fault; aeromagnetic flight-line / tie-line levelling residues are "
                                 "linear, surface-invisible and strike with the survey plan."),
        evidence_classes=dict(
            HOLDOUT_DTI="internal hide-and-recover (gems52-pooled-hide-v1); not a leaderboard score",
            ORGANIZER_CONFIRMED="none produced by this round",
            PUBLIC_LEADERBOARD="team rows with no filename; never attached to a file here"),
        leakage_canary=dict(max_auc=canary["max_auc"], feature=canary["max_feature"],
                            alarm_threshold=canary["alarm_auc"], any_alarm=canary["any_alarm"]),
        independence=dict(max_abs_correlation=indep["max_abs_correlation"],
                          n_blocks=indep["n_blocks"], threshold=indep["threshold"],
                          allow_exchange=indep["allow_exchange"],
                          negative_class=indep["negative_class"]),
        sufficiency=dict(S1_global_mean_auc_A=s1["mean_auc_A"], S1_global_pass=s1["S1_global_pass"],
                         S1_conditional_blind_auc=s1["mean_auc_A_blind"],
                         S1_conditional_bright_auc=s1["mean_auc_A_brightB"],
                         S1_conditional_margin=s1["conditional_margin"],
                         S1_conditional_pass=s1["S1_conditional_pass"]),
        holdout_dti=dict(
            evaluator_version="gems52-pooled-hide-v1",
            withheld_positive_pixels=hold["withheld_positive_pixels"],
            shipped_arm=arm, shipped_arm_dti=scores[arm]["dti"], shipped_arm_ci95=scores[arm]["ci95"],
            single_B_control=scores["single_B"]["dti"], single_B_ci95=scores["single_B"]["ci95"],
            paired_delta_vs_single_B=pairs[arm]["delta"], paired_ci95=pairs[arm]["ci95"],
            all_arms=({k: dict(dti=v["dti"], ci95=v["ci95"]) for k, v in scores.items()}),
            control_reproduction=hold["control_reproduction"],
            caveat=hold["caveat"]),
        correlation_overlap_vs_registry=dict(
            surface_max_spearman_policy=lane_surface["policy"]["max_spearman"],
            surface_verdict_literal=lane_surface["literal"]["verdict"],
            surface_verdict_policy=lane_surface["policy"]["verdict"],
            dots_max_near_3px_policy=lane_dots["policy"]["max_near_3px_fraction"],
            dots_max_near_3px_literal=lane_dots["literal"]["max_near_3px_fraction"],
            dots_verdict_literal=lane_dots["literal"]["verdict"],
            dots_verdict_policy=lane_dots["policy"]["verdict"],
            informative_priors=lane_dots["policy"]["informative_priors"],
            universal_coverage_probes=lane_dots["policy"]["universal_coverage_probes"],
            novel_fraction_vs_prior_union=uniq["novel_fraction"],
            relation_to_prior_union=uniq["relation_to_union"],
            canonical_pattern_unique=uniq["canonical_pattern_unique"],
            distinct_from_every_comparable_prior=uniq["distinct_from_every_comparable_prior"],
            identical_prior_paths=uniq["identical_prior_paths"],
            audit_complete=uniq["audit_complete"],
            priors_compared=uniq["n_priors_compared"],
            incomparable_priors=uniq["incomparable_priors"],
            equals_literal_prior_union=uniq["equals_literal_prior_union"],
            consensus_threshold=place["consensus_threshold"]),
        raster_sha256=receipt["sha256"], raster_bytes=receipt["bytes"],
        validator=dict(no_nan_inside_footprint=int(fmt["nan_pixels"]) == 0,
                       values_in_0_1=bool(fmt["min"] >= 0.0 and fmt["max"] <= 1.0),
                       value_set=[0.0, 1.0], bands=fmt["bands"], dtype=fmt["dtype"],
                       crs=fmt["crs"], shape=[fmt["height"], fmt["width"]],
                       transform=fmt["transform"], matches_sample=bool(fmt["ok"]),
                       mass_outside_footprint=fmt.get("mass_outside_footprint", 0),
                       problems=fmt["problems"]),
        not_union=not_union,
        disagreement=dis,
        placement=place,
        a_only_reasoning=reasoning_summary,
        submission_name=name, submission_note=note, note_chars=len(note),
        gates=clauses, failing_clauses=failing,
        verdict=verdict,
        download_ok=bool(fmt["ok"]),
        submit_recommended=bool(promote),
        submit_recommendation_reason=(
            "all six frozen clauses in knowledge/67 section 3 pass" if promote else
            "The frozen promote rule requires format AND uniqueness AND the final-dot lane AND "
            "not-the-union AND conditional sufficiency AND a holdout paired CI lower bound above "
            "single_B; failing clauses: " + ", ".join(failing) + " -> do not spend a weekly slot"),
        slots_used=0,
        organizer_confirmed=False,
        seconds=round(time.time() - t0, 1))
    H.write_ev("run_card", card)
    H.write_ev("format_gate", fmt)
    H.write_ev("uniqueness", {k: v for k, v in uniq.items() if k != "per_prior"})
    H.write_ev("lane_surface", {k: v for k, v in lane_surface.items() if k != "per_prior"})
    H.write_ev("lane_dots", {k: v for k, v in lane_dots.items() if k != "per_prior"})

    # ---- 6. publish the one-click download ------------------------------------------------------
    DOWN.mkdir(parents=True, exist_ok=True)
    (DOWN / "h77cond-candidate.tif").write_bytes(tif.read_bytes())
    (DOWN / "h77cond-candidate.zip").write_bytes(tif.with_suffix(".zip").read_bytes())
    (SUBM / "H77COND_LATEST.txt").write_text(
        f"{tif.name}\n# site pointer, NOT an upload approval. Verdict: {verdict}. "
        f"Download OK: {fmt['ok']}. Spend a weekly slot: {promote}.\n")
    (SUBM / f"{name}-run-card.json").write_text(
        json.dumps(card, indent=1, allow_nan=False, default=H._json_default) + "\n")
    log(f"RUN CARD verdict={verdict} | download_ok={fmt['ok']} | submit={promote}")
    log(f"TIFF {tif.name} {receipt['bytes']} bytes sha256 {receipt['sha256']}")
    return card


def _reasoning(a_only, pred, rA, rB, cat, store, eligible):
    """One row per A-only (A-confident / B-abstaining) candidate cell: measured context, a named
    non-fault process that could mimic it, and the falsifier a Phase-2 reviewer would apply.

    The list is the lane's, so it exists even when the holdout sends a different arm to the TIFF;
    each row records whether the shipped raster actually emits that cell."""
    d = np.asarray(a_only, bool)
    shipped = pred > 0
    yy, xx = np.nonzero(d)
    rows = []
    if not len(yy):
        return rows, dict(n_a_only_candidates=0,
                          note="the lane produced no cell inside the strict A-only stratum")
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        tr = ref.transform
    catd = ndi.distance_transform_edt(~cat, sampling=100.0)
    flat = (yy * eligible.shape[1] + xx).astype(np.int64)
    # Names verified line-by-line against src/gems52_h1/spec.py OFFICIAL_BANDS, which was read
    # from the restored GeoTIFF headers.  IR-52-01: band 6 "tc" is a MAGNETIC tilt/total-curvature
    # derivative, NOT radiometric total count -- true airborne gamma-ray channels only exist in the
    # external USGS GeoDAWN layers (X_rad_*), so the radiometric column below uses those.
    cols = ["raw_band_15", "raw_band_13", "raw_band_02", "raw_band_19", "raw_band_06",
            "raw_band_12", "X_rad_K_rank", "X_rad_Th_rank", "X_rad_U_rank"]
    X = store.gather(flat, cols)
    pct = {}
    for j, c in enumerate(cols):
        col = np.load(store.directory / f"{c}.npy", mmap_mode="r")
        q = np.quantile(np.asarray(col[::97], np.float64), np.linspace(0, 1, 101))
        pct[c] = np.clip(np.searchsorted(q, X[:, j]), 0, 100)
        del col
    for i in range(len(yy)):
        e, n = tr * (float(xx[i]) + 0.5, float(yy[i]) + 0.5)
        cover = int(pct["raw_band_15"][i])
        mimic = ("buried lithologic contact (Tertiary volcanic unit against basin fill) — same "
                 "potential-field edge, no surface step, not a fault"
                 if cover >= 50 else
                 "aeromagnetic flight-line / tie-line levelling residue — linear, surface-invisible, "
                 "strikes with the survey plan, not a fault")
        rows.append(dict(
            utm11n_easting_m=round(float(e), 1), utm11n_northing_m=round(float(n), 1),
            row=int(yy[i]), col=int(xx[i]),
            view_A_oof_rank=round(float(rA[yy[i], xx[i]]), 5),
            view_B_oof_rank=round(float(rB[yy[i], xx[i]]), 5),
            depth_to_basement_b15_pctile=cover,
            isostatic_gravity_b13_pctile=int(pct["raw_band_13"][i]),
            rtp_magnetic_b02_pctile=int(pct["raw_band_02"][i]),
            detrended_elev_slope_b19_pctile=int(pct["raw_band_19"][i]),
            detrended_elev_b12_pctile=int(pct["raw_band_12"][i]),
            mag_tilt_total_curvature_b06_pctile=int(pct["raw_band_06"][i]),
            radiometric_K_pctile=int(pct["X_rad_K_rank"][i]),
            radiometric_Th_pctile=int(pct["X_rad_Th_rank"][i]),
            radiometric_U_pctile=int(pct["X_rad_U_rank"][i]),
            distance_to_mapped_trace_m=round(float(catd[yy[i], xx[i]]), 1),
            interpretation=("View A (potential field / subsurface) is in its top 5% here while View B "
                            "(surface) abstains: the candidate is a basement-offsetting structure "
                            "with no 100 m-scale surface expression, i.e. a fault concealed beneath "
                            "cover" if cover >= 50 else
                            "View A confident, View B abstaining on thin cover: either a steeply "
                            "dipping structure with a subdued scarp, or an artefact"),
            named_non_fault_mimic=mimic,
            falsifier=("reject if the anomaly strike lies within 10 deg of the survey flight azimuth, "
                       "or if 1 m LiDAR shows a continuous unfaulted Quaternary surface across it, or "
                       "if mapped Tertiary volcanic contacts coincide within 300 m"),
            emitted_in_shipped_raster=bool(shipped[yy[i], xx[i]]),
            evidence_class="HYPOTHESIS from measured context; NOT field-verified geology"))
    summary = dict(n_a_only_candidates=int(len(rows)),
                   n_emitted_in_shipped_raster=int((d & shipped).sum()),
                   median_depth_to_basement_pctile=float(np.median(pct["raw_band_15"])),
                   median_dem_slope_pctile=float(np.median(pct["raw_band_19"])),
                   median_distance_to_mapped_trace_m=float(np.median(catd[yy, xx])),
                   rule=("every A-only candidate the lane identifies carries a written reason, a "
                         "named non-fault mimic and a falsifier, whether or not the shipped arm "
                         "emits it"),
                   evidence_class="HYPOTHESIS, not verified geology")
    return rows, summary
