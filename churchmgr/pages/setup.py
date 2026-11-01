"""First run: New church setup when no church copy is open.

Until a church copy is open, the server sends every page here. The pastor types the
church name; a blank church copy (default lists only) is made in the copies root,
opened, remembered in ``current.txt``, and the Dashboard opens.
"""

from .. import db, paths
from .. import setup as church_setup
from .. import ui
from ..server import Response
from ..ui import h


def _form(req, name="", error=None, status=200):
    root = req.state.copies_root
    body = (
        '<section class="panel narrow">'
        '<p>No church copy is open yet. Start a blank church copy. It keeps only the default lists '
        '(Status, Fund, Spending category, Recipient, Purpose, Ministry).</p>'
        + ui.form("/setup",
                  ui.field("Church name", "church_name", name, error=error, required=True, autocomplete="off",
                           hint="For example: Hội Thánh Tin Lành Bình An")
                  + ui.button("Start the church copy"))
        + f'<p class="hint">It is saved in <span class="path">{h(root)}</span>, outside OneDrive.</p>'
        "</section>"
    )
    return Response.html(ui.page("New church setup", body), status)


def setup_page(req):
    if req.state.copy_folder is not None:
        return Response.redirect("/")
    return _form(req)


def setup_post(req):
    if req.state.copy_folder is not None:
        return Response.redirect("/")
    name = req.form.get("church_name", "")
    try:
        folder = church_setup.new_church_setup(req.state.copies_root, name)
    except (ValueError, db.ChurchCopyError, paths.CopyPathError) as exc:
        return _form(req, name, error=str(exc), status=400)
    req.state.switch_copy(folder)
    return Response.redirect(ui.url("/", msg="New church setup is done. This is your Dashboard."))


ROUTES = [
    ("GET", "/setup", setup_page),
    ("POST", "/setup", setup_post),
]
