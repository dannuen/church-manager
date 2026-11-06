# Quickstart: check that Add People From an Excel File works

Use a fake church in a temp folder outside OneDrive (Constitution V). Never the real church copy.

## Setup

```bash
cd "C:/Users/danng/OneDrive/Desktop/Church Manager Hermes"
python -m churchmgr.fake "$LOCALAPPDATA/Temp/cm-people-file"
python app.py --copy "$LOCALAPPDATA/Temp/cm-people-file"
```

Open http://127.0.0.1:8765/people.

## Scenarios

| # | Do | Expect |
|---|---|---|
| 1 | Press "Thêm từ tệp .xlsx", then "Lấy tệp mẫu trống" | A `.xlsx` downloads. Sheet 1 has Vietnamese titles only; sheet 2 has help and one example. |
| 2 | Switch to English, get the empty file again | English titles. |
| 3 | Fill 30 rows in sheet 1 (some with Status, 4 rows with one new Family name, 2 rows with an existing Family name). Pick the file. | Check page: 30 OK, "new Family" on 4 rows. People count not changed yet. |
| 4 | Press Save | Back on People: "30 people added, 1 new Family". The new Family has 4 members with their Family roles; the existing Family has 2 more. Each Person page shows Status and Family with the start date. |
| 5 | Pick a file with an empty name on row 7 and birth date `31/02/1990` on row 12 | Rows 7 and 12 show the column and the problem. No Save button. |
| 6 | Pick a file with a name already in the church | A warning on that row. Save still works. |
| 7 | Pick a `.docx`, an empty file, and a file with no "Họ và tên" column | One clear sentence each. Nothing saved. |
| 8 | On a check page with no errors, press Cancel | Nothing saved. |
| 9 | Phone typed as a Text cell `0912345678` | Saved as `0912345678`. |

## Automatic checks

```bash
python -m unittest discover -s tests -p test_people_file.py
python -m unittest discover -s tests -p test_db.py   # the Avoid words check
python verify.py                                      # must print ALL ... CHECKS PASS
```

`tests/test_people_file.py` must cover: read an `.xlsx` made by `xlsx.write` (round trip); shared
strings and rich text; a date serial and a `dd/mm/yyyy` text date; a number phone without `.0`;
title matching in both languages without diacritics; each row error; same-name warnings; one new
Family for many rows; the 2-Families error; all-or-nothing (a row made bad between check and Save
leaves the People and Family counts unchanged); not-a-zip and too-many-rows sentences; no Private
note is written.
