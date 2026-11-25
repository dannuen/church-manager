# People file: Family role default and year-only Birth date. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A People file row with a Family and no Family role gets `Head` (name = Family name) or `Other`; Birth date takes a year only everywhere.

**Architecture:** A year-only Birth date is stored as `YYYY-00-00` (the `birth_date GLOB` check in `schema.py:111` already accepts it; no migration). One parser (`birth_from_input` in `pages/people.py`) is used by the Add form, the Edit form and the People file. The role default lives in `_check_rows` of `pages/people_file.py`.

**Tech Stack:** Python 3.14, standard library, unittest, SQLite.

**Spec:** `docs/superpowers/specs/2026-11-20-people-file-family-role-and-birth-year-design.md`

## Global Constraints

- Standard library only. No schema change, no migration.
- Words of `GLOSSARY.md` only. Never write the Avoid words in `churchmgr/*.py` or `tests/*.py`: no "Member" (use `Other`), no "Upload", no "import file". Role codes are `Head`, `Spouse`, `Child`, `Other`.
- Past Family links are kept, never overwritten.
- Use a fake church in a temp folder (`python -m churchmgr.fake <folder>`), never a real copy.
- `python verify.py` must exit 0 and print `ALL ... CHECKS PASS`.
- Year-only: a year from 1900, not after today. Stored `YYYY-00-00`, shown `1980`.
- Screen words go in `churchmgr/i18n.py`, Vietnamese and English.

## Review Focus

- Edit Person on a year-only Person, saved with no change: the year stays (not erased).
- A spreadsheet number cell `1980` is a year, not a date serial.
- `2027` (after today) and `1850` (before 1900) are refused as a year.
- Family role typed in the file wins over the default.
- Family role filled but Family empty: still an error (`people.file_err_family_needed`).
- Name equals Family name with different accents or case (`nguyen van an` vs `Nguyễn Văn An`): `Head`.

---

### Task 1: Core rules for a year-only Birth date

**Files:**
- Modify: `churchmgr/text.py` (add `check_birth_date`)
- Modify: `churchmgr/people.py:83` and its two calls at lines 100 and 128 (Birth date only)
- Modify: `churchmgr/ui.py:124` area (add `fmt_birth_date`)
- Test: `tests/test_text.py`, `tests/test_people.py`

**Interfaces:**
- Produces: `text.check_birth_date(value, what="Birth date") -> str`: `YYYY-MM-DD` as `check_date` does, or `YYYY-00-00` (year 1900 to 9999) kept as is; else `TextError("errors.date", label=what)`.
- Produces: `ui.fmt_birth_date(value) -> str`: `"1980"` for `1980-00-00`; otherwise `fmt_date(value)`.

- [ ] **Step 1: Write failing tests:** `test_check_birth_date_year_only` (`"1980-00-00"` returns `"1980-00-00"`; `"1850-00-00"`, `"1980-00-05"`, `"1980-13-00"` raise `ValueError`; `"1980-12-31"` returns itself). `test_add_person_year_only` (add_person with `birth_date="1980-00-00"` saves it; `get_person` returns it). `test_fmt_birth_date` (`"1980-00-00"` gives `"1980"`, `"1980-12-31"` gives `"31/12/1980"`, `None` gives `"—"`). `test_family_members_sort_year_only` (a `1980-00-00` Person sorts before `1980-06-01` in the same role).
- [ ] **Step 2: Run** `python -m unittest discover -s tests -p test_text.py` and `test_people.py`. Expected: FAIL.
- [ ] **Step 3: Implement** the two functions above. `people._optional_date` gets a second helper `_optional_birth` calling `text.check_birth_date`; `add_person` and `update_person` use it for `birth_date` only.
- [ ] **Step 4: Run** the same commands. Expected: PASS.
- [ ] **Step 5: Commit** `feat: year-only Birth date rules`.

### Task 2: Add and Edit Person take a year only

**Files:**
- Modify: `churchmgr/pages/people.py` (`_plain_fields` line 325, `add_person_from_form` ~360, `edit_post` ~406, edit prefill ~381, Person page display line 522; add `birth_from_input`)
- Modify: `churchmgr/i18n.py` (`people.birth_hint`, and a new error sentence if needed)
- Test: `tests/test_pages_people.py`, `tests/test_i18n_people.py`

**Interfaces:**
- Consumes: Task 1 `text.check_birth_date`, `ui.fmt_birth_date`.
- Produces: `pages.people.birth_from_input(value, what="people.birth_date") -> str`. `value` is a typed string or a spreadsheet cell (str, int, float). Returns `YYYY-MM-DD` or `YYYY-00-00`. Reads: `1980` or `1980-00-00` (year-only), `31/12/1980`, `1980-12-31` (via `xlsx.cell_date(value, False)`). A whole number 1900 to the current year is a year (shortcut: a serial in that range would be a 1905-1927 date; upgrade if that ever matters). Not after today (`past_or_today` string compare works for `YYYY-00-00`). Wrong input raises `TextError("errors.date", ...)`; a year after today raises the `people.err_after_today` error.

- [ ] **Step 1: Write failing tests:** `test_birth_from_input` (cases: `"1980"`→`"1980-00-00"`; `1980` int→`"1980-00-00"`; `"31/12/1980"`→`"1980-12-31"`; `"1980-00-00"`→itself; `"2999"`, `"1850"`, `"abc"` raise `ValueError`). `test_add_person_form_year_only` (form `birth_date="1980"` stores `1980-00-00`). `test_edit_person_keeps_year` (GET edit page shows `value="1980"`; POST with that value leaves `birth_date == "1980-00-00"`). `test_person_page_shows_year` (page text has `1980`, no `00/00`).
- [ ] **Step 2: Run** `python -m unittest discover -s tests -p test_pages_people.py`. Expected: FAIL.
- [ ] **Step 3: Implement.** The Birth date field becomes `type="text"` with the hint "dd/mm/yyyy or year only". Add and Edit call `birth_from_input` before `people.add_person` / `update_person`. The edit prefill shows `ui.fmt_birth_date` of the stored value (full dates as `dd/mm/yyyy`, so the text box round-trips). The Person page uses `fmt_birth_date`. `add_person_from_form` also takes ISO input, so the Hermes door and the People file keep working.
- [ ] **Step 4: Run** the same command plus `test_i18n_people.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: Add and Edit Person take a year-only Birth date`.

### Task 3: People file reads year-only and defaults the Family role

**Files:**
- Modify: `churchmgr/pages/people_file.py` (`_check_rows` birth date and Family role, `_date_cell` for Birth date, `EXAMPLE`/`help_rows`)
- Modify: `churchmgr/i18n.py` (`people.file_help_birth_date`, `people.file_help_family_role`; leave `people.file_err_family_role_needed` unused or delete it and its test)
- Test: `tests/test_people_file.py`

**Interfaces:**
- Consumes: `birth_from_input` (Task 2).
- Rule: after the typed role is read, if `values["family"]` is set and no role was typed: `values["family_role"] = "Head"` when `text.fold(values["family"]) == text.fold(values["full_name"])`, else `"Other"`. A typed role wins. Role without Family stays an error.

- [ ] **Step 1: Write failing tests** in `test_people_file.py`: `test_family_role_default_head` (name `Nguyễn Văn An`, Family `nguyen van an`, no role → `Head`); `test_family_role_default_other` (another name in that Family → `Other`); `test_family_role_typed_wins` (`Child` typed stays `Child`); `test_family_role_without_family_error` (still an error); `test_birth_year_only_text_and_number` (cells `"1980"` and `1980` → `1980-00-00`, saved after Save); `test_birth_year_bad` (`2999`, `1850` give a row error, nothing saved); `test_check_page_shows_default_role` (page shows the role word and `1980`). Fix any old test that expected the "role needed" error.
- [ ] **Step 2: Run** `python -m unittest discover -s tests -p test_people_file.py`. Expected: FAIL.
- [ ] **Step 3: Implement.** In `_check_rows` the nested `date(key, label)` uses `birth_from_input` for `birth_date` only (start date keeps `xlsx.cell_date`). `_date_cell` uses `fmt_birth_date` for the Birth date column. Help sheet text says year only is allowed and the role may be left empty (empty: `Head` if the name is the Family name, else `Other`).
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `feat: People file Family role default and year-only Birth date`.

### Task 4: Hermes door, skill doc, end-to-end check

**Files:**
- Modify: `churchmgr/agent.py:367` (hint: `YYYY-MM-DD, or YYYY-00-00 for a year only; not after today`)
- Modify: `hermes/skills/church-manager/SKILL.md` (Birth date line; output `1980-00-00` means year only)
- Test: `tests/test_agent.py`

- [ ] **Step 1: Write failing test:** `test_agent_add_person_year_only` (dry run and `--yes` with `birth_date="1980-00-00"` works; a read command returns it as is).
- [ ] **Step 2: Run** `python -m unittest discover -s tests -p test_agent.py`. Expected: FAIL.
- [ ] **Step 3: Implement** the hint and the skill text. `agent.py` already calls `add_person_from_form`, so it needs no other change; check this.
- [ ] **Step 4: Run** `python verify.py`. Expected: exit 0 and `ALL ... CHECKS PASS`. Also grep `churchmgr/*.py tests/*.py` for the GLOSSARY Avoid words (a test does this).
- [ ] **Step 5: Commit** `feat: year-only Birth date in the Hermes door and skill`.
