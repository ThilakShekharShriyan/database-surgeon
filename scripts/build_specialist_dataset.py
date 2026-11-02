#!/usr/bin/env python3
"""Build a Fireworks LoRA SFT (+ DPO) set from verified harness wins.

Crazy-but-safe training story for the hackathon:
  distill the *surgical harness* into a specialist — never train on frontier
  outputs, never train on held-out templates.

Sources (dev split JSONL only):
  - existing teacher SFT (.local/training/sft.jsonl)
  - accepted rewrites from open-harness / oss20b-harness / rules-only
  - DPO: harness-safe answer vs open-raw incorrect on the same case id
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".local" / "training"
CASES = ROOT / "benchmarks" / "eval_v2" / "cases.jsonl"
RUNS = ROOT / "benchmarks" / "eval_v2" / "runs"

SYSTEM = """You optimize PostgreSQL 16 SELECT queries. Reply with JSON {"sql": ..., "rationale": ...}.
The rewrite must return exactly the same rows on every possible database that satisfies the schema.
If you are not confident that a rewrite is both equivalent and faster, return the original SQL unchanged."""


def load_cases():
    by_id = {}
    for line in CASES.read_text().splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        if case.get("split") == "heldout":
            continue  # never train on held-out
        by_id[case["id"]] = case
    return by_id


def load_run(name):
    path = RUNS / name / "dev_t0.jsonl"
    if not path.exists():
        return {}
    rows = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows[row["case"]] = row
    return rows


def messages(case, answer_sql, rationale):
    user = (
        f"Schema family: {case.get('family')}\n"
        f"Optimize this query. Return JSON only.\n\n{case['sql']}"
    )
    assistant = json.dumps({"sql": answer_sql, "rationale": rationale})
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]


def main():
    cases = load_cases()
    harness_names = ["open-harness", "oss20b-harness", "rules-only"]
    harness = {}
    for name in harness_names:
        for cid, row in load_run(name).items():
            if row.get("outcome") != "accepted":
                continue
            # prefer open-harness over others when multiple
            if cid not in harness or name == "open-harness":
                harness[cid] = (name, row)

    raw = load_run("open-raw")
    sft, dpo, seen = [], [], set()

    # 1) Prior teacher SFT
    prior = OUT / "sft.jsonl"
    if prior.exists():
        for line in prior.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = json.dumps(row.get("messages"), sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            sft.append({"messages": row["messages"], "meta": {"source": "teacher", **(row.get("meta") or {})}})

    # 2) Verified harness wins
    for cid, (src, row) in harness.items():
        case = cases.get(cid)
        if not case:
            continue
        msgs = messages(
            case,
            row["result_sql"],
            f"Verified equivalent + faster ({src}; speedup={row.get('speedup')}).",
        )
        key = json.dumps(msgs, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        sft.append({"messages": msgs, "meta": {"source": src, "case": cid, "changed": True}})

        # 3) DPO: raw incorrect vs harness accepted
        bad = raw.get(cid)
        if bad and bad.get("outcome") == "incorrect" and bad.get("result_sql"):
            dpo.append({
                "prompt": msgs[:2],
                "chosen": msgs[2]["content"],
                "rejected": json.dumps({"sql": bad["result_sql"], "rationale": "Raw rewrite."}),
                "meta": {"case": cid, "source": "raw-vs-harness"},
            })

    OUT.mkdir(parents=True, exist_ok=True)
    fw = OUT / "fireworks_sft.jsonl"
    fw.write_text("".join(json.dumps({"messages": r["messages"]}) + "\n" for r in sft))
    (OUT / "specialist_sft.jsonl").write_text("".join(json.dumps(r) + "\n" for r in sft))
    (OUT / "specialist_dpo.jsonl").write_text("".join(json.dumps(r) + "\n" for r in dpo))
    stats = {
        "sft_rows": len(sft),
        "dpo_pairs": len(dpo),
        "harness_wins_used": len(harness),
        "fireworks_file": str(fw),
        "note": "Dev-only; no held-out templates. Ready for Fireworks managed LoRA SFT.",
    }
    (OUT / "specialist_stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
