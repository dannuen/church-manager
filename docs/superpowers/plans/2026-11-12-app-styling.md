# App Styling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the look of every page of the dashboard with one shared CSS pass, with no change to data, routes or text.

**Architecture:** `web/style.css` already has `:root` tokens (colors, sizes, gaps) and all rules use them. The redesign changes the tokens first, then the rules per area (shell, tables, forms, cards, charts). Python page code changes only where a page uses inline `style=` or a class that must be renamed.

**Tech Stack:** Plain CSS, `web/app.js`, no build, no package (AGENTS.md rule 2). Tests: unittest. Check: `python verify.py`.

**Spec:** None yet. The pastor chose: "Full redesign of every page", "All pages with one shared CSS pass", and "I will show you an example later" for the look. **Task 1 is blocked until the example arrives.** Write `docs/superpowers/specs/2026-11-12-app-styling-design.md` from it before Task 2.

## Global Constraints

- Standard library only, no CSS framework, no web fonts from the internet (offline app).
- Use the words of `GLOSSARY.md` in any text, class names and comments.
- Do not change page text, routes, form names or data. Style only.
- Keep `web/print.css` working: `.no-print` and `.act` stay hidden on paper.
- Keep numbers in tabular figures; keep `:focus-visible` outline; text contrast at least 4.5:1.
- Test on a fake church in a temp folder outside OneDrive: `python -m churchmgr.fake <folder>`, then `python app.py --copy <folder>`. Never open the real church copy.
- `python verify.py` must exit 0 before each commit.

## Review Focus

- Long Vietnamese names and diacritics: no clipped or overlapping text in tables and cards.
- Empty lists (no People, no Money rows): the empty state still looks finished.
- Narrow window (about 800px) and 1440px: no horizontal scroll on the canvas, sidebar still usable.
- Wide tables (Money, People): the table scrolls inside its card, not the page.
- Print preview of People and Money: no sidebar, no buttons, no dark backgrounds.

---

### Task 1: Get the look (blocked on the pastor's example)

**Files:**
- Create: `docs/superpowers/specs/2026-11-12-app-styling-design.md`

**Interfaces:**
- Produces: a table of new token values (every `--name` in `:root` of `web/style.css`) plus any new tokens (e.g. `--shadow`), and a yes/no on dark mode.

- [x] **Step 1 (DECIDED by pastor):** Look = Pinterest pin (calm light teal, see values above). Keep the sidebar. Light theme only, no dark mode. Pinterest reference: https://www.pinterest.com/pin/1130825787720526406/ Pastor still must say yes to the spec in Step 3. Values read earlier: page `#F4F6F6`, white cards radius 16-20px, deep teal `#0F3D3E` / mid `#2C6E70` / tint `#D5E6E5`, pill buttons, soft shadow, gradient header band, one dark-teal highlight card, green/red only for amounts.
- [ ] **Step 1b (old note, ignore):** Pastor gave 3 examples. Read so far: Pinterest pin (finance dashboard by MD Mostahid) = calm light look: page `#F4F6F6`, white cards radius 16-20px, one deep teal `#0F3D3E` / mid `#2C6E70` / tint `#D5E6E5`, pill buttons and tabs, soft shadow, gradient header band, one inverted dark-teal highlight card, green/red only for amounts. Both X posts were blocked (403): pictures unseen; reply text hints at a dark theme with a sunset header band. **Pastor still must confirm** which look to use (answer was not received). Note: this look drops the sidebar for top tabs; keep the sidebar unless the pastor says otherwise.
- [ ] **Step 2:** Write the spec: new value for every `:root` token, the font choice (a system font stack only), and 3 sample screens to judge by (Dashboard, People, Money).
- [ ] **Step 3:** Pastor says yes to the spec. Commit `docs/superpowers/specs/`.

### Task 2: Tokens and shell

**Files:**
- Modify: `web/style.css` (`:root`, shell, `.sidebar`, `.nav-item`, `.title-row`, `.flash`; lines 1-62)
- Test: `tests/test_pages_ui.py`

**Interfaces:**
- Consumes: the token table from Task 1.
- Produces: final token names. Later tasks use only `var(--…)`, no raw colors.

- [ ] **Step 1: Write the failing test** `test_style_uses_only_tokens` in `tests/test_pages_ui.py`: read `web/style.css`, remove the `:root{…}` block, assert no `#rrggbb` color remains outside it.
- [ ] **Step 2:** Run `python -m unittest discover -s tests -p test_pages_ui.py`. Expected: FAIL listing the raw colors.
- [ ] **Step 3:** Update `:root` values and shell rules; move every raw color in the file into a token.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Open the fake church; check the sample screens at 800px and 1440px.
- [ ] **Step 6:** `python verify.py` exits 0. Commit `style: tokens and shell`.

### Task 3: Tables and lists (People, Families, Chi phái, Money, Documents, Sent)

**Files:**
- Modify: `web/style.css` (table, `.act`, row, pager rules)
- Modify: `churchmgr/pages/money.py` (remove inline `style=`, use a class)
- Test: `tests/test_pages_ui.py`

**Interfaces:**
- Consumes: tokens from Task 2.

- [ ] **Step 1: Write the failing test** `test_pages_have_no_inline_style`: for People, Money and Documents pages from the fake church, assert `'style="'` is not in the HTML.
- [ ] **Step 2:** Run it. Expected: FAIL on the Money page.
- [ ] **Step 3:** Restyle tables (row height `--row`, header, zebra or rule, hover, empty state). Replace the inline style in `churchmgr/pages/money.py` with a class in `style.css`. Wrap wide tables so they scroll inside their card.
- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5:** Check with a 60-character Vietnamese name and an empty list. `python verify.py` exits 0. Commit `style: tables and lists`.

### Task 4: Forms and buttons (all pages with a form, Settings, Setup)

**Files:**
- Modify: `web/style.css` (input, select, textarea, button, `.primary`, error text)

- [ ] **Step 1:** Restyle controls: height `--control-height`, border, focus, disabled, error, primary and plain buttons.
- [ ] **Step 2:** Check by hand: tab through the Add person form; focus ring visible on every control.
- [ ] **Step 3:** `python verify.py` exits 0. Commit `style: forms and buttons`.

### Task 5: Dashboard cards, Calendar, Care, charts

**Files:**
- Modify: `web/style.css` (card, KPI, `.chart`, calendar grid, Care rules)
- Modify: `web/app.js` only if it sets a color or class by name (check with search first)

- [ ] **Step 1:** Restyle KPI cards, the Services chart (keep the one accent hue for the Services line unless the Task 1 spec says otherwise), Calendar grid and Care lists.
- [ ] **Step 2:** Check Dashboard search box and chart ticks still show (they sit in `.chart` padding).
- [ ] **Step 3:** `python verify.py` exits 0. Commit `style: dashboard, calendar, care`.

### Task 6: Print and final pass

**Files:**
- Modify: `web/print.css` (only if a new class shows on paper)

- [ ] **Step 1:** Print preview of People, Money and one Handover page: no sidebar, no buttons, black on white.
- [ ] **Step 2:** Walk every sidebar page once at 800px and 1440px with the fake church; list problems, fix them.
- [ ] **Step 3:** `python verify.py` prints `ALL ... CHECKS PASS`. Commit `style: print and final pass`.

---

## Self-review

- Coverage: every page group (shell, tables, forms, cards, print) has a task. Look is gated by Task 1.
- Dark mode: not planned. Add a Task after Task 2 only if the Task 1 spec says yes.
- Names: the test file `tests/test_pages_ui.py` is the one place for style checks; I did not open it, so the implementer must read it first and match its helpers.
