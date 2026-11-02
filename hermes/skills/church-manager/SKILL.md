---
name: church-manager
description: Use when the pastor asks about Church Manager data (people, Family, calendar, Offering, Expense, Visits), or asks to add a Person, record an Offering or Expense, add a Calendar item, plan a Visit or mark a Visit done. Works only through `python -m churchmgr.agent`, with a dry run before every save.
---

# Church Manager

Church Manager is the pastor's offline database for one church. Its data is a church copy on this
computer. You reach it through one door only: `python -m churchmgr.agent COMMAND`. Each command
prints one JSON object.

## When to use

- The pastor asks about People, a Family, the calendar, Offerings, Expenses, or who needs a Visit.
- The pastor asks you to add a Person, record an Offering or an Expense, add a Calendar item, plan
  a Visit or mark a Visit done.
- Not for work on the app's code. For that, read `AGENTS.md` in the Church Manager folder.

## How to run a command

- Run each command in the Church Manager folder: the folder with `app.py` and `AGENTS.md`. If you
  do not know where it is, ask the pastor.
- With no `--copy`, a command opens the church copy that `python app.py` opens with no options (or
  the one named in `CHURCH_MANAGER_COPY`). If the pastor starts Church Manager with
  `--copy FOLDER`, give the same `--copy FOLDER` to every command.
- `python -m churchmgr.agent COMMAND --help` shows every option of a command (in the key `help`).
- An answer is `{"ok": true, "command": ...}` or `{"ok": false, "error": CODE, "message": ...}`.

## First step: status

Run `python -m churchmgr.agent status` first, each time you start.

- `"ok": true`: go on. You see the church name, the church copy folder and how many People,
  Families, Calendar items, Offerings and Expenses it has. The first time, check with the pastor
  that `church_name` is their church.
- `"error": "door_off"` (exit code 3): the Hermes door is off. Tell the pastor:
  "The Hermes door is off. To let me help, open Church Manager, go to Settings, set Hermes door
  to On, and press Save settings." Then STOP. Do not try another way.

## Commands

Read commands change nothing. A write command is a dry run unless you add `--yes`.
The ids in the examples are only examples. Get the real ids from `search`, `person`, `lists` and
`calendar`.

### Read commands

| Command | What it gives | Example |
|---|---|---|
| `status` | Church name, copy folder, counts and a quick database check | `python -m churchmgr.agent status` |
| `search` | People by name, with or without accents: `id`, `full_name`, `status_name`. 20 at most; `--limit` 1 to 100 | `python -m churchmgr.agent search nguyen hai dang` |
| `person` | One Person: details, Status, Family, Ministries and story. Never Private notes | `python -m churchmgr.agent person 12` |
| `family` | One Family: name, address, Chi phái and the people in it now | `python -m churchmgr.agent family 3` |
| `calendar` | Calendar items from `--from` to `--to` (default: today and the next 6 days; 366 days at most) | `python -m churchmgr.agent calendar --from 2026-11-01 --to 2026-11-30` |
| `money` | Offerings, Expenses and balance of one month, in whole dong (default: this month) | `python -m churchmgr.agent money --year 2026 --month 10` |
| `care-due` | People who need a visit: no Visit within the care reminder time | `python -m churchmgr.agent care-due` |
| `lists` | Ids and names of the Status, Fund and Spending category lists, and the Calendar item kinds | `python -m churchmgr.agent lists` |

### Write commands (a dry run unless `--yes`)

| Command | What it saves | Example (a dry run) |
|---|---|---|
| `add-person` | A new Person. `--full-name` is needed. Also `--gender` (M or F), `--birth-date`, `--phone`, `--address`, `--note`, `--status-id` (from `lists`), `--start-date` | `python -m churchmgr.agent add-person --full-name "Lê Văn An" --status-id 3` |
| `add-offering` | An Offering: `--amount`, `--fund-id` (from `lists`), `--giver person-ID` or `--giver family-ID` (no `--giver` = a no-name offering), `--date`, `--note` | `python -m churchmgr.agent add-offering --amount 1.250.000 --fund-id 9 --giver person-5` |
| `add-expense` | An Expense: `--amount`, `--spending-category-id` (from `lists`), `--date`, `--note` | `python -m churchmgr.agent add-expense --amount 350000 --spending-category-id 13 --note "Tiền điện tháng 10"` |
| `add-calendar-item` | A Calendar item: `--kind` (Service, Meeting, Visit or Event), `--title`, `--starts-at`, `--ends-at`, `--place`, `--note`; `--repeat weekly` or `monthly` with `--repeat-until`; for a Visit `--person-id` or `--family-id` | `python -m churchmgr.agent add-calendar-item --kind Meeting --title "Họp Ban Chấp Sự" --starts-at "2026-11-10 19:00"` |
| `plan-visit` | A planned Visit for one Person (`--person-id`) or one Family (`--family-id`), with `--starts-at` and `--note` | `python -m churchmgr.agent plan-visit --starts-at "2026-11-12 09:30" --person-id 12` |
| `visit-done` | Marks a planned Visit done, so it goes in the Care log: the Calendar item id, `--done-date`, `--care-note` | `python -m churchmgr.agent visit-done 48 --care-note "Đã thăm, cầu nguyện chung"` |

A dry run answers `"dry_run": true, "saved": false`, with `would_save` (the values) and `result`
(the ids it would get). The same command with `--yes` answers `"dry_run": false, "saved": true` and
`result`. Money comes back as `amount` (whole dong, an integer) and `amount_text` (for example
"1.250.000 ₫").

## Rules

1. **Read first.** Answer questions with read commands. Read only what the question needs.
2. **Two steps for every save.**
   1. Run the write command WITHOUT `--yes`. This is a dry run: nothing is saved.
   2. Tell the pastor in plain words what would be saved. Use names, not ids (look them up with
      `person` and `lists`). For example: "I will record an Offering of 1.250.000 ₫ to the General
      Fund from Nguyễn Hải Đăng, on 2026-11-02."
   3. Ask: "Save this? yes or no"
   4. Only after a clear yes ("yes" or "có" to this question), run the SAME command again with
      `--yes` added. Anything else is a no: save nothing, or change the values and show a new dry
      run. One yes is for one save.
3. **Never delete or edit.** No command deletes or changes a record. The one change is
   `visit-done`, which marks a planned Visit done. Do not try another way. If the pastor wants to
   delete or change something, tell them to do it in Church Manager.
4. **Only the door.** Never open `church.db` with sqlite, Python or any other tool. Never read files
   in the church copy folder (also not its `documents` folder). Never use the Church Manager web
   pages or their addresses (a browser, curl) to read or change data. Never try to get Private
   notes. Never turn on the Hermes door yourself, and never work around it.
5. **Glossary words.** Say Person and People (Member is a Status, not a kind of Person), Family,
   Chi phái, Trưởng Chi phái, Calendar item, Visit, Care log, Offering, Giver, Fund, Expense,
   Spending category, Private note. Keep the Vietnamese accents in names.
6. **Where the data goes.** All that a command prints goes to the AI model chosen in Hermes. With a
   cloud model, church data leaves this computer. Prefer a local model.
7. **Exit codes.** Read `ok` and `error` in the answer, then do this:

| Exit code | `error` | What it means | What you do |
|---|---|---|---|
| 0 | none (`"ok": true`) | Done. A write without `--yes` saved nothing yet. | Answer, or show the dry run and ask. |
| 1 | `invalid` | A value was refused. Nothing was saved. `message` is the sentence the web form shows. | Tell the pastor the message in plain words. Ask for the right value. |
| 1 | `not_found` | No record has that id. | Find the right id with `search`, `lists` or `calendar`, then run it again. |
| 1 | `no_copy` | The church copy was not found or could not be read. | Tell the pastor the message. Ask them to open Church Manager once (`python app.py`), or to give you the church copy folder. Do not look for the file yourself. |
| 2 | `usage` | The command or an option is wrong. | Your mistake. Read `--help`, fix the command, run it again. |
| 3 | `door_off` | The Hermes door is off. | Tell the pastor how to turn it on (see First step). Then stop. |

If the output is not one JSON object (for example a Python error), stop. Show the pastor what it
printed. Do not try another way.

## Pitfalls

- **Save once.** Each run with `--yes` saves again: two runs make two Offerings. If you are not sure
  a save worked, read it back first (see Verification). Never run `--yes` again "to be safe".
- **Ids are not 1, 2, 3.** Fund, Spending category and Status ids come from `lists`. A Person id
  comes from `search`. A Family id is `family_id` inside `family` in the `person` answer (its `id`
  is the id of the link, not of the Family). A planned Visit id is in `calendar` (`kind` Visit,
  `visit_done` 0). The calendar shows 7 days by default: give `--from` and `--to`.
- **Money is whole dong.** Write `1250000` or `1.250.000`. No decimals and no minus sign: `1,5` is
  refused. Tell the pastor the `amount_text`.
- **Dates and times.** A day is `YYYY-MM-DD`. A date and time is `"2026-11-08 09:00"` (with the
  quotes) or `2026-11-08T09:00`. The date of an Offering, an Expense, a Status start or a done Visit
  cannot be after today.
- **A repeat makes many Calendar items.** `--repeat weekly` or `monthly` with `--repeat-until` makes
  one item per week or month. Tell the pastor how many (`calendar_item_ids` in the dry run). A Visit
  does not repeat.
- **A Visit is for one Person or one Family**, not both.
- **`--note` is a normal note.** On `add-person` it shows on the Person page. It is never a Private
  note. Only the pastor writes Private notes, in Church Manager.
- **Search works with or without accents.** "nguyen hai dang" finds "Nguyễn Hải Đăng".
- **"No module named churchmgr"** means you are in the wrong folder. Go to the Church Manager folder.
- **The ids in a dry run** are the ids `--yes` gets only if nothing else is saved in between. Use the
  ids from the `--yes` answer.

## Verification

After each save with `--yes`:

1. Check that the answer has `"saved": true`.
2. Read it back with a read command:
   - `add-person`: `person` with the new `person_id`.
   - `add-offering` or `add-expense`: `money` with `--year` and `--month` of its date. Read it before
     the save too: the total is now higher by `amount`.
   - `add-calendar-item` or `plan-visit`: `calendar` with `--from` and `--to` around its day shows
     the new id.
   - `visit-done`: the same `calendar` shows `visit_done` 1 and the `care_note`.
3. Tell the pastor in one short sentence what was saved.
