"""Settings of one church copy (table ``setting``): church_name, care_reminder_months, hermes_door,
language."""

from . import i18n, text
from .i18n import TextError

HERMES_DOOR = "hermes_door"  # "on" or "off"; no row = off (the default)
HERMES_DOOR_CHOICES = ("off", "on")
LANGUAGE = "language"  # "vi" or "en"; no row, or any other text, = "vi"
LANGUAGE_CHOICES = i18n.LANGS  # ("vi", "en")


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
