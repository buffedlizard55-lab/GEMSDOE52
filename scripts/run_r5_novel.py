#!/usr/bin/env python3
"""R5 stage 7 -- build, judge and emit the *strictly novel* R5 submission.

Why this script exists separately from ``run_r5.py``
---------------------------------------------------
``run_r5.py`` ranks candidates on the whole-component localisation assay (hide a fold of the mapped
catalogue, emit inside it, measure lateral error).  That instrument is **not** a promotion gate, and
this round reproduced the reason on new data: on it the champion family's habitat field scores
0.0003 while uniform random scores 0.0275 and the new six-family trace field scores 0.0395, an
ordering the organiser's own board contradicts completely (the champion file is the *worst* of the
13 on that instrument and the *best* on the board -- ``knowledge/10`` §5, Spearman -0.1045,
p = 0.734, n = 13).  So the assay is reported as evidence about mechanism and is used for nothing
else.

What is used instead, frozen before any of the numbers below were computed
--------------------------------------------------------------------------
Every statement here must be read with the provenance limits in ``knowledge/49`` and
``evidence/r5_provenance_audit_20261009.json``. Published score/file associations are owner-reported,
not organizer-authenticated. This is a historical research build; its format and build-time uniqueness
checks do not grant submission eligibility.

Conditional scenario model (not hidden-truth measurement)
  * The legacy ``|G| = 14,088.7 px`` point estimate and the earlier claim that the 100-200 m ring
    has exactly zero credit are not established. The organizer states that new-fault truth may lie
    within 300 m of known traces. The R5 budget calculation used the legacy estimate; retain it only
    as a conditional scenario, not a measured truth size or score explanation.
  * The official distance-weighted Tversky metric is the source of truth. The sparse-emission
    simplification ``DTI ≈ T / (0.2 S + 0.8 |G|)`` depends on assumptions about ``M`` and is not an
    identity for arbitrary rasters or hidden faults.
  * ``T(S) = 471.6 S^0.2284`` is a model fit to owner-reported score associations, not a measurement
    against hidden labels. Its posterior projections are not leaderboard scores and the associated
    hide-and-recover instrument is not a qualified leaderboard predictor.
  * Strike-coherence summaries describe the local owner-score-derived reference cloud; they do not
    establish credited hidden-truth pixels or confirm a geological fault.

Frozen rules
  R1  The historical build-time emission was compared with the accessible inventory at build time:
      the receipt records 71 rasters and 1.0 support novelty. It also excluded cells within 200 m of
      the local known-fault mask as an internal project rule, not an organizer scoring rule. A
      2026-10-09 cumulative closure recheck finds 120 accessible rasters, 0.874408 support novelty,
      and a distinct decoded pattern. Thus it is not strictly novel against the current inventory.
      The free-text submission note's original 55 count was stale and is corrected in the audit receipt.
      This does not make the TIFF submission-approved.
  R2  The budget is ``S* = 4 |G| beta / (1 - beta)`` with the measured ``beta``.  Not tuned.
  R3  Among candidates, choose the one with the largest **coherence lift over the random control**
      (mean coherence at sigma=4 plus fraction above 0.8, each minus the control's), subject to its
      dominant strike falling inside the credited band 095-115 deg array convention.  If no candidate
      satisfies the band, take the largest lift and report the failure.
  R4  Report ``P(DTI > 0.2778)`` and ``P(DTI > 0.3195)`` under the frozen field-quality prior
      ``kappa ~ U[0.3, 1.3]`` on ``T(S) = kappa * 471.6 * S^0.2284``, where kappa = 1 is "as good as
      this family's own field at the same budget".  The measured spread across the repo's 13 files is
      kappa ~ 0.1 (PLACEHOLDER) to ~1.0 (the champion), and an outside-family PINN file scored
      0.2750 at 38,854 px, i.e. kappa ~ 1.0, so the prior is not optimistic.

Writes ``evidence/r5_novel_emission.json`` (+ ``docs/data/``), the ranked-candidate table, and the
GeoTIFF itself into ``submission/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import gates as G                    # noqa: E402
from gems52 import grid as GRID                  # noqa: E402
from gems52 import revealed as RV                # noqa: E402
from gems52_r5 import layers as L                # noqa: E402
from gems52_r5 import localize as Z              # noqa: E402
from gems52_r5 import revealed_r5 as R           # noqa: E402

WORK = ROOT / "work" / "r5"
EVID = ROOT / "evidence"
SUB = ROOT / "submission"
DOCS = ROOT / "docs"

G_PX = R.G_PX                 # legacy conditional point estimate; not established (see knowledge/49)
BETA = 0.2284                 # owner-score-derived model exponent; not hidden-truth measurement
C_FIELD = 471.6               # owner-score-derived model amplitude; not hidden-truth measurement
CORRIDOR_M = 200.0            # internal historical emission rule, not an organizer scoring buffer
CHAMPION = 0.2778             # owner-reported reference; extradr19 was observed at rank 17 on 2026-10-09 20:18 UTC; no file mapping
BOARD = 0.3195                # DARD, observed at rank 7 on the saved 2026-10-09 20:18 UTC board reading
BOARD_TOP = 0.3774            # xiaofanhu, observed at rank 1 on the saved 2026-10-09 20:18 UTC board reading
CREDITED_STRIKE_DEG = (100.0, 110.0)     # array convention, knowledge/10 §7
BAND_TOL_DEG = 5.0
MIN_SEP = 3.0
KAPPA = (0.3, 1.3)
SEED = 20261012


def log(m: str) -> None:
    rss = float("nan")
    with open("/proc/self/status") as fh:
        for line in fh:
            if line.startswith("VmRSS:"):
                rss = float(line.split()[1]) / 1024.0
    print(f"{m}   [rss {rss:.0f} MB]", flush=True)


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def budget_star(g: float = G_PX, beta: float = BETA) -> int:
    """DTI-optimal budget for a credit curve ``T = c S^beta``: ``S* = 4 g beta / (1 - beta)``.

    Derived by setting d/dS [c S^beta / (0.2 S + 0.8 g)] = 0; the amplitude ``c`` cancels, so the
    optimum depends only on the exponent and on |G| -- which is why it can be frozen before any
    candidate is built.
    """
    return int(round(4.0 * g * beta / (1.0 - beta)))


def dti_of(t: float, s: float, g: float = G_PX) -> float:
    return float(t) / (0.2 * float(s) + 0.8 * g)


def win_probability(s: int, target: float, kappa: tuple[float, float] = KAPPA) -> dict:
    """P(DTI > target) under ``T = kappa * C_FIELD * s^BETA``, ``kappa ~ U[kappa[0], kappa[1]]``."""
    t1 = C_FIELD * s ** BETA
    need = target * (0.2 * s + 0.8 * G_PX)          # credit required to clear the target
    k_need = need / t1
    lo, hi = kappa
    p = float(np.clip((hi - k_need) / (hi - lo), 0.0, 1.0))
    if need > G_PX:                                  # the |G| cap makes it unreachable at any kappa
        p = float(np.clip((hi - G_PX / t1) / (hi - lo), 0.0, 1.0)) if G_PX / t1 < hi else 0.0
    return dict(budget=s, target=target, credit_needed=need, kappa_needed=k_need,
                t_at_kappa1=t1, dti_at_kappa1=dti_of(min(t1, G_PX), s),
                dti_at_kappa_lo=dti_of(min(lo * t1, G_PX), s),
                dti_at_kappa_hi=dti_of(min(hi * t1, G_PX), s), p_win=p)


def coherence_stats(dots: np.ndarray, sigmas=(4.0, 6.0, 10.0)) -> dict:
    """knowledge/10 §7's instrument: structure-tensor coherence of the emitted dot cloud."""
    out = {"n_dots": int(dots.sum())}
    coh4 = None
    for sg in sigmas:
        coh, strike, dens = RV.strike_field(dots, sigma_px=sg)
        at = dots > 0
        c = coh[at]
        out[f"mean_coherence_sigma{sg:g}"] = float(c.mean()) if c.size else 0.0
        out[f"frac_coh_above_0.8_sigma{sg:g}"] = float((c > 0.8).mean()) if c.size else 0.0
        if sg == 4.0:
            coh4 = (coh, strike)
    coh, strike = coh4
    at = dots > 0
    deg = np.degrees(strike[at]) % 180.0
    hist, edges = np.histogram(deg, bins=18, range=(0.0, 180.0))
    peak = int(np.argmax(hist))
    out["dominant_strike_deg_array"] = float(0.5 * (edges[peak] + edges[peak + 1]))
    out["dominant_strike_frac"] = float(hist[peak] / max(hist.sum(), 1))
    out["strike_hist_10deg"] = [int(x) for x in hist]
    lo, hi = CREDITED_STRIKE_DEG[0] - BAND_TOL_DEG, CREDITED_STRIKE_DEG[1] + BAND_TOL_DEG
    out["frac_in_credited_band"] = float(((deg >= lo) & (deg <= hi)).mean())
    out["in_credited_band"] = bool(lo <= out["dominant_strike_deg_array"] <= hi)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=0, help="override S* (0 = use the frozen rule)")
    ap.add_argument("--dry-run", action="store_true", help="judge candidates, do not write a raster")
    args = ap.parse_args()
    t0 = time.time()

    valid = np.load(WORK / "valid.npy")
    cat = L.catalogue()
    edt_cat = ndimage.distance_transform_edt(~cat, sampling=100.0)
    legal = valid & (edt_cat > CORRIDOR_M)
    # Novelty is checked against every accessible raster in these shared locations, not only the 13
    # organizer-scored files. The inventory changes as parallel research artifacts arrive; therefore
    # record the exact run-time prior count and date in the emission receipt instead of hard-coding a
    # count here. An earlier build showed overlap with an unscored research artifact, motivating the
    # broader comparison. Build-time uniqueness is not submission eligibility.
    prior_paths = G.find_priors([ROOT / "data/scored", ROOT / "data/reference", ROOT / "submission",
                                 ROOT / "docs/downloads"])
    # ... minus this round's own builds and their short alias.  The emission is deterministic, so a
    # rebuild that counted its own previous output as a prior would place its dots somewhere else and
    # stop reproducing -- the same self-comparison trap that gates.py records as IR-52-026, arriving
    # from the other direction.  Every other round stays a prior.
    SELF = ("gems52-r5-novel-", "r5-candidate.tif")
    n_all = len(prior_paths)
    prior_paths = [q for q in prior_paths if not q.name.startswith(SELF[0]) and q.name != SELF[1]]
    n_self = n_all - len(prior_paths)
    prior_union = np.zeros(valid.shape, bool)
    for pp in prior_paths:
        with rasterio.open(pp) as ds:
            a = G.canonical(ds.read(1))
        prior_union |= (a > 0) if bool(np.isin(a, [0, 1]).all()) else (a >= 0.5)
        del a
    # the 13 organiser-scored supports, recomputed from the restored bytes rather than read from a
    # cache in the gitignored work/ tree: a fresh checkout has no such file, and a script that only
    # runs where its author left a cache behind is not reproducible
    supp = R.load_supports(ROOT / "data")
    scored_union = np.zeros(valid.shape, bool)
    for m in supp.values():
        scored_union |= m & valid
    del supp
    novel = legal & ~prior_union
    log(f"[inputs] footprint {int(valid.sum()):,} px, legal (off-ring) {int(legal.sum()):,} px")
    log(f"[inputs] {len(prior_paths)} repo rasters ({n_self} of this round's own builds excluded so a "
        f"rebuild reproduces) -> prior union {int(prior_union.sum()):,} px "
        f"({int((prior_union & legal).sum()):,} of them legal); the 13 organiser-scored files alone "
        f"cover {int((scored_union & legal).sum()):,} legal px")
    log(f"[inputs] strictly-novel pool {int(novel.sum()):,} px "
        f"({100.0 * novel.sum() / legal.sum():.1f} % of the legal footprint)")

    corr99 = np.load(WORK / f"corrobor_{0.99:g}.npy")
    corr95 = np.load(WORK / f"corrobor_{0.95:g}.npy")
    fams = [np.load(WORK / f"fam_{f}.npz")["resp"] for f in L.FAMILIES]
    rmax = np.nan_to_num(np.max(np.stack(fams), axis=0), nan=0.0)
    del fams
    from gems52_r5 import emit_r5 as EM
    persist = {f: EM.persistence_length(np.load(WORK / f"trace_{f}_{0.99:g}.npy"))
               for f in L.FAMILIES}
    persist_max = ndimage.maximum_filter(
        np.max(np.stack([persist[f] for f in L.FAMILIES]), axis=0), size=5)
    persist_n = np.log1p(persist_max) / max(float(np.percentile(persist_max[valid], 99.9)), 1e-9)
    del persist, persist_max

    trace = corr99.astype(np.float64) / 6.0 + 0.5 * corr95.astype(np.float64) / 6.0 + 0.35 * rmax
    score = (trace + 0.5 * persist_n).astype(np.float32)
    del trace, corr95, rmax, persist_n

    # the detector's own lineament network, for the along-strike term: structure tensor of the
    # multi-family trace mask at tau 0.99 with >= 2 families agreeing
    network = (corr99 >= 2) & legal
    coh_net, strike_net, _ = RV.strike_field(network, sigma_px=4.0)
    d_deg = np.degrees(strike_net) % 180.0
    band = np.cos(np.radians(d_deg - 0.5 * (CREDITED_STRIKE_DEG[0] + CREDITED_STRIKE_DEG[1]))) ** 2
    del network, strike_net, d_deg
    log(f"[strike] detector network {int((corr99 >= 2).sum()):,} px; coherence mean "
        f"{float(coh_net[legal].mean()):.4f}, credited-band match mean "
        f"{float(band[legal].mean()):.4f}")

    oof = {v: np.load(WORK / f"oof_{v}.npy") for v in ("A", "B")}
    habitat = np.nanmax(np.stack([np.nan_to_num(oof["A"], nan=0.0),
                                  np.nan_to_num(oof["B"], nan=0.0)]), axis=0).astype(np.float32)
    del oof

    st = np.ones((3, 3), bool)
    pool2 = ndimage.binary_dilation(corr99 >= 2, st) & novel
    pool3 = ndimage.binary_dilation(corr99 >= 3, st) & novel
    del corr99

    s_star = args.budget or budget_star()
    log(f"[budget] frozen rule S* = 4|G|beta/(1-beta) = {s_star:,} px "
        f"(beta={BETA}, |G|={G_PX}); 9,945-24,152 over beta in [0.15,0.30]")

    cands = [
        dict(name="N1_trace_field", score=score, pool=None, prefilter=True,
             what="six-family corroborated trace rank + persistence, peaks over the whole novel set"),
        dict(name="N2_ridge_C2", score=score, pool=pool2, prefilter=False,
             what="the same rank, walked along the >=2-family ridge network (1-px wide)"),
        dict(name="N3_ridge_C3", score=score, pool=pool3, prefilter=False,
             what="the same rank, walked along the >=3-family ridge network"),
        dict(name="N4_strike_gated", score=score + 1.0 * coh_net * band, pool=None, prefilter=True,
             what="trace rank gated by the network's own coherence x credited-azimuth match"),
        dict(name="N5_strike_ridge", score=score + 1.0 * coh_net * band, pool=pool2, prefilter=False,
             what="N4's score walked along the >=2-family ridge network"),
        dict(name="N6_habitat", score=habitat, pool=None, prefilter=True,
             what="the two-view co-training propensity (contrast: knowledge/10 §6 says habitat != credit)"),
    ]
    rng = np.random.default_rng(SEED)
    rand_score = rng.random(valid.shape).astype(np.float32)
    cands.append(dict(name="N9_random_control", score=rand_score, pool=None, prefilter=True,
                      what="uniform random over the strictly-novel pool (the control everything is lift over)"))

    rows = []
    emissions = {}
    for c in cands:
        allowed = novel if c["pool"] is None else c["pool"]
        dots = Z.place_dots(c["score"], allowed, s_star, min_sep_px=MIN_SEP,
                            prefilter=c["prefilter"], scan_cap=4_000_000)
        got, want, seen = Z.place_dots.last_shortfall
        stats = coherence_stats(dots)
        row = dict(name=c["name"], what=c["what"], placed=got, requested=want, candidates_seen=seen,
                   pool=("ridge" if c["pool"] is not None else "field"),
                   prefilter=bool(c["prefilter"]), novel_fraction=1.0,
                   min_distance_to_prior_px=None, **stats)
        ys, xs = np.nonzero(dots)
        if ys.size:
            dpr = ndimage.distance_transform_edt(~prior_union, sampling=1.0)
            row["min_distance_to_prior_px"] = float(dpr[ys, xs].min())
            row["median_distance_to_prior_px"] = float(np.median(dpr[ys, xs]))
            dcat = edt_cat[ys, xs]
            row["min_distance_to_catalogue_m"] = float(dcat.min())
            row["median_distance_to_catalogue_m"] = float(np.median(dcat))
            del dpr, dcat
        rows.append(row)
        emissions[c["name"]] = dots
        log(f"[cand] {c['name']:18s} placed {got:6,d}/{want:,d}  coh4={stats['mean_coherence_sigma4']:.4f} "
            f"frac>0.8={stats['frac_coh_above_0.8_sigma4']:.4f} "
            f"strike={stats['dominant_strike_deg_array']:.1f}deg "
            f"in-band={stats['in_credited_band']}")
        del dots

    # the credited cloud (the champion file itself) and a mass-matched random cloud, as references
    with rasterio.open(ROOT / "data/reference/h33-2-b2-zeros.tif") as ds:
        champ = (np.nan_to_num(ds.read(1).astype(np.float32), nan=0.0) > 0) & valid
    ref_champ = coherence_stats(champ)
    rand_match = Z.place_dots(rand_score, legal, int(champ.sum()), min_sep_px=MIN_SEP,
                              prefilter=True, scan_cap=4_000_000)
    ref_rand = coherence_stats(rand_match)
    log(f"[ref] champion cloud  coh4={ref_champ['mean_coherence_sigma4']:.4f} "
        f"frac>0.8={ref_champ['frac_coh_above_0.8_sigma4']:.4f} "
        f"strike={ref_champ['dominant_strike_deg_array']:.1f}deg")
    log(f"[ref] random-matched  coh4={ref_rand['mean_coherence_sigma4']:.4f} "
        f"frac>0.8={ref_rand['frac_coh_above_0.8_sigma4']:.4f}")

    ctrl = next(r for r in rows if r["name"] == "N9_random_control")
    for r in rows:
        r["coherence_lift_over_random"] = (
            (r["mean_coherence_sigma4"] - ctrl["mean_coherence_sigma4"])
            + (r["frac_coh_above_0.8_sigma4"] - ctrl["frac_coh_above_0.8_sigma4"]))
        r["coherence_lift_over_random_sigma10"] = (
            r["mean_coherence_sigma10"] - ctrl["mean_coherence_sigma10"])
    ranked = sorted((r for r in rows if r["name"] != "N9_random_control"),
                    key=lambda r: -r["coherence_lift_over_random"])
    in_band = [r for r in ranked if r["in_credited_band"]]
    chosen = in_band[0] if in_band else ranked[0]
    log(f"[rule R3] chosen {chosen['name']} (coherence lift {chosen['coherence_lift_over_random']:+.4f}, "
        f"strike {chosen['dominant_strike_deg_array']:.1f} deg, in credited band "
        f"{chosen['in_credited_band']}); {len(in_band)}/{len(ranked)} candidates inside the band")

    # all three bars, because the brief's stated target is rank 7 and not the top (IR-R5-005)
    proj = {f"{t:g}": win_probability(s_star, t) for t in (CHAMPION, BOARD, BOARD_TOP)}
    proj_curve = []
    for s in (5_000, 10_000, budget_star(), 25_000, 40_000, 60_000, 100_000, 166_000):
        wc, wb = win_probability(s, CHAMPION), win_probability(s, BOARD)
        wt = win_probability(s, BOARD_TOP)
        proj_curve.append(dict(budget=s, p_beat_champion=wc["p_win"], p_beat_board=wb["p_win"],
                               p_beat_board_top=wt["p_win"], kappa_needed_board_top=wt["kappa_needed"],
                               kappa_needed_champion=wc["kappa_needed"],
                               kappa_needed_board=wb["kappa_needed"],
                               dti_at_kappa1=wc["dti_at_kappa1"],
                               dti_at_kappa_lo=wc["dti_at_kappa_lo"],
                               dti_at_kappa_hi=wc["dti_at_kappa_hi"]))
    log(f"[prior] kappa ~ U{KAPPA} on T = kappa*{C_FIELD}*S^{BETA}: "
        f"P(DTI>{CHAMPION}) = {proj[f'{CHAMPION:g}']['p_win']:.3f}, "
        f"P(DTI>{BOARD}) = {proj[f'{BOARD:g}']['p_win']:.3f}, "
        f"P(DTI>{BOARD_TOP}) = {proj[f'{BOARD_TOP:g}']['p_win']:.3f}; "
        f"DTI at kappa=1 is {proj[f'{CHAMPION:g}']['dti_at_kappa1']:.4f}, "
        f"at kappa={KAPPA[0]} {proj[f'{CHAMPION:g}']['dti_at_kappa_lo']:.4f}, "
        f"at kappa={KAPPA[1]} {proj[f'{CHAMPION:g}']['dti_at_kappa_hi']:.4f}")

    receipt = dict(
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        frozen_rules=dict(
            R1_strict_novelty=f"no pixel emitted by any of {len(prior_paths)} accessible build-time priors "
                              f"(union {int(prior_union.sum()):,} px); none within {CORRIDOR_M:g} m "
                              "of the local known-fault mask (repository rule, not an organizer scoring buffer)",
            R2_budget=(f"conditional scenario S*=4|G|beta/(1-beta), beta={BETA}; uses legacy "
                       f"|G|={G_PX:g}, which is not established from hidden truth"),
            R3_choice="largest coherence lift over the random control, subject to the dominant "
                      "strike falling in the credited band 095-115 deg (array convention)",
            R4_prior=f"kappa ~ U{KAPPA} on T(S) = kappa*471.6*S^0.2284"),
        budget_star=s_star, budget_sensitivity=dict(
            beta_0p15=budget_star(beta=0.15), beta_0p2284=budget_star(),
            beta_0p30=budget_star(beta=0.30)),
        min_sep_px=MIN_SEP,
        assay_not_used_as_gate=(
            "the whole-component localisation assay is reported in evidence/r5_budget.json but does "
            "not choose this emission: knowledge/10 §5 disqualified it (Spearman -0.1045, p=0.734, "
            "n=13) and this round reproduced the inversion -- on that instrument the champion "
            "family's habitat field scores 0.0003 against uniform random 0.0275, while on the "
            "organiser's board the same family is the best of the 13"),
        candidates=rows, ranked_by_rule=[r["name"] for r in ranked],
        reference_champion_cloud=ref_champ, reference_random_matched=ref_rand,
        chosen=chosen["name"], chosen_row=chosen,
        projection=proj, projection_budget_curve=proj_curve,
        seconds=time.time() - t0)

    if args.dry_run:
        log("[dry-run] no raster written")
        (EVID / "r5_novel_candidates.json").write_text(json.dumps(receipt, indent=1))
        return 0

    dots = emissions[chosen["name"]]
    emission = np.zeros(valid.shape, np.float32)
    emission[dots] = 1.0
    got = int(emission.sum())
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    name = f"gems52-r5-novel-{chosen['name'].lower()}-{got}px-{stamp}"
    SUB.mkdir(exist_ok=True)
    tif = SUB / f"{name}.tif"
    info = GRID.write_geotiff(tif, emission)
    h8 = info["sha256"][:8]
    final = SUB / f"{name}-{h8}-zeros.tif"
    tif.rename(final)
    log(f"[emit] wrote {final.name} ({info['bytes']:,} bytes) px={got} "
        f"unique_values={info['unique_values']} min={info['min']} max={info['max']} "
        f"finite={info['finite_pixels']}/{info['height'] * info['width']} nodata={info['nodata_repr']}")

    priors = G.find_priors([ROOT / "data/scored", ROOT / "data/reference", ROOT / "submission",
                            ROOT / "docs/downloads"], exclude=final)
    fmt = G.format_report(final, ROOT / "data/sample_submission.tif", footprint=valid)
    uniq = G.uniqueness_report(emission, priors)
    d_emit = edt_cat[emission > 0]
    receipt.update(
        name=final.stem, tif=str(final.relative_to(ROOT)), bytes=info["bytes"],
        sha256=info["sha256"], emitted_px=got,
        values=dict(min=info["min"], max=info["max"], unique=info["unique_values"],
                    positive_pixels=info["positive_pixels"],
                    finite_pixels=info["finite_pixels"],
                    nan_or_inf=info["height"] * info["width"] - info["finite_pixels"],
                    all_finite=bool(info["finite_pixels"] == info["height"] * info["width"]),
                    in_unit_interval=bool(info["min"] >= 0.0 and info["max"] <= 1.0),
                    nodata_tag=info["nodata_repr"], dtype=info["dtype"],
                    crs=info["crs"], transform=info["transform"]),
        format_gate=dict(ok=fmt["ok"], problems=fmt["problems"]),
        uniqueness_gate=dict(ok=uniq["ok"], pattern_unique=uniq["canonical_pattern_unique"],
                             n_priors_checked=uniq["n_priors_checked"],
                             novel_fraction=uniq["novel_fraction"],
                             equals_literal_prior_union=uniq["equals_literal_prior_union"],
                             relation=uniq["relation_to_union"]),
        distance_to_catalogue_m=dict(min=float(d_emit.min()) if d_emit.size else None,
                                     median=float(np.median(d_emit)) if d_emit.size else None),
        novelty=dict(novel_vs_all_repo_rasters=uniq["novel_fraction"],
                     own_builds_excluded_from_prior_scan=n_self,
                     n_repo_rasters=uniq["n_priors_checked"],
                     novel_vs_13_organiser_scored=float(
                         (emission[dots & ~scored_union].sum()) / max(int(dots.sum()), 1)),
                     union_px=uniq["union_px"], relation_to_union=uniq["relation_to_union"],
                     support_novelty_gate_ok=uniq["support_novelty_gate_ok"]),
        ok_to_download=bool(fmt["ok"] and info["finite_pixels"] == info["height"] * info["width"]
                            and info["min"] >= 0.0 and info["max"] <= 1.0),
        portal_format_valid=bool(fmt["ok"] and info["finite_pixels"] == info["height"] * info["width"]
                                 and info["min"] >= 0.0 and info["max"] <= 1.0),
        ok_to_submit=False,
        approved_for_weekly_slot=False,
        submission_eligibility="NO — not approved; a local format/uniqueness gate is not promotion evidence",
        seconds=time.time() - t0)
    for p in (EVID / "r5_novel_emission.json", DOCS / "data" / "r5_novel_emission.json",
              EVID / "r5_novel_candidates.json"):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(receipt, indent=1))
    log(f"[gate] format_ok={fmt['ok']} pattern_unique={uniq['canonical_pattern_unique']} "
        f"novel_fraction={uniq['novel_fraction']:.4f} priors_checked={uniq['n_priors_checked']} "
        f"-> OK_TO_DOWNLOAD={receipt['ok_to_download']} OK_TO_SUBMIT={receipt['ok_to_submit']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
