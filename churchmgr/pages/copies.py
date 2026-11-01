"""Copies (card C3): ``/copies`` says where this church copy is saved, makes a Handover, starts a
New church setup, and opens another church copy of the copies folder.

Rules kept here:
- A Handover is made only by ``handover.make_handover`` into ``<copies root>/handovers/``; the open
  church copy is never changed. A refused Handover says why in plain words and never shows the
  text of a Private note.
- New church setup makes a new folder in the copies root (``setup.new_church_setup``); it never
  touches the open church copy. The server then opens the new copy (``switch_copy`` also writes
  ``current.txt`` when the app was started the default way).
- A church copy is opened, and a Handover zip is given back, only by a name this page found in the
  folder itself, never by a path from the request. OneDrive folders are refused.
"""

import sqlite3
from pathlib import Path

from .. import db, documents, handover, paths
from .. import setup as church_setup
from .. import text, ui
from ..server import Response
from ..ui import h, vi
from .documents import fmt_size
from .people import empty, panel, person_link, table

HANDOVERS = "handovers"  # the folder in the copies root that holds the Handover zips
HANDOVER_ROWS = 5

# Where the text of a Private note was found: table -> (glossary word, page of the row or of the list).
_PLACES = {
    "person": ("Person", "/people/{}"), "family": ("Family", "/families/{}"),
    "chi_phai": ("Chi phái", "/chi-phai/{}"), "calendar_item": ("Calendar item", "/calendar/{}"),
    "head_count": ("Head count", "/calendar"), "offering": ("Offering", "/money"), "expense": ("Expense", "/money"),
    "document": ("Document", "/documents"), "sent_document": ("Sent document", "/sent"),
    "list_item": ("Lists", "/lists"), "setting": ("Settings", "/settings"),
}
_FIELDS = {"full_name": "name", "original_name": "file name", "care_note": "Care note", "absent_note": "absent note"}
PLACE_ROWS = 10  # a refused Handover lists at most this many places


# ---------------------------------------------------------------- what is in the copies folder

def handovers_dir(copies_root):
    return Path(copies_root) / HANDOVERS


def path_html(path):
    """A folder or file path, escaped, that may wrap only after a ``\\`` or ``/`` (never inside a name)."""
    return '<span class="path">' + h(path).replace("\\", "\\<wbr>").replace("/", "/<wbr>") + "</span>"


def _read_copy(folder):
    """``(church name, number of Persons)`` of the church copy in ``folder``, read-only; ``None`` if unreadable."""
    try:
        conn = sqlite3.connect((folder / db.DB_NAME).resolve().as_uri() + "?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        row = conn.execute("SELECT value FROM setting WHERE key = 'church_name'").fetchone()
        persons = conn.execute("SELECT COUNT(*) FROM person").fetchone()[0]
        return (row[0] if row else None), persons
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def list_copies(copies_root):
    """Every church copy in the copies root (a folder there with ``church.db``), by church name.

    Each is a dict: ``folder`` (Path), ``name`` and ``persons`` (``None`` when it cannot be read),
    ``onedrive`` (True when the path is refused)."""
    root = Path(copies_root)
    found = []
    if not root.is_dir():
        return found
    for folder in root.iterdir():
        if folder.is_symlink() or not folder.is_dir() or not (folder / db.DB_NAME).is_file():
            continue
        try:
            paths.check_not_onedrive(folder)
            onedrive = False
        except paths.CopyPathError:
            onedrive = True
        info = None if onedrive else _read_copy(folder)
        name, persons = info if info else (None, None)
        found.append({"folder": folder.resolve(), "name": name, "persons": persons, "onedrive": onedrive})
    return sorted(found, key=lambda c: ((c["name"] or "").lower(), c["folder"].name))


def list_handovers(copies_root):
    """The Handover zips in ``<copies root>/handovers``, newest first: ``[(Path, size), ...]``."""
    folder = handovers_dir(copies_root)
    if not folder.is_dir():
        return []
    zips = [p for p in folder.iterdir()
            if p.is_file() and not p.is_symlink() and p.name.startswith("handover-") and p.suffix == ".zip"]
    zips.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    return [(p, p.stat().st_size) for p in zips]


def find_handover(copies_root, name):
    """The Handover zip called ``name`` as found in the folder listing, or ``None``. No path is joined."""
    return next((p for p, _size in list_handovers(copies_root) if p.name == name), None)


def _private_notes(conn, min_length):
    """``[(person id, text), ...]`` of the Private notes long enough to search for."""
    return [(r["person_id"], r["body"]) for r in conn.execute("SELECT person_id, body FROM private_note")
            if isinstance(r["body"], str) and len(r["body"]) >= min_length]


def private_text_places(conn, min_length=handover.MIN_CHECK_LENGTH):
    """Where the text of a Private note is also written in the church copy (the reason a Handover is
    refused). Returns sorted ``[(note person id, table, row id, column), ...]``; never the text itself."""
    notes = _private_notes(conn, min_length)
    if not notes:
        return []
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name != 'private_note'")]
    places = set()
    for table_name in tables:
        cols = [c["name"] for c in conn.execute(f'PRAGMA table_info("{table_name}")') if c["type"].upper() == "TEXT"]
        for col in cols:
            for person_id, body in notes:
                for row in conn.execute(f'SELECT rowid FROM "{table_name}" WHERE instr("{col}", ?) > 0', (body,)):
                    places.add((person_id, table_name, row[0], col))
    return sorted(places)


def private_text_documents(conn, copy_folder, min_length=handover.MIN_CHECK_LENGTH):
    """Which Document files hold the text of a Private note, read as plain bytes like the Handover
    check (``handover.private_text_files``). Returns sorted ``[(note person id, Document id, file name
    on disk), ...]``; the Document id is ``None`` for a file of ``documents/`` with no Document row.
    Never the text itself."""
    notes = _private_notes(conn, min_length)
    if not notes:
        return []
    ids = {r["stored_name"]: r["id"] for r in conn.execute("SELECT id, stored_name FROM document")}
    files = documents.documents_on_disk(copy_folder)
    found = {(person_id, ids.get(f.name), f.name) for f, person_id in handover.private_text_files(files, notes)}
    return sorted(found, key=lambda t: (t[0], t[1] or 0, t[2]))


def _safe_label(label, bodies, fallback):
    """``label`` unless it holds the text of a Private note; then ``fallback`` (the words never show)."""
    if not label or any(b in label for b in bodies):
        return fallback
    return label


# ---------------------------------------------------------------- /copies

def _this_copy(req):
    state = req.state
    current = paths.read_current(state.copies_root)
    if current is not None and current.resolve() == state.copy_folder:
        at_start = "This church copy (named in current.txt)"
    elif current is not None:
        at_start = f'{path_html(current)} (named in current.txt)'
    else:
        at_start = ui.DASH
    if not state.remember:
        at_start += ('<br><span class="faint">Church Manager was started with a set folder (--copy), '
                     "so opening another copy does not change current.txt.</span>")
    counts = req.conn.execute(
        "SELECT (SELECT COUNT(*) FROM person), (SELECT COUNT(*) FROM document), "
        "(SELECT COALESCE(SUM(size), 0) FROM document)").fetchone()
    rows = [
        ("Church", vi(req.church_name)),
        ("Saved in", f'{path_html(state.copy_folder)}'),
        ("Copies folder", f'{path_html(state.copies_root)}'),
        ("Inside", h(f"{db.DB_NAME} ({ui.plural(counts[0], 'Person', 'People')}) and the documents folder "
                     f"({ui.plural(counts[1], 'Document', 'Documents')}, {fmt_size(counts[2])})")),
        ("Opens at start", at_start),
    ]
    kv = '<dl class="kv wide">' + "".join(f"<div><dt>{h(k)}</dt><dd>{v}</dd></div>" for k, v in rows) + "</dl>"
    note = '<p class="hint">A church copy is kept outside OneDrive. Copy the whole folder to keep a spare.</p>'
    return panel("this-copy", "This church copy", kv + note)


def _copies_panel(req, error):
    state = req.state
    lines = []
    for c in list_copies(state.copies_root):
        is_open = c["folder"] == state.copy_folder
        name = vi(c["name"]) if c["name"] else '<span class="faint">Cannot be read</span>'
        if is_open:
            action = '<span class="tag open">Open now</span>'
        elif c["onedrive"]:
            action = '<span class="faint">Inside OneDrive: not opened</span>'
        elif c["name"] is None:
            action = ui.DASH
        else:
            action = (f'<form class="row-form" action="/copies/open" method="post">{ui.hidden("folder", c["folder"].name)}'
                      f'<button class="btn secondary" type="submit" aria-label="Open {h(c["name"])}">Open</button></form>')
        persons = f'<span class="num">{h(ui.plural(c["persons"], "Person", "People"))}</span>' if c["persons"] is not None else ui.DASH
        lines.append([name, f'<span class="path">{h(c["folder"].name)}</span>', persons, action])
    if lines:
        body = table([("Church", False), ("Folder", False), ("People", True), ("", True)], lines, "copies")
    else:
        body = empty("No church copy in the copies folder.")
    if error and error[0] == "open":
        body = f'<p class="error" role="alert">{h(error[1])}</p>' + body
    meta = "Folders of the copies folder that hold a church.db"
    return panel("copies", "Church copies", body, meta=meta)


def _handover_result(req):
    made = find_handover(req.state.copies_root, req.query.get("made") or "")
    if made is None:
        return ""
    return ('<div class="result" role="status" data-row>'
            '<p><strong>Handover made.</strong> Private notes were removed.</p>'
            f'<p class="hint">Saved as {path_html(made)} ({h(fmt_size(made.stat().st_size))})</p>'
            f'<p><a class="btn secondary" href="/copies/handovers/{h(made.name)}">Download the Handover zip</a></p>'
            "</div>")


_LABEL_SQL = {"person": "SELECT full_name FROM person WHERE id = ?", "family": "SELECT name FROM family WHERE id = ?",
              "chi_phai": "SELECT name FROM chi_phai WHERE id = ?",
              "calendar_item": "SELECT title FROM calendar_item WHERE id = ?"}


def _row_link(conn, table_name, rowid, bodies):
    """A link to the Person, Family, Chi phái or Calendar item ``rowid``, named safely."""
    word, href = _PLACES[table_name]
    label = conn.execute(_LABEL_SQL[table_name], (rowid,)).fetchone()[0]
    return (f'<a href="{h(href.format(rowid))}" lang="vi">'
            f'{h(_safe_label(label, bodies, f"{word} {rowid}"))}</a>')


def _db_place(conn, place, bodies, _docs_folder):
    _person_id, table_name, rowid, col = place
    word, href = _PLACES.get(table_name, (table_name.replace("_", " "), "/"))
    field = _FIELDS.get(col, col.replace("_", " "))
    if table_name in _LABEL_SQL:
        return f"the {h(field)} of the {h(word)} {_row_link(conn, table_name, rowid, bodies)}."
    return f'a {h(field)} in <a href="{h(href)}">{h(word)}</a>.'


def _document_place(conn, place, bodies, docs_folder):
    """Where a Document file holds the words, then what to do about it: Delete for a Document. A file
    of the documents folder that no Document row names cannot be deleted in the app: File Explorer."""
    _person_id, doc_id, stored = place
    if doc_id is None:
        shown = _safe_label(stored, bodies, "")
        file_html = f"the file {path_html(shown)}" if shown else "a file"
        return (f"{file_html} of the documents folder. No Document in the app has this file: remove it from "
                f"the folder {path_html(docs_folder)} in File Explorer.")
    doc = documents.get_document(conn, doc_id)
    name = _safe_label(doc["original_name"], bodies, f"Document {doc_id}")
    where = f'the Document <span lang="vi">{h(name)}</span>'
    for col, table_name in (("person_id", "person"), ("family_id", "family"), ("calendar_item_id", "calendar_item")):
        if doc[col] is not None:
            where += f" of {_row_link(conn, table_name, doc[col], bodies)}"
            break
    return (f'{where}. <a href="/documents/{int(doc_id)}/delete" aria-label="Delete the Document {h(name)}">'
            "Delete</a>")


def _refusal_html(conn, copy_folder, refusal):
    """A refused Handover (a ``handover.HandoverError``) in plain words: what was found and where
    (in the database or in a Document file, each Document with its Delete link), never the words of
    the Private note. Changing the Private note does not change a Document file, so the page says so."""
    if not refusal.private_text_found:
        return (f'<div class="refusal" role="alert"><p><strong>Handover not made.</strong> {h(refusal)}</p>'
                "<p>Nothing was changed. Fix this, then press Make Handover again.</p></div>")
    bodies = [r[0] for r in conn.execute("SELECT body FROM private_note") if len(r[0]) >= handover.MIN_CHECK_LENGTH]
    places = ([(p, _db_place) for p in private_text_places(conn)]
              + [(p, _document_place) for p in private_text_documents(conn, copy_folder)])
    docs_folder = db.documents_folder(copy_folder)
    lines = []
    for place, where in places[:PLACE_ROWS]:
        person_id = place[0]
        owner = conn.execute("SELECT full_name FROM person WHERE id = ?", (person_id,)).fetchone()[0]
        # whose Private note: the link opens their Private note panel, where each note has its Edit link
        owner_html = person_link(person_id, _safe_label(owner, bodies, f"Person {person_id}"), "#private-note")
        lines.append(f"<li>The Private note of {owner_html} is also written in "
                     f"{where(conn, place, bodies, docs_folder)}</li>")
    if len(places) > PLACE_ROWS:
        lines.append(f"<li>And {len(places) - PLACE_ROWS} more places.</li>")
    found = f'<ul class="places">{"".join(lines)}</ul>' if lines else ""
    return ('<div class="refusal" role="alert">'
            "<p><strong>Handover not made.</strong> The words of a Private note are also written somewhere else "
            "in this church copy, so they would go to the next pastor.</p>"
            f"{found}"
            "<p>To fix it, take the private words out of each place above. For a Document, press Delete: "
            "changing the Private note does not change a Document file, and the file still goes to the next "
            "pastor. For other text, open it and change it. Then press Make Handover again. "
            "Nothing was changed and no zip was saved.</p></div>")


def _handover_panel(req, refusal):
    root = req.state.copies_root
    out = handovers_dir(root)
    intro = ("<p>A Handover is one zip file for the next pastor of this church: the database and every "
             "Document. Private notes are removed from it. This church copy is not changed.</p>")
    form = ui.form("/copies/handover", ui.button("Make Handover"))
    where = f'<p class="hint">Saved in {path_html(out)}</p>'
    made = list_handovers(root)
    if made:
        rows = "".join(
            f'<li class="row" data-row><span class="what wrap">'
            f'<a class="file-name" href="/copies/handovers/{h(p.name)}">{h(p.name)}</a></span>'
            f'<span class="side num">{h(fmt_size(size))}</span></li>' for p, size in made[:HANDOVER_ROWS])
        listing = f'<h3 class="sub-head">Handovers made</h3><ul class="rows">{rows}</ul>'
    else:
        listing = ""
    refusal_html = _refusal_html(req.conn, req.state.copy_folder, refusal) if refusal else ""
    body = _handover_result(req) + refusal_html + intro + form + where + listing
    return panel("handover", "Handover", body)


def _setup_panel(error):
    message = error[1] if error and error[0] == "setup" else None
    form = ui.form("/copies/new",
                   ui.field("Church name", "church_name", "", error=message, required=True, autocomplete="off",
                            lang="vi", hint="For example: Hội Thánh Tin Lành Bình An")
                   + ui.button("Start New church setup", "secondary"))
    intro = ("<p>Starts a blank church copy that keeps only the default lists, in a new folder of the copies "
             "folder. Church Manager then opens it. This church copy is kept; open it again from Church copies.</p>")
    return panel("new-church-setup", "New church setup", intro + form)


def _view(req, error=None, refusal=None, status=200):
    left = _this_copy(req) + _copies_panel(req, error)
    right = _handover_panel(req, refusal) + _setup_panel(error)
    body = (f'<div class="grid copies"><div class="span-7 stack">{left}</div>'
            f'<div class="span-5 stack">{right}</div></div>')
    n = len(list_copies(req.state.copies_root))
    sub = h(f"{req.church_name} is open · {ui.plural(n, 'church copy', 'church copies')} in the copies folder")
    return Response.html(ui.page("Copies", body, "copies", sub=sub), status)


def copies_page(req):
    return _view(req)


def handover_post(req):
    try:
        made = handover.make_handover(req.state.copy_folder, handovers_dir(req.state.copies_root))
    except handover.HandoverError as exc:
        return _view(req, refusal=exc, status=400)
    return Response.redirect(ui.url("/copies", made=made.name, msg="Handover made. Private notes were removed."))


def handover_file(req):
    found = find_handover(req.state.copies_root, req.params["name"])
    if found is None:
        body = '<p class="lead">There is no Handover zip with this name.</p><p><a href="/copies">Go to Copies</a></p>'
        return Response.html(ui.page("Handover not found", body, "copies"), 404)
    return Response.file(found, found.name)


def new_church_post(req):
    name = req.form.get("church_name", "")
    try:
        text.clean_name(name, "Church name")  # refuse an empty name before anything is made
        # The handovers folder exists first, so a church called "Handovers" gets "handovers-2", not that folder.
        handovers_dir(req.state.copies_root).mkdir(parents=True, exist_ok=True)
        folder = church_setup.new_church_setup(req.state.copies_root, name)
        req.state.switch_copy(folder)
    except (ValueError, db.ChurchCopyError) as exc:  # paths.CopyPathError is a ValueError
        return _view(req, ("setup", str(exc)), status=400)
    church = text.clean_name(name, "Church name")
    return Response.redirect(ui.url("/", msg=f"New church setup is done: {church}. This is its Dashboard. "
                                             "The other church copies are kept in Copies."))


def open_post(req):
    wanted = req.form.get("folder") or ""
    found = next((c for c in list_copies(req.state.copies_root) if c["folder"].name == wanted), None)
    try:
        if found is None:
            raise ValueError("There is no church copy with this folder name in the copies folder.")
        if found["onedrive"]:
            raise ValueError("This church copy is inside OneDrive, so it is not opened. Move it outside OneDrive first.")
        if found["folder"] == req.state.copy_folder:
            return Response.redirect(ui.url("/", msg="This church copy is already open."))
        req.state.switch_copy(found["folder"])
    except (ValueError, db.ChurchCopyError) as exc:
        return _view(req, ("open", str(exc)), status=400)
    return Response.redirect(ui.url("/", msg=f"Opened {found['name'] or found['folder'].name}."))


ROUTES = [
    ("GET", "/copies", copies_page),
    ("POST", "/copies/handover", handover_post),
    ("GET", "/copies/handovers/<name>", handover_file),
    ("POST", "/copies/new", new_church_post),
    ("POST", "/copies/open", open_post),
]
