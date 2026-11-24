"""Round 4 "Pearl": the parts that need page code (docs/redesign-pearl-for-hermes.md).

Part 4 (class DotOnEveryServiceTest): the Services chart has a dot on each Head count, the newest filled; the
dots sit in the outer ``<svg class="chart">`` (in the stretched ``<svg class="plot">`` a circle turns into an
oval), at the x of the date labels and the y of the line, before the last number.
Part 5 (class DashboardPageTest): a Dashboard row of Next 7 days shows the kind of its Calendar item as a
``<span class="tag">``; the place or the visited name after it stays plain grey text. The Services card of the
page has one dot per Head count it shows.
Part 2 (classes FiguresAndNextItemTest, DashboardPageTest, VietnameseDashboardTest): under the title row, one
``<section class="figures">`` with 3 figures: the Calendar items of the Next 7 days, the People who need a
visit, the Balance of this month. A value that failed to load is a dash. No 01 02 03 numbers. The count of
Calendar items is said once (CRIT-3): the line under the h1 keeps the weekday and the date only.
Part 3 (same classes): ``<aside class="next-item">``, the first row of Next 7 days (day, time and kind, then its
title as a link to it). Nothing when the 7 days have no Calendar item or did not load. The title shows 2 lines
at most (``clamp2``, PP-F1): from 1181px the card has a fixed top over the figures strip. The children of
``main.canvas`` are: the language switch, the title row, the next item, the figures, the grid.
390px and 1440px (no sideways scroll) need a browser: no test here runs one, it is measured on the card.
"""

import contextlib
import datetime as dt
import html
import io
import pathlib
import re
import tempfile
import unittest
from html.parser import HTMLParser
from unittest import mock

import _support  # noqa: F401 - puts the repo root on sys.path
from churchmgr import care, fake, i18n, money, people, ui
from churchmgr import calendar as cal
from churchmgr.i18n import english_left
from churchmgr.pages import dashboard
from test_pages_people import TODAY, VOID, PagesTestBase, section

PLOT = re.compile(r'<svg class="plot"[^>]*>.*?</svg>', re.S)
DOT = re.compile(r'<circle class="(dot(?: last)?)" cx="(\d+\.\d\d)%" cy="(\d+\.\d)" r="(\d\.\d)"/>')
DATE_LABEL = re.compile(r'<text class="tick" x="(\d+\.\d\d)%" y="\d+" text-anchor="middle">(\d\d/\d\d)</text>')
COUNTS = (60, 82, 75, 91, 74, 88, 66, 79)
FIGURES = re.compile(r'<section class="figures" aria-label="([^"]*)">(.*?)</section>', re.S)
FIGURE = re.compile(r'<div class="figure"><span class="figure-label">(.*?)</span>'
                    r'<span class="figure-value num">(.*?)</span></div>')
# PP-F1: the title is in clamp2 (at most 2 lines on screen, then "…"), its whole text in the title: the same
# escaped text (\4)
NEXT_ITEM = re.compile(r'<aside class="next-item" aria-label="([^"]*)"><span class="when">([^<]*)</span>'
                       r'<a class="what" href="(/calendar/\d+)" lang="vi"><span class="clamp-2" title="([^"]*)">\4'
                       r'</span></a></aside>')
DAY = dt.date(2026, 11, 24)  # a Tuesday
# PP-F1: a title of 120 characters, with the 3 signs HTML must escape
LONG_TITLE = ('Lễ Tạ Ơn & Mừng Chúa Giáng Sinh của Hội Thánh <Ban Thanh niên> cùng các Chi phái, '
              'Hội đồng bồi linh "Ngọc trai" về thăm.')


def head_counts(n):
    return [{"starts_at": f"2026-09-{d:02d} 08:00", "count": COUNTS[d - 1]} for d in range(1, n + 1)]


def row_items(html_text):
    """The inner HTML of each ``<li class="row ..." data-row>`` (rows are never nested)."""
    return re.findall(r'<li class="row[^"]*" data-row>(.*?)</li>', html_text, re.S)


def figures(html_text):
    """``(aria-label, [(label, value), ...])`` of the one figures strip, or None."""
    found = FIGURES.findall(html_text)
    assert len(found) <= 1, "more than one figures strip"
    return (found[0][0], FIGURE.findall(found[0][1])) if found else None


def title_head(page):
    return re.search(r'<header class="title-row">.*?</header>', page, re.S).group(0)


def month_name(lang):
    return i18n.t("core.month_year", lang, month=i18n.t(f"core.month_{TODAY.month}", lang), year=TODAY.year)


class CanvasChildren(HTMLParser):
    """The direct children of ``<main class="canvas">``: ``(tag, class)`` in page order."""

    def __init__(self):
        super().__init__()
        self.depth, self.main, self.children = 0, None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.main is not None and self.depth == self.main + 1:
            self.children.append((tag, a.get("class", "")))
        if tag == "main" and "canvas" in (a.get("class") or "").split():
            self.main = self.depth
        if tag not in VOID:
            self.depth += 1

    def handle_startendtag(self, tag, attrs):
        if self.main is not None and self.depth == self.main + 1:
            self.children.append((tag, dict(attrs).get("class", "")))

    def handle_endtag(self, tag):
        if tag not in VOID:
            self.depth -= 1
        if tag == "main" and self.main == self.depth:
            self.main = None


def canvas_children(page):
    p = CanvasChildren()
    p.feed(page)
    return p.children


def item(item_id, day, time, kind="Meeting", title="Họp Ban Chấp Sự", place="Phòng họp", visit_name=None):
    return {"id": item_id, "starts_at": f"{day.isoformat()} {time}", "kind": kind, "title": title,
            "place": place, "visit_name": visit_name}


class DotOnEveryServiceTest(unittest.TestCase):
    def test_one_dot_per_head_count_the_newest_is_the_last(self):
        for n in range(2, dashboard.HEAD_COUNTS + 1):
            with self.subTest(n=n):
                svg = dashboard.services_svg(head_counts(n))
                dots = DOT.findall(svg)
                self.assertEqual(len(dots), n)
                self.assertEqual(svg.count("<circle"), n)  # every circle is a dot of this shape
                self.assertEqual([cls for cls, *_ in dots], ["dot"] * (n - 1) + ["dot last"])
                self.assertEqual([r for *_, r in dots], ["3.5"] * (n - 1) + ["4.5"])
                self.assertEqual(svg.count('class="dot last"'), 1)

    def test_a_dot_is_at_the_date_label_x_and_on_the_line(self):
        for n in range(2, dashboard.HEAD_COUNTS + 1):
            with self.subTest(n=n):
                rows = head_counts(n)
                svg = dashboard.services_svg(rows)
                dots = DOT.findall(svg)
                label_x = {label: x for x, label in DATE_LABEL.findall(svg)}
                self.assertTrue(label_x)
                if n <= 5:  # every date is labelled
                    self.assertEqual(len(label_x), n)
                for (_cls, cx, _cy, _r), row in zip(dots, rows):
                    label = ui.fmt_date(row["starts_at"])[:5]
                    if label in label_x:
                        self.assertEqual(cx, label_x[label], label)
                points = re.search(r'<polyline class="line" points="([^"]+)"/>', svg).group(1).split()
                self.assertEqual([f"{cx},{cy}" for _cls, cx, cy, _r in dots], points)  # x and y of the line

    def test_the_dots_are_in_the_outer_chart_after_the_plot_before_the_last_number(self):
        svg = dashboard.services_svg(head_counts(8))
        self.assertTrue(svg.startswith('<svg class="chart" '))
        plot = PLOT.search(svg)
        assert plot is not None
        self.assertNotIn("<circle", plot.group(0))  # not in the stretched plot: no ovals
        end = svg.index('<text class="end"')
        self.assertEqual(svg.index("<circle"), plot.end())  # right after the plot
        self.assertLess(svg.rindex("<circle"), end)  # the number stays on top
        self.assertEqual(svg[plot.end():end], "".join(m.group(0) for m in DOT.finditer(svg)))
        self.assertEqual(svg.count("<svg"), 2)  # still one chart and one plot
        self.assertEqual(svg.count(f'height="{dashboard.CHART_HEIGHT}"'), 2)
        self.assertEqual(dashboard.CHART_HEIGHT, 154)


class FiguresAndNextItemTest(unittest.TestCase):
    """Parts 2 and 3 from given rows, in each language (no server)."""

    WEEK = [item(12, DAY + dt.timedelta(days=1), "19:00", title="Họp Ban Chấp Sự <b>"),
            item(13, DAY + dt.timedelta(days=2), "08:00", kind="Service", title="Giờ thờ phượng sáng")]
    NEEDS = [{"person_id": n} for n in range(37)]
    TOTALS = {"offerings": 20_000_000, "expenses": 3_860_000, "balance": 16_140_000}

    def use(self, lang):
        self.addCleanup(i18n.set_lang_getter, i18n._lang_getter)
        i18n.set_lang_getter(lambda: lang)

    def strip(self, week=WEEK, needs=NEEDS, totals=TOTALS):
        return dashboard._figures(week, needs, totals, DAY)

    def test_three_figures_in_english(self):
        self.use("en")
        self.assertEqual(figures(self.strip()), ("At a glance", [
            ("Next 7 days", "2 Calendar items"), ("Needs a visit", "37 People"),
            ("Balance, November 2026", "16.140.000 ₫")]))
        self.assertEqual(figures(self.strip(self.WEEK[:1], self.NEEDS[:1]))[1][:2],
                         [("Next 7 days", "1 Calendar item"), ("Needs a visit", "1 Person")])
        self.assertEqual(figures(self.strip([], [], {"offerings": 0, "expenses": 500, "balance": -500}))[1],
                         [("Next 7 days", "0 Calendar items"), ("Needs a visit", "0 People"),
                          ("Balance, November 2026", "-500 ₫")])

    def test_three_figures_in_vietnamese(self):
        self.use("vi")
        self.assertEqual(figures(self.strip()), ("Tóm tắt", [
            ("7 ngày tới", "2 Lịch"), ("Cần thăm viếng", "37 người"), ("Số dư, Tháng 11/2026", "16.140.000 ₫")]))
        self.assertEqual(figures(self.strip(self.WEEK[:1], self.NEEDS[:1]))[1][:2],
                         [("7 ngày tới", "1 Lịch"), ("Cần thăm viếng", "1 người")])

    def test_a_value_that_failed_to_load_is_a_dash(self):
        self.use("en")
        failed = dashboard._FAILED
        for place, args in ((0, (failed, self.NEEDS, self.TOTALS)), (1, (self.WEEK, failed, self.TOTALS)),
                            (2, (self.WEEK, self.NEEDS, failed))):
            with self.subTest(place=place):
                labels, values = zip(*figures(dashboard._figures(*args, DAY))[1])
                self.assertEqual(labels, ("Next 7 days", "Needs a visit", "Balance, November 2026"))  # labels stay
                self.assertEqual([v == ui.DASH for v in values], [i == place for i in range(3)])
        _label, rows = figures(dashboard._figures(failed, failed, failed, DAY))
        self.assertEqual([v for _l, v in rows], [ui.DASH] * 3)

    def test_no_numbers_before_the_figures(self):
        self.use("en")
        strip = FIGURES.search(self.strip()).group(2)
        self.assertEqual(strip.count('<div class="figure">'), 3)
        text = re.sub(r"<[^>]+>", "|", strip)
        for n in ("01", "02", "03"):
            self.assertNotIn(f"|{n}", text)
            self.assertNotIn(f"{n}|", text)
        self.assertNotIn("style=", strip)

    def test_the_next_item_is_the_first_row(self):
        self.use("en")
        self.assertEqual(NEXT_ITEM.fullmatch(dashboard._next_item(self.WEEK, DAY)).groups(),
                         ("Next Calendar item", "Tomorrow · 19:00 · Meeting", "/calendar/12",
                          "Họp Ban Chấp Sự &lt;b&gt;"))
        today = [item(7, DAY, "08:00", kind="Visit", title="Thăm cụ Lan", visit_name="Lê Thị Lan")]
        self.assertEqual(NEXT_ITEM.fullmatch(dashboard._next_item(today + self.WEEK, DAY)).group(2),
                         "Today · 08:00 · Visit")
        later = [item(9, DAY + dt.timedelta(days=3), "18:30", kind="Event", title="Sinh hoạt")]
        self.assertEqual(NEXT_ITEM.fullmatch(dashboard._next_item(later, DAY)).group(2), "Fri 27/11 · 18:30 · Event")
        self.use("vi")
        self.assertEqual(NEXT_ITEM.fullmatch(dashboard._next_item(self.WEEK, DAY)).groups()[:2],
                         ("Lịch sắp tới", "Ngày mai · 19:00 · Buổi họp"))

    def test_no_next_item_with_no_row_or_a_failed_load(self):
        self.use("en")
        self.assertEqual(dashboard._next_item([], DAY), "")
        self.assertEqual(dashboard._next_item(dashboard._FAILED, DAY), "")

    def test_a_long_title_shows_2_lines_at_most_its_whole_text_in_the_title(self):
        """PP-F1 (D1): from 1181px the card has a fixed top over the figures strip, so a 3rd line of title ran
        over the Balance label. The title is in clamp2: at most 2 lines on screen, then "…"; its whole text is
        in the title (and on paper: style.css prints a .clamp-2 whole). Escaped once."""
        self.use("vi")
        self.assertEqual(len(LONG_TITLE), 120)
        card = dashboard._next_item([item(21, DAY, "23:30", kind="Event", title=LONG_TITLE)], DAY)
        esc = ui.h(LONG_TITLE)
        self.assertIn(f'<a class="what" href="/calendar/21" lang="vi"><span class="clamp-2" title="{esc}">{esc}'
                      '</span></a></aside>', card)
        self.assertEqual(card.count('<span class="clamp-2"'), 1)
        for twice in ("&amp;amp;", "&amp;lt;", "&amp;gt;", "&amp;quot;"):  # escaped once, never twice
            self.assertNotIn(twice, card)
        self.assertEqual(html.unescape(NEXT_ITEM.fullmatch(card).group(4)), LONG_TITLE)
        self.assertNotIn("style=", card)


class DashboardPageTest(PagesTestBase):
    def test_the_services_card_has_a_dot_per_head_count_it_shows(self):
        rows = cal.recent_head_counts(self.db(), dashboard.HEAD_COUNTS)
        self.assertGreater(len(rows), 1)  # the fake church has Head counts: the chart is drawn
        services = section(self.page("/"), "services")
        self.assertEqual(len(DOT.findall(services)), len(rows))
        self.assertEqual(services.count('class="dot last"'), 1)

    def test_the_kind_is_a_tag_and_the_place_or_name_stays_plain(self):
        conn = self.db()
        day = TODAY.isoformat()
        place = "Phòng họp nhỏ sau nhà thờ"
        meeting = cal.add_calendar_item(conn, "Meeting", "PP-1 Họp Ban Chấp Sự", f"{day} 00:05", place=place)[0]
        person = people.list_persons(conn)[0]
        name = person["full_name"]
        visit = care.plan_visit(conn, f"{day} 00:10", person_id=person["id"], title="PP-1 Thăm gia đình mới")
        page = self.page("/")
        rows = row_items(section(page, "this-week"))
        meeting_row = next(r for r in rows if f'href="/calendar/{meeting}"' in r)
        visit_row = next(r for r in rows if f'href="/calendar/{visit}"' in r)
        self.assertIn(f'<span class="side" title="Meeting · {place}"><span class="tag">Meeting</span> · '
                      f'<span lang="vi">{place}</span></span>', meeting_row)
        self.assertIn(f'<span class="side" title="Visit · {ui.h(name)}"><span class="tag">Visit</span> · '
                      f'<span lang="vi">{ui.h(name)}</span></span>', visit_row)
        for row in rows:  # every row: one tag, the kind, first in the grey side text
            tags = re.findall(r'<span class="tag">([^<]*)</span>', row)
            self.assertEqual(len(tags), 1, row)
            self.assertIn(tags[0], ("Service", "Meeting", "Visit", "Event"))
            self.assertRegex(row, r'<span class="side" title="[^"]*"><span class="tag">')
        self.assertNotIn('<span class="tag"><span lang="vi">', page)  # the place is never in the tag

    def loaded(self):
        conn = self.db()
        week = cal.items_between(conn, TODAY, TODAY + dt.timedelta(days=6))
        return week, care.needs_visit(conn, TODAY), money.month_totals(conn, TODAY.year, TODAY.month)

    def test_the_figures_strip_has_the_three_values(self):
        week, needs, totals = self.loaded()
        page = self.page("/")
        self.assertTrue(week and needs)  # the fake church has both
        n, k = len(week), len(needs)
        self.assertEqual(figures(page), ("At a glance", [
            ("Next 7 days", f"{n} Calendar item{'' if n == 1 else 's'}"),
            ("Needs a visit", f"{k} {'Person' if k == 1 else 'People'}"),
            (f"Balance, {month_name('en')}", money.format_vnd(totals["balance"]))]))

    def test_the_line_under_the_h1_has_the_date_only(self):
        head = title_head(self.page("/"))
        weekday = i18n.t(f"core.weekday_{TODAY.weekday()}", "en")
        self.assertIn(f'<p class="sub">{weekday} {TODAY:%d/%m/%Y}</p>', head)  # CRIT-3: the count is in the strip
        self.assertNotIn("Calendar item", head)

    def test_the_next_item_is_the_first_row_of_next_7_days(self):
        week, _needs, _totals = self.loaded()
        self.assertTrue(week)
        page = self.page("/")
        first = row_items(section(page, "this-week"))[0]
        day = re.search(r'<span class="day">([^<]*)</span>', first).group(1)
        time = re.search(r'<span class="time num">([^<]*)</span>', first).group(1)
        kind = re.search(r'<span class="tag">([^<]*)</span>', first).group(1)
        href, title = re.search(r'<a href="(/calendar/\d+)">([^<]*)</a>', first).groups()
        self.assertEqual(href, f"/calendar/{week[0]['id']}")
        self.assertEqual(NEXT_ITEM.findall(page), [("Next Calendar item", f"{day} · {time} · {kind}", href, title)])

    def test_the_canvas_order_title_row_next_item_figures_grid(self):
        page = self.page("/")
        self.assertEqual(canvas_children(page), [
            ("form", "lang-switch"), ("header", "title-row"), ("aside", "next-item"), ("section", "figures"),
            ("div", "grid dashboard")])
        self.assertRegex(page, r'</header><aside class="next-item"[^>]*>.*?</aside><section class="figures"'
                               r'[^>]*>.*?</section><div class="grid dashboard">')

    def test_no_next_item_when_the_7_days_are_empty(self):
        with mock.patch.object(dashboard.cal, "items_between", return_value=[]):
            page = self.page("/")
        self.assertNotIn("next-item", page)
        self.assertEqual(figures(page)[1][0], ("Next 7 days", "0 Calendar items"))
        self.assertIn("Nothing in the next 7 days.", section(page, "this-week"))
        self.assertEqual([tag for tag, _cls in canvas_children(page)], ["form", "header", "section", "div"])

    def test_a_part_that_failed_to_load_is_a_dash_in_the_strip(self):
        def broken(*args):
            raise RuntimeError("disk gone")
        for place, (module, name) in enumerate(((dashboard.cal, "items_between"), (dashboard.care, "needs_visit"),
                                                (dashboard.money, "month_totals"))):
            with self.subTest(name=name), mock.patch.object(module, name, broken), \
                    contextlib.redirect_stderr(io.StringIO()):
                page = self.page("/")
                values = [v for _label, v in figures(page)[1]]
                self.assertEqual([v == ui.DASH for v in values], [i == place for i in range(3)])
                if place == 0:  # no next item, and the line under the h1 still has the date
                    self.assertNotIn("next-item", page)
                    self.assertRegex(title_head(page), r'<p class="sub">\w+ \d\d/\d\d/\d{4}</p>')
                    self.assertIn("Could not load Next 7 days.", page)


class VietnameseDashboardTest(PagesTestBase):
    """The same strip and card on a Tiếng Việt church copy."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        cls.root = pathlib.Path(cls.tmp.name)
        assert "onedrive" not in str(cls.root.resolve()).lower()
        cls.copy = cls.root / "fake"
        fake.build_fake_church(cls.copy, people=20, lang="vi")
        cls.start(cls.copy, cls.root, remember=False)

    def test_the_strip_and_the_next_item_in_vietnamese(self):
        conn = self.db()
        week = cal.items_between(conn, TODAY, TODAY + dt.timedelta(days=6))
        needs = care.needs_visit(conn, TODAY)
        totals = money.month_totals(conn, TODAY.year, TODAY.month)
        page = self.page("/")
        self.assertIn('<html lang="vi">', page)
        self.assertEqual(figures(page), ("Tóm tắt", [
            ("7 ngày tới", f"{len(week)} Lịch"), ("Cần thăm viếng", f"{len(needs)} người"),
            (f"Số dư, {month_name('vi')}", money.format_vnd(totals["balance"]))]))
        self.assertTrue(week)
        label, when, href, _title = NEXT_ITEM.search(page).groups()
        self.assertEqual((label, href), ("Lịch sắp tới", f"/calendar/{week[0]['id']}"))
        kind = i18n.t(f"core.kind_{week[0]['kind'].lower()}", "vi")
        self.assertTrue(when.endswith(f" · {ui.fmt_time(week[0]['starts_at'])} · {kind}"), when)
        weekday = i18n.t(f"core.weekday_{TODAY.weekday()}", "vi")
        self.assertIn(f'<p class="sub">{weekday} {TODAY:%d/%m/%Y}</p>', title_head(page))
        strip = FIGURES.search(page).group(0) + NEXT_ITEM.search(page).group(0)
        self.assertEqual(english_left(strip), [])


if __name__ == "__main__":
    unittest.main()
