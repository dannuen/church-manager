import sqlite3
import unicodedata
import unittest

from _support import CopyTestCase
from churchmgr import i18n, lists, people, search, text
from churchmgr.i18n import TextError

NAME = "Nguyễn Hải Đăng"


def nfd(s):
    return unicodedata.normalize("NFD", s)


class PersonTest(CopyTestCase):
    def test_nfd_name_is_stored_nfc(self):
        pid = people.add_person(self.conn, nfd(NAME))
        row = people.get_person(self.conn, pid)
        self.assertEqual(row["full_name"], NAME)
        self.assertTrue(unicodedata.is_normalized("NFC", row["full_name"]))
        self.assertEqual(row["name_folded"], "nguyen hai dang")

    def test_add_person_all_fields_and_status(self):
        pid = people.add_person(
            self.conn, "  Trần   Thị Mỹ Dung ", gender="f", birth_date="1990-04-12", phone=" 0903 123 456 ",
            address=nfd("12 Lê Lợi, Đà Lạt"), note="Hát hay", status_id=self.status("member"),
            start_date="2020-01-05",
        )
        row = people.get_person(self.conn, pid)
        self.assertEqual(
            (row["full_name"], row["gender"], row["birth_date"], row["phone"], row["address"], row["note"]),
            ("Trần Thị Mỹ Dung", "F", "1990-04-12", "0903 123 456", "12 Lê Lợi, Đà Lạt", "Hát hay"),
        )
        self.assertRegex(row["created_at"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        status = people.current_status(self.conn, pid)
        self.assertEqual((status["code"], status["start_date"]), ("member", "2020-01-05"))

    def test_bad_input_refused_and_nothing_saved(self):
        for kwargs in ({"full_name": "  "}, {"full_name": "A", "gender": "X"},
                       {"full_name": "A", "birth_date": "12/04/1990"},
                       {"full_name": "A", "status_id": self.item("fund", name="General")},
                       {"full_name": "A", "status_id": 99999}):
            with self.assertRaises(ValueError, msg=kwargs):
                people.add_person(self.conn, **kwargs)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM person").fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM person_status").fetchone()[0], 0)

    def test_update_person_keeps_name_folded_in_sync(self):
        pid = people.add_person(self.conn, "Lê Văn Khoa", phone="1")
        people.update_person(self.conn, pid, full_name=nfd("Lê Văn Đức"), phone=None)
        row = people.get_person(self.conn, pid)
        self.assertEqual((row["full_name"], row["name_folded"], row["phone"]), ("Lê Văn Đức", "le van duc", None))
        self.assertEqual([r["id"] for r in search.search_persons(self.conn, "duc")], [pid])
        self.assertEqual(search.search_persons(self.conn, "khoa"), [])
        with self.assertRaises(ValueError):
            people.update_person(self.conn, pid, full_name="")
        with self.assertRaises(ValueError):
            people.update_person(self.conn, 99999, phone="2")

    def test_add_person_year_only(self):
        """BY-1: a year-only Birth date is stored YYYY-00-00 by add_person and update_person."""
        pid = people.add_person(self.conn, "Lê Văn Khoa", birth_date="1980-00-00")
        self.assertEqual(people.get_person(self.conn, pid)["birth_date"], "1980-00-00")
        people.update_person(self.conn, pid, birth_date="1975-03-09")
        self.assertEqual(people.get_person(self.conn, pid)["birth_date"], "1975-03-09")
        people.update_person(self.conn, pid, birth_date="1980-00-00")
        self.assertEqual(people.get_person(self.conn, pid)["birth_date"], "1980-00-00")
        for bad in ("0980-00-00", "1980-00-00x", "1850-00-00", "1980-00-05", "1980"):
            with self.assertRaisesRegex(ValueError, r"^Birth date must be a real date", msg=bad):
                people.add_person(self.conn, "Lê Văn Bình", birth_date=bad)
            with self.assertRaisesRegex(ValueError, r"^Birth date must be a real date", msg=bad):
                people.update_person(self.conn, pid, birth_date=bad)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM person").fetchone()[0], 1)
        self.assertEqual(people.get_person(self.conn, pid)["birth_date"], "1980-00-00")
        people.update_person(self.conn, pid, birth_date="")
        self.assertIsNone(people.get_person(self.conn, pid)["birth_date"])

    def test_list_persons_sorted_by_given_name(self):
        for name in ("Nguyễn Văn Bình", "Trần Thị An", "Lê Hải Đăng", "Phạm Ánh", "Đỗ Văn An"):
            people.add_person(self.conn, name)
        self.assertEqual(
            [r["full_name"] for r in people.list_persons(self.conn)],
            ["Đỗ Văn An", "Trần Thị An", "Phạm Ánh", "Nguyễn Văn Bình", "Lê Hải Đăng"],
        )

    def test_list_persons_by_status(self):
        a = people.add_person(self.conn, "Lê Văn An", status_id=self.status("member"), start_date="2020-01-01")
        b = people.add_person(self.conn, "Lê Văn Bình", status_id=self.status("visitor"), start_date="2020-01-01")
        people.set_status(self.conn, b, self.status("member"), "2021-01-01")
        people.add_person(self.conn, "Lê Văn Cường")
        members = people.list_persons(self.conn, status_id=self.status("member"))
        self.assertEqual([r["id"] for r in members], [a, b])
        self.assertEqual(members[0]["status_name"], "Member")
        self.assertEqual(people.list_persons(self.conn, status_id=self.status("visitor")), [])
        self.assertEqual(len(people.list_persons(self.conn)), 3)


class StatusHistoryTest(CopyTestCase):
    def setUp(self):
        super().setUp()
        self.pid = people.add_person(self.conn, NAME, status_id=self.status("visitor"), start_date="2024-01-07")

    def test_set_status_closes_old_row_and_keeps_it(self):
        people.set_status(self.conn, self.pid, self.status("attender"), "2024-06-02")
        people.set_status(self.conn, self.pid, self.status("member"), "2025-03-16")
        rows = [(r["code"], r["start_date"], r["end_date"]) for r in people.status_history(self.conn, self.pid)]
        self.assertEqual(rows, [
            ("visitor", "2024-01-07", "2024-06-02"),
            ("attender", "2024-06-02", "2025-03-16"),
            ("member", "2025-03-16", None),
        ])
        self.assertEqual(people.current_status(self.conn, self.pid)["name"], "Member")

    def test_same_status_is_no_change(self):
        open_id = people.current_status(self.conn, self.pid)["id"]
        self.assertEqual(people.set_status(self.conn, self.pid, self.status("visitor"), "2025-01-01"), open_id)
        self.assertEqual(len(people.status_history(self.conn, self.pid)), 1)

    def test_earlier_start_date_refused(self):
        with self.assertRaisesRegex(ValueError, "before 07/01/2024"):
            people.set_status(self.conn, self.pid, self.status("member"), "2023-12-31")
        self.assertEqual(len(people.status_history(self.conn, self.pid)), 1)
        self.assertIsNone(people.current_status(self.conn, self.pid)["end_date"])

    def test_wrong_list_or_bad_date_refused(self):
        with self.assertRaises(ValueError):
            people.set_status(self.conn, self.pid, self.item("ministry", name="Youth"), "2025-01-01")
        with self.assertRaises(ValueError):
            people.set_status(self.conn, self.pid, self.status("member"), "2025-13-01")
        with self.assertRaises(ValueError):
            people.set_status(self.conn, 99999, self.status("member"), "2025-01-01")

    def test_text_ids_work_like_numbers(self):
        open_id = people.current_status(self.conn, self.pid)["id"]
        self.assertEqual(people.set_status(self.conn, str(self.pid), str(self.status("visitor")), "2025-01-01"), open_id)


class InsertStatusTest(CopyTestCase):
    """people.insert_status: a Status change at any past date, in any order (card SP-1)."""

    def person(self, *lines):
        """A Person with these Status lines, oldest first: (code, start date); the last one stays open."""
        (code, start), *rest = lines
        pid = people.add_person(self.conn, NAME, status_id=self.status(code), start_date=start)
        for code, start in rest:
            people.set_status(self.conn, pid, self.status(code), start)
        return pid

    def hist(self, pid):
        return [(r["code"], r["start_date"], r["end_date"]) for r in people.status_history(self.conn, pid)]

    def open_count(self, pid):
        return self.conn.execute(
            "SELECT COUNT(*) FROM person_status WHERE person_id = ? AND end_date IS NULL", (pid,)
        ).fetchone()[0]

    def insert(self, pid, code, day):
        return people.insert_status(self.conn, pid, self.status(code), day)

    def test_insert_status_inside_open_line(self):
        pid = self.person(("visitor", "2010-01-01"))
        self.assertIs(self.insert(pid, "left", "2018-06-30"), True)
        self.assertEqual(self.hist(pid), [("visitor", "2010-01-01", "2018-06-30"), ("left", "2018-06-30", None)])
        self.assertEqual(people.current_status(self.conn, pid)["code"], "left")
        self.assertEqual(self.open_count(pid), 1)

    def test_insert_status_inside_closed_line(self):
        pid = self.person(("visitor", "2010-01-01"), ("member", "2024-01-01"))
        open_id = people.current_status(self.conn, pid)["id"]
        self.assertIs(self.insert(pid, "left", "2018-06-30"), True)
        self.assertEqual(self.hist(pid), [
            ("visitor", "2010-01-01", "2018-06-30"),
            ("left", "2018-06-30", "2024-01-01"),
            ("member", "2024-01-01", None),
        ])
        now = people.current_status(self.conn, pid)
        self.assertEqual((now["id"], now["code"]), (open_id, "member"))
        self.assertEqual(self.open_count(pid), 1)

    def test_insert_status_before_first(self):
        pid = self.person(("visitor", "2024-03-15"))
        open_id = people.current_status(self.conn, pid)["id"]
        self.assertIs(self.insert(pid, "member", "2010-01-01"), True)
        self.assertEqual(self.hist(pid), [("member", "2010-01-01", "2024-03-15"), ("visitor", "2024-03-15", None)])
        now = people.current_status(self.conn, pid)
        self.assertEqual((now["id"], now["code"]), (open_id, "visitor"))
        self.assertEqual(self.open_count(pid), 1)

    def test_insert_status_spec_example(self):
        """Visitor from 15/03/2024; add Member from 01/01/2010, then Left from 30/06/2018."""
        pid = self.person(("visitor", "2024-03-15"))
        self.assertIs(self.insert(pid, "member", "2010-01-01"), True)
        self.assertIs(self.insert(pid, "left", "2018-06-30"), True)
        self.assertEqual(self.hist(pid), [
            ("member", "2010-01-01", "2018-06-30"),
            ("left", "2018-06-30", "2024-03-15"),
            ("visitor", "2024-03-15", None),
        ])
        self.assertEqual(people.current_status(self.conn, pid)["code"], "visitor")
        self.assertEqual(self.open_count(pid), 1)

    def test_insert_status_in_a_gap(self):
        """A day between two lines that do not touch (only a test copy has one): the new line runs to
        the next start. The lines are made with plain INSERTs in this test copy."""
        pid = people.add_person(self.conn, NAME)
        sql = "INSERT INTO person_status (person_id, status_id, start_date, end_date) VALUES (?, ?, ?, ?)"
        self.conn.execute(sql, (pid, self.status("visitor"), "2020-01-01", "2020-06-01"))
        self.conn.execute(sql, (pid, self.status("member"), "2021-01-01", None))
        self.assertIs(self.insert(pid, "left", "2020-08-01"), True)
        self.assertEqual(self.hist(pid), [
            ("visitor", "2020-01-01", "2020-06-01"),
            ("left", "2020-08-01", "2021-01-01"),
            ("member", "2021-01-01", None),
        ])
        self.assertEqual(people.current_status(self.conn, pid)["code"], "member")
        self.assertEqual(self.open_count(pid), 1)

    def test_insert_status_same_as_covering_returns_false(self):
        pid = self.person(("visitor", "2010-01-01"), ("member", "2024-01-01"))
        before = self.hist(pid)
        for code, day in (("visitor", "2018-06-30"),   # inside the closed line
                          ("visitor", "2010-01-01"),   # on the start of the closed line
                          ("member", "2024-01-01"),    # on the start of the open line
                          ("member", "2025-05-05")):   # inside the open line
            self.assertIs(self.insert(pid, code, day), False, msg=(code, day))
            self.assertEqual(self.hist(pid), before, msg=(code, day))
            self.assertEqual(self.open_count(pid), 1)

    def test_insert_status_on_existing_start_refused(self):
        pid = self.person(("visitor", "2010-01-01"), ("member", "2024-01-01"))
        before = self.hist(pid)
        with self.assertRaises(TextError) as caught:
            self.insert(pid, "left", "2010-01-01")
        self.assertEqual(caught.exception.key, "people.err_status_day")
        self.assertEqual(str(caught.exception),
                         "Start date 01/01/2010: a Status already starts on that day. Pick another date.")
        self.assertEqual(i18n.error_text(caught.exception, "vi"),
                         "Ngày bắt đầu 01/01/2010: đã có một Trạng thái bắt đầu vào ngày đó. Hãy chọn ngày khác.")
        self.assertEqual(self.hist(pid), before)
        self.assertEqual(self.open_count(pid), 1)

    def test_insert_status_same_day_forward_as_set_status(self):
        today = text.today_text()
        a = self.person(("visitor", today))
        b = self.person(("visitor", today))
        self.assertIs(self.insert(a, "member", today), True)
        people.set_status(self.conn, b, self.status("member"), today)
        self.assertEqual(self.hist(a), [("visitor", today, today), ("member", today, None)])
        self.assertEqual(self.hist(a), self.hist(b))
        self.assertEqual(people.current_status(self.conn, a)["code"], "member")
        self.assertEqual(self.open_count(a), 1)

    def test_insert_status_open_row_stays_unique(self):
        """Every case on one Person, in turn: one open line after each, the current Status kept."""
        pid = self.person(("visitor", "2024-03-15"))
        steps = (
            ("member", "2010-01-01", True),    # before the first line
            ("left", "2018-06-30", True),      # inside a closed line
            ("member", "2019-01-01", True),    # inside a closed line again
            ("visitor", "2020-01-01", True),   # inside a closed line, the next line has this Status too
            ("member", "2012-05-05", False),   # same as the covering line
            ("attender", "2018-06-30", None),  # a line starts that day: refused
            ("member", "2024-03-15", True),    # on the last change: as set_status
            ("member", "2025-01-01", False),   # same as the open line
            ("attender", "2026-01-01", True),  # after the last change: as set_status
        )
        for code, day, result in steps:
            if result is None:
                with self.assertRaises(TextError, msg=(code, day)):
                    self.insert(pid, code, day)
            else:
                self.assertIs(self.insert(pid, code, day), result, msg=(code, day))
            self.assertEqual(self.open_count(pid), 1, msg=(code, day))
        self.assertEqual(self.hist(pid), [
            ("member", "2010-01-01", "2018-06-30"),
            ("left", "2018-06-30", "2019-01-01"),
            ("member", "2019-01-01", "2020-01-01"),
            ("visitor", "2020-01-01", "2024-03-15"),  # two neighbour lines with one Status: kept, not merged
            ("visitor", "2024-03-15", "2024-03-15"),
            ("member", "2024-03-15", "2026-01-01"),
            ("attender", "2026-01-01", None),
        ])

    def test_insert_status_bad_input_changes_nothing(self):
        pid = self.person(("visitor", "2010-01-01"), ("member", "2024-01-01"))
        before = self.hist(pid)
        bad = (
            (pid, self.item("ministry", name="Youth"), "2018-06-30"),  # not a Status
            (pid, 99999, "2018-06-30"),
            (pid, "abc", "2018-06-30"),
            (99999, self.status("left"), "2018-06-30"),                 # no such Person
            (pid, self.status("left"), "2018-13-01"),                   # bad dates
            (pid, self.status("left"), "30/06/2018"),
            (pid, self.status("left"), ""),
        )
        for person_id, status_id, day in bad:
            with self.assertRaises(TextError, msg=(person_id, status_id, day)):
                people.insert_status(self.conn, person_id, status_id, day)
            self.assertEqual(self.hist(pid), before)
            self.assertEqual(self.open_count(pid), 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM person_status").fetchone()[0], 2)


class HistoryRulesInDatabaseTest(CopyTestCase):
    """The database itself refuses to delete or rewrite history."""

    def setUp(self):
        super().setUp()
        c = self.conn
        self.pid = people.add_person(c, NAME, status_id=self.status("visitor"), start_date="2024-01-07")
        self.pid2 = people.add_person(c, "Trần Văn Bảo")
        self.fid = people.add_family(c, "Gia đình Nguyễn")
        self.cid = people.add_chi_phai(c, "Chi phái Một")
        people.set_status(c, self.pid, self.status("member"), "2024-06-02")
        people.set_family(c, self.pid, self.fid, "Head", "2024-01-07")
        people.set_family_chi_phai(c, self.fid, self.cid, "2024-01-07")
        people.set_truong_chi_phai(c, self.cid, self.pid, "2024-01-07")
        people.set_ministry(c, self.pid, self.item("ministry", name="Worship"), "Member", "2024-01-07")

    def test_delete_fails_on_every_history_table(self):
        for table in ("person_status", "family_link", "chi_phai_link", "truong_chi_phai", "ministry_link"):
            with self.assertRaisesRegex(sqlite3.IntegrityError, "history is never deleted", msg=table):
                self.conn.execute(f"DELETE FROM {table}")
            self.assertGreater(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)

    def test_update_of_closed_row_fails(self):
        closed = self.conn.execute(
            "SELECT id FROM person_status WHERE person_id = ? AND end_date IS NOT NULL", (self.pid,)
        ).fetchone()["id"]
        for sql in ("UPDATE person_status SET end_date = '2024-07-01' WHERE id = ?",
                    "UPDATE person_status SET end_date = NULL WHERE id = ?",
                    "UPDATE person_status SET start_date = '2023-01-01' WHERE id = ?"):
            with self.assertRaisesRegex(sqlite3.IntegrityError, "history is never changed", msg=sql):
                self.conn.execute(sql, (closed,))
        row = self.conn.execute("SELECT start_date, end_date FROM person_status WHERE id = ?", (closed,)).fetchone()
        self.assertEqual(tuple(row), ("2024-01-07", "2024-06-02"))

    def test_closed_status_row_may_only_be_cut_earlier(self):
        """SP-1, the Rule 4 exception: a closed Status row may get an earlier end date, on or after its
        start date (people.insert_status cuts it). Its Status and start date never change."""
        closed = self.conn.execute(
            "SELECT id FROM person_status WHERE person_id = ? AND end_date IS NOT NULL", (self.pid,)
        ).fetchone()["id"]
        left = self.status("left")
        for sql, params in (
            ("UPDATE person_status SET end_date = '2024-01-06' WHERE id = ?", (closed,)),  # before its start
            ("UPDATE person_status SET end_date = '2024-06-03' WHERE id = ?", (closed,)),  # later
            ("UPDATE person_status SET end_date = NULL WHERE id = ?", (closed,)),
            ("UPDATE person_status SET end_date = '2024-03-01', status_id = ? WHERE id = ?", (left, closed)),
            ("UPDATE person_status SET end_date = '2024-03-01', start_date = '2024-01-08' WHERE id = ?", (closed,)),
        ):
            with self.assertRaisesRegex(sqlite3.IntegrityError, "history is never changed", msg=sql):
                self.conn.execute(sql, params)
        self.conn.execute("UPDATE person_status SET end_date = '2024-03-01' WHERE id = ?", (closed,))
        self.conn.execute("UPDATE person_status SET end_date = '2024-01-07' WHERE id = ?", (closed,))  # = start
        row = self.conn.execute("SELECT status_id, start_date, end_date FROM person_status WHERE id = ?",
                                (closed,)).fetchone()
        self.assertEqual(tuple(row), (self.status("visitor"), "2024-01-07", "2024-01-07"))

    def test_other_closed_history_rows_are_never_cut(self):
        for table in ("family_link", "chi_phai_link", "truong_chi_phai", "ministry_link"):
            self.conn.execute(f"UPDATE {table} SET end_date = '2025-01-01'")  # closing once is allowed
            with self.assertRaisesRegex(sqlite3.IntegrityError, "history is never changed", msg=table):
                self.conn.execute(f"UPDATE {table} SET end_date = '2024-06-01'")
            self.assertEqual([r[0] for r in self.conn.execute(f"SELECT end_date FROM {table}")], ["2025-01-01"])

    def test_open_row_can_only_be_closed(self):
        open_id = people.current_status(self.conn, self.pid)["id"]
        with self.assertRaises(sqlite3.IntegrityError):  # change the value
            self.conn.execute("UPDATE person_status SET status_id = ? WHERE id = ?", (self.status("left"), open_id))
        with self.assertRaises(sqlite3.IntegrityError):  # end before start
            self.conn.execute("UPDATE person_status SET end_date = '2024-01-01' WHERE id = ?", (open_id,))
        for table in ("family_link", "chi_phai_link", "truong_chi_phai", "ministry_link"):
            with self.assertRaises(sqlite3.IntegrityError, msg=table):
                self.conn.execute(f"UPDATE {table} SET start_date = '2020-01-01'")
        self.conn.execute("UPDATE person_status SET end_date = '2025-01-01' WHERE id = ?", (open_id,))  # allowed once

    def test_two_open_rows_impossible(self):
        inserts = {
            "person_status": ("person_id, status_id", (self.pid, self.status("left"))),
            "family_link": ("person_id, family_id, family_role", (self.pid, self.fid, "Other")),
            "chi_phai_link": ("family_id, chi_phai_id", (self.fid, self.cid)),
            "truong_chi_phai": ("chi_phai_id, person_id", (self.cid, self.pid2)),
            "ministry_link": ("person_id, ministry_id, ministry_role",
                              (self.pid, self.item("ministry", name="Worship"), "Leader")),
        }
        for table, (cols, values) in inserts.items():
            with self.assertRaisesRegex(sqlite3.IntegrityError, "UNIQUE", msg=table):
                self.conn.execute(
                    f"INSERT INTO {table} ({cols}, start_date) VALUES ({', '.join('?' * len(values))}, '2025-01-01')",
                    values,
                )

    def test_insert_or_replace_cannot_remove_history(self):
        open_row = people.current_status(self.conn, self.pid)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT OR REPLACE INTO person_status (id, person_id, status_id, start_date) VALUES (?, ?, ?, '2025-01-01')",
                (open_row["id"], self.pid, self.status("left")),
            )
        self.assertEqual(len(people.status_history(self.conn, self.pid)), 2)

    def test_person_with_history_cannot_be_deleted(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("DELETE FROM person WHERE id = ?", (self.pid,))


class FamilyTest(CopyTestCase):
    def setUp(self):
        super().setUp()
        c = self.conn
        self.f1 = people.add_family(c, nfd("Gia đình Nguyễn"), address="1 Lê Lợi")
        self.f2 = people.add_family(c, "Gia đình Trần", address="2 Hai Bà Trưng")
        self.dad = people.add_person(c, NAME, birth_date="1970-01-01", address="Own street")
        self.mom = people.add_person(c, "Lê Thị Hoa", birth_date="1972-01-01")
        self.kid = people.add_person(c, "Nguyễn Văn Bé", birth_date="2000-01-01")

    def test_family_members_order_and_role(self):
        people.set_family(self.conn, self.kid, self.f1, "Child", "2000-01-01")
        people.set_family(self.conn, self.mom, self.f1, "Spouse", "1995-01-01")
        people.set_family(self.conn, self.dad, self.f1, "Head", "1995-01-01")
        members = people.family_members(self.conn, self.f1)
        self.assertEqual([(m["full_name"], m["family_role"]) for m in members],
                         [(NAME, "Head"), ("Lê Thị Hoa", "Spouse"), ("Nguyễn Văn Bé", "Child")])
        self.assertEqual(people.get_family(self.conn, self.f1)["name"], "Gia đình Nguyễn")

    def test_family_members_sort_year_only(self):
        """BY-1: in one Family role, a 1980-00-00 Person sorts before a 1980-06-01 one."""
        june = people.add_person(self.conn, "An Văn Một", birth_date="1980-06-01")  # first by name and id
        year = people.add_person(self.conn, "Bùi Văn Hai", birth_date="1980-00-00")
        for pid in (self.kid, june, year):
            people.set_family(self.conn, pid, self.f1, "Child", "2000-01-01")
        members = people.family_members(self.conn, self.f1)
        self.assertEqual([m["id"] for m in members], [year, june, self.kid])
        self.assertEqual(members[0]["birth_date"], "1980-00-00")

    def test_move_family_keeps_history(self):
        people.set_family(self.conn, self.kid, self.f1, "Child", "2000-01-01")
        people.set_family(self.conn, self.kid, self.f2, "Spouse", "2024-05-01")
        hist = [(h["name"], h["family_role"], h["start_date"], h["end_date"])
                for h in people.family_history(self.conn, self.kid)]
        self.assertEqual(hist, [("Gia đình Nguyễn", "Child", "2000-01-01", "2024-05-01"),
                                ("Gia đình Trần", "Spouse", "2024-05-01", None)])
        self.assertEqual(people.current_family(self.conn, self.kid)["family_id"], self.f2)
        self.assertEqual([m["id"] for m in people.family_members(self.conn, self.f1, on_date="2010-06-01")], [self.kid])
        self.assertEqual(people.family_members(self.conn, self.f1, on_date="2024-05-01"), [])
        self.assertEqual(people.family_members(self.conn, self.f1), [])
        self.assertEqual([m["id"] for m in people.family_members(self.conn, self.f2)], [self.kid])

    def test_role_change_in_same_family_is_new_row(self):
        people.set_family(self.conn, self.kid, self.f1, "Child", "2000-01-01")
        people.set_family(self.conn, self.kid, self.f1, "Child", "2010-01-01")  # same = no change
        people.set_family(self.conn, self.kid, self.f1, "Head", "2020-01-01")
        self.assertEqual([h["family_role"] for h in people.family_history(self.conn, self.kid)], ["Child", "Head"])

    def test_leave_family_and_address(self):
        people.set_family(self.conn, self.dad, self.f1, "Head", "1995-01-01")
        self.assertEqual(people.person_address(self.conn, self.dad), "1 Lê Lợi")
        people.set_family(self.conn, self.dad, None, None, "2024-01-01")
        self.assertIsNone(people.current_family(self.conn, self.dad))
        self.assertEqual(people.family_history(self.conn, self.dad)[0]["end_date"], "2024-01-01")
        self.assertEqual(people.person_address(self.conn, self.dad), "Own street")
        self.assertIsNone(people.set_family(self.conn, self.dad, None, None, "2024-02-01"))  # nothing to end
        with self.assertRaises(ValueError):  # cannot join before leaving date
            people.set_family(self.conn, self.dad, self.f2, "Head", "2023-12-01")

    def test_bad_role_refused(self):
        for role in ("Wife", None, "head"):
            with self.assertRaises(ValueError):
                people.set_family(self.conn, self.kid, self.f1, role, "2000-01-01")
        self.assertEqual(people.family_history(self.conn, self.kid), [])

    def test_update_and_list_families(self):
        people.update_family(self.conn, self.f2, name="Gia đình Đặng", address=None)
        row = people.get_family(self.conn, self.f2)
        self.assertEqual((row["name"], row["name_folded"], row["address"]), ("Gia đình Đặng", "gia dinh dang", None))
        self.assertEqual([f["id"] for f in people.list_families(self.conn)], [self.f2, self.f1])


class ChiPhaiTest(CopyTestCase):
    def setUp(self):
        super().setUp()
        c = self.conn
        self.c1 = people.add_chi_phai(c, "Chi phái Một")
        self.c2 = people.add_chi_phai(c, "Chi phái Hai")
        self.fam = people.add_family(c, "Gia đình Nguyễn")
        self.p1 = people.add_person(c, NAME)
        self.p2 = people.add_person(c, "Trần Văn Bảo")

    def test_family_chi_phai_history(self):
        people.set_family_chi_phai(self.conn, self.fam, self.c1, "2020-01-01")
        people.set_family_chi_phai(self.conn, self.fam, self.c2, "2023-01-01")
        self.assertEqual(people.current_chi_phai(self.conn, self.fam)["name"], "Chi phái Hai")
        hist = [(h["name"], h["start_date"], h["end_date"]) for h in people.family_chi_phai_history(self.conn, self.fam)]
        self.assertEqual(hist, [("Chi phái Một", "2020-01-01", "2023-01-01"), ("Chi phái Hai", "2023-01-01", None)])
        self.assertEqual([f["id"] for f in people.chi_phai_families(self.conn, self.c1, on_date="2021-01-01")], [self.fam])
        self.assertEqual(people.chi_phai_families(self.conn, self.c1), [])
        people.set_family_chi_phai(self.conn, self.fam, None, "2024-01-01")
        self.assertIsNone(people.current_chi_phai(self.conn, self.fam))

    def test_truong_chi_phai_history(self):
        people.set_truong_chi_phai(self.conn, self.c1, self.p1, "2019-01-01")
        people.set_truong_chi_phai(self.conn, self.c1, self.p2, "2024-01-01")
        self.assertEqual(people.current_truong_chi_phai(self.conn, self.c1)["full_name"], "Trần Văn Bảo")
        hist = [(h["full_name"], h["start_date"], h["end_date"]) for h in people.truong_chi_phai_history(self.conn, self.c1)]
        self.assertEqual(hist, [(NAME, "2019-01-01", "2024-01-01"), ("Trần Văn Bảo", "2024-01-01", None)])
        people.set_truong_chi_phai(self.conn, self.c1, None, "2025-01-01")
        self.assertIsNone(people.current_truong_chi_phai(self.conn, self.c1))
        self.assertEqual(len(people.truong_chi_phai_history(self.conn, self.c1)), 2)

    def test_names_unique_and_rename(self):
        with self.assertRaises(ValueError):
            people.add_chi_phai(self.conn, "Chi phái Một")
        people.rename_chi_phai(self.conn, self.c2, nfd("Chi phái Đông"))
        self.assertEqual(people.get_chi_phai(self.conn, self.c2)["name_folded"], "chi phai dong")
        with self.assertRaises(ValueError):
            people.rename_chi_phai(self.conn, self.c2, "Chi phái Một")
        self.assertEqual([c["name"] for c in people.list_chi_phai(self.conn)], ["Chi phái Đông", "Chi phái Một"])


class MinistryTest(CopyTestCase):
    def test_ministry_role_change_and_end(self):
        pid = people.add_person(self.conn, NAME)
        other = people.add_person(self.conn, "Trần Văn Bảo")
        worship = self.item("ministry", name="Worship")
        youth = self.item("ministry", name="Youth")
        people.set_ministry(self.conn, pid, worship, "Member", "2020-01-01")
        people.set_ministry(self.conn, pid, youth, "Leader", "2021-01-01")
        people.set_ministry(self.conn, pid, worship, "Leader", "2022-01-01")
        people.set_ministry(self.conn, other, worship, "Member", "2022-01-01")
        self.assertEqual([(m["name"], m["ministry_role"]) for m in people.current_ministries(self.conn, pid)],
                         [("Worship", "Leader"), ("Youth", "Leader")])
        self.assertEqual([p["id"] for p in people.ministry_people(self.conn, worship)], [pid, other])
        people.set_ministry(self.conn, pid, youth, None, "2023-01-01")
        self.assertEqual([m["name"] for m in people.current_ministries(self.conn, pid)], ["Worship"])
        hist = [(h["name"], h["ministry_role"], h["start_date"], h["end_date"])
                for h in people.ministry_history(self.conn, pid)]
        self.assertEqual(hist, [("Worship", "Member", "2020-01-01", "2022-01-01"),
                                ("Youth", "Leader", "2021-01-01", "2023-01-01"),
                                ("Worship", "Leader", "2022-01-01", None)])
        self.assertEqual(people.ministry_people(self.conn, youth), [])
        self.assertEqual([p["id"] for p in people.ministry_people(self.conn, youth, on_date="2022-06-01")], [pid])

    def test_bad_ministry_or_role_refused(self):
        pid = people.add_person(self.conn, NAME)
        with self.assertRaises(ValueError):
            people.set_ministry(self.conn, pid, self.status("member"), "Member", "2020-01-01")
        with self.assertRaises(ValueError):
            people.set_ministry(self.conn, pid, self.item("ministry", name="Youth"), "Boss", "2020-01-01")


class PrivateNoteTest(CopyTestCase):
    def test_add_and_list_private_notes(self):
        pid = people.add_person(self.conn, NAME)
        other = people.add_person(self.conn, "Trần Văn Bảo")
        first = people.add_private_note(self.conn, pid, nfd("Cầu nguyện cho gia đình"))
        second = people.add_private_note(self.conn, pid, "Tư vấn")
        people.add_private_note(self.conn, other, "Khác")
        notes = people.list_private_notes(self.conn, pid)
        self.assertEqual([n["id"] for n in notes], [second, first])
        self.assertEqual(notes[1]["body"], "Cầu nguyện cho gia đình")
        with self.assertRaises(ValueError):
            people.add_private_note(self.conn, pid, "   ")
        # the normal note is a different field, never private
        self.assertIsNone(people.get_person(self.conn, pid)["note"])

    def test_update_private_note_replaces_the_text_in_place(self):
        """B13: the pastor can change a Private note (so a refused Handover can be made)."""
        pid = people.add_person(self.conn, NAME)
        other = people.add_person(self.conn, "Trần Văn Bảo")
        nid = people.add_private_note(self.conn, pid, "Lời cũ cần xóa 7731")
        keep = people.add_private_note(self.conn, other, "Của người khác")
        created = people.list_private_notes(self.conn, pid)[0]["created_at"]
        people.update_private_note(self.conn, pid, nid, nfd("  Lời mới đã đổi  "))
        notes = people.list_private_notes(self.conn, pid)
        self.assertEqual([(n["id"], n["body"], n["created_at"]) for n in notes], [(nid, "Lời mới đã đổi", created)])
        rows = self.conn.execute("SELECT body FROM private_note").fetchall()
        self.assertEqual(sorted(r[0] for r in rows), sorted(["Lời mới đã đổi", "Của người khác"]))  # no old copy
        self.assertFalse(any("7731" in r[0] for r in rows))
        # empty text, a note of another Person, a note that does not exist: refused, nothing changed
        with self.assertRaisesRegex(ValueError, r"^A private note needs some text\.$"):
            people.update_private_note(self.conn, pid, nid, "  \n ")
        for person, note in ((pid, keep), (other, nid), (pid, 9999)):
            with self.assertRaises(ValueError, msg=(person, note)):
                people.update_private_note(self.conn, person, note, "Thử đổi")
        with self.assertRaises(ValueError):
            people.update_private_note(self.conn, 9999, nid, "Thử đổi")
        self.assertEqual(sorted(r[0] for r in self.conn.execute("SELECT body FROM private_note")),
                         sorted(["Lời mới đã đổi", "Của người khác"]))


class SearchTest(CopyTestCase):
    def setUp(self):
        super().setUp()
        c = self.conn
        self.dang = people.add_person(c, nfd(NAME), status_id=self.status("member"), start_date="2020-01-01")
        self.dung = people.add_person(c, "Nguyễn Hải Dũng")
        self.dang2 = people.add_person(c, "Đặng Văn Nguyên")
        self.pct = people.add_person(c, "Lê 100% Vui_Vẻ")

    def ids(self, q, **kw):
        return [r["id"] for r in search.search_persons(self.conn, q, **kw)]

    def test_search_finds_with_or_without_diacritics(self):
        for q in ("nguyen hai dang", NAME, nfd(NAME), "dang nguyen", "DANG  hai", "Đăng", "hai dang"):
            self.assertIn(self.dang, self.ids(q), q)
        self.assertNotIn(self.dung, self.ids("nguyen hai dang"))
        self.assertEqual(self.ids("nguyen hai dang"), [self.dang])

    def test_search_returns_status_name(self):
        row = search.search_persons(self.conn, "hai dang")[0]
        self.assertEqual((row["id"], row["full_name"], row["status_name"]), (self.dang, NAME, "Member"))
        self.assertIsNone(search.search_persons(self.conn, "dung")[0]["status_name"])

    def test_whole_words_first_and_limit(self):
        self.assertEqual(self.ids("dang")[:2], [self.dang, self.dang2])
        self.assertEqual(len(self.ids("nguyen", limit=1)), 1)
        self.assertEqual(self.ids("   "), [])
        self.assertEqual(self.ids(""), [])
        with self.assertRaises(ValueError):
            search.search_persons(self.conn, "a", limit=0)

    def test_like_wildcards_are_plain_text(self):
        self.assertEqual(self.ids("%"), [self.pct])
        self.assertEqual(self.ids("_"), [self.pct])
        self.assertEqual(self.ids("'; DROP TABLE person; --"), [])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM person").fetchone()[0], 4)


if __name__ == "__main__":
    unittest.main()
