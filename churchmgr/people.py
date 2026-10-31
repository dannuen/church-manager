"""People: Person, Status, Family, Chi phái, Trưởng Chi phái, Ministry, Private note.

History is never lost. A change closes the open row (end_date = the new
start_date) and adds a new open row. Old rows are never deleted or rewritten.
A link counts on a date d when start_date <= d and (end_date is empty or d < end_date).
"""

from . import lists, text
from .db import transaction
from .schema import FAMILY_ROLES, MINISTRY_ROLES

GENDERS = ("M", "F")
_KEEP = object()  # "do not change this field" in update functions


# ---------------------------------------------------------------- helpers

def _require_row(conn, table, row_id, what):
    rid = text.to_id(row_id, what)
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (rid,)).fetchone()
    if row is None:
        raise ValueError(f"No {what} with id {rid}.")
    return row


def _set_history(conn, table, owner, values, start_date):
    """Change one history line. Shared by Status, Family, Chi phái, Trưởng Chi phái, Ministry.

    ``owner``: columns that pick the line, e.g. ``{"person_id": 5}``.
    ``values``: the new values, or ``None`` to only close the open row.
    Same values as the open row = no change. A start date before the last
    change in this line is refused. Returns the open row id, or ``None``.
    Call inside a transaction.
    """
    start = text.check_date(start_date, "Start date")
    where = " AND ".join(f"{col} = ?" for col in owner)
    rows = conn.execute(f"SELECT * FROM {table} WHERE {where}", tuple(owner.values())).fetchall()
    open_row = next((r for r in rows if r["end_date"] is None), None)
    if open_row is not None and values is not None and all(open_row[c] == v for c, v in values.items()):
        return open_row["id"]
    if open_row is None and values is None:
        return None
    latest = max((r["end_date"] or r["start_date"] for r in rows), default=None)
    if latest is not None and start < latest:
        raise ValueError(
            f"Start date {start} is before {latest}, the date of the last change. "
            "History is never rewritten; use a date on or after it."
        )
    if open_row is not None:
        conn.execute(f"UPDATE {table} SET end_date = ? WHERE id = ?", (start, open_row["id"]))
    if values is None:
        return None
    cols = [*owner, *values, "start_date"]
    params = [*owner.values(), *values.values(), start]
    cur = conn.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", params
    )
    return cur.lastrowid


def _on_date_filter(alias, on_date):
    """SQL and params for 'the link counts on this date' (``None`` = the open row)."""
    if on_date is None:
        return f"{alias}.end_date IS NULL", []
    day = text.check_date(on_date, "Date")
    return f"{alias}.start_date <= ? AND ({alias}.end_date IS NULL OR {alias}.end_date > ?)", [day, day]


def _gender(value):
    if value is None or value == "":
        return None
    g = str(value).strip().upper()
    if g not in GENDERS:
        raise ValueError("Gender must be M or F, or empty.")
    return g


def _optional_date(value, what):
    return None if value is None or value == "" else text.check_date(value, what)


def _given_name_key(row):
    folded = row["name_folded"]
    return (folded.rsplit(" ", 1)[-1], folded, row["full_name"], row["id"])


# ---------------------------------------------------------------- Person

def add_person(conn, full_name, gender=None, birth_date=None, phone=None, address=None,
               note=None, status_id=None, start_date=None):
    """Add a Person and return the id. With ``status_id``, also set their Status
    from ``start_date`` (today if empty). ``note`` is a normal note, not private."""
    name = text.clean_name(full_name, "Full name")
    values = (
        name, text.fold(name), _gender(gender), _optional_date(birth_date, "Birth date"),
        text.clean_text(phone), text.clean_text(address), text.clean_text(note), text.now_text(),
    )
    with transaction(conn):
        cur = conn.execute(
            "INSERT INTO person (full_name, name_folded, gender, birth_date, phone, address, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            values,
        )
        person_id = cur.lastrowid
        if status_id is not None and status_id != "":
            set_status(conn, person_id, status_id, start_date or text.today_text())
    return person_id


def update_person(conn, person_id, *, full_name=_KEEP, gender=_KEEP, birth_date=_KEEP,
                  phone=_KEEP, address=_KEEP, note=_KEEP):
    """Change the given fields of a Person. ``None`` clears a field (not the name).
    ``name_folded`` always follows ``full_name``."""
    pid = _require_row(conn, "person", person_id, "Person")["id"]
    changes = {}
    if full_name is not _KEEP:
        name = text.clean_name(full_name, "Full name")
        changes["full_name"] = name
        changes["name_folded"] = text.fold(name)
    if gender is not _KEEP:
        changes["gender"] = _gender(gender)
    if birth_date is not _KEEP:
        changes["birth_date"] = _optional_date(birth_date, "Birth date")
    if phone is not _KEEP:
        changes["phone"] = text.clean_text(phone)
    if address is not _KEEP:
        changes["address"] = text.clean_text(address)
    if note is not _KEEP:
        changes["note"] = text.clean_text(note)
    if changes:
        sets = ", ".join(f"{col} = ?" for col in changes)
        conn.execute(f"UPDATE person SET {sets} WHERE id = ?", [*changes.values(), pid])


def get_person(conn, person_id):
    """One Person row, or ``None``."""
    return conn.execute(
        "SELECT * FROM person WHERE id = ?", (text.to_id(person_id, "Person"),)
    ).fetchone()


def list_persons(conn, status_id=None):
    """All Persons with their current Status, sorted by given name (last word), then full name.
    With ``status_id``, only Persons whose current Status is that item."""
    sql = (
        "SELECT p.*, ps.status_id, li.name AS status_name, li.code AS status_code "
        "FROM person p "
        "LEFT JOIN person_status ps ON ps.person_id = p.id AND ps.end_date IS NULL "
        "LEFT JOIN list_item li ON li.id = ps.status_id"
    )
    params = []
    if status_id is not None:
        sql += " WHERE ps.status_id = ?"
        params.append(text.to_id(status_id, "Status"))
    return sorted(conn.execute(sql, params).fetchall(), key=_given_name_key)


def person_address(conn, person_id):
    """The address to use: the current Family's address if it has one, else the Person's own."""
    person = _require_row(conn, "person", person_id, "Person")
    family = current_family(conn, person["id"])
    if family is not None and family["address"]:
        return family["address"]
    return person["address"]


# ---------------------------------------------------------------- Status

def set_status(conn, person_id, status_id, start_date):
    """Give a Person a new Status from ``start_date``. The old row is closed and kept.
    Same Status as now = no change. Returns the open row id."""
    with transaction(conn):
        pid = _require_row(conn, "person", person_id, "Person")["id"]
        sid = lists.require_item(conn, status_id, "status")["id"]
        return _set_history(conn, "person_status", {"person_id": pid}, {"status_id": sid}, start_date)


def current_status(conn, person_id):
    """The open Status row (status_id, name, code, start_date), or ``None``."""
    return conn.execute(
        "SELECT ps.id, ps.status_id, li.name, li.code, ps.start_date, ps.end_date "
        "FROM person_status ps JOIN list_item li ON li.id = ps.status_id "
        "WHERE ps.person_id = ? AND ps.end_date IS NULL",
        (text.to_id(person_id, "Person"),),
    ).fetchone()


def status_history(conn, person_id):
    """Every Status row of a Person, oldest first."""
    return conn.execute(
        "SELECT ps.id, ps.status_id, li.name, li.code, ps.start_date, ps.end_date "
        "FROM person_status ps JOIN list_item li ON li.id = ps.status_id "
        "WHERE ps.person_id = ? ORDER BY ps.start_date, ps.id",
        (text.to_id(person_id, "Person"),),
    ).fetchall()


# ---------------------------------------------------------------- Family

def add_family(conn, name, address=None):
    """Add a Family and return the id."""
    name = text.clean_name(name, "Family name")
    cur = conn.execute(
        "INSERT INTO family (name, name_folded, address, created_at) VALUES (?, ?, ?, ?)",
        (name, text.fold(name), text.clean_text(address), text.now_text()),
    )
    return cur.lastrowid


def update_family(conn, family_id, *, name=_KEEP, address=_KEEP):
    """Change the name and/or address of a Family."""
    fid = _require_row(conn, "family", family_id, "Family")["id"]
    changes = {}
    if name is not _KEEP:
        clean = text.clean_name(name, "Family name")
        changes["name"] = clean
        changes["name_folded"] = text.fold(clean)
    if address is not _KEEP:
        changes["address"] = text.clean_text(address)
    if changes:
        sets = ", ".join(f"{col} = ?" for col in changes)
        conn.execute(f"UPDATE family SET {sets} WHERE id = ?", [*changes.values(), fid])


def get_family(conn, family_id):
    """One Family row, or ``None``."""
    return conn.execute(
        "SELECT * FROM family WHERE id = ?", (text.to_id(family_id, "Family"),)
    ).fetchone()


def list_families(conn):
    """All Families sorted by name."""
    return conn.execute("SELECT * FROM family ORDER BY name_folded, id").fetchall()


def set_family(conn, person_id, family_id, family_role, start_date):
    """Put a Person in a Family with a Family role from ``start_date``.
    ``family_id=None`` = the Person leaves their Family. A new role in the same
    Family is a new row. Old rows are closed and kept. Returns the open row id or ``None``."""
    with transaction(conn):
        pid = _require_row(conn, "person", person_id, "Person")["id"]
        if family_id is None or family_id == "":
            return _set_history(conn, "family_link", {"person_id": pid}, None, start_date)
        fid = _require_row(conn, "family", family_id, "Family")["id"]
        if family_role not in FAMILY_ROLES:
            raise ValueError(f"Family role must be one of: {', '.join(FAMILY_ROLES)}.")
        return _set_history(
            conn, "family_link", {"person_id": pid},
            {"family_id": fid, "family_role": family_role}, start_date,
        )


def current_family(conn, person_id):
    """The Person's open Family link (family_id, name, address, family_role, start_date), or ``None``."""
    return conn.execute(
        "SELECT fl.id, fl.family_id, f.name, f.address, fl.family_role, fl.start_date, fl.end_date "
        "FROM family_link fl JOIN family f ON f.id = fl.family_id "
        "WHERE fl.person_id = ? AND fl.end_date IS NULL",
        (text.to_id(person_id, "Person"),),
    ).fetchone()


def family_members(conn, family_id, on_date=None):
    """Persons in a Family now (or on ``on_date``): Head, Spouse, Child, Other, then by birth date."""
    where, params = _on_date_filter("fl", on_date)
    return conn.execute(
        "SELECT p.id, p.full_name, p.name_folded, p.birth_date, fl.family_role, fl.start_date, fl.end_date "
        "FROM family_link fl JOIN person p ON p.id = fl.person_id "
        f"WHERE fl.family_id = ? AND {where} "
        "ORDER BY CASE fl.family_role WHEN 'Head' THEN 0 WHEN 'Spouse' THEN 1 WHEN 'Child' THEN 2 ELSE 3 END, "
        "p.birth_date IS NULL, p.birth_date, p.name_folded, p.id",
        [text.to_id(family_id, "Family"), *params],
    ).fetchall()


def family_history(conn, person_id):
    """Every Family link of a Person, oldest first."""
    return conn.execute(
        "SELECT fl.id, fl.family_id, f.name, fl.family_role, fl.start_date, fl.end_date "
        "FROM family_link fl JOIN family f ON f.id = fl.family_id "
        "WHERE fl.person_id = ? ORDER BY fl.start_date, fl.id",
        (text.to_id(person_id, "Person"),),
    ).fetchall()


# ---------------------------------------------------------------- Chi phái

def add_chi_phai(conn, name):
    """Add a Chi phái and return the id. Names are unique."""
    name = text.clean_name(name, "Chi phái name")
    if conn.execute("SELECT 1 FROM chi_phai WHERE name = ?", (name,)).fetchone():
        raise ValueError(f'Chi phái "{name}" already exists.')
    cur = conn.execute("INSERT INTO chi_phai (name, name_folded) VALUES (?, ?)", (name, text.fold(name)))
    return cur.lastrowid


def rename_chi_phai(conn, chi_phai_id, name):
    """Give a Chi phái a new name."""
    cid = _require_row(conn, "chi_phai", chi_phai_id, "Chi phái")["id"]
    name = text.clean_name(name, "Chi phái name")
    other = conn.execute("SELECT id FROM chi_phai WHERE name = ?", (name,)).fetchone()
    if other is not None and other["id"] != cid:
        raise ValueError(f'Chi phái "{name}" already exists.')
    conn.execute("UPDATE chi_phai SET name = ?, name_folded = ? WHERE id = ?", (name, text.fold(name), cid))


def get_chi_phai(conn, chi_phai_id):
    """One Chi phái row, or ``None``."""
    return conn.execute(
        "SELECT * FROM chi_phai WHERE id = ?", (text.to_id(chi_phai_id, "Chi phái"),)
    ).fetchone()


def list_chi_phai(conn):
    """All Chi phái sorted by name."""
    return conn.execute("SELECT * FROM chi_phai ORDER BY name_folded, id").fetchall()


def set_family_chi_phai(conn, family_id, chi_phai_id, start_date):
    """Put a Family in a Chi phái from ``start_date``. ``None`` = the Family leaves its Chi phái."""
    with transaction(conn):
        fid = _require_row(conn, "family", family_id, "Family")["id"]
        if chi_phai_id is None or chi_phai_id == "":
            return _set_history(conn, "chi_phai_link", {"family_id": fid}, None, start_date)
        cid = _require_row(conn, "chi_phai", chi_phai_id, "Chi phái")["id"]
        return _set_history(conn, "chi_phai_link", {"family_id": fid}, {"chi_phai_id": cid}, start_date)


def current_chi_phai(conn, family_id):
    """The Family's open Chi phái link (chi_phai_id, name, start_date), or ``None``."""
    return conn.execute(
        "SELECT cl.id, cl.chi_phai_id, c.name, cl.start_date, cl.end_date "
        "FROM chi_phai_link cl JOIN chi_phai c ON c.id = cl.chi_phai_id "
        "WHERE cl.family_id = ? AND cl.end_date IS NULL",
        (text.to_id(family_id, "Family"),),
    ).fetchone()


def family_chi_phai_history(conn, family_id):
    """Every Chi phái link of a Family, oldest first."""
    return conn.execute(
        "SELECT cl.id, cl.chi_phai_id, c.name, cl.start_date, cl.end_date "
        "FROM chi_phai_link cl JOIN chi_phai c ON c.id = cl.chi_phai_id "
        "WHERE cl.family_id = ? ORDER BY cl.start_date, cl.id",
        (text.to_id(family_id, "Family"),),
    ).fetchall()


def chi_phai_families(conn, chi_phai_id, on_date=None):
    """Families in a Chi phái now (or on ``on_date``), by name."""
    where, params = _on_date_filter("cl", on_date)
    return conn.execute(
        "SELECT f.id, f.name, f.address, cl.start_date, cl.end_date "
        "FROM chi_phai_link cl JOIN family f ON f.id = cl.family_id "
        f"WHERE cl.chi_phai_id = ? AND {where} ORDER BY f.name_folded, f.id",
        [text.to_id(chi_phai_id, "Chi phái"), *params],
    ).fetchall()


def set_truong_chi_phai(conn, chi_phai_id, person_id, start_date):
    """Make a Person the Trưởng Chi phái from ``start_date``. ``None`` = no leader from then.
    The past leader's row is closed and kept."""
    with transaction(conn):
        cid = _require_row(conn, "chi_phai", chi_phai_id, "Chi phái")["id"]
        if person_id is None or person_id == "":
            return _set_history(conn, "truong_chi_phai", {"chi_phai_id": cid}, None, start_date)
        pid = _require_row(conn, "person", person_id, "Person")["id"]
        return _set_history(conn, "truong_chi_phai", {"chi_phai_id": cid}, {"person_id": pid}, start_date)


def current_truong_chi_phai(conn, chi_phai_id):
    """The open Trưởng Chi phái row (person_id, full_name, start_date), or ``None``."""
    return conn.execute(
        "SELECT t.id, t.person_id, p.full_name, t.start_date, t.end_date "
        "FROM truong_chi_phai t JOIN person p ON p.id = t.person_id "
        "WHERE t.chi_phai_id = ? AND t.end_date IS NULL",
        (text.to_id(chi_phai_id, "Chi phái"),),
    ).fetchone()


def truong_chi_phai_history(conn, chi_phai_id):
    """Every Trưởng Chi phái of a Chi phái, oldest first."""
    return conn.execute(
        "SELECT t.id, t.person_id, p.full_name, t.start_date, t.end_date "
        "FROM truong_chi_phai t JOIN person p ON p.id = t.person_id "
        "WHERE t.chi_phai_id = ? ORDER BY t.start_date, t.id",
        (text.to_id(chi_phai_id, "Chi phái"),),
    ).fetchall()


# ---------------------------------------------------------------- Ministry

def set_ministry(conn, person_id, ministry_id, ministry_role, start_date):
    """Give a Person a Ministry role (Leader or Member) in a Ministry from ``start_date``.
    ``ministry_role=None`` = the Person stops serving in that Ministry. Old rows are kept."""
    with transaction(conn):
        pid = _require_row(conn, "person", person_id, "Person")["id"]
        mid = lists.require_item(conn, ministry_id, "ministry")["id"]
        owner = {"person_id": pid, "ministry_id": mid}
        if ministry_role is None or ministry_role == "":
            return _set_history(conn, "ministry_link", owner, None, start_date)
        if ministry_role not in MINISTRY_ROLES:
            raise ValueError(f"Ministry role must be one of: {', '.join(MINISTRY_ROLES)}.")
        return _set_history(conn, "ministry_link", owner, {"ministry_role": ministry_role}, start_date)


def current_ministries(conn, person_id):
    """The Person's open Ministry links (ministry_id, name, ministry_role, start_date)."""
    return conn.execute(
        "SELECT ml.id, ml.ministry_id, li.name, ml.ministry_role, ml.start_date, ml.end_date "
        "FROM ministry_link ml JOIN list_item li ON li.id = ml.ministry_id "
        "WHERE ml.person_id = ? AND ml.end_date IS NULL ORDER BY li.sort_order, li.id",
        (text.to_id(person_id, "Person"),),
    ).fetchall()


def ministry_history(conn, person_id):
    """Every Ministry link of a Person, oldest first."""
    return conn.execute(
        "SELECT ml.id, ml.ministry_id, li.name, ml.ministry_role, ml.start_date, ml.end_date "
        "FROM ministry_link ml JOIN list_item li ON li.id = ml.ministry_id "
        "WHERE ml.person_id = ? ORDER BY ml.start_date, ml.id",
        (text.to_id(person_id, "Person"),),
    ).fetchall()


def ministry_people(conn, ministry_id, on_date=None):
    """Persons in a Ministry now (or on ``on_date``): Leaders first, then by given name."""
    where, params = _on_date_filter("ml", on_date)
    rows = conn.execute(
        "SELECT p.id, p.full_name, p.name_folded, ml.ministry_role, ml.start_date, ml.end_date "
        "FROM ministry_link ml JOIN person p ON p.id = ml.person_id "
        f"WHERE ml.ministry_id = ? AND {where}",
        [text.to_id(ministry_id, "Ministry"), *params],
    ).fetchall()
    return sorted(rows, key=lambda r: (r["ministry_role"] != "Leader", _given_name_key(r)))


# ---------------------------------------------------------------- Private note

def add_private_note(conn, person_id, body):
    """Add a Private note (pastor only; removed at Handover). Returns the id."""
    pid = _require_row(conn, "person", person_id, "Person")["id"]
    clean = text.clean_text(body)
    if clean is None:
        raise ValueError("A private note needs some text.")
    cur = conn.execute(
        "INSERT INTO private_note (person_id, body, created_at) VALUES (?, ?, ?)",
        (pid, clean, text.now_text()),
    )
    return cur.lastrowid


def list_private_notes(conn, person_id):
    """A Person's Private notes, newest first."""
    return conn.execute(
        "SELECT id, person_id, body, created_at FROM private_note "
        "WHERE person_id = ? ORDER BY created_at DESC, id DESC",
        (text.to_id(person_id, "Person"),),
    ).fetchall()
