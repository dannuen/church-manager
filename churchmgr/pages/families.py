"""Family pages: ``/families`` (list), ``/families/new``, ``/families/<id>`` (the people in it now
and before, the address, the Chi phái now and before, and the form to change the Chi phái) and
``/families/<id>/edit`` (the Family name and Address: plain fields, not history).

The Chi phái changes only through ``people.set_family_chi_phai`` (history is kept).
A Person joins or leaves a Family on the Person page.
"""

from .. import people, ui
from ..server import Response
from ..ui import h, vi
from . import documents as document_pages  # card C3: the shared Documents block
from .people import (card_link, change_box, chi_phai_link, date_field, empty, field_errors, form_error,
                     latest_change, list_panel, newest_first, not_found, num, panel, past_or_today, period,
                     person_link, same_change, statement_href, table)


def _past_people(conn, family_id):
    """Every closed Family link of this Family (a Person who left, or an old Family role), newest first."""
    return conn.execute(
        "SELECT p.id, p.full_name, fl.family_role, fl.start_date, fl.end_date "
        "FROM family_link fl JOIN person p ON p.id = fl.person_id "
        "WHERE fl.family_id = ? AND fl.end_date IS NOT NULL "
        "ORDER BY fl.end_date DESC, p.name_folded, fl.id",
        (family_id,),
    ).fetchall()


# ---------------------------------------------------------------- /families

def list_page(req):
    conn = req.conn
    families = people.list_families(conn)
    lines, in_family = [], 0
    for f in families:
        members = people.family_members(conn, f["id"])
        in_family += len(members)
        cp = people.current_chi_phai(conn, f["id"])
        lines.append([
            f'<a href="/families/{f["id"]}">{vi(f["name"])}</a>',
            vi(f["address"]),
            num(len(members)),
            chi_phai_link(cp["chi_phai_id"], cp["name"]) if cp else ui.DASH,
        ])
    body = (table([("Family", False), ("Address", False), ("People now", True), ("Chi phái", False)], lines,
                  "families")
            if lines else empty("No Family yet. Add the first Family."))
    sub = h(f"{ui.plural(len(families), 'Family', 'Families')} · "
            f"{ui.plural(in_family, 'Person', 'People')} in a Family now")
    actions = ui.link_button("Add a Family", "/families/new", "primary")
    return Response.html(ui.page("Families", list_panel("families", "Families list", body), "families",
                                 sub=sub, actions=actions))


# ---------------------------------------------------------------- /families/new

def _new_form(req, values=None, error=None, status=200):
    values = values or {}
    errors = field_errors(error, "new", {"name": "Family name"})
    inner = (
        ui.field("Family name", "name", values.get("name", ""), error=errors.get("name"), required=True,
                 autocomplete="off", lang="vi", hint="For example: Gia đình Nguyễn Hải Đăng")
        + ui.textarea_field("Address", "address", values.get("address", ""), lang="vi",
                            hint="Every Person in this Family uses this address.")
        + form_error(errors) + ui.button("Add Family")
    )
    body = (f'<section class="panel narrow">{ui.form("/families/new", inner)}'
            '<p class="hint">Then put people in it from each Person page (Family, Family role and date).</p>'
            "</section>")
    return Response.html(ui.page("Add a Family", body, "families"), status)


def new_page(req):
    return _new_form(req)


def new_post(req):
    try:
        fid = people.add_family(req.conn, req.form.get("name"), req.form.get("address"))
    except ValueError as exc:
        return _new_form(req, req.form, ("new", str(exc)), 400)
    return Response.redirect(ui.url(f"/families/{fid}", msg="Family added."))


# ---------------------------------------------------------------- /families/<id>

def _people_panels(conn, fid):
    now = people.family_members(conn, fid)
    now_lines = [[person_link(p["id"], p["full_name"]), h(p["family_role"]),
                  num(ui.fmt_date(p["start_date"]))] for p in now]
    now_body = (table([("Person", False), ("Family role", False), ("Since", True)], now_lines, "people-now")
                if now_lines else empty("No one is in this Family now."))
    past = _past_people(conn, fid)
    past_lines = [[person_link(p["id"], p["full_name"]), h(p["family_role"]), *period(p["start_date"], p["end_date"])]
                  for p in past]
    past_body = (table([("Person", False), ("Family role", False), ("From", True), ("To", True)], past_lines,
                       "history")
                 if past_lines else empty("No one has left this Family."))
    hint = '<p class="hint">To add or move a Person, open their Person page.</p>'
    return (panel("people-now", "People now", now_body + hint)
            + panel("people-before", "People before", past_body,
                    meta="Old Family links, kept with their dates"))


def _chi_phai_panel(conn, fid, error, vals):
    rows = people.family_chi_phai_history(conn, fid)
    current = next((r for r in rows if r["end_date"] is None), None)
    errors = field_errors(error, "chi-phai", {"start_date": "Start date", "chi_phai_id": "Chi phái"})
    first = ("", "— Leave the Chi phái —") if current else ("", "— No Chi phái —")
    options = [first] + [(c["id"], c["name"]) for c in people.list_chi_phai(conn)]
    form = ui.form(f"/families/{fid}/chi-phai", (
        ui.select_field("Chi phái", "chi_phai_id", options, id="chi-phai-id", lang="vi",
                        selected=vals.get("chi_phai_id", current["chi_phai_id"] if current else ""),
                        error=errors.get("chi_phai_id"))
        + date_field("Start date", "start_date", "chi-phai-date", vals.get("start_date"), errors.get("start_date"),
                     min_date=latest_change(rows), hint="The old Chi phái link is kept with its dates.")
        + form_error(errors) + ui.button("Change Chi phái")))
    lines = [[chi_phai_link(r["chi_phai_id"], r["name"]), *period(r["start_date"], r["end_date"])]
             for r in newest_first(rows)]
    body = (table([("Chi phái", False), ("From", True), ("To", True)], lines, "history")
            if lines else empty("This Family is not in a Chi phái."))
    return panel("chi-phai", "Chi phái", body + change_box("Change Chi phái", form, bool(errors)))


def _family_view(req, family, error=None, status=200):
    conn = req.conn
    fid = family["id"]
    vals = req.form if error else {}
    members = people.family_members(conn, fid)
    cp = people.current_chi_phai(conn, fid)
    finding = [ui.plural(len(members), "Person", "People") + " now"]
    finding.append(f"{cp['name']} since {ui.fmt_date(cp['start_date'])}" if cp else "No Chi phái")
    address = panel("address", "Address", f'<p>{vi(family["address"])}</p>',
                    meta="Every Person in this Family uses it",
                    foot=card_link("Edit name or Address", f"/families/{fid}/edit"))
    body = (f'<div class="grid family"><div class="span-8 stack">{_people_panels(conn, fid)}</div>'
            f'<div class="side-4 stack">{address}{_chi_phai_panel(conn, fid, error, vals)}'
            f'{document_pages.documents_panel(conn, family_id=fid)}</div></div>')
    actions = (ui.link_button("Edit Family", f"/families/{fid}/edit")
               + ui.link_button("Giving statement", statement_href(family_id=fid)))
    return Response.html(ui.page(family["name"], body, "families", sub=h(" · ".join(finding)), actions=actions,
                                 lang="vi"), status)


def _family_or_none(req):
    return people.get_family(req.conn, req.params["id"])


def family_page(req):
    family = _family_or_none(req)
    if family is None:
        return not_found("Family", "/families", "Go to Families")
    return _family_view(req, family)


# ---------------------------------------------------------------- /families/<id>/edit

def _edit_form(req, family, values=None, error=None, status=200):
    """Family name and Address. They are plain fields, not history (who is in the Family and its Chi phái are)."""
    values = values if values is not None else {"name": family["name"], "address": family["address"] or ""}
    errors = field_errors(error, "edit", {"name": "Family name"})
    fid = family["id"]
    inner = (
        ui.field("Family name", "name", values.get("name", ""), error=errors.get("name"), required=True,
                 autocomplete="off", lang="vi")
        + ui.textarea_field("Address", "address", values.get("address", ""), lang="vi",
                            hint="Every Person in this Family uses this address.")
        + form_error(errors) + ui.button("Save")
    )
    body = (f'<section class="panel narrow">{ui.form(f"/families/{fid}/edit", inner)}'
            '<p class="hint">Who is in this Family changes on each Person page, and its Chi phái on the '
            f'<a href="/families/{fid}">Family page</a>. Both keep their history.</p></section>')
    return Response.html(ui.page(f"Edit {family['name']}", body, "families", lang="vi",
                                 actions=ui.link_button("Back to the Family", f"/families/{fid}")), status)


def edit_page(req):
    family = _family_or_none(req)
    if family is None:
        return not_found("Family", "/families", "Go to Families")
    return _edit_form(req, family)


def edit_post(req):
    family = _family_or_none(req)
    if family is None:
        return not_found("Family", "/families", "Go to Families")
    try:
        people.update_family(req.conn, family["id"], name=req.form.get("name"), address=req.form.get("address"))
    except ValueError as exc:
        return _edit_form(req, family, req.form, ("edit", str(exc)), 400)
    return Response.redirect(ui.url(f"/families/{family['id']}", msg="Family name and Address saved."))


def chi_phai_post(req):
    family = _family_or_none(req)
    if family is None:
        return not_found("Family", "/families", "Go to Families")
    conn, fid = req.conn, family["id"]
    try:
        day = past_or_today(req.form.get("start_date"), "Start date")
        new_id = req.form.get("chi_phai_id") or None
        before = people.current_chi_phai(conn, fid)
        if new_id is None and before is None:
            message = same_change("This Family is not in a Chi phái.")
        elif new_id is None:
            people.set_family_chi_phai(conn, fid, None, day)
            message = f"Left {before['name']} on {ui.fmt_date(day)}. The old link is kept."
        elif before is not None and str(before["chi_phai_id"]) == new_id:
            message = same_change(f"Already in {before['name']}.")
        else:
            people.set_family_chi_phai(conn, fid, new_id, day)
            message = f"Now in {people.current_chi_phai(conn, fid)['name']} from {ui.fmt_date(day)}."
    except ValueError as exc:
        return _family_view(req, family, ("chi-phai", str(exc)), 400)
    return Response.redirect(ui.url(f"/families/{fid}", msg=message))


ROUTES = [
    ("GET", "/families", list_page),
    ("GET", "/families/new", new_page),
    ("POST", "/families/new", new_post),
    ("GET", "/families/<int:id>", family_page),
    ("GET", "/families/<int:id>/edit", edit_page),
    ("POST", "/families/<int:id>/edit", edit_post),
    ("POST", "/families/<int:id>/chi-phai", chi_phai_post),
]
