# Plan: design-critic profile for Church Manager

## Goal
Add a `critic` profile on kanban board `church-manager`. When given a "DESIGN CRITIQUE" card, it looks at the dashboard and creates one kanban card per finding.

## Context / assumptions
- Board `church-manager` has profiles orchestrator, coder, reviewer, tester, researcher. Profiles live in `%LOCALAPPDATA%\hermes\profiles\<name>\` (each has `profile.yaml`, `config.yaml`, `SOUL.md`, `skills/`). Rollback notes: `ROLLBACK-agent-team.md`.
- Reviewer already runs the `impeccable` skill `critique` command, but only on a card with `FINAL UI REVIEW`, and it only adds rows to its own report. It never makes cards. The critic does NOT replace this. It is a separate, on-demand job.
- AGENTS.md rules apply: use a fake church in a temp folder outside OneDrive; never open the real church copy (`%LOCALAPPDATA%\ChurchManager\`); never edit `church.db`; no private notes in output.
- Assumption (from the user): "critique job" = a kanban profile; output = one card per finding.
- Assumption: findings cards are assigned to `orchestrator` with title `GOAL: ...` (same as the pastor's change requests), so the orchestrator decides what to build. Critic never edits code.
- Assumption: `hermes profile create` and `hermes -p <name> tools ...` work as noted in ROLLBACK-agent-team.md (the `--clone-from default` option failed on Windows; use `--no-skills`).

## Approach
Create profile `critic` modeled on `reviewer` (same model, kanban + browser + file + terminal + vision tools, no cronjob/delegation). Give it a `SOUL.md` that: starts a fake church, opens the dashboard, runs `impeccable` critique, then makes one card per P0/P1 finding (P2/P3 go into one summary card). Add one line to the orchestrator `SOUL.md` so it routes "design critique" requests to `critic`.

## Steps

1. **Back up first** (read-only copy).
   `cp -r "$LOCALAPPDATA/hermes/profiles/orchestrator" "$LOCALAPPDATA/hermes/backups/critic-2026-11-14-orchestrator"`
   Expect: no error; folder exists.

2. **Create the profile.**
   `hermes profile create critic --no-skills`
   Expect: profile created. Verify: `ls "$LOCALAPPDATA/hermes/profiles/critic"` shows `config.yaml`.

3. **Copy config from reviewer, change effort.**
   Copy `profiles/reviewer/profile.yaml` and `config.yaml` over the critic ones, then edit:
   - `profile.yaml` description →
     `Design critic. Looks at the dashboard in a fake church and makes one card per finding. Never edits code.`
   - `config.yaml` `agent.reasoning_effort: high`
   - Keep `platform_toolsets.cli` the same as reviewer (browser, clarify, file, kanban, memory, session_search, skills, terminal, todo, vision, web).
   Verify: `grep -c "kanban" "$LOCALAPPDATA/hermes/profiles/critic/config.yaml"` → at least 1; `grep -c cronjob .../config.yaml` → only in the `known_builtin_toolsets` list, not in `platform_toolsets`.

4. **Give it the skills it needs.** Copy folders `impeccable` and `design-taste-frontend` from `profiles/reviewer/skills/` into `profiles/critic/skills/` (reviewer already has both; do not touch the default profile).
   Verify: `ls "$LOCALAPPDATA/hermes/profiles/critic/skills"` lists both.

5. **Write `profiles/critic/SOUL.md`** with exactly:

   ```
   You are Critic. You judge the design of the Church Manager dashboard. You never edit product code.

   ## Job (card title starts with "DESIGN CRITIQUE")
   1. `kanban_show` your card. The body may name pages (People, Calendar, Money...). No names = all pages.
   2. Make a fake church OUTSIDE OneDrive: `python -m churchmgr.fake "$LOCALAPPDATA/Temp/critic-church"` then `python app.py --copy "$LOCALAPPDATA/Temp/critic-church"`. Never open the real church copy in `%LOCALAPPDATA%\ChurchManager\`.
   3. Open each page in the browser. Load `impeccable` and run its `critique` command. Use `design-taste-frontend` for taste checks. Check: hierarchy, spacing, contrast, small screens, Vietnamese text fit (long words, diacritics), empty states, words that break GLOSSARY.md.
   4. Never show or quote a private note.
   5. Sort findings: P0 = Blocker, P1 = Major, P2/P3 = Minor.
   6. For each P0 and P1 finding, create ONE card:
      `kanban_create` title `GOAL: <short fix title>`, assignee `orchestrator`, body = page, what is wrong, why it matters to the pastor, where in the file (`web/...` or `churchmgr/pages/...`) if you know, suggested fix.
      Before creating, `kanban_list` the board and skip a finding that already has an open card with the same title.
   7. Put all P2/P3 findings in ONE card `GOAL: Design polish (P2/P3 list)`.
   8. Stop the app. `kanban_complete` with a summary: counts per level and the created card ids in `created_cards`.

   ## Limits
   Report only. Do not fix. Do not create more than 10 cards per run (merge the rest into the polish card).
   ```
   Verify: `wc -l .../critic/SOUL.md` > 10.

6. **Route to it.** Add one line to `profiles/orchestrator/SOUL.md` (append under its routing section; read the file first and match its style):
   `If the pastor asks for a design critique, create a card titled "DESIGN CRITIQUE: <pages>" assigned to critic. Findings come back as GOAL cards for you.`
   Verify: `grep -n "DESIGN CRITIQUE" .../orchestrator/SOUL.md` → one hit.

7. **Document + rollback.** Append to `ROLLBACK-agent-team.md` (repo root):
   ```
   ## Critic profile (2026-11-14)
   | Change | Undo |
   |---|---|
   | profile critic | hermes profile delete critic |
   | orchestrator SOUL.md: DESIGN CRITIQUE line | remove that line (backup: backups/critic-2026-11-14-orchestrator) |
   ```
   Also add `critic` to the profile list in `README.md` only if README lists the other profiles (check: search for `reviewer`). If not, skip.

8. **Smoke test (real run).**
   `hermes kanban --board church-manager create "DESIGN CRITIQUE: People page" --assignee critic --body "Critique the People page only. Max 2 findings for this test."`
   Wait for the dispatcher. Then `hermes kanban --board church-manager list`.
   Expect: critic card `done`; 1-3 new `GOAL:` cards assigned to `orchestrator`; no card body contains a private note. If the critic cannot start the app, fix the SOUL command, not the app.
   Then archive or delete the test cards so the orchestrator does not build them (ask the pastor which to keep).

9. **Repo check.** `python verify.py` → prints `ALL ... CHECKS PASS`, exit 0. (No code changes expected; this proves the repo is untouched.) `git status --short` should show only `ROLLBACK-agent-team.md` (and README if edited) as new changes from this plan.

10. **Commit** (only if the pastor asks): `git add ROLLBACK-agent-team.md && git commit -m "docs: critic profile rollback notes"`. Profile files are outside the repo and are not committed.

## Tests / validation
No Python code, so no unit test. Validation is step 3 to 6 greps plus the step 8 smoke run and step 9 `verify.py`.

## Risks / open questions
- Card flood: each finding becomes a `GOAL:` card the orchestrator will build. Mitigation: max 10 cards, dedupe by title, P2/P3 merged. Question: should P1 cards wait for pastor approval first (use `initial_status: blocked`)? Default in this plan: no.
- Critic cards get built by coder with no pastor check. Option: create them `triage` so the pastor picks. Not done (YAGNI) unless asked.
- AGENTS.md writes by workers need human approval and time out: this plan does not touch AGENTS.md.
- `hermes profile create` flags may differ on this version; if step 2 fails, run `hermes profile create --help` and stop and ask.
- Not covered: scheduled/repeating critique (cron). Add later only if wanted.
