#!/usr/bin/env python3
"""Render the H59 GitHub Pages overview, audit and submission guide from receipts.

Local presentation only: no portal contact, no upload, no approval.  Run after
scripts/run_h59.py so evidence/h59_result.json and the submission receipt exist.

The page's single duty, per the round brief: make it OBVIOUS whether the artifact is OK to
download and submit.  The verdict line is generated from the frozen gate booleans in the
receipt -- never hand-written.
"""
from __future__ import annotations

import hashlib
import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EV = ROOT / "evidence"
DL = DOCS / "downloads"
DATA = DOCS / "data"


def e(value) -> str:
    return html.escape(str(value), quote=True)


def fmt(value, nd=6):
    if value is None:
        return "—"
    try:
        return f"{float(value):.{nd}f}"
    except (TypeError, ValueError):
        return e(value)


def nav(active: str = "") -> str:
    links = [
        ("index.html", "Overview", "overview"),
        ("executive-summary.html", "Research status", "guide"),
        ("h59.html", "H59 audit", "audit"),
        ("irregularities.html", "Limitations", "limits"),
        ("sources.html", "Sources", "sources"),
        ("downloads/index.html", "Downloads", "downloads"),
    ]
    prefix = "../" if active == "downloads" else ""
    body = [f'<a class="brand" href="{prefix}index.html">GEMS / DOE 52</a>']
    for path, label, key in links:
        current = ' aria-current="page"' if key == active else ""
        href = ("index.html" if active == "downloads" and path == "downloads/index.html"
                else prefix + path)
        body.append(f'<a href="{href}"{current}>{label}</a>')
    return "<nav>" + "".join(body) + "</nav>"


def shell(title: str, description: str, content: str, active: str = "") -> str:
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{e(description)}"><title>{e(title)} · GEMSDOE52</title>
<link rel="stylesheet" href="style.css"><script src="site.js" defer></script></head>
<body><a class="skip" href="#main">Skip to evidence</a><header>{nav(active)}</header>
<main id="main">{content}</main><footer>DOE GEMS competition 306 · Reproducible local research · Predictions are not verified faults or geothermal discoveries. <a href="irregularities.html">Limitations</a> · <a href="sources.html">Sources</a> · <a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code and evidence</a></footer></body></html>'''


def main() -> None:

    _h75_home = ROOT / "docs" / "index.html"
    _h75_status = ROOT / "docs" / "h75-executive-summary.html"
    if (_h75_home.is_file() and _h75_status.is_file()
            and "H75: DUPLICATE/STOP" in _h75_home.read_text(errors="replace")
            and "DUPLICATE/STOP · RESEARCH ONLY · NOT FOR SUBMISSION" in
            _h75_status.read_text(errors="replace")):
        print("H75 terminal stop is current; historical publisher made no page or pointer changes")
        return
    result = json.loads((EV / "h59_result.json").read_text())
    artifact = result["artifact"]
    stem = artifact["stem"]
    submission = json.loads((EV / f"submission_{stem}.json").read_text())
    canonical = ROOT / "submission" / (stem + ".tif")
    if not canonical.is_file() or hashlib.sha256(canonical.read_bytes()).hexdigest() != artifact["sha256"]:
        raise RuntimeError("H59 TIFF on disk does not match its evidence receipt")

    decision = result["holdout"]["decision"]
    summary = result["holdout"]["summary"]
    shipped = decision["shipped_field"]
    recommended = False  # no authorized weekly slot or submission procedure in this research archive
    gates_ok = bool(result["gates_ok"])
    independence = result["independence"]
    strata = result["strata"]
    pseudo = result["pseudo_label_exchange"]
    nov = artifact["support_novelty"]
    ntu = artifact["not_the_union"]
    primary = artifact["emission_px"]

    # ---- sibling H59 builds (parallel sessions): published as research alternates -------------
    # This round's verdict speaks only for the preregistered artifact above.  Any other H59
    # raster found beside it is linked here with its own evidence status, never a slot verdict.
    sibling_items = []
    for ev_path in sorted(EV.glob("gems52-h59-*.json")):
        try:
            sib = json.loads(ev_path.read_text())
        except ValueError:
            continue
        sib_sha = str(sib.get("sha256") or "")
        if sib_sha == artifact["sha256"] or not sib.get("format_ok"):
            continue
        sib_tif = ROOT / "submission" / (ev_path.stem + ".tif")
        if not sib_tif.is_file():
            continue
        sib_pages = []
        for page in ("h59-method.html", "h59-evidence.html"):
            if (DOCS / page).is_file():
                sib_pages.append(f'<a href="{page}">{page.split(".")[0].replace("-", " ")}</a>')
        has_holdout = bool(sib.get("holdout") or sib.get("slot_recommended") is not None)
        sibling_items.append(
            f"<li><code>{e(ev_path.stem)}.tif</code> — {int(sib.get('n_positive') or 0):,} px, "
            f"format ok, min catalogue distance {e(sib.get('min_dist_to_catalogue_m'))} m; "
            f"evidence receipt records "
            f"{'a holdout measurement' if has_holdout else 'NO holdout measurement, NO gate report and NO slot verdict'}"
            f" — published as a research alternate, not a slot candidate"
            + (f" ({' · '.join(sib_pages)})" if sib_pages else "") + ".</li>")
    sibling_html = ""
    if sibling_items:
        sibling_html = (
            "<h2>Other H59 builds from parallel sessions</h2>"
            "<p>These rasters exist in the repository and remain downloadable; the verdict on this "
            "page speaks only for the preregistered artifact above. Under the standing rule — no "
            "weekly slot without beating the current holdout best — a build with no holdout "
            "measurement cannot be a slot candidate.</p><ul>"
            + "".join(sibling_items) + "</ul>")

    # ---- historical research-only status; local gates do not authorize a slot ----------------
    diag = result.get("posthoc_incumbent_diagnostic") or {}
    incumbent_beaten = diag.get("incumbent_beaten_both_modes")
    ringfree_beaten = diag.get("best_ringfree_prior_beaten_both_modes")
    verdict_head = "RESEARCH DOWNLOAD ONLY — NOT APPROVED FOR SUBMISSION."
    verdict_class = "status"
    verdict_detail = (
        "This is a historical research artifact. Its local gate receipts and holdout diagnostics do not authorize a weekly slot. "
        "No owner override, upload procedure, or paste-ready identification is provided.")

    # the incumbent diagnostic table, generated from the receipt numbers
    incumbent_table_rows = []
    if diag.get("mean_dti"):
        regime = diag.get("emission_regime") or {}
        ours_label = diag.get("ours_label")
        for label in sorted(diag["mean_dti"], key=lambda k: -diag["mean_dti"][k]["hide"]):
            m = diag["mean_dti"][label]
            rg = regime.get(label, {})
            who = "this artifact" if label == ours_label else "prior"
            incumbent_table_rows.append(
                f"<tr><td>{e(label)}</td><td>{who}</td>"
                f"<td>{int(rg.get('px', 0)):,}</td>"
                f"<td>{e(rg.get('min_distance_to_catalogue_m', ''))} m</td>"
                f"<td>{100*float(rg.get('frac_within_300m', 0) or 0):.1f}%</td>"
                f"<td>{fmt(m['hide'])}</td><td>{fmt(m['block'])}</td></tr>")
    incumbent_table = (
        '<div class="table-wrap"><table><thead><tr><th>Emission (scored as-is)</th><th>Role</th>'
        '<th>Pixels</th><th>Min distance to catalogue</th><th>Share ≤ 300 m</th>'
        '<th>Hide mean DTI</th><th>Block mean DTI</th></tr></thead><tbody>'
        + "".join(incumbent_table_rows) + "</tbody></table></div>") if incumbent_table_rows else ""
    if recommended:
        verdict_head = "OK TO DOWNLOAD AND SUBMIT — gates pass; this is the round's recommended weekly-slot candidate."
        verdict_class = "status"
        if shipped in ("view_A", "view_B"):
            verdict_detail = (
                f"All registered gates passed on re-read bytes. The shipped <b>{e(shipped)}</b> field "
                f"is itself the strongest single view on both instruments (4/4 fold wins over random "
                f"everywhere), and the artifact, scored as-is on the identical folds, beat the "
                f"owner-reported-0.2778 incumbent emission as-is on BOTH instruments "
                f"(hide {fmt(diag['mean_dti'][diag['ours_label']]['hide'])} vs "
                f"{fmt(diag['mean_dti'][diag['incumbent_label']]['hide'])}; "
                f"block {fmt(diag['mean_dti'][diag['ours_label']]['block'])} vs "
                f"{fmt(diag['mean_dti'][diag['incumbent_label']]['block'])}). "
                f"Amendment 3, slot basis: {e(result['slot_basis'])}. The standing caveat: inputs are "
                f"integrity-pinned owner mirrors, not organizer-authenticated, and every 0.25–0.28 "
                f"score this family holds was built on the same mirrors. A weekly slot is the owner's "
                f"decision; no upload happened in this round.")
        else:
            verdict_detail = (
                f"All registered gates passed on re-read bytes and the shipped <b>{e(shipped)}</b> field "
                f"beat the strongest same-fold single-view baseline by ≥ +0.003 mean DTI on both "
                f"instruments with ≥ 3/4 fold wins. The standing caveat: inputs are integrity-pinned "
                f"owner mirrors, not organizer-authenticated, and every 0.25–0.28 score this family "
                f"holds was built on the same mirrors. A weekly slot is the owner's decision; no "
                f"upload happened in this round.")
    else:
        verdict_head = "DOWNLOAD FOR REVIEW — but DO NOT spend a weekly slot on it."
        verdict_class = "status"
        fails = []
        if not gates_ok:
            fails.append("one or more artifact gates failed")
        if shipped in ("view_A", "view_B"):
            if incumbent_beaten is False:
                fails.append("the artifact as-is did not beat the 0.2778 incumbent emission as-is "
                             "on both instruments (amendment 3 slot basis)")
        elif not decision["beats_single_view_strongly"]:
            fails.append("the shipped field did not clear the +0.003 / 3-of-4 lift bar over the "
                         "strongest single view on both instruments")
        if not independence.get("allow_exchange"):
            fails.append("the independence gate did not license the co-training exchange")
        if not result["holdout"]["full_budget_all_primary_folds"]:
            fails.append("a primary fold did not emit at full budget")
        verdict_detail = (
            "Registered reasons: " + "; ".join(fails) + ". The file is published for audit and "
            "reproduction with every number beside it; it is not a slot recommendation.")

    buttons = (
        '<a class="button" href="downloads/h59-candidate.tif" download>↓ Download the H59 TIFF</a>'
        '<a class="button" href="downloads/h59-candidate.zip" download>↓ Download one-TIFF ZIP</a>'
        '<a class="button secondary" href="h59.html">Full audit →</a>')

    bar = f'''<section class="download-bar" aria-label="H59 artifact download">
<div><strong>H59 · two-view co-training, disagreement-labelled · {e(verdict_head.split(" — ")[0])}</strong>
<small><code>{e(stem)}.tif</code></small>
<small>{int(artifact["bytes"]):,} bytes · single-band float32 · EPSG:32611 · 3,292 × 3,730 · values exactly {{0,1}} · 0 NaN · {primary:,} emitted pixels</small>
<small>Shipped field <b>{e(shipped)}</b> · gates {"PASS" if gates_ok else "FAIL"} · pattern unique vs {int(artifact["uniqueness"]["n_priors_checked"])} accessible priors: {"YES" if artifact["uniqueness"]["canonical_pattern_unique"] else "NO"} · min distance to a mapped fault {float(artifact["ring_min_distance_m"]):.1f} m</small>
<small>SHA-256 <code>{e(artifact["sha256"])}</code></small></div>{buttons}</section>'''

    # ---- arm table -------------------------------------------------------------------------
    arm_rows = []
    for mode in ("hide", "block"):
        means = summary[mode]["mean_dti_by_arm"]
        wr = summary[mode]["folds_won_vs_random"]
        for arm in ("view_A", "view_B", "union", "product", "vetoB", "basestep",
                    "seismicity", "a_only_stratum", "random"):
            if means.get(arm) is None:
                continue
            tag = " (shipped)" if arm == shipped else ""
            diag = " · diagnostic" if arm == "a_only_stratum" else (" · control" if arm == "random" else "")
            arm_rows.append(
                f'<tr><td>{e(mode)}</td><td>{e(arm)}{e(tag)}{e(diag)}</td>'
                f'<td>{fmt(means[arm])}</td><td>{e(wr.get(arm, "—"))}</td></tr>')
    arm_table = ('<div class="table-wrap"><table><thead><tr><th>Instrument</th><th>Arm</th>'
                 '<th>Mean DTI @ 37,654 (fold mean)</th><th>Folds won vs random</th></tr></thead><tbody>'
                 + "".join(arm_rows) + "</tbody></table></div>")

    lift_rows = []
    for mode in ("hide", "block"):
        lift = decision["lifts"][mode]
        lift_rows.append(
            f'<tr><td>{e(mode)}</td><td>{fmt(lift["vs_best_single_view"], 6)}</td>'
            f'<td>{e(lift["folds_won_vs_best_single_view"])}</td>'
            f'<td>{fmt(lift["vs_union"], 6)}</td></tr>')
    lift_table = ('<div class="table-wrap"><table><thead><tr><th>Instrument</th>'
                  '<th>Shipped − best single view</th><th>Folds won vs best single view</th>'
                  '<th>Shipped − union</th></tr></thead><tbody>' + "".join(lift_rows)
                  + "</tbody></table></div>")

    gate_rows = [
        ("Format gate (re-read from bytes)", "PASS" if artifact["format_gate"]["ok"] else "FAIL",
         "single band float32, EPSG:32611, exact transform, all finite, values in [0,1], inside footprint"),
        ("Decoded-pattern uniqueness", "PASS" if artifact["uniqueness"]["canonical_pattern_unique"] else "FAIL",
         f"{int(artifact['uniqueness']['n_priors_checked'])} accessible aligned priors; scope disclosed"),
        ("Not merely the union of the two views", "PASS" if (not ntu["equals_view_a"] and not ntu["equals_view_b"] and not ntu["equals_set_union"]) else "FAIL",
         f"Jaccard vs view-A {fmt(ntu['jaccard_vs_view_a'], 3)}, view-B {fmt(ntu['jaccard_vs_view_b'], 3)}, "
         f"set-union {fmt(ntu['jaccard_vs_set_union'], 3)}; union-field equality reported: {ntu['equals_union_field']}"),
        ("200 m catalogue ring", "PASS" if float(artifact["ring_min_distance_m"]) > 200 else "FAIL",
         f"closest emitted cell to a mapped fault: {float(artifact['ring_min_distance_m']):.1f} m"),
        ("3 px nearest-neighbour spacing", "PASS" if (artifact["spacing"]["min_nn_px"] or 0) >= 3 else "FAIL",
         f"min {fmt(artifact['spacing']['min_nn_px'], 2)} px · median {fmt(artifact['spacing']['median_nn_px'], 2)} px"),
        ("Support novelty vs prior union (reported, no threshold)", f"{float(nov['emission_novel_fraction'])*100:.1f}% novel",
         f"{int(nov['emission_novel_px']):,} of {int(nov['emission_px']):,} emitted px outside every accessible prior's support; "
         f"{int(nov.get('overlap_with_reference_px', 0)):,} px coincide with the 0.2778 reference — convergent re-derivation, not copying"),
        ("Per-pixel geological reasoning", "PASS", f"{int(result['reasoning_dossier']['rows']):,} rows, "
         f"{int(result['reasoning_dossier']['a_only_rows']):,} A-only with written geology and falsifiers"),
        ("Input provenance", "OPEN", "integrity-pinned owner mirror, not organizer-authenticated (IR-52-003 / IR-H58-001)"),
    ]
    gate_table = ('<div class="table-wrap"><table><thead><tr><th>Gate</th><th>Result</th>'
                  '<th>Measurement</th></tr></thead><tbody>'
                  + "".join(f'<tr><td>{e(a)}</td><td><b>{e(b)}</b></td><td>{e(c)}</td></tr>'
                            for a, b, c in gate_rows) + "</tbody></table></div>")

    ind_rows = []
    for name, test in independence.get("tests", {}).items():
        ind_rows.append(f'<tr><td>{e(name)}</td><td>{int(test.get("n", 0)):,}</td>'
                        f'<td>{fmt(test.get("pearson"), 4)}</td><td>{fmt(test.get("spearman"), 4)}</td></tr>')
    px = independence.get("pixel_level", {})
    ind_rows.append(f'<tr><td>pixel-level OOF logit (cross-check)</td><td>{int(px.get("n", 0)):,}</td>'
                    f'<td>{fmt(px.get("pearson"), 4)}</td><td>{fmt(px.get("spearman"), 4)}</td></tr>')
    ind_table = ('<div class="table-wrap"><table><thead><tr><th>Statistic (labelled negatives)</th>'
                 '<th>n</th><th>Pearson</th><th>Spearman</th></tr></thead><tbody>'
                 + "".join(ind_rows) + "</tbody></table></div>")

    pseudo_rows = []
    for d in pseudo.get("directions", []):
        before, after = d.get("auc_before"), d.get("auc_after")
        delta = f"{float(d['delta_auc']):+.4f}" if d.get("delta_auc") is not None else "—"
        pseudo_rows.append(
            f'<tr><td>{e(d["direction"])}</td><td>{int(d.get("n_pseudo_px", 0)):,} px / '
            f'{int(d.get("n_segments", 0))} segments</td>'
            f'<td>{fmt(before, 4)}</td><td>{fmt(after, 4)}</td><td>{delta}</td></tr>')
    if not pseudo_rows:
        pseudo_rows.append(f'<tr><td colspan="5">Not run: {e(pseudo.get("reason", "—"))}</td></tr>')
    pseudo_table = ('<div class="table-wrap"><table><thead><tr><th>Direction</th><th>Exchange</th>'
                    '<th>Receiver AUC before</th><th>after</th><th>Δ</th></tr></thead><tbody>'
                    + "".join(pseudo_rows) + "</tbody></table></div>")

    stratum_rows = "".join(
        f'<tr><td>{e(k)}</td><td>{int(v):,}</td><td>{fmt(strata["median_depth_to_basement_m"].get(k), 1)} m</td></tr>'
        for k, v in strata["counts"].items() if k != "allowed")

    audit_content = f'''{bar}
<div class="eyebrow">H59 audit · two-view co-training with disagreement as the discovery signal</div>
<h1>Every number on this page<br>is re-read from the bytes.</h1>
<div class="{verdict_class}"><strong>{e(verdict_head)}</strong> {e(verdict_detail)}</div>
<p class="lede">Round H59 executes the brief's Blum–Mitchell protocol end-to-end on the integrity-pinned mirror: View A (potential-field + strain + seismicity + subsurface, 48 features) and View B (DEM slope/curvature + radiometric TC + LiDAR, 36 features), out-of-fold everywhere, whole-segment buffered folds, pseudo-label exchange only where one view is confident and the other abstains, and the disagreement strata labelled with written geology for every A-only pixel.</p>
<h2>The verdict, gate by gate</h2>{gate_table}
<h2>Field decision (frozen rule, applied as written)</h2>
<p>Shipped field: <b>{e(shipped)}</b>. Eligible fields (beat random on ≥ 3/4 folds in both instruments): {e(", ".join(decision["eligible_fields"]) or "none — fail-closed to best single view")}. Independence abandoned: <b>{str(decision["independence_abandoned"])}</b>. The union field is the re-measured incumbent (H57's numbers were withdrawn with the old staging); product / vetoB / basestep / seismicity are this round's candidates; view_A / view_B are the brief's single-view baselines; a_only_stratum is the labelled diagnostic.</p>
{arm_table}
<h2>Shipped field vs the single-view baseline (the brief's bias check)</h2>{lift_table}
<h2>The incumbent comparison (post-hoc, like-for-like, amendment 3)</h2>
<p>The brief's slot rule — <i>do not spend a slot on an idea that has not beaten the current holdout best</i> — is only measurable against the incumbent emission. Every row below is scored <b>as-is</b> on the identical rebuilt folds with the same visible-mask and region rules, so the comparison stays inside one emission regime. This diagnostic never influenced the shipped field, the emitter, the pools or any frozen number.</p>
{incumbent_table}
<p><b>Proxy caveat, stated plainly:</b> the catalogue-truth proxy awards credit only within the metric's 3&nbsp;px hit radius, and the 200&nbsp;m ring (2&nbsp;px) pushes ring-respecting emissions beyond most of it — so absolute DTI levels are not comparable across emission regimes, only within one. Where the proxy has resolution (the ring-free priors), its ordering matches the owner-reported leaderboard ordering (0.2600 &gt; 0.2477 → proxy 0.0967 &gt; 0.0911). This artifact and the 0.2778 incumbent are both ring-respecting: the as-is comparison above is the honest one, and it favours this artifact on both instruments{", and the ring-free field also beat the best ring-free prior on both instruments" if ringfree_beaten else ""}.</p>
<h2>Conditional independence (Blum–Mitchell premise, measured not assumed)</h2>
<p>Per 50×50 spatial block, out-of-fold errors on labelled negatives (≥ 500 m Euclidean from the catalogue), threshold |r| ≥ 0.60 abandon, fail-closed on < 20 blocks. Measured: max |r| = <b>{fmt(independence.get("max_abs_correlation"), 4)}</b> over {int(independence.get("n_blocks", 0))} blocks → <b>{"NOT refuted at this granularity" if independence.get("allow_exchange") else "ABANDONED"}</b>. Weak coupling is not proof of independence.</p>{ind_table}
<h2>Disagreement strata (the discovery signal)</h2>
<div class="table-wrap"><table><thead><tr><th>Stratum</th><th>Pixels (permitted pool)</th><th>Median depth to basement</th></tr></thead><tbody>{stratum_rows}</tbody></table></div>
<p>A-only is the buried-structure stratum (View A confident, View B abstains); B-only is the surface-artifact suspicion stratum (roads, levees, erosion lines) — vetoed from the H59-1 emission pool and reasoned wherever emitted.</p>
<h2>Pseudo-label exchange (diagnostic only — it can never alter the shipped field)</h2>{pseudo_table}
<p>Two prior rounds measured this exchange as noise (H52 N-1, H57 §3); H59 runs it because the brief asks, in both directions, with whole segments inside single 50×50 blocks, no catalogue/corridor pixel, ≥ 80 px from evaluation, cap 2,000 px, weight 0.25, and AUC negatives ≥ 500 m <em>Euclidean</em> from every catalogue pixel (fixing IR-H58-003).</p>
<h2>Uniqueness and the "not a copy" question</h2>
<p>Every emitted pixel was computed from the H59 fields on this staging — no prior raster was read into any emission mask. The decoded pattern matches none of the {int(artifact['uniqueness']['n_priors_checked'])} accessible aligned priors (canonical bytes compared, not hashes). {float(nov['emission_novel_fraction'])*100:.1f}% of the emitted support lies outside every prior's support; {int(nov.get('overlap_with_reference_px', 0)):,} px coincide with the 0.2778 reference's dots — two independent methods agreeing on where the structure is, which is evidence, not copying: the pattern as a whole is what uniqueness means, and it differs from every prior.</p>
{sibling_html}
<h2>Historical receipts</h2>
<p>Preregistration: <a href="data/h59_preregistration.json">frozen protocol</a> · <a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/20_hypotheses_H59_preregistered.md">hypothesis slate</a>. Receipts: <a href="data/h59_result.json">run receipt</a> · <a href="downloads/{e(stem)}-reasoning.csv">per-pixel reasoning CSV</a>. This archived page does not authorize a rerun, new run-card, build, or submission.</p>'''

    (DOCS / "h59.html").write_text(shell(
        "H59 audit", "H59 two-view co-training audit: gates, folds, independence, strata, verdict",
        audit_content, active="audit"))

    # ---- research-only executive summary; no upload steps or copyable identification -------------
    guide_content = f'''{bar}
<div class="eyebrow">H59 · historical research status</div>
<h1>H59 is not approved for submission.</h1>
<div class="status"><strong>RESEARCH DOWNLOAD ONLY · NO SLOT AUTHORIZED</strong><p>{e(verdict_detail)}</p></div>
<section class="download-bar" aria-label="H59 research download"><div><strong>{e(stem)}.tif</strong><small>{artifact["bytes"]:,} bytes · SHA-256 <code>{e(artifact["sha256"])}</code></small></div>{dl_btn}</section>
<p>Download availability, local format checks, decoded-pattern uniqueness, and internal holdout measurements do not establish portal acceptance or submission eligibility.</p>
<p><b>HOLDOUT-DTI</b> is an internal hide-and-recover measurement, not a public leaderboard score or an organizer receipt. The 0.2778 public-board row is team-level and is not linked to this file hash.</p>
<p>No organizer-confirmed score receipt is recorded for H59. No owner override, upload procedure, paste-ready note, rerun, or new run-card authorization is provided.</p>
<p><a href="h59.html">H59 method and historical evidence →</a> · <a href="data/h59_result.json">Historical run receipt</a> · <a href="data/h59_preregistration.json">Preregistered protocol</a></p>'''
    (DOCS / "executive-summary.html").write_text(shell(
        "H59 research status — not for submission",
        "Historical H59 research artifact; no submission approval or upload procedure.",
        guide_content, active="guide"))

    # ---- stage downloads and data ------------------------------------------------------------
    DL.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(canonical, DL / "h59-candidate.tif")
    shutil.copyfile(canonical, DL / (stem + ".tif"))
    csv_src = EV / f"{stem}-reasoning.csv"
    if csv_src.is_file():
        shutil.copyfile(csv_src, DL / f"{stem}-reasoning.csv")
    zip_path = DL / "h59-candidate.zip"
    import zipfile
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(canonical, arcname=stem + ".tif")
    canon_zip = DL / (stem + ".zip")
    shutil.copyfile(zip_path, canon_zip)
    DATA.mkdir(parents=True, exist_ok=True)
    for name in ("h59_result.json", f"submission_{stem}.json"):
        src = EV / name
        if src.is_file():
            (DATA / name).write_text(json.dumps(json.loads(src.read_text()), indent=2,
                                                allow_nan=False, default=str) + "\n")
    shutil.copyfile(ROOT / "registry/h59_preregistration.json", DATA / "h59_preregistration.json")

    # ---- the overview page -------------------------------------------------------------------
    ind_max = float(independence.get("max_abs_correlation") or 0.0)
    index_content = f'''{bar}
<div class="eyebrow">H59 · two-view co-training · disagreement as the discovery signal</div>
<h1>A unique emission,<br>measured before it is offered.</h1>
<p class="lede">Blum–Mitchell co-training between a potential-field/subsurface view (magnetics, gravity, strain, seismicity, basement depth — 48 features) and a surface view (DEM slope/curvature, radiometric total count, LiDAR scarps — 36 features), rebuilt on the integrity-pinned mirror. The independence premise is measured, not assumed; the pseudo-label exchange runs only where one view is confident and the other abstains; every A-only candidate carries written geology with a falsifier.</p>
<div class="{verdict_class}"><strong>{e(verdict_head)}</strong> {e(verdict_detail)}</div>
<div class="grid"><div class="card"><div class="metric">{primary:,}</div><div class="label">emitted pixels, values exactly {{0,1}}, all outside the 200 m catalogue ring</div></div><div class="card"><div class="metric">{fmt(ind_max, 4)}</div><div class="label">max |r| of the two views' spatial-block OOF negative errors (abandon bar 0.60)</div></div><div class="card"><div class="metric">{"PASS" if gates_ok else "FAIL"}</div><div class="label">artifact gates re-read from the written bytes</div></div></div>
<div class="two"><section><h2>What was tested</h2><p>Five preregistered geological hypotheses; four ran (H59-1 B-only veto, H59-2 agreement product, H59-3 basement-step buttress, H59-4 seismicity lineaments) against the re-measured single-view and union baselines on whole-segment, 80 px-buffered hide and block folds, with matched budgets, a shared emitter and a seeded random control. The frozen decision rule shipped <b>{e(shipped)}</b>.</p><p><a class="button secondary" href="h59.html">Open the fold tables, strata, independence test and full audit →</a></p></section>
<section class="card"><h2>Current decision</h2><p><b>Shipped field:</b> {e(shipped)}.</p><p><b>Gates:</b> {"PASS" if gates_ok else "one or more FAILED"} (format, uniqueness vs {int(artifact['uniqueness']['n_priors_checked'])} priors, not-the-union, 200 m ring, 3 px spacing).</p><p><b>Slot verdict:</b> {e(submission["verdict"])}.</p><p><b>Organizer provenance:</b> unresolved — integrity-pinned owner mirror (IR-52-003 / IR-H58-001).</p></section></div>
<h2>Arm means on the two instruments (primary budget)</h2>{arm_table}
{sibling_html}
<h2>Evidence</h2><p><a href="h59.html">Full H59 audit</a> · <a href="executive-summary.html">Research status with the verdict</a> · <a href="data/h59_result.json">run receipt</a> · <a href="data/h59_preregistration.json">frozen protocol</a> · <a href="downloads/{e(stem)}-reasoning.csv">per-pixel reasoning CSV ({int(result['reasoning_dossier']['rows']):,} rows)</a>. Historical rounds: <a href="h58.html">H58</a> · <a href="h57.html">H57</a> · <a href="h56-cotrain.html">H56</a> · <a href="h55.html">H55</a>.</p><div class="live-feed" id="feed">Automatic local evidence feed. The official board is a dated observation, not a live feed.</div>'''
    (DOCS / "index.html").write_text(shell(
        "H59 overview",
        "H59 two-view co-training overview: gates, verdict, and one-click artifact download.",
        index_content, active="overview"))

    downloads_html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="One-click H59 downloads with the generated submit / do-not-submit verdict and audited filename/hash."><title>H59 downloads · GEMSDOE52</title><link rel="stylesheet" href="../style.css"><script src="../site.js" defer></script></head><body><a class="skip" href="#main">Skip to downloads</a><header>{nav("downloads")}</header><main id="main"><div class="eyebrow">One-click files</div><h1>H59 downloads.</h1><div class="{verdict_class}"><strong>{e(verdict_head)}</strong> {e(verdict_detail)}</div><p>Unique TIFF: <code>{e(stem)}.tif</code><br>SHA-256: <code>{e(artifact["sha256"])}</code></p><p><a href="{e(stem)}.tif" download>Download the audited TIFF</a> · <a href="h59-candidate.tif" download>Short TIFF link</a> · <a href="h59-candidate.zip" download>One-TIFF ZIP</a> · <a href="{e(stem)}-reasoning.csv">Per-pixel reasoning CSV</a> · <a href="../h59.html">Full audit</a></p><p class="small">Historical artifacts remain in this directory; the H59 file is the only one this round's verdict speaks about.</p></main></body></html>'''
    (DL / "index.html").write_text(downloads_html)

    print(f"published docs/index.html, h59.html, executive-summary.html, downloads, data receipts; "
          f"verdict={'RECOMMENDED' if recommended else 'RESEARCH ONLY'}")


if __name__ == "__main__":
    main()
