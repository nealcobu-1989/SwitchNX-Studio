"""Single instance: a second launch hands its nxm:// link to the running window.

The running app listens on 127.0.0.1, on the first free port of PORTS, and
writes ``{"port", "token", "pid"}`` to a token file in the settings folder.
A second process reads that file, connects, sends one JSON line
``{"token": ..., "nxm": "nxm://..."}`` (or ``{"token": ..., "focus": true}``)
and exits when the answer is ``{"ok": true}``. Other local programs can't
inject links without reading the token file, which only the user can read.

Typical use in main.py::

    srv = ipc.claim(token_file, on_message, url=nxm_arg)
    if srv is None:      # another window took it
        sys.exit(0)
"""
from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import socket
import threading
from pathlib import Path
from typing import Callable

HOST = "127.0.0.1"
PORTS = range(47811, 47816)
MAX_MSG = 8192
MAX_URL = 4096
_NXM = re.compile(r"(?i)^nxm://[^\s\x00-\x1f\x7f]+$")


def valid_nxm(url) -> bool:
    return isinstance(url, str) and len(url) <= MAX_URL and bool(_NXM.match(url))


def _read_token(token_file) -> dict | None:
    try:
        d = json.loads(Path(token_file).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or not isinstance(d.get("token"), str):
        return None
    if not isinstance(d.get("port"), int) or not (0 < d["port"] < 65536):
        return None
    return d


def _write_token(token_file: Path, data: dict):
    token_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = token_file.with_name(token_file.name + f".{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp, token_file)


def _recv_line(conn: socket.socket, limit: int = MAX_MSG) -> bytes | None:
    buf = b""
    while b"\n" not in buf:
        chunk = conn.recv(1024)
        if not chunk:
            break
        buf += chunk
        if len(buf) > limit:
            return None
    return buf.split(b"\n", 1)[0]


class Server:
    """Listens for hand-offs. ``on_message(msg)`` gets ``{"nxm": url}`` or
    ``{"focus": True}``, on the server's thread (keep it short)."""

    def __init__(self, token_file, on_message: Callable[[dict], None], ports=PORTS,
                 host: str = HOST):
        self.token_file = Path(token_file)
        self.on_message = on_message
        self.ports, self.host = list(ports), host
        self.token = secrets.token_urlsafe(32)
        self.port: int | None = None
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def __repr__(self):
        return f"Server(port={self.port}, running={self.running})"

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> int:
        last = None
        for port in self.ports:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):  # Windows: nobody can share the port
                s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                s.bind((self.host, port))
                s.listen(4)
            except OSError as e:
                last = e
                s.close()
                continue
            s.settimeout(0.5)
            self._sock, self.port = s, port
            break
        if self._sock is None:
            raise OSError(f"no free port in {self.ports[0]}-{self.ports[-1]}") from last
        _write_token(self.token_file, {"port": self.port, "token": self.token, "pid": os.getpid()})
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="skynx-ipc", daemon=True)
        self._thread.start()
        return self.port

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        d = _read_token(self.token_file)
        if d and d.get("token") == self.token:
            try:
                self.token_file.unlink()
            except OSError:
                pass

    def _loop(self):
        while not self._stop.is_set():
            try:
                conn, _addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                conn.settimeout(2.0)
                try:
                    reply = self._handle(_recv_line(conn))
                    conn.sendall((json.dumps(reply) + "\n").encode())
                except (OSError, socket.timeout):
                    pass

    def _handle(self, raw: bytes | None) -> dict:
        if not raw:
            return {"ok": False, "error": "empty or too big"}
        try:
            msg = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return {"ok": False, "error": "bad json"}
        if not isinstance(msg, dict):
            return {"ok": False, "error": "bad json"}
        tok = msg.get("token")
        if not isinstance(tok, str) or not hmac.compare_digest(tok.encode(), self.token.encode()):
            return {"ok": False, "error": "bad token"}
        if msg.get("ping") is True:
            return {"ok": True}
        if "nxm" in msg:
            if not valid_nxm(msg["nxm"]):
                return {"ok": False, "error": "not an nxm link"}
            out = {"nxm": msg["nxm"]}
        elif msg.get("focus") is True:
            out = {"focus": True}
        else:
            return {"ok": False, "error": "unknown message"}
        try:
            self.on_message(out)
        except Exception:  # noqa: BLE001  the sender shouldn't wait on our bugs
            pass
        return {"ok": True}


def _talk(token_file, payload: dict, timeout: float) -> bool:
    d = _read_token(token_file)
    if not d:
        return False
    payload = dict(payload, token=d["token"])
    data = (json.dumps(payload) + "\n").encode()
    if len(data) > MAX_MSG:
        return False
    try:
        with socket.create_connection((HOST, d["port"]), timeout=timeout) as s:
            s.settimeout(timeout)
            s.sendall(data)
            line = _recv_line(s)
    except OSError:
        return False
    try:
        return bool(line) and json.loads(line.decode("utf-8")).get("ok") is True
    except (UnicodeDecodeError, ValueError, AttributeError):
        return False


def send(token_file, message, timeout: float = 3.0) -> bool:
    """Hands ``message`` (an nxm URL, or ``{"nxm": url}`` / ``{"focus": True}``) to the
    running instance. True when it was accepted."""
    if isinstance(message, str):
        message = {"nxm": message}
    if not isinstance(message, dict):
        return False
    if "nxm" in message:
        if not valid_nxm(message["nxm"]):
            return False
        message = {"nxm": message["nxm"]}
    elif message.get("focus") is True:
        message = {"focus": True}
    else:
        return False
    return _talk(token_file, message, timeout)


def is_running(token_file, timeout: float = 1.0) -> bool:
    return _talk(token_file, {"ping": True}, timeout)


def claim(token_file, on_message: Callable[[dict], None], url: str | None = None,
          timeout: float = 3.0, ports=PORTS) -> Server | None:
    """Hands ``url`` (or a focus request) to a running instance and returns None, or
    becomes the running instance and returns its started Server."""
    msg = {"nxm": url} if url and valid_nxm(url) else {"focus": True}
    if _read_token(token_file) and send(token_file, msg, timeout):
        return None
    srv = Server(token_file, on_message, ports=ports)
    srv.start()
    return srv
