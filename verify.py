"""Check Church Manager from end to end. Prints one PASS or FAIL line per check.

    python verify.py [--keep] [--people N]

1. Runs all tests (``python -m unittest discover -s tests``).
2. Builds a fake church of N People (default 50) in a new temp folder outside OneDrive.
   It never touches ``%LOCALAPPDATA%\\ChurchManager``.
3. Starts the real server on 127.0.0.1 and checks the 6 Dashboard panels and Search.
4. Makes a Handover through the app (POST /copies/handover) and proves the zip has no Private notes.
5. Checks the Giving statement of one Person and one Family has no Private note.
   Then checks the Hermes door (``python -m churchmgr.agent``): with the door off, ``status`` stops with
   exit 3; the door is turned on through the app (POST /settings); ``status``, ``search``, ``person``,
   ``care-due`` and ``money`` answer ok; a dry run of ``add-person`` saves nothing; no answer holds a
   Private note.
6. Both languages. First, every Tiếng Việt text (``i18n.TEXT["vi"]``) must be Vietnamese: no ASCII word
   (3 or more letters) of the English texts, outside ``i18n.ALLOW`` and the fixed ``VI_ASCII_OK`` list.
   Then builds a fake church in Tiếng Việt and one in English. On each, every GET page of
   every page module (real ids of the fake data, some query variants, a 404, a 400 and a 405 page) and
   the first run page (no church copy open) must have the expected status, ``<html lang>`` = the
   language, the switch (``action="/language"``, buttons "Tiếng Việt" and "English") and no ``[[``;
   every Tiếng Việt page must have ``i18n.english_left(page) == []`` and show no English word of a
   Tiếng Việt text. Then the switch: POST /language
   to English, the next page is English, a NEW server on the same church copy still shows English, and
   back to Tiếng Việt. Last, a church copy with no ``language`` row (made as before this setting
   existed) shows Tiếng Việt.
7. Stops the server and removes the temp folder (``--keep`` keeps it and prints its path).

Exit code 0 only when every check passes, else 1. Standard library only.
"""

import argparse
import html
import http.client
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.parse
import zipfile
from contextlib import closing, contextmanager
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

from churchmgr import care, db, fake, i18n, pages, paths, schema, server, settings

ROOT = Path(__file__).resolve().parent
MARKER = b"PRIVATE-NOTE-MARKER"  # every Private note of the fake church starts with it
PANELS = ("this-week", "needs-visit", "services", "money-month", "sent-documents", "search")
DATA_PANELS = PANELS[:-1]  # the search panel is a form; its rows come live from /api/search
TEST_TIMEOUT = 600  # seconds; tests that hang longer are a FAIL (Checks.run), not a stuck window
AGENT_DRY_RUN_NAME = "Verify Agent Dry Run"  # add-person without --yes: this Person must not be saved
LANGUAGES = (("vi", "Tiếng Việt"), ("en", "English"))  # the two buttons of the switch on every page
SWITCH_FORM = re.compile(r'<form class="lang-switch" method="post" action="/language"[^>]*>(.*?)</form>', re.S)
HTML_LANG = re.compile(r'<html lang="([^"]*)"')
H1 = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.S)
MISSING_KEY = re.compile(r"\[\[[^\[\]]*\]\]")  # i18n.t gives [[key]] for a key with no text
# The ASCII words a Tiếng Việt text may share with the English texts (step 6). Written here by hand, never
# taken from i18n.TEXT["vi"]: so an English word put into a Tiếng Việt text is still seen.
VI_ASCII_OK = frozenset({
    "byte",      # the unit of a file size: "0 byte", "{n} byte"
    "chi",       # Vietnamese: Chi phái, Khoản chi, Hạng mục chi, Chi tiết
    "cung",      # Vietnamese: "Lễ Cung Hiến", the example subject of a Sent document
    "english",   # the name of the switch button: "Tiếng Việt hoặc English"
    "gia",       # Vietnamese: Gia đình
    "onedrive",  # the name of the cloud folder a church copy must stay out of
    "thu",       # Vietnamese: "thu hẹp" (to narrow a search)
    "tin",       # Vietnamese: thông tin, Tin Lành
    "yyyy",      # the date form the pastor types: YYYY-MM-DD
    "xlsx",      # the file kind of a People file: tệp .xlsx
    "zip",       # the file kind of a Handover: tệp ZIP
})


class Checks:
    """Prints a PASS/FAIL line per check and remembers the results."""

    def __init__(self):
        self.results = []

    def run(self, name, fn, *args):
        """``fn(*args)`` returns ``(ok, detail)``. An exception is a FAIL. Returns ``ok``."""
        try:
            ok, detail = fn(*args)
        except Exception as exc:  # a check that crashes is a FAIL, the others still run
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        self.results.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f": {detail}" if detail else ""), flush=True)
        return bool(ok)


class PanelParser(HTMLParser):
    """Per ``<section data-panel>``: the number of ``data-row`` elements and the text."""

    def __init__(self):
        super().__init__()
        self.rows, self.text, self.stack = {}, {}, []

    def _panel(self):
        return next((name for name in reversed(self.stack) if name), None)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "section":
            name = a.get("data-panel")
            self.stack.append(name)
            if name:
                self.rows.setdefault(name, 0)
                self.text.setdefault(name, [])
        panel = self._panel()
        if panel and "data-row" in a:
            self.rows[panel] += 1

    def handle_endtag(self, tag):
        if tag == "section" and self.stack:
            self.stack.pop()

    def handle_data(self, data):
        panel = self._panel()
        if panel:
            self.text[panel].append(data)

    def panel_text(self, name):
        return re.sub(r"\s+", " ", " ".join(self.text.get(name, []))).strip()


# ---------------------------------------------------------------- helpers

def request(port, method, path, body=None):
    """One request to the app with the right ``Host`` (and ``Origin`` on a POST).
    Returns ``(status, headers with lower-case names, body bytes)``."""
    headers = {"Host": f"127.0.0.1:{port}"}
    if method == "POST":
        headers["Origin"] = f"http://127.0.0.1:{port}"
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, resp.read()
    finally:
        conn.close()


def read_only(db_path):
    """A read-only SQLite connection (use it in ``with closing(...)``)."""
    return sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)


def count(db_path, table):
    with closing(read_only(db_path)) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def note_texts(db_path):
    """The text of every Private note, as UTF-8 bytes."""
    with closing(read_only(db_path)) as conn:
        return [row[0].encode("utf-8") for row in conn.execute("SELECT body FROM private_note")]


def strip_tags(html_text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html_text)).strip()


# ---------------------------------------------------------------- checks

def run_tests():
    print("....  running all tests (about one minute)", flush=True)
    # The tests get no CHURCH_MANAGER_COPY / CHURCH_MANAGER_HOME, so they never reach a real church copy.
    env = {k: v for k, v in os.environ.items() if k not in (paths.ENV_COPY, paths.ENV_HOME)}
    proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env={**env, "PYTHONIOENCODING": "utf-8"}, timeout=TEST_TIMEOUT)
    out = (proc.stdout + proc.stderr).strip()
    lines = out.splitlines() or ["(no output)"]
    ran = [line for line in lines if re.fullmatch(r"Ran \d+ tests? in \S+", line)]
    if proc.returncode != 0:
        print("\n".join(lines[-40:]))  # the end of the test output says what failed
    return proc.returncode == 0, f"{ran[-1] if ran else 'no Ran line'}, {lines[-1]} (exit code {proc.returncode})"


def check_temp(tmp):
    paths.check_not_onedrive(tmp)  # raises CopyPathError inside OneDrive
    default_root = paths.default_copies_root().resolve()
    if tmp.resolve().is_relative_to(default_root):
        return False, f"{tmp} is inside {default_root}"
    return True, f"{tmp} (not inside OneDrive, not inside {default_root})"


def build(copy, people):
    counts = fake.build_fake_church(copy, people=people)
    db_path = copy / db.DB_NAME
    persons, notes = count(db_path, "person"), count(db_path, "private_note")
    marked = sum(1 for body in note_texts(db_path) if body.startswith(MARKER))
    ok = persons == people and notes > 0 and marked == notes
    return ok, (f"{persons} People, {counts['families']} Families, {counts['offerings']} Offerings, "
                f"{notes} Private notes ({marked} with PRIVATE-NOTE-MARKER)")


def get_dashboard(port, state):
    status, _headers, body = request(port, "GET", "/")
    parser = PanelParser()
    parser.feed(body.decode("utf-8"))
    state["panels"] = parser
    missing = [name for name in PANELS if name not in parser.rows]
    return status == 200 and not missing, (f"GET / -> {status}; panels found: {', '.join(sorted(parser.rows))}"
                                           + (f"; MISSING: {', '.join(missing)}" if missing else ""))


def check_rows(state):
    rows = state["panels"].rows
    empty = [name for name in DATA_PANELS if rows.get(name, 0) < 1]
    detail = ", ".join(f"{name} {rows.get(name, 0)}" for name in DATA_PANELS)
    return not empty, f"data-row count: {detail}" + (f"; NO ROWS: {', '.join(empty)}" if empty else "")


def check_money(state):
    text = state["panels"].panel_text("money-month")
    amounts = re.findall(r"(Offerings|Expenses|Balance) (-?\d[\d.]*) ₫", text)
    non_zero = [value for _label, value in amounts if int(value.replace(".", "")) != 0]
    shown = ", ".join(f"{label} {value} ₫" for label, value in amounts) or f"no amount in: {text[:120]}"
    return bool(non_zero), shown


def check_sent(state):
    year = date.today().year
    text = state["panels"].panel_text("sent-documents")
    found = re.search(rf"Next number (\d{{2,}}/{year})\b", text)
    return found is not None, (f"Next number {found.group(1)}" if found else f"no NN/{year} in: {text[:120]}")


def check_search(port, query):
    path = "/api/search?q=" + urllib.parse.quote(query)
    status, _headers, body = request(port, "GET", path)
    names = [row["full_name"] for row in json.loads(body.decode("utf-8"))] if status == 200 else []
    ok = fake.FIRST_PERSON in names
    return ok, f"GET {path} -> {status}, {len(names)} found" + (f", has {fake.FIRST_PERSON}" if ok else "")


def make_handover(port, root, state):
    status, headers, body = request(port, "POST", "/copies/handover", body=b"")
    location = headers.get("location", "")
    name = urllib.parse.parse_qs(urllib.parse.urlsplit(location).query).get("made", [""])[0]
    if status != 303 or not name:
        return False, f"POST /copies/handover -> {status}: {strip_tags(body.decode('utf-8', 'replace'))[:300]}"
    saved = root / "handovers" / name
    dl_status, _headers, data = request(port, "GET", "/copies/handovers/" + urllib.parse.quote(name))
    state["zip"] = data
    same = saved.is_file() and saved.read_bytes() == data
    return dl_status == 200 and same, (
        f"made through the app: POST /copies/handover -> {status}, saved as {saved}; "
        f"download GET /copies/handovers/{name} -> {dl_status}, {len(data)} bytes, "
        + ("same bytes as the saved zip" if same else "NOT the same as the saved zip"))


def unzip_db(state, work):
    """Open the zip and write its church.db to ``work`` for the next checks."""
    with zipfile.ZipFile(io.BytesIO(state["zip"])) as zf:
        state["files"] = {n: zf.read(n) for n in zf.namelist() if not n.endswith("/")}
    work.mkdir()
    state["zip_db"] = work / db.DB_NAME
    state["zip_db"].write_bytes(state["files"][db.DB_NAME])


def check_zip_notes(state, work):
    unzip_db(state, work)
    left = count(state["zip_db"], "private_note")
    return left == 0, f"{left} rows in private_note of the handover church.db"


def check_zip_bytes(state, bodies):
    files = state["files"]
    bad = [name for name, data in files.items() if MARKER in data or any(b in data for b in bodies)]
    docs = len(files) - 1
    return not bad, (f"{len(files)} files in the zip checked ({db.DB_NAME} + {docs} Documents): "
                     + (f"FOUND in {', '.join(bad)}" if bad else "no PRIVATE-NOTE-MARKER, no Private note text"))


def check_zip_people(state, source_db, people):
    in_zip, in_source = count(state["zip_db"], "person"), count(source_db, "person")
    return in_zip == in_source == people, f"{in_zip} People in the zip, {in_source} in the source"


def check_source_notes(source_db, before):
    after = count(source_db, "private_note")
    return after == before and after > 0, f"{before} Private notes before the Handover, {after} after"


def statement_giver(source_db, kind):
    """The Person (or current Family of a Person) with a Private note who has the most Offerings this year."""
    year = str(date.today().year)
    if kind == "person":
        sql = ("SELECT pn.person_id, p.full_name, COUNT(DISTINCT o.id) FROM private_note pn "
               "JOIN person p ON p.id = pn.person_id "
               "LEFT JOIN offering o ON o.giver_person_id = pn.person_id AND substr(o.date, 1, 4) = ? "
               "GROUP BY pn.person_id ORDER BY 3 DESC, pn.person_id LIMIT 1")
    else:
        sql = ("SELECT f.id, f.name, COUNT(DISTINCT o.id) FROM private_note pn "
               "JOIN family_link fl ON fl.person_id = pn.person_id AND fl.end_date IS NULL "
               "JOIN family f ON f.id = fl.family_id "
               "LEFT JOIN offering o ON o.giver_family_id = f.id AND substr(o.date, 1, 4) = ? "
               "GROUP BY f.id ORDER BY 3 DESC, f.id LIMIT 1")
    with closing(read_only(source_db)) as conn:
        return conn.execute(sql, (year,)).fetchone()


def check_statement(port, source_db, kind, bodies):
    giver_id, name, offerings = statement_giver(source_db, kind)
    year = date.today().year
    path = f"/money/statement?{kind}_id={giver_id}&year={year}"
    status, _headers, body = request(port, "GET", path)
    page = body.decode("utf-8")
    leak = MARKER in body or any(b in body for b in bodies)
    ok = status == 200 and "Giving statement" in page and html.escape(name) in page and not leak
    return ok, (f"GET {path} -> {status}; {kind.title()} {name} ({offerings} Offerings in {year}, has a Private note "
                f"in the source); {'PRIVATE NOTE FOUND' if leak else 'no PRIVATE-NOTE-MARKER'}")


def agent(copy, root, *argv):
    """``python -m churchmgr.agent ARGV --copy COPY --copies-root ROOT``, run in this folder.
    Returns ``(exit code, the JSON answer, stdout + stderr bytes)``."""
    env = {k: v for k, v in os.environ.items() if k not in (paths.ENV_COPY, paths.ENV_HOME)}
    proc = subprocess.run([sys.executable, "-m", "churchmgr.agent", *argv, "--copy", str(copy),
                           "--copies-root", str(root)], cwd=ROOT, capture_output=True, env=env, timeout=60)
    try:
        answer = json.loads(proc.stdout.decode("utf-8"))
    except ValueError:
        raise RuntimeError(f"{argv[0]}: exit {proc.returncode}, no JSON answer; "
                           f"{proc.stderr.decode('utf-8', 'replace')[-300:]}") from None
    return proc.returncode, answer, proc.stdout + proc.stderr


def json_texts(value):
    """Every text inside a JSON answer (a Private note could hide behind JSON escapes in the raw bytes)."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from json_texts(item)
    elif isinstance(value, list):
        for item in value:
            yield from json_texts(item)


def check_agent(port, root, source_db, bodies):
    """The Hermes door from end to end, on the running server and the fake church."""
    copy, runs, failed, steps = source_db.parent, [], [], []

    def run(*argv):
        code, answer, raw = agent(copy, root, *argv)
        runs.append((argv[0], raw, answer))
        return code, answer

    def run_ok(*argv):
        code, answer = run(*argv)
        if code != 0 or answer.get("ok") is not True:
            failed.append(f"{argv[0]} -> exit {code}, {answer.get('error')}: {answer.get('message')}")
        return answer

    code, answer = run("status")
    if (code, answer.get("error")) != (3, "door_off"):
        return False, f"door off: status -> exit {code}, {answer}"
    steps.append("door off: status -> exit 3 door_off")

    with closing(read_only(source_db)) as conn:
        conn.row_factory = sqlite3.Row
        form = {"church_name": settings.get_setting(conn, "church_name"),
                "care_reminder_months": str(care.reminder_months(conn)), settings.HERMES_DOOR: "on"}
    status, _headers, body = request(port, "POST", "/settings", urllib.parse.urlencode(form).encode("utf-8"))
    if status != 303:
        return False, f"POST /settings hermes_door=on -> {status}: {strip_tags(body.decode('utf-8', 'replace'))[:300]}"
    steps.append("door turned on through the app: POST /settings -> 303")

    run_ok("status")
    found = run_ok("search", "nguyen hai dang").get("results") or []
    if not found:
        return False, "search \"nguyen hai dang\" found no one" + (f"; {'; '.join(failed)}" if failed else "")
    run_ok("person", str(found[0]["id"]))
    run_ok("care-due")
    run_ok("money")
    steps.append(f"status, search ({found[0]['full_name']}, id {found[0]['id']}), person, care-due, money -> "
                 + ("exit 0 ok" if not failed else "NOT ALL OK"))

    before = count(source_db, "person")
    dry = run_ok("add-person", "--full-name", AGENT_DRY_RUN_NAME)
    after = count(source_db, "person")
    if dry.get("saved") is not False or after != before:
        failed.append(f"add-person dry run: saved {dry.get('saved')}, {before} People before, {after} after")
    steps.append(f"add-person dry run: saved {dry.get('saved')}, {before} People before and {after} after")

    texts = [note.decode("utf-8") for note in bodies]
    leaks = [command for command, raw, answer in runs
             if MARKER in raw or any(b in raw for b in bodies)
             or any(t in s for s in json_texts(answer) for t in texts)]
    if leaks:
        failed.append(f"Private note FOUND in: {', '.join(leaks)}")
    steps.append(f"{len(runs)} answers: " + ("no PRIVATE-NOTE-MARKER, no Private note text" if not leaks
                                              else "PRIVATE NOTE FOUND"))
    return not failed, "; ".join(steps) + (f"; FAILED: {'; '.join(failed)}" if failed else "")


def start_server(copy, root, state):
    """Start the real server on 127.0.0.1 and a free port, in a thread."""
    httpd = server.make_server(copy, root, 0, remember=False)  # remember=False: never writes current.txt
    server.serve_in_thread(httpd)
    state["httpd"] = httpd
    return True, f"started at {httpd.url} (copies folder {root})"


def stop(httpd):
    httpd.shutdown()
    httpd.server_close()
    return True, "shut down"


def clean_up(tmp, keep):
    if keep:
        return True, f"kept (--keep): {tmp}"
    for attempt in range(10):  # a request thread may close its SQLite file a moment after the reply
        try:
            shutil.rmtree(tmp)
            return True, f"removed {tmp}"
        except OSError:
            if attempt == 9:
                raise
            time.sleep(0.5)
    return False, "not removed"


# ---------------------------------------------------------------- both languages (step 6)

@contextmanager
def running(copy, root):
    """The real server on ``copy`` (``None``: first run, no church copy open) for the ``with`` block.
    Yields its port; stops it at the end."""
    httpd = server.make_server(copy, root, 0, remember=False)
    server.serve_in_thread(httpd)
    try:
        yield httpd.port
    finally:
        stop(httpd)


def post_form(port, path, form):
    return request(port, "POST", path, urllib.parse.urlencode(form).encode("utf-8"))


def language_row(copy):
    """The ``language`` setting row of a church copy, or ``None`` when there is no row."""
    with closing(read_only(copy / db.DB_NAME)) as conn:
        row = conn.execute("SELECT value FROM setting WHERE key = ?", (settings.LANGUAGE,)).fetchone()
    return None if row is None else row[0]


def build_lang(copy, people, lang):
    fake.build_fake_church(copy, people=people, lang=lang)
    persons, row = count(copy / db.DB_NAME, "person"), language_row(copy)
    return persons == people and row == lang, f"{persons} People in {copy.name}, language row {row!r}"


def page_paths(db_path):
    """``[(path, status, kind)]``: every GET page of the app on the fake church in ``db_path``, with real ids
    of its data and some query variants, then a 404, a 400 and a 405 page. ``kind`` is ``page`` (HTML) or
    ``answer`` (a GET route that gives a file or JSON, no page)."""
    today = date.today()
    with closing(read_only(db_path)) as conn:
        def first(sql, *args):
            row = conn.execute(sql, args).fetchone()
            if row is None or row[0] is None:
                raise RuntimeError(f"the fake church has no row for: {sql}")
            return row[0]

        person = first("SELECT id FROM person WHERE full_name = ?", fake.FIRST_PERSON)
        note = first("SELECT MIN(id) FROM private_note WHERE person_id = ?", person)
        persons = [person,
                   first("SELECT person_id FROM person_status GROUP BY person_id ORDER BY COUNT(*) DESC, person_id"),
                   first("SELECT person_id FROM family_link GROUP BY person_id ORDER BY COUNT(*) DESC, person_id"),
                   first("SELECT person_id FROM ministry_link WHERE ministry_role = 'Leader' ORDER BY id")]
        family = first("SELECT family_id FROM chi_phai_link GROUP BY family_id ORDER BY COUNT(*) DESC, family_id")
        chi_phai = first("SELECT chi_phai_id FROM truong_chi_phai GROUP BY chi_phai_id ORDER BY COUNT(*) DESC, 1")
        items = [first("SELECT MIN(calendar_item_id) FROM head_count"),
                 first("SELECT MIN(id) FROM calendar_item WHERE kind = 'Service' AND id NOT IN "
                       "(SELECT calendar_item_id FROM head_count)"),
                 first("SELECT MIN(id) FROM calendar_item WHERE kind = 'Meeting'"),
                 first("SELECT MIN(calendar_item_id) FROM document"),
                 first("SELECT MIN(id) FROM calendar_item WHERE kind = 'Visit' AND visit_done = 1"),
                 first("SELECT MIN(id) FROM calendar_item WHERE kind = 'Visit' AND visit_done = 0")]
        offerings = [first("SELECT MIN(id) FROM offering WHERE giver_person_id IS NOT NULL"),
                     first("SELECT MIN(id) FROM offering WHERE giver_family_id IS NOT NULL"),
                     first("SELECT MIN(id) FROM offering WHERE giver_person_id IS NULL AND giver_family_id IS NULL")]
        expense = first("SELECT MIN(id) FROM expense")
        document = first("SELECT MIN(id) FROM document WHERE person_id IS NOT NULL")
        giver = first("SELECT giver_person_id FROM offering WHERE giver_person_id IS NOT NULL "
                      "GROUP BY 1 ORDER BY COUNT(*) DESC, 1")
        giver_family = first("SELECT giver_family_id FROM offering WHERE giver_family_id IS NOT NULL "
                             "GROUP BY 1 ORDER BY COUNT(*) DESC, 1")
    found_none = "zzzzqqq"  # a search that finds no one
    out = ["/", "/search", "/search?q=nguyen", f"/search?q={found_none}",
           "/people", "/people?q=nguyen", "/people/new", "/people/file", f"/people/{person}/edit",
           f"/people/{person}?edit_note={note}"]
    out += [f"/people/{pid}" for pid in persons]
    out += ["/families", "/families/new", f"/families/{family}", f"/families/{family}/edit",
            "/chi-phai", "/chi-phai/new", f"/chi-phai/{chi_phai}", f"/chi-phai/{chi_phai}/edit",
            "/calendar", f"/calendar?month={today:%Y-%m}", f"/calendar?month={today.year + 4}-01",
            f"/calendar?from={today}", "/calendar/new", f"/calendar/new?date={today}"]
    out += [f"/calendar/{iid}" for iid in items]
    out += ["/care", "/care?log=all",
            "/money", f"/money?month={today:%Y-%m}", "/money/offerings/new", "/money/expenses/new",
            f"/money/expenses/{expense}/edit", "/money/statement",
            f"/money/statement?person_id={giver}&year={today.year}",
            f"/money/statement?family_id={giver_family}&year={today.year}"]
    out += [f"/money/offerings/{oid}/edit" for oid in offerings]
    out += ["/documents", f"/documents/new?person_id={person}", f"/documents/new?family_id={family}",
            f"/documents/new?calendar_item_id={items[3]}", f"/documents/{document}/delete",
            "/sent", f"/sent?year={today.year - 1}", "/sent/new", "/lists", "/copies", "/settings"]
    listed = [(path, 200, "page") for path in out]
    listed += [("/no-such-page", 404, "page"), ("/people/999999", 404, "page"),
               ("/copies/handovers/handover-none-2001-01-01.zip", 404, "page"),
               ("/money?month=nope", 400, "page"), ("/documents/new", 400, "page"),  # a Document needs one link
               ("/language", 405, "page"),
               ("/api/search?q=nguyen", 200, "answer"), (f"/documents/{document}/file", 200, "answer")]
    return listed


def switch_problems(page, lang):
    """The language switch: a form that posts to /language with ``next`` and the buttons Tiếng Việt and
    English; the button of ``lang`` has ``aria-pressed="true"``, the other ``"false"``."""
    form = SWITCH_FORM.search(page)
    if form is None:
        return ['no switch form (action="/language")']
    out = [] if 'name="next"' in form.group(1) else ["the switch has no next field"]
    for code, name in LANGUAGES:
        button = re.search(rf"<button\b([^>]*)>{re.escape(name)}</button>", form.group(1))
        pressed = "true" if code == lang else "false"
        if button is None:
            out.append(f"no switch button {name}")
        elif f'value="{code}"' not in button.group(1) or f'aria-pressed="{pressed}"' not in button.group(1):
            out.append(f'switch button {name}: expected value="{code}" aria-pressed="{pressed}"')
    return out


def vi_english():
    """``{key: sorted words}``: each Tiếng Việt text (``i18n.TEXT["vi"]``) that holds an English word. A word
    is English when the English texts have it and it is not in ``i18n.ALLOW`` or ``VI_ASCII_OK``. Word rule
    of ``i18n._ascii_words`` (ASCII, 3 or more letters, lower case, ``{params}`` left out); the phrase
    "Church Manager" is left out, as in ``i18n.english_left``."""
    english = i18n._ascii_words(i18n.TEXT["en"].values()) - i18n.ALLOW - VI_ASCII_OK
    out = {}
    for key, value in i18n.TEXT["vi"].items():
        words = i18n._ascii_words([value.replace("Church Manager", " ")]) & english
        if words:
            out[key] = sorted(words)
    return out


def check_vi_texts():
    """Every Tiếng Việt text is Vietnamese. Prints each text with an English word (key and words) on its
    own line before the PASS/FAIL line."""
    bad = vi_english()
    for key, words in bad.items():
        print(f"      {key}: {', '.join(words)}", flush=True)
    return not bad, (f"{len(i18n.TEXT['vi'])} texts checked; " + (
        f"{len(bad)} TEXTS WITH ENGLISH WORDS, listed above" if bad else
        "no English word (ASCII words shared with the English texts are only i18n.ALLOW and "
        f"VI_ASCII_OK: {', '.join(sorted(VI_ASCII_OK))})"))


def vi_english_shown(page):
    """The visible words of a page that are English words of a Tiếng Việt text (``vi_english``), sorted.
    Visible text as in ``i18n.english_left``."""
    bad = {word for words in vi_english().values() for word in words}
    if not bad:
        return []
    parser = i18n._Visible()
    parser.feed(page)
    parser.close()
    visible = "\n".join(parser.parts).replace("Church Manager", " ")
    return sorted({w for w in i18n._WORD.findall(visible) if w.isascii() and w.lower() in bad})


def page_problems(lang, status, headers, body, expect):
    """What is wrong with one HTML page in ``lang`` (an empty list: nothing)."""
    out = [] if status == expect else [f"status {status}, expected {expect}"]
    if not headers.get("content-type", "").startswith("text/html"):
        return out + [f"no HTML page: {headers.get('content-type')}"]
    page = body.decode("utf-8", "replace")
    found = HTML_LANG.search(page)
    if found is None or found.group(1) != lang:
        out.append(f'<html lang="{found.group(1) if found else "?"}">, expected "{lang}"')
    out += switch_problems(page, lang)
    if "[[" in page:
        out.append("[[ on the page: " + (", ".join(sorted(set(MISSING_KEY.findall(page)))) or "[["))
    if lang == "vi":
        words = [w for w in i18n.english_left(page) if not w.startswith("[[")]
        if words:
            out.append("English left: " + ", ".join(words))
        shown = vi_english_shown(page)  # english_left cannot see these: they are inside TEXT["vi"]
        if shown:
            out.append("English from a Tiếng Việt text: " + ", ".join(shown))
    elif not i18n.english_left(page):  # proves the vi rule can see English words on this page
        out.append("no English word seen by i18n.english_left")
    return out


def answer_problems(status, headers, body, expect):
    """A GET route that gives a file or JSON: the status, no HTML, no ``[[``."""
    out = [] if status == expect else [f"status {status}, expected {expect}"]
    if headers.get("content-type", "").startswith("text/html"):
        out.append("an HTML page, expected a file or JSON")
    if b"[[" in body:
        out.append("[[ in the answer")
    return out


def check_routes(db_path):
    """Every GET route of every page module has a path in the page list (``/setup`` is the first run page)."""
    routes = [route for route in server.build_routes(pages.PAGES) if route[0] == "GET"]
    covered = {"/setup"}
    for path, _status, _kind in page_paths(db_path):
        bare = urllib.parse.urlsplit(path).path
        covered.update(pattern for _m, regex, _c, _h, pattern in routes if regex.match(bare))
    missing = [route[4] for route in routes if route[4] not in covered]
    return not missing, (f"{len(routes)} GET routes of {len(pages.PAGES)} page modules, " + (
        f"NO PAGE CHECKED FOR: {', '.join(missing)}" if missing else "each one has a page to check"))


def check_pages(lang, copy, root):
    """Every path of ``page_paths`` on ``copy`` (its language is ``lang``), then the first run page in ``lang``.
    Prints each problem (page and words) on its own line before the PASS/FAIL line."""
    problems, n_pages, n_answers = [], 0, 0
    with running(copy, root) as port:
        for path, expect, kind in page_paths(copy / db.DB_NAME):
            status, headers, body = request(port, "GET", path)
            if kind == "answer":
                n_answers += 1
                bad = answer_problems(status, headers, body, expect)
            else:
                n_pages += 1
                bad = page_problems(lang, status, headers, body, expect)
            problems += [f"GET {path}: {problem}" for problem in bad]
    with running(None, root) as port:  # first run: no church copy open; the screens start in Tiếng Việt
        if lang != "vi":
            status, headers, _b = post_form(port, "/language", {"lang": lang, "next": "/setup"})
            if (status, headers.get("location")) != (303, "/setup"):
                problems.append(f"first run: POST /language lang={lang} -> {status} {headers.get('location')}")
        status, headers, body = request(port, "GET", "/setup")
        n_pages += 1
        problems += [f"GET /setup (first run): {p}" for p in page_problems(lang, status, headers, body, 200)]
    for problem in problems:
        print(f"      {problem}", flush=True)
    rules = f'status, <html lang="{lang}">, switch, no [[, ' + (
        "no English left, no English word of a Tiếng Việt text" if lang == "vi"
        else "English words seen (so the Tiếng Việt rule can see them)")
    return not problems, (f"{n_pages} pages checked (first run page included) + {n_answers} file/JSON answers; "
                          + (f"{len(problems)} PROBLEMS, listed above" if problems else rules))


def shown_in(port, path, lang, h1_key):
    """GET ``path``: the problems of the page in ``lang``, and its h1 must be ``TEXT[lang][h1_key]``."""
    status, headers, body = request(port, "GET", path)
    problems = page_problems(lang, status, headers, body, 200)
    h1 = H1.search(body.decode("utf-8", "replace"))
    text = html.unescape(strip_tags(h1.group(1))) if h1 else None
    if text != i18n.TEXT[lang][h1_key]:
        problems.append(f"h1 {text!r}, expected {i18n.TEXT[lang][h1_key]!r}")
    return problems


def check_switch(copy, root):
    """The switch from end to end on the Tiếng Việt church copy: to English, kept by a new server, back."""
    steps = []

    def switch(port, lang):
        status, headers, _b = post_form(port, "/language", {"lang": lang, "next": "/people"})
        ok = (status, headers.get("location")) == (303, "/people")
        steps.append(f"POST /language lang={lang} next=/people -> {status} {headers.get('location')}")
        return ok

    def look(port, lang, when):
        bad = shown_in(port, "/people", lang, "people.title")
        steps.append(f"{when} GET /people: " + ("; ".join(bad) if bad else
                                                f"{dict(LANGUAGES)[lang]} (h1 {i18n.TEXT[lang]['people.title']})"))
        return not bad

    with running(copy, root) as port:
        ok = switch(port, "en") and look(port, "en", "then")
    row = language_row(copy)
    steps.append(f"server stopped; language row {row!r}")
    with running(copy, root) as port:  # a NEW server on the same church copy
        ok = (look(port, "en", "new server:") and switch(port, "vi") and look(port, "vi", "then")
              and ok and row == "en")
    return ok, "; ".join(steps)


def old_copy(folder):
    """A church copy made the way the app made it before the ``language`` setting existed: the schema, the
    default lists, ``church_name`` and ``care_reminder_months``, and no ``language`` row. Nothing is deleted."""
    folder.mkdir()
    (folder / db.DOCUMENTS_DIR).mkdir()
    conn = db.connect(folder / db.DB_NAME)
    try:
        with db.transaction(conn):
            schema.create_schema(conn)
            schema.insert_default_lists(conn, "en")  # the old lists were in English
            for key, value in {"church_name": fake.CHURCH_NAME, **schema.DEFAULT_SETTINGS}.items():
                settings.set_setting(conn, key, value)
    finally:
        conn.close()


def check_no_language_row(folder, root):
    old_copy(folder)
    row = language_row(folder)
    with closing(read_only(folder / db.DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        lang = settings.get_language(conn)
    with running(folder, root) as port:
        bad = shown_in(port, "/", "vi", "dashboard.title") + shown_in(port, "/settings", "vi", "settings.title")
    ok = row is None and lang == "vi" and not bad
    return ok, (f"language row {row!r}, settings.get_language -> {lang!r}; GET / and GET /settings: "
                + ("; ".join(bad) if bad else 'Tiếng Việt (<html lang="vi">, no English left)'))


def check_languages(checks, tmp, people):
    """Step 6: every page in Tiếng Việt and in English, the switch, a church copy with no language row."""
    copies = {lang: tmp / f"fake-{lang}" for lang, _name in LANGUAGES}
    checks.run("6. every Tiếng Việt text is Vietnamese", check_vi_texts)
    built = [checks.run(f"6. fake church in {name}", build_lang, copies[lang], people, lang)
             for lang, name in LANGUAGES]
    if all(built):
        checks.run("6. every GET route is in the page list", check_routes, copies["vi"] / db.DB_NAME)
        for lang, name in LANGUAGES:
            checks.run(f"6. every page in {name}", check_pages, lang, copies[lang], tmp)
        checks.run("6. language switch, kept after a restart", check_switch, copies["vi"], tmp)
    checks.run("6. church copy with no language row shows Tiếng Việt", check_no_language_row, tmp / "old-copy", tmp)


# ---------------------------------------------------------------- main

def check_app(checks, port, tmp, source_db, people, state):
    """Steps 3 to 5, on the running server."""
    if checks.run("3. Dashboard panels", get_dashboard, port, state):
        checks.run("3. Dashboard data rows", check_rows, state)
        checks.run("3. Money this month is not zero", check_money, state)
        checks.run("3. Sent documents next number", check_sent, state)
    name = fake.FIRST_PERSON
    for label, query in (("no accents", "nguyen hai dang"),
                         ("NFC accents", unicodedata.normalize("NFC", name)),
                         ("NFD accents", unicodedata.normalize("NFD", name))):
        checks.run(f"3. Search ({label})", check_search, port, query)

    bodies = note_texts(source_db)
    if checks.run("4. Handover", make_handover, port, tmp, state):
        checks.run("4. Handover has no Private note rows", check_zip_notes, state, tmp / "handover-check")
        if "zip_db" in state:  # the zip opened: check its bytes and People too
            checks.run("4. Handover zip has no Private note text", check_zip_bytes, state, bodies)
            checks.run("4. Handover has every Person", check_zip_people, state, source_db, people)
    checks.run("4. source church copy keeps its Private notes", check_source_notes, source_db, len(bodies))

    for kind in ("person", "family"):
        checks.run(f"5. Giving statement of a {kind.title()}", check_statement, port, source_db, kind, bodies)
    checks.run("5. Agent CLI (Hermes door)", check_agent, port, tmp, source_db, bodies)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(prog="python verify.py", description="Check Church Manager from end to end.")
    parser.add_argument("--keep", action="store_true", help="keep the temp folder and print its path")
    parser.add_argument("--people", type=int, default=50,
                        help=f"People in the fake church ({fake.MIN_PEOPLE} to {fake.MAX_PEOPLE}, default 50)")
    args = parser.parse_args(argv)
    if not fake.MIN_PEOPLE <= args.people <= fake.MAX_PEOPLE:
        parser.error(f"--people must be from {fake.MIN_PEOPLE} to {fake.MAX_PEOPLE}")

    print(f"Church Manager verify: Python {sys.version.split()[0]}, folder {ROOT}", flush=True)
    checks = Checks()
    checks.run("1. all tests", run_tests)

    tmp = Path(tempfile.mkdtemp(prefix="cm-verify-")).resolve()
    copy, state = tmp / "fake-church", {}
    try:
        ready = (checks.run("2. temp folder", check_temp, tmp)
                 and checks.run(f"2. fake church of {args.people} People", build, copy, args.people)
                 and checks.run("3. server", start_server, copy, tmp, state))
        if ready:
            httpd = state["httpd"]
            try:
                check_app(checks, httpd.port, tmp, copy / db.DB_NAME, args.people, state)
                check_languages(checks, tmp, args.people)  # its own servers and church copies
            finally:
                checks.run("7. server stopped", stop, httpd)
    finally:
        checks.run("7. temp folder", clean_up, tmp, args.keep)

    failed = checks.results.count(False)
    if failed:
        print(f"FAILED: {failed} of {len(checks.results)} checks")
        return 1
    print(f"ALL {len(checks.results)} CHECKS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
