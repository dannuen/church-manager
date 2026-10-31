"""Fake church: a made-up church copy with real-looking data for every dashboard panel.

    python -m churchmgr.fake <folder> [--people 50] [--seed 1] [--today YYYY-MM-DD]

The same seed and the same today give the same data (only clock stamps such as
``created_at`` and the random file names of Documents differ). It uses only
the public data-layer functions. A OneDrive folder or a folder that already
has ``church.db`` is refused.
"""

import argparse
import datetime as _dt
import random
import shutil
import sys

from . import calendar, care, db, documents, lists, money, paths, sent, text
from . import people as people_data
from .db import transaction

FIRST_PERSON = "Nguyễn Hải Đăng"
CHURCH_NAME = "Hội Thánh Tin Lành Bình An"
MARKER = "PRIVATE-NOTE-MARKER-"
MIN_PEOPLE, MAX_PEOPLE = 20, 1000  # fewer than 20 cannot fill 3 Chi phái and every panel

SURNAMES = ("Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng",
            "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý")
MALE_MIDDLE = ("Văn", "Hữu", "Minh", "Quang", "Đức", "Thanh", "Công", "Gia")
FEMALE_MIDDLE = ("Thị", "Ngọc", "Thu", "Thanh", "Mỹ", "Kim", "Bảo")
MALE_GIVEN = ("An", "Bình", "Cường", "Dũng", "Hiếu", "Hùng", "Khoa", "Long", "Nam", "Phúc",
              "Quân", "Sơn", "Tuấn", "Thắng", "Vinh", "Đức", "Huy", "Lộc")
FEMALE_GIVEN = ("Hà", "Hạnh", "Hoa", "Hương", "Lan", "Linh", "Mai", "Ngọc", "Thảo", "Trang",
                "Uyên", "Vy", "Yến", "Nhung", "Phương", "Ánh")
STREETS = ("Lê Lợi", "Trần Hưng Đạo", "Nguyễn Trãi", "Hai Bà Trưng", "Phan Đình Phùng",
           "Lý Thường Kiệt", "Quang Trung", "Võ Thị Sáu")
WARDS = ("Phường 1", "Phường 4", "Phường 7", "Phường 9")
CHI_PHAI_NAMES = ("Chi phái Hòa Bình", "Chi phái Phước Thành", "Chi phái Đông Hải")
AMOUNTS = (50_000, 100_000, 200_000, 300_000, 500_000, 1_000_000, 2_000_000)
CARE_NOTES = ("Thăm hỏi sức khỏe, cầu nguyện chung.", "Chia sẻ Lời Chúa với cả nhà.",
              "Động viên sau khi nằm viện.", "Mừng em bé mới sinh.", "Hỏi thăm việc làm mới.",
              "Cầu nguyện cho kỳ thi của các con.")
PRIVATE_TEXTS = ("Cần cầu nguyện cho hôn nhân.", "Đang gặp khó khăn tài chính, cần nâng đỡ.",
                 "Đã nói chuyện riêng về con cái.", "Xin cầu thay cho bệnh tình của mẹ.",
                 "Muốn chịu báp-têm trong năm tới.", "Đang cố bỏ thuốc lá.")


class _Fake:
    """Builds the fake church step by step on one open connection."""

    def __init__(self, conn, folder, rng, today, n_people):
        self.conn, self.folder, self.rng, self.today, self.n = conn, folder, rng, today, n_people
        self.used_names = {FIRST_PERSON}
        self.status = {code: lists.find_item(conn, "status", code=code)["id"]
                       for code in ("member", "attender", "visitor", "left", "passed_away")}
        self.counts = {}

    # ---- small helpers
    def ago(self, days):
        return (self.today - _dt.timedelta(days=days)).isoformat()

    def ahead(self, days):
        return (self.today + _dt.timedelta(days=days)).isoformat()

    def item(self, list_name, name):
        return lists.find_item(self.conn, list_name, name=name)["id"]

    def add_count(self, key, k=1):
        self.counts[key] = self.counts.get(key, 0) + k

    def name(self, surname, gender):
        rng = self.rng
        full = ""
        for _ in range(60):
            middle = rng.choice(MALE_MIDDLE if gender == "M" else FEMALE_MIDDLE)
            given = rng.choice(MALE_GIVEN if gender == "M" else FEMALE_GIVEN)
            full = f"{surname} {middle} {given}"
            if full not in self.used_names:
                break
        self.used_names.add(full)
        return full

    def birth(self, age):
        return _dt.date(self.today.year - age, self.rng.randint(1, 12), self.rng.randint(1, 28))

    def address(self):
        return f"{self.rng.randint(1, 199)} {self.rng.choice(STREETS)}, {self.rng.choice(WARDS)}, Đà Lạt"

    def phone(self):
        return f"09{self.rng.randrange(10_000_000, 100_000_000)}"

    def person(self, full_name, gender, birth, address=None):
        pid = people_data.add_person(self.conn, full_name, gender=gender, birth_date=birth.isoformat(),
                                     phone=self.phone(), address=address)
        self.people.append({"id": pid, "name": full_name, "gender": gender, "birth": birth})
        return pid

    # ---- steps
    def run(self):
        self.people = []
        self.make_families()
        self.make_statuses()
        self.make_chi_phai()
        self.make_ministries()
        self.make_calendar()
        self.make_visits()
        self.make_money()
        self.make_documents_and_sent()
        self.make_private_notes()
        return self.counts

    def make_families(self):
        rng, n = self.rng, self.n
        n_families = max(3, round(n / 4.2))  # 50 people -> 12 Families
        regular = n_families - 1  # the last Family is made later, when a Person moves
        in_families = round(n * 0.8)
        sizes = [2] * regular
        sizes[1] = 3  # Family 1 has a grown-up child who moves out
        left = in_families - sum(sizes)
        while left > 0:
            i = rng.randrange(regular)
            if sizes[i] < 6:
                sizes[i] += 1
                left -= 1
        self.families = []
        for i, size in enumerate(sizes):
            surname = "Nguyễn" if i == 0 else rng.choice(SURNAMES)
            founded = self.today - _dt.timedelta(days=rng.randint(365 * 4, 365 * 15))
            head_age = rng.randint(38, 66)
            head_name = FIRST_PERSON if i == 0 else self.name(surname, "M")
            fid = people_data.add_family(self.conn, f"Gia đình {head_name}", address=self.address())
            fam = {"id": fid, "name": f"Gia đình {head_name}", "founded": founded, "members": []}
            self.families.append(fam)
            members = [(head_name, "M", self.birth(head_age), "Head")]
            spouse_surname = rng.choice(SURNAMES)
            members.append((self.name(spouse_surname, "F"), "F", self.birth(head_age - rng.randint(0, 5)), "Spouse"))
            for k in range(size - 2):
                if size >= 5 and k == size - 3:
                    members.append((self.name(surname, "F"), "F", self.birth(rng.randint(72, 88)), "Other"))
                    continue
                gender = rng.choice("MF")
                age = 26 if (i == 1 and k == 0) else rng.randint(1, max(1, head_age - 22))
                members.append((self.name(surname, gender), gender, self.birth(age), "Child"))
            for full, gender, birth, role in members:
                pid = self.person(full, gender, birth)
                start = max(founded, birth)
                people_data.set_family(self.conn, pid, fid, role, start.isoformat())
                fam["members"].append({"id": pid, "role": role, "start": start})
        member_ids = {m["id"] for f in self.families for m in f["members"]}
        self.singles = []
        n_singles = n - len(member_ids)
        for k in range(n_singles):
            gender = rng.choice("MF")
            age = rng.randint(62, 75) if k == n_singles - 1 else rng.randint(19, 60)
            pid = self.person(self.name(rng.choice(SURNAMES), gender), gender, self.birth(age), self.address())
            self.singles.append(pid)
        # A grown-up child of Family 1 marries one single Person and they start a new Family.
        self.move_date = self.ago(100)
        mover = self.families[1]["members"][2]["id"]
        spouse = self.singles[0]
        mover_name = next(p["name"] for p in self.people if p["id"] == mover)
        fid = people_data.add_family(self.conn, f"Gia đình {mover_name}", address=self.address())
        people_data.set_family(self.conn, mover, fid, "Head", self.move_date)
        people_data.set_family(self.conn, spouse, fid, "Spouse", self.move_date)
        self.families.append({"id": fid, "name": f"Gia đình {mover_name}",
                              "founded": _dt.date.fromisoformat(self.move_date),
                              "members": [{"id": mover, "role": "Head"}, {"id": spouse, "role": "Spouse"}]})
        self.mover = mover
        self.add_count("persons", len(self.people))
        self.add_count("families", len(self.families))

    def make_statuses(self):
        rng, st = self.rng, self.status
        ids = [p["id"] for p in self.people]
        first = ids[0]
        heads = {f["members"][0]["id"] for f in self.families}  # heads (and Trưởng Chi phái) stay Members
        others = [pid for pid in ids if pid not in heads]
        rng.shuffle(others)
        n_left = max(1, self.n // 16)
        groups = {
            "left": others[:n_left],
            "passed_away": others[n_left:n_left + 1],
            "visitor": others[n_left + 1:n_left + 1 + self.n // 10],
            "attender": others[n_left + 1 + self.n // 10:n_left + 1 + 2 * (self.n // 10)],
        }
        special = {pid for group in groups.values() for pid in group}
        members = [first] + [pid for pid in ids if pid != first and pid not in special]
        self.inactive = set(groups["left"]) | set(groups["passed_away"])
        changed = 0
        for pid in members:
            if pid == first or rng.random() < 0.25:  # visitor -> attender -> member
                start = rng.randint(1500, 3000)
                people_data.set_status(self.conn, pid, st["visitor"], self.ago(start))
                people_data.set_status(self.conn, pid, st["attender"], self.ago(start - 200))
                people_data.set_status(self.conn, pid, st["member"], self.ago(start - 500))
                changed += 1
            else:
                people_data.set_status(self.conn, pid, st["member"], self.ago(rng.randint(400, 4000)))
        for code in ("left", "passed_away"):
            for pid in groups[code]:
                people_data.set_status(self.conn, pid, st["member"], self.ago(rng.randint(900, 3000)))
                people_data.set_status(self.conn, pid, st[code], self.ago(rng.randint(30, 700)))
                changed += 1
        for code in ("visitor", "attender"):
            for pid in groups[code]:
                people_data.set_status(self.conn, pid, st[code], self.ago(rng.randint(10, 300)))
        self.active = [pid for pid in ids if pid not in self.inactive]
        self.add_count("status_changes", changed)

    def make_chi_phai(self):
        cps = [people_data.add_chi_phai(self.conn, name) for name in CHI_PHAI_NAMES]
        regular = self.families[:-1]
        moved = len(regular) - 1  # this Family changes Chi phái
        for i, fam in enumerate(regular):
            people_data.set_family_chi_phai(self.conn, fam["id"], cps[i % 3], fam["founded"].isoformat())
        people_data.set_family_chi_phai(self.conn, regular[moved]["id"], cps[(moved + 1) % 3], self.ago(200))
        people_data.set_family_chi_phai(self.conn, self.families[-1]["id"], cps[0], self.move_date)
        for j, cid in enumerate(cps):
            fams = [f for i, f in enumerate(regular) if i % 3 == j and i != moved]
            head = fams[0]["members"][0]["id"]
            if j == 0:  # one past Trưởng Chi phái
                people_data.set_truong_chi_phai(self.conn, cid, self.singles[-1], self.ago(2200))
                people_data.set_truong_chi_phai(self.conn, cid, head, self.ago(500))
            else:
                people_data.set_truong_chi_phai(self.conn, cid, head, self.ago(self.rng.randint(600, 1800)))
        self.chi_phai = cps
        self.add_count("chi_phai", len(cps))

    def make_ministries(self):
        rng = self.rng
        worship, youth, children = (self.item("ministry", n) for n in ("Worship", "Youth", "Children"))
        active = set(self.active)
        by_age = sorted((p for p in self.people if p["id"] in active), key=lambda p: p["birth"])
        adults = [p["id"] for p in by_age if (self.today - p["birth"]).days > 25 * 365]
        young = [p["id"] for p in by_age if 15 * 365 < (self.today - p["birth"]).days <= 30 * 365]
        first = self.people[0]["id"]
        pool = [pid for pid in adults if pid != first]
        rng.shuffle(pool)
        team_worship = [first] + pool[:5]
        # Worship: Nguyễn Hải Đăng led, then handed over to another Person 300 days ago.
        people_data.set_ministry(self.conn, team_worship[0], worship, "Leader", self.ago(1500))
        people_data.set_ministry(self.conn, team_worship[1], worship, "Member", self.ago(1200))
        people_data.set_ministry(self.conn, team_worship[0], worship, "Member", self.ago(300))
        people_data.set_ministry(self.conn, team_worship[1], worship, "Leader", self.ago(300))
        for pid in team_worship[2:]:
            people_data.set_ministry(self.conn, pid, worship, "Member", self.ago(rng.randint(100, 1000)))
        young_pool = [pid for pid in young if pid not in team_worship] or pool[5:10]
        group_youth = young_pool[:5]
        for k, pid in enumerate(group_youth):
            people_data.set_ministry(self.conn, pid, youth, "Leader" if k == 0 else "Member",
                                     self.ago(rng.randint(200, 900)))
        if len(group_youth) > 2:  # one stopped serving
            people_data.set_ministry(self.conn, group_youth[-1], youth, None, self.ago(90))
        group_children = [pid for pid in pool[5:] if pid not in group_youth][:4]
        for k, pid in enumerate(group_children):
            people_data.set_ministry(self.conn, pid, children, "Leader" if k == 0 else "Member",
                                     self.ago(rng.randint(200, 1500)))
        self.worship_team = team_worship
        self.add_count("ministry_people", len(team_worship) + len(group_youth) + len(group_children))

    def make_calendar(self):
        rng, conn, today = self.rng, self.conn, self.today
        back = (today.weekday() + 1) % 7 or 7  # last Sunday before today
        last_sunday = today - _dt.timedelta(days=back)
        first = last_sunday - _dt.timedelta(weeks=11)
        until = last_sunday + _dt.timedelta(weeks=4)
        ids = calendar.add_calendar_item(conn, "Service", "Thờ phượng Chúa Nhật", f"{first} 08:00",
                                         ends_at=f"{first} 10:00", place="Nhà thờ", repeat="weekly",
                                         repeat_until=until.isoformat())
        self.services = ids
        self.sundays = [first + _dt.timedelta(weeks=k) for k in range(len(ids))]
        notes = (None, None, "Mưa lớn, nhiều gia đình vắng.", "Một số em đi trại.", None)
        for k, iid in enumerate(ids):
            serving = rng.sample(self.worship_team, 2)
            for pid in serving:
                calendar.add_person_to_item(conn, iid, pid, "serves")
            for pid in rng.sample([p for p in self.active if p not in serving], 3):
                calendar.add_person_to_item(conn, iid, pid, "joins")
            if k < 12:
                calendar.set_head_count(conn, iid, rng.randint(55, 95), rng.choice(notes))
        self.add_count("head_counts", 12)
        meeting = calendar.add_calendar_item(conn, "Meeting", "Họp Ban Chấp Sự", f"{self.ahead(1)} 19:00",
                                             ends_at=f"{self.ahead(1)} 21:00", place="Phòng họp")[0]
        for pid in self.worship_team[:4]:
            calendar.add_person_to_item(conn, meeting, pid, "joins")
        self.event = calendar.add_calendar_item(conn, "Event", "Ngày Gia Đình Hội Thánh", f"{self.ahead(3)} 16:00",
                                                ends_at=f"{self.ahead(3)} 20:00", place="Sân nhà thờ",
                                                note="Mỗi gia đình mang một món ăn.")[0]
        calendar.add_person_to_item(conn, self.event, self.worship_team[1], "serves")
        start_month = today - _dt.timedelta(days=90)
        monthly = calendar.add_calendar_item(conn, "Meeting", "Họp Trưởng Chi phái", f"{start_month} 19:30",
                                             repeat="monthly", repeat_until=self.ahead(150))
        next_saturday = today + _dt.timedelta(days=(5 - today.weekday()) % 7)
        youth = calendar.add_calendar_item(conn, "Meeting", "Nhóm Thanh Niên", f"{next_saturday} 18:00",
                                           ends_at=f"{next_saturday} 20:00", repeat="weekly",
                                           repeat_until=(next_saturday + _dt.timedelta(weeks=7)).isoformat())
        past_event = calendar.add_calendar_item(conn, "Event", "Lễ Tạ Ơn", f"{self.ago(60)} 09:00",
                                                place="Nhà thờ")[0]
        for pid in rng.sample(self.active, 6):
            calendar.add_person_to_item(conn, past_event, pid, "joins")
        self.add_count("calendar_items", len(ids) + 2 + len(monthly) + len(youth) + 1)

    def make_visits(self):
        rng, conn = self.rng, self.conn
        people_pool = [pid for pid in self.active if pid != self.people[0]["id"]]
        rng.shuffle(people_pool)
        fams = list(self.families)
        rng.shuffle(fams)
        done = 0
        plan = [(rng.randint(5, 80), k) for k in range(7)] + [(rng.randint(120, 300), k) for k in range(7, 12)]
        for days, k in plan:
            day = self.ago(days)
            if k % 2 == 0:
                iid = care.plan_visit(conn, f"{day} 10:00", person_id=people_pool[k])
            else:
                iid = care.plan_visit(conn, f"{day} 15:00", family_id=fams[k % len(fams)]["id"])
            care.mark_visit_done(conn, iid, day, rng.choice(CARE_NOTES))
            done += 1
        care.plan_visit(conn, f"{self.ahead(2)} 10:00", family_id=fams[0]["id"], note="Thăm cả nhà.")
        care.plan_visit(conn, f"{self.ahead(5)} 15:00", person_id=self.people[0]["id"])
        self.add_count("visits_done", done)
        self.add_count("visits_planned", 2)

    def make_money(self):
        rng, conn, today = self.rng, self.conn, self.today
        general, building, missions = (self.item("fund", n) for n in ("General", "Building", "Missions"))
        funds = [general] * 7 + [building] * 2 + [missions]
        offerings = 0
        sundays = [today - _dt.timedelta(days=(today.weekday() + 1) % 7) - _dt.timedelta(weeks=k)
                   for k in range(26)]
        givers_f = [f["id"] for f in self.families]
        for sunday in sorted(sundays):
            day = sunday.isoformat()
            for fid in rng.sample(givers_f, min(4, len(givers_f))):
                money.add_offering(conn, day, rng.choice(AMOUNTS), rng.choice(funds), giver_family_id=fid)
                offerings += 1
            for pid in rng.sample(self.active, 2):
                money.add_offering(conn, day, rng.choice(AMOUNTS), rng.choice(funds), giver_person_id=pid)
                offerings += 1
            money.add_offering(conn, day, rng.choice(AMOUNTS) * 3, general, note="Hộp dâng hiến")
            offerings += 1
        # The Person who moved gave before and after the move (shows on two Family statements).
        before = (_dt.date.fromisoformat(self.move_date) - _dt.timedelta(days=20)).isoformat()
        money.add_offering(conn, before, 500_000, general, giver_person_id=self.mover)
        money.add_offering(conn, self.move_date, 700_000, building, giver_person_id=self.mover)
        money.add_offering(conn, today.isoformat(), 1_000_000, general, giver_family_id=self.families[0]["id"])
        offerings += 3
        rent, utilities, events = (self.item("spending_category", n) for n in ("Rent", "Utilities", "Events"))
        expenses = 0
        for back in range(6, -1, -1):
            month_first = calendar.add_months(today.replace(day=1), -back)
            money.add_expense(conn, month_first.isoformat(), 6_000_000, rent, note="Thuê hội trường")
            expenses += 1
            for day, amount, cat in ((10, 1_200_000 + rng.randrange(0, 50) * 10_000, utilities),
                                     (20, 2_500_000, events)):
                when = month_first.replace(day=day)
                if when <= today:
                    money.add_expense(conn, when.isoformat(), amount, cat)
                    expenses += 1
        self.add_count("offerings", offerings)
        self.add_count("expenses", expenses)

    def make_documents_and_sent(self):
        conn, today = self.conn, self.today
        first = self.people[0]["id"]
        documents.add_document(conn, self.folder,
                               f"Giấy chứng nhận Báp-têm\n{FIRST_PERSON}\n".encode("utf-8"),
                               f"Chứng nhận Báp-têm - {FIRST_PERSON}.txt", person_id=first)
        documents.add_document(conn, self.folder, "Chương trình:\n16:00 Trò chơi\n18:00 Ăn tối\n".encode("utf-8"),
                               "Chương trình Ngày Gia Đình.txt", calendar_item_id=self.event)
        sent_file = documents.add_document(conn, self.folder, "Kính mời quý Hội Thánh...\n".encode("utf-8"),
                                           "Giấy mời Lễ Cung Hiến.txt")
        self.add_count("documents", 3)
        r = {n: self.item("recipient", n) for n in ("Chính quyền", "Giáo hội", "Hội Thánh")}
        p = {n: self.item("purpose", n) for n in ("Invitation", "Notice", "Certificate", "Report")}
        last_year = today.year - 1
        sent.add_sent_document(conn, f"{last_year}-11-05", r["Giáo hội"], p["Report"], "Báo cáo tổng kết năm")
        sent.add_sent_document(conn, f"{last_year}-12-10", r["Chính quyền"], p["Notice"],
                               "Thông báo Lễ Giáng Sinh")
        jan1 = _dt.date(today.year, 1, 1)
        days = [max(jan1, today - _dt.timedelta(days=d)) for d in (120, 45, 7)]
        sent.add_sent_document(conn, days[0].isoformat(), r["Chính quyền"], p["Notice"], "Xin phép sinh hoạt")
        sent.add_sent_document(conn, days[1].isoformat(), r["Giáo hội"], p["Certificate"],
                               f"Chứng nhận tín hữu {FIRST_PERSON}")
        sent.add_sent_document(conn, days[2].isoformat(), r["Hội Thánh"], p["Invitation"], "Mời dự Lễ Cung Hiến",
                               document_id=sent_file)
        self.add_count("sent_documents", 5)

    def make_private_notes(self):
        targets = [self.people[0]["id"]] + self.rng.sample(self.active[1:], len(PRIVATE_TEXTS) - 1)
        for n, (pid, words) in enumerate(zip(targets, PRIVATE_TEXTS), start=1):
            people_data.add_private_note(self.conn, pid, f"{MARKER}{n}: {words}")
        self.add_count("private_notes", len(PRIVATE_TEXTS))


def _check_people(value):
    if isinstance(value, bool) or not isinstance(value, int) or not MIN_PEOPLE <= value <= MAX_PEOPLE:
        raise ValueError(f"people must be a whole number from {MIN_PEOPLE} to {MAX_PEOPLE}.")
    return value


def build_fake_church(folder, people=50, seed=1, today=None):
    """Make a new church copy in ``folder`` filled with a fake church. Returns a dict of counts.

    ``today`` (a date or ``YYYY-MM-DD``; default: today) is the day the data is built around.
    """
    n_people = _check_people(people)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be a whole number.")
    day = _dt.date.today() if today is None else _dt.date.fromisoformat(text.check_date(today, "Today"))
    target = paths.check_not_onedrive(folder)
    existed = target.exists()
    docs_existed = db.documents_folder(target).exists()
    conn = db.create_church_copy(target, CHURCH_NAME)
    ok = False
    try:
        with transaction(conn):
            counts = _Fake(conn, target, random.Random(seed), day, n_people).run()
        ok = True
    finally:
        conn.close()
        if not ok:  # leave nothing half made
            if not existed:
                shutil.rmtree(target, ignore_errors=True)
            else:
                (target / db.DB_NAME).unlink(missing_ok=True)
                if not docs_existed:
                    shutil.rmtree(db.documents_folder(target), ignore_errors=True)
    return {"folder": str(target), "church_name": CHURCH_NAME, "today": day.isoformat(), **counts}


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(prog="python -m churchmgr.fake",
                                     description="Make a fake church copy for tests and demos.")
    parser.add_argument("folder", help="new church copy folder (outside OneDrive)")
    parser.add_argument("--people", type=int, default=50, help="number of Persons (20 to 1000, default 50)")
    parser.add_argument("--seed", type=int, default=1, help="random seed (default 1)")
    parser.add_argument("--today", default=None, help="build around this date, YYYY-MM-DD (default today)")
    args = parser.parse_args(argv)
    try:
        counts = build_fake_church(args.folder, people=args.people, seed=args.seed, today=args.today)
    except (db.ChurchCopyError, paths.CopyPathError, ValueError) as exc:
        print(f"Not made: {exc}", file=sys.stderr)
        return 2
    print(f"Fake church made in {counts.pop('folder')}")
    for key, value in counts.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
