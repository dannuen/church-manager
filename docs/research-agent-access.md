# Research: how Hermes can safely read and help run Church Manager

Date: 2026-11-02. Method: Church Manager code and the Hermes Agent docs.
Where I could not confirm something, I say "not confirmed".

## 1. Short answer

1. The smallest good step is an `AGENTS.md` + a Hermes skill + a tiny read-only CLI.
2. Use files and commands first. A stdlib MCP server is a later step, only if you want Hermes to call named tools.
3. Safety is deny-first: read-only calls run, everything else asks. Unknown means "ask", never "allow".

## 2. Patterns to use

1. Give the agent a map first (`AGENTS.md`). It beats letting the agent explore.
2. Mark generated files and fence them. Keep one place the agent may write.
3. One gather command that returns a bounded, read-only report.
4. A skill with trigger words, a decision order, and a break/fix playbook: gather evidence, diagnose, fix in the owning module, verify, say how to undo.
5. Deny-first safety: a call that cannot be proven a pure read must ask.
6. Secret paths (`.env`, keys, tokens, passwords) always ask, even for reads.
7. Never hand-edit the agent's own config. Use its supported interface.
8. Log what the agent did.

## 3. Plan for Church Manager

### 3.1 What Church Manager has now (verified in code)

- Pure Python 3.14 stdlib. `python app.py` serves on 127.0.0.1:8765. Only HTML form POSTs; every POST needs a same-origin `Origin`/`Referer` (`churchmgr/server.py`). There is no JSON API, so Hermes cannot just call a URL.
- Logic lives in `churchmgr/*.py` and takes a sqlite connection from `db.connect(path)`. Church copy path comes from `paths.resolve(...)` and `%LOCALAPPDATA%\ChurchManager\<slug>\church.db`.
- `handover._connect_ro(path)` already opens SQLite read-only with `?mode=ro`. That is the exact pattern for a read-only agent door.
- `story.person_story(conn, person_id, include_private=False)` defaults to no private notes. `people.list_private_notes` / `add_private_note` / `update_private_note` are the only code that touches the `private_note` table (plus `story` with `include_private=True`, and `handover`).
- Church Manager must stay dependency free (GOAL.md rule 6). MCP over stdio is newline-delimited JSON-RPC, so a stdlib server is possible but is code we would write and test ourselves.

### 3.2 Ranked options (smallest first)

| Rank | Option | New code | Dependencies | What Hermes gets |
|---|---|---|---|---|
| 1 | `AGENTS.md` + Hermes skill (docs only) | none | none | Map of the app, rules, how to run `python verify.py`. Good for debugging and developing the app. No live data. |
| 2 | Add a read-only CLI: `python -m churchmgr.agent <command> --json` | about 100 lines | none | Hermes runs it with its terminal tool. Live read access. |
| 3 | Stdlib MCP server `mcp_churchmgr.py` wrapping the same functions | about 200 lines | none (hand-written JSON-RPC) | Named tools Hermes lists and filters with `tools.include`. Needs its own tests. |
| 4 | Write tools (add person, add offering, mark visit) | extra | none | Hermes can change data. Not recommended until read-only has run for a while. |

Recommendation: do rank 1 now, rank 2 next. Move to rank 3 only if you want tool names in Hermes, because the CLI gives the same data with less code.

### 3.3 Rank 1: AGENTS.md and a skill

- Add `AGENTS.md` at the repo root. Keep it short: what the app is; use glossary words from `GLOSSARY.md`; `python verify.py` must exit 0; data lives outside OneDrive; Private notes rules; never edit `church.db` by hand; routes live in `churchmgr/pages/*.py`; logic in `churchmgr/*.py`.
- Add a Hermes skill `church-manager` (folder with `SKILL.md`; frontmatter `name`, `description`, and sections When to Use / Procedure / Pitfalls / Verification). Source: [Hermes skills docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills). Exact Windows skills path not confirmed; check with `hermes skills`.
- Playbook: run `python verify.py`, read the first failure, find the module from `AGENTS.md`, fix, rerun, say how to undo.

### 3.4 Rank 2: read-only CLI over existing modules

Open the DB the way `handover._connect_ro` does: `sqlite3.connect(Path(p).as_uri() + "?mode=ro", uri=True)`, with `row_factory = sqlite3.Row`. A write attempt then fails at the SQLite level. Do not use `db.connect` for this door, because it opens read/write.

Proposed tools (names are proposals; functions are real):

| Proposed tool | Real function | Read/Write |
|---|---|---|
| `find_person(q, limit)` | `search.search_persons(conn, q, limit)` | read |
| `person_story(person_id)` | `story.person_story(conn, person_id, include_private=False)` (fixed False) | read |
| `list_persons(status_id)` | `people.list_persons(conn, status_id)` (strip `note`? see 3.6) | read |
| `list_families()` / `family_members(family_id)` | `people.list_families`, `people.family_members` | read |
| `needs_visit()` | `care.needs_visit(conn)` | read |
| `care_log(person_id)` | `care.care_log(conn, person_id)` | read |
| `calendar_between(start, end)` | `calendar.items_between(conn, start, end)` | read |
| `recent_head_counts(n)` | `calendar.recent_head_counts(conn, n)` | read |
| `month_totals(year, month)` | `money.month_totals(conn, year, month)` | read |
| `list_offerings(start, end)` / `list_expenses(start, end)` | `money.list_offerings`, `money.list_expenses` | read (see 3.6) |
| `next_sent_number(year)` | `sent.next_number(conn, year)` | read |
| `list_sent_documents(year)` | `sent.list_sent_documents(conn, year)` | read |
| `doctor()` | new code: `PRAGMA integrity_check`, `PRAGMA user_version`, row counts, copy path, is it inside OneDrive, is port 8765 free (do not call `db.open_church_copy`: it opens read/write) | read |

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

### 3.5 Rank 3: MCP server config (only if wanted)

A stdlib stdio MCP server needs three JSON-RPC methods: `initialize`, `tools/list`, `tools/call` (plus the `notifications/initialized` notification). Exact message shapes are **not confirmed**; check the official MCP spec before writing it.

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
- `CHURCH_MANAGER_COPY` is the real env var name (`paths.ENV_COPY`, read by `paths.resolve`).
- `paths.check_not_onedrive` already keeps the data outside OneDrive.
- `trust` and `readOnlyHint` are mentioned in the docs but not read in full: **not confirmed**.
- Reload with `/reload-mcp` or restart Hermes after editing config.

### 3.6 How Private notes stay protected

1. Never offer a tool that reads `private_note`.
2. `person_story` is called with `include_private=False` fixed in code, not as a parameter.
3. Open the DB with `mode=ro`, so no tool can write by accident.
4. Do not use `SELECT *` on `person`. `person.note` is not private but may be sensitive. Decide with the pastor whether `note`, `phone`, `address`, `birth_date` go to the model. Default: return `id`, `full_name`, `status_name` only.
5. Offering and giving data is sensitive. Do not give `giving_statement` to an agent without a clear decision.
6. Add the leak check from 3.4 to `verify.py`.
7. Anything a tool returns is sent to the model provider chosen in Hermes. This conflicts with the rule "Offline only. No cloud". A local model keeps data on the machine; a cloud model sends church data off the machine. The user must decide.

### 3.7 Hermes-side safety

- Keep Hermes approvals on. Do not use `/yolo` with write tools.
- Start with read tools only.
- Use a separate Hermes profile for church work (`hermes profile create church`).
- Never run `app.py` against the real church copy while debugging code; use `fake.build_fake_church` in a temp folder.

## 4. Open questions / not confirmed

1. Exact MCP message shapes for a stdlib server: check the MCP spec first.
2. Hermes on Windows: exact skills path and config path not verified.
3. Hermes `trust`, `readOnlyHint` and approval behavior for MCP tools: not read in full.
4. Data privacy: may a cloud model see church data? GOAL.md says offline only. Recommendation: local model, or only non-personal tools (counts, totals, next number).
5. Which fields of `person` may leave the machine (see 3.6).
6. Does the pastor want Hermes to write data at all, or only read and help debug code?

## 5. Sources

- https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp
- https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
- Church Manager code: `churchmgr/db.py`, `paths.py`, `search.py`, `people.py`, `care.py`, `calendar.py`, `money.py`, `sent.py`, `story.py`, `handover.py`, `app.py`, `docs/GOAL.md`.
