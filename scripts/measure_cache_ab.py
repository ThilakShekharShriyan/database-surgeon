#!/usr/bin/env python3
"""Workload fingerprint cache A/B: hit-rate + estimated optimizer latency savings.

Compares:
  A) no-cache path — every miss would pay open-harness median llm_ms
  B) warm cache — fingerprint hits skip the LLM ($0 / ~0 llm_ms)

Writes .local/training/cache_ab_report.json and prints a short table.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from surgeon.eval.cases import load_cases  # noqa: E402
from surgeon.eval.workload_cache import WorkloadCache, seed_from_harness_runs  # noqa: E402


def _llm_p50(run_name: str = "open-harness") -> float:
    path = ROOT / "benchmarks" / "eval_v2" / "runs" / run_name / "dev_t0.jsonl"
    if not path.exists():
        return 2500.0
    vals = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("llm_ms") is not None:
            vals.append(float(row["llm_ms"]))
    return statistics.median(vals) if vals else 2500.0


def main() -> None:
    seed = seed_from_harness_runs()
    cache = WorkloadCache()
    cases, _ = load_cases("dev")
    llm_p50 = _llm_p50()
    hits_pos = hits_neg = misses = 0
    details = []
    for case in cases:
        hit = cache.lookup(case["sql"])
        if hit and hit.get("kind") == "positive":
            hits_pos += 1
            kind = "positive"
        elif hit and hit.get("kind") == "negative":
            hits_neg += 1
            kind = "negative"
        else:
            misses += 1
            kind = "miss"
        details.append({"case": case["id"], "kind": kind, "family": case.get("family")})
    n = len(cases)
    hit_rate = (hits_pos + hits_neg) / n if n else 0.0
    # A = always pay LLM; B = pay LLM only on miss (negatives also abstain without LLM)
    cost_a_ms = n * llm_p50
    cost_b_ms = misses * llm_p50
    report = {
        "seed": seed,
        "cases": n,
        "positive_hits": hits_pos,
        "negative_hits": hits_neg,
        "misses": misses,
        "hit_rate": round(hit_rate, 4),
        "open_harness_llm_p50_ms": round(llm_p50, 1),
        "optimizer_latency_no_cache_ms_sum": round(cost_a_ms, 1),
        "optimizer_latency_warm_cache_ms_sum": round(cost_b_ms, 1),
        "estimated_speedup_factor": round(cost_a_ms / cost_b_ms, 2) if cost_b_ms else None,
        "note": "Estimated from fingerprint coverage × open-harness median llm_ms; "
                "excludes verify time. Run cache-rules / open-harness-nocache for live A/B.",
        "details": details,
    }
    out = ROOT / ".local" / "training" / "cache_ab_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "details"}, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
