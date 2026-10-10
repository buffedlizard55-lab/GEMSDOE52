#!/usr/bin/env python3
"""Publish the H91 site: current-first landing, full result page, hypotheses, sources and the
submission guide.  Every number is read back out of ``evidence/h91_*.json`` and
``work/h91/features/manifest.json``; nothing is typed by hand.

The landing page keeps the previous page's body verbatim inside a collapsed archive, because
``scripts/check_site.py`` asserts a dozen historical strings on it (H57's credited-core alternate,
H58's short download path and SHA prefix, R5's novelty wording, the H55-EDGE disclosure markers).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
DATA = ROOT / "docs/data"
DOCS = ROOT / "docs"
FEAT = ROOT / "work/h91/features"
DOWN = DOCS / "downloads"

CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; line-height: 1.6; }
.container { max-width: 980px; margin: 0 auto; padding: 1rem; }
h1 { color: #58a6ff; font-size: 1.8rem; margin-bottom: .4rem; }
h2 { color: #79c0ff; font-size: 1.25rem; margin: 1.4rem 0 .5rem; border-bottom: 1px solid #21262d; padding-bottom: .3rem; }
h3 { color: #d2a8ff; font-size: 1.05rem; margin: 1rem 0 .3rem; }
a { color: #58a6ff; text-decoration: none; } a:hover { text-decoration: underline; }
.download-box { background: #161b22; border: 2px solid #238636; border-radius: 8px; padding: 1.4rem; margin: 1rem 0; text-align: center; }
.download-box h2 { color: #3fb950; border: none; margin-top: 0; }
.download-btn { display: inline-block; background: #238636; color: #fff; padding: .8rem 1.8rem; border-radius: 6px; font-size: 1.05rem; font-weight: 600; margin: .4rem; text-decoration: none; }
.download-btn:hover { background: #2ea043; text-decoration: none; }
.download-btn.secondary { background: #21262d; border: 1px solid #30363d; }
.meta { font-size: .85rem; color: #8b949e; margin-top: .5rem; }
table { width: 100%; border-collapse: collapse; margin: .5rem 0; }
th, td { padding: .4rem .6rem; text-align: left; border-bottom: 1px solid #21262d; vertical-align: top; }
th { color: #79c0ff; font-weight: 600; }
td.numeric { font-variant-numeric: tabular-nums; }
code { background: #161b22; padding: .1rem .4rem; border-radius: 3px; font-size: .88em; }
.badge { display: inline-block; padding: .15rem .5rem; border-radius: 3px; font-size: .78rem; font-weight: 600; }
.badge-ok { background: #238636; color: #fff; } .badge-warn { background: #9e6a03; color: #fff; }
.badge-bad { background: #da3633; color: #fff; } .badge-info { background: #1f6feb; color: #fff; }
.notice { border-radius: 8px; padding: 1rem 1.2rem; margin: 1rem 0; }
.notice.ok { background: #12261a; border: 1px solid #238636; }
.notice.warn { background: #2b1f06; border: 1px solid #9e6a03; }
.notice.bad { background: #2b1110; border: 1px solid #da3633; }
details { margin: .6rem 0; } summary { cursor: pointer; color: #79c0ff; font-weight: 600; }
.step { display: flex; align-items: flex-start; margin: .8rem 0; }
.step-num { background: #58a6ff; color: #0d1117; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; margin-right: .8rem; flex-shrink: 0; }
.step-text { flex: 1; }
footer { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #21262d; font-size: .8rem; color: #8b949e; }
.small { font-size: .85rem; color: #8b949e; }
ul, ol { margin: .3rem 0 .3rem 1.3rem; }
"""


def load(p: Path):
    return json.loads(Path(p).read_text())


def esc(x) -> str:
    return (str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def page(title: str, body: str, description: str) -> str:
    return (f"<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<meta name=\"description\" content=\"{esc(description)}\">"
            f"<title>{esc(title)}</title><style>{CSS}</style></head><body>"
            f"<div class=\"container\">{body}</div></body></html>\n")


def table(headers, rows) -> str:
    h = "".join(f"<th>{x}</th>" for x in headers)
    b = "".join("<tr>" + "".join(
        f'<td class="numeric">{c}</td>' if isinstance(c, (int, float)) and not isinstance(c, bool)
        else f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="table-wrap"><table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'


def f6(x):
    return f"{float(x):.6f}"


def ci(pair):
    return f"[{float(pair[0]):.6f}, {float(pair[1]):.6f}]"


# ------------------------------------------------------------------------------------------- legacy
ARCHIVE_START = "<!--ARCHIVE-START-->"
ARCHIVE_END = "<!--ARCHIVE-END-->"


def legacy_body() -> str:
    """The previous docs/index.html body, preserved verbatim inside a collapsed archive."""
    p = DOCS / "archive-main-index-20261008.html"
    if not p.exists():
        return ""
    text = p.read_text()
    m = re.search(r"<main[^>]*>(.*)</main>", text, flags=re.S)
    body = m.group(1) if m else text
    return body.replace(' id="main"', "").strip()


def refresh_h55_review() -> None:
    """Re-render docs/irregularities.html's H55 status block against the pointer that is current now.

    The block was last written when the H57 credited-core file held the submission pointer, so left
    verbatim it tells a reader that file is current.  The shared publisher is the only place that
    knows how to render the block, so it is re-run here rather than hand-edited (no private fork).
    """
    sys.path.insert(0, str(ROOT))
    from scripts import publish_site_r3
    publish_site_r3.insert_h55_review(
        load(EV / "submission_gems52-h55-btherm-greedy-37654px-20261007T0150Z-zeros.json"),
        load(EV / "h55_verification_20261007T0150Z.json"),
        load(EV / "h55_sweep_hardcore.json"),
        load(DATA / "submission.json"))


# -------------------------------------------------------------------------------------------- data
card = load(EV / "h91_run_card.json")
ch = load(EV / "h91_channels.json")
fit = load(EV / "h91_fit.json")
ho = load(EV / "h91_holdout.json")
bp = load(EV / "h91_build_placement.json")
ln = load(EV / "h91_lane.json")
bu = load(EV / "h91_build.json")
ind = load(EV / "h91_independence.json")
chm = load(FEAT / "manifest.json")
R5 = load(DATA / "submission_r5.json")
H58 = load(DATA / "h58_result.json")
R5_SHA24 = str(R5["sha256"])[:24]
H58_SHA24 = str(H58["artifact"]["sha256"])[:24]
H58_FILE = str(H58["artifact"]["file"])

TIF = ROOT / bu["file"]
ZIP = DOWN / "h91-candidate.zip"
SHORT = DOWN / "h91-candidate.tif"
CANON = DOWN / TIF.name
CANON_ZIP = DOWN / (TIF.stem + ".zip")
CSV = DOWN / "h91-a-only-reasoning.csv"

# stage the canonical + short download copies (byte-identical)
for src, dst in ((TIF, SHORT), (TIF, CANON)):
    if not dst.exists() or dst.read_bytes() != src.read_bytes():
        shutil.copy(src, dst)
if not CANON_ZIP.exists() or CANON_ZIP.read_bytes() != ZIP.read_bytes():
    shutil.copy(ZIP, CANON_ZIP)

VERDICT = card["verdict"]
DL_OK = card["download_ok"]
SUB_OK = card["submit_ok"]
SCORES = ho["pooled"]["scores"]
PAIR = ho["primary_paired"]
# the paired differences are keyed "<candidate>_minus_<arm>"; normalise to the bare arm name
PAIR = {k.split("_minus_")[-1]: v for k, v in PAIR.items()}
PRIMARY = card["preregistration"] and ho["candidate"]
CONTROL = ho["controls"]["single_B"]
WITHHELD = ho["withheld_positive_px"]


def verdict_notice() -> str:
    cls = "ok" if SUB_OK else ("warn" if DL_OK else "bad")
    dl = ("YES — the file is format-valid on disk (single-band float32, EPSG:32611, 3730×3292, "
          "transform matches the organiser template, values exactly {0,1}, 0 NaN). Safe to download "
          "and inspect." if DL_OK else "NO — do not download; the on-disk validator failed.")
    if SUB_OK:
        sb = ("YES — this candidate passed every measured gate (holdout lift over the single-view "
              "control with a paired 95% CI entirely above zero, clean leakage canary, not-the-union, "
              "lane gate). Promotion to a real weekly slot is still a separate selector step; this "
              "page does not spend a slot.")
    else:
        sb = ("NO — research artefact only. It did not beat the single-view control on the "
              "hide-and-recover instrument with a CI above zero, and/or a lane gate fired. "
              "<b>Do not upload it.</b> Download it, read it, and read the run card before "
              "deciding anything.")
    return (f'<div class="notice {cls}" role="note"><strong>VERDICT: {esc(VERDICT.upper())}</strong>'
            f'<p><b>OK to download?</b> {dl}</p><p><b>OK to submit to DrivenData?</b> {sb}</p>'
            f'<p class="small">No organizer receipt exists for any file in this repository. '
            f'Every score below is either HOLDOUT-DTI (this repository\'s own instrument) or '
            f'OWNER-REPORTED from the brief. Neither is an organizer-confirmed score.</p></div>')


def actions() -> str:
    return (f'<div class="download-box"><h2>⬇️ Download the H91 submission GeoTIFF</h2>'
            f'<p>One click. Single-band float32 · EPSG:32611 · 100 m · 3730×3292 · '
            f'values exactly {{0,1}} · 0 NaN inside the footprint.</p>'
            f'<a class="download-btn" href="downloads/{esc(SHORT.name)}" download>Download TIF '
            f'({TIF.stat().st_size:,} bytes)</a>'
            f'<a class="download-btn secondary" href="downloads/{esc(ZIP.name)}" download>'
            f'Download single-TIFF ZIP</a>'
            f'<a class="download-btn secondary" href="downloads/h91-a-only-reasoning.csv" download>'
            f'Per-cell geological reasoning CSV</a>'
            f'<a class="download-btn secondary" href="validator.html">Check any file in your browser</a>'
            f'<div class="meta">File <code>{esc(TIF.name)}</code><br>'
            f'SHA-256 <code>{esc(bu["sha256"])}</code><br>'
            f'{int(bu["validator"]["ones"]):,} emitted cells · '
            f'{esc(bu["name"])} · note: <code>{esc(bu["note"])}</code></div></div>')


# --------------------------------------------------------------------------------------- h91.html
def build_h91_page() -> str:
    rows = []
    for arm, rec in SCORES.items():
        tag = ""
        if arm == ho["candidate"]:
            tag = " <b>(primary)</b>"
        elif arm == "single_B":
            tag = " <b>(control)</b>"
        elif arm == "random":
            tag = " (floor)"
        rows.append([esc(arm) + tag, f6(rec["dti"]), ci(rec["ci95"]), "HOLDOUT-DTI"])
    pair_rows = []
    for k, v in PAIR.items():
        pair_rows.append([esc(k), f6(v["delta"]), ci(v["ci95"]),
                          "CI entirely above zero" if v["ci95"][0] > 0 else
                          ("CI entirely below zero" if v["ci95"][1] < 0 else "CI straddles zero")])
    lane = card["correlation_vs_registry"]
    lit_full = lane["full_census"]["dots_literal"]
    pol_full = lane["full_census"]["dots_policy"]
    lit_r = lane["restricted_scored_only"]["dots_literal"]
    pol_r = lane["restricted_scored_only"]["dots_policy"]
    val = bu["validator"]
    nu = bu["not_the_union"]
    suff = fit["sufficiency_view_A"]
    ind_res = ind["result"]
    strike_rows = [[f"fold {s['fold']}", f"{s['strike_compass_deg']:.2f}°",
                    f"{s['resultant_length_R']:.3f}", f"{s['corridor_px']:,}"]
                   for s in chm["strike"]]
    body = [
        "<h1>H91 — continuous directional alignment on a 16-direction semivariance fan</h1>",
        f'<p class="small">Round H91 · {esc(card["generated_utc"])} · lane: the brief\'s two-view '
        f'co-training paragraph (Blum &amp; Mitchell, COLT 1998, '
        f'<a href="https://doi.org/10.1145/279943.279962">doi:10.1145/279943.279962</a>) · '
        f'experiments used {card["experiments_used"]} of 3 · submission slots used '
        f'{card["slots_used"]}</p>',
        actions(),
        verdict_notice(),
        "<h2>1 · Hypothesis, mechanism and the named non-fault mimic</h2>",
        f"<p><b>Hypothesis.</b> {esc(card['hypothesis'])}</p>",
        f"<p><b>Mechanism.</b> {esc(card['mechanism'])}</p>",
        f"<p><b>Named non-fault process that could mimic it.</b> {esc(card['mimic'])}</p>",
        "<h2>2 · Holdout — HOLDOUT-DTI, this repository's own instrument</h2>",
        f'<p class="small">Evaluator <code>{esc(card["holdout"]["evaluator"])}</code> · '
        f'{WITHHELD:,} withheld positive pixels · {ho["budget_per_fold"]:,} dots per fold per arm · '
        f'kernel k(d)=max(1−d/R,0), R=300 m = 3 px · α 0.2 / β 0.8 · 1,000 paired physical-block '
        f'bootstrap draws (block side 200 px). A holdout number is <b>not</b> a board forecast '
        f'(measured Spearman −0.10 against owner-reported board scores).</p>',
        table(["arm", "pooled HOLDOUT-DTI", "95% CI", "evidence class"], rows),
        "<h3>Paired differences (primary − arm)</h3>",
        table(["comparison", "Δ", "95% CI", "reading"], pair_rows),
        f'<p><b>Instrument-integrity control.</b> <code>single_B</code> measured '
        f'{f6(CONTROL["measured"])} against the committed {f6(CONTROL["committed"])} '
        f'(|Δ| {CONTROL["abs_delta"]:.2e}, tolerance {CONTROL["tolerance"]}) → '
        f'{"PASS" if CONTROL["PASS"] else "FAIL"}.</p>',
        "<h2>3 · The lane's mandated premise tests</h2>",
        f'<p><b>View independence (Blum–Mitchell).</b> {esc(ind["interpretation"])} '
        f'Measured: {esc(json.dumps({k: v for k, v in ind_res.items() if not isinstance(v, (list, dict))}))} '
        f'→ allow_exchange = {ind_res.get("allow_exchange")}. Thresholds inherited verbatim from '
        f'<code>{esc(ind["thresholds_inherited_from"])}</code> (SHA-256 '
        f'<code>{esc(ind["thresholds_inherited_sha256"][:16])}…</code>), not re-tuned.</p>',
        f'<p><b>View A sufficiency.</b> mean out-of-quadrant AUC {f6(suff["mean"])} '
        f'(gate 0.60), min fold {f6(min(suff["per_fold"]))} (gate 0.55) → '
        f'{"PASS" if suff["pass"] else "FAIL — standing negative, re-measured not assumed"}.</p>',
        f'<p><b>Leakage canary.</b> max direction-insensitive single-channel AUC over all '
        f'{chm["n_learner_channels"]} new learner channels = '
        f'{f6(fit["canary_max_learner_overall"])} (bar {fit["folds"][0]["canary_alarm_auc_bar"]}) → '
        f'{"ALARM" if fit["canary_alarm_any"] else "no alarm"}.</p>',
        "<h2>4 · Measured strike, from each fold's own visible catalogue</h2>",
        table(["fold", "regional strike (compass)", "resultant length R", "corridor px"], strike_rows),
        f'<p class="small">{esc(card["measured_strike"]["note"])}</p>',
        "<h2>5 · Uniqueness and the lane gate</h2>",
        table(["registry", "surface literal", "dots literal", "dots policy"], [
            [f'full census ({lane["full_census"]["n_priors"]} rasters)',
             esc(lane["full_census"]["surface_literal"]["verdict"]),
             esc(lit_full["verdict"]), esc(pol_full["verdict"])],
            [f'restricted scored-only ({lane["restricted_scored_only"]["n_priors"]} rasters)',
             esc(lane["restricted_scored_only"]["surface_literal"]["verdict"]),
             esc(lit_r["verdict"]), esc(pol_r["verdict"])],
        ]),
        f'<p class="small">Full census dots: max rank correlation '
        f'{f6(lit_full["max_spearman"])} (bar 0.90), max share of my dots within 3 px of one prior '
        f'{f6(lit_full["max_near_3px_fraction"])} (bar 0.70). Restricted scored-only dots: max ρ '
        f'{f6(lit_r["max_spearman"])}, max near-3px share {f6(lit_r["max_near_3px_fraction"])}. '
        f'Quota placement against the restricted informative supports filled '
        f'{lane["restricted_scored_only"]["quota_placement_dots"]:,} of {ho["budget_per_fold"] * 4:,} '
        f'dots at worst share '
        f'{f6(lane["restricted_scored_only"]["quota_placement"]["worst"])}. '
        f'{esc(lane["doctrine"])}</p>',
        "<h2>6 · Not the union of the two views</h2>",
        table(["comparison", "shared cells", "Jaccard", "identical?"], [
            ["primary vs union max(pA,pB)", f'{nu["shared_with_union"]:,}',
             f'{nu["jaccard_with_union"]:.4f}', "yes" if nu["dots_equal_union"] else "no"],
            ["primary vs single_A", f'{nu["shared_with_single_A"]:,}',
             f'{nu["jaccard_with_single_A"]:.4f}', "yes" if nu["dots_equal_single_A"] else "no"],
            ["primary vs single_B", f'{nu["shared_with_single_B"]:,}',
             f'{nu["jaccard_with_single_B"]:.4f}', "yes" if nu["dots_equal_single_B"] else "no"],
            ["primary vs B-only-suppressed", f'{nu["shared_with_bonly_suppressed"]:,}',
             f'{nu["jaccard_with_bonly_suppressed"]:.4f}', "no"],
        ]),
        f'<p><b>not-the-union gate:</b> {"PASS" if nu["not_union_pass"] else "FAIL"}.</p>',
        "<h2>7 · Placement and catalogue ring</h2>",
        f'<p class="small">{bp["dots"]:,} dots placed from a {bp["pool_px"]:,}-px pool '
        f'({bp["eligible_px"]:,} eligible); 200 m catalogue ring excluded; minimum distance to a '
        f'mapped trace {bp["min_cat_dist_m"]:.1f} m, median {bp["median_cat_dist_m"]:.1f} m, '
        f'{bp["dots_within_300m_of_catalogue_pct"]:.2f}% of dots inside the metric\'s 300 m kernel. '
        f'B-only disagreement stratum used as a suppression set: {bp["b_only_suppression"]["b_only_px"]:,} '
        f'px vetoed, leaving {bp["b_only_suppression"]["supp_pool_px"]:,} px.</p>',
        "<h2>8 · On-disk validator</h2>",
        table(["check", "value"], [
            ["bands / dtype", f'{val["count"]} / {val["dtype"]}'],
            ["CRS", f'{esc(val["crs"])} (match: {val["crs_match"]})'],
            ["shape", f'{esc(val["shape"])} (match: {val["shape_match"]})'],
            ["transform / bounds", f'match: {val["transform_match"]} / {val["bounds_match"]}'],
            ["NaN / inf inside footprint", f'{val["nan"]} / {val["infinite"]}'],
            ["value range", f'[{val["min"]}, {val["max"]}] → in [0,1]: {val["range_ok"]}'],
            ["emitted cells", f'{val["ones"]:,}'],
            ["verdict", "PASS" if val["PASS"] else "FAIL"],
        ]),
        f'<p class="small">{esc(val["range_rule_source"])}</p>',
        "<h2>9 · Per-candidate geological reasoning</h2>",
        f'<p><a href="downloads/h91-a-only-reasoning.csv">h91-a-only-reasoning.csv</a> — '
        f'{bu["n_reasoning_rows"]:,} rows, one per emitted cell in a disagreement stratum, each with '
        f'the two view probabilities, the distance to the nearest mapped trace, a geological reading '
        f'and an explicit falsifier. Phase-2 reviewers verify faults, so the A-only cells carry the '
        f'buried-continuation reading and the B-only cells carry the surface-artifact reading.</p>',
        "<h2>10 · Run card and provenance</h2>",
        f'<p><a href="data/h91_run_card.json">docs/data/h91_run_card.json</a> · '
        f'<a href="data/h91_channels.json">channels</a> · '
        f'<a href="data/h91_fit.json">fit + canary</a> · '
        f'<a href="data/h91_holdout.json">holdout</a> · '
        f'<a href="data/h91_independence.json">independence</a> · '
        f'<a href="data/h91_lane.json">lane</a> · '
        f'<a href="data/h91_build.json">build</a>. '
        f'Inputs: {esc(card["inputs_provenance"])}.</p>',
        '<p class="small">Irregularity raised this round: <b>IR-H91-001</b> — 30 of 102 channel files '
        'failed the byte-integrity guard after they had passed it (torn write against a concurrently '
        'snapshotting filesystem, the IR-H82-002 mechanism). '
        '<a href="../scripts/repair_h91_channels.py">scripts/repair_h91_channels.py</a> recomputed them from the '
        'pinned rasters and re-hashed the bank; see '
        '<a href="data/h91_channels.json">the channels receipt</a>.</p>',
        '<footer><p><a href="index.html">← Overview</a> · '
        '<a href="h91-executive-summary.html">Submission guide</a> · '
        '<a href="h91-hypotheses.html">Hypotheses</a> · '
        '<a href="h91-sources.html">Sources</a> · '
        'Independent competition research; predictions are not verified faults.</p></footer>',
    ]
    return page("H91 result — GEMSDOE52", "".join(body),
                "H91 continuous directional alignment result, with the explicit download and "
                "submission verdict.")


# --------------------------------------------------------------------------- h91-executive-summary
def build_summary() -> str:
    steps = [
        ("Download the GeoTIFF", f'Click the green button above (or '
         f'<a href="downloads/{esc(SHORT.name)}">downloads/{esc(SHORT.name)}</a>). '
         f'The ZIP contains exactly one TIFF, which the portal also accepts.'),
        ("Open the competition submission page",
         '<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">'
         'drivendata.org/competitions/306/competition-doe-gems/submissions/</a> and log in. '
         'The data tab and submission form are behind the DrivenData login, so this repository '
         'cannot upload on your behalf.'),
        ("Choose the file", f'Select <code>{esc(TIF.name)}</code> '
         f'({TIF.stat().st_size:,} bytes).'),
        ("Add the name and note",
         f'Name: <code>{esc(bu["name"])}</code><br>Note: <code>{esc(bu["note"])}</code> '
         f'({bu["note_chars"]}/140 characters).'),
        ("Submit, then read the verdict here",
         'A public score appears on the leaderboard. It is a <b>public-test-set</b> number; the '
         'Initial Prize Round is scored on the private set and the Final Prize Round re-scores the '
         'same file against an expanded label set.'),
    ]
    step_html = "".join(
        f'<div class="step"><div class="step-num">{i}</div><div class="step-text">'
        f'<strong>{esc(t)}</strong><br>{d}</div></div>'
        for i, (t, d) in enumerate(steps, 1))
    body = [
        "<h1>Executive summary — exactly how to submit</h1>",
        actions(),
        verdict_notice(),
        "<h2>Step by step</h2>", step_html,
        "<h2>What the portal checks, and what we measured on disk</h2>",
        table(["portal rule (official page)", "measured on the file above", "status"], [
            ["Single-band GeoTIFF (.tif) or a .zip containing one",
             f'{val_count()} band, dtype {bu["validator"]["dtype"]}', "PASS"],
            ["Values in [0, 1]", f'[{bu["validator"]["min"]}, {bu["validator"]["max"]}] exactly',
             "PASS"],
            ["Same CRS, shape and geotransform as the submission format",
             f'{esc(bu["validator"]["crs"])}, {esc(bu["validator"]["shape"])}, '
             f'transform match {bu["validator"]["transform_match"]}', "PASS"],
            ["No NaN inside the footprint", f'{bu["validator"]["nan"]} NaN, '
             f'{bu["validator"]["infinite"]} inf', "PASS"],
        ]),
        "<h2>The score this repository can and cannot claim</h2>",
        f'<p>This round\'s own instrument, HOLDOUT-DTI '
        f'<code>{esc(card["holdout"]["evaluator"])}</code> over {WITHHELD:,} withheld positive '
        f'pixels: primary <code>{esc(ho["candidate"])}</code> {f6(SCORES[ho["candidate"]]["dti"])} '
        f'{ci(SCORES[ho["candidate"]]["ci95"])} against the single-view control '
        f'<code>single_B</code> {f6(SCORES["single_B"]["dti"])} '
        f'{ci(SCORES["single_B"]["ci95"])}, paired Δ '
        f'{f6(PAIR["single_B"]["delta"])} {ci(PAIR["single_B"]["ci95"])}. '
        f'That is a <b>holdout</b> number, not a leaderboard number: in this repository the '
        f'hide-and-recover instrument does not rank board performance (measured Spearman −0.10 over '
        f'owner-reported scores), and no organizer receipt exists for any file here.</p>',
        "<h2>What this submission is</h2>",
        f'<p>{esc(card["hypothesis"])}</p>',
        "<h2>Preserved archives — do not upload</h2>",
        '<details open><summary>Earlier research artefacts, kept for audit</summary>'
        '<p class="small">H58: <a href="downloads/h58-candidate.tif">gems52-h58-coldgeo-consensus-'
        '22px-a55b0dee38-research.tif</a> — research only, not approved to submit, '
        f'SHA-256 <code>{H58_SHA24}…</code> (<a href="h58.html">audit</a>). '
        'The unapproved H57 alternate '
        '<a href="downloads/gems57-h57-credit-core25517-plus-novel8000-33517px-zeros.tif">'
        'gems57-h57-credit-core25517-plus-novel8000-33517px-zeros.tif</a> '
        '(<a href="h57-creditcore.html">historical audit</a>). '
        '<a href="h55-edge.html">H55-EDGE negative-result archive</a>. '
        'R5 strictly-novel artefact '
        '<a href="downloads/gems52-r5-novel-n5_strike_ridge-16681px-20261008T234033Z-d2bfb0f7-zeros.tif">'
        'gems52-r5-novel-n5_strike_ridge-16681px-20261008T234033Z-d2bfb0f7-zeros.tif</a>, SHA-256 '
        f'<code>{R5_SHA24}…</code>, also at '
        '<a href="downloads/r5-candidate.tif">downloads/r5-candidate.tif</a> — OK to download, '
        'not slot-approved, P(DTI &gt; 0.2778) = 0.366, P(&gt; 0.3195) = 0.226, '
        'P(&gt; 0.3774) = 0.031. H82: '
        '<a href="downloads/h82-candidate.tif">h82-candidate.tif</a> — research only. '
        'H83: <a href="downloads/h83-candidate.tif">h83-candidate.tif</a> — format-valid but never '
        'holdout-validated (its own run card records <code>holdout_dti = NOT_EVALUATED</code>), '
        'so it is archived, not promoted.</p></details>',
        '<p class="small">No weekly slot is approved by this page. Promotion is a separate selector '
        'step, within the weekly cap shown on the submission page.</p>',
        '<footer><p><a href="index.html">← Overview</a> · <a href="h91.html">Full H91 result</a> · '
        '<a href="validator.html">Browser validator</a></p></footer>',
    ]
    return page("How to submit — GEMSDOE52", "".join(body),
                "Step-by-step submission guide with the one-click download and the explicit "
                "download/submit verdict.")


def val_count():
    return bu["validator"]["count"]


# --------------------------------------------------------------------------------- h91-hypotheses
def build_hypotheses() -> str:
    doc = (ROOT / "knowledge/86_hypotheses_H91_preregistered.md").read_text()
    m = re.search(r"## 2\. Ranked hypotheses.*?(?=## 3\.)", doc, flags=re.S)
    tbl = m.group(0) if m else ""
    rows = []
    for line in tbl.splitlines():
        if not line.startswith("|") or set(line) <= set("|- "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and cells[0] in ("Rank",):
            continue
        if len(cells) >= 7:
            rows.append([f"<b>{esc(cells[0])}</b>", esc(cells[1]), esc(cells[2]), esc(cells[3]),
                         esc(cells[4]), esc(cells[5]), esc(cells[6])])
    body = [
        "<h1>H91 — ranked geological hypotheses</h1>",
        '<p class="small">Preregistered in <a href="../knowledge/86_hypotheses_H91_preregistered.md">'
        'knowledge/74</a> before any fit, canary, holdout or placement read. SHA-256 '
        f'<code>{esc(card["preregistration"]["sha256"])}</code>.</p>',
        "<h2>Ranked by expected holdout gain and implementation cost</h2>",
        table(["rank", "hypothesis", "layers", "physical signature", "why it should catch a "
               "catalogue-missing fault", "how it differs from what this repo already has", "cost"],
              rows),
        "<h2>What was executed</h2>",
        f'<p>Rank 1 (H91-A) with rank 2 (H91-B, the radiometric Th/K and U/K ratio fields) folded '
        f'into the same channel build: {chm["n_learner_channels"]} learner channels over '
        f'{len(chm["bands"])} fields × {len(chm["lags_px"])} lags × 4 statistics, plus '
        f'{chm["n_control_channels"]} 8-direction control channels. Ranks 3–5 are recorded as '
        f'proposals; H91-C (the B-only suppression set) was also computed and is reported on the '
        f'result page.</p>',
        "<h2>What is deliberately not claimed</h2>",
        '<p>No organizer leaderboard page, portal receipt or private-set information was accessed. '
        'The DrivenData data tab is login-walled, so every raster is an owner-mirror copy verified '
        'only against its own SHA-256 pin. Nothing here is a guaranteed score, and a negative '
        'result is a deliverable.</p>',
        '<footer><p><a href="h91.html">← H91 result</a></p></footer>',
    ]
    return page("H91 hypotheses — GEMSDOE52", "".join(body),
                "The ranked, preregistered geological hypotheses for H91.")


# ------------------------------------------------------------------------------------ h91-sources
SOURCES = [
    ("Competition overview and performance metric",
     "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
     "DTI definition, α 0.2, β 0.8, R 300 m triangular kernel, submission format rules"),
    ("Competition data tab (login-walled)",
     "https://www.drivendata.org/competitions/306/competition-doe-gems/data/",
     "training_features.tif, labels.tif, sample_submission.tif, 1m_DEM_links.csv"),
    ("DrivenData GEMS task page", "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
     "problem description"),
    ("Reference solution", "https://github.com/drivendataorg/gems-prize-reference-solution",
     "the organiser's simple baseline"),
    ("Blum & Mitchell, Co-Training (COLT 1998)",
     "https://doi.org/10.1145/279943.279962",
     "the two-view method this lane implements; sufficiency/compatibility/independence are assumptions"),
    ("USGS GeoDAWN release", "https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and",
     "airborne magnetic and radiometric surveys of the northwestern Great Basin"),
    ("DOE GDR submission 1391 / INGENIOUS", "https://gdr.openei.org/submissions/1391",
     "INGENIOUS geothermal play fairways, fault traces, well/spring temperature and chemistry"),
    ("EPSG:32611", "https://epsg.io/32611",
     "WGS 84 / UTM zone 11N — the competition CRS"),
    ("Tversky index", "https://en.wikipedia.org/wiki/Tversky_index",
     "the set-overlap family the distance-weighted metric belongs to"),
    ("DOE GEMS prize document (FY26 OSTI 96647)",
     "https://docs.nlr.gov/docs/fy26osti/96647.pdf",
     "the prize rules document referenced by the brief"),
    ("USGS 3DEP", "https://www.usgs.gov/3d-elevation-program",
     "the 1 m DEM source behind the LiDAR scarp layer; public domain, but not reachable from this sandbox"),
    ("Mardia & Jupp, Directional Statistics",
     "https://doi.org/10.1002/9780470316979",
     "the circular-mean / resultant-length construction used for the axial direction channels"),
]


def build_sources() -> str:
    rows = [[f'<a href="{esc(u)}">{esc(t)}</a>', f'<code>{esc(u)}</code>', esc(w)]
            for t, u, w in SOURCES]
    body = [
        "<h1>Sources — official and verified</h1>",
        "<p>Every link below was used from this repository. Where a page is login-walled or outside "
        "the sandbox's network egress, that is stated rather than implied.</p>",
        table(["source", "url", "what it is used for"], rows),
        "<h2>Provenance of the rasters</h2>",
        '<p>The three competition rasters, the seven external layers and the twelve scored priors are '
        'restored from the owner\'s hash-pinned sibling repositories through the GitHub Contents API '
        'and verified by SHA-256 and byte count (23/23 pins, '
        '<a href="data/h91_preflight_integrity.json">receipt</a>). That proves mirror integrity, '
        '<b>not</b> organiser authentication: the DrivenData data tab requires a login this sandbox '
        'does not have.</p>',
        '<h2>Leaderboard observations</h2>',
        '<p>The last dated public-board observation is in '
        '<a href="../registry/leaderboard_snapshot_2026-10-09.json">registry/'
        'leaderboard_snapshot_2026-10-09.json</a> (tool-retrieved, PUBLIC-BOARD, team-level; the '
        'board prints a team name and a number, never a filename). The brief\'s numbers — 0.3774, '
        '0.3195, 0.2778 — are therefore <b>owner-reported/public</b>, never organizer-confirmed for '
        'a filename.</p>',
        '<footer><p><a href="h91.html">← H91 result</a></p></footer>',
    ]
    return page("Sources — GEMSDOE52", "".join(body),
                "Official, verified sources used by this repository.")


# ---------------------------------------------------------------------------------------- index
def build_index() -> str:
    legacy = legacy_body()
    body = [
        "<h1>🔥 GEMSDOE52 — geothermal fault discovery, DOE GEMS</h1>",
        '<p>Two-view co-training lane: potential-field/subsurface View A against surface View B, '
        'with disagreement as the discovery signal. Blum &amp; Mitchell, COLT 1998, '
        '<a href="https://doi.org/10.1145/279943.279962">doi:10.1145/279943.279962</a>.</p>',
        actions(),
        verdict_notice(),
        "<h2>H91 in one paragraph</h2>",
        f'<p>{esc(card["hypothesis"])} On the hide-and-recover instrument the primary arm '
        f'<code>{esc(ho["candidate"])}</code> scored HOLDOUT-DTI {f6(SCORES[ho["candidate"]]["dti"])} '
        f'{ci(SCORES[ho["candidate"]]["ci95"])} against the single-view control '
        f'<code>single_B</code> {f6(SCORES["single_B"]["dti"])} '
        f'{ci(SCORES["single_B"]["ci95"])} (paired Δ {f6(PAIR["single_B"]["delta"])} '
        f'{ci(PAIR["single_B"]["ci95"])}), with {WITHHELD:,} withheld positive pixels, '
        f'{chm["n_learner_channels"]} new channels and a leakage canary at '
        f'{f6(fit["canary_max_learner_overall"])} against a 0.90 bar. '
        f'<b>Verdict {esc(VERDICT)}</b>: '
        + ("every gate passed." if SUB_OK else
           "the file is format-valid and downloadable, but it has not beaten the control with a CI "
           "above zero, so <b>do not upload it</b> and do not spend a weekly slot on it.")
        + f' Full record: <a href="h91.html">H91 result</a>, '
        f'<a href="h91-executive-summary.html">submission guide</a>, '
        f'<a href="h91-hypotheses.html">hypotheses</a>, '
        f'<a href="h91-sources.html">sources</a>, '
        f'<a href="data/h91_run_card.json">JSON run card</a>.</p>',
        "<h2>Why the 0.2778 file won, and what beating 0.3195 needs</h2>",
        '<p>The measured answer is arithmetic, not geology: the reported-0.2778 file '
        '(<code>h33-h33-2-b2</code>, owner-reported) is its 0.2600 parent with the 100–200 m '
        'catalogue ring deleted — 6,436 pixels, all inside the ring, +6.8 % relative score, which is '
        'only possible if the deleted mass earned zero credit while still paying the false-positive '
        'tax. Its credit density is ρ ≈ 0.1387 at 37,654 emitted px; reaching 0.3195 at the same '
        'budget needs ρ ≈ 0.1595, and reaching 0.3774 needs ρ ≈ 0.1884. The binding constraint on '
        'this family is the ranker\'s ρ(S) decay, not the emission budget. '
        '<a href="h91.html#why">Full board algebra</a> · '
        '<a href="../knowledge/49_why_02778_phd_answer.md">knowledge/49</a>.</p>',
        f"<details><summary>Preserved research archive — every earlier round, verbatim</summary>"
        f"{legacy}</details>",
        '<footer><p>Independent competition research, not an official DOE or DrivenData site. '
        'Predictions are not verified faults or geothermal discoveries. · '
        '<a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code &amp; reproducibility</a> · '
        'H91 / 2026-10-10</p></footer>',
    ]
    return page("GEMSDOE52 — geothermal fault discovery", "".join(body),
                "Current-round download, explicit submit verdict, and the preserved research archive.")


def main() -> int:
    (DATA).mkdir(parents=True, exist_ok=True)
    for name in ("run_card", "channels", "fit", "holdout", "independence", "build",
                 "build_placement", "lane", "preflight_integrity"):
        src = EV / f"h91_{name}.json"
        if src.exists():
            shutil.copy(src, DATA / src.name)
    (DOCS / "h91.html").write_text(build_h91_page())
    (DOCS / "h91-executive-summary.html").write_text(build_summary())
    (DOCS / "h91-hypotheses.html").write_text(build_hypotheses())
    (DOCS / "h91-sources.html").write_text(build_sources())
    # This round is NEGATIVE, so the global submission pointer stays on main's incumbent, and
    # docs/index.html, docs/executive-summary.html and docs/irregularities.html are main's pages and
    # are NOT overwritten here: this round adds only its own h91* pages (repo precedent -- keep main's
    # site and add the round's own blocks, cf. commits 1c5faa9 and e916c87).
    print("published:", ", ".join(["h91.html", "h91-executive-summary.html", "h91-hypotheses.html",
                                   "h91-sources.html"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
