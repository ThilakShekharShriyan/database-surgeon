'use strict';

const SHOW = ['open-raw', 'frontier-raw', 'open-harness'];
const NAMES = {
  'open-raw': 'Open-raw',
  'frontier-raw': 'Frontier-raw',
  'open-harness': 'Open-harness (ours)',
};

const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));
const pct = (v) => (typeof v === 'number' && Number.isFinite(v) ? (v * 100).toFixed(1) + '%' : '—');
const money = (v) => (typeof v === 'number' && Number.isFinite(v) ? '$' + v.toFixed(4) : '—');
const sec = (ms) => (typeof ms === 'number' && Number.isFinite(ms) ? (ms / 1000).toFixed(1) + 's' : '—');
const pval = (v) => {
  if (!(typeof v === 'number' && Number.isFinite(v))) return '—';
  return v < 0.001 ? v.toExponential(1) : v.toFixed(3);
};

function pick(systems) {
  const by = Object.fromEntries(systems.map((s) => [s.system, s]));
  return SHOW.map((id) => by[id]).filter(Boolean);
}

function scoreboard(rows) {
  document.querySelector('#scoreboard tbody').innerHTML = rows.map((r) => {
    const ours = r.system === 'open-harness' ? ' class="ours"' : '';
    const wrongClass = r.incorrect_returned_count > 0 ? ' bad' : '';
    return `<tr${ours}>
      <td>${esc(NAMES[r.system] || r.system)}</td>
      <td class="num">${pct(r.accepted_rate)}</td>
      <td class="num${wrongClass}">${r.incorrect_returned_count}</td>
      <td class="num">${money(r.cost_per_case_usd)}</td>
      <td class="num">${sec(r.latency_p50_ms)}</td>
    </tr>`;
  }).join('');
}

function bars(id, rows, valueFn, formatFn, badWhen) {
  const max = Math.max(0.01, ...rows.map((r) => valueFn(r) || 0));
  document.getElementById(id).innerHTML = rows.map((r) => {
    const v = valueFn(r) || 0;
    const bad = badWhen && badWhen(r);
    return `<div class="bar-row">
      <div class="bar-label"><b>${esc(NAMES[r.system] || r.system)}</b><span>${esc(formatFn(r))}</span></div>
      <div class="track"><span class="fill${bad ? ' bad' : ''}" style="width:${(v / max) * 100}%"></span></div>
    </div>`;
  }).join('');
}

function stats(data) {
  const comps = data.paired_stats?.comparisons || [];
  const hit = comps.find((c) => c.system === 'open-harness' && c.baseline === 'open-raw' && c.split === 'dev')
    || comps.find((c) => c.system === 'open-harness' && c.baseline === 'open-raw');
  const el = document.getElementById('stats');
  if (!hit) {
    el.innerHTML = '<p class="empty">Paired stats not in this snapshot.</p>';
    return;
  }
  const gap = hit.bootstrap_accept_gap;
  const ci = gap?.ci95;
  const gapPp = typeof gap?.mean === 'number' ? '+' + (gap.mean * 100).toFixed(1) + ' pp' : '—';
  el.innerHTML = [
    ['McNemar p (accept)', pval(hit.mcnemar_accepted?.p_value), `harness vs open-raw, n=${hit.pairs}`],
    ['Accept gap', gapPp, `bootstrap 95% CI [${pct(ci?.[0])}, ${pct(ci?.[1])}]`],
    ['Wrong returns', `${hit.incorrect_count_b} → ${hit.incorrect_count_a}`, 'open-raw → harness'],
    ['McNemar p (incorrect)', pval(hit.mcnemar_incorrect?.p_value), 'fewer incorrect is better'],
  ].map(([k, v, note]) => `
    <div class="stat">
      <strong>${esc(v)}</strong>
      <p>${esc(k)}. ${esc(note)}.</p>
    </div>`).join('');
}

function render(data) {
  const dev = data.splits?.dev;
  if (!dev) throw new Error('No development split');
  const rows = pick(dev.systems || []);
  document.getElementById('stamp').textContent =
    'Snapshot ' + new Date(data.generated_at).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    }) + '.';
  scoreboard(rows);
  bars('accept', rows, (r) => r.accepted_rate, (r) => pct(r.accepted_rate));
  bars('wrong', rows, (r) => r.incorrect_returned_count, (r) => String(r.incorrect_returned_count),
    (r) => r.incorrect_returned_count > 0);
  stats(data);
}

fetch('data/research.json', { cache: 'no-store' })
  .then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
  .then(render)
  .catch((err) => {
    document.getElementById('stamp').textContent = 'Snapshot unavailable.';
    document.getElementById('stats').innerHTML = `<p class="empty">${esc(err.message)}</p>`;
  });
