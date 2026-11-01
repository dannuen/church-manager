"""Card C3: Documents through the real server (port 0, a fake church in a temp folder, the Host
header on every request, the Origin header on every POST, multipart bodies built here)."""

import re
import unicodedata
import unittest

import _support  # noqa: F401 - puts the repo root on sys.path
from churchmgr import documents, fake, people
from churchmgr.pages import documents as doc_pages
from test_pages_people import ROOT, PagesTestBase, section
from test_server import parse_panels

STORED = re.compile(r"[0-9a-f]{32}(\.[a-z0-9]{1,8})?")
VI_NAME = "Thư mời Hội Thánh.pdf"
VI_STAR = "filename*=UTF-8''Th%C6%B0%20m%E1%BB%9Di%20H%E1%BB%99i%20Th%C3%A1nh.pdf"


def multipart(fields, files=None):
    """A ``multipart/form-data`` body the way a browser sends it (a file name as raw UTF-8).
    Returns ``(body, content type)``."""
    boundary = "----c3DocumentsBoundary4Kq8Zt"
    out = b""
    for name, value in fields.items():
        out += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n').encode("utf-8") \
            + str(value).encode("utf-8") + b"\r\n"
    for name, (filename, data) in (files or {}).items():
        out += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n").encode("utf-8") + data + b"\r\n"
    out += f"--{boundary}--\r\n".encode("ascii")
    return out, f"multipart/form-data; boundary={boundary}"


class MultipartMixin:
    def post_multipart(self, path, fields, files=None, expect=303):
        body, ctype = multipart(fields, files)
        status, headers, data = self.request("POST", path, body, headers={"Content-Type": ctype})
        self.assertEqual(status, expect, data.decode("utf-8", "replace")[:2000])
        return headers, data.decode("utf-8", "replace")


class DocumentsPagesTest(MultipartMixin, PagesTestBase):
    def person_id(self):
        return next(p["id"] for p in people.list_persons(self.db()) if p["full_name"] == fake.FIRST_PERSON)

    def docs_dir(self):
        return (self.copy / "documents").resolve()

    def add(self, link, name, data, expect=303):
        return self.post_multipart("/documents/new", link, {"file": (name, data)}, expect=expect)

    def doc_rows(self):
        return self.db().execute("SELECT * FROM document ORDER BY id").fetchall()

    def test_vietnamese_and_traversal_names_are_kept_inside_documents_under_random_names(self):
        pid = self.person_id()
        before = {p.name for p in self.docs_dir().iterdir()}
        vi_bytes = bytes(range(256)) * 8 + "Hội Thánh".encode("utf-8")
        evil_bytes = b"C3 evil content ../../"
        headers, _ = self.add({"person_id": pid}, VI_NAME, vi_bytes)
        self.assertTrue(headers["location"].startswith(f"/people/{pid}?msg="), headers["location"])
        self.assertTrue(headers["location"].endswith("#documents"))
        self.add({"person_id": pid}, "../../evil.txt", evil_bytes)

        new = {p.name for p in self.docs_dir().iterdir()} - before
        self.assertEqual(len(new), 2)
        for name in new:
            self.assertRegex(name, STORED)
            self.assertIsNotNone(STORED.fullmatch(name), name)
        for place in (self.copy, self.root, self.root.parent, self.docs_dir().parent.parent):
            self.assertFalse((place / "evil.txt").exists(), place)
        by_name = {r["original_name"]: r for r in self.doc_rows() if r["stored_name"] in new}
        vi_row, evil_row = by_name[VI_NAME], by_name["evil.txt"]  # only the last part of a path is kept
        self.assertTrue(vi_row["stored_name"].endswith(".pdf"))
        self.assertTrue(evil_row["stored_name"].endswith(".txt"))
        self.assertEqual((vi_row["person_id"], evil_row["person_id"]), (pid, pid))
        self.assertEqual((self.docs_dir() / vi_row["stored_name"]).read_bytes(), vi_bytes)

        status, headers, data = self.request("GET", f"/documents/{vi_row['id']}/file")
        self.assertEqual(status, 200)
        self.assertEqual(data, vi_bytes)
        self.assertEqual(headers["content-type"], "application/octet-stream")
        self.assertEqual(headers["x-content-type-options"], "nosniff")
        disposition = headers["content-disposition"]
        self.assertTrue(disposition.startswith('attachment; filename="Thu moi Hoi Thanh.pdf"; '), disposition)
        self.assertIn(VI_STAR, disposition)
        status, headers, data = self.request("GET", f"/documents/{evil_row['id']}/file")
        self.assertEqual((status, data), (200, evil_bytes))
        self.assertIn("filename*=UTF-8''evil.txt", headers["content-disposition"])

        panel = section(self.page(f"/people/{pid}"), "documents")
        for row in (vi_row, evil_row):
            self.assertIn(f'href="/documents/{row["id"]}/file"', panel)
        self.assertIn(VI_NAME, panel)
        self.assertIn(">Add document</button>", panel)
        self.assertIn('enctype="multipart/form-data"', panel)
        self.assertIn(f'name="person_id" value="{pid}"', panel)
        self.assertIn("up to 50 MB", panel)

    def test_nfd_file_name_is_kept_as_nfc(self):
        nfc = "Giấy chứng nhận Báp-têm C3.txt"
        self.add({"person_id": self.person_id()}, unicodedata.normalize("NFD", nfc), b"C3 NFD")
        self.assertEqual(self.doc_rows()[-1]["original_name"], nfc)

    def test_family_and_calendar_item_pages_add_and_list_documents(self):
        fid = people.list_families(self.db())[0]["id"]
        headers, _ = self.add({"family_id": fid}, "Sổ gia đình C3.pdf", b"%PDF-1.4 C3 family")
        self.assertTrue(headers["location"].startswith(f"/families/{fid}?msg="))
        page = self.page(headers["location"].split("#")[0])
        self.assertIn("Document added: Sổ gia đình C3.pdf.", page)
        self.assertIn("Sổ gia đình C3.pdf", section(page, "documents"))
        self.assertEqual(self.doc_rows()[-1]["family_id"], fid)

        iid = self.db().execute("SELECT id FROM calendar_item ORDER BY id LIMIT 1").fetchone()[0]
        headers, _ = self.add({"calendar_item_id": iid}, "Chương trình C3.docx", b"C3 program")
        self.assertTrue(headers["location"].startswith(f"/calendar/{iid}?msg="))
        panel = section(self.page(f"/calendar/{iid}"), "documents")
        self.assertIn("Chương trình C3.docx", panel)
        self.assertIn(f'name="calendar_item_id" value="{iid}"', panel)
        self.assertEqual(self.doc_rows()[-1]["calendar_item_id"], iid)
        # the standalone form names what the Document is for
        page = self.page(f"/documents/new?family_id={fid}")
        self.assertIn("For the Family", page)
        self.assertIn('action="/documents/new"', page)

    def test_documents_list_is_newest_first_with_what_each_is_linked_to(self):
        self.add({"person_id": self.person_id()}, "Mới nhất C3.txt", b"newest")
        page = self.page("/documents")
        listing = section(page, "documents-list")
        rows = self.db().execute("SELECT id, original_name FROM document ORDER BY added_at DESC, id DESC").fetchall()
        self.assertEqual(parse_panels(page).rows["documents-list"], len(rows))
        spots = [listing.index(f'href="/documents/{r["id"]}/file"') for r in rows]
        self.assertEqual(spots, sorted(spots))  # newest first
        self.assertIn("Mới nhất C3.txt", listing)
        self.assertIn(fake.FIRST_PERSON, listing)  # linked to the Person
        sent_row = self.db().execute(
            "SELECT printf('%02d/%d', seq, year) FROM sent_document WHERE document_id IS NOT NULL").fetchone()
        self.assertIn(f">{sent_row[0]}</a>", listing)  # the file of a Sent document shows its number
        total = sum(r["size"] for r in self.doc_rows())
        self.assertIn(doc_pages.fmt_size(total), page)
        self.assertIn("Add document", page)  # the hint says where to add one

    def test_refusals_keep_nothing(self):
        pid = self.person_id()
        rows_before = len(self.doc_rows())
        files_before = sorted(p.name for p in self.docs_dir().iterdir())
        _h, page = self.post_multipart("/documents/new", {"person_id": pid}, expect=400)
        self.assertIn("Choose a file first.", page)
        self.assertIn(f'id="doc-file-{pid}-error"', page)
        _h, page = self.add({"person_id": pid}, "trống.txt", b"", expect=400)
        self.assertIn("The file is empty", page)
        fid = people.list_families(self.db())[0]["id"]
        _h, page = self.add({"person_id": pid, "family_id": fid}, "hai.txt", b"two links", expect=400)
        self.assertIn("one Person, one Family or one Calendar item", page)
        _h, page = self.add({"person_id": 999999}, "ai.txt", b"nobody", expect=400)
        self.assertIn("No Person with id 999999", page)
        _h, page = self.add({}, "khong.txt", b"no link", expect=400)
        self.assertIn("one Person, one Family or one Calendar item", page)

        # the size limit: lowered to 1 MB here so the test stays small; the same check guards 50 MB
        limit = documents.MAX_SIZE
        self.assertEqual(limit, 50 * 1024 * 1024)
        documents.MAX_SIZE = 1024 * 1024
        self.addCleanup(setattr, documents, "MAX_SIZE", limit)
        _h, page = self.add({"person_id": pid}, "lớn.bin", b"x" * (1024 * 1024 + 1), expect=400)
        self.assertIn("The file is too large. The limit is 1 MB.", page)
        self.assertIn('aria-invalid="true"', page)

        self.assertEqual(len(self.doc_rows()), rows_before)
        self.assertEqual(sorted(p.name for p in self.docs_dir().iterdir()), files_before)
        self.assertIn("There is no Document", self.page("/documents/999999/file", expect=404))
        self.page("/documents/new", expect=400)

    def test_a_missing_file_gives_a_plain_404(self):
        conn = self.db()
        doc_id = documents.add_document(conn, self.copy, b"C3 gone soon", "Sắp mất C3.txt")
        documents.document_path(conn, self.copy, doc_id).unlink()
        page = self.page(f"/documents/{doc_id}/file", expect=404)
        self.assertIn("is missing from the documents folder", page)


class SmallLogicTest(unittest.TestCase):
    def test_fmt_size(self):
        mb = 1024 * 1024
        cases = {0: "0 bytes", 1: "1 byte", 1023: "1023 bytes", 1024: "1 KB", 1025: "2 KB", 20480: "20 KB",
                 mb: "1,0 MB", 3_565_158: "3,4 MB", 50 * mb: "50,0 MB", 1500 * mb: "1.500,0 MB"}
        for size, words in cases.items():
            self.assertEqual(doc_pages.fmt_size(size), words, size)

    def test_parse_link(self):
        self.assertEqual(doc_pages.parse_link({"person_id": "5"}), ("person_id", 5))
        self.assertEqual(doc_pages.parse_link({"family_id": " 2 ", "person_id": ""}), ("family_id", 2))
        self.assertEqual(doc_pages.parse_link({"calendar_item_id": "9"}), ("calendar_item_id", 9))
        for bad in ({}, {"person_id": "1", "family_id": "2"}, {"person_id": "x"}, {"person_id": "0"},
                    {"calendar_item_id": "-1"}, {"person_id": "1.5"}):
            with self.assertRaises(ValueError, msg=bad):
                doc_pages.parse_link(bad)

    def test_files_are_written_and_read_only_through_the_data_layer(self):
        source = (ROOT / "churchmgr" / "pages" / "documents.py").read_text(encoding="utf-8")
        for banned in ("open(", "write_bytes", "read_bytes", "copy_folder /", "Path("):
            self.assertNotIn(banned, source)
        self.assertIn("docs.add_document(", source)
        self.assertIn("docs.document_path(", source)


if __name__ == "__main__":
    unittest.main()
