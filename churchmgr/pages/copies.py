"""Copies (card C3): ``/copies`` says where this church copy is saved, makes a Handover, starts a
New church setup, and opens another church copy of the copies folder.

Rules kept here:
- A Handover is made only by ``handover.make_handover`` into ``<copies root>/handovers/``; the open
  church copy is never changed. A refused Handover says why in plain words and never shows the
  text of a Private note.
- New church setup makes a new folder in the copies root (``setup.new_church_setup``), with the default
  lists in the language picked on the form (Tiếng Việt at the start); it never touches the open church
  copy. The server then opens the new copy (``switch_copy`` also writes ``current.txt`` when the app was
  started the default way).
- A church copy is opened, and a Handover zip is given back, only by a name this page found in the
  folder itself, never by a path from the request. OneDrive folders are refused.
- Words on screen come from the text table (section ``copies``). Paths and file names are data: shown
  as they are, never translated.
"""

import sqlite3
from pathlib import Path

from .. import db, documents, handover, i18n, paths, settings
from .. import setup as church_setup
from .. import text, ui
from ..i18n import t, tn
from ..server import Response
from ..ui import h, vi
from .documents import fmt_size
from .people import empty, panel, person_link, table

HANDOVERS = "handovers"  # the folder in the copies root that holds the Handover zips
HANDOVER_ROWS = 5

# Where the text of a Private note was found: table -> (TEXT key of its word, page of the row or of the list).
_PLACES = {
    "person": ("copies.word_person", "/people/{}"), "family": ("copies.word_family", "/families/{}"),
    "chi_phai": ("copies.word_chi_phai", "/chi-phai/{}"), "calendar_item": ("copies.word_calendar_item", "/calendar/{}"),
    "head_count": ("copies.word_head_count", "/calendar"), "offering": ("copies.word_offering", "/money"),
    "expense": ("copies.word_expense", "/money"), "document": ("copies.word_document", "/documents"),
    "sent_document": ("copies.word_sent_document", "/sent"), "list_item": ("core.nav_lists", "/lists"),
    "setting": ("core.nav_settings", "/settings"),
}
# The words of a column the pastor can type into; any other column is ``copies.field_other``.
_FIELDS = {"full_name": "copies.field_name", "name": "copies.field_name", "original_name": "copies.field_file_name",
           "care_note": "copies.field_care_note", "absent_note": "copies.field_absent_note",
           "note": "copies.field_note", "address": "copies.field_address", "phone": "copies.field_phone",
           "title": "copies.field_title", "place": "copies.field_place", "subject": "copies.field_subject",
           "value": "copies.field_value"}
PLACE_ROWS = 10  # a refused Handover lists at most this many places


# ---------------------------------------------------------------- what is in the copies folder

def handovers_dir(copies_root):
    return Path(copies_root) / HANDOVERS


def _lang_attr(code):
    """`` lang="<code>"`` on a page that is not in English, ``""`` on an English page (it keeps the markup
    it always had). ``zxx`` (no language) marks a path, a file name or a flag; ``en`` the English name of a
    column or table. A screen reader and the check for English words then leave those words out."""
    return "" if ui.current_lang() == "en" else f' lang="{code}"'


def mark(value, code="zxx"):
    """``value`` escaped; in ``<span lang="<code>">`` on a page that is not in English (see ``_lang_attr``)."""
    attr = _lang_attr(code)
    return f"<span{attr}>{h(value)}</span>" if attr else h(value)


def path_html(path):
    """A folder or file path, escaped, that may wrap only after a ``\\`` or ``/`` (never inside a name)."""
    return (f'<span class="path"{_lang_attr("zxx")}>' + h(path).replace("\\", "\\<wbr>").replace("/", "/<wbr>")
            + "</span>")


def size_text(size):
    """``fmt_size`` in the words of the page: below 1 KB it says ``byte`` itself.
    shortcut: ``pages/documents.py`` (another card) still writes ``byte``/``bytes`` in English; use its
    ``fmt_size`` alone once that card puts it in the text table."""
    return tn("copies.bytes", size) if size < 1024 else fmt_size(size)


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
    current_txt = mark(paths.CURRENT_FILE)
    if current is not None and current.resolve() == state.copy_folder:
        at_start = ui.t_html("copies.start_this", file=current_txt)
    elif current is not None:
        at_start = ui.t_html("copies.start_other", path=path_html(current), file=current_txt)
    else:
        at_start = ui.DASH
    if not state.remember:
        at_start += ('<br><span class="faint">'
                     + ui.t_html("copies.set_folder", flag=mark("--copy"), file=current_txt) + "</span>")
    counts = req.conn.execute(
        "SELECT (SELECT COUNT(*) FROM person), (SELECT COUNT(*) FROM document), "
        "(SELECT COALESCE(SUM(size), 0) FROM document)").fetchone()
    inside = ui.t_html("copies.inside", db=mark(db.DB_NAME), people=h(tn("people.count", counts[0])),
                       documents=h(tn("copies.documents", counts[1])), size=h(size_text(counts[2])))
    rows = [
        (t("copies.church"), vi(req.church_name)),
        (t("copies.saved_in_row"), path_html(state.copy_folder)),
        (t("copies.copies_folder"), path_html(state.copies_root)),
        (t("copies.inside_row"), inside),
        (t("copies.opens_at_start"), at_start),
    ]
    kv = '<dl class="kv wide">' + "".join(f"<div><dt>{h(k)}</dt><dd>{v}</dd></div>" for k, v in rows) + "</dl>"
    note = f'<p class="hint">{h(t("copies.keep_outside"))}</p>'
    return panel("this-copy", t("copies.this_copy"), kv + note)


def _copies_panel(req, error):
    state = req.state
    lines = []
    for c in list_copies(state.copies_root):
        is_open = c["folder"] == state.copy_folder
        name = vi(c["name"]) if c["name"] else f'<span class="faint">{h(t("copies.cannot_read"))}</span>'
        if is_open:
            action = f'<span class="tag open">{h(t("copies.open_now"))}</span>'
        elif c["onedrive"]:
            action = f'<span class="faint">{h(t("copies.in_onedrive"))}</span>'
        elif c["name"] is None:
            action = ui.DASH
        else:
            label = h(t("copies.open_label", name=c["name"]))
            action = (f'<form class="row-form" action="/copies/open" method="post">{ui.hidden("folder", c["folder"].name)}'
                      f'<button class="btn secondary" type="submit" aria-label="{label}">{h(t("core.btn_open"))}</button>'
                      "</form>")
        persons = (f'<span class="num">{h(tn("people.count", c["persons"]))}</span>' if c["persons"] is not None
                   else ui.DASH)
        lines.append([name, path_html(c["folder"].name), persons, action])
    if lines:
        body = table([(t("copies.church"), False), (t("copies.folder"), False), (t("copies.people"), True), ("", True)],
                     lines, "copies")
    else:
        body = empty(t("copies.no_copies"))
    if error and error[0] == "open":
        body = f'<p class="error" role="alert">{h(i18n.error_text(error[1]))}</p>' + body
    meta = ui.t_html("copies.list_meta", db=mark(db.DB_NAME))
    return panel("copies", t("copies.list_title"), body, meta=meta)


def _handover_result(req):
    made = find_handover(req.state.copies_root, req.query.get("made") or "")
    if made is None:
        return ""
    saved_as = ui.t_html("copies.saved_as", path=path_html(made), size=h(size_text(made.stat().st_size)))
    return ('<div class="result" role="status" data-row>'
            f'<p><strong>{h(t("copies.made"))}</strong> {h(t("copies.notes_removed"))}</p>'
            f'<p class="hint">{saved_as}</p>'
            f'<p><a class="btn secondary" href="/copies/handovers/{h(made.name)}">{h(t("copies.download"))}</a></p>'
            "</div>")


_LABEL_SQL = {"person": "SELECT full_name FROM person WHERE id = ?", "family": "SELECT name FROM family WHERE id = ?",
              "chi_phai": "SELECT name FROM chi_phai WHERE id = ?",
              "calendar_item": "SELECT title FROM calendar_item WHERE id = ?"}


def _word_html(table_name):
    """The word on screen for a table of the church copy, as HTML. A link table has no word of its own:
    ``copies.word_other`` with its English name (``person status``)."""
    if table_name in _PLACES:
        return h(t(_PLACES[table_name][0]))
    return ui.t_html("copies.word_other", table=mark(table_name.replace("_", " "), "en"))


def _row_link(conn, table_name, rowid, bodies):
    """A link to the Person, Family, Chi phái or Calendar item ``rowid``, named safely."""
    key, href = _PLACES[table_name]
    label = conn.execute(_LABEL_SQL[table_name], (rowid,)).fetchone()[0]
    return (f'<a href="{h(href.format(rowid))}" lang="vi">'
            f'{h(_safe_label(label, bodies, f"{t(key)} {rowid}"))}</a>')


def _db_place(conn, place, bodies, _docs_folder):
    _person_id, table_name, rowid, col = place
    href = _PLACES.get(table_name, (None, "/"))[1]
    if col in _FIELDS:
        field = h(t(_FIELDS[col]))
    else:  # a column the pastor does not type into (a date, a code): its English name
        field = ui.t_html("copies.field_other", col=mark(col.replace("_", " "), "en"))
    if table_name in _LABEL_SQL:
        return ui.t_html("copies.place_field_of", field=field, word=_word_html(table_name),
                         link=_row_link(conn, table_name, rowid, bodies))
    return ui.t_html("copies.place_field_in", field=field, link=f'<a href="{h(href)}">{_word_html(table_name)}</a>')


def _document_place(conn, place, bodies, docs_folder):
    """Where a Document file holds the words, then what to do about it: Delete for a Document. A file
    of the documents folder that no Document row names cannot be deleted in the app: File Explorer."""
    _person_id, doc_id, stored = place
    if doc_id is None:
        shown = _safe_label(stored, bodies, "")
        file_html = ui.t_html("copies.place_file", path=path_html(shown)) if shown else h(t("copies.place_a_file"))
        return ui.t_html("copies.place_stray", file=file_html, folder=path_html(docs_folder))
    doc = documents.get_document(conn, doc_id)
    name = _safe_label(doc["original_name"], bodies, f"{t('copies.word_document')} {doc_id}")
    name_html = f'<span lang="vi">{h(name)}</span>'
    owner = next(((col, table_name) for col, table_name in
                  (("person_id", "person"), ("family_id", "family"), ("calendar_item_id", "calendar_item"))
                  if doc[col] is not None), None)
    if owner:
        where = ui.t_html("copies.place_doc_of", name=name_html,
                          link=_row_link(conn, owner[1], doc[owner[0]], bodies))
    else:
        where = ui.t_html("copies.place_doc", name=name_html)
    return (f'{where}. <a href="/documents/{int(doc_id)}/delete" aria-label="{h(t("copies.delete_doc", name=name))}">'
            f'{h(t("core.btn_delete"))}</a>')


def _refusal_html(conn, copy_folder, refusal):
    """A refused Handover (a ``handover.HandoverError``) in plain words: what was found and where
    (in the database or in a Document file, each Document with its Delete link), never the words of
    the Private note. Changing the Private note does not change a Document file, so the page says so."""
    not_made = f'<strong>{h(t("copies.not_made"))}</strong>'
    if not refusal.private_text_found:
        return (f'<div class="refusal" role="alert"><p>{not_made} {h(i18n.error_text(refusal))}</p>'
                f'<p>{h(t("copies.nothing_changed"))}</p></div>')
    bodies = [r[0] for r in conn.execute("SELECT body FROM private_note") if len(r[0]) >= handover.MIN_CHECK_LENGTH]
    places = ([(p, _db_place) for p in private_text_places(conn)]
              + [(p, _document_place) for p in private_text_documents(conn, copy_folder)])
    docs_folder = db.documents_folder(copy_folder)
    lines = []
    for place, where in places[:PLACE_ROWS]:
        person_id = place[0]
        owner = conn.execute("SELECT full_name FROM person WHERE id = ?", (person_id,)).fetchone()[0]
        # whose Private note: the link opens their Private note panel, where each note has its Edit link
        owner_html = person_link(person_id, _safe_label(owner, bodies, f"{t('copies.word_person')} {person_id}"),
                                 "#private-note")
        lines.append("<li>" + ui.t_html("copies.place_line", owner=owner_html,
                                        where=where(conn, place, bodies, docs_folder)) + "</li>")
    if len(places) > PLACE_ROWS:
        lines.append(f'<li>{h(t("copies.more_places", n=len(places) - PLACE_ROWS))}</li>')
    found = f'<ul class="places">{"".join(lines)}</ul>' if lines else ""
    return ('<div class="refusal" role="alert">'
            f'<p>{not_made} {h(t("copies.found_elsewhere"))}</p>'
            f"{found}"
            f'<p>{h(t("copies.fix_places"))}</p></div>')


def _handover_panel(req, refusal):
    root = req.state.copies_root
    out = handovers_dir(root)
    intro = f'<p>{h(t("copies.handover_intro"))}</p>'
    form = ui.form("/copies/handover", ui.button(t("copies.make")))
    where = f'<p class="hint">{ui.t_html("copies.saved_in", path=path_html(out))}</p>'
    made = list_handovers(root)
    if made:
        rows = "".join(
            f'<li class="row" data-row><span class="what wrap">'
            f'<a class="file-name" href="/copies/handovers/{h(p.name)}"{_lang_attr("zxx")}>{h(p.name)}</a></span>'
            f'<span class="side num">{h(size_text(size))}</span></li>' for p, size in made[:HANDOVER_ROWS])
        listing = f'<h3 class="sub-head">{h(t("copies.made_list"))}</h3><ul class="rows">{rows}</ul>'
    else:
        listing = ""
    refusal_html = _refusal_html(req.conn, req.state.copy_folder, refusal) if refusal else ""
    body = _handover_result(req) + refusal_html + intro + form + where + listing
    return panel("handover", t("copies.handover"), body)


def _setup_panel(error, lang):
    """The New church setup form: the church name and the language of the new church copy (its default
    lists are made in that language; Tiếng Việt at the start)."""
    errors = {error[1]: i18n.error_text(error[2])} if error and error[0] == "setup" else {}
    form = ui.form("/copies/new",
                   ui.field(t("settings.church_name"), "church_name", "", error=errors.get("church_name"),
                            required=True, autocomplete="off", lang="vi", hint=t("setup.name_hint"))
                   + ui.select_field(t("core.language"), settings.LANGUAGE, ui.LANG_NAMES, lang,
                                     error=errors.get(settings.LANGUAGE), hint=t("setup.language_hint"))
                   + ui.button(t("copies.setup_start"), "secondary"))
    intro = f'<p>{h(t("copies.setup_intro"))}</p>'
    return panel("new-church-setup", t("setup.title"), intro + form)


def _view(req, error=None, refusal=None, status=200, lang=i18n.DEFAULT_LANG):
    left = _this_copy(req) + _copies_panel(req, error)
    right = _handover_panel(req, refusal) + _setup_panel(error, lang)
    body = (f'<div class="grid copies"><div class="span-7 stack">{left}</div>'
            f'<div class="span-5 stack">{right}</div></div>')
    n = len(list_copies(req.state.copies_root))
    sub = ui.t_html("copies.sub", church=vi(req.church_name), copies=h(tn("copies.copies", n)))
    return Response.html(ui.page(t("copies.title"), body, "copies", sub=sub), status)


def copies_page(req):
    return _view(req)


def handover_post(req):
    try:
        made = handover.make_handover(req.state.copy_folder, handovers_dir(req.state.copies_root))
    except handover.HandoverError as exc:
        return _view(req, refusal=exc, status=400)
    return Response.redirect(ui.url("/copies", made=made.name, msg=f'{t("copies.made")} {t("copies.notes_removed")}'))


def handover_file(req):
    found = find_handover(req.state.copies_root, req.params["name"])
    if found is None:
        body = (f'<p class="lead">{h(t("copies.no_zip"))}</p>'
                f'<p><a href="/copies">{h(t("copies.go_copies"))}</a></p>')
        return Response.html(ui.page(t("copies.zip_not_found"), body, "copies"), 404)
    return Response.file(found, found.name)


def new_church_post(req):
    name = req.form.get("church_name", "")
    lang = req.form.get(settings.LANGUAGE) or i18n.DEFAULT_LANG  # no field: Tiếng Việt, as on the form
    try:
        settings.check_language(lang)
    except ValueError as exc:
        return _view(req, ("setup", settings.LANGUAGE, exc), status=400)
    try:
        text.clean_name(name, "settings.church_name")  # refuse an empty name before anything is made
        # The handovers folder exists first, so a church called "Handovers" gets "handovers-2", not that folder.
        handovers_dir(req.state.copies_root).mkdir(parents=True, exist_ok=True)
        folder = church_setup.new_church_setup(req.state.copies_root, name, lang)
        req.state.switch_copy(folder)
    except (ValueError, db.ChurchCopyError) as exc:  # paths.CopyPathError is a ValueError
        return _view(req, ("setup", "church_name", exc), status=400, lang=lang)
    church = text.clean_name(name, "settings.church_name")
    # the flash is in the language the next page shows: the new church copy's
    return Response.redirect(ui.url("/", msg=t("copies.setup_done", lang, church=church)))


def open_post(req):
    wanted = req.form.get("folder") or ""
    found = next((c for c in list_copies(req.state.copies_root) if c["folder"].name == wanted), None)
    try:
        if found is None:
            raise i18n.TextError("copies.err_no_such_copy")
        if found["onedrive"]:
            raise i18n.TextError("copies.err_copy_in_onedrive")
        if found["folder"] == req.state.copy_folder:
            return Response.redirect(ui.url("/", msg=t("copies.already_open")))
        req.state.switch_copy(found["folder"])
    except (ValueError, db.ChurchCopyError) as exc:
        return _view(req, ("open", exc), status=400)
    # the flash is in the language the next page shows: the opened church copy's (req.conn may be the old one)
    conn = db.connect(found["folder"] / db.DB_NAME)
    try:
        lang = settings.get_language(conn)
    finally:
        conn.close()
    return Response.redirect(ui.url("/", msg=t("copies.opened", lang, name=found["name"] or found["folder"].name)))


ROUTES = [
    ("GET", "/copies", copies_page),
    ("POST", "/copies/handover", handover_post),
    ("GET", "/copies/handovers/<name>", handover_file),
    ("POST", "/copies/new", new_church_post),
    ("POST", "/copies/open", open_post),
]
