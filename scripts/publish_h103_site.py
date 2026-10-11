#!/usr/bin/env python3
"""Publish round H103 to the site and README: idempotent, receipt-driven, never a rewrite.

Rules (AGENTS.md):
* Every number is read from ``evidence/h103_*.json``; nothing is typed by hand.
* Shared pages (``docs/index.html``, ``docs/executive-summary.html``, root ``index.html``) get a delimited
  ``<!--H103-CARD-->`` block at the top of ``<body>``; re-running replaces only that block.
* ``README.md`` and ``AGENTS.md`` get delimited ``<!--H103-README-->`` / ``<!--H103-AGENTS-->`` blocks at the top.
* The verdict is the first thing a reader sees: OK TO DOWNLOAD and OK TO SUBMIT, separately.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS, EVID = ROOT / "docs", ROOT / "evidence"
DL = DOCS / "downloads"
CARD = json.loads((EVID / "h103_run_card.json").read_text())
WR = json.loads((EVID / "h103_write.json").read_text())
DG = json.loads((EVID / "h103_posthoc_diagnostic.json").read_text())
HO = json.loads((EVID / "h103_holdout.json").read_text())
LN = json.loads((EVID / "h103_lane.json").read_text())
CC = json.loads((EVID / "h103_lane_chance_control.json").read_text())
esc = lambda x: html.escape(str(x))  # noqa: E731
SUBMIT_OK = bool(CARD["submit_ok"])
DOWNLOAD_OK = bool(CARD["download_ok"])
TIF = Path(WR["file"])
ZIP = Path(WR["zip"])
REASON = Path(WR["a_only_reasoning"]["path"])
SHA = CARD["raster"]["sha256"]
NAME, NOTE = CARD["submission_name"], CARD["submission_note"]
GR = CARD["holdout"]["graft_primary"]
BAR = CARD["holdout"]["bar"]
CI = CARD["holdout"]["paired_graft_minus_B_DVA2_HVA"]


def f6(x):
    return f"{float(x):.6f}"


def ci(v):
    return f"[{float(v[0]):.6f}, {float(v[1]):.6f}]"


def verdict_html():
    dl = ("<b>OK TO DOWNLOAD: YES</b> — format-valid for the portal (single-band float32, EPSG:32611, values exactly "
          "{0,1}, no NaN). Download is for audit and for the format check only." if DOWNLOAD_OK
          else "<b>OK TO DOWNLOAD: NO</b> — the format validator failed; see the run card.")
    sb = ("<b>OK TO SUBMIT: YES — the selector step may consider this file.</b>" if SUBMIT_OK
          else "<b>OK TO SUBMIT: NO — research-only, do not upload.</b>")
    fails = [k for k, v in CARD["checks"].items() if not v]
    why = (f"HOLDOUT-DTI {f6(GR['dti'])} {ci(GR['ci95'])} against the promotable bar {f6(BAR)} (H84). "
           f"Paired graft minus B_DVA2_HVA {f6(CI['delta'])} {ci(CI['ci95'])}. Failed gates: "
           f"{', '.join(fails) if fails else 'none'}.")
    return (f"<div class=\"h103v\"><p>{dl}</p><p>{sb} {esc(why)} No weekly slot is approved; "
            f"slots used: {CARD['slots_used']}; experiments used: {CARD['experiments_used']} of 3.</p></div>")


def buttons(prefix=""):
    return (f"<p><a href=\"{prefix}downloads/{TIF.name}\" download>Download the H103 GeoTIFF</a> · "
            f"<a href=\"{prefix}downloads/{ZIP.name}\" download>ZIP</a> · "
            f"<a href=\"{prefix}downloads/{REASON.name}\" download>A-only reasoning CSV</a> · "
            f"<a href=\"{prefix}h103.html\">full result</a> · "
            f"<a href=\"https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/evidence/h103_run_card.json\">run card (JSON)</a></p>")


def identity():
    return (f"<p><b>Submission name</b> <code>{esc(NAME)}</code><br><b>Note ({len(NOTE)}/140 chars)</b> "
            f"<code>{esc(NOTE)}</code><br><b>File</b> <code>{esc(TIF.name)}</code> · SHA-256 <code>{esc(SHA)}</code></p>")


def holdout_table():
    rows = []
    for a in ("B_DVA2_HVA", "single_A", "graft_primary", "consensus_only", "random"):
        s = HO["pooled"]["scores"][a]
        rows.append(f"<tr><td><code>{a}</code></td><td>{f6(s['dti'])}</td><td>{ci(s['ci95'])}</td></tr>")
    return ("<table><tr><th>arm (HOLDOUT-DTI, gems52-pooled-hide-v1, "
            f"{CARD['holdout']['withheld_positive_px']:,} withheld positive px)</th><th>DTI</th><th>95 % CI</th></tr>"
            + "".join(rows) + "</table>")


def diagnostic_table():
    rows = []
    for a in ("B_DVA2_HVA", "graft_primary", "graft_no_veto", "veto_only"):
        s = DG["pooled"][a]
        rows.append(f"<tr><td><code>{a}</code></td><td>{f6(s['dti'])}</td><td>{ci(s['ci95'])}</td></tr>")
    return ("<table><tr><th>post-hoc diagnostic arm (not preregistered; not promotable)</th><th>DTI</th>"
            "<th>95 % CI</th></tr>" + "".join(rows) + "</table>")


def card_html(prefix):
    return ("<style>.h103card{border:2px solid #7b1fa2;border-radius:12px;padding:16px 18px;margin:16px 0;"
            "background:#faf5fc;color:#14181d;font:15px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,"
            "Helvetica,Arial,sans-serif}.h103card h2{margin:0 0 8px;font-size:19px;color:#7b1fa2}"
            ".h103card a{color:#7b1fa2;font-weight:700}.h103card code{background:#f0e6f5;padding:1px 4px;"
            "border-radius:3px;font-size:12.5px;word-break:break-all}.h103v p{margin:4px 0}</style>"
            "<div class=\"h103card\"><h2>Latest round H103 — H96 disagreement formula grafted on the H84 surface learner</h2>"
            + verdict_html() + buttons(prefix) + identity()
            + f"<p><small>HOLDOUT-DTI graft {f6(GR['dti'])} vs bar {f6(BAR)}; a holdout number is not a board score.</small></p>"
            "</div>")


def insert_block(path: Path, marker: str, blob: str, *, top_of_body=True, after=None):
    text = path.read_text(encoding="utf-8") if path.exists() else "<!doctype html><html><body></body></html>"
    block = f"<!--{marker}-->\n{blob}\n<!--/{marker}-->\n"
    if f"<!--{marker}-->" in text:
        text = re.sub(f"<!--{marker}-->.*?<!--/{marker}-->\\n?", lambda m: block, text, flags=re.S)
    elif after and after in text:
        # the tests (tests/test_h95.py) require the H95 README block to remain the first block: insert after it
        i = text.index(after) + len(after)
        text = text[:i] + "\n" + block + text[i:]
    elif top_of_body and "<body" in text:
        i = text.find(">", text.find("<body")) + 1
        text = text[:i] + "\n" + block + text[i:]
    else:
        text = block + "\n" + text
    path.write_text(text, encoding="utf-8")


def readme_block():
    return (f"# Current status — H103 (2026-10-11): disagreement graft on the H84 surface learner · NEGATIVE\n\n"
            f"> **OK TO DOWNLOAD: {'YES' if DOWNLOAD_OK else 'NO'}** — format check only. "
            f"**OK TO SUBMIT: {'YES' if SUBMIT_OK else 'NO — research-only, do not upload'}.**\n>\n"
            f"> HOLDOUT-DTI graft {f6(GR['dti'])} {ci(GR['ci95'])} vs promotable bar {f6(BAR)} (H84 `B_DVA2_HVA`). "
            f"Paired graft − B_DVA2_HVA {f6(CI['delta'])} {ci(CI['ci95'])}. Weekly slots used: {CARD['slots_used']}.\n\n"
            f"- **File:** `{TIF}` · SHA-256 `{SHA}`\n"
            f"- **Name:** `{NAME}` · **Note ({len(NOTE)}/140):** `{NOTE}`\n"
            f"- **Why negative:** the holdout fails the bar; the placed dots fall in A-confident / B-abstaining cells. "
            f"The dot lane is a literal DUPLICATE/STOP: the literal 3 px share {f6(LN['full_dots']['literal']['max_near_3px_fraction'])} "
            f"comes from universal-coverage probes; the policy share on an informative (non-probe) raster is "
            f"{f6(LN['full_dots']['policy']['max_near_3px_fraction'])}, and a random set of the same size scores "
            f"{f6(CC['result']['random_same_count']['max_near_3px_fraction'])} there (IR-H103-006). "
            f"On the holdout the A-only arm `single_A` scores {f6(HO['pooled']['scores']['single_A']['dti'])} "
            f"against {f6(HO['pooled']['scores']['random']['dti'])} for random dots (`evidence/h103_holdout.json`); "
            f"decomposition: [`evidence/h103_posthoc_diagnostic.json`](evidence/h103_posthoc_diagnostic.json). "
            f"Full result: [`docs/h103.html`](docs/h103.html) · run card: [`evidence/h103_run_card.json`](evidence/h103_run_card.json) · "
            f"preregistration: [`knowledge/97`](knowledge/108_hypotheses_H97_preregistered.md).\n\n---\n")


def agents_block():
    return ("## Current H103 continuation (2026-10-11) — READ FIRST\n"
            f"Verdict **NEGATIVE** (download {'yes' if DOWNLOAD_OK else 'no'}, submit NO). Experiments {CARD['experiments_used']} of 3, slots 0.\n"
            "- The H96 disagreement formula grafted on the H84 `B_DVA2_HVA` learner (preregistered, `registry/h103_preregistration.json`) "
            f"scored HOLDOUT-DTI {f6(GR['dti'])}, far below the H84 control {f6(BAR)}. Do not re-run this graft with changed weights; "
            "it is measured.\n"
            f"- The A-only term (`a·(a−b)`) puts the whole budget on A-confident/B-abstaining cells; the A-only arm scores {f6(HO['pooled']['scores']['single_A']['dti'])} vs random {f6(HO['pooled']['scores']['random']['dti'])}. "
            "The veto is not the main cause (diagnostic `graft_no_veto`).\n"
            "- `scripts/fetch_prior_inventory.py` now falls back to `codeload.github.com` with git-blob-SHA-1 verification when the Git Data API "
            "rate-limits (IR-H103-003). Its receipt records the source of every blob.\n"
            "- The H84 receipt `B_DVA2` control fails its own tolerance (IR-H103-001); the H103 control `B_DVA2_HVA` reproduces.\n")


def main():
    DL.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / TIF, DL / TIF.name)
    with zipfile.ZipFile(DL / ZIP.name, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(ROOT / TIF, arcname=TIF.name)
    if (ROOT / REASON).resolve() != (DL / REASON.name).resolve():  # the write stage already writes it to docs/downloads
        shutil.copy(ROOT / REASON, DL / REASON.name)

    body = ("<h1>H103 — H96 disagreement formula grafted on the H84 surface learner</h1>"
            f"<p class=\"muted\">preregistration <code>knowledge/97</code> (SHA-256 "
            f"<code>{esc(CARD['preregistration']['document_sha256'][:24])}</code>, frozen before the graft was scored) · "
            f"experiments {CARD['experiments_used']} of 3 (experiment 2 is a labelled post-hoc diagnostic)</p>"
            + verdict_html() + buttons() + identity() + "<h2>HOLDOUT-DTI (pre-registered arms)</h2>" + holdout_table()
            + "<h2>Post-hoc decomposition (diagnostic)</h2>" + diagnostic_table()
            + "<h2>Pre-registered checks</h2><table><tr><th>check</th><th>result</th></tr>"
            + "".join(f"<tr><td>{esc(k)}</td><td>{'PASS' if v else 'FAIL'}</td></tr>" for k, v in CARD["checks"].items())
            + "</table>"
            + "<h2>Hypothesis, mechanism, named mimic</h2>"
            f"<p><b>Hypothesis.</b> {esc(CARD['hypothesis'])}</p><p><b>Mechanism.</b> {esc(CARD['mechanism'])}</p>"
            f"<p><b>Named non-fault mimic.</b> {esc(CARD['named_non_fault_mimic'])}</p>"
            "<h2>Sources (official, for manual review)</h2><ul>"
            "<li><a href=\"https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/\">DrivenData problem "
            "description: distance-weighted Tversky index, alpha 0.2, beta 0.8, triangular kernel 300 m, float32 in [0,1]</a></li>"
            "<li><a href=\"https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/\">DrivenData leaderboard</a></li>"
            "<li><a href=\"https://doi.org/10.1145/279943.279962\">Blum &amp; Mitchell, COLT 1998 (co-training)</a></li>"
            "<li><a href=\"https://epsg.io/32611\">EPSG:32611</a></li></ul>")
    page = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>H103 — GEMSDOE52</title>"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<style>body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:920px;margin:0 auto;padding:20px;"
            "line-height:1.55;color:#14181d}table{border-collapse:collapse;width:100%;margin:8px 0}th,td{border-bottom:1px solid #ddd;"
            "padding:6px 8px;text-align:left}code{background:#f0f0f0;padding:1px 4px;border-radius:3px;word-break:break-all}"
            "a{color:#1f4e79}.muted{color:#666}</style></head><body>"
            + body + "</body></html>")
    (DOCS / "h103.html").write_text(page, encoding="utf-8")

    insert_block(DOCS / "index.html", "H103-CARD", card_html(""))
    insert_block(DOCS / "executive-summary.html", "H103-CARD", card_html(""))
    insert_block(ROOT / "index.html", "H103-CARD", card_html("docs/"))
    insert_block(ROOT / "README.md", "H103-README", readme_block(), top_of_body=False, after="<!--/H95-README-->")
    insert_block(ROOT / "AGENTS.md", "H103-AGENTS", agents_block(), top_of_body=False)
    print("published", TIF.name, "verdict", CARD["verdict"], "download", DOWNLOAD_OK, "submit", SUBMIT_OK)


if __name__ == "__main__":
    main()
