"""Shared test helpers. Every test works in a tempfile folder only."""

import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from churchmgr import db, lists  # noqa: E402


def temp_folder(test):
    """A new temp folder, removed after the test."""
    tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
    test.addCleanup(tmp.cleanup)
    folder = pathlib.Path(tmp.name)
    assert "onedrive" not in str(folder.resolve()).lower(), "temp folder must be outside OneDrive"
    return folder


class CopyTestCase(unittest.TestCase):
    """Each test gets a fresh church copy in a temp folder and an open connection."""

    def setUp(self):
        self.tmp = temp_folder(self)
        self.folder = self.tmp / "copy"
        self.conn = db.create_church_copy(self.folder, "Hội Thánh Thử")
        self.addCleanup(self.conn.close)  # runs before the folder cleanup

    def item(self, list_name, code=None, name=None):
        row = lists.find_item(self.conn, list_name, code=code, name=name)
        assert row is not None, (list_name, code, name)
        return row["id"]

    def status(self, code):
        return self.item("status", code=code)
