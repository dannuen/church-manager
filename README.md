# Church Manager

Church Manager helps one senior pastor run one church: People, Families, Chi phái, the Calendar,
Money, Care, Documents and Sent documents. It works offline, in your browser. Each church has its
own church copy.

## Start

1. Get Python 3.14 from python.org. Nothing else is needed.
2. Open a command window in this folder (in File Explorer: click the address bar, write `cmd`, press Enter).
3. Run `python app.py`.
4. The browser opens Church Manager at http://127.0.0.1:8765. Keep the command window open while
   you work. Press Ctrl+C in it to stop Church Manager.

| Option | What it does |
|---|---|
| `--port N` | Use port N. Without it: port 8765, or the next free port up to 8785. |
| `--no-browser` | Do not open the browser. The window prints the address. |
| `--copy FOLDER` | Open the church copy in FOLDER. |
| `--copies-root FOLDER` | Use FOLDER as the copies folder (see below). |

The first time, there is no church copy yet. The app asks for the church name (New church setup)
and makes a blank church copy with the default lists.

## Where the church copy is saved

A church copy is one folder: `church.db` (the database) and `documents\` (the Document files).

- By default it is `%LOCALAPPDATA%\ChurchManager\<church-slug>\`. The slug is the church name
  without accents, for example `hoi-thanh-tin-lanh-binh-an`.
- `%LOCALAPPDATA%\ChurchManager\` is the copies folder. Its file `current.txt` names the church
  copy that opens at start.
- A church copy is never saved inside OneDrive. The app refuses any folder with "OneDrive" in its path.
- `--copy FOLDER` (or the environment variable `CHURCH_MANAGER_COPY`) opens the church copy in
  FOLDER. FOLDER must hold `church.db`. This start does not change `current.txt`.
- `--copies-root FOLDER` (or the environment variable `CHURCH_MANAGER_HOME`) sets another copies
  folder. If a church copy is given with `--copy` and no copies folder is set, the copies folder is
  the parent folder of the church copy.

## Handover

A Handover gives the church copy to the next pastor of the same church. Private notes are removed.

1. Open **Copies** in the menu.
2. Press **Make Handover**.
3. The zip is saved as `<copies folder>\handovers\handover-<church-slug>-<YYYY-MM-DD>.zip`.
   The page also has a link to download it.

Your church copy is not changed. If the words of a Private note are also written somewhere else in
the church copy, no zip is made: the page lists where. Take the words out of each place: change the
other text, or press **Delete** next to a Document (also in **Documents**). Changing the Private note
does not change a Document file, so the file would still go to the next pastor. Then press
**Make Handover** again. Document files are checked as plain text only: text inside Word or PDF
files is not read.

The next pastor:

1. Unzips the file into a new folder OUTSIDE OneDrive. That folder then holds `church.db` and `documents\`.
2. Starts Church Manager with `python app.py --copy "<that folder>"` (each time, or sets
   `CHURCH_MANAGER_COPY` to that folder).

## New church setup

To start a blank church copy: **Copies** -> **New church setup** -> write the church name ->
**Start New church setup**. It keeps only the default lists and is saved in a new folder of the
copies folder. Church Manager then opens it. The old church copy is kept: open it again from
**Church copies** on the same page.

## Backup

Stop Church Manager (Ctrl+C), then copy the whole church copy folder (`church.db` and
`documents\`) to a USB drive or another folder outside OneDrive.

## Check that everything works

Run `python verify.py`. It runs all tests, builds a fake church of 50 People in a temp folder, starts
the app, checks every Dashboard panel and Search, makes a Handover and proves it has no Private
notes, checks two Giving statements, and checks the Hermes door commands (`python -m churchmgr.agent`).
It prints PASS or FAIL for each check and exits with 0 only when all pass. It never opens your own
church copy. `--keep` keeps the temp folder; `--people N` sets the number of People (20 to 1000).

## Use with Hermes (optional)

Hermes is an AI helper that runs on this computer. It is optional. Church Manager works the same
without it, and the app needs nothing new.

When the Hermes door is on, Hermes can read this church copy and save new records for you, but only
after you say yes. It uses the command `python -m churchmgr.agent` and the guide in the folder
`hermes\skills\church-manager`. It never sees Private notes.

### Turn it on

1. Open Church Manager, then **Settings**.
2. Set **Hermes door** to **On**.
3. Press **Save settings**.

### Add the skill to Hermes

1. Copy the folder `hermes\skills\church-manager` (in this folder) into `%LOCALAPPDATA%\hermes\skills\`.
   If you use a Hermes profile, copy it into `%LOCALAPPDATA%\hermes\profiles\<name>\skills\` instead.
2. Run `hermes skills list` and check that `church-manager` is in the list.

### Try it

In a command window in this folder, run `python -m churchmgr.agent status`. It prints the church name
and how many People, Families, Calendar items, Offerings and Expenses there are. When the Hermes door
is off, it prints that the door is off and changes nothing.

### How saving works

1. Hermes first runs a command without `--yes`. This is a dry run: nothing is saved.
2. Hermes tells you what it would save and asks: "Save this? yes or no".
3. Only after you say yes, Hermes runs the same command with `--yes`. Then it is saved.

No command deletes or changes a record. The one change is marking a planned Visit done.

### Turn it off

- In Church Manager: **Settings** > **Hermes door** > **Off**, then **Save settings**. Every command
  then stops with a clear message.
- To remove the skill, delete the `church-manager` folder you copied into the Hermes `skills` folder.

### Safety

- Private notes never leave the app. No command reads them.
- The Hermes door controls the agent commands. It is NOT a lock on the file: a program on this
  computer can still read the church copy files. So use only a Hermes you trust.
- What Hermes reads is sent to the AI model you chose in Hermes. With a cloud model, church data
  leaves this computer. A local model keeps it here.
