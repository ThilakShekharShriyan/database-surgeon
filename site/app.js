'use strict';

const SHOW = ['rules-only', 'open-raw', 'frontier-raw', 'open-harness'];
const NAMES = {
  'rules-only': 'Rules-only',
  'open-raw': 'Open-raw',
  'frontier-raw': 'Frontier-raw',
  'open-harness': 'Open-harness (ours)',
};
const BASE_ORDER = ['open-raw', 'frontier-raw', 'rules-only'];

const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));
const finite = (v) => typeof v === 'number' && Number.isFinite(v);
const pct = (v, d = 1) => finite(v) ? (v * 100).toFixed(d) + '%' : '—';
const pp = (v) => finite(v) ? ((v >= 0 ? '+' : '') + (v * 100).toFixed(1) + ' pp') : '—';
const money = (v) => finite(v) ? '$' + v.toFixed(4) : '—';
const sec = (ms) => finite(ms) ? (ms / 1000).toFixed(1) + 's' : '—';
const num = (v, d = 2) => finite(v) ? v.toFixed(d) : '—';
const pval = (v) => {
  if (!finite(v)) return '—';
  if (v < 1e-4) return v.toExponential(1);
  return v < 0.001 ? v.toFixed(4) : v.toFixed(3);
};
const name = (id) => NAMES[id] || id;

function pick(systems, ids = SHOW) {
  const by = Object.fromEntries(systems.map((s) => [s.system, s]));
  return ids.map((id) => by[id]).filter(Boolean);
}

function callAccept(p, ci) {
  const sig = finite(p) && p < 0.05;
  const boot = Array.isArray(ci) && (ci[0] > 0 || ci[1] < 0);
  if (sig && boot) return 'Real gain';
  if (!sig && Array.isArray(ci) && ci[0] <= 0 && ci[1] >= 0) return 'Not sig.';
  if (sig) return 'McNemar only';
  if (boot) return 'Bootstrap only';
  return '—';
}

function scoreboard(rows) {
  document.querySelector('#scoreboard tbody').innerHTML = rows.map((r) => {
    const ours = r.system === 'open-harness' ? ' class="ours"' : '';
    const wrongClass = r.incorrect_returned_count > 0 ? ' bad' : '';
    const partial = r.complete === false ? '†' : '';
    return `<tr${ours}>
      <td>${esc(name(r.system))}${partial}</td>
      <td class="num">${pct(r.accepted_rate)}</td>
      <td class="num${wrongClass}">${r.incorrect_returned_count}</td>
      <td class="num">${money(r.cost_per_case_usd)}</td>
      <td class="num">${sec(r.latency_p50_ms)}</td>
      <td class="num">${r.cases}/${r.expected_cases || r.cases}</td>
    </tr>`;
  }).join('');
}

function bars(id, rows, valueFn, formatFn, badWhen) {
  const vals = rows.map((r) => valueFn(r) || 0);
  const max = Math.max(0.01, ...vals);
  document.getElementById(id).innerHTML = rows.map((r) => {
    const v = valueFn(r) || 0;
    const bad = badWhen && badWhen(r);
    return `<div class="bar-row">
      <div class="bar-label"><b>${esc(name(r.system))}</b><span>${esc(formatFn(r))}</span></div>
      <div class="track"><span class="fill${bad ? ' bad' : ''}" style="width:${(v / max) * 100}%"></span></div>
    </div>`;
  }).join('');
}

function pairedComps(data) {
  const list = (data.paired_stats?.comparisons || [])
    .filter((c) => c.system === 'open-harness' && c.split === 'dev');
  list.sort((a, b) => BASE_ORDER.indexOf(a.baseline) - BASE_ORDER.indexOf(b.baseline));
  return list;
}

function mcnemarTables(comps) {
  const acceptBody = document.querySelector('#mcnemar-accept tbody');
  const wrongBody = document.querySelector('#mcnemar-wrong tbody');
  acceptBody.innerHTML = comps.map((c) => {
    const m = c.mcnemar_accepted || {};
    const ci = c.bootstrap_accept_gap?.ci95;
    return `<tr>
      <td>${esc(name(c.baseline))}</td>
      <td class="num">${m.a_only ?? '—'}</td>
      <td class="num">${m.baseline_only ?? '—'}</td>
      <td class="num">${m.discordant ?? '—'}</td>
      <td class="num">${pval(m.p_value)}</td>
      <td>${esc(callAccept(m.p_value, ci))}</td>
    </tr>`;
  }).join('');
  wrongBody.innerHTML = comps.map((c) => {
    const m = c.mcnemar_incorrect || {};
    const fewer = (m.baseline_only || 0) > (m.a_only || 0);
    const call = finite(m.p_value) && m.p_value < 0.05 && fewer ? 'Safer'
      : finite(m.p_value) && m.p_value < 0.05 ? 'Sig.'
      : m.discordant === 0 ? 'Tied (0)'
      : 'Not sig.';
    return `<tr>
      <td>${esc(name(c.baseline))}</td>
      <td class="num">${m.a_only ?? '—'}</td>
      <td class="num">${m.baseline_only ?? '—'}</td>
      <td class="num">${m.discordant ?? '—'}</td>
      <td class="num">${pval(m.p_value)}</td>
      <td>${esc(call)}</td>
    </tr>`;
  }).join('');
}

function bootstrapTable(comps) {
  document.querySelector('#bootstrap tbody').innerHTML = comps.map((c) => {
    const g = c.bootstrap_accept_gap || {};
    const ci = g.ci95 || [];
    const m = c.mcnemar_accepted || {};
    const agrees = callAccept(m.p_value, ci) === 'Real gain' ? 'Yes'
      : callAccept(m.p_value, ci) === 'Not sig.' ? 'Yes (null)'
      : 'No';
    return `<tr>
      <td>${esc(name(c.baseline))}</td>
      <td class="num">${pp(g.mean)}</td>
      <td class="num">[${pct(ci[0])}, ${pct(ci[1])}]</td>
      <td class="num">${g.clusters ?? '—'}</td>
      <td>${esc(agrees)}</td>
    </tr>`;
  }).join('');
}

function templateSens(data) {
  const cmp = data.splits?.dev?.comparisons?.['open-raw']?.['open-harness'];
  const body = document.querySelector('#template-sens tbody');
  if (!cmp?.mcnemar) {
    body.innerHTML = '<tr><td colspan="4">Template sensitivity unavailable.</td></tr>';
    return;
  }
  const rows = [
    ['Accepted (all instances)', cmp.mcnemar.accepted?.template_sensitivity],
    ['Incorrect (any instance)', cmp.mcnemar.incorrect_returned?.template_sensitivity],
  ];
  body.innerHTML = rows.map(([label, t]) => `<tr>
    <td>${esc(label)}</td>
    <td class="num">${t?.a_only ?? '—'}</td>
    <td class="num">${t?.baseline_only ?? '—'}</td>
    <td class="num">${pval(t?.p_value)}</td>
  </tr>`).join('');
}

function resources(data) {
  const vsRaw = data.splits?.dev?.comparisons?.['open-raw']?.['open-harness']?.paired_metrics;
  const vsFr = data.splits?.dev?.comparisons?.['frontier-raw']?.['open-harness']?.paired_metrics;
  const body = document.querySelector('#resources tbody');
  if (!vsRaw) {
    body.innerHTML = '<tr><td colspan="6">Paired metrics unavailable.</td></tr>';
    return;
  }
  const specs = [
    ['API $ / case', 'cost_usd', money, true],
    ['Opt. time mean (s)', 'latency_ms', (v) => finite(v) ? (v / 1000).toFixed(1) + 's' : '—', true],
    ['Verify time mean (s)', 'verify_ms', (v) => finite(v) ? (v / 1000).toFixed(2) + 's' : '—', true],
    ['Model calls / case', 'calls', (v) => num(v, 2), true],
    ['Output tokens / case', 'output_tokens', (v) => finite(v) ? Math.round(v).toLocaleString('en-US') : '—', true],
    ['SQL speedup (×)', 'speedup', (v) => num(v, 2), false],
  ];
  body.innerHTML = specs.map(([label, key, fmt]) => {
    const a = vsRaw[key];
    const b = vsFr?.[key];
    return `<tr>
      <td>${esc(label)}</td>
      <td class="num">${fmt(a?.mean_a)}</td>
      <td class="num">${fmt(a?.mean_baseline)}</td>
      <td class="num">${fmt(b?.mean_baseline)}</td>
      <td class="num">${num(a?.ratio_of_means_a_over_baseline, 2)}×</td>
      <td class="num">${num(b?.ratio_of_means_a_over_baseline, 2)}×</td>
    </tr>`;
  }).join('');
}

function reading(comps) {
  const vsRaw = comps.find((c) => c.baseline === 'open-raw');
  const vsFr = comps.find((c) => c.baseline === 'frontier-raw');
  const vsRules = comps.find((c) => c.baseline === 'rules-only');
  const bits = [];
  if (vsRaw) {
    bits.push(`<p><strong>vs open-raw.</strong> Accept gap ${esc(pp(vsRaw.bootstrap_accept_gap?.mean))}
      (95% CI [${esc(pct(vsRaw.bootstrap_accept_gap?.ci95?.[0]))}, ${esc(pct(vsRaw.bootstrap_accept_gap?.ci95?.[1]))}]);
      McNemar p=${esc(pval(vsRaw.mcnemar_accepted?.p_value))}. Wrong returns ${vsRaw.incorrect_count_b}→${vsRaw.incorrect_count_a}
      (p=${esc(pval(vsRaw.mcnemar_incorrect?.p_value))}). Both tests agree: real gain.</p>`);
  }
  if (vsFr) {
    bits.push(`<p><strong>vs frontier-raw.</strong> Accept gap ${esc(pp(vsFr.bootstrap_accept_gap?.mean))};
      CI includes 0 ([${esc(pct(vsFr.bootstrap_accept_gap?.ci95?.[0]))}, ${esc(pct(vsFr.bootstrap_accept_gap?.ci95?.[1]))}]);
      McNemar p=${esc(pval(vsFr.mcnemar_accepted?.p_value))}. Do not claim a sealed accept win. Board still leads on point estimate, $/case, and p50.</p>`);
  }
  if (vsRules) {
    bits.push(`<p><strong>vs rules-only.</strong> Accept gap ${esc(pp(vsRules.bootstrap_accept_gap?.mean))};
      McNemar p=${esc(pval(vsRules.mcnemar_accepted?.p_value))}. Rules are free and safe but cover little of the bench.</p>`);
  }
  document.getElementById('reading').innerHTML = bits.join('') || '<p class="empty">No paired comparisons.</p>';
}

function render(data) {
  const dev = data.splits?.dev;
  if (!dev) throw new Error('No development split');
  const rows = pick(dev.systems || []);
  document.getElementById('stamp').textContent =
    'Snapshot ' + new Date(data.generated_at).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    }) + '. Complete systems only in Table I core rows.';

  scoreboard(rows);
  bars('accept', rows, (r) => r.accepted_rate, (r) => pct(r.accepted_rate));
  bars('wrong', rows, (r) => r.incorrect_returned_count, (r) => String(r.incorrect_returned_count),
    (r) => r.incorrect_returned_count > 0);
  bars('cost', rows, (r) => r.cost_per_case_usd || 0, (r) => money(r.cost_per_case_usd || 0));
  bars('latency', rows, (r) => (r.latency_p50_ms || 0) / 1000, (r) => sec(r.latency_p50_ms));

  const comps = pairedComps(data);
  mcnemarTables(comps);
  bootstrapTable(comps);
  templateSens(data);
  resources(data);
  reading(comps);
}

fetch('data/research.json', { cache: 'no-store' })
  .then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
  .then(render)
  .catch((err) => {
    document.getElementById('stamp').textContent = 'Snapshot unavailable.';
    document.getElementById('reading').innerHTML = `<p class="empty">${esc(err.message)}</p>`;
  });
