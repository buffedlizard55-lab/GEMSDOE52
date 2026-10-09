'use strict';
// Clipboard convenience only; names and notes remain selectable without JavaScript.
for (const button of document.querySelectorAll('[data-copy-id]')) {
  button.addEventListener('click', async () => {
    const field = document.getElementById(button.dataset.copyId);
    const status = document.getElementById('copy-status');
    if (!field) return;
    try {
      await navigator.clipboard.writeText(field.value);
      if (status) status.textContent = 'Copied for identification. This artifact is NOT approved for submission.';
    } catch (_) {
      field.focus(); field.select();
      if (status) status.textContent = 'Text selected. Use your device’s copy command. Submission is not approved.';
    }
  });
}
const target = document.getElementById('local-feed');
if (target) {
  fetch('data/feed.json', {cache: 'no-cache'})
    .then(r => { if (!r.ok) throw new Error('feed unavailable'); return r.json(); })
    .then(data => {
      const latest = data.latest_research || {};
      const round = data.current_round || latest.round || 'not recorded';
      const verdict = data.current_verdict || latest.verdict || 'not recorded';
      const candidate = data.current_candidate_exists ?? latest.candidate_raster_exists;
      const download = data.current_download_ok ?? latest.download_ok;
      const submit = data.current_submit_ok ?? latest.submit_ok;
      const holdout = (latest.holdout_dti || {}).status || 'not recorded';
      target.textContent = `Current research ${round}: ${verdict}; candidate GeoTIFF ${candidate === false ? 'NO' : candidate === true ? 'YES' : 'not recorded'}, current download ${download === false ? 'NO' : download === true ? 'YES' : 'not recorded'}, submit ${submit === false ? 'NO' : submit === true ? 'YES' : 'not recorded'}, HOLDOUT-DTI ${holdout}. Feed generated ${data.generated_utc || 'at an unknown time'}. The historical marker is not current upload approval.`;
    })
    .catch(() => {
      target.textContent = 'Live local-feed check unavailable. The dated audit below remains available. Submission gate stays CLOSED.';
    });
}
