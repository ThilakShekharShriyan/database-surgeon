"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Activity, ArrowDownToLine, ArrowUpRight, Check, ChevronRight, Database, FlaskConical,
  GitCompareArrows, Layers3, Maximize2, RefreshCw, Search, ShieldCheck, Terminal } from "lucide-react";
import type { Comparison, ResearchSnapshot, ResearchSystem } from "@/lib/research-types";
import { Acceptance, CostBars, FamilyMatrix, LatencyCDF, Outcomes, RuntimeHistogram, Tradeoff,
  label, money, outcomeKinds, percent, seconds } from "./research-charts";
import "../app/research.css";

type Tab = "overview" | "statistics" | "queries" | "method";
const sections = [{id:"overview",name:"Benchmark overview",icon:Activity},{id:"statistics",name:"Paired statistics",icon:GitCompareArrows},
  {id:"queries",name:"Query evidence",icon:Terminal},{id:"method",name:"Protocol & scope",icon:Layers3}] as const;
const primary = ["frontier-raw","open-raw","open-harness","fw-nemotron-harness","fw-fast-harness","rules-only"];
const aliases = new Set(["fw-open-harness","fw-gpt-oss-harness","cascade-open-fw","cascade-oss-fw","fw-nemotron-ultra-harness"]);
const pvalue=(v:number|null|undefined)=>v==null?"—":v<.0001?v.toExponential(2):v.toFixed(4);
const signed=(v:number, digits=2)=>`${v>0?"+":""}${v.toFixed(digits)}`;
function Panel({title,note,children,action,className=""}:{title:string;note?:string;children:ReactNode;action?:ReactNode;className?:string}) {
  return <section className={`r-panel ${className}`}><header><div><h2>{title}</h2>{note&&<p>{note}</p>}</div>{action}</header>{children}</section>;
}
function Legend({a,b}:{a:string;b:string}) {return <div className="r-legend"><span><i/>{label(a)}</span><span><i className="baseline"/>{label(b)}</span></div>;}
function download(body:string,filename:string,type:string) {const url=URL.createObjectURL(new Blob([body],{type}));const link=document.createElement("a");link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}

export function ResearchDashboard({embedded=false,initialData=null}:{embedded?:boolean;initialData?:ResearchSnapshot|null}) {
  const [data,setData]=useState<ResearchSnapshot|null>(initialData),[error,setError]=useState(""),[refreshing,setRefreshing]=useState(false);
  const [tab,setTab]=useState<Tab>("overview"),[split,setSplit]=useState<"dev"|"heldout">("dev");
  const [selected,setSelected]=useState("open-harness"),[baseline,setBaseline]=useState("frontier-raw");
  const [axis,setAxis]=useState<"cost"|"latency">("cost"),[showPartial,setShowPartial]=useState(true);
  const [search,setSearch]=useState(""),[family,setFamily]=useState("all"),[caseId,setCaseId]=useState("");
  const [presenting,setPresenting]=useState(false),[executions,setExecutions]=useState(10000),[copied,setCopied]=useState(false);
  const refresh=useCallback(async()=>{setRefreshing(true);try {
    const response=await fetch("/api/research",{cache:"no-store"});const value=await response.json();
    if(!response.ok)throw Error(value.error||"Could not load research snapshot.");
    setData(value);setError("");
  }catch(e){setError(e instanceof Error?e.message:"Could not load research snapshot.");}finally{setRefreshing(false);}},[]);
  useEffect(()=>{void refresh();},[refresh]);
  const current=data?.splits[split];
  const systems=current?.systems||[];
  const system=systems.find(r=>r.system===selected)||systems.find(r=>r.system==="rules-only")||systems[0];
  const reference=systems.find(r=>r.system===baseline);
  const comparison:Comparison|undefined=current?.comparisons[baseline]?.[system?.system||""];
  const featured=useMemo(()=>{
    const rows=systems.filter(r=>primary.includes(r.system));
    if(system&&!rows.includes(system))rows.push(system);
    return rows.filter(r=>showPartial||r.complete);
  },[systems,system,showPartial]);
  const records=system?.records||[];
  const recordMap=new Map(records.map(r=>[r.case,r]));
  const filteredCases=(current?.cases||[]).filter(c=>(family==="all"||c.family===family)&&
    `${c.id} ${c.family} ${c.sql}`.toLowerCase().includes(search.toLowerCase()));
  const chosenCase=filteredCases.find(c=>c.id===caseId)||filteredCases.find(c=>recordMap.get(c.id)?.outcome==="accepted")||filteredCases[0];
  const chosenRecord=chosenCase?recordMap.get(chosenCase.id):undefined;
  const matches=records.filter(r=>r.outcome==="accepted");
  const acceptance=comparison?.mcnemar.accepted,incorrect=comparison?.mcnemar.incorrect_returned;
  const costs=comparison?.paired_metrics.cost_usd,latency=comparison?.paired_metrics.latency_ms;
  const totalCases=data?Object.values(data.splits).reduce((sum,s)=>sum+s.expected_cases,0):0;
  const totalTemplates=data?Object.values(data.splits).reduce((sum,s)=>sum+s.templates,0):0;
  const fullSystems=systems.filter(r=>r.complete&&!aliases.has(r.system));
  function switchSplit(value:"dev"|"heldout") {setSplit(value);setCaseId("");setFamily("all");setSearch("");}
  function exportCSV() {
    const keys=["system","cases","expected_cases","trials","complete","accepted_rate","incorrect_returned_count","cost_per_case_usd","latency_p50_ms","latency_p95_ms","calls_per_case"] as const;
    download([keys.join(","),...systems.map(r=>keys.map(k=>JSON.stringify(r[k]??"")).join(","))].join("\n"),`surgeon-${split}-systems.csv`,"text/csv");
  }
  const reportCommand=`.venv/bin/python -m surgeon.eval report --split ${split} --baseline ${baseline} --comparison-trial 0`;
  const savePerExecution=chosenRecord?.outcome==="accepted" && chosenRecord.verdict?.original_ms!=null && chosenRecord.verdict.candidate_ms!=null
    ?chosenRecord.verdict.original_ms-chosenRecord.verdict.candidate_ms:null;
  const breakeven=savePerExecution!=null&&savePerExecution>0?Math.ceil((chosenRecord?.latency_ms||0)/savePerExecution):null;

  return <div className={`research ${presenting?"r-presenting":""} ${embedded?"r-embedded":""}`}>
    {!embedded&&<aside className="r-rail" aria-label="Research navigation"><a href="/" className="r-mark" aria-label="Database Surgeon research"><Database size={23}/></a>
      <nav>{sections.map(item=><button key={item.id} className={tab===item.id?"active":""} onClick={()=>setTab(item.id)} aria-label={item.name} title={item.name}><item.icon size={19}/><span>{item.id==="overview"?"Results":item.name.split(" ")[0]}</span></button>)}</nav>
      <a className="r-rail-demo" href="/demo" title="Open live demo" aria-label="Open live demo"><FlaskConical size={19}/><span>Demo</span></a>
      <span className="r-rail-bottom">PG16</span>
    </aside>}
    <div className="r-workspace">
      <header className="r-topbar"><a href="/" className="r-brand">Database Surgeon <span>/</span><b>Research observatory</b></a><div><a href="/demo">Live demo <ArrowUpRight size={13}/></a><a href="/lab">Workbench <ArrowUpRight size={13}/></a><button onClick={()=>setPresenting(v=>!v)} aria-pressed={presenting} title="Toggle presentation view"><Maximize2 size={15}/><span>{presenting?"Exit presentation":"Present"}</span></button></div></header>
      <main className="r-main">
        <div className="r-title"><div><div className="r-breadcrumb">Research <ChevronRight size={12}/>{sections.find(t=>t.id===tab)?.name}</div><h1>{tab==="overview"?"The evidence, in full.":tab==="statistics"?"Every comparison is paired.":tab==="queries"?"Follow the query.":"What the experiment measures."}</h1><p>{tab==="overview"?"PostgreSQL rewrites measured across quality, correctness, cost and optimizer time.":tab==="statistics"?"Discordant outcomes, effect sizes and uncertainty on the same cases.":tab==="queries"?"Inspect original SQL, the returned rewrite and the evaluator’s verdict.":"A fixed workload, explicit contracts and limitations beside every claim."}</p></div>
          <div className="r-title-actions"><button className="r-button" onClick={exportCSV} disabled={!data}><ArrowDownToLine size={14}/>Export CSV</button><button className="r-button" onClick={()=>void refresh()} disabled={refreshing} aria-label="Refresh research snapshot"><RefreshCw size={14} className={refreshing?"r-spinning":""}/>{refreshing?"Loading":"Refresh"}</button></div></div>
        <div className="r-tabs" role="tablist" aria-label="Research sections">{sections.map(item=><button key={item.id} role="tab" aria-selected={tab===item.id} onClick={()=>setTab(item.id)}>{item.name}</button>)}</div>
        {error&&<div className="r-error" role="alert">{error}<button onClick={()=>void refresh()}>Try again</button></div>}
        {!data&&!error&&<div className="r-loading" role="status"><Activity size={20}/>Loading saved benchmark evidence…</div>}
        {data&&current&&system&&<>
          <div className="r-controls"><div className="r-split"><button className={split==="dev"?"active":""} onClick={()=>switchSplit("dev")}>Development <span>{data.splits.dev.expected_cases}</span></button><button className={split==="heldout"?"active":""} onClick={()=>switchSplit("heldout")}>Held-out <span>{data.splits.heldout.expected_cases}</span></button></div>
            <label>System<select aria-label="Research system" value={system.system} onChange={e=>{setSelected(e.target.value);setCaseId("");}}>{systems.filter(r=>!aliases.has(r.system)).map(r=><option key={r.system} value={r.system}>{label(r.system)}{r.complete?"":" · partial"}</option>)}</select></label>
            <label>Compare with<select aria-label="Research baseline" value={baseline} onChange={e=>setBaseline(e.target.value)}><option value="frontier-raw">Frontier · raw</option><option value="open-raw" disabled={!systems.some(r=>r.system==="open-raw")}>Open · raw</option></select></label></div>
          <div className="r-snapshot-note"><span className="r-status-dot"/><span>Saved evidence · {new Date(data.generated_at).toLocaleString("en-US",{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit",hour12:false,timeZone:"UTC"})} UTC · read-only · no inference calls</span><span>{split==="dev"?"Development · exploratory":"Held-out coverage is incomplete"}</span></div>
          {tab==="overview"&&<>
            <div className="r-kpis">
              <div><span>Accepted beneficial rewrites</span><strong>{percent(system.accepted_rate)}</strong><small>{system.cases}/{current.expected_cases} cases · {system.trials} trial{system.trials!==1?"s":""}{!system.complete?" · partial":""}</small></div>
              <div><span>Incorrect returned</span><strong className={system.incorrect_returned_count?"r-negative":""}>{system.incorrect_returned_count}</strong><small>{system.wrong_candidates_caught} failed checks recorded internally</small></div>
              <div><span>API cost / 1,000 optimizations</span><strong>{money(system.cost_per_case_usd==null?null:system.cost_per_case_usd*1000)}</strong><small>Configured token rates · DB compute excluded</small></div>
              <div><span>Optimizer latency · p50 / p95</span><strong>{(system.latency_p50_ms/1000).toFixed(2)}<em>s</em><i>/</i>{(system.latency_p95_ms/1000).toFixed(2)}<em>s</em></strong><small>Recorded service time · queue/throttle excluded</small></div>
            </div>
            <div className="r-finding"><GitCompareArrows size={17}/><p><strong>{label(system.system)} vs {label(baseline)}.</strong> {comparison?.pairs?`${comparison.pairs} paired cases in trial 0. Acceptance McNemar p = ${pvalue(acceptance?.p_value)}. Mean cost ${costs?.ratio_of_means_a_over_baseline?.toFixed(2)??"—"}×; mean optimizer latency ${latency?.ratio_of_means_a_over_baseline?.toFixed(2)??"—"}× the baseline.`:"No matched comparison available for this split."}</p><button onClick={()=>setTab("statistics")}>Inspect test <ArrowUpRight size={14}/></button></div>
            <div className="r-chart-grid">
              <Panel title="The quality–efficiency tradeoff" note="Each point is a system. Select a point to inspect it." action={<div className="r-segment"><button aria-pressed={axis==="cost"} onClick={()=>setAxis("cost")}>Cost</button><button aria-pressed={axis==="latency"} onClick={()=>setAxis("latency")}>Latency</button></div>}>
                <div className="r-svg-scroll"><Tradeoff rows={featured} selected={system.system} baseline={baseline} axis={axis} onSelect={setSelected}/></div><div className="r-chart-foot"><Legend a={system.system} b={baseline}/><span>Dashed mark = incomplete · red = incorrect observed</span></div>
              </Panel>
              <Panel title="Beneficial rewrite coverage" note="Descriptive 95% case-bootstrap intervals; related templates limit inference.">
                <div className="r-svg-scroll"><Acceptance rows={featured} selected={system.system}/></div><div className="r-chart-foot"><label className="r-checkbox"><input type="checkbox" checked={showPartial} onChange={e=>setShowPartial(e.target.checked)}/>Include partial runs in charts</label><span>Full-denominator claims require complete runs</span></div>
              </Panel>
              <Panel title="Time to optimize a query" note="Empirical cumulative distribution · a line further left is faster."><div className="r-svg-scroll"><LatencyCDF a={system} b={reference}/></div><Legend a={system.system} b={baseline}/></Panel>
              <Panel title="What happened to the SQL?" note="Trial 0 · every observed query belongs to exactly one segment."><Outcomes rows={featured}/><div className="r-legend r-wrap">{outcomeKinds.map(k=><span key={k.key}><i style={{background:k.color}}/>{k.name}</span>)}</div></Panel>
              <Panel title="Model spend at workload scale" note="USD per 1,000 optimization requests · all recorded trials."><CostBars rows={featured}/><p className="r-caption">Zero means no API charge. Local hardware, energy and database validation are additional.</p></Panel>
              <Panel title="The benchmark’s runtime scale" note="Original SQL on synthetic fixtures · build-time execution measurements."><div className="r-svg-scroll"><RuntimeHistogram cases={current.cases}/></div><p className="r-caption">{current.cases.filter(c=>c.original_ms<10).length}/{current.expected_cases} originals take under 10 ms. Repeated execution matters to the business case.</p></Panel>
            </div>
            <Panel title="Where each system succeeds" note="Acceptance by family · descriptive averages across available trials. Zero is distinct from missing." className="r-wide"><FamilyMatrix rows={featured.slice(0,6)} cases={current.cases}/></Panel>
            <Panel title="The complete experiment ledger" note="All recorded systems, including aliases and unfinished runs. Select a row for its evidence." className="r-wide">
              <div className="r-table-wrap"><table><thead><tr><th>System / coverage</th><th>Accepted</th><th>Wrong</th><th>API $ / 1k</th><th>p50</th><th>p95</th><th>Calls / case</th><th>Trials</th></tr></thead><tbody>{[...systems].sort((a,b)=>b.accepted_rate-a.accepted_rate).map(r=><tr key={r.system} className={r.system===system.system?"r-current":""}><td><button className="r-table-link" onClick={()=>setSelected(r.system)}>{label(r.system)}</button><small>{r.system} · {r.cases}/{current.expected_cases}{r.complete?" · complete":" · partial"}{r.simulated?" · replay simulation":""}</small></td><td>{percent(r.accepted_rate)}</td><td className={r.incorrect_returned_count?"r-negative":""}>{r.incorrect_returned_count}</td><td>{money(r.cost_per_case_usd==null?null:r.cost_per_case_usd*1000)}</td><td>{seconds(r.latency_p50_ms)}</td><td>{seconds(r.latency_p95_ms)}</td><td>{r.calls_per_case.toFixed(1)}</td><td>{r.trials}</td></tr>)}</tbody></table></div>
            </Panel>
          </>}
          {tab==="statistics"&&<>
            <div className="r-method-banner"><ShieldCheck size={18}/><div><strong>One declared trial. Matched cases. Explicit uncertainty.</strong><p>Primary comparison uses trial 0. P-values are two-sided and unadjusted; development findings are exploratory. Non-significance does not establish equivalence or noninferiority.</p></div></div>
            {!comparison?.pairs?<div className="r-empty">No matched trial-zero records for these systems. Select another split or comparator.</div>:<>
              <div className="r-kpis r-stats-kpis"><div><span>Matched cases</span><strong>{comparison.pairs}<em> / {current.expected_cases}</em></strong><small>{comparison.complete?"Complete matched trial":"Shared subset only · not full coverage"}</small></div><div><span>Acceptance difference</span><strong>{signed((acceptance?.rate_difference_a_minus_baseline||0)*100,1)}<em> pp</em></strong><small>A minus baseline · trial 0</small></div><div><span>Acceptance McNemar</span><strong>p = {pvalue(acceptance?.p_value)}</strong><small>Exact binomial · discordant pairs only</small></div><div><span>Incorrect-return McNemar</span><strong>p = {pvalue(incorrect?.p_value)}</strong><small>Observed incorrect outputs · lower is better</small></div></div>
              <div className="r-chart-grid">
                <Panel title="The paired outcome table" note={`A = ${label(system.system)} · B = ${label(baseline)}`}>
                  <div className="r-contingency"><div/><div>B not accepted</div><div>B accepted</div><div>A not accepted</div><strong>{acceptance?.table[0][0]}</strong><strong className="r-discordant">{acceptance?.table[0][1]}<small>Baseline alone</small></strong><div>A accepted</div><strong className="r-discordant">{acceptance?.table[1][0]}<small>A alone</small></strong><strong>{acceptance?.table[1][1]}</strong></div>
                  <p className="r-caption">Only the off-diagonal cells enter McNemar’s exact test. Concordant outcomes contribute to coverage, not the test statistic.</p>
                </Panel>
                <Panel title="Check dependence between variants" note="Template-level sensitivity analysis · complete matched template groups only.">
                  <div className="r-test-list"><div><span>Template acceptance test</span><strong>p = {pvalue(acceptance?.template_sensitivity?.p_value)}</strong></div><div><span>Independent template groups assumed</span><strong>{acceptance?.template_sensitivity?.pairs??"—"}</strong></div><div><span>A alone / baseline alone</span><strong>{acceptance?.template_sensitivity?.a_only??"—"} / {acceptance?.template_sensitivity?.baseline_only??"—"}</strong></div><div><span>Template incorrect-return test</span><strong>p = {pvalue(incorrect?.template_sensitivity?.p_value)}</strong></div></div><p className="r-caption">A template is accepted only when all its instances are accepted. Any incorrect instance marks a template incorrect. This changes the estimand; it is a sensitivity check.</p>
                </Panel>
              </div>
              <Panel title="Effect sizes beyond acceptance" note="Paired means on identical cases · differences are A minus baseline · 95% intervals resample whole templates.">
                <div className="r-table-wrap"><table><thead><tr><th>Measurement</th><th>A mean</th><th>Baseline mean</th><th>Difference</th><th>95% interval</th><th>A / baseline</th><th>Pairs</th></tr></thead><tbody>{Object.entries(comparison.paired_metrics).map(([key,m])=>{
                  const format=(v:number|null)=>v==null?"—":key==="cost_usd"?money(v*1000):key.endsWith("_ms")?seconds(v):v.toFixed(2);
                  const range=m.difference_ci95_template_bootstrap;return <tr key={key}><td>{({cost_usd:"API USD / 1,000",latency_ms:"Optimizer latency",llm_ms:"Model time",verify_ms:"Verification time",calls:"Inference calls",output_tokens:"Output tokens",speedup:"SQL speedup (conditional)"} as Record<string,string>)[key]}<small>{m.lower_is_better?"Lower is better":"Higher is better"}</small></td><td>{format(m.mean_a)}</td><td>{format(m.mean_baseline)}</td><td>{format(m.mean_difference)}</td><td>{range?`${format(range[0])} to ${format(range[1])}`:"—"}</td><td>{m.ratio_of_means_a_over_baseline?.toFixed(2)??"—"}×</td><td>{m.pairs}{m.excluded_pairs?` (${m.excluded_pairs} omitted)`:""}</td></tr>;})}</tbody></table></div>
                <p className="r-caption">SQL speedup omits wrong/invalid outputs; it is not workload savings. Latency excludes throttle and lock queueing. Intervals describe template variation in one trial, not fresh timing uncertainty.</p>
              </Panel>
              <Panel title="Interpretation & reproducibility" note="The limits are part of the result."><ul className="r-limit-list">{comparison.warnings.map(w=><li key={w}>{w}</li>)}</ul><div className="r-command"><code>{reportCommand}</code><button aria-label="Copy reproduction command" onClick={()=>{void navigator.clipboard.writeText(reportCommand).then(()=>{setCopied(true);setTimeout(()=>setCopied(false),1500);});}}>{copied?<Check size={15}/>:"Copy"}</button></div></Panel>
            </>}
          </>}
          {tab==="queries"&&<>
            <div className="r-query-controls"><label className="r-search"><Search size={16}/><input aria-label="Search query evidence" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search SQL, case or family…"/></label><label>Family<select aria-label="Query family" value={family} onChange={e=>setFamily(e.target.value)}><option value="all">All query families</option>{[...new Set(current.cases.map(c=>c.family))].sort().map(f=><option key={f}>{f}</option>)}</select></label><span>{filteredCases.length} matching cases</span></div>
            <div className="r-query-layout"><section className="r-query-list" aria-label="Query cases">{filteredCases.map(c=>{const r=recordMap.get(c.id);return <button key={c.id} className={chosenCase?.id===c.id?"active":""} onClick={()=>setCaseId(c.id)}><strong>{c.id.replaceAll("_"," ")}</strong><span>{c.family.replaceAll("_"," ")}<i className={r?.outcome==="incorrect"?"r-negative":""}>{r?.outcome?.replaceAll("_"," ")||"not run"}</i></span></button>;})}{!filteredCases.length&&<p className="r-empty">No queries match these filters.</p>}</section>
              <div>{chosenCase&&<>
                <div className="r-query-heading"><div><small>{chosenCase.template}</small><h2>{chosenCase.id}</h2></div><span className={chosenRecord?.outcome==="incorrect"?"r-negative":""}>{chosenRecord?.outcome.replaceAll("_"," ")||"Not evaluated"}</span></div>
                <div className="r-sql-grid"><Panel title="Original SQL" note={chosenCase.source||"Own synthetic input"}><pre><code>{chosenCase.sql}</code></pre></Panel><Panel title="Returned SQL" note={label(system.system)}><pre><code>{chosenRecord?.result_sql||"No recorded output for this query."}</code></pre></Panel></div>
                <div className="r-query-metrics"><div><span>Original runtime</span><strong>{chosenRecord?.verdict?.original_ms?.toFixed(3)??chosenCase.original_ms.toFixed(3)} ms</strong></div><div><span>Candidate runtime</span><strong>{chosenRecord?.verdict?.candidate_ms?.toFixed(3)??"—"} ms</strong></div><div><span>SQL speedup</span><strong>{chosenRecord?.speedup?.toFixed(2)??"—"}×</strong></div><div><span>Optimizer time</span><strong>{chosenRecord?seconds(chosenRecord.latency_ms):"—"}</strong></div></div>
                {chosenRecord?.verdict?.counterexample!=null&&<Panel title="The counterexample" note={`Evaluator fixture: ${chosenRecord.verdict.schema||"recorded fixture"}`}><pre className="r-counterexample">{JSON.stringify(chosenRecord.verdict.counterexample,null,2)}</pre><p className="r-caption">{chosenRecord.verdict.reason}</p></Panel>}
                <Panel title="When does this rewrite pay back?" note="An elapsed-time illustration for this one accepted query, not a dollar or CPU savings estimate.">
                  {breakeven==null?<p className="r-empty">Select an accepted query with measured original and candidate times to calculate payback.</p>:<><label className="r-range">Executions after optimization <strong>{executions.toLocaleString()}</strong><input aria-label="Execution count" type="range" min={100} max={100000} step={100} value={executions} onChange={e=>setExecutions(Number(e.target.value))}/></label><div className="r-payback"><div><span>Break-even executions</span><strong>{breakeven.toLocaleString()}</strong></div><div><span>Execution time saved</span><strong>{((savePerExecution||0)*executions/1000).toFixed(2)} s</strong></div><div><span>Net of optimizer time</span><strong>{signed(((savePerExecution||0)*executions-(chosenRecord?.latency_ms||0))/1000)} s</strong></div></div><p className="r-caption">Assumes the measured speedup persists and optimization occurs once. Queueing, throttling, validation compute cost and drift are excluded.</p></>}
                </Panel>
              </>}</div></div>
          </>}
          {tab==="method"&&<>
            <div className="r-kpis"><div><span>Frozen SQL cases</span><strong>{totalCases}</strong><small>Development + held-out</small></div><div><span>Template IDs</span><strong>{totalTemplates}</strong><small>Parameter variants grouped</small></div><div><span>Correctness fixtures</span><strong>5 <i>+</i> 3</strong><small>System-visible + evaluator-only</small></div><div><span>Acceptance threshold</span><strong>≥20<em>%</em></strong><small>Median execution-time reduction</small></div></div>
            <Panel title="The surgical protocol" note="Candidate generation is separate from the benchmark judge."><div className="r-pipeline">{[{n:"01",title:"Context",body:"SQL, declared schema, indexes and EXPLAIN."},{n:"02",title:"Propose",body:"Rules, retrieval and bounded model sampling."},{n:"03",title:"Verify",body:"Five fixtures; preserve types, bags, NULLs and duplicates."},{n:"04",title:"Measure",body:"Paired warm timing; accept a ≥20% reduction."},{n:"05",title:"Evaluate",body:"Eight fixtures, including three extra; five timing pairs."}].map(s=><div key={s.n}><span>{s.n}</span><h3>{s.title}</h3><p>{s.body}</p></div>)}</div></Panel>
            <div className="r-chart-grid"><Panel title="Split coverage" note="A split existing does not mean all systems have completed it."><div className="r-test-list">{Object.entries(data.splits).map(([name,s])=><div key={name}><span>{name==="dev"?"Development":"Held-out"} · {s.expected_cases} cases · {s.templates} templates</span><strong>{s.systems.filter(r=>r.complete&&!aliases.has(r.system)).length} complete systems</strong></div>)}<div><span>Selected split · accepted rewrites</span><strong>{matches.length} in trial 0</strong></div><div><span>Selected split · complete systems (aliases excluded)</span><strong>{fullSystems.length}</strong></div></div></Panel>
              <Panel title="What is being compared?" note="Separate model effects from the additional inference and verification budget."><div className="r-test-list"><div><span>Raw systems</span><strong>1 model sample + EXPLAIN</strong></div><div><span>Full harness</span><strong>Up to 3 × 3 samples</strong></div><div><span>System-side timing</span><strong>3 paired trials</strong></div><div><span>Evaluator timing</span><strong>5 paired trials</strong></div></div><p className="r-caption">Rules can return before a model call. A same-harness frontier comparison and matched budgets are needed to isolate model advantage.</p></Panel></div>
            <Panel title="Limits that change the interpretation" note="These are development microbenchmarks on PostgreSQL 16."><div className="r-limit-grid"><div><h3>Finite checks, not a proof</h3><p>Eight fixture databases cannot establish equivalence for arbitrary future data. Missing foreign-key relationships have already exposed incorrect rewrites that passed system-side checks.</p></div><div><h3>Microfixtures, not warehouses</h3><p>Many originals finish in milliseconds. Scale, skew, concurrency, cache state and traffic frequency can change performance and return on optimization.</p></div><div><h3>Training overlap</h3><p>Specialist exports include exact development examples. Future specialist development scores do not demonstrate unseen-query generalization.</p></div><div><h3>Experiment identity</h3><p>Existing cache and resume keys do not fully pin code, database contents or workload-cache state. Snapshot comparisons disclose these limits.</p></div></div></Panel>
            <Panel title="Reproduce and inspect" note="The research frontend reads saved traces and never starts inference."><div className="r-command"><code>.venv/bin/python scripts/export_research.py</code></div><div className="r-command"><code>{reportCommand}</code></div><div className="r-provenance"><span>Input SHA-256</span><code>{current.cases_sha256}</code><span>Source</span><code>{data.source}</code></div><button className="r-button" onClick={()=>download(JSON.stringify(data,null,2),"database-surgeon-research.json","application/json")}><ArrowDownToLine size={14}/>Download research snapshot</button></Panel>
          </>}
          <footer className="r-footer"><span><Database size={13}/>PostgreSQL 16 · synthetic microfixtures · {split==="dev"?"exploratory development evidence":"held-out run coverage incomplete"}</span><span>Snapshot {current.cases_sha256.slice(0,12)} <a href="/demo">Open demo <ArrowUpRight size={12}/></a></span></footer>
        </>}
      </main>
    </div>
  </div>;
}
