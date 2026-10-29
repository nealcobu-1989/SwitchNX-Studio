"""Tiny local server: serves the page and maps POST /api/<method> to Api.

Used for the browser fallback and for development. Listens on 127.0.0.1 only.
"""
from __future__ import annotations

import json
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def serve(api, web_dir: Path, port: int = 8765, open_browser: bool = True):
    web_dir = Path(web_dir)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(web_dir), **kw)

        def log_message(self, *a):  # quiet
            pass

        def do_POST(self):
            if not self.path.startswith("/api/"):
                self.send_error(404)
                return
            # Only our own page may call the API: a custom header can't be sent
            # cross-site without a preflight (which we never answer), and the
            # Origin, when present, must be this server.
            origin = self.headers.get("Origin")
            if self.headers.get("X-SkyNX") != "1" or (
                    origin and origin not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")):
                self.send_error(403)
                return
            name = self.path[5:]
            fn = getattr(api, name, None)
            if name.startswith("_") or not callable(fn):
                self.send_error(404)
                return
            n = int(self.headers.get("Content-Length") or 0)
            args = json.loads(self.rfile.read(n) or b"[]")
            try:
                out = fn(*args)
                body = json.dumps(out, ensure_ascii=False, default=str).encode("utf-8")
                self.send_response(200)
            except Exception as e:  # noqa: BLE001
                body = json.dumps({"ok": False, "error": str(e)}).encode()
                self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/index.html?mode=server"
    print(f"SwitchNX Studio: {url}")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    httpd.serve_forever()
