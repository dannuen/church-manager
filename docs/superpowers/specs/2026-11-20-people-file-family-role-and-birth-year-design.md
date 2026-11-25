# Design: People file family role default, and year-only Birth date

Status: waiting for the pastor's approval. Size: small project.

## Intent
Adding many people from a People file is slow when every row needs a Family role, and some people only
know a birth year. The pastor wants less typing and no fake dates.

## Goals
1. People file: when a row has a Family and the Family role is empty:
   - Full name equals the Family name (folded: no diacritics, any case) -> role `Head` (the pastor says "owner").
   - Any other name -> role `Other` (the pastor says "member"). **Builder/assistant call: `Other`.**
   - A role typed in the file always wins.
2. Birth date accepts a year only (`1980`) in the People file, the Add Person form and the Edit Person form.

## Non-goals
- No new Family role, no schema change, no migration.
- No change to Status, Family match rules, or "no Chi phái from a file".
- No age or birthday feature.

## Anti-goals
- Editing a Person with a year-only Birth date must never erase or change the year.
- A Family role with no Family stays an error (`people.file_err_family_needed`).

## Approaches
- **A. Store `YYYY-00-00` (picked).** The database check `birth_date GLOB` already accepts it; no migration;
  sorts right (a year-only date sorts first in its year). Risk: code that reads the value as a real date.
  Found only in `people.py` (`_optional_date`), `pages/people.py` (form, line ~522 display), `agent.py`
  (output) and the agent skill doc.
- B. New `birth_year` column. Needs a migration on every church copy and two fields that can disagree. Rejected.

## Decisions
- Birth date input on Add and Edit becomes a text box (`31/12/1980` or `1980`); the date picker cannot take a year.
  Same parser as the People file (see `xlsx.cell_date` and `people_pages.past_or_today`): one rule, not a copy.
- A year-only value must be a year from 1900 to the current year (not after today). Display: `1980`.
- The Edit form shows an existing `1980-00-00` as `1980`, so saving keeps it.
- The People file reads a year-only cell (number `1980` or text `1980`) as year-only, not as a date serial.
- The check page shows the role it will use, so the pastor can see it before Save.
- Agent output keeps the raw value; `hermes/skills/church-manager/SKILL.md` says `YYYY-00-00` means year only.

## Left to the builder
- Exact screen words (English and Vietnamese) in the text table, per GLOSSARY.md.
- Where the one shared parser lives (`text.py` is the likely home).
- Tests: role default (Head, Other, typed wins, no Family), year-only in file/Add/Edit, sort in `family_members`,
  edit round trip keeps the year. `python verify.py` must pass.
