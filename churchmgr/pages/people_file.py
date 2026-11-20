"""People file pages: ``/people/file`` (pick a .xlsx file, see the check page), ``/people/file/save`` and
``/people/file/empty.xlsx`` (the empty file: the column titles, and a Help sheet with one example row).

Rules kept here:
- A row is checked with the rules of the Add a Person form, by calling them (``text.clean_name``,
  ``people._gender``, ``people_pages.birth_from_input``, ``people_pages.past_or_today``,
  ``people_pages.add_person_from_form``), never a copy. A Birth date may be a year only (stored ``1980-00-00``).
- A Family is found by its name without diacritics (``family.name_folded``): no match = one new Family for
  all the rows with that name, two or more = a row error. Save writes it with ``people.add_family`` and
  ``people_pages.set_family_from_form``. A Family already in the church copy is never changed: a Person
  only joins it (a new Family link). No Chi phái is set from a file.
- A Family with no Family role typed gets Head when the Full name is the Family name (without diacritics, in
  any case), else Other. A typed Family role always wins; a Family role with no Family is a row error.
- Nothing is saved before Save. Save checks the rows again (the hidden field is input like any other)
  and writes every row in one transaction: one bad row and nothing is saved, no Person and no Family.
- A file of 2 or more rows where every name is already in the church was maybe saved before: Save needs the
  box "Add them again anyway" (``all_in_church``), and Save checks that again too.
- The picked file is read once and never kept. A Private note is never read from a file: a column
  with that title is an ignored column like any unknown one.
- Words on screen come from the text table (section ``people``); the pastor's own values are shown as
  typed, in ``lang="vi"``.
"""

import json
import re
import uuid

from .. import db, i18n, lists, people, schema, settings, text, ui, xlsx
from ..i18n import TextError, t, tn
from ..server import Response, content_disposition
from ..ui import h, vi
from . import people as people_pages

# The columns of a People file, in the order of the empty file. A title matches the screen word of
# ``people.file_col_<key>`` in either language, or the key itself, without diacritics and in any case.
COLUMNS = ("full_name", "gender", "birth_date", "phone", "address", "note", "status", "start_date", "family",
           "family_role")
ACCEPT = ".xlsx," + xlsx.MEDIA_TYPE
USED_CODES = "people_file_used"  # setting: the codes of the newest Saves that worked, as a JSON list
KEEP_CODES = 200
CODE = re.compile(r"[0-9a-f]{32}")  # what new_code() gives
# The example row of the Help sheet. Gender, Status and Family role are added from the screen words and the
# Status list.
EXAMPLE = {"full_name": "Nguyễn Văn An", "birth_date": "31/12/1980", "phone": "0912345678", "address": "12 Lê Lợi",
           "start_date": "01/01/2024", "family": "Gia đình Nguyễn Văn An"}


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

def _role_words(lang):
    """The screen words of the Family roles in ``lang``, in the order of ``schema.FAMILY_ROLES``."""
    return [t(f"core.family_role_{code.lower()}", lang) for code in schema.FAMILY_ROLES]


def _lookups(conn):
    """What a row is checked against, read once per file: gender words, Status items by folded word,
    the Status names, the folded names of the Persons already in the church copy, the Family role codes by
    folded word (the codes and the screen words of both languages), and the Families by folded name."""
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
    roles = {text.fold(code): code for code in schema.FAMILY_ROLES}
    for lang in i18n.LANGS:
        roles.update(zip(map(text.fold, _role_words(lang)), schema.FAMILY_ROLES))
    families = {}
    for family in conn.execute("SELECT id, name, name_folded FROM family ORDER BY id"):
        families.setdefault(family["name_folded"], []).append(family)
    return genders, statuses, [item["name"] for item in items], names, roles, families


def _check_rows(conn, numbered, date1904):
    """Row checks (see ``data-model.md``) for ``numbered``: ``[(row number, {key: cell})]``. A cell is
    what the file holds (text, number or ``None``) or text from the check page. The sentences are in the
    language of the page."""
    genders, statuses, status_names, names, roles, families = _lookups(conn)
    new_names = {}  # the folded name of each new Family -> its name as the first row with it writes it
    checks = []
    for row, raw in numbered:
        values, errors = {}, []
        status_id = status_name = None
        family_id = family_name = new_family = None

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

        typed = xlsx.cell_text(raw.get("birth_date"))
        try:  # a date, or a year only (1980 -> 1980-00-00): the rule of the Add a Person form
            values["birth_date"] = people_pages.birth_from_input(raw.get("birth_date"), "people.birth_date",
                                                                 date1904) or ""
        except ValueError as exc:
            values["birth_date"] = typed
            refuse("birth_date", i18n.error_text(exc))
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

        # Family: a name of the church copy (joined), or a new name (one new Family per name); never two.
        values["family"] = xlsx.cell_text(raw.get("family"))
        if values["family"]:
            try:
                values["family"] = text.clean_name(values["family"], "families.name")
            except ValueError as exc:
                refuse("family", i18n.error_text(exc))
            else:
                folded = text.fold(values["family"])
                found = families.get(folded, [])
                if len(found) > 1:
                    refuse("family", t("people.file_err_family_two"))
                elif found:
                    family_id, family_name = found[0]["id"], found[0]["name"]
                else:
                    new_family = new_names.setdefault(folded, values["family"])
        typed = xlsx.cell_text(raw.get("family_role"))
        values["family_role"] = roles.get(text.fold(typed), typed)  # the code, or as typed when unknown
        if typed and values["family_role"] not in schema.FAMILY_ROLES:
            refuse("family_role", t("people.file_err_family_role", names=", ".join(_role_words(None))))
        elif typed and not values["family"]:
            refuse("family_role", t("people.file_err_family_needed"))
        elif values["family"] and not typed:  # empty: Head when the Full name is the Family name, else Other
            same = text.fold(values["family"]) == text.fold(values["full_name"])
            values["family_role"] = "Head" if same else "Other"

        checks.append({"row": row, "values": values, "status_id": status_id, "status_name": status_name,
                       "family_id": family_id, "family_name": family_name, "new_family": new_family,
                       "errors": errors, "warnings": [], "in_church": False})

    same = {}  # folded name -> the checks of the rows with that name
    for check in checks:
        if not any(key == "full_name" for key, _s in check["errors"]):
            same.setdefault(text.fold(check["values"]["full_name"]), []).append(check)
    for folded, group in same.items():
        for check in group:
            if folded in names:
                check["in_church"] = True
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


def all_in_church(checks):
    """True for a file of 2 or more rows where every name is a Person already in the church: it was maybe saved
    before (Back after Save sends the file again, and the new check page has a new code). Save then needs a second
    Yes, the box ``again``. One row only is a namesake, not a file saved before."""
    return len(checks) > 1 and all(c["in_church"] for c in checks)


def new_code():
    """The one-use code of one check page: its Save works once (a double click, or Back and Save, adds nothing).
    ``uuid4`` is 122 random bits from the system's random source."""
    return uuid.uuid4().hex


def save_people_file(conn, rows_json_text, code, again=False):
    """Save the rows of a check page (``rows_json`` text, and the page's ``new_code()``). Every row is
    checked again first. ``again``: the pastor ticked "Add them again anyway" (see ``all_in_church``).

    Returns ``(added, families, checks)``: ``(n, m, [])`` when all ``n`` rows were added in one transaction,
    with ``m`` new Families (one per new Family name, its address the first Address among its rows), or
    ``(0, 0, checks)`` when a row has an error now, or every name is in the church now and ``again`` is not set
    (nothing saved, the code can be used again). A hidden field that is not rows and a code of a check page,
    or a code of a Save that already worked, raises ``TextError``.
    """
    try:
        items = json.loads(rows_json_text)
    except (TypeError, ValueError) as exc:
        raise TextError("people.file_err_pick_again") from exc
    if not isinstance(items, list) or not items or not isinstance(code, str) or not CODE.fullmatch(code):
        raise TextError("people.file_err_pick_again")
    if len(items) > xlsx.MAX_ROWS - 1:  # the same limit as the file: the title row and 5,000 rows
        raise TextError("people.file_err_too_many_rows")
    numbered = []
    for item in items:
        if not (isinstance(item, dict) and type(item.get("row")) is int and isinstance(item.get("values"), dict)):
            raise TextError("people.file_err_pick_again")
        numbered.append((item["row"], {k: v for k, v in item["values"].items() if k in COLUMNS and isinstance(v, str)}))
    today = people_pages.today_text()
    # The used codes are read and written in the transaction of the Persons (BEGIN IMMEDIATE): two Saves of
    # one page at the same moment cannot both pass, and the codes are still known after a restart.
    with db.transaction(conn):
        used = json.loads(settings.get_setting(conn, USED_CODES) or "[]")
        if code in used:
            raise TextError("people.file_err_saved_already")
        checks = _check_rows(conn, numbered, date1904=False)
        if any(c["errors"] for c in checks) or (all_in_church(checks) and not again):
            return 0, 0, checks
        settings.set_setting(conn, USED_CODES, json.dumps((used + [code])[-KEEP_CODES:]))
        addresses = {}  # each new Family name -> the first Address among its rows
        for c in checks:
            if c["new_family"] and c["values"]["address"]:
                addresses.setdefault(c["new_family"], c["values"]["address"])
        made = {}  # each new Family name -> the id of the Family made for it, at its first row
        for c in checks:
            v = c["values"]
            start = v["start_date"] or today  # of the Status link and of the Family link
            pid = people_pages.add_person_from_form(conn, {
                "full_name": v["full_name"], "gender": v["gender"], "birth_date": v["birth_date"],
                "phone": v["phone"], "address": v["address"], "note": v["note"],
                "status_id": str(c["status_id"]) if c["status_id"] else "", "start_date": start,
            })
            if c["new_family"] and c["new_family"] not in made:
                made[c["new_family"]] = people.add_family(conn, c["new_family"], addresses.get(c["new_family"]))
            family_id = c["family_id"] or made.get(c["new_family"])
            if family_id:
                people_pages.set_family_from_form(conn, pid, {"family_id": family_id, "family_role": v["family_role"],
                                                              "start_date": start})
    return len(checks), len(made), []


# ---------------------------------------------------------------- the empty file

def _titles(lang):
    """The column titles of the empty file in ``lang``, in the order of ``COLUMNS``."""
    return [t(f"people.file_col_{key}", lang) for key in COLUMNS]


def help_rows(conn, lang):
    """The rows of the Help sheet in ``lang``: what the sheet is for; one line per column (its title, then how
    to fill it, with the words it takes and the names of the active Status items); then one example row under
    the column titles. The example is only here, never on the people sheet, so it is never added by mistake."""
    statuses = [item["name"] for item in lists.get_list(conn, "status")]  # active items only
    words = {  # the words a row may use, of both languages; each help line takes the ones it names
        "genders": ", ".join([t(key, other) for other in i18n.LANGS for key in people_pages.GENDER_WORDS.values()]
                             + list(people.GENDERS)),
        "statuses": ", ".join(statuses) or "—",
        "roles": ", ".join(dict.fromkeys([word for other in i18n.LANGS for word in _role_words(other)]
                                         + list(schema.FAMILY_ROLES))),
    }
    example = {**EXAMPLE, "gender": t(people_pages.GENDER_WORDS["M"], lang),
               "status": statuses[0] if statuses else None, "family_role": _role_words(lang)[0]}
    titles = _titles(lang)
    return ([[t("people.file_help_sheet", lang, people=t("people.file_sheet_people", lang))], [],
             [t("people.file_help_column", lang), t("people.file_help_how", lang)]]
            + [[title, t(f"people.file_help_{key}", lang, **words)] for key, title in zip(COLUMNS, titles)]
            + [[], [t("people.file_help_example", lang)], titles, [example.get(key) for key in COLUMNS]])


def empty_file(conn, lang):
    """The empty People file (bytes) in ``lang``. Sheet 1: the row of column titles only; its columns are Text
    cells, so a typed 0912345678 or 31/12/1980 stays as typed. Sheet 2: the Help sheet (``help_rows``)."""
    return xlsx.write([(t("people.file_sheet_people", lang), [_titles(lang)]),
                       (t("people.file_sheet_help", lang), help_rows(conn, lang))])


# ---------------------------------------------------------------- pages

def _pick_form(error=None):
    field = ui.field(t("people.file_pick"), "file", "", type="file", accept=ACCEPT, required=True, error=error)
    return ui.form("/people/file", field + ui.button(t("people.file_check")), multipart=True)


def _help(conn):
    """The format, in two sentences: the column titles, then the words Gender, Status and Family role accept
    (the screen words of both languages, each marked with its language)."""
    columns = ", ".join(t(f"people.file_col_{key}") for key in COLUMNS)
    keys = people_pages.GENDER_WORDS.values()
    genders = ", ".join([f'<span lang="{lang}">{h(", ".join(t(key, lang) for key in keys))}</span>'
                         for lang in i18n.LANGS] + list(people.GENDERS))
    roles = ", ".join(f'<span lang="{lang}">{h(", ".join(_role_words(lang)))}</span>' for lang in i18n.LANGS)
    statuses = ", ".join(item["name"] for item in lists.get_list(conn, "status"))
    lead = t("people.file_help", columns=columns, full_name=t("people.file_col_full_name"))
    words = ui.t_html("people.file_help_words", gender=h(t("people.file_col_gender")), genders=genders,
                      status=h(t("people.file_col_status")), statuses=h(statuses),
                      start_date=h(t("people.file_col_start_date")), family=h(t("people.file_col_family")),
                      family_role=h(t("people.file_col_family_role")), roles=roles,
                      full_name=h(t("people.file_col_full_name")))
    return f'<p class="lead">{h(lead)}</p><p class="hint">{words}</p>'


def _pick_page(req, error=None, status=200):
    body = f'<section class="panel narrow">{_help(req.conn)}{_pick_form(error)}</section>'
    empty = ui.link_button(t("people.file_empty"), "/people/file/empty.xlsx")
    return Response.html(ui.page(t("people.file_title"), body, "people", actions=empty), status)


def pick_page(req):
    return _pick_page(req)


def empty_get(req):
    """GET /people/file/empty.xlsx: the empty People file, in the language of the screens."""
    lang = ui.current_lang()
    return Response(200, empty_file(req.conn, lang), xlsx.MEDIA_TYPE,
                    {"Content-Disposition": content_disposition(t("people.file_download_name", lang))})


def _date_cell(value, birth=False):
    """A date of a row, or the value as typed when it is not one. ``birth``: a Birth date, where a year only
    (``1980-00-00``) shows as ``1980``."""
    if not value:
        return ui.DASH
    try:
        day = text.check_birth_date(value) if birth else text.check_date(value)
    except ValueError:  # as typed: not a date
        return vi(value)
    return people_pages.num(ui.fmt_birth_date(day) if birth else ui.fmt_date(day))


def _family_cells(check):
    """The Family cell (the Family found, or the new name with "new Family", or the name as typed) and the
    Family role cell (its screen word, or as typed)."""
    v = check["values"]
    if check["family_id"]:
        family = vi(check["family_name"])
    elif check["new_family"]:
        family = f'{vi(check["new_family"])} <span class="faint">{h(t("people.file_new_family"))}</span>'
    else:
        family = vi(v["family"]) if v["family"] else ui.DASH
    role = v["family_role"]
    if role in schema.FAMILY_ROLES:
        return [family, h(ui.family_role(role))]
    return [family, vi(role) if role else ui.DASH]


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
            _date_cell(v["birth_date"], birth=True), people_pages.num(v["phone"]) if v["phone"] else ui.DASH, status,
            start, *_family_cells(check), result]


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
        again = all_in_church(checks)  # maybe saved before: the box is a second Yes, checked again on Save
        # the inner div keeps the box at its own size, at the left (a .field is a grid and would stretch it)
        box = (f'<div class="field"><label for="f-again">{h(t("people.file_again"))}</label>'
               '<div><input id="f-again" name="again" type="checkbox" value="1" required></div></div>' if again else "")
        actions = (f'<div class="form-actions">{ui.button(t("core.btn_save"))}'
                   f'<a class="text-action" href="/people/file">{h(t("core.btn_cancel"))}</a></div>')
        lead = t("people.file_saved_before") if again else t("people.file_ready")
        top = (f'<p class="lead">{h(lead)}</p>' + ignored_html
               + ui.form("/people/file/save", ui.hidden("rows", rows_json(checks)) + ui.hidden("code", new_code())
                         + box + actions, data_once=True))
    today = people_pages.today_text()
    headers = [(t("people.file_row"), True), (t("people.file_col_full_name"), False),
               (t("people.file_col_gender"), False), (t("people.file_col_birth_date"), True),
               (t("people.file_col_phone"), False), (t("people.file_col_status"), False),
               (t("people.file_col_start_date"), True), (t("people.file_col_family"), False),
               (t("people.file_col_family_role"), False), (t("people.file_result"), False)]
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
    """POST /people/file/save: check the rows again, then add them all (and their new Families) in one
    transaction."""
    try:
        added, families, checks = save_people_file(req.conn, req.form.get("rows"), req.form.get("code"),
                                                   again=req.form.get("again") == "1")
    except ValueError as exc:
        return _pick_page(req, i18n.error_text(exc), 400)
    if not added:
        return _check_page(req, checks, [], 400)
    message = tn("people.file_added", added)
    if families:
        message += " " + tn("people.file_added_families", families)
    return Response.redirect(ui.url("/people", msg=message))


ROUTES = [
    ("GET", "/people/file", pick_page),
    ("POST", "/people/file", check_post),
    ("POST", "/people/file/save", save_post),
    ("GET", "/people/file/empty.xlsx", empty_get),
]
