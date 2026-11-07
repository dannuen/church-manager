# Feature Specification: Add People From an Excel File

**Feature Branch**: `main` (no branch hook; spec folder `specs/001-people-excel-import`)

**Created**: 2026-11-07

**Status**: Draft

**Input**: User description: "Add an option to quickly add people by having an excel with the right format"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Add many people from one filled-in Excel file (Priority: P1)

The pastor has a list of people (for example from an old paper book or an old spreadsheet). On the
People page he opens "Add from Excel file". He picks a filled-in Excel file. The app reads every
row and shows a check page: each row with its values and either "OK" or a clear sentence that says
what to fix. Nothing is saved yet. When every row is OK, he presses Save, and all the people are
added at once. When one or more rows have a problem, he cannot save; he fixes the file and picks it
again.

**Why this priority**: This is the whole value: many Persons in a few minutes, not one form per
Person.

**Independent Test**: In a fake church, pick a file with 30 good rows, see 30 OK rows, press Save,
and see 30 new Persons in People with the right Status.

**Acceptance Scenarios**:

1. **Given** a file with 30 good rows, **When** the pastor picks it, **Then** the check page lists
   30 rows marked OK and the People count has not changed.
2. **Given** the check page with all rows OK, **When** the pastor presses Save, **Then** 30 Persons
   are added, each with the Status from the file starting on the date from the file (today if
   empty), and the app says "30 people added".
3. **Given** a file where row 7 has no full name and row 12 has the birth date "31/02/1990",
   **When** the pastor picks it, **Then** the check page marks row 7 and row 12 with a sentence
   that names the column and the problem, and Save is not possible.
4. **Given** a file where a Status is not in the Status list (for example "Tin huu" with a typo),
   **When** the pastor picks it, **Then** that row says the Status is not in the list and shows
   the allowed names.
5. **Given** the check page, **When** the pastor presses Cancel, **Then** nothing is saved.

---

### User Story 2 - Get an empty Excel file in the right format (Priority: P2)

The pastor does not know the right columns. On the "Add from Excel file" page he presses "Get the
empty Excel file". He gets an Excel file with the right column titles in the current screen
language, and a help sheet with one example row and a short help line for each column (which columns are
required, the date form, the allowed Status names and genders).

**Why this priority**: Without the right format, Story 1 fails for most first tries. But Story 1
still works alone if the pastor follows the format written on the page.

**Independent Test**: Get the empty file, type 3 people into it in Excel, pick it in Story 1, and
all 3 rows are OK.

**Acceptance Scenarios**:

1. **Given** the screen language is Vietnamese, **When** the pastor gets the empty file, **Then**
   the column titles are in Vietnamese and the allowed Status names match the current Status list.
2. **Given** the pastor gets the file, fills rows and picks it again without changing the titles,
   **When** the app reads it, **Then** every column is understood.

---

### User Story 3 - Put the new people in Families (Priority: P3)

The pastor's list groups people by Family. In the file he types a Family name and a Family role
(Head, Spouse, Child, Other) on each row. When the name matches a Family already in the church
copy, the Person joins it. When the name is new, the app makes one new Family for all rows with
that name, and the check page says "new Family". The Family link starts on the row's start date.

**Why this priority**: It saves a second round of work (open each Person, set Family). Stories 1
and 2 still work without it: rows with an empty Family name add Persons with no Family.

**Independent Test**: In a fake church, pick a file with 4 rows named "Gia đình Nguyễn Văn A"
(new) and 2 rows named an existing Family. After Save there is 1 new Family with 4 members, and the
existing Family has 2 more members with the right Family roles.

**Acceptance Scenarios**:

1. **Given** a row with Family name "Gia đình Trần" that does not exist, **When** the file is
   checked, **Then** the row says it will make a new Family, and after Save that Family exists once,
   even if 5 rows name it.
2. **Given** a row with an existing Family name typed without diacritics, **When** the file is
   checked, **Then** the row is matched to that Family.
3. **Given** a row with a Family name but no Family role, **When** the file is checked, **Then**
   the row is an error: "Family role is needed when Family is set."
4. **Given** two Families in the church copy with the same name, **When** a row names it, **Then**
   the row is an error that says to set the Family on the Person page instead.
5. **Given** a new Family named in the file, **When** it is saved, **Then** its address is the
   first non-empty Address among its rows.

---

### Edge Cases

- The file is not an Excel file, is an old-style `.xls`, is empty, or has no title row: the app says
  so in one sentence and shows the "Get the empty Excel file" button.
- The column titles are in the other language (an English file while the screen is Vietnamese):
  the app still understands them.
- A column title is unknown or missing: unknown columns are named and ignored; a missing required
  column (Full name) stops the file with a clear sentence.
- Empty rows between people are skipped, not errors.
- A date typed as an Excel date, as `dd/mm/yyyy` or as `yyyy-mm-dd`: all are read as the same day.
  A birth date or start date in the future is refused (same rule as the Add a Person form).
- A phone number that Excel shows as a number (leading 0 lost, like 912345678): the app keeps it as
  text and does not change digits. [Assumption: no auto-fix of a lost leading 0.]
- Names typed without NFC or with extra spaces: saved cleaned, the same as the Add a Person form.
- Two rows in the file with the same full name, or a row with the same name as a Person already in
  the church copy (compared without diacritics): the row shows a warning ("A Person with this name
  is already in the church" / "Same name as row 9"), but Save is still possible, because two
  people can have the same name.
- Every row of a file with 2 or more rows has the name of a Person already in the church (for example
  Back after Save sends the file again): the check page says the file may have been saved before, and
  Save adds the rows only when the pastor ticks "Add them again anyway" (Save checks this again).
- A very large file (for example 2,000 rows): it is read; the check page stays usable.
- The file has a column called "Private note" or similar: it is ignored. Private notes are never
  added from a file.
- The app is stopped between the check page and Save: nothing was saved; the pastor picks the file
  again.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The People page MUST have an "Add from Excel file" action next to "Add".
- **FR-002**: The pastor MUST be able to pick one Excel file (`.xlsx`) from the computer.
- **FR-003**: The app MUST read these columns: Full name (required), Gender, Birth date, Phone,
  Address, Note, Status, Start date, Family, Family role. Each value follows the same rules as the Add a Person
  form; the same rule code MUST be used, not a copy.
- **FR-004**: Column titles MUST be accepted in Vietnamese and in English, with or without
  diacritics and in any letter case.
- **FR-005**: Gender MUST accept the words shown on screen in both languages (for example Nam / Nữ,
  Male / Female) and the short form (M / F).
- **FR-006**: Status MUST match a name in the current Status list, in either language, with or
  without diacritics.
- **FR-007**: Before saving, the app MUST show a check page with every row, its values and either
  OK or a sentence that names the row number, the column and what to fix.
- **FR-008**: The app MUST save nothing until the pastor presses Save on a check page where every
  row is OK.
- **FR-009**: Save MUST be all-or-nothing: either every row becomes a Person or none does.
- **FR-010**: The app MUST tell the pastor how many people were added and link to the People list.
- **FR-011**: The app MUST offer an empty Excel file with the right column titles in the current
  screen language, and a second help sheet with a help line per column and one example row. The
  example is not on the people sheet, so it is never added by mistake.
- **FR-012**: Each new Person's Status MUST be saved as a Status link with a start date (Start
  date, or today if empty), like the Add a Person form.
- **FR-013**: The feature MUST work with no Internet and MUST NOT keep a copy of the picked file in
  the church copy.
- **FR-014**: Every word on screen MUST exist in both Vietnamese and English and MUST follow
  `GLOSSARY.md`. The idea "a file with many people to add" MUST get a glossary entry before code.
  Proposed: **People file** / _Tệp danh sách người_. The words "upload", "attachment", "tải lên",
  "tệp đính kèm" MUST NOT be used.
- **FR-015**: The Hermes door MAY get the same action later; it is not part of this feature.
- **FR-016**: A row with a Family name MUST also have a Family role. The Family name MUST match an
  existing Family by name (without diacritics, any case); a name with no match MUST make exactly
  one new Family per distinct name in the file; a name that matches two or more Families MUST be a
  row error. The Family link MUST start on the row's Start date (today if empty). A new Family's
  address MUST be the first non-empty Address among its rows.
- **FR-017**: A row whose full name matches a Person already in the church copy, or another row in
  the file (without diacritics, any case), MUST show a warning on the check page. A warning MUST
  NOT stop Save. Only errors stop Save.
- **FR-018**: The Family role column MUST accept the screen words in both languages (for example
  Chủ gia đình / Head) and MUST refuse other values.

### Key Entities

- **People file**: An Excel file the pastor fills in. One title row, then one row per Person. It is
  read once and not kept.
- **Row check**: For each row: row number, the values read, and OK or a list of problems (column +
  sentence). Lives only on the check page.
- **Person** (existing): full name, gender, birth date, phone, address, note.
- **Status link** (existing): Person, Status, start date; end date empty.
- **Family** (existing): name, address. New ones may be made by the file.
- **Family link** (existing): Person, Family, Family role, start date; end date empty.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The pastor adds 50 people from a filled-in file in under 3 minutes (pick file, check,
  Save), against about 50 separate forms today.
- **SC-002**: A file filled from the empty file, with no typing mistakes, has 100% of rows OK on the
  first pick.
- **SC-003**: For every bad row, the sentence names the row and the column, and the pastor can fix
  it without help.
- **SC-004**: A file with any error row adds 0 people and 0 Families. A file with only good rows adds exactly as many
  Persons as it has rows.
- **SC-005**: A 2,000-row file shows its check page in under 10 seconds on the pastor's computer.

## Assumptions

- Only `.xlsx` (Excel 2007 and later, also made by free office programs) is read. Old `.xls` files
  get a sentence: "Open it in Excel and save it as .xlsx." CSV is not needed.
- Only the first sheet of the file is read.
- Chi phái (also of new Families), Trưởng Chi phái, Ministry and Private notes are not set from the file. The pastor sets
  them on each Person page.
- The file only adds new Persons (and new Families). It never changes or deletes a Person or a
  Family already in the church copy; joining an existing Family adds a link only.
- The pastor is the only user; no permission rules are needed.
- Dates are read as `dd/mm/yyyy` (Vietnamese habit), `yyyy-mm-dd`, or an Excel date cell.
