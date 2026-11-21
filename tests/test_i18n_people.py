"""I18N-U2: the People, Families and Chi phái pages in Tiếng Việt and English.

Real servers on 127.0.0.1 (port 0) over fake churches in temp folders: a Vietnamese copy (every page
of this card has ``<html lang="vi">``, the switch, no English word left and no ``[[key]]``), a blank
Vietnamese copy (the empty lists) and an English copy (no ``[[key]]``; the old tests read its words).
Then the errors of ``people.py`` (``TextError``: ``str()`` English, ``error_text(e, "vi")`` Vietnamese)
and the Person story lines in both languages.
"""

import datetime as dt
import pathlib
import re
import tempfile
import unittest
import urllib.parse

import _support
from churchmgr import db, fake, i18n, lists, people, schema, story
from churchmgr.i18n import TEXT, TextError, english_left, error_text
from churchmgr.pages import people as people_pages
from test_i18n_core import html_lang, switch
from test_server import LiveServer

TODAY = dt.date.today()
ACCENTED = "Nguyễn Thị Ánh Tuyết"  # NFC
# The Documents block (pages/documents.py) belongs to the Documents card; it is left out of the
# English check until that card puts its words in the text table.
DOCUMENTS_BLOCK = re.compile(r'<div id="documents">.*?</section></div>', re.S)


def ago(days):
    return (TODAY - dt.timedelta(days=days)).isoformat()


def shown(iso):
    return dt.date.fromisoformat(iso).strftime("%d/%m/%Y")


def outside_documents(page):
    assert len(DOCUMENTS_BLOCK.findall(page)) <= 1
    return DOCUMENTS_BLOCK.sub("", page)


def flash(page):
    m = re.search(r'<p class="flash" role="status">([^<]*)</p>', page)
    return m.group(1) if m else None


class CopyServer(LiveServer):
    """One fake church in a temp folder and one live server for the test class."""

    LANG = "vi"
    PEOPLE = 20

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        cls.root = pathlib.Path(cls.tmp.name)
        assert "onedrive" not in str(cls.root.resolve()).lower()
        cls.copy = cls.root / "fake"
        if cls.PEOPLE:
            fake.build_fake_church(cls.copy, people=cls.PEOPLE, lang=cls.LANG)
        else:
            db.create_church_copy(cls.copy, "Hội Thánh Trống", lang=cls.LANG).close()
        cls.start(cls.copy, cls.root, remember=False)

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.tmp.cleanup()

    def db(self):
        conn = db.connect(self.copy / db.DB_NAME)
        self.addCleanup(conn.close)
        return conn

    def one(self, sql):
        return self.db().execute(sql).fetchone()[0]

    def page(self, path, expect=200):
        status, _h, page = self.get_text(path)
        self.assertEqual(status, expect, path)
        return page

    def post(self, path, form, expect=303):
        status, headers, data = self.request("POST", path, form)
        self.assertEqual(status, expect, data.decode("utf-8")[:1500])
        return headers, data.decode("utf-8")

    def follow(self, headers):
        """The page a redirect goes to, and its flash message."""
        page = self.page(headers["location"].split("#")[0])
        return page, flash(page)

    def item(self, list_name, code=None, name=None):
        return lists.find_item(self.db(), list_name, code=code, name=name)["id"]

    def card_pages(self):
        """Every page of this card: (path, status). The Status, Family and Ministry forms are on the
        Person page; the Trưởng Chi phái form is on the Chi phái page."""
        pid = self.one("SELECT fl.person_id FROM family_link fl JOIN ministry_link ml ON ml.person_id = fl.person_id "
                       "WHERE fl.end_date IS NULL AND ml.end_date IS NULL ORDER BY fl.person_id LIMIT 1")
        note_pid, note_id = self.db().execute("SELECT person_id, id FROM private_note LIMIT 1").fetchone()
        fid = self.one("SELECT family_id FROM chi_phai_link WHERE end_date IS NULL ORDER BY family_id LIMIT 1")
        cid = self.one("SELECT chi_phai_id FROM truong_chi_phai ORDER BY chi_phai_id LIMIT 1")
        return [("/people", 200), ("/people?status=none", 200), ("/people?q=zzzz", 200), ("/people/new", 200),
                (f"/people/{pid}", 200), (f"/people/{pid}/edit", 200),
                (f"/people/{note_pid}?edit_note={note_id}", 200),
                ("/families", 200), ("/families/new", 200), (f"/families/{fid}", 200), (f"/families/{fid}/edit", 200),
                ("/chi-phai", 200), ("/chi-phai/new", 200), (f"/chi-phai/{cid}", 200), (f"/chi-phai/{cid}/edit", 200),
                ("/people/999999", 404), ("/families/999999", 404), ("/chi-phai/999999", 404)]

    def new_person(self, name, start=None):
        form = {"full_name": name, "gender": "", "birth_date": "", "phone": "", "address": "", "note": "",
                "status_id": self.item("status", "visitor"), "start_date": start or ago(0)}
        headers, _ = self.post("/people/new", form)
        return int(re.fullmatch(r"/people/(\d+)\?msg=.+", headers["location"]).group(1)), headers


class VietnamesePagesTest(CopyServer, unittest.TestCase):
    def assert_vietnamese(self, page, where):
        self.assertEqual(html_lang(page), "vi", where)
        self.assertEqual(switch(page)[1:], ("true", "false"), where)
        self.assertNotIn("[[", page, where)
        self.assertEqual(english_left(outside_documents(page)), [], where)

    def test_every_page_of_this_card(self):
        for path, status in self.card_pages():
            self.assert_vietnamese(self.page(path, status), path)

    def test_the_forms_are_there_in_vietnamese(self):
        pages = dict(self.card_pages())
        person = next(p for p in pages if re.fullmatch(r"/people/\d+", p))
        pid = person.rsplit("/", 1)[1]
        page = self.page(person)
        for form in ("status", "family", "ministry", "private-notes"):
            self.assertIn(f'action="/people/{pid}/{form}"', page)
        self.assertIn('<label for="status-id">Trạng thái mới</label>', page)
        self.assertIn('<label for="family-role">Vai trò trong gia đình</label>', page)
        self.assertRegex(page, r'<option value="Head"( selected)?>Chủ gia đình</option>')
        self.assertRegex(page, r'<option value="Leader"( selected)?>Trưởng ban</option>')
        self.assertIn("<h2 id=\"p-private-note\">Ghi chú cá nhân — chỉ mình bạn thấy</h2>", page)
        self.assertIn('<th scope="col" class="n">Từ</th><th scope="col" class="n">Đến</th>', page)
        chi_phai = next(p for p in pages if re.fullmatch(r"/chi-phai/\d+", p))
        page = self.page(chi_phai)
        self.assertIn(f'action="{chi_phai}/truong"', page)
        self.assertIn("Chọn Trưởng Chi phái</button>", page)
        self.assertIn('<optgroup label="Những người khác">', page)
        self.assertIn('<a class="btn primary" href="/people/new">Thêm Người</a>', self.page("/people"))
        self.assertIn("<h1>Mọi người</h1>", self.page("/people"))
        self.assertIn("<h1>Gia đình</h1>", self.page("/families"))
        self.assertIn('<p class="lead">Không có Người với mã số này.</p>', self.page("/people/999999", 404))

    def test_the_person_story_is_vietnamese(self):
        conn = self.db()
        pid = conn.execute("SELECT o.giver_person_id FROM offering o JOIN calendar_person cp "
                           "ON cp.person_id = o.giver_person_id LIMIT 1").fetchone()[0]
        page = self.page(f"/people/{pid}")
        box = re.search(r'data-panel="story".*?</section>', page, re.S).group(0)
        self.assertRegex(box, r"<td>(Tham dự|Phục vụ tại) (Giờ thờ phượng|Buổi họp|Thăm viếng|Chương trình): ")
        self.assertRegex(box, r"<td>Dâng hiến [0-9.]+ ₫ vào ")
        self.assertIn("<td>Trạng thái: ", box)
        self.assertNotIn("Ghi chú cá nhân:", box)  # the story never holds a Private note

    def test_form_errors_are_vietnamese(self):
        member = self.item("status", "member")
        form = {"full_name": "  ", "status_id": member, "start_date": ago(0)}
        _h, page = self.post("/people/new", form, expect=400)
        self.assertIn('<p class="error" id="f-full_name-error">Cần nhập Họ và tên.</p>', page)
        self.assert_vietnamese(page, "new person, no name")
        tomorrow = (TODAY + dt.timedelta(days=1)).isoformat()
        _h, page = self.post("/people/new", {**form, "full_name": "Lê Văn Bình", "start_date": tomorrow}, expect=400)
        self.assertIn(f'<p class="error" id="f-start_date-error">Ngày bắt đầu không được sau hôm nay '
                      f"({shown(ago(0))}). Hãy dùng hôm nay hoặc một ngày trước đó.</p>", page)
        self.assert_vietnamese(page, "new person, start tomorrow")

        pid, _headers = self.new_person("Lê Văn Cường")
        _h, page = self.post(f"/people/{pid}/status", {"status_id": "abc", "start_date": ago(0)}, expect=400)
        self.assertIn('<p class="error" id="status-id-error">Trạng thái: hãy chọn một mục trong danh sách.</p>', page)
        self.assert_vietnamese(page, "status, bad item")
        fid = self.one("SELECT id FROM family ORDER BY id LIMIT 1")
        self.post(f"/people/{pid}/family", {"family_id": fid, "family_role": "Child", "start_date": ago(0)})
        _h, page = self.post(f"/people/{pid}/family", {"family_id": fid, "family_role": "Head", "start_date": ago(5)},
                             expect=400)
        self.assertIn(f'<p class="error" id="family-date-error">Ngày bắt đầu {shown(ago(5))} sớm hơn {shown(ago(0))}, '
                      "ngày của lần thay đổi gần nhất. Những gì đã qua không bao giờ bị viết lại; hãy dùng ngày "
                      f"{shown(ago(0))} hoặc sau đó.</p>", page)
        self.assert_vietnamese(page, "family, before the last change")
        worship = self.item("ministry", name="Ban Âm nhạc")
        _h, page = self.post(f"/people/{pid}/ministry",
                             {"ministry_id": worship, "ministry_role": "Boss", "start_date": ago(0)}, expect=400)
        self.assertIn('<p class="error" id="ministry-role-error">Vai trò trong ban phải là một trong: Trưởng ban, '
                      "Ban viên.</p>", page)
        self.assert_vietnamese(page, "ministry, bad role")
        _h, page = self.post(f"/people/{pid}/private-notes", {"body": "   "}, expect=400)
        self.assertIn('<p class="error" role="alert">Ghi chú cá nhân cần có nội dung.</p>', page)
        self.assert_vietnamese(page, "private note, no words")

        _h, page = self.post("/families/new", {"name": "", "address": ""}, expect=400)
        self.assertIn('<p class="error" id="f-name-error">Cần nhập Tên Gia đình.</p>', page)
        self.assert_vietnamese(page, "new family, no name")
        name = self.db().execute("SELECT name FROM chi_phai ORDER BY id LIMIT 1").fetchone()[0]
        _h, page = self.post("/chi-phai/new", {"name": name}, expect=400)
        self.assertIn(f'<p class="error" id="f-name-error">Đã có Chi phái &quot;{name}&quot;.</p>', page)
        self.assert_vietnamese(page, "new chi phai, name taken")
        cid = self.one("SELECT id FROM chi_phai ORDER BY id LIMIT 1")
        _h, page = self.post(f"/chi-phai/{cid}/truong", {"person_id": "", "start_date": "31/12/2025"}, expect=400)
        self.assertIn('<p class="error" id="truong-date-error">Ngày bắt đầu phải là một ngày có thật, viết '
                      "YYYY-MM-DD, ví dụ 2026-05-31.</p>", page)
        self.assert_vietnamese(page, "truong, bad date")

    def test_birth_date_year_only_in_vietnamese(self):
        """BY-2: the Birth date hint and its errors in Vietnamese; a year only is saved and shown as 1980."""
        page = self.page("/people/new")
        self.assertIn('<p class="hint" id="f-birth_date-hint">Như 31/12/1980, hoặc chỉ năm: 1980. '
                      "Để trống nếu không biết.</p>", page)
        member = self.item("status", "member")
        form = {"full_name": "Lê Văn Năm Sinh", "birth_date": "1850", "status_id": member, "start_date": ago(0)}
        _h, page = self.post("/people/new", form, expect=400)
        self.assertIn('<p class="error" id="f-birth_date-error">Ngày sinh phải là một ngày có thật như 31/12/1980, '
                      "hoặc một năm từ 1900 như 1980.</p>", page)
        self.assert_vietnamese(page, "new person, birth year before 1900")
        _h, page = self.post("/people/new", {**form, "birth_date": str(TODAY.year + 1)}, expect=400)
        self.assertIn(f'<p class="error" id="f-birth_date-error">Ngày sinh không được sau hôm nay ({shown(ago(0))}). '
                      "Hãy dùng hôm nay hoặc một ngày trước đó.</p>", page)
        headers, _ = self.post("/people/new", {**form, "birth_date": "1980"})
        pid = int(re.fullmatch(r"/people/(\d+)\?msg=.+", headers["location"]).group(1))
        page = self.page(f"/people/{pid}")
        self.assertIn('<dd><span class="num">1980</span></dd>', page)
        self.assert_vietnamese(page, "person page, year only")
        page = self.page(f"/people/{pid}/edit")
        self.assertRegex(page, r'<input [^>]*name="birth_date"[^>]*value="1980"')
        self.assert_vietnamese(page, "edit person, year only")

    def test_flash_messages_are_vietnamese(self):
        pid, headers = self.new_person("Trần Thị Diệu")
        page, message = self.follow(headers)
        self.assertEqual(message, "Đã thêm Người.")
        self.assert_vietnamese(page, "person added")
        member = self.item("status", "member")
        headers, _ = self.post(f"/people/{pid}/status", {"status_id": member, "start_date": ago(0)})
        page, message = self.follow(headers)
        self.assertEqual(message, f"Đã đổi Trạng thái thành Tín hữu từ {shown(ago(0))}.")
        self.assert_vietnamese(page, "status changed")
        headers, _ = self.post(f"/people/{pid}/status", {"status_id": member, "start_date": ago(0)})
        self.assertEqual(self.follow(headers)[1], "Trạng thái đã là Tín hữu. Không có gì thay đổi.")
        fid, fname = self.db().execute("SELECT id, name FROM family ORDER BY id LIMIT 1").fetchone()
        headers, _ = self.post(f"/people/{pid}/family", {"family_id": fid, "family_role": "Child", "start_date": ago(0)})
        self.assertEqual(self.follow(headers)[1], f"Nay ở trong {fname} với vai trò Con từ {shown(ago(0))}.")
        worship = self.item("ministry", name="Ban Âm nhạc")
        headers, _ = self.post(f"/people/{pid}/ministry",
                               {"ministry_id": worship, "ministry_role": "Leader", "start_date": ago(0)})
        self.assertEqual(self.follow(headers)[1], f"Trưởng ban trong Ban Âm nhạc từ {shown(ago(0))}.")
        headers, _ = self.post(f"/people/{pid}/private-notes", {"body": "Lời cầu nguyện riêng"})
        page, message = self.follow(headers)
        self.assertEqual(message, "Đã thêm Ghi chú cá nhân.")
        self.assertNotIn("Lời cầu nguyện riêng", headers["location"])
        headers, _ = self.post(f"/people/{pid}/edit", {"full_name": "Trần Thị Diệu Hiền"})
        self.assertEqual(self.follow(headers)[1], "Đã lưu thông tin.")
        headers, _ = self.post("/chi-phai/new", {"name": "Chi phái Thử Nghiệm"})
        page, message = self.follow(headers)
        self.assertEqual(message, "Đã thêm Chi phái.")
        self.assert_vietnamese(page, "chi phai added")
        cid = int(re.match(r"/chi-phai/(\d+)", headers["location"]).group(1))
        headers, _ = self.post(f"/chi-phai/{cid}/truong", {"person_id": pid, "start_date": ago(0)})
        self.assertEqual(self.follow(headers)[1], f"Trần Thị Diệu Hiền làm Trưởng Chi phái từ {shown(ago(0))}.")
        headers, _ = self.post("/families/new", {"name": "Gia đình Thử Nghiệm", "address": ""})
        page, message = self.follow(headers)
        self.assertEqual(message, "Đã thêm Gia đình.")
        new_fid = int(re.match(r"/families/(\d+)", headers["location"]).group(1))
        headers, _ = self.post(f"/families/{new_fid}/chi-phai", {"chi_phai_id": cid, "start_date": ago(0)})
        self.assertEqual(self.follow(headers)[1], f"Nay ở trong Chi phái Thử Nghiệm từ {shown(ago(0))}.")

    def test_a_name_with_accents_is_shown_as_typed(self):
        pid, headers = self.new_person(ACCENTED)
        page = self.page(f"/people/{pid}")
        self.assertIn(f'<h1 lang="vi">{ACCENTED}</h1>', page)
        self.assertIn(f'<title lang="vi">{ACCENTED} · ', page)
        self.assertIn(f'<span lang="vi">{ACCENTED}</span>', self.page("/people?q=" + urllib.parse.quote("anh tuyet")))
        self.assertIn(f'<h1 lang="vi">Chỉnh sửa {ACCENTED}</h1>', self.page(f"/people/{pid}/edit"))


class BlankVietnameseCopyTest(CopyServer, unittest.TestCase):
    """A new church copy: the lists of this card are empty."""

    PEOPLE = 0

    def test_empty_lists(self):
        for path, sentence in (("/people", "Chưa có Người nào. Hãy thêm Người đầu tiên."),
                               ("/families", "Chưa có Gia đình nào. Hãy thêm Gia đình đầu tiên."),
                               ("/chi-phai", "Chưa có Chi phái nào. Hãy thêm Chi phái đầu tiên.")):
            page = self.page(path)
            self.assertIn(f'<p class="empty">{sentence}</p>', page)
            self.assertEqual(html_lang(page), "vi")
            self.assertNotIn("[[", page)
            self.assertEqual(english_left(page), [], path)
        page = self.page("/people")  # CRIT-3: on screen the count is on the All chip; under the h1 for paper only
        self.assertIn('aria-current="true">Tất cả <span class="num">0</span></a>', page)
        self.assertIn('<p class="sub"><span class="on-paper">0 người</span></p>', page)


class EnglishPagesTest(CopyServer, unittest.TestCase):
    LANG = "en"

    def test_every_page_of_this_card(self):
        for path, status in self.card_pages():
            page = self.page(path, status)
            self.assertEqual(html_lang(page), "en", path)
            self.assertEqual(switch(page)[1:], ("false", "true"), path)
            self.assertNotIn("[[", page, path)
        self.assertIn("<h1>People</h1>", self.page("/people"))
        self.assertIn('<p class="lead">There is no Person with this number.</p>', self.page("/people/999999", 404))
        self.assertIn('<p class="hint" id="f-birth_date-hint">Like 31/12/1980, or the year only: 1980. '
                      "Leave empty if you do not know it.</p>", self.page("/people/new"))

    def test_a_name_with_accents_is_shown_as_typed(self):
        pid, headers = self.new_person(ACCENTED)
        self.assertEqual(self.follow(headers)[1], "Person added.")
        page = self.page(f"/people/{pid}")
        self.assertIn(f'<h1 lang="vi">{ACCENTED}</h1>', page)
        self.assertIn(f'<span lang="vi">{ACCENTED}</span>', self.page("/people?q=" + urllib.parse.quote("anh tuyet")))
        self.assertIn(f'<h1 lang="vi">Edit {ACCENTED}</h1>', self.page(f"/people/{pid}/edit"))


class PeopleErrorsTest(_support.CopyTestCase):
    """``people.py`` refuses with a ``TextError``: ``str()`` is today's English, pages show Vietnamese."""

    def refused(self, fn):
        with self.assertRaises(TextError) as ctx:
            fn()
        return str(ctx.exception), error_text(ctx.exception, "vi")

    def test_english_str_and_vietnamese_text(self):
        conn, member = self.conn, self.status("member")
        pid = people.add_person(conn, "Lê Văn An", status_id=member, start_date="2026-01-10")
        fid = people.add_family(conn, "Gia đình Lê Văn An")
        people.add_chi_phai(conn, "Chi phái Hòa Bình")
        worship = self.item("ministry", name="Worship")
        cases = [
            (lambda: people.add_person(conn, "  "), "Full name is required.", "Cần nhập Họ và tên."),
            (lambda: people.add_person(conn, "A", gender="X"), "Gender must be M or F, or empty.",
             "Giới tính phải là M (Nam) hoặc F (Nữ), hoặc để trống."),
            (lambda: people.add_person(conn, "A", birth_date="31/12/2000"),
             "Birth date must be a real date written YYYY-MM-DD, for example 2026-05-31.",
             "Ngày sinh phải là một ngày có thật, viết YYYY-MM-DD, ví dụ 2026-05-31."),
            (lambda: people.add_family(conn, ""), "Family name is required.", "Cần nhập Tên Gia đình."),
            (lambda: people.add_chi_phai(conn, "Chi phái Hòa Bình"), 'Chi phái "Chi phái Hòa Bình" already exists.',
             'Đã có Chi phái "Chi phái Hòa Bình".'),
            (lambda: people.get_person(conn, "abc"), "Person must be a whole number.", "Người phải là số nguyên."),
            (lambda: people.set_status(conn, 999999, member, "2026-02-01"), "No Person with id 999999.",
             "Không có Người với mã số 999999."),
            (lambda: people.set_status(conn, pid, self.status("attender"), "2026-01-01"),
             "Start date 01/01/2026 is before 10/01/2026, the date of the last change. History is never rewritten; "
             "use a date on or after it.",
             "Ngày bắt đầu 01/01/2026 sớm hơn 10/01/2026, ngày của lần thay đổi gần nhất. Những gì đã qua không bao "
             "giờ bị viết lại; hãy dùng ngày 10/01/2026 hoặc sau đó."),
            (lambda: people.set_family(conn, pid, fid, "Boss", "2026-02-01"),
             "Family role must be one of: Head, Spouse, Child, Other.",
             "Vai trò trong gia đình phải là một trong: Chủ gia đình, Vợ/Chồng, Con, Người thân khác."),
            (lambda: people.set_ministry(conn, pid, worship, "Boss", "2026-02-01"),
             "Ministry role must be one of: Leader, Member.", "Vai trò trong ban phải là một trong: Trưởng ban, Ban viên."),
            (lambda: people.add_private_note(conn, pid, " "), "A private note needs some text.",
             "Ghi chú cá nhân cần có nội dung."),
            (lambda: people.update_private_note(conn, pid, 999999, "x"), "This Person has no Private note with id 999999.",
             "Người này không có Ghi chú cá nhân với mã số 999999."),
            (lambda: people.set_truong_chi_phai(conn, 999999, pid, "2026-02-01"), "No Chi phái with id 999999.",
             "Không có Chi phái với mã số 999999."),
        ]
        for fn, english, vietnamese in cases:
            self.assertEqual(self.refused(fn), (english, vietnamese), english)

    def test_the_role_lists_in_the_english_errors_are_the_schema_lists(self):
        self.assertEqual(TEXT["en"]["people.err_family_role"],
                         f"Family role must be one of: {', '.join(schema.FAMILY_ROLES)}.")
        self.assertEqual(TEXT["en"]["people.err_ministry_role"],
                         f"Ministry role must be one of: {', '.join(schema.MINISTRY_ROLES)}.")
        words = [TEXT["vi"][f"core.family_role_{r.lower()}"] for r in schema.FAMILY_ROLES]
        self.assertIn(", ".join(words), TEXT["vi"]["people.err_family_role"])
        words = [TEXT["vi"][f"core.ministry_role_{r.lower()}"] for r in schema.MINISTRY_ROLES]
        self.assertIn(", ".join(words), TEXT["vi"]["people.err_ministry_role"])


class SharedHelpersTest(unittest.TestCase):
    def use_lang(self, lang):
        self.addCleanup(i18n.set_lang_getter, i18n._lang_getter)
        i18n.set_lang_getter(lambda: lang)

    def test_field_errors_reads_the_english_and_shows_the_page_language(self):
        self.use_lang("vi")
        labels = {"start_date": "people.start_date", "family_role": "people.family_role", "family_id": "people.family",
                  "done_date": "Done date"}
        required = TextError("errors.required", label="people.family_role")
        self.assertEqual(people_pages.field_errors(("f", required), "f", labels),
                         {"family_role": "Cần nhập Vai trò trong gia đình."})
        self.assertEqual(people_pages.field_errors(("f", TextError("people.err_family_role")), "f", labels),
                         {"family_role": TEXT["vi"]["people.err_family_role"]})
        self.assertEqual(people_pages.field_errors(("f", TextError("people.err_no_row", what="people.family", id=9)),
                                                   "f", labels), {"": "Không có Gia đình với mã số 9."})
        self.assertEqual(people_pages.field_errors(("f", ValueError("Done date x")), "f", labels), {"done_date": "Done date x"})
        self.assertEqual(people_pages.field_errors(("f", "Ngày bắt đầu x"), "f", labels), {"start_date": "Ngày bắt đầu x"})
        self.assertEqual(people_pages.field_errors(("g", required), "f", labels), {})

    def test_past_or_today_and_list_choice_keep_their_english(self):
        self.use_lang("vi")
        tomorrow = (TODAY + dt.timedelta(days=1)).isoformat()
        with self.assertRaises(TextError) as ctx:
            people_pages.past_or_today(tomorrow, "people.start_date")
        self.assertEqual(str(ctx.exception), f"Start date cannot be after today ({shown(ago(0))}). "
                                             "Use today or an earlier date.")
        self.assertTrue(error_text(ctx.exception).startswith("Ngày bắt đầu không được sau hôm nay"))
        with self.assertRaises(TextError) as ctx:
            people_pages.past_or_today(tomorrow, "Done date")  # a plain word from an old caller stays as it is
        self.assertTrue(error_text(ctx.exception).startswith("Done date không được sau hôm nay"))
        self.assertEqual(people_pages.same_change("A."), "A. Không có gì thay đổi.")
        self.use_lang("en")
        self.assertEqual(people_pages.same_change("A."), "A. Nothing changed.")
        self.assertEqual(people_pages.period("2026-01-02", None)[1], '<span class="faint">now</span>')

    def test_birth_from_input_keeps_its_english(self):
        """BY-2: a refused Birth date: ``str()`` English, the page shows Vietnamese."""
        self.use_lang("vi")
        with self.assertRaises(TextError) as ctx:
            people_pages.birth_from_input("1850")
        self.assertEqual(str(ctx.exception),
                         "Birth date must be a real date like 31/12/1980, or a year from 1900 like 1980.")
        self.assertEqual(error_text(ctx.exception),
                         "Ngày sinh phải là một ngày có thật như 31/12/1980, hoặc một năm từ 1900 như 1980.")
        with self.assertRaises(TextError) as ctx:
            people_pages.birth_from_input(str(TODAY.year + 1))
        self.assertEqual(str(ctx.exception), f"Birth date cannot be after today ({shown(ago(0))}). "
                                             "Use today or an earlier date.")
        self.assertTrue(error_text(ctx.exception).startswith("Ngày sinh không được sau hôm nay"))


class StoryTest(_support.CopyTestCase):
    LANG = "vi"

    def test_story_lines_in_both_languages(self):
        conn = self.conn
        pid = people.add_person(conn, "Lê Văn An", status_id=self.status("member"), start_date="2020-01-01")
        fid = people.add_family(conn, "Gia đình Lê Văn An")
        people.set_family(conn, pid, fid, "Head", "2020-01-01")
        cid = people.add_chi_phai(conn, "Chi phái Hòa Bình")
        people.set_family_chi_phai(conn, fid, cid, "2020-01-01")
        people.set_truong_chi_phai(conn, cid, pid, "2021-01-01")
        people.set_truong_chi_phai(conn, cid, None, "2022-01-01")
        worship = self.item("ministry", name="Ban Âm nhạc")
        people.set_ministry(conn, pid, worship, "Leader", "2020-01-01")
        people.set_ministry(conn, pid, worship, None, "2023-01-01")
        people.set_family(conn, pid, None, None, "2024-01-01")
        people.add_private_note(conn, pid, "Cầu nguyện riêng")
        vi = [e["text"] for e in story.person_story(conn, pid, lang="vi")]
        self.assertEqual(vi, ["Trạng thái: Tín hữu", "Gia đình: Gia đình Lê Văn An (Chủ gia đình)",
                              "Chi phái: Chi phái Hòa Bình (của Gia đình Lê Văn An)",
                              "Ban ngành: Ban Âm nhạc (Trưởng ban)", "Trưởng Chi phái: Chi phái Hòa Bình",
                              "Thôi làm Trưởng Chi phái: Chi phái Hòa Bình",
                              "Thôi phục vụ trong Ban Âm nhạc", "Rời Gia đình Lê Văn An"])
        en = [e["text"] for e in story.person_story(conn, pid)]  # the Hermes door: English, as before
        self.assertEqual(en, ["Status: Tín hữu", "Family: Gia đình Lê Văn An (Head)",
                              "Chi phái: Chi phái Hòa Bình (Gia đình Lê Văn An)",
                              "Ministry: Ban Âm nhạc (Leader)", "Trưởng Chi phái: Chi phái Hòa Bình",
                              "No longer Trưởng Chi phái: Chi phái Hòa Bình", "Stopped serving in Ban Âm nhạc",
                              "Left Gia đình Lê Văn An"])
        private = story.person_story(conn, pid, include_private=True, lang="vi")
        self.assertEqual([e["text"] for e in private if e["kind"] == "private_note"],
                         ["Ghi chú cá nhân: Cầu nguyện riêng"])
        with self.assertRaises(TextError) as ctx:
            story.person_story(conn, 999999, lang="vi")
        self.assertEqual((str(ctx.exception), error_text(ctx.exception, "vi")),
                         ("No Person with id 999999.", "Không có Người với mã số 999999."))


if __name__ == "__main__":
    unittest.main()
