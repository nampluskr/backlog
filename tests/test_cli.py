import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from backlog import errors
from backlog.cli import main

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def run(argv):
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class ValidateCommandTest(unittest.TestCase):
    def test_valid_file(self):
        code, out, err = run(["--file", os.path.join(FIXTURES, "valid.json"), "validate"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "VALID 2 task(s)")

    def test_invalid_file(self):
        code, out, err = run(["--file", os.path.join(FIXTURES, "invalid_refs.json"), "validate"])
        self.assertEqual(code, 1)
        self.assertIn("INVALID:", err)
        self.assertIn("[REF_MISSING]", err)

    def test_missing_file_is_io_error(self):
        code, out, err = run(["--file", os.path.join(FIXTURES, "nope.json"), "validate"])
        self.assertEqual(code, 3)

    def test_syntax_error_is_data_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{ oops")
            code, out, err = run(["--file", path, "validate"])
        self.assertEqual(code, 1)

    def test_list_table_and_empty_result(self):
        f = os.path.join(FIXTURES, "valid.json")
        code, out, err = run(["--file", f, "list"])
        self.assertEqual(code, 0)
        self.assertIn("AA-001", out)
        code, out, err = run(["--file", f, "list", "--status", "blocked"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip().split("\n"), ["ID  STATUS  PRIORITY  CATEGORY  TITLE"])

    def test_list_json_roundtrips(self):
        f = os.path.join(FIXTURES, "valid.json")
        code, out, err = run(["--file", f, "list", "--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)), 2)

    def test_list_unknown_filter_exits_1(self):
        f = os.path.join(FIXTURES, "valid.json")
        code, out, err = run(["--file", f, "list", "--status", "archived"])
        self.assertEqual(code, 1)
        self.assertIn("enums.status", err)

    def test_show_found_and_missing(self):
        f = os.path.join(FIXTURES, "valid.json")
        code, out, err = run(["--file", f, "show", "AA-001"])
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("id: AA-001"))
        code, out, err = run(["--file", f, "show", "ZZ-999"])
        self.assertEqual(code, 1)
        self.assertIn('no task with id "ZZ-999"', err)

    def test_show_json(self):
        f = os.path.join(FIXTURES, "valid.json")
        code, out, err = run(["--file", f, "show", "AA-002", "--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["id"], "AA-002")

    def test_bad_format_exits_2(self):
        f = os.path.join(FIXTURES, "valid.json")
        with self.assertRaises(SystemExit) as ctx:
            run(["--file", f, "list", "--format", "yaml"])
        self.assertEqual(ctx.exception.code, 2)

    def test_malformed_task_entry_no_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "m.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('{"enums": {}, "tasks": [null]}')
            code, out, err = run(["--file", path, "list"])
        self.assertEqual(code, 0)
        self.assertNotIn("Traceback", err)

    def test_root_without_tasks_array_is_data_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "r.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('{"tasks": {}}')
            code, out, err = run(["--file", path, "show", "AA-001"])
        self.assertEqual(code, 1)

    def test_missing_command_exits_2(self):
        with self.assertRaises(SystemExit) as ctx:
            run([])
        self.assertEqual(ctx.exception.code, 2)

    def test_add_missing_required_exits_2(self):
        with self.assertRaises(SystemExit) as ctx:
            run(["add", "--category", "io"])
        self.assertEqual(ctx.exception.code, 2)


class WriteCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.path = os.path.join(self.tmp, "backlog.json")
        shutil.copy(os.path.join(FIXTURES, "valid.json"), self.path)

    def _digest(self):
        with open(self.path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()

    def _tasks(self):
        with open(self.path, "r", encoding="utf-8") as handle:
            return json.load(handle)["tasks"]

    def test_add_appends_and_prints_id(self):
        code, out, err = run(["--file", self.path, "add", "--title", "New", "--category", "io"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "AA-003")
        self.assertEqual([t["id"] for t in self._tasks()], ["AA-001", "AA-002", "AA-003"])

    def test_add_missing_required_no_file_touch(self):
        before = self._digest()
        with self.assertRaises(SystemExit) as ctx:
            run(["--file", self.path, "add", "--title", "New"])
        self.assertEqual(ctx.exception.code, 2)
        self.assertEqual(self._digest(), before)

    def test_add_bad_reference_rejected_original_intact(self):
        before = self._digest()
        code, out, err = run(["--file", self.path, "add", "--title", "N",
                              "--category", "io", "--parent", "AA-999"])
        self.assertEqual(code, 1)
        self.assertEqual(self._digest(), before)
        self.assertIn("REF_MISSING", err)

    def test_update_changes_field(self):
        code, out, err = run(["--file", self.path, "update", "AA-002", "--status", "done"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "Updated AA-002")
        task = [t for t in self._tasks() if t["id"] == "AA-002"][0]
        self.assertEqual(task["status"], "done")
        self.assertIsNotNone(task["done_at"])

    def test_update_no_options_exits_2_before_io(self):
        before = self._digest()
        code, out, err = run(["--file", self.path, "update", "AA-002"])
        self.assertEqual(code, 2)
        self.assertEqual(self._digest(), before)

    def test_update_missing_task_exits_1(self):
        before = self._digest()
        code, out, err = run(["--file", self.path, "update", "ZZ-999", "--title", "x"])
        self.assertEqual(code, 1)
        self.assertEqual(self._digest(), before)

    def test_add_to_empty_backlog_requires_prefix(self):
        empty = os.path.join(self.tmp, "empty.json")
        shutil.copy(os.path.join(FIXTURES, "empty.json"), empty)
        code, out, err = run(["--file", empty, "add", "--title", "First", "--category", "env"])
        self.assertEqual(code, 2)
        self.assertIn("prefix", err)
        code, out, err = run(["--file", empty, "add", "--title", "First",
                              "--category", "env", "--prefix", "BL"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "BL-001")

    def test_write_failure_leaves_original_byte_for_byte(self):
        before = self._digest()
        with mock.patch("backlog.cli.write_document",
                        side_effect=errors.FileWriteError("boom")):
            code, out, err = run(["--file", self.path, "add", "--title", "N", "--category", "io"])
        self.assertEqual(code, 3)
        self.assertEqual(self._digest(), before)


if __name__ == "__main__":
    unittest.main()
