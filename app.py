"""Start Church Manager and open the Dashboard in the browser.

    python app.py [--copy FOLDER] [--copies-root FOLDER] [--port N] [--no-browser]

With no options it opens the church copy named in ``current.txt`` of the default copies
folder (see ``churchmgr.paths``; first run: New church setup). The server listens on
127.0.0.1 only. Press Ctrl+C to stop.
"""

import argparse
import os
import sys
import webbrowser

from churchmgr import db, paths, server

DEFAULT_PORT = 8765
EXTRA_PORTS = 20  # when the default port is busy, try the next 20


def candidate_ports(port):
    """The ports to try: only ``port`` when it was given, else 8765 and the next 20."""
    if port is not None:
        return [port]
    return list(range(DEFAULT_PORT, DEFAULT_PORT + EXTRA_PORTS + 1))


def start_server(copy, root, ports, remember):
    """A server on the first free port of ``ports``. Raises ``OSError`` when all are busy."""
    last = None
    for port in ports:
        try:
            return server.make_server(copy, root, port, remember=remember)
        except OSError as exc:
            last = exc
    raise last if last else OSError("No port to try.")


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(prog="python app.py", description="Start Church Manager.")
    parser.add_argument("--copy", help="the church copy folder to open (outside OneDrive)")
    parser.add_argument("--copies-root", help="the folder that holds the church copies "
                                              f"(default {paths.default_copies_root()})".replace("%", "%%"))
    parser.add_argument("--port", type=int, help=f"port on 127.0.0.1 (default {DEFAULT_PORT}, "
                                                 f"or the next free one of the {EXTRA_PORTS} after it)")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    args = parser.parse_args(argv)

    explicit = bool(args.copy or os.environ.get(paths.ENV_COPY))
    try:
        copy, root = paths.resolve(args.copy, args.copies_root)
    except paths.CopyPathError as exc:
        print(f"Not started: {exc}", file=sys.stderr)
        return 2
    if copy is not None and not (copy / db.DB_NAME).is_file():
        if explicit:
            print(f"Not started: there is no church copy in {copy} ({db.DB_NAME} is missing).", file=sys.stderr)
            return 2
        print(f"The church copy named in {paths.CURRENT_FILE} was not found: {copy}")
        print("The app opens New church setup instead.")
        copy = None

    try:
        httpd = start_server(copy, root, candidate_ports(args.port), remember=not explicit)
    except db.ChurchCopyError as exc:
        print(f"Not started: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        which = f"Port {args.port} is" if args.port is not None else \
            f"Ports {DEFAULT_PORT} to {DEFAULT_PORT + EXTRA_PORTS} are"
        print(f"Not started: {which} busy ({exc}). Close the other program or use --port.", file=sys.stderr)
        return 2

    print(f"Church Manager is running at {httpd.url}")
    print(f"Church copy:   {copy if copy is not None else '(none yet: New church setup)'}")
    print(f"Copies folder: {root}")
    print("Keep this window open while you work. Press Ctrl+C to stop.")
    if not args.no_browser:
        webbrowser.open(httpd.url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
