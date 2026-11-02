"""I18N-FIX-T r1: three fixes the tester asked for.

L3: the language switch on a page shown for a POST (a refused form) never leads to a 405. Its ``next`` is the
POST path when that path has a GET page, else the page the form was on (the ``Referer``) when that path has a
GET page, else ``/``. GET pages keep their own path and query (without ``msg``).
L2: the flash after opening a church copy or after a New church setup is in the language of the next page,
that is the language of the church copy now open.
L1: the English history error shows its dates dd/mm/yyyy, like the Tiếng Việt one.

Real servers on 127.0.0.1 (port 0) over church copies in temp folders.
"""

import datetime as dt
import pathlib
import re
import sqlite3
import tempfile
import types
import unittest
from unittest import mock

import _support
from churchmgr import db, fake, handover, lists, pages, people, server, ui
from churchmgr.i18n import TEXT, TextError, error_text
from churchmgr.pages import copies as copy_pages
from test_i18n_copies import flash
from test_i18n_core import html_lang, switch
from test_server import LiveServer

TODAY = dt.date.today()
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
NEXT = re.compile(r'<input type="hidden" name="next" value="([^"]*)">')


def shown(day):
    return day.strftime("%d/%m/%Y")


def temp_root():
    tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
    root = pathlib.Path(tmp.name)
    assert "onedrive" not in str(root.resolve()).lower(), "temp folder must be outside OneDrive"
    return tmp, root


class SwitchAfterPostTest(LiveServer, unittest.TestCase):
    """L3 (and L1 on screen). One Tiếng Việt fake church; a new Person in Ban Âm nhạc since 10 days ago."""

    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.root = temp_root()
        cls.copy = cls.root / "fake"
        fake.build_fake_church(cls.copy, people=20, lang="vi")
        conn = db.connect(cls.copy / db.DB_NAME)
        try:
            cls.pid = people.add_person(conn, "Nguyễn Văn Sửa")
            cls.worship = lists.find_item(conn, "ministry", name="Ban Âm nhạc")["id"]
            cls.since = TODAY - dt.timedelta(days=10)
            people.set_ministry(conn, cls.pid, cls.worship, "Member", cls.since.isoformat())
        finally:
            conn.close()
        cls.start(cls.copy, cls.root, remember=False)

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.tmp.cleanup()

    def setUp(self):
        self.press_switch("vi", "/")  # every test starts on Tiếng Việt screens

    def url(self, path):
        return f"http://127.0.0.1:{self.httpd.port}{path}"

    def press_switch(self, lang, next_):
        """POST /language like the switch does, then follow the redirect: ``(location, status, page)``."""
        status, headers, _d = self.request("POST", "/language", {"lang": lang, "next": next_})
        self.assertEqual(status, 303)
        status, _h, page = self.get_text(headers["location"])
        return headers["location"], status, page

    def post_page(self, path, form, referer=None, expect=400):
        """A POST with ``Origin`` (and ``Referer`` when given); the page it shows."""
        headers = {"Referer": referer} if referer is not None else None
        status, _h, data = self.request("POST", path, form, headers=headers)
        page = data.decode("utf-8")
        self.assertEqual(status, expect, page[-2000:])
        return page

    def refused_ministry(self, referer=None):
        """A Ministry change dated before the last change: the Person page again, 400."""
        self.early = TODAY - dt.timedelta(days=20)
        form = {"ministry_id": self.worship, "ministry_role": "Leader", "start_date": self.early.isoformat()}
        return self.post_page(f"/people/{self.pid}/ministry", form, referer)

    def test_refused_ministry_comes_back_to_the_person_page(self):
        page = self.refused_ministry(self.url(f"/people/{self.pid}"))
        self.assertEqual(html_lang(page), "vi")
        next_, vi_pressed, _en = switch(page)
        self.assertEqual((next_, vi_pressed), (f"/people/{self.pid}", "true"))
        location, status, page = self.press_switch("en", next_)
        self.assertEqual((location, status, html_lang(page)), (f"/people/{self.pid}", 200, "en"))
        self.assertEqual(switch(page)[1:], ("false", "true"))

    def test_the_referer_query_is_kept_and_msg_left_out(self):
        page = self.refused_ministry(self.url(f"/people/{self.pid}?tab=2&msg=%C4%90%C3%A3+l%C6%B0u"))
        self.assertEqual(switch(page)[0], f"/people/{self.pid}?tab=2")

    def test_no_referer_comes_back_to_the_dashboard(self):
        page = self.refused_ministry()  # Origin only
        self.assertEqual(switch(page)[0], "/")
        location, status, page = self.press_switch("en", "/")
        self.assertEqual((location, status, html_lang(page)), ("/", 200, "en"))

    def test_a_referer_with_no_get_page_comes_back_to_the_dashboard(self):
        """The form sent again from the refused page: its address is the POST path."""
        page = self.refused_ministry(self.url(f"/people/{self.pid}/ministry"))
        self.assertEqual(switch(page)[0], "/")
        page = self.refused_ministry(self.url("/language"))  # a POST-only path too
        self.assertEqual(switch(page)[0], "/")

    def test_refused_handover_comes_back_to_copies(self):
        refused = handover.HandoverError("copies.err_door")
        with mock.patch.object(handover, "make_handover", side_effect=refused):
            page = self.post_page("/copies/handover", {}, self.url("/copies"))
        self.assertEqual(html_lang(page), "vi")
        self.assertIn(TEXT["vi"]["copies.err_door"], page)
        self.assertEqual(switch(page)[0], "/copies")
        location, status, page = self.press_switch("en", "/copies")
        self.assertEqual((location, status, html_lang(page)), ("/copies", 200, "en"))

    def test_a_post_path_with_a_get_page_keeps_its_own_path(self):
        page = self.post_page("/people/new", {"full_name": " "}, self.url("/people"))
        self.assertEqual(switch(page)[0], "/people/new")
        location, status, page = self.press_switch("en", "/people/new")
        self.assertEqual((location, status, html_lang(page)), ("/people/new", 200, "en"))

    def test_get_pages_keep_their_path_and_query(self):
        """Same as before the fix, even with a Referer."""
        cases = ((f"/people/{self.pid}?msg=x&b=2", 200, f"/people/{self.pid}?b=2"),
                 ("/people?q=Nguy%E1%BB%85n", 200, "/people?q=Nguy%E1%BB%85n"),
                 ("/no-such-page", 404, "/no-such-page"))
        for path, expect, want in cases:
            status, _h, page = self.get_text(path, headers={"Referer": self.url("/copies")})
            self.assertEqual(status, expect, path)
            self.assertEqual(switch(page)[0], want, path)

    def test_english_history_error_on_screen(self):
        """L1 on the page: dd/mm/yyyy, no ISO date."""
        self.press_switch("en", "/")
        page = self.refused_ministry(self.url(f"/people/{self.pid}"))
        self.assertEqual(html_lang(page), "en")
        m = re.search(r'<p class="error" id="ministry-date-error">([^<]*)</p>', page)
        assert m is not None, page[-3000:]
        self.assertEqual(m.group(1), f"Start date {shown(self.early)} is before {shown(self.since)}, the date of the "
                                     "last change. History is never rewritten; use a date on or after it.")
        self.assertNotRegex(m.group(1), ISO_DATE)


class SwitchWithoutServerTest(unittest.TestCase):
    """L3 without a server: the next field of ``ui.lang_switch`` for a hand-made request."""

    def next_of(self, method, path, query=None, headers=None, routes=True):
        state = types.SimpleNamespace(copy_folder=None, first_run_lang="vi")
        if routes:
            state.routes = server.build_routes(pages.PAGES)
        ui.set_request(server.Request(state, method, path, query or {}, headers=headers))
        self.addCleanup(ui.set_request, None)
        return NEXT.search(ui.lang_switch()).group(1)

    def test_no_routes_keeps_the_path(self):
        """A request whose state has no routes (unit fakes): the path and query as before."""
        self.assertEqual(self.next_of("POST", "/people/5/ministry", {"msg": ["x"], "a": ["1"]}, routes=False),
                         "/people/5/ministry?a=1")

    def test_post_paths(self):
        referer = {"Referer": "http://127.0.0.1:8765/people/5?msg=x"}
        self.assertEqual(self.next_of("POST", "/people/5/ministry"), "/")  # no headers at all
        self.assertEqual(self.next_of("POST", "/people/5/ministry", headers={}), "/")
        self.assertEqual(self.next_of("POST", "/people/5/ministry", headers=referer), "/people/5")
        self.assertEqual(self.next_of("POST", "/people/new", headers=referer), "/people/new")
        self.assertEqual(self.next_of("POST", "/settings", {"msg": ["x"]}, headers=referer), "/settings")
        self.assertEqual(self.next_of("POST", "/copies/open", headers={"Referer": "not a web address"}), "/")
        self.assertEqual(self.next_of("GET", "/copies/open", headers=referer), "/copies/open")  # GET: as before


class FlashAfterOpenTest(LiveServer, unittest.TestCase):
    """L2. A copies root with a Tiếng Việt church copy ``a`` (open at start) and an English church copy ``b``."""

    def setUp(self):
        tmp, self.root = temp_root()
        self.addCleanup(tmp.cleanup)
        db.create_church_copy(self.root / "a", "Hội Thánh An Bình T1", "vi").close()
        db.create_church_copy(self.root / "b", "Grace Test Church T1", "en").close()
        self.start(self.root / "a", self.root, remember=False)
        self.addCleanup(self.stop)

    def next_page(self, path, form):
        status, headers, data = self.request("POST", path, form)
        self.assertEqual(status, 303, data.decode("utf-8")[-2000:])
        status, _h, page = self.get_text(headers["location"])
        self.assertEqual(status, 200)
        return page

    def test_open_an_english_copy_from_a_vietnamese_page(self):
        self.assertEqual(html_lang(self.get_text("/copies")[2]), "vi")
        page = self.next_page("/copies/open", {"folder": "b"})
        self.assertEqual((html_lang(page), flash(page)), ("en", "Opened Grace Test Church T1."))
        page = self.next_page("/copies/open", {"folder": "b"})  # the same copy: in the words of this copy
        self.assertEqual(flash(page), "This church copy is already open.")

    def test_open_a_vietnamese_copy_from_an_english_page(self):
        self.next_page("/copies/open", {"folder": "b"})
        self.assertEqual(html_lang(self.get_text("/copies")[2]), "en")
        page = self.next_page("/copies/open", {"folder": "a"})
        self.assertEqual((html_lang(page), flash(page)), ("vi", "Đã mở Hội Thánh An Bình T1."))
        page = self.next_page("/copies/open", {"folder": "a"})
        self.assertEqual(flash(page), "Dữ liệu Hội Thánh này đang mở.")

    def test_new_church_setup_in_english_from_a_vietnamese_page(self):
        page = self.next_page("/copies/new", {"church_name": "Hope Church T1", "language": "en"})
        self.assertEqual(html_lang(page), "en")
        self.assertTrue(flash(page).startswith("New church setup is done: Hope Church T1. This is its Dashboard."),
                        flash(page))

    def test_new_church_setup_in_vietnamese_from_an_english_page(self):
        self.next_page("/copies/open", {"folder": "b"})
        page = self.next_page("/copies/new", {"church_name": "Hội Thánh Mới T1", "language": "vi"})
        self.assertEqual(html_lang(page), "vi")
        self.assertTrue(flash(page).startswith("Đã lập dữ liệu Hội Thánh mới: Hội Thánh Mới T1."), flash(page))

    def test_open_closes_the_connection_it_opens(self):
        """The handler alone (no request thread): every connection made while it runs is closed after."""
        made, real = [], db.connect

        def spy(path):
            conn = real(path)
            made.append(conn)
            return conn

        req = server.Request(self.httpd, "POST", "/copies/open", {}, {"folder": ["b"]})
        with mock.patch.object(db, "connect", spy):
            resp = copy_pages.open_post(req)
        req.close()
        self.assertEqual(resp.status, 303)
        self.assertIn("msg=Opened+Grace+Test+Church+T1.", resp.headers["Location"])
        self.assertGreaterEqual(len(made), 2)  # the check of switch_copy, and the language of copy b
        for conn in made:
            with self.assertRaises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1")


class EnglishHistoryDatesTest(_support.CopyTestCase):
    """L1. The history error: ``str()`` and the English text dd/mm/yyyy; the Tiếng Việt text as before."""

    def test_dates_dd_mm_yyyy_in_both_languages(self):
        pid = people.add_person(self.conn, "Lê Văn Cường")
        people.set_status(self.conn, pid, self.status("member"), "2026-01-10")
        with self.assertRaises(TextError) as ctx:
            people.set_status(self.conn, pid, self.status("attender"), "2026-01-01")
        e = ctx.exception
        want = ("Start date 01/01/2026 is before 10/01/2026, the date of the last change. History is never "
                "rewritten; use a date on or after it.")
        self.assertEqual(str(e), want)
        self.assertEqual(error_text(e, "en"), want)
        self.assertNotRegex(str(e), ISO_DATE)
        self.assertEqual(error_text(e, "vi"), "Ngày bắt đầu 01/01/2026 sớm hơn 10/01/2026, ngày của lần thay đổi gần "
                                              "nhất. Những gì đã qua không bao giờ bị viết lại; hãy dùng ngày "
                                              "10/01/2026 hoặc sau đó.")

    def test_same_params_in_both_languages(self):
        """Only the format of the dates changed: both texts still take {start} and {latest}."""
        names = {lang: set(re.findall(r"\{(\w+)", TEXT[lang]["people.err_history"])) for lang in ("vi", "en")}
        self.assertEqual(names, {"vi": {"start", "latest"}, "en": {"start", "latest"}})


if __name__ == "__main__":
    unittest.main()
