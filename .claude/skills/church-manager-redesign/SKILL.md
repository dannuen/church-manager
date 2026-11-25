---
name: church-manager-redesign
description: Use when changing the look of the Church Manager dashboard (new style, softer or friendlier look, new fonts or colors, a "redesign", restyling pages in web/style.css), or when asked to apply a design skill stack (ui-ux-pro-max, frontend-design, impeccable, web-design-guidelines, webapp-testing) to this app.
---

# Church Manager redesign

## Overview

A redesign here is a design change only: same pages, words, data and features. The video's skill
stack (design system → design plan → critique and polish → guidelines review → screenshots) works,
but its React + Tailwind build does not: this app is Python standard library, HTML built in
`churchmgr/pages/*.py`, plain CSS in `web/style.css`, offline, and every page works without JS.

**Core principle:** the look is tokens in `:root` made from the pastor's one app color, and the
tests guard contrast, layout and the pastor's past decisions. Change values; keep the guards.

## The steps, in order

**0. Route and read.** In a chat, a change request goes to the `church-manager` board (AGENTS.md)
unless the pastor said "do it here". Before planning, read what is already decided:
- `hermes kanban --board church-manager list` and any redesign card's comments;
- `docs/design-critique-*.md` and `git log --oneline -20`: findings may already be fixed on main.
  Re-check them; do not redo them;
- the comments in `web/style.css`: "approved by the pastor", "spec D2", "CRIT-n" mark decisions;
- `DESIGN.md` if it exists.

**1. Set up.** Worktree branch `wt/redesign` from main; if it already exists, read its `DESIGN.md`
and diff and continue it, or ask the pastor before starting a second one. Fake church in a temp folder outside
OneDrive with `--copies-root` pointing at that temp folder too (never the real copies). Run
`python -m unittest discover -s tests` now: you need a green baseline to know which failures are yours.
Screenshot the current pages with the built-in browser.

Two skills of the video are not installed here. Stand-ins: webapp-testing (Playwright, a
package) → the built-in browser at 390px and 1440px; web-design-guidelines →
`design:accessibility-review` or `impeccable` audit.

**2. Ask the pastor** (one round, choices with a recommendation): how big a change (refresh or
new look), the feel (2-3 options with a small preview), and fonts (Windows fonts, or bundle one).
Bundling = a download: name file, source (github.com/google/fonts, OFL) and size, and wait for yes.
Fonts must have the `vietnamese` subset.

**3. Design system (ui-ux-pro-max).** Run `--design-system`, then judge each part on its own. It
usually returns a landing-page pattern, a dark tech palette, a coding font and GSAP: reject them and
write why in `DESIGN.md`. Re-run once narrower (`--domain style`, `--domain typography` with
"vietnamese"). Colors are never fixed hex: they are mixes of the app color tokens.

**4. Shared pass first (frontend-design).** Edit rules in place (keep comments true; no override
block at the end). Fonts go in `web/fonts/` with their OFL files AND in `STATIC_FILES` in
`churchmgr/server.py`, a fixed dict of path to type: `"fonts/Nunito.ttf": "font/ttf",` (sub-folder
paths work; `@font-face` uses `url("/static/fonts/Nunito.ttf")`). Restart the server after it. Then show the pastor desktop and phone screenshots and get a
yes on the direction before restyling page by page.

**5. Page by page, then impeccable critique → fix → polish.** Then screenshots at 390px and 1440px
of every page, fix, re-shoot.

**6. Done** = the look checked with 3 far-apart app colors in Settings (a dark one, a red, a very
light one such as #ffffcc), all tests pass, `python verify.py` prints `ALL ... CHECKS PASS`, the pastor saw the
after-shots. Commit or merge only when the pastor asks.

## Values that break things

| Change | What breaks | Keep |
|---|---|---|
| body `line-height` (24px) or h1 (36px) | dashboard row math, phone language switch | these two numbers |
| `letter-spacing` or any Avoid word, also in comments | the Avoid-word test scans `web/` too | GLOSSARY.md words |
| `transition` / `animation` | "hover never moves" (pastor, round 2) | no motion |
| a token in a paint rule that print.css does not reset (e.g. `--accent-base`) | the paper test | `--accent-dark`, `--text`-based shadows |
| `--muted` / `--faint` text on the wash or a tint | contrast on a tint | `--text` at full strength there |
| `churchmgr/app_color.py` | the contrast math for every color | leave it alone |
| `print.css` | paper output | leave it alone |

## When a test fails

Read the test before changing it. Three kinds:
- **Pins an old value** (a radius, a gradient string, a weight): update it to the new value and
  mark `# round N`.
- **Guards a property** (contrast, tokens only, no raw colors, 44px taps, no sideways scroll, one
  focus ring, no inner scroll): fix the CSS, never the test.
- **Records a pastor decision** (its docstring or the CSS comment names it): fix the CSS, or ask the
  pastor. Never decide it in the test.

## Red flags: stop

- About to type a Google Fonts URL, a CDN, React, Tailwind or `pip install`.
- About to "fix" findings from an old critique without checking main.
- About to restyle every page before the pastor saw the shared pass.
- About to edit a test because it is "outdated" without saying which kind it is.
