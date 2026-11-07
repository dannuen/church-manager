---

description: "Task list for Add People From an Excel File"
---

# Tasks: Add People From an Excel File

**Input**: Design documents from `specs/001-people-excel-import/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/routes.md,
contracts/people-file.md, quickstart.md

**Tests**: Included. Constitution VII ("Each change MUST come with tests") and quickstart.md
require them. Write each test first and see it fail.

**Organization**: Tasks are grouped by user story so each story can be built and checked alone.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no open dependency)
- **[Story]**: US1, US2, US3 from spec.md
- Paths are from the repo root `C:\Users\danng\OneDrive\Desktop\Church Manager Hermes`

## Rules for every task (from AGENTS.md and the constitution)

- Standard library only. No package. Python 3.14.
- Use `GLOSSARY.md` words. Never write "upload", "attachment", "import file", "tải lên",
  "tệp đính kèm", "Household", "hộ" in `churchmgr/*.py` or `tests/*.py`. Do not write the
  product name "Excel" in code or screen text; say ".xlsx file" / "tệp .xlsx".
- New screen words go in section `people` of `churchmgr/i18n.py`, in **both** `vi` and `en` dicts,
  directly after the `# --- people` line (MERGE RULE at the top of that file).
- Work only with a fake church in a temp folder: `python -m churchmgr.fake "$LOCALAPPDATA/Temp/cm-people-file"`.
  Never open a real church copy. Never edit `church.db` by hand.
- Do not commit unless the pastor asks.

---

## Phase 1: Setup

**Purpose**: The new word and empty files.

- [X] T001 Add a glossary entry under `## People` in `GLOSSARY.md`, after **Private note**: `**People file**:` "A .xlsx file with one row per new Person, used to add many people at once. Read once, never kept." `_Tiếng Việt_: Tệp danh sách người`, `_Tránh (tiếng Việt)_: tải lên, tệp đính kèm`, `_Avoid_: Upload, import file`. Also add a row `| People file | Tệp danh sách người |` under `**Other words**` in the screen words table.
- [X] T002 [P] Create `churchmgr/xlsx.py` with a module docstring only ("Read the first sheet of a .xlsx file and write a simple .xlsx, standard library only. Knows nothing about people.").
- [X] T003 [P] Create `churchmgr/pages/people_file.py` with a module docstring, `from ..server import Response` style imports copied from `churchmgr/pages/people.py`, and `ROUTES = []`.
- [X] T004 Register the module: in `churchmgr/pages/__init__.py` import `people_file` and append it to `PAGES` right after `people` (one line, keep the card comments style).
- [X] T005 [P] Create `tests/test_people_file.py` with `import _support` (puts repo root on `sys.path`), `import unittest`, and an empty `class XlsxTest(unittest.TestCase)` and `class PeopleFileTest(_support.CopyTestCase)`.

---

## Phase 2: Foundational (blocks all stories)

**Purpose**: Read and write `.xlsx` (research R1, R2, R6, R8), and the column map. US1 needs the
reader; US2 needs the writer; tests of US1 build their files with the writer.

**⚠️ No user story work starts before this phase is done.**

### Tests first

- [X] T006 [P] In `tests/test_people_file.py` class `XlsxTest`: round trip `xlsx.read_first_sheet(xlsx.write([("People", rows), ("Help", rows2)]))` returns only sheet 1 rows; text with Vietnamese diacritics comes back NFC; empty middle cells come back as `None` in the right column; a fully empty row is kept as an all-`None` row (the caller skips it).
- [X] T007 [P] In `XlsxTest`: hand-build a small zip (with `zipfile`) that uses `xl/sharedStrings.xml` with a rich-text `<si><r><t>Nguyễn </t></r><r><t>Văn A</t></r></si>`, a `t="inlineStr"` cell, a `t="str"` cell, a number cell `912345678` and a number cell `29221`, cells placed by `r="C7"` with a skipped row; assert the values and positions. Add a case with `<workbookPr date1904="1"/>` and assert `read_first_sheet(...).date1904 is True` (or the returned flag chosen in T009).
- [X] T008 [P] In `XlsxTest`: `read_first_sheet(b"not a zip")`, a zip with no `xl/workbook.xml`, bad XML, a sheet member over the size limit, and a file with 5,001 data rows each raise `text.TextError` (a `ValueError`) with the key `people.file_err_not_xlsx`, `people.file_err_too_big` or `people.file_err_too_many_rows`.

### Implementation

- [X] T009 Implement `read_first_sheet(data: bytes)` in `churchmgr/xlsx.py` per research R1: `zipfile.ZipFile(io.BytesIO(data))`; `xl/workbook.xml` → first `<sheet>` `r:id` → target in `xl/_rels/workbook.xml.rels` → sheet XML; optional `xl/sharedStrings.xml` (join every `<t>` in each `<si>`); cell types `s`, `inlineStr`, `str`, `b`, number (→ `float`); position from `r` attribute (`"C7"` → row 7, col 3). Return a small result: rows `list[list[str|float|None]]` and `date1904: bool` (from `workbookPr`). Text is NFC (`text.nfc`). Limits from R8: input over 10 MB, any member `file_size` over 50 MB, more than 5,001 rows (title + 5,000) → `TextError`. Catch `zipfile.BadZipFile`, `KeyError`, `ElementTree.ParseError` → `TextError("people.file_err_not_xlsx")`. Make T006–T008 pass.
- [X] T010 Implement `write(sheets, text_columns=True)` in `churchmgr/xlsx.py` per research R6: `sheets` is `[(sheet_name, rows)]`; write `[Content_Types].xml`, `_rels/.rels`, `xl/workbook.xml`, `xl/_rels/workbook.xml.rels`, `xl/styles.xml` with one Text cell format (`numFmtId="49"`), and `xl/worksheets/sheetN.xml` with inline-string cells; columns of sheet 1 get the Text style so typed phones and dates stay as typed. Escape XML with `xml.sax.saxutils.escape`. Return `bytes`. Make T006 pass.
- [X] T011 Add a helper `cell_date(value, date1904)` in `churchmgr/xlsx.py` per research R2: a number → `datetime.date(1899, 12, 30) + timedelta(days=int(value))` (or `date(1904, 1, 1)` base when `date1904`); text `dd/mm/yyyy`, `d/m/yyyy` or `yyyy-mm-dd` → `YYYY-MM-DD`; anything else → `None` (the caller makes the row error). And `cell_text(value)`: `float` with no fraction → `str(int(value))`, other values → `str` stripped, `None` → `""`. Add tests for both in `XlsxTest` (serial `29221` → `1980-01-01`; `"31/12/1980"`; `"1980-12-31"`; `"31/02/1990"` → `None`; `912345678.0` → `"912345678"`).
- [X] T012 In `churchmgr/i18n.py` section `people` (vi and en): add the column title keys `people.file_col_full_name`, `..._gender`, `..._birth_date`, `..._phone`, `..._address`, `..._note`, `..._status`, `..._start_date`, `..._family`, `..._family_role` with the words in `contracts/people-file.md` (vi: Họ và tên, Giới tính, Ngày sinh, Điện thoại, Địa chỉ, Ghi chú, Trạng thái, Ngày bắt đầu, Gia đình, Vai trò trong gia đình; en: Full name, Gender, Birth date, Phone, Address, Note, Status, Start date, Family, Family role), and the error keys `people.file_err_not_xlsx` ("This is not a .xlsx file. Open it and save it as .xlsx." / vi), `people.file_err_too_big`, `people.file_err_too_many_rows` ("More than 5,000 people rows. Split the file."), `people.file_err_empty`, `people.file_err_no_name_column`. Run `python -m unittest discover -s tests -p test_i18n.py` (both dicts must have the same keys).
- [X] T013 In `churchmgr/pages/people_file.py` add `COLUMNS = ("full_name", "gender", "birth_date", "phone", "address", "note", "status", "start_date", "family", "family_role")` and `map_titles(title_row)` → `(index_by_key, ignored_titles)`: a title matches a key when `text.fold(title)` equals `text.fold` of `i18n.TEXT[lang][f"people.file_col_{key}"]` for **either** `lang`, or the key itself. Missing `full_name` → `TextError("people.file_err_no_name_column")`. Add a test in `PeopleFileTest` with Vietnamese titles typed without diacritics ("Ho va ten", "ngay sinh") and an unknown title ("Ghi chú cá nhân") that lands in `ignored_titles`.

**Checkpoint**: `python -m unittest discover -s tests -p test_people_file.py` passes.

---

## Phase 3: User Story 1 - Add many people from one file (Priority: P1) 🎯 MVP

**Goal**: Pick a `.xlsx` file, see a check page, Save adds all rows at once (FR-001…FR-010,
FR-012, FR-013, FR-017).

**Independent Test**: In a fake church, pick a file with 30 good rows, see 30 OK rows, Save, and
see 30 new Persons in People with the right Status (quickstart scenarios 3–9 without Family).

### Tests for User Story 1 (write first, see them fail)

- [X] T014 [P] [US1] In `PeopleFileTest` (`tests/test_people_file.py`): `check_people_file(conn, data)` on a file of 3 good rows returns 3 row checks with no `errors`; Gender "Nữ", "male", "M" all read; Status "Tín hữu" typed as "tin huu" and the English word "Member" both match the Status item (`self.status("Member")`); dates `31/12/1980` and serial `29221` read; empty rows are skipped; person count is unchanged (nothing saved).
- [X] T015 [P] [US1] In `PeopleFileTest`: row errors, each naming its row number and column: empty full name; gender "X"; birth date `31/02/1990`; birth date tomorrow; Status not in the list; Start date in the future.
- [X] T016 [P] [US1] In `PeopleFileTest`: warnings, not errors: a full name equal (folded) to a Person already added with `people.add_person`; two rows with the same name ("Same name as row N"). Assert `errors == []` for those rows.
- [X] T017 [P] [US1] In `PeopleFileTest`: `save_people_file(conn, rows_json)` with 3 good rows adds 3 Persons and 3 Status links with the Start date (today when empty); returns the count. All-or-nothing: rows JSON where row 3 has a bad birth date → raises / returns errors, and `SELECT COUNT(*) FROM person` and `FROM person_status` are unchanged. Assert `SELECT COUNT(*) FROM private_note` is unchanged after a save.
- [X] T018 [P] [US1] In `PeopleFileTest` (or a class using `LiveServer` from `tests/test_server.py`, like `tests/test_pages_people.py`): GET `/people` has a link to `/people/file`; GET `/people/file` returns 200 with a file field named `file` and a `multipart/form-data` form; POST `/people/file` with a good file returns 200 with a Save form posting to `/people/file/save`; POST with `b"not a zip"` returns 400 with the not-xlsx sentence; POST `/people/file/save` with good rows redirects (303) to `/people` and the message names the count; a file with an error row shows no Save button.

### Implementation for User Story 1

- [X] T019 [US1] In `churchmgr/i18n.py` section `people` (vi and en) add the page words: `people.file_add` ("Thêm từ tệp .xlsx" / "Add from .xlsx file"), `people.file_title`, `people.file_pick`, `people.file_check` (button), `people.file_help` (one paragraph naming the required column and the date form), `people.file_summary` ("{rows} rows: {ok} OK, {bad} with errors, {warn} warnings"), `people.file_ok`, `people.file_fix_rows` ("Fix these rows in the file, then pick it again."), `people.file_ignored` ("Ignored columns: {names}"), `people.file_added` ("{n} people added"), `people.file_warn_same_church` ("A Person with this name is already in the church"), `people.file_warn_same_row` ("Same name as row {row}"), `people.file_err_row` ("Row {row}, {column}: {problem}"), `people.file_err_date` ("write the date as 31/12/1980"), `people.file_err_status` ("not in the Status list ({names})").
- [X] T020 [US1] In `churchmgr/pages/people_file.py` implement `check_people_file(conn, data)` → `(checks, ignored_titles)`: `xlsx.read_first_sheet` → `map_titles` → for each non-empty row build a row check per `data-model.md` ("Row check": `row`, `values`, `status_id`, `errors`, `warnings`). Load once per call: active Status items (`lists.get_list(conn, "status")`, match `text.fold` of `name`, of `code`, and of each language's screen word) and the set of `person.name_folded`. Per row: run the rules **by calling the existing functions**, not copies — `text.clean_name` for full name; gender: map the screen words (`people.male`/`people.female` in both languages) to `M`/`F`, then `people._gender` for the check; `xlsx.cell_date` then `people_pages.past_or_today` for `birth_date` and `start_date` (empty Start date stays empty). Catch each `ValueError` as one `(column, sentence)` error. Same-name checks → warnings (FR-017). Make T014–T016 pass.
- [X] T021 [US1] In `churchmgr/pages/people_file.py` implement `save_people_file(conn, rows_json)`: `json.loads` the hidden field (bad JSON → `TextError("people.file_err_not_xlsx")`), **run the same row checks again** on the values (research R3), and if any row has errors return them without writing. Else inside one `with db.transaction(conn):` call `people_pages.add_person_from_form(conn, form)` per row, where `form` is a plain dict with `full_name, gender, birth_date, phone, address, note, status_id, start_date`. Return the number added. Make T017 pass.
- [X] T022 [US1] In `churchmgr/pages/people_file.py` add the pages per `contracts/routes.md`: `pick_page(req)` (GET `/people/file`: `ui.form("/people/file", ..., multipart=True)` with `ui.field(t("people.file_pick"), "file", "", type="file", accept=".xlsx")`, `ui.button(t("people.file_check"))`, the help text); `check_post(req)` (POST `/people/file`: `req.files.get("file")`, missing → 400 pick page with sentence; `ValueError` → 400 pick page with `str(exc)`; else 200 check page: summary line, table with `ui`'s table helper as in `churchmgr/pages/people.py` (`table(headers, rows)`), ignored titles line, and either a Save form (`ui.form("/people/file/save", hidden rows + ui.button(t("core.btn_save")))` plus Cancel link to `/people/file`) or `people.file_fix_rows` + the pick form); `save_post(req)` (POST `/people/file/save`: errors → 400 check page; else `Response.redirect(ui.url("/people", msg=t("people.file_added", n=n)))`). Escape every value with `h(...)`. Fill `ROUTES` with the three routes. Make T018 pass (except the empty-file link).
- [X] T023 [US1] In `churchmgr/pages/people.py` `list_page` (around line 293, `actions = ui.link_button(t("people.add"), "/people/new", "primary")`) add `+ ui.link_button(t("people.file_add"), "/people/file")` (secondary). One line.

**Checkpoint**: US1 works alone. Run `python -m unittest discover -s tests -p test_people_file.py` and `-p test_pages_people.py`. MVP can stop here.

---

## Phase 4: User Story 2 - Get an empty file in the right format (Priority: P2)

**Goal**: A button gives an empty `.xlsx` with titles in the screen language and a help sheet
with one example row (FR-011, research R6).

**Independent Test**: Get the empty file, add 3 rows to sheet 1 (in a test: with `xlsx.read_first_sheet` + `xlsx.write`), pick it, all 3 rows OK (quickstart scenarios 1–2).

### Tests for User Story 2

- [X] T024 [P] [US2] In `tests/test_people_file.py`: `empty_file(conn, "vi")` sheet 1 row 1 equals the 10 Vietnamese titles in `COLUMNS` order and has no other rows; with `"en"` the English titles; the second sheet exists (read it with `zipfile` + the sheet2 member) and names every active Status item. Round trip: append 3 good rows to sheet 1, write again, `check_people_file` → 3 rows, no errors. _(Note: until story 3 the file had the 8 columns that were read (research R6); since T031 it has all 10.)_
- [X] T025 [P] [US2] Server test: GET `/people/file/empty.xlsx` returns 200, content type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, a `Content-Disposition` download name, and bytes that `xlsx.read_first_sheet` reads.

### Implementation for User Story 2

- [X] T026 [US2] In `churchmgr/i18n.py` section `people` (vi and en): `people.file_empty` ("Lấy tệp mẫu trống" / "Get the empty file"), `people.file_sheet_people` ("Mọi người" / "People"), `people.file_sheet_help` ("Hướng dẫn" / "Help"), `people.file_download_name` ("Tep danh sach nguoi.xlsx" / "People file.xlsx"), and one help line per column `people.file_help_<key>` (required or not, accepted words, date form "31/12/1980", "Family role is needed when Family is set").
- [X] T027 [US2] In `churchmgr/pages/people_file.py` implement `empty_file(conn, lang)` → `bytes` with `xlsx.write([(sheet_people, [titles]), (sheet_help, help_rows)])`; help rows = one line per column + the current active Status names + one example row (example only on the help sheet). Add `empty_get(req)` returning `Response(body=..., content_type=..., headers={"Content-Disposition": content_disposition(name)})` (use `server.content_disposition`), and the route `("GET", "/people/file/empty.xlsx", empty_get)`. Add the link `ui.link_button(t("people.file_empty"), "/people/file/empty.xlsx")` on the pick page and on the not-xlsx error page. Make T024–T025 pass.

**Checkpoint**: US1 and US2 both work.

---

## Phase 5: User Story 3 - Put the new people in Families (Priority: P3)

**Goal**: Columns Family and Family role link rows to an existing Family or make one new Family
per new name (FR-016, FR-018, research R4/R5).

**Independent Test**: Fake church, file with 4 rows naming one new Family and 2 rows naming an
existing Family → after Save 1 new Family with 4 members, and the existing Family has 2 more, with
the right Family roles (quickstart scenario 4).

### Tests for User Story 3

- [X] T028 [P] [US3] In `PeopleFileTest`: 4 rows with Family "Gia đình Trần" (new) → each row check says new Family, after save exactly 1 Family with that name and 4 open `family_link` rows; its address = first non-empty Address among those rows. 2 rows with an existing Family typed without diacritics → joined, roles "Con" and "Spouse" stored as `Child` and `Spouse`.
- [X] T029 [P] [US3] In `PeopleFileTest`: row errors — Family set but Family role empty ("Family role is needed when Family is set"); Family role "Ông" (unknown); a Family name that matches two Families made with `people.add_family` (error says to set it on the Person page). All-or-nothing: a Family error on row 5 → save writes 0 Persons and 0 Families.

### Implementation for User Story 3

- [X] T030 [US3] In `churchmgr/i18n.py` section `people` (vi and en): `people.file_new_family` ("Gia đình mới" / "new Family"), `people.file_err_family_role_needed`, `people.file_err_family_role`, `people.file_err_family_two` ("Two Families have this name. Set the Family on the Person page.").
- [X] T031 [US3] In `check_people_file` (`churchmgr/pages/people_file.py`): load Families once (`SELECT id, name_folded FROM family`); per row with `family`: folded match count 0 → `new_family` = cleaned name (one per folded name in the file), 1 → `family_id`, 2+ → error; `family_role` must map (by `text.fold` of the codes `Head, Spouse, Child, Other` and the `core.family_role_*` words of both languages) to a code in `schema.FAMILY_ROLES`, else error; Family set + role empty → error. Show Family, "new Family" and role in the check table.
- [X] T032 [US3] In `save_people_file`, inside the same transaction: for each distinct `new_family` call `people.add_family(conn, name, address)` once (address = first non-empty Address of its rows), then for each row with a Family call `people_pages.set_family_from_form(conn, pid, {"family_id": fid, "family_role": code, "start_date": start})`. Add "{m} new Families" to the redirect message (`people.file_added_families`, vi and en). Make T028–T029 pass.

**Checkpoint**: all three stories work.

---

## Phase 6: Polish & cross-cutting

- [X] T033 [P] Update `hermes/skills/church-manager/SKILL.md` with one line: adding many people from a `.xlsx` file is a page in the app (People > Add from .xlsx file), not a Hermes door command (FR-015).
- [X] T034 [P] Add a short section to `README.md` (Vietnamese, like the rest): how to get the empty file, fill it, pick it, check and Save.
- [X] T035 Run `python -m unittest discover -s tests -p test_db.py` (Avoid words), `-p test_i18n.py` (both languages have the same keys) and `-p test_people_file.py`; fix any hit.
- [X] T036 Run the quickstart scenarios 1–9 by hand on a fake church (`specs/001-people-excel-import/quickstart.md`), including a file saved from a real spreadsheet program, and check SC-005 (2,000 rows → check page in under 10 s).
- [X] T037 Run `python verify.py`; it must exit 0 and print `ALL ... CHECKS PASS`.

---

## Dependencies & Execution Order

- **Phase 1 (T001–T005)** → **Phase 2 (T006–T013)** → stories.
- **US1 (T014–T023)** needs Phase 2 only. It is the MVP.
- **US2 (T024–T027)** needs Phase 2 (`xlsx.write`) and `check_people_file` from T020 for its round-trip test; the page link needs T022.
- **US3 (T028–T032)** extends `check_people_file` and `save_people_file` from US1, so it comes after T020–T021.
- **Polish (T033–T037)** after the stories you ship.
- Inside a story: tests → i18n words → logic → pages.

Shared-file warning: T012, T019, T026, T030 all edit `churchmgr/i18n.py`, and T020/T021/T022/T027/T031/T032 all edit `churchmgr/pages/people_file.py`. Do not run those in parallel with each other.

## Parallel Examples

```text
# Phase 1
T002 churchmgr/xlsx.py   |  T003 churchmgr/pages/people_file.py  |  T005 tests/test_people_file.py

# Phase 2 tests (one file, but separate test methods; write together, then run)
T006, T007, T008

# US1 tests, written together before T019–T023
T014, T015, T016, T017, T018

# After US1: US2 and the Polish docs can go side by side
T024–T027 (US2)  |  T033 SKILL.md  |  T034 README.md
```

## Implementation Strategy

1. **MVP**: Phase 1 + Phase 2 + US1. The pastor can add people from a file he makes by following
   the help text on the pick page. Stop, check with quickstart, show the pastor.
2. **+US2**: the empty file makes the first try right (SC-002).
3. **+US3**: Families from the file.
4. Polish, then `python verify.py` must pass before the feature is done.
