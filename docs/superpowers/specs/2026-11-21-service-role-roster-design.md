## SHARED DECISIONS (goal t_de00e182 "Service role roster"; the orchestrator settled these; do not re-decide)

Read `GLOSSARY.md`, `IDEA.md` and `AGENTS.md` in the repo first. Use the glossary words exactly. Never use an Avoid word. Standard library only. Work only on a fake church in a temp folder OUTSIDE OneDrive (`python -m churchmgr.fake <folder>`). Never open the real church copy in `%LOCALAPPDATA%\ChurchManager\`. Never commit on `main`. Never push.

Pastor's sample (read it, do not copy it into the repo): `D:\Obsidian\dannuenobsidianvault\Church Roster\Lịch HDCT Năm 2026 - Tam Dân.md`. One row = one week: `Thursday | Bồi linh | Sunday | HDCT | Dâng hiến | Notes`. Struck names (`~~old~~ → new`) are swaps. Bold = the first Sunday of the month. `NGHỈ TẾT`, `HỘI ĐỒNG BỒI LINH`, `NHÓM BUỔI SÁNG VỚI TRƯỜNG XUÂN` are Skipped dates.

Branch `wt/roster`, worktree `C:\Users\danng\OneDrive\Desktop\Church Manager Hermes\.worktrees\roster`, base `main` at `99cac03`. Main has dirty files from another session (`AGENTS.md` modified, untracked `docs/GOAL-2.md`, `docs/superpowers/...`, `docs/vietnamese-words-*`): never change, stash or commit them; no card changes `AGENTS.md`.

### D1. New glossary words (Calendar section of GLOSSARY.md, after Head count). The Vietnamese words were PROPOSED; the pastor answered (card RO-ASK) and RO-7 applied the answers: Service role, Offering leader, Ministry in charge and Skipped date have new words; Roster, Rotation and Auto-fill keep the proposed ones. Use these words exactly.

| English | Tiếng Việt | Meaning | Avoid |
|---|---|---|---|
| Service role | Phân công | A task done in a Service by one Person (such as Bồi linh, Hướng dẫn chương trình, Offering leader) or by one Ministry (Ministry in charge). The list is editable. | Duty |
| Offering leader | Dâng hiến | The Service role of the person who leads the offering time. Not an Offering (money), not a Giver. On screen it has the same Vietnamese word as Offering (the pastor's choice); in code it stays the offering leader role. | |
| Ministry in charge | Ban ngành | The Service role done by a Ministry (such as Ban Trung niên, Ban Thanh tráng, Ban Tráng niên). The Roster shows it in the Notes column. On screen it has the same Vietnamese word as Ministry (the pastor's choice). | |
| Roster | Lịch phân công | The table of who does each Service role in each Service, one row per week, one table per month, one page per quarter. | Rota, duty list |
| Rotation | Thứ tự luân phiên | The fixed order of people (or Ministries) for one Service role. Auto-fill gives the next turn in this order, so each one gets an equal share. | Rota |
| Skipped date | Bỏ qua | A date auto-fill gives no Service role, such as Tết or a Sunday led by a guest group or the Hội đồng bồi linh. It has a reason the Roster shows. In a Vietnamese sentence it is "ngày Bỏ qua". | Holiday |
| Auto-fill | Tự động xếp lịch | Filling the empty Service roles of a date range from each Rotation. It never changes a Service role that already has a name. | |

Add `"rota", "duty", "holiday"` to `AVOID` in `tests/test_db.py` (CodeRulesTest). Add a "Words on screen" group "Service role (default list)" with the 4 defaults (D3). "Notes" on the Roster page is the plain column header "Ghi chú"/"Notes"; it is NOT a Private note and NOT the person `note`.

### D2. Schema version 2 (only new tables; old tables never change)
`schema.SCHEMA_VERSION = 2`, `schema.KNOWN_VERSIONS = (1, 2)`. New statements go in their own tuples (`TABLES_V2`, `INDEXES_V2`) added to `STATEMENTS` after the old ones. Names are fixed:

```
service_role (id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE CHECK (length(trim(name)) > 0),
  weekday INTEGER NOT NULL CHECK (typeof(weekday) = 'integer' AND weekday BETWEEN 0 AND 6),  -- Python date.weekday(): 0 Monday .. 3 Thursday .. 6 Sunday
  done_by TEXT NOT NULL CHECK (done_by IN ('person', 'ministry')),
  every INTEGER NOT NULL DEFAULT 1 CHECK (typeof(every) = 'integer' AND every BETWEEN 1 AND 8),  -- every Nth Service
  month_start INTEGER NOT NULL DEFAULT 0 CHECK (month_start IN (0, 1)),  -- the first Service of a month starts a round
  month_start_from TEXT CHECK (month_start_from IS NULL OR month_start_from GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),  -- the month Rotation place 1 starts
  sort_order INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)))
rotation_place (service_role_id INTEGER NOT NULL REFERENCES service_role (id),
  position INTEGER NOT NULL CHECK (typeof(position) = 'integer' AND position >= 1),
  person_id INTEGER REFERENCES person (id), ministry_id INTEGER REFERENCES list_item (id),
  CHECK ((person_id IS NULL) + (ministry_id IS NULL) = 1),
  PRIMARY KEY (service_role_id, position))
service_role_link: a HISTORY table (rule 4) made with `_history(...)`, columns
  calendar_item_id INTEGER NOT NULL REFERENCES calendar_item (id),
  service_role_id INTEGER NOT NULL REFERENCES service_role (id),
  person_id INTEGER REFERENCES person (id), ministry_id INTEGER REFERENCES list_item (id),
  + CHECK ((person_id IS NULL) + (ministry_id IS NULL) = 1) (add it inside the CREATE TABLE text)
skipped_date (date TEXT PRIMARY KEY CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  reason TEXT NOT NULL CHECK (length(trim(reason)) > 0))
```
Indexes: `UNIQUE INDEX service_role_link_one_open ON service_role_link (calendar_item_id, service_role_id) WHERE end_date IS NULL`, `INDEX service_role_link_item ON service_role_link (calendar_item_id)`, `INDEX service_role_link_person ON service_role_link (person_id)`.
Triggers: add `"service_role_link": ("calendar_item_id", "service_role_id", "person_id", "ministry_id")` to `HISTORY_TABLES` (never deleted, closed once). A `service_role_never_delete` trigger. A `service_role_keep_done_by` trigger (done_by never changes). New triggers that check `ministry_id` is an item of the `ministry` list must allow NULL (`NEW.ministry_id IS NOT NULL AND NOT EXISTS (...)`) and are written as NEW statements; the text of every OLD trigger stays byte-equal (do not change `LIST_COLUMNS`). `rotation_place` rows MAY be deleted and re-made (a Rotation is an order, not a past link). `skipped_date` rows may be removed.
Migration: `db.open_church_copy` on a version-1 copy runs, in ONE transaction: the V2 tables, indexes and triggers, the 4 default Service roles (names in the copy's `language` setting; no row = `vi`), `PRAGMA user_version = 2`. Version 2: as today. Any other version: the old `copy_version` error. `create_church_copy` makes version 2 with the defaults. `agent.connect_ro` and `handover._read_source` accept any version in `KNOWN_VERSIONS` (they only read old tables).

### D3. Default Service roles (New church setup and migration; `(vi name, en name, weekday, done_by, every, month_start)`)
1. `("Bồi linh", "Bồi linh", 3, "person", 1, 0)`
2. `("Hướng dẫn chương trình", "Service leader", 6, "person", 1, 1)` (month_start_from NULL)
3. `("Dâng hiến", "Offering leader", 6, "person", 1, 0)`
4. `("Ban ngành", "Ministry in charge", 6, "ministry", 2, 0)`
sort_order 1..4. Names are data: shown as stored, never translated.

### D4. Module `churchmgr/roster.py` (API names are fixed; later cards call them)
Errors are `TextError` with keys in the `calendar` section of `i18n.py` (prefix `calendar.roster_`), added in BOTH dicts directly after `# --- calendar` (MERGE RULE in i18n.py).
- Constants: `DONE_BY = ("person", "ministry")`, `SAME_PERSON_RULES = ("service", "week", "any")`, `SAME_PERSON_SETTING = "roster_same_person"`, `SAME_PERSON_DEFAULT = "service"` (the pastor's answer: two Service roles in one week are fine, never two in one day), `MAX_FILL_DAYS = 366`.
- Service roles: `add_role(conn, name, weekday, done_by, every=1, month_start=False, month_start_from=None) -> id`; `update_role(conn, role_id, *, name=_KEEP, weekday=_KEEP, every=_KEEP, month_start=_KEEP, month_start_from=_KEEP)` (done_by never changes; weekday may change only while the role has no `service_role_link` row); `set_role_active(conn, role_id, active)`; `get_role(conn, role_id)`; `roles(conn, include_hidden=False)` ordered by weekday, sort_order, id.
- Rotation: `rotation(conn, role_id)` -> rows `(position, person_id, ministry_id, name)` by position; `set_rotation(conn, role_id, ids)` replaces the whole order (person ids for a person role, ministry list ids for a ministry role; no repeats; an empty list is allowed).
- Skipped dates: `add_skipped_date(conn, date, reason)` (a date already there: new reason replaces), `remove_skipped_date(conn, date)`, `skipped_dates(conn, start, end)`, `skipped_reason(conn, date)` -> text or None.
- Links (rule 4, never overwrite): `set_link(conn, item_id, role_id, person_id=None, ministry_id=None, day=None) -> bool` closes the open link (end_date = day) and opens a new one (start_date = day); same value as the open link = no change, False. `day` defaults to today. Refused: item not a Service, role hidden, item weekday != role weekday, wrong kind of value for done_by, unknown person/ministry. `clear_link(conn, item_id, role_id, day=None) -> bool` closes the open link with no new one (the sample's lone `~~name~~`). `item_links(conn, item_id)` -> every row (open and closed) with role name and person/ministry name, by role order then id. `open_value(conn, item_id, role_id)`.
- Same-person rule: `same_person_rule(conn)` reads setting `roster_same_person` (missing/bad = `SAME_PERSON_DEFAULT`); `set_same_person_rule(conn, rule)`. `conflicts(conn, item_id, role_id, person_id, rule=None, extra=())` -> list of `(role name, date)` where that person holds ANOTHER person role: `service` = same Calendar item; `week` = any Service in the same ISO week (Monday to Sunday); `any` = none. `extra` = proposed `(item_id, role_id, person_id)` not saved yet. Only person roles take part.
- calendar.py: `delete_refusal_key` returns new key `calendar.err_kept_roster` when the item has any `service_role_link` row (checked AFTER the Head count check and BEFORE the Document check). `update_calendar_item` refuses a kind change away from Service when the item has a `service_role_link` row (new key `calendar.err_service_stays_roster`). Old keys and texts stay.

### D5. Auto-fill (`roster.fill_plan(conn, from_date, to_date)` and `roster.save_fill(conn, from_date, to_date, day=None) -> count`)
Range: from <= to, at most `MAX_FILL_DAYS` days. For each active role in `roles()` order that has a non-empty Rotation (n places):
1. `seq` = the role's Services: Calendar items of kind Service whose date has `weekday() == role.weekday`, date <= to, by starts_at then id, minus Services on a Skipped date.
2. every-step: `anchor` = index in seq of the LAST Service before `from` that has an open link for this role; none -> index of the first Service in the range. Step Services = indexes with `(i - anchor) % every == 0` and date in the range. Other Services are not touched.
3. queue = Rotation order. If a Service before `from` holds an open link of this role and the holder is in the Rotation, the queue starts right after the LAST such holder (rotate the list).
4. For each step Service s, in date order:
   - s has ANY link row of this role (open or closed): it is held; if its open holder is in the queue, move the holder to the end. Never change it.
   - else if `role.month_start` and s is the first step Service of its month: starter = `rotation[k % n]`, k = months from `month_start_from` (NULL = the month of `from`) to the month of s. Take the starter if the same-person rule allows him; else pick as below.
   - else pick the FIRST person in the queue who (a) is not reserved and (b) passes `conflicts()` with the rule of `same_person_rule(conn)` (saved links + proposals so far, all roles). Reserved (only when month_start) = the starters of month-first step Services among the next n-1 step Services after s. Nobody: ignore (a). Still nobody: no proposal, the slot is reported as "nobody free".
   - The picked one moves to the end of the queue.
5. Roles are planned in `roles()` order; proposals of earlier roles count in later conflict checks. Ministry roles: same steps, no conflict check, no month start unless set.
`fill_plan` returns `{"proposals": [(item_id, role_id, person_id, ministry_id)], "nobody_free": [(item_id, role_id)]}` and writes nothing. `save_fill` recomputes the plan and saves every proposal with `set_link` in ONE transaction.
Measured by the orchestrator (probe, rotation Huệ, Hiền, Tín, Tứ, Linh, Tài; Sundays of 2026 minus 29/03 and 08/11; month_start=1, month_start_from 2026-01): the 12 first Sundays get Huệ, Hiền, Tín, Tứ, Linh, Tài, Huệ, Hiền, Tín, Tứ, Linh, Tài; counts 9, 9, 8, 8, 8, 8; nobody twice in a row; 04/01-08/02 = Huệ, Tín, Tứ, Linh, Hiền, Tài (6 different). month_start=0: plain turn by turn, each window of 6 has 6 different people. These are test cases.

### D6. Pages (module `churchmgr/pages/roster.py`, added to `PAGES` in `churchmgr/pages/__init__.py`; keep edits to `pages/calendar.py` small)
- `GET /calendar/roster?quarter=YYYY-Q` (default: this quarter). h1 "Lịch phân công" / "Roster", sub "Quý q/yyyy". Prev/next quarter chips. One table per month ("Tháng m"). Row = one ISO week (Monday-Sunday); a week belongs to the month of its Sunday. Columns: for each weekday that has an active Service role, Monday->Sunday: a date column (header = the weekday name, e.g. "Thứ Năm", "Chúa Nhật"; cell `dd/mm` linked to `/calendar/<id>#service-roles`), then one column per PERSON role of that weekday (header = role name). Last column "Ghi chú"/"Notes" = the Ministry-in-charge values of that week. A cell shows the history like the sample: closed names struck (`<s>`), then ` → ` and the open name; a `title` with the dates. The value on the first Service of a month of a month_start role is bold. A Skipped date: the first role cell of that weekday shows the reason (bold), the other role cells of that Service are empty; a Skipped date with no Service still shows its date and reason. No Service and no Skipped date on that weekday: empty cells. Print button (print.css hides menus). Links: "Tự động xếp lịch" form, "Setup".
- `GET /calendar/roster/fill?from=YYYY-MM-DD&to=YYYY-MM-DD` (default: the shown quarter): preview of `fill_plan` in the same table look, new names marked, the "nobody free" list, and a Save form `POST /calendar/roster/fill` (from, to) -> `save_fill` -> redirect to the Roster with a "N filled" message. GET never writes.
- Service page `/calendar/<id>` (kind Service only): a panel with id `service-roles`: for each active role of that weekday (and any role that has a link on this item): open value, history with dates, a form `POST /calendar/<id>/roles` (role_id + person_id or ministry_id) and a remove button `POST /calendar/<id>/roles/clear` (role_id). After a save that breaks the same-person rule: saved, and the page shows a warning naming the other role. A Skipped date shows its reason in the panel.
- `GET /calendar/roster/setup`: Service roles (add / edit name, weekday, every, month start + month / hide-show), each role's Rotation (`GET /calendar/roster/roles/<id>`: ordered list, add a person or Ministry, move up/down, take out), Skipped dates (add date + reason, remove), the same-person rule (3 radio choices). All POST forms redirect back (POST-redirect-GET), refuse bad input with the page's error style.
- Every new page: both languages, no English left on a `vi` page (the existing `i18n.english_left` check), no Private note text anywhere, Calendar menu item active.

### D7. Hard rules for this goal
Rule 4: a `service_role_link` row is never updated except the one close of `end_date`, never deleted. Private notes: no roster page, form, preview or print shows `private_note` text; never join `private_note`. Money: untouched. Each coder card ends: run the touched test files, then the full suite (`python -m unittest discover -s tests`), then `python verify.py` (must print `ALL ... CHECKS PASS`), commit on `wt/roster`, and hand over by the separate reviewer card (call `kanban_complete` with metadata `{"commit": <hash>, "tests": "<N> OK", "verify": "ALL <N> CHECKS PASS"}`).
