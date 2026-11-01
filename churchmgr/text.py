"""Text helpers: NFC, the search fold, slugs, and checks for dates and ids.

Every text value is NFC-normalized before it is stored. Dates are TEXT
``YYYY-MM-DD``; date-times are TEXT ``YYYY-MM-DD HH:MM`` in local time.
"""

import datetime as _dt
import re
import unicodedata

_SPACES = re.compile(r"\s+")
_NOT_SLUG = re.compile(r"[^a-z0-9]+")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_DATETIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}")
_DIGITS = re.compile(r"[0-9]+")
MAX_NAME_LENGTH = 120  # a name (Full name, Family, Chi phái, list item, title) has at most this many characters


def nfc(s):
    """Return ``s`` in Unicode NFC form. ``None`` stays ``None``."""
    if s is None:
        return None
    if not isinstance(s, str):
        raise TypeError(f"text expected, got {type(s).__name__}")
    return unicodedata.normalize("NFC", s)


def fold(s):
    """Fold text for search: no diacritics, lower case, single spaces.

    NFC -> đ/Đ to d/D -> NFD -> drop combining marks (Mn) -> lower ->
    collapse whitespace -> strip. ``fold("Nguyễn Hải Đăng") == "nguyen hai dang"``.
    """
    if s is None:
        return ""
    s = nfc(s).replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return _SPACES.sub(" ", s.lower()).strip()


def slugify(name):
    """Folder-safe name: fold, then every run of non ``[a-z0-9]`` becomes ``-``."""
    slug = _NOT_SLUG.sub("-", fold(name)).strip("-")
    return slug or "church"


def clean_text(value):
    """Optional text field: NFC and strip. Empty text becomes ``None``."""
    if value is None:
        return None
    value = nfc(value).strip()
    return value or None


def clean_name(value, what="Name"):
    """Required name: NFC, single spaces, strip. Empty or longer than ``MAX_NAME_LENGTH``
    characters raises ``ValueError`` starting with ``what``."""
    if value is None or not isinstance(value, str):
        raise ValueError(f"{what} is required.")
    value = _SPACES.sub(" ", nfc(value)).strip()
    if not value:
        raise ValueError(f"{what} is required.")
    if len(value) > MAX_NAME_LENGTH:
        raise ValueError(f"{what}: use at most {MAX_NAME_LENGTH} characters.")
    return value


def check_date(value, what="Date"):
    """Return the date as ``YYYY-MM-DD`` text, or raise ``ValueError``.

    Accepts a ``datetime.date`` or text in exactly that form.
    """
    if isinstance(value, _dt.datetime):
        value = value.date()
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, str):
        v = value.strip()
        if _DATE.fullmatch(v):
            try:
                _dt.date.fromisoformat(v)
                return v
            except ValueError:
                pass
    raise ValueError(f"{what} must be a real date written YYYY-MM-DD, for example 2026-05-31.")


def check_datetime(value, what="Date and time"):
    """Return the date-time as ``YYYY-MM-DD HH:MM`` text (local time), or raise ``ValueError``."""
    if isinstance(value, _dt.datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, str):
        v = value.strip()
        if _DATETIME.fullmatch(v):
            try:
                _dt.datetime.strptime(v, "%Y-%m-%d %H:%M")
                return v
            except ValueError:
                pass
    raise ValueError(f"{what} must be written YYYY-MM-DD HH:MM, for example 2026-05-31 09:30.")


def today_text():
    """Today's local date as ``YYYY-MM-DD``."""
    return _dt.date.today().isoformat()


def now_text():
    """The local date-time now as ``YYYY-MM-DD HH:MM``."""
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def to_id(value, what="id"):
    """Return a positive integer id from an int or digit text, or raise ``ValueError``."""
    if isinstance(value, bool):
        raise ValueError(f"{what} must be a whole number.")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and _DIGITS.fullmatch(value.strip()):
        number = int(value.strip())
    else:
        raise ValueError(f"{what} must be a whole number.")
    if number <= 0:
        raise ValueError(f"{what} must be a whole number above 0.")
    return number
