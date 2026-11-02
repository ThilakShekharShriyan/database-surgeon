"""Run a system over a split for k trials; judge every returned query.

Model calls run in parallel across cases; all database work (system-side
verification and judging) is serialized behind one lock so timings are not
distorted by concurrent queries. Per-case records are written as they finish,
so an interrupted run resumes where it stopped.
"""

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..config import ROOT
from .cases import load_cases
from .judge import Judge
from .llm import BudgetExceeded, Spend
from .systems import System, Verifier

RUNS = ROOT / "benchmarks" / "eval_v2" / "runs"
FROZEN = ROOT / "benchmarks" / "eval_v2" / "FROZEN.json"
MEMORY = ROOT / ".local" / "eval_v2" / "memory.jsonl"


def _uses_retrieval(config):
    return bool(config.retrieval) or any(_uses_retrieval(s) for s in config.stages)


def config_hash(config):
    """Config plus the retrieval memory it reads, so a freeze also pins the memory."""
    data = config.describe()
    data["stages"] = [json.loads(json.dumps(s.describe())) for s in config.stages]
    if _uses_retrieval(config):
        data["memory_sha256"] = hashlib.sha256(MEMORY.read_bytes()).hexdigest() if MEMORY.exists() else None
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]


def load_memory():
    from .systems import shape
    if not MEMORY.exists():
        return []
    items = [json.loads(line) for line in MEMORY.read_text().splitlines()]
    for item in items:
        item["shape"] = shape(item["original"])
    return items


def run_path(name, split, trial):
    return RUNS / name / f"{split}_t{trial}.jsonl"


def load_trials(name, split):
    directory = RUNS / name
    if not directory.exists():
        return []
    trials = []
    for path in sorted(directory.glob(f"{split}_t*.jsonl")):
        trials.append([json.loads(line) for line in path.read_text().splitlines() if line.strip()])
    return trials


def run(config, split="dev", trials=3, workers=6, ceiling_usd=None, cases=None, log=print, router=None):
    all_cases, digest = load_cases(split)
    if split == "heldout":
        frozen = json.loads(FROZEN.read_text()) if FROZEN.exists() else {}
        if frozen.get("systems", {}).get(config.name) != config_hash(config):
            raise PermissionError("Held-out split is sealed: freeze this exact system config first.")
        if frozen.get("cases_sha256") != digest:
            raise PermissionError("Held-out cases changed after the freeze.")
    if cases:
        all_cases = [c for c in all_cases if c["id"] in set(cases)]
    spend = Spend(ceiling_usd)
    verifier, judge = Verifier(), Judge()
    system = System(config, verifier, load_memory(), spend)
    if router is not None:
        system.router = router
    write_lock = threading.Lock()
    for trial in range(trials):
        path = run_path(config.name, split, trial)
        path.parent.mkdir(parents=True, exist_ok=True)
        done = set()
        if path.exists():
            done = {json.loads(line)["case"] for line in path.read_text().splitlines() if line.strip()}
        todo = [c for c in all_cases if c["id"] not in done]
        if not todo:
            continue
        log(f"{config.name} {split} trial {trial}: {len(todo)} cases")

        def one(case, trial=trial):
            trace = system.run(case, trial)
            verdict = judge.judge(case, trace["result_sql"])
            calls = trace.get("calls", [])
            return {
                "case": case["id"], "family": case["family"], "kind": case["kind"], "split": split,
                "trial": trial, "system": config.name, "config_hash": config_hash(config),
                "cases_sha256": digest, "outcome": verdict["outcome"], "speedup": verdict.get("speedup"),
                "verdict": verdict, "result_sql": trace["result_sql"],
                "latency_ms": trace["latency_ms"], "llm_ms": trace.get("llm_ms", 0),
                "verify_ms": trace.get("verify_ms", 0), "throttle_ms": trace.get("throttle_ms", 0),
                "cost_usd": trace.get("cost_usd"),
                "calls": len(calls), "errors": sum(1 for c in calls if c.get("error")),
                "output_tokens": sum(c.get("output_tokens") or 0 for c in calls),
                "input_tokens": sum(c.get("input_tokens") or 0 for c in calls),
                "cached_tokens": sum(c.get("cached_tokens") or 0 for c in calls),
                "candidates": trace.get("candidates", []), "stages": trace.get("stages"),
                "_calls": calls,
            }

        with ThreadPoolExecutor(workers) as pool, path.open("a") as handle:
            futures = {pool.submit(one, case): case for case in todo}
            try:
                for future in as_completed(futures):
                    record = future.result()
                    if any(c.get("transient") for c in record.pop("_calls")):
                        log(f"  {record['case'][:38]:38} provider unavailable; left for a rerun")
                        continue
                    with write_lock:
                        handle.write(json.dumps(record, default=str) + "\n")
                        handle.flush()
                    log(f"  {record['case'][:38]:38} {record['outcome']:10} "
                        f"{(record['speedup'] or 0):6.2f}x {record['latency_ms'] / 1000:6.1f}s")
            except BudgetExceeded:
                for f in futures:
                    f.cancel()
                raise
    return load_trials(config.name, split)
