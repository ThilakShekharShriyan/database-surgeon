import argparse
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from surgeon.config import load_env
from surgeon.database import Database
from surgeon.lab import lab_cases, suite_cases
from surgeon.service import validate_request


class LabTests(unittest.TestCase):
    def test_missing_replay_never_falls_through_to_live_inference(self):
        from surgeon.service import optimize_query
        with patch("surgeon.service._replay_eval_trace", return_value=None), patch(
                "surgeon.eval.systems.System") as system:
            with self.assertRaisesRegex(ValueError, "No recorded replay"):
                optimize_query({"sql": "SELECT 987654 AS unrecorded", "replay": True})
            system.assert_not_called()

    def test_environment_replay_mode_also_fails_closed(self):
        from surgeon.service import optimize_query
        with patch.dict(os.environ, {"DEMO_REPLAY": "1"}), patch(
                "surgeon.service._replay_eval_trace", return_value=None):
            with self.assertRaisesRegex(ValueError, "No recorded replay"):
                optimize_query({"sql": "SELECT 987654 AS unrecorded"})

    def test_public_variants_keep_shared_lineage_and_no_reference_in_prompt(self):
        public = [case for case in lab_cases() if case["id"].startswith("tpch_q17")]
        self.assertEqual(len(public), 2)
        self.assertEqual(public[0]["template_id"], public[1]["template_id"])
        self.assertTrue(all(len(c["source_commit"]) == 40 for c in public))
        self.assertEqual(len(suite_cases("all")), 14)

    def test_service_rejects_unbounded_and_unknown_models(self):
        for request in ({"attempts": 99}, {"provider": "shell"}, {"model": "anything"},
                        {"suite": "pilot", "case": "tpch_q17_0"}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                validate_request(request)

    def test_lab_type_check_rejects_same_values_with_changed_sql_type(self):
        db = Database()
        db.enforce_types = True
        with patch.object(db, "columns", return_value=["x"]), patch.object(
                db, "execute", side_effect=["Column,Type\nx,integer", "Column,Type\nx,bigint"]):
            self.assertFalse(db.check("SELECT 1 AS x", "SELECT 1::bigint AS x")["equivalent"])


@unittest.skipUnless(os.getenv("SURGEON_TEST_DATABASE") == "1", "requires seeded local PostgreSQL")
class LabIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_env()
        cls.db = Database()
        cls.db.enforce_types = True

    def test_all_admitted_originals_execute_on_all_fixtures(self):
        for case in lab_cases():
            with self.subTest(case=case["id"]):
                self.db.columns(case["sql"])
                for schema in ("bench", "check_a", "check_b", "check_nonnull", "check_empty"):
                    self.db.rows(case["sql"], schema)

    def test_empty_public_query_and_nonempty_q17_are_not_vacuous(self):
        self.assertTrue(self.db.rows(next(c for c in lab_cases() if c["id"] == "tpch_q17_0")["sql"]))
        self.assertTrue(self.db.rows("SELECT * FROM emp"))
        self.assertFalse(self.db.rows("SELECT * FROM emp", "check_empty"))

    def test_public_table_fingerprints_and_types(self):
        info = self.db.preflight()
        self.assertEqual(info["fixtures"]["bench"]["lineitem"]["rows"], 50000)
        self.assertFalse(self.db.check("SELECT 1 AS x", "SELECT 1::bigint AS x")["equivalent"])


class QuotaTests(unittest.TestCase):
    def test_rate_reset_units(self):
        from surgeon.providers import reset_seconds
        self.assertAlmostEqual(reset_seconds("1m2s500ms"), 62.5)
        self.assertEqual(reset_seconds(None), 0)

    def test_provider_failure_blocks_remaining_cases_without_losing_denominator(self):
        import tempfile
        from test_operations import FixtureDatabase, arguments
        from surgeon.__main__ import run
        with tempfile.TemporaryDirectory() as directory:
            with patch("surgeon.__main__.ROOT", Path(directory)), patch("surgeon.__main__.Database", FixtureDatabase), patch("surgeon.__main__.Provider.generate", side_effect=RuntimeError("HTTP 429")) as generate, patch("builtins.print"):
                _, summary = run(arguments(case=None))
            self.assertEqual(generate.call_count, 1)
            self.assertEqual(summary["cases"], 3)
            self.assertEqual(summary["not_attempted"], 2)
            self.assertEqual(summary["state"], "failed")

    def test_quota_wait_occurs_before_next_request_without_replaying(self):
        from surgeon.providers import Provider, RATE_STATE
        model = "openai/gpt-oss-120b"
        state = ("api.groq.com", model)
        raw = {"model": model, "choices": [{"finish_reason": "stop", "message": {"content": '{"sql":"SELECT 1","rationale":"unchanged"}'}}], "usage": {}}
        with patch.dict("os.environ", {"GROQ_API_KEY": "test", "GROQ_MODEL": model}, clear=True), patch("surgeon.providers.request_json", return_value=raw) as request, patch("surgeon.providers.time.sleep") as sleep, patch("surgeon.providers.time.monotonic", return_value=10):
            RATE_STATE[state] = {"remaining_tokens": 0, "reset_at": 12}
            try:
                Provider("groq", model).generate({"sql": "SELECT 1"}, {"schema": "", "plan": {}}, [])
                request.assert_called_once()
                sleep.assert_called_once_with(2.5)
            finally:
                RATE_STATE.pop(state, None)


class CredentialRotationTests(unittest.TestCase):
    def test_deduplicated_pool_rotates_only_explicit_429(self):
        from surgeon.providers import Provider, ProviderHTTPError, credential_pool, KEY_CURSOR
        raw = {"model": "openai/gpt-oss-20b", "choices": [{"finish_reason": "stop", "message": {"content": '{"sql":"SELECT 1","rationale":"test"}'}}], "usage": {"prompt_tokens": 2, "completion_tokens": 2}}
        env = {"GROQ_API_KEY": "key-a", "GROQ_API_KEY2": "key-b", "GROQ_API_KEY3": "key-b", "GROQ_API_KEY4": "key-c"}
        with patch.dict("os.environ", env, clear=True), patch("surgeon.providers.request_json", side_effect=[ProviderHTTPError("HTTP 429",429),raw]) as request:
            KEY_CURSOR.clear()
            self.assertEqual(len(credential_pool("groq")),3)
            result = Provider("groq","openai/gpt-oss-20b").generate({"sql":"SELECT 1"},{"schema":"","plan":{}},[])
            self.assertEqual(request.call_count,2)
            self.assertEqual([a["http_status"] for a in result.request_attempts],[429,200])
            self.assertIsNone(result.cost_usd)
            self.assertNotIn("key-a",str(result.request_attempts))

    def test_uncertain_network_failure_is_not_rotated(self):
        from surgeon.providers import Provider, KEY_CURSOR
        with patch.dict("os.environ", {"GROQ_API_KEY":"key-a","GROQ_API_KEY2":"key-b"}, clear=True), patch("surgeon.providers.request_json", side_effect=RuntimeError("network request failed")) as request:
            KEY_CURSOR.clear()
            with self.assertRaises(RuntimeError):
                Provider("groq","openai/gpt-oss-20b").generate({"sql":"SELECT 1"},{"schema":"","plan":{}},[])
            request.assert_called_once()
