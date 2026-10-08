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
      const latest = data.latest_research;
      if (!latest || latest.run_id !== 'ctd5-a24c35d1' || latest.submit_ok !== false) {
        throw new Error('research feed has no matching closed-gate receipt');
      }
      // No innerHTML or portal access; never turn a timestamp into a new measured score.
      target.textContent = `Local evidence refresh: ${data.generated_utc}. Research download hash verified: ${latest.hash_verified ? 'yes' : 'no'}. ` +
        'Submission gate: CLOSED. Organizer results are not live; no automatic competition upload.';
    })
    .catch(() => {
      target.textContent = 'Live local-feed check unavailable. The dated audit below remains available. Submission gate stays CLOSED.';
    });
}
