"""Run after Compose + seed: SURGEON_TEST_DATABASE=1 python3 -m unittest discover -s tests -v"""
import os
import unittest

from surgeon.config import load_env
from surgeon.database import Database
from surgeon.workload import CASES


@unittest.skipUnless(os.getenv("SURGEON_TEST_DATABASE") == "1", "requires seeded local Postgres")
class DatabaseIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_env()
        cls.db = Database()
        # A blocked connection is not evidence of SQL correctness or permissions.
        cls.db.execute("SELECT 1")

    def test_date_rewrite_preserves_boundaries(self):
        case = CASES[0]
        self.assertTrue(self.db.check(case["sql"], case["mock_sql"])["equivalent"])

    def test_aggregate_rewrite_preserves_empty_customers(self):
        case = CASES[1]
        self.assertTrue(self.db.check(case["sql"], case["mock_sql"])["equivalent"])

    def test_null_antijoin_rewrite_is_rejected(self):
        case = CASES[2]
        self.assertFalse(self.db.check(case["sql"], case["mock_sql"])["equivalent"])

    def test_constant_empty_antijoin_cannot_exploit_all_null_fixtures(self):
        self.assertFalse(self.db.check(CASES[2]["sql"], "SELECT id FROM customers WHERE false")["equivalent"])

    def test_no_null_and_no_order_fixtures_exercise_antijoin(self):
        self.assertTrue(self.db.rows(CASES[2]["sql"], "check_nonnull"))
        self.assertEqual(len(self.db.rows(CASES[2]["sql"], "check_empty")), 1000)
        self.assertEqual(self.db.rows("SELECT customer_id FROM orders WHERE customer_id IS NULL", "check_nonnull"), [])

    def test_empty_result_with_changed_alias_is_rejected(self):
        self.assertFalse(self.db.check("SELECT id FROM orders WHERE false",
                                      "SELECT id AS wrong FROM orders WHERE false")["equivalent"])

    def test_exact_numeric_difference_is_rejected(self):
        self.assertFalse(self.db.check("SELECT 0.12345678901234567891::numeric AS amount",
                                      "SELECT 0.12345678901234567892::numeric AS amount")["equivalent"])

    def test_preflight_identifies_restricted_role_and_actual_fixture_content(self):
        metadata = self.db.preflight()
        self.assertEqual(metadata["role"], "surgeon_reader")
        self.assertEqual(metadata["fixtures"]["bench"]["orders"]["rows"], 50000)
        self.assertEqual(len(metadata["fixtures"]["bench"]["orders"]["md5"]), 32)

    def test_actual_role_cannot_write_even_without_application_guard(self):
        with self.assertRaisesRegex(RuntimeError, r"permission denied for table|cannot execute UPDATE in a read-only transaction"):
            self.db.execute("UPDATE customers SET name = 'should never happen' WHERE id = -9999")

    def test_benchmark_has_real_server_timing(self):
        case = CASES[0]
        report = self.db.benchmark(case["sql"], case["mock_sql"], repeats=3)
        self.assertEqual(len(report["samples_ms"]["candidate"]), 3)
        self.assertGreater(report["original_ms"], 0)

