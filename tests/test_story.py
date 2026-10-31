import unittest

from _support import CopyTestCase
from churchmgr import calendar, care, documents, money, people, story


class PersonStoryTest(CopyTestCase):
    def setUp(self):
        super().setUp()
        c = self.conn
        self.p = people.add_person(c, "Nguyễn Hải Đăng", status_id=self.status("visitor"), start_date="2019-01-06")
        people.set_status(c, self.p, self.status("member"), "2020-03-01")
        self.x = people.add_family(c, "Gia đình Nguyễn")
        self.y = people.add_family(c, "Gia đình Đăng")
        people.set_family(c, self.p, self.x, "Child", "2019-01-06")
        people.set_family(c, self.p, self.x, "Other", "2021-01-01")  # new role, same Family
        people.set_family(c, self.p, self.y, "Head", "2025-06-01")
        cp_a = people.add_chi_phai(c, "Chi phái Hòa Bình")
        cp_b = people.add_chi_phai(c, "Chi phái Đông Hải")
        people.set_family_chi_phai(c, self.x, cp_a, "2018-01-01")
        people.set_family_chi_phai(c, self.y, cp_b, "2024-01-01")
        people.set_truong_chi_phai(c, cp_b, self.p, "2025-07-01")
        people.set_truong_chi_phai(c, cp_b, None, "2026-01-01")
        worship = self.item("ministry", name="Worship")
        people.set_ministry(c, self.p, worship, "Member", "2022-01-01")
        people.set_ministry(c, self.p, worship, "Leader", "2023-01-01")
        sid = calendar.add_calendar_item(c, "Service", "Thờ phượng Chúa Nhật", "2026-02-01 08:00")[0]
        calendar.add_person_to_item(c, sid, self.p, "serves")
        v1 = care.plan_visit(c, "2026-02-10 10:00", person_id=self.p)
        care.mark_visit_done(c, v1, "2026-02-10", "Cầu nguyện chung")
        v2 = care.plan_visit(c, "2020-05-01 10:00", family_id=self.x)  # while he was in Family X
        care.mark_visit_done(c, v2, "2020-05-01")
        care.plan_visit(c, "2026-12-01 10:00", family_id=self.y)  # planned, current Family
        money.add_offering(c, "2026-03-01", 1250000, self.item("fund", name="General"), giver_person_id=self.p)
        documents.add_document(c, self.folder, b"x", "Chứng nhận.txt", person_id=self.p)
        people.add_private_note(c, self.p, "PRIVATE-NOTE-MARKER-1 riêng tư")

    def test_story_is_sorted_and_complete(self):
        events = story.person_story(self.conn, self.p)
        dates = [e["date"] for e in events]
        self.assertEqual(dates, sorted(dates))
        texts = [e["text"] for e in events]
        for want in (
            "Status: Visitor", "Status: Member", "Family: Gia đình Nguyễn (Child)", "Family: Gia đình Nguyễn (Other)",
            "Left Family Gia đình Nguyễn", "Family: Gia đình Đăng (Head)",
            "Chi phái: Chi phái Hòa Bình (Family Gia đình Nguyễn)", "Chi phái: Chi phái Đông Hải (Family Gia đình Đăng)",
            "Trưởng Chi phái of Chi phái Đông Hải", "No longer Trưởng Chi phái of Chi phái Đông Hải",
            "Ministry: Worship (Member)", "Ministry: Worship (Leader)", "Serves at Service: Thờ phượng Chúa Nhật",
            "Visit done: Nguyễn Hải Đăng - Cầu nguyện chung", "Visit done: Gia đình Nguyễn",
            "Visit planned: Gia đình Đăng", "Offering 1.250.000 ₫ to General", "Document: Chứng nhận.txt",
        ):
            self.assertIn(want, texts)
        # A new role in the same Family is not "left the Family"; a role change in a Ministry is not "stopped".
        self.assertEqual(texts.count("Left Family Gia đình Nguyễn"), 1)
        self.assertNotIn("Stopped serving in Ministry Worship", texts)
        left = next(e for e in events if e["text"] == "Left Family Gia đình Nguyễn")
        self.assertEqual(left["date"], "2025-06-01")
        cp = next(e for e in events if e["text"].startswith("Chi phái: Chi phái Hòa Bình"))
        self.assertEqual(cp["date"], "2019-01-06")  # from when he joined the Family, not 2018
        self.assertEqual(sum(t.startswith("Chi phái: Chi phái Hòa Bình") for t in texts), 1)  # one stay

    def test_private_notes_only_when_asked(self):
        def has_note(events):
            return any("PRIVATE-NOTE-MARKER" in e["text"] for e in events)
        self.assertFalse(has_note(story.person_story(self.conn, self.p)))
        self.assertFalse(has_note(story.person_story(self.conn, self.p, include_private="yes")))  # only True
        with_notes = story.person_story(self.conn, self.p, include_private=True)
        self.assertTrue(has_note(with_notes))
        self.assertEqual([e["kind"] for e in with_notes if "MARKER" in e["text"]], ["private_note"])

    def test_unknown_person(self):
        with self.assertRaises(ValueError):
            story.person_story(self.conn, 9999)
        self.assertEqual(story.person_story(self.conn, people.add_person(self.conn, "Lê Văn An")), [])


if __name__ == "__main__":
    unittest.main()
