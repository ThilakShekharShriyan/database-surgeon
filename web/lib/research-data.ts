import "server-only";
import { readFile } from "node:fs/promises";
import path from "node:path";
import type { ResearchSnapshot } from "./research-types";

export async function loadResearchSnapshot(): Promise<ResearchSnapshot | null> {
  try {
    return JSON.parse(await readFile(path.join(process.cwd(), "public/research/snapshot.json"), "utf8"));
  } catch {
    return null;
  }
}
