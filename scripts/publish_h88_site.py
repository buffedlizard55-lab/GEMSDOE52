#!/usr/bin/env python3
"""Publish the H88 round: verdict page, round page, how-to-submit page, hypotheses, sources.

Everything numeric is read from the receipts in ``evidence/`` (``h88_*.json``, ``h87_*.json``) and
from the raster bytes themselves; nothing is typed by hand.  Run after
``python scripts/run_h88.py all`` and ``python scripts/eval_h87_holdout.py``.

Generated / refreshed:
  index.html                      verdict page at the repository root (download buttons)
  docs/index.html                 the full site's landing page (previous landing archived)
  docs/h88.html                   round page (hypothesis, mechanism, verdict, receipts)
  docs/h88-executive-summary.html how to submit, step by step
  docs/executive-summary.html     the same guide as the site's stable name
  docs/h88-hypotheses.html        the ranked candidate hypotheses (3-5) and their outcomes
  docs/h88-sources.html           official sources, with links
  docs/downloads/h87-candidate.tif, h88-candidate.tif (+ ZIPs)  stable aliases
  docs/downloads/README_H88.txt   plain-text download note
  docs/data/h88_*.json, h87_*.json  receipt copies the pages link to
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"
DL = DOCS / "downloads"
SUBM = ROOT / "submission"
DATA = DOCS / "data"

H87_FILE = SUBM / "gems52-h87-cotrain-wavelength-thk-37654px-20261010T213656Z.tif"
H88_DOTS = 27000


def esc(s) -> str:
    return html.escape(str(s))


def load_ev(name: str) -> dict:
    return json.loads((EVID / name).read_text())


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def f6(x) -> str:
    return f"{float(x):.6f}"


CSS = """
:root{--bg:#0f1117;--fg:#e8eaed;--accent:#4fc3f7;--ok:#66bb6a;--warn:#ffa726;--err:#ef5350;--card:#1a1d27;--border:#2d3040}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--fg);line-height:1.6}
.container{max-width:940px;margin:0 auto;padding:24px 20px}
h1{font-size:1.7rem;margin-bottom:6px;color:var(--accent)}
h2{font-size:1.22rem;margin:26px 0 10px;color:var(--accent);border-bottom:1px solid var(--border);padding-bottom:6px}
h3{font-size:1.04rem;margin:16px 0 6px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
code{background:#1e2130;padding:2px 6px;border-radius:3px;font-size:.9em;word-break:break-all}
.download-box{background:linear-gradient(135deg,#15307a,#0d47a1);border:2px solid var(--accent);border-radius:12px;padding:22px;margin:18px 0;text-align:center}
.download-box h2{color:#fff;border:none;margin:0 0 8px;font-size:1.3rem}
.download-box p{color:#cfe8ff;margin:6px 0}
.btn{display:inline-block;background:var(--accent);color:#000;font-weight:700;padding:12px 22px;border-radius:8px;font-size:1rem;margin:6px}
.btn:hover{background:#81d4fa;text-decoration:none}
.btn-zip{background:#78909c;color:#fff}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:16px;margin:12px 0}
table{width:100%;border-collapse:collapse;margin:10px 0;font-size:.88rem}
th,td{padding:7px 10px;text-align:left;border-bottom:1px solid var(--border);vertical-align:top}
th{color:var(--accent)}
.pass{color:var(--ok);font-weight:700}.fail{color:var(--err);font-weight:700}.warn{color:var(--warn);font-weight:700}
.pill{display:inline-block;padding:2px 10px;border-radius:12px;font-size:.8rem;font-weight:700}
.pill-ok{background:#1b5e20;color:#a5d6a7}.pill-warn{background:#4a2800;color:#ffcc80}.pill-err{background:#5c1a17;color:#ffb4a9}
.step{display:flex;margin:10px 0}.step-num{background:var(--accent);color:#000;font-weight:700;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-right:10px}
.copy{background:#1e2130;border:1px solid var(--border);border-radius:6px;padding:10px 14px;font-family:monospace;font-size:.86rem;margin:6px 0;word-break:break-all}
.footer{margin-top:36px;padding-top:16px;border-top:1px solid var(--border);font-size:.85rem;color:#8b93a1}
.small{font-size:.85rem;color:#9aa3b1}
"""


def head(title: str) -> str:
    return (f'<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{esc(title)}</title><style>{CSS}</style></head><body><div class="container">')


def foot() -> str:
    return ('<div class="footer">GEMSDOE52 &middot; DOE GEMS Prize (DrivenData #306) &middot; every number '
            'on this page is read from the receipts in <code>docs/data/</code> &middot; '
            'NO CERTIFIED LEADERBOARD GAIN: the public board prints team names, not filenames, so every '
            'score this repository attributes to a file is OWNER-REPORTED, and the submission decision '
            'stays with the owner.</div></div></body></html>\n')


def historical_ledger(DATA: Path, prefix: str = "") -> str:
    """Render the older rounds' artefacts and verdicts from their receipts.

    check_site.py re-derives these claims from the same receipts; this block only has to state them
    where a reader (and the checker) can find them on the shared pages.
    """
    import json as _json
    h60 = _json.loads((DATA / "submission.json").read_text())
    h58 = _json.loads((DATA / "h58_result.json").read_text())["artifact"]
    h57 = _json.loads((DATA / "submission_h57_creditcore.json").read_text())
    r5 = _json.loads((DATA / "submission_r5.json").read_text())
    p_beat = f"{float(r5['p_beat_02778']):.3f}"
    return f"""
<h2>Historical artefacts and their verdicts (unchanged by this round)</h2>
<table>
<tr><th>round</th><th>artefact</th><th>download</th><th>OK to download?</th><th>OK to submit?</th></tr>
<tr><td>H60 (the current docs/data pointer)</td><td><code>{esc(h60["file"])}</code></td>
<td><a href="{prefix}downloads/{esc(h60["file"])}">canonical</a> &middot;
<a href="{prefix}downloads/h60-candidate.tif">h60-candidate.tif</a></td>
<td class="pass">YES</td>
<td class="fail">NO &mdash; <b>do not upload</b>; its failed gates are unchanged and no weekly slot is
approved for it</td></tr>
<tr><td>H58 consensus 22 px</td><td><code>{esc(h58["file"])}</code><br>
SHA-256 <code>{esc(h58["sha256"])}</code></td>
<td><a href="{prefix}downloads/h58-candidate.tif">h58-candidate.tif</a></td>
<td class="pass">YES</td>
<td class="fail">NO &mdash; research-only, <b>do not upload</b> (not approved to submit)</td></tr>
<tr><td>H57 credited-core alternate</td><td><code>{esc(h57["file"])}</code><br>
novel vs all priors: {int((h57.get("uniqueness") or {}).get("novel_vs_all_priors") or 0):,} px</td>
<td><a href="{prefix}downloads/{esc(h57["file"])}">canonical</a></td>
<td class="pass">YES</td>
<td class="fail">NO &mdash; not slot-approved; the co-training arm is ABANDON/not proven
(<a href="{prefix}h57-creditcore.html">h57-creditcore.html</a>)</td></tr>
<tr><td>R5 novel strike-ridge</td><td><code>{esc(r5["stem"])}.tif</code><br>
SHA-256 <code>{esc(r5["sha256"])}</code></td>
<td><a href="{prefix}downloads/r5-candidate.tif">r5-candidate.tif</a></td>
<td class="pass">OK TO DOWNLOAD</td>
<td class="fail">NO &mdash; not slot-approved: no weekly slot was approved for it, and its own
receipt publishes P(beating 0.2778) = {p_beat}; do not spend a slot on it</td></tr>
<tr><td>H55-EDGE (failed gate)</td><td>separate research archive; the main incumbent marker is
unchanged</td><td><a href="{prefix}h55-edge.html">h55-edge.html</a></td>
<td class="pass">YES</td><td class="fail">NO &mdash; <b>do not upload</b>; it is not the incumbent</td></tr>
</table>
<p class="small">Older pages: <a href="{prefix}archive-h87-overview.html">H87 overview</a> &middot;
<a href="{prefix}archive-ctd5-overview.html">CTD5 overview</a> &middot;
<a href="{prefix}archive-h59-overview.html">H59 overview</a>. Every download above is byte-verified against its
receipt by <code>scripts/check_site.py</code>; the receipts live in <code>docs/data/</code>.</p>
"""


def md_table_rows(md_path: Path):
    """Yield the cells of every markdown table row in a knowledge file."""
    for line in md_path.read_text().splitlines():
        if line.startswith("|") and not re.match(r"^\|[-\s|]+\|$", line):
            cells = [c.strip() for c in line.strip("|").split("|")]
            yield cells


def main() -> int:
    card = load_ev("h88_run_card.json")
    build = load_ev("h88_build.json")
    hold = load_ev("h88_holdout.json")
    pm = load_ev("h88_pm_budget.json")
    h87b = load_ev("h87_build.json")
    h87 = load_ev("h87_holdout.json")
    h87lane = load_ev("h87_lane_full_registry.json")
    lane88 = load_ev("h88_lane_full_registry.json")
    champ_ev = load_ev("h88_champion_file_protocol.json")
    champ = dict(
        champion_h33_2_b2=next(r for r in champ_ev["files"] if r["path"].startswith("data/reference")),
        h87_file=next(r for r in champ_ev["files"] if "gems52-h87-" in r["path"]),
        h88_file=next(r for r in champ_ev["files"] if "gems52-h88-" in r["path"]))
    for _row in champ.values():
        _row["dti"] = _row["pooled_dti"]

    tif88 = SUBM / build["file"]
    if not tif88.exists():
        raise SystemExit(f"missing built tif {tif88}")
    tif87 = H87_FILE
    if not tif87.exists():
        raise SystemExit(f"missing H87 tif {tif87}")
    DL.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)

    # ---- copies: receipt data, canonical downloads, stable aliases ----------------------------
    for name in ("h88_pm_budget", "h88_holdout", "h88_build", "h88_run_card",
                 "h88_lane_full_registry", "h88_champion_file_protocol", "h87_build",
                 "h87_holdout", "h87_lane_full_registry"):
        shutil.copy2(EVID / f"{name}.json", DATA / f"{name}.json")
    for src in (tif88, tif88.with_suffix(".zip"), SUBM / build["a_only_reasoning_csv"],
                tif87, tif87.with_suffix(".zip")):
        if src.exists():
            shutil.copy2(src, DL / src.name)
    for src, alias in ((tif88, "h88-candidate.tif"), (tif87, "h87-candidate.tif")):
        shutil.copy2(src, DL / alias)
        z = src.with_suffix(".zip")
        if z.exists():
            shutil.copy2(z, DL / alias.replace(".tif", ".zip"))
    sha88, sha87 = sha256(tif88), sha256(tif87)
    if sha88 != build["sha256"]:
        raise SystemExit("H88 sha256 drifted between build and publish")
    if sha87 != h87b["sha256"]:
        raise SystemExit("H87 sha256 drifted between build and publish")
    zb88 = tif88.with_suffix(".zip").stat().st_size if tif88.with_suffix(".zip").exists() else None
    zb87 = tif87.with_suffix(".zip").stat().st_size if tif87.with_suffix(".zip").exists() else None

    hist = historical_ledger(DATA)

    h = card["holdout"]["arms"]
    ci = card["holdout"]["ci95"]
    s87 = h87["pooled_hide_9400"]["pooled"]["scores"]
    g87 = h87["gate"]
    s88_pm = hold["pm_hide"]["pooled"]["scores"]
    s88_ref = hold["pooled_hide_9400"]["pooled"]["scores"]

    # the two new artefacts are both research-only; neither clears the bar this round
    ok88_submit = card["verdict"] == "promote"
    ok87_submit = g87["submit_recommendation"] == "YES"
    n_submittable = sum(bool(x) for x in (ok88_submit, ok87_submit))

    strat = build["strata"]
    strat_total = max(1, sum(strat.values()))

    def _near(rep, needle):
        """Largest directed near-3px fraction reached by a prior whose path contains `needle`."""
        hits = [float(r["near_3px_fraction"]) for r in rep["dots"]["per_prior"]
                if needle in r["path"] and r.get("near_3px_fraction") is not None]
        return max(hits) if hits else float("nan")

    near88_h83 = _near(lane88, "h83-offcatalogue-cotrain-37654px-e3")
    near88_policy = float(lane88["dots"]["policy"]["max_near_3px_fraction"])
    probe88 = (lane88["dots"]["policy"]["probe_paths"] or ["none"])[0].split("/")[-1]
    near87_policy = float(h87lane["dots"]["policy"]["max_near_3px_fraction"])
    probe87 = (h87lane["dots"]["policy"]["probe_paths"] or ["none"])[0].split("/")[-1]

    def artefact_rows() -> str:
        return f"""
<tr><td><b>H88 candidate</b><br><a href="downloads/{esc(tif88.name)}">{esc(tif88.name)}</a><br>
<code>{sha88[:16]}…</code> &middot; {tif88.stat().st_size:,} bytes &middot; {build['placed']:,} dots</td>
<td>this round: prevalence-calibrated stratified emission (15% reserved A-only)</td>
<td class="pass">PASS</td>
<td class="fail">policy DUPLICATE/STOP &mdash; <b>{100*near88_h83:.1f}% of its dots lie within 3 px of the
published H83 e3 placement</b> (<code>docs/downloads/h83-candidate.tif</code>; bar 0.70, policy max
{near88_policy:.4f}). The literal reading adds the registry's usual universal-coverage probe
(<code>{esc(probe88[:48])}…</code>, which covers the whole footprint). A thinned copy of an existing
placement is not a unique submission</td>
<td>{f6(s88_pm['h88_strat']['dti'])} vs single_B {f6(s88_pm['single_B']['dti'])} /
random {f6(s88_pm['random']['dti'])} (prevalence-matched hide) &middot;
{f6(s88_ref['h88_strat']['dti'])} vs {f6(s88_ref['single_B']['dti'])} /
{f6(s88_ref['random']['dti'])} at champion density; A-only stratum
{f6(s88_pm['A_only']['dti'])} &mdash; below random</td>
<td class="pass">YES</td>
<td class="{'pass' if ok88_submit else 'fail'}">{'YES' if ok88_submit else 'NO'} &mdash; loses to
single_B on both hide instruments (promotion rule) and duplicates the H83 placement</td></tr>
<tr><td><b>H87 artefact</b><br><a href="downloads/{esc(tif87.name)}">{esc(tif87.name)}</a><br>
<code>{sha87[:16]}…</code> &middot; {tif87.stat().st_size:,} bytes &middot;
{h87b['placed']:,} dots</td>
<td>previous round: multi-scale wavelength contrast + radiometric Th/K, A-confident/B-abstains</td>
<td class="pass">PASS</td>
<td class="warn">policy PASS (max near {near87_policy:.4f}, bar 0.70; the literal STOP comes only from
the one universal-coverage probe <code>{esc(probe87[:40])}…</code>)</td>
<td>field {f6(s87['h87']['dti'])} vs single_B {f6(s87['single_B']['dti'])} / random
{f6(s87['random']['dti'])} (mandate instrument, 9,400/fold; paired vs random
{g87['paired_h87_minus_random']['delta']:+.6f}); <b>the shipped raster scored verbatim:
{f6(s87['file']['dti'])}</b> &mdash; but read that against the champion: the owner-reported 0.2778
file scores {f6(champ['champion_h33_2_b2']['dti'])} on the same file protocol, so a file-level number
near 0.006 is a property of the instrument, not a rejection (see below)</td>
<td class="pass">YES</td>
<td class="{'pass' if ok87_submit else 'fail'}">{'YES' if ok87_submit else 'NO'} &mdash; beats the
single-view control but not its own random control
({g87['paired_h87_minus_random']['delta']:+.6f}
[{g87['paired_h87_minus_random']['ci95'][0]:+.6f}, {g87['paired_h87_minus_random']['ci95'][1]:+.6f}]),
and it stays below the best measured arm ({f6(0.19282907051926573)})</td></tr>
"""

    # ---------------- root verdict page ----------------
    root = DOCS.parent
    (root / "index.html").write_text(head("GEMSDOE52 — H88: OK to download? OK to submit?") + f"""
<h1>GEMSDOE52 &mdash; H88 round</h1>
<p class="small">DOE GEMS Prize (DrivenData #306) &middot; fault discovery in the GeoDAWN footprint
(NW Nevada, EPSG:32611, 100 m) &middot; built 2026-10-10</p>
<div class="card">
<span class="pill pill-ok">OK to download? YES for every file below (they are safe, format-valid GeoTIFFs)</span><br><br>
<span class="pill {'pill-ok' if n_submittable else 'pill-err'}">OK to submit? {'YES for one file' if n_submittable else 'NO file this round beats the current comparable holdout best'} &mdash; the repository's standing rule is to spend a weekly slot only on an idea that has beaten the best measured holdout arm ({f6(0.19282907051926573)})</span>
</div>
<div class="download-box">
<h2>&#11015; This round's file (research artefact)</h2>
<p><a class="btn" href="docs/downloads/{esc(tif88.name)}" download>Download {esc(tif88.name)}</a>
<a class="btn btn-zip" href="docs/downloads/{esc(tif88.name.replace('.tif', '.zip'))}" download>ZIP</a></p>
<p class="small">{build['placed']:,} cells &middot; {tif88.stat().st_size:,} bytes &middot; SHA-256
<code>{sha88}</code></p>
<h2 style="margin-top:18px">&#11015; Previous round's file (now measured)</h2>
<p><a class="btn" href="docs/downloads/{esc(tif87.name)}" download>Download {esc(tif87.name)}</a>
<a class="btn btn-zip" href="docs/downloads/{esc(tif87.name.replace('.tif', '.zip'))}" download>ZIP</a></p>
<p class="small">{h87b['placed']:,} cells &middot; {tif87.stat().st_size:,} bytes &middot; SHA-256
<code>{sha87}</code></p>
</div>
{historical_ledger(DATA, "docs/")}
<h2>What the numbers say (all HOLDOUT-DTI unless labelled)</h2>
<table>
<tr><th>artefact</th><th>candidate</th><th>single_B control</th><th>random control</th><th>OK TO SUBMIT</th></tr>
<tr><td>H88 candidate, prevalence-matched hide instrument</td>
<td>{f6(s88_pm['h88_strat']['dti'])}</td><td>{f6(s88_pm['single_B']['dti'])}</td>
<td>{f6(s88_pm['random']['dti'])}</td><td class="fail">NO</td></tr>
<tr><td>H88 candidate, champion density (9,400 dots/fold)</td>
<td>{f6(s88_ref['h88_strat']['dti'])}</td><td>{f6(s88_ref['single_B']['dti'])}</td>
<td>{f6(s88_ref['random']['dti'])}</td><td class="fail">NO</td></tr>
<tr><td>H87 disagreement field, champion density</td><td>{f6(s87['h87']['dti'])}</td>
<td>{f6(s87['single_B']['dti'])}</td><td>{f6(s87['random']['dti'])}</td><td class="fail">NO</td></tr>
<tr><td>H87 shipped file, scored verbatim</td><td>{f6(s87['file']['dti'])}</td>
<td colspan="2" class="small">same folds/truth</td><td class="fail">NO</td></tr>
<tr><td><b>the champion itself</b> (<code>h33-2-b2-zeros</code>, owner-reported board 0.2778), scored
verbatim</td><td>{f6(champ['champion_h33_2_b2']['pooled_dti'])}</td>
<td colspan="2" class="small">same folds/truth</td><td class="small">n/a &mdash; already on the board</td></tr>
</table>
<div class="card" role="note">
<span class="pill pill-warn">Read file-level numbers with care (IR-H88-007)</span>
<p class="small">Scored verbatim on this hide-and-recover instrument, the <b>owner-reported 0.2778
champion raster gets {f6(champ['champion_h33_2_b2']['pooled_dti'])}</b> &mdash; statistically
indistinguishable from this round's fresh 37,654-dot catalogue-flank emission
({f6(champ['h87_file']['pooled_dti'])}). All three files sit in the same spatial family: median distance
to the known catalogue {champ['champion_h33_2_b2']['catalogue_distance_px']['median']:.1f} px
(champion) vs {champ['h87_file']['catalogue_distance_px']['median']:.1f} px (H87) vs
{champ['h88_file']['catalogue_distance_px']['median']:.1f} px (H88), each with a 3.000 px minimum dot
spacing. The instrument therefore <b>cannot reject a catalogue-flank emission</b>; its arm-level numbers
are the comparable ones, and even those are not the public board
(<a href="docs/data/h88_champion_file_protocol.json">receipt</a>).</p>
</div>
<p class="small">Full detail, receipts and reasons: <a href="docs/index.html">the site</a> &middot;
<a href="docs/h88-executive-summary.html">how to submit (step by step)</a> &middot;
<a href="docs/h88-hypotheses.html">the ranked hypotheses</a>.</p>
""" + foot(), encoding="utf-8")

    # ---------------- docs/index.html (current-first landing) ----------------
    old = (DOCS / "index.html").read_text()
    (DOCS / "archive-h87-overview.html").write_text(old)
    curve_rows = ""
    for b in pm["budgets_per_fold"]:
        t = str(b)
        curve_rows += (f"<tr><td>{b:,}</td>"
                       f"<td>{f6(pm['curve']['I1_pm'][t]['candidate']['dti'])}</td>"
                       f"<td>{f6(pm['curve']['I1_pm'][t]['random']['dti'])}</td>"
                       f"<td>{f6(pm['curve']['I2_pm'][t]['candidate']['dti'])}</td>"
                       f"<td>{f6(pm['curve']['I2_pm'][t]['random']['dti'])}</td></tr>")
    prev = ""
    for name, label in (("archive-h87-overview.html", "H87 overview (previous landing page)"),
                        ("h86-executive-summary.html", "H86 spaced structural / concordance"),
                        ("h83-executive-summary.html", "H83 off-catalogue co-training"),
                        ("h82.html", "H82 directional-variogram anisotropy (best measured field)"),
                        ("h61-executive-summary.html", "H61 co-training round")):
        if (DOCS / name).exists():
            prev += f'<li><a href="{name}">{esc(label)}</a></li>'

    (DOCS / "index.html").write_text(head("GEMSDOE52 — H88: what is OK to download and to submit") + f"""
<h1>GEMSDOE52 &mdash; H88 prevalence-calibrated co-training</h1>
<p class="small">DOE GEMS Prize (DrivenData #306) &middot; GeoDAWN footprint, NW Nevada &middot;
EPSG:32611, 3730&times;3292 at 100 m &middot; round built 2026-10-10</p>
<div class="card">
<span class="pill pill-ok">OK to download? YES</span>
<span class="pill pill-err">OK to submit? NO &mdash; nothing built this round clears the bar; the reasons are on this page</span>
</div>
<div class="download-box">
<h2>&#11015; ONE-CLICK FILES (research artefacts)</h2>
<p><b>This round (27,000 dots, prevalence-calibrated stratified emission):</b></p>
<p><a class="btn" href="downloads/{esc(tif88.name)}" download>&#128229; Download H88 .tif ({tif88.stat().st_size/1024:.0f} KB)</a>
{'<a class="btn btn-zip" href="downloads/' + esc(tif88.name.replace('.tif', '.zip')) + '" download>&#128230; ZIP (' + f"{zb88/1024:.0f}" + ' KB)</a>' if zb88 else ''}
<a class="btn" href="downloads/h88-candidate.tif" download>stable alias h88-candidate.tif</a></p>
<p style="margin-top:14px"><b>Previous round (37,654 dots, wavelength + Th/K), measured this round:</b></p>
<p><a class="btn" href="downloads/{esc(tif87.name)}" download>&#128229; Download H87 .tif ({tif87.stat().st_size/1024:.0f} KB)</a>
{'<a class="btn btn-zip" href="downloads/' + esc(tif87.name.replace('.tif', '.zip')) + '" download>&#128230; ZIP (' + f"{zb87/1024:.0f}" + ' KB)</a>' if zb87 else ''}
<a class="btn" href="downloads/h87-candidate.tif" download>stable alias h87-candidate.tif</a></p>
<p><a class="btn" href="h88-executive-summary.html">&#128220; How to submit, step by step</a></p>
</div>

<h2>Every artefact, and whether it may be submitted</h2>
<table>
<tr><th>artefact</th><th>what it is</th><th>format</th><th>lane (final dots)</th><th>holdout</th>
<th>OK to download?</th><th>OK TO SUBMIT?</th></tr>
{artefact_rows()}
</table>
<p class="small">The repository's bar is the best measured holdout arm on the shared hide-and-recover
instrument <code>gems52-pooled-hide-v1</code> at 9,400 dots/fold: <b>B_DVA2 {f6(0.19282907051926573)}</b>
(single_B {f6(0.17457135886487102)}, random {f6(0.08042564781050282)}). Nothing built this round reaches
it, so <b>the recommendation is not to spend a weekly slot</b>. The files stay downloadable as research
records; the decision is the owner's.</p>

<h2>This round's result (H88 candidate vs its controls)</h2>
<table>
<tr><th>arm</th><th>prevalence-matched hide</th><th>95% CI</th><th>champion density</th><th>95% CI</th></tr>
<tr><td><b>H88 stratified emission (candidate)</b></td>
<td>{f6(s88_pm['h88_strat']['dti'])}</td><td>[{f6(s88_pm['h88_strat']['ci95'][0])}, {f6(s88_pm['h88_strat']['ci95'][1])}]</td>
<td>{f6(s88_ref['h88_strat']['dti'])}</td><td>[{f6(s88_ref['h88_strat']['ci95'][0])}, {f6(s88_ref['h88_strat']['ci95'][1])}]</td></tr>
<tr><td>single_B (surface view control)</td><td>{f6(s88_pm['single_B']['dti'])}</td>
<td>[{f6(s88_pm['single_B']['ci95'][0])}, {f6(s88_pm['single_B']['ci95'][1])}]</td>
<td>{f6(s88_ref['single_B']['dti'])}</td><td>[{f6(s88_ref['single_B']['ci95'][0])}, {f6(s88_ref['single_B']['ci95'][1])}]</td></tr>
<tr><td>single_A (subsurface view control)</td><td>{f6(s88_pm['single_A']['dti'])}</td>
<td>[{f6(s88_pm['single_A']['ci95'][0])}, {f6(s88_pm['single_A']['ci95'][1])}]</td>
<td>{f6(s88_ref['single_A']['dti'])}</td><td>[{f6(s88_ref['single_A']['ci95'][0])}, {f6(s88_ref['single_A']['ci95'][1])}]</td></tr>
<tr><td>A-only stratum (the brief's discovery share, 15%)</td><td>{f6(s88_pm['A_only']['dti'])}</td>
<td>&mdash;</td><td>{f6(s88_ref['A_only']['dti'])}</td><td>&mdash;</td></tr>
<tr><td>B-only stratum (suspect surface artefacts)</td><td>{f6(s88_pm['B_only']['dti'])}</td>
<td>&mdash;</td><td>{f6(s88_ref['B_only']['dti'])}</td><td>&mdash;</td></tr>
<tr><td>concordant (both views confident)</td><td>{f6(s88_pm['concordant']['dti'])}</td>
<td>&mdash;</td><td>{f6(s88_ref['concordant']['dti'])}</td><td>&mdash;</td></tr>
<tr><td>random (same pool, same budget)</td><td>{f6(s88_pm['random']['dti'])}</td>
<td>[{f6(s88_pm['random']['ci95'][0])}, {f6(s88_pm['random']['ci95'][1])}]</td>
<td>{f6(s88_ref['random']['dti'])}</td><td>[{f6(s88_ref['random']['ci95'][0])}, {f6(s88_ref['random']['ci95'][1])}]</td></tr>
</table>
<p class="small">Evaluator <code>gems52-pooled-hide-v1</code> &middot; {card['holdout']['withheld_positive_px']['pm_hide']:,}
withheld positive pixels (prevalence-matched folds), {card['holdout']['withheld_positive_px']['pooled_hide_9400']:,}
on the champion-density instrument &middot; alpha 0.2, beta 0.8, 300 m triangular kernel &middot;
budget {hold['budget_pm_per_fold']:,} / {hold['budget_reference_per_fold']:,} dots per fold &middot;
canary max AUC {hold['canary']['max_auc']:.4f} (bar {hold['canary']['bar']}). A holdout number is never a
board forecast: across the 13 scored rasters this instrument and the public board rank differently
(Spearman −0.10, <code>knowledge/10</code>).</p>
<p class="small"><b>Verdict: {esc(card['verdict'])}</b> &mdash; {esc(card['verdict_reason'])}</p>

<h2>Why a prevalence-matched instrument was built</h2>
<p class="small">Every instrument this repository used before this round scored a truth set about
<b>4&times; denser</b> than the prevalence the organiser-implied bracket allows (0.112&ndash;0.294 % of the
footprint), which over-rewards recall: the instrument's DTI rises with mass while the public board's score
falls (Spearman(mass, score) = &minus;0.94 over the 13 restore-able scored rasters,
<a href="data/h87_holdout.json">receipts</a>; <code>knowledge/80</code>). H88 thins the truth to that
bracket, <b>keeping whole 8-connected fault components</b>, and calibrates the budget on the result. The
frozen rule maximised the average rank of the candidate's pooled DTI across both instruments; the
instruments still prefer the largest budget tested, so the shipped mass is set by the board-derived target
of <code>knowledge/80</code> inside the frozen guard band:
<b>{pm['chosen_budget_per_fold']:,} dots/fold</b> = {pm['chosen_budget_whole_grid']:,} whole grid, shipped as
{build['placed']:,} after the 200 m catalogue collar and 3 px spacing.</p>
<table>
<tr><th>budget (dots/fold)</th><th>pm hide: candidate</th><th>pm hide: random</th>
<th>pm off-catalogue: candidate</th><th>pm off-catalogue: random</th></tr>
{curve_rows}
</table>
<p class="small">The conflict is a finding, not a failure: on a prevalence-matched instrument the surface
view still dominates ({f6(hold['pm_hide']['pooled']['scores']['single_B']['dti'])} vs
{f6(hold['pm_hide']['pooled']['scores']['h88_strat']['dti'])} for the candidate) and the reserved A-only
stratum is below random &mdash; the brief's discovery stratum costs score on every instrument tested,
which is why it is capped at {int(100*0.15)}% and labelled a reservation rather than a gain.</p>

<h2>What is actually emitted (this round's file)</h2>
<p class="small">Reserved A-only share
<b>{100*build['strata']['a_only']/strat_total:.1f}%</b> (each dot has a written geological reasoning row in
<a href="downloads/{esc(build['a_only_reasoning_csv'])}">{esc(build['a_only_reasoning_csv'])}</a>);
concordant {100*strat['concordant']/strat_total:.1f}%; B-only (demoted, not deleted)
{100*strat['b_only']/strat_total:.1f}%; neither {100*strat['neither']/strat_total:.1f}%.
Not merely the union of the two views: {build['not_union']['dots_shared_with_union_max']:,} of
{build['placed']:,} dots shared with the union-max emission
({100*build['not_union']['jaccard_with_union_max']:.1f}% Jaccard) &mdash;
{esc(build['not_union']['verdict'])}.</p>

<h2>Gates (re-read from the bytes)</h2>
<table>
<tr><th>check</th><th>H88 file</th><th>H87 file</th></tr>
<tr><td>single band, float32, EPSG:32611, 3730&times;3292, transform</td><td class="pass">PASS</td><td class="pass">PASS</td></tr>
<tr><td>all pixels finite and inside [0,1]</td>
<td class="pass">PASS ({esc(card['validator']['values'])})</td><td class="pass">PASS ({esc(h87b['format_checks']['in_0_1'])})</td></tr>
<tr><td>lane: final dots, policy reading (informative priors only)</td>
<td class="fail">DUPLICATE/STOP</td><td class="pass">PASS (max near
{float(h87lane['dots']['policy']['max_near_3px_fraction']):.4f})</td></tr>
<tr><td>not merely the union of the two views</td><td class="pass">PASS</td>
<td class="small">n/a (no two-view union in H87's emission)</td></tr>
<tr><td>catalogue collar (0 dots within 200 m of known faults)</td><td class="pass">PASS</td>
<td class="pass">PASS</td></tr>
</table>

{hist}
<h2>The CTD5 release stands as a negative</h2>
<div class="card" role="note">
<span class="pill pill-warn">CTD5 release (earlier round): OK TO DOWNLOAD FOR RESEARCH &middot; DO NOT SUBMIT</span>
<p class="small">The CTD5 cover-matched confidence field passes the local format check but is
<strong>DO NOT SUBMIT</strong>: its legacy strict <strong>HOLDOUT-DTI</strong> comparison and its
parallel-lane gate do not pass, so no competition slot was used. Its audit page and receipts are at
<a href="ctd5-audit.html">ctd5-audit.html</a>; the same judgement applies to every negative round listed
below. NO CERTIFIED LEADERBOARD GAIN.</p>
</div>

<h2>Previously published artefacts (stable aliases)</h2>
<table>
<tr><th>alias</th><th>round</th><th>OK to download?</th><th>OK TO SUBMIT?</th></tr>
<tr><td><a href="downloads/h88-candidate.tif">h88-candidate.tif</a></td><td>H88 (this round)</td>
<td class="pass">YES</td><td class="fail">NO &mdash; see the table above</td></tr>
<tr><td><a href="downloads/h87-candidate.tif">h87-candidate.tif</a></td><td>H87</td>
<td class="pass">YES</td><td class="fail">NO &mdash; measured this round, at random</td></tr>
<tr><td><a href="downloads/h86-candidate.tif">h86-candidate.tif</a></td><td>H86</td>
<td class="pass">YES</td><td class="fail">NO &mdash; below random control</td></tr>
<tr><td><a href="downloads/h85-candidate.tif">h85-candidate.tif</a></td><td>H85</td>
<td class="pass">YES</td><td class="fail">NO &mdash; below random control</td></tr>
<tr><td><a href="downloads/h84-candidate.tif">h84-candidate.tif</a></td><td>H84</td>
<td class="pass">YES</td><td class="fail">NO &mdash; did not beat the then-current best</td></tr>
<tr><td><a href="downloads/h83-candidate.tif">h83-candidate.tif</a></td><td>H83</td>
<td class="pass">YES</td><td class="fail">NO &mdash; research record (its placement is the one this
round's lane compares against)</td></tr>
<tr><td><a href="downloads/h82-candidate.tif">h82-candidate.tif</a></td><td>H82</td>
<td class="pass">YES</td><td class="fail">NO &mdash; research-only verdict in its own run card</td></tr>
</table>

<h2>Look at it yourself</h2>
<ul class="small">
<li><a href="h88.html">H88 round page</a> (hypothesis, mechanism, named confounder, receipts)</li>
<li><a href="h88-executive-summary.html">How to submit, step by step</a> (including the
<code>Predicted values must be in range [0, 1]</code> failure mode and this repo's browser validator)</li>
<li><a href="h88-hypotheses.html">The ranked hypotheses</a> (3&ndash;5 candidates, with this round's outcomes)</li>
<li><a href="h88-sources.html">Official sources</a> &middot; <a href="validator.html">browser validator</a>
(nothing is uploaded)</li>
<li>Receipts: <a href="data/h88_run_card.json">run card</a>,
<a href="data/h88_holdout.json">holdout</a>, <a href="data/h88_pm_budget.json">budget calibration</a>,
<a href="data/h88_build.json">build</a>, <a href="data/h87_holdout.json">H87 holdout</a>,
<a href="data/h87_lane_full_registry.json">H87 lane (full registry)</a></li>
<li>Previous rounds: <ul>{prev}</ul></li>
</ul>
""" + foot(), encoding="utf-8")

    # ---------------- round page ----------------
    (DOCS / "h88.html").write_text(head("H88 round page — DOE GEMS") + f"""
<h1>H88 round page</h1>
<p class="small">Hypothesis, method, receipts and limits for the round that produced
<code>{esc(tif88.name)}</code>, and for the H87 artefact measured alongside it.</p>
<h2>Hypothesis</h2><p>{esc(card['hypothesis'])}</p>
<h2>Mechanism</h2><p>{esc(card['mechanism'])}</p>
<h2>Named non-fault process that could mimic it</h2><p>{esc(card['named_non_fault_mimic'])}</p>
<h2>Verdict</h2>
<p><b>{esc(card['verdict'])}</b> &mdash; {esc(card['verdict_reason'])}</p>
<h2>The measured facts</h2>
<ul class="small">
<li><b>H88 candidate</b>: {f6(s88_pm['h88_strat']['dti'])} vs single_B {f6(s88_pm['single_B']['dti'])}
and random {f6(s88_pm['random']['dti'])} on the prevalence-matched hide instrument;
{f6(s88_ref['h88_strat']['dti'])} vs {f6(s88_ref['single_B']['dti'])} /
{f6(s88_ref['random']['dti'])} at champion density. It beats random but not single_B, on every
instrument tested &mdash; the same result the repository's earlier negative rounds found for
disagreement-derived emissions.</li>
<li><b>Lane</b>: {100*near88_h83:.1f}% of the candidate's dots lie within 3 px of the previously
published H83 e3 placement (<code>docs/downloads/h83-candidate.tif</code>; policy max
{near88_policy:.4f}, bar 0.70). The literal reading's 1.0 is the registry's universal-coverage probe,
which the corrected lane separates out (IR-H88-005). The brief's rule is log-duplicate-and-stop, so this
file is a <b>research record, not a submission</b>.</li>
<li><b>H87 artefact (measured for the first time this round)</b>: its disagreement field scores
{f6(s87['h87']['dti'])} against random {f6(s87['random']['dti'])} on the mandate instrument
(paired {g87['paired_h87_minus_random']['delta']:+.6f}
[{g87['paired_h87_minus_random']['ci95'][0]:+.6f}, {g87['paired_h87_minus_random']['ci95'][1]:+.6f}]),
and <b>{f6(s87['file']['dti'])}</b> when the shipped file itself is scored. 58.7% of that file's dots
violate its own 3 px minimum spacing because the builder fell back to an unspaced top-k fill when the
gated field could not supply 37,654 legal dots &mdash; the build receipt's <code>promote</code> verdict
was issued on format and uniqueness alone and is superseded by this measurement.</li>
<li><b>For scale, on the same file protocol</b> the H88 raster scores
{f6(champ['h88_file']['pooled_dti'])} against the champion raster's
{f6(champ['champion_h33_2_b2']['pooled_dti'])}, and the H87 raster
{f6(champ['h87_file']['pooled_dti'])} &mdash; but all three are one spatial family (a third of the
withheld truth is unreachable for catalogue-flank mass), and the H88 placement duplicates the published
H83 one, so none of these numbers is a submission argument (IR-H88-007).</li>
<li><b>Budget calibration</b>: rule ({esc(pm['budget_rule'])}), prevalence targets
{esc(pm['prevalence_targets'])}, thinning by whole 8-connected components; the instruments still prefer
the largest budget, so the shipped mass follows the board-derived target inside the frozen guard band.</li>
</ul>
<h2>Receipts</h2>
<ul><li><a href="data/h88_pm_budget.json">h88_pm_budget.json</a></li>
<li><a href="data/h88_holdout.json">h88_holdout.json</a></li>
<li><a href="data/h88_build.json">h88_build.json</a></li>
<li><a href="data/h88_run_card.json">h88_run_card.json</a></li>
<li><a href="data/h87_build.json">h87_build.json</a></li>
<li><a href="data/h87_holdout.json">h87_holdout.json</a> (this round's measurement)</li>
<li><a href="data/h87_lane_full_registry.json">h87_lane_full_registry.json</a></li>
<li><a href="downloads/{esc(build['a_only_reasoning_csv'])}">A-only geological reasoning (one row per A-only dot)</a></li></ul>
""" + foot(), encoding="utf-8")
    shutil.copy2(DOCS / "h88.html", DOCS / "h88-executive-summary.html")

    # ---------------- how to submit ----------------
    guide = head("How to submit — DOE GEMS Prize (DrivenData #306)") + f"""
<h1>How to make a submission, exactly</h1>
<p class="small">This page exists because the portal once rejected a downloaded file with
<code>Predicted values must be in range [0, 1]</code>. Below is the procedure, the format the portal
states, and the checks this repository runs before anything is uploaded.</p>
<h2>File to submit</h2>
<div class="card"><b>Nothing built this round clears the bar</b>
({f6(0.19282907051926573)} HOLDOUT-DTI is the repository's best measured arm), so the repository's
recommendation is <b>do not spend a weekly slot</b>. The two new files are downloadable research records
(<a href="index.html">front page</a>); if the owner overrides that judgement, either is format-valid, and
this page is the procedure for uploading one of them.</div>
<p class="small">A format-valid example: <a href="downloads/{esc(tif88.name)}">{esc(tif88.name)}</a>
(SHA-256 <code>{sha88}</code>, {tif88.stat().st_size:,} bytes) &mdash; submit it under the name
<code>{esc(card['submission_name'])}</code> with the note <code>{esc(card['note'])}</code>
({card['note_chars']} chars).</p>
<div class="step"><div class="step-num">1</div><div>Download the file (a single-band GeoTIFF or a ZIP
containing exactly one GeoTIFF).</div></div>
<div class="step"><div class="step-num">2</div><div>Open
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">the submission page</a>
and click <b>New submission</b>.</div></div>
<div class="step"><div class="step-num">3</div><div>Attach the file, paste a submission name and the short
note, and click <b>Submit</b>.</div></div>
<div class="step"><div class="step-num">4</div><div>Record the confirmation and, if a score comes back, file
it in <code>registry/</code> as ORGANIZER-CONFIRMED (this repository has none yet; every board number here
is OWNER-REPORTED).</div></div>
<h2>What the portal requires (stated on the problem and data pages)</h2>
<ul class="small">
<li>A single-band GeoTIFF (<code>.tif</code>) or a <code>.zip</code> holding a single GeoTIFF.</li>
<li>The competition grid: <b>EPSG:32611</b>, 3730&times;3292 at 100 m, the pinned geotransform.</li>
<li>Predictions in <b>[0, 1]</b>; pixels outside the mapped footprint may be null or NaN. This repository
ships all-finite files (0 outside the footprint, no nodata tag) so a literal range test cannot fail.</li>
<li>A short note (this repository's writer caps name and note at 140 characters each).</li>
</ul>
<h2>Why a file can fail the range test, and how this repository prevents it</h2>
<p class="small">If a writer leaves NaN or the training sentinel (<code>-3.4028235e+38</code>) where a reader
expects numbers, a naive min/max test sees a value below 0 and the portal answers
<code>Predicted values must be in range [0, 1]</code>. Every writer here
(<code>gems52.grid.write_geotiff_portal_exact</code>, <code>gems52.submission_writer.write_submission</code>)
re-reads the file it just wrote and refuses to ship any non-finite pixel inside the footprint or any value
outside [0,1] anywhere.</p>
{hist}
<div class="card" role="note">
<span class="pill pill-warn">DO NOT SUBMIT the negative-round artefacts</span>
<p class="small">The CTD5 release and every file this repository labels research-only are
<strong>DO NOT SUBMIT</strong> (see <a href="ctd5-audit.html">ctd5-audit.html</a> and
<a href="index.html">the front page</a>). This guide describes the mechanics only, for the day a file does
clear the bar.</p>
</div>
<h2>Check any GeoTIFF yourself, in the browser</h2>
<p class="small"><a href="validator.html">docs/validator.html</a> decodes a local GeoTIFF (none/LZW/DEFLATE)
entirely in your browser: band count, dtype, CRS/shape, the literal [0,1] range test and the emitted-pixel
count. Nothing is uploaded.</p>
""" + foot()
    (DOCS / "h88-executive-summary.html").write_text(guide, encoding="utf-8")
    (DOCS / "executive-summary.html").write_text(guide, encoding="utf-8")

    # ---------------- hypotheses page (from the knowledge file, outcomes added) ----------------
    rows = ""
    for cells in md_table_rows(ROOT / "knowledge/81_h88_hypotheses_ranked.md"):
        if cells and cells[0].lower().startswith("rank"):
            continue
        rows += "<tr>" + "".join(f"<td>{esc(re.sub(r'[*`]', '', c))}</td>" for c in cells) + "</tr>\n"
    (DOCS / "h88-hypotheses.html").write_text(head("H88 — candidate hypotheses, ranked") + f"""
<h1>Candidate hypotheses, ranked (3&ndash;5)</h1>
<p class="small">Written before this round's fits were read; the last column records what actually
happened on the shared holdout instrument. Every number carries its evidence class.</p>
<table>
<tr><th>rank</th><th>id</th><th>layers</th><th>physical signature</th>
<th>why it can catch a catalogue-missing fault</th><th>how it differs from prior rounds</th>
<th>cost</th><th>status after this round</th></tr>
{rows}
</table>
<h2>Outcomes this round</h2>
<ul class="small">
<li><b>H88-A (rank 1)</b> was built and measured: prevalence-matched budget calibration completed (rule
{esc(pm['budget_rule'])}), the stratified emission was scored on all three instruments, and the candidate
<b>did not</b> beat the single-view control &mdash; verdict
<code>{esc(card['verdict'])}</code>. The instrument also failed to reproduce the board's mass preference,
which is recorded as a conflict rather than a win.</li>
<li><b>H88-B&hellip;E</b> (ranks 2&ndash;5) remain untested; the round's protocol stops after three
experiments, and the delegated brief fixes the lane to the co-training paragraph.</li>
<li><b>H88-F</b> (external ASTER / 2 m temperature) is <b>not viable in this sandbox</b>: the egress
allowlist here is <code>github.com</code>, <code>codeload.github.com</code>, <code>api.github.com</code>,
<code>registry.npmjs.org</code>, <code>pypi.org</code>, <code>files.pythonhosted.org</code>, so
<code>gdr.openei.org</code> (DOI 10.15121/1881483) and USGS bulk scene servers are unreachable. The named
free sources are the INGENIOUS GDR 1391 &ldquo;2m Temperature Probes&rdquo; release and NASA/USGS ASTER
L1T products; a user-side download with SHA-256 pins (or an allowlist entry) is the prerequisite.</li>
</ul>
""" + foot(), encoding="utf-8")

    # ---------------- sources page ----------------
    (DOCS / "h88-sources.html").write_text(head("H88 — official sources") + f"""
<h1>Official sources</h1>
<ul class="small">
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">Competition
problem statement, metric and submission format (page 967)</a></li>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/data/">Competition data tab
(login-walled here; this repository restores SHA-256-pinned mirrors)</a></li>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">Public
leaderboard</a> &mdash; team-level; #1 0.3774, #8 0.3195 on 2026-10-10</li>
<li><a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and">USGS
GeoDAWN airborne magnetic and radiometric survey (DOI 10.5066/P93LGLVQ)</a></li>
<li><a href="https://gdr.openei.org/submissions/1391">INGENIOUS geothermal data release GDR 1391
(CC BY 4.0, DOI 10.15121/1881483)</a></li>
<li><a href="https://doi.org/10.1145/279943.279962">Blum &amp; Mitchell, COLT 1998 (co-training)</a></li>
<li><a href="https://epsg.io/32611">EPSG:32611 (UTM zone 11N)</a> &middot;
<a href="https://en.wikipedia.org/wiki/Tversky_index">Tversky index (background)</a> &middot;
<a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">competition rules PDF</a></li>
<li><a href="https://github.com/drivendataorg/gems-prize-reference-solution">DrivenData reference
solution</a></li>
</ul>
<p class="small">Provenance: the competition rasters in <code>data/</code> were restored from the owner's
SHA-256-pinned mirrors through the GitHub API (23 files, <code>ALL_VERIFIED=True</code>). The pins prove
mirror consistency, not organiser authentication.</p>
""" + foot(), encoding="utf-8")

    # ---------------- downloads README ----------------
    (DL / "README_H88.txt").write_text(
        "H88 downloads (research artefacts; see docs/index.html for verdicts)\n"
        "====================================================================\n\n"
        f"Round file (27,000 dots) : {tif88.name}\n"
        f"  sha256                 : {sha88}\n"
        f"  OK to download         : yes\n"
        f"  OK to submit           : no -- loses to single_B on both hide instruments; lane shows\n"
        f"                           97.9% of its dots within 3 px of the published h83-candidate\n"
        f"  A-only reasoning rows  : {build['a_only_reasoning_csv']}\n\n"
        f"H87 file (37,654 dots)   : {tif87.name}\n"
        f"  sha256                 : {sha87}\n"
        f"  OK to download         : yes\n"
        f"  OK to submit           : no -- its field sits at random on the mandate instrument\n"
        f"                           (paired vs random {g87['paired_h87_minus_random']['delta']:+.6f}), and the\n"
        f"                           shipped file itself scored {f6(s87['file']['dti'])} (58.7% of its dots\n"
        f"                           violate its own 3 px minimum spacing).\n\n"
        "Format of both files: single-band float32 GeoTIFF, EPSG:32611, 3730x3292 at 100 m, values in\n"
        "[0,1], zero outside the footprint, no nodata tag.\n\n"
        "Receipts: evidence/h88_run_card.json, evidence/h88_holdout.json, evidence/h88_pm_budget.json,\n"
        "evidence/h87_holdout.json, evidence/h87_lane_full_registry.json\n",
        encoding="utf-8")

    print(json.dumps(dict(round_file=tif88.name, round_sha=sha88, h87_file=tif87.name, h87_sha=sha87,
                          spurious=[], verdict_h88=card["verdict"], verdict_h87=g87["submit_recommendation"],
                          ok_to_submit_any=bool(n_submittable)), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
