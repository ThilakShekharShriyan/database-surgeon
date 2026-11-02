"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Check, ShieldAlert, ShieldCheck, Sparkles, X } from "lucide-react";
import { FrontierView } from "@/components/frontier";
import { BENCHMARK, FINOPS, LEDGER, VERSIONS } from "@/lib/rubric";
import "../app/demo.css";

type PipelineStep = {
  id: string;
  title: string;
  status: string;
  detail?: string;
  reduction?: number | null;
  speedup?: number | null;
  cost_usd?: number | null;
  latency_ms?: number | null;
  calls?: number;
  candidates?: number;
  repairs?: number;
};

type OptimizeResult = {
  system?: string;
  case_id?: string;
  original_sql?: string;
  result_sql?: string;
  changed?: boolean;
  cost_usd?: number | null;
  latency_ms?: number;
  wall_ms?: number;
  pipeline?: { steps: PipelineStep[]; accepted_origin?: string };
  candidates?: { origin: string; verified?: boolean; stage?: string; reduction?: number | null; sql?: string }[];
  stage_models?: { name: string; provider: string; model: string }[];
  stack?: { fireworks?: boolean; nvidia_nemotron?: boolean; label?: string };
  corrupt_sql?: string;
  outcome?: string;
  replay?: boolean;
  note?: string;
  error?: string;
};

type Row = {
  system: string;
  accepted_rate: number;
  incorrect_returned_count: number;
  cost_per_case_usd: number | null;
  geomean_speedup: number;
  latency_p50_ms?: number;
  cases?: number;
  trials?: number;
  complete?: boolean;
  expected_cases?: number;
};

const PRESETS = [
  {
    id: "date_filter",
    tier: "Tier 1 · Instant AST triage",
    blurb: "Sargability trap — sqlglot should fix in milliseconds for $0.",
    sql: `SELECT id, amount FROM orders WHERE to_char(created_at, 'YYYY-MM-DD') = '2026-03-15'`,
    trap: null as string | null,
    preferReplay: false,
  },
  {
    id: "corr_avg_salary_dept__0",
    tier: "Tier 2 · EXPLAIN-guided LLM surgery",
    blurb: "Correlated AVG — inspect a recorded model rewrite and its measured gates.",
    sql: `SELECT e.empno, e.ename FROM emp e WHERE e.job = 'MANAGER' AND e.sal > (SELECT avg(e2.sal) FROM emp e2 WHERE e2.deptno = e.deptno)`,
    trap: null as string | null,
    preferReplay: true,
  },
  {
    id: "nullable_antijoin",
    tier: "Tier 3 · Corruption prevented",
    blurb: "NULL-sensitive NOT IN — oss20b-raw returned wrong rows on fixtures; harness must repair or abstain.",
    sql: `SELECT id FROM customers WHERE id NOT IN (SELECT customer_id FROM orders)`,
    trap: "NOT IN and NOT EXISTS differ when customer_id contains NULL. Inspect the recorded counterexample and the system's response. Passing finite fixtures is evidence, not a general proof of equivalence.",
    preferReplay: true,
  },
] as const;

const JUDGE = [
  {
    q: "Who benefits? (25% Business)",
    a: FINOPS.user,
  },
  {
    q: "What task?",
    a: "Propose a PostgreSQL rewrite, compare rows and output types on development fixtures, measure execution time, and retain the original if no candidate clears the gates. Optional specialist training uses selected traces; hosted inference and training send their supplied SQL and context to the provider.",
  },
  {
    q: "How evaluate? (40% Benchmark)",
    a: `The case set contains ${BENCHMARK.dev} development and ${BENCHMARK.heldout} held-out cases. The evaluator checks eight fixtures, including three withheld from the system verifier, and requires at least 20% lower median execution time. Run coverage, incorrect returns, API cost, latency and paired statistics must be read together.`,
  },
  {
    q: "What improved vs frontier?",
    a: "The complete development open-harness run matches the frontier baseline's aggregate acceptance rate and improves observed correctness over open-raw. Its current API cost and optimizer latency are higher than the frontier's. The research view shows paired tests and confidence intervals; held-out comparisons remain separate.",
  },
  {
    q: "Tradeoffs / limits?",
    a: "Harness adds verify/repair latency (~seconds) — for CI / pg_stat daemons, not always inline. SFT still needs a trust decision to leave the box. Synthetic fixtures ≠ warehouse scale. Cannot invent missing indexes.",
  },
];

type MetricRow = {
  version: string;
  title: string;
  accept: string;
  wrong: string;
  geo: string;
  p50: string;
  cost1k: string;
  dAccept: string;
  dWrong: string;
  dCost: string;
  partial?: boolean;
};

function buildDelta(summary: Row[] | null): MetricRow[] {
  const pick = (name: string) => summary?.find((r) => r.system === name);
  const frontier = pick("frontier-raw");
  const openRaw = pick("open-raw");
  const harness = pick("open-harness");
  const cascade = pick("cascade-surgeon");
  const fmtA = (r?: Row) => (r ? pct(r.accepted_rate) : "—");
  const fmtW = (r?: Row) => (r ? String(r.incorrect_returned_count) : "—");
  const fmtG = (r?: Row) => (r ? r.geomean_speedup.toFixed(2) + "×" : "—");
  const cost1k = (r?: Row) =>
    r?.cost_per_case_usd == null ? "—" : "$" + (r.cost_per_case_usd * 1000).toFixed(2);
  const p50 = (name: string) => {
    const full = summary?.find((r) => r.system === name);
    if (full?.latency_p50_ms == null) return "—";
    return (full.latency_p50_ms / 1000).toFixed(1) + " s";
  };
  const dPp = (a?: Row, b?: Row) => {
    if (!a || !b) return "—";
    const d = (a.accepted_rate - b.accepted_rate) * 100;
    return (d >= 0 ? "+" : "") + d.toFixed(1) + " pp";
  };
  const dWrong = (a?: Row, b?: Row) => {
    if (!a || !b) return "—";
    const d = a.incorrect_returned_count - b.incorrect_returned_count;
    return (d > 0 ? "+" : "") + String(d);
  };
  const dCost = (a?: Row, b?: Row) => {
    if (a?.cost_per_case_usd == null || b?.cost_per_case_usd == null || b.cost_per_case_usd === 0) return "—";
    const ratio = a.cost_per_case_usd / b.cost_per_case_usd;
    return ratio < 1 ? `−${((1 - ratio) * 100).toFixed(0)}% $` : `+${((ratio - 1) * 100).toFixed(0)}% $`;
  };
  return [
    {
      version: "v0",
      title: "Frontier raw",
      accept: fmtA(frontier),
      wrong: fmtW(frontier),
      geo: fmtG(frontier),
      p50: p50("frontier-raw"),
      cost1k: cost1k(frontier),
      dAccept: "baseline",
      dWrong: "baseline",
      dCost: "baseline",
    },
    {
      version: "v1",
      title: "Open raw",
      accept: fmtA(openRaw),
      wrong: fmtW(openRaw),
      geo: fmtG(openRaw),
      p50: p50("open-raw"),
      cost1k: cost1k(openRaw),
      dAccept: dPp(openRaw, frontier),
      dWrong: dWrong(openRaw, frontier),
      dCost: dCost(openRaw, frontier),
    },
    {
      version: "v2",
      title: "+ Surgical harness",
      accept: fmtA(harness),
      wrong: fmtW(harness),
      geo: fmtG(harness),
      p50: p50("open-harness"),
      cost1k: cost1k(harness),
      dAccept: dPp(harness, frontier),
      dWrong: dWrong(harness, frontier),
      dCost: dCost(harness, frontier),
      partial: Boolean(harness && (harness.complete === false || (harness.cases ?? 0) < BENCHMARK.dev)),
    },
    {
      version: "v3",
      title: "Cascade · rules → open models",
      accept: fmtA(cascade),
      wrong: fmtW(cascade),
      geo: fmtG(cascade),
      p50: p50("cascade-surgeon"),
      cost1k: cost1k(cascade),
      dAccept: dPp(cascade, frontier),
      dWrong: dWrong(cascade, frontier),
      dCost: dCost(cascade, frontier),
      partial: Boolean(cascade && (cascade.complete === false || (cascade.cases ?? 0) < BENCHMARK.dev)),
    },
  ];
}

function Mark() {
  return (
    <svg viewBox="0 0 32 32" width="22" height="22" aria-hidden="true">
      <path d="M5 9c0-3 22-3 22 0v14c0 4-22 4-22 0V9Zm0 0c0 4 22 4 22 0M5 16c0 3 11 4 16 2" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="m15 26 11-13 3 3-11 13-4 1Z" fill="#fff" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function pct(v: number) {
  return (100 * v).toFixed(1) + "%";
}
function usd(v: number | null | undefined) {
  if (v == null) return "—";
  if (v === 0) return "$0";
  if (v < 0.001) return "$" + v.toPrecision(2);
  return "$" + v.toFixed(4);
}

export function SurgeryDemo({ onOpenLab }: { onOpenLab: () => void }) {
  const [tab, setTab] = useState<"surgery" | "pitch" | "ledger">("pitch");
  const [preset, setPreset] = useState(0);
  const [sql, setSql] = useState<string>(PRESETS[0].sql);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<OptimizeResult | null>(null);
  const [fault, setFault] = useState("");
  const [summary, setSummary] = useState<Row[] | null>(null);
  const [heldoutNote, setHeldoutNote] = useState("Loading held-out coverage…");

  useEffect(() => {
    fetch("/api/frontier", { cache: "no-store" })
      .then((r) => { if (!r.ok) throw new Error("Benchmark summaries unavailable"); return r.json(); })
      .then((d) => {
        setSummary(d?.dev?.systems || []);
        const heldout = d?.heldout?.systems || [];
        const complete = heldout.filter((r: Row) => r.complete !== false && (r.cases ?? 0) >= BENCHMARK.heldout);
        setHeldoutNote(`${complete.length} system${complete.length === 1 ? "" : "s"} have full held-out coverage; model comparisons may be incomplete.`);
      })
      .catch(() => { setSummary([]); setHeldoutNote("Held-out coverage unavailable."); });
  }, []);

  const kpi = useMemo(() => {
    const rows = summary || [];
    const pick = (name: string) => rows.find((r) => r.system === name);
    const harness = pick("open-harness");
    const frontier = pick("frontier-raw");
    const openRaw = pick("open-raw");
    return { harness, frontier, openRaw };
  }, [summary]);

  const deltaRows = useMemo(() => buildDelta(summary), [summary]);

  async function runSurgery(opts?: { replay?: boolean }) {
    setBusy(true);
    setFault("");
    setResult(null);
    const replay = opts?.replay ?? PRESETS[preset].preferReplay;
    if (replay && sql.trim() !== PRESETS[preset].sql.trim()) {
      setFault("Restore the preset to replay its recorded trace. Use Live for an edited query; live model stages may make paid API calls.");
      setBusy(false);
      return;
    }
    try {
      const response = await fetch("/api/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sql, system: "cascade-surgeon", replay }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Optimize failed");
      setResult(data);
    } catch (err) {
      setFault(err instanceof Error ? err.message : "Optimize failed");
    } finally {
      setBusy(false);
    }
  }

  const steps = result?.pipeline?.steps || [];
  const delta =
    kpi.harness && kpi.frontier
      ? (kpi.harness.accepted_rate - kpi.frontier.accepted_rate) * 100
      : null;

  return (
    <div className="sd pitch-shell">
      <header className="sd-top">
        <button className="sd-brand" type="button" onClick={() => { setTab("surgery"); setResult(null); }}>
          <Mark /> Database Surgeon
        </button>
        <nav className="pitch-tabs" aria-label="Demo sections">
          <a className="sd-link" href="/research">Research</a>
          <button type="button" className={tab === "pitch" ? "active" : ""} onClick={() => setTab("pitch")}>Judge pitch</button>
          <button type="button" className={tab === "surgery" ? "active" : ""} onClick={() => setTab("surgery")}>Live surgery</button>
          <button type="button" className={tab === "ledger" ? "active" : ""} onClick={() => setTab("ledger")}>Experiments</button>
          <button type="button" className="sd-link" onClick={onOpenLab}>Lab</button>
        </nav>
      </header>

      {tab === "ledger" ? (
        <main className="sd-main is-run pitch-main">
          <h1 className="sd-fade">Experiments & reproducibility.</h1>
          <p className="sd-lede">
            Inspect the registered systems, harness settings and saved JSONL traces. Fine-tuning is optional; measured outcomes determine the result.
          </p>
          <div className="ledger-list">
            {VERSIONS.map((v, i) => (
              <article key={v.id} className="ledger-card">
                <header>
                  <strong>{v.id}</strong> {v.title}
                </header>
                <p><span>Registry</span> <code>{v.system}</code></p>
                <p><span>Model</span> {v.model}</p>
                <p><span>Harness</span> {v.harness}</p>
                <p className="muted">{v.blurb}</p>
                <pre className="repro-cmd">{LEDGER[i].reproduce}</pre>
                <pre className="repro-cmd">{"config " + JSON.stringify(LEDGER[i].config)}</pre>
              </article>
            ))}
          </div>
          <section className="judge-gotcha" style={{ marginTop: 24 }}>
            <ShieldCheck size={18} />
            <div>
              <strong>Reproduce the benchmark</strong>
              <p>
                Cases frozen at <code>benchmarks/eval_v2/cases.jsonl</code> ({BENCHMARK.total} = {BENCHMARK.dev} dev + {BENCHMARK.heldout} held-out).
                System configuration hashes are recorded in <code>benchmarks/eval_v2/FROZEN.json</code>; they do not fully pin code, mutable caches or database state. Per-query traces: <code>benchmarks/eval_v2/runs/&lt;system&gt;/&#123;dev,heldout&#125;_t*.jsonl</code>.
                Report: <code>.venv/bin/python -m surgeon.eval report --split dev</code> and <code>--split heldout</code>.
              </p>
            </div>
          </section>
        </main>
      ) : tab === "pitch" ? (
        <main className="sd-main is-run pitch-main">
          <p className="rubric-chip">Judging: 40% Benchmark · 25% Business · 20% Technical · 10% Demo · 5% Docs</p>
          <h1 className="sd-fade">Evidence first — {BENCHMARK.total} fixed cases.</h1>
          <p className="sd-lede">
            {BENCHMARK.dev} development cases and {BENCHMARK.heldout} held-out cases are defined. The comparisons below use development evidence.
            {" "}{heldoutNote}
          </p>

          <section className="finops-banner">
            <h2>Workload economics</h2>
            <p><strong>User.</strong> {FINOPS.user}</p>
            <p><strong>Problem.</strong> {FINOPS.problem}</p>
            <p>
              <strong>When it helps.</strong> Optimize repeated, expensive queries once and reuse the result after checking its context.
              Break-even executions = total optimization overhead ÷ time saved per execution.
              A seven-second optimization saving one millisecond needs roughly 7,000 executions to recover elapsed time.
              This is an arithmetic illustration, not measured customer savings.
            </p>
            <p>
              <strong>Private retrain loop.</strong> {FINOPS.privacyLoop}
            </p>
            <p className="muted">
              API costs below exclude database compute, hardware and training. Execution-time reduction does not directly establish CPU or dollar savings. Loop CLI:{" "}
              <code>.venv/bin/python scripts/private_retrain_loop.py plan</code>
            </p>
          </section>

          <div className="kpi-row">
            <article className="kpi-card hero">
              <span>Development acceptance</span>
              <strong>
                {kpi.harness && kpi.frontier
                  ? `${pct(kpi.harness.accepted_rate)} vs ${pct(kpi.frontier.accepted_rate)}`
                  : "Awaiting evidence"}
              </strong>
              <p>
                Open harness vs frontier-raw on the same eval
                {delta != null ? ` · ${delta >= 0 ? "+" : ""}${delta.toFixed(1)} pp` : ""}
                {kpi.harness?.cases != null && kpi.harness.cases < 98 ? ` · harness n=${kpi.harness.cases}/98` : ""}
              </p>
            </article>
            <article className="kpi-card">
              <span>Observed incorrect returns</span>
              <strong>{kpi.harness ? kpi.harness.incorrect_returned_count : "—"} wrong</strong>
              <p>
                Open harness · open-raw returned{" "}
                <em className="bad">{kpi.openRaw?.incorrect_returned_count ?? "—"}</em> incorrect queries.
                Observed counts do not guarantee future correctness.
              </p>
            </article>
            <article className="kpi-card">
              <span>Benchmark size</span>
              <strong>{BENCHMARK.total}</strong>
              <p>{BENCHMARK.dev} dev + {BENCHMARK.heldout} held-out · fixed scoring · hidden fixtures</p>
            </article>
          </div>

          <section className="delta-table-wrap">
            <h2>Explain what improved — same eval, step-by-step</h2>
            <div className="table-scroll">
              <table className="delta-table">
                <thead>
                  <tr>
                    <th>Version</th>
                    <th>Accept %</th>
                    <th>Δ Accept</th>
                    <th>Wrong</th>
                    <th>Δ Wrong</th>
                    <th>Geo×</th>
                    <th>p50</th>
                    <th>$/1k q</th>
                    <th>Δ Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {deltaRows.map((r) => (
                    <tr key={r.version}>
                      <td><strong>{r.version}</strong> {r.title}{r.partial ? " · partial" : ""}</td>
                      <td className="numeric">{r.accept}</td>
                      <td className={"numeric " + (r.dAccept.startsWith("+") ? "gain" : "")}>{r.dAccept}</td>
                      <td className={"numeric " + (r.wrong !== "0" && r.wrong !== "—" ? "bad" : "")}>{r.wrong}</td>
                      <td className="numeric">{r.dWrong}</td>
                      <td className="numeric">{r.geo}</td>
                      <td className="numeric">{r.p50}</td>
                      <td className="numeric">{r.cost1k}</td>
                      <td className={"numeric " + (r.dCost.startsWith("−") || r.dCost.startsWith("-") ? "gain" : "")}>{r.dCost}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted">Descriptive development summaries; repetition counts can differ across systems. Partial rows describe observed cases only. Paired comparisons use the same case/trial in the research view.</p>
          </section>

          <section className="safety-cliff">
            <h2>The safety cliff</h2>
            <div className="cliff-bars" role="img" aria-label="Accepted rate and wrong returns by system">
              {[
                { label: "rules-only", row: summary?.find((r) => r.system === "rules-only") },
                { label: "open-raw", row: kpi.openRaw },
                { label: "frontier-raw", row: kpi.frontier },
                { label: "open-harness (ours)", row: kpi.harness },
              ].map(({ label, row }) => {
                const accept = row?.accepted_rate ?? 0;
                const wrong = row?.incorrect_returned_count ?? 0;
                return (
                  <div className="cliff-col" key={label}>
                    <div className="cliff-accept" style={{ height: `${Math.max(8, accept * 160)}px` }} title={pct(accept)} />
                    <div className={"cliff-wrong " + (wrong ? "hot" : "")} style={{ height: `${Math.min(80, wrong * 2.2)}px` }} title={`${wrong} wrong`} />
                    <span>{label}</span>
                    <small>{row ? `${pct(accept)} · ${wrong} wrong` : "pending"}</small>
                  </div>
                );
              })}
            </div>
            <p className="muted">Green = accepted beneficial rewrite rate. Red stub = wrong SQL returned (production corruption risk).</p>
          </section>

          <section className="pitch-frontier">
            <h2>Pareto — quality vs $/query</h2>
            <FrontierView />
          </section>

          <section className="judge-grid">
            <h2>Scoresheet answers</h2>
            <div className="judge-cards">
              {JUDGE.map((item) => (
                <article key={item.q}>
                  <h3>{item.q}</h3>
                  <p>{item.a}</p>
                </article>
              ))}
            </div>
            <aside className="judge-gotcha">
              <ShieldCheck size={18} />
              <div>
                <strong>What the harness contributes</strong>
                <p>
                  Both raw and harnessed systems receive execution-plan context. The harness adds rules, catalog facts,
                  retrieved patterns, multiple samples, repair and finite-instance verification. Compare frontier with the same
                  harness and budgets before attributing differences to the open model itself.
                </p>
              </div>
            </aside>
          </section>
        </main>
      ) : (
        <main className="sd-main is-compose">
          <h1 className="sd-fade">Live query surgery.</h1>
          <p className="sd-lede">
            Inspect a recorded trace or run a query through the development verifier. Live model stages may make paid API calls.
          </p>
          <div className="sponsor-badge">Configured cascade: rules → Fireworks GLM / NVIDIA Nemotron. Actual model stages appear in each live result.</div>

          <div className="preset-row">
            {PRESETS.map((item, index) => (
              <button
                key={item.id}
                type="button"
                disabled={busy}
                className={"preset-card " + (preset === index ? "active" : "")}
                onClick={() => {
                  setPreset(index);
                  setSql(item.sql);
                  setResult(null);
                  setFault("");
                }}
              >
                <strong>{item.tier}</strong>
                <span>{item.blurb}</span>
              </button>
            ))}
          </div>

          {PRESETS[preset].trap && (
            <p className="sd-fault" style={{ marginTop: 16 }} role="note">{PRESETS[preset].trap}</p>
          )}

          <div className="sd-card">
            <label className="sr-only" htmlFor="surgery-sql">PostgreSQL query</label>
            <textarea id="surgery-sql" value={sql} onChange={(e) => setSql(e.target.value)} spellCheck={false} disabled={busy} />
            <div className="sd-card-foot">
              <p className="muted">
                System: <code>cascade-surgeon</code> · recorded traces retain their source system; live stages depend on local configuration.
              </p>
              <div style={{ display: "flex", gap: 8 }}>
                <button className="sd-go wide" type="button" disabled={!sql.trim() || busy} onClick={() => void runSurgery({ replay: PRESETS[preset].preferReplay })}>
                  {busy ? "Operating…" : PRESETS[preset].preferReplay ? "Replay recorded trace" : "Run surgery"} <ArrowRight size={16} />
                </button>
                {PRESETS[preset].preferReplay && (
                  <button className="sd-link strong" type="button" disabled={busy} onClick={() => void runSurgery({ replay: false })}>Live</button>
                )}
              </div>
            </div>
          </div>

          {fault && <p className="sd-fault" role="alert">{fault}</p>}

          {result && (
            <section className="pipeline">
              <div className="pipeline-head">
                <h2>Surgical pipeline trace</h2>
                <span>
                  {result.outcome === "incorrect" ? "Recorded incorrect rewrite" : result.changed ? "Rewrite cleared recorded gates" : "Original kept"}
                  {result.pipeline?.accepted_origin ? ` · ${result.pipeline.accepted_origin}` : ""}
                  {" · "}{result.corrupt_sql ? "Illustrative fallback · no fresh model call" : `${result.replay ? "Recorded API cost " : "API cost "}${usd(result.cost_usd)}`}
                  {result.replay ? ` · ${(result.latency_ms ?? 0).toFixed(0)} ms recorded optimizer time` : ` · ${(result.wall_ms ?? 0).toFixed(0)} ms wall`}
                </span>
              </div>
              {!!result.stage_models?.length && (
                <p className="muted" style={{ marginTop: 8 }}>
                  Models: {result.stage_models.map((s) => `${s.provider}:${s.model.replace("accounts/fireworks/models/", "")}`).join(" → ")}
                </p>
              )}
              <ol className="pipeline-steps">
                {steps.map((step) => {
                  const ok = ["applied", "passed", "ran", "used"].includes(step.status);
                  const warn = ["abstained", "skipped", "no_change", "tried"].includes(step.status);
                  return (
                    <li key={step.id} className={ok ? "ok" : warn ? "warn" : "bad"}>
                      <span className="pip-icon">{ok ? <Check size={14} /> : warn ? <Sparkles size={14} /> : <X size={14} />}</span>
                      <div>
                        <strong>{step.title}</strong>
                        <em>{step.status}</em>
                        <p>{step.detail}</p>
                        {step.id === "speedup" && step.speedup != null && (
                          <p className="speed-line">{step.speedup.toFixed(2)}× implied · reduction {(100 * (step.reduction || 0)).toFixed(0)}%</p>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ol>
              {result.corrupt_sql && (
                <div className="sql-diff-mini" style={{ marginBottom: 10 }}>
                  <div>
                    <span>Recorded incorrect raw-model output</span>
                    <pre style={{ color: "#c4242a" }}>{result.corrupt_sql}</pre>
                  </div>
                  <div>
                    <span>Illustrative fallback: retain the original</span>
                    <pre>{result.result_sql}</pre>
                  </div>
                </div>
              )}
              {!result.corrupt_sql && (
                <div className="sql-diff-mini">
                  <div>
                    <span>Before</span>
                    <pre>{result.original_sql}</pre>
                  </div>
                  <div>
                    <span>After</span>
                    <pre>{result.result_sql}</pre>
                  </div>
                </div>
              )}
              {result.note && <p className="muted" style={{ marginTop: 8 }}>{result.replay ? "Recorded replay · " : ""}{result.corrupt_sql ? "This illustrates rejection of a recorded raw-model error; it is not a fresh harness execution." : result.note}</p>}
              {!!result.candidates?.length && (
                <details className="cand-log">
                  <summary>Candidates ({result.candidates.length})</summary>
                  <ul>
                    {result.candidates.map((c, i) => (
                      <li key={i}>
                        <code>{c.origin}</code> · {c.verified ? "verified" : "rejected"} · {c.stage || "—"}
                        {c.reduction != null ? ` · ${(c.reduction * 100).toFixed(0)}% red.` : ""}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              {!result.changed && preset > 0 && (
                <p className="sd-status"><ShieldAlert size={14} /> Harness abstained or could not clear the gates — that is a feature, not a bug.</p>
              )}
            </section>
          )}
        </main>
      )}
    </div>
  );
}
