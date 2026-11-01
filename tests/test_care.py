import unittest

from _support import CopyTestCase
from churchmgr import calendar, care, lists, people, settings, story, text

TODAY = "2026-05-31"  # 3 months back = 2026-02-28 (the day is clamped)


class PlanVisitTest(CopyTestCase):
    def setUp(self):
        super().setUp()
        self.p = people.add_person(self.conn, "Lê Văn An")
        self.f = people.add_family(self.conn, "Gia đình Lê Văn An")

    def test_plan_for_person_or_family(self):
        a = care.plan_visit(self.conn, "2026-05-04 10:00", person_id=self.p, note="Mang Kinh Thánh")
        b = care.plan_visit(self.conn, "2026-05-05 15:00", family_id=self.f, title="Thăm cả nhà")
        ra, rb = calendar.get_calendar_item(self.conn, a), calendar.get_calendar_item(self.conn, b)
        self.assertEqual((ra["kind"], ra["title"], ra["visit_person_id"], ra["visit_family_id"], ra["visit_done"]),
                         ("Visit", "Visit Lê Văn An", self.p, None, 0))
        self.assertEqual((rb["title"], rb["visit_person_id"], rb["visit_family_id"]), ("Thăm cả nhà", None, self.f))

    def test_exactly_one_of_person_or_family(self):
        for kwargs in ({}, {"person_id": self.p, "family_id": self.f}, {"person_id": 999}, {"family_id": 999}):
            with self.assertRaises(ValueError, msg=kwargs):
                care.plan_visit(self.conn, "2026-05-04 10:00", **kwargs)
        with self.assertRaises(ValueError):
            care.plan_visit(self.conn, "2026-05-04", person_id=self.p)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM calendar_item").fetchone()[0], 0)

    def test_mark_done_and_again(self):
        v = care.plan_visit(self.conn, "2026-05-04 10:00", person_id=self.p)
        care.mark_visit_done(self.conn, v, "2026-05-04", "Thăm hỏi sức khỏe")
        row = calendar.get_calendar_item(self.conn, v)
        self.assertEqual((row["visit_done"], row["visit_done_date"], row["care_note"]),
                         (1, "2026-05-04", "Thăm hỏi sức khỏe"))
        care.mark_visit_done(self.conn, v, "2026-05-05")
        self.assertEqual(calendar.get_calendar_item(self.conn, v)["visit_done_date"], "2026-05-05")
        meeting = calendar.add_calendar_item(self.conn, "Meeting", "Họp", "2026-05-03 19:00")[0]
        with self.assertRaisesRegex(ValueError, "Only a Visit"):
            care.mark_visit_done(self.conn, meeting, "2026-05-04")
        with self.assertRaises(ValueError):
            care.mark_visit_done(self.conn, v, "04/05/2026")
        with self.assertRaises(ValueError):
            care.mark_visit_done(self.conn, 9999, "2026-05-04")


class NeedsVisitTest(CopyTestCase):
    def setUp(self):
        super().setUp()
        c = self.conn
        member = self.status("member")

        def person(name, status=member):
            return people.add_person(c, name, status_id=status, start_date="2020-01-01") if status else \
                people.add_person(c, name)

        def visit(done, person_id=None, family_id=None, note=None):
            iid = care.plan_visit(c, f"{done} 10:00", person_id=person_id, family_id=family_id)
            care.mark_visit_done(c, iid, done, note)
            return iid

        self.an = person("An Lê")              # Person visit 2026-04-01 -> no
        self.binh = person("Bình Lê")          # Family visit 2026-05-01 -> no
        self.cuong = person("Cường Lê")        # Person visit 2026-01-15 -> yes
        self.dung = person("Dũng Lê", None)    # no Status, never -> yes
        self.ha = person("Hà Lê", self.status("left"))
        self.lan = person("Lan Lê", self.status("passed_away"))
        self.mai = person("Mai Lê")            # old Family visited 2026-02-10 while she was in it -> yes
        self.nam = person("Nam Lê")            # visit exactly on the cut-off day -> no
        self.phuc = person("Phúc Lê")          # visit one day before the cut-off -> yes
        self.quan = person("Quân Lê", self.status("attender"))  # only a planned Visit -> yes
        custom = lists.add_item(c, "status", "Khách mời")  # a new Status with no code is included
        self.khach = person("Khánh Lê", custom)
        self.f1 = people.add_family(c, "Gia đình Bình")
        self.f2 = people.add_family(c, "Gia đình cũ")
        self.f3 = people.add_family(c, "Gia đình mới")
        people.set_family(c, self.binh, self.f1, "Head", "2020-01-01")
        people.set_family(c, self.mai, self.f2, "Child", "2020-01-01")
        people.set_family(c, self.mai, self.f3, "Spouse", "2026-03-01")
        visit("2026-04-01", person_id=self.an, note="Thăm hỏi")
        visit("2026-05-01", family_id=self.f1, note="Thăm cả nhà")
        visit("2026-01-15", person_id=self.cuong)
        visit("2026-02-10", family_id=self.f2)
        visit("2026-02-28", person_id=self.nam)
        visit("2026-02-27", person_id=self.phuc)
        visit("2025-01-01", person_id=self.ha)
        care.plan_visit(c, "2026-06-02 10:00", person_id=self.quan)

    def names(self, rows):
        return [r["full_name"] for r in rows]

    def test_needs_visit_default_three_months(self):
        rows = care.needs_visit(self.conn, today=TODAY)
        never = [r for r in rows if r["last_visit"] is None]
        dated = [r for r in rows if r["last_visit"] is not None]
        self.assertEqual(rows[: len(never)], never)  # never visited comes first
        self.assertEqual(set(self.names(never)), {"Dũng Lê", "Quân Lê", "Khánh Lê"})
        # Mai: the Visit to the Family she was in on that day counts (B20: past Families too)
        self.assertEqual([(r["full_name"], r["last_visit"]) for r in dated],
                         [("Cường Lê", "2026-01-15"), ("Mai Lê", "2026-02-10"), ("Phúc Lê", "2026-02-27")])
        for name in ("An Lê", "Bình Lê", "Nam Lê", "Hà Lê", "Lan Lê"):
            self.assertNotIn(name, self.names(rows))
        self.assertEqual(next(r for r in rows if r["full_name"] == "Mai Lê")["family_name"], "Gia đình mới")

    def test_setting_changes_the_time(self):
        settings.set_setting(self.conn, "care_reminder_months", 6)
        self.assertEqual(set(self.names(care.needs_visit(self.conn, today=TODAY))),
                         {"Dũng Lê", "Quân Lê", "Khánh Lê"})
        settings.set_setting(self.conn, "care_reminder_months", 1)  # cut-off 2026-04-30
        names = self.names(care.needs_visit(self.conn, today=TODAY))
        self.assertIn("An Lê", names)
        self.assertNotIn("Bình Lê", names)
        self.assertEqual(care.reminder_months(self.conn), 1)

    def test_family_visit_counts_only_for_people_in_the_family_that_day(self):
        # B20: Bé joined Gia đình Bình on 2026-05-20, after its Visit of 2026-05-01: not her Visit
        child = people.add_person(self.conn, "Bé Lê", status_id=self.status("member"), start_date="2026-05-20")
        people.set_family(self.conn, child, self.f1, "Child", "2026-05-20")
        rows = care.needs_visit(self.conn, today=TODAY)
        self.assertEqual(next(r for r in rows if r["full_name"] == "Bé Lê")["last_visit"], None)
        self.assertNotIn("Bình Lê", self.names(rows))  # in the Family since before the Visit: it counts

    def test_today_default_runs(self):
        self.assertIsInstance(care.needs_visit(self.conn), list)

    def test_care_log_newest_first_and_for_one_person(self):
        log = care.care_log(self.conn)
        self.assertEqual([r["done_date"] for r in log],
                         ["2026-05-01", "2026-04-01", "2026-02-28", "2026-02-27", "2026-02-10", "2026-01-15",
                          "2025-01-01"])
        self.assertEqual((log[0]["who"], log[0]["care_note"]), ("Gia đình Bình", "Thăm cả nhà"))
        self.assertEqual([r["who"] for r in care.care_log(self.conn, self.binh)], ["Gia đình Bình"])
        # Mai's log keeps the visit to the Family she was in on that day.
        self.assertEqual([r["who"] for r in care.care_log(self.conn, self.mai)], ["Gia đình cũ"])
        self.assertEqual(care.care_log(self.conn, self.quan), [])  # planned only


class LongNameVisitTest(CopyTestCase):
    """B14: Plan a Visit for a Person or Family with a long name (Care has no Title field)."""

    def test_default_title_is_cut_to_the_name_limit(self):
        for size in (114, 115, 116, 120):
            name = ("Trần Thị Hồng " * 9)[: size - 1] + "Z"
            self.assertEqual(len(name), size)
            pid = people.add_person(self.conn, name)
            title = calendar.get_calendar_item(self.conn, care.plan_visit(self.conn, "2026-05-04 10:00",
                                                                          person_id=pid))["title"]
            self.assertLessEqual(len(title), text.MAX_NAME_LENGTH, size)
            if size == 114:
                self.assertEqual(title, f"Visit {name}")  # 6 + 114 = 120: fits, not cut
            else:
                self.assertEqual(title, f"Visit {name}"[: text.MAX_NAME_LENGTH - 1].rstrip() + "…", size)
        name = ("Gia đình Trần Văn Long " * 6)[:119] + "Z"
        family = people.add_family(self.conn, name)
        self.assertEqual(len(people.get_family(self.conn, family)["name"]), 120)
        title = calendar.get_calendar_item(self.conn, care.plan_visit(self.conn, "2026-05-05 15:00",
                                                                      family_id=family))["title"]
        self.assertEqual((len(title), title[-1]), (120, "…"))
        self.assertTrue(title.startswith("Visit Gia đình Trần Văn Long"))

    def test_a_given_title_is_not_cut(self):
        pid = people.add_person(self.conn, "Lê Văn An")
        with self.assertRaisesRegex(ValueError, "Title: use at most 120 characters"):
            care.plan_visit(self.conn, "2026-05-04 10:00", person_id=pid, title="T" * 121)
        iid = care.plan_visit(self.conn, "2026-05-04 10:00", person_id=pid, title="T" * 120)
        self.assertEqual(calendar.get_calendar_item(self.conn, iid)["title"], "T" * 120)


class FamilyVisitDayTest(CopyTestCase):
    """B20: a Family Visit counts for a Person only when the Person was in that Family on its day."""

    def setUp(self):
        super().setUp()
        c, member = self.conn, self.status("member")
        self.f = people.add_family(c, "Gia đình Phạm")
        self.new = people.add_person(c, "Phạm Văn Mới", status_id=member, start_date="2025-01-01")
        self.old = people.add_person(c, "Phạm Thị Cũ", status_id=member, start_date="2025-01-01")
        self.gone = people.add_person(c, "Phạm Văn Đi", status_id=member, start_date="2025-01-01")
        people.set_family(c, self.old, self.f, "Head", "2025-01-01")      # in F before the Visit
        people.set_family(c, self.gone, self.f, "Child", "2025-01-01")
        people.set_family(c, self.gone, None, None, "2026-06-01")          # left F after the Visit
        people.set_family(c, self.new, self.f, "Spouse", "2026-09-01")     # joined F after the Visit
        self.visit = care.plan_visit(c, "2026-01-01 10:00", family_id=self.f)
        care.mark_visit_done(c, self.visit, "2026-01-01", "Thăm cả nhà")
        care.plan_visit(c, "2026-08-01 10:00", family_id=self.f)          # planned, before he joined
        self.later = care.plan_visit(c, "2026-12-01 10:00", family_id=self.f)  # planned, he is in F then

    def visits(self, pid):
        return [(e["ref_id"], e["done"]) for e in story.person_story(self.conn, pid) if e["kind"] == "visit"]

    def test_joined_after_the_visit(self):
        self.assertEqual(care.care_log(self.conn, self.new), [])
        row = next(r for r in care.needs_visit(self.conn, today="2026-11-01") if r["person_id"] == self.new)
        self.assertEqual((row["last_visit"], row["family_name"]), (None, "Gia đình Phạm"))
        self.assertEqual(self.visits(self.new), [(self.later, False)])  # not the done Visit, not the 08-01 one
        # the past link is untouched
        self.assertEqual([(r["start_date"], r["end_date"]) for r in people.family_history(self.conn, self.new)],
                         [("2026-09-01", None)])

    def test_in_the_family_on_the_day_keeps_the_visit(self):
        for pid in (self.old, self.gone):
            self.assertEqual([r["id"] for r in care.care_log(self.conn, pid)], [self.visit], pid)
            row = next(r for r in care.needs_visit(self.conn, today="2026-11-01") if r["person_id"] == pid)
            self.assertEqual(row["last_visit"], "2026-01-01", pid)  # older than 3 months: still needs one
            self.assertIn((self.visit, True), self.visits(pid))
        self.assertNotIn(self.gone, [r["person_id"] for r in care.needs_visit(self.conn, today="2026-03-01")])


if __name__ == "__main__":
    unittest.main()
