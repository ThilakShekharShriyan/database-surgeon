#!/usr/bin/env python3
"""Read saved artifacts into a dated study packet; no DB, API, or cache writes."""
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from surgeon.eval.cases import load_cases
from surgeon.eval.comparison import compare
from surgeon.eval.metrics import summarize


def main():
    evidence = {"captured_at_utc": datetime.now(timezone.utc).isoformat(),
                "primary_trial": 0, "source_files": {}, "splits": {}, "comparisons_dev": {},
                "artifact_notes": {}, "warnings": [
                    "Artifact snapshot, not a new model or database evaluation.",
                    "Current source hashes do not establish which code produced historical runs.",
                    "Active jobs may add records after capture. Partial records are disclosed.",
                    "Current verifier and judge share all eight fixtures; these are not independent hidden correctness tests."]}
    for name in ("surgeon/eval/systems.py", "surgeon/eval/registry.py", "surgeon/eval/runner.py",
                 "surgeon/eval/judge.py", "surgeon/eval/workload_cache.py", "surgeon/eval/comparison.py",
                 "scripts/build_specialist_dataset.py", "scripts/measure_cache_ab.py",
                 "scripts/pg_stat_workload_slice.py", "benchmarks/eval_v2/cases.jsonl"):
        evidence["source_files"][name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    all_runs = {}
    for split in ("dev", "heldout"):
        cases, digest = load_cases(split)
        expected = {c["id"] for c in cases}
        results, runs = {}, {}
        for directory in sorted((ROOT / "benchmarks/eval_v2/runs").iterdir()):
            path = directory / f"{split}_t0.jsonl"
            if not path.is_file():
                continue
            body = path.read_bytes()
            rows, bad = [], 0
            for line in body.decode().splitlines():
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    bad += 1
            if not rows:
                continue
            summary = summarize([rows])
            summary.update(expected_cases=len(expected), complete=len(rows) == len(expected)
                           and {r["case"] for r in rows} == expected,
                           record_count=len(rows), skipped_malformed_lines=bad,
                           trace_path=str(path.relative_to(ROOT)),
                           trace_sha256=hashlib.sha256(body).hexdigest(),
                           config_hashes=dict(Counter(r.get("config_hash") for r in rows)),
                           simulated_records=sum(bool(r.get("simulated")) for r in rows))
            results[directory.name], runs[directory.name] = summary, [rows]
        evidence["splits"][split] = {
            "cases": len(cases), "templates": len({c["template"] for c in cases}),
            "families": dict(Counter(c["family"] for c in cases)),
            "under_10_ms_at_build": sum(c["original_ms"] < 10 for c in cases),
            "cases_sha256": digest, "systems": results}
        all_runs[split] = (cases, runs)
    cases, runs = all_runs["dev"]
    for a, b in (("open-harness", "open-raw"), ("open-harness", "frontier-raw"),
                 ("open-harness", "rules-only")):
        if a in runs and b in runs:
            evidence["comparisons_dev"][f"{a}_vs_{b}"] = compare(runs[a], runs[b], cases)
    selected = {
        ".local/training/cache_ab_report.json": ("cases", "positive_hits", "negative_hits", "misses", "hit_rate", "estimated_speedup_factor", "note"),
        ".local/training/pg_stat_slice_report.json": ("extension", "replayed_statements", "exported", "error"),
        ".local/training/specialist_stats.json": ("sft_rows", "dpo_pairs", "harness_wins_used", "note"),
        ".local/training/specialist_model.json": ("base_model", "surface", "train_rows", "holdout_rows", "sql_field_accuracy", "note"),
        ".local/training/muse_summary.json": ("steps", "exact_match_delta", "paired"),
    }
    for name, keys in selected.items():
        path = ROOT / name
        if path.exists():
            record = json.loads(path.read_text())
            evidence["artifact_notes"][name] = {k: record.get(k) for k in keys}
    training = ROOT / ".local/training/specialist_sft.jsonl"
    muse = ROOT / ".local/cookbook/training/muse_starter_logs/sql-specialist-20261102-112625"
    if training.exists() and all((muse / f).exists() for f in ("train.jsonl", "holdout.jsonl")):
        read = lambda path: [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        key = lambda row: json.dumps(row["messages"], sort_keys=True)
        metadata = {key(r): r.get("meta", {}) for r in read(training)}
        template_by_id = {r["id"]: r["template"] for r in read(ROOT / "benchmarks/eval_v2/cases.jsonl")}
        groups = {}
        unresolved = 0
        for filename in ("train.jsonl", "holdout.jsonl"):
            rows = read(muse / filename)
            templates = set()
            for row in rows:
                meta = metadata.get(key(row), {})
                template = meta.get("template") or template_by_id.get(meta.get("case"))
                if template is None:
                    unresolved += 1
                else:
                    templates.add(template)
            groups[filename] = {"rows": len(rows), "templates": sorted(templates),
                                "path": str((muse / filename).relative_to(ROOT))}
        shared = sorted(set(groups["train.jsonl"]["templates"]) & set(groups["holdout.jsonl"]["templates"]))
        evidence["specialist_split_audit"] = {"files": groups, "overlapping_templates": shared,
                                             "overlap_count": len(shared), "unresolved_rows": unresolved}
    output = ROOT / "docs/STUDY_EVIDENCE.json"
    output.write_text(json.dumps(evidence, indent=2) + "\n")
    print("Wrote docs/STUDY_EVIDENCE.json; primary trial 0; no model/database/cache operations.")
    for name in ("frontier-raw", "open-raw", "open-harness", "rules-only", "fw-fast-harness", "fw-nemotron-harness"):
        row = evidence["splits"]["dev"]["systems"].get(name)
        if row:
            print(name, json.dumps({k: row[k] for k in ("cases", "accepted_rate", "incorrect_returned_count", "cost_per_case_usd", "latency_p50_ms", "complete")}))


if __name__ == "__main__":
    main()
