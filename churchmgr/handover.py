"""Handover: give the church copy to the next pastor, with Private notes removed.

Steps (any failed check raises ``HandoverError`` and leaves no zip):
1. Copy ``church.db`` with the SQLite backup API into a work folder (the source
   is opened read-only and never changed).
2. On the copy: ``PRAGMA secure_delete=ON``, ``DELETE FROM private_note``, ``VACUUM``.
3. Check: no Private note row is left, the database is whole, and no Private
   note text (4+ characters) is found in the bytes of the file, nor in the bytes of any
   Document file (as UTF-8, NFC and NFD; text inside Word or PDF files is not read).
4. Zip ``church.db`` and every file in ``documents/``, check the zip again, then
   give it its final name ``handover-<slug>-<YYYY-MM-DD>.zip`` (``-2``, ``-3`` if taken).
"""

import os
import shutil
import sqlite3
import tempfile
import unicodedata
import zipfile
from pathlib import Path

from . import db, documents, paths, schema, text

MIN_CHECK_LENGTH = 4  # Private note texts this long or longer are searched for in the bytes


class HandoverError(Exception):
    """The Handover was stopped. No zip was made.

    ``private_text_found`` is True only when the text of a Private note was found in the
    handover database or in a Document file (it is also written somewhere else in the church
    copy). The Copies page then lists where, instead of showing the message.
    """

    def __init__(self, message, private_text_found=False):
        super().__init__(message)
        self.private_text_found = private_text_found


def _connect_ro(path):
    return sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True)


def _note_texts(conn):
    return [
        (note_id, body.encode("utf-8"))
        for note_id, body in conn.execute("SELECT id, body FROM private_note")
        if isinstance(body, str) and len(body) >= MIN_CHECK_LENGTH
    ]


def _read_source(db_path):
    """Return ``(church slug, [(note id, private note text as UTF-8 bytes)])``. Changes nothing."""
    src = _connect_ro(db_path)
    try:
        version = src.execute("PRAGMA user_version").fetchone()[0]
        if version != schema.SCHEMA_VERSION:
            raise HandoverError(f"{db_path} is not a Church Manager database of version {schema.SCHEMA_VERSION}.")
        row = src.execute("SELECT value FROM setting WHERE key = 'church_name'").fetchone()
        slug = text.slugify(row[0] if row else "church")
        bodies = _note_texts(src)
    finally:
        src.close()
    return slug, bodies


def _backup(db_path, target):
    """Copy the source database into ``target`` with the backup API. Returns the
    Private note texts of the copy (the same notes as the source at that moment)."""
    src = _connect_ro(db_path)
    try:
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
            return _note_texts(dst)
        finally:
            dst.close()
    finally:
        src.close()


def _strip_private(path):
    """Remove every Private note from the database file at ``path`` and rebuild the file."""
    conn = sqlite3.connect(path, isolation_level=None)
    try:
        conn.execute("PRAGMA journal_mode = MEMORY")  # no journal file with the old pages on disk
        conn.execute("PRAGMA secure_delete = ON")
        conn.execute("DELETE FROM private_note")
        conn.execute("VACUUM")
    finally:
        conn.close()


def _check_db_file(path, bodies):
    """Raise ``HandoverError`` unless the file has 0 Private notes, is whole, and holds no note text."""
    conn = _connect_ro(path)
    try:
        left = conn.execute("SELECT COUNT(*) FROM private_note").fetchone()[0]
        whole = conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()
    if left != 0:
        raise HandoverError(f"{left} Private note(s) were still in the handover database. No handover was made.")
    if whole != "ok":
        raise HandoverError(f"The handover database failed its check ({whole}). No handover was made.")
    check_no_private_text(path.read_bytes(), bodies)


def check_no_private_text(data, bodies):
    """Raise ``HandoverError`` if any Private note text is found in ``data`` (bytes)."""
    for note_id, body in bodies:
        if body in data:
            raise HandoverError(
                f"The text of Private note {note_id} was still found in the handover database "
                "(maybe the same text is also used somewhere else). No handover was made.",
                private_text_found=True,
            )


def private_text_files(files, notes):
    """Which files hold the text of a Private note: ``[(file, key), ...]`` in file order.

    ``notes`` is ``[(key, text as str or UTF-8 bytes), ...]``. A file is read as plain bytes and
    searched for the UTF-8 bytes of the text in NFC and in NFD (an editor may save either).
    shortcut: text inside Word or PDF files (zipped or encoded) is not read; add a reader if needed.
    """
    forms = []
    for key, body in notes:
        body = body.decode("utf-8") if isinstance(body, bytes) else body
        forms.append((key, {unicodedata.normalize(f, body).encode("utf-8") for f in ("NFC", "NFD")}))
    found = []
    for f in files:
        data = Path(f).read_bytes()
        found.extend((f, key) for key, needles in forms if any(n in data for n in needles))
    return found


def _free_name(out_dir, slug, day):
    base = f"handover-{slug}-{day}"
    name = f"{base}.zip"
    n = 2
    while (out_dir / name).exists():
        name = f"{base}-{n}.zip"
        n += 1
    return name


def _write_zip(zip_path, db_file, doc_files):
    with zipfile.ZipFile(zip_path, "x", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(db_file, db.DB_NAME)
        zf.mkdir(db.DOCUMENTS_DIR)
        for f in doc_files:
            zf.write(f, f"{db.DOCUMENTS_DIR}/{f.name}")


def _check_zip(zip_path, bodies, work, doc_files):
    with zipfile.ZipFile(zip_path) as zf:
        bad = zf.testzip()
        if bad is not None:
            raise HandoverError(f"The handover zip is damaged ({bad}). No handover was made.")
        names = set(zf.namelist())
        if db.DB_NAME not in names:
            raise HandoverError("The handover zip has no church.db. No handover was made.")
        if not {f"{db.DOCUMENTS_DIR}/{f.name}" for f in doc_files} <= names:
            raise HandoverError("A Document file is missing from the handover zip. No handover was made.")
        check_path = work / "check.db"
        check_path.write_bytes(zf.read(db.DB_NAME))
    _check_db_file(check_path, bodies)


def make_handover(copy_folder, out_dir, today=None):
    """Make a Handover zip of the church copy in ``copy_folder`` inside ``out_dir``.

    Returns the zip path. ``out_dir`` may not be inside OneDrive or inside the
    copy's ``documents/``. The source church copy is never changed.
    """
    try:
        folder = paths.check_not_onedrive(copy_folder)
        out = paths.check_not_onedrive(out_dir)
    except paths.CopyPathError as exc:
        raise HandoverError(str(exc)) from exc
    db_path = folder / db.DB_NAME
    if not db_path.is_file():
        raise HandoverError(f"No church copy in {folder}: {db.DB_NAME} is missing.")
    docs = db.documents_folder(folder).resolve()
    if out == docs or out.is_relative_to(docs):
        raise HandoverError("Save the handover outside the documents folder of the church copy.")
    day = text.check_date(today if today is not None else text.today_text(), "Date")

    work = None
    partial = None
    try:
        slug, bodies = _read_source(db_path)
        out.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix=".handover-work-", dir=out))
        work_db = work / db.DB_NAME
        bodies = sorted(set(bodies) | set(_backup(db_path, work_db)))
        _strip_private(work_db)
        _check_db_file(work_db, bodies)
        doc_files = documents.documents_on_disk(folder)
        if private_text_files(doc_files, bodies):
            raise HandoverError("The text of a Private note is also written in a Document file, "
                                "so it would go to the next pastor. No handover was made.", private_text_found=True)
        partial = out / (_free_name(out, slug, day) + ".partial")
        _write_zip(partial, work_db, doc_files)
        _check_zip(partial, bodies, work, doc_files)
        final = out / _free_name(out, slug, day)
        os.rename(partial, final)  # on Windows this never replaces a file
        partial = None
        return final
    except HandoverError:
        raise
    except (sqlite3.Error, OSError, zipfile.BadZipFile) as exc:
        raise HandoverError(f"The handover could not be made: {exc}") from exc
    finally:
        if partial is not None:
            Path(partial).unlink(missing_ok=True)
        if work is not None:
            shutil.rmtree(work, ignore_errors=True)
