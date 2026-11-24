"""Dashboard ``/``: what needs the pastor this week? Six panels on one page.

Round 4: between the title row and the panels, the next Calendar item (``<aside class="next-item">``, the
first row of Next 7 days) and a strip of 3 figures (``<section class="figures">``); both are styled in
``web/style.css``. Neither is a panel: they have no ``data-panel`` and no ``data-row``.

Each panel is ``<section data-panel="NAME">``; each data line in it has ``data-row``.
A panel that cannot load keeps its frame and says so (the error goes to the console).
Words on screen come from the text table (section ``dashboard``), also the words of the live search:
the form carries them in ``data-text-*`` attributes and ``web/app.js`` reads them there.
"""

import datetime as _dt
import traceback

from .. import calendar as cal
from .. import care, money, sent, ui
from ..i18n import t, tn
from ..server import Response
from ..ui import clamp2, h, vi

# DASH RULE (CRIT-4): a Dashboard list never scrolls inside its card. It shows at most this many rows; when
# there are more, its foot link names the full count ("View all N ..."). The numbers are below the 5/5/2 of
# the rule so the page fits 1280x800 with every title on 2 lines (rule 4). Needs a visit has one row less than
# the Next 7 days: its head is 41px taller (the hint line and the list head), so the 2 cards of row 1 end level.
WEEK_ROWS = 4  # Calendar items of the Next 7 days
VISIT_ROWS = 3  # Persons in Needs a visit
HEAD_COUNTS = 8
SENT_ROWS = 2  # B17: 2 recent rows keep Sent documents level with Services and Money this month
CHART_HEIGHT = 154  # px, the Services chart at every width
# Row 2 of the 12 columns: Services, Money this month, Sent documents (4 + 4 + 4)
ROW2_SPANS = ("span-4", "span-4", "span-4")
_FAILED = object()
TREND_WORDS = {"Up": "dashboard.trend_up", "Down": "dashboard.trend_down", "Same": "dashboard.trend_same"}


# ---------------------------------------------------------------- small logic (tested)

def trend(counts):
    """The last Head count against the average of the earlier ones.

    Returns ``(word, average)``: word ``"Up"``, ``"Down"`` or ``"Same"`` (a code: the page shows
    ``TREND_WORDS``); the average is rounded half up. Fewer than 2 counts -> ``(None, None)``.
    Whole numbers only.
    """
    if len(counts) < 2:
        return None, None
    *earlier, last = counts
    total, k = sum(earlier), len(earlier)
    word = "Up" if last * k > total else "Down" if last * k < total else "Same"
    return word, (2 * total + k) // (2 * k)


def fit_scale(low_value, high_value):
    """Y axis that fits the Head counts (CRIT-9): ``(low, high)``, the lowest count rounded down to 10 and
    the highest rounded up to 10. They stay at least 20 apart: 10 apart, the top grows by 10; 0 apart, the
    top and the bottom grow by 10 each (the bottom never under 0, then the top takes it). Integers only."""
    low, high = low_value // 10 * 10, -(-high_value // 10) * 10
    short = max(0, 20 - (high - low))
    down = min(low, short // 20 * 10)
    return low - down, high + short - down


def services_svg(rows):
    """A small one-series line of Head counts (oldest left), drawn as inline SVG.

    The chart has one height (``CHART_HEIGHT``) at every width and fills the card width: x places are
    percentages, and the line sits in an inner SVG stretched across the plot (its stroke does not
    scale). So the 12px text keeps its size and the Services card keeps its height when the window
    changes. The y ticks and the last value sit in the side padding of ``.chart`` (style.css).
    The y scale fits the counts (``fit_scale``), not 0 to a round top, so a change from 91 to 74 shows;
    its two lines, the low and the high one, carry their numbers, so the scale is honest. The low line is
    the darker base line only when it is 0.
    Each Head count has a dot (``.chart .dot``), the newest a bigger filled one (``.dot.last``).
    With more than 5 Services every second date is labelled, counted back from the last one.
    """
    counts = [r["count"] for r in rows]
    n = len(counts)
    low, high = fit_scale(min(counts), max(counts))
    height, pad_top, bottom = CHART_HEIGHT, 10, 28
    plot_h = height - pad_top - bottom

    def x(i):
        return 100 * i / (n - 1) if n > 1 else 50

    def y(c):
        return pad_top + plot_h - plot_h * (c - low) / (high - low)

    parts = []
    for v in (low, high):
        yy = y(v)
        cls = "gridline base" if v == 0 else "gridline"
        parts.append(f'<line class="{cls}" x1="0" x2="100%" y1="{yy:.1f}" y2="{yy:.1f}"/>')
        parts.append(f'<text class="tick" x="-8" y="{yy + 4:.1f}" text-anchor="end">{v}</text>')
    label_every = 2 if n > 5 else 1
    for i, r in enumerate(rows):
        if (n - 1 - i) % label_every == 0:
            parts.append(f'<text class="tick" x="{x(i):.2f}%" y="{height - 8}" text-anchor="middle">'
                         f'{h(ui.fmt_date(r["starts_at"])[:5])}</text>')
    points = " ".join(f"{x(i):.2f},{y(c):.1f}" for i, c in enumerate(counts))
    parts.append(f'<svg class="plot" width="100%" height="{height}" viewBox="0 0 100 {height}" '
                 f'preserveAspectRatio="none"><polyline class="line" points="{points}"/></svg>')
    # round 4: a dot on each Head count, the newest filled; in the outer chart (in the stretched plot a
    # circle turns into an oval), before the last number so the number stays on top
    for i, c in enumerate(counts):
        newest = i == n - 1
        parts.append(f'<circle class="dot{" last" if newest else ""}" cx="{x(i):.2f}%" cy="{y(c):.1f}" '
                     f'r="{"4.5" if newest else "3.5"}"/>')
    parts.append(f'<text class="end" x="100%" dx="8" y="{y(counts[-1]) + 4:.1f}">{counts[-1]}</text>')
    label = "; ".join(f"{ui.fmt_date(r['starts_at'])} {r['count']}" for r in rows)
    return (f'<svg class="chart" width="100%" height="{height}" role="img" '
            f'aria-label="{h(t("dashboard.chart_label", n=n, counts=label))}">{"".join(parts)}</svg>')


# ---------------------------------------------------------------- panels

def _load(fn, *args):
    try:
        return fn(*args)
    except Exception:
        traceback.print_exc()
        return _FAILED


def _panel(name, title, body, meta="", head_link="", foot="", span=""):
    meta_html = f'<span class="meta">{meta}</span>' if meta else ""
    foot_html = f"<footer>{foot}</footer>" if foot else ""
    return (f'<section class="panel {span}" data-panel="{name}" aria-labelledby="p-{name}">'
            f'<header><div><h2 id="p-{name}">{h(title)}</h2>{meta_html}</div>{head_link}</header>'
            f"{body}{foot_html}</section>")


def _failed(name, title, span):
    return _panel(name, title, f'<p class="empty">{h(t("dashboard.failed", title=title))} '
                               f'<a class="no-print" href="/">{h(t("dashboard.retry"))}</a></p>', span=span)


def _empty(sentence):
    return f'<p class="empty">{h(sentence)}</p>'


def _link(text, href):
    return f'<a class="card-link" href="{h(href)}">{h(text)}</a>'


def _day_label(day, today):
    if day == today:
        return t("dashboard.today")
    if day == today + _dt.timedelta(days=1):
        return t("dashboard.tomorrow")
    return f"{ui.fmt_weekday(day)} {day.strftime('%d/%m')}"


def _next_item(items, today):
    """Round 4: the first row of Next 7 days (``items[0]``) as a small dark card: its day, time and kind on
    one line, its title as a link to it. Nothing when the 7 days did not load or have no Calendar item.
    The title shows 2 lines at most (``clamp2``, its whole text in the title and on paper): from 1181px the
    card has a fixed top, so a 3rd line ran over the figures strip under it."""
    if items is _FAILED or not items:
        return ""
    it = items[0]
    day = _dt.date.fromisoformat(it["starts_at"][:10])
    when = " · ".join((_day_label(day, today), ui.fmt_time(it["starts_at"]), ui.calendar_kind(it["kind"])))
    return (f'<aside class="next-item" aria-label="{h(t("dashboard.next_item"))}">'
            f'<span class="when">{h(when)}</span>'
            f'<a class="what" href="/calendar/{it["id"]}" lang="vi">{clamp2(h(it["title"]), it["title"])}</a>'
            '</aside>')


def _figures(week, needs, totals, today):
    """Round 4: the strip of 3 figures under the title row: the Calendar items of the Next 7 days, the People
    who need a visit and the Balance of this month, each with its word (no 01 02 03). A value that did not
    load is a dash; its label stays."""
    def figure(label, value_html):
        return (f'<div class="figure"><span class="figure-label">{h(label)}</span>'
                f'<span class="figure-value num">{value_html}</span></div>')

    items = ui.DASH if week is _FAILED else h(tn("dashboard.figure_items", len(week)))
    persons = ui.DASH if needs is _FAILED else h(tn("dashboard.persons", len(needs)))
    balance = ui.DASH if totals is _FAILED else h(ui.fmt_money(totals["balance"]))
    month = ui.fmt_month(today.year, today.month)
    return (f'<section class="figures" aria-label="{h(t("dashboard.figures"))}">'
            + figure(t("dashboard.this_week"), items) + figure(t("dashboard.needs_visit"), persons)
            + figure(f'{t("dashboard.balance")}, {month}', balance) + "</section>")


def _this_week(items, today, span):
    name, title = "this-week", t("dashboard.this_week")
    if items is _FAILED:
        return _failed(name, title, span)
    last = today + _dt.timedelta(days=6)
    meta = f"{today.strftime('%d/%m')} – {last.strftime('%d/%m/%Y')}"
    rows = []
    for it in items[:WEEK_ROWS]:
        day = _dt.date.fromisoformat(it["starts_at"][:10])
        kind = ui.calendar_kind(it["kind"])
        # round 4: the kind is a small tag; the place or the visited name after it stays plain grey text
        sub, words = [f'<span class="tag">{h(kind)}</span>'], [kind]
        if it["kind"] == "Visit" and it["visit_name"] and it["visit_name"] not in it["title"]:
            sub.append(vi(it["visit_name"]))
            words.append(it["visit_name"])
        elif it["place"]:
            sub.append(vi(it["place"]))
            words.append(it["place"])
        # B26: the title wraps to 2 lines (full text in its title) and gets the width before the place
        link = f'<a href="/calendar/{it["id"]}">{h(it["title"])}</a>'
        rows.append(
            '<li class="row" data-row>'
            f'<span class="day">{h(_day_label(day, today))}</span>'
            f'<span class="time num">{h(ui.fmt_time(it["starts_at"]))}</span>'
            f'<span class="what wrap">{clamp2(link, it["title"], lang="vi")}</span>'
            f'{ui.row_side(sub, words)}</li>'
        )
    body = f'<ul class="rows">{"".join(rows)}</ul>' if rows else _empty(t("dashboard.nothing_week"))
    more = (t("dashboard.view_all_calendar", n=len(items)) if len(items) > WEEK_ROWS
            else t("dashboard.open_calendar"))
    # the same 7 days on the Calendar (its 7-day view, not its Monday-to-Sunday week), so the count matches
    href = ui.url("/calendar", **{"from": today.isoformat()})
    return _panel(name, title, body, meta=meta, foot=_link(more, href), span=span)


def _needs_visit(people, months, span):
    name, title = "needs-visit", t("dashboard.needs_visit")
    if people is _FAILED or months is _FAILED:
        return _failed(name, title, span)
    meta = t("dashboard.no_visit_in", months=tn("core.months", months))
    count = f'<span class="count num">{h(tn("dashboard.persons", len(people)))}</span>'
    last_visit = t("dashboard.last_visit")
    rows = []
    for p in people[:VISIT_ROWS]:
        last = ui.fmt_date(p["last_visit"]) if p["last_visit"] else t("dashboard.never")
        link = f'<a href="/people/{p["person_id"]}">{h(p["full_name"])}</a>'
        status = h(p["status_name"]) if p["status_name"] else ui.DASH
        rows.append(
            '<li class="row" data-row>'
            f'<span class="what wrap">{clamp2(link, p["full_name"], lang="vi")}</span>'
            f'{ui.row_side([status], [p["status_name"]])}'
            f'<span class="figure num{" faint" if not p["last_visit"] else ""}" '
            f'title="{h(last_visit)}">{h(last)}</span></li>'
        )
    body = ((f'<div class="list-head" aria-hidden="true"><span>{h(t("dashboard.person"))}</span>'
             f'<span>{h(t("dashboard.status"))}</span><span>{h(last_visit)}</span></div>'
             f'<ul class="rows">{"".join(rows)}</ul>')
            if rows else _empty(t("dashboard.no_needs")))
    more = t("dashboard.view_all_care", n=len(people)) if len(people) > VISIT_ROWS else t("dashboard.open_care")
    return _panel(name, title, body, meta=h(meta), head_link=count, foot=_link(more, "/care"), span=span)


def _services(rows, span):
    name, title = "services", t("dashboard.services")
    if rows is _FAILED:
        return _failed(name, title, span)
    meta = tn("dashboard.services_meta", len(rows)) if rows else t("dashboard.head_count")
    # the link sits at the foot, as in the other panels: the header keeps one line in a 4-column card
    link = _link(t("core.nav_calendar"), "/calendar")
    if not rows:
        return _panel(name, title, _empty(t("dashboard.no_head_count")), meta=h(meta), foot=link, span=span)
    counts = [r["count"] for r in rows]
    last = rows[-1]
    word, average = trend(counts)
    said = t("dashboard.said", count=last["count"], date=ui.fmt_date(last["starts_at"]))
    if word is None:
        line = f'<p class="trend" data-row>{h(t("dashboard.trend_later", said=said))}</p>'
    else:
        sentence = tn("dashboard.trend_line", len(counts) - 1, said=said, average=average)
        line = (f'<p class="trend" data-row><strong class="trend-{word.lower()}">{h(t(TREND_WORDS[word]))}</strong>'
                f' · {h(sentence)}</p>')
    chart = services_svg(rows) if len(rows) > 1 else ""
    return _panel(name, title, chart + line, meta=h(meta), foot=link, span=span)


def _money_month(totals, today, span):
    name, title = "money-month", t("dashboard.money_month")
    if totals is _FAILED:
        return _failed(name, title, span)
    balance_cls = " neg" if totals["balance"] < 0 else ""
    body = (
        '<div class="kpis">'
        f'<div class="kpi" data-row><span class="kpi-label">{h(t("dashboard.offerings"))}</span>'
        f'<span class="kpi-value num">{h(ui.fmt_money(totals["offerings"]))}</span></div>'
        f'<div class="kpi" data-row><span class="kpi-label">{h(t("dashboard.expenses"))}</span>'
        f'<span class="kpi-value num">{h(ui.fmt_money(totals["expenses"]))}</span></div>'
        f'<div class="kpi" data-row><span class="kpi-label">{h(t("dashboard.balance"))}</span>'
        f'<span class="kpi-value num strong{balance_cls}">{h(ui.fmt_money(totals["balance"]))}</span></div>'
        "</div>"
    )
    if totals["offerings"] == 0 and totals["expenses"] == 0:
        body += _empty(t("dashboard.no_money"))
    foot = _link(t("dashboard.record_offering"), "/money/offerings/new") + _link(t("dashboard.open_money"), "/money")
    return _panel(name, title, body, meta=h(ui.fmt_month(today.year, today.month)), foot=foot, span=span)


def _sent_documents(next_number, recent, year, span):
    name, title = "sent-documents", t("dashboard.sent_documents")
    if next_number is _FAILED or recent is _FAILED:
        return _failed(name, title, span)
    count, recent = recent
    meta = tn("dashboard.sent_in_year", count, year=year)
    body = (f'<div class="kpi" data-row><span class="kpi-label">{h(t("dashboard.next_number"))}</span>'
            f'<span class="kpi-value num">{h(next_number)}</span></div>')
    rows = []
    for s in recent:
        # date · Recipient · Purpose may wrap to 2 lines (full text in the title); a "·" stays with
        # the word after it (no-break space), so no line ends on a dangling "·"
        items = (h(ui.fmt_date(s["date"])), vi(s["recipient_name"]), h(s["purpose_name"]) or ui.DASH)
        sub = " ·\u00a0".join(items)
        sub_text = " · ".join(x or "—" for x in (ui.fmt_date(s["date"]), s["recipient_name"], s["purpose_name"]))
        number = f'<span class="num nowrap">{h(s["number"])}</span>'
        subject = clamp2(f'{number} {vi(s["subject"]) if s["subject"] else ""}',
                         f'{s["number"]} {s["subject"] or ""}'.strip())
        rows.append(f'<li class="row" data-row><span class="what wrap">{subject}'
                    f'{clamp2(sub, sub_text, cls="sub")}</span></li>')
    body += f'<ul class="rows">{"".join(rows)}</ul>' if rows else _empty(t("dashboard.no_sent"))
    # /sent lists this year: more than SENT_ROWS this year means the rows shown are this year's newest
    more = t("dashboard.view_all_sent", n=count) if count > SENT_ROWS else t("dashboard.open_sent")
    return _panel(name, title, body, meta=h(meta), foot=_link(more, "/sent"), span=span)


def _search_panel():
    """Search sits in the title row: type a name, see People at once (app.js), or press Search.
    The two sentences app.js may show are in ``data-text-none`` and ``data-text-failed``."""
    return (
        '<section class="title-search" data-panel="search" aria-labelledby="p-search">'
        f'<h2 id="p-search" class="sr-only">{h(t("search.title"))}</h2>'
        '<form class="search-form" action="/search" method="get" role="search" data-live-search '
        f'data-text-none="{h(t("search.live_none"))}" data-text-failed="{h(t("search.live_failed"))}">'
        f'<label for="dash-q">{h(t("search.find_person"))}</label>'
        '<div class="search-line"><input class="input" id="dash-q" name="q" type="search" '
        f'autocomplete="off" placeholder="{h(t("search.placeholder"))}">'
        f'<button class="btn secondary" type="submit">{h(t("core.btn_search"))}</button></div>'
        '<ul class="results" data-results aria-live="polite" hidden></ul>'
        "</form></section>"
    )


def _recent_sent(conn, year):
    """``(count, rows)``: how many Sent documents ``year`` has, and the last ones, newest first
    (this year, then last year if needed)."""
    this_year = sent.list_sent_documents(conn, year)
    rows = list(reversed(this_year))
    if len(rows) < SENT_ROWS:
        rows += list(reversed(sent.list_sent_documents(conn, year - 1)))
    return len(this_year), rows[:SENT_ROWS]


# ---------------------------------------------------------------- page

def dashboard(req):
    conn = req.conn
    today = _dt.date.today()
    week = _load(cal.items_between, conn, today, today + _dt.timedelta(days=6))
    needs = _load(care.needs_visit, conn, today)
    months = _load(care.reminder_months, conn)
    counts = _load(cal.recent_head_counts, conn, HEAD_COUNTS)
    totals = _load(money.month_totals, conn, today.year, today.month)
    next_number = _load(sent.next_number, conn, today.year)
    recent = _load(_recent_sent, conn, today.year)

    # CRIT-3, a number is said once: the line under the h1 is the day only; how many Calendar items the
    # Next 7 days have is in the figures strip
    finding = f"{ui.fmt_weekday(today)} {ui.fmt_date(today)}"
    body = (
        _next_item(week, today)
        + _figures(week, needs, totals, today)
        + '<div class="grid dashboard">'
        + _this_week(week, today, "span-7")
        + _needs_visit(needs, months, "span-5")
        + _services(counts, ROW2_SPANS[0])
        + _money_month(totals, today, ROW2_SPANS[1])
        + _sent_documents(next_number, recent, today.year, ROW2_SPANS[2])
        + "</div>"
    )
    actions = _search_panel() + ui.link_button(t("dashboard.plan_visit"), "/care", "primary")
    return Response.html(ui.page(t("dashboard.title"), body, "dashboard", sub=h(finding),
                                 actions=actions))


ROUTES = [("GET", "/", dashboard)]
