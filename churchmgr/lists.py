"""Editable lists: status, ministry, fund, spending_category, recipient, purpose.

Items are never deleted. Hide an item with ``set_active(conn, item_id, False)``;
old rows that use it keep working. Item names are data: shown as stored, never translated.
Errors are ``TextError`` (``str()`` English; a page shows ``i18n.error_text``).
"""

import re
import sqlite3

from . import text
from .i18n import TextError, t
from .schema import LIST_NAMES

_CODE = re.compile(r"[a-z0-9_]+")
# list name -> the glossary word the pastor reads (English; the agent and old callers use it)
LABELS = {"status": "Status", "ministry": "Ministry", "fund": "Fund", "spending_category": "Spending category",
          "recipient": "Recipient", "purpose": "Purpose"}
# list name -> the TEXT key of that word (pages and errors, in the language of the page)
LABEL_KEYS = {name: f"lists.{name}" for name in LABELS}
assert set(LABELS) == set(LIST_NAMES), "every list has a label"
assert all(t(LABEL_KEYS[n], "en") == LABELS[n] for n in LABELS), "the English word of each list is its label"


def _check_list_name(list_name):
    if list_name not in LIST_NAMES:
        raise TextError("lists.err_unknown", name=repr(list_name), names=", ".join(LIST_NAMES))
    return list_name


def get_list(conn, list_name, include_hidden=False):
    """Items of one list in their sort order. Hidden items only if ``include_hidden``."""
    _check_list_name(list_name)
    sql = "SELECT * FROM list_item WHERE list_name = ?"
    if not include_hidden:
        sql += " AND active = 1"
    return conn.execute(sql + " ORDER BY sort_order, id", (list_name,)).fetchall()


def get_item(conn, item_id):
    """One list item by id, or ``None``."""
    return conn.execute(
        "SELECT * FROM list_item WHERE id = ?", (text.to_id(item_id, "lists.list_item"),)
    ).fetchone()


def find_item(conn, list_name, *, code=None, name=None):
    """Find an item of ``list_name`` by its code or its exact (NFC) name, or ``None``."""
    _check_list_name(list_name)
    if code is not None:
        return conn.execute(
            "SELECT * FROM list_item WHERE list_name = ? AND code = ?", (list_name, code)
        ).fetchone()
    if name is not None:
        return conn.execute(
            "SELECT * FROM list_item WHERE list_name = ? AND name = ?",
            (list_name, text.clean_name(name, "lists.name")),
        ).fetchone()
    raise TextError("lists.err_find")


def require_item(conn, item_id, list_name):
    """Return the item, or raise ``TextError`` ("Fund: choose one from the list.") if it is not
    in ``list_name`` (no such id, another list, or not a whole number)."""
    _check_list_name(list_name)
    try:
        item = get_item(conn, item_id)
    except ValueError:  # not a whole number above 0
        item = None
    if item is None or item["list_name"] != list_name:
        raise TextError("lists.err_choose", label=LABEL_KEYS[list_name])
    return item


def _name_taken(conn, list_name, name, except_id=None):
    """True when another item of the list (hidden ones too) has this name, upper or lower case aside.
    Python ``casefold`` of the NFC name: SQL ``lower`` folds only A-Z, not Vietnamese."""
    key = text.nfc(name).casefold()
    return any(text.nfc(r["name"]).casefold() == key and r["id"] != except_id
               for r in conn.execute("SELECT id, name FROM list_item WHERE list_name = ?", (list_name,)))


def add_item(conn, list_name, name, code=None):
    """Add an item at the end of the list and return its id."""
    _check_list_name(list_name)
    name = text.clean_name(name, "lists.name")
    if code is not None and not _CODE.fullmatch(code):
        raise TextError("lists.err_code")
    if _name_taken(conn, list_name, name):
        raise TextError("lists.err_taken", name=name, list=LABEL_KEYS[list_name])
    last = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) FROM list_item WHERE list_name = ?", (list_name,)
    ).fetchone()[0]
    try:
        cur = conn.execute(
            "INSERT INTO list_item (list_name, code, name, sort_order, active) VALUES (?, ?, ?, ?, 1)",
            (list_name, code, name, last + 1),
        )
    except sqlite3.IntegrityError as exc:
        raise TextError("lists.err_cannot_add", name=name, list=LABEL_KEYS[list_name], detail=str(exc)) from exc
    return cur.lastrowid


def rename_item(conn, item_id, new_name):
    """Give an item a new name. Rows that use it follow the new name."""
    item = get_item(conn, item_id)
    if item is None:
        raise TextError("lists.err_no_item", id=item_id)
    name = text.clean_name(new_name, "lists.name")
    if _name_taken(conn, item["list_name"], name, except_id=item["id"]):
        raise TextError("lists.err_taken", name=name, list=LABEL_KEYS[item["list_name"]])
    conn.execute("UPDATE list_item SET name = ? WHERE id = ?", (name, item["id"]))


def set_active(conn, item_id, active):
    """Show (``True``) or hide (``False``) an item. Nothing is deleted."""
    item = get_item(conn, item_id)
    if item is None:
        raise TextError("lists.err_no_item", id=item_id)
    if active not in (True, False, 0, 1):
        raise TextError("lists.err_active")
    conn.execute("UPDATE list_item SET active = ? WHERE id = ?", (1 if active else 0, item["id"]))
