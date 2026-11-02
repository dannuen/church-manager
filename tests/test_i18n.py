"""The text table (churchmgr/i18n.py), the language setting and the default list items in two languages."""

import contextlib
import io
import re
import string
import unittest

import _support
from _support import ROOT, temp_folder
from churchmgr import db, fake, i18n, lists, schema, settings, text
from churchmgr.i18n import TEXT, TextError, english_left, error_text, t, tn
from churchmgr.setup import new_church_setup


def params(template):
    return {name for _lit, name, _spec, _conv in string.Formatter().parse(template) if name is not None}


def keep_lang_getter(test, fn):
    """Use ``fn`` as the language getter for one test, then put back the one that was there."""
    test.addCleanup(i18n.set_lang_getter, i18n._lang_getter)
    i18n.set_lang_getter(fn)


class TextTableTest(unittest.TestCase):
    def test_same_keys_in_both_languages(self):
        self.assertEqual(tuple(TEXT), i18n.LANGS)
        self.assertEqual(list(TEXT["vi"]), list(TEXT["en"]))  # same keys, same order
        self.assertEqual(i18n.DEFAULT_LANG, "vi")

    def test_values(self):
        for lang in i18n.LANGS:
            for key, value in TEXT[lang].items():
                self.assertIsInstance(value, str, (lang, key))
                self.assertTrue(value.strip(), (lang, key))
                self.assertNotIn("[[", value, (lang, key))
        for key, en in TEXT["en"].items():
            self.assertEqual(params(TEXT["vi"][key]), params(en), key)

    def test_sections_in_order(self):
        for lang in i18n.LANGS:
            seen, per_section = [], {}
            for key in TEXT[lang]:
                section, dot, name = key.partition(".")
                self.assertTrue(dot and name, key)
                self.assertIn(section, i18n.SECTIONS, key)
                if not seen or seen[-1] != section:
                    seen.append(section)
                per_section[section] = per_section.get(section, 0) + 1
            self.assertEqual(seen, list(i18n.SECTIONS), lang)  # each section once, in order, none missing
            self.assertEqual([s for s, n in per_section.items() if n < 2], [], lang)
        self.assertEqual(len(i18n.SECTIONS), 16)
        source = (ROOT / "churchmgr" / "i18n.py").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^ *# --- (\w+)$", source, re.M), list(i18n.SECTIONS) * 2)

    def test_core_words_are_the_glossary_words(self):
        glossary = (ROOT / "GLOSSARY.md").read_text(encoding="utf-8").split("## Words on screen", 1)[1]
        table, group = {}, None
        for en, vi in re.findall(r"^\| (.+?) \| (.+?) \|$", glossary, re.M):
            if en.startswith("**"):
                group = en.strip("*")
            else:
                table[(group, en)] = vi
        prefixes = {"Family role": "core.family_role_", "Ministry role": "core.ministry_role_",
                    "Calendar item kind": "core.kind_", "Menu": "core.nav_", "Buttons": "core.btn_"}
        checked = 0
        for (group, en), vi in table.items():
            if group in prefixes:
                word = en.split(" (")[0]  # "Close (end a link)" -> "Close"
                keys = [k for k, v in TEXT["en"].items() if k.startswith(prefixes[group]) and v == word]
                self.assertEqual(len(keys), 1, (group, en, keys))
                self.assertEqual(TEXT["vi"][keys[0]], vi, keys[0])
                checked += 1
        self.assertEqual(checked, 4 + 2 + 4 + 12 + 9)
        groups = {"status": "Status", "ministry": "Ministry (default list)", "fund": "Fund (default list)",
                  "spending_category": "Spending category (default list)", "purpose": "Purpose (default list)"}
        for list_name, group in groups.items():
            for _code, vi, en in schema.DEFAULT_LISTS[list_name]:
                self.assertEqual(vi, table[(group, en)], (list_name, en))
        self.assertEqual([(vi, en) for _c, vi, en in schema.DEFAULT_LISTS["recipient"]],
                         [("Chính quyền",) * 2, ("Giáo hội",) * 2, ("Hội Thánh",) * 2])
        self.assertEqual((TEXT["vi"]["core.btn_delete"], TEXT["vi"]["core.nav_chi_phai"]), ("Xóa", "Chi phái"))

    def test_no_vietnamese_avoid_words(self):
        """No word of a "Tránh (tiếng Việt)" line, unless it is inside an approved word (Nghỉ nhóm, Thư mời)."""
        glossary = (ROOT / "GLOSSARY.md").read_text(encoding="utf-8")
        approved = re.findall(r"^_Tiếng Việt_: (.+)$", glossary, re.M)
        approved += [vi.strip("*") for vi in re.findall(r"^\| .+? \| (.+?) \|$", glossary, re.M)]
        avoid = [w.strip().lower() for line in re.findall(r"^_Tránh \(tiếng Việt\)_: (.+)$", glossary, re.M)
                 for w in re.sub(r"\([^)]*\)", "", line).split(",")]
        self.assertIn("thành viên", avoid)
        values = list(TEXT["vi"].values()) + [vi for items in schema.DEFAULT_LISTS.values() for _c, vi, _en in items]
        found = []
        for value in (v.lower() for v in values):
            ok = [m.span() for w in approved for m in re.finditer(re.escape(w.lower()), value)]
            found += [(value, w) for w in avoid for m in re.finditer(rf"(?<!\w){re.escape(w)}(?!\w)", value)
                      if not any(a <= m.start() and m.end() <= b for a, b in ok)]
        self.assertEqual(found, [])

    def test_t(self):
        self.assertEqual(t("core.btn_save", "vi"), "Lưu")
        self.assertEqual(t("core.btn_save", "en"), "Save")
        self.assertEqual(t("core.btn_save", "fr"), "Lưu")  # an unknown language: DEFAULT_LANG
        self.assertEqual(t("no.such_key", "en"), "[[no.such_key]]")
        self.assertEqual(t("no.such_key", "vi", label="x"), "[[no.such_key]]")
        self.assertEqual(t("errors.required", "en", label="Full name"), "Full name is required.")

    def test_lang_getter(self):
        keep_lang_getter(self, None)
        self.assertEqual(t("core.btn_save"), "Lưu")  # no getter: DEFAULT_LANG
        i18n.set_lang_getter(lambda: "en")
        self.assertEqual(t("core.btn_save"), "Save")
        self.assertEqual(tn("people.count", 2), "2 People")
        self.assertEqual(t("core.btn_save", "vi"), "Lưu")  # an explicit language wins
        i18n.set_lang_getter(lambda: None)
        self.assertEqual(t("core.btn_save"), "Lưu")

    def test_tn(self):
        self.assertEqual(tn("people.count", 1, "en"), "1 Person")
        self.assertEqual(tn("people.count", 0, "en"), "0 People")
        self.assertEqual(tn("people.count", 2, "en"), "2 People")
        self.assertEqual(tn("people.count", 1, "vi"), "1 người")
        self.assertEqual(tn("no.such", 1, "en"), "[[no.such_one]]")
        self.assertEqual(tn("no.such", 5, "en"), "[[no.such_many]]")


class TextErrorTest(unittest.TestCase):
    def test_key_label_is_translated(self):
        e = TextError("errors.required", label="settings.church_name")
        self.assertIsInstance(e, ValueError)
        self.assertEqual((e.key, e.params), ("errors.required", {"label": "settings.church_name"}))
        self.assertEqual(str(e), "Church name is required.")
        self.assertEqual(error_text(e, "en"), "Church name is required.")
        self.assertEqual(error_text(e, "vi"), "Cần nhập Tên Hội Thánh.")
        keep_lang_getter(self, lambda: "vi")
        self.assertEqual(error_text(e), "Cần nhập Tên Hội Thánh.")
        self.assertEqual(str(e), "Church name is required.")  # str() stays English on a Vietnamese page

    def test_plain_label_and_other_errors(self):
        e = TextError("errors.required", label="Full name")  # not a TEXT key: kept as it is
        self.assertEqual(str(e), "Full name is required.")
        self.assertEqual(error_text(e, "vi"), "Cần nhập Full name.")
        self.assertEqual(error_text(ValueError("Plain words."), "vi"), "Plain words.")

    def test_text_and_settings_errors_keep_their_english(self):
        cases = (
            (lambda: text.clean_name("   ", "Full name"), "Full name is required."),
            (lambda: text.clean_name(None), "Name is required."),
            (lambda: text.clean_name("x" * 121, "Full name"), "Full name: use at most 120 characters."),
            (lambda: text.check_date("2026-02-30"),
             "Date must be a real date written YYYY-MM-DD, for example 2026-05-31."),
            (lambda: text.check_date_years("1899-12-31"), "Date: use a year from 1900 to 9999."),
            (lambda: text.check_datetime("2026-05-31"),
             "Date and time must be written YYYY-MM-DD HH:MM, for example 2026-05-31 09:30."),
            (lambda: text.to_id(True, "Person"), "Person must be a whole number."),
            (lambda: text.to_id("abc", "Person"), "Person must be a whole number."),
            (lambda: text.to_id("0", "Family"), "Family must be a whole number above 0."),
            (lambda: text.to_id(str(text.MAX_ID + 1), "Person"), "No Person with that id."),
            (lambda: settings.check_hermes_door("maybe"), "Hermes door must be On or Off."),
            (lambda: settings.check_language("fr"), "Language must be Tiếng Việt or English."),
        )
        for fn, english in cases:
            with self.assertRaises(TextError) as ctx:
                fn()
            self.assertEqual(str(ctx.exception), english)
            self.assertTrue(ctx.exception.key.startswith("errors."), english)
            vi = error_text(ctx.exception, "vi")
            self.assertNotIn("[[", vi)
            self.assertNotEqual(vi, english)


class LanguageSettingTest(_support.CopyTestCase):
    LANG = "vi"

    def test_get_and_set_language(self):
        self.assertEqual(settings.get_language(self.conn), "vi")
        settings.set_setting(self.conn, settings.LANGUAGE, "en")
        self.assertEqual(settings.get_language(self.conn), "en")
        for bad in ("fr", "EN", " en", "", None, 1):
            with self.assertRaises(TextError, msg=repr(bad)):
                settings.set_setting(self.conn, settings.LANGUAGE, bad)
        self.assertEqual(settings.get_language(self.conn), "en")  # unchanged
        settings.set_setting(self.conn, settings.LANGUAGE, "vi")
        self.assertEqual(settings.get_language(self.conn), "vi")
        self.conn.execute("UPDATE setting SET value = 'fr' WHERE key = 'language'")  # a bad row (temp copy)
        self.assertEqual(settings.get_language(self.conn), "vi")
        self.conn.execute("DELETE FROM setting WHERE key = 'language'")  # no row
        self.assertEqual(settings.get_language(self.conn), "vi")

    def test_vietnamese_copy_has_vietnamese_items(self):
        self.assertEqual(settings.get_setting(self.conn, settings.LANGUAGE), "vi")
        for list_name, items in schema.DEFAULT_LISTS.items():
            self.assertEqual([(r["code"], r["name"]) for r in lists.get_list(self.conn, list_name)],
                             [(code, vi) for code, vi, _en in items], list_name)
        self.assertEqual(self.status("member"), self.item("status", name="Tín hữu"))

    def test_english_copy_and_a_bad_language(self):
        conn = db.create_church_copy(self.tmp / "en", "Hội Thánh B")  # default: en (old tests)
        self.addCleanup(conn.close)
        self.assertEqual(settings.get_language(conn), "en")
        self.assertEqual([r["name"] for r in lists.get_list(conn, "fund")], ["General", "Building", "Missions"])
        with self.assertRaises(TextError):
            db.create_church_copy(self.tmp / "fr", "Hội Thánh C", lang="fr")
        self.assertFalse((self.tmp / "fr").exists())

    def test_new_church_setup_is_vietnamese_by_default(self):
        root = self.tmp / "copies"
        for name, lang, funds in (("Hội Thánh A", None, ["Quỹ Hội Thánh", "Quỹ xây dựng", "Quỹ truyền giáo"]),
                                  ("Hội Thánh B", "en", ["General", "Building", "Missions"])):
            folder = new_church_setup(root, name) if lang is None else new_church_setup(root, name, lang)
            conn = db.open_church_copy(folder)
            try:
                self.assertEqual(settings.get_language(conn), lang or "vi")
                self.assertEqual([r["name"] for r in lists.get_list(conn, "fund")], funds)
            finally:
                conn.close()


class EnglishLeftTest(unittest.TestCase):
    def page(self, body, title="Trang chủ · Church Manager"):
        return ('<!doctype html>\n<html lang="vi">\n<head><meta charset="utf-8"><title>' + title + '</title>'
                '<script src="/static/app.js">var Save = 1;</script><style>.Save {}</style></head>\n'
                '<body><main>' + body + '</main></body>\n</html>\n')

    def test_finds_english_words(self):
        self.assertEqual(english_left(self.page("<p>Lưu</p>")), [])
        self.assertEqual(english_left(self.page("<p><button>Save</button> Lưu</p>")), ["Save"])
        self.assertEqual(english_left(self.page("<p>Lưu</p>", title="People · Hội Thánh")), ["People"])
        self.assertEqual(english_left(self.page('<p><span lang="vi">Save</span> Cancel</p>')), ["Cancel"])
        self.assertEqual(english_left(self.page('<div lang="vi"><p>Save</div> Cancel')), ["Cancel"])

    def test_leaves_out_lang_elements_attributes_and_the_app_name(self):
        body = ('<p lang="vi">Save</p><span lang="en">English Save <b>Cancel</b></span>'
                '<input value="Save" placeholder="Save" lang="vi"><br><a title="Save" href="/save">Lưu</a>'
                '<p>Church Manager</p><p>Chi phái · Cổng Hermes · 1.250.000 ₫ · 01/11/2026</p>')
        self.assertEqual(english_left(self.page(body)), [])

    def test_finds_markers(self):
        self.assertEqual(english_left(self.page("<p>[[x.y]]</p>")), ["[[x.y]]"])
        self.assertEqual(english_left(self.page('<p lang="vi">[[x.y]] Save</p>')), ["[[x.y]]"])


class FakeChurchLanguageTest(unittest.TestCase):
    def test_both_languages_build_the_same_church(self):
        tmp = temp_folder(self)
        counts, sums = {}, {}
        for lang in ("vi", "en"):
            got = fake.build_fake_church(tmp / lang, people=20, seed=3, today="2026-11-01", lang=lang)
            got.pop("folder")
            counts[lang] = got
            conn = db.open_church_copy(tmp / lang)
            try:
                self.assertEqual(settings.get_language(conn), lang)
                sums[lang] = conn.execute(
                    "SELECT li.sort_order, SUM(o.amount) FROM offering o JOIN list_item li ON li.id = o.fund_id "
                    "GROUP BY li.sort_order ORDER BY li.sort_order").fetchall()
                funds = {r[0] for r in conn.execute(
                    "SELECT DISTINCT li.name FROM offering o JOIN list_item li ON li.id = o.fund_id")}
            finally:
                conn.close()
            self.assertEqual(funds, {schema.default_name(item, lang) for item in schema.DEFAULT_LISTS["fund"]})
        self.assertEqual(counts["vi"], counts["en"])
        self.assertEqual([tuple(r) for r in sums["vi"]], [tuple(r) for r in sums["en"]])

    def test_command_line_lang(self):
        folder = temp_folder(self) / "vi"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(fake.main([str(folder), "--people", "20", "--today", "2026-11-01", "--lang", "vi"]), 0)
        conn = db.open_church_copy(folder)
        self.addCleanup(conn.close)
        self.assertEqual(settings.get_language(conn), "vi")


if __name__ == "__main__":
    unittest.main()
