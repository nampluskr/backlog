import copy
import json
import os
import unittest

from backlog.validate import validate_document

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load(name):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


def codes(result):
    return [error["code"] for error in result["errors"]]


class ValidateTest(unittest.TestCase):
    def test_valid_document(self):
        result = validate_document(load("valid.json"))
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["task_count"], 2)

    def test_empty_tasks_is_valid(self):
        result = validate_document(load("empty.json"))
        self.assertTrue(result["valid"])
        self.assertEqual(result["task_count"], 0)

    def test_root_not_object(self):
        result = validate_document([1, 2, 3])
        self.assertFalse(result["valid"])
        self.assertEqual(codes(result), ["ROOT_NOT_OBJECT"])

    def test_schema_version_number_is_invalid(self):
        doc = load("valid.json")
        doc["$schema_version"] = 1
        result = validate_document(doc)
        self.assertIn("SCHEMA_VERSION_INVALID", codes(result))

    def test_missing_task_field(self):
        doc = load("valid.json")
        del doc["tasks"][0]["where"]
        result = validate_document(doc)
        self.assertIn("REQUIRED_FIELD_MISSING", codes(result))
        paths = [e["path"] for e in result["errors"]]
        self.assertIn("tasks[0].where", paths)

    def test_id_format_invalid(self):
        doc = load("valid.json")
        doc["tasks"][0]["id"] = "lb-1"
        result = validate_document(doc)
        self.assertIn("ID_FORMAT_INVALID", codes(result))

    def test_mixed_prefix(self):
        result = validate_document(load("mixed_prefix.json"))
        self.assertFalse(result["valid"])
        self.assertIn("ID_PREFIX_MIXED", codes(result))

    def test_duplicate_id(self):
        doc = load("valid.json")
        doc["tasks"][1]["id"] = "AA-001"
        result = validate_document(doc)
        self.assertIn("DUPLICATE_ID", codes(result))

    def test_ref_missing(self):
        doc = load("valid.json")
        doc["tasks"][1]["deps"] = ["AA-999"]
        result = validate_document(doc)
        self.assertIn("REF_MISSING", codes(result))

    def test_self_reference_and_dangling(self):
        result = validate_document(load("invalid_refs.json"))
        self.assertIn("SELF_REFERENCE", codes(result))
        self.assertIn("REF_MISSING", codes(result))

    def test_duplicate_deps_entry(self):
        doc = load("valid.json")
        doc["tasks"][1]["deps"] = ["AA-001", "AA-001"]
        result = validate_document(doc)
        self.assertIn("DUPLICATE_DEPS_ENTRY", codes(result))

    def test_done_at_mismatch(self):
        doc = load("valid.json")
        doc["tasks"][0]["done_at"] = None
        result = validate_document(doc)
        self.assertIn("DONE_AT_MISMATCH", codes(result))

    def test_enum_invalid(self):
        doc = load("valid.json")
        doc["tasks"][0]["status"] = "archived"
        result = validate_document(doc)
        self.assertIn("ENUM_INVALID", codes(result))

    def test_title_empty(self):
        doc = load("valid.json")
        doc["tasks"][0]["title"] = ""
        result = validate_document(doc)
        self.assertIn("TITLE_EMPTY", codes(result))

    def test_bad_date_format(self):
        doc = load("valid.json")
        doc["meta"]["updated"] = "2026-13-40"
        result = validate_document(doc)
        self.assertIn("DATE_FORMAT_INVALID", codes(result))

    def test_self_backlog_passes(self):
        root = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(root, "backlog.json"), "r", encoding="utf-8") as handle:
            doc = json.load(handle)
        result = validate_document(doc)
        self.assertTrue(result["valid"], msg=str(result["errors"]))

    def test_id_rejects_non_ascii_digits(self):
        doc = load("valid.json")
        doc["tasks"][0]["id"] = "AA-٠٠١"
        result = validate_document(doc)
        self.assertIn("ID_FORMAT_INVALID", codes(result))

    def test_input_not_mutated(self):
        doc = load("valid.json")
        snapshot = copy.deepcopy(doc)
        validate_document(doc)
        self.assertEqual(doc, snapshot)


if __name__ == "__main__":
    unittest.main()
