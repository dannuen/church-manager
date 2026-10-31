import datetime as dt
import subprocess
import sys
import tempfile
import unicodedata
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import _support
from _support import temp_folder
from churchmgr import calendar, care, db, documents, fake, handover, lists, money, people, search, sent, story

TODAY = dt.date(2026, 11, 1)  # a Sunday


def dashboard(conn, today):
    """What the dashboard shows. Every panel must have real data."""
    week_end = today + dt.timedelta(days=6)
    return {
        "this_week": calendar.items_between(conn, today.isoformat(), week_end.isoformat()),
        "needs_visit": care.needs_visit(conn, today=today),
        "head_counts": calendar.recent_head_counts(conn, n=8, now=f"{today} 00:00"),
        "money": money.month_totals(conn, today.year, today.month),
        "next_number": sent.next_number(conn, today.year),
        "search": search.search_persons(conn, "nguyen hai dang"),
    }


def snapshot(conn):
    """The data of a church copy without clock stamps or random file names."""
    queries = {
        "person": "SELECT full_name, gender, birth_date, phone, address FROM person ORDER BY id",
        "person_status": "SELECT person_id, status_id, start_date, end_date FROM person_status ORDER BY id",
        "family_link": "SELECT * FROM family_link ORDER BY id",
        "chi_phai_link": "SELECT * FROM chi_phai_link ORDER BY id",
        "truong_chi_phai": "SELECT * FROM truong_chi_phai ORDER BY id",
        "ministry_link": "SELECT * FROM ministry_link ORDER BY id",
        "calendar_item": "SELECT * FROM calendar_item ORDER BY id",
        "calendar_person": "SELECT * FROM calendar_person ORDER BY 1, 2, 3",
        "head_count": "SELECT * FROM head_count ORDER BY id",
        "offering": "SELECT date, amount, fund_id, giver_person_id, giver_family_id, note FROM offering ORDER BY id",
        "expense": "SELECT date, amount, spending_category_id, note FROM expense ORDER BY id",
        "sent_document": "SELECT year, seq, date, recipient_id, purpose_id, subject FROM sent_document ORDER BY id",
        "private_note": "SELECT person_id, body FROM private_note ORDER BY id",
        "document": "SELECT original_name, size, sha256, person_id, family_id, calendar_item_id FROM document",
    }
    return {name: [tuple(r) for r in conn.execute(sql)] for name, sql in queries.items()}


class FakeChurchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="cm-test-fake-")
        cls.tmp = Path(cls._tmp.name)
        assert "onedrive" not in str(cls.tmp.resolve()).lower()
        cls.folder = cls.tmp / "fake"
        cls.counts = fake.build_fake_church(cls.folder, people=50, seed=1, today=TODAY)
        cls.conn = db.open_church_copy(cls.folder)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        cls._tmp.cleanup()

    def count(self, sql, *params):
        return self.conn.execute(sql, params).fetchone()[0]

    def test_every_dashboard_panel_has_data(self):
        d = dashboard(self.conn, TODAY)
        self.assertGreaterEqual(len(d["this_week"]), 3)
        self.assertTrue(d["needs_visit"])
        self.assertTrue([r for r in d["needs_visit"] if r["last_visit"] is not None])  # visited, but long ago
        self.assertEqual(len(d["head_counts"]), 8)
        self.assertGreater(d["money"]["offerings"], 0)
        self.assertGreater(d["money"]["expenses"], 0)
        self.assertEqual(d["next_number"], "04/2026")
        self.assertEqual(d["search"][0]["full_name"], "Nguyễn Hải Đăng")
        self.assertEqual(search.search_persons(self.conn, "Nguyễn Hải Đăng")[0]["full_name"], "Nguyễn Hải Đăng")

    def test_people_and_history(self):
        persons = people.list_persons(self.conn)
        self.assertEqual(len(persons), 50)
        names = [p["full_name"] for p in persons]
        self.assertEqual(names.count("Nguyễn Hải Đăng"), 1)
        self.assertGreaterEqual(sum(not n.isascii() for n in names), 45)  # Vietnamese with diacritics
        self.assertTrue(all(unicodedata.is_normalized("NFC", n) for n in names))
        self.assertEqual(len(people.list_families(self.conn)), 12)
        chi_phai = people.list_chi_phai(self.conn)
        self.assertEqual(len(chi_phai), 3)
        for cp in chi_phai:
            self.assertIsNotNone(people.current_truong_chi_phai(self.conn, cp["id"]))
            self.assertTrue(people.chi_phai_families(self.conn, cp["id"]))
        self.assertTrue(any(len(people.truong_chi_phai_history(self.conn, cp["id"])) >= 2 for cp in chi_phai))
        changed = self.count("SELECT COUNT(*) FROM (SELECT person_id FROM person_status GROUP BY person_id "
                             "HAVING COUNT(*) > 1)")
        self.assertGreaterEqual(changed, 5)
        codes = {p["status_code"] for p in persons}
        self.assertTrue({"member", "attender", "visitor", "left", "passed_away"} <= codes)
        self.assertGreaterEqual(self.count("SELECT COUNT(*) FROM family_link WHERE end_date IS NOT NULL"), 1)
        self.assertGreaterEqual(self.count("SELECT COUNT(*) FROM chi_phai_link WHERE end_date IS NOT NULL"), 1)
        for m in lists.get_list(self.conn, "ministry"):
            self.assertTrue(people.ministry_people(self.conn, m["id"]), m["name"])

    def test_calendar_care_money_sent(self):
        services = self.conn.execute("SELECT starts_at FROM calendar_item WHERE kind = 'Service' "
                                     "ORDER BY starts_at").fetchall()
        self.assertEqual(len(services), 16)
        past = [s for s in services if s[0] < f"{TODAY} 00:00"]
        self.assertEqual(len(past), 12)
        self.assertTrue(all(dt.datetime.strptime(s[0], "%Y-%m-%d %H:%M").weekday() == 6 for s in services))
        self.assertEqual(self.count("SELECT COUNT(*) FROM head_count"), 12)
        self.assertGreaterEqual(self.count("SELECT COUNT(*) FROM calendar_person"), 16)
        log = care.care_log(self.conn)
        cutoff = calendar.add_months(TODAY, -3).isoformat()
        self.assertTrue([r for r in log if r["done_date"] < cutoff])
        self.assertTrue([r for r in log if r["done_date"] >= cutoff])
        for back in (0, 1, 3, 5):
            month = calendar.add_months(TODAY.replace(day=1), -back)
            totals = money.month_totals(self.conn, month.year, month.month)
            self.assertGreater(totals["offerings"], 0, month)
            self.assertGreater(totals["expenses"], 0, month)
        self.assertGreaterEqual(len(sent.list_sent_documents(self.conn, TODAY.year)), 3)
        self.assertEqual(sent.next_number(self.conn, TODAY.year - 1), f"03/{TODAY.year - 1}")
        families = people.list_families(self.conn)
        st = money.giving_statement(self.conn, TODAY.year, family_id=families[0]["id"])
        self.assertTrue(st["rows"])
        self.assertGreater(st["total"], 0)

    def test_private_notes_documents_and_story(self):
        bodies = [r[0] for r in self.conn.execute("SELECT body FROM private_note ORDER BY id")]
        self.assertGreaterEqual(len(bodies), 5)
        for n, body in enumerate(bodies, start=1):
            self.assertIn(f"PRIVATE-NOTE-MARKER-{n}", body)
        docs = documents.list_documents(self.conn)
        self.assertGreaterEqual(len(docs), 2)
        for d in docs:
            self.assertEqual(documents.document_path(self.conn, self.folder, d["id"]).stat().st_size, d["size"])
        first = search.search_persons(self.conn, "nguyen hai dang")[0]["id"]
        events = story.person_story(self.conn, first)
        kinds = {e["kind"] for e in events}
        self.assertTrue({"status", "family", "chi_phai", "truong_chi_phai", "ministry", "calendar", "visit",
                         "document"} <= kinds, kinds)
        self.assertNotIn("private_note", kinds)
        self.assertIn("private_note", {e["kind"] for e in story.person_story(self.conn, first, include_private=True)})

    def test_handover_of_fake_church_has_no_private_notes(self):
        zip_path = handover.make_handover(self.folder, self.tmp / "handover-out", today=TODAY)
        with zipfile.ZipFile(zip_path) as zf:
            data = zf.read("church.db")
            self.assertEqual(len([n for n in zf.namelist() if n.startswith("documents/") and n != "documents/"]),
                             len(documents.list_documents(self.conn)))
        self.assertNotIn(b"PRIVATE-NOTE-MARKER", data)
        self.assertGreaterEqual(self.count("SELECT COUNT(*) FROM private_note"), 5)  # the source keeps them

    def test_same_seed_same_data_other_seed_other_data(self):
        tmp = temp_folder(self)
        fake.build_fake_church(tmp / "again", people=50, seed=1, today=TODAY)
        fake.build_fake_church(tmp / "other", people=50, seed=2, today=TODAY)
        again = db.open_church_copy(tmp / "again")
        other = db.open_church_copy(tmp / "other")
        self.addCleanup(again.close)
        self.addCleanup(other.close)
        self.assertEqual(snapshot(again), snapshot(self.conn))
        self.assertNotEqual(snapshot(other)["person"], snapshot(self.conn)["person"])


class FakeOtherDaysTest(unittest.TestCase):
    def test_dashboard_has_data_on_any_day(self):
        tmp = temp_folder(self)
        for k, today in enumerate((dt.date(2027, 1, 1), dt.date(2027, 1, 2), dt.date(2026, 3, 4),
                                   dt.date(2026, 2, 28), dt.date(2028, 2, 29), dt.date(2026, 10, 31))):
            folder = tmp / f"c{k}"
            fake.build_fake_church(folder, people=20 + k * 7, seed=k, today=today)
            conn = db.open_church_copy(folder)
            try:
                d = dashboard(conn, today)
                self.assertGreaterEqual(len(d["this_week"]), 3, today)
                self.assertTrue(d["needs_visit"], today)
                self.assertEqual(len(d["head_counts"]), 8, today)
                self.assertGreater(d["money"]["offerings"], 0, today)
                self.assertGreater(d["money"]["expenses"], 0, today)
                self.assertEqual(d["next_number"], f"04/{today.year}", today)
                self.assertEqual(d["search"][0]["full_name"], "Nguyễn Hải Đăng", today)
                self.assertEqual(len(people.list_persons(conn)), 20 + k * 7)
            finally:
                conn.close()

    def test_refusals_leave_nothing_half_made(self):
        tmp = temp_folder(self)
        with self.assertRaises(ValueError):
            fake.build_fake_church(tmp / "few", people=5)
        self.assertFalse((tmp / "few").exists())
        with self.assertRaises(ValueError):
            fake.build_fake_church(tmp / "OneDrive" / "c")
        self.assertFalse((tmp / "OneDrive").exists())
        fake.build_fake_church(tmp / "c", people=20, today=TODAY)
        before = (tmp / "c" / "church.db").read_bytes()
        with self.assertRaises(db.ChurchCopyError):
            fake.build_fake_church(tmp / "c", people=20, today=TODAY)
        self.assertEqual((tmp / "c" / "church.db").read_bytes(), before)
        with mock.patch.object(fake._Fake, "make_private_notes", side_effect=RuntimeError("stop")):
            with self.assertRaises(RuntimeError):
                fake.build_fake_church(tmp / "broken", people=20, today=TODAY)
        self.assertFalse((tmp / "broken").exists())


class FakeCliTest(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "churchmgr.fake", *args], cwd=_support.ROOT,
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)

    def test_cli(self):
        tmp = temp_folder(self)
        target = tmp / "cli-copy"
        done = self.run_cli(str(target), "--people", "30", "--seed", "2", "--today", "2026-11-01")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Fake church made in", done.stdout)
        self.assertIn("persons: 30", done.stdout)
        self.assertTrue((target / "church.db").is_file())
        again = self.run_cli(str(target))
        self.assertEqual(again.returncode, 2)
        self.assertIn("Not made", again.stderr)
        bad = self.run_cli(str(tmp / "OneDrive" / "copy"))
        self.assertEqual(bad.returncode, 2)
        self.assertIn("OneDrive", bad.stderr)
        self.assertFalse((tmp / "OneDrive").exists())


if __name__ == "__main__":
    unittest.main()
