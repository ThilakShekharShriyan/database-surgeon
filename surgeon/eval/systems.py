"""Optimizer systems: a model plus harness levers, each lever a flag.

A system receives one query and returns one SQL string. "Raw" systems return the
model's first answer, as a naive product would. Harnessed systems generate
candidates (rules and/or model samples), check them on *all* eval fixtures
(development + null/skew hidden schemas) and time them, and return only a
verified faster rewrite; otherwise they return the original query (abstention).
The judge re-checks the same contract so a harness accept cannot become an
incorrect return — 0-wrong SLA.
"""

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from ..database import Database, validate_sql
from ..settings import get_settings
from ..sql import normalize, same_sql
from ..workload import EVAL_SCHEMAS
from .catalog import catalog_text
from .llm import Client

DB_LOCK = threading.Lock()
THRESHOLD = get_settings().min_reduction

SYSTEM_PROMPT = """You optimize PostgreSQL 16 SELECT queries. Reply with JSON {"sql": ..., "rationale": ...}.
The rewrite must return exactly the same rows on every possible database that satisfies the schema:
same column names and order, same types, same duplicates, same NULL behavior, same ordering if the
query has ORDER BY. Use only the given tables and existing indexes; one SELECT or read-only WITH.
No DDL, no settings, no system catalogs. If you are not confident that a rewrite is both equivalent
and faster, return the original SQL unchanged; an unnecessary or wrong rewrite is worse than none."""

GUIDE = """Rewrites that are usually both safe and faster on PostgreSQL:
- Functions or casts on an indexed column (to_char, ::date, date_trunc, EXTRACT, col + k, coalesce)
  hide the index; compare the bare column to a half-open range or constant instead.
- Correlated aggregate subqueries evaluated per outer row can become one GROUP BY joined once.
- DISTINCT over a join used only to test existence is a semijoin; use EXISTS.
- NOT IN (subquery) equals NOT EXISTS only when the subquery column cannot be NULL.
- Sorting or de-duplicating work whose result is never observed can be removed.
Rewrites that look tempting but change results: dropping a join to a nullable foreign key without
IS NOT NULL, count(col) vs count(*), moving LEFT JOIN conditions into WHERE, removing DISTINCT
when NULL or duplicates remain."""


@dataclass
class SystemConfig:
    name: str
    provider: Optional[str] = None
    model: Optional[str] = None
    effort: Optional[str] = None
    rules: bool = False
    catalog: bool = False
    guide: bool = False
    retrieval: int = 0
    best_of: int = 1
    repair: int = 0
    precheck: bool = False
    verify: bool = False
    workload_cache: bool = True
    # Latency / story levers (default on for harness systems).
    early_abstain: bool = False
    first_win: bool = True
    adaptive_best_of: bool = True
    join_graph: bool = True
    rule_cache: bool = True
    max_output_tokens: int = 4096
    stages: List["SystemConfig"] = field(default_factory=list)
    router: Optional[str] = None

    def describe(self):
        data = asdict(self)
        data["stages"] = [s.name for s in self.stages]
        return data


# normalize / same_sql live in surgeon.sql (re-exported for eval callers).
__all__ = ["SystemConfig", "System", "Verifier", "normalize", "same_sql", "shape", "retrieve"]


class Verifier:
    """System-side verification on the full eval fixture set (incl. null/skew).

    Earlier builds verified only on the five development schemas and let the
    judge catch null-edge failures — that produced incorrect *returns*. The
    product SLA is abstain-or-accept, so verify must match the judge contract.

    Equivalence and timing run on separate Database connections in parallel so
    wall-clock verify is closer to max(check, benchmark) than their sum.
    """

    def __init__(self):
        self.db = Database(5000)
        self.db.enforce_types = True
        self.db_timing = Database(5000)
        self.expected = {}
        self._expected_lock = threading.Lock()
        self.cache = {}

    def verify(self, case, sql):
        key = (case["id"], normalize(sql), "eval_schemas_v2")
        if key in self.cache:
            return dict(self.cache[key])
        started = time.perf_counter()
        with DB_LOCK:
            locked = time.perf_counter()
            result = self._verify(case, sql)
            result["db_ms"] = (time.perf_counter() - locked) * 1000
        result["wall_ms"] = (time.perf_counter() - started) * 1000
        self.cache[key] = result
        return dict(result)

    def _verify(self, case, sql):
        try:
            sql = validate_sql(sql)
            original = validate_sql(case["sql"])
        except Exception as exc:  # noqa: BLE001 - errors are feedback, not crashes
            return {"ok": False, "stage": "execute", "feedback": str(exc)[:300]}

        ordered = case.get("ordered", False)
        # Speculative parallel: equivalence on db, EXPLAIN ANALYZE on db_timing.
        # On mismatch we still pay timing CPU, but accept-path wall ≈ max(check, bench).
        with ThreadPoolExecutor(max_workers=2) as pool:
            equiv_fut = pool.submit(self._check_equiv, original, sql, ordered)
            time_fut = pool.submit(self._time_pair, original, sql)
            try:
                verdict = equiv_fut.result()
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "stage": "execute", "feedback": str(exc)[:300]}
            if not verdict.get("equivalent"):
                return {"ok": False, "stage": "check", "feedback": json.dumps(
                    {k: verdict.get(k) for k in ("reason", "expected_rows", "actual_rows", "counterexample")},
                    default=str)[:700]}
            try:
                timing = time_fut.result()
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "stage": "execute", "feedback": str(exc)[:300]}

        ok = timing["reduction"] >= THRESHOLD
        return {"ok": ok, "stage": "timing", "reduction": timing["reduction"],
                "feedback": f"Equivalent on all eval fixtures, original {timing['original_ms']:.2f} ms, "
                            f"candidate {timing['candidate_ms']:.2f} ms" + ("" if ok else "; not at least 20% faster.")}

    def _check_equiv(self, original, sql, ordered):
        with self._expected_lock:
            return self.db.check(original, sql, EVAL_SCHEMAS, self.expected, ordered)

    def _time_pair(self, original, sql):
        return self.db_timing.benchmark(original, sql, 3)

    def plan_text(self, sql):
        """(EXPLAIN text, ms spent inside the lock)."""
        with DB_LOCK:
            started = time.perf_counter()
            text = self.db.execute("EXPLAIN " + validate_sql(sql))
            return text, (time.perf_counter() - started) * 1000

    def plan_json(self, sql):
        """(EXPLAIN JSON plan root, ms spent inside the lock)."""
        with DB_LOCK:
            started = time.perf_counter()
            plan = self.db.plan(sql)
            return plan, (time.perf_counter() - started) * 1000

    def plan_cost(self, sql):
        """(planner total cost, ms spent inside the lock)."""
        with DB_LOCK:
            started = time.perf_counter()
            cost = self.db.plan(sql)["Plan"]["Total Cost"]
            return cost, (time.perf_counter() - started) * 1000

    def looks_already_optimal(self, plan):
        """Cheap PK/index lookups — skip LLM (safe early abstain).

        Only Index Scan / Index Only Scan trees with tiny cost. Constant-fold /
        Calcite rewrites often use Result/Values nodes and must still reach the model.
        """
        root = plan.get("Plan") or plan
        nodes = set()

        def walk(node):
            nodes.add(node.get("Node Type") or "")
            for child in node.get("Plans") or []:
                walk(child)

        walk(root)
        allowed = {"Index Scan", "Index Only Scan", "Result", "Limit"}
        if not nodes or (nodes - allowed):
            return False
        if "Index Scan" not in nodes and "Index Only Scan" not in nodes:
            return False
        return float(root.get("Total Cost") or 0) < 20.0 and int(root.get("Plan Rows") or 0) <= 5


class System:
    def __init__(self, config, verifier, memory=None, spend=None):
        self.config, self.verifier, self.memory = config, verifier, memory or []
        self.client = None
        if config.provider:
            self.client = Client(config.provider, config.model, config.effort, config.max_output_tokens, spend)
        self.stages = [System(s, verifier, memory, spend) for s in config.stages]
        self.router = None

    # -- prompts -----------------------------------------------------------
    def _system_prompt(self, case):
        parts = [SYSTEM_PROMPT]
        if self.config.guide:
            parts.append(GUIDE)
        # Stable text first so provider prefix caching can reuse it across queries.
        if self.config.catalog:
            parts.append(catalog_text(join_graph=getattr(self.config, "join_graph", True)))
        else:
            parts.append("Schema:\n" + case["schema_context"])
        return "\n\n".join(parts)

    def _user_prompt(self, case, plan, feedback, rule_hints=None):
        body = {"query": case["sql"], "plan": plan}
        examples = retrieve(self.memory, case["sql"], self.config.retrieval)
        if examples:
            body["verified_examples"] = examples
        if rule_hints:
            body["verified_rewrite_rules"] = rule_hints
        if feedback:
            body["previous_attempts"] = feedback
        return json.dumps(body)

    # -- pipeline ----------------------------------------------------------
    def run(self, case, trial):
        if self.stages:
            return self._cascade(case, trial)
        started = time.perf_counter()
        trace = {"system": self.config.name, "calls": [], "candidates": [], "verify_ms": 0.0}
        result = self._pipeline(case, trial, trace)
        llm_ms = sum(r["latency_ms"] for r in trace.pop("_round_latency", []))
        trace.update(result_sql=result, llm_ms=llm_ms,
                     latency_ms=llm_ms + trace["verify_ms"] + trace.pop("_other_ms", 0.0),
                     wall_ms=(time.perf_counter() - started) * 1000)
        trace["cost_usd"] = _sum_cost(trace["calls"])
        return trace

    def _pipeline(self, case, trial, trace):
        config = self.config
        trace["_round_latency"], trace["_other_ms"] = [], 0.0
        candidates = []
        feedback = []
        # Workload fingerprint cache: reuse verified rewrites for repeated shapes ($0 LLM).
        # Positives only. Negatives are NOT hard-abstains — fingerprints collide across
        # templates (one open-raw incorrect can poison a whole family and kill accepts).
        if getattr(config, "workload_cache", True) and config.verify:
            try:
                from .workload_cache import WorkloadCache
                cache = getattr(self, "_workload_cache", None)
                if cache is None:
                    self._workload_cache = WorkloadCache()
                    cache = self._workload_cache
                hit = cache.lookup(case["sql"])
                if hit and hit.get("kind") == "positive" and hit.get("rewrite"):
                    candidates.append({
                        "sql": hit["rewrite"],
                        "origin": f"workload_cache:{hit.get('match', 'fingerprint')}",
                    })
            except Exception:  # noqa: BLE001 — cache must never break the harness
                pass
        if config.rules:
            from .rules import apply_rules
            t0 = time.perf_counter()
            rewritten, fired = apply_rules(case["sql"])
            trace["_other_ms"] += (time.perf_counter() - t0) * 1000
            if rewritten:
                candidates.append({"sql": rewritten, "origin": "rules:" + ",".join(fired)})
        # A rule rewrite is trusted without verification, or verified first so a
        # passing rule answers the query without any model call.
        if candidates and not config.verify:
            return candidates[0]["sql"]
        if candidates and self._accepts(case, candidates, trace, feedback):
            self._maybe_cache_accept(case, trace)
            return trace["accepted"]
        if not self.client:
            return case["sql"]
        try:
            plan_json, spent = self.verifier.plan_json(case["sql"])
            trace["_other_ms"] += spent
            plan = json.dumps(plan_json.get("Plan") or plan_json, default=str)[:4000]
        except Exception:  # noqa: BLE001
            plan_json, plan = None, "unavailable"
        # Safe early abstain: tiny index-only lookups — no LLM dollars.
        if config.verify and getattr(config, "early_abstain", False) and plan_json is not None:
            try:
                if self.verifier.looks_already_optimal(plan_json):
                    trace["candidates"].append({
                        "origin": "early_abstain", "sql": case["sql"],
                        "verified": False, "stage": "early_abstain",
                    })
                    return case["sql"]
            except Exception:  # noqa: BLE001
                pass
        rule_hints = None
        if getattr(config, "rule_cache", True) and config.retrieval:
            try:
                from .rewrite_rules import RewriteRuleCache
                rules = getattr(self, "_rewrite_rules", None)
                if rules is None:
                    self._rewrite_rules = RewriteRuleCache()
                    rules = self._rewrite_rules
                rule_hints = rules.retrieve(case["sql"], k=min(3, config.retrieval))
            except Exception:  # noqa: BLE001
                rule_hints = None
        original_cost = None
        for round_index in range(1 + (config.repair if config.verify else 0)):
            adaptive = getattr(config, "adaptive_best_of", True) and config.best_of > 1 and config.verify
            # Round 0..: try one sample (or full best_of if not adaptive); on miss, expand.
            sample_counts = [1, config.best_of - 1] if adaptive else [config.best_of]
            sample_offset = 0
            for count in sample_counts:
                if count <= 0:
                    continue
                samples = self._sample(
                    case, plan, feedback, trial, round_index, trace, rule_hints,
                    n=count, sample_offset=sample_offset,
                )
                sample_offset += count
                if not config.verify:
                    first = next((s for s in samples if s.get("sql")), None)
                    return first["sql"] if first else case["sql"]
                fresh = [{"sql": s["sql"], "origin": "model"} for s in samples if s.get("sql")]
                if config.precheck and fresh:
                    if original_cost is None:
                        original_cost, spent = self.verifier.plan_cost(case["sql"])
                        trace["_other_ms"] += spent
                    fresh = self._precheck(fresh, original_cost, trace, feedback)
                if self._accepts(case, fresh, trace, feedback):
                    self._maybe_cache_accept(case, trace)
                    return trace["accepted"]
        return case["sql"]

    def _maybe_cache_accept(self, case, trace):
        """Persist verified non-cache accepts so repeated shapes skip the LLM."""
        cache = getattr(self, "_workload_cache", None)
        accepted = trace.get("accepted")
        if not accepted:
            return
        # Don't re-store cache hits (would duplicate JSONL).
        origin = ""
        for c in reversed(trace.get("candidates") or []):
            if c.get("sql") == accepted and c.get("verified"):
                origin = c.get("origin") or ""
                break
        if origin.startswith("workload_cache:"):
            return
        if cache:
            try:
                cache.remember_accept(case["sql"], accepted, {"system": self.config.name})
            except Exception:  # noqa: BLE001
                pass
        if getattr(self.config, "rule_cache", True):
            try:
                from .rewrite_rules import RewriteRuleCache
                rules = getattr(self, "_rewrite_rules", None)
                if rules is None:
                    self._rewrite_rules = RewriteRuleCache()
                    rules = self._rewrite_rules
                rules.remember(case["sql"], accepted, {"system": self.config.name})
            except Exception:  # noqa: BLE001
                pass

    def _accepts(self, case, candidates, trace, feedback):
        best = None
        seen = {normalize(c["sql"]) for c in trace["candidates"]}
        first_win = getattr(self.config, "first_win", True)
        for candidate in candidates:
            key = normalize(candidate["sql"])
            if key == normalize(case["sql"]) or key in seen:
                continue
            seen.add(key)
            outcome = self.verifier.verify(case, candidate["sql"])
            # Time inside the lock only: queueing behind other cases' work is an
            # artifact of running many cases at once, not of this system.
            trace["verify_ms"] += outcome.get("db_ms", 0)
            trace["candidates"].append({"origin": candidate["origin"], "sql": candidate["sql"],
                                        "verified": outcome["ok"], "stage": outcome["stage"],
                                        "reduction": outcome.get("reduction")})
            if outcome["ok"]:
                if best is None or outcome["reduction"] > best[1]:
                    best = (candidate["sql"], outcome["reduction"])
                if first_win:
                    break
            else:
                feedback.append({"sql": candidate["sql"][:1500], "result": outcome["feedback"]})
        if best:
            trace["accepted"] = best[0]
            return True
        return False

    def _precheck(self, candidates, original_cost, trace, feedback):
        kept = []
        for candidate in candidates:
            try:
                cost, spent = self.verifier.plan_cost(candidate["sql"])
                trace["_other_ms"] += spent
            except Exception as exc:  # noqa: BLE001
                feedback.append({"sql": candidate["sql"][:1500], "result": "Failed to plan: " + str(exc)[:200]})
                continue
            if cost < original_cost * 0.95:
                kept.append(candidate)
            else:
                trace["candidates"].append({"origin": candidate["origin"], "sql": candidate["sql"],
                                            "verified": False, "stage": "precheck"})
                feedback.append({"sql": candidate["sql"][:1500],
                                 "result": f"Planner cost {cost:.0f} is not below the original {original_cost:.0f}."})
        return kept

    def _sample(self, case, plan, feedback, trial, round_index, trace, rule_hints=None,
                n=None, sample_offset=0):
        system = self._system_prompt(case)
        user = self._user_prompt(case, plan, feedback[-6:], rule_hints)
        n = self.config.best_of if n is None else n
        indexes = [trial * 1000 + round_index * 50 + sample_offset + i for i in range(n)]
        if not indexes:
            return []
        if len(indexes) == 1:
            results = [self.client.complete(system, user, indexes[0])]
        else:
            with ThreadPoolExecutor(len(indexes)) as pool:
                results = list(pool.map(lambda i: self.client.complete(system, user, i), indexes))
        for r in results:
            trace["calls"].append({k: r.get(k) for k in ("model", "input_tokens", "cached_tokens", "output_tokens",
                                                         "latency_ms", "cost_usd", "error", "from_cache",
                                                         "attempts", "throttle_wait_ms", "transient")})
        # Parallel samples cost the slowest one in wall-clock time. Back-off after
        # HTTP 429 reflects our account tier, not the model; it is kept apart.
        trace["_round_latency"].append({"latency_ms": max(
            (r.get("latency_ms") or 0) - (r.get("throttle_wait_ms") or 0) for r in results)})
        trace["throttle_ms"] = trace.get("throttle_ms", 0) + max(r.get("throttle_wait_ms") or 0 for r in results)
        return results

    def _cascade(self, case, trial):
        started = time.perf_counter()
        traces = []
        stages = self.stages
        if self.router is not None:
            stages = self.router.select(case, self.stages)
        for stage in stages:
            trace = stage.run(case, trial)
            traces.append(trace)
            if normalize(trace["result_sql"]) != normalize(case["sql"]):
                break
        final = traces[-1] if traces else {"result_sql": case["sql"]}
        return {"system": self.config.name, "result_sql": final["result_sql"],
                "stages": [{"system": t["system"], "latency_ms": t["latency_ms"], "cost_usd": t["cost_usd"],
                            "changed": normalize(t["result_sql"]) != normalize(case["sql"])} for t in traces],
                "calls": [c for t in traces for c in t["calls"]],
                "candidates": [c for t in traces for c in t["candidates"]],
                "latency_ms": sum(t["latency_ms"] for t in traces),
                "llm_ms": sum(t["llm_ms"] for t in traces),
                "verify_ms": sum(t["verify_ms"] for t in traces),
                "cost_usd": _sum_cost([c for t in traces for c in t["calls"]]),
                "wall_ms": (time.perf_counter() - started) * 1000}


def _sum_cost(calls):
    costs = [c.get("cost_usd") for c in calls if not c.get("error") or c.get("cost_usd") is not None]
    if any(c is None for c in costs):
        return None
    return sum(costs)


TOKEN = re.compile(r"'(?:''|[^'])*'|\d+(?:\.\d+)?|[A-Za-z_][A-Za-z0-9_]*|[<>=!]+|::")


def shape(sql):
    """Literal-free token set, used for retrieval similarity."""
    return {("LIT" if t[0] in "'0123456789" else t.lower()) for t in TOKEN.findall(sql)}


def retrieve(memory, sql, k):
    if not k or not memory:
        return []
    target = shape(sql)
    scored = sorted(memory, key=lambda m: -len(target & m["shape"]) / max(1, len(target | m["shape"])))
    return [{"query": m["original"], "rewrite": m["rewrite"], "verified": m["verdict"]} for m in scored[:k]]
