"""Cascade and learned routing over harnessed stages.

A cascade runs stages cheapest-first and stops at the first one that returns a
verified rewrite. The learned router predicts, from query shape and planner cost
alone, the chance that each model stage succeeds, then skips stages unlikely to
help (or abstains outright). It is a per-stage L2 logistic regression in plain
Python, trained on dev traces. Dev predictions are cross-fitted: each case is
scored by a model that never saw its template.

Because a stage behaves identically inside a cascade (same response cache, same
sample indices, same judge verdict), cascades and routers can be evaluated
exactly from each stage's standalone runs; `simulate` does that.
"""

import hashlib
import json
import math
import re
from collections import defaultdict

from ..config import ROOT
from .runner import load_trials

MODEL = ROOT / "benchmarks" / "eval_v2" / "router.json"
STAGES = ("rules-only", "oss20b-harness", "oss120b-harness")
FOLDS = 5

PATTERNS = {
    "not_in": r"\bNOT\s+IN\s*\(", "not_exists": r"\bNOT\s+EXISTS\b", "exists": r"(?<!NOT )\bEXISTS\b",
    "in_sub": r"\bIN\s*\(\s*SELECT", "distinct": r"\bDISTINCT\b", "group": r"\bGROUP\s+BY\b",
    "order": r"\bORDER\s+BY\b", "limit": r"\bLIMIT\b", "union": r"\bUNION\b", "or": r"\bOR\b",
    "left": r"\bLEFT\s+JOIN\b", "to_char": r"\bto_char\s*\(", "trunc": r"\bdate_trunc\s*\(",
    "extract": r"\bEXTRACT\s*\(", "cast_date": r"::\s*date\b", "coalesce": r"\bcoalesce\s*\(",
    "arith": r"\w\s*[-+]\s*\d+\s*=", "count": r"\bcount\s*\(", "agg": r"\b(sum|avg|max|min)\s*\(",
    "having": r"\bHAVING\b", "values": r"\bVALUES\b",
}


def features(case, plan_cost):
    sql = case["sql"]
    f = {name: float(bool(re.search(p, sql, re.I))) for name, p in PATTERNS.items()}
    f["joins"] = min(4, len(re.findall(r"\bJOIN\b", sql, re.I))) / 4
    f["subqueries"] = min(4, len(re.findall(r"\(\s*SELECT\b", sql, re.I))) / 4
    f["log_cost"] = math.log10(1 + plan_cost) / 6
    f["length"] = min(1.0, len(sql) / 1500)
    f["bias"] = 1.0
    return f


def _fit(rows, labels, l2=0.05, steps=600, lr=0.5):
    names = sorted(rows[0]) if rows else []
    w = {n: 0.0 for n in names}
    for _ in range(steps):
        grad = {n: l2 * w[n] for n in names}
        for x, y in zip(rows, labels):
            p = 1 / (1 + math.exp(-sum(w[n] * x[n] for n in names)))
            for n in names:
                grad[n] += (p - y) * x[n] / len(rows)
        for n in names:
            w[n] -= lr * grad[n]
    return w


def _predict(w, x):
    return 1 / (1 + math.exp(-sum(w.get(n, 0) * v for n, v in x.items())))


def _fold(template):
    return int(hashlib.sha256(template.encode()).hexdigest()[:8], 16) % FOLDS


def _outcomes(name, split):
    """case -> list over trials of (accepted, record)."""
    by_case = defaultdict(list)
    for trial in load_trials(name, split):
        for r in trial:
            by_case[r["case"]].append(r)
    return by_case


def _plan_costs(cases):
    from ..database import Database
    db, costs = Database(), {}
    for case in cases:
        try:
            costs[case["id"]] = db.plan(case["sql"])["Plan"]["Total Cost"]
        except Exception:  # noqa: BLE001
            costs[case["id"]] = 0.0
    return costs


def train(split="dev", stages=STAGES + ("frontier-harness",)):
    from .cases import load_cases
    cases, _ = load_cases(split)
    costs = _plan_costs(cases)
    X = {c["id"]: features(c, costs[c["id"]]) for c in cases}
    model = {"stages": {}, "folds": {}, "features": sorted(next(iter(X.values())))}
    for stage in stages[1:]:
        outcomes = _outcomes(stage, split)
        if not outcomes:
            continue
        ids = [c["id"] for c in cases if c["id"] in outcomes]
        labels = {i: sum(r["outcome"] == "accepted" for r in outcomes[i]) / len(outcomes[i]) for i in ids}
        model["stages"][stage] = _fit([X[i] for i in ids], [labels[i] for i in ids])
        template = {c["id"]: c["template"] for c in cases}
        for k in range(FOLDS):
            train_ids = [i for i in ids if _fold(template[i]) != k]
            model["folds"].setdefault(stage, {})[str(k)] = _fit([X[i] for i in train_ids], [labels[i] for i in train_ids])
    MODEL.write_text(json.dumps(model, indent=2) + "\n")
    return {"stages": list(model["stages"]), "cases": len(cases)}


def router_for(config):
    if not MODEL.exists():
        raise FileNotFoundError("Train the router first: python -m surgeon.eval train-router")
    return LearnedRouter(json.loads(MODEL.read_text()))


class LearnedRouter:
    def __init__(self, model, threshold=0.15, cross_fit=True):
        self.model, self.threshold, self.cross_fit = model, threshold, cross_fit
        self._costs = {}

    def probabilities(self, case, plan_cost):
        x = features(case, plan_cost)
        out = {}
        for stage, weights in self.model["stages"].items():
            if self.cross_fit and case.get("split") == "dev":
                weights = self.model["folds"][stage][str(_fold(case["template"]))]
            out[stage] = _predict(weights, x)
        return out

    def plan(self, case, plan_cost):
        """Stage names to run. Rules always run (free); model stages need p >= threshold."""
        p = self.probabilities(case, plan_cost)
        return ["rules-only"] + [s for s, v in p.items() if v >= self.threshold]

    def select(self, case, stages):
        if case["id"] not in self._costs:
            self._costs.update(_plan_costs([case]))
        wanted = self.plan(case, self._costs[case["id"]])
        return [s for s in stages if s.config.name in wanted]


def simulate(stage_names, split="dev", router=None, cases=None):
    """Exact cascade replay from standalone stage runs -> trials of records."""
    from .cases import load_cases
    cases = cases or load_cases(split)[0]
    runs = {name: _outcomes(name, split) for name in stage_names}
    costs = _plan_costs(cases) if router else {}
    trials = defaultdict(list)
    for case in cases:
        order = router.plan(case, costs[case["id"]]) if router else stage_names
        order = [n for n in stage_names if n in order]
        n_trials = min((len(runs[n][case["id"]]) for n in order if case["id"] in runs[n]), default=0)
        for t in range(n_trials):
            latency, cost, calls, final, complete = 0.0, 0.0, 0, None, True
            for name in order:
                if case["id"] not in runs[name] or len(runs[name][case["id"]]) <= t:
                    complete = False  # a stage this case reaches was never run
                    break
                r = runs[name][case["id"]][t]
                latency += r["latency_ms"]
                cost = None if cost is None or r["cost_usd"] is None else cost + r["cost_usd"]
                calls += r["calls"]
                final = r
                if r["outcome"] != "no_change":
                    break
            if not complete:
                continue
            record = dict(final) if final else {"outcome": "no_change", "speedup": 1.0, "candidates": []}
            record.update(case=case["id"], kind=case["kind"], family=case["family"], latency_ms=latency,
                          cost_usd=cost if final else 0.0, calls=calls, simulated=True, stages=order)
            trials[t].append(record)
    return [trials[t] for t in sorted(trials)]


CASCADES = {
    "cascade-open": ("rules-only", "oss20b-harness", "oss120b-harness"),
    "cascade-hybrid": ("rules-only", "oss20b-harness", "oss120b-harness", "frontier-harness"),
    # Groq-free path used by the demo; must match registry.systems() cascade-local.
    "cascade-local": ("rules-only", "ollama-gpt-oss-20b-harness"),
    # Fireworks prize path (no dedicated deploy required — serverless stages only).
    "cascade-open-fw": ("rules-only", "open-harness"),
    "cascade-nemotron": ("rules-only", "open-harness", "fw-nemotron-harness"),
    "cascade-surgeon": ("rules-only", "fw-fast-harness", "fw-nemotron-harness"),
    "cascade-oss-fw": ("rules-only", "fw-gpt-oss-harness"),
}
THRESHOLDS = (0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.45, 0.6, 1.01)


def write_cascades(split="dev"):
    """Replay cascades and router sweeps into run files and routing_curve.json."""
    from .metrics import summarize
    from .runner import RUNS
    from .report import OUT
    curve = {}
    model = json.loads(MODEL.read_text()) if MODEL.exists() else None
    for name, stage_names in CASCADES.items():
        # Skip cascades whose stage runs are not on disk yet (e.g. Groq paused).
        if any(not _outcomes(s, split) for s in stage_names):
            continue
        trials = simulate(stage_names, split)
        _write_runs(RUNS / name, split, trials)
        if not model:
            continue
        points = []
        for threshold in THRESHOLDS:
            sub = {"stages": {s: w for s, w in model["stages"].items() if s in stage_names},
                   "folds": {s: f for s, f in model["folds"].items() if s in stage_names}}
            if not sub["stages"]:
                continue
            router = LearnedRouter(sub, threshold, cross_fit=(split == "dev"))
            routed = simulate(stage_names, split, router)
            summary = summarize(routed)
            if not summary or summary.get("cost_per_case_usd") is None:
                continue
            points.append({"label": f"t={threshold}", "threshold": threshold,
                           "accepted_rate": summary["accepted_rate"],
                           "cost_per_case_usd": summary["cost_per_case_usd"],
                           "latency_p50_ms": summary["latency_p50_ms"],
                           "latency_p95_ms": summary["latency_p95_ms"],
                           "incorrect_returned_count": summary["incorrect_returned_count"]})
            if threshold == 0.15:
                _write_runs(RUNS / name.replace("cascade", "router"), split, routed)
        key = {"cascade-open": "open", "cascade-hybrid": "hybrid", "cascade-local": "local"}.get(name, name)
        curve[key] = points
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / ("routing_curve.json" if split == "dev" else f"routing_curve_{split}.json")
    path.write_text(json.dumps(curve, indent=2) + "\n")
    return curve


def _write_runs(directory, split, trials):
    directory.mkdir(parents=True, exist_ok=True)
    for old in directory.glob(f"{split}_t*.jsonl"):
        old.unlink()
    for t, records in enumerate(trials):
        (directory / f"{split}_t{t}.jsonl").write_text("".join(json.dumps(r, default=str) + "\n" for r in records))
