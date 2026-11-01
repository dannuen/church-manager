"""Card C1: People, Families and Chi phái pages through the real server.

Each class runs one server on 127.0.0.1 with a free port (port 0) over a fake church in a temp
folder. Every request sends the Host header, and every POST sends the Origin header
(``test_server.LiveServer.request``).
"""

import datetime as dt
import pathlib
import re
import tempfile
import unicodedata
import unittest
import urllib.parse
from html.parser import HTMLParser

import _support  # noqa: F401 - puts the repo root on sys.path
from churchmgr import db, fake, lists, people, story
from churchmgr.pages import people as people_pages
from test_server import LiveServer, parse_panels

ROOT = pathlib.Path(_support.ROOT)
TODAY = dt.date.today()
PRIVATE_LABEL = "Private note — only you see this"
# HTML elements that never have an end tag (only the ones a page here can hold).
VOID = {"br", "hr", "img", "input", "link", "meta", "source", "wbr", "col"}


def ago(days):
    return (TODAY - dt.timedelta(days=days)).isoformat()


def shown(iso):
    """``2026-11-01`` -> ``01/11/2026`` (how the pages show a date)."""
    return dt.date.fromisoformat(iso).strftime("%d/%m/%Y")


def section(page, name):
    """The inner HTML of ``<section ... data-panel="name">`` (panels are never nested)."""
    m = re.search(rf'<section [^>]*data-panel="{re.escape(name)}"[^>]*>(.*?)</section>', page, re.S)
    assert m is not None, f"no panel {name!r}"
    return m.group(1)


class TextPlaces(HTMLParser):
    """For each text piece that holds ``needle``: is it inside an element with class ``no-print``?"""

    def __init__(self, needle):
        super().__init__(convert_charrefs=True)
        self.needle, self.stack, self.inside = needle, [], []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append((tag, "no-print" in (dict(attrs).get("class") or "").split()))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if self.needle in data:
            self.inside.append(any(flag for _tag, flag in self.stack))


def places(page, needle):
    p = TextPlaces(needle)
    p.feed(page)
    return p.inside


class PagesTestBase(LiveServer, unittest.TestCase):
    """One fake church and one live server per test class."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        cls.root = pathlib.Path(cls.tmp.name)
        assert "onedrive" not in str(cls.root.resolve()).lower()
        cls.copy = cls.root / "fake"
        fake.build_fake_church(cls.copy)
        cls.start(cls.copy, cls.root, remember=False)

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.tmp.cleanup()

    def db(self):
        conn = db.connect(self.copy / db.DB_NAME)
        self.addCleanup(conn.close)
        return conn

    def item(self, list_name, code=None, name=None):
        return lists.find_item(self.db(), list_name, code=code, name=name)["id"]

    def post(self, path, form, expect=303):
        status, headers, data = self.request("POST", path, form)
        self.assertEqual(status, expect, data.decode("utf-8")[:2000])
        return headers, data.decode("utf-8")

    def page(self, path, expect=200):
        status, _h, text_ = self.get_text(path)
        self.assertEqual(status, expect, path)
        return text_

    def new_person(self, name, status_code="visitor", start=None, **extra):
        form = {"full_name": name, "gender": "", "birth_date": "", "phone": "", "address": "", "note": "",
                "status_id": self.item("status", code=status_code), "start_date": start or ago(0), **extra}
        headers, _ = self.post("/people/new", form)
        m = re.fullmatch(r"/people/(\d+)\?msg=.+", headers["location"])
        self.assertIsNotNone(m, headers["location"])
        return int(m.group(1))


class PeoplePagesTest(PagesTestBase):
    def test_add_person_with_nfd_name_is_stored_nfc_and_found(self):
        nfc = "Lê Thị Hồng Nhung"
        nfd = unicodedata.normalize("NFD", nfc)
        self.assertNotEqual(nfd, nfc)
        pid = self.new_person(nfd, start=ago(3), gender="F", birth_date="1990-05-12", phone="0903 123 456",
                              address="12 Lê Lợi, Phường 1", note="Mới đến từ Đà Lạt")
        row = people.get_person(self.db(), pid)
        self.assertEqual(row["full_name"], nfc)
        self.assertEqual(row["name_folded"], "le thi hong nhung")
        self.assertEqual((row["gender"], row["birth_date"], row["phone"]), ("F", "1990-05-12", "0903 123 456"))
        # found by the quick search on /people, with or without accents, NFC or NFD
        for q in ("le thi hong nhung", "Hồng Nhung", unicodedata.normalize("NFD", "Hồng Nhung")):
            page = self.page("/people?q=" + urllib.parse.quote(q))
            self.assertIn(f'href="/people/{pid}"', page, q)
            self.assertIn(nfc, page, q)
        self.assertIn(f'href="/people/{pid}"', self.page("/search?q=nhung+hong"))
        # the Person page: one h1, the name in NFC, the first Status with its date
        page = self.page(f"/people/{pid}")
        self.assertEqual(parse_panels(page).h1, 1)
        self.assertIn(f'<h1 lang="vi">{nfc}</h1>', page)
        self.assertNotIn(nfd, page)
        status_html = section(page, "status")
        self.assertIn("Visitor", status_html)
        self.assertIn(shown(ago(3)), status_html)

    def test_status_changed_twice_shows_three_rows_with_dates(self):
        pid = self.new_person("Trần Văn Ba Lần", "visitor", start=ago(300))
        self.post(f"/people/{pid}/status", {"status_id": self.item("status", code="attender"), "start_date": ago(200)})
        self.post(f"/people/{pid}/status", {"status_id": self.item("status", code="member"), "start_date": ago(100)})
        page = self.page(f"/people/{pid}")
        status_html = section(page, "status")
        self.assertEqual(parse_panels(page).rows["status"], 3)
        for name in ("Visitor", "Attender", "Member"):
            self.assertIn(f"<td>{name}</td>", status_html)
        for day in (ago(300), ago(200), ago(100)):
            self.assertIn(shown(day), status_html)
        self.assertIn(">now<", status_html)
        history = people.status_history(self.db(), pid)
        self.assertEqual([(r["code"], r["start_date"], r["end_date"]) for r in history],
                         [("visitor", ago(300), ago(200)), ("attender", ago(200), ago(100)), ("member", ago(100), None)])
        # the same Status again changes nothing and says so
        headers, _ = self.post(f"/people/{pid}/status", {"status_id": self.item("status", code="member"),
                                                         "start_date": ago(0)})
        self.assertIn("Nothing+changed", headers["location"])
        self.assertEqual(len(people.status_history(self.db(), pid)), 3)

    def test_dates_after_today_and_before_the_last_change_are_refused(self):
        tomorrow = (TODAY + dt.timedelta(days=1)).isoformat()
        pid = self.new_person("Phạm Thị Ngày Mai", "visitor", start=ago(10))
        _h, page = self.post(f"/people/{pid}/status", {"status_id": self.item("status", code="left"),
                                                       "start_date": tomorrow}, expect=400)
        self.assertIn("Start date cannot be after today", page)
        self.assertIn('id="status-date-error"', page)  # the sentence sits next to the date field
        self.assertIn("<details class=\"change\" open>", page)
        _h, page = self.post(f"/people/{pid}/status", {"status_id": self.item("status", code="member"),
                                                       "start_date": ago(20)}, expect=400)
        self.assertIn("History is never rewritten", page)
        self.assertEqual(len(people.status_history(self.db(), pid)), 1)
        # Family, Ministry, Chi phái and Trưởng Chi phái forms refuse a future date too
        conn = self.db()
        fam = people.list_families(conn)[0]["id"]
        ministry = self.item("ministry", name="Worship")
        cid = people.list_chi_phai(conn)[0]["id"]
        for path, form in ((f"/people/{pid}/family", {"family_id": fam, "family_role": "Other"}),
                           (f"/people/{pid}/ministry", {"ministry_id": ministry, "ministry_role": "Member"}),
                           (f"/families/{fam}/chi-phai", {"chi_phai_id": cid}),
                           (f"/chi-phai/{cid}/truong", {"person_id": pid})):
            _h, page = self.post(path, {**form, "start_date": tomorrow}, expect=400)
            self.assertIn("Start date cannot be after today", page, path)
        self.assertIsNone(people.current_family(conn, pid))
        self.assertEqual(people.current_ministries(conn, pid), [])
        self.assertNotEqual(people.current_truong_chi_phai(conn, cid)["person_id"], pid)
        # a new Person with a future first Status is not added at all
        before = len(people.list_persons(conn))
        self.post("/people/new", {"full_name": "Võ Văn Tương Lai", "status_id": self.item("status", code="member"),
                                  "start_date": tomorrow}, expect=400)
        self.assertEqual(len(people.list_persons(conn)), before)

    def test_move_person_to_another_family_keeps_the_old_link(self):
        conn = self.db()
        families = people.list_families(conn)
        old, new = families[0], families[1]
        mover = people.family_members(conn, old["id"])[-1]
        pid = mover["id"]
        self.post(f"/people/{pid}/family", {"family_id": new["id"], "family_role": "Other", "start_date": ago(1)})
        rows = people.family_history(conn, pid)
        old_row = next(r for r in rows if r["family_id"] == old["id"])
        self.assertEqual(old_row["end_date"], ago(1))
        self.assertEqual(people.current_family(conn, pid)["family_id"], new["id"])
        page = self.page(f"/people/{pid}")
        fam_html = section(page, "family")
        self.assertIn(old["name"], fam_html)
        self.assertIn(new["name"], fam_html)
        self.assertGreaterEqual(fam_html.count(shown(ago(1))), 2)  # the old link's To, the new link's From
        old_page = self.page(f"/families/{old['id']}")
        self.assertIn(f'href="/people/{pid}"', section(old_page, "people-before"))
        self.assertIn(shown(ago(1)), section(old_page, "people-before"))
        self.assertNotIn(f'href="/people/{pid}"', section(old_page, "people-now"))
        self.assertIn(f'href="/people/{pid}"', section(self.page(f"/families/{new['id']}"), "people-now"))
        # leaving the Family keeps every link
        self.post(f"/people/{pid}/family", {"family_id": "", "family_role": "Other", "start_date": ago(0)})
        self.assertIsNone(people.current_family(conn, pid))
        self.assertEqual(len(people.family_history(conn, pid)), len(rows))

    def test_truong_chi_phai_set_twice_both_are_shown(self):
        conn = self.db()
        cid = people.list_chi_phai(conn)[1]["id"]
        first = self.new_person("Hoàng Văn Trưởng Một", "member", start=ago(400))
        second = self.new_person("Đặng Thị Trưởng Hai", "member", start=ago(400))
        self.post(f"/chi-phai/{cid}/truong", {"person_id": first, "start_date": ago(20)})
        self.post(f"/chi-phai/{cid}/truong", {"person_id": second, "start_date": ago(10)})
        history = people.truong_chi_phai_history(conn, cid)
        self.assertEqual([(r["person_id"], r["start_date"], r["end_date"]) for r in history[-2:]],
                         [(first, ago(20), ago(10)), (second, ago(10), None)])
        page = self.page(f"/chi-phai/{cid}")
        truong = section(page, "truong-chi-phai")
        for name, day in (("Hoàng Văn Trưởng Một", ago(20)), ("Đặng Thị Trưởng Hai", ago(10))):
            self.assertIn(name, truong)
            self.assertIn(shown(day), truong)
        self.assertEqual(parse_panels(page).rows["truong-chi-phai"], len(history))
        self.assertIn("Trưởng Chi phái Đặng Thị Trưởng Hai", page)  # the finding line under the h1

    def test_private_note_only_on_the_person_page_inside_no_print(self):
        pid = self.new_person("Lý Thị Riêng Tư", "member", start=ago(50))
        note = "C1-PRIVATE-Cầu nguyện cho hôn nhân"
        self.post(f"/people/{pid}/private-notes", {"body": note})
        page = self.page(f"/people/{pid}")
        box = re.search(r'<section class="panel private no-print"[^>]*>(.*?)</section>', page, re.S)
        self.assertIsNotNone(box)
        self.assertIn(f">{PRIVATE_LABEL}</h2>", box.group(1))
        self.assertIn(note, box.group(1))
        self.assertEqual(places(page, note), [True])  # once, and inside .no-print
        self.assertNotIn(note, section(page, "story"))
        self.assertIn(".no-print", (ROOT / "web" / "print.css").read_text(encoding="utf-8"))
        # never on the lists or other pages (the fake church's Private notes neither)
        conn = self.db()
        fam = people.list_families(conn)[0]["id"]
        cid = people.list_chi_phai(conn)[0]["id"]
        for path in ("/people", "/people?q=rieng+tu", f"/families/{fam}", f"/chi-phai/{cid}", "/families",
                     "/chi-phai", "/care", "/search?q=rieng", "/", f"/people/{pid}/edit"):
            other = self.page(path)
            self.assertNotIn(note, other, path)
            self.assertNotIn(fake.MARKER, other, path)
        # the fake church's first Person has a Private note: only in the box on their own page
        first = people.list_persons(conn)
        first_id = next(r["id"] for r in first if r["full_name"] == fake.FIRST_PERSON)
        first_page = self.page(f"/people/{first_id}")
        self.assertTrue(places(first_page, fake.MARKER))
        self.assertTrue(all(places(first_page, fake.MARKER)))

    def test_ministry_add_and_end(self):
        pid = self.new_person("Bùi Văn Phục Vụ", "member", start=ago(60))
        youth = self.item("ministry", name="Youth")
        self.post(f"/people/{pid}/ministry", {"ministry_id": youth, "ministry_role": "Member", "start_date": ago(30)})
        self.post(f"/people/{pid}/ministry", {"ministry_id": youth, "ministry_role": "Leader", "start_date": ago(20)})
        self.post(f"/people/{pid}/ministry", {"ministry_id": youth, "ministry_role": "", "start_date": ago(10)})
        rows = people.ministry_history(self.db(), pid)
        self.assertEqual([(r["ministry_role"], r["start_date"], r["end_date"]) for r in rows],
                         [("Member", ago(30), ago(20)), ("Leader", ago(20), ago(10))])
        page = self.page(f"/people/{pid}")
        self.assertEqual(parse_panels(page).rows["ministries"], 2)
        self.assertIn("Not serving now", section(page, "ministries"))

    def test_edit_person_plain_fields(self):
        pid = self.new_person("Ngô Văn Cũ", "member", start=ago(5))
        self.assertIn('value="Ngô Văn Cũ"', self.page(f"/people/{pid}/edit"))
        self.post(f"/people/{pid}/edit", {"full_name": unicodedata.normalize("NFD", "Ngô Văn Mới"), "gender": "M",
                                          "birth_date": "1980-01-02", "phone": "0909", "address": "5 Hai Bà Trưng",
                                          "note": "Đã đổi tên"})
        row = people.get_person(self.db(), pid)
        self.assertEqual((row["full_name"], row["name_folded"], row["gender"], row["birth_date"]),
                         ("Ngô Văn Mới", "ngo van moi", "M", "1980-01-02"))
        _h, page = self.post(f"/people/{pid}/edit", {"full_name": "  "}, expect=400)
        self.assertIn("Full name is required", page)
        self.assertIn('id="f-full_name-error"', page)

    def test_full_name_at_most_120_characters(self):
        """B3: a Full name of 120 characters is saved; 121 is refused next to the field (add and edit)."""
        long_name = "Trần Thị B3 " + "Hồng" * 27
        self.assertEqual(len(long_name), 120)
        pid = self.new_person(long_name)
        self.assertEqual(people.get_person(self.db(), pid)["full_name"], long_name)
        sentence = '<p class="error" id="f-full_name-error">Full name: use at most 120 characters.</p>'
        form = {"full_name": long_name + "x", "gender": "", "birth_date": "", "phone": "", "address": "", "note": "",
                "status_id": self.item("status", code="visitor"), "start_date": ago(0)}
        _h, page = self.post("/people/new", form, expect=400)
        self.assertIn(sentence, page)
        self.assertEqual([p for p in people.list_persons(self.db()) if p["full_name"].startswith(long_name)][0]["id"],
                         pid)  # the 121 one was not added
        _h, page = self.post(f"/people/{pid}/edit", {"full_name": long_name + "x"}, expect=400)
        self.assertIn(sentence, page)
        self.assertEqual(people.get_person(self.db(), pid)["full_name"], long_name)
        self.post(f"/people/{pid}/edit", {"full_name": "Trần Thị B3 Ngắn"})
        self.post(f"/people/{pid}/edit", {"full_name": long_name})  # 120 is saved on edit too
        self.assertEqual(people.get_person(self.db(), pid)["full_name"], long_name)

    def test_families_and_chi_phai_forms(self):
        headers, _ = self.post("/families/new", {"name": "Gia đình Thử Nghiệm", "address": "9 Nguyễn Trãi"})
        fid = int(re.fullmatch(r"/families/(\d+)\?msg=.+", headers["location"]).group(1))
        headers, _ = self.post("/chi-phai/new", {"name": "Chi phái Thử Nghiệm"})
        cid = int(re.fullmatch(r"/chi-phai/(\d+)\?msg=.+", headers["location"]).group(1))
        _h, page = self.post("/chi-phai/new", {"name": "Chi phái Thử Nghiệm"}, expect=400)
        self.assertIn("already exists", page)
        other = people.list_chi_phai(self.db())[0]["id"]
        self.post(f"/families/{fid}/chi-phai", {"chi_phai_id": cid, "start_date": ago(30)})
        self.post(f"/families/{fid}/chi-phai", {"chi_phai_id": other, "start_date": ago(5)})
        page = self.page(f"/families/{fid}")
        cp = section(page, "chi-phai")
        self.assertIn("Chi phái Thử Nghiệm", cp)
        self.assertIn(shown(ago(30)), cp)
        self.assertIn(shown(ago(5)), cp)
        self.assertIn("9 Nguyễn Trãi", section(page, "address"))
        self.assertIn(f"/money/statement?family_id={fid}&amp;year={TODAY.year}", page)
        cp_page = self.page(f"/chi-phai/{cid}")
        self.assertIn(f'href="/families/{fid}"', section(cp_page, "families-before"))
        self.assertNotIn(f'href="/families/{fid}"', section(cp_page, "families-now"))
        self.assertIn(f'href="/families/{fid}"', section(self.page(f"/chi-phai/{other}"), "families-now"))

    def test_list_pages_filter_and_not_found(self):
        conn = self.db()
        everyone = people.list_persons(conn)
        page = self.page("/people")
        self.assertEqual(parse_panels(page).rows["people"], len(everyone))
        self.assertEqual(parse_panels(page).h1, 1)
        member = self.item("status", code="member")
        page = self.page(f"/people?status={member}")
        members = [r for r in everyone if r["status_id"] == member]
        self.assertEqual(parse_panels(page).rows["people"], len(members))
        self.assertIn(f"{len(members)} of {len(everyone)} People", page)
        self.assertIn("No Person matches", self.page("/people?q=zzzz-nobody"))
        self.assertEqual(parse_panels(self.page("/families")).rows["families"], len(people.list_families(conn)))
        self.assertEqual(parse_panels(self.page("/chi-phai")).rows["chi-phai-list"], len(people.list_chi_phai(conn)))
        new_page = self.page("/people/new")
        self.assertIn(f'type="date" value="{TODAY.isoformat()}"', new_page)  # date fields default to today
        self.assertIn(f'max="{TODAY.isoformat()}"', new_page)
        self.page("/families/new")
        self.page("/chi-phai/new")
        for path in ("/people/999999", "/families/999999", "/chi-phai/999999", "/people/999999/edit"):
            self.assertIn("not found", self.page(path, expect=404))
        first = everyone[0]["id"]
        self.assertIn(f"/money/statement?person_id={first}&amp;year={TODAY.year}", self.page(f"/people/{first}"))

    def test_values_are_escaped(self):
        people.add_person(self.db(), "<script>x</script> Thoát Ký Tự")
        page = self.page("/people?q=thoat+ky+tu")
        self.assertIn("&lt;script&gt;x&lt;/script&gt; Thoát Ký Tự", page)
        self.assertNotIn("<script>x</script>", page)

    def test_story_never_holds_private_note_text(self):
        pid = self.new_person("Đỗ Thị Câu Chuyện", "member", start=ago(40))
        note = "C1B-PRIVATE-Xin cầu nguyện cho con trai"
        self.post(f"/people/{pid}/private-notes", {"body": note})
        page = self.page(f"/people/{pid}")
        story_html = section(page, "story")
        self.assertNotIn(note, story_html)
        self.assertNotIn("Private note", story_html)
        # the story lists exactly what the data layer gives without Private notes
        self.assertEqual(parse_panels(page).rows["story"], len(story.person_story(self.db(), pid)))
        # the on-screen Private note box still shows the note
        box = re.search(r'<section class="panel private no-print"[^>]*>(.*?)</section>', page, re.S)
        self.assertIsNotNone(box)
        self.assertIn(note, box.group(1))
        # the fake church's first Person has a Private note too: not in the story
        first_id = next(r["id"] for r in people.list_persons(self.db()) if r["full_name"] == fake.FIRST_PERSON)
        first_page = self.page(f"/people/{first_id}")
        self.assertNotIn(fake.MARKER, section(first_page, "story"))
        self.assertIn(fake.MARKER, first_page)  # in its box

    def test_refused_status_and_ministry_say_the_glossary_word(self):
        pid = self.new_person("Mai Văn Từ Chối", "member", start=ago(40))
        ministry = self.item("ministry", name="Worship")
        member = self.item("status", code="member")
        # a Status that is not a whole number: the sentence says Status (not Item), next to the Status field
        _h, page = self.post(f"/people/{pid}/status", {"status_id": "abc", "start_date": ago(0)}, expect=400)
        self.assertIn('<p class="error" id="status-id-error">Status must be one of the choices in the list.</p>',
                      page)
        # a Ministry id from another list
        _h, page = self.post(f"/people/{pid}/ministry", {"ministry_id": member, "ministry_role": "Member",
                                                         "start_date": ago(0)}, expect=400)
        self.assertIn('<p class="error" id="ministry-id-error">Ministry must be one of the choices in the list.</p>',
                      page)
        # a wrong Ministry role still goes next to the Ministry role field, not the Ministry field
        _h, page = self.post(f"/people/{pid}/ministry", {"ministry_id": ministry, "ministry_role": "Boss",
                                                         "start_date": ago(0)}, expect=400)
        self.assertIn('id="ministry-role-error"', page)
        self.assertNotIn('id="ministry-id-error"', page)
        # a new Person with a Ministry id as first Status is not added
        conn = self.db()
        before = len(people.list_persons(conn))
        _h, page = self.post("/people/new", {"full_name": "Lâm Văn Sai Danh Sách", "status_id": ministry,
                                             "start_date": ago(0)}, expect=400)
        self.assertIn('<p class="error" id="f-status_id-error">Status must be one of the choices in the list.</p>',
                      page)
        self.assertEqual(len(people.list_persons(conn)), before)
        self.assertEqual(len(people.status_history(conn, pid)), 1)
        self.assertEqual(people.current_ministries(conn, pid), [])

    def test_vietnamese_names_in_the_h1_have_lang_vi(self):
        conn = self.db()
        pid = people.list_persons(conn)[0]["id"]
        fid = people.list_families(conn)[0]["id"]
        cid = people.list_chi_phai(conn)[0]["id"]
        iid = conn.execute("SELECT id FROM calendar_item ORDER BY id LIMIT 1").fetchone()[0]
        for path in (f"/people/{pid}", f"/people/{pid}/edit", f"/families/{fid}", f"/families/{fid}/edit",
                     f"/chi-phai/{cid}", f"/chi-phai/{cid}/edit", f"/calendar/{iid}"):
            self.assertEqual(len(re.findall(r'<h1 lang="vi">', self.page(path))), 1, path)
        for path in ("/", "/people", "/families", "/chi-phai", "/calendar", "/money"):
            self.assertIn("<h1>", self.page(path), path)  # English page names keep the page language


class SmallLogicTest(unittest.TestCase):
    def test_past_or_today(self):
        today = TODAY.isoformat()
        self.assertEqual(people_pages.past_or_today(today, "Start date"), today)
        self.assertEqual(people_pages.past_or_today("2020-02-29", "Start date"), "2020-02-29")
        for bad in ((TODAY + dt.timedelta(days=1)).isoformat(), "", None, "2020-02-30", "01/11/2026"):
            with self.assertRaises(ValueError) as ctx:
                people_pages.past_or_today(bad, "Done date")
            self.assertTrue(str(ctx.exception).startswith("Done date"), bad)

    def test_field_errors(self):
        labels = {"start_date": "Start date", "family_role": "Family role", "family_id": "Family"}
        self.assertEqual(people_pages.field_errors(None, "family", labels), {})
        self.assertEqual(people_pages.field_errors(("status", "Start date x"), "family", labels), {})
        self.assertEqual(people_pages.field_errors(("family", "Start date x"), "family", labels),
                         {"start_date": "Start date x"})
        self.assertEqual(people_pages.field_errors(("family", "Family role must be"), "family", labels),
                         {"family_role": "Family role must be"})
        self.assertEqual(people_pages.field_errors(("family", "No Family with id 9."), "family", labels),
                         {"": "No Family with id 9."})

    def test_pages_never_write_history_tables_with_sql(self):
        tables = "person_status|family_link|chi_phai_link|truong_chi_phai|ministry_link"
        for name in ("people.py", "families.py", "chi_phai.py", "care.py"):
            source = (ROOT / "churchmgr" / "pages" / name).read_text(encoding="utf-8")
            self.assertIsNone(re.search(rf"\b(UPDATE|INSERT\s+INTO|DELETE\s+FROM)\s+({tables})\b", source, re.I), name)
            self.assertNotRegex(source, r"\bUPDATE\s+\w+\s+SET\b", name)  # the C1 pages only read with SQL

    def test_no_page_asks_the_story_for_private_notes(self):
        """The story is printed. A page that asked for Private notes and filtered them out again
        would leak any new private kind added later."""
        for path in sorted((ROOT / "churchmgr" / "pages").glob("*.py")):
            self.assertNotIn("include_private", path.read_text(encoding="utf-8"), path.name)

    def test_list_choice(self):
        conn = db.create_church_copy(pathlib.Path(_support.temp_folder(self)) / "copy", "Hội Thánh Thử")
        self.addCleanup(conn.close)
        worship = lists.find_item(conn, "ministry", name="Worship")
        self.assertEqual(people_pages.list_choice(conn, str(worship["id"]), "ministry", "Ministry")["id"],
                         worship["id"])
        lists.set_active(conn, worship["id"], False)  # a hidden item is still a choice of its list
        self.assertEqual(people_pages.list_choice(conn, worship["id"], "ministry", "Ministry")["id"], worship["id"])
        for bad in ("", None, "abc", "0", "-3", "999999", str(lists.find_item(conn, "status", code="member")["id"])):
            with self.assertRaises(ValueError) as ctx:
                people_pages.list_choice(conn, bad, "ministry", "Ministry")
            self.assertEqual(str(ctx.exception), "Ministry must be one of the choices in the list.", bad)


class FamilyAndChiPhaiEditTest(PagesTestBase):
    """The Family name and Address, and a Chi phái's name: plain fields changed in place, not history."""

    def new_family(self, name, address=""):
        headers, _ = self.post("/families/new", {"name": name, "address": address})
        m = re.fullmatch(r"/families/(\d+)\?msg=.+", headers["location"])
        self.assertIsNotNone(m, headers["location"])
        return int(m.group(1))

    def new_chi_phai(self, name):
        headers, _ = self.post("/chi-phai/new", {"name": name})
        m = re.fullmatch(r"/chi-phai/(\d+)\?msg=.+", headers["location"])
        self.assertIsNotNone(m, headers["location"])
        return int(m.group(1))

    def test_edit_family_name_and_address(self):
        fid = self.new_family("Gia đình Trần Văn Cũ", "12 Lê Lợi")
        pid = self.new_person("Trần Văn Dời Nhà", start=ago(30))
        self.post(f"/people/{pid}/family", {"family_id": fid, "family_role": "Head", "start_date": ago(20)})
        links_before = [tuple(r) for r in people.family_history(self.db(), pid)]
        page = self.page(f"/families/{fid}")
        self.assertIn(f'href="/families/{fid}/edit"', page)                         # Edit Family
        self.assertEqual(page.count(f'href="/families/{fid}/edit"'), 1)              # only that one (FIX-T B7)
        form = self.page(f"/families/{fid}/edit")
        self.assertEqual(parse_panels(form).h1, 1)
        self.assertIn('value="Gia đình Trần Văn Cũ"', form)
        self.assertIn(">12 Lê Lợi</textarea>", form)

        headers, _ = self.post(f"/families/{fid}/edit", {"name": "Gia đình Trần Văn Mới",
                                                        "address": "45 Hai Bà Trưng, Phường 3"})
        self.assertTrue(headers["location"].startswith(f"/families/{fid}?msg="), headers["location"])
        row = people.get_family(self.db(), fid)
        self.assertEqual((row["name"], row["address"]), ("Gia đình Trần Văn Mới", "45 Hai Bà Trưng, Phường 3"))
        page = self.page(headers["location"])
        self.assertIn('<h1 lang="vi">Gia đình Trần Văn Mới</h1>', page)
        self.assertIn("45 Hai Bà Trưng, Phường 3", section(page, "address"))
        self.assertIn("Family name and Address saved.", page)
        self.assertIn("Gia đình Trần Văn Mới", self.page("/families"))
        # every Person in it now shows the new address; the Family link history is not touched
        self.assertIn("45 Hai Bà Trưng, Phường 3", section(self.page(f"/people/{pid}"), "details"))
        self.assertEqual([tuple(r)[:2] + tuple(r)[3:] for r in people.family_history(self.db(), pid)],
                         [r[:2] + r[3:] for r in links_before])  # all but the Family name column

    def test_edit_family_refusals(self):
        fid = self.new_family("Gia đình Không Đổi", "1 Nguyễn Huệ")
        _h, page = self.post(f"/families/{fid}/edit", {"name": "  ", "address": "9 Pasteur"}, expect=400)
        self.assertIn('id="f-name-error"', page)  # one sentence next to the Family name field
        self.assertIn("Family name is required.", page)
        self.assertIn(">9 Pasteur</textarea>", page)  # the form keeps what was typed
        status, _h, _d = self.request("POST", f"/families/{fid}/edit", {"name": "Gia đình Lạ", "address": ""},
                                      origin=False)
        self.assertEqual(status, 403)
        row = people.get_family(self.db(), fid)
        self.assertEqual((row["name"], row["address"]), ("Gia đình Không Đổi", "1 Nguyễn Huệ"))
        self.page("/families/999999/edit", expect=404)
        self.post("/families/999999/edit", {"name": "Gia đình Lạ"}, expect=404)

    def test_family_and_chi_phai_name_at_most_120_characters(self):
        """B3: a Family name of 120 characters is saved; 121 is refused next to the field (add and edit)."""
        long_name = "Gia đình B3 " + "Lê" * 54
        self.assertEqual(len(long_name), 120)
        fid = self.new_family(long_name)
        self.assertEqual(people.get_family(self.db(), fid)["name"], long_name)
        sentence = '<p class="error" id="f-name-error">Family name: use at most 120 characters.</p>'
        _h, page = self.post("/families/new", {"name": long_name + "x", "address": ""}, expect=400)
        self.assertIn(sentence, page)
        _h, page = self.post(f"/families/{fid}/edit", {"name": long_name + "x", "address": ""}, expect=400)
        self.assertIn(sentence, page)
        self.assertEqual(people.get_family(self.db(), fid)["name"], long_name)
        _h, page = self.post("/chi-phai/new", {"name": "Chi phái " + "x" * 112}, expect=400)
        self.assertIn("Chi phái name: use at most 120 characters.", page)

    def test_rename_chi_phai(self):
        cid = self.new_chi_phai("Chi phái Thử Tênn")
        fid = self.new_family("Gia đình Trong Chi Phái")
        self.post(f"/families/{fid}/chi-phai", {"chi_phai_id": cid, "start_date": ago(5)})
        links_before = [(r["id"], r["chi_phai_id"], r["start_date"], r["end_date"])
                        for r in people.family_chi_phai_history(self.db(), fid)]
        self.assertIn(f'href="/chi-phai/{cid}/edit"', self.page(f"/chi-phai/{cid}"))  # Rename Chi phái
        form = self.page(f"/chi-phai/{cid}/edit")
        self.assertEqual(parse_panels(form).h1, 1)
        self.assertIn('value="Chi phái Thử Tênn"', form)

        headers, _ = self.post(f"/chi-phai/{cid}/edit", {"name": "Chi phái Thử Tên"})
        self.assertTrue(headers["location"].startswith(f"/chi-phai/{cid}?msg="), headers["location"])
        page = self.page(headers["location"])
        self.assertIn('<h1 lang="vi">Chi phái Thử Tên</h1>', page)
        self.assertIn("Renamed to Chi phái Thử Tên.", page)
        self.assertIn("Chi phái Thử Tên", self.page("/chi-phai"))
        self.assertNotIn("Thử Tênn", self.page("/chi-phai"))
        self.assertIn("Chi phái Thử Tên", section(self.page(f"/families/{fid}"), "chi-phai"))
        self.assertEqual([(r["id"], r["chi_phai_id"], r["start_date"], r["end_date"])
                          for r in people.family_chi_phai_history(self.db(), fid)], links_before)
        # the same name again changes nothing and says so
        headers, _ = self.post(f"/chi-phai/{cid}/edit", {"name": "Chi phái Thử Tên"})
        self.assertIn("Nothing+changed", headers["location"])

    def test_rename_chi_phai_refusals(self):
        cid = self.new_chi_phai("Chi phái Bình An")
        self.new_chi_phai("Chi phái Tân Phú")
        _h, page = self.post(f"/chi-phai/{cid}/edit", {"name": ""}, expect=400)
        self.assertIn('id="f-name-error"', page)
        self.assertIn("Chi phái name is required.", page)
        _h, page = self.post(f"/chi-phai/{cid}/edit", {"name": "Chi phái Tân Phú"}, expect=400)
        self.assertIn('id="f-name-error"', page)
        self.assertIn("already exists", page)
        self.assertIn('value="Chi phái Tân Phú"', page)  # the form keeps what was typed
        status, _h, _d = self.request("POST", f"/chi-phai/{cid}/edit", {"name": "Chi phái Lạ"}, origin=False)
        self.assertEqual(status, 403)
        self.assertEqual(people.get_chi_phai(self.db(), cid)["name"], "Chi phái Bình An")
        self.page("/chi-phai/999999/edit", expect=404)
        self.post("/chi-phai/999999/edit", {"name": "Chi phái Lạ"}, expect=404)


if __name__ == "__main__":
    unittest.main()
