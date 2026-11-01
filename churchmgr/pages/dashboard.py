"""Dashboard ``/``: what needs the pastor this week? Six panels on one page.

Each panel is ``<section data-panel="NAME">``; each data line in it has ``data-row``.
A panel that cannot load keeps its frame and says so (the error goes to the console).
"""

import datetime as _dt
import traceback

from .. import calendar as cal
from .. import care, money, sent, ui
from ..server import Response
from ..ui import clamp2, h, vi

WEEK_ROWS = 6  # Calendar items shown before "View all"
VISIT_ROWS = 6  # Persons shown in Needs a visit (the card allows up to 10; the design rule caps lists at 4-6)
HEAD_COUNTS = 8
SENT_ROWS = 2  # B17: 2 recent rows keep Sent documents level with Services and Money this month
CHART_HEIGHT = 154  # px, the Services chart at every width
# Row 2 of the 12 columns: Services, Money this month, Sent documents (4 + 4 + 4)
ROW2_SPANS = ("span-4", "span-4", "span-4")
_FAILED = object()
# Round chart steps: 1, 2, 5, 10, 20, 25, 50, ... (integers only).
_STEPS = tuple(sorted({m * 10 ** e for e in range(9) for m in (1, 2, 5)} | {25 * 10 ** e for e in range(8)}))


# ---------------------------------------------------------------- small logic (tested)

def trend(counts):
    """The last Head count against the average of the earlier ones.

    Returns ``(word, average)``: word ``"Up"``, ``"Down"`` or ``"Same"``; the average is
    rounded half up. Fewer than 2 counts -> ``(None, None)``. Whole numbers only.
    """
    if len(counts) < 2:
        return None, None
    *earlier, last = counts
    total, k = sum(earlier), len(earlier)
    word = "Up" if last * k > total else "Down" if last * k < total else "Same"
    return word, (2 * total + k) // (2 * k)


def nice_scale(max_value):
    """Y axis for counts: ``(top, step)`` with round steps, ``top > max_value``, at most 4 steps."""
    for step in _STEPS:
        top = (max_value // step + 1) * step
        if top // step <= 4:
            return top, step
    return max_value + 1, max_value + 1


def services_svg(rows):
    """A small one-series line of Head counts (oldest left), drawn as inline SVG.

    The chart has one height (``CHART_HEIGHT``) at every width and fills the card width: x places are
    percentages, and the line sits in an inner SVG stretched across the plot (its stroke does not
    scale). So the 12px text keeps its size and the Services card keeps its height when the window
    changes. The y ticks and the last value sit in the side padding of ``.chart`` (style.css).
    With more than 5 Services every second date is labelled, counted back from the last one.
    """
    counts = [r["count"] for r in rows]
    n = len(counts)
    top, step = nice_scale(max(counts))
    height, pad_top, bottom = CHART_HEIGHT, 10, 28
    plot_h = height - pad_top - bottom

    def x(i):
        return 100 * i / (n - 1) if n > 1 else 50

    def y(c):
        return pad_top + plot_h - plot_h * c / top

    parts = []
    for v in range(0, top + 1, step):
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
    parts.append(f'<text class="end" x="100%" dx="8" y="{y(counts[-1]) + 4:.1f}">{counts[-1]}</text>')
    label = "; ".join(f"{ui.fmt_date(r['starts_at'])} {r['count']}" for r in rows)
    return (f'<svg class="chart" width="100%" height="{height}" role="img" '
            f'aria-label="Head count of the last {n} Services: {h(label)}">{"".join(parts)}</svg>')


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
    return _panel(name, title, f'<p class="empty">Could not load {h(title)}. <a class="no-print" href="/">Retry</a></p>',
                  span=span)


def _empty(sentence):
    return f'<p class="empty">{h(sentence)}</p>'


def _link(text, href):
    return f'<a class="card-link" href="{h(href)}">{h(text)}</a>'


def _day_label(day, today):
    if day == today:
        return "Today"
    if day == today + _dt.timedelta(days=1):
        return "Tomorrow"
    return f"{ui.fmt_weekday(day)} {day.strftime('%d/%m')}"


def _this_week(items, today, span):
    name, title = "this-week", "This week"
    if items is _FAILED:
        return _failed(name, title, span)
    last = today + _dt.timedelta(days=6)
    meta = f"{today.strftime('%d/%m')} – {last.strftime('%d/%m/%Y')}"
    rows = []
    for it in items[:WEEK_ROWS]:
        day = _dt.date.fromisoformat(it["starts_at"][:10])
        sub, words = [h(it["kind"])], [it["kind"]]
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
    body = f'<ul class="rows">{"".join(rows)}</ul>' if rows else _empty("Nothing this week.")
    more = f"View all {len(items)} in Calendar" if len(items) > WEEK_ROWS else "Open Calendar"
    # the same 7 days on the Calendar (not its Monday-to-Sunday week), so the count matches
    href = ui.url("/calendar", **{"from": today.isoformat()})
    return _panel(name, title, body, meta=meta, foot=_link(more, href), span=span)


def _needs_visit(people, months, span):
    name, title = "needs-visit", "Needs a visit"
    if people is _FAILED or months is _FAILED:
        return _failed(name, title, span)
    meta = f"No Visit in the last {ui.plural(months, 'month', 'months')}, or never"
    count = f'<span class="count num">{ui.plural(len(people), "Person", "People")}</span>'
    rows = []
    for p in people[:VISIT_ROWS]:
        last = ui.fmt_date(p["last_visit"]) if p["last_visit"] else "never"
        link = f'<a href="/people/{p["person_id"]}">{h(p["full_name"])}</a>'
        status = h(p["status_name"]) if p["status_name"] else ui.DASH
        rows.append(
            '<li class="row" data-row>'
            f'<span class="what wrap">{clamp2(link, p["full_name"], lang="vi")}</span>'
            f'{ui.row_side([status], [p["status_name"]])}'
            f'<span class="figure num{" faint" if not p["last_visit"] else ""}" '
            f'title="Last Visit">{h(last)}</span></li>'
        )
    body = (('<div class="list-head" aria-hidden="true"><span>Person</span><span>Status</span>'
             f'<span>Last Visit</span></div><ul class="rows">{"".join(rows)}</ul>')
            if rows else _empty("No one needs a visit now."))
    more = f"View all {len(people)} in Care" if len(people) > VISIT_ROWS else "Open Care"
    return _panel(name, title, body, meta=meta, head_link=count, foot=_link(more, "/care"), span=span)


def _services(rows, span):
    name, title = "services", "Services"
    if rows is _FAILED:
        return _failed(name, title, span)
    meta = f"Head count of the last {ui.plural(len(rows), 'Service', 'Services')}" if rows else "Head count"
    # the link sits at the foot, as in the other panels: the header keeps one line in a 4-column card
    link = _link("Calendar", "/calendar")
    if not rows:
        return _panel(name, title, _empty("No Head count recorded yet."), meta=meta, foot=link, span=span)
    counts = [r["count"] for r in rows]
    last = rows[-1]
    word, average = trend(counts)
    said = f"Head count {last['count']} on {ui.fmt_date(last['starts_at'])}"
    if word is None:
        line = f'<p class="trend" data-row>{h(said)}. A trend shows after the second Head count.</p>'
    else:
        before = ui.plural(len(counts) - 1, "Service", "Services")
        line = (f'<p class="trend" data-row><strong class="trend-{word.lower()}">{word}</strong> · '
                f'{h(said)}, against an average of {average} for the {before} before.</p>')
    chart = services_svg(rows) if len(rows) > 1 else ""
    return _panel(name, title, chart + line, meta=meta, foot=link, span=span)


def _money_month(totals, today, span):
    name, title = "money-month", "Money this month"
    if totals is _FAILED:
        return _failed(name, title, span)
    balance_cls = " neg" if totals["balance"] < 0 else ""
    body = (
        '<div class="kpis">'
        f'<div class="kpi" data-row><span class="kpi-label">Offerings</span>'
        f'<span class="kpi-value num">{h(ui.fmt_money(totals["offerings"]))}</span></div>'
        f'<div class="kpi" data-row><span class="kpi-label">Expenses</span>'
        f'<span class="kpi-value num">{h(ui.fmt_money(totals["expenses"]))}</span></div>'
        f'<div class="kpi" data-row><span class="kpi-label">Balance</span>'
        f'<span class="kpi-value num strong{balance_cls}">{h(ui.fmt_money(totals["balance"]))}</span></div>'
        "</div>"
    )
    if totals["offerings"] == 0 and totals["expenses"] == 0:
        body += _empty("No Offering or Expense recorded this month.")
    foot = _link("Record Offering", "/money/offerings/new") + _link("Open Money", "/money")
    return _panel(name, title, body, meta=h(ui.fmt_month(today.year, today.month)), foot=foot, span=span)


def _sent_documents(next_number, recent, year, span):
    name, title = "sent-documents", "Sent documents"
    if next_number is _FAILED or recent is _FAILED:
        return _failed(name, title, span)
    count, recent = recent
    meta = f"{ui.plural(count, 'Sent document', 'Sent documents')} in {year}"
    body = (f'<div class="kpi" data-row><span class="kpi-label">Next number</span>'
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
    body += f'<ul class="rows">{"".join(rows)}</ul>' if rows else _empty("No Sent document yet.")
    return _panel(name, title, body, meta=h(meta), foot=_link("Open Sent documents", "/sent"), span=span)


def _search_panel():
    """Search sits in the title row: type a name, see People at once (app.js), or press Search."""
    return (
        '<section class="title-search" data-panel="search" aria-labelledby="p-search">'
        '<h2 id="p-search" class="sr-only">Search</h2>'
        '<form class="search-form" action="/search" method="get" role="search" data-live-search>'
        '<label for="dash-q">Find a Person</label>'
        '<div class="search-line"><input class="input" id="dash-q" name="q" type="search" '
        'autocomplete="off" placeholder="With or without accents">'
        '<button class="btn secondary" type="submit">Search</button></div>'
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

    finding = [f"{ui.fmt_weekday(today)} {ui.fmt_date(today)}"]
    if needs is not _FAILED:
        finding.append(f"{ui.plural(len(needs), 'Person needs', 'People need')} a visit")
    if week is not _FAILED:
        finding.append(f"{ui.plural(len(week), 'Calendar item', 'Calendar items')} this week")
    body = (
        '<div class="grid dashboard">'
        + _this_week(week, today, "span-7")
        + _needs_visit(needs, months, "span-5")
        + _services(counts, ROW2_SPANS[0])
        + _money_month(totals, today, ROW2_SPANS[1])
        + _sent_documents(next_number, recent, today.year, ROW2_SPANS[2])
        + "</div>"
    )
    actions = _search_panel() + ui.link_button("Plan a Visit", "/care", "primary")
    return Response.html(ui.page("Dashboard", body, "dashboard", sub=h(" · ".join(finding)), actions=actions))


ROUTES = [("GET", "/", dashboard)]
