"""Sent documents: date, Recipient, Purpose and a number per year (such as 05/2026).

The number restarts at 01 each year and is never used twice: ``UNIQUE (year, seq)``
and there is no delete. The next number is taken inside ``BEGIN IMMEDIATE``.
"""

from . import lists, text
from .calendar import check_year as _check_year
from .db import transaction


def number_text(seq, year):
    """``number_text(6, 2026) == "06/2026"``."""
    return f"{seq:02d}/{year}"


def _next_seq(conn, year):
    return conn.execute(
        "SELECT COALESCE(MAX(seq), 0) + 1 FROM sent_document WHERE year = ?", (year,)
    ).fetchone()[0]


def next_number(conn, year):
    """The number the next Sent document of ``year`` will get, like ``"06/2026"``.
    This only shows it; it does not keep it."""
    year = _check_year(year)
    return number_text(_next_seq(conn, year), year)


def add_sent_document(conn, date, recipient_id, purpose_id, subject=None, document_id=None):
    """Record a Sent document. The year is the year of ``date``.
    Returns ``(id, number_text)``, for example ``(12, "06/2026")``."""
    day = text.check_date_years(date, "Date")  # a year from 1900 to 9999, like an Offering
    year = int(day[:4])
    with transaction(conn):  # BEGIN IMMEDIATE: no one else can take the same number
        recipient = lists.require_item(conn, recipient_id, "recipient")["id"]
        purpose = lists.require_item(conn, purpose_id, "purpose")["id"]
        doc = None
        if document_id not in (None, ""):
            doc = text.to_id(document_id, "Document")
            if conn.execute("SELECT 1 FROM document WHERE id = ?", (doc,)).fetchone() is None:
                raise ValueError(f"No Document with id {doc}.")
        seq = _next_seq(conn, year)
        cur = conn.execute(
            "INSERT INTO sent_document (year, seq, date, recipient_id, purpose_id, subject, document_id, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (year, seq, day, recipient, purpose, text.clean_text(subject), doc, text.now_text()),
        )
        return cur.lastrowid, number_text(seq, year)


def list_sent_documents(conn, year):
    """Sent documents of one year by number. Extra columns: number, recipient_name,
    purpose_name, document_name."""
    year = _check_year(year)
    return conn.execute(
        "SELECT s.id, s.year, s.seq, printf('%02d/%d', s.seq, s.year) AS number, s.date, "
        "s.recipient_id, r.name AS recipient_name, s.purpose_id, pu.name AS purpose_name, "
        "s.subject, s.document_id, d.original_name AS document_name, s.created_at "
        "FROM sent_document s JOIN list_item r ON r.id = s.recipient_id "
        "JOIN list_item pu ON pu.id = s.purpose_id "
        "LEFT JOIN document d ON d.id = s.document_id "
        "WHERE s.year = ? ORDER BY s.seq",
        (year,),
    ).fetchall()
