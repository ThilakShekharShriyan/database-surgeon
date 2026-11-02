"""Quality, safety, latency and cost for one system on one split, with CIs.

Each trial is one full pass over the split. Per-case values are averaged across
trials before bootstrapping over cases, so the interval reflects both sampling
noise and the finite case set. Paired differences resample the same cases for
both systems.
"""

import math
import random
import statistics
from collections import defaultdict

SAFE = ("no_change", "accepted", "not_faster")


def _speed(record):
    if record["outcome"] in ("accepted", "not_faster", "regression"):
        return max(0.1, record.get("speedup") or 0.1)
    return 1.0


def _pct(values, q):
    if not values:
        return None
    values = sorted(values)
    index = min(len(values) - 1, max(0, math.ceil(q * len(values)) - 1))
    return values[index]


def per_case(trials):
    """trials: list of lists of records -> {case_id: averaged per-case stats}."""
    grouped = defaultdict(list)
    for trial in trials:
        for record in trial:
            grouped[record["case"]].append(record)
    result = {}
    for case_id, records in grouped.items():
        n = len(records)
        result[case_id] = {
            "accepted": sum(r["outcome"] == "accepted" for r in records) / n,
            "incorrect": sum(r["outcome"] == "incorrect" for r in records) / n,
            "unsafe": sum(r["outcome"] not in SAFE for r in records) / n,
            "log_speed": sum(math.log(_speed(r)) for r in records) / n,
            "kind": records[0]["kind"], "family": records[0]["family"],
        }
    return result


def bootstrap(values, iterations=2000, seed=7):
    if not values:
        return None, None
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(iterations))
    return means[int(0.025 * iterations)], means[int(0.975 * iterations) - 1]


def summarize(trials):
    records = [r for trial in trials for r in trial]
    if not records:
        return {}
    cases = per_case(trials)
    outcomes = defaultdict(int)
    for r in records:
        outcomes[r["outcome"]] += 1
    n = len(records)
    latencies = [r["latency_ms"] for r in records]
    llm_latencies = [r.get("llm_ms") or 0 for r in records]
    verify_latencies = [r.get("verify_ms") or 0 for r in records]
    costs = [r["cost_usd"] for r in records]
    known_cost = all(c is not None for c in costs)
    proposed_wrong = sum(sum(1 for c in r.get("candidates", []) if c.get("stage") == "check") for r in records)
    accepted = [c["accepted"] for c in cases.values()]
    incorrect = [c["incorrect"] for c in cases.values()]
    log_speed = [c["log_speed"] for c in cases.values()]
    decoys = [c for c in cases.values() if c["kind"] == "decoy"]
    traps = [c for c in cases.values() if c["kind"] == "trap"]
    summary = {
        "cases": len(cases), "trials": len(trials),
        "outcomes": {k: round(v / n, 4) for k, v in sorted(outcomes.items())},
        "accepted_rate": statistics.mean(accepted), "accepted_ci95": bootstrap(accepted),
        "incorrect_returned_rate": statistics.mean(incorrect), "incorrect_ci95": bootstrap(incorrect),
        "incorrect_returned_count": outcomes["incorrect"],
        "wrong_candidates_caught": proposed_wrong,
        "geomean_speedup": math.exp(statistics.mean(log_speed)),
        "geomean_speedup_ci95": tuple(math.exp(v) for v in bootstrap(log_speed)),
        "decoy_safe_rate": statistics.mean(1 - c["unsafe"] for c in decoys) if decoys else None,
        "trap_incorrect_rate": statistics.mean(c["incorrect"] for c in traps) if traps else None,
        "latency_p50_ms": _pct(latencies, 0.5), "latency_p95_ms": _pct(latencies, 0.95),
        "optimizer_llm_p50_ms": _pct(llm_latencies, 0.5),
        "optimizer_llm_p95_ms": _pct(llm_latencies, 0.95),
        "optimizer_verify_p50_ms": _pct(verify_latencies, 0.5),
        "optimizer_verify_p95_ms": _pct(verify_latencies, 0.95),
        "cost_per_case_usd": statistics.mean(costs) if known_cost else None,
        "cost_known": known_cost,
        "calls_per_case": statistics.mean(r["calls"] for r in records),
        "output_tokens_per_case": statistics.mean(r.get("output_tokens", 0) for r in records),
        "errors_per_case": statistics.mean(r.get("errors", 0) for r in records),
    }
    families = defaultdict(list)
    for c in cases.values():
        families[c["family"]].append(c["accepted"])
    summary["accepted_by_family"] = {f: round(statistics.mean(v), 3) for f, v in sorted(families.items())}
    return summary


def paired_difference(trials_a, trials_b, metric="accepted", iterations=2000, seed=11):
    """Mean of (A - B) over shared cases with a paired bootstrap 95% CI."""
    a, b = per_case(trials_a), per_case(trials_b)
    shared = sorted(set(a) & set(b))
    diffs = [a[c][metric] - b[c][metric] for c in shared]
    if not diffs:
        return None
    low, high = bootstrap(diffs, iterations, seed)
    return {"mean": statistics.mean(diffs), "ci95": (low, high), "cases": len(diffs)}
