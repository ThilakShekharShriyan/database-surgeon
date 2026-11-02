export const dynamic = "force-dynamic";
export async function GET() {
  try {
    const response = await fetch("http://127.0.0.1:8765/snapshot", { cache: "no-store", signal: AbortSignal.timeout(8000) });
    return Response.json(await response.json(), { status: response.status });
  } catch {
    return Response.json({ error: "The evaluator API is offline. Start python3 -m surgeon.service on port 8765." }, { status: 503 });
  }
}
