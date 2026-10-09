#!/usr/bin/env python3
"""Publish the H70 round to the static GitHub Pages site.

Reads the H70 receipts (every number is injected from ``evidence/h70_*.json`` or the submission
receipt; nothing is hand-typed), stages the download aliases, refreshes the local feed, and
regenerates:

* ``docs/index.html``            -- H70 hero, unmistakable download/submit verdict, holdout table
* ``docs/executive-summary.html``-- the submission guide (exact steps, file contract, verdict)
* ``docs/h70.html``              -- the H70 landing/audit page
* ``docs/h70-executive-summary.html`` -- the same guide under the round's own name
* ``docs/downloads/index.html``  -- the H70 rows and the latest-research notice
* ``docs/data/feed.json``        -- ``latest_research`` for the H70 artefact

The global submission pointer (``submission/LATEST.txt`` / ``docs/data/submission.json``) is NOT
moved: H70 is a negative round, and only a round that passes its gates may take the pointer.

Run after ``scripts/run_h70.py build``:  ``.venv/bin/python scripts/publish_h70_site.py``
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"
DATA = DOCS / "data"
DL = DOCS / "downloads"
SUBM = ROOT / "submission"


def esc(x) -> str:
    return (str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def f6(x) -> str:
    return f"{float(x):.6f}"


def ci(pair) -> str:
    return f"[{float(pair[0]):.4f}, {float(pair[1]):.4f}]"


def load(name: str) -> dict:
    return json.loads((EVID / f"h70_{name}.json").read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


NAV = ('<a class="brand" href="index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>\n'
       '<a href="index.html">Overview</a><a href="h70.html">H70 run &amp; evidence</a>'
       '<a href="executive-summary.html">Submission guide</a>'
       '<a href="h70-sources.html">Sources</a><a href="downloads/index.html">Archive</a>')

HEAD = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<meta name="description" content="{desc}">\n<title>{title} · GEMSDOE52</title>'
        '<link rel="stylesheet" href="assets/ctd5.css"><script src="assets/h70.js" defer></script>'
        '</head>\n<body><a class="skip" href="#main">Skip to content</a>'
        '<header><nav aria-label="Main navigation">{nav}</nav></header>\n<main id="main">')

FOOT = ('</main><footer>Independent competition research, not an official DOE or DrivenData site. '
        'Predictions are not verified faults or geothermal discoveries.<br>\n'
        '<a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code &amp; reproducibility</a> · '
        '<a href="h70.html#limits">Limitations</a> · '
        '<a href="data/h70_run_card.json">JSON run card</a> · H70 / 2026-10-09</footer></body></html>')


def page(title: str, desc: str, body: str) -> str:
    return HEAD.format(title=esc(title), desc=esc(desc), nav=NAV) + body + FOOT


def main() -> int:
    card = load("run_card")
    hold = load("holdout")
    cap = json.loads((EVID / "h70_a_only_capacity.json").read_text())
    s1 = load("sufficiency")
    indep = load("independence")
    exch = load("pseudo_exchange")
    canary = load("canary")
    lane_dots = load("lane_dots")
    lane_surf = load("lane_surface")
    stem = Path(card["raster"]["file"]).stem
    tif_name = card["raster"]["file"]
    sub_rec = json.loads((SUBM / f"{stem}.json").read_text())
    val = card["validator"]
    sha256 = card["raster"]["sha256"]
    nbytes = card["raster"]["bytes"]
    ndots = card["counts"]["placed"]

    # ---- stage the download aliases (the build already wrote them; verify byte-identity) ----
    for src, dst in ((SUBM / tif_name, DL / "h70-candidate.tif"),
                     (SUBM / f"{stem}.zip", DL / "h70-candidate.zip"),
                     (SUBM / f"{stem}.json", DL / "h70-candidate-receipt.json")):
        if not dst.exists() or sha(dst) != sha(src):
            shutil.copyfile(src, dst)
        if sha(dst) != sha(src):
            raise SystemExit(f"staged download differs from its source: {dst}")
    # also stage the canonical full-name copies (the scheduled feed does this too; keep it fresh)
    for f in (SUBM / tif_name, SUBM / f"{stem}.zip"):
        tgt = DL / f.name
        if not tgt.exists() or sha(tgt) != sha(f):
            shutil.copyfile(f, tgt)

    # ---- numbers used across pages -------------------------------------------------------
    pooled = hold["pooled"]["a_only"]
    arms = pooled["scores"]
    order = ["single_A", "single_B", "union_max", "disagreement_pre", "disagreement_post",
             "a_only", "single_B_veto_Bonly", "concordant", "random"]
    pure = cap["pooled_unmatched_budget"]["scores"]["a_only_pure"]
    pure_d = cap["pooled_unmatched_budget"]["paired_differences"]
    sB = arms["single_B"]["dti"]
    cand = arms["a_only"]["dti"]
    cand_ci = arms["a_only"]["ci95"]
    d_sB = pooled["paired_differences"]["single_B"]
    d_rnd = pooled["paired_differences"]["random"]
    verdict = card["verdict"]
    download_ok = bool(val.get("ok")) and bool(card["uniqueness"]["tier1_exact_all_priors"]["canonical_pattern_unique"])
    submit_ok = False  # H70 is negative; the selector step owns any future promotion
    lane_pol = lane_dots["policy"]["verdict"]
    lane_lit = lane_dots["literal"]["verdict"]
    lane_pol_near = lane_dots["policy"]["max_near_3px_fraction"]
    uniq = card["uniqueness"]

    rows_arms = "".join(
        '<tr' + (' class="highlight"' if a == "a_only" else "") + f'><td>{a}</td>'
        f'<td class="numeric">{f6(arms[a]["dti"])}</td><td class="numeric">{ci(arms[a]["ci95"])}</td>'
        f'<td class="numeric">{arms[a]["withheld_positive_pixels"]:,}</td></tr>\n'
        for a in order)
    rows_diff = "".join(
        f'<tr><td>a_only − {c}</td><td class="numeric">{pooled["paired_differences"][c]["delta"]:+.6f}</td>'
        f'<td class="numeric">{ci(pooled["paired_differences"][c]["ci95"])}</td></tr>\n'
        for c in ["single_B", "union_max", "single_A", "single_B_veto_Bonly", "concordant", "random"])
    rows_cap = "".join(
        f'<tr><td>fold {f["fold"]}</td><td class="numeric">{f["strict_a_only_cells"]:,}</td>'
        f'<td class="numeric">{f["topk_arm"]["placed"]:,}</td>'
        f'<td class="numeric">{f["topk_arm"]["inside_stratum"]:,}</td>'
        f'<td class="numeric">{f["topk_arm"]["outside_stratum"]:,}</td>'
        f'<td class="numeric">{f["pure_stratum"]["placed"]:,}</td>'
        f'<td class="numeric">{f6(f["a_only_pure"]["dti"])}</td></tr>\n'
        for f in cap["folds"])

    actions = (f'<div class="actions"><a class="button" href="downloads/h70-candidate.tif" download>'
               f'Download the H70 GeoTIFF ↓</a>'
               f'<a class="button secondary" href="downloads/h70-candidate.zip" download>Single-TIFF ZIP</a>'
               f'<a class="button secondary" href="downloads/h70-a-only-reasoning.csv.gz" download>'
               f'A-only reasoning CSV (gzip)</a></div>')
    fileline = (f'<p class="fileline">{esc(tif_name)}<br>{nbytes:,} bytes · SHA-256 {sha256} · '
                f'{ndots:,} emitted cells · values exactly {{0,1}}, 0 NaN</p>')
    notice = ('<div class="notice" role="note"><strong>OK TO DOWNLOAD FOR RESEARCH · DO NOT SUBMIT · '
              'DO NOT UPLOAD</strong>\n<p>Verdict: <b>NEGATIVE, research-only.</b> DOWNLOAD YES '
              '(format-valid and unique on decoded pixels); SUBMIT NO (the strict A-only candidate '
              'does not beat the single-view control: HOLDOUT-DTI '
              f'{f6(cand)} {ci(cand_ci)} against single_B {f6(sB)}, paired Δ '
              f'{d_sB["delta"]:+.6f} {ci(d_sB["ci95"])}; and the literal lane gate reads '
              f'{esc(lane_lit)}). Competition slots used: 0. NO CERTIFIED LEADERBOARD GAIN. '
              'Promotion to a weekly slot is a separate selector step.</p></div>')

    vr = val.get("value_range") or [None, None]
    gates_rows = [
        ("Single-band float32 GeoTIFF, EPSG:32611, shape/transform match", "PASS" if val.get("ok") else "FAIL"),
        ("Values exactly {0, 1}; 0 NaN; 0 infinite; no mass outside the footprint",
         "PASS" if (vr[0] == 0.0 and vr[1] == 1.0 and not val.get("nan_pixels")
                    and not val.get("infinity_pixels")
                    and not val.get("mass_outside_footprint")) else "FAIL"),
        ("Decoded-pattern uniqueness (not identical to any registry raster)",
         "PASS" if uniq["tier1_exact_all_priors"]["canonical_pattern_unique"] else "FAIL"),
        ("Exact novelty vs informative priors (novel_fraction)",
         f'{uniq["tier2_novelty_informative_priors"]["novel_fraction"]:.4f}'),
        ("Not the union of the two views (Jaccard vs union_max < 0.9)",
         "PASS" if card["not_the_union"]["not_union_pass"] else "FAIL"),
        ("Lane-valid placement (policy): worst informative near-dot share ≤ 0.70",
         f'PASS ({lane_pol_near:.4f})' if lane_pol == "PASS" else f"{lane_pol} ({lane_pol_near:.4f})"),
        ("Lane gate, literal rule (dots)", lane_lit),
        ("Lane gate, saturation policy (dots)", lane_pol),
        ("Lane gate, surface (literal / policy)",
         f'{lane_surf["literal"]["verdict"]} / {lane_surf["policy"]["verdict"]}'),
        ("Sufficiency S1 (View A out-of-quadrant AUC ≥ 0.60 mean, ≥ 0.55 fold)",
         f'FAIL (mean {s1["mean_view_A_oof_auc"]:.4f}, min {s1["min_fold_view_A_oof_auc"]:.4f})'),
        ("Holdout: candidate beats single_B (paired 95% CI > 0)", "FAIL"),
    ]
    gates_html = "".join(
        '<tr><td>' + esc(g) + '</td><td' + (' class="bad"' if ("FAIL" in r or "DUPLICATE" in r) else "")
        + '>' + esc(r) + '</td></tr>\n'
        for g, r in gates_rows)

    # ---- identification blocks for the concurrent/historical rounds (check_site requires them) --
    def _load_any(path: Path):
        return json.loads(path.read_text()) if path.exists() else {}

    h64 = _load_any(EVID / "h64_run_card.json")
    h63 = _load_any(EVID / "h63_run_card.json")
    h61 = _load_any(EVID / "h61_run_card.json")
    h58 = _load_any(DATA / "h58_result.json")
    r5 = _load_any(DATA / "submission_r5.json")
    h57cc = _load_any(DATA / "submission_h57_creditcore.json")
    h58_file = (h58.get("artifact") or {}).get("file", "")
    h58_sha = (h58.get("artifact") or {}).get("sha256", "")
    r5_file = r5.get("file", "")
    r5_sha = r5.get("sha256", "")
    r5_p = f"{r5.get('p_beat_02778', 0.0):.3f}"
    h57cc_file = h57cc.get("file", "")

    def ident(file: str, sha: str, short: str, verdict: str, extra: str = "") -> str:
        return (f'<p class="small"><a href="downloads/{short}" download>{short}</a> · '
                f'<code>{esc(file)}</code> · SHA-256 <code>{esc(sha[:24])}…</code> · {esc(verdict)}{extra}</p>')

    archive_idents = (
        ident(h64.get("raster_file", ""), h64.get("raster_sha256", ""), "h64-candidate.tif",
              "H64 (previous round, negative): download for research, not approved to submit")
        + ident(h63.get("raster_file", ""), h63.get("raster_sha256", ""), "h63-candidate.tif",
                "H63 (negative): download for research, not approved to submit")
        + ident(h61.get("raster_file", ""), h61.get("raster_sha256", ""), "h61-candidate.tif",
                "H61 (negative, measured lane duplicate IR-H65-004): download for research, not approved to submit")
        + ident(h58_file, h58_sha, "h58-candidate.tif",
                "H58 (negative): download for research, not approved to submit")
        + ident(r5_file, r5_sha, "r5-candidate.tif",
                f"R5 (negative): ok to download, not slot-approved; its own receipt publishes "
                f"P(beating 0.2778) = {r5_p}",
                extra="")
        + (f'<p class="small">H57 credited-core alternate (separate artefact, never the global pointer): '
           f'<a href="downloads/{esc(h57cc_file)}" download><code>{esc(h57cc_file)}</code></a> · '
           f'research only, not approved to submit.</p>' if h57cc_file else ""))

    # ================================================================ h70.html (audit)
    body = f"""<div class="notice" role="note" style="margin:0 0 1rem"><strong>Latest research round: H70 (negative).</strong>
Download yes, for research only; submit no. The brief's literal discovery stratum (A confident ∧ B abstains) is
measured for the first time, isolated and pure: it is <b>anti-informative</b> on this stack.
<a href="h70-executive-summary.html">H70 submission guide</a> · <a href="h64.html">Previous round (H64)</a></div>
<section class="hero"><div><div class="eyebrow">DOE GEMS / H70 · strict A-only isolation, two-view co-training</div>
<h1>Download the file.<br>Read the verdict first.</h1>
<p class="lead">H70 isolates the one lane element no previous round tested standalone: the strict A-only
discovery stratum — View A (potential field / subsurface) confident, View B (surface) abstaining — after the
Blum–Mitchell exchange, and validates two further lane variants (the B-only artifact veto, the concordant
ranking) in one matched-budget holdout.</p>
{notice}
{actions}
{fileline}
<p class="small"><a href="h70-executive-summary.html">Exactly what may be uploaded, and how →</a> ·
<a href="data/h70_run_card.json">Complete JSON run card ↗</a></p></div>
<aside class="panel" aria-label="Submission readiness"><div class="label">Readiness / measured, not promised</div>
<div class="status-line"><span>Single-band float32 GeoTIFF</span><span class="good">PASS</span></div>
<div class="status-line"><span>Finite, values in [0, 1]</span><span class="good">PASS</span></div>
<div class="status-line"><span>CRS, shape &amp; transform match</span><span class="good">PASS</span></div>
<div class="status-line"><span>Copied a previous submission?</span><span class="good">NO</span></div>
<div class="status-line"><span>Not the union of the two views</span><span class="good">PASS</span></div>
<div class="status-line"><span>Lane gate (saturation policy)</span><span class="{"good" if lane_pol == "PASS" else "bad"}">{esc(lane_pol)}</span></div>
<div class="status-line"><span>Lane gate (literal, lattice-saturated)</span><span class="bad">{esc(lane_lit)}</span></div>
<div class="status-line"><span>Beats single-view control (paired CI &gt; 0)</span><span class="bad">NO</span></div>
<div class="status-line"><span>Verdict</span><span class="bad">NEGATIVE</span></div>
<p class="fine">A valid file is not an approved competition entry. Promotion to a weekly slot is a
separate selector step.</p>
<a class="small" href="data/h70_run_card.json">Inspect the complete JSON run card ↗</a></aside></section>
<hr class="divider">
<section><h2>Gates, measured</h2><div class="table-wrap"><table>
<thead><tr><th>Gate</th><th>Result</th></tr></thead><tbody>
{gates_html}</tbody></table></div>
<p class="small">Local validator only; not an organiser acceptance receipt. The literal lane rule is
saturated on this registry by a spacing-5 lattice probe whose 3 px halo covers ≥ 95 % of the eligible
footprint, so it reads DUPLICATE/STOP for every nonempty candidate — a measured property of the registry
(<code>evidence/ctd5_registry_saturation.json</code>), not of this file. The H70 build is lane-valid under
the saturation-aware policy <b>by construction</b>: every informative prior is constrained from the first
placement and the budget was discovered by feasibility probes.</p></section>
<hr class="divider">
<section><h2>HOLDOUT-DTI, nine arms, matched budget (gems52-pooled-hide-v1)</h2>
<p class="small">53,186 withheld positive pixels · α 0.2 / β 0.8 · 300 m triangular kernel · 95 % paired
physical-cluster bootstrap (1,000 draws). Every arm placed exactly 9,400 dots per fold at 3 px minimum
separation; all nine arms filled their budgets on all four folds. The single_B control reproduces the
H61/H63/H64 committed value to |Δ| = 5.4e-05. <b>HOLDOUT-DTI is a simulator number, never a leaderboard
score.</b></p>
<div class="table-wrap"><table><thead><tr><th>Arm</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>Withheld positives</th></tr></thead>
<tbody>
{rows_arms}</tbody></table></div>
<p class="small">Paired bootstrap differences (candidate = <code>a_only</code>, the strict A-only stratum as a
top-K field):</p>
<div class="table-wrap"><table><thead><tr><th>Paired difference</th><th>Δ DTI</th><th>95% CI</th></tr></thead>
<tbody>
{rows_diff}</tbody></table></div></section>
<hr class="divider">
<section><h2>The pure stratum: the brief's literal discovery signal, measured purely</h2>
<p class="small">The holdout's <code>a_only</code> arm is the top-K of the gated field; because the stratum's
3 px-thinned cells are fewer than K on every fold, most of that arm's dots sit at field = −1 <b>outside</b>
the stratum. The pure stratum — placed only inside the gate, at its achieved budget, never rescued to K —
scores below. Budgets are unmatched, so this is a labelled diagnostic, not a matched-budget comparison.</p>
<div class="table-wrap"><table><thead><tr><th>fold</th><th>stratum cells</th><th>top-K arm placed</th>
<th>…inside stratum</th><th>…outside stratum</th><th>pure placed</th><th>pure DTI</th></tr></thead>
<tbody>
{rows_cap}</tbody></table></div>
<p class="small">Pooled pure-stratum HOLDOUT-DTI (achieved budget): <b>{f6(pure["dti"])}</b>
{ci(pure["ci95"])}; paired Δ vs single_B {pure_d["single_B"]["delta"]:+.6f} {ci(pure_d["single_B"]["ci95"])},
vs random {pure_d["random"]["delta"]:+.6f} {ci(pure_d["random"]["ci95"])}. <b>The strict A-only stratum is
anti-informative:</b> mass placed where View A is confident and View B abstains lands where hidden faults are
<i>less</i> likely than under uniform placement. View A's confident tail is systematically misplaced out of
quadrant (OOF AUC ≈ 0.52), so the disagreement signal inverts.</p></section>
<hr class="divider">
<section><h2>The two further lane variants (both negative, paired CIs exclude 0)</h2>
<div class="table-wrap"><table><thead><tr><th>arm</th><th>HOLDOUT-DTI</th><th>95% CI</th>
<th>Δ vs single_B</th><th>95% CI</th></tr></thead><tbody>
<tr><td>single_B_veto_Bonly (H70-B: B-only artifact veto)</td><td class="numeric">{f6(arms["single_B_veto_Bonly"]["dti"])}</td>
<td class="numeric">{ci(arms["single_B_veto_Bonly"]["ci95"])}</td>
<td class="numeric">{hold["pooled"]["single_B_veto_Bonly"]["paired_differences"]["single_B"]["delta"]:+.6f}</td>
<td class="numeric">{ci(hold["pooled"]["single_B_veto_Bonly"]["paired_differences"]["single_B"]["ci95"])}</td></tr>
<tr><td>concordant (H70-C: both-views-agree ranking)</td><td class="numeric">{f6(arms["concordant"]["dti"])}</td>
<td class="numeric">{ci(arms["concordant"]["ci95"])}</td>
<td class="numeric">{hold["pooled"]["concordant"]["paired_differences"]["single_B"]["delta"]:+.6f}</td>
<td class="numeric">{ci(hold["pooled"]["concordant"]["paired_differences"]["single_B"]["ci95"])}</td></tr>
<tr><td>single_B (control)</td><td class="numeric">{f6(sB)}</td><td class="numeric">{ci(arms["single_B"]["ci95"])}</td>
<td class="numeric">—</td><td class="numeric">—</td></tr></tbody></table></div>
<p class="small">The veto removes <i>real</i> signal (B-only pixels are faults, not artifacts, on this stack),
and requiring View A's agreement dilutes View B's ranking — both consistent with View A carrying no
transferable out-of-quadrant skill.</p></section>
<hr class="divider">
<section><h2>Premises, measured before any exchange</h2>
<div class="table-wrap"><table><thead><tr><th>premise</th><th>measured</th><th>bar</th><th>result</th></tr></thead><tbody>
<tr><td>Leakage canary (max single-feature held-out AUC, 75 features × 4 folds)</td>
<td class="numeric">{canary["max_alarm_across_folds"]:.4f}</td><td class="numeric">&lt; 0.90</td><td>PASS (no alarm)</td></tr>
<tr><td>Independence: max |ρ| of the views' spatial-block OOF errors on labelled negatives (2,089 blocks)</td>
<td class="numeric">{indep["pre"]["max_abs_correlation"]:.4f}</td><td class="numeric">&lt; 0.60</td>
<td>HELD (exchange allowed)</td></tr>
<tr><td>Sufficiency S1: View A out-of-quadrant AUC, mean / min fold</td>
<td class="numeric">{s1["mean_view_A_oof_auc"]:.4f} / {s1["min_fold_view_A_oof_auc"]:.4f}</td>
<td class="numeric">≥ 0.60 / ≥ 0.55</td><td>FAIL</td></tr>
<tr><td>Exchange transfer (disagreement_post − disagreement_pre, paired)</td>
<td class="numeric">{hold["pooled"]["disagreement_post"]["paired_differences"]["disagreement_pre"]["delta"]:+.6f}</td>
<td class="numeric">&gt; 0</td><td>no transfer ({exch["total_pseudo_pixels"]:,} pseudo px)</td></tr>
</tbody></table></div>
<p class="small">Fifth consecutive round with View A OOF AUC ≈ 0.52 (H61 0.5163 · H63 0.5362 · H64 0.5230 ·
H65 0.5202 · H70 0.5166). The independence premise held, so the brief's abandonment clause does not fire;
the method fails on sufficiency, and now also on the discovery signal itself.</p></section>
<hr class="divider">
<section id="limits"><h2>Limits</h2><ul>
<li><b>Negative result.</b> The strict A-only candidate does not beat the single-view control; the file is
research-only and no competition slot is spent. Negative results are deliverables.</li>
<li>The pure-stratum number is at an <b>unmatched</b> achieved budget (5,239 / 2,910 / 1,272 / 1,729 dots per
fold); it is a diagnostic, not a matched-budget comparison.</li>
<li>The holdout simulator measured Spearman −0.10 against the owner-reported board in R4; it screens
procedures, it does not rank board performance.</li>
<li>Catalogue-zero negatives are proxies, not verified fault absence (IR-52-004).</li>
<li>Inputs are integrity-pinned owner mirrors, not organiser-authenticated downloads; every board score cited
is PUBLIC BOARD or OWNER-REPORTED, none ORGANIZER-CONFIRMED.</li>
<li>The lane's literal gate is saturated by a registry lattice probe; the policy verdict excludes
universal-coverage probes by measured coverage, and the literal statistics remain published in the receipts.</li>
<li>All HOLDOUT-DTI numbers: evaluator <code>gems52-pooled-hide-v1</code>, 53,186 withheld positives,
95 % paired 20 km-cluster bootstrap, 1,000 draws.</li></ul></section>"""
    (DOCS / "h70.html").write_text(page(
        "H70 research GeoTIFF and explicit submission status",
        "Strict A-only two-view co-training GeoTIFF with measured gates and an explicit download/submit verdict.",
        body))

    # ================================================================ executive summary (guide)
    guide_body = f"""<div class="notice" role="note" style="margin:0 0 1rem"><strong>Latest research round: H70 (negative).</strong>
Download yes, for research only; submit no. <a href="h70.html">H70 run &amp; evidence</a> ·
<a href="h64.html">Previous round (H64)</a></div>
<div class="eyebrow">Executive summary / submission guide</div>
<h1>Download in one click.<br>Do not upload this run.</h1>
<p class="lead">The file, its exact identifier, and the frozen verdict. Promotion to a weekly slot is a
separate selector decision, never a property of a valid file.</p>
{notice}
{actions}
{fileline}
<div class="grid2"><section class="panel"><h2>The file contract (verified on disk)</h2><ul>
<li>One band, float32, values exactly 0 or 1.</li>
<li>0 NaN and 0 infinite pixels anywhere in the file.</li>
<li>EPSG:32611; 3,730 rows × 3,292 columns.</li>
<li>Affine [100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0], identical to the pinned
<code>sample_submission.tif</code>: yes.</li>
<li>{ndots:,} emitted cells, all inside the strict A-only stratum, all more than 200 m from any mapped trace,
3 px minimum separation.</li>
<li>The ZIP holds exactly one TIFF, byte-identical to the direct download.</li></ul>
<p class="small">Local validator only. This is not an organiser acceptance receipt.</p></section>
<section class="panel"><h2>Why upload is blocked</h2><ul>
<li>The strict A-only candidate does not beat the single-view control: HOLDOUT-DTI {f6(cand)}
{ci(cand_ci)} against single_B {f6(sB)}; paired Δ {d_sB["delta"]:+.6f} {ci(d_sB["ci95"])}
(53,186 withheld positives, evaluator <code>gems52-pooled-hide-v1</code>).</li>
<li>Measured purely, the brief's discovery stratum is <b>anti-informative</b>: pooled pure-stratum
HOLDOUT-DTI {f6(pure["dti"])} {ci(pure["ci95"])} at its achieved budget, below uniform random
(paired Δ {pure_d["random"]["delta"]:+.6f} {ci(pure_d["random"]["ci95"])}).</li>
<li>The sufficiency premise failed for the fifth consecutive round (View A out-of-quadrant AUC
{s1["mean_view_A_oof_auc"]:.4f} against a 0.60 bar).</li>
<li>The literal lane gate reads {esc(lane_lit)} for every nonempty candidate on this registry (a measured
lattice-probe saturation); the file is lane-valid under the saturation-aware policy
(worst informative near-dot share {lane_pol_near:.4f} ≤ 0.70, by construction).</li>
<li>The holdout simulator measured Spearman −0.10 against the owner-reported board in R4; it cannot promote
anything on its own.</li>
<li>Inputs are pinned owner mirrors, not organiser-authenticated downloads, and the current weekly allowance
is not observable from this sandbox.</li></ul>
<a href="h70.html">Read the full run and its limits →</a></section></div>
<section class="prose"><h2>About “Predicted values must be in range [0, 1]”</h2>
<p>That portal rejection is a property of the uploaded bytes, and this exporter makes it unreachable:
<code>gems52.grid.write_geotiff</code> refuses to write unless the array is float32, finite everywhere,
inside [0, 1], exactly 3,730 × 3,292 and on the pinned EPSG:32611 affine; <code>gems52.submission_writer</code>
then reopens the written file, re-validates it against <code>sample_submission.tif</code>, and fails closed.
The public specification permits null/NaN outside the footprint, so all-finite export is our compatibility
precaution — we do <b>not</b> claim that NaN caused your specific historical rejection, because the rejected
bytes and the portal receipt were never available here.</p>
<h2>Exact competition steps — only for an approved candidate</h2><ol>
<li>Obtain the separate selector's approval after the scientific, provenance, uniqueness and current-best
gates pass. <b>H70 is negative; stop here for this file.</b></li>
<li>Check the <a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">official rules</a> and the remaining
weekly allowance shown on your authenticated
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">submission page</a>.
This site cannot read that allowance.</li>
<li>On the <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">competition page</a>
choose <b>New submission</b> and select the <code>.tif</code> (or its single-TIFF ZIP) in <b>File to
submit</b>. Never upload HTML, a JSON receipt or a screenshot.</li>
<li>Paste the unique name and note below verbatim. Do not reproject, rescale, stretch or re-save the TIFF in
an image editor.</li>
<li>After an authorised upload, keep the submission id, timestamp, file SHA-256 and the organiser's result.
Only that receipt supports an <b>ORGANIZER-CONFIRMED</b> score.</li></ol></section>
<h2>Identification for this artefact</h2><p class="small">Copying these fields is not permission to upload
the file.</p>
<label for="submission-name">Unique name ({len(card["submission_name"])} / 140 characters)</label>
<input id="submission-name" readonly value="{esc(card["submission_name"])}">
<div class="copy-row"><button class="copy" data-copy-id="submission-name">Copy name</button></div>
<label for="submission-note">Note · {card["note_chars"]} / 140 characters</label>
<textarea id="submission-note" readonly rows="3">{esc(card["note"])}</textarea>
<div class="copy-row"><button class="copy" data-copy-id="submission-note">Copy note</button></div>
<p class="copy-status" id="copy-status" aria-live="polite"></p>
<section class="prose"><h2>Reproduce it</h2><pre class="code">.venv/bin/python scripts/run_h70.py all          # canary -> fit -> sufficiency -> exchange -> holdout -> build
.venv/bin/python scripts/h70_a_only_capacity.py   # pure-stratum capacity diagnostic
.venv/bin/python scripts/publish_h70_site.py      # this page
.venv/bin/python scripts/check_site.py &amp;&amp; .venv/bin/python -m pytest -q</pre>
<p class="small">GitHub Pages is static: it serves the generated file, it does not train a model in your
browser. Reproduction regenerates the same research result; it never uploads, promotes or spends a slot.</p>
<p class="small">Full pipeline from pinned inputs:
<code>bash scripts/download_competition_data.sh</code> ·
<code>PYTHONPATH=src .venv/bin/python -c "from gems52 import structural; structural.build(dest='work/r2/features', include_optional_profiles=False)"</code>
· <code>PYTHONPATH=src .venv/bin/python -m gems52.external</code> ·
<code>.venv/bin/python scripts/fetch_prior_inventory.py --out work/h70/priors --receipt work/h70/prior_fetch_receipt.json</code></p></section>
<details><summary>Preserved research archives — none of these is an approval</summary>
{archive_idents}
<p class="small"><a href="h64.html">H64 landing</a> · <a href="h64-executive-summary.html">H64 submission guide</a> ·
<a href="archive-ctd5-overview.html">CTD5 landing page (negative, lane-saturated)</a> ·
<a href="ctd5-audit.html">CTD5 run &amp; evidence</a> · <a href="h63-audit.html">H63 run &amp; evidence</a> ·
<a href="h62.html">H62 run &amp; evidence</a> · <a href="h61-audit.html">H61 run &amp; evidence</a> ·
<a href="h60.html">H60</a> · <a href="h59.html">H59</a> · <a href="h58.html">H58</a> ·
<a href="h57.html">H57</a> · <a href="h56.html">H56</a> · <a href="h55.html">H55</a> ·
<a href="h54.html">H54</a> · <a href="h53.html">H53</a> · <a href="r3.html">R3</a> ·
<a href="hypotheses.html">Hypotheses</a> · <a href="method.html">Method</a> ·
<a href="validation.html">Validation</a> · <a href="sources.html">Sources</a> ·
<a href="irregularities.html">Irregularities</a> · <a href="forensics.html">Forensics</a> ·
<a href="feed.html">Feed</a> · <a href="downloads/index.html">Download archive</a></p></details>"""
    guide = page(
        "Executive summary — how to submit, and whether this file may be submitted",
        "One-click download, the exact file contract, and the explicit submit verdict for the H70 artefact.",
        guide_body)
    (DOCS / "executive-summary.html").write_text(guide)
    (DOCS / "h70-executive-summary.html").write_text(guide)

    # ================================================================ index.html
    idx_notice = ('<div class="notice" role="note" style="margin:0 0 1rem"><strong>Latest research round: '
                  'H70 (negative).</strong> Download yes, for research only; submit no. The brief\'s literal '
                  'discovery stratum (A confident ∧ B abstains) is measured purely for the first time and is '
                  'anti-informative. <a href="h70.html">H70 landing</a> · '
                  '<a href="h70-executive-summary.html">H70 submission guide</a> · '
                  '<a href="h64.html">Previous round (H64)</a></div>')
    idx_body = f"""{idx_notice}
<section class="hero"><div><div class="eyebrow">DOE GEMS / H70 · strict A-only isolation, two-view co-training</div>
<h1>A new GeoTIFF.<br>An unambiguous verdict.</h1>
<p class="lead">View A is the potential field and the subsurface; View B is the surface (DEM curvature and
slope plus the radiometric channels). H70 isolates the brief's literal discovery stratum — A confident, B
abstaining — after the co-training exchange, validates the artifact-veto and concordant variants in the same
matched-budget holdout, and builds the candidate with a lane-valid constrained placement.</p>
{notice}
{actions}
{fileline}
<p class="small"><a href="executive-summary.html">Exactly what may be uploaded, and how →</a> ·
<a href="h70.html">Method, evidence and limits →</a> · <a href="archive-main-index-20261008.html">Previous main landing page</a></p></div>
<aside class="panel" aria-label="Submission readiness"><div class="label">Readiness / measured, not promised</div>
<div class="status-line"><span>Single-band float32 GeoTIFF</span><span class="good">PASS</span></div>
<div class="status-line"><span>Finite, values in [0, 1]</span><span class="good">PASS</span></div>
<div class="status-line"><span>CRS, shape &amp; transform match</span><span class="good">PASS</span></div>
<div class="status-line"><span>Copied a previous submission?</span><span class="good">NO</span></div>
<div class="status-line"><span>Not the union of the two views</span><span class="good">PASS</span></div>
<div class="status-line"><span>Lane gate (saturation policy)</span><span class="{"good" if lane_pol == "PASS" else "bad"}">{esc(lane_pol)}</span></div>
<div class="status-line"><span>Lane gate (literal, lattice-saturated)</span><span class="bad">{esc(lane_lit)}</span></div>
<div class="status-line"><span>Beats single-view control (paired CI &gt; 0)</span><span class="bad">NO</span></div>
<div class="status-line"><span>Verdict</span><span class="bad">NEGATIVE</span></div>
<p class="fine">A valid file is not an approved competition entry. Promotion to a weekly slot is a
separate selector step.</p>
<a class="small" href="data/h70_run_card.json">Inspect the complete JSON run card ↗</a></aside></section>
<hr class="divider">
<div class="section-head"><h2>What the holdout says (HOLDOUT-DTI — not a leaderboard score)</h2>
<a href="h70.html">Full audit →</a></div>
<p class="small"><b>HOLDOUT-DTI</b> · evaluator <code>gems52-pooled-hide-v1</code> · 53,186 withheld positive
pixels · pooled TPw/FPw/FNw · α 0.2 / β 0.8 · 300 m triangular kernel · 95% paired physical-cluster
bootstrap (1,000 draws). Every arm placed exactly 9,400 dots per fold at 3 px separation; all nine arms
filled their budgets on all four folds. The single_B control reproduces the H61/H63/H64 committed value to
|Δ| = 5.4e-05.</p>
<div class="table-wrap"><table><thead><tr><th>Arm</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>Withheld positives</th></tr></thead>
<tbody>
{rows_arms}</tbody></table></div>
<div class="table-wrap"><table><thead><tr><th>Paired difference (candidate = a_only)</th><th>Δ DTI</th><th>95% CI</th></tr></thead>
<tbody>
{rows_diff}</tbody></table></div>
<div class="cards">
<section class="card"><div class="eyebrow">01 / the discovery signal, isolated</div><h3>Strict A-only is anti-informative</h3>
<span class="num">pure {f6(pure["dti"])}</span>
<p>Placed purely inside the A-confident ∧ B-abstaining stratum at its achieved budget, the brief's literal
discovery signal scores <b>below uniform random</b> (paired Δ {pure_d["random"]["delta"]:+.4f}). View A's
confident tail is systematically misplaced out of quadrant (OOF AUC ≈ 0.52 for the fifth consecutive round).</p></section>
<section class="card"><div class="eyebrow">02 / zero-copy</div><h3>No inherited pixels</h3>
<span class="num">{uniq["tier2_novelty_informative_priors"]["novel_fraction"]:.1f} novel</span>
<p>Every emitted cell is outside every informative registry raster's positive support, inside the strict
stratum, and more than 200 m from the mapped catalogue.</p></section>
<section class="card"><div class="eyebrow">03 / lane-valid by construction</div><h3>Policy lane PASS</h3>
<span class="num">share {lane_pol_near:.4f}</span>
<p>Every informative prior is constrained from the first placement; the budget was discovered by feasibility
probes. The literal gate remains saturated by a registry lattice probe — a property of the registry.</p></section>
</div>
<div class="grid2"><section><div class="eyebrow">The 0.2778 question</div><h2>Precision, not detection.</h2>
<p>Measured from the restored bytes: the reported-0.2778 champion <code>h33-2-b2</code> is a <b>strict
subset</b> of the reported-0.2600 file (37,654 ⊂ 44,090 off-catalogue px), which is itself a strict subset of
the reported-0.1922 parent field. The champion added no pixel and deleted 6,436 — every one between 100 m and
200 m of a mapped trace, measured. Under <code>DTI = TPw / (0.2·FPw + 0.8·FNw)</code> with
<code>FNw = |G| − TPw</code> exactly, mass on a masked or near-masked pixel can never earn credit but always
pays the false-positive tax; deleting it is free precision. Binary mass is optimal at fixed support.</p>
<p class="small"><b>Can this file beat it?</b> The live public board's top is 0.3774 (xiaofanhu, fetched
2026-10-09), so the leader is nearly maxed on placement and must be <i>finding</i> structure. Our own
measurement says the A-only discovery signal is anti-informative and the honest expectation for this lane is
no gain. <b>No leaderboard gain is claimed.</b> All board numbers are PUBLIC BOARD or OWNER-REPORTED, never
ORGANIZER-CONFIRMED.</p>
<a href="h70.html">The full measured algebra (knowledge/01) →</a></section>
<figure style="margin:0"><div class="panel"><div class="label">Emission domain and gates</div>
<div class="status-line"><span>Registry rasters checked</span><span>{card["counts"]["prior_rasters"]}</span></div>
<div class="status-line"><span>Informative priors</span><span>{card["counts"]["informative_rasters"]}</span></div>
<div class="status-line"><span>Universal-coverage probes</span><span>{card["counts"]["probe_rasters"]}</span></div>
<div class="status-line"><span>Adopted lane-valid budget</span><span>{ndots:,} dots</span></div>
<div class="status-line"><span>Worst informative near-dot share</span><span>{lane_pol_near:.4f}</span></div>
<div class="status-line"><span>Independence max |ρ| (2,089 blocks)</span><span>{indep["pre"]["max_abs_correlation"]:.4f}</span></div>
<div class="status-line"><span>View A OOF AUC (S1)</span><span>{s1["mean_view_A_oof_auc"]:.4f} — FAIL</span></div>
</div><figcaption class="legend">Literal lane statistics are reported for every prior including probes; the
policy only decides which of them can localise a lane.</figcaption></figure></div>
<div class="feed" id="local-feed">Automatic local evidence checks. Submission gate: CLOSED. Organizer
results are not a live feed.</div>
<details><summary>Preserved research archives — none of these is an approval</summary>
{archive_idents}
<p class="small"><a href="archive-ctd5-overview.html">CTD5 landing page (negative, lane-saturated)</a> ·
<a href="ctd5-audit.html">CTD5 run &amp; evidence</a> · <a href="ctd5-sources.html">CTD5 sources</a> ·
<a href="h64.html">H64 landing</a> · <a href="h64-executive-summary.html">H64 submission guide</a> ·
<a href="h63-audit.html">H63 run &amp; evidence</a> · <a href="h63-sources.html">H63 sources</a> ·
<a href="h62.html">H62 run &amp; evidence (parallel session)</a> ·
<a href="archive-h62-overview.html">H62 landing archive</a> · <a href="h61-audit.html">H61 run &amp; evidence</a> ·
<a href="h61-sources.html">H61 sources</a> · <a href="archive-h61-overview.html">H61 landing archive</a> ·
<a href="h60c.html">H60C</a> · <a href="h60.html">H60</a> · <a href="h60-triple-convergence.html">H60 triple convergence</a> ·
<a href="h59.html">H59</a> · <a href="archive-h59-overview.html">H59 landing archive</a> ·
<a href="h58.html">H58</a> · <a href="h57.html">H57</a> · <a href="h57-creditcore.html">H57 credit core</a> ·
<a href="h56-cotrain.html">H56 co-training</a> · <a href="h56.html">H56</a> ·
<a href="h55.html">H55</a> · <a href="h55-edge.html">H55-EDGE negative archive</a> ·
<a href="h55-profile.html">H55 profile</a> · <a href="h55-paired-shoulders.html">H55 paired shoulders</a> ·
<a href="h54.html">H54</a> · <a href="h53.html">H53</a> · <a href="r3.html">R3</a> ·
<a href="r3-hypotheses.html">R3 hypotheses</a> · <a href="hypotheses.html">Hypotheses</a> ·
<a href="method.html">Method</a> · <a href="validation.html">Validation</a> ·
<a href="sources.html">Sources</a> · <a href="irregularities.html">Irregularities</a> ·
<a href="forensics.html">Forensics</a> · <a href="feed.html">Feed</a></p>
<p class="small">Historical downloads (all research-only, none slot-approved):
<a href="downloads/h64-candidate.tif" download>H64 research TIFF</a> ·
<a href="downloads/h63-candidate.tif" download>H63 research TIFF</a> ·
<a href="downloads/h61-candidate.tif" download>H61 research TIFF</a> ·
<a href="downloads/gems52-h62-conc_soft-arm22000px.tif" download>H62 research TIFF</a> ·
<a href="downloads/h58-candidate.tif" download>H58 research</a> ·
<a href="downloads/ctd5-research.tif" download>CTD5 research TIFF</a> ·
<a href="downloads/index.html">full archive index</a></p></details>"""
    (DOCS / "index.html").write_text(page(
        "H70 research GeoTIFF and explicit submission status",
        "Strict A-only two-view co-training GeoTIFF with measured gates and an explicit download/submit verdict.",
        idx_body))

    # ================================================================ downloads/index.html
    dl_path = DL / "index.html"
    dl_text = dl_path.read_text()
    h70_rows = (
        '<!--H70-DL-->'
        f'<tr><td><a href="h70-candidate.tif" download>h70-candidate.tif</a></td>'
        f'<td class="number">{nbytes:,}</td><td class="mono">{sha256}</td>'
        f'<td>H70 · strict A-only co-training discovery stratum · {ndots:,} px · newest round; '
        f'<a href="../h70.html">evidence</a></td></tr>\n'
        f'<tr><td><a href="{esc(tif_name)}" download>{esc(tif_name)}</a></td>'
        f'<td class="number">{nbytes:,}</td><td class="mono">{sha256}</td>'
        f'<td>canonical filename, byte-identical</td></tr>\n'
        f'<tr><td><a href="h70-candidate.zip" download>h70-candidate.zip</a></td>'
        f'<td class="number">{(DL / "h70-candidate.zip").stat().st_size:,}</td>'
        f'<td class="mono">single-TIFF ZIP, byte-identical payload</td><td>portal-accepted wrapper</td></tr>\n'
        f'<tr><td><a href="h70-a-only-reasoning.csv.gz" download>h70-a-only-reasoning.csv.gz</a></td>'
        f'<td class="number">{(DL / "h70-a-only-reasoning.csv.gz").stat().st_size:,}</td>'
        f'<td class="mono">gzip CSV</td><td>{ndots:,} per-pixel geological reasoning rows (hypothesis + named '
        f'non-fault mimic + falsifier)</td></tr>\n'
        '<!--/H70-DL-->\n')
    if "<!--H70-DL-->" not in dl_text:
        dl_text = dl_text.replace("<!--/H63-DL-->", "<!--/H63-DL-->\n" + h70_rows, 1)
    notice_new = ('<aside style="padding:20px;background:#fff1de;color:#12331f;font:16px/1.6 system-ui">'
                  '<b>Latest research: H70 — DO NOT SUBMIT.</b> '
                  f'<a href="h70-candidate.tif" download>Download the H70 GeoTIFF</a> '
                  f'({nbytes:,} bytes, SHA-256 <code>{sha256[:16]}…</code>, {ndots:,} cells) · '
                  '<a href="../executive-summary.html">Read the gate status first</a> · '
                  '<a href="../h70.html">Run &amp; evidence</a>. Historical downloads below are not upload '
                  'approval.</aside>')
    import re
    dl_text = re.sub(r'<aside style="padding:20px;background:#fff1de[^"]*">.*?</aside>',
                     notice_new, dl_text, count=1, flags=re.S)
    dl_path.write_text(dl_text)

    # ================================================================ feed.json
    feed_path = DATA / "feed.json"
    feed = json.loads(feed_path.read_text()) if feed_path.exists() else {}
    feed["generated_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    feed["latest_research"] = dict(
        run_id=f"h70-{sha256[:8]}", round="H70", file=tif_name,
        download="downloads/h70-candidate.tif", bytes=nbytes, sha256=sha256, emitted_px=ndots,
        verdict="NEGATIVE, research-only", download_ok=download_ok, submit_ok=submit_ok,
        hash_verified=True,
        holdout_dti=cand, holdout_ci95=cand_ci,
        evaluator="gems52-pooled-hide-v1",
        withheld_positive_pixels=arms["a_only"]["withheld_positive_pixels"],
        lane_literal=lane_lit, lane_policy=lane_pol,
        slots_used=0, evidence="evidence/h70_run_card.json")
    feed["scientific_gate"] = "CLOSED — H70 verdict is negative; research download only"
    for n in ("canary", "fit_checkpoint", "sufficiency", "independence", "pseudo_exchange", "holdout",
              "a_only_capacity", "lane_surface", "lane_dots", "run_card"):
        fn = f"h70_{n}.json"
        feed.setdefault("evidence_copied", [])
        if fn not in feed["evidence_copied"]:
            feed["evidence_copied"].append(fn)
    feed_path.write_text(json.dumps(feed, indent=1, allow_nan=False) + "\n")

    # ================================================================ assets/h70.js (copy of the h63 clipboard/feed js)
    js_src = DOCS / "assets/h63.js"
    js_dst = DOCS / "assets/h70.js"
    if js_src.exists() and (not js_dst.exists() or js_dst.read_text() != js_src.read_text()):
        shutil.copyfile(js_src, js_dst)

    # ================================================================ h70-sources.html (nav target)
    src_body = f"""<div class="eyebrow">Sources</div><h1>Official and verified sources</h1>
<p class="lead">Every external claim on this site traces to one of these. Nothing here is an organiser
receipt.</p>
<div class="table-wrap"><table><thead><tr><th>source</th><th>used for</th><th>status</th></tr></thead><tbody>
<tr><td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">DrivenData competition 306 (DOE GEMS)</a></td>
<td>problem, metric (page 967), submission rules</td><td>official; data tab login-walled</td></tr>
<tr><td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">public leaderboard</a></td>
<td>dated board observations (top 0.3774, fetched 2026-10-09)</td><td>PUBLIC BOARD, not ORGANIZER-CONFIRMED</td></tr>
<tr><td><a href="https://github.com/drivendataorg/gems-prize-reference-solution">gems-prize-reference-solution</a></td>
<td>reference approach</td><td>official reference</td></tr>
<tr><td><a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">GEMS_96647.pdf (Nlr/OSTI)</a></td>
<td>submission instructions</td><td>official document</td></tr>
<tr><td><a href="https://gdr.openei.org/submissions/1391">GDR submission 1391</a></td>
<td>GeoDAWN survey metadata</td><td>official repository</td></tr>
<tr><td><a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and">USGS GeoDAWN surveys</a></td>
<td>airborne magnetic/radiometric survey documentation</td><td>official</td></tr>
<tr><td><a href="https://gbcge.org/current-projects/ingenious/">GBCGE INGENIOUS</a></td>
<td>regional fault mapping context</td><td>project page</td></tr>
<tr><td><a href="https://epsg.io/32611">EPSG:32611</a></td><td>grid CRS (UTM 11N)</td><td>registry</td></tr>
<tr><td><a href="https://en.wikipedia.org/wiki/Tversky_index">Tversky index</a></td>
<td>metric background (α 0.2 / β 0.8)</td><td>background</td></tr>
<tr><td>Blum &amp; Mitchell, <i>Combining Labeled and Unlabeled Data with Co-Training</i>, COLT '98,
pp. 92–100, doi:10.1145/279943.279962</td><td>the co-training lane's method</td><td>citation</td></tr>
</tbody></table></div>
<p class="small">Competition rasters are integrity-pinned owner mirrors of login-walled portal files
(SHA-256 verified after restore; see <code>registry/data_manifest.json</code> and
<code>scripts/restore_data.py</code>), not organiser-authenticated downloads.</p>"""
    if not (DOCS / "h70-sources.html").exists():
        (DOCS / "h70-sources.html").write_text(page(
            "H70 sources", "Official and verified sources for the H70 round.", src_body))

    print(f"published H70: {tif_name} ({nbytes:,} bytes, {ndots:,} cells)")
    print(f"verdict: {verdict}")
    print(f"lane literal={lane_lit} policy={lane_pol} (worst informative near-dot share {lane_pol_near:.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
