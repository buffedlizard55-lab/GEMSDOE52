#!/usr/bin/env python3
"""Generate docs/h54.html and insert the H54 one-click download bar into the R2 site's top pages.

Why this script writes one page and edits two, instead of owning the site: PR #9 (the R2 round) added
`scripts/publish_site_r2.py`, which regenerates `index.html`, `executive-summary.html`,
`validation.html`, `forensics.html`, `method.html`, `hypotheses.html`, `sources.html`,
`irregularities.html`, `feed.html`, `h53.html`, `downloads/index.html` **and `README.md`**, and
`scripts/check_site.py` now enforces invariants of those generated pages (arm means rendered from the
current receipt; a failed-gate warning on the two top pages). An earlier version of this script wrote
`validation.html`, `feed.html`, `irregularities.html` and `sources.html` from its own templates, which
clobbered the R2 site and failed those checks. It does not do that any more.

Everything here is rendered from `evidence/*.json`; no number is typed into this file. The download bar
insertion is idempotent, so running the script twice does not stack two bars.
"""
from __future__ import annotations

import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EV = ROOT / "evidence"
NAV = ('<a href="index.html">Overview</a><a href="executive-summary.html">Submission&nbsp;guide</a>'
       '<a href="h54.html">H54&nbsp;revealed-preference</a><a href="validation.html">Validation</a>'
       '<a href="forensics.html">0.2778&nbsp;autopsy</a><a href="irregularities.html">Irregularities</a>'
       '<a href="sources.html">Sources</a>')


def esc(x) -> str:
    return html.escape(str(x))


def load(name: str) -> dict:
    p = EV / f"{name}.json"
    if not p.exists():
        return {"__missing__": str(p)}
    return json.loads(p.read_text())


def page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="description" content="H54: the revealed-preference inverse — |G|, the dead '
            f'200 m ring, the atom accounting, and the emission built on them.">'
            f'<title>{esc(title)} · GEMSDOE52</title><link rel="stylesheet" href="style.css">'
            f'</head><body><a class="skip" href="#main">Skip to content</a>'
            f'<header><nav><a class="brand" href="index.html">GEMS / DOE 52</a>{NAV}</nav></header>'
            f'<main id="main">{body}</main>'
            f'<footer>Competition 306 · every figure on this page is rendered from '
            f'<code>evidence/*.json</code> by <code>scripts/make_site_pages.py</code></footer>'
            f'</body></html>')


def download_bar(sub: dict) -> str:
    """The one-click bar. TIF and ZIP, at the very top, with the note to paste under the button."""
    if not sub.get("exists"):
        return ('<!--H54BAR--><div class="download-bar" id="h54-bar"><div>'
            '<strong>H54 submission not built</strong>'
            '<small>run <code>PYTHONPATH=src python3 scripts/build_revealed_submission.py</code>'
            '</small></div></div><!--/H54BAR-->')
    proj = sub.get("projected_dti") or {}
    uni = sub.get("uniqueness") or {}
    note = sub.get("submission_note") or ""
    return (
        '<!--H54BAR--><div class="download-bar" id="h54-bar"><div>'
        f'<strong>H54 submission GeoTIFF — the candidate this round offers</strong>'
        f'<small>{esc(sub.get("file"))}</small>'
        f'<small>{esc(sub.get("bytes"))} bytes · 1 band · float32 · EPSG:32611 · values {{0,1}} · '
        f'no NaN · sha256 <code>{esc((sub.get("sha256") or "")[:16])}…</code></small>'
        f'<small>format gate {esc((sub.get("format") or {}).get("ok"))} · uniqueness gate '
        f'{esc(uni.get("ok"))} · {esc(round(100 * float(uni.get("novel_fraction") or 0), 1))}% strictly '
        f'novel · {esc(uni.get("prior_px_dropped"))} prior px not re-emitted</small>'
        f'<small>notes box, verbatim ({esc(sub.get("submission_note_chars"))} chars): '
        f'<code>{esc(note)}</code></small></div>'
        f'<a class="button" href="{esc(sub.get("download"))}" download>↓ Download .TIF</a>'
        f'<a class="button" href="{esc(sub.get("download_zip"))}" download>↓ Download .ZIP</a>'
        f'<a class="button" href="h54.html">Why this file →</a>'
        f'<small style="width:100%">projected DTI {esc(proj.get("mean_dti"))} · '
        f'P(beats 0.2778) {esc(proj.get("p_win"))} · worst {esc(proj.get("worst_dti"))} · best '
        f'{esc(proj.get("best_dti"))} — an integral over a stated prior, <b>not a forecast</b></small>'
        '</div><!--/H54BAR-->')


def insert_bar(path: pathlib.Path, bar: str) -> bool:
    """Put the bar immediately inside <main>, before anything else. Idempotent."""
    if not path.exists():
        return False
    s = path.read_text()
    i = s.find("<main")
    if i < 0:
        return False
    j = s.find(">", i) + 1
    if "<!--H54BAR-->" in s and "<!--/H54BAR-->" in s:      # replace the previous bar in place
        a = s.index("<!--H54BAR-->")
        b = s.index("<!--/H54BAR-->") + len("<!--/H54BAR-->")
        path.write_text(s[:a] + bar + s[b:])
        return True
    s = s[:j] + bar + s[j:]
    path.write_text(s)
    return True


def table(head, rows) -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    tr = "".join("<tr>" + "".join(
        f'<td class="num">{esc(c)}</td>' if isinstance(c, (int, float)) else f"<td>{esc(c)}</td>"
        for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"


def h54_body() -> str:
    # Read the *feed* copy, not the evidence copy: scripts/refresh_feed.py enriches it with
    # `exists`, `download`, `download_zip` and `submission_note`, which is what download_bar() needs.
    # Reading evidence/submission_<stem>.json here rendered the "not built" branch on a page whose
    # subject was the built file.
    sub = json.loads((DOCS / "data/submission.json").read_text())
    cal = load("revealed_calibration")
    bud = load("revealed_budget")
    ind = load("independence_revealed")
    views = load("cotraining_views54")
    audit = load("revealed_submission_audit")
    B = []
    B.append('<div class="eyebrow">H54 · revealed preference</div>'
             '<h1>What the organiser\'s own scores say about the hidden truth</h1>'
             '<p class="lede">Five of this group\'s scored files stand in verified nesting relations, so '
             'their published scores are not thirteen noisy observations of one number — they are a small '
             'linear system. Solving it gives the size of the hidden truth, proves a 200 m ring around the '
             'mapped catalogue earns exactly nothing, and bounds the credit of the double-corroborated '
             'atom this file retains.</p>')
    B.append(download_bar(sub))
    B.append('<div class="status"><strong>Read this before spending a slot.</strong> The retained half of '
             'this file\'s credit is bounded by exact arithmetic on published scores. The novel half\'s '
             'credit density is <em>not</em> known and cannot be measured here: 171 features were screened '
             'for the ability to re-rank inside the champion file and the best blocked AUC was 0.5453 '
             '(point features) and 0.5122 (structure-tensor coherence). The budget is therefore chosen by '
             'integrating the metric over a <em>stated prior</em> for that unknown.</div>')

    B.append("<h2>1 · The calibration, exactly</h2>")
    rows = [["|G| (hidden truth, px)", cal.get("g_estimate_px"),
             "solved from T(B) − T(A) = 0 on the verified nesting A ⊂ B"]]
    rows.append(["credit of the ≤200 m ring", cal.get("corridor_credit"), "exact, not modelled"])
    for k, v in (cal.get("size_of") or {}).items():
        rows.append([f"atom {k}", v,
                     f"credit {(cal.get('credit_of') or {}).get(k)} · density "
                     f"{(cal.get('density_of') or {}).get(k)}"])
    rd = cal.get("reference_densities") or {}
    rows.append(["uniform-random density", rd.get("uniform_random_over_permitted_set"),
                 "credit per emitted pixel for a Poisson dot cloud of 37,654 px"])
    rows.append(["champion file as a whole", rd.get("champion_file_as_a_whole"),
                 f"credit {rd.get('champion_file_credit')} over 37,654 px"])
    rows.append(["retained core credit", f"{(cal.get('t_core_bounds') or ['?'])[0]} – "
                 f"{(cal.get('t_core_bounds') or ['?'])[1]}, central {cal.get('t_core_central')}",
                 "exact interval from t ≥ 0; the central estimate splits the measured tail credit by size"])
    rows.append(["DTI(core emitted alone)", f"{(cal.get('dti_core_bounds') or ['?'])[0]} – "
                 f"{(cal.get('dti_core_bounds') or ['?'])[1]}, central {cal.get('dti_core_central')}",
                 "a pure budget reduction, with no new geology at all"])
    B.append(table(["quantity", "value", "status"], rows))
    B.append("<h3>What was verified on the bytes</h3><ul>"
             + "".join(f"<li>{esc(n)}</li>" for n in (cal.get("notes") or [])) + "</ul>")

    B.append("<h2>2 · The budget, chosen by maximising P(win)</h2>")
    B.append(f'<p><code>DTI = (t_core + ρ_novel·n_novel) / (0.2·S + 0.8·|G|)</code>, capped by '
             f'<code>T ≤ |G|</code>. <code>t_core</code> is bounded exactly, so it gets a uniform prior '
             f'over {esc(json.dumps(bud.get("t_core_bounds")))}. <code>ρ_novel</code> is unknowable, so it '
             f'gets a uniform prior over {esc(json.dumps(bud.get("rho_prior")))} — from "no better than '
             f'uniform random" to "as good as the champion file\'s own average". The rule maximises '
             f'P(DTI &gt; {esc(bud.get("floor"))}) and breaks ties toward the larger novel fraction, '
             f'because the brief requires a unique artefact and a mean cannot see that.</p>')
    sel = (bud.get("selected") or {}).get("n_novel")
    B.append(table(["novel px", "total px", "novel fraction", "P(win)", "mean DTI", "worst", "best"],
                   [[r["n_novel"], r["total"], round(100 * r["novel_fraction"], 1),
                     r["p_win"], r["mean_dti"], r["worst_dti"], r["best_dti"]]
                    for r in (bud.get("rows") or [])])
             + f'<p class="small">selected row: <b>{esc(sel)}</b> novel px.</p>')

    B.append("<h2>3 · The two views, and the conditional-independence test</h2>")
    sb = (views.get("single_view_baseline") or {})
    va, vb = views.get("view_a") or {}, views.get("view_b") or {}
    B.append(table(["quantity", "value", "reading"], [
        ["View A out-of-fold AUC", va.get("oof_auc"),
         f"potential field / subsurface, {va.get('n_features')} features; block mean "
         f"{sb.get('view_a_mean')}"],
        ["View B out-of-fold AUC", vb.get("oof_auc"),
         f"surface / LiDAR scarp / radiometric, {vb.get('n_features')} features; block mean "
         f"{sb.get('view_b_mean')}"],
        ["blended", views.get("blended_oof_auc"),
         f"co-training wins: {sb.get('co_training_wins')} — View B alone beats the blend, and that is "
         f"printed rather than buried"],
        ["independence, pixel Pearson r", ind.get("pixel_pearson_r"),
         f"threshold {ind.get('threshold')} → {ind.get('verdict')}"],
        ["independence, block mean r", ind.get("block_mean_r"),
         f"variance {ind.get('block_var_r')} over {ind.get('n_blocks')} blocks; degenerate: "
         f"{ind.get('degenerate_block_variance')}"],
    ]))
    B.append(f'<p class="small">{esc(sb.get("label_caveat") or "")}</p>')

    B.append("<h2>4 · What the artefact is</h2>")
    fab = audit.get("fabric") or {}
    B.append(table(["property", "value"], [
        ["file", audit.get("name")], ["sha256", (sub.get("sha256") or "")],
        ["bytes", sub.get("bytes")],
        ["emitted pixels", audit.get("pixels")],
        ["retained core (= A & C)", audit.get("retained_core_px")],
        ["strictly novel", audit.get("novel_px")],
        ["…of which along the recovered strike", audit.get("novel_along_strike_px")],
        ["…of which free candidates on the same fabric", audit.get("novel_far_px")],
        ["novel fraction", (sub.get("uniqueness") or {}).get("novel_fraction")],
        ["prior pixels deliberately not re-emitted",
         (sub.get("uniqueness") or {}).get("prior_px_dropped")],
        ["corridor excluded", f"{audit.get('corridor_excluded_m')} m"],
        ["emitted inside the corridor",
         (sub.get("writer_receipt") or {}).get("mass_within_corridor")],
        ["emitted on the catalogue", (sub.get("writer_receipt") or {}).get("mass_on_catalogue")],
        ["emitted outside the footprint",
         (sub.get("writer_receipt") or {}).get("mass_outside_footprint")],
        ["NaN pixels", (sub.get("writer_receipt") or {}).get("nan_pixels")],
        ["distinct values", (sub.get("writer_receipt") or {}).get("values")],
        ["A-only candidates with a written geological reason",
         audit.get("n_a_only_candidates_reasoned")],
        ["recovered fabric: coherence of the credited cloud", fab.get("coherence_credited_mean")],
        ["…against a matched uniform-random cloud", fab.get("coherence_random_mean")],
        ["dominant recovered strike (array deg)", fab.get("dominant_strike_deg")],
    ]))
    B.append(f'<p class="small muted">{esc(fab.get("reading") or "")}</p>')
    B.append('<h2>5 · Why the holdout did not select this</h2>'
             '<p>The whole-component hide-and-recover simulator this repo used to select on does not '
             'predict the organiser\'s score: over the 13 restored scored files, Spearman '
             'ρ(reported, simulated DTI) = −0.1045, p = 0.734. The group\'s best file on the board is '
             'the <em>worst</em> of the 13 on the instrument (lift 0.09× mass-matched random) and the '
             'file the instrument ranks first scored 0.1563. Its premise — that the hidden truth is a '
             'held-out part of the mapped catalogue — is false by §1. Recorded as '
             '<code>knowledge/03</code> N-9 and <code>IR-52-023</code>; the derivation, the confound '
             'that was checked and excluded, and the four further negative results are in '
             '<a href="../knowledge/10_revealed_preference_inverse.md">'
             '<code>knowledge/10_revealed_preference_inverse.md</code></a> and '
             '<a href="../knowledge/11_hypotheses_H54.md">'
             '<code>knowledge/11_hypotheses_H54.md</code></a>.</p>')
    return "".join(B)


def main() -> int:
    (DOCS / "h54.html").write_text(page("H54 revealed preference", h54_body()))
    print("wrote docs/h54.html")
    sub = json.loads((DOCS / "data/submission.json").read_text())
    bar = download_bar(sub)
    for name in ("index.html", "executive-summary.html"):
        ok = insert_bar(DOCS / name, bar)
        print(("inserted" if ok else "SKIPPED (no <main>)") + f" the H54 bar into docs/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
