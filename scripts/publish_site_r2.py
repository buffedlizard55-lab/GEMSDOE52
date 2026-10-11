#!/usr/bin/env python3
"""Build the audited static site from actual R2 receipts, never from projected scores."""
from pathlib import Path
import hashlib
import html
import json

import numpy as np
import rasterio
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
EV = ROOT / 'evidence'


def read(name):
    return json.loads((EV / (name + '_r2.json')).read_text())


def esc(value):
    return html.escape(str(value))


def link(path, text=None):
    return f'<a href="{esc(path)}">{esc(text or path)}</a>'


def table(headers, rows, primary=None):
    cells = []
    for row in rows:
        cls = ' class="primary"' if primary is not None and row[0] == primary else ''
        cells.append(f'<tr{cls}>' + ''.join(f'<td>{v}</td>' for v in row) + '</tr>')
    return '<div class="table-wrap"><table><thead><tr>' + ''.join(f'<th>{esc(v)}</th>' for v in headers) + '</tr></thead><tbody>' + ''.join(cells) + '</tbody></table></div>'


def page(name, title, body, r):
    menu = [('index.html', 'Overview'), ('executive-summary.html', 'Submission guide'),
            ('validation.html', 'Validation'), ('forensics.html', '0.2778 autopsy'), ('sources.html', 'Sources'), ('h53.html', 'Parallel H53')]
    nav = ''.join(link(p, t) for p, t in menu)
    bar = f'''<div class="download-bar"><div><strong>New R2 research GeoTIFF</strong><small>{esc(r['file'])}</small><small>FORMAT CHECKED · UNSCORED · NOT APPROVED FOR A WEEKLY SLOT</small></div><a class="button" href="downloads/{esc(r['file'])}" download>↓ Download .TIF</a></div>'''
    doc = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="New fault-prediction research TIFF, spatial validation and auditable source evidence. No unsupported leaderboard forecast."><title>{esc(title)} · GEMSDOE52</title><link rel="stylesheet" href="style.css"><script src="site.js" defer></script></head><body><a class="skip" href="#main">Skip to evidence</a><header><nav><a class="brand" href="index.html">GEMS / DOE 52</a>{nav}</nav></header><main id="main">{bar}{body}</main><footer>Competition 306 · Reproducible CPU research · Fault predictions, not confirmed geothermal vents. {link('irregularities.html','Limitations & review')} · {link('method.html','Method')} · {link('hypotheses.html','Hypotheses')} · {link('https://github.com/buffedlizard55-lab/GEMSDOE52','Code & complete prompt')}</footer></body></html>'''
    (DOCS / name).write_text(doc)


def preview(r):
    assets = DOCS / 'assets'
    assets.mkdir(exist_ok=True)
    with rasterio.open(DOCS / 'downloads' / r['file']) as src:
        pred, footprint = src.read(1), src.dataset_mask() > 0
    with rasterio.open(ROOT / 'data/labels.tif') as src:
        cat = src.read(1) == 1
    # Max-pool proposals and traces so downsampling cannot erase narrow lines.
    def pool(a, size=4):
        h, w = a.shape
        b = np.pad(a, ((0, (-h) % size), (0, (-w) % size)))
        return b.reshape(b.shape[0] // size, size, b.shape[1] // size, size).max((1, 3))
    fp, cp, pp = pool(footprint), pool(cat), pool(pred > 0)
    rgb = np.full(fp.shape + (3,), (237, 241, 233), np.uint8)
    rgb[fp] = (217, 226, 215)
    rgb[cp & fp] = (74, 113, 151)
    rgb[pp] = (202, 133, 57)
    im = Image.fromarray(rgb)
    draw = ImageDraw.Draw(im)
    draw.line((35, 60, 35, 24), fill=(24, 51, 46), width=3)
    draw.polygon([(35, 19), (29, 30), (41, 30)], fill=(24, 51, 46))
    draw.text((30, 6), 'N', fill=(24, 51, 46))
    im.save(assets / 'prediction-r2.png')


def main():
    # This R2 publisher predates the current H75 terminal-stop status pages and writes
    # shared root/download pages. Fail closed rather than replacing a newer reviewed status.
    index = DOCS / 'index.html'
    h75_status = DOCS / 'h75-executive-summary.html'
    if index.is_file() and h75_status.is_file():
        current_index = index.read_text(errors='replace')
        current_h75 = h75_status.read_text(errors='replace')
        if ('H75: DUPLICATE/STOP' in current_index
                and 'NOT FOR SUBMISSION' in current_h75
                and 'no owner override' in current_h75.lower()):
            raise RuntimeError('Refusing to overwrite reviewed H75 shared pages with the historical R2 publisher.')
    r, h, u, why = read('submission'), read('holdout'), read('uniqueness'), read('a_only_reasoning')
    f, source = read('reference_forensics'), read('source_review')
    inv, verified = read('prior_inventory'), read('verified_claims')
    independent, pseudo = read('independence'), read('pseudo_exchange')
    actual = hashlib.sha256((DOCS / 'downloads' / r['file']).read_bytes()).hexdigest()
    assert actual == r['sha256'], 'Do not publish a raster different from its receipt'
    assert r['format']['ok'] and u['research_publication_ok'] and r['view_comparison']['not_merely_union']
    assert not r['validation']['approved_for_slot'], 'This research-only site requires a separate reviewed promotion workflow'
    preview(r)
    budget = r['stats']['emitted']
    gate = h['slot_gate']
    warning = '<div class="status"><strong>Research-only. Do not upload this run.</strong>The registered candidate did not beat the strongest comparable baseline. Download for review/reproduction, not permission to spend a competition slot. No organizer score or portal acceptance is claimed.</div>'
    cards = f'''<div class="grid"><div class="card"><div class="metric">{budget:,}</div><div class="label">new, kernel-placed unit predictions</div></div><div class="card"><div class="metric">{h['means']['structural_contrast']:.5f}</div><div class="label">mean local catalogue-holdout DTI</div></div><div class="card"><div class="metric">0 / 3</div><div class="label">weekly slots used by this work / official weekly limit</div></div></div>'''
    overview = f'''<div class="eyebrow">New model. Independent inference. Evidence first.</div><h1>Fault discovery,<br>without the false certainty.</h1><p class="lede">Geophysical–surface structural contrast on the Great Basin grid. A genuinely new prediction, a measured failed gate, and the evidence needed to decide what to try next.</p>{warning}{cards}<div class="two"><div><h2>What changed</h2><p>Signed gravity–cover normals, persistent gradients and surface curvature replace the old ad-hoc rank blend. The file was inferred from a newly fitted model using competition feature/label rasters only. No prior submission supplies a pixel or model feature.</p><p>Measured comparison: <strong>{h['means']['structural_contrast']:.5f}</strong> versus <strong>{h['means']['view_B']:.5f}</strong> for surface-only; paired lift <strong>{gate['mean_dti_lift']:+.5f}</strong>, {gate['positive_folds']}/4 folds positive. Local catalogue scores are not public leaderboard scores.</p><div class="actions">{link('method.html','Read the method →')} {link('validation.html','Inspect every fold →')}</div><h2>Unique, not a renamed reference</h2><p>{u['n_priors_checked']} aligned accessible prior files compared. No canonical decoded match. <strong>{100*u['novel_fraction']:.1f}%</strong> of emitted support is outside the binary / ≥0.5 continuous diagnostic union (the original 20% support-novelty diagnostic FAILED);  {u['prior_px_dropped']:,} prior-union cells are not emitted. A dense historical density-probe fills nearly the whole footprint, so zero support novelty against that union does not mean the sparse decoded pattern was copied. Independently placed A/B outputs are also not simply unioned; a same-budget max-view union differs at 32,553 emitted positions.</p><p class="small">Bounded audit, not global novelty or proof of new faults. NaN/sentinel prior cells are normalized to zero and values compared at float32 precision. See full comparison scope and exclusions.</p>{link('data/uniqueness_r2.json','Open every comparison →')}<h2>Reported 0.2778 — evidence classes and limits</h2><p><strong>PUBLIC-LEADERBOARD observation:</strong> the saved 2026-10-09 20:18 UTC board places extradr19 at 0.2778/rank 17 and the top row at 0.3774. The team-level row has no TIFF hash or receipt. <strong>OWNER-REPORTED attribution:</strong> the H33 file association is not organizer-authenticated. <strong>LOCAL pixel comparison:</strong> the 37,654-cell H33 bitmap is a strict subset of a separately 0.2600-labelled 44,090-cell bitmap; this is not proof of why a score changed. <strong>ORGANIZER-CONFIRMED receipt:</strong> none binds a submission ID, file hash, and 0.2778 score. Staff clarified that the known-fault mask is pixel-exact, only new-fault truth is scored, and new-fault truth may occur within 300 m of known traces. Near-trace pixels are not automatically zero-credit or penalized; no causal explanation is established.</p>{link('forensics.html','Read the evidence review →')}</div><figure><img src="assets/prediction-r2.png" alt="North-up template grid: known catalogue traces blue, new research predictions amber, survey footprint grey-green."><figcaption>Actual R2 output · north up · 4× max-pooling for display. Blue: known catalogue; amber: research proposals. Not verified fault discoveries or geothermal vents.</figcaption></figure></div><h2>Every A-only proposal gets a reason</h2><p>{why['rows']:,} emitted A-only pixels have individual coordinate, score, physical-signature, alternative-explanation and verification-status rows. These are falsifiable hypotheses, not expert certification.</p>{link('downloads/'+why['file'],'Download geological reasoning CSV →')}<div class="live-feed" id="feed">Automatic local evidence feed. The official board is a dated observation, not a live feed.</div><p class="small">Historical observation 2026-10-06: top row 0.3774; 0.3195 was rank 7. The later saved 2026-10-09 20:18 UTC observation places extradr19 at 0.2778/rank 17 and the top row at 0.3774; neither observation binds a file hash or receipt. DrivenData automatic access is disabled under its Terms; no artificial freshness is reported.</p>'''
    page('index.html', 'Fault mapping, evidence first', overview, r)
    guide = f'''<div class="eyebrow">R2 · historical research status</div>
<h1>Research download only.<br>NOT APPROVED FOR SUBMISSION.</h1>
{warning}
<p>This registered candidate failed its scientific promotion gate against the strongest comparable baseline. A local format check is not portal acceptance or submission eligibility. No upload instructions, owner override, paste-ready name/note, or weekly slot authorization is provided.</p>
<p>Historical file: <code>{esc(r['file'])}</code> · SHA-256 <code>{r['sha256']}</code>. Download, if available in the archive, is for research review only.</p>
<p>The local catalogue-proxy holdout is an internal measurement, not a leaderboard score or organizer-confirmed receipt. Public-board observations, owner-reported associations, local pixel comparisons, and organizer receipts remain separate evidence classes.</p>
<p><a href="validation.html">R2 validation and failed promotion gate</a> · <a href="forensics.html">0.2778 evidence review</a> · <a href="data/submission_r2.json">Historical machine-readable receipt</a></p>'''
    page('executive-summary.html', 'Submission guide', guide, r)
    names = {'raw_fusion':'Raw early fusion', 'view_A':'Geophysical view A', 'view_B':'Surface view B', 'naive_union':'Naive max/union field', 'structural_contrast':'Registered structural contrast', 'disagreement_router':'Disagreement router'}
    rows = []
    for arm in h['means']:
        rows.append([esc(names[arm])] + [f"{fold['arms'][arm]['dti']:.6f}" for fold in h['folds']] + [f"<strong>{h['means'][arm]:.6f}</strong>"])
    pseudo_rows = []
    for arm in ('view_A','view_B'):
        scores = [rr['views'][arm].get('dti_after_exchange', h['folds'][rr['fold']]['arms'][arm]['dti']) for rr in pseudo['rounds']]
        mean = sum(scores)/len(scores) if scores else h['means'][arm]
        pseudo_rows.append([esc(names[arm]), f"{h['means'][arm]:.6f}", f"{mean:.6f}", f"{mean-h['means'][arm]:+.6f}", str(sum(rr['views'][arm]['pixels'] for rr in pseudo['rounds']))])
    validation = f'''<div class="eyebrow">Whole-component spatial hide & recover</div><h1>The controls decide.</h1>{warning}<p>Four quadrant holds; entire original 8-connected components are assigned once, including their tails. An 80-pixel (8 km) Euclidean training buffer exceeds twice the maximum 36-pixel transform support. Zero original train/truth component overlap in all four receipts. Features are computed without labels; no held labels train a learner or pseudo-label a neighbor.</p>{table(['Arm','NW','NE','SW','SE','Mean local DTI'],rows, names['structural_contrast'])}<p>All arms use identical per-fold emitted density corresponding to the fixed global budget of 37,654. Kernel support is included at held boundaries; supported input footprint is 4,593,171 cells. Unsupported truth pixels remain FN rather than silently disappearing. Proxy negatives are catalogue-zero pixels outside the 300 m positive collar, not verified fault absence.</p><h2>Co-training: assumptions checked, outcome measured</h2><p>{independent['n_negative_predictions']:,} finite held-out proxy-negative predictions in {independent['n_blocks']:,} 50×50 blocks. Largest absolute Pearson/tie-aware Spearman: <strong>{independent['max_abs_correlation']:.4f}</strong>, below the frozen 0.60 rejection threshold. Missing, constant or too few blocks would disable exchange. Low correlation is a diagnostic, not proof of sufficient, compatible, conditionally independent views.</p>{table(['View','Before','After one round','Mean change','Pseudo-pixels across folds'],pseudo_rows)}<p>Only confident-donor/abstaining-receiver whole proposal components within one spatial block are accepted; boundary-crossing components are rejected, not clipped. Training-only and evaluation-pixel counts are published for every exchanged segment. Pseudo-label weight 0.25, cap 2,000 per direction/fold. This separate arm cannot replace the predeclared primary after looking at results.</p><h2>Why the slot remains closed</h2><p>Required ≥+0.005 versus the strongest comparable baseline, ≥3/4 positive folds, comparable frozen incumbent confirmation and format/novelty gates. Actual lift {gate['mean_dti_lift']:+.6f}, {gate['positive_folds']}/4 positive. Historical tip/live-mirror validations are not comparable; scoring their fully trained shipped TIFFs on these held labels would leak.</p><p>{link('data/holdout_r2.json','Every TP/FP/FN, fold and placement receipt')} · {link('data/independence_r2.json','All negative-error blocks')} · {link('data/pseudo_exchange_r2.json','Every pseudo-component')}</p><h2>Scope</h2><p>Catalogue proxy validation, one seed, four geographically dependent folds. No hidden-label truth, official score forecast, significance guarantee, conditional-independence proof or geothermal discovery certification.</p>'''
    page('validation.html','Validation & failed promotion gate',validation,r)
    forensic = f'''<div class="eyebrow">Evidence review · reported 0.2778</div>
<h1>Separate the public row from the file attribution.</h1>
<div class="status"><strong>No file-to-score receipt or causal explanation is established.</strong> The saved public-board row is team-level; the owner-reported H33 association and local pixel comparison do not authenticate an upload or explain a score change.</div>
<h2>Four evidence classes</h2>
{table(['Class','Evidence','Limit'],[
 ['PUBLIC-LEADERBOARD observation','Saved 2026-10-09 20:18 UTC: extradr19 0.2778/rank 17; top row 0.3774/rank 1.','No TIFF hash, submission ID, or receipt; 0.2778 is not the highest public score.'],
 ['OWNER-REPORTED attribution','Owner materials associate an H33-labelled raster with 0.2778.','Not organizer-authenticated.'],
 ['LOCAL pixel comparison','H33 has 37,654 cells and is a strict subset of a separate 44,090-cell bitmap labelled 0.2600 (6,436 removed, none added).','Local bytes only; does not establish hidden truth, score attribution, or causation.'],
 ['ORGANIZER-CONFIRMED receipt','None located binding a submission identifier, file hash, and 0.2778 score.','No organizer-confirmed file/score mapping is available.']])}
<h2>Scoring clarification and measured distances</h2>
<p>The local distance calculations are geometric relations to the provided known-fault raster. DrivenData staff clarified that the known-fault mask is pixel-exact and identical to the training fault labels, only new-fault truth is scored, and new-fault truth may occur within 300 m of known traces. Thus near-trace pixels are not automatically penalized or zero-credit. Hidden credit for locally removed cells is unknown.</p>
<p>The 0.2600-to-0.2778 byte comparison is not proof of why a score changed. No causal explanation is established. Any internal HOLDOUT-DTI value is a separate hide-and-recover measurement, not a public score or organizer receipt.</p>
<h2>Reviewable sources</h2><p>{link('https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/','Official public leaderboard')} · {link('https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4','Official staff clarification')} · {link('../knowledge/49_why_02778_phd_answer.md','Full evidence note')}</p>'''
    page('forensics.html','Why the reference reportedly scored 0.2778',forensic,r)
    method = '''<div class="eyebrow">Method / no reused predictions</div><h1>Two views.<br>One honest experiment.</h1><p>57 label-free feature columns: 19 raw, 17 geophysical transforms, 16 surface transforms and 5 cross-view terms. A uses magnetics (1,2,3,6,9,14), gravity (5,11,13,18), strain/geodetics (4,7,8), seismic context (10,16), cover/basement (15), and electrical conductivity (17). B uses detrended elevation (12) and slope (19), smoothed gradient/curvature and residual statistics. No radiometric bands exist in this 19-band file. Seismic density is 100 km context, not localized microseismicity.</p><h2>Signed-normal physical hypothesis</h2><p>Normalized convolution at Gaussian scales 1/3/8 px avoids zero-filled boundary edges. Derivatives, signed gravity–cover normal cosine, persistent gradients, tensor coherence and cross-view surface agreement distinguish potential structural boundaries from unsigned rank overlap. Opposed gravity/cover normals are physically plausible for basement relief, but lithology, inversion/model bias and acquisition artifacts are alternatives. Source models can share inputs, so derived features are not independent evidence by construction.</p><h2>Fixed learner, fixed test</h2><p>CPU histogram gradient boosting: 120 iterations, 15 leaves, 0.08 learning rate, L2=2, minimum leaf 80, no early stopping; balanced training weights and at most 160,000 proxy negatives. Seed 520206. No test-tuned hyperparameters or post-hoc primary choice. Feature arrays are atomically written, numerically re-opened and SHA checked; the feature index must exactly equal the eligible grid positions.</p><h2>Metric-aware does not mean metric-optimal</h2><p>Actual incremental triangular max-cover gains, zero-padded boundaries and deterministic lazy greedy updates. This optimizes a density-weighted coverage surrogate under a fixed budget on a restricted candidate pool, <strong>not expected DTI or a global binary optimum</strong>. Prior-adjusted model probabilities are proxies. The optional FP discount assumes independent Bernoulli truth and is unused for matched-budget validation. A ratio of expected terms is not an expected ratio.</p><h2>Geological review</h2><p>A-only requires a confident geophysical donor and an abstaining surface view. It may indicate cover but also lithologic edges, depth-model artifacts or acquisition effects. B-only can be a genuine surface fault or roads/drainage/fan edges. Neither class establishes a geothermal resource. Every emitted A-only pixel has a conditional reasoning row and alternatives, all marked unverified.</p><p><a href="data/r2_preregistration.json">Frozen configuration</a> · <a href="data/features_r2.json">Feature definitions and input/array hashes</a> · <a href="data/a_only_reasoning_r2.json">Reasoning coverage receipt</a> · <a href="https://www.cs.cmu.edu/~avrim/Papers/cotrain.pdf">Blum & Mitchell primary paper</a></p>'''
    page('method.html','Physical method & mathematical scope',method,r)
    hypotheses = '''<div class="eyebrow">Preregistered before implementation</div><h1>Physical hypotheses,<br>then a falsifiable test.</h1><p>Ranking is a planning judgment, not a claimed score improvement. All four hypotheses use the available core layers; no unavailable external data is represented as viable.</p>'''
    hypotheses += table(['Rank / cost','Layers & transform','Missing-fault mechanism / difference','Outcome'],[
        ['1 · medium','Gravity 13, cover/basement 15, detrended elevation 12; signed gradient-normal cosine at 1/3 px, persistence 3↔8, surface silence','Buried basement offsets may evade surface cataloguing. Explicit polarity and cross-scale persistence, not the old generic unsigned Hessian/rank fusion. Lithologic contacts are competing explanations.','Implemented; registered primary failed gate'],
        ['2 · medium','Detrended elevation 12, slope 19; paired along-normal shoulder contrast with local affine-plane removal','A persistent step across both shoulders versus symmetric drainage/fan shapes. Adds paired-shoulder geometry beyond existing scalar curvature. Related profile methods exist in sibling repos; no global novelty claim.','Next test; no scored result'],
        ['3 · medium-high','Magnetics 1/2/3/6/9/14 plus gravity; scale-persistent axis/orientation change at corridor bends','Rupture transfer/relay zones may interrupt an obvious mapped trace. Multi-scale geometric junction signal, not unconditional tip growth or every edge. Acquisition geometry can mimic it.','Not implemented; no claimed gain'],
        ['4 · low-medium','Raw and transformed A/B plus their confident disagreement; strict buffered, weighted one-round exchange','Missing structures with differing surface/deep responses. Whole proposal components, actual negative OOF gate and explicit abstention rather than legacy pixel promotion. Both views may be insufficient for buried faults.','Separate co-training trial; not used in TIFF']])
    hypotheses += '<p><a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/07_r2_hypotheses_preregistered.md">Full ranking, physical signatures and cost/expected-lift rationale</a> · <a href="data/r2_preregistration.json">Frozen parameter registration</a></p><h2>External-data rule</h2><p>Future 1 m elevation/radiometric/thermal studies need a free official release, a compatible sponsor-sharing license, successful resource-byte download, spatial coverage and provenance receipts <em>before</em> being called viable. GDR 1391 and GeoDAWN metadata are available and licensed; this run uses no new external derivative or geothermal point labels. Metadata availability is not evidence that a mirrored derivative is legally/provenance-valid.</p>'
    page('hypotheses.html','Ranked hypotheses & outcomes',hypotheses,r)
    source_rows = [[esc(c['id']), esc(c['claim']), link(c['source'],'Primary/manual-review link'), esc(c['status'])] for c in verified['claims']]
    source_body = '<div class="eyebrow">Claims / data / accessible prior inventory</div><h1>Follow every claim<br>back to evidence.</h1><p>Primary-source facts, owner-reported scores and local experiments are different evidence classes. Model success, new faults and geothermal vents are never inferred just from a source being public.</p>' + table(['ID','Bounded claim','Official/primary source','Verification class'], source_rows)
    source_body += '<h2>All supplied owner sites</h2><p>Source blobs are pinned to resolved GitHub commit/blob identities when direct HTTPS fails. A source mirror is <strong>not proof of deployed HTTP</strong> or organizer score attribution. TIFF aliases with the same Git blob are collapsed; numeric and mask equivalence are checked separately.</p>'
    sites = [entry for entry in source['entries'] if entry['id'].startswith('site:')]
    source_body += table(['Site','Source link','Transport/access','Methodology note'], [[esc(entry['id'].removeprefix('site:')), link(entry['url'],'Open supplied site'), esc(entry.get('access')), esc(entry.get('title') or entry.get('error') or 'not parsed')] for entry in sites])
    source_body += f'''<p>{len(inv['entries'])} TIFF inventory entries; {sum(bool(e.get('eligible_prior')) for e in inv['entries'])} accessible grid-aligned inventory objects. Input/wrong-grid/multiband and inaccessible records keep their reasons. Private/unlinked objects are not covered. The brief supplied no complete URL for 53GEMSDOE/54GEMSDOE; repository discovery is disclosed separately.</p><p>{link('data/source_review_r2.json','Every source request, source-blob identity and irregularity')} · {link('data/prior_inventory_r2.json','Every TIFF, alias, hash and exclusion')} · {link('data/restore_receipt_r2.json','All 23 restored input pins')} · {link('data/data_manifest.json','Restoration manifest')}</p><h2>Access & licenses</h2><p>Data-page login redirect verified. Core inputs came from owner mirrors; SHA integrity does not authenticate them against organizer bytes. No new external file is used for training. GeoDAWN metadata says CC0; INGENIOUS GDR 1391 says CC BY 4.0. Unresolved external derivative lineage/license means those files stay out of R2.</p><h2>Automatic feed, within source restrictions</h2><div class="live-feed" id="feed">Local-evidence JSON refreshes automatically; the board keeps its original observed date.</div><p>The scheduled job refreshes local receipts/hashes, not the restricted DrivenData board or portal. A live board feed needs documented permission or a sanctioned API. {link('data/source_policy.json','Full source policy')}</p>'''
    page('sources.html','Primary-source and data audit',source_body,r)
    irregularities = '''<div class="eyebrow">Three-pass review / limitations</div><h1>Errors are findings.<br>Not things to hide.</h1><ul><li><strong>Known-pixel penalty story retracted.</strong> H33 removed off-mask flanks. Exact-known predictions are masked, not taxed.</li><li><strong>Incorrect DTI simplifications fixed.</strong> Restored the TP denominator term; incremental credit is not universally nearest-truth weight. Removed the 224 m universal rule, inferred hidden prevalence and 0.464 ceiling.</li><li><strong>Old independence evidence invalid.</strong> It contained no negative OOF predictions, constant zero blocks and tie-wrong Spearman. Undefined now disables exchange; R2 actually measured held-out negative predictions.</li><li><strong>Input-array integrity defect caught.</strong> Initial validation aborted on a feature-index mapping mismatch. Arrays were rebuilt with atomic flushed writes, numerical rereads, index invariants and per-column SHA checks; no invalid scores were accepted. The underlying filesystem cause was not proven.</li><li><strong>No radiometric bands in the available stack.</strong> No invented data layers, LiDAR-only hidden-label claims or local microseismic locations.</li><li><strong>Geophysical view is weaker here.</strong> Low negative-error correlation did not make co-training win. Strong surface-only control prevented a false promotion.</li><li><strong>All-prior support novelty is not unique inference.</strong> A 5.1M-cell density-probe and high-ignorance diagnostic rasters saturate the union. Original ≥20% support-novelty test failed and remains reported. Canonical-pattern difference and non-literal A/B union are verified separately; no slot approval changed.</li><li><strong>Current public leader snapshot is 0.3774.</strong> 0.3195 is not the observed leader; no new official score or filename attribution is authenticated.</li><li><strong>Source/deployment gap disclosed.</strong> GitHub blob mirrors are not live-page proof. Input SHA pins are not organizer authentication or external derivative license proof.</li><li><strong>Portal behavior unknown.</strong> Raw range/mask/geometry checked locally; no actual upload or undocumented validator claim.</li><li><strong>Automatic access restricted.</strong> DrivenData scraping disabled after Terms review; automatic local feed does not fabricate external freshness.</li></ul><h2>Next session, in order</h2><ol><li>Read README’s full current prompt, the three-pass review and this failed gate first.</li><li>Freeze the surface-only control and untouched confirmation regions before trying R2-H2 paired-shoulder step geometry. Add calibrated residual-risk/stratified geological error analysis; do not pick a new primary retrospectively.</li><li>Refit the historical incumbent’s actual generative algorithm on the same whole-component folds, with all catalogue-derived exclusions recomputed from visible labels only. Shipped fully-trained TIFFs cannot serve as clean OOF incumbents.</li><li>Authenticate core files against organizer downloads when permitted; obtain official licensed resource bytes and coverage receipts for new 1 m/radiometric data before using them.</li><li>Obtain independent geological validation of A-only alternatives, then reconsider a weekly slot only after the frozen candidate clears the strongest baseline, confirmation, format and novelty gates.</li></ol><p><a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/09_r2_review.md">Full three-pass review and acceptance matrix</a> · <a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/10_model_narrative_r2.md">AI use / model narrative</a></p>'''
    page('irregularities.html','Irregularities, limits & next steps',irregularities,r)
    page('feed.html','Dated evidence feed','<div class="eyebrow">Source freshness policy</div><h1>Automatic evidence.<br>Honest timestamps.</h1><div class="live-feed" id="feed">Loading local evidence feed.</div><p>DrivenData automated access is disabled without documented permission. This is not a live board scrape, and no portal slot is used. A local regeneration never changes the original external observation date.</p><p><a href="data/feed.json">Feed JSON</a> · <a href="data/leaderboard.json">Dated board snapshot</a> · <a href="data/source_policy.json">Source policy</a></p>',r)
    # All-downloads routing no longer advertises historical forced files as approved.
    (DOCS / 'downloads/index.html').write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Research downloads · GEMSDOE52</title><link rel="stylesheet" href="../style.css"></head><body><main><p><a href="../index.html">← Overview</a></p><h1>Research downloads</h1>{warning}<p><a href="{r['file']}" download>Download the new R2 TIFF</a> · <a href="{r['file'].replace('.tif','.zip')}" download>Single-TIFF ZIP</a> · <a href="{why['file']}">Geological reasoning CSV</a> · <a href="{r['file'].replace('.tif','-audit.json')}">Full audit</a></p><p>Historical R1/H1 files remain for reproduction only; they are not the current candidate and have no slot approval.</p></main></body></html>''')
    # Preserve the reviewed README, archived task prompt and current H55 status block.

    print('Published R2 site from audited receipts:', r['file'])


if __name__ == '__main__':
    main()
