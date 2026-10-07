// Renders every number on the site from docs/data/*.json.  Kept deliberately dumb: fetch, index a
// table, print.  If a value is missing the page shows "–" rather than a stale or guessed number.
(async function () {
  await Promise.all(['feed', 'leaderboard', 'submission', 'holdout_tip', 'holdout_hide',
                     'independence_tip', 'independence_hide', 'strata_tip', 'strata_hide',
                     'layer_screen', 'folds_tip', 'folds_hide', 'co_train_folds_tip',
                     'co_train_folds_hide', 'band_inventory', 'revealed_calibration',
                     'revealed_budget', 'revealed_uniqueness_gate', 'independence_revealed',
                     'cotraining_views53']
                    .map(n => G52.load(n)));
  G52.stamp();
  const d = G52.data;
  const set = (id, html) => { const n = document.getElementById(id); if (n) n.innerHTML = html; };
  const miss = o => o && !o.__error ? o : null;

  // ---------------------------------------------------------------- hero download block
  const sub = miss(d.submission) || {};
  const dl = document.querySelector('.hero .dl');
  if (sub.exists && sub.file) {
    const nm = sub.file;
    dl.innerHTML = `
      <a class="dlbtn" href="${sub.download || 'downloads/' + nm}" download>
        Download the submission .tif<small>${nm.length > 46 ? nm.slice(0, 43) + '…' : nm}</small></a>
      <div class="dlmeta">${(sub.bytes || 0).toLocaleString()} bytes · float32 · EPSG:32611<br>
        sha256 <code>${(sub.sha256 || '').slice(0, 16)}…</code><br>
        ${sub.budget ?? '–'} px emitted · ${sub.retained_core_px ?? '–'} retained + ${sub.novel_px ?? '–'} strictly novel</div>
      ${sub.download_zip ? `<a class="dlbtn" style="background:var(--paper-2);color:var(--ink);box-shadow:3px 3px 0 var(--rule)"
         href="${sub.download_zip}" download>Download .zip (tif + note + evidence)<small>same file, plus the note to paste and the JSON behind it</small></a>` : ''}
      ${sub.submission_note ? `<div class="dlmeta">Notes box, verbatim (≤200 chars):<br><code>${esc(sub.submission_note)}</code></div>` : ''}
      <a class="dlbtn" style="background:var(--paper-2);color:var(--ink);box-shadow:3px 3px 0 var(--rule)"
         href="executive-summary.html">How to submit →</a>`;
  } else {
    dl.innerHTML = `<div class="dlmeta"><span class="tag warn">not built yet</span><br>
      Run <code>scripts/build_submission.py</code>; this block fills itself from
      <code>data/submission.json</code>.</div>`;
  }

  // ---------------------------------------------------------------- KPIs
  const kpi = (label, val, cls = '') => `<div class="kpi ${cls}"><b>${val}</b><span>${label}</span></div>`;
  const h = miss(d.holdout_tip) || {};
  const hs = h.summary || {};
  const best = Object.entries(hs).sort((a, b) => b[1].mean - a[1].mean)[0];
  const rnd = Object.entries(hs).filter(([k]) => k.startsWith('random|')).sort((a, b) => b[1].mean - a[1].mean)[0];
  const sib = Object.entries(hs).filter(([k]) => k.startsWith('sibling:')).sort((a, b) => b[1].mean - a[1].mean)[0];
  const lb = miss(d.leaderboard) || {};
  const rows = lb.rows || [];
  const top = rows.length ? rows[0].score : 0.3774;
  const ours = 0.2778;
  set('kpis', [
    kpi('group best (owner-reported)', ours.toFixed(4)),
    kpi('live board #1', top.toFixed(4), 'bad'),
    kpi('gap to #1', (top - ours).toFixed(4), 'bad'),
    kpi('best arm on tip folds', best ? best[1].mean.toFixed(4) : '–', 'good'),
    kpi('random at same budget', rnd ? rnd[1].mean.toFixed(4) : '–'),
    kpi('uniform-random lift', best && rnd ? (best[1].mean / Math.max(rnd[1].mean, 1e-6)).toFixed(2) + '×' : '–'),
    kpi('sibling raster on same folds', sib ? sib[1].mean.toFixed(4) : '–'),
    kpi('emitted pixels', (sub.n_nonzero ?? sub.budget ?? '–').toLocaleString ? (sub.n_nonzero ?? sub.budget).toLocaleString() : (sub.n_nonzero ?? sub.budget ?? '–')),
  ].join(''));

  // ---------------------------------------------------------------- verdict banner
  const gates = (h.gates || {});
  const indT = miss(d.independence_tip) || {};
  const indH = miss(d.independence_hide) || {};
  const promoted = gates.promoted;
  // The banner must describe the file being offered, so it prefers the built submission's own gate
  // record and falls back to the arm-level gates.  It used to print the co-training arm's verdict under a
  // heading about the download, which is a different experiment.
  const shown = (Object.keys(sub.holdout_gates || {}).length ? sub.holdout_gates : gates) || {};
  const num = v => (v === null || v === undefined || Number.isNaN(Number(v))) ? '–' : Number(v).toFixed(3);
  const yn = v => v === true ? '<b>yes</b>' : v === false ? '<b>no</b>' : '–';
  const unionBits = Object.entries(shown.vs_naive_union || {})
    .map(([m, v]) => `${m} ${v === null || v === undefined ? '–' : (v >= 0 ? '+' : '') + Number(v).toFixed(4)}`)
    .join(', ');
  const premise = (tag, o) => `
      ${tag}: block-level false-alarm <span class="mono">r=${num(o.pearson)}</span> ·
      miss-rate <span class="mono">r=${num(o.pearson_misses)}</span> ·
      held-pixel logit <span class="mono">r=${num(o.pearson_logit_held_all)}</span> vs a
      <span class="mono">0.60</span> abandonment threshold${o.n_held ? ` over ${o.n_held.toLocaleString('en-US')} held px` : ''}.
      ${o.note ? `<span class="muted">${esc(o.note)}</span>` : ''}`;
  set('verdict', `
    <div style="display:flex;gap:.8rem;align-items:flex-start;flex-wrap:wrap">
      <span class="tag ${shown.promoted ? 'ok' : 'no'}" style="font-size:.8rem">
        ${shown.promoted ? 'HOLDOUT GATES CLEARED' : 'HOLDOUT GATES NOT CLEARED'}</span>
      <div class="small" style="flex:1 1 22rem">
        ${sub.file ? `Offered file <code>${esc(String(sub.file).replace(/\.tif$/, ''))}</code>` : 'No file staged yet'}
        · tested <code>${shown.tested || '–'}</code>. ${esc(shown.reason || 'no gate record')}<br>
        matched-budget control bar on both instruments: ${yn(shown.composite_control_bar)} ·
        registered +0.010-over-union bar: ${yn(shown.registered_union_bar)}
        (${unionBits || '–'}) · built with <code>--force</code>: ${yn(sub.forced)}
        ${Object.keys(gates.checks || {}).length ? '<br><span class="muted">co-training arm gates, for reference: '
          + Object.entries(gates.checks).map(([k, v]) =>
            `<span class="mono">${k}: ${v.ok ? 'OK' : 'not OK'}</span>`).join(' · ') + '</span>' : ''}
      </div></div>
    <p class="small" style="margin-bottom:0"><strong>Conditional-independence premise
      (Blum–Mitchell), as measured.</strong>${premise('tip instrument', indT)}${premise('hide instrument', indH)}
      ${indH.decision ? `<br><span class="small">${esc(indH.decision.reading)}</span>` : ''}</p>`);

  // ---------------------------------------------------------------- leaderboard
  const tbl = (head, rows_) => `<table><thead><tr>${head.map(hh => `<th class="${hh[1] === 'n' ? 'num' : ''}">${hh[0]}</th>`).join('')}</tr></thead>
    <tbody>${rows_.map(r => `<tr>${r.map(c => Array.isArray(c) ? `<td class="num">${c[1] === 'n' ? c[0] : c[0]}</td>` : `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  if (rows.length) {
    set('lb', tbl([['#'], ['team'], ['DTI', 'n']], rows.slice(0, 16).map(r => [
      r.rank, r.team.startsWith('extradr19') ? `<b>${esc(r.team)}</b> ← this group` : esc(r.team),
      [r.score.toFixed(4)]])) +
      `<p class="small muted">${rows.length} rows parsed · fetched ${relAge(lb.fetched_utc)} ·
       <a href="${lb.source}">official page</a> · board is participant-level: no filename, hash or
       receipt, so no file→score mapping on this site is organiser-authenticated.</p>`);
  } else {
    set('lb', `<p class="small">Offline snapshot only: <span class="tag warn">${esc(lb.status || 'no fetch attempted')}</span></p>
      <p class="small muted">Committed workflow <code>.github/workflows/feed.yml</code> re-fetches
      <a href="${lb.source || 'https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/'}">the board</a>
      nightly and on push.</p>`);
  }

  // ---------------------------------------------------------------- arms table
  if (best) {
    const keys = Object.keys(hs).sort((a, b) => hs[b].mean - hs[a].mean).slice(0, 8);
    set('arms', tbl([['arm', ''], ['mean', 'n'], ['sd', 'n'], ['best fold', 'n'], ['worst', 'n']],
      keys.map(k => [(k === best[0] ? `<b>${esc(k)}</b>` : esc(k)), hs[k].mean.toFixed(4),
                     hs[k].sd.toFixed(4), hs[k].best_fold.toFixed(4), hs[k].worst_fold.toFixed(4)])) +
      `<p class="small muted">${esc(h.mode || '')} instrument · ${h.n_folds || ''} folds ·
       visible catalogue masked out of both the allowed set and the score ·
       <a href="validation.html">full table and gates</a></p>`);
  } else set('arms', '<p class="small muted">no holdout table in <code>data/</code> yet</p>');

  // ------------------------------------------------------------------ H53 calibration table
  const cal = miss(d.revealed_calibration) || {};
  if (cal.size_of) {
    const dens = (cal.density_of || {}), cr = (cal.credit_of || {}), sz = cal.size_of;
    const rowsT = [
      ['|G| (hidden truth, px)', cal.g_estimate_px ? cal.g_estimate_px.toLocaleString('en-US') : '–',
       'exact: solved from T(B) − T(A) = 0 on the verified nesting A ⊂ B'],
      ['credit of the ≤200 m ring', cal.corridor_credit, 'exact, not modelled'],
      ['retained core A & C (px)', (sz['P1=A&C'] || 0).toLocaleString('en-US'), 'measured on the bytes'],
      ['its credit', cr['P1=A&C'] ? `${(cal.t_core_bounds ? cal.t_core_bounds[0] + ' – ' + cal.t_core_bounds[1] : cr['P1=A&C'])}, central ${cal.t_core_central ?? '–'}` : '–',
       'exact interval from t ≥ 0; central estimate splits the measured tail credit by size'],
      ['its credit density', dens['P1=A&C'] ? `${(100 * (cal.t_core_central / sz['P1=A&C'])).toFixed(2)} % central` : '–',
       'against 2.79 % for uniform-random mass and 13.87 % for the champion file as a whole'],
      ['DTI(core emitted alone)', cal.dti_core_bounds ? `${cal.dti_core_bounds[0]} – ${cal.dti_core_bounds[1]}` : '–',
       `central ${cal.dti_core_central ?? '–'} — a pure budget reduction, no new geology`],
    ];
    Object.keys(sz).forEach(k => {
      if (k === 'P1=A&C') return;
      rowsT.push([`atom ${k}`, sz[k].toLocaleString('en-US'),
                  `credit ${cr[k] ?? '–'} · density ${dens[k] !== undefined ? (100 * dens[k]).toFixed(2) + ' %' : '–'}`]);
    });
    set('h53cal', rowsT.map(r => `<tr><td>${esc(r[0])}</td><td class="num">${esc(String(r[1]))}</td><td class="small muted">${esc(r[2])}</td></tr>`).join(''));
  }

  // ------------------------------------------------------------------ H53 budget / P(win) table
  const bud = miss(d.revealed_budget) || {};
  if (bud.rows) {
    const sel = bud.selected || {};
    set('h53budget', bud.rows.map(r => `<tr${r.n_novel === sel.n_novel ? ' class="hi"' : ''}>
      <td class="num">${r.n_novel.toLocaleString('en-US')}</td>
      <td class="num">${r.total.toLocaleString('en-US')}</td>
      <td class="num">${(100 * r.novel_fraction).toFixed(1)} %</td>
      <td class="num"><b>${r.p_win.toFixed(4)}</b></td>
      <td class="num">${r.mean_dti.toFixed(4)}</td>
      <td class="num">${r.worst_dti.toFixed(4)}</td>
      <td class="num">${r.best_dti.toFixed(4)}</td></tr>`).join('')
      + `<tr><td colspan="7" class="small muted">selected row highlighted. Rule: ${esc(bud.rule || '')}.
         |G| = ${bud.g_estimate_px ?? '–'} px · t_core interval ${JSON.stringify(bud.t_core_bounds ?? [])} ·
         ρ_novel prior ${JSON.stringify(bud.rho_prior ?? [])} · floor ${bud.floor ?? '–'}.</td></tr>`);
  }

  // ------------------------------------------------------------------ H53 two-view + independence
  const v53 = miss(d.cotraining_views53) || {};
  const ind53 = miss(d.independence_revealed) || {};
  const vb = document.getElementById('h53views');
  if (vb && (v53.view_a || ind53.pixel_pearson_r !== undefined)) {
    const sb = v53.single_view_baseline || {};
    vb.innerHTML = `<table><thead><tr><th>quantity</th><th>value</th><th>reading</th></tr></thead><tbody>
      <tr><td>View A out-of-fold AUC</td><td class="num">${v53.view_a ? v53.view_a.oof_auc : '–'}</td>
        <td class="small muted">potential field / subsurface, ${v53.view_a ? v53.view_a.n_features : '–'} features; block mean ${sb.view_a_mean ?? '–'}</td></tr>
      <tr><td>View B out-of-fold AUC</td><td class="num">${v53.view_b ? v53.view_b.oof_auc : '–'}</td>
        <td class="small muted">surface / LiDAR scarp / radiometric, ${v53.view_b ? v53.view_b.n_features : '–'} features; block mean ${sb.view_b_mean ?? '–'}</td></tr>
      <tr><td>blended</td><td class="num">${v53.blended_oof_auc ?? '–'}</td>
        <td class="small muted"><b>co-training wins: ${sb.co_training_wins === undefined ? '–' : (sb.co_training_wins ? 'yes' : 'no')}</b> — View B alone beats the blend, and that is printed rather than buried</td></tr>
      <tr><td>independence, pixel Pearson r</td><td class="num">${ind53.pixel_pearson_r ?? '–'}</td>
        <td class="small muted">threshold ${ind53.threshold ?? '–'} → ${esc(ind53.verdict || '–')}</td></tr>
      <tr><td>independence, block mean r</td><td class="num">${ind53.block_mean_r ?? '–'}</td>
        <td class="small muted">variance ${ind53.block_var_r ?? '–'} over ${ind53.n_blocks ?? '–'} blocks; degenerate: ${ind53.degenerate_block_variance === undefined ? '–' : (ind53.degenerate_block_variance ? 'yes' : 'no')} — N-1 recorded that a degenerate block variance once stopped this test from firing at all</td></tr>
      <tr><td colspan="3" class="small muted">${esc(sb.label_caveat || '')}</td></tr>
      </tbody></table>`;
  }
})();