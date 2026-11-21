"""Card RO-4 (decision D6): the Service roles panel of a Service page, through the real server (port 0, a
fake church in a temp folder): pick, swap and clear a Service role with its history kept (rule 4), the
same-person warning, refusals that save nothing, the Skipped date reason, hidden Service roles, the confirm
step on a past Service, no Private note text, and the panel in Tiếng Việt with no English left."""

import datetime as dt
import pathlib
import re
import tempfile
import unittest
import urllib.parse

import _support  # noqa: F401 - puts the repo root on sys.path
from churchmgr import calendar as cal
from churchmgr import db, fake, lists, people, roster
from churchmgr.i18n import english_left
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


if __name__ == "__main__":
    unittest.main()
