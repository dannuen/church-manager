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
"""

from .. import documents as docs
from .. import text, ui
from ..server import Response
from ..ui import h, vi
from . import people as person_pages  # a module import on purpose: people.py imports this module too

# The one thing a Document is linked to: form field -> (glossary word, page of it).
LINKS = {
    "person_id": ("Person", "/people/{}"),
    "family_id": ("Family", "/families/{}"),
    "calendar_item_id": ("Calendar item", "/calendar/{}"),
}
_NAME_SQL = {
    "person_id": "SELECT full_name FROM person WHERE id = ?",
    "family_id": "SELECT name FROM family WHERE id = ?",
    "calendar_item_id": "SELECT title FROM calendar_item WHERE id = ?",
}
MB = 1024 * 1024


# ---------------------------------------------------------------- small logic (tested)

def fmt_size(size):
    """Whole bytes as plain words: ``512 bytes``, ``20 KB``, ``3,4 MB`` (integer maths only)."""
    if size < 1024:
        return ui.plural(size, "byte", "bytes")
    if size < MB:
        return f"{(size + 1023) // 1024} KB"
    tenths = (size * 10 + MB // 2) // MB
    return f"{tenths // 10:,}".replace(",", ".") + f",{tenths % 10} MB"


def parse_link(values):
    """The one link of a new Document from form or query values, like ``("person_id", 5)``.
    No link, two links or a bad number raise ``ValueError``."""
    given = [(key, (values.get(key) or "").strip()) for key in LINKS]
    given = [(key, raw) for key, raw in given if raw]
    if len(given) != 1:
        raise ValueError("A Document is added to one Person, one Family or one Calendar item.")
    key, raw = given[0]
    return key, text.to_id(raw, LINKS[key][0])


def link_target(conn, key, rid):
    """``(word, name, href)`` of the Person, Family or Calendar item, or ``ValueError`` if it is not there."""
    word, href = LINKS[key]
    row = conn.execute(_NAME_SQL[key], (rid,)).fetchone()
    if row is None:
        raise ValueError(f"No {word} with id {rid}.")
    return word, row[0], href.format(rid)


# ---------------------------------------------------------------- the shared block

def add_form(key, rid, error=None):
    """The Add document form: one file and the hidden link to its Person, Family or Calendar item."""
    inner = (
        ui.hidden(key, rid)
        + ui.field("File", "file", "", type="file", id=f"doc-file-{rid}", required=True, error=error,
                   hint=f"Any file up to {docs.MAX_SIZE // MB} MB. It is kept inside this church copy.")
        + ui.button("Add document", "secondary")
    )
    return ui.form("/documents/new", inner, multipart=True)


def _doc_row(row):
    """One Document: its name wraps to 2 lines at most (full name in the title), then size and date."""
    meta = f"{fmt_size(row['size'])} · added {ui.fmt_date(row['added_at'])}"
    name = row["original_name"]
    link = f'<a href="/documents/{int(row["id"])}/file">{h(name)}</a>'
    return ('<li class="row" data-row><span class="what wrap">'
            f'{person_pages.clamp2(link, name, lang="vi")}'
            f'<span class="sub num">{h(meta)}</span></span></li>')


def documents_panel(conn, **link):
    """The Documents block of one Person, Family or Calendar item: its files, newest first (each one
    a download link), and the Add document form. ``link`` is ``person_id=5``, ``family_id=2`` or
    ``calendar_item_id=9``."""
    (key, rid), = link.items()
    rows = list(reversed(docs.list_documents(conn, **{key: rid})))
    word = LINKS[key][0]
    body = (f'<ul class="rows">{"".join(_doc_row(r) for r in rows)}</ul>' if rows
            else person_pages.empty(f"No Document for this {word} yet."))
    meta = ui.plural(len(rows), "Document", "Documents") if rows else "Files kept in this church copy"
    form = f'<div class="add-form">{add_form(key, rid)}</div>'
    return f'<div id="documents">{person_pages.panel("documents", "Documents", body + form, meta=h(meta))}</div>'


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


def _linked(r):
    if r["person_id"] is not None:
        return f'<span class="faint">Person</span> {person_pages.person_link(r["person_id"], r["person_name"])}'
    if r["family_id"] is not None:
        return f'<span class="faint">Family</span> {person_pages.family_link(r["family_id"], r["family_name"])}'
    if r["calendar_item_id"] is not None:
        return (f'<span class="faint">Calendar item</span> <a href="/calendar/{int(r["calendar_item_id"])}">'
                f'{vi(r["item_title"])}</a> <span class="faint num">{h(ui.fmt_date(r["item_starts"]))}</span>')
    if r["sent_number"] is not None:
        return (f'<span class="faint">Sent document</span> '
                f'<a class="num" href="{h(ui.url("/sent", year=r["sent_year"]))}">{h(r["sent_number"])}</a>')
    return ui.DASH


def _delete_link(r):
    """The quiet Delete text action that ends a row of the list: it opens the one question."""
    return (f'<a href="/documents/{int(r["id"])}/delete" aria-label="Delete the Document {h(r["original_name"])}">'
            "Delete</a>")


def list_page(req):
    rows = req.conn.execute(_ALL_SQL).fetchall()
    lines = [[f'<a href="/documents/{int(r["id"])}/file">{vi(r["original_name"])}</a>', _linked(r),
              person_pages.num(fmt_size(r["size"])), person_pages.num(ui.fmt_date(r["added_at"])), _delete_link(r)]
             for r in rows]
    if lines:
        body = person_pages.table([("Document", False), ("Linked to", False), ("Size", True), ("Added", True),
                                   ("", False)], lines, "documents")
    else:
        body = person_pages.empty("No Document yet.")
    hint = ('<p class="hint list-foot">To add a Document, open its Person, Family or Calendar item '
            "and press Add document there.</p>")
    total = sum(r["size"] for r in rows)
    sub = h(f"{ui.plural(len(rows), 'Document', 'Documents')} · {fmt_size(total)} in this church copy · newest first")
    content = person_pages.list_panel("documents-list", "Documents list", body) + hint
    return Response.html(ui.page("Documents", content, "documents", sub=sub))


# ---------------------------------------------------------------- /documents/new

def _new_view(req, key, rid, error=None, status=200):
    word, name, href = link_target(req.conn, key, rid)
    body = (f'<section class="panel narrow" data-panel="add-document">{add_form(key, rid, error)}'
            f'<p class="hint">Back to <a href="{h(href)}">{vi(name)}</a></p></section>')
    return Response.html(ui.page("Add document", body, "documents", sub=f"For the {h(word)} {vi(name)}"), status)


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
            raise ValueError("Choose a file first.")
        file_name, data = chosen
        if not data:
            raise ValueError("The file is empty (0 bytes). Choose another file.")
        doc_id = docs.add_document(conn, req.state.copy_folder, data, file_name, **{key: rid})
    except ValueError as exc:
        return _new_view(req, key, rid, str(exc), 400)
    shown = docs.get_document(conn, doc_id)["original_name"]
    return Response.redirect(ui.url(href, msg=f"Document added: {shown}.") + "#documents")


# ---------------------------------------------------------------- /documents/<id>/file

def file_page(req):
    conn = req.conn
    row = docs.get_document(conn, req.params["id"])
    if row is None:
        return person_pages.not_found("Document", "/documents", "Go to Documents")
    path = docs.document_path(conn, req.state.copy_folder, row["id"])
    if not path.is_file():
        body = (f'<p class="lead">The file of {vi(row["original_name"])} is missing from the documents folder '
                'of this church copy.</p><p><a href="/documents">Go to Documents</a></p>')
        return Response.html(ui.page("File missing", body, "documents"), 404)
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
    facts = [("Size", person_pages.num(fmt_size(row["size"]))),
             ("Added", person_pages.num(ui.fmt_date(row["added_at"]))), ("Linked to", _linked(row))]
    kv = '<dl class="kv">' + "".join(f"<div><dt>{h(k)}</dt><dd>{v}</dd></div>" for k, v in facts) + "</dl>"
    numbers = _sent_numbers(conn, did)
    if len(numbers) == 1:
        keeps = f"The Sent document {numbers[0]} stays, with its number, date, Recipient and Purpose, but no file."
    elif numbers:
        keeps = (f"The Sent documents {', '.join(numbers)} stay, with their numbers, dates, Recipients and Purposes, "
                 "but no file.")
    else:
        keeps = ""
    form = ui.form(f"/documents/{did}/delete", ui.hidden("confirm", "yes") + ui.button("Yes, delete it", "danger"))
    body = (f'<section class="panel narrow" data-panel="confirm"><p class="lead">Delete the Document '
            f'<strong class="confirm-name" lang="vi">{h(row["original_name"])}</strong>?</p>{kv}'
            + (f'<p class="hint">{h(keeps)}</p>' if keeps else "")
            + '<p class="hint">The file is removed from this church copy. This cannot be undone.</p>'
            f'<div class="confirm-actions">{form}{ui.link_button("Cancel", "/documents")}</div></section>')
    return Response.html(ui.page("Delete this Document?", body, "documents"))


def _row_or_none(req):
    row = docs.get_document(req.conn, req.params["id"])
    return None if row is None else req.conn.execute(_ONE_SQL, (row["id"],)).fetchone()


def delete_page(req):
    row = _row_or_none(req)
    if row is None:
        return person_pages.not_found("Document", "/documents", "Go to Documents")
    return _confirm_delete(req.conn, row)


def delete_post(req):
    """Delete only with ``confirm=yes``; without it, the question again. The row goes in one
    transaction, then the file (``docs.delete_document``)."""
    row = _row_or_none(req)
    if row is None:
        return person_pages.not_found("Document", "/documents", "Go to Documents")
    if req.form.get("confirm") != "yes":
        return _confirm_delete(req.conn, row)
    left = docs.delete_document(req.conn, req.state.copy_folder, row["id"])
    msg = f"Document deleted: {row['original_name']}."
    if left is not None:  # the row is gone, but the file stays (for example it is open in another program)
        msg += (f" Its file {left.name} could not be removed from the documents folder. Close any program "
                "that has it open, then remove that file in File Explorer.")
    return Response.redirect(ui.url("/documents", msg=msg))


ROUTES = [
    ("GET", "/documents", list_page),
    ("GET", "/documents/new", new_page),
    ("POST", "/documents/new", new_post),
    ("GET", "/documents/<int:id>/file", file_page),
    ("GET", "/documents/<int:id>/delete", delete_page),
    ("POST", "/documents/<int:id>/delete", delete_post),
]
