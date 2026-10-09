#!/usr/bin/env python3
"""H61 forensics: re-derive the organiser-score algebra from bytes, with two repairs.

This is the shared forensic instrument for every round that reasons about *what the
organiser's published scores imply*.  It replaces the H60 accounting
(``scripts/h60_forensics.py``) on two points that the bytes settle, and it reports the
rigorous identification interval for ``|G|`` instead of a single assumption-dependent
point value.

Repair 1 -- masked support ``S``.
    DrivenData staff (community thread 11516, posts #2 and #4, quoted in
    ``src/gems52/holdout.py``): pixels on known USGS/INGENIOUS faults are *masked out of
    evaluation*, pixel-exactly, so they neither earn credit nor pay the false-positive
    tax.  H60 nevertheless charged every file its raw positive count ``S_raw``, including
    catalogue pixels.  That is internally inconsistent, and the bytes prove it:
    ``8GEMSDOE_Hedge-v2_submission.tif`` and ``gemsdoe-ens12-adopted-7f00890a.tif`` have
    *identical* off-catalogue support (verified here pixel-for-pixel) and both report
    0.1563, yet raw-``S`` accounting gives them different credit (8,873.5 vs 7,168.8).
    Masked accounting gives both 6,967.0.  Every number below is therefore reported twice:
    ``S_raw`` (H60 convention) and ``S_masked`` (organiser-consistent).

Repair 2 -- ``|G|`` is an interval, not a measurement.
    H60 states ``|G| = 14,088.7 px`` as measured, with a +/-70 px rounding sensitivity.
    In fact the score equations are 13 equations in 14 unknowns (13 credits plus ``|G|``),
    so ``|G|`` is only *set-identified*.  Two rigorous constraint families bound it:

      (a) ``T_i <= |G|`` for every file, because TPw cannot exceed the number of truth
          pixels: ``|G| >= 0.2*score_i*S_i / (1 - 0.8*score_i)``.
      (b) max-cover monotonicity on every *nested* pair ``X subset Y``: ``T_X <= T_Y``,
          which for ``score_X > score_Y`` gives an upper bound on ``|G|``.

    The point value 14,088.7 is what (b) yields at its extreme, i.e. under the extra
    assumption that the 6,436 px the champion deleted earn *exactly zero* credit.  That
    assumption is plausible but unproven, so this script publishes the interval and the
    sensitivity of ``|G|`` to the deleted-ring credit ``delta``.

Repair 3 (diagnostic, not a repair) -- attribution hash-links.
    The owner's score list embeds a 12-hex token in most filenames.  For some files that
    token is a prefix of the file's SHA-256 (a real hash-link); for others it is not.
    Which is which is measured here under six hash conventions, because the champion's
    0.2778 attribution -- the single input the whole ``|G|`` story rests on -- is only as
    strong as its link to bytes.

Nothing here is an organiser score.  All inputs are the SHA-256-pinned mirrors restored by
``scripts/restore_data.py``; pins prove mirror consistency, not organiser authentication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]

# Owner-reported scores, keyed by manifest id.  Provenance class is decided by measurement
# below (hash-linked vs filename-only), never asserted here.
REPORTED = {
    "ref_h33_2_b2": (0.2778, "h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros", "e5eb6e7e"),
    "scored_d28_unscored": (0.2600, "d28-poisson300m-offcat-44090-20261003T233156Z-91eae1ca", "91eae1ca"),
    "scored_d15_scored": (0.2477, "h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan", "989f5950"),
    "scored_gems27_tgc_v2_d15": (0.2449, "topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan", "5512495c"),
    "scored_h19_5": (0.1922, "h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan", "e27054cf"),
    "scored_h19_4": (0.1894, "h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan", "691e4dfa"),
    "scored_h16_1": (0.1855, "h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan", "df20f65e"),
    "calib_gems10-h28-dotted-ridge-20260928T0202562": (
        0.1839, "h28-dotted-ridge-20260928T020256236880Z-6452ae1d00", "6452ae1d"),
    "calib_8GEMSDOE_Hedge-v2_submission": (0.1563, "Hedge-v2_submission", ""),
    "calib_gemsdoe-ens12-adopted-7f00890a": (
        0.1563, "gems-submission-20260925T001403Z-7f00890a", "7f00890a"),
    "calib_gems10-h25-ctx-ridge-20260927T2329477041": (
        0.1280, "H25-ctx-ridge-20260927T232947704150Z-6452ae1d00", "6452ae1d"),
    "calib_13gems_20261001_r13-lattice-s5_v2_nan-ou": (
        0.0904, "20261001_r13-lattice-s5_v2_nan-outside", ""),
    "calib_gemsdoe9-PLACEHOLDER-2314b599": (0.0107, "2314b599", "2314b599"),
}
ALPHA, BETA = 0.2, 0.8
CMAX = 3.0          # exact credit of one dot on a straight 1-px trace: 1 + 2*(2/3) + 2*(1/3)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_variants(path: Path, arr: np.ndarray) -> dict[str, str]:
    """Six identity conventions, so a filename token can be tested rather than assumed."""
    finite = np.isfinite(arr)
    zeroed = np.where(finite, arr, 0.0).astype(np.float32)
    support = (np.nan_to_num(arr, nan=0.0) > 0).astype(np.uint8)
    raw = path.read_bytes()
    return {
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "file_sha1": hashlib.sha1(raw).hexdigest(),
        "file_md5": hashlib.md5(raw).hexdigest(),
        "decoded_f32_nan0_sha256": hashlib.sha256(np.ascontiguousarray(zeroed).tobytes()).hexdigest(),
        "support_u8_sha256": hashlib.sha256(np.ascontiguousarray(support).tobytes()).hexdigest(),
        "support_bool_sha256": hashlib.sha256(
            np.ascontiguousarray(support.astype(bool)).tobytes()).hexdigest(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="evidence/h61_forensics.json")
    ap.add_argument("--docs-out", default="docs/data/h61_forensics.json")
    args = ap.parse_args()

    data = ROOT / args.data
    manifest = json.loads((ROOT / "registry/data_manifest.json").read_text())
    pins = {f["id"]: f for f in manifest["files"]}

    # ---------------------------------------------------------------- grid, catalogue, eligible
    with rasterio.open(data / "sample_submission.tif") as ref:
        shape, crs, transform = ref.shape, str(ref.crs), tuple(ref.transform)[:6]
        sub = ref.read(1)
    sub_finite = np.isfinite(sub) & (sub > -1e38)
    with rasterio.open(data / "labels.tif") as ds:
        lab = ds.read(1)
        if (ds.shape, str(ds.crs), tuple(ds.transform)[:6]) != (shape, crs, transform):
            raise SystemExit("labels grid does not match sample_submission grid")
    catalogue = lab == 1
    with rasterio.open(data / "training_features.tif") as src:
        fp = None
        for b in range(1, src.count + 1):
            a = src.read(b)
            ok = np.isfinite(a) & (a > -1e38)
            fp = ok if fp is None else (fp & ok)
        descriptions = {b: src.descriptions[b - 1] for b in range(1, src.count + 1)}
    eligible = fp & sub_finite & ~catalogue       # where a submission can earn or lose credit
    grid = dict(shape=list(shape), crs=crs, transform=list(transform),
                sample_submission_finite_px=int(sub_finite.sum()),
                all_band_finite_px=int(fp.sum()),
                catalogue_px=int(catalogue.sum()),
                eligible_px=int(eligible.sum()),
                catalogue_is_subset_of_sample_finite=bool((catalogue & ~sub_finite).sum() == 0),
                sample_submission_ones_equal_catalogue=bool(((sub == 1) == catalogue).all()))
    del sub, lab, fp

    # ---------------------------------------------------------------- per-file support accounting
    files: dict[str, dict] = {}
    supports: dict[str, np.ndarray] = {}
    for fid, (score, name, token) in REPORTED.items():
        pin = pins[fid]
        path = data / pin["dest"]
        raw = sha256_file(path)
        if raw != pin["sha256"] or path.stat().st_size != pin["bytes"]:
            raise SystemExit(f"pin mismatch, refusing to reason about {fid}")
        with rasterio.open(path) as src:
            if src.count != 1 or src.shape != shape or str(src.crs) != crs \
                    or tuple(src.transform)[:6] != transform:
                raise SystemExit(f"{fid} is not on the competition grid")
            arr = src.read(1).astype(np.float32)
        finite = np.isfinite(arr)
        sup = finite & (arr > 0)
        on_cat = sup & catalogue
        off_cat = sup & ~catalogue
        variants = hash_variants(path, arr)
        linked = sorted({k for k, v in variants.items() if token and v.startswith(token)})
        files[fid] = dict(
            id=fid, dest=pin["dest"], reported_score=score, owner_name=name, name_token=token,
            sha256=raw, bytes=path.stat().st_size, hash_variants=variants,
            token_hash_linked=linked, attribution_class=(
                "HASH-LINKED-OWNER-REPORTED" if linked else
                "FILENAME-ONLY-OWNER-REPORTED" if token else "NAME-ONLY-OWNER-REPORTED"),
            nonfinite_px=int((~finite).sum()),
            unique_values=[float(v) for v in np.unique(arr[finite])][:6],
            S_raw=int(sup.sum()), S_on_catalogue=int(on_cat.sum()), S_masked=int(off_cat.sum()),
            S_outside_sample_finite=int((sup & ~sub_finite).sum()),
            min=float(arr[finite].min()), max=float(arr[finite].max()))
        supports[fid] = sup
        del arr, finite

    # ---------------------------------------------------------------- the two masked-S witnesses
    hedge, ens = ("calib_8GEMSDOE_Hedge-v2_submission", "calib_gemsdoe-ens12-adopted-7f00890a")
    off_support = {k: supports[k] & ~catalogue for k in (hedge, ens)}
    identical_off = bool((off_support[hedge] == off_support[ens]).all())

    # ---------------------------------------------------------------- nested-pair lattice
    ids = list(REPORTED)
    off_support = {k: supports[k] & ~catalogue for k in ids}
    pairs = []
    for i, x in enumerate(ids):
        for y in ids[i + 1:]:
            xi, yi = off_support[x], off_support[y]
            inter = int((xi & yi).sum())
            x_sub_y = bool((xi & ~yi).sum() == 0) and inter > 0
            y_sub_x = bool((yi & ~xi).sum() == 0) and inter > 0
            if x_sub_y or y_sub_x or inter:
                pairs.append(dict(x=x, y=y, intersection=inter, x_only=int((xi & ~yi).sum()),
                                  y_only=int((yi & ~xi).sum()),
                                  x_subset_of_y=x_sub_y, y_subset_of_x=y_sub_x,
                                  jaccard=inter / max(1, int(xi.sum() + yi.sum() - inter))))
    subset_pairs = [p for p in pairs if p["x_subset_of_y"] or p["y_subset_of_x"]]

    # ---------------------------------------------------------------- |G|: rigorous interval
    def credit(fid: str, G: float, masked: bool) -> float:
        S = files[fid]["S_masked" if masked else "S_raw"]
        return files[fid]["reported_score"] * (ALPHA * S + BETA * G)

    bounds = {}
    for masked in (True, False):
        key = "masked" if masked else "raw"
        lo = 0.0
        lo_src = None
        for fid in ids:
            s = files[fid]["reported_score"]
            S = files[fid]["S_masked" if masked else "S_raw"]
            # T_i <= G  and  T_i = s*(0.2 S + 0.8 G)  =>  G >= 0.2 s S / (1 - 0.8 s)
            need = ALPHA * s * S / (1.0 - BETA * s)
            if need > lo:
                lo, lo_src = need, fid
        hi = float("inf")
        hi_src = None
        for p in subset_pairs:
            sub, sup = (p["x"], p["y"]) if p["x_subset_of_y"] else (p["y"], p["x"])
            s_sub, s_sup = files[sub]["reported_score"], files[sup]["reported_score"]
            S_sub = files[sub]["S_masked" if masked else "S_raw"]
            S_sup = files[sup]["S_masked" if masked else "S_raw"]
            if s_sub <= s_sup:
                continue        # monotonicity is not binding in this direction
            # s_sub(0.2 S_sub + 0.8G) <= s_sup(0.2 S_sup + 0.8G), s_sub > s_sup
            num = ALPHA * (s_sup * S_sup - s_sub * S_sub)
            den = BETA * (s_sub - s_sup)
            cap = num / den
            if cap < hi:
                hi, hi_src = cap, dict(subset=sub, superset=sup, s_sub=s_sub, s_sup=s_sup)
        bounds[key] = dict(G_lower_bound=lo, G_lower_binding_file=lo_src,
                           G_upper_bound=(None if not np.isfinite(hi) else hi),
                           G_upper_binding_pair=hi_src,
                           n_nested_pairs=len(subset_pairs),
                           n_binding_nested_pairs=int(sum(
                               1 for p in subset_pairs
                               if files[(p["x"] if p["x_subset_of_y"] else p["y"])][
                                   "reported_score"] >
                               files[(p["y"] if p["x_subset_of_y"] else p["x"])][
                                   "reported_score"])))

    # The H60 point value: the champion/base nested pair with zero credit for the deleted ring.
    champ, base = "ref_h33_2_b2", "scored_d28_unscored"
    sA, sB = files[champ]["reported_score"], files[base]["reported_score"]
    SA, SB = files[champ]["S_masked"], files[base]["S_masked"]
    G_point = ALPHA * (sB * SB - sA * SA) / (BETA * (sA - sB))
    ring_px = SB - SA
    sensitivity = [dict(delta_credit=d, G_px=(ALPHA * (sB * SB - sA * SA) - d) / (BETA * (sA - sB))
                        if (BETA * (sA - sB)) else None)
                   for d in (0.0, 25.0, 50.0, 100.0, 150.0, 200.0)]
    Gref = bounds["masked"]["G_lower_bound"]
    table = {}
    for fid in ids:
        row = {}
        for tag, G in (("point", G_point), ("lower", Gref)):
            S_m, S_r = files[fid]["S_masked"], files[fid]["S_raw"]
            row[tag] = dict(G_px=G, T_masked=credit(fid, G, True), T_raw=credit(fid, G, False),
                            density_masked=credit(fid, G, True) / max(1, S_m),
                            density_raw=credit(fid, G, False) / max(1, S_r),
                            DTI_check_masked=credit(fid, G, True) / (ALPHA * S_m + BETA * G))
        table[fid] = row
    Tchamp = credit(champ, G_point, True)
    marginal_bar = {f"dti_{d:.2f}": ALPHA * d / (1 - ALPHA * d) for d in (0.20, 0.2778, 0.3195, 0.3774)}

    # ---------------------------------------------------------------- band 6 identity test
    with rasterio.open(data / "training_features.tif") as src:
        b6 = src.read(6).astype(np.float32)
        b3 = src.read(3).astype(np.float32)
        b9 = src.read(9).astype(np.float32)
        b14 = src.read(14).astype(np.float32)
    tilt_deg = np.degrees(np.arctan2(b9, np.maximum(b3, 1e-9)))
    from scipy.stats import spearmanr
    sel = eligible.copy()
    sel &= np.isfinite(b6) & np.isfinite(b3) & np.isfinite(b9)
    # subsample for speed on 2 CPUs
    rng = np.random.default_rng(61)
    idx = np.flatnonzero(sel.ravel())
    idx = idx[rng.choice(idx.size, size=min(400_000, idx.size), replace=False)]
    b6s, b3s, b9s, tilts, b14s = (a.ravel()[idx] for a in (b6, b3, b9, tilt_deg, b14))
    ext = {}
    for path, names in ((data / "external/geodawn_rad_u8.tif", None),
                        (data / "external/geodawn_extensions_u8.tif", None)):
        with rasterio.open(path) as src:
            for b in range(1, src.count + 1):
                nm = src.descriptions[b - 1] or f"{path.stem}_b{b}"
                ext[nm] = src.read(b).astype(np.float32).ravel()[idx]
    band6 = dict(
        measured_range=[float(np.nanmin(b6[eligible])), float(np.nanmax(b6[eligible]))],
        description_in_file=descriptions.get(6),
        n_sampled=int(idx.size),
        spearman_vs_tilt_deg_of_TMI=float(spearmanr(b6s, tilts).statistic),
        spearman_vs_tmi_hg=float(spearmanr(b6s, b3s).statistic),
        spearman_vs_tmi=float(spearmanr(b6s, b14s).statistic),
        spearman_vs_external={k: float(spearmanr(b6s, v).statistic) for k, v in ext.items()},
        tilt_angle_deg_range=[float(np.nanmin(tilts)), float(np.nanmax(tilts))],
        verdict=None)
    best = max(band6["spearman_vs_external"].items(), key=lambda kv: abs(kv[1]))
    band6["best_external_match"] = dict(name=best[0], spearman=best[1])
    band6["verdict"] = (
        "band 6 rank-matches external radiometric "
        f"{best[0]} (rho={best[1]:.4f}) far better than any magnetic transform "
        f"(tilt rho={band6['spearman_vs_tilt_deg_of_TMI']:.4f}, tmi_hg "
        f"rho={band6['spearman_vs_tmi_hg']:.4f}); the file's own description "
        f"'{descriptions.get(6)}' is therefore inconsistent with the bytes. "
        "Provisional identity: radiometric total count. Units remain unauthenticated."
        if abs(best[1]) > max(abs(band6["spearman_vs_tilt_deg_of_TMI"]),
                              abs(band6["spearman_vs_tmi_hg"])) + 0.15 else
        "band 6 identity NOT resolved by this test: no external layer dominates the "
        "magnetic transforms. Keep band 6 out of view A either way.")

    # ---------------------------------------------------------------- catalogue-distance rings
    dist_cat_m = ndi.distance_transform_edt(~catalogue, sampling=100.0)
    champ_off = supports[champ] & ~catalogue
    base_only = (supports[base] & ~catalogue) & ~champ_off
    rings = dict(
        champion_px=int(champ_off.sum()), base_only_px=int(base_only.sum()),
        base_only_distance_to_catalogue_m={
            "min": float(dist_cat_m[base_only].min()) if base_only.any() else None,
            "max": float(dist_cat_m[base_only].max()) if base_only.any() else None,
            "all_within_100_200m": bool(((dist_cat_m[base_only] >= 99.0) &
                                        (dist_cat_m[base_only] <= 201.0)).all()) if base_only.any() else None},
        champion_distance_to_catalogue_m_min=float(dist_cat_m[champ_off].min()) if champ_off.any() else None)

    out = dict(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        instrument="scripts/h61_forensics.py",
        evidence_class="MEASURED-FROM-PINNED-BYTES + HASH-LINKED/FILENAME-ONLY OWNER-REPORTED SCORES; "
                       "NOT ORGANIZER-CONFIRMED",
        provenance_caveat="All rasters are SHA-256-pinned owner mirrors of a login-walled portal "
                          "file; pins prove mirror consistency, not organiser authentication. "
                          "Scores are owner-reported attributions supplied in the session brief.",
        grid=grid, files=files,
        masked_accounting_witness=dict(
            files=[hedge, ens], off_catalogue_support_identical=identical_off,
            both_report=0.1563,
            T_under_raw_accounting=[table[hedge]["point"]["T_raw"], table[ens]["point"]["T_raw"]],
            T_under_masked_accounting=[table[hedge]["point"]["T_masked"],
                                       table[ens]["point"]["T_masked"]],
            conclusion="raw-S accounting assigns different credit to two files with identical "
                       "off-catalogue support and identical reported scores; masked accounting "
                       "assigns them the same credit. Masked accounting is used below."),
        subset_pairs=subset_pairs, intersecting_pairs=pairs,
        G_identification=bounds,
        G_point_under_zero_ring_credit=dict(G_px=G_point, ring_px=ring_px,
                                            assumption="the 6,436 px the champion deleted earn exactly 0 credit",
                                            sensitivity_to_ring_credit=sensitivity),
        credit_table=table, CMAX=CMAX, marginal_bar=marginal_bar,
        champion_credit_at_point=Tchamp, band6_identity=band6, catalogue_rings=rings)
    for p in (args.out, args.docs_out):
        dest = ROOT / p
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(out, indent=1, allow_nan=False, default=str) + "\n")
    print(json.dumps(dict(eligible_px=grid["eligible_px"], catalogue_px=grid["catalogue_px"],
                          identical_off_support=identical_off,
                          n_subset_pairs=len(subset_pairs),
                          G_interval_masked=[bounds["masked"]["G_lower_bound"],
                                             bounds["masked"]["G_upper_bound"]],
                          G_interval_raw=[bounds["raw"]["G_lower_bound"],
                                          bounds["raw"]["G_upper_bound"]],
                          G_point=G_point, band6=band6["verdict"][:160],
                          hash_linked=[f for f in ids if files[f]["attribution_class"]
                                       .startswith("HASH")],
                          out=args.out), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
