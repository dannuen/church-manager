"""Card C2: the Calendar pages through the real server (port 0, a fake church in a temp folder,
Host and Origin headers): a weekly repeat, people who serve or join, the Head count on the
dashboard, the past-item rules, delete with a confirm step, and a Visit from /calendar/new."""

import contextlib
import datetime as dt
import html
import re
import time
import types
import unittest
from unittest import mock

import _support  # noqa: F401 - puts the repo root on sys.path
from churchmgr import calendar as cal
from churchmgr import people
from churchmgr.pages import calendar as cal_pages
from churchmgr.pages import dashboard
from test_pages_people import TODAY, PagesTestBase, section, shown
from test_server import parse_panels


def at(day, hm="19:00"):
    """``datetime-local`` text for ``day`` (a date) at ``hm``."""
    return f"{day.isoformat()}T{hm}"


def days(n):
    return TODAY + dt.timedelta(days=n)


class _FixedDate(dt.date):
    """``date`` whose ``today()`` is ``_FixedDate.fixed``."""
    fixed = None

    @classmethod
    def today(cls):
        return cls.fixed


@contextlib.contextmanager
def today_is(day):
    """While in this ``with`` block, the Dashboard and the Calendar pages see ``day`` as today."""
    _FixedDate.fixed = day
    fake_dt = types.SimpleNamespace(date=_FixedDate, timedelta=dt.timedelta, datetime=dt.datetime)
    with mock.patch.object(dashboard, "_dt", fake_dt), mock.patch.object(cal_pages, "_dt", fake_dt):
        yield


class CalendarPagesTest(PagesTestBase):
    def new_item(self, expect=303, **form):
        base = {"kind": "Service", "title": "", "starts_at": at(TODAY), "ends_at": "", "place": "", "note": "",
                "repeat": "none", "repeat_until": "", "person_id": "", "family_id": ""}
        headers, page = self.post("/calendar/new", {**base, **form}, expect=expect)
        if expect != 303:
            return page
        m = re.fullmatch(r"/calendar/(\d+)\?msg=.+", headers["location"])
        self.assertIsNotNone(m, headers["location"])
        return int(m.group(1))

    def some_person(self, k=0):
        return people.list_persons(self.db())[k]

    def test_weekly_service_people_head_count_and_dashboard(self):
        title = "C2 Thờ phượng tối thứ Tư"
        first, until = days(-22), days(6)
        iid = self.new_item(kind="Service", title=title, starts_at=at(first), ends_at=at(first, "20:30"),
                            place="Nhà thờ", repeat="weekly", repeat_until=until.isoformat())
        series = cal.series_items(self.db(), iid)
        self.assertEqual([s["starts_at"] for s in series],
                         [f"{days(n).isoformat()} 19:00" for n in (-22, -15, -8, -1, 6)])
        self.assertTrue(all(s["ends_at"][11:] == "20:30" and s["place"] == "Nhà thờ" for s in series))
        # all 5 are listed: once by week, once by month (the link text; the title attribute holds it too)
        weeks = sorted({cal_pages.week_start(days(n)) for n in (-22, -15, -8, -1, 6)})
        by_week = sum(section(self.page(f"/calendar?week={w.isoformat()}"), "calendar-list").count(f">{title}</a>")
                      for w in weeks)
        months = sorted({s["starts_at"][:7] for s in series})
        by_month = sum(section(self.page(f"/calendar?month={m}"), "calendar-list").count(f">{title}</a>")
                       for m in months)
        self.assertEqual((by_week, by_month), (5, 5))
        week_page = self.page(f"/calendar?week={days(-1).isoformat()}")
        self.assertIn("19:00–20:30", section(week_page, "calendar-list"))
        self.assertIn("Service", section(week_page, "calendar-list"))
        self.assertIn("Nhà thờ", section(week_page, "calendar-list"))
        self.assertIn("1 of 5", section(self.page(f"/calendar/{iid}"), "details"))

        # a Person serves at the Service of yesterday
        last_past = series[3]["id"]
        person = self.some_person(2)
        self.post(f"/calendar/{last_past}/people", {"person_id": person["id"], "part": "serves"})
        self.assertEqual([(p["person_id"], p["part"]) for p in cal.item_people(self.db(), last_past)],
                         [(person["id"], "serves")])
        listed = section(self.page(f"/calendar/{last_past}"), "people")
        self.assertIn(person["full_name"], listed)
        self.assertIn("Serves", listed)
        headers, _ = self.post(f"/calendar/{last_past}/people", {"person_id": person["id"], "part": "serves"})
        self.assertIn("Nothing+changed", headers["location"])

        # the Head count of that Service shows on the dashboard Services panel
        self.post(f"/calendar/{last_past}/head-count", {"count": "137", "absent_note": "C2 vắng: gia đình anh Tâm"})
        hc = cal.get_head_count(self.db(), last_past)
        self.assertEqual((hc["count"], hc["absent_note"]), (137, "C2 vắng: gia đình anh Tâm"))
        services = section(self.page("/"), "services")
        self.assertIn(f"Head count 137 on {shown(days(-1).isoformat())}", services)
        item_page = self.page(f"/calendar/{last_past}")
        self.assertIn("C2 vắng: gia đình anh Tâm", section(item_page, "head-count"))
        self.assertIn("Head count 137", item_page)  # the finding line
        # a bad number is refused next to its field; a Service after today cannot have one yet
        _h, page = self.post(f"/calendar/{last_past}/head-count", {"count": "7.5"}, expect=400)
        self.assertIn('id="hc-count-error"', page)
        self.assertEqual(cal.get_head_count(self.db(), last_past)["count"], 137)
        future = series[4]["id"]
        _h, page = self.post(f"/calendar/{future}/head-count", {"count": "50"}, expect=400)
        self.assertIn("has not happened yet", page)
        self.assertIsNone(cal.get_head_count(self.db(), future))
        self.assertIn("on the day of the Service or after", section(self.page(f"/calendar/{future}"), "head-count"))
        # a Service with a Head count is kept: the page says why and offers no delete button
        delete_box = section(self.page(f"/calendar/{last_past}"), "delete")
        self.assertIn("has a Head count, so it is kept", delete_box)
        self.assertNotIn(f'action="/calendar/{last_past}/delete"', delete_box)
        _h, page = self.post(f"/calendar/{last_past}/delete", {"confirm": "yes"}, expect=400)
        self.assertIn("has a Head count, so it is kept", page)
        self.assertIsNotNone(cal.get_calendar_item(self.db(), last_past))

    def test_past_item_keeps_its_people(self):
        iid = self.new_item(kind="Event", title="C2 Lễ đã qua", starts_at=at(days(-10), "09:00"))
        person = self.some_person(3)
        self.post(f"/calendar/{iid}/people", {"person_id": person["id"], "part": "joins"})
        # it cannot move to today or later (then it could be deleted)
        form = {"kind": "Event", "title": "C2 Lễ đã qua", "starts_at": at(days(3), "09:00"), "ends_at": "",
                "place": "", "note": ""}
        _h, page = self.post(f"/calendar/{iid}/edit", form, expect=400)
        self.assertIn("cannot move to today or later", page)
        self.assertIn('id="edit-starts-error"', page)
        self.assertEqual(cal.get_calendar_item(self.db(), iid)["starts_at"], f"{days(-10).isoformat()} 09:00")
        # another past date is fine
        self.post(f"/calendar/{iid}/edit", {**form, "starts_at": at(days(-11), "10:00")})
        self.assertEqual(cal.get_calendar_item(self.db(), iid)["starts_at"], f"{days(-11).isoformat()} 10:00")
        # taking the Person off asks first (a POST confirm step), then removes
        status, _h, data = self.request("POST", f"/calendar/{iid}/people/remove",
                                        {"person_id": person["id"], "part": "joins"})
        page = data.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("Are you sure?", page)
        self.assertIn(person["full_name"], section(page, "confirm"))
        self.assertIn('name="confirm" value="yes"', page)
        self.assertEqual(len(cal.item_people(self.db(), iid)), 1)
        self.post(f"/calendar/{iid}/people/remove", {"person_id": person["id"], "part": "joins", "confirm": "yes"})
        self.assertEqual(cal.item_people(self.db(), iid), [])

    def test_delete_asks_first_and_a_future_item_loses_people_at_once(self):
        iid = self.new_item(kind="Meeting", title="C2 Họp sẽ xoá", starts_at=at(days(9), "18:00"))
        person = self.some_person(4)
        self.post(f"/calendar/{iid}/people", {"person_id": person["id"], "part": "joins"})
        self.post(f"/calendar/{iid}/people/remove", {"person_id": person["id"], "part": "joins"})  # no confirm
        self.assertEqual(cal.item_people(self.db(), iid), [])
        status, _h, data = self.request("POST", f"/calendar/{iid}/delete", {})
        self.assertEqual(status, 200)
        self.assertIn("C2 Họp sẽ xoá", section(data.decode("utf-8"), "confirm"))
        self.assertIsNotNone(cal.get_calendar_item(self.db(), iid))
        headers, _ = self.post(f"/calendar/{iid}/delete", {"confirm": "yes"})
        self.assertTrue(headers["location"].startswith("/calendar?week="))
        self.assertIsNone(cal.get_calendar_item(self.db(), iid))
        self.assertIn("not found", self.page(f"/calendar/{iid}", expect=404))

    def test_item_page_needs_no_write_lock(self):
        """Showing or hiding Delete only reads: the page opens while another connection holds the write lock."""
        iid = self.new_item(kind="Meeting", title="C2 Họp không khoá", starts_at=at(days(5), "18:00"))
        kept = self.new_item(kind="Meeting", title="C2 Họp đã qua", starts_at=at(days(-5), "18:00"))
        self.post(f"/calendar/{kept}/people", {"person_id": self.some_person(2)["id"], "part": "joins"})
        writer = self.db()
        writer.execute("BEGIN IMMEDIATE")  # the write lock (a real delete would wait for it, then fail)
        try:
            started = time.monotonic()
            page = self.page(f"/calendar/{iid}")
            self.assertIn(f'action="/calendar/{iid}/delete"', section(page, "delete"))
            kept_box = section(self.page(f"/calendar/{kept}"), "delete")
            self.assertLess(time.monotonic() - started, 3)  # sqlite3 waits 5 s for a lock
        finally:
            writer.execute("ROLLBACK")
        self.assertIn("in the past and people joined or served it, so it is kept", kept_box)
        self.assertNotIn(f'action="/calendar/{kept}/delete"', kept_box)

    def test_visit_from_the_calendar_form(self):
        person = self.some_person(5)
        iid = self.new_item(kind="Visit", person_id=person["id"], starts_at=at(days(2), "10:00"),
                            ends_at=at(days(2), "11:00"), place="Nhà riêng")
        row = cal.get_calendar_item(self.db(), iid)
        self.assertEqual((row["kind"], row["visit_person_id"], row["title"], row["place"]),
                         ("Visit", person["id"], f"Visit {person['full_name']}", "Nhà riêng"))
        self.assertEqual(row["ends_at"], f"{days(2).isoformat()} 11:00")
        self.assertIn(f'href="/people/{person["id"]}"', section(self.page(f"/calendar/{iid}"), "details"))
        # a Visit needs one Person or Family, and does not repeat; other kinds take no Person
        page = self.new_item(expect=400, kind="Visit", starts_at=at(days(2)))
        self.assertIn('id="f-person_id-error"', page)
        page = self.new_item(expect=400, kind="Visit", person_id=person["id"], repeat="weekly",
                             repeat_until=days(30).isoformat())
        self.assertIn("does not repeat", page)
        page = self.new_item(expect=400, kind="Meeting", title="C2 Họp", person_id=person["id"])
        self.assertIn("only for a Visit", page)
        page = self.new_item(expect=400, kind="Meeting", title="C2 Họp", repeat="weekly")
        self.assertIn('id="f-repeat_until-error"', page)
        page = self.new_item(expect=400, kind="Meeting", title="", starts_at=at(days(1)))
        self.assertIn('id="f-title-error"', page)

    def test_calendar_list_blocks_and_escaping(self):
        page = self.page("/calendar")
        self.assertEqual(parse_panels(page).h1, 1)
        self.assertEqual(section(page, "calendar-list").count('class="cal-day'), 7)  # the 7 days of this week
        self.assertIn("This week", page)
        self.assertIn('name="month" type="month"', page)
        self.assertIn("Head count to record", page)
        self.assertRegex(page, r'<p class="sub">Week [^<]* · \d+ Calendar items? · ')  # the finding line
        iid = self.new_item(kind="Event", title="<b>C2 Thoát</b>", starts_at=at(TODAY, "23:30"))
        page = self.page("/calendar")
        self.assertIn("&lt;b&gt;C2 Thoát&lt;/b&gt;", page)
        self.assertNotIn("<b>C2 Thoát</b>", page)
        self.assertIn("&lt;b&gt;C2 Thoát&lt;/b&gt;", self.page(f"/calendar/{iid}"))
        self.assertIn('action="/documents/new"', section(self.page(f"/calendar/{iid}"), "documents"))  # card C3
        self.assertIn("Month must be written YYYY-MM", self.page("/calendar?month=2026-13", expect=400))
        self.assertIn('type="datetime-local"', self.page("/calendar/new"))

    def test_dashboard_view_all_opens_the_same_7_days(self):
        """B1: on a Sunday and on a Wednesday, the count on the Dashboard link is the count of the
        Calendar page it opens (``?from=`` today, 7 days), not of the Monday-to-Sunday week."""
        sunday = dt.date(2031, 6, 1)  # far from the fake church's Calendar items
        self.assertEqual(sunday.weekday(), 6)
        for n in range(-1, 11):  # one Meeting a day, from the Saturday before to 10 days after
            self.new_item(kind="Meeting", title=f"B1 Họp ngày {n}", starts_at=at(sunday + dt.timedelta(days=n), "18:00"))
        for today in (sunday, sunday + dt.timedelta(days=3)):  # a Sunday and a Wednesday
            with today_is(today):
                week = section(self.page("/"), "this-week")
                m = re.search(r'<a class="card-link" href="([^"]+)">View all (\d+) in Calendar</a>', week)
                self.assertIsNotNone(m, week)
                href, count = html.unescape(m.group(1)), int(m.group(2))
                self.assertEqual(href, f"/calendar?from={today.isoformat()}")
                page = self.page(href)
            last = today + dt.timedelta(days=6)
            self.assertIn(f'<p class="sub">{today:%d/%m} – {last:%d/%m/%Y} · {count} Calendar items · ', page)
            listing = section(page, "calendar-list")
            self.assertEqual(listing.count('class="row cal-row"'), count)
            self.assertEqual(listing.count('class="cal-day'), 7)  # every day is listed
            first = (today - sunday).days
            self.assertEqual(sorted(int(n) for n in re.findall(r">B1 Họp ngày (-?\d+)</a>", listing)),
                             list(range(first, first + 7)))
            self.assertEqual(count, 7)
            # Previous and Next move 7 days and keep ?from=
            self.assertIn(f'href="/calendar?from={today - dt.timedelta(days=7)}"', page)
            self.assertIn(f'href="/calendar?from={today + dt.timedelta(days=7)}"', page)
        self.assertIn("First day must be a real date written YYYY-MM-DD",
                      self.page("/calendar?from=2031-02-30", expect=400))
        # the week mode is not changed: Monday to Sunday, so that Sunday's week holds only 2 of them
        self.assertIn("Week 26/05 – 01/06/2031 · 2 Calendar items", self.page(f"/calendar?week={sunday}"))

    def test_month_links_stop_at_1900_01_and_9999_12(self):
        """B21: no chip links to a month the app refuses. 1900-01 has no previous month; 9999-12 opens
        with its last day and has no next month. Plain sentences only, never Python text."""
        page = self.page("/calendar?month=1900-01")
        self.assertNotIn("December 1899", page)
        self.assertNotIn("month=1899-12", page)
        self.assertIn('href="/calendar?month=1900-02">February 1900 ›</a>', page)
        self.assertIn("This month", page)
        cal.add_calendar_item(self.db(), "Event", "B21 Lễ ngày cuối", "9999-12-31 23:59")  # the very last minute
        page = self.page("/calendar?month=9999-12")
        self.assertNotIn("January 10000", page)
        self.assertNotIn("month=10000-01", page)
        self.assertIn('href="/calendar?month=9999-11">‹ November 9999</a>', page)
        self.assertIn("This month", page)
        self.assertIn("B21 Lễ ngày cuối", section(page, "calendar-list"))  # the last day of 9999 is listed
        for bad in ("1899-12", "0000-01"):
            self.assertIn("Month: use a year from 1900 to 9999.", self.page(f"/calendar?month={bad}", expect=400))
        page = self.page("/calendar?month=10000-01", expect=400)  # a 5-digit year: the form sentence
        self.assertIn("Month must be written YYYY-MM, for example 2026-11.", page)
        self.assertNotIn("year must be in", page)
        for path in ("/calendar", "/calendar?month=1900-01", "/calendar?month=9999-12", f"/calendar?from={TODAY}"):
            self.assertRegex(self.page(path), r'id="cal-month" name="month" type="month" value="[0-9]{4}-[0-9]{2}" '
                                              r'min="1900-01" max="9999-12" required>')

    def test_week_and_7_days_stop_at_the_first_and_the_last_day(self):
        """B21: the week of Monday 9999-12-27 and the 7 days from it end on Friday 9999-12-31 with no next
        link (no 500 from a date past 9999-12-31). The week of Monday 0001-01-01 and the 7 days from it have
        no previous link, and no Month chip to a month the app refuses."""
        cal.add_calendar_item(self.db(), "Event", "B21 Lễ thứ Sáu cuối", "9999-12-31 08:00")
        for path, next_chip in (("/calendar?week=9999-12-27", "Next week ›"), ("/calendar?from=9999-12-27",
                                                                                "Next 7 days ›")):
            page = self.page(path)
            listing = section(page, "calendar-list")
            self.assertEqual(listing.count('class="cal-day'), 5, path)  # Monday 27 to Friday 31
            self.assertIn("B21 Lễ thứ Sáu cuối", listing)
            self.assertIn("27/12 – 31/12/9999", page)  # the finding line ends on the last day
            self.assertNotIn(next_chip, page)
            self.assertNotIn("10000", page)
            self.assertIn('href="/calendar?month=9999-12">Month</a>', page)
        self.assertIn('href="/calendar?week=9999-12-20">‹ Previous week</a>', self.page("/calendar?week=9999-12-27"))
        page = self.page("/calendar?from=9999-12-24")  # its next 7 days start on the last day
        self.assertIn('href="/calendar?from=9999-12-31">Next 7 days ›</a>', page)
        last = self.page("/calendar?from=9999-12-31")
        self.assertEqual(section(last, "calendar-list").count('class="cal-day'), 1)
        self.assertIn('href="/calendar?from=9999-12-24">‹ Previous 7 days</a>', last)
        for path, prev_chip, next_href in (
                ("/calendar?week=0001-01-01", "‹ Previous week", "/calendar?week=0001-01-08"),
                ("/calendar?from=0001-01-01", "‹ Previous 7 days", "/calendar?from=0001-01-08")):
            page = self.page(path)
            self.assertEqual(section(page, "calendar-list").count('class="cal-day'), 7, path)
            self.assertNotIn(prev_chip, page)
            self.assertIn(f'href="{next_href}"', page)
            self.assertNotIn("month=0001-01", page)  # the month 0001-01 is refused, so no Month chip


class SmallLogicTest(unittest.TestCase):
    def test_weeks_and_months(self):
        self.assertEqual(cal_pages.week_start(dt.date(2026, 11, 1)), dt.date(2026, 10, 26))  # a Sunday
        self.assertEqual(cal_pages.week_start(dt.date(2026, 11, 2)), dt.date(2026, 11, 2))   # a Monday
        self.assertEqual(cal_pages.parse_week("", dt.date(2026, 11, 4)), dt.date(2026, 11, 2))
        self.assertEqual(cal_pages.parse_week("2026-12-31", dt.date(2026, 11, 4)), dt.date(2026, 12, 28))
        self.assertEqual(cal_pages.parse_month(" 2026-02 "), (2026, 2))
        for bad in ("2026-13", "2026-1", "26-01", "", None, "2026-00", "abcd-ef"):
            with self.assertRaises(ValueError):
                cal_pages.parse_month(bad)
        self.assertEqual(cal_pages.shift_month(2026, 12, 1), (2027, 1))
        self.assertEqual(cal_pages.shift_month(2026, 1, -1), (2025, 12))
        self.assertEqual(cal_pages.month_text(2026, 3), "2026-03")

    def test_parse_month_says_which_years(self):
        """B21: the right form with a year outside 1900 to 9999 gets its own sentence."""
        for value in ("1899-12", "0000-01", "0001-06"):
            with self.assertRaises(ValueError) as ctx:
                cal_pages.parse_month(value)
            self.assertEqual(str(ctx.exception), "Month: use a year from 1900 to 9999.", value)
        for value in ("10000-01", "1899-13", "2026-1"):
            with self.assertRaises(ValueError) as ctx:
                cal_pages.parse_month(value)
            self.assertEqual(str(ctx.exception), "Month must be written YYYY-MM, for example 2026-11.", value)
        self.assertEqual(cal_pages.parse_month("1900-01"), (1900, 1))
        self.assertEqual(cal_pages.parse_month("9999-12"), (9999, 12))

    def test_month_step_and_day_step_stop_at_the_edges(self):
        """B21: one rule for every month chip (1900-01 to 9999-12) and every week or 7-day link
        (no date before 0001-01-01 or after 9999-12-31)."""
        self.assertEqual(cal_pages.month_step(1900, 1, 1), (1900, 2))
        self.assertIsNone(cal_pages.month_step(1900, 1, -1))
        self.assertEqual(cal_pages.month_step(9999, 12, -1), (9999, 11))
        self.assertIsNone(cal_pages.month_step(9999, 12, 1))
        self.assertEqual(cal_pages.month_step(2026, 12, 1), (2027, 1))
        self.assertEqual(cal_pages.month_step(1900, 1), (1900, 1))  # k = 0: the month itself
        self.assertIsNone(cal_pages.month_step(1899, 12))
        self.assertIsNone(cal_pages.month_step(1, 1))
        self.assertEqual(cal_pages.day_step(dt.date(9999, 12, 24), 7), dt.date(9999, 12, 31))
        self.assertIsNone(cal_pages.day_step(dt.date(9999, 12, 25), 7))
        self.assertEqual(cal_pages.day_step(dt.date(1, 1, 8), -7), dt.date(1, 1, 1))
        self.assertIsNone(cal_pages.day_step(dt.date(1, 1, 7), -7))

    def test_form_datetime_and_time_span(self):
        self.assertEqual(cal_pages.form_datetime("2026-11-08T08:00", "Starts at"), "2026-11-08 08:00")
        self.assertIsNone(cal_pages.form_datetime("  ", "Ends at"))
        with self.assertRaises(ValueError) as ctx:
            cal_pages.form_datetime("08/11/2026 08:00", "Ends at")
        self.assertTrue(str(ctx.exception).startswith("Ends at"))
        self.assertEqual(cal_pages.input_datetime("2026-11-08 08:00"), "2026-11-08T08:00")
        self.assertEqual(cal_pages.time_span("2026-11-08 08:00", None), "08:00")
        self.assertEqual(cal_pages.time_span("2026-11-08 08:00", "2026-11-08 10:00"), "08:00–10:00")
        self.assertEqual(cal_pages.time_span("2026-11-08 20:00", "2026-11-09 06:00"), "20:00 – 09/11 06:00")

    def test_leaves_the_past(self):
        today = "2026-11-08"
        self.assertTrue(cal_pages.leaves_the_past("2026-11-01 08:00", "2026-11-08 08:00", [1], today))
        self.assertTrue(cal_pages.leaves_the_past("2026-11-01 08:00", "2026-12-01 08:00", [1], today))
        self.assertFalse(cal_pages.leaves_the_past("2026-11-01 08:00", "2026-11-07 08:00", [1], today))
        self.assertFalse(cal_pages.leaves_the_past("2026-11-01 08:00", "2026-12-01 08:00", [], today))
        self.assertFalse(cal_pages.leaves_the_past("2026-11-09 08:00", "2026-12-01 08:00", [1], today))

    def test_parse_head_count(self):
        self.assertEqual(cal_pages.parse_head_count(" 72 "), 72)
        self.assertEqual(cal_pages.parse_head_count("0"), 0)
        for bad in ("", None, "7.5", "-3", "1,000", "７２", "abc", str(cal.MAX_HEAD_COUNT + 1)):
            with self.assertRaises(ValueError) as ctx:
                cal_pages.parse_head_count(bad)
            self.assertTrue(str(ctx.exception).startswith("Head count"), bad)


if __name__ == "__main__":
    unittest.main()
