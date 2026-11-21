"""The Service role pages of the Roster (goal "Service role Roster", decision D6).

Card RO-4: the Service roles panel of a Service page ``/calendar/<id>`` (``#service-roles``) and its two
forms: ``POST /calendar/<id>/roles`` (pick or swap a name: ``roster.set_link``) and
``POST /calendar/<id>/roles/clear`` (``roster.clear_link``). Both go back to the panel (POST-redirect-GET);
a refused form shows the Service page again (400) with the sentence in the panel.

Card RO-5: the Roster ``/calendar/roster?quarter=YYYY-Q`` (the pastor's quarter list: one table per month,
one row per ISO week; a week belongs to the month of its Sunday) and Auto-fill: the preview
``GET /calendar/roster/fill?from=&to=`` (``roster.fill_plan``, never writes) and Save
``POST /calendar/roster/fill`` (``roster.save_fill``, then back to the Roster with "N filled").

Card RO-6: the Roster setup ``/calendar/roster/setup`` (the Service roles, the Skipped dates of this year and
next, the same-person rule) and the page of one Service role ``/calendar/roster/roles/<id>`` (its Rotation and
its edit form). Every form goes back to its page (POST-redirect-GET); a refused one shows the page again (400)
with the sentence under its field (or at the top of its form) and saves nothing. The data changes only through
``roster.*``. Done by is chosen once, when a Service role is added; the weekday stays once the Service role is on
the Roster (``roster.role_has_links``).

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

from .. import i18n, lists, people, roster, text, ui
from ..calendar import month_days
from ..i18n import TextError, t, tn
from ..server import Response
from ..ui import clamp2, h, vi
from . import calendar as cal_pages  # a module import: pages/calendar.py imports this module in _item_view
from .people import empty, form_error, not_found, num, panel, person_link, table, today_text

FORM = "service-roles"  # the form key of a refused change, and the id of the panel
SETUP = "/calendar/roster/setup"  # the Roster setup (card RO-6)
ROLES = "/calendar/roster/roles"  # the page of one Service role: ROLES/<id>
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
               + ui.link_button(t("calendar.roster_setup_link"), SETUP)
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


# ---------------------------------------------------------------- the setup: small logic (card RO-6, tested)

# Where a refused form shows its sentence: field -> the error keys and the field labels that belong to it.
ROLE_PLACES = {
    "name": ("calendar.roster_role_name", "calendar.roster_err_name_taken"),
    "weekday": ("calendar.roster_err_weekday", "calendar.roster_err_weekday_kept"),
    "done_by": ("calendar.roster_err_done_by",),
    "every": ("calendar.roster_err_every",),
    "month_start": ("calendar.roster_month_start",),
    "month_start_from": ("calendar.err_month_form", "calendar.err_month_years"),
}
SKIPPED_PLACES = {"date": ("calendar.roster_skipped_date",), "reason": ("calendar.roster_reason",)}


def placed(exc, places):
    """``{field: sentence}`` of a refused form: the field of ``places`` that ``exc`` names by its key or by its
    ``label``, else ``""`` (the top of the form). The sentence is in the language of the page."""
    key = getattr(exc, "key", None)
    label = (getattr(exc, "params", None) or {}).get("label")
    field = next((name for name, marks in places.items() if key in marks or label in marks), "")
    return {field: i18n.error_text(exc)}


def rotation_order(ids, value, action):
    """The new order of a Rotation (a list of ids) after ``action`` on ``value``: ``add`` (at the end; a repeat is
    refused by ``roster.set_rotation``), ``up`` or ``down`` (one place; the first one up or the last one down: no
    change) or ``remove``. A ``value`` that is not in the Rotation: ``TextError``."""
    if action == "add":
        return [*ids, value]
    if value not in ids:
        raise TextError("calendar.roster_err_not_in_rotation")
    k, out = ids.index(value), list(ids)
    if action == "remove":
        del out[k]
    elif action == "up" and k > 0:
        out[k - 1], out[k] = out[k], out[k - 1]
    elif action == "down" and k < len(out) - 1:
        out[k], out[k + 1] = out[k + 1], out[k]
    return out


# ---------------------------------------------------------------- the setup: parts of the pages

def _errors(error, form_key, places, fields):
    """``{field: sentence}`` of ``error`` (``(form key, exception)``) for the form ``form_key``, or ``{}``. A
    sentence whose field the form does not show goes to the top of the form (``""``)."""
    if not error or error[0] != form_key:
        return {}
    (field, sentence), = placed(error[1], places).items()
    return {field if field in fields else "": sentence}


def _anchored(name, title, body, meta=""):
    """A panel inside ``<div id=name>``: a form goes back to it (``#name``)."""
    return f'<div id="{name}">{panel(name, title, body, meta=meta)}</div>'


def _weekday_name(day):
    return t(f"calendar.roster_weekday_{day}")


def _done_by_text(role):
    return t(f"calendar.roster_by_{role['done_by']}")


def _month_start_text(role):
    """``New round each month, from 01/2027`` (empty: no month start)."""
    if not role["month_start"]:
        return ""
    month = role["month_start_from"]
    if month:
        return t("calendar.roster_month_round_from", month=f"{month[5:7]}/{month[:4]}")
    return t("calendar.roster_month_round")


def _places_text(role, n):
    """``6 People``, ``3 Ministries``, or ``No Rotation yet``."""
    return tn(f"calendar.roster_places_{role['done_by']}", n) if n else t("calendar.roster_no_places")


def _on(value):
    """A checkbox: not sent is off, ``1`` is on; anything else goes to ``roster`` as it is (refused there)."""
    return False if value is None else True if value == "1" else value


def _choice(kind, name, value, fid, label, hint, checked=False, error=None):
    """A radio button or a checkbox (``kind``) with its label on its right and one plain sentence under the
    label (``.choice`` in style.css)."""
    described = f"{fid}-hint" + (f" {fid}-error" if error else "")
    marks = (' aria-invalid="true"' if error else "") + (" checked" if checked else "")
    error_html = f'<p class="error" id="{fid}-error">{h(error)}</p>' if error else ""
    return (f'<div class="choice"><input type="{kind}" id="{fid}" name="{h(name)}" value="{h(value)}" '
            f'aria-describedby="{described}"{marks}><label for="{fid}">{h(label)}</label>'
            f'<p class="hint" id="{fid}-hint">{h(hint)}</p>{error_html}</div>')


def _toggle_form(role):
    """Hide or Show of one Service role: a plain word in the app color, as on the Lists page."""
    toggle = "show" if not role["active"] else "hide"
    label = t(f"calendar.roster_{toggle}_aria", name=role["name"])
    return (f'<form class="row-form" action="{ROLES}/{role["id"]}/{toggle}" method="post">'
            f'<button class="link-btn" type="submit" aria-label="{h(label)}">{h(t(f"calendar.roster_{toggle}"))}'
            "</button></form>")


def _role_fields(fid, vals, errors, locked=False, add=False):
    """The fields of the add form (``add``: with Done by) or of the edit form, by field name. ``locked``: no
    weekday field (the Service role is on the Roster). ``vals``: the texts to show."""
    fields = {"name": ui.field(t("calendar.roster_role_name"), "name", vals.get("name", ""), id=f"{fid}-name",
                               required=True, autocomplete="off", lang="vi", error=errors.get("name"))}
    if not locked:
        fields["weekday"] = ui.select_field(t("calendar.roster_weekday"), "weekday",
                                            [(d, _weekday_name(d)) for d in range(7)],
                                            selected=vals.get("weekday", ""), id=f"{fid}-weekday", required=True,
                                            error=errors.get("weekday"))
    if add:
        fields["done_by"] = ui.select_field(t("calendar.roster_done_by"), "done_by",
                                            [(d, t(f"calendar.roster_by_{d}")) for d in roster.DONE_BY],
                                            selected=vals.get("done_by", ""), id=f"{fid}-done_by", required=True,
                                            error=errors.get("done_by"), hint=t("calendar.roster_done_by_hint"))
    fields["every"] = ui.field(t("calendar.roster_every_label"), "every", vals.get("every", ""), type="number",
                               min="1", max=str(roster.MAX_EVERY), step="1", id=f"{fid}-every", required=True,
                               error=errors.get("every"), hint=t("calendar.roster_every_hint", max=roster.MAX_EVERY))
    fields["month_start"] = _choice("checkbox", "month_start", "1", f"{fid}-month_start",
                                    t("calendar.roster_month_start"), t("calendar.roster_month_start_hint"),
                                    checked=vals.get("month_start") == "1", error=errors.get("month_start"))
    fields["month_start_from"] = ui.field(t("calendar.roster_month_from"), "month_start_from",
                                          vals.get("month_start_from", ""), type="month",
                                          id=f"{fid}-month_start_from", error=errors.get("month_start_from"),
                                          hint=t("calendar.roster_month_from_hint"))
    return fields


def _roles_panel(conn, error, vals):
    """The Service roles: a table (name to its page, day, done by, how often, month start, Rotation, Hide/Show)
    and the add form under it."""
    rows = []
    for role in roster.roles(conn, include_hidden=True):
        tag = "" if role["active"] else f' <span class="tag">{h(t("calendar.roster_hidden_tag"))}</span>'
        rows.append([f'<a href="{ROLES}/{role["id"]}">{vi(role["name"])}</a>{tag}',
                     h(_weekday_name(role["weekday"])), h(_done_by_text(role)),
                     h(tn("calendar.roster_every", role["every"])), h(_month_start_text(role)),
                     h(_places_text(role, len(roster.rotation(conn, role["id"])))), _toggle_form(role)])
    head = [(t(key), False) for key in ("calendar.roster_role", "calendar.roster_col_day",
                                         "calendar.roster_col_done_by", "calendar.roster_col_every",
                                         "calendar.roster_col_month", "calendar.roster_rotation")]
    head.append(("", False, "act"))  # Hide or Show: off paper (print.css)
    body = table(head, rows, cls="roster-roles") if rows else empty(t("calendar.roster_no_roles"))
    errors = _errors(error, "add-role", ROLE_PLACES, set(ROLE_PLACES))
    shown = vals if errors else {"weekday": "6", "done_by": "person", "every": "1"}
    f = _role_fields("add-role", shown, errors, add=True)
    add = ui.form(f"{ROLES}/add", (
        f'<fieldset class="group"><legend>{h(t("calendar.roster_add_role"))}</legend>'
        f'<div class="inline-fields two">{f["name"]}{f["weekday"]}</div>'
        f'<div class="inline-fields two">{f["done_by"]}{f["every"]}</div>'
        f'{f["month_start"]}<div class="inline-fields two">{f["month_start_from"]}</div></fieldset>'
        + form_error(errors) + ui.button(t("core.btn_add"), "secondary")))
    return _anchored("setup-roles", t("calendar.roster_panel"), body + f'<div class="add-form">{add}</div>',
                     meta=h(t("calendar.roster_roles_meta")))


def _rule_panel(conn, error, vals):
    """The same-person rule: 3 radio choices, each with one plain sentence."""
    errors = _errors(error, "rule", {}, ())
    posted = vals.get("rule") if errors else None
    current = posted if posted in roster.SAME_PERSON_RULES else roster.same_person_rule(conn)
    choices = "".join(_choice("radio", "rule", rule, f"rule-{rule}", t(f"calendar.roster_rule_{rule}"),
                              t(f"calendar.roster_rule_{rule}_hint"), checked=rule == current)
                      for rule in roster.SAME_PERSON_RULES)
    form = ui.form("/calendar/roster/rule", (
        f'<fieldset class="group"><legend>{h(t("calendar.roster_rule_question"))}</legend>{choices}</fieldset>'
        + form_error(errors) + ui.button(t("core.btn_save"), "secondary")))
    return _anchored("same-person", t("calendar.roster_rule_title"), form, meta=h(t("calendar.roster_rule_meta")))


def _skipped_panel(conn, error, vals, today):
    """The Skipped dates of this year and next (date, reason, Remove) and the add form."""
    first, last = today.year, min(today.year + 1, LAST_YEAR)
    rows = []
    for r in roster.skipped_dates(conn, f"{first:04d}-01-01", f"{last:04d}-12-31"):
        day = ui.fmt_date(r["date"])
        remove = (f'<form class="row-form" action="/calendar/roster/skipped/remove" method="post">'
                  f'{ui.hidden("date", r["date"])}<button class="link-btn" type="submit" '
                  f'aria-label="{h(t("calendar.roster_remove_aria", date=day))}">{h(t("calendar.roster_remove"))}'
                  "</button></form>")
        weekday = _weekday_name(_dt.date.fromisoformat(r["date"]).weekday())
        rows.append([num(f"{weekday} {day}"), vi(r["reason"]), remove])
    head = [(t("calendar.roster_date"), False), (t("calendar.roster_reason"), False), ("", False, "act")]
    body = (table(head, rows, cls="skipped-dates") if rows
            else empty(t("calendar.roster_skipped_none", first=first, last=last)))
    top = _errors(error, "skipped", {}, ())  # a refused Remove
    errors = _errors(error, "add-skipped", SKIPPED_PLACES, set(SKIPPED_PLACES))
    shown = vals if errors else {}
    add = ui.form("/calendar/roster/skipped/add", (
        f'<fieldset class="group"><legend>{h(t("calendar.roster_add_skipped"))}</legend><div class="inline-fields">'
        + ui.field(t("calendar.roster_date"), "date", shown.get("date", ""), type="date", id="add-skipped-date",
                   required=True, error=errors.get("date"))
        + ui.field(t("calendar.roster_reason"), "reason", shown.get("reason", ""), id="add-skipped-reason",
                   required=True, autocomplete="off", lang="vi", error=errors.get("reason"),
                   hint=t("calendar.roster_reason_hint"))
        + "</div></fieldset>" + form_error(errors) + ui.button(t("core.btn_add"), "secondary")))
    return _anchored("skipped-dates", t("calendar.roster_skipped_dates"),
                     form_error(top) + body + f'<div class="add-form">{add}</div>',
                     meta=h(t("calendar.roster_skipped_meta", first=first, last=last)))


def _setup_view(req, error=None, vals=None, status=200):
    """The setup page. ``error``: ``(form key, exception)`` of a refused form; ``vals``: that form."""
    conn, vals = req.conn, vals or {}
    body = (f'<div class="grid lists roster-setup"><div class="span-12 stack">{_roles_panel(conn, error, vals)}'
            '</div>'
            f'<div class="span-7 stack">{_skipped_panel(conn, error, vals, _dt.date.today())}</div>'
            f'<div class="span-5 stack">{_rule_panel(conn, error, vals)}</div></div>')
    actions = ui.link_button(t("calendar.roster_title"), "/calendar/roster")
    return Response.html(ui.page(t("calendar.roster_setup"), body, "calendar",
                                 sub=h(t("calendar.roster_setup_sub")), actions=actions), status)


def _move_form(rid, action, field, value, name):
    word, aria = {"up": ("calendar.roster_up", "calendar.roster_up_aria"),
                  "down": ("calendar.roster_down", "calendar.roster_down_aria"),
                  "remove": ("calendar.roster_take_out", "calendar.roster_take_out_aria")}[action]
    return (f'<form class="row-form" action="{ROLES}/{rid}/rotation/{action}" method="post">'
            f'{ui.hidden(field, value)}<button class="link-btn" type="submit" aria-label="{h(t(aria, name=name))}">'
            f'{h(t(word))}</button></form>')


def _field_of(role):
    return "person_id" if role["done_by"] == "person" else "ministry_id"


def _rotation_panel(conn, role, error, vals):
    """The Rotation of a Service role: its places in order (Move up, Move down, Take out) and a select to add a
    Person (a role done by a Person) or a Ministry (a role done by a Ministry) at the end."""
    rid, field = role["id"], _field_of(role)
    places = roster.rotation(conn, rid)
    lines = []
    for k, place in enumerate(places, start=1):
        value, name = place[field], place["name"]
        lines.append([f'{num(f"{k}.")} {vi(name)}', _move_form(rid, "up", field, value, name) if k > 1 else "",
                      _move_form(rid, "down", field, value, name) if k < len(places) else "",
                      _move_form(rid, "remove", field, value, name)])
    what = t("calendar.person" if field == "person_id" else "calendar.roster_ministry")
    head = [(what, False)] + [("", False, "act")] * 3
    body = table(head, lines, cls="rotation") if lines else empty(t("calendar.roster_rotation_empty"))
    taken = {place[field] for place in places}
    if field == "person_id":
        options = [("", t("calendar.choose_person"))] + [(p["id"], p["full_name"])
                                                         for p in people.list_persons(conn) if p["id"] not in taken]
        label = t("calendar.roster_add_person")
    else:
        options = [("", t("calendar.roster_choose_ministry"))] + [(m["id"], m["name"])
                                                                  for m in lists.get_list(conn, "ministry")
                                                                  if m["id"] not in taken]
        label = t("calendar.roster_add_ministry")
    add_error = i18n.error_text(error[1]) if error and error[0] == "rotation-add" else None
    add = ui.form(f"{ROLES}/{rid}/rotation/add", (
        '<div class="inline-add">'
        + ui.select_field(label, field, options, selected=vals.get(field, "") if add_error else "",
                          id="rotation-add", lang="vi", required=True, error=add_error)
        + ui.button(t("core.btn_add"), "secondary") + "</div>"))
    top = _errors(error, "rotation", {}, ())  # a refused Move up, Move down or Take out
    return _anchored("rotation", t("calendar.roster_rotation"),
                     form_error(top) + body + f'<div class="add-form">{add}</div>',
                     meta=h(t("calendar.roster_rotation_meta")))


def _edit_panel(conn, role, error, vals):
    """The edit form of a Service role. Done by is shown, never changed; the weekday is shown with the reason
    once the Service role is on the Roster."""
    locked = roster.role_has_links(conn, role["id"])
    fields = {"name", "every", "month_start", "month_start_from"} | (set() if locked else {"weekday"})
    errors = _errors(error, "edit", ROLE_PLACES, fields)
    shown = vals if errors else {"name": role["name"], "weekday": str(role["weekday"]),
                                 "every": str(role["every"]), "month_start": "1" if role["month_start"] else "",
                                 "month_start_from": role["month_start_from"] or ""}
    f = _role_fields("edit-role", shown, errors, locked=locked)
    facts = [(t("calendar.roster_done_by"), _done_by_text(role))]
    notes = [t("calendar.roster_done_by_hint")]
    if locked:
        facts.append((t("calendar.roster_weekday"), _weekday_name(role["weekday"])))
        notes.append(t("calendar.roster_weekday_locked"))
    kv = '<dl class="kv wide">' + "".join(f"<div><dt>{h(a)}</dt><dd>{h(b)}</dd></div>" for a, b in facts) + "</dl>"
    form = ui.form(f"{ROLES}/{role['id']}", (
        kv + f'<p class="hint">{h(" ".join(notes))}</p>' + f["name"] + f.get("weekday", "") + f["every"]
        + f["month_start"] + f["month_start_from"] + form_error(errors) + ui.button(t("core.btn_save"))))
    return _anchored("role-edit", t("calendar.roster_edit_role"), form)


def _role_view(req, role, error=None, vals=None, status=200):
    """The page of one Service role: its Rotation, then its edit form."""
    conn, vals = req.conn, vals or {}
    body = (f'<div class="grid lists roster-setup"><div class="span-7 stack">'
            f'{_rotation_panel(conn, role, error, vals)}</div>'
            f'<div class="span-5 stack">{_edit_panel(conn, role, error, vals)}</div></div>')
    sub = [_weekday_name(role["weekday"]), _done_by_text(role)] + ([] if role["active"] else
                                                                  [t("calendar.roster_hidden_tag")])
    actions = ui.link_button(t("calendar.roster_setup"), f"{SETUP}#setup-roles")
    return Response.html(ui.page(role["name"], body, "calendar", sub=h(" · ".join(sub)), actions=actions,
                                 lang="vi"), status)


# ---------------------------------------------------------------- /calendar/roster/setup and its forms

def _to_setup(anchor, msg):
    return Response.redirect(ui.url(SETUP, msg=msg) + f"#{anchor}")


def _to_role(rid, anchor, msg):
    return Response.redirect(ui.url(f"{ROLES}/{rid}", msg=msg) + f"#{anchor}")


def _role_or_none(req):
    return roster.get_role(req.conn, req.params["id"])


def _no_role():
    return not_found("calendar.roster_role", SETUP, "calendar.roster_setup")


def setup_page(req):
    return _setup_view(req)


def role_add_post(req):
    f = req.form
    try:
        rid = roster.add_role(req.conn, f.get("name"), f.get("weekday"), f.get("done_by"), every=f.get("every"),
                              month_start=_on(f.get("month_start")), month_start_from=f.get("month_start_from"))
    except ValueError as exc:
        return _setup_view(req, ("add-role", exc), f, 400)
    return _to_setup("setup-roles", t("calendar.roster_role_added", name=roster.get_role(req.conn, rid)["name"]))


def _set_active(req, active):
    role = _role_or_none(req)
    if role is None:
        return _no_role()
    roster.set_role_active(req.conn, role["id"], active)
    return _to_setup("setup-roles", t("calendar.roster_role_shown" if active else "calendar.roster_role_hidden",
                                      name=role["name"]))


def role_hide_post(req):
    return _set_active(req, False)


def role_show_post(req):
    return _set_active(req, True)


def rule_post(req):
    rule = req.form.get("rule") or ""
    try:
        roster.set_same_person_rule(req.conn, rule)
    except ValueError as exc:
        return _setup_view(req, ("rule", exc), req.form, 400)
    return _to_setup("same-person", t("calendar.roster_rule_saved", rule=t(f"calendar.roster_rule_{rule}")))


def skipped_add_post(req):
    f = req.form
    try:
        day = text.check_date(f.get("date") or "", "calendar.roster_skipped_date")
        old = roster.skipped_reason(req.conn, day)
        roster.add_skipped_date(req.conn, day, f.get("reason"))
    except ValueError as exc:
        return _setup_view(req, ("add-skipped", exc), f, 400)
    new, shown = roster.skipped_reason(req.conn, day), ui.fmt_date(day)
    if old is None:
        msg = t("calendar.roster_skipped_added", date=shown, reason=new)
    elif old == new:
        msg = t("calendar.roster_skipped_unchanged", date=shown)
    else:
        msg = t("calendar.roster_skipped_replaced", date=shown, reason=new)
    return _to_setup("skipped-dates", msg)


def skipped_remove_post(req):
    try:
        day = text.check_date(req.form.get("date") or "", "calendar.roster_skipped_date")
    except ValueError as exc:
        return _setup_view(req, ("skipped", exc), req.form, 400)
    removed = roster.remove_skipped_date(req.conn, day)
    key = "calendar.roster_skipped_removed" if removed else "calendar.roster_skipped_not_there"
    return _to_setup("skipped-dates", t(key, date=ui.fmt_date(day)))


# ---------------------------------------------------------------- /calendar/roster/roles/<id> and its forms

def role_page(req):
    role = _role_or_none(req)
    return _no_role() if role is None else _role_view(req, role)


def role_post(req):
    """Save the edit form. Done by is never sent (it never changes); a weekday that is not sent stays."""
    role = _role_or_none(req)
    if role is None:
        return _no_role()
    f = req.form
    changes = {"name": f.get("name"), "every": f.get("every"), "month_start": _on(f.get("month_start")),
               "month_start_from": f.get("month_start_from")}
    if f.get("weekday") is not None:
        changes["weekday"] = f["weekday"]
    try:
        roster.update_role(req.conn, role["id"], **changes)
    except ValueError as exc:
        return _role_view(req, role, ("edit", exc), f, 400)
    name = roster.get_role(req.conn, role["id"])["name"]
    return _to_role(role["id"], "role-edit", t("calendar.roster_role_saved", name=name))


def _rotation_post(req, action):
    """One change of a Rotation (``action``: see :func:`rotation_order`), saved with ``roster.set_rotation``.
    Refused: the page of the Service role again (400), the sentence in its Rotation card, nothing saved."""
    role = _role_or_none(req)
    if role is None:
        return _no_role()
    conn, rid, field = req.conn, role["id"], _field_of(role)
    by_person = field == "person_id"
    before = roster.rotation(conn, rid)
    ids = [place[field] for place in before]
    try:
        raw = (req.form.get(field) or "").strip()
        if not raw:
            raise TextError("calendar.err_choose_person" if by_person else "calendar.roster_err_choose_ministry")
        value = text.to_id(raw, "calendar.person" if by_person else "calendar.roster_ministry")
        order = rotation_order(ids, value, action)
        if order != ids:
            roster.set_rotation(conn, rid, order)
    except ValueError as exc:
        return _role_view(req, role, ("rotation-add" if action == "add" else "rotation", exc), req.form, 400)
    if order == ids:
        return _to_role(rid, "rotation", t("calendar.roster_rotation_unchanged"))
    after = roster.rotation(conn, rid)
    name = next(place["name"] for place in [*after, *before] if place[field] == value)
    if action == "remove":
        return _to_role(rid, "rotation", t("calendar.roster_rotation_taken_out", name=name))
    key = "calendar.roster_rotation_added" if action == "add" else "calendar.roster_rotation_moved"
    return _to_role(rid, "rotation", t(key, name=name, place=order.index(value) + 1))


def rotation_add_post(req):
    return _rotation_post(req, "add")


def rotation_up_post(req):
    return _rotation_post(req, "up")


def rotation_down_post(req):
    return _rotation_post(req, "down")


def rotation_remove_post(req):
    return _rotation_post(req, "remove")


ROUTES = [
    ("GET", "/calendar/roster", roster_page),
    ("GET", "/calendar/roster/fill", fill_page),
    ("POST", "/calendar/roster/fill", fill_post),
    ("POST", "/calendar/<int:id>/roles", roles_post),
    ("POST", "/calendar/<int:id>/roles/clear", roles_clear_post),
    ("GET", SETUP, setup_page),
    ("POST", "/calendar/roster/rule", rule_post),
    ("POST", "/calendar/roster/skipped/add", skipped_add_post),
    ("POST", "/calendar/roster/skipped/remove", skipped_remove_post),
    ("POST", f"{ROLES}/add", role_add_post),
    ("GET", f"{ROLES}/<int:id>", role_page),
    ("POST", f"{ROLES}/<int:id>", role_post),
    ("POST", f"{ROLES}/<int:id>/hide", role_hide_post),
    ("POST", f"{ROLES}/<int:id>/show", role_show_post),
    ("POST", f"{ROLES}/<int:id>/rotation/add", rotation_add_post),
    ("POST", f"{ROLES}/<int:id>/rotation/up", rotation_up_post),
    ("POST", f"{ROLES}/<int:id>/rotation/down", rotation_down_post),
    ("POST", f"{ROLES}/<int:id>/rotation/remove", rotation_remove_post),
]
