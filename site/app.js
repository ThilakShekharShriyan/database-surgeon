'use strict';

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value == null ? '' : value).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const finite = (v) => typeof v === 'number' && Number.isFinite(v);
const pct = (v) => finite(v) ? (v * 100).toFixed(1) + '%' : '—';
const num = (v, d = 2) => finite(v) ? v.toLocaleString('en-US', {minimumFractionDigits:d, maximumFractionDigits:d}) : '—';
const money = (v) => finite(v) ? '$' + num(v, v && v < .01 ? 4 : 2) : 'Unknown';
const pv = (v) => !finite(v) ? '—' : v < .0001 ? v.toExponential(2) : v.toFixed(4);
const names = {'frontier-raw':'Frontier raw','open-raw':'Open raw · Fireworks','open-harness':'Open harness · Fireworks','rules-only':'Rules only','fw-nemotron-harness':'Nemotron harness','cascade-surgeon':'Cascade Surgeon'};
const label = (r) => names[r.system] || r.system;
const priority = ['frontier-raw','open-raw','open-harness','rules-only','fw-nemotron-harness','cascade-surgeon'];
let snapshot, split = 'dev', includePartial = false, selected = 'open-harness';
const empty = (text) => '<p class="empty">' + esc(text) + '</p>';
const state = () => snapshot && snapshot.splits[split];
const visible = () => (state()?.systems || []).filter((r) => includePartial || r.complete);
const core = () => visible().filter((r) => priority.includes(r.system)).sort((a,b) => priority.indexOf(a.system) - priority.indexOf(b.system));
const coverage = (r) => String(r.cases) + '/' + String(r.expected_cases) + (r.complete ? ' · complete' : ' · partial');
const testText = (r) => esc(label(r)) + (r.complete ? '' : ' · partial');

function acceptance(rows) {
  $('acceptance').innerHTML = rows.length ? rows.map((r) => {
    const ci = r.accepted_ci95;
    return '<div class="measure-row"><div class="measure-label"><b>' + testText(r) + '</b><span>' + pct(r.accepted_rate) + '</span></div><div class="track" role="img" aria-label="' + esc(label(r) + ': ' + pct(r.accepted_rate) + ' accepted; ' + coverage(r)) + '"><span class="fill" style="width:' + (100 * r.accepted_rate) + '%"></span>' +
      (Array.isArray(ci) ? '<span class="whisker" style="left:' + (100 * ci[0]) + '%;width:' + (100 * (ci[1] - ci[0])) + '%" title="95% CI ' + pct(ci[0]) + ' to ' + pct(ci[1]) + '"></span>' : '') + '</div></div>';
  }).join('') : empty('No core-system results match this coverage filter.');
}

function costChart(rows) {
  rows = rows.filter((r) => finite(r.cost_per_case_usd));
  if (!rows.length) { $('cost-chart').innerHTML = empty('No priced core-system results for this split.'); return; }
  const W=560,H=245,pad={l:45,r:20,t:25,b:43};
  const max = Math.max(.1,...rows.map((r) => r.cost_per_case_usd * 1000)) * 1.2;
  const x = (v) => pad.l + v/max*(W-pad.l-pad.r);
  const y = (v) => H-pad.b-v*(H-pad.t-pad.b);
  const grids = [0,.25,.5,.75,1].map((v) => '<line class="grid" x1="'+pad.l+'" x2="'+(W-pad.r)+'" y1="'+y(v)+'" y2="'+y(v)+'"/><text x="'+(pad.l-8)+'" y="'+(y(v)+4)+'" text-anchor="end">'+pct(v)+'</text>').join('');
  const ticks = [0,.25,.5,.75,1].map((v) => '<text x="'+x(max*v)+'" y="'+(H-22)+'" text-anchor="middle">'+money(max*v)+'</text>').join('');
  $('cost-chart').innerHTML = '<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Acceptance rate against API cost per thousand optimization cases">'+grids+ticks+'<text class="axis-label" x="'+(W/2)+'" y="'+(H-3)+'" text-anchor="middle">API cost / 1,000 cases →</text>'+rows.map((r,i) => {
    const cx=x(r.cost_per_case_usd*1000),cy=y(r.accepted_rate);
    const color = r.incorrect_returned_count ? '#f08494' : '#7eb4ec';
    const right = cx > W * .65, offset = [18,-13,-13,17,-13,17][i] || 15;
    return '<g><circle cx="'+cx+'" cy="'+cy+'" r="5" fill="'+(r.incorrect_returned_count?'#131217':color)+'" stroke="'+color+'" stroke-width="1.7"><title>'+esc(label(r)+': '+pct(r.accepted_rate)+' accepted; '+money(r.cost_per_case_usd*1000)+'/1k; '+r.incorrect_returned_count+' incorrect; '+coverage(r))+'</title></circle><text class="point-label" text-anchor="'+(right?'end':'start')+'" x="'+(cx+(right?-8:8))+'" y="'+(cy+offset)+'">'+esc(label(r).replace(' · Fireworks',''))+'</text></g>';
  }).join('')+'</svg>';
}

function latency(rows) {
  const max = Math.max(1,...rows.map((r) => r.latency_p95_ms || 0));
  $('latency').innerHTML = rows.length ? rows.map((r) => '<div class="measure-row"><div class="measure-label"><b>'+testText(r)+'</b><span>p50 '+num(r.latency_p50_ms/1000,1)+'s / p95 '+num(r.latency_p95_ms/1000,1)+'s</span></div><div class="track" role="img" aria-label="'+esc(label(r)+' median '+num(r.latency_p50_ms/1000,1)+' seconds, p95 '+num(r.latency_p95_ms/1000,1)+' seconds')+'"><span class="p95" style="width:'+(r.latency_p95_ms/max*100)+'%"></span><span class="fill" style="width:'+(r.latency_p50_ms/max*100)+'%"></span></div></div>').join('') : empty('No core-system latency records for this split.');
}

function outcomes(rows) {
  $('outcomes').innerHTML = rows.length ? rows.map((r) => {
    const o=r.outcomes||{};
    const bins=[['accepted',o.accepted||0],['no_change',o.no_change||0],['not_faster',o.not_faster||0],['incorrect',(o.incorrect||0)+(o.invalid||0)],['regression',o.regression||0]];
    return '<div class="measure-row"><div class="measure-label"><b>'+testText(r)+'</b><span>'+coverage(r)+'</span></div><div class="track" role="img" aria-label="'+esc(label(r)+': '+bins.map(([n,v])=>n+' '+pct(v)).join(', '))+'">'+bins.map(([n,v])=>'<span class="'+n+'" style="width:'+(v*100)+'%" title="'+esc(n)+' '+pct(v)+'"></span>').join('')+'</div></div>';
  }).join('') : empty('No core-system outcomes for this split.');
}

function families(rows) {
  const all = [...new Set(rows.flatMap((r) => Object.keys(r.accepted_by_family || {})))].sort();
  $('families').innerHTML = rows.length ? '<table><thead><tr><th>Query family</th>'+rows.map((r)=>'<th class="num">'+testText(r)+'</th>').join('')+'</tr></thead><tbody>'+all.map((family)=>'<tr><td>'+esc(family.replaceAll('_',' '))+'</td>'+rows.map((r)=>{
    const v=r.accepted_by_family?.[family];
    return '<td class="num"><span class="heat" style="background:rgba(126,180,236,'+(finite(v)? .04+.24*v : 0)+')">'+pct(v)+'</span></td>';
  }).join('')+'</tr>').join('')+'</tbody></table>' : empty('No family comparisons for this coverage filter.');
}

function paired() {
  const base = $('baseline').value;
  const comparison = state()?.comparisons?.[base]?.[selected];
  if (!comparison || !comparison.pairs) { $('paired-tests').innerHTML = empty('No matched trial-0 records for this system and baseline on the selected split.'); return; }
  const tests = [['accepted','Beneficial acceptance'],['incorrect_returned','Incorrect returns']];
  $('paired-tests').innerHTML = tests.map(([key,title])=>{
    const t=comparison.mcnemar[key], s=t.template_sensitivity;
    return '<article class="test"><h3>'+title+'</h3><div class="test-value">'+pv(t.p_value)+'<small>exact McNemar p</small></div><p>'+comparison.pairs+'/'+comparison.expected_cases+' matched cases · trial '+comparison.trial+(comparison.complete?' · complete':' · shared subset')+'</p><div class="test-grid"><div><strong>'+t.a_only+'</strong>System A only</div><div><strong>'+t.baseline_only+'</strong>Baseline only</div></div><p>Template sensitivity: p='+pv(s?.p_value)+' · '+(s?.pairs||0)+' complete templates.</p><p>'+(key==='accepted'?'Higher acceptance is beneficial.':'Fewer incorrect returns is beneficial. Neither an abstention nor an invalid query counts as an accepted optimization.')+'</p></article>';
  }).join('')+'<article class="test paired-measures"><h3>Matched resource and performance estimates</h3><div class="table-wrap"><table><thead><tr><th>Measure</th><th class="num">A mean</th><th class="num">Baseline mean</th><th class="num">A / baseline</th><th class="num">Difference 95% CI</th><th class="num">Pairs</th></tr></thead><tbody>'+[
    ['cost_usd','API cost / case',money],
    ['latency_ms','Optimizer time (s)',v=>num(finite(v)?v/1000:null,2)],
    ['verify_ms','Verification time (s)',v=>num(finite(v)?v/1000:null,2)],
    ['calls','Model calls',v=>num(v,2)],
    ['speedup','SQL speedup (×)',v=>num(v,2)]
  ].map(([key,title,fmt])=>{
    const m=comparison.paired_metrics[key],ci=m?.difference_ci95_template_bootstrap;
    return '<tr><td>'+title+'</td><td class="num">'+fmt(m?.mean_a)+'</td><td class="num">'+fmt(m?.mean_baseline)+'</td><td class="num">'+num(m?.ratio_of_means_a_over_baseline,2)+'×</td><td class="num">'+(ci?fmt(ci[0])+' to '+fmt(ci[1]):'—')+'</td><td class="num">'+(m?.pairs||0)+'</td></tr>';
  }).join('')+'</tbody></table></div><p class="method-note">Differences are A minus baseline; intervals resample whole templates. Lower resource use is better; higher SQL speedup is better. Speedup excludes incorrect/invalid output pairs and is not workload-weighted savings. API cost excludes compute; recorded optimizer time excludes queueing and throttling.</p><details class="provenance"><summary>Comparison warnings</summary>'+comparison.warnings.map((w)=>'<p>'+esc(w)+'</p>').join('')+'</details></article>';
}

function systems(rows) {
  $('systems').innerHTML = rows.length ? '<table><thead><tr><th>System</th><th>Coverage</th><th class="num">Accepted</th><th class="num">95% CI</th><th class="num">Wrong</th><th class="num">p50 / p95</th><th class="num">API $ / 1k</th><th class="num">Calls / case</th></tr></thead><tbody>'+rows.map((r)=>'<tr><td>'+esc(label(r))+'<small>'+esc(r.system)+' · '+r.trials+' trial'+(r.trials===1?'':'s')+(r.simulated?' · simulated':'')+'</small></td><td class="'+(r.complete?'good':'partial')+'">'+coverage(r)+'</td><td class="num">'+pct(r.accepted_rate)+'</td><td class="num">'+pct(r.accepted_ci95?.[0])+'–'+pct(r.accepted_ci95?.[1])+'</td><td class="num '+(r.incorrect_returned_count?'bad':'')+'">'+r.incorrect_returned_count+'</td><td class="num">'+num(r.latency_p50_ms/1000,1)+' / '+num(r.latency_p95_ms/1000,1)+' s</td><td class="num">'+money(finite(r.cost_per_case_usd)?r.cost_per_case_usd*1000:null)+'</td><td class="num">'+num(r.calls_per_case,1)+'</td></tr>').join('')+'</tbody></table>' : empty('No systems match this coverage filter. Include partial systems to inspect unfinished runs.');
  $('download-csv').disabled=!rows.length;
}

function render() {
  const data=state(),rows=visible(),charts=core();
  document.querySelectorAll('[data-split]').forEach((b)=>{const on=b.dataset.split===split;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));});
  if (!data) { $('finding').textContent='No snapshot for this split.'; return; }
  const complete=data.systems.filter((r)=>r.complete);
  const baseline=data.systems.find((r)=>r.system==='frontier-raw');
  const harness=data.systems.find((r)=>r.system==='open-harness');
  $('snapshot-status').textContent='Snapshot '+new Date(snapshot.generated_at).toLocaleString()+' · '+(split==='dev'?'Development: exploratory evidence':'Held-out: inspect completeness before comparing')+' · charts show predefined core systems, table includes all visible systems.';
  $('finding').textContent=split==='dev'&&harness&&baseline?
    'Open harness: '+pct(harness.accepted_rate)+' accepted, '+harness.incorrect_returned_count+' incorrect returned. Frontier raw: '+pct(baseline.accepted_rate)+' accepted, '+baseline.incorrect_returned_count+' incorrect returned. Quality, cost and latency are separate questions.':
    complete.length+' of '+data.systems.length+' recorded systems have complete '+split+' coverage. Partial comparisons describe their matched subset only.';
  $('facts').innerHTML=[['Expected cases',data.expected_cases,'In the selected split'],['Template groups',data.templates,'Related variants share a group'],['Complete systems',complete.length+' / '+data.systems.length,'Every expected case in every trial'],['Visible systems',rows.length,includePartial?'Includes partial records':'Complete records only']].map(([l,v,n])=>'<div><span>'+l+'</span><strong>'+v+'</strong><small>'+n+'</small></div>').join('');
  acceptance(charts);costChart(charts);latency(charts);outcomes(charts);families(charts);systems(rows);
  const choices=rows.filter((r)=>r.system!==$('baseline').value);
  if(!choices.some((r)=>r.system===selected))selected=choices.find((r)=>r.system==='open-harness')?.system||choices[0]?.system||'';
  $('system-a').innerHTML=choices.map((r)=>'<option value="'+esc(r.system)+'"'+(r.system===selected?' selected':'')+'>'+esc(label(r))+(r.complete?'':' · partial')+'</option>').join('');
  paired();
  $('provenance').innerHTML='<p>Generated: '+esc(snapshot.generated_at)+'</p><p>Source: <code>'+esc(snapshot.source)+'</code></p><p>Selected split case SHA-256: <code>'+esc(data.cases_sha256)+'</code></p><p>Comparison trial: '+snapshot.comparison_trial+'</p>'+(snapshot.warnings.length?snapshot.warnings.map((w)=>'<p>'+esc(w)+'</p>').join(''):'<p>No export warnings recorded.</p>');
}

document.querySelectorAll('[data-split]').forEach((b)=>b.addEventListener('click',()=>{split=b.dataset.split;if(snapshot)render();}));
$('partial').addEventListener('change',(e)=>{includePartial=e.target.checked;if(snapshot)render();});
$('system-a').addEventListener('change',(e)=>{selected=e.target.value;paired();});
$('baseline').addEventListener('change',()=>{if(snapshot)render();});
$('download-csv').addEventListener('click',()=>{
  const fields=['system','cases','expected_cases','complete','trials','accepted_rate','incorrect_returned_count','cost_per_case_usd','latency_p50_ms','latency_p95_ms','calls_per_case'];
  const csv=[fields,...visible().map((r)=>fields.map((f)=>r[f]))].map((r)=>r.map((v)=>'"'+String(v==null?'':v).replaceAll('"','""')+'"').join(',')).join('\r\n');
  const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='database-surgeon-'+split+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
fetch('data/research.json',{cache:'no-store'}).then((r)=>{if(!r.ok)throw Error('Snapshot HTTP '+r.status);return r.json();}).then((data)=>{if(!data.splits)throw Error('Snapshot has no splits');snapshot=data;render();}).catch((error)=>{
  $('snapshot-status').textContent='Evidence snapshot unavailable.';
  $('finding').textContent='Serve this directory with a static HTTP server and export the snapshot with scripts/export_research.py. No model or database service is required to read saved results. '+error.message;
  ['acceptance','cost-chart','latency','outcomes','families','systems','paired-tests'].forEach((id)=>{$(id).innerHTML=empty('No measurements loaded.');});
});
