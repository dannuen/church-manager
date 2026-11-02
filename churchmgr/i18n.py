"""The words on screen in Tiếng Việt and English (the text table), and errors the pastor can read.

- Every key is ``<section>.<name>``. The 16 sections come in the order of ``SECTIONS``, in both
  dicts, each one after a ``# --- <section>`` line. Shared words (menu, buttons, roles, kinds,
  weekdays, months) live in ``core``.
- MERGE RULE: a card adds keys ONLY in its own sections, in BOTH dicts, directly after the
  ``# --- <section>`` line. Never reorder, rename or delete other keys.
- The English text is the text the app showed before it had two languages.
- Data is never translated: names, notes, titles and list items are shown as stored.
- This module imports nothing from ``churchmgr``.
"""

import re
from html.parser import HTMLParser

LANGS = ("vi", "en")
DEFAULT_LANG = "vi"
SECTIONS = ("core", "dashboard", "people", "families", "chi_phai", "calendar", "care", "money", "documents",
            "sent", "lists", "copies", "settings", "setup", "search", "errors")

TEXT = {
    "vi": {
        # --- core
        "core.nav_dashboard": "Trang chủ",
        "core.nav_people": "Mọi người",
        "core.nav_families": "Gia đình",
        "core.nav_chi_phai": "Chi phái",
        "core.nav_calendar": "Lịch",
        "core.nav_care": "Thăm viếng",
        "core.nav_money": "Tài chính",
        "core.nav_documents": "Tài liệu",
        "core.nav_sent": "Văn bản đi",
        "core.nav_lists": "Danh mục",
        "core.nav_copies": "Dữ liệu",
        "core.nav_settings": "Cài đặt",
        "core.nav_search": "Tìm kiếm",
        "core.btn_add": "Thêm",
        "core.btn_save": "Lưu",
        "core.btn_edit": "Chỉnh sửa",
        "core.btn_cancel": "Hủy",
        "core.btn_print": "In",
        "core.btn_back": "Quay lại",
        "core.btn_open": "Mở",
        "core.btn_close": "Kết thúc",
        "core.btn_mark_done": "Hoàn tất",
        "core.btn_search": "Tìm kiếm",
        "core.btn_delete": "Xóa",
        "core.family_role_head": "Chủ gia đình",
        "core.family_role_spouse": "Vợ/Chồng",
        "core.family_role_child": "Con",
        "core.family_role_other": "Người thân khác",
        "core.ministry_role_leader": "Trưởng ban",
        "core.ministry_role_member": "Ban viên",
        "core.kind_service": "Giờ thờ phượng",
        "core.kind_meeting": "Buổi họp",
        "core.kind_visit": "Thăm viếng",
        "core.kind_event": "Chương trình",
        "core.weekday_0": "Thứ Hai",
        "core.weekday_1": "Thứ Ba",
        "core.weekday_2": "Thứ Tư",
        "core.weekday_3": "Thứ Năm",
        "core.weekday_4": "Thứ Sáu",
        "core.weekday_5": "Thứ Bảy",
        "core.weekday_6": "Chúa Nhật",
        "core.month_1": "Tháng 1",
        "core.month_2": "Tháng 2",
        "core.month_3": "Tháng 3",
        "core.month_4": "Tháng 4",
        "core.month_5": "Tháng 5",
        "core.month_6": "Tháng 6",
        "core.month_7": "Tháng 7",
        "core.month_8": "Tháng 8",
        "core.month_9": "Tháng 9",
        "core.month_10": "Tháng 10",
        "core.month_11": "Tháng 11",
        "core.month_12": "Tháng 12",
        # --- dashboard
        "dashboard.title": "Trang chủ",
        "dashboard.open_calendar": "Mở Lịch",
        # --- people
        "people.title": "Mọi người",
        "people.add": "Thêm Người",
        "people.count_one": "{n} người",
        "people.count_many": "{n} người",
        # --- families
        "families.title": "Gia đình",
        "families.add": "Thêm Gia đình",
        # --- chi_phai
        "chi_phai.title": "Chi phái",
        "chi_phai.add": "Thêm Chi phái",
        # --- calendar
        "calendar.title": "Lịch",
        "calendar.add": "Thêm Lịch",
        # --- care
        "care.title": "Thăm viếng",
        "care.needs_visit": "Cần thăm viếng",
        "care.care_log": "Nhật ký thăm viếng",
        # --- money
        "money.title": "Tài chính",
        "money.offerings": "Dâng hiến",
        "money.expenses": "Khoản chi",
        "money.giving_statement": "Tổng kết dâng hiến",
        # --- documents
        "documents.title": "Tài liệu",
        "documents.add": "Thêm Tài liệu",
        # --- sent
        "sent.title": "Văn bản đi",
        "sent.add": "Thêm Công văn đi",
        # --- lists
        "lists.title": "Danh mục",
        "lists.status": "Trạng thái",
        # --- copies
        "copies.title": "Dữ liệu",
        "copies.handover": "Bàn giao",
        # --- settings
        "settings.title": "Cài đặt",
        "settings.church_name": "Tên Hội Thánh",
        "settings.hermes_door": "Cổng Hermes",
        "settings.save": "Lưu cài đặt",
        # --- setup
        "setup.title": "Lập dữ liệu Hội Thánh mới",
        "setup.done": "Đã lập dữ liệu Hội Thánh mới. Đây là Trang chủ.",
        # --- search
        "search.title": "Tìm kiếm",
        "search.find_person": "Tìm Người",
        # --- errors
        "errors.required": "Cần nhập {label}.",
        "errors.name_too_long": "{label}: tối đa {max} ký tự.",
        "errors.date": "{label} phải là một ngày có thật, viết YYYY-MM-DD, ví dụ 2026-05-31.",
        "errors.date_years": "{label}: năm phải từ 1900 đến 9999.",
        "errors.datetime": "{label} phải viết YYYY-MM-DD HH:MM, ví dụ 2026-05-31 09:30.",
        "errors.whole_number": "{label} phải là số nguyên.",
        "errors.above_zero": "{label} phải là số nguyên lớn hơn 0.",
        "errors.no_such_id": "Không có {label} với mã số đó.",
        "errors.hermes_door": "Cổng Hermes phải là Bật hoặc Tắt.",
        "errors.setting_value": "Cài đặt {name} cần có giá trị.",
        "errors.care_reminder_months": "Nhắc thăm viếng phải là số tháng nguyên từ 1 đến 120.",
        "errors.language": "Ngôn ngữ phải là Tiếng Việt hoặc English.",
    },
    "en": {
        # --- core
        "core.nav_dashboard": "Dashboard",
        "core.nav_people": "People",
        "core.nav_families": "Families",
        "core.nav_chi_phai": "Chi phái",
        "core.nav_calendar": "Calendar",
        "core.nav_care": "Care",
        "core.nav_money": "Money",
        "core.nav_documents": "Documents",
        "core.nav_sent": "Sent documents",
        "core.nav_lists": "Lists",
        "core.nav_copies": "Copies",
        "core.nav_settings": "Settings",
        "core.nav_search": "Search",
        "core.btn_add": "Add",
        "core.btn_save": "Save",
        "core.btn_edit": "Edit",
        "core.btn_cancel": "Cancel",
        "core.btn_print": "Print",
        "core.btn_back": "Back",
        "core.btn_open": "Open",
        "core.btn_close": "Close",
        "core.btn_mark_done": "Mark done",
        "core.btn_search": "Search",
        "core.btn_delete": "Delete",
        "core.family_role_head": "Head",
        "core.family_role_spouse": "Spouse",
        "core.family_role_child": "Child",
        "core.family_role_other": "Other",
        "core.ministry_role_leader": "Leader",
        "core.ministry_role_member": "Member",
        "core.kind_service": "Service",
        "core.kind_meeting": "Meeting",
        "core.kind_visit": "Visit",
        "core.kind_event": "Event",
        "core.weekday_0": "Mon",
        "core.weekday_1": "Tue",
        "core.weekday_2": "Wed",
        "core.weekday_3": "Thu",
        "core.weekday_4": "Fri",
        "core.weekday_5": "Sat",
        "core.weekday_6": "Sun",
        "core.month_1": "January",
        "core.month_2": "February",
        "core.month_3": "March",
        "core.month_4": "April",
        "core.month_5": "May",
        "core.month_6": "June",
        "core.month_7": "July",
        "core.month_8": "August",
        "core.month_9": "September",
        "core.month_10": "October",
        "core.month_11": "November",
        "core.month_12": "December",
        # --- dashboard
        "dashboard.title": "Dashboard",
        "dashboard.open_calendar": "Open Calendar",
        # --- people
        "people.title": "People",
        "people.add": "Add a Person",
        "people.count_one": "{n} Person",
        "people.count_many": "{n} People",
        # --- families
        "families.title": "Families",
        "families.add": "Add a Family",
        # --- chi_phai
        "chi_phai.title": "Chi phái",
        "chi_phai.add": "Add a Chi phái",
        # --- calendar
        "calendar.title": "Calendar",
        "calendar.add": "Add a Calendar item",
        # --- care
        "care.title": "Care",
        "care.needs_visit": "Needs a visit",
        "care.care_log": "Care log",
        # --- money
        "money.title": "Money",
        "money.offerings": "Offerings",
        "money.expenses": "Expenses",
        "money.giving_statement": "Giving statement",
        # --- documents
        "documents.title": "Documents",
        "documents.add": "Add document",
        # --- sent
        "sent.title": "Sent documents",
        "sent.add": "Record a Sent document",
        # --- lists
        "lists.title": "Lists",
        "lists.status": "Status",
        # --- copies
        "copies.title": "Copies",
        "copies.handover": "Handover",
        # --- settings
        "settings.title": "Settings",
        "settings.church_name": "Church name",
        "settings.hermes_door": "Hermes door",
        "settings.save": "Save settings",
        # --- setup
        "setup.title": "New church setup",
        "setup.done": "New church setup is done. This is your Dashboard.",
        # --- search
        "search.title": "Search",
        "search.find_person": "Find a Person",
        # --- errors
        "errors.required": "{label} is required.",
        "errors.name_too_long": "{label}: use at most {max} characters.",
        "errors.date": "{label} must be a real date written YYYY-MM-DD, for example 2026-05-31.",
        "errors.date_years": "{label}: use a year from 1900 to 9999.",
        "errors.datetime": "{label} must be written YYYY-MM-DD HH:MM, for example 2026-05-31 09:30.",
        "errors.whole_number": "{label} must be a whole number.",
        "errors.above_zero": "{label} must be a whole number above 0.",
        "errors.no_such_id": "No {label} with that id.",
        "errors.hermes_door": "Hermes door must be On or Off.",
        "errors.setting_value": "Setting {name} needs a value.",
        "errors.care_reminder_months": "Care reminder time must be a whole number of months from 1 to 120.",
        "errors.language": "Language must be Tiếng Việt or English.",
    },
}


def _default_lang():
    return DEFAULT_LANG


_lang_getter = _default_lang


def set_lang_getter(fn):
    """``ui.py`` registers ``fn()``: the language of the current request. ``None`` goes back to
    ``DEFAULT_LANG``."""
    global _lang_getter
    _lang_getter = fn or _default_lang


def _lang(lang):
    if lang is None:
        lang = _lang_getter()
    return lang if lang in LANGS else DEFAULT_LANG


def t(key, lang=None, **params):
    """The text of ``key`` in ``lang`` (``None``: the language of the current request), with
    ``params`` filled in. A missing key gives ``[[key]]``, so it is easy to see on the page."""
    template = TEXT[_lang(lang)].get(key)
    if template is None:
        return f"[[{key}]]"
    return template.format(**params)


def tn(key, n, lang=None, **params):
    """``t(key + "_one")`` when ``n == 1``, else ``t(key + "_many")``; ``{n}`` is ``n``."""
    return t(f"{key}_{'one' if n == 1 else 'many'}", lang, n=n, **params)


class TextError(ValueError):
    """An error the pastor can read: ``TextError("errors.required", label="settings.church_name")``.

    ``str(e)`` is the English text (the agent and the logs read it); pages show ``error_text(e)``.
    """

    def __init__(self, key, **params):
        self.key, self.params = key, params
        super().__init__(error_text(self, "en"))


def error_text(exc, lang=None):
    """The text of an error in ``lang``. For a ``TextError`` every param that is a TEXT key (such
    as a field label) is first put in that language too. Any other error: ``str(exc)``."""
    if not isinstance(exc, TextError):
        return str(exc)
    lang = _lang(lang)
    params = {k: t(v, lang) if isinstance(v, str) and v in TEXT[lang] else v for k, v in exc.params.items()}
    return t(exc.key, lang, **params)


# ---------------------------------------------------------------- English left on a page

ALLOW = frozenset({"hermes", "email", "pdf", "ok", "sqlite"})
_WORD = re.compile(r"[^\W\d_]+")
_PARAM = re.compile(r"\{[^{}]*\}")
_MARKER = re.compile(r"\[\[[^\[\]]*\]\]")
_VOID = frozenset({"base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track",
                   "wbr"})  # HTML tags with no end tag


def _ascii_words(values):
    return {w.lower() for v in values for w in _WORD.findall(_PARAM.sub(" ", v)) if w.isascii() and len(w) >= 3}


def english_words():
    """ASCII words (3 or more characters, lower case) of the English text, minus the Vietnamese and ``ALLOW``."""
    return _ascii_words(TEXT["en"].values()) - _ascii_words(TEXT["vi"].values()) - ALLOW


class _Visible(HTMLParser):
    """Collects the visible text: no ``<script>``/``<style>``, no attribute value, nothing inside an
    element with its own ``lang`` (pastor data, the "English" switch button). ``<html lang>`` counts
    as no ``lang``: it is the page language."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.open, self.hidden = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in _VOID:
            return
        hide = tag in ("script", "style") or (tag != "html" and any(k == "lang" for k, _v in attrs))
        self.open.append((tag, hide))
        self.hidden += hide

    def handle_endtag(self, tag):
        for i in range(len(self.open) - 1, -1, -1):
            if self.open[i][0] == tag:  # closes the tags left open inside it too
                self.hidden -= sum(hide for _t, hide in self.open[i:])
                del self.open[i:]
                return

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def english_left(page_html):
    """Problems on a Vietnamese page, sorted: every ``[[key]]`` marker, and every English word in
    the visible text (``<title>`` and body). The phrase "Church Manager" is left out."""
    parser = _Visible()
    parser.feed(page_html)
    parser.close()
    visible = "\n".join(parser.parts).replace("Church Manager", " ")
    english = english_words()
    found = set(_MARKER.findall(page_html))
    found.update(w for w in _WORD.findall(visible) if w.isascii() and w.lower() in english)
    return sorted(found)
