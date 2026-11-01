"""Chi phái pages: ``/chi-phai`` (list), ``/chi-phai/new``, ``/chi-phai/<id>`` (Families now and
before, the Trưởng Chi phái now and before, and the form to set the Trưởng Chi phái) and
``/chi-phai/<id>/edit`` (a new name: a plain field, not history).

The Trưởng Chi phái changes only through ``people.set_truong_chi_phai`` (history is kept).
A Family changes its Chi phái on the Family page.
"""

from .. import people, ui
from ..server import Response
from ..ui import h, vi
from .people import (change_box, date_field, empty, family_link, field_errors, form_error, latest_change,
                     list_panel, newest_first, not_found, num, panel, past_or_today, period, person_link,
                     same_change, table)


def _past_families(conn, chi_phai_id):
    """Every closed Chi phái link of this Chi phái, newest first."""
    return conn.execute(
        "SELECT f.id, f.name, cl.start_date, cl.end_date "
        "FROM chi_phai_link cl JOIN family f ON f.id = cl.family_id "
        "WHERE cl.chi_phai_id = ? AND cl.end_date IS NOT NULL "
        "ORDER BY cl.end_date DESC, f.name_folded, cl.id",
        (chi_phai_id,),
    ).fetchall()


def _people_now(conn, families):
    """The Persons in these Families now, as ``[(id, full_name)]`` (each once)."""
    seen, out = set(), []
    for f in families:
        for p in people.family_members(conn, f["id"]):
            if p["id"] not in seen:
                seen.add(p["id"])
                out.append((p["id"], p["full_name"]))
    return out


# ---------------------------------------------------------------- /chi-phai

def list_page(req):
    conn = req.conn
    rows = people.list_chi_phai(conn)
    lines = []
    for c in rows:
        families = people.chi_phai_families(conn, c["id"])
        leader = people.current_truong_chi_phai(conn, c["id"])
        lines.append([
            f'<a href="/chi-phai/{c["id"]}">{vi(c["name"])}</a>',
            person_link(leader["person_id"], leader["full_name"]) if leader else ui.DASH,
            num(ui.fmt_date(leader["start_date"])) if leader else ui.DASH,
            num(len(families)),
            num(len(_people_now(conn, families))),
        ])
    body = (table([("Chi phái", False), ("Trưởng Chi phái", False), ("Since", True), ("Families now", True),
                   ("People now", True)], lines, "chi-phai")
            if lines else empty("No Chi phái yet. Add the first Chi phái."))
    actions = ui.link_button("Add a Chi phái", "/chi-phai/new", "primary")
    return Response.html(ui.page("Chi phái", list_panel("chi-phai-list", "Chi phái list", body), "chi-phai",
                                 sub=h(ui.plural(len(rows), "Chi phái", "Chi phái")), actions=actions))


# ---------------------------------------------------------------- /chi-phai/new

def _new_form(req, values=None, error=None, status=200):
    values = values or {}
    errors = field_errors(error, "new", {"name": "Chi phái"})
    inner = (
        ui.field("Chi phái name", "name", values.get("name", ""), error=errors.get("name"), required=True,
                 autocomplete="off", lang="vi", hint="For example: Chi phái Hòa Bình")
        + form_error(errors) + ui.button("Add Chi phái")
    )
    body = (f'<section class="panel narrow">{ui.form("/chi-phai/new", inner)}'
            '<p class="hint">Then put Families in it from each Family page.</p></section>')
    return Response.html(ui.page("Add a Chi phái", body, "chi-phai"), status)


def new_page(req):
    return _new_form(req)


def new_post(req):
    try:
        cid = people.add_chi_phai(req.conn, req.form.get("name"))
    except ValueError as exc:
        return _new_form(req, req.form, ("new", str(exc)), 400)
    return Response.redirect(ui.url(f"/chi-phai/{cid}", msg="Chi phái added."))


# ---------------------------------------------------------------- /chi-phai/<id>

def _families_panels(conn, cid, families):
    now_lines = [[family_link(f["id"], f["name"]), vi(f["address"]), num(ui.fmt_date(f["start_date"]))]
                 for f in families]
    now_body = (table([("Family", False), ("Address", False), ("Since", True)], now_lines, "families-now")
                if now_lines else empty("No Family is in this Chi phái now."))
    past = _past_families(conn, cid)
    past_lines = [[family_link(f["id"], f["name"]), *period(f["start_date"], f["end_date"])] for f in past]
    past_body = (table([("Family", False), ("From", True), ("To", True)], past_lines, "history")
                 if past_lines else empty("No Family has left this Chi phái."))
    hint = '<p class="hint">To add or move a Family, open its Family page.</p>'
    return (panel("families-now", "Families now", now_body + hint)
            + panel("families-before", "Families before", past_body, meta="Old Chi phái links, kept with their dates"))


def _person_select(conn, families, selected, error):
    """Pick a Person: first the people in this Chi phái now, then everyone else."""
    inside = _people_now(conn, families)
    inside_ids = {pid for pid, _ in inside}
    others = [(p["id"], p["full_name"]) for p in people.list_persons(conn) if p["id"] not in inside_ids]

    def options(pairs):
        return "".join(f'<option value="{pid}"{" selected" if str(pid) == str(selected) else ""}>{h(name)}</option>'
                       for pid, name in pairs)

    groups = '<option value="">— No Trưởng Chi phái —</option>'
    if inside:
        groups += f'<optgroup label="In this Chi phái">{options(inside)}</optgroup>'
    groups += f'<optgroup label="Everyone else">{options(others)}</optgroup>'
    error_html = f'<p class="error" id="truong-person-error">{h(error)}</p>' if error else ""
    invalid = ' aria-invalid="true" aria-describedby="truong-person-error"' if error else ""
    return ('<div class="field"><label for="truong-person">Person</label>'
            f'<select class="input" id="truong-person" name="person_id" lang="vi"{invalid}>{groups}</select>'
            f"{error_html}</div>")


def _truong_panel(conn, cid, families, error, vals):
    rows = people.truong_chi_phai_history(conn, cid)
    current = next((r for r in rows if r["end_date"] is None), None)
    errors = field_errors(error, "truong", {"start_date": "Start date", "person_id": "Person"})
    selected = vals.get("person_id", current["person_id"] if current else "")
    form = ui.form(f"/chi-phai/{cid}/truong", (
        _person_select(conn, families, selected, errors.get("person_id"))
        + date_field("Start date", "start_date", "truong-date", vals.get("start_date"), errors.get("start_date"),
                     min_date=latest_change(rows), hint="The past Trưởng Chi phái is kept with dates.")
        + form_error(errors) + ui.button("Set Trưởng Chi phái")))
    lines = [[person_link(r["person_id"], r["full_name"]), *period(r["start_date"], r["end_date"])]
             for r in newest_first(rows)]
    body = (table([("Person", False), ("From", True), ("To", True)], lines, "history")
            if lines else empty("No Trưởng Chi phái yet."))
    return panel("truong-chi-phai", "Trưởng Chi phái", body + change_box("Set Trưởng Chi phái", form, bool(errors)))


def _chi_phai_view(req, row, error=None, status=200):
    conn = req.conn
    cid = row["id"]
    vals = req.form if error else {}
    families = people.chi_phai_families(conn, cid)
    leader = people.current_truong_chi_phai(conn, cid)
    finding = [f"Trưởng Chi phái {leader['full_name']} since {ui.fmt_date(leader['start_date'])}" if leader
               else "No Trưởng Chi phái",
               ui.plural(len(families), "Family", "Families") + " now",
               ui.plural(len(_people_now(conn, families)), "Person", "People") + " now"]
    body = (f'<div class="grid chi-phai"><div class="span-8 stack">{_families_panels(conn, cid, families)}</div>'
            f'<div class="side-4 stack">{_truong_panel(conn, cid, families, error, vals)}</div></div>')
    actions = ui.link_button("Rename Chi phái", f"/chi-phai/{cid}/edit")
    return Response.html(ui.page(row["name"], body, "chi-phai", sub=h(" · ".join(finding)), actions=actions,
                                 lang="vi"), status)


def _row_or_none(req):
    return people.get_chi_phai(req.conn, req.params["id"])


def chi_phai_page(req):
    row = _row_or_none(req)
    if row is None:
        return not_found("Chi phái", "/chi-phai", "Go to Chi phái")
    return _chi_phai_view(req, row)


# ---------------------------------------------------------------- /chi-phai/<id>/edit

def _edit_form(req, row, values=None, error=None, status=200):
    """Rename a Chi phái. The name is a plain field, not history (its Families and Trưởng Chi phái are)."""
    values = values if values is not None else {"name": row["name"]}
    errors = field_errors(error, "edit", {"name": "Chi phái"})
    cid = row["id"]
    inner = (
        ui.field("Chi phái name", "name", values.get("name", ""), error=errors.get("name"), required=True,
                 autocomplete="off", lang="vi")
        + form_error(errors) + ui.button("Rename Chi phái")
    )
    body = (f'<section class="panel narrow">{ui.form(f"/chi-phai/{cid}/edit", inner)}'
            '<p class="hint">Its Families and its Trưởng Chi phái stay as they are, with their dates. '
            'The new name shows on every page at once.</p></section>')
    return Response.html(ui.page(f"Rename {row['name']}", body, "chi-phai", lang="vi",
                                 actions=ui.link_button("Back to the Chi phái", f"/chi-phai/{cid}")), status)


def edit_page(req):
    row = _row_or_none(req)
    if row is None:
        return not_found("Chi phái", "/chi-phai", "Go to Chi phái")
    return _edit_form(req, row)


def edit_post(req):
    row = _row_or_none(req)
    if row is None:
        return not_found("Chi phái", "/chi-phai", "Go to Chi phái")
    try:
        people.rename_chi_phai(req.conn, row["id"], req.form.get("name"))
    except ValueError as exc:
        return _edit_form(req, row, req.form, ("edit", str(exc)), 400)
    name = people.get_chi_phai(req.conn, row["id"])["name"]
    message = f"Renamed to {name}." if name != row["name"] else same_change(f"The name is already {name}.")
    return Response.redirect(ui.url(f"/chi-phai/{row['id']}", msg=message))


def truong_post(req):
    row = _row_or_none(req)
    if row is None:
        return not_found("Chi phái", "/chi-phai", "Go to Chi phái")
    conn, cid = req.conn, row["id"]
    try:
        day = past_or_today(req.form.get("start_date"), "Start date")
        person_id = req.form.get("person_id") or None
        before = people.current_truong_chi_phai(conn, cid)
        if person_id is None and before is None:
            message = same_change("This Chi phái has no Trưởng Chi phái.")
        elif person_id is None:
            people.set_truong_chi_phai(conn, cid, None, day)
            message = f"{before['full_name']} is no longer Trưởng Chi phái from {ui.fmt_date(day)}."
        elif before is not None and str(before["person_id"]) == person_id:
            message = same_change(f"{before['full_name']} is already Trưởng Chi phái.")
        else:
            people.set_truong_chi_phai(conn, cid, person_id, day)
            now = people.current_truong_chi_phai(conn, cid)
            message = f"{now['full_name']} is Trưởng Chi phái from {ui.fmt_date(day)}."
    except ValueError as exc:
        return _chi_phai_view(req, row, ("truong", str(exc)), 400)
    return Response.redirect(ui.url(f"/chi-phai/{cid}", msg=message))


ROUTES = [
    ("GET", "/chi-phai", list_page),
    ("GET", "/chi-phai/new", new_page),
    ("POST", "/chi-phai/new", new_post),
    ("GET", "/chi-phai/<int:id>", chi_phai_page),
    ("GET", "/chi-phai/<int:id>/edit", edit_page),
    ("POST", "/chi-phai/<int:id>/edit", edit_post),
    ("POST", "/chi-phai/<int:id>/truong", truong_post),
]
