# Contract: The People file format

## The file

- Type: `.xlsx`. Only the **first sheet** is read. Other sheets (like "Help") are ignored.
- Max 10 MB, max 5,000 people rows.
- Row 1: column titles. Rows 2…: one Person per row. Empty rows are skipped.
- Column order does not matter. Titles match without diacritics and in any case, in either
  language.

## Columns

| Key | Title (vi) | Title (en) | Required | Accepted values |
|---|---|---|---|---|
| `full_name` | Họ và tên | Full name | yes | any text |
| `gender` | Giới tính | Gender | no | Nam, Nữ, Male, Female, M, F |
| `birth_date` | Ngày sinh | Birth date | no | 31/12/1980, 1980-12-31, or a date cell; or a year only, 1980 (text or number; a year from 1900); not in the future |
| `phone` | Điện thoại | Phone | no | text (keep it a Text cell to keep a leading 0) |
| `address` | Địa chỉ | Address | no | text |
| `note` | Ghi chú | Note | no | text; a normal note, seen by anyone with the church copy |
| `status` | Trạng thái | Status | no | a name in the Status list (Tín hữu, Thân hữu, Khách, …, or the English words) |
| `start_date` | Ngày bắt đầu | Start date | no | 31/12/1980, 1980-12-31, or a date cell (no year only); not in the future; empty = today |
| `family` | Gia đình | Family | no | an existing Family name, or a new name (makes one new Family) |
| `family_role` | Vai trò trong gia đình | Family role | no; only with a Family | Chủ gia đình, Vợ/Chồng, Con, Người thân khác, Head, Spouse, Child, Other. Empty: Head when Full name = Family name (no diacritics, any case), else Other. A typed role always wins |

The real title words come from the text table, so they always match the screen words. The table
above shows today's words.

## Errors (stop Save) and warnings (do not)

| Kind | When |
|---|---|
| error | Not a `.xlsx` file, empty sheet, no "Full name" column, more than 5,000 rows, file too big |
| row error | Empty full name; unknown gender; bad or future date (a year only before 1900 or after this year); Status not in the list; Family role set but no Family; unknown Family role; Family name matches two or more Families; Family name too long |
| warning | Full name same as a Person in the church copy; full name same as another row |

## The empty file (`/people/file/empty.xlsx`)

- Sheet 1: the title row in the current screen language; all columns are Text cells.
- Sheet 2 "Hướng dẫn" / "Help": one line per column (required, accepted values, the current
  Status names) and one example row.
