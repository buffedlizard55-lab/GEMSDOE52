#!/usr/bin/env python3
"""H88 verification — re-measure the champion's byte geometry and the mass lever from the restored bytes.

Every number written to ``evidence/h88_mass_lever.json`` is read from the pinned rasters in this
checkout.  Owner-reported scores are copied from the brief's table (``docs/data/ctd5_owner_reported_results.json``
and ``knowledge/76`` §4) and are labelled ``OWNER/USER-REPORTED; NOT ORGANIZER-CONFIRMED`` — they are
never mixed with measured quantities.  The metric inversion uses the published identity
``DTI = T / (0.2(T + S - M) + 0.8|G|)`` from ``src/gems52/metric.py`` with the **measured** M, not the
``M = T`` shortcut that ``knowledge/76`` §3 used.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import metric  # noqa: E402

RING_PX = metric.R_PX / 2.0 * 2  # 3.0 px kernel radius; the ring under test is 200 m = 2 px
RING_200M_PX = 2.0

SCORED = {
    "data/reference/h33-2-b2-zeros.tif": 0.2778,
    "data/scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif": 0.2600,
    "data/scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif": 0.2477,
    "data/scored/gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif": 0.2449,
    "data/scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif": 0.1922,
    "data/scored/gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan.tif": 0.1894,
    "data/scored/gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif": 0.1855,
    "data/scored/gems10-h28-dotted-ridge-20260928T020256236880Z-6452ae1d00.tif": 0.1839,
    "data/scored/gemsdoe-ens12-adopted-7f00890a.tif": 0.1563,
    "data/scored/8GEMSDOE_Hedge-v2_submission.tif": 0.1563,
    "data/scored/gems10-h25-ctx-ridge-20260927T232947704150Z-6452ae1d00.tif": 0.1280,
    "data/scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif": 0.0904,
    "data/scored/gemsdoe9-PLACEHOLDER-2314b599.tif": 0.0107,
}


def read(path):
    with rasterio.open(path) as s:
        a = s.read(1)
        meta = dict(dtype=s.dtypes[0], shape=s.shape, crs=s.crs.to_epsg() if s.crs else None,
                    res=tuple(s.res), nodata=s.nodata, compression=str(s.compression),
                    tiled=bool(s.is_tiled), bands=s.count)
    return a, meta


def mass_of(a):
    f = np.nan_to_num(a.astype(np.float64), nan=0.0)
    pos = f > 0
    binary = bool(pos.sum() and np.array_equal(f[pos], np.ones(int(pos.sum()))))
    return float(f.sum()), int(pos.sum()), binary


def implied_T(dti, S, M, nG):
    """Invert the published identity for T given DTI, mass S, measured kernel cover M, truth |G|."""
    num = dti * (0.2 * (S - M) + 0.8 * nG)
    return num / (1.0 - 0.2 * dti)


def required_T(dti, S, M, nG):
    """T needed to reach ``dti`` at a given S with measured M."""
    return dti * (0.2 * (S - M) + 0.8 * nG) / (1.0 - 0.2 * dti)


def main():
    champ_a, champ_meta = read(ROOT / "data/reference/h33-2-b2-zeros.tif")
    with rasterio.open(ROOT / "data/labels.tif") as s:
        labels = s.read(1)
    cat = labels == 1
    d_cat = ndi.distance_transform_edt(~cat)
    S, npos, binary = mass_of(champ_a)
    pos = champ_a == 1
    q = np.maximum(1.0 - (d_cat * metric.PIXEL_M) / metric.R_M, 0.0)
    M = float((champ_a.astype(np.float64) * q).sum())
    out = dict(
        stage="mass_lever_verification", generated_utc=__import__("datetime").datetime.utcnow().isoformat() + "Z",
        champion=dict(
            path="data/reference/h33-2-b2-zeros.tif", sha256=__import__("hashlib").sha256(
                (ROOT / "data/reference/h33-2-b2-zeros.tif").read_bytes()).hexdigest(),
            meta=champ_meta, distinct_values=int(np.unique(champ_a).size), binary=binary,
            mass_S=S, positives=npos,
            min_distance_to_catalogue_m=float(d_cat[pos].min() * metric.PIXEL_M),
            median_distance_to_catalogue_m=float(np.median(d_cat[pos]) * metric.PIXEL_M),
            share_within_300m_pct=float((d_cat[pos] <= metric.R_PX).mean() * 100.0),
            M_kernel_cover=round(M, 3), M_over_S=round(M / S, 6),
        ),
        nested_pair_test=dict(),
        mass_vs_score_table=[], metric_inversion=dict(), notes=[],
    )
    # --- nested pair: champion vs the 0.2600 file it came from --------------------------------
    d28_path = ROOT / "data/scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif"
    if d28_path.exists():
        b, bmeta = read(d28_path)
        posb = np.nan_to_num(b.astype(np.float64), nan=0.0) > 0
        ring = posb & (d_cat <= RING_200M_PX)
        out["nested_pair_test"] = dict(
            parent=str(d28_path.relative_to(ROOT)), parent_meta=bmeta,
            parent_positives=int(posb.sum()),
            parent_px_within_200m=int(ring.sum()),
            parent_share_within_200m_pct=round(float(ring.sum()) / float(posb.sum()) * 100.0, 3),
            champion_px_within_200m=int((pos & (d_cat <= RING_200M_PX)).sum()),
            champion_minus_parent_px=int((pos & ~posb).sum()),
            parent_minus_champion_px=int((posb & ~pos).sum()),
            parent_minus_champion_all_in_ring=bool((posb & ~pos & (d_cat > RING_200M_PX)).sum() == 0),
            champion_equals_parent_minus_ring=bool(np.array_equal(pos, posb & (d_cat > RING_200M_PX))),
        )
    # --- mass vs owner-reported score ---------------------------------------------------------
    for rel, score in SCORED.items():
        p = ROOT / rel
        if not p.exists():
            out["notes"].append(f"missing raster, excluded from the table: {rel}")
            continue
        a, _ = read(p)
        m, n, binx = mass_of(a)
        out["mass_vs_score_table"].append(dict(path=rel, mass=m, positives=n, binary=binx,
                                              owner_reported_score=score,
                                              evidence_class="OWNER/USER-REPORTED; NOT ORGANIZER-CONFIRMED"))
    tbl = [r for r in out["mass_vs_score_table"] if "PLACEHOLDER" not in r["path"]]
    ph = [r for r in out["mass_vs_score_table"] if "PLACEHOLDER" in r["path"]]
    if len(tbl) >= 3:
        rho = stats.spearmanr([r["mass"] for r in tbl], [r["owner_reported_score"] for r in tbl])
        out["spearman_mass_vs_score"] = dict(
            n=len(tbl), rho=round(float(rho.statistic), 4), p=round(float(rho.pvalue), 4),
            excluded=[r["path"] for r in ph],
            note=("PLACEHOLDER file excluded: its id in registry/data_manifest.json says the bytes are a "
                  "stand-in, so its mass is not the real submission's mass"),)
        if ph:
            out["notes"].append("2314b599 (0.0107) is a PLACEHOLDER raster; excluded from the correlation")
    # --- metric inversion with measured M -----------------------------------------------------
    nG_bracket = dict(lower_5949=5949, upper_12512=12512, incumbent_14089=14089)
    out["metric_inversion"] = dict(
        identity="DTI = T / (0.2*(T + S - M) + 0.8*|G|),  FNw = |G| - T identically",
        M_measured=M, S=S,
        implied_T_by_truth_size={k: round(implied_T(0.2778, S, M, v), 2) for k, v in nG_bracket.items()},
        knowledge76_implied_T_MequalsT_assumption={k: round(0.2778 * (0.2 * S + 0.8 * v), 2)
                                                  for k, v in nG_bracket.items()},
        required_T_for_0_3195_at_S37654={k: round(required_T(0.3195, S, M, v), 2) for k, v in nG_bracket.items()},
        required_T_for_0_3774_at_S37654={k: round(required_T(0.3774, S, M, v), 2) for k, v in nG_bracket.items()},
        mass_for_0_3195_at_champion_credit_14089=round(
            (nG_bracket["incumbent_14089"] and 0) + 0, 1),
        note=("knowledge/76 §3 evaluates the reduced form DTI = T/(0.2 S + 0.8|G|), which is exact only "
              "when M = T. The champion's measured M = %.3f against an implied T of thousands, so the "
              "reduced form is not exact here; the table above uses the measured M." % M),
    )
    # mass needed at the champion's implied credit to reach 0.3195
    T_champ = implied_T(0.2778, S, M, nG_bracket["incumbent_14089"])
    inert = out["metric_inversion"]
    del inert["mass_for_0_3195_at_champion_credit_14089"]
    # solve 0.3195 = T / (0.2*(T + S' - M) + 0.8|G|) for S' at T = T_champ
    # S' = (T/DTI - 0.8|G|)/0.2 - T + M
    nG = nG_bracket["incumbent_14089"]
    Sp = (T_champ / 0.3195 - 0.8 * nG) / 0.2 - T_champ + M
    inert["mass_for_0_3195_at_champion_credit_14089"] = round(Sp, 1)
    inert["mass_check_S_prime_gives_target"] = round(
        T_champ / (0.2 * (T_champ + Sp - M) + 0.8 * nG), 5)
    # the same question with the M=T shortcut knowledge/76 used, for the record
    T76 = 0.2778 * (0.2 * S + 0.8 * nG)
    inert["mass_for_0_3195_with_MequalsT_shortcut"] = round((T76 / 0.3195 - 0.8 * nG) / 0.2 - T76 + T76, 1)
    inert["credit_density_champion_pct"] = round(T_champ / S * 100.0, 2)
    inert["credit_density_required_at_S37654_pct"] = round(required_T(0.3195, S, M, nG) / S * 100.0, 2)
    inert["champion_implied_T_at_14089"] = round(T_champ, 2)
    (ROOT / "evidence").mkdir(exist_ok=True)
    (ROOT / "evidence/h88_mass_lever.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "mass_vs_score_table"}, indent=1, default=str))
    print(f"\nwrote {ROOT/'evidence/h88_mass_lever.json'}")


if __name__ == "__main__":
    main()
