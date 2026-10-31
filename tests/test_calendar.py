import datetime as dt
import sqlite3
import unittest

from _support import CopyTestCase
from churchmgr import calendar, care, documents, people


class MonthMathTest(unittest.TestCase):
    def test_add_months_clamps_day(self):
        d = dt.date
        cases = [
            (d(2026, 1, 31), 1, d(2026, 2, 28)),
            (d(2028, 1, 31), 1, d(2028, 2, 29)),
            (d(2026, 5, 31), -3, d(2026, 2, 28)),
            (d(2026, 3, 31), -3, d(2025, 12, 31)),
            (d(2026, 1, 15), -1, d(2025, 12, 15)),
            (d(2026, 12, 31), 2, d(2027, 2, 28)),
            (d(2026, 8, 31), -6, d(2026, 2, 28)),
        ]
        for start, months, want in cases:
            self.assertEqual(calendar.add_months(start, months), want, (start, months))

    def test_check_year(self):
        self.assertEqual(calendar.check_year(2026), 2026)
        self.assertEqual(calendar.check_year(" 2027 "), 2027)
        for bad in (True, 1899, 10000, "20x6", 2026.0, None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                calendar.check_year(bad)


class RepeatTest(CopyTestCase):
    def test_no_repeat_gives_one_row_without_series(self):
        ids = calendar.add_calendar_item(self.conn, "Meeting", "Họp", "2026-05-03 19:00")
        self.assertEqual(len(ids), 1)
        self.assertIsNone(calendar.get_calendar_item(self.conn, ids[0])["series_id"])

    def test_weekly_count_times_and_series(self):
        ids = calendar.add_calendar_item(
            self.conn, "Service", "Thờ phượng Chúa Nhật", "2026-01-04 08:00", ends_at="2026-01-04 10:00",
            place="Nhà thờ", repeat="weekly", repeat_until="2026-03-29",
        )
        self.assertEqual(len(ids), 13)  # 4 Jan .. 29 Mar, both included
        rows = calendar.series_items(self.conn, ids[0])
        self.assertEqual([r["id"] for r in rows], ids)
        self.assertEqual({r["series_id"] for r in rows}, {ids[0]})
        self.assertEqual(rows[0]["starts_at"], "2026-01-04 08:00")
        self.assertEqual(rows[-1]["starts_at"], "2026-03-29 08:00")
        self.assertEqual(rows[-1]["ends_at"], "2026-03-29 10:00")
        self.assertEqual({r["place"] for r in rows}, {"Nhà thờ"})
        self.assertEqual(
            len(calendar.add_calendar_item(self.conn, "Meeting", "x", "2026-01-04 08:00", repeat="weekly",
                                           repeat_until="2026-03-28")), 12)

    def test_monthly_clamps_to_month_end_and_comes_back(self):
        ids = calendar.add_calendar_item(self.conn, "Meeting", "Họp Trưởng Chi phái", "2026-01-31 19:30",
                                         repeat="monthly", repeat_until="2026-06-30")
        starts = [calendar.get_calendar_item(self.conn, i)["starts_at"] for i in ids]
        self.assertEqual(starts, ["2026-01-31 19:30", "2026-02-28 19:30", "2026-03-31 19:30",
                                  "2026-04-30 19:30", "2026-05-31 19:30", "2026-06-30 19:30"])
        leap = calendar.add_calendar_item(self.conn, "Event", "x", "2028-01-31 10:00", repeat="monthly",
                                          repeat_until="2028-03-01")
        self.assertEqual([calendar.get_calendar_item(self.conn, i)["starts_at"][:10] for i in leap],
                         ["2028-01-31", "2028-02-29"])

    def test_max_104_rows(self):
        ids = calendar.add_calendar_item(self.conn, "Service", "s", "2026-01-01 08:00", repeat="weekly",
                                         repeat_until="2027-12-23")
        self.assertEqual(len(ids), 104)
        before = self.conn.execute("SELECT COUNT(*) FROM calendar_item").fetchone()[0]
        with self.assertRaisesRegex(ValueError, "104"):
            calendar.add_calendar_item(self.conn, "Service", "s", "2026-01-01 08:00", repeat="weekly",
                                       repeat_until="2027-12-30")
        with self.assertRaisesRegex(ValueError, "104"):
            calendar.add_calendar_item(self.conn, "Meeting", "m", "2026-01-01 08:00", repeat="monthly",
                                       repeat_until="2099-01-01")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM calendar_item").fetchone()[0], before)

    def test_bad_repeat_input_refused(self):
        bad = [
            dict(repeat="weekly"),  # no end date
            dict(repeat="daily", repeat_until="2026-02-01"),
            dict(repeat="weekly", repeat_until="2025-12-31"),  # before the start
            dict(repeat="none", repeat_until="2026-02-01"),
            dict(repeat="weekly", repeat_until="01/02/2026"),
        ]
        for kwargs in bad:
            with self.assertRaises(ValueError, msg=kwargs):
                calendar.add_calendar_item(self.conn, "Meeting", "m", "2026-01-01 08:00", **kwargs)
        for kwargs in (dict(kind="Party"), dict(title="  "), dict(starts_at="2026-01-01"),
                       dict(ends_at="2025-12-31 08:00"), dict(kind="Visit")):
            args = dict(kind="Meeting", title="m", starts_at="2026-01-01 08:00")
            args.update(kwargs)
            with self.assertRaises(ValueError, msg=kwargs):
                calendar.add_calendar_item(self.conn, **args)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM calendar_item").fetchone()[0], 0)

    def test_text_is_nfc(self):
        nfd = "Tho\u031b\u0300 phu\u031bo\u031b\u0323ng"  # "Thờ phượng" in NFD
        iid = calendar.add_calendar_item(self.conn, "Service", nfd, "2026-01-04 08:00", place=nfd)[0]
        row = calendar.get_calendar_item(self.conn, iid)
        self.assertEqual((row["title"], row["place"]), ("Thờ phượng", "Thờ phượng"))


class ItemTest(CopyTestCase):
    def setUp(self):
        super().setUp()
        self.a = people.add_person(self.conn, "Lê Văn An")
        self.b = people.add_person(self.conn, "Trần Thị Bình")

    def service(self, when="2026-05-03 08:00"):
        return calendar.add_calendar_item(self.conn, "Service", "Thờ phượng Chúa Nhật", when)[0]

    def test_head_count_only_on_service(self):
        meeting = calendar.add_calendar_item(self.conn, "Meeting", "Họp", "2026-05-03 19:00")[0]
        event = calendar.add_calendar_item(self.conn, "Event", "Tiệc", "2026-05-03 19:00")[0]
        visit = care.plan_visit(self.conn, "2026-05-04 10:00", person_id=self.a)
        for iid in (meeting, event, visit):
            with self.assertRaisesRegex(ValueError, "only for a Service"):
                calendar.set_head_count(self.conn, iid, 10)
        sid = self.service()
        calendar.set_head_count(self.conn, sid, 80, "Gia đình Lê đi vắng")
        calendar.set_head_count(self.conn, sid, 82)  # replaces
        rows = self.conn.execute("SELECT count, absent_note FROM head_count").fetchall()
        self.assertEqual([tuple(r) for r in rows], [(82, None)])
        calendar.set_head_count(self.conn, sid, 0)
        self.assertEqual(calendar.get_head_count(self.conn, sid)["count"], 0)
        for bad in (-1, 1.5, True, "12", None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                calendar.set_head_count(self.conn, sid, bad)
        self.assertEqual(calendar.get_head_count(self.conn, sid)["count"], 0)
        with self.assertRaises(ValueError):
            calendar.set_head_count(self.conn, 9999, 5)

    def test_recent_head_counts_newest_last_past_only(self):
        ids = calendar.add_calendar_item(self.conn, "Service", "s", "2026-01-04 08:00", repeat="weekly",
                                         repeat_until="2026-03-29")
        for k, iid in enumerate(ids):
            if k != 3:  # one Service without a Head count
                calendar.set_head_count(self.conn, iid, 50 + k)
        rows = calendar.recent_head_counts(self.conn, n=8, now="2026-03-15 12:00")
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[-1]["starts_at"], "2026-03-15 08:00")  # newest last
        self.assertEqual([r["count"] for r in rows], [52, 54, 55, 56, 57, 58, 59, 60])
        self.assertNotIn("2026-03-22 08:00", [r["starts_at"] for r in rows])  # future
        self.assertNotIn("2026-01-25 08:00", [r["starts_at"] for r in rows])  # no Head count
        self.assertEqual(len(calendar.recent_head_counts(self.conn, n=50, now="2026-03-15 12:00")), 10)
        self.assertEqual(calendar.recent_head_counts(self.conn, now="2025-01-01 00:00"), [])
        with self.assertRaises(ValueError):
            calendar.recent_head_counts(self.conn, n=0)

    def test_delete_refused_for_history(self):
        sid = self.service()
        calendar.set_head_count(self.conn, sid, 40)
        with self.assertRaisesRegex(ValueError, "Head count"):
            calendar.delete_calendar_item(self.conn, sid)
        event = calendar.add_calendar_item(self.conn, "Event", "Tiệc", "2026-05-03 19:00")[0]
        documents.add_document(self.conn, self.folder, b"plan", "plan.txt", calendar_item_id=event)
        with self.assertRaisesRegex(ValueError, "Document"):
            calendar.delete_calendar_item(self.conn, event)
        visit = care.plan_visit(self.conn, "2026-05-04 10:00", person_id=self.a)
        care.mark_visit_done(self.conn, visit, "2026-05-04")
        with self.assertRaisesRegex(ValueError, "done"):
            calendar.delete_calendar_item(self.conn, visit)
        for iid in (sid, event, visit):
            self.assertIsNotNone(calendar.get_calendar_item(self.conn, iid))

    def test_delete_plain_item_removes_its_people(self):
        meeting = calendar.add_calendar_item(self.conn, "Meeting", "Họp", "2026-05-03 19:00")[0]
        calendar.add_person_to_item(self.conn, meeting, self.a, "joins")
        planned = care.plan_visit(self.conn, "2026-05-04 10:00", family_id=people.add_family(self.conn, "Gia đình Lê"))
        calendar.delete_calendar_item(self.conn, meeting)
        calendar.delete_calendar_item(self.conn, planned)  # a Visit not done yet can go
        self.assertIsNone(calendar.get_calendar_item(self.conn, meeting))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM calendar_person").fetchone()[0], 0)

    def test_people_on_an_item(self):
        sid = self.service()
        self.assertTrue(calendar.add_person_to_item(self.conn, sid, self.b, "joins"))
        self.assertTrue(calendar.add_person_to_item(self.conn, sid, self.a, "serves"))
        self.assertTrue(calendar.add_person_to_item(self.conn, sid, self.a, "joins"))
        self.assertFalse(calendar.add_person_to_item(self.conn, sid, self.a, "joins"))  # already there
        self.assertEqual([(r["full_name"], r["part"]) for r in calendar.item_people(self.conn, sid)],
                         [("Lê Văn An", "serves"), ("Lê Văn An", "joins"), ("Trần Thị Bình", "joins")])
        for bad in (dict(part="leads"), dict(person_id=9999)):
            args = dict(item_id=sid, person_id=self.a, part="joins")
            args.update(bad)
            with self.assertRaises(ValueError, msg=bad):
                calendar.add_person_to_item(self.conn, **args)
        self.assertEqual(calendar.remove_person_from_item(self.conn, sid, self.a, "serves"), 1)
        self.assertEqual(calendar.remove_person_from_item(self.conn, sid, self.b), 1)
        self.assertEqual([(r["full_name"], r["part"]) for r in calendar.item_people(self.conn, sid)],
                         [("Lê Văn An", "joins")])

    def test_items_between_order_and_bounds(self):
        late = calendar.add_calendar_item(self.conn, "Meeting", "late", "2026-05-09 23:59")[0]
        early = calendar.add_calendar_item(self.conn, "Event", "early", "2026-05-03 00:00")[0]
        mid = self.service("2026-05-05 08:00")
        calendar.add_calendar_item(self.conn, "Event", "before", "2026-05-02 23:59")
        calendar.add_calendar_item(self.conn, "Event", "after", "2026-05-10 00:00")
        calendar.set_head_count(self.conn, mid, 70)
        visit = care.plan_visit(self.conn, "2026-05-06 10:00", person_id=self.a)
        rows = calendar.items_between(self.conn, "2026-05-03", "2026-05-09")
        self.assertEqual([r["id"] for r in rows], [early, mid, visit, late])
        self.assertEqual(rows[1]["head_count"], 70)
        self.assertEqual(rows[2]["visit_name"], "Lê Văn An")
        self.assertEqual(rows[2]["title"], "Visit Lê Văn An")
        with self.assertRaises(ValueError):
            calendar.items_between(self.conn, "2026-05-09", "2026-05-03")

    def test_update_item(self):
        ids = calendar.add_calendar_item(self.conn, "Meeting", "Họp", "2026-05-03 19:00",
                                         ends_at="2026-05-03 21:00", repeat="weekly", repeat_until="2026-05-17")
        calendar.update_calendar_item(self.conn, ids[1], title="Họp đặc biệt", starts_at="2026-05-11 18:00",
                                      ends_at=None, place="Phòng 2")
        row = calendar.get_calendar_item(self.conn, ids[1])
        self.assertEqual((row["title"], row["starts_at"], row["ends_at"], row["place"]),
                         ("Họp đặc biệt", "2026-05-11 18:00", None, "Phòng 2"))
        self.assertEqual(calendar.get_calendar_item(self.conn, ids[2])["title"], "Họp")  # only one row
        with self.assertRaises(ValueError):
            calendar.update_calendar_item(self.conn, ids[0], ends_at="2026-05-03 18:00")
        with self.assertRaises(ValueError):
            calendar.update_calendar_item(self.conn, ids[0], kind="Visit")
        calendar.update_calendar_item(self.conn, ids[0], kind="Event")
        self.assertEqual(calendar.get_calendar_item(self.conn, ids[0])["kind"], "Event")
        sid = self.service()
        calendar.set_head_count(self.conn, sid, 10)
        with self.assertRaisesRegex(ValueError, "Head count"):
            calendar.update_calendar_item(self.conn, sid, kind="Meeting")
        visit = care.plan_visit(self.conn, "2026-05-04 10:00", person_id=self.a)
        with self.assertRaises(ValueError):
            calendar.update_calendar_item(self.conn, visit, kind="Meeting")
        calendar.update_calendar_item(self.conn, visit, place="Nhà riêng")
        self.assertEqual(calendar.get_calendar_item(self.conn, visit)["place"], "Nhà riêng")

    def test_db_still_refuses_visit_fields_on_a_service(self):
        sid = self.service()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE calendar_item SET visit_person_id = ? WHERE id = ?", (self.a, sid))


if __name__ == "__main__":
    unittest.main()
