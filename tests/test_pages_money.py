"""Card C2: the Money pages and the printable Giving statement through the real server
(port 0, a fake church in a temp folder, Host and Origin headers)."""

import re
import unittest

import _support  # noqa: F401 - puts the repo root on sys.path
from churchmgr import fake, lists, money, people
from churchmgr.pages import money as money_pages
from test_pages_people import ROOT, TODAY, PagesTestBase, section, shown
from test_server import parse_panels

MONTH = TODAY.strftime("%Y-%m")


def amounts_in(html):
    """Every money figure shown in ``html`` as whole dong: ``"1.250.000 ₫"`` -> ``1250000``."""
    return [int(m.replace(".", "")) for m in re.findall(r"(-?[0-9][0-9.]*) ₫", html)]


class MoneyPagesTest(PagesTestBase):
    def offering_rows(self):
        return self.db().execute("SELECT * FROM offering ORDER BY id").fetchall()

    def fund(self, name="General"):
        return lists.find_item(self.db(), "fund", name=name)["id"]

    def record_offering(self, amount, giver="", expect=303, day=None):
        form = {"date": day or TODAY.isoformat(), "amount": amount, "fund_id": self.fund(), "giver": giver}
        return self.post("/money/offerings/new", form, expect=expect)

    def first_person_id(self):
        return next(p["id"] for p in people.list_persons(self.db()) if p["full_name"] == fake.FIRST_PERSON)

    def test_offering_amount_is_stored_as_whole_dong_and_the_month_total_grows_by_it(self):
        before = money.month_totals(self.db(), TODAY.year, TODAY.month)
        count = len(self.offering_rows())
        headers, _ = self.record_offering("1.250.000")
        self.assertTrue(headers["location"].startswith(f"/money?month={MONTH}&msg="))
        rows = self.offering_rows()
        self.assertEqual(len(rows), count + 1)
        new = rows[-1]
        self.assertEqual((new["amount"], type(new["amount"])), (1250000, int))
        self.assertIsNone(new["giver_person_id"])
        self.assertIsNone(new["giver_family_id"])
        after = money.month_totals(self.db(), TODAY.year, TODAY.month)
        self.assertEqual(after["offerings"] - before["offerings"], 1250000)
        self.assertEqual(after["balance"] - before["balance"], 1250000)
        page = self.page("/money")
        totals = section(page, "money-totals")
        self.assertIn(money.format_vnd(after["offerings"]), totals)
        self.assertIn(money.format_vnd(after["balance"]), totals)
        # the list holds the new row, and its total row adds up from the rows shown
        offerings = section(page, "offerings")
        shown_amounts = amounts_in(offerings)
        self.assertEqual(sum(shown_amounts[:-1]), shown_amounts[-1])
        self.assertEqual(shown_amounts[-1], after["offerings"])
        self.assertEqual(parse_panels(page).rows["offerings"],
                         len(money.list_offerings(self.db(), f"{MONTH}-01", TODAY.isoformat())))
        self.assertIn(money_pages.NO_NAME, offerings)  # the Offering with no Giver

    def test_bad_amounts_are_refused_and_nothing_is_saved(self):
        count = len(self.offering_rows())
        for bad in ("1,5", "1.5", "-100", "abc", "", "0"):
            _h, page = self.record_offering(bad, expect=400)
            self.assertIn('id="f-amount-error"', page, bad)
            self.assertIn('name="amount"', page)
        _h, page = self.record_offering("1,5", expect=400)
        self.assertIn("not understood", page)
        self.assertIn('value="1,5"', page)  # the form comes back with what was typed
        self.assertEqual(len(self.offering_rows()), count)
        # an Expense with a bad amount is refused the same way
        cat = lists.find_item(self.db(), "spending_category", name="Utilities")["id"]
        n_exp = self.db().execute("SELECT COUNT(*) FROM expense").fetchone()[0]
        _h, page = self.post("/money/expenses/new", {"date": TODAY.isoformat(), "amount": "2,5",
                                                     "spending_category_id": cat, "note": ""}, expect=400)
        self.assertIn('id="f-amount-error"', page)
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM expense").fetchone()[0], n_exp)

    def test_expense_is_recorded(self):
        before = money.month_totals(self.db(), TODAY.year, TODAY.month)
        cat = lists.find_item(self.db(), "spending_category", name="Events")["id"]
        self.post("/money/expenses/new", {"date": TODAY.isoformat(), "amount": "650.000 ₫",
                                          "spending_category_id": cat, "note": "C2 Hoa cho Lễ Tạ Ơn"})
        after = money.month_totals(self.db(), TODAY.year, TODAY.month)
        self.assertEqual(after["expenses"] - before["expenses"], 650000)
        self.assertEqual(before["balance"] - after["balance"], 650000)
        expenses = section(self.page("/money"), "expenses")
        self.assertIn("C2 Hoa cho Lễ Tạ Ơn", expenses)
        self.assertEqual(amounts_in(expenses)[-1], after["expenses"])
        _h, page = self.post("/money/expenses/new", {"date": "2099-01-01", "amount": "1000",
                                                     "spending_category_id": cat}, expect=400)
        self.assertIn("Date cannot be after today", page)

    def test_giving_statement_for_a_person_and_a_family(self):
        pid = self.first_person_id()
        secret = "C2-PRIVATE-Cầu nguyện riêng cho gia đình"
        self.post(f"/people/{pid}/private-notes", {"body": secret})
        self.record_offering("2.000.000", giver=f"person-{pid}")
        family = people.current_family(self.db(), pid)
        self.record_offering("3.000.000", giver=f"family-{family['family_id']}")

        # Person: the total is the sum of that Person's Offerings this year, counted here on its own
        expected = self.db().execute(
            "SELECT COALESCE(SUM(amount), 0) FROM offering WHERE giver_person_id = ? AND date BETWEEN ? AND ?",
            (pid, f"{TODAY.year}-01-01", f"{TODAY.year}-12-31")).fetchone()[0]
        page = self.page(f"/money/statement?person_id={pid}&year={TODAY.year}")
        sheet = section(page, "statement")
        self.assertIn(fake.CHURCH_NAME, sheet)
        self.assertIn(fake.FIRST_PERSON, sheet)
        self.assertIn(f"Giving statement {TODAY.year}", sheet)
        for word in ("Date", "Fund", "Given by", "Amount"):
            self.assertIn(f">{word}</th>", sheet)
        figures = amounts_in(sheet)
        self.assertEqual(figures[-1], expected)
        self.assertEqual(sum(figures[:-1]), expected)
        self.assertIn(money.format_vnd(expected), sheet)
        self.assertNotIn("<tfoot", sheet)  # the total is the last body row
        for text_ in (fake.MARKER, "PRIVATE-NOTE-MARKER", secret):
            self.assertNotIn(text_, page)
        self.assertIn("data-print", page)  # the Print button (app.js calls window.print)
        self.assertIn('href="/static/print.css"', page)
        self.assertIn('name="year"', page)  # pick another year

        # Family: the same total as the data layer, the rows add up, no Private note text
        st = money.giving_statement(self.db(), TODAY.year, family_id=family["family_id"])
        page = self.page(f"/money/statement?family_id={family['family_id']}&year={TODAY.year}")
        sheet = section(page, "statement")
        self.assertIn(family["name"], sheet)
        figures = amounts_in(sheet)
        self.assertEqual(figures[-1], st["total"])
        self.assertEqual(sum(figures[:-1]), st["total"])
        self.assertEqual(parse_panels(page).rows["statement"], len(st["rows"]))
        self.assertIn(fake.FIRST_PERSON, sheet)  # given by the Person while in the Family
        self.assertGreaterEqual(st["total"], 2_000_000 + 3_000_000)
        for text_ in (fake.MARKER, "PRIVATE-NOTE-MARKER", secret, "Hộp dâng hiến"):
            self.assertNotIn(text_, page)

        # another year with no Offering keeps the frame and says so
        page = self.page(f"/money/statement?person_id={pid}&year=2001")
        self.assertIn("No Offering from this Giver in 2001", section(page, "statement"))

    def test_statement_picker_and_refusals(self):
        page = self.page("/money/statement")
        self.assertIn("Open Giving statement", section(page, "statement-picker"))
        pid = self.first_person_id()
        fid = people.list_families(self.db())[0]["id"]
        page = self.page(f"/money/statement?person_id={pid}&family_id={fid}&year={TODAY.year}", expect=400)
        self.assertIn("one Person or one Family", page)
        self.assertIn("Year must be", self.page(f"/money/statement?person_id={pid}&year=12", expect=400))
        self.assertIn("No Person with id", self.page("/money/statement?person_id=999999", expect=400))

    def test_offering_with_a_giver_and_the_month_pages(self):
        pid = self.first_person_id()
        self.record_offering("500000", giver=f"person-{pid}", day=f"{MONTH}-01")
        new = self.offering_rows()[-1]
        self.assertEqual((new["giver_person_id"], new["amount"], new["date"]), (pid, 500000, f"{MONTH}-01"))
        page = self.page(f"/money?month={MONTH}")
        self.assertEqual(parse_panels(page).h1, 1)
        self.assertIn(f'href="/people/{pid}"', section(page, "offerings"))
        self.assertIn("This month", page)
        self.assertIn('name="month" type="month"', page)
        self.assertIn("Giving statement", page)
        self.assertIn("No Offering recorded in January 2001", section(self.page("/money?month=2001-01"), "offerings"))
        self.assertIn("Month must be written", self.page("/money?month=nope", expect=400))
        _h, page = self.record_offering("1000", giver="person-abc", expect=400)
        self.assertIn("Giver must be", page)
        form = self.page("/money/offerings/new")
        self.assertIn(money_pages.NO_NAME, form)
        self.assertIn('<optgroup label="Families">', form)
        self.assertIn(f'value="{TODAY.isoformat()}"', form)  # the date is today by default
        self.assertIn(shown(TODAY.isoformat()), self.page("/money"))

    def test_print_css_rules(self):
        css = (ROOT / "web" / "print.css").read_text(encoding="utf-8")
        for rule in ("@media print", "size: A4", "display: table-header-group", "break-inside: avoid",
                     ".no-print", ".sidebar", "button"):
            self.assertIn(rule, css)


class SmallLogicTest(unittest.TestCase):
    def test_parse_giver(self):
        self.assertEqual(money_pages.parse_giver(""), (None, None))
        self.assertEqual(money_pages.parse_giver(None), (None, None))
        self.assertEqual(money_pages.parse_giver("person-5"), (5, None))
        self.assertEqual(money_pages.parse_giver(" family-12 "), (None, 12))
        for bad in ("person-", "person-0", "family-x", "5", "giver-3", "person-1.5"):
            with self.assertRaises(ValueError) as ctx:
                money_pages.parse_giver(bad)
            self.assertTrue(str(ctx.exception).startswith("Giver"), bad)

    def test_month_of(self):
        today = TODAY
        self.assertEqual(money_pages.month_of("", today), (today.year, today.month))
        self.assertEqual(money_pages.month_of("2025-12", today), (2025, 12))
        with self.assertRaises(ValueError):
            money_pages.month_of("2025-12-01", today)

    def test_amounts_are_never_floats_in_the_money_page_code(self):
        source = (ROOT / "churchmgr" / "pages" / "money.py").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"\bfloat\(|\bDecimal\b|/ *100\b")
        self.assertIn("money_data.parse_amount", source)


if __name__ == "__main__":
    unittest.main()
