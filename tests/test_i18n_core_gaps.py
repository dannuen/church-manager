"""I18N-U8: the core gaps left after the screens got two languages.

- ``db.ChurchCopyError`` has a TEXT key (``errors.copy_*``): ``str()`` is the old English sentence (the
  agent and ``app.py`` read it), ``error_text(e, "vi")`` is Vietnamese, and the Copies page shows it in
  the language of the page.
- A Vietnamese page has ``<title lang="vi">``: the title holds names (pastor data). English pages keep
  a plain ``<title>``.
- One Vietnamese word for Plan a Visit.
- The history error shows dd/mm/yyyy dates in Vietnamese; ``str()`` keeps the ISO dates.

Real servers on 127.0.0.1 (port 0) over fake churches in temp folders, one Vietnamese and one English.
"""

import datetime as dt
import html
import pathlib
import re
import tempfile
import unittest

import _support
from churchmgr import care, db, fake, lists, people, schema, server
from churchmgr.i18n import TEXT, TextError, english_left, error_text
from test_i18n_copies import ScreensBase, Site

LANGS = ("vi", "en")
TODAY = dt.date.today()
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
NAME = "Mark Phạm Thu Mai"  # a Christian name first; "Mark" is also an English word of the text table (Mark done)
DATA = ("root", "folder", "path", "db", "detail", "mode")  # params shown as they are: paths, SQLite words


def old_english(key, p):
    """The English sentence of each error before it had a TEXT key (written like the old code)."""
    if key == "errors.copy_foreign_keys":
        return "SQLite foreign keys could not be turned on."
    if key == "errors.copy_journal_mode":
        return f"SQLite journal mode is {p['mode']}, expected delete."
    if key == "errors.copy_exists":
        return f"A church copy already exists in {p['folder']}. It was not changed."
    if key == "errors.copy_missing":
        return f"No church copy in {p['folder']}: {db.DB_NAME} is missing."
    if key == "errors.copy_not_database":
        return f"{p['path']} is not a Church Manager database ({p['detail']})."
    if key == "errors.copy_version":
        return f"{p['path']} has database version {p['version']}; this app needs version {schema.SCHEMA_VERSION}."
    where = "is the church copy folder itself" if key == "errors.copy_root_is_copy" else (
        f"is inside the church copy {p['folder']}")
    return (f"The copies folder {p['root']} {where}, so Handover zips and New church setups would be saved "
            "in the church copy: choose a copies folder outside it.")


def paragraph(exc, lang):
    """``error_text(exc, lang)`` in a ``<p>``, each data param (path, SQLite text) in a ``lang="zxx"`` span."""
    words = html.escape(error_text(exc, lang))
    for name in DATA:
        if name in exc.params:
            value = html.escape(str(exc.params[name]))
            words = words.replace(value, f'<span lang="zxx">{value}</span>')
    return f"<p>{words}</p>"


def shown(day):
    return day.strftime("%d/%m/%Y")


class CopyErrorTest(unittest.TestCase):
    def errors(self):
        """One ``ChurchCopyError`` of each key, made the way the app meets it."""
        tmp = _support.temp_folder(self)
        found = {}

        def catch(fn):
            with self.assertRaises(db.ChurchCopyError) as ctx:
                fn()
            self.assertNotIn(ctx.exception.key, found)
            found[ctx.exception.key] = ctx.exception

        copy = tmp / "copy"
        db.create_church_copy(copy, "Hội Thánh Thử").close()
        catch(lambda: db.create_church_copy(copy, "Hội Thánh Thử"))
        catch(lambda: db.open_church_copy(tmp / "empty"))
        (tmp / "broken").mkdir()
        (tmp / "broken" / db.DB_NAME).write_bytes(b"x" * 512)  # not SQLite
        catch(lambda: db.open_church_copy(tmp / "broken"))
        (tmp / "old").mkdir()
        (tmp / "old" / db.DB_NAME).write_bytes(b"")  # an empty SQLite file: version 0
        catch(lambda: db.open_church_copy(tmp / "old"))
        catch(lambda: server.make_server(copy, copy, 0, remember=False))
        catch(lambda: server.make_server(copy, copy / "backups", 0, remember=False))
        # SQLite settings that only a broken SQLite gives: made by hand.
        found["errors.copy_foreign_keys"] = db.ChurchCopyError("errors.copy_foreign_keys")
        found["errors.copy_journal_mode"] = db.ChurchCopyError("errors.copy_journal_mode", mode="wal")
        return found

    def test_every_copy_error_keeps_its_english_and_has_vietnamese(self):
        found = self.errors()
        self.assertEqual(sorted(found), sorted(k for k in TEXT["en"] if k.startswith("errors.copy_")
                                               and k != "errors.copy_plain"))
        for key, e in found.items():
            self.assertIsInstance(e, Exception, key)
            self.assertNotIsInstance(e, ValueError, key)  # the base is still Exception: every except as before
            self.assertEqual(str(e), old_english(key, e.params), key)
            self.assertEqual(e.args, (str(e),), key)
            self.assertEqual(error_text(e, "en"), str(e), key)
            vi = error_text(e, "vi")
            self.assertNotEqual(vi, str(e), key)
            self.assertNotIn("[[", vi, key)
            self.assertEqual(english_left(paragraph(e, "vi")), [], (key, vi))
            self.assertNotEqual(english_left(paragraph(e, "en")), [], key)  # the check is real
        p = found["errors.copy_missing"].params
        self.assertEqual(error_text(found["errors.copy_missing"], "vi"),
                         f"Không có Dữ liệu Hội Thánh trong {p['folder']}: thiếu church.db.")
        p = found["errors.copy_version"].params
        self.assertEqual(error_text(found["errors.copy_version"], "vi"),
                         f"{p['path']} là cơ sở dữ liệu bản 0; ứng dụng này cần bản {schema.SCHEMA_VERSION}.")
        self.assertEqual(found["errors.copy_not_database"].params["detail"], "file is not a database")

    def test_vietnamese_words(self):
        """The glossary words: "Dữ liệu Hội Thánh", "nơi lưu"; never "bản sao" or "thư mục"."""
        values = [v for k, v in TEXT["vi"].items() if k.startswith("errors.copy_")]
        self.assertTrue(all("bản sao" not in v and "thư" not in v.lower() for v in values))
        self.assertIn("Nơi lưu {folder} đã có Dữ liệu Hội Thánh.", TEXT["vi"]["errors.copy_exists"])

    def test_a_plain_sentence_is_kept_in_every_language(self):
        e = db.ChurchCopyError("Some plain words.")
        self.assertEqual((e.key, e.params, str(e)), ("errors.copy_plain", {"message": "Some plain words."},
                                                     "Some plain words."))
        self.assertEqual(error_text(e, "vi"), "Some plain words.")

    def test_error_text_reads_any_error_with_a_text_key(self):
        class Other(Exception):
            def __init__(self, key, params):
                super().__init__("English words.")
                self.key, self.params = key, params

        def vi(key, params):
            return error_text(Other(key, params), "vi")

        self.assertEqual(vi("errors.copy_missing", {"folder": "D:/x", "db": "church.db"}),
                         "Không có Dữ liệu Hội Thánh trong D:/x: thiếu church.db.")
        self.assertEqual(vi("errors.required", {"label": "settings.church_name"}),  # a key param: put in vi too
                         "Cần nhập Tên Hội Thánh.")
        self.assertEqual(vi("no.such_key", {}), "English words.")  # not a TEXT key: str()
        self.assertEqual(vi("errors.copy_missing", None), "English words.")  # no params dict: str()
        self.assertEqual(error_text(KeyError("k"), "vi"), "'k'")


class CoreGapsScreensTest(ScreensBase):
    """Per language: a fake church, a folder with an empty ``church.db`` (version 0) and a folder with a
    ``church.db`` that is not SQLite, in the same copies root. A Person whose name holds an English word
    (``NAME``) has a planned Visit."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        base = pathlib.Path(cls.tmp.name)
        assert "onedrive" not in str(base.resolve()).lower()
        cls.roots, cls.sites, cls.persons, cls.visits, cls.plain = {}, {}, {}, {}, {}
        cls.member, cls.attender = {}, {}
        for lang in LANGS:
            root = base / lang
            copy = root / "fake"
            fake.build_fake_church(copy, people=20, lang=lang)
            (root / "old").mkdir()
            (root / "old" / db.DB_NAME).write_bytes(b"")
            (root / "broken").mkdir()
            (root / "broken" / db.DB_NAME).write_bytes(b"x" * 512)
            conn = db.open_church_copy(copy)
            try:
                cls.persons[lang] = people.add_person(conn, NAME)
                cls.visits[lang] = care.plan_visit(conn, f"{TODAY + dt.timedelta(days=1)} 10:00",
                                                   person_id=cls.persons[lang])
                cls.plain[lang] = people.add_person(conn, "Lê Văn Cường")  # no Visit: no story line with NAME
                cls.member[lang] = lists.find_item(conn, "status", code="member")["id"]
                cls.attender[lang] = lists.find_item(conn, "status", code="attender")["id"]
            finally:
                conn.close()
            httpd = server.make_server(copy, root, 0, remember=False)
            server.serve_in_thread(httpd)
            cls.roots[lang], cls.sites[lang] = root, Site(httpd)

    @classmethod
    def tearDownClass(cls):
        for site in cls.sites.values():
            site.httpd.shutdown()
            site.httpd.server_close()
        cls.tmp.cleanup()

    def test_open_a_folder_that_is_not_a_church_copy(self):
        for lang in LANGS:
            for folder, key in (("old", "errors.copy_version"), ("broken", "errors.copy_not_database")):
                where = (lang, folder)
                page = self.post(lang, "/copies/open", {"folder": folder}, 400)[1]
                with self.assertRaises(db.ChurchCopyError) as ctx:
                    db.open_church_copy(self.roots[lang] / folder)
                e = ctx.exception
                self.assertEqual(e.key, key, where)
                self.assertIn(f'<p class="error" role="alert">{html.escape(error_text(e, lang))}</p>', page, where)
                if lang == "en":
                    self.assertIn(html.escape(old_english(key, e.params)), page, where)
                    self.assert_screen(lang, page, where)
                    continue
                for name in ("path", "detail"):  # data: the path, and the SQLite words (English, from SQLite)
                    if name in e.params:
                        page = page.replace(html.escape(str(e.params[name])), "")
                self.assert_screen(lang, page, where)

    def test_a_visit_title_with_a_name(self):
        vi_page = self.get("vi", f"/calendar/{self.visits['vi']}")
        self.assertIn(f'<title lang="vi">Thăm viếng {NAME} · ', vi_page)
        self.assert_screen("vi", vi_page, "Visit page")
        # The check is real: with a plain <title> it finds "Mark" in the name.
        self.assertEqual(english_left(vi_page.replace('<title lang="vi">', "<title>")), ["Mark"])
        en_page = self.get("en", f"/calendar/{self.visits['en']}")
        self.assertIn(f"<title>Visit {NAME} · ", en_page)
        self.assertNotIn("<title lang", en_page)
        for path in ("/", "/people", f"/people/{self.persons['vi']}", "/calendar", "/copies", "/nope"):
            expect = 404 if path == "/nope" else 200
            self.assertEqual(self.get("vi", path, expect).count('<title lang="vi">'), 1, path)
            page = self.get("en", path if path != f"/people/{self.persons['vi']}" else
                            f"/people/{self.persons['en']}", expect)
            self.assertEqual((page.count("<title>"), page.count("<title lang")), (1, 0), path)

    def test_plan_a_visit_is_one_word(self):
        words = {TEXT["vi"][k] for k in ("people.plan_visit", "care.plan_visit", "dashboard.plan_visit")}
        self.assertEqual(words, {"Lên lịch Thăm viếng"})
        page = self.get("vi", f"/people/{self.persons['vi']}")
        self.assertIn(">Lên lịch Thăm viếng</a>", page)
        self.assertNotIn("kế hoạch", page)

    def test_history_error_on_a_vietnamese_page(self):
        pid, member, attender = self.plain["vi"], self.member["vi"], self.attender["vi"]
        self.post("vi", f"/people/{pid}/status", {"status_id": member, "start_date": TODAY.isoformat()})
        early = TODAY - dt.timedelta(days=5)
        page = self.post("vi", f"/people/{pid}/status", {"status_id": attender, "start_date": early.isoformat()},
                         400)[1]
        m = re.search(r'<p class="error" id="status-date-error">([^<]*)</p>', page)
        assert m is not None, page[-3000:]
        self.assertEqual(m.group(1), f"Ngày bắt đầu {shown(early)} sớm hơn {shown(TODAY)}, ngày của lần thay đổi "
                                     "gần nhất. Những gì đã qua không bao giờ bị viết lại; hãy dùng ngày "
                                     f"{shown(TODAY)} hoặc sau đó.")
        self.assertNotRegex(m.group(1), ISO_DATE)
        self.assert_screen("vi", page, "status before the last change")


class HistoryErrorTest(_support.CopyTestCase):
    LANG = "vi"

    def test_dates_in_the_words_of_each_language(self):
        pid = people.add_person(self.conn, "Lê Văn Cường")
        people.set_status(self.conn, pid, self.status("member"), "2026-01-10")
        with self.assertRaises(TextError) as ctx:
            people.set_status(self.conn, pid, self.status("attender"), "2026-01-01")
        e = ctx.exception
        self.assertEqual(str(e), "Start date 2026-01-01 is before 2026-01-10, the date of the last change. "
                                 "History is never rewritten; use a date on or after it.")
        self.assertEqual(error_text(e, "en"), str(e))
        vi = error_text(e, "vi")
        self.assertEqual(vi, "Ngày bắt đầu 01/01/2026 sớm hơn 10/01/2026, ngày của lần thay đổi gần nhất. Những gì "
                             "đã qua không bao giờ bị viết lại; hãy dùng ngày 10/01/2026 hoặc sau đó.")
        self.assertNotRegex(vi, ISO_DATE)

    def test_every_history_line_uses_it(self):
        """Trưởng Chi phái too (the same shared code): a start date before the last change."""
        cid = people.add_chi_phai(self.conn, "Chi phái Hòa Bình")
        a, b = people.add_person(self.conn, "Nguyễn Văn An"), people.add_person(self.conn, "Trần Thị Bình")
        people.set_truong_chi_phai(self.conn, cid, a, "2026-03-01")
        with self.assertRaises(TextError) as ctx:
            people.set_truong_chi_phai(self.conn, cid, b, "2026-02-28")
        self.assertEqual(ctx.exception.key, "people.err_history")
        self.assertIn("2026-02-28 is before 2026-03-01", str(ctx.exception))
        self.assertTrue(error_text(ctx.exception, "vi").startswith("Ngày bắt đầu 28/02/2026 sớm hơn 01/03/2026,"))


if __name__ == "__main__":
    unittest.main()
