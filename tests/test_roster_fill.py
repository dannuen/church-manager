"""Auto-fill (card RO-3, decision D5): roster.fill_plan and roster.save_fill on the pastor's sample.

Each test has a fresh church copy in a temp folder (not the fake church) with 6 people named after the
sample, a weekly Thursday Service and a weekly Sunday Service for all of 2026, and 3 more Ministries.
"""

import collections
import datetime as _dt
import unittest
from unittest import mock

import _support  # noqa: F401  (puts the repo on sys.path)
from _support import CopyTestCase
from churchmgr import calendar, i18n, lists, people, roster, text
from churchmgr.i18n import TextError

NAMES: tuple[str, ...] = ("Huệ", "Hiền", "Tín", "Tứ", "Linh", "Tài")
MINISTRIES = ("Ban Trung niên", "Ban Thanh tráng", "Ban Tráng niên")
YEAR = ("2026-01-01", "2026-12-31")
SAMPLE_SKIPPED = ("2026-03-29", "2026-11-08")


class FillCase(CopyTestCase):
    LANG = "vi"

    def setUp(self):
        super().setUp()
        self.ids = [people.add_person(self.conn, name) for name in NAMES]
        self.person_name = dict(zip(self.ids, NAMES))
        by_order = {r["sort_order"]: r["id"] for r in roster.roles(self.conn)}  # the 4 default Service roles (D3)
        self.boi_linh, self.leader, self.offering, self.in_charge = (by_order[k] for k in (1, 2, 3, 4))
        self.ministries = [lists.add_item(self.conn, "ministry", name) for name in MINISTRIES]
        self.ministry_name = dict(zip(self.ministries, MINISTRIES))
        calendar.add_calendar_item(self.conn, "Service", "Thờ phượng Chúa Nhật", "2026-01-04 08:00",
                                   repeat="weekly", repeat_until="2026-12-31")
        calendar.add_calendar_item(self.conn, "Service", "Bồi linh", "2026-01-01 19:30",
                                   repeat="weekly", repeat_until="2026-12-31")
        self.date = {r["id"]: r["starts_at"][:10] for r in self.conn.execute("SELECT id, starts_at FROM calendar_item")}
        self.item_on = {day: iid for iid, day in self.date.items()}

    def leader_rotation(self, month_start, month_start_from=None):
        """The Service leader (HDCT) role with the 6 people in the sample's order."""
        roster.update_role(self.conn, self.leader, month_start=month_start, month_start_from=month_start_from)
        roster.set_rotation(self.conn, self.leader, self.ids)

    def value_name(self, person_id, ministry_id):
        return self.person_name[person_id] if person_id is not None else self.ministry_name[ministry_id]

    def proposed(self, plan, role_id):
        """``{date: name}`` of the proposals of one Service role."""
        return {self.date[item]: self.value_name(person, ministry)
                for item, role, person, ministry in plan["proposals"] if role == role_id}

    def saved(self, role_id):
        """``{date: name}`` of the open links of one Service role."""
        return {self.date[r[0]]: self.value_name(r[1], r[2]) for r in self.conn.execute(
            "SELECT calendar_item_id, person_id, ministry_id FROM service_role_link "
            "WHERE service_role_id = ? AND end_date IS NULL", (role_id,))}

    @staticmethod
    def in_order(by_date):
        return [by_date[day] for day in sorted(by_date)]

    def links(self):
        return [tuple(r) for r in self.conn.execute(
            "SELECT calendar_item_id, service_role_id, person_id, ministry_id, start_date, end_date "
            "FROM service_role_link ORDER BY id")]

    def refused(self, key, fn, *args, **kwargs):
        with self.assertRaises(TextError) as ctx:
            fn(self.conn, *args, **kwargs)
        self.assertEqual(ctx.exception.key, key, str(ctx.exception))
        self.assertNotIn("[[", i18n.error_text(ctx.exception, "vi"))
        return ctx.exception


class SampleTest(FillCase):
    def test_1_the_pastor_sample_with_month_start(self):
        """The D5 measured case: HDCT, month start from 2026-01, Skipped dates 29/03 and 08/11."""
        self.leader_rotation(True, "2026-01")
        for day in SAMPLE_SKIPPED:
            roster.add_skipped_date(self.conn, day, "Hội đồng bồi linh")
        plan = roster.fill_plan(self.conn, *YEAR)
        self.assertEqual(plan["nobody_free"], [])
        self.assertEqual({role for _item, role, _p, _m in plan["proposals"]}, {self.leader})  # other Rotations: empty
        got = self.proposed(plan, self.leader)
        self.assertEqual(len(got), 50)  # 52 Sundays, 2 of them Skipped
        self.assertFalse(set(SAMPLE_SKIPPED) & set(got))
        first_sundays = [min(day for day in got if day[5:7] == f"{month:02d}") for month in range(1, 13)]
        self.assertTrue(all(int(day[8:]) <= 7 for day in first_sundays), first_sundays)
        self.assertEqual([got[day] for day in first_sundays], list(NAMES) * 2)
        counts = collections.Counter(got.values())
        self.assertEqual([counts[name] for name in NAMES], [9, 9, 8, 8, 8, 8])
        names = self.in_order(got)
        self.assertEqual([a for a, b in zip(names, names[1:]) if a == b], [])  # nobody on two Sundays in a row
        self.assertEqual(sorted(got)[5], "2026-02-08")
        self.assertEqual(names[:6], ["Huệ", "Tín", "Tứ", "Linh", "Hiền", "Tài"])  # 04/01 to 08/02

    def test_no_month_start_from_counts_from_the_month_of_from(self):
        self.leader_rotation(True)
        got = self.proposed(roster.fill_plan(self.conn, "2026-04-01", "2026-06-30"), self.leader)
        self.assertEqual((got["2026-04-05"], got["2026-05-03"], got["2026-06-07"]), ("Huệ", "Hiền", "Tín"))

    def test_a_range_from_mid_month_gives_that_month_starter_to_no_later_sunday(self):
        """The first Service of a month is counted over all the role's Services: 01/02 began February's round,
        so 15/02 (the first Sunday of the range) is a plain turn, not Hiền (February's starter)."""
        self.leader_rotation(True, "2026-01")
        got = self.proposed(roster.fill_plan(self.conn, "2026-02-10", "2026-03-31"), self.leader)
        self.assertEqual(got["2026-02-15"], "Huệ")
        self.assertEqual(got["2026-03-01"], "Tín")  # March's starter (2 months after 2026-01)

    def test_2_month_start_off_is_plain_turn_by_turn(self):
        self.leader_rotation(False)
        for day in SAMPLE_SKIPPED:
            roster.add_skipped_date(self.conn, day, "Hội đồng bồi linh")
        names = self.in_order(self.proposed(roster.fill_plan(self.conn, *YEAR), self.leader))
        self.assertEqual(names, [NAMES[k % 6] for k in range(50)])
        for k in range(len(names) - 5):
            self.assertEqual(len(set(names[k:k + 6])), 6, k)  # any 6 Sundays in a row: 6 different people
        counts = collections.Counter(names).values()
        self.assertLessEqual(max(counts) - min(counts), 1)

    def test_a_hidden_role_or_an_empty_rotation_gets_nothing(self):
        self.leader_rotation(False)
        self.assertEqual(roster.rotation(self.conn, self.offering), [])
        roster.set_role_active(self.conn, self.leader, False)
        self.assertEqual(roster.fill_plan(self.conn, *YEAR), {"proposals": [], "nobody_free": []})

    def test_when_only_a_kept_one_is_free_the_kept_one_is_taken(self):
        """D5 "Nobody: ignore (a)": on 25/01 Hiền is kept for 01/02 (February's starter) and Huệ holds the
        Offering leader in that Service (rule service), so Hiền takes 25/01 rather than nobody."""
        hue, hien = self.ids[:2]
        roster.update_role(self.conn, self.leader, month_start=True, month_start_from="2026-01")
        roster.set_rotation(self.conn, self.leader, [hue, hien])
        roster.set_link(self.conn, self.item_on["2026-01-25"], self.offering, hue, day="2025-12-01")
        plan = roster.fill_plan(self.conn, "2026-01-01", "2026-02-28")
        self.assertEqual(plan["nobody_free"], [])
        got = self.proposed(plan, self.leader)
        self.assertEqual([got[d] for d in ("2026-01-04", "2026-01-11", "2026-01-18", "2026-01-25", "2026-02-01")],
                         ["Huệ", "Hiền", "Huệ", "Hiền", "Hiền"])


class SkippedAndHeldTest(FillCase):
    def test_3_a_skipped_date_gets_no_link_and_uses_no_turn(self):
        self.leader_rotation(False)
        roster.set_rotation(self.conn, self.boi_linh, self.ids)
        roster.add_skipped_date(self.conn, "2026-01-18", "Hội đồng bồi linh")
        roster.add_skipped_date(self.conn, "2026-01-01", "Tết Dương lịch")  # a Thursday
        plan = roster.fill_plan(self.conn, "2026-01-01", "2026-01-31")
        self.assertEqual(self.proposed(plan, self.leader),
                         {"2026-01-04": "Huệ", "2026-01-11": "Hiền", "2026-01-25": "Tín"})
        self.assertEqual(self.proposed(plan, self.boi_linh),
                         {"2026-01-08": "Huệ", "2026-01-15": "Hiền", "2026-01-22": "Tín", "2026-01-29": "Tứ"})
        self.assertEqual(plan["nobody_free"], [])  # a Skipped date is not reported either
        self.assertEqual(roster.save_fill(self.conn, "2026-01-01", "2026-01-31", day="2025-12-20"), 7)
        self.assertEqual(roster.item_links(self.conn, self.item_on["2026-01-18"]), [])
        self.assertEqual(roster.item_links(self.conn, self.item_on["2026-01-01"]), [])

    def test_4_a_held_service_is_never_changed_and_its_holder_goes_to_the_end(self):
        self.leader_rotation(False)
        guest = people.add_person(self.conn, "Phúc")  # not in the Rotation
        self.person_name[guest] = "Phúc"
        tai, hien = self.ids[5], self.ids[1]
        roster.set_link(self.conn, self.item_on["2026-01-18"], self.leader, tai, day="2025-12-01")  # the pastor
        roster.set_link(self.conn, self.item_on["2026-02-01"], self.leader, hien, day="2025-12-01")
        roster.clear_link(self.conn, self.item_on["2026-02-01"], self.leader, day="2025-12-02")  # cleared: held
        roster.set_link(self.conn, self.item_on["2026-03-01"], self.leader, guest, day="2025-12-01")
        kept = self.links()
        plan = roster.fill_plan(self.conn, "2026-01-01", "2026-03-31")
        expected = {"2026-01-04": "Huệ", "2026-01-11": "Hiền", "2026-01-25": "Tín", "2026-02-08": "Tứ",
                    "2026-02-15": "Linh", "2026-02-22": "Huệ", "2026-03-08": "Hiền", "2026-03-15": "Tài",
                    "2026-03-22": "Tín", "2026-03-29": "Tứ"}  # Tài (18/01) went to the end; Phúc moves nobody
        self.assertEqual(self.proposed(plan, self.leader), expected)
        self.assertEqual(roster.save_fill(self.conn, "2026-01-01", "2026-03-31", day="2025-12-20"), 10)
        self.assertEqual(self.links()[:len(kept)], kept)  # the held rows did not change
        self.assertEqual(self.saved(self.leader), {**expected, "2026-01-18": "Tài", "2026-03-01": "Phúc"})
        self.assertIsNone(roster.open_value(self.conn, self.item_on["2026-02-01"], self.leader))
        self.assertEqual(roster.fill_plan(self.conn, "2026-01-01", "2026-03-31"), {"proposals": [], "nobody_free": []})
        self.assertEqual(roster.save_fill(self.conn, "2026-01-01", "2026-03-31", day="2025-12-21"), 0)
        self.assertEqual(len(self.links()), len(kept) + 10)

    def test_5_the_queue_goes_on_after_the_last_holder_before_from(self):
        self.leader_rotation(False)
        roster.set_rotation(self.conn, self.in_charge, self.ministries)  # every 2nd Sunday (D3)
        one_go = roster.fill_plan(self.conn, "2026-01-01", "2026-06-30")
        expected = {role: self.proposed(one_go, role) for role in (self.leader, self.in_charge)}
        self.assertEqual(roster.save_fill(self.conn, "2026-01-01", "2026-03-31", day="2025-12-20"), 13 + 7)
        self.assertEqual(roster.save_fill(self.conn, "2026-04-01", "2026-06-30", day="2025-12-20"), 13 + 6)
        for role, by_date in expected.items():
            self.assertEqual(self.saved(role), by_date)
        self.assertEqual(expected[self.leader]["2026-04-05"], "Hiền")  # turn 13 (13 % 6 = 1), not Huệ again

    def test_6_every_second_sunday_for_the_ministry_in_charge(self):
        roster.set_rotation(self.conn, self.in_charge, self.ministries)
        self.assertEqual(roster.get_role(self.conn, self.in_charge)["every"], 2)
        m1, m2, m3 = MINISTRIES
        got = self.proposed(roster.fill_plan(self.conn, "2026-01-01", "2026-03-31"), self.in_charge)
        self.assertEqual(got, {"2026-01-04": m1, "2026-01-18": m2, "2026-02-01": m3, "2026-02-15": m1,
                               "2026-03-01": m2, "2026-03-15": m3, "2026-03-29": m1})
        # The pastor set 11/01: the next step is 2 Services later, and the next turn comes after that Ministry.
        roster.set_link(self.conn, self.item_on["2026-01-11"], self.in_charge, ministry_id=self.ministries[1],
                        day="2025-12-01")
        got = self.proposed(roster.fill_plan(self.conn, "2026-01-12", "2026-03-31"), self.in_charge)
        self.assertEqual(got, {"2026-01-25": m3, "2026-02-08": m1, "2026-02-22": m2, "2026-03-08": m3,
                               "2026-03-22": m1})


class SamePersonRuleTest(FillCase):
    """Test 7: 3 Service roles done by a Person with the same 6 people: Bồi linh on Thursday, the Service
    leader (HDCT) and the Offering leader on Sunday."""

    PROPOSALS = 53 + 52 * 2  # 2026 starts on a Thursday: 53 Thursdays (Bồi linh), 52 Sundays x 2 roles

    def setUp(self):
        super().setUp()
        for role in (self.boi_linh, self.leader, self.offering):
            roster.set_rotation(self.conn, role, self.ids)

    def plan(self, rule):
        roster.set_same_person_rule(self.conn, rule)
        before = self.conn.total_changes
        plan = roster.fill_plan(self.conn, *YEAR)
        self.assertEqual(self.conn.total_changes, before)  # fill_plan writes nothing
        self.assertEqual(plan["nobody_free"], [])
        self.assertEqual(len(plan["proposals"]), self.PROPOSALS)
        return plan

    def by_slot(self, plan):
        """``{(item_id, role_id): person_id}`` of a plan."""
        return {(item, role): person for item, role, person, _m in plan["proposals"]}

    def by_week(self, plan):
        """``{ISO week: [person_id, ...]}`` of a plan."""
        weeks = collections.defaultdict(list)
        for item, _role, person, _m in plan["proposals"]:
            weeks[_dt.date.fromisoformat(self.date[item]).isocalendar()[:2]].append(person)
        return weeks

    def sundays(self):
        return [iid for iid, day in self.date.items() if _dt.date.fromisoformat(day).weekday() == 6]

    def test_service_never_twice_in_one_service(self):
        plan = self.plan("service")
        slot = self.by_slot(plan)
        for sunday in self.sundays():  # the Service leader proposals (not saved) count for the Offering leader
            self.assertNotEqual(slot[(sunday, self.leader)], slot[(sunday, self.offering)], self.date[sunday])
        self.assertTrue(any(len(set(p)) < len(p) for p in self.by_week(plan).values()))  # a week may repeat one

    def test_week_never_twice_in_one_iso_week(self):
        plan = self.plan("week")
        for week, persons in self.by_week(plan).items():
            self.assertEqual(len(set(persons)), len(persons), week)
        self.assertEqual(roster.save_fill(self.conn, *YEAR, day="2025-12-20"), self.PROPOSALS)
        for item, role, person, _m in plan["proposals"]:
            self.assertEqual(roster.conflicts(self.conn, item, role, person, "week"), [], self.date[item])

    def test_any_makes_no_check(self):
        slot = self.by_slot(self.plan("any"))
        self.assertTrue(any(slot[(s, self.leader)] == slot[(s, self.offering)] for s in self.sundays()))

    def test_8_nobody_free_is_reported_not_filled(self):
        hue, hien = self.ids[:2]
        for role in (self.boi_linh, self.leader, self.offering):
            roster.set_rotation(self.conn, role, [hue, hien])
        roster.set_same_person_rule(self.conn, "week")
        jan1, jan4, jan8, jan11 = (self.item_on[d] for d in ("2026-01-01", "2026-01-04", "2026-01-08", "2026-01-11"))
        plan = roster.fill_plan(self.conn, "2026-01-01", "2026-01-11")
        self.assertEqual(plan["proposals"], [(jan1, self.boi_linh, hue, None), (jan8, self.boi_linh, hien, None),
                                             (jan4, self.leader, hien, None), (jan11, self.leader, hue, None)])
        self.assertEqual(plan["nobody_free"], [(jan4, self.offering), (jan11, self.offering)])
        self.assertEqual(roster.save_fill(self.conn, "2026-01-01", "2026-01-11", day="2025-12-20"), 4)
        self.assertIsNone(roster.open_value(self.conn, jan4, self.offering))
        self.assertIsNone(roster.open_value(self.conn, jan11, self.offering))


class SaveFillTest(FillCase):
    def test_9_save_fill_saves_with_set_link_from_day(self):
        self.leader_rotation(False)
        roster.set_rotation(self.conn, self.in_charge, self.ministries)
        plan = roster.fill_plan(self.conn, "2026-01-01", "2026-03-31")
        self.assertEqual(roster.save_fill(self.conn, "2026-01-01", "2026-03-31", day="2025-12-20"), 13 + 7)
        self.assertEqual(self.links(), [(*p, "2025-12-20", None) for p in plan["proposals"]])

    def test_the_day_defaults_to_today(self):
        self.leader_rotation(False)
        self.assertEqual(roster.save_fill(self.conn, "2026-01-01", "2026-01-31"), 4)
        self.assertEqual({row[4] for row in self.links()}, {text.today_text()})

    def test_9_a_failure_in_the_middle_saves_nothing(self):
        self.leader_rotation(False)
        real, calls = roster.set_link, []

        def fails_on_the_fifth(*args, **kwargs):
            calls.append(args)
            if len(calls) == 5:
                raise TextError("calendar.roster_err_not_service")
            return real(*args, **kwargs)

        with mock.patch.object(roster, "set_link", fails_on_the_fifth):
            self.refused("calendar.roster_err_not_service", roster.save_fill, "2026-01-01", "2026-03-31",
                         day="2025-12-20")
        self.assertEqual(len(calls), 5)
        self.assertEqual(self.links(), [])  # the 4 saved before the failure are gone too
        self.assertFalse(self.conn.in_transaction)
        self.assertEqual(roster.save_fill(self.conn, "2026-01-01", "2026-03-31", day="2025-12-20"), 13)

    def test_fill_plan_writes_nothing(self):
        self.leader_rotation(True, "2026-01")
        before = self.conn.total_changes
        plan = roster.fill_plan(self.conn, *YEAR)
        self.assertEqual(len(plan["proposals"]), 52)
        self.assertEqual(self.conn.total_changes, before)
        self.assertFalse(self.conn.in_transaction)
        self.assertEqual(self.links(), [])


class RangeTest(FillCase):
    def test_refusals(self):
        for fn in (roster.fill_plan, roster.save_fill):
            with self.subTest(fn=fn.__name__):
                self.refused("calendar.roster_err_fill_before", fn, "2026-03-01", "2026-02-28")
                self.refused("calendar.roster_err_fill_long", fn, "2026-01-01", "2027-01-03")  # 367 days after
                self.refused("errors.date", fn, "01/01/2026", "2026-02-01")
                self.refused("errors.date", fn, "2026-01-01", None)
        self.refused("errors.date", roster.save_fill, "2026-01-01", "2026-01-31", day="2026-02-30")
        self.assertEqual(self.links(), [])
        roster.fill_plan(self.conn, "2026-01-01", "2027-01-02")  # 366 days after: the longest range
        roster.fill_plan(self.conn, "2026-01-04", "2026-01-04")  # one day

    def test_the_texts(self):
        cases = (("calendar.roster_err_fill_before", {}, "Auto-fill: the end date is before the start date.",
                  "Tự động xếp lịch: ngày kết thúc ở trước ngày bắt đầu."),
                 ("calendar.roster_err_fill_long", {"max": 366},
                  "Auto-fill: the end date may be at most 366 days after the start date.",
                  "Tự động xếp lịch: ngày kết thúc chỉ được sau ngày bắt đầu nhiều nhất 366 ngày."))
        for key, params, en, vi in cases:
            e = TextError(key, **params)
            self.assertEqual((str(e), i18n.error_text(e, "en"), i18n.error_text(e, "vi")), (en, en, vi))


if __name__ == "__main__":
    unittest.main()
