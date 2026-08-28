import copy
import json
import os
import unittest

from backlog import mutate

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load(name):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


class ParseDepsTest(unittest.TestCase):
    def test_empty_and_none(self):
        self.assertEqual(mutate.parse_deps_value(""), [])
        self.assertEqual(mutate.parse_deps_value("  none "), [])

    def test_comma_split_and_trim(self):
        self.assertEqual(mutate.parse_deps_value(" AA-001 , AA-002 ,"), ["AA-001", "AA-002"])


class ComputeFieldUpdatesTest(unittest.TestCase):
    def test_no_options_raises(self):
        with self.assertRaises(mutate.NoUpdateOptionsError):
            mutate.compute_field_updates({"file": "x", "id": "AA-001"})

    def test_none_maps_to_null_for_nullable(self):
        updates = mutate.compute_field_updates({"priority": "none", "summary": "none"})
        self.assertEqual(updates, {"priority": None, "summary": None})

    def test_deps_parsed(self):
        self.assertEqual(mutate.compute_field_updates({"deps": "AA-001"}), {"deps": ["AA-001"]})


class ComputeCreateFieldsTest(unittest.TestCase):
    def test_missing_required_raises(self):
        with self.assertRaises(mutate.MissingRequiredFieldsError):
            mutate.compute_create_fields({"title": "x"})
        with self.assertRaises(mutate.MissingRequiredFieldsError):
            mutate.compute_create_fields({})

    def test_supplied_required_ok(self):
        fields = mutate.compute_create_fields({"title": "x", "category": "io"})
        self.assertEqual(fields, {"title": "x", "category": "io"})


class DetectPrefixTest(unittest.TestCase):
    def test_from_existing(self):
        self.assertEqual(mutate.detect_prefix([{"id": "AA-001"}], None), "AA")

    def test_empty_needs_prefix(self):
        with self.assertRaises(mutate.PrefixError):
            mutate.detect_prefix([], None)

    def test_empty_with_prefix(self):
        self.assertEqual(mutate.detect_prefix([], "BL"), "BL")

    def test_conflicting_prefix_rejected(self):
        with self.assertRaises(mutate.PrefixError):
            mutate.detect_prefix([{"id": "AA-001"}], "BB")


class ComputeNextIdTest(unittest.TestCase):
    def test_max_plus_one_zero_padded(self):
        tasks = [{"id": "AA-001"}, {"id": "AA-007"}]
        self.assertEqual(mutate.compute_next_id(tasks, "AA"), "AA-008")

    def test_rollover_past_three_digits(self):
        self.assertEqual(mutate.compute_next_id([{"id": "AA-999"}], "AA"), "AA-1000")

    def test_empty_starts_at_001(self):
        self.assertEqual(mutate.compute_next_id([], "BL"), "BL-001")

    def test_long_numeric_suffix_no_int_crash(self):
        nines = "AA-" + "9" * 4300
        self.assertEqual(mutate.compute_next_id([{"id": nines}], "AA"),
                         "AA-" + "1" + "0" * 4300)
        long_one = "AA-" + "1" * 4301
        self.assertEqual(mutate.compute_next_id([{"id": long_one}], "AA"),
                         "AA-" + "1" * 4300 + "2")


class BuildTaskTest(unittest.TestCase):
    def setUp(self):
        self.doc = load("valid.json")

    def test_defaults_and_id(self):
        before = copy.deepcopy(self.doc)
        result, new_id = mutate.build_task(
            self.doc, {"title": "new", "category": "io"}, "AA", "2026-08-28")
        self.assertEqual(new_id, "AA-003")
        self.assertEqual(self.doc, before)  # not mutated
        task = result["tasks"][-1]
        self.assertEqual(task["status"], "todo")
        self.assertIsNone(task["priority"])
        self.assertEqual(task["deps"], [])
        self.assertIsNone(task["done_at"])
        self.assertEqual(result["meta"]["updated"], "2026-08-28")
        self.assertEqual(list(task.keys())[:5], ["id", "status", "priority", "category", "title"])

    def test_status_done_sets_done_at(self):
        result, _ = mutate.build_task(
            self.doc, {"title": "x", "category": "io", "status": "done"}, "AA", "2026-08-28")
        self.assertEqual(result["tasks"][-1]["done_at"], "2026-08-28")


class ApplyUpdateTest(unittest.TestCase):
    def setUp(self):
        self.doc = load("valid.json")

    def test_not_found(self):
        with self.assertRaises(mutate.TaskNotFoundError):
            mutate.apply_update(self.doc, "ZZ-999", {"title": "x"}, "2026-08-28")

    def test_field_change_no_mutation(self):
        before = copy.deepcopy(self.doc)
        result = mutate.apply_update(self.doc, "AA-002", {"title": "renamed"}, "2026-08-28")
        self.assertEqual(self.doc, before)
        self.assertEqual(result["tasks"][1]["title"], "renamed")
        self.assertEqual(result["meta"]["updated"], "2026-08-28")

    def test_status_done_stamps_done_at(self):
        result = mutate.apply_update(self.doc, "AA-002", {"status": "done"}, "2026-08-28")
        self.assertEqual(result["tasks"][1]["done_at"], "2026-08-28")

    def test_status_away_from_done_clears_done_at(self):
        result = mutate.apply_update(self.doc, "AA-001", {"status": "todo"}, "2026-08-28")
        self.assertIsNone(result["tasks"][0]["done_at"])

    def test_existing_done_at_not_overwritten(self):
        result = mutate.apply_update(self.doc, "AA-001", {"status": "done"}, "2099-01-01")
        self.assertEqual(result["tasks"][0]["done_at"], "2026-08-27")


if __name__ == "__main__":
    unittest.main()
