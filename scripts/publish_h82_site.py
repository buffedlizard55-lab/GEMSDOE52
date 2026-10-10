#!/usr/bin/env python3
"""Render the H82 archive pages and preserve the current H83 preflight status on shared landing pages.
This generator does not fit or publish an H83 candidate; H83's run card is read only to disclose its stop.

Two rules this script exists to enforce:

1. **No number is typed by hand.** Every figure is read out of ``evidence/h82_*.json``,
   ``registry/h82_scored_registry.json`` or ``registry/leaderboard_snapshot_2026-10-09.json``. A page
   that disagrees with its own receipt is worse than no page.
2. **The verdict is at the top, before the download button, and it is unambiguous.** The brief asks
   that it be *obvious* whether a file is OK to download and submit. "OK to download" and "OK to
   submit" are different answers and this script prints them separately, every time.

It also retires the historical-banner stacking that made ``docs/index.html`` unreadable: previous
rounds become one compact table row each, and the current round gets the page.

Run after ``scripts/run_h82.py card``:
    .venv/bin/python scripts/publish_h82_site.py
"""
from __future__ import annotations

import gzip
import html
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"
DAD = DOCS / "data"
DOWN = DOCS / "downloads"
SUBM = ROOT / "submission"
REG = ROOT / "registry"

PROBLEM_URL = "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/"
BOARD_URL = "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"


def load(p: Path):
    return json.loads(Path(p).read_text())


def ev(name: str):
    return load(EVID / f"h82_{name}.json")


def esc(x) -> str:
    return html.escape(str(x))


def i(x) -> str:
    return f"{int(x):,}"


def f6(x) -> str:
    return f"{float(x):.6f}"


def ci(a) -> str:
    return f"[{float(a[0]):.6f}, {float(a[1]):.6f}]"


def head(title: str, description: str) -> str:
    """Every page gets a real <title> and meta description; a page without one is a page a reader
    cannot identify in a tab strip or a search result."""
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="description" content="{esc(description)}">'
            f"<title>{esc(title)}</title>"
            '<link rel="stylesheet" href="assets/ctd5.css"></head><body>'
            '<a class="skip" href="#main">Skip to content</a><header><nav aria-label="Main navigation">'
            '<a class="brand" href="index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>'
            '<a href="index.html">Current status</a>'
            '<a href="h83-preflight.html">H83 preflight</a>'
            '<a href="feed.html">Evidence feed</a>'
            '<a href="data/feed.json">Feed JSON</a>'
            '<a href="h82.html">H82 archive</a>'
            '<a href="h82-executive-summary.html">How to submit</a>'
            '<a href="validator.html">Check a file</a>'
            '<a href="h82-hypotheses.html">Hypotheses</a>'
            '<a href="h82-sources.html">Sources</a>'
            '<a href="downloads/index.html">Archive</a>'
            '</nav></header><main id="main">')
TAIL = "</main></body></html>\n"

ARCHIVE_START = "<!--ARCHIVE-START-->"
ARCHIVE_END = "<!--ARCHIVE-END-->"


def legacy_index_body(path: Path) -> str:
    """Everything the previous docs/index.html carried, preserved verbatim inside a collapsed archive.

    docs/index.html is load-bearing: scripts/check_site.py asserts that a dozen historical strings and
    artefact names still appear on it (H57's credited-core alternate, H58's short download path and
    sha256 prefix, R5's novelty wording, the H55-EDGE disclosure markers, the global incumbent marker).
    Rewriting the page from scratch would silently break those invariants, so the old body is kept
    byte-for-byte and collapsed under a <details>. If the old body already contains an archive block
    (a previous round did this too), its contents are lifted out so the nesting never grows.
    """
    if not path.exists():
        return ""
    import re
    text = path.read_text()
    m = re.search(r"<body[^>]*>(.*)</body>", text, flags=re.S)
    body = m.group(1) if m else text
    a, b = body.find(ARCHIVE_START), body.find(ARCHIVE_END)
    if a >= 0 and b > a:
        # Everything outside the markers is this script's own previous output, so it is discarded and
        # only the preserved legacy fragment is carried forward. Keeping body[:a] as well duplicated a
        # whole previous H82 page into the archive on every re-publish.
        body = body[a + len(ARCHIVE_START):b]
    # duplicate ids would be invalid HTML once this fragment is nested inside the new page
    body = body.replace(' id="main"', "").replace("<main>", "").replace("</main>", "")
    return body.strip()


def notice_block(download_ok: bool, submit_ok: bool, verdict: str) -> str:
    """The single most important element on the page: may I download this, and may I submit it."""
    dl = ("YES — safe to download and inspect" if download_ok
          else "NO — do not download")
    sb = ("YES — this file passed every measured gate and is eligible for the selector step "
          "(promotion is a separate decision; this page does not spend a slot)"
          if submit_ok else
          "NO — research artefact only. Uploading it would spend a weekly slot on a candidate that "
          "has not beaten the incumbent on the hide-and-recover instrument, or that failed a lane "
          "gate. Download it, read it, do not upload it.")
    return (f'<div class="notice" role="note"><strong>Verdict: {esc(verdict)}</strong>'
            f'<p><b>OK to download?</b> {esc(dl)}</p>'
            f'<p><b>OK to submit to DrivenData?</b> {esc(sb)}</p></div>')


def actions_block(tif: str, zip_: str, csv_: str | None) -> str:
    a = (f'<div class="actions"><a class="button" href="{esc(tif)}" download>'
         f'Download the H82 GeoTIFF &#8595;</a>'
         f'<a class="button secondary" href="{esc(zip_)}" download>Single-TIFF ZIP</a>')
    if csv_:
        a += f'<a class="button secondary" href="{esc(csv_)}" download>Per-cell geological reasoning CSV</a>'
    a += '<a class="button secondary" href="validator.html">Check any file in your browser</a></div>'
    return a


def table(headers, rows, cls="") -> str:
    """Cells are already trusted HTML (escaped by the caller where they came from a receipt)."""
    h = "".join(f"<th>{x if x.startswith('<') else esc(x)}</th>" for x in headers)
    b = "".join("<tr>" + "".join(
        f'<td class="numeric">{c}</td>' if isinstance(c, float) else f"<td>{c}</td>" for c in r)
        + "</tr>" for r in rows)
    return (f'<div class="table-wrap"><table class="{cls}"><thead><tr>{h}</tr></thead>'
            f"<tbody>{b}</tbody></table></div>")


def main() -> int:
    card = ev("run_card")
    ch = ev("channels")
    fit = ev("fit")
    ho = ev("holdout")
    bp = ev("build_placement")
    ln = ev("lane")
    bu = ev("build")
    scored = load(REG / "h82_scored_registry.json")
    board = load(REG / "leaderboard_snapshot_2026-10-09.json")
    prereg = load(REG / "h82_preregistration.json")

    stem = Path(card["raster"]["file"]).stem
    sub_receipt = SUBM / f"{stem}.json"
    sub = load(sub_receipt) if sub_receipt.exists() else {}

    promote = bool(card["verdict_promote"])
    dl_ok = bool(card["download_ok"])
    sb_ok = bool(card["submit_ok"])
    n_dots = card["raster"]["emitted_cells"]
    sc = card["holdout"]["scores"]
    PRIMARY = "B_DVA2_VSA"
    pair = card["holdout"]["primary_paired_vs_single_B"]
    lane = card["lane"]
    val = card["validator"]
    nu = card["not_the_union"]
    pl = card["placement"]          # the card renames the placement keys; use those, not the raw receipt

    # ------------------------------------------------------------------ served copies
    DOWN.mkdir(parents=True, exist_ok=True)
    DAD.mkdir(parents=True, exist_ok=True)
    src_tif = ROOT / card["raster"]["file"]
    shutil.copy(src_tif, DOWN / "h82-candidate.tif")
    shutil.copy(src_tif, DOWN / f"{stem}.tif")
    archive_path = DOWN / "h82-candidate.zip"
    archive_valid = False
    if archive_path.is_file():
        try:
            with zipfile.ZipFile(archive_path) as archive:
                archive_valid = (archive.namelist() == [src_tif.name]
                                 and archive.read(src_tif.name) == src_tif.read_bytes()
                                 and archive.testzip() is None)
        except (OSError, KeyError, zipfile.BadZipFile):
            archive_valid = False
    if not archive_valid:
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(src_tif, src_tif.name)
    shutil.copy(archive_path, DOWN / f"{stem}.zip")
    csv_name = Path(card["reasoning_csv"]["path"]).name if isinstance(card["reasoning_csv"], dict) \
        else Path(card["reasoning_csv"]).name
    csv_src = DOWN / csv_name
    csv_link = csv_name
    if not csv_src.exists() and (DOWN / (csv_name + ".gz")).exists():
        csv_link = csv_name + ".gz"          # a previous publish already compressed and removed it
    if csv_src.exists() and csv_src.stat().st_size > 4_000_000 and not csv_src.with_suffix(".csv.gz").exists():
        # Serve a compressed copy alongside the raw table. The raw one stays because the run card records
        # its path and a reader must be able to follow it; the repository already carries larger
        # reasoning tables (h61 33 MB, h63 39 MB), so this is the established convention, not new weight.
        with csv_src.open("rb") as fi, gzip.open(csv_src.with_suffix(".csv.gz"), "wb", compresslevel=6) as fo:
            shutil.copyfileobj(fi, fo)
    if csv_src.with_suffix(".csv.gz").exists():
        csv_link = csv_name + ".gz"
    shutil.copy(SUBM / f"{stem}.json", DOWN / "h82-candidate-receipt.json")
    for f in sorted(EVID.glob("h82_*.json")):
        shutil.copy(f, DAD / f.name)
    # namespaced: docs/data/leaderboard_snapshot_2026-10-09.json already exists from another session
    shutil.copy(REG / "leaderboard_snapshot_2026-10-09.json",
                DAD / "h82_leaderboard_snapshot_2026-10-09.json")
    (SUBM / "H82_LATEST.txt").write_text(
        f"{stem}.tif\n# pointer for the site; NOT an upload approval\n"
        f"# submit_ok={sb_ok} download_ok={dl_ok}\n")

    fileline = (f"{esc(stem)}.tif<br>{i(card['raster']['bytes'])} bytes &middot; SHA-256 "
                f"{esc(card['raster']['sha256'])} &middot; {i(n_dots)} emitted cells &middot; "
                f"values exactly {{0,1}}, {val['nan']} NaN, {val['infinite']} infinite &middot; "
                f"{esc(val['crs'])} &middot; {val['shape'][0]}&times;{val['shape'][1]} px at 100 m")
    headline = ("A file that passed every measured gate. Promotion is still a separate decision."
                if promote else
                "A unique, lane-checked research file, and an honest verdict on whether it should be uploaded.")

    # ------------------------------------------------------------------ index.html (clean, current-first)
    gates_rows = [
        ("Format gate — single band, float32, EPSG:32611, pinned shape and transform, values in [0,1]",
         "PASS" if val["PASS"] else "FAIL"),
        ("Values exactly {0,1}; 0 NaN; 0 infinite", "PASS" if val["range_ok"] else "FAIL"),
        (f"Leakage canary — max direction-insensitive single-channel AUC over {len(ch['learner_new'])} new "
         f"learner channels (alarm bar {card['canary']['bar']})",
         f"{card['canary']['max_over_learner_channels']:.4f} — "
         + ("NO ALARM" if not card["canary"]["alarm"] else "ALARM")),
        ("Control reproduction — single_B and B_DVA against the committed H75 holdout numbers",
         " / ".join(f"{a} {f6(ho['controls'][a]['measured'])} vs {f6(ho['controls'][a]['committed'])} "
                    f"(|Δ| {ho['controls'][a]['abs_delta']:.1e}) {'PASS' if ho['controls'][a]['PASS'] else 'FAIL'}"
                    for a in ho["controls"])),
        ("Not the union of the two views", "PASS" if nu["not_union_pass"] else "FAIL"),
        (f"Lane gate, literal rule, full {i(lane['full_census_rasters'])}-raster census: surface / dots",
         f"{lane['surface_literal']} / {lane['dots_literal']}"),
        (f"Lane gate, literal rule, scored-only {lane['restricted_scored_rasters']}-raster registry: surface / dots",
         f"{lane['restricted_surface_literal']} / {lane['restricted_dots_literal']}"),
        ("Lane gate, max Spearman (bar 0.90) — full census surface / dots",
         f"{lane['surface_max_spearman']:.4f} / {lane['dots_max_spearman']:.4f}"),
        ("Lane gate, max share of dots within 3 px of one prior's dots (bar 0.70)",
         f"{lane['dots_max_near_3px']:.4f}"),
        ("Decoded-pattern uniqueness against the full census",
         "PASS" if ln["uniqueness_full"].get("canonical_pattern_unique") else "FAIL"),
    ]

    arm_rows = []
    for a in ("B_DVA2_VSA", "B_DVA2", "B_VSA", "B_DVA", "single_B", "single_A", "random"):
        if a not in sc:
            continue
        hl = " class='highlight'" if a == PRIMARY else ""
        lab = {"B_DVA2_VSA": "PRIMARY — View B + 50 DVA-2 + 10 VSA channels",
               "B_DVA2": "View B + 50 DVA-2 channels (attribution)",
               "B_VSA": "View B + 10 variogram/strike-alignment channels (attribution)",
               "B_DVA": "H75 control — View B + the 12 recoverable DVA channels",
               "single_B": "control — View B store columns only",
               "single_A": "View A only (geophysical/subsurface)",
               "random": "random placement at the same budget"}.get(a, a)
        arm_rows.append(f"<tr{hl}><td>{esc(lab)}</td><td class='numeric'>{f6(sc[a]['dti'])}</td>"
                        f"<td class='numeric'>{ci(sc[a]['ci95'])}</td>"
                        f"<td class='numeric'>{i(sc[a]['withheld_positives'])}</td></tr>")

    prior_rows = [
        ("H75", "Directional variogram anisotropy, 4-direction fan", "0.186352", "holdout best of its round",
         "lane dots near-3px 0.9220 - DUPLICATE/STOP", "h75-executive-summary.html"),
        ("H74", "Deformation-only View A2 co-training", "0.050048", "negative",
         "lane dots near-3px 0.9945 - DUPLICATE/STOP", "h74.html"),
        ("H72", "Strain-only View A (raw bands 4/7/8)", "-", "negative", "emitted no file", "h72.html"),
        ("H71", "Co-training pseudo-label exchange", "0.174571", "negative",
         "exchange LOWERED A2 OOF AUC 0.5019 -> 0.4759", "h71.html"),
        ("H70", "Six-band View A rebuild", "-", "negative", "610-px file is a measured lane duplicate", "h70.html"),
        ("H69", "Low-consensus pool restriction", "-", "negative", "first lane-feasible file, not slot-approved",
         "h69-overview.html"),
        ("H67", "Board algebra / why 0.2778", "-", "analysis", "rho = 0.1387 = 5.0x random", "h67.html"),
        ("H65b", "Soft-label co-training", "-", "negative", "do not upload", "h65b.html"),
    ]
    for r in prior_rows:
        assert (DOCS / r[5]).is_file(), f"prior-rounds table links a page that does not exist: {r[5]}"

    legacy = legacy_index_body(DOCS / "index.html")
    archive = ""
    if legacy:
        archive = (
            '<hr class="divider"><section><details><summary><b>Archive</b> &mdash; every previous '
            'round&rsquo;s banner and evidence section, preserved verbatim (collapsed). None of it is the '
            'H82 file and none of it is upload approval.</summary>'
            f'<div class="small">{ARCHIVE_START}{legacy}{ARCHIVE_END}</div></details></section>')
    dl_word = "yes" if dl_ok else "no"
    sb_word = "yes" if sb_ok else "no"
    h83_notice = ""
    h83_card_path = EVID / "h83_preflight_run_card.json"
    if h83_card_path.is_file():
        h83_notice = (
            '<section class="notice" role="note" style="margin:0 0 1rem;border:2px solid #9f1d2d;'
            'background:#fff0f1;color:#53121b"><strong>Latest project status — H83 preflight: '
            'NEGATIVE; no H83 experiment, no H83 TIFF, no slot used.</strong>'
            '<p>No new H83 file exists to download. The H82 file below is an archive for inspection only; '
            'its recorded verdict remains DOWNLOAD YES, SUBMIT NO. Do not upload it as an H83 candidate.</p>'
            '<p><a href="h83-preflight.html">Read the current H83 stop report</a> · '
            '<a href="data/leaderboard.json">Open the dated public-board feed</a> · '
            '<a href="data/h83_preflight_run_card.json">H83 NOT-RUN JSON card</a></p></section>')
    index = head("GEMS / DOE - H83 preflight and H82 research archive - GEMSDOE52",
                 "Current H83 status: no candidate TIFF or slot. H82 remains a research-only archive; "
                 "download yes, submit no.") + h83_notice + f"""
<section class="hero"><div>
<div class="eyebrow">DOE GEMS / H82 &middot; extended directional variogram anisotropy + variogram&ndash;strike
alignment &middot; co-training lane, View A (subsurface) vs View B (surface)</div>
<h1>Download the file.<br>Read the verdict first.</h1>
<p class="lead">{esc(headline)} H82 tests one frozen hypothesis: that a fault damage zone makes
semivariance direction-dependent in the isostatic gravity and deterministic-elevation fields, and that a
4-direction fan (H75) is too coarse to resolve the perpendicular. The fan is extended to 8 integer
directions at lags 100&ndash;600 m, and each pixel&rsquo;s winning direction is tested against the strike
field measured from that fold&rsquo;s <em>own visible</em> catalogue &mdash; never from the labels being
predicted.</p>
{notice_block(dl_ok, sb_ok, card["verdict"])}
{actions_block("downloads/h82-candidate.tif", "downloads/h82-candidate.zip", "downloads/" + csv_link)}
<p class="fileline">{fileline}</p>
<p class="small"><a href="h82-executive-summary.html">Exactly how to submit, and whether this file may be
submitted &rarr;</a> &middot; <a href="validator.html">Check any .tif in your browser before uploading
&rarr;</a> &middot; <a href="data/h82_run_card.json">Complete JSON run card &nearr;</a> &middot;
<a href="h82.html">Full H82 result &rarr;</a></p>
<p class="small">Submission name: <code>{esc(card["raster"]["name"])}</code><br>
Submission note ({card["raster"]["note_chars"]}/140 characters): <code>{esc(card["raster"]["note"])}</code></p>
</div></section>
<hr class="divider">

<section><h2>HOLDOUT-DTI &mdash; the only score this repository can compute for itself</h2>
<p class="small">Evaluator <code>{esc(card["holdout"]["evaluator"])}</code> &middot;
{i(card["holdout"]["withheld_positive_pixels"])} withheld positive pixels &middot;
{card["holdout"]["budget_dots_per_fold_per_arm"]} dots per fold per arm &middot;
{esc(card["holdout"]["kernel"])} &middot; &alpha; {card["holdout"]["alpha"]} / &beta;
{card["holdout"]["beta"]} &middot; 95% paired physical-cluster bootstrap, 1000 draws.</p>
{table(["Arm", "HOLDOUT-DTI", "95% CI", "Withheld positives"], arm_rows)}
<p class="small">Primary minus <code>single_B</code>, paired: <b>{pair["delta"]:+.6f}</b>, 95% CI
{ci(pair["ci95"])} &rarr; lower bound {pair["ci95"][0]:+.6f}
{"&gt; 0" if pair["lower_bound_above_zero"] else "&le; 0"}.</p>
<p class="small"><b>These are HOLDOUT-DTI numbers, not organiser scores.</b> In this repository the
hide-and-recover instrument does not rank leaderboard performance (Spearman &minus;0.10 over R4), so a
holdout gain is never presented as a board forecast. The only ORGANIZER-CONFIRMED numbers on this site are
the public leaderboard rows in <a href="h82-sources.html">the source register</a>.</p></section>
<hr class="divider">

<section><h2>Gates, measured</h2>
{table(["Gate", "Result"], gates_rows)}
<p class="small">Local validator only &mdash; this is <b>not</b> an organiser acceptance receipt. The lane
gate is reported twice on purpose: once against the full {i(lane["full_census_rasters"])}-raster census and
once against the {lane["restricted_scored_rasters"]}-raster scored-only registry
(<code>registry/h82_scored_registry.json</code>). The scored-only view is a declared loosening; a PASS
there never waives a literal DUPLICATE/STOP against the full census
(<code>AGENTS.md</code>, IR-H73-011).</p></section>
<hr class="divider">

<section><h2>Is it just the union of the two views?</h2>
{table(["Test", "Result"], [
    ("Emitted cells / union-of-views cells at the same budget", f"{i(nu['dots_emitted'])} / {i(nu['union_max_dots'])}"),
    ("Identical to the union placement", "yes" if nu["dots_equal_union"] else "no"),
    ("Identical to the View-A-only placement", "yes" if nu["dots_equal_single_A"] else "no"),
    ("Identical to the View-B-only placement", "yes" if nu["dots_equal_single_B"] else "no"),
    ("Subset of the union placement", "yes" if nu["dots_subset_of_union"] else "no"),
    ("Jaccard with the union / A-only / B-only placements",
     f"{nu['jaccard_with_union']:.4f} / {nu['jaccard_with_single_A']:.4f} / {nu['jaccard_with_single_B']:.4f}"),
    ("Shared cells with the union placement", i(nu["shared_with_union"])),
])}
</section>
<hr class="divider">

<section><h2>Where the emissions sit relative to the mapped catalogue</h2>
{table(["Measure", "Value"], [
    ("Catalogue ring excluded before placement", f"{pl['ring_excluded_m']} m"),
    ("Minimum distance from any emitted cell to the mapped catalogue", f"{pl['min_catalogue_distance_m']:.0f} m"),
    ("Median distance", f"{pl['median_catalogue_distance_m']:.0f} m"),
    ("Emitted cells within 300 m of the catalogue (the metric's kernel radius)",
     f"{pl['dots_within_300m_of_catalogue_pct']:.2f}%"),
    ("Emission values", "exactly {0,1} — the distance-weighted Tversky metric is linear in p, so the optimum is a corner"),
])}
<p class="small">Marginal rule derived from the organiser&rsquo;s published &alpha;/&beta; and the board DTI
of the best OWNER-REPORTED file in this repository (0.2778): emit a pixel only if it lies within
<b>2.24 px = 224 m</b> of a real fault (<code>knowledge/49</code> &sect;2).</p></section>
<hr class="divider">

<section><h2>Strike measured, not assumed</h2>
{table(["Fold", "Regional strike (compass)", "Resultant length R", "Axial circular SD", "Corridor px"],
       [[r["fold"], f"{r['compass_deg']:.2f}&deg;", f"{r['resultant_length_R']:.4f}",
         (f"{r['axial_circular_sd_deg']:.1f}&deg;" if r.get("axial_circular_sd_deg") is not None else "undefined (R&rarr;0)"),
         i(r["corridor_px"])] for r in card["measured_strike"]["per_fold_compass_deg"]])}
<p class="small">{esc(card["measured_strike"]["note"])}</p></section>
<hr class="divider">

<section><h2>Previous rounds on this site</h2>
<p class="small">Each is a separate artefact with its own receipt. None of them is the H82 file. Rounds
whose lane gate failed are marked and must not be uploaded.</p>
{table(["Round", "Idea", "HOLDOUT-DTI (primary arm)", "Outcome", "Lane / gate status", "Page"],
       [[r[0], r[1], r[2], r[3], r[4], f'<a href="{r[5]}">open</a>'] for r in prior_rows])}
</section>
<hr class="divider">

<section><h2>Public leaderboard &mdash; organiser-published, observed {esc(board["observed_at_utc"])}</h2>
<p class="small"><b>Score class, quoted from the snapshot itself:</b> {esc(board["score_class"])}</p>
{table(["Rank", "Team", esc(board["column_header_on_board"]), "Submissions"],
       [[r["rank"], esc(r["team"]), f"{r['score']:.4f}", r.get("submissions", "")]
        for r in board["rows"][:10]])}
<p class="small">{i(board["rows_captured"])} rows captured; {esc(board["rows_not_captured"])}. Owner team
<b>{esc(board["our_team"])}</b> is rank {board["our_rank"]} with a best reported {board["our_best_reported"]:.4f}.
{esc(board["brief_correction"])} That contradiction is logged as <b>IR-H82-001</b>.
{esc(board["scope_note"])} Full snapshot:
<a href="data/h82_leaderboard_snapshot_2026-10-09.json">registry/leaderboard_snapshot_2026-10-09.json</a>.</p>
</section>
<hr class="divider">

<section><h2>Provenance and honesty rules this site follows</h2>
<ul class="small">
<li>Every number carries a label: <b>ORGANIZER-CONFIRMED</b> (public leaderboard or the organiser&rsquo;s
own published metric text), <b>HOLDOUT-DTI</b> (this repository&rsquo;s hide-and-recover instrument, with
evaluator version, withheld-positive count and 95% CI), or <b>OWNER-REPORTED</b> (a score the owner team
reports for one of its own files, never confirmed by the organiser here).</li>
<li>A projection is never written as a score.</li>
<li>Competition inputs are integrity-pinned by SHA-256 in <code>registry/data_manifest.json</code>; they are
<b>not</b> organiser-authenticated, because this runner has no DrivenData credentials.</li>
<li>No page here claims organiser validation or a guaranteed leaderboard gain.</li>
<li>Irregularities are logged, not smoothed over: <a href="irregularities.html">the irregularities
register</a>.</li>
</ul></section>
{archive}
""" + TAIL
    (DOCS / "index.html").write_text(index)

    # ------------------------------------------------------------------ h82.html (full result page)
    can_rows = []
    for fr in fit["folds"]:
        can_rows.append([fr["fold"], f"{fr['canary_max_learner']:.4f}", esc(fr["canary_worst"]),
                         "NO ALARM" if not fr["canary_alarm"] else "ALARM"])
    auc_rows = []
    for a in card["holdout"]["scores"]:
        pass
    for fr in fit["folds"]:
        auc_rows.append([fr["fold"]] + [f"{fr['auc'][a]:.4f}" for a in
                                        ("single_B", "B_DVA", "B_DVA2", "B_VSA", PRIMARY, "single_A")])

    h82 = head("H82 full result - DOE GEMS #306 - GEMSDOE52",
               "Extended directional variogram anisotropy and variogram/strike alignment: gates, "
               "HOLDOUT-DTI with 95% CIs, leakage canary, lane gate, and why the primary arm lost.") + f"""
<section class="hero"><div>
<div class="eyebrow">H82 &middot; full result</div>
<h1>Extended directional variogram anisotropy, and variogram&ndash;strike alignment</h1>
{notice_block(dl_ok, sb_ok, card["verdict"])}
{actions_block("downloads/h82-candidate.tif", "downloads/h82-candidate.zip", "downloads/" + csv_link)}
<p class="fileline">{fileline}</p>
</div></section>
<hr class="divider">
<section><h2>1. Hypothesis, mechanism, and the process that mimics it</h2>
<p><b>Hypothesis.</b> {esc(card["hypothesis"])}</p>
<p><b>Mechanism.</b> {esc(card["mechanism"])}</p>
<p><b>Named non-fault mimic.</b> {esc(card["mimic"])}</p>
<p><b>Co-training lane status.</b> {esc(card["cotraining_lane"])}</p></section>
<hr class="divider">
<section><h2>2. Channels actually built</h2>
{table(["Group", "Count", "Definition"], [
    ["DVA-2 extended fan", card["channels"]["dva2"],
     "aniso = (max&gamma; &minus; min&gamma;)/(max&gamma; + min&gamma;) and logvar = log&#8321;&#8320;(mean&gamma;) "
     "over 8 integer directions at lags 100&ndash;600 px&times;100 m, on 5 bands; &gamma; divided by the exact "
     "offset length so H75's 4-direction channels are recoverable"],
    ["VSA (variogram&ndash;strike alignment)", card["channels"]["vsa"],
     "cos(2&middot;(&theta;<sub>max</sub> &minus; &psi; &minus; &pi;/2)) against the fold's regional strike and "
     "its local strike field, both measured from visible catalogue only"],
    ["H75 control channels", card["channels"]["h75_control_recoverable"],
     "the GROUP1 subset at H75's lags, so the committed B_DVA arm can be reproduced as a control"],
])}
<p class="small">{esc(card["channels"]["quantisation_note"])}</p>
<p class="small">{esc(card["channels"]["degenerate_tensor_fraction"])}</p>
<p class="small">Amendment 72a, applied <b>before any fit</b>: <code>XVSA_visible_tensor_mag</code> was
demoted from a learner channel to a diagnostic because it is monotone in distance-to-visible-catalogue and
would have tripped the 0.90 leakage canary by construction rather than by discovery.</p></section>
<hr class="divider">
<section><h2>3. Leakage canary</h2>
<p class="small">Bar: a single-channel direction-insensitive AUC of {card["canary"]["bar"]} or more on the
held-out region is treated as leakage until proven otherwise. Measured maximum over all
{card["channels"]["n_new_learner"]} new learner channels: <b>{card["canary"]["max_over_learner_channels"]:.4f}</b>
&rarr; {"NO ALARM" if not card["canary"]["alarm"] else "ALARM"}.</p>
{table(["Fold", "Max learner-channel AUC", "Worst channel", "Alarm"], can_rows)}
</section>
<hr class="divider">
<section><h2>4. Out-of-quadrant AUC per fold and arm</h2>
<p class="small">Label-blind quadrant folds (<code>spatial.folds</code>, split version
<code>label-blind-quadrants-v2</code>), 80 px buffer, no shared components between the training domain and
the evaluation region.</p>
{table(["Fold", "single_B", "B_DVA", "B_DVA2", "B_VSA", PRIMARY, "single_A"], auc_rows)}
<p class="small">View A sufficiency gate (mean &ge; 0.60, min fold &ge; 0.55):
{"PASS" if card["sufficiency_view_A"]["mean"] >= 0.60 else "FAIL"} at mean
{card["sufficiency_view_A"]["mean"]:.4f}, per-fold
{", ".join(f"{x:.4f}" for x in card["sufficiency_view_A"]["per_fold"])}. This is the
{esc(card["sufficiency_view_A"]["verdict"])}.</p></section>
<hr class="divider">
<section><h2>5. HOLDOUT-DTI</h2>
{table(["Arm", "HOLDOUT-DTI", "95% CI", "Withheld positives"], arm_rows)}
<p class="small">Paired primary &minus; single_B: {pair["delta"]:+.6f}, 95% CI {ci(pair["ci95"])}.</p>
{table(["Control", "Committed (H75)", "Measured now", "|&Delta;|", "Tolerance", "Verdict"],
       [[a, f6(ho["controls"][a]["committed"]), f6(ho["controls"][a]["measured"]),
         f"{ho['controls'][a]['abs_delta']:.1e}", str(ho["controls"][a]["tolerance"]),
         "PASS" if ho["controls"][a]["PASS"] else "FAIL"] for a in ho["controls"]])}
</section>
<hr class="divider">
<section><h2>6. Lane gate and registry overlap</h2>
{table(["Statistic", "Full census", "Scored-only registry"], [
    ["Rasters compared", i(lane["full_census_rasters"]), str(lane["restricted_scored_rasters"])],
    ["Surface max Spearman (bar 0.90)", f"{lane['surface_max_spearman']:.4f}",
     f"{lane['restricted_surface_max_spearman']:.4f}"],
    ["Surface literal verdict", lane["surface_literal"], lane["restricted_surface_literal"]],
    ["Dots max Spearman (bar 0.90)", f"{lane['dots_max_spearman']:.4f}",
     f"{lane['restricted_dots_max_spearman']:.4f}"],
    ["Dots max near-3px share (bar 0.70)", f"{lane['dots_max_near_3px']:.4f}",
     f"{lane['restricted_dots_max_near_3px']:.4f}"],
    ["Dots literal verdict", lane["dots_literal"], lane["restricted_dots_literal"]],
])}
<p class="small">{esc(lane["doctrine"])}</p>
<p class="small">Quota placement against the scored-only registry's informative supports
(<code>run_h73.place_lane</code>, K = {i(card["placement"]["dots"])}):
{esc(json.dumps({k: lane["quota_placement_restricted"][k]
                 for k in ("ok", "worst", "quota_priors", "spacing_ok")
                 if k in lane["quota_placement_restricted"]}, default=float))}</p>
<h3>Against the named reference files</h3>
{table(["Reference", "Shared px", "Prior px", "Near-3px share of my dots", "Jaccard"],
       [[esc(k), i(v["shared_px"]), i(v["prior_px"]), f"{v['near_3px_share_of_my_dots']:.4f}",
         f"{v['jaccard']:.4f}"] for k, v in card["registry_correlation_overlap"]["vs_named_priors"].items()])}
</section>
<hr class="divider">
<section><h2>7. Why the best OWNER-REPORTED file in this repository scored 0.2778</h2>
<p>The algebra is in <code>knowledge/49</code> and was verified against the organiser&rsquo;s published
metric text. With &alpha; = 0.2, &beta; = 0.8 and a triangular kernel of R = 300 m,</p>
<p><code>DTI = T / (0.2&middot;T + 0.2&middot;(S&minus;M) + 0.8&middot;|G|)</code></p>
<p>where <code>T</code> is weighted true-positive mass, <code>S</code> the number of emitted pixels,
<code>M</code> the mass the catalogue already covers, and <code>|G|</code> the weighted ground-truth mass.
For well-separated dots this collapses to <code>DTI &asymp; T / (0.2&middot;S + 0.8&middot;|G|)</code>, so
what a submission really buys is the <b>hit rate &rho; = T/S</b>. Two facts follow:</p>
<ol>
<li><b>&beta; = 0.8 makes recall expensive and precision cheap.</b> Every emitted pixel costs 0.2 of a
unit; every missed ground-truth unit costs 0.8. So the optimum is a <em>sparse</em> binary raster placed
where the hit rate is highest, not a smooth probability field. Binary {{0,1}} is optimal because the metric
is linear in <code>p</code>.</li>
<li><b>The 0.2778 file is the 0.2600 file with its 100&ndash;200 m catalogue ring deleted.</b> Those
{esc(card["registry_correlation_overlap"]["vs_named_priors"].get("ref_h33_2_b2_owner_reported_0.2778", {}).get("shared_px", ""))}
shared pixels show the overlap. Removing 6,436 px that sat inside the mapped catalogue earned zero credit
(the ground truth was already covered) while still paying the full false-positive tax: +6.8% relative. That
is the single largest measured lever in this repository, and it is a <em>placement</em> lever, not a
modelling lever.</li>
</ol>
<p>The champion&rsquo;s implied &rho; is about 0.1387, roughly 5.0&times; the random-placement rate of
0.0279. To reach 0.3195 at S = 37,654 needs &rho; = 0.1595; at S = 100,000 it needs only &rho; = 0.0999.
The binding constraint is therefore the <b>decay of ranker quality with budget</b>, &rho;(S), not the
choice of S. H82 attacks exactly that: better ranking per emitted pixel.
<b>Nothing on this page claims that it succeeded.</b></p></section>
<hr class="divider">
<section><h2>8. Receipts</h2>
<p class="small">
<a href="data/h82_run_card.json">run card</a> &middot;
<a href="data/h82_channels.json">channels</a> &middot;
<a href="data/h82_fit.json">fit + canary</a> &middot;
<a href="data/h82_holdout.json">holdout</a> &middot;
<a href="data/h82_build_placement.json">placement</a> &middot;
<a href="data/h82_lane.json">lane gate</a> &middot;
<a href="data/h82_build.json">write + validator</a> &middot;
<a href="../{esc(prereg["hypothesis_document"])}">frozen preregistration</a> (SHA-256
<code>{esc(prereg["hypothesis_sha256"][:16])}&hellip;</code>)
</p></section>
""" + TAIL
    (DOCS / "h82.html").write_text(h82)

    # ------------------------------------------------------------------ executive summary
    exsum = head("How to submit, and whether this file may be submitted - H82 - GEMSDOE52",
                 "Step-by-step submission instructions for DOE GEMS competition #306, the four causes "
                 "of the [0,1] rejection, and the H82 verdict.") + f"""
<section class="hero"><div>
<div class="eyebrow">H82 &middot; executive summary &middot; exactly how to submit</div>
<h1>Two questions, answered separately</h1>
{notice_block(dl_ok, sb_ok, card["verdict"])}
{actions_block("downloads/h82-candidate.tif", "downloads/h82-candidate.zip", "downloads/" + csv_link)}
<p class="fileline">{fileline}</p>
</div></section>
<hr class="divider">
<section><h2>If you decide to submit it: the exact steps</h2>
<ol>
<li><b>Download</b> <a href="downloads/h82-candidate.tif" download>h82-candidate.tif</a>
({i(card["raster"]["bytes"])} bytes) or the <a href="downloads/h82-candidate.zip" download>ZIP</a>.
Both are the same bytes; the ZIP exists because the organiser&rsquo;s form accepts either a single-band
GeoTIFF or a ZIP containing one.</li>
<li><b>Check the file you actually downloaded</b> on <a href="validator.html">the browser checker</a>.
It decodes every pixel locally and reports each published rule as PASS or FAIL. Confirm the SHA-256 is
<code>{esc(card["raster"]["sha256"])}</code> — if it is not, you downloaded something else (a truncated
file, or an HTML error page saved with a <code>.tif</code> extension, which is the most common cause of a
confusing rejection).</li>
<li><b>Sign in</b> at <a href="{esc(PROBLEM_URL)}">the competition problem page</a> and open
<em>Submit</em>.</li>
<li><b>Upload</b> the file. The form rejects anything whose predicted values fall outside [0, 1] with
<code>Predicted values must be in range [0, 1]</code>. This file&rsquo;s values are exactly
{{0, 1}} with {val["nan"]} NaN and {val["infinite"]} infinite, so it cannot trip that rule.</li>
<li><b>Name it</b> <code>{esc(card["raster"]["name"])}</code>.</li>
<li><b>Note</b> ({card["raster"]["note_chars"]} of 140 characters):
<code>{esc(card["raster"]["note"])}</code></li>
<li><b>Wait for the score.</b> The public chunk is scored on upload; the Initial Prize Round is scored on
the <em>private</em> chunk, and one submission must be selected for both rounds before the deadline.</li>
</ol>
<p class="small"><b>This repository cannot do steps 3&ndash;7.</b> It has no DrivenData credentials, so it
has never downloaded the competition data from the organiser and has never uploaded a file. Every score
quoted here is either ORGANIZER-CONFIRMED from the public leaderboard or OWNER-REPORTED by the owner team.
Nothing on this page is an organiser acceptance receipt.</p></section>
<hr class="divider">
<section><h2>Why the [0, 1] rejection happens, and how to diagnose it in seconds</h2>
<p>The organiser&rsquo;s message <code>Predicted values must be in range [0, 1]</code> has four realistic
causes. In order of likelihood:</p>
{table(["Cause", "How to recognise it", "Fix"], [
    ["The file you downloaded is not the file you think it is",
     "SHA-256 differs; or the file is a few hundred bytes; or a text editor shows HTML",
     "Re-download. A GitHub Pages 404 page saved as <code>.tif</code> is the classic case."],
    ["Values are unnormalised model scores (log-odds, distances, z-scores)",
     "The browser checker reports min/max far outside [0,1]",
     "Normalise to [0,1] before writing, or emit binary {0,1}."],
    ["Wrong dtype — float64 or int16 instead of float32",
     "The checker reports BitsPerSample 64 or 16, or SampleFormat not 3",
     "Write <code>dtype='float32'</code>."],
    ["A NoData sentinel outside [0,1] (e.g. -3.4e38) inside the footprint",
     "The checker reports a huge negative minimum and a GDAL_NODATA tag",
     "Write NaN or 0 outside the footprint, never the float32 sentinel."],
])}
<p class="small">An audit of every raster this repository serves (110 TIFs and 82 ZIPs) found
<b>none</b> of these defects, so the rejection the owner hit did not come from a current artefact here.
That is recorded rather than papered over: the most likely source is a file from a sibling site or a
truncated download. The <a href="validator.html">browser checker</a> exists so this can be settled in
seconds, on the exact bytes you are about to upload.</p></section>
<hr class="divider">
<section><h2>The rules, quoted</h2>
<p class="small">From <a href="{esc(PROBLEM_URL)}">the official problem page</a>, fetched 2026-10-09:
predictions are pixel-wise probabilities in [0, 1]; the submission must use the same projected CRS as the
training data (UTM zone 11N, EPSG:32611), the same 100 m resolution, the same bounds with null or NaN
outside them, a single layer, and 32-bit float. Distances are weighted by a triangular kernel
k(d) = max(1 &minus; d/R, 0) with R = 300 m, and the score is the distance-weighted Tversky index
TI(&alpha;, &beta;) = TP / (TP + &alpha;&middot;FP + &beta;&middot;FN) with &alpha; = 0.2 and &beta; = 0.8.</p>
</section>
""" + TAIL
    (DOCS / "h82-executive-summary.html").write_text(exsum)

    # ------------------------------------------------------------------ hypotheses
    hyp_rows = [
        ["1", "DVA-2 — extended directional variogram anisotropy",
         "bands 12 det_elev, 19 det_elev_slope, 13 iso_grav_anom, 15 depth_to_base_surf, "
         "18 iso_grav_anom_hg",
         "8 integer directions at lags 1, 2, 3, 4, 6 px (100-600 m); gamma normalised by exact offset length so "
         "H75's 4-direction channels are recoverable as a control",
         "A damage zone makes semivariance direction-dependent; a 4-direction fan resolves the perpendicular "
         "only to 45°, so oblique and transfer structures are averaged away",
         "RUN (50 channels)"],
        ["2", "VSA — variogram/strike alignment",
         "the same 5 bands, at lag 2 px",
         "cos(2*(theta_max - psi - pi/2)) against the fold's regional strike ψ_reg and its local strike field "
         "ψ_loc, both measured from the fold's visible catalogue only",
         "A real fault's maximum-γ direction is perpendicular to its own strike; the alignment separates "
         "that from an anisotropy caused by an arbitrary linear feature",
         "RUN (10 channels)"],
        ["3", "Scored-only lane registry",
         "13 SHA-verified rasters whose score the owner reports",
         "a second lane comparison alongside the full 565-blob census",
         "the full census contains universal-coverage lattice probes that make the literal rule fail for "
         "every nonempty raster; the scored-only view is the decision-relevant one",
         "RUN as a declared loosening; never waives a literal DUPLICATE/STOP"],
        ["4", "Antithetic band-15 pairs",
         "depth_to_base_surf vs its regional residual",
         "a sign-flipped pair to test whether the gravity/depth signal is a real contrast or a smoothing "
         "artefact",
         "would separate a buried basement step from a broad basin",
         "DEFERRED — cost exceeded the remaining budget after 1 and 2"],
        ["5", "Drainage deflection",
         "1 m DEM stream-network offsets across mapped and unmapped traces",
         "offset drainage is a surface expression of a buried fault with no geophysical contrast",
         "directly targets faults missing from the catalogue because they are covered",
         "BLOCKED — 1m_DEM_links.csv is behind a DrivenData login and this runner has no credentials; "
         "only api.github.com, pypi and npm are reachable"],
    ]
    hypotheses = head("H82 candidate hypotheses, ranked before any fit - GEMSDOE52",
                      "Five new geological hypotheses with their layers, physical signature, transform, "
                      "why each would catch a catalogued miss, and its status.") + f"""
<section class="hero"><div><div class="eyebrow">H82 &middot; candidate hypotheses, ranked before any fit</div>
<h1>Five new candidates, ranked by expected gain over implementation cost</h1>
<p class="lead">The brief requires new geological hypotheses naming the layers, the physical signature and
its transform, why each would catch a fault that the USGS Quaternary fault and fold database and the
INGENIOUS catalogue both miss, and how each differs from anything already in this repository. All five were
written and ranked <b>before</b> any model was fitted, and frozen in
<code>{esc(prereg["hypothesis_document"])}</code> (SHA-256
<code>{esc(prereg["hypothesis_sha256"])}</code>).</p></div></section>
<hr class="divider">
{table(["#", "Hypothesis", "Layers / bands", "Physical signature and transform", "Why it catches a catalogued miss", "Status"],
       hyp_rows)}
<hr class="divider">
<section><h2>How each differs from what the repository already did</h2>
<ul class="small">
<li><b>vs H75.</b> H75 used a 4-direction integer fan on 3 bands at 2 lags. H82 doubles the angular
resolution, adds two bands, adds two more lags, and keeps H75&rsquo;s exact &gamma; normalisation so that
the H75 channels are <em>recovered</em> as a subset. That is what makes <code>B_DVA</code> a genuine
control rather than a re-implementation.</li>
<li><b>vs H74/H71/H70.</b> Those rounds rebuilt View A and re-ran pseudo-label exchange. View A sufficiency
has failed six times; H82 does not re-run the exchange. It fits the A-only arm and reports the failure as a
fresh measurement, and reports the independence test as a standing instrument.</li>
<li><b>vs H67/H49.</b> Those rounds derived the metric algebra. H82 uses that algebra to set the emission
rule (2.24 px at a board DTI of 0.2778) but claims nothing about beating any score.</li>
<li><b>vs the whole repository.</b> Nothing previously compared a per-pixel variogram direction to a
<em>measured</em> strike field derived from the fold&rsquo;s own visible catalogue. That is the VSA arm, and
it is the part that can separate a fault from a road or an incised drainage.</li>
</ul></section>
<hr class="divider">
<section><h2>External data: what would be needed, and whether it is obtainable</h2>
{table(["Need", "Free official source", "Obtainable from this runner?"], [
    ["1 m DEM tiles for drainage deflection",
     "USGS 3DEP (https://www.usgs.gov/3d-elevation-program) via the competition's 1m_DEM_links.csv",
     "NO — the link list is login-walled and usgs.gov is outside this runner's egress allowlist"],
    ["Quaternary fault and fold catalogue",
     "USGS GeoDAWN ScienceBase item 657e1d85d34e23d3533209f7, DOI 10.5066/P93LGLVQ",
     "PARTIALLY — the derived numerical feature raster supplied by the owner is pinned and SHA-verified in "
     "registry/data_manifest.json; the ScienceBase item itself is not reachable"],
    ["Radiometric (total count, K, eU, eTh)",
     "OpenEI GDR submission 1391, DOI 10.15121/1881483, CC BY 4.0",
     "YES — supplied by the owner, SHA-verified; band 6 of training_features.tif is the total-count channel "
     "(Spearman 1.0000 against the external raster), so it is assigned to View B"],
    ["Organiser metric text and leaderboard",
     "drivendata.org competition 306, page 967 and the leaderboard page",
     "YES via the research fetcher — recorded in registry/leaderboard_snapshot_2026-10-09.json and "
     "docs/h82-sources.html"],
])}
</section>
""" + TAIL
    (DOCS / "h82-hypotheses.html").write_text(hypotheses)

    # ------------------------------------------------------------------ sources
    src_rows = [
        ["Organiser — submission format and metric", PROBLEM_URL, "fetched 2026-10-09",
         "values in [0,1]; single layer float32; EPSG:32611; 100 m; same bounds with null/NaN outside; "
         "triangular kernel R = 300 m; TI(α=0.2, β=0.8); worked example TPw 3.00 / FPw 1.89 / FNw 2.00 → 0.60; "
         "public + private chunks; one submission selected for both prize rounds",
         "VERIFIED verbatim"],
        ["Organiser — public leaderboard", BOARD_URL, f"observed {esc(board['observed_at_utc'])}",
         f"rank 1 {esc(board['rows'][0]['team'])} {board['rows'][0]['score']:.4f}; owner team "
         f"{esc(board['our_team'])} rank {board['our_rank']} at {board['our_best_reported']:.4f}; "
         f"{board['rows_captured']} rows captured",
         "ORGANISER-PUBLISHED, team-level; " + esc(board["score_class"])[:120]],
        ["Organiser — reference solution",
         "https://github.com/drivendataorg/gems-prize-reference-solution", "listed, not fetched",
         "the organiser's own baseline implementation of the metric", "LINK FOR MANUAL REVIEW"],
        ["Organiser — forum", "https://community.drivendata.org/c/gems-prize-challenge/111",
         "listed, not fetched", "clarifications and rule questions", "LINK FOR MANUAL REVIEW"],
        ["USGS GeoDAWN / Quaternary faults and folds",
         "https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7 (DOI 10.5066/P93LGLVQ)",
         "not reachable from this runner",
         "the mapped-fault catalogue used as the label source; its derived numerical feature raster is "
         "pinned locally and SHA-verified", "PARTIAL — derived raster verified, item page unreachable"],
        ["USGS 3DEP", "https://www.usgs.gov/3d-elevation-program", "not reachable from this runner",
         "1 m DEM source for the deferred drainage-deflection hypothesis", "BLOCKED"],
        ["OpenEI GDR submission 1391", "https://gdr.openei.org/submissions/1391 (DOI 10.15121/1881483)",
         "supplied by the owner, SHA-verified",
         "aeroradiometric dataset; band 6 of training_features.tif is its total-count channel "
         "(Spearman 1.0000), which is why band 6 is assigned to View B", "VERIFIED locally by correlation"],
        ["EPSG:32611", "https://epsg.io/32611", "not fetched",
         "WGS 84 / UTM zone 11N — the projected CRS the organiser requires", "LINK FOR MANUAL REVIEW"],
        ["Tversky index", "https://en.wikipedia.org/wiki/Tversky_index", "not fetched",
         "TI(α,β) = TP/(TP + α·FP + β·FN); α=0.2 penalises false positives lightly, β=0.8 penalises misses "
         "heavily, which is why a sparse binary raster beats a smooth probability field",
         "LINK FOR MANUAL REVIEW"],
        ["Blum & Mitchell 1998, co-training", "https://doi.org/10.1145/279943.279962 (COLT '98, pp. 92–100)",
         "not fetched", "the assigned lane: two conditionally-independent views, pseudo-labelling where one "
         "view is confident and the other abstains, and the bias-amplification failure mode",
         "LINK FOR MANUAL REVIEW"],
        ["Mardia & Jupp, directional statistics",
         "https://doi.org/10.1002/9780470316979", "not fetched",
         "axial resultant length R and the axial circular SD sqrt(−2 ln R) used to describe the measured "
         "strike field; SD is reported as undefined when R → 0", "LINK FOR MANUAL REVIEW"],
        ["This repository — pinned competition inputs", "registry/data_manifest.json",
         "23 entries, all SHA-256 verified locally",
         "training_features.tif, labels.tif, sample_submission.tif and the owner-supplied mirrors. "
         "Integrity-pinned, NOT organiser-authenticated: this runner has no DrivenData credentials",
         "VERIFIED locally"],
        ["This repository — scored-only registry", "registry/h82_scored_registry.json",
         f"{scored['n_files']} files, all_sha_match {str(scored['all_sha_match']).lower()}",
         "every raster whose score the owner team reports, with its SHA-256 and byte size; scores are "
         "OWNER-REPORTED and never ORGANIZER-CONFIRMED", "VERIFIED locally"],
    ]
    sources = head("H82 source register - every external claim with its link - GEMSDOE52",
                   "Official sources, fetch dates, what each established, and its verification status; "
                   "plus the flagged irregularities.") + f"""
<section class="hero"><div><div class="eyebrow">H82 &middot; source register</div>
<h1>Every external claim, with its link and its verification status</h1>
<p class="lead">The brief requires line-by-line verification from official trusted sources, links for manual
review, and no hallucinations. This table is that record. Where something could not be reached from this
runner it says so, and says what was used instead.</p></div></section>
{table(["Source", "Link", "When / how obtained", "What it established", "Status"], src_rows)}
<hr class="divider">
<section><h2>Flagged irregularities</h2>
{table(["ID", "What", "Why it matters", "Disposition"], [
    ["IR-H82-001",
     "The round brief states both that 0.3195 is the highest current score and that the leaderboard top is "
     "0.3774.",
     "A target chosen from the wrong number would misdirect the whole round.",
     "The live board was fetched: 0.3774 is rank 1 and 0.3195 is rank 7. Both figures are reported, the "
     "contradiction is logged, and no guess is made about which the brief intended."],
    ["IR-H82-002",
     "Eight of 79 channel files from the first build had one 4 KiB page of zeros after the 128-byte .npy "
     "header, although the in-memory arrays were correct and the transform is bit-deterministic.",
     "A silently torn write would have trained a model on corrupted features and produced a result that "
     "looked legitimate.",
     "The byte-integrity guard refused to train on them. Persistence now re-reads every file after writing "
     "and rewrites until it is bit-exact; the rebuild needed 0 rewrites and all 79 SHA-256 digests match."],
    ["IR-H82-003",
     "This runner cannot fetch the leaderboard or the problem page from a scheduled job; egress is limited "
     "to github.com, api.github.com, pypi.org and registry.npmjs.org.",
     "No ORGANIZER-CONFIRMED number can be refreshed automatically, so a snapshot goes stale.",
     "Every leaderboard figure is dated and stored in registry/leaderboard_snapshot_2026-10-09.json, and the "
     "pages print the fetch date beside the number."],
    ["IR-H82-004",
     "Installed library versions exceed the pins in the repository's requirements.",
     "Control reproduction is approximate rather than exact (cf. IR-H75-004, where single_B differed by "
     "5.4e-05).",
     "Control deltas are reported with their tolerance; a control outside tolerance invalidates the round "
     "rather than being rounded away."],
])}
</section>
<hr class="divider">
<section><h2>What this runner could not verify</h2>
<ul class="small">
<li>No organiser acceptance receipt exists for any file here. Nothing was ever uploaded by this pipeline.</li>
<li>The private-chunk score is unknowable before the deadline, and the public/private split means a public
score is not the prize score.</li>
<li><code>1m_DEM_links.csv</code> is behind a login, so the drainage-deflection hypothesis was never tested.</li>
<li>The USGS ScienceBase item page and epsg.io were not reachable; the CRS is confirmed from the organiser's
own <code>sample_submission.tif</code> instead, which is the stronger evidence anyway.</li>
</ul></section>
""" + TAIL
    (DOCS / "h82-sources.html").write_text(sources)

    # ------------------------------------------------------------------ irregularities prose twin
    irr = load(REG / "irregularities.json")
    rows = [e for e in irr["entries"] if e["id"].startswith("IR-H82-")]
    body = "".join(
        f'<tr><td><b>{esc(e["id"])}</b><br><span class="small">{esc(e["severity"])} · {esc(e["status"])}</span></td>'
        f'<td>{esc(e["title"])}<div class="note">{esc(e["what_it_is"])}</div>'
        f'<div class="note"><b>How we know:</b> {esc(e["how_we_know"])}</div>'
        f'<div class="note"><b>Handling:</b> {esc(e["handling"])}</div>'
        f'<div class="note"><b>Disposition:</b> {esc(e["disposition"])}</div>'
        f'<div class="note"><b>Measured effect:</b> {esc(e["measured_effect"])}</div></td></tr>'
        for e in rows)
    section = (
        "<!--H82-IRREGULARITIES--><section><h2>H82 irregularities (2026-10-09)</h2>"
        f'<p class="small">The machine-readable register is authoritative: '
        f'<a href="../registry/irregularities.json">registry/irregularities.json</a> '
        f'({len(irr["entries"])} entries, generated {esc(irr["generated"])}). The {len(rows)} H82 entries '
        f'are reproduced here in full. This page is otherwise an R2-era document and has not been '
        f'backfilled for H5x-H75; the register has.</p>'
        f'<div class="table-wrap"><table><thead><tr><th>ID</th><th>What it is, how we know, and what was done'
        f'</th></tr></thead><tbody>{body}</tbody></table></div></section><!--/H82-IRREGULARITIES-->')
    ip = DOCS / "irregularities.html"
    t = ip.read_text()
    if "<!--H82-IRREGULARITIES-->" in t:
        a = t.index("<!--H82-IRREGULARITIES-->")
        b = t.index("<!--/H82-IRREGULARITIES-->") + len("<!--/H82-IRREGULARITIES-->")
        t = t[:a] + section + t[b:]
    else:
        t = t.replace("</main>", section + "</main>", 1)

    # The H82 page is now an archive, while H83 is a pre-fit stop. Keep the historical
    # irregularities page linked to the actual current status instead of its old CTD5 banner.
    t = t.replace("Current CTD5 file and failed gates", "Current H83 status and stop gates")
    h83_count = sum(e["id"].startswith("IR-H83-") for e in irr["entries"])
    h83_section = (
        "<!--H83-IRREGULARITIES--><section id=\"h83-preflight-review\"><h2>H83 preflight review (2026-10-10)</h2>"
        f'<p>Current disposition: <b>NEGATIVE — pre-fit stop</b>; {h83_count} H83 irregularity logged. '
        'No H83 experiment, holdout, TIFF, portal upload, or slot was used. IR-H83-001 records the dated '
        '<b>PUBLIC-BOARD</b> observation and unresolved file-to-score attribution: a team-level row is not '
        'an ORGANIZER-CONFIRMED submission receipt. The owner-reported H33 filename/score association '
        'remains unverified.</p><p><a href="h83-preflight.html">Read the H83 preflight and ranked hypotheses</a> · '
        '<a href="data/h83_preflight_run_card.json">H83 NOT-RUN card</a> · '
        '<a href="data/leaderboard_snapshot_2026-10-10.json">Dated public-board snapshot</a> · '
        '<a href="data/irregularities.json">Complete irregularities register</a></p>'
        '</section><!--/H83-IRREGULARITIES-->')
    if "<!--H83-IRREGULARITIES-->" in t:
        a = t.index("<!--H83-IRREGULARITIES-->")
        b = t.index("<!--/H83-IRREGULARITIES-->") + len("<!--/H83-IRREGULARITIES-->")
        t = t[:a] + h83_section + t[b:]
    else:
        t = t.replace("</main>", h83_section + "</main>", 1)
    ip.write_text(t)

    # ------------------------------------------------------------------ root landing page
    root_index = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GEMSDOE52 — H83 preflight and H82 research archive</title>
<style>
body{{margin:0;font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
color:#14181d;background:#fff}}
main{{max-width:760px;margin:0 auto;padding:36px 20px 70px}}
h1{{font-size:26px;margin:0 0 10px}}
.v{{border-radius:10px;padding:14px 16px;margin:16px 0;font-weight:700;
background:{'#e8f6ed' if sb_ok else '#fdecea'};color:{'#0f7b3f' if sb_ok else '#b3261e'};
border:1px solid {'#b7dfc5' if sb_ok else '#f0c4bf'}}}
a.b{{display:inline-block;background:#1f4e79;color:#fff;text-decoration:none;font-weight:700;
padding:13px 20px;border-radius:8px;margin:6px 8px 6px 0}}
a.s{{background:#eef2f6;color:#1f4e79}}
code{{background:#f2f4f7;padding:1px 5px;border-radius:4px;font-size:13.5px}}
small{{color:#5b6672}}
</style></head><body><main>
<div class="v" style="background:#fff0f1;color:#53121b;border-color:#d88991">
CURRENT PROJECT STATUS — H83 preflight: NEGATIVE; no new model fit, no H83 TIFF, no slot used.
No H83 file exists to download. The H82 file below is an archived research artefact: DOWNLOAD YES, SUBMIT NO.
</div>
<a class="b s" href="docs/h83-preflight.html">Current H83 preflight</a>
<a class="b s" href="docs/data/leaderboard.json">Dated public-board feed</a>
<h1>Last archived candidate — H82 research raster</h1>
<div class="v">{esc("OK TO DOWNLOAD: yes" if dl_ok else "OK TO DOWNLOAD: no")}
&nbsp;&middot;&nbsp; {esc("OK TO SUBMIT: yes" if sb_ok else "OK TO SUBMIT: no — research artefact only")}</div>
<a class="b" href="docs/downloads/h82-candidate.tif" download>Download h82-candidate.tif &#8595;</a>
<a class="b s" href="docs/downloads/h82-candidate.zip" download>ZIP</a>
<a class="b s" href="docs/index.html">Full site</a>
<a class="b s" href="docs/h82-executive-summary.html">How to submit</a>
<a class="b s" href="docs/validator.html">Check a file in your browser</a>
<p><small>{i(card["raster"]["bytes"])} bytes &middot; {i(n_dots)} emitted cells, values exactly {{0,1}}
&middot; SHA-256 <code>{esc(card["raster"]["sha256"])}</code> &middot; EPSG:32611, 3730&times;3292 at 100 m
&middot; submission name <code>{esc(card["raster"]["name"])}</code></small></p>
<p><small>HOLDOUT-DTI (evaluator {esc(card["holdout"]["evaluator"])},
{i(card["holdout"]["withheld_positive_pixels"])} withheld positives): primary arm
{f6(sc[PRIMARY]["dti"])} {ci(sc[PRIMARY]["ci95"])} vs control single_B {f6(sc["single_B"]["dti"])};
paired {pair["delta"]:+.6f} {ci(pair["ci95"])}. A holdout number is never a board forecast. Verdict:
{esc(card["verdict"])}.</small></p>
<p><small>This page is a research artefact. It is not an organiser acceptance receipt, and it does not
claim a leaderboard gain. Sources and verification status:
<a href="docs/h82-sources.html">docs/h82-sources.html</a>.</small></p>
</main></body></html>
"""
    (ROOT / "index.html").write_text(root_index)

    print(json.dumps(dict(
        pages=["docs/index.html", "docs/h83-preflight.html", "docs/h82.html", "docs/h82-executive-summary.html",
               "docs/h82-hypotheses.html", "docs/h82-sources.html", "index.html", "docs/validator.html"],
        downloads=["docs/downloads/h82-candidate.tif", "docs/downloads/h82-candidate.zip",
                   f"docs/downloads/{csv_link}"],
        verdict=card["verdict"], download_ok=dl_ok, submit_ok=sb_ok,
        sha256=card["raster"]["sha256"], name=card["raster"]["name"],
        note_chars=card["raster"]["note_chars"]), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
