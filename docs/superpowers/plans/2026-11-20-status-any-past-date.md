# Change Status takes any past date. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the Person page, "Change Status" accepts any date up to today, in any order, and builds a Status history with no gaps and no overlaps.

**Architecture:** A new data function `people.insert_status` handles a change at any date. `set_status` and `_set_history` stay exactly as they are, so Family, Chi phái, Ministry, Add Person, the People file, `fake.py` and the Hermes door keep today's rule. Only `status_post` and the Status form on the Person page switch to `insert_status`.

**Tech Stack:** Python 3.14, standard library, unittest, SQLite.

**Spec:** `docs/superpowers/specs/2026-11-20-status-any-past-date-design.md`

## Global Constraints

- Standard library only. No schema change, no migration.
- Words of `GLOSSARY.md` only; never its Avoid words in `churchmgr/*.py` or `tests/*.py`. In tests, name Statuses by their codes as `fake.py` does (`visitor`, `attender`, `member`, `left`).
- Rule 4 exception, approved by the pastor: a change inside a closed line cuts it (its `end_date` becomes the new date). A line is never deleted; its Status and start date never change.
- The unique index `person_status_one_open` (`schema.py:242`) must never break.
- Use a fake church in a temp folder (`python -m churchmgr.fake <folder>`), never a real copy.
- `python verify.py` must exit 0 and print `ALL ... CHECKS PASS`.
- Screen words in `churchmgr/i18n.py`, Vietnamese and English.

## Review Focus

- Add Left on 2018 to a Person with Visitor 2010 to now: Visitor 2010 to 2018, Left 2018 to now, current Status is Left.
- A change before the first line: new line runs to the first line's start; the current Status does not change.
- A date equal to an existing start: refused, nothing changes.
- The same Status as the line that covers the date: "no change" message, nothing written (also when it is not the current Status).
- A date after today: refused.
- A failed change leaves the history as it was (one transaction).

---

### Task 1: `people.insert_status`

**Files:**
- Modify: `churchmgr/people.py` (add after `set_status`, line ~181)
- Modify: `churchmgr/i18n.py` (new error sentence `people.err_status_day`, Vietnamese and English)
- Test: `tests/test_people.py`

**Interfaces:**
- Produces: `people.insert_status(conn, person_id, status_id, day) -> bool`. `day` is `YYYY-MM-DD`, checked with `text.check_date`. Returns `True` when a line was written, `False` when the line that covers `day` already has that Status (nothing written). Raises `TextError("people.err_status_day", day=...)` when a line of this Person already starts on `day`. Runs in `transaction(conn)`.
- Cases (D = `day`): D after the last start = same result as `set_status`. D before the first start = new line `[D, first.start)`. D inside a line (`start < D < end`, or the open line) = that line's `end_date` becomes D and the new line is `[D, old end)` (open if the old line was open).
- Consumes: `lists.require_item`, `_require_row`, `transaction` (as `set_status` does).

- [ ] **Step 1: Write failing tests:** `test_insert_status_inside_open_line` (Visitor from 2010-01-01; insert `left` on 2018-06-30; history Visitor 2010-01-01 to 2018-06-30, Left from 2018-06-30 open; `current_status` is Left). `test_insert_status_inside_closed_line` (Visitor 2010 to 2024, Member from 2024 open; insert Left on 2018-06-30: Visitor to 2018-06-30, Left 2018-06-30 to 2024, Member open). `test_insert_status_before_first` (first line from 2024-03-15; insert on 2010-01-01: new line 2010-01-01 to 2024-03-15; current Status unchanged). `test_insert_status_same_as_covering_returns_false` (history unchanged). `test_insert_status_on_existing_start_refused` (`ValueError`, history unchanged). `test_insert_status_open_row_stays_unique` (query `person_status` where `end_date IS NULL` count is 1 after each case).
- [ ] **Step 2: Run** `python -m unittest discover -s tests -p test_people.py`. Expected: FAIL (`insert_status` missing).
- [ ] **Step 3: Implement** `insert_status` with SQL on `person_status` (read the Person's lines ordered by `start_date`; find the covering line = last line with `start_date < D`; branch on the cases). Add the sentence: English "A Status already starts on {day:%d/%m/%Y}. Pick another date." and its Vietnamese pair.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `feat: insert a Status at any past date`.

### Task 2: Person page uses it

**Files:**
- Modify: `churchmgr/pages/people.py` (`_status_panel` line ~463, `status_post` line ~699)
- Modify: `churchmgr/i18n.py` (`people.move_hint`-style hint for the Status date: "An earlier date adds to the past.")
- Test: `tests/test_pages_people.py`

**Interfaces:**
- Consumes: `people.insert_status` (Task 1).

- [ ] **Step 1: Write failing tests:** `test_status_form_has_no_min_date` (the Status date input has no `min`). `test_status_post_past_date` (Visitor from 2010, POST Left on 30/06/2018: redirect with the "changed" message; the history table shows both lines). `test_status_post_same_as_covering` (message `people.status_same`, nothing written). `test_status_post_existing_start_date` (400 or the form with the error next to the date, history unchanged). `test_status_post_after_today` (refused, as today).
- [ ] **Step 2: Run** `python -m unittest discover -s tests -p test_pages_people.py`. Expected: FAIL.
- [ ] **Step 3: Implement.** `_status_panel` drops `min_date=latest_change(rows)` for the Status date and shows the hint. `status_post.change` calls `people.insert_status`: on `False` returns `same_change(t("people.status_same", name=<name of new_id>))`; the "changed" message uses the new Status name and date (not `current_status`, which may be another line). Remove the old `before ... == new_id` check (it compares with the current line, not the covering one).
- [ ] **Step 4: Run** the same command, then `python verify.py`. Expected: PASS and exit 0.
- [ ] **Step 5: Commit** `feat: Person page Status change takes any past date`.
