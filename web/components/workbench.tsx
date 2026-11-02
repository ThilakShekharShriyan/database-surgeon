"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, ArrowDown, ArrowRight, ArrowUpRight, Check, ChevronDown, ChevronRight, Clock3, Code2, Copy, Database, FlaskConical, GitBranch, Layers3, Play, RefreshCw, Send, ShieldCheck, Sparkles, Square, Terminal, X } from "lucide-react";
import { useAgent, useAgentContext, useCopilotKit, useFrontendTool } from "@copilotkit/react-core/v2";
import { z } from "zod";
import type { Attempt, CaseResult, Run, Snapshot } from "@/lib/types";
import { SurgeryDemo } from "@/components/surgery-demo";
import { FrontierView } from "@/components/frontier";

const names: Record<string,string> = {date_filter:"Date filter",correlated_count:"Correlated count",nullable_antijoin:"NULL-sensitive anti-join",month_range:"Month range",distinct_customer:"Distinct customers",count_nonnull:"Non-null count",repeated_sum:"Repeated aggregate",already_indexed:"Already indexed",tpch_q17_0:"TPC-H Q17 · variant 0",tpch_q17_1:"TPC-H Q17 · variant 1",calcite_union:"Calcite · union filter",calcite_empty_minus:"Calcite · empty EXCEPT",calcite_exists:"Calcite · two EXISTS",calcite_not_in:"Calcite · correlated NOT IN"};
const title = (id:string) => names[id] || id.replaceAll("_"," ");
const shortModel = (name:string) => name?.replace("openai/","").replace("accounts/fireworks/models/","") || "Mock fixture";
const number = (value:number|undefined, digits=2) => value === undefined ? "—" : value.toLocaleString("en-US",{minimumFractionDigits:digits,maximumFractionDigits:digits});
const stateLabel = (state:string) => ({accepted:"Accepted",not_faster:"No benefit",incorrect:"Incorrect",no_change:"Kept original",duplicate:"Duplicate",generating:"Generating",evaluating:"Verifying",error:"Error",not_attempted:"Not run"}[state] || state);
const chosenAttempt = (c?:CaseResult) => c?.attempts.find(a=>a.status==="accepted") || c?.attempts.at(-1);
const caseStatus = (c:CaseResult) => chosenAttempt(c)?.status || "pending";

function Mark(){return <svg viewBox="0 0 32 32" width="29" height="29" aria-hidden="true"><path d="M5 9c0-3 22-3 22 0v14c0 4-22 4-22 0V9Zm0 0c0 4 22 4 22 0M5 16c0 3 11 4 16 2" fill="none" stroke="currentColor" strokeWidth="1.5"/><path d="m15 26 11-13 3 3-11 13-4 1Z" fill="var(--ground)" stroke="currentColor" strokeWidth="1.5"/></svg>}

function SQL({sql}:{sql:string}) {
  const keywords=/^(SELECT|FROM|WHERE|AND|OR|NOT|IN|EXISTS|AS|JOIN|LEFT|RIGHT|INNER|OUTER|ON|GROUP|BY|HAVING|WITH|IS|NULL|DISTINCT|CASE|WHEN|THEN|ELSE|END|UNION|ALL|EXCEPT|LIMIT|TIMESTAMP|DATE|TRUE|FALSE)$/i;
  const parts=sql.split(/('(?:''|[^'])*'|\b(?:SELECT|FROM|WHERE|AND|OR|NOT|IN|EXISTS|AS|JOIN|LEFT|RIGHT|INNER|OUTER|ON|GROUP|BY|HAVING|WITH|IS|NULL|DISTINCT|CASE|WHEN|THEN|ELSE|END|UNION|ALL|EXCEPT|LIMIT|TIMESTAMP|DATE|TRUE|FALSE)\b)/gi);
  return <code>{parts.map((part,i)=><span key={i} className={keywords.test(part)?"sql-keyword":part.startsWith("'")?"sql-string":""}>{part}</span>)}</code>;
}

function RuntimePlot({record}:{record?:CaseResult}) {
  const benchmark=chosenAttempt(record)?.benchmark;
  if(!benchmark) return <div className="plot-empty"><span>No paired timing for this candidate</span><p>Only correct, changed SQL advances to measurement.</p></div>;
  const max=Math.max(benchmark.original_ms,benchmark.candidate_ms)*1.2;
  return <div className="runtime-plot" role="img" aria-label={"Original "+benchmark.original_ms+" milliseconds, candidate "+benchmark.candidate_ms+" milliseconds"}>
    <div className="plot-scale"><span>Execution time</span><span>{number(max)} ms</span></div>
    {[["Original",benchmark.original_ms],["Candidate",benchmark.candidate_ms]].map(([label,value])=><div className="runtime-row" key={label as string}><span>{label}</span><div className="runtime-track"><div className={label==="Candidate"?"candidate-bar":"original-bar"} style={{width:Math.max(.7,(value as number)/max*100)+"%"}}/></div><strong>{number(value as number,3)}<small>ms</small></strong></div>)}
    <div className="plot-ticks"><span>0</span><span>{number(max/2)}</span><span>{number(max)}</span></div>
  </div>;
}

function CopilotPanel({snapshot,run,onSelect,onClose}:{snapshot:Snapshot|null;run?:Run;onSelect:(id:string)=>void;onClose:()=>void}) {
  const {agent,isReady}=useAgent();
  const {copilotkit}=useCopilotKit();
  const [text,setText]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [messages,setMessages]=useState(agent.messages.slice());
  const [evidence,setEvidence]=useState<CaseResult|null>(null);
  useEffect(()=>{setMessages(agent.messages.slice());const subscription=agent.subscribe({onMessagesChanged:()=>{setMessages(agent.messages.slice());}});return ()=>subscription.unsubscribe();},[agent]);
  useAgentContext({description:"Current Database Surgeon development evaluation scope",value:{run_id:run?.manifest.run_id??null,model:run?.manifest.requested_model??null,cases:run?.summary.cases??null,accepted:run?.summary.accepted??null,data_scope:snapshot?.dataset.note??null}});
  useFrontendTool({
    name:"read_evidence",description:"Read current real experiment evidence before answering questions about performance. Costs can be unknown. All runs use development data.",
    parameters:z.object({}),
    handler:async()=>JSON.stringify({run:run?{run_id:run.manifest.run_id,model:run.manifest.requested_model,suite:run.manifest.suite,max_attempts:run.manifest.max_attempts}:null,summary:run?.summary,cases:run?.cases.map(c=>{const a=chosenAttempt(c);return {id:c.case_id,status:caseStatus(c),benchmark:a?.benchmark?{original_ms:a.benchmark.original_ms,candidate_ms:a.benchmark.candidate_ms,speedup:a.benchmark.speedup}:null,correctness:a?.correctness};}),dataset:snapshot?.dataset.note})
  },[run,snapshot?.dataset.note]);
  useFrontendTool({
    name:"show_query",description:"Open a query in the workbench and display its actual SQL, verification and timing evidence.",
    parameters:z.object({case_id:z.string().describe("The exact case ID from read_evidence")}),
    handler:async({case_id})=>{const found=run?.cases.find(c=>c.case_id===case_id);if(!found)return JSON.stringify({error:"No measured case with that ID in this run."});onSelect(case_id);setEvidence(found);return JSON.stringify(found);},
    render:({args,status})=><div className="tool-card"><ShieldCheck size={16}/><span>{status==="complete"?"Evidence loaded":"Loading evidence"} · {args.case_id}</span></div>
  },[run,onSelect]);
  async function submit(prompt?:string) {
    const message=(prompt||text).trim(); if(!message||busy||!isReady)return;
    setText("");setError("");setBusy(true);
    try {agent.addMessage({id:crypto.randomUUID(),role:"user",content:message});await copilotkit.runAgent({agent});}
    catch(err){setError(err instanceof Error?err.message:"The assistant request failed.");}finally{setBusy(false);}
  }
  return <aside className="copilot-panel" aria-label="Research copilot">
    <header><div><Sparkles size={17}/><strong>Research copilot</strong></div><button className="icon-button" onClick={onClose} aria-label="Close copilot"><X size={18}/></button></header>
    <div className="copilot-caption">Groq GPT-OSS 20B · CopilotKit built-in agent</div>
    <div className="chat-messages" aria-live="polite">
      {messages.filter(m=>m.role==="user"||m.role==="assistant").length===0&&<div className="chat-welcome"><div className="chat-symbol"><Mark/></div><h2>Ask the evidence.</h2><p>Inspect a rewrite, understand a rejection, or find the next experiment.</p><button onClick={()=>submit("Read the current evidence and open an accepted query using show_query. Explain its measured improvement and limitations.")}>Inspect an accepted rewrite <ArrowUpRight size={15}/></button><button onClick={()=>submit("Read the current evidence. What are the most important limitations of this experiment?")}>What should we test next? <ArrowUpRight size={15}/></button></div>}
      {messages.filter(m=>m.role==="user"||m.role==="assistant").map(m=><div className={"chat-message "+m.role} key={m.id}><span>{m.role==="user"?"You":"Surgeon"}</span><p>{typeof m.content==="string"?m.content:""}</p></div>)}
      {evidence&&<div className="tool-card evidence-card"><ShieldCheck size={17}/><div><strong>{title(evidence.case_id)}</strong><p>{stateLabel(caseStatus(evidence))} · {chosenAttempt(evidence)?.benchmark?number(chosenAttempt(evidence)?.benchmark?.speedup??undefined,1)+"× measured speedup":"No accepted timing claim"}</p></div></div>}
      {busy&&<p className="muted">Reading experiment evidence…</p>}
      {error&&<p className="error-message" role="alert">{error}</p>}
    </div>
    <form className="chat-compose" onSubmit={e=>{e.preventDefault();void submit();}}><label className="sr-only" htmlFor="copilot-input">Ask the research copilot</label><textarea id="copilot-input" value={text} onChange={e=>setText(e.target.value)} placeholder="Why was this rewrite rejected?" onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();void submit();}}}/><button disabled={!text.trim()||!isReady||busy} aria-label="Send message"><Send size={17}/></button></form>
    <div className="chat-footnote">Messages use the API. Tools inspect data; they cannot execute SQL.</div>
  </aside>;
}

function Lab({onOpenDemo}:{onOpenDemo:()=>void}) {
  const [snapshot,setSnapshot]=useState<Snapshot|null>(null);
  const [error,setError]=useState("");
  const [view,setView]=useState<"workbench"|"experiments"|"datasets"|"frontier">("workbench");
  const [selectedRun,setSelectedRun]=useState("");
  const [selectedCase,setSelectedCase]=useState("");
  const [search,setSearch]=useState("");
  const [chat,setChat]=useState(false);
  const [modal,setModal]=useState(false);
  const [model,setModel]=useState("groq:openai/gpt-oss-20b");
  const [suite,setSuite]=useState("all");
  const [attempts,setAttempts]=useState(1);
  const [launching,setLaunching]=useState(false);
  const [copied,setCopied]=useState("");
  const refresh=useCallback(async()=>{
    try {const response=await fetch("/api/snapshot",{cache:"no-store"});const data=await response.json();if(!response.ok)throw Error(data.error);setSnapshot(data);setError("");}
    catch(err){setError(err instanceof Error?err.message:"Could not load experiment data.");}
  },[]);
  useEffect(()=>{void refresh();const timer=setInterval(()=>void refresh(),3500);return()=>clearInterval(timer);},[refresh]);
  const runs=snapshot?.runs||[];
  const run=runs.find(r=>r.manifest.run_id===selectedRun)||runs.find(r=>!r.manifest.mock&&r.manifest.state==="completed")||runs[0];
  const cases=run?.cases||[];
  const record=cases.find(c=>c.case_id===selectedCase)||cases.find(c=>c.accepted)||cases[0];
  const attempt=chosenAttempt(record);
  const comparison=runs.filter(r=>!r.manifest.mock&&r.manifest.state==="completed"&&r.manifest.workload_sha256===run?.manifest.workload_sha256&&r.manifest.evaluator_sha256===run?.manifest.evaluator_sha256&&r.manifest.max_attempts===run?.manifest.max_attempts&&r.manifest.max_output_tokens===run?.manifest.max_output_tokens&&r.manifest.repeats===run?.manifest.repeats&&!!r.manifest.database&&JSON.stringify(r.manifest.database)===JSON.stringify(run?.manifest.database));
  const byModel=[...new Map(comparison.map(r=>[r.manifest.requested_model,r] as const).reverse()).values()];
  const activeJob=snapshot?.jobs.find(j=>j.state==="queued"||j.state==="running");
  const status=attempt?.status||"pending";
  const benchmark=attempt?.benchmark;
  const totalTokens=(run?.summary.input_tokens||0)+(run?.summary.output_tokens||0);
  const filtered=cases.filter(c=>(title(c.case_id)+" "+c.family).toLowerCase().includes(search.toLowerCase()));
  const selectQuery=useCallback((id:string)=>{setSelectedCase(id);setView("workbench");},[]);
  const familyCount=new Set(snapshot?.dataset.cases.map(c=>c.family)).size;
  async function copy(sql:string,id:string){await navigator.clipboard.writeText(sql);setCopied(id);setTimeout(()=>setCopied(""),1800);}
  async function launch(){
    setLaunching(true);setError("");
    try {const colon=model.indexOf(":");const provider=model.slice(0,colon);const modelId=model.slice(colon+1);const response=await fetch("/api/runs",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({provider,model:modelId,suite,attempts})});const data=await response.json();if(!response.ok)throw Error(data.error);setModal(false);await refresh();}
    catch(err){setError(err instanceof Error?err.message:"Could not start evaluation.");}finally{setLaunching(false);}
  }
  return <div className={"app-shell "+(chat?"with-copilot":"")}>
    <nav className="icon-rail" aria-label="Main navigation"><a className="brand-mark" href="/" aria-label="Database Surgeon home"><Mark/></a><div className="rail-links">
      <button title="Workbench" aria-label="Workbench" className={view==="workbench"?"selected":""} onClick={()=>setView("workbench")}><Terminal/><span>Lab</span></button>
      <button title="Experiments" aria-label="Experiments" className={view==="experiments"?"selected":""} onClick={()=>setView("experiments")}><Activity/><span>Runs</span></button>
      <button title="Frontier" aria-label="Frontier" className={view==="frontier"?"selected":""} onClick={()=>setView("frontier")}><Sparkles/><span>Frontier</span></button>
      <button title="Datasets" aria-label="Datasets" className={view==="datasets"?"selected":""} onClick={()=>setView("datasets")}><Database/><span>Data</span></button>
    </div><button title="Research copilot" aria-label="Research copilot" className={"rail-copilot "+(chat?"selected":"")} onClick={()=>setChat(v=>!v)}><Sparkles/><span>Copilot</span></button><div className="rail-bottom"><span className="online-dot"/><span className="sr-only">Local workspace</span></div></nav>
    <div className="workspace">
      <header className="topbar"><div className="brand-name">Database Surgeon <span className="slash">/</span><span className="workspace-name">Local lab</span><ChevronDown size={13}/></div><div className="topbar-right"><span className="connection">Saved lab artifacts</span><a className="text-button" href="/research">Research</a><a className="text-button" href="/research/FORGE_RESEARCH.md" target="_blank" rel="noreferrer">Write-up</a><button className="text-button" onClick={()=>void refresh()}><RefreshCw size={13}/> Refresh</button><button className="text-button" onClick={onOpenDemo}>Demo</button><button className="copilot-toggle" onClick={()=>setChat(v=>!v)}><Sparkles size={14}/> Ask copilot</button></div></header>
      <main>
        <div className="title-row"><div><div className="breadcrumb">Workspace <ChevronRight size={12}/> {view==="datasets"?"Datasets":view==="experiments"?"Experiments":view==="frontier"?"Frontier":"Workbench"}</div><h1>{view==="workbench"?"Optimization lab":view==="experiments"?"Experiment ledger":view==="frontier"?"Quality, cost and latency frontier":"Dataset registry"}</h1><p className="page-finding">{view==="workbench"?"Faster SQL has to earn its place. Inspect the rewrite and the evidence.":view==="experiments"?"Every attempt counts, including the ones that did not improve the query.":view==="frontier"?"Coverage, correctness, and optimization overhead from saved benchmark traces.":"Known sources. Explicit scope. No hidden benchmark claims."}</p></div><button className="primary-button" disabled={!!activeJob} onClick={()=>setModal(true)}><Play size={14}/>{activeJob?"Evaluation running":"Run evaluation"}</button></div>
        {error&&<div className="error-banner" role="alert">{error}<button onClick={()=>void refresh()}>Retry</button></div>}
        {activeJob&&<div className="job-strip"><span className="running-indicator"/><span>{shortModel(activeJob.model)} is evaluating the {activeJob.suite} suite.</span><span>Results checkpoint automatically</span></div>}
        {view==="workbench"&&<>
          <div className="run-toolbar"><div className="section-tabs"><button className="active">Query evidence</button><button onClick={()=>setView("experiments")}>Model comparison</button></div><label className="run-selector"><span>Experiment</span><select aria-label="Select experiment" value={run?.manifest.run_id||""} onChange={e=>{setSelectedRun(e.target.value);setSelectedCase("");}}>{runs.map(r=><option key={r.manifest.run_id} value={r.manifest.run_id}>{shortModel(r.manifest.requested_model)} · {r.manifest.suite||"pilot"} · {r.manifest.run_id.slice(9,15)}{r.manifest.mock?" · mock":""}</option>)}</select></label></div>
          <div className="summary-strip">
            <div className="lead-metric"><span>Verified improvements</span><strong>{run?.summary.accepted??"—"}<small> / {run?.summary.cases??"—"} queries</small></strong><p>At least 20% faster on this instance</p></div>
            <div><span>Optimization wall time</span><strong>{number(run?run.summary.total_wall_ms/1000:undefined,1)}<small>s</small></strong><p>Includes model and validation work</p></div>
            <div><span>Model tokens</span><strong>{number(run?totalTokens:undefined,0)}</strong><p>Input + output across attempts</p></div>
            <div><span>Estimated API cost</span><strong className={!run||run.summary.estimated_model_cost_usd===null?"unknown-value":""}>{run?.summary.estimated_model_cost_usd==null?"Unknown":"$"+number(run.summary.estimated_model_cost_usd,5)}</strong><p>{run?.summary.estimated_model_cost_usd==null?"Model rates are not configured":"Configured rates · compute excluded"}</p></div>
          </div>
          <div className="lab-grid">
            <section className="query-list panel"><div className="panel-heading"><h2>Query queue</h2><span>{cases.length} cases</span></div><label className="query-search"><Code2 size={14}/><input aria-label="Filter queries" placeholder="Filter queries…" value={search} onChange={e=>setSearch(e.target.value)}/></label><div className="query-rows">{filtered.length===0?<p className="empty-state">No matching queries.</p>:filtered.map((c,index)=><button key={c.case_id} onClick={()=>setSelectedCase(c.case_id)} className={"query-row "+(record?.case_id===c.case_id?"active":"")}><span className="query-number">{String(index+1).padStart(2,"0")}</span><div><strong>{title(c.case_id)}</strong><small>{c.family.replaceAll("_"," ")}</small></div><span className={"status-dot "+caseStatus(c)} title={stateLabel(caseStatus(c))}/></button>)}</div><div className="queue-footer"><ShieldCheck size={13}/><span>Five correctness fixtures</span></div></section>
            <div className="query-evidence">
              <section className="evidence-heading"><div><span className="mono muted">{record?.case_id||"Waiting for results"}</span><h2>{record?title(record.case_id):"No experiment selected"}</h2></div><span className={"status-label "+status}>{status==="accepted"?<Check size={13}/>:status==="incorrect"?<X size={13}/>:<span/>}{stateLabel(status)}</span></section>
              <div className="sql-grid"><section className="sql-panel"><div className="sql-header"><span>01 <b>Original SQL</b></span><button aria-label="Copy original SQL" onClick={()=>record&&void copy(record.original_sql,"original")}>{copied==="original"?<Check size={14}/>:<Copy size={14}/>}</button></div><pre><SQL sql={record?.original_sql||"No SQL has been evaluated yet."}/></pre></section><section className="sql-panel"><div className="sql-header"><span>02 <b>Model candidate</b></span><button aria-label="Copy candidate SQL" onClick={()=>attempt?.generation&&void copy(attempt.generation.sql,"candidate")}>{copied==="candidate"?<Check size={14}/>:<Copy size={14}/>}</button></div><pre><SQL sql={attempt?.generation?.sql||"No candidate returned for this attempt."}/></pre></section></div>
              <section className="reasoning-note"><GitBranch size={15}/><div><strong>Rewrite rationale</strong><p>{attempt?.generation?.rationale||attempt?.error||"Generation evidence appears here when an attempt is recorded."}</p></div></section>
              <div className="evidence-bottom"><section className="measurement-panel"><div className="panel-heading"><h2>Measured execution</h2>{benchmark&&<strong className="speedup">{number(benchmark.speedup??undefined,1)}<small>× speedup</small></strong>}</div><RuntimePlot record={record}/><p className="panel-footnote">{benchmark?"Median of "+(benchmark.samples_ms?.original?.length||5)+" alternating timing pairs · PostgreSQL execution only":"No timing claim without a valid measured rewrite"}</p></section><section className="validation-panel"><div className="panel-heading"><h2>Verification</h2><ShieldCheck size={16}/></div><div className="check-row"><span>Result equivalence</span><strong className={attempt?.correctness?.equivalent?"positive":attempt?.correctness?"negative":""}>{attempt?.correctness?.equivalent?"Passed":attempt?.correctness?"Mismatch":"Not evaluated"}</strong></div><div className="check-row"><span>Fixture coverage</span><strong>{attempt?.correctness?.equivalent?"5 / 5":"—"}</strong></div><div className="check-row"><span>Attempt budget</span><strong>{record?.attempts.length??0} / {run?.manifest.max_attempts??0}</strong></div><div className="check-row"><span>Win rate in timing pairs</span><strong>{benchmark?.candidate_win_rate!==undefined?number(benchmark.candidate_win_rate*100,0)+"%":"—"}</strong></div><p className="panel-footnote">{attempt?.correctness?.reason||"Finite-instance checks are evidence, not a general equivalence proof."}</p></section></div>
            </div>
          </div>
        </>}
        {view==="experiments"&&<>
          <section className="comparison-section"><div className="panel-heading"><div><h2>Comparable model runs</h2><p>Same recorded database metadata, workload/evaluator hashes, attempt/output budgets and timing pairs.</p></div><span>{byModel.length} models</span></div><div className="comparison-bars">{byModel.length===0?<p className="empty-state">No completed comparable model runs yet.</p>:byModel.map(r=><div className="comparison-row" key={r.manifest.run_id}><div><strong>{shortModel(r.manifest.requested_model)}</strong><small>{r.manifest.provider}</small></div><div className="coverage-track"><span style={{width:(r.summary.cases?r.summary.accepted/r.summary.cases*100:0)+"%"}}/></div><strong>{r.summary.accepted}<small> / {r.summary.cases}</small></strong><span className="mono">{number(r.summary.total_wall_ms/1000,1)} s</span></div>)}</div></section>
          <section className="ledger-section"><div className="panel-heading"><h2>All experiments</h2><span>{runs.length} recorded runs</span></div><div className="table-scroll"><table><thead><tr><th>Model / run</th><th>Dataset</th><th>Outcome</th><th>Accepted</th><th>Rejected incorrect</th><th>Wall time</th><th>API cost</th><th/></tr></thead><tbody>{runs.map(r=><tr key={r.manifest.run_id}><td><strong>{shortModel(r.manifest.requested_model)}</strong><small className="mono">{r.manifest.run_id}</small></td><td>{r.manifest.suite||"pilot"}{r.manifest.mock&&<small>Mock fixtures</small>}</td><td>{r.manifest.state||"Legacy"}</td><td className="numeric">{r.summary.accepted} / {r.summary.cases}</td><td className="numeric">{r.summary.incorrect_candidates_rejected}</td><td className="numeric">{number(r.summary.total_wall_ms/1000,1)} s</td><td className="numeric">{r.summary.estimated_model_cost_usd==null?"—":"$"+number(r.summary.estimated_model_cost_usd,5)}</td><td><button className="text-button" onClick={()=>{setSelectedRun(r.manifest.run_id);setSelectedCase("");setView("workbench");}}>Inspect <ArrowUpRight size={13}/></button></td></tr>)}</tbody></table></div></section>
        </>}
        {view==="frontier"&&<FrontierView/>}
        {view==="datasets"&&<>
          <div className="dataset-intro"><div><Layers3 size={24}/><h2>Public SQL. Explicit microfixtures.</h2><p>{snapshot?.dataset.note||"Loading dataset metadata…"}</p></div><div className="dataset-facts"><div><span>Admitted SQL inputs</span><strong>{snapshot?.dataset.cases.length??"—"}</strong></div><div><span>Query families</span><strong>{familyCount||"—"}</strong></div><div><span>Correctness fixtures</span><strong>5</strong></div><div><span>Performance line items</span><strong>{number(snapshot?.dataset.benchmark_lineitems,0)}</strong></div></div></div>
          <div className="source-note"><GitBranch size={15}/><span>R-Bot source commit</span><a href={"https://github.com/curtis-sun/LLM4Rewrite/tree/"+snapshot?.dataset.source_commit} target="_blank" rel="noreferrer" className="mono">{snapshot?.dataset.source_commit.slice(0,12)||"—"} <ArrowUpRight size={12}/></a><span>Raw files and SHA-256 provenance retained locally.</span></div>
          <div className="table-scroll"><table><thead><tr><th>Query</th><th>Source</th><th>Family</th><th>Template lineage</th><th/></tr></thead><tbody>{snapshot?.dataset.cases.map(c=><tr key={c.id}><td><strong>{title(c.id)}</strong><small className="mono">{c.id}</small></td><td>{c.source||"Own development fixture"}</td><td>{c.family.replaceAll("_"," ")}</td><td className="mono">{c.template_id||c.id}</td><td><button className="text-button" onClick={()=>{const measured=runs.find(r=>r.cases.some(x=>x.case_id===c.id));if(measured){setSelectedRun(measured.manifest.run_id);setSelectedCase(c.id);setView("workbench");}}}>Evidence <ArrowUpRight size={13}/></button></td></tr>)}</tbody></table></div>
          <div className="dataset-caveats"><h2>Admission limitations</h2>{snapshot?.dataset.unsupported?.map(c=><p key={c.source}><strong>{c.source}</strong> — {c.reason}</p>)}<p>Two Q17 parameter variants share one template. Public inputs are development data. Ordered/LIMIT-sensitive benchmark cases require a separate result contract before admission.</p></div>
        </>}
        <footer className="workspace-footer"><span><i/>Development evidence · no held-out ranking</span><span>{snapshot?"Updated "+new Date(snapshot.updated_at).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"}):"Connecting to local evaluator"}<span className="footer-separator">/</span>Powered by PostgreSQL + CopilotKit</span></footer>
      </main>
    </div>
    {chat&&<CopilotPanel snapshot={snapshot} run={run} onSelect={selectQuery} onClose={()=>setChat(false)}/>}
    {modal&&<div className="modal-backdrop" onClick={()=>setModal(false)}><section className="run-modal" role="dialog" aria-modal="true" aria-labelledby="run-title" onClick={e=>e.stopPropagation()}><div className="panel-heading"><h2 id="run-title">Run an evaluation</h2><button className="icon-button" onClick={()=>setModal(false)} aria-label="Close evaluation dialog"><X size={18}/></button></div><p>Generate candidates and validate them against the local database. This makes paid API calls.</p><label>Model<select value={model} onChange={e=>setModel(e.target.value)}><option value="groq:openai/gpt-oss-20b">Groq · GPT-OSS 20B</option><option value="groq:openai/gpt-oss-120b">Groq · GPT-OSS 120B</option><option value="openai:gpt-6.1-sol">OpenAI · GPT-6.1 Sol</option><option value="mock:">Mock · no API calls</option></select></label><label>Dataset<select value={suite} onChange={e=>setSuite(e.target.value)}><option value="all">All admitted queries · 14 cases</option><option value="pilot">Pilot · 3 cases</option><option value="lab">Expanded lab · 11 cases</option></select></label><label>Maximum attempts per case<select value={attempts} onChange={e=>setAttempts(Number(e.target.value))}><option value={1}>1 · one-shot</option><option value={2}>2 · with repair</option><option value={3}>3 · with repair</option></select></label><div className="run-budget"><ShieldCheck size={16}/><span>Up to {(suite==="all"?14:suite==="lab"?11:3)*attempts} inference calls · 4,096 output tokens per call · five timing pairs</span></div><p className="muted">API cost depends on tokens and model rates. Database compute is additional. Failed API requests are not automatically retried.</p><button className="primary-button" disabled={launching} onClick={()=>void launch()}><Play size={14}/>{launching?"Starting…":"Start evaluation"}</button></section></div>}
  </div>;
}

export function Workbench({initialSurface = "demo"}:{initialSurface?: "demo" | "lab"}) {
  const [surface, setSurface] = useState<"demo" | "lab">(initialSurface);
  if (surface === "demo") return <SurgeryDemo onOpenLab={() => setSurface("lab")} />;
  return <Lab onOpenDemo={() => setSurface("demo")} />;
}
