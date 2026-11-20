"""People pages: ``/people`` (list, Status filter, quick search), ``/people/new``,
``/people/<id>`` (the whole story and the forms that change it) and ``/people/<id>/edit``.

The helpers at the top are shared by the other C1 pages (Families, Chi phái, Care).

Rules kept here:
- History changes go only through the data layer (``people.set_status``, ``set_family``,
  ``set_ministry``, ...). Never an SQL UPDATE on a history table.
- A start date after today is refused (the data layer would count it as current at once).
- A Birth date is a text box: a full date or a year only (:func:`birth_from_input`, made to read a
  People file cell too). A year only is stored ``YYYY-00-00`` and shown ``1980``.
- Private notes show only on this Person page, inside ``.no-print``; never in the story list,
  never on another page. ``print.css`` hides ``.no-print``.
- Words on screen come from the text table (``t``/``tn``; sections ``people``, ``families``,
  ``chi_phai``). The shared helpers take a label as a TEXT key (or a plain word from an old caller)
  and a refused change as the exception itself: :func:`field_errors` finds its field on the
  English sentence and shows it in the language of the page.
"""

import datetime as _dt
import re

from .. import care, i18n, lists, people, story, text, ui, xlsx
from .. import search as person_search
from ..i18n import TextError, t, tn
from ..schema import FAMILY_ROLES, MINISTRY_ROLES
from ..server import Response
from ..ui import clamp2, h, vi
from . import documents as document_pages  # card C3 (a module import: pages/documents.py imports this one)

GENDER_WORDS = {"M": "people.male", "F": "people.female"}  # code -> TEXT key
SEARCH_LIMIT = 100_000  # the quick search on /people keeps every match
_BIRTH_YEAR = re.compile(r"[0-9]{4}(-00-00)?")  # a Birth date with the year only: 1980 or 1980-00-00


# ---------------------------------------------------------------- shared helpers (C1 pages)

def today_text():
    return _dt.date.today().isoformat()


def is_key(label):
    """Is ``label`` a key of the text table (``"people.start_date"``)?"""
    return isinstance(label, str) and label in i18n.TEXT["en"]


def word(label):
    """A label on screen: the text of a TEXT key, or a plain word as it is (old callers)."""
    return t(label) if is_key(label) else label


def past_or_today(value, what):
    """``value`` as ``YYYY-MM-DD`` when it is a real date on or before today.

    Otherwise a ``TextError`` whose English sentence starts with ``what`` (a TEXT key such as
    ``"people.start_date"``, or a plain word), so :func:`field_errors` puts it next to that field.
    """
    day = text.check_date(value or "", what)
    if day > today_text():
        raise TextError("people.err_after_today", label=what, today=ui.fmt_date(today_text()))
    return day


def birth_from_input(value, what="people.birth_date", date1904=False):
    """A Birth date typed in a form or read from a People file cell: ``YYYY-MM-DD``, or ``YYYY-00-00``
    for a year only. Empty (``None``, ``""``, spaces) gives ``None``.

    A year is a whole number from 1000 to 9999, 4 digits of text, or ``YYYY-00-00``; it must be from 1900
    and not after this year. Any other number is a spreadsheet date (``date1904``: the file's date system).
    Other text is read as 31/12/1980, 1/2/1980 or 1980-12-31, and that day is not after today.
    A refusal is a ``TextError`` whose English sentence starts with ``what``.
    """
    if isinstance(value, str):
        value = value.strip()
    if value is None or value == "":
        return None
    year = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 1000 <= value <= 9999 and float(value).is_integer():
            year = int(value)
    elif isinstance(value, str) and _BIRTH_YEAR.fullmatch(value):
        year = int(value[:4])
    if year is not None:
        if year < 1900:
            raise TextError("people.err_birth_date", label=what)
        if year > int(today_text()[:4]):
            raise TextError("people.err_after_today", label=what, today=ui.fmt_date(today_text()))
        return f"{year}-00-00"  # never past_or_today: text.check_date refuses a year only
    day = xlsx.cell_date(value, date1904)
    if day is None:
        raise TextError("people.err_birth_date", label=what)
    return past_or_today(day, what)


def field_errors(error, form_key, labels):
    """Where to show a refused change.

    ``error`` is ``(form_key, exc)`` or ``None``: ``exc`` is the exception (best: a ``TextError`` shows
    in the language of the page) or a sentence already made. ``labels`` is ``{field_name: label}``, each
    label a TEXT key or a plain word; the first label the English sentence starts with wins (so put
    "Ministry role" before "Ministry"). For the form ``form_key`` this returns ``{field_name: sentence}``,
    or ``{"": sentence}`` (the whole form) when no label fits. Other forms get ``{}``.
    """
    if not error or error[0] != form_key:
        return {}
    exc = error[1]
    made = not isinstance(exc, Exception)
    message = exc if made else i18n.error_text(exc)
    for name, label in labels.items():
        if made:
            fits = message.startswith(label) or message.startswith(word(label))
        else:
            fits = str(exc).startswith(t(label, "en") if is_key(label) else label)
        if fits:
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


def table(headers, rows, cls="", row_classes=()):
    """A table. ``headers``: ``[(text, numeric), ...]`` or ``[(text, numeric, column class), ...]``;
    ``rows``: lists of trusted cell HTML. The column class is on the header and on every cell of that
    column (``act``: a column of text actions only, which print.css leaves off paper).
    Every body row has ``data-row``. ``row_classes``: a class per body row, in the order of ``rows``
    (``""`` or a missing one: none), such as ``inactive`` on People. On a phone each row becomes two
    lines (style.css)."""
    def cell(tag, content, header, extra=""):
        names = (["n"] if header[1] else []) + list(header[2:3])
        cls = f' class="{" ".join(names)}"' if names else ""
        return f"<{tag}{extra}{cls}>{content}</{tag}>"

    def row_start(i):
        name = row_classes[i] if i < len(row_classes) else ""
        return f'<tr data-row class="{h(name)}">' if name else "<tr data-row>"

    head = "".join(cell("th", h(c[0]), c, ' scope="col"') for c in headers)
    body = "".join(
        row_start(n) + "".join(cell("td", c, headers[i]) for i, c in enumerate(r)) + "</tr>"
        for n, r in enumerate(rows)
    )
    return (f'<div class="table-wrap"><table class="list {h(cls)}"><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def period(start, end):
    """``[From, To]`` cells of a history row. An open row says ``now``."""
    return [f'<span class="num">{h(ui.fmt_date(start))}</span>',
            f'<span class="num">{h(ui.fmt_date(end))}</span>' if end
            else f'<span class="faint">{h(t("people.now"))}</span>']


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
    """The 404 page of one row. ``what`` and ``back_text``: TEXT keys (or plain words from old callers)."""
    what = word(what)
    body = (f'<p class="lead">{h(t("people.not_found_text", what=what))}</p>'
            f'<p><a href="{h(back_href)}">{h(word(back_text))}</a></p>')
    return Response.html(ui.page(t("people.not_found_title", what=what), body), 404)


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
    return t("people.nothing_changed", message=message)


def list_choice(conn, value, list_name, label):
    """The item of ``list_name`` picked in a form's ``<select>``, or a ``TextError``.

    The English refusal starts with ``label``, a glossary word as a TEXT key (``"people.status"``,
    ``"people.ministry"``), so :func:`field_errors` puts it next to that field and the pastor never
    reads "Item". A hidden item is still accepted (old rows keep it); the data layer decides the rest.
    """
    try:
        item = lists.get_item(conn, value or "")
    except ValueError:  # not a whole number above 0
        item = None
    if item is None or item["list_name"] != list_name:
        raise TextError("people.err_list_choice", label=label)
    return item


# ---------------------------------------------------------------- /people

def _status_counts(rows):
    counts = {}
    for r in rows:
        counts[r["status_id"]] = counts.get(r["status_id"], 0) + 1
    return counts


def _chips(items, counts, total, selected, q):
    chips = [("", t("people.all"), total)]
    chips += [(str(i["id"]), i["name"], counts.get(i["id"], 0)) for i in items if i["active"] or counts.get(i["id"])]
    if counts.get(None):
        chips.append(("none", t("people.no_status"), counts[None]))
    out = []
    for value, label, n in chips:
        href = ui.url("/people", status=value or None, q=q or None)
        current = ' aria-current="true"' if value == selected else ""
        out.append(f'<a class="chip" href="{h(href)}"{current}>{h(label)} <span class="num">{n}</span></a>')
    return f'<div class="chips" role="group" aria-label="{h(t("people.filter_status"))}">{"".join(out)}</div>'


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
    lines, marks = [], []
    for r in rows:
        fam = people.current_family(conn, r["id"])
        family_cell, chi_cell = ui.DASH, ui.DASH
        if fam is not None:
            family_cell = (f'{family_link(fam["family_id"], fam["name"])} '
                           f'<span class="faint">{h(ui.family_role(fam["family_role"]))}</span>')
            if fam["family_id"] not in chi_phai_of:
                chi_phai_of[fam["family_id"]] = people.current_chi_phai(conn, fam["family_id"])
            cp = chi_phai_of[fam["family_id"]]
            if cp is not None:
                chi_cell = chi_phai_link(cp["chi_phai_id"], cp["name"])
        # CRIT-6: a Person who Left or Passed away stays in the list, the row muted and the Status a tag,
        # so the pastor sees it before calling the phone of that row
        inactive = r["status_code"] in care.NOT_CARED_STATUS_CODES
        status = h(r["status_name"]) if r["status_name"] else ui.DASH
        lines.append([
            person_link(r["id"], r["full_name"]),
            f'<span class="tag">{status}</span>' if inactive else status,
            family_cell,
            chi_cell,
            num(r["phone"]) if r["phone"] else ui.DASH,
        ])
        marks.append("inactive" if inactive else "")

    search = (
        '<form class="search-form toolbar" action="/people" method="get" role="search">'
        f'<label for="people-q">{h(t("people.find_in_list"))}</label>'
        f'<div class="search-line"><input class="input" id="people-q" name="q" type="search" value="{h(q)}" '
        f'autocomplete="off" placeholder="{h(t("people.search_hint"))}">'
        + (ui.hidden("status", selected) if selected else "")
        + f'<button class="btn secondary" type="submit">{h(t("core.btn_search"))}</button>'
        + (f'<a class="btn secondary" href="{h(ui.url("/people", status=selected or None))}">'
           f'{h(t("people.clear"))}</a>' if q else "")
        + "</div></form>"
    )
    if lines:
        body = table([(t("people.person"), False), (t("people.status"), False), (t("people.family"), False),
                      (t("people.chi_phai"), False), (t("people.phone"), False)], lines, "people", marks)
    elif not everyone:
        body = empty(t("people.empty"))
    elif q:
        body = empty(t("people.empty_q", q=q))
    else:
        body = empty(t("people.empty_status"))

    items = lists.get_list(conn, "status", include_hidden=True)
    toolbar = (f'<div class="list-toolbar">{_chips(items, _status_counts(everyone), len(everyone), selected, q)}'
               f"{search}</div>")
    content = toolbar + list_panel("people", t("people.list"), body)
    shown = tn("people.count", len(everyone))
    count = shown if len(rows) == len(everyone) and not q else t("people.count_of", n=len(rows), total=shown)
    # CRIT-3: on screen the Status chips hold the counts ("All 50"), so the line under the h1 shows only how
    # many a search found (no chip shows that). Without a search it is on paper only: print.css hides the chips
    sub = h(count) if q else f'<span class="on-paper">{h(count)}</span>'
    actions = (ui.link_button(t("people.add"), "/people/new", "primary")
               + ui.link_button(t("people.file_add"), "/people/file"))  # the People file (spec 001)
    return Response.html(ui.page(t("people.title"), content, "people", sub=sub, actions=actions))


# ---------------------------------------------------------------- /people/new and /people/<id>/edit

_PERSON_LABELS = {"full_name": "people.full_name", "gender": "people.gender", "birth_date": "people.birth_date",
                  "start_date": "people.start_date", "status_id": "people.status"}


def _plain_fields(values, errors):
    v = values.get
    genders = [("", "—")] + [(code, t(key)) for code, key in GENDER_WORDS.items()]
    return (
        ui.field(t("people.full_name"), "full_name", v("full_name", ""), error=errors.get("full_name"),
                 required=True, autocomplete="off", lang="vi")
        + ui.select_field(t("people.gender"), "gender", genders, selected=v("gender", ""), error=errors.get("gender"))
        + ui.field(t("people.birth_date"), "birth_date", v("birth_date", ""), type="text",  # takes a year only
                   error=errors.get("birth_date"), hint=t("people.birth_hint"))
        + ui.field(t("people.phone"), "phone", v("phone", ""), type="tel", autocomplete="off")
        + ui.textarea_field(t("people.own_address"), "address", v("address", ""), lang="vi",
                            hint=t("people.address_hint"))
        + ui.textarea_field(t("people.note"), "note", v("note", ""), lang="vi", hint=t("people.note_hint"))
    )


def _new_form(req, values=None, error=None, status=200):
    conn = req.conn
    values = values or {}
    errors = field_errors(error, "new", _PERSON_LABELS)
    items = lists.get_list(conn, "status")
    visitor = next((i["id"] for i in items if i["code"] == "visitor"), None)
    inner = (
        _plain_fields(values, errors)
        + ui.select_field(t("people.first_status"), "status_id", [(i["id"], i["name"]) for i in items],
                          selected=values.get("status_id", visitor), error=errors.get("status_id"))
        + date_field(t("people.start_date"), "start_date", "f-start_date", values.get("start_date"),
                     errors.get("start_date"), hint=t("people.start_hint"))
        + form_error(errors) + ui.button(t("people.add_button"))
    )
    body = f'<section class="panel narrow">{ui.form("/people/new", inner)}</section>'
    return Response.html(ui.page(t("people.add"), body, "people"), status)


def new_page(req):
    return _new_form(req)


def add_person_from_form(conn, form):
    """Add a Person from the Add a Person form: the one place of its rules, for this page and the
    Hermes door. ``form`` has ``.get`` (the server's form or a plain dict). Returns the Person id;
    a refused value raises ``ValueError`` (a ``TextError``: ``str()`` is the English sentence)."""
    f = form
    birth = birth_from_input(f.get("birth_date"))
    start = past_or_today(f.get("start_date"), "people.start_date")
    status_id = list_choice(conn, f["status_id"], "status", "people.status")["id"] if f.get("status_id") else None
    return people.add_person(conn, f.get("full_name"), gender=f.get("gender"), birth_date=birth,
                             phone=f.get("phone"), address=f.get("address"), note=f.get("note"),
                             status_id=status_id, start_date=start)


def new_post(req):
    f = req.form
    try:
        pid = add_person_from_form(req.conn, f)
    except ValueError as exc:
        return _new_form(req, f, ("new", exc), 400)
    return Response.redirect(ui.url(f"/people/{pid}", msg=t("people.added")))


def _edit_form(req, person, values=None, error=None, status=200):
    values = values if values is not None else {
        **{k: person[k] or "" for k in ("full_name", "gender", "phone", "address", "note")},
        # 1980 or 31/12/1980, as the box reads it back (Save with no change keeps it); empty, never a dash
        "birth_date": ui.fmt_birth_date(person["birth_date"]) if person["birth_date"] else "",
    }
    errors = field_errors(error, "edit", _PERSON_LABELS)
    pid = person["id"]
    inner = _plain_fields(values, errors) + form_error(errors) + ui.button(t("core.btn_save"))
    link = f'<a href="/people/{pid}">{h(t("people.person_page"))}</a>'
    body = (f'<section class="panel narrow">{ui.form(f"/people/{pid}/edit", inner)}'
            f'<p class="hint">{ui.t_html("people.edit_hint", link=link)}</p></section>')
    return Response.html(ui.page(t("people.edit_title", name=person["full_name"]), body, "people", lang="vi"),
                         status)


def edit_page(req):
    person = people.get_person(req.conn, req.params["id"])
    if person is None:
        return not_found("people.person", "/people", "people.go_people")
    return _edit_form(req, person)


def edit_post(req):
    person = people.get_person(req.conn, req.params["id"])
    if person is None:
        return not_found("people.person", "/people", "people.go_people")
    f = req.form
    try:
        birth = birth_from_input(f.get("birth_date"))
        people.update_person(req.conn, person["id"], full_name=f.get("full_name"), gender=f.get("gender"),
                             birth_date=birth, phone=f.get("phone"), address=f.get("address"),
                             note=f.get("note"))
    except ValueError as exc:
        return _edit_form(req, person, f, ("edit", exc), 400)
    return Response.redirect(ui.url(f"/people/{person['id']}", msg=t("people.details_saved")))


# ---------------------------------------------------------------- /people/<id>

def history_headers(*first):
    """Table headers of a history list: ``first`` (TEXT keys), then From and To."""
    return [(t(key), False) for key in first] + [(t("people.from"), True), (t("people.to"), True)]


def _status_panel(conn, pid, error, vals):
    rows = people.status_history(conn, pid)
    current = next((r for r in rows if r["end_date"] is None), None)
    errors = field_errors(error, "status", {"start_date": "people.start_date", "status_id": "people.status"})
    items = lists.get_list(conn, "status")
    form = ui.form(f"/people/{pid}/status", (
        ui.select_field(t("people.new_status"), "status_id", [(i["id"], i["name"]) for i in items], id="status-id",
                        selected=vals.get("status_id") or (current["status_id"] if current else None),
                        error=errors.get("status_id"))
        + date_field(t("people.start_date"), "start_date", "status-date", vals.get("start_date"),
                     errors.get("start_date"), min_date=latest_change(rows))
        + form_error(errors) + ui.button(t("people.change_status"), "secondary")))
    lines = [[h(r["name"]), *period(r["start_date"], r["end_date"])] for r in newest_first(rows)]
    body = (table(history_headers("people.status"), lines, "history")
            if lines else empty(t("people.no_status_yet")))
    return panel("status", t("people.status"), body + change_box(t("people.change_status"), form, bool(errors)))


def _family_panel(conn, pid, error, vals):
    rows = people.family_history(conn, pid)
    current = next((r for r in rows if r["end_date"] is None), None)
    # "Family role" before "Family": field_errors takes the first label a sentence starts with.
    errors = field_errors(error, "family", {"start_date": "people.start_date", "family_role": "people.family_role",
                                            "family_id": "people.family"})
    first = ("", t("people.leave_family")) if current else ("", t("people.no_family_option"))
    options = [first] + [(f["id"], f["name"]) for f in people.list_families(conn)]
    role = vals.get("family_role") or (current["family_role"] if current else "Head")
    form = ui.form(f"/people/{pid}/family", (
        ui.select_field(t("people.family"), "family_id", options, id="family-id", lang="vi",
                        selected=vals.get("family_id", current["family_id"] if current else ""),
                        error=errors.get("family_id"))
        + ui.select_field(t("people.family_role"), "family_role", [(r, ui.family_role(r)) for r in FAMILY_ROLES],
                          id="family-role", selected=role, error=errors.get("family_role"))
        + date_field(t("people.start_date"), "start_date", "family-date", vals.get("start_date"),
                     errors.get("start_date"), min_date=latest_change(rows), hint=t("people.move_hint"))
        + form_error(errors) + ui.button(t("people.save_family"), "secondary")))
    now = ""
    if current is not None:
        cp = people.current_chi_phai(conn, current["family_id"])
        address = people.person_address(conn, pid)
        chi_phai = chi_phai_link(cp["chi_phai_id"], cp["name"]) if cp else ui.DASH
        now = ('<dl class="kv">'
               f'<div><dt>{h(t("people.family"))}</dt><dd>{family_link(current["family_id"], current["name"])}</dd></div>'
               f'<div><dt>{h(t("people.family_role"))}</dt><dd>{h(ui.family_role(current["family_role"]))}</dd></div>'
               f'<div><dt>{h(t("people.chi_phai"))}</dt><dd>{chi_phai}</dd></div>'
               f'<div><dt>{h(t("people.address"))}</dt><dd>{vi(address)}</dd></div>'
               "</dl>")
    lines = [[family_link(r["family_id"], r["name"]), h(ui.family_role(r["family_role"])),
              *period(r["start_date"], r["end_date"])] for r in newest_first(rows)]
    body = now + (table(history_headers("people.family", "people.family_role"), lines, "history")
                  if lines else empty(t("people.not_in_family")))
    foot = card_link(t("families.add"), "/families/new")
    return panel("family", t("people.family"), body + change_box(t("people.set_family"), form, bool(errors)),
                 foot=foot)


def _ministry_panel(conn, pid, error, vals):
    rows = people.ministry_history(conn, pid)
    current = [r for r in rows if r["end_date"] is None]
    # "Ministry role" before "Ministry": field_errors takes the first label a sentence starts with.
    errors = field_errors(error, "ministry", {"start_date": "people.start_date",
                                              "ministry_role": "people.ministry_role",
                                              "ministry_id": "people.ministry"})
    items = lists.get_list(conn, "ministry")
    roles = [(r, ui.ministry_role(r)) for r in MINISTRY_ROLES] + [("", t("people.stop_serving"))]
    form = ui.form(f"/people/{pid}/ministry", (
        ui.select_field(t("people.ministry"), "ministry_id", [(i["id"], i["name"]) for i in items], id="ministry-id",
                        selected=vals.get("ministry_id"), error=errors.get("ministry_id"))
        + ui.select_field(t("people.ministry_role"), "ministry_role", roles, id="ministry-role",
                          selected=vals.get("ministry_role", "Member"), error=errors.get("ministry_role"))
        + date_field(t("people.start_date"), "start_date", "ministry-date", vals.get("start_date"),
                     errors.get("start_date"))
        + form_error(errors) + ui.button(t("people.save_ministry"), "secondary")))
    lines = [[h(r["name"]), h(ui.ministry_role(r["ministry_role"])), *period(r["start_date"], r["end_date"])]
             for r in newest_first(rows)]
    body = (table(history_headers("people.ministry", "people.ministry_role"), lines, "history")
            if lines else empty(t("people.not_serving")))
    meta = h(" · ".join(f"{r['name']} ({ui.ministry_role(r['ministry_role'])})" for r in current) if current
             else t("people.not_serving_now"))
    return panel("ministries", t("people.ministries"),
                 body + change_box(t("people.change_ministry"), form, bool(errors)), meta=meta)


def _story_panel(events):
    lines = [[num(ui.fmt_date(e["date"])), h(e["text"])]
             for e in sorted(events, key=lambda e: e["date"], reverse=True)]
    body = (table([(t("people.date"), False), (t("people.what_happened"), False)], lines, "story")
            if lines else empty(t("people.no_story")))
    return panel("story", t("people.story"), body, meta=h(tn("people.story_lines", len(events))))


def _details_panel(conn, person):
    pid = person["id"]
    address = people.person_address(conn, pid)
    family = people.current_family(conn, pid)
    from_family = family is not None and family["address"] and address == family["address"]
    gender = GENDER_WORDS.get(person["gender"])
    rows = [
        ("people.gender", h(t(gender)) if gender else ui.DASH),
        ("people.birth_date", num(ui.fmt_birth_date(person["birth_date"])) if person["birth_date"] else ui.DASH),
        ("people.phone", num(person["phone"]) if person["phone"] else ui.DASH),
        ("people.address", vi(address)
         + (f' <span class="faint">{h(t("people.family_address"))}</span>' if from_family else "")),
    ]
    if from_family and person["address"]:
        rows.append(("people.own_address", vi(person["address"])))
    rows.append(("people.note", vi(person["note"])))
    body = '<dl class="kv">' + "".join(f"<div><dt>{h(t(k))}</dt><dd>{v}</dd></div>" for k, v in rows) + "</dl>"
    return panel("details", t("people.details"), body,
                 foot=card_link(t("people.edit_details"), f"/people/{pid}/edit"))


def _private_panel(conn, pid, error, vals, edit_id=None, edit_vals=None):
    """Private notes: only here, only on screen (``no-print``). Each note has an Edit link
    (``?edit_note=<id>#private-note``); with ``edit_id`` that note shows in a form instead.
    The words of a note are only ever in this panel: never in a URL, a message or the story."""
    notes = people.list_private_notes(conn, pid)
    editing = next((n for n in notes if n["id"] == edit_id), None)
    errors = field_errors(error, "private", {})
    # matched on the English sentence of people.err_note_empty (never shown)
    edit_errors = field_errors(error, "private-edit", {"body": "A private note"})
    edit_vals = edit_vals or {}
    here = f"/people/{pid}"

    def item(n):
        when_text = ui.fmt_datetime(n["created_at"])
        when = h(when_text)
        if editing is not None and n["id"] == editing["id"]:
            form = ui.form(f"{here}/private-notes/{n['id']}", (
                ui.textarea_field(t("people.change_note"), "body", edit_vals.get("body", n["body"]),
                                  id="private-edit-body", lang="vi", rows=4, required=True,
                                  error=edit_errors.get("body"))
                + form_error(edit_errors)
                + '<div class="form-actions">' + ui.button(t("people.save_note"), "secondary")
                + f'<a class="text-action" href="{here}#private-note">{h(t("core.btn_cancel"))}</a></div>'))
            return f'<li class="note editing" data-row><span class="when num">{when}</span>{form}</li>'
        edit = (f'<a class="note-edit" href="{h(ui.url(here, edit_note=n["id"]))}#private-note" '
                f'aria-label="{h(t("people.edit_note_aria", when=when_text))}">{h(t("core.btn_edit"))}</a>')
        return (f'<li class="note" data-row><div class="note-head"><span class="when num">{when}</span>{edit}</div>'
                f'<p lang="vi">{h(n["body"])}</p></li>')

    listing = (f'<ul class="notes">{"".join(item(n) for n in notes)}</ul>' if notes
               else empty(t("people.no_note")))
    if editing is None:
        listing = form_error(edit_errors) + listing  # a refused change of a note that is not here
        listing += ui.form(f"{here}/private-notes", (
            ui.textarea_field(t("people.new_note"), "body", vals.get("body", ""), id="private-body", lang="vi",
                              required=True)
            + form_error(errors) + ui.button(t("people.add_note"), "secondary")))
    section_html = panel("private-note", t("people.private_label"), listing, cls="private no-print",
                         meta=h(t("people.private_meta")))
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
    body = f'<ul class="rows">{rows}</ul>' if log else empty(t("people.no_visit_done"))
    foot = card_link(t("people.plan_visit"), ui.url("/care", person_id=pid) + "#plan")
    return panel("care-log", t("care.care_log"), body, meta=h(t("people.care_meta")), foot=foot)


def _person_view(req, person, error=None, status=200):
    conn = req.conn
    pid = person["id"]
    form_key = error[0] if error else None

    def vals(key):
        return req.form if form_key == key else {}

    events = story.person_story(conn, pid, lang=ui.current_lang())  # no Private note: the story is printed
    current_status = people.current_status(conn, pid)
    family = people.current_family(conn, pid)
    finding = [t("people.status_since", status=current_status["name"], date=ui.fmt_date(current_status["start_date"]))
               if current_status else t("people.no_status")]
    if family is not None:
        finding.append(f"{family['name']} ({ui.family_role(family['family_role'])})")
        cp = people.current_chi_phai(conn, family["family_id"])
        if cp is not None:
            finding.append(cp["name"])
    log = care.care_log(conn, pid)
    finding.append(t("people.last_visit", date=ui.fmt_date(log[0]["done_date"])) if log else t("people.no_visit"))

    left = (_status_panel(conn, pid, error, vals("status")) + _family_panel(conn, pid, error, vals("family"))
            + _ministry_panel(conn, pid, error, vals("ministry")) + _story_panel(events))
    right = (_details_panel(conn, person)
             + _private_panel(conn, pid, error, vals("private"), _edit_note_id(req, form_key), vals("private-edit"))
             + _care_panel(conn, pid) + document_pages.documents_panel(conn, person_id=pid))
    body = (f'<div class="grid person"><div class="span-8 stack">{left}</div>'
            f'<div class="side-4 stack">{right}</div></div>')
    actions = (ui.link_button(t("core.btn_edit"), f"/people/{pid}/edit")
               + ui.link_button(t("money.giving_statement"), statement_href(person_id=pid))
               + ui.link_button(t("people.plan_visit"), ui.url("/care", person_id=pid) + "#plan", "primary"))
    return Response.html(ui.page(person["full_name"], body, "people", sub=h(" · ".join(finding)), actions=actions,
                                 lang="vi"), status)


def _person_or_none(req):
    return people.get_person(req.conn, req.params["id"])


def _edit_note_id(req, form_key):
    """The Private note shown in its edit form: the one a refused change was for, else
    ``?edit_note=<id>``. ``None`` when there is none or the value is not a whole number."""
    raw = req.params.get("note_id") if form_key == "private-edit" else req.query.get("edit_note")
    try:
        return text.to_id(raw if raw is not None else "", "people.private_note")
    except ValueError:
        return None


def person_page(req):
    person = _person_or_none(req)
    if person is None:
        return not_found("people.person", "/people", "people.go_people")
    return _person_view(req, person)


def _history_post(req, key, change):
    """Run one history change for the Person page. ``change(conn, pid)`` returns the flash text
    (made with ``t`` now, in the language of this request). A refused change shows the Person page
    again with the sentence next to its field."""
    person = _person_or_none(req)
    if person is None:
        return not_found("people.person", "/people", "people.go_people")
    try:
        message = change(req.conn, person["id"])
    except ValueError as exc:
        return _person_view(req, person, (key, exc), 400)
    return Response.redirect(ui.url(f"/people/{person['id']}", msg=message))


def status_post(req):
    def change(conn, pid):
        day = past_or_today(req.form.get("start_date"), "people.start_date")
        before = people.current_status(conn, pid)
        new_id = list_choice(conn, req.form.get("status_id"), "status", "people.status")["id"]
        if before is not None and before["status_id"] == new_id:
            return same_change(t("people.status_same", name=before["name"]))
        people.set_status(conn, pid, new_id, day)
        return t("people.status_changed", name=people.current_status(conn, pid)["name"], date=ui.fmt_date(day))
    return _history_post(req, "status", change)


def set_family_from_form(conn, pid, form):
    """Put a Person in a Family from the Family form, for this page and the Hermes door.
    Old links are closed and kept. Returns the start day."""
    day = past_or_today(form.get("start_date"), "people.start_date")
    people.set_family(conn, pid, form.get("family_id"), form.get("family_role"), day)
    return day


def family_post(req):
    def change(conn, pid):
        day = past_or_today(req.form.get("start_date"), "people.start_date")
        family_id = req.form.get("family_id") or None
        role = req.form.get("family_role")
        before = people.current_family(conn, pid)
        if family_id is None:
            if before is None:
                return same_change(t("people.family_none"))
            people.set_family(conn, pid, None, None, day)
            return t("people.family_left", name=before["name"], date=ui.fmt_date(day))
        if before is not None and str(before["family_id"]) == family_id and before["family_role"] == role:
            return same_change(t("people.family_same", name=before["name"], role=ui.family_role(role)))
        set_family_from_form(conn, pid, req.form)
        now = people.current_family(conn, pid)
        return t("people.family_now", name=now["name"], role=ui.family_role(now["family_role"]),
                 date=ui.fmt_date(day))
    return _history_post(req, "family", change)


def ministry_post(req):
    def change(conn, pid):
        day = past_or_today(req.form.get("start_date"), "people.start_date")
        item = list_choice(conn, req.form.get("ministry_id"), "ministry", "people.ministry")
        role = req.form.get("ministry_role") or None
        before = next((r for r in people.current_ministries(conn, pid) if r["ministry_id"] == item["id"]), None)
        if role is None:
            if before is None:
                return same_change(t("people.ministry_none", name=item["name"]))
            people.set_ministry(conn, pid, item["id"], None, day)
            return t("people.ministry_stopped", name=item["name"], date=ui.fmt_date(day))
        if before is not None and before["ministry_role"] == role:
            return same_change(t("people.ministry_same", role=ui.ministry_role(role), name=item["name"]))
        people.set_ministry(conn, pid, item["id"], role, day)
        return t("people.ministry_now", role=ui.ministry_role(role), name=item["name"], date=ui.fmt_date(day))
    return _history_post(req, "ministry", change)


def private_note_post(req):
    def change(conn, pid):
        people.add_private_note(conn, pid, req.form.get("body"))
        return t("people.note_added")
    return _history_post(req, "private", change)


def private_note_edit_post(req):
    """Save the changed text of one Private note. The words go only into the database: the
    message and the URL never hold them. A note of another Person is not found here."""
    person = _person_or_none(req)
    if person is None:
        return not_found("people.person", "/people", "people.go_people")
    pid, note_id = person["id"], req.params["note_id"]
    if not any(n["id"] == note_id for n in people.list_private_notes(req.conn, pid)):
        return not_found("people.private_note", f"/people/{pid}", "people.go_person")
    try:
        people.update_private_note(req.conn, pid, note_id, req.form.get("body"))
    except ValueError as exc:
        return _person_view(req, person, ("private-edit", exc), 400)
    return Response.redirect(ui.url(f"/people/{pid}", msg=t("people.note_changed")) + "#private-note")


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
