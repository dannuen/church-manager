# Research: Add People From an Excel File

All Technical Context items were known; no NEEDS CLARIFICATION was left. The items below are the
design choices.

## R1. Read `.xlsx` with the standard library

- **Decision**: `churchmgr/xlsx.py` opens the bytes with `zipfile.ZipFile(io.BytesIO(data))` and
  reads `xl/workbook.xml` → first `<sheet>` → its target in `xl/_rels/workbook.xml.rels` → that
  sheet XML, plus `xl/sharedStrings.xml` if present. Cells: `t="s"` (shared string, join all `<t>`
  in the `<si>`, so rich text works), `t="inlineStr"`, `t="str"`, `t="b"`, number (no `t`). Cell
  place from the `r` attribute (`C7` → row 7, column 3), so skipped cells and rows are right.
  Returns `list[list[str | float | None]]`. Text is NFC.
- **Rationale**: The `.xlsx` format is a zip of XML (an open ISO standard). Reading only values
  needs about 60 lines. Constitution II forbids a package.
- **Alternatives**: a spreadsheet package (forbidden); CSV only (the pastor would need to "save
  as CSV", and CSV from a Vietnamese system often breaks diacritics: refused); reading `.xls`
  (old binary format, far more code: refused, the app asks to save as `.xlsx`).

## R2. Dates and numbers in cells

- **Decision**: The code knows which columns hold dates (Birth date, Start date). A number in a
  date column is a spreadsheet date serial: day = 1899-12-30 + serial days (or 1904-01-01 when
  `workbookPr date1904="1"`). Text in a date column is read as `dd/mm/yyyy`, `d/m/yyyy` or
  `yyyy-mm-dd`. A number in a text column (Phone) is written without `.0` (`912345678.0` →
  `"912345678"`); digits are not changed.
- **Rationale**: Knowing the column avoids reading `styles.xml` number formats. Vietnamese users
  type day first.
- **Alternatives**: read cell styles to detect dates (much more code, no gain).

## R3. Keep the rows between the check page and Save

- **Decision**: The check page holds the cleaned row values as one hidden field (`rows`, JSON
  text). Save reads it and **runs the full check again** before it writes. The file itself is not
  kept anywhere.
- **Rationale**: No server state, no temp file in the church copy (FR-013), the browser cannot be
  asked to send the file again. Re-checking makes the hidden field a normal untrusted input (trust
  boundary) and catches changes made between check and Save (for example a Family added in another
  tab). 2,000 rows ≈ 0.5 MB, far below `MAX_BODY`.
- **One check page = one Save** (added after review): the page also holds a random one-use `code`
  (`uuid.uuid4().hex`; the `secrets` module is not used because its name is an Avoid word for the code
  check). Save reads the used codes (setting `people_file_used`, the newest 200)
  and adds its code inside the same `BEGIN IMMEDIATE` transaction as the Persons, so a double click,
  Back + Save or two Saves at once add the rows only once, also after a restart. A Save with row errors
  does not use up the code.
- **Alternatives**: a server-side dict by token (lost on restart, needs expiry code); a temp file
  (data outside the app, cleanup code).

## R4. All-or-nothing Save, existing rules

- **Decision**: `save_people_file(conn, rows)` runs inside one `db.transaction(conn)`. For each row
  it builds a form dict and calls `people_page.add_person_from_form(conn, form)`; for a new Family
  name it calls `people.add_family(conn, name, address)` once; then
  `people_page.set_family_from_form(conn, pid, form)`. Those functions open nested transactions,
  which `db.transaction` turns into SAVEPOINTs, so any error rolls back the whole file.
- **Rationale**: Constitution III and Data Safety Rules: no copied rules, only app functions write.
- **Alternatives**: bulk SQL insert (copies rules, skips Status/Family history rules: refused).

## R5. Matching words the pastor types

- **Decision**: Compare with `text.fold` (no diacritics, any case, single spaces).
  - Column titles: the title words of both languages from the text table, plus the English column
    key. Unknown titles are listed as ignored.
  - Gender: `M`/`F`, and the screen words in both languages (for example Nam/Nữ, Male/Female).
  - Status: list item `name` or `code`, or its screen word in either language; active items only.
  - Family role: the codes `Head/Spouse/Child/Other` and their screen words in both languages.
  - Family: `family.name_folded`. 0 matches → new Family (one per distinct folded name in the
    file); 1 → join; 2+ → row error.
  - Same name warning: `person.name_folded` in the church copy, and other rows in the file.
- **Rationale**: Spec FR-004/5/6/16/17/18 and Constitution VI.
- **Alternatives**: exact match (too strict for typed text).

## R6. The empty file

- **Decision**: `xlsx.write(sheets)` writes a minimal `.xlsx` (content types, rels, workbook, one
  `styles.xml` with a Text cell format, sheets with inline strings). Sheet 1 "People" / "Mọi
  người": the title row only, columns formatted as Text so leading zeros of phones and typed dates
  stay as typed. Sheet 2 "Help" / "Hướng dẫn": one line per column (required or not, allowed
  words, date form) and one example row. Titles in the current screen language.
- **Rationale**: The example row is on the help sheet, so it can never be added by mistake (spec
  FR-011 was updated to say so). Only sheet 1 is read.
- **Alternatives**: ship a fixed file in `web/` (cannot list the church's own Status names, one
  file per language).

## R7. Words

- **Decision**: New glossary entry **People file** — _Tiếng Việt_: **Tệp danh sách người** — "A
  `.xlsx` file with one row per new Person, used to add many people at once. Read once, never
  kept." _Avoid_: Upload, import file; _Tránh_: tải lên, tệp đính kèm. Screen labels: "Add from
  .xlsx file" / "Thêm từ tệp .xlsx", "Get the empty file" / "Lấy tệp mẫu trống". The product name
  is not used on screen or in code (`docs/GOAL.md` rule 8). Module, route and test names use
  `people_file`.
- **Rationale**: Constitution I; the Avoid test scans code.
- **Alternatives**: "Import" (not in the glossary; "nhập" is vague in Vietnamese).

## R8. Safety of a file from outside

- **Decision**: Refuse a file over 10 MB, a zip member over 50 MB uncompressed, or more than 5,000
  rows, with a clear sentence. Catch `zipfile.BadZipFile`, `KeyError`, `ElementTree.ParseError` →
  "This is not a .xlsx file". No Private note column exists; a column that folds to "private note"
  / "ghi chu ca nhan" is ignored like any unknown column. No row values are logged.
- **Rationale**: Trust boundary (Data Safety Rules), zip bombs, Constitution IV. Python's XML
  parser does not load outside entities, and its expat has entity-expansion limits.
- **Alternatives**: no limits (a bad file could freeze the app).
