# Design: Change Status takes any past date

Status: waiting for the pastor's approval. Size: small project.

## Intent
Some people were Members in the past and left. The pastor cannot record that now: "Change Status" refuses a
date earlier than the Person's last change (`_set_history`, `churchmgr/people.py:55`; the date picker has
`min = latest_change`, `churchmgr/pages/people.py:469`). The pastor wants to choose the date freely and
build the history of a Person by adding changes in any order.

## Goals
- On the Person page, "Change Status" accepts any date from the Person's start to today, in any order of
  entry. A Status lasts until the next change, so a history has no gaps and no overlaps.
- Example: a Person has `Visitor from 15/03/2024`. The pastor adds `Member from 01/01/2010`, then
  `Left from 30/06/2018`. Result: Member 2010 to 2018, Left 2018 to 2024, Visitor 2024 to now.

## Non-goals
- Family, Chi phái, Trưởng Chi phái and Ministry history keep their rule: no date before the last change.
  `_set_history` is shared, so the new behavior is opt-in for Status only.
- No edit or delete of a history line. No change to the People file (one Status per row) or to Add and Edit Person.
- No "Add an old period" form (the pastor chose option C over it).

## Anti-goals
- No Status line is ever deleted. A line's Status and start date are never changed.

## Approaches
- A. "Add an old period" form (Status, start, end). Keeps rule 4 fully. Not picked.
- B. Edit any history line. Breaks rule 4. Rejected.
- **C. "Change Status" takes any past date (picked by the pastor).** Smallest for the pastor: same form,
  no gaps possible.

## Decisions
- **Rule 4 exception, approved by the pastor:** when a change falls inside a closed line, that line's
  `end_date` becomes the new date (the line is cut in two). Its Status and start date stay. The new line
  runs from the new date to the old end date of the cut line. Example: Visitor 2010 to 2024, add Left on 2018
  gives Visitor 2010 to 2018 and Left 2018 to 2024.
- Cases for a new date D on a Person's Status history:
  - D is after the last start: as today (close the open line, open a new one).
  - D is before the first start: new line from D to the first start.
  - D is inside a line (start < D < end, or the open line): cut it as above.
  - D equals the start of any line: refused with a clear sentence (a Status already starts that day).
  - Same Status as the line that covers D: no change, as today.
  - D after today: refused, as today.
- Two neighbors with the same Status can end up next to each other (e.g. Member, Member). Allowed, not merged.
- Only the data layer changes the history (`people.set_status`); the page only passes the date.
- The date picker on the Status form loses its `min`. The hint tells the pastor that an earlier date adds
  to the past.

## Left to the builder
- How to opt in: a keyword on `_set_history` (e.g. `backdate=False`) or a separate Status function.
  `set_status` is called by the Add Person form, the People file and the Hermes door: check them all.
  The Hermes door (`agent.py`) should keep today's rule unless the pastor says otherwise.
- Screen words (English and Vietnamese, per GLOSSARY.md) and the refusal sentence.
- Tests: all cases above, history order on the Person page, the unique index "one open line per person"
  (`schema.py:242`) is never broken, `python verify.py` passes.
- Check what else reads "the latest Status line" (Care `NOT_CARED_STATUS_CODES`, People list, Handover)
  and that a past change does not alter the current Status.
