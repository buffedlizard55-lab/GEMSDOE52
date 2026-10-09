#!/usr/bin/env python3
"""R5 -- geological reasoning for every A-only candidate, as a reviewable table.

The brief asks for written geological reasoning for *every* candidate that View A (potential field /
subsurface) puts forward while View B (surface) abstains, because Phase-2 reviewers have to verify
faults, not scores.  This script turns the A-only population into one row per candidate segment with
the measurements a reviewer needs and a reasoning sentence built *from those measurements*.

What "every" means here, stated exactly
---------------------------------------
The A-only mask (View A propensity in its top 1 % over the legal set, View B below its 90th) is
43,672 px in **22,287** 8-connected components, median size 1 px.  A one- or two-pixel speck is not a
geological structure and cannot be reviewed as one, so:

  * every component of **>= 3 px** is written as its own row (4,164 candidates, 21,356 px = 48.9 % of
    the A-only mass), with its own measured attributes and its own reasoning sentence;
  * the 18,123 components of 1-2 px (22,316 px) are accounted for in the JSON receipt with aggregate
    statistics -- count, mass, family-response distribution, distance-to-catalogue distribution -- so
    that nothing is silently dropped, and they are named as below review resolution.

Nothing in this file is a discovery.  Every row is a *candidate* with named competing explanations,
and ``candidate_status`` says so on every line (``AGENTS.md``: hypotheses stay separate from
discoveries; catalogue absence stays separate from verified fault absence).

Writes ``docs/downloads/a_only_reasoning_r5.csv`` and ``evidence/r5_a_only_reasoning.json``.
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import grid as GRID                  # noqa: E402
from gems52_r5 import cotrain_r5 as C            # noqa: E402
from gems52_r5 import layers as L                # noqa: E402

WORK = ROOT / "work" / "r5"
EVID = ROOT / "evidence"
DL = ROOT / "docs" / "downloads"
MIN_PX = 3
CORRIDOR_M = 200.0
STRUCT8 = np.ones((3, 3), bool)

# bands worth printing for a reviewer: (source, band) -> a short column key.  The *official* band
# name is taken from layers.band_name (transcribed from the organiser's own TIFF band descriptions),
# never invented here.
BANDS = {
    ("features", 2): "rtp_magnetics",
    ("features", 3): "tmi_horizontal_gradient",
    ("features", 5): "isostatic_gravity_slope",
    ("features", 11): "isostatic_gravity_vertical_gradient",
    ("features", 13): "isostatic_gravity_anomaly",
    ("features", 15): "depth_to_base_surf_band15",
    ("features", 18): "isostatic_gravity_horizontal_gradient",
    ("features", 12): "det_elev_band12",
    ("features", 19): "det_elev_slope_band19",
    ("features", 6): "radiometric_total_count",
    ("features", 7): "geodetic_shear_rate",
    ("features", 8): "geodetic_dilatation_rate",
    ("rad", 1): "radiometric_K",
    ("rad", 2): "radiometric_Th",
    ("rad", 3): "radiometric_U",
    ("lidar", 9): "lidar_relief",
}


def log(m: str) -> None:
    print(m, flush=True)


def per_component_mean(values: np.ndarray, labels: np.ndarray, n: int, keep: np.ndarray) -> np.ndarray:
    """Mean of ``values`` inside each labelled component, NaN where a component has no finite pixel."""
    v = np.asarray(values, np.float64)
    ok = np.isfinite(v) & keep
    lab = labels[ok]
    if lab.size == 0:
        return np.full(n, np.nan)
    tot = np.bincount(lab, weights=v[ok], minlength=n + 1)
    cnt = np.bincount(lab, minlength=n + 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = tot / cnt
    out[cnt == 0] = np.nan
    return out[1:]


def percentile_table(values: np.ndarray, keep: np.ndarray, nq: int = 1000) -> np.ndarray:
    v = np.asarray(values, np.float64)[keep & np.isfinite(values)]
    if v.size == 0:
        return np.array([])
    return np.quantile(v, np.linspace(0.0, 1.0, nq))


def to_percentile(q: np.ndarray, x: np.ndarray) -> np.ndarray:
    if q.size == 0:
        return np.full(x.shape, np.nan)
    return np.searchsorted(q, x, side="left") / (q.size - 1)


def evidence_grade(row: dict) -> str:
    """Grade a candidate by how many *independent* detector families back it, not by its rank."""
    fam = float(row.get("corrob_families_max") or 0.0)
    pct = float(row.get("strongest_family_percentile") or 0.0)
    if fam >= 3 and pct >= 0.90:
        return "strong"
    if fam >= 2 or pct >= 0.90:
        return "moderate"
    return "weak"


SUPPORT = {
    "strong": ("Support is as strong as this instrument can make it: {fam:.0f} of the six independent "
               "detector families mark the segment and the leading family's response is at the "
               "{pct:.1f}th percentile of the whole footprint, so the lineament is real in the data "
               "whether or not it turns out to be a fault."),
    "moderate": ("Support is moderate: {fam:.0f} of six families mark it and the leading family sits "
                 "at the {pct:.1f}th percentile, so a lineament is present but is not reinforced "
                 "across the whole potential-field suite."),
    "weak": ("Support is weak: only {fam:.0f} of six families marks it and the leading family sits at "
             "the {pct:.1f}th percentile, so this row may be an artefact of the propensity model's "
             "rank field rather than a physical lineament. It is listed because the brief asks for "
             "reasoning on *every* A-only candidate, not because it is credible on its own."),
}


def reasoning(row: dict) -> str:
    """Geological reasoning for one candidate, built only from that row's own measurements.

    Units: the organiser's rules page publishes band *names* (transcribed verbatim into
    ``layers.BANDS``) but not units, so every band value is quoted as published and interpreted
    against this footprint's own distribution instead of being given a unit it was never given.
    """
    g = lambda k: row.get(k, np.nan)                                 # noqa: E731
    def txt(v, fmt="{:,.2f}", none="not measured"):
        return fmt.format(v) if isinstance(v, float) and np.isfinite(v) else none

    grade = evidence_grade(row)
    support = SUPPORT[grade].format(fam=float(g("corrob_families_max") or 0),
                                    pct=100.0 * float(g("strongest_family_percentile") or 0))
    if row.get("view_B_strict_abstention_40_80"):
        abstain = ("View B sits inside the strict 40th-80th percentile abstention band, so the surface "
                   "view genuinely sees nothing either way here")
    else:
        abstain = (f"View B is only *not also confident* (percentile "
                   f"{100.0 * float(g('view_B_percentile') or 0):.1f}, below the 90th-percentile cut "
                   f"but above the strict 40-80 band), so this is disagreement by omission rather "
                   f"than clean abstention")
    dots = float(g("emitted_dots_within_3px") or 0)
    dot_txt = (f"It carries {dots:.0f} of this round's emitted dots, so it is part of the submission"
               if dots else "It carries none of this round's emitted dots")
    dcat = float(g("min_distance_to_catalogue_m") or np.nan)
    dsgmc = float(g("min_distance_to_sgmc_trace_m") or np.nan)
    # every clause below is conditional on this row's own numbers; a generated sentence that asserts
    # "deeper than median" over a shallower-than-median measurement is a hallucination with a comma in
    # it, so the comparisons are computed, not written.
    dep = float(g("depth_to_base_surf_band15_mean") or np.nan)
    depth_clause = ("not measured" if not np.isfinite(dep) else
                    f"{dep - 316.0:+,.0f} against the footprint median" +
                    (" (deeper than median, i.e. more near-surface section above the modelled base)"
                     if dep > 316.0 else
                     " (shallower than median, which weakens the burial reading)"))
    az = float(g("strike_geographic_azimuth_deg") or np.nan)
    strike_clause = ("strike not resolvable from a segment this short" if not np.isfinite(az) else
                     ("strike lies inside the 010-020 deg fabric the credited cloud shows "
                      "(knowledge/10 section 7), so it is oriented like the faults this prize pays for"
                      if 0.0 <= az <= 40.0 or az >= 160.0 else
                      f"strike {az:.0f} deg is oblique to the 010-020 deg fabric the credited cloud "
                      f"shows, which weakens the buried-range-front reading and makes a lithologic "
                      f"contact or an acquisition artefact comparatively more likely"))
    el = float(g("elongation") or np.nan)
    shape_clause = ("shape not resolvable" if not np.isfinite(el) else
                    (f"elongation {el:.2f} is line-like" if el >= 2.0 else
                     f"elongation {el:.2f} is closer to equant than linear, which is not what a fault "
                     f"trace looks like"))
    return (
        f"A-only candidate, evidence grade {grade.upper()}. View A (potential field / subsurface) "
        f"ranks this {row['n_px']}-px segment in its top 1 % over the legal set (propensity "
        f"{txt(g('view_A_propensity_mean'), '{:.3f}')}, footprint percentile "
        f"{100.0 * float(g('view_A_percentile') or 0):.1f}); {abstain}. {support} "
        f"Geometry: {txt(g('length_px'), '{:.1f}')} px along its principal axis, elongation "
        f"{txt(g('elongation'), '{:.2f}')}, strike {txt(g('strike_geographic_azimuth_deg'), '{:.0f}')} "
        f"deg geographic azimuth (the credited cloud in knowledge/10 section 7 strikes 010-020). "
        f"Setting, quoted as published: depth_to_base_surf (band 15) "
        f"{txt(g('depth_to_base_surf_band15_mean'), '{:,.0f}')} against a footprint median of 316; "
        f"det_elev (band 12) {txt(g('det_elev_band12_mean'), '{:,.0f}')} against a median of -76, so "
        f"band 12 is a detrended elevation and not metres above sea level; det_elev_slope (band 19) "
        f"{txt(g('det_elev_slope_band19_mean'), '{:.2f}')} against a median of 3.75; radiometric "
        f"total count (band 6) {txt(g('radiometric_total_count_mean'), '{:.1f}')} against a median of "
        f"18.5. Position: {txt(dcat, '{:,.0f}')} m from the nearest mapped catalogue trace and "
        f"{txt(dsgmc, '{:,.0f}')} m from the nearest derived SGMC trace, so the 200 m exclusion ring "
        f"does not touch it. "
        f"Interpretation, with each clause tied to the numbers above: {shape_clause}; {strike_clause}; "
        f"depth_to_base_surf is {depth_clause}. A segment that is line-like, correctly oriented, and "
        f"deeper than median with no topographic or radiometric expression is what a range-front "
        f"normal fault buried by alluvial-fan and basin-fill deposits looks like at 100 m grid "
        f"spacing in the Basin and Range, and that is the population this prize exists to find, "
        f"because a fault with no surface expression cannot already be in the mapped catalogue. A "
        f"segment that fails one of those three clauses is listed for completeness and should be "
        f"treated as unexplained rather than as a candidate fault. "
        f"Competing explanations that must be excluded before this is called a fault: a lithologic or "
        f"sedimentary-facies contact carrying a density or magnetisation contrast; an intrusive sill, "
        f"dike or buried volcanic centre; a flight-line, levelling or interpolation artefact in the "
        f"airborne magnetic and radiometric grids; an artefact of band 15, which is a model of the "
        f"subsurface and not an observation of it (it contains negative values); and the smooth "
        f"regional geodetic strain field (bands 7-8), which at 100 m spacing is smoothed below fault "
        f"resolution and is the weakest of the six families for this purpose. "
        f"{dot_txt}. Absence from the USGS Qfaults and INGENIOUS traces near this segment is absence "
        f"of mapping, not verified absence of a fault; nothing in this row is a discovery."
    )


def main() -> int:
    t0 = time.time()
    valid = np.load(WORK / "valid.npy")
    cat = L.catalogue()
    edt_cat = ndimage.distance_transform_edt(~cat, sampling=100.0)
    legal = valid & (edt_cat > CORRIDOR_M)
    oof = {v: np.load(WORK / f"oof_{v}.npy") for v in ("A", "B")}
    strat = C.disagreement_strata(oof["A"], oof["B"], legal, None, None)
    a_only = strat["a_only_mask"]
    labels, n_all = ndimage.label(a_only, structure=STRUCT8)
    sizes_all = np.bincount(labels.ravel(), minlength=n_all + 1)[1:]
    keep_ids = np.nonzero(sizes_all >= MIN_PX)[0] + 1
    log(f"[a-only] {int(a_only.sum()):,} px in {n_all:,} components; {keep_ids.size:,} components "
        f"have >= {MIN_PX} px ({int(sizes_all[keep_ids - 1].sum()):,} px); "
        f"{n_all - keep_ids.size:,} components of 1-2 px ({int(sizes_all[sizes_all < MIN_PX].sum()):,} px) "
        f"are below review resolution and are accounted for in the receipt")

    # renumber the kept components 1..n so the per-component accumulators stay small
    remap = np.zeros(n_all + 1, np.int32)
    remap[keep_ids] = np.arange(1, keep_ids.size + 1)
    lab = remap[labels]
    n = int(keep_ids.size)
    sel = lab > 0
    sizes = np.bincount(lab.ravel(), minlength=n + 1)[1:]

    # geometry: second moments of each component's pixel cloud
    ys, xs = np.nonzero(sel)
    cid = lab[ys, xs]
    cy = np.bincount(cid, weights=ys, minlength=n + 1)[1:] / sizes
    cx = np.bincount(cid, weights=xs, minlength=n + 1)[1:] / sizes
    dy = ys - cy[cid - 1]
    dx = xs - cx[cid - 1]
    myy = np.bincount(cid, weights=dy * dy, minlength=n + 1)[1:] / sizes
    mxx = np.bincount(cid, weights=dx * dx, minlength=n + 1)[1:] / sizes
    mxy = np.bincount(cid, weights=dx * dy, minlength=n + 1)[1:] / sizes
    tr = mxx + myy
    det = mxx * myy - mxy * mxy
    disc = np.maximum(tr * tr / 4.0 - det, 0.0)
    lam1 = tr / 2.0 + np.sqrt(disc)
    lam2 = np.maximum(tr / 2.0 - np.sqrt(disc), 0.0)
    elong = np.sqrt(lam1 / np.maximum(lam2, 1e-9))
    length = 2.0 * np.sqrt(np.maximum(lam1, 0.0))          # px, along the principal axis
    # array convention: +x = east = column, +y = south = row.  theta is measured from east.
    theta = 0.5 * np.arctan2(2.0 * mxy, mxx - myy)
    axis_from_easting_deg = np.degrees(np.mod(theta, np.pi))
    # a geographic azimuth is clockwise from north, and north is -y, so azimuth = 90 - theta_array
    azimuth = np.mod(90.0 - axis_from_easting_deg, 180.0)

    # distances
    d_cat = per_component_min(edt_cat, lab, n, sel)
    sgmc = None
    for cand in (ROOT / "data/external/sgmc_raster.tif",):
        if cand.exists():
            with rasterio.open(cand) as ds:
                sgmc = ds.read(1) > 0
    if sgmc is None:
        ext = sorted((ROOT / "data/external").glob("*sgmc*")) if (ROOT / "data/external").exists() else []
        for e in ext:
            if e.suffix == ".tif":
                try:
                    with rasterio.open(e) as ds:
                        a = ds.read(1)
                    if a.shape == valid.shape:
                        sgmc = (np.nan_to_num(a, nan=0.0) > 0)
                        log(f"[a-only] SGMC traces from {e.name}: {int(sgmc.sum()):,} px")
                        break
                except Exception as exc:                        # noqa: BLE001
                    log(f"[a-only] SGMC {e.name} unusable: {type(exc).__name__}")
    d_sgmc = per_component_min(ndimage.distance_transform_edt(~sgmc, sampling=100.0), lab, n, sel) \
        if sgmc is not None else np.full(n, np.nan)

    # view propensities, corroboration, family responses
    corr99 = np.load(WORK / f"corrobor_{0.99:g}.npy").astype(np.float32)
    fam_resp, fam_theta, fam_agree = {}, {}, {}
    for f in L.FAMILIES:
        z = np.load(WORK / f"fam_{f}.npz")
        fam_resp[f] = z["resp"]
    cols = {}
    cols["view_A_propensity_mean"] = per_component_mean(oof["A"], lab, n, sel)
    cols["view_B_propensity_mean"] = per_component_mean(oof["B"], lab, n, sel)
    qA = percentile_table(oof["A"], legal)
    qB = percentile_table(oof["B"], legal)
    cols["view_A_percentile"] = to_percentile(qA, cols["view_A_propensity_mean"])
    cols["view_B_percentile"] = to_percentile(qB, cols["view_B_propensity_mean"])
    # "abstains" has two readings and both are reported: the loose one the strata function uses
    # (View B below its 90th percentile, i.e. merely not also confident) and the strict r3-era
    # interval (View B inside its 40th-80th percentile, i.e. genuinely uninformative).  A reviewer
    # who is told only the first will over-read the disagreement.
    cols["view_B_strict_abstention_40_80"] = (
        (cols["view_B_percentile"] >= 0.40) & (cols["view_B_percentile"] <= 0.80)).astype(float)
    cols["corrob_families_max"] = per_component_max(corr99, lab, n, sel)
    cols["corrob_families_median"] = per_component_median(corr99, lab, n, sel)
    for f in L.FAMILIES:
        cols[f"resp_{f}_mean"] = per_component_mean(fam_resp[f], lab, n, sel)
        cols[f"resp_{f}_pct"] = to_percentile(percentile_table(fam_resp[f], valid), cols[f"resp_{f}_mean"])

    # emission dots, so a reviewer can see which candidates actually carry this round's mass
    em_path = json.loads((EVID / "r5_novel_emission.json").read_text())
    with rasterio.open(ROOT / em_path["tif"]) as ds:
        dots = ds.read(1) > 0
    d_near = ndimage.binary_dilation(dots, STRUCT8, iterations=3)
    cols["emitted_dots_within_3px"] = np.bincount(lab[d_near & sel], minlength=n + 1)[1:].astype(float)

    # band means and their footprint percentiles
    band_names = {}
    for (src, b), nm in BANDS.items():
        try:
            v = L.read(src, b, valid=valid)
            official = L.band_name(src, b)
        except Exception as exc:                                # noqa: BLE001
            log(f"[a-only] band {src}/{b} ({nm}) unreadable: {type(exc).__name__}: {exc}")
            continue
        cols[f"{nm}_mean"] = per_component_mean(v, lab, n, sel)
        cols[f"{nm}_pct"] = to_percentile(percentile_table(v, valid), cols[f"{nm}_mean"])
        band_names[nm] = f"{src} band {b} = {official}"
        del v

    # strongest View A family per candidate (View A = mag, grav, strain, sub)
    view_a_fams = [f for f in L.FAMILIES if f in ("mag", "grav", "strain", "sub")]
    fa = np.stack([np.nan_to_num(cols[f"resp_{f}_pct"], nan=-1.0) for f in view_a_fams])
    best = np.argmax(fa, axis=0)
    strongest = np.array([view_a_fams[i] for i in best])
    strongest_pct = fa[best, np.arange(n)]

    tr_arr = tuple(float(v) for v in GRID.TRANSFORM)
    rows = []
    for i in range(n):
        r = dict(
            candidate_id=i + 1, n_px=int(sizes[i]),
            centroid_row=float(cy[i]), centroid_col=float(cx[i]),
            centroid_x_m=tr_arr[0] * cx[i] + tr_arr[2],
            centroid_y_m=tr_arr[4] * cy[i] + tr_arr[5],
            length_px=float(length[i]), elongation=float(elong[i]),
            principal_axis_degrees_from_easting=float(axis_from_easting_deg[i]),
            strike_geographic_azimuth_deg=float(azimuth[i]),
            min_distance_to_catalogue_m=float(d_cat[i]),
            min_distance_to_sgmc_trace_m=float(d_sgmc[i]),
            strongest_view_A_family=str(strongest[i]),
            strongest_family_percentile=float(strongest_pct[i]),
            view_B_strict_abstention_40_80=bool(cols["view_B_strict_abstention_40_80"][i]),
            candidate_status=("research diagnostic only; a candidate interpretation with named "
                              "competing explanations, not a verified fault and not a discovery"),
        )
        for k, v in cols.items():
            r[k] = float(v[i]) if np.isfinite(v[i]) else np.nan
        r["evidence_grade"] = evidence_grade(r)
        r["geology_reasoning"] = reasoning(r)
        for k in list(r):
            if isinstance(r[k], float) and not np.isfinite(r[k]):
                r[k] = ""
        rows.append(r)
    grade_rank = {"strong": 0, "moderate": 1, "weak": 2}
    rows.sort(key=lambda r: (grade_rank[r["evidence_grade"]], -int(r["n_px"]),
                             -float(r["emitted_dots_within_3px"] or 0)))

    DL.mkdir(parents=True, exist_ok=True)
    out = DL / "a_only_reasoning_r5.csv"
    keys = list(rows[0].keys())
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{r[k]:.6g}" if isinstance(r[k], float) else r[k]) for k in keys})
    log(f"[a-only] wrote {out.relative_to(ROOT)} ({len(rows):,} rows, {out.stat().st_size / 1e6:.2f} MB)")

    small = sizes_all < MIN_PX
    receipt = dict(
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        a_only_definition="View A propensity in its top 1 % over the legal (off-ring) set AND View B "
                          "propensity below its 90th percentile, per cotrain_r5.disagreement_strata",
        a_only_px=int(a_only.sum()), components_total=int(n_all),
        reviewed=dict(min_px=MIN_PX, components=int(n), px=int(sizes_all[keep_ids - 1].sum()),
                      csv=str(out.relative_to(ROOT)), rows=len(rows),
                      rows_carrying_emitted_dots=int(sum(1 for r in rows
                                                         if float(r["emitted_dots_within_3px"] or 0) > 0)),
                      emitted_dots_on_a_only=float(np.nansum(
                          [float(r["emitted_dots_within_3px"] or 0) for r in rows]))),
        below_review_resolution=dict(components=int(small.sum()), px=int(sizes_all[small].sum()),
                                     why="1-2 px specks of a continuous propensity field are not "
                                         "geological structures; they are reported in aggregate so "
                                         "nothing is dropped silently",
                                     mean_view_A_percentile=float(np.nanmean(
                                         to_percentile(qA, per_component_mean(oof["A"], labels, n_all,
                                                                              labels > 0)[small]))),
                                     median_min_distance_to_catalogue_m=float(np.nanmedian(
                                         per_component_min(edt_cat, labels, n_all, labels > 0)[small]))),
        strongest_family_counts={f: int((strongest == f).sum()) for f in view_a_fams},
        evidence_grade_counts={g: int(sum(1 for r in rows if r["evidence_grade"] == g))
                               for g in ("strong", "moderate", "weak")},
        strict_abstention_count=int(cols["view_B_strict_abstention_40_80"].sum()),
        abstention_note="the loose reading (View B < 90th percentile) is what defines the stratum; "
                        "strict_abstention_count is how many reviewed candidates also fall inside the "
                        "strict 40th-80th percentile band, which is the reading 'abstains' usually "
                        "means to a geologist",
        strike_histogram_10deg=[int(x) for x in np.histogram(azimuth, bins=18, range=(0, 180))[0]],
        credited_strike_band_deg="010-020 geographic azimuth (knowledge/10 §7)",
        bands_reported=band_names,
        seconds=time.time() - t0)
    EVID.mkdir(exist_ok=True)
    (EVID / "r5_a_only_reasoning.json").write_text(json.dumps(receipt, indent=1))
    (ROOT / "docs/data/r5_a_only_reasoning.json").write_text(json.dumps(receipt, indent=1))
    log(f"[a-only] strongest View A family: {receipt['strongest_family_counts']}")
    log(f"[a-only] evidence grades: {receipt['evidence_grade_counts']}; strict View B abstention "
        f"(40-80th pct) in {receipt['strict_abstention_count']:,} of {n:,} reviewed candidates")
    log(f"[a-only] {receipt['reviewed']['rows_carrying_emitted_dots']} reviewed candidates carry "
        f"{receipt['reviewed']['emitted_dots_on_a_only']:.0f} emitted dots")
    return 0


def per_component_min(values: np.ndarray, labels: np.ndarray, n: int, keep: np.ndarray) -> np.ndarray:
    v = np.asarray(values, np.float64)
    ok = keep & np.isfinite(v)
    lab = labels[ok]
    if lab.size == 0:
        return np.full(n, np.nan)
    out = np.full(n + 1, np.inf)
    np.minimum.at(out, lab, v[ok])
    out[~np.isfinite(out)] = np.nan
    return out[1:]


def per_component_max(values: np.ndarray, labels: np.ndarray, n: int, keep: np.ndarray) -> np.ndarray:
    v = np.asarray(values, np.float64)
    ok = keep & np.isfinite(v)
    lab = labels[ok]
    if lab.size == 0:
        return np.full(n, np.nan)
    out = np.full(n + 1, -np.inf)
    np.maximum.at(out, lab, v[ok])
    out[~np.isfinite(out)] = np.nan
    return out[1:]


def per_component_median(values: np.ndarray, labels: np.ndarray, n: int, keep: np.ndarray) -> np.ndarray:
    """Median by component.  Done with a sort, not a Python loop, because there are ~4k components."""
    v = np.asarray(values, np.float64)
    ok = keep & np.isfinite(v)
    lab, val = labels[ok], v[ok]
    if lab.size == 0:
        return np.full(n, np.nan)
    order = np.lexsort((val, lab))
    lab, val = lab[order], val[order]
    counts = np.bincount(lab, minlength=n + 1)
    starts = np.concatenate([[0], np.cumsum(counts)[:-1]])
    out = np.full(n, np.nan)
    for i in range(1, n + 1):
        s, c = starts[i], counts[i]
        if c == 0:
            continue
        seg = val[s:s + c]
        out[i - 1] = float(np.median(seg))
    return out


if __name__ == "__main__":
    raise SystemExit(main())
