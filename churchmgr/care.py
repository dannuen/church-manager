"""Care: plan a Visit, mark it done, the Care log, and Needs a visit.

A Visit is a Calendar item of kind Visit for one Person or one Family.
Done Visits make up the Care log.
"""

import datetime as _dt

from . import settings, text
from .calendar import _add_items, add_months
from .db import transaction

DEFAULT_REMINDER_MONTHS = 3
NOT_CARED_STATUS_CODES = ("left", "passed_away")

# A done Visit ``ci`` is in the Care log of Person ``:pid`` when it was for the
# Person, for their current Family, or for a Family they were in on the done date.
_FOR_PERSON = (
    "(ci.visit_person_id = :pid"
    " OR ci.visit_family_id IN (SELECT family_id FROM family_link WHERE person_id = :pid AND end_date IS NULL)"
    " OR EXISTS (SELECT 1 FROM family_link fl WHERE fl.person_id = :pid AND fl.family_id = ci.visit_family_id"
    " AND fl.start_date <= {day} AND (fl.end_date IS NULL OR fl.end_date > {day})))"
)


def plan_visit(conn, starts_at, person_id=None, family_id=None, title=None, note=None):
    """Plan a Visit for exactly one Person or one Family. Returns the Calendar item id.
    The title defaults to "Visit <name>"."""
    has_person = person_id not in (None, "")
    has_family = family_id not in (None, "")
    if has_person == has_family:
        raise ValueError("A Visit is for one Person or one Family: give exactly one of them.")
    with transaction(conn):
        if has_person:
            pid = text.to_id(person_id, "Person")
            row = conn.execute("SELECT full_name AS name FROM person WHERE id = ?", (pid,)).fetchone()
            if row is None:
                raise ValueError(f"No Person with id {pid}.")
            fid = None
        else:
            fid = text.to_id(family_id, "Family")
            row = conn.execute("SELECT name FROM family WHERE id = ?", (fid,)).fetchone()
            if row is None:
                raise ValueError(f"No Family with id {fid}.")
            pid = None
        if title is None or (isinstance(title, str) and not title.strip()):
            title = f"Visit {row['name']}"
        return _add_items(conn, "Visit", title, starts_at, note=note,
                          visit_person_id=pid, visit_family_id=fid)[0]


def mark_visit_done(conn, item_id, done_date, care_note=None):
    """Mark a Visit done on ``done_date`` with an optional short Care note.
    Marking it again changes the date and the note."""
    day = text.check_date(done_date, "Done date")
    with transaction(conn):
        iid = text.to_id(item_id, "Calendar item")
        row = conn.execute("SELECT kind FROM calendar_item WHERE id = ?", (iid,)).fetchone()
        if row is None:
            raise ValueError(f"No Calendar item with id {iid}.")
        if row["kind"] != "Visit":
            raise ValueError("Only a Visit can be marked done.")
        conn.execute(
            "UPDATE calendar_item SET visit_done = 1, visit_done_date = ?, care_note = ? WHERE id = ?",
            (day, text.clean_text(care_note), iid),
        )


def care_log(conn, person_id=None):
    """Done Visits, newest first: who, when (``done_date``) and the short note.

    With ``person_id``: Visits for that Person, for their current Family, or for a
    Family they were in on the done date.
    """
    sql = (
        "SELECT ci.id, ci.title, ci.visit_done_date AS done_date, ci.care_note, "
        "ci.visit_person_id, ci.visit_family_id, COALESCE(p.full_name, f.name) AS who "
        "FROM calendar_item ci "
        "LEFT JOIN person p ON p.id = ci.visit_person_id "
        "LEFT JOIN family f ON f.id = ci.visit_family_id "
        "WHERE ci.kind = 'Visit' AND ci.visit_done = 1"
    )
    params = {}
    if person_id is not None:
        sql += " AND " + _FOR_PERSON.format(day="ci.visit_done_date")
        params["pid"] = text.to_id(person_id, "Person")
    return conn.execute(sql + " ORDER BY ci.visit_done_date DESC, ci.id DESC", params).fetchall()


def reminder_months(conn):
    """The care reminder time in months (setting ``care_reminder_months``, default 3)."""
    months = settings.get_int_setting(conn, "care_reminder_months", DEFAULT_REMINDER_MONTHS)
    return months if months >= 1 else DEFAULT_REMINDER_MONTHS


def needs_visit(conn, today=None):
    """Persons who need a visit, oldest last Visit first (never visited comes first).

    A Person is included when their current Status is not Left or Passed away
    (no Status counts as included) and their last done Visit is older than the
    care reminder time, or they never had one. A done Visit counts for a Person
    when it was for them or for their current Family.
    Each item: person_id, full_name, status_name, family_name, last_visit (date text or ``None``).
    """
    day = _dt.date.today() if today is None else _dt.date.fromisoformat(text.check_date(today, "Today"))
    cutoff = add_months(day, -reminder_months(conn)).isoformat()
    codes = ", ".join("?" * len(NOT_CARED_STATUS_CODES))
    rows = conn.execute(
        "SELECT p.id AS person_id, p.full_name, p.name_folded, li.name AS status_name, "
        "f.name AS family_name, "
        "(SELECT MAX(ci.visit_done_date) FROM calendar_item ci "
        " WHERE ci.kind = 'Visit' AND ci.visit_done = 1 AND (ci.visit_person_id = p.id "
        " OR (fl.family_id IS NOT NULL AND ci.visit_family_id = fl.family_id))) AS last_visit "
        "FROM person p "
        "LEFT JOIN person_status ps ON ps.person_id = p.id AND ps.end_date IS NULL "
        "LEFT JOIN list_item li ON li.id = ps.status_id "
        "LEFT JOIN family_link fl ON fl.person_id = p.id AND fl.end_date IS NULL "
        "LEFT JOIN family f ON f.id = fl.family_id "
        f"WHERE li.code IS NULL OR li.code NOT IN ({codes})",
        NOT_CARED_STATUS_CODES,
    ).fetchall()
    out = [
        {
            "person_id": r["person_id"],
            "full_name": r["full_name"],
            "status_name": r["status_name"],
            "family_name": r["family_name"],
            "last_visit": r["last_visit"],
            "_folded": r["name_folded"],
        }
        for r in rows
        if r["last_visit"] is None or r["last_visit"] < cutoff
    ]
    out.sort(key=lambda r: (r["last_visit"] is not None, r["last_visit"] or "", r["_folded"], r["person_id"]))
    for r in out:
        del r["_folded"]
    return out
