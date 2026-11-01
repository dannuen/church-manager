import sqlite3
import unicodedata
import unittest

from _support import CopyTestCase
from churchmgr import db, documents, sent


class SentDocumentTest(CopyTestCase):
    def setUp(self):
        super().setUp()
        self.gov = self.item("recipient", name="Chính quyền")
        self.church = self.item("recipient", name="Hội Thánh")
        self.notice = self.item("purpose", name="Notice")
        self.invite = self.item("purpose", name="Invitation")

    def add(self, date, **kwargs):
        return sent.add_sent_document(self.conn, date, self.gov, self.notice, **kwargs)

    def test_numbers_per_year_restart_and_never_repeat(self):
        self.assertEqual(sent.next_number(self.conn, 2026), "01/2026")
        self.assertEqual(sent.next_number(self.conn, 2026), "01/2026")  # a preview keeps nothing
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM sent_document").fetchone()[0], 0)
        got = [self.add(d)[1] for d in ("2026-01-05", "2026-02-10", "2026-12-31")]
        self.assertEqual(got, ["01/2026", "02/2026", "03/2026"])
        self.assertEqual(self.add("2027-01-01")[1], "01/2027")  # new year starts at 01
        self.assertEqual(self.add("2026-12-31")[1], "04/2026")  # a late entry for the old year goes on
        self.assertEqual(sent.next_number(self.conn, 2026), "05/2026")
        self.assertEqual(sent.next_number(self.conn, "2027"), "02/2027")
        self.assertEqual(sent.next_number(self.conn, 2025), "01/2025")
        numbers = [r["number"] for y in (2026, 2027) for r in sent.list_sent_documents(self.conn, y)]
        self.assertEqual(numbers, ["01/2026", "02/2026", "03/2026", "04/2026", "01/2027"])
        self.assertEqual(len(numbers), len(set(numbers)))
        self.assertFalse([n for n in dir(sent) if "delete" in n or "remove" in n])

    def test_number_text_format(self):
        self.assertEqual(sent.number_text(6, 2026), "06/2026")
        self.assertEqual(sent.number_text(10, 2026), "10/2026")
        self.assertEqual(sent.number_text(123, 2026), "123/2026")
        last = [self.add("2026-03-01")[1] for _ in range(10)][-1]
        self.assertEqual(last, "10/2026")
        self.assertEqual(sent.list_sent_documents(self.conn, 2026)[-1]["number"], "10/2026")

    def test_two_connections_never_share_a_number(self):
        other = db.open_church_copy(self.folder)
        self.addCleanup(other.close)
        got = []
        for k in range(6):
            conn = self.conn if k % 2 == 0 else other
            got.append(sent.add_sent_document(conn, "2026-04-01", self.gov, self.notice)[1])
        self.assertEqual(got, [f"{k:02d}/2026" for k in range(1, 7)])

    def test_list_details_and_checks(self):
        doc = documents.add_document(self.conn, self.folder, b"x", "Giấy mời.txt")
        sid, number = sent.add_sent_document(self.conn, "2026-05-02", self.church, self.invite,
                                             subject=unicodedata.normalize("NFD", "Mời dự Lễ"), document_id=doc)
        row = sent.list_sent_documents(self.conn, 2026)[0]
        self.assertEqual((row["id"], row["number"], row["date"], row["recipient_name"], row["purpose_name"]),
                         (sid, number, "2026-05-02", "Hội Thánh", "Invitation"))
        self.assertEqual((row["subject"], row["document_name"]), ("Mời dự Lễ", "Giấy mời.txt"))
        bad = [
            (("2026-05-02", self.notice, self.notice), {}),  # a Purpose is not a Recipient
            (("2026-05-02", self.gov, self.gov), {}),
            (("02/05/2026", self.gov, self.notice), {}),
            (("2026-05-02", self.gov, self.notice), {"document_id": 9999}),
            (("2026-05-02", 9999, self.notice), {}),
        ]
        for args, kwargs in bad:
            with self.assertRaises(ValueError, msg=(args, kwargs)):
                sent.add_sent_document(self.conn, *args, **kwargs)
        self.assertEqual(sent.next_number(self.conn, 2026), "02/2026")  # refused calls took no number
        with self.assertRaises(ValueError):
            sent.next_number(self.conn, 26.5)

    def test_a_date_needs_a_year_from_1900_to_9999(self):
        """B24: a row dated 1899 got a number but showed in no Sent documents year."""
        for day in ("1899-12-31", "0001-01-01"):
            with self.assertRaisesRegex(ValueError, r"^Date: use a year from 1900 to 9999\.$", msg=day):
                self.add(day)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM sent_document").fetchone()[0], 0)  # nothing saved
        self.assertEqual(self.add("1900-01-01")[1], "01/1900")
        self.assertEqual(self.add("9999-12-31")[1], "01/9999")
        self.assertEqual([r["number"] for r in sent.list_sent_documents(self.conn, 1900)], ["01/1900"])
        self.assertEqual([r["number"] for r in sent.list_sent_documents(self.conn, 9999)], ["01/9999"])

    def test_database_keeps_the_rule_too(self):
        self.add("2026-01-05")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO sent_document (year, seq, date, recipient_id, purpose_id, created_at) "
                "VALUES (2026, 1, '2026-02-01', ?, ?, 'x')", (self.gov, self.notice))


if __name__ == "__main__":
    unittest.main()
