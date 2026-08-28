import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from backlog.document_io import read_document, write_document
from backlog.errors import DocumentParseError, FileReadError, FileWriteError

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class ReadDocumentTest(unittest.TestCase):
    def test_reads_valid_json(self):
        doc = read_document(os.path.join(FIXTURES, "valid.json"))
        self.assertEqual(doc["$schema_version"], "1")

    def test_missing_file_raises_file_read_error(self):
        with self.assertRaises(FileReadError):
            read_document(os.path.join(FIXTURES, "does_not_exist.json"))

    def test_syntax_error_raises_parse_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{ not json")
            with self.assertRaises(DocumentParseError):
                read_document(path)

    def test_nan_infinity_rejected_as_parse_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "nan.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('{"probe": NaN}')
            with self.assertRaises(DocumentParseError):
                read_document(path)


class WriteDocumentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.path = os.path.join(self.tmp, "backlog.json")
        shutil.copy(os.path.join(FIXTURES, "valid.json"), self.path)

    def test_unencodable_string_raises_write_error_and_cleans_temp(self):
        with open(self.path, "rb") as handle:
            original = handle.read()
        doc = read_document(self.path)
        doc["tasks"][0]["title"] = "\ud800"
        with self.assertRaises(FileWriteError):
            write_document(self.path, doc)
        with open(self.path, "rb") as handle:
            self.assertEqual(handle.read(), original)
        leftovers = [n for n in os.listdir(self.tmp) if n.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_round_trip(self):
        doc = read_document(self.path)
        doc["meta"]["note"] = "updated"
        write_document(self.path, doc)
        self.assertEqual(read_document(self.path)["meta"]["note"], "updated")

    def test_serialization_format(self):
        doc = read_document(self.path)
        write_document(self.path, doc)
        with open(self.path, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(text, json.dumps(doc, ensure_ascii=False, indent=2) + "\n")

    def test_failure_leaves_original_and_no_temp(self):
        with open(self.path, "rb") as handle:
            original = handle.read()
        doc = read_document(self.path)
        with mock.patch("backlog.document_io.os.replace", side_effect=OSError("boom")):
            with self.assertRaises(FileWriteError):
                write_document(self.path, doc)
        with open(self.path, "rb") as handle:
            self.assertEqual(handle.read(), original)
        leftovers = [n for n in os.listdir(self.tmp) if n.endswith(".tmp")]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
