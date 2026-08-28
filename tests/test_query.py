import json
import os
import unittest

from backlog import query

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load(name):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


class FilterSortTest(unittest.TestCase):
    def setUp(self):
        self.tasks = load("valid.json")["tasks"]

    def test_no_filters_returns_all_sorted(self):
        result = query.filter_and_sort_tasks(self.tasks)
        self.assertEqual([t["id"] for t in result], ["AA-001", "AA-002"])

    def test_status_filter(self):
        result = query.filter_and_sort_tasks(self.tasks, status="todo")
        self.assertEqual([t["id"] for t in result], ["AA-002"])

    def test_priority_none_matches_null(self):
        result = query.filter_and_sort_tasks(self.tasks, priority="none")
        self.assertEqual([t["id"] for t in result], ["AA-002"])

    def test_and_combined_filters(self):
        result = query.filter_and_sort_tasks(self.tasks, status="done", category="io")
        self.assertEqual(result, [])

    def test_sort_by_prefix_then_number(self):
        tasks = [
            {"id": "BB-002"}, {"id": "AA-010"}, {"id": "AA-002"}, {"id": "bad"},
        ]
        result = query.filter_and_sort_tasks(tasks)
        self.assertEqual([t["id"] for t in result], ["AA-002", "AA-010", "BB-002", "bad"])

    def test_short_id_is_malformed_and_sorts_last(self):
        result = query.filter_and_sort_tasks([{"id": "AA-2"}, {"id": "AA-010"}])
        self.assertEqual([t["id"] for t in result], ["AA-010", "AA-2"])

    def test_non_dict_task_dropped(self):
        result = query.filter_and_sort_tasks([None, {"id": "AA-001"}, 5])
        self.assertEqual([t["id"] for t in result], ["AA-001"])

    def test_huge_numeric_suffix_sorts_numerically(self):
        huge = "AA-" + "9" * 5000
        result = query.filter_and_sort_tasks(
            [{"id": "bad"}, {"id": huge}, {"id": "AA-002"}])
        self.assertEqual([t["id"] for t in result], ["AA-002", huge, "bad"])

    def test_leading_zero_ids_sort_by_value(self):
        result = query.filter_and_sort_tasks([{"id": "AA-010"}, {"id": "AA-009"}])
        self.assertEqual([t["id"] for t in result], ["AA-009", "AA-010"])

    def test_priority_none_ignores_missing_field(self):
        tasks = [{"id": "AA-001"}, {"id": "AA-002", "priority": None}]
        result = query.filter_and_sort_tasks(tasks, priority="none")
        self.assertEqual([t["id"] for t in result], ["AA-002"])


class ValidateFiltersTest(unittest.TestCase):
    def setUp(self):
        self.enums = load("valid.json")["enums"]

    def test_valid_filters(self):
        self.assertEqual(query.validate_filters(self.enums, status="todo"), [])

    def test_unknown_status(self):
        errs = query.validate_filters(self.enums, status="archived")
        self.assertEqual(len(errs), 1)

    def test_priority_none_is_not_checked(self):
        self.assertEqual(query.validate_filters(self.enums, priority="none"), [])

    def test_missing_enums_skipped(self):
        self.assertEqual(query.validate_filters(None, status="whatever"), [])


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.tasks = load("valid.json")["tasks"]

    def test_table_header_only_on_empty(self):
        text = query.render_table([])
        self.assertEqual(text.strip(), "ID  STATUS  PRIORITY  CATEGORY  TITLE")

    def test_table_null_priority_is_none(self):
        text = query.render_table(self.tasks)
        self.assertIn("(none)", text)

    def test_table_control_chars_kept_single_line(self):
        tasks = [dict(self.tasks[0], title="first\nsecond", category="a\tb")]
        text = query.render_table(tasks)
        self.assertEqual(len(text.rstrip("\n").split("\n")), 2)  # header + 1 row
        self.assertNotIn("\t", text.split("\n")[1])

    def test_table_title_not_truncated(self):
        tasks = [dict(self.tasks[0], title="x" * 200)]
        self.assertIn("x" * 200, query.render_table(tasks))

    def test_tasks_json_roundtrips(self):
        text = query.render_tasks_json(self.tasks)
        self.assertEqual(json.loads(text), self.tasks)

    def test_task_text_field_order_and_none(self):
        text = query.render_task_text(self.tasks[1])
        lines = text.strip().split("\n")
        self.assertEqual(lines[0], "id: AA-002")
        self.assertEqual(
            [line.split(":")[0] for line in lines],
            query.TASK_FIELD_ORDER,
        )
        self.assertIn("priority: (none)", text)
        self.assertIn("deps: AA-001", text)
        self.assertIn("deps: (none)", query.render_task_text(self.tasks[0]))

    def test_task_text_deps_joined(self):
        task = dict(self.tasks[0], deps=["AA-002", "AA-003"])
        self.assertIn("deps: AA-002, AA-003", query.render_task_text(task))

    def test_task_json_enforces_field_order(self):
        scrambled = {"title": "x", "id": "AA-001", "category": "io", "status": "todo",
                     "priority": None, "summary": None, "where": None, "parent": None,
                     "deps": [], "doc": None, "done_at": None, "note": None}
        text = query.render_task_json(scrambled)
        self.assertEqual(list(json.loads(text).keys()), query.TASK_FIELD_ORDER)

    def test_task_text_deps_coerces_non_strings(self):
        task = dict(self.tasks[0], deps=[1, 2])
        self.assertIn("deps: 1, 2", query.render_task_text(task))

    def test_table_display_width_alignment(self):
        text = query.render_table([
            {"id": "AA-001", "status": "todo", "priority": None,
             "category": "환경", "title": "ZZZ"},
            {"id": "AA-002", "status": "todo", "priority": None,
             "category": "abc", "title": "ZZZ"},
        ])
        rows = text.split("\n")
        # Both TITLE cells must begin at the same terminal column.
        self.assertEqual(
            query._display_width(rows[1].split("ZZZ")[0]),
            query._display_width(rows[2].split("ZZZ")[0]),
        )

    def test_display_width_ignores_combining_marks(self):
        self.assertEqual(query._display_width("é"), 1)
        self.assertEqual(query._display_width("ab"), 2)
        self.assertEqual(query._display_width("e" + chr(0x0301)), 1)
        self.assertEqual(query._display_width(chr(0xAC00) + chr(0x0301)), 2)

    def test_find_task_by_id(self):
        self.assertIsNone(query.find_task_by_id(self.tasks, "ZZ-999"))
        self.assertEqual(query.find_task_by_id(self.tasks, "AA-001")["id"], "AA-001")


if __name__ == "__main__":
    unittest.main()
