"""Page layout and small HTML helpers shared by every page.

Rules for page code:
- Every value that goes into HTML passes through :func:`h` (or a helper here that calls it).
- Vietnamese data (names, titles, places, notes) goes in ``lang="vi"``: use :func:`vi`.
- No inline ``<script>`` or ``onclick``: the server's Content-Security-Policy blocks them.
  The only JS is ``web/app.js`` (live search; a button with ``data-print`` prints the page).
- A handler returns ``Response.html(ui.page(title, body_html, active))``. ``page`` adds the one h1,
  the sidebar with the church name, and the flash message from ``?msg=`` (see :func:`url`).
"""

import datetime as _dt
import html
import threading
import urllib.parse

from . import money

NAV = (
    ("dashboard", "Dashboard", "/"),
    ("people", "People", "/people"),
    ("families", "Families", "/families"),
    ("chi-phai", "Chi phái", "/chi-phai"),
    ("calendar", "Calendar", "/calendar"),
    ("money", "Money", "/money"),
    ("care", "Care", "/care"),
    ("documents", "Documents", "/documents"),
    ("sent", "Sent documents", "/sent"),
    ("lists", "Lists", "/lists"),
    ("copies", "Copies", "/copies"),
    ("settings", "Settings", "/settings"),
)
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December")
DASH = '<span class="dash">—</span>'  # a missing value

_local = threading.local()


def set_request(req):
    """The server calls this before a handler runs (and with ``None`` after)."""
    _local.request = req


def current_request():
    return getattr(_local, "request", None)


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
    """``"2026-11-01"`` -> ``"Sun"``."""
    return WEEKDAYS[_parse_day(value).weekday()]


def fmt_month(year, month):
    """``fmt_month(2026, 11)`` -> ``"November 2026"``."""
    return f"{MONTHS[month - 1]} {year}"


def fmt_money(amount):
    """Whole dong -> ``"1.250.000 ₫"`` (``money.format_vnd``; never a float)."""
    return money.format_vnd(amount)


def plural(n, one, many):
    """``plural(1, "Person", "People")`` -> ``"1 Person"``."""
    return f"{n} {one if n == 1 else many}"


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

def _head(title):
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{h(title)}</title>\n'
        '<link rel="stylesheet" href="/static/style.css">\n'
        '<link rel="stylesheet" href="/static/print.css">\n'
        '<script src="/static/app.js" defer></script>\n</head>\n'
    )


def _sidebar(church, active):
    current = ' aria-current="page"'
    links = "".join(
        f'<a class="nav-item" href="{href}"{current if key == active else ""}>{h(label)}</a>'
        for key, label, href in NAV
    )
    return (
        '<aside class="sidebar">'
        f'<a class="brand" href="/"><span class="brand-app">Church Manager</span>'
        f'<span class="brand-church" lang="vi">{h(church)}</span></a>'
        f'<nav class="nav" aria-label="Main">{links}</nav>'
        '</aside>'
    )


def title_row(title, sub=None, actions=""):
    sub_html = f'<p class="sub">{sub}</p>' if sub else ""
    actions_html = f'<div class="actions">{actions}</div>' if actions else ""
    return f'<header class="title-row"><div><h1>{h(title)}</h1>{sub_html}</div>{actions_html}</header>'


def page(title, body_html, active=None, sub=None, actions=""):
    """The whole HTML page: sidebar (church name + nav), the h1 ``title``, the flash
    message from ``?msg=``, then ``body_html``.

    ``active``: the NAV key to mark (``"people"``, ``"money"``, ...). ``sub`` is trusted HTML
    (escape its values) for the one line under the h1; ``actions`` is trusted HTML for buttons
    on the right of the title. With no church copy open (first run) there is no navigation.
    """
    req = current_request()
    church = req.church_name if req is not None else None
    msg = req.query.get("msg") if req is not None else None
    flash = f'<p class="flash" role="status">{h(msg)}</p>' if msg else ""
    full_title = f"{title} · {church}" if church else f"{title} · Church Manager"
    side = _sidebar(church, active) if church else (
        '<aside class="sidebar"><span class="brand"><span class="brand-app">Church Manager</span></span></aside>'
    )
    return (
        _head(full_title)
        + f'<body>\n<div class="app">{side}<main class="canvas">'
        + flash + title_row(title, sub, actions) + body_html
        + "</main></div>\n</body>\n</html>\n"
    )


def bare_page(title, body_html):
    """A page with no data at all (used for errors when the church copy cannot be read)."""
    return (
        _head(f"{title} · Church Manager")
        + '<body>\n<div class="app"><aside class="sidebar"><a class="brand" href="/">'
        + '<span class="brand-app">Church Manager</span></a></aside><main class="canvas">'
        + title_row(title) + body_html + "</main></div>\n</body>\n</html>\n"
    )
