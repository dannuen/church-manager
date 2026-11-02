"""Card HD1: the Hermes door Setting and the read commands of ``python -m churchmgr.agent``.

Fake churches in temp folders only. Every agent run names ``--copy`` and ``--copies-root``.
"""

import contextlib
import datetime as dt
import hashlib
import io
import json
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import _support  # noqa: F401 - puts the repo root on sys.path
from churchmgr import agent, care, db, fake, lists, money, paths, schema, settings
from test_pages_people import PagesTestBase

ROOT = _support.ROOT
AGENT_SOURCE = (ROOT / "churchmgr" / "agent.py").read_text(encoding="utf-8")
READ_COMMANDS = (["status"], ["search", "nguyen"], ["person", "1"], ["family", "1"], ["calendar"], ["money"],
                 ["care-due"], ["lists"])
DOOR_OFF_TEXT = ("The Hermes door is off for this church copy. The pastor can turn it on in Church Manager: "
                 "Settings > Hermes door > On.")


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


class FakeChurchBase(unittest.TestCase):
    """One fake church of 20 people per test class, in a temp folder outside OneDrive."""

    DOOR = None  # None = no hermes_door row

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        cls.root = pathlib.Path(cls.tmp.name)
        assert "onedrive" not in str(cls.root.resolve()).lower()
        cls.copy = cls.root / "church1"
        fake.build_fake_church(cls.copy, people=20)
        cls.db_path = cls.copy / db.DB_NAME
        if cls.DOOR is not None:
            cls.set_door(cls.DOOR)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def set_door(cls, value):
        conn = db.connect(cls.db_path)
        try:
            settings.set_setting(conn, settings.HERMES_DOOR, value)
        finally:
            conn.close()

    def sql(self, statement, params=()):
        """Run one statement on the church copy (read/write, like the app)."""
        conn = db.connect(self.db_path)
        try:
            return [tuple(r) for r in conn.execute(statement, params).fetchall()]
        finally:
            conn.close()

    def ro(self):
        conn = agent.connect_ro(self.db_path)
        self.addCleanup(conn.close)
        return conn

    def run_agent(self, *argv):
        """``agent.main`` in this process. Returns (exit code, the one JSON object it printed)."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = agent.main([*argv, "--copy", str(self.copy), "--copies-root", str(self.root)])
        return code, json.loads(out.getvalue())  # json.loads refuses anything after the one object

    def ok(self, *argv):
        code, answer = self.run_agent(*argv)
        self.assertEqual((code, answer["ok"], answer["command"]), (0, True, argv[0]), answer)
        return answer

    def refused(self, error, *argv):
        code, answer = self.run_agent(*argv)
        self.assertEqual(answer["ok"], False, answer)
        self.assertEqual(answer["error"], error, answer)
        self.assertEqual(code, agent.EXIT[error])
        self.assertEqual(set(answer), {"ok", "error", "message"})
        self.assertTrue(answer["message"].endswith("."), answer)
        return answer

    def subprocess_agent(self, *argv):
        env = {**os.environ, paths.ENV_HOME: str(self.root), paths.ENV_COPY: str(self.copy)}
        proc = subprocess.run([sys.executable, "-m", "churchmgr.agent", *argv,
                               "--copy", str(self.copy), "--copies-root", str(self.root)],
                              cwd=ROOT, env=env, capture_output=True, timeout=60)
        return proc


class DoorOffTest(FakeChurchBase):
    """No hermes_door row: the door is off and every command stops at the door."""

    def test_missing_row_is_off_and_every_read_command_stops_with_exit_3(self):
        self.assertEqual(self.sql("SELECT value FROM setting WHERE key = ?", (settings.HERMES_DOOR,)), [])
        self.assertFalse(settings.hermes_door_on(self.ro()))
        self.assertEqual(agent.DOOR_OFF, DOOR_OFF_TEXT)
        before = sha(self.db_path)
        guards = {n: mock.Mock(side_effect=AssertionError(n)) for n in dir(agent) if n.startswith("cmd_")}
        self.assertGreaterEqual(len(guards), len(READ_COMMANDS))
        with mock.patch.multiple(agent, **guards):  # no command function runs behind a closed door
            for argv in READ_COMMANDS:
                answer = self.refused("door_off", *argv)
                self.assertEqual(answer["message"], DOOR_OFF_TEXT)
            # bad values are not even looked at: the door comes first
            for argv in (["person", "abc"], ["search", "x", "--limit", "0"], ["calendar", "--from", "nope"],
                         ["money", "--month", "13"], ["family", "999999"]):
                self.refused("door_off", *argv)
        self.assertEqual(sha(self.db_path), before)
        self.assertFalse((self.copy / "church.db-journal").exists())

    def test_off_and_any_text_but_exactly_on_is_off(self):
        self.addCleanup(self.sql, "DELETE FROM setting WHERE key = ?", (settings.HERMES_DOOR,))
        self.set_door("off")
        self.refused("door_off", "status")
        for text in ("ON", "On", " on", "yes", "1", "true"):  # written past set_setting, which refuses them
            self.sql("INSERT INTO setting (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = ?",
                     (settings.HERMES_DOOR, text, text))
            self.assertFalse(settings.hermes_door_on(self.ro()), text)
            self.refused("door_off", "status")

    def test_door_off_in_a_real_process_exits_3(self):
        before = sha(self.db_path)
        proc = self.subprocess_agent("status")
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertEqual(proc.stderr, b"")
        answer = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual(answer, {"ok": False, "error": "door_off", "message": DOOR_OFF_TEXT})
        self.assertEqual(sha(self.db_path), before)


class ReadCommandsTest(FakeChurchBase):
    """The door is on: each read command gives ok JSON and changes nothing."""

    DOOR = "on"

    def test_read_commands_change_nothing_and_never_open_read_write(self):
        before = sha(self.db_path)
        with mock.patch.object(db, "connect", side_effect=AssertionError("db.connect")), \
                mock.patch.object(db, "open_church_copy", side_effect=AssertionError("db.open_church_copy")):
            for argv in READ_COMMANDS:
                self.ok(*argv)
        self.assertEqual(sha(self.db_path), before)
        self.assertFalse((self.copy / "church.db-journal").exists())

    def test_status(self):
        answer = self.ok("status")
        self.assertEqual(answer["church_name"], fake.CHURCH_NAME)
        self.assertEqual(answer["copy_folder"], str(self.copy.resolve()))
        self.assertEqual(answer["copies_root"], str(self.root.resolve()))
        self.assertEqual(answer["schema_version"], schema.SCHEMA_VERSION)
        self.assertEqual(answer["hermes_door"], "on")
        self.assertEqual(answer["quick_check"], "ok")
        expected = {t: self.sql(f"SELECT COUNT(*) FROM {t}")[0][0] for t in agent.COUNTED}
        self.assertEqual(set(expected), {"person", "family", "calendar_item", "offering", "expense"})
        self.assertEqual(answer["counts"], expected)
        self.assertEqual(answer["counts"]["person"], 20)

    def test_search_finds_vietnamese_names_with_or_without_accents(self):
        pid, name = self.sql("SELECT id, full_name FROM person WHERE id = 1")[0]
        self.assertFalse(name.isascii(), name)
        for words in (name.split(), self.ro().execute("SELECT name_folded FROM person WHERE id = 1")
                      .fetchone()[0].split()):
            answer = self.ok("search", *words)
            self.assertEqual(answer["limit"], 20)
            found = [r for r in answer["results"] if r["id"] == pid]
            self.assertEqual([r["full_name"] for r in found], [name], words)
            for row in answer["results"]:
                self.assertEqual(set(row), {"id", "full_name", "status_name"})
        self.assertLessEqual(len(self.ok("search", "n", "--limit", "2")["results"]), 2)
        self.assertEqual(self.ok("search", "zzzz-no-one")["results"], [])
        for bad in ("0", "101", "x", "", "-1", "2.5", "１２"):
            answer = self.refused("invalid", "search", "nguyen", "--limit", bad)
            self.assertEqual(answer["message"], "Limit must be a whole number from 1 to 100.")

    def test_person(self):
        answer = self.ok("person", "1")
        self.assertEqual(set(answer), {"ok", "command", "person", "status", "family", "ministries", "story"})
        person = answer["person"]
        self.assertLessEqual({"id", "full_name", "gender", "birth_date", "phone", "address", "note"}, set(person))
        self.assertEqual(person["id"], 1)
        self.assertEqual(person["full_name"], self.sql("SELECT full_name FROM person WHERE id = 1")[0][0])
        self.assertIsNotNone(answer["status"]["name"])
        self.assertIsInstance(answer["ministries"], list)
        self.assertTrue(answer["story"])
        for event in answer["story"]:
            self.assertLessEqual({"date", "kind", "text", "ref_id"}, set(event))
            self.assertNotEqual(event["kind"], "private_note")
        self.assertNotIn("name_folded", json.dumps(answer))

    def test_person_never_shows_a_private_note(self):
        owners = [r[0] for r in self.sql("SELECT DISTINCT person_id FROM private_note")]
        self.assertTrue(owners)
        bodies = [r[0] for r in self.sql("SELECT body FROM private_note")]
        for pid in owners:
            flat = json.dumps(self.ok("person", str(pid)), ensure_ascii=False)
            self.assertNotIn(fake.MARKER, flat)
            for body in bodies:
                self.assertNotIn(body, flat)

    def test_family(self):
        fid = self.sql("SELECT family_id FROM family_link WHERE end_date IS NULL ORDER BY family_id LIMIT 1")[0][0]
        answer = self.ok("family", str(fid))
        self.assertEqual(set(answer["family"]), {"id", "name", "address"})
        self.assertEqual(answer["family"]["id"], fid)
        members = {r[0] for r in self.sql("SELECT person_id FROM family_link WHERE family_id = ? "
                                          "AND end_date IS NULL", (fid,))}
        self.assertEqual({m["id"] for m in answer["members"]}, members)
        self.assertIn("chi_phai", answer)
        self.assertNotIn("name_folded", json.dumps(answer))

    def test_calendar(self):
        today = dt.date.today()
        answer = self.ok("calendar")
        self.assertEqual((answer["from"], answer["to"]), (today.isoformat(), (today + dt.timedelta(6)).isoformat()))
        answer = self.ok("calendar", "--from", (today - dt.timedelta(60)).isoformat(), "--to", today.isoformat())
        self.assertTrue(answer["items"])
        for item in answer["items"]:
            self.assertTrue(answer["from"] <= item["starts_at"][:10] <= answer["to"])
            self.assertLessEqual({"id", "kind", "title", "starts_at"}, set(item))
        expected = self.sql("SELECT COUNT(*) FROM calendar_item WHERE substr(starts_at, 1, 10) BETWEEN ? AND ?",
                            (answer["from"], answer["to"]))[0][0]
        self.assertEqual(len(answer["items"]), expected)
        self.assertEqual(self.ok("calendar", "--from", "2026-03-10")["to"], "2026-03-16")
        self.assertEqual(self.ok("calendar", "--from", "9999-12-30")["to"], "9999-12-31")
        self.assertEqual(self.ok("calendar", "--from", "2026-01-01", "--to", "2027-01-01")["to"], "2027-01-01")
        long = self.refused("invalid", "calendar", "--from", "2026-01-01", "--to", "2027-01-02")  # 367 days
        self.assertIn("at most 366 days", long["message"])
        self.assertIn("real date", self.refused("invalid", "calendar", "--from", "2026-02-30")["message"])
        self.assertEqual(self.refused("invalid", "calendar", "--from", "2026-05-01", "--to", "2026-04-01")["message"],
                         "The end date is before the start date.")

    def test_money(self):
        today = dt.date.today()
        answer = self.ok("money")
        self.assertEqual((answer["year"], answer["month"]), (today.year, today.month))
        answer = self.ok("money", "--year", "2026", "--month", "05")
        self.assertEqual((answer["year"], answer["month"]), (2026, 5))
        expected = money.month_totals(self.ro(), 2026, 5)
        for key in ("offerings", "expenses", "balance"):
            self.assertIs(type(answer[key]), int, key)  # whole dong, never a float
            self.assertEqual(answer[key], expected[key])
            self.assertEqual(answer[f"{key}_text"], money.format_vnd(expected[key]))
        self.assertEqual(answer["balance"], answer["offerings"] - answer["expenses"])
        self.assertGreater(answer["offerings"], 0)
        self.assertEqual(self.refused("invalid", "money", "--month", "13")["message"],
                         "Month must be a whole number from 1 to 12.")
        self.assertEqual(self.refused("invalid", "money", "--year", "1800")["message"],
                         "Year: use a year from 1900 to 9999.")
        self.refused("invalid", "money", "--year", "abc")

    def test_care_due(self):
        answer = self.ok("care-due")
        self.assertEqual(answer["reminder_months"], 3)
        self.assertEqual(answer["people"], care.needs_visit(self.ro()))
        self.assertTrue(answer["people"])
        self.assertLessEqual({"person_id", "full_name", "last_visit"}, set(answer["people"][0]))

    def test_lists(self):
        answer = self.ok("lists")
        conn = self.ro()
        for name in ("status", "fund", "spending_category"):
            self.assertEqual(answer[name], [{"id": r["id"], "name": r["name"], "code": r["code"]}
                                            for r in lists.get_list(conn, name)])
            self.assertTrue(answer[name])
        self.assertEqual(answer["calendar_kind"], list(schema.CALENDAR_KINDS))

    def test_missing_ids_are_not_found(self):
        self.assertEqual(self.refused("not_found", "person", "999999")["message"], "No Person with id 999999.")
        self.assertEqual(self.refused("not_found", "family", "999999")["message"], "No Family with id 999999.")
        self.refused("not_found", "person", "99999999999999999999")  # too big for SQLite: no such row

    def test_bad_ids_are_invalid(self):
        self.assertEqual(self.refused("invalid", "person", "abc")["message"], "Person must be a whole number.")
        self.assertEqual(self.refused("invalid", "family", "0")["message"], "Family must be a whole number above 0.")
        self.refused("invalid", "person", "-3")

    def test_bad_usage_is_json_with_exit_2(self):
        for argv in ([], ["bogus"], ["person"], ["person", "1", "--nope"], ["search"], ["status", "extra"]):
            answer = self.refused("usage", *argv)
            self.assertIn("--help", answer["message"])

    def test_help_is_json(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = agent.main(["--help"])
        answer = json.loads(out.getvalue())
        self.assertEqual((code, answer["ok"], answer["command"]), (0, True, "help"))
        for name in ("status", "search", "person", "family", "calendar", "money", "care-due", "lists"):
            self.assertIn(name, answer["help"])

    def test_a_real_process_prints_utf8_json_with_vietnamese_names(self):
        name = self.sql("SELECT full_name FROM person WHERE id = 1")[0][0]
        proc = self.subprocess_agent("search", *name.split())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, b"")
        self.assertIn(name.encode("utf-8"), proc.stdout)  # real UTF-8, not \u escapes
        self.assertNotIn(b"\\u", proc.stdout)
        answer = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual(answer["results"][0]["full_name"], name)


class NoCopyTest(unittest.TestCase):
    def setUp(self):
        self.root = _support.temp_folder(self)

    def main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                mock.patch.dict(os.environ, {}, clear=False) as env:
            env.pop(paths.ENV_COPY, None)
            env.pop(paths.ENV_HOME, None)
            code = agent.main(list(argv))
        return code, json.loads(out.getvalue())

    def test_no_church_copy_is_refused(self):
        empty = self.root / "empty"
        empty.mkdir()
        cases = (
            ["status", "--copy", str(empty), "--copies-root", str(self.root)],  # no church.db
            ["status", "--copies-root", str(empty)],  # no --copy and no current.txt
            ["status", "--copy", str(self.root / "OneDrive" / "c"), "--copies-root", str(self.root)],
        )
        for argv in cases:
            code, answer = self.main(*argv)
            self.assertEqual((code, answer["ok"], answer["error"]), (1, False, "no_copy"), answer)
        self.assertIn("OneDrive", answer["message"])

    def test_connect_ro_refuses_what_is_not_a_church_copy(self):
        not_db = self.root / "a" / db.DB_NAME
        not_db.parent.mkdir()
        not_db.write_bytes(b"hello, not a database")
        other = self.root / "b" / db.DB_NAME
        other.parent.mkdir()
        conn = sqlite3.connect(other)
        conn.execute("PRAGMA user_version = 7")
        conn.close()
        for path in (not_db, other, self.root / "none" / db.DB_NAME, self.root / "OneDrive" / db.DB_NAME):
            with self.assertRaises(agent.AgentError) as caught:
                agent.connect_ro(path).close()
            self.assertEqual(caught.exception.code, "no_copy", path)


class ConnectRoTest(_support.CopyTestCase):
    def test_connect_ro_opens_mode_ro_and_a_write_fails(self):
        self.conn.close()
        path = self.folder / db.DB_NAME
        before = sha(path)
        with mock.patch.object(agent.sqlite3, "connect", wraps=sqlite3.connect) as spy:
            conn = agent.connect_ro(path)
        self.addCleanup(conn.close)
        target = spy.call_args.args[0]
        self.assertTrue(target.startswith("file:"), target)
        self.assertTrue(target.endswith("?mode=ro"), target)
        self.assertIs(spy.call_args.kwargs.get("uri"), True)
        self.assertIs(conn.row_factory, sqlite3.Row)
        with self.assertRaises(sqlite3.OperationalError):
            conn.execute("INSERT INTO setting (key, value) VALUES ('hermes_door', 'on')")
        with self.assertRaises(sqlite3.OperationalError):
            conn.execute("UPDATE setting SET value = 'x'")
        conn.close()
        self.assertEqual(sha(path), before)


class DoorSettingTest(_support.CopyTestCase):
    def test_hermes_door_setting(self):
        self.assertEqual(settings.HERMES_DOOR, "hermes_door")
        self.assertIsNone(settings.get_setting(self.conn, "hermes_door"))  # a new church copy: no row = off
        self.assertFalse(settings.hermes_door_on(self.conn))
        settings.set_setting(self.conn, "hermes_door", "on")
        self.assertTrue(settings.hermes_door_on(self.conn))
        settings.set_setting(self.conn, "hermes_door", "off")
        self.assertFalse(settings.hermes_door_on(self.conn))
        for bad in ("ON", "On", "yes", "1", "true", "", "o n", " on", "on ", "bật", None):
            with self.assertRaises(ValueError) as caught:
                settings.set_setting(self.conn, "hermes_door", bad)
            self.assertEqual(str(caught.exception), "Hermes door must be On or Off.", bad)
        self.assertEqual(settings.get_setting(self.conn, "hermes_door"), "off")


class DoorSettingPageTest(PagesTestBase):
    """The Settings page, through the real server, on its own fake church."""

    def door(self):
        return settings.get_setting(self.db(), settings.HERMES_DOOR)

    def reset(self):
        conn = self.db()
        conn.execute("DELETE FROM setting WHERE key = 'hermes_door'")
        settings.set_setting(conn, "care_reminder_months", "3")

    def form(self, **extra):
        return {"church_name": fake.CHURCH_NAME, "care_reminder_months": "3", **extra}

    def test_the_field_shows_off_by_default(self):
        self.assertIsNone(self.door())
        page = self.page("/settings")
        self.assertIn('<label for="f-hermes_door">Hermes door</label>', page)
        self.assertRegex(page, r'<select class="input" id="f-hermes_door" name="hermes_door"[^>]*>'
                               r'<option value="off" selected>Off</option><option value="on">On</option></select>')
        self.assertIn("Optional. On lets the Hermes helper on this computer read this church copy and save new "
                      "records after you say yes. It never sees Private notes.", page)

    def test_save_on_and_off_and_keep_the_door_when_the_field_is_absent(self):
        self.addCleanup(self.reset)
        headers, _ = self.post("/settings", self.form(hermes_door="on"))
        self.assertEqual(self.door(), "on")
        page = self.page(headers["location"])
        self.assertIn("Hermes door on.", page)
        self.assertIn('<option value="on" selected>On</option>', page)
        headers, _ = self.post("/settings", self.form(care_reminder_months="4"))  # an old form: no hermes_door
        self.assertEqual(self.door(), "on")
        self.assertEqual(care.reminder_months(self.db()), 4)
        self.assertIn("Hermes door on.", self.page(headers["location"]))
        headers, _ = self.post("/settings", self.form(hermes_door="off"))
        self.assertEqual(self.door(), "off")
        self.assertIn("Hermes door off.", self.page(headers["location"]))

    def test_a_bad_value_is_refused_with_400(self):
        before = self.door()
        for bad in ("maybe", "ON", "", " on"):
            _h, page = self.post("/settings", self.form(hermes_door=bad, church_name="Hội Thánh Đổi Tên"),
                                 expect=400)
            self.assertIn('<p class="error" id="f-hermes_door-error">Hermes door must be On or Off.</p>', page, bad)
            self.assertEqual(self.door(), before, bad)
            self.assertEqual(settings.get_setting(self.db(), "church_name"), fake.CHURCH_NAME)


class AgentSourceTest(unittest.TestCase):
    def test_the_agent_never_names_private_notes(self):
        self.assertNotIn("private_note", AGENT_SOURCE)
        self.assertNotIn("include_private=True", AGENT_SOURCE)
        self.assertIn("person_story(conn, pid, include_private=False)", AGENT_SOURCE)
        self.assertEqual(re.findall(r"person_story\([^)]*\)", AGENT_SOURCE),
                         ["person_story(conn, pid, include_private=False)"])

    def test_no_product_module_imports_the_agent(self):
        pattern = re.compile(r"^\s*(import\s+churchmgr\.agent|from\s+churchmgr\.agent\s|from\s+\.+agent\s"
                             r"|from\s+(churchmgr|\.+)\s+import\s+[^\n]*\bagent\b)", re.M)
        files = [p for p in (ROOT / "churchmgr").rglob("*.py") if p.name != "agent.py"]
        files += [ROOT / "app.py", ROOT / "verify.py"]
        hits = [str(p) for p in files if pattern.search(p.read_text(encoding="utf-8"))]
        self.assertEqual(hits, [])
        self.assertTrue(pattern.search("from churchmgr import agent, db"))  # the pattern itself works
        self.assertTrue(pattern.search("from . import agent"))


if __name__ == "__main__":
    unittest.main()
