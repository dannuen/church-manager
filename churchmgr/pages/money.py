"""Money pages (card C2): ``/money`` (one month: totals, Offerings, Expenses),
``/money/offerings/new``, ``/money/expenses/new`` and ``/money/statement`` (the printable
Giving statement of one Person or one Family for one year). ``/money/offerings/<id>/edit`` and
``/money/expenses/<id>/edit`` correct a row in place; ``.../delete`` removes it after one question.

Rules kept here:
- An amount is typed as text and read only by ``money.parse_amount`` (whole dong). It is shown
  only with ``money.format_vnd``, the same text in both languages. No float, no money maths in JS.
- An Offering with no Giver is shown as "no-name offering" (Ẩn danh).
- The Giving statement shows only what ``money.giving_statement`` returns: date, Fund, given by,
  amount, total. Never a Private note, never an Offering note.
- Words on screen come from the text table (``t``/``tn``, section ``money``). Fund, Spending category
  and Giver names are data: shown as stored. A refused value is a ``TextError``: its field is found on
  the English sentence and the sentence shows in the language of the page.
"""

import datetime as _dt

from .. import calendar as cal
from .. import i18n, lists, people, text, ui
from .. import money as money_data
from ..i18n import TEXT, TextError, t, tn
from ..server import Response
from ..ui import h, vi
from .calendar import FIRST_MONTH, LAST_MONTH, month_chip, month_step, month_text, parse_month
from .people import card_link, empty, family_link, field_errors, form_error, num, panel, person_link, today_text

NO_NAME = TEXT["en"]["money.no_name"]  # the English words of t("money.no_name"); old tests read them
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
        return text.to_id(rid, "money.giver"), None
    if kind == "family":
        return None, text.to_id(rid, "money.giver")
    raise TextError("money.err_giver")


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
    return f'<span class="faint">{h(t("money.no_name"))}</span>'


def _field_errors(error, form_key, labels):
    """Where a refused value shows: ``error`` is ``(form_key, exc)``, ``labels`` maps a field to a TEXT key.
    The field is found by :func:`pages.people.field_errors` on the English sentence (``str(exc)`` starts with
    the English label); the sentence shows in the language of the page (``i18n.error_text``)."""
    if not error or error[0] != form_key:
        return {}
    exc = error[1]
    english = {name: t(key, "en") for name, key in labels.items()}
    return {name: i18n.error_text(exc) for name in field_errors((form_key, str(exc)), form_key, english)}


def _past_or_today(value):
    """The date of a form as ``YYYY-MM-DD`` when it is a real date on or before today, else a ``TextError``
    whose English sentence starts with "Date" (so it shows next to the Date field).
    shortcut: the same rule as ``pages.people.past_or_today``, which takes a TEXT key only after the
    People card; use that one once both cards are on main."""
    day = text.check_date(value or "", "money.date")
    if day > today_text():
        raise TextError("money.err_after_today", today=ui.fmt_date(today_text()))
    return day


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
        edit = h(t("core.btn_edit"))
        head += f'<th scope="col" class="edit no-print"><span class="sr-only">{edit}</span></th>'
        tails = [f'<td class="edit no-print"><a href="{h(href)}" aria-label="{h(label)}">{edit}</a></td>'
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

def _month_picker(value):
    """The "Go to a month" form, limited to 1900-01 to 9999-12.
    shortcut: a copy of ``pages.calendar.month_picker`` with the words of this page, so this card needs no
    change in the Calendar card's file; use that one again once it takes its words from the text table."""
    return ('<form class="month-picker" action="/money" method="get">'
            f'<label for="money-month">{h(t("money.go_to_month"))}</label><div class="search-line">'
            f'<input class="input" id="money-month" name="month" type="month" value="{h(value)}" '
            f'min="{month_text(*FIRST_MONTH)}" max="{month_text(*LAST_MONTH)}" required>'
            f'<button class="btn secondary" type="submit">{h(t("money.show"))}</button></div></form>')


def _month_toolbar(year, month, today):
    """The month chips and the month picker. At 1900-01 there is no previous chip and at 9999-12 no next
    chip (``month_step`` gives ``None``): no link to a month the app refuses."""
    this = (year, month) == (today.year, today.month)
    current = ' aria-current="true"' if this else ""
    links = (month_chip("‹ {}", "/money", month_step(year, month, -1))
             + f'<a class="chip" href="/money"{current}>{h(t("money.this_month"))}</a>'
             + month_chip("{} ›", "/money", month_step(year, month, 1)))
    return (f'<div class="list-toolbar"><nav class="chips" aria-label="{h(t("money.months_label"))}">{links}</nav>'
            f"{_month_picker(month_text(year, month))}</div>")


def _kpis(totals, n_offerings, n_expenses):
    balance_cls = " neg" if totals["balance"] < 0 else ""
    cells = (
        (t("money.offerings"), money_data.format_vnd(totals["offerings"]), tn("money.offering_count", n_offerings),
         ""),
        (t("money.expenses"), money_data.format_vnd(totals["expenses"]), tn("money.expense_count", n_expenses), ""),
        (t("money.balance"), money_data.format_vnd(totals["balance"]), t("money.balance_sub"),
         f" strong{balance_cls}"),
    )
    inner = "".join(
        f'<div class="kpi" data-row><span class="kpi-label">{h(label)}</span>'
        f'<span class="kpi-value num{cls}">{h(value)}</span><span class="kpi-sub">{h(sub)}</span></div>'
        for label, value, sub, cls in cells)
    return f'<section class="kpi-strip" data-panel="money-totals" aria-label="{h(t("money.totals"))}">{inner}</section>'


def _offerings_panel(rows, total, scope):
    lines = [[num(ui.fmt_date(r["date"])), h(r["fund_name"]), giver_cell(r), money_cell(r["amount"])] for r in rows]
    edits = [(f"/money/offerings/{r['id']}/edit",
              t("money.edit_offering_on", date=ui.fmt_date(r["date"]), fund=r["fund_name"])) for r in rows]
    headers = [(t("money.date"), False, "date"), (t("money.fund"), False), (t("money.giver"), False),
               (t("money.amount"), True)]
    body = (_table("offerings", headers, lines, t("money.total_offerings"), total, edits)
            if rows else empty(t("money.no_offering_in", month=scope)))
    link = card_link(t("money.record_offering"), "/money/offerings/new")
    meta = t("money.count_in", count=tn("money.offering_count", len(rows)), month=scope)
    return panel("offerings", t("money.offerings"), body, meta=h(meta), head_right=link)


def _expenses_panel(rows, total, scope):
    lines = [[num(ui.fmt_date(r["date"])), h(r["spending_category_name"]), vi(r["note"]), money_cell(r["amount"])]
             for r in rows]
    edits = [(f"/money/expenses/{r['id']}/edit",
              t("money.edit_expense_on", date=ui.fmt_date(r["date"]), category=r["spending_category_name"]))
             for r in rows]
    headers = [(t("money.date"), False, "date"), (t("money.spending_category"), False, "category"),
               (t("money.note"), False, "note"), (t("money.amount"), True)]
    body = (_table("expenses", headers, lines, t("money.total_expenses"), total, edits)
            if rows else empty(t("money.no_expense_in", month=scope)))
    link = card_link(t("money.record_expense"), "/money/expenses/new")
    meta = t("money.count_in", count=tn("money.expense_count", len(rows)), month=scope)
    return panel("expenses", t("money.expenses"), body, meta=h(meta), head_right=link)


def _statement_picker(conn, year, values=None, error=None):
    """The Giving statement form. ``error`` is a sentence already in the language of the page."""
    v = (values or {}).get
    persons = [("", t("money.choose_person"))] + [(p["id"], p["full_name"]) for p in people.list_persons(conn)]
    families = [("", t("money.or_family"))] + [(f["id"], f["name"]) for f in people.list_families(conn)]
    inner = (
        ui.select_field(t("money.person"), "person_id", persons, selected=v("person_id", ""), id="st-person",
                        lang="vi")
        + ui.select_field(t("money.family"), "family_id", families, selected=v("family_id", ""), id="st-family",
                          lang="vi", hint=t("money.choose_hint"))
        + ui.field(t("money.year"), "year", v("year") or year, type="number", id="st-year", min="1900", max="9999",
                   step="1", required=True)
        + (f'<p class="error" role="alert">{h(error)}</p>' if error else "")
        + ui.button(t("money.open_statement"), "secondary")
    )
    # a form only: on paper (print.css hides .no-print) it would be a heading over nothing
    return panel("statement-picker", t("money.giving_statement"), ui.form("/money/statement", inner, method="get"),
                 meta=h(t("money.statement_meta")), cls="no-print")


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
    state = t("money.state_up") if totals["balance"] >= 0 else t("money.state_down")
    finding = h(t("money.finding", month=scope, balance=money_data.format_vnd(totals["balance"]), state=state))
    body = (
        _month_toolbar(year, month, today)
        + _kpis(totals, len(offerings), len(expenses))
        + '<div class="grid money-month">'
        + f'<div class="span-6 stack">{_offerings_panel(offerings, totals["offerings"], scope)}</div>'
        + f'<div class="span-6 stack">{_expenses_panel(expenses, totals["expenses"], scope)}'
        + f"{_statement_picker(conn, year)}</div></div>"
    )
    actions = (ui.link_button(t("money.year_report"), ui.url("/money/year", year=year))
               + ui.link_button(t("money.record_expense"), "/money/expenses/new")
               + ui.link_button(t("money.record_offering"), "/money/offerings/new", "primary"))
    return Response.html(ui.page(t("money.title"), body, "money", sub=finding, actions=actions))


# ---------------------------------------------------------------- Record, Edit and Delete an Offering or Expense
#
# /money/offerings/new and /money/expenses/new record a row. /money/<kind>/<id>/edit shows the same
# fields filled in (Note included) and saves the row in place; the Delete box comes last and asks
# once more on its own page before the row goes. A typo is not history: no old copy is kept.
# ``kind`` below is "offering" or "expense": it picks the TEXT keys (money.<kind>, money.delete_<kind>, ...).

def _amount_field(value, error):
    return ui.field(t("money.amount"), "amount", value, error=error, hint=t("money.amount_hint"), autocomplete="off",
                    required=True, spellcheck="false")


def _choices(conn, list_name, keep_id=None):
    """The shown items of a list as ``[(id, name)]``. The item ``keep_id`` stays in even when it is
    hidden, marked "(hidden)", so an old Offering or Expense keeps its Fund or Spending category."""
    return [(i["id"], i["name"] if i["active"] else t("money.hidden_item", name=i["name"]))
            for i in lists.get_list(conn, list_name, include_hidden=True)
            if i["active"] or i["id"] == keep_id]


def _giver_field(conn, selected, error):
    options = [f'<option value="">{h(t("money.no_giver"))}</option>']
    groups = ((t("money.group_people"), "person", [(p["id"], p["full_name"]) for p in people.list_persons(conn)]),
              (t("money.group_families"), "family", [(f["id"], f["name"]) for f in people.list_families(conn)]))
    for label, prefix, items in groups:
        opts = "".join(
            f'<option value="{prefix}-{rid}"{" selected" if f"{prefix}-{rid}" == selected else ""}>{h(name)}</option>'
            for rid, name in items)
        options.append(f'<optgroup label="{h(label)}">{opts}</optgroup>')
    described = "f-giver-hint" + (" f-giver-error" if error else "")
    invalid = ' aria-invalid="true"' if error else ""
    err = f'<p class="error" id="f-giver-error">{h(error)}</p>' if error else ""
    return (f'<div class="field"><label for="f-giver">{h(t("money.giver"))}</label>'
            f'<select class="input" id="f-giver" name="giver" lang="vi" aria-describedby="{described}"{invalid}>'
            f'{"".join(options)}</select>'
            f'<p class="hint" id="f-giver-hint">{h(t("money.giver_hint"))}</p>'
            f"{err}</div>")


def _giver_value(row):
    """The Giver field value of a saved Offering: ``person-5``, ``family-3`` or ``""``."""
    if row["giver_person_id"] is not None:
        return f"person-{row['giver_person_id']}"
    if row["giver_family_id"] is not None:
        return f"family-{row['giver_family_id']}"
    return ""


def _giver_html(name):
    """The Giver of a saved Offering in a sentence: the name (``lang="vi"``) or the no-name offering words."""
    return vi(name) if name else h(t("money.no_name"))


def _delete_box(action, kind):
    """The last block of an edit page: Delete, in the negative colour. It asks once more first."""
    body = (ui.form(action, ui.button(t(f"money.delete_{kind}"), "danger"))
            + f'<p class="hint">{h(t("money.delete_hint"))}</p>')
    return panel("delete", t("core.btn_delete"), body, cls="narrow no-print")


def _edit_page(title, form_html, delete_html, sub, month, status):
    """An Edit page. ``sub`` is trusted HTML (escape its values)."""
    back = ui.link_button(t("money.back_to", month=ui.fmt_month(int(month[:4]), int(month[5:7]))),
                          ui.url("/money", month=month))
    body = f'<div class="stack"><section class="panel narrow">{form_html}</section>{delete_html}</div>'
    return Response.html(ui.page(title, body, "money", sub=sub, actions=back), status)


def _confirm_delete(kind, row, details, action, back_href):
    """The one question before a Delete, naming the row: "Delete this Offering of 1.000.000 ₫ on 05/10/2026?".
    ``details`` is trusted HTML (the Fund and Giver, or the Spending category and Note)."""
    question = ui.t_html(f"money.confirm_{kind}",
                         amount=f'<strong class="num">{h(money_data.format_vnd(row["amount"]))}</strong>',
                         date=f'<span class="num">{h(ui.fmt_date(row["date"]))}</span>')
    form = ui.form(action, ui.hidden("confirm", "yes") + ui.button(t("money.yes_delete"), "danger"))
    body = (f'<section class="panel narrow" data-panel="confirm"><p class="lead">{question}</p>'
            f'<p class="hint">{details}</p>'
            f'<p class="hint">{h(t("money.confirm_hint"))}</p>'
            f'<div class="confirm-actions">{form}{ui.link_button(t("core.btn_cancel"), back_href)}</div></section>')
    return Response.html(ui.page(t(f"money.confirm_{kind}_title"), body, "money"))


def _missing(kind):
    """The 404 page of an Offering or Expense that is not there.
    shortcut: the page of ``pages.people.not_found``, which takes TEXT keys only after the People card."""
    what = t(f"money.{kind}")
    body = (f'<p class="lead">{h(t("money.not_found_text", what=what))}</p>'
            f'<p><a href="/money">{h(t("money.go_money"))}</a></p>')
    return Response.html(ui.page(t("money.not_found_title", what=what), body), 404)


def _saved(conn, kind, amount, day, item_id, new):
    """Back to /money on the month of ``day`` with a short message naming the row."""
    name = lists.get_item(conn, item_id)["name"]
    key = f"money.{kind}_recorded" if new else f"money.{kind}_saved"
    msg = t(key, amount=money_data.format_vnd(amount), date=ui.fmt_date(day), name=name)
    return Response.redirect(ui.url("/money", month=day[:7], msg=msg))


def _deleted(kind, row):
    msg = t(f"money.{kind}_deleted", amount=money_data.format_vnd(row["amount"]), date=ui.fmt_date(row["date"]))
    return Response.redirect(ui.url("/money", month=row["date"][:7], msg=msg))


# ---- Offering

_OFFERING_LABELS = {"date": "money.date", "amount": "money.amount", "fund_id": "money.fund", "giver": "money.giver"}


def _offering_form(req, values=None, error=None, status=200, row=None):
    """The Record Offering form; with ``row`` the Edit Offering form (the same fields filled in,
    then the Delete box). Both have the Note. ``error`` is ``("offering", exc)``."""
    conn = req.conn
    v = (values or {}).get
    errors = _field_errors(error, "offering", _OFFERING_LABELS)
    funds = _choices(conn, "fund", row["fund_id"] if row else None)
    inner = (
        ui.field(t("money.date"), "date", v("date") or today_text(), type="date", min=MIN_DATE, max=today_text(),
                 required=True, error=errors.get("date"))
        + _amount_field(v("amount", ""), errors.get("amount"))
        + ui.select_field(t("money.fund"), "fund_id", funds, selected=v("fund_id", funds[0][0] if funds else ""),
                          error=errors.get("fund_id"))
        + _giver_field(conn, v("giver", ""), errors.get("giver"))
        + ui.textarea_field(t("money.note"), "note", v("note", ""), lang="vi", rows=2,
                            hint=t("money.offering_note_hint"))
        + form_error(errors) + ui.button(t("core.btn_save") if row else t("money.record_offering"))
    )
    if row is None:
        body = f'<section class="panel narrow">{ui.form("/money/offerings/new", inner)}</section>'
        return Response.html(ui.page(t("money.record_offering"), body, "money"), status)
    oid = row["id"]
    sub = ui.t_html("money.offering_now", amount=h(money_data.format_vnd(row["amount"])),
                    date=h(ui.fmt_date(row["date"])), fund=h(row["fund_name"]), giver=_giver_html(row["giver_name"]),
                    recorded=h(ui.fmt_datetime(row["created_at"])))
    return _edit_page(t("money.edit_offering"), ui.form(f"/money/offerings/{oid}/edit", inner),
                      _delete_box(f"/money/offerings/{oid}/delete", "offering"), sub, row["date"][:7], status)


def _offering_input(f):
    """Read the Offering form: ``(date, amount, person_id, family_id)``. The amount only via ``parse_amount``."""
    day = _past_or_today(f.get("date"))
    amount = money_data.parse_amount(f.get("amount") or "")
    if not f.get("fund_id"):
        raise TextError("money.err_choose_fund")
    person_id, family_id = parse_giver(f.get("giver"))
    return day, amount, person_id, family_id


def add_offering_from_form(conn, form):
    """Record an Offering from the Record Offering form: the one place of its rules, for this page and
    the Hermes door. ``form`` has ``.get``. Returns the Offering id; a refused value raises ``ValueError``
    (a ``TextError``: ``str()`` is the English sentence, the page shows it in its own language)."""
    day, amount, person_id, family_id = _offering_input(form)
    return money_data.add_offering(conn, day, amount, form["fund_id"], giver_person_id=person_id,
                                   giver_family_id=family_id, note=form.get("note"))


def offering_new_page(req):
    return _offering_form(req)


def offering_new_post(req):
    f = req.form
    try:
        oid = add_offering_from_form(req.conn, f)
    except ValueError as exc:
        return _offering_form(req, f, ("offering", exc), 400)
    row = money_data.get_offering(req.conn, oid)
    return _saved(req.conn, "offering", row["amount"], row["date"], row["fund_id"], new=True)


def offering_edit_page(req):
    row = money_data.get_offering(req.conn, req.params["id"])
    if row is None:
        return _missing("offering")
    values = {"date": row["date"], "amount": money_data.format_vnd(row["amount"]), "fund_id": row["fund_id"],
              "giver": _giver_value(row), "note": row["note"] or ""}
    return _offering_form(req, values, row=row)


def offering_edit_post(req):
    row = money_data.get_offering(req.conn, req.params["id"])
    if row is None:
        return _missing("offering")
    f = req.form
    try:
        day, amount, person_id, family_id = _offering_input(f)
        money_data.update_offering(req.conn, row["id"], date=day, amount=amount, fund_id=f["fund_id"],
                                   giver_person_id=person_id, giver_family_id=family_id, note=f.get("note"))
    except ValueError as exc:
        return _offering_form(req, f, ("offering", exc), 400, row=row)
    return _saved(req.conn, "offering", amount, day, f["fund_id"], new=False)


def offering_delete_post(req):
    row = money_data.get_offering(req.conn, req.params["id"])
    if row is None:
        return _missing("offering")
    if req.form.get("confirm") != "yes":
        details = ui.t_html("money.offering_detail", fund=h(row["fund_name"]), giver=_giver_html(row["giver_name"]))
        return _confirm_delete("offering", row, details, f"/money/offerings/{row['id']}/delete",
                               f"/money/offerings/{row['id']}/edit")
    money_data.delete_offering(req.conn, row["id"])
    return _deleted("offering", row)


# ---- Expense

_EXPENSE_LABELS = {"date": "money.date", "amount": "money.amount", "spending_category_id": "money.spending_category"}


def _expense_form(req, values=None, error=None, status=200, row=None):
    """The Record Expense form; with ``row`` the Edit Expense form (filled in, then the Delete box).
    ``error`` is ``("expense", exc)``."""
    conn = req.conn
    v = (values or {}).get
    errors = _field_errors(error, "expense", _EXPENSE_LABELS)
    cats = _choices(conn, "spending_category", row["spending_category_id"] if row else None)
    inner = (
        ui.field(t("money.date"), "date", v("date") or today_text(), type="date", min=MIN_DATE, max=today_text(),
                 required=True, error=errors.get("date"))
        + _amount_field(v("amount", ""), errors.get("amount"))
        + ui.select_field(t("money.spending_category"), "spending_category_id", cats,
                          selected=v("spending_category_id", cats[0][0] if cats else ""),
                          error=errors.get("spending_category_id"))
        + ui.textarea_field(t("money.note"), "note", v("note", ""), lang="vi", rows=2,
                            hint=t("money.expense_note_hint"))
        + form_error(errors) + ui.button(t("core.btn_save") if row else t("money.record_expense"))
    )
    if row is None:
        body = f'<section class="panel narrow">{ui.form("/money/expenses/new", inner)}</section>'
        return Response.html(ui.page(t("money.record_expense"), body, "money"), status)
    eid = row["id"]
    sub = ui.t_html("money.expense_now", amount=h(money_data.format_vnd(row["amount"])),
                    date=h(ui.fmt_date(row["date"])), category=h(row["spending_category_name"]),
                    recorded=h(ui.fmt_datetime(row["created_at"])))
    return _edit_page(t("money.edit_expense"), ui.form(f"/money/expenses/{eid}/edit", inner),
                      _delete_box(f"/money/expenses/{eid}/delete", "expense"), sub, row["date"][:7], status)


def _expense_input(f):
    """Read the Expense form: ``(date, amount)``. The amount only via ``parse_amount``."""
    day = _past_or_today(f.get("date"))
    amount = money_data.parse_amount(f.get("amount") or "")
    if not f.get("spending_category_id"):
        raise TextError("money.err_choose_category")
    return day, amount


def add_expense_from_form(conn, form):
    """Record an Expense from the Record Expense form: the one place of its rules, for this page and
    the Hermes door. ``form`` has ``.get``. Returns the Expense id; a refused value raises ``ValueError``
    (a ``TextError``: ``str()`` is the English sentence, the page shows it in its own language)."""
    day, amount = _expense_input(form)
    return money_data.add_expense(conn, day, amount, form["spending_category_id"], note=form.get("note"))


def expense_new_page(req):
    return _expense_form(req)


def expense_new_post(req):
    f = req.form
    try:
        eid = add_expense_from_form(req.conn, f)
    except ValueError as exc:
        return _expense_form(req, f, ("expense", exc), 400)
    row = money_data.get_expense(req.conn, eid)
    return _saved(req.conn, "expense", row["amount"], row["date"], row["spending_category_id"], new=True)


def expense_edit_page(req):
    row = money_data.get_expense(req.conn, req.params["id"])
    if row is None:
        return _missing("expense")
    values = {"date": row["date"], "amount": money_data.format_vnd(row["amount"]),
              "spending_category_id": row["spending_category_id"], "note": row["note"] or ""}
    return _expense_form(req, values, row=row)


def expense_edit_post(req):
    row = money_data.get_expense(req.conn, req.params["id"])
    if row is None:
        return _missing("expense")
    f = req.form
    try:
        day, amount = _expense_input(f)
        money_data.update_expense(req.conn, row["id"], date=day, amount=amount,
                                  spending_category_id=f["spending_category_id"], note=f.get("note"))
    except ValueError as exc:
        return _expense_form(req, f, ("expense", exc), 400, row=row)
    return _saved(req.conn, "expense", amount, day, f["spending_category_id"], new=False)


def expense_delete_post(req):
    row = money_data.get_expense(req.conn, req.params["id"])
    if row is None:
        return _missing("expense")
    if req.form.get("confirm") != "yes":
        details = ui.t_html("money.expense_detail", category=h(row["spending_category_name"]))
        if row["note"]:
            details += f" · {vi(row['note'])}"
        return _confirm_delete("expense", row, details, f"/money/expenses/{row['id']}/delete",
                               f"/money/expenses/{row['id']}/edit")
    money_data.delete_expense(req.conn, row["id"])
    return _deleted("expense", row)


# ---------------------------------------------------------------- /money/statement

def _statement_sheet(st, today):
    """The sheet that prints: church, title, Giver, year, the date printed, the rows and the total.
    Every word is from the text table; names and Funds are data."""
    kind_word = t(f"money.{st['kind']}")
    giver_href = f"/people/{st['giver_id']}" if st["kind"] == "person" else f"/families/{st['giver_id']}"
    rows = [[num(ui.fmt_date(r["date"])), h(r["fund"]), vi(r["given_by"]), money_cell(r["amount"])]
            for r in st["rows"]]
    if rows:
        headers = [(t("money.date"), False, "date"), (t("money.fund"), False), (t("money.given_by"), False),
                   (t("money.amount"), True)]
        count = tn("money.offering_count", len(rows))
        table = _table("statement", headers, rows, t("money.total_count", count=count), st["total"])
    else:
        table = empty(t("money.statement_empty", year=st["year"], total=money_data.format_vnd(0)))
    family_note = f'<p class="hint">{h(t("money.family_note"))}</p>' if st["kind"] == "family" else ""
    return (
        '<section class="panel statement" data-panel="statement" aria-labelledby="st-title">'
        '<header class="statement-head">'
        f'<p class="statement-church" lang="vi">{h(st["church_name"] or "")}</p>'
        f'<h2 id="st-title">{h(t("money.statement_title", year=st["year"]))}</h2>'
        '<dl class="kv">'
        f'<div><dt>{h(t("money.giver"))}</dt><dd><a href="{giver_href}">{vi(st["giver_name"])}</a> '
        f'<span class="faint">({h(kind_word)})</span></dd></div>'
        f'<div><dt>{h(t("money.year"))}</dt><dd class="num">01/01/{st["year"]} – 31/12/{st["year"]}</dd></div>'
        f'<div><dt>{h(t("money.printed"))}</dt><dd class="num">{h(ui.fmt_date(today))}</dd></div>'
        "</dl></header>"
        f"{table}{family_note}</section>"
    )


def _year_form(st):
    giver = ui.hidden("person_id" if st["kind"] == "person" else "family_id", st["giver_id"])
    return ('<form class="year-form" action="/money/statement" method="get">'
            f'{giver}<label for="st-other-year">{h(t("money.year"))}</label><div class="search-line">'
            f'<input class="input" id="st-other-year" name="year" type="number" min="1900" max="9999" step="1" '
            f'value="{st["year"]}" required><button class="btn secondary" type="submit">{h(t("money.show"))}</button>'
            "</div></form>")


def statement_page(req):
    conn = req.conn
    today = _dt.date.today()
    q = req.query
    person_id = (q.get("person_id") or "").strip() or None
    family_id = (q.get("family_id") or "").strip() or None
    year = (q.get("year") or "").strip() or str(today.year)
    if person_id is None and family_id is None:
        body = f'<div class="grid money-month"><div class="span-5 stack">{_statement_picker(conn, year, q)}</div></div>'
        return Response.html(ui.page(t("money.giving_statement"), body, "money",
                                     sub=h(t("money.statement_choose"))))
    try:
        st = money_data.giving_statement(conn, year, person_id=person_id, family_id=family_id)
    except ValueError as exc:
        body = (f'<div class="grid money-month"><div class="span-5 stack">'
                f"{_statement_picker(conn, year, q, i18n.error_text(exc))}</div></div>")
        return Response.html(ui.page(t("money.giving_statement"), body, "money"), 400)
    sub = ui.t_html("money.statement_sub", name=vi(st["giver_name"]), year=h(st["year"]),
                    count=h(tn("money.offering_count", len(st["rows"]))), total=h(money_data.format_vnd(st["total"])))
    actions = (_year_form(st)
               + f'<button class="btn primary" type="button" data-print>{h(t("core.btn_print"))}</button>')
    body = _statement_sheet(st, today)
    return Response.html(ui.page(t("money.giving_statement"), body, "money", sub=sub, actions=actions))


# ---------------------------------------------------------------- /money/year

def _signed(n):
    return ("+" if n > 0 else "") + money_data.format_vnd(n)


def _chart(report):
    """Bars of Offerings and Expenses per month, inline SVG. Heights are whole pixels (integer maths);
    fills are colours, so they print (a CSS background would not)."""
    top = max([m[k] for m in report["months"] for k in ("offerings", "expenses")] + [1])
    bars = ""
    for m in report["months"]:
        x = (m["month"] - 1) * 60 + 8
        for k, dx, fill in (("offerings", 0, "#2f6f4f"), ("expenses", 22, "#999")):
            height = m[k] * 150 // top
            bars += f'<rect x="{x + dx}" y="{160 - height}" width="20" height="{height}" fill="{fill}"/>'
        bars += f'<text x="{x + 20}" y="178" text-anchor="middle" font-size="11">{m["month"]}</text>'
    label = t("money.year_chart", year=report["year"])
    legend = (f'<p class="hint"><span style="color:#2f6f4f">\u25a0</span> {h(t("money.offerings"))} \u00b7 '
              f'<span style="color:#999">\u25a0</span> {h(t("money.expenses"))}</p>')
    return (f'<svg class="year-chart" viewBox="0 0 720 184" role="img" aria-label="{h(label)}" width="100%">{bars}</svg>'
            + legend)


def _months_table(report):
    rows = "".join(
        f'<tr data-row><td>{h(ui.fmt_month(report["year"], m["month"]))}</td><td class="n">{money_cell(m["offerings"])}</td>'
        f'<td class="n">{money_cell(m["expenses"])}</td><td class="n">{money_cell(m["balance"])}</td></tr>'
        for m in report["months"])
    tot = report["total"]
    rows += (f'<tr class="total"><th scope="row">{h(t("money.year"))} {report["year"]}</th>'
             f'<td class="n">{money_cell(tot["offerings"], True)}</td><td class="n">{money_cell(tot["expenses"], True)}</td>'
             f'<td class="n">{money_cell(tot["balance"], True)}</td></tr>')
    head = "".join(f'<th scope="col"{c}>{h(w)}</th>' for w, c in (
        (t("money.month"), ""), (t("money.offerings"), ' class="n"'), (t("money.expenses"), ' class="n"'),
        (t("money.balance"), ' class="n"')))
    return (f'<div class="table-wrap"><table class="list money year-months"><thead><tr>{head}</tr></thead>'
            f"<tbody>{rows}</tbody></table></div>")


def _compare_table(report):
    before = report["before"]
    if before is None:
        return empty(t("money.compare_none", year=report["year"] - 1))
    head = "".join(f'<th scope="col"{c}>{h(w)}</th>' for w, c in (
        ("", ""), (report["year"], ' class="n"'), (report["year"] - 1, ' class="n"'),
        (t("money.compare_change"), ' class="n"'), (t("money.compare_percent"), ' class="n"')))
    rows = ""
    for key, label in (("offerings", "money.offerings"), ("expenses", "money.expenses"), ("balance", "money.balance")):
        now, then = report["total"][key], before[key]
        pct = money_data.percent_change(now, then)
        pct_text = "\u2013" if pct is None else ("+" if pct > 0 else "") + f"{pct}%"
        rows += (f'<tr data-row><th scope="row">{h(t(label))}</th><td class="n">{money_cell(now)}</td>'
                 f'<td class="n">{money_cell(then)}</td><td class="n">{h(_signed(now - then))}</td>'
                 f'<td class="n">{h(pct_text)}</td></tr>')
    return (f'<div class="table-wrap"><table class="list money year-compare"><thead><tr>{head}</tr></thead>'
            f"<tbody>{rows}</tbody></table></div>")


def year_page(req):
    today = _dt.date.today()
    raw = (req.query.get("year") or "").strip() or str(today.year)
    try:
        report = money_data.year_report(req.conn, raw)
    except ValueError as exc:
        body = f'<p class="error" role="alert">{h(i18n.error_text(exc))}</p>'
        return Response.html(ui.page(t("money.year_report"), body, "money"), 400)
    year, tot = report["year"], report["total"]
    funds = _table("year-funds", [(t("money.fund"), False), (t("money.amount"), True)],
                   [[h(n), money_cell(a)] for n, a in report["funds"]], t("money.total_offerings"), tot["offerings"])
    cats = _table("year-categories", [(t("money.spending_category"), False), (t("money.amount"), True)],
                  [[h(n), money_cell(a)] for n, a in report["categories"]], t("money.total_expenses"), tot["expenses"])
    form = ('<form class="year-form" action="/money/year" method="get">'
            f'<label for="yr-year">{h(t("money.year"))}</label><div class="search-line">'
            f'<input class="input" id="yr-year" name="year" type="number" min="1900" max="9999" step="1" '
            f'value="{year}" required><button class="btn secondary" type="submit">{h(t("money.show"))}</button></div></form>')
    actions = form + f'<button class="btn primary" type="button" data-print>{h(t("core.btn_print"))}</button>'
    body = (
        '<section class="panel statement year-report" data-panel="year-report" aria-labelledby="yr-title">'
        '<header class="statement-head">'
        f'<p class="statement-church" lang="vi">{h(report["church_name"] or "")}</p>'
        f'<h2 id="yr-title">{h(t("money.year_report_title", year=year))}</h2>'
        '<dl class="kv">'
        f'<div><dt>{h(t("money.printed"))}</dt><dd class="num">{h(ui.fmt_date(today))}</dd></div>'
        "</dl></header>"
        f"{_chart(report)}{_months_table(report)}"
        f'<h3>{h(t("money.by_fund"))}</h3>{funds}'
        f'<h3>{h(t("money.by_category"))}</h3>{cats}'
        f'<h3>{h(t("money.compare_title", year=year - 1))}</h3>{_compare_table(report)}'
        "</section>")
    return Response.html(ui.page(t("money.year_report"), body, "money", actions=actions))


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
    ("GET", "/money/year", year_page),
]
