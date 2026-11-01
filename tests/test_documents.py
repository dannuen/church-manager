import hashlib
import unittest
from unittest import mock

from _support import CopyTestCase
from churchmgr import calendar, documents, lists, people, sent


class FileNameTest(unittest.TestCase):
    def test_clean_file_name_keeps_only_the_base_name(self):
        cases = {
            "../../x.txt": "x.txt", "..\\..\\x.txt": "x.txt", "C:\\fakepath\\Báo cáo.PDF": "Báo cáo.PDF",
            "/etc/passwd": "passwd", "a/b/../../../c.txt": "c.txt", " ảnh\u0000 cưới.jpg ": "ảnh cưới.jpg",
            "e\u0301.txt": "é.txt", "gpj\u202e.exe": "gpj.exe",
        }
        for raw, want in cases.items():
            self.assertEqual(documents.clean_file_name(raw), want, repr(raw))
        long = "a" * 300 + ".pdf"
        self.assertEqual(len(documents.clean_file_name(long)), 150)
        self.assertTrue(documents.clean_file_name(long).endswith(".pdf"))
        for bad in ("", "  ", ".", "..", "../", "a/..", None, b"x.txt"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                documents.clean_file_name(bad)

    def test_safe_extension(self):
        cases = {"x.PDF": "pdf", "x.tar.gz": "gz", "x.ábc": "", "x.verylongext": "", "noext": "", ".bashrc": "",
                 "x.": "", "x.mp4": "mp4", "x.12345678": "12345678", "x.a-b": ""}
        for name, want in cases.items():
            self.assertEqual(documents.safe_extension(name), want, name)


class DocumentTest(CopyTestCase):
    def setUp(self):
        super().setUp()
        self.p = people.add_person(self.conn, "Lê Văn An")
        self.f = people.add_family(self.conn, "Gia đình Lê")
        self.c = calendar.add_calendar_item(self.conn, "Event", "Tiệc", "2026-05-03 19:00")[0]
        self.docs = (self.folder / "documents").resolve()

    def files(self):
        return sorted(p.name for p in self.docs.iterdir())

    def test_add_and_read_back(self):
        data = bytes(range(256)) * 10
        did = documents.add_document(self.conn, self.folder, data, "C:\\fakepath\\Chứng nhận.PDF", person_id=self.p)
        row = documents.get_document(self.conn, did)
        self.assertEqual(row["original_name"], "Chứng nhận.PDF")
        self.assertRegex(row["stored_name"], r"^[0-9a-f]{32}\.pdf$")
        self.assertEqual((row["size"], row["sha256"]), (len(data), hashlib.sha256(data).hexdigest()))
        self.assertEqual((row["person_id"], row["family_id"], row["calendar_item_id"]), (self.p, None, None))
        path = documents.document_path(self.conn, self.folder, did)
        self.assertEqual(path.parent, self.docs)
        self.assertEqual(path.read_bytes(), data)
        self.assertEqual(documents.documents_on_disk(self.folder), [path])

    def test_traversal_names_stay_inside_documents(self):
        for raw in ("../../x.txt", "..\\..\\..\\win.ini", "/etc/passwd", "....//....//y.txt", "C:/z.txt"):
            did = documents.add_document(self.conn, self.folder, b"x", raw)
            path = documents.document_path(self.conn, self.folder, did)
            self.assertEqual(path.parent, self.docs, raw)
            self.assertTrue(path.is_file(), raw)
            self.assertNotIn("..", documents.get_document(self.conn, did)["original_name"])
        self.assertEqual(len(self.files()), 5)
        self.assertEqual([p.name for p in self.tmp.iterdir()], ["copy"])  # nothing was written outside

    def test_tampered_stored_name_is_not_opened(self):
        did = documents.add_document(self.conn, self.folder, b"x", "a.txt")
        for bad in ("../../church.db", "..\\church.db", "0" * 32 + "/../../x", "ABC", "0" * 32 + ".TXT"):
            self.conn.execute("UPDATE document SET stored_name = ? WHERE id = ?", (bad, did))
            with self.assertRaises(ValueError, msg=bad):
                documents.document_path(self.conn, self.folder, did)
        with self.assertRaises(ValueError):
            documents.document_path(self.conn, self.folder, 9999)

    def test_links_and_list(self):
        a = documents.add_document(self.conn, self.folder, b"1", "a.txt", person_id=self.p)
        b = documents.add_document(self.conn, self.folder, b"2", "b.txt", family_id=self.f)
        c = documents.add_document(self.conn, self.folder, b"3", "c.txt", calendar_item_id=self.c)
        d = documents.add_document(self.conn, self.folder, b"", "empty.txt")  # no link, empty file is fine
        ids = lambda rows: [r["id"] for r in rows]  # noqa: E731
        self.assertEqual(ids(documents.list_documents(self.conn, person_id=self.p)), [a])
        self.assertEqual(ids(documents.list_documents(self.conn, family_id=self.f)), [b])
        self.assertEqual(ids(documents.list_documents(self.conn, calendar_item_id=self.c)), [c])
        self.assertEqual(ids(documents.list_documents(self.conn)), [a, b, c, d])
        with self.assertRaises(ValueError):
            documents.list_documents(self.conn, person_id=self.p, family_id=self.f)

    def test_refused_and_nothing_left_on_disk(self):
        bad = [
            dict(data="text, not bytes"), dict(person_id=self.p, family_id=self.f), dict(person_id=9999),
            dict(calendar_item_id=9999), dict(original_name=".."),
        ]
        for kwargs in bad:
            args = dict(data=b"x", original_name="a.txt")
            args.update(kwargs)
            with self.assertRaises(ValueError, msg=kwargs):
                documents.add_document(self.conn, self.folder, **args)
        with mock.patch.object(documents, "MAX_SIZE", 10):
            with self.assertRaisesRegex(ValueError, "too large"):
                documents.add_document(self.conn, self.folder, b"x" * 11, "big.bin")
            documents.add_document(self.conn, self.folder, b"x" * 10, "ok.bin")
        self.assertEqual(len(self.files()), 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM document").fetchone()[0], 1)
        self.assertEqual(documents.MAX_SIZE, 50 * 1024 * 1024)

    def test_failed_write_removes_the_file_and_the_row(self):
        made = []

        class BrokenFile:
            def __init__(self, path, mode):
                self.fh = open(path, mode)  # the file is really created
                made.append(path)

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self.fh.close()

            def write(self, data):
                raise OSError("disk full")

        with mock.patch.object(documents, "open", BrokenFile, create=True):
            with self.assertRaisesRegex(OSError, "disk full"):
                documents.add_document(self.conn, self.folder, b"x", "a.txt", person_id=self.p)
        self.assertEqual(len(made), 1)
        self.assertFalse(made[0].exists())
        self.assertEqual(self.files(), [])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM document").fetchone()[0], 0)

    def test_onedrive_copy_folder_refused(self):
        with self.assertRaises(ValueError):
            documents.add_document(self.conn, self.tmp / "OneDrive" / "copy", b"x", "a.txt")
        self.assertFalse((self.tmp / "OneDrive").exists())


class DeleteDocumentTest(CopyTestCase):
    """FIX-T 3b (B22): Delete a Document. The row and the file go; a Sent document stays with no file."""

    def setUp(self):
        super().setUp()
        self.p = people.add_person(self.conn, "Lê Văn An")
        self.keep = documents.add_document(self.conn, self.folder, b"keep B22", "giữ lại.txt", person_id=self.p)

    def count(self):
        return self.conn.execute("SELECT COUNT(*) FROM document").fetchone()[0]

    def test_delete_removes_the_row_and_the_file_and_the_sent_document_keeps_its_row(self):
        did = documents.add_document(self.conn, self.folder, b"B22 old private words", "Giấy mời.txt")
        path = documents.document_path(self.conn, self.folder, did)
        r = lists.find_item(self.conn, "recipient", name="Giáo hội")["id"]
        pu = lists.find_item(self.conn, "purpose", name="Invitation")["id"]
        sid, number = sent.add_sent_document(self.conn, "2026-05-03", r, pu, "Mời dự lễ", document_id=did)
        self.assertEqual(self.count(), 2)

        self.assertIsNone(documents.delete_document(self.conn, self.folder, did))
        self.assertIsNone(documents.get_document(self.conn, did))
        self.assertFalse(path.exists())
        row = self.conn.execute("SELECT * FROM sent_document WHERE id = ?", (sid,)).fetchone()
        self.assertIsNone(row["document_id"])  # the Sent document stays, with no file
        self.assertEqual((number, row["date"], row["recipient_id"], row["purpose_id"], row["subject"]),
                         ("01/2026", "2026-05-03", r, pu, "Mời dự lễ"))
        kept = documents.document_path(self.conn, self.folder, self.keep)
        self.assertEqual(documents.documents_on_disk(self.folder), [kept])  # the other Document is not touched
        self.assertEqual(kept.read_bytes(), b"keep B22")
        with self.assertRaises(ValueError):  # gone: an unknown id
            documents.delete_document(self.conn, self.folder, did)

    def test_a_missing_file_still_deletes_the_row(self):
        did = documents.add_document(self.conn, self.folder, b"x", "mất.txt")
        documents.document_path(self.conn, self.folder, did).unlink()
        self.assertIsNone(documents.delete_document(self.conn, self.folder, did))
        self.assertEqual(self.count(), 1)

    def test_a_file_that_cannot_be_removed_is_given_back_and_the_row_is_gone(self):
        did = documents.add_document(self.conn, self.folder, b"x", "đang mở.txt")
        path = documents.document_path(self.conn, self.folder, did)
        with mock.patch.object(type(path), "unlink", side_effect=PermissionError("in use")):
            left = documents.delete_document(self.conn, self.folder, did)
        self.assertEqual(left, path)
        self.assertTrue(path.is_file())  # the file stays (no Document row names it now)
        self.assertIsNone(documents.get_document(self.conn, did))

    def test_unknown_id_or_bad_stored_name_changes_nothing(self):
        files = sorted(p.name for p in (self.folder / "documents").iterdir())
        for bad in (9999, 0, "x"):
            with self.assertRaises(ValueError, msg=bad):
                documents.delete_document(self.conn, self.folder, bad)
        self.conn.execute("UPDATE document SET stored_name = '../church.db' WHERE id = ?", (self.keep,))
        with self.assertRaises(ValueError):
            documents.delete_document(self.conn, self.folder, self.keep)
        self.assertEqual(self.count(), 1)
        self.assertTrue((self.folder / "church.db").is_file())
        self.assertEqual(sorted(p.name for p in (self.folder / "documents").iterdir()), files)


if __name__ == "__main__":
    unittest.main()
