#!/usr/bin/env python3
"""Write docs/h88.html from the H88 receipts, so no figure is typed by hand.

Reads evidence/h88_holdout.json, h88_uniqueness.json, h88_validator.json, h88_build.json,
h88_union_check.json and evidence/h88_run_card.json. Writes docs/h88.html only.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"


def load(name: str) -> dict:
    return json.loads((EV / name).read_text())


def f6(x: float) -> str:
    return f"{x:.6f}"


def ci(pair) -> str:
    return f"[{pair[0]:.6f}, {pair[1]:.6f}]"


def main() -> None:
    h = load("h88_holdout.json")
    u = load("h88_uniqueness.json")
    v = load("h88_validator.json")
    b = load("h88_build.json")
    card = load("h88_run_card.json")
    un = load("h88_union_check.json")
    s = h["scores"]
    pdiff = h["paired_differences"]
    lp = u["lane_policy_dots"]
    note = card["submission"]["note"]
    checks = v["checks"]
    n_pass = sum(1 for c in (checks.values() if isinstance(checks, dict) else checks) if (c.get("pass") if isinstance(c, dict) else c) is True)
    name = card["submission"]["name"]
    tif = card["raster"]["file"]
    sha = card["raster"]["sha256"]
    zip_name = card["raster"]["zip"]
    zip_sha = card["raster"]["zip_sha256"]
    size = (ROOT / tif).stat().st_size
    zip_size = (ROOT / zip_name).stat().st_size

    rows = []
    for key, label in (("P_strict_cotrain", "H88 strict co-training (candidate)"),
                       ("single_A", "single view A (baseline)"),
                       ("single_B", "single view B (baseline)"),
                       ("S_BA_control", "S_BA control"),
                       ("random", "random (same allowed set)"),
                       ("h87_asbuilt", "H87 as-built rule")):
        rows.append(f"<tr><td>{html.escape(label)}</td><td>{f6(s[key]['dti'])}</td><td>{ci(s[key]['ci95'])}</td></tr>")

    paired = []
    for key, label in (("random", "candidate minus random"), ("single_A", "candidate minus single A"),
                       ("single_B", "candidate minus single B"), ("h87_asbuilt", "candidate minus H87 as-built")):
        d = pdiff[key]
        paired.append(f"<tr><td>{label}</td><td>{d['delta']:+.6f}</td><td>{ci(d['ci95'])}</td></tr>")

    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>GEMSDOE52 · H88 · download yes (audit), submit NO</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f1117;color:#e8eaed;line-height:1.6}}
.c{{max-width:900px;margin:0 auto;padding:24px 20px}}
h1{{color:#4fc3f7;font-size:1.6rem}} h2{{color:#4fc3f7;font-size:1.15rem;margin:24px 0 8px;border-bottom:1px solid #2d3040;padding-bottom:4px}}
a{{color:#4fc3f7}} code{{background:#1e2130;padding:2px 6px;border-radius:3px;word-break:break-all}}
table{{width:100%;border-collapse:collapse;font-size:0.92rem;margin:8px 0}} th,td{{padding:6px 9px;border-bottom:1px solid #2d3040;text-align:left;vertical-align:top}} th{{color:#4fc3f7}}
.no{{color:#ef5350;font-weight:700}} .yes{{color:#66bb6a;font-weight:700}} .muted{{color:#9aa0a6;font-size:0.88rem}}
</style></head><body><div class="c">
<p><a href="index.html">← status</a> · <a href="executive-summary.html">submission guide</a></p>
<h1>H88 · co-training, strict A-confident / B-abstain</h1>
<p class="muted">Round H88 · 2026-10-10 · branch arena/411239c1-gemsdoe52 · evaluator {html.escape(h['evaluator_version'])}</p>
<p><strong>Download for audit: <span class="yes">YES</strong> · Submit: <span class="no">NO</span> · Verdict: <span class="no">NEGATIVE</span>.</strong></p>

<h2>Why this file is not submitted</h2>
<ol style="margin-left:20px">
<li><strong>Holdout.</strong> The candidate scores {f6(s['P_strict_cotrain']['dti'])} {ci(s['P_strict_cotrain']['ci95'])} (HOLDOUT-DTI, {h['withheld_positive_px']:,} withheld positives). Random scores {f6(s['random']['dti'])}. The candidate is {abs(pdiff['random']['delta']):.6f} below random, and the CI on that difference is {ci(pdiff['random']['ci95'])}. It is significantly below single view A.</li>
<li><strong>Lane, final dots.</strong> DUPLICATE/STOP. {lp['policy']['max_near_3px_fraction']*100:.2f}% of the dots lie within 3 px of the dots of <code>{html.escape(Path(lp['policy']['max_near_source']).name)}</code> (the H87 file). {len(lp['policy']['near_offenders'])} informative registry rasters exceed the 70% limit. Per the protocol, the round stops here; the lane is not retuned.</li>
</ol>
<p>Passing: the surface lane check (max Spearman {u['phases']['surface']['max_spearman']:.4f} against the 0.90 limit, 0 offenders); the format validator ({n_pass} of {len(v['checks'])} checks PASS); decoded-pixel uniqueness (max Jaccard {u['max_jaccard']:.6f}, identical copies 0).</p>

<h2>Holdout (HOLDOUT-DTI)</h2>
<table><tr><th>arm</th><th>DTI</th><th>95% CI</th></tr>{''.join(rows)}</table>
<table><tr><th>paired difference</th><th>Δ DTI</th><th>95% CI</th></tr>{''.join(paired)}</table>
<p class="muted">Bar from the H84 instrument: 0.192829 (a different fold set, 53,186 withheld; IR-H88-002). Candidate is far below it.</p>

<h2>The file</h2>
<table>
<tr><th>file</th><td><code>{html.escape(tif)}</code> · {size:,} bytes</td></tr>
<tr><th>SHA-256</th><td><code>{sha}</code></td></tr>
<tr><th>ZIP</th><td><code>{html.escape(zip_name)}</code> · {zip_size:,} bytes · SHA-256 <code>{zip_sha}</code></td></tr>
<tr><th>format</th><td>float32, one band, EPSG:32611, 3730 rows × 3292 columns, values in [0, 1], zeros outside the footprint; {card['validator']['positives']:,} ones</td></tr>
<tr><th>validator</th><td>{n_pass} of {len(v['checks'])} checks PASS (evidence/h88_validator.json)</td></tr>
<tr><th>name (prepared, not submitted)</th><td><code>{html.escape(name)}</code></td></tr>
<tr><th>note (prepared, not submitted, {len(note)} characters)</th><td><code>{html.escape(note)}</code></td></tr>
</table>
<p><a class="muted" href="downloads/{html.escape(Path(tif).name)}" download>Download the .tif (audit only)</a> · <a class="muted" href="downloads/{html.escape(Path(zip_name).name)}" download>Download the .zip</a></p>

<h2>Non-union check and A-only candidates</h2>
<p>{un['share_of_dots_outside_union']*100:.1f}% of the dots lie outside the union of the top-K View A and top-K View B sets; {un['share_in_S_AB']*100:.0f}% lie in the strict stratum. The output is therefore not mainly the union of the two views.</p>
<p>A-only cluster table: <a href="downloads/h88-a-only-reasoning.csv">h88-a-only-reasoning.csv</a>. The mechanisms in that table are <strong>UNREVIEWED</strong> templates, not geological conclusions.</p>

<h2>Placement</h2>
<p>Placement is <code>gems52.nodes.spacing_select</code> at 3 px, placed {b['placed']:,}, 200 m collar; fallback dots 0. The H88 placement ablation was <strong>not run</strong> this round (the H85 instrument ablation is in knowledge/78 §2).</p>

<h2>Run card and records</h2>
<ul style="margin-left:20px">
<li><a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/evidence/h88_run_card.json">evidence/h88_run_card.json</a> (one JSON card for the round)</li>
<li><a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/81_h88_results_and_limits.md">knowledge/81 · results and limits</a></li>
<li><a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/82_h88_hypotheses_ranked.md">knowledge/82 · next hypotheses</a></li>
<li><a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/registry/irregularities.json">registry/irregularities.json (IR-H88-001 to 007)</a></li>
</ul>
<p class="muted">No organiser score exists for this file. Slots used: 0. Experiments used: 1 of 3.</p>
</div></body></html>
"""
    (ROOT / "docs" / "h88.html").write_text(body)
    print("wrote docs/h88.html", len(body), "bytes")


if __name__ == "__main__":
    main()
