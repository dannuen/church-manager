"""The Service role pages of the Roster (goal "Service role Roster", decision D6).

Card RO-4: the Service roles panel of a Service page ``/calendar/<id>`` (``#service-roles``) and its two
forms: ``POST /calendar/<id>/roles`` (pick or swap a name: ``roster.set_link``) and
``POST /calendar/<id>/roles/clear`` (``roster.clear_link``). Both go back to the panel (POST-redirect-GET);
a refused form shows the Service page again (400) with the sentence in the panel.

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

from .. import i18n, lists, roster, text, ui
from ..i18n import TextError, t
from ..server import Response
from ..ui import h, vi
from . import calendar as cal_pages  # a module import: pages/calendar.py imports this module in _item_view
from .people import empty, form_error, num, panel, person_link, today_text

FORM = "service-roles"  # the form key of a refused change, and the id of the panel


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


ROUTES = [
    ("POST", "/calendar/<int:id>/roles", roles_post),
    ("POST", "/calendar/<int:id>/roles/clear", roles_clear_post),
]
