"""The whole Church Manager database schema (version 1) and the default lists.

Rules kept by the database itself:
- History rows (Status, Family link, Chi phái link, Trưởng Chi phái, Ministry
  link) are never deleted. The only allowed update closes ``end_date`` once:
  NULL -> a date on or after ``start_date``. One open row per owner.
- Money is INTEGER dong only: a CHECK on ``typeof(amount) = 'integer'``.
- Private notes live only in ``private_note``.
- List items are never deleted (hide them with ``active = 0``).
"""

SCHEMA_VERSION = 1

# New church setup keeps only these. Tuples of (code, name).
DEFAULT_LISTS = {
    "status": (
        ("member", "Member"),
        ("attender", "Attender"),
        ("visitor", "Visitor"),
        ("left", "Left"),
        ("passed_away", "Passed away"),
    ),
    "ministry": ((None, "Worship"), (None, "Youth"), (None, "Children")),
    "fund": ((None, "General"), (None, "Building"), (None, "Missions")),
    "spending_category": ((None, "Rent"), (None, "Utilities"), (None, "Events")),
    "recipient": ((None, "Chính quyền"), (None, "Giáo hội"), (None, "Hội Thánh")),
    "purpose": ((None, "Invitation"), (None, "Notice"), (None, "Certificate"), (None, "Report")),
}
LIST_NAMES = tuple(DEFAULT_LISTS)

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
}

# (table, column, list_name): the column must point at an item of that list.
LIST_COLUMNS = (
    ("person_status", "status_id", "status"),
    ("ministry_link", "ministry_id", "ministry"),
    ("offering", "fund_id", "fund"),
    ("expense", "spending_category_id", "spending_category"),
    ("sent_document", "recipient_id", "recipient"),
    ("sent_document", "purpose_id", "purpose"),
)

_D = "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"
_DT = "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]'"


def _in(values):
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def _history(name, columns_sql):
    return f"""
CREATE TABLE {name} (
    id         INTEGER PRIMARY KEY,
{columns_sql}
    start_date TEXT NOT NULL,
    end_date   TEXT,
    CHECK (start_date GLOB {_D}),
    CHECK (end_date IS NULL OR (end_date GLOB {_D} AND end_date >= start_date))
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


def _history_triggers():
    out = []
    for table, columns in HISTORY_TABLES.items():
        same = " AND ".join(f"NEW.{c} IS OLD.{c}" for c in ("id", "start_date") + columns)
        out.append(
            f"CREATE TRIGGER {table}_never_delete BEFORE DELETE ON {table}\n"
            "BEGIN SELECT RAISE(ABORT, 'history is never deleted'); END"
        )
        out.append(
            f"CREATE TRIGGER {table}_close_only BEFORE UPDATE ON {table}\n"
            f"WHEN NOT (OLD.end_date IS NULL AND NEW.end_date IS NOT NULL\n"
            f"          AND NEW.end_date >= OLD.start_date AND {same})\n"
            "BEGIN SELECT RAISE(ABORT, "
            "'history is never changed: only an open row may be closed once, "
            "with an end date on or after its start date'); END"
        )
    return out


def _list_triggers():
    out = []
    for table, column, list_name in LIST_COLUMNS:
        check = (
            f"WHEN NOT EXISTS (SELECT 1 FROM list_item WHERE id = NEW.{column} "
            f"AND list_name = '{list_name}')\n"
            f"BEGIN SELECT RAISE(ABORT, '{column} must be an item of the {list_name} list'); END"
        )
        out.append(f"CREATE TRIGGER {table}_{column}_list_insert BEFORE INSERT ON {table}\n{check}")
        out.append(f"CREATE TRIGGER {table}_{column}_list_update BEFORE UPDATE OF {column} ON {table}\n{check}")
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


STATEMENTS = TABLES + INDEXES + tuple(_history_triggers()) + tuple(_list_triggers())


def create_schema(conn):
    """Create every table, index and trigger, then set ``PRAGMA user_version``.

    Run inside a transaction on an empty database.
    """
    for statement in STATEMENTS:
        conn.execute(statement)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def insert_default_lists(conn):
    """Insert ``DEFAULT_LISTS`` into ``list_item`` (sort_order 1, 2, 3, ...)."""
    for list_name, items in DEFAULT_LISTS.items():
        for order, (code, name) in enumerate(items, start=1):
            conn.execute(
                "INSERT INTO list_item (list_name, code, name, sort_order, active) VALUES (?, ?, ?, ?, 1)",
                (list_name, code, name, order),
            )
