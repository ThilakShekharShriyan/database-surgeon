import threading
import unittest

from surgeon.eval.llm import extract_json, price
from surgeon.eval.metrics import paired_difference, summarize
from surgeon.eval.systems import System, SystemConfig, retrieve, shape

try:
    import sqlglot  # noqa: F401
    from surgeon.eval.rules import apply_rules
except ImportError:  # the stdlib-only interpreter skips rule tests
    apply_rules = None


def record(case, outcome, speedup=1.0, kind="rewrite", latency=1000.0, cost=0.001):
    return {"case": case, "outcome": outcome, "speedup": speedup, "kind": kind, "family": "f",
            "latency_ms": latency, "cost_usd": cost, "calls": 1, "candidates": []}


class FakeClient:
    def __init__(self, answers):
        # Assign answers in first-seen sample order (locked) so parallel best_of
        # and sequential repair both stay deterministic per sample id.
        self.answers, self.calls = list(answers), 0
        self._map, self._lock = {}, threading.Lock()

    def complete(self, system, user, sample=0):
        with self._lock:
            self.calls += 1
            if sample not in self._map:
                used = len(self._map)
                self._map[sample] = self.answers[used] if used < len(self.answers) else None
            sql = self._map[sample]
        return {"sql": sql, "latency_ms": 100.0, "cost_usd": 0.001, "error": None if sql else "unparseable output"}


class FakeVerifier:
    def __init__(self, good):
        self.good, self.seen = good, []

    def verify(self, case, sql):
        self.seen.append(sql)
        ok = sql in self.good
        return {"ok": ok, "stage": "timing" if ok else "check", "reduction": 0.9 if ok else None,
                "feedback": "rows differ", "db_ms": 10.0}

    def plan_text(self, sql):
        return "Seq Scan", 1.0

    def plan_json(self, sql):
        return {"Plan": {"Node Type": "Seq Scan", "Total Cost": 100.0, "Plan Rows": 1000}}, 1.0

    def plan_cost(self, sql):
        return 100.0, 1.0

    def looks_already_optimal(self, plan):
        return False


CASE = {"id": "c", "sql": "SELECT 1 AS a", "schema_context": "t(a int)"}


def build(config, answers, good):
    system = System(config, FakeVerifier(good))
    system.client = FakeClient(answers)
    return system


class PipelineTests(unittest.TestCase):
    def test_raw_system_returns_first_answer_unverified(self):
        system = build(SystemConfig("raw", "local", "m"), ["SELECT 2 AS a"], set())
        self.assertEqual(system.run(CASE, 0)["result_sql"], "SELECT 2 AS a")
        self.assertEqual(system.verifier.seen, [])

    def test_verify_abstains_when_nothing_passes(self):
        system = build(SystemConfig("v", "local", "m", verify=True), ["SELECT 2 AS a"], set())
        trace = system.run(CASE, 0)
        self.assertEqual(trace["result_sql"], CASE["sql"])
        self.assertEqual(trace["candidates"][0]["stage"], "check")

    def test_repair_round_gets_feedback_and_can_succeed(self):
        system = build(SystemConfig("r", "local", "m", verify=True, repair=1),
                       ["SELECT 2 AS a", "SELECT 3 AS a"], {"SELECT 3 AS a"})
        trace = system.run(CASE, 0)
        self.assertEqual(trace["result_sql"], "SELECT 3 AS a")
        self.assertEqual(system.client.calls, 2)

    def test_best_of_returns_the_verified_sample(self):
        system = build(SystemConfig("b", "local", "m", verify=True, best_of=3, adaptive_best_of=True),
                       ["SELECT 2 AS a", "SELECT 4 AS a", "SELECT 2 AS a"], {"SELECT 4 AS a"})
        self.assertEqual(system.run(CASE, 0)["result_sql"], "SELECT 4 AS a")
        # Adaptive: first sample fails verify, then remaining two are drawn.
        self.assertEqual(system.verifier.seen.count("SELECT 2 AS a"), 1)
        self.assertIn("SELECT 4 AS a", system.verifier.seen)

    def test_first_win_stops_after_first_verified(self):
        system = build(
            SystemConfig("fw", "local", "m", verify=True, first_win=True),
            [],
            {"SELECT 4 AS a", "SELECT 5 AS a", "SELECT 6 AS a"},
        )
        trace = {"candidates": [], "verify_ms": 0.0}
        feedback = []
        ok = system._accepts(CASE, [
            {"sql": "SELECT 4 AS a", "origin": "model"},
            {"sql": "SELECT 5 AS a", "origin": "model"},
            {"sql": "SELECT 6 AS a", "origin": "model"},
        ], trace, feedback)
        self.assertTrue(ok)
        self.assertEqual(trace["accepted"], "SELECT 4 AS a")
        self.assertEqual(system.verifier.seen, ["SELECT 4 AS a"])

    def test_early_abstain_skips_model_on_index_lookup(self):
        class OptimalVerifier(FakeVerifier):
            def looks_already_optimal(self, plan):
                return True

        config = SystemConfig(
            "ea", "local", "m", verify=True, early_abstain=True, workload_cache=False,
        )
        system = System(config, OptimalVerifier(set()))
        system.client = FakeClient(["SELECT 2 AS a"])
        trace = system.run(CASE, 0)
        self.assertEqual(trace["result_sql"], CASE["sql"])
        self.assertEqual(system.client.calls, 0)
        self.assertTrue(any(c.get("stage") == "early_abstain" for c in trace["candidates"]))

    def test_cascade_stops_at_first_stage_that_changes_the_query(self):
        first = build(SystemConfig("s1", "local", "m", verify=True), ["SELECT 2 AS a"], set())
        second = build(SystemConfig("s2", "local", "m", verify=True), ["SELECT 5 AS a"], {"SELECT 5 AS a"})
        cascade = System(SystemConfig("cascade"), first.verifier)
        cascade.stages = [first, second]
        trace = cascade.run(CASE, 0)
        self.assertEqual(trace["result_sql"], "SELECT 5 AS a")
        self.assertEqual([s["changed"] for s in trace["stages"]], [False, True])


class MetricTests(unittest.TestCase):
    def test_summary_counts_incorrect_and_safe_decoys(self):
        trial = [record("a", "accepted", 4.0), record("b", "incorrect"),
                 record("d", "no_change", kind="decoy"), record("e", "regression", 0.5, kind="decoy")]
        summary = summarize([trial])
        self.assertEqual(summary["accepted_rate"], 0.25)
        self.assertEqual(summary["incorrect_returned_count"], 1)
        self.assertEqual(summary["decoy_safe_rate"], 0.5)
        self.assertAlmostEqual(summary["geomean_speedup"], (4.0 * 1 * 1 * 0.5) ** 0.25)

    def test_unknown_cost_stays_unknown(self):
        summary = summarize([[record("a", "accepted", 2.0, cost=None)]])
        self.assertIsNone(summary["cost_per_case_usd"])

    def test_paired_difference(self):
        a = [[record("x", "accepted", 2.0), record("y", "accepted", 2.0)]]
        b = [[record("x", "no_change"), record("y", "accepted", 2.0)]]
        diff = paired_difference(a, b)
        self.assertEqual(diff["mean"], 0.5)
        self.assertEqual(diff["cases"], 2)


class ParsingTests(unittest.TestCase):
    def test_extract_json_from_prose_and_fences(self):
        self.assertEqual(extract_json('{"sql": "SELECT 1"}')["sql"], "SELECT 1")
        self.assertEqual(extract_json('Sure: {"sql": "SELECT 1", "rationale": ""} done')["sql"], "SELECT 1")
        self.assertEqual(extract_json("```sql\nSELECT 1\n```")["sql"].strip(), "SELECT 1")
        self.assertIsNone(extract_json("no sql here"))

    def test_price_uses_sourced_table_or_unknown(self):
        self.assertAlmostEqual(price("groq", "openai/gpt-oss-20b", 1_000_000, 0, 1_000_000), 0.375)
        self.assertEqual(price("local", "my-model", 10, 0, 10), 0.0)
        self.assertIsNone(price("fireworks", "unpriced-model", 10, 0, 10))

    def test_retrieval_prefers_same_shape(self):
        memory = [{"original": q, "rewrite": q, "verdict": "x", "shape": shape(q)} for q in (
            "SELECT id FROM orders WHERE to_char(created_at, 'YYYY') = '1'",
            "SELECT name FROM customers WHERE id = 3")]
        top = retrieve(memory, "SELECT id FROM orders WHERE to_char(created_at, 'YYYY') = '9'", 1)
        self.assertIn("to_char", top[0]["query"])


@unittest.skipIf(apply_rules is None, "sqlglot not installed in this interpreter")
class RuleTests(unittest.TestCase):
    def test_day_and_month_ranges(self):
        sql, fired = apply_rules("SELECT id FROM orders WHERE created_at::date = DATE '2026-12-31'")
        self.assertEqual(fired, ["sargable_day"])
        self.assertIn("2027-01-01", sql)
        sql, fired = apply_rules("SELECT id FROM orders WHERE date_trunc('month', created_at) = TIMESTAMP '2026-12-01'")
        self.assertIn("2027-01-01", sql)

    def test_rules_do_not_fire_on_unsafe_patterns(self):
        for sql in ("SELECT id FROM orders WHERE coalesce(customer_id, -1) = -1",
                    "SELECT id FROM orders WHERE date_trunc('month', created_at) = TIMESTAMP '2026-03-15'",
                    "SELECT count(*) FROM (SELECT * FROM orders ORDER BY id LIMIT 5) t",
                    "SELECT DISTINCT customer_id FROM orders"):
            self.assertEqual(apply_rules(sql), (None, []), sql)


if __name__ == "__main__":
    unittest.main()
