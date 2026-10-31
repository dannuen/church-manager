"""Person story: everything the church copy knows about one Person, by date.

Private notes are added only with ``include_private=True`` (only the Person
page on screen asks for them; never a print, a Giving statement or a Handover).
"""

from . import text
from .care import _FOR_PERSON
from .money import format_vnd

# Order of events on the same day.
_KIND_ORDER = {k: i for i, k in enumerate((
    "status", "family_end", "family", "chi_phai", "truong_chi_phai_end", "truong_chi_phai",
    "ministry_end", "ministry", "calendar", "visit", "offering", "document", "private_note",
))}


def _event(day, kind, words, ref_id, **extra):
    return {"date": day, "kind": kind, "text": words, "ref_id": ref_id, **extra}


def _ends(rows, key):
    """End events of history rows, left out when the same line goes on that day
    (for example a new Family role in the same Family)."""
    starts = {(key(r), r["start_date"]) for r in rows}
    return [r for r in rows if r["end_date"] is not None and (key(r), r["end_date"]) not in starts]


def _stays(family_rows):
    """Join Family rows that follow each other in the same Family (a role change)
    into one stay: ``(family_id, name, start_date, end_date)``."""
    out = []
    for r in sorted(family_rows, key=lambda r: (r["start_date"], r["id"])):
        if out and out[-1][0] == r["family_id"] and out[-1][3] == r["start_date"]:
            out[-1] = (out[-1][0], out[-1][1], out[-1][2], r["end_date"])
        else:
            out.append((r["family_id"], r["name"], r["start_date"], r["end_date"]))
    return out


def person_story(conn, person_id, include_private=False):
    """A list of dated events, oldest first. Each event: date (``YYYY-MM-DD``),
    kind, text, ref_id (and end_date for history rows).

    Kinds: status, family, family_end, chi_phai, truong_chi_phai(_end),
    ministry(_end), calendar, visit, offering, document, private_note.
    """
    pid = text.to_id(person_id, "Person")
    if conn.execute("SELECT 1 FROM person WHERE id = ?", (pid,)).fetchone() is None:
        raise ValueError(f"No Person with id {pid}.")
    events = []

    for r in conn.execute(
        "SELECT ps.id, li.name, ps.start_date, ps.end_date FROM person_status ps "
        "JOIN list_item li ON li.id = ps.status_id WHERE ps.person_id = ?", (pid,)
    ):
        events.append(_event(r["start_date"], "status", f"Status: {r['name']}", r["id"], end_date=r["end_date"]))

    families = conn.execute(
        "SELECT fl.id, fl.family_id, f.name, fl.family_role, fl.start_date, fl.end_date "
        "FROM family_link fl JOIN family f ON f.id = fl.family_id WHERE fl.person_id = ?", (pid,)
    ).fetchall()
    for r in families:
        events.append(_event(r["start_date"], "family", f"Family: {r['name']} ({r['family_role']})", r["id"],
                             end_date=r["end_date"]))
    for r in _ends(families, lambda r: r["family_id"]):
        events.append(_event(r["end_date"], "family_end", f"Left Family {r['name']}", r["id"]))

    # Chi phái of each Family while the Person was in it.
    for family_id, family_name, stay_start, stay_end in _stays(families):
        for r in conn.execute(
            "SELECT cl.id, c.name, cl.start_date, cl.end_date FROM chi_phai_link cl "
            "JOIN chi_phai c ON c.id = cl.chi_phai_id WHERE cl.family_id = ? "
            "AND (? IS NULL OR cl.start_date < ?) AND (cl.end_date IS NULL OR cl.end_date > ?)",
            (family_id, stay_end, stay_end, stay_start),
        ):
            day = max(r["start_date"], stay_start)
            events.append(_event(day, "chi_phai", f"Chi phái: {r['name']} (Family {family_name})", r["id"],
                                 end_date=r["end_date"]))

    terms = conn.execute(
        "SELECT t.id, t.chi_phai_id, c.name, t.start_date, t.end_date FROM truong_chi_phai t "
        "JOIN chi_phai c ON c.id = t.chi_phai_id WHERE t.person_id = ?", (pid,)
    ).fetchall()
    for r in terms:
        events.append(_event(r["start_date"], "truong_chi_phai", f"Trưởng Chi phái of {r['name']}", r["id"],
                             end_date=r["end_date"]))
        if r["end_date"] is not None:
            events.append(_event(r["end_date"], "truong_chi_phai_end",
                                 f"No longer Trưởng Chi phái of {r['name']}", r["id"]))

    ministries = conn.execute(
        "SELECT ml.id, ml.ministry_id, li.name, ml.ministry_role, ml.start_date, ml.end_date "
        "FROM ministry_link ml JOIN list_item li ON li.id = ml.ministry_id WHERE ml.person_id = ?", (pid,)
    ).fetchall()
    for r in ministries:
        events.append(_event(r["start_date"], "ministry", f"Ministry: {r['name']} ({r['ministry_role']})",
                             r["id"], end_date=r["end_date"]))
    for r in _ends(ministries, lambda r: r["ministry_id"]):
        events.append(_event(r["end_date"], "ministry_end", f"Stopped serving in Ministry {r['name']}", r["id"]))

    for r in conn.execute(
        "SELECT ci.id, ci.kind, ci.title, ci.starts_at, cp.part FROM calendar_person cp "
        "JOIN calendar_item ci ON ci.id = cp.calendar_item_id WHERE cp.person_id = ?", (pid,)
    ):
        verb = "Serves at" if r["part"] == "serves" else "Joins"
        events.append(_event(r["starts_at"][:10], "calendar", f"{verb} {r['kind']}: {r['title']}", r["id"],
                             starts_at=r["starts_at"]))

    day_sql = "COALESCE(ci.visit_done_date, substr(ci.starts_at, 1, 10))"
    for r in conn.execute(
        f"SELECT ci.id, ci.visit_done, {day_sql} AS day, ci.care_note, COALESCE(p.full_name, f.name) AS who "
        "FROM calendar_item ci LEFT JOIN person p ON p.id = ci.visit_person_id "
        "LEFT JOIN family f ON f.id = ci.visit_family_id "
        "WHERE ci.kind = 'Visit' AND " + _FOR_PERSON.format(day=day_sql), {"pid": pid}
    ):
        words = f"Visit done: {r['who']}" if r["visit_done"] else f"Visit planned: {r['who']}"
        if r["visit_done"] and r["care_note"]:
            words += f" - {r['care_note']}"
        events.append(_event(r["day"], "visit", words, r["id"], done=bool(r["visit_done"])))

    for r in conn.execute(
        "SELECT o.id, o.date, o.amount, li.name AS fund FROM offering o "
        "JOIN list_item li ON li.id = o.fund_id WHERE o.giver_person_id = ?", (pid,)
    ):
        events.append(_event(r["date"], "offering", f"Offering {format_vnd(r['amount'])} to {r['fund']}",
                             r["id"], amount=r["amount"]))

    for r in conn.execute(
        "SELECT id, original_name, added_at FROM document WHERE person_id = ?", (pid,)
    ):
        events.append(_event(r["added_at"][:10], "document", f"Document: {r['original_name']}", r["id"]))

    if include_private is True:
        for r in conn.execute("SELECT id, body, created_at FROM private_note WHERE person_id = ?", (pid,)):
            events.append(_event(r["created_at"][:10], "private_note", f"Private note: {r['body']}", r["id"]))

    events.sort(key=lambda e: (e["date"], _KIND_ORDER[e["kind"]], e["ref_id"]))
    return events
