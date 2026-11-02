"""I18N-U4: the Money pages and the Giving statement (and its print view) in Tiếng Việt and English.

Two real servers on 127.0.0.1 (port 0) over two fake churches in temp folders, built the same way (same
seed, same day): one Vietnamese, one English. Every page of this card on the Vietnamese copy has
``<html lang="vi">``, the switch, no English word left and no ``[[key]]``; on the English copy no
``[[key]]``. The amounts are the same ``format_vnd`` text in both. Then form errors and flash messages in
Tiếng Việt, and the errors of ``money.py`` (``TextError``: ``str()`` English, ``error_text(e, "vi")``
Vietnamese).
"""

import datetime as dt
import html
import pathlib
import re
import tempfile
import unittest

import _support
from churchmgr import db, fake, lists, money, server
from churchmgr.i18n import TextError, english_left, error_text
from churchmgr.pages import money as money_pages
from test_i18n_core import html_lang, switch
from test_pages_money import amounts_in
from test_pages_people import section, shown
from test_server import LiveServer

TODAY = dt.date.today()
LANGS = ("vi", "en")
AMOUNT = re.compile(r"-?[0-9]{1,3}(?:\.[0-9]{3})* ₫")  # how format_vnd writes money, in both languages
HELP_VI = "Hãy ghi số đồng nguyên lớn hơn 0, ví dụ 1250000 hoặc 1.250.000."
HELP_EN = "Write a whole number of dong above 0, for example 1250000 or 1.250.000."


def flash(page):
    m = re.search(r'<p class="flash" role="status">([^<]*)</p>', page)
    return html.unescape(m.group(1)) if m else None


def plain(fragment):
    """The text of an HTML fragment, without its tags."""
    return html.unescape(re.sub(r"<[^>]+>", "", fragment))


class Site(LiveServer):
    """The request helpers of ``LiveServer`` on one server of this test class."""

    def __init__(self, httpd):
        self.httpd = httpd


class MoneyTwoLanguagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        root = pathlib.Path(cls.tmp.name)
        assert "onedrive" not in str(root.resolve()).lower()
        cls.copies, cls.sites = {}, {}
        for lang in LANGS:
            copy = root / f"fake-{lang}"
            fake.build_fake_church(copy, people=20, lang=lang)
            httpd = server.make_server(copy, root, 0, remember=False)
            server.serve_in_thread(httpd)
            cls.copies[lang], cls.sites[lang] = copy, Site(httpd)

    @classmethod
    def tearDownClass(cls):
        for site in cls.sites.values():
            site.httpd.shutdown()
            site.httpd.server_close()
        cls.tmp.cleanup()

    # ---- helpers

    def db(self, lang):
        conn = db.connect(self.copies[lang] / db.DB_NAME)
        self.addCleanup(conn.close)
        return conn

    def one(self, lang, sql, *params):
        row = self.db(lang).execute(sql, params).fetchone()
        return row[0] if row else None

    def fetch(self, lang, method, path, expect=200, form=None):
        status, headers, data = self.sites[lang].request(method, path, form if method == "POST" else None)
        page = data.decode("utf-8")
        self.assertEqual(status, expect, (lang, method, path, page[:600]))
        return headers, page

    def get(self, lang, path, expect=200):
        return self.fetch(lang, "GET", path, expect)[1]

    def post(self, lang, path, form, expect=303):
        return self.fetch(lang, "POST", path, expect, form)

    def follow(self, lang, headers):
        """The page a redirect goes to, and its flash message."""
        page = self.get(lang, headers["location"])
        return page, flash(page)

    def fund(self, lang):
        item = lists.get_list(self.db(lang), "fund")[0]
        return item["id"], item["name"]

    def category(self, lang):
        item = lists.get_list(self.db(lang), "spending_category")[0]
        return item["id"], item["name"]

    def no_name_month(self, lang):
        return self.one(lang, "SELECT substr(MAX(date), 1, 7) FROM offering "
                              "WHERE giver_person_id IS NULL AND giver_family_id IS NULL")

    def givers(self, lang):
        """A Person and a Family with Offerings this year (a Person with none early in January)."""
        year = str(TODAY.year)
        pid = self.one(lang, "SELECT giver_person_id FROM offering WHERE giver_person_id IS NOT NULL "
                             "AND substr(date, 1, 4) = ? GROUP BY giver_person_id ORDER BY COUNT(*) DESC, "
                             "giver_person_id LIMIT 1", year) or self.one(lang, "SELECT MIN(id) FROM person")
        fid = self.one(lang, "SELECT giver_family_id FROM offering WHERE giver_family_id IS NOT NULL "
                             "AND substr(date, 1, 4) = ? ORDER BY giver_family_id LIMIT 1", year)
        return pid, fid

    def card_pages(self, lang):
        """Every page of this card: ``(method, path, status)``. A Delete with no ``confirm`` is the question page."""
        oid = self.one(lang, "SELECT MAX(id) FROM offering WHERE giver_person_id IS NOT NULL")
        no_name = self.one(lang, "SELECT MAX(id) FROM offering WHERE giver_person_id IS NULL "
                                 "AND giver_family_id IS NULL")
        eid = self.one(lang, "SELECT MAX(id) FROM expense WHERE note IS NOT NULL")
        pid, fid = self.givers(lang)
        year = TODAY.year
        return [
            ("GET", "/money", 200), ("GET", f"/money?month={self.no_name_month(lang)}", 200),
            ("GET", "/money?month=2001-01", 200),
            ("GET", "/money/offerings/new", 200), ("GET", "/money/expenses/new", 200),
            ("GET", f"/money/offerings/{oid}/edit", 200), ("GET", f"/money/offerings/{no_name}/edit", 200),
            ("GET", f"/money/expenses/{eid}/edit", 200),
            ("POST", f"/money/offerings/{oid}/delete", 200), ("POST", f"/money/offerings/{no_name}/delete", 200),
            ("POST", f"/money/expenses/{eid}/delete", 200),
            ("GET", "/money/statement", 200),
            ("GET", f"/money/statement?person_id={pid}&year={year}", 200),
            ("GET", f"/money/statement?family_id={fid}&year={year}", 200),
            ("GET", f"/money/statement?person_id={pid}&year=2001", 200),
            ("GET", "/money/offerings/999999/edit", 404), ("GET", "/money/expenses/999999/edit", 404),
        ]

    def assert_vietnamese(self, page, where):
        self.assertEqual(html_lang(page), "vi", where)
        self.assertEqual(switch(page)[1:], ("true", "false"), where)
        self.assertNotIn("[[", page, where)
        self.assertEqual(english_left(page), [], where)

    # ---- every page

    def test_every_page_in_vietnamese(self):
        for method, path, status in self.card_pages("vi"):
            self.assert_vietnamese(self.fetch("vi", method, path, status, {})[1], (method, path))

    def test_every_page_in_english(self):
        for method, path, status in self.card_pages("en"):
            page = self.fetch("en", method, path, status, {})[1]
            self.assertEqual(html_lang(page), "en", path)
            self.assertEqual(switch(page)[1:], ("false", "true"), path)
            self.assertNotIn("[[", page, path)

    def test_the_words_on_the_vietnamese_pages(self):
        month = self.no_name_month("vi")
        page = self.get("vi", f"/money?month={month}")
        self.assertIn("<h1>Tài chính</h1>", page)
        self.assertIn('aria-label="Tổng cộng"', page)
        self.assertIn('<span class="kpi-label">Số dư</span>', page)
        self.assertIn('<a class="btn primary" href="/money/offerings/new">Ghi Dâng hiến</a>', page)
        self.assertIn('<label for="money-month">Đến tháng</label>', page)
        offerings = section(page, "offerings")
        self.assertIn('<th scope="col" class="date">Ngày</th><th scope="col">Quỹ</th>'
                      '<th scope="col">Người dâng hiến</th><th scope="col" class="n">Số tiền</th>', offerings)
        self.assertIn('<span class="faint">Ẩn danh</span>', offerings)  # the no-name offering
        self.assertIn('<th scope="row" colspan="3">Tổng Dâng hiến</th>', offerings)
        self.assertIn("Chưa ghi khoản Dâng hiến nào trong Tháng 1/2001.",
                      section(self.get("vi", "/money?month=2001-01"), "offerings"))
        form = self.get("vi", "/money/offerings/new")
        self.assertIn('<option value="">— Không có Người dâng hiến (Ẩn danh) —</option>', form)
        self.assertIn('<optgroup label="Người">', form)
        self.assertIn('<optgroup label="Gia đình">', form)
        self.assertIn('<p class="lead">Không có Dâng hiến nào với mã số này.</p>',
                      self.get("vi", "/money/offerings/999999/edit", 404))

        pid, fid = self.givers("vi")
        sheet = section(self.get("vi", f"/money/statement?person_id={pid}&year={TODAY.year}"), "statement")
        self.assertIn(f'<h2 id="st-title">Tổng kết dâng hiến {TODAY.year}</h2>', sheet)
        for word in ("Người dâng hiến", "Năm", "Ngày in"):
            self.assertIn(f"<dt>{word}</dt>", sheet)
        page = self.get("vi", f"/money/statement?family_id={fid}&year={TODAY.year}")
        sheet = section(page, "statement")
        self.assertIn('<th scope="col">Người dâng</th>', sheet)
        self.assertRegex(sheet, r'<th scope="row" colspan="3">Tổng \([0-9]+ khoản Dâng hiến\)</th>')
        self.assertIn("Tổng kết dâng hiến của một Gia đình cũng gồm Dâng hiến của từng Người", sheet)
        self.assertIn('<span class="faint">(Gia đình)</span>', sheet)
        self.assertIn('<button class="btn primary" type="button" data-print>In</button>', page)
        empty_year = section(self.get("vi", f"/money/statement?person_id={pid}&year=2001"), "statement")
        self.assertIn("Người dâng hiến này không có khoản Dâng hiến nào trong năm 2001. Tổng 0 ₫.", empty_year)

    def test_the_delete_question_in_vietnamese(self):
        oid = self.one("vi", "SELECT MAX(id) FROM offering WHERE giver_person_id IS NOT NULL")
        row = money.get_offering(self.db("vi"), oid)
        _h, page = self.post("vi", f"/money/offerings/{oid}/delete", {}, expect=200)
        question = plain(section(page, "confirm"))
        self.assertIn(f"Xóa khoản Dâng hiến {money.format_vnd(row['amount'])} ngày {shown(row['date'])}?", question)
        self.assertIn(f"Quỹ {row['fund_name']} · Người dâng hiến {row['giver_name']}", question)
        self.assertIn("<h1>Xóa khoản Dâng hiến này?</h1>", page)
        self.assertIsNotNone(money.get_offering(self.db("vi"), oid))  # only a question: nothing deleted

    # ---- money text

    def test_the_amounts_are_the_same_text_in_both_languages(self):
        pages = {lang: [] for lang in LANGS}
        for lang in LANGS:
            pid, fid = self.givers(lang)
            for path in ("/money", f"/money?month={self.no_name_month(lang)}",
                         f"/money/statement?person_id={pid}&year={TODAY.year}",
                         f"/money/statement?family_id={fid}&year={TODAY.year}"):
                pages[lang].append(self.get(lang, path))
        for vi_page, en_page in zip(pages["vi"], pages["en"], strict=True):
            vi_amounts, en_amounts = AMOUNT.findall(vi_page), AMOUNT.findall(en_page)
            self.assertTrue(vi_amounts)
            self.assertEqual(vi_amounts, en_amounts)  # the same figures, written the same way
        for lang in LANGS:
            totals = money.month_totals(self.db(lang), TODAY.year, TODAY.month)
            strip = section(pages[lang][0], "money-totals")
            self.assertEqual(amounts_in(strip), [totals["offerings"], totals["expenses"], totals["balance"]])
            for key in ("offerings", "expenses", "balance"):
                self.assertIn(money.format_vnd(totals[key]), strip)

    # ---- form errors and flash messages

    def test_form_errors_in_vietnamese(self):
        fund, _name = self.fund("vi")
        cat, _cat_name = self.category("vi")
        good = {"date": TODAY.isoformat(), "amount": "100.000", "fund_id": fund, "giver": "", "note": ""}
        tomorrow = (TODAY + dt.timedelta(days=1)).isoformat()
        oid = self.one("vi", "SELECT MAX(id) FROM offering")
        eid = self.one("vi", "SELECT MAX(id) FROM expense")
        counts = (self.one("vi", "SELECT COUNT(*) FROM offering"), self.one("vi", "SELECT COUNT(*) FROM expense"))
        cases = (
            ("/money/offerings/new", {**good, "amount": "1,5"}, "amount",
             f'Không đọc được Số tiền "1,5". Không dùng số lẻ, không dùng dấu trừ. {HELP_VI}'),
            ("/money/offerings/new", {**good, "amount": ""}, "amount", f"Chưa nhập Số tiền. {HELP_VI}"),
            (f"/money/offerings/{oid}/edit", {**good, "amount": "0"}, "amount", f"Số tiền phải lớn hơn 0. {HELP_VI}"),
            ("/money/offerings/new", {**good, "date": tomorrow}, "date",
             f"Ngày không được sau hôm nay ({shown(TODAY.isoformat())}). Hãy dùng hôm nay hoặc một ngày trước đó."),
            ("/money/offerings/new", {**good, "date": "1899-12-31"}, "date", "Ngày: năm phải từ 1900 đến 9999."),
            ("/money/offerings/new", {**good, "date": "31/12/2025"}, "date",
             "Ngày phải là một ngày có thật, viết YYYY-MM-DD, ví dụ 2026-05-31."),
            ("/money/offerings/new", {**good, "fund_id": ""}, "fund_id", "Quỹ: hãy chọn một Quỹ."),
            ("/money/offerings/new", {**good, "giver": "person-abc"}, "giver", "Người dâng hiến phải là số nguyên."),
            ("/money/offerings/new", {**good, "giver": "giver-3"}, "giver",
             "Người dâng hiến phải là một Người, một Gia đình, hoặc để trống."),
            ("/money/expenses/new", {"date": TODAY.isoformat(), "amount": "2,5", "spending_category_id": cat},
             "amount", f'Không đọc được Số tiền "2,5". Không dùng số lẻ, không dùng dấu trừ. {HELP_VI}'),
            (f"/money/expenses/{eid}/edit", {"date": TODAY.isoformat(), "amount": "1000", "spending_category_id": ""},
             "spending_category_id", "Hạng mục chi: hãy chọn một Hạng mục chi."),
        )
        for path, form, field, sentence in cases:
            _h, page = self.post("vi", path, form, expect=400)
            where = (path, form)
            self.assertIn(f'<p class="error" id="f-{field}-error">{html.escape(sentence)}</p>', page, where)
            self.assert_vietnamese(page, where)
        # a sentence that fits no field shows above the button, in Tiếng Việt too
        pid, fid = self.givers("vi")
        page = self.get("vi", f"/money/statement?person_id={pid}&family_id={fid}&year={TODAY.year}", 400)
        self.assertIn('<p class="error" role="alert">Tổng kết dâng hiến là của một Người hoặc một Gia đình: '
                      "hãy chọn đúng một.</p>", page)
        self.assert_vietnamese(page, "statement of two givers")
        page = self.get("vi", "/money/statement?person_id=999999", 400)
        self.assertIn("Không có Người với mã số 999999.", page)
        self.assert_vietnamese(page, "statement of no Person")
        self.assertEqual((self.one("vi", "SELECT COUNT(*) FROM offering"),
                          self.one("vi", "SELECT COUNT(*) FROM expense")), counts)  # nothing saved

    def test_flash_messages_in_both_languages(self):
        """The same Offering and Expense on both copies: recorded, corrected, deleted. The flash is in the
        language of the copy, the amount is the same text in both. Each copy ends as it began."""
        day = shown(TODAY.isoformat())
        words = {
            "vi": ("Đã ghi Dâng hiến {a} ngày {d} ({n}).", "Đã lưu Dâng hiến: {a} ngày {d} ({n}).",
                   "Đã xóa Dâng hiến {a} ngày {d}.", "Đã ghi Khoản chi {a} ngày {d} ({n}).",
                   "Đã xóa Khoản chi {a} ngày {d}."),
            "en": ("Offering of {a} recorded on {d} ({n}).", "Offering saved: {a} on {d} ({n}).",
                   "Offering of {a} on {d} deleted.", "Expense of {a} recorded on {d} ({n}).",
                   "Expense of {a} on {d} deleted."),
        }
        for lang in LANGS:
            recorded, saved, deleted, expense_recorded, expense_deleted = words[lang]
            fund, fund_name = self.fund(lang)
            form = {"date": TODAY.isoformat(), "amount": "1.234.567", "fund_id": fund, "giver": "", "note": ""}
            headers, _ = self.post(lang, "/money/offerings/new", form)
            page, msg = self.follow(lang, headers)
            self.assertEqual(msg, recorded.format(a="1.234.567 ₫", d=day, n=fund_name))
            if lang == "vi":
                self.assert_vietnamese(page, "flash: recorded")
            oid = self.one(lang, "SELECT MAX(id) FROM offering")
            headers, _ = self.post(lang, f"/money/offerings/{oid}/edit", {**form, "amount": "2000000"})
            page, msg = self.follow(lang, headers)
            self.assertEqual(msg, saved.format(a="2.000.000 ₫", d=day, n=fund_name))
            headers, _ = self.post(lang, f"/money/offerings/{oid}/delete", {"confirm": "yes"})
            page, msg = self.follow(lang, headers)
            self.assertEqual(msg, deleted.format(a="2.000.000 ₫", d=day))
            if lang == "vi":
                self.assert_vietnamese(page, "flash: deleted")
            self.assertIsNone(money.get_offering(self.db(lang), oid))

            cat, cat_name = self.category(lang)
            headers, _ = self.post(lang, "/money/expenses/new", {"date": TODAY.isoformat(), "amount": "650000",
                                                                 "spending_category_id": cat, "note": ""})
            page, msg = self.follow(lang, headers)
            self.assertEqual(msg, expense_recorded.format(a="650.000 ₫", d=day, n=cat_name))
            eid = self.one(lang, "SELECT MAX(id) FROM expense")
            headers, _ = self.post(lang, f"/money/expenses/{eid}/delete", {"confirm": "yes"})
            page, msg = self.follow(lang, headers)
            self.assertEqual(msg, expense_deleted.format(a="650.000 ₫", d=day))
            if lang == "vi":
                self.assert_vietnamese(page, "flash: expense deleted")

    # ---- the Giving statement on paper

    def test_the_print_view(self):
        """The statement page is the print view: print.css hides the forms (the switch too) and the buttons."""
        pid, _fid = self.givers("vi")
        private_text = "U4-RIÊNG-Cầu nguyện cho công việc"
        self.post("vi", f"/people/{pid}/private-notes", {"body": private_text})
        page = self.get("vi", f"/money/statement?person_id={pid}&year={TODAY.year}")
        self.assert_vietnamese(page, "print view")
        self.assertIn('<link rel="stylesheet" href="/static/print.css">', page)
        self.assertIn("data-print>In</button>", page)
        self.assertIn('<form class="lang-switch"', page)
        css = (_support.ROOT / "web" / "print.css").read_text(encoding="utf-8")
        hidden = re.search(r"@media print \{\s*([^{]*)\{ display: none !important; \}", css).group(1)
        for rule in ("form", "button", ".btn", ".title-row .actions"):
            self.assertIn(f"{rule},", hidden + ",")
        for text_ in (private_text, fake.MARKER, "Hộp dâng hiến"):  # no Private note, no Offering note
            self.assertNotIn(text_, page)

    # ---- the errors of money.py

    def test_text_errors_of_money_py(self):
        conn = self.db("vi")
        fund, _name = self.fund("vi")
        day = TODAY.isoformat()
        cases = (
            (lambda: money.parse_amount("1,5"),
             f'Amount "1,5" not understood. No decimals, no minus sign. {HELP_EN}',
             f'Không đọc được Số tiền "1,5". Không dùng số lẻ, không dùng dấu trừ. {HELP_VI}'),
            (lambda: money.parse_amount(None), f"Amount not understood. {HELP_EN}",
             f"Không đọc được Số tiền. {HELP_VI}"),
            (lambda: money.parse_amount(" ₫ "), f"Amount is empty. {HELP_EN}", f"Chưa nhập Số tiền. {HELP_VI}"),
            (lambda: money.parse_amount("9" * 20), "Amount is too large.", "Số tiền quá lớn."),
            (lambda: money.check_amount("100"), f"Amount must be a whole number of dong. {HELP_EN}",
             f"Số tiền phải là số đồng nguyên. {HELP_VI}"),
            (lambda: money.check_amount(0), f"Amount must be above 0. {HELP_EN}", f"Số tiền phải lớn hơn 0. {HELP_VI}"),
            (lambda: money.format_vnd("5"), "Only a whole number of dong can be shown as money.",
             "Chỉ số đồng nguyên mới hiện được thành số tiền."),
            (lambda: money.month_totals(conn, 2026, 13), "Month must be a whole number from 1 to 12.",
             "Tháng phải là số nguyên từ 1 đến 12."),
            (lambda: money.list_offerings(conn, "2026-02-01", "2026-01-01"), "The end date is before the start date.",
             "Ngày kết thúc ở trước ngày bắt đầu."),
            (lambda: money.list_expenses(conn, "x", "2026-01-01"),
             "Start date must be a real date written YYYY-MM-DD, for example 2026-05-31.",
             "Ngày bắt đầu phải là một ngày có thật, viết YYYY-MM-DD, ví dụ 2026-05-31."),
            (lambda: money.delete_offering(conn, 999999), "No Offering with id 999999.",
             "Không có Dâng hiến với mã số 999999."),
            (lambda: money.delete_expense(conn, 999999), "No Expense with id 999999.",
             "Không có Khoản chi với mã số 999999."),
            (lambda: money.get_offering(conn, "abc"), "Offering must be a whole number.", "Dâng hiến phải là số nguyên."),
            (lambda: money.add_offering(conn, "1899-12-31", 1000, fund), "Date: use a year from 1900 to 9999.",
             "Ngày: năm phải từ 1900 đến 9999."),
            (lambda: money.add_offering(conn, day, 1000, fund, giver_person_id=1, giver_family_id=1),
             "An Offering has one Giver: a Person or a Family, not both.",
             "Một khoản Dâng hiến chỉ có một Người dâng hiến: một Người hoặc một Gia đình, không phải cả hai."),
            (lambda: money.add_offering(conn, day, 1000, fund, giver_person_id=999999), "No Person with id 999999.",
             "Không có Người với mã số 999999."),
            (lambda: money.giving_statement(conn, TODAY.year),
             "A Giving statement is for one Person or one Family: give exactly one of them.",
             "Tổng kết dâng hiến là của một Người hoặc một Gia đình: hãy chọn đúng một."),
            (lambda: money.giving_statement(conn, TODAY.year, family_id=999999), "No Family with id 999999.",
             "Không có Gia đình với mã số 999999."),
            (lambda: money_pages.parse_giver("giver-3"), "Giver must be a Person, a Family, or none.",
             "Người dâng hiến phải là một Người, một Gia đình, hoặc để trống."),
        )
        for call, english, vietnamese in cases:
            with self.assertRaises(TextError) as ctx:
                call()
            self.assertIsInstance(ctx.exception, ValueError)
            self.assertEqual(str(ctx.exception), english)
            self.assertEqual(error_text(ctx.exception, "en"), english)
            self.assertEqual(error_text(ctx.exception, "vi"), vietnamese)

    def test_every_refusal_in_the_money_code_is_a_text_error(self):
        for name in ("money.py", "pages/money.py"):
            source = (_support.ROOT / "churchmgr" / name).read_text(encoding="utf-8")
            self.assertNotIn("raise ValueError", source, name)


if __name__ == "__main__":
    unittest.main()
