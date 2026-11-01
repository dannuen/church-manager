"""Card C1: the Care page through the real server (port 0, a fake church in a temp folder,
Host and Origin headers): Needs a visit, Plan a Visit, Mark Visit done and the Care log."""

import datetime as dt
import unittest

import _support  # noqa: F401 - puts the repo root on sys.path
from churchmgr import care, people
from churchmgr.pages import care as care_pages
from test_pages_people import TODAY, PagesTestBase, section, shown
from test_server import parse_panels


class CarePageTest(PagesTestBase):
    def latest_planned(self, person_id=None, family_id=None):
        row = self.db().execute(
            "SELECT id FROM calendar_item WHERE kind = 'Visit' AND visit_done = 0 "
            "AND (visit_person_id = ? OR visit_family_id = ?) ORDER BY id DESC LIMIT 1",
            (person_id, family_id),
        ).fetchone()
        self.assertIsNotNone(row)
        return row["id"]

    def test_plan_and_mark_done_puts_it_in_the_care_log_and_the_person_leaves_needs_a_visit(self):
        conn = self.db()
        needs = care.needs_visit(conn)
        person = next(p for p in needs if p["last_visit"] is None)
        pid = person["person_id"]
        page = self.page("/care")
        self.assertIn(f'href="/people/{pid}"', section(page, "needs-visit"))
        self.assertEqual(parse_panels(page).rows["needs-visit"], len(needs))

        self.post("/care/visits", {"person_id": pid, "family_id": "", "starts_at": f"{TODAY.isoformat()}T09:30",
                                   "note": "Mang theo Kinh Thánh"})
        iid = self.latest_planned(person_id=pid)
        page = self.page("/care")
        planned = section(page, "planned")
        self.assertIn(f'action="/care/visits/{iid}/done"', planned)
        self.assertIn(f"{shown(TODAY.isoformat())} 09:30", planned)
        self.assertIn("Mang theo Kinh Thánh", planned)

        note = "C1-CARE-Đã thăm, cầu nguyện chung"
        self.post(f"/care/visits/{iid}/done", {"done_date": TODAY.isoformat(), "care_note": note})
        page = self.page("/care")
        log = section(page, "care-log")
        self.assertIn(note, log)
        self.assertIn(person["full_name"], log)
        self.assertIn(shown(TODAY.isoformat()), log)
        self.assertNotIn(f'href="/people/{pid}"', section(page, "needs-visit"))
        self.assertNotIn(f"/care/visits/{iid}/done", section(page, "planned"))
        self.assertNotIn(pid, [p["person_id"] for p in care.needs_visit(conn)])
        # the Person page shows that Person's Care log too
        person_page = self.page(f"/people/{pid}")
        self.assertIn(note, section(person_page, "care-log"))
        self.assertIn(f"Last Visit {shown(TODAY.isoformat())}", person_page)

    def test_done_date_after_today_is_refused(self):
        conn = self.db()
        pid = care.needs_visit(conn)[-1]["person_id"]
        self.post("/care/visits", {"person_id": pid, "starts_at": f"{TODAY.isoformat()}T15:00"})
        iid = self.latest_planned(person_id=pid)
        tomorrow = (TODAY + dt.timedelta(days=1)).isoformat()
        _h, page = self.post(f"/care/visits/{iid}/done", {"done_date": tomorrow, "care_note": "x"}, expect=400)
        self.assertIn("Done date cannot be after today", page)
        self.assertIn(f'id="done-date-{iid}-error"', page)  # next to that Visit's date field
        row = conn.execute("SELECT visit_done FROM calendar_item WHERE id = ?", (iid,)).fetchone()
        self.assertEqual(row["visit_done"], 0)
        # a Visit that is done already cannot be marked done again from the page
        self.post(f"/care/visits/{iid}/done", {"done_date": TODAY.isoformat()})
        _h, page = self.post(f"/care/visits/{iid}/done", {"done_date": TODAY.isoformat()}, expect=400)
        self.assertIn("not a planned Visit", page)

    def test_plan_needs_one_person_or_one_family(self):
        conn = self.db()
        pid = people.list_persons(conn)[0]["id"]
        fid = people.list_families(conn)[0]["id"]
        when = f"{TODAY.isoformat()}T10:00"
        for form in ({"person_id": "", "family_id": ""}, {"person_id": pid, "family_id": fid}):
            _h, page = self.post("/care/visits", {**form, "starts_at": when}, expect=400)
            self.assertIn("one Person or one Family", page)
        _h, page = self.post("/care/visits", {"person_id": pid, "starts_at": "tomorrow"}, expect=400)
        self.assertIn('id="plan-starts-error"', page)
        # a Family Visit
        self.post("/care/visits", {"family_id": fid, "starts_at": when, "note": ""})
        iid = self.latest_planned(family_id=fid)
        self.assertIn(f'href="/families/{fid}"', section(self.page("/care"), "planned"))
        self.assertIn(f"/care/visits/{iid}/done", self.page("/care"))

    def test_care_page_blocks(self):
        page = self.page("/care?person_id=1")
        self.assertEqual(parse_panels(page).h1, 1)
        self.assertIn("No Visit in the last 3 months, or never", section(page, "needs-visit"))
        self.assertIn('<option value="1" selected>', section(page, "plan"))  # "Plan" from a row picks the Person
        self.assertIn('type="datetime-local"', section(page, "plan"))
        self.assertGreaterEqual(parse_panels(page).rows["care-log"], 1)
        self.assertIn("People need a visit", page)  # the finding line


class SmallLogicTest(unittest.TestCase):
    def test_visit_start(self):
        self.assertEqual(care_pages.visit_start("2026-11-03T10:00"), "2026-11-03 10:00")
        self.assertEqual(care_pages.visit_start("2026-11-03T10:00:00"), "2026-11-03 10:00")
        self.assertEqual(care_pages.visit_start("2026-11-03 10:00"), "2026-11-03 10:00")
        for bad in ("", None, "2026-11-03", "2026-02-30T10:00", "03/11/2026 10:00"):
            with self.assertRaises(ValueError) as ctx:
                care_pages.visit_start(bad)
            self.assertTrue(str(ctx.exception).startswith("Date and time"), bad)

    def test_default_start(self):
        self.assertEqual(care_pages.default_start(dt.datetime(2026, 11, 1, 9, 15)), "2026-11-01T10:00")
        self.assertEqual(care_pages.default_start(dt.datetime(2026, 12, 31, 23, 30)), "2027-01-01T00:00")


if __name__ == "__main__":
    unittest.main()
