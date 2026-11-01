import ast
import pathlib
import re
import unittest

import _support
from _support import CopyTestCase
from churchmgr import money, people


class ParseAmountTest(unittest.TestCase):
    def test_good_amounts(self):
        good = {
            "1.250.000": 1250000, "1,250,000": 1250000, "1250000": 1250000, " 1.250.000 ₫": 1250000,
            "1.250.000đ": 1250000, "1.250.000 VND": 1250000, "500.000 vnđ": 500000, "₫ 50.000": 50000,
            "1 250 000": 1250000, "1\u00a0250\u00a0000": 1250000, "999": 999, "1.000": 1000, "12,345": 12345,
            "1.000.000.000": 1000000000, "007": 7,
        }
        for value, want in good.items():
            got = money.parse_amount(value)
            self.assertEqual(got, want, value)
            self.assertIs(type(got), int, value)

    def test_bad_amounts(self):
        bad = ("1,5", "1.5", "12.34", "-100", "abc", "0", "", "   ", "000", "1.2345", "1..250", ".250", "250.",
               "1.250,000", "1,250.000", "1.250.000,00", "1250.000", "1e6", "+100", "١٢٣", "1đ250", "đ", "1/2")
        for value in bad:
            with self.assertRaises(ValueError, msg=repr(value)):
                money.parse_amount(value)
        for value in (None, 1.5, 2.0, True, b"100", 0, -5):
            with self.assertRaises(ValueError, msg=repr(value)):
                money.parse_amount(value)
        self.assertEqual(money.parse_amount(1250000), 1250000)  # a whole int passes
        with self.assertRaises(ValueError):
            money.parse_amount("9" * 16)  # too large

    def test_error_message_is_plain(self):
        with self.assertRaisesRegex(ValueError, "whole number of dong"):
            money.parse_amount("1,5")

    def test_first_thousands_block_has_no_leading_zero(self):
        for value in ("000.001", "0.100", "000,001", "0,100", "01.000"):
            with self.assertRaises(ValueError, msg=repr(value)):
                money.parse_amount(value)
        self.assertEqual(money.parse_amount("1.250.000"), 1250000)
        self.assertEqual(money.parse_amount("1,250,000"), 1250000)
        self.assertEqual(money.parse_amount("100.000"), 100000)

    def test_format_vnd(self):
        self.assertEqual(money.format_vnd(1250000), "1.250.000 ₫")
        self.assertEqual(money.format_vnd(999), "999 ₫")
        self.assertEqual(money.format_vnd(0), "0 ₫")
        self.assertEqual(money.format_vnd(-5000), "-5.000 ₫")
        for bad in (1.5, True, "100"):
            with self.assertRaises(ValueError):
                money.format_vnd(bad)
        for n in (1, 12, 123, 1234, 1250000, 987654321012):
            self.assertEqual(money.parse_amount(money.format_vnd(n)), n)  # round trip


class MoneyCodeTest(unittest.TestCase):
    def test_money_code_has_no_decimals(self):
        src = (pathlib.Path(_support.ROOT) / "churchmgr" / "money.py").read_text(encoding="utf-8")
        found = []
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, (ast.BinOp, ast.AugAssign)) and isinstance(node.op, ast.Div):
                found.append(("division", node.lineno))
            elif isinstance(node, ast.Constant) and type(node.value) is float:
                found.append(("float constant", node.lineno))
            elif isinstance(node, ast.Name) and node.id in ("float", "Decimal", "round"):
                found.append((node.id, node.lineno))
        self.assertEqual(found, [])
        self.assertIsNone(re.search(r"\b(TOTAL|AVG)\s*\(", src, re.IGNORECASE))
        self.assertIn("SUM(amount)", src)


class MoneyTest(CopyTestCase):
    def setUp(self):
        super().setUp()
        self.general = self.item("fund", name="General")
        self.building = self.item("fund", name="Building")
        self.rent = self.item("spending_category", name="Rent")
        self.p = people.add_person(self.conn, "Lê Văn An")
        self.f = people.add_family(self.conn, "Gia đình Lê")

    def count(self, table):
        return self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_offering_checks(self):
        money.add_offering(self.conn, "2026-05-03", 500000, self.general)  # no-name offering
        money.add_offering(self.conn, "2026-05-03", 100000, self.general, giver_person_id=self.p)
        money.add_offering(self.conn, "2026-05-03", 200000, self.building, giver_family_id=self.f, note="Xây dựng")
        bad = [
            dict(amount=1.5), dict(amount=True), dict(amount="100"), dict(amount=0), dict(amount=-1),
            dict(fund_id=self.rent), dict(fund_id=9999), dict(date="03/05/2026"),
            dict(giver_person_id=self.p, giver_family_id=self.f), dict(giver_person_id=9999),
            dict(giver_family_id=9999), dict(amount=10 ** 16),
        ]
        for kwargs in bad:
            args = dict(date="2026-05-03", amount=1000, fund_id=self.general)
            args.update(kwargs)
            with self.assertRaises(ValueError, msg=kwargs):
                money.add_offering(self.conn, **args)
        self.assertEqual(self.count("offering"), 3)
        rows = money.list_offerings(self.conn, "2026-05-01", "2026-05-31")
        self.assertEqual([r["giver_name"] for r in rows], [None, "Lê Văn An", "Gia đình Lê"])
        self.assertEqual(rows[2]["fund_name"], "Building")

    def test_expense_checks(self):
        money.add_expense(self.conn, "2026-05-01", 6000000, self.rent, note="Thuê hội trường")
        for kwargs in (dict(amount=2.5), dict(amount=False), dict(spending_category_id=self.general)):
            args = dict(date="2026-05-01", amount=1000, spending_category_id=self.rent)
            args.update(kwargs)
            with self.assertRaises(ValueError, msg=kwargs):
                money.add_expense(self.conn, **args)
        rows = money.list_expenses(self.conn, "2026-05-01", "2026-05-01")
        self.assertEqual([(r["amount"], r["spending_category_name"]) for r in rows], [(6000000, "Rent")])
        with self.assertRaises(ValueError):
            money.list_expenses(self.conn, "2026-05-31", "2026-05-01")

    def test_month_totals(self):
        for day, amount in (("2026-04-30", 1), ("2026-05-01", 1250000), ("2026-05-31", 750000), ("2026-06-01", 7)):
            money.add_offering(self.conn, day, amount, self.general)
        money.add_expense(self.conn, "2026-05-15", 2600000, self.rent)
        totals = money.month_totals(self.conn, 2026, 5)
        self.assertEqual(totals, {"offerings": 2000000, "expenses": 2600000, "balance": -600000})
        for v in totals.values():
            self.assertIs(type(v), int)
        self.assertEqual(money.month_totals(self.conn, 2026, 7), {"offerings": 0, "expenses": 0, "balance": 0})
        self.assertEqual(money.month_totals(self.conn, "2026", "6")["offerings"], 7)
        money.add_offering(self.conn, "2026-12-31", 5, self.general)
        self.assertEqual(money.month_totals(self.conn, 2026, 12)["offerings"], 5)
        for y, m in ((2026, 13), (2026, 0), (1.5, 1), (2026, True)):
            with self.assertRaises(ValueError):
                money.month_totals(self.conn, y, m)

    def test_month_totals_of_the_first_and_the_last_month(self):
        """B21: 9999-12 ends on 9999-12-31 (no date in the year 10000) and 1900-01 starts on 1900-01-01.
        The totals stay whole dong."""
        for day, amount in (("9999-11-30", 1), ("9999-12-01", 20), ("9999-12-31", 9_999_000),
                            ("1900-01-01", 1_900_000), ("1900-01-31", 300), ("1900-02-01", 7)):
            money.add_offering(self.conn, day, amount, self.general)
        money.add_expense(self.conn, "9999-12-31", 4_000, self.rent)
        totals = money.month_totals(self.conn, 9999, 12)
        self.assertEqual(totals, {"offerings": 9_999_020, "expenses": 4_000, "balance": 9_995_020})
        for v in totals.values():
            self.assertIs(type(v), int)
        self.assertEqual(money.month_totals(self.conn, 9999, 11), {"offerings": 1, "expenses": 0, "balance": 1})
        self.assertEqual(money.month_totals(self.conn, 1900, 1),
                         {"offerings": 1_900_300, "expenses": 0, "balance": 1_900_300})
        self.assertEqual(money.month_totals(self.conn, 1900, 2)["offerings"], 7)


class GivingStatementTest(CopyTestCase):
    """Person P is in Family X until 2026-06-01, then in Family Y."""

    def setUp(self):
        super().setUp()
        c = self.conn
        self.general = self.item("fund", name="General")
        self.missions = self.item("fund", name="Missions")
        self.p = people.add_person(c, "Nguyễn Hải Đăng")
        self.q = people.add_person(c, "Trần Thị Mai")
        self.x = people.add_family(c, "Gia đình Nguyễn")
        self.y = people.add_family(c, "Gia đình Đăng")
        people.set_family(c, self.p, self.x, "Child", "2025-01-01")
        people.set_family(c, self.q, self.x, "Head", "2025-01-01")
        people.set_family(c, self.p, self.y, "Head", "2026-06-01")
        add = money.add_offering
        add(c, "2025-12-31", 900000, self.general, giver_person_id=self.p)   # other year
        add(c, "2026-03-01", 100000, self.general, giver_person_id=self.p, note="ghi chú thường")
        add(c, "2026-04-01", 200000, self.missions, giver_family_id=self.x)
        add(c, "2026-05-01", 300000, self.general, giver_person_id=self.q)
        add(c, "2026-06-01", 400000, self.general, giver_person_id=self.p)   # first day in Family Y
        add(c, "2026-07-01", 500000, self.general, giver_family_id=self.y)
        add(c, "2026-07-02", 600000, self.general)                           # no-name
        people.add_private_note(c, self.p, "PRIVATE-NOTE-MARKER-1 rất riêng tư")

    def rows(self, st):
        return [(r["date"], r["fund"], r["amount"], r["given_by"]) for r in st["rows"]]

    def test_person_statement(self):
        st = money.giving_statement(self.conn, 2026, person_id=self.p)
        self.assertEqual((st["kind"], st["giver_name"], st["year"], st["church_name"]),
                         ("person", "Nguyễn Hải Đăng", 2026, "Hội Thánh Thử"))
        self.assertEqual(self.rows(st), [("2026-03-01", "General", 100000, "Nguyễn Hải Đăng"),
                                         ("2026-06-01", "General", 400000, "Nguyễn Hải Đăng")])
        self.assertEqual(st["total"], 500000)
        self.assertIs(type(st["total"]), int)
        self.assertEqual(money.giving_statement(self.conn, 2025, person_id=self.p)["total"], 900000)

    def test_family_statement_follows_the_family_change(self):
        x = money.giving_statement(self.conn, 2026, family_id=self.x)
        self.assertEqual(self.rows(x), [("2026-03-01", "General", 100000, "Nguyễn Hải Đăng"),
                                        ("2026-04-01", "Missions", 200000, "Gia đình Nguyễn"),
                                        ("2026-05-01", "General", 300000, "Trần Thị Mai")])
        self.assertEqual(x["total"], 600000)
        y = money.giving_statement(self.conn, 2026, family_id=self.y)
        self.assertEqual(self.rows(y), [("2026-06-01", "General", 400000, "Nguyễn Hải Đăng"),
                                        ("2026-07-01", "General", 500000, "Gia đình Đăng")])
        self.assertEqual(y["total"], 900000)
        self.assertEqual(money.giving_statement(self.conn, 2025, family_id=self.x)["rows"][0]["amount"], 900000)

    def test_no_private_note_and_no_offering_note(self):
        for st in (money.giving_statement(self.conn, 2026, person_id=self.p),
                   money.giving_statement(self.conn, 2026, family_id=self.x)):
            flat = repr(st)
            self.assertNotIn("PRIVATE-NOTE-MARKER", flat)
            self.assertNotIn("ghi chú thường", flat)
            self.assertEqual(set(st["rows"][0]), {"date", "fund", "amount", "given_by"})

    def test_bad_requests(self):
        for kwargs in ({}, {"person_id": self.p, "family_id": self.x}, {"person_id": 9999}, {"family_id": 9999}):
            with self.assertRaises(ValueError, msg=kwargs):
                money.giving_statement(self.conn, 2026, **kwargs)
        with self.assertRaises(ValueError):
            money.giving_statement(self.conn, 26.0, person_id=self.p)
        empty = money.giving_statement(self.conn, 2024, person_id=self.q)
        self.assertEqual((empty["rows"], empty["total"]), ([], 0))


class CorrectAndDeleteTest(CopyTestCase):
    """A mistyped Offering or Expense is corrected in place or deleted (a typo is not history)."""

    OLD = "2026-05-03 09:00:00"

    def setUp(self):
        super().setUp()
        c = self.conn
        self.general = self.item("fund", name="General")
        self.building = self.item("fund", name="Building")
        self.rent = self.item("spending_category", name="Rent")
        self.events = self.item("spending_category", name="Events")
        self.p = people.add_person(c, "Lê Văn An")
        self.f = people.add_family(c, "Gia đình Lê")
        # 10.000.000 typed instead of 1.000.000
        self.oid = money.add_offering(c, "2026-05-03", 10_000_000, self.general, giver_person_id=self.p, note="gõ nhầm")
        self.eid = money.add_expense(c, "2026-05-10", 6_500_000, self.rent, note="Thuê hội trường")
        for table in ("offering", "expense"):  # an old created_at, so a changed one would show
            c.execute(f"UPDATE {table} SET created_at = ?", (self.OLD,))

    def row(self, table, rid):
        return self.conn.execute(f"SELECT * FROM {table} WHERE id = ?", (rid,)).fetchone()

    def count(self, table):
        return self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def statement_total(self, **giver):
        return money.giving_statement(self.conn, 2026, **giver)["total"]

    def test_update_offering_fixes_the_row_in_place(self):
        self.assertEqual(self.statement_total(person_id=self.p), 10_000_000)
        money.update_offering(self.conn, self.oid, date="2026-05-04", amount=1_000_000, fund_id=self.building,
                              giver_person_id=self.p, note="đã sửa")
        row = self.row("offering", self.oid)
        self.assertEqual((row["date"], row["amount"], row["fund_id"], row["giver_person_id"], row["giver_family_id"],
                          row["note"], row["created_at"]),
                         ("2026-05-04", 1_000_000, self.building, self.p, None, "đã sửa", self.OLD))
        self.assertIs(type(row["amount"]), int)
        self.assertEqual(self.count("offering"), 1)  # no second row, no correcting entry
        self.assertEqual(money.month_totals(self.conn, 2026, 5),
                         {"offerings": 1_000_000, "expenses": 6_500_000, "balance": -5_500_000})
        st = money.giving_statement(self.conn, 2026, person_id=self.p)
        self.assertEqual(([(r["date"], r["fund"], r["amount"]) for r in st["rows"]], st["total"]),
                         ([("2026-05-04", "Building", 1_000_000)], 1_000_000))
        # the Giver moves to the Family, then to nobody (a no-name offering); the note is cleared
        money.update_offering(self.conn, self.oid, date="2026-05-04", amount=1_000_000, fund_id=self.building,
                              giver_family_id=self.f)
        self.assertEqual((self.statement_total(person_id=self.p), self.statement_total(family_id=self.f)),
                         (0, 1_000_000))
        money.update_offering(self.conn, self.oid, date="2026-05-04", amount=1_000_000, fund_id=self.building)
        row = self.row("offering", self.oid)
        self.assertEqual((row["giver_person_id"], row["giver_family_id"], row["note"]), (None, None, None))
        self.assertEqual(self.statement_total(family_id=self.f), 0)
        # a new date in June: May loses it, June gets it
        money.update_offering(self.conn, self.oid, date="2026-06-01", amount=1_000_000, fund_id=self.building)
        self.assertEqual(money.month_totals(self.conn, 2026, 5)["offerings"], 0)
        self.assertEqual(money.month_totals(self.conn, 2026, 6)["offerings"], 1_000_000)

    def test_update_offering_refuses_what_add_offering_refuses(self):
        before = tuple(self.row("offering", self.oid))
        good = dict(date="2026-05-03", amount=1000, fund_id=self.general)
        bad = [
            dict(amount=1.5), dict(amount="1.000"), dict(amount=True), dict(amount=0), dict(amount=-1),
            dict(amount=10 ** 16), dict(fund_id=self.rent), dict(fund_id=9999), dict(date="03/05/2026"),
            dict(giver_person_id=self.p, giver_family_id=self.f), dict(giver_person_id=9999),
            dict(giver_family_id=9999),
        ]
        for kwargs in bad:
            with self.assertRaises(ValueError, msg=kwargs):
                money.update_offering(self.conn, self.oid, **{**good, **kwargs})
        with self.assertRaisesRegex(ValueError, "one Giver"):
            money.update_offering(self.conn, self.oid, **good, giver_person_id=self.p, giver_family_id=self.f)
        self.assertEqual(tuple(self.row("offering", self.oid)), before)  # nothing changed
        with self.assertRaisesRegex(ValueError, r"^No Offering with id 9999\.$"):
            money.update_offering(self.conn, 9999, **good)
        with self.assertRaisesRegex(ValueError, r"^No Offering with id 9999\.$"):
            money.delete_offering(self.conn, 9999)
        with self.assertRaisesRegex(ValueError, "Offering must be a whole number"):
            money.delete_offering(self.conn, "abc")
        self.assertEqual(self.count("offering"), 1)

    def test_delete_offering(self):
        keep = money.add_offering(self.conn, "2026-05-20", 300_000, self.general, giver_person_id=self.p)
        money.delete_offering(self.conn, self.oid)
        self.assertIsNone(money.get_offering(self.conn, self.oid))
        self.assertEqual(money.get_offering(self.conn, keep)["amount"], 300_000)
        self.assertEqual(money.month_totals(self.conn, 2026, 5)["offerings"], 300_000)
        st = money.giving_statement(self.conn, 2026, person_id=self.p)
        self.assertEqual(([r["amount"] for r in st["rows"]], st["total"]), ([300_000], 300_000))
        with self.assertRaisesRegex(ValueError, "No Offering with id"):
            money.delete_offering(self.conn, self.oid)  # already gone

    def test_update_and_delete_expense(self):
        money.update_expense(self.conn, self.eid, date="2026-05-11", amount=650_000, spending_category_id=self.events,
                             note="Hoa cho Lễ Tạ Ơn")
        row = self.row("expense", self.eid)
        self.assertEqual((row["date"], row["amount"], row["spending_category_id"], row["note"], row["created_at"]),
                         ("2026-05-11", 650_000, self.events, "Hoa cho Lễ Tạ Ơn", self.OLD))
        self.assertIs(type(row["amount"]), int)
        self.assertEqual(money.month_totals(self.conn, 2026, 5),
                         {"offerings": 10_000_000, "expenses": 650_000, "balance": 9_350_000})
        before = tuple(row)
        good = dict(date="2026-05-11", amount=1000, spending_category_id=self.rent)
        for kwargs in (dict(amount=2.5), dict(amount="650000"), dict(amount=0), dict(amount=False),
                       dict(spending_category_id=self.general), dict(spending_category_id=9999),
                       dict(date="2026-13-01")):
            with self.assertRaises(ValueError, msg=kwargs):
                money.update_expense(self.conn, self.eid, **{**good, **kwargs})
        self.assertEqual(tuple(self.row("expense", self.eid)), before)
        with self.assertRaisesRegex(ValueError, r"^No Expense with id 9999\.$"):
            money.update_expense(self.conn, 9999, **good)
        with self.assertRaisesRegex(ValueError, r"^No Expense with id 9999\.$"):
            money.delete_expense(self.conn, 9999)
        money.delete_expense(self.conn, self.eid)
        self.assertIsNone(money.get_expense(self.conn, self.eid))
        self.assertEqual(self.count("expense"), 0)
        self.assertEqual(money.month_totals(self.conn, 2026, 5),
                         {"offerings": 10_000_000, "expenses": 0, "balance": 10_000_000})

    def test_get_offering_and_get_expense(self):
        o = money.get_offering(self.conn, self.oid)
        self.assertEqual((o["amount"], o["fund_name"], o["giver_name"], o["note"]),
                         (10_000_000, "General", "Lê Văn An", "gõ nhầm"))
        e = money.get_expense(self.conn, self.eid)
        self.assertEqual((e["amount"], e["spending_category_name"]), (6_500_000, "Rent"))
        self.assertIsNone(money.get_offering(self.conn, 9999))
        self.assertIsNone(money.get_expense(self.conn, 9999))

    def test_a_date_needs_a_year_from_1900(self):
        """B18: a row dated before 1900 would be in no Money month (a month starts at 1900-01)."""
        before = (tuple(self.row("offering", self.oid)), tuple(self.row("expense", self.eid)))
        counts = (self.count("offering"), self.count("expense"))
        for day in ("0001-01-01", "1899-12-31"):
            calls = (
                lambda: money.add_offering(self.conn, day, 1000, self.general),
                lambda: money.update_offering(self.conn, self.oid, date=day, amount=1000, fund_id=self.general),
                lambda: money.add_expense(self.conn, day, 1000, self.rent),
                lambda: money.update_expense(self.conn, self.eid, date=day, amount=1000, spending_category_id=self.rent),
            )
            for i, call in enumerate(calls):
                with self.assertRaisesRegex(ValueError, r"^Date: use a year from 1900 to 9999\.$", msg=(day, i)):
                    call()
        self.assertEqual((self.count("offering"), self.count("expense")), counts)  # nothing saved
        self.assertEqual((tuple(self.row("offering", self.oid)), tuple(self.row("expense", self.eid))), before)
        oid = money.add_offering(self.conn, "1900-01-01", 1000, self.general)
        money.update_expense(self.conn, self.eid, date="1900-01-01", amount=500, spending_category_id=self.rent)
        self.assertEqual(money.get_offering(self.conn, oid)["date"], "1900-01-01")
        self.assertEqual(money.month_totals(self.conn, 1900, 1), {"offerings": 1000, "expenses": 500, "balance": 500})


if __name__ == "__main__":
    unittest.main()
