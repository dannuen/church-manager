"""Chi phái pages: ``/chi-phai`` (list), ``/chi-phai/new``, ``/chi-phai/<id>`` (Families now and
before, the Trưởng Chi phái now and before, and the form to set the Trưởng Chi phái) and
``/chi-phai/<id>/edit`` (a new name: a plain field, not history).

The Trưởng Chi phái changes only through ``people.set_truong_chi_phai`` (history is kept).
A Family changes its Chi phái on the Family page.
Words on screen come from the text table (``t``/``tn``, section ``chi_phai``, and ``people`` /
``families`` for the shared words); names are shown as stored.
"""

from .. import people, ui
from ..i18n import t, tn
from ..server import Response
from ..ui import h, vi
from .people import (change_box, date_field, empty, family_link, field_errors, form_error, history_headers,
                     latest_change, list_panel, newest_first, not_found, num, panel, past_or_today, period,
                     person_link, same_change, table)


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
    body = (table([(t("people.chi_phai"), False), (t("chi_phai.truong"), False), (t("people.since"), True),
                   (t("chi_phai.col_families_now"), True), (t("families.col_people_now"), True)], lines, "chi-phai")
            if lines else empty(t("chi_phai.empty")))
    actions = ui.link_button(t("chi_phai.add"), "/chi-phai/new", "primary")
    return Response.html(ui.page(t("chi_phai.title"), list_panel("chi-phai-list", t("chi_phai.list"), body),
                                 "chi-phai", sub=h(tn("chi_phai.count", len(rows))), actions=actions))


# ---------------------------------------------------------------- /chi-phai/new

def _new_form(req, values=None, error=None, status=200):
    values = values or {}
    errors = field_errors(error, "new", {"name": "people.chi_phai"})
    inner = (
        ui.field(t("chi_phai.name"), "name", values.get("name", ""), error=errors.get("name"), required=True,
                 autocomplete="off", lang="vi", hint=t("chi_phai.name_hint"))
        + form_error(errors) + ui.button(t("chi_phai.add_button"))
    )
    body = (f'<section class="panel narrow">{ui.form("/chi-phai/new", inner)}'
            f'<p class="hint">{h(t("chi_phai.new_hint"))}</p></section>')
    return Response.html(ui.page(t("chi_phai.add"), body, "chi-phai"), status)


def new_page(req):
    return _new_form(req)


def new_post(req):
    try:
        cid = people.add_chi_phai(req.conn, req.form.get("name"))
    except ValueError as exc:
        return _new_form(req, req.form, ("new", exc), 400)
    return Response.redirect(ui.url(f"/chi-phai/{cid}", msg=t("chi_phai.added")))


# ---------------------------------------------------------------- /chi-phai/<id>

def _families_panels(conn, cid, families):
    now_lines = [[family_link(f["id"], f["name"]), vi(f["address"]), num(ui.fmt_date(f["start_date"]))]
                 for f in families]
    now_body = (table([(t("people.family"), False), (t("people.address"), False), (t("people.since"), True)],
                      now_lines, "families-now")
                if now_lines else empty(t("chi_phai.no_family_now")))
    past = _past_families(conn, cid)
    past_lines = [[family_link(f["id"], f["name"]), *period(f["start_date"], f["end_date"])] for f in past]
    past_body = (table(history_headers("people.family"), past_lines, "history")
                 if past_lines else empty(t("chi_phai.no_family_left")))
    hint = f'<p class="hint">{h(t("chi_phai.move_hint"))}</p>'
    return (panel("families-now", t("chi_phai.families_now"), now_body + hint)
            + panel("families-before", t("chi_phai.families_before"), past_body,
                    meta=h(t("chi_phai.families_before_meta"))))


def _person_select(conn, families, selected, error):
    """Pick a Person: first the people in this Chi phái now, then everyone else."""
    inside = _people_now(conn, families)
    inside_ids = {pid for pid, _ in inside}
    others = [(p["id"], p["full_name"]) for p in people.list_persons(conn) if p["id"] not in inside_ids]

    def options(pairs):
        return "".join(f'<option value="{pid}"{" selected" if str(pid) == str(selected) else ""}>{h(name)}</option>'
                       for pid, name in pairs)

    groups = f'<option value="">{h(t("chi_phai.no_truong_option"))}</option>'
    if inside:
        groups += f'<optgroup label="{h(t("chi_phai.inside"))}">{options(inside)}</optgroup>'
    groups += f'<optgroup label="{h(t("chi_phai.others"))}">{options(others)}</optgroup>'
    error_html = f'<p class="error" id="truong-person-error">{h(error)}</p>' if error else ""
    invalid = ' aria-invalid="true" aria-describedby="truong-person-error"' if error else ""
    return (f'<div class="field"><label for="truong-person">{h(t("people.person"))}</label>'
            f'<select class="input" id="truong-person" name="person_id" lang="vi"{invalid}>{groups}</select>'
            f"{error_html}</div>")


def _truong_panel(conn, cid, families, error, vals):
    rows = people.truong_chi_phai_history(conn, cid)
    current = next((r for r in rows if r["end_date"] is None), None)
    errors = field_errors(error, "truong", {"start_date": "people.start_date", "person_id": "people.person"})
    selected = vals.get("person_id", current["person_id"] if current else "")
    form = ui.form(f"/chi-phai/{cid}/truong", (
        _person_select(conn, families, selected, errors.get("person_id"))
        + date_field(t("people.start_date"), "start_date", "truong-date", vals.get("start_date"),
                     errors.get("start_date"), min_date=latest_change(rows), hint=t("chi_phai.truong_hint"))
        + form_error(errors) + ui.button(t("chi_phai.set_truong"))))
    lines = [[person_link(r["person_id"], r["full_name"]), *period(r["start_date"], r["end_date"])]
             for r in newest_first(rows)]
    body = (table(history_headers("people.person"), lines, "history")
            if lines else empty(t("chi_phai.no_truong_yet")))
    return panel("truong-chi-phai", t("chi_phai.truong"),
                 body + change_box(t("chi_phai.set_truong"), form, bool(errors)))


def _chi_phai_view(req, row, error=None, status=200):
    conn = req.conn
    cid = row["id"]
    vals = req.form if error else {}
    families = people.chi_phai_families(conn, cid)
    leader = people.current_truong_chi_phai(conn, cid)
    finding = [t("chi_phai.truong_since", name=leader["full_name"], date=ui.fmt_date(leader["start_date"])) if leader
               else t("chi_phai.no_truong"),
               t("people.count_now", count=tn("families.count", len(families))),
               t("people.count_now", count=tn("people.count", len(_people_now(conn, families))))]
    body = (f'<div class="grid chi-phai"><div class="span-8 stack">{_families_panels(conn, cid, families)}</div>'
            f'<div class="side-4 stack">{_truong_panel(conn, cid, families, error, vals)}</div></div>')
    actions = ui.link_button(t("chi_phai.rename"), f"/chi-phai/{cid}/edit")
    return Response.html(ui.page(row["name"], body, "chi-phai", sub=h(" · ".join(finding)), actions=actions,
                                 lang="vi"), status)


def _row_or_none(req):
    return people.get_chi_phai(req.conn, req.params["id"])


def chi_phai_page(req):
    row = _row_or_none(req)
    if row is None:
        return not_found("people.chi_phai", "/chi-phai", "chi_phai.go")
    return _chi_phai_view(req, row)


# ---------------------------------------------------------------- /chi-phai/<id>/edit

def _edit_form(req, row, values=None, error=None, status=200):
    """Rename a Chi phái. The name is a plain field, not history (its Families and Trưởng Chi phái are)."""
    values = values if values is not None else {"name": row["name"]}
    errors = field_errors(error, "edit", {"name": "people.chi_phai"})
    cid = row["id"]
    inner = (
        ui.field(t("chi_phai.name"), "name", values.get("name", ""), error=errors.get("name"), required=True,
                 autocomplete="off", lang="vi")
        + form_error(errors) + ui.button(t("chi_phai.rename"))
    )
    body = (f'<section class="panel narrow">{ui.form(f"/chi-phai/{cid}/edit", inner)}'
            f'<p class="hint">{h(t("chi_phai.rename_hint"))}</p></section>')
    return Response.html(ui.page(t("chi_phai.rename_title", name=row["name"]), body, "chi-phai", lang="vi",
                                 actions=ui.link_button(t("chi_phai.back"), f"/chi-phai/{cid}")), status)


def edit_page(req):
    row = _row_or_none(req)
    if row is None:
        return not_found("people.chi_phai", "/chi-phai", "chi_phai.go")
    return _edit_form(req, row)


def edit_post(req):
    row = _row_or_none(req)
    if row is None:
        return not_found("people.chi_phai", "/chi-phai", "chi_phai.go")
    try:
        people.rename_chi_phai(req.conn, row["id"], req.form.get("name"))
    except ValueError as exc:
        return _edit_form(req, row, req.form, ("edit", exc), 400)
    name = people.get_chi_phai(req.conn, row["id"])["name"]
    message = (t("chi_phai.renamed", name=name) if name != row["name"]
               else same_change(t("chi_phai.name_same", name=name)))
    return Response.redirect(ui.url(f"/chi-phai/{row['id']}", msg=message))


def truong_post(req):
    row = _row_or_none(req)
    if row is None:
        return not_found("people.chi_phai", "/chi-phai", "chi_phai.go")
    conn, cid = req.conn, row["id"]
    try:
        day = past_or_today(req.form.get("start_date"), "people.start_date")
        person_id = req.form.get("person_id") or None
        before = people.current_truong_chi_phai(conn, cid)
        if person_id is None and before is None:
            message = same_change(t("chi_phai.truong_none"))
        elif person_id is None:
            people.set_truong_chi_phai(conn, cid, None, day)
            message = t("chi_phai.truong_ended", name=before["full_name"], date=ui.fmt_date(day))
        elif before is not None and str(before["person_id"]) == person_id:
            message = same_change(t("chi_phai.truong_same", name=before["full_name"]))
        else:
            people.set_truong_chi_phai(conn, cid, person_id, day)
            now = people.current_truong_chi_phai(conn, cid)
            message = t("chi_phai.truong_now", name=now["full_name"], date=ui.fmt_date(day))
    except ValueError as exc:
        return _chi_phai_view(req, row, ("truong", exc), 400)
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
