"""Settings of one church copy (table ``setting``): church_name, care_reminder_months, hermes_door,
language, app_color."""

from . import app_color, i18n, text
from .i18n import TextError

HERMES_DOOR = "hermes_door"  # "on" or "off"; no row = off (the default)
HERMES_DOOR_CHOICES = ("off", "on")
LANGUAGE = "language"  # "vi" or "en"; no row, or any other text, = "vi"
LANGUAGE_CHOICES = i18n.LANGS  # ("vi", "en")
APP_COLOR = "app_color"  # "#rrggbb", saved in lower case; no row, or any other text, = DEFAULT_APP_COLOR
DEFAULT_APP_COLOR = "#1f5c99"


def get_app_color(conn):
    """The app color the pastor picked (``#rrggbb``, lower case). No row, or a bad value, is the default."""
    try:
        return check_app_color(get_setting(conn, APP_COLOR))
    except ValueError:
        return DEFAULT_APP_COLOR


def check_app_color(value):
    """``"#1F5C99"`` -> ``"#1f5c99"``. Only text that is exactly ``#`` and 6 hex digits (no space, no
    short ``#fff``, no color name); anything else raises ``ValueError``."""
    if not isinstance(value, str) or app_color.HEX.fullmatch(value) is None:
        raise TextError("errors.app_color")
    return value.lower()


def hermes_door_on(conn):
    """True only when the Hermes door setting is exactly ``on``. No row, or any other text, is off."""
    return get_setting(conn, HERMES_DOOR) == "on"


def check_hermes_door(value):
    """Return ``value`` if it is ``on`` or ``off``, else raise ``ValueError``."""
    if value not in HERMES_DOOR_CHOICES:
        raise TextError("errors.hermes_door")
    return value


def get_language(conn):
    """The language of the screens: ``vi`` or ``en``. No row, or any other text, is ``vi``."""
    value = get_setting(conn, LANGUAGE)
    return value if value in LANGUAGE_CHOICES else i18n.DEFAULT_LANG


def check_language(value):
    """Return ``value`` if it is ``vi`` or ``en``, else raise ``ValueError``."""
    if value not in LANGUAGE_CHOICES:
        raise TextError("errors.language")
    return value


def get_setting(conn, key, default=None):
    """Return the setting text for ``key``, or ``default`` if it is not set."""
    row = conn.execute("SELECT value FROM setting WHERE key = ?", (key,)).fetchone()
    return default if row is None else row["value"]


def get_int_setting(conn, key, default):
    """Return the setting as a whole number, or ``default`` if it is missing or not a number."""
    value = get_setting(conn, key)
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def set_setting(conn, key, value):
    """Save a setting. The value is stored as NFC text."""
    key = text.clean_name(key, "Setting name")
    if key == HERMES_DOOR:
        check_hermes_door(value)  # exactly "on" or "off": no spaces, no other case, no None
    elif key == LANGUAGE:
        check_language(value)  # exactly "vi" or "en"
    elif key == APP_COLOR:
        value = check_app_color(value)  # exactly "#rrggbb", saved in lower case
    if value is None:
        raise TextError("errors.setting_value", name=key)
    value = text.nfc(str(value)).strip()
    if key == "church_name":
        value = text.clean_name(value, "settings.church_name")
    elif key == "care_reminder_months":
        if not value.isascii() or not value.isdigit() or not 1 <= int(value) <= 120:
            raise TextError("errors.care_reminder_months")
        value = str(int(value))
    conn.execute(
        "INSERT INTO setting (key, value) VALUES (?, ?) "
        "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
