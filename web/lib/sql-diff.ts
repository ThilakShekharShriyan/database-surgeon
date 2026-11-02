export type ApplyOk = {
  ok: true;
  sql: string;
  added: string[];
  removed: string[];
  freshLineIndexes: number[];
};

export type ApplyResult = ApplyOk | { ok: false; error: string };

type HunkLine = { kind: "add" | "del" | "ctx"; text: string };

const MAX_DIFF_CHARS = 8000;
const MAX_CHANGED_LINES = 40;

export function applyUnifiedDiff(source: string, diff: string): ApplyResult {
  if (!diff || !diff.trim()) return { ok: false, error: "The diff was empty." };
  if (diff.length > MAX_DIFF_CHARS) return { ok: false, error: "That diff is too large. Send a smaller hunk." };
  const hunks = parseHunks(diff);
  if (!hunks.length) {
    return { ok: false, error: "No hunk found. Start one with @@ and prefix lines with a space, + or -." };
  }

  let lines = splitLines(source);
  const originalCount = lines.length;
  const added: string[] = [];
  const removed: string[] = [];
  let contextLines = 0;
  let changed = 0;

  for (const hunk of hunks) {
    const oldLines = hunk.filter((line) => line.kind !== "add").map((line) => line.text);
    const newLines = hunk.filter((line) => line.kind !== "del").map((line) => line.text);
    if (!oldLines.length) {
      return { ok: false, error: "A hunk has nowhere to land. Keep at least one unchanged context line." };
    }
    const at = findSpan(lines, oldLines);
    if (at < 0) {
      return { ok: false, error: "A hunk did not match the current query. Diff against the latest SQL and keep context lines." };
    }
    lines = [...lines.slice(0, at), ...newLines, ...lines.slice(at + oldLines.length)];
    for (const line of hunk) {
      if (line.kind === "add") added.push(line.text);
      if (line.kind === "del") removed.push(line.text);
      if (line.kind === "ctx") contextLines += 1;
      else changed += 1;
    }
  }

  if (changed === 0) return { ok: false, error: "The diff does not change any line." };
  if (changed > MAX_CHANGED_LINES) return { ok: false, error: "That cut is too wide. Change fewer lines." };
  if (originalCount > 1 && contextLines === 0 && removed.length >= originalCount) {
    return { ok: false, error: "This replaces the whole query. Keep the unchanged lines as context." };
  }

  const sql = lines.join("\n").trim();
  if (!sql) return { ok: false, error: "The diff erased the query." };
  if (sql === source.trim()) return { ok: false, error: "The query is unchanged." };
  return { ok: true, sql, added, removed, freshLineIndexes: freshLines(splitLines(source), lines) };
}

export function assertSelect(sql: string): string | null {
  const body = sql.trim().replace(/;+\s*$/, "");
  if (!body) return "The query is empty.";
  if (body.includes(";")) return "Keep a single statement.";
  if (!/^(select|with)\b/i.test(body)) return "The document has to stay a SELECT.";
  if (/\b(insert|update|delete|drop|alter|create|grant|revoke|copy|truncate|call|do)\b/i.test(body)) {
    return "Only a SELECT can land on this canvas.";
  }
  return null;
}

export type DiffRow = { kind: "add" | "del" | "ctx"; text: string };

export function lineDiff(before: string, after: string): DiffRow[] {
  const left = splitLines(before);
  const right = splitLines(after);
  const width = right.length + 1;
  const scores: number[] = Array((left.length + 1) * width).fill(0);
  const at = (row: number, column: number) => row * width + column;
  for (let row = left.length - 1; row >= 0; row -= 1) {
    for (let column = right.length - 1; column >= 0; column -= 1) {
      scores[at(row, column)] = left[row] === right[column]
        ? scores[at(row + 1, column + 1)] + 1
        : Math.max(scores[at(row + 1, column)], scores[at(row, column + 1)]);
    }
  }
  const rows: DiffRow[] = [];
  let row = 0;
  let column = 0;
  while (row < left.length && column < right.length) {
    if (left[row] === right[column]) {
      rows.push({ kind: "ctx", text: left[row] });
      row += 1;
      column += 1;
    } else if (scores[at(row + 1, column)] >= scores[at(row, column + 1)]) {
      rows.push({ kind: "del", text: left[row] });
      row += 1;
    } else {
      rows.push({ kind: "add", text: right[column] });
      column += 1;
    }
  }
  while (row < left.length) rows.push({ kind: "del", text: left[row++] });
  while (column < right.length) rows.push({ kind: "add", text: right[column++] });
  return rows;
}

function splitLines(sql: string): string[] {
  const normalized = sql.replace(/\r\n/g, "\n").replace(/\n+$/, "");
  return normalized.length ? normalized.split("\n") : [];
}

function parseHunks(diff: string): HunkLine[][] {
  const hunks: HunkLine[][] = [];
  let current: HunkLine[] | null = null;
  for (const line of diff.replace(/\r\n/g, "\n").split("\n")) {
    if (line.startsWith("@@")) {
      if (current?.length) hunks.push(current);
      current = [];
      continue;
    }
    if (line.startsWith("---") || line.startsWith("+++") || line.startsWith("diff ") || line.startsWith("index ")) continue;
    if (line.startsWith("\\")) continue;
    const kind = line.startsWith("+") ? "add" : line.startsWith("-") ? "del" : line.startsWith(" ") ? "ctx" : null;
    if (!kind) continue;
    if (!current) current = [];
    current.push({ kind, text: line.slice(1) });
  }
  if (current?.length) hunks.push(current);
  return hunks;
}

function findSpan(lines: string[], needle: string[]): number {
  const exact = matchAt(lines, needle, (left, right) => left === right);
  if (exact >= 0) return exact;
  return matchAt(lines, needle, (left, right) => left.trim() === right.trim());
}

function matchAt(lines: string[], needle: string[], same: (left: string, right: string) => boolean): number {
  if (!needle.length || needle.length > lines.length) return -1;
  outer: for (let index = 0; index <= lines.length - needle.length; index += 1) {
    for (let offset = 0; offset < needle.length; offset += 1) {
      if (!same(lines[index + offset], needle[offset])) continue outer;
    }
    return index;
  }
  return -1;
}

function freshLines(before: string[], after: string[]): number[] {
  const fresh: number[] = [];
  let left = 0;
  let right = 0;
  while (right < after.length) {
    if (left < before.length && before[left] === after[right]) {
      left += 1;
      right += 1;
      continue;
    }
    const ahead = before.indexOf(after[right], left);
    if (ahead === -1) {
      fresh.push(right);
      right += 1;
      continue;
    }
    left = ahead + 1;
    right += 1;
  }
  return fresh;
}
