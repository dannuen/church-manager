"""Settings (card C3): ``/settings`` changes the church name and the care reminder time.

The care reminder time is a whole number of months from 1 to 24: a Person needs a visit when their
last Visit is older than that. The page shows what the setting gives today (how many People need a
visit), next to the field that changes it.
"""

from .. import care, settings, text, ui
from ..db import transaction
from ..server import Response
from ..ui import h, vi
from .people import form_error, panel

MIN_MONTHS, MAX_MONTHS = 1, 24
_MONTHS_ERROR = f"Care reminder time must be a whole number of months from {MIN_MONTHS} to {MAX_MONTHS}."


def parse_months(value):
    """``" 6 "`` -> ``6``. Only plain digits from 1 to 24; anything else raises ``ValueError``."""
    raw = (value or "").strip()
    if not (raw.isascii() and raw.isdigit()) or not MIN_MONTHS <= int(raw) <= MAX_MONTHS:
        raise ValueError(_MONTHS_ERROR)
    return int(raw)


def _view(req, values=None, errors=None, status=200):
    conn = req.conn
    errors = errors or {}
    months = care.reminder_months(conn)
    v = values or {"church_name": req.church_name, "care_reminder_months": str(months)}
    inner = (
        ui.field("Church name", "church_name", v.get("church_name", ""), required=True, autocomplete="off",
                 lang="vi", error=errors.get("church_name"),
                 hint="Shown at the top of every page, on the Giving statement and in the Handover file name.")
        + ui.field("Care reminder time (months)", "care_reminder_months", v.get("care_reminder_months", ""),
                   type="number", min=str(MIN_MONTHS), max=str(MAX_MONTHS), step="1", required=True,
                   error=errors.get("care_reminder_months"),
                   hint=f"A Person needs a visit when their last Visit is older than this. "
                        f"{MIN_MONTHS} to {MAX_MONTHS} months; 3 is the usual.")
        + form_error(errors) + ui.button("Save settings")
    )
    form_panel = panel("settings-form", "Church", ui.form("/settings", inner))
    need = len(care.needs_visit(conn))
    effect = (f'<div class="kpi" data-row><span class="kpi-label">Needs a visit today</span>'
              f'<span class="kpi-value num">{h(ui.plural(need, "Person", "People"))}</span>'
              f'<span class="kpi-sub">No Visit in the last {h(ui.plural(months, "month", "months"))}, or never</span>'
              "</div>")
    links = ('<p class="hint">See them in <a href="/care">Care</a>. The lists of choices are in '
             '<a href="/lists">Lists</a>; where this church copy is saved is in <a href="/copies">Copies</a>.</p>')
    side = panel("settings-effect", "Care reminder", effect + links, meta="What the care reminder time gives today")
    body = (f'<div class="grid settings"><div class="span-7 stack">{form_panel}</div>'
            f'<div class="span-5 stack">{side}</div></div>')
    sub = f"{vi(req.church_name)} · care reminder time {h(ui.plural(months, 'month', 'months'))}"
    return Response.html(ui.page("Settings", body, "settings", sub=sub), status)


def settings_page(req):
    return _view(req)


def settings_post(req):
    f = req.form
    errors, name, months = {}, None, None
    try:
        name = text.clean_name(f.get("church_name"), "Church name")
    except ValueError as exc:
        errors["church_name"] = str(exc)
    try:
        months = parse_months(f.get("care_reminder_months"))
    except ValueError as exc:
        errors["care_reminder_months"] = str(exc)
    if errors:
        return _view(req, f, errors, 400)
    with transaction(req.conn):
        settings.set_setting(req.conn, "church_name", name)
        settings.set_setting(req.conn, "care_reminder_months", months)
    return Response.redirect(ui.url("/settings", msg=f"Settings saved: {name}, care reminder time "
                                                     f"{ui.plural(months, 'month', 'months')}."))


ROUTES = [
    ("GET", "/settings", settings_page),
    ("POST", "/settings", settings_post),
]
