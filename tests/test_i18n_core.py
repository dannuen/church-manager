"""I18N-U1b: the language on screen. The switch on every page, ``<html lang>``, the server pages (404, 400,
500), the first run (New church setup) and the Settings page, through real servers on 127.0.0.1 (port 0)
over fake churches in temp folders. These tests read Tiếng Việt; the old tests stay English.
"""

import contextlib
import html
import io
import pathlib
import re
import tempfile
import unittest
import urllib.parse

import _support  # noqa: F401 - puts the repo root on sys.path
from churchmgr import db, fake, i18n, lists, schema, server, settings, ui
from churchmgr.i18n import TEXT, english_left
from churchmgr.pages import settings as settings_pages
from test_server import LiveServer

NAV_VI = ("Trang chủ", "Mọi người", "Gia đình", "Chi phái", "Lịch", "Tài chính", "Thăm viếng", "Tài liệu",
          "Văn bản đi", "Danh mục", "Dữ liệu", "Cài đặt", "Tìm kiếm")
NAV_EN = ("Dashboard", "People", "Families", "Chi phái", "Calendar", "Money", "Care", "Documents",
          "Sent documents", "Lists", "Copies", "Settings", "Search")
SWITCH = re.compile(
    r'<main class="canvas" id="main" tabindex="-1"><form class="lang-switch" method="post" action="/language"[^>]*>'
    r'<input type="hidden" name="next" value="([^"]*)">'
    r'<button name="lang" value="vi" lang="vi" aria-pressed="(true|false)">Tiếng Việt</button>'
    r'<button name="lang" value="en" lang="en" aria-pressed="(true|false)">English</button></form>')
LANG_SELECT = ('<select class="input" id="f-language" name="language" aria-describedby="f-language-hint">'
               '<option value="vi"{vi}>Tiếng Việt</option><option value="en"{en}>English</option></select>')


def switch(page):
    """``(next, vi pressed, en pressed)``. The switch must be the first thing in ``main.canvas``."""
    m = SWITCH.search(page)
    assert m is not None, "no language switch at the top of main.canvas"
    return html.unescape(m.group(1)), m.group(2), m.group(3)


def html_lang(page):
    return re.match(r'<!doctype html>\n<html lang="(\w+)">', page).group(1)


def nav_words(page):
    """``(menu label, the 13 menu words)``: the menu items before the phone's More fold (CRIT-2)."""
    nav = re.search(r'<nav class="nav" aria-label="([^"]*)">(.*?)</nav>', page, re.S)
    items = nav.group(2).split('<details class="nav-more">')[0]
    return nav.group(1), tuple(re.findall(r'<a class="nav-item(?: in-more)?"[^>]*>([^<]*)</a>', items))


def lang_select(selected):
    return LANG_SELECT.format(vi=" selected" if selected == "vi" else "", en=" selected" if selected == "en" else "")


def is_empty(folder):
    return not folder.exists() or not any(folder.iterdir())


class VietnameseCopyTest(LiveServer, unittest.TestCase):
    """A Vietnamese fake church (``fake --lang vi``). A test that changes the language puts ``vi`` back."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        cls.root = pathlib.Path(cls.tmp.name)
        assert "onedrive" not in str(cls.root.resolve()).lower()
        cls.copy = cls.root / "fake"
        fake.build_fake_church(cls.copy, people=20, lang="vi")
        cls.start(cls.copy, cls.root, remember=False)

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.tmp.cleanup()

    def db(self):
        conn = db.connect(self.copy / db.DB_NAME)
        self.addCleanup(conn.close)
        return conn

    def lang_now(self):
        return settings.get_language(self.db())

    def keep_vi(self):
        self.addCleanup(settings.set_setting, self.db(), settings.LANGUAGE, "vi")

    def page(self, path, expect=200):
        status, _h, page = self.get_text(path)
        self.assertEqual(status, expect, path)
        return page

    def post(self, path, form, expect=303):
        status, headers, data = self.request("POST", path, form)
        self.assertEqual(status, expect, data.decode("utf-8")[:1500])
        return headers, data.decode("utf-8")

    def test_switch_html_lang_and_nav_on_a_normal_page(self):
        page = self.page("/people")
        self.assertEqual(html_lang(page), "vi")
        self.assertEqual(switch(page), ("/people", "true", "false"))
        self.assertEqual(nav_words(page), ("Menu chính", NAV_VI))
        self.assertIn('<span class="brand-church" lang="vi">', page)  # pastor data keeps lang="vi"
        # back to the same page with its query, in ASCII, without the one-time flash
        page = self.page("/people?q=" + urllib.parse.quote("Nguyễn Hải") + "&msg=Saved")
        self.assertEqual(switch(page)[0], "/people?q=Nguy%E1%BB%85n+H%E1%BA%A3i")

    def test_404_page(self):
        page = self.page("/no-such-page", expect=404)
        self.assertEqual(html_lang(page), "vi")
        self.assertEqual(switch(page), ("/no-such-page", "true", "false"))
        self.assertIn("<h1>Không tìm thấy trang</h1>", page)
        self.assertIn('<a href="/">Về Trang chủ</a>', page)
        self.assertEqual(english_left(page), [])
        self.keep_vi()
        settings.set_setting(self.db(), settings.LANGUAGE, "en")
        page = self.page("/no-such-page", expect=404)
        self.assertEqual(html_lang(page), "en")
        self.assertEqual(switch(page), ("/no-such-page", "false", "true"))
        self.assertIn("<h1>Page not found</h1>", page)
        self.assertEqual(nav_words(page), ("Main", NAV_EN))
        self.assertNotIn("[[", page)

    def test_500_page_has_the_switch_too(self):
        def boom(req):
            raise RuntimeError("hidden-trace-text")
        self.httpd.routes.insert(0, server.compile_route("GET", "/boom", boom))
        self.addCleanup(self.httpd.routes.pop, 0)
        with contextlib.redirect_stderr(io.StringIO()):
            page = self.page("/boom", expect=500)
        self.assertEqual(html_lang(page), "vi")
        self.assertEqual(switch(page), ("/boom", "true", "false"))
        self.assertIn("<h1>Có lỗi xảy ra</h1>", page)
        self.assertNotIn("hidden-trace-text", page)
        self.assertEqual(english_left(page), [])

    def test_a_bad_language_is_a_400_page(self):
        for form in ({"lang": "xx", "next": "/people"}, {"next": "/people"}, {"lang": "EN"}, {"lang": " vi"}):
            _h, page = self.post("/language", form, expect=400)
            self.assertEqual(html_lang(page), "vi")
            self.assertEqual(switch(page)[1:], ("true", "false"))
            self.assertIn("<h1>Chưa làm được</h1>", page)
            self.assertIn('<p class="lead">Ngôn ngữ phải là Tiếng Việt hoặc English.</p>', page)
            self.assertEqual(english_left(page), [], form)
        self.assertEqual(self.lang_now(), "vi")
        self.keep_vi()
        settings.set_setting(self.db(), settings.LANGUAGE, "en")
        _h, page = self.post("/language", {"lang": "xx"}, expect=400)
        self.assertIn("<h1>Not done</h1>", page)
        self.assertIn('<p class="lead">Language must be Tiếng Việt or English.</p>', page)
        self.assertNotIn("[[", page)
        self.assertEqual(self.lang_now(), "en")

    def test_next_must_be_a_page_of_this_app(self):
        for bad in ("//evil.example", "/\\x", "http://x", "", "evil", "/a\r\nSet-Cookie: x=1", "/Nguyễn",
                    "\\\\evil.example"):
            headers, _ = self.post("/language", {"lang": "vi", "next": bad})
            self.assertEqual(headers["location"], "/", repr(bad))
        headers, _ = self.post("/language", {"lang": "vi"})
        self.assertEqual(headers["location"], "/")
        for good in ("/people?q=Nguy%E1%BB%85n+H%E1%BA%A3i", "/settings", "/calendar?month=2026-11"):
            headers, _ = self.post("/language", {"lang": "vi", "next": good})
            self.assertEqual(headers["location"], good)

    def test_the_switch_saves_the_language_and_a_new_server_keeps_it(self):
        self.keep_vi()
        headers, _ = self.post("/language", {"lang": "en", "next": "/settings"})
        self.assertEqual(headers["location"], "/settings")
        self.assertEqual(self.lang_now(), "en")
        page = self.page("/settings")
        self.assertEqual(html_lang(page), "en")
        self.assertEqual(switch(page), ("/settings", "false", "true"))
        self.assertEqual(nav_words(page), ("Main", NAV_EN))
        self.assertIn(lang_select("en"), page)
        again = LiveServer()  # a restart: a new server on the same church copy
        again.httpd = server.make_server(self.copy, self.root, 0, remember=False)
        server.serve_in_thread(again.httpd)
        try:
            _s, _h, page = again.get_text("/settings")
            self.assertEqual(html_lang(page), "en")
            self.assertEqual(switch(page)[1:], ("false", "true"))
        finally:
            again.httpd.shutdown()
            again.httpd.server_close()
        self.post("/language", {"lang": "vi", "next": "/"})
        self.assertEqual(self.lang_now(), "vi")
        self.assertEqual(html_lang(self.page("/settings")), "vi")

    def test_settings_page_in_vietnamese(self):
        page = self.page("/settings")
        self.assertEqual(html_lang(page), "vi")
        self.assertEqual(switch(page), ("/settings", "true", "false"))
        self.assertIn("<h1>Cài đặt</h1>", page)
        self.assertIn('<label for="f-language">Ngôn ngữ</label>', page)
        self.assertIn(lang_select("vi"), page)
        self.assertIn('<option value="off" selected>Tắt</option><option value="on">Bật</option>', page)
        self.assertIn("Lưu cài đặt</button>", page)
        self.assertIn('<a href="/care">Thăm viếng</a>', page)
        self.assertEqual(english_left(page), [])

    def test_the_settings_select_saves_the_language(self):
        conn = self.db()
        self.keep_vi()
        form = {"church_name": settings.get_setting(conn, "church_name"), "care_reminder_months": "3"}
        headers, _ = self.post("/settings", {**form, "language": "en"})
        self.assertEqual(self.lang_now(), "en")
        page = self.page(headers["location"])
        self.assertEqual(html_lang(page), "en")
        self.assertIn(f"Settings saved: {fake.CHURCH_NAME}, care reminder time 3 months, Hermes door off.", page)
        self.assertIn(lang_select("en"), page)
        _h, page = self.post("/settings", {**form, "language": "fr"}, expect=400)
        self.assertIn('<p class="error" id="f-language-error">Language must be Tiếng Việt or English.</p>', page)
        self.assertEqual(self.lang_now(), "en")
        self.post("/settings", form)  # an old form with no language field keeps the language
        self.assertEqual(self.lang_now(), "en")
        headers, _ = self.post("/settings", {**form, "language": "vi"})
        self.assertEqual(self.lang_now(), "vi")
        page = self.page(headers["location"])
        self.assertIn(f"Đã lưu cài đặt: {fake.CHURCH_NAME}, nhắc thăm viếng 3 tháng, Cổng Hermes tắt.", page)
        _h, page = self.post("/settings", {**form, "care_reminder_months": "25", "church_name": " "}, expect=400)
        self.assertIn('id="f-care_reminder_months-error">Nhắc thăm viếng phải là số tháng nguyên từ 1 đến 24.</p>',
                      page)
        self.assertIn('id="f-church_name-error">Cần nhập Tên Hội Thánh.</p>', page)
        self.assertEqual(english_left(page), [])


class FirstRunLanguageTest(LiveServer, unittest.TestCase):
    """No church copy open: the language is kept in server memory for this run, Tiếng Việt at the start."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name) / "copies"
        self.start(None, self.root)
        self.addCleanup(self.stop)

    def setup_page(self, expect=200):
        status, _h, page = self.get_text("/setup")
        self.assertEqual(status, expect)
        return page

    def test_the_first_run_page_is_vietnamese_with_the_switch(self):
        page = self.setup_page()
        self.assertEqual(html_lang(page), "vi")
        self.assertEqual(switch(page), ("/setup", "true", "false"))
        self.assertIn("<h1>Lập dữ liệu Hội Thánh mới</h1>", page)
        self.assertIn(lang_select("vi"), page)
        self.assertIn("Lập dữ liệu Hội Thánh</button>", page)
        self.assertRegex(page, r'<input [^>]*name="church_name"[^>]*lang="vi"')
        self.assertEqual(english_left(page), [])
        status, headers, _d = self.request("GET", "/people")
        self.assertEqual((status, headers["location"]), (303, "/setup"))

    def test_the_choice_is_kept_in_memory_for_this_run_only(self):
        status, _h, data = self.request("POST", "/language", {"lang": "xx", "next": "/setup"})
        page = data.decode("utf-8")
        self.assertEqual(status, 400)
        self.assertIn("Ngôn ngữ phải là Tiếng Việt hoặc English.", page)
        self.assertEqual(english_left(page), [])
        status, headers, _d = self.request("POST", "/language", {"lang": "en", "next": "/setup"})
        self.assertEqual((status, headers["location"]), (303, "/setup"))
        self.assertEqual(self.httpd.first_run_lang, "en")
        self.assertIsNone(self.httpd.copy_folder)
        self.assertTrue(is_empty(self.root))  # nothing written
        page = self.setup_page()
        self.assertEqual(html_lang(page), "en")
        self.assertEqual(switch(page), ("/setup", "false", "true"))
        self.assertIn("<h1>New church setup</h1>", page)
        self.assertIn(lang_select("en"), page)  # the language on screen is picked for the new copy
        self.assertNotIn("[[", page)
        again = LiveServer()  # the next run starts in Tiếng Việt again
        again.httpd = server.make_server(None, self.root, 0)
        server.serve_in_thread(again.httpd)
        try:
            _s, _h, page = again.get_text("/setup")
            self.assertEqual(html_lang(page), "vi")
        finally:
            again.httpd.shutdown()
            again.httpd.server_close()

    def funds_and_language(self, folder):
        conn = db.open_church_copy(folder)
        try:
            return [r["name"] for r in lists.get_list(conn, "fund")], settings.get_language(conn)
        finally:
            conn.close()

    def test_new_church_setup_with_no_language_field_is_vietnamese(self):
        status, headers, _d = self.request("POST", "/setup", {"church_name": "Hội Thánh Thử Nghiệm"})
        self.assertEqual(status, 303)
        msg = urllib.parse.parse_qs(urllib.parse.urlsplit(headers["location"]).query)["msg"][0]
        self.assertEqual(msg, "Đã lập dữ liệu Hội Thánh mới. Đây là Trang chủ.")
        folder = self.root / "hoi-thanh-thu-nghiem"
        funds = [vi for _c, vi, _en in schema.DEFAULT_LISTS["fund"]]
        self.assertEqual(self.funds_and_language(folder), (funds, "vi"))
        _s, _h, page = self.get_text("/settings")
        self.assertEqual(html_lang(page), "vi")
        self.assertEqual(nav_words(page), ("Menu chính", NAV_VI))

    def test_new_church_setup_in_english(self):
        status, headers, _d = self.request("POST", "/setup", {"church_name": "Hội Thánh B", "language": "en"})
        self.assertEqual(status, 303)
        funds = [en for _c, _vi, en in schema.DEFAULT_LISTS["fund"]]
        self.assertEqual(self.funds_and_language(self.root / "hoi-thanh-b"), (funds, "en"))
        _s, _h, page = self.get_text(headers["location"])
        self.assertEqual(html_lang(page), "en")
        self.assertIn("New church setup is done. This is your Dashboard.", page)

    def test_refusals_make_nothing(self):
        status, _h, data = self.request("POST", "/setup", {"church_name": "Hội Thánh C", "language": "fr"})
        page = data.decode("utf-8")
        self.assertEqual(status, 400)
        self.assertIn('<p class="error" id="f-language-error">Ngôn ngữ phải là Tiếng Việt hoặc English.</p>', page)
        self.assertEqual(english_left(page), [])
        status, _h, data = self.request("POST", "/setup", {"church_name": "  ", "language": "vi"})
        page = data.decode("utf-8")
        self.assertEqual(status, 400)
        self.assertIn('<p class="error" id="f-church_name-error">Cần nhập Tên Hội Thánh.</p>', page)
        self.assertEqual(english_left(page), [])
        self.assertIsNone(self.httpd.copy_folder)
        self.assertTrue(is_empty(self.root))


class SmallLanguageTest(unittest.TestCase):
    def use_lang(self, lang):
        self.addCleanup(i18n.set_lang_getter, i18n._lang_getter)
        i18n.set_lang_getter(lambda: lang)

    def test_ui_registers_the_language_getter(self):
        self.assertIs(i18n._lang_getter, ui.current_lang)
        self.assertEqual(ui.current_lang(), "vi")  # outside a request: DEFAULT_LANG

    def test_safe_next(self):
        for bad in (None, "", "people", "//evil.example", "/\\x", "\\\\x", "http://x", "/a\nb", "/Nguyễn", "/a\x00"):
            self.assertEqual(settings_pages.safe_next(bad), "/", repr(bad))
        for good in ("/", "/people?q=a+b", "/calendar?month=2026-11#x"):
            self.assertEqual(settings_pages.safe_next(good), good)

    def test_days_months_roles_and_kinds(self):
        self.use_lang("vi")
        self.assertEqual((ui.fmt_weekday("2026-11-01"), ui.fmt_weekday("2026-11-02")), ("Chúa Nhật", "Thứ Hai"))
        self.assertEqual(ui.fmt_month(2026, 11), "Tháng 11/2026")
        self.assertEqual(ui.fmt_date("2026-11-01"), "01/11/2026")  # dates are dd/mm/yyyy in both
        self.assertEqual(ui.fmt_money(1_250_000), "1.250.000 ₫")
        words = {code: ui.family_role(code) for code in schema.FAMILY_ROLES}
        self.assertEqual(words, {"Head": "Chủ gia đình", "Spouse": "Vợ/Chồng", "Child": "Con",
                                 "Other": "Người thân khác"})
        self.assertEqual([ui.ministry_role(c) for c in schema.MINISTRY_ROLES], ["Trưởng ban", "Ban viên"])
        self.assertEqual([ui.calendar_kind(c) for c in schema.CALENDAR_KINDS],
                         ["Giờ thờ phượng", "Buổi họp", "Thăm viếng", "Chương trình"])
        self.assertEqual(ui.calendar_kind("Picnic"), "Picnic")  # an unknown code is shown as it is
        self.use_lang("en")
        self.assertEqual((ui.fmt_weekday("2026-11-01"), ui.fmt_month(2026, 11)), ("Sun", "November 2026"))
        self.assertEqual([ui.family_role(c) for c in schema.FAMILY_ROLES], list(schema.FAMILY_ROLES))
        self.assertEqual([ui.ministry_role(c) for c in schema.MINISTRY_ROLES], list(schema.MINISTRY_ROLES))
        self.assertEqual([ui.calendar_kind(c) for c in schema.CALENDAR_KINDS], list(schema.CALENDAR_KINDS))
        self.assertEqual(ui.plural(2, "Person", "People"), "2 People")  # old callers still work

    def test_t_html_escapes_the_words_not_the_html(self):
        for lang in i18n.LANGS:
            TEXT[lang]["core.zz_probe"] = "A & <b> {link} {link}"
            self.addCleanup(TEXT[lang].pop, "core.zz_probe")
        self.use_lang("en")
        self.assertEqual(ui.t_html("core.zz_probe", link='<a href="/x">x</a>'),
                         'A &amp; &lt;b&gt; <a href="/x">x</a> <a href="/x">x</a>')
        self.assertEqual(ui.t_html("no.such_key"), "[[no.such_key]]")

    def test_the_switch_on_a_bare_page_outside_a_request(self):
        page = ui.bare_page("X", "")
        self.assertEqual(html_lang(page), "vi")
        self.assertEqual(switch(page), ("/", "true", "false"))


if __name__ == "__main__":
    unittest.main()
