# Round 4 "Pearl": what is left for the page code

Round 4 gave the app the pastor's pearl look with `web/style.css` only (see `DESIGN.md`). Six parts of the
pastor's mockup need page code, so they are not built. This file says how to build each one so it lands
on the same look. The mockup to compare with: `docs/mockups/8-tweaks.html` (open it in a browser, paste the
settings line of `DESIGN.md` into the box at the bottom of its panel, press Apply).

**The look is written already.** For every part below, the CSS is in `web/style.css` under the heading
"round 4: ready for later pages". Write the HTML with the class names given here and it is styled. Do not
write new CSS for these parts unless a step below says so.

## Rules for any page work after round 4

1. Use the classes that exist: `.panel`, `.rows` and `.row`, `.kpi`, `.btn`, `.input`, `.chip`, `.tag`,
   `.grid` with `.span-N`. A new page built from them needs no CSS.
2. No `style` attribute in HTML and no raw color outside `:root` (tests check both). A new look is a class
   in `web/style.css`, its colors made from the `:root` tokens.
3. A token used in a paint rule must be one `web/print.css` turns to ink, grey or white (the paper test).
   Safe: `--text`, `--muted`, `--surface`, `--ground`, `--raised`, `--active`, `--border`, `--rule`,
   `--control`, `--accent-text`, `--accent-dark`, `--shadow`, `--shadow-raised`.
4. Body text stays 16px on 24px lines; a page title keeps 36px lines under 861px.
5. Motion only inside `@media (prefers-reduced-motion: no-preference)`. The test
   `test_secondary_danger_hover_error_and_disabled` lists the moves allowed: a new one is the pastor's call.
6. Words on screen come from `GLOSSARY.md` and the text table (`churchmgr/i18n.py`), in both languages.

## 1. The church picture (the hero photo)

**The pastor sees:** in Settings, a field to choose one picture of the church. On every page that picture
fills the top of the page, under the menu and behind the title card, soft and a little dark, and fades out
at its lower edge. With no picture the top stays plain pearl, as now.

**Build:**
- Settings: one file field (JPEG, PNG or WebP; refuse other kinds and a file over 5 MB with a plain sentence)
  and a "Remove the picture" action. Keep the file inside the church copy folder, next to `documents/`, under
  one fixed name. It is the church's own data: it is part of a Handover. Never keep it in `web/`.
- A route that serves that one file to the open church copy (for example `GET /church-picture`), with its
  real content type. The CSP allows it (`img-src 'self'`). No path from the request reaches the file system.
- `churchmgr/ui.py`, `_app_color_style()`: when the church copy has a picture, add one more token to the
  `<style>:root{...}` it writes: `--hero-image:url(/church-picture?v=<file time>)`.
- `churchmgr/ui.py`, `page()`: when there is a picture, write `<div class="app has-hero">` instead of
  `<div class="app">`.
- `web/print.css` already hides the wash (`.canvas::before`): the picture never prints. Nothing to change there.

**Already styled** (`.has-hero`): the picture covers the wash at `50% 52%` (the pastor's position 52), blur
4px, 4% darker, 360px high (`--wash-h`); from 861px it runs under the menu bar, which gets a white veil;
the language switch gets a white pill; on the Dashboard the title card sits 54px lower.

**The pastor's values, do not change them:** `heroh 360`, `menuover 1`, `photoy 52`, `pblur 4`, `dim 0.04`.

**Tests to add:** the token and the class are in the page only when a picture is set; the route refuses
anything but the one file; a Handover holds the picture; a church copy with no picture renders as before.

## 2. The figures strip on the Dashboard

**The pastor sees:** under the title card, one white card with 3 big figures side by side: how many Calendar
items in the next 7 days, how many People need a visit, the Balance of this month. No 01 02 03 numbers.

**HTML** (in `churchmgr/pages/dashboard.py`, between the title row and `<div class="grid dashboard">`):

```html
<section class="figures" aria-label="...">
  <div class="figure"><span class="figure-label">Next 7 days</span><span class="figure-value num">8 Calendar items</span></div>
  <div class="figure"><span class="figure-label">Needs a visit</span><span class="figure-value num">37 People</span></div>
  <div class="figure"><span class="figure-label">Balance, November 2026</span><span class="figure-value num">16.140.000 ₫</span></div>
</section>
```

Use the values `dashboard()` loads already (`week`, `needs`, `totals`) and the words of the text table
(`dashboard.finding_week`, `dashboard.persons`, `dashboard.balance`). A part that failed to load shows a dash.

**Watch:** the finding line of the title row says the Calendar item count already (CRIT-3: a number is said
once). Take it out of the finding line when the strip shows it, and update that test.

## 3. The "next Calendar item" card

**The pastor sees:** at the right of the picture, a small dark glass card with the next Calendar item: its
day, time and kind on one small line, its title in large serif letters, and a link to it.

**HTML** (a child of `<main class="canvas">`, right after the title row, on the Dashboard only):

```html
<aside class="next-item" aria-label="...">
  <span class="when">Tomorrow · 19:00 · Meeting</span>
  <a class="what" href="/calendar/12">Họp Ban Chấp Sự</a>
</aside>
```

It is the first row of Next 7 days (`items[0]`); with no Calendar item, write nothing. From 1181px the CSS
places it at the right of the wash; under that it is a full-width card in the flow. It is styled for screen
only, so on paper it is plain text.

## 4. A dot on every Service in the chart

**The pastor sees:** a small ring on each Head count of the Services line, and a filled dot on the newest.

**Build** in `services_svg()` (`churchmgr/pages/dashboard.py`): after the `<polyline class="line">`, in the
**outer** `<svg class="chart">` (not in the stretched inner `<svg class="plot">`, where a circle would turn
into an oval), one circle per Head count:

```html
<circle class="dot" cx="42.86%" cy="61.0" r="3.5"/>
<circle class="dot last" cx="100%" cy="88.2" r="4.5"/>
```

`cx` is the same percentage `x(i)` gives the date labels; `cy` is `y(count)`. The chart height stays
`CHART_HEIGHT` (B17). `.chart .dot` and `.chart .dot.last` are styled.

## 5. The kind of a Calendar item as a small tag

**The pastor sees:** on the Dashboard rows, the kind (Meeting, Visit, Service) as a small grey tag at the
right, instead of plain grey words.

**Build:** in `_this_week()`, wrap the kind word in `<span class="tag">`. `.tag` exists (20px high, the tint
of the app color, a pill). The place or the name after it stays plain. Check the row at 390px: the tag must
not push the page sideways.

## 6. Letter spacing of the titles (the pastor's value: 2.5)

The Avoid-word test (`test_no_avoid_words_in_pages_app_and_web`) forbids the CSS property `letter-spacing`
in `web/`. Ask the pastor first: he set 2.5 on the tweak page, but the ban is a rule of the project. If he
says yes, lift the ban for that one property and add to `web/style.css`:

```css
.title-row h1, .panel h2 { letter-spacing: 2.5px; }
```

Then check a long Vietnamese title at 390px: wide spacing wraps earlier.

## Not possible, by decision

- **Dark mode:** the app is light only (`test_style_uses_only_tokens`).
- **Line height 1.15 for body text:** see `DESIGN.md`.
