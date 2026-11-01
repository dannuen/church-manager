"""Care page ``/care``: who needs a visit, Plan a Visit, the planned Visits (each with
"Mark Visit done"), and the Care log (all done Visits: who, when, short note).

Visits change only through ``care.plan_visit`` and ``care.mark_visit_done``.
A done date after today is refused here (the data layer would accept it).
"""

import datetime as _dt

from .. import care, people, text, ui
from ..server import Response
from ..ui import h, vi
from .people import (card_link, empty, family_link, field_errors, form_error, num, panel, past_or_today,
                     person_link, today_text)

LOG_ROWS = 20  # Care log rows before "Show all"


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
    return text.check_datetime(raw, "Date and time")


# ---------------------------------------------------------------- blocks

def _needs_panel(conn, needs, months):
    rows = "".join(
        '<li class="row" data-row><span class="what">'
        f'{person_link(p["person_id"], p["full_name"])}'
        f'<span class="sub">{h(p["status_name"]) if p["status_name"] else "—"}'
        f'{" · " + vi(p["family_name"]) if p["family_name"] else ""}</span></span>'
        f'<span class="figure num{" faint" if not p["last_visit"] else ""}" title="Last Visit">'
        f'{h(ui.fmt_date(p["last_visit"])) if p["last_visit"] else "never"}</span>'
        f'<a class="row-action" href="{h(ui.url("/care", person_id=p["person_id"]))}#plan" '
        f'aria-label="Plan a Visit for {h(p["full_name"])}">Plan</a></li>'
        for p in needs
    )
    body = (('<div class="list-head" aria-hidden="true"><span>Person</span><span>Last Visit</span>'
             f'<span class="spacer"></span></div><ul class="rows">{rows}</ul>')
            if needs else empty("No one needs a visit now."))
    meta = h(f"No Visit in the last {ui.plural(months, 'month', 'months')}, or never. "
             "Left and Passed away are not listed.")
    count = f'<span class="count num">{h(ui.plural(len(needs), "Person", "People"))}</span>'
    return panel("needs-visit", "Needs a visit", body, meta=meta, head_right=count)


def _plan_panel(conn, req, error):
    errors = field_errors(error, "plan", {"starts_at": "Date and time", "person_id": "Person",
                                          "family_id": "Family"})
    vals = req.form if errors else req.query
    persons = [("", "— Choose a Person —")] + [(p["id"], p["full_name"]) for p in people.list_persons(conn)]
    families = [("", "— or a Family —")] + [(f["id"], f["name"]) for f in people.list_families(conn)]
    inner = (
        ui.select_field("Person", "person_id", persons, selected=vals.get("person_id", ""), id="plan-person",
                        lang="vi", error=errors.get("person_id"))
        + ui.select_field("Family", "family_id", families, selected=vals.get("family_id", ""), id="plan-family",
                          lang="vi", error=errors.get("family_id"), hint="Choose one Person or one Family.")
        + ui.field("Date and time", "starts_at", vals.get("starts_at") or default_start(), type="datetime-local",
                   id="plan-starts", required=True, error=errors.get("starts_at"))
        + ui.textarea_field("Note", "note", vals.get("note", "") if errors else "", id="plan-note", lang="vi",
                            rows=2)
        + form_error(errors) + ui.button("Plan a Visit")
    )
    return panel("plan", "Plan a Visit", ui.form("/care/visits", inner, id="plan"),
                 meta="It goes on the Calendar as a Visit.")


def _done_form(row, error, vals):
    iid = row["id"]
    mine = field_errors(error, f"done-{iid}", {"done_date": "Done date"})
    vals = vals if mine else {}
    inner = (
        f'<div class="inline-fields">'
        + ui.field("Done date", "done_date", vals.get("done_date") or today_text(), type="date",
                   id=f"done-date-{iid}", max=today_text(), required=True, error=mine.get("done_date"))
        + ui.field("Short note", "care_note", vals.get("care_note", ""), id=f"done-note-{iid}",
                   lang="vi", autocomplete="off")
        + "</div>" + form_error(mine) + ui.button("Mark Visit done", "secondary")
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
    body = f'<ul class="visits">{rows}</ul>' if planned else empty("No Visit planned. Plan one above.")
    return panel("planned", "Planned Visits", body, meta=h(ui.plural(len(planned), "Visit", "Visits") + " not done yet"))


def _log_panel(log, show_all):
    shown = log if show_all else log[:LOG_ROWS]
    rows = "".join(
        '<li class="row" data-row><span class="what">'
        f'<span>{_who(r)}</span><span class="sub" lang="vi">{h(r["care_note"]) if r["care_note"] else "—"}</span>'
        f'</span><span class="figure num">{h(ui.fmt_date(r["done_date"]))}</span></li>'
        for r in shown
    )
    body = f'<ul class="rows">{rows}</ul>' if shown else empty("No Visit done yet.")
    foot = ""
    if len(log) > len(shown):
        foot = card_link(f"Show all {len(log)} in the Care log", "/care?log=all#care-log")
    return panel("care-log", "Care log", body, meta=h(ui.plural(len(log), "done Visit", "done Visits") + ", newest first"),
                 foot=foot)


def _care_view(req, error=None, status=200):
    conn = req.conn
    needs = care.needs_visit(conn)
    months = care.reminder_months(conn)
    planned = _planned_visits(conn)
    log = care.care_log(conn)
    finding = h(" · ".join((f"{ui.plural(len(needs), 'Person needs', 'People need')} a visit",
                            f"{ui.plural(len(planned), 'Visit', 'Visits')} planned",
                            f"{ui.plural(len(log), 'done Visit', 'done Visits')} in the Care log")))
    body = (f'<div class="grid care"><div class="span-7 stack">{_needs_panel(conn, needs, months)}</div>'
            f'<div class="span-5 stack">{_plan_panel(conn, req, error)}{_planned_panel(planned, error, req)}'
            f'{_log_panel(log, req.query.get("log") == "all")}</div></div>')
    return Response.html(ui.page("Care", body, "care", sub=finding), status)


# ---------------------------------------------------------------- handlers

def care_page(req):
    return _care_view(req)


def plan_post(req):
    f = req.form
    try:
        starts = visit_start(f.get("starts_at"))
        care.plan_visit(req.conn, starts, person_id=f.get("person_id") or None, family_id=f.get("family_id") or None,
                        note=f.get("note"))
    except ValueError as exc:
        return _care_view(req, ("plan", str(exc)), 400)
    return Response.redirect(ui.url("/care", msg=f"Visit planned for {ui.fmt_datetime(starts)}."))


def done_post(req):
    iid = req.params["id"]
    row = req.conn.execute("SELECT kind, visit_done FROM calendar_item WHERE id = ?", (iid,)).fetchone()
    if row is None or row["kind"] != "Visit" or row["visit_done"]:
        raise ValueError("This is not a planned Visit. It may be marked done already.")
    try:
        day = past_or_today(req.form.get("done_date"), "Done date")
        care.mark_visit_done(req.conn, iid, day, req.form.get("care_note"))
    except ValueError as exc:
        return _care_view(req, (f"done-{iid}", str(exc)), 400)
    return Response.redirect(ui.url("/care", msg=f"Visit marked done on {ui.fmt_date(day)}. It is in the Care log."))


ROUTES = [
    ("GET", "/care", care_page),
    ("POST", "/care/visits", plan_post),
    ("POST", "/care/visits/<int:id>/done", done_post),
]
