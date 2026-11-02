import { sameOrigin } from "@/lib/environment";
import { readFile } from "node:fs/promises";
import path from "node:path";
import type { ResearchSnapshot } from "@/lib/research-types";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  if (!sameOrigin(request)) return Response.json({error:"Local same-origin requests only."},{status:403});
  try {
    const body = await request.text();
    if (body.length > 8192) {
      return Response.json({ error: "Request too large." }, { status: 413 });
    }
    let input;
    try { input = JSON.parse(body); } catch { return Response.json({error:"Expected a JSON request."},{status:400}); }
    if (typeof input.sql !== "string" || !input.sql.trim()) return Response.json({error:"Expected SQL."},{status:400});
    if (input.replay === true) {
      // Replay is strictly offline and cannot fall through to inference.
      const snapshot: ResearchSnapshot = JSON.parse(await readFile(path.join(process.cwd(), "public/research/snapshot.json"), "utf8"));
      const normalize = (sql:string) => sql.trim().replace(/;+$/, "").trim().replace(/\s+/g," ");
      const query = snapshot.splits.dev.cases.find(c => normalize(c.sql) === normalize(input.sql));
      if (!query) return Response.json({error:"No recorded replay for this SQL. Restore a preset or explicitly choose Live."},{status:404});
      const preferred = ["open-harness", "rules-only", "fw-nemotron-harness"];
      const evidence = preferred.map(name => {
        const system = snapshot.splits.dev.systems.find(s => s.system === name);
        return {system:name, record:system?.records.find(r => r.case === query.id)};
      });
      const found = evidence.find(e => e.record?.outcome === "accepted") || evidence.find(e => e.record);
      if (!found?.record) return Response.json({error:"No saved system output for this preset."},{status:404});
      const r = found.record;
      const accepted = r.outcome === "accepted";
      const checked = ["accepted", "not_faster", "regression"].includes(r.outcome);
      return Response.json({
        system:`replay:${found.system}`, case_id:query.id, original_sql:query.sql, result_sql:r.result_sql,
        changed:normalize(query.sql)!==normalize(r.result_sql), cost_usd:r.cost_usd, latency_ms:r.latency_ms,
        wall_ms:0, replay:true, outcome:r.outcome, candidates:[], stage_models:[],
        stack:{label:"Saved evaluation snapshot; no model or database call"},
        note:`Recorded ${found.system} trial 0. Source: ${snapshot.source}. Saved API cost and optimizer latency describe the original run.`,
        pipeline:{accepted_origin:accepted?found.system:undefined,steps:[
          {id:"record",title:"Recorded optimizer output",status:accepted?"passed":"abstained",detail:`${found.system} · trial 0 · ${r.outcome}. This is saved evidence, not a fresh pipeline execution.`},
          {id:"equivalence",title:"Independent evaluator result",status:checked?"passed":r.outcome==="incorrect"?"failed":"skipped",detail:checked?"Output checks passed on eight fixture databases; finite checks are not a general equivalence proof.":r.verdict?.reason||"Original retained; no new equivalence claim."},
          {id:"speedup",title:"Recorded paired execution timing",status:accepted?"passed":"not_met",speedup:checked?r.speedup:undefined,reduction:r.verdict?.reduction,detail:accepted?`${r.verdict.original_ms?.toFixed(3)} ms original → ${r.verdict.candidate_ms?.toFixed(3)} ms candidate.`:"No accepted beneficial rewrite recorded."}
        ]}
      });
    }
    const response = await fetch("http://127.0.0.1:8765/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      signal: AbortSignal.timeout(180000),
    });
    return Response.json(await response.json(), { status: response.status });
  } catch {
    return Response.json({
      error: "The evaluator API is offline. Start python3 -m surgeon.service on port 8765.",
    }, { status: 503 });
  }
}
