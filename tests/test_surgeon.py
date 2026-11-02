import json
import unittest
import argparse
import io
import tempfile
import urllib.error
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch

from surgeon.database import Database, equivalent, validate_sql, unique_columns
from surgeon.providers import parse_generation, Provider, request_json
from surgeon.workload import CASES
from surgeon.__main__ import run


class CorrectnessTests(unittest.TestCase):
    def test_decimal_precision_cannot_hide_a_changed_value(self):
        first = Decimal("0.12345678901234567891")
        second = Decimal("0.12345678901234567892")
        self.assertEqual(float(first), float(second))
        self.assertFalse(equivalent([{"amount": first}], [{"amount": second}]))
        self.assertTrue(equivalent([{"amount": Decimal("1.00")}], [{"amount": 1}]))
        self.assertFalse(equivalent([{"amount": True}], [{"amount": 1}]))

    def test_quoted_functions_and_session_mutation_are_rejected(self):
        for sql in ['SELECT "pg_sleep"(1)', "SELECT set_config('statement_timeout', '0', false)",
                    "SELECT nextval('orders_id_seq')", "SELECT 1 /* outer /* nested */ */"]:
            with self.subTest(sql=sql), self.assertRaises(ValueError):
                validate_sql(sql)

    def test_empty_results_still_require_matching_columns(self):
        db = Database()
        with patch.object(db, "columns", side_effect=[["id"], ["wrong"]]), patch.object(db, "rows") as rows:
            self.assertFalse(db.check("SELECT id FROM orders WHERE false", "SELECT id AS wrong FROM orders WHERE false")["equivalent"])
            rows.assert_not_called()

    def test_row_parser_preserves_decimal_precision(self):
        with patch.object(Database, "execute", return_value='[{"x":0.12345678901234567891}]'):
            self.assertEqual(Database().rows("SELECT 1 AS x")[0]["x"], Decimal("0.12345678901234567891"))

    def test_duplicate_column_names_cannot_be_silently_dropped(self):
        with self.assertRaises(ValueError):
            json.loads('[{"id":1,"id":2}]', object_pairs_hook=unique_columns)
    def test_duplicates_are_not_sets(self):
        self.assertFalse(equivalent([{"id": 1}, {"id": 1}], [{"id": 1}]))

    def test_null_is_not_zero_or_empty(self):
        for value in (0, "", "null"):
            self.assertFalse(equivalent([{"x": None}], [{"x": value}]))

    def test_unordered_bags_and_column_names(self):
        self.assertTrue(equivalent([{"a": 1}, {"a": 2}], [{"a": 2}, {"a": 1}]))
        self.assertFalse(equivalent([{"a": 1}], [{"b": 1}]))

    def test_rejects_mutation_multiple_statements_and_escape(self):
        for sql in ["DELETE FROM orders", "SELECT 1; DROP TABLE orders", "WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x", "SELECT pg_read_file('/etc/passwd')", "SELECT $$hello$$", "SELECT 1 INTO temp t", "SELECT 1\\gexec"]:
            with self.subTest(sql=sql), self.assertRaises(ValueError):
                validate_sql(sql)

    def test_literals_comments_and_single_trailing_semicolon(self):
        self.assertEqual(validate_sql("SELECT ';DROP TABLE' AS x;"), "SELECT ';DROP TABLE' AS x")
        self.assertEqual(validate_sql("SELECT 1 /* update */"), "SELECT 1 /* update */")


class ProviderTests(unittest.TestCase):
    def test_discovery_http_error_identifies_provider_without_leaking_body_or_retrying(self):
        secret = "private-key-and-error-body"
        error = urllib.error.HTTPError("https://api.groq.com/openai/v1/models", 403,
                                       "Forbidden", {}, io.BytesIO(secret.encode()))
        with patch("surgeon.providers.urllib.request.urlopen", side_effect=error) as send:
            with self.assertRaisesRegex(RuntimeError, r"api\.groq\.com HTTP 403 during model discovery") as raised:
                request_json("https://api.groq.com/openai/v1/models", secret)
        send.assert_called_once()
        self.assertNotIn(secret, str(raised.exception))
        request = send.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), "database-surgeon/0.1")

    def test_responses_output_and_cached_cost(self):
        raw = {"status": "completed", "model": "pinned-model", "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps({"sql": "SELECT 1", "rationale": "test"})}]}],
            "usage": {"input_tokens": 100, "output_tokens": 10, "input_tokens_details": {"cached_tokens": 40}}}
        with patch.dict("os.environ", {"OPENAI_INPUT_PRICE": "2", "OPENAI_CACHED_PRICE": "1", "OPENAI_OUTPUT_PRICE": "4"}):
            result = parse_generation("openai", "requested", raw)
        self.assertEqual(result.model, "pinned-model")
        self.assertAlmostEqual(result.cost_usd, 0.0002)

    def test_groq_usage_and_truncation(self):
        raw = {"model": "openai/gpt-oss-120b", "choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps({"sql": "SELECT 1", "rationale": "test"})}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8}}
        self.assertEqual(parse_generation("groq", "x", raw).input_tokens, 12)
        raw["choices"][0]["finish_reason"] = "length"
        with self.assertRaises(ValueError):
            parse_generation("groq", "x", raw)

    def test_missing_price_is_not_free(self):
        raw = {"status": "completed", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": '{"sql":"SELECT 1","rationale":"x"}'}]}], "usage": {"input_tokens": 1, "output_tokens": 1}}
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(parse_generation("openai", "x", raw).cost_usd)

    def test_mock_is_labeled_and_reproducible(self):
        result = Provider("mock").generate(CASES[0], {}, [])
        self.assertEqual(result.model, "mock-fixture")
        self.assertIn("TIMESTAMP", result.sql)

    def test_refusal_and_invalid_schema(self):
        for parts in [[{"type": "refusal", "refusal": "no"}], [{"type": "output_text", "text": '{"sql":1}'}]]:
            with self.assertRaises(ValueError):
                parse_generation("openai", "x", {"status": "completed", "output": [{"type": "message", "content": parts}]})


class HarnessTests(unittest.TestCase):
    def test_mock_run_records_rejection_and_measured_acceptance(self):
        class FixtureDatabase:
            def __init__(self, *args):
                pass

            def execute(self, sql):
                return "16-test"

            def preflight(self):
                return {"version": "16-test", "role": "surgeon_reader", "fixtures": {}}

            def columns(self, sql):
                return ["id"]

            def rows(self, sql, schema):
                return []

            def plan(self, sql):
                return {"Plan": {"Node Type": "Fixture"}}

            def check(self, original, candidate):
                return {"equivalent": "NOT IN" not in original}

            def benchmark(self, original, candidate, repeats):
                return {"reduction": 0.5, "original_ms": 2, "candidate_ms": 1}

        args = argparse.Namespace(provider="mock", model=None, max_output_tokens=2048,
                                  timeout_ms=5000, case=None, attempts=1, repeats=3, min_reduction=0.2)
        with tempfile.TemporaryDirectory() as directory:
            with patch("surgeon.__main__.ROOT", Path(directory)), patch("surgeon.__main__.Database", FixtureDatabase), patch("builtins.print"):
                run(args)
            output = next((Path(directory) / "results").iterdir())
            summary = json.loads((output / "summary.json").read_text())
            self.assertTrue(summary["mock"])
            self.assertEqual(summary["accepted"], 2)
            self.assertEqual(summary["incorrect_candidates_rejected"], 1)
            self.assertIsNone(summary["estimated_model_cost_usd"])
            self.assertEqual(len(list(output.glob("*.json"))), 6)
            self.assertTrue((output / "evaluator_sources.json").exists())
            self.assertEqual(summary["state"], "completed")
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["selected_cases"], [c["id"] for c in CASES])
            self.assertIn("fixture_sha256", manifest)
            self.assertIn("evaluator_sha256", manifest)


if __name__ == "__main__":
    unittest.main()
