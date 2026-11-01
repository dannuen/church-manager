"""Lists (card C3): ``/lists`` has one section per editable list (Recipient, Purpose, Fund, Spending
category, Ministry, Status). Each item can be renamed, hidden or shown; new items are added at the end.

Rules kept here:
- List items are never deleted (the database refuses it too). Hide an item instead.
- A hidden item is left out of every new-entry dropdown (``lists.get_list`` gives shown items only),
  and old rows that use it keep showing its name.
- The last shown item of a list cannot be hidden: new entries always need one to choose.
"""

from .. import lists, ui
from ..schema import LIST_NAMES
from ..server import Response
from ..ui import h
from .people import empty, form_error, panel

# list name -> (section title, one line from the glossary, words for what uses an item)
LIST_INFO = {
    "recipient": ("Recipient", "The outside body a Sent document goes to", ("Sent document", "Sent documents")),
    "purpose": ("Purpose", "Why a Sent document is sent", ("Sent document", "Sent documents")),
    "fund": ("Fund", "Where an Offering goes", ("Offering", "Offerings")),
    "spending_category": ("Spending category", "What an Expense is for", ("Expense", "Expenses")),
    "ministry": ("Ministry", "Where a Person serves in the church", ("Person serving now", "People serving now")),
    "status": ("Status", "Where a Person stands with the church now", ("Person now", "People now")),
}
LIST_ORDER = tuple(LIST_INFO)
assert set(LIST_ORDER) == set(LIST_NAMES), "every editable list has a section"

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
    """Raise ``ValueError`` when ``item_id`` is the last shown item of its list."""
    shown = [i for i in items if i["active"]]
    if len(shown) == 1 and shown[0]["id"] == item_id:
        title = LIST_INFO[shown[0]["list_name"]][0]
        raise ValueError(f"Keep at least one {title} shown: new entries need one to choose.")


# ---------------------------------------------------------------- /lists

def _item_row(item, used, words, error):
    iid = int(item["id"])
    hidden = not item["active"]
    tag = ' <span class="tag">Hidden</span>' if hidden else ""
    use_text = ui.plural(used, *words)  # a real zero prints 0
    toggle = "show" if hidden else "hide"
    toggle_form = (f'<form class="row-form" action="/lists/items/{iid}/{toggle}" method="post">'
                   f'<button class="link-btn" type="submit" aria-label="{toggle.title()} {h(item["name"])}">'
                   f"{toggle.title()}</button></form>")
    rename_error = error[1] if error and error[0] == f"rename-{iid}" else None
    rename = (f'<details class="rename"{" open" if rename_error else ""}><summary>Rename</summary>'
              + ui.form(f"/lists/items/{iid}/rename",
                        '<div class="inline-add">'
                        + ui.field("New name", "name", item["name"], id=f"rename-{iid}", required=True,
                                   autocomplete="off", lang="vi", error=rename_error)
                        + ui.button("Save", "secondary") + "</div>")
              + "</details>")
    return (f'<li class="row list-item{" is-hidden" if hidden else ""}" data-row>'
            f'<span class="what" lang="vi">{h(item["name"])}{tag}</span>'
            f'<span class="side num">{h(use_text)}</span>{toggle_form}{rename}</li>')


def _section(conn, list_name, error):
    title, line, words = LIST_INFO[list_name]
    items = lists.get_list(conn, list_name, include_hidden=True)
    used = dict(conn.execute(_USAGE_SQL[list_name]).fetchall())
    rows = "".join(_item_row(i, used.get(i["id"], 0), words, error) for i in items)
    body = f'<ul class="rows">{rows}</ul>' if items else empty(f"No {title} yet.")
    add_error = error[1] if error and error[0] == f"add-{list_name}" else None
    add = ui.form(f"/lists/{list_name}/add",
                  '<div class="inline-add">'
                  + ui.field(f"New {title}", "name", "", id=f"add-{anchor(list_name)}", required=True,
                             autocomplete="off", lang="vi", error=add_error)
                  + ui.button("Add", "secondary") + "</div>")
    shown = sum(1 for i in items if i["active"])
    meta = h(f"{line} · {shown} shown" + (f", {len(items) - shown} hidden" if shown != len(items) else ""))
    return (f'<div id="{anchor(list_name)}">'
            + panel(anchor(list_name), title, body + f'<div class="add-form">{add}</div>', meta=meta)
            + "</div>")


def _view(req, error=None, status=200):
    conn = req.conn
    # Two columns that stack on their own (no shared row heights): Recipient, Fund, Ministry on the
    # left; Purpose, Spending category, Status on the right. Read across, the order is the card's.
    left = "".join(_section(conn, name, error) for name in LIST_ORDER[0::2])
    right = "".join(_section(conn, name, error) for name in LIST_ORDER[1::2])
    sections = f'<div class="span-6 stack">{left}</div><div class="span-6 stack">{right}</div>'
    general = form_error({"": error[1]}) if error and error[0] == "page" else ""
    sub = h("Rename, hide or show an item, or add a new one. Nothing is ever deleted: "
            "a hidden item is not offered for new entries, and what already uses it keeps its name.")
    return Response.html(ui.page("Lists", general + f'<div class="grid lists">{sections}</div>', "lists", sub=sub),
                         status)


def lists_page(req):
    return _view(req)


def _plain(message, list_name):
    """The data layer names a list by its code (``spending_category``); the page uses the glossary word."""
    return message.replace(f"the {list_name} list", f"the {LIST_INFO[list_name][0]} list")


def _done(list_name, message):
    return Response.redirect(ui.url("/lists", msg=message) + "#" + anchor(list_name))


def add_post(req):
    list_name = req.params["name"]
    if list_name not in LIST_INFO:
        raise ValueError(f"There is no list called {list_name}.")
    try:
        lists.add_item(req.conn, list_name, req.form.get("name"))
    except ValueError as exc:
        return _view(req, (f"add-{list_name}", _plain(str(exc), list_name)), 400)
    name = lists.find_item(req.conn, list_name, name=req.form.get("name"))["name"]
    return _done(list_name, f"{name} added to {LIST_INFO[list_name][0]}.")


def _item(req):
    item = lists.get_item(req.conn, req.params["id"])
    if item is None:
        raise ValueError(f"No list item with id {req.params['id']}.")
    return item


def rename_post(req):
    item = _item(req)
    try:
        lists.rename_item(req.conn, item["id"], req.form.get("name"))
    except ValueError as exc:
        return _view(req, (f"rename-{item['id']}", _plain(str(exc), item["list_name"])), 400)
    new = lists.get_item(req.conn, item["id"])["name"]
    if new == item["name"]:
        return _done(item["list_name"], f"{new} kept its name. Nothing changed.")
    return _done(item["list_name"], f"{item['name']} is now called {new}. Everything that uses it shows the new name.")


def hide_post(req):
    item = _item(req)
    try:
        check_can_hide(lists.get_list(req.conn, item["list_name"], include_hidden=True), item["id"])
    except ValueError as exc:
        return _view(req, ("page", str(exc)), 400)
    lists.set_active(req.conn, item["id"], False)
    return _done(item["list_name"], f"{item['name']} is hidden. It is not offered for new entries; "
                                    "what already uses it keeps its name.")


def show_post(req):
    item = _item(req)
    lists.set_active(req.conn, item["id"], True)
    return _done(item["list_name"], f"{item['name']} is shown again.")


ROUTES = [
    ("GET", "/lists", lists_page),
    ("POST", "/lists/<name>/add", add_post),
    ("POST", "/lists/items/<int:id>/rename", rename_post),
    ("POST", "/lists/items/<int:id>/hide", hide_post),
    ("POST", "/lists/items/<int:id>/show", show_post),
]
