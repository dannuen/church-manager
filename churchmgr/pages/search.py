"""Search: find a Person by name, with or without Vietnamese accents.

``GET /search?q=`` is the page (works without JS); ``GET /api/search?q=`` gives JSON
``[{"id", "full_name", "status"}]`` for the live results on the dashboard.
"""

from .. import search as person_search
from .. import ui
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
        '<label for="q">Find a Person</label>'
        f'<div class="search-line"><input class="input" id="q" name="q" type="search" value="{h(q)}" '
        'autocomplete="off" aria-describedby="q-hint">'
        '<button class="btn primary" type="submit">Search</button></div>'
        '<p class="hint" id="q-hint">Type part of a name, with or without accents.</p></form>'
    )
    if not q:
        result = ""
    elif not rows:
        result = f'<p class="empty">No Person found for “{h(q)}”.</p>'
    else:
        items = "".join(
            '<li class="row" data-row><span class="what wrap">'
            + ui.clamp2(f'<a href="/people/{r["id"]}">{h(r["full_name"])}</a>', r["full_name"], lang="vi")
            + f'<span class="sub">{h(r["status_name"]) if r["status_name"] else ui.DASH}</span></span></li>'
            for r in rows
        )
        more = f'<p class="hint">Showing the first {LIMIT}. Type more of the name to narrow it.</p>' \
            if len(rows) == LIMIT else ""
        result = (f'<section class="panel" aria-label="Results"><ul class="rows">{items}</ul>{more}</section>')
    sub = h(ui.plural(len(rows), "Person", "People") + " found") if q else None
    return Response.html(ui.page("Search", form + result, "people", sub=sub))


def search_api(req):
    _q, rows = _find(req)
    return Response.json([{"id": r["id"], "full_name": r["full_name"], "status": r["status_name"]} for r in rows])


ROUTES = [
    ("GET", "/search", search_page),
    ("GET", "/api/search", search_api),
]
