import { readFile } from "node:fs/promises";
import path from "node:path";
import type { ResearchSnapshot } from "@/lib/research-types";
export const dynamic = "force-dynamic";
export async function GET() {
  try {
    const data: ResearchSnapshot = JSON.parse(await readFile(path.join(process.cwd(), "public/research/snapshot.json"), "utf8"));
    const result = Object.fromEntries(Object.entries(data.splits).map(([split, value]) => [split, {
      split, systems: value.systems, note: "Saved synthetic-fixture evidence; partial results are labeled.",
      pareto_safe: []
    }]));
    return Response.json(result);
  } catch {
    return Response.json({error:"Research snapshot unavailable. Run scripts/export_research.py."}, {status:503});
  }
}
