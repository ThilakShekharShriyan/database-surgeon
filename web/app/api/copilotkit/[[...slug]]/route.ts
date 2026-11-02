import { BuiltInAgent, CopilotRuntime, InMemoryAgentRunner, createCopilotRuntimeHandler } from "@copilotkit/runtime/v2";
import { createOpenAI } from "@ai-sdk/openai";
import { loadProjectEnvironment, sameOrigin } from "@/lib/environment";
export const runtime = "nodejs";
export const maxDuration = 120;
loadProjectEnvironment();
const groqKeys = [...new Set(Object.keys(process.env)
  .filter(name=>/^GROQ_API_KEY(?:_?\d+)?$/.test(name))
  .sort((a,b)=>(Number(b.match(/\d+$/)?.[0])||0)-(Number(a.match(/\d+$/)?.[0])||0))
  .map(name=>process.env[name]).filter((value):value is string=>!!value))].slice(0,4);
let keyCursor=0;
const rotatingFetch: typeof fetch = async (input,init) => {
  for(let attempt=0;attempt<Math.max(1,groqKeys.length);attempt++){
    const headers=new Headers(init?.headers);
    if(groqKeys.length) headers.set("Authorization","Bearer "+groqKeys[(keyCursor+attempt)%groqKeys.length]);
    const response=await fetch(input,{...init,headers});
    if(response.status===429 && attempt+1<groqKeys.length){await response.body?.cancel();continue;}
    keyCursor=(keyCursor+attempt+1)%Math.max(1,groqKeys.length);
    return response;
  }
  throw new Error("All configured Groq credential slots are rate-limited.");
};
const groq = createOpenAI({ apiKey: groqKeys[0], baseURL: "https://api.groq.com/openai/v1", fetch:rotatingFetch });
const agent = new BuiltInAgent({
  model: groq.chat("openai/gpt-oss-20b"),
  maxSteps: 6, maxOutputTokens: 2048, maxRetries: 0, urlDownload: "disabled",
  prompt: `You are the Database Surgeon agent.

On the demo canvas, apply_sql_diff and state_next_idea are available. Change the open PostgreSQL SELECT only by calling apply_sql_diff with a unified diff against the current document. Never paste a replacement query. Use small hunks with context lines that start with a space, headers --- query and +++ query, and @@ ranges. Each tool result is the document the next diff must match. Preserve the result rows exactly, including NULL behaviour and duplicates. After the last diff, stop. The canvas then verifies the rewrite on Postgres and asks you for the next idea; only then call state_next_idea exactly once. The idea follows from the verification result: a second cut, a semantic risk such as NULL or ordering, or a measurement the local lab could run. Never claim a speedup the verification did not report.

In the lab, read_evidence and show_query are available. Read current experiment evidence before any performance claim. Use show_query to open a case. Missing costs are unknown.

All data is development data, including public SQL on synthetic microfixtures. No held-out frontier win is established. You cannot execute SQL, launch a benchmark, change files, or deploy a model. After this demo, the project still needs Fireworks capability checks when access arrives, then held-out templates and repeated trials before any quality claim. Keep answers concise.`,
});
const copilotRuntime = new CopilotRuntime({ agents: {default:agent}, runner:new InMemoryAgentRunner(), identifyUser:()=>({id:"local-workbench",name:"Local researcher"}) });
const handler = createCopilotRuntimeHandler({runtime:copilotRuntime,basePath:"/api/copilotkit"});
export const GET = handler;
export async function POST(request: Request) {
  if (!sameOrigin(request)) return Response.json({error:"Cross-origin requests are not allowed."},{status:403});
  const reader = request.body?.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  if (reader) {
    while (true) {
      const next = await reader.read();
      if (next.done) break;
      total += next.value.byteLength;
      if (total > 65536) { await reader.cancel(); return Response.json({error:"Chat request exceeds 64 KiB."},{status:413}); }
      chunks.push(next.value);
    }
  }
  const body = Buffer.concat(chunks).toString("utf8");
  try {
    const parsed = JSON.parse(body || "{}");
    if ((parsed.messages?.length || 0) > 40 || (parsed.tools?.length || 0) > 8 || (parsed.context?.length || 0) > 8) {
      return Response.json({error:"Chat context exceeds the local session limit."},{status:400});
    }
  } catch { return Response.json({error:"Invalid chat request."},{status:400}); }
  request = new Request(request.url, {method:request.method, headers:request.headers, body});
  if (!process.env.GROQ_API_KEY) return Response.json({error:"GROQ_API_KEY is not configured."},{status:503});
  return handler(request);
}
export const PATCH = POST;
export const DELETE = POST;
