"""Calendar pages (card C2): ``/calendar`` (one week, one month, or the 7 days from ``?from=``),
``/calendar/new``, and
``/calendar/<id>`` (details, edit, delete, the people who join or serve, the Head count).

Rules kept here:
- Calendar items change only through the data layer (``calendar.*`` and ``care.plan_visit``).
- Past links are history. A past Calendar item that people joined or served cannot move to today
  or later (then it could be deleted), and taking a Person off a past item asks "Are you sure?" first.
- Delete always asks first. The data layer decides what may be deleted; the page shows its reason.
- A Head count is for a Service on or before today.
"""

import datetime as _dt
import re

from .. import calendar as cal
from .. import care, people, text, ui
from ..db import transaction
from ..schema import CALENDAR_KINDS
from ..server import Response
from ..ui import clamp2, h, vi
from . import documents as document_pages  # card C3: the shared Documents block
from .care import default_start
from .people import (change_box, empty, family_link, field_errors, form_error, not_found, num, panel,
                     person_link, today_text)

PART_WORDS = {"serves": "Serves", "joins": "Joins"}
REPEATS = (("none", "Does not repeat"), ("weekly", "Every week"), ("monthly", "Every month"))
RECORD_WEEKS = 8  # "Head count to record" looks back this many weeks
_MONTH = re.compile(r"([0-9]{4})-([0-9]{2})")

_ITEM_LABELS = {"kind": "Kind", "title": "Title", "starts_at": "Starts at", "ends_at": "Ends at",
                "repeat_until": "Repeat until", "repeat": "Repeat", "person_id": "Person", "family_id": "Family"}


# ---------------------------------------------------------------- small logic (tested)

def week_start(day):
    """The Monday of the week that holds ``day``."""
    return day - _dt.timedelta(days=day.weekday())


def parse_week(value, today):
    """``?week=YYYY-MM-DD`` -> the Monday of that week. Empty -> the Monday of this week."""
    if not (value or "").strip():
        return week_start(today)
    return week_start(_dt.date.fromisoformat(text.check_date(value, "Week")))


def parse_from(value):
    """``?from=YYYY-MM-DD`` -> that date (the first of 7 days). A bad date raises ``ValueError``."""
    return _dt.date.fromisoformat(text.check_date(value, "First day"))


def parse_month(value):
    """``"2026-11"`` -> ``(2026, 11)``. Anything else raises ``ValueError``: the form sentence, or the
    years sentence for the right form with a year outside :data:`FIRST_MONTH` to :data:`LAST_MONTH`."""
    m = _MONTH.fullmatch((value or "").strip())
    if m is None or not 1 <= int(m.group(2)) <= 12:
        raise ValueError("Month must be written YYYY-MM, for example 2026-11.")
    year, month = int(m.group(1)), int(m.group(2))
    if month_step(year, month) is None:
        raise ValueError("Month: use a year from 1900 to 9999.")
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
    """The "Go to a month" form of the Money and Calendar pages, limited to 1900-01 to 9999-12."""
    return (f'<form class="month-picker" action="{action}" method="get">'
            f'<label for="{input_id}">Go to a month</label><div class="search-line">'
            f'<input class="input" id="{input_id}" name="month" type="month" value="{h(value)}" '
            f'min="{month_text(*FIRST_MONTH)}" max="{month_text(*LAST_MONTH)}" required>'
            '<button class="btn secondary" type="submit">Show</button></div></form>')


def form_datetime(value, what):
    """``2026-11-08T08:00`` (from ``<input type="datetime-local">``) -> ``2026-11-08 08:00``.
    Empty -> ``None``. A bad value raises ``ValueError`` starting with ``what``."""
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
        raise ValueError("Head count must be a whole number of people, for example 72.")
    count = int(raw)
    if count > cal.MAX_HEAD_COUNT:
        raise ValueError("Head count is too large.")
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
    """Where a refused Calendar form shows its sentence (a repeat message goes to Repeat until)."""
    errs = field_errors(error, key, _ITEM_LABELS)
    message = errs.get("")
    if message:
        low = message.lower()
        if "repeat" in low:
            return {"repeat_until": message}
        if "visit is for" in low:
            return {"person_id": message}
    return errs


def _day_label(day):
    return f"{ui.fmt_weekday(day)} {day.strftime('%d/%m')}"


def _kind(kind):
    return f'<span class="kind k-{h(kind.lower())}">{h(kind)}</span>'


# ---------------------------------------------------------------- /calendar

def _item_row(it):
    sub, words = [_kind(it["kind"])], [it["kind"]]
    if it["kind"] == "Visit" and it["visit_name"] and it["visit_name"] not in it["title"]:
        sub.append(vi(it["visit_name"]))
        words.append(it["visit_name"])
    if it["place"]:
        sub.append(vi(it["place"]))
        words.append(it["place"])
    if it["kind"] == "Service" and it["head_count"] is not None:
        sub.append(f'Head count <span class="num">{it["head_count"]}</span>')
        words.append(f'Head count {it["head_count"]}')
    if it["kind"] == "Visit" and it["visit_done"]:
        sub.append("done")
        words.append("done")
    # B26: the title wraps to 2 lines (full text in its title); the grey line under it keeps one line
    link = f'<a href="/calendar/{it["id"]}">{h(it["title"])}</a>'
    return ('<li class="row cal-row" data-row>'
            f'<span class="time num">{h(time_span(it["starts_at"], it["ends_at"]))}</span>'
            f'<span class="what wrap">{clamp2(link, it["title"], lang="vi")}'
            f'<span class="sub" title="{h(" · ".join(words))}">{" · ".join(sub)}</span></span></li>')


def _day_block(day, items, today):
    is_today = day == today
    tag = ' <span class="today-tag">Today</span>' if is_today else ""
    rows = (f'<ul class="rows">{"".join(_item_row(it) for it in items)}</ul>' if items
            else '<p class="cal-none">Nothing on the Calendar.</p>')
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
    when ``month`` is ``None``. ``{}`` in ``label`` becomes the month name."""
    return "" if month is None else _chip(label.format(ui.fmt_month(*month)), ui.url(path, month=month_text(*month)))


def _day_chip(label, day, key):
    """A chip to the week (``key="week"``) or the 7 days (``key="from"``) of ``day``; nothing when ``None``."""
    return "" if day is None else _chip(label, ui.url("/calendar", **{key: day.isoformat()}))


def _toolbar(mode, first, today):
    if mode == "week":
        this = week_start(today)
        shown_month = today if first == this else first  # the month picker starts at the month in view
        links = (_day_chip("‹ Previous week", day_step(first, -7), "week")
                 + _chip("This week", "/calendar", first == this)
                 + _day_chip("Next week ›", day_step(first, 7), "week")
                 + month_chip("Month", "/calendar", month_step(shown_month.year, shown_month.month)))
        month_value = month_text(shown_month.year, shown_month.month)
    elif mode == "days":  # 7 days from ?from= (the Dashboard's "This week": today and the 6 days after)
        links = (_day_chip("‹ Previous 7 days", day_step(first, -7), "from")
                 + _chip("From today", ui.url("/calendar", **{"from": today.isoformat()}), first == today)
                 + _day_chip("Next 7 days ›", day_step(first, 7), "from")
                 + _day_chip("Week", first, "week")
                 + month_chip("Month", "/calendar", month_step(first.year, first.month)))
        month_value = month_text(first.year, first.month)
    else:
        this_month = (first.year, first.month) == (today.year, today.month)
        links = (month_chip("‹ {}", "/calendar", month_step(first.year, first.month, -1))
                 + _chip("This month", ui.url("/calendar", month=month_text(today.year, today.month)), this_month)
                 + month_chip("{} ›", "/calendar", month_step(first.year, first.month, 1))
                 + _chip("Week", "/calendar" if this_month else ui.url("/calendar", week=first.isoformat())))
        month_value = month_text(first.year, first.month)
    label = {"week": "Calendar weeks", "days": "Calendar 7 days"}.get(mode, "Calendar months")
    return (f'<div class="list-toolbar"><nav class="chips" aria-label="{label}">{links}</nav>'
            f'{month_picker("/calendar", "cal-month", month_value)}</div>')


def _to_record_panel(conn, today):
    since = today - _dt.timedelta(weeks=RECORD_WEEKS)
    rows = [it for it in cal.items_between(conn, since, today)
            if it["kind"] == "Service" and it["head_count"] is None]
    lines = "".join(
        '<li class="row" data-row><span class="what wrap">'
        + clamp2(f'<a href="/calendar/{it["id"]}#head-count">{h(it["title"])}</a>', it["title"], lang="vi")
        + f'<span class="sub num">{h(ui.fmt_weekday(it["starts_at"]))} {h(ui.fmt_datetime(it["starts_at"]))}</span></span>'
        f'<a class="row-action" href="/calendar/{it["id"]}#head-count">Record</a></li>'
        for it in reversed(rows)
    )
    body = (f'<ul class="rows">{lines}</ul>' if rows
            else empty(f"Every Service of the last {RECORD_WEEKS} weeks has a Head count."))
    count = f'<span class="count num">{h(ui.plural(len(rows), "Service", "Services"))}</span>' if rows else ""
    return panel("to-record", "Head count to record", body,
                 meta=f"Services of the last {RECORD_WEEKS} weeks with no Head count", head_right=count)


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
        scope = f"Week {first.strftime('%d/%m')} – {last.strftime('%d/%m/%Y')}"
    items = cal.items_between(conn, first, last)
    services = sum(1 for it in items if it["kind"] == "Service")
    finding = h(" · ".join((scope, ui.plural(len(items), "Calendar item", "Calendar items"),
                            ui.plural(services, "Service", "Services"))))
    agenda = _agenda(items, first, last, today, every_day=mode != "month")
    if not agenda:
        agenda = empty(f"Nothing on the Calendar in {scope}.")
    main = (f'<section class="panel list-panel agenda" data-panel="calendar-list" aria-label="{h(scope)}">'
            f"{agenda}</section>")
    body = (_toolbar(mode, first, today)
            + f'<div class="grid calendar"><div class="span-8 stack">{main}</div>'
            f'<div class="side-4 stack">{_to_record_panel(conn, today)}</div></div>')
    actions = ui.link_button("Add a Calendar item", "/calendar/new", "primary")
    return Response.html(ui.page("Calendar", body, "calendar", sub=finding, actions=actions))


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
    persons = [("", "— Choose a Person —")] + [(p["id"], p["full_name"]) for p in people.list_persons(conn)]
    families = [("", "— or a Family —")] + [(f["id"], f["name"]) for f in people.list_families(conn)]
    inner = (
        ui.select_field("Kind", "kind", [(k, k) for k in CALENDAR_KINDS], selected=v("kind", "Service"),
                        error=errors.get("kind"))
        + ui.field("Title", "title", v("title", ""), error=errors.get("title"), autocomplete="off", lang="vi",
                   hint="For a Visit it may stay empty: it becomes “Visit” and the name.")
        + '<div class="inline-fields two">'
        + ui.field("Starts at", "starts_at", v("starts_at") or _start_value(req), type="datetime-local",
                   required=True, error=errors.get("starts_at"))
        + ui.field("Ends at", "ends_at", v("ends_at", ""), type="datetime-local", error=errors.get("ends_at"),
                   hint="Optional.")
        + "</div>"
        + ui.field("Place", "place", v("place", ""), autocomplete="off", lang="vi")
        + ui.textarea_field("Note", "note", v("note", ""), lang="vi", rows=2)
        + '<div class="inline-fields two">'
        + ui.select_field("Repeat", "repeat", REPEATS, selected=v("repeat", "none"), error=errors.get("repeat"))
        + ui.field("Repeat until", "repeat_until", v("repeat_until", ""), type="date",
                   error=errors.get("repeat_until"), hint="The last day, included.")
        + "</div>"
        + '<fieldset class="group"><legend>For a Visit only</legend><div class="inline-fields two">'
        + ui.select_field("Person", "person_id", persons, selected=v("person_id", ""), lang="vi",
                          error=errors.get("person_id"))
        + ui.select_field("Family", "family_id", families, selected=v("family_id", ""), lang="vi",
                          error=errors.get("family_id"))
        + '</div><p class="hint">A Visit is for one Person or one Family. It does not repeat.</p></fieldset>'
        + form_error(errors) + ui.button("Add to the Calendar")
    )
    body = f'<section class="panel narrow">{ui.form("/calendar/new", inner)}</section>'
    return Response.html(ui.page("Add a Calendar item", body, "calendar"), status)


def new_page(req):
    return _new_form(req)


def new_post(req):
    conn = req.conn
    f = req.form
    try:
        kind = f.get("kind") or ""
        if kind not in CALENDAR_KINDS:
            raise ValueError(f"Kind must be one of: {', '.join(CALENDAR_KINDS)}.")
        starts = form_datetime(f.get("starts_at"), "Starts at")
        if starts is None:
            raise ValueError("Starts at is required.")
        ends = form_datetime(f.get("ends_at"), "Ends at")
        if ends is not None and ends < starts:
            raise ValueError("Ends at cannot be before Starts at.")
        repeat = f.get("repeat") or "none"
        until = (f.get("repeat_until") or "").strip() or None
        person_id = f.get("person_id") or None
        family_id = f.get("family_id") or None
        if kind == "Visit":
            if repeat != "none" or until:
                raise ValueError("Repeat: a Visit does not repeat. Plan each Visit on its own.")
            with transaction(conn):
                iid = care.plan_visit(conn, starts, person_id=person_id, family_id=family_id,
                                      title=f.get("title"), note=f.get("note"))
                if ends is not None or (f.get("place") or "").strip():
                    cal.update_calendar_item(conn, iid, ends_at=ends, place=f.get("place"))
            ids = [iid]
        else:
            if person_id or family_id:
                raise ValueError("Person: a Person or a Family is only for a Visit. Choose kind Visit, "
                                 "or leave Person and Family empty.")
            ids = cal.add_calendar_item(conn, kind, f.get("title"), starts, ends, f.get("place"), f.get("note"),
                                        repeat, until)
    except ValueError as exc:
        return _new_form(req, f, ("new", str(exc)), 400)
    if len(ids) == 1:
        msg = f"{kind} added on {ui.fmt_datetime(starts)}."
    else:
        word = "week" if repeat == "weekly" else "month"
        msg = f"{len(ids)} Calendar items added: every {word} until {ui.fmt_date(until)}."
    return Response.redirect(ui.url(f"/calendar/{ids[0]}", msg=msg))


# ---------------------------------------------------------------- /calendar/<id>

def _details_panel(conn, row):
    iid = row["id"]
    rows = [("Kind", _kind(row["kind"])),
            ("Starts at", num(f"{ui.fmt_weekday(row['starts_at'])} {ui.fmt_datetime(row['starts_at'])}")),
            ("Ends at", num(ui.fmt_datetime(row["ends_at"])) if row["ends_at"] else ui.DASH),
            ("Place", vi(row["place"])),
            ("Note", vi(row["note"]))]
    if row["kind"] == "Visit":
        if row["visit_person_id"] is not None:
            who = person_link(row["visit_person_id"], people.get_person(conn, row["visit_person_id"])["full_name"])
        elif row["visit_family_id"] is not None:
            fam = conn.execute("SELECT name FROM family WHERE id = ?", (row["visit_family_id"],)).fetchone()
            who = family_link(row["visit_family_id"], fam["name"])
        else:
            who = ui.DASH
        rows.append(("For", who))
        if row["visit_done"]:
            rows.append(("Visit", f'Done on <span class="num">{h(ui.fmt_date(row["visit_done_date"]))}</span>'))
            rows.append(("Care note", vi(row["care_note"])))
        else:
            rows.append(("Visit", 'Not done yet.<span class="no-print"> <a href="/care">Mark it done in Care</a></span>'))
    if row["series_id"] is not None:
        series = cal.series_items(conn, row["series_id"])
        k = next(i for i, s in enumerate(series) if s["id"] == iid)
        links = []
        if k > 0:
            links.append(f'<a href="/calendar/{series[k - 1]["id"]}">‹ {h(ui.fmt_date(series[k - 1]["starts_at"]))}</a>')
        if k < len(series) - 1:
            links.append(f'<a href="/calendar/{series[k + 1]["id"]}">{h(ui.fmt_date(series[k + 1]["starts_at"]))} ›</a>')
        rows.append(("Repeat", f'<span class="num">{k + 1} of {len(series)}</span>, until '
                               f'<span class="num">{h(ui.fmt_date(series[-1]["starts_at"]))}</span>'
                               + (f'<br><span class="series-links">{" · ".join(links)}</span>' if links else "")))
    body = '<dl class="kv">' + "".join(f"<div><dt>{h(k)}</dt><dd>{v}</dd></div>" for k, v in rows) + "</dl>"
    return panel("details", "Details", body)


def _edit_panel(row, error, vals):
    errors = _errors(error, "edit")
    v = vals.get if errors else (lambda key, default="": {
        "kind": row["kind"], "title": row["title"], "starts_at": input_datetime(row["starts_at"]),
        "ends_at": input_datetime(row["ends_at"]), "place": row["place"] or "", "note": row["note"] or "",
    }.get(key, default))
    if row["kind"] == "Visit":
        kind_field = '<p class="hint">Kind: Visit. A Visit keeps its kind.</p>'
    else:
        kind_field = ui.select_field("Kind", "kind", [(k, k) for k in CALENDAR_KINDS if k != "Visit"],
                                     selected=v("kind", row["kind"]), id="edit-kind", error=errors.get("kind"))
    inner = (
        kind_field
        + ui.field("Title", "title", v("title", ""), id="edit-title", required=True, lang="vi", autocomplete="off",
                   error=errors.get("title"))
        + ui.field("Starts at", "starts_at", v("starts_at", ""), type="datetime-local", id="edit-starts",
                   required=True, error=errors.get("starts_at"))
        + ui.field("Ends at", "ends_at", v("ends_at", ""), type="datetime-local", id="edit-ends",
                   error=errors.get("ends_at"), hint="Optional.")
        + ui.field("Place", "place", v("place", ""), id="edit-place", lang="vi", autocomplete="off")
        + ui.textarea_field("Note", "note", v("note", ""), id="edit-note", lang="vi", rows=2)
        + form_error(errors) + ui.button("Save")
    )
    form = ui.form(f"/calendar/{row['id']}/edit", inner)
    hint = ('<p class="hint">Only this Calendar item changes, not the rest of its repeat.</p>'
            if row["series_id"] is not None else "")
    return panel("edit", "Edit", hint + change_box("Edit this Calendar item", form, bool(errors)))


def _people_panel(conn, row, error, vals, today):
    iid = row["id"]
    listed = cal.item_people(conn, iid)
    errors = field_errors(error, "people", {"person_id": "Person", "part": "Part"})
    past = row["starts_at"][:10] < today
    lines = "".join(
        '<li class="row" data-row>'
        f'<span class="what wrap">{clamp2(person_link(p["person_id"], p["full_name"]), p["full_name"])}</span>'
        f'{ui.row_side([h(PART_WORDS[p["part"]])], [PART_WORDS[p["part"]]])}'
        f'<form class="row-form" action="/calendar/{iid}/people/remove" method="post">'
        f'{ui.hidden("person_id", p["person_id"])}{ui.hidden("part", p["part"])}'
        f'<button class="link-btn" type="submit" aria-label="Remove {h(p["full_name"])} ({h(PART_WORDS[p["part"]])})">'
        "Remove</button></form></li>"
        for p in listed
    )
    body = f'<ul class="rows">{lines}</ul>' if listed else empty("No one is listed yet.")
    if past and listed:
        body += '<p class="hint">This Calendar item is in the past. Taking a Person off asks you first.</p>'
    persons = [("", "— Choose a Person —")] + [(p["id"], p["full_name"]) for p in people.list_persons(conn)]
    form = ui.form(f"/calendar/{iid}/people", (
        '<div class="add-person">'
        + ui.select_field("Person", "person_id", persons, selected=vals.get("person_id", ""), id="add-person",
                          lang="vi", error=errors.get("person_id"))
        + ui.select_field("Part", "part", [("serves", "Serves"), ("joins", "Joins")],
                          selected=vals.get("part", "serves"), id="add-part", error=errors.get("part"))
        + ui.button("Add", "secondary") + "</div>" + form_error(errors)))
    form = f'<div class="add-form">{form}</div>'
    serves = sum(1 for p in listed if p["part"] == "serves")
    meta = f"Serves {serves} · Joins {len(listed) - serves}"
    return panel("people", "People who serve or join", body + form, meta=meta)


def _head_count_panel(conn, row, error, vals, today):
    iid = row["id"]
    hc = cal.get_head_count(conn, iid)
    errors = field_errors(error, "head-count", {"count": "Head count", "absent_note": "Absent"})
    if hc is not None:
        absent = (f'<p class="absent" lang="vi">{h(hc["absent_note"])}</p>' if hc["absent_note"]
                  else '<p class="absent faint">No note about who was absent.</p>')
        current = (f'<div class="kpi" data-row><span class="kpi-label">Head count</span>'
                   f'<span class="kpi-value num">{hc["count"]}</span></div>{absent}')
    else:
        current = ""
    if row["starts_at"][:10] > today:
        form_html = empty("The Head count can be recorded on the day of the Service or after.")
        if errors:
            form_html += form_error({"": next(iter(errors.values()))})
    else:
        v = vals.get if errors else (lambda key, default="": (
            {"count": str(hc["count"]), "absent_note": hc["absent_note"] or ""} if hc else {}).get(key, default))
        form = ui.form(f"/calendar/{iid}/head-count", (
            '<div class="inline-fields">'
            + ui.field("Head count", "count", v("count", ""), type="number", id="hc-count", min="0", step="1",
                       required=True, error=errors.get("count"), hint="People at this Service.")
            + ui.textarea_field("Absent", "absent_note", v("absent_note", ""), id="hc-absent", lang="vi", rows=2,
                                hint="A note about who was absent. Optional.")
            + "</div>" + form_error(errors) + ui.button("Save Head count", "secondary")))
        form_html = change_box("Change Head count", form, bool(errors)) if hc else form
    if hc is None and row["starts_at"][:10] <= today and not errors:
        current = '<p class="hint">No Head count yet.</p>'
    return f'<div id="head-count">{panel("head-count", "Head count", current + form_html)}</div>'


def _delete_panel(conn, row, error):
    message = error[1] if error and error[0] == "delete" else None
    reason = message or cal.delete_refusal(conn, row["id"])  # a read only: no write lock on a page view
    if reason:
        body = f'<p class="{"error" if message else "hint"}" role="{"alert" if message else "note"}">{h(reason)}</p>'
    else:
        body = (ui.form(f"/calendar/{row['id']}/delete", ui.button("Delete this Calendar item", "danger"))
                + '<p class="hint">You are asked once more before it goes.</p>')
    return panel("delete", "Delete", body, cls="no-print")


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
    finding = [row["kind"], f"{ui.fmt_weekday(row['starts_at'])} {ui.fmt_date(row['starts_at'])}",
               time_span(row["starts_at"], row["ends_at"])]
    if row["place"]:
        finding.append(row["place"])
    if row["kind"] == "Service":
        hc = cal.get_head_count(conn, row["id"])
        finding.append(f"Head count {hc['count']}" if hc else "No Head count yet")
    week = ui.url("/calendar", week=row["starts_at"][:10])
    actions = ui.link_button("Back to the week", week)
    return Response.html(ui.page(row["title"], body, "calendar", sub=h(" · ".join(finding)), actions=actions,
                                 lang="vi"), status)


def _item_or_none(req):
    return cal.get_calendar_item(req.conn, req.params["id"])


def _missing():
    return not_found("Calendar item", "/calendar", "Go to the Calendar")


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
        return _item_view(req, cal.get_calendar_item(req.conn, row["id"]) or row, (key, str(exc)), 400)
    if isinstance(result, Response):
        return result
    return Response.redirect(ui.url(f"/calendar/{row['id']}", msg=result))


def edit_post(req):
    def do(conn, row):
        f = req.form
        starts = form_datetime(f.get("starts_at"), "Starts at")
        if starts is None:
            raise ValueError("Starts at is required.")
        ends = form_datetime(f.get("ends_at"), "Ends at")
        if ends is not None and ends < starts:
            raise ValueError("Ends at cannot be before Starts at.")
        if leaves_the_past(row["starts_at"], starts, cal.item_people(conn, row["id"]), today_text()):
            raise ValueError("Starts at: this Calendar item is in the past and people joined or served it. "
                             "It cannot move to today or later. Past links are history.")
        changes = {"title": f.get("title"), "starts_at": starts, "ends_at": ends, "place": f.get("place"),
                   "note": f.get("note")}
        if row["kind"] != "Visit":
            changes["kind"] = f.get("kind") or row["kind"]
        cal.update_calendar_item(conn, row["id"], **changes)
        return "Calendar item saved."
    return _change(req, "edit", do)


def people_post(req):
    def do(conn, row):
        if not req.form.get("person_id"):
            raise ValueError("Person: choose a Person.")
        part = req.form.get("part") or ""
        added = cal.add_person_to_item(conn, row["id"], req.form["person_id"], part)
        name = people.get_person(conn, req.form["person_id"])["full_name"]
        word = PART_WORDS.get(part, part).lower()
        return f"{name} {word}." if added else f"{name} already {word}. Nothing changed."
    return _change(req, "people", do)


def _confirm_page(title, question, action, fields, button_text, back_href):
    inner = "".join(ui.hidden(k, v) for k, v in fields.items()) + ui.hidden("confirm", "yes")
    form = ui.form(action, inner + ui.button(button_text, "danger"))
    body = (f'<section class="panel narrow" data-panel="confirm"><p class="lead">{question}</p>'
            f'<div class="confirm-actions">{form}{ui.link_button("Cancel", back_href)}</div></section>')
    return Response.html(ui.page(title, body, "calendar"))


def _when(row):
    return f"{ui.fmt_weekday(row['starts_at'])} {ui.fmt_datetime(row['starts_at'])}"


def remove_person_post(req):
    def do(conn, row):
        f = req.form
        person = people.get_person(conn, f.get("person_id") or "0")
        part = f.get("part") or ""
        if person is None or part not in PART_WORDS:
            raise ValueError("Person: this Person is not listed here.")
        past = row["starts_at"][:10] < today_text()
        if past and f.get("confirm") != "yes":
            question = (f"Are you sure? Take <strong lang=\"vi\">{h(person['full_name'])}</strong> "
                        f"({h(PART_WORDS[part])}) off <strong lang=\"vi\">{h(row['title'])}</strong> on "
                        f"<span class=\"num\">{h(_when(row))}</span>? This Calendar item is in the past, "
                        "so it leaves this Person's story.")
            return _confirm_page("Are you sure?", question, f"/calendar/{row['id']}/people/remove",
                                 {"person_id": person["id"], "part": part}, "Yes, take this Person off",
                                 f"/calendar/{row['id']}")
        removed = cal.remove_person_from_item(conn, row["id"], person["id"], part)
        if not removed:
            return f"{person['full_name']} was not listed. Nothing changed."
        return f"{person['full_name']} is no longer listed ({PART_WORDS[part]})."
    return _change(req, "people", do)


def head_count_post(req):
    def do(conn, row):
        if row["kind"] != "Service":
            raise ValueError("Head count: a Head count is only for a Service.")
        if row["starts_at"][:10] > today_text():
            raise ValueError("Head count: this Service has not happened yet. Record it on the day or after.")
        count = parse_head_count(req.form.get("count"))
        cal.set_head_count(conn, row["id"], count, req.form.get("absent_note"))
        return f"Head count {count} saved."
    return _change(req, "head-count", do)


def delete_post(req):
    def do(conn, row):
        if req.form.get("confirm") != "yes":
            reason = cal.delete_refusal(conn, row["id"])
            if reason:
                raise ValueError(reason)
            question = (f"Delete <strong lang=\"vi\">{h(row['title'])}</strong> ({h(row['kind'])}) on "
                        f"<span class=\"num\">{h(_when(row))}</span>? This cannot be undone.")
            return _confirm_page("Delete this Calendar item?", question, f"/calendar/{row['id']}/delete", {},
                                 "Yes, delete it", f"/calendar/{row['id']}")
        cal.delete_calendar_item(conn, row["id"])
        msg = f"Deleted {row['title']} ({ui.fmt_datetime(row['starts_at'])})."
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
