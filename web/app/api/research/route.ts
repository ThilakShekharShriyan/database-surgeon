import { readFile } from "node:fs/promises";
import path from "node:path";
export const dynamic = "force-dynamic";
export async function GET() {
  try {
    const body = await readFile(path.join(process.cwd(), "public/research/snapshot.json"), "utf8");
    return new Response(body, { headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ error: "Research snapshot unavailable. Run .venv/bin/python scripts/export_research.py from the project root." }, { status: 503 });
  }
}
