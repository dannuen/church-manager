"""FIX-T 1b: the UI minors the tester found, through the real server (port 0, a fake church in a temp
folder, Host and Origin headers) and in ``web/style.css``.

B6 Record Offering has the Note. B7 the Family page has one link to its edit page. B9 the Expense Note
column keeps about 16ch and dates stay on one line. B10 a Sent document subject and the Care log text
wrap to 2 lines (full text in the title) instead of one cut line. B11 the Dashboard panels under the
first row keep their own height. B12 one filled primary button on the Person page and on a Calendar item.
"""

import datetime as dt
import re
import unittest

import _support  # noqa: F401 - puts the repo root on sys.path
from churchmgr import calendar as cal
from churchmgr import care, lists, money, people, sent
from test_pages_people import ROOT, TODAY, PagesTestBase, section
from test_server import PANELS, parse_panels

PRIMARY = 'class="btn primary"'
YESTERDAY = (TODAY - dt.timedelta(days=1)).isoformat()


def css_rules():
    """``[(selector, declarations)]`` of ``web/style.css``, comments removed (a rule in ``@media`` too)."""
    css = re.sub(r"/\*.*?\*/", "", (ROOT / "web" / "style.css").read_text(encoding="utf-8"), flags=re.S)
    return [(sel.strip(), body) for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)]


def declarations(selector):
    """Every declaration block whose selector list holds exactly ``selector``."""
    found = [body for sel, body in css_rules() if selector in (s.strip() for s in sel.split(","))]
    assert found, f"no CSS rule for {selector!r}"
    return " ".join(found)


class UiMinorsTest(PagesTestBase):
    def test_b6_record_offering_has_the_note_and_saves_it(self):
        self.assertIn('<textarea class="input" id="f-note"', self.page("/money/offerings/new"))
        fund = lists.find_item(self.db(), "fund", name="General")["id"]
        note = "FIX-T B6 Dâng cho quỹ xây dựng"
        form = {"date": TODAY.isoformat(), "amount": "250.000", "fund_id": fund, "giver": "", "note": note}
        _h, page = self.post("/money/offerings/new", {**form, "amount": "1,5"}, expect=400)
        self.assertIn(f"{note}</textarea>", page)  # a refused form keeps the Note that was typed
        self.post("/money/offerings/new", form)
        oid = self.db().execute("SELECT MAX(id) FROM offering").fetchone()[0]
        row = money.get_offering(self.db(), oid)
        self.assertEqual((row["amount"], row["note"]), (250_000, note))
        self.assertIn(f"{note}</textarea>", self.page(f"/money/offerings/{oid}/edit"))  # shown on Edit

    def test_b7_the_family_page_has_one_edit_link(self):
        fid = people.list_families(self.db())[0]["id"]
        page = self.page(f"/families/{fid}")
        self.assertEqual(page.count(f'href="/families/{fid}/edit"'), 1)
        self.assertIn(f'<a class="btn secondary" href="/families/{fid}/edit">Edit Family</a>', page)
        self.assertNotIn("Edit name or Address", page)

    def test_b9_the_expense_note_keeps_16ch_and_dates_and_amounts_stay_on_one_line(self):
        events = lists.find_item(self.db(), "spending_category", name="Events")["id"]
        money.add_expense(self.db(), TODAY.isoformat(), 1_500_000, events, note="FIX-T B9 Thuê hội trường")
        page = self.page("/money")
        expenses = section(page, "expenses")
        self.assertIn('<th scope="col" class="note">Note</th>', expenses)
        self.assertIn('<td class="note"><span lang="vi">FIX-T B9 Thuê hội trường</span></td>', expenses)
        self.assertIn('<th scope="col" class="category">Spending category</th>', expenses)
        self.assertIn('<td class="n"><span class="num">1.500.000 ₫</span></td>', expenses)
        for panel_name in ("expenses", "offerings"):
            cells = re.findall(r'<td( class="[^"]*")?><span class="num">\d\d/\d\d/\d{4}</span></td>',
                               section(page, panel_name))
            self.assertTrue(cells and set(cells) == {' class="date"'}, panel_name)  # every date cell
        self.assertIn("min-width: 16ch", declarations("table.money td.note"))
        self.assertIn("white-space: nowrap", declarations("table.money td.date"))
        self.assertIn("white-space: nowrap", declarations("table.money td.n"))
        self.assertIn("text-align: right", declarations("td.n"))
        self.assertIn("tabular-nums", declarations("table"))
        self.assertIn("white-space: normal", declarations("table.money th.category"))  # the header may wrap

    def test_b10_long_text_wraps_to_two_lines_with_the_full_text_in_the_title(self):
        conn = self.db()
        subject = "FIX-T B10 Báo cáo năm về sinh hoạt của Hội Thánh, các Chi phái và các Ban ngành gửi Giáo hội"
        _id, number = sent.add_sent_document(conn, TODAY.isoformat(), lists.find_item(conn, "recipient",
                                                                                         name="Giáo hội")["id"],
                                             lists.find_item(conn, "purpose", name="Report")["id"], subject)
        dash = section(self.page("/"), "sent-documents")
        self.assertIn(f'<span class="clamp-2" title="{number} {subject}"><span class="num nowrap">{number}</span> '
                      f'<span lang="vi">{subject}</span></span>', dash)
        # the Care log of a Person: the Family name and the note
        family = "FIX-T B10 Gia đình Nguyễn Thị Phương Thảo và Trần Văn Hoàng Long"
        note = "FIX-T B10 Thăm cả nhà, cầu nguyện cho bà ngoại đang nằm viện và cho các cháu đi học xa nhà."
        fid = people.add_family(conn, family, "12 Lê Lợi")
        pid = people.add_person(conn, "FIX-T B10 Trần Văn Hoàng Long", status_id=lists.find_item(
            conn, "status", code="member")["id"], start_date=YESTERDAY)
        people.set_family(conn, pid, fid, "Head", YESTERDAY)
        care.mark_visit_done(conn, care.plan_visit(conn, f"{TODAY.isoformat()} 09:00", family_id=fid),
                             TODAY.isoformat(), note)
        log = section(self.page(f"/people/{pid}"), "care-log")
        self.assertIn(f'<span class="what wrap"><span class="clamp-2" lang="vi" title="{family}">{family}</span>', log)
        self.assertIn(f'<span class="clamp-2 sub" lang="vi" title="{note}">{note}</span>', log)
        self.assertIn('class="figure num"', log)
        clamp = declarations(".clamp-2")
        for rule in ("-webkit-line-clamp: 2", "line-clamp: 2", "display: -webkit-box", "white-space: normal"):
            self.assertIn(rule, clamp)
        self.assertIn("white-space: normal", declarations(".row .what.wrap"))
        self.assertIn("white-space: nowrap", declarations(".nowrap"))  # the number stays on one line
        self.assertIn("white-space: nowrap", declarations(".row .figure"))  # and the date
        css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"@media print \{[^}]*\.clamp-2[^}]*line-clamp: none;")  # paper shows all of it

    def test_b11_dashboard_panels_under_the_first_row_do_not_stretch(self):
        for name in ("services", "money-month", "sent-documents"):
            self.assertIn("align-self: start", declarations(f'.dashboard > [data-panel="{name}"]'), name)
        self.assertEqual(set(parse_panels(self.page("/")).rows), PANELS)  # still the six panels

    def test_b12_one_filled_primary_button_per_screen(self):
        pid = people.list_persons(self.db())[0]["id"]
        page = self.page(f"/people/{pid}")
        self.assertEqual(page.count(PRIMARY), 1)
        self.assertIn(f'<a class="btn primary" href="/care?person_id={pid}#plan">Plan a Visit</a>', page)
        for label in ("Change Status", "Save Family", "Save Ministry"):
            self.assertIn(f'<button class="btn secondary" type="submit">{label}</button>', page)
        # a past Service shows its Head count form and the Edit form; a Meeting only the Edit form
        conn = self.db()
        service = cal.add_calendar_item(conn, "Service", "FIX-T B12 Thờ phượng", f"{YESTERDAY} 08:00")[0]
        meeting = cal.add_calendar_item(conn, "Meeting", "FIX-T B12 Họp", f"{YESTERDAY} 19:00")[0]
        for iid in (service, meeting):
            page = self.page(f"/calendar/{iid}")
            self.assertEqual(page.count(PRIMARY), 1, iid)
            self.assertIn('<button class="btn primary" type="submit">Save</button>', section(page, "edit"))
            buttons = re.findall(r'class="btn (\w+)"', page)
            self.assertEqual(buttons[-1], "danger")  # Delete comes last, in the negative colour
        page = self.page(f"/calendar/{service}")
        self.assertIn('<button class="btn secondary" type="submit">Save Head count</button>', page)
        _h, confirm = self.post(f"/calendar/{service}/delete", {}, expect=200)
        self.assertIn("FIX-T B12 Thờ phượng", section(confirm, "confirm"))  # the confirm names it


if __name__ == "__main__":
    unittest.main()
