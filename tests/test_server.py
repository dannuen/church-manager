"""Card B: the local server, the page framework, the dashboard, search and first-run setup.

Every server test talks to a real server on 127.0.0.1 with a free port, in a thread,
over a fake church copy in a temp folder.
"""

import contextlib
import datetime as dt
import http.client
import io
import json
import pathlib
import socket
import tempfile
import unicodedata
import unittest
import urllib.parse
from html.parser import HTMLParser

import _support  # noqa: F401 - puts the repo root on sys.path
import app
import test_db  # module import only, so its test classes are not collected twice
from churchmgr import db, fake, money, paths, people, sent, server, ui
from churchmgr.pages import dashboard

ROOT = pathlib.Path(_support.ROOT)
PANELS = {"this-week", "needs-visit", "services", "money-month", "sent-documents", "search"}
DATA_PANELS = PANELS - {"search"}  # the search panel has a form, its rows come live


class PanelParser(HTMLParser):
    """Counts ``data-row`` elements inside each ``<section data-panel>``; counts ``<h1>``."""

    def __init__(self):
        super().__init__()
        self.rows, self.current, self.h1 = {}, None, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "h1":
            self.h1 += 1
        if tag == "section" and "data-panel" in a:
            self.current = a["data-panel"]
            self.rows[self.current] = 0
        elif self.current and "data-row" in a:
            self.rows[self.current] += 1

    def handle_endtag(self, tag):
        if tag == "section":
            self.current = None


def parse_panels(html_text):
    p = PanelParser()
    p.feed(html_text)
    return p


class LiveServer:
    """Helpers for a test class that runs one server."""

    httpd = None

    @classmethod
    def start(cls, copy_folder, copies_root, remember=True):
        cls.httpd = server.make_server(copy_folder, copies_root, 0, remember=remember)
        server.serve_in_thread(cls.httpd)

    @classmethod
    def stop(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def request(self, method, path, body=None, headers=None, host=None, origin=True):
        port = self.httpd.port
        h = {"Host": host or f"127.0.0.1:{port}"}
        if method == "POST" and origin is True:
            h["Origin"] = f"http://127.0.0.1:{port}"
        if isinstance(body, dict):
            body = urllib.parse.urlencode(body).encode("ascii")
            h["Content-Type"] = "application/x-www-form-urlencoded"
        h.update(headers or {})
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
        try:
            conn.request(method, path, body=body, headers=h)
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, {k.lower(): v for k, v in resp.getheaders()}, data
        finally:
            conn.close()

    def get_text(self, path, **kw):
        status, headers, data = self.request("GET", path, **kw)
        return status, headers, data.decode("utf-8")


class FakeChurchServerTest(LiveServer, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        cls.root = pathlib.Path(cls.tmp.name)
        assert "onedrive" not in str(cls.root.resolve()).lower()
        cls.copy = cls.root / "fake"
        fake.build_fake_church(cls.copy)
        cls.start(cls.copy, cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.tmp.cleanup()

    def add_route(self, method, pattern, handler):
        self.httpd.routes.insert(0, server.compile_route(method, pattern, handler))
        self.addCleanup(self.httpd.routes.pop, 0)

    # ---- address and dashboard
    def test_binds_loopback_only(self):
        self.assertEqual(self.httpd.server_address[0], "127.0.0.1")

    def test_dashboard_has_six_panels_with_rows(self):
        status, headers, page = self.get_text("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html; charset=utf-8", headers["content-type"])
        self.assertIn('<meta charset="utf-8">', page)
        parsed = parse_panels(page)
        self.assertEqual(set(parsed.rows), PANELS)
        for name in DATA_PANELS:
            self.assertGreaterEqual(parsed.rows[name], 1, name)
        self.assertEqual(parsed.h1, 1)
        self.assertIn('lang="vi"', page)
        self.assertIn(fake.CHURCH_NAME, page)  # church name at the top of the sidebar
        self.assertIn("<svg", page)  # the Services line
        self.assertIn('action="/search"', page)  # search works without JS

    def test_dashboard_numbers(self):
        _s, _h, page = self.get_text("/")
        today = dt.date.today()
        conn = db.connect(self.copy / db.DB_NAME)
        try:
            totals = money.month_totals(conn, today.year, today.month)
            next_number = sent.next_number(conn, today.year)
        finally:
            conn.close()
        self.assertIn(money.format_vnd(totals["offerings"]), page)
        self.assertIn(money.format_vnd(totals["balance"]), page)
        self.assertIn(next_number, page)
        self.assertNotIn("PRIVATE-NOTE-MARKER", page)

    def test_security_headers(self):
        _s, headers, _p = self.request("GET", "/")
        self.assertEqual(headers["x-frame-options"], "DENY")
        self.assertIn("frame-ancestors 'none'", headers["content-security-policy"])
        self.assertEqual(headers["x-content-type-options"], "nosniff")

    # ---- search
    def search(self, q):
        status, headers, data = self.request("GET", "/api/search?q=" + urllib.parse.quote(q))
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["content-type"])
        return json.loads(data.decode("utf-8"))

    def test_api_search_without_accents(self):
        status, _h, data = self.request("GET", "/api/search?q=nguyen%20hai%20dang")
        self.assertEqual(status, 200)
        rows = json.loads(data.decode("utf-8"))
        self.assertIn(fake.FIRST_PERSON, [r["full_name"] for r in rows])
        self.assertEqual(set(rows[0]), {"id", "full_name", "status"})

    def test_api_search_with_accents_nfc_and_nfd(self):
        for q in ("Nguyễn", unicodedata.normalize("NFD", "Nguyễn Hải Đăng")):
            self.assertIn(fake.FIRST_PERSON, [r["full_name"] for r in self.search(q)], q)

    def test_api_search_empty(self):
        self.assertEqual(self.search(""), [])
        self.assertEqual(self.search("zzzz-nobody"), [])

    def test_search_page_without_js(self):
        status, _h, page = self.get_text("/search?q=nguyen+hai+dang")
        self.assertEqual(status, 200)
        self.assertIn(fake.FIRST_PERSON, page)
        self.assertIn("/people/", page)
        _s, _h, page = self.get_text("/search?q=zzzz-nobody")
        self.assertIn("No Person found", page)

    def test_values_are_escaped(self):
        conn = db.connect(self.copy / db.DB_NAME)
        try:
            people.add_person(conn, "<b>Lê Thử</b> Escape")
        finally:
            conn.close()
        _s, _h, page = self.get_text("/search?q=escape")
        self.assertIn("&lt;b&gt;Lê Thử&lt;/b&gt; Escape", page)
        self.assertNotIn("<b>Lê Thử</b>", page)
        _s, _h, page = self.get_text("/?msg=" + urllib.parse.quote("<i>hi</i>"))
        self.assertIn("&lt;i&gt;hi&lt;/i&gt;", page)

    # ---- safety
    def test_bad_host_is_refused(self):
        port = self.httpd.port
        for host in ("evil.example", f"evil.example:{port}", "127.0.0.1:1", f"192.168.1.5:{port}"):
            status, _h, _d = self.request("GET", "/", host=host)
            self.assertEqual(status, 403, host)
        self.assertEqual(self.request("POST", "/setup", {"church_name": "X"}, host="evil.example")[0], 403)
        self.assertEqual(self.request("GET", "/", host=f"localhost:{port}")[0], 200)

    def test_post_needs_same_origin(self):
        port = self.httpd.port
        form = {"church_name": "X"}
        bad = [
            {},  # no Origin, no Referer
            {"Origin": "http://evil.example"},
            {"Origin": "null"},
            {"Origin": f"http://127.0.0.1:{port + 1}"},
            {"Referer": "http://evil.example/page"},
            {"Origin": f"http://127.0.0.1:{port}", "Sec-Fetch-Site": "cross-site"},
        ]
        for headers in bad:
            status, _h, _d = self.request("POST", "/setup", form, headers=headers, origin=False)
            self.assertEqual(status, 403, headers)
        good = [{"Origin": f"http://127.0.0.1:{port}"}, {"Referer": f"http://localhost:{port}/setup"}]
        for headers in good:
            status, _h, _d = self.request("POST", "/setup", form, headers=headers, origin=False)
            self.assertEqual(status, 303, headers)  # a copy is open: /setup sends you to the Dashboard

    def test_body_over_limit_is_refused_before_reading(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.port, timeout=20)
        try:
            conn.putrequest("POST", "/setup", skip_host=True)
            conn.putheader("Host", f"127.0.0.1:{self.httpd.port}")
            conn.putheader("Origin", f"http://127.0.0.1:{self.httpd.port}")
            conn.putheader("Content-Type", "application/x-www-form-urlencoded")
            conn.putheader("Content-Length", str(server.MAX_BODY + 1))
            conn.endheaders()
            self.assertEqual(conn.getresponse().status, 413)
        finally:
            conn.close()

    def test_static_files_only_from_the_list(self):
        status, headers, data = self.request("GET", "/static/style.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", headers["content-type"])
        self.assertEqual(data, (ROOT / "web" / "style.css").read_bytes())
        self.assertEqual(self.request("GET", "/static/app.js")[0], 200)
        for path in ("/static/../app.py", "/static/%2e%2e/app.py", "/static/..%2fapp.py",
                     "/static/..%5capp.py", "/static/..\\app.py", "/static/", "/static/web/style.css",
                     "/app.py", "/static/../churchmgr/db.py"):
            status, _h, data = self.request("GET", path)
            self.assertIn(status, (403, 404), path)
            self.assertNotIn(b"import", data, path)

    # ---- framework
    def test_friendly_404(self):
        status, _h, page = self.get_text("/no-such-page")
        self.assertEqual(status, 404)
        self.assertIn("Page not found", page)
        self.assertIn('href="/people"', page)  # the navigation is there

    def test_friendly_500_hides_the_traceback(self):
        def boom(req):
            raise RuntimeError("secret-trace-text")
        self.add_route("GET", "/boom", boom)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            status, _h, page = self.get_text("/boom")
        self.assertEqual(status, 500)
        self.assertIn("Something went wrong", page)
        self.assertNotIn("secret-trace-text", page)
        self.assertNotIn("Traceback", page)
        self.assertIn("secret-trace-text", err.getvalue())  # it went to the console

    def test_value_error_shows_its_plain_message(self):
        def refuse(req):
            raise ValueError("Amount must be above 0 <here>.")
        self.add_route("GET", "/refuse", refuse)
        status, _h, page = self.get_text("/refuse")
        self.assertEqual(status, 400)
        self.assertIn("Amount must be above 0 &lt;here&gt;.", page)

    def test_route_params_and_method(self):
        seen = {}

        def show(req):
            seen.update(req.params, q=req.query.get("q"))
            return server.Response.json({"ok": True})
        self.add_route("GET", "/thing/<int:id>/<name>", show)
        status, _h, _d = self.request("GET", "/thing/42/Hu%E1%BB%87?q=a")
        self.assertEqual(status, 200)
        self.assertEqual(seen, {"id": 42, "name": "Huệ", "q": "a"})
        self.assertEqual(self.request("GET", "/thing/abc/x")[0], 404)
        self.assertEqual(self.request("POST", "/thing/1/x", {"a": "b"})[0], 405)

    def test_post_redirect_and_forms(self):
        got = {}

        def save(req):
            got.update(form=req.form, all=req.form_all, files={k: (n, len(b)) for k, (n, b) in req.files.items()})
            return server.Response.redirect(ui.url("/", msg="Saved"))
        self.add_route("POST", "/save", save)
        status, headers, _d = self.request("POST", "/save", {"name": unicodedata.normalize("NFD", "Đăng"),
                                                             "tag": "a"})
        self.assertEqual(status, 303)
        self.assertEqual(headers["location"], "/?msg=Saved")
        self.assertEqual(got["form"]["name"], "Đăng")  # NFC
        # multipart through the real server
        body, ctype = multipart_body({"note": "Ghi chú"}, {"file": ("Thư mời Hội Thánh.pdf", bytes(range(256)))})
        status, _h, _d = self.request("POST", "/save", body, headers={"Content-Type": ctype})
        self.assertEqual(status, 303)
        self.assertEqual(got["form"], {"note": "Ghi chú"})
        self.assertEqual(got["files"], {"file": ("Thư mời Hội Thánh.pdf", 256)})

    def test_dashboard_panel_error_keeps_the_frame(self):
        original = dashboard.money.month_totals

        def broken(*args):
            raise RuntimeError("disk gone")
        dashboard.money.month_totals = broken
        self.addCleanup(setattr, dashboard.money, "month_totals", original)
        with contextlib.redirect_stderr(io.StringIO()):
            status, _h, page = self.get_text("/")
        self.assertEqual(status, 200)
        self.assertEqual(set(parse_panels(page).rows), PANELS)
        self.assertIn("Could not load Money this month", page)


def multipart_body(fields, files):
    boundary = "----cmtestboundary7MA4YWxkTrZu0gW"
    out = b""
    for name, value in fields.items():
        out += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n').encode() \
            + value.encode("utf-8") + b"\r\n"
    for name, (filename, data) in files.items():
        out += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n").encode("utf-8") + data + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return out, f"multipart/form-data; boundary={boundary}"


class FirstRunTest(LiveServer, unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name) / "copies"
        self.start(None, self.root)
        self.addCleanup(self.stop)

    def test_first_run_sends_every_page_to_setup(self):
        for path in ("/", "/people", "/api/search?q=a", "/search?q=a"):
            status, headers, _d = self.request("GET", path)
            self.assertEqual(status, 303, path)
            self.assertEqual(headers["location"], "/setup", path)
        self.assertEqual(self.request("GET", "/static/style.css")[0], 200)
        status, _h, page = self.get_text("/setup")
        self.assertEqual(status, 200)
        self.assertIn('name="church_name"', page)
        self.assertIn("New church setup", page)

    def test_setup_makes_a_copy_and_opens_it(self):
        status, _h, data = self.request("POST", "/setup", {"church_name": "  "})
        self.assertEqual(status, 400)
        self.assertIn("Church name is required", data.decode("utf-8"))
        self.assertIsNone(self.httpd.copy_folder)

        status, headers, _d = self.request("POST", "/setup", {"church_name": "Hội Thánh Thử Nghiệm"})
        self.assertEqual(status, 303)
        self.assertTrue(headers["location"].startswith("/?msg="))
        folder = self.root / "hoi-thanh-thu-nghiem"
        self.assertTrue((folder / db.DB_NAME).is_file())
        self.assertEqual(self.httpd.copy_folder, folder.resolve())
        self.assertEqual(paths.read_current(self.root).resolve(), folder.resolve())

        status, _h, page = self.get_text(headers["location"])
        self.assertEqual(status, 200)
        parsed = parse_panels(page)
        self.assertEqual(set(parsed.rows), PANELS)
        self.assertIn("Hội Thánh Thử Nghiệm", page)
        self.assertIn("New church setup is done", page)  # the flash message
        for sentence in ("Nothing this week.", "No one needs a visit now.", "No Head count recorded yet.",
                         "No Offering or Expense recorded this month.", "No Sent document yet."):
            self.assertIn(sentence, page)
        self.assertIn("0 ₫", page)  # a real zero prints 0
        self.assertGreaterEqual(parsed.rows["money-month"], 3)
        self.assertEqual(self.request("GET", "/setup")[0], 303)  # setup is only for the first run


class SwitchCopyTest(unittest.TestCase):
    def test_current_txt_only_for_a_default_start(self):
        tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        for name in ("a", "b"):
            db.create_church_copy(root / name, f"Hội Thánh {name}").close()
        httpd = server.make_server(root / "a", root, 0, remember=False)
        try:
            httpd.switch_copy(root / "b")
            self.assertEqual(httpd.copy_folder, (root / "b").resolve())
            self.assertIsNone(paths.read_current(root))
            httpd.remember = True
            httpd.switch_copy(root / "a")
            self.assertEqual(paths.read_current(root).resolve(), (root / "a").resolve())
            with self.assertRaises(db.ChurchCopyError):
                httpd.switch_copy(root / "missing")
            self.assertEqual(httpd.copy_folder, (root / "a").resolve())  # unchanged after a refusal
        finally:
            httpd.server_close()


class AppStartTest(unittest.TestCase):
    def run_app(self, *argv):
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            code = app.main([*argv, "--no-browser"])
        return code, out.getvalue() + err.getvalue()

    def test_refuses_onedrive(self):
        tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        self.addCleanup(tmp.cleanup)
        code, text = self.run_app("--copy", str(pathlib.Path(tmp.name) / "OneDrive - Home" / "copy"))
        self.assertEqual(code, 2)
        self.assertIn("must not be inside OneDrive", text)

    def test_refuses_a_missing_copy(self):
        tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        self.addCleanup(tmp.cleanup)
        code, text = self.run_app("--copy", str(pathlib.Path(tmp.name) / "missing"))
        self.assertEqual(code, 2)
        self.assertIn("no church copy", text)

    def test_ports(self):
        self.assertEqual(app.candidate_ports(None), list(range(8765, 8786)))
        self.assertEqual(app.candidate_ports(9001), [9001])

    def test_busy_port_moves_to_the_next(self):
        tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        self.addCleanup(tmp.cleanup)
        busy = socket.socket()
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        self.addCleanup(busy.close)
        port = busy.getsockname()[1]
        httpd = app.start_server(None, pathlib.Path(tmp.name), [port, 0], remember=False)
        try:
            self.assertNotEqual(httpd.port, port)
            self.assertEqual(httpd.server_address[0], "127.0.0.1")
        finally:
            httpd.server_close()
        with self.assertRaises(OSError):
            app.start_server(None, pathlib.Path(tmp.name), [port], remember=False)


class SmallLogicTest(unittest.TestCase):
    def test_trend(self):
        self.assertEqual(dashboard.trend([]), (None, None))
        self.assertEqual(dashboard.trend([70]), (None, None))
        self.assertEqual(dashboard.trend([60, 80, 75]), ("Up", 70))
        self.assertEqual(dashboard.trend([60, 80, 65]), ("Down", 70))
        self.assertEqual(dashboard.trend([60, 80, 70]), ("Same", 70))
        self.assertEqual(dashboard.trend([1, 2, 2]), ("Up", 2))  # 1.5 rounds half up to 2; 2 > 1.5 is Up

    def test_nice_scale(self):
        self.assertEqual(dashboard.nice_scale(95), (100, 25))
        self.assertEqual(dashboard.nice_scale(60), (80, 20))
        self.assertEqual(dashboard.nice_scale(100), (150, 50))
        self.assertEqual(dashboard.nice_scale(4), (6, 2))
        self.assertEqual(dashboard.nice_scale(0), (1, 1))
        for m in (1, 7, 55, 99, 101, 999, 12345, 1_000_000):
            top, step = dashboard.nice_scale(m)
            self.assertGreater(top, m)
            self.assertLessEqual(top // step, 4)
            self.assertEqual(top % step, 0)

    def test_services_svg(self):
        rows = [{"starts_at": f"2026-10-{d:02d} 08:00", "count": c} for d, c in ((4, 60), (11, 82), (18, 75))]
        svg = dashboard.services_svg(rows)
        self.assertIn("<polyline", svg)
        self.assertIn("04/10", svg)
        self.assertIn(">75</text>", svg)  # the last value is labelled

    def test_ui_helpers(self):
        self.assertEqual(ui.fmt_date("2026-11-01"), "01/11/2026")
        self.assertEqual(ui.fmt_date("2026-11-01 08:30"), "01/11/2026")
        self.assertEqual(ui.fmt_datetime("2026-11-01 08:30"), "01/11/2026 08:30")
        self.assertEqual(ui.fmt_date(None), "—")
        self.assertEqual(ui.fmt_money(1250000), "1.250.000 ₫")
        self.assertEqual(ui.h('<a href="x">'), "&lt;a href=&quot;x&quot;&gt;")
        self.assertEqual(ui.url("/money/statement", person_id=5, year=2026, family_id=None),
                         "/money/statement?person_id=5&year=2026")
        self.assertIn('aria-invalid="true"', ui.field("Date", "date", "x", error="Bad date."))
        self.assertIn("selected", ui.select_field("Fund", "fund", [(1, "General"), (2, "Building")], selected=2))

    def test_content_disposition(self):
        header = server.content_disposition("Thư mời Hội Thánh.pdf")
        self.assertIn('filename="Thu moi Hoi Thanh.pdf"', header)
        self.assertIn("filename*=UTF-8''Th%C6%B0%20m%E1%BB%9Di%20H%E1%BB%99i%20Th%C3%A1nh.pdf", header)
        bad = server.content_disposition('a"b\r\n\\c.txt')
        self.assertNotIn("\r", bad)
        self.assertNotIn("\n", bad)
        self.assertIn('filename="a_b___c.txt"', bad)

    def test_parse_multipart(self):
        body, ctype = multipart_body({"note": "Ghi chú"}, {"file": ("Thư mời.pdf", bytes(range(256))),
                                                          "empty": ("", b"")})
        form, files = server.parse_multipart(ctype, body)
        self.assertEqual(form, {"note": ["Ghi chú"]})
        self.assertEqual(files, {"file": ("Thư mời.pdf", bytes(range(256)))})

    def test_duplicate_route_is_an_error(self):
        class A:
            ROUTES = [("GET", "/x", None)]
        with self.assertRaises(ValueError):
            server.build_routes([A, A])

    def test_no_avoid_words_in_pages_app_and_web(self):
        files = sorted((ROOT / "churchmgr" / "pages").glob("*.py")) + [ROOT / "app.py"] \
            + sorted((ROOT / "web").glob("*.*"))
        found = []
        for f in files:
            found += [(f.name, hit) for hit in test_db.CodeRulesTest.avoid_hits(f.read_text(encoding="utf-8"))]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
