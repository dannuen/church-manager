"""Documents: files kept inside the church copy, in ``<copy>/documents/``.

The file on disk gets a random name (``uuid4().hex`` + a safe extension), so a
file name given by a person can never point outside ``documents/``. The name a
person sees (``original_name``) is kept only in the database.
"""

import hashlib
import re
import unicodedata
import uuid

from . import db, paths, text
from .db import transaction

MAX_SIZE = 50 * 1024 * 1024  # 50 MB, card rule
MAX_NAME_LENGTH = 150  # the shown name is cut to this length (the extension is kept)
_EXT = re.compile(r"[a-z0-9]{1,8}")
_STORED = re.compile(r"[0-9a-f]{32}(?:\.[a-z0-9]{1,8})?")
_LINKS = ("person_id", "family_id", "calendar_item_id")
_LINK_TABLES = {"person_id": ("person", "Person"), "family_id": ("family", "Family"),
                "calendar_item_id": ("calendar_item", "Calendar item")}


def clean_file_name(original_name):
    """The name to show: NFC, only the last part of any path, no control marks,
    at most 150 characters (the extension is kept). Raises ``ValueError`` if empty."""
    if not isinstance(original_name, str):
        raise ValueError("A Document needs a file name.")
    name = text.nfc(original_name).replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if not unicodedata.category(ch).startswith("C")).strip()
    if name in ("", ".", ".."):
        raise ValueError("A Document needs a file name.")
    if len(name) > MAX_NAME_LENGTH:
        stem, dot, ext = name.rpartition(".")
        if dot and 0 < len(ext) <= 8:
            name = stem[: MAX_NAME_LENGTH - len(ext) - 1] + "." + ext
        else:
            name = name[:MAX_NAME_LENGTH]
    return name


def safe_extension(name):
    """The lower-case extension if it is 1 to 8 of ``a-z0-9``, else ``""``."""
    stem, dot, ext = name.rpartition(".")
    if not dot or not stem.strip("."):
        return ""
    ext = ext.lower()
    return ext if _EXT.fullmatch(ext) else ""


def _documents_dir(copy_folder):
    return db.documents_folder(paths.check_not_onedrive(copy_folder)).resolve()


def _links(person_id, family_id, calendar_item_id):
    given = {k: v for k, v in zip(_LINKS, (person_id, family_id, calendar_item_id)) if v not in (None, "")}
    if len(given) > 1:
        raise ValueError("A Document is linked to one Person, one Family or one Calendar item, not more.")
    return given


def add_document(conn, copy_folder, data, original_name, person_id=None, family_id=None,
                 calendar_item_id=None):
    """Keep a file in the church copy and return the Document id.

    ``data`` is the file content (bytes, at most 50 MB). The link is one Person,
    one Family, one Calendar item, or none (for example the file of a Sent document).
    """
    if isinstance(data, (bytearray, memoryview)):
        data = bytes(data)
    if not isinstance(data, bytes):
        raise ValueError("The file content must be bytes.")
    if len(data) > MAX_SIZE:
        raise ValueError(f"The file is too large. The limit is {MAX_SIZE // (1024 * 1024)} MB.")
    name = clean_file_name(original_name)
    links = _links(person_id, family_id, calendar_item_id)
    folder = _documents_dir(copy_folder)
    folder.mkdir(parents=True, exist_ok=True)
    ext = safe_extension(name)
    stored_name = uuid.uuid4().hex + (f".{ext}" if ext else "")
    target = folder / stored_name
    created = False
    try:
        with transaction(conn):
            values = {}
            for column, value in links.items():
                table, what = _LINK_TABLES[column]
                rid = text.to_id(value, what)
                if conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (rid,)).fetchone() is None:
                    raise ValueError(f"No {what} with id {rid}.")
                values[column] = rid
            cols = ["original_name", "stored_name", "size", "sha256", *values, "added_at"]
            params = [name, stored_name, len(data), hashlib.sha256(data).hexdigest(), *values.values(),
                      text.now_text()]
            cur = conn.execute(
                f"INSERT INTO document ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", params
            )
            with open(target, "xb") as fh:  # "x": never write over a file
                created = True
                fh.write(data)
            doc_id = cur.lastrowid
    except BaseException:
        if created:
            target.unlink(missing_ok=True)
        raise
    return doc_id


def get_document(conn, doc_id):
    """One Document row, or ``None``."""
    return conn.execute("SELECT * FROM document WHERE id = ?", (text.to_id(doc_id, "Document"),)).fetchone()


def document_path(conn, copy_folder, doc_id):
    """The full path of a Document's file. It is always inside ``documents/``;
    anything else raises ``ValueError``. The file itself may be missing."""
    row = get_document(conn, doc_id)
    if row is None:
        raise ValueError(f"No Document with id {doc_id}.")
    stored = row["stored_name"]
    if not isinstance(stored, str) or not _STORED.fullmatch(stored):
        raise ValueError(f"Document {row['id']} has a bad stored name and is not opened.")
    folder = _documents_dir(copy_folder)
    path = (folder / stored).resolve()
    if path.parent != folder or not path.is_relative_to(folder):
        raise ValueError(f"Document {row['id']} points outside the documents folder and is not opened.")
    return path


def list_documents(conn, person_id=None, family_id=None, calendar_item_id=None):
    """Documents of one Person, one Family or one Calendar item (or all of them), oldest first."""
    links = _links(person_id, family_id, calendar_item_id)
    sql = "SELECT * FROM document"
    params = []
    for column, value in links.items():
        sql += f" WHERE {column} = ?"
        params.append(text.to_id(value, _LINK_TABLES[column][1]))
    return conn.execute(sql + " ORDER BY added_at, id", params).fetchall()


def documents_on_disk(copy_folder):
    """Every file in ``documents/`` (not folders, not links), by name."""
    folder = _documents_dir(copy_folder)
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and not p.is_symlink())
