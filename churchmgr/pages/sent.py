"""Sent documents (card C3): ``/sent`` (the Sent documents of one year and the next number) and
``/sent/new`` (date, Recipient, Purpose, subject and an optional file).

Rules kept here:
- The number is given only by ``sent.add_sent_document`` when the Sent document is saved, so it is
  never typed and never used twice. The page only shows the next one (``sent.next_number``).
- The file goes in through ``documents.add_document`` in the same transaction as the Sent document;
  if the save fails, the new file is removed again.
- A hidden Recipient or Purpose is not offered and is refused for a new Sent document. Old Sent
  documents keep showing its name.
- Words on screen come from the text table (section ``sent``). Numbers (06/2026), subjects and the
  Recipient and Purpose items are data, shown as stored.
"""

import datetime as _dt

from .. import calendar as cal
from .. import documents as docs
from .. import i18n, lists, sent, text, ui
from ..db import transaction
from ..i18n import TextError, t, tn
from ..server import Response
from ..ui import h, vi
from .people import date_field, empty, form_error, list_panel, num, panel, table, today_text

# form field -> TEXT key of its label. A refusal whose English sentence starts with the English label
# shows next to that field.
_LABELS = {"date": "sent.date", "recipient_id": "sent.recipient", "purpose_id": "sent.purpose",
           "subject": "sent.subject", "file": "sent.file"}


def year_of(value, today):
    """``?year=`` -> the year (empty = this year). A bad value raises ``ValueError``."""
    raw = (value or "").strip()
    return today.year if not raw else cal.check_year(raw)


def placed_errors(exc):
    """Where to show a refused Sent document: ``{field: sentence}`` in the language of the page. The
    field is the one whose English label starts the English sentence (``str(exc)``), else ``""`` (the
    whole form). ``None`` gives ``{}``."""
    if exc is None:
        return {}
    english = str(exc)
    shown = i18n.error_text(exc)
    for name, key in _LABELS.items():
        if english.startswith(t(key, "en")):
            return {name: shown}
    return {"": shown}


def sent_date(value):
    """The Sent document date as ``YYYY-MM-DD``: a real date, not after today; else a ``TextError``
    that starts with "Date"."""
    day = text.check_date(value or "", "sent.date")
    if day > today_text():
        raise TextError("sent.err_after_today", today=ui.fmt_date(today_text()))
    return day


def require_shown_item(conn, value, list_name, label):
    """The list item chosen in a form. Missing, from another list or hidden raises ``TextError``
    starting with ``label`` (a TEXT key; so the sentence shows next to that field)."""
    try:
        item = lists.require_item(conn, value or "0", list_name)
    except ValueError:
        raise TextError("lists.err_choose", label=label) from None
    if not item["active"]:
        raise TextError("sent.err_hidden", label=label, name=item["name"])
    return item


# ---------------------------------------------------------------- /sent

def _year_chips(year, today):
    def chip(label, y, current=False):
        mark = ' aria-current="true"' if current else ""
        href = "/sent" if y == today.year else ui.url("/sent", year=y)
        return f'<a class="chip" href="{h(href)}"{mark}>{h(label)}</a>'
    links = ((chip(f"‹ {year - 1}", year - 1) if year > 1900 else "")  # a Sent documents year is 1900 to 9999
             + chip(t("sent.this_year"), today.year, year == today.year)
             + (chip(f"{year + 1} ›", year + 1) if year < 9999 else ""))
    return f'<div class="list-toolbar"><nav class="chips" aria-label="{h(t("sent.years"))}">{links}</nav></div>'


def _subject_cell(row):
    """The subject, and under it the file of the Sent document (a download link) when there is one."""
    if row["document_id"] is None:
        return vi(row["subject"])
    link = f'<a href="/documents/{int(row["document_id"])}/file">{vi(row["document_name"])}</a>'
    return f'{vi(row["subject"])}<span class="cell-sub">{ui.t_html("sent.file_link", link=link)}</span>'


def _next_panel(conn, year, rows):
    next_no = sent.next_number(conn, year)
    head = (f'<div class="kpi next-number" data-row><span class="kpi-value num">{h(next_no)}</span>'
            f'<span class="kpi-sub">{h(t("sent.next_hint"))}</span></div>')
    counts = {}
    for r in rows:
        counts[r["recipient_name"]] = counts.get(r["recipient_name"], 0) + 1
    if counts:
        by = "".join(f'<div><dt lang="vi">{h(name)}</dt><dd class="num">{n}</dd></div>'
                     for name, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
        breakdown = (f'<h3 class="sub-head">{h(t("sent.by_recipient", year=year))}</h3>'
                     f'<dl class="kv counts">{by}</dl>')
    else:
        breakdown = ""
    return panel("next-number", t("sent.next_number"), head + breakdown)


def list_page(req):
    conn = req.conn
    today = _dt.date.today()
    year = year_of(req.query.get("year"), today)
    rows = sent.list_sent_documents(conn, year)
    lines = [[num(r["number"]), num(ui.fmt_date(r["date"])), vi(r["recipient_name"]), h(r["purpose_name"]),
              _subject_cell(r)] for r in reversed(rows)]
    if lines:
        body = table([(t("sent.number"), False), (t("sent.date"), False), (t("sent.recipient"), False),
                      (t("sent.purpose"), False), (t("sent.subject"), False)], lines, "sent")
    else:
        body = empty(t("sent.empty", year=year))
    main = list_panel("sent-list", t("sent.list", year=year), body)
    content = (_year_chips(year, today)
               + f'<div class="grid sent"><div class="span-8 stack">{main}</div>'
               f'<div class="side-4 stack">{_next_panel(conn, year, rows)}</div></div>')
    sub = h(t("sent.sub", year=year, count=tn("sent.count", len(rows)), next=sent.next_number(conn, year)))
    actions = ui.link_button(t("sent.add"), "/sent/new", "primary")
    return Response.html(ui.page(t("sent.title"), content, "sent", sub=sub, actions=actions))


# ---------------------------------------------------------------- /sent/new

def _options(conn, list_name):
    return [("", t("sent.choose"))] + [(i["id"], i["name"]) for i in lists.get_list(conn, list_name)]


def _new_form(req, values=None, error=None, status=200):
    """The form; ``error`` is the refusal (an exception) of the last save, or ``None``."""
    conn = req.conn
    v = (values or {}).get
    errors = placed_errors(error)
    year = _dt.date.today().year
    number = f'<strong class="num">{h(sent.next_number(conn, year))}</strong>'
    lists_link = f'<a href="/lists">{h(t("core.nav_lists"))}</a>'
    inner = (
        date_field(t("sent.date"), "date", "f-date", v("date"), errors.get("date"), min_date="1900-01-01",
                   hint=t("sent.date_hint"))
        + '<div class="inline-fields two">'
        + ui.select_field(t("sent.recipient"), "recipient_id", _options(conn, "recipient"),
                          selected=v("recipient_id", ""), required=True, lang="vi", error=errors.get("recipient_id"))
        + ui.select_field(t("sent.purpose"), "purpose_id", _options(conn, "purpose"), selected=v("purpose_id", ""),
                          required=True, error=errors.get("purpose_id"))
        + "</div>"
        + ui.field(t("sent.subject"), "subject", v("subject", ""), required=True, autocomplete="off", lang="vi",
                   error=errors.get("subject"), hint=t("sent.subject_hint"))
        + ui.field(t("sent.file"), "file", "", type="file", error=errors.get("file"),
                   hint=t("sent.file_hint", mb=docs.MAX_SIZE // (1024 * 1024)), data_max_bytes=docs.MAX_SIZE,
                   data_text_too_large=t("documents.err_too_large", mb=docs.MAX_SIZE // (1024 * 1024)))
        + f'<p class="hint">{ui.t_html("sent.number_hint", number=number, lists=lists_link)}</p>'
        + form_error(errors) + ui.button(t("sent.save"))
    )
    body = f'<section class="panel narrow" data-panel="sent-form">{ui.form("/sent/new", inner, multipart=True)}</section>'
    return Response.html(ui.page(t("sent.add"), body, "sent"), status)


def new_page(req):
    return _new_form(req)


def new_post(req):
    conn = req.conn
    f = req.form
    chosen = req.files.get("file")
    path = None
    try:
        day = sent_date(f.get("date"))
        recipient = require_shown_item(conn, f.get("recipient_id"), "recipient", "sent.recipient")
        purpose = require_shown_item(conn, f.get("purpose_id"), "purpose", "sent.purpose")
        subject = text.clean_text(f.get("subject"))
        if subject is None:
            raise TextError("errors.required", label="sent.subject")
        if chosen is not None and not chosen[1]:
            raise TextError("sent.err_empty_file")
        with transaction(conn):
            doc_id = None
            if chosen is not None:
                doc_id = docs.add_document(conn, req.state.copy_folder, chosen[1], chosen[0])
                path = docs.document_path(conn, req.state.copy_folder, doc_id)
            _sid, number = sent.add_sent_document(conn, day, recipient["id"], purpose["id"], subject, doc_id)
    except ValueError as exc:
        if path is not None:
            path.unlink(missing_ok=True)
        if getattr(exc, "key", None) == "documents.err_too_large":  # shown next to the File field
            exc = TextError("sent.err_too_large", **exc.params)
        return _new_form(req, f, exc, 400)
    except BaseException:
        if path is not None:
            path.unlink(missing_ok=True)
        raise
    msg = t("sent.saved", number=number)
    return Response.redirect(ui.url("/sent", year=int(day[:4]), msg=msg))


ROUTES = [
    ("GET", "/sent", list_page),
    ("GET", "/sent/new", new_page),
    ("POST", "/sent/new", new_post),
]
