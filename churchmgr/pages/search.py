"""Search: find a Person by name, with or without Vietnamese accents.

``GET /search?q=`` is the page (works without JS); ``GET /api/search?q=`` gives JSON
``[{"id", "full_name", "status"}]`` for the live results on the dashboard. Words on screen come from
the text table (section ``search``); names and Status items are data, shown as stored.
"""

from .. import search as person_search
from .. import ui
from ..i18n import t, tn
from ..server import Response
from ..ui import h

LIMIT = 20


def _find(req):
    q = (req.query.get("q") or "").strip()
    return q, (person_search.search_persons(req.conn, q, limit=LIMIT) if q else [])


def search_page(req):
    q, rows = _find(req)
    form = (
        '<form class="search-form panel" action="/search" method="get" role="search">'
        f'<label for="q">{h(t("search.find_person"))}</label>'
        f'<div class="search-line"><input class="input" id="q" name="q" type="search" value="{h(q)}" '
        'autocomplete="off" aria-describedby="q-hint">'
        f'<button class="btn primary" type="submit">{h(t("core.btn_search"))}</button></div>'
        f'<p class="hint" id="q-hint">{h(t("search.hint"))}</p></form>'
    )
    if not q:
        result = ""
    elif not rows:
        result = f'<p class="empty">{h(t("search.none", q=q))}</p>'
    else:
        items = "".join(
            '<li class="row" data-row><span class="what wrap">'
            + ui.clamp2(f'<a href="/people/{r["id"]}">{h(r["full_name"])}</a>', r["full_name"], lang="vi")
            + f'<span class="sub">{h(r["status_name"]) if r["status_name"] else ui.DASH}</span></span></li>'
            for r in rows
        )
        more = f'<p class="hint">{h(t("search.first_n", n=LIMIT))}</p>' if len(rows) == LIMIT else ""
        result = (f'<section class="panel" aria-label="{h(t("search.results"))}"><ul class="rows">{items}</ul>'
                  f"{more}</section>")
    sub = h(tn("search.found", len(rows))) if q else None
    return Response.html(ui.page(t("search.title"), form + result, "search", sub=sub))


def search_api(req):
    _q, rows = _find(req)
    return Response.json([{"id": r["id"], "full_name": r["full_name"], "status": r["status_name"]} for r in rows])


ROUTES = [
    ("GET", "/search", search_page),
    ("GET", "/api/search", search_api),
]
