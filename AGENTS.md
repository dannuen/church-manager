# AGENTS.md: Church Manager

Church Manager is an offline database with a dashboard in the browser. It helps one senior pastor
run one church: People, Families, Chi phái, the Calendar, Money, Care, Documents and Sent documents.
Each church has its own church copy. Python 3.14, standard library only. `README.md` says how to
run it.

## Map

| Where | What |
|---|---|
| `churchmgr/*.py` | The logic, one module per part (people, calendar, money, care, ...). Functions take a SQLite connection. |
| `churchmgr/pages/*.py` | The web pages: routes, forms and the form rules (`*_from_form`). |
| `churchmgr/agent.py` | The Hermes door: `python -m churchmgr.agent`, JSON commands for the Hermes helper. No other module imports it. |
| `churchmgr/fake.py` | A fake church for tests and demos. |
| `web/` | CSS and JavaScript of the dashboard. |
| `tests/` | The tests (unittest). One file: `python -m unittest discover -s tests -p test_people.py`. |
| `verify.py` | The check from end to end. |
| `GLOSSARY.md` | The words of this project. |
| `hermes/skills/church-manager/SKILL.md` | The Hermes skill: how to read and add church data. |

## Rules

1. Use the words of `GLOSSARY.md` exactly, in code, names and text. Never use a word from its
   Avoid lists. A test checks `churchmgr/*.py` and `tests/*.py` for them.
2. Standard library only. Add no package.
3. Money is a whole number of dong (int). Never a float.
4. Past links (Status, Family, Chi phái, Trưởng Chi phái) are kept with start and end dates. Never
   overwrite or delete them.
5. Private notes never leave the app: not in a Handover, not in an agent command, not in a log, not
   in an answer to anyone.
6. Never edit `church.db` by hand (no sqlite tool, no script). Data changes only through the app.
7. The real church copies live in `%LOCALAPPDATA%\ChurchManager\`, never in OneDrive. Do not open
   them when you work on code.
8. When you change code, use a fake church in a temp folder outside OneDrive, never the real church
   copy: `python -m churchmgr.fake <folder>`, then `python app.py --copy <folder>`.
9. `python verify.py` must exit 0 (it prints `ALL ... CHECKS PASS`) before a change is done.

## Church data

To read or add church data, use only `python -m churchmgr.agent`. Follow
`hermes/skills/church-manager/SKILL.md`. The commands work only when the pastor has turned on
Settings > Hermes door. A write command saves nothing without `--yes`. Add `--yes` only after the
pastor says yes to the dry run.
