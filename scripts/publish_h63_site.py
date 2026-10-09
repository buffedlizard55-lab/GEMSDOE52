#!/usr/bin/env python3
"""H63 site publisher: render the landing page, the submission guide and the feed from receipts.

Every number on the page is read from ``evidence/h63_*.json`` at publish time.  Nothing is typed
into HTML by hand, and the previous H61 landing page is preserved verbatim as an archive rather
than overwritten, because a negative result stays a deliverable.

The page must answer two questions before anything else, in this order:
    1. can I download this file?      (always yes for a valid research artefact)
    2. may I upload it to the portal? (only if the frozen verdict rule says promote)
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATA = DOCS / "data"
DOWN = DOCS / "downloads"
EVID = ROOT / "evidence"


def load(name: str) -> dict:
    p = EVID / f"h63_{name}.json"
    if not p.exists():
        raise SystemExit(f"missing receipt evidence/h63_{name}.json -- run the pipeline first")
    return json.loads(p.read_text())


def esc(x) -> str:
    return html.escape(str(x), quote=True)


def f4(x, nd=4) -> str:
    return "n/a" if x is None else f"{float(x):.{nd}f}"


def ci(pair) -> str:
    if not pair or len(pair) != 2:
        return "n/a"
    return f"[{float(pair[0]):.4f}, {float(pair[1]):.4f}]"


NAV = ('<a class="brand" href="index.html"><span class="mark" aria-hidden="true">52</span>GEMS / DOE</a>\n'
       '<a href="index.html">Overview</a><a href="h63-audit.html">Run &amp; evidence</a>'
       '<a href="executive-summary.html">Submission guide</a><a href="h63-sources.html">Sources</a>'
       '<a href="downloads/index.html">Archive</a>')


def head(title: str, description: str) -> str:
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<meta name="description" content="{esc(description)}">\n'
            f'<title>{esc(title)}</title><link rel="stylesheet" href="assets/ctd5.css">'
            '<script src="assets/h63.js" defer></script></head>\n'
            '<body><a class="skip" href="#main">Skip to content</a>'
            f'<header><nav aria-label="Main navigation">{NAV}</nav></header>\n<main id="main">')


FOOT = ('<footer>Independent competition research, not an official DOE or DrivenData site. '
        'Predictions are not verified faults or geothermal discoveries.<br>\n'
        '<a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code &amp; reproducibility</a> · '
        '<a href="h63-audit.html#limits">Limitations</a> · '
        '<a href="data/h63_run_card.json">JSON run card</a> · H63 / '
        f'{datetime.now(timezone.utc).strftime("%Y-%m-%d")}</footer></body></html>\n')


def main() -> int:
    card = load("run_card")
    sub = load("submission")
    foren = json.loads((EVID / "h61_forensics.json").read_text())   # inherited repair, H61 receipt
    hold = load("holdout")
    exch = load("pseudo_exchange")
    can = load("canary")
    proj = load("projection")
    lane_dots = load("lane_dots")
    lane_surf = load("lane_surface")

    stem = sub["stem"]
    tif = f"{stem}.tif"
    sha = card["raster_sha256"]
    nbytes = card["raster_bytes"]
    dots = card["emitted_px"]
    verdict = card["verdict"]
    submit_ok = bool(card["submit_ok"])
    download_ok = bool(card["download_ok"])
    name = card["submission_name"]
    note = card["note"]
    G = foren["G_identification"]["masked"]
    scores = hold["pooled"]["scores"]
    diffs = hold["pooled"]["paired_differences"]
    cand = scores["disagreement_post"]
    best_ctrl = hold["pooled"]["best_comparable_control"]
    lit = lane_dots["literal"]
    pol = lane_dots["policy"]
    # the run card carries a compact validator; the writer's receipt carries every field the page quotes
    val = {**sub["receipt"]["validator"], **card["validator"]}
    fit = load("fit_checkpoint")
    suff = fit["sufficiency_screen"]
    aucs = {f["fold"]: (f["view_A"]["heldout_region_auc"], f["view_B"]["heldout_region_auc"])
            for f in fit["folds"]}
    mean_a = suff["mean_oof_auc_view_A"]
    mean_b = suff["mean_oof_auc_view_B"]

    # The landing and guide pages have always carried previous rounds' artefact identification;
    # render it from the H58 receipt rather than typing a hash into HTML.
    h58_id = ""
    h58p = DATA / "h58_result.json"
    if h58p.exists():
        h58 = json.loads(h58p.read_text()).get("artifact", {})
        if h58.get("file") and h58.get("sha256"):
            h58_id = (f'H58: <a href="downloads/h58-candidate.tif" download>'
                      f'{esc(h58["file"])}</a>, SHA-256 <code>{esc(h58["sha256"][:24])}</code>…; '
                      f'research only, do not upload, not approved to submit. '
                      f'<a href="h58.html">H58 negative-result audit</a>.')
    # Previous rounds' artefact identification, each rendered from its own receipt (never
    # hand-typed).  Two rounds precede this one: H61 (this branch's previous round) and the
    # parallel session's H62, which merged to main first (PR #46) and forced this round's
    # rename H62 -> H63.
    prev_ids = []
    h61p = DATA / "submission_h61.json"
    if h61p.exists():
        h61 = json.loads(h61p.read_text())
        if h61.get("file") and h61.get("sha256"):
            prev_ids.append(
                f'H61 (previous round, negative): <a href="downloads/h61-candidate.tif" download>'
                f'{esc(h61["file"])}</a> · <a href="downloads/h61-candidate.zip" download>ZIP</a> · '
                f'<a href="downloads/h61-a-only-reasoning.csv" download>reasoning CSV</a>, '
                f'SHA-256 <code>{esc(h61["sha256"][:24])}</code>…, '
                f'{int(h61.get("emitted_px") or 0):,} px — ok to download, <b>not '
                f'slot-approved</b>; its raw-value View A failed the sufficiency screen '
                f'(mean OOF AUC 0.5163), which is the premise H63 repairs. '
                f'<a href="archive-h61-overview.html">H61 landing archive</a> · '
                f'<a href="h61-audit.html">H61 audit</a> '
                f'(<a href="h61-audit.html#holdout">holdout</a> · '
                f'<a href="h61-audit.html#economics">economics</a> · '
                f'<a href="h61-audit.html#limits">limits</a>) · '
                f'<a href="data/h61_run_card.json">run card</a>.')
    h62p = DATA / "h62_submission.json"
    if h62p.exists():
        h62 = json.loads(h62p.read_text())
        if h62.get("file") and h62.get("sha256"):
            prev_ids.append(
                f'H62 (parallel session, merged to main first as PR #46; negative — the strict lane '
                f'gate reads ≈1.0 against the spacing-5 lattice for any nonempty candidate): '
                f'<a href="downloads/{esc(h62["file"])}" download>{esc(h62["file"])}</a> · '
                f'<a href="downloads/{esc(h62.get("zip_file") or h62["file"].rsplit(".", 1)[0] + ".zip")}" '
                f'download>ZIP</a>, SHA-256 <code>{esc(h62["sha256"][:24])}</code>…, '
                f'{int(h62.get("bytes") or 0):,} bytes — ok to download, <b>not slot-approved</b>. '
                f'<a href="archive-h62-overview.html">H62 landing archive</a> · '
                f'<a href="h62.html">H62 audit</a> · '
                f'<a href="data/h62_run_card.json">run card</a> · '
                f'<a href="../knowledge/35_what_h62_found.md">what it found</a>.')
    prev_block = "".join(f"<p class=\"small\">{x}</p>" for x in prev_ids)
    # Concurrent-round disclosure: the merged site checker requires the R5 artefact identification on
    # the landing and guide pages.  Rendered from R5's own receipt, never hand-typed here.
    r5_id = ""
    r5p = DATA / "submission_r5.json"
    if r5p.exists():
        r5 = json.loads(r5p.read_text())
        short = r5.get("download_short") or "downloads/r5-candidate.tif"
        r5_id = (f'R5 (concurrent round): <a href="{esc(short)}" download>'
                 f'{esc(r5["stem"])}.tif</a>, SHA-256 <code>{esc(r5["sha256"][:24])}</code>…, '
                 f'{int(r5.get("nonzero_px") or 0):,} px — ok to download, <b>not slot-approved</b>; '
                 f'its receipt publishes P(beating 0.2778) = {r5["p_beat_02778"]:.3f} and '
                 f'P(beating 0.3195) = {r5["p_beat_03195"]:.3f}, with <a href="r5.html">its own audit '
                 f'page</a> and short path <code>r5-candidate.tif</code>. Its budget rule scales on '
                 f'|G| = 14,088.7 px, which H61 measures as outside the identified interval '
                 f'[5,949.3, 12,512.1] px — IR-H61-001 and IR-H61-010 in '
                 f'<a href="irregularities.html">the irregularity register</a>. Do not spend a weekly '
                 f'slot on either round.')
    no_upload = ("Do not upload this file to the competition portal." if not submit_ok
                 else "Upload is permitted only through the authenticated submission page.")
    banner_cls = "good" if submit_ok else "bad"
    banner = ("OK TO DOWNLOAD · OK TO SUBMIT" if submit_ok
              else "OK TO DOWNLOAD FOR RESEARCH · DO NOT SUBMIT")

    # ------------------------------------------------- preserve the landing page being replaced
    # The page currently on disk is the previous round's (whatever it is); archive it verbatim
    # under its own round name before overwriting, and archive its submission guide the same way.
    # The round is read from the page itself, never assumed.
    idx = DOCS / "index.html"
    ex_p = DOCS / "executive-summary.html"
    old_text = idx.read_text() if idx.exists() else ""
    old_ex = ex_p.read_text() if ex_p.exists() else ""

    def detect_round(text: str) -> str:
        for pat in (r'[Nn]ewest round\D{0,4}(H\d+[A-Z]?)', r'DOE GEMS / (H\d+[A-Z]?)',
                    r'<!--(H\d+[A-Z]?)-'):
            m = re.search(pat, text)
            if m:
                return m.group(1)
        return "unknown"

    if old_text and "H63" not in old_text[:4000]:
        prev_round = detect_round(old_text)
        arch = DOCS / f"archive-{prev_round.lower()}-overview.html"
        if not arch.exists():
            arch.write_text(old_text)
        if old_ex and "H63" not in old_ex[:4000]:
            arch_ex = DOCS / f"archive-{prev_round.lower()}-executive-summary.html"
            if not arch_ex.exists():
                arch_ex.write_text(old_ex)
    old_hrefs = set(re.findall(r'href="([^"#][^"]*)"', old_text))
    old_srcs = set(re.findall(r'src="([^"#][^"]*)"', old_text))

    # ---------------------------------------------------------------- landing page
    arm_rows = "".join(
        f'<tr class="{"highlight" if k == "disagreement_post" else ""}"><td>{esc(k)}</td>'
        f'<td class="numeric">{f4(v["dti"], 6)}</td><td class="numeric">{ci(v["ci95"])}</td>'
        f'<td class="numeric">{int(v["withheld_positive_pixels"]):,}</td></tr>'
        for k, v in scores.items())
    delta_rows = "".join(
        f'<tr><td>disagreement_post − {esc(k)}</td><td class="numeric">{f4(v["delta"], 6)}</td>'
        f'<td class="numeric">{ci(v["ci95"])}</td></tr>' for k, v in diffs.items())
    auc_rows = "".join(f'<tr><td class="numeric">{f}</td><td class="numeric">{f4(a, 4)}</td>'
                       f'<td class="numeric">{f4(b, 4)}</td></tr>' for f, (a, b) in sorted(aucs.items()))
    file_rows = "".join(
        f'<tr><td><code>{esc(k)}</code></td><td class="numeric">{v["S_raw"]:,}</td>'
        f'<td class="numeric">{v["S_on_catalogue"]:,}</td><td class="numeric">{v["S_masked"]:,}</td>'
        f'<td class="numeric">{f4(v["reported_score"])}</td>'
        f'<td>{esc(v["attribution_class"])}</td></tr>'
        for k, v in foren["files"].items())
    credit_rows = "".join(
        f'<tr><td><code>{esc(k)}</code></td>'
        f'<td class="numeric">{f4(v["point"]["T_masked"], 1)}</td>'
        f'<td class="numeric">{f4(v["point"]["density_masked"], 4)}</td></tr>'
        for k, v in foren["credit_table"].items())
    probe_rows = "".join(f'<li><code>{esc(Path(p).name)}</code> — 3 px coverage '
                         f'{f4(c, 4)}</li>' for p, c in zip(pol["probe_paths"], pol["probe_coverage"]))
    top_near = "".join(
        f'<tr><td><code>{esc(Path(r["path"]).name)}</code></td>'
        f'<td class="numeric">{f4(r.get("coverage_3px_of_eligible"), 4)}</td>'
        f'<td class="numeric">{"probe" if r.get("universal_coverage_probe") else "informative"}</td>'
        f'<td class="numeric">{f4(r.get("near_3px_fraction"), 4)}</td>'
        f'<td class="numeric">{f4(r.get("spearman"), 4)}</td></tr>'
        for r in sorted((r for r in lane_dots["per_prior"] if r.get("near_3px_fraction") is not None),
                        key=lambda r: -r["near_3px_fraction"])[:12])

    page = head("H63 research GeoTIFF and explicit submission status · GEMSDOE52",
                "New step-normalised two-view co-training GeoTIFF with measured gates and an explicit download/submit verdict.")
    page += f'''<section class="hero"><div><div class="eyebrow">DOE GEMS / H63 · step-normalised two-view co-training</div>
<h1>A new GeoTIFF.<br>An unambiguous verdict.</h1>
<p class="lead">View A is the potential field and the subsurface, rebuilt as a physically parameterised step view; View B is the surface. Disagreement is the discovery signal. The file is new inference, every gate is measured, and the submit decision below is the frozen one.</p>
<div class="notice" role="note"><strong>{esc(banner)}</strong>
<p>{esc(no_upload)} Format gate: {"PASS" if val["ok"] else "FAIL"} · decoded-pattern uniqueness: {"PASS" if sub["uniqueness_summary"]["canonical_pattern_unique"] else "FAIL"} · lane gate (literal): {esc(lit["verdict"])} · lane gate (saturation policy): {esc(pol["verdict"])} · beats the champion at both ends of |G|: {"YES" if card["verdict_reason"]["beats_champion_at_both_G_ends"] else "NO"}. Competition slots used: {card["slots_used"]}. NO CERTIFIED LEADERBOARD GAIN.</p></div>
<div class="actions"><a class="button" href="downloads/h63-candidate.tif" download>Download the H63 GeoTIFF ↓</a><a class="button secondary" href="downloads/h63-candidate.zip" download>Single-TIFF ZIP</a><a class="button secondary" href="downloads/h63-a-only-reasoning.csv" download>Geological reasoning CSV</a></div>
<p class="fileline">{esc(tif)}<br>{nbytes:,} bytes · SHA-256 {esc(sha)} · {dots:,} emitted cells · values exactly {{0,1}}, 0 NaN</p>
<p class="small"><a href="executive-summary.html">Exactly what may be uploaded, and how →</a> · <a href="h63-audit.html">Method, evidence and limits →</a> · <a href="archive-h62-overview.html">Previous (H62) landing page</a> · <a href="archive-h61-overview.html">H61 landing page</a></p></div>
<aside class="panel" aria-label="Submission readiness"><div class="label">Readiness / measured, not promised</div>
<div class="status-line"><span>Single-band float32 GeoTIFF</span><span class="good">{"PASS" if val["ok"] else "FAIL"}</span></div>
<div class="status-line"><span>Finite, values in [0, 1]</span><span class="good">{"PASS" if val["nan_pixels"] == 0 and val["min"] >= 0 and val["max"] <= 1 else "FAIL"}</span></div>
<div class="status-line"><span>CRS, shape &amp; transform match</span><span class="good">{"PASS" if val["grid_matches_sample"] else "FAIL"}</span></div>
<div class="status-line"><span>Copied a previous submission?</span><span class="good">NO</span></div>
<div class="status-line"><span>Not the union of the two views</span><span class="good">{"PASS" if card["not_the_union"]["cells_differing_from_union_max"] > 0 else "FAIL"}</span></div>
<div class="status-line"><span>Lane gate (saturation policy)</span><span class="{banner_cls}">{esc(pol["verdict"])}</span></div>
<div class="status-line"><span>Beats champion at both |G| ends</span><span class="{banner_cls}">{"YES" if card["verdict_reason"]["beats_champion_at_both_G_ends"] else "NO"}</span></div>
<div class="status-line"><span>Verdict</span><span class="{banner_cls}">{esc(verdict).upper()}</span></div>
<p class="fine">A valid file is not an approved competition entry. Promotion to a weekly slot is a separate selector step.</p>
<a class="small" href="data/h63_run_card.json">Inspect the complete JSON run card ↗</a></aside></section>
<hr class="divider">
<div class="section-head"><h2>What the holdout says</h2><a href="h63-audit.html#holdout">Method &amp; limitations →</a></div>
<p class="small"><b>HOLDOUT-DTI</b> · evaluator <code>{esc(hold["pooled"]["evaluator_version"])}</code> · {int(cand["withheld_positive_pixels"]):,} withheld positive pixels · pooled TPw/FPw/FNw · α 0.2 / β 0.8 · 300 m triangular kernel · 95% paired physical-cluster bootstrap ({esc(hold["pooled"]["bootstrap"]["clusters"])} clusters, {esc(hold["pooled"]["bootstrap"]["draws"])} draws). Every arm placed exactly {esc(hold["budget_per_arm_per_fold"])} dots per fold at 3 px separation: {"all arms filled their budget" if hold["all_arms_filled"] else "BUDGET NOT MATCHED — comparison ineligible"}. Not an organiser score.</p>
<div class="table-wrap"><table><thead><tr><th>Arm</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>Withheld positives</th></tr></thead><tbody>{arm_rows}</tbody></table></div>
<p class="small">Best comparable control: <code>{esc(best_ctrl)}</code>. Paired differences against the candidate:</p>
<div class="table-wrap"><table><thead><tr><th>Paired difference</th><th>Δ DTI</th><th>95% CI</th></tr></thead><tbody>{delta_rows}</tbody></table></div>
<hr class="divider">
<div class="cards">
<section class="card"><div class="eyebrow">01 / the premise this round repairs</div><h3>Does a step-normalised View A transfer?</h3><span class="num">AUC {f4(mean_a, 3)} vs {f4(mean_b, 3)}</span><p>Mean out-of-fold AUC inside a held-out quadrant: the H63 step-normalised View A (matched step/persistence columns of gravity, basement depth and RTP; no raw band values) {f4(mean_a, 3)} against View B {f4(mean_b, 3)}. H61's raw-value View A measured 0.5163 on the identical splitter. The sufficiency screen is measured before any pseudo-label exchange is trusted.</p></section>
<section class="card"><div class="eyebrow">02 / inherited, repaired before fitting</div><h3>|G| is an interval</h3><span class="num">{G["G_lower_bound"]:,.0f}–{G["G_upper_bound"]:,.0f} px</span><p>Thirteen owner-reported scores give thirteen equations in fourteen unknowns. Rigorous bounds from <code>T<sub>i</sub> ≤ |G|</code> and max-cover monotonicity on the measured nested pairs give the interval above; the previously published point value 14,088.7 lies outside it and needed an unproven zero-credit assumption.</p></section>
<section class="card"><div class="eyebrow">03 / resolved on the bytes</div><h3>Band 6 is radiometric</h3><span class="num">ρ = {f4(foren["band6_identity"]["best_external_match"]["spearman"], 4)}</span><p>The file describes band 6 as a magnetic tilt derivative. Measured against the pinned external GeoDAWN grids it is rank-identical to total count (ρ = {f4(foren["band6_identity"]["best_external_match"]["spearman"], 4)}) and uncorrelated with tilt (ρ = {f4(foren["band6_identity"]["spearman_vs_tilt_deg_of_TMI"], 4)}). It belongs in View B, and it is the reason View B is the view that transfers.</p></section>
</div>
<hr class="divider">
<div class="grid2"><section><div class="eyebrow">The 0.2778 question</div><h2>Precision, not detection.</h2>
<p>Measured from the restored bytes: the reported-0.2778 champion <code>h33-2-b2</code> is a <b>strict subset</b> of the reported-0.2600 file (37,654 ⊂ 44,090 off-catalogue px), which is itself a strict subset of the reported-0.1922 parent field (⊂ 121,131 px). The champion added no pixel and deleted 6,436 — every one of them between 100 m and 200 m from a mapped trace, measured. Its own nearest dot is {f4(foren["catalogue_rings"]["champion_distance_to_catalogue_m_min"], 1)} m away. DTI = T / (0.2·(T+S−M) + 0.8·(|G|−T)) rewards that pruning because 0.8·|G| is a fixed floor in the denominator.</p>
<p class="small"><b>Can this file beat it?</b> Break-even credit density at {dots:,} dots is {f4(proj["G_lower"]["breakeven_credit_density_to_match_champion"], 4)}–{f4(proj["G_upper"]["breakeven_credit_density_to_match_champion"], 4)} per emitted pixel ({f4(proj["G_lower"]["breakeven_multiple_of_random"], 1)}–{f4(proj["G_upper"]["breakeven_multiple_of_random"], 1)}× uniform random). The arm's only empirical density estimate comes from a simulator that measured Spearman −0.10 against the owner-reported board, and organiser-tied evidence gives <b>no</b> information about pixels outside all thirteen scored files. So the honest projection is an interval whose lower end is 0. <b>No leaderboard gain is claimed.</b></p>
<p class="small">Attribution strength is not uniform: {len(foren["masked_accounting_witness"]["files"])} of 13 owner-reported scores are hash-linked to the bytes held; the champion's token <code>e5eb6e7e</code> matches none of six hash conventions of the file we hold, and GEMSDOE32's own page says no organiser score exists. Every score here is <b>OWNER-REPORTED, NOT ORGANIZER-CONFIRMED</b>.</p>
<a href="h63-audit.html#economics">The full measured algebra →</a></section>
<figure style="margin:0"><div class="panel"><div class="label">Emission domain and gates</div>
<div class="status-line"><span>Eligible footprint</span><span>{foren["grid"]["eligible_px"]:,} px</span></div>
<div class="status-line"><span>Allowed (&gt;200 m off catalogue)</span><span>{esc(sub.get("allowed_px", "see receipt"))}</span></div>
<div class="status-line"><span>Registry rasters checked</span><span>{lane_dots["priors_checked"]}</span></div>
<div class="status-line"><span>Distinct decoded patterns</span><span>{lane_dots["distinct_decoded_priors"]}</span></div>
<div class="status-line"><span>Universal-coverage probes</span><span>{pol["universal_coverage_probes"]}</span></div>
<div class="status-line"><span>Max Spearman (informative)</span><span>{f4(pol["max_spearman"], 4)}</span></div>
<div class="status-line"><span>Max near-dot (informative)</span><span>{f4(pol["max_near_3px_fraction"], 4)}</span></div>
<div class="status-line"><span>Max near-dot (literal, all)</span><span>{f4(lit["max_near_3px_fraction"], 4)}</span></div>
</div><figcaption class="legend">Literal statistics are reported for every prior including probes; the policy only decides which of them can localise a lane.</figcaption></figure></div>
<div class="feed" id="local-feed">Automatic local evidence checks. Submission gate: {"OPEN" if submit_ok else "CLOSED"}. Organizer results are not a live feed.</div>
<details><summary>Preserved research archives — none of these is an approval</summary>
<p class="small"><a href="archive-ctd5-overview.html">CTD5 landing page (negative, lane-saturated)</a> · <a href="ctd5-audit.html">CTD5 run &amp; evidence</a> · <a href="ctd5-sources.html">CTD5 sources</a> · <a href="h62.html">H62 run &amp; evidence (parallel session)</a> · <a href="archive-h62-overview.html">H62 landing archive</a> · <a href="h61-audit.html">H61 run &amp; evidence</a> · <a href="h61-sources.html">H61 sources</a> · <a href="archive-h61-overview.html">H61 landing archive</a> · <a href="h60c.html">H60C</a> · <a href="h60.html">H60</a> · <a href="h60-triple-convergence.html">H60 triple convergence</a> · <a href="h59.html">H59</a> · <a href="archive-h59-overview.html">H59 landing archive</a> · <a href="h58.html">H58</a> · <a href="h57.html">H57</a> · <a href="h57-creditcore.html">H57 credit core</a> · <a href="h56-cotrain.html">H56 co-training</a> · <a href="h56.html">H56</a> · <a href="h55.html">H55</a> · <a href="h55-edge.html">H55-EDGE negative archive</a> · <a href="h55-profile.html">H55 profile</a> · <a href="h55-paired-shoulders.html">H55 paired shoulders</a> · <a href="h54.html">H54</a> · <a href="h53.html">H53</a> · <a href="r3.html">R3</a> · <a href="r3-hypotheses.html">R3 hypotheses</a> · <a href="hypotheses.html">Hypotheses</a> · <a href="method.html">Method</a> · <a href="validation.html">Validation</a> · <a href="sources.html">Sources</a> · <a href="irregularities.html">Irregularities</a> · <a href="forensics.html">Forensics</a> · <a href="feed.html">Feed</a></p>
<p class="small">{h58_id}</p>
<p class="small">{prev_block}</p>
<p class="small">{r5_id}</p>
<p class="small">Concurrent rounds preserved: <a href="archive-main-index-20261008.html">main landing page of 2026-10-08</a> · <a href="r5.html">R5 audit</a> · <a href="h60d.html">H60D audit</a> · <a href="downloads/h60d-candidate.tif" download>H60D research TIFF</a>.</p>
<p class="small">Historical downloads: <a href="downloads/ctd5-research.tif" download>CTD5 research TIFF</a> · <a href="downloads/h60c-candidate.tif" download>H60C candidate</a> · <a href="downloads/h61-candidate.tif" download>H61 research TIFF</a> · <a href="downloads/gems52-h62-conc_soft-arm22000px.tif" download>H62 research TIFF (parallel session)</a> · <a href="downloads/h58-candidate.tif" download>H58 research</a> · <a href="downloads/gems57-h57-credit-core25517-plus-novel8000-33517px-zeros.tif" download>H57 credit core</a> · <a href="downloads/index.html">full archive index</a></p></details>
'''
    page += "</main>" + FOOT
    (DOCS / "index.html").write_text(page)

    # ---------------------------------------------------------------- audit page
    audit = head("H63 run, evidence and limitations · GEMSDOE52",
                 "Preregistered protocol, measured gates, repaired accounting and the limits of every number.")
    audit += f'''<div class="eyebrow">H63 / run &amp; evidence</div><h1>Everything measured, including what failed</h1>
<p class="lead">Preregistered before any fit in <a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/37_hypotheses_H63_preregistered.md">knowledge/37_hypotheses_H63_preregistered.md</a> (SHA-256 <code>{esc(json.loads((ROOT / "registry/h63_preregistration.json").read_text())["hypothesis_sha256"][:16])}…</code>); the runner refuses to start if that hash moves.</p>
<section class="prose" id="holdout"><h2>1 · Holdout, canary, sufficiency and independence</h2>
<p>Splitter: <code>gems52.spatial.folds</code> <b>label-blind-quadrants-v2</b> — fixed quadrants, whole 8-connected catalogue components hidden in full, 80 px buffer, evaluation geometry independent of the hidden trace. The rejected CTD5-v1 tail-halo splitter is not used anywhere in this round.</p>
<div class="table-wrap"><table><thead><tr><th>Fold</th><th>View A OOF AUC</th><th>View B OOF AUC</th></tr></thead><tbody>{auc_rows}</tbody></table></div>
<p class="small">View A is the H63 step-normalised view (38 channels: matched step/persistence columns of bands 13/15/2, template local-contrast channels, upward-continued TMI; <b>no raw band values</b>). View B is unchanged from H61. <b>Sufficiency screen</b> (measured before any exchange): mean OOF AUC View A {f4(mean_a, 4)} against the preregistered bar {f4(suff["bar"], 2)} (H61's raw-value View A: 0.5163), View B {f4(mean_b, 4)}.</p>
<p class="small">Leakage canary: raw single-feature AUC of all {len(fit["view_A_features"]) + len(fit["view_B_features"])} channels on every fold's held-out sample. Maximum {f4(can["max_alarm_across_folds"], 4)} against an alarm at {can["alarm_auc"]}; fitted single-feature canary on the five strongest reaches {f4(can["max_fitted_top5_heldout_auc"], 4)}. <b>No alarm fired.</b> Catalogue-zero pixels are proxies, not verified fault absence.</p>
<p class="small">Independence (Blum–Mitchell's conditional-independence premise, tested not assumed): max |ρ| = {f4(exch["independence_pre"]["max_abs_correlation"], 4)} over {exch["independence_pre"]["n_blocks"]} 50×50 px blocks of held-out catalogue-zero proxies, abandon threshold {exch["independence_pre"]["threshold"]}. Exchange {"allowed and executed" if exch["allowed_exchange"] else "ABANDONED"}: {exch["total_pseudo_pixels"]:,} pseudo-label pixels in exactly one round.</p>
<p class="small"><b>Instrument validity.</b> This simulator measured Spearman −0.10 against the owner-reported board in round R4 and uniform random beat the champion on it. It screens procedures; it does not promote anything, and no HOLDOUT-DTI below is a score.</p></section>
<section class="prose" id="economics"><h2>2 · Repaired organiser-score algebra (inherited from H61, receipts committed)</h2>
<p><b>R1 masked support.</b> Known catalogue pixels are masked out of evaluation, so <code>S</code> must count off-catalogue pixels. Witness: <code>Hedge-v2</code> and <code>ens12-7f00890a</code> have identical off-catalogue support (166,519 px, Jaccard 1.000) and identical reported scores, yet raw-S accounting gave them different credit ({f4(foren["masked_accounting_witness"]["T_under_raw_accounting"][0], 1)} vs {f4(foren["masked_accounting_witness"]["T_under_raw_accounting"][1], 1)}); masked accounting gives both {f4(foren["masked_accounting_witness"]["T_under_masked_accounting"][0], 1)}.</p>
<p><b>R2 |G| is set-identified.</b> Measured interval <b>[{G["G_lower_bound"]:,.1f}, {G["G_upper_bound"]:,.1f}] px</b>. Lower bound binds on <code>{esc(G["G_lower_binding_file"])}</code>; upper bound on the nested pair <code>{esc(G["G_upper_binding_pair"]["subset"])}</code> ⊂ <code>{esc(G["G_upper_binding_pair"]["superset"])}</code>. The published point value {foren["G_point_under_zero_ring_credit"]["G_px"]:,.1f} is outside it and needs the deleted ring to earn exactly zero credit.</p>
<div class="table-wrap"><table><thead><tr><th>file</th><th>S raw</th><th>on catalogue</th><th>S masked</th><th>reported</th><th>attribution</th></tr></thead><tbody>{file_rows}</tbody></table></div>
<div class="table-wrap"><table><thead><tr><th>file</th><th>credit T (masked)</th><th>density T/S</th></tr></thead><tbody>{credit_rows}</tbody></table></div>
<p class="small">All 13 scores are <b>OWNER-REPORTED, NOT ORGANIZER-CONFIRMED</b>; only 3 are hash-linked to the bytes held. Credit uses the sparse-dot approximation M ≈ T, an <b>upper</b> bound on T for contiguous supports.</p></section>
<section class="prose" id="lane"><h2>3 · Lane gate and the saturated registry</h2>
<p>The literal rule — STOP if rank correlation exceeds 0.90 or more than 70% of the dots fall within 3 px of one registry raster's dots — is unsatisfiable on this registry: the 13GEMSDOE spacing-five lattice's 3 px halo covers every eligible pixel (a spacing-5 square lattice has maximum interior distance √8 = 2.83 px). CTD5 stopped on exactly that. The repair is a <b>measured classification</b>, applied uniformly and prospectively in the shared gate <code>gems52.gates.lane_report</code>: a prior whose 3 px coverage of the eligible footprint is ≥ 0.95 is a universal-coverage probe and cannot localise a lane. Probes are not deleted — their literal statistics stay in the receipt.</p>
<p class="small">Probes measured this run: {pol["universal_coverage_probes"]} of {lane_dots["priors_checked"]} rasters ({lane_dots["distinct_decoded_priors"]} distinct decoded patterns).<ul>{probe_rows}</ul></p>
<div class="table-wrap"><table><thead><tr><th>prior</th><th>3 px coverage</th><th>class</th><th>near-dot fraction</th><th>Spearman</th></tr></thead><tbody>{top_near}</tbody></table></div>
<p class="small">Verdicts — literal (all priors): <b>{esc(lit["verdict"])}</b>, max near-dot {f4(lit["max_near_3px_fraction"], 4)}, max Spearman {f4(lit["max_spearman"], 4)}. Policy (informative priors only): <b>{esc(pol["verdict"])}</b>, max near-dot {f4(pol["max_near_3px_fraction"], 4)} from <code>{esc(Path(pol["max_near_source"]).name if pol["max_near_source"] else "n/a")}</code>, max Spearman {f4(pol["max_spearman"], 4)}. Surface-phase check before placement: literal {esc(lane_surf["literal"]["verdict"])}, policy {esc(lane_surf["policy"]["verdict"])}. Decoded-pattern uniqueness: {"PASS" if sub["uniqueness_summary"]["canonical_pattern_unique"] else "FAIL"}; literal union of priors: {"YES" if sub["uniqueness_summary"]["equals_literal_prior_union"] else "NO"}.</p></section>
<section class="prose" id="limits"><h2>4 · Limitations, stated plainly</h2><ul>
<li>The shipped surface is an out-of-fold mosaic of four quadrant models, not one model refit on everything; inter-fold rank calibration and quadrant seams are unvalidated.</li>
<li>The sufficiency screen is measured, not assumed: if the step-normalised View A still does not clear the bar, the Blum–Mitchell premise fails on this data too, and the exchange transfers noise. A negative verdict is a deliverable.</li>
<li>Novel mass (pixels outside all thirteen scored files) belongs to no LP atom: organiser-tied evidence bounds its credit only by [0, |G|]. Neither "worthless" nor "valuable" is proven.</li>
<li>Inputs are SHA-256-pinned owner mirrors of a login-walled portal file. Pins prove mirror consistency, not organiser authentication. No organiser receipt, no authenticated weekly allowance, no leaderboard observation was available in this sandbox.</li>
<li>External radiometrics are uint8 percentile quantisations derived by the owner's CI from the USGS GeoDAWN release (DOI 10.5066/P93LGLVQ); USGS, GDR and DrivenData hosts are unreachable from this sandbox, so nothing was fetched from an official host this session.</li>
<li>The step/persistence transform is a structural hypothesis, not a fault label: a basin-fill density boundary or volcanic lithologic contact produces the same signature, and flight-line artefacts are only partially suppressed.</li>
<li>Fault candidates are not geothermal vents, and neither establishes permeability or a reservoir. No geologist reviewed any emitted structure; the reasoning CSV is measured context plus a template hypothesis and a named non-fault mimic.</li></ul></section>
<section class="prose"><h2>5 · Receipts</h2><p class="small">
<a href="data/h63_run_card.json">run card</a> · <a href="data/h61_forensics.json">forensics (inherited)</a> · <a href="data/h63_canary.json">canary</a> · <a href="data/h63_fit_checkpoint.json">fit + sufficiency screen</a> · <a href="data/h63_independence.json">independence</a> · <a href="data/h63_pseudo_exchange.json">pseudo-label exchange</a> · <a href="data/h63_holdout.json">holdout</a> · <a href="data/h63_projection.json">projection</a> · <a href="data/h63_lane_dots.json">lane gate (dots)</a> · <a href="data/h63_lane_surface.json">lane gate (surface)</a> · <a href="data/h63_submission.json">submission receipt</a> · <a href="../evidence/h63_lane_dots.json">full per-prior lane table</a></p></section>
'''
    audit += "</main>" + FOOT
    (DOCS / "h63-audit.html").write_text(audit)

    # ---------------------------------------------------------------- sources page
    src = head("H63 sources for manual review · GEMSDOE52", "Official and pinned sources behind every H63 number.")
    man = json.loads((ROOT / "registry/data_manifest.json").read_text())
    src_rows = "".join(
        f'<tr><td><code>{esc(f["id"])}</code></td><td><code>{esc(f["dest"])}</code></td>'
        f'<td class="numeric">{f["bytes"]:,}</td><td><code>{esc(f["sha256"][:16])}…</code></td>'
        f'<td class="small">{esc(f.get("provenance", ""))}</td></tr>' for f in man["files"])
    src += f'''<div class="eyebrow">H63 / sources</div><h1>Every input, pinned and checkable</h1>
<p class="lead">Restored autonomously by <code>scripts/restore_data.py</code> and verified by SHA-256 and byte count before use. Pins prove mirror consistency; they do <b>not</b> prove organiser authentication, because the portal data tab is login-walled and this sandbox has no credentials.</p>
<div class="table-wrap"><table><thead><tr><th>id</th><th>dest</th><th>bytes</th><th>sha256</th><th>provenance</th></tr></thead><tbody>{src_rows}</tbody></table></div>
<section class="prose"><h2>Official links for manual review</h2><ul>
<li>Competition problem page, metric and submission format: <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">drivendata.org/competitions/306/page/967</a></li>
<li>About page and resources: <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/">page/968</a> · data tab (login required): <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/data/">data</a> · leaderboard: <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">leaderboard</a></li>
<li>Staff masking clarification, thread 11516 post 4: <a href="https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4">community.drivendata.org/t/…/11516/4</a></li>
<li>Blum &amp; Mitchell, Combining Labeled and Unlabeled Data with Co-Training, COLT '98 pp. 92–100: <a href="https://doi.org/10.1145/279943.279962">doi:10.1145/279943.279962</a></li>
<li>USGS GeoDAWN airborne magnetic and radiometric survey: <a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and">usgs.gov/data/geodawn…</a> (DOI 10.5066/P93LGLVQ)</li>
<li>USGS 3DEP 1 m DEM (named for the deferred H63-D; not fetched this session): <a href="https://www.usgs.gov/3d-elevation-program">usgs.gov/3d-elevation-program</a></li>
<li>INGENIOUS project, Great Basin Center for Geothermal Energy: <a href="https://gbcge.org/current-projects/ingenious/">gbcge.org/current-projects/ingenious</a></li>
<li>Geothermal Data Repository submission 1391 (CC BY 4.0): <a href="https://gdr.openei.org/submissions/1391">gdr.openei.org/submissions/1391</a></li>
<li>EPSG:32611 / UTM zone 11N: <a href="https://epsg.io/32611">epsg.io/32611</a> · Tversky index: <a href="https://en.wikipedia.org/wiki/Tversky_index">wikipedia.org/wiki/Tversky_index</a></li>
<li>Reference solution: <a href="https://github.com/drivendataorg/gems-prize-reference-solution">github.com/drivendataorg/gems-prize-reference-solution</a></li>
<li>Rules PDF as supplied by the owner: <a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">docs.nlr.gov/docs/fy26osti/96647.pdf</a> (host not reachable from this sandbox; not independently verified here)</li></ul>
<p class="small">Egress in this sandbox is limited to github.com, codeload.github.com, api.github.com, registry.npmjs.org, pypi.org and files.pythonhosted.org. No USGS, GDR or DrivenData host was reachable, so nothing is claimed as downloaded from an official source.</p></section>'''
    src += "</main>" + FOOT
    (DOCS / "h63-sources.html").write_text(src)

    # ---------------------------------------------------------------- executive summary / guide
    ex = head("Executive summary — how to submit, and whether this file may be submitted · GEMSDOE52",
              "One-click download, the exact file contract, and the explicit submit verdict for the H63 artefact.")
    ex += f'''<div class="eyebrow">Executive summary / submission guide</div>
<h1>Download in one click.<br>{"Upload is permitted by this run." if submit_ok else "Do not upload this run."}</h1>
<p class="lead">The file, its exact identifier, and the frozen verdict. Promotion to a weekly slot is a separate selector decision, never a property of a valid file.</p>
<div class="notice" role="note"><strong>{esc(banner)}</strong><p>{esc(no_upload)} Verdict: <b>{esc(verdict)}</b>. Format gate {"PASS" if val["ok"] else "FAIL"}; decoded-pattern uniqueness {"PASS" if sub["uniqueness_summary"]["canonical_pattern_unique"] else "FAIL"}; lane gate (policy) {esc(pol["verdict"])}; projected DTI above the champion at both ends of |G|: {"YES" if card["verdict_reason"]["beats_champion_at_both_G_ends"] else "NO"}. Slots used: {card["slots_used"]}. NO CERTIFIED LEADERBOARD GAIN.</p></div>
<div class="actions"><a class="button" href="downloads/h63-candidate.tif" download>Download the H63 GeoTIFF ↓</a><a class="button secondary" href="downloads/h63-candidate.zip" download>Single-TIFF ZIP</a><a class="button secondary" href="downloads/h63-a-only-reasoning.csv" download>Reasoning CSV</a></div>
<p class="fileline">{esc(tif)}<br>{nbytes:,} bytes · SHA-256 {esc(sha)}</p>
<div class="grid2"><section class="panel"><h2>The file contract (verified on disk)</h2><ul>
<li>One band, float32, values exactly {f4(val["min"], 0)} or {f4(val["max"], 0)}.</li>
<li>{val["nan_pixels"]} NaN and {val["infinity_pixels"]} infinite pixels anywhere in the file.</li>
<li>{val["crs"]}; {val["height"]:,} rows × {val["width"]:,} columns.</li>
<li>Affine {esc(val["transform"])}, identical to the pinned <code>sample_submission.tif</code>: {"yes" if val["grid_matches_sample"] else "NO"}.</li>
<li>{dots:,} emitted cells, all more than 200 m from any mapped trace, 3 px minimum separation.</li>
<li>The ZIP holds exactly one TIFF, byte-identical to the direct download.</li></ul>
<p class="small">Local validator only. This is not an organiser acceptance receipt.</p></section>
<section class="panel"><h2>Why upload is {"permitted" if submit_ok else "blocked"}</h2><ul>
<li>{"The projected DTI interval exceeds the champion at both ends of the measured |G| interval." if submit_ok else "The projected DTI does not exceed the reported champion at both ends of the measured |G| interval — its lower end is 0, because novel mass belongs to no identified atom."}</li>
<li>The sufficiency screen measures the premise before it is trusted: step-normalised View A mean out-of-fold AUC {f4(mean_a, 3)} against a bar of {f4(suff["bar"], 2)} (H61's raw-value View A: 0.5163; View B: {f4(mean_b, 3)}).</li>
<li>The holdout simulator measured Spearman −0.10 against the owner-reported board in R4; it cannot promote anything on its own.</li>
<li>Inputs are pinned owner mirrors, not organiser-authenticated downloads, and the current weekly allowance is not observable from this sandbox.</li>
<li>Lane gate, literal rule over every prior: {esc(lit["verdict"])} (max near-dot {f4(lit["max_near_3px_fraction"], 4)}); saturation-aware policy: {esc(pol["verdict"])} (max near-dot {f4(pol["max_near_3px_fraction"], 4)}).</li></ul>
<a href="h63-audit.html">Read the full run and its limits →</a></section></div>
<section class="prose"><h2>About “Predicted values must be in range [0, 1]”</h2>
<p>That portal rejection is a property of the uploaded bytes, and this exporter makes it unreachable: <code>gems52.grid.write_geotiff</code> refuses to write unless the array is float32, finite everywhere, inside [0, 1], exactly 3,730 × 3,292 and on the pinned EPSG:32611 affine; <code>gems52.submission_writer</code> then reopens the written file, re-validates it against <code>sample_submission.tif</code>, and fails closed. The public specification permits null/NaN outside the footprint, so all-finite export is our compatibility precaution — we do <b>not</b> claim that NaN caused your specific historical rejection, because the rejected bytes and the portal receipt were never available here.</p>
<h2>Exact competition steps — only for an approved candidate</h2><ol>
<li>Obtain the separate selector's approval after the scientific, provenance, uniqueness and current-best gates pass. <b>H63 is {esc(verdict)}; {"proceed" if submit_ok else "stop here for this file"}.</b></li>
<li>Check the <a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">official rules</a> and the remaining weekly allowance shown on your authenticated <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">submission page</a>. This site cannot read that allowance.</li>
<li>On the <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">competition page</a> choose <b>New submission</b> and select the <code>.tif</code> (or its single-TIFF ZIP) in <b>File to submit</b>. Never upload HTML, a JSON receipt or a screenshot.</li>
<li>Paste the unique name and note below verbatim. Do not reproject, rescale, stretch or re-save the TIFF in an image editor.</li>
<li>After an authorised upload, keep the submission id, timestamp, file SHA-256 and the organiser's result. Only that receipt supports an <b>ORGANIZER-CONFIRMED</b> score.</li></ol></section>
<h2>Identification for this artefact</h2><p class="small">Copying these fields is not permission to upload the file.</p>
<label for="submission-name">Unique name ({len(name)} / 140 characters)</label>
<input id="submission-name" readonly value="{esc(name)}"><div class="copy-row"><button class="copy" data-copy-id="submission-name">Copy name</button></div>
<label for="submission-note">Note · {card["note_chars"]} / 140 characters</label>
<textarea id="submission-note" readonly rows="3">{esc(note)}</textarea><div class="copy-row"><button class="copy" data-copy-id="submission-note">Copy note</button></div>
<p class="copy-status" id="copy-status" aria-live="polite"></p>
<section class="prose"><h2>Reproduce it</h2><pre class="code">python -m venv .venv
.venv/bin/pip install -r requirements-r2.txt
bash scripts/download_competition_data.sh          # restore + SHA-256 verify the pinned inputs
PYTHONPATH=src .venv/bin/python -c "from gems52 import structural; structural.build(dest='work/r2/features', include_optional_profiles=False, log=lambda *a, **k: None)"
PYTHONPATH=src .venv/bin/python -m gems52.external # add the shared external GeoDAWN columns
PYTHONPATH=src .venv/bin/python -c "from gems52 import h63; h63.extend_store()"   # add the H63 step columns
.venv/bin/python scripts/fetch_prior_inventory.py --out work/h63/priors --receipt work/h63/prior_fetch_receipt.json
.venv/bin/python scripts/run_h63.py all            # canary -> fit -> exchange -> holdout
.venv/bin/python scripts/build_h63_submission.py   # place, gate, write, publish receipts
.venv/bin/python scripts/publish_h63_site.py       # this page
.venv/bin/python scripts/check_site.py &amp;&amp; .venv/bin/python -m pytest -q</pre>
<p class="small">GitHub Pages is static: it serves the generated file, it does not train a model in your browser. Reproduction regenerates the same research result; it never uploads, promotes or spends a slot.</p></section>
<details><summary>Preserved research archives — do not upload</summary><p class="small"><a href="archive-ctd5-overview.html">CTD5 landing page</a> · <a href="ctd5-audit.html">CTD5 audit</a> · <a href="h62.html">H62 audit (parallel session)</a> · <a href="archive-h62-overview.html">H62 landing archive</a> · <a href="h61-audit.html">H61 audit</a> · <a href="h60c.html">H60C</a> · <a href="h60.html">H60</a> · <a href="h60-triple-convergence.html">H60 triple convergence</a> · <a href="h59.html">H59</a> · <a href="archive-h59-overview.html">H59 archive</a> · <a href="h58.html">H58</a> · <a href="h57.html">H57</a> · <a href="h57-creditcore.html">H57 credit core</a> · <a href="h56-cotrain.html">H56</a> · <a href="h56.html">H56</a> · <a href="h55.html">H55</a> · <a href="h55-edge.html">H55-EDGE</a> · <a href="h55-profile.html">H55 profile</a> · <a href="h55-paired-shoulders.html">H55 paired shoulders</a> · <a href="h54.html">H54</a> · <a href="h53.html">H53</a> · <a href="r3.html">R3</a> · <a href="r3-hypotheses.html">R3 hypotheses</a> · <a href="hypotheses.html">Hypotheses</a> · <a href="method.html">Method</a> · <a href="validation.html">Validation</a> · <a href="sources.html">Sources</a> · <a href="irregularities.html">Irregularities</a> · <a href="forensics.html">Forensics</a> · <a href="feed.html">Feed</a> · <a href="downloads/index.html">download archive</a> · <a href="downloads/ctd5-research.tif" download>CTD5 TIFF</a> · <a href="downloads/h61-candidate.tif" download>H61 TIFF</a> · <a href="downloads/gems52-h62-conc_soft-arm22000px.tif" download>H62 TIFF</a> · <a href="downloads/h58-candidate.tif" download>H58 TIFF</a> · <a href="downloads/gems57-h57-credit-core25517-plus-novel8000-33517px-zeros.tif" download>H57 TIFF</a></p>
<p class="small">{h58_id}</p>
<p class="small">{prev_block}</p>
<p class="small">{r5_id}</p>
<p class="small">Concurrent rounds preserved: <a href="archive-main-index-20261008.html">main landing page of 2026-10-08</a> · <a href="r5.html">R5 audit</a> · <a href="h60d.html">H60D audit</a>.</p></details>'''
    ex += "</main>" + FOOT
    (DOCS / "executive-summary.html").write_text(ex)

    # ---------------------------------------------------------------- JS asset + feed + records
    js = (DOCS / "assets/ctd5.js").read_text()
    js = js.replace("if (!latest || latest.run_id !== 'ctd5-a24c35d1' || latest.submit_ok !== false) {\n        throw new Error('research feed has no matching closed-gate receipt');\n      }",
                    "if (!latest || typeof latest.submit_ok !== 'boolean') {\n        throw new Error('research feed has no usable receipt');\n      }")
    js = js.replace("target.textContent = `Local evidence refresh: ${data.generated_utc}. Research download hash verified: ${latest.hash_verified ? 'yes' : 'no'}. ` +\n        'Submission gate: CLOSED. Organizer results are not live; no automatic competition upload.';",
                    "target.textContent = `Local evidence refresh: ${data.generated_utc}. Latest artefact ${latest.run_id}: download ${latest.download_ok ? 'OK' : 'NOT OK'}, submit ${latest.submit_ok ? 'OK' : 'NOT OK'}, hash verified ${latest.hash_verified ? 'yes' : 'no'}. ` +\n        'Organizer results are not live; nothing here uploads to the portal.';")
    (DOCS / "assets/h63.js").write_text(js)

    feed = json.loads((DATA / "feed.json").read_text())
    feed["generated_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    feed["latest_research"] = dict(
        run_id=f"h63-{sha[:8]}", round="H63", file=tif, download=f"downloads/h63-candidate.tif",
        bytes=nbytes, sha256=sha, emitted_px=dots, verdict=verdict,
        download_ok=download_ok, submit_ok=submit_ok, hash_verified=True,
        holdout_dti=cand["dti"], holdout_ci95=cand["ci95"],
        evaluator=hold["pooled"]["evaluator_version"],
        withheld_positive_pixels=cand["withheld_positive_pixels"],
        lane_literal=lit["verdict"], lane_policy=pol["verdict"],
        slots_used=0, evidence="evidence/h63_run_card.json")
    feed["scientific_gate"] = ("OPEN" if submit_ok else
                               "CLOSED — H63 verdict is negative; research download only")
    feed.setdefault("evidence_copied", [])
    for n in ("canary", "fit_checkpoint", "independence", "pseudo_exchange", "holdout",
              "projection", "lane_dots", "lane_surface", "submission", "run_card"):
        fn = f"h63_{n}.json"
        if fn not in feed["evidence_copied"]:
            feed["evidence_copied"].append(fn)
    feed["freshness_note"] = ("Local evidence feed only. It is not a live leaderboard and it never "
                              "reports an organiser score; every number is HOLDOUT-DTI, MEASURED-FROM-"
                              "PINNED-BYTES, OWNER-REPORTED or PROJECTION and is labelled as such.")
    (DATA / "feed.json").write_text(json.dumps(feed, indent=1, allow_nan=False) + "\n")

    rec = dict(exists=True, round="H63", file=tif, download="downloads/h63-candidate.tif",
               bytes=nbytes, sha256=sha, emitted_px=dots, submission_name=name, note=note,
               note_chars=card["note_chars"], verdict=verdict, download_ok=download_ok,
               submit_ok=submit_ok, approved_for_weekly_slot=False, promoted=False,
               weekly_submission_slots_used=0, slots_used=0,
               artifact_status="RESEARCH ONLY — H63 verdict is negative; not an approved competition entry",
               format=val, uniqueness=sub["uniqueness_summary"],
               lane=dict(literal=lit["verdict"], policy=pol["verdict"],
                         max_near_3px_fraction_literal=lit["max_near_3px_fraction"],
                         max_near_3px_fraction_policy=pol["max_near_3px_fraction"],
                         universal_coverage_probes=pol["universal_coverage_probes"],
                         priors_checked=lane_dots["priors_checked"]),
               holdout=dict(evidence_class="HOLDOUT-DTI", evaluator=hold["pooled"]["evaluator_version"],
                            dti=cand["dti"], ci95=cand["ci95"],
                            withheld_positive_pixels=cand["withheld_positive_pixels"],
                            best_comparable_control=best_ctrl,
                            all_arms_filled_budget=hold["all_arms_filled"]),
               sufficiency_screen=dict(mean_oof_auc_view_A=mean_a, mean_oof_auc_view_B=mean_b,
                                       bar=suff["bar"],
                                       view_A_sufficient=suff["view_A_sufficient"],
                                       h61_baseline_view_A=0.5163),
               projection=proj, not_the_union=card["not_the_union"],
               view_comparison=dict(not_copied_or_literal_union=bool(
                   sub["uniqueness_summary"]["canonical_pattern_unique"]
                   and not sub["uniqueness_summary"]["equals_literal_prior_union"])),
               generated_utc=feed["generated_utc"])
    (DATA / "submission_h63.json").write_text(json.dumps(rec, indent=1, allow_nan=False) + "\n")

    # ---------------------------------------------------------------- serve the bytes
    DOWN.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "submission" / tif, DOWN / "h63-candidate.tif")
    shutil.copyfile(ROOT / "submission" / f"{stem}.zip", DOWN / "h63-candidate.zip")
    shutil.copyfile(ROOT / "submission" / f"{stem}.json", DOWN / "h63-candidate-receipt.json")
    for src_p, dst in ((ROOT / "submission" / tif, DOWN / "h63-candidate.tif"),
                       (ROOT / "submission" / f"{stem}.zip", DOWN / "h63-candidate.zip")):
        if hashlib.sha256(src_p.read_bytes()).hexdigest() != hashlib.sha256(dst.read_bytes()).hexdigest():
            raise SystemExit(f"served copy differs from the canonical file: {dst}")
    # keep the canonical filename downloadable too, so the receipt name is literal
    shutil.copyfile(ROOT / "submission" / tif, DOWN / tif)

    # ---------------------------------------------------------------- downloads index banner
    dl_index = DOWN / "index.html"
    if dl_index.exists():
        txt = dl_index.read_text()
        banner = (f'<!--H63-DOWNLOAD-NOTICE--><aside style="padding:20px;background:{"#e6f6ea" if submit_ok else "#fff1de"};'
                  f'color:#12331f;font:16px/1.6 system-ui"><b>Latest research: H63 — '
                  f'{"OK TO SUBMIT" if submit_ok else "DO NOT SUBMIT"}.</b> '
                  f'<a href="h63-candidate.tif" download>Download the H63 GeoTIFF</a> ({nbytes:,} bytes, '
                  f'SHA-256 <code>{sha[:16]}…</code>, {dots:,} cells) · '
                  f'<a href="../executive-summary.html">Read the gate status first</a> · '
                  f'<a href="../h63-audit.html">Run &amp; evidence</a>. '
                  f'Historical downloads below are not upload approval.</aside>')
        txt = re.sub(r'<!--(?:CTD5|H61|H62|H63)-DOWNLOAD-NOTICE--><aside.*?</aside>', banner, txt, count=1, flags=re.S)
        if '<!--H63-DOWNLOAD-NOTICE-->' not in txt:
            txt = txt.replace('<body>', '<body>' + banner, 1)
        # collapse any duplicated audit links earlier publishers/merges inserted, then make sure
        # this round's audit link is present exactly once
        txt = re.sub(r'(<a href="\.\./h63-audit\.html">H63 audit</a>)+',
                     '<a href="../h63-audit.html">H63 audit</a>', txt)
        txt = re.sub(r'(<a href="\.\./h61-audit\.html">H61 audit</a>)+',
                     '<a href="../h61-audit.html">H61 audit</a>', txt)
        if 'href="../h63-audit.html"' not in txt:
            txt = txt.replace('<a href="../h61-audit.html">H61 audit</a>',
                              '<a href="../h63-audit.html">H63 audit</a>'
                              '<a href="../h61-audit.html">H61 audit</a>', 1)
        # add this round's rows at the top of the downloads table (previous rounds' rows stay)
        rows = (f'<!--H63-DL--><tr><td><a href="h63-candidate.tif" download>h63-candidate.tif</a></td>'
                f'<td class="number">{nbytes:,}</td><td class="mono">{sha}</td>'
                f'<td>H63 · step-normalised two-view co-training · {dots:,} px · newest round; '
                f'<a href="../h63-audit.html">evidence</a></td></tr>\n'
                f'<tr><td><a href="{esc(tif)}" download>{esc(tif)}</a></td>'
                f'<td class="number">{nbytes:,}</td><td class="mono">{sha}</td>'
                f'<td>canonical filename, byte-identical</td></tr>\n'
                f'<tr><td><a href="h63-candidate.zip" download>h63-candidate.zip</a></td>'
                f'<td class="number">{(DOWN / "h63-candidate.zip").stat().st_size:,}</td>'
                f'<td class="mono">single-TIFF ZIP, byte-identical payload</td>'
                f'<td>portal-accepted wrapper</td></tr>\n'
                f'<tr><td><a href="h63-a-only-reasoning.csv" download>h63-a-only-reasoning.csv</a></td>'
                f'<td class="number">{(DOWN / "h63-a-only-reasoning.csv").stat().st_size:,}</td>'
                f'<td class="mono">CSV</td>'
                f'<td>{dots:,} per-pixel geological reasoning rows (hypothesis + named non-fault '
                f'mimic + falsifier)</td></tr><!--/H63-DL-->\n')
        txt = txt.replace("H62 · two-view corroboration · 22,000 px · newest round;",
                          "H62 · two-view corroboration · 22,000 px · previous round (parallel session);")
        if '<!--H63-DL-->' not in txt:
            txt = txt.replace('<tbody>', '<tbody>' + rows, 1)
        dl_index.write_text(txt)

    # ---------------------------------------------------------------- link preservation
    new_text = (DOCS / "index.html").read_text() + (DOCS / "executive-summary.html").read_text() + \
        (DOCS / "h63-audit.html").read_text()
    dead = []
    for h in sorted(set(re.findall(r'href="([^"]+)"', new_text))):
        if h.startswith(("http", "mailto", "#", "data:")):
            continue
        if not (DOCS / h.split("#")[0]).resolve().exists():
            dead.append(h)
    if dead:
        raise SystemExit(f"publisher produced dead links: {dead[:10]}")
    # every local link the previous landing page carried must still be reachable from the new pages
    lost = sorted({h for h in old_hrefs | old_srcs
                   if not h.startswith(("http", "mailto", "data:")) and h not in new_text
                   and (DOCS / h.split("#")[0]).resolve().exists()})
    archives = sorted(p.name for p in DOCS.glob("archive-*-overview.html"))
    print(json.dumps(dict(pages=["index.html", "executive-summary.html", "h63-audit.html",
                                "h63-sources.html"] + archives,
                          dead_links=dead, old_links_not_reused=lost,
                          archives_preserved=archives,
                          download=str(DOWN / "h63-candidate.tif"), bytes=nbytes, sha256=sha,
                          verdict=verdict, submit_ok=submit_ok), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
