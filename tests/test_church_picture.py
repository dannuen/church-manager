"""Round 4 "Pearl", part 1: the church picture (docs/redesign-pearl-for-hermes.md, card PP-3).

One file, ``church-picture`` (no extension), in the church copy folder next to ``documents/``, never in
``web/``. Settings saves it (JPEG, PNG or WebP, the kind read from its first bytes, never from a file name;
at most 5 MB) or removes it. ``GET /church-picture`` gives that one file with its real type; no part of the
request reaches the file system. With a picture every page of ``ui.page`` has ``--hero-image`` in its
``:root`` style and ``<div class="app has-hero">``; with none the page is exactly as before.
``ui.bare_page`` never has them. The Handover part is card PP-3H. 390px and 1440px need a browser: they are
measured on the card.
"""

import hashlib
import re
import tempfile
import types
import unittest
import pathlib

import _support  # noqa: F401 - puts the repo root on sys.path
import verify
from churchmgr import app_color, db, i18n, picture, server, settings, ui
from churchmgr.i18n import TextError, english_left
from churchmgr.pages import settings as settings_pages
from test_pages_documents import MultipartMixin
from test_pages_people import PagesTestBase, flash_of, section
from churchmgr import fake

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + bytes(range(256)) * 4
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + bytes(range(64))
WEBP = b"RIFF" + (4 + 68).to_bytes(4, "little") + b"WEBPVP8 " + bytes(range(64))
KINDS = {"image/jpeg": JPEG, "image/png": PNG, "image/webp": WEBP}
TEXT_FILE = b"This is plain text, not a picture. Its name ends in .jpg.\n"
TOO_BIG = JPEG + bytes(picture.MAX_SIZE)  # a JPEG start, over 5 MB
STYLE = re.compile(r"<style>:root\{([^}]*)\}</style>")
TOKEN = re.compile(r"--hero-image:url\(/church-picture\?v=(\d+)\)")
SQLITE = b"SQLite format 3"

# The 12 text keys of DECISIONS-pearl-parts.md, part 1: (key, en, vi).
KEYS = (
    ("settings.panel_picture", "Church picture", "Hình Hội Thánh"),
    ("settings.picture", "Picture", "Hình"),
    ("settings.picture_hint", "JPEG, PNG or WebP, at most {mb} MB. It shows at the top of every page.",
     "JPEG, PNG hoặc WebP, tối đa {mb} MB. Hình hiện ở đầu mỗi trang."),
    ("settings.picture_save", "Save the picture", "Lưu hình"),
    ("settings.picture_remove", "Remove the picture", "Gỡ hình"),
    ("settings.picture_alt", "The church picture", "Hình Hội Thánh"),
    ("settings.picture_none", "No picture yet: the top of the page stays plain.", "Chưa có hình: đầu trang để trơn."),
    ("settings.picture_saved", "The church picture is saved.", "Đã lưu hình Hội Thánh."),
    ("settings.picture_removed", "The church picture is removed.", "Đã gỡ hình Hội Thánh."),
    ("settings.err_picture_kind", "Choose a JPEG, PNG or WebP picture.", "Hãy chọn một hình JPEG, PNG hoặc WebP."),
    ("settings.err_picture_size", "The picture is over {mb} MB. Choose a smaller one.",
     "Hình lớn hơn {mb} MB. Hãy chọn hình nhỏ hơn."),
    ("settings.err_picture_none", "Choose a picture first.", "Hãy chọn một hình trước."),
)
REFUSED = {  # what is sent -> the sentence, in each language
    "kind": {"en": "Choose a JPEG, PNG or WebP picture.", "vi": "Hãy chọn một hình JPEG, PNG hoặc WebP."},
    "size": {"en": "The picture is over 5 MB. Choose a smaller one.", "vi": "Hình lớn hơn 5 MB. Hãy chọn hình nhỏ hơn."},
    "none": {"en": "Choose a picture first.", "vi": "Hãy chọn một hình trước."},
}
# The path tricks of the card: none of them may ever give church.db.
TRICKS = ("/church-picture/../church.db", "/church-picture/..%2Fchurch.db", "/church-picture%2F..%2Fchurch.db",
          "/church-picture/%2e%2e/church.db", "/church-picture/", "/church-picture/church.db",
          "/church-picture/..", "/church-picture?x=../church.db", "/church-picture?v=../church.db",
          "/church-picture?v=..%2F..%2Fchurch.db&x=church.db")


def tokens(page):
    """The names of the CSS tokens the page head sets in ``<style>:root{...}</style>``."""
    return [part.split(":", 1)[0] for part in STYLE.search(page).group(1).split(";")]


def files_of(folder):
    """``{relative path: sha256}`` of every file under ``folder``."""
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


class PictureFileTest(unittest.TestCase):
    """``churchmgr/picture.py`` on a plain folder (no server)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        self.addCleanup(tmp.cleanup)
        self.folder = pathlib.Path(tmp.name).resolve() / "copy"
        assert "onedrive" not in str(self.folder).lower()
        (self.folder / db.DOCUMENTS_DIR).mkdir(parents=True)

    def test_the_kind_comes_from_the_first_bytes(self):
        for kind, data in KINDS.items():
            self.assertEqual(picture.picture_type(data), kind)
        for data in (b"", b"\xff\xd8", b"\x89PNG\r\n", b"RIFF\x00\x00\x00\x00WAVEfmt ", b"RIFF1234WEB",
                     b"GIF89a\x01\x00\x01\x00", b"%PDF-1.7", b"<svg xmlns='http://www.w3.org/2000/svg'/>",
                     TEXT_FILE, SQLITE + bytes(100)):
            self.assertIsNone(picture.picture_type(data), data[:20])

    def test_one_fixed_file_in_the_copy_folder_never_in_web(self):
        self.assertEqual(db.PICTURE_NAME, "church-picture")
        self.assertEqual(picture.MAX_SIZE, 5 * 1024 * 1024)
        web_before = sorted(p.name for p in server.WEB_DIR.iterdir())
        for kind, data in KINDS.items():
            with self.subTest(kind=kind):
                path = picture.save_picture(self.folder, data)
                self.assertEqual(path, self.folder / "church-picture")
                self.assertEqual(path.read_bytes(), data)
                self.assertEqual(picture.picture_path(self.folder), path)
                self.assertEqual(picture.picture_type(path.read_bytes()), kind)
                self.assertEqual(picture.picture_version(self.folder), path.stat().st_mtime_ns)
                self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["church-picture", "documents"])
        self.assertEqual(sorted(p.name for p in server.WEB_DIR.iterdir()), web_before)
        self.assertFalse((server.WEB_DIR / "church-picture").exists())

    def test_no_picture(self):
        self.assertIsNone(picture.picture_path(self.folder))
        self.assertIsNone(picture.picture_version(self.folder))
        self.assertFalse(picture.remove_picture(self.folder))  # nothing to remove: no error
        (self.folder / "church-picture").mkdir()  # a folder by that name is not a picture
        self.assertIsNone(picture.picture_path(self.folder))
        self.assertIsNone(picture.picture_version(self.folder))

    def test_refused_with_its_sentence_and_nothing_is_written(self):
        cases = ((b"", "none"), (None, "none"), (TEXT_FILE, "kind"), (TOO_BIG, "size"),
                 (b"RIFF\x00\x00\x00\x00WAVEfmt " + bytes(64), "kind"))
        for data, why in cases:
            with self.subTest(why=why, data=(data or b"")[:12]):
                with self.assertRaises(TextError) as caught:
                    picture.save_picture(self.folder, data)
                self.assertEqual(str(caught.exception), REFUSED[why]["en"])
                self.assertEqual(i18n.error_text(caught.exception, "vi"), REFUSED[why]["vi"])
                self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["documents"])  # no .partial
        picture.save_picture(self.folder, PNG)
        for data, why in cases:  # a refused file leaves the picture there as it was
            with self.assertRaises(TextError):
                picture.save_picture(self.folder, data)
            self.assertEqual((self.folder / "church-picture").read_bytes(), PNG)

    def test_5_mb_is_the_limit(self):
        exact = JPEG[:3] + bytes(picture.MAX_SIZE - 3)
        picture.save_picture(self.folder, exact)
        self.assertEqual((self.folder / "church-picture").stat().st_size, picture.MAX_SIZE)
        with self.assertRaises(TextError):
            picture.save_picture(self.folder, exact + b"\x00")
        self.assertEqual((self.folder / "church-picture").stat().st_size, picture.MAX_SIZE)

    def test_a_new_picture_takes_the_place_of_the_old(self):
        picture.save_picture(self.folder, JPEG)
        picture.save_picture(self.folder, WEBP)
        self.assertEqual((self.folder / "church-picture").read_bytes(), WEBP)
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["church-picture", "documents"])

    def test_remove_deletes_only_the_picture(self):
        picture.save_picture(self.folder, JPEG)
        (self.folder / db.DB_NAME).write_bytes(SQLITE + bytes(100))
        (self.folder / db.DOCUMENTS_DIR / "a1b2.pdf").write_bytes(b"%PDF-1.7 a Document")
        (self.folder / "church-picture.jpg").write_bytes(JPEG)  # another name: not the church picture
        before = files_of(self.folder)
        self.assertTrue(picture.remove_picture(self.folder))
        self.assertIsNone(picture.picture_path(self.folder))
        after = files_of(self.folder)
        self.assertEqual(after, {k: v for k, v in before.items() if k != "church-picture"})


class TextKeysTest(unittest.TestCase):
    def test_the_12_keys_in_both_languages(self):
        for key, en, vi in KEYS:
            with self.subTest(key=key):
                self.assertEqual((i18n.TEXT["en"][key], i18n.TEXT["vi"][key]), (en, vi))

    def test_no_english_word_in_the_vietnamese_texts(self):
        """verify.py step 6: JPEG, PNG and WebP are names of file kinds (``i18n.ALLOW``), not English."""
        self.assertEqual({k: v for k, v in verify.vi_english().items() if k.startswith("settings.")}, {})
        self.assertTrue({"jpeg", "png", "webp"} <= i18n.ALLOW)


class PicturePagesTest(MultipartMixin, PagesTestBase):
    """The Settings panel, ``GET /church-picture`` and the page head, on an English fake church."""

    def setUp(self):
        picture.remove_picture(self.copy)
        self.addCleanup(picture.remove_picture, self.copy)

    def choose(self, data, name="photo.jpg", expect=303):
        return self.post_multipart("/settings/church-picture", {}, {"picture": (name, data)}, expect=expect)

    def version(self):
        return picture.picture_version(self.copy)

    def test_no_picture_no_class_and_no_token(self):
        color_tokens = list(app_color.theme(settings.get_app_color(self.db())))
        for path, status in (("/", 200), ("/people", 200), ("/settings", 200), ("/no-such-page", 404)):
            with self.subTest(path=path):
                page = self.page(path, status)
                self.assertEqual(page.count('<div class="app">'), 1)
                self.assertNotIn("has-hero", page)
                self.assertNotIn("--hero-image", page)
                self.assertNotIn("/church-picture?v=", page)
                self.assertEqual(tokens(page), color_tokens)  # the 4 app color tokens, as before

    def test_a_picture_gives_the_token_and_the_class_on_every_page(self):
        self.choose(WEBP, "church.webp")
        version = self.version()
        self.assertIsNotNone(version)
        for path, status in (("/", 200), ("/people", 200), ("/calendar", 200), ("/settings", 200),
                             ("/no-such-page", 404), ("/church-picture/x", 404)):
            with self.subTest(path=path):
                page = self.page(path, status)
                self.assertEqual(page.count('<div class="app has-hero">'), 1)
                self.assertNotIn('<div class="app">', page)
                self.assertEqual(TOKEN.findall(STYLE.search(page).group(1)), [str(version)])
                self.assertEqual(page.count("--hero-image"), 1)  # only in the :root style of the head

    def test_the_only_change_is_the_class_and_the_token_and_remove_brings_back_the_page(self):
        paths = ("/people", "/families", "/lists")
        before = {path: self.page(path) for path in paths}
        self.choose(JPEG)
        token = f";--hero-image:url(/church-picture?v={self.version()})"
        for path in paths:
            with self.subTest(path=path):
                page = self.page(path)
                self.assertEqual(page.count(token), 1)
                self.assertEqual(page.replace('<div class="app has-hero">', '<div class="app">', 1)
                                 .replace(token, "", 1), before[path])
        self.post("/settings/church-picture/remove", {})
        for path in paths:
            self.assertEqual(self.page(path), before[path])  # plain pearl again, byte for byte

    def test_the_bare_page_never_has_the_picture(self):
        self.choose(PNG, "church.png")
        req = server.Request(self.httpd, "GET", "/", {})
        self.addCleanup(req.close)
        ui.set_request(req)
        self.addCleanup(ui.set_request, None)
        bare = ui.bare_page("Something went wrong", "<p>x</p>")
        self.assertIn('<div class="app"><aside class="sidebar">', bare)
        self.assertNotIn("has-hero", bare)
        self.assertNotIn("--hero-image", bare)
        self.assertIn('<div class="app has-hero">', ui.page("Title", "<p>x</p>"))  # same request, a full page

    def test_each_kind_is_saved_and_given_back_with_its_type(self):
        for kind, data in KINDS.items():
            with self.subTest(kind=kind):
                headers, _ = self.choose(data, "no-extension")  # the name says nothing: the bytes do
                self.assertTrue(headers["location"].startswith("/settings?msg="), headers["location"])
                self.assertEqual(flash_of(headers), "The church picture is saved.")
                self.assertEqual((self.copy / "church-picture").read_bytes(), data)
                status, got, body = self.request("GET", "/church-picture")
                self.assertEqual(status, 200)
                self.assertEqual(got["content-type"], kind)
                self.assertEqual(got["cache-control"], "no-cache")
                self.assertEqual(got["x-content-type-options"], "nosniff")
                self.assertNotIn("content-disposition", got)
                self.assertEqual(body, data)
                status, _got, again = self.request("GET", f"/church-picture?v={self.version()}")
                self.assertEqual((status, again), (200, data))  # the ?v= only makes a new address
        self.assertFalse((server.WEB_DIR / "church-picture").exists())
        self.assertEqual(sorted(p.name for p in self.copy.iterdir() if p.name.startswith("church-picture")),
                         ["church-picture"])

    def test_the_settings_panel_with_no_picture(self):
        page = self.page("/settings")
        self.assertLess(page.index('data-panel="settings-form"'), page.index('data-panel="settings-picture"'))
        self.assertRegex(page, r'<div class="span-7 stack"><section [^>]*data-panel="settings-form".*?</section>'
                               r'<section [^>]*data-panel="settings-picture"')
        panel = section(page, "settings-picture")
        self.assertIn('<h2 id="p-settings-picture">Church picture</h2>', panel)
        self.assertIn("No picture yet: the top of the page stays plain.", panel)
        self.assertIn('<form class="form" action="/settings/church-picture" method="post" '
                      'enctype="multipart/form-data">', panel)
        field = re.search(r'<input class="input"[^>]*>', panel).group(0)
        for attr in ('id="f-picture"', 'name="picture"', 'type="file"', 'accept="image/jpeg,image/png,image/webp"',
                     "required", f'data-max-bytes="{picture.MAX_SIZE}"',
                     'data-text-too-large="The picture is over 5 MB. Choose a smaller one."'):
            self.assertIn(attr, field)
        self.assertIn('<label for="f-picture">Picture</label>', panel)
        self.assertIn("JPEG, PNG or WebP, at most 5 MB. It shows at the top of every page.", panel)
        self.assertIn('<button class="btn primary" type="submit">Save the picture</button>', panel)
        self.assertNotIn("<img", panel)
        self.assertNotIn("/settings/church-picture/remove", panel)
        self.assertNotIn("style=", panel)

    def test_the_settings_panel_with_a_picture(self):
        self.choose(JPEG)
        panel = section(self.page("/settings"), "settings-picture")
        self.assertRegex(panel, rf'<img src="/church-picture\?v={self.version()}" alt="The church picture"'
                                r' width="\d+">')
        self.assertIn('<form class="form" action="/settings/church-picture/remove" method="post">'
                      '<button class="btn secondary" type="submit">Remove the picture</button></form>', panel)
        self.assertIn('action="/settings/church-picture" method="post" enctype="multipart/form-data"', panel)
        # the picture, Remove right under it, then the form for a new one under a line
        self.assertRegex(panel, r'^<header>.*?</header><p><img [^>]*></p><form class="form" action="/settings/'
                                r'church-picture/remove" method="post">.*?</form><div class="add-form"><form class="form" '
                                r'action="/settings/church-picture" method="post" enctype="multipart/form-data">.*?'
                                r'</form></div>$')
        self.assertNotIn("No picture yet", panel)
        self.assertNotIn("style=", panel)

    def test_a_refused_file_gives_the_page_again_with_the_sentence_at_the_field(self):
        sent = {"kind": (TEXT_FILE, "photo.jpg"), "size": (TOO_BIG, "big.jpg"), "none": (b"", "")}
        for why, (data, name) in sent.items():
            with self.subTest(why=why):
                _h, page = self.choose(data, name, expect=400)
                panel = section(page, "settings-picture")
                self.assertIn(f'<p class="error" id="f-picture-error">{REFUSED[why]["en"]}</p>', panel)
                self.assertIn('aria-invalid="true"', re.search(r'<input class="input" id="f-picture"[^>]*>',
                                                               panel).group(0))
                self.assertIn("<h1>Settings</h1>", page)
                self.assertIn('data-panel="settings-form"', page)  # the church form is still there
                self.assertIsNone(picture.picture_path(self.copy))
        _h, page = self.post("/settings/church-picture", {}, expect=400)  # a form with no file part at all
        self.assertIn(f'<p class="error" id="f-picture-error">{REFUSED["none"]["en"]}</p>', page)
        self.choose(WEBP)
        self.choose(TEXT_FILE, "photo.jpg", expect=400)
        self.assertEqual((self.copy / "church-picture").read_bytes(), WEBP)  # the old picture stays

    def test_get_church_picture_with_no_picture_is_the_404_page(self):
        status, headers, body = self.request("GET", "/church-picture")
        self.assertEqual(status, 404)
        self.assertTrue(headers["content-type"].startswith("text/html"))
        page = body.decode("utf-8")
        self.assertIn("<h1>Church picture not found</h1>", page)
        self.assertIn("No picture yet: the top of the page stays plain.", page)
        self.assertIn('<a href="/settings">Settings</a>', page)

    def test_no_church_copy_open_is_the_404_page(self):
        req = types.SimpleNamespace(state=types.SimpleNamespace(copy_folder=None), query={})
        resp = settings_pages.picture_file(req)
        self.assertEqual(resp.status, 404)
        self.assertNotIn(SQLITE, resp.body)

    def test_path_tricks_never_give_church_db(self):
        church_db = (self.copy / db.DB_NAME).read_bytes()
        for state in ("no picture", "a picture"):
            if state == "a picture":
                self.choose(JPEG)
            for path in TRICKS:
                with self.subTest(state=state, path=path):
                    status, _headers, body = self.request("GET", path)
                    self.assertNotIn(SQLITE, body)
                    self.assertNotEqual(body, church_db)
                    if state == "a picture" and path.startswith("/church-picture?"):
                        self.assertEqual((status, body), (200, JPEG))  # the query is ignored
                    else:
                        self.assertEqual(status, 404)

    def test_remove_deletes_only_the_church_picture(self):
        self.choose(JPEG)
        before = files_of(self.copy)
        self.assertIn("church-picture", before)
        self.assertIn(db.DB_NAME, before)
        self.assertTrue(any(name.startswith("documents/") for name in before))
        headers, _ = self.post("/settings/church-picture/remove", {})
        self.assertTrue(headers["location"].startswith("/settings?msg="), headers["location"])
        self.assertEqual(flash_of(headers), "The church picture is removed.")
        self.assertEqual(files_of(self.copy), {k: v for k, v in before.items() if k != "church-picture"})
        self.assertEqual(self.request("GET", "/church-picture")[0], 404)
        self.post("/settings/church-picture/remove", {})  # again, with no picture: no error


class VietnamesePictureTest(MultipartMixin, PagesTestBase):
    """The same panel, sentences and pages on a Tiếng Việt church copy."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        cls.root = pathlib.Path(cls.tmp.name)
        assert "onedrive" not in str(cls.root.resolve()).lower()
        cls.copy = cls.root / "fake"
        fake.build_fake_church(cls.copy, people=20, lang="vi")
        cls.start(cls.copy, cls.root, remember=False)

    def setUp(self):
        picture.remove_picture(self.copy)
        self.addCleanup(picture.remove_picture, self.copy)

    def choose(self, data, name="hinh.jpg", expect=303):
        return self.post_multipart("/settings/church-picture", {}, {"picture": (name, data)}, expect=expect)

    def test_the_panel_in_vietnamese(self):
        page = self.page("/settings")
        self.assertIn('<html lang="vi">', page)
        panel = section(page, "settings-picture")
        for words in ('<h2 id="p-settings-picture">Hình Hội Thánh</h2>', '<label for="f-picture">Hình</label>',
                      "JPEG, PNG hoặc WebP, tối đa 5 MB. Hình hiện ở đầu mỗi trang.", "Chưa có hình: đầu trang để trơn.",
                      ">Lưu hình</button>", 'data-text-too-large="Hình lớn hơn 5 MB. Hãy chọn hình nhỏ hơn."'):
            self.assertIn(words, panel)
        self.assertEqual(english_left(page), [])
        headers, _ = self.choose(WEBP)
        self.assertEqual(flash_of(headers), "Đã lưu hình Hội Thánh.")
        page = self.page("/settings")
        self.assertIn('<div class="app has-hero">', page)
        panel = section(page, "settings-picture")
        self.assertIn('alt="Hình Hội Thánh"', panel)
        self.assertIn('<button class="btn secondary" type="submit">Gỡ hình</button>', panel)
        self.assertEqual(english_left(page), [])
        headers, _ = self.post("/settings/church-picture/remove", {})
        self.assertEqual(flash_of(headers), "Đã gỡ hình Hội Thánh.")

    def test_the_sentences_in_vietnamese(self):
        sent = {"kind": (TEXT_FILE, "anh.jpg"), "size": (TOO_BIG, "lon.jpg"), "none": (b"", "")}
        for why, (data, name) in sent.items():
            with self.subTest(why=why):
                _h, page = self.choose(data, name, expect=400)
                self.assertIn(f'<p class="error" id="f-picture-error">{REFUSED[why]["vi"]}</p>',
                              section(page, "settings-picture"))
                self.assertEqual(english_left(page), [])

    def test_the_404_page_in_vietnamese(self):
        status, _headers, body = self.request("GET", "/church-picture")
        page = body.decode("utf-8")
        self.assertEqual(status, 404)
        self.assertIn("<h1>Không tìm thấy Hình Hội Thánh</h1>", page)
        self.assertIn('<a href="/settings">Cài đặt</a>', page)
        self.assertEqual(english_left(page), [])


if __name__ == "__main__":
    unittest.main()
