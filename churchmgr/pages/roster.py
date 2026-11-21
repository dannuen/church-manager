"""The Service role pages of the Roster (goal "Service role Roster", decision D6).

Card RO-4: the Service roles panel of a Service page ``/calendar/<id>`` (``#service-roles``) and its two
forms: ``POST /calendar/<id>/roles`` (pick or swap a name: ``roster.set_link``) and
``POST /calendar/<id>/roles/clear`` (``roster.clear_link``). Both go back to the panel (POST-redirect-GET);
a refused form shows the Service page again (400) with the sentence in the panel.

Card RO-5: the Roster ``/calendar/roster?quarter=YYYY-Q`` (the pastor's quarter list: one table per month,
one row per ISO week; a week belongs to the month of its Sunday) and Auto-fill: the preview
``GET /calendar/roster/fill?from=&to=`` (``roster.fill_plan``, never writes) and Save
``POST /calendar/roster/fill`` (``roster.save_fill``, then back to the Roster with "N filled").

Rules kept here:
- Rule 4: a link changes only through ``roster.set_link`` and ``roster.clear_link``. The old names stay,
  struck, with their dates.
- Clear on a past Service asks "Are you sure?" first, like taking a Person off a past Calendar item.
- A save that breaks the same-person rule is saved. The panel then shows a warning line from
  ``roster.conflicts``. It comes from the saved links, so it stays until the names are changed.
- No Private note text: nothing here reads the ``private_note`` table.
- Words on screen come from the text table (section ``calendar``, prefix ``calendar.roster_``). Service role,
  Person and Ministry names and the reason of a Skipped date are data: shown as stored.
"""

import datetime as _dt
import re

from .. import i18n, lists, roster, text, ui
from ..calendar import month_days
from ..i18n import TextError, t, tn
from ..server import Response
from ..ui import clamp2, h, vi
from . import calendar as cal_pages  # a module import: pages/calendar.py imports this module in _item_view
from .people import empty, form_error, num, panel, person_link, today_text

FORM = "service-roles"  # the form key of a refused change, and the id of the panel
QUARTER = re.compile(r"([0-9]{4})-([1-4])")
FIRST_YEAR, LAST_YEAR = 1900, 9999  # the years of a Roster quarter, as a Calendar month
ARROW = "\u00a0\u2192 "  # between the names of a swap; the no-break space keeps the arrow after its name


# ---------------------------------------------------------------- the panel

def _value(link):
    """The name of an open link: a link to the Person page, or the Ministry name."""
    if link["person_id"] is not None:
        return person_link(link["person_id"], link["name"])
    return vi(link["name"])


def _names(conn, iid, role, mine):
    """The open name (or the empty word), the closed ones struck with their dates (newest first), and a
    warning line for each other Service role the open Person holds against the same-person rule."""
    held = next((link for link in mine if link["end_date"] is None), None)
    if held is None:
        out = f'<p class="faint">{h(t("calendar.roster_empty"))}</p>'
    else:
        since = t("calendar.roster_since", date=ui.fmt_date(held["start_date"]))
        out = f'<p>{_value(held)} <span class="hint">· {h(since)}</span></p>'
    old = sorted((link for link in mine if link["end_date"] is not None), key=lambda link: link["id"],
                 reverse=True)
    if old:
        lines = (f'<s lang="vi">{h(link["name"])}</s> · '
                 + h(t("calendar.roster_from_to", start=ui.fmt_date(link["start_date"]),
                       end=ui.fmt_date(link["end_date"])))
                 for link in old)
        out += f'<p class="hint">{"<br>".join(lines)}</p>'
    if held is not None and held["person_id"] is not None:
        for other, day in roster.conflicts(conn, iid, role["id"], held["person_id"]):
            out += ('<p class="hint" role="note">'
                    + ui.t_html("calendar.roster_conflict", name=vi(held["name"]), role=vi(other),
                                date=num(ui.fmt_date(day)))
                    + "</p>")
    return out, held


def _choices(conn, role, held, persons):
    """The options of the select: every Person (the Calendar page's select), or the shown Ministries. A
    hidden Ministry that holds the role now is added, so Save keeps it."""
    if role["done_by"] == "person":
        return persons()
    options = [("", t("calendar.roster_choose_ministry"))] + [(m["id"], m["name"])
                                                              for m in lists.get_list(conn, "ministry")]
    if held is not None and held["ministry_id"] not in {value for value, _name in options}:
        options.append((held["ministry_id"], held["name"]))
    return options


def _forms(conn, iid, role, held, message, vals, persons):
    """Pick or swap (a select and Save) and Clear. A hidden Service role takes no new name: only Clear."""
    clear_label = t("calendar.roster_clear_label", role=role["name"])
    if not role["active"]:
        out = f'<p class="hint">{h(t("calendar.roster_hidden"))}</p>' + form_error({"": message})
        if held is not None:
            out += ui.form(f"/calendar/{iid}/roles/clear", ui.hidden("role_id", role["id"])
                           + ui.button(t("calendar.roster_clear"), "secondary", aria_label=clear_label))
        return out
    field = "person_id" if role["done_by"] == "person" else "ministry_id"
    label = t("calendar.person" if field == "person_id" else "calendar.roster_ministry")
    selected = vals.get(field, "") if message else (held[field] if held is not None else "")
    clear = "" if held is None else ui.button(t("calendar.roster_clear"), "secondary", aria_label=clear_label,
                                              formaction=f"/calendar/{iid}/roles/clear", formnovalidate=True)
    return ui.form(f"/calendar/{iid}/roles", (
        ui.hidden("role_id", role["id"]) + '<div class="add-person">'
        + ui.select_field(label, field, _choices(conn, role, held, persons), selected=selected,
                          id=f"role-{role['id']}", lang="vi", required=True, error=message)
        + ui.button(t("core.btn_save"), "secondary") + clear + "</div>"))


def service_roles_panel(conn, row, error=None, vals=None):
    """The Service roles panel of a Service (``row``: its Calendar item). One part per shown Service role of
    the Service's weekday and per Service role with a link on this Service (a hidden one too: its history
    stays); a hidden Service role with no link is not shown. ``error``: ``(form key, exception)`` of a refused
    form (key :data:`FORM`), shown under the select of its Service role (or at the top); ``vals``: that form."""
    vals = vals or {}
    iid = row["id"]
    message = i18n.error_text(error[1]) if error and error[0] == FORM else None
    links = roster.item_links(conn, iid)
    linked = {link["service_role_id"] for link in links}
    weekday = _dt.date.fromisoformat(row["starts_at"][:10]).weekday()
    shown = [r for r in roster.roles(conn, include_hidden=True)
             if r["id"] in linked or (r["active"] and r["weekday"] == weekday)]
    posted = str(vals.get("role_id", "")).strip()
    at_role = message is not None and posted in {str(r["id"]) for r in shown}
    cache = []

    def persons():  # read once per panel, only when a Service role done by a Person needs it
        if not cache:
            cache.append(cal_pages._persons(conn))
        return cache[0]

    body = ""
    reason = roster.skipped_reason(conn, row["starts_at"][:10])  # at the top: the line under the panel title
    meta = ui.t_html("calendar.roster_skipped", reason=f'<strong lang="vi">{h(reason)}</strong>') if reason else ""
    if message and not at_role:
        body += form_error({"": message})
    parts = []
    for role in shown:
        names, held = _names(conn, iid, role, [link for link in links if link["service_role_id"] == role["id"]])
        role_error = message if at_role and posted == str(role["id"]) else None
        parts.append(f'<div data-row data-role="{role["id"]}"><dt lang="vi">{h(role["name"])}</dt>'
                     f'<dd>{names}{_forms(conn, iid, role, held, role_error, vals, persons)}</dd></div>')
    body += f'<dl class="kv wide">{"".join(parts)}</dl>' if parts else empty(t("calendar.roster_none"))
    return f'<div id="{FORM}">{panel(FORM, t("calendar.roster_panel"), body, meta=meta)}</div>'


# ---------------------------------------------------------------- the forms

def _back(row, msg):
    """Back to the panel of the Service, with the flash text ``msg``."""
    return Response.redirect(ui.url(f"/calendar/{row['id']}", msg=msg) + f"#{FORM}")


def _refuse_not_service(req):
    """A Calendar item that is not a Service has no panel to show the sentence in: the plain 400 page."""
    row = cal_pages._item_or_none(req)
    if row is not None and row["kind"] != "Service":
        raise TextError("calendar.roster_err_not_service")


def roles_post(req):
    _refuse_not_service(req)

    def do(conn, row):
        f = req.form
        changed = roster.set_link(conn, row["id"], f.get("role_id") or "", person_id=f.get("person_id"),
                                  ministry_id=f.get("ministry_id"))
        role = roster.get_role(conn, f["role_id"])
        held = roster.open_value(conn, row["id"], role["id"])
        key = "calendar.roster_saved" if changed else "calendar.roster_unchanged"
        return _back(row, t(key, name=held["name"], role=role["name"]))
    return cal_pages._change(req, FORM, do)


def roles_clear_post(req):
    _refuse_not_service(req)

    def do(conn, row):
        rid = text.to_id(req.form.get("role_id") or "", "calendar.roster_role")
        role = roster.get_role(conn, rid)
        if role is None:
            raise TextError("calendar.roster_err_no_role", id=rid)
        if roster.open_value(conn, row["id"], rid) is None:
            return _back(row, t("calendar.roster_not_open", role=role["name"]))
        if row["starts_at"][:10] < today_text() and req.form.get("confirm") != "yes":
            question = ui.t_html("calendar.roster_clear_question",
                                 role=f'<strong lang="vi">{h(role["name"])}</strong>',
                                 title=f'<strong lang="vi">{h(row["title"])}</strong>',
                                 when=num(cal_pages._when(row)))
            return cal_pages._confirm_page(t("calendar.sure"), question, f"/calendar/{row['id']}/roles/clear",
                                           {"role_id": rid}, t("calendar.roster_clear_yes"),
                                           f"/calendar/{row['id']}#{FORM}")
        cleared = roster.clear_link(conn, row["id"], rid)
        key = "calendar.roster_cleared" if cleared else "calendar.roster_not_open"
        return _back(row, t(key, role=role["name"]))
    return cal_pages._change(req, FORM, do)


# ---------------------------------------------------------------- quarters (small logic, tested)

def week_month(monday):
    """``(year, month)`` of the Roster week that starts on ``monday``: the month of its Sunday (the last
    week of 9999 has no Sunday: December 9999)."""
    sunday = roster._plus_days(monday, 6) or _dt.date.max
    return sunday.year, sunday.month


def quarter_of(day):
    """The quarter ``(year, q)`` whose Roster holds the week of ``day``."""
    year, month = week_month(day - _dt.timedelta(days=day.weekday()))
    return year, (month - 1) // 3 + 1


def parse_quarter(value, today):
    """``?quarter=2026-4`` -> ``(2026, 4)``; empty -> the quarter of this week. Anything else raises
    ``TextError``: the form sentence, or the years sentence for a year outside 1900 to 9999."""
    raw = (value or "").strip()
    if not raw:
        return quarter_of(today)
    found = QUARTER.fullmatch(raw)
    if found is None:
        raise TextError("calendar.roster_err_quarter")
    year, q = int(found.group(1)), int(found.group(2))
    if not FIRST_YEAR <= year <= LAST_YEAR:
        raise TextError("calendar.roster_err_quarter_years")
    return year, q


def quarter_text(year, q):
    """``(2026, 4)`` -> ``"2026-4"`` (the ``?quarter=`` value)."""
    return f"{year:04d}-{q}"


def quarter_step(year, q, k):
    """The quarter ``k`` quarters from ``(year, q)``, or ``None`` outside 1900 to 9999 (no chip goes there)."""
    to_year, index = divmod(year * 4 + q - 1 + k, 4)
    return (to_year, index + 1) if FIRST_YEAR <= to_year <= LAST_YEAR else None


def quarter_dates(year, q):
    """The first and the last date of the Roster of a quarter: the Monday of the week of its first Sunday,
    and its last Sunday (a week belongs to the month of its Sunday)."""
    start = _dt.date(year, 3 * q - 2, 1)
    end = _dt.date(year, 3 * q, month_days(year, 3 * q))
    first_sunday = start + _dt.timedelta(days=6 - start.weekday())
    return first_sunday - _dt.timedelta(days=6), end - _dt.timedelta(days=(end.weekday() + 1) % 7)


def fill_dates(first, last, today):
    """The Auto-fill dates of a Roster from ``first`` to ``last``: from today on when today is in it (a past
    Service is not filled by itself), else all of it."""
    return (max(first, today) if first <= today <= last else first), last


# ---------------------------------------------------------------- the Roster table

def _columns(conn):
    """The columns of the Roster: ``[(weekday, [Service roles done by a Person])]`` for each weekday with a
    shown Service role, Monday first, and the shown Service roles done by a Ministry (the Notes column)."""
    days, ministry = {}, []
    for role in roster.roles(conn):
        persons = days.setdefault(role["weekday"], [])
        (persons if role["done_by"] == "person" else ministry).append(role)
    return sorted(days.items()), ministry


def _when_text(link):
    since = ui.fmt_date(link["start_date"])
    if link["end_date"] is None:
        return t("calendar.roster_since", date=since)
    return t("calendar.roster_from_to", start=since, end=ui.fmt_date(link["end_date"]))


def _cell_names(links, bold=False, new=None):
    """One cell as the pastor writes it: each closed name struck, then → and the open name (bold when
    ``bold``); its dates in the ``title``. ``new``: the name Auto-fill would add (the preview), marked."""
    parts, lines = [], []
    for link in links:  # oldest first
        name = h(link["name"])
        if link["end_date"] is not None:
            parts.append(f'<s lang="vi">{name}</s>')
        else:
            parts.append(f'<strong lang="vi">{name}</strong>' if bold else f'<span lang="vi">{name}</span>')
        lines.append(f'{link["name"]} · {_when_text(link)}')
    if new is not None:
        mark = f'<ins class="roster-new" lang="vi">{h(new)}</ins>'
        parts.append(f"<strong>{mark}</strong>" if bold else mark)
    if not parts:
        return ""
    title = f' title="{h(chr(10).join(lines))}"' if lines else ""
    return f'<span class="roster-names"{title}>{ARROW.join(parts)}</span>'


def _date_cell(day, this_week):
    """The date of one weekday: ``dd/mm`` linked to the Service roles of its Service; a Skipped date with no
    Service shows its date only; no Service: empty. More Services that day: their times under it."""
    if day is None or (day["service"] is None and day["skipped"] is None):
        out = ""
    elif day["service"] is None:
        out = num(day["date"].strftime("%d/%m"))
    else:
        out = f'<a href="/calendar/{day["service"]}#{FORM}">{num(day["date"].strftime("%d/%m"))}</a>'
        for iid, starts_at in day["others"]:
            also = t("calendar.roster_also", time=ui.fmt_time(starts_at))
            out += (f'<span class="cell-sub"><a href="/calendar/{iid}#{FORM}" title="{h(also)}" aria-label="{h(also)}">'
                    f'{num(ui.fmt_time(starts_at))}</a></span>')
    if this_week:
        out += f'<span class="today-tag no-print">{h(t("calendar.this_week"))}</span>'
    return out


def _cell_value(day, role, new):
    """The names of one Service role in one day's Service (``new``: ``{(item id, role id): name}``)."""
    if day is None or day["service"] is None:
        return ""
    bold = bool(role["month_start"]) and day["month_first"]
    return _cell_names(day["links"].get(role["id"], []), bold, new.get((day["service"], role["id"])))


def _row(week, columns, ministry, new, today):
    """One week: per weekday its date and its Service roles done by a Person, then Notes. A Skipped date's
    reason is bold in the first Service role cell of its weekday (in the date cell when that weekday has only
    a Ministry role)."""
    this_week = week["monday"] <= today <= week["monday"] + _dt.timedelta(days=6)
    cells = []
    for k, (weekday, persons) in enumerate(columns):
        day = week["days"].get(weekday)
        reason = f'<strong lang="vi">{h(day["skipped"])}</strong>' if day and day["skipped"] else ""
        date_html = _date_cell(day, this_week and k == 0)
        if reason and not persons:
            date_html += f"<br>{reason}"
        cells.append(f'<td class="roster-date">{date_html}</td>')
        for n, role in enumerate(persons):
            value = _cell_value(day, role, new)
            if reason and n == 0:
                value = reason + (f"<br>{value}" if value else "")
            cells.append(f"<td>{value}</td>")
    notes = [_cell_value(week["days"].get(role["weekday"]), role, new) for role in ministry]
    cells.append(f'<td>{"<br>".join(v for v in notes if v)}</td>')
    return f"<tr>{''.join(cells)}</tr>"


def _month_panel(year, month, title, weeks, columns, ministry, new, today):
    name = f"roster-{year:04d}-{month:02d}"
    head = []
    for weekday, persons in columns:
        head.append(f'<th scope="col" class="roster-date">{h(t(f"core.weekday_{weekday}"))}</th>')
        head += [f'<th scope="col" lang="vi">{h(role["name"])}</th>' for role in persons]
    head.append(f'<th scope="col">{h(t("calendar.roster_notes"))}</th>')
    rows = "".join(_row(week, columns, ministry, new, today) for week in weeks)
    table = (f'<div class="table-wrap"><table class="roster-table" aria-labelledby="p-{name}">'
             f'<thead><tr>{"".join(head)}</tr></thead><tbody>{rows}</tbody></table></div>')
    return panel(name, title, table, cls="roster-month")


def _months(conn, first, last, today, new=None, quarter=None):
    """The month cards of the Roster from ``first`` to ``last``. ``quarter``: its 3 months, titled
    "Tháng m" (the year is in the page line); otherwise each month that has a week, with its year."""
    columns, ministry = _columns(conn)
    if not columns:
        return empty(t("calendar.roster_no_roles"))
    by_month = {}
    for week in roster.roster_weeks(conn, first, last):
        by_month.setdefault(week_month(week["monday"]), []).append(week)
    if quarter is not None:
        months = [(quarter[0], 3 * quarter[1] - 2 + k, t(f"core.month_{3 * quarter[1] - 2 + k}")) for k in range(3)]
    else:
        months = [(y, m, ui.fmt_month(y, m)) for y, m in by_month]
    return '<div class="stack roster">' + "".join(
        _month_panel(y, m, title, by_month.get((y, m), []), columns, ministry, new or {}, today)
        for y, m, title in months) + "</div>"


# ---------------------------------------------------------------- /calendar/roster

def _quarter_chip(label, quarter, current=False):
    if quarter is None:
        return ""
    mark = ' aria-current="true"' if current else ""
    href = ui.url("/calendar/roster", quarter=quarter_text(*quarter))
    return f'<a class="chip" href="{h(href)}"{mark}>{h(label)}</a>'


def _quarter_bar(year, q, today):
    """Prev / This / Next quarter, one line (the Calendar period bar)."""
    def label(quarter):
        return "" if quarter is None else t("calendar.roster_quarter", q=quarter[1], year=quarter[0])

    prev, this, next_ = quarter_step(year, q, -1), quarter_of(today), quarter_step(year, q, 1)
    period = (_quarter_chip(f"‹ {label(prev)}", prev) + _quarter_chip(t("calendar.roster_this_quarter"), this,
                                                                        this == (year, q))
              + _quarter_chip(f"{label(next_)} ›", next_))
    return (f'<nav class="list-toolbar" aria-label="{h(t("calendar.roster_chips"))}">'
            f'<div class="period">{period}</div></nav>')


def _fill_href(first, last):
    return ui.url("/calendar/roster/fill", **{"from": first.isoformat(), "to": last.isoformat()})


def roster_page(req):
    conn = req.conn
    today = _dt.date.today()
    year, q = parse_quarter(req.query.get("quarter"), today)
    first, last = quarter_dates(year, q)
    body = _quarter_bar(year, q, today) + _months(conn, first, last, today, quarter=(year, q))
    actions = (f'<button class="btn secondary" type="button" data-print>{h(t("core.btn_print"))}</button>'
               + ui.link_button(t("calendar.roster_fill"), _fill_href(*fill_dates(first, last, today)), "primary"))
    return Response.html(ui.page(t("calendar.roster_title"), body, "calendar",
                                 sub=h(t("calendar.roster_quarter", q=q, year=year)), actions=actions))


# ---------------------------------------------------------------- /calendar/roster/fill

def _fill_range(query, today):
    """The dates of the preview: ``?from=&to=``; both empty: :func:`fill_dates` of the Roster of
    ``?quarter=`` (empty: this one). Checked again by ``roster.fill_plan`` (order, length)."""
    raw_from, raw_to = (query.get("from") or "").strip(), (query.get("to") or "").strip()
    if not raw_from and not raw_to:
        year, q = parse_quarter(query.get("quarter"), today)
        return fill_dates(*quarter_dates(year, q), today)
    return (_dt.date.fromisoformat(text.check_date(raw_from, "calendar.start_date")),
            _dt.date.fromisoformat(text.check_date(raw_to, "calendar.end_date")))


def _new_names(conn, proposals):
    """``{(item id, role id): name}`` of the proposals of a plan."""
    persons = {p for _i, _r, p, _m in proposals if p is not None}
    ministries = {m for _i, _r, _p, m in proposals if m is not None}
    names = {}
    for table, column, ids in (("person", "full_name", persons), ("list_item", "name", ministries)):
        if ids:
            marks = ", ".join("?" * len(ids))
            names[table] = {r[0]: r[1] for r in conn.execute(
                f"SELECT id, {column} FROM {table} WHERE id IN ({marks})", sorted(ids))}
    return {(iid, rid): names["person"][p] if p is not None else names["list_item"][m]
            for iid, rid, p, m in proposals}


def _nobody_panel(conn, slots):
    """The Services where nobody in the Rotation was free: date and Service role, each to its Service."""
    rows = []
    for iid, rid in slots:
        item = conn.execute("SELECT starts_at FROM calendar_item WHERE id = ?", (iid,)).fetchone()
        role = roster.get_role(conn, rid)
        when = f"{ui.fmt_weekday(item['starts_at'])} {ui.fmt_date(item['starts_at'])}"
        link = f'<a href="/calendar/{iid}#{FORM}">{num(when)}</a>'
        rows.append(f'<li class="row" data-row><span class="what wrap">{clamp2(link, when)}</span>'
                    f'{ui.row_side([vi(role["name"])], [role["name"]])}</li>')
    return panel("nobody-free", t("calendar.roster_nobody_free"), f'<ul class="rows">{"".join(rows)}</ul>',
                 meta=h(t("calendar.roster_nobody_free_meta")))


def fill_page(req):
    conn = req.conn
    today = _dt.date.today()
    first, last = _fill_range(req.query, today)
    plan = roster.fill_plan(conn, first, last)  # reads only; refuses a range in the wrong order or too long
    count = len(plan["proposals"])
    span = f"{ui.fmt_date(first)} – {ui.fmt_date(last)}"
    summary = (f'<p>{h(tn("calendar.roster_new", count))}</p>'
               f'<p class="hint">{h(t("calendar.roster_fill_hint"))}</p>')
    no_rotation = [r["name"] for r in roster.roles(conn) if not roster.rotation(conn, r["id"])]
    if no_rotation:
        summary += f'<p class="hint">{ui.t_html("calendar.roster_no_rotation", roles=vi(", ".join(no_rotation)))}</p>'
    if count:
        summary += (f'<p class="hint"><ins class="roster-new">{h(t("calendar.roster_new_legend"))}</ins></p>'
                    + ui.form("/calendar/roster/fill", ui.hidden("from", first.isoformat())
                              + ui.hidden("to", last.isoformat()) + ui.button(t("calendar.roster_save_fill"))))
    else:
        summary += empty(t("calendar.roster_nothing_to_fill"))
    dates = ui.form("/calendar/roster/fill", (
        ui.field(t("calendar.start_date"), "from", first.isoformat(), type="date", id="fill-from", required=True)
        + ui.field(t("calendar.end_date"), "to", last.isoformat(), type="date", id="fill-to", required=True)
        + ui.button(t("calendar.roster_preview"), "secondary")), method="get")
    side = panel("fill-dates", t("calendar.roster_fill_range"), dates, cls="no-print")
    if plan["nobody_free"]:
        side += _nobody_panel(conn, plan["nobody_free"])
    body = (f'<div class="grid calendar"><div class="span-8 stack">'
            f'{panel("fill-summary", t("calendar.roster_fill"), summary, meta=num(span))}</div>'
            f'<div class="side-4 stack">{side}</div></div>')
    body += _months(conn, first, last, today, new=_new_names(conn, plan["proposals"]))
    back = ui.link_button(t("calendar.roster_title"),
                          ui.url("/calendar/roster", quarter=quarter_text(*quarter_of(first))))
    sub = h(f"{span} · {tn('calendar.roster_new', count)}")
    return Response.html(ui.page(t("calendar.roster_fill"), body, "calendar", sub=sub, actions=back))


def fill_post(req):
    """Save the Auto-fill of ``from`` to ``to`` (made again, in one transaction), then the Roster of the
    quarter of ``from`` with "N filled". A bad date: the 400 page, nothing saved."""
    first = text.check_date(req.form.get("from") or "", "calendar.start_date")
    last = text.check_date(req.form.get("to") or "", "calendar.end_date")
    count = roster.save_fill(req.conn, first, last)
    quarter = quarter_text(*quarter_of(_dt.date.fromisoformat(first)))
    return Response.redirect(ui.url("/calendar/roster", quarter=quarter, msg=tn("calendar.roster_filled", count)))


ROUTES = [
    ("GET", "/calendar/roster", roster_page),
    ("GET", "/calendar/roster/fill", fill_page),
    ("POST", "/calendar/roster/fill", fill_post),
    ("POST", "/calendar/<int:id>/roles", roles_post),
    ("POST", "/calendar/<int:id>/roles/clear", roles_clear_post),
]
