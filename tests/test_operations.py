import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from surgeon.__main__ import run, main
from surgeon.artifacts import evaluation_lock, persist
from surgeon.reporting import build_report, comparison_key
from surgeon.workload import CASES


class FixtureDatabase:
    def __init__(self, *args):
        pass

    def preflight(self):
        return {"version": "16-test", "role": "surgeon_reader", "fixtures": {}}

    def columns(self, sql):
        return ["id"]

    def rows(self, sql, schema):
        return []

    def plan(self, sql):
        return {"Plan": {"Node Type": "Fixture"}}

    def check(self, original, candidate):
        return {"equivalent": True}

    def benchmark(self, original, candidate, repeats):
        return {"reduction": 0.5, "original_ms": 2, "candidate_ms": 1, "speedup": 2}


def arguments(**overrides):
    values = dict(provider="mock", model=None, max_output_tokens=2048, timeout_ms=5000,
                  case=CASES[0]["id"], attempts=1, repeats=3, min_reduction=0.2)
    values.update(overrides)
    return argparse.Namespace(**values)


class CheckpointTests(unittest.TestCase):
    def test_concurrent_evaluation_is_rejected_before_database_or_provider_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with evaluation_lock(root), patch("surgeon.__main__.ROOT", root), \
                    patch("surgeon.__main__.Database") as database, \
                    patch("surgeon.__main__.Provider") as provider:
                with self.assertRaisesRegex(RuntimeError, "Another evaluation is running"):
                    run(arguments())
                database.assert_not_called()
                provider.assert_not_called()
    def test_failed_serialization_preserves_existing_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            persist(path, {"complete": True})
            with self.assertRaises(ValueError):
                persist(path, {"number": float("nan")})
            self.assertEqual(json.loads(path.read_text()), {"complete": True})
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_database_failure_prevents_provider_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("surgeon.__main__.ROOT", Path(directory)), \
                    patch("surgeon.__main__.Database.preflight", side_effect=RuntimeError("unavailable")), \
                    patch("surgeon.__main__.Provider.generate") as generate:
                with self.assertRaisesRegex(RuntimeError, "unavailable"):
                    run(arguments())
                generate.assert_not_called()

    def test_invalid_budget_prevents_any_database_or_provider_work(self):
        with patch("surgeon.__main__.Database") as database, patch("surgeon.__main__.Provider") as provider:
            with self.assertRaises(ValueError):
                run(arguments(attempts=0))
            database.assert_not_called()
            provider.assert_not_called()

    def test_interrupt_preserves_successful_generation_and_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("surgeon.__main__.ROOT", Path(directory)), \
                    patch("surgeon.__main__.Database", FixtureDatabase), \
                    patch.object(FixtureDatabase, "check", side_effect=KeyboardInterrupt), patch("builtins.print"):
                with self.assertRaises(KeyboardInterrupt):
                    run(arguments())
            output = next((Path(directory) / "results").iterdir())
            case = json.loads((output / "date_filter.json").read_text())
            manifest = json.loads((output / "manifest.json").read_text())
            summary = json.loads((output / "summary.json").read_text())
            self.assertIn("generation", case["attempts"][0])
            self.assertEqual(manifest["state"], "interrupted")
            self.assertEqual(summary["unfinished_attempts"], 1)
            self.assertFalse(summary["cost_complete"])

    def test_provider_failure_is_not_retried_and_run_is_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("surgeon.__main__.ROOT", Path(directory)), \
                    patch("surgeon.__main__.Database", FixtureDatabase), \
                    patch("surgeon.__main__.Provider.generate", side_effect=RuntimeError("API failed")) as generate, \
                    patch("builtins.print"):
                _, summary = run(arguments(attempts=3))
            generate.assert_called_once()
            self.assertEqual(summary["state"], "failed")
            self.assertEqual(summary["errors"], 1)
            self.assertIsNone(summary["estimated_model_cost_usd"])

    def test_unchanged_candidate_is_checkpointed(self):
        from surgeon.providers import Generation
        with tempfile.TemporaryDirectory() as directory:
            with patch("surgeon.__main__.ROOT", Path(directory)), \
                    patch("surgeon.__main__.Database", FixtureDatabase), \
                    patch("surgeon.__main__.Provider.generate", return_value=Generation(CASES[0]["sql"], "unchanged", "test")), \
                    patch("builtins.print"):
                output, summary = run(arguments())
            case = json.loads((output / "date_filter.json").read_text())
            self.assertEqual(case["attempts"][0]["status"], "no_change")
            self.assertEqual(summary["unfinished_attempts"], 0)

    def test_doctor_exits_nonzero_for_unavailable_database(self):
        with patch("sys.argv", ["surgeon", "doctor", "--json"]), \
                patch("surgeon.__main__.Database.preflight", side_effect=RuntimeError("connection denied")), \
                patch("builtins.print"):
            self.assertEqual(main(), 1)


class ReportTests(unittest.TestCase):
    def test_different_budgets_fixtures_and_mock_status_cannot_share_a_group(self):
        manifest = dict(artifact_version=2, run_id="test", max_attempts=1, mock=False,
                        selected_cases=["date_filter"], database={"fixtures": "a"})
        for key, value in (("max_attempts", 3), ("mock", True), ("selected_cases", ["nullable_antijoin"]),
                           ("database", {"fixtures": "b"}), ("evaluator_sha256", "changed")):
            with self.subTest(key=key):
                self.assertNotEqual(comparison_key(manifest), comparison_key(dict(manifest, **{key: value})))
        self.assertEqual(comparison_key(manifest), comparison_key(dict(manifest, provider="groq", requested_model="different")))

    def test_report_labels_mock_legacy_unknown_cost_and_corrupt_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            persist(root / "legacy" / "manifest.json", dict(run_id="legacy", provider="mock", mock=True))
            persist(root / "legacy" / "summary.json", dict(run_id="legacy", cases=1, accepted=0, estimated_model_cost_usd=None))
            (root / "broken").mkdir()
            (root / "broken" / "manifest.json").write_text("{")
            output = root / "report.md"
            result = build_report(root, output)
            report = output.read_text()
            self.assertEqual(result["runs"], 1)
            self.assertEqual(result["skipped"], 1)
            self.assertIn("legacy/unverified", report)
            self.assertIn("unknown", report)
            self.assertIn("not model-performance evidence", report)
            self.assertTrue(output.with_suffix(".json").exists())


class WatchTests(unittest.TestCase):
    def test_single_cycle_checks_only_mock_and_persists_health(self):
        from surgeon.watch import watch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = arguments(interval=10, cycles=1)
            def mock_run(received):
                self.assertEqual(received.provider, "mock")
                return root / "results" / "fixture", {"errors": 0}
            with patch("surgeon.watch.ROOT", root), \
                    patch("surgeon.watch.subprocess.run") as checks, patch("builtins.print"):
                checks.return_value = argparse.Namespace(returncode=0, stdout="", stderr="passed")
                state = watch(args, mock_run)
            self.assertEqual(state["last_check"], "healthy")
            self.assertEqual(state["cycles"], 1)
            self.assertEqual(json.loads((root / ".local" / "watch.json").read_text())["state"], "finished")

    def test_failed_unit_checks_skip_database_benchmark(self):
        from surgeon.watch import watch
        with tempfile.TemporaryDirectory() as directory:
            with patch("surgeon.watch.ROOT", Path(directory)), \
                    patch("surgeon.watch.subprocess.run") as checks, patch("builtins.print"), \
                    patch("surgeon.__main__.run") as benchmark:
                checks.return_value = argparse.Namespace(returncode=1, stdout="", stderr="failed")
                state = watch(arguments(interval=10, cycles=1), benchmark)
                benchmark.assert_not_called()
            self.assertEqual(state["last_check"], "tests_failed")


class VerifyTests(unittest.TestCase):
    def verify(self, data, database=FixtureDatabase):
        from surgeon.service import verify_candidate
        with tempfile.TemporaryDirectory() as directory, patch("surgeon.service.ROOT", Path(directory)):
            return verify_candidate(data, database)

    def test_only_admitted_queries_can_be_verified(self):
        with self.assertRaisesRegex(ValueError, "admitted"):
            self.verify({"case": "not_a_case", "candidate": "SELECT 1"})

    def test_candidate_must_pass_the_select_guard(self):
        with self.assertRaises(ValueError):
            self.verify({"case": CASES[0]["id"], "candidate": "DELETE FROM orders"})

    def test_correct_faster_candidate_is_accepted(self):
        result = self.verify({"case": CASES[0]["id"], "candidate": CASES[0]["mock_sql"]})
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["benchmark"]["speedup"], 2)

    def test_incorrect_candidate_is_not_timed(self):
        class Mismatch(FixtureDatabase):
            def check(self, original, candidate):
                return {"equivalent": False, "reason": "Result mismatch on an evaluation instance."}
            def benchmark(self, *args):
                raise AssertionError("An incorrect candidate must not be timed.")
        result = self.verify({"case": CASES[2]["id"], "candidate": CASES[2]["mock_sql"]}, Mismatch)
        self.assertEqual(result["status"], "incorrect")
        self.assertNotIn("benchmark", result)

    def test_unchanged_query_is_not_evaluated(self):
        result = self.verify({"case": CASES[0]["id"], "candidate": CASES[0]["sql"]})
        self.assertEqual(result["status"], "no_change")
