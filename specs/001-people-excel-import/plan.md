# Implementation Plan: Add People From an Excel File

**Branch**: `001-people-excel-import` (spec folder; work stays on `main` until the pastor asks for a branch) | **Date**: 2026-11-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-people-excel-import/spec.md`

## Summary

The pastor picks one filled-in `.xlsx` file on a new People page. The app reads the first sheet
with the standard library (`zipfile` + `xml.etree`), checks every row with the **same form rules**
as Add a Person and Set Family, and shows a check page (errors stop Save, same-name warnings do
not). Save re-checks the rows and writes all Persons, new Families, Status links and Family links
in **one transaction**. A second action gives an empty `.xlsx` file in the right format, written
with the standard library too. No schema change.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: Standard library only (`zipfile`, `xml.etree.ElementTree`, `datetime`,
`json`). No package (Constitution II).

**Storage**: Existing SQLite church copy. No new table, no new column. The picked file is never
stored (FR-013).

**Testing**: `unittest`, new file `tests/test_people_file.py`; then `python verify.py`.

**Target Platform**: Windows PC, local web server on 127.0.0.1, any modern browser, offline.

**Project Type**: Local web app (server-rendered pages, `churchmgr/pages/*.py`).

**Performance Goals**: 2,000-row file → check page in < 10 s (SC-005). One DB read per lookup
list, not per row.

**Constraints**: Offline; all-or-nothing save; Private notes never read from a file; no Avoid
words; screen text in vi and en; body ≤ `server.MAX_BODY` (60 MB).

**Scale/Scope**: One church, up to a few thousand people per file. Limit 5,000 rows per file.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Pre-design | Post-design |
|---|---|---|---|
| I. Glossary words only | New idea gets a glossary entry first; no Avoid words ("upload", "attachment", "tải lên", "tệp đính kèm", "Household", "hộ") | PASS (entry "People file" planned as task 1) | PASS: routes, keys and names use People file / Family / Status; see [research.md](research.md) R7 |
| II. Standard library only | No package for `.xlsx` | PASS | PASS: `zipfile` + `ElementTree` read and write (R1, R2) |
| III. Data is never lost | All-or-nothing; past links kept; only app functions write | PASS | PASS: one `db.transaction`; writes go through `add_person_from_form`, `people.add_family`, `set_family_from_form`; only new rows, nothing overwritten (R4) |
| IV. Private notes stay in the app | No Private note in or out | PASS | PASS: no Private note column; unknown columns ignored; nothing logged (R8) |
| V. Offline, one church copy | No network; file not kept | PASS | PASS: file bytes live only in the request; check page carries cleaned values, not the file (R3) |
| VI. Vietnamese first, easy | Both languages; clear sentences; diacritics optional in matching | PASS | PASS: column titles, Status, Gender, Family role and Family names matched with `text.fold` (R5) |
| VII. Proven before done | Tests + `verify.py` exit 0 | PASS | PASS: [quickstart.md](quickstart.md) lists the checks |
| Data Safety: reuse `*_from_form` | No copied rules | PASS | PASS: rows become a form dict and go through the existing functions |

No violation. Complexity Tracking is empty.

One note outside the constitution: `docs/GOAL.md` rule 8 says docs must not name other companies'
products. The pastor asked for "Excel", so the spec keeps his words, but **screen text and code say
".xlsx file" / "tệp .xlsx"**, not the product name (R7). The pastor can change this.

## Project Structure

### Documentation (this feature)

```text
specs/001-people-excel-import/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── routes.md        # Phase 1: pages and forms
│   └── people-file.md   # Phase 1: the file format
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks, not made here)
```

### Source Code (repository root)

```text
GLOSSARY.md                      # + entry "People file" / "Tệp danh sách người"
churchmgr/
├── xlsx.py                      # NEW: read first sheet -> rows of text/number; write a simple .xlsx
├── i18n.py                      # + keys in section "people" (vi and en)
└── pages/
    ├── __init__.py              # + people_file in PAGES
    ├── people.py                # + "Add from .xlsx file" button on /people (one line)
    └── people_file.py           # NEW: routes, column map, check_people_file, save_people_file
tests/
└── test_people_file.py          # NEW
```

**Structure Decision**: Follow the existing layers. The generic file format code goes in
`churchmgr/xlsx.py` (logic layer, takes bytes, knows nothing about people). The rules for People
files go in `churchmgr/pages/people_file.py`, next to `add_person_from_form` and
`set_family_from_form`, which it calls. The Hermes door is not changed (FR-015).

## Complexity Tracking

None.
