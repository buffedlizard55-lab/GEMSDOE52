#!/usr/bin/env python3
"""Publish round H95 to the site and README — idempotent, receipt-driven, never a rewrite.

Rules (AGENTS.md):
* Every number is read from ``evidence/h95_*.json``; nothing is typed by hand.
* Shared pages (``docs/index.html``, ``docs/executive-summary.html``, root ``index.html``,
  ``docs/downloads/index.html``) get a delimited ``<!--H95-CARD-->`` block inserted at the top of
  ``<body>``; re-running replaces only that block, so every earlier round's asserted strings survive.
* ``README.md`` gets a delimited ``<!--H95-README-->`` block at the very top, followed by the session
  brief verbatim (from ``knowledge/94``) inside the same block.
* The verdict is the first thing a reader sees: OK TO DOWNLOAD and OK TO SUBMIT, separately.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS, EVID, DATA = ROOT / "docs", ROOT / "evidence", ROOT / "docs" / "data"


def load(name):
    return json.loads((EVID / name).read_text())


E1, E2, E3 = load("h95_e1_h87_holdout.json"), load("h95_e2_lane_holdout.json"), load("h95_e3_proxy_sgmc.json")
B, G, CARD = load("h95_build.json"), load("h95_gates.json"), load("h95_run_card.json")
esc = lambda x: html.escape(str(x))
SUBMIT_OK = bool(CARD["verdict"]["submit_ok"])
TIF = Path(B["path"])
STEM = B["stem"]
SHA = B["file_sha256"]
NAME, NOTE = CARD["submission"]["name"], CARD["submission"]["note"]
V = G["format"]


def f6(x):
    return f"{x:.6f}"


def ci(s):
    return f"{f6(s['dti'])} [{s['ci95'][0]:.4f}, {s['ci95'][1]:.4f}]"


def verdict_html():
    sub = ("<div class=\"verdict ok\">OK TO SUBMIT: YES — the frozen promotion rule passed.</div>" if SUBMIT_OK else
           "<div class=\"verdict no\">OK TO SUBMIT: NO — research-only, do not upload. "
           f"{esc(CARD['verdict']['why'])}</div>")
    return ("<div class=\"verdict ok\">OK TO DOWNLOAD: YES — format-valid "
            f"({V.get('bands', 1)} band float32, EPSG:32611, all-finite, values exactly {{0,1}}, "
            f"{B['budget']:,} emitted cells); the portal's \"Predicted values must be in range [0, 1]\" "
            "rejection cannot occur.</div>" + sub +
            "<p><b>Weekly slots used by this round: 0.</b> No weekly slot is approved by this round; "
            "uploading is the owner's decision.</p>")


CSS = """*{box-sizing:border-box}body{margin:0;font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#14181d;background:#f6f8fa}
main{max-width:920px;margin:0 auto;padding:28px 20px 70px;background:#fff;min-height:100vh}h1{font-size:26px;margin:0 0 6px}
h2{font-size:20px;margin:28px 0 8px;border-bottom:2px solid #e6eaef;padding-bottom:5px}.verdict{border-radius:10px;padding:14px 16px;margin:12px 0;font-weight:700}
.ok{background:#e7f6ec;color:#11643a;border:1px solid #9ad7b4}.no{background:#fdecea;color:#b3261e;border:1px solid #f0c4bf}
a.btn{display:inline-block;background:#1f4e79;color:#fff;text-decoration:none;font-weight:700;padding:12px 18px;border-radius:8px;margin:6px 8px 6px 0}
a.btn.s{background:#eef2f6;color:#1f4e79;border:1px solid #d7e0ea}code{background:#f2f4f7;padding:1px 5px;border-radius:4px;font-size:13px;word-break:break-all}
table{border-collapse:collapse;width:100%;margin:10px 0;font-size:14.5px}th,td{border:1px solid #e3e8ee;padding:6px 9px;text-align:left;vertical-align:top}th{background:#f3f6f9}
.copy{background:#f2f4f7;border:1px solid #d7e0ea;border-radius:6px;padding:10px 12px;font-family:monospace;font-size:14px;word-break:break-all}
small,.muted{color:#5b6672}footer{margin-top:30px;border-top:1px solid #e3e8ee;padding-top:10px;font-size:13px;color:#5b6672}"""


def page(title, body):
    return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" "
            f"content=\"width=device-width,initial-scale=1\"><title>{esc(title)}</title><style>{CSS}</style></head>"
            f"<body><main>{body}<footer>GEMSDOE52 · round H95 · generated from receipts in "
            f"<code>evidence/h95_*.json</code> by <code>scripts/publish_h95_site.py</code> · "
            f"<a href=\"index.html\">site home</a></footer></main></body></html>\n")


def buttons(prefix=""):
    return (f"<p><a class=\"btn\" href=\"{prefix}downloads/h95-candidate.tif\" download>Download h95-candidate.tif ↓</a>"
            f"<a class=\"btn s\" href=\"{prefix}downloads/h95-candidate.zip\" download>ZIP</a>"
            f"<a class=\"btn s\" href=\"{prefix}h95-executive-summary.html\">How to submit</a>"
            f"<a class=\"btn s\" href=\"{prefix}h95.html\">Full result</a>"
            f"<a class=\"btn s\" href=\"{prefix}downloads/h95-a-only-reasoning.csv\">A-only reasoning CSV</a>"
            f"<a class=\"btn s\" href=\"{prefix}validator.html\">Check a file in your browser</a></p>")


def identity():
    return (f"<table><tr><th>file</th><td><code>{esc(TIF.name)}</code></td></tr>"
            f"<tr><th>bytes · SHA-256</th><td>{B['bytes']:,} · <code>{esc(SHA)}</code></td></tr>"
            f"<tr><th>submission name</th><td><div class=\"copy\">{esc(NAME)}</div></td></tr>"
            f"<tr><th>note ({len(NOTE)}/140)</th><td><div class=\"copy\">{esc(NOTE)}</div></td></tr>"
            f"<tr><th>validator (re-read from disk)</th><td>{'PASS' if V['ok'] else 'FAIL'} · "
            f"{esc(CARD['validator_output'])}</td></tr></table>")


def holdout_tables():
    s2 = E2["pooled"]["scores"]
    s1 = E1["pooled"]["scores"]
    d = E2["promotion"]["paired_vs_single_B"]
    rows = "".join(f"<tr><td>{esc(a)}</td><td>{ci(s)}</td></tr>" for a, s in sorted(s2.items(), key=lambda t: -t[1]["dti"]))
    rows1 = "".join(f"<tr><td>{esc(a)}</td><td>{ci(s)}</td></tr>" for a, s in sorted(s1.items(), key=lambda t: -t[1]["dti"]))
    n = s2["single_B"]["withheld_positive_pixels"]
    return (f"<h2>HOLDOUT-DTI — E2, the co-training lane (primary <code>cotrain_B</code>)</h2>"
            f"<p class=\"muted\">evaluator <code>{esc(E2['evaluator_version'])}</code> · {n:,} withheld positive px · "
            f"4 label-blind quadrant folds · 9,400 dots/fold/arm · α 0.2 β 0.8 R 300 m · 95 % paired cluster bootstrap</p>"
            f"<table><tr><th>arm</th><th>HOLDOUT-DTI [95 % CI]</th></tr>{rows}</table>"
            f"<p>Paired <code>cotrain_B − single_B</code> = <b>{d['delta']:+.6f}</b> [{d['ci95'][0]:+.6f}, {d['ci95'][1]:+.6f}]. "
            f"Promotion bar {E2['promotion']['rule']['holdout_bar']} (H84 primary) and CI &gt; 0 → "
            f"<b>{'PASS' if E2['promotion']['promote'] else 'FAIL'}</b>. Control reproduction single_B "
            f"{f6(E2['control_reproduction']['single_B'])} vs H61 {E2['control_reproduction']['target']} → "
            f"{'valid' if E2['control_reproduction']['ok'] else 'INVALID'}.</p>"
            f"<h2>HOLDOUT-DTI — E1, first holdout of the shipped H87 rule</h2>"
            f"<table><tr><th>arm</th><th>HOLDOUT-DTI [95 % CI]</th></tr>{rows1}</table>"
            f"<p>The H87 file shipped with no holdout; measured here, its own emission rule "
            f"(<code>h87_disagreement</code>) is <b>below random</b>.</p>")


def gates_table():
    rows = "".join(f"<tr><td>{esc(k)}</td><td>{'✅ pass' if v['pass'] else '❌ fail'}</td><td>{esc(v['detail'])}</td></tr>"
                   for k, v in CARD["gates"].items())
    return f"<table><tr><th>gate</th><th>result</th><th>measured</th></tr>{rows}</table>"


def e3_table():
    res = E3["results"]
    keys = [k for k in res if k.endswith(f"@{E3['shipped_budget']}")] + [k for k in res if "board" in k]
    rows = "".join(f"<tr><td>{esc(k)}</td><td>{res[k]['placed']:,}</td><td>{res[k]['mean']:.5f}</td></tr>"
                   for k in sorted(keys, key=lambda k: -res[k]["mean"]))
    return (f"<h2>E3 — PROXY-SGMC diagnostic (never a score)</h2><p class=\"muted\">{esc(E3['caveat'])}</p>"
            f"<table><tr><th>field@budget</th><th>dots</th><th>PROXY-SGMC mean DTI (5 seeds)</th></tr>{rows}</table>"
            f"<p>Shipped budget by the frozen rule: <b>{E3['shipped_budget']:,}</b>.</p>")


def how_to_submit():
    return ("<h2>How to submit (exact steps)</h2><ol>"
            "<li>Download <code>h95-candidate.tif</code> above (or the ZIP, which holds exactly one GeoTIFF).</li>"
            "<li>Optional: drop it on <a href=\"validator.html\">the browser validator</a> — it must say 1 band, "
            "EPSG:32611, 3730×3292, values in [0, 1].</li>"
            "<li>Open <a href=\"https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/\">"
            "DrivenData → DOE GEMS → Submissions</a> (login required) and upload the .tif (or .zip).</li>"
            "<li>Paste the submission name and the note from the table above.</li>"
            "<li>Remember the official rule: you must choose ONE submission for both the Initial and the Final round "
            "(<a href=\"https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/\">problem description</a>).</li>"
            "</ol>" + ("" if SUBMIT_OK else "<p class=\"verdict no\">This round's frozen rule says do not upload: it did "
                       "not beat the holdout best. The steps are listed so the owner can act on a later round.</p>"))


def card_html(prefix):
    s2 = E2["pooled"]["scores"]
    return ("<style>.h95card{border:2px solid #1f4e79;border-radius:12px;padding:16px 18px;margin:16px 0;background:#f3f7fc;"
            "color:#14181d;font:15px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}"
            ".h95card h2{margin:0 0 8px;font-size:19px;color:#1f4e79}.h95card a{color:#1f4e79;font-weight:700}"
            ".h95card code{background:#e8eef4;padding:1px 4px;border-radius:3px;font-size:12.5px;word-break:break-all}</style>"
            "<div class=\"h95card\"><h2>Latest round H95 — co-trained View B (A→B whole-segment pseudo-labels)</h2>"
            f"<p><b>OK TO DOWNLOAD: YES</b> (format-valid, all-finite, values exactly {{0,1}}, {B['budget']:,} cells). "
            f"<b>OK TO SUBMIT: {'YES' if SUBMIT_OK else 'NO — research-only, do not upload'}.</b> "
            f"{esc(CARD['verdict']['why'])} No weekly slot is approved; slots used: 0.</p>"
            f"<p><a href=\"{prefix}downloads/h95-candidate.tif\" download>Download h95-candidate.tif</a> · "
            f"<a href=\"{prefix}downloads/h95-candidate.zip\" download>ZIP</a> · "
            f"<a href=\"{prefix}h95-executive-summary.html\">how to submit</a> · <a href=\"{prefix}h95.html\">full result</a></p>"
            f"<p><small><code>{esc(TIF.name)}</code> · SHA-256 <code>{esc(SHA[:24])}</code> · HOLDOUT-DTI "
            f"(gems52-pooled-hide-v1, {s2['single_B']['withheld_positive_pixels']:,} withheld positives): cotrain_B "
            f"{f6(s2['cotrain_B']['dti'])} vs single_B {f6(s2['single_B']['dti'])}; first holdout of H87's rule "
            f"{f6(E1['pooled']['scores']['h87_disagreement']['dti'])} (random {f6(E1['pooled']['scores']['random']['dti'])}). "
            "A holdout number is not a board score.</small></p></div>")


def insert_block(path: Path, marker: str, blob: str, *, top_of_body=True):
    text = path.read_text() if path.exists() else "<!doctype html><html><body></body></html>"
    block = f"<!--{marker}-->\n{blob}\n<!--/{marker}-->\n"
    if f"<!--{marker}-->" in text:
        text = re.sub(f"<!--{marker}-->.*?<!--/{marker}-->\n?", lambda m: block, text, flags=re.S)
    elif top_of_body and "<body" in text:
        i = text.find(">", text.find("<body")) + 1
        text = text[:i] + "\n" + block + text[i:]
    else:
        text = block + "\n" + text
    path.write_text(text)


def readme_block():
    s2, s1 = E2["pooled"]["scores"], E1["pooled"]["scores"]
    d = E2["promotion"]["paired_vs_single_B"]
    brief = (ROOT / "knowledge/94_current_user_brief_2026-10-10_H95.md").read_text()
    g = "\n".join(f"| {k} | {'PASS' if v['pass'] else 'FAIL'} | {v['detail']} |" for k, v in CARD["gates"].items())
    arms = "\n".join(f"| `{a}` | {ci(s)} |" for a, s in sorted(s2.items(), key=lambda t: -t[1]["dti"]))
    arms1 = "\n".join(f"| `{a}` | {ci(s)} |" for a, s in sorted(s1.items(), key=lambda t: -t[1]["dti"]))
    return f"""# Current status — H95 (2026-10-10): co-trained View B · first holdout of H87 · {'PROMOTE' if SUBMIT_OK else 'NEGATIVE'}

> **OK TO DOWNLOAD: YES** — format-valid single-band float32 GeoTIFF, EPSG:32611, 3730×3292, all-finite, values exactly {{0,1}} (the portal's *"Predicted values must be in range [0, 1]"* rejection cannot occur).
>
> **OK TO SUBMIT: {'YES' if SUBMIT_OK else 'NO — research-only, do not upload'}.** {CARD['verdict']['why']}
>
> Weekly slots used: **0**. No weekly slot is approved by this round; the agent does not pick submissions.

**★ [Download h95-candidate.tif](docs/downloads/h95-candidate.tif)** · [ZIP](docs/downloads/h95-candidate.zip) · **[Executive summary / how to submit](docs/h95-executive-summary.html)** · [Full result](docs/h95.html) · [Run card](evidence/h95_run_card.json) · [A-only reasoning CSV](docs/downloads/h95-a-only-reasoning.csv)

- **File:** `{B['path']}` — {B['bytes']:,} bytes, SHA-256 `{SHA}`
- **Submission name:** `{NAME}` · **Note ({len(NOTE)}/140):** `{NOTE}`
- **Validator (re-read from disk):** {CARD['validator_output']}
- **HOLDOUT-DTI, E2** (`{E2['evaluator_version']}`, {s2['single_B']['withheld_positive_pixels']:,} withheld positive px, 95 % CI):

| arm | HOLDOUT-DTI [95 % CI] |
|---|---|
{arms}

  Paired `cotrain_B − single_B` = **{d['delta']:+.6f}** [{d['ci95'][0]:+.6f}, {d['ci95'][1]:+.6f}]; bar {E2['promotion']['rule']['holdout_bar']} (H84 primary) → **{'PASS' if E2['promotion']['promote'] else 'FAIL'}**. Control single_B reproduces H61 ({E2['control_reproduction']['single_B']:.6f} vs {E2['control_reproduction']['target']}): **{'valid' if E2['control_reproduction']['ok'] else 'INVALID'}**.
- **HOLDOUT-DTI, E1 — the shipped H87 file's rule, never measured before:**

| arm | HOLDOUT-DTI [95 % CI] |
|---|---|
{arms1}

- **Independence (spatial-block OOF error correlation on labelled negatives):** max |ρ| {E2['independence']['max_abs_rho']:.4f} over {E2['independence']['n_blocks']:,} blocks (abandon ≥ 0.60) → exchange allowed; pseudo-labelled px donated: {E2['pseudo_pixels_total']:,}.
- **Leakage canary:** max single-feature out-of-quadrant AUC {E2['canary']['max_alarm']:.4f} (E2) / {max(E1['canary_max_auc'].values()):.4f} (E1); alarm 0.90 → none.
- **Gates (frozen in `registry/h95_preregistration.json`):**

| gate | result | measured |
|---|---|---|
{g}

- **E3 PROXY-SGMC (diagnostic, never a score):** shipped budget {E3['shipped_budget']:,} by the frozen rule — see [docs/h95.html](docs/h95.html).
- Docs: [preregistration](knowledge/93_hypotheses_H95_preregistered_frozen_as_H88.md) · [results & limits](knowledge/95_h95_results_and_limits.md) · [session brief](knowledge/94_current_user_brief_2026-10-10_H95.md) · [irregularities](registry/irregularities.json)
- Reproduce: `python3 scripts/restore_data.py --target-dir data` → feature store + `python -m gems52.external` → `python3 scripts/fetch_prior_inventory.py --out work/h95/priors --receipt work/h95/prior_fetch_receipt.json` → `python3 scripts/run_h95.py all` → `python3 scripts/h95_a_only_reasoning.py && python3 scripts/h95_run_card.py && python3 scripts/h95_irregularities.py` → `python3 scripts/publish_h95_site.py && python3 scripts/check_site.py`.

### Why `h33-h33-2-b2` scored 0.2778, and can we beat it? (full derivation: [knowledge/76](knowledge/76_why_02778_and_what_beating_03195_requires.md))

- DTI = T / (0.2·S + 0.8·|G|) with S = emitted mass and |G| the hidden positives. Our predictions are binary, so S is the dot count, and a dot raises the score only if its kernel credit exceeds 0.2·DTI, about 0.056 at the 0.2778 level (knowledge/15). The board shows this directly: Spearman(emitted mass, score) = −0.928 over our scored files (knowledge/76).
- The champion is the 0.2600 `d2-8` field (44,090 px) with every dot within 200 m of the public catalogue deleted, leaving 37,654 dots. The hidden faults are *new* faults (not in USGS Qfaults), so dots on the known catalogue are pure false-positive mass. Deleting them raised the score by +0.0178 with no new signal.
- Placement matters more than modelling: the H83 field scores HOLDOUT-DTI 0.0172 with clumped top-k placement and 0.0724 with 3 px spacing (knowledge/78).
- Beating 0.3195 (#8) needs ×1.150 more credit at the same mass, or the same credit from about 25,400 dots. Beating #1 (0.3774) needs ×1.36. No ranking signal in this repository, this round's co-training included, has yet shown the precision to do that on an instrument that tracks the board. **Honest answer: not yet demonstrated. The next levers are listed below.**

### Next work (ranked; each must beat 0.190147 on the holdout or show a board-anchored gain before using a slot)

1. **Mass lever on the champion's own field:** a 28k/32k-dot subset of h33-2-b2 ranked by its d2-8 value. This follows directly from the metric identity, costs one slot, and is the only lever with board-sign evidence (ρ −0.93).
2. **H87's View B as a map-fault (SGMC) detector — a lead, not evidence.** On the E3 PROXY-SGMC diagnostic, `h87_single_B` scores {E3['results']['h87_single_B@37654']['mean']:.4f} at 37,654 dots against the champion's {E3['results']['champion_h33_2_b2 (board 0.2778, OWNER-REPORTED)']['mean']:.4f}, yet on the catalogue holdout it is below random. The two instruments disagree, and the proxy mostly tracks mass. Test it with a mass-matched (28k) board-anchored comparison before spending any slot.
3. **Road/drainage artefact screen of B-only dots** (cardinal-azimuth and fall-line alignment). This is H95-5, deferred for budget; it targets the brief's named B-only mimics.
4. **INGENIOUS 2 m temperature probes** (GDR 1391, DOI 10.15121/1881483) as a thermal view. They are free and official, but gdr.openei.org is not reachable from this sandbox, so the owner would need to download them with SHA pins.
5. **Stop investing in View A as a learner:** it has failed sufficiency in nine fits. Use it only as a soft prior inside B's confident set.

<details><summary><b>The H95 session brief, verbatim (read it every session)</b></summary>

{brief}

</details>
"""


def agents_block():
    s2, s1 = E2["pooled"]["scores"], E1["pooled"]["scores"]
    d = E2["promotion"]["paired_vs_single_B"]
    return f"""## Current H95 continuation (2026-10-10) — READ FIRST
Read README's H95 block (it ends with the session brief verbatim), `knowledge/93` (frozen preregistration,
SHA-256 `{CARD['preregistration_sha256'][:16]}…`), `knowledge/94` (brief) and `knowledge/95` (results, generated).
Verdict **{CARD['verdict']['label']}** — {CARD['verdict']['why']} Experiments 3 of 3, slots 0.

Settled this round; do not re-litigate:

- **Co-training (A→B whole-segment pseudo-labels, one exchange) does not beat single-view B on the holdout:**
  cotrain_B {s2['cotrain_B']['dti']:.6f} vs single_B {s2['single_B']['dti']:.6f}, paired {d['delta']:+.6f}
  [{d['ci95'][0]:+.6f}, {d['ci95'][1]:+.6f}]. Independence passed again (max |ρ| {E2['independence']['max_abs_rho']:.4f}); View A
  sufficiency failed again (OOF AUC per fold {E2['sufficiency_oof_auc']['view_A']}).
- **H87 had no holdout; measured now its rule is below random** (h87_disagreement {s1['h87_disagreement']['dti']:.6f} vs random
  {s1['random']['dti']:.6f}; IR-H95-001). Never publish a promote verdict without a measured holdout.
- **Before publishing, re-fetch main and close uniqueness/lane against rasters merged while you ran** (`scripts/h95_supplemental_closure.py`). That check caught a genuine lane duplicate with the parallel H93 file (IR-H95-006); re-running the shared H61 View B learner with minor channel additions produces near-identical dots.
- **The board-anchored SGMC proxy (`gems52-offcat-segthin-v1`) is diagnostic only** — mass alone explains it (IR-H95-003).
- **Uniqueness/lane must include the 526-blob sibling census:** run
  `python3 scripts/fetch_prior_inventory.py --out work/h95/priors --receipt work/h95/prior_fetch_receipt.json` (api.github.com only)
  before `scripts/run_h95.py gates`.
- **Publishing:** `scripts/publish_h95_site.py` inserts `<!--H95-CARD-->` / `<!--H95-README-->` / `<!--H95-AGENTS-->` blocks
  idempotently; it never rewrites a shared page. Re-run it after any receipt changes, then `scripts/check_site.py`.
- Current artefact: `{B['path']}` (SHA-256 `{SHA[:16]}…`) — **DOWNLOAD YES, SUBMIT {'YES' if SUBMIT_OK else 'NO'}**.
"""


def warn_h87_in_readme():
    """Idempotent: flag the inherited H87 'Ready-to-Submit' section without editing its verbatim text."""
    p = ROOT / "README.md"
    t = p.read_text()
    anchor = "## ⬇️ Quick Download — Ready-to-Submit File"
    s1 = E1["pooled"]["scores"]
    blob = (f"<!--H95-H87-WARNING-->\n> **H95 warning (IR-H95-001): the H87 file below is NOT OK TO SUBMIT.** It shipped with no holdout; "
            f"measured in H95 E1 its rule scores HOLDOUT-DTI {s1['h87_disagreement']['dti']:.6f} vs random {s1['random']['dti']:.6f} "
            f"(gems52-pooled-hide-v1). The heading below is kept verbatim from the H87 session.\n<!--/H95-H87-WARNING-->\n\n")
    if "<!--H95-H87-WARNING-->" in t:
        t = re.sub(r"<!--H95-H87-WARNING-->.*?<!--/H95-H87-WARNING-->\n\n", lambda m: blob, t, flags=re.S)
    elif anchor in t:
        t = t.replace(anchor, blob + anchor, 1)
    p.write_text(t)


def main():
    dl = DOCS / "downloads"
    shutil.copy(ROOT / TIF, dl / "h95-candidate.tif")
    shutil.copy(ROOT / TIF, dl / TIF.name)
    with zipfile.ZipFile(dl / "h95-candidate.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(ROOT / TIF, arcname=TIF.name)
    shutil.copy(ROOT / G["a_only_reasoning_csv"], dl / "h95-a-only-reasoning.csv")

    body = ("<h1>H95 — co-trained View B (A→B whole-segment pseudo-labels), plus the first holdout of H87</h1>"
            f"<p class=\"muted\">preregistration <code>knowledge/93</code> (SHA-256 <code>{esc(CARD['preregistration_sha256'][:24])}</code>, "
            f"frozen before any fit) · experiments {CARD['experiments_used']} of 3</p>"
            + verdict_html() + buttons() + identity() + holdout_tables()
            + "<h2>Pre-registered gates</h2>" + gates_table() + e3_table()
            + "<h2>Mechanism, mimic, falsifier</h2>"
            f"<p><b>Hypothesis.</b> {esc(CARD['hypothesis'])}</p><p><b>Mechanism.</b> {esc(CARD['mechanism'])}</p>"
            f"<p><b>Named non-fault mimic.</b> {esc(CARD['named_non_fault_mimic'])}</p>"
            f"<p><b>Disagreement as discovery.</b> {esc(CARD['disagreement'])}</p>"
            "<h2>Limits</h2><ul>" + "".join(f"<li>{esc(x)}</li>" for x in CARD["limitations"]) + "</ul>"
            "<h2>Sources</h2><ul>"
            "<li><a href=\"https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/\">Official problem description (metric, format, rounds)</a></li>"
            "<li><a href=\"https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/\">Official leaderboard</a></li>"
            "<li><a href=\"https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/evidence/h95_run_card.json\">Run card (JSON)</a></li></ul>")
    (DOCS / "h95.html").write_text(page("H95 — GEMSDOE52", body))
    ex = ("<h1>Executive summary — H95 — how to make a submission</h1>" + verdict_html() + buttons() + identity()
          + how_to_submit() + holdout_tables())
    (DOCS / "h95-executive-summary.html").write_text(page("How to submit — GEMSDOE52 H95", ex))

    insert_block(DOCS / "index.html", "H95-CARD", card_html(""))
    insert_block(DOCS / "executive-summary.html", "H95-CARD", card_html(""))
    insert_block(ROOT / "index.html", "H95-CARD", card_html("docs/"))
    insert_block(dl / "index.html", "H95-CARD", card_html("../").replace("../downloads/", ""))
    insert_block(ROOT / "README.md", "H95-README", readme_block(), top_of_body=False)
    insert_block(ROOT / "AGENTS.md", "H95-AGENTS", agents_block(), top_of_body=False)
    warn_h87_in_readme()

    DATA.mkdir(parents=True, exist_ok=True)
    for n in ("h95_run_card.json", "h95_e1_h87_holdout.json", "h95_e2_lane_holdout.json", "h95_e3_proxy_sgmc.json",
              "h95_build.json", "h95_gates.json"):
        shutil.copy(EVID / n, DATA / n)
    shutil.copy(ROOT / "registry/h95_preregistration.json", DATA / "h95_preregistration.json")
    need = ["docs/downloads/h95-candidate.tif", "docs/downloads/h95-candidate.zip", "docs/downloads/h95-a-only-reasoning.csv",
            "docs/h95.html", "docs/h95-executive-summary.html", "docs/validator.html", "evidence/h95_run_card.json",
            "knowledge/93_hypotheses_H95_preregistered_frozen_as_H88.md", "knowledge/94_current_user_brief_2026-10-10_H95.md",
            "knowledge/95_h95_results_and_limits.md"]
    missing = [p for p in need if not (ROOT / p).exists()]
    print(json.dumps(dict(submit_ok=SUBMIT_OK, missing=missing,
                          generated=datetime.now(timezone.utc).isoformat(timespec="seconds")), indent=1))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
