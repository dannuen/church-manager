"""Calendar: Calendar items (Service, Meeting, Visit, Event), repeats, people, Head counts.

A repeat is stored as separate rows that share ``series_id`` (the id of the
first row). Each row can then be changed or deleted on its own.
Date-times are TEXT ``YYYY-MM-DD HH:MM`` (local time).

Visits are made with :func:`churchmgr.care.plan_visit`, not here.
"""

import datetime as _dt

from . import text
from .db import transaction
from .schema import CALENDAR_KINDS, CALENDAR_PARTS

REPEATS = ("none", "weekly", "monthly")
MAX_REPEAT_ROWS = 104  # card rule: at most 2 years of weekly items in one repeat
MAX_HEAD_COUNT = 1_000_000  # sanity limit: no Service is bigger
_KEEP = object()  # "do not change this field" in update functions
_FMT = "%Y-%m-%d %H:%M"


# ---------------------------------------------------------------- dates

def month_days(year, month):
    """Number of days in a month (28 to 31)."""
    if month == 12:
        return 31
    return (_dt.date(year, month + 1, 1) - _dt.timedelta(days=1)).day


def add_months(day, months):
    """``day`` plus ``months`` (may be negative). The day is clamped to the month end:
    2026-01-31 + 1 month = 2026-02-28; 2026-05-31 - 3 months = 2026-02-28."""
    total = day.year * 12 + (day.month - 1) + months
    year, month0 = divmod(total, 12)
    month = month0 + 1
    return day.replace(year=year, month=month, day=min(day.day, month_days(year, month)))


def check_year(year):
    """Return the year as an int (from an int or digit text, 1900 to 9999), or raise ``ValueError``."""
    if isinstance(year, str) and year.strip().isascii() and year.strip().isdigit():
        year = int(year.strip())
    if type(year) is not int or not 1900 <= year <= 9999:
        raise ValueError("Year must be a whole number like 2026.")
    return year


def _to_date(value, what):
    return _dt.date.fromisoformat(text.check_date(value, what))


def _to_datetime(value, what):
    return _dt.datetime.strptime(text.check_datetime(value, what), _FMT)


def _next_day(day_text):
    return (_dt.date.fromisoformat(day_text) + _dt.timedelta(days=1)).isoformat()


# ---------------------------------------------------------------- helpers

def _require_item(conn, item_id):
    iid = text.to_id(item_id, "Calendar item")
    row = conn.execute("SELECT * FROM calendar_item WHERE id = ?", (iid,)).fetchone()
    if row is None:
        raise ValueError(f"No Calendar item with id {iid}.")
    return row


def _require_person(conn, person_id):
    pid = text.to_id(person_id, "Person")
    if conn.execute("SELECT 1 FROM person WHERE id = ?", (pid,)).fetchone() is None:
        raise ValueError(f"No Person with id {pid}.")
    return pid


def _check_kind(kind):
    if kind not in CALENDAR_KINDS:
        raise ValueError(f"Kind must be one of: {', '.join(CALENDAR_KINDS)}.")
    return kind


def _check_part(part):
    if part not in CALENDAR_PARTS:
        raise ValueError(f"Part must be one of: {', '.join(CALENDAR_PARTS)}.")
    return part


def _start_dates(start, repeat, repeat_until):
    """All start date-times of a new item and its repeats."""
    if repeat is None or repeat == "":
        repeat = "none"
    if repeat not in REPEATS:
        raise ValueError(f"Repeat must be one of: {', '.join(REPEATS)}.")
    if repeat == "none":
        if repeat_until not in (None, ""):
            raise ValueError("A repeat end date needs a repeat (weekly or monthly).")
        return [start]
    if repeat_until in (None, ""):
        raise ValueError("A repeat needs an end date (repeat until).")
    until = _to_date(repeat_until, "Repeat until")
    if until < start.date():
        raise ValueError("The repeat end date is before the first date.")
    out = []
    k = 0
    while True:
        if repeat == "weekly":
            nxt = start + _dt.timedelta(weeks=k)
        else:
            nxt = _dt.datetime.combine(add_months(start.date(), k), start.time())
        if nxt.date() > until:
            break
        out.append(nxt)
        if len(out) > MAX_REPEAT_ROWS:
            raise ValueError(
                f"A repeat can make at most {MAX_REPEAT_ROWS} Calendar items. Choose an earlier end date."
            )
        k += 1
    return out


def _add_items(conn, kind, title, starts_at, ends_at=None, place=None, note=None,
               repeat="none", repeat_until=None, visit_person_id=None, visit_family_id=None):
    """Insert one Calendar item, or a repeat series. Returns the list of ids.

    Shared by :func:`add_calendar_item` and :func:`churchmgr.care.plan_visit`.
    """
    _check_kind(kind)
    clean_title = text.clean_name(title, "Title")
    start = _to_datetime(starts_at, "Start")
    length = None
    if ends_at not in (None, ""):
        end = _to_datetime(ends_at, "End")
        if end < start:
            raise ValueError("The end is before the start.")
        length = end - start
    starts = _start_dates(start, repeat, repeat_until)
    clean_place = text.clean_text(place)
    clean_note = text.clean_text(note)
    ids = []
    with transaction(conn):
        for when in starts:
            end_text = None if length is None else (when + length).strftime(_FMT)
            cur = conn.execute(
                "INSERT INTO calendar_item (kind, title, starts_at, ends_at, place, note, series_id, "
                "visit_person_id, visit_family_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (kind, clean_title, when.strftime(_FMT), end_text, clean_place, clean_note,
                 ids[0] if ids else None, visit_person_id, visit_family_id),
            )
            ids.append(cur.lastrowid)
        if len(ids) > 1:
            conn.execute("UPDATE calendar_item SET series_id = ? WHERE id = ?", (ids[0], ids[0]))
    return ids


# ---------------------------------------------------------------- Calendar item

def add_calendar_item(conn, kind, title, starts_at, ends_at=None, place=None, note=None,
                      repeat="none", repeat_until=None):
    """Add a Calendar item and return the list of new ids (one id when it does not repeat).

    ``repeat``: ``'none'``, ``'weekly'`` or ``'monthly'``. A repeat needs
    ``repeat_until`` (a date, included). Monthly keeps the first day of the month
    when it can and clamps to the month end (31 Jan -> 28 Feb -> 31 Mar).
    At most 104 rows. A Visit needs a Person or Family: use ``care.plan_visit``.
    """
    if kind == "Visit":
        raise ValueError("A Visit needs a Person or a Family: plan it with care.plan_visit.")
    return _add_items(conn, kind, title, starts_at, ends_at, place, note, repeat, repeat_until)


def get_calendar_item(conn, item_id):
    """One Calendar item row, or ``None``."""
    return conn.execute(
        "SELECT * FROM calendar_item WHERE id = ?", (text.to_id(item_id, "Calendar item"),)
    ).fetchone()


def series_items(conn, series_id):
    """All rows of one repeat series, by start."""
    return conn.execute(
        "SELECT * FROM calendar_item WHERE series_id = ? ORDER BY starts_at, id",
        (text.to_id(series_id, "Series"),),
    ).fetchall()


def update_calendar_item(conn, item_id, *, kind=_KEEP, title=_KEEP, starts_at=_KEEP,
                         ends_at=_KEEP, place=_KEEP, note=_KEEP):
    """Change one Calendar item (only this row, not the rest of its series).

    ``None`` clears ``ends_at``, ``place`` or ``note``. The kind cannot become or
    stop being a Visit, and a Service with a Head count stays a Service.
    """
    with transaction(conn):
        row = _require_item(conn, item_id)
        changes = {}
        if kind is not _KEEP and kind != row["kind"]:
            _check_kind(kind)
            if kind == "Visit" or row["kind"] == "Visit":
                raise ValueError("A Visit cannot change kind. Plan a new Visit or a new Calendar item instead.")
            if row["kind"] == "Service" and _has_head_count(conn, row["id"]):
                raise ValueError("This Service has a Head count, so it stays a Service.")
            changes["kind"] = kind
        if title is not _KEEP:
            changes["title"] = text.clean_name(title, "Title")
        if starts_at is not _KEEP:
            changes["starts_at"] = text.check_datetime(starts_at, "Start")
        if ends_at is not _KEEP:
            changes["ends_at"] = None if ends_at in (None, "") else text.check_datetime(ends_at, "End")
        if place is not _KEEP:
            changes["place"] = text.clean_text(place)
        if note is not _KEEP:
            changes["note"] = text.clean_text(note)
        start = changes.get("starts_at", row["starts_at"])
        end = changes.get("ends_at", row["ends_at"])
        if end is not None and end < start:
            raise ValueError("The end is before the start.")
        if changes:
            sets = ", ".join(f"{col} = ?" for col in changes)
            conn.execute(f"UPDATE calendar_item SET {sets} WHERE id = ?", [*changes.values(), row["id"]])


def _has_head_count(conn, item_id):
    return conn.execute("SELECT 1 FROM head_count WHERE calendar_item_id = ?", (item_id,)).fetchone() is not None


def delete_calendar_item(conn, item_id):
    """Delete one Calendar item (and its list of people).

    Refused when it has a Head count, a Document, or is a done Visit: that is history.
    """
    with transaction(conn):
        row = _require_item(conn, item_id)
        if _has_head_count(conn, row["id"]):
            raise ValueError("This Service has a Head count, so it is kept.")
        if conn.execute("SELECT 1 FROM document WHERE calendar_item_id = ?", (row["id"],)).fetchone():
            raise ValueError("This Calendar item has a Document, so it is kept.")
        if row["kind"] == "Visit" and row["visit_done"]:
            raise ValueError("This Visit is done and is part of the Care log, so it is kept.")
        conn.execute("DELETE FROM calendar_item WHERE id = ?", (row["id"],))


def items_between(conn, start_date, end_date):
    """Calendar items that start on a day from ``start_date`` to ``end_date`` (both included),
    in time order. Extra columns: ``head_count``, ``absent_note``, ``visit_name``."""
    start = text.check_date(start_date, "Start date")
    end = text.check_date(end_date, "End date")
    if end < start:
        raise ValueError("The end date is before the start date.")
    return conn.execute(
        "SELECT ci.*, hc.count AS head_count, hc.absent_note, "
        "COALESCE(vp.full_name, vf.name) AS visit_name "
        "FROM calendar_item ci "
        "LEFT JOIN head_count hc ON hc.calendar_item_id = ci.id "
        "LEFT JOIN person vp ON vp.id = ci.visit_person_id "
        "LEFT JOIN family vf ON vf.id = ci.visit_family_id "
        "WHERE ci.starts_at >= ? AND ci.starts_at < ? "
        "ORDER BY ci.starts_at, ci.id",
        (start + " 00:00", _next_day(end) + " 00:00"),
    ).fetchall()


# ---------------------------------------------------------------- people of an item

def add_person_to_item(conn, item_id, person_id, part):
    """List a Person on a Calendar item as ``'joins'`` or ``'serves'``.
    Returns ``True`` if added, ``False`` if they were already listed that way."""
    iid = _require_item(conn, item_id)["id"]
    pid = _require_person(conn, person_id)
    cur = conn.execute(
        "INSERT OR IGNORE INTO calendar_person (calendar_item_id, person_id, part) VALUES (?, ?, ?)",
        (iid, pid, _check_part(part)),
    )
    return cur.rowcount == 1


def remove_person_from_item(conn, item_id, person_id, part=None):
    """Take a Person off a Calendar item (one part, or both when ``part`` is ``None``).
    Returns the number of rows removed."""
    iid = _require_item(conn, item_id)["id"]
    pid = text.to_id(person_id, "Person")
    if part is None:
        cur = conn.execute(
            "DELETE FROM calendar_person WHERE calendar_item_id = ? AND person_id = ?", (iid, pid)
        )
    else:
        cur = conn.execute(
            "DELETE FROM calendar_person WHERE calendar_item_id = ? AND person_id = ? AND part = ?",
            (iid, pid, _check_part(part)),
        )
    return cur.rowcount


def item_people(conn, item_id):
    """People of a Calendar item: those who serve first, then those who join, by name."""
    return conn.execute(
        "SELECT cp.person_id, p.full_name, cp.part FROM calendar_person cp "
        "JOIN person p ON p.id = cp.person_id WHERE cp.calendar_item_id = ? "
        "ORDER BY CASE cp.part WHEN 'serves' THEN 0 ELSE 1 END, p.name_folded, p.id",
        (text.to_id(item_id, "Calendar item"),),
    ).fetchall()


# ---------------------------------------------------------------- Head count

def set_head_count(conn, item_id, count, absent_note=None):
    """Record the Head count of a Service (a whole number from 0). A new count
    replaces the old one for that Service."""
    if isinstance(count, bool) or not isinstance(count, int):
        raise ValueError("A Head count must be a whole number.")
    if not 0 <= count <= MAX_HEAD_COUNT:
        raise ValueError("A Head count must be 0 or more.")
    with transaction(conn):
        row = _require_item(conn, item_id)
        if row["kind"] != "Service":
            raise ValueError("A Head count is only for a Service.")
        conn.execute(
            "INSERT INTO head_count (calendar_item_id, count, absent_note) VALUES (?, ?, ?) "
            "ON CONFLICT (calendar_item_id) DO UPDATE SET count = excluded.count, "
            "absent_note = excluded.absent_note",
            (row["id"], count, text.clean_text(absent_note)),
        )


def get_head_count(conn, item_id):
    """The Head count row of a Service (count, absent_note), or ``None``."""
    return conn.execute(
        "SELECT calendar_item_id, count, absent_note FROM head_count WHERE calendar_item_id = ?",
        (text.to_id(item_id, "Calendar item"),),
    ).fetchone()


def recent_head_counts(conn, n=8, now=None):
    """The last ``n`` past Services that have a Head count, newest last.

    Rows: id, title, starts_at, count, absent_note. ``now`` (``YYYY-MM-DD HH:MM``)
    defaults to the local time now.
    """
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("n must be a whole number above 0.")
    limit = text.now_text() if now is None else text.check_datetime(now, "Now")
    rows = conn.execute(
        "SELECT ci.id, ci.title, ci.starts_at, hc.count, hc.absent_note "
        "FROM calendar_item ci JOIN head_count hc ON hc.calendar_item_id = ci.id "
        "WHERE ci.kind = 'Service' AND ci.starts_at <= ? "
        "ORDER BY ci.starts_at DESC, ci.id DESC LIMIT ?",
        (limit, n),
    ).fetchall()
    return rows[::-1]
