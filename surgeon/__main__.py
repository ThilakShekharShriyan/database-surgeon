import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import uuid

from .config import ROOT, load_env
from .artifacts import evaluation_lock, persist
from .database import Database, validate_sql
from .providers import Provider, ProviderOutputError, request_json
from .workload import CASES, SCHEMA, FIXTURE_SCHEMAS, seed_sql
from .lab import suite_cases


def validate_run_args(args):
    if (not 0 < args.min_reduction < 1 or args.timeout_ms < 100
            or args.max_output_tokens < 128 or not 1 <= args.attempts <= 5
            or not 3 <= args.repeats <= 15):
        raise ValueError("Invalid reduction, timeout, attempt, repeat or output budget.")


def run(args):
    validate_run_args(args)
    with evaluation_lock(ROOT):
        return run_locked(args)


def run_locked(args):
    run_started = time.perf_counter()
    provider = Provider(args.provider, args.model, args.max_output_tokens)
    db = Database(args.timeout_ms)
    # Database readiness must be established before any paid model call.
    workload = suite_cases(getattr(args, "suite", "pilot"))
    db.enforce_types = getattr(args, "suite", "pilot") != "pilot"
    selected = [c for c in workload if not args.case or c["id"] == args.case]
    if not selected:
        raise ValueError("No workload cases selected.")
    database = db.preflight()
    contexts = {}
    for case in selected:
        db.columns(case["sql"])
        for schema in FIXTURE_SCHEMAS:
            db.rows(case["sql"], schema)
        contexts[case["id"]] = {"schema": SCHEMA + "\n" + case.get("schema_context", ""), "plan": db.plan(case["sql"])}
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    directory = ROOT / "results" / run_id
    directory.mkdir(parents=True)
    evaluation_sources = {name: (Path(__file__).parent / name).read_text()
                          for name in ("database.py", "providers.py", "__main__.py", "artifacts.py", "lab.py")}
    manifest = {"artifact_version": 2, "run_id": run_id, "state": "running",
                "provider": args.provider, "requested_model": provider.model,
                "mock": args.provider == "mock", "split": "development",
                "suite": getattr(args, "suite", "pilot"),
                "selected_cases": [c["id"] for c in selected],
                "max_attempts": args.attempts, "min_reduction": args.min_reduction,
                "repeats": args.repeats, "statement_timeout_ms": args.timeout_ms,
                "max_output_tokens": args.max_output_tokens,
                "pricing_usd_per_million_tokens": {
                    kind: os.getenv(args.provider.upper() + "_" + kind + "_PRICE") or None
                    for kind in ("INPUT", "CACHED", "OUTPUT")},
                "workload_sha256": hashlib.sha256(json.dumps(workload, sort_keys=True).encode()).hexdigest(),
                "fixture_sha256": hashlib.sha256((SCHEMA + seed_sql()).encode()).hexdigest(),
                "evaluator_sha256": hashlib.sha256(json.dumps(evaluation_sources, sort_keys=True).encode()).hexdigest(),
                "database": database, "database_version": database["version"],
                "setup_wall_ms": (time.perf_counter() - run_started) * 1000,
                "correctness_scope": f"unordered row bags on {len(FIXTURE_SCHEMAS)} development instances; not a proof",
                "created_at": datetime.now(timezone.utc).isoformat()}
    persist(directory / "manifest.json", manifest)
    persist(directory / "evaluator_sources.json", evaluation_sources)
    results = []
    provider_stopped = False
    try:
        for case in selected:
            if provider_stopped:
                result = {"case_id": case["id"], "family": case["family"], "original_sql": case["sql"],
                          "accepted": False, "wall_ms": 0, "attempts": [{"attempt": 0, "status": "not_attempted",
                          "reason": "Provider circuit breaker stopped this run after an API failure."}]}
                persist(directory / (case["id"] + ".json"), result)
            else:
                result = evaluate_case(args, provider, db, case, contexts[case["id"]], directory)
                provider_stopped = any(a["status"] == "error" and "generation" not in a for a in result["attempts"])
            results.append(result)
            persist(directory / "summary.json", summarize(results, manifest))
    except (KeyboardInterrupt, Exception) as exc:
        manifest["state"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        # Include the last checkpoint even when a process was interrupted mid-case.
        results = [json.loads((directory / (c["id"] + ".json")).read_text())
                   for c in selected if (directory / (c["id"] + ".json")).exists()]
        raise
    else:
        manifest["state"] = "failed" if any(a["status"] == "error" for r in results for a in r["attempts"]) else "completed"
    finally:
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        manifest["run_wall_ms"] = (time.perf_counter() - run_started) * 1000
        persist(directory / "manifest.json", manifest)
        summary = summarize(results, manifest)
        persist(directory / "summary.json", summary)
        print(json.dumps(summary, indent=2))
        print(f"Artifacts: {directory}")
    return directory, summary


def evaluate_case(args, provider, db, case, context, directory):
    started = time.perf_counter()
    result = {"case_id": case["id"], "family": case["family"],
              "original_sql": case["sql"], "accepted": False, "attempts": [], "wall_ms": 0}
    path = directory / (case["id"] + ".json")
    persist(path, result)
    feedback, seen = [], set()
    for attempt in range(args.attempts):
        record = {"attempt": attempt + 1, "status": "generating"}
        result["attempts"].append(record)
        persist(path, result)
        try:
            generation = provider.generate(case, context, feedback)
            record["generation"] = asdict(generation)
            record["status"] = "evaluating"
            # Persist successful API output and usage before evaluating it.
            persist(path, result)
            candidate = validate_sql(generation.sql)
            if candidate in seen:
                record["status"] = "duplicate"
                break
            seen.add(candidate)
            if candidate.strip() == validate_sql(case["sql"]).strip():
                record["status"] = "no_change"
                break
            record["correctness"] = db.check(case["sql"], candidate)
            if not record["correctness"]["equivalent"]:
                record["status"] = "incorrect"
            else:
                record["benchmark"] = db.benchmark(case["sql"], candidate, args.repeats)
                record["status"] = "accepted" if record["benchmark"]["reduction"] >= args.min_reduction else "not_faster"
                if record["status"] == "accepted":
                    result["accepted"] = True
                    result["accepted_sql"] = candidate
            feedback.append({"sql": candidate, "status": record["status"],
                             "benchmark": record.get("benchmark"),
                             "reason": record["correctness"].get("reason")})
        except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
            record.update(status="error", error=str(exc))
            record["request_attempts"] = list(getattr(provider, "last_request_attempts", []))
            if isinstance(exc, ProviderOutputError):
                record["failed_output_usage"] = exc.usage
                record["returned_model"] = exc.model
            feedback.append({"status": "error", "reason": str(exc)})
            # An API failure is not replayed; SQL/evaluation errors may guide repair.
            if "generation" not in record:
                break
        finally:
            result["wall_ms"] = (time.perf_counter() - started) * 1000
            persist(path, result)
        print(f"{case['id']} attempt {attempt + 1}: {record['status']}", flush=True)
        if result["accepted"]:
            break
    result["wall_ms"] = (time.perf_counter() - started) * 1000
    persist(path, result)
    return result


def summarize(results, manifest):
    attempts = [a for r in results for a in r["attempts"]]
    generations = [a["generation"] for a in attempts if "generation" in a]
    costs = [g["cost_usd"] for g in generations]
    complete = (bool(generations) and all(c is not None for c in costs)
                and all("generation" in a for a in attempts)
                and manifest.get("state", "completed") == "completed")
    complete = complete and all(item.get("http_status") == 200 for g in generations for item in g.get("request_attempts", []))
    failed_usage = [a["failed_output_usage"] for a in attempts if "failed_output_usage" in a]
    return {"run_id": manifest["run_id"], "provider": manifest["provider"],
            "state": manifest.get("state", "completed"),
            "mock": manifest["mock"], "split": manifest["split"], "cases": len(results),
            "accepted": sum(r["accepted"] for r in results),
            "acceptance_rate": sum(r["accepted"] for r in results) / len(results) if results else 0,
            "incorrect_candidates_rejected": sum(a["status"] == "incorrect" for a in attempts),
            "errors": sum(a["status"] == "error" for a in attempts),
            "unfinished_attempts": sum(a["status"] in ("generating", "evaluating") for a in attempts),
            "input_tokens": sum(g["input_tokens"] for g in generations) + sum(u.get("input_tokens", u.get("prompt_tokens", 0)) for u in failed_usage),
            "output_tokens": sum(g["output_tokens"] for g in generations) + sum(u.get("output_tokens", u.get("completion_tokens", 0)) for u in failed_usage),
            "not_attempted": sum(a["status"] == "not_attempted" for a in attempts),
            "provider_throttle_wait_ms": sum(g.get("throttle_wait_ms", 0) for g in generations),
            "http_requests_recorded": sum(len(g.get("request_attempts", [])) for g in generations) + sum(len(a.get("request_attempts", [])) for a in attempts if "generation" not in a),
            "rate_limit_rejections": sum(item.get("http_status") == 429 for a in attempts for item in (a.get("generation", {}).get("request_attempts", []) + a.get("request_attempts", []))),
            "cost_complete": complete, "estimated_model_cost_usd": sum(costs) if complete else None,
            "total_wall_ms": manifest.get("run_wall_ms", sum(r.get("wall_ms", 0) for r in results)),
            "case_wall_ms": sum(r.get("wall_ms", 0) for r in results),
            "note": "Development pilot only. Mock results are fixtures, not model evidence. Database compute cost is not monetized."}


def add_run_arguments(parser, paid=True):
    if paid:
        parser.add_argument("--provider", choices=["mock"] + list(Provider.BASES), default="mock")
        parser.add_argument("--model")
    else:
        parser.set_defaults(provider="mock", model=None)
    parser.add_argument("--suite", choices=["pilot", "lab", "all"], default="pilot")
    parser.add_argument("--case", choices=[c["id"] for c in suite_cases("all")])
    parser.add_argument("--attempts", type=int, choices=range(1, 6), default=1)
    parser.add_argument("--repeats", type=int, choices=range(3, 16), default=5)
    parser.add_argument("--min-reduction", type=float, default=0.20)
    parser.add_argument("--timeout-ms", type=int, default=5000)
    parser.add_argument("--max-output-tokens", type=int, default=2048)


def main():
    load_env()
    parser = argparse.ArgumentParser(description="Database Surgeon development pilot")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor")
    doctor.add_argument("--json", action="store_true", help="Machine-readable readiness and a nonzero exit on failure")
    commands.add_parser("seed")
    models = commands.add_parser("models")
    models.add_argument("provider", choices=list(Provider.BASES))
    runner = commands.add_parser("run")
    add_run_arguments(runner)
    reporter = commands.add_parser("report", help="Build an offline Markdown comparison report")
    reporter.add_argument("--results", type=Path, default=ROOT / "results")
    reporter.add_argument("--output", type=Path, default=ROOT / "results" / "report.md")
    watcher = commands.add_parser("watch", help="Continuously run unit checks and mock database benchmarks; no paid calls")
    add_run_arguments(watcher, paid=False)
    watcher.add_argument("--interval", type=float, default=60, help="Seconds between completed checks (>=10)")
    watcher.add_argument("--cycles", type=int, default=0, help="Number of checks, or 0 to continue until stopped")
    args = parser.parse_args()
    # Let process managers stop long-running checks while preserving checkpoints.
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        if args.command == "doctor":
            diagnostic = {"psql_available": bool(shutil.which("psql")), "database_ready": False,
                          "keys_present": {p: bool(os.getenv(p.upper() + "_API_KEY")) for p in Provider.BASES},
                          "models": {p: os.getenv(p.upper() + "_MODEL") or "unset" for p in Provider.BASES}}
            try:
                diagnostic["database"] = Database().preflight()
                diagnostic["database_ready"] = True
            except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
                diagnostic["database_error"] = str(exc)
            print(json.dumps(diagnostic, indent=2))
            if not diagnostic["database_ready"]:
                if not args.json:
                    print("Postgres unavailable or fixtures/role invalid. Run docker compose up -d --wait, then python3 -m surgeon seed.")
                return 1
        elif args.command == "seed":
            # Only the project-owned Compose service is used for DDL and fixtures.
            subprocess.run(["docker", "compose", "exec", "-T", "postgres", "psql", "-X",
                            "-v", "ON_ERROR_STOP=1", "-U", "surgeon_admin", "-d", "surgeon"],
                           input=seed_sql(), text=True, check=True, cwd=ROOT)
            print("Seeded development workload; existing rows preserved.")
        elif args.command == "models":
            key = os.getenv(args.provider.upper() + "_API_KEY")
            if not key:
                raise ValueError(f"Set {args.provider.upper()}_API_KEY in .env first.")
            response = request_json(Provider.BASES[args.provider] + "/models", key)
            print("\n".join(sorted(m["id"] for m in response.get("data", []))))
        elif args.command == "report":
            from .reporting import build_report
            print(json.dumps(build_report(args.results, args.output), indent=2))
        elif args.command == "watch":
            from .watch import watch
            validate_run_args(args)
            state = watch(args, run)
            return int(state.get("last_check", state["state"]) not in ("healthy", "stopped"))
        else:
            _, summary = run(args)
            return int(summary["errors"] > 0)
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Stopped. Completed checkpoints are preserved.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
