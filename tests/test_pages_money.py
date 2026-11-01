"""Card C2: the Money pages and the printable Giving statement through the real server
(port 0, a fake church in a temp folder, Host and Origin headers)."""

import datetime as dt
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

    def test_a_bad_fund_or_spending_category_says_choose_one_from_the_list(self):
        """B5: an id that is not in the list gets the glossary word next to its field, never "Item 99999"."""
        count = len(self.offering_rows())
        form = {"date": TODAY.isoformat(), "amount": "100.000", "fund_id": "99999", "giver": ""}
        _h, page = self.post("/money/offerings/new", form, expect=400)
        self.assertIn('<p class="error" id="f-fund_id-error">Fund: choose one from the list.</p>', page)
        self.assertNotIn("Item 99999", page)
        self.assertEqual(len(self.offering_rows()), count)
        n_exp = self.db().execute("SELECT COUNT(*) FROM expense").fetchone()[0]
        form = {"date": TODAY.isoformat(), "amount": "100.000", "spending_category_id": "99999", "note": ""}
        _h, page = self.post("/money/expenses/new", form, expect=400)
        self.assertIn('<p class="error" id="f-spending_category_id-error">Spending category: choose one from the list.</p>',
                      page)
        self.assertNotIn("Item 99999", page)
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM expense").fetchone()[0], n_exp)

    def test_giving_statement_for_a_person_and_a_family(self):
        pid = self.first_person_id()
        private_text = "C2-PRIVATE-Cầu nguyện riêng cho gia đình"
        self.post(f"/people/{pid}/private-notes", {"body": private_text})
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
        for text_ in (fake.MARKER, "PRIVATE-NOTE-MARKER", private_text):
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
        for text_ in (fake.MARKER, "PRIVATE-NOTE-MARKER", private_text, "Hộp dâng hiến"):
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

    def test_month_links_stop_at_1900_01_and_9999_12(self):
        """B21: no chip links to a month the app refuses. 1900-01 has no previous month; 9999-12 opens
        (no date in the year 10000) and has no next month. Plain sentences only, never Python text."""
        money.add_offering(self.db(), "1900-01-01", 1_900_001, self.fund())
        page = self.page("/money?month=1900-01")
        self.assertNotIn("December 1899", page)
        self.assertNotIn("month=1899-12", page)
        self.assertIn('href="/money?month=1900-02">February 1900 ›</a>', page)
        self.assertIn("This month", page)
        self.assertIn("1.900.001 ₫", section(page, "money-totals"))
        money.add_offering(self.db(), "9999-12-31", 9_999_001, self.fund())  # the data layer takes a far date
        page = self.page("/money?month=9999-12")
        self.assertNotIn("January 10000", page)
        self.assertNotIn("month=10000-01", page)
        self.assertIn('href="/money?month=9999-11">‹ November 9999</a>', page)
        self.assertIn("This month", page)
        self.assertIn("9.999.001 ₫", section(page, "money-totals"))
        self.assertIn(shown("9999-12-31"), section(page, "offerings"))
        for bad in ("1899-12", "0000-01"):
            self.assertIn("Month: use a year from 1900 to 9999.", self.page(f"/money?month={bad}", expect=400))
        page = self.page("/money?month=10000-01", expect=400)  # a 5-digit year: the form sentence
        self.assertIn("Month must be written YYYY-MM, for example 2026-11.", page)
        self.assertNotIn("year must be in", page)
        for path in ("/money", "/money?month=1900-01", "/money?month=9999-12"):
            self.assertRegex(self.page(path), r'id="money-month" name="month" type="month" value="[0-9]{4}-[0-9]{2}" '
                                              r'min="1900-01" max="9999-12" required>')

    def test_print_css_rules(self):
        css = (ROOT / "web" / "print.css").read_text(encoding="utf-8")
        for rule in ("@media print", "size: A4", "display: table-header-group", "break-inside: avoid",
                     ".no-print", ".sidebar", "button",
                     ".panel .table-wrap { margin: 0; overflow: visible; }"):  # no 12px bleed past the sheet
            self.assertIn(rule, css)
        print_block = css[css.index("@media print"):]
        self.assertIn(".panel .table-wrap", print_block)


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


class CorrectMoneyPagesTest(PagesTestBase):
    """Edit and Delete of an Offering and an Expense on /money (its own fake church and server)."""

    def fund(self, name="General"):
        return lists.find_item(self.db(), "fund", name=name)["id"]

    def category(self, name):
        return lists.find_item(self.db(), "spending_category", name=name)["id"]

    def first_person_id(self):
        return next(p["id"] for p in people.list_persons(self.db()) if p["full_name"] == fake.FIRST_PERSON)

    def offering_form(self, amount, giver="", fund=None, day=None, note=""):
        return {"date": day or TODAY.isoformat(), "amount": amount, "fund_id": fund or self.fund(), "giver": giver,
                "note": note}

    def test_edit_offering_saves_in_place_and_the_totals_follow(self):
        pid = self.first_person_id()
        oid = money.add_offering(self.db(), TODAY.isoformat(), 10_000_000, self.fund(), giver_person_id=pid,
                                 note="C1A Hộp ghi nhầm")
        conn = self.db()
        before = money.month_totals(conn, TODAY.year, TODAY.month)
        st_before = money.giving_statement(conn, TODAY.year, person_id=pid)["total"]
        count = conn.execute("SELECT COUNT(*) FROM offering").fetchone()[0]

        offerings = section(self.page(f"/money?month={MONTH}"), "offerings")
        self.assertIn(f'href="/money/offerings/{oid}/edit"', offerings)  # an Edit link on the row
        self.assertIn('class="edit no-print"', offerings)                # never printed
        form = self.page(f"/money/offerings/{oid}/edit")
        self.assertEqual(parse_panels(form).h1, 1)
        self.assertIn("<h1>Edit Offering</h1>", form)
        self.assertIn('value="10.000.000 ₫"', form)                      # shown with format_vnd
        self.assertIn(f'<option value="person-{pid}" selected>', form)
        self.assertIn(f'value="{TODAY.isoformat()}"', form)
        self.assertIn("C1A Hộp ghi nhầm</textarea>", form)               # the note stays in its field
        delete_box = section(form, "delete")
        self.assertIn(f'action="/money/offerings/{oid}/delete"', delete_box)
        self.assertIn('class="btn danger"', delete_box)
        self.assertLess(form.index('name="amount"'), form.index('data-panel="delete"'))  # Delete comes last

        # the amount typed the way the page shows it ("1.000.000 ₫") is read by parse_amount
        headers, _ = self.post(f"/money/offerings/{oid}/edit",
                               self.offering_form(money.format_vnd(1_000_000), f"person-{pid}", self.fund("Building"),
                                                  note="C1A đã sửa"))
        self.assertTrue(headers["location"].startswith(f"/money?month={MONTH}&msg="), headers["location"])
        conn = self.db()
        row = money.get_offering(conn, oid)
        self.assertEqual((row["amount"], type(row["amount"]), row["fund_name"], row["note"]),
                         (1_000_000, int, "Building", "C1A đã sửa"))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM offering").fetchone()[0], count)  # no new row
        after = money.month_totals(conn, TODAY.year, TODAY.month)
        self.assertEqual(before["offerings"] - after["offerings"], 9_000_000)
        self.assertEqual(before["balance"] - after["balance"], 9_000_000)
        self.assertEqual(st_before - money.giving_statement(conn, TODAY.year, person_id=pid)["total"], 9_000_000)

        page = self.page(headers["location"])
        self.assertIn(f"Offering saved: 1.000.000 ₫ on {shown(TODAY.isoformat())} (Building).", page)
        figures = amounts_in(section(page, "offerings"))
        self.assertEqual(sum(figures[:-1]), figures[-1])
        self.assertEqual(figures[-1], after["offerings"])
        self.assertIn(money.format_vnd(after["balance"]), section(page, "money-totals"))
        sheet = section(self.page(f"/money/statement?person_id={pid}&year={TODAY.year}"), "statement")
        self.assertEqual(amounts_in(sheet)[-1], st_before - 9_000_000)
        self.assertNotIn("/edit", sheet)  # the Giving statement has no Edit column

    def test_edit_offering_refusals(self):
        oid = money.add_offering(self.db(), TODAY.isoformat(), 2_000_000, self.fund())
        before = tuple(money.get_offering(self.db(), oid))
        _h, page = self.post(f"/money/offerings/{oid}/edit", self.offering_form("1,5"), expect=400)
        self.assertIn('id="f-amount-error"', page)  # the sentence sits next to the Amount field
        self.assertIn("not understood", page)
        self.assertIn('value="1,5"', page)          # the form keeps what was typed
        self.assertIn("<h1>Edit Offering</h1>", page)
        _h, page = self.post(f"/money/offerings/{oid}/edit", self.offering_form("1000", giver="person-abc"), expect=400)
        self.assertIn("Giver must be", page)
        tomorrow = (TODAY + dt.timedelta(days=1)).isoformat()
        _h, page = self.post(f"/money/offerings/{oid}/edit", self.offering_form("1000", day=tomorrow), expect=400)
        self.assertIn("Date cannot be after today", page)
        # without the right Origin nothing is saved or deleted
        for path, form in ((f"/money/offerings/{oid}/edit", self.offering_form("1000")),
                           (f"/money/offerings/{oid}/delete", {"confirm": "yes"})):
            for extra in ({"origin": False}, {"origin": False, "headers": {"Origin": "http://evil.example"}}):
                status, _h, _d = self.request("POST", path, form, **extra)
                self.assertEqual(status, 403, (path, extra))
        self.assertEqual(tuple(money.get_offering(self.db(), oid)), before)
        # an Offering that does not exist
        self.page("/money/offerings/999999/edit", expect=404)
        self.post("/money/offerings/999999/edit", self.offering_form("1000"), expect=404)
        self.post("/money/offerings/999999/delete", {"confirm": "yes"}, expect=404)

    def test_delete_offering_asks_first_and_names_the_row(self):
        pid = self.first_person_id()
        day = f"{MONTH}-01"
        oid = money.add_offering(self.db(), day, 1_234_000, self.fund(), giver_person_id=pid)
        before = money.month_totals(self.db(), TODAY.year, TODAY.month)
        st_before = money.giving_statement(self.db(), TODAY.year, person_id=pid)["total"]
        _h, page = self.post(f"/money/offerings/{oid}/delete", {}, expect=200)  # no confirm: one question first
        question = re.sub(r"<[^>]+>", "", section(page, "confirm"))
        self.assertIn(f"Delete this Offering of 1.234.000 ₫ on {shown(day)}?", question)
        self.assertIn(fake.FIRST_PERSON, question)
        self.assertIn('name="confirm" value="yes"', page)
        self.assertIsNotNone(money.get_offering(self.db(), oid))  # still there

        headers, _ = self.post(f"/money/offerings/{oid}/delete", {"confirm": "yes"})
        self.assertTrue(headers["location"].startswith(f"/money?month={day[:7]}&msg="), headers["location"])
        self.assertIsNone(money.get_offering(self.db(), oid))
        after = money.month_totals(self.db(), TODAY.year, TODAY.month)
        self.assertEqual(before["offerings"] - after["offerings"], 1_234_000)
        self.assertEqual(st_before - money.giving_statement(self.db(), TODAY.year, person_id=pid)["total"], 1_234_000)
        page = self.page(headers["location"])
        self.assertIn(f"Offering of 1.234.000 ₫ on {shown(day)} deleted.", page)
        self.assertNotIn(f"/money/offerings/{oid}/edit", page)

    def test_a_hidden_fund_stays_on_the_edit_form(self):
        conn = self.db()
        old_fund = lists.add_item(conn, "fund", "C1A Quỹ cũ")
        oid = money.add_offering(conn, TODAY.isoformat(), 500_000, old_fund)
        lists.set_active(conn, old_fund, False)
        self.assertNotIn("C1A Quỹ cũ", self.page("/money/offerings/new"))  # hidden: not offered for new rows
        form = self.page(f"/money/offerings/{oid}/edit")
        self.assertIn(f'<option value="{old_fund}" selected>C1A Quỹ cũ (hidden)</option>', form)
        self.post(f"/money/offerings/{oid}/edit", self.offering_form("600.000", fund=old_fund))
        row = money.get_offering(self.db(), oid)
        self.assertEqual((row["fund_id"], row["amount"]), (old_fund, 600_000))

    def test_edit_and_delete_pages_escape_what_was_typed(self):
        events = self.category("Events")
        eid = money.add_expense(self.db(), TODAY.isoformat(), 10_000, events, note='<script>alert(1)</script> "C1A"')
        for page in (self.page(f"/money/expenses/{eid}/edit"),
                     self.post(f"/money/expenses/{eid}/delete", {}, expect=200)[1]):
            self.assertNotIn("<script>alert", page)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)

    def test_edit_and_delete_expense(self):
        events = self.category("Events")
        eid = money.add_expense(self.db(), TODAY.isoformat(), 6_500_000, events, note="C1A Hoa ghi nhầm")
        before = money.month_totals(self.db(), TODAY.year, TODAY.month)
        expenses = section(self.page("/money"), "expenses")
        self.assertIn(f'href="/money/expenses/{eid}/edit"', expenses)
        form = self.page(f"/money/expenses/{eid}/edit")
        self.assertIn("<h1>Edit Expense</h1>", form)
        self.assertIn('value="6.500.000 ₫"', form)
        self.assertIn(f'<option value="{events}" selected>Events</option>', form)
        self.assertIn("C1A Hoa ghi nhầm</textarea>", form)
        self.assertIn(f'action="/money/expenses/{eid}/delete"', section(form, "delete"))

        good = {"date": TODAY.isoformat(), "amount": "650.000", "spending_category_id": events, "note": "C1A Hoa"}
        _h, page = self.post(f"/money/expenses/{eid}/edit", {**good, "amount": "2,5"}, expect=400)
        self.assertIn('id="f-amount-error"', page)
        self.assertIn('value="2,5"', page)
        self.assertEqual(money.get_expense(self.db(), eid)["amount"], 6_500_000)
        status, _h, _d = self.request("POST", f"/money/expenses/{eid}/edit", good, origin=False)
        self.assertEqual(status, 403)
        headers, _ = self.post(f"/money/expenses/{eid}/edit", good)
        self.assertTrue(headers["location"].startswith(f"/money?month={MONTH}&msg="))
        row = money.get_expense(self.db(), eid)
        self.assertEqual((row["amount"], type(row["amount"]), row["note"]), (650_000, int, "C1A Hoa"))
        after = money.month_totals(self.db(), TODAY.year, TODAY.month)
        self.assertEqual(before["expenses"] - after["expenses"], 5_850_000)
        page = self.page(headers["location"])
        self.assertIn(f"Expense saved: 650.000 ₫ on {shown(TODAY.isoformat())} (Events).", page)
        self.assertEqual(amounts_in(section(page, "expenses"))[-1], after["expenses"])

        _h, page = self.post(f"/money/expenses/{eid}/delete", {}, expect=200)
        question = re.sub(r"<[^>]+>", "", section(page, "confirm"))
        self.assertIn(f"Delete this Expense of 650.000 ₫ on {shown(TODAY.isoformat())}?", question)
        self.assertIn("C1A Hoa", question)
        headers, _ = self.post(f"/money/expenses/{eid}/delete", {"confirm": "yes"})
        self.assertIsNone(money.get_expense(self.db(), eid))
        self.assertEqual(after["expenses"] - money.month_totals(self.db(), TODAY.year, TODAY.month)["expenses"],
                         650_000)
        self.assertIn("Expense of 650.000 ₫", self.page(headers["location"]))
        self.page(f"/money/expenses/{eid}/edit", expect=404)
        self.post(f"/money/expenses/{eid}/delete", {"confirm": "yes"}, expect=404)

    def test_a_date_before_1900_is_refused_next_to_the_date(self):
        """B18: such a row would be in no Money month. Add and Edit, Offering and Expense."""
        conn = self.db()
        events = self.category("Events")
        oid = money.add_offering(conn, TODAY.isoformat(), 70_000, self.fund())
        eid = money.add_expense(conn, TODAY.isoformat(), 80_000, events)
        rows = (tuple(money.get_offering(conn, oid)), tuple(money.get_expense(conn, eid)))
        counts = [conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("offering", "expense")]
        sentence = '<p class="error" id="f-date-error">Date: use a year from 1900 to 9999.</p>'
        for path in ("/money/offerings/new", f"/money/offerings/{oid}/edit", "/money/expenses/new",
                     f"/money/expenses/{eid}/edit"):
            self.assertRegex(self.page(path), r'name="date" type="date" value="[0-9-]+" min="1900-01-01" max=')
            form = (self.offering_form("1000") if "offerings" in path else
                    {"date": "", "amount": "1000", "spending_category_id": events, "note": ""})
            for day in ("0001-01-01", "1899-12-31"):
                _h, page = self.post(path, {**form, "date": day}, expect=400)
                self.assertIn(sentence, page, (path, day))
        conn = self.db()
        self.assertEqual((tuple(money.get_offering(conn, oid)), tuple(money.get_expense(conn, eid))), rows)
        self.assertEqual([conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("offering", "expense")],
                         counts)  # nothing saved
        # 1900-01-01 is saved and shown in the month 1900-01
        headers, _ = self.post("/money/offerings/new", self.offering_form("1.900.000", day="1900-01-01"))
        self.assertTrue(headers["location"].startswith("/money?month=1900-01&msg="), headers["location"])
        page = self.page(headers["location"])
        self.assertIn("1.900.000 ₫", section(page, "offerings"))
        self.assertIn(shown("1900-01-01"), section(page, "offerings"))
        self.assertIn("1.900.000 ₫", section(self.page("/money?month=1900-01"), "money-totals"))


if __name__ == "__main__":
    unittest.main()
