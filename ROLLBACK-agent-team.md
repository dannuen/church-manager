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
