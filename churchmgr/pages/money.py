"""Money pages (card C2): ``/money`` (one month: totals, Offerings, Expenses),
``/money/offerings/new``, ``/money/expenses/new`` and ``/money/statement`` (the printable
Giving statement of one Person or one Family for one year). ``/money/offerings/<id>/edit`` and
``/money/expenses/<id>/edit`` correct a row in place; ``.../delete`` removes it after one question.

Rules kept here:
- An amount is typed as text and read only by ``money.parse_amount`` (whole dong). It is shown
  only with ``money.format_vnd``. No float, no money maths in JS.
- An Offering with no Giver is shown as "no-name offering".
- The Giving statement shows only what ``money.giving_statement`` returns: date, Fund, given by,
  amount, total. Never a Private note, never an Offering note.
"""

import datetime as _dt

from .. import calendar as cal
from .. import lists, people, text, ui
from .. import money as money_data
from ..server import Response
from ..ui import h, vi
from .calendar import month_chip, month_picker, month_step, month_text, parse_month
from .people import (card_link, empty, family_link, field_errors, form_error, not_found, num, panel,
                     past_or_today, person_link, today_text)

NO_NAME = "no-name offering"
AMOUNT_HINT = "Whole dong, for example 1.250.000 or 1250000."
MIN_DATE = "1900-01-01"  # an Offering or Expense date has a year from 1900 (money._money_date)


# ---------------------------------------------------------------- small logic (tested)

def parse_giver(value):
    """The Giver field: ``""`` -> ``(None, None)`` (a no-name offering), ``"person-5"`` -> ``(5, None)``,
    ``"family-3"`` -> ``(None, 3)``. Anything else raises ``ValueError``."""
    raw = (value or "").strip()
    if not raw:
        return None, None
    kind, _, rid = raw.partition("-")
    if kind == "person":
        return text.to_id(rid, "Giver"), None
    if kind == "family":
        return None, text.to_id(rid, "Giver")
    raise ValueError("Giver must be a Person, a Family, or none.")


def month_of(value, today):
    """``?month=`` -> ``(year, month)``; empty -> this month."""
    if not (value or "").strip():
        return today.year, today.month
    return parse_month(value)


def money_cell(amount, strong=False):
    cls = "num strong" if strong else "num"
    return f'<span class="{cls}">{h(money_data.format_vnd(amount))}</span>'


def giver_cell(row):
    """Who gave an Offering: a link to the Person or Family, or the no-name offering label."""
    if row["giver_person_id"] is not None:
        return person_link(row["giver_person_id"], row["giver_name"])
    if row["giver_family_id"] is not None:
        return family_link(row["giver_family_id"], row["giver_name"])
    return f'<span class="faint">{NO_NAME}</span>'


def _table(name, headers, rows, total_label, total, edits=None):
    """A money table: ``headers`` = ``[(text, numeric)]`` or ``[(text, numeric, column class)]``,
    ``rows`` = lists of trusted cell HTML. The column class (``date``, ``category``, ``note``) is on the
    header and on every cell of that column (style.css: a date stays on one line, a Note wraps by words).
    ``edits``: one ``(href, label)`` per row for the Edit link that ends the row (screen only).
    The total is the last body row (never a ``<tfoot>``: Chromium prints a tfoot on every page)."""
    def col(header):
        names = (["n"] if header[1] else []) + list(header[2:3])
        return f' class="{" ".join(names)}"' if names else ""

    head = "".join(f'<th scope="col"{col(c)}>{h(c[0])}</th>' for c in headers)
    tails, total_tail = [""] * len(rows), ""  # the Edit cell that ends each row, and an empty one in the total row
    if edits is not None:
        head += '<th scope="col" class="edit no-print"><span class="sr-only">Edit</span></th>'
        tails = [f'<td class="edit no-print"><a href="{h(href)}" aria-label="{h(label)}">Edit</a></td>'
                 for href, label in edits]
        total_tail = '<td class="edit no-print"></td>'
    body = "".join(
        "<tr data-row>" + "".join(f"<td{col(headers[i])}>{c}</td>" for i, c in enumerate(r)) + tail + "</tr>"
        for r, tail in zip(rows, tails, strict=True))
    span = len(headers) - 1
    body += (f'<tr class="total"><th scope="row" colspan="{span}">{h(total_label)}</th>'
             f'<td class="n">{money_cell(total, True)}</td>{total_tail}</tr>')
    return (f'<div class="table-wrap"><table class="list money {h(name)}"><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


# ---------------------------------------------------------------- /money

def _month_toolbar(year, month, today):
    """The month chips and the month picker. At 1900-01 there is no previous chip and at 9999-12 no next
    chip (``month_step`` gives ``None``): no link to a month the app refuses."""
    this = (year, month) == (today.year, today.month)
    current = ' aria-current="true"' if this else ""
    links = (month_chip("‹ {}", "/money", month_step(year, month, -1))
             + f'<a class="chip" href="/money"{current}>This month</a>'
             + month_chip("{} ›", "/money", month_step(year, month, 1)))
    picker = month_picker("/money", "money-month", month_text(year, month))
    return f'<div class="list-toolbar"><nav class="chips" aria-label="Money months">{links}</nav>{picker}</div>'


def _kpis(totals, n_offerings, n_expenses):
    balance_cls = " neg" if totals["balance"] < 0 else ""
    cells = (
        ("Offerings", money_data.format_vnd(totals["offerings"]), ui.plural(n_offerings, "Offering", "Offerings"), ""),
        ("Expenses", money_data.format_vnd(totals["expenses"]), ui.plural(n_expenses, "Expense", "Expenses"), ""),
        ("Balance", money_data.format_vnd(totals["balance"]), "Offerings minus Expenses", f" strong{balance_cls}"),
    )
    inner = "".join(
        f'<div class="kpi" data-row><span class="kpi-label">{h(label)}</span>'
        f'<span class="kpi-value num{cls}">{h(value)}</span><span class="kpi-sub">{h(sub)}</span></div>'
        for label, value, sub, cls in cells)
    return f'<section class="kpi-strip" data-panel="money-totals" aria-label="Totals">{inner}</section>'


def _offerings_panel(rows, total, scope):
    lines = [[num(ui.fmt_date(r["date"])), h(r["fund_name"]), giver_cell(r), money_cell(r["amount"])] for r in rows]
    edits = [(f"/money/offerings/{r['id']}/edit", f"Edit Offering on {ui.fmt_date(r['date'])}, {r['fund_name']}")
             for r in rows]
    body = (_table("offerings", [("Date", False, "date"), ("Fund", False), ("Giver", False), ("Amount", True)], lines,
                   "Total Offerings", total, edits)
            if rows else empty(f"No Offering recorded in {scope}."))
    link = card_link("Record Offering", "/money/offerings/new")
    return panel("offerings", "Offerings", body, meta=h(f"{ui.plural(len(rows), 'Offering', 'Offerings')} in {scope}"),
                 head_right=link)


def _expenses_panel(rows, total, scope):
    lines = [[num(ui.fmt_date(r["date"])), h(r["spending_category_name"]), vi(r["note"]), money_cell(r["amount"])]
             for r in rows]
    edits = [(f"/money/expenses/{r['id']}/edit",
              f"Edit Expense on {ui.fmt_date(r['date'])}, {r['spending_category_name']}") for r in rows]
    body = (_table("expenses", [("Date", False, "date"), ("Spending category", False, "category"),
                                ("Note", False, "note"), ("Amount", True)],
                   lines, "Total Expenses", total, edits)
            if rows else empty(f"No Expense recorded in {scope}."))
    link = card_link("Record Expense", "/money/expenses/new")
    return panel("expenses", "Expenses", body, meta=h(f"{ui.plural(len(rows), 'Expense', 'Expenses')} in {scope}"),
                 head_right=link)


def _statement_picker(conn, year, values=None, error=None):
    v = (values or {}).get
    persons = [("", "— Choose a Person —")] + [(p["id"], p["full_name"]) for p in people.list_persons(conn)]
    families = [("", "— or a Family —")] + [(f["id"], f["name"]) for f in people.list_families(conn)]
    inner = (
        ui.select_field("Person", "person_id", persons, selected=v("person_id", ""), id="st-person", lang="vi")
        + ui.select_field("Family", "family_id", families, selected=v("family_id", ""), id="st-family", lang="vi",
                          hint="Choose one Person or one Family.")
        + ui.field("Year", "year", v("year") or year, type="number", id="st-year", min="1900", max="9999",
                   step="1", required=True)
        + (f'<p class="error" role="alert">{h(error)}</p>' if error else "")
        + ui.button("Open Giving statement", "secondary")
    )
    # a form only: on paper (print.css hides .no-print) it would be a heading over nothing
    return panel("statement-picker", "Giving statement", ui.form("/money/statement", inner, method="get"),
                 meta="A yearly list of one Giver's Offerings, ready to print", cls="no-print")


def money_page(req):
    conn = req.conn
    today = _dt.date.today()
    year, month = month_of(req.query.get("month"), today)
    first = _dt.date(year, month, 1)
    last = first.replace(day=cal.month_days(year, month))
    scope = ui.fmt_month(year, month)
    totals = money_data.month_totals(conn, year, month)
    offerings = money_data.list_offerings(conn, first, last)
    expenses = money_data.list_expenses(conn, first, last)
    state = "Offerings above Expenses" if totals["balance"] >= 0 else "Expenses above Offerings"
    finding = h(f"{scope} · Balance {money_data.format_vnd(totals['balance'])} ({state})")
    body = (
        _month_toolbar(year, month, today)
        + _kpis(totals, len(offerings), len(expenses))
        + '<div class="grid money-month">'
        + f'<div class="span-6 stack">{_offerings_panel(offerings, totals["offerings"], scope)}</div>'
        + f'<div class="span-6 stack">{_expenses_panel(expenses, totals["expenses"], scope)}'
        + f"{_statement_picker(conn, year)}</div></div>"
    )
    actions = (ui.link_button("Record Expense", "/money/expenses/new")
               + ui.link_button("Record Offering", "/money/offerings/new", "primary"))
    return Response.html(ui.page("Money", body, "money", sub=finding, actions=actions))


# ---------------------------------------------------------------- Record, Edit and Delete an Offering or Expense
#
# /money/offerings/new and /money/expenses/new record a row. /money/<kind>/<id>/edit shows the same
# fields filled in (Note included) and saves the row in place; the Delete box comes last and asks
# once more on its own page before the row goes. A typo is not history: no old copy is kept.

def _amount_field(value, error):
    return ui.field("Amount", "amount", value, error=error, hint=AMOUNT_HINT, autocomplete="off", required=True,
                    spellcheck="false")


def _choices(conn, list_name, keep_id=None):
    """The shown items of a list as ``[(id, name)]``. The item ``keep_id`` stays in even when it is
    hidden, marked "(hidden)", so an old Offering or Expense keeps its Fund or Spending category."""
    return [(i["id"], i["name"] if i["active"] else f"{i['name']} (hidden)")
            for i in lists.get_list(conn, list_name, include_hidden=True)
            if i["active"] or i["id"] == keep_id]


def _giver_field(conn, selected, error):
    options = ['<option value="">— No Giver (no-name offering) —</option>']
    groups = (("People", "person", [(p["id"], p["full_name"]) for p in people.list_persons(conn)]),
              ("Families", "family", [(f["id"], f["name"]) for f in people.list_families(conn)]))
    for label, prefix, items in groups:
        opts = "".join(
            f'<option value="{prefix}-{rid}"{" selected" if f"{prefix}-{rid}" == selected else ""}>{h(name)}</option>'
            for rid, name in items)
        options.append(f'<optgroup label="{h(label)}">{opts}</optgroup>')
    described = "f-giver-hint" + (" f-giver-error" if error else "")
    invalid = ' aria-invalid="true"' if error else ""
    err = f'<p class="error" id="f-giver-error">{h(error)}</p>' if error else ""
    return ('<div class="field"><label for="f-giver">Giver</label>'
            f'<select class="input" id="f-giver" name="giver" lang="vi" aria-describedby="{described}"{invalid}>'
            f'{"".join(options)}</select>'
            '<p class="hint" id="f-giver-hint">A Person or a Family. With no Giver it is a no-name offering.</p>'
            f"{err}</div>")


def _giver_value(row):
    """The Giver field value of a saved Offering: ``person-5``, ``family-3`` or ``""``."""
    if row["giver_person_id"] is not None:
        return f"person-{row['giver_person_id']}"
    if row["giver_family_id"] is not None:
        return f"family-{row['giver_family_id']}"
    return ""


def _delete_box(action, what):
    """The last block of an edit page: Delete, in the negative colour. It asks once more first."""
    body = (ui.form(action, ui.button(f"Delete this {what}", "danger"))
            + '<p class="hint">You are asked once more before it goes. It cannot be undone.</p>')
    return panel("delete", "Delete", body, cls="narrow no-print")


def _edit_page(title, form_html, delete_html, sub, month, status):
    back = ui.link_button(f"Back to {ui.fmt_month(int(month[:4]), int(month[5:7]))}", ui.url("/money", month=month))
    body = f'<div class="stack"><section class="panel narrow">{form_html}</section>{delete_html}</div>'
    return Response.html(ui.page(title, body, "money", sub=h(sub), actions=back), status)


def _confirm_delete(what, row, details, action, back_href):
    """The one question before a Delete, naming the row: "Delete this Offering of 1.000.000 ₫ on 05/10/2026?".
    ``details`` is trusted HTML (the Fund and Giver, or the Spending category and Note)."""
    question = (f'Delete this {h(what)} of <strong class="num">{h(money_data.format_vnd(row["amount"]))}</strong> '
                f'on <span class="num">{h(ui.fmt_date(row["date"]))}</span>?')
    form = ui.form(action, ui.hidden("confirm", "yes") + ui.button("Yes, delete it", "danger"))
    body = (f'<section class="panel narrow" data-panel="confirm"><p class="lead">{question}</p>'
            f'<p class="hint">{details}</p>'
            '<p class="hint">The month totals and the Giving statement change at once. It cannot be undone.</p>'
            f'<div class="confirm-actions">{form}{ui.link_button("Cancel", back_href)}</div></section>')
    return Response.html(ui.page(f"Delete this {what}?", body, "money"))


def _missing(what):
    return not_found(what, "/money", "Go to Money")


def _saved(conn, what, amount, day, item_id, new):
    """Back to /money on the month of ``day`` with a short message naming the row."""
    name = lists.get_item(conn, item_id)["name"]
    figure, when = money_data.format_vnd(amount), ui.fmt_date(day)
    msg = f"{what} of {figure} recorded on {when} ({name})." if new else f"{what} saved: {figure} on {when} ({name})."
    return Response.redirect(ui.url("/money", month=day[:7], msg=msg))


def _deleted(what, row):
    msg = f"{what} of {money_data.format_vnd(row['amount'])} on {ui.fmt_date(row['date'])} deleted."
    return Response.redirect(ui.url("/money", month=row["date"][:7], msg=msg))


# ---- Offering

def _offering_form(req, values=None, error=None, status=200, row=None):
    """The Record Offering form; with ``row`` the Edit Offering form (the same fields filled in,
    then the Delete box). Both have the Note."""
    conn = req.conn
    v = (values or {}).get
    errors = field_errors(error, "offering", {"date": "Date", "amount": "Amount", "fund_id": "Fund", "giver": "Giver"})
    funds = _choices(conn, "fund", row["fund_id"] if row else None)
    inner = (
        ui.field("Date", "date", v("date") or today_text(), type="date", min=MIN_DATE, max=today_text(),
                 required=True, error=errors.get("date"))
        + _amount_field(v("amount", ""), errors.get("amount"))
        + ui.select_field("Fund", "fund_id", funds, selected=v("fund_id", funds[0][0] if funds else ""),
                          error=errors.get("fund_id"))
        + _giver_field(conn, v("giver", ""), errors.get("giver"))
        + ui.textarea_field("Note", "note", v("note", ""), lang="vi", rows=2,
                            hint="Optional. It is never printed on a Giving statement.")
        + form_error(errors) + ui.button("Save" if row else "Record Offering")
    )
    if row is None:
        body = f'<section class="panel narrow">{ui.form("/money/offerings/new", inner)}</section>'
        return Response.html(ui.page("Record Offering", body, "money"), status)
    oid = row["id"]
    sub = (f"Saved now: {money_data.format_vnd(row['amount'])} on {ui.fmt_date(row['date'])} · {row['fund_name']} · "
           f"{row['giver_name'] or NO_NAME} · Recorded {ui.fmt_datetime(row['created_at'])}")
    return _edit_page("Edit Offering", ui.form(f"/money/offerings/{oid}/edit", inner),
                      _delete_box(f"/money/offerings/{oid}/delete", "Offering"), sub, row["date"][:7], status)


def _offering_input(f):
    """Read the Offering form: ``(date, amount, person_id, family_id)``. The amount only via ``parse_amount``."""
    day = past_or_today(f.get("date"), "Date")
    amount = money_data.parse_amount(f.get("amount") or "")
    if not f.get("fund_id"):
        raise ValueError("Fund: choose a Fund.")
    person_id, family_id = parse_giver(f.get("giver"))
    return day, amount, person_id, family_id


def offering_new_page(req):
    return _offering_form(req)


def offering_new_post(req):
    f = req.form
    try:
        day, amount, person_id, family_id = _offering_input(f)
        money_data.add_offering(req.conn, day, amount, f["fund_id"], giver_person_id=person_id,
                                giver_family_id=family_id, note=f.get("note"))
    except ValueError as exc:
        return _offering_form(req, f, ("offering", str(exc)), 400)
    return _saved(req.conn, "Offering", amount, day, f["fund_id"], new=True)


def offering_edit_page(req):
    row = money_data.get_offering(req.conn, req.params["id"])
    if row is None:
        return _missing("Offering")
    values = {"date": row["date"], "amount": money_data.format_vnd(row["amount"]), "fund_id": row["fund_id"],
              "giver": _giver_value(row), "note": row["note"] or ""}
    return _offering_form(req, values, row=row)


def offering_edit_post(req):
    row = money_data.get_offering(req.conn, req.params["id"])
    if row is None:
        return _missing("Offering")
    f = req.form
    try:
        day, amount, person_id, family_id = _offering_input(f)
        money_data.update_offering(req.conn, row["id"], date=day, amount=amount, fund_id=f["fund_id"],
                                   giver_person_id=person_id, giver_family_id=family_id, note=f.get("note"))
    except ValueError as exc:
        return _offering_form(req, f, ("offering", str(exc)), 400, row=row)
    return _saved(req.conn, "Offering", amount, day, f["fund_id"], new=False)


def offering_delete_post(req):
    row = money_data.get_offering(req.conn, req.params["id"])
    if row is None:
        return _missing("Offering")
    if req.form.get("confirm") != "yes":
        details = f"Fund {h(row['fund_name'])} · Giver {vi(row['giver_name']) if row['giver_name'] else NO_NAME}"
        return _confirm_delete("Offering", row, details, f"/money/offerings/{row['id']}/delete",
                               f"/money/offerings/{row['id']}/edit")
    money_data.delete_offering(req.conn, row["id"])
    return _deleted("Offering", row)


# ---- Expense

def _expense_form(req, values=None, error=None, status=200, row=None):
    """The Record Expense form; with ``row`` the Edit Expense form (filled in, then the Delete box)."""
    conn = req.conn
    v = (values or {}).get
    errors = field_errors(error, "expense", {"date": "Date", "amount": "Amount",
                                             "spending_category_id": "Spending category"})
    cats = _choices(conn, "spending_category", row["spending_category_id"] if row else None)
    inner = (
        ui.field("Date", "date", v("date") or today_text(), type="date", min=MIN_DATE, max=today_text(),
                 required=True, error=errors.get("date"))
        + _amount_field(v("amount", ""), errors.get("amount"))
        + ui.select_field("Spending category", "spending_category_id", cats,
                          selected=v("spending_category_id", cats[0][0] if cats else ""),
                          error=errors.get("spending_category_id"))
        + ui.textarea_field("Note", "note", v("note", ""), lang="vi", rows=2, hint="What it was for. Optional.")
        + form_error(errors) + ui.button("Save" if row else "Record Expense")
    )
    if row is None:
        body = f'<section class="panel narrow">{ui.form("/money/expenses/new", inner)}</section>'
        return Response.html(ui.page("Record Expense", body, "money"), status)
    eid = row["id"]
    sub = (f"Saved now: {money_data.format_vnd(row['amount'])} on {ui.fmt_date(row['date'])} · "
           f"{row['spending_category_name']} · Recorded {ui.fmt_datetime(row['created_at'])}")
    return _edit_page("Edit Expense", ui.form(f"/money/expenses/{eid}/edit", inner),
                      _delete_box(f"/money/expenses/{eid}/delete", "Expense"), sub, row["date"][:7], status)


def _expense_input(f):
    """Read the Expense form: ``(date, amount)``. The amount only via ``parse_amount``."""
    day = past_or_today(f.get("date"), "Date")
    amount = money_data.parse_amount(f.get("amount") or "")
    if not f.get("spending_category_id"):
        raise ValueError("Spending category: choose a Spending category.")
    return day, amount


def expense_new_page(req):
    return _expense_form(req)


def expense_new_post(req):
    f = req.form
    try:
        day, amount = _expense_input(f)
        money_data.add_expense(req.conn, day, amount, f["spending_category_id"], note=f.get("note"))
    except ValueError as exc:
        return _expense_form(req, f, ("expense", str(exc)), 400)
    return _saved(req.conn, "Expense", amount, day, f["spending_category_id"], new=True)


def expense_edit_page(req):
    row = money_data.get_expense(req.conn, req.params["id"])
    if row is None:
        return _missing("Expense")
    values = {"date": row["date"], "amount": money_data.format_vnd(row["amount"]),
              "spending_category_id": row["spending_category_id"], "note": row["note"] or ""}
    return _expense_form(req, values, row=row)


def expense_edit_post(req):
    row = money_data.get_expense(req.conn, req.params["id"])
    if row is None:
        return _missing("Expense")
    f = req.form
    try:
        day, amount = _expense_input(f)
        money_data.update_expense(req.conn, row["id"], date=day, amount=amount,
                                  spending_category_id=f["spending_category_id"], note=f.get("note"))
    except ValueError as exc:
        return _expense_form(req, f, ("expense", str(exc)), 400, row=row)
    return _saved(req.conn, "Expense", amount, day, f["spending_category_id"], new=False)


def expense_delete_post(req):
    row = money_data.get_expense(req.conn, req.params["id"])
    if row is None:
        return _missing("Expense")
    if req.form.get("confirm") != "yes":
        details = f"Spending category {h(row['spending_category_name'])}"
        if row["note"]:
            details += f" · {vi(row['note'])}"
        return _confirm_delete("Expense", row, details, f"/money/expenses/{row['id']}/delete",
                               f"/money/expenses/{row['id']}/edit")
    money_data.delete_expense(req.conn, row["id"])
    return _deleted("Expense", row)


# ---------------------------------------------------------------- /money/statement

def _statement_sheet(st, today):
    kind_word = "Person" if st["kind"] == "person" else "Family"
    giver_href = f"/people/{st['giver_id']}" if st["kind"] == "person" else f"/families/{st['giver_id']}"
    rows = [[num(ui.fmt_date(r["date"])), h(r["fund"]), vi(r["given_by"]), money_cell(r["amount"])]
            for r in st["rows"]]
    count = ui.plural(len(rows), "Offering", "Offerings")
    if rows:
        table = _table("statement", [("Date", False, "date"), ("Fund", False), ("Given by", False), ("Amount", True)],
                       rows, f"Total ({count})", st["total"])
    else:
        table = empty(f"No Offering from this Giver in {st['year']}. Total {money_data.format_vnd(0)}.")
    family_note = ('<p class="hint">A Family statement also lists the Offerings of each Person on the dates '
                   "when that Person was in this Family.</p>") if st["kind"] == "family" else ""
    return (
        '<section class="panel statement" data-panel="statement" aria-labelledby="st-title">'
        '<header class="statement-head">'
        f'<p class="statement-church" lang="vi">{h(st["church_name"] or "")}</p>'
        f'<h2 id="st-title">Giving statement {st["year"]}</h2>'
        '<dl class="kv">'
        f'<div><dt>Giver</dt><dd><a href="{giver_href}">{vi(st["giver_name"])}</a> '
        f'<span class="faint">({kind_word})</span></dd></div>'
        f'<div><dt>Year</dt><dd class="num">01/01/{st["year"]} – 31/12/{st["year"]}</dd></div>'
        f'<div><dt>Printed</dt><dd class="num">{h(ui.fmt_date(today))}</dd></div>'
        "</dl></header>"
        f"{table}{family_note}</section>"
    )


def _year_form(st):
    giver = ui.hidden("person_id" if st["kind"] == "person" else "family_id", st["giver_id"])
    return ('<form class="year-form" action="/money/statement" method="get">'
            f'{giver}<label for="st-other-year">Year</label><div class="search-line">'
            f'<input class="input" id="st-other-year" name="year" type="number" min="1900" max="9999" step="1" '
            f'value="{st["year"]}" required><button class="btn secondary" type="submit">Show</button></div></form>')


def statement_page(req):
    conn = req.conn
    today = _dt.date.today()
    q = req.query
    person_id = (q.get("person_id") or "").strip() or None
    family_id = (q.get("family_id") or "").strip() or None
    year = (q.get("year") or "").strip() or str(today.year)
    if person_id is None and family_id is None:
        body = f'<div class="grid money-month"><div class="span-5 stack">{_statement_picker(conn, year, q)}</div></div>'
        return Response.html(ui.page("Giving statement", body, "money",
                                     sub="Choose a Person or a Family and a year."))
    try:
        st = money_data.giving_statement(conn, year, person_id=person_id, family_id=family_id)
    except ValueError as exc:
        body = (f'<div class="grid money-month"><div class="span-5 stack">'
                f"{_statement_picker(conn, year, q, str(exc))}</div></div>")
        return Response.html(ui.page("Giving statement", body, "money"), 400)
    sub = h(f"{st['giver_name']} · {st['year']} · {ui.plural(len(st['rows']), 'Offering', 'Offerings')} · "
            f"total {money_data.format_vnd(st['total'])}")
    actions = (_year_form(st)
               + '<button class="btn primary" type="button" data-print>Print</button>')
    body = _statement_sheet(st, today)
    return Response.html(ui.page("Giving statement", body, "money", sub=sub, actions=actions))


ROUTES = [
    ("GET", "/money", money_page),
    ("GET", "/money/offerings/new", offering_new_page),
    ("POST", "/money/offerings/new", offering_new_post),
    ("GET", "/money/offerings/<int:id>/edit", offering_edit_page),
    ("POST", "/money/offerings/<int:id>/edit", offering_edit_post),
    ("POST", "/money/offerings/<int:id>/delete", offering_delete_post),
    ("GET", "/money/expenses/new", expense_new_page),
    ("POST", "/money/expenses/new", expense_new_post),
    ("GET", "/money/expenses/<int:id>/edit", expense_edit_page),
    ("POST", "/money/expenses/<int:id>/edit", expense_edit_post),
    ("POST", "/money/expenses/<int:id>/delete", expense_delete_post),
    ("GET", "/money/statement", statement_page),
]
