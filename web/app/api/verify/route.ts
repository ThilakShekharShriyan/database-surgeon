import { sameOrigin } from "@/lib/environment";
export async function POST(request: Request) {
  if (!sameOrigin(request)) return Response.json({error:"Cross-origin requests are not allowed."},{status:403});
  try {
    const text = await request.text();
    if (text.length > 8192) return Response.json({error:"Request too large."},{status:413});
    const response = await fetch("http://127.0.0.1:8765/verify", {method:"POST",headers:{"Content-Type":"application/json"},body:text,signal:AbortSignal.timeout(90000)});
    return Response.json(await response.json(),{status:response.status});
  } catch { return Response.json({error:"Could not reach the evaluator."},{status:503}); }
}
