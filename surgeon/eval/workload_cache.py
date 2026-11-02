"""Workload fingerprint cache — $0 LLM hits for repeated query shapes.

Industry pattern (EverSQL / pganalyze / agent FinOps): normalize away literals,
key on structural fingerprint, reuse *verified* rewrites only. Never cache a
rewrite that failed equivalence.

Positive entries come from harness accepts (or pg_stat_statements mining later).
Negative entries force abstain / skip LLM for known-corrupt shapes.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from surgeon.sql import normalize

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = ROOT / ".local" / "training" / "workload_cache.jsonl"

# Local copy of shape() — avoid circular import with systems.py
_TOKEN = re.compile(r"'(?:''|[^'])*'|\d+(?:\.\d+)?|[A-Za-z_][A-Za-z0-9_]*|[<>=!]+|::")


def _shape(sql: str) -> set[str]:
    return {("LIT" if t[0] in "'0123456789" else t.lower()) for t in _TOKEN.findall(sql)}


def fingerprint(sql: str) -> str:
    """Stable id: sorted shape tokens (literals collapsed)."""
    tokens = sorted(_shape(sql))
    digest = hashlib.sha256("\0".join(tokens).encode()).hexdigest()[:24]
    return digest


class WorkloadCache:
    def __init__(self, path: Path | None = None):
        self.path = path or DEFAULT_PATH
        self.positive: dict[str, dict] = {}  # fp -> {original, rewrite, hits}
        self.negative: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            fp = row.get("fingerprint") or fingerprint(row.get("original") or "")
            if row.get("kind") == "negative":
                self.negative.add(fp)
            elif row.get("rewrite"):
                self.positive[fp] = row

    def lookup(self, sql: str) -> dict | None:
        fp = fingerprint(sql)
        if fp in self.negative:
            return {"kind": "negative", "fingerprint": fp}
        hit = self.positive.get(fp)
        if not hit:
            # Exact normalized match fallback (same literals)
            key = normalize(sql)
            for row in self.positive.values():
                if normalize(row.get("original") or "") == key:
                    return {**row, "kind": "positive", "match": "exact"}
            return None
        return {**hit, "kind": "positive", "match": "fingerprint", "fingerprint": fp}

    def remember_accept(self, original: str, rewrite: str, meta: dict | None = None) -> None:
        if normalize(original) == normalize(rewrite):
            return
        fp = fingerprint(original)
        row = {
            "kind": "positive",
            "fingerprint": fp,
            "original": original,
            "rewrite": rewrite,
            "meta": meta or {},
        }
        self.positive[fp] = row
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as fh:
            fh.write(json.dumps(row) + "\n")

    def remember_incorrect(self, original: str, bad_rewrite: str, meta: dict | None = None) -> None:
        fp = fingerprint(original)
        self.negative.add(fp)
        row = {
            "kind": "negative",
            "fingerprint": fp,
            "original": original,
            "bad_rewrite": bad_rewrite,
            "meta": meta or {},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as fh:
            fh.write(json.dumps(row) + "\n")


def seed_from_harness_runs(
    run_names: tuple[str, ...] = ("open-harness", "fw-nemotron-harness", "oss20b-harness", "open-raw"),
    path: Path | None = None,
) -> dict:
    """Rebuild cache from verified accepts / incorrects on disk (dev split)."""
    out = path or DEFAULT_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    cases = {}
    for line in (ROOT / "benchmarks" / "eval_v2" / "cases.jsonl").read_text().splitlines():
        if line.strip():
            c = json.loads(line)
            cases[c["id"]] = c
    rows_out: list[dict] = []
    seen_pos: set[str] = set()
    seen_neg: set[str] = set()
    runs = ROOT / "benchmarks" / "eval_v2" / "runs"
    for name in run_names:
        f = runs / name / "dev_t0.jsonl"
        if not f.exists():
            continue
        for line in f.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            case = cases.get(row.get("case"))
            if not case:
                continue
            orig = case["sql"]
            fp = fingerprint(orig)
            if row.get("outcome") == "accepted" and row.get("result_sql"):
                if fp in seen_pos or normalize(orig) == normalize(row["result_sql"]):
                    continue
                seen_pos.add(fp)
                rows_out.append({
                    "kind": "positive",
                    "fingerprint": fp,
                    "original": orig,
                    "rewrite": row["result_sql"],
                    "meta": {"source": name, "case": row["case"]},
                })
            elif row.get("outcome") == "incorrect" and row.get("result_sql"):
                if fp in seen_neg:
                    continue
                seen_neg.add(fp)
                rows_out.append({
                    "kind": "negative",
                    "fingerprint": fp,
                    "original": orig,
                    "bad_rewrite": row["result_sql"],
                    "meta": {"source": name, "case": row["case"]},
                })
    out.write_text("".join(json.dumps(r) + "\n" for r in rows_out))
    return {"positive": len(seen_pos), "negative": len(seen_neg), "path": str(out), "rows": len(rows_out)}
