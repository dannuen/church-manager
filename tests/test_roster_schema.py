"""Schema version 2: the Service role tables, their rules, the default Service roles and the move from
version 1 (card RO-1, decisions D2 and D3)."""

import hashlib
import sqlite3
import unittest

import _support  # noqa: F401  (puts the repo on sys.path)
from _support import CopyTestCase, temp_folder
from churchmgr import agent, db, handover, i18n, lists, people, schema

V2_TABLES = ("service_role_link", "rotation_place", "skipped_date", "service_role")  # links first: they point at roles

# D3: (name, weekday, done_by, every, month_start, month_start_from, sort_order, active)
DEFAULTS = {
    "vi": [("Bồi linh", 3, "person", 1, 0, None, 1, 1),
           ("Hướng dẫn chương trình", 6, "person", 1, 1, None, 2, 1),
           ("Hướng dẫn dâng hiến", 6, "person", 1, 0, None, 3, 1),
           ("Ban phụ trách", 6, "ministry", 2, 0, None, 4, 1)],
    "en": [("Bồi linh", 3, "person", 1, 0, None, 1, 1),
           ("Service leader", 6, "person", 1, 1, None, 2, 1),
           ("Offering leader", 6, "person", 1, 0, None, 3, 1),
           ("Ministry in charge", 6, "ministry", 2, 0, None, 4, 1)],
}


def service_roles(conn):
    return [tuple(r) for r in conn.execute(
        "SELECT name, weekday, done_by, every, month_start, month_start_from, sort_order, active "
        "FROM service_role ORDER BY sort_order")]


def triggers(conn):
    return {r[0]: r[1] for r in conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'trigger'")}


def version(conn):
    return conn.execute("PRAGMA user_version").fetchone()[0]


def make_v1_copy(test, lang="vi"):
    """A church copy the way version 1 of the app left it: no V2 tables (so none of their triggers and
    indexes), ``user_version`` 1. Returns ``(folder, open connection)``."""
    folder = temp_folder(test) / "copy"
    conn = db.create_church_copy(folder, "Hội Thánh Thử", lang=lang)
    test.addCleanup(conn.close)
    for table in V2_TABLES:
        conn.execute(f"DROP TABLE {table}")
    conn.execute("PRAGMA user_version = 1")
    left = conn.execute("SELECT name FROM sqlite_master WHERE tbl_name IN (?, ?, ?, ?)", V2_TABLES).fetchall()
    test.assertEqual(left, [])
    return folder, conn


class NewCopyTest(unittest.TestCase):
    def test_version_numbers(self):
        self.assertEqual((schema.SCHEMA_VERSION, schema.KNOWN_VERSIONS), (2, (1, 2)))

    def test_version_1_statements_are_the_old_ones(self):
        """make_v1_copy builds with this code, so it is a real version-1 copy only if the old statements did not
        change. The hashes are of schema.TRIGGERS and schema.TABLES + schema.INDEXES at commit 99cac03
        (the last version-1 app), joined with a new line."""
        def sha(statements):
            return hashlib.sha256("\n".join(statements).encode("utf-8")).hexdigest()
        self.assertEqual((len(schema.TRIGGERS_V1), sha(schema.TRIGGERS_V1)),
                         (24, "03b6d2d4d6ea353bb9bd0cba4e75c39fb8209b391ddc0411905e30ad332f4897"))
        self.assertEqual((len(schema.TABLES + schema.INDEXES), sha(schema.TABLES + schema.INDEXES)),
                         (36, "52087dfffb16abab090e226de7976768290a7c1d4064b0fdecb354fde83e2de1"))

    def test_new_copy_is_version_2_with_the_default_service_roles(self):
        for lang in ("vi", "en"):
            with self.subTest(lang=lang):
                conn = db.create_church_copy(temp_folder(self) / "copy", "Hội Thánh Thử", lang=lang)
                self.addCleanup(conn.close)
                self.assertEqual(version(conn), 2)
                self.assertEqual(service_roles(conn), DEFAULTS[lang])
                for table in ("rotation_place", "service_role_link", "skipped_date"):
                    self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0, table)
                self.assertEqual(sorted(triggers(conn).values()), sorted(schema.TRIGGERS))


class MigrationTest(unittest.TestCase):
    def test_version_1_copy_becomes_version_2(self):
        for lang in ("vi", "en"):
            with self.subTest(lang=lang):
                folder, conn = make_v1_copy(self, lang)
                member = lists.find_item(conn, "status", code="member")["id"]
                pid = people.add_person(conn, "Lê Văn An", status_id=member, start_date="2010-01-01")
                before = triggers(conn)
                conn.close()
                conn = db.open_church_copy(folder)
                self.addCleanup(conn.close)
                self.assertEqual(version(conn), 2)
                self.assertEqual(service_roles(conn), DEFAULTS[lang])
                self.assertEqual(conn.execute("SELECT full_name FROM person WHERE id = ?", (pid,)).fetchone()[0],
                                 "Lê Văn An")
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM person_status").fetchone()[0], 1)
                after = triggers(conn)
                self.assertEqual({name: after.get(name) for name in before}, before)  # old triggers byte-equal
                self.assertEqual(sorted(after.values()), sorted(schema.TRIGGERS))
                self.assertEqual(schema.stale_triggers(conn), [])
                # The second open has nothing to do: no schema write.
                mark = conn.execute("PRAGMA schema_version").fetchone()[0]
                conn.close()
                conn = db.open_church_copy(folder)
                self.addCleanup(conn.close)
                self.assertEqual(conn.execute("PRAGMA schema_version").fetchone()[0], mark)

    def test_no_language_row_gives_vietnamese_names(self):
        folder, conn = make_v1_copy(self, "en")
        conn.execute("DELETE FROM setting WHERE key = 'language'")
        conn.close()
        conn = db.open_church_copy(folder)
        self.addCleanup(conn.close)
        self.assertEqual(service_roles(conn), DEFAULTS["vi"])

    def test_migration_is_one_transaction(self):
        folder, conn = make_v1_copy(self)
        conn.execute("CREATE TABLE skipped_date (x)")  # the last V2 table cannot be made
        conn.close()
        with self.assertRaises(db.ChurchCopyError) as ctx:  # a page shows the text of a key, not SQLite text
            db.open_church_copy(folder)
        self.assertEqual((ctx.exception.key, ctx.exception.params["needed"]), ("errors.copy_upgrade", 2))
        self.assertIsInstance(ctx.exception.__cause__, sqlite3.OperationalError)
        self.assertIn("could not be brought to database version 2 (table skipped_date already exists). "
                      "It was not changed.", str(ctx.exception))
        self.assertIn("không thay đổi", i18n.error_text(ctx.exception, "vi"))
        conn = db.connect(folder / db.DB_NAME)
        self.addCleanup(conn.close)
        self.assertEqual(version(conn), 1)
        made = conn.execute("SELECT name FROM sqlite_master WHERE name IN ('service_role', 'rotation_place', "
                            "'service_role_link')").fetchall()
        self.assertEqual(made, [])

    def test_version_3_still_refused_with_the_old_message(self):
        folder = temp_folder(self) / "copy"
        conn = db.create_church_copy(folder, "Hội Thánh Thử")
        conn.execute("PRAGMA user_version = 3")
        conn.close()
        with self.assertRaises(db.ChurchCopyError) as ctx:
            db.open_church_copy(folder)
        self.assertEqual((ctx.exception.key, ctx.exception.params["version"], ctx.exception.params["needed"]),
                         ("errors.copy_version", 3, 2))
        self.assertTrue(str(ctx.exception).endswith("church.db has database version 3; this app needs version 2."),
                        str(ctx.exception))
        with self.assertRaises(agent.AgentError) as ctx:
            agent.connect_ro(folder / db.DB_NAME)
        self.assertEqual(ctx.exception.code, "no_copy")
        self.assertTrue(ctx.exception.message.endswith("has database version 3; this app needs version 2."))
        with self.assertRaises(handover.HandoverError) as ctx:
            handover._read_source(folder / db.DB_NAME)
        self.assertEqual(ctx.exception.key, "copies.err_db_version")

    def test_read_only_doors_accept_a_version_1_copy(self):
        folder, conn = make_v1_copy(self)
        conn.close()
        ro = agent.connect_ro(folder / db.DB_NAME)
        self.addCleanup(ro.close)
        self.assertEqual(version(ro), 1)
        slug, notes = handover._read_source(folder / db.DB_NAME)
        self.assertEqual((slug, notes), ("hoi-thanh-thu", []))


class ServiceRoleRulesTest(CopyTestCase):
    def setUp(self):
        super().setUp()
        self.item_id = self.conn.execute(
            "INSERT INTO calendar_item (kind, title, starts_at) VALUES ('Service', 'Sunday service', "
            "'2026-05-03 08:00')").lastrowid
        self.person = people.add_person(self.conn, "Lê Văn An")
        self.other = people.add_person(self.conn, "Trần Thị Bình")
        self.leader = self.role("Service leader")
        self.offering_leader = self.role("Offering leader")
        self.in_charge = self.role("Ministry in charge")
        self.youth = self.item("ministry", name="Youth")
        self.fund = self.item("fund", name="General")

    def role(self, name):
        return self.conn.execute("SELECT id FROM service_role WHERE name = ?", (name,)).fetchone()[0]

    def link(self, role_id, person_id=None, ministry_id=None, start="2026-04-20", item_id=None):
        return self.conn.execute(
            "INSERT INTO service_role_link (calendar_item_id, service_role_id, person_id, ministry_id, start_date) "
            "VALUES (?, ?, ?, ?, ?)", (item_id or self.item_id, role_id, person_id, ministry_id, start)).lastrowid

    def test_link_is_never_deleted_and_only_closed_once(self):
        link = self.link(self.leader, self.person)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "history is never deleted"):
            self.conn.execute("DELETE FROM service_role_link WHERE id = ?", (link,))
        later = self.conn.execute("INSERT INTO calendar_item (kind, title, starts_at) VALUES ('Service', "
                                  "'Sunday service', '2026-05-10 08:00')").lastrowid
        for change in (f"person_id = {self.other}", f"person_id = NULL, ministry_id = {self.youth}",
                       "start_date = '2026-04-21'", f"service_role_id = {self.offering_leader}",
                       f"calendar_item_id = {later}", f"id = {link} + 1",
                       "end_date = '2026-04-19'",  # a close before the start date
                       f"end_date = '2026-04-27', person_id = {self.other}"):  # a close that changes more
            with self.subTest(change=change), self.assertRaisesRegex(sqlite3.IntegrityError,
                                                                     "history is never changed"):
                self.conn.execute(f"UPDATE service_role_link SET {change} WHERE id = ?", (link,))
        self.conn.execute("UPDATE service_role_link SET end_date = '2026-04-27' WHERE id = ?", (link,))
        for change in ("end_date = '2026-04-28'", "end_date = NULL"):  # closed once: no second close, no reopen
            with self.subTest(change=change), self.assertRaisesRegex(sqlite3.IntegrityError,
                                                                     "history is never changed"):
                self.conn.execute(f"UPDATE service_role_link SET {change} WHERE id = ?", (link,))
        row = self.conn.execute("SELECT person_id, start_date, end_date FROM service_role_link").fetchone()
        self.assertEqual(tuple(row), (self.person, "2026-04-20", "2026-04-27"))

    def test_one_open_link_per_item_and_role(self):
        first = self.link(self.leader, self.person)
        with self.assertRaises(sqlite3.IntegrityError):
            self.link(self.leader, self.other)
        self.link(self.offering_leader, self.other)  # another Service role on the same item
        self.conn.execute("UPDATE service_role_link SET end_date = '2026-04-27' WHERE id = ?", (first,))
        self.link(self.leader, self.other, start="2026-04-27")  # a swap: the new open row
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM service_role_link").fetchone()[0], 3)

    def test_link_holds_a_person_or_a_ministry(self):
        for person_id, ministry_id in ((None, None), (self.person, self.youth)):  # neither, both
            with self.subTest(person_id=person_id), self.assertRaises(sqlite3.IntegrityError):
                self.link(self.in_charge, person_id, ministry_id)
        self.link(self.in_charge, ministry_id=self.youth)
        with self.assertRaises(sqlite3.IntegrityError):  # end before start
            self.conn.execute("INSERT INTO service_role_link (calendar_item_id, service_role_id, person_id, "
                              "start_date, end_date) VALUES (?, ?, ?, '2026-04-20', '2026-04-19')",
                              (self.item_id, self.leader, self.person))

    def test_service_role_is_never_deleted_and_keeps_done_by(self):
        with self.assertRaisesRegex(sqlite3.IntegrityError, "never deleted"):
            self.conn.execute("DELETE FROM service_role WHERE id = ?", (self.leader,))
        with self.assertRaisesRegex(sqlite3.IntegrityError, "done_by"):
            self.conn.execute("UPDATE service_role SET done_by = 'ministry' WHERE id = ?", (self.leader,))
        self.conn.execute("UPDATE service_role SET done_by = 'person', name = 'MC', active = 0 WHERE id = ?",
                          (self.leader,))  # same done_by, other fields change
        self.assertEqual(tuple(self.conn.execute("SELECT name, done_by, active FROM service_role WHERE id = ?",
                                                 (self.leader,)).fetchone()), ("MC", "person", 0))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM service_role").fetchone()[0], 4)

    def test_service_role_checks(self):
        add = "INSERT INTO service_role (name, weekday, done_by, every, month_start_from) VALUES (?, ?, ?, ?, ?)"
        for bad in (("  ", 6, "person", 1, None), ("Bồi linh", 6, "person", 1, None), ("X", 7, "person", 1, None),
                    ("X", 1.5, "person", 1, None), ("X", 6, "family", 1, None), ("X", 6, "person", 0, None),
                    ("X", 6, "person", 9, None), ("X", 6, "person", 1, "2026-1"), ("X", 6, "person", 1, "2026-01-01")):
            with self.subTest(bad=bad), self.assertRaises(sqlite3.IntegrityError):
                self.conn.execute(add, bad)
        self.conn.execute(add, ("X", 0, "person", 8, "2026-01"))

    def test_ministry_id_must_be_a_ministry_list_item(self):
        with self.assertRaisesRegex(sqlite3.IntegrityError, "ministry_id must be an item of the ministry list"):
            self.link(self.in_charge, ministry_id=self.fund)
        self.link(self.leader, self.person)  # NULL ministry_id is fine
        place = "INSERT INTO rotation_place (service_role_id, position, person_id, ministry_id) VALUES (?, ?, ?, ?)"
        with self.assertRaisesRegex(sqlite3.IntegrityError, "ministry_id must be an item of the ministry list"):
            self.conn.execute(place, (self.in_charge, 1, None, self.fund))
        self.conn.execute(place, (self.in_charge, 1, None, self.youth))
        self.conn.execute(place, (self.leader, 1, self.person, None))  # NULL ministry_id is fine
        with self.assertRaisesRegex(sqlite3.IntegrityError, "ministry_id must be an item of the ministry list"):
            self.conn.execute("UPDATE rotation_place SET ministry_id = ? WHERE service_role_id = ?",
                              (self.fund, self.in_charge))

    def test_rotation_place_and_skipped_date_rows(self):
        place = "INSERT INTO rotation_place (service_role_id, position, person_id, ministry_id) VALUES (?, ?, ?, ?)"
        self.conn.execute(place, (self.leader, 1, self.person, None))
        for bad in ((self.leader, 1, self.other, None), (self.leader, 0, self.other, None),
                    (self.leader, 2, None, None), (self.leader, 2, self.other, self.youth)):
            with self.subTest(bad=bad), self.assertRaises(sqlite3.IntegrityError):
                self.conn.execute(place, bad)
        self.conn.execute("DELETE FROM rotation_place")  # a Rotation is an order, not a past link
        skip = "INSERT INTO skipped_date (date, reason) VALUES (?, ?)"
        for bad in ((None, "Tết"), ("17/02/2026", "Tết"), ("2026-02-17", " ")):
            with self.subTest(bad=bad), self.assertRaises(sqlite3.IntegrityError):
                self.conn.execute(skip, bad)
        self.conn.execute(skip, ("2026-02-17", "Tết"))
        self.conn.execute("DELETE FROM skipped_date")


if __name__ == "__main__":
    unittest.main()
