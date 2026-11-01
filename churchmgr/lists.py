"""Editable lists: status, ministry, fund, spending_category, recipient, purpose.

Items are never deleted. Hide an item with ``set_active(conn, item_id, False)``;
old rows that use it keep working.
"""

import re
import sqlite3

from . import text
from .schema import LIST_NAMES

_CODE = re.compile(r"[a-z0-9_]+")
# list name -> the glossary word the pastor reads
LABELS = {"status": "Status", "ministry": "Ministry", "fund": "Fund", "spending_category": "Spending category",
          "recipient": "Recipient", "purpose": "Purpose"}
assert set(LABELS) == set(LIST_NAMES), "every list has a label"


def _check_list_name(list_name):
    if list_name not in LIST_NAMES:
        raise ValueError(f"Unknown list {list_name!r}. Lists are: {', '.join(LIST_NAMES)}.")
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
        "SELECT * FROM list_item WHERE id = ?", (text.to_id(item_id, "List item"),)
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
            (list_name, text.clean_name(name)),
        ).fetchone()
    raise ValueError("Give a code or a name to find a list item.")


def require_item(conn, item_id, list_name):
    """Return the item, or raise ``ValueError`` ("Fund: choose one from the list.") if it is not
    in ``list_name`` (no such id, another list, or not a whole number)."""
    _check_list_name(list_name)
    try:
        item = get_item(conn, item_id)
    except ValueError:  # not a whole number above 0
        item = None
    if item is None or item["list_name"] != list_name:
        raise ValueError(f"{LABELS[list_name]}: choose one from the list.")
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
    name = text.clean_name(name, "Name")
    if code is not None and not _CODE.fullmatch(code):
        raise ValueError("A code uses only a-z, 0-9 and _.")
    if _name_taken(conn, list_name, name):
        raise ValueError(f"{name} is already in the {LABELS[list_name]} list.")
    last = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) FROM list_item WHERE list_name = ?", (list_name,)
    ).fetchone()[0]
    try:
        cur = conn.execute(
            "INSERT INTO list_item (list_name, code, name, sort_order, active) VALUES (?, ?, ?, ?, 1)",
            (list_name, code, name, last + 1),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"{name} cannot be added to the {LABELS[list_name]} list: {exc}.") from exc
    return cur.lastrowid


def rename_item(conn, item_id, new_name):
    """Give an item a new name. Rows that use it follow the new name."""
    item = get_item(conn, item_id)
    if item is None:
        raise ValueError(f"No list item with id {item_id}.")
    name = text.clean_name(new_name, "Name")
    if _name_taken(conn, item["list_name"], name, except_id=item["id"]):
        raise ValueError(f"{name} is already in the {LABELS[item['list_name']]} list.")
    conn.execute("UPDATE list_item SET name = ? WHERE id = ?", (name, item["id"]))


def set_active(conn, item_id, active):
    """Show (``True``) or hide (``False``) an item. Nothing is deleted."""
    item = get_item(conn, item_id)
    if item is None:
        raise ValueError(f"No list item with id {item_id}.")
    if active not in (True, False, 0, 1):
        raise ValueError("active must be True or False.")
    conn.execute("UPDATE list_item SET active = ? WHERE id = ?", (1 if active else 0, item["id"]))
