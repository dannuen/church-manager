import hashlib
import sqlite3
import unicodedata
import unittest
import zipfile
from unittest import mock

from _support import CopyTestCase, temp_folder
from churchmgr import db, documents, handover, lists, paths, people, schema, settings
from churchmgr.setup import new_church_setup

NOTES = (
    "PRIVATE-NOTE-MARKER-1 Cần cầu nguyện cho hôn nhân.",
    "Đang gặp khó khăn tài chính, cần nâng đỡ.",
    "PRIVATE-NOTE-MARKER-2",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class HandoverTest(CopyTestCase):
    def setUp(self):
        super().setUp()
        c = self.conn
        self.p = people.add_person(c, "Nguyễn Hải Đăng", note="ghi chú thường")
        for body in NOTES:
            people.add_private_note(c, self.p, body)
        people.add_private_note(c, self.p, "ok")  # too short to search for, still removed
        self.doc = documents.add_document(c, self.folder, "Chứng nhận".encode("utf-8"), "Chứng nhận.txt",
                                          person_id=self.p)
        self.stored = documents.get_document(c, self.doc)["stored_name"]
        self.out = self.tmp / "out"
        self.db_file = self.folder / "church.db"

    def make(self, today="2026-11-01"):
        return handover.make_handover(self.folder, self.out, today=today)

    def open_zip_db(self, zip_path):
        target = self.tmp / f"check-{zip_path.stem}.db"
        with zipfile.ZipFile(zip_path) as zf:
            target.write_bytes(zf.read("church.db"))
        conn = sqlite3.connect(target)
        self.addCleanup(conn.close)
        return target, conn

    def test_zip_has_no_private_notes_and_source_keeps_them(self):
        before = sha(self.db_file)
        zip_path = self.make()
        self.assertEqual(zip_path, (self.out / "handover-hoi-thanh-thu-2026-11-01.zip").resolve())
        with zipfile.ZipFile(zip_path) as zf:
            self.assertIsNone(zf.testzip())
            self.assertEqual(sorted(zf.namelist()), ["church.db", "documents/", f"documents/{self.stored}"])
            self.assertEqual(zf.read(f"documents/{self.stored}"), "Chứng nhận".encode("utf-8"))
        path, conn = self.open_zip_db(zip_path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM private_note").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT full_name, note FROM person").fetchall(),
                         [("Nguyễn Hải Đăng", "ghi chú thường")])  # other data is kept
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], schema.SCHEMA_VERSION)
        data = path.read_bytes()
        for body in NOTES:
            self.assertNotIn(body.encode("utf-8"), data)
        self.assertNotIn(b"PRIVATE-NOTE-MARKER", data)
        # The source church copy is not changed and still has its notes.
        self.assertEqual(sha(self.db_file), before)
        self.assertEqual(len(people.list_private_notes(self.conn, self.p)), 4)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), [zip_path.name])  # no work files left

    def test_the_zip_opens_as_a_church_copy(self):
        zip_path = self.make()
        target = self.tmp / "next-pastor"
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(target)
        conn = db.open_church_copy(target)
        self.addCleanup(conn.close)
        self.assertEqual(settings.get_setting(conn, "church_name"), "Hội Thánh Thử")
        self.assertEqual(documents.document_path(conn, target, self.doc).read_bytes(), "Chứng nhận".encode("utf-8"))

    def test_name_gets_a_number_when_taken(self):
        names = [self.make().name for _ in range(3)]
        self.assertEqual(names, ["handover-hoi-thanh-thu-2026-11-01.zip", "handover-hoi-thanh-thu-2026-11-01-2.zip",
                                 "handover-hoi-thanh-thu-2026-11-01-3.zip"])
        self.assertRegex(handover.make_handover(self.folder, self.out).name,
                         r"^handover-hoi-thanh-thu-\d{4}-\d{2}-\d{2}(-\d+)?\.zip$")

    def test_onedrive_and_documents_out_dir_refused(self):
        bad_out = self.tmp / "OneDrive - Personal" / "out"
        with self.assertRaisesRegex(handover.HandoverError, "OneDrive"):
            handover.make_handover(self.folder, bad_out)
        self.assertFalse((self.tmp / "OneDrive - Personal").exists())
        with self.assertRaises(handover.HandoverError):
            handover.make_handover(self.folder, self.folder / "documents" / "x")
        with self.assertRaises(handover.HandoverError):
            handover.make_handover(self.tmp / "no-copy-here", self.out)

    def test_failed_count_check_leaves_no_zip(self):
        with mock.patch.object(handover, "_strip_private", lambda path: None):
            with self.assertRaisesRegex(handover.HandoverError, "Private note"):
                self.make()
        self.assertEqual(list(self.out.iterdir()), [])  # no zip, no partial file, no work folder

    def test_byte_check_catches_text_left_in_free_pages(self):
        def weak_strip(path):  # deletes the rows but leaves the old bytes in the file
            conn = sqlite3.connect(path, isolation_level=None)
            conn.execute("PRAGMA secure_delete = OFF")
            conn.execute("DELETE FROM private_note")
            conn.close()

        with mock.patch.object(handover, "_strip_private", weak_strip):
            with self.assertRaisesRegex(handover.HandoverError, "still found"):
                self.make()
        self.assertEqual(list(self.out.iterdir()), [])

    def test_check_no_private_text(self):
        handover.check_no_private_text(b"abc", [(1, "Cầu nguyện".encode("utf-8"))])
        with self.assertRaises(handover.HandoverError):
            handover.check_no_private_text(b"xx " + "Cầu nguyện".encode("utf-8"), [(1, "Cầu nguyện".encode("utf-8"))])

    # ---- B2: the text of a Private note inside a Document file

    def refused_by_document(self, form):
        """Add a .txt Document holding a Private note's text in Unicode ``form``; the Handover must refuse."""
        note = "PRIVATE-NOTE-MARKER tư vấn hôn nhân của chị Tuyết"
        people.add_private_note(self.conn, self.p, note)
        data = ("Ghi chú:\n" + unicodedata.normalize(form, note) + "\n").encode("utf-8")
        doc = documents.add_document(self.conn, self.folder, data, "ghichu.txt", person_id=self.p)
        file = documents.document_path(self.conn, self.folder, doc)
        before = sha(self.db_file)
        with self.assertRaises(handover.HandoverError) as ctx:
            self.make()
        self.assertTrue(ctx.exception.private_text_found)  # the Copies page then lists where
        self.assertIn("Document", str(ctx.exception))
        self.assertNotIn("tư vấn", unicodedata.normalize("NFC", str(ctx.exception)))  # never the note words
        self.assertEqual(list(self.out.iterdir()), [])  # no zip, no .partial file, no work folder
        self.assertEqual(sha(self.db_file), before)  # the source church copy is not changed
        self.assertEqual(file.read_bytes(), data)
        self.assertEqual(len(people.list_private_notes(self.conn, self.p)), 5)

    def test_document_with_the_note_text_nfc_is_refused(self):
        self.refused_by_document("NFC")

    def test_document_with_the_note_text_nfd_is_refused(self):
        self.refused_by_document("NFD")

    def test_document_without_the_note_text_is_kept_in_the_zip(self):
        people.add_private_note(self.conn, self.p, "PRIVATE-NOTE-MARKER tư vấn hôn nhân của chị Tuyết")
        data = "Tư vấn hôn nhân: lịch họp tháng 11.\n".encode("utf-8")  # same words in part, not the note
        doc = documents.add_document(self.conn, self.folder, data, "ghichu.txt", person_id=self.p)
        stored = documents.get_document(self.conn, doc)["stored_name"]
        with zipfile.ZipFile(self.make()) as zf:
            self.assertEqual(zf.read(f"documents/{stored}"), data)

    def test_private_text_files(self):
        folder = self.tmp / "files"
        folder.mkdir()
        note = "Cầu nguyện cho chị Tuyết"
        files = []
        for name, content in (("nfc.txt", note), ("nfd.txt", unicodedata.normalize("NFD", note)),
                              ("other.txt", "Cầu nguyện chung")):
            files.append(folder / name)
            files[-1].write_bytes(("x " + content + " y").encode("utf-8"))
        found = handover.private_text_files(files, [(7, note.encode("utf-8")), (8, "không có ở đâu")])
        self.assertEqual(found, [(files[0], 7), (files[1], 7)])
        self.assertEqual(handover.private_text_files(files, [(7, unicodedata.normalize("NFD", note))]),
                         [(files[0], 7), (files[1], 7)])  # an NFD note text finds both forms too

    def test_zip_check_failure_leaves_no_zip(self):
        with mock.patch.object(handover, "_check_zip", side_effect=handover.HandoverError("zip check")):
            with self.assertRaisesRegex(handover.HandoverError, "zip check"):
                self.make()
        self.assertEqual(list(self.out.iterdir()), [])

    def test_only_the_private_text_refusal_says_private_text_found(self):
        """The Copies page picks its layout by this flag, not by the words of the message."""
        with self.assertRaises(handover.HandoverError) as ctx:
            handover.check_no_private_text(b"xx " + "Cầu nguyện".encode("utf-8"), [(1, "Cầu nguyện".encode("utf-8"))])
        self.assertTrue(ctx.exception.private_text_found)
        with mock.patch.object(handover, "_strip_private", lambda path: None):  # the count check says "Private note"
            with self.assertRaises(handover.HandoverError) as ctx:
                self.make()
        self.assertIn("Private note", str(ctx.exception))
        self.assertFalse(ctx.exception.private_text_found)
        with self.assertRaises(handover.HandoverError) as ctx:
            handover.make_handover(self.folder, self.tmp / "OneDrive - Personal" / "out")
        self.assertFalse(ctx.exception.private_text_found)
        self.assertFalse(handover.HandoverError("plain").private_text_found)


class NewChurchSetupTest(unittest.TestCase):
    def setUp(self):
        self.root = temp_folder(self) / "copies"

    def test_blank_copy_with_default_lists_only(self):
        folder = new_church_setup(self.root, "Hội Thánh Tin Lành Đà Lạt")
        self.assertEqual(folder, (self.root / "hoi-thanh-tin-lanh-da-lat").resolve())
        conn = db.open_church_copy(folder)
        self.addCleanup(conn.close)
        self.assertEqual(settings.get_setting(conn, "church_name"), "Hội Thánh Tin Lành Đà Lạt")
        self.assertEqual(settings.get_setting(conn, "care_reminder_months"), "3")
        for list_name, items in schema.DEFAULT_LISTS.items():
            self.assertEqual([(r["code"], r["name"]) for r in lists.get_list(conn, list_name, include_hidden=True)],
                             list(items))
        for table in ("person", "family", "chi_phai", "private_note", "calendar_item", "offering", "expense",
                      "document", "sent_document", "head_count"):
            self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0, table)
        self.assertEqual(list((folder / "documents").iterdir()), [])

    def test_taken_folder_gets_a_number(self):
        first = new_church_setup(self.root, "Hội Thánh A")
        second = new_church_setup(self.root, "Hội Thánh A")
        (self.root / "hoi-thanh-a-3").mkdir()  # any folder counts as taken
        fourth = new_church_setup(self.root, "Hội Thánh A")
        self.assertEqual([p.name for p in (first, second, fourth)], ["hoi-thanh-a", "hoi-thanh-a-2", "hoi-thanh-a-4"])

    def test_refused_inputs(self):
        with self.assertRaises(paths.CopyPathError):
            new_church_setup(self.root / "OneDrive", "Hội Thánh")
        self.assertFalse((self.root / "OneDrive").exists())
        with self.assertRaises(ValueError):
            new_church_setup(self.root, "   ")
        self.assertFalse(self.root.exists())


if __name__ == "__main__":
    unittest.main()
