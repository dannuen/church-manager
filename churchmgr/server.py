"""The local web server: one church copy, pages from ``churchmgr.pages``, files from ``web/``.

Safety rules (card B):
- Binds ``127.0.0.1`` only.
- Every request needs ``Host: 127.0.0.1:<port>`` or ``localhost:<port>`` (stops DNS rebinding), else 403.
- Every POST needs an ``Origin`` or ``Referer`` of this same server, else 403 (stops other web pages).
- A body over ``MAX_BODY`` gets 413 before it is read.
- Static files come only from the fixed ``STATIC_FILES`` list in ``web/``.
- Each request opens its own SQLite connection (``db.connect``) and closes it after.

A page module has ``ROUTES = [("GET", "/people/<int:id>", handler), ...]``. A handler takes a
:class:`Request` and returns a :class:`Response`. Path parts ``<int:name>`` and ``<name>`` land in
``req.params``. A ``ValueError`` that leaves a handler is shown as a plain 400 page with its message.
"""

import html
import json as _json
import os
import re
import threading
import traceback
import unicodedata
import urllib.parse
from email import policy as _policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import db, paths, settings, ui

HOST = "127.0.0.1"
MAX_BODY = 60 * 1024 * 1024  # bytes
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
STATIC_FILES = {
    "style.css": "text/css; charset=utf-8",
    "print.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
}
# No inline <script>: JS lives only in web/app.js. No framing by other pages (clickjacking).
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
FIRST_RUN_OPEN = {"/setup"}  # the only pages that work before a church copy is open


class Response:
    """What a handler returns. Use the helpers: ``Response.html``, ``.redirect``, ``.file``, ``.json``."""

    def __init__(self, status=200, body=b"", content_type="text/html; charset=utf-8", headers=None):
        self.status = status
        self.body = body
        self.headers = {"Content-Type": content_type, **(headers or {})}

    @classmethod
    def html(cls, body, status=200):
        return cls(status, body.encode("utf-8"))

    @classmethod
    def redirect(cls, url):
        """303 See Other to a path of this server (POST-redirect-GET)."""
        if not url.startswith("/") or url.startswith("//"):
            raise ValueError(f"Redirect only to a page of this app, not {url!r}.")
        return cls(303, b"", headers={"Location": url})

    @classmethod
    def json(cls, obj, status=200):
        return cls(status, _json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    @classmethod
    def file(cls, path, download_name=None):
        """The bytes of ``path`` as a download named ``download_name`` (Vietnamese names keep their accents)."""
        name = download_name or Path(path).name
        return cls(200, Path(path).read_bytes(), "application/octet-stream",
                   {"Content-Disposition": content_disposition(name)})


def content_disposition(name):
    """``attachment; filename="<ascii>"; filename*=UTF-8''<percent-encoded NFC name>`` (RFC 6266)."""
    name = unicodedata.normalize("NFC", name)
    ascii_name = unicodedata.normalize("NFKD", name.replace("đ", "d").replace("Đ", "D"))
    ascii_name = ascii_name.encode("ascii", "ignore").decode("ascii")
    ascii_name = re.sub(r'[^A-Za-z0-9._ -]', "_", ascii_name).strip() or "document"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{urllib.parse.quote(name, safe='')}"


class Request:
    """One request. ``query`` and ``form`` hold the first value of each field (NFC text);
    ``query_all`` / ``form_all`` hold every value. ``files`` is ``{field: (file name, bytes)}``.
    ``state`` is the server (``copy_folder``, ``copies_root``, ``port``, ``switch_copy``).
    ``conn`` opens the church copy on first use; the server closes it after the response."""

    def __init__(self, state, method, path, query_all, form_all=None, files=None, headers=None, params=None):
        self.state = state
        self.method = method
        self.path = path
        self.query_all = query_all
        self.form_all = form_all or {}
        self.query = {k: v[0] for k, v in query_all.items()}
        self.form = {k: v[0] for k, v in self.form_all.items()}
        self.files = files or {}
        self.headers = headers
        self.params = params or {}
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            if self.state.copy_folder is None:
                raise RuntimeError("No church copy is open.")
            self._conn = db.connect(self.state.copy_folder / db.DB_NAME)
        return self._conn

    @property
    def church_name(self):
        """The church name of the open copy, or ``None`` when no copy is open (first run)."""
        if self.state.copy_folder is None:
            return None
        return settings.get_setting(self.conn, "church_name") or "Church"

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None


class HTTPError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------- parsing

def _nfc_lists(pairs):
    out = {}
    for key, values in pairs.items():
        out[unicodedata.normalize("NFC", key)] = [unicodedata.normalize("NFC", v) for v in values]
    return out


def parse_query(raw):
    """``a=1&b=Nguy%E1%BB%85n`` -> ``{"a": ["1"], "b": ["Nguyễn"]}`` (NFC, blanks kept)."""
    return _nfc_lists(urllib.parse.parse_qs(raw, keep_blank_values=True, encoding="utf-8", errors="replace"))


def parse_multipart(content_type, body):
    """Parse a ``multipart/form-data`` body (the stdlib ``cgi`` module is gone).

    Returns ``(form_all, files)``: text fields as ``{name: [values]}`` and files as
    ``{name: (file name, bytes)}``. An empty file field (no file chosen) is left out.
    """
    head = b"Content-Type: " + content_type.encode("latin-1") + b"\r\nMIME-Version: 1.0\r\n\r\n"
    msg = BytesParser(policy=_policy.HTTP).parsebytes(head + body)
    if not msg.is_multipart():
        raise HTTPError(400, "The form could not be read.")
    form_all, files = {}, {}
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        name = unicodedata.normalize("NFC", str(name))
        data = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename is not None:
            if filename or data:
                files[name] = (unicodedata.normalize("NFC", filename), data)
            continue
        value = data.decode(part.get_content_charset() or "utf-8", errors="replace")
        form_all.setdefault(name, []).append(unicodedata.normalize("NFC", value))
    return form_all, files


# ---------------------------------------------------------------- routes

_PARAM = re.compile(r"<(?:(int):)?([A-Za-z_][A-Za-z0-9_]*)>")


def compile_route(method, pattern, handler):
    """``("GET", "/people/<int:id>", f)`` -> ``(method, regex, converters, handler, pattern)``."""
    regex, converters, pos = "", {}, 0
    for m in _PARAM.finditer(pattern):
        regex += re.escape(pattern[pos:m.start()])
        kind, name = m.group(1), m.group(2)
        regex += f"(?P<{name}>[0-9]+)" if kind == "int" else f"(?P<{name}>[^/]+)"
        converters[name] = int if kind == "int" else str
        pos = m.end()
    regex += re.escape(pattern[pos:])
    return (method.upper(), re.compile(f"^{regex}$"), converters, handler, pattern)


def build_routes(modules):
    """All ``ROUTES`` of the page modules, compiled. A route given twice is an error."""
    routes, seen = [], set()
    for module in modules:
        for method, pattern, handler in module.ROUTES:
            key = (method.upper(), pattern)
            if key in seen:
                raise ValueError(f"Route {method} {pattern} is defined twice.")
            seen.add(key)
            routes.append(compile_route(method, pattern, handler))
    return routes


# ---------------------------------------------------------------- server

class ChurchServer(ThreadingHTTPServer):
    """The HTTP server and the app state: ``copy_folder`` (or ``None``), ``copies_root``, ``port``."""

    daemon_threads = True
    # On Windows SO_REUSEADDR lets a second server take a busy port; we want the bind to fail instead.
    allow_reuse_address = os.name != "nt"

    def __init__(self, port, copy_folder, copies_root, remember, routes):
        self.copy_folder = None
        self.copies_root = paths.check_not_onedrive(copies_root)
        self.remember = remember
        self.routes = routes
        self.log_requests = False
        super().__init__((HOST, port), _Handler)
        self.port = self.server_address[1]
        if copy_folder is not None:
            try:
                self.switch_copy(copy_folder, write_current=False)
            except BaseException:
                self.server_close()
                raise

    @property
    def url(self):
        return f"http://{HOST}:{self.port}/"

    def switch_copy(self, folder, write_current=True):
        """Open the church copy in ``folder`` for every next request.

        Checks the copy first (``church.db`` there, right version, not in OneDrive), and that the
        copies root is not this folder or inside it (Handover zips and New church setups would then
        be saved inside the church copy). Nothing is written before these checks pass.
        Writes ``current.txt`` in the copies root only when the app was started the
        default way (``remember``); a ``--copy`` start never changes it.
        """
        folder = paths.check_not_onedrive(folder)
        root = self.copies_root
        if root == folder or root.is_relative_to(folder):  # Windows paths compare without case
            where = "is the church copy folder itself" if root == folder else f"is inside the church copy {folder}"
            raise db.ChurchCopyError(
                f"The copies folder {root} {where}, so Handover zips and New church setups would be saved "
                "in the church copy: choose a copies folder outside it.")
        db.open_church_copy(folder).close()
        self.copy_folder = folder
        if write_current and self.remember:
            paths.write_current(self.copies_root, folder)
        return folder


def make_server(copy_folder, copies_root, port=0, remember=True):
    """A ready server on ``127.0.0.1:port`` (0 = any free port). Call ``serve_forever()`` to run it.

    ``copy_folder`` ``None`` = first run: every page sends you to New church setup.
    """
    from . import pages  # late import: pages import this module
    return ChurchServer(port, copy_folder, copies_root, remember, build_routes(pages.PAGES))


class _Handler(BaseHTTPRequestHandler):
    server_version = "ChurchManager"
    sys_version = ""

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def log_message(self, format, *args):  # noqa: A002 - name from the stdlib
        if self.server.log_requests:
            super().log_message(format, *args)

    # ---- one request
    def _handle(self, method):
        self._req = None
        self._body_read = False
        try:
            try:
                resp = self._respond(method)
            except HTTPError as exc:
                self._drain_small_body()
                resp = _plain(exc.status, str(exc))
            except Exception:
                traceback.print_exc()
                resp = _error_page(None, 500)
            self._send(resp)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        finally:
            ui.set_request(None)
            if self._req is not None:
                self._req.close()

    def _drain_small_body(self):
        """Read an unread small body before a refusal, so the client sees the status, not a reset."""
        raw = self.headers.get("Content-Length") or ""
        if not self._body_read and raw.isdigit() and int(raw) <= 1024 * 1024:
            self.rfile.read(int(raw))
            self._body_read = True

    def _allowed_hosts(self):
        port = self.server.port
        return {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _check_host(self):
        if (self.headers.get("Host") or "").strip().lower() not in self._allowed_hosts():
            raise HTTPError(403, "Forbidden: this app only answers http://127.0.0.1 on its own port.")

    def _check_same_origin(self):
        allowed = {f"http://{h}" for h in self._allowed_hosts()}
        origin = self.headers.get("Origin")
        referer = self.headers.get("Referer")
        if origin is not None:
            ok = origin.strip().lower() in allowed
        elif referer:
            parts = urllib.parse.urlsplit(referer.strip())
            ok = f"{parts.scheme}://{parts.netloc}".lower() in allowed
        else:
            ok = False
        site = self.headers.get("Sec-Fetch-Site")
        if site is not None and site not in ("same-origin", "none"):
            ok = False
        if not ok:
            raise HTTPError(403, "Forbidden: a change must come from a page of this app.")

    def _read_body(self):
        if self.headers.get("Transfer-Encoding"):
            raise HTTPError(411, "Length required.")
        raw = self.headers.get("Content-Length") or "0"
        if not raw.isdigit():
            raise HTTPError(400, "Bad Content-Length.")
        length = int(raw)
        if length > MAX_BODY:
            self.close_connection = True
            raise HTTPError(413, f"Too large: the limit is {MAX_BODY // (1024 * 1024)} MB.")
        body = self.rfile.read(length) if length else b""
        self._body_read = True
        if len(body) != length:
            raise HTTPError(400, "The request body was cut short.")
        return body

    def _respond(self, method):
        self._check_host()
        raw_path, _, raw_query = self.path.partition("?")
        raw_query = raw_query.partition("#")[0]
        path = urllib.parse.unquote(raw_path, errors="replace")

        if path.startswith("/static/"):
            if method != "GET":
                raise HTTPError(405, "Method not allowed.")
            return _static(path[len("/static/"):])
        if path == "/favicon.ico":
            return _plain(404, "Not found.")

        form_all, files = {}, {}
        if method == "POST":
            body = self._read_body()  # read first (size is checked): a reply before the body resets the socket
            self._check_same_origin()
            ctype = self.headers.get("Content-Type") or ""
            if ctype.lower().startswith("multipart/form-data"):
                form_all, files = parse_multipart(ctype, body)
            elif ctype.lower().startswith("application/x-www-form-urlencoded"):
                form_all = parse_query(body.decode("latin-1"))

        req = self._req = Request(self.server, method, path, parse_query(raw_query), form_all, files,
                                  self.headers)
        ui.set_request(req)

        if self.server.copy_folder is None and path not in FIRST_RUN_OPEN:
            return Response.redirect("/setup")

        allowed = []
        for r_method, regex, converters, handler, _pattern in self.server.routes:
            m = regex.match(path)
            if m is None:
                continue
            if r_method != method:
                allowed.append(r_method)
                continue
            req.params = {k: converters[k](v) for k, v in m.groupdict().items()}
            try:
                return handler(req)
            except (ValueError, db.ChurchCopyError) as exc:
                return _message_page(400, "Not done", str(exc))
        if allowed:
            return _message_page(405, "Not allowed", "This page cannot be opened that way.")
        return _error_page(req, 404)

    def _send(self, resp):
        body = resp.body if isinstance(resp.body, bytes) else resp.body.encode("utf-8")
        self.send_response(resp.status)
        headers = {
            "Content-Length": str(len(body)),
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": CSP,
            "Cache-Control": "no-store",
            **resp.headers,
        }
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------- built-in responses

def _plain(status, message):
    return Response(status, message.encode("utf-8"), "text/plain; charset=utf-8")


def _static(name):
    ctype = STATIC_FILES.get(name)  # fixed list: "../app.py" and friends are simply not in it
    if ctype is None:
        return _plain(404, "Not found.")
    return Response(200, (WEB_DIR / name).read_bytes(), ctype, {"Cache-Control": "no-cache"})


def _message_page(status, title, message):
    body = f'<p class="lead">{html.escape(message)}</p><p>Use the Back button of the browser, fix it and try again.</p>'
    try:
        return Response.html(ui.page(title, body), status)
    except Exception:
        traceback.print_exc()
        return Response.html(ui.bare_page(title, body), status)


def _error_page(req, status):
    """Friendly 404 / 500 page. The traceback goes only to the console."""
    if status == 404:
        title, body = "Page not found", '<p class="lead">This page does not exist.</p><p><a href="/">Go to the Dashboard</a></p>'
    else:
        title = "Something went wrong"
        body = ('<p class="lead">Something went wrong on this page.</p>'
                '<p>Try again. If it happens again, close Church Manager and start it again.</p>'
                '<p><a href="/">Go to the Dashboard</a></p>')
    if req is not None and status == 404:
        try:
            return Response.html(ui.page(title, body), status)
        except Exception:
            traceback.print_exc()
    return Response.html(ui.bare_page(title, body), status)


def serve_in_thread(server):
    """Start ``server.serve_forever`` in a daemon thread (tests and verify.py). Returns the thread."""
    thread = threading.Thread(target=server.serve_forever, name="church-manager", daemon=True)
    thread.start()
    return thread
