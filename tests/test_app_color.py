"""COLOR-1: the one app color. The pastor picks it in Settings; it is saved in the church copy (table
``setting``, key ``app_color``) and every page head sets its 4 colors (``churchmgr/app_color.py`` ``theme``).
Real servers on 127.0.0.1 (port 0) over fake churches in temp folders outside OneDrive.
"""

import pathlib
import re
import tempfile
import unittest

import _support  # noqa: F401 - puts the repo root on sys.path
from churchmgr import app_color, db, fake, settings, server
from churchmgr.i18n import TextError, english_left
from test_server import LiveServer

COLORS = ("#1f5c99", "#ff0000", "#008000", "#00ff00", "#ffffcc", "#ffff00", "#808080", "#7f7fff", "#000000",
          "#ffffff")
BAD = ("#fff", "red", "rgb(1,2,3)", "#12345g", "", "#1f5c99 ", "#1f5c99\n", "1f5c99", " #1f5c99", "#1f5c9")
STYLE_LINK = '<link rel="stylesheet" href="/static/style.css">\n'
DEFAULT_STYLE = "<style>:root{--accent:#1f5c99;--accent-base:#1f5c99;--on-accent:#ffffff;--accent-text:#1f5c99}</style>"
RED_STYLE = "<style>:root{--accent:#ff0000;--accent-base:#d90000;--on-accent:#ffffff;--accent-text:#d90000}</style>"
PICKER = ('<input class="input" id="f-app_color" name="app_color" aria-describedby="f-app_color-hint" '
          'type="color" value="{}">')


def head_of(page):
    return page.split("</head>", 1)[0]


class ChurchServer(LiveServer):
    """One fake church (``LANG``) and one live server per test class."""

    LANG = "en"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        cls.root = pathlib.Path(cls.tmp.name)
        assert "onedrive" not in str(cls.root.resolve()).lower()
        cls.copy = cls.root / "fake"
        fake.build_fake_church(cls.copy, lang=cls.LANG)
        cls.start(cls.copy, cls.root, remember=False)

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

    def post(self, form, expect=303):
        status, headers, data = self.request("POST", "/settings", form)
        self.assertEqual(status, expect, data.decode("utf-8")[:2000])
        return headers, data.decode("utf-8")


class DefaultColorTest(ChurchServer, unittest.TestCase):
    """Test 1: a fresh fake church (Tiếng Việt) has no app color row and shows the default color."""

    LANG = "vi"

    def test_a_fresh_church_has_the_default_color(self):
        conn = self.db()
        self.assertIsNone(settings.get_setting(conn, settings.APP_COLOR))  # no row
        self.assertEqual(settings.get_app_color(conn), "#1f5c99")
        self.assertEqual(settings.DEFAULT_APP_COLOR, "#1f5c99")
        page = self.page("/settings")
        self.assertIn(PICKER.format("#1f5c99"), page)
        self.assertIn('<label for="f-app_color">Màu giao diện</label>', page)
        self.assertIn('<p class="hint" id="f-app_color-hint">Chọn một màu. Ứng dụng tự tạo màu chuyển cho phần đầu '
                      'trang, menu và các nút.</p>', page)
        # in the same form, right after the language field, before the Save button
        self.assertLess(page.index('id="f-language"'), page.index('id="f-app_color"'))
        self.assertLess(page.index('id="f-app_color"'), page.index("Lưu cài đặt</button>"))
        self.assertEqual(page.count('type="color"'), 1)
        self.assertEqual(english_left(page), [])
        for path in ("/", "/settings"):
            head = head_of(self.page(path))
            self.assertIn("--accent:#1f5c99", head)
            self.assertIn(STYLE_LINK + DEFAULT_STYLE + "\n", head)  # right after style.css
            self.assertEqual(head.count("<style"), 1)


class SaveColorTest(ChurchServer, unittest.TestCase):
    """Tests 2-4: saving, refusing a bad color, an old form. Each test sets the color it starts from."""

    def form(self, **extra):
        return {"church_name": fake.CHURCH_NAME, "care_reminder_months": "3", **extra}

    def start_from(self, color):
        settings.set_setting(self.db(), settings.APP_COLOR, color)
        self.assertEqual(settings.get_app_color(self.db()), color)

    def test_a_picked_color_is_saved_in_lower_case_and_every_head_sets_it(self):
        self.start_from("#1f5c99")
        headers, _ = self.post(self.form(app_color="#FF0000"))
        self.assertTrue(headers["location"].startswith("/settings?msg="))
        self.assertEqual(settings.get_setting(self.db(), settings.APP_COLOR), "#ff0000")
        self.assertEqual(app_color.theme("#ff0000"), {"--accent": "#ff0000", "--accent-base": "#d90000",
                                                      "--on-accent": "#ffffff", "--accent-text": "#d90000"})
        for path in ("/", "/people", "/settings"):
            head = head_of(self.page(path))
            self.assertIn(STYLE_LINK + RED_STYLE + "\n", head, path)
            self.assertEqual(head.count("<style"), 1, path)
        self.assertIn(PICKER.format("#ff0000"), self.page("/settings"))
        again = LiveServer()  # a restart: a new server on the same church copy
        again.httpd = server.make_server(self.copy, self.root, 0, remember=False)
        server.serve_in_thread(again.httpd)
        try:
            status, _h, page = again.get_text("/settings")
            self.assertEqual(status, 200)
            self.assertIn(STYLE_LINK + RED_STYLE + "\n", head_of(page))
            self.assertIn(PICKER.format("#ff0000"), page)
        finally:
            again.httpd.shutdown()
            again.httpd.server_close()

    def test_a_bad_color_is_refused_and_nothing_is_saved(self):
        self.start_from("#123456")
        for bad in BAD:
            form = self.form(church_name="Hội Thánh Đổi Tên", care_reminder_months="4", app_color=bad)
            _h, page = self.post(form, expect=400)
            self.assertIn('<p class="error" id="f-app_color-error">This color is not valid. Pick a color again.</p>',
                          page, repr(bad))
            self.assertIn('aria-invalid="true" aria-describedby="f-app_color-hint f-app_color-error"', page)
            self.assertIn('type="color" value="#123456">', page)  # the picker shows the saved color
            conn = self.db()
            self.assertEqual(settings.get_setting(conn, settings.APP_COLOR), "#123456", repr(bad))
            self.assertEqual(settings.get_setting(conn, "church_name"), fake.CHURCH_NAME, repr(bad))
            self.assertNotEqual(settings.get_setting(conn, "care_reminder_months"), "4", repr(bad))
            self.assertIn("--accent:#123456;", head_of(page))
        # a good color with another bad field: nothing saved, the picker keeps the color that was picked
        _h, page = self.post(self.form(church_name=" ", app_color="#00FF00"), expect=400)
        self.assertIn('type="color" value="#00ff00">', page)
        self.assertNotIn('id="f-app_color-error"', page)
        self.assertEqual(settings.get_setting(self.db(), settings.APP_COLOR), "#123456")

    def test_an_old_form_with_no_color_field_keeps_the_color(self):
        self.start_from("#123456")
        headers, _ = self.post(self.form())
        self.assertTrue(headers["location"].startswith("/settings?msg="))
        self.assertEqual(settings.get_setting(self.db(), settings.APP_COLOR), "#123456")


class FirstRunTest(LiveServer, unittest.TestCase):
    """Test 6: no church copy open: no ``<style>`` in the page (style.css keeps its default colors)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        self.addCleanup(tmp.cleanup)
        self.start(None, pathlib.Path(tmp.name) / "copies")
        self.addCleanup(self.stop)

    def test_the_first_run_page_has_no_style_tag(self):
        status, _h, page = self.get_text("/setup")
        self.assertEqual(status, 200)
        self.assertIn(STYLE_LINK, page)
        self.assertNotIn("<style", page)
        status, headers, _d = self.request("GET", "/people")  # every page sends you to the setup page
        self.assertEqual((status, headers["location"]), (303, "/setup"))


class SettingRulesTest(_support.CopyTestCase):
    """``check_app_color``, ``set_setting`` and ``get_app_color`` on a church copy in a temp folder."""

    def test_only_hash_and_six_hex_digits_are_saved_in_lower_case(self):
        self.assertIsNone(settings.get_setting(self.conn, settings.APP_COLOR))
        self.assertEqual(settings.get_app_color(self.conn), settings.DEFAULT_APP_COLOR)
        settings.set_setting(self.conn, settings.APP_COLOR, "#AbCdEf")
        self.assertEqual(settings.get_setting(self.conn, settings.APP_COLOR), "#abcdef")
        for bad in BAD + (None, 123, b"#1f5c99"):
            with self.assertRaises(TextError, msg=repr(bad)) as caught:
                settings.set_setting(self.conn, settings.APP_COLOR, bad)
            self.assertEqual(caught.exception.key, "errors.app_color")
            with self.assertRaises(ValueError, msg=repr(bad)):
                settings.check_app_color(bad)
        self.assertEqual(settings.get_setting(self.conn, settings.APP_COLOR), "#abcdef")  # never changed

    def test_a_bad_stored_value_gives_the_default(self):
        for bad in ("#fff", "red", "", "#1f5c99 "):
            # a bad row written by hand on this temp copy only: the app never writes one
            self.conn.execute("INSERT INTO setting (key, value) VALUES ('app_color', ?) "
                              "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (bad,))
            self.assertEqual(settings.get_app_color(self.conn), "#1f5c99", repr(bad))


class ThemeMathTest(unittest.TestCase):
    """Test 5: the text on the gradient and the color as text stay readable (WCAG contrast >= 4.6)."""

    def test_mix_and_contrast(self):
        self.assertEqual(app_color.mix("#000000", "#ffffff", 50), "#808080")  # 127.5 rounds half up
        self.assertEqual(app_color.mix("#1f5c99", "#ffffff", 0), "#1f5c99")
        self.assertEqual(app_color.mix("#1f5c99", "#000000", 100), "#000000")
        self.assertEqual(app_color.ends("#1f5c99"), ("#4174a8", "#16406b"))
        self.assertAlmostEqual(app_color.contrast("#ffffff", "#000000"), 21.0)
        self.assertAlmostEqual(app_color.contrast("#777777", "#777777"), 1.0)
        self.assertAlmostEqual(app_color.contrast("#ffffff", "#767676"), 4.54, places=2)  # the known AA grey
        with self.assertRaises(ValueError):
            app_color.mix("#fff", "#000000", 10)
        with self.assertRaises(ValueError):
            app_color.mix("#ffffff", "#000000", 101)

    def test_every_sample_color_reads_on_both_ends_and_on_the_light_surfaces(self):
        for color in COLORS:
            th = app_color.theme(color)
            self.assertEqual(list(th), ["--accent", "--accent-base", "--on-accent", "--accent-text"])
            self.assertEqual(th["--accent"], color)
            for value in th.values():
                self.assertRegex(value, r"\A#[0-9a-f]{6}\Z")
            self.assertIn(th["--on-accent"], ("#ffffff", "#151515"))
            light, dark = app_color.ends(th["--accent-base"])
            worst = min(app_color.contrast(th["--on-accent"], end) for end in (light, dark))
            self.assertGreaterEqual(worst, 4.6, color)
            for surface in ("#ffffff", "#f7f7f6", "#f2f2f1"):
                self.assertGreaterEqual(app_color.contrast(th["--accent-text"], surface), 4.6, (color, surface))

    def test_the_rule_picks_the_smaller_nudge(self):
        self.assertEqual(app_color.theme("#1f5c99")["--accent-base"], "#1f5c99")  # the default look stays
        self.assertEqual(app_color.theme("#1F5C99")["--accent"], "#1f5c99")
        self.assertEqual(app_color.theme("#ffffcc")["--on-accent"], "#151515")
        self.assertEqual(app_color.theme("#ff0000")["--on-accent"], "#ffffff")
        self.assertEqual(app_color.theme("#00ff00")["--accent-base"], "#00ff00")  # dark text, no nudge
        # #808080: white needs 30% toward black (#5a5a5a); dark text needs more toward white
        self.assertEqual(app_color.theme("#808080")["--accent-base"], "#5a5a5a")
        for bad in ("#fff", "red", None):
            with self.assertRaises(ValueError):
                app_color.theme(bad)

    def test_the_css_defaults_are_the_theme_of_the_default_color(self):
        css = (pathlib.Path(_support.ROOT) / "web" / "style.css").read_text(encoding="utf-8")
        plain = re.sub(r"/\*.*?\*/", "", css, flags=re.S)  # comments removed
        root = re.search(r":root \{(.*?)\}", plain, re.S).group(1)
        for name, value in app_color.theme(settings.DEFAULT_APP_COLOR).items():
            self.assertRegex(root, rf"{name}: {value};")
        self.assertIn("--accent-light: color-mix(in srgb, var(--accent-base), #ffffff 15%);", root)
        self.assertIn("--accent-dark: color-mix(in srgb, var(--accent-base), #000000 30%);", root)
        self.assertIn("--gradient: linear-gradient(135deg, var(--accent-light), var(--accent-dark));", root)


def css_rules(name):
    """``[(selector, {property: value})]`` of ``web/<name>``, comments removed (a rule in ``@media`` too)."""
    css = re.sub(r"/\*.*?\*/", "", (pathlib.Path(_support.ROOT) / "web" / name).read_text(encoding="utf-8"),
                 flags=re.S)
    out = []
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        decls = (d.split(":", 1) for d in body.split(";") if d.strip())
        out.append((selector.strip(), {p.strip(): v.strip() for p, v in decls}))
    return out


def props(selector, name="style.css"):
    """``{property: value}`` of the rules whose selector list holds exactly ``selector`` (a later rule wins)."""
    found = [d for sel, d in css_rules(name) if selector in (s.strip() for s in sel.split(","))]
    assert found, f"no CSS rule for {selector!r} in {name}"
    return {p: v for d in found for p, v in d.items()}


class SurfacesTest(unittest.TestCase):
    """COLOR-2: the gradient of the app color on the header band (``.title-row``), the active menu item, the
    active filter and the primary buttons, with ``--on-accent`` text; the plain accent on the chart line and
    the focus ring; the color as text on the light surfaces in ``--accent-text``. Paper never gets the
    gradient."""

    GRADIENT = (".title-row", '.nav-item[aria-current="page"]', '.chip[aria-current="true"]', ".btn.primary")

    def test_the_band_the_active_menu_item_the_active_filter_and_primary_buttons_use_the_gradient(self):
        for selector in self.GRADIENT:
            rule = props(selector)
            self.assertEqual(rule["background"], "var(--gradient)", selector)
            self.assertEqual(rule["color"], "var(--on-accent)", selector)
        band = props(".title-row")
        self.assertEqual((band["padding"], band["border-radius"]), ("16px 20px", "var(--radius)"))
        for selector in ('.chip[aria-current="true"]', ".btn.primary"):  # the border goes with the gradient
            self.assertEqual(props(selector)["border-color"], "var(--accent-dark)", selector)
        self.assertEqual(props(".btn.primary:hover"), {"background": "var(--accent-dark)"})
        self.assertEqual(props(".title-row .btn.primary"), {"border-color": "var(--on-accent)"})  # the 1px ring

    def test_every_text_in_the_band_is_on_accent_at_full_strength(self):
        self.assertEqual(props(".title-row .sub")["color"], "var(--on-accent)")
        band_rules = [(sel, d) for sel, d in css_rules("style.css") if ".title-row" in sel]
        self.assertGreater(len(band_rules), 5)
        for sel, decls in band_rules:
            self.assertNotIn("opacity", decls, sel)
            for value in decls.values():
                self.assertNotIn("var(--muted)", value, sel)
                self.assertNotIn("var(--faint)", value, sel)
        # a control with its own white surface keeps its ink: secondary .btn, the search field, the results
        self.assertEqual((props(".btn")["background"], props(".btn")["color"]), ("var(--surface)", "var(--text)"))
        self.assertEqual(props(".input")["background"], "var(--surface)")
        for selector in (".title-row .input", ".title-row .results"):
            self.assertEqual(props(selector)["color"], "var(--text)", selector)

    def test_the_plain_accent_stays_on_the_chart_line_and_the_focus_ring(self):
        self.assertEqual(props(".chart .line")["stroke"], "var(--accent)")
        self.assertEqual(props(":focus-visible")["outline"], "2px solid var(--accent)")
        self.assertEqual(props(".title-row :focus-visible"), {"outline-color": "var(--on-accent)"})  # on the band
        self.assertEqual(props(".title-row .results :focus-visible"), {"outline-color": "var(--accent)"})

    def test_the_color_as_text_on_light_surfaces_is_accent_text(self):
        self.assertEqual(props(".today-tag")["color"], "var(--accent-text)")
        self.assertEqual(props(".kind.k-service")["color"], "var(--accent-text)")
        self.assertEqual(props(".chart .end")["fill"], "var(--accent-text)")
        for sel, decls in css_rules("style.css"):  # no text in the raw saved color (it may be very light)
            for prop in ("color", "fill"):
                self.assertNotEqual(decls.get(prop), "var(--accent)", sel)

    def test_no_rule_outside_root_has_a_raw_color_for_the_accent(self):
        css = (pathlib.Path(_support.ROOT) / "web" / "style.css").read_text(encoding="utf-8")
        plain = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        root = re.search(r":root \{(.*?)\}", plain, re.S).group(1)
        rest = plain.replace(root, "")
        accent = {v for k, v in app_color.theme(settings.DEFAULT_APP_COLOR).items() if k != "--on-accent"}
        for raw in accent | {"#1d1f20", "#3a3d3f"}:
            self.assertNotIn(raw, rest.lower(), raw)  # the default color, the old primary and its hover
        self.assertNotIn("--primary", plain)  # no rule used --primary / --primary-ink after COLOR-2
        for selector in self.GRADIENT + (".btn.primary:hover", ".title-row .btn.primary", ".title-row .sub"):
            for value in props(selector).values():
                self.assertNotIn("#", value, selector)  # their colors come from the tokens only
        defined = set(re.findall(r"(--[\w-]+):", root))
        self.assertLessEqual(set(re.findall(r"var\((--[\w-]+)\)", plain)), defined)  # no unknown token

    def test_paper_never_gets_the_gradient(self):
        css = (pathlib.Path(_support.ROOT) / "web" / "print.css").read_text(encoding="utf-8")
        plain = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        self.assertNotIn("gradient", plain)
        self.assertNotIn("var(--", plain)
        media = plain.index("@media print {")
        self.assertLess(media, plain.index(".title-row {"))  # the rules below are for paper only
        band = props(".title-row", "print.css")
        self.assertEqual((band["background"], band["color"], band["padding"]), ("none", "#000", "0"))
        self.assertEqual(props(".title-row .sub", "print.css"), {"color": "#333"})
        self.assertEqual(props('.chip[aria-current="true"]', "print.css")["background"], "none")


if __name__ == "__main__":
    unittest.main()
