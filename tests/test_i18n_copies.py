"""I18N-U6: the Copies page and the Handover screens in Tiếng Việt and English.

Real servers on 127.0.0.1 (port 0) over fake churches in temp folders, one Vietnamese and one English,
built the same way. Every screen of this card (the Copies page, Make Handover and its result page, the
refused Handover, the missing Handover zip, the refused New church setup and the refused open) on the
Vietnamese copy has ``<html lang="vi">``, the switch, no English word left and no ``[[key]]``; on the
English copy no ``[[key]]``. New church setup from the Copies page makes the default lists in the language
picked on the form. A Handover keeps the ``language`` setting and holds no Private note. The errors of
``handover.py`` and ``paths.py`` are ``TextError``: ``str()`` English, ``error_text(e, "vi")`` Vietnamese.
"""

import datetime as dt
import html
import pathlib
import re
import shutil
import sqlite3
import tempfile
import unittest
import urllib.parse
import zipfile
from unittest import mock

import _support
from churchmgr import db, documents, fake, handover, lists, money, paths, people, schema, server, settings, ui
from churchmgr.i18n import TEXT, TextError, english_left, error_text
from churchmgr.pages import copies as copy_pages
from churchmgr.pages.documents import fmt_size
from test_i18n_core import html_lang, switch
from test_pages_people import section
from test_server import LiveServer

LANGS = ("vi", "en")
TODAY = dt.date.today().isoformat()
OPTION = '<option value="{code}"{sel}>{name}</option>'


def flash(page):
    m = re.search(r'<p class="flash" role="status">([^<]*)</p>', page)
    return html.unescape(m.group(1)) if m else None


def plain(fragment):
    """The text of an HTML fragment, without its tags and ``<wbr>``."""
    return html.unescape(re.sub(r"<[^>]+>", "", fragment))


def made_name(location):
    return urllib.parse.parse_qs(urllib.parse.urlsplit(location).query)["made"][0]


class Site(LiveServer):
    """The request helpers of ``LiveServer`` on one server."""

    def __init__(self, httpd):
        self.httpd = httpd


class ScreensBase(unittest.TestCase):
    """Helpers for a test class with one server per language in ``cls.sites``."""

    sites = {}

    def fetch(self, lang, method, path, expect=200, form=None):
        status, headers, data = self.sites[lang].request(method, path, form if method == "POST" else None)
        page = data.decode("utf-8")
        self.assertEqual(status, expect, (lang, method, path, page[:800]))
        return headers, page

    def get(self, lang, path, expect=200):
        return self.fetch(lang, "GET", path, expect)[1]

    def post(self, lang, path, form, expect=303):
        return self.fetch(lang, "POST", path, expect, form)

    def assert_screen(self, lang, page, where):
        """vi: html lang, the switch with Tiếng Việt pressed, no English word left, no [[key]]. en: no [[key]]."""
        self.assertNotIn("[[", page, where)
        if lang == "vi":
            self.assertEqual(html_lang(page), "vi", where)
            self.assertEqual(switch(page)[1:], ("true", "false"), where)
            self.assertEqual(english_left(page), [], where)
        else:
            self.assertEqual(html_lang(page), "en", where)


class CopiesScreensTest(ScreensBase):
    """One fake church per language (with Private notes), a second church copy and a church copy inside a
    OneDrive folder in the same copies root. Started with a set folder (``--copy``)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        base = pathlib.Path(cls.tmp.name)
        assert "onedrive" not in str(base.resolve()).lower()
        cls.roots, cls.copies, cls.sites = {}, {}, {}
        for lang in LANGS:
            root = base / lang
            copy = root / "fake"
            fake.build_fake_church(copy, people=20, lang=lang)
            db.create_church_copy(root / "other", "Hội Thánh Bình Minh U6", lang).close()
            (root / "OneDrive - Home").mkdir()  # listed, never opened (made outside, then put there)
            shutil.copyfile(root / "other" / db.DB_NAME, root / "OneDrive - Home" / db.DB_NAME)
            httpd = server.make_server(copy, root, 0, remember=False)
            server.serve_in_thread(httpd)
            cls.roots[lang], cls.copies[lang], cls.sites[lang] = root, copy, Site(httpd)

    @classmethod
    def tearDownClass(cls):
        for site in cls.sites.values():
            site.httpd.shutdown()
            site.httpd.server_close()
        cls.tmp.cleanup()

    def db(self, lang):
        conn = db.connect(self.copies[lang] / db.DB_NAME)
        self.addCleanup(conn.close)
        return conn

    def screens(self, lang):
        """Every screen of this card on one server: ``[(where, page), ...]``. Makes one Handover."""
        out = [("GET /copies", self.get(lang, "/copies"))]
        headers, _ = self.post(lang, "/copies/handover", {})
        out.append(("Handover result", self.get(lang, headers["location"])))
        out.append(("missing zip", self.get(lang, "/copies/handovers/handover-nope-2001-01-01.zip", 404)))
        for form in ({"folder": "nope"}, {"folder": "OneDrive - Home"}):
            out.append((f"open {form}", self.post(lang, "/copies/open", form, 400)[1]))
        for form in ({"church_name": "  ", "language": lang}, {"church_name": "Hội Thánh U6", "language": "fr"}):
            out.append((f"new {form}", self.post(lang, "/copies/new", form, 400)[1]))
        refused = handover.HandoverError("copies.err_door")
        with mock.patch.object(handover, "make_handover", side_effect=refused):
            out.append(("plain refusal", self.post(lang, "/copies/handover", {}, 400)[1]))
        return out

    def test_every_screen_in_both_languages(self):
        for lang in LANGS:
            for where, page in self.screens(lang):
                self.assert_screen(lang, page, (lang, where))

    def test_the_check_finds_english_words(self):
        """The vi check is real: on the English Copies page it finds English words."""
        found = {w.lower() for w in english_left(self.get("en", "/copies"))}
        self.assertTrue({"handover", "copies", "folder"} <= found, found)

    def test_the_copies_page_in_vietnamese(self):
        page = self.get("vi", "/copies")
        self.assertIn("<h1>Dữ liệu</h1>", page)
        this = section(page, "this-copy")
        self.assertIn(">Dữ liệu Hội Thánh này</h2>", this)
        self.assertIn("<dt>Nơi chứa dữ liệu</dt>", this)
        self.assertIn(f'<span class="path" lang="zxx">{self.copies["vi"].resolve()}'.replace("\\", "\\<wbr>"), this)
        self.assertIn('Church Manager được mở với một nơi lưu cố định (<span lang="zxx">--copy</span>)', this)
        self.assertRegex(plain(this), r"church\.db \(20 người\) và nơi lưu tài liệu \(\d+ Tài liệu, ")
        listing = section(page, "copies")
        self.assertIn('aria-label="Mở Hội Thánh Bình Minh U6">Mở</button>', listing)
        self.assertIn('<span class="tag open">Đang mở</span>', listing)
        self.assertIn('<span class="faint">Nằm trong OneDrive: không mở</span>', listing)
        self.assertIn('<th scope="col">Nơi lưu</th>', listing)
        self.assertIn(">Tạo Bàn giao</button>", section(page, "handover"))
        setup = section(page, "new-church-setup")
        self.assertIn(">Lập dữ liệu Hội Thánh mới</h2>", setup)
        self.assertIn('<option value="vi" selected>Tiếng Việt</option><option value="en">English</option>', setup)
        self.assertIn('<label for="f-language">Ngôn ngữ</label>', setup)

    def test_a_handover_keeps_the_language_and_no_private_note(self):
        for lang in LANGS:
            notes = self.db(lang).execute("SELECT COUNT(*) FROM private_note").fetchone()[0]
            self.assertGreater(notes, 0)
            headers, _ = self.post(lang, "/copies/handover", {})
            self.assertEqual(flash(self.get(lang, headers["location"])),
                             {"vi": "Đã tạo Bàn giao. Các Ghi chú cá nhân đã được bỏ ra.",
                              "en": "Handover made. Private notes were removed."}[lang])
            zip_path = self.roots[lang] / copy_pages.HANDOVERS / made_name(headers["location"])
            check = self.roots[lang] / f"check-{lang}.db"
            with zipfile.ZipFile(zip_path) as zf:
                check.write_bytes(zf.read(db.DB_NAME))
            conn = sqlite3.connect(check)
            try:
                conn.row_factory = sqlite3.Row
                self.assertEqual(settings.get_setting(conn, settings.LANGUAGE), lang)
                self.assertEqual(settings.get_language(conn), lang)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM private_note").fetchone()[0], 0)
            finally:
                conn.close()
            self.assertEqual(self.db(lang).execute("SELECT COUNT(*) FROM private_note").fetchone()[0], notes)

    def test_the_handover_result_page_in_vietnamese(self):
        headers, _ = self.post("vi", "/copies/handover", {})
        name = made_name(headers["location"])
        box = section(self.get("vi", headers["location"]), "handover")
        self.assertIn("<p><strong>Đã tạo Bàn giao.</strong> Các Ghi chú cá nhân đã được bỏ ra.</p>", box)
        self.assertIn('<p class="hint">Đã lưu thành <span class="path" lang="zxx">', box)
        self.assertIn(f'href="/copies/handovers/{name}">Tải về tệp ZIP Bàn giao</a>', box)
        self.assertIn(f'<a class="file-name" href="/copies/handovers/{name}" lang="zxx">{name}</a>', box)
        self.assertIn('<h3 class="sub-head">Các Bàn giao đã tạo</h3>', box)

    def test_refused_screens_say_why_in_vietnamese(self):
        _h, page = self.post("vi", "/copies/open", {"folder": "nope"}, 400)
        self.assertIn('<p class="error" role="alert">Không có Dữ liệu Hội Thánh nào có nơi lưu tên này trong nơi '
                      "chứa dữ liệu.</p>", section(page, "copies"))
        _h, page = self.post("vi", "/copies/open", {"folder": "OneDrive - Home"}, 400)
        self.assertIn("Dữ liệu Hội Thánh này nằm trong OneDrive nên không được mở.", section(page, "copies"))
        _h, page = self.post("vi", "/copies/new", {"church_name": " ", "language": "vi"}, 400)
        self.assertIn('<p class="error" id="f-church_name-error">Cần nhập Tên Hội Thánh.</p>', page)
        _h, page = self.post("vi", "/copies/new", {"church_name": "Hội Thánh U6", "language": "fr"}, 400)
        self.assertIn('<p class="error" id="f-language-error">Ngôn ngữ phải là Tiếng Việt hoặc English.</p>', page)
        self.assertNotIn("Hội Thánh U6", section(page, "copies"))  # nothing was made
        refused = handover.HandoverError("copies.err_door")
        with mock.patch.object(handover, "make_handover", side_effect=refused):
            _h, page = self.post("vi", "/copies/handover", {}, 400)
        self.assertIn("<p><strong>Chưa tạo Bàn giao.</strong> Cổng Hermes chưa tắt trong cơ sở dữ liệu Bàn giao. "
                      "Chưa tạo Bàn giao.</p><p>Không có gì bị thay đổi.", section(page, "handover"))
        page = self.get("vi", "/copies/handovers/handover-nope-2001-01-01.zip", 404)
        self.assertIn('<p class="lead">Không có tệp ZIP Bàn giao nào có tên này.</p>', page)

    # ---- a refused Handover: the words of a Private note are also written somewhere else

    def refusal(self, lang, owner_index, words, extra):
        """Add a Private note with ``words`` to a Person, let ``extra(conn, words)`` write them elsewhere, and
        return the refused Handover page (400). Everything is taken back after the test."""
        conn = self.db(lang)
        owner = people.list_persons(conn)[owner_index]["id"]
        note_id = people.add_private_note(conn, owner, words)
        self.addCleanup(conn.execute, "DELETE FROM private_note WHERE id = ?", (note_id,))
        extra(conn, words)
        before = sorted(p.name for p in (self.roots[lang] / copy_pages.HANDOVERS).glob("*"))
        _h, page = self.post(lang, "/copies/handover", {}, 400)
        self.assertEqual(sorted(p.name for p in (self.roots[lang] / copy_pages.HANDOVERS).glob("*")), before)
        self.assertNotIn(words, page)
        return section(page, "handover"), page

    def written_in_four_places(self, lang):
        def extra(conn, words):
            persons = people.list_persons(conn)
            other = persons[1]["id"]
            people.update_person(conn, other, note=f"Ghi chú: {words}")
            self.addCleanup(people.update_person, conn, other, note=None)
            fund = lists.get_list(conn, "fund")[0]["id"]
            offering = money.add_offering(conn, TODAY, 50000, fund, giver_person_id=other, note=words)
            self.addCleanup(money.delete_offering, conn, offering)
            doc = documents.add_document(conn, self.copies[lang], f"Ghi: {words}\n".encode("utf-8"), "u6.txt",
                                         person_id=persons[2]["id"])
            self.addCleanup(documents.delete_document, conn, self.copies[lang], doc)
            stray = db.documents_folder(self.copies[lang].resolve()) / ("cd" * 16 + ".txt")
            stray.write_bytes(f"x {words}\n".encode("utf-8"))
            self.addCleanup(stray.unlink)
            return doc

        return self.refusal(lang, 0, "U6 lời riêng tư 7731", extra)

    def test_a_refusal_with_places_in_both_languages(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                box, page = self.written_in_four_places(lang)
                self.assert_screen(lang, page, (lang, "refusal with places"))
                if lang == "en":
                    self.assertIn("The words of a Private note are also written somewhere else", box)
                    continue
                self.assertIn("<p><strong>Chưa tạo Bàn giao.</strong> Chữ của một Ghi chú cá nhân cũng được ghi ở chỗ "
                              "khác trong Dữ liệu Hội Thánh này", box)
                lines = re.findall(r"<li>(.*?)</li>", box)
                self.assertEqual(len(lines), 4, lines)
                for line in lines:
                    self.assertRegex(line, r'^Ghi chú cá nhân của <a href="/people/\d+#private-note"><span lang="vi">'
                                           r'[^<]+</span></a> cũng có ở ')
                text = sorted(plain(line.replace("<wbr>", "")).split(" cũng có ở ", 1)[1] for line in lines)
                self.assertRegex(text[0], r"^Tài liệu u6\.txt của [^.]+\. Xóa$")
                self.assertRegex(text[1], r"^ghi chú của Người [^.]+\.$")
                self.assertEqual(text[2], "ghi chú trong Dâng hiến.")
                self.assertRegex(text[3], r"^tệp c[cd]+\.txt trong nơi lưu tài liệu\. Không có Tài liệu nào trong ứng "
                                          r"dụng giữ tệp này: hãy mở .+ trên máy tính rồi xóa tệp đó\.$")
                joined = "".join(lines).replace("<wbr>", "")
                self.assertIn('href="/money">Dâng hiến</a>.', joined)
                self.assertIn('aria-label="Xóa Tài liệu u6.txt">Xóa</a>', joined)
                self.assertIn(f'tệp <span class="path" lang="zxx">{"cd" * 16}.txt</span> trong nơi lưu tài liệu.', joined)
                self.assertIn("<p>Để sửa, hãy bỏ những chữ riêng tư đó khỏi từng chỗ ở trên. Với một Tài liệu, hãy bấm "
                              "Xóa:", box)

    def test_a_refusal_in_a_link_table_and_more_places(self):
        """A Private note that is a code (``Head``) is found in a link table: its table and column have no word
        of their own, so their English names are shown, marked ``lang="en"``. Only 2 places, then "more"."""
        for lang in LANGS:
            with self.subTest(lang=lang):
                with mock.patch.object(copy_pages, "PLACE_ROWS", 2):
                    box, page = self.refusal(lang, -1, "Head", lambda conn, words: None)
                self.assert_screen(lang, page, (lang, "refusal in a link table"))
                lines = re.findall(r"<li>(.*?)</li>", box)
                self.assertEqual(len(lines), 3, lines)
                joined = "".join(lines)
                if lang == "vi":
                    self.assertIn('cũng có ở ô <span lang="en">family role</span> trong <a href="/">bảng '
                                  '<span lang="en">family link</span></a>.', joined)
                    self.assertRegex(lines[2], r"^Và \d+ chỗ khác nữa\.$")
                else:
                    self.assertIn('is also written in a family role in <a href="/">family link</a>.', joined)
                    self.assertRegex(lines[2], r"^And \d+ more places\.$")

    # ---- CRIT-5: the developer words wait under a closed "Technical details" fold

    def test_developer_words_wait_under_a_closed_fold(self):
        """On the Copies page and the Handover result page, in both languages: church.db, --copy, current.txt,
        every full path and every size in bytes are only inside the 3 folds (closed); outside them the size is
        in plain words and the sentences say what the pastor can do."""
        for lang in LANGS:
            with self.subTest(lang=lang):
                headers, _ = self.post(lang, "/copies/handover", {})
                root = self.roots[lang].resolve()
                zip_path = root / copy_pages.HANDOVERS / made_name(headers["location"])
                size = self.db(lang).execute("SELECT COALESCE(SUM(size), 0) FROM document").fetchone()[0]
                for where, page in (("GET /copies", self.get(lang, "/copies")),
                                    ("Handover result", self.get(lang, headers["location"]))):
                    body = page.split("<main", 1)[1].replace("<wbr>", "")
                    self.assertNotIn('<details class="tech" open', body, where)
                    folds = [plain(f) for f in re.findall(r'<details class="tech">(.*?)</details>', body, re.S)]
                    outside = plain(re.sub(r'<details class="tech">.*?</details>', " ", body, flags=re.S))
                    self.assertEqual([f.split(TEXT[lang]["copies.tech"], 1)[0] for f in folds], ["", "", ""], where)
                    inside = " ".join(folds)
                    words = ["church.db", "--copy", "current.txt", str(self.copies[lang].resolve()), str(root),
                             str(root / copy_pages.HANDOVERS)]
                    if where == "Handover result":
                        words.append(str(zip_path))
                    for word in words:
                        self.assertNotIn(word, outside, (where, word))
                        self.assertIn(word, inside, (where, word))
                    self.assertNotRegex(outside, r"\bbytes?\b", where)
                    self.assertIn(f"({copy_pages.size_text(size, lang)})", outside, where)
                    self.assertIn(f"{fmt_size(size, lang)})", inside, where)  # in bytes below 1 KB
                    for key in ("copies.set_folder_plain", "copies.list_hint", "copies.keep_outside"):
                        self.assertIn(TEXT[lang][key], outside, (where, key))



class NewChurchSetupTest(ScreensBase):
    """A Vietnamese church copy ``a`` in a temp copies root; the app started the default way (remember)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        assert "onedrive" not in str(self.root.resolve()).lower()
        self.a = self.root / "a"
        conn = db.create_church_copy(self.a, "Hội Thánh An Bình U6", "vi")
        people.add_person(conn, "Trần Thị Bé U6")
        conn.close()
        httpd = server.make_server(self.a, self.root, 0, remember=True)
        server.serve_in_thread(httpd)
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        self.httpd = httpd
        self.sites = {"vi": Site(httpd)}

    def items(self, folder):
        conn = db.connect(folder / db.DB_NAME)
        try:
            names = sorted((r["list_name"], r["name"]) for r in conn.execute("SELECT list_name, name FROM list_item"))
            return names, settings.get_setting(conn, settings.LANGUAGE)
        finally:
            conn.close()

    def defaults(self, lang):
        return sorted((list_name, vi if lang == "vi" else en)
                      for list_name, items in schema.DEFAULT_LISTS.items() for _c, vi, en in items)

    def test_the_form_starts_on_tieng_viet(self):
        page = self.get("vi", "/copies")
        self.assert_screen("vi", page, "GET /copies")
        self.assertIn(OPTION.format(code="vi", sel=" selected", name="Tiếng Việt"), section(page, "new-church-setup"))

    def test_new_church_setup_in_vietnamese(self):
        headers, _ = self.post("vi", "/copies/new", {"church_name": "Hội Thánh Mới U6", "language": "vi"})
        folder = self.root / "hoi-thanh-moi-u6"
        self.assertEqual(self.httpd.copy_folder, folder.resolve())
        self.assertEqual(self.items(folder), (self.defaults("vi"), "vi"))
        page = self.get("vi", headers["location"])
        self.assertEqual(flash(page), "Đã lập dữ liệu Hội Thánh mới: Hội Thánh Mới U6. Đây là Trang chủ của dữ liệu "
                                      "đó. Các Dữ liệu Hội Thánh khác vẫn được giữ trong Dữ liệu.")
        self.assertEqual(html_lang(page), "vi")
        page = self.get("vi", "/copies")  # the new blank copy: 0 Persons, 0 Documents, 0 byte
        self.assert_screen("vi", page, "GET /copies of the new copy")
        this = plain(section(page, "this-copy"))
        self.assertIn("church.db (0 người) và nơi lưu tài liệu (0 Tài liệu, 0 byte)", this)
        self.assertIn("Dữ liệu Hội Thánh này (ghi trong current.txt)", this)
        self.assertIn("đang mở · 2 Dữ liệu Hội Thánh trong nơi chứa dữ liệu", plain(page))

    def test_new_church_setup_in_english(self):
        headers, _ = self.post("vi", "/copies/new", {"church_name": "Grace Church U6", "language": "en"})
        folder = self.root / "grace-church-u6"
        self.assertEqual(self.items(folder), (self.defaults("en"), "en"))
        # the flash is in the language of the next page: the new church copy's (English) ...
        self.assertTrue(flash(self.get("vi", headers["location"])).startswith("New church setup is done:"))
        # ... and the new church copy shows its screens in English
        page = self.get("vi", "/copies")
        self.assert_screen("en", page, "GET /copies of the English copy")
        self.assertIn("church.db (0 People) and the documents folder (0 Documents, 0 bytes)",
                      plain(section(page, "this-copy")))

    def test_open_another_church_copy(self):
        db.create_church_copy(self.root / "b", "Hội Thánh Bình Minh U6", "en").close()
        page = self.get("vi", "/copies")
        self.assert_screen("vi", page, "GET /copies with two copies")
        self.assertIn('aria-label="Mở Hội Thánh Bình Minh U6">Mở</button>', section(page, "copies"))
        headers, _ = self.post("vi", "/copies/open", {"folder": "b"})
        self.assertEqual(self.httpd.copy_folder, (self.root / "b").resolve())
        page = self.get("vi", headers["location"])
        self.assertEqual(flash(page), "Opened Hội Thánh Bình Minh U6.")
        self.assertEqual(html_lang(page), "en")  # copy b is an English church copy
        headers, _ = self.post("vi", "/copies/open", {"folder": "a"})
        self.assertEqual(flash(self.get("vi", headers["location"])), "Đã mở Hội Thánh An Bình U6.")
        headers, _ = self.post("vi", "/copies/open", {"folder": "a"})
        self.assertEqual(flash(self.get("vi", headers["location"])), "Dữ liệu Hội Thánh này đang mở.")
        _h, page = self.post("vi", "/copies/open", {"folder": "../b"}, 400)
        self.assert_screen("vi", page, "refused open")

    def test_plain_words_say_which_copy_opens_at_start_and_how_to_open_another(self):
        """CRIT-5: outside the folds the row Mở khi khởi động names the church copy in plain words (this one, or
        another one), never current.txt or a path (those are in the fold); the line under Các Dữ liệu Hội Thánh
        is there only when another church copy can be opened."""
        def view():
            page = self.get("vi", "/copies")
            self.assert_screen("vi", page, "GET /copies")
            this = section(page, "this-copy")
            outside = re.sub(r'<details class="tech">.*?</details>', "", this, flags=re.S)
            fold = plain(re.search(r'<details class="tech">(.*?)</details>', this, re.S).group(1).replace("<wbr>", ""))
            row = re.search(r"<dt>Mở khi khởi động</dt><dd>(.*?)</dd>", outside).group(1)
            return row, fold, page

        row, fold, page = view()  # nothing in current.txt yet; only the open church copy in the copies folder
        self.assertEqual(row, ui.DASH)
        self.assertNotIn('<span class="meta">', section(page, "copies"))
        paths.write_current(self.root, self.a)
        row, fold, _page = view()
        self.assertEqual(row, "Dữ liệu Hội Thánh này")
        self.assertIn("Dữ liệu Hội Thánh này (ghi trong current.txt)", fold)
        other = self.root / "b"
        db.create_church_copy(other, "Hội Thánh Bình Minh U6", "en").close()
        paths.write_current(self.root, other)
        row, fold, page = view()
        self.assertEqual(row, "Một Dữ liệu Hội Thánh khác")
        self.assertIn(f"{other.resolve()} (ghi trong current.txt)", fold)
        self.assertIn('<span class="meta">Bấm Mở để chuyển sang một Dữ liệu Hội Thánh khác.</span>',
                      section(page, "copies"))


class CopiesTextErrorTest(unittest.TestCase):
    """The errors of ``paths.py`` and ``handover.py``: ``str()`` English, ``error_text(e, "vi")`` Vietnamese."""

    def setUp(self):
        self.tmp = _support.temp_folder(self)
        self.copy = self.tmp / "c"
        conn = db.create_church_copy(self.copy, "Hội Thánh U6", "vi")
        people.add_private_note(conn, people.add_person(conn, "Lê Văn U6"), "Cầu nguyện riêng U6")
        conn.close()

    def check(self, exc, key, en, vi):
        self.assertIsInstance(exc, TextError)
        self.assertIsInstance(exc, ValueError)
        self.assertEqual(exc.key, key)
        self.assertEqual(str(exc), en)
        self.assertEqual(error_text(exc, "en"), en)
        self.assertEqual(error_text(exc, "vi"), vi)

    def test_paths(self):
        inside = self.tmp / "OneDrive - Home" / "c"
        with self.assertRaises(paths.CopyPathError) as ctx:
            paths.check_not_onedrive(inside)
        where = inside.resolve()
        self.check(ctx.exception, "copies.err_onedrive",
                   f"The church copy must not be inside OneDrive: {where}. Choose a folder outside OneDrive, "
                   "for example under %LOCALAPPDATA%.",
                   f"Dữ liệu Hội Thánh không được nằm trong OneDrive: {where}. Hãy chọn một nơi lưu ngoài OneDrive, "
                   "ví dụ trong %LOCALAPPDATA%.")
        with self.assertRaises(paths.CopyPathError) as ctx:
            paths.check_not_onedrive("  ")
        self.check(ctx.exception, "copies.err_folder_required", "A folder is required for the church copy.",
                   "Cần chọn nơi lưu cho Dữ liệu Hội Thánh.")

    def test_handover(self):
        out = self.tmp / "out"
        with self.assertRaises(handover.HandoverError) as ctx:
            handover.make_handover(self.copy, self.tmp / "OneDrive" / "out")
        self.assertEqual(ctx.exception.key, "copies.err_onedrive")
        self.assertTrue(error_text(ctx.exception, "vi").startswith("Dữ liệu Hội Thánh không được nằm trong OneDrive"))
        missing = (self.tmp / "none").resolve()
        with self.assertRaises(handover.HandoverError) as ctx:
            handover.make_handover(missing, out)
        self.check(ctx.exception, "copies.err_no_copy", f"No church copy in {missing}: church.db is missing.",
                   f"Không có Dữ liệu Hội Thánh trong {missing}: thiếu church.db.")
        with self.assertRaises(handover.HandoverError) as ctx:
            handover.make_handover(self.copy, self.copy / db.DOCUMENTS_DIR / "x")
        self.check(ctx.exception, "copies.err_out_in_documents",
                   "Save the handover outside the documents folder of the church copy.",
                   "Hãy lưu Bàn giao ở ngoài nơi lưu tài liệu của Dữ liệu Hội Thánh.")
        with mock.patch.object(handover, "_strip_private", lambda path: None):
            with self.assertRaises(handover.HandoverError) as ctx:
                handover.make_handover(self.copy, out)
        self.check(ctx.exception, "copies.err_notes_left",
                   "1 Private note(s) were still in the handover database. No handover was made.",
                   "Vẫn còn 1 Ghi chú cá nhân trong cơ sở dữ liệu Bàn giao. Chưa tạo Bàn giao.")
        self.assertFalse(ctx.exception.private_text_found)
        found = handover.HandoverError("copies.err_text_in_document", private_text_found=True)
        self.assertTrue(found.private_text_found)
        self.assertTrue(error_text(found, "vi").startswith("Chữ của một Ghi chú cá nhân cũng được ghi trong"))

    def test_a_plain_sentence_stays_as_it_is(self):
        exc = handover.HandoverError("zip check", private_text_found=True)
        self.assertEqual((exc.key, str(exc), error_text(exc, "vi")), ("copies.err_plain", "zip check", "zip check"))
        self.assertTrue(exc.private_text_found)


class CopiesTextTableTest(unittest.TestCase):
    CODE = [_support.ROOT / "churchmgr" / name for name in ("pages/copies.py", "handover.py", "paths.py")]

    def test_every_key_in_the_code_is_in_both_languages(self):
        used = set()
        for path in self.CODE:
            used |= set(re.findall(r'"((?:copies|core|settings|setup|people)\.[a-z_0-9]+)"', path.read_text("utf-8")))
        self.assertIn("copies.err_onedrive", used)
        plural = {"copies.documents", "copies.copies", "people.count"}  # tn() keys
        for key in sorted(used):
            for lang in LANGS:
                names = [f"{key}_one", f"{key}_many"] if key in plural else [key]
                for name in names:
                    self.assertIn(name, TEXT[lang], (lang, name))

    def test_the_vietnamese_words_hold_no_english_word(self):
        """No English word in the vi ``copies.*`` values: their all-ASCII words that are English words of the
        table (and in no Vietnamese text of another section, like Gia đình, OneDrive, Church Manager) are only
        the names ZIP and byte."""
        def words(values):
            return {w.lower() for v in values for w in re.findall(r"[^\W\d_]+", re.sub(r"\{[^{}]*\}", " ", v))
                    if w.isascii() and len(w) >= 3}

        others_vi = words(v for k, v in TEXT["vi"].items() if not k.startswith("copies."))
        english = words(TEXT["en"].values()) - others_vi
        mine = words(v for k, v in TEXT["vi"].items() if k.startswith("copies."))
        self.assertLessEqual(mine & english, {"zip", "byte"})

    def test_a_size_in_plain_words(self):
        """CRIT-5: below 1 KB a size outside the folds says "under 1 KB" / "dưới 1 KB"; from 1 KB it is
        ``fmt_size`` (integer maths only). ``copies.bytes`` is gone: the fold says bytes with ``fmt_size``."""
        for size, vi_words, en_words in ((0, "dưới 1 KB", "under 1 KB"), (1023, "dưới 1 KB", "under 1 KB"),
                                         (1024, "1 KB", "1 KB"), (1025, "2 KB", "2 KB"),
                                         (5 * 1024 * 1024, "5,0 MB", "5,0 MB")):
            self.assertEqual((copy_pages.size_text(size, "vi"), copy_pages.size_text(size, "en")),
                             (vi_words, en_words), size)
        self.assertEqual((fmt_size(137, "vi"), fmt_size(137, "en")), ("137 byte", "137 bytes"))
        for lang in LANGS:
            self.assertEqual([k for k in TEXT[lang] if k.startswith("copies.bytes")], [], lang)


if __name__ == "__main__":
    unittest.main()
