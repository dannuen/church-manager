<!--
Sync Impact Report
- Version change: template (unversioned) → 1.0.0 (first real constitution)
- Principles set: I. Glossary Words Only; II. Standard Library Only, Keep It Small;
  III. Data Is Never Lost; IV. Private Notes Stay In The App; V. Offline, One Church Copy;
  VI. Vietnamese First, Easy For One Pastor; VII. Proven Before Done
- Added sections: Data Safety Rules; Development Workflow; Governance
- Removed sections: none
- Templates: plan-template.md reads this file at run time (no edit needed); spec-template.md and
  tasks-template.md have no principle-specific slots (no edit needed)
- Follow-up TODOs: none
- Source: AGENTS.md, docs/GOAL.md, GLOSSARY.md. Ratified date = first goal brief commit.
-->

# Church Manager Constitution

## Core Principles

### I. Glossary Words Only

Code, names, screen text and docs MUST use the words of `GLOSSARY.md` exactly. A word from an
Avoid list (English or Vietnamese) MUST NOT appear in `churchmgr/*.py` or `tests/*.py`; a test
checks this. A new idea that needs a new word MUST get a glossary entry first.
Rationale: one pastor, one set of words; a wrong word confuses a non-technical reader.

### II. Standard Library Only, Keep It Small

The app runs on Python 3.14 and its standard library only. No package is added, ever. Choose the
simplest change that fully works; do not add a dependency or an abstraction for a few lines.
Rationale: the pastor installs only Python; every extra part is a part that can break.

### III. Data Is Never Lost

- Money MUST be a whole number of dong (int), never a float.
- Past links (Status, Family, Chi phái, Trưởng Chi phái) MUST be kept with start and end dates.
  They are never overwritten or deleted.
- Data changes MUST go only through the app's own functions. Nobody edits `church.db` by hand or
  with a script.
- A change that writes many rows MUST be all-or-nothing: either every row is saved or none is.
Rationale: the church copy is the church's memory; a lost or half-saved record cannot be rebuilt.

### IV. Private Notes Stay In The App

Private notes MUST NOT leave the app: not in a Handover, a print, a Giving statement, an agent
command, a log, an export or an answer to anyone.
Rationale: counseling and prayer notes are for the pastor only.

### V. Offline, One Church Copy

The app works with no Internet. One church = one church copy (one database file + one documents
folder). Real church copies live in `%LOCALAPPDATA%\ChurchManager\`, never in OneDrive. Work on
code uses a fake church in a temp folder (`python -m churchmgr.fake <folder>`), never a real copy.
Rationale: church data must not go to the cloud by accident.

### VI. Vietnamese First, Easy For One Pastor

Vietnamese is the default screen language and English is one click away. Text is UTF-8 and NFC
everywhere; search works with or without diacritics. The pastor's own data is never translated.
Every feature MUST be usable by one non-technical person with no training: plain words, clear
error sentences that say what to fix.
Rationale: the user is one pastor, not an IT team.

### VII. Proven Before Done

Each change MUST come with tests (unittest). `python verify.py` MUST exit 0 and print
`ALL ... CHECKS PASS` before a change is done.
Rationale: there is no support desk; the checks are the safety net.

## Data Safety Rules

- Form rules live in one place per form (`*_from_form` in `churchmgr/pages/`), shared by the web
  page and the Hermes door. A new way in (a page, a file, an agent command) MUST reuse them, not
  copy them.
- Input from outside (forms, files, agent commands) is checked at the door. A bad value gives a
  clear sentence, not a crash, and saves nothing.
- The Hermes door (`python -m churchmgr.agent`) saves nothing without `--yes`, and works only when
  Settings > Hermes door is on.

## Development Workflow

- Read `AGENTS.md` and `GLOSSARY.md` before a change.
- Logic goes in `churchmgr/*.py` (functions take a SQLite connection); pages, routes and form rules
  go in `churchmgr/pages/*.py`; screen text goes in the text table (`churchmgr/i18n.py`) in both
  languages.
- Test against a fake church; run the one test file first, then `python verify.py`.
- Do not commit, push or rewrite history unless the pastor asks.

## Governance

This constitution sits above other practice notes. `AGENTS.md` is the runtime guide and MUST agree
with it; if they disagree, fix one of them in the same change. An amendment needs the pastor's
yes, a version bump and a Sync Impact Report. Versions follow semantic rules: MAJOR for a removed
or redefined principle, MINOR for a new principle or section, PATCH for wording. Every plan runs
the Constitution Check; every review checks the principles above.

**Version**: 1.0.0 | **Ratified**: 2026-11-01 | **Last Amended**: 2026-11-07
