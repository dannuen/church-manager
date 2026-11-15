"""Settings (card C3): ``/settings`` changes the church name, the care reminder time, the Hermes door,
the language of the screens and the app color. ``POST /language`` is the language switch at the top of
every page.

The care reminder time is a whole number of months from 1 to 24: a Person needs a visit when their
last Visit is older than that. The page shows what the setting gives today (how many People need a
visit), next to the field that changes it. The Hermes door (Off by default) lets the optional Hermes
helper use this church copy through ``python -m churchmgr.agent``.
"""

from .. import care, i18n, settings, text, ui
from ..db import transaction
from ..i18n import TextError, t, tn
from ..server import Response
from ..ui import h, vi
from .people import form_error, panel

MIN_MONTHS, MAX_MONTHS = 1, 24


def parse_months(value):
    """``" 6 "`` -> ``6``. Only plain digits from 1 to 24; anything else raises ``ValueError``."""
    raw = (value or "").strip()
    if not (raw.isascii() and raw.isdigit()) or not MIN_MONTHS <= text.digits_to_int(raw) <= MAX_MONTHS:
        raise TextError("settings.months_error", min=MIN_MONTHS, max=MAX_MONTHS)
    return int(raw)


def safe_next(value):
    """The page to go back to after the language switch: a path of this app, else ``"/"``.
    Refused: no leading ``/``; ``//`` (another site); any ``\\`` (browsers read it as ``/``); anything
    that is not plain printable ASCII (it goes into the Location header)."""
    value = value or ""
    if value.startswith("/") and not value.startswith("//") and "\\" not in value \
            and value.isascii() and value.isprintable():
        return value
    return "/"


def _shown_color(conn, posted):
    """The color in the picker: the one sent back with a refused form when it is a good color, else the
    saved one (a color picker cannot show a bad value)."""
    try:
        return settings.check_app_color(posted)
    except ValueError:
        return settings.get_app_color(conn)


def _view(req, values=None, errors=None, status=200):
    conn = req.conn
    errors = errors or {}
    months = care.reminder_months(conn)
    door = "on" if settings.hermes_door_on(conn) else "off"
    v = values or {"church_name": req.church_name, "care_reminder_months": str(months)}
    door_options = [("off", t("settings.door_off")), ("on", t("settings.door_on"))]
    inner = (
        ui.field(t("settings.church_name"), "church_name", v.get("church_name", ""), required=True,
                 autocomplete="off", lang="vi", error=errors.get("church_name"), hint=t("settings.church_name_hint"))
        + ui.field(t("settings.care_months"), "care_reminder_months", v.get("care_reminder_months", ""),
                   type="number", min=str(MIN_MONTHS), max=str(MAX_MONTHS), step="1", required=True,
                   error=errors.get("care_reminder_months"),
                   hint=t("settings.care_months_hint", min=MIN_MONTHS, max=MAX_MONTHS))
        + ui.select_field(t("settings.hermes_door"), settings.HERMES_DOOR, door_options,
                          v.get(settings.HERMES_DOOR, door), error=errors.get(settings.HERMES_DOOR),
                          hint=t("settings.door_hint"))
        + ui.select_field(t("core.language"), settings.LANGUAGE, ui.LANG_NAMES,
                          v.get(settings.LANGUAGE, settings.get_language(conn)), error=errors.get(settings.LANGUAGE),
                          hint=t("settings.language_hint"))
        + ui.field(t("settings.app_color"), settings.APP_COLOR, _shown_color(conn, v.get(settings.APP_COLOR)),
                   type="color", error=errors.get(settings.APP_COLOR), hint=t("settings.app_color_hint"))
        + form_error(errors) + ui.button(t("settings.save"))
    )
    form_panel = panel("settings-form", t("settings.panel_church"), ui.form("/settings", inner))
    need = len(care.needs_visit(conn))
    effect = (f'<div class="kpi" data-row><span class="kpi-label">{h(t("settings.needs_today"))}</span>'
              f'<span class="kpi-value num">{h(tn("people.count", need))}</span>'
              f'<span class="kpi-sub">{h(t("settings.no_visit_in", months=tn("core.months", months)))}</span>'
              "</div>")
    links = ui.t_html("settings.links", care=f'<a href="/care">{h(t("core.nav_care"))}</a>',
                      lists=f'<a href="/lists">{h(t("core.nav_lists"))}</a>',
                      copies=f'<a href="/copies">{h(t("core.nav_copies"))}</a>')
    side = panel("settings-effect", t("settings.panel_care"), effect + f'<p class="hint">{links}</p>',
                 meta=h(t("settings.panel_care_meta")))
    body = (f'<div class="grid settings"><div class="span-7 stack">{form_panel}</div>'
            f'<div class="span-5 stack">{side}</div></div>')
    sub = f"{vi(req.church_name)} · {h(t('settings.sub', months=tn('core.months', months)))}"
    return Response.html(ui.page(t("settings.title"), body, "settings", sub=sub), status)


def settings_page(req):
    return _view(req)


def settings_post(req):
    f = req.form
    errors, name, months = {}, None, None
    try:
        name = text.clean_name(f.get("church_name"), "settings.church_name")
    except ValueError as exc:
        errors["church_name"] = i18n.error_text(exc)
    try:
        months = parse_months(f.get("care_reminder_months"))
    except ValueError as exc:
        errors["care_reminder_months"] = i18n.error_text(exc)
    door = f.get(settings.HERMES_DOOR)  # no field (an old form) = keep the door as it is
    if door is not None:
        try:
            settings.check_hermes_door(door)
        except ValueError as exc:
            errors[settings.HERMES_DOOR] = i18n.error_text(exc)
    lang = f.get(settings.LANGUAGE)  # no field (an old form) = keep the language as it is
    if lang is not None:
        try:
            settings.check_language(lang)
        except ValueError as exc:
            errors[settings.LANGUAGE] = i18n.error_text(exc)
    color = f.get(settings.APP_COLOR)  # no field (an old form) = keep the app color as it is
    if color is not None:
        try:
            color = settings.check_app_color(color)
        except ValueError as exc:
            errors[settings.APP_COLOR] = i18n.error_text(exc)
    if errors:
        return _view(req, f, errors, 400)
    with transaction(req.conn):
        settings.set_setting(req.conn, "church_name", name)
        settings.set_setting(req.conn, "care_reminder_months", months)
        if door is not None:
            settings.set_setting(req.conn, settings.HERMES_DOOR, door)
        if lang is not None:
            settings.set_setting(req.conn, settings.LANGUAGE, lang)
        if color is not None:
            settings.set_setting(req.conn, settings.APP_COLOR, color)
    door_now = "on" if settings.hermes_door_on(req.conn) else "off"
    # made after the save: the flash is in the language the next page shows
    return Response.redirect(ui.url("/settings", msg=t("settings.saved", name=name, months=tn("core.months", months),
                                                       door=t(f"settings.door_state_{door_now}"))))


def language_post(req):
    """The language switch (``lang`` = ``vi`` or ``en``, else 400). Saved in the open church copy; with no
    church copy open (first run) kept in server memory for this run only. Then back to ``next``."""
    lang = settings.check_language(req.form.get("lang"))
    if req.state.copy_folder is None:
        req.state.first_run_lang = lang
    else:
        with transaction(req.conn):
            settings.set_setting(req.conn, settings.LANGUAGE, lang)
    return Response.redirect(safe_next(req.form.get("next")))


ROUTES = [
    ("GET", "/settings", settings_page),
    ("POST", "/settings", settings_post),
    ("POST", "/language", language_post),
]
