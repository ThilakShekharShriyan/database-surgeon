#!/usr/bin/env python3
"""Export a reproducible, credential-free UI snapshot. No DB or model calls."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from surgeon.eval.cases import load_cases
from surgeon.eval.comparison import compare
from surgeon.eval.metrics import summarize


def main():
    snapshot = {"generated_at": datetime.now(timezone.utc).isoformat(), "splits": {},
                "source": "benchmarks/eval_v2/runs/*/{split}_t*.jsonl",
                "comparison_trial": 0, "warnings": []}
    for split in ("dev", "heldout"):
        cases, digest = load_cases(split)
        expected = {c["id"] for c in cases}
        systems, runs = [], {}
        for directory in sorted((ROOT / "benchmarks/eval_v2/runs").iterdir()):
            if not directory.is_dir():
                continue
            trials = []
            for path in sorted(directory.glob(f"{split}_t*.jsonl")):
                rows = []
                for line in path.read_text().splitlines():
                    if not line.strip():
                        continue
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        snapshot["warnings"].append(f"Skipped incomplete record in {path.name} ({directory.name}).")
                trials.append(rows)
            if not any(trials):
                continue
            runs[directory.name] = trials
            summary = summarize(trials)
            summary.update(system=directory.name, expected_cases=len(cases), complete=all(
                len(t) == len(expected) and {r['case'] for r in t} == expected for t in trials))
            summary["records"] = [{k: r.get(k) for k in (
                "case", "outcome", "latency_ms", "cost_usd", "calls", "verify_ms", "llm_ms",
                "speedup", "result_sql", "verdict", "errors", "input_tokens", "output_tokens")}
                for t in trials for r in t if r.get("trial") == 0]
            summary["simulated"] = any(r.get("simulated") for t in trials for r in t)
            systems.append(summary)
        comparisons = {}
        for baseline in ("frontier-raw", "open-raw"):
            if baseline not in runs:
                continue
            comparisons[baseline] = {}
            for name, trials in runs.items():
                comparisons[baseline][name] = compare(trials, runs[baseline], cases)
        snapshot["splits"][split] = {
            "cases_sha256": digest, "expected_cases": len(cases), "systems": systems,
            "templates": len({c["template"] for c in cases}), "comparisons": comparisons,
            "cases": [{k: c.get(k) for k in (
                "id", "template", "family", "kind", "sql", "original_ms", "source", "headroom")}
                for c in cases]}
    body = json.dumps(snapshot, separators=(",", ":")) + "\n"
    for path in (ROOT / "web/public/research/snapshot.json", ROOT / "site/data/research.json"):
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(body)
        temp.replace(path)
    print(f"Exported research snapshot ({len(body):,} bytes); no inference or database calls.")


if __name__ == "__main__":
    main()
