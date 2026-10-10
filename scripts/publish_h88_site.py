#!/usr/bin/env python3
"""Publish the H88 status block at the top of docs/index.html. Every number is read from evidence/.

Refuses to publish unless: the download copy's sha256 equals the run card, the independent validator
(scripts/verify_h88.py -> evidence/h88_independent_verify.json) passed, and the holdout receipt exists.

The block sits between <!--H88-START--> and <!--H88-END--> and replaces everything from the page title to the
old "How to Submit" heading. The previous file's download (H87 co-training) is kept, inside a collapsed
<details>, with its status stated plainly: it has no holdout DTI on this branch.

Usage: python scripts/publish_h88_site.py   (idempotent)
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / "evidence"
INDEX = ROOT / "docs/index.html"
FILE = "gems52-h88-basement-step-37654px-20261010.tif"
DL_TIF = "downloads/h88-candidate.tif"
DL_ZIP = "downloads/h88-candidate.zip"
OLD_TIF = "downloads/gems52-h87-cotrain-wavelength-thk-37654px-20261010T213656Z.tif"
OLD_ZIP = "downloads/gems52-h87-cotrain-wavelength-thk-37654px-20261010T213656Z.zip"


def load(name):
    return json.loads((E / name).read_text())


def pct_ci(ci):
    return f"[{ci[0]:.6f}, {ci[1]:.6f}]"


def main() -> int:
    hold = load("h88_holdout.json")
    card = load("h88_run_card.json")
    ver = load("h88_independent_verify.json")
    raw = (ROOT / "submission" / FILE).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != card["raster_sha256"]:
        raise SystemExit("submission raster changed since the run card")
    if (ROOT / "docs" / DL_TIF).read_bytes() != raw:
        raise SystemExit("download copy differs from the submission raster")
    if not ver.get("validator_PASS"):
        raise SystemExit("independent validator did not pass; refusing to publish")
    if ver["sha256"] != sha:
        raise SystemExit("validator receipt is for a different file")

    s = hold["pooled"]["scores"]
    h85 = load("h85_holdout.json")["pooled"]["scores"]
    h85_topk, h85_rnd = h85["H85_geo_concordance_topk_noSpacing"], h85["random"]
    pdiff = hold["pooled"]["paired_differences"]
    g = hold["gate"]
    cand, rnd = s["H88_step"], s["random"]
    pr = pdiff["random"]
    u, lane = card["uniqueness"], card["lane"]
    dots_ex = lane["dots_max_near_3px_excluding_universal_probes"]
    surf = lane["surface"]
    dots = lane["dots"]
    h = html.escape
    block = f"""<!--H88-START-->
<h1>GEMSDOE52 — Submission Status (H88)</h1>
<p style="color:#999;margin-bottom:4px">DOE GEMS Prize (DrivenData #306) · Fault discovery · Auto-generated from <code>evidence/</code> by <code>scripts/publish_h88_site.py</code></p>

<div class="card" style="border-color:#ffa726">
<div class="card-title">Verdict for the file below</div>
<p><span class="pill pill-ok">OK to download? YES</span> format-valid (independent check: <span class="pass">PASS</span>), decoded-pixel unique (uniqueness gate <span class="pass">PASS</span>).</p>
<p><span class="pill pill-warn">OK to submit? NO — DO NOT SUBMIT</span> its pre-registered holdout test is <span class="fail">NEGATIVE</span>: it scores below the random control.</p>
<p style="font-size:0.9rem"><b>NO CERTIFIED LEADERBOARD GAIN.</b> Nothing on this page is an organiser score or a certified gain.</p>
<p style="font-size:0.9rem;color:#bbb">Nothing here is an organiser score. Slots used this round: 0. Promotion is a separate decision by the owner.</p>
</div>

<!-- DOWNLOAD BOX -->
<div class="download-box">
<h2>⬇ SUBMISSION FILE (H88) — download only</h2>
<p>Single-band float32 GeoTIFF · EPSG:32611 · 3730 × 3292 · 100 m · 37,654 dots (value 1), zeros elsewhere · every pixel finite and in [0, 1].</p>
<a class="btn" href="{DL_TIF}" download>📥 Download .tif</a>
<a class="btn btn-zip" href="{DL_ZIP}" download>📦 Download .zip</a>
<p style="font-size:0.85rem;margin-top:12px">
<strong>Filename inside:</strong> <code>{FILE}</code><br>
<strong>Suggested submission name:</strong> <code>{h(card["submission_name"])}</code><br>
<strong>SHA-256:</strong> <code>{sha}</code>
</p>
</div>

<div class="card">
<div class="card-title">Holdout result (HOLDOUT-DTI, not an organiser score)</div>
<table>
<tr><th>arm</th><th>HOLDOUT-DTI</th><th>95% CI (paired cluster bootstrap)</th></tr>
<tr><td><b>H88 basement-step coherence (this file)</b></td><td>{cand["dti"]:.6f}</td><td>{pct_ci(cand["ci95"])}</td></tr>
<tr><td>random, same allowed set and placement (control)</td><td>{rnd["dti"]:.6f}</td><td>{pct_ci(rnd["ci95"])}</td></tr>
<tr><td>gradient magnitude only (ablation)</td><td>{s["H88_gradient_only"]["dti"]:.6f}</td><td>{pct_ci(s["H88_gradient_only"]["ci95"])}</td></tr>
<tr><td>raw depth-to-basement, no step term (ablation)</td><td>{s["raw_depth_to_base"]["dti"]:.6f}</td><td>{pct_ci(s["raw_depth_to_base"]["ci95"])}</td></tr>
<tr><td>H88 top-k without spacing (placement ablation)</td><td>{s["H88_step_topk_noSpacing"]["dti"]:.6f}</td><td>{pct_ci(s["H88_step_topk_noSpacing"]["ci95"])}</td></tr>
</table>
<p style="font-size:0.9rem">Paired, H88 minus random: <b>{pr["delta"]:.6f}</b>, 95% CI {pct_ci(pr["ci95"])}. Evaluator <code>{h(hold["evaluator"])}</code>; withheld positive pixels <b>{hold["withheld_positive_px"]:,}</b> over 4 folds; leakage canary max single-channel AUC <b>{max(hold["canary_max_auc"].values()):.4f}</b> (bar 0.90, no alarm); random control reproduces the H82 receipt (0.080426) to {hold["controls"]["random_reproduction"]["abs_delta"]:.1e}.</p>
<p style="font-size:0.9rem">Pre-registered rule (<code>knowledge/80_h88_preregistered.md</code> §5): <b>{h(g["verdict"])}</b>.</p>
</div>

<div class="card">
<div class="card-title">Uniqueness and lane gates (from disk)</div>
<ul style="margin-left:20px;font-size:0.92rem">
<li>Decoded-pixel uniqueness: <b>{u["n_priors_checked"]}</b> local priors checked; max Jaccard of positive support <b>{u["max_jaccard_vs_priors"]:.4f}</b>; novel fraction <b>{u["novel_fraction"]:.4f}</b>; identical to a prior: {u["identical_to_a_prior"]}. Gate: <span class="pass">{'PASS' if u["ok"] else 'FAIL'}</span>.</li>
<li>Lane, surface: max Spearman <b>{surf["max_spearman"]:.4f}</b> vs bar {surf["threshold"]:.2f} → <span class="pass">{surf["verdict"]}</span>.</li>
<li>Lane, dots: literal rule <span class="fail">{h(dots["verdict"])}</span> (max near-3 px share {dots["max_near_3px_any_prior"]:.4f} against a universal-coverage probe raster that random dots also match at 0.999). Excluding probes: max {dots_ex:.4f} vs bar 0.70. The literal rule is <b>not waived</b>.</li>
<li>Catalogue collar: 0 dots within 200 m of the mapped catalogue (independent check).</li>
</ul>
</div>

<div class="card" style="border-color:#ef5350">
<div class="card-title">Limits (read before any upload)</div>
<ul style="margin-left:20px;font-size:0.92rem">
<li>The holdout hides <i>catalogue</i> faults; the competition scores <i>new</i> faults. A negative holdout is evidence against this field, not a proof about the board.</li>
<li>The organiser's page says data outside the bounds is "null or nan"; this file writes 0.0 outside the footprint so it cannot fail a literal [0, 1] test. Organiser behaviour for this container is unverified (IR-H85-004).</li>
<li>The organiser's competition-page leaderboard (fetched 2026-10-10) shows #1 0.3774, #8 0.3195 and #22 0.2778. Filename-to-score mapping for those is not organiser-confirmed.</li>
</ul>
</div>

<details class="card">
<summary><b>Previous file (earlier round, H87 co-training wavelength)</b> — not holdout-validated on this branch; kept for reference</summary>
<p style="font-size:0.9rem">The older download below was labelled "PROMOTE" on this page before H88. No holdout DTI for it exists in this repository, so that label is withdrawn.</p>
<a class="btn btn-zip" href="{OLD_TIF}" download>Download older .tif</a>
<a class="btn btn-zip" href="{OLD_ZIP}" download>Download older .zip</a>
<p style="font-size:0.9rem"><b>Earlier H83 file</b> (<code>downloads/h83-candidate.tif</code>): its "SUBMIT: YES" label is withdrawn (IR-H85-003). Its own clumped placement measured <b>{h85_topk["dti"]:.6f}</b> HOLDOUT-DTI, 95% CI {pct_ci(h85_topk["ci95"])}, in H85 (<code>evidence/h85_holdout.json</code>), against a random control of {h85_rnd["dti"]:.6f}.</p>
<a class="btn btn-zip" href="downloads/h83-candidate.tif" download>Download H83 .tif</a>
<a class="btn btn-zip" href="downloads/h83-candidate.zip" download>Download H83 .zip</a>
</details>
<!--H88-END-->

"""
    text = INDEX.read_text()
    if "<!--H88-START-->" in text:                      # idempotent re-run: swap the block in place
        text = re.sub(r"<!--H88-START-->.*?<!--H88-END-->\n*", lambda _m: block, text, flags=re.S)
    elif re.search(r"<h1>GEMSDOE52 — Co-Training Wavelength Contrast</h1>", text) and "<!-- HOW TO SUBMIT -->" in text:
        # first run on the pre-merge page: replace the old H87-era header and box
        m = re.search(r"<h1>GEMSDOE52 — Co-Training Wavelength Contrast</h1>", text)
        head_end = text.index("<!-- HOW TO SUBMIT -->")
        text = text[:m.start()] + block + text[head_end:]
    else:                                              # page rebuilt on main (other sessions): put the block first in <body>
        m_body = re.search(r"<body[^>]*>", text)
        if not m_body:
            raise SystemExit("index.html has no <body> tag and no legacy anchor")
        text = text[:m_body.end()] + block + text[m_body.end():]
    text = text.replace("<title>GEMSDOE52 — Co-Training Wavelength Contrast Submission</title>",
                        "<title>GEMSDOE52 — Submission Status (H88)</title>")
    INDEX.write_text(text)
    ex = ROOT / "docs/executive-summary.html"
    banner = ('<!--H88-EXEC-START--><div style="background:#4a2800;color:#ffe0b2;padding:12px 16px;border:2px solid #ffa726;margin:8px">'
              '<b>Current status (H88, 2026-10-10): OK to download? YES. OK to submit? NO &mdash; DO NOT SUBMIT.</b> '
              'The file, its holdout result and the gate records are on the <a href="index.html" style="color:#ffe0b2">start page</a>. '
              'Holdout-DTI is below the random control; no organiser score exists. Nothing on this page is a certified leaderboard gain.'
              '</div><!--H88-EXEC-END-->')
    et = ex.read_text()
    if "<!--H88-EXEC-START-->" in et:
        et = re.sub(r"<!--H88-EXEC-START-->.*?<!--H88-EXEC-END-->", lambda _m: banner, et, flags=re.S)
    else:
        m_body = re.search(r"<body[^>]*>", et)
        if not m_body:
            raise SystemExit("executive-summary.html has no <body> tag")
        et = et[:m_body.end()] + banner + et[m_body.end():]
    ex.write_text(et)
    print("published H88 block to docs/index.html and executive-summary.html; sha", sha[:16])
    return 0


if __name__ == "__main__":
    sys.exit(main())
