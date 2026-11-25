# Plan: run impeccable critique in chat, hand it to the orchestrator

Supersedes `2026-11-14_120000-design-critic-profile.md` (no new profile needed).

## Goal
Run the `impeccable` critique of the Church Manager dashboard in this chat, save it as a report, and give it to the orchestrator in one card so it makes fix cards and assigns them to other profiles.

## Context / assumptions
- The default profile (this chat) has the `impeccable` skill: `C:\Users\danng\AppData\Local\hermes\skills\impeccable\`. Command: `critique [target]` (reference `reference/critique.md`). Launcher: `scripts/impeccable.cmd` (Windows) or `scripts/impeccable`.
- Orchestrator `SOUL.md` already knows how to route: it splits a goal into cards, assigns `coder` (needs a git worktree), writes `DESIGN JOB` in coder/tester card bodies for look-and-feel work, and writes `FINAL UI REVIEW` in the last reviewer card (reviewer then runs its own impeccable critique). So we only have to give it a good GOAL card. No change to any profile.
- AGENTS.md: a chat session sends work to the board with a card titled `GOAL: <title>`, assigned to `orchestrator`, board `church-manager`. Run the app only on a fake church in a temp folder outside OneDrive. Never open `%LOCALAPPDATA%\ChurchManager\`. Private notes must not appear in the report.
- The critique only reports. It never edits code.
- Working tree has uncommitted edits (`churchmgr/pages/calendar.py`, `settings.py`, `server.py`, `AGENTS.md`). The critique reads the running app, so critique what is there. Tell the orchestrator the report was made on `main` at commit `<sha>` plus uncommitted edits.

## Approach
Chat does 3 things: (1) start a fake church, (2) run `impeccable critique` and save the result to `docs/design-critique-2026-11-14.md`, (3) create ONE `GOAL:` card that points at that file. The orchestrator turns the P0/P1 findings into small cards with owners.

## Steps

1. **Fake church, outside OneDrive.**
   `python -m churchmgr.fake "$LOCALAPPDATA/Temp/critique-church"`
   Expect: command exits 0, folder exists.
2. **Start the app (background).**
   `python app.py --copy "$LOCALAPPDATA/Temp/critique-church"` as a background process. Note the URL it prints (check the output, do not guess the port).
   Verify: open that URL in the browser tool; the dashboard shows people. If not, stop and ask.
3. **Load impeccable context once.**
   `"C:/Users/danng/AppData/Local/hermes/skills/impeccable/scripts/impeccable.cmd" context` (cwd = repo root).
   Expect: it prints PRODUCT/DESIGN context or a note that they are missing. If the launcher fails, follow the skill's "Launcher unavailable" rule (say so, read PRODUCT.md/DESIGN.md directly if they exist).
4. **Run the critique.** Load `reference/critique.md` via `skill_view(name='impeccable', file_path='reference/critique.md')`, then critique each page the app has: Dashboard, People, Families, Chi phái, Calendar, Money, Care, Documents, Sent documents, Settings. Look at each page at desktop and phone width. Use Vietnamese text and long names from the fake church. Never quote a private note.
5. **Save the report** to `docs/design-critique-2026-11-14.md` with this exact shape (so the orchestrator can split it):
   ```
   # Design critique 2026-11-14
   Base: main @ <git rev-parse --short HEAD> + uncommitted edits
   Method: impeccable critique, fake church, desktop + phone width

   | # | Severity | Page | Problem | Why it matters to the pastor | Files (best guess) | Suggested fix |
   |---|---|---|---|---|---|---|
   | 1 | P1 | People | ... | ... | `web/...`, `churchmgr/pages/people.py` | ... |

   Severity: P0 Blocker, P1 Major, P2/P3 Minor.
   ```
   Verify: `python -c "import pathlib;t=pathlib.Path('docs/design-critique-2026-11-14.md').read_text(encoding='utf-8');print(t.count('| P'))"` prints a number > 0.
6. **Stop the app** (kill the background process) and delete the temp church: `rm -rf "$LOCALAPPDATA/Temp/critique-church"`.
7. **Commit the report** so coder worktrees can read it (card workers use git worktrees, an untracked file is invisible to them). Ask the pastor first (rule: no commit unless asked). Command if yes:
   `git add docs/design-critique-2026-11-14.md && git commit -m "docs: design critique 2026-11-14"`
   Expect: 1 file changed.
8. **Create the hand-off card.**
   ```
   hermes kanban --board church-manager create "GOAL: Fix design critique findings (2026-11-14)" --assignee orchestrator --body "Read docs/design-critique-2026-11-14.md (committed on main). Make one coder card per P0 and P1 row (merge rows that touch the same file). Merge all P2/P3 rows into one polish card. Every coder and tester card is a DESIGN JOB. Put FINAL UI REVIEW in the last reviewer card. Keep each card to about 30 minutes. Cap fix loops at 3. Do not touch private notes handling, money rules, or history rules (AGENTS.md)."
   ```
   Expect: it prints a card id. Tell the pastor the id and stop (AGENTS.md rule).
9. **Check the board** later: `hermes kanban --board church-manager list` → the new card moves to running; child cards appear, assigned `coder`/`reviewer`/`tester`.

## Tests / validation
No code changes, so no unit tests. Checks are the commands above. At the end: `python verify.py` → `ALL ... CHECKS PASS`, and `git status --short` shows only the report (if uncommitted).

## Risks / open questions
- Report file must be committed before workers start, or coder worktrees will not see it. Fallback: paste the table into the card body instead.
- Orchestrator may create many cards. The body asks it to merge by file and P2/P3 into one card. Pastor can ask for P0 only.
- The three uncommitted edits (calendar/settings/server) may change the look; critique reflects them, coder cards branch from `main` without them. Open question: commit or stash those first?
- Review cost: reviewer's `FINAL UI REVIEW` runs a second critique. That is intended as the check that fixes worked.
- Not done: a recurring/scheduled critique and a new critic profile (YAGNI).
