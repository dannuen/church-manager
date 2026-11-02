# Research: how Ryoku connects Hermes to Rashin, and what Church Manager can copy

Date: 2026-11-02. Method: primary sources only (Ryoku repo files on
raw.githubusercontent.com, the GitHub tree listing, and the Hermes Agent docs).
Where I could not confirm something, I say "not confirmed".

## 1. Short answer

1. Rashin is Ryoku's optional "agent OS": a Go daemon (`ryoku-rashin`) plus a markdown "vault" that describes the machine.
2. Hermes does NOT connect to Rashin by MCP. Rashin's own doc says it is "not an MCP server".
3. The link is files and commands: a skill (symlinked into `~/.hermes/skills/ryoku`), a pointer block in Hermes `MEMORY.md`, a vault with `AGENTS.md`, and CLI tools like `ryoku owner` and `ryoku-rashin logs`.
4. Safety is mostly rules in the skill plus an approval gate: read-only tool calls auto-run, everything else asks. Ask mode is strictly read-only.
5. For Church Manager, the smallest good step is an `AGENTS.md` + a Hermes skill + a tiny read-only CLI. A stdlib MCP server is the next step, only if you want Hermes to call tools directly.

## 2. How Ryoku does it

### 2.1 What Rashin is

- Rashin ("compass needle") is "Ryoku's optional agent OS: a machine-generated knowledge vault, a local daemon, and frontends for installed agent harnesses". Hermes is one of the supported agents (also Codex, Claude Code, opencode, omp, Gemini CLI). [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md)
- Language: Go. "One Go program (module `ryoku-rashin`), stdlib plus one dependency (`github.com/coder/websocket`)". The web console is Svelte, built and embedded into the Go binary. [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md)
- Where in the repo: daemon `ryoku/rashin/backend/` (Go), console `ryoku/rashin/web/` (Svelte), GTK window `ryoku/rashin/app/` (C++), skill `ryoku/rashin/skills/ryoku/`, wiki `ryoku/rashin/wiki/`, systemd unit `ryoku/rashin/systemd/ryoku-rashin.service`. [GitHub tree](https://api.github.com/repos/Ryoku-dev/ryoku/git/trees/main?recursive=1)
- It is off by default, local only, and binds `127.0.0.1:3600`. Gate file: `~/.config/ryoku/rashin.json` = `{ "enabled": false, "port": 3600 }`. [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md)
- Hermes brings its own model. Rashin is "not a bundled LLM". [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md)

### 2.2 The vault (the main idea)

- The vault is a folder of markdown at `~/.local/share/ryoku/rashin/`. Every agent reads it. Files: `AGENTS.md`, `system.md`, `desktop.md`, `packages.md`, `user.md`, `habits.md`, `ownership.md`, `logs.md`, plus agent-writable `memory/` and `journal/`. [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md)
- Generated files are fenced with `<!-- rashin:generated:begin -->` / `<!-- rashin:generated:end -->`. A reindex rewrites only inside the fence. Agents must not edit generated files. [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md)
- Rashin's stated reason for markdown instead of MCP: "Markdown files are the interface every agent already speaks. MCP is a possible v2." [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md)

### 2.3 How Hermes is wired in

Three wiring paths, all file based:

1. Skill link. `ryoku-rashin wire` symlinks the shipped skill folder into each agent's skills folder, including `~/.hermes/skills/ryoku` and each `~/.hermes/profiles/*/skills/ryoku`. `unwire` removes only symlinks that point at the skill. The doctor re-runs `wire` if a link is missing. [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md)
2. Memory pointer block. Wiring appends a marker-fenced block to Hermes `~/.hermes/memories/MEMORY.md` (other agents: `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, and so on). The block says: a system map exists at `~/.local/share/ryoku/rashin/`, read `AGENTS.md` first. It is idempotent and reversible: `<!-- ryoku-rashin:begin -->` ... `<!-- ryoku-rashin:end -->`. [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md), code: [hermes.go](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/backend/hermes.go) (`hermesMemory()`, `WireHermesMemory()`)
3. ACP chat backend. The Rashin window's Agent/Chat drives Hermes through ACP (Agent Client Protocol, JSON-RPC over stdio) by running the `hermes acp` child process. Setup runs `hermes acp --check` to verify. [setup.go](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/backend/setup.go), [acp.go](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/backend/acp.go)

Also: "Fix with AI" opens Hermes in a real terminal, in the vault folder, with the problem as the first message. Hermes cannot start interactively with a first message, so it runs the brief as one query and then resumes that session. [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md)

Hermes config is never edited by hand. "Wiring uses the supported interface, never a raw edit of `~/.hermes/config.yaml`." An existing Hermes is never reinstalled or re-onboarded. [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md), [setup.go](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/backend/setup.go)

### 2.4 What Hermes can "call" (names)

Not MCP tools. Plain commands that the skill tells Hermes to run:

| Command | Job | Source |
|---|---|---|
| `ryoku-rashin logs <target> [--since] [--lines]` | Gather units, journal, coredumps, OOM, app logs, package history into one bounded markdown bundle. Read-only, no root, always exits 0. | [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md) |
| `ryoku owner <path>` (`--map`, `--json`) | Says who owns a file (`ryoku`, `generated`, `store`, `seed`, `user-override`) and where a change belongs. | [SKILL.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/skills/ryoku/SKILL.md) |
| `ryoku-rashin status [--json]`, `index`, `wire`, `unwire`, `enable`, `disable`, `setup`, `serve`, `ask`, `terminal`, `fix ...`, `repo-index` | Daemon and wiring control. | [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md) |
| `ryoku doctor --json`, `ryoku rollback`, `ryoku reset <path>`, `ryoku update` | System health, undo, update. | [SKILL.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/skills/ryoku/SKILL.md), [troubleshoot.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/skills/ryoku/troubleshoot.md) |
| `ryoku-shell`, `ryoku-hub`, `ryogami` | Owner tools for bar, settings, wallpaper. | [SKILL.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/skills/ryoku/SKILL.md) |
| `prowl overview / search / find / def / outline / references / impact` | Read-only code index (separate tool "Prowl"). AGENTS.md says to run it before grep. | [AGENTS.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/AGENTS.md) |

Prowl note: AGENTS.md says "If your harness also wires Prowl as an MCP server, the same index is reachable there; the CLI needs no server and is the first choice." So MCP exists for Prowl only as an optional extra, and the docs prefer CLI. [AGENTS.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/AGENTS.md)

### 2.5 The skill

- One skill named `ryoku`: `SKILL.md` plus topic guides `gui.md`, `bar.md`, `plugins.md`, `feature.md`, `troubleshoot.md`, `wm.md`, `build.md`. Folder: `ryoku/rashin/skills/ryoku/`. The package installs it to `/usr/share/ryoku/skills/ryoku`. [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md)
- It has YAML frontmatter (`name`, `description` with trigger words) and sections: when to use, read the vault first, answer policy, safety rules, command discovery, decision framework, example requests. [SKILL.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/skills/ryoku/SKILL.md)
- `troubleshoot.md` is the break/fix playbook: 1 gather evidence, 2 diagnose before touching, 3 fix through the owning command, 4 verify, 5 rollback paths. It ends with "Never bypass a safety gate". [troubleshoot.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/skills/ryoku/troubleshoot.md)

### 2.6 Repo-level agent context (AGENTS.md)

- The repo root `AGENTS.md` has "Cardinal rules" (one purpose per file, repo is source of truth, never `--no-verify`, commit subject format, and so on) and a Prowl block between `<!-- prowl-agent -->` markers. [AGENTS.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/AGENTS.md)

## 3. Safety model

What Ryoku does, with proof:

1. Local only. Daemon binds `127.0.0.1`. WebSocket upgrades check the Origin host. Mutating routes reject cross-origin browser calls. No auth, because it is single user and local. [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md), [server.go](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/backend/server.go) (`allowLocalMutation`, `loopbackOrigin`)
2. Three approval modes for the agent's tool calls: `read-only` (default), `ask`, `auto`. In `read-only`, calls that only read run without a prompt; everything else asks. Unknown values fall back to `read-only`. [config.go](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/backend/config.go)
3. The read-only check is deny-first. "Anything it cannot prove is a pure read returns false." Edit, delete, move, switch_mode and unknown kinds ask. [readonly.go](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/backend/readonly.go)
4. Secret paths always ask, even for reads. The marker list includes `.ssh`, `.gnupg`, `.env`, `.netrc`, `/etc/shadow`, `.hermes`, `token`, `secret`, `password`, and more. [readonly.go](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/backend/readonly.go)
5. Ask mode (quick questions) is strictly read-only. It answers a permission request by auto-allowing only proven reads, and rejecting the rest. A denied write returns `needsAgent` instead of acting. [acp.go](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/backend/acp.go) (`handleAgentRequest`, `session/request_permission`), [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md)
6. Terminal commands are tiered `read / write / system / danger`. The classifier is "deny-first and pessimistic: an unknown or unparseable command classifies as write, never read". [danger.go](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/backend/danger.go)
7. Rules for agents (in skill and vault): ask `ryoku owner <path>` before editing; never edit shipped files; user changes go to `~/.config/ryoku/user_edits`; prefer a command over a file edit; prefer a reversible fix; ask before anything destructive or needing sudo; record work in `journal/`. [SKILL.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/skills/ryoku/SKILL.md), [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md)
8. Setup never uses sudo. [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md)
9. Log gathering is read-only, short-timeout, no root, bounded. [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md)
10. The Prowl token never goes to the browser. Rashin proxies with the token added server side. [docs/rashin.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md)

Polkit: the repo has polkit code (`ryoku/shell/ipc/polkit.go`, a Quickshell polkit agent UI). I did not find it tied to Hermes or Rashin permissions. So: polkit as part of the Hermes safety model is **not confirmed**. It looks like the desktop's own auth prompt agent.

## 4. rashin-reviewer and the commit gate

What is confirmed:

- `.githooks/` holds `commit-msg`, `pre-commit`, `pre-push`, `post-commit`. Turn on with `git config core.hooksPath .githooks`. [development.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/development.md)
- `commit-msg` blocks: no impact label `[global|installation|system|ryoku|docs|test|tooling|release]`, subject over 72 chars or ending in a period, AI/bot attribution or co-author trailers, em-dash, and a malformed `Note:` trailer. [commit-msg](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/.githooks/commit-msg)
- `pre-commit` runs in order: em-dash scan; `bash -n` on staged scripts; filler-comment scan; "every user config is delivered" check; compositor-isolation check; then step 6, the review gate. [pre-commit](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/.githooks/pre-commit)
- Step 6 runs `rashin-reviewer hook run pre-commit`. Exit 0 = pass, 1 = blocking issues, other = reviewer failed to run (also blocks). If the reviewer is not installed, the step is skipped, unless the clone sets `git config ryoku.reviewGate required`, which then refuses to commit. [pre-commit](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/.githooks/pre-commit)
- What the gate checks (from the docs): no secrets or conflict markers; no JSON/YAML/TOML/Python/Lua/QML file left unparseable; ShellCheck (CI flags) and gofmt clean on added lines. `rashin-reviewer review` adds a model review of uncommitted work, steered by `.coderabbit.yaml`. [development.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/development.md)
- `.rashin-reviewer.yaml`: `block_at: major` (severity that blocks), a `vendored` list (skip style checks, keep security and syntax checks), `tools` overrides (bash syntax off because pre-commit does it; shellcheck args match CI), and `rules.allow` path allow-lists (for example `large-file`, `debug-leftover`). An intentional hit is marked in code with `rashin-reviewer:allow <rule>`. `rashin-reviewer rules` lists all rules. [.rashin-reviewer.yaml](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/.rashin-reviewer.yaml), [development.md](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/development.md)
- `pre-push`: `main` moves only as a release fast-forward from `unstable-dev` (needs `RYOKU_RELEASE_PUSH=1`); never rewritten or deleted; ShellCheck on pushed shell files. [pre-push](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/.githooks/pre-push)
- `post-commit`: a non-blocking delivery report. [post-commit](https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/.githooks/post-commit)

Not confirmed: the source code of `rashin-reviewer`. It is not in the Ryoku tree (no matching path). It is a separate binary found on PATH or at `~/.local/bin/rashin-reviewer`. Its language, install method and full rule list are not confirmed.

Important: `rashin-reviewer` is a code-review tool for Ryoku developers. It is not part of how Hermes operates the running system. Do not mix the two.

## 5. Patterns worth copying (summary)

1. Give the agent a map first (vault, `AGENTS.md`). It beats letting the agent explore.
2. Mark generated files and fence them. Keep one place the agent may write (`memory/`, `journal/`).
3. One gather command that returns a bounded, read-only bundle (`ryoku-rashin logs`).
4. A skill with trigger words, a decision order, and a break/fix playbook.
5. Deny-first safety: unknown means "ask", never "allow".
6. Idempotent, reversible wiring (marker blocks, symlinks, `wire`/`unwire`, status shows drift).
7. Never hand-edit the agent's own config. Use its supported interface.
8. Log what the agent did in a journal.

## 6. Suggested plan for Church Manager

### 6.1 What Church Manager has now (verified in code)

- Pure Python 3.14 stdlib. `python app.py` serves on 127.0.0.1:8765. Only HTML form POSTs; every POST needs a same-origin `Origin`/`Referer` (`churchmgr/server.py`). There is no JSON API, so Hermes cannot just call a URL.
- Logic lives in `churchmgr/*.py` and takes a sqlite connection from `db.connect(path)`. Church copy path comes from `paths.resolve(...)` and `%LOCALAPPDATA%\ChurchManager\<slug>\church.db`.
- `handover._connect_ro(path)` already opens SQLite read-only with `?mode=ro`. That is the exact pattern for a read-only agent door.
- `story.person_story(conn, person_id, include_private=False)` defaults to no private notes. `people.list_private_notes` / `add_private_note` / `update_private_note` are the only code that touches the `private_note` table (plus `story` with `include_private=True`, and `handover`).
- Python `mcp` SDK is not installed here and Church Manager must stay dependency free (GOAL.md rule 6). MCP over stdio is newline-delimited JSON-RPC, so a stdlib server is possible but is code we would write and test ourselves.

### 6.2 Ranked options (smallest first)

| Rank | Option | New code | Dependencies | What Hermes gets |
|---|---|---|---|---|
| 1 | `AGENTS.md` + Hermes skill (docs only) | none | none | Map of the app, rules, how to run `python verify.py`. Good for debugging and developing the app. No live data. |
| 2 | Add a read-only CLI: `python -m churchmgr.agent <command> --json` | about 100 lines | none | Hermes runs it with its terminal tool. Live read access. Same pattern as Ryoku (commands, not MCP). |
| 3 | Stdlib MCP server `mcp_churchmgr.py` wrapping the same functions | about 200 lines | none (hand-written JSON-RPC) | Named tools Hermes lists and filters with `tools.include`. Needs its own tests. |
| 4 | Write tools (add person, add offering, mark visit) | extra | none | Hermes can change data. Not recommended until read-only has run for a while. |

Recommendation: do rank 1 now, rank 2 next. Move to rank 3 only if you want tool names in Hermes, because the CLI gives the same data with less code. This follows Ryoku's own choice (files and commands first, MCP "a possible v2").

### 6.3 Rank 1: AGENTS.md and a skill

- Add `AGENTS.md` at the repo root. Keep it short: what the app is; use glossary words from `GLOSSARY.md`; `python verify.py` must exit 0; data lives outside OneDrive; Private notes rules; never edit `church.db` by hand; routes live in `churchmgr/pages/*.py`; logic in `churchmgr/*.py`.
- Add a Hermes skill `church-manager` (folder with `SKILL.md`; Hermes skills use frontmatter `name`, `description`, and sections When to Use / Procedure / Pitfalls / Verification). Source: [Hermes skills docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills). Copy it to `~/.hermes/skills/church-manager` (on Windows: `%USERPROFILE%\.hermes\skills\church-manager`; exact Windows path not confirmed in the docs I read, check with `hermes skills`). Hermes can also scan external skill folders; see the "External Skill Directories" section of the same page (not read in full, so not confirmed in detail).
- Skill content to copy from Ryoku's `troubleshoot.md`: gather evidence first (run `python verify.py`, read the failing test), diagnose, change the owning module, verify, say how to undo.

### 6.4 Rank 2: read-only CLI over existing modules

Open the DB the way `handover._connect_ro` does: `sqlite3.connect(Path(p).as_uri() + "?mode=ro", uri=True)`, with `row_factory = sqlite3.Row`. A write attempt then fails at the SQLite level. Do not use `db.connect` for this door, because it opens read/write.

Proposed tools (names are proposals; functions are real):

| Proposed tool | Real function | Read/Write |
|---|---|---|
| `find_person(q, limit)` | `search.search_persons(conn, q, limit)` | read |
| `person_story(person_id)` | `story.person_story(conn, person_id, include_private=False)` (fixed False) | read |
| `list_persons(status_id)` | `people.list_persons(conn, status_id)` (strip `note`? see 6.6) | read |
| `list_families()` / `family_members(family_id)` | `people.list_families`, `people.family_members` | read |
| `needs_visit()` | `care.needs_visit(conn)` | read |
| `care_log(person_id)` | `care.care_log(conn, person_id)` | read |
| `calendar_between(start, end)` | `calendar.items_between(conn, start, end)` | read |
| `recent_head_counts(n)` | `calendar.recent_head_counts(conn, n)` | read |
| `month_totals(year, month)` | `money.month_totals(conn, year, month)` | read |
| `list_offerings(start, end)` / `list_expenses(start, end)` | `money.list_offerings`, `money.list_expenses` | read (see 6.6) |
| `next_sent_number(year)` | `sent.next_number(conn, year)` | read |
| `list_sent_documents(year)` | `sent.list_sent_documents(conn, year)` | read |
| `doctor()` | new code: `PRAGMA integrity_check`, `PRAGMA user_version`, row counts (do not call `db.open_church_copy`: it opens read/write) | read |

Write tools, later and one at a time, each behind Hermes approval:

| Proposed tool | Real function | Note |
|---|---|---|
| `add_person` | `people.add_person` | validates through `text.clean_name` |
| `add_offering` / `add_expense` | `money.add_offering` / `money.add_expense` | amounts through `money.parse_amount` |
| `plan_visit` / `mark_visit_done` | `care.plan_visit` / `care.mark_visit_done` | |
| `set_head_count` | `calendar.set_head_count` | |
| `add_sent_document` | `sent.add_sent_document` | takes a number: not undoable by design |

Do NOT expose: `add_private_note`, `update_private_note`, `list_private_notes`, `person_story(include_private=True)`, `delete_*`, `handover.make_handover`, `db.create_church_copy`, anything that moves or deletes files in `documents/`.

A tiny self-check test is needed: open a fake church (`fake.build_fake_church`), run every read command, assert no output contains any text from `private_note` (reuse the idea in `handover.check_no_private_text`), and assert a write attempt on the read-only connection raises `sqlite3.OperationalError`. Add it to `verify.py`.

### 6.5 Rank 3: MCP server config (only if wanted)

A stdlib stdio MCP server needs three JSON-RPC methods: `initialize`, `tools/list`, `tools/call` (plus the `notifications/initialized` notification). I have not read the MCP spec in this research, so exact message shapes are **not confirmed**; check the official MCP spec before writing it.

Hermes side, from the official docs (file `~/.hermes/config.yaml`, key `mcp_servers`, stdio uses `command`, `args`, `env`, `cwd`; tools are filtered with `tools.include` / `tools.exclude`; tool names appear as `mcp_<server>_<tool>`): [Hermes MCP docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)

```yaml
mcp_servers:
  churchmgr:
    command: "python"
    args: ["C:/Users/danng/OneDrive/Desktop/Church Manager Hermes/mcp_churchmgr.py"]
    env:
      CHURCH_MANAGER_COPY: "C:/Users/danng/AppData/Local/ChurchManager/<slug>"
    timeout: 30
    tools:
      include:
        - find_person
        - person_story
        - needs_visit
        - calendar_between
        - month_totals
        - next_sent_number
```

Notes:
- `include` is an allow-list; the docs say `include` wins over `exclude`. Use `include`, never `exclude`, so a new tool is hidden until you add it.
- `CHURCH_MANAGER_COPY` is the real env var name (`paths.ENV_COPY`, read by `paths.resolve`). The server can reuse `paths.resolve()` to find the copy.
- Run `python` from a path outside OneDrive for the data (already enforced by `paths.check_not_onedrive`).
- Whether Hermes supports `tools.include` for write-vs-read approval, `trust`, or `readOnlyHint` for stdio servers is partly documented (the docs mention `trust: untrusted` and `readOnlyHint: true`) but I did not read that section in full: **not confirmed** in detail.
- Reload with `/reload-mcp` or restart Hermes after editing config (stated in the docs).

### 6.6 How Private notes stay protected

1. Never offer a tool that reads `private_note`. The agent door has no path to `list_private_notes`.
2. `person_story` is called with `include_private=False` fixed in code, not as a parameter.
3. Open the DB with `mode=ro`, so no tool can write by accident.
4. Do not use `SELECT *` on `person`: the `person.note` column is a normal note, not private (schema comment says so), but it may still be sensitive. Decide with the pastor whether `note`, `phone`, `address`, `birth_date` go to the model. Default suggestion: return `id`, `full_name`, `status_name` only, and add more fields on request.
5. Offering and giving data is sensitive. `giving_statement` is for printing to a person; do not give it to an agent without a clear decision.
6. Add the automatic leak check from 6.4 to `verify.py`.
7. Remember that anything a tool returns is sent to the model provider you chose in Hermes. This conflicts with the project rule "Offline only. No cloud". Using a local model (for example through Ollama) keeps data on the machine; with a cloud model, church data leaves the machine. This must be decided by the user. See open questions.

### 6.7 Hermes-side safety for Church Manager

- Keep Hermes approvals on (Hermes has approval modes; `/yolo` skips prompts per the MCP docs, so do not use it with write tools). 
- Start with read tools only.
- Use a separate Hermes profile for church work (`hermes profile create church`; profiles are documented as separate folders under `~/.hermes/profiles/<name>`, and Ryoku wires skills into `~/.hermes/profiles/*/skills/ryoku`). That keeps church memory and skills apart from other projects. [Skills docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) mention `hermes profile create research --no-skills`.
- Tell the skill: never run `app.py` against the real church copy while debugging code; use `fake.build_fake_church` in a temp folder.

### 6.8 Debugging the app itself (the Ryoku "operate the system" idea)

Ryoku lets Hermes debug because there is one gather command plus a map. Church Manager equivalent:

- A `python -m churchmgr.agent doctor --json` command that reports: copy folder path, schema version, `PRAGMA integrity_check`, row counts per table, is the path inside OneDrive, is port 8765 free. Read-only.
- A skill playbook: run `verify.py`, read the first failure, find the module from `AGENTS.md`, fix, rerun.

## 7. Open questions / not confirmed

1. Where `rashin-reviewer` comes from, its language and its full rule list: not confirmed (not in the Ryoku tree).
2. Whether polkit is part of any Hermes/Rashin permission flow: not confirmed; I found only a desktop polkit agent UI.
3. Exact wording of the MCP protocol messages for a stdlib server: not read; check the MCP spec first.
4. Hermes on Windows: the exact skills path, config path, and `hermes acp` behavior on Windows were not verified. The Ryoku docs and code are Linux only.
5. Hermes `trust`, `readOnlyHint` and approval behavior for MCP tools: mentioned in the docs, not read in full here.
6. Data privacy: is a cloud model allowed to see church data? GOAL.md says offline only. Needs a decision from the user. Recommendation: local model, or restrict tools to non-personal data (counts, totals, next number).
7. Which fields of `person` may leave the machine (see 6.6).
8. Does the pastor want Hermes to write data at all, or only read and help debug code?
9. Ryoku claims about the Rashin window (ACP, approvals UI) are about Ryoku's own app. Church Manager does not need ACP. Using it is not recommended.

## 8. Sources

Ryoku repo (raw files, branch `main`):
- https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/AGENTS.md
- https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/.rashin-reviewer.yaml
- https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/.githooks/commit-msg
- https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/.githooks/pre-commit
- https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/.githooks/pre-push
- https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/.githooks/post-commit
- https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/rashin.md
- https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/docs/development.md
- https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/skills/ryoku/SKILL.md
- https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/skills/ryoku/troubleshoot.md
- https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/backend/hermes.go
- https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/backend/setup.go
- https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/backend/acp.go
- https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/backend/config.go
- https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/backend/readonly.go
- https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/backend/danger.go
- https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/rashin/backend/server.go
- https://raw.githubusercontent.com/Ryoku-dev/ryoku/main/ryoku/cli/internal/doctor/reconcile_hermes_agent.go
- https://api.github.com/repos/Ryoku-dev/ryoku/git/trees/main?recursive=1

Hermes Agent official docs:
- https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp
- https://hermes-agent.nousresearch.com/docs/user-guide/features/skills

Church Manager code read for this plan: `churchmgr/db.py`, `paths.py`, `search.py`, `people.py`, `care.py`, `calendar.py`, `money.py`, `sent.py`, `story.py`, `handover.py`, `app.py`, `docs/GOAL.md`.
