# GOAL: Build Church Manager

Build Church Manager: an offline app that helps one senior pastor run one church, with a database and a dashboard as the final product. Read IDEA.md and GLOSSARY.md in this folder first. Use the glossary words exactly. Never invent other names.

## THE PASTOR SEES (dashboard, one page)
- This week: Calendar items in date order.
- Needs a visit: people whose last Visit is older than 3 months (setting can change).
- Services: recent Head counts with a simple trend.
- Money this month: Offerings, Expenses, balance.
- Sent documents: the next number for this year (like 06/2026).
- Search: type a name, find the Person. Vietnamese works with or without diacritics.

## THE PASTOR CAN DO (from the app, not only from code)
- People: add and edit Persons. Set Status, Family, Chi phái, Trưởng Chi phái, Ministry and role. Open a Person to see their whole story.
- Calendar: add and repeat Calendar items, list who joins or serves, record a Head count per Service.
- Money: record Offerings (amount, Fund, optional Giver) and Expenses (amount, Spending category). Print a yearly Giving statement for a person or family.
- Care: mark a Visit done. See the Care log.
- Documents: attach files to a Person, Family or Calendar item. Record Sent documents with date, Recipient, Purpose and an automatic number per year. Recipient and Purpose lists are editable.
- Copies: do a Handover (Private notes removed). Start a New church setup (blank, default lists only).

## RULES
1. Offline only. No cloud, no web login. One church = one church copy (one database file + one documents folder).
2. History is never lost. Status, Family, Chi phái and Trưởng Chi phái changes keep start and end dates.
3. Private notes are for the pastor only. They never appear in a Handover, a print or a Giving statement.
4. Vietnamese first. UTF-8 and NFC everywhere. Names, diacritics and search are always right.
5. Easy for one non-technical person. No training needed.
6. Keep it small. Choose the simplest stack. Do not add a dependency for a few lines of code.
7. Decide tech, layout and build order yourself. Ask the user only if a rule conflicts with the glossary.
8. Docs never name other people's products, apps or companies. This is most important in research notes. Describe the idea in plain words ("a local daemon", "a code index tool"), not the product. Allowed: Hermes, Python, SQLite, standard web tech, and official specs (like MCP).

## NOT IN SCOPE
User accounts, online sync, email or SMS, mobile app, online payments, many churches in one view.

## DONE MEANS
Every gate the user adds with `/goal gate` passes, and `python verify.py` exits 0.
The team must create `verify.py` itself as part of this goal. It runs all tests, builds a fake church of about 50 people, checks every dashboard panel has real data, makes a Handover and proves it has no Private notes.
Also write a short README.md: how to start, where the church copy is saved, how to do a Handover.
Save the church copy OUTSIDE OneDrive (the project folder is inside OneDrive; the live church copy must not be).
