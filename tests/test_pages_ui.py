"""FIX-T 1b: the UI minors the tester found, through the real server (port 0, a fake church in a temp
folder, Host and Origin headers) and in ``web/style.css``.

B6 Record Offering has the Note. B7 the Family page has one link to its edit page. B9 the Expense Note
column keeps about 16ch and dates stay on one line. B10 a Sent document subject and the Care log text
wrap to 2 lines (full text in the title) instead of one cut line. B11 the Dashboard panels under the
first row keep their own height. B12 one filled primary button on the Person page and on a Calendar item.
FIX-T 2b (class UiMinorsRound2Test): B15 B16 B17 B19.
FIX-T 4b (class UiMinorsRound4Test): B25 no action words on paper, B26 row titles wrap to 2 lines.
STYLE-2 (class StyleTokensTest): every color of style.css is a token, made from the app color.
STYLE-4 (classes FormsAndButtonsTest, FormControlsTest): pills, one control height, the states and one
focus ring that no rule takes away; every form control of a page carries a class that style.css styles.
STYLE-5 (class CardsAndChartsTest): cards, the one dark card, green and red on money only.
STYLE-6 (class PrintAndFinalWalkTest): paper is ink on white; the faults of the final walk stay fixed.
STYLE-FIX-1 (class StyleFix1Test): the wash grows with the head; the Dashboard language switch and a flash;
a table's own scroll box; Money this month fits row 2 in an empty month.
STYLE-FIX-2 (class StyleFix2Test): a Dashboard list row is as tall as its 2-line title (no overlap).
STYLE-FIX-3 (class StyleFix3Test): Dashboard row 1 always shows one whole row in This week and Needs a
visit (no fixed 150px floor); up to 720px high the space around row 1 is tighter and the hint is one line.
CRIT-1 (class CritOneTest): links in the app color, row actions at weight 400, a whole table row opens its
page, and every small action is a 44px tap under 861px.
CRIT-4 (class CritFourTest): the Dashboard card of today and the 6 days after is "Next 7 days"; the DASH RULE:
no Dashboard list scrolls inside its card, each shows a fixed number of rows and names the full count.
CRIT-2 (class CritTwoTest): under 861px the menu is 5 items and a More fold (no sideways scroll); a skip link
is the first stop of every page.
CRIT-3 (class CritThreeTest): under 861px the title-row actions sit side by side, the primary first; no number
or button twice in the head of People, Money, Sent documents and the Dashboard.
CRIT-6 (class CritSixTest): in the People list a Person who Left or Passed away keeps the row, muted, with the
Status as a tag; the All list keeps everyone (the pastor chose A).
CRIT-7 (class CritSevenTest): the one dark card is Needs a visit (the pastor chose B); Money this month is a
white card; a name on the dark card is underlined to show it is a link.
CRIT-8 (class CritEightTest): the Calendar and Money period bar: Prev / This / Next on one line, the month
chips say MM/YYYY, the month picker opens a month on change with app.js (Show stays without it).
CRIT-9 (class CritNineTest): in the Calendar an empty day is its date and a faint dash (the sentence for screen
readers only); a date is lighter than the titles of its items.
"""

import datetime as dt
import itertools
import re
import unittest
import urllib.parse
from html.parser import HTMLParser

import _support  # noqa: F401 - puts the repo root on sys.path
from churchmgr import app_color, care, documents, lists, money, people, sent, ui
from churchmgr import calendar as cal
from churchmgr.pages import dashboard
from test_pages_people import ROOT, TODAY, VOID, PagesTestBase, section
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


class UiMinorsRound2Test(PagesTestBase):
    """FIX-T 2b. B15 a Document name wraps to 2 lines (Person, Family and Calendar item pages). B16 the
    Dashboard Sent documents line "date · Recipient · Purpose" wraps to 2 lines. B17 the Dashboard row 2
    is 4 + 4 + 4 columns, 2 Sent document rows and a chart of one height. B19 a Handover zip name shows
    whole."""

    def test_b15_a_document_name_wraps_to_two_lines_with_the_full_name_in_the_title(self):
        conn = self.db()
        name = "FIX-T B15 Chứng nhận Báp-têm - Nguyễn Hải Đăng và gia đình, tháng 10 năm 2026.txt"
        pid = people.list_persons(conn)[0]["id"]
        fid = people.list_families(conn)[0]["id"]
        iid = cal.add_calendar_item(conn, "Meeting", "FIX-T B15 Họp", f"{YESTERDAY} 19:00")[0]
        for key, rid, path in (("person_id", pid, f"/people/{pid}"), ("family_id", fid, f"/families/{fid}"),
                               ("calendar_item_id", iid, f"/calendar/{iid}")):
            did = documents.add_document(conn, self.copy, b"FIX-T B15 file", name, **{key: rid})
            panel = section(self.page(path), "documents")
            self.assertIn(f'<li class="row" data-row><span class="what wrap"><span class="clamp-2" lang="vi" '
                          f'title="{name}"><a href="/documents/{did}/file">{name}</a></span>'
                          '<span class="sub num">', panel)
        self.assertIn("white-space: normal", declarations(".row .what.wrap"))
        self.assertIn("-webkit-line-clamp: 2", declarations(".row .what .clamp-2"))

    def test_b16_the_sent_documents_line_wraps_with_the_full_text_in_the_title(self):
        conn = self.db()
        sent.add_sent_document(conn, TODAY.isoformat(), lists.find_item(conn, "recipient", name="Chính quyền")["id"],
                               lists.find_item(conn, "purpose", name="Certificate")["id"], "FIX-T B16 Xin phép")
        dash = section(self.page("/"), "sent-documents")
        day = ui.fmt_date(TODAY.isoformat())
        full = f"{day} · Chính quyền · Certificate"
        # a "·" stays with the word after it (no-break space): no line ends on a dangling "·"
        line = f'{day} ·\u00a0<span lang="vi">Chính quyền</span> ·\u00a0Certificate'
        self.assertIn(f'<span class="clamp-2 sub" title="{full}">{line}</span>', dash)
        self.assertNotIn('<span class="sub" title=', dash)  # no one-line cut line is left
        # inside .what the clamp wins over the one-line ".row .sub" rule
        self.assertIn("white-space: normal", declarations(".row .what .clamp-2"))

    def test_b17_dashboard_row_two_is_4_4_4_with_two_sent_rows_and_a_chart_of_one_height(self):
        conn = self.db()
        recipient = lists.find_item(conn, "recipient", name="Giáo hội")["id"]
        purpose = lists.find_item(conn, "purpose", name="Report")["id"]
        for i in range(3):
            sent.add_sent_document(conn, TODAY.isoformat(), recipient, purpose, f"FIX-T B17 Báo cáo {i}")
        page = self.page("/")
        spans = {name: re.search(rf'<section class="panel (span-\d+)" data-panel="{name}"', page).group(1)
                 for name in ("services", "money-month", "sent-documents")}
        self.assertEqual(spans, {"services": "span-4", "money-month": "span-4", "sent-documents": "span-4"})
        self.assertEqual(sum(int(s.split("-")[1]) for s in spans.values()), 12)  # the row fills the 12 columns
        listing = section(page, "sent-documents")
        self.assertEqual(listing.count('<li class="row" data-row>'), 2)  # 2 recent rows, newest first
        self.assertIn("FIX-T B17 Báo cáo 2", listing)
        self.assertNotIn("FIX-T B17 Báo cáo 0", listing)
        count = len(sent.list_sent_documents(conn, TODAY.year))
        self.assertIn(f'<span class="meta">{count} Sent documents in {TODAY.year}</span>', listing)
        self.assertIn(f'<footer><a class="card-link" href="/sent">View all {count}</a></footer>', listing)  # CRIT-4
        services = section(page, "services")
        self.assertIn(f'<svg class="chart" width="100%" height="{dashboard.CHART_HEIGHT}" role="img"', services)
        self.assertIn('<footer><a class="card-link" href="/calendar">Calendar</a></footer>', services)
        # the chart: x places in percent, one height, every second date from the last when more than 5
        rows = [{"starts_at": f"2026-09-{d:02d} 08:00", "count": 50 + d} for d in range(1, 9)]
        svg = dashboard.services_svg(rows)
        self.assertNotIn('<svg class="chart" viewBox', svg)
        labels = re.findall(r'text-anchor="middle">(\d\d/\d\d)</text>', svg)
        self.assertEqual(labels, ["02/09", "04/09", "06/09", "08/09"])
        self.assertIn('<polyline class="line" points="0.00,', svg)
        self.assertIn(">58</text>", svg)  # the last value is labelled
        self.assertIn("vector-effect: non-scaling-stroke", declarations(".chart .line"))
        self.assertIn("overflow: visible", declarations(".chart"))
        for name in ("services", "money-month", "sent-documents"):  # B11: each keeps its own height
            self.assertIn("align-self: start", declarations(f'.dashboard > [data-panel="{name}"]'), name)

    def test_b19_a_handover_zip_name_shows_whole(self):
        headers = self.post("/copies/handover", {})[0]
        name = urllib.parse.parse_qs(urllib.parse.urlsplit(headers["location"]).query)["made"][0]
        self.assertRegex(name, r"^handover-[a-z0-9-]+-\d{4}-\d{2}-\d{2}(-\d+)?\.zip$")
        panel = section(self.page("/copies"), "handover")
        self.assertIn(f'<li class="row" data-row><span class="what wrap"><a class="file-name" '
                      f'href="/copies/handovers/{name}">{name}</a></span><span class="side num">', panel)
        self.assertIn("overflow-wrap: anywhere", declarations(".row .what .file-name"))
        self.assertIn("white-space: normal", declarations(".row .what.wrap"))  # no one-line "…" cut


# ---------------------------------------------------------------- FIX-T 4b helpers

def print_hide_selectors():
    """The selectors of the hide rule of ``web/print.css``: the first rule inside ``@media print`` that
    says ``display: none !important``. Each selector is a list of ``(tag or None, {classes})`` parts,
    read left to right with a space between them (a descendant)."""
    css = re.sub(r"/\*.*?\*/", "", (ROOT / "web" / "print.css").read_text(encoding="utf-8"), flags=re.S)
    media = css[css.index("@media print"):]
    selector_list = next(sel for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", media[media.index("{") + 1:])
                         if re.search(r"display:\s*none\s*!important", body))
    out = []
    for selector in (s.strip() for s in selector_list.split(",")):
        parts = []
        for part in selector.split():
            m = re.fullmatch(r"([a-z][a-z0-9]*)?((?:\.[a-zA-Z0-9_-]+)*)", part)
            assert m and part, f"the test cannot read the print selector {selector!r}"
            parts.append((m.group(1), set(m.group(2).split(".")) - {""}))
        out.append((selector, parts))
    return out


def _part_matches(part, element):
    tag, classes = part
    return (tag is None or tag == element[0]) and classes <= element[1]


def selector_matches(parts, chain):
    """Does the selector (``parts``) match the last element of ``chain`` (root first)?"""
    if not _part_matches(parts[-1], chain[-1]):
        return False
    i = len(chain) - 2
    for part in reversed(parts[:-1]):
        while i >= 0 and not _part_matches(part, chain[i]):
            i -= 1
        if i < 0:
            return False
        i -= 1
    return True


class OnPaper(HTMLParser):
    """Every link, button and summary of a page with its text and its href, and whether print.css
    hides it (a hide selector matches it or one of the elements around it)."""

    def __init__(self, selectors):
        super().__init__(convert_charrefs=True)
        self.selectors, self.stack, self.found, self.open = selectors, [], [], []

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        a = dict(attrs)
        chain = [(t, c) for t, c, _hidden in self.stack] + [(tag, set((a.get("class") or "").split()))]
        hidden = bool(self.stack and self.stack[-1][2]) or any(
            selector_matches(parts, chain) for _sel, parts in self.selectors)
        self.stack.append((tag, chain[-1][1], hidden))
        if tag in ("a", "button", "summary"):
            item = {"tag": tag, "href": a.get("href") or "", "hidden": hidden, "text": "", "depth": len(self.stack)}
            self.found.append(item)
            self.open.append(item)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
        self.open = [item for item in self.open if item["depth"] <= len(self.stack)]

    def handle_data(self, data):
        for item in self.open:
            item["text"] += data


def on_paper(page):
    parser = OnPaper(print_hide_selectors())
    parser.feed(page)
    for item in parser.found:
        item["text"] = " ".join(item["text"].split())
    return parser.found


ACTION_WORDS = {"Delete", "Edit", "Plan", "Record", "Edit details", "Plan a Visit", "Add a Family",
                "Record Offering", "Record Expense", "Rename", "Cancel", "Retry", "Calendar"}
ACTION_STARTS = ("View all ", "Open ", "Show all ", "Mark it done")


def is_action(text_):
    return text_ in ACTION_WORDS or text_.startswith(ACTION_STARTS)


def row_items(html_text):
    """The inner HTML of each ``<li class="row ..." data-row>`` (rows are never nested)."""
    return re.findall(r'<li class="row[^"]*" data-row>(.*?)</li>', html_text, re.S)


CLAMPED_TITLE = re.compile(r'<span class="what wrap"><span class="clamp-2"(?: lang="vi")? title="([^"]+)">')


class UiMinorsRound4Test(PagesTestBase):
    """FIX-T 4b. B25 no action words on paper: the hide rule of print.css covers every text action.
    B26 the title of every row list wraps to 2 lines (full text in its title); the grey side text gets
    at most 30% of the row, one line, full text in its title."""

    def test_b25_no_action_words_on_paper(self):
        conn = self.db()
        pid = people.list_persons(conn)[0]["id"]
        money.add_offering(conn, TODAY.isoformat(), 100_000, lists.find_item(conn, "fund", name="General")["id"])
        cal.add_calendar_item(conn, "Service", "FIX-T B25 Thờ phượng", f"{YESTERDAY} 08:00")  # Record
        people.add_private_note(conn, pid, "FIX-T B25 ghi chú")  # its Edit link
        selectors = [sel for sel, _parts in print_hide_selectors()]
        for sel in (".card-link", ".row-action", ".note-edit", ".form-actions", "td.edit", "th.edit",
                    "td.act", "th.act"):
            self.assertIn(sel, selectors)
        paths = ("/documents", "/care", f"/people/{pid}", "/", "/money", "/calendar", "/lists")
        hidden_words, data_links = set(), {}
        for path in paths:
            found = on_paper(self.page(path))
            for item in found:
                if is_action(item["text"]):
                    self.assertTrue(item["hidden"], f"{path}: {item['tag']} {item['text']!r} shows on paper")
                    hidden_words.add(item["text"])
            data_links[path] = [i["href"] for i in found if not i["hidden"] and not is_action(i["text"])]
        for word in ("Delete", "Edit", "Plan", "Record", "Edit details", "Plan a Visit", "Add a Family",
                     "Record Offering", "Record Expense", "Rename"):
            self.assertIn(word, hidden_words)  # each one was on a page, and is hidden
        for start in ("View all ", "Open "):
            self.assertTrue(any(w.startswith(start) for w in hidden_words), start)
        # links that are data stay on paper (as ink text)
        self.assertTrue(any(re.fullmatch(r"/documents/\d+/file", href) for href in data_links["/documents"]))
        self.assertTrue(any(re.fullmatch(r"/people/\d+", href) for href in data_links["/care"]))
        self.assertTrue(any(re.fullmatch(r"/calendar/\d+", href) for href in data_links["/"]))
        # the Documents Delete column goes whole: its header and every cell have the class act
        docs = section(self.page("/documents"), "documents-list")
        self.assertEqual(docs.count('<th scope="col" class="act"></th>'), 1)
        self.assertEqual(docs.count('<td class="act"><a href="/documents/'), docs.count("<tr data-row>"))
        self.assertIn(".list-head .spacer", selectors)  # Care: no empty Plan column in the list head
        # a panel that is only a form is not a heading over nothing on paper
        self.assertIn('<section class="panel no-print" data-panel="plan"', self.page("/care"))
        self.assertIn('<section class="panel no-print" data-panel="statement-picker"', self.page("/money"))
        self.assertIn('<p class="hint list-foot no-print">To add a Document', self.page("/documents"))

    def test_b26_row_titles_wrap_to_two_lines_and_the_side_gets_30_percent(self):
        conn = self.db()
        title, place = "Lễ Tạ Ơn – Thờ phượng Chúa Nhật", "Sân nhà thờ lớn phía sau hội trường"
        today_id = cal.add_calendar_item(conn, "Service", title, f"{TODAY.isoformat()} 06:00", place=place)[0]
        to_record = "Thờ phượng Chúa Nhật vòng 3"
        record_id = cal.add_calendar_item(conn, "Service", to_record, f"{YESTERDAY} 09:00")[0]
        week = section(self.page("/"), "this-week")
        self.assertIn(f'<span class="what wrap"><span class="clamp-2" lang="vi" title="{title}">'
                      f'<a href="/calendar/{today_id}">{title}</a></span></span>'
                      f'<span class="side" title="Service · {place}">Service · <span lang="vi">{place}</span></span>',
                      week)
        record = section(self.page("/calendar"), "to-record")
        self.assertIn(f'<span class="what wrap"><span class="clamp-2" lang="vi" title="{to_record}">'
                      f'<a href="/calendar/{record_id}#head-count">{to_record}</a></span>', record)
        side = declarations(".row .side")
        self.assertIn("max-width: 30%", side)
        self.assertIn("flex: 0 1 auto", side)
        self.assertIn("text-overflow: ellipsis", side)
        # long names (120 characters at most): every row list puts its title in .clamp-2, whole in the title
        long_title = ("FIX-T B26 Hội nghị Chấp sự và Trưởng Chi phái toàn Hội Thánh bàn kế hoạch thăm viếng "
                      "các gia đình mới về Hội Thánh dịp cuối năm")[:120].rstrip()
        long_name = ("FIX-T B26 Nguyễn Trần Lê Phạm Hoàng Huỳnh Phan Vũ Võ Đặng Bùi Đỗ Hồ Ngô Dương Lý "
                     "Thị Minh Khai Phương Thảo Ngọc Bích Hồng Nhung Kim")[:120].rstrip()
        self.assertGreaterEqual(min(len(long_title), len(long_name)), 115)
        item = cal.add_calendar_item(conn, "Meeting", long_title, f"{TODAY.isoformat()} 19:00", place=place)[0]
        member = lists.find_item(conn, "status", code="member")["id"]
        person = people.add_person(conn, long_name, status_id=member, start_date=YESTERDAY)
        cal.add_person_to_item(conn, item, person, "serves")
        lists_by_page = (("/", "this-week"), ("/", "needs-visit"), ("/calendar", "calendar-list"),
                         ("/calendar", "to-record"), ("/care", "needs-visit"), ("/care", "care-log"),
                         (f"/calendar/{item}", "people"), ("/search?q=FIX-T+B26", None))
        for path, name in lists_by_page:
            page = self.page(path)
            html_text = section(page, name) if name else page
            rows = row_items(html_text)
            self.assertTrue(rows, (path, name))
            for row in rows:
                m = CLAMPED_TITLE.search(row)
                self.assertIsNotNone(m, (path, name, row[:300]))
                for side_span in re.findall(r'<span class="side"[^>]*>', row):
                    self.assertIn(' title="', side_span, (path, name))
        joined = "".join(self.page(p) for p in ("/calendar", "/care", f"/calendar/{item}", "/search?q=FIX-T+B26"))
        self.assertIn(f'title="{long_title}"', joined)
        self.assertIn(f'title="{long_name}"', joined)
        # one row height rule for every list: each part sits on the first line of the title
        self.assertIn("align-items: baseline", declarations(".row:has(> .what.wrap)"))
        self.assertIn("white-space: nowrap", declarations(".row .time"))


# ---------------------------------------------------------------- STYLE-2 helpers

# a raw color: #rgb, #rgba, #rrggbb, #rrggbbaa (an id such as #head-count is not one), rgb(), hsl()
RAW_HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![0-9a-zA-Z_-])")
RAW_FUNCTION = re.compile(r"\b(?:rgba?|hsla?)\([^)]*\)", re.IGNORECASE)
CSS_MIX = re.compile(r"color-mix\(in srgb, (#[0-9a-f]{6})(?: (\d+)%)?, (#[0-9a-f]{6})(?: (\d+)%)?\)")
SAMPLE_COLORS = ("#1f5c99", "#2c6e70", "#ffffcc", "#ffff00", "#00ff00", "#ff0000", "#808080", "#7f7fff",
                 "#000000", "#ffffff")
HIGHLIGHT_STOPS = ("--highlight", "--highlight-mid", "--highlight-end")  # the dark card, top left to bottom right
TEXT_PAIRS = (  # (text, what it sits on): at least 4.5:1
    *(("--text", s) for s in ("--surface", "--ground", "--raised", "--active")),
    *(("--muted", s) for s in ("--surface", "--ground", "--raised", "--active")),
    *(("--faint", s) for s in ("--surface", "--ground", "--raised")),
    ("--accent-text", "--surface"), ("--accent-text", "--ground"),  # the church name in the sidebar
    ("--negative", "--surface"), ("--negative", "--raised"), ("--positive", "--surface"),
    # the wash, the current menu item; the white pill of the title row is --accent-dark on --on-accent
    *(("--on-accent", s) for s in ("--accent-dark", "--accent-base", "--accent-light")),
    ("--accent-deep", "--active"),  # STYLE-4: the bold text of the current chip on its tint
    # STYLE-5, CRIT-7: the one dark card (Needs a visit): each text on each of its 3 stops (no money on it)
    *((fg, s) for fg in ("--highlight-ink", "--highlight-muted") for s in HIGHLIGHT_STOPS),
    # CRIT-1: a foot link on the dark card is its --accent-text (--highlight-focus)
    *(("--highlight-focus", s) for s in HIGHLIGHT_STOPS),
)
PART_PAIRS = (  # a field border or the focus ring: at least 3:1
    ("--control", "--surface"), ("--control", "--ground"), ("--control", "--raised"),
    ("--accent-text", "--surface"), ("--accent-text", "--ground"),
    # STYLE-4: the ring on the Private note panel and beside a tint; the edge of the current chip
    ("--accent-text", "--raised"), ("--accent-text", "--active"),
    *(("--highlight-focus", s) for s in HIGHLIGHT_STOPS),  # STYLE-5: the ring on the dark card
    *(("--highlight-line", s) for s in HIGHLIGHT_STOPS),  # CRIT-7: the line under a name on the dark card
)


def style_css(comments=False):
    css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
    return css if comments else re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def root_tokens():
    """``{token: value}`` of the one ``:root {…}`` block of ``web/style.css``."""
    body = re.search(r":root \{([^{}]*)\}", style_css()).group(1)
    declarations_ = (d.split(":", 1) for d in body.split(";") if d.strip())
    return {name.strip(): value.strip() for name, value in declarations_}


def token_color(tokens, name):
    """The ``#rrggbb`` a color token comes to: ``var()`` and ``color-mix(in srgb, …)`` worked out as the
    browser does (``app_color.mix``)."""
    value = re.sub(r"var\((--[\w-]+)\)", lambda m: token_color(tokens, m.group(1)), tokens[name]).lower()
    if re.fullmatch(r"#[0-9a-f]{6}", value):
        return value
    a, share_a, b, share_b = CSS_MIX.fullmatch(value).groups()
    return app_color.mix(a, b, int(share_b) if share_b else 100 - int(share_a) if share_a else 50)


class StyleTokensTest(unittest.TestCase):
    """STYLE-2: every color of ``web/style.css`` is a token of its ``:root`` block, and the tokens are made
    from the app color (Settings) so that text stays readable whatever color the pastor picks."""

    def test_style_uses_only_tokens(self):
        rest, blocks = re.subn(r":root \{[^{}]*\}", "", style_css())
        self.assertEqual(blocks, 1)
        raw = RAW_HEX.findall(rest) + RAW_FUNCTION.findall(rest)  # in @media rules too
        self.assertEqual(raw, [], "raw colors outside :root")
        self.assertNotIn("prefers-color-scheme", style_css(comments=True))  # light only

    def test_every_token_reads_on_its_surface_for_any_app_color(self):
        root = root_tokens()
        levels = range(0, 256, 51)
        colors = {"#%02x%02x%02x" % rgb for rgb in itertools.product(levels, repeat=3)} | set(SAMPLE_COLORS)
        low = []
        for color in sorted(colors):
            tokens = {**root, **app_color.theme(color)}  # what the page head sets for that color
            for pairs, need in ((TEXT_PAIRS, 4.5), (PART_PAIRS, 3.0)):
                for fg, bg in pairs:
                    ratio = app_color.contrast(token_color(tokens, fg), token_color(tokens, bg))
                    if ratio < need:
                        low.append((color, fg, bg, round(ratio, 2)))
        self.assertEqual(low, [])


class TablesAndListsTest(PagesTestBase):
    """STYLE-3: tables and lists. No page puts a ``style`` attribute in its HTML: every look is a class of
    style.css, so the one CSS pass reaches it. The Year report chart paints its bars and its legend keys
    with a class each, and style.css gives each class its color from a token (an SVG fill prints on
    paper: it is not a CSS background). A wide table scrolls inside its card; only a data row (never the
    total row) lights up under the pointer."""

    PAGES = ("/people", "/money", "/documents", "/money/year", "/families", "/chi-phai", "/sent")

    def test_pages_have_no_inline_style(self):
        for path in self.PAGES:
            page = self.page(path)
            self.assertFalse('style="' in page, (path, re.findall(r'<[^<>]* style="[^"]*"', page)))
        page = self.page("/money/year")
        svg = re.search(r'<svg class="year-chart"[^>]*>(.*?)</svg>', page, re.S).group(1)
        bars = re.findall(r"<rect [^>]*>", svg)
        self.assertEqual(len(bars), 24)  # 12 months, an Offerings bar and an Expenses bar each
        for kind in ("offerings", "expenses"):
            self.assertEqual(sum(f'class="bar-{kind}"' in bar for bar in bars), 12, kind)
            self.assertIn(f'<span class="bar-{kind}">\u25a0</span>', page)  # its legend key
            rule = declarations(f".bar-{kind}")
            self.assertIn(f"fill: var(--bar-{kind})", rule)
            self.assertIn(f"color: var(--bar-{kind})", rule)
        self.assertNotIn(" fill=", svg)  # the color comes from style.css only
        tokens = root_tokens()  # spec 3.3: the two bar colors stay as they were; they are tokens now
        self.assertEqual((tokens["--bar-offerings"], tokens["--bar-expenses"]), ("#2f6f4f", "#999999"))

    def test_a_wide_table_scrolls_inside_its_card_and_only_data_rows_light_up(self):
        self.assertIn("overflow-x: auto", declarations(".table-wrap"))
        self.assertIn("max-width: 100%", declarations(".table-wrap"))
        # in a panel the wrap is 24px wider than the panel's inside (12px each side): no cap, or the right
        # side would end 24px short of the left
        self.assertIn("margin: 0 -12px", declarations(".panel .table-wrap"))
        self.assertIn("max-width: none", declarations(".panel .table-wrap"))
        hovered_rows = [s.strip() for sel, _body in css_rules() for s in sel.split(",")
                        if re.search(r"(?<![\w-])tr(\[[^\]]*\])*:hover", s)]
        self.assertTrue(hovered_rows)
        for sel in hovered_rows:
            self.assertIn("tr[data-row]:hover", sel)  # a total row has no data-row: it never lights up
        self.assertIn('<tr class="total">', section(self.page("/money/year"), "year-report"))


# ---------------------------------------------------------------- STYLE-4 helpers

def media_rules(query):
    """``[(selector, declarations)]`` of the ``@media <query> {…}`` blocks of ``web/style.css`` only."""
    css, out = style_css(), []
    for m in re.finditer(r"@media ([^{]+)\{", css):
        if m.group(1).strip() != query:
            continue
        depth, end = 1, m.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(css[end], 0)
            end += 1
        out += [(sel.strip(), body) for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css[m.end():end - 1])]
    return out


DATE_RINGS = tuple(f'input[type="{kind}"].input:focus-within' for kind in ("date", "datetime-local", "month"))


class FormsAndButtonsTest(unittest.TestCase):
    """STYLE-4 (spec 4.6, 4.7): a field and a button are one height (``--control-height``, 44px under
    861px); buttons, chips, the change summaries, the search fields and the file button are pills; a
    field has 12px corners. The states: hover, an error in red (a state, D4), disabled still readable,
    the current chip bold. One focus ring (2px ``--accent-text``, 2px away; ``--on-accent`` on the wash)
    that no rule takes away. Nothing moves on hover."""

    def test_fields_and_buttons_are_one_height_and_buttons_are_pills(self):
        self.assertEqual(root_tokens()["--control-height"], "40px")
        for selector in (".btn", ".input"):
            self.assertIn("height: var(--control-height)", declarations(selector), selector)
        self.assertIn("min-height: var(--control-height)", declarations("details.change > summary"))
        phone = media_rules("(max-width: 860px)")
        for selector, height in ((".btn", "height: 44px"), (".input", "height: 44px"),
                                 ("details.change > summary", "min-height: 44px")):
            self.assertIn(height, " ".join(body for sel, body in phone if sel == selector), selector)
        for selector in (".btn", ".chip", "details.change > summary", ".toolbar .input", ".search-line .input",
                         'input[type="file"].input::file-selector-button', ".title-row .input"):
            self.assertIn("border-radius: var(--radius-pill)", declarations(selector), selector)
        self.assertIn("border-radius: var(--radius-control)", declarations(".input"))
        self.assertEqual(root_tokens()["--radius-control"], "10px")  # round 4 (Pearl, 24/11/2026)

    def test_secondary_danger_hover_error_and_disabled(self):
        button = declarations(".btn")
        for part in ("background: var(--surface)", "border: 1px solid var(--control)", "color: var(--text)"):
            self.assertIn(part, button)
        self.assertIn("background: var(--raised)", declarations(".btn:hover"))
        danger = declarations(".btn.danger")
        for part in ("color: var(--negative)", "border-color: currentColor", "background: var(--surface)"):
            self.assertIn(part, danger)
        self.assertIn("border-color: var(--muted)", declarations(":where(.input):hover"))
        self.assertIn("border-color: var(--negative)", declarations('.input[aria-invalid="true"]'))
        self.assertIn("color: var(--negative)", declarations(".error"))
        for selector in (".btn:disabled", ".btn:disabled:hover", '.btn[aria-disabled="true"]', ".input:disabled"):
            rule = declarations(selector)
            for part in ("background: var(--raised)", "border-color: var(--border)", "color: var(--faint)",
                         "cursor: not-allowed"):
                self.assertIn(part, rule, selector)
        # Round 4 (24/11/2026) ends "hover never moves" (round 2). The pastor: "Try to match the tweak I did",
        # with the tweak values fade 1400ms ease-out, the Services line draws itself, a card grows x1.005.
        # These moves and no other, each only when Windows does not ask for less motion; then all stop.
        moves = re.findall(r"\b(?:transition|animation)\s*:\s*([^;]+)", style_css())
        self.assertEqual(set(moves), {"none !important", "enter 1400ms ease-out both", "draw 3500ms ease-out both",
                                      "transform 200ms ease-out"})
        calm = " ".join(body for _sel, body in media_rules("(prefers-reduced-motion: no-preference)"))
        for move in ("enter 1400ms", "draw 3500ms", "transform 200ms", "scale(1.005)"):
            self.assertIn(move, calm)
        self.assertIn("animation: none !important", " ".join(b for _s, b in media_rules("(prefers-reduced-motion: reduce)")))

    def test_the_current_chip_is_marked_by_more_than_its_color(self):
        chip, current = declarations(".chip"), declarations('.chip[aria-current="true"]')
        self.assertIn("border: 1px solid var(--border)", chip)
        self.assertNotIn("font-weight", chip)
        for part in ("background: var(--active)", "border-color: var(--accent-text)", "font-weight: 600"):
            self.assertIn(part, current)

    def test_one_focus_ring_that_no_rule_takes_away(self):
        ring = declarations(":focus-visible")
        self.assertIn("outline: 2px solid var(--accent-text)", ring)
        self.assertIn("outline-offset: 2px", ring)
        colors = set()
        for selector, body in css_rules():
            self.assertNotRegex(body, r"outline(?:-style|-width)?\s*:\s*(?:none|0)\b", selector)
            colors |= set(re.findall(r"outline(?:-color)?\s*:[^;]*?(var\(--[\w-]+\))", body))
        # the ring is one of the 2 tokens StyleTokensTest and test_app_color check for 3:1 on what is under it
        self.assertEqual(colors, {"var(--accent-text)"})  # round 4: the title card is white, no ring in --on-accent
        # Tab also stops on the calendar button inside a date field: the field keeps the ring then
        for selector in DATE_RINGS:
            self.assertIn("outline: 2px solid var(--accent-text)", declarations(selector), selector)
            self.assertIn("outline-offset: 2px", declarations(selector), selector)


class FormControlsTest(PagesTestBase):
    """STYLE-4: every form control of the pages with a form carries a class that style.css styles, so the
    one CSS pass reaches all of them; a refused form marks its field and its sentence with the classes
    style.css paints red."""

    STYLED = {".input", ".btn", ".link-btn", ".lang-switch button", 'input[type="checkbox"]',
              "details.change > summary", "details.rename > summary", ".nav-more > summary", "details.tech > summary"}

    def test_every_form_control_carries_a_class_style_css_styles(self):
        conn = self.db()
        pid = people.list_persons(conn)[0]["id"]
        fid = people.list_families(conn)[0]["id"]
        iid = cal.add_calendar_item(conn, "Service", "STYLE-4 Thờ phượng", f"{YESTERDAY} 08:00")[0]
        paths = ("/people/new", f"/people/{pid}", f"/people/{pid}/edit", f"/families/{fid}", "/money",
                 "/money/offerings/new", "/money/expenses/new", "/money/statement", "/money/year",
                 "/calendar", "/calendar/new", f"/calendar/{iid}", "/care", "/lists", "/copies", "/sent/new",
                 "/people/file", "/search", "/settings", "/")
        for path in paths:
            page = self.page(path)
            controls = re.findall(r"<(input|select|textarea|button)\b([^>]*)>", page)
            self.assertTrue(controls, path)
            for tag, attrs in controls:
                if 'type="hidden"' in attrs or 'type="checkbox"' in attrs:
                    continue
                if tag == "button" and 'name="lang"' in attrs:  # the language switch (.lang-switch button)
                    self.assertIn("lang-switch", page)
                    continue
                cls = re.search(r'class="([^"]*)"', attrs)
                self.assertTrue(cls and {"input", "btn", "link-btn"} & set(cls.group(1).split()),
                                (path, tag, attrs))
            for attrs in re.findall(r"<details\b([^>]*)>", page):  # its summary is a pill or a text action
                # nav-more: the menu (CRIT-2); tech: a Technical details fold of the Copies page (CRIT-5)
                self.assertRegex(attrs, r'class="(change|rename|nav-more|tech)"', path)
        for selector in self.STYLED:
            self.assertTrue(declarations(selector), selector)

    def test_an_empty_required_field_shows_its_error_in_red(self):
        form = {"full_name": "", "gender": "", "birth_date": "", "phone": "", "address": "", "note": "",
                "status_id": self.item("status", code="visitor"), "start_date": TODAY.isoformat()}
        _h, page = self.post("/people/new", form, expect=400)
        self.assertRegex(page, r'<input class="input" id="f-full_name"[^>]* aria-invalid="true"')
        self.assertIn('<p class="error" id="f-full_name-error">', page)
        self.assertIn("border-color: var(--negative)", declarations('.input[aria-invalid="true"]'))
        self.assertIn("color: var(--negative)", declarations(".error"))


# ---------------------------------------------------------------- STYLE-5 helpers

def rule_props(selector, name="style.css"):
    """``{property: value}`` of every rule of ``web/<name>`` whose selector list holds exactly ``selector``
    (a later rule wins), comments removed."""
    css = re.sub(r"/\*.*?\*/", "", (ROOT / "web" / name).read_text(encoding="utf-8"), flags=re.S)
    found = {}
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if selector in (s.strip() for s in sel.split(",")):
            found.update((p.strip(), v.strip()) for p, v in (d.split(":", 1) for d in body.split(";") if d.strip()))
    assert found, f"no CSS rule for {selector!r} in {name}"
    return found


CARD = '.dashboard > [data-panel="money-month"]'  # Money this month: its row 2 sizes (B11, STYLE-FIX-1, CRIT-4)
DARK_CARD = '.dashboard > [data-panel="needs-visit"]'  # the one dark card (CRIT-7: the pastor chose Needs a visit)


class CardsAndChartsTest(PagesTestBase):
    """STYLE-5 (spec 4.3, 4.4, 4.8-4.12, D2, D5, D6): white cards with round corners and a soft shadow;
    ONE dark card (Dashboard, Needs a visit since CRIT-7) made from the app color, whose every text reads on it
    (its own tokens; StyleTokensTest checks them for 220 app colors); green and red on money amounts only
    (the Services trend word is not money); the Private note panel unlike the other cards; on paper the
    dark card is ink on white and nothing is green or red."""

    def test_cards_are_white_with_round_corners_and_a_soft_shadow(self):
        tokens = root_tokens()
        self.assertEqual((tokens["--radius-card"], tokens["--radius"]), ("10px", "10px"))  # round 4 (Pearl, 24/11/2026)
        for selector in (".panel", ".kpi-strip"):  # the Money totals strip is a light card too
            rule = rule_props(selector)
            self.assertEqual((rule["background"], rule["border"], rule["border-radius"], rule["box-shadow"]),
                             ("var(--surface)", "1px solid var(--border)", "var(--radius-card)", "var(--shadow)"),
                             selector)
        self.assertEqual(rule_props(".panel h2")["font-weight"], "800")  # round 4 (Pearl, 24/11/2026)
        self.assertEqual(rule_props(".card-link")["color"], "var(--accent-text)")   # CRIT-1: a link shows it is one
        self.assertEqual(rule_props(".panel .meta")["color"], "var(--muted)")
        # the Private note panel: a tint, a dashed edge, no shadow (it stays .no-print)
        private = rule_props(".panel.private")
        self.assertEqual((private["background"], private["border"], private["box-shadow"]),
                         ("var(--raised)", "1px dashed var(--control)", "none"))
        # a small box (Handover result and refusal, the empty box, search results) has the 12px corners
        for selector in (".result", ".refusal", ".empty", ".results"):
            self.assertEqual(rule_props(selector)["border-radius"], "var(--radius)", selector)

    def test_one_dark_card_made_from_the_app_color(self):
        card = rule_props(DARK_CARD)
        self.assertEqual((card["background"], card["box-shadow"], card["color"], card["border-color"]),
                         ("var(--highlight-fill)", "var(--shadow-raised)", "var(--text)", "transparent"))
        # every color token a rule inside the card uses points to a token checked on the 3 stops
        self.assertEqual({p: v for p, v in card.items() if p.startswith("--")}, {
            "--text": "var(--highlight-ink)", "--muted": "var(--highlight-muted)", "--faint": "var(--highlight-muted)",
            "--rule": "var(--highlight-rule)", "--border": "var(--highlight-rule)", "--control": "var(--highlight-rule)",
            "--accent-text": "var(--highlight-focus)",  # the focus ring is --accent-text: white on the card
            "--raised": "var(--highlight-rule)"})  # round 4: a row lights up under the pointer, here too
        # it stretches to the height of Next 7 days (row 1): no align-self of its own
        self.assertNotIn("align-self", declarations(DARK_CARD))
        # no other dark card: the fill is used by this one rule only
        fill_rules = [sel for sel, body in css_rules() if "var(--highlight-fill)" in body]
        self.assertEqual(fill_rules, [DARK_CARD])
        # the fill: 3 stops, each the app color as text (--accent-text) taken darker
        tokens = root_tokens()
        self.assertEqual(re.findall(r"var\((--[\w-]+)\)", tokens["--highlight-fill"]), list(HIGHLIGHT_STOPS))
        for stop in HIGHLIGHT_STOPS:
            self.assertRegex(tokens[stop], r"^color-mix\(in srgb, var\(--accent-text\), #000000 \d+%\)$", stop)
        page = self.page("/")
        self.assertEqual(page.count('data-panel="needs-visit"'), 1)
        # every class inside it is one these rules reach (a new class with its own color would show here)
        classes = set(" ".join(re.findall(r'class="([^"]*)"', section(page, "needs-visit"))).split())
        self.assertLessEqual(classes, {"count", "num", "meta", "list-head", "rows", "row", "what", "wrap", "clamp-2",
                                       "side", "figure", "faint", "dash", "card-link", "empty", "no-print"})

    def test_green_and_red_only_on_money_amounts(self):
        # Balance: green when 0 or more, red below 0; a Services trend word is never green or red (D5)
        self.assertEqual(rule_props(".kpi-value.strong:not(.neg)")["color"], "var(--positive)")
        self.assertEqual(rule_props(".neg")["color"], "var(--negative)")
        self.assertEqual(rule_props(".trend .trend-up")["color"], "var(--accent-text)")
        self.assertEqual(rule_props(".trend .trend-down")["color"], "var(--muted)")
        green = {sel for sel, body in css_rules() if "var(--positive)" in body}
        red = {sel for sel, body in css_rules() if "var(--negative)" in body}
        self.assertEqual(green, {".kpi-value.strong:not(.neg)"})
        # red is also a state (D4): an error, a field with an error, the Delete button
        self.assertEqual(red, {".neg", ".error", '.input[aria-invalid="true"]', ".btn.danger"})

    def test_services_chart_today_and_service(self):
        line = rule_props(".chart .line")
        self.assertEqual((line["stroke"], line["stroke-width"], line["stroke-linejoin"]),
                         ("var(--accent)", "2", "round"))  # round 4 (Pearl, 24/11/2026)
        self.assertEqual((rule_props(".chart .end")["fill"], rule_props(".chart .end")["font-weight"]),
                         ("var(--accent-text)", "700"))
        self.assertEqual(rule_props(".chart .gridline")["stroke"], "var(--grid)")
        self.assertEqual(rule_props(".chart .gridline.base")["stroke"], "var(--grid-base)")
        self.assertEqual(rule_props(".chart .tick")["fill"], "var(--muted)")
        self.assertIn("padding: 0 32px 0 40px", declarations(".chart"))  # the ticks sit in this padding
        today = rule_props(".today-tag")  # a small outlined pill: --accent-text on white reads for any color
        self.assertEqual((today["color"], today["border"], today["border-radius"]),
                         ("var(--accent-text)", "1px solid currentColor", "var(--radius-pill)"))
        self.assertEqual(rule_props(".kind.k-service")["color"], "var(--accent-text)")

    def test_on_paper_the_dark_card_is_ink_on_white(self):
        card = rule_props(DARK_CARD, "print.css")
        self.assertEqual((card["background"], card["box-shadow"], card["--highlight-ink"], card["--highlight-muted"],
                          card["--highlight-rule"], card["--highlight-line"]),
                         ("none", "none", "#000", "#333", "#888", "#888"))
        self.assertEqual(rule_props(".panel", "print.css")["box-shadow"], "none")
        self.assertEqual(rule_props(".kpi-strip", "print.css")["box-shadow"], "none")
        for selector in (".kpi-value.strong", ".kpi-value.strong:not(.neg)"):  # no green or red Balance
            self.assertEqual(rule_props(selector, "print.css")["color"], "#000", selector)


# ---------------------------------------------------------------- STYLE-6 helpers

def print_media_props(selector):
    """``{property: value}`` of the rules inside ``@media print {…}`` of ``web/print.css`` whose selector
    list holds exactly ``selector`` (a later rule wins), comments removed."""
    css = re.sub(r"/\*.*?\*/", "", (ROOT / "web" / "print.css").read_text(encoding="utf-8"), flags=re.S)
    start = css.index("@media print {") + len("@media print {")
    depth, end = 1, start
    while depth:
        depth += {"{": 1, "}": -1}.get(css[end], 0)
        end += 1
    found = {}
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css[start:end - 1]):
        if selector in (s.strip() for s in sel.split(",")):
            found.update((p.strip(), v.strip()) for p, v in (d.split(":", 1) for d in body.split(";") if d.strip()))
    assert found, f"no @media print rule for {selector!r}"
    return found


def media_props(query, selector):
    """The declarations of ``selector`` in the ``@media <query>`` blocks of ``web/style.css``, joined."""
    found = [body for sel, body in media_rules(query) if selector in (s.strip() for s in sel.split(","))]
    assert found, f"no rule for {selector!r} in @media {query}"
    return " ".join(found)


# the properties that paint: a token used in one of them shows on paper unless print.css re-sets it
PAINT = re.compile(r"(?:color|background(?:-color)?|border(?:-(?:top|right|bottom|left))?(?:-color)?|outline(?:-color)?"
                   r"|fill|stroke|accent-color|scrollbar-color|box-shadow)")
PAPER_KEEPS = {"--bar-offerings", "--bar-expenses"}  # spec 3.3: the Year report bars print in their two colors
# backgrounds whose rules print.css clears or hides itself: the wash (.canvas::before), the fill of the dark
# card, the gradient of the current menu item and of the primary button (the menu and the buttons)
PAPER_CLEARS = {"--wash", "--highlight-fill", "--gradient"}
GREY = re.compile(r"#(?:([0-9a-f])\1\1|([0-9a-f]{2})\2\2)")  # red = green = blue: ink, a grey or white


class PrintAndFinalWalkTest(PagesTestBase):
    """STYLE-6 (spec D6, 4.13, and the final walk over every page at 1440, 800 and 390px). On paper no card,
    title row or dark card keeps a shadow or a fill, and every color token that style.css paints with turns
    ink, grey or white (whatever the app color): print.css comes after the app color of the page head, so
    its ``:root`` wins. The layout faults the walk found (also at 900, 1000 and 1180px) stay fixed."""

    def test_on_paper_no_shadow_and_no_fill_on_cards_the_title_row_and_the_dark_card(self):
        for selector in (".panel", ".title-row", DARK_CARD):
            rule = print_media_props(selector)
            self.assertEqual((rule.get("box-shadow"), rule.get("background")), ("none", "none"), selector)
        self.assertEqual(print_media_props(".canvas::before")["display"], "none !important")  # no wash
        # print.css is last: after style.css and after the <style> that sets the app color
        page = self.page("/people")
        self.assertLess(page.index('href="/static/style.css"'), page.index("<style>:root{"))
        self.assertLess(page.index("<style>:root{"), page.index('href="/static/print.css"'))

    def test_on_paper_every_paint_token_is_ink_grey_or_white(self):
        used = set()
        for sel, body in css_rules():
            if sel == ":root":
                continue
            for decl in body.split(";"):
                prop, _colon, value = decl.partition(":")
                if PAINT.fullmatch(prop.strip()):
                    used |= set(re.findall(r"var\((--[\w-]+)\)", value))
        paper = print_media_props(":root")
        need = used - PAPER_KEEPS - PAPER_CLEARS
        self.assertGreaterEqual(len(need), 20)  # the text, line, tint, chart and shadow tokens
        for token in sorted(need):
            value = paper.get(token, "")  # "": print.css does not re-set it, so it keeps its screen color
            self.assertTrue(value == "none" or GREY.fullmatch(value), (token, value))
        # the gradient sits only on the current menu item and on the primary button: print.css hides both
        hidden = {selector for selector, _parts in print_hide_selectors()}
        self.assertLessEqual({".sidebar", ".btn"}, hidden)
        for sel, body in css_rules():
            if "var(--gradient)" in body:
                self.assertTrue(sel.startswith(".nav-item") or ".btn" in sel, sel)

    def test_the_layout_faults_of_the_final_walk_stay_fixed(self):
        # under 861px a short page (Chi phái, Documents): the top bar kept growing an empty band of up to
        # 200px under the menu; it keeps its own height now and the canvas takes the rest
        self.assertIn("grid-template-rows: auto 1fr", media_props("(max-width: 860px)", ".app"))
        # the menu: it was one row that scrolled sideways (a thin bar, the current pill scrolled into view);
        # now it is a grid of 5 items and the More fold, with no sideways scroll and no bar (CRIT-2)
        menu = media_props("(max-width: 860px)", ".nav")
        self.assertIn("display: grid", menu)
        self.assertNotRegex(menu, r"overflow|scrollbar")
        self.assertFalse([sel for sel, body in css_rules() if "scroll-initial-target" in body], "no strip to scroll")
        # the Dashboard day column: "Chúa Nhật 15/11" ran into the time at 92px under 1181px
        self.assertIn("width: 112px", declarations(".row .day"))
        # the Search page with no result: its dashed box sat on the wash (1.05:1); it is white now
        self.assertIn("background: var(--surface)", declarations(".canvas > .empty"))
        # the People search with a query (a field and 2 buttons) pushed the page 72px sideways at 390px
        self.assertIn("min-width: 0", declarations(".toolbar"))
        self.assertIn("flex-basis: 80px", media_props("(max-width: 640px)", ".toolbar .input"))  # CRIT-FIX-1: one line
        # a phone: "Chỉnh sửa" was wider than the 36px kept for Edit, so each Money list scrolled 20px
        self.assertIn("width: auto", media_props("(max-width: 640px)", "table.money td.edit"))
        self.assertIn("flex-basis: 100%", media_props("(max-width: 640px)", "table.money tr[data-row]::after"))
        # the sign of a card link never sits alone on the next line
        self.assertIn('content: "\\00a0›"', declarations(".card-link::after"))
        # 861px to 1180px: the actions squeezed a Person's name to 108px (3 lines); the title keeps 240px
        # now and the actions wrap under it (from 1181px the Dashboard title row still fits one line)
        self.assertIn("flex-wrap: wrap", declarations(".title-row"))
        self.assertIn("flex: 1 1 240px", declarations(".title-row > :first-child"))
        self.assertIn("flex: none", media_props("(max-width: 860px)", ".title-row > :first-child"))
        # ... and on the Dashboard a name of Needs visit or a title of This week was squeezed to a few
        # characters a line at half the canvas: the two list cards take the full row there; a Chi phái
        # name in a narrow history table got 27px beside two 112px dates
        for panel in ("this-week", "needs-visit"):
            self.assertIn("grid-column: 1 / -1", media_props("(max-width: 1180px)", f'.dashboard > [data-panel="{panel}"]'))
        self.assertIn("width: 1%", declarations("table.history td.n"))
        self.assertIn("width: auto", media_props("(max-width: 640px)", "table.history td.n"))  # a phone row
        # Lists (1180px): "6 người đang phục vụ" was cut at 30% of a row with room; Money (390px): the
        # card head link broke over 2 lines
        self.assertIn("max-width: none", declarations(".list-item .side"))
        self.assertIn("white-space: nowrap", declarations("header .card-link"))


# ---------------------------------------------------------------- STYLE-FIX-1 helpers

def at_block(css, head):
    """The inside of the first ``<head> {…}`` block of ``css``, and ``css`` without that block."""
    start = css.index(head)
    inside = css.index("{", start) + 1
    depth, end = 1, inside
    while depth:
        depth += {"{": 1, "}": -1}.get(css[end], 0)
        end += 1
    return css[inside:end - 1], css[:start] + css[end:]


def block_props(css, selector):
    """``{property: value}`` of the rules of ``css`` whose selector list holds exactly ``selector``."""
    found = {}
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if selector in (s.strip() for s in sel.split(",")):
            found.update((p.strip(), v.strip()) for p, v in (d.split(":", 1) for d in body.split(";") if d.strip()))
    return found


WIDE = "screen and (min-width: 1181px)"  # the Dashboard on one screen


class StyleFix1Test(PagesTestBase):
    """STYLE-FIX-1, the bugs of TEST-STYLE-1. BUG-2: the wash grows with the head (a CSS anchor on the title
    row), so its white text never sits on the fade, whatever the title, the width or a flash; a short head
    looks as before. BUG-1: on the Dashboard a flash puts the language switch back in the flow (it sat on
    the pale flash). BUG-3: the hidden Edit header of a table stays in the table's own scroll box (the Money
    page scrolled sideways). BUG-4: Money this month fits row 2 of the Dashboard, an empty month too."""

    def test_bug2_the_wash_grows_with_the_head(self):
        tokens = root_tokens()
        # the fade is a fixed length at the bottom of the wash: from 861px a short 48px (CRIT-9: a long fade was a
        # grey-blue band in the gutters); under 861px 40% of the old fixed height, so a wash of it looks the same
        self.assertEqual((tokens["--wash-h"], tokens["--wash-fade"]), ("360px", "48px"))  # round 4 (Pearl, 24/11/2026)
        self.assertEqual((tokens["--wash-h-narrow"], tokens["--wash-fade-narrow"]), ("600px", "240px"))
        # round 4: the wash paints only a church picture (--hero-image, none in style.css: the page head may set it)
        self.assertEqual((tokens["--wash"], tokens["--hero-image"]), ("var(--hero-image)", "none"))
        self.assertEqual(rule_props(".title-row")["anchor-name"], "--title-row")
        inside, outside = at_block(style_css(), "@supports (anchor-name: --a)")
        narrow, wide = at_block(inside, "@media (max-width: 860px)")
        # with no anchors (outside @supports): the fixed height as before, the fade drawn at its bottom
        self.assertNotIn("anchor(", outside)
        top_level = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", outside)
        base = block_props(top_level, ".canvas::before")
        self.assertEqual((base["height"], base["background"], base["mask-image"]),  # round 4: the fade is a mask
                         ("var(--wash-h)", "var(--wash) 50% 52% / cover no-repeat",
                          "linear-gradient(to bottom, black calc(100% - var(--wash-fade)), transparent)"))
        stacked = media_props("(max-width: 860px)", ".canvas::before")
        self.assertIn("height: var(--wash-h-narrow)", stacked)
        self.assertIn("black calc(100% - var(--wash-fade-narrow))", stacked)
        # with anchors: the wash ends its fade + 8px under the title row, never shorter than before
        for css, low, fade in ((wide, "var(--wash-h)", "var(--wash-fade)"),
                               (narrow, "var(--wash-h-narrow)", "var(--wash-fade-narrow)")):
            rule = block_props(css, ".canvas::before")
            self.assertEqual(rule.get("min-height"), low)
            self.assertEqual(rule.get("bottom"), f"calc(anchor(--title-row bottom) - {fade} - 8px)")
        self.assertEqual(block_props(wide, ".canvas::before")["height"], "auto")
        # one title row a page, in the canvas next to the wash: the anchor is that page's own
        page = self.page("/people")
        self.assertEqual(page.count('class="title-row"'), 1)
        self.assertRegex(page, r'<main class="canvas" id="main" tabindex="-1">.*<header class="title-row">')

    def test_bug1_with_a_flash_the_dashboard_language_switch_is_in_the_flow(self):
        # no flash: as before, the switch sits at the top right of the canvas
        self.assertIn("position: absolute", media_props(WIDE, ".canvas:has(> .dashboard) > .lang-switch"))
        flow = media_props(WIDE, ".canvas:has(> .dashboard):has(> .flash) > .lang-switch")
        self.assertIn("position: static", flow)
        self.assertIn("margin: 0 12px 4px", flow)  # as on every other page (.lang-switch)
        self.assertIn("margin: 0 12px 4px", declarations(".lang-switch"))
        # the real page: the switch, then the flash, both children of the canvas; the grid too
        page = self.page("/?msg=" + urllib.parse.quote("Đã lưu."))
        self.assertRegex(page, r'<main class="canvas" id="main" tabindex="-1"><form class="lang-switch"[^>]*>.*?</form><p class="flash" role="status">')
        self.assertIn('</header><div class="grid dashboard">', page)

    def test_bug3_a_table_scrolls_inside_its_own_box(self):
        # the hidden Edit header word is absolute: the positioned wrap holds it (it pushed the Money page
        # sideways from 1250px to 1340px)
        self.assertIn("position: absolute", declarations(".sr-only"))
        wrap = rule_props(".table-wrap")
        self.assertEqual((wrap["position"], wrap["overflow-x"]), ("relative", "auto"))
        page = self.page("/money")
        self.assertIn('<th scope="col" class="edit no-print"><span class="sr-only">', page)
        self.assertIn('<div class="table-wrap">', page)

    def test_bug4_money_this_month_fits_row_2_in_an_empty_month(self):
        card = media_props(WIDE, CARD)
        self.assertIn("min-height: var(--dash-row2)", card)
        self.assertIn("max-height: var(--dash-row2)", card)
        # capped, never cut: no rule of the card hides what does not fit; the content is made to fit
        self.assertNotIn("overflow", " ".join(body for sel, body in css_rules() if "money-month" in sel))
        self.assertIn("padding: 4px 0", media_props(WIDE, CARD + " .kpi"))
        empty = CARD + ":has(> .empty)"  # an empty month: the 3 zero amounts side by side
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", media_props(WIDE, empty + " .kpis"))
        side = media_props(WIDE, empty + " .kpi + .kpi")
        self.assertIn("border-top: 0", side)
        self.assertIn("border-left: 1px dotted var(--rule)", side)  # round 4 (Pearl, 24/11/2026)
        # the real markup: in an empty month the dashed box is a child of the card, right after the amounts
        html = dashboard._money_month({"offerings": 0, "expenses": 0, "balance": 0}, TODAY, "span-4")
        self.assertIn('</div></div><p class="empty">', html)
        self.assertNotIn('class="empty"', dashboard._money_month({"offerings": 5, "expenses": 2, "balance": 3},
                                                                 TODAY, "span-4"))


DASH_LISTS = ("this-week", "needs-visit", "sent-documents")  # the Dashboard lists (CRIT-4: none scrolls in its card)


class StyleFix2Test(PagesTestBase):
    """STYLE-FIX-2, BUG-5 of TEST-STYLE-FIX-1. From 1181px a Dashboard list has a short fixed height (it scrolls
    inside its card), so its grid rows shrank to the row min-height (40px, 34px up to 720px high) and a title on
    2 lines (48px) was drawn over the next row. Each row now takes its content height (grid-auto-rows:
    max-content); the row min-heights and the 2-line clamp stay as they were. CRIT-4: a list has no height of
    its own any more (no scroll in the card), so each row takes its content height without that rule."""

    def test_bug5_a_dashboard_list_row_is_as_tall_as_its_2_line_title(self):
        for panel in DASH_LISTS:  # CRIT-4: no rule gives a Dashboard list a height or a scroll
            self.assertFalse([sel for sel, _body in css_rules() if f'[data-panel="{panel}"] .rows' in sel], panel)
        # unchanged: the row min-heights and the clamp of a title to 2 lines
        self.assertFalse([sel for sel, _b in css_rules() if sel == ".dashboard .row"])  # round 4: a row as everywhere
        self.assertIn("-webkit-line-clamp: 2", declarations(".clamp-2"))
        # the real page: a long title of This week (about 110 characters, 2 lines) is a row of its <ul class="rows">
        title = "Buổi nhóm cầu nguyện đặc biệt của Ban Thanh Niên và Ban Phụ Nữ tại Nhà thờ chính"
        cal.add_calendar_item(self.db(), "Meeting", title, f"{TODAY.isoformat()} 19:00")
        week = section(self.page("/"), "this-week")
        self.assertRegex(week, r'<ul class="rows"><li class="row" data-row>.*<span class="what wrap">'
                               rf'<span class="clamp-2" lang="vi" title="{title}">')


def media_wins(query, selector):
    """``{property: value}`` of ``selector`` in the ``@media <query>`` blocks of ``web/style.css`` (a later rule
    wins, as in the browser for rules of one weight)."""
    found = {}
    for sel, body in media_rules(query):
        if selector in (s.strip() for s in sel.split(",")):
            found.update((p.strip(), v.strip()) for p, v in (d.split(":", 1) for d in body.split(";") if d.strip()))
    assert found, f"no rule for {selector!r} in @media {query}"
    return found


SHORT = WIDE + " and (max-height: 720px)"  # the Dashboard on one screen, up to 720px high
ROW1 = ("this-week", "needs-visit")  # the 2 cards of Dashboard row 1


class StyleFix3Test(PagesTestBase):
    """STYLE-FIX-3, BUG-6 of TEST-STYLE-FIX-2. From 1181px row 1 of the Dashboard had a fixed 150px floor: on a
    short window (1181x640 in vi) the Needs a visit list kept 1px and showed no row. Row 1 is now never shorter
    than its 2 cards with one whole row in each list: the list is at least as high as one row at its tallest (a
    title clamped to 2 lines) and row 1 is min-content. Up to 720px high that height comes from the space around
    the row 1 cards and the title row, and the Needs a visit hint takes the whole header width (one line); it
    never comes from the text. Row 2 stays as it was. CRIT-4: the lists no longer scroll; each shows a fixed
    number of whole rows, so the floor and the min-content row are gone; the tight title row is now from 1181px
    at every height."""

    def test_bug6_row_1_always_shows_one_whole_row_in_each_list(self):
        self.assertFalse([sel for sel, body in css_rules() if ".dashboard" in sel and "grid-template-rows" in body])
        self.assertNotIn("minmax(150px", style_css())  # no fixed floor is left
        for panel in ROW1:  # CRIT-4: no floor and no scroll: the list shows its rows whole (at most a fixed number)
            self.assertFalse([sel for sel, _body in css_rules() if f'[data-panel="{panel}"] .rows' in sel], panel)
        self.assertIn("font: var(--fs-body)/24px", declarations("body"))  # a title line is 24px high
        # the real page: the Needs a visit rows are a <ul class="rows"> inside its card, under the list head
        visit = section(self.page("/"), "needs-visit")
        self.assertRegex(visit, r'<div class="list-head" aria-hidden="true">.*</div><ul class="rows">'
                                r'<li class="row" data-row>')

    def test_round_4_the_look_ready_for_later_pages_stays_in_style_css(self):
        """Round 4: docs/redesign-pearl-for-hermes.md tells the page code which classes to write for the parts
        of the pastor's mockup that need new HTML. Their rules are in style.css already: no page uses them
        yet, so this keeps them from being cleaned away as unused."""
        selectors = {sel for rule, _body in css_rules() for sel in (s.strip() for s in rule.split(","))}
        for ready in (".has-hero .canvas::before", ".has-hero .sidebar", ".figures", ".figure + .figure",
                      ".figure-label", ".figure-value", ".next-item", ".next-item .what", ".chart .dot",
                      ".chart .dot.last"):
            self.assertIn(ready, selectors)
        self.assertEqual(root_tokens()["--hero-image"], "none")  # the page head sets it for a church picture
        # the amounts count up in app.js: whole dong only, never when Windows asks for less motion
        js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn('querySelectorAll(".kpi-value")', js)
        self.assertIn('matchMedia("(prefers-reduced-motion:reduce)").matches', js)
        self.assertIn("el.textContent = whole", js)  # it ends as the server wrote it

    def test_round_4_the_dashboard_may_scroll_and_row_2_ends_level(self):
        """Round 4 (24/11/2026) ends DASH RULE 4 (the Dashboard on one screen from 1181px). The pastor was asked
        which wins, the rule or the roomy mockup, and chose: "My design; it may scroll". So no block makes the
        Dashboard tighter in a short window any more, and its cards have the padding of every card."""
        self.assertFalse(media_rules(SHORT))  # no short-window block is left
        self.assertFalse([sel for sel, body in css_rules() if sel == ".dashboard > .panel" and "padding" in body])
        self.assertEqual(root_tokens()["--card-pad"], "37px")
        # the pastor's page: the title card 476px wide, and row 1 is 6 + 6
        self.assertEqual(media_wins(WIDE, ".canvas:has(> .dashboard) > .title-row")["max-width"], "476px")
        for panel in ROW1:
            self.assertEqual(media_wins(WIDE, f'.dashboard > [data-panel="{panel}"]')["grid-column"], "span 6", panel)
        # row 2: each card at least --dash-row2 high, so the 3 end level; Money this month never taller
        self.assertEqual(root_tokens()["--dash-row2"], "430px")
        for panel in ("services", "money-month", "sent-documents"):
            card = f'.dashboard > [data-panel="{panel}"]'
            self.assertEqual(media_wins(WIDE, card)["min-height"], "var(--dash-row2)", panel)
        self.assertEqual(media_wins(WIDE, CARD)["max-height"], "var(--dash-row2)")
        self.assertTrue(WIDE.startswith("screen and "))  # screen only: on paper every list prints whole


PHONE = "(max-width: 860px)"  # a phone or a tablet: the top bar


def whole_rule(rules, selector_list):
    """``{property: value}`` of the rules whose whole selector list (spaces squeezed) is ``selector_list``."""
    found = {}
    for sel, body in rules:
        if " ".join(sel.split()) == selector_list:
            found.update((p.strip(), v.strip()) for p, v in (d.split(":", 1) for d in body.split(";") if d.strip()))
    assert found, f"no rule {selector_list!r}"
    return found


def top_level_rules():
    """``[(selector, declarations)]`` of ``web/style.css`` outside every ``@media`` block (the sizes from 861px)."""
    top = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", style_css())
    return [(sel.strip(), body) for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", top)]


class CritOneTest(PagesTestBase):
    """CRIT-1, the design critique of 2026-11-14 (rows 1, 3, 7). Row 3: a link in a table cell, in a row title
    and a card foot link is in the app color (--accent-text), underlined under the pointer and on keyboard
    focus, one tag weight so paper keeps it ink; the dark card keeps its own light color. Row 7: a row action
    (Money Edit, Documents Delete, Plan, Rename, Hide/Show) is a plain word in the app color at weight 400;
    the pills keep their weight. Row 1: in a table.list row whose first cell holds a link, that link covers the
    whole row (screen only) and every other link, button or form of the row stays on top; under 861px every
    small action is at least 44px high, all of it a tap; from 861px each keeps its own size."""

    TAPS = (".lang-switch button", ".card-link", ".row .row-action", "details.rename > summary", ".link-btn",
            "table.list td a")
    ROW_ACTIONS = ("table.money td.edit a", ".row .row-action", "details.rename > summary", ".link-btn",
                   "table.documents td:last-child a")

    def add_offering(self):
        conn = self.db()
        money.add_offering(conn, TODAY.isoformat(), 100_000, lists.find_item(conn, "fund", name="General")["id"])

    def test_links_in_cells_rows_and_card_feet_are_in_the_app_color(self):
        for selector in (":where(td) a", ":where(.row .what) a", ".card-link"):
            self.assertEqual(rule_props(selector)["color"], "var(--accent-text)", selector)
        self.assertEqual(rule_props("a")["text-decoration"], "none")  # no underline at rest
        for selector in ("a:hover", ":where(td) a:focus-visible", ":where(.row .what) a:focus-visible",
                         ".card-link:focus-visible"):
            self.assertEqual(rule_props(selector)["text-decoration"], "underline", selector)
        self.assertIn("outline: 2px solid var(--accent-text)", declarations(":focus-visible"))  # the one ring
        # no rule paints a link of a cell back to ink (the Sent document file link was .cell-sub a)
        self.assertFalse([sel for sel, _b in css_rules() if sel == ".cell-sub a"])
        # one tag weight: the later "a" rule of print.css keeps a data link ink on paper
        self.assertEqual(rule_props("a", "print.css")["color"], "inherit")
        # the dark card: its own --accent-text is --highlight-focus, white (StyleTokensTest: 4.5:1 on its stops)
        self.assertEqual(rule_props(DARK_CARD)["--accent-text"], "var(--highlight-focus)")
        self.assertEqual(root_tokens()["--highlight-focus"], "#ffffff")
        self.assertIn(("--accent-text", "--surface"), TEXT_PAIRS)  # a link on a card: 4.5:1 for any app color
        self.assertIn(("--highlight-focus", "--highlight"), TEXT_PAIRS)  # a foot link on the dark card
        # the real pages: names in a table cell and in a row title are links
        self.assertRegex(self.page("/people"), r'<tr data-row><td><a href="/people/\d+">')
        self.assertRegex(section(self.page("/care"), "needs-visit"), r'<span class="what[^"]*">.*?<a href="/people/\d+"')

    def test_row_actions_are_plain_words_in_the_app_color(self):
        for selector in self.ROW_ACTIONS:
            rule = rule_props(selector)
            self.assertEqual((rule["font-weight"], rule["color"]), ("400", "var(--accent-text)"), selector)
        # the pills keep their weight (header buttons, the "+" folding pills); bold stays for data and titles
        self.assertEqual(rule_props(".btn")["font-weight"], "600")
        self.assertEqual(rule_props("details.change > summary")["font-weight"], "600")
        self.assertEqual(rule_props("table.list td:first-child")["font-weight"], "500")  # the name of a row
        # each row action is on a real page
        self.add_offering()
        self.assertIn('<a class="row-action" href="', self.page("/care"))
        self.assertIn('<td class="edit no-print"><a href="/money/', self.page("/money"))
        lists_page = self.page("/lists")
        self.assertIn('<details class="rename">', lists_page)
        self.assertIn('<button class="link-btn" type="submit"', lists_page)

    def test_a_whole_table_row_opens_its_page(self):
        screen = media_rules("screen")
        self.assertEqual(whole_rule(screen, "table.list tbody tr")["position"], "relative")
        cover = whole_rule(screen, "table.list td:first-child > a::after")
        self.assertEqual((cover["content"], cover["position"], cover["inset"]), ('""', "absolute", "0"))
        on_top = whole_rule(screen, "table.list tr:has(> td:first-child > a) > td:not(:first-child) :is(a, button, form)")
        self.assertEqual((on_top["position"], on_top["z-index"]), ("relative", "1"))
        # screen only: no rule outside @media screen sets the cover, and print.css does not know it
        self.assertFalse([sel for sel, _b in top_level_rules() if "::after" in sel and "table.list" in sel])
        self.assertNotIn("table.list", (ROOT / "web" / "print.css").read_text(encoding="utf-8"))
        # the scroll box of a table (STYLE-FIX-1) stays positioned: the row is inside it
        self.assertEqual(rule_props(".table-wrap")["position"], "relative")
        # the real lists: the first cell of every row is the link; the other links sit in later cells
        for path, href in (("/people", "/people/"), ("/families", "/families/"), ("/chi-phai", "/chi-phai/")):
            body = re.search(r"<tbody>(.*?)</tbody>", self.page(path), re.S).group(1)
            rows = re.findall(r"<tr data-row>(.*?)</tr>", body, re.S)
            self.assertTrue(rows, path)
            for row in rows:
                self.assertTrue(row.startswith(f'<td><a href="{href}'), (path, row[:120]))

    def test_every_small_action_is_a_44px_tap_under_861px(self):
        for selector in self.TAPS:
            rule = media_wins(PHONE, selector)
            self.assertEqual((rule.get("display"), rule.get("align-items"), rule.get("min-height")),
                             ("inline-flex", "center", "44px"), selector)
        self.assertEqual(media_wins(PHONE, ".row .row-action")["justify-content"], "flex-end")
        # the name link keeps its line height: the whole row is its tap already
        self.assertEqual(media_wins(PHONE, "table.list td:first-child > a")["margin-block"], "-12px")
        # the rule comes after the base rule of each (one weight: the later rule wins)
        css = style_css()
        last = css.rindex("table.list td a { display: inline-flex")
        for base in (".lang-switch button {", ".card-link {", ".row .row-action {", "details.rename > summary {",
                     ".link-btn {"):
            self.assertLess(css.index(base), last, base)
        # a Money table is a table.list too, so its links (Edit, the Giver) get the 44px tap
        self.add_offering()
        self.assertIn('<table class="list money offerings">', self.page("/money"))
        # a phone row: a 44px link and a plain field sit on one baseline
        self.assertIn("align-items: baseline", media_props("(max-width: 640px)", "table.list tr"))
        # one place for these taps: the old phone-only rules are gone
        for selector in (".link-btn", "details.rename > summary"):
            self.assertFalse([s for s, _b in media_rules("(max-width: 640px)")
                              if selector in (x.strip() for x in s.split(","))], selector)
        # from 861px each keeps its own size (the Copies Technical details fold shares the Rename rule, CRIT-5)
        top = top_level_rules()
        for selector, height in ((".lang-switch button", "28px"), (".link-btn", "36px"),
                                 ("details.tech > summary, details.rename > summary", "36px")):
            self.assertEqual(whole_rule(top, selector)["min-height"], height, selector)
        for selector in (".card-link", ".row .row-action", "table.money td.edit a"):
            self.assertNotIn("min-height", whole_rule(top, selector), selector)


class CritTwoTest(PagesTestBase):
    """CRIT-2, the design critique of 2026-11-14 (rows 2, 11). Row 2: under 861px the menu shows 5 items
    (Dashboard, People, Calendar, Money, Care) and a "More" fold (``<details>``, it works with no JS) with
    the other 8 in NAV order: a grid, no row that scrolls sideways. The 8 menu items hide there and the fold
    hides from 861px (display: none), so a screen reader meets each item once; from 861px the sidebar is as
    before. The fold's summary takes the current-page look when the page is one of the 8, and its link there
    has aria-current. Each item and the summary is a 44px tap. Row 11: a skip link is the first thing in
    ``<body>`` of both page shells; it goes to ``main#main`` (tabindex -1) and shows only with the focus."""

    FIVE = ("/", "/people", "/calendar", "/money", "/care")
    EIGHT = ("/families", "/chi-phai", "/documents", "/sent", "/lists", "/copies", "/settings", "/search")
    SKIP = '<a class="skip-link no-print" href="#main">{}</a><div class="app">'

    @staticmethod
    def menu(page):
        """``(the 13 menu items, the More fold)`` of the page's one nav."""
        nav = re.findall(r'<nav class="nav" aria-label="[^"]*">(.*?)</nav>', page, re.S)
        assert len(nav) == 1, "one menu a page"
        items, _sep, fold = nav[0].partition('<details class="nav-more">')
        return items, fold

    @staticmethod
    def lang(page):
        return re.search(r'<html lang="(\w+)">', page).group(1)

    def test_the_menu_holds_the_13_items_then_the_more_fold_with_the_8(self):
        self.assertEqual(tuple(key for key, _label, _href in ui.NAV if key in ui.NAV_MORE), ui.NAV_MORE)  # NAV order
        page = self.page("/people")
        items, fold = self.menu(page)
        links = re.findall(r'<a class="([^"]+)" href="([^"]+)"', items)
        self.assertEqual([href for _c, href in links], [href for _k, _l, href in ui.NAV])  # the 13 as before
        self.assertEqual(tuple(href for cls, href in links if cls == "nav-item"), self.FIVE)
        self.assertEqual(tuple(href for cls, href in links if cls == "nav-item in-more"), self.EIGHT)
        more = ui.t("core.nav_more", self.lang(page))
        self.assertTrue(fold.startswith(f'<summary class="nav-item">{more}</summary><div class="nav-more-list">'), fold[:120])
        self.assertTrue(fold.endswith("</div></details>"))
        self.assertEqual(tuple(re.findall(r'<a class="nav-item" href="([^"]+)"', fold)), self.EIGHT)
        # a page of the 5: current in the menu only
        self.assertEqual(re.findall(r'href="([^"]+)" aria-current="page"', items), ["/people"])
        self.assertNotIn("aria-current", fold)
        # a page of the 8: current in the menu (from 861px) and in the fold (under 861px)
        for path in ("/families", "/settings"):
            items, fold = self.menu(self.page(path))
            self.assertEqual(re.findall(r'href="([^"]+)" aria-current="page"', items), [path])
            self.assertEqual(re.findall(r'href="([^"]+)" aria-current="page"', fold), [path])

    def test_the_words_more_and_skip_to_content(self):
        self.assertEqual((ui.t("core.nav_more", "vi"), ui.t("core.nav_more", "en")), ("Mục khác", "More"))
        self.assertEqual((ui.t("core.skip_to_content", "vi"), ui.t("core.skip_to_content", "en")),
                         ("Chuyển đến nội dung", "Skip to content"))

    def test_under_861px_5_items_and_the_fold_and_from_861px_the_sidebar_as_before(self):
        # Round 4 (24/11/2026): the pastor moved the menu to the top at every width ("Move it to the top").
        # From 861px it is a bar of pills in a row: the same 5 items and the fold as under 861px.
        top = top_level_rules()
        self.assertEqual(whole_rule(top, ".nav-more")["display"], "block")
        self.assertEqual(whole_rule(top, ".nav .in-more")["display"], "none")
        bar = whole_rule(top, ".nav")
        self.assertEqual((bar["display"], bar["position"]), ("flex", "relative"))
        self.assertNotIn("flex-direction", bar)  # a row
        self.assertEqual(whole_rule(top, ".nav-item")["min-height"], "44px")
        fold = whole_rule(top, ".nav-more-list")  # a white card under "More", over the page
        self.assertEqual((fold["position"], fold["top"], fold["right"], fold["background"]),
                         ("absolute", "calc(100% + 4px)", "0", "var(--surface)"))
        self.assertFalse([p for p in whole_rule(top, ".sidebar") if p.startswith(("overflow", "scrollbar"))])
        self.assertEqual(media_wins(PHONE, ".nav .in-more")["display"], "none")
        self.assertEqual(media_wins(PHONE, ".nav-more")["display"], "block")
        nav = media_wins(PHONE, ".nav")
        self.assertEqual((nav["position"], nav["display"], nav["grid-template-columns"]),
                         ("relative", "grid", "repeat(6, minmax(0, 1fr))"))  # a tablet: one row of 6
        self.assertFalse([prop for prop in nav if prop.startswith(("overflow", "scrollbar"))])
        phone = media_wins("(max-width: 640px)", ".nav")
        self.assertEqual(phone["grid-template-columns"], "repeat(3, minmax(0, 1fr))")  # a phone: 2 rows of 3
        self.assertEqual(media_wins(PHONE, ".nav-item")["min-height"], "44px")  # the summary is a .nav-item too
        summary = media_wins(PHONE, ".nav-more > summary")
        self.assertEqual((summary["cursor"], summary["list-style"]), ("pointer", "none"))
        self.assertEqual(media_wins(PHONE, ".nav-more > summary::-webkit-details-marker")["display"], "none")
        # the open fold: a white card under the menu, over the page; the top bar does not cut it
        card = media_wins(PHONE, ".nav-more-list")
        self.assertEqual((card["position"], card["top"], card["left"], card["right"], card["background"]),
                         ("absolute", "calc(100% + 4px)", "0", "0", "var(--surface)"))
        self.assertEqual(media_wins("(max-width: 640px)", ".nav-more-list")["grid-template-columns"],
                         "repeat(2, minmax(0, 1fr))")
        self.assertEqual(media_wins(PHONE, ".sidebar")["overflow"], "visible")
        # the summary of a fold that holds the current page has the current-page look
        for selector in ('.nav-item[aria-current="page"]', '.nav-more:has([aria-current="page"]) > summary'):
            rule = rule_props(selector)
            self.assertEqual((rule["background"], rule["color"], rule["font-weight"]),
                             ("var(--gradient)", "var(--on-accent)", "600"), selector)
            self.assertEqual(rule_props(selector + ":hover")["background"], "var(--accent-dark)", selector)
        # paper: print.css hides the menu, so the fold too, and the skip link (.no-print)
        hidden = {selector for selector, _parts in print_hide_selectors()}
        self.assertLessEqual({".sidebar", "nav", ".no-print"}, hidden)

    def test_a_skip_link_is_the_first_stop_of_both_page_shells(self):
        for path, status in (("/people", 200), ("/families", 200), ("/no-such-page", 404)):
            page = self.page(path, expect=status)
            body = page.split("<body>\n", 1)[1]
            skip = self.SKIP.format(ui.t("core.skip_to_content", self.lang(page)))
            self.assertTrue(body.startswith(skip), (path, body[:160]))
            self.assertEqual(page.count('id="main"'), 1, path)
            self.assertEqual(page.count('href="#main"'), 1, path)
            self.assertIn('<main class="canvas" id="main" tabindex="-1">', page, path)
        bare = ui.bare_page("X", "")  # the page for a church copy that cannot be read (no request: Vietnamese)
        self.assertTrue(bare.split("<body>\n", 1)[1].startswith(self.SKIP.format("Chuyển đến nội dung")))
        self.assertIn('<main class="canvas" id="main" tabindex="-1">', bare)
        # out of sight until it has the focus; then top left, above everything, with the one ring
        link = rule_props(".skip-link")
        self.assertEqual((link["position"], link["top"], link["left"], link["transform"], link["min-height"]),
                         ("fixed", "8px", "8px", "translateY(-200%)", "44px"))
        self.assertEqual((link["background"], link["color"]), ("var(--surface)", "var(--accent-text)"))
        self.assertNotIn("outline", link)
        self.assertNotIn("box-shadow", link)  # no shadow peeks into the window while it is out of sight
        focus = rule_props(".skip-link:focus")
        self.assertEqual((focus["transform"], focus["box-shadow"]), ("none", "var(--shadow-raised)"))
        self.assertIn("outline: 2px solid var(--accent-text)", declarations(":focus-visible"))
        z_index = int(link["z-index"])
        self.assertGreater(z_index, int(media_wins(PHONE, ".nav-more-list")["z-index"]))
        self.assertGreater(z_index, int(rule_props(".results")["z-index"]))


def title_head(page):
    """The ``<header class="title-row">`` of a page: the h1, the line under it and the actions."""
    return re.search(r'<header class="title-row">.*?</header>', page, re.S).group(0)


class CritThreeTest(PagesTestBase):
    """CRIT-3, the design critique of 2026-11-14 (row 8). Under 861px the title-row actions sit side by side at
    their own width and wrap (gap 8px), the primary button first; the Dashboard search keeps a whole row above
    its button. From 861px the actions are as before. No number or button twice: the line under the h1 leaves
    the counts to the People chips (it shows only how many a search found), the Balance to its Money card, the
    Next number to its Sent documents card (and the /sent/new form) and how many need a visit to the Dashboard
    card; the Record buttons of Money are in the title row only, not again on the Offerings and Expenses cards."""

    def test_under_861px_the_actions_sit_side_by_side_the_primary_first(self):
        self.assertEqual(media_wins(PHONE, ".title-row .actions"), {"flex-wrap": "wrap", "gap": "8px"})  # a row
        self.assertEqual(media_wins(PHONE, ".title-row .actions > .primary"), {"order": "-1"})
        self.assertEqual(media_wins(PHONE, ".title-row .title-search"), {"order": "-2", "flex": "1 1 100%"})
        self.assertFalse([sel for sel, body in media_rules(PHONE) if ".title-row" in sel and "width: 100%" in body])
        self.assertEqual(whole_rule(top_level_rules(), ".title-row .actions"),
                         {"display": "flex", "align-items": "flex-end", "gap": "12px", "flex": "none"})  # from 861px

    def test_people_counts_are_on_the_chips_and_a_search_says_how_many_it_found(self):
        everyone = people.list_persons(self.db())
        page = self.page("/people")
        self.assertIn(f'aria-current="true">All <span class="num">{len(everyone)}</span></a>', page)
        # the line under the h1 is for paper only (print.css hides the chips): no screen rule shows it
        self.assertIn(f'<p class="sub"><span class="on-paper">{len(everyone)} People</span></p>', title_head(page))
        self.assertEqual(media_wins("screen", ".title-row .sub:has(> .on-paper)"), {"display": "none"})
        self.assertNotIn("on-paper", (ROOT / "web" / "print.css").read_text(encoding="utf-8"))
        member = lists.find_item(self.db(), "status", code="member")["id"]
        members = sum(1 for r in everyone if r["status_id"] == member)
        self.assertIn(f'<span class="on-paper">{members} of {len(everyone)} People</span>',
                      self.page(f"/people?status={member}"))
        found = self.page("/people?q=Nguyen")
        n = parse_panels(found).rows["people"]
        self.assertGreater(n, 0)
        self.assertIn(f'<p class="sub">{n} of {len(everyone)} People</p>', title_head(found))

    def test_money_shows_the_balance_on_its_card_and_each_record_button_once(self):
        for path in ("/money", "/money?month=1950-01"):  # a month with data and an empty one
            page = self.page(path)
            head = title_head(page)
            self.assertRegex(head, r'<p class="sub">[^<·₫]+</p>', path)  # the month only
            self.assertNotIn("₫", head, path)
            self.assertRegex(page, r'<span class="kpi-label">Balance</span><span class="kpi-value num strong[^"]*">'
                                   r'-?[\d.]+ ₫</span>')
            for href in ("/money/offerings/new", "/money/expenses/new"):
                self.assertEqual(page.count(f'href="{href}"'), 1, (path, href))
                self.assertIn(f'href="{href}"', head, (path, href))

    def test_sent_documents_show_the_next_number_on_its_card_only(self):
        conn = self.db()
        for year in (TODAY.year, 1950):  # a year with Sent documents and an empty one
            next_no = sent.next_number(conn, year)
            page = self.page(f"/sent?year={year}")
            head = title_head(page)
            self.assertNotIn(next_no, head, year)
            self.assertRegex(head, rf'<p class="sub">{year} · \d+ Sent documents? · newest first</p>')
            self.assertEqual(page.count(f">{next_no}<"), 1, year)  # a date like 07/04/2026 does not count
            self.assertIn(next_no, section(page, "next-number"), year)
        self.assertIn(sent.next_number(conn, TODAY.year), self.page("/sent/new"))  # where the next one is made

    def test_the_dashboard_says_how_many_need_a_visit_on_the_card_only(self):
        page = self.page("/")
        self.assertNotIn("visit", title_head(page).split('<div class="actions">')[0])
        self.assertIn('<span class="count num">', section(page, "needs-visit"))


CRIT_FIX = "screen and (max-width: 860px)"  # the language switch on the h1 line (CRIT-FIX-1)
SMALL = "(max-width: 640px)"  # a phone


class CritFixOneTest(PagesTestBase):
    """CRIT-FIX-1, fix round 1 of the design critique (row 8: CRIT-3 Major M1 and Minors m1-m3). Under 861px the
    language switch has no row of its own: it sits at the top right of the canvas, level with the first line of
    the h1, which keeps 160px free at its right on that line only; with a flash it goes back in the flow above
    the flash. Under 641px the People search label is for screen readers only (still the label of the field),
    the field and Search sit on one line, and the bar and its chips are one notch tighter, every chip in view.
    The Money head reads Record Offering, Record Expense, Year report; the Dashboard search field never pushes
    the page sideways; the Sent documents line says "newest first" again; 5 keys no code used are gone. From
    861px nothing moves."""

    def test_under_861px_the_language_switch_sits_on_the_first_h1_line(self):
        self.assertEqual(media_wins(CRIT_FIX, ".lang-switch"),
                         {"position": "absolute", "z-index": "1", "top": "29px", "right": "28px", "margin": "0"})
        self.assertIn("position: relative", declarations(".canvas"))  # the box the switch is placed in
        # round 4, the title is in a card (1px edge, 16px padding): 29px + a 44px tap = 73px = the 16px canvas
        # padding + 1px + 16px + 4px + one 36px h1 line: the switch ends where the first h1 line ends, so the
        # line under it (the next h1 line or the sub line) is never under it
        self.assertIn("padding: 16px", media_props(PHONE, ".title-row"))
        self.assertIn("padding: 16px", media_props(PHONE, ".canvas"))
        self.assertIn("min-height: 44px", media_props(PHONE, ".lang-switch button"))
        self.assertEqual(rule_props(".title-row h1")["line-height"], "36px")
        self.assertEqual(media_wins(CRIT_FIX, ".lang-switch + .title-row h1"), {"padding-top": "4px"})
        # the first h1 line keeps the switch width free (a 1px float: that line only)
        self.assertEqual(media_wins(CRIT_FIX, ".lang-switch + .title-row h1::before"),
                         {"content": '""', "float": "right", "width": "160px", "height": "1px"})
        # a flash comes first: the switch goes back in the flow above it, as on every page from 861px
        self.assertEqual(media_wins(CRIT_FIX, ".canvas:has(> .flash) > .lang-switch"),
                         {"position": "static", "margin": "0 12px 4px"})
        self.assertIn("margin: 0 12px 4px", declarations(".lang-switch"))
        # the page order these rules use: the switch, the flash (when there is one), then the title row
        main = re.escape('<main class="canvas" id="main" tabindex="-1">')
        self.assertRegex(self.page("/people"), main + r'<form class="lang-switch"[^>]*>.*?</form><header class="title-row">')
        self.assertRegex(self.page("/people?msg=Saved"), main + r'<form class="lang-switch"[^>]*>.*?</form>'
                                                         r'<p class="flash" role="status">Saved</p><header class="title-row">')
        # screen only: on paper the h1 keeps its whole line; from 861px no rule moves the switch
        self.assertTrue(CRIT_FIX.startswith("screen and "))
        self.assertNotIn("position", whole_rule(top_level_rules(), ".lang-switch"))

    def test_under_641px_the_people_search_is_one_line_with_a_label_for_screen_readers(self):
        self.assertEqual(media_wins(SMALL, ".toolbar label"), rule_props(".sr-only"))  # the .sr-only look, by CSS
        page = self.page("/people?q=Nguyen")
        self.assertIn('<label for="people-q">Find in this list</label>', page)  # still the label of the field
        self.assertIn('<input class="input" id="people-q"', page)
        # the field grows (flex 1, min-width 0) beside Search; Clear wraps only when the field would get under 80px
        self.assertEqual(media_wins(SMALL, ".toolbar .input"), {"flex-basis": "80px"})
        self.assertIn("flex: 1", declarations(".toolbar .input"))
        self.assertIn("min-width: 0", declarations(".input"))
        self.assertEqual(media_wins(SMALL, ".toolbar .search-line"), {"flex-wrap": "wrap"})

    def test_under_641px_the_bar_is_tighter_and_every_chip_stays_in_view(self):
        self.assertEqual(media_wins(SMALL, ".list-toolbar"), {"gap": "8px", "margin-bottom": "12px", "padding": "8px 12px"})
        chip = media_wins(SMALL, ".chip")
        self.assertEqual((chip["padding"], chip["min-height"]), ("0 12px", "44px"))
        self.assertIn("flex-wrap: wrap", declarations(".chips"))  # the chips wrap: no strip that scrolls sideways
        self.assertNotRegex(" ".join(body for sel, body in css_rules() if "chip" in sel), r"overflow|nowrap|scroll")

    def test_under_861px_the_money_head_reads_record_offering_record_expense_year_report(self):
        self.assertEqual(media_wins(PHONE, ".title-row .actions > .primary"), {"order": "-1"})
        self.assertEqual(media_wins(PHONE, '.title-row .actions > [href^="/money/year"]'), {"order": "1"})
        links = re.findall(r'<a class="btn (\w+)" href="([^"]+)">([^<]+)</a>', title_head(self.page("/money")))
        self.assertEqual([text for _kind, _href, text in links], ["Year report", "Record Expense", "Record Offering"])

        def order(link):  # the CSS order under 861px; one order keeps the page order
            kind, href, _text = link
            return -1 if kind == "primary" else 1 if href.startswith("/money/year") else 0
        self.assertEqual([text for _kind, _href, text in sorted(links, key=order)],
                         ["Record Offering", "Record Expense", "Year report"])
        # from 861px the head keeps the page order
        self.assertFalse([sel for sel, body in top_level_rules() if ".title-row" in sel and re.search(r"(^|;)\s*order:", body)])

    def test_under_861px_the_dashboard_search_field_never_pushes_the_page_sideways(self):
        # its own width (about 20 characters) and Search were wider than a 360px phone in vi (361px); width 0,
        # the field takes what the button leaves
        self.assertEqual(media_wins(PHONE, ".title-search .input"), {"width": "0", "flex": "1"})
        self.assertEqual(whole_rule(top_level_rules(), ".title-search .input"), {"width": "clamp(180px, 22vw, 300px)"})

    def test_the_sent_documents_line_says_newest_first_and_unused_words_are_gone(self):
        from churchmgr import i18n
        year = TODAY.year
        n = len(sent.list_sent_documents(self.db(), year))
        head = title_head(self.page(f"/sent?year={year}"))
        self.assertRegex(head, rf'<p class="sub">{year} · {n} Sent documents? · newest first</p>')
        self.assertEqual(i18n.t("sent.sub", "vi", year=year, count=i18n.tn("sent.count", 3, "vi")),
                         f"{year} · 3 Công văn đi · mới nhất trước")
        for key in ("dashboard.finding_needs_one", "dashboard.finding_needs_many", "money.state_up",
                    "money.state_down", "money.finding"):
            for lang in ("vi", "en"):
                self.assertNotIn(key, i18n.TEXT[lang], (key, lang))



class CritFourTest(PagesTestBase):
    """CRIT-4, critique rows 4 and 5. Row 4: the Dashboard card of today and the 6 days after is "Next 7 days"
    ("7 ngày tới"); its foot link opens the Calendar 7-day view, with the same count. The Calendar chip
    "This week" (Monday to Sunday) keeps its words. Row 5, the DASH RULE: 1. no Dashboard list scrolls inside
    its card; 2. every row shown is whole; 3. each list shows at most a fixed number of rows and its foot link
    then names the full count; 4. from 1181px the page fits 1440x900 and 1280x800 with titles on 2 lines (rule
    4 is measured in a browser: see the card)."""

    def test_row_4_next_7_days_is_today_and_the_6_days_after(self):
        from churchmgr.i18n import t
        page = self.page("/")
        week = section(page, "this-week")
        last = TODAY + dt.timedelta(days=6)
        self.assertIn(f'<h2 id="p-this-week">Next 7 days</h2><span class="meta">{TODAY:%d/%m} – {last:%d/%m/%Y}</span>',
                      week)
        self.assertIn(f'<a class="card-link" href="/calendar?from={TODAY.isoformat()}">', week)
        self.assertRegex(page, r'<p class="sub">[^<]* · \d+ Calendar items? in the next 7 days</p>')
        self.assertEqual([t("dashboard.this_week", lang) for lang in ("vi", "en")], ["7 ngày tới", "Next 7 days"])
        self.assertEqual(t("dashboard.nothing_week", "vi"), "7 ngày tới không có gì trong Lịch.")
        # the Monday-to-Sunday chip of the Calendar keeps "This week"
        self.assertEqual([t("calendar.this_week", lang) for lang in ("vi", "en")], ["Tuần này", "This week"])
        self.assertIn(">This week</a>", self.page("/calendar"))

    def test_dash_rule_1_no_dashboard_list_scrolls_in_its_card(self):
        for sel, body in css_rules():
            if ".dashboard" in sel:
                self.assertNotRegex(body, r"overflow|scrollbar|overscroll", sel)
        for panel in DASH_LISTS:  # no rule gives a list a height: it is as high as its rows
            self.assertFalse([sel for sel, _body in css_rules() if f'[data-panel="{panel}"] .rows' in sel], panel)
        # the canvas is not one window high any more: the cards are as high as their rows; a short window scrolls
        # the page, never a card
        self.assertEqual(media_wins(WIDE, ".canvas:has(> .dashboard)"), {"padding-bottom": "12px"})
        self.assertNotIn("max-height", media_wins(WIDE, '.dashboard > [data-panel="sent-documents"]'))  # 2 whole rows
        self.assertIn("max-height: var(--dash-row2)", media_props(WIDE, CARD))  # Money this month as before

    def test_dash_rule_4_the_sent_date_line_is_one_line_from_1181px(self):
        # a long Recipient name (date · Recipient · Purpose on 2 lines) made the page 814px high at 1280x800 en:
        # from 1181px that line is one line; the whole of it stays in its title, and every other list keeps 2
        sub = '.dashboard > [data-panel="sent-documents"] .row .what .sub'
        self.assertEqual(media_wins(WIDE, sub), {"-webkit-line-clamp": "1", "line-clamp": "1"})
        self.assertIn("-webkit-line-clamp: 2", declarations(".row .what .clamp-2"))
        self.assertEqual(sum(sub in sel for sel, _body in css_rules()), 1)  # only there: on paper and under 1181px 2
        self.assertRegex(section(self.page("/"), "sent-documents"), r'<span class="clamp-2 sub" title="[^"]+">')

    def test_dash_rule_3_each_list_shows_a_fixed_number_of_rows_and_names_the_full_count(self):
        # at most 5 / 5 / 2 by the rule; lower so the page fits 1280x800 with titles on 2 lines (rule 4)
        self.assertEqual((dashboard.WEEK_ROWS, dashboard.VISIT_ROWS, dashboard.SENT_ROWS), (4, 3, 2))
        conn = self.db()
        for i in range(6):
            cal.add_calendar_item(conn, "Meeting", f"CRIT-4 Họp {i}", f"{TODAY + dt.timedelta(days=i):%Y-%m-%d} 20:00")
        recipient = lists.find_item(conn, "recipient", name="Giáo hội")["id"]
        purpose = lists.find_item(conn, "purpose", name="Report")["id"]
        for i in range(3):
            sent.add_sent_document(conn, TODAY.isoformat(), recipient, purpose, f"CRIT-4 Báo cáo {i}")
        week_n = len(cal.items_between(conn, TODAY, TODAY + dt.timedelta(days=6)))
        visit_n = len(care.needs_visit(conn, TODAY))
        sent_n = len(sent.list_sent_documents(conn, TODAY.year))
        page = self.page("/")
        for name, cap, n, words in (("this-week", dashboard.WEEK_ROWS, week_n, f"View all {week_n} in Calendar"),
                                    ("needs-visit", dashboard.VISIT_ROWS, visit_n, f"View all {visit_n} in Care"),
                                    ("sent-documents", dashboard.SENT_ROWS, sent_n, f"View all {sent_n}")):
            box = section(page, name)
            self.assertGreater(n, cap, name)
            self.assertEqual(box.count('<li class="row" data-row>'), cap, name)
            self.assertRegex(box, rf'<footer><a class="card-link" href="[^"]+">{re.escape(words)}</a></footer>$', name)

    def test_dash_rule_3_the_sent_documents_link_names_the_count_only_when_there_are_more(self):
        from churchmgr.i18n import t
        row = {"date": TODAY.isoformat(), "recipient_name": "Giáo hội", "purpose_name": "Report",
               "number": f"01/{TODAY.year}", "subject": "CRIT-4"}
        self.assertEqual([t("dashboard.view_all_sent", lang, n=3) for lang in ("vi", "en")],
                         ["Xem tất cả 3", "View all 3"])
        opened = t("dashboard.open_sent")  # outside a request: the default language
        for count, words in ((0, opened), (2, opened), (3, t("dashboard.view_all_sent", n=3)),
                             (40, t("dashboard.view_all_sent", n=40))):
            box = dashboard._sent_documents("05/2026", (count, [row] * min(count, 2)), TODAY.year, "span-4")
            self.assertIn(f'<footer><a class="card-link" href="/sent">{words}</a></footer>', box, count)
        # 1 this year and last year's newest under it: /sent lists this year only (1), so no count is named
        box = dashboard._sent_documents("02/2026", (1, [row, row]), TODAY.year, "span-4")
        self.assertIn(f">{opened}</a>", box)


class CritFiveTest(PagesTestBase):
    """CRIT-5, critique row 10: the Copies page puts its developer words (church.db, --copy, current.txt, full
    paths, sizes in bytes) under one "Technical details" fold per panel that holds them: a ``<details
    class="tech">``, closed at the start, that opens with no JS. Its summary shares the Rename rule (a plain word
    in the app color, weight 400), is a 44px tap under 861px, and has a drawn chevron that turns when it opens.
    The words of both languages, inside and outside the folds: test_i18n_copies.CopiesScreensTest."""

    def test_the_fold_has_the_rename_look_and_a_drawn_chevron(self):
        top = top_level_rules()
        shared = whole_rule(top, "details.tech > summary, details.rename > summary")
        self.assertEqual((shared["color"], shared["font-weight"], shared["list-style"], shared["min-height"]),
                         ("var(--accent-text)", "400", "none", "36px"))
        marker = "details.tech > summary::-webkit-details-marker, details.rename > summary::-webkit-details-marker"
        self.assertEqual(whole_rule(top, marker), {"display": "none"})
        self.assertEqual(whole_rule(top, "details.tech > summary"), {"gap": "8px", "margin-left": "-4px"})
        chevron = whole_rule(top, "details.tech > summary::after")
        self.assertEqual((chevron["content"], chevron["border-width"], chevron["transform"]),
                         ('""', "0 1.5px 1.5px 0", "translateY(-2px) rotate(45deg)"))
        self.assertEqual(whole_rule(top, "details.tech[open] > summary::after"),
                         {"transform": "translateY(2px) rotate(-135deg)"})
        rule = media_wins(PHONE, "details.tech > summary")
        self.assertEqual((rule.get("display"), rule.get("align-items"), rule.get("min-height")),
                         ("inline-flex", "center", "44px"))

    def test_the_copies_page_has_one_closed_fold_per_panel_with_developer_words(self):
        page = self.page("/copies")
        self.assertEqual(page.count("<details"), 4, "the menu's More fold and 3 Technical details folds")
        for name in ("this-copy", "copies", "handover"):
            box = section(page, name)
            self.assertEqual(box.count("<details"), 1, name)
            self.assertIn('<details class="tech"><summary>Technical details</summary>', box, name)
        self.assertNotIn("<details", section(page, "new-church-setup"))  # no developer word there


class CritSixTest(PagesTestBase):
    """CRIT-6, critique row 12 (the pastor chose A: the All list keeps everyone). In the People list a Person
    whose current Status is Left or Passed away (care.NOT_CARED_STATUS_CODES) keeps the row, the name link
    and the phone, but the row is ``inactive``: its text is --muted (4.5:1 on --surface and on the --raised
    hover for any app color: StyleTokensTest) and its Status is a ``.tag`` at the start of its cell. The links
    keep the app color (CRIT-1). Member, Attender and Visitor rows are as before. A search finds them too."""

    ROW = re.compile(r'<tr data-row(?: class="([^"]*)")?><td><a href="/people/(\d+)">(.*?)</tr>', re.S)

    def rows(self, path):
        """``{person id: (row class, row html)}`` of the People table of ``path``."""
        body = re.search(r"<tbody>(.*?)</tbody>", self.page(path), re.S).group(1)
        found = {int(pid): (cls or "", html_) for cls, pid, html_ in self.ROW.findall(body)}
        self.assertEqual(len(found), body.count("<tr data-row"), "every row starts with its name link")
        return found

    def test_the_muted_row_and_the_tag_in_style_css(self):
        top = top_level_rules()
        self.assertEqual(whole_rule(top, "table.people tr.inactive > td"), {"color": "var(--muted)"})
        self.assertEqual(whole_rule(top, "table.people td > .tag"),
                         {"margin-left": "0", "vertical-align": "baseline"})  # the row keeps its height
        tag = whole_rule(top, ".tag")
        self.assertEqual((tag["background"], tag["color"]), ("var(--active)", "var(--muted)"))
        for surface in ("--surface", "--raised", "--active"):  # the row, its hover, the tag
            self.assertIn(("--muted", surface), TEXT_PAIRS, surface)
        # the links of the row keep the app color: no rule paints a link of an inactive row
        self.assertFalse([sel for sel, _b in css_rules() if "inactive" in sel and " a" in sel])

    def test_left_and_passed_away_rows_are_muted_with_a_status_tag_and_all_keeps_everyone(self):
        persons = people.list_persons(self.db())
        inactive = {p["id"]: p for p in persons if p["status_code"] in ("left", "passed_away")}
        self.assertEqual({p["status_code"] for p in inactive.values()}, {"left", "passed_away"})  # the fake has both
        rows = self.rows("/people")
        self.assertEqual(set(rows), {p["id"] for p in persons})  # row12 = A: All shows everyone
        page = self.page("/people")
        self.assertRegex(page, rf'<a class="chip" href="/people" aria-current="true">[^<]+ '
                               rf'<span class="num">{len(persons)}</span></a>')  # the All count is its rows
        for p in persons:
            cls, row = rows[p["id"]]
            if p["id"] in inactive:
                self.assertEqual(cls, "inactive", p["full_name"])
                self.assertIn(f'<td><span class="tag">{ui.h(p["status_name"])}</span></td>', row)
                if p["phone"]:
                    self.assertIn(f'<span class="num">{ui.h(p["phone"])}</span>', row)  # the phone stays
            else:
                self.assertEqual(cls, "", p["full_name"])
                self.assertNotIn('class="tag"', row, p["full_name"])
        # the Status chip of Left and of Passed away still lists them, muted
        for code in ("left", "passed_away"):
            chip_rows = self.rows(f"/people?status={self.item('status', code=code)}")
            self.assertEqual({pid for pid in chip_rows}, {i for i, p in inactive.items() if p["status_code"] == code})
            self.assertEqual({cls for cls, _r in chip_rows.values()}, {"inactive"})

    def test_a_search_finds_a_person_who_left_and_marks_the_row(self):
        pid = self.new_person("Trịnh Văn Khải Crit Sáu", status_code="left", phone="0901 234 567")
        rows = self.rows("/people?q=" + urllib.parse.quote("Khải Crit Sáu"))
        self.assertEqual(list(rows), [pid])
        cls, row = rows[pid]
        self.assertEqual(cls, "inactive")
        self.assertIn('<span class="tag">', row)
        self.assertIn('<span class="num">0901 234 567</span>', row)

    def test_table_rows_have_no_class_unless_one_is_given(self):
        from churchmgr.pages import people as people_pages
        plain = people_pages.table([("A", False)], [["x"], ["y"]])
        self.assertEqual(plain.count("<tr data-row>"), 2)
        marked = people_pages.table([("A", False)], [["x"], ["y"], ["z"]], "people", ["", "inactive"])
        self.assertEqual(re.findall(r"<tr data-row(?: class=\"(\w+)\")?>", marked), ["", "inactive", ""])


class CritSevenTest(PagesTestBase):
    """CRIT-7, critique row 6 (the pastor chose B): the one dark card of the Dashboard is Needs a visit, so the
    people who need care come before money. Money this month is a white card like the others: its amounts in
    ink, the Balance green or red (STYLE-5: green and red on money amounts only). On the dark card a name is
    white like the words beside it, so a line (--highlight-line, 3:1 on each stop for any app color) shows it is
    a link; under the pointer and on keyboard focus the line turns white. The card shape and the DASH RULE stay
    (the sizes are measured in a browser: see the card)."""

    LINK = ':where(.dashboard > [data-panel="needs-visit"] .row .what) a'

    def test_money_this_month_is_a_white_card(self):
        # no rule paints the Money card: no fill, no shadow, no edge color, no token of its own
        for sel, body in css_rules():
            if "money-month" in sel:
                self.assertNotRegex(body, r"(^|;)\s*(--[\w-]+|background[\w-]*|color|box-shadow|border-color)\s*:", sel)
        self.assertNotIn("money-month", (ROOT / "web" / "print.css").read_text(encoding="utf-8"))
        self.assertNotIn("color", rule_props(".kpi-value"))  # the amounts take the ink of the white card
        self.assertEqual(rule_props(".kpi-value.strong:not(.neg)")["color"], "var(--positive)")  # Balance 0 or more
        # the Balance on a dark fill is gone with its 2 tokens
        for name in ("style.css", "print.css"):
            self.assertNotRegex((ROOT / "web" / name).read_text(encoding="utf-8"), r"--(positive|negative)-on-dark", name)
        # the real page: Money this month keeps its 3 amounts, as a plain panel
        self.add_offering()
        money_box = section(self.page("/"), "money-month")
        self.assertEqual(money_box.count('class="kpi-value num'), 3)
        self.assertIn('class="kpi-value num strong"', money_box)

    def test_a_name_on_the_dark_card_is_underlined_to_show_it_is_a_link(self):
        line = rule_props(self.LINK)
        self.assertEqual((line["text-decoration"], line["text-decoration-color"], line["text-decoration-thickness"],
                          line["text-underline-offset"]), ("underline", "var(--highlight-line)", "1px", "3px"))
        # the line: white over the lightest stop, 3:1 on each stop for any app color (StyleTokensTest)
        self.assertEqual(root_tokens()["--highlight-line"],
                         "color-mix(in srgb, var(--highlight-ink) 65%, var(--highlight-end))")
        for stop in HIGHLIGHT_STOPS:
            self.assertIn(("--highlight-line", stop), PART_PAIRS, stop)
        # one class stronger: under the pointer and on keyboard focus the shorthand draws the line in white
        for selector in ("a:hover", ":where(.row .what) a:focus-visible"):
            self.assertEqual(rule_props(selector)["text-decoration"], "underline", selector)
        # one tag weight: the later "a" rule of print.css keeps the name plain ink on paper
        self.assertEqual(rule_props("a", "print.css")["text-decoration"], "none")
        self.assertEqual(rule_props(DARK_CARD, "print.css")["--highlight-line"], "#888")
        # only the dark card: the names of Needs a visit on the Care page keep the app color, no line at rest
        self.assertEqual([sel for sel, body in css_rules() if "text-decoration: underline" in body
                          and "needs-visit" in sel], [self.LINK])
        # the real page: each name of the dark card is a link inside .row .what
        visit = section(self.page("/"), "needs-visit")
        names = re.findall(r'<li class="row" data-row><span class="what wrap"><span class="clamp-2" lang="vi" '
                           r'title="[^"]+"><a href="/people/\d+">', visit)
        self.assertEqual(len(names), dashboard.VISIT_ROWS)

    def add_offering(self):
        conn = self.db()
        money.add_offering(conn, TODAY.isoformat(), 100_000, lists.find_item(conn, "fund", name="General")["id"])


class CritEightTest(PagesTestBase):
    """CRIT-8, critique row 9: the period bar of the Calendar and Money is one nav. Prev / This / Next sit in
    ``.period``, a grid of one row: no chip goes to the next line alone (on a phone the words of Prev and Next
    may take 2 lines inside the pill; the middle chip keeps one line). The month chips say ``‹ MM/YYYY`` and
    ``MM/YYYY ›``. The view chips (``.views``: Week, Month) and the "Go to a month" picker follow. The picker
    opens the chosen month on change with app.js (``data-auto-submit``, its 5th job); style.css hides Show only
    under ``html.js``, so with no script Show sends the form. The sizes (one line at 390 and 360px, vi and en,
    no sideways scroll) and the picker with the script on and off are measured in a browser: see the card."""

    CHIP = r'<a class="chip" href="([^"]+)"(?: aria-current="true")?>([^<]+)</a>'

    def bar(self, path):
        """``(nav label, [(href, words)] of .period, [(href, words)] of .views, the picker form)`` of ``path``."""
        page = self.page(path)
        nav = re.search(r'<nav class="list-toolbar" aria-label="([^"]+)">(.*?)</nav>', page, re.S)
        self.assertIsNotNone(nav, path)
        period = re.search(r'<div class="period">(.*?)</div>', nav.group(2), re.S).group(1)
        views = re.search(r'<div class="chips views">(.*?)</div>', nav.group(2), re.S)
        form = re.search(r'<form class="month-picker".*?</form>', nav.group(2), re.S).group(0)
        return (nav.group(1), re.findall(self.CHIP, period), re.findall(self.CHIP, views.group(1)) if views else [],
                form)

    def test_the_month_chips_say_mm_yyyy_and_the_view_chips_stand_apart(self):
        this = f"{TODAY:%Y-%m}"
        label, period, views, _form = self.bar("/calendar?month=2030-01")
        self.assertEqual(label, "Calendar months")
        self.assertEqual(period, [("/calendar?month=2029-12", "‹ 12/2029"), (f"/calendar?month={this}", "This month"),
                                  ("/calendar?month=2030-02", "02/2030 ›")])
        self.assertEqual(views, [("/calendar?week=2030-01-01", "Week")])
        label, period, views, _form = self.bar("/money?month=2030-01")
        self.assertEqual(label, "Money months")
        self.assertEqual(period, [("/money?month=2029-12", "‹ 12/2029"), ("/money", "This month"),
                                  ("/money?month=2030-02", "02/2030 ›")])
        self.assertEqual(views, [])
        from churchmgr.pages import calendar as cal_pages
        self.assertEqual(cal_pages.month_chip("{} ›", "/money", (1900, 2)),
                         '<a class="chip" href="/money?month=1900-02">02/1900 ›</a>')  # the same in Tiếng Việt: no t()
        self.assertEqual(cal_pages.month_chip("‹ {}", "/money", None), "")

    def test_week_and_7_day_chips_keep_their_words_and_every_period_stays_reachable(self):
        label, period, views, _form = self.bar("/calendar?week=2030-01-07")
        self.assertEqual(label, "Calendar weeks")
        self.assertEqual(period, [("/calendar?week=2029-12-31", "‹ Previous week"), ("/calendar", "This week"),
                                  ("/calendar?week=2030-01-14", "Next week ›")])
        self.assertEqual(views, [("/calendar?month=2030-01", "Month")])
        label, period, views, _form = self.bar("/calendar?from=2030-01-07")
        self.assertEqual(label, "Calendar 7 days")
        self.assertEqual(period, [("/calendar?from=2029-12-31", "‹ Previous 7 days"),
                                  (f"/calendar?from={TODAY.isoformat()}", "From today"),
                                  ("/calendar?from=2030-01-14", "Next 7 days ›")])
        self.assertEqual(views, [("/calendar?week=2030-01-07", "Week"), ("/calendar?month=2030-01", "Month")])

    def test_the_picker_opens_a_month_on_change_and_keeps_show_for_pages_without_the_script(self):
        for path, action, field, show in (("/calendar", "/calendar", "cal-month", "Show"),
                                          ("/calendar?from=2030-01-07", "/calendar", "cal-month", "Show"),
                                          ("/money", "/money", "money-month", "Show")):
            form = self.bar(path)[3]
            self.assertTrue(form.startswith(f'<form class="month-picker" action="{action}" method="get" '
                                            'data-auto-submit>'), path)
            self.assertIn(f'id="{field}" name="month" type="month"', form)
            self.assertIn(f'<button class="btn secondary" type="submit">{show}</button>', form)  # no script: Show
        # style.css hides Show only when app.js has run (html.js); no other rule hides it
        self.assertEqual(rule_props('.js form[data-auto-submit] button[type="submit"]'), {"display": "none"})
        self.assertEqual([sel for sel, _body in css_rules() if "data-auto-submit" in sel],
                         ['.js form[data-auto-submit] button[type="submit"]'])
        js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        code = re.sub(r"^\s*//.*$", "", js, flags=re.M)
        self.assertIn("Six jobs", js)  # round 4: the money amounts count up
        # html.js is set first, before any job: then CSS may hide what the script replaces
        self.assertLess(code.index('document.documentElement.classList.add("js")'), code.index("querySelectorAll"))
        job = code[code.index('querySelectorAll("form[data-auto-submit]")'):]
        for part in ('input[type=month]', '"change"', "checkValidity()", "/^[0-9]{4}-[0-9]{2}$/",
                     "input.defaultValue", "requestSubmit", '"keydown"', '"blur"', '"pageshow"'):
            self.assertIn(part, job)
        self.assertNotIn("innerHTML", code)

    def test_prev_this_next_are_one_row_that_never_wraps_a_chip(self):
        period = rule_props(".period")
        self.assertEqual((period["display"], period["grid-auto-flow"], period["justify-content"]),
                         ("grid", "column", "start"))
        chip = rule_props(".period > .chip")
        self.assertEqual((chip["text-wrap"], chip["text-align"], chip["line-height"]), ("balance", "center", "18px"))
        # the middle chip (This week, From today, This month) keeps its one line when Prev and Next are there
        self.assertEqual(rule_props(".period:has(> :nth-child(3)) > :nth-child(2)"), {"min-width": "max-content"})
        self.assertEqual(rule_props(".list-toolbar > .views"), {"margin-right": "auto"})
        # a phone: the three take line 1, one notch tighter; the picker may sit beside the view chips
        self.assertEqual(media_wins(SMALL, ".period"), {"flex": "1 1 100%", "gap": "6px"})
        self.assertEqual(media_wins(SMALL, ".period > .chip"), {"padding": "0 10px"})
        self.assertEqual(media_wins(SMALL, ".month-picker"), {"flex": "1 1 auto"})
        self.assertEqual(media_wins(SMALL, ".year-form"), {"flex": "1 1 100%"})
        for sel, body in css_rules():
            if "period" in sel:
                self.assertNotRegex(body, r"overflow|nowrap|scroll|flex-wrap", sel)  # no strip that scrolls


class CritNineTest(PagesTestBase):
    """CRIT-9, the polish rows of the design critique. Row 13: in the Calendar an empty day is one short line,
    its date in grey and a faint dash; "Nothing on the Calendar" stays for screen readers only (.sr-only); a
    date is weight 400, lighter than the titles of its items (500). Row 14, the 48px fade of the wash: see
    StyleFix1Test. Row 15, Needs a visit ties by given name: tests/test_care.py. The Services chart scale that
    fits the counts: tests/test_server.py. The Offerings table ends with a total row as the Expenses table (it
    had one already). The heights, weights and looks are measured in a browser: see the card."""

    NONE = ('<p class="cal-none"><span class="dash" aria-hidden="true">—</span>'
            '<span class="sr-only">Nothing on the Calendar.</span></p>')

    def test_an_empty_day_is_its_date_and_a_faint_dash(self):
        empty = self.page(f"/calendar?week={TODAY.year + 4}-01-07")  # a week with nothing on the Calendar
        days = re.findall(r'<div class="cal-day[^"]*">(.*?)</div>', empty, re.S)
        self.assertEqual(len(days), 7)
        for day in days:
            self.assertRegex(day, r'^<p class="cal-date"><span class="num">[^<]+</span></p>' + re.escape(self.NONE) + "$")
        self.assertNotIn('<p class="cal-none">Nothing', empty)  # never the whole sentence on screen
        this_week = self.page("/calendar")  # a day with items keeps its rows and no dash
        for day in re.findall(r'<div class="cal-day[^"]*">(.*?)</div>', this_week, re.S):
            self.assertNotEqual('<ul class="rows">' in day, self.NONE in day, day)

    def test_a_date_is_lighter_than_its_item_titles_and_an_empty_day_is_short(self):
        self.assertEqual(rule_props(".cal-date")["font-weight"], "400")
        self.assertEqual(rule_props(".row .what")["font-weight"], "500")  # the title of a Calendar item
        none = rule_props(".cal-none")
        self.assertEqual(none["color"], "var(--faint)")
        self.assertNotIn("padding", none)  # one 24px line, level with the date
        self.assertEqual(rule_props(".cal-day:has(> .cal-none) > .cal-date"), {"padding-top": "0", "color": "var(--muted)"})
        # a phone: the date and the dash stay on one line, the dashes in one column as from 641px (a day with items
        # puts its rows under the date)
        self.assertEqual(media_wins(SMALL, ".cal-day:has(> .cal-none)"),
                         {"grid-template-columns": "112px minmax(0, 1fr)", "gap": "12px"})
        self.assertEqual(rule_props(".sr-only")["clip-path"], "inset(50%)")
        self.assertEqual(rule_props(".dash")["color"], "var(--faint)")

    def test_the_offerings_table_ends_with_a_total_row_as_the_expenses_table(self):
        # the critique's minor note "Offerings has no total row; Expenses has one": both have had one since C2
        # (money._table writes it); a 1440x900 view ends before the total of a long Offerings table. This pins it:
        # the same row in both tables, the sum of the shown whole dong amounts, the same money format, on paper too
        conn = self.db()
        general = lists.find_item(conn, "fund", name="General")["id"]
        events = lists.find_item(conn, "spending_category", name="Events")["id"]
        for amount in (13_500_000, 300_000, 50_000):
            money.add_offering(conn, TODAY.isoformat(), amount, general)
        money.add_expense(conn, TODAY.isoformat(), 1_500_000, events)
        page = self.page("/money")
        for name, label, added in (("offerings", "Total Offerings", [13_500_000, 300_000, 50_000]),
                                   ("expenses", "Total Expenses", [1_500_000])):
            table = section(page, name)
            shown = [int(a.replace(".", "")) for a in re.findall(r'<td class="n"><span class="num">([\d.]+) ₫</span>', table)]
            self.assertTrue(set(added) <= set(shown), name)
            self.assertIn(f'<tr class="total"><th scope="row" colspan="3">{label}</th><td class="n">'
                          f'<span class="num strong">{money.format_vnd(sum(shown))}</span></td>'
                          '<td class="edit no-print"></td></tr></tbody>', table)


class CritFixF1Test(PagesTestBase):
    """CRIT-FIXF1, BUG-1 of TEST-CRIT (row 8): on a vi church copy with the screen in English, at 360px the 2
    People head buttons took 2 lines (20px at the sides), so the list started 52px lower (600px, limit 560).
    Under 641px the title-row pills keep 14px at the sides (never under 12px): both share one line. The gap
    between them stays 8px, every pill stays 44px high, the words are the same. From 641px a pill keeps 20px."""

    def test_under_641px_the_title_row_pills_keep_14px_at_the_sides(self):
        self.assertEqual(media_wins(SMALL, ".title-row .btn"), {"padding": "0 14px"})
        side = int(re.fullmatch(r"0 (\d+)px", media_wins(SMALL, ".title-row .btn")["padding"]).group(1))
        self.assertGreaterEqual(side, 12)  # a pill keeps room around its words
        # the one rule that sets it: no other rule gives the title-row pills a padding
        pads = [sel for sel, body in css_rules()
                if ".title-row .btn" in (s.strip() for s in sel.split(",")) and "padding" in body]
        self.assertEqual(pads, [".title-row .btn"])
        # from 641px a pill keeps 20px at the sides; under 861px it is 44px high; the gap between the actions
        # stays 8px under 861px (no phone rule changes it)
        self.assertEqual(rule_props(".btn")["padding"], "0 20px")
        self.assertNotIn("padding", whole_rule(top_level_rules(), ".title-row .btn"))
        self.assertIn("height: 44px", media_props(PHONE, ".btn"))
        self.assertEqual(media_wins(PHONE, ".title-row .actions")["gap"], "8px")
        self.assertFalse([sel for sel, _body in media_rules(SMALL) if ".title-row .actions" in sel])
        # the 2 People head buttons, with their words as before
        head = title_head(self.page("/people"))
        for words in ("Add a Person", "Add from .xlsx file"):
            self.assertRegex(head, rf'<a class="btn[^"]*" href="[^"]+">{re.escape(words)}</a>')


if __name__ == "__main__":
    unittest.main()
