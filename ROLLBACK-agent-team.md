# Rollback: agent team for Church Manager (2026-11-01)

Backups of old config: C:/Users/danng/AppData/Local/hermes/backups/agent-team-2026-11-01/

## Old values (before any change)
- Profiles: default (claude-sonnet-5-5), researcher (claude-sonnet-5-5)
- kanban.orchestrator_profile = orchestrator (profile did not exist)
- kanban.default_assignee = orchestrator
- kanban.max_in_progress = 2
- Boards: default only
- Project folder was NOT a git repo
- agent.reasoning_effort (default profile) = none

## Changes and undo
| Change | Undo |
|---|---|
| git init in project folder | delete the `.git` folder |
| profile orchestrator | hermes profile delete orchestrator |
| profile coder | hermes profile delete coder |
| profile reviewer | hermes profile delete reviewer |
| profile tester | hermes profile delete tester |
| board church-manager | hermes kanban boards rm church-manager (check `boards --help`) |
| researcher: only kanban toolset turned ON | hermes -p researcher tools disable kanban |

## Actual result (done)
- `--clone-from default` failed on Windows (WinError 5 on plugins/superpowers). Profiles were made with `--no-skills` (blank), then configured by hand.
- Profiles: orchestrator(high), coder(xhigh), reviewer(medium), tester(high), all claude-opus-5-5. Effort key: `agent.reasoning_effort` in each profile's config.yaml (the CLI warns it is "not recognized"; the value is saved).
- Tools per role: kanban ON everywhere. delegation, cronjob, image_gen, tts, computer_use OFF. code_execution OFF for orchestrator and reviewer. tester: browser.backend=off.
- researcher: unchanged except `kanban` toolset ON.
- Board `church-manager` (workdir = this repo). Active board switched to it (old: `default`; undo: `hermes kanban boards switch default`).
- kanban.orchestrator_profile/default_assignee/max_in_progress were already these values.
- SOUL.md written for the 4 new profiles. No old SOUL.md was overwritten.

## Skills copied (user said keep + copy)
Copied into profiles orchestrator, coder, reviewer, tester (folder `<profile>/skills/`):
design-taste-frontend (from C:/Users/danng/.hermes/skills), impeccable, mattpocock (33 skills),
ponytail/ (6 skills: ponytail, -audit, -debt, -gain, -help, -review; copied from the plugin as plain skills, the plugin hooks are NOT copied).
Undo: delete those folders from each profile's skills/ folder (they hold nothing else; each profile had only autonomous-ai-agents/hermes-agent before).
