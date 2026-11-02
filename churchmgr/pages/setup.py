"""First run: New church setup when no church copy is open.

Until a church copy is open, the server sends every page here. The pastor types the church name and
picks the language (Tiếng Việt at the start); a blank church copy (default lists only, their items in
that language, and that ``language`` setting) is made in the copies root, opened, remembered in
``current.txt``, and the Dashboard opens.
"""

from .. import db, i18n, paths, settings
from .. import setup as church_setup
from .. import ui
from ..i18n import t
from ..server import Response
from ..ui import h


def _form(req, name="", lang=None, errors=None, status=200):
    errors = errors or {}
    root = req.state.copies_root
    # a folder path is no language: lang="zxx" keeps it out of the words to translate
    path = f'<span class="path" lang="zxx">{h(root)}</span>'
    body = (
        '<section class="panel narrow">'
        f'<p>{h(t("setup.intro"))}</p>'
        + ui.form("/setup",
                  ui.field(t("settings.church_name"), "church_name", name, error=errors.get("church_name"),
                           required=True, autocomplete="off", lang="vi", hint=t("setup.name_hint"))
                  + ui.select_field(t("core.language"), settings.LANGUAGE, ui.LANG_NAMES, lang or ui.current_lang(),
                                    error=errors.get(settings.LANGUAGE), hint=t("setup.language_hint"))
                  + ui.button(t("setup.start")))
        + f'<p class="hint">{ui.t_html("setup.saved_in", path=path)}</p>'
        "</section>"
    )
    return Response.html(ui.page(t("setup.title"), body), status)


def setup_page(req):
    if req.state.copy_folder is not None:
        return Response.redirect("/")
    return _form(req)


def setup_post(req):
    if req.state.copy_folder is not None:
        return Response.redirect("/")
    name = req.form.get("church_name", "")
    lang = req.form.get(settings.LANGUAGE) or ui.current_lang()  # no field: the language on screen (vi at start)
    try:
        settings.check_language(lang)
    except ValueError as exc:
        return _form(req, name, lang, {settings.LANGUAGE: i18n.error_text(exc)}, 400)
    try:
        folder = church_setup.new_church_setup(req.state.copies_root, name, lang)
    except (ValueError, db.ChurchCopyError, paths.CopyPathError) as exc:
        return _form(req, name, lang, {"church_name": i18n.error_text(exc)}, 400)
    req.state.switch_copy(folder)
    return Response.redirect(ui.url("/", msg=t("setup.done")))  # the new copy is open: its language


ROUTES = [
    ("GET", "/setup", setup_page),
    ("POST", "/setup", setup_post),
]
