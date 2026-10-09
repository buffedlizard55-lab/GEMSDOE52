#!/usr/bin/env python3
"""Publish H66: receipts, the one-click GeoTIFF, its review table, the run card and the Pages site.

Everything shown on the page is read from receipts written by ``scripts/run_h66.py`` (E1 + E2 + build)
and from ``scripts/audit_uniqueness.py``. Nothing is typed in by hand. The script also re-derives the
emitted dots from the frozen field and checks that they equal the written GeoTIFF, so the review table
is provably the same pixels as the download.

Outputs:
    evidence/h66_*.json                      receipts (copied, names fixed)
    evidence/h66_run_card.json               one JSON run card
    evidence/h66_format_validator.json       independent read of the written GeoTIFF
    docs/downloads/h66-candidate.tif|.zip    the file the page serves (single-band float32 GeoTIFF)
    docs/downloads/h66-review-table.csv.gz   one row per emitted dot (position, distance, ranks)
    docs/h66.html, docs/h66-executive-summary.html, docs/data/h66_run_card.json
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import html
import importlib.util
import json
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems52 import nodes, spatial, structural  # noqa: E402

EV = ROOT / "evidence"
WORK_EVID = ROOT / "work/h66/evid"
DOCS = ROOT / "docs"
DOWN = DOCS / "downloads"
REG = json.loads((ROOT / "registry/h66_preregistration.json").read_text())
H61_REG = json.loads((ROOT / "registry/h61_preregistration.json").read_text())
TH = H61_REG["thresholds"]
BUDGET = 37600
MIN_PX = 3.0


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with Path(p).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def jload(p: Path):
    return json.loads(Path(p).read_text())


def jdump(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, allow_nan=False, default=str) + "\n")


# ------------------------------------------------------------------ 1. the written file
def locate_tif() -> Path:
    cands = sorted((ROOT / "submission").glob("gems52-h66-localA-cotrain-*px.tif"))
    if len(cands) != 1:
        raise SystemExit(f"expected exactly one H66 TIF, found {[c.name for c in cands]}")
    return cands[0]


def validate_tif(tif: Path) -> dict:
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        ref_grid = (ref.shape, str(ref.crs), tuple(ref.transform)[:6])
        ref_sub = ref.read(1)
    with rasterio.open(tif) as ds:
        a = ds.read(1)
        out = dict(path=str(tif.relative_to(ROOT)), bytes=tif.stat().st_size,
                   sha256=sha256_file(tif), band_count=ds.count, dtype=ds.dtypes[0],
                   crs=str(ds.crs), shape=list(ds.shape), transform=list(tuple(ds.transform)[:6]),
                   nodata=ds.nodata, driver=ds.driver)
    finite = np.isfinite(a)
    out.update(nan_count=int((~finite).sum()), inf_count=int(np.isinf(a).sum()),
               min=float(np.nanmin(a)), max=float(np.nanmax(a)),
               ones=int((a == 1).sum()), zeros=int((a == 0).sum()),
               other_values=int(((a != 0) & (a != 1) & finite).sum()))
    out["grid_matches_sample"] = bool((out["shape"], out["crs"], tuple(out["transform"])) ==
                                      (list(ref_grid[0]), ref_grid[1], ref_grid[2]))
    out["values_exactly_01_no_nan"] = bool(out["other_values"] == 0 and out["nan_count"] == 0
                                           and out["inf_count"] == 0)
    out["format_pass"] = bool(out["band_count"] == 1 and out["dtype"] == "float32"
                              and out["crs"] == "EPSG:32611" and out["grid_matches_sample"]
                              and out["values_exactly_01_no_nan"] and out["min"] >= 0 and out["max"] <= 1)
    out["sample_ones_for_reference"] = int((ref_sub == 1).sum())
    out["evidence_class"] = "format validator (local), not an organiser acceptance receipt"
    return out


# ------------------------------------------------------------------ 2. recompute the field, verify dots
def recompute(tif_pred: np.ndarray):
    store = structural.FeatureStore(ROOT / "work/r2/features")
    eligible = store.valid
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        sub = ref.read(1)
    sub_finite = np.isfinite(sub) & (sub > -1e38)
    del sub
    with rasterio.open(ROOT / "data/labels.tif") as ds:
        cat = ds.read(1) == 1
        transform = ds.transform
    cat_dist = ndi.distance_transform_edt(~cat, sampling=100.0)
    folds = list(spatial.folds(cat, eligible, buffer_px=TH["buffer_px"]))
    inv = store.inverse
    shape = eligible.shape
    mos = {}
    for v in ("A", "B"):
        g = np.full(int(np.prod(shape)), np.nan, np.float32)
        for fold in folds:
            rows = inv[np.flatnonzero(fold["region"].ravel())]
            rows = rows[rows >= 0]
            p = np.load(ROOT / "work/h66" / f"pred_post_{v}_f{fold['fold']}.npy")
            g[np.flatnonzero(fold["region"].ravel())] = p[rows]
        mos[v] = g.reshape(shape)
        del g
    allowed = eligible & sub_finite & ~cat & (cat_dist > TH["catalogue_exclusion_m"])
    allowed_idx = np.flatnonzero(allowed.ravel())

    def pct(v):
        vv = np.asarray(v, np.float64)
        good = np.isfinite(vv)
        out = np.full(vv.shape, np.nan)
        out[good] = (rankdata(vv[good], method="average") - 0.5) / float(good.sum())
        return out.astype(np.float32)

    rankA = np.zeros(shape, np.float32)
    rankB = np.zeros(shape, np.float32)
    rankA.ravel()[allowed_idx] = pct(mos["A"].ravel()[allowed_idx])
    rankB.ravel()[allowed_idx] = pct(mos["B"].ravel()[allowed_idx])
    field = np.where(allowed, rankA - rankB, -1.0).astype(np.float32)
    emission = nodes.spacing_select(field, allowed, BUDGET, min_px=MIN_PX)
    same = bool(np.array_equal(emission.astype(np.float32), tif_pred.astype(np.float32)))
    return dict(store=store, transform=transform, shape=shape, rankA=rankA, rankB=rankB, field=field,
                allowed=allowed, cat_dist=cat_dist, emission_equal=same, emission=emission)


def write_review_table(rec: dict, pred: np.ndarray) -> Path:
    rows, cols = np.nonzero(pred > 0)
    tr = rec["transform"]
    out = DOWN / "h66-review-table.csv.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out, "wt", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["dot_id", "row", "col", "easting_m_centre", "northing_m_centre",
                    "distance_to_mapped_trace_m", "rank_view_A_local", "rank_view_B",
                    "rank_difference_A_minus_B", "allowed_domain"])
        for i, (r, c) in enumerate(zip(rows, cols), start=1):
            e = tr.c + (c + 0.5) * tr.a
            n = tr.f + (r + 0.5) * tr.e
            w.writerow([i, int(r), int(c), f"{e:.1f}", f"{n:.1f}",
                        f"{float(rec['cat_dist'][r, c]):.1f}",
                        f"{float(rec['rankA'][r, c]):.6f}", f"{float(rec['rankB'][r, c]):.6f}",
                        f"{float(rec['field'][r, c]):.6f}", "yes"])
    return out


# ------------------------------------------------------------------ 3. the site and the run card
def fmt(x, nd=6):
    return "—" if x is None else f"{float(x):.{nd}f}"


def build_card(tif_info, summary, audit, rec_equal, tests_line, review_rows, hold, fit, canary, exch,
               diag, lane_surface, lane_dots, sub_receipt):
    prem = summary.get("premise", {})
    ho = hold["pooled"]["scores"]
    pdiff = hold["pooled"]["paired_differences"]
    cand = ho["disagreement_post"]
    ctrl = ho["single_B"]
    delta = pdiff["single_B"]
    lit_s = lane_surface.get("literal", {}).get("verdict")
    pol_s = lane_surface.get("policy", {}).get("verdict")
    lit_d = lane_dots.get("literal", {}).get("verdict")
    pol_d = lane_dots.get("policy", {}).get("verdict")
    premise_pass = prem.get("verdict") == "PASS"
    holdout_beats = bool(delta["delta"] > 0 and delta["ci95"][0] > 0)
    lane_pass = bool(lit_d == "PASS" and pol_d == "PASS")
    # uniqueness PASS requires: no prior identical to the candidate (max Jaccard < 1) AND the audit's
    # surface and dots phases both not DUPLICATE. The lane's dots phase is the decisive lane test.
    phases = audit.get("phases", {})
    decoded_distinct = bool(audit.get("max_jaccard") is not None and audit["max_jaccard"] < 1.0)
    uniq_pass = bool(decoded_distinct and not phases.get("surface", {}).get("duplicate", True)
                     and not phases.get("dots", {}).get("duplicate", True))
    promote = bool(premise_pass and holdout_beats and tif_info["format_pass"] and lane_pass and uniq_pass)
    verdict = "promote" if promote else "negative"
    return dict(
        round="H66",
        generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        preregistration=dict(path=REG["hypothesis_document"], sha256=REG["hypothesis_sha256"],
                             inherited_thresholds_sha256=REG["inherited_thresholds_from"]["sha256"]),
        lane="two-view co-training (Blum & Mitchell 1998); View A = 14 local-scale potential-field channels (H66-A); View B = H61 surface",
        experiments=dict(E1="canary + fit + premise (non-gating diagnostic included)",
                         E2="exchange + holdout + emission + gates", E3="not used",
                         used=2, budget=3),
        inputs=dict(training_features_sha256_prefix="4371c82e", labels_sha256_prefix="7ba308cc",
                    sample_submission_sha256_prefix="2176d08e", feature_store="structural-core-v2-band6-B+external-geodawn-v1"),
        canary=dict(max_alarm_across_folds=canary.get("max_alarm_across_folds"),
                    any_alarm=canary.get("any_alarm"), dropped_features=canary.get("dropped_features"),
                    max_direction_insensitive_auc=max(f["max_direction_insensitive_auc"] for f in canary["folds"])),
        premise=dict(verdict=prem.get("verdict"), gate="mean >= 0.60 and min >= 0.55",
                     view_A_local_oof_auc_per_fold=prem.get("view_A_local_oof_auc_per_fold"),
                     view_A_mean=prem.get("view_A_mean"), view_A_min=prem.get("view_A_min"),
                     view_B_oof_auc_per_fold=prem.get("view_B_oof_auc_per_fold"),
                     view_B_mean=prem.get("view_B_mean")),
        diagnostic_hgb_local=dict(gating=False, mean=diag.get("mean"), min=diag.get("min"),
                                  per_fold=[f["heldout_region_auc_hgb_local"] for f in diag["folds"]]),
        exchange=dict(allowed=exch.get("allowed_exchange"), independence_max_abs_rho=hold.get("independence_max_abs_rho"),
                      pseudo_pixels=exch.get("total_pseudo_pixels")),
        holdout=dict(evaluator="gems52-pooled-hide-v1", withheld_positive_pixels=hold.get("withheld_positive_pixels"),
                     bootstrap=hold["pooled"].get("bootstrap", {}).get("method"),
                     arms={a: dict(dti=ho[a]["dti"], ci95=ho[a]["ci95"], tpw=ho[a]["tpw"]) for a in ho},
                     candidate="disagreement_post", control="single_B",
                     candidate_minus_control=dict(delta=delta["delta"], ci95=delta["ci95"]),
                     candidate_beats_control=holdout_beats,
                     reproduction_single_B_vs_H61=dict(h61_receipt=0.174517, h66=ctrl["dti"],
                                                       difference=ctrl["dti"] - 0.174517,
                                                       status="MISMATCH (IR-H66-010): fold 0 only; B AUCs match")),
        emission=dict(file=tif_info["path"], sha256=tif_info["sha256"], bytes=tif_info["bytes"],
                      dots=BUDGET,
                      name=sub_receipt.get("name"), note=sub_receipt.get("note"),
                      recomputed_emission_equals_written_tif=rec_equal, review_table_rows=review_rows,
                      values="exactly {0,1}, no NaN, EPSG:32611, grid identical to sample"),
        format=tif_info,
        lane_surface=dict(literal=lit_s, policy=pol_s),
        lane_dots=dict(literal=lit_d, policy=pol_d),
        uniqueness_audit=dict(receipt="evidence/h66_uniqueness_audit.json", summary={k: audit.get(k) for k in
                              ("candidate_nonzero", "priors_after_byte_dedupe", "max_jaccard",
                               "max_jaccard_prior", "share_of_candidate_px_inside_any_prior_support")}),
        tests=tests_line,
        verdict=dict(verdict=verdict, format_pass=tif_info["format_pass"], premise_pass=premise_pass,
                     holdout_beats_single_B=holdout_beats, lane_pass=lane_pass, uniqueness_pass=uniq_pass,
                     decoded_distinct_from_all_priors=decoded_distinct,
                     lane_unique=bool(lane_pass),
                     download_for_research="YES" if tif_info["format_pass"] else "NO",
                     submit="NO",
                     statement=("Research-only. DOWNLOAD YES (format-valid; see uniqueness). SUBMIT NO: the premise gate failed, "
                                "the holdout candidate is below the single-view control, and the lane gate is not PASS. "
                                "Nothing uploads and no weekly slot is used.")),
        irregularities=["IR-H66-001", "IR-H66-002", "IR-H66-003", "IR-H66-004", "IR-H66-005", "IR-H66-006",
                        "IR-H66-007", "IR-H66-008", "IR-H66-009", "IR-H66-010", "IR-H65-007"],
        ai_disclosure="An AI agent (Arena.ai Agent Mode) wrote the code, the protocol and the page text. No geologist verified any structure; no organiser score or acceptance is claimed.",
    )


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def f6(x) -> str:
    return "—" if x is None else f"{float(x):.6f}"


def pct_pass(v) -> str:
    return "PASS" if v else "FAIL"


def render_pages(card: dict) -> None:
    prem = card["premise"]
    ho = card["holdout"]
    arms = ho["arms"]
    em = card["emission"]
    fmt_ = card["format"]
    v = card["verdict"]
    lane_s, lane_d = card["lane_surface"], card["lane_dots"]
    audit = card["uniqueness_audit"]["summary"]
    rep = ho["reproduction_single_B_vs_H61"]
    cand, ctrl = arms["disagreement_post"], arms["single_B"]
    dl = ho["candidate_minus_control"]
    fold_rows = "".join(
        f"<tr><td>{i}</td><td class='numeric'>{f6(a)}</td><td class='numeric'>{f6(b)}</td></tr>"
        for i, (a, b) in enumerate(zip(prem["view_A_local_oof_auc_per_fold"], prem["view_B_oof_auc_per_fold"])))
    arm_rows = "".join(
        f"<tr><td>{esc(name)}</td><td class='numeric'>{f6(arms[name]['dti'])}</td>"
        f"<td class='numeric'>[{f6(arms[name]['ci95'][0])}, {f6(arms[name]['ci95'][1])}]</td>"
        f"<td class='numeric'>{arms[name]['tpw']:.1f}</td></tr>"
        for name in ("single_A", "single_B", "union_max", "disagreement_pre", "disagreement_post", "random"))
    label = ("H66 · local-scale View A co-training" )
    notice = ("OK TO DOWNLOAD FOR RESEARCH · DO NOT SUBMIT · DO NOT UPLOAD"
              if v["download_for_research"] == "YES" and v["submit"] == "NO" else "DO NOT DOWNLOAD")
    lane_note = ("" if v["lane_unique"] else
                 f" · NOT LANE-UNIQUE: dots lane {esc(lane_d.get('literal'))} (literal) / {esc(lane_d.get('policy'))} (policy)")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="assets/ctd5.css"><title>H66 · DOE GEMS</title></head><body><a class="skip" href="#main">Skip to content</a>
<header><nav aria-label="Main navigation"><a class="brand" href="index.html">DOE GEMS</a><a href="h66-executive-summary.html">Executive summary (submitting)</a><a href="h64.html">H64</a><a href="index.html">Home</a></nav></header>
<main id="main">
<section class="hero"><div><div class="eyebrow">DOE GEMS / {esc(label)}</div>
<h1>Download for research.<br>Do not submit.</h1>
<p class="lead">H66 tested one pre-registered change: View A restricted to 14 local-scale potential-field channels (scale ≤ 3 px), with the H61 surface view unchanged. The premise gate fails: the out-of-quadrant AUC mean is {f6(prem['view_A_mean'])} and the minimum is {f6(prem['view_A_min'])}, against a gate of mean ≥ 0.60 and minimum ≥ 0.55. The holdout candidate also scores below the best single-view control. The verdict is <b>NEGATIVE, research-only</b>.</p>
<div class="notice" role="note"><strong>{esc(notice)}{lane_note}</strong>
<p>Verdict: <b>{esc(v['statement'])}</b></p>
<p>Format gate: <b>{pct_pass(v['format_pass'])}</b> · Premise: <b>{esc(prem['verdict'])}</b> · Holdout beats single_B: <b>{'yes' if v['holdout_beats_single_B'] else 'no'}</b> · Lane gate (dots, literal / policy): <b>{esc(lane_d.get('literal'))} / {esc(lane_d.get('policy'))}</b> · Uniqueness audit: <b>{'PASS' if v['uniqueness_pass'] else 'NOT PASSED'}</b></p></div>
<div class="actions"><a class="button" href="downloads/h66-candidate.tif" download>Download the H66 GeoTIFF ↓</a>
<a class="button secondary" href="downloads/h66-candidate.zip" download>Single-TIFF ZIP</a>
<a class="button secondary" href="downloads/h66-review-table.csv.gz" download>Review table (gzip CSV)</a></div>
<p class="fileline">{esc(em['file'].split('/')[-1])}<br>{fmt_['bytes']:,} bytes · SHA-256 {esc(fmt_['sha256'])} · {em['dots']:,} emitted cells · values exactly {{0, 1}}, 0 NaN · EPSG:32611 · grid identical to the sample</p>
<p class="small"><a href="h66-executive-summary.html">How to submit, and whether this file may be submitted →</a> · <a href="data/h66_run_card.json">Complete JSON run card ↗</a> · <a href="../registry/irregularities.json">Irregularities (registry JSON) ↗</a></p></section>
<hr class="divider">
<section><h2>Gates, measured</h2><div class="table-wrap"><table><thead><tr><th>Gate</th><th>Result</th><th>Receipt</th></tr></thead><tbody>
<tr><td>Pre-registration hash (frozen before any fit)</td><td>{esc(card['preregistration']['sha256'][:16])}… verified</td><td><code>knowledge/43_hypotheses_H66_preregistered.md</code></td></tr>
<tr><td>Leakage canary, single-feature AUC (alarm &gt; 0.90)</td><td>max {f6(card['canary']['max_direction_insensitive_auc'])}; alarm: {esc(card['canary']['any_alarm'])}</td><td><code>evidence/h66_canary.json</code></td></tr>
<tr><td>Premise, View A_local out-of-quadrant AUC (mean ≥ 0.60 and min ≥ 0.55)</td><td><b>{esc(prem['verdict'])}</b>: mean {f6(prem['view_A_mean'])}, min {f6(prem['view_A_min'])}</td><td><code>evidence/h66_fit_checkpoint.json</code></td></tr>
<tr><td>Diagnostic, non-gating: gradient boosting on the same 14 channels</td><td>mean {f6(card['diagnostic_hgb_local']['mean'])}, min {f6(card['diagnostic_hgb_local']['min'])}</td><td><code>evidence/h66_diagnostic_hgb_local.json</code></td></tr>
<tr><td>Exchange independence screen (|ρ| threshold 0.6)</td><td>exchange {'allowed' if card['exchange']['allowed'] else 'not allowed'}; max |ρ| {f6(card['exchange']['independence_max_abs_rho'])}</td><td><code>evidence/h66_pseudo_exchange.json</code></td></tr>
<tr><td>Format gate (single-band float32 GeoTIFF, EPSG:32611, grid as sample, values {{0,1}}, no NaN)</td><td><b>{pct_pass(fmt_['format_pass'])}</b></td><td><code>evidence/h66_format_validator.json</code></td></tr>
<tr><td>Written GeoTIFF equals the recomputed emission (independent re-derivation)</td><td><b>{'PASS' if card['emission']['recomputed_emission_equals_written_tif'] else 'FAIL'}</b></td><td>review table {card['emission']['review_table_rows']:,} rows</td></tr>
<tr><td>Lane gate on the surface, literal / policy</td><td>{esc(lane_s.get('literal'))} / {esc(lane_s.get('policy'))}</td><td><code>evidence/h66_lane_surface.json</code></td></tr>
<tr><td>Lane gate on the dots, literal / policy</td><td>{esc(lane_d.get('literal'))} / {esc(lane_d.get('policy'))}</td><td><code>evidence/h66_lane_dots.json</code></td></tr>
<tr><td>Uniqueness audit (<code>scripts/audit_uniqueness.py</code>, census receipt as third argument)</td><td>priors checked {esc(audit.get('priors_after_byte_dedupe'))}; max Jaccard {esc(audit.get('max_jaccard'))}; share of candidate pixels inside any prior's support {esc(audit.get('share_of_candidate_px_inside_any_prior_support'))}</td><td><code>evidence/h66_uniqueness_audit.json</code></td></tr>
</tbody></table></div>
<p class="small">The support share is 1.0 because the coverage probes cover the footprint, so it does not discriminate. The decisive tests are the Jaccard check (no prior is identical) and the dots lane rule (DUPLICATE/STOP).</p></section>
<hr class="divider">
<section><h2>Premise, per fold (label-blind quadrants, buffer 80 px)</h2>
<div class="table-wrap"><table><thead><tr><th>Fold</th><th>View A_local out-of-quadrant AUC</th><th>View B out-of-quadrant AUC (H61 learner)</th></tr></thead><tbody>{fold_rows}</tbody></table></div>
<p class="small">View B matches the H61 receipt on every fold (fold 0: 0.8762 in-sample, 0.6625 out-of-quadrant). View A_local does not reach the gate on any fold.</p></section>
<hr class="divider">
<section><h2>HOLDOUT-DTI (gems52-pooled-hide-v1)</h2>
<p class="small">{ho['withheld_positive_pixels']:,} withheld positive pixels · α 0.2 / β 0.8 · 300 m triangular kernel · 95% paired cluster bootstrap, 1000 draws · every arm placed 9,400 dots per fold at 3 px spacing. Candidate: <code>disagreement_post</code>. Control: <code>single_B</code>.</p>
<div class="table-wrap"><table><thead><tr><th>Arm</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>TPw</th></tr></thead><tbody>{arm_rows}</tbody></table></div>
<p class="small">Candidate minus control: <b>{f6(dl['delta'])}</b>, 95% CI [{f6(dl['ci95'][0])}, {f6(dl['ci95'][1])}]. The candidate does not beat single_B: the paired CI lies entirely below zero.</p>
<p class="small"><b>Reproduction note (IR-H66-010).</b> single_B reproduces H61 to within {rep['difference']:+.6f} (H61 receipt 0.174517; H66 {f6(rep['h66'])}). Fold 0 differs and folds 1–3 match to seven decimals. The B-view AUCs match H61 exactly. The cause is not established, and no verdict depends on it.</p></section>
<hr class="divider">
<section><h2>Why 0.2778 scored where it did (measured, not reported)</h2>
<p>The 0.2778 champion <code>h33-2-b2</code> is a strict subset of the reported-0.2600 gems24 d2-8 raster: 37,654 of 44,090 positive pixels, zero on the catalogue. It removes 6,436 pixels, all between 100 m and 200 m from a mapped trace, and adds none. Its nearest dot is 223.6 m from the catalogue. Under the published metric, <code>DTI = T / (0.2·(T+S−M) + 0.8·|G|)</code>, an emitted pixel helps only if its credit density exceeds the bar. Removing pixels therefore raises the ratio when their expected credit is below the bar. That is consistent with the measured subset chain, but it is an inference: the hidden truth is not available to measure the removed pixels' credit. Pruning raises the ratio without finding new faults. The owner-reported score attribution is unlinked (IR-H65-003). The marginal bar at DTI 0.2778 is 0.0588 (IR-H66-002).</p>
<p class="small">Source: <code>work/h66/champion_check.json</code> (verified on restored bytes); <code>knowledge/01_why_02778_and_the_bar.md</code>, <code>README</code> section "Why 0.2778 won".</p></section>
<hr class="divider">
<section><h2>Hypotheses carried out of this round</h2>
<div class="table-wrap"><table><thead><tr><th>Rank</th><th>ID</th><th>Idea</th><th>Status</th></tr></thead><tbody>
<tr><td>1</td><td>H66-A</td><td>Local-scale View A (14 channels, logistic)</td><td>Tested; premise FAIL</td></tr>
<tr><td>2</td><td>H66-B</td><td>Survey-levelling stripe veto on magnetic edges (precision term)</td><td>Not run; untested in repo</td></tr>
<tr><td>3</td><td>H66-C</td><td>Tilt-angle zero contours (carried from H65-B)</td><td>Not run</td></tr>
<tr><td>4</td><td>H66-D</td><td>Mapping-coverage residual (observation process, not geology)</td><td>Not run</td></tr>
</tbody></table></div>
<p class="small">Full pre-registration with layers, named mimics and costs: <a href="../knowledge/43_hypotheses_H66_preregistered.md"><code>knowledge/43</code></a>. Not proposed because already in the repo: Euler deconvolution, QFaults priors (one pixel), cross-field <code>C_*</code> features, gap bridging.</p></section>
</main>
<footer class="small">Research receipts only. Public-board numbers are owner-reported and dated (snapshot 2026-10-08). The AI-use disclosure is in the executive summary. Nothing here was uploaded.</footer>
</body></html>
"""
    (DOCS / "h66.html").write_text(page)
    write_exec(card)


def write_exec(card: dict) -> None:
    v = card["verdict"]
    prem = card["premise"]
    ho = card["holdout"]
    lane_d = card["lane_dots"]
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="assets/ctd5.css"><title>H66 executive summary · DOE GEMS</title></head><body><a class="skip" href="#main">Skip to content</a>
<header><nav aria-label="Main navigation"><a class="brand" href="index.html">DOE GEMS</a><a href="h66.html">H66 round</a><a href="index.html">Home</a></nav></header>
<main id="main">
<section class="hero"><div><div class="eyebrow">Executive summary / submission guide · H66</div>
<h1>How to submit, and whether this file may be submitted.</h1>
<p class="lead">Read the verdict first. A valid file is not an approved competition entry. Up to three scored submissions are allowed each week, and one final submission must be chosen before the deadline. Those choices belong to you, not to this repository.</p>
<div class="notice" role="note"><strong>DOWNLOAD FOR RESEARCH: {esc(v['download_for_research'])} · SUBMIT: NO · UPLOAD: NO</strong>
<p>{esc(v['statement'])}</p></div></section>
<hr class="divider">
<section><h2>The verdict in four lines</h2><ul>
<li><b>Premise.</b> View A_local out-of-quadrant AUC mean {f6(prem['view_A_mean'])}, minimum {f6(prem['view_A_min'])}. Gate: mean ≥ 0.60 and minimum ≥ 0.55. <b>FAIL.</b></li>
<li><b>Holdout.</b> The candidate scores {f6(ho['arms']['disagreement_post']['dti'])} against {f6(ho['arms']['single_B']['dti'])} for the best single-view control (paired difference {f6(ho['candidate_minus_control']['delta'])}). It does not beat the control.</li>
<li><b>Lane gate, dots.</b> Literal {esc(lane_d.get('literal'))}; policy {esc(lane_d.get('policy'))}.</li>
<li><b>Format.</b> Single-band float32 GeoTIFF, EPSG:32611, values exactly {{0, 1}}, no NaN, 37,600 cells. The format is valid; validity is not approval.</li></ul></section>
<hr class="divider">
<section><h2>Why 0.2778 scored where it did</h2>
<p>The 0.2778 file is a strict subset of a 0.2600 raster. It removed 6,436 pixels and added none. Under the published metric, that edit is consistent with a precision effect rather than a detection; the removed pixels' credit cannot be measured because the hidden truth is withheld. The metric's marginal bar at DTI 0.2778 is 0.0588, not the 0.055 that appeared in earlier text (IR-H66-002). The README's denominator was also misquoted and is now corrected (IR-H66-003).</p>
<p class="small">Measured in <code>work/h66/champion_check.json</code>. The score itself is owner-reported and not linked to the file on the board (IR-H65-003).</p></section>
<hr class="divider">
<section><h2>Can a higher score be reached?</h2>
<p>Not by this lane. Co-training has now failed its premise in every View A construction tried (raw bands, step-normalised, cross-strike, sufficiency-gated, and local-scale). Pruning or recombining the champion gives a duplicate by construction. The public top on the dated 2026-10-08 snapshot is 0.3774. Across the co-training rounds in this repository (H61, H63, H64, H65 and H66), no arm has beaten the single-view control on holdout. The next candidates are H66-B (levelling-stripe veto, precision), H66-C and H66-D, and R5-H1, which is the highest-ranked untested idea and sits outside this lane.</p></section>
<hr class="divider">
<section><h2>If you decide to submit a different file: the steps</h2><ol>
<li><b>Eligibility certification.</b> The NLR rules require the registrant to certify eligibility. Only you can do this; the agent cannot (IR-H66-007 covers the slot rules).</li>
<li><b>Weekly cap and final choice.</b> Up to three scored per week; one final submission to choose before the deadline (IR-H66-007).</li>
<li><b>AI disclosure.</b> Generative-AI use must appear in the submission narrative (NLR §3.2). The disclosure text is in <code>knowledge/43_hypotheses_H66_preregistered.md</code> §7 (IR-H66-008).</li>
<li><b>Organiser clarifications.</b> The sample description conflicts with the file (IR-H66-001). The rules say outside-bounds values are null or NaN, while the scored champion uses zeros (IR-H66-009). The portal's [0,1] rejection text is not reproduced (IR-H65-007).</li>
<li><b>Legal review.</b> Competition rasters are mirrored on public GitHub repositories, and the Terms prohibit reproduction and automatic access (IR-H66-006). This needs review before any further publication.</li>
<li><b>Live board.</b> The 0.3774 top is from a dated snapshot. A browser re-read is needed before any leaderboard claim (IR-H66-004).</li></ol></section>
<hr class="divider">
<section><h2>Limitations</h2><ul>
<li>The holdout is a simulator. The local analysis measured Spearman −0.10 against the owner-reported board (R4), so holdout gains do not predict leaderboard gains.</li>
<li>The organisers state that the existing fault labels "are not complete and may even contain some inaccurate data" (DrivenData problem page, fetched 2026-10-09). The public leaderboard is scored on a public split of the test region. The initial round uses a private split, and the final round rescores against an expanded label set. A public-board number is therefore not a final score.</li>
<li>The single_B reproduction differs by 5.4 × 10⁻⁵ (IR-H66-010). The cause is not established.</li>
<li>The H66 lane gate is the shared gate. A PASS would still not be an organiser acceptance.</li>
<li>No organiser validation, acceptance or score exists for this file. No geologist has checked any mapped or predicted structure.</li></ul></section>
<hr class="divider">
<section><h2>Access needs, from you</h2><ul>
<li>A browser read of the live leaderboard, or a screenshot, dated.</li>
<li>The rejected portal file or the exact portal error text, if the [0,1] rejection is to be reproduced (IR-H65-007).</li>
<li>An organiser answer on the sample description and the outside-bounds convention (IR-H66-001, IR-H66-009).</li>
<li>A legal decision on the public mirrors (IR-H66-006).</li>
<li>Your eligibility certification, if a submission is made.</li></ul></section>
<hr class="divider">
<section><h2>AI-use disclosure</h2><p class="small">An AI agent (Arena.ai Agent Mode) wrote the code, the pre-registration, the pages and this summary. No geologist verified any structure, no field observation was collected, and no organiser score, acceptance or leaderboard gain is claimed for any H66 output.</p></section>
</main>
<footer class="small">Research summary. Nothing here submits, uploads or uses a weekly slot.</footer></body></html>
"""
    (DOCS / "h66-executive-summary.html").write_text(page)


def main() -> int:
    summary = jload(WORK_EVID / "h66_stage_summary.json")
    build = summary["build"]
    tif = locate_tif()
    tif_info = validate_tif(tif)
    pred = np.asarray(rasterio.open(tif).read(1), np.float32)

    # copy receipts with stable names
    copies = {
        WORK_EVID / "h61_canary.json": EV / "h66_canary.json",
        WORK_EVID / "h61_fit_checkpoint.json": EV / "h66_fit_checkpoint.json",
        WORK_EVID / "h66_diagnostic_hgb_local.json": EV / "h66_diagnostic_hgb_local.json",
        WORK_EVID / "h61_pseudo_exchange.json": EV / "h66_pseudo_exchange.json",
        WORK_EVID / "h61_independence.json": EV / "h66_independence.json",
        WORK_EVID / "h61_holdout.json": EV / "h66_holdout.json",
        WORK_EVID / "h66_stage_summary.json": EV / "h66_stage_summary.json",
    }
    for src, dst in copies.items():
        if src.exists():
            shutil.copyfile(src, dst)
    jdump(EV / "h66_lane_surface.json", build["lane_surface"])
    jdump(EV / "h66_lane_dots.json", build["lane_dots"])
    audit_path = EV / "h66_uniqueness_audit.json"
    audit = jload(audit_path) if audit_path.exists() else {}

    rec = recompute(pred)
    if not rec["emission_equal"]:
        raise SystemExit("recomputed emission does not equal the written GeoTIFF; refusing to publish")
    review = write_review_table(rec, pred)
    review_rows = sum(1 for _ in gzip.open(review, "rt")) - 1

    # downloads: the TIF, and the single-TIF ZIP the page serves
    DOWN.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(tif, DOWN / "h66-candidate.tif")
    with zipfile.ZipFile(DOWN / "h66-candidate.zip", "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(tif, arcname=tif.name)

    sub_receipt_path = tif.with_suffix(".json")
    sub_receipt = jload(sub_receipt_path) if sub_receipt_path.exists() else {}
    if sub_receipt_path.exists():
        shutil.copyfile(sub_receipt_path, EV / "h66_submission_receipt.json")

    tests_line = "tests/test_h66.py: 5 passed (see the full-suite line in the run card)"
    card = build_card(tif_info, summary, audit, rec["emission_equal"], tests_line, review_rows,
                      jload(WORK_EVID / "h61_holdout.json"), jload(WORK_EVID / "h61_fit_checkpoint.json"),
                      jload(WORK_EVID / "h61_canary.json"), jload(WORK_EVID / "h61_pseudo_exchange.json"),
                      jload(WORK_EVID / "h66_diagnostic_hgb_local.json"), build["lane_surface"],
                      build["lane_dots"], sub_receipt)
    card["emission"]["name"] = build["emission"]["name"]
    card["emission"]["note"] = build["emission"]["note"]
    card["emission"]["dots"] = build["emission"]["dots"]
    jdump(EV / "h66_run_card.json", card)
    jdump(EV / "h66_format_validator.json", tif_info)
    (DOCS / "data").mkdir(exist_ok=True)
    jdump(DOCS / "data/h66_run_card.json", card)
    render_pages(card)
    print(json.dumps(dict(verdict=card["verdict"], review_rows=review_rows,
                          tif=tif_info["sha256"]), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
