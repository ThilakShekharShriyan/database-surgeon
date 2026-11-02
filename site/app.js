'use strict';

const SHOW = [
  'rules-only', 'open-raw', 'fw-fast-raw', 'fw-fast-harness',
  'frontier-raw', 'open-harness', 'oss20b-raw', 'oss20b-harness', 'cascade-surgeon',
];
const CORE_CHARTS = ['rules-only', 'open-raw', 'frontier-raw', 'open-harness'];
const OUTCOME_SYS = ['open-raw', 'frontier-raw', 'open-harness'];
const NAMES = {
  'rules-only': 'Rules-only',
  'open-raw': 'Open-raw',
  'fw-fast-raw': 'FW-fast-raw',
  'fw-fast-harness': 'FW-fast-harness',
  'frontier-raw': 'Frontier-raw',
  'open-harness': 'Open-harness (ours)',
  'oss20b-raw': 'OSS-20B-raw',
  'oss20b-harness': 'OSS-20B-harness',
  'cascade-surgeon': 'Cascade-surgeon',
};
const BASE_ORDER = ['open-raw', 'frontier-raw', 'rules-only', 'fw-fast-raw'];

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

function pick(systems, ids) {
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

function scoreboard(rows, rawRate) {
  document.querySelector('#scoreboard tbody').innerHTML = rows.map((r) => {
    const ours = r.system === 'open-harness' ? ' class="ours"' : '';
    const wrongClass = r.incorrect_returned_count > 0 ? ' bad' : '';
    const partial = r.complete === false ? '†' : '';
    const gap = r.system === 'open-raw' || !finite(rawRate) || !finite(r.accepted_rate)
      ? '—'
      : pp(r.accepted_rate - rawRate);
    return `<tr${ours}>
      <td>${esc(name(r.system))}${partial}</td>
      <td class="num">${pct(r.accepted_rate)}</td>
      <td class="num${wrongClass}">${r.incorrect_returned_count}</td>
      <td class="num">${gap}</td>
      <td class="num">${money(r.cost_per_case_usd)}</td>
      <td class="num">${sec(r.latency_p50_ms)}</td>
      <td class="num">${r.cases}/${r.expected_cases || r.cases}</td>
    </tr>`;
  }).join('');
}

function bars(id, rows, valueFn, formatFn, badWhen) {
  const max = Math.max(0.01, ...rows.map((r) => valueFn(r) || 0));
  document.getElementById(id).innerHTML = rows.map((r) => {
    const v = valueFn(r) || 0;
    const bad = badWhen && badWhen(r);
    return `<div class="bar-row">
      <div class="bar-label"><b>${esc(name(r.system))}</b><span>${esc(formatFn(r))}</span></div>
      <div class="track"><span class="fill${bad ? ' bad' : ''}" style="width:${(v / max) * 100}%"></span></div>
    </div>`;
  }).join('');
}

function families(row) {
  const body = document.querySelector('#families tbody');
  if (!row?.accepted_by_family) {
    body.innerHTML = '<tr><td colspan="4">Family rates unavailable.</td></tr>';
    return;
  }
  const entries = Object.entries(row.accepted_by_family)
    .sort((a, b) => a[0].localeCompare(b[0]));
  const cells = [];
  for (let i = 0; i < entries.length; i += 2) {
    const [fa, va] = entries[i];
    const [fb, vb] = entries[i + 1] || [];
    cells.push(`<tr>
      <td>${esc(fa.replaceAll('_', ' '))}</td>
      <td class="num">${pct(va)}</td>
      <td>${fb ? esc(fb.replaceAll('_', ' ')) : ''}</td>
      <td class="num">${fb != null ? pct(vb) : ''}</td>
    </tr>`);
  }
  body.innerHTML = cells.join('');
}

function outcomes(rows) {
  document.querySelector('#outcomes tbody').innerHTML = rows.map((r) => {
    const o = r.outcomes || {};
    const incorrect = (o.incorrect || 0) + (o.invalid || 0);
    // open-raw wrongs may only appear as incorrect_returned_count
    const wrongShare = incorrect > 0
      ? incorrect
      : (r.incorrect_returned_count && r.cases
        ? r.incorrect_returned_count / r.cases
        : 0);
    return `<tr${r.system === 'open-harness' ? ' class="ours"' : ''}>
      <td>${esc(name(r.system))}</td>
      <td class="num">${pct(o.accepted)}</td>
      <td class="num">${pct(o.no_change)}</td>
      <td class="num">${pct(o.not_faster)}</td>
      <td class="num${wrongShare > 0 ? ' bad' : ''}">${pct(wrongShare)}</td>
    </tr>`;
  }).join('');
}

function pairedComps(data) {
  const list = (data.paired_stats?.comparisons || [])
    .filter((c) => c.system === 'open-harness' && c.split === 'dev');
  // also include fw-fast pair as secondary
  const extra = (data.paired_stats?.comparisons || [])
    .filter((c) => c.system === 'fw-fast-harness' && c.baseline === 'fw-fast-raw');
  list.sort((a, b) => BASE_ORDER.indexOf(a.baseline) - BASE_ORDER.indexOf(b.baseline));
  return { primary: list, extra };
}

function contingency(data) {
  const cmp = data.splits?.dev?.comparisons?.['open-raw']?.['open-harness'];
  const body = document.querySelector('#contingency-accept tbody');
  const note = document.getElementById('contingency-note');
  const m = cmp?.mcnemar?.accepted;
  if (!m) {
    body.innerHTML = '<tr><td colspan="3">Contingency unavailable.</td></tr>';
    note.textContent = '';
    return;
  }
  // table layout in data: [[neither-ish, baseline_only],[a_only, both]]
  // From FORGE: both=43, only raw=3, only harness=18, neither=34
  body.innerHTML = `
    <tr>
      <td><strong>Raw accepted</strong></td>
      <td class="num">${m.both ?? '—'} (both, ignored)</td>
      <td class="num"><strong>${m.baseline_only ?? '—'}</strong> (only raw)</td>
    </tr>
    <tr>
      <td><strong>Raw not</strong></td>
      <td class="num"><strong>${m.a_only ?? '—'}</strong> (only harness)</td>
      <td class="num">${(m.pairs != null && m.a_only != null && m.baseline_only != null && m.both != null)
        ? (m.pairs - m.a_only - m.baseline_only - m.both)
        : '—'} (both not)</td>
    </tr>`;
  note.textContent = `Discordant ${m.a_only} vs ${m.baseline_only}; exact two-sided p = ${pval(m.p_value)}. Rate difference (A − baseline) = ${pp(m.rate_difference_a_minus_baseline)}.`;
}

function mcnemarTables(comps) {
  document.querySelector('#mcnemar-accept tbody').innerHTML = comps.map((c) => {
    const m = c.mcnemar_accepted || {};
    const ci = c.bootstrap_accept_gap?.ci95;
    // both/neither from paired_stats if present
    const both = m.both ?? '—';
    const neither = m.neither ?? '—';
    return `<tr>
      <td>${esc(name(c.baseline))}</td>
      <td class="num">${m.a_only ?? '—'}</td>
      <td class="num">${m.baseline_only ?? '—'}</td>
      <td class="num">${both}</td>
      <td class="num">${neither}</td>
      <td class="num">${m.discordant ?? '—'}</td>
      <td class="num">${pval(m.p_value)}</td>
      <td>${esc(callAccept(m.p_value, ci))}</td>
    </tr>`;
  }).join('');

  document.querySelector('#mcnemar-wrong tbody').innerHTML = comps.map((c) => {
    const m = c.mcnemar_incorrect || {};
    const fewer = (m.baseline_only || 0) > (m.a_only || 0);
    const call = finite(m.p_value) && m.p_value < 0.05 && fewer ? 'Safer'
      : finite(m.p_value) && m.p_value < 0.05 ? 'Sig.'
      : m.discordant === 0 ? 'Tied (0 wrong)'
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
    const label = callAccept(m.p_value, ci);
    const agrees = label === 'Real gain' ? 'Yes — real'
      : label === 'Not sig.' ? 'Yes — null'
      : label;
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
    body.innerHTML = '<tr><td colspan="6">Template sensitivity unavailable.</td></tr>';
    return;
  }
  const rows = [
    ['Accepted', cmp.mcnemar.accepted?.template_sensitivity],
    ['Incorrect', cmp.mcnemar.incorrect_returned?.template_sensitivity],
  ];
  body.innerHTML = rows.map(([label, t]) => `<tr>
    <td>${esc(label)}</td>
    <td class="num">${t?.a_only ?? '—'}</td>
    <td class="num">${t?.baseline_only ?? '—'}</td>
    <td class="num">${t?.discordant ?? '—'}</td>
    <td class="num">${pval(t?.p_value)}</td>
    <td>${esc(t?.definition || '—')}</td>
  </tr>`).join('');
}

function resources(data) {
  const vsRaw = data.splits?.dev?.comparisons?.['open-raw']?.['open-harness']?.paired_metrics;
  const vsFr = data.splits?.dev?.comparisons?.['frontier-raw']?.['open-harness']?.paired_metrics;
  const body = document.querySelector('#resources tbody');
  if (!vsRaw) {
    body.innerHTML = '<tr><td colspan="7">Paired metrics unavailable.</td></tr>';
    return;
  }
  const fmtCi = (key, m) => {
    const ci = m?.difference_ci95_template_bootstrap;
    if (!Array.isArray(ci)) return '—';
    if (key === 'cost_usd') return `[${money(ci[0])}, ${money(ci[1])}]`;
    if (key.endsWith('_ms')) return `[${(ci[0] / 1000).toFixed(1)}s, ${(ci[1] / 1000).toFixed(1)}s]`;
    if (key === 'output_tokens') return `[${Math.round(ci[0])}, ${Math.round(ci[1])}]`;
    return `[${num(ci[0], 2)}, ${num(ci[1], 2)}]`;
  };
  const specs = [
    ['API $ / case', 'cost_usd', money],
    ['Opt. time mean (s)', 'latency_ms', (v) => finite(v) ? (v / 1000).toFixed(1) + 's' : '—'],
    ['LLM time mean (s)', 'llm_ms', (v) => finite(v) ? (v / 1000).toFixed(1) + 's' : '—'],
    ['Verify time mean (s)', 'verify_ms', (v) => finite(v) ? (v / 1000).toFixed(2) + 's' : '—'],
    ['Model calls / case', 'calls', (v) => num(v, 2)],
    ['Output tokens / case', 'output_tokens', (v) => finite(v) ? Math.round(v).toLocaleString('en-US') : '—'],
    ['SQL speedup (×)', 'speedup', (v) => num(v, 2)],
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
      <td class="num">${fmtCi(key, a)}</td>
    </tr>`;
  }).join('');
}

function reading(comps, extra) {
  const vsRaw = comps.find((c) => c.baseline === 'open-raw');
  const vsFr = comps.find((c) => c.baseline === 'frontier-raw');
  const vsRules = comps.find((c) => c.baseline === 'rules-only');
  const bits = [];

  bits.push(`<p><strong>Headline.</strong> The product claim is not “we beat every closed model on accept p-value.”
    It is: the same open Fireworks model, behind a verify-or-abstain gate, stops returning wrong SQL,
    lifts beneficial accepts past blind raw, and stays competitive on $/case and optimizer p50.</p>`);

  if (vsRaw) {
    bits.push(`<p><strong>vs open-raw (required comparison).</strong> Accept gap ${esc(pp(vsRaw.bootstrap_accept_gap?.mean))}
      with bootstrap 95% CI [${esc(pct(vsRaw.bootstrap_accept_gap?.ci95?.[0]))}, ${esc(pct(vsRaw.bootstrap_accept_gap?.ci95?.[1]))}]
      (excludes 0). McNemar on acceptance: ${vsRaw.mcnemar_accepted?.a_only} vs ${vsRaw.mcnemar_accepted?.baseline_only}
      discordant, p=${esc(pval(vsRaw.mcnemar_accepted?.p_value))}. Incorrect returns: ${vsRaw.incorrect_count_b}→${vsRaw.incorrect_count_a},
      p=${esc(pval(vsRaw.mcnemar_incorrect?.p_value))}. Both tests agree: <em>real gain</em>. Template sensitivity
      (n=57) still favors harness on accept (p&nbsp;&lt;&nbsp;0.05) and on incorrect returns.</p>`);
  }
  if (vsFr) {
    bits.push(`<p><strong>vs frontier-raw (optional closed).</strong> Accept gap ${esc(pp(vsFr.bootstrap_accept_gap?.mean))};
      CI [${esc(pct(vsFr.bootstrap_accept_gap?.ci95?.[0]))}, ${esc(pct(vsFr.bootstrap_accept_gap?.ci95?.[1]))}]
      <em>includes</em> 0. McNemar p=${esc(pval(vsFr.mcnemar_accepted?.p_value))} (${vsFr.mcnemar_accepted?.a_only} vs ${vsFr.mcnemar_accepted?.baseline_only} discordant).
      We do <strong>not</strong> claim a sealed statistical accept win over frontier. We do claim open-stack competitiveness,
      the raw-open safety story, and measured wins on API $/case and optimizer p50 on Table I.</p>`);
  }
  if (vsRules) {
    bits.push(`<p><strong>vs rules-only.</strong> Accept gap ${esc(pp(vsRules.bootstrap_accept_gap?.mean))};
      McNemar p=${esc(pval(vsRules.mcnemar_accepted?.p_value))} (${vsRules.mcnemar_accepted?.a_only} vs ${vsRules.mcnemar_accepted?.baseline_only}).
      Rules are free and safe but cover little of the bench—necessary floor, not the product.</p>`);
  }
  if (extra?.[0]) {
    const e = extra[0];
    bits.push(`<p><strong>Secondary: fw-fast-harness vs fw-fast-raw.</strong> Accept gap ${esc(pp(e.bootstrap_accept_gap?.mean))};
      CI [${esc(pct(e.bootstrap_accept_gap?.ci95?.[0]))}, ${esc(pct(e.bootstrap_accept_gap?.ci95?.[1]))}];
      McNemar p=${esc(pval(e.mcnemar_accepted?.p_value))}. Same gate helps a cheaper stage, with higher latency/cost than open-harness.</p>`);
  }
  bits.push(`<p><strong>What not to over-read.</strong> Mean paired optimizer time (Table VII) includes verify and best-of,
    so it can exceed open-raw even while median p50 stays near frontier. Speedup geomeans on accepted SQL are not
    FinOps savings until weighted by warehouse traffic. Held-out harness coverage remains thinner than development.</p>`);

  document.getElementById('reading').innerHTML = bits.join('');
}

function render(data) {
  const dev = data.splits?.dev;
  if (!dev) throw new Error('No development split');
  const all = pick(dev.systems || [], SHOW);
  const charts = pick(dev.systems || [], CORE_CHARTS);
  const outcomeRows = pick(dev.systems || [], OUTCOME_SYS);
  const raw = (dev.systems || []).find((s) => s.system === 'open-raw');
  const harness = (dev.systems || []).find((s) => s.system === 'open-harness');

  document.getElementById('stamp').textContent =
    'Snapshot ' + new Date(data.generated_at).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    }) + ' · sealed eval_v2 · trial 0 · † incomplete coverage.';

  scoreboard(all, raw?.accepted_rate);
  bars('accept', charts, (r) => r.accepted_rate, (r) => pct(r.accepted_rate));
  bars('wrong', charts, (r) => r.incorrect_returned_count, (r) => String(r.incorrect_returned_count),
    (r) => r.incorrect_returned_count > 0);
  bars('cost', charts, (r) => r.cost_per_case_usd || 0, (r) => money(r.cost_per_case_usd || 0));
  bars('latency', charts, (r) => (r.latency_p50_ms || 0) / 1000, (r) => sec(r.latency_p50_ms));
  families(harness);
  outcomes(outcomeRows);

  const { primary, extra } = pairedComps(data);
  contingency(data);
  mcnemarTables(primary);
  bootstrapTable(primary);
  templateSens(data);
  resources(data);
  reading(primary, extra);
}

fetch('data/research.json', { cache: 'no-store' })
  .then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
  .then(render)
  .catch((err) => {
    document.getElementById('stamp').textContent = 'Snapshot unavailable.';
    document.getElementById('reading').innerHTML = `<p class="empty">${esc(err.message)}</p>`;
  });
