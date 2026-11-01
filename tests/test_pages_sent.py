"""Card C3: Sent documents and Lists through the real server (port 0, a new blank church copy in a
temp folder for each test, the Host header on every request, the Origin header on every POST)."""

import pathlib
import re
import tempfile
import unittest

import _support  # noqa: F401 - puts the repo root on sys.path
from churchmgr import db, lists
from churchmgr.pages import lists as list_pages
from churchmgr.pages import sent as sent_pages
from test_pages_documents import VI_NAME, VI_STAR, MultipartMixin
from test_pages_people import TODAY, section
from test_server import LiveServer, parse_panels

YEAR = TODAY.year


class BlankCopyTest(MultipartMixin, LiveServer, unittest.TestCase):
    """A new blank church copy (default lists only) and its own server for every test."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        assert "onedrive" not in str(self.root.resolve()).lower()
        self.copy = self.root / "copy"
        db.create_church_copy(self.copy, "Hội Thánh Thử C3").close()
        self.start(self.copy, self.root, remember=False)
        self.addCleanup(self.stop)

    def db(self):
        conn = db.connect(self.copy / db.DB_NAME)
        self.addCleanup(conn.close)
        return conn

    def item(self, list_name, name):
        return lists.find_item(self.db(), list_name, name=name)["id"]

    def page(self, path, expect=200):
        status, _h, text_ = self.get_text(path)
        self.assertEqual(status, expect, path)
        return text_

    def post(self, path, form, expect=303):
        status, headers, data = self.request("POST", path, form)
        self.assertEqual(status, expect, data.decode("utf-8")[:2000])
        return headers, data.decode("utf-8")

    def record(self, subject, recipient="Giáo hội", purpose="Invitation", day=None, file=None, expect=303, **extra):
        fields = {"date": day or TODAY.isoformat(), "recipient_id": self.item("recipient", recipient),
                  "purpose_id": self.item("purpose", purpose), "subject": subject, **extra}
        return self.post_multipart("/sent/new", fields, {"file": file} if file else None, expect=expect)

    def sent_rows(self):
        return self.db().execute("SELECT * FROM sent_document ORDER BY year, seq").fetchall()


class SentPagesTest(BlankCopyTest):
    def test_numbers_go_01_02_and_the_dashboard_next_number_follows(self):
        self.assertIn(f"01/{YEAR}", section(self.page("/"), "sent-documents"))
        page = self.page("/sent")
        self.assertIn(f">01/{YEAR}</span>", section(page, "next-number"))
        self.assertIn(f"No Sent document in {YEAR} yet.", page)

        headers, _ = self.record("Mời dự Lễ Tạ Ơn C3")
        self.assertTrue(headers["location"].startswith(f"/sent?year={YEAR}&msg=Saved+as+01%2F{YEAR}."),
                        headers["location"])
        self.assertIn(f"Saved as 01/{YEAR}.", self.page(headers["location"]))
        file_bytes = b"%PDF-1.4 C3 sent " + bytes(range(256))
        headers, _ = self.record("Thông báo C3", recipient="Chính quyền", purpose="Notice",
                                 file=(VI_NAME, file_bytes))
        page = self.page(headers["location"])
        self.assertIn(f"Saved as 02/{YEAR}.", page)

        rows = self.sent_rows()
        self.assertEqual([(r["year"], r["seq"]) for r in rows], [(YEAR, 1), (YEAR, 2)])
        self.assertIsNone(rows[0]["document_id"])
        doc_id = rows[1]["document_id"]
        doc = self.db().execute("SELECT * FROM document WHERE id = ?", (doc_id,)).fetchone()
        self.assertEqual(doc["original_name"], VI_NAME)
        self.assertEqual((doc["person_id"], doc["family_id"], doc["calendar_item_id"]), (None, None, None))

        listing = section(page, "sent-list")
        self.assertEqual(parse_panels(page).rows["sent-list"], 2)
        self.assertLess(listing.index(f"02/{YEAR}"), listing.index(f"01/{YEAR}"))  # newest first
        self.assertIn("Chính quyền", listing)
        self.assertIn(f'href="/documents/{doc_id}/file"', listing)
        self.assertIn(f">03/{YEAR}</span>", section(page, "next-number"))
        self.assertIn(f"03/{YEAR}", section(self.page("/"), "sent-documents"))  # the dashboard follows

        status, headers, data = self.request("GET", f"/documents/{doc_id}/file")
        self.assertEqual((status, data), (200, file_bytes))
        self.assertIn(VI_STAR, headers["content-disposition"])
        self.assertIn(f">02/{YEAR}</a>", section(self.page("/documents"), "documents-list"))

    def test_refusals_save_nothing(self):
        cases = [
            ({"day": "2999-01-01"}, "Date cannot be after today", 'id="f-date-error"'),
            ({"day": "2026-02-30"}, "Date must be a real date", 'id="f-date-error"'),
            ({"subject_": ""}, "Subject is required", 'id="f-subject-error"'),
            ({"file": ("rỗng.pdf", b"")}, "the file is empty", 'id="f-file-error"'),
        ]
        for extra, words, where in cases:
            subject = extra.pop("subject_", "C3 bị từ chối")
            _h, page = self.record(subject, expect=400, **extra)
            self.assertIn(words, page, words)
            self.assertIn(where, page, words)
        good = {"date": TODAY.isoformat(), "subject": "C3", "purpose_id": self.item("purpose", "Notice")}
        for recipient in ("", "999999", str(self.item("purpose", "Report"))):
            _h, page = self.post_multipart("/sent/new", {**good, "recipient_id": recipient}, expect=400)
            self.assertIn("Recipient: choose one from the list.", page)
            self.assertIn('id="f-recipient_id-error"', page)
        lists.set_active(self.db(), self.item("recipient", "Hội Thánh"), False)
        _h, page = self.record("C3", recipient="Hội Thánh", file=("thư.txt", b"C3 file"), expect=400)
        self.assertIn("Hội Thánh is hidden in Lists", page)
        self.assertIn('value="C3"', page)  # the form comes back with what was typed
        self.assertEqual(self.sent_rows(), [])
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM document").fetchone()[0], 0)
        self.assertEqual(list((self.copy / "documents").iterdir()), [])
        self.assertIn(f">01/{YEAR}</span>", section(self.page("/sent"), "next-number"))

    def test_other_years(self):
        self.record("Năm ngoái C3", day=f"{YEAR - 1}-12-30")
        page = self.page(f"/sent?year={YEAR - 1}")
        self.assertIn(f"01/{YEAR - 1}", section(page, "sent-list"))
        self.assertIn(f">02/{YEAR - 1}</span>", section(page, "next-number"))
        self.assertIn(f"No Sent document in {YEAR} yet.", self.page("/sent"))  # this year starts at 01 again
        self.assertIn("No Sent document in 2001 yet.", self.page("/sent?year=2001"))
        self.assertIn("Year must be", self.page("/sent?year=abc", expect=400))
        form = self.page("/sent/new")
        self.assertIn(f"01/{YEAR}", form)
        self.assertIn('enctype="multipart/form-data"', form)
        self.assertIn(f'value="{TODAY.isoformat()}"', form)  # today by default

    def test_years_from_1900_to_9999(self):
        """B24: a Sent document date and the year pages stay in 1900 to 9999, like Money."""
        sentence = '<p class="error" id="f-date-error">Date: use a year from 1900 to 9999.</p>'
        for day in ("1899-12-31", "0001-01-01"):
            _h, page = self.record("C4 năm cũ", day=day, file=("thư cũ.txt", b"C4 file"), expect=400)
            self.assertIn(sentence, page, day)
            self.assertNotIn("Saved as", page, day)
        self.assertEqual(self.sent_rows(), [])  # no row, no Document, no file left behind
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM document").fetchone()[0], 0)
        self.assertEqual(list((self.copy / "documents").iterdir()), [])
        headers, _ = self.record("C4 năm 1900", day="1900-01-01")
        self.assertIn("Saved as 01/1900.", self.page(headers["location"]))
        self.assertEqual([(r["year"], r["seq"]) for r in self.sent_rows()], [(1900, 1)])

        def chips(year):
            page = self.page(f"/sent?year={year}")
            start = page.index('aria-label="Years"')
            return page[start:page.index("</nav>", start)]
        first, last = chips(1900), chips(9999)
        self.assertNotIn("1899", first)  # no chip to a year that cannot be opened
        self.assertIn("1901 ›", first)
        self.assertNotIn("10000", last)
        self.assertIn("‹ 9998", last)
        for nav in (first, last):
            self.assertIn(">This year</a>", nav)
        for bad in ("1899", "10000", "0"):
            self.assertIn("Year: use a year from 1900 to 9999.", self.page(f"/sent?year={bad}", expect=400), bad)
        tag = re.search(r'<input[^>]*name="date"[^>]*>', self.page("/sent/new")).group(0)
        self.assertIn('min="1900-01-01"', tag)
        self.assertIn(f'max="{TODAY.isoformat()}"', tag)  # never after today, so never after 9999-12-31


class ListsPagesTest(BlankCopyTest):
    def options(self, path, field):
        page = self.page(path)
        start = page.index(f'name="{field}"')
        return page[start:page.index("</select>", start)]

    def test_add_rename_hide_and_show_a_recipient(self):
        page = self.page("/lists")
        spots = [page.index(f'data-panel="{list_pages.anchor(n)}"')
                 for n in list_pages.LIST_ORDER[0::2] + list_pages.LIST_ORDER[1::2]]
        self.assertEqual(spots, sorted(spots))  # left: Recipient, Fund, Ministry; right: Purpose, Spending category, Status
        self.assertEqual(parse_panels(page).h1, 1)

        headers, _ = self.post("/lists/recipient/add", {"name": " Ủy ban  xã C3 "})
        self.assertTrue(headers["location"].endswith("#list-recipient"), headers["location"])
        item = lists.find_item(self.db(), "recipient", name="Ủy ban xã C3")
        self.assertEqual((item["active"], item["sort_order"]), (1, 4))
        self.assertIn("Ủy ban xã C3", section(self.page("/lists"), "list-recipient"))
        self.assertIn("Ủy ban xã C3", self.options("/sent/new", "recipient_id"))
        self.record("Xin xác nhận C3", recipient="Ủy ban xã C3")
        self.assertIn("1 Sent document", section(self.page("/lists"), "list-recipient"))

        self.post(f"/lists/items/{item['id']}/rename", {"name": "UBND xã C3"})
        self.assertEqual(lists.get_item(self.db(), item["id"])["name"], "UBND xã C3")
        self.assertIn("UBND xã C3", section(self.page("/sent"), "sent-list"))  # the old row follows the name

        headers, _ = self.post(f"/lists/items/{item['id']}/hide", {})
        self.assertIn("is hidden", self.page(headers["location"].split("#")[0]))
        self.assertEqual(lists.get_item(self.db(), item["id"])["active"], 0)
        self.assertNotIn("UBND xã C3", self.options("/sent/new", "recipient_id"))  # not offered for new entries
        self.assertIn("UBND xã C3", section(self.page("/sent"), "sent-list"))  # the old Sent document keeps it
        listed = section(self.page("/lists"), "list-recipient")
        self.assertIn("UBND xã C3", listed)
        self.assertIn(">Hidden</span>", listed)
        self.assertIn(f'action="/lists/items/{item["id"]}/show"', listed)
        self.record("C3 sau khi ẩn", recipient="UBND xã C3", expect=400)

        self.post(f"/lists/items/{item['id']}/show", {})
        self.assertIn("UBND xã C3", self.options("/sent/new", "recipient_id"))
        count = self.db().execute("SELECT COUNT(*) FROM list_item WHERE list_name = 'recipient'").fetchone()[0]
        self.assertEqual(count, 4)  # nothing was deleted

    def test_refusals(self):
        _h, page = self.post("/lists/recipient/add", {"name": "Giáo hội"}, expect=400)
        self.assertIn("is already in the Recipient list", page)
        self.assertIn('id="add-list-recipient-error"', page)
        _h, page = self.post("/lists/recipient/add", {"name": "giáo hội"}, expect=400)  # B4: case aside
        self.assertIn('<p class="error" id="add-list-recipient-error">giáo hội is already in the Recipient list.</p>',
                      page)
        _h, page = self.post("/lists/spending_category/add", {"name": "  "}, expect=400)
        self.assertIn("Name is required", page)
        self.assertIn('id="add-list-spending-category-error"', page)
        rid = self.item("recipient", "Giáo hội")
        _h, page = self.post(f"/lists/items/{rid}/rename", {"name": "Hội Thánh"}, expect=400)
        self.assertIn("is already in the Recipient list", page)
        self.assertIn(f'id="rename-{rid}-error"', page)
        self.assertIn("<details class=\"rename\" open>", page)  # the rename form opens by itself
        self.assertIn("There is no list called", self.post("/lists/nope/add", {"name": "X"}, expect=400)[1])
        self.post("/lists/items/999999/hide", {}, expect=400)

        funds = lists.get_list(self.db(), "fund")
        for f in funds[1:]:
            self.post(f"/lists/items/{f['id']}/hide", {})
        _h, page = self.post(f"/lists/items/{funds[0]['id']}/hide", {}, expect=400)
        self.assertIn("Keep at least one Fund shown", page)
        self.assertEqual([i["name"] for i in lists.get_list(self.db(), "fund")], [funds[0]["name"]])
        self.assertEqual(len(lists.get_list(self.db(), "fund", include_hidden=True)), len(funds))

    def test_check_can_hide(self):
        rows = [{"id": 1, "active": 1, "list_name": "fund"}, {"id": 2, "active": 0, "list_name": "fund"}]
        with self.assertRaises(ValueError):
            list_pages.check_can_hide(rows, 1)
        list_pages.check_can_hide(rows, 2)  # hiding a hidden one again is fine
        list_pages.check_can_hide(rows + [{"id": 3, "active": 1, "list_name": "fund"}], 1)


class SmallLogicTest(unittest.TestCase):
    def test_year_of(self):
        self.assertEqual(sent_pages.year_of("", TODAY), TODAY.year)
        self.assertEqual(sent_pages.year_of(" 2025 ", TODAY), 2025)
        for bad in ("abc", "25", "2025-01", "-2025"):
            with self.assertRaises(ValueError):
                sent_pages.year_of(bad, TODAY)


if __name__ == "__main__":
    unittest.main()
