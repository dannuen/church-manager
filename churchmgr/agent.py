"""Hermes door: a JSON command line for the optional Hermes helper.

    python -m churchmgr.agent COMMAND [options] [--copy FOLDER] [--copies-root FOLDER]

Read commands: status, search, person, family, calendar, money, care-due, lists.

- The door is off by default. The pastor turns it on in Church Manager: Settings > Hermes door.
  With the door off, every command prints the ``door_off`` answer, changes nothing and exits 3.
- Read commands open church.db read-only with :func:`connect_ro` (SQLite ``mode=ro``), so a write
  fails inside SQLite. They reuse the app's functions; this module has no rules of its own.
- Private notes are never read: the Person story is always asked for without them.
- Output: exactly one JSON object on stdout, UTF-8. ``{"ok": true, "command": ...}`` or
  ``{"ok": false, "error": CODE, "message": ...}``. Exit codes: 0 ok, 1 refused (``invalid``,
  ``not_found``, ``no_copy``), 2 bad usage (``usage``), 3 door off (``door_off``).
- No other module of the app imports this one.
"""

import argparse
import datetime as _dt
import json
import sqlite3
import sys
from pathlib import Path

from . import calendar, care, db, lists, money, paths, people, schema, search, settings, story, text

EXIT = {"invalid": 1, "not_found": 1, "no_copy": 1, "usage": 2, "door_off": 3}
DOOR_OFF = ("The Hermes door is off for this church copy. The pastor can turn it on in Church Manager: "
            "Settings > Hermes door > On.")
COUNTED = ("person", "family", "calendar_item", "offering", "expense")  # tables in the status counts
LISTS = ("status", "fund", "spending_category")
MAX_SEARCH = 100
MAX_DAYS = 366
_INTERNAL = ("name_folded",)  # columns only the app needs (search keys)


class AgentError(Exception):
    """A refusal: ``code`` is a key of ``EXIT``, ``message`` one plain sentence."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


class _HelpAsked(Exception):
    """``--help`` was given. The help text goes out inside the JSON answer."""


class _Parser(argparse.ArgumentParser):
    """An argument parser whose usage errors and help come out as JSON too."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("allow_abbrev", False)
        if sys.version_info >= (3, 14):
            kwargs.setdefault("color", False)  # no terminal colour codes inside the help text
        super().__init__(*args, **kwargs)

    def error(self, message):
        raise AgentError("usage", f"{message[:1].upper()}{message[1:]}. Run with --help to see the commands.")

    def print_help(self, file=None):
        raise _HelpAsked(self.format_help())


# ---------------------------------------------------------------- opening the church copy

def connect_ro(db_path):
    """Open ``church.db`` read-only, the way the Handover reads it (SQLite ``mode=ro``): every write
    fails with ``sqlite3.OperationalError``. Rows are ``sqlite3.Row``. A OneDrive path, a missing file
    or a file that is not a Church Manager database of this version raises ``AgentError`` no_copy."""
    try:
        path = paths.check_not_onedrive(db_path)
    except paths.CopyPathError as exc:
        raise AgentError("no_copy", str(exc)) from exc
    if not path.is_file():
        raise AgentError("no_copy", f"There is no church copy here: {path} is missing.")
    conn = sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.DatabaseError as exc:
        conn.close()
        raise AgentError("no_copy", f"{path} is not a Church Manager database ({exc}).") from exc
    if version != schema.SCHEMA_VERSION:
        conn.close()
        raise AgentError("no_copy", f"{path} has database version {version}; "
                                    f"this app needs version {schema.SCHEMA_VERSION}.")
    return conn


def _find_copy(args):
    """``(copy folder, copies root)`` found the same way as ``app.py``."""
    try:
        copy, root = paths.resolve(args.copy, args.copies_root)
    except paths.CopyPathError as exc:
        raise AgentError("no_copy", str(exc)) from exc
    if copy is None:
        raise AgentError("no_copy", "No church copy was found. Give its folder with --copy FOLDER.")
    return copy, root


# ---------------------------------------------------------------- small helpers

def _dict(row):
    """A row as a plain dict without internal columns. ``None`` stays ``None``."""
    return None if row is None else {k: row[k] for k in row.keys() if k not in _INTERNAL}


def _dicts(rows):
    return [_dict(r) for r in rows]


def _id(raw, what):
    try:
        return text.to_id(raw, what)
    except ValueError as exc:
        # "No Person with that id." (a number too big for SQLite) is a missing id, as on the web pages
        raise AgentError("not_found" if str(exc).startswith("No ") else "invalid", str(exc)) from exc


def _whole(raw, what, low, high):
    value = raw.strip()
    number = text.digits_to_int(value) if value.isascii() and value.isdigit() else None
    if number is None or not low <= number <= high:
        raise AgentError("invalid", f"{what} must be a whole number from {low} to {high}.")
    return number


def _day(raw, what, default):
    return default if raw is None else _dt.date.fromisoformat(text.check_date(raw, what))


# ---------------------------------------------------------------- read commands

def cmd_status(conn, args, copy, root):
    checks = [r[0] for r in conn.execute("PRAGMA quick_check")]
    return {
        "church_name": settings.get_setting(conn, "church_name"),
        "copy_folder": str(copy),
        "copies_root": str(root),
        "schema_version": conn.execute("PRAGMA user_version").fetchone()[0],
        "hermes_door": settings.get_setting(conn, settings.HERMES_DOOR),
        "counts": {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in COUNTED},
        "quick_check": "\n".join(checks),
    }


def cmd_search(conn, args, copy, root):
    limit = _whole(args.limit, "Limit", 1, MAX_SEARCH)
    words = " ".join(args.words)
    rows = search.search_persons(conn, words, limit)
    return {"words": words, "limit": limit,
            "results": [{"id": r["id"], "full_name": r["full_name"], "status_name": r["status_name"]}
                        for r in rows]}


def cmd_person(conn, args, copy, root):
    pid = _id(args.id, "Person")
    row = people.get_person(conn, pid)
    if row is None:
        raise AgentError("not_found", f"No Person with id {pid}.")
    person = {k: row[k] for k in ("id", "full_name", "gender", "birth_date", "phone")}
    person["address"] = people.person_address(conn, pid)  # the Family's address when it has one
    person["own_address"] = row["address"]
    person["note"] = row["note"]
    return {
        "person": person,
        "status": _dict(people.current_status(conn, pid)),
        "family": _dict(people.current_family(conn, pid)),
        "ministries": _dicts(people.current_ministries(conn, pid)),
        "story": story.person_story(conn, pid, include_private=False),
    }


def cmd_family(conn, args, copy, root):
    fid = _id(args.id, "Family")
    row = people.get_family(conn, fid)
    if row is None:
        raise AgentError("not_found", f"No Family with id {fid}.")
    return {
        "family": {"id": row["id"], "name": row["name"], "address": row["address"]},
        "chi_phai": _dict(people.current_chi_phai(conn, fid)),
        "members": _dicts(people.family_members(conn, fid)),
    }


def cmd_calendar(conn, args, copy, root):
    start = _day(args.date_from, "From date", _dt.date.today())
    week_end = min(start, _dt.date.max - _dt.timedelta(days=6)) + _dt.timedelta(days=6)  # 9999-12-31 at most
    end = _day(args.date_to, "To date", week_end)
    if (end - start).days >= MAX_DAYS:
        raise AgentError("invalid", f"Ask for at most {MAX_DAYS} days at a time (--from to --to).")
    items = calendar.items_between(conn, start, end)  # refuses an end before the start
    return {"from": start.isoformat(), "to": end.isoformat(), "items": _dicts(items)}


def cmd_money(conn, args, copy, root):
    today = _dt.date.today()
    year = today.year if args.year is None else calendar.check_year(args.year)
    month = today.month if args.month is None else args.month
    totals = money.month_totals(conn, year, month)  # refuses a month that is not 1 to 12
    out = {"year": year, "month": int(str(month).strip()), **totals}
    for key in ("offerings", "expenses", "balance"):
        out[f"{key}_text"] = money.format_vnd(totals[key])
    return out


def cmd_care_due(conn, args, copy, root):
    return {"reminder_months": care.reminder_months(conn), "people": care.needs_visit(conn)}


def cmd_lists(conn, args, copy, root):
    out = {name: [{"id": r["id"], "name": r["name"], "code": r["code"]} for r in lists.get_list(conn, name)]
           for name in LISTS}
    out["calendar_kind"] = list(schema.CALENDAR_KINDS)
    return out


# ---------------------------------------------------------------- command line

def build_parser():
    common = _Parser(add_help=False)
    common.add_argument("--copy", metavar="FOLDER", help="the church copy folder (outside OneDrive)")
    common.add_argument("--copies-root", metavar="FOLDER", help="the folder that holds the church copies")
    parser = _Parser(prog="python -m churchmgr.agent",
                     description="Church Manager for the Hermes helper. Works only when Settings > Hermes door "
                                 "is On. Prints one JSON object.")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    def add(name, run, words):
        p = sub.add_parser(name, parents=[common], help=words, description=words)
        p.set_defaults(run=run)
        return p

    add("status", cmd_status, "Church name, copy folder, row counts and a quick database check.")
    p = add("search", cmd_search, "Find People by name, with or without Vietnamese accents.")
    p.add_argument("words", nargs="+", help="words of the name")
    p.add_argument("--limit", default="20", metavar="N", help=f"at most N results, 1 to {MAX_SEARCH} (default 20)")
    p = add("person", cmd_person, "One Person: details, Status, Family, Ministries and story. "
                                  "Never Private notes.")
    p.add_argument("id", help="the Person id")
    p = add("family", cmd_family, "One Family: name, address, Chi phái and the people in it now.")
    p.add_argument("id", help="the Family id")
    p = add("calendar", cmd_calendar, f"Calendar items from --from to --to (at most {MAX_DAYS} days).")
    p.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="first day (default today)")
    p.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="last day (default 6 days after --from)")
    p = add("money", cmd_money, "Offerings, Expenses and balance of one month, in whole dong.")
    p.add_argument("--year", metavar="YYYY", help="the year (default this year)")
    p.add_argument("--month", metavar="M", help="the month, 1 to 12 (default this month)")
    add("care-due", cmd_care_due, "People who need a visit: no Visit within the care reminder time.")
    add("lists", cmd_lists, "Ids and names of the Status, Fund and Spending category lists, "
                            "and the Calendar item kinds.")
    return parser


def run(argv=None):
    """Do one command and return its answer dict. Raises ``AgentError`` for a refusal."""
    args = build_parser().parse_args(argv)
    copy, root = _find_copy(args)
    conn = connect_ro(copy / db.DB_NAME)
    try:
        if not settings.hermes_door_on(conn):  # the only read before the door is open
            raise AgentError("door_off", DOOR_OFF)
        result = args.run(conn, args, copy, root)
    except ValueError as exc:
        raise AgentError("invalid", str(exc)) from exc
    except sqlite3.Error as exc:
        raise AgentError("no_copy", f"The church copy could not be read ({exc}).") from exc
    finally:
        conn.close()
    return {"ok": True, "command": args.command, **result}


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        out, code = run(argv), 0
    except _HelpAsked as exc:
        out, code = {"ok": True, "command": "help", "help": str(exc)}, 0
    except AgentError as exc:
        out, code = {"ok": False, "error": exc.code, "message": exc.message}, EXIT[exc.code]
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
