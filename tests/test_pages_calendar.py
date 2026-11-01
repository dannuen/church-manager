"""Card C2: the Calendar pages through the real server (port 0, a fake church in a temp folder,
Host and Origin headers): a weekly repeat, people who serve or join, the Head count on the
dashboard, the past-item rules, delete with a confirm step, and a Visit from /calendar/new."""

import datetime as dt
import re
import unittest

import _support  # noqa: F401 - puts the repo root on sys.path
from churchmgr import calendar as cal
from churchmgr import people
from churchmgr.pages import calendar as cal_pages
from test_pages_people import TODAY, PagesTestBase, section, shown
from test_server import parse_panels


def at(day, hm="19:00"):
    """``datetime-local`` text for ``day`` (a date) at ``hm``."""
    return f"{day.isoformat()}T{hm}"


def days(n):
    return TODAY + dt.timedelta(days=n)


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
        # all 5 are listed: once by week, once by month
        weeks = sorted({cal_pages.week_start(days(n)) for n in (-22, -15, -8, -1, 6)})
        by_week = sum(section(self.page(f"/calendar?week={w.isoformat()}"), "calendar-list").count(title)
                      for w in weeks)
        months = sorted({s["starts_at"][:7] for s in series})
        by_month = sum(section(self.page(f"/calendar?month={m}"), "calendar-list").count(title) for m in months)
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
        self.assertIn("C3: the Documents list", self.page(f"/calendar/{iid}"))  # the marked spot for card C3
        self.assertIn("Month must be written YYYY-MM", self.page("/calendar?month=2026-13", expect=400))
        self.assertIn('type="datetime-local"', self.page("/calendar/new"))


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
