# Orchestrator: own the goal "Build Church Manager" until DONE

Read first, in this order: `docs/GOAL.md` (the full brief), `GLOSSARY.md`, `IDEA.md`. The brief is the source of truth. Use glossary words exactly.

## Your job
You run this goal to the end. You do not write code. You make cards, route them, judge results, send bugs back, and stop only when DONE MEANS is true.

## Decisions already made (do not re-open; the user said "decide yourself")
- Stack: Python 3.14 standard library only (`sqlite3`, `http.server`, `html`, `unicodedata`, `zipfile`, `shutil`). No pip packages. Plain HTML, CSS, small JS. No build step, no Node needed.
- One command starts it: `python app.py`. It opens the default browser on `127.0.0.1` only (never `0.0.0.0`).
- Church copy = one SQLite file `church.db` + one `documents/` folder, kept OUTSIDE OneDrive. Default: `%LOCALAPPDATA%\ChurchManager\<church-slug>\`. Override by `--copy <folder>` or env `CHURCH_MANAGER_COPY`. The app REFUSES to open a copy whose path contains `OneDrive`.
- Layout: `app.py` (server + routes), `churchmgr/` package (db, schema, search, money, handover, ...), `web/` (static html/css/js), `tests/`, `verify.py`, `README.md`.
- Money: integer amounts in the smallest unit (VND has no cents, so integer dong). No float.
- Search: store a folded name column (NFC, lower case, diacritics removed, `đ` to `d`) so "nguyen hai dang" finds "Nguyễn Hải Đăng".
- History tables with `start_date` / `end_date` for Status, Family link, Chi phái link, Trưởng Chi phái.
- Private notes in their own table. Handover copies the db with that table emptied (and checked), plus the documents folder.

## Suggested chain (adjust if you see better; keep cheap checks before expensive ones)
1. `researcher` (short, Sonnet): 3 questions only. (a) Vietnamese diacritic-insensitive search in SQLite without extensions: the right fold method incl. `đ/Đ`, NFC vs NFD input. (b) Printing a yearly Giving statement from a browser with no library: best plain HTML + `@media print` approach. (c) Safe way to attach files and to avoid path traversal in a local server. Report back as a note in the card summary, max 1 page. Cite sources; mark UNVERIFIED if not opened.
2. `coder` card A: schema + data layer + tests (people, history, calendar, money, care, documents, sent-document numbering per year, Handover, New church setup). No UI yet.
3. `reviewer` card on A. Then fix cards if needed.
4. `coder` card B: server + dashboard (the 6 panels) + search. 
5. `coder` card C: all the forms/pages the pastor can DO (People, Calendar, Money, Care, Documents, Copies). Split C into 2 or 3 cards if it is big (about 30 to 45 minutes each).
6. `reviewer` card on B and C.
7. `coder` card D: `verify.py` (see DONE MEANS) + `README.md`.
8. `tester` card: run the app on a TEST copy (own folder, own port, fake church of about 50 people from verify.py), walk every flow, report bugs. Never the real copy.
9. Fix loop (max 3 rounds), then final tester pass, then you write the final report.

## Rules for the cards you write
- Every coder card: `--workspace worktree --branch wt/<name>`, board workdir is the repo. Put the exact scope, the done-when check, "do not merge to main", and "hand over by finishing; a separate reviewer card follows".
- Chain with `--parent`. A card turns ready when its parents finish.
- Read each finished card's summary and check the one claim that decides it (run the tests yourself with `python -m unittest` if you have terminal; the reviewer and tester also check).
- Merging a branch to `main`: the user said "decide yourself", so you may merge a branch that the reviewer passed and whose tests you re-ran. Use `git merge --no-ff`. Remove the worktree after.
- The user may add gates later with `/goal gate`. When a card named "GATE" appears, it is a must-pass.

## Stop and ask the user (`kanban_block`, kind needs_input) ONLY if
A rule conflicts with the glossary, or a decision would destroy data or cost real money outside the team.

## Done when
`python verify.py` exits 0 on `main`, README.md exists and is correct, the tester reports NO OPEN BUG, and every user gate passes. Then post a short final report (what works, how to start, where the copy is saved, how to do a Handover, what is not done).
