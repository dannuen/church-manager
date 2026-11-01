"""People pages: ``/people`` (list, Status filter, quick search), ``/people/new``,
``/people/<id>`` (the whole story and the forms that change it) and ``/people/<id>/edit``.

The helpers at the top are shared by the other C1 pages (Families, Chi phái, Care).

Rules kept here:
- History changes go only through the data layer (``people.set_status``, ``set_family``,
  ``set_ministry``, ...). Never an SQL UPDATE on a history table.
- A start date after today is refused (the data layer would count it as current at once).
- Private notes show only on this Person page, inside ``.no-print``; never in the story list,
  never on another page. ``print.css`` hides ``.no-print``.
"""

import datetime as _dt

from .. import care, lists, people, story, text, ui
from .. import search as person_search
from ..schema import FAMILY_ROLES, MINISTRY_ROLES
from ..server import Response
from ..ui import clamp2, h, vi
from . import documents as document_pages  # card C3 (a module import: pages/documents.py imports this one)

GENDERS = (("", "—"), ("M", "Male"), ("F", "Female"))
GENDER_WORDS = {"M": "Male", "F": "Female"}
PRIVATE_LABEL = "Private note — only you see this"
SEARCH_LIMIT = 100_000  # the quick search on /people keeps every match


# ---------------------------------------------------------------- shared helpers (C1 pages)

def today_text():
    return _dt.date.today().isoformat()


def past_or_today(value, what):
    """``value`` as ``YYYY-MM-DD`` when it is a real date on or before today.

    Otherwise ``ValueError``. The message starts with ``what``, so :func:`field_errors`
    puts it next to the field with that label.
    """
    day = text.check_date(value or "", what)
    if day > today_text():
        raise ValueError(f"{what} cannot be after today ({ui.fmt_date(today_text())}). "
                         "Use today or an earlier date.")
    return day


def field_errors(error, form_key, labels):
    """Where to show a refused change.

    ``error`` is ``(form_key, message)`` or ``None``. For the form ``form_key`` this returns
    ``{field_name: message}``: the field whose label the message starts with, or ``""``
    (the whole form) when no label fits. Other forms get ``{}``.
    """
    if not error or error[0] != form_key:
        return {}
    message = error[1]
    for name, label in labels.items():
        if message.startswith(label):
            return {name: message}
    return {"": message}


def form_error(errors):
    """The form-level error sentence (just above the Save button), or nothing."""
    message = errors.get("")
    return f'<p class="error" role="alert">{h(message)}</p>' if message else ""


def date_field(label, name, fid, value=None, error=None, min_date=None, hint=None):
    """A required ``<input type="date">``: today by default, never after today."""
    return ui.field(label, name, value or today_text(), type="date", id=fid, error=error,
                    max=today_text(), min=min_date, required=True, hint=hint)


def table(headers, rows, cls=""):
    """A table. ``headers``: ``[(text, numeric), ...]`` or ``[(text, numeric, column class), ...]``;
    ``rows``: lists of trusted cell HTML. The column class is on the header and on every cell of that
    column (``act``: a column of text actions only, which print.css leaves off paper).
    Every body row has ``data-row``. On a phone each row becomes two lines (style.css)."""
    def cell(tag, content, header, extra=""):
        names = (["n"] if header[1] else []) + list(header[2:3])
        cls = f' class="{" ".join(names)}"' if names else ""
        return f"<{tag}{extra}{cls}>{content}</{tag}>"

    head = "".join(cell("th", h(c[0]), c, ' scope="col"') for c in headers)
    body = "".join(
        "<tr data-row>" + "".join(cell("td", c, headers[i]) for i, c in enumerate(r)) + "</tr>"
        for r in rows
    )
    return (f'<div class="table-wrap"><table class="list {h(cls)}"><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def period(start, end):
    """``[From, To]`` cells of a history row. An open row says ``now``."""
    return [f'<span class="num">{h(ui.fmt_date(start))}</span>',
            f'<span class="num">{h(ui.fmt_date(end))}</span>' if end else '<span class="faint">now</span>']


def latest_change(rows):
    """The last change date of one history line: a new change may not start before it."""
    return max((r["end_date"] or r["start_date"] for r in rows), default=None)


def newest_first(rows):
    return sorted(rows, key=lambda r: (r["start_date"], r["id"]), reverse=True)


def panel(name, title, body, meta="", cls="", head_right="", foot=""):
    """A ``<section class="panel" data-panel=NAME>`` with an h2. ``meta``/``body``/``foot`` are trusted HTML."""
    meta_html = f'<span class="meta">{meta}</span>' if meta else ""
    foot_html = f"<footer>{foot}</footer>" if foot else ""
    return (f'<section class="panel {cls}" data-panel="{h(name)}" aria-labelledby="p-{h(name)}">'
            f'<header><div><h2 id="p-{h(name)}">{h(title)}</h2>{meta_html}</div>{head_right}</header>'
            f"{body}{foot_html}</section>")


def list_panel(name, label, body):
    """A full list in a panel with no visible header: the h1 and its line already name it."""
    return f'<section class="panel list-panel" data-panel="{h(name)}" aria-label="{h(label)}">{body}</section>'


def change_box(summary, form_html, is_open=False):
    """A form folded under one click (``<details>``). It opens by itself when it has an error."""
    return f'<details class="change"{" open" if is_open else ""}><summary>{h(summary)}</summary>{form_html}</details>'


def empty(sentence):
    return f'<p class="empty">{h(sentence)}</p>'


def card_link(text_, href):
    return f'<a class="card-link" href="{h(href)}">{h(text_)}</a>'


def not_found(what, back_href, back_text):
    body = f'<p class="lead">There is no {h(what)} with this number.</p><p><a href="{h(back_href)}">{h(back_text)}</a></p>'
    return Response.html(ui.page(f"{what} not found", body), 404)


def person_link(pid, name, anchor=""):
    """A link to the Person page; ``anchor`` (such as ``"#private-note"``) goes to one panel of it."""
    return f'<a href="/people/{int(pid)}{h(anchor)}">{vi(name)}</a>'


def family_link(fid, name):
    return f'<a href="/families/{int(fid)}">{vi(name)}</a>'


def chi_phai_link(cid, name):
    return f'<a href="/chi-phai/{int(cid)}">{vi(name)}</a>'


def num(value):
    return f'<span class="num">{h(value)}</span>'


def statement_href(year=None, **giver):
    """The Giving statement page of card C2 for one Person or one Family."""
    return ui.url("/money/statement", **giver, year=year or _dt.date.today().year)


def same_change(message):
    """The flash text when a form changes nothing (the same value as now)."""
    return f"{message} Nothing changed."


def list_choice(conn, value, list_name, label):
    """The item of ``list_name`` picked in a form's ``<select>``, or ``ValueError``.

    The refusal starts with ``label``, a glossary word ("Status", "Ministry"), so
    :func:`field_errors` puts it next to that field and the pastor never reads "Item".
    A hidden item is still accepted (old rows keep it); the data layer decides the rest.
    """
    try:
        item = lists.get_item(conn, value or "")
    except ValueError:  # not a whole number above 0
        item = None
    if item is None or item["list_name"] != list_name:
        raise ValueError(f"{label} must be one of the choices in the list.")
    return item


# ---------------------------------------------------------------- /people

def _status_counts(rows):
    counts = {}
    for r in rows:
        counts[r["status_id"]] = counts.get(r["status_id"], 0) + 1
    return counts


def _chips(items, counts, total, selected, q):
    chips = [("", "All", total)]
    chips += [(str(i["id"]), i["name"], counts.get(i["id"], 0)) for i in items if i["active"] or counts.get(i["id"])]
    if counts.get(None):
        chips.append(("none", "No Status", counts[None]))
    out = []
    for value, label, n in chips:
        href = ui.url("/people", status=value or None, q=q or None)
        current = ' aria-current="true"' if value == selected else ""
        out.append(f'<a class="chip" href="{h(href)}"{current}>{h(label)} <span class="num">{n}</span></a>')
    return f'<div class="chips" role="group" aria-label="Filter by Status">{"".join(out)}</div>'


def list_page(req):
    conn = req.conn
    everyone = people.list_persons(conn)
    selected = (req.query.get("status") or "").strip()
    q = (req.query.get("q") or "").strip()
    rows = everyone
    if selected == "none":
        rows = [r for r in rows if r["status_id"] is None]
    elif selected:
        rows = [r for r in rows if str(r["status_id"]) == selected]
    if q:
        found = {r["id"] for r in person_search.search_persons(conn, q, limit=SEARCH_LIMIT)}
        rows = [r for r in rows if r["id"] in found]

    chi_phai_of = {}
    lines = []
    for r in rows:
        fam = people.current_family(conn, r["id"])
        family_cell, chi_cell = ui.DASH, ui.DASH
        if fam is not None:
            family_cell = f'{family_link(fam["family_id"], fam["name"])} <span class="faint">{h(fam["family_role"])}</span>'
            if fam["family_id"] not in chi_phai_of:
                chi_phai_of[fam["family_id"]] = people.current_chi_phai(conn, fam["family_id"])
            cp = chi_phai_of[fam["family_id"]]
            if cp is not None:
                chi_cell = chi_phai_link(cp["chi_phai_id"], cp["name"])
        lines.append([
            person_link(r["id"], r["full_name"]),
            h(r["status_name"]) if r["status_name"] else ui.DASH,
            family_cell,
            chi_cell,
            num(r["phone"]) if r["phone"] else ui.DASH,
        ])

    search = (
        '<form class="search-form toolbar" action="/people" method="get" role="search">'
        '<label for="people-q">Find in this list</label>'
        f'<div class="search-line"><input class="input" id="people-q" name="q" type="search" value="{h(q)}" '
        'autocomplete="off" placeholder="With or without accents">'
        + (ui.hidden("status", selected) if selected else "")
        + '<button class="btn secondary" type="submit">Search</button>'
        + (f'<a class="btn secondary" href="{h(ui.url("/people", status=selected or None))}">Clear</a>' if q else "")
        + "</div></form>"
    )
    if lines:
        body = table([("Person", False), ("Status", False), ("Family", False), ("Chi phái", False),
                      ("Phone", False)], lines, "people")
    elif not everyone:
        body = empty("No Person yet. Add the first Person.")
    elif q:
        body = empty(f"No Person matches “{q}” here.")
    else:
        body = empty("No Person has this Status now.")

    items = lists.get_list(conn, "status", include_hidden=True)
    toolbar = (f'<div class="list-toolbar">{_chips(items, _status_counts(everyone), len(everyone), selected, q)}'
               f"{search}</div>")
    content = toolbar + list_panel("people", "People list", body)
    shown = ui.plural(len(everyone), "Person", "People")
    sub = h(shown) if len(rows) == len(everyone) else h(f"{len(rows)} of {shown}")
    actions = ui.link_button("Add a Person", "/people/new", "primary")
    return Response.html(ui.page("People", content, "people", sub=sub, actions=actions))


# ---------------------------------------------------------------- /people/new and /people/<id>/edit

_PERSON_LABELS = {"full_name": "Full name", "gender": "Gender", "birth_date": "Birth date",
                  "start_date": "Start date", "status_id": "Status"}


def _plain_fields(values, errors):
    v = values.get
    return (
        ui.field("Full name", "full_name", v("full_name", ""), error=errors.get("full_name"), required=True,
                 autocomplete="off", lang="vi")
        + ui.select_field("Gender", "gender", GENDERS, selected=v("gender", ""), error=errors.get("gender"))
        + ui.field("Birth date", "birth_date", v("birth_date", ""), type="date", max=today_text(),
                   error=errors.get("birth_date"), hint="Leave empty if you do not know it.")
        + ui.field("Phone", "phone", v("phone", ""), type="tel", autocomplete="off")
        + ui.textarea_field("Own address", "address", v("address", ""), lang="vi",
                            hint="Used when the Person is not in a Family.")
        + ui.textarea_field("Note", "note", v("note", ""), lang="vi",
                            hint="A normal note. A Private note is added on the Person page.")
    )


def _new_form(req, values=None, error=None, status=200):
    conn = req.conn
    values = values or {}
    errors = field_errors(error, "new", _PERSON_LABELS)
    items = lists.get_list(conn, "status")
    visitor = next((i["id"] for i in items if i["code"] == "visitor"), None)
    inner = (
        _plain_fields(values, errors)
        + ui.select_field("First Status", "status_id", [(i["id"], i["name"]) for i in items],
                          selected=values.get("status_id", visitor), error=errors.get("status_id"))
        + date_field("Start date", "start_date", "f-start_date", values.get("start_date"), errors.get("start_date"),
                     hint="The day this Status began. Not after today.")
        + form_error(errors) + ui.button("Add Person")
    )
    body = f'<section class="panel narrow">{ui.form("/people/new", inner)}</section>'
    return Response.html(ui.page("Add a Person", body, "people"), status)


def new_page(req):
    return _new_form(req)


def new_post(req):
    f = req.form
    try:
        if f.get("birth_date"):
            past_or_today(f["birth_date"], "Birth date")
        start = past_or_today(f.get("start_date"), "Start date")
        status_id = list_choice(req.conn, f["status_id"], "status", "Status")["id"] if f.get("status_id") else None
        pid = people.add_person(req.conn, f.get("full_name"), gender=f.get("gender"), birth_date=f.get("birth_date"),
                                phone=f.get("phone"), address=f.get("address"), note=f.get("note"),
                                status_id=status_id, start_date=start)
    except ValueError as exc:
        return _new_form(req, f, ("new", str(exc)), 400)
    return Response.redirect(ui.url(f"/people/{pid}", msg="Person added."))


def _edit_form(req, person, values=None, error=None, status=200):
    values = values if values is not None else {
        k: person[k] or "" for k in ("full_name", "gender", "birth_date", "phone", "address", "note")
    }
    errors = field_errors(error, "edit", _PERSON_LABELS)
    pid = person["id"]
    inner = _plain_fields(values, errors) + form_error(errors) + ui.button("Save")
    body = (f'<section class="panel narrow">{ui.form(f"/people/{pid}/edit", inner)}'
            f'<p class="hint">Status, Family and Ministry keep their history: change them on the '
            f'<a href="/people/{pid}">Person page</a>.</p></section>')
    return Response.html(ui.page(f"Edit {person['full_name']}", body, "people", lang="vi"), status)


def edit_page(req):
    person = people.get_person(req.conn, req.params["id"])
    if person is None:
        return not_found("Person", "/people", "Go to People")
    return _edit_form(req, person)


def edit_post(req):
    person = people.get_person(req.conn, req.params["id"])
    if person is None:
        return not_found("Person", "/people", "Go to People")
    f = req.form
    try:
        if f.get("birth_date"):
            past_or_today(f["birth_date"], "Birth date")
        people.update_person(req.conn, person["id"], full_name=f.get("full_name"), gender=f.get("gender"),
                             birth_date=f.get("birth_date"), phone=f.get("phone"), address=f.get("address"),
                             note=f.get("note"))
    except ValueError as exc:
        return _edit_form(req, person, f, ("edit", str(exc)), 400)
    return Response.redirect(ui.url(f"/people/{person['id']}", msg="Details saved."))


# ---------------------------------------------------------------- /people/<id>

def _status_panel(conn, pid, error, vals):
    rows = people.status_history(conn, pid)
    current = next((r for r in rows if r["end_date"] is None), None)
    errors = field_errors(error, "status", {"start_date": "Start date", "status_id": "Status"})
    items = lists.get_list(conn, "status")
    form = ui.form(f"/people/{pid}/status", (
        ui.select_field("New Status", "status_id", [(i["id"], i["name"]) for i in items], id="status-id",
                        selected=vals.get("status_id") or (current["status_id"] if current else None),
                        error=errors.get("status_id"))
        + date_field("Start date", "start_date", "status-date", vals.get("start_date"), errors.get("start_date"),
                     min_date=latest_change(rows))
        + form_error(errors) + ui.button("Change Status", "secondary")))
    lines = [[h(r["name"]), *period(r["start_date"], r["end_date"])] for r in newest_first(rows)]
    body = (table([("Status", False), ("From", True), ("To", True)], lines, "history")
            if lines else empty("No Status yet."))
    return panel("status", "Status", body + change_box("Change Status", form, bool(errors)))


def _family_panel(conn, pid, error, vals):
    rows = people.family_history(conn, pid)
    current = next((r for r in rows if r["end_date"] is None), None)
    errors = field_errors(error, "family", {"start_date": "Start date", "family_role": "Family role",
                                            "family_id": "Family"})
    first = ("", "— Leave the Family —") if current else ("", "— Not in a Family —")
    options = [first] + [(f["id"], f["name"]) for f in people.list_families(conn)]
    role = vals.get("family_role") or (current["family_role"] if current else "Head")
    form = ui.form(f"/people/{pid}/family", (
        ui.select_field("Family", "family_id", options, id="family-id", lang="vi",
                        selected=vals.get("family_id", current["family_id"] if current else ""),
                        error=errors.get("family_id"))
        + ui.select_field("Family role", "family_role", [(r, r) for r in FAMILY_ROLES], id="family-role",
                          selected=role, error=errors.get("family_role"))
        + date_field("Start date", "start_date", "family-date", vals.get("start_date"), errors.get("start_date"),
                     min_date=latest_change(rows), hint="The day of the move. The old Family link is kept.")
        + form_error(errors) + ui.button("Save Family", "secondary")))
    now = ""
    if current is not None:
        cp = people.current_chi_phai(conn, current["family_id"])
        address = people.person_address(conn, pid)
        now = ('<dl class="kv">'
               f'<div><dt>Family</dt><dd>{family_link(current["family_id"], current["name"])}</dd></div>'
               f'<div><dt>Family role</dt><dd>{h(current["family_role"])}</dd></div>'
               f'<div><dt>Chi phái</dt><dd>{chi_phai_link(cp["chi_phai_id"], cp["name"]) if cp else ui.DASH}</dd></div>'
               f'<div><dt>Address</dt><dd>{vi(address)}</dd></div>'
               "</dl>")
    lines = [[family_link(r["family_id"], r["name"]), h(r["family_role"]), *period(r["start_date"], r["end_date"])]
             for r in newest_first(rows)]
    body = now + (table([("Family", False), ("Family role", False), ("From", True), ("To", True)], lines, "history")
                  if lines else empty("Not in a Family. The Person's own address is used."))
    foot = card_link("Add a Family", "/families/new")
    return panel("family", "Family", body + change_box("Set or leave a Family", form, bool(errors)), foot=foot)


def _ministry_panel(conn, pid, error, vals):
    rows = people.ministry_history(conn, pid)
    current = [r for r in rows if r["end_date"] is None]
    # "Ministry role" before "Ministry": field_errors takes the first label a message starts with.
    errors = field_errors(error, "ministry", {"start_date": "Start date", "ministry_role": "Ministry role",
                                              "ministry_id": "Ministry"})
    items = lists.get_list(conn, "ministry")
    form = ui.form(f"/people/{pid}/ministry", (
        ui.select_field("Ministry", "ministry_id", [(i["id"], i["name"]) for i in items], id="ministry-id",
                        selected=vals.get("ministry_id"), error=errors.get("ministry_id"))
        + ui.select_field("Ministry role", "ministry_role",
                          [(r, r) for r in MINISTRY_ROLES] + [("", "Stop serving in this Ministry")],
                          id="ministry-role", selected=vals.get("ministry_role", "Member"),
                          error=errors.get("ministry_role"))
        + date_field("Start date", "start_date", "ministry-date", vals.get("start_date"), errors.get("start_date"))
        + form_error(errors) + ui.button("Save Ministry", "secondary")))
    lines = [[h(r["name"]), h(r["ministry_role"]), *period(r["start_date"], r["end_date"])] for r in newest_first(rows)]
    body = (table([("Ministry", False), ("Ministry role", False), ("From", True), ("To", True)], lines, "history")
            if lines else empty("Not serving in a Ministry."))
    meta = (h(" · ".join(f"{r['name']} ({r['ministry_role']})" for r in current)) if current
            else "Not serving now")
    return panel("ministries", "Ministries", body + change_box("Add, change or end a Ministry", form, bool(errors)),
                 meta=meta)


def _story_panel(events):
    lines = [[num(ui.fmt_date(e["date"])), h(e["text"])]
             for e in sorted(events, key=lambda e: e["date"], reverse=True)]
    body = table([("Date", False), ("What happened", False)], lines, "story") if lines else empty("No story yet.")
    return panel("story", "Story", body, meta=h(f"{ui.plural(len(events), 'line', 'lines')}, newest first"))


def _details_panel(conn, person):
    pid = person["id"]
    address = people.person_address(conn, pid)
    family = people.current_family(conn, pid)
    from_family = family is not None and family["address"] and address == family["address"]
    rows = [
        ("Gender", h(GENDER_WORDS.get(person["gender"], "")) or ui.DASH),
        ("Birth date", num(ui.fmt_date(person["birth_date"])) if person["birth_date"] else ui.DASH),
        ("Phone", num(person["phone"]) if person["phone"] else ui.DASH),
        ("Address", vi(address) + (' <span class="faint">(Family address)</span>' if from_family else "")),
    ]
    if from_family and person["address"]:
        rows.append(("Own address", vi(person["address"])))
    rows.append(("Note", vi(person["note"])))
    body = '<dl class="kv">' + "".join(f"<div><dt>{h(k)}</dt><dd>{v}</dd></div>" for k, v in rows) + "</dl>"
    return panel("details", "Details", body, foot=card_link("Edit details", f"/people/{pid}/edit"))


def _private_panel(conn, pid, error, vals, edit_id=None, edit_vals=None):
    """Private notes: only here, only on screen (``no-print``). Each note has an Edit link
    (``?edit_note=<id>#private-note``); with ``edit_id`` that note shows in a form instead.
    The words of a note are only ever in this panel: never in a URL, a message or the story."""
    notes = people.list_private_notes(conn, pid)
    editing = next((n for n in notes if n["id"] == edit_id), None)
    errors = field_errors(error, "private", {})
    edit_errors = field_errors(error, "private-edit", {"body": "A private note"})
    edit_vals = edit_vals or {}
    here = f"/people/{pid}"

    def item(n):
        when = h(ui.fmt_datetime(n["created_at"]))
        if editing is not None and n["id"] == editing["id"]:
            form = ui.form(f"{here}/private-notes/{n['id']}", (
                ui.textarea_field("Change this Private note", "body", edit_vals.get("body", n["body"]),
                                  id="private-edit-body", lang="vi", rows=4, required=True,
                                  error=edit_errors.get("body"))
                + form_error(edit_errors)
                + '<div class="form-actions">' + ui.button("Save Private note", "secondary")
                + f'<a class="text-action" href="{here}#private-note">Cancel</a></div>'))
            return f'<li class="note editing" data-row><span class="when num">{when}</span>{form}</li>'
        edit = (f'<a class="note-edit" href="{h(ui.url(here, edit_note=n["id"]))}#private-note" '
                f'aria-label="Edit the Private note of {when}">Edit</a>')
        return (f'<li class="note" data-row><div class="note-head"><span class="when num">{when}</span>{edit}</div>'
                f'<p lang="vi">{h(n["body"])}</p></li>')

    listing = f'<ul class="notes">{"".join(item(n) for n in notes)}</ul>' if notes else empty("No Private note yet.")
    if editing is None:
        listing = form_error(edit_errors) + listing  # a refused change of a note that is not here
        listing += ui.form(f"{here}/private-notes", (
            ui.textarea_field("New Private note", "body", vals.get("body", ""), id="private-body", lang="vi",
                              required=True)
            + form_error(errors) + ui.button("Add Private note", "secondary")))
    section_html = panel("private-note", PRIVATE_LABEL, listing, cls="private no-print",
                         meta="Never printed. Removed at Handover.")
    return f'<div id="private-note" class="no-print">{section_html}</div>'


def _care_panel(conn, pid):
    log = care.care_log(conn, pid)
    rows = "".join(
        '<li class="row" data-row><span class="what wrap">'
        + (clamp2(h(r["who"]), r["who"], lang="vi") if r["who"] else ui.DASH)
        + (clamp2(h(r["care_note"]), r["care_note"], lang="vi", cls="sub") if r["care_note"]
           else '<span class="sub">—</span>')
        + f'</span><span class="figure num">{h(ui.fmt_date(r["done_date"]))}</span></li>'
        for r in log
    )
    body = f'<ul class="rows">{rows}</ul>' if log else empty("No Visit done yet.")
    foot = card_link("Plan a Visit", ui.url("/care", person_id=pid) + "#plan")
    return panel("care-log", "Care log", body, meta="Done Visits, newest first", foot=foot)


def _person_view(req, person, error=None, status=200):
    conn = req.conn
    pid = person["id"]
    form_key = error[0] if error else None

    def vals(key):
        return req.form if form_key == key else {}

    events = story.person_story(conn, pid)  # no Private note: the story is printed
    current_status = people.current_status(conn, pid)
    family = people.current_family(conn, pid)
    finding = [f"{current_status['name']} since {ui.fmt_date(current_status['start_date'])}"
               if current_status else "No Status"]
    if family is not None:
        finding.append(f"{family['name']} ({family['family_role']})")
        cp = people.current_chi_phai(conn, family["family_id"])
        if cp is not None:
            finding.append(cp["name"])
    log = care.care_log(conn, pid)
    finding.append(f"Last Visit {ui.fmt_date(log[0]['done_date'])}" if log else "No Visit yet")

    left = (_status_panel(conn, pid, error, vals("status")) + _family_panel(conn, pid, error, vals("family"))
            + _ministry_panel(conn, pid, error, vals("ministry")) + _story_panel(events))
    right = (_details_panel(conn, person)
             + _private_panel(conn, pid, error, vals("private"), _edit_note_id(req, form_key), vals("private-edit"))
             + _care_panel(conn, pid) + document_pages.documents_panel(conn, person_id=pid))
    body = (f'<div class="grid person"><div class="span-8 stack">{left}</div>'
            f'<div class="side-4 stack">{right}</div></div>')
    actions = (ui.link_button("Edit", f"/people/{pid}/edit")
               + ui.link_button("Giving statement", statement_href(person_id=pid))
               + ui.link_button("Plan a Visit", ui.url("/care", person_id=pid) + "#plan", "primary"))
    return Response.html(ui.page(person["full_name"], body, "people", sub=h(" · ".join(finding)), actions=actions,
                                 lang="vi"), status)


def _person_or_none(req):
    return people.get_person(req.conn, req.params["id"])


def _edit_note_id(req, form_key):
    """The Private note shown in its edit form: the one a refused change was for, else
    ``?edit_note=<id>``. ``None`` when there is none or the value is not a whole number."""
    raw = req.params.get("note_id") if form_key == "private-edit" else req.query.get("edit_note")
    try:
        return text.to_id(raw if raw is not None else "", "Private note")
    except ValueError:
        return None


def person_page(req):
    person = _person_or_none(req)
    if person is None:
        return not_found("Person", "/people", "Go to People")
    return _person_view(req, person)


def _history_post(req, key, change):
    """Run one history change for the Person page. ``change(conn, pid)`` returns the flash text.
    A refused change shows the Person page again with the sentence next to its field."""
    person = _person_or_none(req)
    if person is None:
        return not_found("Person", "/people", "Go to People")
    try:
        message = change(req.conn, person["id"])
    except ValueError as exc:
        return _person_view(req, person, (key, str(exc)), 400)
    return Response.redirect(ui.url(f"/people/{person['id']}", msg=message))


def status_post(req):
    def change(conn, pid):
        day = past_or_today(req.form.get("start_date"), "Start date")
        before = people.current_status(conn, pid)
        new_id = list_choice(conn, req.form.get("status_id"), "status", "Status")["id"]
        if before is not None and before["status_id"] == new_id:
            return same_change(f"Status is already {before['name']}.")
        people.set_status(conn, pid, new_id, day)
        return f"Status changed to {people.current_status(conn, pid)['name']} from {ui.fmt_date(day)}."
    return _history_post(req, "status", change)


def family_post(req):
    def change(conn, pid):
        day = past_or_today(req.form.get("start_date"), "Start date")
        family_id = req.form.get("family_id") or None
        role = req.form.get("family_role")
        before = people.current_family(conn, pid)
        if family_id is None:
            if before is None:
                return same_change("The Person is not in a Family.")
            people.set_family(conn, pid, None, None, day)
            return f"Left {before['name']} on {ui.fmt_date(day)}. The old Family link is kept."
        if before is not None and str(before["family_id"]) == family_id and before["family_role"] == role:
            return same_change(f"Already in {before['name']} as {role}.")
        people.set_family(conn, pid, family_id, role, day)
        now = people.current_family(conn, pid)
        return f"Now in {now['name']} as {now['family_role']} from {ui.fmt_date(day)}."
    return _history_post(req, "family", change)


def ministry_post(req):
    def change(conn, pid):
        day = past_or_today(req.form.get("start_date"), "Start date")
        item = list_choice(conn, req.form.get("ministry_id"), "ministry", "Ministry")
        role = req.form.get("ministry_role") or None
        before = next((r for r in people.current_ministries(conn, pid) if r["ministry_id"] == item["id"]), None)
        if role is None:
            if before is None:
                return same_change(f"The Person does not serve in {item['name']}.")
            people.set_ministry(conn, pid, item["id"], None, day)
            return f"Stopped serving in {item['name']} on {ui.fmt_date(day)}."
        if before is not None and before["ministry_role"] == role:
            return same_change(f"Already {role} in {item['name']}.")
        people.set_ministry(conn, pid, item["id"], role, day)
        return f"{role} in {item['name']} from {ui.fmt_date(day)}."
    return _history_post(req, "ministry", change)


def private_note_post(req):
    def change(conn, pid):
        people.add_private_note(conn, pid, req.form.get("body"))
        return "Private note added."
    return _history_post(req, "private", change)


def private_note_edit_post(req):
    """Save the changed text of one Private note. The words go only into the database: the
    message and the URL never hold them. A note of another Person is not found here."""
    person = _person_or_none(req)
    if person is None:
        return not_found("Person", "/people", "Go to People")
    pid, note_id = person["id"], req.params["note_id"]
    if not any(n["id"] == note_id for n in people.list_private_notes(req.conn, pid)):
        return not_found("Private note", f"/people/{pid}", "Go back to the Person")
    try:
        people.update_private_note(req.conn, pid, note_id, req.form.get("body"))
    except ValueError as exc:
        return _person_view(req, person, ("private-edit", str(exc)), 400)
    return Response.redirect(ui.url(f"/people/{pid}", msg="Private note changed.") + "#private-note")


ROUTES = [
    ("GET", "/people", list_page),
    ("GET", "/people/new", new_page),
    ("POST", "/people/new", new_post),
    ("GET", "/people/<int:id>", person_page),
    ("GET", "/people/<int:id>/edit", edit_page),
    ("POST", "/people/<int:id>/edit", edit_post),
    ("POST", "/people/<int:id>/status", status_post),
    ("POST", "/people/<int:id>/family", family_post),
    ("POST", "/people/<int:id>/ministry", ministry_post),
    ("POST", "/people/<int:id>/private-notes", private_note_post),
    ("POST", "/people/<int:id>/private-notes/<int:note_id>", private_note_edit_post),
]
