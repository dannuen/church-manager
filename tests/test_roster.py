"""roster.py (card RO-2, decision D4): Service roles, Rotations, Skipped dates, Service role links with
history (rule 4), the same-person rule, and the Calendar rules that keep a Service on the Roster."""

import unittest

import _support  # noqa: F401  (puts the repo on sys.path)
from _support import CopyTestCase
from churchmgr import calendar, documents, i18n, people, roster, settings, text
from churchmgr.i18n import TextError

SUNDAY = "2026-05-03"  # a Sunday
THURSDAY = "2026-04-30"  # the Thursday of the same ISO week
MONDAY = "2026-05-04"  # the Monday after: the next ISO week


class RosterCase(CopyTestCase):
    def setUp(self):
        super().setUp()
        self.p1 = people.add_person(self.conn, "Lê Văn An")
        self.p2 = people.add_person(self.conn, "Trần Thị Bình")
        self.p3 = people.add_person(self.conn, "Phạm Văn Cường")
        by_name = {r["name"]: r["id"] for r in roster.roles(self.conn)}
        self.boi_linh = by_name["Bồi linh"]
        self.leader = by_name["Service leader"]
        self.offering = by_name["Offering leader"]
        self.in_charge = by_name["Ministry in charge"]
        self.worship = self.item("ministry", name="Worship")
        self.youth = self.item("ministry", name="Youth")
        self.fund = self.item("fund", name="General")
        self.sunday = self.service(f"{SUNDAY} 08:00")
        self.thursday = self.service(f"{THURSDAY} 19:30")

    def service(self, starts_at, kind="Service"):
        return calendar.add_calendar_item(self.conn, kind, "Thờ phượng", starts_at)[0]

    def refused(self, key, fn, *args, **kwargs):
        with self.assertRaises(TextError) as ctx:
            fn(self.conn, *args, **kwargs)
        self.assertEqual(ctx.exception.key, key, str(ctx.exception))
        self.assertNotIn("[[", i18n.error_text(ctx.exception, "vi"))
        return ctx.exception

    def links(self):
        return [tuple(r) for r in self.conn.execute(
            "SELECT calendar_item_id, service_role_id, person_id, ministry_id, start_date, end_date "
            "FROM service_role_link ORDER BY id")]


class RoleTest(RosterCase):
    def test_constants(self):
        self.assertEqual((roster.DONE_BY, roster.SAME_PERSON_RULES, roster.SAME_PERSON_SETTING,
                          roster.SAME_PERSON_DEFAULT, roster.MAX_FILL_DAYS),
                         (("person", "ministry"), ("service", "week", "any"), "roster_same_person", "service", 366))

    def test_roles_by_weekday_then_sort_order(self):
        self.assertEqual([r["name"] for r in roster.roles(self.conn)],
                         ["Bồi linh", "Service leader", "Offering leader", "Ministry in charge"])
        monday = roster.add_role(self.conn, "Cầu nguyện", 0, "person")
        sunday = roster.add_role(self.conn, "Đọc Kinh Thánh", 6, "person")
        self.assertEqual([r["id"] for r in roster.roles(self.conn)],
                         [monday, self.boi_linh, self.leader, self.offering, self.in_charge, sunday])

    def test_add_role(self):
        rid = roster.add_role(self.conn, "  Đọc   Kinh Thánh ", 6, "person")
        row = roster.get_role(self.conn, rid)
        self.assertEqual((row["name"], row["weekday"], row["done_by"], row["every"], row["month_start"],
                          row["month_start_from"], row["sort_order"], row["active"]),
                         ("Đọc Kinh Thánh", 6, "person", 1, 0, None, 5, 1))
        rid = roster.add_role(self.conn, "Ban hát", "3", "ministry", every="2", month_start=True,
                              month_start_from=" 2026-01 ")
        row = roster.get_role(self.conn, rid)
        self.assertEqual((row["weekday"], row["done_by"], row["every"], row["month_start"], row["month_start_from"],
                          row["sort_order"]), (3, "ministry", 2, 1, "2026-01", 6))

    def test_add_role_refusals(self):
        add = roster.add_role
        self.refused("errors.required", add, "  ", 6, "person")
        self.refused("calendar.roster_err_name_taken", add, "service LEADER", 6, "person")
        for bad in (7, -1, "x", True, 1.5, None, "６"):
            with self.subTest(weekday=bad):
                self.refused("calendar.roster_err_weekday", add, "X", bad, "person")
        self.refused("calendar.roster_err_done_by", add, "X", 6, "family")
        for bad in (0, 9, "0", 2.0):
            with self.subTest(every=bad):
                self.refused("calendar.roster_err_every", add, "X", 6, "person", every=bad)
        e = self.refused("calendar.roster_err_on_off", add, "X", 6, "person", month_start="yes")
        self.assertEqual(str(e), "The first Service of a month starts a round must be on or off.")
        for bad, key in (("2026-13", "calendar.err_month_form"), ("2026-1", "calendar.err_month_form"),
                         ("2026-01-01", "calendar.err_month_form"), (202601, "calendar.err_month_form"),
                         ("1899-12", "calendar.err_month_years")):
            with self.subTest(month=bad):
                self.refused(key, add, "X", 6, "person", month_start_from=bad)
        self.assertEqual(len(roster.roles(self.conn, include_hidden=True)), 4)  # nothing added

    def test_update_role(self):
        roster.update_role(self.conn, self.leader, name="MC", every=2, month_start=False, month_start_from="2026-03")
        row = roster.get_role(self.conn, self.leader)
        self.assertEqual((row["name"], row["weekday"], row["done_by"], row["every"], row["month_start"],
                          row["month_start_from"]), ("MC", 6, "person", 2, 0, "2026-03"))
        roster.update_role(self.conn, self.leader, name="mc", month_start_from=None, weekday="5")
        row = roster.get_role(self.conn, self.leader)
        self.assertEqual((row["name"], row["weekday"], row["month_start_from"]), ("mc", 5, None))
        roster.update_role(self.conn, self.leader)  # nothing to change
        with self.assertRaises(TypeError):  # done_by never changes
            roster.update_role(self.conn, self.leader, done_by="ministry")

    def test_update_role_refusals(self):
        self.refused("calendar.roster_err_no_role", roster.update_role, 999, name="X")
        self.refused("errors.above_zero", roster.update_role, 0, name="X")
        self.refused("calendar.roster_err_name_taken", roster.update_role, self.leader, name="offering leader")
        self.refused("calendar.roster_err_weekday", roster.update_role, self.leader, weekday=7)
        self.refused("calendar.roster_err_every", roster.update_role, self.leader, every=9)
        self.refused("calendar.roster_err_on_off", roster.update_role, self.leader, month_start=2)
        self.refused("calendar.err_month_form", roster.update_role, self.leader, month_start_from="03/2026")
        roster.set_link(self.conn, self.sunday, self.leader, self.p1, day="2026-04-20")
        roster.clear_link(self.conn, self.sunday, self.leader, day="2026-04-21")  # a closed link counts too
        self.refused("calendar.roster_err_weekday_kept", roster.update_role, self.leader, weekday=5)
        roster.update_role(self.conn, self.leader, weekday=6, name="Service leader 2")  # the same weekday: fine
        row = roster.get_role(self.conn, self.leader)
        self.assertEqual((row["name"], row["weekday"], row["every"]), ("Service leader 2", 6, 1))

    def test_hide_show_and_get_role(self):
        roster.set_role_active(self.conn, self.offering, False)
        self.assertNotIn(self.offering, [r["id"] for r in roster.roles(self.conn)])
        self.assertIn(self.offering, [r["id"] for r in roster.roles(self.conn, include_hidden=True)])
        self.assertEqual(roster.get_role(self.conn, self.offering)["active"], 0)
        roster.set_role_active(self.conn, self.offering, 1)
        self.assertIn(self.offering, [r["id"] for r in roster.roles(self.conn)])
        self.refused("calendar.roster_err_on_off", roster.set_role_active, self.offering, "no")
        self.refused("calendar.roster_err_no_role", roster.set_role_active, 999, False)
        self.assertIsNone(roster.get_role(self.conn, 999))
        self.refused("errors.whole_number", roster.get_role, "x")


class RotationTest(RosterCase):
    def test_set_and_replace_a_rotation(self):
        self.assertEqual(roster.rotation(self.conn, self.leader), [])
        roster.set_rotation(self.conn, self.leader, [self.p3, str(self.p1), self.p2])
        self.assertEqual([tuple(r) for r in roster.rotation(self.conn, self.leader)],
                         [(1, self.p3, None, "Phạm Văn Cường"), (2, self.p1, None, "Lê Văn An"),
                          (3, self.p2, None, "Trần Thị Bình")])
        roster.set_rotation(self.conn, self.leader, [self.p2])
        self.assertEqual([tuple(r) for r in roster.rotation(self.conn, self.leader)],
                         [(1, self.p2, None, "Trần Thị Bình")])
        roster.set_rotation(self.conn, self.leader, [])
        self.assertEqual(roster.rotation(self.conn, self.leader), [])

    def test_ministry_rotation(self):
        roster.set_rotation(self.conn, self.in_charge, (self.youth, self.worship))
        self.assertEqual([tuple(r) for r in roster.rotation(self.conn, self.in_charge)],
                         [(1, None, self.youth, "Youth"), (2, None, self.worship, "Worship")])

    def test_refusals_keep_the_old_rotation(self):
        roster.set_rotation(self.conn, self.leader, [self.p1, self.p2])
        self.refused("calendar.roster_err_twice", roster.set_rotation, self.leader, [self.p3, self.p1, self.p3])
        self.refused("calendar.err_no_person", roster.set_rotation, self.leader, [self.p3, 999])
        self.refused("errors.whole_number", roster.set_rotation, self.leader, [None])
        self.refused("calendar.roster_err_no_ministry", roster.set_rotation, self.in_charge, [self.fund])
        self.refused("calendar.roster_err_no_ministry", roster.set_rotation, self.in_charge, [999])
        self.refused("calendar.roster_err_no_role", roster.set_rotation, 999, [self.p1])
        with self.assertRaises(TypeError):
            roster.set_rotation(self.conn, self.leader, "12")
        self.assertEqual([r["person_id"] for r in roster.rotation(self.conn, self.leader)], [self.p1, self.p2])
        self.assertEqual(roster.rotation(self.conn, self.in_charge), [])


class SkippedDateTest(RosterCase):
    def test_add_replace_read_and_remove(self):
        roster.add_skipped_date(self.conn, "2026-02-17", " Tết ")
        roster.add_skipped_date(self.conn, SUNDAY, "Hội đồng bồi linh")
        self.assertEqual(roster.skipped_reason(self.conn, "2026-02-17"), "Tết")
        roster.add_skipped_date(self.conn, "2026-02-17", "Nghỉ Tết")  # the new reason replaces
        self.assertEqual(roster.skipped_reason(self.conn, "2026-02-17"), "Nghỉ Tết")
        self.assertIsNone(roster.skipped_reason(self.conn, "2026-02-18"))
        self.assertEqual([tuple(r) for r in roster.skipped_dates(self.conn, "2026-01-01", "2026-12-31")],
                         [("2026-02-17", "Nghỉ Tết"), (SUNDAY, "Hội đồng bồi linh")])
        self.assertEqual([tuple(r) for r in roster.skipped_dates(self.conn, SUNDAY, SUNDAY)],
                         [(SUNDAY, "Hội đồng bồi linh")])  # both ends included
        self.assertEqual(roster.skipped_dates(self.conn, "2026-02-18", "2026-05-02"), [])
        self.assertTrue(roster.remove_skipped_date(self.conn, "2026-02-17"))
        self.assertFalse(roster.remove_skipped_date(self.conn, "2026-02-17"))
        self.assertIsNone(roster.skipped_reason(self.conn, "2026-02-17"))

    def test_refusals(self):
        self.refused("errors.date", roster.add_skipped_date, "17/02/2026", "Tết")
        self.refused("errors.required", roster.add_skipped_date, "2026-02-17", "  ")
        self.refused("errors.date", roster.remove_skipped_date, "2026-02-30")
        self.refused("errors.date", roster.skipped_reason, None)
        self.refused("calendar.err_end_date_before", roster.skipped_dates, "2026-02-17", "2026-02-16")
        self.assertEqual(roster.skipped_dates(self.conn, "1900-01-01", "9999-12-31"), [])


class LinkTest(RosterCase):
    def test_a_swap_keeps_the_old_row_with_its_dates(self):
        self.assertIsNone(roster.open_value(self.conn, self.sunday, self.leader))
        self.assertTrue(roster.set_link(self.conn, self.sunday, self.leader, self.p1, day="2026-04-20"))
        self.assertFalse(roster.set_link(self.conn, self.sunday, self.leader, str(self.p1), day="2026-04-25"))
        self.assertTrue(roster.set_link(self.conn, self.sunday, self.leader, self.p2, day="2026-04-27"))
        self.assertEqual(self.links(), [(self.sunday, self.leader, self.p1, None, "2026-04-20", "2026-04-27"),
                                        (self.sunday, self.leader, self.p2, None, "2026-04-27", None)])
        held = roster.open_value(self.conn, self.sunday, self.leader)
        self.assertEqual((held["person_id"], held["ministry_id"], held["name"], held["start_date"]),
                         (self.p2, None, "Trần Thị Bình", "2026-04-27"))
        self.assertTrue(roster.set_link(self.conn, self.sunday, self.leader, self.p1, day="2026-04-27"))  # same day
        self.assertEqual(len(self.links()), 3)

    def test_clear_link_keeps_the_row(self):
        self.assertFalse(roster.clear_link(self.conn, self.sunday, self.leader, day="2026-04-20"))  # nothing open
        roster.set_link(self.conn, self.sunday, self.leader, self.p1, day="2026-04-20")
        self.assertTrue(roster.clear_link(self.conn, self.sunday, self.leader, day="2026-04-22"))
        self.assertIsNone(roster.open_value(self.conn, self.sunday, self.leader))
        self.assertEqual(self.links(), [(self.sunday, self.leader, self.p1, None, "2026-04-20", "2026-04-22")])
        self.assertFalse(roster.clear_link(self.conn, self.sunday, self.leader, day="2026-04-23"))
        self.refused("calendar.roster_err_day_before", roster.set_link, self.sunday, self.leader, self.p2,
                     day="2026-04-21")  # before the clear: the history stays in order
        self.assertTrue(roster.set_link(self.conn, self.sunday, self.leader, self.p1, day="2026-04-24"))
        self.assertEqual(len(self.links()), 2)

    def test_day_defaults_to_today(self):
        roster.set_link(self.conn, self.sunday, self.in_charge, ministry_id=self.youth)
        roster.set_link(self.conn, self.sunday, self.offering, person_id=self.p3, day=None)
        self.assertEqual([r[4] for r in self.links()], [text.today_text()] * 2)
        roster.clear_link(self.conn, self.sunday, self.in_charge)
        self.assertEqual(self.links()[0][5], text.today_text())

    def test_set_link_refusals(self):
        meeting = self.service(f"{SUNDAY} 14:00", kind="Meeting")
        self.refused("calendar.roster_err_not_service", roster.set_link, meeting, self.leader, self.p1)
        roster.set_role_active(self.conn, self.offering, False)
        e = self.refused("calendar.roster_err_role_hidden", roster.set_link, self.sunday, self.offering, self.p1)
        self.assertEqual(str(e), "The Service role “Offering leader” is hidden. Show it first.")
        self.refused("calendar.roster_err_wrong_day", roster.set_link, self.sunday, self.boi_linh, self.p1)
        self.refused("calendar.roster_err_wrong_day", roster.set_link, self.thursday, self.leader, self.p1)
        self.refused("calendar.roster_err_need_person", roster.set_link, self.sunday, self.leader,
                     ministry_id=self.youth)
        self.refused("calendar.roster_err_need_person", roster.set_link, self.sunday, self.leader, self.p1,
                     self.youth)
        self.refused("calendar.roster_err_need_person", roster.set_link, self.sunday, self.leader)
        self.refused("calendar.roster_err_need_ministry", roster.set_link, self.sunday, self.in_charge, self.p1)
        self.refused("calendar.roster_err_need_ministry", roster.set_link, self.sunday, self.in_charge)
        self.refused("calendar.err_no_person", roster.set_link, self.sunday, self.leader, 999)
        self.refused("calendar.roster_err_no_ministry", roster.set_link, self.sunday, self.in_charge,
                     ministry_id=self.fund)
        self.refused("calendar.err_no_item", roster.set_link, 999, self.leader, self.p1)
        self.refused("calendar.roster_err_no_role", roster.set_link, self.sunday, 999, self.p1)
        self.refused("errors.date", roster.set_link, self.sunday, self.leader, self.p1, day="20/04/2026")
        self.assertEqual(self.links(), [])
        roster.set_link(self.conn, self.sunday, self.leader, self.p1, day="2026-04-20")
        e = self.refused("calendar.roster_err_day_before", roster.set_link, self.sunday, self.leader, self.p2,
                         day="2026-04-19")
        self.assertIn("19/04/2026", i18n.error_text(e, "vi"))
        self.assertIn("20/04/2026", i18n.error_text(e, "vi"))
        self.refused("calendar.roster_err_day_before", roster.clear_link, self.sunday, self.leader, day="2026-04-19")
        self.assertEqual(self.links(), [(self.sunday, self.leader, self.p1, None, "2026-04-20", None)])

    def test_clear_link_refusals(self):
        self.refused("calendar.err_no_item", roster.clear_link, 999, self.leader)
        self.refused("calendar.roster_err_no_role", roster.clear_link, self.sunday, 999)
        self.refused("errors.date", roster.clear_link, self.sunday, self.leader, day="2026-4-20")

    def test_item_links_by_role_order_then_id(self):
        roster.set_link(self.conn, self.sunday, self.in_charge, ministry_id=self.youth, day="2026-04-01")
        roster.set_link(self.conn, self.sunday, self.offering, self.p3, day="2026-04-01")
        roster.set_link(self.conn, self.sunday, self.leader, self.p1, day="2026-04-01")
        roster.set_link(self.conn, self.sunday, self.leader, self.p2, day="2026-04-05")
        roster.set_link(self.conn, self.thursday, self.boi_linh, self.p1, day="2026-04-01")  # another item
        rows = roster.item_links(self.conn, self.sunday)
        self.assertEqual([(r["role_name"], r["done_by"], r["name"], r["start_date"], r["end_date"]) for r in rows],
                         [("Service leader", "person", "Lê Văn An", "2026-04-01", "2026-04-05"),
                          ("Service leader", "person", "Trần Thị Bình", "2026-04-05", None),
                          ("Offering leader", "person", "Phạm Văn Cường", "2026-04-01", None),
                          ("Ministry in charge", "ministry", "Youth", "2026-04-01", None)])
        self.assertEqual((rows[3]["person_id"], rows[3]["ministry_id"]), (None, self.youth))
        self.assertEqual(roster.open_value(self.conn, self.sunday, self.in_charge)["name"], "Youth")
        self.assertEqual(roster.item_links(self.conn, self.service(f"{SUNDAY} 18:00")), [])


class SamePersonTest(RosterCase):
    def test_rule_setting(self):
        self.assertEqual(roster.same_person_rule(self.conn), "service")
        roster.set_same_person_rule(self.conn, "week")
        self.assertEqual(roster.same_person_rule(self.conn), "week")
        self.assertEqual(settings.get_setting(self.conn, "roster_same_person"), "week")
        self.refused("calendar.roster_err_rule", roster.set_same_person_rule, "month")
        self.assertEqual(roster.same_person_rule(self.conn), "week")
        settings.set_setting(self.conn, "roster_same_person", "nonsense")  # a bad value reads as the default
        self.assertEqual(roster.same_person_rule(self.conn), "service")

    def test_service_rule(self):
        roster.set_link(self.conn, self.sunday, self.leader, self.p1, day="2026-04-20")
        conflicts = roster.conflicts
        self.assertEqual(conflicts(self.conn, self.sunday, self.offering, self.p1, rule="service"),
                         [("Service leader", SUNDAY)])
        self.assertEqual(conflicts(self.conn, self.sunday, self.offering, self.p1), [("Service leader", SUNDAY)])
        self.assertEqual(conflicts(self.conn, self.sunday, self.leader, self.p1, "service"), [])  # the slot itself
        self.assertEqual(conflicts(self.conn, self.sunday, self.offering, self.p2, "service"), [])
        later = self.service(f"{SUNDAY} 18:00")  # another Service on the same day: not the same Service
        self.assertEqual(conflicts(self.conn, later, self.offering, self.p1, "service"), [])
        self.assertEqual(conflicts(self.conn, self.sunday, self.in_charge, self.p1, "service"), [])  # a Ministry role

    def test_week_rule_is_monday_to_sunday(self):
        roster.set_link(self.conn, self.thursday, self.boi_linh, self.p1, day="2026-04-20")
        conflicts = roster.conflicts
        self.assertEqual(conflicts(self.conn, self.sunday, self.leader, self.p1, rule="week"),
                         [("Bồi linh", THURSDAY)])
        self.assertEqual(conflicts(self.conn, self.sunday, self.leader, self.p1, rule="service"), [])
        prayer = roster.add_role(self.conn, "Cầu nguyện", 0, "person")
        monday = self.service(f"{MONDAY} 19:00")
        roster.set_link(self.conn, monday, prayer, self.p1, day="2026-04-20")
        roster.set_link(self.conn, self.sunday, self.offering, self.p1, day="2026-04-20")
        self.assertEqual(conflicts(self.conn, self.sunday, self.leader, self.p1, rule="week"),
                         [("Bồi linh", THURSDAY), ("Offering leader", SUNDAY)])  # not the next Monday
        self.assertEqual(conflicts(self.conn, monday, prayer, self.p1, rule="week"), [])  # the next ISO week
        roster.set_same_person_rule(self.conn, "week")
        self.assertEqual(conflicts(self.conn, self.thursday, self.boi_linh, self.p1),
                         [("Offering leader", SUNDAY)])  # the saved rule
        roster.clear_link(self.conn, self.sunday, self.offering, day="2026-04-21")  # a closed link: not held
        self.assertEqual(conflicts(self.conn, self.thursday, self.boi_linh, self.p1), [])

    def test_any_rule(self):
        roster.set_link(self.conn, self.sunday, self.leader, self.p1, day="2026-04-20")
        roster.set_link(self.conn, self.thursday, self.boi_linh, self.p1, day="2026-04-20")
        self.assertEqual(roster.conflicts(self.conn, self.sunday, self.offering, self.p1, rule="any"), [])
        roster.set_same_person_rule(self.conn, "any")
        self.assertEqual(roster.conflicts(self.conn, self.sunday, self.offering, self.p1), [])

    def test_extra_proposals(self):
        conflicts = roster.conflicts
        extra = [(self.sunday, self.leader, self.p2), (str(self.thursday), str(self.boi_linh), str(self.p2)),
                 (self.sunday, self.in_charge, None)]
        self.assertEqual(conflicts(self.conn, self.sunday, self.offering, self.p2, "service", extra),
                         [("Service leader", SUNDAY)])
        self.assertEqual(conflicts(self.conn, self.sunday, self.offering, self.p2, "week", extra),
                         [("Bồi linh", THURSDAY), ("Service leader", SUNDAY)])
        self.assertEqual(conflicts(self.conn, self.sunday, self.offering, self.p1, "week", extra), [])
        self.assertEqual(conflicts(self.conn, self.sunday, self.leader, self.p2, "service", extra), [])  # its slot
        self.assertEqual(self.links(), [])  # proposals are not saved

    def test_refusals(self):
        self.refused("calendar.roster_err_rule", roster.conflicts, self.sunday, self.leader, self.p1, rule="month")
        self.refused("calendar.err_no_item", roster.conflicts, 999, self.leader, self.p1)
        self.refused("calendar.roster_err_no_role", roster.conflicts, self.sunday, 999, self.p1)
        self.refused("errors.whole_number", roster.conflicts, self.sunday, self.leader, None)


class CalendarKeepsTheRosterTest(RosterCase):
    def test_delete_of_a_service_with_a_link_is_refused(self):
        free = self.service(f"{SUNDAY} 18:00")
        self.assertIsNone(calendar.delete_refusal_key(self.conn, free, today="2026-01-01"))
        roster.set_link(self.conn, self.sunday, self.leader, self.p1, day="2026-04-20")
        roster.clear_link(self.conn, self.sunday, self.leader, day="2026-04-21")  # closed: still history
        self.assertEqual(calendar.delete_refusal_key(self.conn, self.sunday, today="2026-01-01"),
                         "calendar.err_kept_roster")
        e = self.refused("calendar.err_kept_roster", calendar.delete_calendar_item, self.sunday, today="2026-01-01")
        self.assertEqual(str(e), "This Service has Service roles on the Roster, so it is kept.")
        self.assertIsNotNone(calendar.get_calendar_item(self.conn, self.sunday))
        calendar.delete_calendar_item(self.conn, free, today="2026-01-01")
        self.assertIsNone(calendar.get_calendar_item(self.conn, free))

    def test_the_head_count_reason_comes_first_then_the_roster_then_a_document(self):
        roster.set_link(self.conn, self.sunday, self.leader, self.p1, day="2026-04-20")
        documents.add_document(self.conn, self.folder, b"order of service", "order.txt", calendar_item_id=self.sunday)
        self.assertEqual(calendar.delete_refusal_key(self.conn, self.sunday), "calendar.err_kept_roster")
        calendar.set_head_count(self.conn, self.sunday, 70)
        self.assertEqual(calendar.delete_refusal_key(self.conn, self.sunday), "calendar.err_kept_head_count")

    def test_a_service_with_a_link_stays_a_service(self):
        roster.set_link(self.conn, self.thursday, self.boi_linh, self.p1, day="2026-04-20")
        self.refused("calendar.err_service_stays_roster", calendar.update_calendar_item, self.thursday, kind="Event")
        calendar.update_calendar_item(self.conn, self.thursday, kind="Service", title="Bồi linh")  # same kind: fine
        self.assertEqual(calendar.get_calendar_item(self.conn, self.thursday)["kind"], "Service")
        calendar.update_calendar_item(self.conn, self.sunday, kind="Event")  # no link: the kind may change
        self.assertEqual(calendar.get_calendar_item(self.conn, self.sunday)["kind"], "Event")


if __name__ == "__main__":
    unittest.main()
