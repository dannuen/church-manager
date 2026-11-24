"""Round 4 "Pearl": the parts that need page code (docs/redesign-pearl-for-hermes.md).

Part 4 (class DotOnEveryServiceTest): the Services chart has a dot on each Head count, the newest filled; the
dots sit in the outer ``<svg class="chart">`` (in the stretched ``<svg class="plot">`` a circle turns into an
oval), at the x of the date labels and the y of the line, before the last number.
Part 5 (class DashboardPageTest): a Dashboard row of Next 7 days shows the kind of its Calendar item as a
``<span class="tag">``; the place or the visited name after it stays plain grey text. The Services card of the
page has one dot per Head count it shows.
390px (no sideways scroll with the tag) needs a browser: no test here runs one, it is measured on the card.
"""

import re
import unittest

import _support  # noqa: F401 - puts the repo root on sys.path
from churchmgr import care, people, ui
from churchmgr import calendar as cal
from churchmgr.pages import dashboard
from test_pages_people import TODAY, PagesTestBase, section

PLOT = re.compile(r'<svg class="plot"[^>]*>.*?</svg>', re.S)
DOT = re.compile(r'<circle class="(dot(?: last)?)" cx="(\d+\.\d\d)%" cy="(\d+\.\d)" r="(\d\.\d)"/>')
DATE_LABEL = re.compile(r'<text class="tick" x="(\d+\.\d\d)%" y="\d+" text-anchor="middle">(\d\d/\d\d)</text>')
COUNTS = (60, 82, 75, 91, 74, 88, 66, 79)


def head_counts(n):
    return [{"starts_at": f"2026-09-{d:02d} 08:00", "count": COUNTS[d - 1]} for d in range(1, n + 1)]


def row_items(html_text):
    """The inner HTML of each ``<li class="row ..." data-row>`` (rows are never nested)."""
    return re.findall(r'<li class="row[^"]*" data-row>(.*?)</li>', html_text, re.S)


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


if __name__ == "__main__":
    unittest.main()
