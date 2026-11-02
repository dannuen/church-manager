"""Care page ``/care``: who needs a visit, Plan a Visit, the planned Visits (each with
"Mark Visit done"), and the Care log (all done Visits: who, when, short note).

Visits change only through ``care.plan_visit`` and ``care.mark_visit_done``.
A done date after today is refused here (the data layer would accept it).
Words on screen come from the text table (sections ``care`` and ``calendar``); names and notes are shown
as stored.
"""

import datetime as _dt

from .. import calendar as cal
from .. import care, i18n, people, text, ui
from ..i18n import TextError, t, tn
from ..server import Response
from ..ui import h, vi
from .people import card_link, empty, family_link, field_errors, form_error, panel, person_link, today_text

LOG_ROWS = 20  # Care log rows before "Show all"


def placed_errors(error, form_key, labels):
    """:func:`field_errors` for a refused change ``(form_key, exc)``, in the language of the page.

    ``labels`` maps a field name to the TEXT key of its label. The field is found from the English
    sentence (``str(exc)`` starts with the English label); the sentence shown is ``i18n.error_text(exc)``.
    The Calendar pages use it too.
    """
    if not error or error[0] != form_key:
        return {}
    exc = error[1]
    english = {name: t(key, "en") for name, key in labels.items()}
    return {name: i18n.error_text(exc) for name in field_errors((form_key, str(exc)), form_key, english)}


def _planned_visits(conn):
    """Visits not done yet, oldest first: id, starts_at, note, who, visit_person_id, visit_family_id."""
    return conn.execute(
        "SELECT ci.id, ci.title, ci.starts_at, ci.note, ci.visit_person_id, ci.visit_family_id, "
        "COALESCE(p.full_name, f.name) AS who "
        "FROM calendar_item ci "
        "LEFT JOIN person p ON p.id = ci.visit_person_id "
        "LEFT JOIN family f ON f.id = ci.visit_family_id "
        "WHERE ci.kind = 'Visit' AND ci.visit_done = 0 "
        "ORDER BY ci.starts_at, ci.id"
    ).fetchall()


def _who(row):
    if row["visit_person_id"] is not None:
        return person_link(row["visit_person_id"], row["who"])
    if row["visit_family_id"] is not None:
        return family_link(row["visit_family_id"], row["who"])
    return vi(row["who"])


def default_start(now=None):
    """The default date and time for a new Visit: the next whole hour, as ``YYYY-MM-DDTHH:MM``."""
    now = now or _dt.datetime.now()
    nxt = (now + _dt.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    return nxt.strftime("%Y-%m-%dT%H:%M")


def visit_start(value):
    """``2026-11-03T10:00`` (from ``<input type="datetime-local">``) -> ``2026-11-03 10:00``."""
    raw = (value or "").strip().replace("T", " ")[:16]
    return text.check_datetime(raw, "care.date_time")


def done_day(value):
    """The done date of a Visit as ``YYYY-MM-DD``: a real date on or before today. Otherwise a
    ``TextError`` that starts with "Done date", so :func:`placed_errors` puts it next to that field."""
    day = text.check_date(value or "", "care.done_date")
    today = today_text()
    if day > today:
        raise TextError("care.err_done_future", today=ui.fmt_date(today))
    return day


def _persons(conn):
    return [("", t("calendar.choose_person"))] + [(p["id"], p["full_name"]) for p in people.list_persons(conn)]


def _families(conn):
    return [("", t("calendar.or_family"))] + [(f["id"], f["name"]) for f in people.list_families(conn)]


# ---------------------------------------------------------------- blocks

def _needs_panel(conn, needs, months):
    def sub(p):
        status = p["status_name"] or "—"
        text_ = f'{status} · {p["family_name"]}' if p["family_name"] else status
        family = f' · {vi(p["family_name"])}' if p["family_name"] else ""
        return f'<span class="sub" title="{h(text_)}">{h(status)}{family}</span>'

    last_visit = h(t("care.last_visit"))
    rows = "".join(
        '<li class="row" data-row><span class="what wrap">'
        f'{ui.clamp2(person_link(p["person_id"], p["full_name"]), p["full_name"])}{sub(p)}</span>'
        f'<span class="figure num{" faint" if not p["last_visit"] else ""}" title="{last_visit}">'
        f'{h(ui.fmt_date(p["last_visit"])) if p["last_visit"] else h(t("care.never"))}</span>'
        f'<a class="row-action" href="{h(ui.url("/care", person_id=p["person_id"]))}#plan" '
        f'aria-label="{h(t("care.plan_for", name=p["full_name"]))}">{h(t("care.plan"))}</a></li>'
        for p in needs
    )
    body = ((f'<div class="list-head" aria-hidden="true"><span>{h(t("calendar.person"))}</span>'
             f'<span>{last_visit}</span><span class="spacer"></span></div><ul class="rows">{rows}</ul>')
            if needs else empty(t("care.no_needs")))
    meta = h(t("care.needs_meta", months=tn("core.months", months)))
    count = f'<span class="count num">{h(tn("care.persons", len(needs)))}</span>'
    return panel("needs-visit", t("care.needs_visit"), body, meta=meta, head_right=count)


def _plan_panel(conn, req, error):
    errors = placed_errors(error, "plan", {"starts_at": "care.date_time", "person_id": "calendar.person",
                                           "family_id": "calendar.family"})
    vals = req.form if errors else req.query
    inner = (
        ui.select_field(t("calendar.person"), "person_id", _persons(conn), selected=vals.get("person_id", ""),
                        id="plan-person", lang="vi", error=errors.get("person_id"))
        + ui.select_field(t("calendar.family"), "family_id", _families(conn), selected=vals.get("family_id", ""),
                          id="plan-family", lang="vi", error=errors.get("family_id"), hint=t("care.choose_one"))
        + ui.field(t("care.date_time"), "starts_at", vals.get("starts_at") or default_start(), type="datetime-local",
                   id="plan-starts", required=True, error=errors.get("starts_at"))
        + ui.textarea_field(t("calendar.note"), "note", vals.get("note", "") if errors else "", id="plan-note",
                            lang="vi", rows=2)
        + form_error(errors) + ui.button(t("care.plan_visit"))
    )
    # a form only: on paper (print.css hides .no-print) it would be a heading over nothing
    return panel("plan", t("care.plan_visit"), ui.form("/care/visits", inner, id="plan"),
                 meta=h(t("care.plan_meta")), cls="no-print")


def _done_form(row, error, vals):
    iid = row["id"]
    mine = placed_errors(error, f"done-{iid}", {"done_date": "care.done_date"})
    vals = vals if mine else {}
    inner = (
        f'<div class="inline-fields">'
        + ui.field(t("care.done_date"), "done_date", vals.get("done_date") or today_text(), type="date",
                   id=f"done-date-{iid}", max=today_text(), required=True, error=mine.get("done_date"))
        + ui.field(t("care.short_note"), "care_note", vals.get("care_note", ""), id=f"done-note-{iid}",
                   lang="vi", autocomplete="off")
        + "</div>" + form_error(mine) + ui.button(t("care.mark_done"), "secondary")
    )
    return f'<div class="done-form">{ui.form(f"/care/visits/{iid}/done", inner)}</div>'


def _planned_panel(planned, error, req):
    rows = "".join(
        '<li class="visit" data-row><div class="visit-head">'
        f'<span class="when num">{h(ui.fmt_weekday(r["starts_at"]))} {h(ui.fmt_datetime(r["starts_at"]))}</span>'
        f'<span class="what">{_who(r)}</span></div>'
        + (f'<p class="sub" lang="vi">{h(r["note"])}</p>' if r["note"] else "")
        + _done_form(r, error, req.form) + "</li>"
        for r in planned
    )
    body = f'<ul class="visits">{rows}</ul>' if planned else empty(t("care.none_planned"))
    return panel("planned", t("care.planned"), body, meta=h(tn("care.planned_meta", len(planned))))


def _log_panel(log, show_all):
    shown = log if show_all else log[:LOG_ROWS]
    # as on the Person page: the name and the note each wrap to 2 lines, the full text in the title
    rows = "".join(
        '<li class="row" data-row><span class="what wrap">'
        + ui.clamp2(_who(r), r["who"] or "")
        + (ui.clamp2(h(r["care_note"]), r["care_note"], lang="vi", cls="sub") if r["care_note"]
           else '<span class="sub">—</span>')
        + f'</span><span class="figure num">{h(ui.fmt_date(r["done_date"]))}</span></li>'
        for r in shown
    )
    body = f'<ul class="rows">{rows}</ul>' if shown else empty(t("care.no_log"))
    foot = ""
    if len(log) > len(shown):
        foot = card_link(t("care.show_all", n=len(log)), "/care?log=all#care-log")
    return panel("care-log", t("care.care_log"), body, meta=h(tn("care.log_meta", len(log))), foot=foot)


def _care_view(req, error=None, status=200):
    conn = req.conn
    needs = care.needs_visit(conn)
    months = care.reminder_months(conn)
    planned = _planned_visits(conn)
    log = care.care_log(conn)
    finding = h(" · ".join((tn("care.finding_needs", len(needs)), tn("care.finding_planned", len(planned)),
                            tn("care.finding_log", len(log)))))
    body = (f'<div class="grid care"><div class="span-7 stack">{_needs_panel(conn, needs, months)}</div>'
            f'<div class="span-5 stack">{_plan_panel(conn, req, error)}{_planned_panel(planned, error, req)}'
            f'{_log_panel(log, req.query.get("log") == "all")}</div></div>')
    return Response.html(ui.page(t("care.title"), body, "care", sub=finding), status)


# ---------------------------------------------------------------- handlers

def care_page(req):
    return _care_view(req)


class NotPlannedVisit(TextError):
    """Mark Visit done on a Calendar item that is not a Visit waiting to be marked done."""


def plan_visit_from_form(conn, form):
    """Plan a Visit from the Plan a Visit form: the one place of its rules, for this page and the Hermes
    door. ``form`` has ``.get``. Returns the Calendar item id; a refused value raises ``ValueError``."""
    f = form
    starts = visit_start(f.get("starts_at"))
    return care.plan_visit(conn, starts, person_id=f.get("person_id") or None, family_id=f.get("family_id") or None,
                           note=f.get("note"))


def mark_visit_done_from_form(conn, item_id, form):
    """Mark the planned Visit ``item_id`` done from its Mark Visit done form: the one place of its rules,
    for this page and the Hermes door. Returns the done date. Not a planned Visit: ``NotPlannedVisit``;
    another refused value: ``ValueError``."""
    row = conn.execute("SELECT kind, visit_done FROM calendar_item WHERE id = ?", (item_id,)).fetchone()
    if row is None or row["kind"] != "Visit" or row["visit_done"]:
        raise NotPlannedVisit("care.err_not_planned")
    day = done_day(form.get("done_date"))
    care.mark_visit_done(conn, item_id, day, form.get("care_note"))
    return day


def plan_post(req):
    f = req.form
    try:
        iid = plan_visit_from_form(req.conn, f)
    except ValueError as exc:
        return _care_view(req, ("plan", exc), 400)
    starts = cal.get_calendar_item(req.conn, iid)["starts_at"]
    return Response.redirect(ui.url("/care", msg=t("care.planned_flash", when=ui.fmt_datetime(starts))))


def done_post(req):
    iid = req.params["id"]
    try:
        day = mark_visit_done_from_form(req.conn, iid, req.form)
    except NotPlannedVisit:
        raise  # the server's plain 400 "Not done" page, as before
    except ValueError as exc:
        return _care_view(req, (f"done-{iid}", exc), 400)
    return Response.redirect(ui.url("/care", msg=t("care.done_flash", date=ui.fmt_date(day))))


ROUTES = [
    ("GET", "/care", care_page),
    ("POST", "/care/visits", plan_post),
    ("POST", "/care/visits/<int:id>/done", done_post),
]
