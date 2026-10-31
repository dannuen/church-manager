"""Find a Person by name. Vietnamese works with or without diacritics."""

from . import text


def _like_escape(token):
    return token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_persons(conn, q, limit=20):
    """Persons whose folded name holds every word of ``q`` (any order).

    "nguyen hai dang", "Nguyễn Hải Đăng" and "dang nguyen" all find
    "Nguyễn Hải Đăng". Rows: id, full_name, status_name (current Status or
    ``None``), name_folded. Whole-word matches come first, then by given name.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a whole number above 0.")
    tokens = text.fold(q).split()
    if not tokens:
        return []
    where = " AND ".join(["p.name_folded LIKE ? ESCAPE '\\'"] * len(tokens))
    rows = conn.execute(
        "SELECT p.id, p.full_name, li.name AS status_name, p.name_folded "
        "FROM person p "
        "LEFT JOIN person_status ps ON ps.person_id = p.id AND ps.end_date IS NULL "
        "LEFT JOIN list_item li ON li.id = ps.status_id "
        f"WHERE {where}",
        [f"%{_like_escape(t)}%" for t in tokens],
    ).fetchall()

    def rank(row):
        words = row["name_folded"].split()
        if all(t in words for t in tokens):
            level = 0
        elif all(any(w.startswith(t) for w in words) for t in tokens):
            level = 1
        else:
            level = 2
        return (level, words[-1] if words else "", row["name_folded"], row["full_name"], row["id"])

    return sorted(rows, key=rank)[:limit]
