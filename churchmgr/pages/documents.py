"""Documents (card C3): ``/documents`` (every Document, newest first), ``/documents/new`` (the Add
document form for one Person, Family or Calendar item), ``/documents/<id>/file`` (the download) and
``/documents/<id>/delete`` (Delete, after one question; FIX-T 3b).

Rules kept here:
- A file goes in only through ``documents.add_document``, comes out only through
  ``documents.document_path`` and goes away only through ``documents.delete_document``. The file on
  disk has a random name; no name or path from the request is ever joined to a folder.
- The download is ``application/octet-stream`` with the ``Content-Disposition`` of
  ``server.content_disposition`` (an ASCII name plus the UTF-8 NFC name); the server adds ``nosniff``.
- :func:`documents_panel` is the shared Documents block of the Person, Family and Calendar item pages.
- Words on screen come from the text table (section ``documents``); file names are data, shown as stored.
"""

from .. import documents as docs
from .. import i18n, text, ui
from ..i18n import TextError, t, tn
from ..server import Response
from ..ui import h, vi
from . import people as person_pages  # a module import on purpose: people.py imports this module too

# The one thing a Document is linked to: form field -> (TEXT key of the glossary word, page of it).
LINKS = {
    "person_id": ("documents.person", "/people/{}"),
    "family_id": ("documents.family", "/families/{}"),
    "calendar_item_id": ("documents.calendar_item", "/calendar/{}"),
}
_NAME_SQL = {
    "person_id": "SELECT full_name FROM person WHERE id = ?",
    "family_id": "SELECT name FROM family WHERE id = ?",
    "calendar_item_id": "SELECT title FROM calendar_item WHERE id = ?",
}
MB = 1024 * 1024


# ---------------------------------------------------------------- small logic (tested)

def fmt_size(size, lang=None):
    """Whole bytes as plain words: ``512 bytes``, ``20 KB``, ``3,4 MB`` (integer maths only).

    ``lang``: ``None`` is the language of the request; outside a request (tests, logs) it is English,
    like ``str()`` of a ``TextError``. KB and MB read the same in both languages."""
    if size < 1024:
        if lang is None:
            lang = ui.current_lang() if ui.current_request() is not None else "en"
        return tn("documents.bytes", size, lang)
    if size < MB:
        return f"{(size + 1023) // 1024} KB"
    tenths = (size * 10 + MB // 2) // MB
    return f"{tenths // 10:,}".replace(",", ".") + f",{tenths % 10} MB"


def parse_link(values):
    """The one link of a new Document from form or query values, like ``("person_id", 5)``.
    No link, two links or a bad number raise ``ValueError`` (a ``TextError``)."""
    given = [(key, (values.get(key) or "").strip()) for key in LINKS]
    given = [(key, raw) for key, raw in given if raw]
    if len(given) != 1:
        raise TextError("documents.err_one_link")
    key, raw = given[0]
    return key, text.to_id(raw, LINKS[key][0])


def link_target(conn, key, rid):
    """``(word, name, href)`` of the Person, Family or Calendar item (``word`` in the language of the
    page), or ``ValueError`` if it is not there."""
    word, href = LINKS[key]
    row = conn.execute(_NAME_SQL[key], (rid,)).fetchone()
    if row is None:
        raise TextError("documents.err_no_row", what=word, id=rid)
    return t(word), row[0], href.format(rid)


# ---------------------------------------------------------------- the shared block

def add_form(key, rid, error=None):
    """The Add document form: one file and the hidden link to its Person, Family or Calendar item.
    ``error`` is a sentence already in the language of the page."""
    inner = (
        ui.hidden(key, rid)
        + ui.field(t("documents.file"), "file", "", type="file", id=f"doc-file-{rid}", required=True, error=error,
                   hint=t("documents.file_hint", mb=docs.MAX_SIZE // MB), data_max_bytes=docs.MAX_SIZE,
                   data_text_too_large=t("documents.err_too_large", mb=docs.MAX_SIZE // MB))
        + ui.button(t("documents.add"), "secondary")
    )
    return ui.form("/documents/new", inner, multipart=True)


def _doc_row(row):
    """One Document: its name wraps to 2 lines at most (full name in the title), then size and date."""
    meta = t("documents.size_added", size=fmt_size(row["size"]), date=ui.fmt_date(row["added_at"]))
    name = row["original_name"]
    link = f'<a href="/documents/{int(row["id"])}/file">{h(name)}</a>'
    return ('<li class="row" data-row><span class="what wrap">'
            f'{ui.clamp2(link, name, lang="vi")}'
            f'<span class="sub num">{h(meta)}</span></span></li>')


def documents_panel(conn, **link):
    """The Documents block of one Person, Family or Calendar item: its files, newest first (each one
    a download link), and the Add document form. ``link`` is ``person_id=5``, ``family_id=2`` or
    ``calendar_item_id=9``."""
    (key, rid), = link.items()
    rows = list(reversed(docs.list_documents(conn, **{key: rid})))
    body = (f'<ul class="rows">{"".join(_doc_row(r) for r in rows)}</ul>' if rows
            else person_pages.empty(t("documents.panel_empty", what=t(LINKS[key][0]))))
    meta = tn("documents.count", len(rows)) if rows else t("documents.panel_meta")
    form = f'<div class="add-form">{add_form(key, rid)}</div>'
    return (f'<div id="documents">{person_pages.panel("documents", t("documents.title"), body + form, meta=h(meta))}'
            "</div>")


# ---------------------------------------------------------------- /documents

_SELECT = (
    "SELECT d.id, d.original_name, d.size, d.added_at, d.person_id, p.full_name AS person_name, "
    "d.family_id, f.name AS family_name, d.calendar_item_id, c.title AS item_title, c.starts_at AS item_starts, "
    "(SELECT printf('%02d/%d', s.seq, s.year) FROM sent_document s WHERE s.document_id = d.id "
    " ORDER BY s.id LIMIT 1) AS sent_number, "
    "(SELECT s.year FROM sent_document s WHERE s.document_id = d.id ORDER BY s.id LIMIT 1) AS sent_year "
    "FROM document d LEFT JOIN person p ON p.id = d.person_id LEFT JOIN family f ON f.id = d.family_id "
    "LEFT JOIN calendar_item c ON c.id = d.calendar_item_id "
)
_ALL_SQL = _SELECT + "ORDER BY d.added_at DESC, d.id DESC"
_ONE_SQL = _SELECT + "WHERE d.id = ?"


def _faint(key):
    return f'<span class="faint">{h(t(key))}</span>'


def _linked(r):
    if r["person_id"] is not None:
        return f'{_faint("documents.person")} {person_pages.person_link(r["person_id"], r["person_name"])}'
    if r["family_id"] is not None:
        return f'{_faint("documents.family")} {person_pages.family_link(r["family_id"], r["family_name"])}'
    if r["calendar_item_id"] is not None:
        return (f'{_faint("documents.calendar_item")} <a href="/calendar/{int(r["calendar_item_id"])}">'
                f'{vi(r["item_title"])}</a> <span class="faint num">{h(ui.fmt_date(r["item_starts"]))}</span>')
    if r["sent_number"] is not None:
        return (f'{_faint("documents.sent_document")} '
                f'<a class="num" href="{h(ui.url("/sent", year=r["sent_year"]))}">{h(r["sent_number"])}</a>')
    return ui.DASH


def _delete_link(r):
    """The quiet Delete text action that ends a row of the list: it opens the one question.
    Its column has the class ``act``: print.css leaves the whole column off paper."""
    label = t("documents.delete_aria", name=r["original_name"])
    return f'<a href="/documents/{int(r["id"])}/delete" aria-label="{h(label)}">{h(t("core.btn_delete"))}</a>'


def list_page(req):
    rows = req.conn.execute(_ALL_SQL).fetchall()
    lines = [[f'<a href="/documents/{int(r["id"])}/file">{vi(r["original_name"])}</a>', _linked(r),
              person_pages.num(fmt_size(r["size"])), person_pages.num(ui.fmt_date(r["added_at"])), _delete_link(r)]
             for r in rows]
    if lines:
        body = person_pages.table([(t("documents.document"), False), (t("documents.linked_to"), False),
                                   (t("documents.size"), True), (t("documents.added_col"), True),
                                   ("", False, "act")], lines, "documents")
    else:
        body = person_pages.empty(t("documents.empty"))
    hint = f'<p class="hint list-foot no-print">{h(t("documents.list_hint"))}</p>'
    total = sum(r["size"] for r in rows)
    sub = h(t("documents.list_sub", count=tn("documents.count", len(rows)), size=fmt_size(total)))
    content = person_pages.list_panel("documents-list", t("documents.list"), body) + hint
    return Response.html(ui.page(t("documents.title"), content, "documents", sub=sub))


# ---------------------------------------------------------------- /documents/new

def _new_view(req, key, rid, error=None, status=200):
    word, name, href = link_target(req.conn, key, rid)
    back = f'<a href="{h(href)}">{vi(name)}</a>'
    body = (f'<section class="panel narrow" data-panel="add-document">{add_form(key, rid, error)}'
            f'<p class="hint">{ui.t_html("documents.back_to", link=back)}</p></section>')
    sub = ui.t_html("documents.for_link", what=h(word), name=vi(name))
    return Response.html(ui.page(t("documents.add"), body, "documents", sub=sub), status)


def new_page(req):
    key, rid = parse_link(req.query)
    return _new_view(req, key, rid)


def new_post(req):
    conn = req.conn
    key, rid = parse_link(req.form)
    _word, _name, href = link_target(conn, key, rid)  # a missing Person / Family / item: the 400 page
    chosen = req.files.get("file")
    try:
        if chosen is None:
            raise TextError("documents.err_choose_file")
        file_name, data = chosen
        if not data:
            raise TextError("documents.err_empty_file")
        doc_id = docs.add_document(conn, req.state.copy_folder, data, file_name, **{key: rid})
    except ValueError as exc:
        return _new_view(req, key, rid, i18n.error_text(exc), 400)
    shown = docs.get_document(conn, doc_id)["original_name"]
    return Response.redirect(ui.url(href, msg=t("documents.added", name=shown)) + "#documents")


# ---------------------------------------------------------------- /documents/<id>/file

def _not_found():
    """The 404 page of a Document (the shared page of pages/people.py, given the words of this page)."""
    return person_pages.not_found(t("documents.document"), "/documents", t("documents.go_documents"))


def file_page(req):
    conn = req.conn
    row = docs.get_document(conn, req.params["id"])
    if row is None:
        return _not_found()
    path = docs.document_path(conn, req.state.copy_folder, row["id"])
    if not path.is_file():
        body = (f'<p class="lead">{ui.t_html("documents.file_missing_text", name=vi(row["original_name"]))}</p>'
                f'<p><a href="/documents">{h(t("documents.go_documents"))}</a></p>')
        return Response.html(ui.page(t("documents.file_missing"), body, "documents"), 404)
    return Response.file(path, row["original_name"])


# ---------------------------------------------------------------- /documents/<id>/delete

def _sent_numbers(conn, doc_id):
    """The numbers of the Sent documents that use this Document's file, like ``["05/2026"]``."""
    return [r[0] for r in conn.execute("SELECT printf('%02d/%d', seq, year) FROM sent_document "
                                       "WHERE document_id = ? ORDER BY year, seq", (doc_id,))]


def _confirm_delete(conn, row):
    """The one question before a Delete: the Document's name, size, date, what it is linked to and
    what stays (a Sent document keeps its row, with no file). One danger button, and Cancel."""
    did = int(row["id"])
    facts = [(t("documents.size"), person_pages.num(fmt_size(row["size"]))),
             (t("documents.added_col"), person_pages.num(ui.fmt_date(row["added_at"]))),
             (t("documents.linked_to"), _linked(row))]
    kv = '<dl class="kv">' + "".join(f"<div><dt>{h(k)}</dt><dd>{v}</dd></div>" for k, v in facts) + "</dl>"
    numbers = _sent_numbers(conn, did)
    keeps = tn("documents.keeps", len(numbers), numbers=", ".join(numbers)) if numbers else ""
    form = ui.form(f"/documents/{did}/delete",
                   ui.hidden("confirm", "yes") + ui.button(t("documents.yes_delete"), "danger"))
    name = f'<strong class="confirm-name" lang="vi">{h(row["original_name"])}</strong>'
    body = (f'<section class="panel narrow" data-panel="confirm"><p class="lead">'
            f'{ui.t_html("documents.delete_question", name=name)}</p>{kv}'
            + (f'<p class="hint">{h(keeps)}</p>' if keeps else "")
            + f'<p class="hint">{h(t("documents.delete_hint"))}</p>'
            f'<div class="confirm-actions">{form}{ui.link_button(t("core.btn_cancel"), "/documents")}</div></section>')
    return Response.html(ui.page(t("documents.delete_title"), body, "documents"))


def _row_or_none(req):
    row = docs.get_document(req.conn, req.params["id"])
    return None if row is None else req.conn.execute(_ONE_SQL, (row["id"],)).fetchone()


def delete_page(req):
    row = _row_or_none(req)
    if row is None:
        return _not_found()
    return _confirm_delete(req.conn, row)


def delete_post(req):
    """Delete only with ``confirm=yes``; without it, the question again. The row goes in one
    transaction, then the file (``docs.delete_document``)."""
    row = _row_or_none(req)
    if row is None:
        return _not_found()
    if req.form.get("confirm") != "yes":
        return _confirm_delete(req.conn, row)
    left = docs.delete_document(req.conn, req.state.copy_folder, row["id"])
    msg = t("documents.deleted", name=row["original_name"])
    if left is not None:  # the row is gone, but the file stays (for example it is open in another program)
        msg += " " + t("documents.file_left", file=left.name)
    return Response.redirect(ui.url("/documents", msg=msg))


ROUTES = [
    ("GET", "/documents", list_page),
    ("GET", "/documents/new", new_page),
    ("POST", "/documents/new", new_post),
    ("GET", "/documents/<int:id>/file", file_page),
    ("GET", "/documents/<int:id>/delete", delete_page),
    ("POST", "/documents/<int:id>/delete", delete_post),
]
