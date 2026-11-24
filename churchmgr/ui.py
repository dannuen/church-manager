"""Page layout and small HTML helpers shared by every page.

Rules for page code:
- Every value that goes into HTML passes through :func:`h` (or a helper here that calls it).
- Vietnamese data (names, titles, places, notes) goes in ``lang="vi"``: use :func:`vi`.
- No inline ``<script>`` or ``onclick``: the server's Content-Security-Policy blocks them.
  The only JS is ``web/app.js`` (live search; a button with ``data-print`` prints the page).
- A handler returns ``Response.html(ui.page(title, body_html, active))``. ``page`` adds the one h1,
  the sidebar with the church name, and the flash message from ``?msg=`` (see :func:`url`).
- Words on screen come from the text table: ``i18n.t(key)`` in the language of this request
  (:func:`current_lang`). Data (names, notes, list items) is never translated.
"""

import datetime as _dt
import html
import threading
import urllib.parse

from . import app_color, i18n, money, picture, settings
from .i18n import t

NAV = (  # (key, TEXT key of the label, href)
    ("dashboard", "core.nav_dashboard", "/"),
    ("people", "core.nav_people", "/people"),
    ("families", "core.nav_families", "/families"),
    ("chi-phai", "core.nav_chi_phai", "/chi-phai"),
    ("calendar", "core.nav_calendar", "/calendar"),
    ("money", "core.nav_money", "/money"),
    ("care", "core.nav_care", "/care"),
    ("documents", "core.nav_documents", "/documents"),
    ("sent", "core.nav_sent", "/sent"),
    ("lists", "core.nav_lists", "/lists"),
    ("copies", "core.nav_copies", "/copies"),
    ("settings", "core.nav_settings", "/settings"),
    ("search", "core.nav_search", "/search"),
)
# Under 861px the top bar shows the other 5 items and a "More" fold that holds these 8, in NAV order. The
# 8 stay in the menu too (class in-more): style.css shows one place or the other, never both (CRIT-2).
NAV_MORE = ("families", "chi-phai", "documents", "sent", "lists", "copies", "settings", "search")
LANG_NAMES = (("vi", "Tiếng Việt"), ("en", "English"))  # never translated: each name in its own language
DASH = '<span class="dash">—</span>'  # a missing value

_local = threading.local()


def set_request(req):
    """The server calls this before a handler runs (and with ``None`` after)."""
    _local.request = req


def current_request():
    return getattr(_local, "request", None)


def current_lang():
    """The language of the screens for this request: the ``language`` setting of the open church copy.
    With no church copy open (first run): the choice kept in server memory for this run (``vi`` at start).
    Outside a request: ``i18n.DEFAULT_LANG``."""
    req = current_request()
    if req is None:
        return i18n.DEFAULT_LANG
    if req.state.copy_folder is None:
        return req.state.first_run_lang
    try:
        return settings.get_language(req.conn)
    except Exception:  # the church copy cannot be read: the error page still needs its words
        return i18n.DEFAULT_LANG


i18n.set_lang_getter(current_lang)


# ---------------------------------------------------------------- text

def h(value):
    """HTML-escape any value. ``None`` becomes empty text."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def vi(value):
    """Vietnamese data in ``<span lang="vi">``; a missing value shows a grey dash."""
    if value is None or value == "":
        return DASH
    return f'<span lang="vi">{h(value)}</span>'


def clamp2(inner_html, full_text, lang=None, cls=""):
    """Text that wraps to 2 lines at most and then ends with "…" (``.clamp-2`` in style.css), never
    one cut line. The full text is in the ``title``. ``inner_html`` is trusted HTML (escape its values).
    In a row list put it in ``<span class="what wrap">``: the title of the row gets the width first."""
    lang_attr = f' lang="{h(lang)}"' if lang else ""
    return f'<span class="clamp-2{" " + cls if cls else ""}"{lang_attr} title="{h(full_text)}">{inner_html}</span>'


def row_side(html_parts, text_parts):
    """The grey ``<span class="side">`` of a row: one line with "…" (at most 30% of the row, style.css),
    its full text in the ``title``. ``html_parts`` are trusted HTML; ``text_parts`` are the same words as
    plain text (an empty one is left out of the title)."""
    full = " · ".join(t for t in text_parts if t)
    title = f' title="{h(full)}"' if full else ""
    return f'<span class="side"{title}>{" · ".join(html_parts)}</span>'


def url(path, **params):
    """``url("/money/statement", person_id=5, year=2026)`` -> ``/money/statement?person_id=5&year=2026``.
    ``None`` values are left out. Use ``msg=`` for the flash message on the next page."""
    clean = {k: v for k, v in params.items() if v is not None}
    return path + ("?" + urllib.parse.urlencode(clean) if clean else "")


def _parse_day(value):
    if isinstance(value, _dt.datetime):
        return value
    if isinstance(value, _dt.date):
        return _dt.datetime(value.year, value.month, value.day)
    text = str(value).strip()
    if len(text) >= 16:
        return _dt.datetime.strptime(text[:16], "%Y-%m-%d %H:%M")
    return _dt.datetime.strptime(text[:10], "%Y-%m-%d")


def fmt_date(value):
    """``"2026-11-01"`` (or a date-time, or a ``date``) -> ``"01/11/2026"``. Missing -> ``"—"``."""
    if value is None or value == "":
        return "—"
    return _parse_day(value).strftime("%d/%m/%Y")


def fmt_birth_date(value):
    """A Birth date: ``"1980-00-00"`` (the year only) -> ``"1980"``; a full date as :func:`fmt_date`
    (``"31/12/1980"``). Missing -> ``"—"``."""
    if isinstance(value, str) and value[4:] == "-00-00":
        return value[:4]
    return fmt_date(value)


def fmt_datetime(value):
    """``"2026-11-01 08:00"`` -> ``"01/11/2026 08:00"``. Missing -> ``"—"``."""
    if value is None or value == "":
        return "—"
    return _parse_day(value).strftime("%d/%m/%Y %H:%M")


def fmt_time(value):
    """``"2026-11-01 08:00"`` -> ``"08:00"``. Missing -> ``""``."""
    if value is None or len(str(value)) < 16:
        return ""
    return str(value)[11:16]


def fmt_weekday(value):
    """``"2026-11-01"`` -> ``"Sun"`` (``"Chúa Nhật"`` in Tiếng Việt)."""
    return t(f"core.weekday_{_parse_day(value).weekday()}")


def fmt_month(year, month):
    """``fmt_month(2026, 11)`` -> ``"November 2026"`` (``"Tháng 11/2026"`` in Tiếng Việt)."""
    return t("core.month_year", month=t(f"core.month_{month}"), year=year)


def fmt_money(amount):
    """Whole dong -> ``"1.250.000 ₫"`` (``money.format_vnd``; never a float)."""
    return money.format_vnd(amount)


def plural(n, one, many):
    """``plural(1, "Person", "People")`` -> ``"1 Person"``. Old callers only: new code uses ``i18n.tn``."""
    return f"{n} {one if n == 1 else many}"


def _code_word(prefix, code):
    """The word on screen for a code stored in English (``"Head"`` -> ``core.family_role_head``).
    An unknown code is shown as it is."""
    key = f"{prefix}{str(code).lower()}"
    return t(key) if key in i18n.TEXT[i18n.DEFAULT_LANG] else code


def family_role(code):
    """``"Head"`` -> ``"Chủ gia đình"`` / ``"Head"`` (``schema.FAMILY_ROLES``)."""
    return _code_word("core.family_role_", code)


def ministry_role(code):
    """``"Leader"`` -> ``"Trưởng ban"`` / ``"Leader"`` (``schema.MINISTRY_ROLES``)."""
    return _code_word("core.ministry_role_", code)


def calendar_kind(code):
    """``"Service"`` -> ``"Giờ thờ phượng"`` / ``"Service"`` (``schema.CALENDAR_KINDS``)."""
    return _code_word("core.kind_", code)


def t_html(key, **html_params):
    """``t(key)`` as HTML: the words escaped, each ``{param}`` filled with trusted HTML (escape its values),
    such as a link inside a sentence."""
    marks = {name: f"\x00{name}\x00" for name in html_params}
    out = h(t(key, **marks))
    for name, value in html_params.items():
        out = out.replace(marks[name], value)
    return out


# ---------------------------------------------------------------- forms

def _attrs(attrs):
    out = []
    for key, value in attrs.items():
        if value is None or value is False:
            continue
        key = key.rstrip("_").replace("_", "-")
        out.append(f" {key}" if value is True else f' {key}="{h(value)}"')
    return "".join(out)


def _wrap(label, fid, control, error, hint):
    hint_html = f'<p class="hint" id="{fid}-hint">{h(hint)}</p>' if hint else ""
    error_html = f'<p class="error" id="{fid}-error">{h(error)}</p>' if error else ""
    return f'<div class="field"><label for="{fid}">{h(label)}</label>{control}{hint_html}{error_html}</div>'


def _control_attrs(name, fid, error, hint, attrs):
    described = " ".join(x for x in (f"{fid}-hint" if hint else "", f"{fid}-error" if error else "") if x)
    return {"id": fid, "name": name, "aria_invalid": "true" if error else None,
            "aria_describedby": described or None, **attrs}


def field(label, name, value="", type="text", error=None, hint=None, **attrs):
    """A labelled ``<input>``: the label sits above it, an error sentence below it.
    Extra keyword arguments become attributes (``required=True``, ``max="2026-11-01"``, ``id=...``)."""
    fid = attrs.pop("id", f"f-{name}")
    a = _control_attrs(name, fid, error, hint, {"type": type, "value": value, **attrs})
    return _wrap(label, fid, f'<input class="input"{_attrs(a)}>', error, hint)


def textarea_field(label, name, value="", error=None, hint=None, **attrs):
    fid = attrs.pop("id", f"f-{name}")
    a = _control_attrs(name, fid, error, hint, {"rows": 3, **attrs})
    return _wrap(label, fid, f'<textarea class="input"{_attrs(a)}>{h(value)}</textarea>', error, hint)


def select_field(label, name, options, selected=None, error=None, hint=None, **attrs):
    """A labelled ``<select>``. ``options``: ``[(value, text), ...]``."""
    fid = attrs.pop("id", f"f-{name}")
    a = _control_attrs(name, fid, error, hint, attrs)
    opts = "".join(
        f'<option value="{h(v)}"{" selected" if str(v) == str(selected) else ""}>{h(t)}</option>'
        for v, t in options
    )
    return _wrap(label, fid, f'<select class="input"{_attrs(a)}>{opts}</select>', error, hint)


def hidden(name, value):
    return f'<input type="hidden" name="{h(name)}" value="{h(value)}">'


def button(text, kind="primary", **attrs):
    """A submit button. ``kind``: ``primary`` (near-black), ``secondary`` or ``danger``."""
    a = {"type": "submit", **attrs}
    return f'<button class="btn {h(kind)}"{_attrs(a)}>{h(text)}</button>'


def form(action, inner_html, method="post", multipart=False, **attrs):
    """A ``<form>``. ``multipart=True`` for a file field."""
    a = {"action": action, "method": method,
         "enctype": "multipart/form-data" if multipart else None, **attrs}
    return f'<form class="form"{_attrs(a)}>{inner_html}</form>'


def link_button(text, href, kind="secondary"):
    """A link that looks like a button (``primary``, ``secondary``)."""
    return f'<a class="btn {h(kind)}" href="{h(href)}">{h(text)}</a>'


# ---------------------------------------------------------------- layout

def _picture_version():
    """The ``st_mtime_ns`` of the church picture of the open church copy (``picture.picture_version``), or
    ``None``: no picture, no church copy open (first run), outside a request, or it cannot be read."""
    req = current_request()
    if req is None or req.state.copy_folder is None:
        return None
    try:
        return picture.picture_version(req.state.copy_folder)
    except Exception:  # the folder cannot be read: the top of the page stays plain
        return None


def _app_color_style(hero=None):
    """``<style>`` that sets the 4 colors of the app color of the open church copy (``app_color.theme`` of
    a checked ``#rrggbb``), right after style.css. No church copy open (first run), or it cannot be read:
    nothing, and style.css keeps its default colors.
    ``hero``: the :func:`_picture_version` of the church picture (``page`` only). Then one more token,
    ``--hero-image:url(/church-picture?v=<hero>)``: the wash of ``.has-hero`` paints it (web/style.css)."""
    req = current_request()
    if req is None or req.state.copy_folder is None:
        return ""
    try:
        values = app_color.theme(settings.get_app_color(req.conn))
    except Exception:  # the church copy cannot be read: the error page still needs its head
        return ""
    parts = [f"{name}:{value}" for name, value in values.items()]
    if hero is not None:
        parts.append(f"--hero-image:url(/church-picture?v={int(hero)})")
    return "<style>:root{" + ";".join(parts) + "}</style>\n"


def _head(title, hero=None):
    lang = current_lang()
    # The title holds pastor data (a name, the church name), and no element can carry its own lang there.
    title_tag = '<title lang="vi">' if lang == "vi" else "<title>"
    return (
        f'<!doctype html>\n<html lang="{h(lang)}">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'{title_tag}{h(title)}</title>\n'
        '<link rel="stylesheet" href="/static/style.css">\n'
        + _app_color_style(hero)
        + '<link rel="stylesheet" href="/static/print.css">\n'
        '<script src="/static/app.js" defer></script>\n</head>\n'
    )


def _here():
    """The path and query of this request (ASCII, for the switch to come back to). ``msg`` is left out:
    the flash was for one time. A page shown for a POST (a refused form) whose path has no GET page comes
    back to the page the form was on (the ``Referer``) when that path has a GET page, else to ``/``:
    the switch never leads to a 405."""
    req = current_request()
    if req is None:
        return "/"

    def where(path, query_all):
        query = {k: v for k, v in query_all.items() if k != "msg"}
        return urllib.parse.quote(path) + ("?" + urllib.parse.urlencode(query, doseq=True) if query else "")

    routes = getattr(req.state, "routes", None)
    if req.method == "GET" or routes is None:
        return where(req.path, req.query_all)
    get_pages = [regex for method, regex, *_rest in routes if method == "GET"]
    if any(regex.match(req.path) for regex in get_pages):
        return where(req.path, req.query_all)
    referer = urllib.parse.urlsplit((req.headers.get("Referer") if req.headers is not None else None) or "")
    path = urllib.parse.unquote(referer.path, errors="replace")
    if any(regex.match(path) for regex in get_pages):
        return where(path, urllib.parse.parse_qs(referer.query, keep_blank_values=True, errors="replace"))
    return "/"


def lang_switch():
    """The language switch at the top of every page: a POST to ``/language`` with the page to come back to.
    The current language has ``aria-pressed="true"``."""
    lang = current_lang()
    buttons = "".join(
        f'<button name="lang" value="{code}" lang="{code}" aria-pressed="{"true" if code == lang else "false"}">'
        f"{h(name)}</button>"
        for code, name in LANG_NAMES
    )
    return (f'<form class="lang-switch" method="post" action="/language" aria-label="{h(t("core.language"))}">'
            f'{hidden("next", _here())}{buttons}</form>')


def _sidebar(church, active):
    def item(key, label, href, cls):
        current = ' aria-current="page"' if key == active else ""
        return f'<a class="{cls}" href="{href}"{current}>{h(t(label))}</a>'

    links = "".join(item(key, label, href, "nav-item in-more" if key in NAV_MORE else "nav-item")
                    for key, label, href in NAV)
    more = "".join(item(key, label, href, "nav-item") for key, label, href in NAV if key in NAV_MORE)
    fold = (f'<details class="nav-more"><summary class="nav-item">{h(t("core.nav_more"))}</summary>'
            f'<div class="nav-more-list">{more}</div></details>')
    return (
        '<aside class="sidebar">'
        f'<a class="brand" href="/"><span class="brand-app">Church Manager</span>'
        f'<span class="brand-church" lang="vi">{h(church)}</span></a>'
        f'<nav class="nav" aria-label="{h(t("core.nav_label"))}">{links}{fold}</nav>'
        '</aside>'
    )


def _skip_link():
    """The first thing Tab reaches on every page: it jumps over the menu to ``main#main`` (CRIT-2)."""
    return f'<a class="skip-link no-print" href="#main">{h(t("core.skip_to_content"))}</a>'


def title_row(title, sub=None, actions="", lang=None):
    """The h1 (escaped ``title``), the one line under it and the buttons on its right.
    ``lang="vi"`` marks an h1 that holds a Vietnamese name (a Person, Family, Chi phái, Calendar item)."""
    sub_html = f'<p class="sub">{sub}</p>' if sub else ""
    actions_html = f'<div class="actions">{actions}</div>' if actions else ""
    lang_attr = f' lang="{h(lang)}"' if lang else ""
    return f'<header class="title-row"><div><h1{lang_attr}>{h(title)}</h1>{sub_html}</div>{actions_html}</header>'


def page(title, body_html, active=None, sub=None, actions="", lang=None):
    """The whole HTML page: sidebar (church name + nav), the h1 ``title``, the flash
    message from ``?msg=``, then ``body_html``.

    ``active``: the NAV key to mark (``"people"``, ``"money"``, ...). ``sub`` is trusted HTML
    (escape its values) for the one line under the h1; ``actions`` is trusted HTML for buttons
    on the right of the title. ``lang="vi"`` when the h1 holds a Vietnamese name.
    With no church copy open (first run) there is no navigation. The language switch comes first in ``main``;
    a skip link to ``main#main`` is the first thing in ``<body>``.
    With a church picture (``picture.py``) the head sets ``--hero-image`` and the app is
    ``<div class="app has-hero">``; with none the page is as it was before the picture.
    """
    req = current_request()
    hero = _picture_version()
    church = req.church_name if req is not None else None
    msg = req.query.get("msg") if req is not None else None
    flash = f'<p class="flash" role="status">{h(msg)}</p>' if msg else ""
    full_title = f"{title} · {church}" if church else f"{title} · Church Manager"
    side = _sidebar(church, active) if church else (
        '<aside class="sidebar"><span class="brand"><span class="brand-app">Church Manager</span></span></aside>'
    )
    return (
        _head(full_title, hero)
        + f'<body>\n{_skip_link()}<div class="{"app" if hero is None else "app has-hero"}">{side}'
        '<main class="canvas" id="main" tabindex="-1">'
        + lang_switch() + flash + title_row(title, sub, actions, lang) + body_html
        + "</main></div>\n</body>\n</html>\n"
    )


def bare_page(title, body_html):
    """A page with no data at all (used for errors when the church copy cannot be read)."""
    return (
        _head(f"{title} · Church Manager")
        + '<body>\n' + _skip_link() + '<div class="app"><aside class="sidebar"><a class="brand" href="/">'
        + '<span class="brand-app">Church Manager</span></a></aside><main class="canvas" id="main" tabindex="-1">'
        + lang_switch() + title_row(title) + body_html + "</main></div>\n</body>\n</html>\n"
    )
