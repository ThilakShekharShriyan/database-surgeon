#!/usr/bin/env python3
"""Paired McNemar + template-cluster bootstrap for sealed eval_v2 comparisons.

Writes benchmarks/eval_v2/results/paired_stats.json used by docs/FORGE_RESEARCH.md.
"""

from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "benchmarks" / "eval_v2" / "runs"
CASES = ROOT / "benchmarks" / "eval_v2" / "cases.jsonl"
OUT = ROOT / "benchmarks" / "eval_v2" / "results" / "paired_stats.json"

PAIRS = [
    ("open-harness", "open-raw"),
    ("open-harness", "frontier-raw"),
    ("open-harness", "rules-only"),
    ("fw-fast-harness", "fw-fast-raw"),
]


def load_run(name: str, split: str = "dev") -> dict:
    path = RUNS / name / f"{split}_t0.jsonl"
    if not path.exists():
        return {}
    return {
        json.loads(line)["case"]: json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    }


def mcnemar(a_flags: list[bool], b_flags: list[bool]) -> dict:
    a_only = b_only = both = neither = 0
    for x, y in zip(a_flags, b_flags):
        if x and y:
            both += 1
        elif x and not y:
            a_only += 1
        elif y and not x:
            b_only += 1
        else:
            neither += 1
    n = a_only + b_only
    if n == 0:
        p = 1.0
    else:
        p = min(1.0, 2 * sum(math.comb(n, k) for k in range(min(a_only, b_only) + 1)) / (1 << n))
    return {
        "a_only": a_only,
        "baseline_only": b_only,
        "both": both,
        "neither": neither,
        "discordant": n,
        "p_value": p,
    }


def cluster_bootstrap_gap(
    ids: list[str],
    a: dict,
    b: dict,
    templates: dict[str, str],
    pred,
    iterations: int = 5000,
    seed: int = 11,
) -> dict:
    clusters: dict[str, list[float]] = defaultdict(list)
    for i in ids:
        clusters[templates[i]].append((1.0 if pred(a[i]) else 0.0) - (1.0 if pred(b[i]) else 0.0))
    keys = list(clusters)
    rng = random.Random(seed)
    gaps = []
    for _ in range(iterations):
        sample = [rng.choice(keys) for _ in keys]
        vals = [v for k in sample for v in clusters[k]]
        gaps.append(sum(vals) / len(vals))
    gaps.sort()
    return {
        "mean": sum(gaps) / len(gaps),
        "ci95": [gaps[int(0.025 * iterations)], gaps[int(0.975 * iterations) - 1]],
        "clusters": len(keys),
        "iterations": iterations,
    }


def compare_pair(a_name: str, b_name: str, cases: dict, split: str = "dev") -> dict | None:
    a, b = load_run(a_name, split), load_run(b_name, split)
    ids = sorted(set(a) & set(b) & set(cases))
    if len(ids) < 10:
        return None
    templates = {i: cases[i].get("template") or cases[i].get("family") or i for i in ids}

    def accepted(r):
        return r.get("outcome") == "accepted"

    def incorrect(r):
        return r.get("outcome") == "incorrect"

    acc_a = [accepted(a[i]) for i in ids]
    acc_b = [accepted(b[i]) for i in ids]
    inc_a = [incorrect(a[i]) for i in ids]
    inc_b = [incorrect(b[i]) for i in ids]
    return {
        "system": a_name,
        "baseline": b_name,
        "split": split,
        "pairs": len(ids),
        "accept_rate_a": sum(acc_a) / len(ids),
        "accept_rate_b": sum(acc_b) / len(ids),
        "incorrect_count_a": sum(inc_a),
        "incorrect_count_b": sum(inc_b),
        "mcnemar_accepted": mcnemar(acc_a, acc_b),
        "mcnemar_incorrect": mcnemar(inc_a, inc_b),
        "bootstrap_accept_gap": cluster_bootstrap_gap(ids, a, b, templates, accepted),
    }


def main() -> None:
    cases = {
        c["id"]: c
        for line in CASES.read_text().splitlines()
        if line.strip()
        for c in [json.loads(line)]
        if c.get("split") == "dev"
    }
    results = []
    for a, b in PAIRS:
        row = compare_pair(a, b, cases)
        if row:
            results.append(row)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_by": "scripts/compute_paired_stats.py",
        "note": "Exact two-sided McNemar on discordant pairs; bootstrap resamples templates/families.",
        "comparisons": results,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
