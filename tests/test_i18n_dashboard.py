"""I18N-U5: the Dashboard, Search, Documents, Sent documents and Lists screens in Tiếng Việt and English,
through real servers on 127.0.0.1 (port 0) over fake churches in temp folders
(``fake.build_fake_church(..., lang=...)``). The old tests stay English; these read Tiếng Việt, and check
that an English copy shows no ``[[key]]``. The live search of the Dashboard takes its sentences from
``data-text-*`` attributes made by the server: ``web/app.js`` holds none.
"""

import datetime as dt
import html
import pathlib
import re
import tempfile
import unittest
import urllib.parse

import _support  # noqa: F401 - puts the repo root on sys.path
from churchmgr import db, documents, fake, lists, people, search, sent, text
from churchmgr.i18n import TEXT, TextError, english_left, error_text, t
from churchmgr.pages import documents as doc_pages
from churchmgr.pages import lists as list_pages
from churchmgr.pages import sent as sent_pages
from test_i18n_core import html_lang, switch
from test_pages_documents import multipart
from test_server import LiveServer

ROOT = pathlib.Path(_support.ROOT)
TODAY = dt.date.today()
DOCUMENTS = re.compile(r'<div id="documents">.*?</section></div>', re.S)
HIDDEN = "Cảm tạ U5"  # a Purpose added and hidden: refused for a new Sent document
NEW_ITEM = "Mời họp U5"


def days(n):
    return (TODAY + dt.timedelta(days=n)).isoformat()


def flash(page):
    m = re.search(r'<p class="flash" role="status">([^<]*)</p>', page)
    return html.unescape(m.group(1)) if m else None


def field_error(page, field_id):
    m = re.search(rf'<p class="error" id="{re.escape(field_id)}">([^<]*)</p>', page)
    return html.unescape(m.group(1)) if m else None


class _Screens(LiveServer, unittest.TestCase):
    """One fake church in ``LANG`` and one live server per test class. Deleted at the end of this file:
    only its two subclasses (Tiếng Việt, English) run."""

    LANG = "vi"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        root = pathlib.Path(cls.tmp.name)
        assert "onedrive" not in str(root.resolve()).lower()
        cls.copy = root / "fake"
        fake.build_fake_church(cls.copy, people=20, lang=cls.LANG)
        conn = db.connect(cls.copy / db.DB_NAME)
        try:
            one = lambda sql, *args: conn.execute(sql, args).fetchone()[0]  # noqa: E731
            cls.ids = {
                "person": one("SELECT person_id FROM document WHERE person_id IS NOT NULL"),
                "family": one("SELECT id FROM family ORDER BY id LIMIT 1"),
                "item": one("SELECT calendar_item_id FROM document WHERE calendar_item_id IS NOT NULL"),
                "doc": one("SELECT id FROM document WHERE person_id IS NOT NULL"),
                "sent_doc": one("SELECT document_id FROM sent_document WHERE document_id IS NOT NULL"),
                "recipient": lists.get_list(conn, "recipient")[0]["id"],
                "purpose": lists.get_list(conn, "purpose")[0]["id"],
                "hidden": lists.add_item(conn, "purpose", HIDDEN),
            }
            lists.set_active(conn, cls.ids["hidden"], False)
            cls.purpose_name = lists.get_list(conn, "purpose")[0]["name"]
            cls.surname = people.get_person(conn, cls.ids["person"])["full_name"].split()[0]
        finally:
            conn.close()
        cls.start(cls.copy, root, remember=False)

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.tmp.cleanup()

    def db(self):
        conn = db.connect(self.copy / db.DB_NAME)
        self.addCleanup(conn.close)
        return conn

    def page(self, path, expect=200):
        status, _h, page = self.get_text(path)
        self.assertEqual(status, expect, path)
        return page

    def post(self, path, form, expect=303):
        status, headers, data = self.request("POST", path, form)
        self.assertEqual(status, expect, data.decode("utf-8")[:1500])
        return headers, data.decode("utf-8")

    def post_multipart(self, path, fields, files=None, expect=303):
        body, ctype = multipart(fields, files)
        status, headers, data = self.request("POST", path, body, headers={"Content-Type": ctype})
        self.assertEqual(status, expect, data.decode("utf-8", "replace")[:1500])
        return headers, data.decode("utf-8")

    def our_pages(self):
        """Every GET page of these screens: the Dashboard; Search empty, with results (a name typed
        without accents) and with none; the Documents list, the Add document form for a Person, a Family
        and a Calendar item, the Delete question of a plain Document and of the file of a Sent document;
        the Sent documents of this year, of last year and of an empty year (each Sent document is a row
        of its year page: there is no page of one Sent document), the Record form; the Lists page with
        its Add, Rename and Hide/Show forms (a hidden item too)."""
        i = self.ids
        q = urllib.parse.quote(text.fold(self.surname))  # typed without accents
        return ["/", "/search", f"/search?q={q}", "/search?q=zzzzqq", "/documents",
                f"/documents/new?person_id={i['person']}", f"/documents/new?family_id={i['family']}",
                f"/documents/new?calendar_item_id={i['item']}", f"/documents/{i['doc']}/delete",
                f"/documents/{i['sent_doc']}/delete", "/sent", f"/sent?year={TODAY.year - 1}",
                f"/sent?year={TODAY.year + 3}", "/sent/new", "/lists"]

    def documents_panels(self):
        """The Documents block (pages/documents.py) on a Person, a Family and a Calendar item page."""
        i = self.ids
        for path in (f"/people/{i['person']}", f"/families/{i['family']}", f"/calendar/{i['item']}"):
            m = DOCUMENTS.search(self.page(path))
            self.assertIsNotNone(m, path)
            yield path, m.group(0)

    def check_lang(self, page, path):
        self.assertEqual(html_lang(page), self.LANG, path)
        self.assertEqual(switch(page)[1:], ("true", "false") if self.LANG == "vi" else ("false", "true"), path)
        self.assertNotIn("[[", page, path)

    def test_search_nav_item_is_current_on_the_search_page(self):
        page = self.page("/search?q=a")
        nav = re.search(r'<nav class="nav"[^>]*>(.*?)</nav>', page, re.S).group(1)
        # once in the menu, once in the phone's More fold (CRIT-2): style.css shows one of them
        self.assertEqual(re.findall(r'href="([^"]+)" aria-current="page"', nav), ["/search", "/search"])
        self.assertIn(f'aria-current="page">{t("core.nav_search", self.LANG)}</a>', nav)

    def test_live_search_words_are_in_data_attributes(self):
        form = re.search(r'<form class="search-form"[^>]*data-live-search[^>]*>', self.page("/")).group(0)
        for name, key in (("none", "search.live_none"), ("failed", "search.live_failed")):
            self.assertIn(f'data-text-{name}="{html.escape(t(key, self.LANG))}"', form)
        js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        for words in ("No Person found", "Could not search", "Press Search", TEXT["vi"]["search.live_none"]):
            self.assertNotIn(words, js)
        self.assertIn('form.getAttribute("data-text-" + name)', js)
        code = re.sub(r"^\s*//.*$", "", js, flags=re.M)  # the comments may speak English
        sentences = [s for s in re.findall(r'"([^"\\]*)"', code) if " " in s.strip() and s != "use strict"]
        self.assertEqual(sentences, [])  # no sentence in the script: the page gives them
        status, _h, data = self.request("GET", f"/api/search?q={urllib.parse.quote(self.surname)}")
        self.assertEqual(status, 200)
        self.assertIn(b'"full_name"', data)


class VietnameseScreensTest(_Screens):
    LANG = "vi"

    def assert_vietnamese(self, page, path=""):
        self.check_lang(page, path)
        self.assertEqual(english_left(page), [], path)

    def test_every_page_is_vietnamese(self):
        for path in self.our_pages():
            self.assert_vietnamese(self.page(path), path)
        for path, box in self.documents_panels():
            self.assertEqual(english_left(box), [], path)
            self.assertNotIn("[[", box, path)
            self.assertIn('<h2 id="p-documents">Tài liệu</h2>', box, path)
            self.assertIn('>Thêm Tài liệu</button>', box, path)

    def test_dashboard_words(self):
        page = self.page("/")
        for words in ("<h1>Trang chủ</h1>", '<h2 id="p-this-week">7 ngày tới</h2>',
                      '<h2 id="p-needs-visit">Cần thăm viếng</h2>', '<h2 id="p-services">Giờ thờ phượng</h2>',
                      '<h2 id="p-money-month">Tài chính tháng này</h2>', '<h2 id="p-sent-documents">Văn bản đi</h2>',
                      '<span class="kpi-label">Dâng hiến</span>', '<span class="kpi-label">Số dư</span>',
                      '<span class="kpi-label">Số tiếp theo</span>', '<label for="dash-q">Tìm Người</label>',
                      'placeholder="Có dấu hoặc không dấu"', ">Lên lịch Thăm viếng</a>",
                      'aria-label="Số người nhóm của ', "<span>Thăm gần nhất</span>"):
            self.assertIn(words, page)
        weekday = t(f"core.weekday_{TODAY.weekday()}", "vi")
        self.assertRegex(page, rf'<p class="sub">{weekday} {TODAY:%d/%m/%Y} · '  # CRIT-3: Needs a visit has its
                               r'\d+ Lịch trong 7 ngày tới</p>')  # count on its card, not again here
        count = len(sent.list_sent_documents(self.db(), TODAY.year))
        # CRIT-4: more than the rows shown -> the foot link names them all
        self.assertIn(f">Xem tất cả {count}</a>" if count > 2 else ">Mở Văn bản đi</a>", page)
        self.assertIn(f'<span class="meta">{count} Công văn đi trong năm {TODAY.year}</span>', page)
        self.assertRegex(page, r'<strong class="trend-(up|down|same)">(Tăng|Giảm|Không đổi)</strong> · '
                               r'Số người nhóm \d+ ngày \d\d/\d\d/\d{4}, so với trung bình \d+ của \d+ '
                               r'Giờ thờ phượng trước đó\.</p>')

    def test_search_documents_sent_and_lists_words(self):
        i = self.ids
        found = self.page(self.our_pages()[2])
        self.assertIn('<label for="q">Tìm Người</label>', found)
        self.assertRegex(found, r'<p class="sub">Tìm thấy \d+ người</p>')
        self.assertIn("Không tìm thấy Người nào cho “zzzzqq”.", self.page("/search?q=zzzzqq"))
        listing = self.page("/documents")
        self.assertIn('<th scope="col">Liên kết với</th>', listing)
        self.assertRegex(listing, r'<p class="sub">\d+ Tài liệu · \d+ (byte|KB) trong Dữ liệu Hội Thánh này · '
                                  r'mới nhất trước</p>')
        self.assertIn('<span class="faint">Công văn đi</span>', listing)
        number = self.db().execute("SELECT printf('%02d/%d', seq, year) FROM sent_document "
                                   "WHERE document_id = ?", (i["sent_doc"],)).fetchone()[0]
        question = self.page(f"/documents/{i['sent_doc']}/delete")
        for words in ("<h1>Xóa Tài liệu này?</h1>", ">Có, xóa Tài liệu này</button>", ">Hủy</a>",
                      f"Công văn đi {number} vẫn được giữ, cùng số, ngày, Nơi nhận và Mục đích, nhưng không còn tệp."):
            self.assertIn(words, question)
        new_form = self.page(f"/documents/new?family_id={i['family']}")
        self.assertIn('<p class="sub">Cho Gia đình <span lang="vi">', new_form)
        year_page = self.page("/sent")
        for words in ("<h1>Văn bản đi</h1>", '>Năm nay</a>', '>Thêm Công văn đi</a>', '<th scope="col">Trích yếu</th>',
                      f"Năm {TODAY.year} theo Nơi nhận", '<span class="cell-sub">Tệp: <a href="/documents/'):
            self.assertIn(words, year_page)
        self.assertIn(f"Chưa có Công văn đi nào trong năm {TODAY.year + 3}.", self.page(f"/sent?year={TODAY.year + 3}"))
        form = self.page("/sent/new")
        self.assertRegex(form, r'<option value=""( selected)?>— Chọn —</option>')
        self.assertIn(">Lưu Công văn đi</button>", form)
        self.assertNotIn(HIDDEN, form)  # a hidden Purpose is not offered
        page = self.page("/lists")
        for title in ("Nơi nhận", "Mục đích", "Quỹ", "Hạng mục chi", "Ban ngành", "Trạng thái"):
            self.assertRegex(page, rf'<h2 id="p-list-[a-z-]+">{title}</h2>')
        self.assertIn(f'<span class="what" lang="vi">{HIDDEN} <span class="tag">Đang ẩn</span></span>', page)
        self.assertIn(f'aria-label="Hiện {HIDDEN}">Hiện</button>', page)
        self.assertIn("đang hiện, 1 đang ẩn", page)
        self.assertIn('<label for="add-list-purpose">Mục đích mới</label>', page)
        self.assertIn(f'<span class="what" lang="vi">{html.escape(self.purpose_name)}</span>', page)  # as stored

    def test_form_errors_are_vietnamese_and_next_to_their_field(self):
        i = self.ids
        base = {"date": days(0), "recipient_id": i["recipient"], "purpose_id": i["purpose"], "subject": NEW_ITEM}
        before = self.db().execute("SELECT COUNT(*) FROM sent_document").fetchone()[0]
        cases = (
            ("/sent/new", {**base, "date": ""}, "Ngày phải là một ngày có thật, viết YYYY-MM-DD, ví dụ 2026-05-31.",
             "f-date-error"),
            ("/sent/new", {**base, "date": days(1)},
             f"Ngày không được sau hôm nay ({TODAY:%d/%m/%Y}). Hãy dùng hôm nay hoặc một ngày trước đó.",
             "f-date-error"),
            ("/sent/new", {**base, "recipient_id": ""}, "Nơi nhận: hãy chọn một mục trong danh sách.",
             "f-recipient_id-error"),
            ("/sent/new", {**base, "purpose_id": i["hidden"]},
             f"Mục đích: {HIDDEN} đang ẩn trong Danh mục. Hãy chọn mục khác, hoặc hiện lại mục đó trong Danh mục.",
             "f-purpose_id-error"),
            ("/sent/new", {**base, "subject": " "}, "Cần nhập Trích yếu.", "f-subject-error"),
            ("/lists/purpose/add", {"name": " "}, "Cần nhập Tên.", "add-list-purpose-error"),
            ("/lists/purpose/add", {"name": self.purpose_name}, f"{self.purpose_name} đã có trong danh mục Mục đích.",
             "add-list-purpose-error"),
            (f"/lists/items/{i['purpose']}/rename", {"name": ""}, "Cần nhập Tên.", f"rename-{i['purpose']}-error"),
            ("/documents/new", {"person_id": i["person"]}, "Hãy chọn một tệp trước.", f"doc-file-{i['person']}-error"),
        )
        for path, form, sentence, field_id in cases:
            _h, page = self.post(path, form, expect=400)
            self.assert_vietnamese(page, path)
            self.assertEqual(field_error(page, field_id), sentence, (path, form))
        _h, page = self.post_multipart("/sent/new", base, {"file": ("trống.txt", b"")}, expect=400)
        self.assertEqual(field_error(page, "f-file-error"),
                         "Tệp: tệp này trống (0 byte). Hãy chọn tệp khác, hoặc không chọn tệp nào.")
        limit = documents.MAX_SIZE
        documents.MAX_SIZE = 1024 * 1024  # a file over 1 MB, not over 50 MB
        self.addCleanup(setattr, documents, "MAX_SIZE", limit)
        big = {"file": ("lớn.bin", b"x" * (1024 * 1024 + 1))}
        _h, page = self.post_multipart("/sent/new", base, big, expect=400)
        self.assert_vietnamese(page)
        self.assertEqual(field_error(page, "f-file-error"), "Tệp: Tệp quá lớn. Giới hạn là 1 MB.")
        _h, page = self.post_multipart("/documents/new", {"person_id": i["person"]}, big, expect=400)
        self.assert_vietnamese(page)
        self.assertEqual(field_error(page, f"doc-file-{i['person']}-error"), "Tệp quá lớn. Giới hạn là 1 MB.")
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM sent_document").fetchone()[0], before)

    def show_again(self, ids):
        conn = db.connect(self.copy / db.DB_NAME)
        try:
            for iid in ids:
                lists.set_active(conn, iid, True)
        finally:
            conn.close()

    def test_hide_show_and_the_last_shown_item(self):
        items = lists.get_list(self.db(), "spending_category")
        self.assertGreater(len(items), 1)
        self.addCleanup(self.show_again, [r["id"] for r in items])
        for item in items[1:]:
            headers, _ = self.post(f"/lists/items/{item['id']}/hide", {})
            self.assertEqual(flash(self.page(headers["location"])),
                             f"Đã ẩn {item['name']}. Mục này không được đưa ra để chọn khi nhập mới; những gì đã "
                             "dùng mục này vẫn giữ tên.")
        _h, page = self.post(f"/lists/items/{items[0]['id']}/hide", {}, expect=400)
        self.assert_vietnamese(page)
        self.assertIn('role="alert">Hãy để ít nhất một Hạng mục chi đang hiện: khi nhập mới cần có một mục '
                      'để chọn.</p>', page)
        for item in items[1:]:
            headers, _ = self.post(f"/lists/items/{item['id']}/show", {})
            page = self.page(headers["location"])
            self.assert_vietnamese(page)
            self.assertEqual(flash(page), f"Đã hiện lại {item['name']}.")

    def test_flash_messages_are_vietnamese(self):
        i = self.ids
        number = sent.next_number(self.db(), TODAY.year)
        headers, _ = self.post("/sent/new", {"date": days(0), "recipient_id": i["recipient"],
                                             "purpose_id": i["purpose"], "subject": NEW_ITEM})
        page = self.page(headers["location"])
        self.assert_vietnamese(page)
        self.assertEqual(flash(page), f"Đã lưu với số {number}. Hãy ghi số này lên Công văn đi.")
        headers, _ = self.post("/lists/fund/add", {"name": NEW_ITEM})
        page = self.page(headers["location"])
        self.assert_vietnamese(page)
        self.assertEqual(flash(page), f"Đã thêm {NEW_ITEM} vào Quỹ.")
        item = lists.find_item(self.db(), "fund", name=NEW_ITEM)["id"]
        headers, _ = self.post(f"/lists/items/{item}/rename", {"name": NEW_ITEM + " B"})
        self.assertEqual(flash(self.page(headers["location"])),
                         f"{NEW_ITEM} nay có tên mới là {NEW_ITEM} B. Mọi nơi dùng mục này đều hiện tên mới.")
        headers, _ = self.post(f"/lists/items/{item}/rename", {"name": NEW_ITEM + " B"})
        self.assertEqual(flash(self.page(headers["location"])), f"{NEW_ITEM} B vẫn giữ tên cũ. Không có gì thay đổi.")
        headers, _ = self.post_multipart("/documents/new", {"family_id": i["family"]},
                                         {"file": ("Biên bản họp U5.txt", "Nội dung".encode("utf-8"))})
        self.assertEqual(flash(self.page(headers["location"].split("#")[0])), "Đã thêm Tài liệu: Biên bản họp U5.txt.")
        doc = self.db().execute("SELECT id FROM document ORDER BY id DESC LIMIT 1").fetchone()[0]
        self.assert_vietnamese(self.page(f"/documents/{doc}/delete"))
        headers, _ = self.post(f"/documents/{doc}/delete", {"confirm": "yes"})
        page = self.page(headers["location"])
        self.assert_vietnamese(page)
        self.assertEqual(flash(page), "Đã xóa Tài liệu: Biên bản họp U5.txt.")

    def test_refusal_pages_of_these_screens(self):
        cases = (("GET", "/documents/new", None, "Mỗi Tài liệu được thêm cho một Người, một Gia đình hoặc một Lịch."),
                 ("GET", "/documents/new?person_id=999999", None, "Không có Người với mã số 999999."),
                 ("GET", "/documents/new?calendar_item_id=abc", None, "Lịch phải là số nguyên."),
                 ("POST", "/lists/nolist/add", {"name": "x"}, "Không có danh mục nào tên là nolist."),
                 ("POST", "/lists/items/999999/hide", {}, "Không có mục danh mục với mã số 999999."))
        for method, path, form, sentence in cases:
            page = self.page(path, expect=400) if method == "GET" else self.post(path, form, expect=400)[1]
            self.assert_vietnamese(page, path)
            self.assertIn(f'<p class="lead">{html.escape(sentence)}</p>', page, path)


class EnglishScreensTest(_Screens):
    LANG = "en"

    def test_every_page_has_its_words(self):
        for path in self.our_pages():
            self.check_lang(self.page(path), path)
        for path, box in self.documents_panels():
            self.assertNotIn("[[", box, path)
            self.assertIn(">Add document</button>", box, path)
        self.assertIn('data-text-none="No Person found. Press Search to see the page."', self.page("/"))
        self.assertIn("<h1>Sent documents</h1>", self.page("/sent"))
        self.assertIn('<label for="add-list-purpose">New Purpose</label>', self.page("/lists"))
        self.assertIn("No Person found for “zzzzqq”.", self.page("/search?q=zzzzqq"))

    def test_form_error_and_flash_stay_english(self):
        i = self.ids
        _h, page = self.post("/sent/new", {"date": days(0), "recipient_id": i["recipient"], "purpose_id": i["purpose"],
                                           "subject": ""}, expect=400)
        self.check_lang(page, "/sent/new")
        self.assertEqual(field_error(page, "f-subject-error"), "Subject is required.")
        _h, page = self.post("/lists/purpose/add", {"name": ""}, expect=400)
        self.assertEqual(field_error(page, "add-list-purpose-error"), "Name is required.")
        headers, _ = self.post("/lists/purpose/add", {"name": NEW_ITEM})
        self.assertEqual(flash(self.page(headers["location"])), f"{NEW_ITEM} added to Purpose.")


class TextErrorTest(_support.CopyTestCase):
    """Errors of documents.py, sent.py, lists.py and search.py: ``str()`` English (the agent and the logs),
    Tiếng Việt on a page."""

    LANG = "vi"

    def assert_texts(self, fn, english, vietnamese):
        with self.assertRaises(TextError) as ctx:
            fn()
        self.assertEqual(str(ctx.exception), english)
        self.assertEqual(error_text(ctx.exception, "en"), english)
        self.assertEqual(error_text(ctx.exception, "vi"), vietnamese)
        return ctx.exception

    def test_errors_of_the_logic_modules(self):
        conn = self.conn
        fund = lists.get_list(conn, "fund")[0]["name"]
        r, p = self.item("recipient", code=None, name="Giáo hội"), lists.get_list(conn, "purpose")[0]["id"]
        self.assert_texts(lambda: lists.require_item(conn, 999, "fund"), "Fund: choose one from the list.",
                          "Quỹ: hãy chọn một mục trong danh sách.")
        self.assert_texts(lambda: lists.add_item(conn, "fund", "  "), "Name is required.", "Cần nhập Tên.")  # m5
        self.assert_texts(lambda: lists.add_item(conn, "fund", fund.upper()),
                          f"{fund.upper()} is already in the Fund list.",
                          f"{fund.upper()} đã có trong danh mục Quỹ.")
        self.assert_texts(lambda: lists.set_active(conn, 999, False), "No list item with id 999.",
                          "Không có mục danh mục với mã số 999.")
        self.assert_texts(lambda: lists.get_item(conn, "x"), "List item must be a whole number.",
                          "Mục danh mục phải là số nguyên.")
        self.assert_texts(lambda: search.search_persons(conn, "a", limit=0), "limit must be a whole number above 0.",
                          "Số kết quả tối đa phải là số nguyên lớn hơn 0.")
        self.assert_texts(lambda: sent.add_sent_document(conn, "2026-02-30", r, p),
                          "Date must be a real date written YYYY-MM-DD, for example 2026-05-31.",
                          "Ngày phải là một ngày có thật, viết YYYY-MM-DD, ví dụ 2026-05-31.")
        self.assert_texts(lambda: sent.add_sent_document(conn, "2026-01-05", r, p, document_id=999),
                          "No Document with id 999.", "Không có Tài liệu với mã số 999.")
        self.assert_texts(lambda: documents.clean_file_name(".."), "A Document needs a file name.",
                          "Tài liệu cần có tên tệp.")
        self.assert_texts(lambda: documents.add_document(conn, self.folder, b"x", "a.txt", person_id=999),
                          "No Person with id 999.", "Không có Người với mã số 999.")
        self.assert_texts(lambda: documents.add_document(conn, self.folder, b"x", "a.txt", person_id=1, family_id=1),
                          "A Document is linked to one Person, one Family or one Calendar item, not more.",
                          "Mỗi Tài liệu chỉ liên kết với một Người, một Gia đình hoặc một Lịch, không hơn.")
        self.assert_texts(lambda: documents.get_document(conn, "x"), "Document must be a whole number.",
                          "Tài liệu phải là số nguyên.")
        self.assert_texts(lambda: doc_pages.parse_link({}),
                          "A Document is added to one Person, one Family or one Calendar item.",
                          "Mỗi Tài liệu được thêm cho một Người, một Gia đình hoặc một Lịch.")
        self.assert_texts(lambda: list_pages.check_can_hide([{"id": 1, "active": 1, "list_name": "fund"}], 1),
                          "Keep at least one Fund shown: new entries need one to choose.",
                          "Hãy để ít nhất một Quỹ đang hiện: khi nhập mới cần có một mục để chọn.")
        self.assert_texts(lambda: sent_pages.require_shown_item(conn, "", "recipient", "sent.recipient"),
                          "Recipient: choose one from the list.", "Nơi nhận: hãy chọn một mục trong danh sách.")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM document").fetchone()[0], 0)  # nothing kept

    def test_small_helpers(self):
        self.assertEqual(doc_pages.fmt_size(512), "512 bytes")  # outside a request: English, like str()
        self.assertEqual(doc_pages.fmt_size(1, "en"), "1 byte")
        self.assertEqual(doc_pages.fmt_size(512, "vi"), "512 byte")
        self.assertEqual(doc_pages.fmt_size(3_565_158, "vi"), "3,4 MB")
        placed = sent_pages.placed_errors
        self.assertEqual(placed(TextError("errors.required", label="sent.subject")), {"subject": "Cần nhập Trích yếu."})
        self.assertEqual(placed(TextError("sent.err_too_large", mb=50)),
                         {"file": "Tệp: Tệp quá lớn. Giới hạn là 50 MB."})
        self.assertEqual(placed(TextError("lists.err_choose", label="sent.purpose")),
                         {"purpose_id": "Mục đích: hãy chọn một mục trong danh sách."})
        self.assertEqual(placed(ValueError("Plain.")), {"": "Plain."})
        self.assertEqual(placed(None), {})
        # the English sentences are the ones the pages showed before the text table
        self.assertEqual(TEXT["en"]["sent.err_too_large"], "File: " + TEXT["en"]["documents.err_too_large"])
        self.assertEqual(TEXT["en"]["lists.err_choose"].format(label="Fund"), "Fund: choose one from the list.")
        self.assertEqual({t(lists.LABEL_KEYS[n], "en") for n in lists.LABELS}, set(lists.LABELS.values()))


del _Screens  # a base class: unittest must not run it on its own

if __name__ == "__main__":
    unittest.main()
