import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from surgeon.eval.comparison import compare, mcnemar
from surgeon.eval.report import write_report


def row(case, outcome="accepted", trial=0, cost=0.001, latency=10):
    return {"case": case, "trial": trial, "outcome": outcome, "cost_usd": cost,
            "latency_ms": latency, "speedup": 2.0, "kind": "rewrite", "family": "f",
            "calls": 1, "config_hash": "frozen", "cases_sha256": "cases"}


CASES = [{"id": name, "template": template, "split": "dev"}
         for name, template in (("a", "t1"), ("b", "t1"), ("c", "t2"))]


class McNemarTests(unittest.TestCase):
    def test_exact_known_tail_and_orientation(self):
        test = mcnemar([True] * 6 + [False], [False] * 6 + [False])
        self.assertEqual(test["table"], [[1, 0], [6, 0]])
        self.assertEqual(test["a_only"], 6)
        self.assertAlmostEqual(test["p_value"], 0.03125)

    def test_symmetry_and_ties(self):
        self.assertEqual(mcnemar([True, False], [False, True])["p_value"], 1.0)
        self.assertEqual(mcnemar([True], [True])["p_value"], 1.0)
        self.assertIsNone(mcnemar([], [])["p_value"])
        a, b = [True] * 10, [False] * 8 + [True] * 2
        self.assertEqual(mcnemar(a, b)["p_value"], mcnemar(b, a)["p_value"])

    def test_no_fractional_or_unpaired_inputs(self):
        with self.assertRaises(ValueError):
            mcnemar([True], [])
        with self.assertRaises(ValueError):
            mcnemar([0.5], [True])


class ComparisonTests(unittest.TestCase):
    def test_matches_ids_and_uses_declared_trial(self):
        a = [[row("a"), row("b", "no_change"), row("c")],
             [row("a", "no_change", trial=1)]]
        b = [[row("c", "no_change"), row("b"), row("a")]]
        result = compare(a, b, CASES)
        self.assertTrue(result["complete"])
        self.assertEqual(result["pairs"], 3)
        self.assertEqual(result["mcnemar"]["accepted"]["a_only"], 1)
        self.assertEqual(result["mcnemar"]["accepted"]["baseline_only"], 1)

    def test_partial_cases_and_incomplete_templates_disclosed(self):
        result = compare([[row("a"), row("c")]], [[row("a"), row("b"), row("c")]], CASES)
        self.assertFalse(result["complete"])
        self.assertEqual(result["missing_a"], ["b"])
        self.assertEqual(result["pairs"], 2)
        self.assertEqual(result["mcnemar"]["accepted"]["template_sensitivity"]["pairs"], 1)

    def test_duplicate_case_trial_rejected(self):
        with self.assertRaises(ValueError):
            compare([[row("a"), row("a")]], [], CASES)

    def test_cost_missing_and_zero_baseline(self):
        result = compare([[row("a", cost=None), row("b", cost=0.1)]],
                         [[row("a"), row("b", cost=0)]], CASES)
        cost = result["paired_metrics"]["cost_usd"]
        self.assertEqual(cost["pairs"], 1)
        self.assertEqual(cost["excluded_pairs"], 1)
        self.assertEqual(cost["mean_difference"], 0.1)
        self.assertIsNone(cost["ratio_of_means_a_over_baseline"])
        self.assertIsNone(cost["difference_ci95_template_bootstrap"])

    def test_latency_ratio_and_cluster_interval(self):
        result = compare([[row(c["id"], latency=10) for c in CASES]],
                         [[row(c["id"], latency=20) for c in CASES]], CASES)
        metric = result["paired_metrics"]["latency_ms"]
        self.assertEqual(metric["ratio_of_means_a_over_baseline"], 0.5)
        self.assertEqual(metric["difference_ci95_template_bootstrap"], [-10.0, -10.0])

    def test_template_safety_uses_any_incorrect_and_speed_excludes_wrong(self):
        result = compare([[row("a", "incorrect"), row("b"), row("c", "no_change")]],
                         [[row(c["id"]) for c in CASES]], CASES)
        test = result["mcnemar"]["incorrect_returned"]["template_sensitivity"]
        self.assertEqual(test["a_only"], 1)
        self.assertEqual(result["paired_metrics"]["speedup"]["pairs"], 2)
        self.assertEqual(result["paired_metrics"]["speedup"]["mean_a"], 1.5)

    def test_empty_trial_has_no_pvalue(self):
        result = compare([[row("a")]], [[row("a")]], CASES, trial=1)
        self.assertEqual(result["pairs"], 0)
        self.assertIsNone(result["mcnemar"]["accepted"]["p_value"])


class ReportTests(unittest.TestCase):
    def test_report_includes_tests_and_excludes_partial_pareto(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("baseline", "partial", "ours"):
                (root / name).mkdir()
            runs = {"baseline": [[row(c["id"], latency=20) for c in CASES]],
                    "ours": [[row(c["id"], latency=10) for c in CASES]],
                    "partial": [[row("a", cost=0, latency=0)]]}
            with patch("surgeon.eval.report.RUNS", root), \
                 patch("surgeon.eval.report.OUT", root / "out"), \
                 patch("surgeon.eval.report.load_cases", return_value=(CASES, "cases")), \
                 patch("surgeon.eval.report.load_trials", side_effect=lambda n, s: runs[n]):
                text = write_report(baseline="baseline")
            saved = json.loads((root / "out" / "summary_dev.json").read_text())
            self.assertIn("McNemar accepted", text)
            self.assertEqual(saved["baseline"], "baseline")
            self.assertNotIn("partial", saved["pareto_safe"])
            ours = next(r for r in saved["systems"] if r["system"] == "ours")
            self.assertEqual(ours["paired_comparison"]["pairs"], 3)


if __name__ == "__main__":
    unittest.main()
