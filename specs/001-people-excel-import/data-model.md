# Data Model: Add People From an Excel File

No schema change. The feature writes only existing tables through existing functions.

## Read-only shapes (live only during one request)

### People file

| Field | Meaning |
|---|---|
| title row | Row 1 of the first sheet. Each cell maps to one column key, or is ignored. |
| rows | Rows 2…N. A row with all cells empty is skipped. Max 5,000 rows. |

### Column keys

| Key | Required | Rule (same as the app forms) |
|---|---|---|
| `full_name` | yes | `text.clean_name` |
| `gender` | no | M / F, or the screen words (R5) |
| `birth_date` | no | date (R2), not in the future (`past_or_today`) |
| `phone` | no | text, digits kept |
| `address` | no | text |
| `note` | no | normal note (never a Private note) |
| `status` | no | an active Status list item (R5) |
| `start_date` | no | date, not in the future; empty = today. Used for Status and Family links |
| `family` | no | Family name (R5) |
| `family_role` | when `family` is set | Head / Spouse / Child / Other, or the screen words |

### Row check

| Field | Meaning |
|---|---|
| `row` | The row number in the sheet (as the pastor sees it). |
| `values` | Cleaned text values by column key (dates as `YYYY-MM-DD`). |
| `status_id` | The matched list item id, or empty. |
| `family_id` / `new_family` | The matched Family id, or the name of the Family to make. |
| `errors` | List of (column key, sentence). Any error stops Save. |
| `warnings` | List of sentences: same name in the church copy, same name as row N. Never stop Save. |

## Written on Save (existing tables)

| Table | Rows written | Through |
|---|---|---|
| `person` | one per row | `pages.people.add_person_from_form` |
| `person_status` | one per row with a Status (start = `start_date`, end empty) | same call |
| `family` | one per distinct new Family name; address = first non-empty `address` of its rows | `people.add_family` |
| `family_link` | one per row with a Family (start = `start_date`, end empty) | `pages.people.set_family_from_form` |

Nothing is updated or deleted. All rows are written in one transaction.

## States

```text
(no file) --pick file--> checked
checked --has errors--> checked (Save hidden; pick a fixed file)
checked --no errors, Save--> re-check --still OK--> saved (redirect to /people with "N people added")
                                      --now errors--> checked (shown again, nothing saved)
checked --Cancel--> (no file), nothing saved
```
