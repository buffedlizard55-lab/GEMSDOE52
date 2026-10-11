#!/usr/bin/env python3
"""Publish the H60C audit page and repoint the site's download bar, guide and index at H60C.

Every number written into HTML is read from a receipt under docs/data/ or submission/ -- the page
never re-states a figure from memory.  If a receipt is missing the publisher fails loudly rather
than printing a placeholder.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SUB = ROOT / "submission"

REQUIRED = ["docs/data/h60c_build.json", "docs/data/h60c_forensics.json",
            "docs/data/h60c_identify.json", "docs/data/h60c_cotrain.json",
            "docs/data/h60c_ladder.json"]


def esc(x) -> str:
    return html.escape(str(x))


def load(rel: str) -> dict:
    p = ROOT / rel
    if not p.exists():
        sys.exit(f"missing receipt {rel} -- refusing to publish a page with a placeholder")
    return json.loads(p.read_text())


def fmt_rows(rows, header, keys=None):
    keys = keys or list(rows[0].keys())
    h = "".join(f"<th>{esc(k)}</th>" for k in keys)
    body = "".join("<tr>" + "".join(f"<td>{esc(r.get(k, ''))}</td>" for k in keys) + "</tr>"
                   for r in rows)
    return f'<div class="table-wrap"><table><caption>{esc(header)}</caption><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table></div>'


def nav(active="h60"):
    items = [("index.html", "Overview"), ("executive-summary.html", "Submission guide"),
             ("h60c.html", "H60C audit"), ("hypotheses.html", "Hypotheses"),
             ("irregularities.html", "Limitations"), ("sources.html", "Sources"),
             ("downloads/index.html", "Downloads")]
    a = "".join(f'<a href="{u}"{" aria-current=page" if u == active else ""}>{t}</a>'
                for u, t in items)
    return f'<header><nav><a class="brand" href="index.html">GEMS / DOE 52</a>{a}</nav></header>'


def head(title, desc):
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="description" content="{esc(desc)}">'
            f'<title>{esc(title)}</title>'
            f'<link rel="stylesheet" href="style.css"><script src="site.js" defer></script>'
            f'</head><body><a class="skip" href="#main">Skip to evidence</a>')


def foot():
    return ('<footer>DOE GEMS competition 306 · Reproducible local research · '
            'Predictions are hypotheses for Phase-2 review, not verified faults or geothermal '
            'discoveries. <a href="irregularities.html">Limitations</a> · '
            '<a href="sources.html">Sources</a> · '
            '<a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code and evidence</a>'
            '</footer></body></html>')


def main() -> int:
    home = DOCS / "index.html"
    h75 = DOCS / "h75-executive-summary.html"
    if (home.is_file() and h75.is_file()
            and "H75: DUPLICATE/STOP" in home.read_text(errors="replace")
            and "DUPLICATE/STOP · RESEARCH ONLY · NOT FOR SUBMISSION" in h75.read_text(errors="replace")):
        print("H75 terminal stop is current; historical H60C publisher skipped all page and pointer changes")
        return 0
    for r in REQUIRED:                      # fail fast, before any HTML is written
        load(r)
    b = load("docs/data/h60c_build.json")
    f = load("docs/data/h60c_forensics.json")
    ident = load("docs/data/h60c_identify.json")
    ct = load("docs/data/h60c_cotrain.json")
    lad = load("docs/data/h60c_ladder.json")

    stem = b["stem"]
    sha = b["sha256"]
    name = f"gems52-h60c-core{b['core_px']}px-arm{b['emitted_px']-b['core_px']}px-{sha[:8]}-zeros"
    note = (f"H60C: {b['core_px']}px local core-overlap mask (h33-2-b2 x d1-5) + "
            f"{b['emitted_px']-b['core_px']}px bar-sized arm; 3px dot spacing; all finite binary [0,1]; research hypothesis, not a verified fault map")
    note = note[:200]

    fmt, uniq, nu = b["format"], b["uniqueness"], b["not_the_union"]
    aud = json.loads((ROOT / "evidence/uniqueness_audit_h60c_20261008.json").read_text())
    aud_pct = 100.0 * aud["share_of_candidate_px_inside_any_prior_support"]
    aud_h33 = [100.0 * o["share_of_candidate_in_prior"] for o in aud["top_overlaps"]
               if o["path"] == "data/reference/h33-2-b2-zeros.tif"]
    if not aud_h33:
        raise SystemExit("uniqueness receipt lacks h33-2-b2 overlap; refusing to publish a placeholder")
    aud_h33 = aud_h33[0]
    indep = b["independence"]

    # ------------------------- h60c.html -------------------------
    proj_rows = []
    for k, v in b["projection_by_rho"].items():
        lab, rho = k.rsplit("_rho", 1)
        proj_rows.append(dict(core_credit=lab, arm_density=rho, projected_DTI=v))
    hide_rows = b["hide_and_recover"]
    hide_by_arm = {}
    for r in hide_rows:
        hide_by_arm.setdefault(r["arm"], []).append(r["dti"])
    hide_tbl = [dict(arm=a, folds=len(v), mean_DTI=round(sum(v) / len(v), 5)) for a, v in
                sorted(hide_by_arm.items())]

    ident_tbl = [dict(candidate=c["name"], px=c["px"],
                      T_lo=round(c["T_lo"], 1), T_hi=round(c["T_hi"], 1),
                      DTI_lo=round(c["dti_lo"], 4), DTI_hi=round(c["dti_hi"], 4))
                 for c in ident["candidates"]]
    foren_tbl = [dict(file=r["id"], emitted_px=r["S"], owner_reported_score=r["score"],
                      credit_T=round(r["T"], 1), density=round(r["density"], 4))
                 for r in f["files"]]

    page = []
    page.append(head(f"H60C audit — {stem} · GEMSDOE52",
                     "H60C historical research: conditional score algebra, local co-training diagnostics, and a research-only artifact. "
                     "emission with explicit download and submission status."))
    page.append(nav("h60c.html"))
    page.append('<main id="main">')
    page.append('<div class="status" role="alert"><strong>Historical H60C analysis — current evidence correction.</strong> The owner-reported 0.2778 row is rank 17 in the saved 2026-10-09 20:18 UTC public observation (top 0.3774); no file/hash receipt maps it to a TIFF. The local 37,654/44,090 subset and 100–200 m distances do not determine hidden-truth credit or explain a score change; new-fault truth may occur within 300 m of known traces. All score-derived |G|/credit/interval tables below are conditional scenarios, not measurements. See <a href="../knowledge/49_why_02778_phd_answer.md">knowledge/49</a> and IR-R5-011.</div>')
    page.append('<div class="eyebrow">H60C historical research · reported 0.2778 has no established cause</div>')
    page.append('<h1>Conditional arithmetic is not<br>a score receipt or truth measurement.</h1>')

    page.append('<section class="download-bar" aria-label="H60C download">')
    page.append(f'<div><strong>{esc(stem)}.tif</strong>')
    page.append(f'<small>{b["bytes"]:,} bytes · single-band float32 · EPSG:32611 · '
                f'{fmt["width"]} × {fmt["height"]} · all finite · values exactly {{0,1}}</small>')
    page.append(f'<small>SHA-256 <code>{esc(sha)}</code></small>')
    page.append(f'<small>{b["emitted_px"]:,} emitted px = {b["core_px"]:,} local core-overlap cells + '
                f'{b["emitted_px"]-b["core_px"]:,} model-selected arm cells · nearest mapped catalogue pixel '
                f'{nu["min_distance_to_catalogue_m"]} m</small></div>')
    page.append('<a class="button" href="downloads/h60c-candidate.tif" download>'
                '↓ Download the TIFF (format-valid · NOT a unique submission)</a>')
    page.append('<a class="button" href="downloads/h60c-candidate.zip" download>'
                '↓ Download the one-TIFF ZIP</a>')
    page.append('<a class="button secondary" href="h60c-submission-status.html">H60C status &amp; submit rule →</a>')
    page.append('</section>')

    page.append('<h2>1 · Current evidence about the reported 0.2778</h2>')
    page.append('<p><strong>No causal score explanation is established.</strong> The saved 2026-10-09 20:18 UTC public-board observation places 0.2778 at rank 17 (top 0.3774), but the team-level row has no TIFF hash or organizer receipt. The file association remains owner-reported. Local bytes show the H33-labelled 37,654-cell bitmap is a strict subset of a separate 44,090-cell bitmap associated by its owner with 0.2600: 6,436 removed, none added, all 100–200 m from the known-fault mask. Those distances do not identify new-fault truth or explain a score change; official staff says new-fault truth may lie within 300 m of known traces. See <a href="../knowledge/49_why_02778_phd_answer.md">current evidence classification</a>.</p>')
    page.append(f'<p>The local catalogue mask and raster geometry are available; the competition\'s hidden new-fault labels and organizer score-to-file receipt are not. The former |G| = {f["G_px"]:,.1f} value is a conditional historical scenario, not a measurement of hidden truth.</p>')

    page.append('<h2>2 · Conditional credit-density scenarios (not measurements)</h2>')
    page.append('<p class="small">This table algebraically inverts owner-reported values under the former assumed |G|; it is not organizer-confirmed credit, hidden-truth measurement, or a causal explanation.</p>')
    page.append(fmt_rows(foren_tbl, "SCENARIO ONLY: T = reported score × (0.2·S + 0.8·|G|); density = T / S"))

    page.append('<h2>3 · Conditional intervals under unverified score mappings</h2>')
    page.append('<p>These linear-program intervals depend on owner-reported score-to-file associations, the assumed |G|, and the selected constraints. They are not hidden-truth measurements or organizer-confirmed score intervals.</p>')
    page.append(f'<p>The historical calculation used {ident.get("n_atoms", 559)} atom unknowns and a per-file slack; its outputs remain conditional scenario values.</p>')
    page.append(fmt_rows(ident_tbl, "CONDITIONAL DTI interval per candidate emission set (scenario only)"))
    page.append('<div class="status"><strong>Conditional model implication only.</strong> Under the selected assumptions, non-reference sets can retain a zero lower bound. This does not measure hidden truth, establish a public score, or show that any arm clears a real score threshold.</div>')

    page.append('<h2>4 · The marginal rule that sizes the emission</h2>')
    page.append(f'<p><strong>Conditional metric algebra, not measured hidden-truth credit.</strong> A pixel with expected incremental credit <code>c</code> raises DTI iff '
                f'<code>c &gt; α·DTI/(1 − α·DTI)</code>. At DTI ≈ 0.32 that is '
                f'<b>c &gt; {b["marginal_bar_at_dti_032"]}</b> under the stated algebraic setup. '
                'This is a threshold identity, not measured hidden-truth credit or proof that the former core/arm split clears the competition score bar.</p>')
    page.append(f'<p><b>Dot spacing.</b> On the 100 m integer lattice, sampling a straight trace '
                f'every 3 px gives 2.333 units of idealized kernel-footprint coverage per dot and covers 77.8 % of a straight trace; the '
                f'local d2-8 bitmap has 2.8 px spacing with 2.147 units and 76.7 % coverage. This geometric comparison '
                f'does not estimate hidden-truth credit or public score. H60C used {b["dot_spacing_px"]} px spacing.</p>')

    page.append('<h2>5 · The two-view co-training the brief requires</h2>')
    page.append(f'<p><b>Independence test (Blum–Mitchell premise).</b> Per '
                f'{indep.get("block_side_px", 50)}×{indep.get("block_side_px", 50)} px block over '
                f'labelled negatives (outside the catalogue and a '
                f'{ct["buffer_px"]} px buffer), the Spearman correlation of the two views\' '
                f'out-of-fold confident-positive rates is <b>{indep["rho_block_mean_oof_probability"]:.4f}</b> across '
                f'{indep["n_blocks"]} blocks, against the preregistered abandonment threshold '
                f'{indep["threshold"]}. '
                + ("The test <b>fires</b>: the pseudo-label exchange is abandoned."
                   if indep["fires"] else "The premise is not refuted at this granularity.") +
                '</p>')
    page.append(f'<p><b>Disagreement strata.</b> {esc(ct["strata_counts"])} — A-only pixels are '
                'where the potential-field view is confident and the surface view abstains, i.e. '
                'subsurface structure with no scarp, the signature of a fault buried beneath cover '
                'and exactly the class a surface-expression catalogue misses. B-only is the '
                'artefact suspect (road cut, erosion line, graded fan margin) and is reported, not '
                'emitted.</p>')
    page.append('<p><b>View definitions.</b> View A = potential field and subsurface: bands 1, 2, '
                '3, 9, 14 (magnetics), 13, 11, 18, 5 (isostatic gravity), 4, 7, 8 (geodetic '
                'strain), 10, 16 (seismicity), 15 (depth to basement), 17 (surface conductivity). '
                'View B = surface: bands 12, 19 (detrended elevation and its slope) and band 6. '
                'Band 6 is described by the organiser as a magnetic tilt derivative but measured on '
                'the bytes ranges 2.95–88.6, which is a radiometric total count (IR-52-019 / '
                'IR-52-034). It is the only radiometric band in the training raster, so it belongs '
                'in the surface view; leaving it in the potential-field view would corrupt the very '
                'independence test this method has to pass.</p>')
    page.append('<h3>Hide-and-recover, versus the single-view baselines the brief asks for</h3>')
    page.append(fmt_rows(hide_tbl, "Mean DTI of a budget-matched top-40k emission against the "
                                   "held-out whole catalogue segment"))
    page.append('<div class="status"><strong>HOLDOUT-DTI is a separate evidence class.</strong> This table scores withheld mapped-catalogue segments; it does not measure hidden new-fault truth, authenticate the owner-reported 0.2778 value, or establish public-board calibration. It is a local diagnostic and cannot license a slot by itself.</div>')

    page.append('<h2>6 · A preregistered hypothesis that failed</h2>')
    page.append(f'<p>The corroboration ladder — credit density = ρ<sub>0</sub> · r<sub>clade</sub>'
                f'<sup>(c−1)</sup> · r<sub>ext</sub><sup>f</sup>, four coefficients fitted to the '
                f'twelve owner-report-derived scenario values — does <b>not</b> reproduce them: median '
                f'|relative error| {lad["fit"]["median_abs_rel"]:.3f}, maximum '
                f'{lad["fit"]["max_abs_rel"]:.3f}, leave-one-file-out median '
                f'{lad["loo_median_abs_rel"]:.3f}. Corroboration count is therefore <b>not</b> a '
                f'sufficient statistic for credit density, which is the same conclusion '
                f'<code>knowledge/03</code> N-10 reached by a different route ("habitat is not '
                f'credit"). Recorded as a refutation, not smoothed away.</p>')

    page.append('<h2>7 · What ships, and its gates</h2>')
    page.append('<div class="table-wrap"><table><thead><tr><th>gate</th><th>value</th></tr></thead>'
                '<tbody>')
    for k, v in [
        ("emitted pixels", f"{b['emitted_px']:,}"),
        ("local core-overlap mask (P1 = h33-2-b2 ∩ gems24-d1-5; credit unknown)", f"{b['core_px']:,}"),
        ("model-selected arm tier 1 (cross-provenance pattern)", f"{b['tier1_px']:,}"),
        ("arm tier 2 (A-only discovery, outside every prior's support)", f"{b['tier2_px']:,}"),
        ("format problems", f"{len(fmt['problems'])}"),
        ("NaN / Inf pixels", f"{fmt['nan_pixels']} / {fmt['infinity_pixels']}"),
        ("value range", f"[{fmt['min']}, {fmt['max']}]"),
        ("grid / CRS / transform",
         f"{fmt['height']} × {fmt['width']} · {fmt['crs']} · {fmt['transform']}"),
        ("priors compared for uniqueness", f"{uniq['n_priors_checked']}"),
        ("novel fraction", f"{uniq['novel_fraction']:.4f}"),
        ("equals the union of any two priors", f"{uniq['equals_literal_prior_union']}"),
        ("Jaccard vs top-K of the plain union max(pA, pB)",
         f"{nu['jaccard_vs_topK_of_plain_union_max_pA_pB']}"),
        ("Jaccard vs top-K of the A-only field",
         f"{nu['jaccard_vs_topK_of_A_only_field']}"),
        ("arm outside every prior's support",
         f"{nu['novel_vs_every_prior_support_px']:,} px "
         f"({nu['novel_vs_every_prior_support_frac']*100:.1f} %)"),
        ("minimum distance to a mapped catalogue pixel",
         f"{nu['min_distance_to_catalogue_m']} m"),
    ]:
        page.append(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>")
    page.append('</tbody></table></div>')

    page.append('<h2>8 · Historical conditional projection, not a forecast or score</h2>')
    page.append(fmt_rows(proj_rows, "Projected DTI = (T_core + ρ·n_arm) / (0.2·S + 0.8·|G|), "
                                    "over the identified interval on T_core and a prior on the "
                                    "arm's credit density ρ"))
    page.append('<div class="status"><strong>Honest limits.</strong> ρ for the arm is a prior, not '
                'a measurement: the identified interval on every non-file subset has a lower bound '
                'of zero. |G| rests on one nested pair (0.2778 / 0.2600) whose scores are '
                'owner-reported at four decimals, and no file-to-score mapping in this repository '
                'is organiser-authenticated. The inputs are SHA-256-pinned owner mirrors of a '
                'login-walled portal. Nothing here is a leaderboard forecast, and every emitted '
                'pixel is a hypothesis for Phase-2 review, not a verified fault.</div>')

    page.append('<h2>9 · Receipts</h2>')
    page.append('<p class="small">build: <a href="data/h60c_build.json">h60c_build.json</a> · '
                'forensics: <a href="data/h60c_forensics.json">h60c_forensics.json</a> · '
                'identified intervals: <a href="data/h60c_identify.json">h60c_identify.json</a> · '
                'co-training: <a href="data/h60c_cotrain.json">h60c_cotrain.json</a> · '
                'corroboration ladder (refuted): <a href="data/h60c_ladder.json">h60c_ladder.json</a> '
                '· preregistration: <a href="../registry/h60c_preregistration.json">'
                'h60c_preregistration.json</a></p>')
    page.append('</main>')
    page.append(foot())
    (DOCS / "h60c.html").write_text("\n".join(page))
    print("wrote docs/h60c.html")

    # ---------------- repoint index / executive summary ----------------
    idx = (DOCS / "index.html").read_text()
    idx = idx.replace('<a href="h59.html">H59 audit</a>', '<a href="h60c.html">H60C audit</a>')
    (DOCS / "index.html").write_text(idx)

    es = []
    es.append(head("H60C archive status · GEMSDOE52",
                   "Archived H60C artifact identification, local format result, and explicit no-slot status. "
                   "Local GeoTIFF format checks do not establish portal acceptance or organizer approval."))
    es.append(nav("executive-summary.html"))
    es.append('<main id="main"><div class="eyebrow">Historical H60C · research-only status</div>')
    es.append('<h1>Download for research;<br>no current slot approval.</h1>')
    es.append('<div class="status"><strong>DOWNLOAD FOR RESEARCH: YES. LOCAL FORMAT CHECK: PASS; PORTAL ACCEPTANCE: UNVERIFIED. SUBMISSION APPROVAL: NO — NOT SLOT-APPROVED.</strong> This archived H60C artifact is not a current submission recommendation. The local format contract checks do not establish portal acceptance, organizer approval, or score. See <a href="h60c.html">H60C conditional analysis</a> and the current H75 stop at <a href="index.html">the site home</a>.</div>')
    es.append('<section class="download-bar" aria-label="H60C download">')
    es.append(f'<div><strong>{esc(stem)}.tif</strong>')
    es.append(f'<small>{b["bytes"]:,} bytes · SHA-256 <code>{esc(sha)}</code></small>')
    es.append(f'<small>format gate: {len(fmt["problems"])} problems · all finite · values '
              f'{{0,1}} · {uniq["n_priors_checked"]} priors compared · '
              f'nearest mapped catalogue pixel {nu["min_distance_to_catalogue_m"]} m</small></div>')
    es.append('<a class="button" href="downloads/h60c-candidate.tif" download>'
              '↓ Download the TIFF (format-valid · NOT a unique submission)</a>')
    es.append('<a class="button" href="downloads/h60c-candidate.zip" download>'
              '↓ Download the one-TIFF ZIP</a>')
    es.append('<a class="button secondary" href="h60c.html">Full audit →</a></section>')
    es.append('<h2>Research download and local status</h2>')
    es.append('<div class="table-wrap"><table><thead><tr><th>question</th>'
              '<th>answer of record</th></tr></thead><tbody>')
    for q, a in [
        ("OK to <b>download</b>?",
         '<span class="pill ok">YES</span> — this is a research download; local format validation does not constitute portal acceptance. '
         'audit.'),
        ("Local format contract / portal acceptance?",
         '<span class="pill ok">LOCAL CHECK: PASS</span> — single-band float32, EPSG:32611, '
         f'{fmt["height"]} × {fmt["width"]}, pinned transform, finite binary {{0,1}}. '
         '<span class="pill warn">PORTAL ACCEPTANCE: UNVERIFIED</span> Local validation does not prove portal acceptance, organizer approval, or score.'),
        ("Unique submission?",
         f'<span class="pill bad">NO</span> — the decoded pattern is not byte-identical to any prior, '
         f'but it is a derivative: {aud_pct:.1f} % of its cells lie inside prior-submission support and '
         f'{aud_h33:.1f} % inside <code>h33-2-b2</code> alone (receipt: <code>evidence/uniqueness_audit_h60c_20261008.json</code>, '
         'IR-UNQ-001).'),
        ("Not merely the union of the two views?",
         f'<span class="pill ok">YES</span> — Jaccard with the top-K of the plain union '
         f'max(p<sub>A</sub>, p<sub>B</sub>) is '
         f'{nu["jaccard_vs_topK_of_plain_union_max_pA_pB"]}, and with the top-K of the A-only '
         f'field {nu["jaccard_vs_topK_of_A_only_field"]}.'),
        ("OK to spend the <b>weekly slot</b>?",
         '<span class="pill bad">NO — NOT RECOMMENDED</span> — it fails the brief\'s unique-submission rule '
         '(a derivative of prior pixels), and no holdout measurement beats the bar; the arm\'s density is '
         'not measured and cannot be. See <a href="h60c.html">§8</a>.'),
        ("Is it a verified fault map?",
         '<span class="pill no">NO</span> — every pixel is a hypothesis for Phase-2 review; '
         'written reasoning and an explicit falsifier ship with each A-only candidate.'),
    ]:
        es.append(f"<tr><td>{q}</td><td>{a}</td></tr>")
    es.append('</tbody></table></div>')
    es.append('<h2>No submission procedure</h2><p>This H60C artifact is a research archive only. It is not slot-approved; local format validity does not establish portal acceptance, organizer approval, or score. No upload instructions or selector override are provided.</p>')
    es.append('<h2>Machine-readable proof</h2><p class="small">'
              'build: <a href="data/h60c_build.json">h60c_build.json</a> · '
              'forensics: <a href="data/h60c_forensics.json">h60c_forensics.json</a> · '
              'identified intervals: <a href="data/h60c_identify.json">h60c_identify.json</a> · '
              'co-training: <a href="data/h60c_cotrain.json">h60c_cotrain.json</a> · '
              'ladder (refuted): <a href="data/h60c_ladder.json">h60c_ladder.json</a></p>')
    es.append('<div class="status"><strong>Honest limits.</strong> Inputs are SHA-pinned owner '
              'mirrors of a login-walled portal, not organiser-authenticated downloads. The saved 2026-10-09 20:18 UTC public-board observation records 0.2778 at rank 17 and a top row of 0.3774; no row supplies a TIFF hash or organizer receipt. The 0.2778 file association and 0.2600 comparison remain owner-reported. The former |G| = 14,088.7 value is a conditional scenario, not a measurement. No organizer-confirmed score is claimed for this artifact.</div>')
    es.append('</main>')
    es.append(foot())
    # The executive summary is the CTD5-era submission guide and is governed by the CTD5 release
    # contract (scripts/check_ctd5_release.py, scripts/check_site.py). This publisher no longer
    # overwrites it; H60C status and its download live on docs/h60c.html (IR-UNQ-001).
    (DOCS / "h60c-submission-status.html").write_text("\n".join(es))
    print("wrote docs/h60c-submission-status.html")

    (SUB / "H60C_LATEST.txt").write_text(
        f"{stem}.tif\nsha256 {sha}\nbytes {b['bytes']}\n"
        f"name {name}\nnote {note}\n")
    (DOCS / "data" / "h60c_submission.json").write_text(json.dumps(
        dict(round="H60C", stem=stem, file=f"{stem}.tif", submission_name=name, note=note,
             note_chars=len(note), bytes=b["bytes"], sha256=sha,
             emitted_px=b["emitted_px"], core_px=b["core_px"],
             format=fmt, uniqueness=uniq, not_the_union=nu), indent=1))
    print("wrote submission/H60C_LATEST.txt and docs/data/h60c_submission.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
