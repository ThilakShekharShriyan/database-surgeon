import os
import unittest

from surgeon.database import Database, counterexample, equivalent, has_top_level_order
from surgeon.eval.cases import heldout_templates, load_cases, train_instances
from surgeon.eval.synth import TEMPLATES, instantiate
from surgeon.workload import EVAL_SCHEMAS, FIXTURE_SCHEMAS


class SplitTests(unittest.TestCase):
    def test_heldout_templates_never_reach_train_or_dev(self):
        held = heldout_templates()
        self.assertTrue(held)
        self.assertFalse({case["template"] for case in train_instances(2)} & held)
        dev, _ = load_cases("dev")
        self.assertFalse({case["template"] for case in dev} & held)

    def test_every_family_has_heldout_and_dev_templates(self):
        held = heldout_templates()
        for family in {t[1] for t in TEMPLATES}:
            names = {t[0] for t in TEMPLATES if t[1] == family}
            self.assertTrue(names & held, family)
            self.assertTrue(names - held, family)

    def test_instances_are_deterministic(self):
        self.assertEqual(instantiate(TEMPLATES[0], 3), instantiate(TEMPLATES[0], 3))
        self.assertNotEqual(instantiate(TEMPLATES[0], 3)["sql"], instantiate(TEMPLATES[0], 4)["sql"])

    def test_frozen_file_hash_is_checked(self):
        cases, digest = load_cases("heldout")
        self.assertEqual(len(digest), 64)
        self.assertTrue(all(case["split"] == "heldout" for case in cases))


class OrderingTests(unittest.TestCase):
    def test_top_level_order_ignores_subqueries_and_literals(self):
        self.assertTrue(has_top_level_order("SELECT id FROM t ORDER BY id"))
        self.assertFalse(has_top_level_order("SELECT * FROM (SELECT id FROM t ORDER BY id) s"))
        self.assertFalse(has_top_level_order("SELECT 'ORDER BY x' AS s"))

    def test_ordered_comparison_rejects_reordering(self):
        a, b = [{"id": 1}, {"id": 2}], [{"id": 2}, {"id": 1}]
        self.assertTrue(equivalent(a, b))
        self.assertFalse(equivalent(a, b, ordered=True))

    def test_counterexample_lists_missing_and_extra_rows(self):
        result = counterexample([{"id": 1}, {"id": None}], [{"id": 1}, {"id": 3}])
        self.assertEqual(result, {"missing_rows": [{"id": None}], "unexpected_rows": [{"id": 3}]})


@unittest.skipUnless(os.getenv("SURGEON_TEST_DATABASE") == "1", "requires seeded local PostgreSQL")
class HiddenFixtureTests(unittest.TestCase):
    def test_midnight_off_by_one_passes_dev_but_not_hidden_fixtures(self):
        db = Database()
        original = "SELECT id, customer_id FROM orders WHERE created_at::date = DATE '2026-05-10'"
        wrong = ("SELECT id, customer_id FROM orders WHERE created_at > TIMESTAMP '2026-05-10' "
                 "AND created_at < TIMESTAMP '2026-05-11'")
        self.assertTrue(db.check(original, wrong, FIXTURE_SCHEMAS)["equivalent"])
        verdict = db.check(original, wrong, EVAL_SCHEMAS)
        self.assertFalse(verdict["equivalent"])
        self.assertTrue(verdict["counterexample"]["missing_rows"])


if __name__ == "__main__":
    unittest.main()
