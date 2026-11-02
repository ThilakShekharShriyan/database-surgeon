"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowRight, ArrowUp } from "lucide-react";
import { useAgent, useCopilotKit, useFrontendTool } from "@copilotkit/react-core/v2";
import { z } from "zod";
import { assertSelect, applyUnifiedDiff, lineDiff, type DiffRow } from "@/lib/sql-diff";
import { SqlDocument } from "@/components/sql-document";
import "../app/demo.css";

const SCHEMA = `Local bench fixture, not a held-out benchmark.
customers(id integer primary key, name text);
orders(id integer primary key, customer_id integer nullable references customers(id), amount numeric(12,2) nullable, created_at timestamp not null);
Indexes: orders(created_at), orders(customer_id).`;

const EXAMPLES = [
  { id: "date_filter", label: "Date filter" },
  { id: "month_range", label: "Month range" },
  { id: "correlated_count", label: "Correlated count" },
  { id: "nullable_antijoin", label: "NULL anti-join" },
  { id: "already_indexed", label: "Already indexed" },
];

type Stage = "compose" | "rewrite" | "verify" | "idea" | "done";
type Idea = { title: string; detail: string };
type Verdict = {
  status: "accepted" | "not_faster" | "incorrect" | "no_change" | "unverified" | "error";
  reason?: string;
  original_ms?: number;
  candidate_ms?: number;
  speedup?: number | null;
};
type DatasetCase = { id: string; sql: string };
type ChatMessage = {
  id: string;
  role: string;
  toolCallId?: string;
  toolCalls?: { id: string; function: { name: string; arguments: string } }[];
};

const normalize = (sql: string) => sql.replace(/\s+/g, " ").replace(/;\s*$/, "").trim().toLowerCase();
const ms = (value?: number) => value === undefined ? "—" : value < 10 ? value.toFixed(2) : value.toFixed(1);

function Mark() {
  return (
    <svg viewBox="0 0 32 32" width="22" height="22" aria-hidden="true">
      <path d="M5 9c0-3 22-3 22 0v14c0 4-22 4-22 0V9Zm0 0c0 4 22 4 22 0M5 16c0 3 11 4 16 2" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="m15 26 11-13 3 3-11 13-4 1Z" fill="#fff" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function jsonString(source: string, field: string) {
  const key = `"${field}"`;
  const at = source.indexOf(key);
  if (at < 0) return "";
  let index = source.indexOf(":", at + key.length);
  if (index < 0) return "";
  while (index < source.length && source[index] !== '"') index += 1;
  if (source[index] !== '"') return "";
  index += 1;
  let out = "";
  while (index < source.length) {
    const char = source[index];
    if (char === "\\") {
      const next = source[index + 1];
      if (!next) break;
      out += next === "n" ? "\n" : next === "t" ? "\t" : next;
      index += 2;
      continue;
    }
    if (char === '"') break;
    out += char;
    index += 1;
  }
  return out;
}

function incomingRows(diff: string): DiffRow[] {
  const rows: DiffRow[] = [];
  for (const line of diff.split("\n")) {
    if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("@@") || line.startsWith("diff ")) continue;
    if (line.startsWith("+")) rows.push({ kind: "add", text: line.slice(1) });
    else if (line.startsWith("-")) rows.push({ kind: "del", text: line.slice(1) });
  }
  return rows;
}

function Steps({ stage }: { stage: Stage }) {
  const order: Stage[] = ["rewrite", "verify", "idea"];
  const labels = { rewrite: "Rewrite by diff", verify: "Verify on Postgres", idea: "Next idea" } as const;
  const current = stage === "done" ? 3 : order.indexOf(stage);
  return (
    <ol className="sd-steps" aria-label="Progress">
      {order.map((step, index) => {
        const state = index < current ? "done" : index === current ? "active" : "";
        return (
          <li className={state} key={step}>
            <span className="sd-step-label">{labels[step as keyof typeof labels]}</span>
            <span className="sd-track"><span /></span>
          </li>
        );
      })}
    </ol>
  );
}

function Result({ verdict }: { verdict: Verdict }) {
  if (verdict.status === "accepted" || verdict.status === "not_faster") {
    const original = verdict.original_ms ?? 0;
    const candidate = verdict.candidate_ms ?? 0;
    const longest = Math.max(original, candidate) || 1;
    const width = (value: number) => Math.max(1.5, (value / longest) * 100) + "%";
    return (
      <section className="sd-result">
        <div className="sd-bars" role="img" aria-label={`Original ${ms(original)} milliseconds, rewrite ${ms(candidate)} milliseconds`}>
          <div className="sd-bar-row"><span>Original</span><div className="sd-bar-track"><div className="sd-bar original" style={{ "--w": width(original) } as React.CSSProperties} /></div><strong>{ms(original)} ms</strong></div>
          <div className="sd-bar-row"><span>Rewrite</span><div className="sd-bar-track"><div className="sd-bar rewrite" style={{ "--w": width(candidate) } as React.CSSProperties} /></div><strong>{ms(candidate)} ms</strong></div>
        </div>
        <p className="sd-caption">Same rows on 5 fixture databases. Median of 5 paired runs on local synthetic data.{verdict.status === "not_faster" ? " Not 20% faster, so the lab keeps the original." : ""}</p>
      </section>
    );
  }
  const text = {
    incorrect: verdict.reason || "The rewrite returns different rows on a fixture database.",
    no_change: "No diff landed, so there is nothing to verify.",
    unverified: "Only the 14 admitted lab queries run on the local fixtures. This rewrite was not executed.",
    error: verdict.reason || "The evaluator could not verify this rewrite.",
  }[verdict.status];
  return <section className={"sd-result " + (verdict.status === "incorrect" ? "bad" : "")}><p className="sd-caption">{text}</p></section>;
}

export function QueryDemo({ onOpenLab }: { onOpenLab: () => void }) {
  const { agent } = useAgent();
  const { copilotkit } = useCopilotKit();
  const [draft, setDraft] = useState("");
  const [stage, setStage] = useState<Stage>("compose");
  const [original, setOriginal] = useState("");
  const [current, setCurrent] = useState("");
  const [notes, setNotes] = useState<string[]>([]);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [idea, setIdea] = useState<Idea | null>(null);
  const [fault, setFault] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [cases, setCases] = useState<DatasetCase[]>([]);
  const docRef = useRef("");
  const cutsRef = useRef(0);
  const ideaRef = useRef(false);
  const runLock = useRef(false);
  const verdictRef = useRef<Verdict | null>(null);
  const missedRef = useRef(false);
  const [unchanged, setUnchanged] = useState(false);

  useEffect(() => {
    setMessages(agent.messages as ChatMessage[]);
    const subscription = agent.subscribe({ onMessagesChanged: () => setMessages(agent.messages.slice() as ChatMessage[]) });
    return () => subscription.unsubscribe();
  }, [agent]);

  useEffect(() => {
    fetch("/api/snapshot", { cache: "no-store" })
      .then((response) => response.json())
      .then((data) => setCases(data?.dataset?.cases ?? []))
      .catch(() => setCases([]));
  }, []);

  useFrontendTool({
    name: "apply_sql_diff",
    description: "Change the query on the canvas. The only allowed edit is a unified diff against the current SQL. Include ---/+++ headers, @@ hunks, and context lines that start with a space. Do not send a full replacement query.",
    parameters: z.object({
      unified_diff: z.string().describe("Unified diff against the current document."),
      note: z.string().describe("One short sentence describing this cut."),
    }),
    handler: async ({ unified_diff, note }) => {
      const applied = applyUnifiedDiff(docRef.current, unified_diff);
      if (!applied.ok) {
        missedRef.current = true;
        setFault(applied.error);
        return JSON.stringify({ applied: false, error: applied.error, current_sql: docRef.current });
      }
      const rejected = assertSelect(applied.sql);
      if (rejected) {
        setFault(rejected);
        return JSON.stringify({ applied: false, error: rejected, current_sql: docRef.current });
      }
      docRef.current = applied.sql;
      cutsRef.current += 1;
      setFault("");
      setCurrent(applied.sql);
      setNotes((list) => [...list, note]);
      return JSON.stringify({ applied: true, sql: applied.sql });
    },
    render: () => null,
  }, []);

  useFrontendTool({
    name: "state_next_idea",
    description: "Only when the canvas asks for the next idea, state one concrete next step. Do not invent a measured speedup.",
    parameters: z.object({
      title: z.string().describe("Short name of the next step, under 70 characters."),
      detail: z.string().describe("One or two sentences: what to try or measure next, and why."),
    }),
    handler: async ({ title, detail }) => {
      ideaRef.current = true;
      setIdea({ title, detail });
      return JSON.stringify({ recorded: true });
    },
    render: () => null,
  }, []);

  async function ask(instruction: string) {
    agent.addMessage({ id: crypto.randomUUID(), role: "user", content: instruction });
    await copilotkit.runAgent({ agent });
  }

  async function verify(caseId: string | undefined, before: number): Promise<Verdict> {
    if (cutsRef.current === before) return { status: "no_change" };
    if (!caseId) return { status: "unverified" };
    try {
      const response = await fetch("/api/verify", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ case: caseId, candidate: docRef.current }) });
      const data = await response.json();
      if (!response.ok) return { status: "error", reason: data.error };
      const counts = data.correctness?.expected_rows !== undefined
        ? ` Expected ${data.correctness.expected_rows.toLocaleString()} rows, got ${data.correctness.actual_rows.toLocaleString()}.` : "";
      return { status: data.status, reason: data.correctness?.reason ? data.correctness.reason + counts : undefined, ...(data.benchmark ?? {}) };
    } catch {
      return { status: "error", reason: "Could not reach the local evaluator." };
    }
  }

  function describe(result: Verdict) {
    if (result.status === "accepted" || result.status === "not_faster") {
      return `${result.status === "accepted" ? "Accepted" : "Correct but under the 20% bar"}: same rows on 5 fixture databases, median ${ms(result.original_ms)} ms before and ${ms(result.candidate_ms)} ms after on local synthetic data.`;
    }
    if (result.status === "incorrect") return "Rejected: the rewrite returned different rows on a fixture database. " + (result.reason ?? "");
    if (result.status === "unverified") return "Not executed: this query is not one of the admitted lab queries.";
    if (result.status === "no_change") return "No diff was applied.";
    return "Verification failed: " + (result.reason ?? "unknown error");
  }

  async function cycle(instruction: string) {
    if (runLock.current) return;
    runLock.current = true;
    const caseId = cases.find((item) => normalize(item.sql) === normalize(original || draft))?.id;
    const before = cutsRef.current;
    const previous = verdictRef.current;
    ideaRef.current = false;
    setIdea(null);
    setVerdict(null);
    setUnchanged(false);
    setFault("");
    try {
      setStage("rewrite");
      missedRef.current = false;
      await ask(instruction);
      if (cutsRef.current === before && missedRef.current) {
        missedRef.current = false;
        await ask(`Your diff did not apply. The current SQL is exactly:\n${docRef.current}\nCall apply_sql_diff again with a hunk whose context and removed lines match it character for character, then stop.`);
      }
      setStage("verify");
      let result = await verify(caseId, before);
      if (result.status === "no_change" && previous && before > 0) {
        result = previous;
        setUnchanged(true);
      }
      verdictRef.current = result;
      setVerdict(result);
      setStage("idea");
      await ask(`Verification result: ${describe(result)} Call state_next_idea once with one concrete next step that follows from this result. Do not apply another diff.`);
      if (!ideaRef.current) await ask("Call state_next_idea once now. Do not apply another diff.");
    } catch (err) {
      setFault(err instanceof Error ? err.message : "The agent request failed.");
    } finally {
      setStage("done");
      runLock.current = false;
    }
  }

  function begin(query: string) {
    docRef.current = query;
    cutsRef.current = 0;
    verdictRef.current = null;
    setOriginal(query);
    setCurrent(query);
    setNotes([]);
    agent.setMessages([]);
  }

  function start() {
    const query = draft.trim();
    const rejected = assertSelect(query);
    if (!query || rejected) {
      setFault(rejected ?? "");
      return;
    }
    begin(query);
    void cycle(`${SCHEMA}

Make this PostgreSQL SELECT faster without changing its result rows, including NULL behaviour. Change it only with apply_sql_diff, in small hunks, each against the SQL the previous tool result returns. If it is already as good as it gets, apply no diff. When the cuts are done, stop. The canvas verifies the result and then asks you for a next idea. Do not paste a replacement query. Do not claim a speedup.

${query}`);
  }

  /** Groq-free path: rules → local Ollama coder via /api/optimize, then same verify. */
  async function startLocal() {
    const query = draft.trim();
    const rejected = assertSelect(query);
    if (!query || rejected) {
      setFault(rejected ?? "");
      return;
    }
    if (runLock.current) return;
    runLock.current = true;
    begin(query);
    ideaRef.current = false;
    setIdea(null);
    setVerdict(null);
    setUnchanged(false);
    setFault("");
    const caseId = cases.find((item) => normalize(item.sql) === normalize(query))?.id;
    try {
      setStage("rewrite");
      setNotes(["Local cascade (rules → Ollama coder)…"]);
      const response = await fetch("/api/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sql: query, system: "cascade-local" }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Optimize failed");
      const next = typeof data.result_sql === "string" ? data.result_sql : query;
      if (next !== query) {
        cutsRef.current += 1;
        docRef.current = next;
        setCurrent(next);
        const origin = data.candidates?.[0]?.origin || data.stages?.at(-1)?.system || "cascade-local";
        setNotes([`Applied ${origin}`]);
      } else {
        setNotes(["Cascade left the query unchanged"]);
      }
      setStage("verify");
      const result = await verify(caseId, 0);
      verdictRef.current = result;
      setVerdict(result);
      setIdea({
        title: data.changed ? "Inspect the local cascade cut" : "Try a harder query",
        detail: data.changed
          ? "This path used cascade-local (no Groq). Compare with the agent rewrite, or pursue another family."
          : "Rules and the local coder abstained. Pick a sargability or correlation example.",
      });
    } catch (err) {
      setFault(err instanceof Error ? err.message : "Local cascade failed.");
    } finally {
      setStage("done");
      runLock.current = false;
    }
  }

  function pursue() {
    if (!idea) return;
    void cycle(`Pursue this idea, only with apply_sql_diff against the current document, then stop: ${idea.title}. ${idea.detail} If no SQL change follows from it, apply no diff.`);
  }

  function reset() {
    if (runLock.current) return;
    agent.setMessages([]);
    docRef.current = "";
    setStage("compose");
    setOriginal("");
    setCurrent("");
    setNotes([]);
    setVerdict(null);
    verdictRef.current = null;
    setUnchanged(false);
    setIdea(null);
    setFault("");
  }

  const running = stage === "rewrite" || stage === "verify" || stage === "idea";
  const openCall = running
    ? [...messages].reverse().flatMap((message) => message.role === "assistant" ? [...(message.toolCalls ?? [])].reverse() : [])
      .find((call) => !messages.some((item) => item.role === "tool" && item.toolCallId === call.id))
    : undefined;
  const liveDiff = openCall?.function.name === "apply_sql_diff" ? jsonString(openCall.function.arguments, "unified_diff") : "";
  const liveNote = openCall?.function.name === "apply_sql_diff" ? jsonString(openCall.function.arguments, "note") : "";
  const liveIdea = openCall?.function.name === "state_next_idea"
    ? { title: jsonString(openCall.function.arguments, "title"), detail: jsonString(openCall.function.arguments, "detail") }
    : null;
  const preview = liveDiff ? applyUnifiedDiff(current, liveDiff) : null;

  const rows: DiffRow[] = preview?.ok ? lineDiff(original, preview.sql)
    : liveDiff ? [...lineDiff(original, current), ...incomingRows(liveDiff)]
    : lineDiff(original, current);

  const shownIdea = idea ?? (liveIdea && (liveIdea.title || liveIdea.detail) ? liveIdea : null);
  const factor = (value: number) => value >= 10 ? value.toFixed(0) : value.toFixed(1);
  const speedup = verdict?.speedup ? factor(verdict.speedup) : "";
  const slowdown = verdict?.speedup && verdict.speedup < 1 ? factor(1 / verdict.speedup) : "";
  const headline = stage === "compose" ? "Make a query faster."
    : stage === "rewrite" ? (liveNote || notes.at(-1) || "Reading the query")
    : stage === "verify" ? "Running both on Postgres"
    : unchanged && verdict ? "No SQL change for that idea."
    : verdict?.status === "accepted" ? `${speedup}× faster. Same rows.`
    : verdict?.status === "not_faster" ? (slowdown ? `Same rows, but ${slowdown}× slower.` : `Same rows. Only ${speedup}× faster.`)
    : verdict?.status === "incorrect" ? "Rejected. The rows changed."
    : verdict?.status === "no_change" ? (missedRef.current ? "The diff didn't land." : "Already in good shape.")
    : verdict?.status === "unverified" ? (notes.at(-1) || "Rewritten, not verified")
    : "Something went wrong";
  const status = stage === "rewrite" ? (liveDiff ? "Writing a diff" : fault ? "That hunk missed. Trying again" : "Thinking")
    : stage === "verify" ? "Checking rows on 5 fixture databases, then timing 5 paired runs"
    : stage === "idea" ? "Deciding what to try next"
    : "";

  return (
    <div className="sd">
      <header className="sd-top">
        <button className="sd-brand" onClick={reset} disabled={running}><Mark /> Database Surgeon</button>
        <button className="sd-link" onClick={onOpenLab}>Lab</button>
      </header>

      <main className={"sd-main " + (stage === "compose" ? "is-compose" : "is-run")}>
        <h1 key={headline} className="sd-fade">{headline}</h1>
        {stage === "compose" && <p className="sd-lede">An open model rewrites it, one diff at a time. Postgres decides whether the rewrite earned its place.</p>}

        {stage === "compose" ? (
          <div className="sd-card">
            <label className="sr-only" htmlFor="sd-query">PostgreSQL query</label>
            <textarea
              id="sd-query"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => { if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) start(); }}
              placeholder="Paste a SELECT…"
              spellCheck={false}
            />
            <div className="sd-card-foot">
              <div className="sd-examples">
                {EXAMPLES.map((example) => {
                  const found = cases.find((item) => item.id === example.id);
                  return found ? <button key={example.id} onClick={() => setDraft(found.sql)}>{example.label}</button> : null;
                })}
              </div>
              <div className="sd-actions">
                <button className="sd-link strong" type="button" disabled={!draft.trim()} onClick={() => void startLocal()}>Local cascade</button>
                <button className="sd-go" aria-label="Rewrite with agent" disabled={!draft.trim()} onClick={start}><ArrowUp size={18} /></button>
              </div>
            </div>
          </div>
        ) : (
          <>
            <Steps stage={stage} />
            <div className="sd-card sd-doc-card"><SqlDocument rows={rows} /></div>
            {status && <p key={status} className="sd-status sd-fade"><i />{status}</p>}
            {verdict && <Result verdict={verdict} />}
            {shownIdea && (
              <section className="sd-idea">
                <span>Next</span>
                <h2>{shownIdea.title}</h2>
                <p>{shownIdea.detail}</p>
                {stage === "done" && idea && <button className="sd-link strong" onClick={pursue}>Pursue <ArrowRight size={15} /></button>}
              </section>
            )}
            {stage === "done" && <button className="sd-link sd-again" onClick={reset}>New query</button>}
          </>
        )}
        {fault && !running && <p className="sd-fault" role="alert">{fault}</p>}
      </main>
    </div>
  );
}
