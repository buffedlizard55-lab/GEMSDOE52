// GEMSDOE52 site feed.  Every number on the page comes from docs/data/*.json, which
// scripts/refresh_feed.py regenerates from the evidence directory (and, on the schedule, from the
// live public leaderboard).  Nothing here is hand-typed, so nothing needs hand-checking.
const G52 = {
  data: {},
  async load(name) {
    try {
      const r = await fetch(`data/${name}.json`, {cache: 'no-store'});
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      this.data[name] = await r.json();
      return this.data[name];
    } catch (e) {
      this.data[name] = {__error: String(e)};
      return this.data[name];
    }
  },
  stamp() {
    const f = this.data.feed || {};
    const el = document.querySelectorAll('[data-feed-stamp]');
    const ago = f.generated_utc ? relAge(f.generated_utc) : 'never';
    el.forEach(n => n.textContent = `${ago} · ${f.generated_utc || 'no feed yet'}`);
    const lb = this.data.leaderboard || {};
    document.querySelectorAll('[data-lb-status]').forEach(n => {
      const ok = (lb.status || '').startsWith('fetched');
      n.innerHTML = ok
        ? `<span class="tag ok">fetched</span> ${relAge(lb.fetched_utc)} · ${esc(lb.fetched_utc || '')}`
        : `<span class="tag warn">${esc(lb.status || 'not fetched')}</span> last snapshot ${relAge(f.generated_utc)}`;
    });
  },
  fmt(v, d = 4) {
    if (v === null || v === undefined) return '–';
    if (typeof v === 'number') return Number.isInteger(v) && Math.abs(v) > 999
      ? v.toLocaleString('en-US') : v.toFixed(d);
    return esc(String(v));
  },
};
function esc(s) {
  return String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}
function relAge(iso) {
  if (!iso) return 'never';
  const t = Date.parse(iso.endsWith('Z') ? iso : iso + 'Z');
  if (Number.isNaN(t)) return 'unknown';
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 90) return `${Math.round(s)} s ago`;
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  if (s < 172800) return `${(s / 3600).toFixed(1)} h ago`;
  return `${(s / 86400).toFixed(1)} d ago`;
}
window.G52 = G52;
window.relAge = relAge; window.esc = esc;
