"""Open, create and use one church copy (``church.db`` + ``documents/``)."""

import sqlite3
from contextlib import contextmanager
from itertools import count
from pathlib import Path

from . import paths, schema, text

DB_NAME = "church.db"
DOCUMENTS_DIR = "documents"

_savepoints = count(1)


class ChurchCopyError(Exception):
    """The folder is not a usable church copy (missing, already there, wrong version)."""


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
            raise ChurchCopyError("SQLite foreign keys could not be turned on.")
        if not memory and mode.lower() != "delete":
            raise ChurchCopyError(f"SQLite journal mode is {mode}, expected delete.")
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


def create_church_copy(folder, church_name):
    """Make a new church copy in ``folder`` and return an open connection.

    Refuses a OneDrive folder and a folder that already has ``church.db``.
    Creates the folder, ``documents/``, the whole schema, the default lists and
    the settings ``church_name`` and ``care_reminder_months`` (3).
    The caller must close the connection.
    """
    folder = paths.check_not_onedrive(folder)
    name = text.clean_name(church_name, "Church name")
    db_path = folder / DB_NAME
    if db_path.exists():
        raise ChurchCopyError(f"A church copy already exists in {folder}. It was not changed.")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / DOCUMENTS_DIR).mkdir(exist_ok=True)
    conn = connect(db_path)
    try:
        with transaction(conn):
            schema.create_schema(conn)
            schema.insert_default_lists(conn)
            settings = {"church_name": name, **schema.DEFAULT_SETTINGS}
            conn.executemany(
                "INSERT INTO setting (key, value) VALUES (?, ?)", list(settings.items())
            )
    except BaseException:
        conn.close()
        db_path.unlink(missing_ok=True)
        raise
    return conn


def open_church_copy(folder):
    """Open the church copy in ``folder`` and return a connection.

    Checks that ``church.db`` exists and has the right ``user_version``.
    Makes ``documents/`` if it is missing. The caller must close the connection.
    """
    folder = paths.check_not_onedrive(folder)
    db_path = folder / DB_NAME
    if not db_path.is_file():
        raise ChurchCopyError(f"No church copy in {folder}: {DB_NAME} is missing.")
    try:
        conn = connect(db_path)
    except sqlite3.DatabaseError as exc:
        raise ChurchCopyError(f"{db_path} is not a Church Manager database ({exc}).") from exc
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.DatabaseError as exc:
        conn.close()
        raise ChurchCopyError(f"{db_path} is not a Church Manager database ({exc}).") from exc
    if version != schema.SCHEMA_VERSION:
        conn.close()
        raise ChurchCopyError(
            f"{db_path} has database version {version}; this app needs version {schema.SCHEMA_VERSION}."
        )
    (folder / DOCUMENTS_DIR).mkdir(exist_ok=True)
    return conn


def documents_folder(folder):
    """The ``documents/`` folder of the church copy in ``folder``."""
    return Path(folder) / DOCUMENTS_DIR
