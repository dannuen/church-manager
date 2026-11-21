"""Card RO-4 (decision D6): the Service roles panel of a Service page, through the real server (port 0, a
fake church in a temp folder): pick, swap and clear a Service role with its history kept (rule 4), the
same-person warning, refusals that save nothing, the Skipped date reason, hidden Service roles, the confirm
step on a past Service, no Private note text, and the panel in Tiếng Việt with no English left.

Card RO-5 (decision D6): the Roster page (the quarter list like the pastor's: one table per month, one row
per ISO week, a week in the month of its Sunday) with its read model ``roster.roster_weeks``, and Auto-fill:
the preview writes nothing, Save fills, a second Save adds 0; bad values give the 400 page."""

import datetime as dt
import pathlib
import re
import tempfile
import unittest
import urllib.parse

import _support  # noqa: F401 - puts the repo root on sys.path
from _support import CopyTestCase
from churchmgr import calendar as cal
from churchmgr import db, fake, lists, people, roster
from churchmgr.i18n import TextError, english_left
from churchmgr.pages import roster as roster_pages
from test_pages_people import TODAY, PagesTestBase, flash_of, section, shown
from test_server import LiveServer

PANEL = "service-roles"


def sunday(weeks):
    """The Sunday ``weeks`` weeks after the Sunday of this ISO week (negative: before it)."""
    return TODAY + dt.timedelta(days=6 - TODAY.weekday(), weeks=weeks)


def block(box, role_id):
    """The part of the panel for one Service role (its name, names with dates, its forms)."""
    m = re.search(rf'<div data-row data-role="{role_id}">(.*?)</dd></div>', box, re.S)
    assert m is not None, f"no Service role {role_id} in the panel"
    return m.group(1)


def struck(name, start, end, lang="en"):
    """A closed link as the panel shows it: the name struck, then its dates."""
    words = ("from", "to") if lang == "en" else ("từ", "đến")
    return f'<s lang="vi">{name}</s> · {words[0]} {shown(start)} {words[1]} {shown(end)}'


class RosterPanelTest(PagesTestBase):
    """One English fake church for the class. Each test makes its own Service on its own Sunday."""

    def setUp(self):
        conn = self.db()
        by_name = {r["name"]: r["id"] for r in roster.roles(conn, include_hidden=True)}
        self.boi_linh, self.leader, self.offering, self.in_charge = (
            by_name[n] for n in ("Bồi linh", "Service leader", "Offering leader", "Ministry in charge"))
        self.persons = people.list_persons(conn)
        roster.set_same_person_rule(conn, "service")  # the default; said here so the warning test can count on it

    def service(self, day, kind="Service"):
        return cal.add_calendar_item(self.db(), kind, f"RO-4 {kind} {day:%d/%m}", f"{day.isoformat()} 08:00")[0]

    def panel(self, iid):
        return section(self.page(f"/calendar/{iid}"), PANEL)

    def save(self, iid, role_id, expect=303, **value):
        headers, page = self.post(f"/calendar/{iid}/roles", {"role_id": role_id, **value}, expect=expect)
        if expect == 303:  # POST-redirect-GET back to the panel
            where = urllib.parse.urlsplit(headers["location"])
            self.assertEqual((where.path, where.fragment), (f"/calendar/{iid}", PANEL))
        return headers, page

    def clear(self, iid, role_id, expect=303, **more):
        return self.post(f"/calendar/{iid}/roles/clear", {"role_id": role_id, **more}, expect=expect)

    def links(self, iid=None):
        sql = "SELECT service_role_id, person_id, ministry_id, start_date, end_date FROM service_role_link"
        args = ()
        if iid is not None:
            sql, args = sql + " WHERE calendar_item_id = ?", (iid,)
        return [tuple(r) for r in self.db().execute(sql + " ORDER BY id", args)]

    def held(self, iid, role_id):
        row = roster.open_value(self.db(), iid, role_id)
        return None if row is None else (row["person_id"], row["ministry_id"])

    def test_the_panel_is_on_a_service_and_not_on_a_meeting(self):
        iid = self.service(sunday(30))
        page = self.page(f"/calendar/{iid}")
        self.assertIn(f'<div id="{PANEL}"><section class="panel " data-panel="{PANEL}"', page)
        box = section(page, PANEL)
        self.assertIn(">Service roles</h2>", box)
        # the 3 Sunday Service roles in their order; the Thursday one is not there
        self.assertEqual(re.findall(r'<dt lang="vi">([^<]*)</dt>', box),
                         ["Service leader", "Offering leader", "Ministry in charge"])
        self.assertNotIn("Bồi linh", box)
        for rid in (self.leader, self.offering, self.in_charge):
            part = block(box, rid)
            self.assertIn('<p class="faint">empty</p>', part)
            self.assertIn(f'action="/calendar/{iid}/roles"', part)
            self.assertIn(f'<input type="hidden" name="role_id" value="{rid}">', part)
            self.assertNotIn("Clear", part)  # nothing to clear yet
        self.assertIn('name="person_id"', block(box, self.leader))
        self.assertIn('name="ministry_id"', block(box, self.in_charge))
        self.assertIn("— Choose a Ministry —", block(box, self.in_charge))
        # after the Head count panel, before People
        self.assertLess(page.index('data-panel="head-count"'), page.index(f'data-panel="{PANEL}"'))
        self.assertLess(page.index(f'data-panel="{PANEL}"'), page.index('data-panel="people"'))
        meeting = self.service(sunday(30), kind="Meeting")
        self.assertNotIn(PANEL, self.page(f"/calendar/{meeting}"))
        # a Service on a weekday with no Service role says so
        wednesday = self.service(sunday(30) - dt.timedelta(days=4))
        self.assertIn('<p class="empty">No Service role for this day of the week yet.</p>', self.panel(wednesday))

    def test_save_swap_and_clear_keep_the_history(self):
        iid = self.service(sunday(31))
        a, b = self.persons[3], self.persons[4]
        today = TODAY.isoformat()
        headers, _ = self.save(iid, self.leader, person_id=a["id"])
        self.assertEqual(flash_of(headers), f"Saved: {a['full_name']} for Service leader.")
        self.assertEqual(self.held(iid, self.leader), (a["id"], None))
        part = block(self.panel(iid), self.leader)
        self.assertIn(f'<a href="/people/{a["id"]}"><span lang="vi">{a["full_name"]}</span></a>', part)
        self.assertIn(f"from {shown(today)}", part)
        self.assertRegex(part, rf'<option value="{a["id"]}" selected>')
        self.assertIn(f'formaction="/calendar/{iid}/roles/clear"', part)
        # a swap: the old name is struck with its dates, the new one is open
        headers, _ = self.save(iid, self.leader, person_id=b["id"])
        self.assertEqual(flash_of(headers), f"Saved: {b['full_name']} for Service leader.")
        part = block(self.panel(iid), self.leader)
        self.assertIn(struck(a["full_name"], today, today), part)
        self.assertIn(f'<span lang="vi">{b["full_name"]}</span></a>', part)
        self.assertEqual(self.links(iid), [(self.leader, a["id"], None, today, today),
                                           (self.leader, b["id"], None, today, None)])
        # the same name again changes nothing
        headers, _ = self.save(iid, self.leader, person_id=b["id"])
        self.assertEqual(flash_of(headers), f"{b['full_name']} already has Service leader. Nothing changed.")
        self.assertEqual(len(self.links(iid)), 2)
        # clear (a Service after today: no confirm step): empty again, both names struck, no row deleted
        headers, _ = self.clear(iid, self.leader)
        self.assertEqual(flash_of(headers), "Service leader is now empty. The old name is kept, struck.")
        self.assertIsNone(self.held(iid, self.leader))
        self.assertEqual(self.links(iid), [(self.leader, a["id"], None, today, today),
                                           (self.leader, b["id"], None, today, today)])
        part = block(self.panel(iid), self.leader)
        self.assertIn('<p class="faint">empty</p>', part)
        self.assertIn(struck(b["full_name"], today, today), part)
        self.assertIn(struck(a["full_name"], today, today), part)
        self.assertLess(part.index(b["full_name"]), part.index(a["full_name"]))  # the newest first
        self.assertNotIn("Clear", part)
        headers, _ = self.clear(iid, self.leader)
        self.assertEqual(flash_of(headers), "Service leader is already empty. Nothing changed.")
        self.assertEqual(len(self.links(iid)), 2)

    def test_a_ministry_role_takes_a_ministry(self):
        iid = self.service(sunday(32))
        youth = lists.find_item(self.db(), "ministry", name="Youth")["id"]
        headers, _ = self.save(iid, self.in_charge, ministry_id=youth)
        self.assertEqual(flash_of(headers), "Saved: Youth for Ministry in charge.")
        self.assertEqual(self.held(iid, self.in_charge), (None, youth))
        part = block(self.panel(iid), self.in_charge)
        self.assertIn('<p><span lang="vi">Youth</span>', part)
        self.assertRegex(part, rf'<option value="{youth}" selected>Youth</option>')
        # a Person for a Ministry role is refused next to its select, and nothing is saved
        _h, page = self.save(iid, self.in_charge, expect=400, person_id=self.persons[0]["id"])
        part = block(section(page, PANEL), self.in_charge)
        self.assertIn(f'<p class="error" id="role-{self.in_charge}-error">The Service role “Ministry in charge” is done '
                      "by a Ministry: choose a Ministry.</p>", part)
        self.assertEqual(self.held(iid, self.in_charge), (None, youth))

    def test_a_same_service_conflict_is_saved_with_a_warning(self):
        day = sunday(33)
        iid = self.service(day)
        a = self.persons[5]
        self.save(iid, self.leader, person_id=a["id"])
        self.save(iid, self.offering, person_id=a["id"])  # breaks the rule: still saved
        self.assertEqual((self.held(iid, self.leader), self.held(iid, self.offering)), ((a["id"], None),) * 2)
        box = self.panel(iid)

        def warning(role):
            return (f'<p class="hint" role="note">Warning: <span lang="vi">{a["full_name"]}</span> also has the '
                    f'Service role <span lang="vi">{role}</span> on <span class="num">{shown(day.isoformat())}</span>.</p>')

        self.assertIn(warning("Service leader"), block(box, self.offering))
        self.assertIn(warning("Offering leader"), block(box, self.leader))
        self.assertNotIn("Warning", block(box, self.in_charge))
        # another Offering leader: the warning is gone
        self.save(iid, self.offering, person_id=self.persons[6]["id"])
        self.assertNotIn("Warning", self.panel(iid))

    def test_a_wrong_role_or_weekday_is_refused_and_saves_nothing(self):
        iid = self.service(sunday(34))
        pid = self.persons[0]["id"]
        youth = lists.find_item(self.db(), "ministry", name="Youth")["id"]
        before = self.links()
        cases = [  # (form, sentence, at its role)
            ({"role_id": self.boi_linh, "person_id": pid}, "The Service role “Bồi linh” is for another day of the week.",
             None),
            ({"role_id": self.leader, "person_id": ""}, "The Service role “Service leader” is done by a Person: "
                                                        "choose a Person.", self.leader),
            ({"role_id": self.leader, "ministry_id": youth}, "The Service role “Service leader” is done by a Person: "
                                                             "choose a Person.", self.leader),
            ({"role_id": self.leader, "person_id": "999999"}, "No Person with id 999999.", self.leader),
            ({"role_id": "999999", "person_id": pid}, "No Service role with id 999999.", None),
            ({"role_id": "x", "person_id": pid}, "Service role must be a whole number.", None),
        ]
        for form, sentence, at in cases:
            _h, page = self.post(f"/calendar/{iid}/roles", form, expect=400)
            box = section(page, PANEL)
            where = block(box, at) if at else box.split("<dl", 1)[0]  # a role not in the panel: at the top
            self.assertIn(sentence, where, form)
            self.assertIn('class="error"', where, form)
            self.assertEqual(box.count('class="error"'), 1, form)
        self.assertEqual(self.links(), before)
        # a Meeting has no Service roles: the plain refusal page
        meeting = self.service(sunday(34), kind="Meeting")
        for path in (f"/calendar/{meeting}/roles", f"/calendar/{meeting}/roles/clear"):
            _h, page = self.post(path, {"role_id": self.leader, "person_id": pid}, expect=400)
            self.assertIn("Only a Service has Service roles.", page)
        self.post("/calendar/999999/roles", {"role_id": self.leader, "person_id": pid}, expect=404)
        self.assertEqual(self.links(), before)

    def test_clear_on_a_past_service_asks_first(self):
        day = sunday(-3)
        iid = self.service(day)
        a = self.persons[7]
        self.save(iid, self.offering, person_id=a["id"])
        _h, page = self.clear(iid, self.offering, expect=200)
        confirm = section(page, "confirm")
        self.assertIn('Clear <strong lang="vi">Offering leader</strong> of <strong lang="vi">RO-4 Service', confirm)
        self.assertIn("This Calendar item is in the past. The old name is kept, struck.", confirm)
        self.assertIn(f'<input type="hidden" name="role_id" value="{self.offering}">', confirm)
        self.assertIn('<input type="hidden" name="confirm" value="yes">', confirm)
        self.assertIn(f'href="/calendar/{iid}#{PANEL}"', confirm)  # Cancel goes back to the panel
        self.assertEqual(self.held(iid, self.offering), (a["id"], None))  # nothing changed yet
        headers, _ = self.clear(iid, self.offering, confirm="yes")
        self.assertEqual(flash_of(headers), "Offering leader is now empty. The old name is kept, struck.")
        self.assertIsNone(self.held(iid, self.offering))

    def test_a_skipped_date_shows_its_reason_on_top(self):
        day = sunday(35)
        iid = self.service(day)
        conn = self.db()
        roster.add_skipped_date(conn, day.isoformat(), "RO-4 Tết")
        self.addCleanup(roster.remove_skipped_date, conn, day.isoformat())
        box = self.panel(iid)
        head = box.split("</header>", 1)[0]  # the line under the panel title
        self.assertIn('<span class="meta">Skipped date: <strong lang="vi">RO-4 Tết</strong></span>', head)
        self.save(iid, self.leader, person_id=self.persons[8]["id"])  # a name can still be set by hand

    def test_a_hidden_role_keeps_its_history_and_one_with_no_link_is_gone(self):
        iid = self.service(sunday(36))
        conn = self.db()
        kept = roster.add_role(conn, "RO-4 Đọc Kinh Thánh", 6, "person")
        gone = roster.add_role(conn, "RO-4 Cầu nguyện", 6, "person")
        for rid in (kept, gone):  # the other tests of this class never see them
            self.addCleanup(roster.set_role_active, conn, rid, False)
        a = self.persons[9]
        self.save(iid, kept, person_id=a["id"])
        self.assertIn("RO-4 Cầu nguyện", self.panel(iid))  # shown while it is active
        roster.set_role_active(conn, kept, False)
        roster.set_role_active(conn, gone, False)
        box = self.panel(iid)
        self.assertNotIn("RO-4 Cầu nguyện", box)
        part = block(box, kept)
        self.assertIn(f'<span lang="vi">{a["full_name"]}</span></a>', part)
        self.assertIn('<p class="hint">This Service role is hidden. Its history is kept.</p>', part)
        self.assertNotIn('name="person_id"', part)  # no pick: a hidden Service role is refused
        self.assertIn(f'action="/calendar/{iid}/roles/clear"', part)
        _h, page = self.save(iid, kept, expect=400, person_id=self.persons[10]["id"])
        self.assertIn("The Service role “RO-4 Đọc Kinh Thánh” is hidden. Show it first.", section(page, PANEL))
        self.assertEqual(self.held(iid, kept), (a["id"], None))
        self.clear(iid, kept)  # a Service after today: no confirm step
        self.assertIsNone(self.held(iid, kept))
        self.assertIn(struck(a["full_name"], TODAY.isoformat(), TODAY.isoformat()), block(self.panel(iid), kept))

    def test_no_private_note_text_on_the_page(self):
        conn = self.db()
        pid = conn.execute("SELECT id FROM person WHERE full_name = ?", (fake.FIRST_PERSON,)).fetchone()[0]
        notes = [r[0] for r in conn.execute("SELECT body FROM private_note")]
        self.assertTrue(notes)
        iid = self.service(sunday(37))
        self.save(iid, self.leader, person_id=pid)  # a Person with a Private note holds a Service role
        page = self.page(f"/calendar/{iid}")
        self.assertIn(fake.FIRST_PERSON, block(section(page, PANEL), self.leader))
        self.assertNotIn(fake.MARKER, page)
        for body in notes:
            self.assertNotIn(body, page)


class VietnameseRosterPanelTest(LiveServer, unittest.TestCase):
    """The panel on a Tiếng Việt fake church: its words, its flash, its refusal and its confirm step."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        root = pathlib.Path(cls.tmp.name)
        assert "onedrive" not in str(root.resolve()).lower()
        cls.copy = root / "fake"
        fake.build_fake_church(cls.copy, people=20, lang="vi")
        cls.start(cls.copy, root, remember=False)

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.tmp.cleanup()

    def setUp(self):
        self.conn = db.connect(self.copy / db.DB_NAME)
        self.addCleanup(self.conn.close)
        self.roles = {r["name"]: r["id"] for r in roster.roles(self.conn)}

    def page(self, path, expect=200):
        status, _h, page = self.get_text(path)
        self.assertEqual(status, expect, path)
        return page

    def post(self, path, form, expect=303):
        status, headers, data = self.request("POST", path, form)
        self.assertEqual(status, expect, data.decode("utf-8")[:1500])
        return headers, data.decode("utf-8")

    def assert_vietnamese(self, page):
        self.assertIn('<html lang="vi">', page)
        self.assertEqual(english_left(page), [])

    def test_a_swap_and_a_clear_of_the_fake_church_in_vietnamese(self):
        iid, rid = self.conn.execute("SELECT calendar_item_id, service_role_id FROM service_role_link "
                                     "WHERE end_date IS NOT NULL ORDER BY id LIMIT 1").fetchone()
        page = self.page(f"/calendar/{iid}")
        self.assert_vietnamese(page)
        box = section(page, PANEL)
        self.assertIn(">Phần vụ</h2>", box)
        for name in ("Hướng dẫn chương trình", "Hướng dẫn dâng hiến", "Ban phụ trách"):
            self.assertIn(f'<dt lang="vi">{name}</dt>', box)
        closed = [r for r in roster.item_links(self.conn, iid) if r["service_role_id"] == rid and r["end_date"]]
        self.assertIn(struck(closed[0]["name"], closed[0]["start_date"], closed[0]["end_date"], "vi"), block(box, rid))

    def test_a_skipped_date_in_vietnamese(self):
        iid = self.conn.execute("SELECT ci.id FROM calendar_item ci JOIN skipped_date sd "
                                "ON sd.date = substr(ci.starts_at, 1, 10) WHERE ci.kind = 'Service'").fetchone()[0]
        page = self.page(f"/calendar/{iid}")
        self.assert_vietnamese(page)
        self.assertIn(f'<span class="meta">Ngày nghỉ phân công: <strong lang="vi">{fake.ROSTER_SKIPPED}</strong>'
                      "</span>", section(page, PANEL).split("</header>", 1)[0])

    def test_a_save_a_warning_a_refusal_and_a_confirm_in_vietnamese(self):
        day = sunday(40)
        iid = cal.add_calendar_item(self.conn, "Service", "RO-4 Thờ phượng", f"{day.isoformat()} 08:00")[0]
        pid = people.list_persons(self.conn)[2]["id"]
        name = people.get_person(self.conn, pid)["full_name"]
        leader, offering = self.roles["Hướng dẫn chương trình"], self.roles["Hướng dẫn dâng hiến"]
        page = self.page(f"/calendar/{iid}")
        self.assert_vietnamese(page)
        self.assertEqual(section(page, PANEL).count('<p class="faint">chưa có</p>'), 3)
        self.post(f"/calendar/{iid}/roles", {"role_id": leader, "person_id": pid})
        headers, _ = self.post(f"/calendar/{iid}/roles", {"role_id": offering, "person_id": pid})
        self.assertEqual(flash_of(headers), f"Đã lưu: {name} làm Hướng dẫn dâng hiến.")
        page = self.page(headers["location"])
        self.assert_vietnamese(page)
        self.assertIn(f'Lưu ý: <span lang="vi">{name}</span> cũng có Phần vụ <span lang="vi">Hướng dẫn chương '
                      f'trình</span> ngày <span class="num">{shown(day.isoformat())}</span>.',
                      block(section(page, PANEL), offering))
        _h, page = self.post(f"/calendar/{iid}/roles", {"role_id": self.roles["Bồi linh"], "person_id": pid},
                             expect=400)
        self.assert_vietnamese(page)
        self.assertIn("Phần vụ “Bồi linh” là của một ngày khác trong tuần.", section(page, PANEL))
        # a past Service: Bỏ trống asks first
        past = cal.add_calendar_item(self.conn, "Service", "RO-4 Thờ phượng", f"{sunday(-2).isoformat()} 08:00")[0]
        self.post(f"/calendar/{past}/roles", {"role_id": leader, "person_id": pid})
        part = block(section(self.page(f"/calendar/{past}"), PANEL), leader)
        self.assertIn(">Bỏ trống</button>", part)
        self.assertIn(f"từ {shown(TODAY.isoformat())}", part)
        _h, page = self.post(f"/calendar/{past}/roles/clear", {"role_id": leader}, expect=200)
        self.assert_vietnamese(page)
        self.assertIn("Lịch này đã qua. Tên cũ vẫn được giữ, gạch ngang.", section(page, "confirm"))
        self.assertIn(">Có, bỏ trống</button>", section(page, "confirm"))

    def test_the_roster_and_auto_fill_in_vietnamese(self):
        year, q = roster_pages.quarter_of(TODAY)
        start, end = TODAY.isoformat(), (TODAY + dt.timedelta(days=56)).isoformat()
        for path in ("/calendar/roster", f"/calendar/roster?quarter={year}-{q}", "/calendar/roster/fill",
                     f"/calendar/roster/fill?from={start}&to={end}"):
            self.assert_vietnamese(self.page(path))
        page = self.page("/calendar/roster")
        self.assertIn(">Lịch phân công</h1>", page)
        self.assertIn(f'<p class="sub">Quý {q}/{year}</p>', page)
        month = 3 * q - 2
        box = section(page, f"roster-{year}-{month:02d}")
        self.assertIn(f">Tháng {month}</h2>", box)
        self.assertEqual(headers(box), ["Thứ Năm", "Bồi linh", "Chúa Nhật", "Hướng dẫn chương trình",
                                        "Hướng dẫn dâng hiến", "Ghi chú"])
        self.assertIn('href="/calendar/roster/fill?from=', page)
        self.assertIn(">Tự động xếp lịch</a>", page)
        # the 400 page of a bad quarter, in Tiếng Việt
        status, _h, bad = self.get_text("/calendar/roster?quarter=nope")
        self.assertEqual(status, 400)
        self.assert_vietnamese(bad)
        self.assertIn("Quý phải viết YYYY-Q, ví dụ 2026-4.", bad)
        # the fake Skipped date shows its reason, bold, on its quarter's page
        day = self.conn.execute("SELECT date FROM skipped_date").fetchone()[0]
        y, k = roster_pages.quarter_of(dt.date.fromisoformat(day))
        self.assertIn(f'<strong lang="vi">{fake.ROSTER_SKIPPED}</strong>', self.page(f"/calendar/roster?quarter={y}-{k}"))


# ---------------------------------------------------------------- card RO-5: the Roster

def headers(box):
    """The column headers of the one Roster table in ``box``."""
    return re.findall(r'<th scope="col"[^>]*>([^<]*)</th>', box)


def body_rows(box):
    """The cells of each body row of the Roster table in ``box``: a list of lists of inner HTML."""
    tbody = box.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    return [re.findall(r"<td[^>]*>(.*?)</td>", row, re.S) for row in re.findall(r"<tr>(.*?)</tr>", tbody, re.S)]


def may_boundary():
    """A Sunday on 1, 2 or 3 May some years ahead: the Thursday of its week is in April."""
    year = TODAY.year + 3
    while dt.date(year, 5, 1).weekday() not in (4, 5, 6):  # 1 May a Friday, Saturday or Sunday
        year += 1
    first = dt.date(year, 5, 1)
    return first + dt.timedelta(days=6 - first.weekday())


class QuarterTest(unittest.TestCase):
    """The small logic of the Roster page: quarters, the month of a week, the Auto-fill dates."""

    def test_parse_quarter(self):
        self.assertEqual(roster_pages.parse_quarter(" 2026-4 ", TODAY), (2026, 4))
        self.assertEqual(roster_pages.parse_quarter("", dt.date(2026, 4, 30)), (2026, 2))
        for bad, key in (("nope", "calendar.roster_err_quarter"), ("2026-5", "calendar.roster_err_quarter"),
                         ("2026-Q1", "calendar.roster_err_quarter"), ("26-1", "calendar.roster_err_quarter"),
                         ("1899-4", "calendar.roster_err_quarter_years"), ("0000-1", "calendar.roster_err_quarter_years")):
            with self.assertRaises(TextError) as ctx:
                roster_pages.parse_quarter(bad, TODAY)
            self.assertEqual(ctx.exception.key, key, bad)

    def test_a_week_belongs_to_the_month_of_its_sunday(self):
        self.assertEqual(roster_pages.week_month(dt.date(2026, 4, 27)), (2026, 5))  # Thursday 30/04, Sunday 03/05
        self.assertEqual(roster_pages.quarter_of(dt.date(2026, 4, 30)), (2026, 2))
        self.assertEqual(roster_pages.quarter_of(dt.date(2026, 6, 29)), (2026, 3))  # its Sunday is 05/07
        self.assertEqual(roster_pages.quarter_of(dt.date(2026, 12, 31)), (2027, 1))  # its Sunday is 03/01/2027
        self.assertEqual(roster_pages.quarter_of(dt.date(9999, 12, 31)), (9999, 4))  # no Sunday after it

    def test_quarter_dates_are_monday_to_the_last_sunday(self):
        d = dt.date
        self.assertEqual(roster_pages.quarter_dates(2026, 1), (d(2025, 12, 29), d(2026, 3, 29)))  # 01/01 .. 29/03
        self.assertEqual(roster_pages.quarter_dates(2026, 2), (d(2026, 3, 30), d(2026, 6, 28)))
        self.assertEqual(roster_pages.quarter_dates(2026, 4), (d(2026, 9, 28), d(2026, 12, 27)))
        self.assertEqual(roster_pages.quarter_dates(1900, 1), (d(1900, 1, 1), d(1900, 3, 25)))
        self.assertEqual(roster_pages.quarter_dates(9999, 4)[1], d(9999, 12, 26))

    def test_quarter_step_and_text(self):
        self.assertEqual(roster_pages.quarter_step(2026, 4, 1), (2027, 1))
        self.assertEqual(roster_pages.quarter_step(2026, 1, -1), (2025, 4))
        self.assertIsNone(roster_pages.quarter_step(1900, 1, -1))
        self.assertIsNone(roster_pages.quarter_step(9999, 4, 1))
        self.assertEqual(roster_pages.quarter_text(2026, 4), "2026-4")

    def test_auto_fill_starts_today_inside_the_quarter(self):
        d = dt.date
        first, last = d(2026, 9, 28), d(2026, 12, 27)
        self.assertEqual(roster_pages.fill_dates(first, last, d(2026, 11, 21)), (d(2026, 11, 21), last))
        self.assertEqual(roster_pages.fill_dates(first, last, d(2027, 1, 5)), (first, last))  # a past quarter
        self.assertEqual(roster_pages.fill_dates(first, last, d(2026, 5, 1)), (first, last))  # a coming one


class RosterWeeksTest(CopyTestCase):
    """``roster.roster_weeks``: the read model of the Roster page."""

    def setUp(self):
        super().setUp()
        self.leader = next(r["id"] for r in roster.roles(self.conn) if r["name"] == "Service leader")
        self.a = people.add_person(self.conn, "Lê Văn An")
        self.b = people.add_person(self.conn, "Trần Thị Bình")

    def service(self, starts_at):
        return cal.add_calendar_item(self.conn, "Service", "Thờ phượng", starts_at)[0]

    def test_weeks_days_links_and_the_first_service_of_a_month(self):
        self.service("2026-04-23 19:30")  # the first Thursday Service of April, before the range
        thursday, sunday = self.service("2026-04-30 19:30"), self.service("2026-05-03 08:00")
        morning, evening = self.service("2026-05-10 08:00"), self.service("2026-05-10 18:00")
        roster.set_link(self.conn, sunday, self.leader, self.a, day="2026-04-20")
        roster.set_link(self.conn, sunday, self.leader, self.b, day="2026-04-25")  # a swap
        before = self.conn.total_changes
        weeks = roster.roster_weeks(self.conn, "2026-04-28", "2026-05-12")
        self.assertEqual(self.conn.total_changes, before)  # reads only
        self.assertEqual([w["monday"] for w in weeks], [dt.date(2026, 4, 27), dt.date(2026, 5, 4), dt.date(2026, 5, 11)])
        self.assertEqual([sorted(w["days"]) for w in weeks], [[3, 6]] * 3)  # Thursday and Sunday have Service roles
        first = weeks[0]["days"]
        self.assertEqual((first[3]["date"], first[3]["service"], first[3]["month_first"]),
                         (dt.date(2026, 4, 30), thursday, False))  # 30/04: not the first Thursday of April
        self.assertEqual((first[6]["service"], first[6]["month_first"], first[6]["skipped"]), (sunday, True, None))
        held = first[6]["links"][self.leader]
        self.assertEqual([(r["person_id"], r["start_date"], r["end_date"]) for r in held],
                         [(self.a, "2026-04-20", "2026-04-25"), (self.b, "2026-04-25", None)])  # oldest first
        second = weeks[1]["days"][6]
        self.assertEqual((second["service"], second["others"], second["month_first"], second["links"]),
                         (morning, [(evening, "2026-05-10 18:00")], False, {}))
        self.assertEqual((weeks[2]["days"][6]["service"], weeks[2]["days"][3]["service"]), (None, None))
        # a Skipped date on the first Sunday: the next Sunday is the first Service of May
        roster.add_skipped_date(self.conn, "2026-05-03", "Hội đồng bồi linh")
        weeks = roster.roster_weeks(self.conn, "2026-04-28", "2026-05-12")
        self.assertEqual((weeks[0]["days"][6]["skipped"], weeks[0]["days"][6]["month_first"]),
                         ("Hội đồng bồi linh", False))
        self.assertTrue(weeks[1]["days"][6]["month_first"])

    def test_the_last_days_and_a_bad_range(self):
        weeks = roster.roster_weeks(self.conn, "9999-12-30", "9999-12-31")
        self.assertEqual([(w["monday"], sorted(w["days"])) for w in weeks], [(dt.date(9999, 12, 27), [3])])
        with self.assertRaises(TextError) as ctx:
            roster.roster_weeks(self.conn, "2026-05-03", "2026-05-02")
        self.assertEqual(ctx.exception.key, "calendar.err_end_date_before")
        for role in roster.roles(self.conn):  # no shown Service role: no days
            roster.set_role_active(self.conn, role["id"], False)
        self.assertEqual(roster.roster_weeks(self.conn, "2026-05-01", "2026-05-03")[0]["days"], {})


class RosterPageTest(PagesTestBase):
    """The Roster page and Auto-fill on an English fake church. The table tests use Services of a year far
    ahead (the fake church has none there); the Auto-fill tests use the fake church's coming Services."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        conn = db.connect(cls.copy / db.DB_NAME)
        try:
            cls.make_year(conn)
        finally:
            conn.close()

    @classmethod
    def make_year(cls, conn):
        """A May like the pastor's sample: its first week starts in April, a swap, a cleared name, a Skipped
        date with a Service and one without."""
        by_name = {r["name"]: r["id"] for r in roster.roles(conn)}
        boi_linh, leader, offering, in_charge = (by_name[n] for n in (
            "Bồi linh", "Service leader", "Offering leader", "Ministry in charge"))
        persons = people.list_persons(conn)
        cls.names = [p["full_name"] for p in persons[20:27]]
        a, b, c, d, e, f, g = (p["id"] for p in persons[20:27])
        youth = lists.find_item(conn, "ministry", name="Youth")["id"]
        s1 = cls.sunday = may_boundary()

        def service(day, hour="08:00"):
            return cal.add_calendar_item(conn, "Service", f"RO-5 {day:%d/%m}", f"{day.isoformat()} {hour}")[0]

        def before(day, days):
            return (day - dt.timedelta(days=days)).isoformat()

        cls.april = service(s1 - dt.timedelta(days=7))
        cls.thursday1, cls.sunday1 = service(s1 - dt.timedelta(days=3), "19:30"), service(s1)
        cls.sunday2, cls.sunday3 = service(s1 + dt.timedelta(days=7)), service(s1 + dt.timedelta(days=14))
        roster.set_link(conn, cls.thursday1, boi_linh, c, day=before(s1, 20))
        roster.set_link(conn, cls.sunday1, leader, a, day=before(s1, 20))
        roster.set_link(conn, cls.sunday1, offering, b, day=before(s1, 20))
        roster.set_link(conn, cls.sunday1, in_charge, ministry_id=youth, day=before(s1, 20))
        roster.set_link(conn, cls.sunday2, leader, d, day=before(s1, 20))
        roster.set_link(conn, cls.sunday2, leader, e, day=before(s1, 10))  # a swap
        roster.set_link(conn, cls.sunday2, offering, f, day=before(s1, 20))
        roster.clear_link(conn, cls.sunday2, offering, day=before(s1, 9))  # cleared: the lone struck name
        roster.set_link(conn, cls.april, leader, g, day=before(s1, 30))
        roster.add_skipped_date(conn, (s1 + dt.timedelta(days=14)).isoformat(), "RO-5 Hội đồng bồi linh")
        roster.add_skipped_date(conn, (s1 + dt.timedelta(days=11)).isoformat(), "RO-5 Nghỉ Tết")  # no Service

    def links(self):
        return [tuple(r) for r in self.db().execute("SELECT * FROM service_role_link ORDER BY id")]

    def quarter_page(self):
        return self.page(f"/calendar/roster?quarter={self.sunday.year}-2")

    def test_the_may_table_has_the_sample_columns_in_order(self):
        page = self.quarter_page()
        self.assertIn(">Roster</h1>", page)
        self.assertIn(f'<p class="sub">Quarter 2, {self.sunday.year}</p>', page)
        for month, title in ((4, "April"), (5, "May"), (6, "June")):
            box = section(page, f"roster-{self.sunday.year}-{month:02d}")
            self.assertIn(f">{title}</h2>", box)
            self.assertEqual(headers(box), ["Thu", "Bồi linh", "Sun", "Service leader", "Offering leader", "Notes"])
        may = section(page, f"roster-{self.sunday.year}-05")
        rows = body_rows(may)
        a, b, c, d, e, f, _g = self.names
        s1 = self.sunday
        self.assertEqual(rows[0], [
            f'<a href="/calendar/{self.thursday1}#{PANEL}"><span class="num">{s1 - dt.timedelta(days=3):%d/%m}</span></a>',
            f'<span class="roster-names" title="{c} · from {shown((s1 - dt.timedelta(days=20)).isoformat())}">'
            f'<span lang="vi">{c}</span></span>',
            f'<a href="/calendar/{self.sunday1}#{PANEL}"><span class="num">{s1:%d/%m}</span></a>',
            f'<span class="roster-names" title="{a} · from {shown((s1 - dt.timedelta(days=20)).isoformat())}">'
            f'<strong lang="vi">{a}</strong></span>',  # the first Service of May: Service leader starts a round
            f'<span class="roster-names" title="{b} · from {shown((s1 - dt.timedelta(days=20)).isoformat())}">'
            f'<span lang="vi">{b}</span></span>',
            f'<span class="roster-names" title="Youth · from {shown((s1 - dt.timedelta(days=20)).isoformat())}">'
            '<span lang="vi">Youth</span></span>',
        ])
        self.assertEqual(len(rows), 5)  # one row per week: May has 5 Sundays when the first is on 1 to 3 May
        self.assertTrue(all(cell == "" for row in rows[3:] for cell in row))  # weeks with no Service
        # the Thursday 30/04 (or so) is in the May table, not in the April one
        april = section(page, f"roster-{self.sunday.year}-04")
        self.assertNotIn(f"/calendar/{self.thursday1}#", april)
        self.assertIn(f"/calendar/{self.april}#", april)
        self.assertIn("<strong", body_rows(april)[-1][3])  # the only April Service: the first of April, bold

    def test_a_swap_and_a_cleared_name_are_struck_with_their_dates(self):
        rows = body_rows(section(self.quarter_page(), f"roster-{self.sunday.year}-05"))
        _a, _b, _c, d, e, f, _g = self.names
        s1 = self.sunday

        def on(days):
            return shown((s1 - dt.timedelta(days=days)).isoformat())

        self.assertEqual(rows[1][3], f'<span class="roster-names" title="{d} · from {on(20)} to {on(10)}\n'
                                     f'{e} · from {on(10)}"><s lang="vi">{d}</s>\u00a0\u2192 <span lang="vi">{e}</span>'
                                     "</span>")
        self.assertEqual(rows[1][4], f'<span class="roster-names" title="{f} · from {on(20)} to {on(9)}">'
                                     f'<s lang="vi">{f}</s></span>')
        self.assertEqual(rows[1][:2], ["", ""])  # no Thursday Service that week
        self.assertNotIn("<strong", rows[1][3])  # only the first Service of the month is bold

    def test_a_skipped_date_shows_its_reason_in_the_first_role_cell(self):
        rows = body_rows(section(self.quarter_page(), f"roster-{self.sunday.year}-05"))
        s3 = self.sunday + dt.timedelta(days=14)
        self.assertEqual(rows[2], [
            f'<span class="num">{s3 - dt.timedelta(days=3):%d/%m}</span>',  # no Service: its date, no link
            '<strong lang="vi">RO-5 Nghỉ Tết</strong>',
            f'<a href="/calendar/{self.sunday3}#{PANEL}"><span class="num">{s3:%d/%m}</span></a>',
            '<strong lang="vi">RO-5 Hội đồng bồi linh</strong>', "", ""])

    def test_the_page_bar_the_print_button_and_the_calendar_link(self):
        page = self.quarter_page()
        year = self.sunday.year
        self.assertIn(f'<a class="chip" href="/calendar/roster?quarter={year}-1">‹ Quarter 1, {year}</a>', page)
        self.assertIn(f'<a class="chip" href="/calendar/roster?quarter={year}-3">Quarter 3, {year} ›</a>', page)
        self.assertNotIn('aria-current="true">This quarter', page)  # another quarter is shown
        self.assertIn('<button class="btn secondary" type="button" data-print>Print</button>', page)
        first, last = roster_pages.quarter_dates(year, 2)
        self.assertIn(f'<a class="btn primary" href="/calendar/roster/fill?from={first}&amp;to={last}">Auto-fill</a>',
                      page)
        now = self.page("/calendar/roster")
        y, q = roster_pages.quarter_of(TODAY)
        self.assertIn(f'<p class="sub">Quarter {q}, {y}</p>', now)
        self.assertIn('aria-current="true">This quarter</a>', now)
        self.assertIn(f'?from={max(roster_pages.quarter_dates(y, q)[0], TODAY)}&amp;', now)  # from today on
        self.assertEqual(now.count('<span class="today-tag no-print">This week</span>'), 1)
        self.assertIn('aria-current="page">Calendar</a>', now)  # the Calendar menu item
        self.assertIn('<a class="btn secondary" href="/calendar/roster">Roster</a>', self.page("/calendar"))

    def test_bad_values_give_the_400_page_and_save_nothing(self):
        before = self.links()
        cases = (("/calendar/roster?quarter=nope", "The quarter must be written YYYY-Q, for example 2026-4."),
                 ("/calendar/roster?quarter=2026-5", "The quarter must be written YYYY-Q, for example 2026-4."),
                 ("/calendar/roster?quarter=1899-4", "Quarter: the year must be from 1900 to 9999."),
                 ("/calendar/roster/fill?from=nope&to=2026-01-01", "Start date"),
                 ("/calendar/roster/fill?from=2026-01-01", "End date"),
                 ("/calendar/roster/fill?from=2026-02-01&to=2026-01-01",
                  "Auto-fill: the end date is before the start date."),
                 ("/calendar/roster/fill?from=2026-01-01&to=2027-06-01",
                  "Auto-fill: the end date may be at most 366 days after the start date."),
                 ("/calendar/roster/fill?quarter=nope", "The quarter must be written YYYY-Q"))
        for path, words in cases:
            status, _h, page = self.get_text(path)
            self.assertEqual(status, 400, path)
            self.assertIn(words, page, path)
            self.assertIn('<p class="lead">', page)  # the site's message page
        for form in ({"from": "nope", "to": "2026-01-01"}, {"from": "2026-02-01", "to": "2026-01-01"}, {}):
            self.post("/calendar/roster/fill", form, expect=400)
        self.assertEqual(self.links(), before)

    def test_preview_writes_nothing_and_save_fills_once(self):
        start, end = TODAY, TODAY + dt.timedelta(days=56)
        path = f"/calendar/roster/fill?from={start}&to={end}"
        plan = roster.fill_plan(self.db(), start.isoformat(), end.isoformat())
        n = len(plan["proposals"])
        self.assertGreater(n, 0)  # the fake church leaves its coming Services empty
        before = self.links()
        page = self.page(path)
        self.assertEqual(self.links(), before)  # GET never writes
        self.assertIn(f"{n} new names", page)
        self.assertEqual(page.count('<ins class="roster-new" lang="vi">'), n)  # every proposal is in a table
        summary = section(page, "fill-summary")
        self.assertIn(f'<input type="hidden" name="from" value="{start}">', summary)
        self.assertIn(f'<input type="hidden" name="to" value="{end}">', summary)
        self.assertIn('<button class="btn primary" type="submit">Save the new names</button>', summary)
        self.assertIn('method="get"', section(page, "fill-dates"))
        headers_, _page = self.post("/calendar/roster/fill", {"from": start.isoformat(), "to": end.isoformat()})
        where = urllib.parse.urlsplit(headers_["location"])
        y, q = roster_pages.quarter_of(start)
        self.assertEqual((where.path, urllib.parse.parse_qs(where.query)["quarter"]), ("/calendar/roster", [f"{y}-{q}"]))
        self.assertEqual(flash_of(headers_), f"{n} Service roles filled.")
        after = self.links()
        self.assertEqual(after[:len(before)], before)  # no old row changed (rule 4)
        self.assertEqual(len(after), len(before) + n)
        again, _page = self.post("/calendar/roster/fill", {"from": start.isoformat(), "to": end.isoformat()})
        self.assertEqual(flash_of(again), "0 Service roles filled.")
        self.assertEqual(self.links(), after)
        page = self.page(path)
        self.assertIn("No empty Service role to fill on these dates.", page)
        self.assertNotIn("Save the new names", page)

    def test_no_private_note_text_on_the_page_or_in_the_print(self):
        conn = self.db()
        notes = [r[0] for r in conn.execute("SELECT body FROM private_note")]
        self.assertTrue(notes)
        pid = conn.execute("SELECT id FROM person WHERE full_name = ?", (fake.FIRST_PERSON,)).fetchone()[0]
        leader = next(r["id"] for r in roster.roles(conn) if r["name"] == "Service leader")
        june = self.sunday + dt.timedelta(days=35)  # a Sunday of June: no other test looks at it
        iid = cal.add_calendar_item(conn, "Service", "RO-5 June", f"{june.isoformat()} 08:00")[0]
        roster.set_link(conn, iid, leader, pid)  # a Person with a Private note holds a Service role
        y, q = roster_pages.quarter_of(TODAY)
        pages = [self.quarter_page(), self.page("/calendar/roster"), self.page(f"/calendar/roster/fill?quarter={y}-{q}")]
        self.assertIn(fake.FIRST_PERSON, pages[0])
        for page in pages:  # the print is this same page (print.css only hides parts)
            self.assertNotIn(fake.MARKER, page)
            for body in notes:
                self.assertNotIn(body, page)


# ---------------------------------------------------------------- card RO-6: the Roster setup

SETUP = "/calendar/roster/setup"


def role_href(rid):
    return f"/calendar/roster/roles/{rid}"


def list_rows(box):
    """The cells of each data row of the (first) table in ``box``: a list of lists of inner HTML."""
    tbody = box.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    return [re.findall(r"<td[^>]*>(.*?)</td>", row, re.S) for row in re.findall(r"<tr data-row[^>]*>(.*?)</tr>", tbody, re.S)]


def plain(cell):
    """The text of a cell, its tags removed."""
    return re.sub(r"<[^>]+>", "", cell)


def option_values(box, name):
    """The values of the options of the select ``name`` in ``box``."""
    m = re.search(rf'<select [^>]*name="{name}"[^>]*>(.*?)</select>', box, re.S)
    assert m is not None, f"no select {name!r}"
    return re.findall(r'<option value="([^"]*)"', m.group(1))


def gone_to(test, headers, path, fragment):
    """A POST-redirect-GET back to ``path#fragment``."""
    where = urllib.parse.urlsplit(headers["location"])
    test.assertEqual((where.path, where.fragment), (path, fragment))


class SetupLogicTest(unittest.TestCase):
    """The small logic of the setup pages: where a refused form shows its sentence, and a Rotation's new order."""

    def test_a_refusal_goes_under_its_field(self):
        cases = [(TextError("errors.required", label="calendar.roster_role_name"), "name"),
                 (TextError("calendar.roster_err_name_taken", name="X"), "name"),
                 (TextError("calendar.roster_err_weekday"), "weekday"),
                 (TextError("calendar.roster_err_weekday_kept", name="X"), "weekday"),
                 (TextError("calendar.roster_err_done_by"), "done_by"),
                 (TextError("calendar.roster_err_every"), "every"),
                 (TextError("calendar.roster_err_on_off", label="calendar.roster_month_start"), "month_start"),
                 (TextError("calendar.err_month_form"), "month_start_from"),
                 (TextError("calendar.err_month_years"), "month_start_from"),
                 (TextError("calendar.roster_err_twice"), ""),  # no field of its own: the top of the form
                 (ValueError("plain words"), "")]
        for exc, field in cases:
            self.assertEqual(list(roster_pages.placed(exc, roster_pages.ROLE_PLACES)), [field], exc)
        self.assertEqual(roster_pages.placed(ValueError("plain words"), {}), {"": "plain words"})
        self.assertEqual(list(roster_pages.placed(TextError("errors.date", label="calendar.roster_skipped_date"),
                                                  roster_pages.SKIPPED_PLACES)), ["date"])

    def test_rotation_order(self):
        order = roster_pages.rotation_order
        self.assertEqual(order([1, 2, 3], 4, "add"), [1, 2, 3, 4])
        self.assertEqual(order([1, 2, 3], 3, "up"), [1, 3, 2])
        self.assertEqual(order([1, 2, 3], 1, "down"), [2, 1, 3])
        self.assertEqual(order([1, 2, 3], 1, "up"), [1, 2, 3])  # the first one up: no change
        self.assertEqual(order([1, 2, 3], 3, "down"), [1, 2, 3])  # the last one down: no change
        self.assertEqual(order([1, 2, 3], 2, "remove"), [1, 3])
        self.assertEqual(order([], 7, "add"), [7])
        for action in ("up", "down", "remove"):
            with self.assertRaises(TextError) as ctx:
                order([1, 2], 5, action)
            self.assertEqual(ctx.exception.key, "calendar.roster_err_not_in_rotation")


class RosterSetupTest(PagesTestBase):
    """Card RO-6 (decision D6): the Roster setup on an English fake church: Service roles, each Rotation, Skipped
    dates and the same-person rule. Every form goes back to its page (POST-redirect-GET); a refused one shows its
    sentence in the page's error style and saves nothing. Each test adds its own Service roles."""

    def setUp(self):
        conn = self.db()
        self.by_name = {r["name"]: r["id"] for r in roster.roles(conn, include_hidden=True)}
        self.persons = people.list_persons(conn)
        self.names = {p["id"]: p["full_name"] for p in self.persons}

    def role_rows(self):
        return [tuple(r) for r in self.db().execute("SELECT * FROM service_role ORDER BY id")]

    def add_role(self, expect=303, **form):
        values = {"weekday": "6", "done_by": "person", "every": "1", "month_start_from": "", **form}
        headers, page = self.post("/calendar/roster/roles/add", values, expect=expect)
        if expect == 303:
            gone_to(self, headers, SETUP, "setup-roles")
        return headers, page

    def new_role(self, name, **form):
        self.add_role(name=name, **form)
        return next(r["id"] for r in roster.roles(self.db(), include_hidden=True) if r["name"] == name)

    def role_row(self, rid):
        return next(r for r in list_rows(section(self.page(SETUP), "setup-roles")) if role_href(rid) in r[0])

    def rotation(self, rid):
        return [r["person_id"] or r["ministry_id"] for r in roster.rotation(self.db(), rid)]

    def test_the_setup_page_lists_the_service_roles_like_the_lists_page(self):
        page = self.page(SETUP)
        self.assertIn(">Roster setup</h1>", page)
        self.assertIn('aria-current="page">Calendar</a>', page)  # the Calendar menu item
        self.assertIn('<a class="btn secondary" href="/calendar/roster">Roster</a>', page)
        box = section(page, "setup-roles")
        self.assertEqual(headers(box), ["Service role", "Day", "Done by", "How often", "Month start", "Rotation", ""])
        rows = [r for r in list_rows(box) if not plain(r[0]).startswith("RO-6")]  # other tests add some
        expect = {"Bồi linh": ["Thursday", "A Person", "Every Service", "", "6 People"],
                  "Service leader": ["Sunday", "A Person", "Every Service", "New round each month", "6 People"],
                  "Offering leader": ["Sunday", "A Person", "Every Service", "", "6 People"],
                  "Ministry in charge": ["Sunday", "A Ministry", "Every 2 Services", "", "3 Ministries"]}
        self.assertEqual([plain(r[0]) for r in rows], list(expect))  # by weekday, then their order
        for row, (name, cells) in zip(rows, expect.items()):
            self.assertEqual(row[0], f'<a href="{role_href(self.by_name[name])}"><span lang="vi">{name}</span></a>')
            self.assertEqual(row[1:6], cells)
            self.assertIn(f'<button class="link-btn" type="submit" aria-label="Hide {name}">Hide</button>', row[6])
        self.assertIn('<legend>Add a Service role</legend>', box)
        self.assertIn('action="/calendar/roster/roles/add"', box)
        for fid in ("name", "weekday", "done_by", "every", "month_start", "month_start_from"):
            self.assertIn(f'<label for="add-role-{fid}">', box)  # every control has a visible label
        self.assertRegex(box, r'<option value="6" selected>Sunday</option>')
        self.assertIn('<option value="ministry">A Ministry</option>', box)
        self.assertNotIn('class="btn primary"', page)  # many small forms, as on the Lists page: no filled button

    def test_add_a_role_edit_it_hide_and_show_it(self):
        headers, _ = self.add_role(name="RO-6 Ushers", every="2", month_start="1", month_start_from="2027-01")
        self.assertEqual(flash_of(headers), "Added the Service role RO-6 Ushers. Click its name to set its Rotation.")
        rid = next(r["id"] for r in roster.roles(self.db()) if r["name"] == "RO-6 Ushers")
        role = roster.get_role(self.db(), rid)
        self.assertEqual(tuple(role[k] for k in ("weekday", "done_by", "every", "month_start", "month_start_from",
                                                 "active")), (6, "person", 2, 1, "2027-01", 1))
        self.assertEqual(self.role_row(rid)[1:6], ["Sunday", "A Person", "Every 2 Services",
                                                   "New round each month, from 01/2027", "No Rotation yet"])
        # edit: a new name, Thursday, every Service, no month start
        page = self.page(role_href(rid))
        self.assertIn('<h1 lang="vi">RO-6 Ushers</h1>', page)
        self.assertRegex(section(page, "role-edit"), r'<input type="checkbox" id="edit-role-month_start" '
                                                     r'name="month_start" value="1"[^>]* checked>')
        headers, _ = self.post(role_href(rid), {"name": "RO-6 Greeters", "weekday": "3", "every": "1",
                                                "month_start_from": ""})
        gone_to(self, headers, role_href(rid), "role-edit")
        self.assertEqual(flash_of(headers), "Saved the Service role RO-6 Greeters.")
        role = roster.get_role(self.db(), rid)
        self.assertEqual(tuple(role[k] for k in ("name", "weekday", "every", "month_start", "month_start_from")),
                         ("RO-6 Greeters", 3, 1, 0, None))
        box = section(self.page(role_href(rid)), "role-edit")
        self.assertRegex(box, r'<option value="3" selected>Thursday</option>')
        self.assertNotRegex(box, r'name="month_start" value="1"[^>]* checked')
        # hide: kept, with the Hidden tag and a Show button; its column leaves the Roster
        headers, _ = self.post(f"{role_href(rid)}/hide", {})
        gone_to(self, headers, SETUP, "setup-roles")
        self.assertEqual(flash_of(headers), "RO-6 Greeters is hidden now. Its history is kept.")
        self.assertEqual(roster.get_role(self.db(), rid)["active"], 0)
        row = self.role_row(rid)
        self.assertIn('<span class="tag">Hidden</span>', row[0])
        self.assertIn(f'action="{role_href(rid)}/show"', row[6])
        self.assertIn('<p class="sub">Thursday · A Person · Hidden</p>', self.page(role_href(rid)))
        self.assertNotIn("RO-6 Greeters", self.page("/calendar/roster"))
        headers, _ = self.post(f"{role_href(rid)}/show", {})
        self.assertEqual(flash_of(headers), "RO-6 Greeters is shown again.")
        self.assertEqual(roster.get_role(self.db(), rid)["active"], 1)
        self.assertIn('<th scope="col" lang="vi">RO-6 Greeters</th>', self.page("/calendar/roster"))

    def test_a_bad_role_form_saves_nothing(self):
        before = self.role_rows()
        cases = [  # (form, the field that shows the sentence, the sentence)
            ({"name": ""}, "name", "Service role name is required."),
            ({"name": "bồi LINH"}, "name", "There is already a Service role named “bồi LINH”. Choose another name."),
            ({"weekday": "7"}, "weekday", "The day of the week must be one from Monday to Sunday."),
            ({"done_by": "robot"}, "done_by", "A Service role is done by a Person or by a Ministry."),
            ({"every": "9"}, "every", "A Service role comes every 1 to 8 Services: use a whole number from 1 to 8."),
            ({"every": ""}, "every", "A Service role comes every 1 to 8 Services: use a whole number from 1 to 8."),
            ({"month_start_from": "2026-13"}, "month_start_from", "Month must be written YYYY-MM, for example 2026-11."),
            ({"month_start": "maybe"}, "month_start", "The first Service of a month starts a round must be on or off."),
        ]
        for change, field, words in cases:
            _h, page = self.add_role(expect=400, **{"name": "RO-6 Bad", **change})
            box = section(page, "setup-roles")
            self.assertIn(f'<p class="error" id="add-role-{field}-error">{words}</p>', box, change)
            self.assertRegex(box, rf'id="add-role-{field}"[^>]*aria-invalid="true"')
        self.assertEqual(self.role_rows(), before)
        _h, page = self.add_role(expect=400, name="RO-6 Kept", weekday="3", every="9")
        box = section(page, "setup-roles")  # the form keeps what was typed
        self.assertIn('value="RO-6 Kept"', box)
        self.assertRegex(box, r'<option value="3" selected>Thursday</option>')
        self.assertEqual(self.role_rows(), before)

    def test_the_weekday_stays_once_on_the_roster_and_done_by_never_changes(self):
        leader = self.by_name["Service leader"]  # the fake church has it on the Roster
        self.assertTrue(roster.role_has_links(self.db(), leader))
        box = section(self.page(role_href(leader)), "role-edit")
        self.assertNotIn('name="weekday"', box)  # shown as text, with the reason
        self.assertIn("<dt>Day of the week</dt><dd>Sunday</dd>", box)
        self.assertIn("This Service role is on the Roster already, so its day of the week cannot change.", box)
        self.assertNotIn('name="done_by"', box)  # chosen once, when the role was added
        self.assertIn("<dt>Done by</dt><dd>A Person</dd>", box)
        self.assertIn("Chosen once, when the Service role is added: it cannot change later.", box)
        before = self.role_rows()
        form = {"name": "Service leader", "every": "1", "month_start": "1", "month_start_from": ""}
        _h, page = self.post(role_href(leader), {**form, "weekday": "3"}, expect=400)
        self.assertIn('<p class="error" role="alert">The Service role “Service leader” is on the Roster already, so its '
                      "day of the week cannot change. Add a new Service role instead.</p>", section(page, "role-edit"))
        for change, field, words in (({"every": "0"}, "every", "A Service role comes every 1 to 8 Services"),
                                     ({"name": " "}, "name", "Service role name is required."),
                                     ({"name": "Bồi linh"}, "name", "There is already a Service role named “Bồi linh”"),
                                     ({"month_start_from": "1899-12"}, "month_start_from",
                                      "Month: use a year from 1900 to 9999.")):
            _h, page = self.post(role_href(leader), {**form, **change}, expect=400)
            self.assertIn(f'<p class="error" id="edit-role-{field}-error">{words}', section(page, "role-edit"), change)
            self.assertIn(f'value="{change.get("name", "Service leader")}"', section(page, "role-edit"))
        self.assertEqual(self.role_rows(), before)
        headers, _ = self.post(role_href(leader), {**form, "done_by": "ministry"})  # not a field here: ignored
        self.assertEqual(flash_of(headers), "Saved the Service role Service leader.")
        self.assertEqual(self.role_rows(), before)
        # a role with no link yet has the weekday select
        rid = self.new_role("RO-6 New")
        self.assertFalse(roster.role_has_links(self.db(), rid))
        self.assertIn('name="weekday"', section(self.page(role_href(rid)), "role-edit"))

    def test_rotation_add_move_up_and_down_take_out_and_a_repeat_refused(self):
        rid = self.new_role("RO-6 Readers")
        url = role_href(rid)
        self.assertIn("No one in the Rotation yet. Auto-fill skips this Service role.", section(self.page(url), "rotation"))
        a, b, c = (p["id"] for p in self.persons[30:33])
        for pid, place in ((a, 1), (b, 2), (c, 3)):
            headers, _ = self.post(f"{url}/rotation/add", {"person_id": pid})
            gone_to(self, headers, url, "rotation")
            self.assertEqual(flash_of(headers), f"Added {self.names[pid]} at place {place} of the Rotation.")
        self.assertEqual(self.rotation(rid), [a, b, c])
        rows = list_rows(section(self.page(url), "rotation"))
        self.assertEqual([plain(r[0]) for r in rows], [f"{k}. {self.names[p]}" for k, p in ((1, a), (2, b), (3, c))])
        self.assertEqual(rows[0][1], "")  # the first place has no Move up
        self.assertIn(f'action="{url}/rotation/up"', rows[1][1])
        self.assertIn(f'aria-label="Move {self.names[b]} up">Move up</button>', rows[1][1])
        self.assertEqual(rows[2][2], "")  # the last place has no Move down
        self.assertIn(f'<input type="hidden" name="person_id" value="{c}">', rows[2][3])
        self.assertIn(">Take out</button>", rows[2][3])
        self.assertEqual(self.role_row(rid)[5], "3 People")
        headers, _ = self.post(f"{url}/rotation/up", {"person_id": c})
        self.assertEqual(flash_of(headers), f"Moved {self.names[c]} to place 2.")
        self.assertEqual(self.rotation(rid), [a, c, b])
        headers, _ = self.post(f"{url}/rotation/down", {"person_id": a})
        self.assertEqual(flash_of(headers), f"Moved {self.names[a]} to place 2.")
        self.assertEqual(self.rotation(rid), [c, a, b])
        headers, _ = self.post(f"{url}/rotation/remove", {"person_id": a})
        self.assertEqual(flash_of(headers), f"Took {self.names[a]} out of the Rotation.")
        self.assertEqual(self.rotation(rid), [c, b])
        headers, _ = self.post(f"{url}/rotation/up", {"person_id": c})  # the first one up
        self.assertEqual(flash_of(headers), "The Rotation did not change.")
        # refused, nothing changes: a repeat, no choice, an unknown Person, one not in the Rotation
        for path, form, field_error, words in (
                ("add", {"person_id": b}, True, "Rotation: each Person or Ministry has one place only."),
                ("add", {"person_id": ""}, True, "Person: choose a Person."),
                ("add", {"person_id": "999999"}, True, "No Person with id 999999."),
                ("up", {"person_id": a}, False, "This Person or Ministry is not in the Rotation."),
                ("remove", {"person_id": a}, False, "This Person or Ministry is not in the Rotation."),
                ("down", {}, False, "Person: choose a Person.")):
            _h, page = self.post(f"{url}/rotation/{path}", form, expect=400)
            box = section(page, "rotation")
            where = '<p class="error" id="rotation-add-error">' if field_error else '<p class="error" role="alert">'
            self.assertIn(where + words + "</p>", box, (path, form))
        self.assertEqual(self.rotation(rid), [c, b])
        # the select offers only the People not in the Rotation yet
        offered = option_values(section(self.page(url), "rotation"), "person_id")
        self.assertEqual(offered[0], "")
        self.assertNotIn(str(b), offered)
        self.assertIn(str(a), offered)

    def test_a_person_role_offers_people_and_a_ministry_role_offers_ministries(self):
        conn = self.db()
        leader, in_charge = self.by_name["Service leader"], self.by_name["Ministry in charge"]
        held = set(self.rotation(leader))
        box = section(self.page(role_href(leader)), "rotation")
        self.assertIn('<label for="rotation-add">Add a Person at the end</label>', box)
        self.assertEqual(option_values(box, "person_id"),
                         [""] + [str(p["id"]) for p in people.list_persons(conn) if p["id"] not in held])
        self.assertNotIn('name="ministry_id"', box)
        mheld = set(self.rotation(in_charge))
        box = section(self.page(role_href(in_charge)), "rotation")
        self.assertIn('<label for="rotation-add">Add a Ministry at the end</label>', box)
        self.assertIn("<th scope=\"col\">Ministry</th>", box)
        self.assertEqual(option_values(box, "ministry_id"),
                         [""] + [str(m["id"]) for m in lists.get_list(conn, "ministry") if m["id"] not in mheld])
        self.assertIn(">Youth</option>", box)
        self.assertNotIn('name="person_id"', box)
        self.assertEqual([plain(r[0]) for r in list_rows(box)],
                         [f"{k}. {name}" for k, name in enumerate(fake.ROSTER_MINISTRIES, start=1)])
        before = self.rotation(in_charge)
        for form, words in (({"person_id": self.persons[0]["id"]}, "Ministry: choose a Ministry."),
                            ({"ministry_id": "999999"}, "No Ministry with id 999999.")):
            _h, page = self.post(f"{role_href(in_charge)}/rotation/add", form, expect=400)
            self.assertIn(f'<p class="error" id="rotation-add-error">{words}</p>', section(page, "rotation"))
        self.assertEqual(self.rotation(in_charge), before)
        youth = lists.find_item(conn, "ministry", name="Youth")["id"]
        headers, _ = self.post(f"{role_href(in_charge)}/rotation/add", {"ministry_id": youth})
        self.assertEqual(flash_of(headers), f"Added Youth at place {len(before) + 1} of the Rotation.")
        self.assertEqual(self.rotation(in_charge), before + [youth])
        self.post(f"{role_href(in_charge)}/rotation/remove", {"ministry_id": youth})
        self.assertEqual(self.rotation(in_charge), before)

    def test_skipped_date_add_replace_the_reason_and_remove(self):
        iso = dt.date(TODAY.year + 1, 2, 17).isoformat()
        day = shown(iso)
        weekday = dt.date.fromisoformat(iso).strftime("%A")

        def add(reason, expect=303):
            got, page = self.post("/calendar/roster/skipped/add", {"date": iso, "reason": reason}, expect=expect)
            if expect == 303:
                gone_to(self, got, SETUP, "skipped-dates")
            return got, page

        got, _ = add("RO-6 Nghỉ Tết")
        self.assertEqual(flash_of(got), f"Added the Skipped date {day}: RO-6 Nghỉ Tết.")
        self.assertEqual(roster.skipped_reason(self.db(), iso), "RO-6 Nghỉ Tết")
        box = section(self.page(SETUP), "skipped-dates")
        self.assertEqual(headers(box), ["Date", "Reason", ""])
        row = next(r for r in list_rows(box) if day in r[0])
        self.assertEqual(row[:2], [f'<span class="num">{weekday} {day}</span>', '<span lang="vi">RO-6 Nghỉ Tết</span>'])
        self.assertIn(f'aria-label="Remove the Skipped date {day}">Remove</button>', row[2])
        got, _ = add("RO-6 Hội đồng bồi linh")
        self.assertEqual(flash_of(got), f"{day} was a Skipped date already. Its new reason: RO-6 Hội đồng bồi linh.")
        self.assertEqual(roster.skipped_reason(self.db(), iso), "RO-6 Hội đồng bồi linh")
        got, _ = add("RO-6 Hội đồng bồi linh")
        self.assertEqual(flash_of(got), f"{day} is a Skipped date with this reason already. Nothing changed.")
        # refused, nothing saved: no reason, a date that is not real
        count = len(roster.skipped_dates(self.db(), "1900-01-01", "9999-12-31"))
        _h, page = add("  ", expect=400)
        self.assertIn('<p class="error" id="add-skipped-reason-error">Reason is required.</p>', section(page, "skipped-dates"))
        _h, page = self.post("/calendar/roster/skipped/add", {"date": "2027-02-30", "reason": "RO-6 x"}, expect=400)
        box = section(page, "skipped-dates")
        self.assertIn('<p class="error" id="add-skipped-date-error">Skipped date must be a real date written YYYY-MM-DD',
                      box)
        self.assertIn('value="RO-6 x"', box)  # what was typed stays
        self.assertEqual(len(roster.skipped_dates(self.db(), "1900-01-01", "9999-12-31")), count)
        self.assertEqual(roster.skipped_reason(self.db(), iso), "RO-6 Hội đồng bồi linh")
        # remove, then remove again
        got, _ = self.post("/calendar/roster/skipped/remove", {"date": iso})
        gone_to(self, got, SETUP, "skipped-dates")
        self.assertEqual(flash_of(got), f"Removed the Skipped date {day}.")
        self.assertIsNone(roster.skipped_reason(self.db(), iso))
        got, _ = self.post("/calendar/roster/skipped/remove", {"date": iso})
        self.assertEqual(flash_of(got), f"{day} is not a Skipped date. Nothing changed.")
        _h, page = self.post("/calendar/roster/skipped/remove", {"date": "nope"}, expect=400)
        self.assertIn('<p class="error" role="alert">Skipped date must be a real date', section(page, "skipped-dates"))
        self.assertEqual(len(roster.skipped_dates(self.db(), "1900-01-01", "9999-12-31")), count - 1)

    def test_the_skipped_dates_of_this_year_and_next_are_listed(self):
        conn = self.db()
        box = section(self.page(SETUP), "skipped-dates")
        self.assertIn(f"{TODAY.year} and {TODAY.year + 1}. Auto-fill gives these dates no Service role.", box)
        listed = [plain(r[0]).split()[-1] for r in list_rows(box)]
        rows = roster.skipped_dates(conn, f"{TODAY.year}-01-01", f"{TODAY.year + 1}-12-31")
        self.assertEqual(listed, [shown(r["date"]) for r in rows])
        self.assertIn(fake.ROSTER_SKIPPED, box)  # the fake church's Skipped date: a coming Sunday

    def test_the_same_person_rule_is_saved_and_read_back(self):
        self.assertEqual(roster.same_person_rule(self.db()), "service")
        box = section(self.page(SETUP), "same-person")
        self.assertIn("<legend>How many Service roles may one Person have?</legend>", box)
        self.assertEqual(re.findall(r'<input type="radio" id="rule-(\w+)" name="rule" value="(\w+)"', box),
                         [("service", "service"), ("week", "week"), ("any", "any")])
        self.assertRegex(box, r'value="service" [^>]* checked>')
        sentences = {"service": ("One Service role per Service", "A Person never has two Service roles in the same Service."),
                     "week": ("One Service role per week", "A Person has at most one Service role from Monday to Sunday."),
                     "any": ("No limit", "A Person may have many Service roles, even in the same Service.")}
        for rule, (label, hint) in sentences.items():
            self.assertIn(f'<label for="rule-{rule}">{label}</label><p class="hint" id="rule-{rule}-hint">{hint}</p>', box)
        for rule in ("week", "any", "service"):
            headers, _ = self.post("/calendar/roster/rule", {"rule": rule})
            gone_to(self, headers, SETUP, "same-person")
            self.assertEqual(flash_of(headers), f"Saved the same-person rule: {sentences[rule][0]}.")
            self.assertEqual(roster.same_person_rule(self.db()), rule)
            self.assertRegex(section(self.page(SETUP), "same-person"), rf'value="{rule}" [^>]* checked>')
        for form in ({"rule": "nope"}, {}):
            _h, page = self.post("/calendar/roster/rule", form, expect=400)
            self.assertIn('<p class="error" role="alert">The same-person rule must be one of: one Service role per Service, '
                          "one Service role per week, no limit.</p>", section(page, "same-person"))
        self.assertEqual(roster.same_person_rule(self.db()), "service")

    def test_the_roster_links_to_its_setup_and_an_unknown_role_is_not_found(self):
        self.assertIn(f'<a class="btn secondary" href="{SETUP}">Setup</a>', self.page("/calendar/roster"))
        status, _h, page = self.get_text(role_href(999999))
        self.assertEqual(status, 404)
        self.assertIn("There is no Service role with this number.", page)
        before = self.role_rows()
        for path in ("", "/hide", "/show", "/rotation/add", "/rotation/up", "/rotation/down", "/rotation/remove"):
            status, _h, _data = self.request("POST", role_href(999999) + path, {"person_id": "1"})
            self.assertEqual(status, 404, path)
        self.assertEqual(self.role_rows(), before)

    def test_no_private_note_text_on_the_setup_pages(self):
        conn = self.db()
        notes = [r[0] for r in conn.execute("SELECT body FROM private_note")]
        self.assertTrue(notes)
        pid = conn.execute("SELECT id FROM person WHERE full_name = ?", (fake.FIRST_PERSON,)).fetchone()[0]
        rid = self.new_role("RO-6 Private")
        self.post(f"{role_href(rid)}/rotation/add", {"person_id": pid})  # a Person with a Private note
        pages = [self.page(SETUP), self.page(role_href(rid)), self.page(role_href(self.by_name["Service leader"]))]
        self.assertIn(fake.FIRST_PERSON, pages[1])
        for page in pages:
            self.assertNotIn(fake.MARKER, page)
            for body in notes:
                self.assertNotIn(body, page)


class VietnameseRosterSetupTest(LiveServer, unittest.TestCase):
    """The setup pages on a Tiếng Việt fake church: no English left, also on a refused form and in a flash."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        root = pathlib.Path(cls.tmp.name)
        assert "onedrive" not in str(root.resolve()).lower()
        cls.copy = root / "fake"
        fake.build_fake_church(cls.copy, people=20, lang="vi")
        cls.start(cls.copy, root, remember=False)

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.tmp.cleanup()

    def setUp(self):
        self.conn = db.connect(self.copy / db.DB_NAME)
        self.addCleanup(self.conn.close)

    def assert_vietnamese(self, page):
        self.assertIn('<html lang="vi">', page)
        self.assertEqual(english_left(page), [])

    def post(self, path, form, expect):
        status, headers, data = self.request("POST", path, form)
        self.assertEqual(status, expect, data.decode("utf-8")[:1500])
        return headers, data.decode("utf-8")

    def test_the_setup_pages_in_vietnamese(self):
        roles = roster.roles(self.conn)
        for path in [SETUP] + [role_href(r["id"]) for r in roles]:
            status, _h, page = self.get_text(path)
            self.assertEqual(status, 200, path)
            self.assert_vietnamese(page)
        _s, _h, page = self.get_text(SETUP)
        for words in (">Thiết lập Lịch phân công</h1>", ">Phần vụ</h2>", ">Quy tắc trùng người</h2>",
                      ">Ngày nghỉ phân công</h2>", "<legend>Thêm một Phần vụ</legend>",
                      '<label for="rule-service">Một Phần vụ mỗi Giờ thờ phượng</label>', "Chúa Nhật", "Một Ban ngành",
                      "2 Giờ thờ phượng một lần", "Vòng mới mỗi đầu tháng"):
            self.assertIn(words, page)
        _s, _h, page = self.get_text("/calendar/roster")
        self.assertIn(f'<a class="btn secondary" href="{SETUP}">Thiết lập</a>', page)
        leader = next(r for r in roles if r["name"] == "Hướng dẫn chương trình")
        _s, _h, page = self.get_text(role_href(leader["id"]))
        self.assertIn(">Thứ tự luân phiên</h2>", page)
        self.assertIn(">Chỉnh sửa Phần vụ</h2>", page)
        self.assertIn("Phần vụ này đã có trong Lịch phân công, nên không đổi được ngày trong tuần.", page)

    def test_refusals_and_a_flash_in_vietnamese(self):
        leader = next(r for r in roster.roles(self.conn) if r["name"] == "Bồi linh")
        held = roster.rotation(self.conn, leader["id"])[0]["person_id"]
        cases = (("/calendar/roster/roles/add", {"name": "", "weekday": "6", "done_by": "person", "every": "1"},
                  "Cần nhập Tên Phần vụ."),
                 (f"{role_href(leader['id'])}/rotation/add", {"person_id": held},
                  "Thứ tự luân phiên: mỗi Người hoặc Ban ngành chỉ có một chỗ."),
                 ("/calendar/roster/rule", {"rule": "nope"}, "Quy tắc trùng người phải là một trong"),
                 ("/calendar/roster/skipped/add", {"date": "2027-02-17", "reason": ""}, "Cần nhập Lý do."))
        for path, form, words in cases:
            _h, page = self.post(path, form, 400)
            self.assert_vietnamese(page)
            self.assertIn(words, page)
        headers, _ = self.post("/calendar/roster/rule", {"rule": "week"}, 303)
        self.assertEqual(flash_of(headers), "Đã lưu quy tắc trùng người: Một Phần vụ mỗi tuần.")
        _s, _h, page = self.get_text(headers["location"])
        self.assert_vietnamese(page)
        self.post("/calendar/roster/rule", {"rule": "service"}, 303)


if __name__ == "__main__":
    unittest.main()
