"""The whole Church Manager database schema (version 2), the default lists and the default Service roles.

Rules kept by the database itself:
- History rows (Status, Family link, Chi phái link, Trưởng Chi phái, Ministry
  link, Service role link) are never deleted. The only allowed update closes ``end_date`` once:
  NULL -> a date on or after ``start_date``. One exception, for Status rows only
  (Rule 4 exception, approved by the pastor): a closed row may also get an earlier
  end date, still on or after its start date, when an older Status is added inside
  it (``people.insert_status``). One open row per owner.
- Money is INTEGER dong only: a CHECK on ``typeof(amount) = 'integer'``.
- Private notes live only in ``private_note``.
- List items and Service roles are never deleted (hide them with ``active = 0``).

A church copy made by an older app gets the triggers of this file when it opens
(``stale_triggers``, ``renew_triggers``). A version-1 copy also gets ``STATEMENTS_V2`` and the default
Service roles (``db.open_church_copy``). Old tables and indexes never change.
"""

SCHEMA_VERSION = 2
KNOWN_VERSIONS = (1, 2)  # versions this app opens; version 1 is brought to 2 when it opens

# New church setup keeps only these. Tuples of (code, Vietnamese name, English name): a new church
# copy stores the name in its language (``default_name``). Status codes never change.
DEFAULT_LISTS = {
    "status": (
        ("member", "Tín hữu", "Member"),
        ("attender", "Thân hữu", "Attender"),
        ("visitor", "Khách", "Visitor"),
        ("left", "Nghỉ nhóm", "Left"),
        ("passed_away", "Về với Chúa", "Passed away"),
    ),
    "ministry": ((None, "Ban Âm nhạc", "Worship"), (None, "Ban Thanh niên", "Youth"),
                 (None, "Ban Thiếu nhi", "Children")),
    "fund": ((None, "Quỹ Hội Thánh", "General"), (None, "Quỹ xây dựng", "Building"),
             (None, "Quỹ truyền giáo", "Missions")),
    "spending_category": ((None, "Tiền thuê", "Rent"), (None, "Điện nước", "Utilities"),
                          (None, "Chương trình", "Events")),
    "recipient": ((None, "Chính quyền", "Chính quyền"), (None, "Giáo hội", "Giáo hội"),
                  (None, "Hội Thánh", "Hội Thánh")),
    "purpose": ((None, "Thư mời", "Invitation"), (None, "Thông báo", "Notice"),
                (None, "Giấy chứng nhận", "Certificate"), (None, "Báo cáo", "Report")),
}
LIST_NAMES = tuple(DEFAULT_LISTS)


def default_name(item, lang):
    """The name of one ``DEFAULT_LISTS`` item in ``lang`` (``vi`` or ``en``)."""
    return item[{"vi": 1, "en": 2}[lang]]


# New church setup and the move to version 2 add these Service roles (sort_order 1, 2, 3, 4). Tuples of
# (Vietnamese name, English name, weekday, done_by, every, month_start); weekday is Python's
# date.weekday() (3 Thursday, 6 Sunday). The copy stores the name of its language. Names are data:
# shown as stored, never translated.
DEFAULT_SERVICE_ROLES = (
    ("Bồi linh", "Bồi linh", 3, "person", 1, 0),
    ("Hướng dẫn chương trình", "Service leader", 6, "person", 1, 1),
    ("Dâng hiến", "Offering leader", 6, "person", 1, 0),  # the pastor's word: the same as the money Offering
    ("Ban ngành", "Ministry in charge", 6, "ministry", 2, 0),  # the pastor's word: the same as Ministry
)


DEFAULT_SETTINGS = {"care_reminder_months": "3"}

FAMILY_ROLES = ("Head", "Spouse", "Child", "Other")
MINISTRY_ROLES = ("Leader", "Member")
CALENDAR_KINDS = ("Service", "Meeting", "Visit", "Event")
CALENDAR_PARTS = ("joins", "serves")

# History table -> the columns besides id/start_date/end_date.
HISTORY_TABLES = {
    "person_status": ("person_id", "status_id"),
    "family_link": ("person_id", "family_id", "family_role"),
    "chi_phai_link": ("family_id", "chi_phai_id"),
    "truong_chi_phai": ("chi_phai_id", "person_id"),
    "ministry_link": ("person_id", "ministry_id", "ministry_role"),
    "service_role_link": ("calendar_item_id", "service_role_id", "person_id", "ministry_id"),  # version 2
}
_V2_HISTORY = ("service_role_link",)

# (table, column, list_name): the column must point at an item of that list.
LIST_COLUMNS = (
    ("person_status", "status_id", "status"),
    ("ministry_link", "ministry_id", "ministry"),
    ("offering", "fund_id", "fund"),
    ("expense", "spending_category_id", "spending_category"),
    ("sent_document", "recipient_id", "recipient"),
    ("sent_document", "purpose_id", "purpose"),
)
# Version 2, the same rule for a column that may be empty (NULL). Kept apart so the text of every
# LIST_COLUMNS trigger stays as it was.
OPTIONAL_LIST_COLUMNS = (
    ("rotation_place", "ministry_id", "ministry"),
    ("service_role_link", "ministry_id", "ministry"),
)

_D = "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"
_DT = "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]'"


def _in(values):
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def _history(name, columns_sql, checks=""):
    return f"""
CREATE TABLE {name} (
    id         INTEGER PRIMARY KEY,
{columns_sql}
    start_date TEXT NOT NULL,
    end_date   TEXT,
    CHECK (start_date GLOB {_D}),
    CHECK (end_date IS NULL OR (end_date GLOB {_D} AND end_date >= start_date)){checks}
)"""


TABLES = (
    """
CREATE TABLE setting (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
)""",
    f"""
CREATE TABLE list_item (
    id         INTEGER PRIMARY KEY,
    list_name  TEXT NOT NULL CHECK (list_name IN {_in(LIST_NAMES)}),
    code       TEXT,
    name       TEXT NOT NULL CHECK (length(trim(name)) > 0),
    sort_order INTEGER NOT NULL DEFAULT 0,
    active     INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    UNIQUE (list_name, name)
)""",
    f"""
CREATE TABLE person (
    id          INTEGER PRIMARY KEY,
    full_name   TEXT NOT NULL CHECK (length(trim(full_name)) > 0),
    name_folded TEXT NOT NULL,
    gender      TEXT CHECK (gender IN ('M', 'F')),
    birth_date  TEXT CHECK (birth_date IS NULL OR birth_date GLOB {_D}),
    phone       TEXT,
    address     TEXT,  -- own address, used when the person has no current Family
    note        TEXT,  -- normal note; Private notes live only in private_note
    created_at  TEXT NOT NULL
)""",
    _history("person_status", """\
    person_id  INTEGER NOT NULL REFERENCES person (id),
    status_id  INTEGER NOT NULL REFERENCES list_item (id),"""),
    """
CREATE TABLE family (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL CHECK (length(trim(name)) > 0),
    name_folded TEXT NOT NULL,
    address     TEXT,
    created_at  TEXT NOT NULL
)""",
    _history("family_link", f"""\
    person_id   INTEGER NOT NULL REFERENCES person (id),
    family_id   INTEGER NOT NULL REFERENCES family (id),
    family_role TEXT NOT NULL CHECK (family_role IN {_in(FAMILY_ROLES)}),"""),
    """
CREATE TABLE chi_phai (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE CHECK (length(trim(name)) > 0),
    name_folded TEXT NOT NULL
)""",
    _history("chi_phai_link", """\
    family_id   INTEGER NOT NULL REFERENCES family (id),
    chi_phai_id INTEGER NOT NULL REFERENCES chi_phai (id),"""),
    _history("truong_chi_phai", """\
    chi_phai_id INTEGER NOT NULL REFERENCES chi_phai (id),
    person_id   INTEGER NOT NULL REFERENCES person (id),"""),
    _history("ministry_link", f"""\
    person_id     INTEGER NOT NULL REFERENCES person (id),
    ministry_id   INTEGER NOT NULL REFERENCES list_item (id),
    ministry_role TEXT NOT NULL CHECK (ministry_role IN {_in(MINISTRY_ROLES)}),"""),
    """
CREATE TABLE private_note (
    id         INTEGER PRIMARY KEY,
    person_id  INTEGER NOT NULL REFERENCES person (id),
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL
)""",
    f"""
CREATE TABLE calendar_item (
    id              INTEGER PRIMARY KEY,
    kind            TEXT NOT NULL CHECK (kind IN {_in(CALENDAR_KINDS)}),
    title           TEXT NOT NULL,
    starts_at       TEXT NOT NULL CHECK (starts_at GLOB {_DT}),
    ends_at         TEXT CHECK (ends_at IS NULL OR ends_at GLOB {_DT}),
    place           TEXT,
    note            TEXT,
    series_id       INTEGER,  -- id of the first row of a repeat series
    visit_person_id INTEGER REFERENCES person (id),
    visit_family_id INTEGER REFERENCES family (id),
    visit_done      INTEGER NOT NULL DEFAULT 0 CHECK (visit_done IN (0, 1)),
    visit_done_date TEXT CHECK (visit_done_date IS NULL OR visit_done_date GLOB {_D}),
    care_note       TEXT,
    CHECK (kind = 'Visit' OR (visit_person_id IS NULL AND visit_family_id IS NULL AND visit_done = 0)),
    CHECK (visit_person_id IS NULL OR visit_family_id IS NULL),
    CHECK ((visit_done = 0 AND visit_done_date IS NULL) OR (visit_done = 1 AND visit_done_date IS NOT NULL)),
    CHECK (ends_at IS NULL OR ends_at >= starts_at)
)""",
    f"""
CREATE TABLE calendar_person (
    calendar_item_id INTEGER NOT NULL REFERENCES calendar_item (id) ON DELETE CASCADE,
    person_id        INTEGER NOT NULL REFERENCES person (id),
    part             TEXT NOT NULL CHECK (part IN {_in(CALENDAR_PARTS)}),
    PRIMARY KEY (calendar_item_id, person_id, part)
)""",
    """
CREATE TABLE head_count (
    id               INTEGER PRIMARY KEY,
    calendar_item_id INTEGER NOT NULL UNIQUE REFERENCES calendar_item (id),
    count            INTEGER NOT NULL CHECK (typeof(count) = 'integer' AND count >= 0),
    absent_note      TEXT
)""",
    f"""
CREATE TABLE offering (
    id              INTEGER PRIMARY KEY,
    date            TEXT NOT NULL CHECK (date GLOB {_D}),
    amount          INTEGER NOT NULL CHECK (typeof(amount) = 'integer' AND amount > 0),
    fund_id         INTEGER NOT NULL REFERENCES list_item (id),
    giver_person_id INTEGER REFERENCES person (id),
    giver_family_id INTEGER REFERENCES family (id),
    note            TEXT,
    created_at      TEXT NOT NULL,
    CHECK (giver_person_id IS NULL OR giver_family_id IS NULL)
)""",
    f"""
CREATE TABLE expense (
    id                   INTEGER PRIMARY KEY,
    date                 TEXT NOT NULL CHECK (date GLOB {_D}),
    amount               INTEGER NOT NULL CHECK (typeof(amount) = 'integer' AND amount > 0),
    spending_category_id INTEGER NOT NULL REFERENCES list_item (id),
    note                 TEXT,
    created_at           TEXT NOT NULL
)""",
    """
CREATE TABLE document (
    id               INTEGER PRIMARY KEY,
    original_name    TEXT NOT NULL,
    stored_name      TEXT NOT NULL UNIQUE,
    size             INTEGER NOT NULL CHECK (typeof(size) = 'integer' AND size >= 0),
    sha256           TEXT NOT NULL,
    person_id        INTEGER REFERENCES person (id),
    family_id        INTEGER REFERENCES family (id),
    calendar_item_id INTEGER REFERENCES calendar_item (id),
    added_at         TEXT NOT NULL,
    CHECK ((person_id IS NOT NULL) + (family_id IS NOT NULL) + (calendar_item_id IS NOT NULL) <= 1)
)""",
    f"""
CREATE TABLE sent_document (
    id           INTEGER PRIMARY KEY,
    year         INTEGER NOT NULL CHECK (typeof(year) = 'integer'),
    seq          INTEGER NOT NULL CHECK (typeof(seq) = 'integer' AND seq > 0),
    date         TEXT NOT NULL CHECK (date GLOB {_D}),
    recipient_id INTEGER NOT NULL REFERENCES list_item (id),
    purpose_id   INTEGER NOT NULL REFERENCES list_item (id),
    subject      TEXT,
    document_id  INTEGER REFERENCES document (id),
    created_at   TEXT NOT NULL,
    UNIQUE (year, seq),
    CHECK (CAST(substr(date, 1, 4) AS INTEGER) = year)
)""",
)

INDEXES = (
    "CREATE UNIQUE INDEX list_item_code ON list_item (list_name, code) WHERE code IS NOT NULL",
    # One open history row per owner.
    "CREATE UNIQUE INDEX person_status_one_open ON person_status (person_id) WHERE end_date IS NULL",
    "CREATE UNIQUE INDEX family_link_one_open ON family_link (person_id) WHERE end_date IS NULL",
    "CREATE UNIQUE INDEX ministry_link_one_open ON ministry_link (person_id, ministry_id) WHERE end_date IS NULL",
    "CREATE UNIQUE INDEX chi_phai_link_one_open ON chi_phai_link (family_id) WHERE end_date IS NULL",
    "CREATE UNIQUE INDEX truong_chi_phai_one_open ON truong_chi_phai (chi_phai_id) WHERE end_date IS NULL",
    # Lookups.
    "CREATE INDEX person_status_person ON person_status (person_id)",
    "CREATE INDEX family_link_person ON family_link (person_id)",
    "CREATE INDEX family_link_family ON family_link (family_id)",
    "CREATE INDEX chi_phai_link_chi_phai ON chi_phai_link (chi_phai_id)",
    "CREATE INDEX truong_chi_phai_person ON truong_chi_phai (person_id)",
    "CREATE INDEX ministry_link_ministry ON ministry_link (ministry_id)",
    "CREATE INDEX private_note_person ON private_note (person_id)",
    "CREATE INDEX calendar_item_starts ON calendar_item (starts_at)",
    "CREATE INDEX calendar_item_series ON calendar_item (series_id)",
    "CREATE INDEX calendar_person_person ON calendar_person (person_id)",
    "CREATE INDEX offering_date ON offering (date)",
    "CREATE INDEX expense_date ON expense (date)",
)

# Version 2: the Service role Roster. A version-1 copy gets these when it opens (``STATEMENTS_V2``).
TABLES_V2 = (
    """
CREATE TABLE service_role (
    id               INTEGER PRIMARY KEY,
    name             TEXT NOT NULL UNIQUE CHECK (length(trim(name)) > 0),
    -- weekday: Python date.weekday(), 0 Monday .. 3 Thursday .. 6 Sunday
    weekday          INTEGER NOT NULL CHECK (typeof(weekday) = 'integer' AND weekday BETWEEN 0 AND 6),
    done_by          TEXT NOT NULL CHECK (done_by IN ('person', 'ministry')),
    -- every: every Nth Service. month_start: the first Service of a month starts a round.
    every            INTEGER NOT NULL DEFAULT 1 CHECK (typeof(every) = 'integer' AND every BETWEEN 1 AND 8),
    month_start      INTEGER NOT NULL DEFAULT 0 CHECK (month_start IN (0, 1)),
    -- month_start_from: the month Rotation place 1 starts (YYYY-MM)
    month_start_from TEXT CHECK (month_start_from IS NULL OR month_start_from GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    sort_order       INTEGER NOT NULL DEFAULT 0,
    active           INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
)""",
    """
CREATE TABLE rotation_place (
    service_role_id INTEGER NOT NULL REFERENCES service_role (id),
    position        INTEGER NOT NULL CHECK (typeof(position) = 'integer' AND position >= 1),
    person_id       INTEGER REFERENCES person (id),
    ministry_id     INTEGER REFERENCES list_item (id),
    CHECK ((person_id IS NULL) + (ministry_id IS NULL) = 1),
    PRIMARY KEY (service_role_id, position)
)""",
    _history("service_role_link", """\
    calendar_item_id INTEGER NOT NULL REFERENCES calendar_item (id),
    service_role_id  INTEGER NOT NULL REFERENCES service_role (id),
    person_id        INTEGER REFERENCES person (id),
    ministry_id      INTEGER REFERENCES list_item (id),""",
             ",\n    CHECK ((person_id IS NULL) + (ministry_id IS NULL) = 1)"),
    f"""
CREATE TABLE skipped_date (
    date   TEXT NOT NULL PRIMARY KEY CHECK (date GLOB {_D}),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0)
)""",
)

INDEXES_V2 = (
    "CREATE UNIQUE INDEX service_role_link_one_open ON service_role_link (calendar_item_id, service_role_id) "
    "WHERE end_date IS NULL",
    "CREATE INDEX service_role_link_item ON service_role_link (calendar_item_id)",
    "CREATE INDEX service_role_link_person ON service_role_link (person_id)",
)


def _history_triggers(tables):
    out = []
    for table in tables:
        columns = HISTORY_TABLES[table]
        same = " AND ".join(f"NEW.{c} IS OLD.{c}" for c in ("id", "start_date") + columns)
        if table == "person_status":
            # Rule 4 exception: an older Status added inside a closed line cuts it (people.insert_status).
            # The name stays, so an older copy's trigger is replaced (renew_triggers), not kept beside it.
            ends = "NEW.end_date IS NOT NULL AND (OLD.end_date IS NULL OR NEW.end_date < OLD.end_date)"
            rule = "only an open row may be closed, or a closed row cut to an earlier end date"
        else:  # this text is the same as before card SP-1
            ends = "OLD.end_date IS NULL AND NEW.end_date IS NOT NULL"
            rule = "only an open row may be closed once"
        out.append(
            f"CREATE TRIGGER {table}_never_delete BEFORE DELETE ON {table}\n"
            "BEGIN SELECT RAISE(ABORT, 'history is never deleted'); END"
        )
        out.append(
            f"CREATE TRIGGER {table}_close_only BEFORE UPDATE ON {table}\n"
            f"WHEN NOT ({ends}\n"
            f"          AND NEW.end_date >= OLD.start_date AND {same})\n"
            "BEGIN SELECT RAISE(ABORT, "
            f"'history is never changed: {rule}, "
            "with an end date on or after its start date'); END"
        )
    return out


def _list_check(table, column, list_name, optional=False):
    """The insert and update triggers that keep ``table.column`` on an item of ``list_name``.
    ``optional``: an empty (NULL) column is allowed too."""
    empty_ok = f"NEW.{column} IS NOT NULL AND " if optional else ""
    check = (
        f"WHEN {empty_ok}NOT EXISTS (SELECT 1 FROM list_item WHERE id = NEW.{column} "
        f"AND list_name = '{list_name}')\n"
        f"BEGIN SELECT RAISE(ABORT, '{column} must be an item of the {list_name} list'); END"
    )
    return [f"CREATE TRIGGER {table}_{column}_list_insert BEFORE INSERT ON {table}\n{check}",
            f"CREATE TRIGGER {table}_{column}_list_update BEFORE UPDATE OF {column} ON {table}\n{check}"]


def _list_triggers():
    out = []
    for table, column, list_name in LIST_COLUMNS:
        out += _list_check(table, column, list_name)
    out.append(
        "CREATE TRIGGER list_item_never_delete BEFORE DELETE ON list_item\n"
        "BEGIN SELECT RAISE(ABORT, 'list items are never deleted; hide them instead'); END"
    )
    out.append(
        "CREATE TRIGGER list_item_keep_list BEFORE UPDATE OF list_name ON list_item\n"
        "WHEN NEW.list_name IS NOT OLD.list_name\n"
        "BEGIN SELECT RAISE(ABORT, 'a list item never moves to another list'); END"
    )
    return out


def _service_role_triggers():
    out = []
    for table, column, list_name in OPTIONAL_LIST_COLUMNS:
        out += _list_check(table, column, list_name, optional=True)
    out.append(
        "CREATE TRIGGER service_role_never_delete BEFORE DELETE ON service_role\n"
        "BEGIN SELECT RAISE(ABORT, 'Service roles are never deleted; hide them instead'); END"
    )
    out.append(
        "CREATE TRIGGER service_role_keep_done_by BEFORE UPDATE OF done_by ON service_role\n"
        "WHEN NEW.done_by IS NOT OLD.done_by\n"
        "BEGIN SELECT RAISE(ABORT, 'the done_by of a Service role never changes'); END"
    )
    return out


TRIGGERS_V1 = (tuple(_history_triggers(t for t in HISTORY_TABLES if t not in _V2_HISTORY))
               + tuple(_list_triggers()))
TRIGGERS_V2 = tuple(_history_triggers(_V2_HISTORY)) + tuple(_service_role_triggers())
TRIGGERS = TRIGGERS_V1 + TRIGGERS_V2  # every trigger of a version-2 copy
STATEMENTS_V2 = TABLES_V2 + INDEXES_V2 + TRIGGERS_V2  # what a version-1 copy gets when it opens
STATEMENTS = TABLES + INDEXES + TRIGGERS_V1 + STATEMENTS_V2


def create_schema(conn):
    """Create every table, index and trigger, then set ``PRAGMA user_version``.

    Run inside a transaction on an empty database.
    """
    for statement in STATEMENTS:
        conn.execute(statement)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def stale_triggers(conn):
    """``(name, statement)`` of each trigger in ``TRIGGERS`` that the church copy lacks or holds with
    another text (a copy made by an older app), in ``TRIGGERS`` order. Reads only."""
    stored = {r[0]: r[1] for r in conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'trigger'")}
    named = ((statement.split()[2], statement) for statement in TRIGGERS)  # CREATE TRIGGER <name> ...
    return [(name, statement) for name, statement in named if stored.get(name) != statement]


def renew_triggers(conn, stale):
    """Make each ``(name, statement)`` from :func:`stale_triggers` again. Run inside a transaction."""
    for name, statement in stale:
        conn.execute(f"DROP TRIGGER IF EXISTS {name}")
        conn.execute(statement)


def insert_default_lists(conn, lang):
    """Insert ``DEFAULT_LISTS`` into ``list_item`` with the names of ``lang`` (sort_order 1, 2, 3, ...)."""
    for list_name, items in DEFAULT_LISTS.items():
        for order, item in enumerate(items, start=1):
            conn.execute(
                "INSERT INTO list_item (list_name, code, name, sort_order, active) VALUES (?, ?, ?, ?, 1)",
                (list_name, item[0], default_name(item, lang), order),
            )


def insert_default_service_roles(conn, lang):
    """Insert ``DEFAULT_SERVICE_ROLES`` into ``service_role`` with the names of ``lang`` (``vi`` or ``en``),
    sort_order 1, 2, 3, 4."""
    name = {"vi": 0, "en": 1}[lang]
    for order, role in enumerate(DEFAULT_SERVICE_ROLES, start=1):
        conn.execute(
            "INSERT INTO service_role (name, weekday, done_by, every, month_start, sort_order) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (role[name], *role[2:], order),
        )
