"""Money: Offerings, Expenses, month totals and the Giving statement.

Every amount is a whole number of dong (INTEGER). There are no decimals
anywhere in money code. Totals use SQL ``SUM`` on INTEGER columns.
"""

import datetime as _dt
import re

from . import lists, settings, text
from .calendar import check_year as _check_year
from .db import transaction

MAX_AMOUNT = 999_999_999_999_999  # dong; far below the SQLite INTEGER limit
_SPACES = re.compile(r"\s+")
_CURRENCY = re.compile(r"^(?:vnđ|vnd|₫|đ)|(?:vnđ|vnd|₫|đ)$", re.IGNORECASE)  # only at the start or end
_PLAIN = re.compile(r"[0-9]+")
# Thousands split by "." or ",". The first block has no leading zero, so "000.001" is refused.
_THOUSANDS = re.compile(r"[1-9][0-9]{0,2}(?:\.[0-9]{3})+|[1-9][0-9]{0,2}(?:,[0-9]{3})+")
_AMOUNT_HELP = "Write a whole number of dong above 0, for example 1250000 or 1.250.000."


# ---------------------------------------------------------------- amounts

def parse_amount(value):
    """Read an amount typed by a person and return whole dong.

    Spaces are dropped, and one mark ₫, đ, VND or VNĐ at the start or end. What is left must be plain
    digits ("1250000") or thousands split by ``.`` or ``,`` ("1.250.000",
    "1,250,000"; the first block has no leading zero). "1,5", "1.5", "12.34",
    "-100", "abc", "0", "000.001" and "" are refused with ``ValueError``.
    """
    if type(value) is int:
        return check_amount(value)
    if not isinstance(value, str):
        raise ValueError(f"Amount not understood. {_AMOUNT_HELP}")
    s = _SPACES.sub("", text.nfc(value))
    s = _CURRENCY.sub("", s)
    if not s:
        raise ValueError(f"Amount is empty. {_AMOUNT_HELP}")
    if _PLAIN.fullmatch(s):
        digits = s
    elif _THOUSANDS.fullmatch(s):
        digits = s.replace(".", "").replace(",", "")
    else:
        raise ValueError(f'Amount "{value.strip()}" not understood. No decimals, no minus sign. {_AMOUNT_HELP}')
    return check_amount(int(digits))


def check_amount(amount):
    """Return ``amount`` if it is a whole number of dong from 1 up to the limit, else raise ``ValueError``."""
    if type(amount) is not int:
        raise ValueError(f"Amount must be a whole number of dong. {_AMOUNT_HELP}")
    if amount <= 0:
        raise ValueError(f"Amount must be above 0. {_AMOUNT_HELP}")
    if amount > MAX_AMOUNT:
        raise ValueError("Amount is too large.")
    return amount


def format_vnd(n):
    """Whole dong as text with dots between thousands: ``1250000 -> "1.250.000 ₫"``."""
    if type(n) is not int:
        raise ValueError("Only a whole number of dong can be shown as money.")
    sign = "-" if n < 0 else ""
    return f"{sign}{abs(n):,}".replace(",", ".") + " ₫"


# ---------------------------------------------------------------- helpers

def _check_month(month):
    if isinstance(month, str) and month.strip().isascii() and month.strip().isdigit():
        month = int(month.strip())
    if type(month) is not int or not 1 <= month <= 12:
        raise ValueError("Month must be a whole number from 1 to 12.")
    return month


def _date_range(start, end):
    first = text.check_date(start, "Start date")
    last = text.check_date(end, "End date")
    if last < first:
        raise ValueError("The end date is before the start date.")
    return first, last


def _require(conn, table, row_id, what):
    rid = text.to_id(row_id, what)
    if conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (rid,)).fetchone() is None:
        raise ValueError(f"No {what} with id {rid}.")
    return rid


def _sum(conn, sql, params):
    """Run a ``SELECT COALESCE(SUM(amount), 0)`` and make sure SQLite gave a whole number."""
    value = conn.execute(sql, params).fetchone()[0]
    if type(value) is not int:
        raise RuntimeError("A money total was not a whole number.")
    return value


# ---------------------------------------------------------------- Offering and Expense
#
# A mistyped Offering or Expense is corrected in place or deleted. Neither is one of the glossary's
# dated links (Status, Family, Chi phái, Trưởng Chi phái), so a typo is not history and no old copy
# is kept. ``created_at`` keeps the moment the row was first recorded.

def _offering_values(conn, date, amount, fund_id, giver_person_id, giver_family_id, note):
    """The checked columns of an Offering: ``(date, amount, fund_id, person_id, family_id, note)``.
    Shared by :func:`add_offering` and :func:`update_offering`; call it inside a transaction."""
    day = text.check_date(date, "Date")
    amount = check_amount(amount)
    has_person = giver_person_id not in (None, "")
    has_family = giver_family_id not in (None, "")
    if has_person and has_family:
        raise ValueError("An Offering has one Giver: a Person or a Family, not both.")
    fund = lists.require_item(conn, fund_id, "fund")["id"]
    pid = _require(conn, "person", giver_person_id, "Person") if has_person else None
    fid = _require(conn, "family", giver_family_id, "Family") if has_family else None
    return day, amount, fund, pid, fid, text.clean_text(note)


def _expense_values(conn, date, amount, spending_category_id, note):
    """The checked columns of an Expense: ``(date, amount, spending_category_id, note)``."""
    day = text.check_date(date, "Date")
    amount = check_amount(amount)
    category = lists.require_item(conn, spending_category_id, "spending_category")["id"]
    return day, amount, category, text.clean_text(note)


def add_offering(conn, date, amount, fund_id, giver_person_id=None, giver_family_id=None, note=None):
    """Record an Offering. ``amount`` is a whole number of dong (int). The Giver is a
    Person, a Family, or nobody (a no-name offering). Returns the id."""
    with transaction(conn):
        values = _offering_values(conn, date, amount, fund_id, giver_person_id, giver_family_id, note)
        cur = conn.execute(
            "INSERT INTO offering (date, amount, fund_id, giver_person_id, giver_family_id, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (*values, text.now_text()),
        )
        return cur.lastrowid


def update_offering(conn, offering_id, *, date, amount, fund_id, giver_person_id=None, giver_family_id=None,
                    note=None):
    """Correct an Offering in place: every column is set again, with the same checks as
    :func:`add_offering`. ``created_at`` is kept. A missing id raises ``ValueError``."""
    with transaction(conn):
        oid = _require(conn, "offering", offering_id, "Offering")
        values = _offering_values(conn, date, amount, fund_id, giver_person_id, giver_family_id, note)
        conn.execute(
            "UPDATE offering SET date = ?, amount = ?, fund_id = ?, giver_person_id = ?, giver_family_id = ?, "
            "note = ? WHERE id = ?",
            (*values, oid),
        )


def delete_offering(conn, offering_id):
    """Delete one Offering (a mistake). A missing id raises ``ValueError``."""
    with transaction(conn):
        oid = _require(conn, "offering", offering_id, "Offering")
        conn.execute("DELETE FROM offering WHERE id = ?", (oid,))


def add_expense(conn, date, amount, spending_category_id, note=None):
    """Record an Expense with a Spending category. Returns the id."""
    with transaction(conn):
        values = _expense_values(conn, date, amount, spending_category_id, note)
        cur = conn.execute(
            "INSERT INTO expense (date, amount, spending_category_id, note, created_at) VALUES (?, ?, ?, ?, ?)",
            (*values, text.now_text()),
        )
        return cur.lastrowid


def update_expense(conn, expense_id, *, date, amount, spending_category_id, note=None):
    """Correct an Expense in place, with the same checks as :func:`add_expense`. ``created_at`` is kept."""
    with transaction(conn):
        eid = _require(conn, "expense", expense_id, "Expense")
        values = _expense_values(conn, date, amount, spending_category_id, note)
        conn.execute("UPDATE expense SET date = ?, amount = ?, spending_category_id = ?, note = ? WHERE id = ?",
                     (*values, eid))


def delete_expense(conn, expense_id):
    """Delete one Expense (a mistake). A missing id raises ``ValueError``."""
    with transaction(conn):
        eid = _require(conn, "expense", expense_id, "Expense")
        conn.execute("DELETE FROM expense WHERE id = ?", (eid,))


_OFFERING_SELECT = (
    "SELECT o.id, o.date, o.amount, o.fund_id, li.name AS fund_name, o.giver_person_id, "
    "o.giver_family_id, COALESCE(p.full_name, f.name) AS giver_name, o.note, o.created_at "
    "FROM offering o JOIN list_item li ON li.id = o.fund_id "
    "LEFT JOIN person p ON p.id = o.giver_person_id "
    "LEFT JOIN family f ON f.id = o.giver_family_id "
)
_EXPENSE_SELECT = (
    "SELECT e.id, e.date, e.amount, e.spending_category_id, li.name AS spending_category_name, "
    "e.note, e.created_at FROM expense e JOIN list_item li ON li.id = e.spending_category_id "
)


def get_offering(conn, offering_id):
    """One Offering with the columns of :func:`list_offerings`, or ``None``."""
    return conn.execute(_OFFERING_SELECT + "WHERE o.id = ?", (text.to_id(offering_id, "Offering"),)).fetchone()


def get_expense(conn, expense_id):
    """One Expense with the columns of :func:`list_expenses`, or ``None``."""
    return conn.execute(_EXPENSE_SELECT + "WHERE e.id = ?", (text.to_id(expense_id, "Expense"),)).fetchone()


def list_offerings(conn, start, end):
    """Offerings from ``start`` to ``end`` (dates, both included), oldest first.
    Extra columns: fund_name, giver_name (``None`` for a no-name offering)."""
    first, last = _date_range(start, end)
    return conn.execute(_OFFERING_SELECT + "WHERE o.date BETWEEN ? AND ? ORDER BY o.date, o.id",
                        (first, last)).fetchall()


def list_expenses(conn, start, end):
    """Expenses from ``start`` to ``end`` (dates, both included), oldest first.
    Extra column: spending_category_name."""
    first, last = _date_range(start, end)
    return conn.execute(_EXPENSE_SELECT + "WHERE e.date BETWEEN ? AND ? ORDER BY e.date, e.id",
                        (first, last)).fetchall()


def month_totals(conn, year, month):
    """Totals of one month: ``{'offerings': int, 'expenses': int, 'balance': int}`` in dong."""
    year = _check_year(year)
    month = _check_month(month)
    first = _dt.date(year, month, 1).isoformat()
    nxt = (_dt.date(year + 1, 1, 1) if month == 12 else _dt.date(year, month + 1, 1)).isoformat()
    offerings = _sum(conn, "SELECT COALESCE(SUM(amount), 0) FROM offering WHERE date >= ? AND date < ?",
                     (first, nxt))
    expenses = _sum(conn, "SELECT COALESCE(SUM(amount), 0) FROM expense WHERE date >= ? AND date < ?",
                    (first, nxt))
    return {"offerings": offerings, "expenses": expenses, "balance": offerings - expenses}


# ---------------------------------------------------------------- Giving statement

_FAMILY_WHERE = (
    "(o.giver_family_id = :fid OR EXISTS (SELECT 1 FROM family_link fl "
    "WHERE fl.person_id = o.giver_person_id AND fl.family_id = :fid "
    "AND fl.start_date <= o.date AND (fl.end_date IS NULL OR fl.end_date > o.date)))"
)


def giving_statement(conn, year, person_id=None, family_id=None):
    """The yearly Giving statement of one Giver (a Person or a Family).

    A Person's statement holds the Offerings they gave. A Family's statement holds
    the Offerings the Family gave plus those of each Person on a date when that
    Person was in the Family. Private notes and Offering notes are never included.

    Returns ``{'year', 'kind' ('person'|'family'), 'giver_id', 'giver_name',
    'church_name', 'rows': [{'date', 'fund', 'amount', 'given_by'}], 'total'}``.
    """
    year = _check_year(year)
    has_person = person_id not in (None, "")
    has_family = family_id not in (None, "")
    if has_person == has_family:
        raise ValueError("A Giving statement is for one Person or one Family: give exactly one of them.")
    params = {"start": f"{year:04d}-01-01", "end": f"{year:04d}-12-31"}
    if has_person:
        params["pid"] = text.to_id(person_id, "Person")
        giver = conn.execute("SELECT full_name AS name FROM person WHERE id = :pid", params).fetchone()
        where, kind, giver_id = "o.giver_person_id = :pid", "person", params["pid"]
    else:
        params["fid"] = text.to_id(family_id, "Family")
        giver = conn.execute("SELECT name FROM family WHERE id = :fid", params).fetchone()
        where, kind, giver_id = _FAMILY_WHERE, "family", params["fid"]
    if giver is None:
        raise ValueError(f"No {kind.title()} with id {giver_id}.")
    base = f"FROM offering o WHERE o.date BETWEEN :start AND :end AND {where}"
    rows = conn.execute(
        "SELECT o.date, li.name AS fund, o.amount, COALESCE(p.full_name, f.name) AS given_by "
        "FROM offering o JOIN list_item li ON li.id = o.fund_id "
        "LEFT JOIN person p ON p.id = o.giver_person_id "
        "LEFT JOIN family f ON f.id = o.giver_family_id "
        f"WHERE o.date BETWEEN :start AND :end AND {where} ORDER BY o.date, o.id",
        params,
    ).fetchall()
    total = _sum(conn, f"SELECT COALESCE(SUM(o.amount), 0) {base}", params)
    return {
        "year": year,
        "kind": kind,
        "giver_id": giver_id,
        "giver_name": giver["name"],
        "church_name": settings.get_setting(conn, "church_name"),
        "rows": [{"date": r["date"], "fund": r["fund"], "amount": r["amount"], "given_by": r["given_by"]}
                 for r in rows],
        "total": total,
    }
