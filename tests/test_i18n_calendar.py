"""I18N-U3: the Calendar and Care screens in Tiếng Việt and English, through real servers on 127.0.0.1
(port 0) over fake churches in temp folders (``fake.build_fake_church(..., lang=...)``). The old tests
stay English; these read Tiếng Việt, and check that an English copy shows no ``[[key]]``.
"""

import datetime as dt
import html
import pathlib
import re
import tempfile
import unittest

import _support  # noqa: F401 - puts the repo root on sys.path
from churchmgr import calendar as cal
from churchmgr import care, db, fake, people
from churchmgr.i18n import TEXT, TextError, english_left, error_text, t
from churchmgr.pages import care as care_pages
from churchmgr.schema import CALENDAR_KINDS, CALENDAR_PARTS
from test_i18n_core import html_lang, switch
from test_server import LiveServer

ACCENTS = "Lễ Tạ Ơn – Tĩnh tâm Đà Lạt"  # a Calendar item title with accents: kept and shown as typed
DOCUMENTS = re.compile(r'<div id="documents">.*?</section></div>', re.S)
TODAY = dt.date.today()


def days(n):
    return (TODAY + dt.timedelta(days=n)).isoformat()


def without_documents(page):
    """A Calendar item page without its Documents panel: its words belong to pages/documents.py
    (the Documents card), not to the Calendar and Care screens."""
    out, n = DOCUMENTS.subn("", page)
    assert n == 1, "one Documents panel on a Calendar item page"
    return out


def flash(page):
    m = re.search(r'<p class="flash" role="status">([^<]*)</p>', page)
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
                "service": one("SELECT ci.id FROM calendar_item ci JOIN head_count hc ON hc.calendar_item_id = ci.id "
                               "ORDER BY ci.starts_at DESC LIMIT 1"),  # past, a Head count, in a weekly repeat
                "meeting": one("SELECT id FROM calendar_item WHERE kind = 'Meeting' AND starts_at > ? "
                               "ORDER BY starts_at, id LIMIT 1", f"{days(0)} 23:59"),
                "event_past": one("SELECT id FROM calendar_item WHERE kind = 'Event' AND starts_at < ? "
                                  "ORDER BY starts_at LIMIT 1", days(0)),
                "visit_done": one("SELECT id FROM calendar_item WHERE kind = 'Visit' AND visit_done = 1 "
                                  "ORDER BY id LIMIT 1"),
                "visit_planned": one("SELECT id FROM calendar_item WHERE kind = 'Visit' AND visit_done = 0 "
                                     "ORDER BY id LIMIT 1"),
                # a past Service with no Head count: the Head count form, and a row in "Head count to record"
                "to_record": cal.add_calendar_item(conn, "Service", ACCENTS, f"{days(-1)} 08:00",
                                                   place="Nhà thờ")[0],
            }
            cls.event_person = one("SELECT person_id FROM calendar_person WHERE calendar_item_id = ? LIMIT 1",
                                   cls.ids["event_past"])
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

    def our_pages(self):
        """Every GET page of the Calendar and Care screens: the Calendar week, next week, month, an empty month and 7 days, the
        Add a Calendar item form, Calendar item pages (Service with a Head count, Service with the Head
        count form, Meeting, past Event, done and planned Visit: their Edit and Head count forms), the
        Care page (Needs a visit, Plan a Visit, planned Visits, the Care log) and the whole Care log."""
        i = self.ids
        return ["/calendar", f"/calendar?week={days(7)}", f"/calendar?month={TODAY:%Y-%m}",
                f"/calendar?month={TODAY.year + 4}-01", f"/calendar?from={days(0)}", "/calendar/new",
                *(f"/calendar/{i[k]}" for k in ("service", "to_record", "meeting", "event_past", "visit_done",
                                                "visit_planned")),
                "/care", "/care?log=all"]

    def check_lang(self, page, path):
        self.assertEqual(html_lang(page), self.LANG, path)
        self.assertEqual(switch(page)[1:], ("true", "false") if self.LANG == "vi" else ("false", "true"), path)
        self.assertNotIn("[[", page, path)

    def new_item(self, **form):
        base = {"kind": "Meeting", "title": ACCENTS, "starts_at": f"{days(2)}T19:00", "ends_at": "", "place": "",
                "note": "", "repeat": "none", "repeat_until": "", "person_id": "", "family_id": ""}
        headers, _ = self.post("/calendar/new", {**base, **form})
        m = re.fullmatch(r"/calendar/(\d+)\?msg=.+", headers["location"])
        assert m is not None, headers["location"]
        return int(m.group(1)), headers["location"]

    def test_accented_title_is_kept_and_shown_as_typed(self):
        iid, location = self.new_item()
        self.assertEqual(cal.get_calendar_item(self.db(), iid)["title"], ACCENTS)
        page = self.page(location)
        self.check_lang(page, location)
        self.assertIn(f'<h1 lang="vi">{ACCENTS}</h1>', page)
        title_tag = '<title lang="vi">' if self.LANG == "vi" else "<title>"
        self.assertIn(f"{title_tag}{ACCENTS} · ", page)
        self.assertIn(f">{ACCENTS}</a>", self.page(f"/calendar?week={days(2)}"))
        when = f"{TODAY + dt.timedelta(days=2):%d/%m/%Y} 19:00"
        self.assertEqual(flash(page), t("calendar.added_one", self.LANG, kind=t("core.kind_meeting", self.LANG),
                                        when=when))


class VietnameseScreensTest(_Screens):
    LANG = "vi"

    def assert_vietnamese(self, page, path=""):
        self.check_lang(page, path)
        self.assertEqual(english_left(page), [], path)

    def test_every_page_is_vietnamese(self):
        for path in self.our_pages():
            page = self.page(path)
            self.assert_vietnamese(without_documents(page) if re.fullmatch(r"/calendar/\d+", path) else page, path)
        week = self.page("/calendar")
        self.assertIn("<h1>Lịch</h1>", week)
        self.assertIn(">Thêm Lịch</a>", week)
        self.assertIn(">Tuần này</a>", week)
        self.assertIn(f"{t('core.weekday_0', 'vi')} ", week)  # Thứ Hai
        self.assertRegex(week, r'<p class="sub">Tuần \d\d/\d\d – \d\d/\d\d/\d{4} · \d+ Lịch · \d+ Giờ thờ phượng</p>')
        self.assertIn('<span class="kind k-service">Giờ thờ phượng</span>', week)
        month = self.page(f"/calendar?month={TODAY:%Y-%m}")
        self.assertIn(f"Tháng {TODAY.month}/{TODAY.year}", month)
        self.assertIn(f"Không có gì trong Lịch vào Tháng 1/{TODAY.year + 4}.", self.page(f"/calendar?month={TODAY.year + 4}-01"))
        to_record = self.page("/calendar")
        self.assertIn('<h2 id="p-to-record">Số người nhóm cần ghi</h2>', to_record)
        self.assertIn(f'href="/calendar/{self.ids["to_record"]}#head-count">Ghi</a>', to_record)
        item = self.page(f"/calendar/{self.ids['to_record']}")
        self.assertIn('<label for="hc-count">Số người nhóm</label>', item)
        self.assertIn('<summary>Chỉnh sửa Lịch này</summary>', item)
        done = self.page(f"/calendar/{self.ids['visit_done']}")
        self.assertIn("Đã hoàn tất ngày", done)
        self.assertIn('<span class="kind k-visit">Thăm viếng</span>', done)
        care_page = self.page("/care")
        for words in ("Cần thăm viếng", "Lên lịch Thăm viếng", "Thăm viếng đã lên lịch", "Nhật ký thăm viếng",
                      ">Hoàn tất</button>", 'title="Thăm gần nhất"', ">Lên\u00a0lịch</a>"):
            self.assertIn(words, care_page)

    def test_visit_title_is_made_in_the_copy_language(self):
        conn = self.db()
        visits = conn.execute("SELECT title FROM calendar_item WHERE kind = 'Visit'").fetchall()
        self.assertTrue(visits)
        self.assertTrue(all(r["title"].startswith("Thăm viếng ") for r in visits), [r["title"] for r in visits])

    def test_form_errors_are_vietnamese_and_next_to_their_field(self):
        i = self.ids
        base = {"kind": "Service", "title": "", "starts_at": f"{days(1)}T08:00", "ends_at": "", "place": "",
                "note": "", "repeat": "none", "repeat_until": "", "person_id": "", "family_id": ""}
        cases = (
            ("/calendar/new", base, "Cần nhập Tiêu đề.", "f-title-error"),
            ("/calendar/new", {**base, "kind": "Visit", "repeat": "weekly"},
             "Lặp lại: Thăm viếng không lặp lại. Hãy lên lịch từng lần Thăm viếng.", "f-repeat-error"),
            ("/calendar/new", {**base, "title": "x", "ends_at": f"{days(1)}T07:00"},
             "Giờ kết thúc không được trước Giờ bắt đầu.", "f-ends_at-error"),
            (f"/calendar/{i['to_record']}/head-count", {"count": "bảy mươi", "absent_note": ""},
             "Số người nhóm phải là số nguyên, ví dụ 72.", "hc-count-error"),
            (f"/calendar/{i['to_record']}/edit", {"kind": "Service", "title": ACCENTS, "starts_at": "",
                                                  "ends_at": "", "place": "", "note": ""},
             "Cần nhập Giờ bắt đầu.", "edit-starts-error"),
            (f"/calendar/{i['event_past']}/people", {"person_id": "", "part": "joins"},
             "Người: hãy chọn một Người.", "add-person-error"),
            ("/care/visits", {"person_id": "", "family_id": "", "starts_at": f"{days(1)}T10:00", "note": ""},
             "Thăm viếng là cho một Người hoặc một Gia đình: hãy chọn đúng một.", None),
            ("/care/visits", {"person_id": "1", "family_id": "", "starts_at": "ngày mai", "note": ""},
             "Ngày giờ phải viết YYYY-MM-DD HH:MM, ví dụ 2026-05-31 09:30.", "plan-starts-error"),
            (f"/care/visits/{i['visit_planned']}/done", {"done_date": days(1), "care_note": ""},
             f"Ngày hoàn tất không được sau hôm nay ({TODAY:%d/%m/%Y}). Hãy chọn hôm nay hoặc một ngày trước đó.",
             f"done-date-{i['visit_planned']}-error"),
            (f"/calendar/{i['service']}/delete", {}, "Giờ thờ phượng này đã có Số người nhóm, nên được giữ lại.", None),
        )
        for path, form, sentence, field_id in cases:
            _h, page = self.post(path, form, expect=400)
            self.assert_vietnamese(without_documents(page) if path.startswith("/calendar/") and "/new" not in path
                                   else page, path)
            if field_id:
                self.assertIn(f'<p class="error" id="{field_id}">{html.escape(sentence)}</p>', page, path)
            else:
                self.assertIn(f'role="alert">{html.escape(sentence)}</p>', page, path)
        self.assertIsNone(cal.get_head_count(self.db(), i["to_record"]))  # nothing saved
        self.assertEqual(self.db().execute("SELECT visit_done FROM calendar_item WHERE id = ?",
                                           (i["visit_planned"],)).fetchone()[0], 0)

    def test_server_pages_of_calendar_and_care(self):
        for path, sentence, expect in (("/calendar?month=2026-13", "Tháng phải viết YYYY-MM, ví dụ 2026-11.", 400),
                                       ("/calendar?week=31/12/2026", "Tuần phải là một ngày có thật", 400),
                                       ("/calendar/999999", "Không có Lịch với số này.", 404)):
            page = self.page(path, expect=expect)
            self.assert_vietnamese(page, path)
            self.assertIn(sentence, page, path)
        _h, page = self.post(f"/care/visits/{self.ids['visit_done']}/done", {"done_date": days(0)}, expect=400)
        self.assert_vietnamese(page)
        self.assertIn("Đây không phải là Thăm viếng đã lên lịch. Có thể đã Hoàn tất rồi.", page)

    def test_confirm_pages(self):
        i = self.ids
        _h, page = self.post(f"/calendar/{i['event_past']}/people/remove",
                             {"person_id": self.event_person, "part": "joins"}, expect=200)
        self.assert_vietnamese(page)
        self.assertIn("<h1>Bạn có chắc không?</h1>", page)
        self.assertIn(">Có, bỏ Người này ra</button>", page)
        _h, page = self.post(f"/calendar/{i['meeting']}/delete", {}, expect=200)
        self.assert_vietnamese(page)
        self.assertIn("<h1>Xóa Lịch này?</h1>", page)
        self.assertIn("(Buổi họp)", page)
        self.assertIsNotNone(cal.get_calendar_item(self.db(), i["meeting"]))  # nothing changed yet

    def test_flash_messages_are_vietnamese(self):
        iid, location = self.new_item(kind="Service", starts_at=f"{days(-2)}T08:00")
        self.assertEqual(flash(self.page(location)), f"Đã thêm Giờ thờ phượng lúc {TODAY - dt.timedelta(days=2):%d/%m/%Y} 08:00.")
        headers, _ = self.post(f"/calendar/{iid}/head-count", {"count": "64", "absent_note": ""})
        page = self.page(headers["location"])
        self.assert_vietnamese(without_documents(page))
        self.assertEqual(flash(page), "Đã lưu Số người nhóm 64.")
        pid = people.list_persons(self.db())[0]["id"]
        headers, _ = self.post(f"/calendar/{iid}/people", {"person_id": pid, "part": "serves"})
        name = people.get_person(self.db(), pid)["full_name"]
        self.assertEqual(flash(self.page(headers["location"])), f"{name} phục vụ.")
        headers, _ = self.post("/care/visits", {"person_id": pid, "family_id": "", "starts_at": f"{days(0)}T07:00",
                                                "note": ""})
        page = self.page(headers["location"])
        self.assert_vietnamese(page)
        self.assertEqual(flash(page), f"Đã lên lịch Thăm viếng lúc {TODAY:%d/%m/%Y} 07:00.")
        visit = self.db().execute("SELECT id, title FROM calendar_item WHERE kind = 'Visit' ORDER BY id DESC").fetchone()
        self.assertEqual(visit["title"], f"Thăm viếng {name}")
        headers, _ = self.post(f"/care/visits/{visit['id']}/done", {"done_date": days(0), "care_note": "Cầu nguyện"})
        self.assertEqual(flash(self.page(headers["location"])),
                         f"Đã hoàn tất Thăm viếng ngày {TODAY:%d/%m/%Y}. Lần thăm này có trong Nhật ký thăm viếng.")


class EnglishScreensTest(_Screens):
    LANG = "en"

    def test_every_page_has_its_words(self):
        for path in self.our_pages():
            self.check_lang(self.page(path), path)
        week = self.page("/calendar")
        self.assertIn("<h1>Calendar</h1>", week)
        self.assertIn('<span class="kind k-service">Service</span>', week)

    def test_visit_title_is_made_in_the_copy_language(self):
        titles = [r[0] for r in self.db().execute("SELECT title FROM calendar_item WHERE kind = 'Visit'")]
        self.assertTrue(titles)
        self.assertTrue(all(title.startswith("Visit ") for title in titles), titles)

    def test_form_error_stays_english(self):
        _h, page = self.post(f"/calendar/{self.ids['to_record']}/head-count", {"count": "x", "absent_note": ""},
                             expect=400)
        self.check_lang(page, "head-count")
        self.assertIn('<p class="error" id="hc-count-error">Head count must be a whole number of people, '
                      'for example 72.</p>', page)


class CalendarTextErrorTest(_support.CopyTestCase):
    """Errors of calendar.py and care.py: ``str()`` English (the agent and the logs), Tiếng Việt on a page."""

    LANG = "vi"

    def assert_texts(self, fn, english, vietnamese):
        with self.assertRaises(TextError) as ctx:
            fn()
        self.assertEqual(str(ctx.exception), english)
        self.assertEqual(error_text(ctx.exception, "en"), english)
        self.assertEqual(error_text(ctx.exception, "vi"), vietnamese)
        return ctx.exception

    def test_calendar_and_care_errors(self):
        pid = people.add_person(self.conn, "Trần Thị Mai", status_id=self.status("member"), start_date="2026-01-01")
        self.assert_texts(lambda: cal.check_year("abc"), "Year must be a whole number like 2026.",
                          "Năm phải là số nguyên, ví dụ 2026.")
        self.assert_texts(lambda: cal.add_calendar_item(self.conn, "Service", "  ", "2026-11-01 08:00"),
                          "Title is required.", "Cần nhập Tiêu đề.")  # a TEXT key label (m5)
        self.assert_texts(lambda: cal.add_calendar_item(self.conn, "Service", "A", "2026-11-01 08:00",
                                                        "2026-11-01 07:00"),
                          "The end is before the start.", "Giờ kết thúc ở trước giờ bắt đầu.")
        self.assert_texts(lambda: cal.add_calendar_item(self.conn, "Party", "A", "2026-11-01 08:00"),
                          "Kind must be one of: Service, Meeting, Visit, Event.",
                          "Loại lịch phải là một trong: Giờ thờ phượng, Buổi họp, Thăm viếng, Chương trình.")
        self.assert_texts(lambda: cal.get_calendar_item(self.conn, "abc"),
                          "Calendar item must be a whole number.", "Lịch phải là số nguyên.")
        self.assert_texts(lambda: care.plan_visit(self.conn, "2026-11-03 10:00"),
                          "A Visit is for one Person or one Family: give exactly one of them.",
                          "Thăm viếng là cho một Người hoặc một Gia đình: hãy chọn đúng một.")
        self.assert_texts(lambda: care.plan_visit(self.conn, "2026-11-03 10:00", family_id=999),
                          "No Family with id 999.", "Không có Gia đình với mã số 999.")
        iid = cal.add_calendar_item(self.conn, "Service", "Thờ phượng", "2026-11-01 08:00")[0]
        self.assert_texts(lambda: care.mark_visit_done(self.conn, iid, "2026-11-01"),
                          "Only a Visit can be marked done.", "Chỉ Thăm viếng mới Hoàn tất được.")
        cal.set_head_count(self.conn, iid, 70)
        self.assertEqual(cal.delete_refusal_key(self.conn, iid), "calendar.err_kept_head_count")
        self.assertEqual(cal.delete_refusal(self.conn, iid), "This Service has a Head count, so it is kept.")
        e = self.assert_texts(lambda: cal.delete_calendar_item(self.conn, iid),
                              "This Service has a Head count, so it is kept.",
                              "Giờ thờ phượng này đã có Số người nhóm, nên được giữ lại.")
        self.assertEqual(e.key, "calendar.err_kept_head_count")
        e = self.assert_texts(lambda: care_pages.mark_visit_done_from_form(self.conn, iid, {"done_date": "2026-11-01"}),
                              "This is not a planned Visit. It may be marked done already.",
                              "Đây không phải là Thăm viếng đã lên lịch. Có thể đã Hoàn tất rồi.")
        self.assertIsInstance(e, care_pages.NotPlannedVisit)
        vid = care.plan_visit(self.conn, "2026-11-03 10:00", person_id=pid)
        self.assertEqual(cal.get_calendar_item(self.conn, vid)["title"], "Thăm viếng Trần Thị Mai")

    def test_old_english_lists_in_the_text(self):
        """The English sentences name the stored codes, as before the text table."""
        self.assertEqual(TEXT["en"]["calendar.err_kind"], f"Kind must be one of: {', '.join(CALENDAR_KINDS)}.")
        self.assertEqual(TEXT["en"]["calendar.err_part"], f"Part must be one of: {', '.join(CALENDAR_PARTS)}.")
        self.assertEqual(TEXT["en"]["calendar.err_repeat"], f"Repeat must be one of: {', '.join(cal.REPEATS)}.")

    def test_placed_errors_finds_the_field_from_the_english_sentence(self):
        exc = TextError("errors.required", label="calendar.title_label")
        labels = {"kind": "calendar.kind", "title": "calendar.title_label"}
        self.assertEqual(care_pages.placed_errors(("new", exc), "new", labels), {"title": "Cần nhập Tiêu đề."})
        self.assertEqual(care_pages.placed_errors(("new", exc), "edit", labels), {})
        self.assertEqual(care_pages.placed_errors(("new", ValueError("Plain.")), "new", labels), {"": "Plain."})


del _Screens  # a base class: unittest must not run it on its own

if __name__ == "__main__":
    unittest.main()
