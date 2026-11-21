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


if __name__ == "__main__":
    unittest.main()
