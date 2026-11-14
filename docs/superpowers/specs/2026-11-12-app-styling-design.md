# App styling design: a calm teal look for every page

Date: 2026-11-12 (round 1), revised 2026-11-13 (round 2). Status: **draft, round 2, waiting for the pastor to say yes.**
Plan: `docs/superpowers/plans/2026-11-12-app-styling.md` (this is Task 1).
Scope: style only. No change to page text, routes, form names or data. One shared CSS pass in `web/style.css`, plus a few lines in `web/print.css`. **Round 2 needs no change in `ui.py` or `dashboard.py` either: it is all CSS.**
Round 1 is kept in `round1/` (spec, summary, 3 pictures, preview CSS, contrast output).

## 0. What changed since round 1

The pastor said: "It's not quite the gradient in pinterest like i wanted. 1 thing to note is that the dashboard should not be scroll, it should display in 1 page."

| # | Round 1 | Round 2 (this file) |
|---|---|---|
| 1 | A pale teal band, drawn as a small card (`.title-row`) | A big **dark-teal wash** at the top of the canvas. It is not a card. It runs behind the title and behind the top of the first row of cards (section 4.2) |
| 2 | Title in deep teal. Primary button deep teal | Title and finding line **white** on the wash. Main button in the title row = **white pill**, other buttons = **outlined white pill** (decision D3, section 2) |
| 3 | Money this month: 2-colour dark gradient | 3-colour teal gradient: dark at the top left, softer at the bottom right (section 4.3) |
| 4 | Dashboard was 1024px high at 1440 wide (it scrolled) | Dashboard fits **one screen**. The page does not scroll. A long list scrolls **inside its own card** (section 4A) |
| 5 | Tokens: 28 old + 24 new | Tokens: 28 old (same) + 36 new. The 4 `--band*` tokens are gone. 16 new tokens for the wash, the one-screen height and the softer dark card (section 3.2) |

Everything else from round 1 stays: all 28 old tokens, pills, the sidebar, ONE dark card, green and red only on the Balance, red errors, light only, print ink on white, style only.

## 1. The look in one paragraph

The look comes from the pastor's Pinterest pin (a finance dashboard, "Lumio", by MD Mostahid). A big dark-teal gradient wash at the top of the content frame. A white title on it. White pill buttons on it. White cards with big round corners and a soft shadow that sit on the wash and below it. ONE dark-teal gradient card. Green and red only on money amounts. The sidebar stays (the pin has top tabs; we ignore that). Light theme only.

**Pin check (round 2).** The pin page asks for a login, but the public picture of the pin loads without one. I looked at the picture again. What I see: a deep-teal wash at the top of the frame, dark at the top left and fading down and to the right into a pale ground; the greeting "Good morning, Alex." in white with a white line under it; two pills on the right (an outlined white pill and a white-filled pill with dark text); row 1 of 3 cards that sit on the lower part of the wash; one card that is a teal gradient (dark at the top, softer toward the bottom); row 2 of 3 cards. The hex values are the orchestrator's and the pastor's (`#0F3D3E`, `#1D5A5C`, `#2C6E70`, `#F4F6F6`, `#D5E6E5`). I did not measure pixels of the picture.

## 2. Decisions already made (not open)

| # | Decision |
|---|---|
| D1 | **CHANGED.** The gradient is a **wash at the top of the canvas** (the `main.canvas` right of the sidebar), on every page, the same on every page. It is a `::before` layer: no new markup, no text change. It is not a card. I chose the canvas and not the whole page: the sidebar then stays on the plain ground, so its text and its dark "current page" pill keep their contrast, and the wash looks like the pin's content frame. See section 4.2. |
| D2 | The one dark CARD is the Dashboard "Money this month" panel: `.dashboard > [data-panel="money-month"]`. CSS only. It now has the pin's teal gradient (section 4.3). No other page has a dark card. The wash is not a card. |
| D3 | **CHANGED.** Everywhere **except in the title row**: primary button = deep-teal fill, white text. **In the title row (on the wash):** the primary button (`.title-row .btn.primary`) = **white fill, deep-teal text**; every other button (`.title-row .btn`) = **outlined white pill** (transparent fill, 1px white border, white text); the search field = a white pill field with ink text. The page title (h1) and the line under it are white (finding line `#E4F1F0`). The focus ring on the wash is white. Markup is not changed: B12 counts `class="btn primary"` and CSS only restyles it. |
| D4 | Green and red are for money amounts only. **One exception: errors and refusals keep a red tone.** That is a state (something went wrong), not decoration. |
| D5 | The Services trend words "Up" and "Down" stop using green and red (they are not money). Up = mid teal, Down = muted grey-teal. The words carry the meaning, not the colour. |
| D6 | Print stays ink on white: no wash, no shadow, no gradient, no dark card, no green or red on paper. Title in black ink. |
| D7 | Light theme only. **Dark mode: NO.** No `prefers-color-scheme` rule. |
| D8 | System font stack only (the app is offline). |
| D9 | **NEW.** The Dashboard (`/`) fits **one screen**: the page itself does not scroll, at the sizes in section 4A. A long list scrolls inside its own card. No word, link or panel is added or removed. Under 861px wide (top-bar layout) the page may scroll. Other pages may scroll as before. |

## 3. Tokens

All colours live in `:root`. After the change no `#rrggbb` or `rgba()` is left in `web/style.css` outside `:root` (the plan's test `test_style_uses_only_tokens` checks this).

### 3.1 Every current token, old value to new value (28 of 28)

| # | Token | Old value | New value | Note |
|---|---|---|---|---|
| 1 | `--ground` | `#f7f7f6` | `#F4F6F6` | Page ground (pin value) |
| 2 | `--surface` | `#ffffff` | `#FFFFFF` | Cards. Same |
| 3 | `--raised` | `#f2f2f1` | `#E8F0F0` | Hover tint, Private note panel, Handover result |
| 4 | `--active` | `#e8e8e7` | `#D5E6E5` | The teal tint (pin value): active chip, tag, flash |
| 5 | `--border` | `#e8e8e8` | `#E2E9E9` | Hairline round a card, table header rule |
| 6 | `--rule` | `#f0f0f0` | `#EBF0F0` | Hairline between rows |
| 7 | `--control` | `#cfd3d6` | `#7E9696` | Input and button border. Now 3.14:1 on white (old one was about 1.5:1) |
| 8 | `--text` | `#151515` | `#0F2A2C` | Ink, a very dark teal |
| 9 | `--muted` | `#5c6066` | `#47605F` | Grey-teal text |
| 10 | `--faint` | `#6b6b6b` | `#566E6E` | Dash, placeholder, "nothing" text |
| 11 | `--accent` | `#1f5c99` | `#2C6E70` | Mid teal (pin value): Services line, Today, Service kind |
| 12 | `--primary` | `#1d1f20` | `#0F3D3E` | Deep teal (pin value): primary button, active menu item |
| 13 | `--primary-ink` | `#ffffff` | `#FFFFFF` | Text on primary. Same |
| 14 | `--positive` | `#247b50` | `#1B7A4A` | Green, money amounts only |
| 15 | `--negative` | `#c4242a` | `#B3261E` | Red: money amounts, errors, Delete |
| 16 | `--font` | `"Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif` | same | Kept (see section 5) |
| 17 | `--fs-small` | `12px` | `12px` | Same |
| 18 | `--fs-meta` | `14px` | `14px` | Same |
| 19 | `--fs-body` | `16px` | `16px` | Same |
| 20 | `--fs-title` | `24px` | `24px` | Same (KPI value). The page title uses the new `--fs-display` |
| 21 | `--gap` | `16px` | `20px` | More air between cards (the Dashboard sets its own 14px gap, section 4A) |
| 22 | `--pad` | `24px` | `24px` | Same |
| 23 | `--card-pad` | `20px` | `24px` | More air inside cards (the Dashboard cards set their own padding, section 4A) |
| 24 | `--radius` | `8px` | `12px` | Small boxes: flash, result, refusal, empty box, search results |
| 25 | `--radius-control` | `6px` | `12px` | Inputs, multi-line fields |
| 26 | `--sidebar` | `232px` | `232px` | Same |
| 27 | `--control-height` | `40px` | `40px` | Same |
| 28 | `--row` | `44px` | `44px` | Same |

Count: old tokens 28, mapped 28.

### 3.2 New tokens (36)

Changed or new in round 2 are marked **R2**.

| Token | Value | Use |
|---|---|---|
| `--primary-hover` | `#2C6E70` | Primary button on hover; active menu item on hover. (Was the raw `#3a3d3f`.) |
| `--focus` | `#2C6E70` | The `:focus-visible` ring (before, `--accent` did this job) |
| `--wash-from` / `--wash-via` / `--wash-to` **R2** | `#0F3D3E` / `#1D5A5C` / `#2A6C6E` | The three stops of the wash, left to right. `--wash-to` is the lightest place any text sits on |
| `--wash` **R2** | `linear-gradient(180deg, transparent 0%, transparent 60%, var(--ground) 100%), linear-gradient(112deg, var(--wash-from) 0%, var(--wash-via) 48%, var(--wash-to) 100%)` | The wash: dark teal from top left to right, fading into the ground in the lower 40% |
| `--wash-h` / `--wash-h-narrow` **R2** | `340px` / `600px` | Height of the wash. The narrow one is for the stacked title row under 861px |
| `--wash-radius` **R2** | `28px` | Round top corners of the wash |
| `--dash-row2` **R2** | `294px` | Dashboard: height of the second row of cards (section 4A) |
| `--wash-ink` **R2** | `#FFFFFF` | Title (h1) and button text on the wash |
| `--wash-soft` **R2** | `#E4F1F0` | Finding line, labels, language switch text on the wash |
| `--wash-btn-fill` / `--wash-btn-ink` **R2** | `#FFFFFF` / `#0F3D3E` | The white main-action pill in the title row: fill, text |
| `--wash-line` **R2** | `#FFFFFF` | Border of the outlined white pill |
| `--wash-hover` **R2** | `rgba(255, 255, 255, 0.12)` | Hover fill of an outlined pill on the wash |
| `--wash-focus` **R2** | `#FFFFFF` | Focus ring on the wash |
| `--highlight` / `--highlight-mid` / `--highlight-end` **R2** | `#0F3D3E` / `#1D5A5C` / `#28696B` | Dark card: three stops of its gradient (round 1 had 2 stops, the last was `#1D5A5C`) |
| `--highlight-fill` **R2** | `linear-gradient(160deg, var(--highlight) 0%, var(--highlight-mid) 55%, var(--highlight-end) 100%)` | Dark card background: dark at the top left, softer at the bottom right |
| `--highlight-ink` | `#FFFFFF` | Dark card: title, amounts, links |
| `--highlight-muted` **R2** | `#E1EEED` | Dark card: labels, month, small text (round 1: `#C2DAD9`; lighter now so it passes on the softer end) |
| `--highlight-rule` | `rgba(255, 255, 255, 0.20)` | Dark card: lines between the three amounts; dashed empty box |
| `--highlight-focus` | `#FFFFFF` | Focus ring inside the dark card |
| `--positive-on-dark` / `--negative-on-dark` **R2** | `#9AF2C4` / `#FFD6D2` | Green and red Balance on the dark card (round 1: `#7FE3AE` / `#FFB9B3`; lighter, same reason) |
| `--grid` | `#E3EBEB` | Services chart: gridlines. (Was the raw `#ececec`.) |
| `--grid-base` | `#C2D0D0` | Services chart: the zero line. (Was the raw `#cfcfcf`.) |
| `--refusal-bg` | `#FFEDEA` | Handover refusal background. (Was the raw `#ffedea`; value kept.) |
| `--refusal-ink` | `#831C1E` | Handover refusal bold word. (Was the raw `#831c1e`; value kept.) |
| `--shadow` | `0 1px 2px rgba(15, 61, 62, 0.05), 0 6px 20px rgba(15, 61, 62, 0.07)` | Cards, Money totals strip, filter bar |
| `--shadow-raised` | `0 10px 30px rgba(15, 61, 62, 0.16)` | Dark card; live search results. (Was the raw `rgba(0, 0, 0, 0.08)` shadow.) |
| `--radius-card` | `18px` | Cards, Money totals strip, filter bar |
| `--radius-pill` | `999px` | Buttons, chips, tags, menu items, search fields, language switch |
| `--fs-display` | `28px` | The page title (h1) on the wash |

Round 1 tokens removed in round 2: `--band-from`, `--band-via`, `--band-to`, `--band` (the pale band is gone).
Count: new tokens 36. `:root` then holds 64 tokens. A script found no token that is defined but unused, and none used but undefined.

### 3.3 Raw colours now outside `:root` in `web/style.css`

| Raw value now | Where | Becomes |
|---|---|---|
| `#ececec` | `.chart .gridline` | `var(--grid)` |
| `#cfcfcf` | `.chart .gridline.base` | `var(--grid-base)` |
| `#3a3d3f` | `.btn.primary:hover` | `var(--primary-hover)` |
| `#ffedea` | `.refusal` background | `var(--refusal-bg)` |
| `#831c1e` | `.refusal strong` | `var(--refusal-ink)` |
| `rgba(0, 0, 0, 0.08)` | `.results` shadow | `var(--shadow-raised)` |

Six raw colours, six tokens. Two more raw colours exist outside `style.css` and are **not** in scope of this CSS pass:
- `web/print.css` uses `#fff`, `#000`, `#888`, `#333` on purpose (ink on white). They stay.
- `churchmgr/pages/money.py` (Year report chart) paints bars with the inline fills `#2f6f4f` (Offerings, green: allowed, it is money) and `#999` (Expenses, grey) and a legend with `style="color:..."`. The plan's Task 3 already removes inline `style=` from `money.py`. Keep both bar colours as they are (they must print).

## 4. Rules by part of the screen

Class names below are the ones in `web/style.css` today. No new markup. The exact CSS I tested is in `preview-style.css` (and `preview-print.css`) next to this file. **A comment in `web/*.css` must not hold an Avoid word** (the test `test_no_avoid_words_in_pages_app_and_web` reads comments too; my first preview comment used one of those words and failed it).

### 4.1 Shell
- Page ground `--ground`. The sidebar has no card: it sits on the ground, not on the wash. Padding 24px 16px, gap 20px.
- Church name (`.brand-church`): deep teal, bold. App name (`.brand-app`): muted, 12px.
- Menu item (`.nav-item`): pill, 40px high, 16px side padding, muted text. Hover: `--raised` fill, ink text.
- Active menu item (`[aria-current="page"]`): **deep teal pill, white text, bold.** Hover on it: `--primary-hover`.
- On a short window (up to 720px high, from 861px wide) the sidebar is one notch tighter, on every page: padding 14px 16px, gap 12px, menu items 34px high. All 13 menu items stay visible (measured: sidebar `scrollHeight` = `clientHeight` from 600px to 900px high).
- Under 860px the sidebar becomes a top bar and the menu becomes a row of pills (as now).
- Flash message (`.flash`): `--active` tint, no border, 12px radius.
- **Language switch** (`.lang-switch`, top right of the canvas, on the wash): two small pills. Idle: `--wash-soft` text, no fill. Hover: `--wash-hover` fill, white text. Current (`aria-pressed="true"`): white fill, ink text, bold. Focus ring white.

### 4.2 The wash (replaces the round 1 band)
The wash is one gradient layer behind the top of the canvas. It is not a card: no border, no shadow, no inner padding of its own. It is the same on every page.

```css
.canvas { position: relative; isolation: isolate; padding-top: 14px; }
.canvas::before { content: ""; position: absolute; z-index: -1; top: 8px; left: 0; right: 12px; height: var(--wash-h);
  background: var(--wash); border-radius: var(--wash-radius) var(--wash-radius) 0 0; pointer-events: none; }
```
- Colour: `#0F3D3E` at the top left, `#1D5A5C` in the middle, `#2A6C6E` at the right. The lower 40% (from 204px to 340px) fades into `--ground`. It runs behind the language switch, the title row and the top of the first row of cards. The cards sit on it (they stay white).
- **Why the canvas and not the whole page:** the sidebar keeps its plain ground, so its text and its dark current-page pill keep their contrast, and the dark pill does not vanish into a dark wash.
- **Title row** (`.title-row`): no background, no card. Padding `0 12px 14px`. Page title (h1): 28px / 36px, bold, `--wash-ink` (white). Finding line (`.sub`) and search label: `--wash-soft`. Buttons and the search field sit on the right, centred in the row. The focus ring in the row is white (`--wash-focus`).
- **Buttons in the title row (D3):** `.title-row .btn` = outlined white pill (transparent fill, 1px `--wash-line` border, white text; hover `--wash-hover`). `.title-row .btn.primary` = `--wash-btn-fill` fill and border, `--wash-btn-ink` text; hover = `--active` fill. The search field in the row: white pill field, ink text (`--text` on `--surface`), white border.
- **Text outside a card never sits on the wash.** The filter bar under the title row on People, Money, Calendar and Sent documents (`.list-toolbar`, with its chips and its search or month field) is a **white bar** (`--surface`, `--radius-card`, `--shadow`, padding 10px 16px). A plain note under a list (`.canvas > .hint`, `.canvas > .lead`; today only the Documents hint) is a small white note (white fill, 1px `--border`, `--radius`, padding 8px 16px). I scanned 27 pages (all 13 menu pages and 14 detail pages) for text that has no card, pill or field under it and sits in the first 340px: only the title row text and the Documents hint were found, and the hint now has the white note.
- Under 861px the title row stacks (title, then actions) and the wash gets `--wash-h-narrow` (600px).

### 4.3 Cards and panels (`.panel`)
- White, 1px `--border`, radius `--radius-card`, `--shadow`, padding `--card-pad`.
- Card title (h2): 16px bold ink. Sub line (`.meta`): muted 14px. Foot links (`.card-link`): ink, bold, with the `›` sign as now.
- Empty state (`.empty`): dashed `--control` border, 12px radius, muted text (still looks finished).
- **The one dark card** (D2): `.dashboard > [data-panel="money-month"]`. Background `--highlight-fill` = `linear-gradient(160deg, #0F3D3E 0%, #1D5A5C 55%, #28696B 100%)`: dark teal at the top left, softer teal at the bottom right, like the pin's gradient card. No border, `--shadow-raised`. It re-sets its own tokens, so every rule inside keeps working with no new selector:
  `--text: --highlight-ink; --muted: --highlight-muted; --faint: --highlight-muted; --rule: --highlight-rule; --control: --highlight-rule; --positive: --positive-on-dark; --negative: --negative-on-dark; --focus: --highlight-focus`.
  Exact colours: title, amounts and links `#FFFFFF`; labels and month `#E1EEED`; green Balance `#9AF2C4`; red Balance `#FFD6D2`. All pass 4.5:1 at all three stops of the gradient (section 6).
  It keeps `align-self: start` (rule B11) so it does not stretch (section 4A).

### 4.4 KPI and the Money page totals strip (`.kpi-strip`)
- KPI: grey label above an ink value (24px, tabular figures), lines between them (as now).
- Balance (`.kpi-value.strong`): **green if it is not negative, red if it is** (`.neg`). CSS only: `.kpi-value.strong:not(.neg) { color: var(--positive); }`. A Balance of 0 shows green. Offerings and Expenses stay ink.
- `.kpi-strip` on the Money page: a **light** card (white, `--radius-card`, `--shadow`), three cells split by 1px `--rule`, cell padding 18px 24px. It is not dark: only the Dashboard card is dark.

### 4.5 Tables (`table`, `table.list`, `table.money`, ...)
- Header cell (`th`): 12px, bold, muted, 1px `--border` under it.
- Row: 1px `--rule` between rows, none under the last row. Row height as now.
- Hover on a row: `--raised` fill, with rounded ends on the first and last cell. The Money total row does not get a hover.
- Amounts stay right-aligned, tabular figures, ink (no green or red in table cells).
- A wide table scrolls **inside its card**: `.table-wrap { overflow-x: auto; max-width: 100%; }`; the card and grid cells keep `min-width: 0`. The page never scrolls sideways.
- Under 640px `table.list` becomes two-line rows (as now).

### 4.6 Forms and buttons
- Input, select, multi-line field: 40px high, white, 1px `--control` border, 12px radius. Search fields (`.search-line`, `.title-search`, `.toolbar`) are pills with 18px side padding.
- Button (`.btn`): **pill**, 40px high, 20px side padding, 14px bold, white fill, 1px `--control` border. Hover: `--raised`.
- Primary (`.btn.primary`), **outside the title row**: fill `--primary`, text `--primary-ink`. Hover: fill `--primary-hover`. One filled primary per screen (a test counts the markup).
- Buttons **in the title row** follow D3 and section 4.2 (white pill and outlined white pill).
- Danger (`.btn.danger`): pill, white fill, red text and border (this is the "red = state" exception D4).
- Focus: `:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }` on every control and link. In the title row and in the language switch `--focus` is white. Inside the dark card the ring is white.
- Disabled (`.btn:disabled`, `.btn[aria-disabled="true"]`, `.input:disabled`): `--raised` fill, `--border` border, `--faint` text, `cursor: not-allowed`. (There is no disabled rule today: this is new.)
- Error: red text (`.error`), red input border (`[aria-invalid="true"]`), as now. Red is kept here by D4.
- File field: its "Choose file" button is a small pill.
- Under 860px buttons and inputs are 44px high (as now).
- `.btn:hover`, `.btn.primary:hover` etc. do not animate. `prefers-reduced-motion` stays honoured (no transitions are added).

### 4.7 Chips, tags and tabs
- Chip (`.chip`, the Status filter, the week / month / Money month links): pill, 32px high, 16px side padding, 1px `--border`, muted text. Hover: `--raised`. The chips sit in the white filter bar (section 4.2).
- Chip on (`[aria-current="true"]`): `--active` fill, 1px `--accent` border, deep-teal bold text.
- Tag (`.tag`, "Hidden", "Open now"): pill, `--active` fill, muted text.
- `details.change > summary` (the "Change Status +" buttons): pill, like `.btn`.

### 4.8 Calendar
- Agenda blocks keep the day on the left and the Calendar items on the right, with a `--rule` line between days.
- Today tag (`.today-tag`): small pill, `--active` fill, deep-teal bold text.
- Service kind (`.kind.k-service`): `--accent` bold (the teal stays on Services).
- Week / month chips and the month picker follow 4.6 and 4.7.

### 4.9 Care
- "Needs a visit" list: rows with `--rule` lines, the Person on the left, Status and last Visit at the right in muted text, the "Plan" action bold ink.
- Visit cards in the care log: rows with `--rule` lines, date muted, name medium weight. "Mark done" form fields follow 4.6.
- Nothing on this page is green or red, except an error message.

### 4.10 The Private note panel
- Must look different from other cards. Rule: `--raised` tint fill, a **dashed** 1px `--control` border, **no shadow**. Other cards are white, solid-bordered and raised. A person sees at once "this one is not like the others".
- Notes inside keep the 1px lines between them. It stays `.no-print`, so it never prints.

### 4.11 Handover result and refusal
- Result (`.result`): `--raised` tint box, 12px radius, ink text.
- Refusal (`.refusal`): `--refusal-bg` (`#FFEDEA`) box, ink text, the bold word in `--refusal-ink` (`#831C1E`). Red tone kept (D4).
- Links inside stay underlined.

### 4.12 Services chart and trend words
- The line is `--accent` (mid teal), 2.5px, round joins. The last value (`.end`) is bold `--accent`.
- Gridlines `--grid`, the zero line `--grid-base`. Tick text `--muted`, 12px.
- Trend words: **Up** = `--accent`, **Down** = `--muted` (D5). Both bold. Not green or red.
- The chart height is the `height` attribute from `dashboard.py` (154px). It is not changed.

### 4.13 Print (`web/print.css`)
Ink on white. Add this block at the end of `web/print.css` (it comes after `style.css`, so `!important` is needed where the screen rule is more exact). I tested it with print media emulated at the A4 width (794px) on the Dashboard and on Money: the title is `rgb(0,0,0)`, the wash layer is `display: none`, no gradient, no dark card (see `preview-print.css`).

```css
@media print {
  .canvas, .canvas:has(> .dashboard) { position: static !important; height: auto !important; min-height: 0 !important; display: block !important; padding: 0 !important; }
  .canvas::before { display: none !important; }
  .title-row { padding: 0 !important; background: none !important; border-radius: 0 !important; box-shadow: none !important; }
  .title-row h1, .title-row .sub, .title-row label { color: #000 !important; }
  .panel, .kpi-strip, .list-toolbar { box-shadow: none !important; background: none !important; border-radius: 0 !important; }
  .dashboard { display: block !important; }
  .dashboard > .panel { min-height: 0 !important; max-height: none !important; margin-bottom: 6mm; break-inside: avoid; }
  .dashboard .rows { overflow: visible !important; margin: 0 !important; padding: 0 !important; }
  .dashboard > [data-panel="money-month"] { background: none !important; box-shadow: none !important; --text: #000; --muted: #333; --faint: #333; --rule: #888; --positive: #000; --negative: #000; color: #000; }
  .kpi-value.strong, .kpi-value.strong:not(.neg) { color: #000 !important; }
  .chart .line { stroke: #000; }
  .chart .end { fill: #000; }
  .tag, .today-tag, .chip { background: none !important; }
  .canvas > .hint, .canvas > .lead { background: none !important; border: 0 !important; padding: 0 !important; }
}
```
- Sidebar, buttons, forms, the language switch, `.no-print` stay hidden as now.
- **Not measured:** a real print preview. Plan Task 6 must print-preview People, Money and a Handover page.

## 4A. Dashboard on one screen (NEW in round 2)

**Goal (D9).** On `/` the page itself does not scroll: `document.documentElement.scrollHeight <= window.innerHeight`, and no sideways scroll. No word, link or panel is added or removed. Body text stays 14px or more.

**Measured** with the fake church (50 People, the busiest week it gives: 7 Calendar items; Needs a visit 37 People), `python -m churchmgr.fake <dir> --people 50 --seed 1`, in Chromium, with the inner window size set by script:

| Inner size (w x h) | `scrollHeight` | `innerHeight` | `scrollWidth` | `clientWidth` | Lowest card bottom | Result |
|---|---|---|---|---|---|---|
| 1440 x 800 | 800 | 800 | 1440 | 1440 | 788 | one screen |
| 1366 x 650 | 650 | 650 | 1366 | 1366 | 638 | one screen |
| 1920 x 960 | 960 | 960 | 1920 | 1920 | 948 | one screen |

More sizes I measured (height sweep at 1440 and at 1366 wide, 900 down to 600): the page fits at every height from 900 down to **640px**; at 620 and at 600 it is 640px high and scrolls by 20 and 40px. At 1181x700, 1600x900 and 2560x1300 it also fits.

**Rules.** They apply from **1181px wide** (media query `min-width: 1181px`). `:has()` is used in the first selector; the app's CSS already uses `:has()` (`.row:has(> .what.wrap)`).

```css
@media (min-width: 1181px) {
  .canvas:has(> .dashboard) { height: 100vh; min-height: 640px; padding-bottom: 12px; display: flex; flex-direction: column; }
  .canvas:has(> .dashboard) > .lang-switch { position: absolute; top: 12px; right: 40px; margin: 0; z-index: 1; }
  .canvas:has(> .dashboard) > .title-row { flex: none; margin-bottom: 12px; padding-top: 6px; padding-bottom: 8px; }
  .canvas:has(> .dashboard) > .title-row .actions { align-items: flex-end; }
  .canvas:has(> .dashboard) > .flash { flex: none; margin-bottom: 8px; }
  .dashboard { flex: 1 1 0; min-height: 0; gap: 14px; grid-template-rows: minmax(150px, 1fr) auto; }
  .dashboard > .panel { min-height: 0; padding: 14px 20px 12px; }
  .dashboard .panel > header { margin-bottom: 4px; }
  .dashboard .panel > header > div { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0 10px; }
  .dashboard .panel > footer { padding-top: 8px; }
  .dashboard .row { min-height: 40px; padding: 4px 0; }
  .dashboard .row .day { width: 112px; }
  .dashboard > [data-panel="this-week"] .rows, .dashboard > [data-panel="needs-visit"] .rows, .dashboard > [data-panel="sent-documents"] .rows {
    flex: 1 1 0; min-height: 0; overflow-y: auto; align-content: start; overscroll-behavior: contain;
    scrollbar-width: thin; scrollbar-color: var(--control) transparent; scrollbar-gutter: stable; margin-right: -14px; padding-right: 6px; }
  .dashboard > [data-panel="services"], .dashboard > [data-panel="money-month"], .dashboard > [data-panel="sent-documents"] { min-height: var(--dash-row2); }
  .dashboard > [data-panel="sent-documents"] { max-height: var(--dash-row2); }
}
@media (min-width: 861px) and (max-height: 720px) { .sidebar { padding: 14px 16px; gap: 12px; } .nav-item { min-height: 34px; } }
@media (min-width: 1181px) and (max-height: 720px) {
  .dashboard .row { min-height: 34px; padding: 2px 0; }
  .dashboard > [data-panel="services"], .dashboard > [data-panel="money-month"], .dashboard > [data-panel="sent-documents"] { padding-top: 10px; padding-bottom: 8px; }
}
```

**How the height is spent** (1440 x 800): top padding 14 + the title row to y=94 + 12 gap; **row 1** (This week, Needs a visit) y 106 to 480 = 374px; 14px gap; **row 2** (Services, Money this month, Sent documents) y 494 to 788 = 294px; 12px at the bottom. Row 1 takes what is left (`1fr`). Row 2 is `--dash-row2` (294px) tall. Columns are the 12-column grid as now: row 1 = 6 + 6, row 2 = 4 + 4 + 4. That is 2 rows and 5 cards, as the markup is today.

**Which card scrolls inside.**
- **This week**, **Needs a visit** and **Sent documents**: the list of rows (`.rows`) is the only part that scrolls (`overflow-y: auto`). The card title, the sub line and the foot link ("View all 7 in Calendar ›") stay in place: the foot link is always visible. A thin scroll bar shows at the right.
- **Services** and **Money this month** never scroll: their content has a fixed size (chart 154px high, three amounts).
- The app already shows at most 6 Calendar items, 6 People and 2 Sent documents on the Dashboard (`WEEK_ROWS`, `VISIT_ROWS`, `SENT_ROWS`). Nothing is cut by this spec. The rows that do not fit are one scroll away.

**What the pastor sees at the three sizes (fake church):**

| Inner size | This week | Needs a visit | Sent documents |
|---|---|---|---|
| 1440 x 800 | all 6 rows | all 6 rows | all 2 rows |
| 1920 x 960 | all 6 rows | all 6 rows | all 2 rows |
| 1366 x 650 | about 4 of 6 rows, the rest by scroll | about 3 of 6 rows, the rest by scroll | all 2 rows |

At 1440 wide a list starts to scroll inside when the window is shorter than about 780px (measured: all rows show at 800px high; at 760px Needs a visit scrolls). At 1366 x 650 the first row is only 224px tall: the lists are short there, and that is the price of one screen.

**Text sizes.** No font size was reduced. Body text on the Dashboard is 14px or 16px. 12px is used only where it was already 12px: the language switch, the list column heads ("Person", "Status", "Last Visit") and the chart tick labels.

**B11.** `align-self: start` on Services, Money this month and Sent documents (rule at `style.css` line 435) is **kept**, and the new rules add only `min-height` and `max-height` for these three. B11 passes: I ran `test_pages_ui`, `test_server` and `test_db` on the preview copy: 85 tests, all OK. There is no conflict.

**Where the page may scroll.**
- **Under 861px wide** (top-bar layout): the page scrolls as before. This is what the orchestrator allowed.
- **From 861px to 1180px wide:** the Dashboard keeps the round 1 grid of 3 rows and the page may scroll. **I did not make this range one screen** (3 rows do not fit a window of about 700px). It is an extra limit and it is listed in section 9.
- **A window shorter than 640px** at 1181px wide or more: the page scrolls by the missing height (for example 40px at 600px high). The floor is 640px so the first row never gets too small to use.
- Other pages (People, Money, ...) may scroll as before.

**Keyboard.** The rows of This week and Needs a visit hold links, so Tab scrolls the list. Sent documents rows hold no links; Edge and Chrome make a scroll box reachable by keyboard themselves. Not measured (section 8).

## 5. Font

Keep `--font: "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif`. No reason to change it: it is a system stack (works offline), it draws Vietnamese diacritics well on Windows, and the pin's look comes from colour, radius and shadow, not from a special face. Sizes stay 12 / 14 / 16 / 24, plus 28 for the page title. Tabular figures stay on `.num, table, .kpi-value, input, select`.

## 6. Contrast (computed by script)

Method: WCAG 2.x relative luminance; ratio = (L1 + 0.05) / (L2 + 0.05). Every text pair must be at least 4.5:1. UI parts (input border, focus ring, outlined pill border) must be at least 3:1. For a gradient, **every stop is tested**: the wash at its left stop, its middle, its right stop (the lightest place a title, a button or a label sits on) and its lowest point at 200px; the dark card at its three stops.

Result: **all text pairs pass. The lowest text ratio is 4.63:1** (the outlined pill text on its hover fill, and the finding line at the lowest point of the wash). All non-text pairs pass; **the lowest is 3.14:1** (input border on a card). The white focus ring on the wash is 5.36:1 or more at every stop.

**Real pixels.** I also read the pixels of the four preview pictures: the lightest flat wash pixel where text or a pill sits is `#28696B`. That is darker than the right stop used above (`#2A6C6E`), so the table is the safe side. White on it is 6.32:1, the finding line colour on it is 5.46:1.

Full output of `contrast-check.py` (same text is in `contrast-output.txt`):

```text
TEXT PAIR                                                                  fg       bg       ratio  need 4.5
page title (h1) on wash, left stop                                         #FFFFFF  #0F3D3E  11.95  PASS
finding line on wash, left stop                                            #E4F1F0  #0F3D3E  10.32  PASS
search label / language switch / outlined pill text on wash, left stop     #E4F1F0  #0F3D3E  10.32  PASS
page title (h1) on wash, middle                                            #FFFFFF  #1D5A5C   7.87  PASS
finding line on wash, middle                                               #E4F1F0  #1D5A5C   6.80  PASS
search label / language switch / outlined pill text on wash, middle        #E4F1F0  #1D5A5C   6.80  PASS
page title (h1) on wash, right stop                                        #FFFFFF  #2A6C6E   6.05  PASS
finding line on wash, right stop                                           #E4F1F0  #2A6C6E   5.23  PASS
search label / language switch / outlined pill text on wash, right stop    #E4F1F0  #2A6C6E   5.23  PASS
page title (h1) on wash, lowest point (200px)                              #FFFFFF  #367476   5.36  PASS
finding line on wash, lowest point (200px)                                 #E4F1F0  #367476   4.63  PASS
search label / language switch / outlined pill text on wash, lowest point (200px) #E4F1F0  #367476   4.63  PASS
body text on card                                                          #0F2A2C  #FFFFFF  15.13  PASS
body text on page ground                                                   #0F2A2C  #F4F6F6  13.95  PASS
body text on hover / Private note panel                                    #0F2A2C  #E8F0F0  13.08  PASS
body text on tint (chip on, flash, tag)                                    #0F2A2C  #D5E6E5  11.73  PASS
muted on card                                                              #47605F  #FFFFFF   6.76  PASS
muted on page ground (sidebar)                                             #47605F  #F4F6F6   6.23  PASS
muted on hover / Private note panel                                        #47605F  #E8F0F0   5.84  PASS
muted on tint (tag)                                                        #47605F  #D5E6E5   5.24  PASS
faint on card (dash, placeholder, no-items text)                           #566E6E  #FFFFFF   5.45  PASS
faint on page ground                                                       #566E6E  #F4F6F6   5.03  PASS
faint on Private note panel                                                #566E6E  #E8F0F0   4.71  PASS
accent text on card (today, Services, chart end value)                     #2C6E70  #FFFFFF   5.88  PASS
accent text on page ground                                                 #2C6E70  #F4F6F6   5.42  PASS
deep teal on tint (active chip, Today tag)                                 #0F3D3E  #D5E6E5   9.26  PASS
deep teal on page ground (church name)                                     #0F3D3E  #F4F6F6  11.02  PASS
primary button text                                                        #FFFFFF  #0F3D3E  11.95  PASS
primary button text, hover                                                 #FFFFFF  #2C6E70   5.88  PASS
active nav item text                                                       #FFFFFF  #0F3D3E  11.95  PASS
positive amount on card                                                    #1B7A4A  #FFFFFF   5.34  PASS
negative amount / error on card                                            #B3261E  #FFFFFF   6.54  PASS
negative error on Private note panel                                       #B3261E  #E8F0F0   5.65  PASS
danger button on hover                                                     #B3261E  #E8F0F0   5.65  PASS
refusal text                                                               #0F2A2C  #FFEDEA  13.37  PASS
refusal heading word                                                       #831C1E  #FFEDEA   8.63  PASS
wash primary pill: deep teal text on white fill                            #0F3D3E  #FFFFFF  11.95  PASS
wash primary pill, hover: deep teal text on tint fill                      #0F3D3E  #D5E6E5   9.26  PASS
search field in the wash: ink on white                                     #0F2A2C  #FFFFFF  15.13  PASS
note under a list (white note): muted on white                             #47605F  #FFFFFF   6.76  PASS
language switch, current: ink on white pill                                #0F2A2C  #FFFFFF  15.13  PASS
outlined pill text, hover (12% white on right stop)                        #FFFFFF  #447E7F   4.63  PASS
Money this month: ink, top-left stop                                       #FFFFFF  #0F3D3E  11.95  PASS
Money this month: muted, top-left stop                                     #E1EEED  #0F3D3E  10.05  PASS
Money this month: positive Balance, top-left stop                          #9AF2C4  #0F3D3E   9.03  PASS
Money this month: negative Balance, top-left stop                          #FFD6D2  #0F3D3E   8.99  PASS
Money this month: ink, middle stop                                         #FFFFFF  #1D5A5C   7.87  PASS
Money this month: muted, middle stop                                       #E1EEED  #1D5A5C   6.61  PASS
Money this month: positive Balance, middle stop                            #9AF2C4  #1D5A5C   5.95  PASS
Money this month: negative Balance, middle stop                            #FFD6D2  #1D5A5C   5.92  PASS
Money this month: ink, bottom-right stop                                   #FFFFFF  #28696B   6.32  PASS
Money this month: muted, bottom-right stop                                 #E1EEED  #28696B   5.31  PASS
Money this month: positive Balance, bottom-right stop                      #9AF2C4  #28696B   4.78  PASS
Money this month: negative Balance, bottom-right stop                      #FFD6D2  #28696B   4.75  PASS
LOWEST TEXT RATIO: 4.63  (outlined pill text, hover (12% white on right stop))

NON-TEXT PAIR                                                              fg       bg       ratio  need 3.0
focus ring (white) on wash, left stop                                      #FFFFFF  #0F3D3E  11.95  PASS
outlined pill border (white) on wash, left stop                            #FFFFFF  #0F3D3E  11.95  PASS
focus ring (white) on wash, middle                                         #FFFFFF  #1D5A5C   7.87  PASS
outlined pill border (white) on wash, middle                               #FFFFFF  #1D5A5C   7.87  PASS
focus ring (white) on wash, right stop                                     #FFFFFF  #2A6C6E   6.05  PASS
outlined pill border (white) on wash, right stop                           #FFFFFF  #2A6C6E   6.05  PASS
focus ring (white) on wash, lowest point (200px)                           #FFFFFF  #367476   5.36  PASS
outlined pill border (white) on wash, lowest point (200px)                 #FFFFFF  #367476   5.36  PASS
input border on card                                                       #7E9696  #FFFFFF   3.14  PASS
Services line on card                                                      #2C6E70  #FFFFFF   5.88  PASS
focus ring on card                                                         #2C6E70  #FFFFFF   5.88  PASS
focus ring on page ground                                                  #2C6E70  #F4F6F6   5.42  PASS
focus ring on tint                                                         #2C6E70  #D5E6E5   4.56  PASS
focus ring beside deep teal fill (gap is white)                            #2C6E70  #FFFFFF   5.88  PASS
focus ring on dark card, bottom-right stop                                 #FFFFFF  #28696B   6.32  PASS
focus ring on dark card, top-left stop                                     #FFFFFF  #0F3D3E  11.95  PASS
chart base line on card (information only)                                 #C2D0D0  #FFFFFF   1.59  info
LOWEST NON-TEXT RATIO: 3.14  (input border on card)
```

Notes on the table above:
- The wash pairs and the dark-card pairs are tested at every stop.
- The input border (`#7E9696`) is 3.14:1 on white. The old `#cfd3d6` was about 1.5:1.
- The disabled text (`--faint` on `--raised`) is 4.71:1, so even disabled text stays readable.
- Gridlines are decoration, not information, so they have no minimum.
- The outlined pill text on hover is white on 12% white over the right stop: 4.63:1.

The script (plain Python, no package) is in the Appendix at the end of this file. Save it as `contrast-check.py` and run `python contrast-check.py`.

## 7. Sample screens to judge by

Pictures are next to this spec. They come from a throw-away copy of the CSS (`git archive HEAD`, only `web/style.css` and `web/print.css` changed) and a fake church of 50 people. They are the spec made visible, not the final code.
- `preview-dashboard.png`: Dashboard, window 1440 x 800, **not** full page: this is one whole screen.
- `preview-dashboard-1366.png`: Dashboard, window 1366 x 650 (a small laptop).
- `preview-people.png` and `preview-money.png`: 1440 wide, full page.

**Dashboard (`/`).** A light grey-green page. On the left the sidebar with a deep-teal pill on "Dashboard". On the canvas, a big dark-teal wash at the top (dark at the top left, lighter to the right, fading down). The title "Dashboard" and the finding line are white on it. On the right: the language switch, the search field (a white pill), an outlined white "Search" pill and a white-filled "Plan a Visit" pill with deep-teal text. Row 1: "This week" and "Needs a visit" as two white cards that sit on the lower part of the wash. Row 2: Services (a mid-teal line, faint gridlines), then **"Money this month" as the one dark card, a teal gradient** (white amounts; Balance in light green, or light red if negative), then Sent documents. The whole page fits the window; at 1366 x 650 two lists show a thin scroll bar inside their card.

**People (`/people`).** The wash says "People" with "Add a Person" (white pill) and "Add from .xlsx file" (outlined white pill). Under it a white filter bar: pill chips for Status (the chosen one has a teal tint and a teal border) and a pill search field. Then one white card with the table: quiet bold header, thin lines, a light-teal row on hover. The table scrolls inside the card if it is too wide. No green or red.

**Money (`/money`).** The wash says "Money" with "Record Expense" (outlined white pill) and "Record Offering" (white pill). A white filter bar with the month chips and the month picker. A **light** totals strip with Offerings and Expenses in ink and Balance in bold green (red if below zero). Below: the Offerings card and the Expenses card side by side, then the Giving statement card. Amounts are right-aligned in tabular figures and stay ink. Green and red appear only on the Balance.

## 8. What I could not check, and what the implementer must check

- **Print:** I only emulated print media at 794px (Dashboard and Money): title black, no wash, no dark card. A real print preview was **NOT MEASURED**. Plan Task 6 covers it.
- **Dashboard between 861px and 1180px wide:** page scroll is allowed there and its height was not measured as one screen. Under 861px: page scroll allowed, not measured.
- **Browser:** Chromium only. Edge is the same engine. Other browsers were not tested. Page zoom other than 100% was not tested.
- **Keyboard scroll of "Sent documents"** (no links inside its rows): not measured.
- **The pin picture:** viewed, not pixel-measured.
- **Tests:** on the preview copy, `test_pages_ui` (B9 to B26, with B11 and B12), `test_server` and `test_db` ran: 85 tests, OK. This was after I took an Avoid word out of one CSS comment. The plan's own new tests (`test_style_uses_only_tokens` and others) do not exist yet.
- `--gap` 16 to 20 and `--card-pad` 20 to 24 make cards narrower inside. The Expenses table (needs about 450px) may scroll inside its card between 1250px and about 1300px. That is allowed (section 4.5). Task 5 may raise the `1250px` breakpoint for `.grid.money-month` if the pastor dislikes it. Also update the comment at the top of `style.css` ("16px gutter", "flat surfaces ... no shadows at rest", "near-black primary") so it matches, and keep Avoid words out of every comment.
- The preview was built from `git archive HEAD` (commit `8a137f7`). The real working folder has uncommitted edits, so a few words on screen may differ from what the pastor sees today. Colours and shapes do not depend on them.
- The preview adds the new rules at the end of `style.css`. The real change should edit the existing rules in place and keep one rule per selector.

## 9. Open questions for the pastor

Round 1 asked about the band colour. The pastor answered: use the dark gradient like the pin. That is now decision D1 and D3. Still open (if he gives no answer, this spec stands as written):

1. **Balance in green.** OK to show a Balance of 0 or more in green (red below 0)? Today only a negative Balance is red. The other choice: red below 0, ink otherwise.
2. **Active menu item.** OK as a filled deep-teal pill? Other choice: a quiet teal tint like the active chip.
3. **One screen on a small window.** The Dashboard fits one screen from 1181px wide and 640px high. On a window of 861px to 1180px wide, or shorter than 640px, the page scrolls. At 1366 x 650 the lists This week and Needs a visit show 4 and 3 rows and scroll inside the card for the rest. Is this OK?

## 10. Words check

This spec uses the words of `GLOSSARY.md` (Person, Status, Calendar item, Service, Head count, Offering, Expense, Giving statement, Year report, Private note, Handover, Needs a visit, Care log, Sent document, church copy). I did not use any word from the Avoid lists. I ran the repo's own `avoid_hits` check on this file and on `pastor-summary.md`: no hit.

## Appendix: the contrast script

```python
# WCAG 2.x contrast check for the Church Manager styling spec (round 2). Run: python contrast-check.py
# Round 2: the pale band is gone. A dark-teal wash sits at the top of the canvas (3 stops, left to right),
# the Money this month card has its own 3-stop gradient. Every gradient is tested at ALL its stops.
P = dict(
    ground="#F4F6F6", surface="#FFFFFF", raised="#E8F0F0", active="#D5E6E5",
    text="#0F2A2C", muted="#47605F", faint="#566E6E", accent="#2C6E70", focus="#2C6E70",
    primary="#0F3D3E", primary_ink="#FFFFFF", primary_hover="#2C6E70",
    positive="#1B7A4A", negative="#B3261E", control="#7E9696",
    # the wash (top of the canvas): left stop, middle stop, right stop (the lightest place any text sits on)
    wash_from="#0F3D3E", wash_via="#1D5A5C", wash_to="#2A6C6E",
    wash_ink="#FFFFFF", wash_soft="#E4F1F0", wash_btn_fill="#FFFFFF", wash_btn_ink="#0F3D3E",
    wash_line="#FFFFFF", wash_focus="#FFFFFF",
    # the dark card: top-left stop, middle stop, bottom-right stop
    hl="#0F3D3E", hl_mid="#1D5A5C", hl_end="#28696B", hl_ink="#FFFFFF", hl_muted="#E1EEED",
    pos_dark="#9AF2C4", neg_dark="#FFD6D2", hl_focus="#FFFFFF",
    refusal_bg="#FFEDEA", refusal_ink="#831C1E",
    grid="#E3EBEB", grid_base="#C2D0D0",
)

def lin(c):
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
def rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
def lum(h):
    r, g, b = rgb(h); return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
def mix(top, alpha, bottom):
    """A colour `top` at opacity `alpha` over `bottom`, as hex."""
    t, b = rgb(top), rgb(bottom)
    return "#%02X%02X%02X" % tuple(round(alpha * x + (1 - alpha) * y) for x, y in zip(t, b))
# derived colours: a white pill hover (12% white) over the lightest wash stop; the wash 6% below the fade start
P["wash_hover"] = mix("#FFFFFF", 0.12, P["wash_to"])
P["wash_low"] = mix(P["ground"], 0.06, P["wash_to"])      # the wash at the very bottom of the text band (200px)
def ratio(a, b):
    la, lb = sorted((lum(P[a]), lum(P[b])), reverse=True)
    return (la + 0.05) / (lb + 0.05)

STOPS = (("left stop", "wash_from"), ("middle", "wash_via"), ("right stop", "wash_to"), ("lowest point (200px)", "wash_low"))
# (what, foreground, background)
TEXT = [
 ("body text on card", "text", "surface"), ("body text on page ground", "text", "ground"),
 ("body text on hover / Private note panel", "text", "raised"), ("body text on tint (chip on, flash, tag)", "text", "active"),
 ("muted on card", "muted", "surface"), ("muted on page ground (sidebar)", "muted", "ground"),
 ("muted on hover / Private note panel", "muted", "raised"), ("muted on tint (tag)", "muted", "active"),
 ("faint on card (dash, placeholder, no-items text)", "faint", "surface"), ("faint on page ground", "faint", "ground"), ("faint on Private note panel", "faint", "raised"),
 ("accent text on card (today, Services, chart end value)", "accent", "surface"), ("accent text on page ground", "accent", "ground"),
 ("deep teal on tint (active chip, Today tag)", "primary", "active"), ("deep teal on page ground (church name)", "primary", "ground"),
 ("primary button text", "primary_ink", "primary"), ("primary button text, hover", "primary_ink", "primary_hover"),
 ("active nav item text", "primary_ink", "primary"),
 ("positive amount on card", "positive", "surface"), ("negative amount / error on card", "negative", "surface"),
 ("negative error on Private note panel", "negative", "raised"), ("danger button on hover", "negative", "raised"),
 ("refusal text", "text", "refusal_bg"), ("refusal heading word", "refusal_ink", "refusal_bg"),
 # white fill pill inside the wash (the main action) and the search field
 ("wash primary pill: deep teal text on white fill", "wash_btn_ink", "wash_btn_fill"),
 ("wash primary pill, hover: deep teal text on tint fill", "wash_btn_ink", "active"),
 ("search field in the wash: ink on white", "text", "surface"),
 ("note under a list (white note): muted on white", "muted", "surface"),
 ("language switch, current: ink on white pill", "text", "surface"),
 ("outlined pill text, hover (12% white on right stop)", "wash_ink", "wash_hover"),
]
for i, (label, key) in enumerate(STOPS):   # text on the wash, tested at both ends and in between
    TEXT.insert(3 * i, (f"page title (h1) on wash, {label}", "wash_ink", key))
    TEXT.insert(3 * i + 1, (f"finding line on wash, {label}", "wash_soft", key))
    TEXT.insert(3 * i + 2, (f"search label / language switch / outlined pill text on wash, {label}", "wash_soft", key))
# the dark card at all three stops
for label, key in (("top-left stop", "hl"), ("middle stop", "hl_mid"), ("bottom-right stop", "hl_end")):
    TEXT += [(f"Money this month: ink, {label}", "hl_ink", key), (f"Money this month: muted, {label}", "hl_muted", key),
             (f"Money this month: positive Balance, {label}", "pos_dark", key), (f"Money this month: negative Balance, {label}", "neg_dark", key)]

NONTEXT = [  # minimum 3:1 (WCAG 1.4.11)
 ("input border on card", "control", "surface"), ("Services line on card", "accent", "surface"),
 ("focus ring on card", "focus", "surface"), ("focus ring on page ground", "focus", "ground"),
 ("focus ring on tint", "focus", "active"), ("focus ring beside deep teal fill (gap is white)", "focus", "surface"),
 ("focus ring on dark card, bottom-right stop", "hl_focus", "hl_end"), ("focus ring on dark card, top-left stop", "hl_focus", "hl"),
 ("chart base line on card (information only)", "grid_base", "surface"),
]
for i, (label, key) in enumerate(STOPS):
    NONTEXT.insert(2 * i, (f"focus ring (white) on wash, {label}", "wash_focus", key))
    NONTEXT.insert(2 * i + 1, (f"outlined pill border (white) on wash, {label}", "wash_line", key))

print(f"{'TEXT PAIR':74} {'fg':8} {'bg':8} ratio  need 4.5")
low = (9e9, "")
for w, f, b in TEXT:
    r = ratio(f, b)
    if r < low[0]: low = (r, w)
    print(f"{w:74} {P[f]:8} {P[b]:8} {r:5.2f}  {'PASS' if r >= 4.5 else 'FAIL'}")
print(f"LOWEST TEXT RATIO: {low[0]:.2f}  ({low[1]})")
print(f"\n{'NON-TEXT PAIR':74} {'fg':8} {'bg':8} ratio  need 3.0")
lown = (9e9, "")
for w, f, b in NONTEXT:
    r = ratio(f, b)
    if "information" not in w and r < lown[0]: lown = (r, w)
    print(f"{w:74} {P[f]:8} {P[b]:8} {r:5.2f}  {'PASS' if r >= 3 else ('info' if 'information' in w else 'FAIL')}")
print(f"LOWEST NON-TEXT RATIO: {lown[0]:.2f}  ({lown[1]})")
```

## After approval (pastor rules)

These rules came after the pastor said yes to round 2. Where they differ from the text above, they win. `web/style.css` follows them.

| # | Rule | What the code does |
|---|---|---|
| A1 | The colors come from the app color (pastor rule on t_be2d76ac) | The teal hex values in sections 3, 4 and 6 are only the look of one color. `--primary*`, `--focus` and the `--wash-*` colors are not tokens of their own: they are built from the app color the pastor picks in Settings, as the `--accent-*` tokens (`--accent`, `--accent-base`, `--accent-text`, `--accent-light`, `--accent-dark`, `--accent-deep`), `--on-accent` and `--gradient`. The page head sets 4 of them. |
| A2 | Today tag | An outlined pill: `--accent-text` text and a 1px edge in the same color, no fill. |
| A3 | Main button in the title row, on hover | Its text is underlined; the fill stays `--on-accent`. |
| A4 | Text of the current chip (the tint chip) | `--accent-deep`, bold: it reads on the `--active` tint (contrast). |
| A5 | The wash grows with the head (STYLE-FIX-1) | The wash is never shorter than before (`--wash-h` 340px; `--wash-h-narrow` 600px under 861px). When the head is taller (a long title, a flash, buttons wrapped under the title), the wash ends `--wash-fade` + 8px under the title row (a CSS anchor on `.title-row`), so every text on it sits on the solid part. The fade is a fixed length at its bottom: `--wash-fade` 136px (`--wash-fade-narrow` 240px), 40% of the old heights, so a short head looks as before. A browser with no CSS anchors keeps the fixed height. |
