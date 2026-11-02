'use strict';

const MAIN = [
  'rules-only', 'open-raw', 'fw-fast-raw', 'fw-fast-harness',
  'frontier-raw', 'open-harness', 'oss20b-raw', 'oss20b-harness',
];
const CORE = ['rules-only', 'open-raw', 'frontier-raw', 'open-harness'];
const DETAIL = ['rules-only', 'open-raw', 'frontier-raw', 'open-harness-nocache', 'open-harness'];
const PAIRS = [
  ['gpt-oss-120b (Fireworks)', 'open-raw', 'open-harness'],
  ['fw-fast (Fireworks)', 'fw-fast-raw', 'fw-fast-harness'],
  ['Nemotron (Fireworks)', 'fw-nemotron-raw', 'fw-nemotron-harness'],
  ['gpt-oss-20b (hosted)', 'oss20b-raw', 'oss20b-harness'],
  ['gpt-oss-20b (Ollama, local)', 'ollama-gpt-oss-20b-raw', 'ollama-gpt-oss-20b-harness'],
];
const LOCAL = [
  'ollama-qwen25-coder-7b-raw', 'ollama-qwen3-8b-raw',
  'ollama-gpt-oss-20b-raw', 'ollama-gpt-oss-20b-harness',
];
const NAMES = {
  'rules-only': 'Rules-only',
  'cache-rules': 'Cache + rules',
  'open-raw': 'Open-raw',
  'open-harness': 'Open-harness (ours)',
  'open-harness-nocache': 'Open-harness, no cache',
  'frontier-raw': 'Frontier-raw',
  'fw-fast-raw': 'FW-fast-raw',
  'fw-fast-harness': 'FW-fast-harness',
  'fw-nemotron-raw': 'Nemotron-raw',
  'fw-nemotron-harness': 'Nemotron-harness',
  'oss20b-raw': 'OSS-20B-raw',
  'oss20b-harness': 'OSS-20B-harness',
  'oss120b-raw': 'OSS-120B-raw (hosted)',
  'ollama-gpt-oss-20b-raw': 'Ollama gpt-oss-20b raw',
  'ollama-gpt-oss-20b-harness': 'Ollama gpt-oss-20b harness',
  'ollama-qwen3-8b-raw': 'Ollama qwen3-8b raw',
  'ollama-qwen25-coder-7b-raw': 'Ollama qwen2.5-coder-7b raw',
};
const BASE_ORDER = ['open-raw', 'frontier-raw', 'rules-only'];
const OUTCOME_LABEL = {
  accepted: 'Accepted',
  no_change: 'Kept original',
  not_faster: 'Not faster (kept original)',
  regression: 'Regression',
  incorrect: 'Incorrect',
  invalid: 'Invalid',
};

const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));
const finite = (v) => typeof v === 'number' && Number.isFinite(v);
const pct = (v, d = 1) => finite(v) ? (v * 100).toFixed(d) + '%' : '—';
const pp = (v) => finite(v) ? ((v >= 0 ? '+' : '') + (v * 100).toFixed(1) + ' pp') : '—';
const money = (v) => finite(v) ? '$' + v.toFixed(4) : '—';
const money2 = (v) => finite(v) ? '$' + v.toFixed(2) : '—';
const sec = (ms) => finite(ms) ? (ms / 1000).toFixed(1) + 's' : '—';
const num = (v, d = 2) => finite(v) ? v.toFixed(d) : '—';
const int = (v) => finite(v) ? Math.round(v).toLocaleString('en-US') : '—';
const ci = (pair, fmt = pct) => Array.isArray(pair) ? `[${fmt(pair[0])}, ${fmt(pair[1])}]` : '—';
const pval = (v) => {
  if (!finite(v)) return '—';
  if (v < 1e-4) return v.toExponential(1);
  return v < 0.001 ? v.toFixed(4) : v.toFixed(3);
};
const name = (id) => NAMES[id] || id;
const marks = (r) => (r.complete === false ? '†' : '') + (r.simulated ? '‡' : '');
const rowClass = (r) => r.system === 'open-harness' ? ' class="ours"' : '';
const fill = (id, rows, cols) => {
  $(id).querySelector('tbody').innerHTML = rows.length
    ? rows.join('')
    : `<tr><td colspan="${cols}">No data in this snapshot.</td></tr>`;
};

function pick(by, ids) {
  return ids.map((id) => by[id]).filter(Boolean);
}

function callAccept(p, interval) {
  const sig = finite(p) && p < 0.05;
  const boot = Array.isArray(interval) && (interval[0] > 0 || interval[1] < 0);
  if (sig && boot) return 'Real gain';
  if (!sig && !boot) return 'Not significant';
  return sig ? 'McNemar only' : 'Bootstrap only';
}

function composition(dev) {
  const fam = {};
  for (const c of dev.cases || []) {
    fam[c.family] ??= { rewrite: 0, trap: 0, decoy: 0 };
    fam[c.family][c.kind] = (fam[c.family][c.kind] || 0) + 1;
  }
  const tot = { rewrite: 0, trap: 0, decoy: 0 };
  const rows = Object.entries(fam).sort((a, b) => {
    const sa = a[1].rewrite + a[1].trap + a[1].decoy;
    const sb = b[1].rewrite + b[1].trap + b[1].decoy;
    return sb - sa || a[0].localeCompare(b[0]);
  }).map(([f, k]) => {
    tot.rewrite += k.rewrite; tot.trap += k.trap; tot.decoy += k.decoy;
    return `<tr><td>${esc(f.replaceAll('_', ' '))}</td><td class="num">${k.rewrite}</td><td class="num">${k.trap}</td><td class="num">${k.decoy}</td><td class="num">${k.rewrite + k.trap + k.decoy}</td></tr>`;
  });
  rows.push(`<tr class="ours"><td>Total</td><td class="num">${tot.rewrite}</td><td class="num">${tot.trap}</td><td class="num">${tot.decoy}</td><td class="num">${tot.rewrite + tot.trap + tot.decoy}</td></tr>`);
  fill('composition', rows, 5);
}

function scoreboard(rows, rawRate) {
  fill('scoreboard', rows.map((r) => {
    const gap = r.system === 'open-raw' ? '—' : pp(r.accepted_rate - rawRate);
    return `<tr${rowClass(r)}>
      <td>${esc(name(r.system))}${marks(r)}</td>
      <td class="num">${pct(r.accepted_rate)}</td>
      <td class="num">${ci(r.accepted_ci95, (v) => pct(v, 0))}</td>
      <td class="num${r.incorrect_returned_count ? ' bad' : ''}">${r.incorrect_returned_count}</td>
      <td class="num">${gap}</td>
      <td class="num">${money(r.cost_per_case_usd)}</td>
      <td class="num">${sec(r.latency_p50_ms)}</td>
      <td class="num">${r.cases}</td>
    </tr>`;
  }), 8);
}

function bars(id, rows, valueFn, formatFn) {
  const max = Math.max(0.01, ...rows.map((r) => valueFn(r) || 0));
  $(id).innerHTML = rows.map((r) => {
    const v = valueFn(r) || 0;
    return `<div class="bar-row">
      <div class="bar-label"><b>${esc(name(r.system))}</b><span>${esc(formatFn(r))}</span></div>
      <div class="track"><span class="fill" style="width:${(v / max) * 100}%"></span></div>
    </div>`;
  }).join('');
}

function safety(rows) {
  fill('safety', rows.map((r) => `<tr${rowClass(r)}>
    <td>${esc(name(r.system))}${marks(r)}</td>
    <td class="num${r.incorrect_returned_count ? ' bad' : ''}">${r.incorrect_returned_count}</td>
    <td class="num">${ci(r.incorrect_ci95, (v) => pct(v, 0))}</td>
    <td class="num">${r.wrong_candidates_caught ?? '—'}</td>
    <td class="num">${pct(r.decoy_safe_rate, 0)}</td>
    <td class="num">${pct(r.trap_incorrect_rate, 0)}</td>
    <td class="num">${num(r.geomean_speedup)}×</td>
    <td class="num">${ci(r.geomean_speedup_ci95, (v) => num(v) + '×')}</td>
  </tr>`), 8);
}

function efficiency(rows) {
  fill('efficiency', rows.map((r) => `<tr${rowClass(r)}>
    <td>${esc(name(r.system))}${marks(r)}</td>
    <td class="num">${sec(r.latency_p50_ms)}</td>
    <td class="num">${sec(r.latency_p95_ms)}</td>
    <td class="num">${sec(r.optimizer_llm_p50_ms)}</td>
    <td class="num">${sec(r.optimizer_verify_p50_ms)}</td>
    <td class="num">${num(r.calls_per_case, 1)}</td>
    <td class="num">${int(r.output_tokens_per_case)}</td>
    <td class="num">${money2((r.cost_per_case_usd || 0) * 1000)}</td>
  </tr>`), 8);
}

function outcomes(rows) {
  fill('outcomes', rows.map((r) => {
    const o = r.outcomes || {};
    const cell = (k, bad) => `<td class="num${bad && o[k] ? ' bad' : ''}">${o[k] ? pct(o[k]) : '0'}</td>`;
    return `<tr${rowClass(r)}>
      <td>${esc(name(r.system))}</td>
      ${cell('accepted')}${cell('no_change')}${cell('not_faster')}
      ${cell('regression', true)}${cell('incorrect', true)}${cell('invalid', true)}
    </tr>`;
  }), 7);
}

function byKind(rows, caseIndex) {
  fill('by-kind', rows.map((r) => {
    const t = { rewrite: {}, trap: {}, decoy: {} };
    const records = (r.records || []).filter((x) => caseIndex[x.case]);
    for (const x of records) {
      const kind = caseIndex[x.case].kind;
      t[kind][x.outcome] = (t[kind][x.outcome] || 0) + 1;
    }
    const wrong = (k) => (t[k].incorrect || 0) + (t[k].invalid || 0);
    const slower = Object.values(t).reduce((s, k) => s + (k.not_faster || 0) + (k.regression || 0), 0);
    const decoyN = Object.values(t.decoy).reduce((a, b) => a + b, 0);
    return `<tr${rowClass(r)}>
      <td>${esc(name(r.system))}</td>
      <td class="num">${t.rewrite.accepted || 0}</td>
      <td class="num${wrong('rewrite') ? ' bad' : ''}">${wrong('rewrite')}</td>
      <td class="num">${t.trap.accepted || 0}</td>
      <td class="num${wrong('trap') ? ' bad' : ''}">${wrong('trap')}</td>
      <td class="num">${t.decoy.no_change || 0}/${decoyN}</td>
      <td class="num">${slower}</td>
    </tr>`;
  }), 7);
}

function families(by, dev) {
  const counts = {};
  for (const c of dev.cases || []) counts[c.family] = (counts[c.family] || 0) + 1;
  const sys = ['rules-only', 'open-raw', 'frontier-raw', 'open-harness'].map((id) => by[id]);
  const fams = Object.keys(counts).sort((a, b) => counts[b] - counts[a] || a.localeCompare(b));
  fill('families', fams.map((f) => {
    const vals = sys.map((s) => s?.accepted_by_family?.[f]);
    const best = Math.max(...vals.filter(finite));
    return `<tr>
      <td>${esc(f.replaceAll('_', ' '))}</td>
      <td class="num">${counts[f]}</td>
      ${vals.map((v) => `<td class="num${finite(v) && v === best && best > 0 ? ' best' : ''}">${pct(v, 0)}</td>`).join('')}
    </tr>`;
  }), 6);
}

function ablation(by) {
  const rows = [];
  const fig = [];
  for (const [label, rawId, harnessId] of PAIRS) {
    const raw = by[rawId];
    const har = by[harnessId];
    if (!raw || !har) continue;
    rows.push(`<tr class="group"><td colspan="6">${esc(label)}</td></tr>`);
    const line = (r, tag) => `<tr${r.system === 'open-harness' ? ' class="ours"' : ''}>
      <td class="indent">${tag}${marks(r)}</td>
      <td class="num">${pct(r.accepted_rate)}</td>
      <td class="num${r.incorrect_returned_count ? ' bad' : ''}">${r.incorrect_returned_count}</td>
      <td class="num">${money(r.cost_per_case_usd)}</td>
      <td class="num">${sec(r.latency_p50_ms)}</td>
      <td class="num">${num(r.calls_per_case, 1)}</td>
    </tr>`;
    rows.push(line(raw, 'Raw'));
    if (rawId === 'open-raw' && by['open-harness-nocache']) {
      rows.push(line(by['open-harness-nocache'], 'Harness, no cache'));
    }
    rows.push(line(har, 'Harness'));
    fig.push({ label, raw: raw.incorrect_returned_count, har: har.incorrect_returned_count });
  }
  fill('ablation', rows, 6);

  const max = Math.max(1, ...fig.map((f) => f.raw));
  $('pairs-fig').innerHTML = fig.map((f) => `<div class="bar-row">
      <div class="bar-label"><b>${esc(f.label)}</b><span>${f.raw} → ${f.har}</span></div>
      <div class="track"><span class="fill" style="width:${(f.raw / max) * 100}%"></span></div>
      <div class="track"><span class="fill" style="width:${(f.har / max) * 100}%"></span></div>
    </div>`).join('');
}

function cacheText(by) {
  const a = by['open-harness-nocache'];
  const b = by['open-harness'];
  if (!a || !b) { $('cache-text').textContent = 'No-cache ablation not in this snapshot.'; return; }
  $('cache-text').innerHTML = `Turning the verified-positive fingerprint cache on (with the latency levers) moves the harness from
    ${pct(a.accepted_rate)} to <strong>${pct(b.accepted_rate)}</strong> accept, optimizer p50 from ${sec(a.latency_p50_ms)}
    to <strong>${sec(b.latency_p50_ms)}</strong>, calls per case from ${num(a.calls_per_case, 1)} to ${num(b.calls_per_case, 1)},
    output tokens from ${int(a.output_tokens_per_case)} to ${int(b.output_tokens_per_case)}, and API cost from
    ${money(a.cost_per_case_usd)} to ${money(b.cost_per_case_usd)} per case. Both runs return 0 wrong. A cache hit is only
    replayed after it was verified once, so it cannot introduce an incorrect rewrite. The trade-off is the tail:
    p95 rises from ${sec(a.latency_p95_ms)} to ${sec(b.latency_p95_ms)} because misses fall through to repair.`;
}

function pairedComps(data) {
  return (data.paired_stats?.comparisons || [])
    .filter((c) => c.system === 'open-harness' && c.split === 'dev')
    .concat((data.paired_stats?.comparisons || []).filter((c) => c.system !== 'open-harness' && c.split === 'dev'))
    .sort((a, b) => {
      const ia = a.system === 'open-harness' ? BASE_ORDER.indexOf(a.baseline) : 9;
      const ib = b.system === 'open-harness' ? BASE_ORDER.indexOf(b.baseline) : 9;
      return ia - ib;
    });
}
const vsLabel = (c) => `${name(c.system).replace(' (ours)', '')} vs ${name(c.baseline)}`;

function contingency(data) {
  const m = data.splits?.dev?.comparisons?.['open-raw']?.['open-harness']?.mcnemar?.accepted;
  if (!m) { fill('contingency-accept', [], 3); return; }
  const both = m.table?.[1]?.[1];
  const neither = m.table?.[0]?.[0];
  fill('contingency-accept', [
    `<tr><td><strong>Raw accepted</strong></td><td class="num">${both} (both)</td><td class="num"><strong>${m.baseline_only}</strong> (raw only)</td></tr>`,
    `<tr><td><strong>Raw not</strong></td><td class="num"><strong>${m.a_only}</strong> (harness only)</td><td class="num">${neither} (neither)</td></tr>`,
  ], 3);
  $('contingency-note').textContent = `Discordant ${m.a_only} vs ${m.baseline_only}; exact two-sided p = ${pval(m.p_value)}. `
    + `Rate difference ${pp(m.rate_difference_a_minus_baseline)}, template-bootstrap 95% CI ${ci(m.difference_ci95_template_bootstrap)}.`;
}

function mcnemarTables(comps) {
  fill('mcnemar-accept', comps.map((c) => {
    const m = c.mcnemar_accepted || {};
    return `<tr>
      <td>${esc(vsLabel(c))}</td>
      <td class="num">${m.a_only}</td>
      <td class="num">${m.baseline_only}</td>
      <td class="num">${m.both}</td>
      <td class="num">${m.neither}</td>
      <td class="num">${pval(m.p_value)}</td>
      <td>${esc(callAccept(m.p_value, c.bootstrap_accept_gap?.ci95))}</td>
    </tr>`;
  }), 7);

  fill('mcnemar-wrong', comps.map((c) => {
    const m = c.mcnemar_incorrect || {};
    const call = m.discordant === 0 ? 'Both 0 wrong'
      : m.p_value < 0.05 && m.baseline_only > m.a_only ? 'Harness safer'
      : 'Not significant';
    return `<tr>
      <td>${esc(vsLabel(c))}</td>
      <td class="num">${m.a_only}</td>
      <td class="num">${m.baseline_only}</td>
      <td class="num">${m.discordant}</td>
      <td class="num">${m.discordant ? pval(m.p_value) : '—'}</td>
      <td>${esc(call)}</td>
    </tr>`;
  }), 6);
}

function bootstrapTable(comps) {
  fill('bootstrap', comps.map((c) => {
    const g = c.bootstrap_accept_gap || {};
    return `<tr>
      <td>${esc(vsLabel(c))}</td>
      <td class="num">${pp(g.mean)}</td>
      <td class="num">${ci(g.ci95)}</td>
      <td class="num">${g.clusters ?? '—'}</td>
      <td>${esc(callAccept(c.mcnemar_accepted?.p_value, g.ci95))}</td>
    </tr>`;
  }), 5);
}

function templateSens(data) {
  const mc = data.splits?.dev?.comparisons?.['open-raw']?.['open-harness']?.mcnemar;
  if (!mc) { fill('template-sens', [], 6); return; }
  const rows = [['Accepted', mc.accepted?.template_sensitivity], ['Incorrect', mc.incorrect_returned?.template_sensitivity]];
  fill('template-sens', rows.map(([label, t]) => `<tr>
    <td>${label}</td>
    <td class="num">${t?.a_only ?? '—'}</td>
    <td class="num">${t?.baseline_only ?? '—'}</td>
    <td class="num">${t?.pairs ?? '—'}</td>
    <td class="num">${pval(t?.p_value)}</td>
    <td>${esc(t?.definition || '—')}</td>
  </tr>`), 6);
}

function resources(data) {
  const vsRaw = data.splits?.dev?.comparisons?.['open-raw']?.['open-harness']?.paired_metrics;
  const vsFr = data.splits?.dev?.comparisons?.['frontier-raw']?.['open-harness']?.paired_metrics;
  if (!vsRaw) { fill('resources', [], 7); return; }
  const s = (v) => finite(v) ? (v / 1000).toFixed(1) + 's' : '—';
  const specs = [
    ['API $ / case', 'cost_usd', money],
    ['Optimizer time', 'latency_ms', s],
    ['LLM time', 'llm_ms', s],
    ['Verify time', 'verify_ms', (v) => finite(v) ? (v / 1000).toFixed(2) + 's' : '—'],
    ['Model calls', 'calls', (v) => num(v, 2)],
    ['Output tokens', 'output_tokens', int],
    ['SQL speedup (×)', 'speedup', (v) => num(v, 2)],
  ];
  fill('resources', specs.map(([label, key, fmt]) => {
    const a = vsRaw[key];
    const b = vsFr?.[key];
    const ratio = (m) => finite(m?.ratio_of_means_a_over_baseline) ? num(m.ratio_of_means_a_over_baseline) + '×' : '—';
    return `<tr>
      <td>${label}${a?.excluded_pairs ? ` <span class="sub-inline">(${a.pairs} pairs)</span>` : ''}</td>
      <td class="num">${fmt(a?.mean_a)}</td>
      <td class="num">${fmt(a?.mean_baseline)}</td>
      <td class="num">${fmt(b?.mean_baseline)}</td>
      <td class="num">${ratio(a)}</td>
      <td class="num">${ratio(b)}</td>
      <td class="num">${ci(a?.difference_ci95_template_bootstrap, fmt)}</td>
    </tr>`;
  }), 7);
}

function caseStudies(by, caseIndex) {
  const raw = by['open-raw'];
  const har = Object.fromEntries((by['open-harness']?.records || []).map((r) => [r.case, r]));
  const wrong = (raw?.records || []).filter((r) => r.outcome === 'incorrect' || r.outcome === 'invalid');
  const tally = {};
  fill('raw-wrong', wrong.map((r) => {
    const h = har[r.case] || {};
    tally[h.outcome] = (tally[h.outcome] || 0) + 1;
    const c = caseIndex[r.case] || {};
    const label = (c.template || r.case).replace(/^calcite_test/, 'calcite: ');
    return `<tr>
      <td class="mono">${esc(label)}</td>
      <td>${esc((c.family || '').replaceAll('_', ' '))}</td>
      <td>${esc(OUTCOME_LABEL[h.outcome] || h.outcome || '—')}</td>
      <td class="num">${h.outcome === 'accepted' ? num(h.speedup, 1) + '×' : '—'}</td>
    </tr>`;
  }), 4);
  const kept = (tally.no_change || 0) + (tally.not_faster || 0);
  $('cases-text').innerHTML = `Open-raw returned ${wrong.length} incorrect results. On those same cases the harness
    returned <strong>${tally.accepted || 0} verified faster rewrites</strong> and kept the original query on
    <strong>${kept}</strong>; it returned <strong>${(tally.incorrect || 0) + (tally.invalid || 0)}</strong> incorrect.
    The model is the same—the difference is that wrong candidates never leave the harness.`;
}

function localModels(by) {
  fill('local', pick(by, LOCAL).map((r) => `<tr>
    <td>${esc(name(r.system))}</td>
    <td class="num">${pct(r.accepted_rate)}</td>
    <td class="num${r.incorrect_returned_count ? ' bad' : ''}">${r.incorrect_returned_count}</td>
    <td class="num">${r.outcomes?.invalid ? pct(r.outcomes.invalid) : '0'}</td>
    <td class="num">${pct(r.trap_incorrect_rate, 0)}</td>
    <td class="num">${sec(r.latency_p50_ms)}</td>
  </tr>`), 6);
}

function heldout(data) {
  const h = data.splits?.heldout;
  if (!h) { $('heldout-text').textContent = 'No held-out split in this snapshot.'; fill('heldout', [], 5); return; }
  const rows = (h.systems || []).slice().sort((a, b) => b.cases - a.cases);
  const complete = rows.filter((r) => r.complete).map((r) => name(r.system));
  $('heldout-text').innerHTML = `The held-out split has ${h.expected_cases} cases from ${h.templates} templates never used in development.
    So far only ${complete.length ? esc(complete.join(', ')) : 'no system'} has complete held-out coverage; frontier-raw has a
    single-case smoke run. The harness held-out run is the most important missing experiment, and we do not claim held-out
    generalization until it is in. Rules-only rising from ${pct(data.splits.dev.systems.find((s) => s.system === 'rules-only')?.accepted_rate)}
    on development to ${pct(rows.find((r) => r.system === 'rules-only')?.accepted_rate)} on held-out shows the split is not trivially harder for mechanical rewrites.`;
  fill('heldout', rows.map((r) => `<tr>
    <td>${esc(name(r.system))}${marks(r)}</td>
    <td class="num">${pct(r.accepted_rate)}</td>
    <td class="num">${r.incorrect_returned_count}</td>
    <td class="num">${num(r.geomean_speedup)}×</td>
    <td class="num">${r.cases}/${r.expected_cases}</td>
  </tr>`), 5);
}

function allSystems(dev, pareto) {
  const rows = (dev.systems || []).slice().sort((a, b) => b.accepted_rate - a.accepted_rate);
  fill('all-systems', rows.map((r) => `<tr${rowClass(r)}>
    <td>${esc(r.system)}${marks(r)}</td>
    <td class="num">${pct(r.accepted_rate)}</td>
    <td class="num${r.incorrect_returned_count ? ' bad' : ''}">${r.incorrect_returned_count}</td>
    <td class="num">${num(r.geomean_speedup)}×</td>
    <td class="num">${money(r.cost_per_case_usd)}</td>
    <td class="num">${sec(r.latency_p50_ms)}</td>
    <td class="num">${r.cases}/${r.expected_cases}</td>
    <td class="num">${r.trials}</td>
  </tr>`), 8);
  if (pareto?.length) {
    $('pareto-note').textContent = `Safe cost–quality Pareto set (0 wrong, from summary_dev.json): ${pareto.join(', ')}. `
      + 'These are cheapest-for-their-accept-rate among safe systems; open-harness trades a little cost for higher, complete-coverage accept.';
  }
}

function reading(comps) {
  const get = (b) => comps.find((c) => c.system === 'open-harness' && c.baseline === b);
  const vsRaw = get('open-raw');
  const vsFr = get('frontier-raw');
  const vsRules = get('rules-only');
  const fast = comps.find((c) => c.system === 'fw-fast-harness');
  const out = [];
  out.push(`<p><strong>Headline.</strong> The claim is not “we beat every closed model.” It is: the same open model, behind a
    verify-or-abstain gate, stops returning wrong SQL, lifts beneficial accepts past blind raw, and stays competitive on cost and median latency.</p>`);
  if (vsRaw) {
    out.push(`<p><strong>Versus open-raw (required comparison).</strong> Accept gap ${pp(vsRaw.bootstrap_accept_gap?.mean)},
      bootstrap 95% CI ${ci(vsRaw.bootstrap_accept_gap?.ci95)} (excludes 0). McNemar ${vsRaw.mcnemar_accepted?.a_only} vs
      ${vsRaw.mcnemar_accepted?.baseline_only}, p = ${pval(vsRaw.mcnemar_accepted?.p_value)}. Wrong returns
      ${vsRaw.incorrect_count_b} → ${vsRaw.incorrect_count_a}, p = ${pval(vsRaw.mcnemar_incorrect?.p_value)}.
      Both tests agree, and the result survives one-vote-per-template sensitivity. This is a real gain.</p>`);
  }
  if (vsFr) {
    out.push(`<p><strong>Versus frontier-raw (optional).</strong> Accept gap ${pp(vsFr.bootstrap_accept_gap?.mean)}, CI
      ${ci(vsFr.bootstrap_accept_gap?.ci95)} includes 0; McNemar ${vsFr.mcnemar_accepted?.a_only} vs
      ${vsFr.mcnemar_accepted?.baseline_only}, p = ${pval(vsFr.mcnemar_accepted?.p_value)}. We do <strong>not</strong>
      claim a statistical accept win. We do claim parity-or-better on the board, lower API $/case, and lower median latency.</p>`);
  }
  if (vsRules) {
    out.push(`<p><strong>Versus rules-only.</strong> Gap ${pp(vsRules.bootstrap_accept_gap?.mean)}, p = ${pval(vsRules.mcnemar_accepted?.p_value)}.
      Rules are free and safe but cover little; they are the floor the harness builds on.</p>`);
  }
  if (fast) {
    out.push(`<p><strong>The gate transfers.</strong> fw-fast-harness vs fw-fast-raw: gap ${pp(fast.bootstrap_accept_gap?.mean)},
      CI ${ci(fast.bootstrap_accept_gap?.ci95)}, p = ${pval(fast.mcnemar_accepted?.p_value)}—also a real gain on a different model.
      Table IX shows wrong returns falling to 0 for every pair.</p>`);
  }
  out.push(`<p><strong>What not to over-read.</strong> Mean optimizer time (Table XV) includes verify and repair and is higher than raw;
    the median is what an agent sees on most calls, the tail is what it sees on hard ones. Geomean speedups on microfixtures are not
    warehouse savings until weighted by real traffic.</p>`);
  $('reading').innerHTML = out.join('');
}

function render(data, pareto) {
  const dev = data.splits?.dev;
  if (!dev) throw new Error('No development split');
  const by = Object.fromEntries((dev.systems || []).map((s) => [s.system, s]));
  const caseIndex = Object.fromEntries((dev.cases || []).map((c) => [c.id, c]));
  const raw = by['open-raw'];

  $('n-dev').textContent = dev.expected_cases;
  $('n-tpl').textContent = dev.templates;
  if (data.splits.heldout) {
    $('n-held').textContent = data.splits.heldout.expected_cases;
    $('n-held-tpl').textContent = data.splits.heldout.templates;
  }
  $('sha').textContent = (dev.cases_sha256 || '').slice(0, 16) + '…';
  $('stamp').textContent = 'Snapshot ' + new Date(data.generated_at).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  }) + ' · development split · accept CI is a case bootstrap.';

  composition(dev);
  const main = pick(by, MAIN);
  const core = pick(by, CORE);
  const detail = pick(by, DETAIL);
  scoreboard(main, raw?.accepted_rate);
  bars('accept', core, (r) => r.accepted_rate, (r) => pct(r.accepted_rate));
  bars('wrong', core, (r) => r.incorrect_returned_count, (r) => String(r.incorrect_returned_count));
  bars('cost', core, (r) => (r.cost_per_case_usd || 0) * 1000, (r) => money2((r.cost_per_case_usd || 0) * 1000));
  bars('latency', core, (r) => (r.latency_p50_ms || 0) / 1000, (r) => sec(r.latency_p50_ms));
  safety(detail);
  efficiency(detail);
  outcomes(detail);
  byKind(detail, caseIndex);
  families(by, dev);
  ablation(by);
  cacheText(by);

  const comps = pairedComps(data);
  contingency(data);
  mcnemarTables(comps);
  bootstrapTable(comps);
  templateSens(data);
  resources(data);
  caseStudies(by, caseIndex);
  localModels(by);
  heldout(data);
  allSystems(dev, pareto);
  reading(comps);
}

Promise.all([
  fetch('data/research.json', { cache: 'no-store' }).then((r) => {
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }),
  fetch('data/summary_dev.json', { cache: 'no-store' })
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null),
])
  .then(([data, summary]) => render(data, summary?.pareto_safe))
  .catch((err) => {
    $('stamp').textContent = 'Snapshot unavailable.';
    $('reading').innerHTML = `<p class="empty">${esc(err.message)}</p>`;
  });
