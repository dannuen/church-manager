# GOAL 2: Backup and Year report

Add two things to Church Manager. Read GOAL.md, AGENTS.md and GLOSSARY.md first. Use the glossary words exactly. Keep every rule of GOAL.md (offline, Vietnamese first, Private notes never leave, simple stack, no new package).

New glossary words to add before coding (the team adds them to GLOSSARY.md):
- **Backup**: a dated copy of the whole church copy (database + documents folder), kept by the pastor for safety. Unlike a Handover, it keeps Private notes. Tiếng Việt: Sao lưu. Avoid: Snapshot, archive.
- **Year report**: a printable page for the church board with one year of Offerings and Expenses. Tiếng Việt: Báo cáo năm. Avoid: Financial statement.

## PART A: Backup

### THE PASTOR CAN DO (from the app, in Copies)
- Make a Backup with one click. It saves one dated file (like `church-2026-11-10.zip`) with the database and the documents folder.
- See the list of Backups with date and size.
- Restore a Backup with one click. The app asks "Yes" first and says that today's data will be replaced. Before it replaces, it makes a Backup of the current church copy.
- Dashboard shows "Last Backup: N days ago". It is red after 30 days (setting can change).

### RULES
1. Backups are saved OUTSIDE OneDrive, in a folder next to the church copy in `%LOCALAPPDATA%\ChurchManager\`. The pastor may pick another folder (for example a USB disk).
2. A Backup keeps Private notes. The app says this on screen. It is never sent anywhere and never used as a Handover.
3. A restore never half-works. If the file is bad, the church copy stays as it was.
4. Standard library only (`zipfile`, `sqlite3` backup API). Do not copy the database file while it is open; use the safe SQLite way.

## PART B: Money trend and Year report

### THE PASTOR SEES (in Money)
- Month by month for the chosen year: Offerings, Expenses, balance. A simple bar chart in plain HTML/CSS or inline SVG, no chart library.
- Offerings by Fund and Expenses by Spending category for the year, with totals.
- Compare with the year before (up or down, in dong and in percent).

### THE PASTOR CAN DO
- Print a Year report. It follows the chosen language. It has the church name, the year, the tables above and the date printed.

### RULES
1. Money is a whole number of dong. No float. The percent is only shown, never stored.
2. The Year report shows totals only. It never shows a Giver name and never shows a Private note.
3. A no-name offering counts in the totals.

## NOT IN SCOPE
Cloud backup, automatic timed backup, encryption, per-Giver lists in the Year report (the Giving statement does that), budgets, export to .xlsx.

## DONE MEANS
- `python verify.py` exits 0 and now also: makes a Backup of the fake church, changes the data, restores, and proves the data is back; proves a bad file does not change the church copy; proves the Year report totals equal the sum of the Offerings and Expenses in the database; proves the Year report has no Giver name and no Private note.
- Every dashboard panel and Money page works in Vietnamese and English.
- README.md says where Backups are saved and how to restore.
- Work on a fake church in a temp folder outside OneDrive. Never open the real church copy.
