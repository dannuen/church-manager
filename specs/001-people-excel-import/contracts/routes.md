# Contract: Pages and forms

All pages use the normal layout, both languages, and the existing form helpers (`ui.form`,
`ui.field`, `ui.button`). Words are keys in the `people` section of the text table.

| Method | Path | Input | Result |
|---|---|---|---|
| GET | `/people` | — | Existing page. New secondary button "Add from .xlsx file" → `/people/file`. |
| GET | `/people/file` | — | Pick page: file field `file` (accept `.xlsx`), Check button, "Get the empty file" link, short format help. |
| POST | `/people/file` | multipart: `file` | 200 check page (see below). Bad or missing file: 400, pick page with one sentence. Nothing is saved. |
| POST | `/people/file/save` | form: `rows` (JSON text from the check page) | All OK after re-check: 303 to `/people?msg=…` ("N people added", "M new Families"). Any error: 400 check page again. Nothing saved on error. |
| GET | `/people/file/empty.xlsx` | — | 200, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, download name "Tep danh sach nguoi.xlsx" / "People file.xlsx" by screen language. |

## Check page

- A count line: "30 rows: 28 OK, 2 with errors, 3 warnings".
- A table: row number, full name, gender, birth date, phone, Status, Family (+ "new Family"),
  Family role, and a last column with OK, the error sentences (column + what to fix) or the
  warnings.
- Ignored column titles, if any, in one line.
- No error: a Save button (form posts hidden `rows` to `/people/file/save`) and Cancel (link to
  `/people/file`).
- Any error: no Save button; a sentence "Fix these rows in the file, then pick it again." and the
  pick form.

## Not in this contract

- No Hermes door command (FR-015).
- No change to any existing route.
