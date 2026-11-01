import pathlib
import re
import sqlite3
import unicodedata
import unittest

import _support
from _support import CopyTestCase, temp_folder
from churchmgr import db, lists, paths, schema, settings


def nfc(s):
    return unicodedata.normalize("NFC", s)


def nfd(s):
    return unicodedata.normalize("NFD", s)


class OneDriveTest(unittest.TestCase):
    def test_onedrive_path_refused_any_case(self):
        for p in (r"C:\Users\x\OneDrive\Desktop\copy", r"C:\Users\x\onedrive - Personal\c",
                  r"D:\ONEDRIVE\c", "/home/x/OneDrive/c"):
            with self.assertRaises(paths.CopyPathError, msg=p):
                paths.check_not_onedrive(p)

    def test_normal_path_allowed(self):
        tmp = temp_folder(self)
        self.assertEqual(paths.check_not_onedrive(tmp / "copy"), (tmp / "copy").resolve())

    def test_create_in_onedrive_refused_and_nothing_made(self):
        tmp = temp_folder(self)
        target = tmp / "OneDrive - Personal" / "copy"
        with self.assertRaises(paths.CopyPathError):
            db.create_church_copy(target, "Hội Thánh")
        self.assertFalse((tmp / "OneDrive - Personal").exists())
        with self.assertRaises(paths.CopyPathError):
            db.open_church_copy(target)
        with self.assertRaises(paths.CopyPathError):
            db.connect(target / "church.db")


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = temp_folder(self)
        self.env = {"LOCALAPPDATA": str(self.tmp / "local")}  # never the real one

    def test_first_run_uses_localappdata_default(self):
        copy, root = paths.resolve(None, None, self.env)
        self.assertIsNone(copy)
        self.assertEqual(root, (self.tmp / "local" / "ChurchManager").resolve())
        self.assertFalse(root.exists())  # resolve creates nothing

    def test_copies_root_order(self):
        env = dict(self.env, CHURCH_MANAGER_HOME=str(self.tmp / "home"))
        self.assertEqual(paths.resolve(None, str(self.tmp / "arg"), env)[1], (self.tmp / "arg").resolve())
        self.assertEqual(paths.resolve(None, None, env)[1], (self.tmp / "home").resolve())
        # parent of --copy when no root is given
        copy, root = paths.resolve(str(self.tmp / "x" / "mychurch"), None, self.env)
        self.assertEqual(copy, (self.tmp / "x" / "mychurch").resolve())
        self.assertEqual(root, (self.tmp / "x").resolve())
        # parent of env CHURCH_MANAGER_COPY too
        env2 = dict(self.env, CHURCH_MANAGER_COPY=str(self.tmp / "y" / "c2"))
        self.assertEqual(paths.resolve(None, None, env2), ((self.tmp / "y" / "c2").resolve(), (self.tmp / "y").resolve()))

    def test_copy_order(self):
        root = self.tmp / "root"
        paths.write_current(root, root / "from-current")
        self.assertEqual((root / "current.txt").read_text(encoding="utf-8").strip(), "from-current")
        env = dict(self.env, CHURCH_MANAGER_COPY=str(self.tmp / "from-env"))
        self.assertEqual(paths.resolve(str(self.tmp / "from-arg"), str(root), env)[0], (self.tmp / "from-arg").resolve())
        self.assertEqual(paths.resolve(None, str(root), env)[0], (self.tmp / "from-env").resolve())
        self.assertEqual(paths.resolve(None, str(root), self.env)[0], (root / "from-current").resolve())

    def test_write_current_outside_root_keeps_full_path(self):
        root = self.tmp / "root"
        paths.write_current(root, self.tmp / "elsewhere")
        self.assertEqual(paths.resolve(None, str(root), self.env)[0], (self.tmp / "elsewhere").resolve())

    def test_onedrive_refused_in_resolve_and_write_current(self):
        bad = str(self.tmp / "OneDrive" / "c")
        with self.assertRaises(paths.CopyPathError):
            paths.resolve(bad, None, self.env)
        with self.assertRaises(paths.CopyPathError):
            paths.resolve(None, bad, self.env)
        with self.assertRaises(paths.CopyPathError):
            paths.resolve(None, None, {"CHURCH_MANAGER_HOME": bad})
        with self.assertRaises(paths.CopyPathError):
            paths.write_current(self.tmp / "root", bad)
        root = self.tmp / "root2"
        root.mkdir()
        (root / "current.txt").write_text(bad, encoding="utf-8")
        with self.assertRaises(paths.CopyPathError):
            paths.resolve(None, str(root), self.env)


class CreateOpenTest(unittest.TestCase):
    def setUp(self):
        self.tmp = temp_folder(self)
        self.folder = self.tmp / "hoi-thanh"

    def test_create_church_copy(self):
        conn = db.create_church_copy(self.folder, nfd("Hội Thánh Tin Lành"))
        self.addCleanup(conn.close)
        self.assertTrue((self.folder / "church.db").is_file())
        self.assertTrue((self.folder / "documents").is_dir())
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 1)
        self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "delete")
        self.assertIs(conn.row_factory, sqlite3.Row)
        self.assertEqual(settings.get_setting(conn, "church_name"), "Hội Thánh Tin Lành")  # NFC
        self.assertEqual(settings.get_setting(conn, "care_reminder_months"), "3")
        self.assertEqual(settings.get_int_setting(conn, "care_reminder_months", 99), 3)

    def test_default_lists_all_there_and_only_them(self):
        conn = db.create_church_copy(self.folder, "Hội Thánh")
        self.addCleanup(conn.close)
        for list_name, items in schema.DEFAULT_LISTS.items():
            got = [(r["code"], r["name"]) for r in lists.get_list(conn, list_name)]
            self.assertEqual(got, list(items), list_name)
        total = sum(len(v) for v in schema.DEFAULT_LISTS.values())
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM list_item").fetchone()[0], total)
        self.assertEqual(
            [r["name"] for r in lists.get_list(conn, "recipient")], ["Chính quyền", "Giáo hội", "Hội Thánh"]
        )
        for _, items in schema.DEFAULT_LISTS.items():
            for _, name in items:
                self.assertEqual(name, nfc(name))
        for table in ("person", "family", "private_note", "offering", "calendar_item", "sent_document"):
            self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0, table)

    def test_create_twice_refused_and_copy_kept(self):
        conn = db.create_church_copy(self.folder, "Hội Thánh A")
        conn.close()
        with self.assertRaises(db.ChurchCopyError):
            db.create_church_copy(self.folder, "Hội Thánh B")
        conn = db.open_church_copy(self.folder)
        self.addCleanup(conn.close)
        self.assertEqual(settings.get_setting(conn, "church_name"), "Hội Thánh A")

    def test_create_with_empty_name_makes_no_db(self):
        with self.assertRaises(ValueError):
            db.create_church_copy(self.folder, "   ")
        self.assertFalse((self.folder / "church.db").exists())

    def test_open_missing_copy(self):
        with self.assertRaises(db.ChurchCopyError):
            db.open_church_copy(self.folder)

    def test_open_wrong_version(self):
        conn = db.create_church_copy(self.folder, "Hội Thánh")
        conn.execute("PRAGMA user_version = 7")
        conn.close()
        with self.assertRaises(db.ChurchCopyError):
            db.open_church_copy(self.folder)

    def test_open_not_a_database(self):
        self.folder.mkdir()
        (self.folder / "church.db").write_bytes(b"this is not sqlite" * 100)
        with self.assertRaises(db.ChurchCopyError):
            db.open_church_copy(self.folder)

    def test_open_makes_missing_documents_folder(self):
        db.create_church_copy(self.folder, "Hội Thánh").close()
        (self.folder / "documents").rmdir()
        conn = db.open_church_copy(self.folder)
        self.addCleanup(conn.close)
        self.assertTrue((self.folder / "documents").is_dir())
        self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)


class TransactionTest(CopyTestCase):
    def test_rollback_on_error(self):
        with self.assertRaises(RuntimeError):
            with db.transaction(self.conn):
                self.conn.execute("INSERT INTO setting (key, value) VALUES ('a', '1')")
                raise RuntimeError("stop")
        self.assertIsNone(settings.get_setting(self.conn, "a"))
        self.assertFalse(self.conn.in_transaction)

    def test_nested_rollback_keeps_outer(self):
        with db.transaction(self.conn):
            self.conn.execute("INSERT INTO setting (key, value) VALUES ('outer', '1')")
            with self.assertRaises(RuntimeError):
                with db.transaction(self.conn):
                    self.conn.execute("INSERT INTO setting (key, value) VALUES ('inner', '1')")
                    raise RuntimeError("stop")
        self.assertEqual(settings.get_setting(self.conn, "outer"), "1")
        self.assertIsNone(settings.get_setting(self.conn, "inner"))


class SettingsTest(CopyTestCase):
    def test_set_and_get(self):
        settings.set_setting(self.conn, "church_name", nfd(" Hội Thánh Mới "))
        self.assertEqual(settings.get_setting(self.conn, "church_name"), "Hội Thánh Mới")
        settings.set_setting(self.conn, "care_reminder_months", 6)
        self.assertEqual(settings.get_int_setting(self.conn, "care_reminder_months", 3), 6)
        self.assertEqual(settings.get_setting(self.conn, "missing", "x"), "x")

    def test_bad_values_refused(self):
        for bad in ("0", "abc", "1.5", "-2", "121"):
            with self.assertRaises(ValueError, msg=bad):
                settings.set_setting(self.conn, "care_reminder_months", bad)
        with self.assertRaises(ValueError):
            settings.set_setting(self.conn, "church_name", "  ")
        self.assertEqual(settings.get_setting(self.conn, "care_reminder_months"), "3")


class ListsTest(CopyTestCase):
    def test_add_rename_hide(self):
        new_id = lists.add_item(self.conn, "ministry", nfd("Thờ phượng"))
        self.assertEqual(lists.get_item(self.conn, new_id)["name"], "Thờ phượng")
        self.assertEqual([r["name"] for r in lists.get_list(self.conn, "ministry")][-1], "Thờ phượng")
        lists.rename_item(self.conn, new_id, "Ban nhạc")
        lists.set_active(self.conn, new_id, False)
        self.assertNotIn("Ban nhạc", [r["name"] for r in lists.get_list(self.conn, "ministry")])
        self.assertIn("Ban nhạc", [r["name"] for r in lists.get_list(self.conn, "ministry", include_hidden=True)])
        lists.set_active(self.conn, new_id, True)
        self.assertIn("Ban nhạc", [r["name"] for r in lists.get_list(self.conn, "ministry")])

    def test_duplicates_and_unknown_list_refused(self):
        with self.assertRaises(ValueError):
            lists.add_item(self.conn, "fund", "General")
        with self.assertRaises(ValueError):
            lists.rename_item(self.conn, self.item("fund", name="Building"), "General")
        with self.assertRaises(ValueError):
            lists.add_item(self.conn, "colour", "Blue")
        with self.assertRaises(ValueError):
            lists.get_list(self.conn, "nope")

    def test_require_item_checks_the_list(self):
        fund = self.item("fund", name="General")
        self.assertEqual(lists.require_item(self.conn, fund, "fund")["name"], "General")
        with self.assertRaises(ValueError):
            lists.require_item(self.conn, fund, "status")
        with self.assertRaises(ValueError):
            lists.require_item(self.conn, 99999, "fund")

    def test_lists_have_no_delete(self):
        public = [n for n in dir(lists) if not n.startswith("_")]
        self.assertFalse([n for n in public if re.search(r"delete|remove|drop", n)], public)
        fund = self.item("fund", name="Missions")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "never deleted"):
            self.conn.execute("DELETE FROM list_item WHERE id = ?", (fund,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE list_item SET list_name = 'status' WHERE id = ?", (fund,))
        self.assertIsNotNone(lists.get_item(self.conn, fund))


class SchemaRulesTest(CopyTestCase):
    def setUp(self):
        super().setUp()
        self.fund = self.item("fund", name="General")
        self.rent = self.item("spending_category", name="Rent")

    def offering(self, amount, **extra):
        cols = {"date": "2026-05-03", "amount": amount, "fund_id": self.fund, "created_at": "2026-05-03 10:00", **extra}
        self.conn.execute(
            f"INSERT INTO offering ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", list(cols.values())
        )

    def test_money_rejects_float(self):
        for bad in (1.5, "1.5", 0, -100):
            with self.assertRaises(sqlite3.IntegrityError, msg=repr(bad)):
                self.offering(bad)
            with self.assertRaises(sqlite3.IntegrityError, msg=repr(bad)):
                self.conn.execute(
                    "INSERT INTO expense (date, amount, spending_category_id, created_at) VALUES (?, ?, ?, ?)",
                    ("2026-05-03", bad, self.rent, "2026-05-03 10:00"),
                )
        self.offering(1250000)
        row = self.conn.execute("SELECT amount, typeof(amount) AS t FROM offering").fetchone()
        self.assertEqual((row["amount"], row["t"]), (1250000, "integer"))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM expense").fetchone()[0], 0)

    def test_no_float_column_anywhere(self):
        tables = [r["name"] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        self.assertEqual(len(tables), 18)
        for table in tables:
            for col in self.conn.execute(f"PRAGMA table_info({table})"):
                self.assertNotRegex(col["type"].upper(), r"REAL|FLOA|DOUB|NUMERIC|DECIMAL", (table, col["name"]))

    def test_head_count_must_be_whole(self):
        self.conn.execute(
            "INSERT INTO calendar_item (kind, title, starts_at) VALUES ('Service', 'Sunday service', '2026-05-03 08:00')"
        )
        for bad in (1.5, -1):
            with self.assertRaises(sqlite3.IntegrityError):
                self.conn.execute("INSERT INTO head_count (calendar_item_id, count) VALUES (1, ?)", (bad,))
        self.conn.execute("INSERT INTO head_count (calendar_item_id, count) VALUES (1, 0)")

    def test_wrong_list_item_refused(self):
        with self.assertRaisesRegex(sqlite3.IntegrityError, "fund list"):
            self.conn.execute(
                "INSERT INTO offering (date, amount, fund_id, created_at) VALUES ('2026-05-03', 5, ?, 'x')",
                (self.rent,),
            )

    def test_offering_has_at_most_one_giver(self):
        self.conn.execute("INSERT INTO person (full_name, name_folded, created_at) VALUES ('A', 'a', 'x')")
        self.conn.execute("INSERT INTO family (name, name_folded, created_at) VALUES ('F', 'f', 'x')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.offering(5, giver_person_id=1, giver_family_id=1)
        self.offering(5, giver_person_id=1)
        self.offering(5)  # no-name offering

    def test_calendar_and_document_checks(self):
        self.conn.execute("INSERT INTO person (full_name, name_folded, created_at) VALUES ('A', 'a', 'x')")
        with self.assertRaises(sqlite3.IntegrityError):  # a Service cannot be a Visit
            self.conn.execute(
                "INSERT INTO calendar_item (kind, title, starts_at, visit_person_id) VALUES ('Service', 't', '2026-05-03 08:00', 1)"
            )
        with self.assertRaises(sqlite3.IntegrityError):  # bad date-time text
            self.conn.execute("INSERT INTO calendar_item (kind, title, starts_at) VALUES ('Event', 't', '2026-05-03')")
        self.conn.execute(
            "INSERT INTO calendar_item (kind, title, starts_at, visit_person_id) VALUES ('Visit', 't', '2026-05-03 08:00', 1)"
        )
        with self.assertRaises(sqlite3.IntegrityError):  # linked to two things
            self.conn.execute(
                "INSERT INTO document (original_name, stored_name, size, sha256, person_id, calendar_item_id, added_at) "
                "VALUES ('a.pdf', 'abc', 1, 'h', 1, 1, 'x')"
            )

    def test_sent_document_number_unique_per_year(self):
        r = self.item("recipient", name="Giáo hội")
        p = self.item("purpose", name="Notice")
        sql = ("INSERT INTO sent_document (year, seq, date, recipient_id, purpose_id, created_at) "
               "VALUES (?, ?, ?, ?, ?, 'x')")
        self.conn.execute(sql, (2026, 1, "2026-02-01", r, p))
        self.conn.execute(sql, (2027, 1, "2027-01-05", r, p))
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(sql, (2026, 1, "2026-03-01", r, p))
        with self.assertRaises(sqlite3.IntegrityError):  # year must be the year of the date
            self.conn.execute(sql, (2026, 2, "2027-03-01", r, p))


class CodeRulesTest(unittest.TestCase):
    """Self-checks on the source code of churchmgr/."""

    PACKAGE = pathlib.Path(_support.ROOT) / "churchmgr"
    AVOID = ("household", "donation", "tithe", "income", "attachment", "upload", "instance", "install",
             "tenant", "contact", "user", "appointment", "schedule", "activity", "attendance record",
             "area", "zone", "cell group", "department", "team", "secret", "letter", "outgoing mail",
             "receipt", "tax letter", "cost", "payment", "pastoral call", "home visit", "mass")

    TESTS = pathlib.Path(_support.ROOT) / "tests"
    # Names from outside this project that hold an Avoid word. They cannot be renamed.
    OUTSIDE_NAMES = (
        "user_version",  # SQLite: PRAGMA user_version
        "attachment; filename",  # HTTP: the Content-Disposition header value for a download
    )

    def package_sources(self):
        return {p.name: p.read_text(encoding="utf-8") for p in sorted(self.PACKAGE.glob("*.py"))}

    def sources(self):
        """Package and test files. This file is left out: it holds the Avoid list."""
        files = sorted(self.PACKAGE.glob("*.py")) + sorted(self.TESTS.glob("*.py"))
        here = pathlib.Path(__file__).resolve()
        return {f"{p.parent.name}/{p.name}": p.read_text(encoding="utf-8") for p in files if p.resolve() != here}

    @classmethod
    def avoid_hits(cls, source):
        """Avoid words in ``source``. A word counts when no letter is next to it, so snake_case
        names like ``team_worship`` are found and ``steam`` is not. A space in an entry
        matches a space or ``_``."""
        for name in cls.OUTSIDE_NAMES:
            source = re.sub(rf"(?<![a-z]){name}(?![a-z])", " ", source, flags=re.IGNORECASE)
        hits = []
        for word in cls.AVOID:
            pattern = r"(?<![a-z])" + word.replace(" ", "[ _]") + r"s?(?![a-z])"
            hits += [m.group(0) for m in re.finditer(pattern, source, re.IGNORECASE)]
        return hits

    def test_no_avoid_words_in_code(self):
        found = []
        for name, source in self.sources().items():
            found += [(name, hit) for hit in self.avoid_hits(source)]
        self.assertEqual(found, [])

    def test_avoid_matcher_sees_snake_case(self):
        for code in ("team_worship = []", "self.worship_team", "cell_group = 1", "TEAMS", "user_id"):
            self.assertNotEqual(self.avoid_hits(code), [], code)
        for code in ("steam = 1", "m.group(0)", 'conn.execute("PRAGMA user_version")'):
            self.assertEqual(self.avoid_hits(code), [], code)

    def test_only_paths_knows_localappdata(self):
        others = [n for n, s in self.package_sources().items() if "LOCALAPPDATA" in s.upper() and n != "paths.py"]
        self.assertEqual(others, [])

    def test_no_float_in_money_storage(self):
        self.assertNotRegex(self.package_sources()["schema.py"], r"\b(REAL|FLOAT|DOUBLE|DECIMAL|NUMERIC)\b")


if __name__ == "__main__":
    unittest.main()
