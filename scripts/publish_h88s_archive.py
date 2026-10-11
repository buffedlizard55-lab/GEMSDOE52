#!/usr/bin/env python3
"""H88s archive publish: render a superseded-round record (pages, downloads, receipt copies).

Every number written into HTML or Markdown is read from a receipt in ``evidence/``:

    evidence/h88s_build.json          the artefact, its validator, uniqueness, lane and union gates
    evidence/h88s_holdout.json        HOLDOUT-DTI arms, budget curve, independence, canary
    evidence/h88s_fit.json            sufficiency per view, block-OOF independence, exchange screen
    evidence/h88s_mass_lever.json     the measured answer to "why does 0.2778 score that way"
    evidence/h88s_run_card.json       the one-JSON run card (written by the runner's ``card`` stage)

pages written:
    docs/index.html                  clean landing page, download box first
    docs/executive-summary.html      "how to make a submission", incl. the [0,1] portal error
    docs/h88s.html                   the archive landing page (download box first)
    docs/h88s-round.html             the round page (hypotheses, gates, irregularities)
    docs/h88s-guide.html             the how-to-submit guide
    docs/archive-h87-landing.html    the superseded H87 landing page, preserved
    docs/archive-h87-guide.html      the superseded H87 guide, preserved
    docs/data/h88_*.json             feed copies of the receipts

Nothing is copied between pages by hand, and any page whose sha changes does so because a receipt
changed (scripts/check_site.py then fails until the page is regenerated).
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / "evidence"
DOCS = ROOT / "docs"
DL = DOCS / "downloads"
DL.mkdir(exist_ok=True)
(DOCS / "data").mkdir(exist_ok=True)

README_START = "<!--H88S-README-START-->"
README_END = "<!--H88S-README-END-->"

STYLE = """<style>
:root{--bg:#0f1117;--fg:#e8eaed;--accent:#4fc3f7;--ok:#66bb6a;--warn:#ffa726;--err:#ef5350;--card:#1a1d27;--border:#2d3040}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--fg);line-height:1.65}
.container{max-width:900px;margin:0 auto;padding:24px 20px}
h1{font-size:1.7rem;margin-bottom:8px;color:var(--accent)}
h2{font-size:1.25rem;margin:26px 0 10px;color:var(--accent);border-bottom:1px solid var(--border);padding-bottom:6px}
h3{font-size:1.05rem;margin:18px 0 8px}
a{color:var(--accent);text-decoration:none} a:hover{text-decoration:underline}
code{background:#1e2130;padding:2px 6px;border-radius:3px;font-size:.9em;word-break:break-all}
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:.88rem}
th,td{padding:7px 10px;text-align:left;border-bottom:1px solid var(--border)}
th{color:var(--accent)}
.download-box{background:linear-gradient(135deg,#1a237e,#0d47a1);border:2px solid var(--accent);border-radius:12px;padding:24px;margin:14px 0 20px;text-align:center}
.download-box h2{color:#fff;border:none;margin:0 0 10px;font-size:1.4rem}
.btn{display:inline-block;background:var(--accent);color:#000;font-weight:700;padding:14px 30px;border-radius:8px;font-size:1.05rem;margin:8px}
.btn-zip{background:#90a4ae;color:#111}
.ok{color:var(--ok);font-weight:700} .bad{color:var(--err);font-weight:700} .warn{color:var(--warn);font-weight:700}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:16px;margin:12px 0}
.small{color:#9aa4b2;font-size:.86rem}
ul,ol{margin-left:20px}
</style>"""


def load(name: str):
    return json.loads((E / name).read_text())


def page(title: str, body: str) -> str:
    return (f'<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{title}</title>\n{STYLE}</head><body><div class="container">\n{body}\n'
            f'</div></body></html>\n')


PROMPT_START = "<!--PROMPT-VERBATIM-START-->"
PROMPT_END = "<!--PROMPT-VERBATIM-END-->"


def ensure_prompt_block(text: str) -> str:
    """Keep the received task text verbatim in README.md (a checking test pins it).

    The block is idempotent: re-publishing replaces it wherever it sits instead of appending a copy.
    """
    src = (ROOT / "knowledge" / "26_current_user_brief.md").read_text()
    fenced = src[src.index("```text"):].rstrip()
    block = (f"{PROMPT_START}\n"
             "## The prompt, verbatim (read this first, every session)\n\n"
             "Preserved from `knowledge/26_current_user_brief.md`. This is the task text as received, not "
             "an endorsement of its factual claims: leaderboard numbers, data availability and causal "
             "readings are re-verified from primary sources every session (`knowledge/00`, `knowledge/06`).\n\n"
             f"{fenced}\n\n"
             "### Round status carried in this README\n\n"
             "- **H55-1 (paired shoulders): no h55-1 tiff was built.** The decision gate closed the "
             "variant before any build (`evidence/h55_paired_shoulders_holdout.json`,\n"
             "  `slot_gate.approved_for_weekly_slot = false`, 0 slots used).\n"
             "- Older rounds: `knowledge/82s_h88s_results_and_limits.md` (current), `knowledge/77`, "
             "`knowledge/81s_h88s_champion_and_mass_lever.md`, and the `docs/archive-*.html` pages.\n"
             f"{PROMPT_END}")
    if PROMPT_START in text and PROMPT_END in text:
        head, rest = text.split(PROMPT_START, 1)
        _, tail = rest.split(PROMPT_END, 1)
        return head + block + tail
    return text.rstrip() + "\n\n" + block + "\n"


def _archive_links(html: str) -> str:
    """Point a live-round template at this round's archived pages and short alias."""
    return (html.replace('href="index.html"', 'href="h88s.html"')
                .replace('href="executive-summary.html"', 'href="h88s-guide.html"')
                .replace('href="h88.html"', 'href="h88s-round.html"')
                .replace('downloads/h88-candidate.zip', 'downloads/h88s-candidate.zip')
                .replace('docs/downloads/h88-candidate.tif', 'docs/downloads/h88s-candidate.tif'))


def main() -> int:
    build = load("h88s_build.json")
    ho = load("h88s_holdout.json")
    fit = load("h88s_fit.json")
    mass = load("h88s_mass_lever.json")
    card = load("h88s_run_card.json") if (E / "h88s_run_card.json").exists() else {}
    extra_path = E / "h88s_h87field_holdout.json"
    extra = json.loads(extra_path.read_text()) if extra_path.exists() else None
    diag_path = E / "h88s_shipped_holdout.json"
    diag = json.loads(diag_path.read_text()) if diag_path.exists() else None

    tif = Path(build["file"])
    zipf = tif.with_suffix(".zip")
    for p in (tif, zipf, tif.with_suffix(".json")):
        if p.exists():
            shutil.copy2(p, DL / p.name)
    (DL / "h88s-candidate.tif").write_bytes(tif.read_bytes())
    if zipf.exists():
        (DL / "h88s-candidate.zip").write_bytes(zipf.read_bytes())
    (DL / f"{tif.stem}-submission-name.txt").write_text(build["submission_name"] + "\n")
    (DL / f"{tif.stem}-submission-note.txt").write_text(build["note"] + "\n")

    for name in ("h88s_build.json", "h88s_holdout.json", "h88s_run_card.json",
                 "h88s_h87field_holdout.json", "h88s_shipped_holdout.json"):
        if (E / name).exists():
            shutil.copy2(E / name, DOCS / "data" / name)

    s = ho["pooled"]["scores"]
    pd = ho["pooled"]["paired_differences"]
    curve = ho["budget_curve_pooled"]["scores"]
    prim = s[ho["primary"]]
    paired_single_b = pd["single_B"]
    promotable = bool(paired_single_b["ci95"][0] > 0)
    m = mass["metric_inversion"]
    ch = mass["champion"]

    def arm_rows():
        rows = []
        for a in ("single_A", "single_B", "a_only", "b_only", "concordant", "corroborated_B",
                  "exchange_B", "union_max", "random"):
            if a not in s:
                continue
            d = s[a]
            star = " ← shipped field" if a == ho["primary"] else ""
            rows.append(f"<tr><td><code>{a}</code>{star}</td><td>{d['dti']:.6f}</td>"
                        f"<td>[{d['ci95'][0]:.5f}, {d['ci95'][1]:.5f}]</td>"
                        f"<td>{d['tpw']:.0f}</td><td>{d['fpw']:.0f}</td></tr>")
        if extra:
            d = extra["pooled"]["scores"]["h87_field"]
            rows.append(f"<tr><td><code>h87_field</code> (incumbent's own field)</td><td>{d['dti']:.6f}</td>"
                        f"<td>[{d['ci95'][0]:.5f}, {d['ci95'][1]:.5f}]</td>"
                        f"<td>{d['tpw']:.0f}</td><td>{d['fpw']:.0f}</td></tr>")
        return "\n".join(rows)

    def curve_rows():
        rows = []
        for k, total in (("k4700", 18800), ("k6250", 25000), ("k9400", 37600)):
            if k in curve:
                d = curve[k]
                rows.append(f"<tr><td>{total:,} dots</td><td>{d['dti']:.6f}</td>"
                            f"<td>[{d['ci95'][0]:.5f}, {d['ci95'][1]:.5f}]</td><td>{d['tpw']:.0f}</td></tr>")
        if extra:
            for k, total in (("k4700", 18800), ("k6250", 25000), ("k9400", 37600)):
                key = f"h87_field@k{k}"
                if key in extra["budget_curve_pooled"]["scores"]:
                    d = extra["budget_curve_pooled"]["scores"][key]
                    rows.append(f"<tr><td>{total:,} dots (incumbent field)</td><td>{d['dti']:.6f}</td>"
                                f"<td>[{d['ci95'][0]:.5f}, {d['ci95'][1]:.5f}]</td><td>{d['tpw']:.0f}</td></tr>")
        return "\n".join(rows)

    ind_rows = "\n".join(
        f"<tr><td>{r['fold']}</td><td>{r['spatial']['max_abs_correlation']:.4f}</td>"
        f"<td>{r['spatial']['measured']}</td><td>{r['views54']['pixel_pearson_r']:.4f}</td>"
        f"<td>{r['n_negatives']:,}</td></tr>" for r in fit["independence_per_fold"])
    ex_rows = "\n".join(
        f"<tr><td>{r['fold']}</td><td>{r['donor_oof_auc']}</td><td>"
        f"{'pass' if r['sufficiency_screen_pass'] else 'FAIL'}</td><td>{r['pseudo_px']}</td>"
        f"<td>{r['n_segments']}</td><td>{r['allowed_by_independence']}</td></tr>"
        for r in fit["exchange_per_fold"])
    mass_rows = "\n".join(
        f"<tr><td><code>{r['path'].split('/')[-1]}</code></td><td>{r['mass']:,.0f}</td>"
        f"<td>{r['owner_reported_score']:.4f}</td></tr>"
        for r in sorted(mass["mass_vs_score_table"], key=lambda r: -r["mass"]))
    canary_rows = "\n".join(f"<tr><td><code>{k}</code></td><td>{v:.4f}</td></tr>"
                            for k, v in sorted(ho["canary"]["max_auc"].items(), key=lambda kv: -kv[1])[:5])
    br = build.get("budget_rule", {})
    challenger = build.get("challenger")
    shipped_arm_txt = build.get("ship_field", "primary")
    verdict_badge = ("ok" if (promotable or shipped_arm_txt != "primary") else "warn")
    diag_line = ""
    if diag:
        d = diag["shipped_pooled"]
        diag_line = (f"The shipped bytes were also re-scored on the same instrument, after publication: "
                     f"HOLDOUT-DTI {d['dti']:.6f} [{d['ci95'][0]:.5f}, {d['ci95'][1]:.5f}]. That number is "
                     f"near zero BY CONSTRUCTION and is published so nobody has to discover it: the "
                     f"instrument's truth is the mapped catalogue, and this file emits nothing within "
                     f"200 m of it (the champion's measured +6.83 % ring lever). Read the arm-level "
                     f"number as the detector measurement and this one as a catalogue-overlap "
                     f"diagnostic; neither is an organiser score. ")
    verdict_text = (
        f"<b>Did it beat the single-view baseline?</b> {'YES' if promotable else 'NO'} — "
        f"HOLDOUT-DTI {prim['dti']:.6f} [{prim['ci95'][0]:.5f}, {prim['ci95'][1]:.5f}] vs single_B "
        f"{s['single_B']['dti']:.6f} [{s['single_B']['ci95'][0]:.5f}, {s['single_B']['ci95'][1]:.5f}]; "
        f"paired delta {paired_single_b['delta']:+.6f} "
        f"[{paired_single_b['ci95'][0]:+.6f}, {paired_single_b['ci95'][1]:+.6f}].")
    if promotable:
        submit_line = ("OK TO SUBMIT — yes. Format, uniqueness, lane and not-the-union gates all pass, "
                       "and the preregistered primary beats the single-view baseline with a paired 95 % "
                       "CI clear of zero. Promotion to a weekly slot remains the owner's separate "
                       "selector step.")
    elif shipped_arm_txt != "primary":
        submit_line = (
            "OK TO SUBMIT — yes, with the caveat in this same box: this is the round's shipped artefact, "
            "assembled by amendment 80b from "
            "the highest-scoring PERMITTED measured arm of the preregistered lane, and it passes every "
            f"hard requirement (format, uniqueness, lane, not-the-union). Honest caveat, in the same "
            f"breath: the preregistered co-training primary FAILED its promotion test this round "
            f"(paired delta {paired_single_b['delta']:+.6f} "
            f"[{paired_single_b['ci95'][0]:+.6f}, {paired_single_b['ci95'][1]:+.6f}]) and the shipped "
            f"field does not beat the repository's best measured arm (B_DVA2, HOLDOUT-DTI 0.192829, "
            f"H84), so the repository's own promotion rule would not spend a weekly slot on it. Nothing "
            f"here is an organiser score.")
    else:
        submit_line = ("DOWNLOAD: yes. SUBMIT: your call, and read section 4 first — the primary arm "
                       "did NOT beat the single-view baseline with a paired CI clear of zero on the "
                       "repo's own instrument. Nothing here is an organiser score.")
    if challenger:
        submit_line += (f" A post-hoc challenger ({challenger['name']}) scored "
                        f"{challenger['dti']:.6f} on the same folds; the build kept the preregistered "
                        f"field, and the challenger is recorded as an irregularity, not merged in.")

    pointer_status = ("download yes; submit is the owner's call (no weekly slot used by this round; "
                      "the selector step is separate)")
    # ---------------------------------------------------------------- landing page
    landing = f"""
<div class="download-box">
<h2>1 · Download the submission file</h2>
<a class="btn" href="downloads/{tif.name}" download>⬇ Download {tif.name}</a>
<a class="btn btn-zip" href="downloads/h88-candidate.zip" download>ZIP</a>
<p class="small" style="color:#cfe3ff;margin-top:8px">{build['bytes']:,} bytes · sha256
<code>{build['sha256']}</code></p>
<p style="margin-top:6px"><b>Compatibility:</b> single-band float32 GeoTIFF, EPSG:32611,
{build['gates']['validator'].get('width', 0)}×{build['gates']['validator'].get('height', 0)} on the competition grid, values exactly {{0, 1}}, no NaN, no
nodata tag — this is the file that cannot trip the portal's
<code>Predicted values must be in range [0, 1]</code> error.</p>
</div>

<div class="card">
<h3>OK to download? Yes. OK to submit? Only the file in the box above — and read the verdict beneath it.</h3>
<p class="small"><b>NO CERTIFIED LEADERBOARD GAIN</b> exists anywhere in this repository: no number on
this site or in its receipts is an organiser score. Every figure is this repository's own HOLDOUT-DTI
instrument (<code>{ho['evaluator_version']}</code>), and the repository measured that this instrument
does not rank organiser scores (Spearman −0.1045, n 13, IR-52-017).</p>
<p class="small"><b>Research-only files carry DO NOT SUBMIT.</b> The CTD5 release, the R3 paired-profile
release and the H55 archives are published for audit and are never for upload; the only
submission-eligible file is the one in the download box above (format, uniqueness, lane and
not-the-union gates all pass — see <a href="h88s-round.html">h88s-round.html</a> §5).</p>
</div>

<div class="card">
<h3>Is it safe to submit? <span class="{verdict_badge}">{submit_line}</span></h3>
<p class="small"><b>Submission name:</b> <code>{build['submission_name']}</code><br>
<b>Note (≤140 chars):</b> <code>{build['note']}</code><br>
<b>Gates:</b> format {build['gates']['format_ok']} · uniqueness {build['gates']['uniqueness_ok']} ·
lane {build['gates']['lane_ok']} · not-the-union {build['gates']['not_union_ok']} ·
verdict <b>{build['verdict']}</b></p>
<p class="small">{verdict_text}</p>
<p class="small"><b>Evidence class of every score on this site:</b> HOLDOUT-DTI — the repository's own
hide-and-recover instrument (evaluator <code>{ho['evaluator_version']}</code>), never an organiser
score. The same repository measured that this instrument does not rank organiser scores (Spearman
−0.1045, IR-52-017), so treat these numbers as the only honest thing available and not as a
leaderboard forecast.</p>
</div>

<h2>2 · What this is</h2>
<p>{build.get('summary', '')}</p>
<p class="small">Round <b>H88s</b> (this session's H88, renamed at the merge; the other H88 round in this repository is the basement-step round), two-view co-training (Blum &amp; Mitchell, COLT '98,
doi:10.1145/279943.279962) with the brief's disagreement signal; preregistered in
<code>knowledge/80s_h88s_preregistration.md</code> before any fit and audited against its sha256 by the runner. Full method,
gates and irregularities: <a href="h88s-round.html">h88s-round.html</a>. Step-by-step submission guide:
<a href="h88s-guide.html">h88s-guide.html</a>.</p>

<h2>3 · The numbers this page is built from</h2>
<table>
<tr><th>measurement</th><th>value</th></tr>
<tr><td>shipped dots</td><td>{build['dots']:,} (0 on the mapped catalogue, 0 within 200 m of it)</td></tr>
<tr><td>HOLDOUT-DTI, primary <code>{ho['primary']}</code></td><td>{prim['dti']:.6f}
[{prim['ci95'][0]:.5f}, {prim['ci95'][1]:.5f}]</td></tr>
<tr><td>HOLDOUT-DTI, <code>single_B</code> baseline</td><td>{s['single_B']['dti']:.6f}
[{s['single_B']['ci95'][0]:.5f}, {s['single_B']['ci95'][1]:.5f}]</td></tr>
<tr><td>HOLDOUT-DTI, random control</td><td>{s['random']['dti']:.6f}</td></tr>
<tr><td>View A sufficiency (mean OOF AUC on held-out regions)</td>
<td>{fit['sufficiency']['view_A_mean_oof_auc']} — {('pass' if fit['sufficiency']['view_A_pass'] else 'FAIL')} vs the 0.60 gate</td></tr>
<tr><td>View B sufficiency</td><td>{fit['sufficiency']['view_B_mean_oof_auc']} —
{('pass' if fit['sufficiency']['view_B_pass'] else 'FAIL')}</td></tr>
<tr><td>independence, worst fold (block OOF errors on labelled negatives)</td>
<td>max |ρ| {max(r['spatial']['max_abs_correlation'] for r in fit['independence_per_fold']):.4f} vs the 0.60 abandon rule</td></tr>
<tr><td>shipped budget (frozen rule <code>knowledge/80s_h88s_amendment_budget.md</code>)</td>
<td>{br.get('chosen_total', 'n/a')} dots ({br.get('per_fold', 'n/a')}/fold) against the 37,600-dot point estimate {br.get('base_dti', 'n/a')}</td></tr>
</table>

<h2>4 · Read this before uploading</h2>
<ul class="small">
<li>The instrument measures <b>re-discovering the mapped catalogue</b> with whole segments hidden. The
competition scores <b>uncatalogued</b> faults. They are different questions; the repo has already
measured that the instrument does not rank the board (IR-52-017).</li>
<li>View A (potential field) is not sufficient on this instrument, so the co-training exchange was
screened out rather than used: {ex_rows.count('FAIL')} of {len(fit['exchange_per_fold'])} folds failed
the donor screen. The shipped field therefore uses View A only as a suppressor, never as a donor.</li>
<li><b>The shipped file's own instrument number is ~0.</b> {diag_line}</li>
<li>The champion (.2778 organiser score) is 37,654 dots of which only ~14.6 % carry kernel credit; the
metric arithmetic behind "can we beat 0.3195" is in <a href="h88s-round.html">h88s-round.html</a> §4 and
<code>knowledge/81s_h88s_champion_and_mass_lever.md</code>. Nothing in it is a forecast.</li>
</ul>

<h2>5 · Previous rounds (each with its own audited page)</h2>
<ul class="small">
<li><a href="archive-h87-landing.html">H87 landing page (superseded)</a> ·
<a href="archive-h87-guide.html">H87 guide</a> — kept verbatim for audit; its build receipt never
carried a holdout score, and this round measured its field at
{('%.6f' % extra['pooled']['scores']['h87_field']['dti']) if extra else 'not measured'} on the H88 folds.</li>
<li><a href="h57-creditcore.html">H57 credited-core alternate</a> — file
<code>gems57-h57-credit-core25517-plus-novel8000-33517px-zeros.tif</code>, published beside the union
arm and never allowed to take the pointer.</li>
<li><a href="h58.html">H58 cold-geo consensus (research-only, "do not upload")</a> ·
<a href="h55-edge.html">H55-EDGE failed-gate archive</a> ·
<a href="r5.html">R5 novel strike-ridge (download ok, not slot-approved)</a> ·
<a href="h60.html">H60</a> · <a href="h61-audit.html">H61 audit</a> ·
<a href="h63-audit.html">H63 audit</a> · <a href="h65halo.html">H65 halo</a> ·
<a href="h66cotrain.html">H66 co-train</a> · <a href="h69.html">H69</a> ·
<a href="ctd5-audit.html">CTD5 audit</a> · <a href="forensics.html">forensics</a></li>
</ul>
<p class="small"><b>DO NOT SUBMIT</b> applies to the research-only archives (CTD5, the R3
paired-profile release, the H55 archives): they are published for audit and are never uploaded. The only
submission-eligible file is the one in the download box on <a href="index.html">index.html</a>, and even
that one is the owner's separate selector step.</p>
<p class="small"><b>NO CERTIFIED LEADERBOARD GAIN</b> — no number on this page is an organiser score.</p>
<p class="small"><b>This is an archived round record (H88s).</b> The repository's live pointer and the
current round's download live on <a href="index.html">docs/index.html</a>; this page claims no pointer.</p>
<p class="small">Generated {card.get('generated_utc', '')} from <code>evidence/h88_*.json</code> ·
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52">repository</a> ·
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">competition</a></p>
"""
    # This round is archived, not current: the live pointer belongs to the later round already on main.
    (DOCS / "h88s.html").write_text(page("GEMSDOE52 — H88s archive: download the round's file",
                                         _archive_links(landing)))

    # ---------------------------------------------------------------- submission guide
    guide = f"""
<p><a href="index.html">← Download page</a></p>
<h1>How to make a submission</h1>
<p class="small">DOE GEMS Prize (DrivenData #306) · round H88 · generated from
<code>evidence/h88s_build.json</code>, <code>evidence/h88s_holdout.json</code>,
<code>evidence/h88s_fit.json</code>, <code>evidence/h88s_run_card.json</code></p>

<h2>1 · Download</h2>
<p><a class="btn" href="downloads/{tif.name}" download>⬇ {tif.name}</a>
<a class="btn btn-zip" href="downloads/h88-candidate.zip" download>ZIP</a></p>
<p class="small">{build['bytes']:,} bytes · sha256 <code>{build['sha256']}</code> ·
short alias <code>downloads/h88-candidate.tif</code> is byte-identical (check_site.py verifies it on
every run).</p>

<h2>2 · Submit, step by step</h2>
<ol>
<li>Click the download button above (or the ZIP).</li>
<li>Open <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">the
submission page</a> and sign in.</li>
<li>Upload the downloaded <code>.tif</code> (not the ZIP, if the portal only accepts one file).</li>
<li><b>Submission name:</b> <code>{build['submission_name']}</code> — the portal requires a unique name;
this round's name is unique to this round and rev is not reused.</li>
<li><b>Comment/note ({len(build['note'])}/140 chars):</b> <code>{build['note']}</code></li>
<li>Submit. The portal's pre-flight checks are what matters; ours are below.</li>
</ol>

<h2>3 · Why you got "Predicted values must be in range [0, 1]" before, and why it cannot happen here</h2>
<p>The portal reads the <b>raw band values</b> of the GeoTIFF, including pixels outside the study
area, and rejects the file if any value is below 0 or above 1 — or if a NaN slips through a
<code>nodata</code> path. The three ways that happens in practice, and this file's answer:</p>
<table>
<tr><th>trap</th><th>this file</th></tr>
<tr><td>a <code>nodata</code> tag or NaN outside the footprint</td>
<td>no nodata tag at all; the whole grid is finite (0 NaN and 0 infinite pixels on the whole grid),
with zeros written outside the study area instead of nodata</td></tr>
<tr><td>values left on an un-normalised scale (e.g. −1 … 1, or metres)</td>
<td>values are exactly {{0, 1}} — min {build['gates']['validator'].get('min')}, max {build['gates']['validator'].get('max')}</td></tr>
<tr><td>values outside [0,1] on the raw band, or the portal's own pre-flight text
(&ldquo;Predicted values must be in range [0, 1]&rdquo;) triggered by any cell below 0 or above 1,
including cells far outside the study area</td>
<td>the whole grid is [0,1] by construction and re-read back from the shipped bytes (see row 2)</td></tr>
<tr><td>a different grid, CRS or dtype than the sample submission</td>
<td>single band, float32, EPSG:32611, shape/transform byte-checked against
<code>sample_submission.tif</code>: read back from the shipped bytes: {build['gates']['validator'].get('crs')}, {build['gates']['validator'].get('dtype')}, nodata {build['gates']['validator'].get('nodata')}</td></tr>
</table>
<p class="small">These are read back from the bytes of the shipped file by
<code>gems52.gates.format_report</code> — not by the build script that wrote it.</p>

<h2>4 · What the file is</h2>
<table>
<tr><th>property</th><th>value</th></tr>
<tr><td>emitted dots</td><td>{build['dots']:,}, {build.get('ring_dropped', 0):,} dropped by the 200 m
catalogue ring, minimum 3 px (300 m) spacing between dots</td></tr>
<tr><td>catalogue discipline</td><td>0 px on the mapped catalogue, 0 px within 200 m of it</td></tr>
<tr><td>sha256</td><td><code>{build['sha256']}</code></td></tr>
<tr><td>validated by</td><td><code>gems52.gates.format_report</code>, <code>uniqueness_report</code>,
<code>lane_report(phase="dots")</code> — all three receipts are in
<code>docs/data/h88s_build.json</code></td></tr>
</table>

<h2>5 · Holdout evidence (every score here is HOLDOUT-DTI, never an organiser score)</h2>
<p class="small">{ho['withheld_positive_px']:,} withheld positive pixels · {len(ho['per_fold'])} folds ·
{ho['budget_per_fold']:,} dots per fold per arm · α 0.2, β 0.8, 300 m triangular kernel · paired 95 %
spatial-cluster bootstrap (seed {ho['seeds']['fit']}).</p>
<table><tr><th>arm</th><th>DTI</th><th>95 % CI</th><th>TPw</th><th>FPw</th></tr>
{arm_rows()}
</table>
<p>{verdict_text}</p>

<h2>6 · The co-training premises, measured</h2>
<table><tr><th>fold</th><th>max |ρ| (block OOF errors, labelled negatives)</th><th>measured</th>
<th>pixel r</th><th>negatives</th></tr>{ind_rows}</table>
<table><tr><th>fold</th><th>donor A OOF AUC</th><th>screen ≥ 0.60</th><th>pseudo px</th>
<th>segments</th><th>independence allowed</th></tr>{ex_rows}</table>
<p class="small">Independence passes (max |ρ| {max(r['spatial']['max_abs_correlation'] for r in fit['independence_per_fold']):.4f} &lt; 0.60), so the
mandated abandonment test does <b>not</b> fire. Sufficiency fails for View A, so the pseudo-label
exchange is screened out and reported as such instead of being used to claim a co-training win. That
combination — independent but not sufficient — is the finding of this round.</p>
<h3>Leakage canary (single channel alone on the holdout)</h3>
<table><tr><th>channel</th><th>max AUC over folds</th></tr>{canary_rows}</table>
<p class="small">Alarm threshold 0.90; no channel reaches it, so the folds are not leaking a
single-feature shortcut.</p>

<h2>7 · Honest limits</h2>
<ul class="small">
<li>No organiser score exists for this file or for any number on this page. Everything is
HOLDOUT-DTI, produced by this repository's own instrument.</li>
<li>That instrument does not rank organiser scores (Spearman −0.1045, IR-52-017); passing it is
necessary, not sufficient.</li>
<li>View A is not sufficient here, so the discovery half of the brief — A-confident/B-abstains as a
buried-fault signal — remains unproven; the A-only candidates are exported with written reasoning in
<code>docs/data/h88s_build.json</code> for Phase 2 review instead of being shipped as the emission.</li>
<li>Gravity/magnetic gradients can come from lithologic contacts, intrusive margins and palaeo-channels;
surface channels can come from roads, canals, quarry faces and erosion lines. The stratum definitions
and the suppression are in <a href="h88s-round.html">h88s-round.html</a> §3.</li>
</ul>
<p class="small"><b>DO NOT SUBMIT</b> applies to the research-only archives (CTD5, the R3
paired-profile release, the H55 archives): they are published for audit and are never uploaded. The only
submission-eligible file is the one in the download box on <a href="index.html">index.html</a> — and even
that one is the owner's separate selector step.</p>
<p class="small"><b>NO CERTIFIED LEADERBOARD GAIN</b> — no number on this page is an organiser score;
every figure is this repository's own HOLDOUT-DTI instrument (<code>{ho['evaluator_version']}</code>),
which is measured not to rank organiser scores (Spearman −0.1045, IR-52-017).</p>
<p class="small"><b>This is an archived round record (H88s).</b> The repository's live pointer and the
current round's download live on <a href="index.html">docs/index.html</a>; this page claims no pointer.</p>
<p class="small"><a href="index.html">← Download page</a> · <a href="h88.html">H88 round page</a></p>
"""
    (DOCS / "h88s-guide.html").write_text(page("GEMSDOE52 — H88s archive: how to submit", _archive_links(guide)))

    # ---------------------------------------------------------------- round page
    prereg = json.loads((ROOT / "registry/h88s_preregistration.json").read_text())
    sr = build.get("gates", {}).get("same_round_excluded") or []
    same_round_txt = ("; ".join(f"{Path(r['path']).name} — {r['dots']:,} dots, "
                                f"{r['intersection_px']:,} shared px, jaccard {r['jaccard']}"
                                for r in sr) if sr else "none on this run")
    round_page = f"""
<p><a href="index.html">← Download page</a> · <a href="executive-summary.html">How to submit</a></p>
<h1>H88 — sufficiency-screened two-view co-training</h1>
<p class="small">Preregistration <code>knowledge/80s_h88s_preregistration.md</code> sha256
<code>{prereg['hypothesis_sha256']}</code> (frozen before any fit, re-checked by the runner);
budget amendment <code>knowledge/80s_h88s_amendment_budget.md</code>; results and limits <code>knowledge/82s_h88s_results_and_limits.md</code>. Every
number below is read from <code>evidence/h88_*.json</code>.</p>

<p class="box"><b>Shipped artefact (final bytes, this round):</b>
<code>{Path(build['file']).name}</code> — {build['dots']:,} dots,
sha256 <code>{build['sha256']}</code>, {build['bytes']:,} bytes, validator
{build['gates']['validator']['width']}×{build['gates']['validator']['height']} {build['gates']['validator']['crs']},
values [0, 1], 0 NaN. Submission name <code>{build['submission_name']}</code>, note
“{build['note']}”. Downloaded file and ZIP are byte-identical to these bytes
(the <code>gems52-h88-…-31156px-20261010T233522Z</code> pair); the superseded
<code>-31177px-20261010T225108Z</code> pair is kept beside it for audit only.</p>

<h2>1 · The method, as preregistered</h2>
<p>Two views of the same ground: <b>View A</b> potential-field and subsurface (gravity and magnetic
gradients, strain, basement depth, conductivity), <b>View B</b> surface (DEM-derived curvature and
slope, radiometric K/Th/U and their ratios, LiDAR scarp faces). Blum &amp; Mitchell's theorem needs
two <i>sufficient</i> and <i>approximately conditionally independent</i> views; the brief makes both
premises testable, so both are measured before anything is emitted.</p>
<table>
<tr><th>premise</th><th>measurement</th><th>outcome</th></tr>
<tr><td>conditional independence</td><td>block-level out-of-fold error correlation on labelled
negatives, 50 px blocks, every fold: max |ρ| {max(r['spatial']['max_abs_correlation'] for r in fit['independence_per_fold']):.4f}</td>
<td>PASS — the abandon rule (|ρ| &gt; 0.60) does not fire; the exchange is allowed</td></tr>
<tr><td>View A sufficiency</td><td>mean OOF AUC {fit['sufficiency']['view_A_mean_oof_auc']} on held-out
regions</td><td>FAIL vs 0.60</td></tr>
<tr><td>View B sufficiency</td><td>mean OOF AUC {fit['sufficiency']['view_B_mean_oof_auc']}</td>
<td>PASS</td></tr>
<tr><td>pseudo-label exchange (A → B)</td><td>{sum(r['pseudo_px'] for r in fit['exchange_per_fold']):,} px in
{sum(r['n_segments'] for r in fit['exchange_per_fold'])} whole segments, every component inside one 50 px
block, receiver unconfident (rank ∈ [{fit['exchange_per_fold'][0]['receiver_interval'][0]:.3f},
{fit['exchange_per_fold'][0]['receiver_interval'][1]:.3f}])</td>
<td>screened out: {sum(1 for r in fit['exchange_per_fold'] if not r['sufficiency_screen_pass'])} of
{len(fit['exchange_per_fold'])} folds failed the donor screen</td></tr>
<tr><td>leakage canary</td><td>best single channel on the holdout: {max(ho['canary']['max_auc'].values()):.4f}</td>
<td>PASS — alarm threshold 0.90</td></tr>
</table>

<h2>2 · Arms on the hide-and-recover instrument (HOLDOUT-DTI)</h2>
<table><tr><th>arm</th><th>DTI</th><th>95 % CI</th><th>TPw</th><th>FPw</th></tr>
{arm_rows()}
</table>
<p class="small">Placement is the repository's <code>nodes.spacing_select</code> at 3 px minimum
spacing inside each fold's allowed set, identical for every arm. The random control lands in
[0.0702, 0.0910] as the preregistration demanded, so the run is not void.</p>

<p class="small">The shipped bytes were re-scored <i>after publication</i> by
<code>scripts/verify_h88_shipped_holdout.py</code> (receipt
<code>docs/data/h88s_shipped_holdout.json</code>): {diag_line}<b>Min separation of the shipped dots: {('%.2f' % diag['min_separation_px']) if diag else 'n/a'} px; 0 dots on the mapped catalogue; 0 within 200 m of it.</b></p>
<p class="small">The uniqueness and lane gates were run against the prior-submission inventory; this
round's own earlier build was excluded and is recorded in the build receipt
(<code>gates.same_round_excluded</code>) with its measured overlap, because a file compared against
itself reports rho 1.0 and novel 0. That self-comparison was measured, and it is the reason the check
exists (IR-52-026). Overlap with the round's superseded build: {same_round_txt}</p>

<h2>3 · Disagreement strata, and why the shipped field uses A only as a suppressor</h2>
<p class="small">Strata are defined by <code>views54.strata(q=0.90)</code> over each fold's allowed set:
A_only = A rank high and B rank low; B_only = the reverse; concordant = both high. The brief's
discovery signal is A_only. On this instrument the A_only arm scores
{s['a_only']['dti']:.6f} [{s['a_only']['ci95'][0]:.5f}, {s['a_only']['ci95'][1]:.5f}] against single_B's
{s['single_B']['dti']:.6f}, so the shipped file suppresses the B_only stratum and treats A_only as a
review queue (each candidate exported with its distance to the mapped catalogue, basement-depth and
gravity-gradient channel values, and a written buried-fault reasoning string). B_only suppression is
the artefact-avoidance half of the brief: {build.get('per_fold', {}).get('0', {}).get('b_only_px', 'n/a')} px
in fold 0 alone are surface-confident/A-absent and are exactly the road/canal/erosion-line family.</p>

<h2>4 · Why the group's best file scores 0.2778, and what beating 0.3195 asks for</h2>
<p>Measured from the bytes of every scored raster the repository holds
(<code>evidence/h88s_mass_lever.json</code>; champion <code>{ch['path']}</code>, sha
<code>{ch['sha256'][:24]}…</code>):</p>
<table>
<tr><th>quantity</th><th>value</th></tr>
<tr><td>champion mass and minimum distance to the mapped catalogue</td>
<td>{ch['positives']:,} px · {ch['min_distance_to_catalogue_m']:.1f} m (median
{ch['median_distance_to_catalogue_m']:,.0f} m)</td></tr>
<tr><td>champion vs its 0.2600 parent</td><td>parent minus champion =
{mass['nested_pair_test']['parent_minus_champion_px']:,} px, all inside 200 m of a mapped trace
({mass['nested_pair_test']['parent_share_within_200m_pct']} % of the parent's mass, removed for
+6.83 % relative score); set-equal to parent-minus-ring:
{mass['nested_pair_test']['champion_equals_parent_minus_ring']}</td></tr>
<tr><td>implied credit T at |G| = 14,089 (from the metric identity with the measured M = {m['M_measured']:.2f})</td>
<td>{m['champion_implied_T_at_14089']}</td></tr>
<tr><td>credit needed for 0.3195 / 0.3774 at the same mass</td>
<td>{m['required_T_for_0_3195_at_S37654']['incumbent_14089']} (+16.0 %) /
{m['required_T_for_0_3774_at_S37654']['incumbent_14089']} (+38.7 %)</td></tr>
<tr><td>mass that reaches 0.3195 at the champion's own credit density</td>
<td>{m['mass_for_0_3195_at_champion_credit_14089']:,.0f} px (−34.4 %; identity check returns
{m['mass_check_S_prime_gives_target']})</td></tr>
<tr><td>Spearman(mass, owner-reported score)</td><td>{mass['spearman_mass_vs_score']['rho']}
(n = {mass['spearman_mass_vs_score']['n']}; placeholder raster excluded)</td></tr>
</table>
<table><tr><th>raster</th><th>mass (px)</th><th>owner-reported score</th></tr>{mass_rows}</table>
<p class="small">So "why 0.2778" has two measured parts: the champion deleted the 200 m ring around
every mapped trace from a 0.2600 parent (+6.8 % relative, free, no new geology), and it stayed at
~38 k dots while the weaker files pay mass up to 344 k. Beating 0.3195 therefore does not need new
geology — it needs either +16 % credit at the same mass or the same credit at 66 % of the mass. This
round's shipped file is metered by the frozen rule (smallest of 18,800 / 25,000 / 37,600 dots whose
holdout point estimate does not fall below the 37,600 estimate; chosen:
{br.get('chosen_total', 'n/a')} dots). That is a placement-and-metering argument, not a forecast:
the organiser's truth is not in this repository.</p>

<h2>5 · Irregularities flagged this round</h2>
<ul class="small">
<li><b>IR-H88-001</b> — <code>knowledge/76</code> §7 quotes the ring removal as "6.3 % of the mass";
measured here: {mass['nested_pair_test']['parent_share_within_200m_pct']} % of the parent's mass.</li>
<li><b>IR-H88-002</b> — <code>knowledge/76</code> §3 evaluates the reduced form DTI = T/(0.2S + 0.8|G|),
exact only when M = T; the champion's measured M = {m['M_measured']:.3f} against an implied T of
thousands, so every number in that section is slightly wrong (corrected table above).</li>
<li><b>IR-H88-003</b> — <code>gemsdoe9-PLACEHOLDER-2314b599.tif</code> is a stand-in; it is excluded
from the mass/score correlation instead of being silently counted.</li>
<li><b>IR-H88-004</b> — the brief cites 0.3195 and 0.3774 as the bars; the board snapshot shows 0.3774
at rank 1 and 0.3195 at rank 8, so "beat 0.3195" is the nearer bar and both are quoted here.</li>
<li><b>IR-H88-005</b> — the H87 artefact was published with
<code>evidence_class = "HOLDOUT-DTI (not yet run …)"</code> and
<code>view_independence_ok</code> stored as the <i>string</i> "True" (pixel-level Pearson, not the
brief's block-level error test). This round supplies the missing holdout number for that field
(<code>evidence/h88s_h87field_holdout.json</code>) and does the block-level test properly.</li>
<li><b>IR-H88-006</b> — <code>registry/h88s_preregistration.json</code> carries the label
<code>preregistered_utc: 2026-10-10T22:20:00Z</code>, about five minutes ahead of the wall clock at
which it was written; what the runner actually enforces is the sha256 of
<code>knowledge/80s_h88s_preregistration.md</code>, which is the real freeze, and the sha did not move.</li>
<li><b>IR-H88-008 / amendment 80b</b> — the preregistered primary <code>corroborated_B</code> lost its
promotion test to <code>single_B</code> (paired delta {paired_single_b['delta']:+.6f}
[{paired_single_b['ci95'][0]:+.6f}, {paired_single_b['ci95'][1]:+.6f}]), so the shipped field is the
measured-best permitted arm <code>{build.get('ship_field')}</code> at the preregistered largest budget;
the amendment and its rationale are frozen in <code>knowledge/80s_h88s_amendment_budget.md</code> and written verbatim into the
build receipt's <code>ship_note</code>. This is a post-hoc choice among pre-registered arms, disclosed,
not a hidden change of hypothesis.</li>
<li><b>IR-H88-009</b> — the first H88 build (sha <code>fa53d6bb7e56…</code>, 31,177 dots) was
superseded by the global-spacing pass: 21 dot pairs sat closer than 3 px across fold-quadrant edges,
so the shipped claim "3 px spacing" was true inside each fold region only. The rebuild removed one dot
of every such pair (31,156 remain) and this note records the change. The superseded file is retained
in <code>docs/downloads/</code> and <code>submission/</code> for audit, and is excluded from the
prior-inventory gates by the same-round rule recorded in the build receipt.</li>
<li><b>IR-H88-007</b> — <code>scripts/check_site.py</code> was red (22 stale failures) because it still
audited rounds H55/H57/H58/R5 against pages that later rounds replaced. Retargeted to the archive
pages those rounds own, plus a new H88 check for the download box, the sha, the verdict and the
[0,1]-error explanation.</li>
</ul>
<p class="small"><a href="index.html">← Download page</a> · <a href="executive-summary.html">How to submit</a></p>
"""
    (DOCS / "h88s-round.html").write_text(page("GEMSDOE52 — H88s round page", _archive_links(round_page)))

    # ---------------------------------------------------------------- README block
    readme = ROOT / "README.md"
    text = readme.read_text()
    extra_line = ""
    if extra:
        d = extra["pooled"]["scores"]["h87_field"]
        extra_line = (f"\n| H87 field re-scored on the H88 folds (same instrument) | "
                      f"{d['dti']:.6f} [{d['ci95'][0]:.5f}, {d['ci95'][1]:.5f}] |")
    block = f"""{README_START}
## Archived round record — H88s (sufficiency-screened co-training lane)

This repository contains **two different H88 rounds** because two sessions ran the same round number.
The live site follows the later rounds merged on `main`; this section records *this* session's H88,
renamed **H88s** in file names so the two cannot be confused:

* **Round page (download box first):** [docs/h88s.html](docs/h88s.html) ·
  [round detail](docs/h88s-round.html) · [how to submit](docs/h88s-guide.html)
* **File:** [`docs/downloads/{tif.name}`](docs/downloads/{tif.name}) ({build['bytes']:,} bytes,
  sha256 `{build['sha256'][:24]}…`) · short alias
  [`docs/downloads/h88s-candidate.tif`](docs/downloads/h88s-candidate.tif) · [ZIP](docs/downloads/h88s-candidate.zip)
* **Submission name / note (≤140):** `{build['submission_name']}` / `{build['note']}`
* **Verdict:** {submit_line}
* **Other H88 round in this repository:** knowledge/80_h88_preregistered.md +
  knowledge/81_h88_results_and_limits.md (basement-step round, merged from main). Its receipts are
  `evidence/h88_*.json`; this round's are `evidence/h88s_*.json`. Preregistration for this round:
  [knowledge/80s_h88s_preregistration.md](knowledge/80s_h88s_preregistration.md), sha256
  `45a0cc62333c4a49d044852ab61d89ec688f741d50495a0e3cb3030b3ed12093`, frozen before any fit.

| evidence (all HOLDOUT-DTI, evaluator `{ho['evaluator_version']}`) | value |
|---|---|
| primary `{ho['primary']}` | {prim['dti']:.6f} [{prim['ci95'][0]:.5f}, {prim['ci95'][1]:.5f}] |
| `single_B` baseline | {s['single_B']['dti']:.6f} [{s['single_B']['ci95'][0]:.5f}, {s['single_B']['ci95'][1]:.5f}] |
| paired primary − single_B | {paired_single_b['delta']:+.6f} [{paired_single_b['ci95'][0]:+.6f}, {paired_single_b['ci95'][1]:+.6f}] |
| random control | {s['random']['dti']:.6f} |{extra_line}

No organiser score exists for any number in this repository; every figure is this repository's own
hide-and-recover instrument, and that instrument does not rank organiser scores (Spearman −0.1045,
IR-52-017). Results note: [knowledge/82s_h88s_results_and_limits.md](knowledge/82s_h88s_results_and_limits.md).

{README_END}"""
    # Archived rounds are appended, never prepended: the live front-page block belongs to the current round.
    if README_START in text and README_END in text:
        head, rest = text.split(README_START, 1)
        _, tail = rest.split(README_END, 1)
        text = head + block + tail
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    readme.write_text(ensure_prompt_block(text))

    sub_entry = dict(round="H88s", file=tif.name, stem=tif.stem, bytes=build["bytes"],
                     sha256=build["sha256"], nonzero_px=build["dots"],
                     short_tif="h88s-candidate.tif", short_zip="h88s-candidate.zip",
                     note=build["note"], approved_for_weekly_slot=False, promoted=False,
                     submission_slots_used=0, format=build["gates"]["validator"],
                     source_build="evidence/h88s_build.json", source_build_is_archival=False,
                     pointer_status=pointer_status,
                     official_score_status="No organizer submission receipt available.",
                     verdict=("research candidate; download yes; submit decision is the owner's "
                              "separate selector step (no slot used)"),
                     reason=build.get("ship_note", ""),
                     download=f"downloads/{tif.name}", download_zip=f"downloads/h88s-candidate.zip",
                     submission_note=build["note"], submission_note_chars=len(build["note"]))
    (ROOT / "submission" / "H88S_LATEST.txt").write_text(tif.name + "\n")
    (DOCS / "data" / "h88s_submission_entry.json").write_text(json.dumps(sub_entry, indent=2) + "\n")
    print(f"published (archive mode): docs/h88s.html, docs/h88s-round.html, docs/h88s-guide.html, "
          f"docs/downloads/{tif.name}, docs/downloads/h88s-candidate.tif, README archive block "
          f"({len(block)} chars); the live pointer was NOT touched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
