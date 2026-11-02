"use client";

import type { ResearchCase, ResearchSystem } from "@/lib/research-types";

export const percent = (n: number) => `${(n * 100).toFixed(1)}%`;
export const money = (n: number | null | undefined, digits = 2) => n == null ? "—" : `$${n.toFixed(digits)}`;
export const seconds = (ms: number) => `${(ms / 1000).toFixed(2)} s`;
export const label = (s: string) => ({"frontier-raw":"Frontier · raw","open-raw":"Open · raw",
  "open-harness":"Open · harness","rules-only":"Rules only","fw-fast-raw":"GLM Flash · raw",
  "fw-fast-harness":"GLM Flash · harness","fw-nemotron-harness":"Nemotron · harness",
  "fw-nemotron-raw":"Nemotron · raw","cascade-surgeon":"Surgeon cascade",
  "oss20b-harness":"OSS 20B · harness","oss20b-raw":"OSS 20B · raw"}[s] || s.replace("ollama-", "Local · ").replaceAll("-", " "));
const W = 640, H = 270, L = 48, R = 22, T = 15, B = 44;
const PX = W - L - R, PY = H - T - B;
const ticks = [0, .25, .5, .75, 1];

export function Tradeoff({rows, selected, baseline, axis, onSelect}:{rows:ResearchSystem[]; selected:string; baseline:string;
  axis:"cost"|"latency"; onSelect:(name:string)=>void}) {
  const value=(r:ResearchSystem)=>axis==="cost" ? r.cost_per_case_usd == null ? null : r.cost_per_case_usd*1000 : r.latency_p50_ms/1000;
  const known=rows.filter(r=>value(r)!=null);
  const max=Math.max(.1,...known.map(r=>value(r)!))*1.12;
  const x=(v:number)=>L+v/max*PX, y=(v:number)=>T+(1-v)*PY;
  return <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Accepted rewrite rate versus ${axis}; select a system point to inspect it`}>
    {ticks.map(v=><g key={v}><line className="r-grid" x1={L} x2={W-R} y1={y(v)} y2={y(v)}/><text x={L-9} y={y(v)+4} textAnchor="end">{Math.round(v*100)}%</text></g>)}
    {ticks.map(v=><text key={v} x={x(v*max)} y={H-B+21} textAnchor={v===0?"start":v===1?"end":"middle"}>{axis==="cost"?"$":""}{(v*max).toFixed(1)}</text>)}
    <text className="r-axis-label" x={W/2} y={H-4} textAnchor="middle">{axis==="cost"?"API cost / 1,000 optimizations (USD)":"Median optimizer latency (seconds)"} · lower is better</text>
    {known.map(r=>{const active=r.system===selected;return <g key={r.system} tabIndex={0} role="button"
      aria-label={`${label(r.system)}, ${percent(r.accepted_rate)} accepted, ${value(r)?.toFixed(3)} ${axis}, ${r.cases}/${r.expected_cases} cases`}
      onClick={()=>onSelect(r.system)} onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();onSelect(r.system);}}}>
      <title>{`${label(r.system)}: ${percent(r.accepted_rate)} · ${r.cases}/${r.expected_cases} · ${r.incorrect_returned_count} incorrect`}</title>
      <line x1={x(value(r)!)} x2={x(value(r)!)} y1={y(r.accepted_ci95[0])} y2={y(r.accepted_ci95[1])} className="r-whisker"/>
      <circle cx={x(value(r)!)} cy={y(r.accepted_rate)} r={active?7:5} className={`r-point ${active?"selected":r.system===baseline?"baseline":""} ${r.incorrect_returned_count?"incorrect":""}`} strokeDasharray={r.complete?undefined:"2 2"}/>
      <circle cx={x(value(r)!)} cy={y(r.accepted_rate)} r={13} fill="transparent"/>
    </g>})}
  </svg>;
}

export function Acceptance({rows,selected}:{rows:ResearchSystem[];selected:string}) {
  const left=184, width=385, height=rows.length*35+38;
  return <svg viewBox={`0 0 640 ${height}`} role="img" aria-label="Acceptance rates and descriptive case-bootstrap 95% intervals">
    {ticks.map(v=><g key={v}><line className="r-grid" x1={left+v*width} x2={left+v*width} y1={8} y2={height-24}/><text x={left+v*width} y={height-6} textAnchor="middle">{Math.round(v*100)}%</text></g>)}
    {rows.map((r,i)=>{const y=19+i*35;return <g key={r.system}><text x={left-12} y={y+4} textAnchor="end" className="r-row-label">{label(r.system)}</text>
      <line x1={left+r.accepted_ci95[0]*width} x2={left+r.accepted_ci95[1]*width} y1={y} y2={y} className={r.system===selected?"r-series-a":"r-series-b"} strokeWidth={2}/>
      <circle cx={left+r.accepted_rate*width} cy={y} r={4} className={r.system===selected?"r-dot-a":"r-dot-b"}/>
      <text x={630} y={y+4} textAnchor="end">{percent(r.accepted_rate)}</text></g>})}
  </svg>;
}

export function LatencyCDF({a,b}:{a:ResearchSystem;b?:ResearchSystem}) {
  const values=[a,b].filter(Boolean) as ResearchSystem[];
  const max=Math.max(1,...values.flatMap(r=>r.records.map(v=>v.latency_ms/1000)));
  const maxLog=Math.log10(1+max);
  const x=(v:number)=>L+Math.log10(1+v)/maxLog*PX,y=(v:number)=>T+(1-v)*PY;
  return <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Empirical cumulative optimizer latency distribution on trial zero">
    {ticks.map(v=><g key={v}><line className="r-grid" x1={L} x2={W-R} y1={y(v)} y2={y(v)}/><text x={L-9} y={y(v)+4} textAnchor="end">{Math.round(v*100)}%</text></g>)}
    {[0,1,5,20,100,500].filter(v=>v<=max).map(v=><text key={v} x={x(v)} y={H-B+20} textAnchor="middle">{v}s</text>)}
    {values.map((r,index)=>{const data=r.records.map(v=>v.latency_ms/1000).sort((v,w)=>v-w);let last=0;const points=[`${x(0)},${y(0)}`];data.forEach((v,i)=>{points.push(`${x(v)},${y(last)}`,`${x(v)},${y((i+1)/data.length)}`);last=(i+1)/data.length;});return <polyline key={r.system} fill="none" strokeWidth={2} className={index===0?"r-series-a":"r-series-b"} points={points.join(" ")}/>;})}
    <text className="r-axis-label" x={W/2} y={H-4} textAnchor="middle">Optimizer seconds · log₁₀(1 + seconds) · trial 0</text>
  </svg>;
}

export const outcomeKinds=[{key:"accepted",name:"Accepted",color:"var(--r-accent)"},{key:"no_change",name:"Unchanged",color:"#71747e"},
  {key:"not_faster",name:"Not faster",color:"#aeb1bb"},{key:"failure",name:"Wrong / invalid / regression",color:"var(--r-negative)"}];
export function Outcomes({rows}:{rows:ResearchSystem[]}) {
  return <div className="r-outcomes">{rows.map(r=>{const counts:Record<string,number>={};r.records.forEach(v=>{const k=outcomeKinds.some(t=>t.key===v.outcome)?v.outcome:"failure";counts[k]=(counts[k]||0)+1;});return <div className="r-outcome-row" key={r.system}>
    <span>{label(r.system)}</span><div className="r-stack" aria-label={`${r.records.length} trial-zero outcomes for ${label(r.system)}`}>{outcomeKinds.map(k=><span key={k.key} style={{width:`${(counts[k.key]||0)/Math.max(1,r.records.length)*100}%`,background:k.color}} title={`${k.name}: ${counts[k.key]||0}`} />)}</div><span className="r-number">{r.records.length}</span></div>;})}</div>;
}

export function FamilyMatrix({rows,cases}:{rows:ResearchSystem[];cases:ResearchCase[]}) {
  const families=[...new Set(cases.map(c=>c.family))].sort();
  return <div className="r-table-wrap"><table className="r-matrix"><thead><tr><th>Query family</th>{rows.map(r=><th key={r.system}>{label(r.system)}</th>)}</tr></thead><tbody>{families.map(f=><tr key={f}><td>{f.replaceAll("_"," ")}<small>{cases.filter(c=>c.family===f).length} cases</small></td>{rows.map(r=>{const v=r.accepted_by_family[f];return <td key={r.system} style={v==null?{}:{background:`rgba(126,180,236,${v*.26})`}}>{v==null?"—":percent(v)}</td>;})}</tr>)}</tbody></table></div>;
}

export function RuntimeHistogram({cases}:{cases:ResearchCase[]}) {
  const bins=Array.from({length:8},()=>0), lo=-3, hi=5;
  cases.forEach(c=>{const index=Math.min(7,Math.max(0,Math.floor(Math.log10(Math.max(.001,c.original_ms))-lo)));bins[index]++;});
  const max=Math.max(1,...bins), step=PX/8;
  return <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Distribution of original query runtimes, equal-width logarithmic bins">
    {[0,.5,1].map(v=><g key={v}><line className="r-grid" x1={L} x2={W-R} y1={T+PY*(1-v)} y2={T+PY*(1-v)}/><text x={L-8} y={T+PY*(1-v)+4} textAnchor="end">{Math.round(max*v)}</text></g>)}
    {bins.map((count,i)=><g key={i}><rect x={L+i*step+3} y={T+PY*(1-count/max)} width={step-6} height={PY*count/max} className="r-dot-a"><title>{`${10**(lo+i)}–${10**(lo+i+1)} ms: ${count} cases`}</title></rect><text x={L+i*step+step/2} y={T+PY*(1-count/max)-6} textAnchor="middle">{count||""}</text><text x={L+i*step} y={H-B+20} textAnchor="start">{10**(lo+i)>=1000?`${10**(lo+i)/1000}k`:10**(lo+i)}</text></g>)}
    <text className="r-axis-label" x={W/2} y={H-4} textAnchor="middle">Original execution time (ms) · logarithmic bins · {hi-lo} bins</text>
  </svg>;
}

export function CostBars({rows}:{rows:ResearchSystem[]}) {
  const max=Math.max(.1,...rows.map(r=>(r.cost_per_case_usd||0)*1000));
  return <div className="r-cost-bars">{rows.map(r=><div key={r.system}><span>{label(r.system)}</span><div className="r-bar-track"><i style={{width:`${(r.cost_per_case_usd||0)*1000/max*100}%`}}/></div><strong className="r-number">{money(r.cost_per_case_usd==null?null:r.cost_per_case_usd*1000)}</strong></div>)}</div>;
}
