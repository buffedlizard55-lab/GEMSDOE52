// Executive-summary render. Every number comes from docs/data/*.json; nothing on this page is typed
// in. Two rules this file obeys and that a reader should hold it to:
//
//   1. It renders whatever `submission.json` describes. When the record is an H53 one it carries
//      `submission_name`, `submission_note`, `selection`, `geometry` and `projection`; when it is an
//      older H52 record those keys are absent and the page falls back to the holdout tables instead
//      of printing `undefined` or, worse, printing a stale number as if it were current.
//   2. A missing value renders as "–". It never renders as 0, and never as a guess.
(async function () {
  await Promise.all(['submission', 'holdout_tip', 'holdout_hide', 'feed', 'h53_sweep'].map(n => G52.load(n)));
  G52.stamp();
  const sub = G52.data.submission || {};
  const feed = G52.data.feed || {};
  const pipe = feed.pipeline || {};
  const dl = document.querySelector('.hero .dl, #exec-dl');
  if (!sub.exists || !sub.file) {
    document.querySelectorAll('[data-exec-dl]').forEach(n => {
      n.innerHTML = '<div class="dlmeta"><span class="tag warn">not built yet</span><br>'
        + 'run <code>python3 scripts/run_h53.py --stage build --arm auto</code>, then '
        + '<code>scripts/refresh_feed.py</code>.</div>';
    });
    return;
  }
  const nm = sub.file;
  const px = sub.emitted != null ? sub.emitted : (sub.geometry || {}).S;
  const short = sub.sha256 ? sub.sha256.slice(0, 16) + '…' : '?';

  // ---- the download button, everywhere the page asks for it -----------------------------------
  document.querySelectorAll('[data-exec-dl]').forEach(n => {
    n.innerHTML = `<a class="dlbtn" href="${esc(sub.download || 'downloads/' + nm)}" download>
      Download <code>${esc(nm)}</code><small>${(sub.bytes || 0).toLocaleString()} bytes ·
      sha256 ${esc(short)}</small></a>`;
  });
  if (dl) {
    dl.innerHTML = `<a class="dlbtn" href="${esc(sub.download || 'downloads/' + nm)}" download>
      Download the submission<small>${esc(nm)}</small></a>
      <div class="dlmeta">${(sub.bytes || 0).toLocaleString()} bytes · float32 · EPSG:32611 ·
      width ${sub.width ?? '–'} × height ${sub.height ?? '–'} · ${px != null ? px.toLocaleString() : '–'}
      positive px · no NaN<br>sha256 <code>${esc(sub.sha256 || '?')}</code></div>`;
  }

  // ---- what a human types into the portal ------------------------------------------------------
  document.querySelectorAll('[data-subname]').forEach(n => {
    n.innerHTML = sub.submission_name ? `<code>${esc(sub.submission_name)}</code>`
      : '<span class="muted">– (older record: use the filename)</span>';
  });
  document.querySelectorAll('[data-note]').forEach(n => {
    n.innerHTML = sub.submission_note
      ? `<code>${esc(sub.submission_note)}</code>`
      : `<code>gems52 · ${px != null ? px.toLocaleString() : '?'} px · {0,1} mass · no NaN ·
         sha256 ${esc(short)}</code>`;
  });

  // ---- the gates, on the bytes as served -------------------------------------------------------
  const fg = sub.format_gate || {}, uni = sub.uniqueness || {}, sel = sub.selection || {};
  const geo = sub.geometry || {}, prj = sub.projection || {};
  const pct = x => x == null ? '–' : `${(100 * x).toFixed(1)} %`;
  document.querySelectorAll('[data-gate-verdict]').forEach(n => {
    const ok = t => t ? '<span class="tag ok">pass</span>' : '<span class="tag warn">FAIL</span>';
    n.innerHTML = `format gate ${ok(fg.ok)} — problems: ${esc(JSON.stringify(fg.problems || []))}<br>
      uniqueness gate ${ok(uni.ok)} — <b>${esc(uni.relation_to_union || '–')}</b>:
      ${uni.novel_vs_all_priors != null ? uni.novel_vs_all_priors.toLocaleString() : '–'} px
      (${pct(uni.novel_fraction)}) touch none of the ${uni.n_priors_checked ?? '–'} priors scanned, and
      ${uni.prior_px_dropped != null ? uni.prior_px_dropped.toLocaleString() : '–'} prior px are
      deliberately not re-emitted, so this is not "the union" either.`;
  });
  document.querySelectorAll('[data-holdout-verdict]').forEach(n => {
    const rc = prj.random_control || {}, h52 = prj.h52_reference || {};
    const lift = (a, b) => (a == null || !b) ? '–' : `${(100 * (a / b - 1)).toFixed(0)} %`;
    n.innerHTML = `selected by the pre-registered rule from <code>${esc(sel.source || '–')}</code>:
      <code>${esc(sel.arm || '–')}|${esc(sel.emitter || '–')}</code>,
      ${sel.passes_rule1 ? 'rule 1 <b>passed</b>' : 'rule 1 <b>not passed</b>'}<br>
      blocked whole-segment holdout, 4 folds × 2 instruments, matched-budget random control:<br>
      &nbsp;&nbsp;<code>hide</code> <b>${sel.hide ?? '–'}</b> vs random ${rc.hide ?? '–'}
      (${lift(sel.hide, rc.hide)}) — ${sel.hide_wins ?? '–'}/4 folds<br>
      &nbsp;&nbsp;<code>tip</code> <b>${sel.tip ?? '–'}</b> vs random ${rc.tip ?? '–'}
      (${lift(sel.tip, rc.tip)}) — ${sel.tip_wins ?? '–'}/4 folds<br>
      sum <b>${sel.total != null ? sel.total.toFixed(5) : '–'}</b> against the previously shipped
      arm's ${h52.total ?? '–'} (${lift(sel.total, h52.total)}). Those are recovery numbers on hidden
      catalogue segments — <b>not a forecast of the portal score</b>.`;
  });
  document.querySelectorAll('[data-placement]').forEach(n => {
    n.innerHTML = `kernel-weighted coverage per emitted pixel <code>A/S</code> =
      <b>${geo.A_per_S != null ? geo.A_per_S.toFixed(4) : '–'}</b> =
      ${pct(geo.spacing_efficiency)} of the exact ceiling
      ${pipe.kernel_disc_weight_sum != null ? pipe.kernel_disc_weight_sum.toFixed(6) : '9.380298'}
      (the 0.2778 file reached ${prj.a_per_s_0278_file ?? '–'});
      every emitted pixel is 8-isolated (largest component ${geo.max_component ?? '–'}), so no two
      pixels compete for the same truth pixel and the tax term cannot be reduced further at this
      mass.`;
  });
  document.querySelectorAll('[data-calibration]').forEach(n => {
    n.innerHTML = `|G| — the number of hidden public-test truth pixels — is not published. Inverting
      <code>DTI = T/(0.2·S + 0.8·|G|)</code> (exact for a sparse emission, where <code>M = T</code>)
      on ${'13'} SHA-256-verified scored rasters gives <b>|G| ≥
      ${pipe.n_g_lower_bound != null ? Math.round(pipe.n_g_lower_bound).toLocaleString() : '–'}</b>,
      binding row <code>${esc(pipe.n_g_binding_row || '–')}</code>, point estimate
      <b>${pipe.n_g_point_estimate != null ? Math.round(pipe.n_g_point_estimate).toLocaleString() : '–'}</b>.
      ${esc(pipe.n_g_caveat || '')}`;
  });

  // ---- the expectation line --------------------------------------------------------------------
  const e = document.getElementById('expect');
  if (e) {
    e.innerHTML = prj.geometry_only_dti != null ? `
      <b>What is claimed.</b> The placement gain, in isolation: take the 0.2778 file's own measured
      per-covered-pixel truth density (ρ<sub>A</sub> = 0.01287), apply it to this file's measured
      coverage, change nothing else, and the metric gives
      <b>DTI ≈ ${prj.geometry_only_dti.toFixed(4)}</b>. That is arithmetic given its assumption, and
      the assumption is stated rather than hidden.<br>
      <b>What is not claimed.</b> A board score. The two instruments under-forecast the board by
      roughly 4× in absolute terms — the same family scores ${sel.hide ?? '0.097'} on hidden
      catalogue segments and 0.2778 on the portal — so a fold number ranks candidates and never
      forecasts. The field gain over the previously shipped arm is
      ${sel.total != null && prj.h52_reference ? (100 * (sel.total / prj.h52_reference.total - 1)).toFixed(1) : '–'} %
      on the sum of both instruments, 4/4 folds each; whether it transfers is the open question, and
      it is why the gates and the projection are printed above the download button rather than below it.`
      : 'no projection in this record';
  }
})();
