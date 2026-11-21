"""Open, create and use one church copy (``church.db`` + ``documents/``)."""

import sqlite3
from contextlib import contextmanager
from itertools import count
from pathlib import Path

from . import i18n, paths, schema, settings, text

DB_NAME = "church.db"
DOCUMENTS_DIR = "documents"

_savepoints = count(1)


class ChurchCopyError(Exception):
    """The folder is not a usable church copy (missing, already there, wrong version).

    ``ChurchCopyError("errors.copy_<name>", **params)``: ``str()`` is the English text (the agent,
    ``app.py`` and the logs read it); a page shows ``i18n.error_text(e)``. Paths and SQLite text are
    params, shown as they are. A plain sentence instead of a key is kept as it is in every language.
    The base stays ``Exception`` (a ``TextError`` is a ``ValueError``), so every ``except`` works as before.
    """

    def __init__(self, key, **params):
        if not (isinstance(key, str) and key in i18n.TEXT["en"]):
            key, params = "errors.copy_plain", {"message": key}
        self.key, self.params = key, params
        super().__init__(i18n.error_text(self, "en"))


def connect(db_path):
    """Open a SQLite connection with the Church Manager settings.

    ``foreign_keys=ON``, ``recursive_triggers=ON`` (so ``INSERT OR REPLACE``
    cannot silently delete history), ``journal_mode=DELETE`` (one file),
    ``row_factory=sqlite3.Row`` and autocommit (use :func:`transaction`).
    A path inside OneDrive is refused.
    """
    memory = str(db_path) == ":memory:"
    if not memory:
        paths.check_not_onedrive(db_path)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA recursive_triggers = ON")
        mode = conn.execute("PRAGMA journal_mode = DELETE").fetchone()[0]
        if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise ChurchCopyError("errors.copy_foreign_keys")
        if not memory and mode.lower() != "delete":
            raise ChurchCopyError("errors.copy_journal_mode", mode=mode)
    except BaseException:
        conn.close()
        raise
    return conn


@contextmanager
def transaction(conn):
    """All writes inside the ``with`` block are saved together or not at all.

    The outer block uses ``BEGIN IMMEDIATE``; a nested block uses a SAVEPOINT.
    """
    if conn.in_transaction:
        name = f"sp_{next(_savepoints)}"
        conn.execute(f"SAVEPOINT {name}")
        try:
            yield conn
        except BaseException:
            conn.execute(f"ROLLBACK TO {name}")
            conn.execute(f"RELEASE {name}")
            raise
        conn.execute(f"RELEASE {name}")
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def create_church_copy(folder, church_name, lang="en"):
    """Make a new church copy in ``folder`` and return an open connection.

    Refuses a OneDrive folder and a folder that already has ``church.db``.
    Creates the folder, ``documents/``, the whole schema, the default lists and the default Service roles
    with the names of ``lang`` (``vi`` or ``en``) and the settings ``church_name``,
    ``care_reminder_months`` (3) and ``language`` (``lang``). The app always passes
    a language; the default ``en`` keeps the old tests in English.
    The caller must close the connection.
    """
    settings.check_language(lang)
    folder = paths.check_not_onedrive(folder)
    name = text.clean_name(church_name, "settings.church_name")
    db_path = folder / DB_NAME
    if db_path.exists():
        raise ChurchCopyError("errors.copy_exists", folder=folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / DOCUMENTS_DIR).mkdir(exist_ok=True)
    conn = connect(db_path)
    try:
        with transaction(conn):
            schema.create_schema(conn)
            schema.insert_default_lists(conn, lang)
            schema.insert_default_service_roles(conn, lang)
            values = {"church_name": name, **schema.DEFAULT_SETTINGS, settings.LANGUAGE: lang}
            conn.executemany(
                "INSERT INTO setting (key, value) VALUES (?, ?)", list(values.items())
            )
    except BaseException:
        conn.close()
        db_path.unlink(missing_ok=True)
        raise
    return conn


def open_church_copy(folder):
    """Open the church copy in ``folder`` and return a connection.

    Checks that ``church.db`` exists and has a ``user_version`` in ``schema.KNOWN_VERSIONS``. A version-1
    copy is brought to version 2 in one transaction (:func:`_to_version_2`). A copy made by an older app
    gets the triggers of this app (``schema.stale_triggers``); an up-to-date copy is not written.
    Makes ``documents/`` if it is missing. The caller must close the connection.
    """
    folder = paths.check_not_onedrive(folder)
    db_path = folder / DB_NAME
    if not db_path.is_file():
        raise ChurchCopyError("errors.copy_missing", folder=folder, db=DB_NAME)
    try:
        conn = connect(db_path)
    except sqlite3.DatabaseError as exc:
        raise ChurchCopyError("errors.copy_not_database", path=db_path, detail=str(exc)) from exc
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.DatabaseError as exc:
        conn.close()
        raise ChurchCopyError("errors.copy_not_database", path=db_path, detail=str(exc)) from exc
    if version not in schema.KNOWN_VERSIONS:
        conn.close()
        raise ChurchCopyError("errors.copy_version", path=db_path, version=version, needed=schema.SCHEMA_VERSION)
    try:
        if version == 1:
            _to_version_2(conn)
        stale = schema.stale_triggers(conn)
        if stale:
            with transaction(conn):
                schema.renew_triggers(conn, stale)
    except BaseException:
        conn.close()
        raise
    (folder / DOCUMENTS_DIR).mkdir(exist_ok=True)
    return conn


def _to_version_2(conn):
    """Bring a version-1 church copy to version 2 in ONE transaction: the new tables, indexes and triggers
    (``schema.STATEMENTS_V2``), the default Service roles in the copy's language, then ``user_version`` 2.
    Old tables and rows are not touched."""
    with transaction(conn):
        for statement in schema.STATEMENTS_V2:
            conn.execute(statement)
        schema.insert_default_service_roles(conn, settings.get_language(conn))
        conn.execute("PRAGMA user_version = 2")


def documents_folder(folder):
    """The ``documents/`` folder of the church copy in ``folder``."""
    return Path(folder) / DOCUMENTS_DIR
