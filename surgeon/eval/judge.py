"""The evaluator: re-checks whatever a system returned, on all eight fixtures.

Outcomes:
  no_change   returned the original query
  invalid     rejected by the SELECT guard or failed to execute
  incorrect   different rows on any fixture (including the hidden three)
  accepted    same rows and at least 20% faster (median of 5 paired EXPLAIN ANALYZE runs)
  not_faster  same rows, within -10%..+20%
  regression  same rows, at least 10% slower

Verdicts are cached per (case, normalized SQL): the same SQL against the same
database gets the same verdict regardless of which system produced it.
"""

import hashlib
import json

from ..config import ROOT
from ..database import Database, validate_sql
from ..workload import EVAL_SCHEMAS
from .systems import DB_LOCK, THRESHOLD, normalize

CACHE = ROOT / ".local" / "eval_v2" / "judge_cache.jsonl"


class Judge:
    def __init__(self, repeats=5):
        self.db = Database(5000)
        self.db.enforce_types = True
        self.repeats = repeats
        self.expected = {}
        self.cache = {}
        if CACHE.exists():
            for line in CACHE.read_text().splitlines():
                record = json.loads(line)
                self.cache[record["key"]] = record["verdict"]

    def judge(self, case, sql):
        if normalize(sql) == normalize(case["sql"]):
            return {"outcome": "no_change", "speedup": 1.0}
        key = hashlib.sha256(json.dumps([case["id"], case["sql"], normalize(sql)]).encode()).hexdigest()
        if key in self.cache:
            return dict(self.cache[key])
        with DB_LOCK:
            verdict = self._judge(case, sql)
        self.cache[key] = verdict
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        with CACHE.open("a") as handle:
            handle.write(json.dumps({"key": key, "case": case["id"], "verdict": verdict}, default=str) + "\n")
        return dict(verdict)

    def _judge(self, case, sql):
        try:
            sql = validate_sql(sql)
            verdict = self.db.check(case["sql"], sql, EVAL_SCHEMAS, self.expected, case.get("ordered", False))
        except Exception as exc:  # noqa: BLE001
            return {"outcome": "invalid", "detail": str(exc)[:300]}
        if not verdict["equivalent"]:
            return {"outcome": "incorrect", "schema": verdict.get("schema"), "reason": verdict["reason"],
                    "counterexample": json.loads(json.dumps(verdict.get("counterexample"), default=str))}
        try:
            timing = self.db.benchmark(case["sql"], sql, self.repeats)
        except Exception as exc:  # noqa: BLE001 - e.g. candidate exceeds statement_timeout
            return {"outcome": "regression", "detail": str(exc)[:200], "speedup": 0.0}
        reduction = timing["reduction"]
        outcome = "accepted" if reduction >= THRESHOLD else "regression" if reduction <= -0.10 else "not_faster"
        return {"outcome": outcome, "speedup": timing["speedup"], "reduction": reduction,
                "original_ms": timing["original_ms"], "candidate_ms": timing["candidate_ms"],
                "win_rate": timing["candidate_win_rate"]}
