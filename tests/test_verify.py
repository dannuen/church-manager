"""B8: verify.py gives the tests at most 600 seconds; a timeout prints one FAIL line, not a traceback.
I18N-U7: the both-language rules of step 6 name each fault, and every GET route must be in the page list.
I18N-U7-fix1: an English word inside a Tiếng Việt text is named (the key, and each page that shows it)."""

import contextlib
import io
import pathlib
import subprocess
import tempfile
import types
import unittest
from unittest import mock

import _support  # noqa: F401 - puts the repo root on sys.path
import verify
from churchmgr import db, fake, i18n


class RunTestsTimeoutTest(unittest.TestCase):
    def test_a_timeout_is_one_fail_line(self):
        seen = {}

        def too_slow(cmd, **kwargs):
            seen.update(kwargs)
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

        out = io.StringIO()
        with mock.patch.object(verify.subprocess, "run", too_slow), contextlib.redirect_stdout(out):
            ok = verify.Checks().run("All tests", verify.run_tests)
        self.assertFalse(ok)
        self.assertEqual(seen["timeout"], 600)
        printed = out.getvalue()
        last = printed.splitlines()[-1]
        self.assertTrue(last.startswith("FAIL  All tests: TimeoutExpired: "), printed)
        self.assertIn("timed out after 600 seconds", last)
        self.assertNotIn("Traceback", printed)


class PageRulesTest(unittest.TestCase):
    """Step 6 on small hand-made pages: a right page has no problem, and each fault is named."""

    SWITCH = ('<form class="lang-switch" method="post" action="/language" aria-label="Ngôn ngữ">'
              '<input type="hidden" name="next" value="/people">'
              '<button name="lang" value="vi" lang="vi" aria-pressed="{vi}">Tiếng Việt</button>'
              '<button name="lang" value="en" lang="en" aria-pressed="{en}">English</button></form>')

    def page(self, lang="vi", body="<h1>Mọi người</h1>", pressed=None):
        pressed = pressed or lang
        switch = self.SWITCH.format(vi=str(pressed == "vi").lower(), en=str(pressed == "en").lower())
        return f'<!doctype html>\n<html lang="{lang}">\n<head><title>x</title></head><body>{switch}{body}</body></html>'

    def problems(self, lang, page, status=200, expect=200, content="text/html; charset=utf-8"):
        return verify.page_problems(lang, status, {"content-type": content}, page.encode("utf-8"), expect)

    def test_a_right_page_has_no_problem(self):
        self.assertEqual(self.problems("vi", self.page()), [])
        self.assertEqual(self.problems("en", self.page("en", "<h1>People</h1>")), [])
        self.assertEqual(self.problems("vi", self.page(), status=404, expect=404), [])

    def test_each_fault_is_named(self):
        cases = [
            ("vi", self.page(body="<h1>People</h1>"), "English left: People"),
            ("vi", self.page(body="<h1>[[people.nope]]</h1>"), "[[ on the page: [[people.nope]]"),
            ("vi", self.page("en"), '<html lang="en">, expected "vi"'),
            ("vi", self.page(pressed="en"), 'switch button Tiếng Việt: expected value="vi" aria-pressed="true"'),
            ("vi", self.page().replace('action="/language"', 'action="/lang"'), 'no switch form (action="/language")'),
            ("vi", self.page().replace(">English<", ">Anh<"), "no switch button English"),
            ("en", self.page("en", "<h1>Mọi người</h1>"), "no English word seen by i18n.english_left"),
        ]
        for lang, page, problem in cases:
            self.assertIn(problem, self.problems(lang, page), problem)
        self.assertIn("status 500, expected 200", self.problems("vi", self.page(), status=500))
        self.assertIn("no HTML page: application/json", self.problems("vi", "[]", content="application/json"))

    def test_a_file_or_json_answer(self):
        self.assertEqual(verify.answer_problems(200, {"content-type": "application/json"}, b"[]", 200), [])
        self.assertEqual(verify.answer_problems(200, {"content-type": "text/html"}, b"[[x]]", 200),
                         ["an HTML page, expected a file or JSON", "[[ in the answer"])

    def vi_texts(self):
        """``check_vi_texts()`` as ``(ok, detail, printed lines)``."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ok, detail = verify.check_vi_texts()
        return ok, detail, out.getvalue()

    def test_every_vi_text_of_today_is_vietnamese(self):
        ok, detail, printed = self.vi_texts()
        self.assertTrue(ok, printed + detail)
        self.assertIn("no English word", detail)

    def test_an_english_word_in_a_vi_text_is_named_with_its_key_and_on_the_page(self):
        """I18N-U7-fix1 (M1): english_left cannot see these words, because they are in TEXT["vi"]."""
        english = {"settings.language_hint": i18n.TEXT["en"]["settings.language_hint"],
                   "families.title": "Gia đình Families"}
        with mock.patch.dict(i18n.TEXT["vi"], english):
            ok, detail, printed = self.vi_texts()
            self.assertFalse(ok)
            self.assertIn("2 TEXTS WITH ENGLISH WORDS", detail)
            self.assertIn("      settings.language_hint: and, items, list, names, notes, screens, stay, the, they, "
                          "typed, were, words\n", printed)
            self.assertIn("      families.title: families\n", printed)
            page = self.page(body="<h1>Gia đình Families</h1>")
            self.assertEqual(i18n.english_left(page), [])  # the old rule alone says nothing
            self.assertIn("English from a Tiếng Việt text: Families", self.problems("vi", page))
            self.assertEqual(self.problems("vi", self.page()), [])  # a page with no such word
            self.assertEqual(self.problems("vi", self.page(body='<h1>Gia đình</h1><p lang="vi">Families</p>')), [])
        self.assertEqual(self.problems("vi", self.page(body="<h1>Gia đình Families</h1>")),
                         ["English left: Families"])  # patch gone: the word is English again


class RoutesListedTest(unittest.TestCase):
    """Every GET route of the page modules is in the page list of step 6; a new route with no page fails."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        root = pathlib.Path(cls.tmp.name)
        assert "onedrive" not in str(root.resolve()).lower()
        fake.build_fake_church(root / "fake", lang="vi")
        cls.db_path = root / "fake" / db.DB_NAME

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_get_route_has_a_page(self):
        ok, detail = verify.check_routes(self.db_path)
        self.assertTrue(ok, detail)

    def test_a_new_route_with_no_page_fails(self):
        extra = types.SimpleNamespace(ROUTES=[("GET", "/nowhere/<int:id>", None)])
        with mock.patch.object(verify.pages, "PAGES", [*verify.pages.PAGES, extra]):
            ok, detail = verify.check_routes(self.db_path)
        self.assertFalse(ok)
        self.assertIn("NO PAGE CHECKED FOR: /nowhere/<int:id>", detail)


if __name__ == "__main__":
    unittest.main()
