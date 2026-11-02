#!/usr/bin/env python3
"""All-round advantages scoreboard from eval_v2 runs → docs/ADVANTAGES.md + JSON."""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "benchmarks" / "eval_v2" / "runs"
OUT_MD = ROOT / "docs" / "ADVANTAGES.md"
OUT_JSON = ROOT / ".local" / "eval_v2" / "advantages_scoreboard.json"

# Pitch axes — every row we care about for judges.
FOCUS = [
    "rules-only",
    "frontier-raw",
    "open-raw",
    "open-harness",
    "open-harness-nocache",
    "cache-rules",
    "fw-fast-raw",
    "fw-fast-harness",
    "fw-nemotron-raw",
    "fw-nemotron-harness",
    "fw-gpt-oss-harness",
    "cascade-open-fw",
    "cascade-nemotron",
    "cascade-surgeon",
    "cascade-oss-fw",
    "oss20b-harness",
    "ollama-gpt-oss-20b-harness",
    "specialist-raw",
    "specialist-harness",
]


def _pct(vals, q):
    if not vals:
        return None
    vals = sorted(vals)
    return vals[min(len(vals) - 1, max(0, math.ceil(q * len(vals)) - 1))]


def summarize(name: str, split: str) -> dict | None:
    path = RUNS / name / f"{split}_t0.jsonl"
    need = 98 if split == "dev" else 73
    if not path.exists() or path.stat().st_size == 0:
        return None
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    if not rows:
        return None
    n = len(rows)
    c = Counter(r.get("outcome") for r in rows)
    lat = [float(r.get("latency_ms") or 0) for r in rows]
    llm = [float(r.get("llm_ms") or 0) for r in rows]
    ver = [float(r.get("verify_ms") or 0) for r in rows]
    costs = [r.get("cost_usd") for r in rows]
    known = all(x is not None for x in costs)
    speed = [float(r["speedup"]) for r in rows if r.get("outcome") == "accepted" and r.get("speedup")]
    return {
        "system": name,
        "split": split,
        "n": n,
        "need": need,
        "complete": n >= need,
        "accept": c.get("accepted", 0),
        "accept_rate": c.get("accepted", 0) / n,
        "wrong": c.get("incorrect", 0),
        "no_change": c.get("no_change", 0),
        "not_faster": c.get("not_faster", 0),
        "regression": c.get("regression", 0),
        "safe": c.get("incorrect", 0) == 0,
        "cost_per_case": (sum(float(x) for x in costs) / n) if known else None,
        "latency_p50_ms": _pct(lat, 0.5),
        "latency_p95_ms": _pct(lat, 0.95),
        "llm_p50_ms": _pct(llm, 0.5),
        "llm_p95_ms": _pct(llm, 0.95),
        "verify_p50_ms": _pct(ver, 0.5),
        "verify_p95_ms": _pct(ver, 0.95),
        "geomean_accept_speedup": math.exp(statistics.mean(math.log(max(0.1, s)) for s in speed)) if speed else None,
        "outcomes": dict(c),
    }


def load_cache_ab() -> dict:
    p = ROOT / ".local" / "training" / "cache_ab_report.json"
    return json.loads(p.read_text()) if p.exists() else {}


def advantage_bullets(rows: list[dict], cache: dict) -> list[str]:
    by = {r["system"]: r for r in rows if r["split"] == "dev" and r["complete"]}
    bullets = []
    oh = by.get("open-harness")
    raw = by.get("open-raw")
    fr = by.get("frontier-raw")
    rules = by.get("rules-only")
    fast = by.get("fw-fast-harness")
    nemo = by.get("fw-nemotron-harness")
    if oh and raw:
        bullets.append(
            f"**Safety cliff:** open-raw wrong={raw['wrong']} → open-harness wrong={oh['wrong']} "
            f"(accept {raw['accept_rate']*100:.1f}% → {oh['accept_rate']*100:.1f}%)."
        )
    if oh and fr:
        bullets.append(
            f"**Vs frontier:** open-harness accept {oh['accept_rate']*100:.1f}% / wrong={oh['wrong']} "
            f"vs frontier-raw {fr['accept_rate']*100:.1f}% / wrong={fr['wrong']}."
        )
    if rules and oh:
        bullets.append(
            f"**Harness > rules:** rules-only {rules['accept_rate']*100:.1f}% → open-harness "
            f"{oh['accept_rate']*100:.1f}% (same 0-wrong gate)."
        )
    if oh and oh.get("cost_per_case") is not None and fr and fr.get("cost_per_case"):
        bullets.append(
            f"**Cost:** open-harness ${oh['cost_per_case']:.4f}/case vs frontier ${fr['cost_per_case']:.4f}/case."
        )
    if oh and oh.get("latency_p50_ms") is not None:
        bullets.append(
            f"**Optimizer latency (open-harness):** p50={oh['latency_p50_ms']/1000:.1f}s "
            f"p95={oh['latency_p95_ms']/1000:.1f}s · LLM p50={oh['llm_p50_ms']/1000:.1f}s · "
            f"verify p50={oh['verify_p50_ms']/1000:.1f}s."
        )
    if cache.get("hit_rate") is not None:
        bullets.append(
            f"**Workload cache:** hit-rate {cache['hit_rate']*100:.1f}% → "
            f"~{cache.get('estimated_speedup_factor')}× estimated LLM latency with warm fingerprints."
        )
    if fast and fast["safe"]:
        bullets.append(
            f"**Flash harness:** fw-fast-harness accept {fast['accept_rate']*100:.1f}% / 0 wrong "
            f"(${(fast.get('cost_per_case') or 0):.4f}/case)."
        )
    if nemo and nemo["complete"]:
        bullets.append(
            f"**Nemotron harness (strict):** accept {nemo['accept_rate']*100:.1f}% / wrong={nemo['wrong']}."
        )
    held = [r for r in rows if r["split"] == "heldout" and r["system"] == "open-harness"]
    if held and held[0]["complete"]:
        h = held[0]
        bullets.append(
            f"**Held-out generalization:** open-harness {h['accept_rate']*100:.1f}% accept / wrong={h['wrong']} "
            f"on {h['n']} sealed held-out cases."
        )
    return bullets


def main() -> None:
    rows = []
    for split in ("dev", "heldout"):
        for name in FOCUS:
            s = summarize(name, split)
            if s:
                rows.append(s)
    cache = load_cache_ab()
    bullets = advantage_bullets(rows, cache)

    def fmt_row(r: dict) -> str:
        cost = "—" if r["cost_per_case"] is None else f"${r['cost_per_case']:.4f}"
        p50 = "—" if r["latency_p50_ms"] is None else f"{r['latency_p50_ms']/1000:.1f}"
        p95 = "—" if r["latency_p95_ms"] is None else f"{r['latency_p95_ms']/1000:.1f}"
        llm = "—" if r["llm_p50_ms"] is None else f"{r['llm_p50_ms']/1000:.1f}"
        done = "✓" if r["complete"] else f"{r['n']}/{r['need']}"
        return (
            f"| {r['system']} | {done} | {r['accept_rate']*100:.1f}% | {r['wrong']} | "
            f"{cost} | {p50} | {p95} | {llm} |"
        )

    dev = [r for r in rows if r["split"] == "dev"]
    held = [r for r in rows if r["split"] == "heldout"]
    lines = [
        "# All-round advantages — Database Surgeon",
        "",
        "Sealed eval_v2 scoreboard across **quality · safety · cost · optimizer latency · cache · cascade**.",
        "Accepted = equivalent on all eval fixtures (incl. null/skew) and ≥20% faster.",
        "",
        "**Narrative + paired tests:** [FORGE_RESEARCH.md](FORGE_RESEARCH.md) · regenerate stats: `scripts/compute_paired_stats.py`",
        "",
        "## Why we win (auto)",
        "",
    ]
    if bullets:
        lines += [f"- {b}" for b in bullets]
    else:
        lines.append("- _(Waiting on complete runs…)_")
    lines += [
        "",
        "## Dev (98 cases)",
        "",
        "| System | Done | Accept | Wrong | $/case | opt p50 s | opt p95 s | LLM p50 s |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in sorted(dev, key=lambda x: (-x["accept_rate"], x["wrong"], x["system"])):
        lines.append(fmt_row(r))
    lines += [
        "",
        "## Held-out (73 cases)",
        "",
        "| System | Done | Accept | Wrong | $/case | opt p50 s | opt p95 s | LLM p50 s |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    if held:
        for r in sorted(held, key=lambda x: (-x["accept_rate"], x["wrong"], x["system"])):
            lines.append(fmt_row(r))
    else:
        lines.append("| _(none yet)_ | | | | | | | |")
    lines += [
        "",
        "## Cache A/B",
        "",
        "```json",
        json.dumps({k: cache.get(k) for k in (
            "hit_rate", "positive_hits", "negative_hits", "misses",
            "estimated_speedup_factor", "open_harness_llm_p50_ms",
        ) if k in cache}, indent=2),
        "```",
        "",
        "## Reproduce",
        "",
        "```bash",
        "bash scripts/run_all_advantages_bench.sh",
        ".venv/bin/python scripts/write_advantages_scoreboard.py",
        "```",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n")
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({"rows": rows, "cache_ab": cache, "bullets": bullets}, indent=2) + "\n")
    print(OUT_MD)
    print(json.dumps({"dev_complete": sum(1 for r in dev if r["complete"]),
                      "held_complete": sum(1 for r in held if r["complete"]),
                      "bullets": len(bullets)}, indent=2))


if __name__ == "__main__":
    main()
