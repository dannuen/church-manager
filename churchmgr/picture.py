"""The church picture: ONE file, ``church-picture`` (no extension, :data:`db.PICTURE_NAME`), in the church
copy folder next to ``documents/``. It is the church's own data, never kept in ``web/``.

With a picture every page shows it at the top (``ui.page``: the ``--hero-image`` token and
``<div class="app has-hero">``, styled in ``web/style.css``). Settings saves it and removes it;
``GET /church-picture`` gives it back (``pages/settings.py``).

Rules kept here:
- The kind is read from the first bytes, never from a file name: JPEG, PNG or WebP, else refused.
- At most :data:`MAX_SIZE` (5 MB). A refusal is a ``TextError`` (``str()`` English; pages show
  ``i18n.error_text``) and writes nothing.
- The one name is fixed: no name or path from a request is ever joined to a folder here.
- A save writes ``church-picture.partial`` first, then ``os.replace``: a picture is there whole or
  not at all.
"""

import os

from . import db, paths
from .i18n import TextError

MAX_SIZE = 5 * 1024 * 1024  # 5 MB, the instruction file (part 1)
MB = 1024 * 1024
PARTIAL = db.PICTURE_NAME + ".partial"


def picture_type(data):
    """The content type from the first bytes: ``"image/jpeg"`` (FF D8 FF), ``"image/png"``
    (89 50 4E 47 0D 0A 1A 0A) or ``"image/webp"`` (``RIFF``, 4 bytes, ``WEBP``); anything else ``None``."""
    data = bytes(data[:12])
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(data) == 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _file(folder):
    return paths.check_not_onedrive(folder) / db.PICTURE_NAME


def save_picture(folder, data):
    """Keep ``data`` (bytes) as the church picture of the church copy in ``folder``, in place of any old
    one. Refused (``TextError``, nothing written): no data, over 5 MB, not a JPEG, PNG or WebP.
    Returns the path of the file."""
    if isinstance(data, (bytearray, memoryview)):
        data = bytes(data)
    if not data:
        raise TextError("settings.err_picture_none")
    if not isinstance(data, bytes):
        raise TypeError("the church picture must be bytes")
    if len(data) > MAX_SIZE:
        raise TextError("settings.err_picture_size", mb=MAX_SIZE // MB)
    if picture_type(data) is None:
        raise TextError("settings.err_picture_kind")
    target = _file(folder)
    partial = target.with_name(PARTIAL)
    try:
        partial.write_bytes(data)
        os.replace(partial, target)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return target


def picture_path(folder):
    """The path of the church picture of the church copy in ``folder``, or ``None`` when there is none."""
    path = _file(folder)
    return path if path.is_file() and not path.is_symlink() else None


def picture_version(folder):
    """The ``st_mtime_ns`` of the church picture (a new picture gives a new page address), or ``None``."""
    path = picture_path(folder)
    if path is None:
        return None
    try:
        return path.stat().st_mtime_ns
    except FileNotFoundError:  # removed just now
        return None


def remove_picture(folder):
    """Delete the church picture, and only that file. ``True`` when there was one, ``False`` when not."""
    path = picture_path(folder)
    if path is None:
        return False
    path.unlink(missing_ok=True)
    return True
