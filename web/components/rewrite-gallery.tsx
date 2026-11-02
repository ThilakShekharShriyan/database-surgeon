"use client";

import type { ResearchCase, ResearchRecord } from "@/lib/research-types";
import { money, seconds } from "./research-charts";

export type RewriteRow = {
  case: ResearchCase;
  record: ResearchRecord;
};

function fmtMs(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return "—";
  if (v < 1) return `${v.toFixed(3)} ms`;
  if (v < 1000) return `${v.toFixed(2)} ms`;
  return `${(v / 1000).toFixed(2)} s`;
}

export function RewriteGallery({
  rows,
  systemLabel,
  onSelect,
  selectedId,
}: {
  rows: RewriteRow[];
  systemLabel: string;
  onSelect?: (id: string) => void;
  selectedId?: string;
}) {
  if (!rows.length) {
    return <p className="r-empty">No accepted rewrites with measured speedup for this system.</p>;
  }
  return (
    <div className="r-rewrite-gallery">
      {rows.map(({ case: c, record: r }) => {
        const orig = r.verdict?.original_ms ?? c.original_ms;
        const cand = r.verdict?.candidate_ms ?? null;
        const active = selectedId === c.id;
        return (
          <article key={c.id} className={`r-rewrite-card${active ? " active" : ""}`}>
            <header>
              <div>
                <small>{c.family.replaceAll("_", " ")} · {c.template}</small>
                <h3>{c.id.replaceAll("_", " ")}</h3>
              </div>
              <div className="r-rewrite-badges">
                <span className="r-badge accent">{(r.speedup ?? 0).toFixed(2)}× SQL</span>
                <span className="r-badge">{r.outcome}</span>
              </div>
            </header>
            <div className="r-sql-grid r-rewrite-sql">
              <div>
                <span className="r-sql-label">Original</span>
                <pre><code>{c.sql}</code></pre>
              </div>
              <div>
                <span className="r-sql-label">Rewrite · {systemLabel}</span>
                <pre><code>{r.result_sql || "—"}</code></pre>
              </div>
            </div>
            <div className="r-rewrite-params">
              <div><span>Original runtime</span><strong>{fmtMs(orig)}</strong></div>
              <div><span>Rewrite runtime</span><strong>{fmtMs(cand)}</strong></div>
              <div><span>SQL speedup</span><strong>{r.speedup?.toFixed(2) ?? "—"}×</strong></div>
              <div><span>Reduction</span><strong>{r.verdict?.reduction != null ? `${(r.verdict.reduction * 100).toFixed(1)}%` : "—"}</strong></div>
              <div><span>API cost</span><strong>{money(r.cost_usd, 4)}</strong></div>
              <div><span>Optimizer</span><strong>{seconds(r.latency_ms)}</strong></div>
              <div><span>LLM time</span><strong>{r.llm_ms != null ? seconds(r.llm_ms) : "—"}</strong></div>
              <div><span>Verify</span><strong>{r.verify_ms != null ? seconds(r.verify_ms) : "—"}</strong></div>
              <div><span>Calls</span><strong>{r.calls}</strong></div>
              <div><span>Out tokens</span><strong>{r.output_tokens}</strong></div>
            </div>
            {onSelect && (
              <button type="button" className="r-button" onClick={() => onSelect(c.id)}>
                Open in query evidence
              </button>
            )}
          </article>
        );
      })}
    </div>
  );
}

export function pickTopRewrites(
  cases: ResearchCase[],
  records: ResearchRecord[],
  limit = 6,
): RewriteRow[] {
  const byId = new Map(cases.map((c) => [c.id, c]));
  return records
    .filter((r) => r.outcome === "accepted" && (r.speedup ?? 0) >= 1.25 && byId.has(r.case))
    .sort((a, b) => (b.speedup ?? 0) - (a.speedup ?? 0))
    .slice(0, limit)
    .map((record) => ({ case: byId.get(record.case)!, record }));
}
