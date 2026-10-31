"""New church setup: start a blank church copy that keeps only the default lists."""

from . import db, paths, text


def free_folder(copies_root, church_name):
    """``<copies_root>/<slug>``, or ``<slug>-2``, ``<slug>-3``, ... if that folder is taken."""
    root = paths.check_not_onedrive(copies_root)
    slug = text.slugify(text.clean_name(church_name, "Church name"))
    folder = root / slug
    n = 2
    while folder.exists():
        folder = root / f"{slug}-{n}"
        n += 1
    return folder


def new_church_setup(copies_root, church_name):
    """Make a blank church copy for ``church_name`` inside ``copies_root`` and return its folder.

    The copy has the default lists and settings only. Refused inside OneDrive.
    """
    folder = free_folder(copies_root, church_name)
    conn = db.create_church_copy(folder, church_name)
    conn.close()
    return folder
