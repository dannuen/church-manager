"""People file pages: ``/people/file`` (pick a .xlsx file, see the check page) and ``/people/file/save``.

Rules kept here:
- A row is checked with the rules of the Add a Person form, by calling them (``text.clean_name``,
  ``people._gender``, ``people_pages.past_or_today``, ``people_pages.add_person_from_form``), never a copy.
- Nothing is saved before Save. Save checks the rows again (the hidden field is input like any other)
  and writes every row in one transaction: one bad row and nothing is saved.
- The picked file is read once and never kept. A Private note is never read from a file: a column
  with that title is an ignored column like any unknown one.
- Words on screen come from the text table (section ``people``); the pastor's own values are shown as
  typed, in ``lang="vi"``.
"""

import json

from .. import db, i18n, lists, people, schema, text, ui, xlsx
from ..i18n import TextError, t, tn
from ..server import Response
from ..ui import h, vi
from . import people as people_pages

# The columns of a People file, in the order of the empty file. A title matches the screen word of
# ``people.file_col_<key>`` in either language, or the key itself, without diacritics and in any case.
COLUMNS = ("full_name", "gender", "birth_date", "phone", "address", "note", "status", "start_date", "family",
           "family_role")
# Family and Family role are read by story 3 of spec 001 (tasks T031-T032). Until then a file that has them
# shows them as ignored columns: never read in silence, never dropped in silence.
NOT_READ_YET = ("family", "family_role")
READ = tuple(key for key in COLUMNS if key not in NOT_READ_YET)
ACCEPT = ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def map_titles(title_row):
    """``(index_by_key, ignored_titles)`` for the row of column titles: the cell index of each known
    column, and the titles that are not a known column (or a second column of the same key), as typed.
    No Full name column: ``TextError("people.file_err_no_name_column")``."""
    keys = {}
    for key in COLUMNS:
        keys[text.fold(key)] = key
        for lang in i18n.LANGS:
            keys[text.fold(i18n.t(f"people.file_col_{key}", lang))] = key
    index, ignored = {}, []
    for i, cell in enumerate(title_row):
        title = xlsx.cell_text(cell)
        if not title:
            continue
        key = keys.get(text.fold(title))
        if key is None or key in index:
            ignored.append(title)
        else:
            index[key] = i
    if "full_name" not in index:
        raise TextError("people.file_err_no_name_column", title="people.file_col_full_name")
    return index, ignored


# ---------------------------------------------------------------- the check

def _lookups(conn):
    """What a row is checked against, read once per file: gender words, Status items by folded word,
    the Status names, and the folded names of the Persons already in the church copy."""
    genders = {text.fold(t(key, lang)): code
               for code, key in people_pages.GENDER_WORDS.items() for lang in i18n.LANGS}
    items = lists.get_list(conn, "status")  # active items only
    screen_words = {code: (vi_word, en_word) for code, vi_word, en_word in schema.DEFAULT_LISTS["status"]}
    statuses = {}
    for item in items:  # weakest first: the screen words of both languages, then the code, then the name
        for word in screen_words.get(item["code"], ()):
            statuses[text.fold(word)] = item
    for item in items:
        if item["code"]:
            statuses[text.fold(item["code"])] = item
    for item in items:
        statuses[text.fold(item["name"])] = item
    names = {row[0] for row in conn.execute("SELECT name_folded FROM person")}
    return genders, statuses, [item["name"] for item in items], names


def _check_rows(conn, numbered, date1904):
    """Row checks (see ``data-model.md``) for ``numbered``: ``[(row number, {key: cell})]``. A cell is
    what the file holds (text, number or ``None``) or text from the check page. The sentences are in the
    language of the page."""
    genders, statuses, status_names, names = _lookups(conn)
    checks = []
    for row, raw in numbered:
        values, errors = {}, []
        status_id = status_name = None

        def refuse(key, problem):
            column = t(f"people.file_col_{key}")
            errors.append((key, t("people.file_err_row", row=row, column=column, problem=problem)))

        def date(key, label):
            cell, typed = raw.get(key), xlsx.cell_text(raw.get(key))
            values[key] = ""
            if not typed:
                return
            day = xlsx.cell_date(cell, date1904)
            if day is None:
                values[key] = typed
                refuse(key, t("people.file_err_date"))
                return
            values[key] = day
            try:
                people_pages.past_or_today(day, label)
            except ValueError as exc:
                refuse(key, i18n.error_text(exc))

        typed = xlsx.cell_text(raw.get("full_name"))
        try:
            values["full_name"] = text.clean_name(typed, "people.full_name")
        except ValueError as exc:
            values["full_name"] = typed
            refuse("full_name", i18n.error_text(exc))

        typed = xlsx.cell_text(raw.get("gender"))
        try:
            values["gender"] = people._gender(genders.get(text.fold(typed), typed)) or ""
        except ValueError as exc:
            values["gender"] = typed
            refuse("gender", i18n.error_text(exc))

        date("birth_date", "people.birth_date")
        for key in ("phone", "address", "note"):
            values[key] = xlsx.cell_text(raw.get(key))

        values["status"] = xlsx.cell_text(raw.get("status"))
        if values["status"]:
            item = statuses.get(text.fold(values["status"]))
            if item is None:
                refuse("status", t("people.file_err_status", names=", ".join(status_names)))
            else:
                status_id, status_name = item["id"], item["name"]

        date("start_date", "people.start_date")
        checks.append({"row": row, "values": values, "status_id": status_id, "status_name": status_name,
                       "errors": errors, "warnings": []})

    same = {}  # folded name -> the checks of the rows with that name
    for check in checks:
        if not any(key == "full_name" for key, _s in check["errors"]):
            same.setdefault(text.fold(check["values"]["full_name"]), []).append(check)
    for folded, group in same.items():
        for check in group:
            if folded in names:
                check["warnings"].append(t("people.file_warn_same_church"))
            other = next((o for o in group if o is not check), None)
            if other is not None:
                check["warnings"].append(t("people.file_warn_same_row", row=other["row"]))
    return checks


def check_people_file(conn, data):
    """Read the People file in ``data`` (bytes) and check every row. Saves nothing.

    Returns ``(checks, ignored_titles)``. The row of column titles is the first row with a value; an
    empty row (no value in a read column) is skipped. A file that cannot be read raises ``TextError``.
    """
    sheet = xlsx.read_first_sheet(data)
    filled = [(n, row) for n, row in enumerate(sheet.rows, start=1) if any(xlsx.cell_text(c) for c in row)]
    if not filled:
        raise TextError("people.file_err_empty")
    title_row = filled[0][1]
    index, ignored = map_titles(title_row)
    for key in NOT_READ_YET:
        if key in index:
            ignored.append(xlsx.cell_text(title_row[index.pop(key)]))
    numbered = []
    for n, row in filled[1:]:
        raw = {key: row[i] for key, i in index.items()}
        if any(xlsx.cell_text(cell) for cell in raw.values()):
            numbered.append((n, raw))
    if not numbered:
        raise TextError("people.file_err_empty")
    return _check_rows(conn, numbered, sheet.date1904), ignored


def rows_json(checks):
    """The hidden field of the check page: the row numbers and the values read, as JSON text."""
    return json.dumps([{"row": c["row"], "values": c["values"]} for c in checks], ensure_ascii=False)


def save_people_file(conn, rows_json_text):
    """Save the rows of a check page (``rows_json`` text). Every row is checked again first.

    Returns ``(added, checks)``: ``(n, [])`` when all ``n`` rows were added in one transaction, or
    ``(0, checks)`` when a row has an error now (nothing saved). A hidden field that is not rows of a
    check page raises ``TextError``.
    """
    try:
        items = json.loads(rows_json_text)
    except (TypeError, ValueError) as exc:
        raise TextError("people.file_err_not_xlsx") from exc
    if not isinstance(items, list):
        raise TextError("people.file_err_not_xlsx")
    numbered = []
    for item in items:
        if not (isinstance(item, dict) and type(item.get("row")) is int and isinstance(item.get("values"), dict)):
            raise TextError("people.file_err_not_xlsx")
        numbered.append((item["row"], {k: v for k, v in item["values"].items() if k in READ and isinstance(v, str)}))
    if not numbered:
        raise TextError("people.file_err_empty")
    checks = _check_rows(conn, numbered, date1904=False)
    if any(c["errors"] for c in checks):
        return 0, checks
    today = people_pages.today_text()
    with db.transaction(conn):
        for c in checks:
            v = c["values"]
            people_pages.add_person_from_form(conn, {
                "full_name": v["full_name"], "gender": v["gender"], "birth_date": v["birth_date"],
                "phone": v["phone"], "address": v["address"], "note": v["note"],
                "status_id": str(c["status_id"]) if c["status_id"] else "",
                "start_date": v["start_date"] or today,
            })
    return len(checks), []


# ---------------------------------------------------------------- pages

def _pick_form(error=None):
    field = ui.field(t("people.file_pick"), "file", "", type="file", accept=ACCEPT, required=True, error=error)
    return ui.form("/people/file", field + ui.button(t("people.file_check")), multipart=True)


def _help(conn):
    """The format, in two sentences: the column titles, then the words Gender and Status accept."""
    columns = ", ".join(t(f"people.file_col_{key}") for key in READ)
    genders = ", ".join([t(key) for key in people_pages.GENDER_WORDS.values()] + list(people.GENDERS))
    statuses = ", ".join(item["name"] for item in lists.get_list(conn, "status"))
    lead = t("people.file_help", columns=columns, full_name=t("people.file_col_full_name"))
    words = t("people.file_help_words", gender=t("people.file_col_gender"), genders=genders,
              status=t("people.file_col_status"), statuses=statuses, start_date=t("people.file_col_start_date"))
    return f'<p class="lead">{h(lead)}</p><p class="hint">{h(words)}</p>'


def _pick_page(req, error=None, status=200):
    body = f'<section class="panel narrow">{_help(req.conn)}{_pick_form(error)}</section>'
    return Response.html(ui.page(t("people.file_title"), body, "people"), status)


def pick_page(req):
    return _pick_page(req)


def _date_cell(value):
    if not value:
        return ui.DASH
    try:
        return people_pages.num(ui.fmt_date(text.check_date(value)))
    except ValueError:  # as typed: not a date
        return vi(value)


def _row_cells(check, today):
    v = check["values"]
    gender = people_pages.GENDER_WORDS.get(v["gender"])
    status = h(check["status_name"]) if check["status_id"] else vi(v["status"])
    start = (_date_cell(v["start_date"]) if v["start_date"]
             else f'<span class="faint num">{h(ui.fmt_date(today))}</span>')
    lines = [f'<p class="error">{h(sentence)}</p>' for _key, sentence in check["errors"]]
    lines += [f'<p class="hint">{h(sentence)}</p>' for sentence in check["warnings"]]
    result = "".join(lines) or f'<span class="faint">{h(t("people.file_ok"))}</span>'
    return [people_pages.num(check["row"]), vi(v["full_name"]), h(t(gender)) if gender else vi(v["gender"]),
            _date_cell(v["birth_date"]), people_pages.num(v["phone"]) if v["phone"] else ui.DASH, status, start,
            result]


def _check_page(req, checks, ignored, status=200):
    """The check page: the count line, then Save (no error) or the rows to fix and the pick form, then
    every row with OK or its sentences."""
    bad = [c["row"] for c in checks if c["errors"]]
    summary = t("people.file_summary", rows=len(checks), ok=len(checks) - len(bad), bad=len(bad),
                warn=sum(1 for c in checks if c["warnings"]))
    ignored_html = (f'<p class="hint">{ui.t_html("people.file_ignored", names=vi(", ".join(ignored)))}</p>'
                    if ignored else "")
    if bad:
        top = (f'<p class="error" role="alert">{h(t("people.file_fix_rows"))} '
               f'{h(t("people.file_bad_rows", rows=", ".join(str(n) for n in bad)))}</p>'
               + ignored_html + _pick_form())
    else:
        actions = (f'<div class="form-actions">{ui.button(t("core.btn_save"))}'
                   f'<a class="text-action" href="/people/file">{h(t("core.btn_cancel"))}</a></div>')
        top = (f'<p class="lead">{h(t("people.file_ready"))}</p>' + ignored_html
               + ui.form("/people/file/save", ui.hidden("rows", rows_json(checks)) + actions))
    today = people_pages.today_text()
    headers = [(t("people.file_row"), True), (t("people.file_col_full_name"), False),
               (t("people.file_col_gender"), False), (t("people.file_col_birth_date"), True),
               (t("people.file_col_phone"), False), (t("people.file_col_status"), False),
               (t("people.file_col_start_date"), True), (t("people.file_result"), False)]
    table = people_pages.table(headers, [_row_cells(c, today) for c in checks], "people-file")
    body = (f'<div class="stack"><section class="panel narrow">{top}</section>'
            + people_pages.list_panel("people-file", t("people.file_title"), table) + "</div>")
    return Response.html(ui.page(t("people.file_title"), body, "people", sub=h(summary)), status)


def check_post(req):
    """POST /people/file: read the picked file and show the check page. Saves nothing."""
    picked = req.files.get("file")
    if picked is None:
        return _pick_page(req, t("people.file_err_missing"), 400)
    try:
        checks, ignored = check_people_file(req.conn, picked[1])
    except ValueError as exc:
        return _pick_page(req, i18n.error_text(exc), 400)
    return _check_page(req, checks, ignored)


def save_post(req):
    """POST /people/file/save: check the rows again, then add them all in one transaction."""
    try:
        added, checks = save_people_file(req.conn, req.form.get("rows"))
    except ValueError as exc:
        return _pick_page(req, i18n.error_text(exc), 400)
    if not added:
        return _check_page(req, checks, [], 400)
    return Response.redirect(ui.url("/people", msg=tn("people.file_added", added)))


ROUTES = [
    ("GET", "/people/file", pick_page),
    ("POST", "/people/file", check_post),
    ("POST", "/people/file/save", save_post),
]
