"use client";

import { useRef } from "react";
import type { DiffRow } from "@/lib/sql-diff";

const STAGGER_MS = 70;

// New words fade in one after another. Each word keeps the delay it got when
// it first appeared, so later stream updates never restart or cut its fade.
export function SqlDocument({ rows }: { rows: DiffRow[] }) {
  const delays = useRef(new Map<string, number>());
  const seen = new Map<string, number>();
  let added = 0;
  let fresh = 0;
  return (
    <pre className="sd-doc">
      {rows.map((row) => {
        let key: string;
        let content: React.ReactNode = row.text || " ";
        if (row.kind === "add") {
          key = "add:" + added++;
          let position = 0;
          content = row.text.split(/(\s+)/).map((part) => {
            if (!part || /^\s+$/.test(part)) return part;
            const id = key + ":" + position++;
            let delay = delays.current.get(id);
            if (delay === undefined) {
              delay = fresh++ * STAGGER_MS;
              delays.current.set(id, delay);
            }
            return <span className="sd-word" key={id} style={{ animationDelay: delay + "ms" }}>{part}</span>;
          });
        } else {
          const base = row.kind + ":" + row.text;
          const count = seen.get(base) ?? 0;
          seen.set(base, count + 1);
          key = base + ":" + count;
        }
        return (
          <div className={"sd-line " + row.kind} key={key}>
            <span className="sd-sign">{row.kind === "add" ? "+" : row.kind === "del" ? "−" : ""}</span>
            <code>{content}</code>
          </div>
        );
      })}
    </pre>
  );
}
