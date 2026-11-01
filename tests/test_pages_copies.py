"""Card C3: Copies (Handover, New church setup, open another church copy) and Settings through the
real server (port 0, temp folders only, the Host header on every request, the Origin header on
every POST)."""

import hashlib
import pathlib
import shutil
import sqlite3
import tempfile
import unittest
import urllib.parse
import zipfile
from unittest import mock

import _support  # noqa: F401 - puts the repo root on sys.path
from churchmgr import care, db, documents, fake, handover, paths, people, schema, settings
from churchmgr.pages import copies as copy_pages
from churchmgr.pages import settings as settings_pages
from test_pages_people import PagesTestBase, section
from test_server import LiveServer

MARKER = b"PRIVATE-NOTE-MARKER"


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


class HandoverPagesTest(PagesTestBase):
    """The fake church (with Private notes); the copies root is the temp folder."""

    def handovers(self):
        folder = self.root / copy_pages.HANDOVERS
        return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []

    def note_count(self):
        return self.db().execute("SELECT COUNT(*) FROM private_note").fetchone()[0]

    def test_copies_page_says_where_everything_is(self):
        page = self.page("/copies")
        this = section(page, "this-copy").replace("<wbr>", "")  # paths may wrap after a \ or /
        self.assertIn(str(self.copy.resolve()), this)
        self.assertIn(str(self.root.resolve()), this)
        self.assertIn(fake.CHURCH_NAME, this)
        self.assertIn(str(self.root.resolve() / "handovers"), section(page, "handover").replace("<wbr>", ""))
        self.assertIn(">Make Handover</button>", page)
        self.assertIn('action="/copies/new"', section(page, "new-church-setup"))
        listing = section(page, "copies")
        self.assertIn(fake.CHURCH_NAME, listing)
        self.assertIn("Open now", listing)

    def test_handover_is_refused_when_private_note_text_is_written_elsewhere(self):
        conn = self.db()
        persons = people.list_persons(conn)
        owner, other = persons[0]["id"], persons[1]["id"]
        words = "C3 trùng lặp riêng tư 4821"
        people.add_private_note(conn, owner, words)
        people.update_person(conn, other, note=f"Ghi chú thường: {words}")
        self.addCleanup(people.update_person, conn, other, note=None)
        before, notes = self.handovers(), self.note_count()

        status, _h, data = self.request("POST", "/copies/handover", {})
        page = data.decode("utf-8")
        self.assertEqual(status, 400)
        refusal = section(page, "handover")
        self.assertIn("Handover not made.", refusal)
        self.assertIn("The words of a Private note are also written somewhere else", refusal)
        self.assertIn(f'href="/people/{owner}"', refusal)  # whose Private note
        self.assertIn(f'the note of the Person <a href="/people/{other}"', refusal)  # where it was found
        self.assertIn("Edit that text", refusal)
        self.assertNotIn(words, page)  # the Private note text is never shown
        self.assertNotIn("trùng lặp", page)
        self.assertEqual(self.handovers(), before)  # no zip, no work folder left
        self.assertEqual(self.note_count(), notes)

    def test_handover_is_refused_when_a_document_file_holds_private_note_text(self):
        """B2: the refusal names the Document and whose it is, never the words of the Private note."""
        conn = self.db()
        owner = people.list_persons(conn)[2]
        words = "B2 tư vấn hôn nhân của chị Tuyết 5307"
        note_id = people.add_private_note(conn, owner["id"], words)
        self.addCleanup(conn.execute, "DELETE FROM private_note WHERE id = ?", (note_id,))  # the next tests hand over
        documents.add_document(conn, self.copy, f"Ghi chú: {words}\n".encode("utf-8"), "ghichu.txt",
                               person_id=owner["id"])
        before, notes, source_hash = self.handovers(), self.note_count(), sha(self.copy / db.DB_NAME)

        status, _h, data = self.request("POST", "/copies/handover", {})
        page = data.decode("utf-8")
        self.assertEqual(status, 400)
        refusal = section(page, "handover")
        self.assertIn("Handover not made.", refusal)
        self.assertRegex(refusal, rf'<li>The Private note of <a href="/people/{owner["id"]}">.*?</a> is also written '
                                  rf'in the Document <span lang="vi">ghichu.txt</span> of '
                                  rf'<a href="/people/{owner["id"]}" lang="vi">.*?</a>\.</li>')
        self.assertNotIn(words, page)  # the Private note text is never shown
        self.assertNotIn("tư vấn", page)
        self.assertEqual(self.handovers(), before)  # no zip, no .partial file, no work folder
        self.assertEqual(self.note_count(), notes)
        self.assertEqual(sha(self.copy / db.DB_NAME), source_hash)  # the church copy is not changed

    def test_make_handover_removes_private_notes_and_keeps_the_copy(self):
        notes = self.note_count()
        self.assertGreater(notes, 0)
        source_hash = sha(self.copy / db.DB_NAME)
        headers = self.post("/copies/handover", {})[0]
        location = headers["location"]
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(location).query)
        name = query["made"][0]
        self.assertRegex(name, r"^handover-[a-z0-9-]+-\d{4}-\d{2}-\d{2}(-\d+)?\.zip$")
        zip_path = self.root / "handovers" / name
        self.assertTrue(zip_path.is_file())
        self.assertNotIn(".partial", " ".join(self.handovers()))

        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            db_bytes = zf.read(db.DB_NAME)
            for member in names:
                self.assertNotIn(MARKER, zf.read(member), member)
        on_disk = {f"documents/{p.name}" for p in documents.documents_on_disk(self.copy)}
        self.assertTrue(on_disk and on_disk <= names)
        self.assertNotIn(MARKER, db_bytes)
        check = self.root / "check-handover.db"
        check.write_bytes(db_bytes)
        conn = sqlite3.connect(check)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM private_note").fetchone()[0], 0)
            self.assertGreater(conn.execute("SELECT COUNT(*) FROM person").fetchone()[0], 0)
        finally:
            conn.close()
        self.assertEqual(self.note_count(), notes)  # the church copy still has its Private notes
        self.assertEqual(sha(self.copy / db.DB_NAME), source_hash)  # and is not changed at all

        page = self.page(location)
        result = section(page, "handover").replace("<wbr>", "")
        self.assertIn("Private notes were removed", result)
        self.assertIn(str(zip_path.resolve()), result)
        self.assertIn(f'href="/copies/handovers/{name}"', result)
        status, headers, data = self.request("GET", f"/copies/handovers/{name}")
        self.assertEqual(status, 200)
        self.assertEqual(data, zip_path.read_bytes())
        self.assertIn(f"filename*=UTF-8''{name}", headers["content-disposition"])
        for bad in ("handover-nope-2001-01-01.zip", "..%2Fcopy%2Fchurch.db", "..%5Cfake%5Cchurch.db"):
            self.assertEqual(self.request("GET", f"/copies/handovers/{bad}")[0], 404, bad)

    def test_refusal_layout_follows_private_text_found_not_the_words(self):
        # words that name a Private note, but not the "text found" refusal: the plain layout with the sentence
        plain = handover.HandoverError("2 Private note(s) were still in the handover database. No handover was made.")
        with mock.patch.object(handover, "make_handover", side_effect=plain):
            status, _h, data = self.request("POST", "/copies/handover", {})
        box = section(data.decode("utf-8"), "handover")
        self.assertEqual(status, 400)
        self.assertIn("2 Private note(s) were still in the handover database.", box)
        self.assertIn("Nothing was changed. Fix this", box)
        self.assertNotIn("also written somewhere else", box)
        # the "text found" refusal, whatever its words: the list of places, not the message
        found = handover.HandoverError("Stopped.", private_text_found=True)
        with mock.patch.object(handover, "make_handover", side_effect=found):
            status, _h, data = self.request("POST", "/copies/handover", {})
        box = section(data.decode("utf-8"), "handover")
        self.assertEqual(status, 400)
        self.assertIn("The words of a Private note are also written somewhere else", box)
        self.assertNotIn("Stopped.", box)


class CopySwitchTest(LiveServer, unittest.TestCase):
    """Blank church copies in a temp copies root; the app started the default way (remember=True)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        assert "onedrive" not in str(self.root.resolve()).lower()
        self.a = self.root / "a"
        conn = db.create_church_copy(self.a, "Hội Thánh An Bình C3")
        people.add_person(conn, "Trần Thị Bé C3")
        conn.close()
        self.start(self.a, self.root, remember=True)
        self.addCleanup(self.stop)

    def post(self, path, form, expect=303):
        status, headers, data = self.request("POST", path, form)
        self.assertEqual(status, expect, data.decode("utf-8")[:2000])
        return headers, data.decode("utf-8")

    def page(self, path, expect=200):
        status, _h, text_ = self.get_text(path)
        self.assertEqual(status, expect, path)
        return text_

    def test_new_church_setup_opens_a_blank_copy_and_keeps_the_old_one(self):
        old_hash = sha(self.a / db.DB_NAME)
        headers, _ = self.post("/copies/new", {"church_name": "Hội Thánh Mới C3"})
        self.assertTrue(headers["location"].startswith("/?msg="), headers["location"])
        folder = self.root / "hoi-thanh-moi-c3"
        self.assertTrue((folder / db.DB_NAME).is_file())
        self.assertTrue((folder / db.DOCUMENTS_DIR).is_dir())
        self.assertEqual(self.httpd.copy_folder, folder.resolve())
        self.assertEqual(paths.read_current(self.root).resolve(), folder.resolve())

        conn = db.connect(folder / db.DB_NAME)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM person").fetchone()[0], 0)
            got = sorted((r["list_name"], r["name"]) for r in conn.execute("SELECT list_name, name FROM list_item"))
            want = sorted((list_name, name) for list_name, items in schema.DEFAULT_LISTS.items() for _c, name in items)
            self.assertEqual(got, want)  # the default lists only
            self.assertEqual(settings.get_setting(conn, "church_name"), "Hội Thánh Mới C3")
            for table in ("offering", "expense", "calendar_item", "document", "sent_document", "private_note"):
                self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0, table)
        finally:
            conn.close()

        page = self.page(headers["location"])
        self.assertIn("Hội Thánh Mới C3", page)  # the server shows the new copy
        self.assertIn("New church setup is done", page)
        self.assertEqual(sha(self.a / db.DB_NAME), old_hash)  # the old copy is not touched
        listing = section(self.page("/copies"), "copies")
        self.assertIn("Hội Thánh An Bình C3", listing)
        self.assertIn('name="folder" value="a"', listing)

    def test_open_another_copy_from_the_list(self):
        db.create_church_copy(self.root / "b", "Hội Thánh Bình Minh C3").close()
        (self.root / "not-a-copy").mkdir()
        listing = section(self.page("/copies"), "copies")
        self.assertIn("Hội Thánh Bình Minh C3", listing)
        self.assertIn('name="folder" value="b"', listing)
        self.assertNotIn("not-a-copy", listing)

        headers, _ = self.post("/copies/open", {"folder": "b"})
        self.assertEqual(self.httpd.copy_folder, (self.root / "b").resolve())
        self.assertEqual(paths.read_current(self.root).resolve(), (self.root / "b").resolve())
        self.assertIn("Opened Hội Thánh Bình Minh C3.", self.page(headers["location"]))
        self.post("/copies/open", {"folder": "a"})
        self.assertEqual(self.httpd.copy_folder, self.a.resolve())

        for bad in ("../a", "", "not-a-copy", str(self.root / "b"), "handovers"):
            _h, page = self.post("/copies/open", {"folder": bad}, expect=400)
            self.assertIn("There is no church copy with this folder name", page, bad)
        self.assertEqual(self.httpd.copy_folder, self.a.resolve())

    def test_a_copy_inside_onedrive_is_listed_but_not_opened(self):
        inside = self.root / "OneDrive - Home"
        inside.mkdir()
        shutil.copyfile(self.a / db.DB_NAME, inside / db.DB_NAME)
        listing = section(self.page("/copies"), "copies")
        self.assertIn("Inside OneDrive: not opened", listing)
        self.assertNotIn('value="OneDrive - Home"', listing)
        _h, page = self.post("/copies/open", {"folder": "OneDrive - Home"}, expect=400)
        self.assertIn("inside OneDrive", page)
        self.assertEqual(self.httpd.copy_folder, self.a.resolve())

    def test_a_church_called_handovers_does_not_take_the_handovers_folder(self):
        self.post("/copies/new", {"church_name": "Handovers"})
        self.assertEqual(self.httpd.copy_folder, (self.root / "handovers-2").resolve())
        self.assertFalse((self.root / copy_pages.HANDOVERS / db.DB_NAME).exists())

    def test_new_church_setup_refusals(self):
        before = sorted(p.name for p in self.root.iterdir())
        _h, page = self.post("/copies/new", {"church_name": "   "}, expect=400)
        self.assertIn("Church name is required", page)
        self.assertIn('id="f-church_name-error"', page)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), before)
        self.assertEqual(self.httpd.copy_folder, self.a.resolve())


class SettingsPagesTest(PagesTestBase):
    def test_change_the_church_name_and_the_care_months(self):
        conn = self.db()
        old_name = settings.get_setting(conn, "church_name")
        self.addCleanup(settings.set_setting, conn, "church_name", old_name)
        self.addCleanup(settings.set_setting, conn, "care_reminder_months", "3")
        page = self.page("/settings")
        self.assertRegex(page, r'name="care_reminder_months"[^>]* value="3"')
        self.assertIn('max="24"', page)

        headers, _ = self.post("/settings", {"church_name": "Hội Thánh Tin Lành Bình An C3",
                                             "care_reminder_months": " 6 "})
        self.assertTrue(headers["location"].startswith("/settings?msg="))
        self.assertEqual(settings.get_setting(conn, "care_reminder_months"), "6")
        self.assertEqual(care.reminder_months(conn), 6)
        self.assertEqual(settings.get_setting(conn, "church_name"), "Hội Thánh Tin Lành Bình An C3")
        page = self.page(headers["location"])
        self.assertIn("Settings saved", page)
        self.assertRegex(page, r'name="care_reminder_months"[^>]* value="6"')
        self.assertIn('<span class="brand-church" lang="vi">Hội Thánh Tin Lành Bình An C3</span>', page)
        effect = section(page, "settings-effect")
        self.assertIn("No Visit in the last 6 months", effect)
        self.assertIn(f">{len(care.needs_visit(conn))} ", effect)
        self.assertIn("No Visit in the last 6 months", section(self.page("/"), "needs-visit"))

    def test_bad_values_are_refused(self):
        conn = self.db()
        before = settings.get_setting(conn, "care_reminder_months")
        for bad in ("0", "25", "3.5", "abc", "", "-1", "１２", "100"):
            _h, page = self.post("/settings", {"church_name": fake.CHURCH_NAME, "care_reminder_months": bad},
                                 expect=400)
            self.assertIn('id="f-care_reminder_months-error"', page, bad)
            self.assertIn("from 1 to 24", page, bad)
        _h, page = self.post("/settings", {"church_name": " ", "care_reminder_months": "4"}, expect=400)
        self.assertIn('id="f-church_name-error"', page)
        self.assertEqual(settings.get_setting(conn, "care_reminder_months"), before)
        self.assertEqual(settings.get_setting(conn, "church_name"), fake.CHURCH_NAME)


class SmallLogicTest(unittest.TestCase):
    def test_parse_months(self):
        self.assertEqual(settings_pages.parse_months("1"), 1)
        self.assertEqual(settings_pages.parse_months(" 24 "), 24)
        for bad in ("0", "25", "3.5", "abc", "", None, "-1", "１２", "+3"):
            with self.assertRaises(ValueError):
                settings_pages.parse_months(bad)

    def test_private_text_places_never_returns_the_text(self):
        tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        self.addCleanup(tmp.cleanup)
        conn = db.create_church_copy(pathlib.Path(tmp.name) / "c", "Hội Thánh C3")
        self.addCleanup(conn.close)
        a = people.add_person(conn, "Lê Văn A")
        b = people.add_person(conn, "Lê Văn B", note="có chữ BÍ MẬT C3 ở đây")
        self.assertEqual(copy_pages.private_text_places(conn), [])
        people.add_private_note(conn, a, "BÍ MẬT C3")
        people.add_private_note(conn, a, "abc")  # under 4 characters: not searched (like the Handover check)
        places = copy_pages.private_text_places(conn)
        self.assertEqual(places, [(a, "person", b, "note")])
        self.assertNotIn("BÍ MẬT", repr(places))
        self.assertEqual(copy_pages._safe_label("Lê Văn B", ["BÍ MẬT C3"], "Person 2"), "Lê Văn B")
        self.assertEqual(copy_pages._safe_label("x BÍ MẬT C3", ["BÍ MẬT C3"], "Person 2"), "Person 2")


if __name__ == "__main__":
    unittest.main()
