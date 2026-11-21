"""The Service role Roster: Service roles, Rotations, Skipped dates, and the links of a Person (or a
Ministry) to a Service role in one Service.

- A link is history (rule 4): a change closes the open row (``end_date``) and opens a new one, so the
  Roster can show a swap (the old name struck, then the new one). A row is never overwritten or deleted.
- ``weekday`` is Python's ``date.weekday()``: 0 Monday .. 3 Thursday .. 6 Sunday.
- Service role names are data: shown as stored, never translated.
- Errors are ``TextError`` with keys of the ``calendar`` section of ``i18n.py`` (prefix ``calendar.roster_``).
"""

import datetime as _dt
import re

from . import settings, text
from .calendar import _require_item
from .db import transaction
from .i18n import TextError

DONE_BY = ("person", "ministry")
SAME_PERSON_RULES = ("service", "week", "any")
SAME_PERSON_SETTING = "roster_same_person"
SAME_PERSON_DEFAULT = "service"
MAX_FILL_DAYS = 366
MAX_EVERY = 8  # every 1st to every 8th Service (schema CHECK)
_KEEP = object()  # "do not change this field" in update_role
_MONTH = re.compile(r"([0-9]{4})-([0-9]{2})")


# ---------------------------------------------------------------- checks

def _whole(value, low, high, key):
    """An int from ``low`` to ``high`` (an int or its digit text), else ``TextError(key)``."""
    if isinstance(value, str) and value.strip().isascii() and value.strip().isdigit():
        value = text.digits_to_int(value.strip())
    if type(value) is not int or not low <= value <= high:
        raise TextError(key)
    return value


def _on_off(value, label):
    if value not in (True, False, 0, 1):
        raise TextError("calendar.roster_err_on_off", label=label)
    return 1 if value else 0


def _month(value):
    """``YYYY-MM`` text (year 1900 to 9999), or ``None`` for no month."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    found = _MONTH.fullmatch(value.strip()) if isinstance(value, str) else None
    if found is None or not 1 <= int(found.group(2)) <= 12:
        raise TextError("calendar.err_month_form")
    if not 1900 <= int(found.group(1)) <= 9999:
        raise TextError("calendar.err_month_years")
    return found.group(0)


def _day(day):
    return text.today_text() if day is None else text.check_date(day, "calendar.roster_day")


def _item_date(item):
    return _dt.date.fromisoformat(item["starts_at"][:10])


def _require_role(conn, role_id):
    rid = text.to_id(role_id, "calendar.roster_role")
    row = conn.execute("SELECT * FROM service_role WHERE id = ?", (rid,)).fetchone()
    if row is None:
        raise TextError("calendar.roster_err_no_role", id=rid)
    return row


def _person(conn, person_id):
    pid = text.to_id(person_id, "calendar.person")
    if conn.execute("SELECT 1 FROM person WHERE id = ?", (pid,)).fetchone() is None:
        raise TextError("calendar.err_no_person", id=pid)
    return pid


def _ministry(conn, ministry_id):
    mid = text.to_id(ministry_id, "calendar.roster_ministry")
    if conn.execute("SELECT 1 FROM list_item WHERE id = ? AND list_name = 'ministry'", (mid,)).fetchone() is None:
        raise TextError("calendar.roster_err_no_ministry", id=mid)
    return mid


def _check_name_free(conn, name, except_id=None):
    """Refuse a name another Service role has (hidden ones too), upper or lower case aside."""
    key = name.casefold()
    for row in conn.execute("SELECT id, name FROM service_role"):
        if row["id"] != except_id and text.nfc(row["name"]).casefold() == key:
            raise TextError("calendar.roster_err_name_taken", name=name)


# ---------------------------------------------------------------- Service roles

def add_role(conn, name, weekday, done_by, every=1, month_start=False, month_start_from=None):
    """Add a Service role at the end of the list and return its id.

    ``done_by``: ``person`` or ``ministry`` (it never changes). ``every``: every 1st to 8th Service of that
    weekday. ``month_start``: the first Service of a month starts a round; ``month_start_from``
    (``YYYY-MM`` or ``None``) is the month Rotation place 1 starts.
    """
    name = text.clean_name(name, "calendar.roster_role_name")
    if done_by not in DONE_BY:
        raise TextError("calendar.roster_err_done_by")
    values = (name, _whole(weekday, 0, 6, "calendar.roster_err_weekday"), done_by,
              _whole(every, 1, MAX_EVERY, "calendar.roster_err_every"),
              _on_off(month_start, "calendar.roster_month_start"), _month(month_start_from))
    with transaction(conn):
        _check_name_free(conn, name)
        last = conn.execute("SELECT COALESCE(MAX(sort_order), 0) FROM service_role").fetchone()[0]
        cur = conn.execute(
            "INSERT INTO service_role (name, weekday, done_by, every, month_start, month_start_from, sort_order) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)", (*values, last + 1))
    return cur.lastrowid


def update_role(conn, role_id, *, name=_KEEP, weekday=_KEEP, every=_KEEP, month_start=_KEEP,
                month_start_from=_KEEP):
    """Change a Service role. ``done_by`` never changes. The weekday changes only while the role has no
    link on any Service (the Roster keeps its history)."""
    with transaction(conn):
        role = _require_role(conn, role_id)
        changes = {}
        if name is not _KEEP:
            changes["name"] = text.clean_name(name, "calendar.roster_role_name")
            _check_name_free(conn, changes["name"], role["id"])
        if weekday is not _KEEP:
            day = _whole(weekday, 0, 6, "calendar.roster_err_weekday")
            if day != role["weekday"]:
                if conn.execute("SELECT 1 FROM service_role_link WHERE service_role_id = ?", (role["id"],)).fetchone():
                    raise TextError("calendar.roster_err_weekday_kept", name=role["name"])
                changes["weekday"] = day
        if every is not _KEEP:
            changes["every"] = _whole(every, 1, MAX_EVERY, "calendar.roster_err_every")
        if month_start is not _KEEP:
            changes["month_start"] = _on_off(month_start, "calendar.roster_month_start")
        if month_start_from is not _KEEP:
            changes["month_start_from"] = _month(month_start_from)
        if changes:
            sets = ", ".join(f"{col} = ?" for col in changes)
            conn.execute(f"UPDATE service_role SET {sets} WHERE id = ?", [*changes.values(), role["id"]])


def set_role_active(conn, role_id, active):
    """Show (``True``) or hide (``False``) a Service role. Nothing is deleted."""
    value = _on_off(active, "calendar.roster_active")
    with transaction(conn):
        role = _require_role(conn, role_id)
        conn.execute("UPDATE service_role SET active = ? WHERE id = ?", (value, role["id"]))


def get_role(conn, role_id):
    """One Service role row, or ``None``."""
    return conn.execute("SELECT * FROM service_role WHERE id = ?",
                        (text.to_id(role_id, "calendar.roster_role"),)).fetchone()


def roles(conn, include_hidden=False):
    """The Service roles by weekday (Monday first), then sort order. Hidden ones only if ``include_hidden``."""
    where = "" if include_hidden else " WHERE active = 1"
    return conn.execute(f"SELECT * FROM service_role{where} ORDER BY weekday, sort_order, id").fetchall()


# ---------------------------------------------------------------- Rotation

def rotation(conn, role_id):
    """The Rotation of a Service role: rows ``(position, person_id, ministry_id, name)`` by position."""
    return conn.execute(
        "SELECT rp.position, rp.person_id, rp.ministry_id, COALESCE(p.full_name, li.name) AS name "
        "FROM rotation_place rp LEFT JOIN person p ON p.id = rp.person_id "
        "LEFT JOIN list_item li ON li.id = rp.ministry_id "
        "WHERE rp.service_role_id = ? ORDER BY rp.position",
        (text.to_id(role_id, "calendar.roster_role"),),
    ).fetchall()


def set_rotation(conn, role_id, ids):
    """Replace the whole Rotation of a Service role with ``ids``, in that order: Person ids for a role done
    by a Person, Ministry (list item) ids for a role done by a Ministry. No one twice; an empty list
    empties it."""
    if isinstance(ids, str):
        raise TypeError("ids must be a list of ids, not text")
    with transaction(conn):
        role = _require_role(conn, role_id)
        check = _person if role["done_by"] == "person" else _ministry
        clean = [check(conn, value) for value in ids]
        if len(set(clean)) != len(clean):
            raise TextError("calendar.roster_err_twice")
        column = "person_id" if role["done_by"] == "person" else "ministry_id"
        conn.execute("DELETE FROM rotation_place WHERE service_role_id = ?", (role["id"],))
        conn.executemany(f"INSERT INTO rotation_place (service_role_id, position, {column}) VALUES (?, ?, ?)",
                         [(role["id"], k, value) for k, value in enumerate(clean, start=1)])


# ---------------------------------------------------------------- Skipped dates

def add_skipped_date(conn, date, reason):
    """Make ``date`` a Skipped date with ``reason``. A date that is already one gets the new reason."""
    day = text.check_date(date, "calendar.roster_skipped_date")
    why = text.clean_name(reason, "calendar.roster_reason")
    with transaction(conn):
        conn.execute("INSERT INTO skipped_date (date, reason) VALUES (?, ?) "
                     "ON CONFLICT (date) DO UPDATE SET reason = excluded.reason", (day, why))


def remove_skipped_date(conn, date):
    """Make ``date`` a normal date again. ``True`` if it was a Skipped date."""
    day = text.check_date(date, "calendar.roster_skipped_date")
    with transaction(conn):
        return conn.execute("DELETE FROM skipped_date WHERE date = ?", (day,)).rowcount == 1


def skipped_dates(conn, start, end):
    """Skipped dates from ``start`` to ``end`` (both included): rows ``(date, reason)`` by date."""
    first = text.check_date(start, "calendar.start_date")
    last = text.check_date(end, "calendar.end_date")
    if last < first:
        raise TextError("calendar.err_end_date_before")
    return conn.execute("SELECT date, reason FROM skipped_date WHERE date >= ? AND date <= ? ORDER BY date",
                        (first, last)).fetchall()


def skipped_reason(conn, date):
    """The reason of a Skipped date, or ``None`` when ``date`` is not one."""
    row = conn.execute("SELECT reason FROM skipped_date WHERE date = ?",
                       (text.check_date(date, "calendar.roster_skipped_date"),)).fetchone()
    return None if row is None else row["reason"]


# ---------------------------------------------------------------- links (rule 4: never overwritten)

def _close_open(conn, item_id, role_id, day):
    """Close the open link of a Service role in one Service on ``day``; return it (``None``: none open).
    ``day`` may not be before the last date of that Service role's history: the history stays in order."""
    rows = conn.execute("SELECT * FROM service_role_link WHERE calendar_item_id = ? AND service_role_id = ?",
                        (item_id, role_id)).fetchall()
    latest = max((r["end_date"] or r["start_date"] for r in rows), default=None)
    if latest is not None and day < latest:  # dates: the Vietnamese text shows them dd/mm/yyyy
        raise TextError("calendar.roster_err_day_before", day=_dt.date.fromisoformat(day),
                        latest=_dt.date.fromisoformat(latest))
    open_row = next((r for r in rows if r["end_date"] is None), None)
    if open_row is not None:
        conn.execute("UPDATE service_role_link SET end_date = ? WHERE id = ?", (day, open_row["id"]))
    return open_row


def set_link(conn, item_id, role_id, person_id=None, ministry_id=None, day=None):
    """Put a Person (a role done by a Person) or a Ministry (a role done by a Ministry) in a Service role of
    one Service from ``day`` (default today). Rule 4: the open link is closed on ``day`` and a new one opens
    on ``day``. The same value as the open link changes nothing: ``False``. ``True`` when saved.

    Refused (``TextError``): the Calendar item is not a Service, the role is hidden or is for another
    weekday, a Person for a Ministry role (or the other way), an unknown Person or Ministry, a ``day``
    before the last change of this Service role in this Service.
    """
    when = _day(day)
    with transaction(conn):
        item = _require_item(conn, item_id)
        role = _require_role(conn, role_id)
        if item["kind"] != "Service":
            raise TextError("calendar.roster_err_not_service")
        if not role["active"]:
            raise TextError("calendar.roster_err_role_hidden", name=role["name"])
        if _item_date(item).weekday() != role["weekday"]:
            raise TextError("calendar.roster_err_wrong_day", name=role["name"])
        if role["done_by"] == "person":
            if person_id in (None, "") or ministry_id not in (None, ""):
                raise TextError("calendar.roster_err_need_person", name=role["name"])
            value = (_person(conn, person_id), None)
        else:
            if ministry_id in (None, "") or person_id not in (None, ""):
                raise TextError("calendar.roster_err_need_ministry", name=role["name"])
            value = (None, _ministry(conn, ministry_id))
        held = open_value(conn, item["id"], role["id"])
        if held is not None and (held["person_id"], held["ministry_id"]) == value:
            return False
        _close_open(conn, item["id"], role["id"], when)
        conn.execute("INSERT INTO service_role_link (calendar_item_id, service_role_id, person_id, ministry_id, "
                     "start_date) VALUES (?, ?, ?, ?, ?)", (item["id"], role["id"], *value, when))
    return True


def clear_link(conn, item_id, role_id, day=None):
    """Close the open link of a Service role in one Service on ``day`` (default today), with no new one: the
    old name stays in the history, struck. ``False`` when nothing was open."""
    when = _day(day)
    with transaction(conn):
        item = _require_item(conn, item_id)
        role = _require_role(conn, role_id)
        if open_value(conn, item["id"], role["id"]) is None:
            return False
        _close_open(conn, item["id"], role["id"], when)
    return True


def item_links(conn, item_id):
    """Every link of one Calendar item, open and closed: rows ``(id, service_role_id, role_name, done_by,
    person_id, ministry_id, name, start_date, end_date)``, by Service role order, then id (oldest first)."""
    return conn.execute(
        "SELECT sl.id, sl.service_role_id, sr.name AS role_name, sr.done_by, sl.person_id, sl.ministry_id, "
        "COALESCE(p.full_name, li.name) AS name, sl.start_date, sl.end_date "
        "FROM service_role_link sl JOIN service_role sr ON sr.id = sl.service_role_id "
        "LEFT JOIN person p ON p.id = sl.person_id LEFT JOIN list_item li ON li.id = sl.ministry_id "
        "WHERE sl.calendar_item_id = ? ORDER BY sr.weekday, sr.sort_order, sr.id, sl.id",
        (text.to_id(item_id, "calendar.item"),),
    ).fetchall()


def open_value(conn, item_id, role_id):
    """The open link of a Service role in one Service: a row ``(id, person_id, ministry_id, name,
    start_date)``, or ``None`` when no one holds it."""
    return conn.execute(
        "SELECT sl.id, sl.person_id, sl.ministry_id, COALESCE(p.full_name, li.name) AS name, sl.start_date "
        "FROM service_role_link sl LEFT JOIN person p ON p.id = sl.person_id "
        "LEFT JOIN list_item li ON li.id = sl.ministry_id "
        "WHERE sl.calendar_item_id = ? AND sl.service_role_id = ? AND sl.end_date IS NULL",
        (text.to_id(item_id, "calendar.item"), text.to_id(role_id, "calendar.roster_role")),
    ).fetchone()


# ---------------------------------------------------------------- same-person rule

def same_person_rule(conn):
    """Where one Person may hold only one Service role: ``service`` (one Service), ``week`` (one ISO week)
    or ``any`` (no limit). No setting, or a bad one, is ``SAME_PERSON_DEFAULT``."""
    value = settings.get_setting(conn, SAME_PERSON_SETTING)
    return value if value in SAME_PERSON_RULES else SAME_PERSON_DEFAULT


def _check_rule(rule):
    if rule not in SAME_PERSON_RULES:
        raise TextError("calendar.roster_err_rule")
    return rule


def set_same_person_rule(conn, rule):
    """Save the same-person rule: one of ``SAME_PERSON_RULES``."""
    _check_rule(rule)
    with transaction(conn):
        settings.set_setting(conn, SAME_PERSON_SETTING, rule)


def conflicts(conn, item_id, role_id, person_id, rule=None, extra=()):
    """Where ``person_id`` holds ANOTHER Service role done by a Person, next to ``role_id`` in Calendar item
    ``item_id``: a list of ``(role name, date YYYY-MM-DD)`` by date, then Service role order.

    ``rule`` (default :func:`same_person_rule`): ``service`` looks at the same Calendar item, ``week`` at
    every Service of the same ISO week (Monday to Sunday), ``any`` nowhere (always an empty list). Open
    links count, and ``extra``: proposed ``(item_id, role_id, person_id)`` not saved yet. The slot
    ``(item_id, role_id)`` itself is left out. A role done by a Ministry has no conflicts. Reads only.
    """
    rule = _check_rule(same_person_rule(conn) if rule is None else rule)
    item = _require_item(conn, item_id)
    role = _require_role(conn, role_id)
    pid = text.to_id(person_id, "calendar.person")
    if rule == "any" or role["done_by"] != "person":
        return []
    if rule == "service":
        scope = {item["id"]: item["starts_at"][:10]}
    else:
        monday = _item_date(item) - _dt.timedelta(days=_item_date(item).weekday())
        scope = {r["id"]: r["starts_at"][:10] for r in conn.execute(
            "SELECT id, starts_at FROM calendar_item WHERE kind = 'Service' AND starts_at >= ? AND starts_at <= ?",
            (f"{monday} 00:00", f"{monday + _dt.timedelta(days=6)} 23:59"))}  # starts_at is YYYY-MM-DD HH:MM
        scope[item["id"]] = item["starts_at"][:10]
    marks = ", ".join("?" * len(scope))
    slots = {(r[0], r[1]) for r in conn.execute(
        "SELECT calendar_item_id, service_role_id FROM service_role_link "
        f"WHERE person_id = ? AND end_date IS NULL AND calendar_item_id IN ({marks})", (pid, *scope))}
    for other_item, other_role, other_person in extra:
        if other_person is not None and text.to_id(other_person, "calendar.person") == pid:
            slot = (text.to_id(other_item, "calendar.item"), text.to_id(other_role, "calendar.roster_role"))
            if slot[0] in scope:
                slots.add(slot)
    slots.discard((item["id"], role["id"]))
    by_id = {r["id"]: r for r in roles(conn, include_hidden=True)}
    order = {rid: k for k, rid in enumerate(by_id)}
    found = sorted((scope[i], order[r], by_id[r]["name"]) for i, r in slots
                   if r in by_id and by_id[r]["done_by"] == "person")
    return [(name, day) for day, _order, name in found]


# ---------------------------------------------------------------- Auto-fill (decision D5)

def _fill_range(from_date, to_date):
    """The range of an Auto-fill as ``YYYY-MM-DD`` texts: ``to`` not before ``from``, at most
    ``MAX_FILL_DAYS`` days after it."""
    first = text.check_date(from_date, "calendar.start_date")
    last = text.check_date(to_date, "calendar.end_date")
    if last < first:
        raise TextError("calendar.roster_err_fill_before")
    if (_dt.date.fromisoformat(last) - _dt.date.fromisoformat(first)).days > MAX_FILL_DAYS:
        raise TextError("calendar.roster_err_fill_long", max=MAX_FILL_DAYS)
    return first, last


def _months(start, day):
    """Months from ``start`` (``YYYY-MM``) to the month of ``day`` (``YYYY-MM-DD``); negative when before."""
    return (int(day[:4]) - int(start[:4])) * 12 + int(day[5:7]) - int(start[5:7])


def _plan_role(conn, role, services, first, rule, plan, proposed):
    """D5 steps 1 to 4 for one Service role with a non-empty Rotation. Adds to ``plan`` and to
    ``proposed`` (the ``(item_id, role_id, person_id)`` not saved yet, for the conflict check)."""
    by_person = role["done_by"] == "person"
    places = [r["person_id"] if by_person else r["ministry_id"] for r in rotation(conn, role["id"])]
    n = len(places)
    # 1. The role's Services up to `to` (already without the Skipped dates): (item id, date).
    seq = [(iid, day) for iid, day, weekday in services if weekday == role["weekday"]]
    held, holder = set(), {}  # held: any link row, open or closed; holder: the open value
    for r in conn.execute("SELECT calendar_item_id, person_id, ministry_id, end_date FROM service_role_link "
                          "WHERE service_role_id = ?", (role["id"],)):
        held.add(r["calendar_item_id"])
        if r["end_date"] is None:
            holder[r["calendar_item_id"]] = r["person_id"] if by_person else r["ministry_id"]
    before = [i for i, (_iid, day) in enumerate(seq) if day < first]
    inside = [i for i, (_iid, day) in enumerate(seq) if day >= first]
    if not inside:
        return
    # 2. every-step: count from the last Service before `from` with an open link, else from the first one in range.
    linked = [i for i in before if seq[i][0] in holder]
    anchor = linked[-1] if linked else inside[0]
    beat = [i for i in range(len(seq)) if (i - anchor) % role["every"] == 0]
    steps = [i for i in beat if seq[i][1] >= first]
    # 3. The queue starts right after the last holder (in the Rotation) before `from`.
    queue = list(places)
    last_holder = next((holder[seq[i][0]] for i in reversed(before) if holder.get(seq[i][0]) in places), None)
    if last_holder is not None:
        k = places.index(last_holder) + 1
        queue = places[k:] + places[:k]
    # The first step Service of each month, counted over ALL the role's Services (also before `from`), so a
    # range that starts mid-month does not give that month's starter to a later Service.
    month_first = {}
    for i in beat:
        month_first.setdefault(seq[i][1][:7], i)
    firsts = set(month_first.values())
    start_month = role["month_start_from"] or first[:7]

    def starter(i):
        return places[_months(start_month, seq[i][1]) % n]

    def free(item_id, who, memo):
        """No conflicts for ``who`` in this slot (a role done by a Ministry has none). ``memo``: one slot."""
        if not by_person:
            return True
        if who not in memo:
            memo[who] = not conflicts(conn, item_id, role["id"], who, rule, proposed)
        return memo[who]

    # 4. Each step Service in date order.
    for at, i in enumerate(steps):
        item_id = seq[i][0]
        if item_id in held:  # never changed; its holder had a turn
            if holder.get(item_id) in queue:
                queue.remove(holder[item_id])
                queue.append(holder[item_id])
            continue
        memo = {}
        pick = None
        if role["month_start"] and i in firsts and free(item_id, starter(i), memo):
            pick = starter(i)
        if pick is None:
            reserved = set()
            if role["month_start"]:  # the starters of the month-first Services among the next n-1 step Services
                reserved = {starter(j) for j in steps[at + 1:at + n] if j in firsts}
            pick = next((who for who in queue if who not in reserved and free(item_id, who, memo)), None)
            if pick is None:
                pick = next((who for who in queue if free(item_id, who, memo)), None)
        if pick is None:
            plan["nobody_free"].append((item_id, role["id"]))
            continue
        queue.remove(pick)
        queue.append(pick)
        if by_person:
            plan["proposals"].append((item_id, role["id"], pick, None))
            proposed.append((item_id, role["id"], pick))
        else:
            plan["proposals"].append((item_id, role["id"], None, pick))


def fill_plan(conn, from_date, to_date):
    """The Auto-fill of the empty Service roles from ``from_date`` to ``to_date`` (both included, at most
    ``MAX_FILL_DAYS`` days apart), from each Rotation. Reads only: nothing is saved.

    Returns ``{"proposals": [(item_id, role_id, person_id, ministry_id)], "nobody_free": [(item_id, role_id)]}``,
    by Service role order (:func:`roles`), then date. For each shown Service role with a Rotation of n places:

    - Its Services: Services on the role's weekday up to ``to_date``, by start, without the Skipped dates.
    - ``every``: the step Services are every ``every``-th one, counted from the last Service before
      ``from_date`` with an open link of this role, else from the first Service of the range.
    - The queue is the Rotation, started right after the last holder before ``from_date``.
    - A step Service with any link of this role (open or closed) is held: never changed; its open holder goes
      to the end of the queue. Else, with ``month_start``, the first step Service of a month (counted over all
      the role's Services, also those before ``from_date``) gets the starter:
      Rotation place ``k % n``, k = months from ``month_start_from`` (none: the month of ``from_date``). Else
      (or when the same-person rule refuses the starter) the first one in the queue who is not kept for a
      coming month start (the next n-1 step Services) and has no :func:`conflicts` with
      :func:`same_person_rule` (saved links and the proposals so far, all roles). Nobody: the first one with
      no conflicts. Still nobody: the slot goes to ``nobody_free``. The one picked goes to the end of the queue.
    - A role done by a Ministry has no conflict check.
    """
    first, last = _fill_range(from_date, to_date)
    skipped = {r["date"] for r in conn.execute("SELECT date FROM skipped_date WHERE date <= ?", (last,))}
    services = []
    for r in conn.execute("SELECT id, starts_at FROM calendar_item WHERE kind = 'Service' "
                          "AND substr(starts_at, 1, 10) <= ? ORDER BY starts_at, id", (last,)):
        day = r["starts_at"][:10]
        if day not in skipped:
            services.append((r["id"], day, _dt.date.fromisoformat(day).weekday()))
    rule = same_person_rule(conn)
    plan = {"proposals": [], "nobody_free": []}
    proposed = []
    for role in roles(conn):
        if conn.execute("SELECT 1 FROM rotation_place WHERE service_role_id = ?", (role["id"],)).fetchone():
            _plan_role(conn, role, services, first, rule, plan, proposed)
    return plan


def save_fill(conn, from_date, to_date, day=None):
    """Make the :func:`fill_plan` again and save every proposal with :func:`set_link` from ``day`` (default
    today), all in ONE transaction: a failure saves nothing. Returns the number of links saved."""
    when = _day(day)
    saved = 0
    with transaction(conn):
        for item_id, role_id, person_id, ministry_id in fill_plan(conn, from_date, to_date)["proposals"]:
            if set_link(conn, item_id, role_id, person_id, ministry_id, day=when):
                saved += 1
    return saved


# ---------------------------------------------------------------- the Roster page (decision D6; reads only)

def _plus_days(day, n):
    """``day`` plus ``n`` days, or ``None`` after 9999-12-31 (Python has no such date)."""
    try:
        return day + _dt.timedelta(days=n)
    except OverflowError:
        return None


def roster_weeks(conn, first_date, last_date):
    """The Roster from the week of ``first_date`` to the week of ``last_date``: one entry per ISO week
    (Monday to Sunday), oldest first. Reads only.

    A week is ``{"monday": date, "days": {weekday: day}}``, with one ``day`` for each weekday that has a
    shown Service role (a day after 9999-12-31 is left out). A day is a dict:

    - ``date``: its ``datetime.date``.
    - ``service``: the id of its first Service (by start, then id), or ``None``; ``others``: rows
      ``(id, starts_at)`` of the other Services of that date, in the same order.
    - ``skipped``: the reason of a Skipped date, or ``None``.
    - ``month_first``: ``True`` when ``service`` is the first Service of its month on that weekday, not
      counting the Services on a Skipped date (the Service where a ``month_start`` role starts a round).
    - ``links``: ``{service_role_id: [rows]}`` of ``service``, every link open or closed, oldest first:
      ``(id, service_role_id, person_id, ministry_id, name, start_date, end_date)``.
    """
    first = _dt.date.fromisoformat(text.check_date(first_date, "calendar.start_date"))
    last = _dt.date.fromisoformat(text.check_date(last_date, "calendar.end_date"))
    if last < first:
        raise TextError("calendar.err_end_date_before")
    weekdays = sorted({r["weekday"] for r in roles(conn)})
    monday = first - _dt.timedelta(days=first.weekday())
    end = _plus_days(last, 6 - last.weekday()) or _dt.date.max
    since = monday.replace(day=1).isoformat()  # the month-first test needs the whole month
    until = end.isoformat()
    skipped = {r["date"]: r["reason"] for r in conn.execute(
        "SELECT date, reason FROM skipped_date WHERE date >= ? AND date <= ?", (since, until))}
    services = {}  # date text -> [(id, starts_at)] by start, then id
    for r in conn.execute("SELECT id, starts_at FROM calendar_item WHERE kind = 'Service' AND substr(starts_at, 1, 10) "
                          ">= ? AND substr(starts_at, 1, 10) <= ? ORDER BY starts_at, id", (since, until)):
        services.setdefault(r["starts_at"][:10], []).append((r["id"], r["starts_at"]))
    firsts, seen = set(), set()
    for day in sorted(services):
        place = (day[:7], _dt.date.fromisoformat(day).weekday())
        if day not in skipped and place not in seen:
            seen.add(place)
            firsts.add(day)
    links = {}  # calendar item id -> {role id: [rows]}
    for r in conn.execute(
            "SELECT sl.id, sl.calendar_item_id, sl.service_role_id, sl.person_id, sl.ministry_id, "
            "COALESCE(p.full_name, li.name) AS name, sl.start_date, sl.end_date FROM service_role_link sl "
            "JOIN calendar_item ci ON ci.id = sl.calendar_item_id LEFT JOIN person p ON p.id = sl.person_id "
            "LEFT JOIN list_item li ON li.id = sl.ministry_id WHERE substr(ci.starts_at, 1, 10) >= ? "
            "AND substr(ci.starts_at, 1, 10) <= ? ORDER BY sl.id", (monday.isoformat(), until)):
        links.setdefault(r["calendar_item_id"], {}).setdefault(r["service_role_id"], []).append(r)
    weeks = []
    while monday is not None and monday <= last:
        days = {}
        for weekday in weekdays:
            day = _plus_days(monday, weekday)
            if day is None:
                continue
            key = day.isoformat()
            held = services.get(key, [])
            service = held[0][0] if held else None
            days[weekday] = {"date": day, "service": service, "others": held[1:], "skipped": skipped.get(key),
                             "month_first": service is not None and key in firsts,
                             "links": links.get(service, {})}
        weeks.append({"monday": monday, "days": days})
        monday = _plus_days(monday, 7)
    return weeks
