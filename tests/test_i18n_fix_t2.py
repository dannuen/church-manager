"""I18N-FIX-T r2: two fixes the tester asked for.

L4: a file over the limit is stopped in the browser, before it is sent. The file ``<input>`` of the Add
document form (Person, Family, Calendar item) and of the Record form of a Sent document carries the limit
(``data-max-bytes``) and the sentence of ``documents.err_too_large`` in the language of the page
(``data-text-too-large``). ``web/app.js`` reads them and sets the message with ``setCustomValidity``: the
browser then refuses to send the form. Without JavaScript a body over ``server.MAX_BODY`` (60 MB) still gets
the plain 413 of the server (known limit). A file between 50 MB and 60 MB still gets the app message.
L5: the Delete Family question and its flash say the Family name once: the name already holds "Gia đình".

Real servers on 127.0.0.1 (port 0) over fake churches in temp folders, one in Tiếng Việt, one in English.
"""

import html
import pathlib
import re
import tempfile
import unittest
from html.parser import HTMLParser

import _support
from churchmgr import db, documents, fake, people
from churchmgr.i18n import TEXT, english_left
from test_i18n_core import html_lang, switch
from test_pages_documents import multipart
from test_server import LiveServer

ROOT = pathlib.Path(_support.ROOT)
LIMIT = 50 * 1024 * 1024
TOO_LARGE = {"vi": "Tệp quá lớn. Giới hạn là 50 MB.", "en": "The file is too large. The limit is 50 MB."}
NEW_FAMILY = "Gia đình Xóa Thử"
QUESTION = {"vi": f"Xóa {NEW_FAMILY}?", "en": f"Delete {NEW_FAMILY}?"}
DELETED = {"vi": f"Đã xóa {NEW_FAMILY}.", "en": f"{NEW_FAMILY} deleted."}
TITLE = {"vi": "Xóa Gia đình này?", "en": "Delete this Family?"}
TAGS = re.compile(r"<[^>]+>")


class _FileInputs(HTMLParser):
    """The attributes (values unescaped) of every ``<input type="file">`` of a page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "input" and a.get("type") == "file":
            self.found.append(a)


def file_inputs(page):
    parser = _FileInputs()
    parser.feed(page)
    parser.close()
    return parser.found


def visible(fragment):
    return html.unescape(TAGS.sub("", fragment))


def lead(page):
    m = re.search(r'<p class="lead">(.*?)</p>', page, re.S)
    return visible(m.group(1)) if m else None


def heading(page):
    m = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
    return visible(m.group(1)).strip() if m else None


def flash(page):
    m = re.search(r'<p class="flash" role="status">([^<]*)</p>', page)
    return html.unescape(m.group(1)) if m else None


def field_error(page, field_id):
    m = re.search(rf'<p class="error" id="{re.escape(field_id)}">([^<]*)</p>', page)
    return html.unescape(m.group(1)) if m else None


class _Screens(LiveServer, unittest.TestCase):
    """One fake church in ``LANG`` and one live server per test class. Deleted at the end of this file:
    only its two subclasses (Tiếng Việt, English) run."""

    LANG = "vi"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        root = pathlib.Path(cls.tmp.name)
        assert "onedrive" not in str(root.resolve()).lower(), "temp folder must be outside OneDrive"
        cls.copy = root / "fake"
        fake.build_fake_church(cls.copy, people=20, lang=cls.LANG)
        conn = db.connect(cls.copy / db.DB_NAME)
        try:
            one = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
            cls.ids = {"person": one("SELECT id FROM person ORDER BY id LIMIT 1"),
                       "family": one("SELECT id FROM family ORDER BY id LIMIT 1"),
                       "item": one("SELECT id FROM calendar_item ORDER BY id LIMIT 1")}
        finally:
            conn.close()
        cls.start(cls.copy, root, remember=False)

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.tmp.cleanup()

    def db(self):
        conn = db.connect(self.copy / db.DB_NAME)
        self.addCleanup(conn.close)
        return conn

    def page(self, path, expect=200):
        status, _h, page = self.get_text(path)
        self.assertEqual(status, expect, path)
        return page

    def post(self, path, form, expect=303):
        status, headers, data = self.request("POST", path, form)
        self.assertEqual(status, expect, data.decode("utf-8", "replace")[:1500])
        return headers, data.decode("utf-8")

    def check_page(self, page, path):
        """The page is in ``LANG``, with the switch, no ``[[key]]``, and (Tiếng Việt) no English word."""
        self.assertEqual(html_lang(page), self.LANG, path)
        self.assertEqual(switch(page)[1:], ("true", "false") if self.LANG == "vi" else ("false", "true"), path)
        self.assertNotIn("[[", page, path)
        if self.LANG == "vi":
            self.assertEqual(english_left(page), [], path)

    # ---- L4
    def test_file_inputs_carry_the_limit_and_its_sentence(self):
        i = self.ids
        paths = (f"/people/{i['person']}", f"/families/{i['family']}", f"/calendar/{i['item']}", "/sent/new",
                 f"/documents/new?person_id={i['person']}")
        for path in paths:
            page = self.page(path)
            self.check_page(page, path)
            inputs = file_inputs(page)
            self.assertEqual(len(inputs), 1, path)
            self.assertEqual(inputs[0].get("data-max-bytes"), "52428800", path)
            self.assertEqual(inputs[0].get("data-text-too-large"), TOO_LARGE[self.LANG], path)
        self.assertEqual(documents.MAX_SIZE, LIMIT)  # the server rule did not move

    def test_the_sentence_is_the_one_of_documents_err_too_large(self):
        self.assertEqual(TEXT[self.LANG]["documents.err_too_large"].format(mb=50), TOO_LARGE[self.LANG])

    def test_app_js_sets_the_message_from_the_page(self):
        status, headers, data = self.request("GET", "/static/app.js")
        self.assertEqual(status, 200)
        self.assertIn("text/javascript", headers["content-type"])
        js = data.decode("utf-8")
        self.assertEqual(js.encode("utf-8"), (ROOT / "web" / "app.js").read_bytes())
        code = re.sub(r"^\s*//.*$", "", js, flags=re.M)  # the comments may speak English
        for part in ('"use strict"', "input[type=file][data-max-bytes]", 'getAttribute("data-max-bytes")',
                     'getAttribute("data-text-too-large")', "setCustomValidity(", "reportValidity()",
                     'addEventListener("change", check)', "input.files", ".size"):
            self.assertIn(part, code)
        self.assertNotIn("innerHTML", code)
        self.assertNotIn(".innerHTML", js)
        for words in TOO_LARGE.values():
            self.assertNotIn(words, js)
        sentences = [s for s in re.findall(r'"([^"\\]*)"', code) if " " in s.strip() and s != "use strict"]
        self.assertEqual(sentences, [])  # no sentence in the script: the page gives them

    def test_a_55_mb_file_still_gets_the_app_message(self):
        """Over 50 MB, under the 60 MB of the server: the server reads it and the page says why (400)."""
        pid = self.ids["person"]
        before = self.db().execute("SELECT COUNT(*) FROM document").fetchone()[0]
        body, ctype = multipart({"person_id": pid}, {"file": ("lớn.bin", b"x" * (55 * 1024 * 1024))})
        status, _h, data = self.request("POST", "/documents/new", body, headers={"Content-Type": ctype})
        page = data.decode("utf-8")
        self.assertEqual(status, 400, page[:1500])
        self.check_page(page, "/documents/new")
        self.assertEqual(field_error(page, f"doc-file-{pid}-error"), TOO_LARGE[self.LANG])
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM document").fetchone()[0], before)

    # ---- L5
    def add_new_family(self):
        headers, _page = self.post("/families/new", {"name": NEW_FAMILY, "address": ""})
        m = re.match(r"/families/(\d+)", headers["location"])
        assert m is not None, headers["location"]
        fid = int(m.group(1))
        self.assertEqual(people.get_family(self.db(), fid)["name"], NEW_FAMILY)
        return fid

    def test_delete_family_says_gia_dinh_once(self):
        fid = self.add_new_family()
        _h, page = self.post(f"/families/{fid}/delete", {}, expect=200)
        self.check_page(page, "delete question")
        self.assertEqual(heading(page), TITLE[self.LANG])
        self.assertEqual(lead(page), QUESTION[self.LANG])
        self.assertNotIn("Gia đình Gia đình", visible(page))
        self.assertNotIn("Family Gia đình", visible(page))
        headers, _p = self.post(f"/families/{fid}/delete", {"confirm": "yes"})
        page = self.page(headers["location"])
        self.check_page(page, headers["location"])
        self.assertEqual(flash(page), DELETED[self.LANG])
        self.assertNotIn("Gia đình Gia đình", visible(page))
        self.assertIsNone(self.db().execute("SELECT id FROM family WHERE id = ?", (fid,)).fetchone())

    def test_the_two_values_are_the_decided_ones(self):
        self.assertEqual(TEXT[self.LANG]["families.confirm"].format(name=NEW_FAMILY), QUESTION[self.LANG])
        self.assertEqual(TEXT[self.LANG]["families.deleted"].format(name=NEW_FAMILY), DELETED[self.LANG])
        self.assertEqual(TEXT[self.LANG]["families.confirm_title"], TITLE[self.LANG])


class VietnameseFixT2Test(_Screens):
    LANG = "vi"


class EnglishFixT2Test(_Screens):
    LANG = "en"


del _Screens

if __name__ == "__main__":
    unittest.main()
