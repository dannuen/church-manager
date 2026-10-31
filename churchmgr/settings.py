"""Settings of one church copy (table ``setting``): church_name, care_reminder_months."""

from . import text


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
    if value is None:
        raise ValueError(f"Setting {key} needs a value.")
    value = text.nfc(str(value)).strip()
    if key == "church_name":
        value = text.clean_name(value, "Church name")
    elif key == "care_reminder_months":
        if not value.isascii() or not value.isdigit() or not 1 <= int(value) <= 120:
            raise ValueError("Care reminder time must be a whole number of months from 1 to 120.")
        value = str(int(value))
    conn.execute(
        "INSERT INTO setting (key, value) VALUES (?, ?) "
        "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
