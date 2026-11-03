"""Family pages: ``/families`` (list), ``/families/new``, ``/families/<id>`` (the people in it now
and before, the address, the Chi phái now and before, and the form to change the Chi phái) and
``/families/<id>/edit`` (the Family name and Address: plain fields, not history).

The Chi phái changes only through ``people.set_family_chi_phai`` (history is kept).
A Person joins or leaves a Family on the Person page.
Words on screen come from the text table (``t``/``tn``, section ``families``, and ``people`` for the
shared words); names and addresses are shown as stored.
"""

from .. import people, ui
from ..i18n import error_text, t, tn
from ..server import Response
from ..ui import h, vi
from . import documents as document_pages  # card C3: the shared Documents block
from .people import (change_box, chi_phai_link, date_field, empty, field_errors, form_error, history_headers,
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
    body = (table([(t("people.family"), False), (t("people.address"), False), (t("families.col_people_now"), True),
                   (t("people.chi_phai"), False)], lines, "families")
            if lines else empty(t("families.empty")))
    sub = h(f"{tn('families.count', len(families))} · "
            f"{t('families.in_family_now', people=tn('people.count', in_family))}")
    actions = ui.link_button(t("families.add"), "/families/new", "primary")
    return Response.html(ui.page(t("families.title"), list_panel("families", t("families.list"), body), "families",
                                 sub=sub, actions=actions))


# ---------------------------------------------------------------- /families/new

def _new_form(req, values=None, error=None, status=200):
    values = values or {}
    errors = field_errors(error, "new", {"name": "families.name"})
    inner = (
        ui.field(t("families.name"), "name", values.get("name", ""), error=errors.get("name"), required=True,
                 autocomplete="off", lang="vi", hint=t("families.name_hint"))
        + ui.textarea_field(t("people.address"), "address", values.get("address", ""), lang="vi",
                            hint=t("families.address_hint"))
        + form_error(errors) + ui.button(t("families.add_button"))
    )
    body = (f'<section class="panel narrow">{ui.form("/families/new", inner)}'
            f'<p class="hint">{h(t("families.new_hint"))}</p>'
            "</section>")
    return Response.html(ui.page(t("families.add"), body, "families"), status)


def new_page(req):
    return _new_form(req)


def add_family_from_form(conn, form):
    """Add a Family from the Add a Family form, for this page and the Hermes door. Returns the Family id."""
    return people.add_family(conn, form.get("name"), form.get("address"))


def new_post(req):
    try:
        fid = add_family_from_form(req.conn, req.form)
    except ValueError as exc:
        return _new_form(req, req.form, ("new", exc), 400)
    return Response.redirect(ui.url(f"/families/{fid}", msg=t("families.added")))


# ---------------------------------------------------------------- /families/<id>

def _people_panels(conn, fid):
    now = people.family_members(conn, fid)
    now_lines = [[person_link(p["id"], p["full_name"]), h(ui.family_role(p["family_role"])),
                  num(ui.fmt_date(p["start_date"]))] for p in now]
    now_body = (table([(t("people.person"), False), (t("people.family_role"), False), (t("people.since"), True)],
                      now_lines, "people-now")
                if now_lines else empty(t("families.no_one_now")))
    past = _past_people(conn, fid)
    past_lines = [[person_link(p["id"], p["full_name"]), h(ui.family_role(p["family_role"])),
                   *period(p["start_date"], p["end_date"])] for p in past]
    past_body = (table(history_headers("people.person", "people.family_role"), past_lines, "history")
                 if past_lines else empty(t("families.no_one_left")))
    hint = f'<p class="hint">{h(t("families.move_hint"))}</p>'
    return (panel("people-now", t("families.people_now"), now_body + hint)
            + panel("people-before", t("families.people_before"), past_body,
                    meta=h(t("families.people_before_meta"))))


def _chi_phai_panel(conn, fid, error, vals):
    rows = people.family_chi_phai_history(conn, fid)
    current = next((r for r in rows if r["end_date"] is None), None)
    errors = field_errors(error, "chi-phai", {"start_date": "people.start_date", "chi_phai_id": "people.chi_phai"})
    first = ("", t("families.leave_chi_phai")) if current else ("", t("families.no_chi_phai_option"))
    options = [first] + [(c["id"], c["name"]) for c in people.list_chi_phai(conn)]
    form = ui.form(f"/families/{fid}/chi-phai", (
        ui.select_field(t("people.chi_phai"), "chi_phai_id", options, id="chi-phai-id", lang="vi",
                        selected=vals.get("chi_phai_id", current["chi_phai_id"] if current else ""),
                        error=errors.get("chi_phai_id"))
        + date_field(t("people.start_date"), "start_date", "chi-phai-date", vals.get("start_date"),
                     errors.get("start_date"), min_date=latest_change(rows), hint=t("families.chi_phai_hint"))
        + form_error(errors) + ui.button(t("families.change_chi_phai"))))
    lines = [[chi_phai_link(r["chi_phai_id"], r["name"]), *period(r["start_date"], r["end_date"])]
             for r in newest_first(rows)]
    body = (table(history_headers("people.chi_phai"), lines, "history")
            if lines else empty(t("families.not_in_chi_phai")))
    return panel("chi-phai", t("people.chi_phai"),
                 body + change_box(t("families.change_chi_phai"), form, bool(errors)))


def _family_view(req, family, error=None, status=200):
    conn = req.conn
    fid = family["id"]
    vals = req.form if error else {}
    members = people.family_members(conn, fid)
    cp = people.current_chi_phai(conn, fid)
    finding = [t("people.count_now", count=tn("people.count", len(members)))]
    finding.append(t("families.chi_phai_since", name=cp["name"], date=ui.fmt_date(cp["start_date"])) if cp
                   else t("families.no_chi_phai"))
    address = panel("address", t("people.address"), f'<p>{vi(family["address"])}</p>',
                    meta=h(t("families.address_meta")))  # "Edit Family" in the title row changes it
    body = (f'<div class="grid family"><div class="span-8 stack">{_people_panels(conn, fid)}</div>'
            f'<div class="side-4 stack">{address}{_chi_phai_panel(conn, fid, error, vals)}'
            f'{document_pages.documents_panel(conn, family_id=fid)}</div></div>')
    actions = (ui.link_button(t("families.edit"), f"/families/{fid}/edit")
               + ui.link_button(t("money.giving_statement"), statement_href(family_id=fid)))
    return Response.html(ui.page(family["name"], body, "families", sub=h(" · ".join(finding)), actions=actions,
                                 lang="vi"), status)


def _family_or_none(req):
    return people.get_family(req.conn, req.params["id"])


def family_page(req):
    family = _family_or_none(req)
    if family is None:
        return not_found("people.family", "/families", "families.go")
    return _family_view(req, family)


# ---------------------------------------------------------------- /families/<id>/edit

def _delete_box(fid, error=None):
    """The last block of the Edit page: Delete, in the negative colour. It asks once more first."""
    body = (ui.form(f"/families/{fid}/delete", ui.button(t("families.delete"), "danger"))
            + (f'<p class="error" role="alert">{h(error_text(error))}</p>' if error else "")
            + f'<p class="hint">{h(t("families.delete_hint"))}</p>')
    return panel("delete", t("core.btn_delete"), body, cls="narrow no-print")


def _edit_form(req, family, values=None, error=None, status=200, delete_error=None):
    """Family name and Address. They are plain fields, not history (who is in the Family and its Chi phái are)."""
    values = values if values is not None else {"name": family["name"], "address": family["address"] or ""}
    errors = field_errors(error, "edit", {"name": "families.name"})
    fid = family["id"]
    inner = (
        ui.field(t("families.name"), "name", values.get("name", ""), error=errors.get("name"), required=True,
                 autocomplete="off", lang="vi")
        + ui.textarea_field(t("people.address"), "address", values.get("address", ""), lang="vi",
                            hint=t("families.address_hint"))
        + form_error(errors) + ui.button(t("core.btn_save"))
    )
    link = f'<a href="/families/{fid}">{h(t("families.family_page"))}</a>'
    body = (f'<div class="stack"><section class="panel narrow">{ui.form(f"/families/{fid}/edit", inner)}'
            f'<p class="hint">{ui.t_html("families.edit_hint", link=link)}</p></section>'
            f'{_delete_box(fid, delete_error)}</div>')
    return Response.html(ui.page(t("people.edit_title", name=family["name"]), body, "families", lang="vi",
                                 actions=ui.link_button(t("families.back"), f"/families/{fid}")), status)


def edit_page(req):
    family = _family_or_none(req)
    if family is None:
        return not_found("people.family", "/families", "families.go")
    return _edit_form(req, family)


def edit_post(req):
    family = _family_or_none(req)
    if family is None:
        return not_found("people.family", "/families", "families.go")
    try:
        people.update_family(req.conn, family["id"], name=req.form.get("name"), address=req.form.get("address"))
    except ValueError as exc:
        return _edit_form(req, family, req.form, ("edit", exc), 400)
    return Response.redirect(ui.url(f"/families/{family['id']}", msg=t("families.saved")))


def delete_post(req):
    family = _family_or_none(req)
    if family is None:
        return not_found("people.family", "/families", "families.go")
    fid = family["id"]
    if req.form.get("confirm") != "yes":
        form = ui.form(f"/families/{fid}/delete", ui.hidden("confirm", "yes")
                       + ui.button(t("families.yes_delete"), "danger"))
        body = (f'<section class="panel narrow" data-panel="confirm">'
                f'<p class="lead">{ui.t_html("families.confirm", name=vi(family["name"]))}</p>'
                f'<p class="hint">{h(t("families.confirm_hint"))}</p>'
                f'<div class="confirm-actions">{form}{ui.link_button(t("core.btn_cancel"), f"/families/{fid}/edit")}'
                f'</div></section>')
        return Response.html(ui.page(t("families.confirm_title"), body, "families"))
    try:
        people.delete_family(req.conn, fid)
    except ValueError as exc:
        return _edit_form(req, family, status=400, delete_error=exc)
    return Response.redirect(ui.url("/families", msg=t("families.deleted", name=family["name"])))


def chi_phai_post(req):
    family = _family_or_none(req)
    if family is None:
        return not_found("people.family", "/families", "families.go")
    conn, fid = req.conn, family["id"]
    try:
        day = past_or_today(req.form.get("start_date"), "people.start_date")
        new_id = req.form.get("chi_phai_id") or None
        before = people.current_chi_phai(conn, fid)
        if new_id is None and before is None:
            message = same_change(t("families.not_in_chi_phai"))
        elif new_id is None:
            people.set_family_chi_phai(conn, fid, None, day)
            message = t("families.chi_phai_left", name=before["name"], date=ui.fmt_date(day))
        elif before is not None and str(before["chi_phai_id"]) == new_id:
            message = same_change(t("families.chi_phai_same", name=before["name"]))
        else:
            people.set_family_chi_phai(conn, fid, new_id, day)
            message = t("families.chi_phai_now", name=people.current_chi_phai(conn, fid)["name"],
                        date=ui.fmt_date(day))
    except ValueError as exc:
        return _family_view(req, family, ("chi-phai", exc), 400)
    return Response.redirect(ui.url(f"/families/{fid}", msg=message))


ROUTES = [
    ("GET", "/families", list_page),
    ("GET", "/families/new", new_page),
    ("POST", "/families/new", new_post),
    ("GET", "/families/<int:id>", family_page),
    ("GET", "/families/<int:id>/edit", edit_page),
    ("POST", "/families/<int:id>/edit", edit_post),
    ("POST", "/families/<int:id>/chi-phai", chi_phai_post),
    ("POST", "/families/<int:id>/delete", delete_post),
]
