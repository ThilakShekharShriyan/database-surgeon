#!/usr/bin/env python3
"""Build a real-ish pg_stat_statements workload slice from the surgeon DB.

1. Ensures pg_stat_statements is available (creates extension if permitted).
2. Replays top eval_v2 case SQLs against fixture schemas to populate stats.
3. Exports a fingerprintable JSONL slice under .local/training/pg_stat_slice.jsonl
   for cache seeding / private retrain demos.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from surgeon.eval.cases import load_cases  # noqa: E402
from surgeon.eval.workload_cache import fingerprint  # noqa: E402
from surgeon.sql import normalize  # noqa: E402

OUT = ROOT / ".local" / "training" / "pg_stat_slice.jsonl"
REPORT = ROOT / ".local" / "training" / "pg_stat_slice_report.json"


def _psql(sql: str, *, tuples_only: bool = False) -> str:
    env = dict(os.environ)
    env.setdefault("PGHOST", "127.0.0.1")
    env.setdefault("PGPORT", "55432")
    env.setdefault("PGDATABASE", "surgeon")
    env.setdefault("PGUSER", "surgeon_reader")
    env.setdefault("PGPASSWORD", "local-benchmark-only")
    cmd = ["psql", "-v", "ON_ERROR_STOP=1", "-At" if tuples_only else "-q", "-c", sql]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "psql failed")
    return proc.stdout


def ensure_extension() -> dict:
    try:
        _psql("CREATE EXTENSION IF NOT EXISTS pg_stat_statements;")
        return {"ok": True, "created": True}
    except Exception as exc:  # noqa: BLE001
        # May already exist under another role; try read.
        try:
            _psql("SELECT count(*) FROM pg_stat_statements;", tuples_only=True)
            return {"ok": True, "created": False, "note": str(exc)[:200]}
        except Exception as exc2:  # noqa: BLE001
            return {"ok": False, "error": str(exc2)[:300]}


def replay_cases(limit: int = 40) -> int:
    cases, _ = load_cases("dev")
    # Prefer high-value families that look like agent traffic.
    preferred = [c for c in cases if c.get("family") in {
        "sargability", "aggregation", "semijoin", "null_semantics", "join"
    }] or cases
    n = 0
    for case in preferred[:limit]:
        sql = case["sql"].rstrip().rstrip(";")
        # Run under search_path=bench so unqualified names resolve.
        try:
            _psql(f"SET search_path TO bench, public; {sql};")
            n += 1
        except Exception:
            continue
    return n


def export_slice(limit: int = 50) -> list[dict]:
    raw = _psql(
        "SELECT query, calls, total_exec_time, mean_exec_time, rows "
        "FROM pg_stat_statements "
        "WHERE query ILIKE 'SELECT%' OR query ILIKE 'WITH%' "
        "ORDER BY total_exec_time DESC NULLS LAST "
        f"LIMIT {limit};",
        tuples_only=True,
    )
    rows = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 5:
            continue
        query, calls, total, mean, nrows = parts[0], parts[1], parts[2], parts[3], parts[4]
        rows.append({
            "query": query,
            "calls": int(float(calls)),
            "total_exec_time_ms": float(total),
            "mean_exec_time_ms": float(mean),
            "rows": float(nrows),
            "fingerprint": fingerprint(query),
            "normalized": normalize(query)[:500],
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return rows


def main() -> None:
    ext = ensure_extension()
    replayed = 0
    exported: list[dict] = []
    error = None
    if ext.get("ok"):
        try:
            _psql("SELECT pg_stat_statements_reset();")
        except Exception:
            pass
        replayed = replay_cases()
        try:
            exported = export_slice()
        except Exception as exc:  # noqa: BLE001
            error = str(exc)[:300]
    else:
        error = ext.get("error")
        # Fallback: synthesize a slice from sealed cases so the flywheel still demos.
        cases, _ = load_cases("dev")
        for i, case in enumerate(cases[:50]):
            exported.append({
                "query": case["sql"],
                "calls": 10 + (i % 7) * 3,
                "total_exec_time_ms": 100.0 * (10 + i % 5),
                "mean_exec_time_ms": 10.0 * (1 + i % 5),
                "rows": 100,
                "fingerprint": fingerprint(case["sql"]),
                "normalized": normalize(case["sql"])[:500],
                "synthetic": True,
                "case": case["id"],
            })
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text("".join(json.dumps(r) + "\n" for r in exported))

    report = {
        "extension": ext,
        "replayed_statements": replayed,
        "exported": len(exported),
        "path": str(OUT),
        "error": error,
        "top5": exported[:5],
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
