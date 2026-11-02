"""Lists (card C3): ``/lists`` has one section per editable list (Recipient, Purpose, Fund, Spending
category, Ministry, Status). Each item can be renamed, hidden or shown; new items are added at the end.

Rules kept here:
- List items are never deleted (the database refuses it too). Hide an item instead.
- A hidden item is left out of every new-entry dropdown (``lists.get_list`` gives shown items only),
  and old rows that use it keep showing its name.
- The last shown item of a list cannot be hidden: new entries always need one to choose.
- Words on screen come from the text table (section ``lists``). The items are data: shown as stored,
  never translated (the default ones too).
"""

from .. import i18n, lists, ui
from ..i18n import TextError, t, tn
from ..schema import LIST_NAMES
from ..server import Response
from ..ui import h
from .people import empty, form_error, panel

# list name -> TEXT keys of (section title, one line from the glossary, how many rows use an item)
LIST_INFO = {
    "recipient": ("lists.recipient", "lists.recipient_line", "lists.uses_sent"),
    "purpose": ("lists.purpose", "lists.purpose_line", "lists.uses_sent"),
    "fund": ("lists.fund", "lists.fund_line", "lists.uses_offering"),
    "spending_category": ("lists.spending_category", "lists.spending_category_line", "lists.uses_expense"),
    "ministry": ("lists.ministry", "lists.ministry_line", "lists.uses_serving"),
    "status": ("lists.status", "lists.status_line", "lists.uses_now"),
}
LIST_ORDER = tuple(LIST_INFO)
assert set(LIST_ORDER) == set(LIST_NAMES), "every editable list has a section"
assert all(LIST_INFO[n][0] == lists.LABEL_KEYS[n] for n in LIST_ORDER), "one glossary word per list"

# How many rows use each item: (item id, count). Status and Ministry count the People now.
_USAGE_SQL = {
    "recipient": "SELECT recipient_id, COUNT(*) FROM sent_document GROUP BY recipient_id",
    "purpose": "SELECT purpose_id, COUNT(*) FROM sent_document GROUP BY purpose_id",
    "fund": "SELECT fund_id, COUNT(*) FROM offering GROUP BY fund_id",
    "spending_category": "SELECT spending_category_id, COUNT(*) FROM expense GROUP BY spending_category_id",
    "ministry": ("SELECT ministry_id, COUNT(DISTINCT person_id) FROM ministry_link WHERE end_date IS NULL "
                 "GROUP BY ministry_id"),
    "status": "SELECT status_id, COUNT(*) FROM person_status WHERE end_date IS NULL GROUP BY status_id",
}


def anchor(list_name):
    """``spending_category`` -> ``list-spending-category`` (the section id)."""
    return "list-" + list_name.replace("_", "-")


def check_can_hide(items, item_id):
    """Raise ``ValueError`` (a ``TextError``) when ``item_id`` is the last shown item of its list."""
    shown = [i for i in items if i["active"]]
    if len(shown) == 1 and shown[0]["id"] == item_id:
        raise TextError("lists.err_keep_one", title=LIST_INFO[shown[0]["list_name"]][0])


# ---------------------------------------------------------------- /lists

def _item_row(item, used, uses_key, error):
    iid = int(item["id"])
    hidden = not item["active"]
    tag = f' <span class="tag">{h(t("lists.hidden_tag"))}</span>' if hidden else ""
    use_text = tn(uses_key, used)  # a real zero prints 0
    toggle = "show" if hidden else "hide"
    toggle_label = t(f"lists.{toggle}_aria", name=item["name"])
    toggle_form = (f'<form class="row-form" action="/lists/items/{iid}/{toggle}" method="post">'
                   f'<button class="link-btn" type="submit" aria-label="{h(toggle_label)}">'
                   f'{h(t(f"lists.{toggle}"))}</button></form>')
    rename_error = error[1] if error and error[0] == f"rename-{iid}" else None
    rename = (f'<details class="rename"{" open" if rename_error else ""}><summary>{h(t("lists.rename"))}</summary>'
              + ui.form(f"/lists/items/{iid}/rename",
                        '<div class="inline-add">'
                        + ui.field(t("lists.new_name"), "name", item["name"], id=f"rename-{iid}", required=True,
                                   autocomplete="off", lang="vi", error=rename_error)
                        + ui.button(t("core.btn_save"), "secondary") + "</div>")
              + "</details>")
    return (f'<li class="row list-item{" is-hidden" if hidden else ""}" data-row>'
            f'<span class="what" lang="vi">{h(item["name"])}{tag}</span>'
            f'<span class="side num">{h(use_text)}</span>{toggle_form}{rename}</li>')


def _section(conn, list_name, error):
    title_key, line_key, uses_key = LIST_INFO[list_name]
    title = t(title_key)
    items = lists.get_list(conn, list_name, include_hidden=True)
    used = dict(conn.execute(_USAGE_SQL[list_name]).fetchall())
    rows = "".join(_item_row(i, used.get(i["id"], 0), uses_key, error) for i in items)
    body = f'<ul class="rows">{rows}</ul>' if items else empty(t("lists.empty", title=title))
    add_error = error[1] if error and error[0] == f"add-{list_name}" else None
    add = ui.form(f"/lists/{list_name}/add",
                  '<div class="inline-add">'
                  + ui.field(t("lists.new_item", title=title), "name", "", id=f"add-{anchor(list_name)}", required=True,
                             autocomplete="off", lang="vi", error=add_error)
                  + ui.button(t("core.btn_add"), "secondary") + "</div>")
    shown = sum(1 for i in items if i["active"])
    line = t(line_key)
    meta = h(t("lists.meta", line=line, shown=shown) if shown == len(items)
             else t("lists.meta_hidden", line=line, shown=shown, hidden=len(items) - shown))
    return (f'<div id="{anchor(list_name)}">'
            + panel(anchor(list_name), title, body + f'<div class="add-form">{add}</div>', meta=meta)
            + "</div>")


def _view(req, error=None, status=200):
    """The page. ``error`` is ``(form key, exception)`` of a refused change, or ``None``: the sentence
    shows in the language of the page."""
    conn = req.conn
    if error is not None:
        error = (error[0], i18n.error_text(error[1]))
    # Two columns that stack on their own (no shared row heights): Recipient, Fund, Ministry on the
    # left; Purpose, Spending category, Status on the right. Read across, the order is the card's.
    left = "".join(_section(conn, name, error) for name in LIST_ORDER[0::2])
    right = "".join(_section(conn, name, error) for name in LIST_ORDER[1::2])
    sections = f'<div class="span-6 stack">{left}</div><div class="span-6 stack">{right}</div>'
    general = form_error({"": error[1]}) if error and error[0] == "page" else ""
    sub = h(t("lists.sub"))
    return Response.html(ui.page(t("lists.title"), general + f'<div class="grid lists">{sections}</div>', "lists",
                                 sub=sub), status)


def lists_page(req):
    return _view(req)


def _done(list_name, message):
    return Response.redirect(ui.url("/lists", msg=message) + "#" + anchor(list_name))


def add_post(req):
    list_name = req.params["name"]
    if list_name not in LIST_INFO:
        raise TextError("lists.err_no_list", name=list_name)
    try:
        lists.add_item(req.conn, list_name, req.form.get("name"))
    except ValueError as exc:
        return _view(req, (f"add-{list_name}", exc), 400)
    name = lists.find_item(req.conn, list_name, name=req.form.get("name"))["name"]
    return _done(list_name, t("lists.added", name=name, title=t(LIST_INFO[list_name][0])))


def _item(req):
    item = lists.get_item(req.conn, req.params["id"])
    if item is None:
        raise TextError("lists.err_no_item", id=req.params["id"])
    return item


def rename_post(req):
    item = _item(req)
    try:
        lists.rename_item(req.conn, item["id"], req.form.get("name"))
    except ValueError as exc:
        return _view(req, (f"rename-{item['id']}", exc), 400)
    new = lists.get_item(req.conn, item["id"])["name"]
    if new == item["name"]:
        return _done(item["list_name"], t("lists.rename_same", name=new))
    return _done(item["list_name"], t("lists.renamed", old=item["name"], new=new))


def hide_post(req):
    item = _item(req)
    try:
        check_can_hide(lists.get_list(req.conn, item["list_name"], include_hidden=True), item["id"])
    except ValueError as exc:
        return _view(req, ("page", exc), 400)
    lists.set_active(req.conn, item["id"], False)
    return _done(item["list_name"], t("lists.hidden_flash", name=item["name"]))


def show_post(req):
    item = _item(req)
    lists.set_active(req.conn, item["id"], True)
    return _done(item["list_name"], t("lists.shown_flash", name=item["name"]))


ROUTES = [
    ("GET", "/lists", lists_page),
    ("POST", "/lists/<name>/add", add_post),
    ("POST", "/lists/items/<int:id>/rename", rename_post),
    ("POST", "/lists/items/<int:id>/hide", hide_post),
    ("POST", "/lists/items/<int:id>/show", show_post),
]
