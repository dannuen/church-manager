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
        self.assertIn('<footer><a class="card-link" href="/sent">Open Sent documents</a></footer>', listing)
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
    # STYLE-5: the one dark card (Money this month): each text on each of its 3 stops
    *((fg, s) for fg in ("--highlight-ink", "--highlight-muted", "--positive-on-dark", "--negative-on-dark")
      for s in HIGHLIGHT_STOPS),
)
PART_PAIRS = (  # a field border or the focus ring: at least 3:1
    ("--control", "--surface"), ("--control", "--ground"), ("--control", "--raised"),
    ("--accent-text", "--surface"), ("--accent-text", "--ground"),
    # STYLE-4: the ring on the Private note panel and beside a tint; the edge of the current chip
    ("--accent-text", "--raised"), ("--accent-text", "--active"),
    *(("--highlight-focus", s) for s in HIGHLIGHT_STOPS),  # STYLE-5: the ring on the dark card
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
        self.assertEqual(root_tokens()["--radius-control"], "12px")

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
        # hover never moves: the only transition or animation is the reduced-motion "none"
        moves = re.findall(r"\b(?:transition|animation)\s*:\s*([^;]+)", style_css())
        self.assertEqual(set(moves), {"none !important"})

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
        self.assertEqual(colors, {"var(--accent-text)", "var(--on-accent)"})
        # Tab also stops on the calendar button inside a date field: the field keeps the ring then
        for selector in DATE_RINGS:
            self.assertIn("outline: 2px solid var(--accent-text)", declarations(selector), selector)
            self.assertIn("outline-offset: 2px", declarations(selector), selector)


class FormControlsTest(PagesTestBase):
    """STYLE-4: every form control of the pages with a form carries a class that style.css styles, so the
    one CSS pass reaches all of them; a refused form marks its field and its sentence with the classes
    style.css paints red."""

    STYLED = {".input", ".btn", ".link-btn", ".lang-switch button", 'input[type="checkbox"]',
              "details.change > summary", "details.rename > summary"}

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
                self.assertRegex(attrs, r'class="(change|rename)"', path)
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


CARD = '.dashboard > [data-panel="money-month"]'


class CardsAndChartsTest(PagesTestBase):
    """STYLE-5 (spec 4.3, 4.4, 4.8-4.12, D2, D5, D6): white cards with round corners and a soft shadow;
    ONE dark card (Dashboard, Money this month) made from the app color, whose every text reads on it
    (its own tokens; StyleTokensTest checks them for 220 app colors); green and red on money amounts only
    (the Services trend word is not money); the Private note panel unlike the other cards; on paper the
    dark card is ink on white and nothing is green or red."""

    def test_cards_are_white_with_round_corners_and_a_soft_shadow(self):
        tokens = root_tokens()
        self.assertEqual((tokens["--radius-card"], tokens["--radius"]), ("18px", "12px"))
        for selector in (".panel", ".kpi-strip"):  # the Money totals strip is a light card too
            rule = rule_props(selector)
            self.assertEqual((rule["background"], rule["border"], rule["border-radius"], rule["box-shadow"]),
                             ("var(--surface)", "1px solid var(--border)", "var(--radius-card)", "var(--shadow)"),
                             selector)
        self.assertEqual(rule_props(".panel h2")["font-weight"], "700")
        self.assertEqual(rule_props(".card-link")["color"], "var(--text)")
        self.assertEqual(rule_props(".panel .meta")["color"], "var(--muted)")
        # the Private note panel: a tint, a dashed edge, no shadow (it stays .no-print)
        private = rule_props(".panel.private")
        self.assertEqual((private["background"], private["border"], private["box-shadow"]),
                         ("var(--raised)", "1px dashed var(--control)", "none"))
        # a small box (Handover result and refusal, the empty box, search results) has the 12px corners
        for selector in (".result", ".refusal", ".empty", ".results"):
            self.assertEqual(rule_props(selector)["border-radius"], "var(--radius)", selector)

    def test_one_dark_card_made_from_the_app_color(self):
        card = rule_props(CARD)
        self.assertEqual((card["background"], card["box-shadow"], card["color"], card["border-color"]),
                         ("var(--highlight-fill)", "var(--shadow-raised)", "var(--text)", "transparent"))
        # every color token a rule inside the card uses points to a token checked on the 3 stops
        self.assertEqual({p: v for p, v in card.items() if p.startswith("--")}, {
            "--text": "var(--highlight-ink)", "--muted": "var(--highlight-muted)", "--faint": "var(--highlight-muted)",
            "--rule": "var(--highlight-rule)", "--border": "var(--highlight-rule)", "--control": "var(--highlight-rule)",
            "--positive": "var(--positive-on-dark)", "--negative": "var(--negative-on-dark)",
            "--accent-text": "var(--highlight-focus)"})  # the focus ring is --accent-text: white on the card
        self.assertIn("align-self: start", declarations(CARD))  # B11 stays
        # no other dark card: the fill is used by this one rule only
        fill_rules = [sel for sel, body in css_rules() if "var(--highlight-fill)" in body]
        self.assertEqual(fill_rules, [CARD])
        # the fill: 3 stops, each the app color as text (--accent-text) taken darker
        tokens = root_tokens()
        self.assertEqual(re.findall(r"var\((--[\w-]+)\)", tokens["--highlight-fill"]), list(HIGHLIGHT_STOPS))
        for stop in HIGHLIGHT_STOPS:
            self.assertRegex(tokens[stop], r"^color-mix\(in srgb, var\(--accent-text\), #000000 \d+%\)$", stop)
        page = self.page("/")
        self.assertEqual(page.count('data-panel="money-month"'), 1)
        # every class inside it is one these rules reach (a new class with its own color would show here)
        classes = set(" ".join(re.findall(r'class="([^"]*)"', section(page, "money-month"))).split())
        self.assertLessEqual(classes, {"kpis", "kpi", "kpi-label", "kpi-value", "num", "strong", "neg", "meta",
                                       "card-link", "empty", "no-print"})

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
                         ("var(--accent)", "2.5", "round"))
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
        card = rule_props(CARD, "print.css")
        self.assertEqual((card["background"], card["box-shadow"], card["--highlight-ink"], card["--highlight-muted"],
                          card["--positive-on-dark"], card["--negative-on-dark"]),
                         ("none", "none", "#000", "#333", "#000", "#000"))
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
        for selector in (".panel", ".title-row", CARD):
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
        # the menu row: a thin bar in the line color, not the browser's grey one; the current page's pill
        # is in view when the page opens (Money, Settings sat off screen to the right)
        self.assertIn("scrollbar-width: thin", media_props("(max-width: 860px)", ".nav"))
        self.assertIn("scroll-initial-target: nearest", media_props("(max-width: 860px)", '.nav-item[aria-current="page"]'))
        # the Dashboard day column: "Chúa Nhật 15/11" ran into the time at 92px under 1181px
        self.assertIn("width: 112px", declarations(".row .day"))
        # the Search page with no result: its dashed box sat on the wash (1.05:1); it is white now
        self.assertIn("background: var(--surface)", declarations(".canvas > .empty"))
        # the People search with a query (a field and 2 buttons) pushed the page 72px sideways at 390px
        self.assertIn("min-width: 0", declarations(".toolbar"))
        self.assertIn("flex-basis: 100%", media_props("(max-width: 640px)", ".toolbar .input"))
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
        # the fade is a fixed length at the bottom of the wash: 40% of the old fixed heights, so a wash of
        # the old height looks the same
        self.assertEqual((tokens["--wash-h"], tokens["--wash-fade"]), ("340px", "136px"))
        self.assertEqual((tokens["--wash-h-narrow"], tokens["--wash-fade-narrow"]), ("600px", "240px"))
        self.assertTrue(tokens["--wash"].startswith("linear-gradient(180deg, transparent, var(--ground)),"))
        self.assertEqual(rule_props(".title-row")["anchor-name"], "--title-row")
        inside, outside = at_block(style_css(), "@supports (anchor-name: --a)")
        narrow, wide = at_block(inside, "@media (max-width: 860px)")
        # with no anchors (outside @supports): the fixed height as before, the fade drawn at its bottom
        self.assertNotIn("anchor(", outside)
        top_level = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", outside)
        base = block_props(top_level, ".canvas::before")
        self.assertEqual((base["height"], base["background"], base["background-size"], base["background-position"],
                          base["background-repeat"]),
                         ("var(--wash-h)", "var(--wash)", "100% var(--wash-fade), 100% 100%", "0 100%, 0 0", "no-repeat"))
        stacked = media_props("(max-width: 860px)", ".canvas::before")
        self.assertIn("height: var(--wash-h-narrow)", stacked)
        self.assertIn("background-size: 100% var(--wash-fade-narrow), 100% 100%", stacked)
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
        self.assertRegex(page, r'<main class="canvas">.*<header class="title-row">')

    def test_bug1_with_a_flash_the_dashboard_language_switch_is_in_the_flow(self):
        # no flash: as before, the switch sits at the top right of the canvas
        self.assertIn("position: absolute", media_props(WIDE, ".canvas:has(> .dashboard) > .lang-switch"))
        flow = media_props(WIDE, ".canvas:has(> .dashboard):has(> .flash) > .lang-switch")
        self.assertIn("position: static", flow)
        self.assertIn("margin: 0 12px 4px", flow)  # as on every other page (.lang-switch)
        self.assertIn("margin: 0 12px 4px", declarations(".lang-switch"))
        # the real page: the switch, then the flash, both children of the canvas; the grid too
        page = self.page("/?msg=" + urllib.parse.quote("Đã lưu."))
        self.assertRegex(page, r'<main class="canvas"><form class="lang-switch"[^>]*>.*?</form><p class="flash" role="status">')
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
        self.assertIn("border-left: 1px solid var(--rule)", side)
        # the real markup: in an empty month the dashed box is a child of the card, right after the amounts
        html = dashboard._money_month({"offerings": 0, "expenses": 0, "balance": 0}, TODAY, "span-4")
        self.assertIn('</div></div><p class="empty">', html)
        self.assertNotIn('class="empty"', dashboard._money_month({"offerings": 5, "expenses": 2, "balance": 3},
                                                                 TODAY, "span-4"))


DASH_LISTS = ("this-week", "needs-visit", "sent-documents")  # the Dashboard lists that scroll in their card


class StyleFix2Test(PagesTestBase):
    """STYLE-FIX-2, BUG-5 of TEST-STYLE-FIX-1. From 1181px a Dashboard list has a short fixed height (it scrolls
    inside its card), so its grid rows shrank to the row min-height (40px, 34px up to 720px high) and a title on
    2 lines (48px) was drawn over the next row. Each row now takes its content height (grid-auto-rows:
    max-content); the row min-heights and the 2-line clamp stay as they were."""

    def test_bug5_a_dashboard_list_row_is_as_tall_as_its_2_line_title(self):
        for panel in DASH_LISTS:
            rows = media_props(WIDE, f'.dashboard > [data-panel="{panel}"] .rows')
            self.assertIn("grid-auto-rows: max-content", rows, panel)
            self.assertIn("overflow-y: auto", rows, panel)  # the list still scrolls inside its card
        # unchanged: the row min-heights and the clamp of a title to 2 lines
        self.assertIn("min-height: 40px", media_props(WIDE, ".dashboard .row"))
        self.assertIn("min-height: 34px", media_props(WIDE + " and (max-height: 720px)", ".dashboard .row"))
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
    never comes from the text. Row 2 stays as it was."""

    def test_bug6_row_1_always_shows_one_whole_row_in_each_list(self):
        grid = media_wins(WIDE, ".dashboard")
        self.assertEqual(grid["grid-template-rows"], "minmax(min-content, 1fr) auto")
        self.assertNotIn("minmax(150px", style_css())  # no fixed floor is left
        for panel in ROW1:
            rows = f'.dashboard > [data-panel="{panel}"] .rows'
            # one row at its tallest: a title on 2 lines of 24px plus the row padding (8px; 4px up to 720px high)
            self.assertEqual(media_wins(WIDE, rows)["min-height"], "56px", panel)
            self.assertEqual(media_wins(SHORT, rows)["min-height"], "52px", panel)
            self.assertEqual(media_wins(WIDE, rows)["overflow-y"], "auto", panel)  # the rest scrolls in the card
        self.assertEqual(media_wins(WIDE, ".dashboard .row")["min-height"], "40px")  # the row min-heights as before
        self.assertEqual(media_wins(SHORT, ".dashboard .row")["min-height"], "34px")
        self.assertEqual(media_wins(WIDE, ".dashboard .row")["padding"], "4px 0")
        self.assertEqual(media_wins(SHORT, ".dashboard .row")["padding"], "2px 0")
        self.assertIn("font: var(--fs-body)/24px", declarations("body"))  # a title line is 24px high
        # the Sent documents list (row 2) keeps no floor of its own
        self.assertEqual(media_wins(WIDE, '.dashboard > [data-panel="sent-documents"] .rows')["min-height"], "0")
        # the real page: the Needs a visit rows are a <ul class="rows"> inside its card, under the list head
        visit = section(self.page("/"), "needs-visit")
        self.assertRegex(visit, r'<div class="list-head" aria-hidden="true">.*</div><ul class="rows">'
                                r'<li class="row" data-row>')

    def test_bug6_up_to_720px_high_the_space_around_row_1_is_tighter(self):
        title_row = media_wins(SHORT, ".canvas:has(> .dashboard) > .title-row")
        self.assertEqual((title_row["padding-top"], title_row["padding-bottom"], title_row["margin-bottom"]),
                         ("0", "4px", "8px"))
        self.assertEqual(media_wins(SHORT, ".dashboard")["row-gap"], "10px")
        for panel in ROW1:
            card = f'.dashboard > [data-panel="{panel}"]'
            props = media_wins(SHORT, card)
            self.assertEqual((props["padding-top"], props["padding-bottom"]), ("10px", "8px"), panel)
            self.assertEqual(media_wins(SHORT, card + " > header")["margin-bottom"], "2px", panel)
            self.assertEqual(media_wins(SHORT, card + " > footer")["padding-top"], "4px", panel)
        # the Needs a visit hint takes the whole header width: one line; the count stays on the title line
        head = '.dashboard > [data-panel="needs-visit"] > header'
        self.assertEqual((media_wins(SHORT, head)["flex-wrap"], media_wins(SHORT, head)["row-gap"]), ("wrap", "0"))
        self.assertEqual(media_wins(SHORT, head + " > div")["display"], "contents")
        meta = media_wins(SHORT, head + " > div > .meta")
        self.assertEqual((meta["order"], meta["flex-basis"]), ("1", "100%"))
        visit = section(self.page("/"), "needs-visit")
        self.assertRegex(visit, r'^<header><div><h2 id="p-needs-visit">[^<]+</h2><span class="meta">[^<]+</span></div>'
                                r'<span class="count num">[^<]+</span></header>')
        # never from the text: no size, line or hiding rule in the short block
        body = " ".join(body for sel, body in media_rules(SHORT))
        for word in ("font-size", "line-height", "display: none", "visibility", "-webkit-line-clamp"):
            self.assertNotIn(word, body)
        # row 2 as it was: its height, its padding, the Money this month card
        self.assertEqual(root_tokens()["--dash-row2"], "294px")
        for panel in ("services", "money-month", "sent-documents"):
            card = f'.dashboard > [data-panel="{panel}"]'
            self.assertEqual(media_wins(WIDE, card)["min-height"], "var(--dash-row2)", panel)
            self.assertEqual((media_wins(SHORT, card)["padding-top"], media_wins(SHORT, card)["padding-bottom"]),
                             ("10px", "8px"), panel)
        self.assertEqual(media_wins(WIDE, CARD)["max-height"], "var(--dash-row2)")
        # screen only: on paper every list prints whole
        for query in (WIDE, SHORT):
            self.assertTrue(query.startswith("screen and "))


if __name__ == "__main__":
    unittest.main()
