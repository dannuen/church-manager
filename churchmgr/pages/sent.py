"""Sent documents (card C3): ``/sent`` (the Sent documents of one year and the next number) and
``/sent/new`` (date, Recipient, Purpose, subject and an optional file).

Rules kept here:
- The number is given only by ``sent.add_sent_document`` when the Sent document is saved, so it is
  never typed and never used twice. The page only shows the next one (``sent.next_number``).
- The file goes in through ``documents.add_document`` in the same transaction as the Sent document;
  if the save fails, the new file is removed again.
- A hidden Recipient or Purpose is not offered and is refused for a new Sent document. Old Sent
  documents keep showing its name.
"""

import datetime as _dt

from .. import calendar as cal
from .. import documents as docs
from .. import lists, sent, text, ui
from ..db import transaction
from ..server import Response
from ..ui import h, vi
from .people import date_field, empty, field_errors, form_error, list_panel, num, panel, past_or_today, table

_LABELS = {"date": "Date", "recipient_id": "Recipient", "purpose_id": "Purpose", "subject": "Subject",
           "file": "File"}


def year_of(value, today):
    """``?year=`` -> the year (empty = this year). A bad value raises ``ValueError``."""
    raw = (value or "").strip()
    return today.year if not raw else cal.check_year(raw)


def require_shown_item(conn, value, list_name, label):
    """The list item chosen in a form. Missing, from another list or hidden raises ``ValueError``
    starting with ``label`` (so the sentence shows next to that field)."""
    try:
        item = lists.require_item(conn, value or "0", list_name)
    except ValueError:
        raise ValueError(f"{label}: choose one from the list.") from None
    if not item["active"]:
        raise ValueError(f"{label}: {item['name']} is hidden in Lists. Choose another one, or show it again in Lists.")
    return item


# ---------------------------------------------------------------- /sent

def _year_chips(year, today):
    def chip(label, y, current=False):
        mark = ' aria-current="true"' if current else ""
        href = "/sent" if y == today.year else ui.url("/sent", year=y)
        return f'<a class="chip" href="{h(href)}"{mark}>{h(label)}</a>'
    links = (chip(f"‹ {year - 1}", year - 1) + chip("This year", today.year, year == today.year)
             + chip(f"{year + 1} ›", year + 1))
    return f'<div class="list-toolbar"><nav class="chips" aria-label="Years">{links}</nav></div>'


def _subject_cell(row):
    """The subject, and under it the file of the Sent document (a download link) when there is one."""
    if row["document_id"] is None:
        return vi(row["subject"])
    return (f'{vi(row["subject"])}<span class="cell-sub">File: <a href="/documents/{int(row["document_id"])}/file">'
            f'{vi(row["document_name"])}</a></span>')


def _next_panel(conn, year, rows):
    next_no = sent.next_number(conn, year)
    head = (f'<div class="kpi next-number" data-row><span class="kpi-value num">{h(next_no)}</span>'
            '<span class="kpi-sub">Given when you save. A number is never used twice.</span></div>')
    counts = {}
    for r in rows:
        counts[r["recipient_name"]] = counts.get(r["recipient_name"], 0) + 1
    if counts:
        by = "".join(f'<div><dt lang="vi">{h(name)}</dt><dd class="num">{n}</dd></div>'
                     for name, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
        breakdown = f'<h3 class="sub-head">{year} by Recipient</h3><dl class="kv counts">{by}</dl>'
    else:
        breakdown = ""
    return panel("next-number", "Next number", head + breakdown)


def list_page(req):
    conn = req.conn
    today = _dt.date.today()
    year = year_of(req.query.get("year"), today)
    rows = sent.list_sent_documents(conn, year)
    lines = [[num(r["number"]), num(ui.fmt_date(r["date"])), vi(r["recipient_name"]), h(r["purpose_name"]),
              _subject_cell(r)] for r in reversed(rows)]
    if lines:
        body = table([("Number", False), ("Date", False), ("Recipient", False), ("Purpose", False),
                      ("Subject", False)], lines, "sent")
    else:
        body = empty(f"No Sent document in {year} yet.")
    main = list_panel("sent-list", f"Sent documents of {year}", body)
    content = (_year_chips(year, today)
               + f'<div class="grid sent"><div class="span-8 stack">{main}</div>'
               f'<div class="side-4 stack">{_next_panel(conn, year, rows)}</div></div>')
    sub = h(f"{year} · {ui.plural(len(rows), 'Sent document', 'Sent documents')} · newest first · "
            f"Next number {sent.next_number(conn, year)}")
    actions = ui.link_button("Record a Sent document", "/sent/new", "primary")
    return Response.html(ui.page("Sent documents", content, "sent", sub=sub, actions=actions))


# ---------------------------------------------------------------- /sent/new

def _options(conn, list_name):
    return [("", "— Choose —")] + [(i["id"], i["name"]) for i in lists.get_list(conn, list_name)]


def _new_form(req, values=None, error=None, status=200):
    conn = req.conn
    v = (values or {}).get
    errors = field_errors(error, "new", _LABELS)
    year = _dt.date.today().year
    inner = (
        date_field("Date", "date", "f-date", v("date"), errors.get("date"),
                   hint="The date written on the Sent document. Its year gives the number.")
        + '<div class="inline-fields two">'
        + ui.select_field("Recipient", "recipient_id", _options(conn, "recipient"), selected=v("recipient_id", ""),
                          required=True, lang="vi", error=errors.get("recipient_id"))
        + ui.select_field("Purpose", "purpose_id", _options(conn, "purpose"), selected=v("purpose_id", ""),
                          required=True, error=errors.get("purpose_id"))
        + "</div>"
        + ui.field("Subject", "subject", v("subject", ""), required=True, autocomplete="off", lang="vi",
                   error=errors.get("subject"), hint="For example: Mời dự Lễ Cung Hiến")
        + ui.field("File", "file", "", type="file", error=errors.get("file"),
                   hint=f"Optional. A copy of the Sent document, up to {docs.MAX_SIZE // (1024 * 1024)} MB.")
        + f'<p class="hint">Dated this year, it gets number <strong class="num">{h(sent.next_number(conn, year))}</strong>. '
          "Recipient and Purpose choices are edited in <a href=\"/lists\">Lists</a>.</p>"
        + form_error(errors) + ui.button("Save Sent document")
    )
    body = f'<section class="panel narrow" data-panel="sent-form">{ui.form("/sent/new", inner, multipart=True)}</section>'
    return Response.html(ui.page("Record a Sent document", body, "sent"), status)


def new_page(req):
    return _new_form(req)


def new_post(req):
    conn = req.conn
    f = req.form
    chosen = req.files.get("file")
    path = None
    try:
        day = past_or_today(f.get("date"), "Date")
        recipient = require_shown_item(conn, f.get("recipient_id"), "recipient", "Recipient")
        purpose = require_shown_item(conn, f.get("purpose_id"), "purpose", "Purpose")
        subject = text.clean_text(f.get("subject"))
        if subject is None:
            raise ValueError("Subject is required.")
        if chosen is not None and not chosen[1]:
            raise ValueError("File: the file is empty (0 bytes). Choose another file, or none.")
        with transaction(conn):
            doc_id = None
            if chosen is not None:
                doc_id = docs.add_document(conn, req.state.copy_folder, chosen[1], chosen[0])
                path = docs.document_path(conn, req.state.copy_folder, doc_id)
            _sid, number = sent.add_sent_document(conn, day, recipient["id"], purpose["id"], subject, doc_id)
    except ValueError as exc:
        if path is not None:
            path.unlink(missing_ok=True)
        message = str(exc)
        if message.startswith("The file is too large"):
            message = "File: " + message
        return _new_form(req, f, ("new", message), 400)
    except BaseException:
        if path is not None:
            path.unlink(missing_ok=True)
        raise
    msg = f"Saved as {number}. Write this number on the Sent document."
    return Response.redirect(ui.url("/sent", year=int(day[:4]), msg=msg))


ROUTES = [
    ("GET", "/sent", list_page),
    ("GET", "/sent/new", new_page),
    ("POST", "/sent/new", new_post),
]
