# Contract: Pages and forms

All pages use the normal layout, both languages, and the existing form helpers (`ui.form`,
`ui.field`, `ui.button`). Words are keys in the `people` section of the text table.

| Method | Path | Input | Result |
|---|---|---|---|
| GET | `/people` | — | Existing page. New secondary button "Add from .xlsx file" → `/people/file`. |
| GET | `/people/file` | — | Pick page: file field `file` (accept `.xlsx`), Check button, "Get the empty file" link, short format help. |
| POST | `/people/file` | multipart: `file` | 200 check page (see below). Bad or missing file: 400, pick page with one sentence. Nothing is saved. |
| POST | `/people/file/save` | form: `rows` (JSON text from the check page), `code` (the one-use code of that check page) and `again` (`1` when the box "Add them again anyway" is ticked) | All OK after re-check: 303 to `/people?msg=…` ("N people added", "M new Families"). Any error: 400 check page again. 2 or more rows, every name already in the church, and no `again=1`: 400 check page again with the box. Nothing saved on error. A `code` already used: 400 "This list was already saved". |
| GET | `/people/file/empty.xlsx` | — | 200, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, download name "Tep danh sach nguoi.xlsx" / "People file.xlsx" by screen language. |

## Check page

- A count line: "30 rows: 28 OK, 2 with errors, 3 warnings".
- A table: row number, full name, gender, birth date, phone, Status, Family (+ "new Family"),
  Family role, and a last column with OK, the error sentences (column + what to fix) or the
  warnings.
- Ignored column titles, if any, in one line.
- No error: a Save button (form posts hidden `rows` and `code` to `/people/file/save`) and Cancel (link to
  `/people/file`). When 2 or more rows all have a name already in the church: the sentence "Every name in
  this file is already in the church. You may have saved this file before." and a required box `again`
  ("Add them again anyway") above Save.
- Any error: no Save button; a sentence "Fix these rows in the file, then pick it again." and the
  pick form.

## Not in this contract

- No Hermes door command (FR-015).
- No change to any existing route.
