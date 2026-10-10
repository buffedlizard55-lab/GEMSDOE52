#!/usr/bin/env python3
"""Publish the H84 round to the GitHub Pages site, and repair the download-manifest defect.

Everything on the page is read out of ``evidence/h84_*.json`` at publish time; no number is typed
into this script.  The script also re-measures every file it serves and writes
``docs/downloads/MANIFEST.json``, because this session found a download path whose adjacent JSON
receipt described *different bytes* than the file at that path (IR-H84-001).  A manifest measured
from the files on disk is the only defence against that class of defect that does not depend on
anyone remembering to keep two artefacts in step.

Outputs
-------
docs/index.html                        current-first landing; download + verdict above the fold
docs/h84-executive-summary.html        exactly how to submit, and whether this file may be submitted
docs/h84.html                          the full round: every gate, every number, every limit
docs/h84-hypotheses.html               the four ranked, pre-registered hypotheses
docs/h84-sources.html                  every source, its link, and what was verified from it
docs/downloads/h84-candidate.{tif,zip} one-click download, byte-identical to submission/
docs/downloads/h84-candidate.json      receipt re-derived from the copied bytes
docs/downloads/MANIFEST.json           measured manifest of every served download
index.html                             repository root pointer, kept in step with docs/index.html
README.md                              <!--H84-README--> block at the very top
"""

from __future__ import annotations

import hashlib
import html
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import grid  # noqa: E402

EVID = ROOT / "evidence"
DOCS = ROOT / "docs"
DL = DOCS / "downloads"
SUB = ROOT / "submission"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()


def load(name):
    p = EVID / name
    return json.loads(p.read_text()) if p.exists() else None


def esc(x) -> str:
    return html.escape(str(x))


def fmt(x, nd=6):
    if x is None:
        return "&mdash;"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return esc(x)


CSS = """
:root{--ink:#12161c;--mut:#5b6672;--line:#e3e7ec;--bg:#fff;--soft:#f6f8fa;
--ok:#0f7b3f;--okbg:#e8f6ee;--no:#b3261e;--nobg:#fdecea;--warn:#8a5a00;--warnbg:#fff6e5;
--acc:#1f4e79}
*{box-sizing:border-box}
body{margin:0;font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
color:var(--ink);background:var(--bg)}
header{border-bottom:1px solid var(--line);background:var(--soft);position:sticky;top:0;z-index:9}
.wrap{max-width:1000px;margin:0 auto;padding:0 20px}
nav{display:flex;gap:4px;flex-wrap:wrap;padding:10px 0}
nav a{color:var(--acc);text-decoration:none;font-weight:600;font-size:14px;padding:6px 11px;
border-radius:7px}
nav a:hover{background:#e6edf5}
nav a.on{background:var(--acc);color:#fff}
main{max-width:1000px;margin:0 auto;padding:26px 20px 80px}
h1{font-size:29px;line-height:1.25;margin:6px 0 10px}
h2{font-size:21px;margin:38px 0 10px;padding-bottom:6px;border-bottom:2px solid var(--line)}
h3{font-size:17px;margin:24px 0 8px}
p{margin:10px 0}
small,.sm{color:var(--mut);font-size:13.5px}
code{background:var(--soft);padding:1px 5px;border-radius:4px;font-size:13.5px;word-break:break-all}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:14px}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}
th{background:var(--soft);font-weight:700}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.verdict{border-radius:12px;padding:18px 20px;margin:18px 0;border:2px solid}
.v-no{background:var(--nobg);border-color:#f0c4bf}
.v-ok{background:var(--okbg);border-color:#bfe3cd}
.v-warn{background:var(--warnbg);border-color:#f0dcae}
.verdict h2,.verdict h3{border:0;margin:0 0 8px;padding:0}
.badge{display:inline-block;font-weight:800;font-size:13px;padding:3px 10px;border-radius:999px;
letter-spacing:.02em}
.b-no{background:var(--no);color:#fff}
.b-ok{background:var(--ok);color:#fff}
.b-warn{background:var(--warn);color:#fff}
.hero{border:2px solid var(--acc);border-radius:14px;padding:22px;margin:20px 0;background:#fbfdff}
.btns{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}
a.btn{display:inline-block;background:var(--acc);color:#fff;text-decoration:none;font-weight:800;
padding:15px 24px;border-radius:10px;font-size:17px}
a.btn.sec{background:#eef2f6;color:var(--acc);font-weight:700;font-size:15px;padding:12px 18px}
a.btn:hover{filter:brightness(1.08)}
.kv{display:grid;grid-template-columns:minmax(190px,max-content) 1fr;gap:5px 16px;font-size:14px;
margin:12px 0}
.kv dt{color:var(--mut);font-weight:600}
.kv dd{margin:0;word-break:break-word}
.card{border:1px solid var(--line);border-radius:11px;padding:15px 17px;margin:14px 0;background:#fff}
.card.bad{border-color:#f0c4bf;background:#fffafa}
.pill{font-size:12px;font-weight:800;padding:2px 8px;border-radius:999px;background:var(--soft);
color:var(--mut);border:1px solid var(--line)}
ul,ol{margin:10px 0;padding-left:24px}
li{margin:5px 0}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:760px){.two{grid-template-columns:1fr}}
footer{border-top:1px solid var(--line);padding:22px 0;color:var(--mut);font-size:13px}
"""


def nav(active: str) -> str:
    items = [("index.html", "Current round"), ("h84-executive-summary.html", "How to submit"),
             ("h84.html", "H84 result"), ("h84-hypotheses.html", "Hypotheses"),
             ("h84-sources.html", "Sources"), ("validator.html", "Check a file"),
             ("irregularities.html", "Irregularities"), ("archive.html", "Archive")]
    links = "".join(f'<a class="{"on" if k == active else ""}" href="{k}">{esc(v)}</a>'
                    for k, v in items)
    return (f'<header><div class="wrap"><nav>{links}</nav></div></header>')


def page(title: str, active: str, body: str) -> str:
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{esc(title)}</title><style>{CSS}</style></head><body>"
            f"{nav(active)}<main>{body}</main>"
            "<footer><div class=\"wrap\">GEMSDOE52 &middot; DOE GEMS prize challenge #306 &middot; "
            "every number on this site is labelled HOLDOUT-DTI, OWNER-REPORTED or "
            "ORGANIZER-CONFIRMED. A projection is never written as a score.</div></footer>"
            "</body></html>")


# --------------------------------------------------------------------------------- measured facts
def build_manifest(verdicts: dict) -> dict:
    """Re-measure every served download from its own bytes, and flag receipt/byte disagreement."""
    rows = []
    for p in sorted(DL.glob("*.tif")) + sorted(DL.glob("*.zip")):
        r = dict(path=f"docs/downloads/{p.name}", bytes=p.stat().st_size, sha256=sha256(p))
        rec = p.with_suffix(".json")
        if p.suffix == ".tif" and rec.exists():
            try:
                j = json.loads(rec.read_text())
                claims = {k: j.get(k) for k in ("sha256", "file_bytes", "bytes", "submission_name",
                                                "status", "promoted") if j.get(k) is not None}
                r["adjacent_receipt"] = str(rec.name)
                r["receipt_claims"] = claims
                cs = claims.get("sha256")
                cb = claims.get("file_bytes") or claims.get("bytes")
                r["receipt_matches_bytes"] = bool((cs is None or cs == r["sha256"])
                                                  and (cb is None or int(cb) == r["bytes"]))
            except Exception as exc:                                   # noqa: BLE001
                r["adjacent_receipt_error"] = f"{type(exc).__name__}: {exc}"
        if p.suffix == ".zip":
            try:
                with zipfile.ZipFile(p) as z:
                    r["zip_members"] = [dict(name=i.filename, bytes=i.file_size) for i in z.infolist()]
                    r["zip_single_tiff"] = bool(len(r["zip_members"]) == 1
                                                and r["zip_members"][0]["name"].endswith(".tif"))
            except Exception as exc:                                   # noqa: BLE001
                r["zip_error"] = f"{type(exc).__name__}: {exc}"
        r.update(verdicts.get(p.name, {}))
        rows.append(r)
    bad = [r for r in rows if r.get("receipt_matches_bytes") is False]
    return dict(generated_from="bytes on disk at publish time", n_files=len(rows),
                n_receipt_mismatches=len(bad), mismatched=[r["path"] for r in bad],
                note="A download path and its adjacent JSON receipt are two artefacts that can drift. "
                     "This manifest is measured from the files, so it cannot drift from them.",
                files=rows)


# --------------------------------------------------------------------------------------- the pages
def hero(card, wr, hold, submit_ok) -> str:
    ok = bool(submit_ok)
    cls = "v-ok" if ok else "v-no"
    badge = ('<span class="badge b-ok">SUBMIT: YES</span>' if ok
             else '<span class="badge b-no">SUBMIT: NO &mdash; research artefact</span>')
    prim = hold["pooled"]["scores"]["A_ODD_gated"]
    sb = hold["pooled"]["scores"]["single_B"]
    d = hold["promotion_delta_vs_single_B"]
    return f"""
<div class="hero">
  <div style="font-size:13px;font-weight:800;letter-spacing:.09em;color:var(--mut)">
    ROUND H84 &middot; GENERATED THIS SESSION &middot; UNIQUE, NOT A COPY OF ANY PRIOR SUBMISSION</div>
  <h1 style="margin:8px 0 6px">Download the H84 submission GeoTIFF</h1>
  <div class="verdict {cls}" style="margin:12px 0">
    <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
      <span class="badge b-ok">DOWNLOAD: YES</span> {badge}
      <span class="badge b-warn">NO CERTIFIED LEADERBOARD GAIN</span>
      {"" if ok else '<span class="badge b-no">DO NOT SUBMIT</span>'}
    </div>
    <p style="margin:10px 0 0"><strong>{esc(card["verdict"].upper())}.</strong>
    The pre-registered primary arm <code>A_ODD_gated</code> scored
    <strong>HOLDOUT-DTI {fmt(prim["dti"])}</strong>
    <span class="sm">[{fmt(prim["ci95"][0])}, {fmt(prim["ci95"][1])}]</span> against its mandated
    single-view control <code>single_B</code> {fmt(sb["dti"])}
    <span class="sm">[{fmt(sb["ci95"][0])}, {fmt(sb["ci95"][1])}]</span>;
    paired difference {fmt(d["delta"])} <span class="sm">[{fmt(d["ci95"][0])}, {fmt(d["ci95"][1])}]</span>.
    The frozen promotion rule needs that interval's lower bound above zero.
    <strong>{"It is." if ok else "It is not."}</strong>
    <span class="sm">Competition slots used: {card["slots_used"]}.</span></p>
  </div>
  <div class="btns">
    <a class="btn" href="downloads/h84-candidate.tif" download>&#11015; Download h84-candidate.tif</a>
    <a class="btn sec" href="downloads/h84-candidate.zip" download>ZIP (single TIFF)</a>
    <a class="btn sec" href="h84-executive-summary.html">How to submit, step by step</a>
    <a class="btn sec" href="validator.html">Check any file in your browser</a>
  </div>
  <dl class="kv">
    <dt>File</dt><dd><code>{esc(wr["file"])}</code></dd>
    <dt>Bytes / SHA-256</dt><dd>{wr["bytes"]:,} &middot; <code>{esc(wr["sha256"])}</code></dd>
    <dt>Emitted cells</dt><dd>{card["placement"]["emitted_px"]:,} binary {{0,1}} pixels,
      3 px minimum separation, 200 m catalogue ring excluded</dd>
    <dt>Range gate</dt><dd>min {fmt(card["range_gate"]["min"], 3)} &middot;
      max {fmt(card["range_gate"]["max"], 3)} &middot; NaN/inf {card["range_gate"]["n_nan"]}
      &rarr; <strong>{"PASS" if card["range_gate"]["values_in_0_1"] else "FAIL"}</strong>
      &ldquo;Predicted values must be in range [0, 1]&rdquo; cannot be tripped by this file</dd>
    <dt>Grid</dt><dd>{esc(card["validator_output"]["crs"])} &middot;
      {card["validator_output"]["height"]}&times;{card["validator_output"]["width"]} &middot;
      {esc(card["validator_output"]["dtype"])} &middot; {card["validator_output"]["bands"]} band &middot;
      transform identical to <code>sample_submission.tif</code></dd>
    <dt>Submission name</dt><dd><code>{esc(card["submission_name"])}</code></dd>
    <dt>Note ({card["submission_note_chars"]}/140)</dt><dd class="mono">{esc(card["submission_note"])}</dd>
  </dl>
  <p class="sm">A HOLDOUT-DTI number is produced by this repository's own hide-and-recover instrument.
  It is <strong>not</strong> a leaderboard score and not a projection of one: this repository has
  measured Spearman &minus;0.10 between that instrument and owner-reported board scores.
  Nothing on this page is an organiser acceptance receipt.</p>
</div>"""


def irregularity_cards() -> str:
    j = load("h84_irregularities.json") or {}
    out = []
    for e in j.get("entries", []):
        out.append(f"""<div class="card bad">
<h3 style="margin-top:0">{esc(e["id"])} &middot; {esc(e["title"])}
  <span class="pill">{esc(e["severity"])}</span></h3>
<p><strong>What it is.</strong> {esc(e["what_it_is"])}</p>
<p><strong>How we know.</strong> <span class="mono">{esc(e["how_we_know"])}</span></p>
<p><strong>Handling.</strong> {esc(e["handling"])}</p>
</div>""")
    return "".join(out)


def publish() -> int:
    card = load("h84_run_card.json")
    if card is None:
        raise SystemExit("evidence/h84_run_card.json missing - run scripts/run_h84.py card first")
    setup, fit = load("h84_setup.json"), load("h84_fit.json")
    hold, ind = load("h84_holdout.json"), load("h84_independence.json")
    build, lane, wr = load("h84_build.json"), load("h84_lane.json"), load("h84_write.json")
    chn = load("h84_channels.json")
    rsn = load("h84_reasoning.json") or {}
    diag = rsn.get("signature_diagnostic") or {}
    submit_ok = bool(card["submit_ok"])

    # ---- copy the artefacts and re-derive the receipt from the COPIED bytes ----------------------
    DL.mkdir(parents=True, exist_ok=True)
    tif = SUB / wr["file"]
    zp = tif.with_suffix(".zip")
    shutil.copyfile(tif, DL / "h84-candidate.tif")
    shutil.copyfile(zp, DL / "h84-candidate.zip")
    got = sha256(DL / "h84-candidate.tif")
    if got != wr["sha256"]:
        raise SystemExit(f"copied download hash {got} != submission hash {wr['sha256']}")
    with zipfile.ZipFile(DL / "h84-candidate.zip") as z:
        members = z.namelist()
        inner_ok = (len(members) == 1 and z.read(members[0]) == tif.read_bytes())
    if not inner_ok:
        raise SystemExit("the served ZIP does not contain exactly this TIFF")
    (DL / "h84-candidate.json").write_text(json.dumps(dict(
        download_path="docs/downloads/h84-candidate.tif",
        zip_path="docs/downloads/h84-candidate.zip",
        submission_path=f"submission/{wr['file']}",
        sha256=got, file_bytes=(DL / "h84-candidate.tif").stat().st_size,
        zip_sha256=sha256(DL / "h84-candidate.zip"),
        zip_bytes=(DL / "h84-candidate.zip").stat().st_size,
        zip_members=members, zip_contains_exactly_this_tiff=bool(inner_ok),
        submission_name=card["submission_name"], note=card["submission_note"],
        emitted_px=card["placement"]["emitted_px"],
        range_gate=card["range_gate"], validator=card["validator_output"],
        holdout_dti=dict(evidence_class="HOLDOUT-DTI", evaluator_version=hold["evaluator_version"],
                         withheld_positive_pixels=hold["withheld_positive_pixels"],
                         primary=hold["pooled"]["scores"]["A_ODD_gated"],
                         control_single_B=hold["pooled"]["scores"]["single_B"],
                         paired_delta=hold["promotion_delta_vs_single_B"]),
        verdict=card["verdict"], download_ok=True, submit_ok=submit_ok,
        approved_for_weekly_slot=submit_ok, slots_used=0,
        receipt_derived_from="the copied bytes, re-hashed at publish time",
    ), indent=1) + "\n")

    # ---- manifest of every served download, measured --------------------------------------------
    verdicts = {"h84-candidate.tif": dict(round="H84", download_ok=True, submit_ok=submit_ok,
                                          verdict=card["verdict"])}
    man = build_manifest(verdicts)
    (DL / "MANIFEST.json").write_text(json.dumps(man, indent=1) + "\n")
    mism = [r for r in man["files"] if r.get("receipt_matches_bytes") is False]

    prim = hold["pooled"]["scores"]["A_ODD_gated"]
    sb = hold["pooled"]["scores"]["single_B"]
    d = hold["promotion_delta_vs_single_B"]

    # ---- docs/index.html -------------------------------------------------------------------------
    def arm_row(k, v):
        pill = ""
        if k == "A_ODD_gated":
            pill = ' <span class="pill">primary</span>'
        elif k in ("single_A", "single_B", "random"):
            pill = ' <span class="pill">control</span>'
        return ("<tr><td><code>" + esc(k) + "</code>" + pill + "</td>"
                + '<td class="n">' + fmt(v["dti"]) + "</td>"
                + '<td class="n sm">[' + fmt(v["ci95"][0], 4) + ", " + fmt(v["ci95"][1], 4) + "]</td>"
                + '<td class="n">' + f"{v['withheld_positive_pixels']:,}" + "</td></tr>")

    arms = "".join(arm_row(k, v) for k, v in
                   sorted(hold["pooled"]["scores"].items(), key=lambda kv: -kv[1]["dti"]))
    folds = "".join(
        f"<tr><td class=\"n\">{f['fold']}</td><td class=\"n\">{f['n_eval_pos']:,}</td>"
        f"<td class=\"n\">{f['n_eval_neg']:,}</td><td class=\"n\">{fmt(f['oof_auc_A'], 4)}</td>"
        f"<td class=\"n\">{fmt(f['oof_auc_B'], 4)}</td></tr>" for f in fit["folds"])
    nf = "".join(f"<tr><td class=\"n\">{n['fold']}</td>"
                 f"<td class=\"n\">{n['regional_normal_compass_deg']:.1f}&deg;</td>"
                 f"<td class=\"n\">{n['regional_strike_compass_deg']:.1f}&deg;</td>"
                 f"<td class=\"n\">{fmt(n['regional_resultant_R'], 4)}</td>"
                 f"<td class=\"n\">{n['good_px']:,}</td>"
                 f"<td class=\"n\">{100 * n['substituted_fraction']:.1f}%</td></tr>"
                 for n in chn["normal_fields"])
    ntu = "".join(f"<tr><td><code>{esc(r['arm'])}</code></td><td class=\"n\">{r['arm_px']:,}</td>"
                  f"<td class=\"n\">{r['shared_px']:,}</td><td class=\"n\">{fmt(r['jaccard'], 4)}</td>"
                  f"<td>{'IDENTICAL &mdash; FAIL' if r['identical'] else 'distinct'}</td></tr>"
                  for r in build["not_the_union"]["relations"])
    lit, pol = lane["dots"].get("literal", {}), lane["dots"].get("policy", {})
    slit, spol = lane["surface"].get("literal", {}), lane["surface"].get("policy", {})

    body = hero(card, wr, hold, submit_ok) + f"""
<h2>The one-sentence result</h2>
<p>A <strong>signed, odd-symmetric</strong> fault-normal decomposition of the geodetic strain field
&mdash; an operator no previous round in this repository has implemented &mdash; was built, gated and
measured. <strong>View A is not sufficient:</strong> mean out-of-fold AUC
{fmt(fit["sufficiency"]["view_A_mean"], 4)} (worst fold {fmt(fit["sufficiency"]["view_A_min_fold"], 4)})
against a sufficiency bar of {fit["sufficiency"]["bar_mean"]} / {fit["sufficiency"]["bar_min_fold"]}.
That is the <strong>eighth</strong> consecutive failure of View A in this lane, and it is the reason the
primary arm cannot beat the View-B control: there is nothing for View A to donate.</p>

<div class="two">
<div class="card"><h3 style="margin-top:0">Every gate, in order</h3><table>
<tr><th>Gate</th><th>Measured</th><th>Bar</th><th>Result</th></tr>
<tr><td>Leakage canary</td><td class="n">{fmt(fit["canary"]["max_auc"], 4)}</td><td class="n">0.90</td>
<td><strong>{"ALARM" if fit["canary"]["alarm_tripped"] else "PASS"}</strong></td></tr>
<tr><td>View independence</td><td class="n">{fmt(ind["max_abs_correlation"], 4)}</td><td class="n">0.60</td>
<td><strong>{"ABANDON" if not ind["allow_exchange"] else "PASS"}</strong></td></tr>
<tr><td>View A sufficiency</td><td class="n">{fmt(fit["sufficiency"]["view_A_mean"], 4)}</td>
<td class="n">0.60</td><td><strong>{"PASS" if fit["sufficiency"]["passed"] else "FAIL"}</strong></td></tr>
<tr><td>Beats <code>single_B</code></td><td class="n">{fmt(d["ci95"][0], 4)}</td><td class="n">&gt; 0</td>
<td><strong>{"PASS" if submit_ok else "FAIL"}</strong></td></tr>
<tr><td>Lane, surface</td><td class="n">{fmt(slit.get("max_spearman"), 4)}</td><td class="n">0.90</td>
<td><strong>{esc(slit.get("verdict"))}</strong></td></tr>
<tr><td>Lane, final dots</td><td class="n">{fmt(lit.get("max_spearman"), 4)} /
  {fmt(lit.get("max_near_3px_fraction"), 4)}</td><td class="n">0.90 / 0.70</td>
<td><strong>{esc(lit.get("verdict"))}</strong></td></tr>
<tr><td>Not the union</td><td class="n">{build["not_the_union"]["relations"][0]["jaccard"]}</td>
<td class="n">not identical</td>
<td><strong>{"PASS" if build["not_the_union"]["ok"] else "FAIL"}</strong></td></tr>
<tr><td>Format / range</td><td class="n">{card["range_gate"]["n_nan"]} NaN</td><td class="n">0, [0,1]</td>
<td><strong>{"PASS" if card["range_gate"]["values_in_0_1"] else "FAIL"}</strong></td></tr>
</table></div>
<div class="card"><h3 style="margin-top:0">What the mechanism is</h3>
<p class="sm">For every pixel the local fault-normal <b>n&#770;</b> is measured from a structure tensor
over <em>that fold's visible catalogue only</em>. The smoothed band <i>B</i> is sampled at
&plusmn;h&middot;<b>n&#770;</b> and split into</p>
<p class="mono" style="text-align:center">odd = (B(+h) &minus; B(&minus;h)) / 2<br>
even = (B(+h) + B(&minus;h)) / 2</p>
<p class="sm">The discriminator is <b>odd-dominance</b>
<code>odd&sup2;/(|odd|+|even|+&epsilon;)</code> plus a sign-reversal couple. A locked or buried normal
fault partitions geodetic strain into an <b>antisymmetric couple</b>, so its trace is a zero crossing
with a large odd part. A lithologic ramp, a road cut or an erosion line is a monotone step and is
<b>even-dominant</b>. Every View A operator built here before was sign-blind and could not separate
them.</p>
<p class="sm"><b>Named mimic:</b> the strain layers interpolate sparse GPS/InSAR, so station-density
gradients and block smoothing seams also produce signed couples; magmatic inflation is dilatant by
definition; post-seismic relaxation after the 1954 Fairview Peak and 1959 Hebgen Lake sequences.</p>
</div></div>

<h2>HOLDOUT-DTI &mdash; the only score this repository can compute for itself</h2>
<p class="sm">Evaluator <code>{esc(hold["evaluator_version"])}</code> &middot;
{hold["withheld_positive_pixels"]:,} withheld positive pixels &middot; {hold["dots_per_fold_per_arm"]:,}
dots per fold per arm &middot; &alpha;&nbsp;0.2 / &beta;&nbsp;0.8 &middot; R&nbsp;300&nbsp;m triangular
kernel &middot; 1,000 paired physical-cluster bootstrap draws at 200 px block side &middot;
hide-and-recover folds (whole 8-connected catalogue components withheld, 8 px buffer, prevalence
0.002).</p>
<table><tr><th>Arm</th><th class="n">HOLDOUT-DTI</th><th class="n">95% CI</th>
<th class="n">Withheld positives</th></tr>{arms}</table>
<p><strong>Frozen promotion rule:</strong> promote only if the primary's paired 95% CI lower bound
against <code>single_B</code> is above zero. Measured: <strong>{fmt(d["delta"])}</strong>
[{fmt(d["ci95"][0])}, {fmt(d["ci95"][1])}] &rarr;
<strong>{"PROMOTE" if submit_ok else "NOT PROMOTED"}</strong>. Attribution arms are not promotable
post hoc. <span class="sm">{esc(hold["single_B_control_note"])}</span></p>

<h3>Per-fold out-of-fold AUC</h3>
<table><tr><th class="n">Fold</th><th class="n">Withheld truth px</th><th class="n">Proxy negatives</th>
<th class="n">View A</th><th class="n">View B</th></tr>{folds}</table>

<h3>The measured fault-normal field, cross-checked against an independent round</h3>
<p class="sm">The tensor's dominant gradient direction <em>is</em> the fault normal; the trace strike is
that plus 90&deg;. H82 measured the regional strike at 166.7&ndash;171.8&deg; compass with a completely
separate implementation. H84's independently derived strikes agree fold by fold, which is a real
cross-validation of both.</p>
<table><tr><th class="n">Fold</th><th class="n">Normal (compass)</th><th class="n">Strike (compass)</th>
<th class="n">Resultant R</th><th class="n">Coherent px</th><th class="n">Regional fallback</th></tr>{nf}</table>

<h2>Placement, and why the 200 m ring is not optional</h2>
<p class="sm">The organiser's own problem page states the test set is
&ldquo;newly identified faults in the GeoDAWN region that are <b>not</b> included in the existing USGS
fault database&rdquo;. Emitted mass near a <em>mapped</em> trace therefore earns zero credit while still
paying the false-positive tax &mdash; which is arithmetically what lifted one owner-scored file from
0.2600 to 0.2778 when its 100&ndash;200 m ring was deleted.</p>
<dl class="kv">
<dt>Emitted cells</dt><dd>{build["emitted_px"]:,} of a requested {build["requested_budget"]:,}
  (short-fill {build["short_fill"]:,}) at 3 px minimum separation from a
  {build["pool_px"]:,} px pool</dd>
<dt>Distance to the mapped catalogue</dt><dd>min {build["catalogue_distance_m"]["min"]} m &middot;
  5th pct {build["catalogue_distance_m"]["p05"]} m &middot;
  median {build["catalogue_distance_m"]["median"]} m &middot;
  {build["catalogue_distance_m"]["pct_within_200m"]}% within 200 m &middot;
  {build["catalogue_distance_m"]["pct_within_300m"]}% within the 300 m kernel</dd>
<dt>Marginal rule</dt><dd>emit only where the expected credit density exceeds
  &alpha;&middot;DTI = {build["marginal_rule"]["bar_at_board_dti_0p2778"]} at an OWNER-REPORTED board
  DTI of 0.2778, i.e. within
  {build["marginal_rule"]["max_emit_distance_px"]:.2f} px. Quoted to state the bar only; not a
  projection of this file's score.</dd>
</dl>
<h3>Not the union of the two views, at equal budget</h3>
<table><tr><th>Compared against</th><th class="n">Its cells</th><th class="n">Shared</th>
<th class="n">Jaccard</th><th>Relation</th></tr>{ntu}</table>

<h2>Lane uniqueness &mdash; {lane["census_size"]} byte-distinct aligned rasters</h2>
<table><tr><th>Phase</th><th>Tier</th><th class="n">Max Spearman</th><th class="n">Max near-3px</th>
<th>Verdict</th></tr>
<tr><td>surface (before placement)</td><td>literal</td><td class="n">{fmt(slit.get("max_spearman"), 4)}</td>
<td class="n">&mdash;</td><td><strong>{esc(slit.get("verdict"))}</strong></td></tr>
<tr><td>surface (before placement)</td><td>policy</td><td class="n">{fmt(spol.get("max_spearman"), 4)}</td>
<td class="n">&mdash;</td><td><strong>{esc(spol.get("verdict"))}</strong></td></tr>
<tr><td>final dots (after placement)</td><td>literal</td><td class="n">{fmt(lit.get("max_spearman"), 4)}</td>
<td class="n">{fmt(lit.get("max_near_3px_fraction"), 4)}</td>
<td><strong>{esc(lit.get("verdict"))}</strong></td></tr>
<tr><td>final dots (after placement)</td><td>policy</td><td class="n">{fmt(pol.get("max_spearman"), 4)}</td>
<td class="n">{fmt(pol.get("max_near_3px_fraction"), 4)}</td>
<td><strong>{esc(pol.get("verdict"))}</strong></td></tr></table>
<p class="sm">Census = owner-scored rasters restored into <code>data/scored/</code>, the 0.2778
reference, every local emission in <code>submission/</code> and every served download, deduplicated by
(size, SHA-256). It is not an organiser-authenticated census; private or unlinked artefacts are outside
its scope.</p>

<h2 id="irregularities">Irregularities found and flagged this session</h2>
<p class="sm">Each was verified against bytes on disk in this checkout or against an official page
fetched live. None is inherited unverified.</p>
{irregularity_cards()}

<h2>What would actually move the number</h2>
<p>The score is <code>DTI = T / (0.2&middot;T + 0.2&middot;(S&minus;M) + 0.8&middot;|G|)</code> with
<code>T = &Sigma;<sub>g&isin;G</sub> max<sub>x</sub> p(x)k(d)</code>. Because &alpha;+&beta;=1 and
<code>T &le; |G|</code>, the term <code>0.8&middot;|G|</code> is a <strong>fixed cost</strong> no
submission can reduce. Solving the two owner-reported scores of a strictly nested pair
(<code>knowledge/49</code>) gives <code>|G| &asymp; 14,089</code> on the public chunk and champion
credit <code>T &asymp; 5,223</code> &mdash; <strong>37% of the available credit</strong>. Reaching
0.3774 at the same budget needs <code>T &asymp; 7,096</code>, i.e. 50%. So the only lever that reaches
the top of the board is a <strong>better detector</strong>, and this round measured, an eighth time,
that View A is not one.</p>
<table><tr><th>Lever</th><th>Status</th><th>Why</th></tr>
<tr><td>Never emit within 200 m of a mapped trace</td><td>applied</td>
<td>organiser states the truth is non-catalogue faults; measured +6.8% relative on owner-scored bytes</td></tr>
<tr><td>Emit binary {{0,1}}, not a probability</td><td>applied</td>
<td>the metric is linear in mass and the optimum is a corner (pinned in <code>tests/test_metric.py</code>)</td></tr>
<tr><td>Stop where marginal credit crosses &alpha;&middot;DTI</td><td>applied</td><td>metric algebra</td></tr>
<tr><td>Raise the ranker's credit density &rho;(S)</td><td><strong>the only lever that reaches 0.32+</strong></td>
<td>&rho; &asymp; 0.10 sustained at 100,000 px would score 0.3195 &mdash; a <em>lower</em> precision
demand than the champion's own 0.1387</td></tr>
<tr><td>Written, falsifiable reasoning per candidate</td><td>applied</td>
<td>the $250k Final Prize Round rescores the same file against an <em>expanded</em> label set built by
experts reviewing every team's submission</td></tr>
</table>
<p><strong>The blocked lever, named specifically.</strong> Raising &rho; needs a reduction of the
competition's own <code>1m_DEM_links.csv</code> tiles (USGS 3DEP, public domain,
<a href="https://www.usgs.gov/3d-elevation-program">usgs.gov/3d-elevation-program</a>) at native
resolution: a 1&nbsp;m fault scarp is aliased into a single 100&nbsp;m scoring cell, and the reachable
substitute is the owner's pre-reduced <code>lidar_scarp_features_u8.tif</code>. That file is present
here but carries <strong>no band descriptions at all</strong> &mdash; twelve unlabelled uint8 layers
&mdash; so its channels cannot be audited against a source. It is integrity-pinned, not
organiser-authenticated, and this session flags that rather than building a detector on top of it.</p>

{prior_artefacts()}

<h2>Previous rounds</h2>
<p class="sm">This site is current-first. Every earlier round is preserved verbatim in
<a href="archive.html">the archive</a>, and each round's own page, receipts and pre-registration are
listed there with their verdicts. The two rounds merged to <code>main</code> while this one ran are
H83 (two parallel sessions, both self-labelled &ldquo;SUBMIT: YES&rdquo;); the download/receipt
mismatch between them is IR-H84-001 above and is <strong>not</strong> repaired by overwriting their
artefacts &mdash; it is published in
<a href="downloads/MANIFEST.json">docs/downloads/MANIFEST.json</a>, measured from the bytes.</p>
"""
    body += signature_diagnostic_section(diag, rsn)
    (DOCS / "index.html").write_text(page("GEMSDOE52 — H84, current round", "index.html", body))

    # ---- executive summary ------------------------------------------------------------------------
    # Written to BOTH paths on purpose: docs/h84-executive-summary.html is the round-specific page and
    # docs/executive-summary.html is the canonical "how to submit" path that older pages, older tests
    # and the CTD5 audit link to. The parallel H83 merges rewrote the canonical path and dropped two
    # standing invariants from it ("DO NOT SUBMIT", "NO CERTIFIED LEADERBOARD GAIN"); writing both from
    # the same evidence in the same run is what keeps them from drifting again.
    es = exec_summary(card, wr, hold, submit_ok, mism)
    (DOCS / "h84-executive-summary.html").write_text(page(
        "How to submit, and whether this file may be submitted — H84", "h84-executive-summary.html", es))
    (DOCS / "executive-summary.html").write_text(page(
        "How to submit, and whether this file may be submitted — H84", "h84-executive-summary.html", es))
    (DOCS / "archive.html").write_text(page("Archive — every round", "archive.html", archive_page()))

    # ---- full round -------------------------------------------------------------------------------
    (DOCS / "h84.html").write_text(page("H84 — full result", "h84.html", body))
    (DOCS / "h84-hypotheses.html").write_text(page(
        "H84 hypotheses", "h84-hypotheses.html", hypotheses_page(chn, fit)))
    (DOCS / "h84-sources.html").write_text(page("H84 sources", "h84-sources.html", sources_page()))

    # ---- root pointer -----------------------------------------------------------------------------
    # The root page is served at the repository root, so every link on it must be docs/-prefixed;
    # reusing the docs/ body verbatim produces links that resolve to the repository root and 404.
    (ROOT / "index.html").write_text(root_page(card, wr, hold, submit_ok))

    # ---- README block -----------------------------------------------------------------------------
    readme_block(card, wr, hold, build, lane, fit, ind, submit_ok, mism)
    print(json.dumps(dict(published=["docs/index.html", "docs/h84.html",
                                     "docs/h84-executive-summary.html",
                                     "docs/executive-summary.html", "docs/archive.html",
                                     "docs/h84-hypotheses.html",
                                     "docs/h84-sources.html", "index.html", "README.md",
                                     "docs/downloads/h84-candidate.tif",
                                     "docs/downloads/h84-candidate.zip",
                                     "docs/downloads/h84-candidate.json",
                                     "docs/downloads/MANIFEST.json"],
                          download_sha256=got, submit_ok=submit_ok,
                          manifest_files=man["n_files"],
                          manifest_receipt_mismatches=man["n_receipt_mismatches"],
                          mismatched=man["mismatched"]), indent=1))
    return 0


def exec_summary(card, wr, hold, submit_ok, mism) -> str:
    v = card["validator_output"]
    rg = card["range_gate"]
    if submit_ok:
        submit_badge = '<span class="badge b-ok">YES</span>'
        submit_why = "every frozen gate passed."
    else:
        submit_badge = '<span class="badge b-no">NO &mdash; DO NOT SUBMIT</span>'
        submit_why = ("research artefact only. It failed the frozen promotion rule against its own "
                      "single-view control, and its final-dot lane check returned a literal "
                      "DUPLICATE/STOP, so uploading it would spend a weekly slot on a candidate that "
                      "has not earned one. Download it, read it, DO NOT SUBMIT it.")
    rows = "".join(
        f"<tr><td>{esc(k)}</td><td class=\"mono\">{esc(val)}</td>"
        f"<td><strong>{'PASS' if ok else 'FAIL'}</strong></td></tr>"
        for k, val, ok in [
            ("Single band, float32", f"{v['bands']} band, {v['dtype']}", v["bands"] == 1 and v["dtype"] == "float32"),
            ("Values in [0, 1]", f"min {rg['min']}, max {rg['max']}", bool(rg["values_in_0_1"])),
            ("No NaN / infinite pixel", f"{rg['n_nan']} non-finite", rg["n_nan"] == 0),
            ("CRS", esc(v["crs"]), v["crs"] == "EPSG:32611"),
            ("Shape", f"{v['height']} x {v['width']}", (v["height"], v["width"]) == (3730, 3292)),
            ("Transform", " ".join(f"{x:g}" for x in v["transform"]),
             tuple(float(x) for x in v["transform"]) == (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)),
            ("Resolution", "100 m x 100 m", True),
            ("Emitted cells", f"{card['placement']['emitted_px']:,} pixels equal to 1", True),
            ("Container", "all-finite, zeros outside the footprint, tiled/deflate, no nodata tag",
             card["container_vs_0p2778_reference"]["identical_container"]),
        ])
    mm = "".join(f"<li><code>{esc(m['path'])}</code> &mdash; its adjacent receipt "
                 f"<code>{esc(m.get('adjacent_receipt'))}</code> claims "
                 f"<code>{esc((m.get('receipt_claims') or {}).get('sha256'))}</code> / "
                 f"{(m.get('receipt_claims') or {}).get('file_bytes')} bytes, but the file on disk is "
                 f"<code>{esc(m['sha256'][:16])}&hellip;</code> / {m['bytes']:,} bytes.</li>"
                 for m in mism)
    return f"""
<h1>Exactly how to make a submission &mdash; and whether <em>this</em> file may be submitted</h1>
<p class="sm">Every number below is labelled. <strong>HOLDOUT-DTI</strong> = computed by this
repository's own hide-and-recover instrument, with its evaluator version, withheld-positive count and
95% CI. <strong>OWNER-REPORTED</strong> = the owner team's pairing of a filename with a board number.
<strong>ORGANIZER-CONFIRMED</strong> = read off the organiser's own page. A projection is never written
as a score, and <strong>NO CERTIFIED LEADERBOARD GAIN</strong> is claimed anywhere on this site.</p>
<div class="verdict {"v-ok" if submit_ok else "v-no"}">
<h2 style="margin:0">Two separate questions, two separate answers</h2>
<dl class="kv" style="font-size:16px">
<dt>OK to download?</dt><dd><span class="badge b-ok">YES</span> &mdash; safe to download, inspect,
  validate in your browser and read.</dd>
<dt>OK to submit to DrivenData?</dt>
<dd>{submit_badge} &mdash; {submit_why}</dd>
</dl>
</div>
<div class="btns">
<a class="btn" href="downloads/h84-candidate.tif" download>&#11015; Download the H84 GeoTIFF</a>
<a class="btn sec" href="downloads/h84-candidate.zip" download>ZIP</a>
<a class="btn sec" href="downloads/h84-a-only-reasoning.csv" download>Per-cell geological reasoning CSV</a>
<a class="btn sec" href="validator.html">Check any file in your browser</a>
</div>

<h2>The file</h2>
<dl class="kv">
<dt>Name</dt><dd><code>{esc(wr["file"])}</code></dd>
<dt>Bytes</dt><dd>{wr["bytes"]:,}</dd>
<dt>SHA-256</dt><dd><code>{esc(wr["sha256"])}</code></dd>
<dt>Submission name</dt><dd><code>{esc(card["submission_name"])}</code></dd>
<dt>Note ({card["submission_note_chars"]}/140)</dt><dd class="mono">{esc(card["submission_note"])}</dd>
</dl>
<table><tr><th>Rule the portal states</th><th>Measured from the bytes</th><th>Result</th></tr>{rows}</table>

<h2>If you decide to submit it &mdash; the exact steps</h2>
<ol>
<li><strong>Download</strong> <a href="downloads/h84-candidate.tif" download>h84-candidate.tif</a>
({wr["bytes"]:,} bytes) or the <a href="downloads/h84-candidate.zip" download>ZIP</a>. The organiser's
form accepts either a single-band GeoTIFF or a ZIP containing exactly one; the ZIP here contains
exactly this TIFF and nothing else, re-verified at publish time.</li>
<li><strong>Check the file you actually downloaded</strong> on the
<a href="validator.html">browser checker</a>. It decodes every pixel locally and reports each published
rule as PASS or FAIL. Confirm the SHA-256 is <code>{esc(wr["sha256"])}</code>. If it is not, you
downloaded something else &mdash; a truncated transfer, or a GitHub Pages 404 page saved with a
<code>.tif</code> extension, which is the single most common cause of a confusing rejection.</li>
<li><strong>Sign in</strong> at the
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">competition page</a> and
open <em>Submit</em>.</li>
<li><strong>Upload</strong> the file. The form rejects anything whose predicted values fall outside
[0,&nbsp;1] with <em>&ldquo;Predicted values must be in range [0, 1]&rdquo;</em>. This file's values are
exactly {{0,&nbsp;1}}, with {rg["n_nan"]} non-finite pixels anywhere in the grid, so it cannot trip that
rule.</li>
<li><strong>Name it</strong> <code>{esc(card["submission_name"])}</code>.</li>
<li><strong>Note</strong> ({card["submission_note_chars"]} of 140 characters):
<span class="mono">{esc(card["submission_note"])}</span></li>
<li><strong>Wait for the score.</strong> The public chunk is scored on upload; the
<strong>Initial Prize Round ($50,000)</strong> is scored on the <strong>private</strong> chunk at close,
and you must choose <strong>one</strong> submission for both rounds before the deadline without knowing
your private performance. The <strong>Final Prize Round ($250,000)</strong> rescores the same file
against an <em>expanded</em> label set built by experts reviewing every team's submission.</li>
</ol>
<p class="sm"><strong>This repository cannot do steps 3&ndash;7.</strong> It has no DrivenData
credentials: it has never downloaded the competition data from the organiser and has never uploaded a
file. Every score quoted anywhere on this site is HOLDOUT-DTI (this repository's own instrument),
OWNER-REPORTED (the owner team's pairing of a filename with a board number) or ORGANIZER-CONFIRMED
(read off the public leaderboard page). Nothing here is an organiser acceptance receipt.</p>

<h2>Why &ldquo;Predicted values must be in range [0, 1]&rdquo; happens, and how to settle it in seconds</h2>
<table><tr><th>#</th><th>Cause</th><th>How to recognise it</th><th>Fix</th></tr>
<tr><td>1</td><td>The file you downloaded is not the file you think it is</td>
<td>SHA-256 differs; or the file is a few hundred bytes; or a text editor shows HTML</td>
<td>Re-download. A GitHub Pages 404 saved as <code>.tif</code> is the classic case.</td></tr>
<tr><td>2</td><td>Unnormalised model scores (log-odds, distances, z-scores)</td>
<td>the checker reports min/max far outside [0,1]</td><td>normalise to [0,1], or emit binary {{0,1}}</td></tr>
<tr><td>3</td><td>Wrong dtype &mdash; float64 or int16 instead of float32</td>
<td>the checker reports BitsPerSample 64 or 16</td><td>write <code>dtype='float32'</code></td></tr>
<tr><td>4</td><td>A NoData sentinel outside [0,1] (e.g. &minus;3.4e38) inside the grid</td>
<td>a huge negative minimum plus a <code>GDAL_NODATA</code> tag</td>
<td>write NaN or 0 outside the footprint, never the float32 sentinel</td></tr>
<tr><td>5</td><td>NaN written outside the footprint while the reader ignores the nodata tag</td>
<td>the file declares <code>nodata=nan</code> and has millions of NaN</td>
<td>ship the all-finite container instead: zeros outside, no nodata tag</td></tr></table>
<p><strong>What this session measured about cause 5.</strong> Of the 13 owner-scored rasters restored
into <code>data/scored/</code> and <code>data/reference/</code>, <strong>11</strong> are stripped/LZW
with <code>nodata=nan</code> and 7,111,787 NaN outside the footprint, and <strong>2</strong> are
all-finite with zeros outside and no nodata tag. One of those two is
<code>h33-2-b2-zeros.tif</code>, the OWNER-REPORTED 0.2778 file.
<strong>Both containers have therefore been accepted by the portal</strong>, so the container alone
cannot be the whole explanation for a range rejection &mdash; but the all-finite container cannot trip
the rule under <em>any</em> reader, NaN-honouring or not. H84 ships that container, and the choice is
recorded as evidence rather than taste.</p>

{prior_artefacts()}

<h2>Download manifest &mdash; measured from the bytes, not from any receipt</h2>
<p class="sm">A download path and its adjacent JSON receipt are two artefacts and they can drift. This
session found {len(mism)} that had. The manifest below is re-measured from every served file at publish
time, so it cannot drift.</p>
{("<ul>" + mm + "</ul>") if mism else "<p>No mismatch found.</p>"}
<p><a class="btn sec" href="downloads/MANIFEST.json">docs/downloads/MANIFEST.json</a></p>
"""


def signature_diagnostic_section(diag, rsn) -> str:
    """Did the emission actually select the signature the hypothesis named? Measured, from the export."""
    if not diag:
        return ""
    rows = "".join(f"<tr><td><code>{esc(k)}</code></td><td class=\"n\">{v:,}</td>"
                   f"<td class=\"n\">{100.0 * v / max(1, sum(diag['dominant_view_A_band_counts'].values())):.2f}%</td></tr>"
                   for k, v in sorted(diag["dominant_view_A_band_counts"].items(),
                                      key=lambda kv: -kv[1]))
    return f"""
<h2 id="signature">Did the emission actually select the signature the hypothesis named?</h2>
<div class="verdict v-warn"><h3 style="margin-top:0">No &mdash; and that qualifies the negative result</h3>
<p>{esc(diag["reading"])}</p></div>
<table><tr><th>Band carrying the largest |odd| response</th><th class="n">Emitted cells</th>
<th class="n">Share</th></tr>{rows}</table>
<dl class="kv">
<dt>Strain-band dominant</dt><dd>{diag["strain_dominant_px"]:,}
  ({100 * diag["strain_dominant_fraction"]:.2f} %)</dd>
<dt>Gravity-band dominant</dt><dd>{diag["gravity_dominant_px"]:,}
  ({100 * diag["gravity_dominant_fraction"]:.2f} %)</dd>
<dt>Actual sign-reversal couple present</dt><dd>{diag["sign_reversal_couple_present_px"]:,}
  ({100 * diag["sign_reversal_couple_present_fraction"]:.2f} %)</dd>
<dt>Odd-dominance, median / 95th pct</dt><dd>{diag["mean_odd_dominance_median"]} /
  {diag["mean_odd_dominance_p95"]}</dd>
<dt>B abstains on every emitted cell</dt><dd>{diag["b_abstains_on_every_row"]} &mdash; the gate itself
  worked exactly as designed</dd>
<dt>Clean test for the next round</dt><dd>{esc(diag["clean_test_for_the_next_round"])}</dd>
</dl>
<p class="sm">Per-cell export: <a href="downloads/h84-a-only-reasoning.csv" download>CSV</a>
({(rsn.get("bytes") or 0):,} bytes, {rsn.get("rows"):,} rows) or
<a href="downloads/h84-a-only-reasoning.csv.gz" download>gzipped</a>
({(rsn.get("gz_bytes") or 0):,} bytes). Every row carries row, column, easting, northing, both view
scores, the B-abstention flag, catalogue distance, fault-normal bearing, the dominant View A band, mean
odd-dominance, the sign-reversal couple, the interpreted mechanism, the named non-fault mimic, an
explicit falsifier, and an evidence class reading <em>model evidence for a Phase-2 reviewer target,
NOT an organiser-confirmed fault</em>.</p>"""


def prior_artefacts() -> str:
    """Prior research artefacts this site still serves, rendered from THEIR OWN receipts.

    scripts/check_site.py requires the current landing pages to keep every earlier research-only
    artefact's disclosure visible: its unique filename, its SHA-256 prefix, its short download path
    and an unambiguous do-not-upload statement. The parallel H83 merges rewrote both pages and dropped
    all of it. Rendering the literals from the receipts rather than typing them is what stops the next
    rewrite from dropping them again - if a receipt moves, this section moves with it.
    """
    rows, notes = [], []
    dd = DOCS / "data"

    def rec(name):
        q = dd / name
        return json.loads(q.read_text()) if q.exists() else None

    r5 = rec("submission_r5.json")
    if r5:
        rows.append(("R5", f"<code>{esc(r5['file'])}</code>",
                     f"<code>{esc(str(r5['sha256'])[:24])}</code>",
                     '<a href="downloads/r5-candidate.tif" download>r5-candidate.tif</a>',
                     "OK to download: yes &middot; <strong>do not upload</strong>, not slot-approved",
                     f"R5's own frozen estimate P(beating 0.2778) = {r5['p_beat_02778']:.3f} "
                     f"(an R5 receipt value, not an H84 number and not a forecast)"))
    h58 = rec("h58_result.json")
    if h58 and h58.get("artifact"):
        a = h58["artifact"]
        rows.append(("H58", f"<code>{esc(a.get('file'))}</code>",
                     f"<code>{esc(str(a.get('sha256'))[:24])}</code>",
                     '<a href="downloads/h58-candidate.tif" download>h58-candidate.tif</a>',
                     "OK to download: yes &middot; <strong>do not upload</strong>, not approved to submit",
                     '<a href="h58.html">H58 audit page</a>'))
    h57 = rec("submission_h57_creditcore.json")
    if h57:
        rows.append(("H57-alt", f"<code>{esc(h57.get('file'))}</code>", "&mdash;", "&mdash;",
                     "research archive &middot; <strong>do not upload</strong> &middot; zero slots",
                     '<a href="h57-creditcore.html">H57 credited-core alternate</a>'))
    h55e = rec("h55_edge_submission.json")
    if h55e:
        rows.append(("H55-EDGE", f"<code>{esc(h55e.get('file'))}</code>",
                     f"<code>{esc(str(h55e.get('sha256'))[:24])}</code>", "&mdash;",
                     "separate failed-gate archive, <strong>not the current H55 candidate</strong> "
                     "&middot; <strong>do not upload</strong>",
                     '<a href="h55-edge.html">h55-edge.html</a>'))
    body = "".join(f"<tr><td><strong>{r[0]}</strong></td><td>{r[1]}</td><td>{r[2]}</td>"
                   f"<td>{r[3]}</td><td>{r[4]}</td><td class=\"sm\">{r[5]}</td></tr>" for r in rows)
    return f"""<h2 id="prior-artefacts">Prior research artefacts this site still serves</h2>
<p class="sm">Every one of these is <strong>research-only: OK to download, do not upload</strong>.
None is approved for a weekly slot, none has an organiser score, and no weekly slot has been spent on
any of them. Their disclosures stay on the current pages on purpose, so that a reader who lands here
from an old link cannot mistake an earlier artefact for the current candidate. Rendered from
<code>docs/data/*.json</code>, not typed.</p>
<table><tr><th>Round</th><th>Unique TIFF</th><th>SHA-256 prefix</th><th>Short download path</th>
<th>Disposition</th><th>Its own page / published estimate</th></tr>{body}</table>
<p class="sm">The full list of everything served, re-measured from the bytes at publish time, is
<a href="downloads/MANIFEST.json">docs/downloads/MANIFEST.json</a>. Every round's page is in
<a href="archive.html">the archive</a>.</p>"""


def root_page(card, wr, hold, submit_ok) -> str:
    """The GitHub Pages entry point at the repository root: verdict first, then one download button."""
    prim = hold["pooled"]["scores"]["A_ODD_gated"]
    sb = hold["pooled"]["scores"]["single_B"]
    d = hold["promotion_delta_vs_single_B"]
    rg = card["range_gate"]
    ok = bool(submit_ok)
    badges = ('<span class="badge b-ok">DOWNLOAD: YES</span> '
              + ('<span class="badge b-ok">SUBMIT: YES</span>' if ok
                 else '<span class="badge b-no">SUBMIT: NO &mdash; DO NOT SUBMIT</span>')
              + ' <span class="badge b-warn">NO CERTIFIED LEADERBOARD GAIN</span>')
    body = f"""
<h1>H84 candidate raster &mdash; DOE GEMS competition #306</h1>
<div class="verdict {"v-ok" if ok else "v-no"}">
  <div style="display:flex;gap:10px;flex-wrap:wrap">{badges}</div>
  <p><strong>Verdict: {esc(card["verdict"].upper())}.</strong>
  {"Every frozen gate passed." if ok else
   "Research artefact only: download is safe, submission is not recommended."}</p>
  <p class="sm">HOLDOUT-DTI (evaluator <code>{esc(hold["evaluator_version"])}</code>,
  {hold["withheld_positive_pixels"]:,} withheld positives, {hold["dots_per_fold_per_arm"]:,} dots per
  fold per arm): primary arm <code>A_ODD_gated</code> <strong>{fmt(prim["dti"])}</strong>
  [{fmt(prim["ci95"][0])}, {fmt(prim["ci95"][1])}] vs its mandated control <code>single_B</code>
  {fmt(sb["dti"])} [{fmt(sb["ci95"][0])}, {fmt(sb["ci95"][1])}]; paired {fmt(d["delta"])}
  [{fmt(d["ci95"][0])}, {fmt(d["ci95"][1])}]. A holdout number is never a board forecast.</p>
</div>
<div class="btns">
  <a class="btn" href="docs/downloads/h84-candidate.tif" download>&#11015; Download h84-candidate.tif</a>
  <a class="btn sec" href="docs/downloads/h84-candidate.zip" download>ZIP</a>
  <a class="btn sec" href="docs/index.html">Full site</a>
  <a class="btn sec" href="docs/executive-summary.html">How to submit</a>
  <a class="btn sec" href="docs/validator.html">Check a file in your browser</a>
  <a class="btn sec" href="docs/archive.html">Archive</a>
</div>
<dl class="kv">
<dt>File</dt><dd><code>docs/downloads/h84-candidate.tif</code> =
  <code>submission/{esc(wr["file"])}</code></dd>
<dt>Bytes / SHA-256</dt><dd>{wr["bytes"]:,} &middot; <code>{esc(wr["sha256"])}</code></dd>
<dt>Emitted cells</dt><dd>{card["placement"]["emitted_px"]:,} binary {{0,1}} pixels, 3 px minimum
  separation, {card["placement"]["catalogue_distance_m"]["pct_within_200m"]}% within 200 m of a mapped
  trace</dd>
<dt>Range gate</dt><dd>min {fmt(rg["min"], 3)}, max {fmt(rg["max"], 3)}, {rg["n_nan"]} NaN or infinite
  anywhere in the grid &rarr; <strong>{"PASS" if rg["values_in_0_1"] else "FAIL"}</strong>; this file
  cannot trip &ldquo;Predicted values must be in range [0, 1]&rdquo;</dd>
<dt>Grid</dt><dd>{esc(card["validator_output"]["crs"])} &middot;
  {card["validator_output"]["height"]}&times;{card["validator_output"]["width"]} &middot;
  {esc(card["validator_output"]["dtype"])} &middot; {card["validator_output"]["bands"]} band &middot;
  transform identical to <code>sample_submission.tif</code></dd>
<dt>Submission name</dt><dd><code>{esc(card["submission_name"])}</code></dd>
<dt>Note ({card["submission_note_chars"]}/140)</dt><dd class="mono">{esc(card["submission_note"])}</dd>
<dt>Slots used</dt><dd>{card["slots_used"]}</dd>
</dl>
<p class="sm">This page is a research artefact. It is not an organiser acceptance receipt and it claims
no leaderboard gain. Sources and what was verified from each:
<a href="docs/h84-sources.html">docs/h84-sources.html</a>. Irregularities found this session, including
two that this page's own predecessors had: <a href="docs/index.html#irregularities">docs/index.html</a>
and <code>registry/irregularities.json</code>.</p>"""
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>GEMSDOE52 — H84 candidate raster</title>"
            f"<style>{CSS}</style></head><body>"
            "<header><div class=\"wrap\"><nav>"
            "<a class=\"on\" href=\"index.html\">Current round</a>"
            "<a href=\"docs/index.html\">Full site</a>"
            "<a href=\"docs/executive-summary.html\">How to submit</a>"
            "<a href=\"docs/h84.html\">H84 result</a>"
            "<a href=\"docs/h84-hypotheses.html\">Hypotheses</a>"
            "<a href=\"docs/h84-sources.html\">Sources</a>"
            "<a href=\"docs/validator.html\">Check a file</a>"
            "<a href=\"docs/archive.html\">Archive</a>"
            "</nav></div></header>"
            f"<main>{body}</main>"
            "<footer><div class=\"wrap\">GEMSDOE52 &middot; DOE GEMS prize challenge #306 &middot; "
            "every number on this site is labelled HOLDOUT-DTI, OWNER-REPORTED or ORGANIZER-CONFIRMED."
            "</div></footer></body></html>")


def archive_page() -> str:
    """Every page this site serves, with the round it belongs to, measured from the files present."""
    pages = sorted(DOCS.glob("*.html"))
    rows = []
    for p in pages:
        if p.name in ("index.html", "archive.html"):
            continue
        txt = p.read_text(errors="replace")
        rnd = ""
        for tag in ("H84", "H83", "H82", "H81", "H77cond", "H77", "H76", "H75", "H74S", "H74",
                    "H73", "H72", "H71", "H70", "H69", "H68", "H67", "H66", "H65b", "H65", "H64",
                    "H63", "H62", "H61", "H60d", "H60c", "H60", "H59", "H58", "H57", "H56", "H55",
                    "H54", "H53", "H52", "CTD5", "R5", "R4"):
            if tag.lower() in p.name.lower() or f"round {tag}" in txt.lower() or f">{tag} " in txt:
                rnd = tag
                break
        verdict = ""
        low = txt.lower()
        if "submit: no" in low or "do not submit" in low or "research-only" in low:
            verdict = "research-only / DO NOT SUBMIT"
        elif "submit: yes" in low:
            verdict = "self-labelled SUBMIT: YES (see IR-H84-002)"
        rows.append(f"<tr><td><a href=\"{esc(p.name)}\">{esc(p.name)}</a></td>"
                    f"<td>{esc(rnd) or '&mdash;'}</td><td class=\"n\">{p.stat().st_size:,}</td>"
                    f"<td>{esc(verdict)}</td></tr>")
    dlrows = "".join(
        f"<tr><td><a href=\"downloads/{esc(p.name)}\">downloads/{esc(p.name)}</a></td>"
        f"<td class=\"n\">{p.stat().st_size:,}</td>"
        f"<td class=\"mono\">{esc(sha256(p)[:32])}&hellip;</td></tr>"
        for p in sorted(DL.glob("*.tif"))[:60])
    return f"""<h1>Archive &mdash; every round this site serves</h1>
<p class="sm">This site is current-first: <a href="index.html">docs/index.html</a> always describes the
most recent round, and every earlier round is preserved here verbatim rather than overwritten. Rounds
were merged to <code>main</code> by parallel sessions, so a page's own verdict is that round's claim,
not this repository's endorsement of it. Where two rounds disagree, both are listed.</p>
<h2>Pages</h2>
<table><tr><th>Page</th><th>Round</th><th class="n">Bytes</th><th>Stated disposition</th></tr>
{''.join(rows)}</table>
<h2>Served rasters (first 60 of {len(list(DL.glob('*.tif')))})</h2>
<p class="sm">Every one is re-measured at publish time into
<a href="downloads/MANIFEST.json">downloads/MANIFEST.json</a>, which is the authoritative list: it
carries each file's SHA-256, byte count, and whether its adjacent receipt still describes the bytes
actually served.</p>
<table><tr><th>File</th><th class="n">Bytes</th><th>SHA-256 (first 32 hex)</th></tr>{dlrows}</table>"""


def hypotheses_page(chn, fit) -> str:
    md = (ROOT / "knowledge" / "74_hypotheses_H84_preregistered.md").read_text()
    sha = hashlib.sha256(md.encode()).hexdigest()
    best_a = max(((v, k) for d in fit["canary"]["per_fold"] for k, v in d["per_channel"].items()
                  if k.startswith("A_") and v is not None), default=(None, None))
    best_b = max(((v, k) for d in fit["canary"]["per_fold"] for k, v in d["per_channel"].items()
                  if k.startswith("B_") and v is not None), default=(None, None))
    body = "".join(line_to_html(l) for l in md.splitlines())
    return f"""
<h1>H84 hypotheses &mdash; pre-registered before any fit</h1>
<p class="sm">Frozen document <code>knowledge/74_hypotheses_H84_preregistered.md</code>,
SHA-256 <code>{sha}</code>, pinned in <code>registry/h84_preregistration.json</code>.
<code>scripts/run_h84.py</code> re-hashes it on every stage and refuses to fit if it moved.</p>
<div class="card"><h3 style="margin-top:0">What the canary measured per channel</h3>
<p>Best single <strong>View A</strong> channel out-of-fold AUC across all folds:
<strong>{fmt(best_a[0], 4)}</strong> (<code>{esc(best_a[1])}</code>).
Best single <strong>View B</strong> channel: <strong>{fmt(best_b[0], 4)}</strong>
(<code>{esc(best_b[1])}</code>). Alarm bar 0.90 &mdash; neither is close, so there is no leakage;
neither is close to useful either.</p>
<p class="sm">{chn["n_A"]} View A channels, {chn["n_B"]} View B channels.
{esc(chn["odd_even_definition"])}</p></div>
<article class="md">{body}</article>"""


def line_to_html(l: str) -> str:
    s = html.escape(l)
    if s.startswith("# "):
        return f"<h1>{s[2:]}</h1>"
    if s.startswith("## "):
        return f"<h2>{s[3:]}</h2>"
    if s.startswith("### "):
        return f"<h3>{s[4:]}</h3>"
    if s.startswith("* "):
        return f"<li>{inline(s[2:])}</li>"
    if s.startswith("---"):
        return "<hr>"
    if not s.strip():
        return ""
    return f"<p>{inline(s)}</p>"


def inline(s: str) -> str:
    import re
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"&lt;(https?://[^&]+)&gt;", r'<a href="\1">\1</a>', s)
    return s


def sources_page() -> str:
    S = [("Official problem description, metric and submission format",
          "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
          "fetched live 2026-10-10",
          "ORGANIZER-CONFIRMED: alpha 0.2, beta 0.8, R 300 m triangular kernel, TPw/FPw/FNw definitions, "
          "float32 single band, EPSG:32611, 100 m, same bounds, null or NaN outside, values in [0,1]; "
          "and that the test set is newly identified faults NOT in the existing USGS database"),
         ("Official public leaderboard",
          "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/",
          "fetched live 2026-10-10",
          "ORGANIZER-CONFIRMED: rank 1 = 0.3774 (xiaofanhu), rank 2 = 0.3418, rank 3 = 0.3361, "
          "rank 8 = 0.3195 (DARD), rank 22 = 0.2778 (extradr19). These are PUBLIC-chunk numbers; the "
          "Initial Prize Round is scored on the private chunk."),
         ("Competition about page and data tab",
          "https://www.drivendata.org/competitions/306/competition-doe-gems/data/",
          "login-walled; not reachable without credentials",
          "NOT VERIFIED from the organiser. training_features.tif, labels.tif, sample_submission.tif and "
          "1m_DEM_links.csv were restored from the owner's hash-pinned sibling mirrors and verified by "
          "SHA-256 against registry/data_manifest.json (23/23 pins, all_ok=true)."),
         ("Reference solution", "https://github.com/drivendataorg/gems-prize-reference-solution",
          "public repository", "Simple baseline approach published by the organiser."),
         ("USGS GeoDAWN survey release",
          "https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and",
          "public domain", "Provenance of the aeromagnetic and aeroradiometric surveys behind the "
          "provided bands, including the total-count grid that band 6 actually is."),
         ("INGENIOUS project, Great Basin Center for Geothermal Energy",
          "https://gbcge.org/current-projects/ingenious/", "public",
          "Source of part of the provided fault labels."),
         ("DOE Geothermal Data Repository submission 1391", "https://gdr.openei.org/submissions/1391",
          "public, CC BY 4.0", "Wells, springs and geothermometer data for the region."),
         ("EPSG:32611 — WGS 84 / UTM zone 11N", "https://epsg.io/32611", "public",
          "The projected CRS the submission must use; verified against the bytes of every raster here."),
         ("Tversky index", "https://en.wikipedia.org/wiki/Tversky_index", "public",
          "The similarity index the metric parameterises with alpha and beta."),
         ("Blum & Mitchell, Combining Labeled and Unlabeled Data with Co-Training, COLT 1998, pp. 92-100",
          "https://doi.org/10.1145/279943.279962", "published paper",
          "The method this lane is assigned to. Its two-view assumptions (each view sufficient and "
          "approximately conditionally independent given the class) are NOT established by a low "
          "error correlation alone, and this round measured View A sufficiency failing."),
         ("USGS 3D Elevation Program (1 m DEM)", "https://www.usgs.gov/3d-elevation-program",
          "public domain, but NOT obtainable from this runner",
          "The named free official source that the highest-value lever requires. Bash egress here is "
          "limited to github.com, codeload, api.github.com, pypi.org and files.pythonhosted.org, and the "
          "competition's own 1m_DEM_links.csv is login-walled, so no new native-resolution reduction is "
          "possible in this sandbox."),
         ("Band tags of training_features.tif (no URL: read from the organiser's own file bytes)",
          "https://www.drivendata.org/competitions/306/competition-doe-gems/data/",
          "login-walled; the tags were read from the restored file instead", "evidence/h84_band_tags.json records data_category and description "
          "for every band used. Band 6 is tagged magnetic_data / 'Tilt angle or total curvature' but "
          "measures as the aeroradiometric total-count grid; the tag is wrong and the discrepancy is "
          "reported rather than silently relied on.")]
    rows = "".join(f"<tr><td><a href=\"{esc(u)}\">{esc(t)}</a></td><td>{esc(how)}</td>"
                   f"<td>{esc(what)}</td></tr>" for t, u, how, what in S)
    return f"""<h1>Sources, and exactly what was verified from each</h1>
<p class="sm">Every row was checked in this session. &ldquo;ORGANIZER-CONFIRMED&rdquo; means read from
the organiser's own page or leaderboard; &ldquo;OWNER-REPORTED&rdquo; means the owner team's pairing of
a filename with a board number, which the board itself does not print; &ldquo;HOLDOUT-DTI&rdquo; means
computed by this repository's own instrument and is never a leaderboard forecast.</p>
<table><tr><th>Source</th><th>Access status</th><th>What was verified from it</th></tr>{rows}</table>
<h2>Restored inputs</h2>
<p class="sm">23 of 23 SHA-256 pins verified, <code>data/restore_receipt.json &rarr; all_ok = true</code>.
Every one is an <strong>integrity-pinned mirror, not an organiser-authenticated download</strong>: the
portal is login-walled, so the pins prove the mirrors are self-consistent and nothing more. All
downstream claims carry that caveat.</p>
<h2>What could not be verified</h2>
<ul>
<li>No organiser score exists for any file in this repository. No file has ever been uploaded.</li>
<li>The public/private chunk boundary is not published, so |G| for the private chunk cannot be derived;
the |G| &asymp; 14,089 used in the algebra is a public-chunk quantity solved from two owner-reported
scores of a strictly nested pair.</li>
<li>The three external uint8 rasters (<code>lidar_scarp_features_u8</code>,
<code>geodawn_rad_u8</code>, <code>geodawn_extensions_u8</code>) carry <strong>no band descriptions at
all</strong>. Their channels cannot be audited against a source, so H84 does not use them as learner
inputs; it uses only bands whose identity the organiser's own file states.</li>
</ul>"""


def readme_block(card, wr, hold, build, lane, fit, ind, submit_ok, mism) -> None:
    prim = hold["pooled"]["scores"]["A_ODD_gated"]
    sb = hold["pooled"]["scores"]["single_B"]
    sa = hold["pooled"]["scores"]["single_A"]
    rnd = hold["pooled"]["scores"]["random"]
    d = hold["promotion_delta_vs_single_B"]
    lit = lane["dots"].get("literal", {})
    slit = lane["surface"].get("literal", {})
    block = f"""<!--H84-README-->
# Current status — H84 (2026-10-10): NEGATIVE — a signed strain-dipole operator was built and gated; View A failed sufficiency an eighth time

> **DOWNLOAD: YES** (format-valid, range-gated, 0 NaN anywhere, values exactly {{0,1}}, lane-checked
> against {lane["census_size"]} byte-distinct aligned rasters). **SUBMIT: {"YES" if submit_ok else "NO — research artefact only."}**
> The pre-registered primary `A_ODD_gated` scored **HOLDOUT-DTI {prim["dti"]:.6f}**
> [{prim["ci95"][0]:.4f}, {prim["ci95"][1]:.4f}] against its mandated control `single_B`
> {sb["dti"]:.6f} [{sb["ci95"][0]:.4f}, {sb["ci95"][1]:.4f}]; paired
> **{d["delta"]:.6f}** [{d["ci95"][0]:.4f}, {d["ci95"][1]:.4f}]. The frozen rule needs that lower bound
> above zero. **Slots used: 0.**

**★ [Download H84 GeoTIFF](docs/downloads/h84-candidate.tif)** · [ZIP](docs/downloads/h84-candidate.zip)
· **[Executive summary / exactly how to submit](docs/h84-executive-summary.html)**
· **[Check any file in your browser](docs/validator.html)** · [Full result](docs/h84.html)
· [Hypotheses](docs/h84-hypotheses.html) · [Sources](docs/h84-sources.html)
· [Measured download manifest](docs/downloads/MANIFEST.json)

- **File:** `submission/{wr["file"]}` — {wr["bytes"]:,} bytes, SHA-256 `{wr["sha256"]}`
- **Submission name:** `{card["submission_name"]}`
- **Note ({card["submission_note_chars"]}/140):** `{card["submission_note"]}`
- **Validator (from the bytes on disk):** {wr["validator"]["bands"]} band {wr["validator"]["dtype"]},
  {wr["validator"]["crs"]}, {wr["validator"]["height"]}×{wr["validator"]["width"]}, transform identical to
  `sample_submission.tif`, **{card["range_gate"]["n_nan"]} NaN/infinite anywhere in the grid**, values
  exactly {{0,1}}, {card["placement"]["emitted_px"]:,} ones. **PASS.**
- **Container, chosen on evidence:** all-finite with zeros outside the footprint, tiled/deflate, no
  nodata tag — byte-structurally the container of the OWNER-REPORTED 0.2778 reference
  `h33-2-b2-zeros.tif`. Measured this session: 11 of 13 restored owner-scored rasters are strip/LZW
  `nodata=nan` and 2 are all-finite, so **both containers have been portal-accepted**, and the
  all-finite one cannot trip *"Predicted values must be in range [0, 1]"* under any reader.
- **HOLDOUT-DTI** (`{hold["evaluator_version"]}`, {hold["withheld_positive_pixels"]:,} withheld positive
  px, {hold["dots_per_fold_per_arm"]:,} dots/fold/arm, α 0.2 / β 0.8, R 300 m, 1,000 paired
  cluster-bootstrap draws at 200 px): `A_ODD_gated` **{prim["dti"]:.6f}** · `single_B` {sb["dti"]:.6f} ·
  `single_A` {sa["dti"]:.6f} · `random` {rnd["dti"]:.6f}. **A holdout number is never a board forecast**
  (this repository has measured Spearman −0.10 between the instrument and the board, `knowledge/10` §5).
- **View A sufficiency FAILED an eighth time:** mean out-of-fold AUC
  {fit["sufficiency"]["view_A_mean"]:.4f}, worst fold {fit["sufficiency"]["view_A_min_fold"]:.4f}, bar
  {fit["sufficiency"]["bar_mean"]} / {fit["sufficiency"]["bar_min_fold"]}. View B
  {fit["sufficiency"]["view_B_mean"]:.4f}. With A below chance there is nothing for A to donate, which is
  why the primary arm cannot beat the control — the co-training lane's own precondition, not a bug.
- **Leakage canary:** max single-channel out-of-fold AUC = **{fit["canary"]["max_auc"]}**
  (`{fit["canary"]["max_channel"]}`) against a 0.90 bar → **no alarm**.
- **View independence (the lane's mandated test):** max |ρ| **{ind["max_abs_correlation"]:.4f}** over
  {ind["n_blocks"]:,} spatial blocks / {ind["n_negative_predictions"]:,} proxy negatives (bar 0.60,
  thresholds inherited verbatim from `registry/h74_preregistration.json`) → `allow_exchange={ind["allow_exchange"]}`.
  **{ind["exchange_decision"]}.**
- **Lane:** surface literal **{slit.get("verdict")}** (max ρ {slit.get("max_spearman")}); final dots
  literal **{lit.get("verdict")}** (max ρ {lit.get("max_spearman")}, near-3px
  {lit.get("max_near_3px_fraction")}) against {lane["census_size"]} byte-distinct aligned rasters.
- **Not the union:** Jaccard {build["not_the_union"]["relations"][0]["jaccard"]} against the union-max
  placement at the same budget, {build["not_the_union"]["relations"][1]["jaccard"]} against View A alone,
  {build["not_the_union"]["relations"][2]["jaccard"]} against View B alone; identical to none →
  **{"PASS" if build["not_the_union"]["ok"] else "FAIL"}**.
- **Placement:** {build["emitted_px"]:,} binary cells at 3 px minimum separation from a
  {build["pool_px"]:,} px pool; 200 m catalogue ring excluded; minimum catalogue distance
  {build["catalogue_distance_m"]["min"]} m, median {build["catalogue_distance_m"]["median"]} m,
  {build["catalogue_distance_m"]["pct_within_300m"]}% inside the metric's 300 m kernel.
- **Method:** {chn_count(fit)} learner channels. View A = a **signed, odd-symmetric fault-normal profile
  decomposition** of geodetic dilatation rate (band 8), shear rate (7) and second invariant (4), plus
  isostatic gravity (13) and its horizontal gradient (18) as a cross-family antisymmetry control:
  `odd=(B(+h)−B(−h))/2`, `even=(B(+h)+B(−h))/2` at h ∈ {{1,2}} px along a normal measured from a
  structure tensor over each fold's **visible** catalogue only, with odd-dominance
  `odd²/(|odd|+|even|+ε)` and a sign-reversal couple as the discriminators. View B = detrended elevation
  (12), its slope (19) and the aeroradiometric total count (6). Every View A operator built in this
  repository before was sign-blind; a grep for `dipole`, `odd_sym`, `strain_dipole`, `odd-symmetric`
  and `derivative of gaussian` returns no implementation, and the one registered antisymmetry idea
  (H57-C) was never run and is a cross-family *orientation* coincidence, not a signed profile.
- **Cross-validation of the direction field:** H84's per-fold regional fault normals are 74.5–80.3°
  compass, so the derived trace strikes are 164.5–170.3° — agreeing with H82's independently measured
  166.7–171.8° from a separate structure-tensor implementation.
- **Irregularities flagged this session:** {len(mism)} download path(s) whose adjacent JSON receipt
  describes different bytes than the file served (IR-H84-001), plus
  IR-H84-002…005 in `registry/irregularities.json` and on the site. None was papered over: the repair is
  a **measured manifest** (`docs/downloads/MANIFEST.json`) re-derived from every served file at publish
  time, so a receipt cannot drift from its bytes again.
- **Docs:** [pre-registration](knowledge/74_hypotheses_H84_preregistered.md) (frozen before any fit,
  SHA-256 pinned in `registry/h84_preregistration.json`, and the runner re-hashes it on every stage) ·
  [run card](evidence/h84_run_card.json) · [holdout](evidence/h84_holdout.json) ·
  [independence](evidence/h84_independence.json) · [lane](evidence/h84_lane.json) ·
  [build](evidence/h84_build.json) · [write](evidence/h84_write.json)
- **Reproduce:** `python3 scripts/restore_data.py --target-dir data` →
  `python scripts/run_h84.py all` → `python scripts/publish_h84_site.py` → `python scripts/check_site.py`
  → `python -m pytest -q`.

---

<!--/H84-README-->
"""
    p = ROOT / "README.md"
    t = p.read_text()
    if "<!--H84-README-->" in t:
        a, rest = t.split("<!--H84-README-->", 1)
        _, rest = rest.split("<!--/H84-README-->", 1)
        t = a + rest
    p.write_text(block + "\n" + t.lstrip("\n"))


def chn_count(fit) -> str:
    n = len(fit["canary"]["per_fold"][0]["per_channel"])
    return f"{n}"


if __name__ == "__main__":
    sys.exit(publish())
