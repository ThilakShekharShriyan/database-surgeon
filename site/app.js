'use strict';

const SHOW = ['open-raw', 'frontier-raw', 'open-harness'];
const NAMES = {
  'open-raw': 'Open-raw',
  'frontier-raw': 'Frontier-raw',
  'open-harness': 'Open-harness',
};

const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));
const pct = (v) => (typeof v === 'number' && Number.isFinite(v) ? (v * 100).toFixed(1) + '%' : '—');
const money = (v) => {
  if (!(typeof v === 'number' && Number.isFinite(v))) return '—';
  return '$' + v.toFixed(v < 0.01 ? 4 : 4);
};
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
  const body = document.querySelector('#scoreboard tbody');
  body.innerHTML = rows.map((r) => {
    const ours = r.system === 'open-harness' ? ' class="ours"' : '';
    const wrongClass = r.incorrect_returned_count > 0 ? ' bad' : ' good';
    return `<tr${ours}>
      <td>${esc(NAMES[r.system] || r.system)}${r.system === 'open-harness' ? '<span class="sub">ours · verify-or-abstain</span>' : ''}</td>
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
  el.innerHTML = `
    <article class="stat">
      <strong>${esc(pval(hit.mcnemar_accepted?.p_value))}</strong>
      <p>McNemar p — harness vs open-raw accept (n=${hit.pairs})</p>
    </article>
    <article class="stat">
      <strong>${esc(gapPp)}</strong>
      <p>Accept gap · bootstrap 95% CI [${esc(pct(ci?.[0]))}, ${esc(pct(ci?.[1]))}]</p>
    </article>
    <article class="stat">
      <strong>${esc(String(hit.incorrect_count_b))}→${esc(String(hit.incorrect_count_a))}</strong>
      <p>Wrong returns: open-raw → harness</p>
    </article>
    <article class="stat">
      <strong>${esc(pval(hit.mcnemar_incorrect?.p_value))}</strong>
      <p>McNemar p — incorrect returns</p>
    </article>`;
}

function render(data) {
  const dev = data.splits?.dev;
  if (!dev) throw new Error('No development split');
  const rows = pick(dev.systems || []);
  document.getElementById('stamp').textContent =
    new Date(data.generated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    + ' · sealed eval_v2';
  scoreboard(rows);
  bars('accept', rows, (r) => r.accepted_rate, (r) => pct(r.accepted_rate));
  bars('wrong', rows, (r) => r.incorrect_returned_count, (r) => String(r.incorrect_returned_count), (r) => r.incorrect_returned_count > 0);
  stats(data);
}

fetch('data/research.json', { cache: 'no-store' })
  .then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
  .then(render)
  .catch((err) => {
    document.getElementById('stamp').textContent = 'Snapshot unavailable';
    document.getElementById('stats').innerHTML = `<p class="empty">${esc(err.message)}</p>`;
  });
