"""Calendar pages (card C2): ``/calendar`` (one week, one month, or the 7 days from ``?from=``),
``/calendar/new``, and
``/calendar/<id>`` (details, edit, delete, the people who join or serve, the Head count).

Rules kept here:
- Calendar items change only through the data layer (``calendar.*`` and ``care.plan_visit``).
- Past links are history. A past Calendar item that people joined or served cannot move to today
  or later (then it could be deleted), and taking a Person off a past item asks "Are you sure?" first.
- Delete always asks first. The data layer decides what may be deleted; the page shows its reason.
- A Head count is for a Service on or before today.
- Words on screen come from the text table (section ``calendar``); kinds through ``ui.calendar_kind``.
  Titles, places, notes and names are shown as stored.
"""

import datetime as _dt
import re

from .. import calendar as cal
from .. import care, i18n, people, text, ui
from ..db import transaction
from ..i18n import TextError, t, tn
from ..schema import CALENDAR_KINDS
from ..server import Response
from ..ui import clamp2, h, vi
from . import documents as document_pages  # card C3: the shared Documents block
from .care import default_start, placed_errors
from .people import change_box, empty, family_link, form_error, num, panel, person_link, today_text

PART_WORDS = {"serves": "calendar.part_serves", "joins": "calendar.part_joins"}  # TEXT keys
REPEATS = (("none", "calendar.repeat_none"), ("weekly", "calendar.repeat_weekly"),
           ("monthly", "calendar.repeat_monthly"))  # (value, TEXT key)
RECORD_WEEKS = 8  # "Head count to record" looks back this many weeks
_MONTH = re.compile(r"([0-9]{4})-([0-9]{2})")

_ITEM_LABELS = {"kind": "calendar.kind", "title": "calendar.title_label", "starts_at": "calendar.starts_at",
                "ends_at": "calendar.ends_at", "repeat_until": "calendar.repeat_until", "repeat": "calendar.repeat",
                "person_id": "calendar.person", "family_id": "calendar.family"}


# ---------------------------------------------------------------- small logic (tested)

def week_start(day):
    """The Monday of the week that holds ``day``."""
    return day - _dt.timedelta(days=day.weekday())


def parse_week(value, today):
    """``?week=YYYY-MM-DD`` -> the Monday of that week. Empty -> the Monday of this week."""
    if not (value or "").strip():
        return week_start(today)
    return week_start(_dt.date.fromisoformat(text.check_date(value, "calendar.week")))


def parse_from(value):
    """``?from=YYYY-MM-DD`` -> that date (the first of 7 days). A bad date raises ``ValueError``."""
    return _dt.date.fromisoformat(text.check_date(value, "calendar.first_day"))


def parse_month(value):
    """``"2026-11"`` -> ``(2026, 11)``. Anything else raises ``TextError``: the form sentence, or the
    years sentence for the right form with a year outside :data:`FIRST_MONTH` to :data:`LAST_MONTH`."""
    m = _MONTH.fullmatch((value or "").strip())
    if m is None or not 1 <= int(m.group(2)) <= 12:
        raise TextError("calendar.err_month_form")
    year, month = int(m.group(1)), int(m.group(2))
    if month_step(year, month) is None:
        raise TextError("calendar.err_month_years")
    return year, month


def month_text(year, month):
    """``(2026, 11)`` -> ``"2026-11"`` (the ``?month=`` value)."""
    return f"{year:04d}-{month:02d}"


def shift_month(year, month, k):
    """``shift_month(2026, 12, 1)`` -> ``(2027, 1)``."""
    total = year * 12 + month - 1 + k
    return total // 12, total % 12 + 1


# A Money month and a Calendar month go from 1900-01 to 9999-12: the years of an Offering or Expense date.
FIRST_MONTH, LAST_MONTH = (1900, 1), (9999, 12)


def month_step(year, month, k=0):
    """The month ``k`` months from ``(year, month)``, or ``None`` when it is outside 1900-01 to 9999-12.
    Every month chip (Money and Calendar) uses it, so no chip links to a month the app refuses."""
    shifted = shift_month(year, month, k)
    return shifted if FIRST_MONTH <= shifted <= LAST_MONTH else None


def day_step(day, k):
    """``day`` plus ``k`` days, or ``None`` before 0001-01-01 or after 9999-12-31 (Python has no such
    date). The week and 7-day links use it, so they leave that link out instead of failing."""
    try:
        return day + _dt.timedelta(days=k)
    except OverflowError:
        return None


def month_picker(action, input_id, value):
    """The "Go to a month" form of the Money and Calendar pages, limited to 1900-01 to 9999-12. With
    ``data-auto-submit`` app.js opens the chosen month at once and style.css hides Show (CRIT-8); without
    the script Show sends the form."""
    return (f'<form class="month-picker" action="{action}" method="get" data-auto-submit>'
            f'<label for="{input_id}">{h(t("calendar.go_to_month"))}</label><div class="search-line">'
            f'<input class="input" id="{input_id}" name="month" type="month" value="{h(value)}" '
            f'min="{month_text(*FIRST_MONTH)}" max="{month_text(*LAST_MONTH)}" required>'
            f'<button class="btn secondary" type="submit">{h(t("calendar.show"))}</button></div></form>')


def form_datetime(value, what):
    """``2026-11-08T08:00`` (from ``<input type="datetime-local">``) -> ``2026-11-08 08:00``.
    Empty -> ``None``. A bad value raises ``ValueError`` starting with ``what`` (a TEXT key or a label)."""
    raw = (value or "").strip()
    if not raw:
        return None
    return text.check_datetime(raw.replace("T", " ")[:16], what)


def input_datetime(value):
    """``2026-11-08 08:00`` -> ``2026-11-08T08:00`` for ``<input type="datetime-local">``."""
    return value.replace(" ", "T") if value else ""


def leaves_the_past(old_start, new_start, has_people, today):
    """True when a past Calendar item that people joined or served would move to today or later.
    (Moved out of the past, it could be deleted and the Person story would lose it.)"""
    return bool(has_people) and old_start[:10] < today <= new_start[:10]


def parse_head_count(value):
    """``" 72 "`` -> ``72``. Only plain digits; too large or anything else raises ``ValueError``."""
    raw = (value or "").strip()
    if not (raw.isascii() and raw.isdigit()):
        raise TextError("calendar.err_hc_number")
    count = int(raw)
    if count > cal.MAX_HEAD_COUNT:
        raise TextError("calendar.err_hc_large")
    return count


def time_span(starts_at, ends_at):
    """``08:00–10:00``; just ``08:00`` with no end; the end date too when it is another day."""
    start = ui.fmt_time(starts_at)
    if not ends_at:
        return start
    if ends_at[:10] == starts_at[:10]:
        return f"{start}–{ui.fmt_time(ends_at)}"
    return f"{start} – {ui.fmt_date(ends_at)[:5]} {ui.fmt_time(ends_at)}"


def _errors(error, key):
    """Where a refused Calendar form shows its sentence (a repeat message goes to Repeat until).
    ``error`` is ``(form key, exception)``; the field is found from the English sentence."""
    errs = placed_errors(error, key, _ITEM_LABELS)
    message = errs.get("")
    if message:
        low = str(error[1]).lower()
        if "repeat" in low:
            return {"repeat_until": message}
        if "visit is for" in low:
            return {"person_id": message}
    return errs


def _day_label(day):
    return f"{ui.fmt_weekday(day)} {day.strftime('%d/%m')}"


def _kind(kind):
    return f'<span class="kind k-{h(kind.lower())}">{h(ui.calendar_kind(kind))}</span>'


def _part(part):
    return t(PART_WORDS[part])


def _persons(conn):
    return [("", t("calendar.choose_person"))] + [(p["id"], p["full_name"]) for p in people.list_persons(conn)]


def _kind_options(kinds):
    return [(k, ui.calendar_kind(k)) for k in kinds]


# ---------------------------------------------------------------- /calendar

def _item_row(it):
    sub, words = [_kind(it["kind"])], [ui.calendar_kind(it["kind"])]
    if it["kind"] == "Visit" and it["visit_name"] and it["visit_name"] not in it["title"]:
        sub.append(vi(it["visit_name"]))
        words.append(it["visit_name"])
    if it["place"]:
        sub.append(vi(it["place"]))
        words.append(it["place"])
    if it["kind"] == "Service" and it["head_count"] is not None:
        sub.append(ui.t_html("calendar.row_head_count", n=f'<span class="num">{it["head_count"]}</span>'))
        words.append(t("calendar.row_head_count", n=it["head_count"]))
    if it["kind"] == "Visit" and it["visit_done"]:
        sub.append(h(t("calendar.row_done")))
        words.append(t("calendar.row_done"))
    # B26: the title wraps to 2 lines (full text in its title); the grey line under it keeps one line
    link = f'<a href="/calendar/{it["id"]}">{h(it["title"])}</a>'
    return ('<li class="row cal-row" data-row>'
            f'<span class="time num">{h(time_span(it["starts_at"], it["ends_at"]))}</span>'
            f'<span class="what wrap">{clamp2(link, it["title"], lang="vi")}'
            f'<span class="sub" title="{h(" · ".join(words))}">{" · ".join(sub)}</span></span></li>')


def _day_block(day, items, today):
    is_today = day == today
    tag = f' <span class="today-tag">{h(t("calendar.today"))}</span>' if is_today else ""
    # an empty day is one short line: its date and a faint dash; the sentence is for screen readers (CRIT-9)
    rows = (f'<ul class="rows">{"".join(_item_row(it) for it in items)}</ul>' if items
            else f'<p class="cal-none"><span class="dash" aria-hidden="true">—</span>'
                 f'<span class="sr-only">{h(t("calendar.nothing_day"))}</span></p>')
    return (f'<div class="cal-day{" today" if is_today else ""}">'
            f'<p class="cal-date"><span class="num">{h(_day_label(day))}</span>{tag}</p>{rows}</div>')


def _agenda(items, first, last, today, every_day):
    by_day = {}
    for it in items:
        by_day.setdefault(_dt.date.fromisoformat(it["starts_at"][:10]), []).append(it)
    days = []
    for n in range((last - first).days + 1):  # never a day past ``last`` (9999-12-31 has no next day)
        day = first + _dt.timedelta(days=n)
        if every_day or day in by_day:
            days.append(_day_block(day, by_day.get(day, []), today))
    return "".join(days)


def _chip(label, href, current=False):
    mark = ' aria-current="true"' if current else ""
    return f'<a class="chip" href="{h(href)}"{mark}>{h(label)}</a>'


def month_chip(label, path, month):
    """A chip to ``month`` (``(year, month)`` from :func:`month_step`) on the page ``path``, or nothing
    when ``month`` is ``None``. ``{}`` in ``label`` becomes the short month ``MM/YYYY`` (``‹ 10/2026``), as
    a date is written in both languages: Prev, This and Next then fit one line on a phone (CRIT-8)."""
    if month is None:
        return ""
    return _chip(label.format(f"{month[1]:02d}/{month[0]:04d}"), ui.url(path, month=month_text(*month)))


def _day_chip(label, day, key):
    """A chip to the week (``key="week"``) or the 7 days (``key="from"``) of ``day``; nothing when ``None``."""
    return "" if day is None else _chip(label, ui.url("/calendar", **{key: day.isoformat()}))


def _toolbar(mode, first, today):
    """The period bar (CRIT-8): Prev / This / Next (``.period``, one line), the view chips (``.views``: Week,
    Month) and the "Go to a month" picker, all in one ``nav``. Each chip goes to a period or a view."""
    if mode == "week":
        this = week_start(today)
        shown_month = today if first == this else first  # the month picker starts at the month in view
        period = (_day_chip(t("calendar.prev_week"), day_step(first, -7), "week")
                  + _chip(t("calendar.this_week"), "/calendar", first == this)
                  + _day_chip(t("calendar.next_week"), day_step(first, 7), "week"))
        views = month_chip(t("calendar.month"), "/calendar", month_step(shown_month.year, shown_month.month))
        month_value = month_text(shown_month.year, shown_month.month)
    elif mode == "days":  # 7 days from ?from= (the Dashboard's "Next 7 days": today and the 6 days after)
        period = (_day_chip(t("calendar.prev_days"), day_step(first, -7), "from")
                  + _chip(t("calendar.from_today"), ui.url("/calendar", **{"from": today.isoformat()}), first == today)
                  + _day_chip(t("calendar.next_days"), day_step(first, 7), "from"))
        views = (_day_chip(t("calendar.week"), first, "week")
                 + month_chip(t("calendar.month"), "/calendar", month_step(first.year, first.month)))
        month_value = month_text(first.year, first.month)
    else:
        this_month = (first.year, first.month) == (today.year, today.month)
        period = (month_chip("‹ {}", "/calendar", month_step(first.year, first.month, -1))
                  + _chip(t("calendar.this_month"), ui.url("/calendar", month=month_text(today.year, today.month)),
                          this_month)
                  + month_chip("{} ›", "/calendar", month_step(first.year, first.month, 1)))
        views = _chip(t("calendar.week"), "/calendar" if this_month else ui.url("/calendar", week=first.isoformat()))
        month_value = month_text(first.year, first.month)
    label = t({"week": "calendar.chips_week", "days": "calendar.chips_days"}.get(mode, "calendar.chips_month"))
    views = f'<div class="chips views">{views}</div>' if views else ""
    return (f'<nav class="list-toolbar" aria-label="{h(label)}"><div class="period">{period}</div>{views}'
            f'{month_picker("/calendar", "cal-month", month_value)}</nav>')


def _to_record_panel(conn, today):
    since = today - _dt.timedelta(weeks=RECORD_WEEKS)
    rows = [it for it in cal.items_between(conn, since, today)
            if it["kind"] == "Service" and it["head_count"] is None]
    record = h(t("calendar.record"))
    lines = "".join(
        '<li class="row" data-row><span class="what wrap">'
        + clamp2(f'<a href="/calendar/{it["id"]}#head-count">{h(it["title"])}</a>', it["title"], lang="vi")
        + f'<span class="sub num">{h(ui.fmt_weekday(it["starts_at"]))} {h(ui.fmt_datetime(it["starts_at"]))}</span></span>'
        f'<a class="row-action" href="/calendar/{it["id"]}#head-count">{record}</a></li>'
        for it in reversed(rows)
    )
    body = (f'<ul class="rows">{lines}</ul>' if rows
            else empty(t("calendar.to_record_none", weeks=RECORD_WEEKS)))
    count = f'<span class="count num">{h(tn("calendar.services", len(rows)))}</span>' if rows else ""
    return panel("to-record", t("calendar.to_record"), body,
                 meta=h(t("calendar.to_record_meta", weeks=RECORD_WEEKS)), head_right=count)


def calendar_page(req):
    conn = req.conn
    today = _dt.date.today()
    if (req.query.get("month") or "").strip():
        year, month = parse_month(req.query["month"])
        mode, first = "month", _dt.date(year, month, 1)
        last = first.replace(day=cal.month_days(year, month))
        scope = ui.fmt_month(year, month)
    elif (req.query.get("from") or "").strip():
        mode, first = "days", parse_from(req.query["from"])
        last = day_step(first, 6) or _dt.date.max  # the last 7 days stop at 9999-12-31
        scope = f"{first.strftime('%d/%m')} – {last.strftime('%d/%m/%Y')}"
    else:
        mode, first = "week", parse_week(req.query.get("week"), today)
        last = day_step(first, 6) or _dt.date.max  # the last week stops on Friday 9999-12-31
        scope = t("calendar.scope_week", first=first.strftime("%d/%m"), last=last.strftime("%d/%m/%Y"))
    items = cal.items_between(conn, first, last)
    services = sum(1 for it in items if it["kind"] == "Service")
    finding = h(" · ".join((scope, tn("calendar.items", len(items)), tn("calendar.services", services))))
    agenda = _agenda(items, first, last, today, every_day=mode != "month")
    if not agenda:
        agenda = empty(t("calendar.nothing_in", scope=scope))
    main = (f'<section class="panel list-panel agenda" data-panel="calendar-list" aria-label="{h(scope)}">'
            f"{agenda}</section>")
    body = (_toolbar(mode, first, today)
            + f'<div class="grid calendar"><div class="span-8 stack">{main}</div>'
            f'<div class="side-4 stack">{_to_record_panel(conn, today)}</div></div>')
    actions = ui.link_button(t("calendar.add"), "/calendar/new", "primary")
    return Response.html(ui.page(t("calendar.title"), body, "calendar", sub=finding, actions=actions))


# ---------------------------------------------------------------- /calendar/new

def _start_value(req):
    day = (req.query.get("date") or "").strip()
    try:
        return f"{text.check_date(day)}T08:00" if day else default_start()
    except ValueError:
        return default_start()


def _new_form(req, values=None, error=None, status=200):
    conn = req.conn
    v = (values or {}).get
    errors = _errors(error, "new")
    families = [("", t("calendar.or_family"))] + [(f["id"], f["name"]) for f in people.list_families(conn)]
    inner = (
        ui.select_field(t("calendar.kind"), "kind", _kind_options(CALENDAR_KINDS), selected=v("kind", "Service"),
                        error=errors.get("kind"))
        + ui.field(t("calendar.title_label"), "title", v("title", ""), error=errors.get("title"), autocomplete="off",
                   lang="vi", hint=t("calendar.title_hint"))
        + '<div class="inline-fields two">'
        + ui.field(t("calendar.starts_at"), "starts_at", v("starts_at") or _start_value(req), type="datetime-local",
                   required=True, error=errors.get("starts_at"))
        + ui.field(t("calendar.ends_at"), "ends_at", v("ends_at", ""), type="datetime-local",
                   error=errors.get("ends_at"), hint=t("calendar.optional"))
        + "</div>"
        + ui.field(t("calendar.place"), "place", v("place", ""), autocomplete="off", lang="vi")
        + ui.textarea_field(t("calendar.note"), "note", v("note", ""), lang="vi", rows=2)
        + '<div class="inline-fields two">'
        + ui.select_field(t("calendar.repeat"), "repeat", [(value, t(key)) for value, key in REPEATS],
                          selected=v("repeat", "none"), error=errors.get("repeat"))
        + ui.field(t("calendar.repeat_until"), "repeat_until", v("repeat_until", ""), type="date",
                   error=errors.get("repeat_until"), hint=t("calendar.until_hint"))
        + "</div>"
        + f'<fieldset class="group"><legend>{h(t("calendar.visit_only"))}</legend><div class="inline-fields two">'
        + ui.select_field(t("calendar.person"), "person_id", _persons(conn), selected=v("person_id", ""), lang="vi",
                          error=errors.get("person_id"))
        + ui.select_field(t("calendar.family"), "family_id", families, selected=v("family_id", ""), lang="vi",
                          error=errors.get("family_id"))
        + f'</div><p class="hint">{h(t("calendar.visit_hint"))}</p></fieldset>'
        + form_error(errors) + ui.button(t("calendar.add_button"))
    )
    body = f'<section class="panel narrow">{ui.form("/calendar/new", inner)}</section>'
    return Response.html(ui.page(t("calendar.add"), body, "calendar"), status)


def new_page(req):
    return _new_form(req)


def add_calendar_item_from_form(conn, form):
    """Add a Calendar item (or its repeat) from the Add a Calendar item form: the one place of its rules,
    for this page and the Hermes door. ``form`` has ``.get``. Returns the list of new Calendar item ids;
    a refused value raises ``ValueError`` (a ``TextError``: ``str()`` is the English sentence)."""
    f = form
    kind = f.get("kind") or ""
    if kind not in CALENDAR_KINDS:
        raise TextError("calendar.err_kind")
    starts = form_datetime(f.get("starts_at"), "calendar.starts_at")
    if starts is None:
        raise TextError("errors.required", label="calendar.starts_at")
    ends = form_datetime(f.get("ends_at"), "calendar.ends_at")
    if ends is not None and ends < starts:
        raise TextError("calendar.err_ends_before")
    repeat = f.get("repeat") or "none"
    until = (f.get("repeat_until") or "").strip() or None
    person_id = f.get("person_id") or None
    family_id = f.get("family_id") or None
    if kind == "Visit":
        if repeat != "none" or until:
            raise TextError("calendar.err_visit_repeat")
        with transaction(conn):
            iid = care.plan_visit(conn, starts, person_id=person_id, family_id=family_id,
                                  title=f.get("title"), note=f.get("note"))
            if ends is not None or (f.get("place") or "").strip():
                cal.update_calendar_item(conn, iid, ends_at=ends, place=f.get("place"))
        return [iid]
    if person_id or family_id:
        raise TextError("calendar.err_not_visit")
    return cal.add_calendar_item(conn, kind, f.get("title"), starts, ends, f.get("place"), f.get("note"),
                                 repeat, until)


def new_post(req):
    conn = req.conn
    f = req.form
    try:
        ids = add_calendar_item_from_form(conn, f)
    except ValueError as exc:
        return _new_form(req, f, ("new", exc), 400)
    if len(ids) == 1:
        first = cal.get_calendar_item(conn, ids[0])
        msg = t("calendar.added_one", kind=ui.calendar_kind(first["kind"]), when=ui.fmt_datetime(first["starts_at"]))
    else:
        key = "calendar.added_weekly" if f.get("repeat") == "weekly" else "calendar.added_monthly"
        msg = t(key, n=len(ids), until=ui.fmt_date(f["repeat_until"].strip()))
    return Response.redirect(ui.url(f"/calendar/{ids[0]}", msg=msg))


# ---------------------------------------------------------------- /calendar/<id>

def _details_panel(conn, row):
    iid = row["id"]
    rows = [(t("calendar.kind"), _kind(row["kind"])),
            (t("calendar.starts_at"), num(f"{ui.fmt_weekday(row['starts_at'])} {ui.fmt_datetime(row['starts_at'])}")),
            (t("calendar.ends_at"), num(ui.fmt_datetime(row["ends_at"])) if row["ends_at"] else ui.DASH),
            (t("calendar.place"), vi(row["place"])),
            (t("calendar.note"), vi(row["note"]))]
    if row["kind"] == "Visit":
        if row["visit_person_id"] is not None:
            who = person_link(row["visit_person_id"], people.get_person(conn, row["visit_person_id"])["full_name"])
        elif row["visit_family_id"] is not None:
            fam = conn.execute("SELECT name FROM family WHERE id = ?", (row["visit_family_id"],)).fetchone()
            who = family_link(row["visit_family_id"], fam["name"])
        else:
            who = ui.DASH
        rows.append((t("calendar.for"), who))
        if row["visit_done"]:
            rows.append((t("core.kind_visit"),
                         ui.t_html("calendar.done_on",
                                   date=f'<span class="num">{h(ui.fmt_date(row["visit_done_date"]))}</span>')))
            rows.append((t("calendar.care_note"), vi(row["care_note"])))
        else:
            rows.append((t("core.kind_visit"), f'{h(t("calendar.not_done_yet"))}<span class="no-print"> '
                                               f'<a href="/care">{h(t("calendar.mark_done_in_care"))}</a></span>'))
    if row["series_id"] is not None:
        series = cal.series_items(conn, row["series_id"])
        k = next(i for i, s in enumerate(series) if s["id"] == iid)
        links = []
        if k > 0:
            links.append(f'<a href="/calendar/{series[k - 1]["id"]}">‹ {h(ui.fmt_date(series[k - 1]["starts_at"]))}</a>')
        if k < len(series) - 1:
            links.append(f'<a href="/calendar/{series[k + 1]["id"]}">{h(ui.fmt_date(series[k + 1]["starts_at"]))} ›</a>')
        position = ui.t_html("calendar.repeat_pos",
                             pos=f'<span class="num">{h(t("calendar.k_of_n", k=k + 1, n=len(series)))}</span>',
                             until=f'<span class="num">{h(ui.fmt_date(series[-1]["starts_at"]))}</span>')
        rows.append((t("calendar.repeat"),
                     position + (f'<br><span class="series-links">{" · ".join(links)}</span>' if links else "")))
    body = '<dl class="kv">' + "".join(f"<div><dt>{h(k)}</dt><dd>{v}</dd></div>" for k, v in rows) + "</dl>"
    return panel("details", t("calendar.details"), body)


def _edit_panel(row, error, vals):
    errors = _errors(error, "edit")
    v = vals.get if errors else (lambda key, default="": {
        "kind": row["kind"], "title": row["title"], "starts_at": input_datetime(row["starts_at"]),
        "ends_at": input_datetime(row["ends_at"]), "place": row["place"] or "", "note": row["note"] or "",
    }.get(key, default))
    if row["kind"] == "Visit":
        kind_field = f'<p class="hint">{h(t("calendar.visit_keeps_kind"))}</p>'
    else:
        kind_field = ui.select_field(t("calendar.kind"), "kind", _kind_options(k for k in CALENDAR_KINDS if k != "Visit"),
                                     selected=v("kind", row["kind"]), id="edit-kind", error=errors.get("kind"))
    inner = (
        kind_field
        + ui.field(t("calendar.title_label"), "title", v("title", ""), id="edit-title", required=True, lang="vi",
                   autocomplete="off", error=errors.get("title"))
        + ui.field(t("calendar.starts_at"), "starts_at", v("starts_at", ""), type="datetime-local", id="edit-starts",
                   required=True, error=errors.get("starts_at"))
        + ui.field(t("calendar.ends_at"), "ends_at", v("ends_at", ""), type="datetime-local", id="edit-ends",
                   error=errors.get("ends_at"), hint=t("calendar.optional"))
        + ui.field(t("calendar.place"), "place", v("place", ""), id="edit-place", lang="vi", autocomplete="off")
        + ui.textarea_field(t("calendar.note"), "note", v("note", ""), id="edit-note", lang="vi", rows=2)
        + form_error(errors) + ui.button(t("core.btn_save"))
    )
    form = ui.form(f"/calendar/{row['id']}/edit", inner)
    hint = (f'<p class="hint">{h(t("calendar.only_this"))}</p>' if row["series_id"] is not None else "")
    return panel("edit", t("core.btn_edit"), hint + change_box(t("calendar.edit_this"), form, bool(errors)))


def _people_panel(conn, row, error, vals, today):
    iid = row["id"]
    listed = cal.item_people(conn, iid)
    errors = placed_errors(error, "people", {"person_id": "calendar.person", "part": "calendar.part"})
    past = row["starts_at"][:10] < today
    remove = h(t("calendar.remove"))
    lines = "".join(
        '<li class="row" data-row>'
        f'<span class="what wrap">{clamp2(person_link(p["person_id"], p["full_name"]), p["full_name"])}</span>'
        f'{ui.row_side([h(_part(p["part"]))], [_part(p["part"])])}'
        f'<form class="row-form" action="/calendar/{iid}/people/remove" method="post">'
        f'{ui.hidden("person_id", p["person_id"])}{ui.hidden("part", p["part"])}'
        f'<button class="link-btn" type="submit" '
        f'aria-label="{h(t("calendar.remove_label", name=p["full_name"], part=_part(p["part"])))}">'
        f"{remove}</button></form></li>"
        for p in listed
    )
    body = f'<ul class="rows">{lines}</ul>' if listed else empty(t("calendar.no_one"))
    if past and listed:
        body += f'<p class="hint">{h(t("calendar.past_hint"))}</p>'
    form = ui.form(f"/calendar/{iid}/people", (
        '<div class="add-person">'
        + ui.select_field(t("calendar.person"), "person_id", _persons(conn), selected=vals.get("person_id", ""),
                          id="add-person", lang="vi", error=errors.get("person_id"))
        + ui.select_field(t("calendar.part"), "part", [(part, _part(part)) for part in ("serves", "joins")],
                          selected=vals.get("part", "serves"), id="add-part", error=errors.get("part"))
        + ui.button(t("core.btn_add"), "secondary") + "</div>" + form_error(errors)))
    form = f'<div class="add-form">{form}</div>'
    serves = sum(1 for p in listed if p["part"] == "serves")
    meta = h(t("calendar.people_meta", serves=serves, joins=len(listed) - serves))
    return panel("people", t("calendar.people"), body + form, meta=meta)


def _head_count_panel(conn, row, error, vals, today):
    iid = row["id"]
    hc = cal.get_head_count(conn, iid)
    errors = placed_errors(error, "head-count", {"count": "calendar.head_count", "absent_note": "calendar.absent"})
    if hc is not None:
        absent = (f'<p class="absent" lang="vi">{h(hc["absent_note"])}</p>' if hc["absent_note"]
                  else f'<p class="absent faint">{h(t("calendar.no_absent_note"))}</p>')
        current = (f'<div class="kpi" data-row><span class="kpi-label">{h(t("calendar.head_count"))}</span>'
                   f'<span class="kpi-value num">{hc["count"]}</span></div>{absent}')
    else:
        current = ""
    if row["starts_at"][:10] > today:
        form_html = empty(t("calendar.hc_later"))
        if errors:
            form_html += form_error({"": next(iter(errors.values()))})
    else:
        v = vals.get if errors else (lambda key, default="": (
            {"count": str(hc["count"]), "absent_note": hc["absent_note"] or ""} if hc else {}).get(key, default))
        form = ui.form(f"/calendar/{iid}/head-count", (
            '<div class="inline-fields">'
            + ui.field(t("calendar.head_count"), "count", v("count", ""), type="number", id="hc-count", min="0",
                       step="1", required=True, error=errors.get("count"), hint=t("calendar.hc_hint"))
            + ui.textarea_field(t("calendar.absent"), "absent_note", v("absent_note", ""), id="hc-absent", lang="vi",
                                rows=2, hint=t("calendar.absent_hint"))
            + "</div>" + form_error(errors) + ui.button(t("calendar.save_hc"), "secondary")))
        form_html = change_box(t("calendar.change_hc"), form, bool(errors)) if hc else form
    if hc is None and row["starts_at"][:10] <= today and not errors:
        current = f'<p class="hint">{h(t("calendar.no_hc"))}.</p>'
    return f'<div id="head-count">{panel("head-count", t("calendar.head_count"), current + form_html)}</div>'


def _delete_panel(conn, row, error):
    message = i18n.error_text(error[1]) if error and error[0] == "delete" else None
    key = None if message else cal.delete_refusal_key(conn, row["id"])  # a read only: no write lock on a page view
    reason = message or (t(key) if key else None)
    if reason:
        body = f'<p class="{"error" if message else "hint"}" role="{"alert" if message else "note"}">{h(reason)}</p>'
    else:
        body = (ui.form(f"/calendar/{row['id']}/delete", ui.button(t("calendar.delete_this"), "danger"))
                + f'<p class="hint">{h(t("calendar.delete_hint"))}</p>')
    return panel("delete", t("core.btn_delete"), body, cls="no-print")


def documents_spot(conn, row):
    """The Documents panel of this Calendar item (card C3), in the main column under People and Head count."""
    return document_pages.documents_panel(conn, calendar_item_id=row["id"])


def _item_view(req, row, error=None, status=200):
    conn = req.conn
    today = today_text()
    form_key = error[0] if error else None

    def vals(key):
        return req.form if form_key == key else {}

    left = ""
    if row["kind"] == "Service":  # the Head count is the Service's own job, so it comes first
        left += _head_count_panel(conn, row, error, vals("head-count"), today)
    left += _people_panel(conn, row, error, vals("people"), today)
    left += documents_spot(conn, row)
    right = _details_panel(conn, row) + _edit_panel(row, error, vals("edit")) + _delete_panel(conn, row, error)
    body = (f'<div class="grid calendar-item"><div class="span-8 stack">{left}</div>'
            f'<div class="side-4 stack">{right}</div></div>')
    finding = [h(ui.calendar_kind(row["kind"])), h(f"{ui.fmt_weekday(row['starts_at'])} {ui.fmt_date(row['starts_at'])}"),
               h(time_span(row["starts_at"], row["ends_at"]))]
    if row["place"]:
        finding.append(vi(row["place"]))
    if row["kind"] == "Service":
        hc = cal.get_head_count(conn, row["id"])
        finding.append(h(t("calendar.row_head_count", n=hc["count"]) if hc else t("calendar.no_hc")))
    week = ui.url("/calendar", week=row["starts_at"][:10])
    actions = ui.link_button(t("calendar.back_to_week"), week)
    return Response.html(ui.page(row["title"], body, "calendar", sub=" · ".join(finding), actions=actions,
                                 lang="vi"), status)


def _item_or_none(req):
    return cal.get_calendar_item(req.conn, req.params["id"])


def _missing():
    body = (f'<p class="lead">{h(t("calendar.not_found_text"))}</p>'
            f'<p><a href="/calendar">{h(t("calendar.go_to_calendar"))}</a></p>')
    return Response.html(ui.page(t("calendar.not_found"), body), 404)


def item_page(req):
    row = _item_or_none(req)
    return _missing() if row is None else _item_view(req, row)


def _change(req, key, do):
    """Run one change on a Calendar item. ``do(conn, row)`` returns the flash text, or a Response.
    A refused change shows the item page again (400) with the sentence next to its field."""
    row = _item_or_none(req)
    if row is None:
        return _missing()
    try:
        result = do(req.conn, row)
    except ValueError as exc:
        return _item_view(req, cal.get_calendar_item(req.conn, row["id"]) or row, (key, exc), 400)
    if isinstance(result, Response):
        return result
    return Response.redirect(ui.url(f"/calendar/{row['id']}", msg=result))


def edit_post(req):
    def do(conn, row):
        f = req.form
        starts = form_datetime(f.get("starts_at"), "calendar.starts_at")
        if starts is None:
            raise TextError("errors.required", label="calendar.starts_at")
        ends = form_datetime(f.get("ends_at"), "calendar.ends_at")
        if ends is not None and ends < starts:
            raise TextError("calendar.err_ends_before")
        if leaves_the_past(row["starts_at"], starts, cal.item_people(conn, row["id"]), today_text()):
            raise TextError("calendar.err_past_move")
        changes = {"title": f.get("title"), "starts_at": starts, "ends_at": ends, "place": f.get("place"),
                   "note": f.get("note")}
        if row["kind"] != "Visit":
            changes["kind"] = f.get("kind") or row["kind"]
        cal.update_calendar_item(conn, row["id"], **changes)
        return t("calendar.saved")
    return _change(req, "edit", do)


def people_post(req):
    def do(conn, row):
        if not req.form.get("person_id"):
            raise TextError("calendar.err_choose_person")
        part = req.form.get("part") or ""
        added = cal.add_person_to_item(conn, row["id"], req.form["person_id"], part)  # refuses another part
        name = people.get_person(conn, req.form["person_id"])["full_name"]
        # calendar.added_serves, calendar.added_joins, calendar.already_serves, calendar.already_joins
        return t(f"calendar.{'added' if added else 'already'}_{part}", name=name)
    return _change(req, "people", do)


def _confirm_page(title, question, action, fields, button_text, back_href):
    inner = "".join(ui.hidden(k, v) for k, v in fields.items()) + ui.hidden("confirm", "yes")
    form = ui.form(action, inner + ui.button(button_text, "danger"))
    body = (f'<section class="panel narrow" data-panel="confirm"><p class="lead">{question}</p>'
            f'<div class="confirm-actions">{form}{ui.link_button(t("core.btn_cancel"), back_href)}</div></section>')
    return Response.html(ui.page(title, body, "calendar"))


def _when(row):
    return f"{ui.fmt_weekday(row['starts_at'])} {ui.fmt_datetime(row['starts_at'])}"


def remove_person_post(req):
    def do(conn, row):
        f = req.form
        person = people.get_person(conn, f.get("person_id") or "0")
        part = f.get("part") or ""
        if person is None or part not in PART_WORDS:
            raise TextError("calendar.err_not_listed")
        past = row["starts_at"][:10] < today_text()
        if past and f.get("confirm") != "yes":
            question = ui.t_html("calendar.remove_question",
                                 name=f'<strong lang="vi">{h(person["full_name"])}</strong>', part=h(_part(part)),
                                 title=f'<strong lang="vi">{h(row["title"])}</strong>',
                                 when=f'<span class="num">{h(_when(row))}</span>')
            return _confirm_page(t("calendar.sure"), question, f"/calendar/{row['id']}/people/remove",
                                 {"person_id": person["id"], "part": part}, t("calendar.remove_yes"),
                                 f"/calendar/{row['id']}")
        removed = cal.remove_person_from_item(conn, row["id"], person["id"], part)
        if not removed:
            return t("calendar.not_listed", name=person["full_name"])
        return t("calendar.removed", name=person["full_name"], part=_part(part))
    return _change(req, "people", do)


def head_count_post(req):
    def do(conn, row):
        if row["kind"] != "Service":
            raise TextError("calendar.err_hc_service")
        if row["starts_at"][:10] > today_text():
            raise TextError("calendar.err_hc_future")
        count = parse_head_count(req.form.get("count"))
        cal.set_head_count(conn, row["id"], count, req.form.get("absent_note"))
        return t("calendar.hc_saved", n=count)
    return _change(req, "head-count", do)


def delete_post(req):
    def do(conn, row):
        if req.form.get("confirm") != "yes":
            key = cal.delete_refusal_key(conn, row["id"])
            if key:
                raise TextError(key)
            question = ui.t_html("calendar.delete_question", title=f'<strong lang="vi">{h(row["title"])}</strong>',
                                 kind=h(ui.calendar_kind(row["kind"])),
                                 when=f'<span class="num">{h(_when(row))}</span>')
            return _confirm_page(t("calendar.delete_title"), question, f"/calendar/{row['id']}/delete", {},
                                 t("calendar.delete_yes"), f"/calendar/{row['id']}")
        cal.delete_calendar_item(conn, row["id"])
        msg = t("calendar.deleted", title=row["title"], when=ui.fmt_datetime(row["starts_at"]))
        return Response.redirect(ui.url("/calendar", week=row["starts_at"][:10], msg=msg))
    return _change(req, "delete", do)


ROUTES = [
    ("GET", "/calendar", calendar_page),
    ("GET", "/calendar/new", new_page),
    ("POST", "/calendar/new", new_post),
    ("GET", "/calendar/<int:id>", item_page),
    ("POST", "/calendar/<int:id>/edit", edit_post),
    ("POST", "/calendar/<int:id>/people", people_post),
    ("POST", "/calendar/<int:id>/people/remove", remove_person_post),
    ("POST", "/calendar/<int:id>/head-count", head_count_post),
    ("POST", "/calendar/<int:id>/delete", delete_post),
]
