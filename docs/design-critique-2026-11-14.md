# Design critique 2026-11-14
Base: main @ 879e3d3 + uncommitted edits (calendar.py, settings.py, server.py)
Method: dual-agent (A: design review · B: detector + browser evidence), fake church, desktop 1440px + phone 390px
Score: 27/40 (Acceptable). Detector found 0 issues, but it only reads markup, and pages are built from Python strings. The measured evidence below is the real data.

Severity: P0 Blocker, P1 Major, P2 Minor, P3 Polish.
No P0 found. Rules to keep (AGENTS.md): money is whole dong (int); history kept with dates; private notes never shown; use GLOSSARY.md words.

## Findings

| # | Severity | Page | Problem | Why it matters to the pastor | Files (best guess) | Suggested fix |
|---|---|---|---|---|---|---|
| 1 | P1 | People, Care, all pages (phone) | Tap targets too small at 390px. People row link is only the name text (88x19px, 132 of 158 controls). Care "Plan" `.row-action` 48x24px. Language buttons 75x28px at every width. Card links 157x24px. Money links 137x19px. | Missed taps on a phone. Tapping beside a name does nothing. | `web/style.css` (`.row .row-action`, `.lang-switch button`, `.card-link`, `table.list` @640) | Min height 44px under 861px. Make the whole row tappable with a stretched link (`td:first-child a::after{position:absolute;inset:0}` with `tr{position:relative}`). |
| 2 | P1 | Nav (phone) | 13 items in one sideways-scrolling strip, about 4 visible. Scrollbar thumb looks like a stray underline under the wrong tab. Items cut off ("Sent documen..."). Settings, Search, Copies off screen. | The pastor cannot see that other pages exist. The bar looks broken. | `web/style.css` `.nav` @860 | Wrap nav onto 2-3 rows and hide the scrollbar, or show 5 main items plus "More". |
| 3 | P1 | All tables and lists | Links look like body text (`a{color:inherit;text-decoration:none}`). Only hover shows an underline; phones have no hover. `.card-link` has the same bold ink as card titles. | Names are the main way into a Person, Family or Chi phái page. Nothing shows a name can be clicked. | `web/style.css` (line 75, `.card-link`) | Show links in `--accent-text` (or underline) inside `td`, `.row .what`, `.card-link`. |
| 4 | P1 | Dashboard vs Calendar | "This week" means two ranges. Dashboard: 14/11-20/11, 7 items. Calendar chip: 09/11-15/11, 3 items. | The pastor sees 7 then 3 and stops trusting numbers. | `churchmgr/pages/dashboard.py`, `churchmgr/pages/calendar.py` | Rename the Dashboard card "Next 7 days", or make both use the Mon-Sun week. |
| 5 | P2 | Dashboard | Lists sit in small scroll boxes. Sent documents shows 2 of 3 rows; This week 6 of 7; Needs a visit 6 of 37. | Mouse wheel gets stuck in cards. Hidden rows are easy to miss. | `web/style.css` STYLE-2 (lines 652-688) | Fixed number of rows, no inner scroll, "View all N" link. |
| 6 | P2 | Dashboard | Emphasis inverted. Money this month is the only dark card with the only colored figure. Needs a visit is plain. | Attention goes to money before people who need care. | `web/style.css` (`[data-panel="money-month"]`), `churchmgr/pages/dashboard.py` | Move the highlight to Needs a visit, or drop it. NOTE: code says the pastor approved the dark Money card (spec D2). Ask the pastor before changing. |
| 7 | P2 | Money, Care, Lists, Documents | Actions come in 4 looks (header pills, "+" folding pills, ink links with "›", bare bold words). Bold "Edit"/"Plan" on each row outweighs name and amount. | Cannot tell what a control does from how it looks. Row actions outweigh data. | `web/style.css` (`table.money td.edit a`, `.row-action`, `details.rename>summary`, `.link-btn`) | Row actions: weight 400, `--accent-text`. Keep bold for data and titles. |
| 8 | P2 | People, Money, Sent, Dashboard (phone) | Header stacks every action full width and repeats counts (People: "50 People" plus "All 50" chip; Money: balance twice, Record buttons twice; Sent: Next number twice). | On a phone the pastor scrolls past chrome before data. On People the first person starts about 670px down. | `web/style.css` `.title-row .actions` @860; title-row sub lines in the pages | Under 861px put action buttons side by side or keep only the main one. Remove repeated counts. |
| 9 | P2 | Calendar, Money | Too many ways to change period: Prev/This/Next, Month chip, "Go to a month" picker, Show button. On phone "December 2026 ›" wraps alone. | Too many controls. | `churchmgr/pages/calendar.py`, `churchmgr/pages/money.py`, `web/style.css` `.chips` | Prev/This/Next on one row with short labels. Picker applies on change; keep a no-JS fallback (pages must work without JS). |
| 10 | P2 | Copies | Developer words: `church.db`, `--copy`, `current.txt`, "137 bytes". | Words the pastor cannot act on. | `churchmgr/pages/copies.py` (lines 188-197) | Put them under a "Technical details" fold. Use plain size words. |
| 11 | P2 | All pages | No skip link. Keyboard users pass brand, 13 nav items and 2 language buttons on every page. | Slow for keyboard users. | `churchmgr/ui.py` (page shell), `web/style.css` | Add "Skip to content" link to `<main id=...>`, shown on focus. |
| 12 | P2 | People | Status is plain text. "Passed away" / "Left" rows look like Members, with phone shown. | Pastoral risk: calling a household about someone who died. | `churchmgr/pages/people.py`, `web/style.css` | Show Left and Passed away rows muted or as a `.tag`. Consider hiding from "All" by default (ask first: changes what the list shows). |
| 13 | P3 | Calendar | Empty days each take a full row "Nothing on the Calendar." Bold day labels outweigh event titles. | Real events lost in noise. | `churchmgr/pages/calendar.py`, `web/style.css` `.cal-none`, `.cal-date` | Shrink empty days to date plus faint dash. Event titles weight 500+. |
| 14 | P3 | All pages | Header gradient fades into a muddy grey-blue smudge in the gutter and gaps (about x 232-257, y 210-340 at desktop). | Looks like a rendering fault. | `web/style.css` `--wash`, `--wash-fade` | Shorter fade (about 48px) or fade to a light tint of the app color. |
| 15 | P3 | Care vs People | Sort orders differ. People sorts by given name. Needs a visit ties sort by full name string. | Same person in different places. | `churchmgr/care.py` or `churchmgr/pages/care.py` | Sort ties by given name like People. |
| 16 | P3 | Settings (from evidence) | Detector evidence: primary button measured 1.00:1 contrast. Probably a false positive (background not resolved). Unverified. | If real, the button text is unreadable. | `web/style.css` (primary button on Settings) | Check by eye on a fake church first. Fix only if real. |

## Minor notes (merge into the P2/P3 polish card)
- Care: Done-date default comes before the planned date. Date fields show US format (11/14/2026) while lists show 16/11/2026.
- Services chart: 0-100 scale makes 91 to 74 look small.
- Money: Offerings table has no total row; Expenses has one.
- Dashboard: Needs a visit has 37 People, but the nav label "Thăm viếng" (Care) and the Calendar Visit kind share one Vietnamese word.
- `web/style.css` is built from stacked patch blocks (FIX-T 1b-4b, STYLE-2, STYLE-FIX-1-3). Extra care needed when editing.

## Strengths (do not break)
1. Glossary words and reassuring sentences in the right places (Sent document number, Lists, Handover).
2. Solid tokens: tested contrast for any app color, tabular figures, `13.850.000 ₫`, one focus ring (0 stops without a ring), reduced-motion respected, 0 horizontal page overflow at 390px on all pages.
3. Care flow: Needs a visit sorted by urgency; Plan link pre-fills the Person; Private note panel looks different.

## Not checked
Vietnamese UI live; invalid form submits; Families, Chi phái, Documents, Settings in detail; widths 861-1180px; dark mode and hover contrast; `aria-live` on live search (code reading only); whether `<html lang>` changes with the language switch.
