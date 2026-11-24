# DESIGN.md: Church Manager, round 4 "Pearl"

The look of the app on screen. It replaces round 2 (`docs/superpowers/specs/2026-11-12-app-styling-design.md`).
Paper (`web/print.css`) stays as it is. Plain CSS in `web/style.css`, no build, works offline.

Source: the pastor chose mockup take 7 (`docs/mockups/7-ngoc-trai-bo-cuc-1.html`), tuned it on the tweak
page (`docs/mockups/8-tweaks.html`) and gave these values on 24/11/2026:

`{"hweight":800,"htrack":2.5,"lh":1.15,"radius":10,"sheetradius":10,"btnradius":28,"chipradius":10,"div":"dotted","shy":8,"shblur":24,"shalpha":0.13,"shtint":1,"hl":0.55,"blur":8,"maxw":1800,"outer":10,"side":90,"cardpad":37,"rowpad":7,"split":"6-6","heroh":360,"menuover":1,"photoy":52,"pblur":4,"dim":0.04,"tinthue":0,"s_nums":0,"cthick":2,"cdots":1,"cdraw":1,"enter":"fade","dur":1400,"ease":"ease-out","hoverscale":1.005,"nudge":1,"rowhover":1,"countup":1,"grain":0.07,"focusw":2}`

## The rule of this round

Only `web/style.css` changes the look (and a few lines of `web/app.js` for the one move CSS cannot do). No
page code, no new file to serve. So later work on pages keeps working with it, and what needs new HTML is
written down for that work in `docs/redesign-pearl-for-hermes.md`.

## Decisions the pastor changed in this round

| Before | Now | The pastor's words |
|---|---|---|
| The menu is a sidebar from 861px | The menu is a bar of pills at the top at every width: 5 items and the "More" fold | "Move it to the top" |
| Hover never moves; no motion at all (round 2) | Motion from the tweak values, off when Windows asks for less motion | "Try to match the tweak I did, if you have to write js for it then do it." |
| DASH RULE 4: from 1181px the Dashboard fits one screen | The Dashboard is roomy and may scroll | "My design; it may scroll" |
| The title row sits on a wash of the app color, its text white | The title row is a frosted white card, its text ink; the wash is only the slot of a church picture | the mockup |

Each has a test that records it with the date (`tests/test_pages_ui.py`, `tests/test_app_color.py`).

## Tokens (`:root` of `web/style.css`)

| What | Token | Round 4 |
|---|---|---|
| Ground | `--ground` | pearl grey, 2% of the app color; with a white sheen at the top left |
| Sheet | `.app` | `--surface` at 58%, a white edge, at most 1800px wide, 10px from the window |
| Cards | `--surface`, `--radius-card` | white, 10px corners |
| Card shadow | `--shadow` | drop 8px, blur 24px, 13% of `--accent-dark`; a white line of light on the top edge (55%) |
| Lines between rows | `--rule` | dotted, 1px |
| Buttons | `--radius-pill` | pills |
| Fields, small boxes | `--radius-control`, `--radius` | 10px |
| Titles and big numbers | `--font-display` | Palatino Linotype, then Book Antiqua, Cambria; weight 800 for titles |
| Body | `--font` | Segoe UI, 16px on 24px lines (kept: a guard, and Vietnamese marks need the room) |
| Card title | `--fs-card` | 30px (24px under 861px) |
| Page title | | 48px from 861px, 60px on the Dashboard, 28px on a phone |
| Space | `--gap`, `--pad`, `--card-pad` | 28px, 90px (32px up to 1180px, 16px under 861px), 37px (24px up to 1180px) |
| The picture slot | `--hero-image`, `--wash`, `--wash-h` | `none`; 360px high |

Every color is still made from the one app color of Settings (`churchmgr/app_color.py`). The mockup's near
black is the app color `#1b1c1f`: the pastor sets it in Settings of the church copy.

## Motion

Only inside `@media (prefers-reduced-motion: no-preference)`; the `reduce` rule stops everything.

- A page opens: the title card, the cards, the filter bar and the Money totals fade in, 1400ms, ease-out.
- The Services line draws itself (3500ms).
- A Dashboard card grows ×1.005 under the pointer (200ms).
- A row lights up under the pointer (a color change, no move).
- A big money amount counts up from 0 in 1400ms (`web/app.js`; it ends as the server wrote it).

## What the pastor asked that is not in, and why

| Value | Why not | Where it stands |
|---|---|---|
| Line height 1.15 | body is 24px by a guard (the phone language switch sits on the first title line), and 1.15 clips ầ, ế between lines | titles are tight; body stays 24px |
| Row density 7 | rows stay 44px taps | 8px, as before |
| Arrow slides 1px | the "›" of a card link must never wrap alone to the next line (final walk) | left out |

## Rejected from the generated design system (ui-ux-pro-max), and why

- "Feature-Rich Showcase" pattern: a marketing page with repeated calls to action, not an app screen.
- "Liquid Glass" lensing and morphing: needs motion and blur everywhere; the pearl look uses one frosted card.
- Gold accent `#A16207`: the palette comes from the pastor's app color, not from a fixed hue.
- Cormorant / Montserrat from Google Fonts: a web font needs the internet or a bundled file; Palatino is on Windows and has the Vietnamese marks.
- GSAP scroll reveals: a library, and pages must work without JS.

Kept from it: near-black on a light ground, 4.5:1 for text, hover feedback of 150 to 300ms, motion off on request.

## Selectors ready for later pages

The pages write them now:

- The Dashboard: `.figures`, `.next-item`, `.chart .dot` and the kind of a Calendar item as a `.tag`.
- Every page head: `.has-hero` and `--hero-image`, when a church picture is set in Settings.
- `.title-row h1, .panel h2` have letter spacing 2.5px (the pastor's yes, 2026-11-24).
- `test_round_4_the_look_ready_for_later_pages_stays_in_style_css` keeps their rules in `web/style.css`.

## Kept as is

Every page, word and feature; the dark Needs a visit card; `web/print.css`; the contrast, focus ring, 44px
tap, no sideways scroll and no inner scroll guards; parts 1 to 3 of the DASH RULE; the 16 critique fixes of
2026-11-14.
