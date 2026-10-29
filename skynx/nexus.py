"""Nexus Mods integration: nxm links, the public REST API (v1) and downloads.

Facts this module relies on (Nexus Mods public API, checked 2026-10):

* Base URL ``https://api.nexusmods.com/v1``; the personal API key goes in the
  ``apikey`` header. The acceptable use policy asks every client to send
  ``Application-Name`` (stable across versions) and ``Application-Version``
  (the current release).
* Rate limits are reported on every response in ``X-RL-Hourly-Limit``,
  ``X-RL-Hourly-Remaining``, ``X-RL-Hourly-Reset``, ``X-RL-Daily-Limit``,
  ``X-RL-Daily-Remaining`` and ``X-RL-Daily-Reset``; going over returns 429.
* ``download_link.json`` needs ``key`` and ``expires`` from the nxm link for
  non-Premium users; Premium users can ask without them.
* ``md5_search`` returns a list of ``{"mod": {...}, "file_details": {...}}``
  and 404 when nothing matches.

Only ``urllib`` is used. The API key is never written to logs, exceptions,
messages or reprs.
"""
from __future__ import annotations

import email.message
import hashlib
import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from . import __version__
from .errors import SkynxError

GAME = "skyrimspecialedition"
API_BASE = "https://api.nexusmods.com/v1"
SITE = "https://www.nexusmods.com"
APP_NAME = "SwitchNX Studio"

# category_id -> category_name as files.json reports them
CATEGORY_BY_ID = {1: "MAIN", 2: "UPDATE", 3: "OPTIONAL", 4: "OLD_VERSION",
                  5: "MISCELLANEOUS", 6: "DELETED", 7: "ARCHIVED"}
LIVE_CATEGORIES = ("MAIN", "UPDATE", "OPTIONAL", "MISCELLANEOUS")
DEAD_CATEGORIES = ("OLD_VERSION", "DELETED", "ARCHIVED", "REMOVED")

RL_HEADERS = {"hourly_limit": "X-RL-Hourly-Limit", "hourly_remaining": "X-RL-Hourly-Remaining",
              "hourly_reset": "X-RL-Hourly-Reset", "daily_limit": "X-RL-Daily-Limit",
              "daily_remaining": "X-RL-Daily-Remaining", "daily_reset": "X-RL-Daily-Reset"}


class NexusError(SkynxError):
    """Error from the Nexus side, in both languages.

    ``kind`` lets the window react: bad_key, expired_link, premium, not_found,
    rate_limit, network, http, bad_link, other_game, bad_name, md5, cancelled.
    """

    def __init__(self, en: str, es: str | None = None, kind: str = "http",
                 status: int | None = None):
        super().__init__(en, es)
        self.kind, self.status = kind, status

    def __repr__(self) -> str:
        return f"NexusError(kind={self.kind!r}, status={self.status!r}, en={self.en!r})"


def _err(kind: str, code: int | None = None, /, **kw) -> NexusError:
    en, es = _MESSAGES[kind]
    return NexusError(en.format(**kw), es.format(**kw), kind=kind, status=code)


_MESSAGES = {
    "bad_link": ("This is not a Nexus mod download link (nxm://...): {why}",
                 "Esto no es un enlace de descarga de Nexus (nxm://...): {why}"),
    "other_game": ("The link is for the game '{game}'. SwitchNX Studio only works with Skyrim "
                   "Special Edition (skyrimspecialedition).",
                   "El enlace es del juego '{game}'. SwitchNX Studio solo trabaja con Skyrim "
                   "Special Edition (skyrimspecialedition)."),
    "collection": ("Nexus collections are not supported. Download the mods one by one with "
                   "'Mod Manager Download'.",
                   "Las colecciones de Nexus no están soportadas. Descarga los mods uno por uno "
                   "con 'Mod Manager Download'."),
    "no_key": ("There is no Nexus API key yet. Paste yours in Settings (nexusmods.com, "
               "Settings, API Keys, Personal API Key).",
               "Todavía no hay clave de API de Nexus. Pega la tuya en Ajustes (nexusmods.com, "
               "Settings, API Keys, Personal API Key)."),
    "bad_key": ("Nexus rejected the API key. Copy it again from nexusmods.com (Settings, API "
                "Keys) and paste it in Settings.",
                "Nexus rechazó la clave de API. Cópiala otra vez desde nexusmods.com (Settings, "
                "API Keys) y pégala en Ajustes."),
    "expired_link": ("The download link expired or belongs to another account. Click 'Mod "
                     "Manager Download' on Nexus again.",
                     "El enlace de descarga venció o es de otra cuenta. Vuelve a hacer clic en "
                     "'Mod Manager Download' en Nexus."),
    "premium": ("Direct downloads without a link need Nexus Premium. Click 'Mod Manager "
                "Download' on the mod's Files tab instead.",
                "Las descargas directas sin enlace necesitan Nexus Premium. Usa 'Mod Manager "
                "Download' en la pestaña Files del mod."),
    "not_found": ("Nexus can't find {what}. It may have been hidden, removed or moved.",
                  "Nexus no encuentra {what_es}. Puede que lo hayan ocultado, borrado o movido."),
    "rate_limit": ("Nexus request limit reached. It resets {when}. Try again then.",
                   "Se alcanzó el límite de consultas a Nexus. Se renueva {when_es}. Intenta "
                   "de nuevo entonces."),
    "network": ("Could not reach Nexus ({why}). Check the internet connection and try again.",
                "No se pudo conectar con Nexus ({why}). Revisa la conexión a internet y vuelve "
                "a intentar."),
    "http": ("Nexus answered with an error (HTTP {status}){detail}.",
             "Nexus respondió con un error (HTTP {status}){detail}."),
    "bad_answer": ("Nexus sent an answer that could not be read.",
                   "Nexus mandó una respuesta que no se pudo leer."),
    "bad_md5": ("'{value}' is not an MD5 hash (32 hexadecimal characters).",
                "'{value}' no es un hash MD5 (32 caracteres hexadecimales)."),
    "bad_name": ("Refusing the file name '{name}': {why}.",
                 "Se rechaza el nombre de archivo '{name}': {why_es}."),
    "md5": ("The downloaded file is damaged (MD5 {got}, Nexus says {want}). It was deleted; "
            "download it again.",
            "El archivo descargado está dañado (MD5 {got}, Nexus dice {want}). Se borró; "
            "descárgalo otra vez."),
    "short": ("The download stopped early ({done} of {total} bytes). Try again: it will resume.",
              "La descarga se cortó antes de terminar ({done} de {total} bytes). Intenta de "
              "nuevo: sigue donde quedó."),
    "cancelled": ("Download cancelled. What was already downloaded is kept to resume later.",
                  "Descarga cancelada. Lo ya descargado se guarda para seguir después."),
}


# ===================================================================== nxm links
@dataclass(frozen=True)
class NxmLink:
    game: str
    mod_id: int
    file_id: int
    key: str | None = None
    expires: int | None = None
    user_id: int | None = None

    def expired(self, now: float | None = None) -> bool:
        return self.expires is not None and (now if now is not None else time.time()) >= self.expires

    def __repr__(self) -> str:  # the download key is short-lived but still personal
        return (f"NxmLink(game={self.game!r}, mod_id={self.mod_id}, file_id={self.file_id}, "
                f"key={'***' if self.key else None}, expires={self.expires}, user_id={self.user_id})")


def parse_nxm(url: str) -> NxmLink:
    """``nxm://skyrimspecialedition/mods/{mod}/files/{file}?key=..&expires=..&user_id=..``"""
    if not isinstance(url, str) or not url.strip():
        raise _err("bad_link", why="empty / vacío")
    s = url.strip().strip('"').strip("'").strip()
    # Some launchers hand over the whole link percent-encoded (nxm%3A%2F%2F...).
    for _ in range(3):
        if re.match(r"(?i)^[a-z][a-z0-9+.-]*%3A", s):
            s = urllib.parse.unquote(s)
        else:
            break
    if len(s) > 4096:
        raise _err("bad_link", why="too long / demasiado largo")
    parts = urllib.parse.urlsplit(s)
    if parts.scheme.lower() != "nxm":
        raise _err("bad_link", why=f"scheme '{parts.scheme or '?'}'")
    game = urllib.parse.unquote(parts.netloc).strip().lower()
    segs = [urllib.parse.unquote(p) for p in parts.path.split("/") if p]
    if game != GAME:
        if not game:
            raise _err("bad_link", why="no game / sin juego")
        raise _err("other_game", game=game)
    if segs and segs[0].lower() == "collections":
        raise _err("collection")
    if len(segs) != 4 or segs[0].lower() != "mods" or segs[2].lower() != "files":
        raise _err("bad_link", why="expected /mods/<id>/files/<id>")
    try:
        mod_id, file_id = int(segs[1]), int(segs[3])
    except ValueError:
        raise _err("bad_link", why="ids must be numbers / los ids deben ser números") from None
    if mod_id <= 0 or file_id <= 0:
        raise _err("bad_link", why="ids must be positive / los ids deben ser positivos")
    q = urllib.parse.parse_qs(parts.query, keep_blank_values=False)

    def one(name):
        v = q.get(name)
        return v[0].strip() if v else None

    key = one("key")
    if key is not None and not re.fullmatch(r"[A-Za-z0-9_\-+/=.~]{1,512}", key):
        raise _err("bad_link", why="odd key / clave rara")

    def num(name):
        v = one(name)
        if v is None or v == "":
            return None
        try:
            return int(v)
        except ValueError:
            raise _err("bad_link", why=f"{name} must be a number / debe ser un número") from None

    return NxmLink(game, mod_id, file_id, key or None, num("expires"), num("user_id"))


def mod_page(mod_id: int, game: str = GAME) -> str:
    return f"{SITE}/{game}/mods/{int(mod_id)}?tab=files"


def file_page(mod_id: int, file_id: int, game: str = GAME) -> str:
    """Opens the 'Mod Manager Download' prompt for one file (the site then fires nxm://)."""
    return f"{SITE}/{game}/mods/{int(mod_id)}?tab=files&file_id={int(file_id)}&nmm=1"


# ===================================================================== API client
def _hget(headers, name: str):
    if headers is None:
        return None
    try:
        v = headers.get(name)
        if v is not None:
            return v
    except Exception:  # noqa: BLE001
        pass
    try:
        low = name.lower()
        for k, v in headers.items():
            if k.lower() == low:
                return v
    except Exception:  # noqa: BLE001
        pass
    return None


def _parse_time(v: str | None) -> float | None:
    if not v:
        return None
    s = v.strip()
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return float(s)
    return _iso(s)


def _iso(s: str) -> float | None:
    s = re.sub(r"\s*([+-]\d{2})(\d{2})$", r"\1:\2", s.replace(" UTC", "+00:00"))
    s = s.replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()


def _when(ts: float | None, now: float) -> tuple[str, str]:
    if ts is None:
        return "later", "más tarde"
    mins = max(1, int(round((ts - now) / 60)))
    if mins < 90:
        return f"in about {mins} min", f"en unos {mins} min"
    hours = int(round(mins / 60))
    return f"in about {hours} h", f"en unas {hours} h"


class Client:
    """Small client for the Nexus Mods v1 REST API.

    ``opener`` is anything with ``open(request, timeout=...)`` (like
    ``urllib.request.OpenerDirector``) or a plain callable ``(request, timeout)``;
    tests inject a fake one. ``sleep`` and ``clock`` are injectable too.
    """

    RETRY_STATUS = (429, 500, 502, 503, 504)

    def __init__(self, api_key: str, app_name: str = APP_NAME, app_version: str = __version__,
                 opener=None, *, game: str = GAME, base_url: str = API_BASE,
                 timeout: float = 30.0, retries: int = 3, max_wait: float = 30.0,
                 cache_ttl: float = 300.0, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.time):
        self.__key = (api_key or "").strip()
        self.app_name, self.app_version = app_name, app_version
        self.game, self.base_url = game, base_url.rstrip("/")
        self.timeout, self.retries, self.max_wait = timeout, retries, max_wait
        self.cache_ttl = cache_ttl
        self._opener = opener or urllib.request.build_opener()
        self._sleep, self._clock = sleep, clock
        self._cache: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()
        self.rate_limits: dict = {}
        self.requests_made = 0

    # ------------------------------------------------------------- plumbing
    def __repr__(self) -> str:
        return (f"Client(app={self.app_name!r}, version={self.app_version!r}, "
                f"key={'set' if self.__key else 'missing'})")

    __str__ = __repr__

    @property
    def has_key(self) -> bool:
        return bool(self.__key)

    def headers(self) -> dict:
        return {"apikey": self.__key, "Application-Name": self.app_name,
                "Application-Version": self.app_version, "Accept": "application/json",
                "User-Agent": f"{self.app_name}/{self.app_version} (Python urllib)"}

    def clear_cache(self):
        with self._lock:
            self._cache.clear()

    def _redact(self, text: str) -> str:
        return text.replace(self.__key, "***") if self.__key and text else text

    def _record_limits(self, headers):
        got = {}
        for k, h in RL_HEADERS.items():
            v = _hget(headers, h)
            if v is None:
                continue
            if k.endswith("_reset"):
                got[k] = str(v)
                got[k + "_ts"] = _parse_time(str(v))
            else:
                try:
                    got[k] = int(str(v).strip())
                except ValueError:
                    pass
        if got:
            with self._lock:
                self.rate_limits.update(got)

    def rate_limit(self) -> dict:
        """Latest numbers Nexus reported: hourly/daily limit, remaining, reset."""
        with self._lock:
            return dict(self.rate_limits)

    def _open(self, req):
        if hasattr(self._opener, "open"):
            return self._opener.open(req, timeout=self.timeout)
        return self._opener(req, self.timeout)

    def _rate_error(self, status=429) -> NexusError:
        rl = self.rate_limit()
        ts = None
        if rl.get("daily_remaining") == 0:
            ts = rl.get("daily_reset_ts")
        if ts is None:
            ts = rl.get("hourly_reset_ts")
        en, es = _when(ts, self._clock())
        return _err("rate_limit", status, when=en, when_es=es)

    def _wait_for(self, attempt: int, status: int | None, headers) -> float | None:
        """Seconds to wait before retrying, or None when it's not worth waiting."""
        if status == 429:
            ra = _hget(headers, "Retry-After")
            if ra is not None:
                try:
                    w = float(str(ra).strip())
                except ValueError:
                    t = _iso(str(ra))
                    w = (t - self._clock()) if t else None
                if w is not None:
                    return max(0.0, w) if w <= self.max_wait else None
            rl = self.rate_limit()
            if rl.get("daily_remaining") == 0 and rl.get("hourly_remaining") == 0:
                return None
            if rl.get("hourly_remaining") == 0 and rl.get("hourly_reset_ts"):
                w = rl["hourly_reset_ts"] - self._clock()
                return max(0.0, w) if w <= self.max_wait else None
        return min(self.max_wait, 1.0 * (2 ** attempt))

    def _request(self, path: str, query: dict | None = None, *, what: tuple[str, str] = ("it", "eso"),
                 context: str = "") -> object:
        if not self.__key:
            raise _err("no_key")
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
        last: NexusError | None = None
        for attempt in range(self.retries + 1):
            req = urllib.request.Request(url, headers=self.headers(), method="GET")
            status, headers, body = None, None, b""
            try:
                self.requests_made += 1
                resp = self._open(req)
                try:
                    status = getattr(resp, "status", None) or resp.getcode()
                    headers = resp.headers
                    body = resp.read()
                finally:
                    close = getattr(resp, "close", None)
                    if close:
                        close()
            except urllib.error.HTTPError as e:
                status, headers = e.code, e.headers
                try:
                    body = e.read() or b""
                except Exception:  # noqa: BLE001
                    body = b""
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as e:
                why = getattr(e, "reason", None) or e.__class__.__name__
                last = _err("network", why=self._redact(str(why))[:120])
                if attempt < self.retries:
                    self._sleep(min(self.max_wait, 2 ** attempt))
                    continue
                raise last from None
            self._record_limits(headers)
            if status is not None and 200 <= status < 300:
                try:
                    return json.loads(body.decode("utf-8") or "null")
                except (ValueError, UnicodeDecodeError):
                    raise _err("bad_answer", status) from None
            if status in self.RETRY_STATUS and attempt < self.retries:
                wait = self._wait_for(attempt, status, headers)
                if wait is not None:
                    self._sleep(wait)
                    continue
            raise self._map_error(status, body, what, context) from None
        raise last or _err("network", why="?")

    def _map_error(self, status, body: bytes, what, context: str) -> NexusError:
        if status == 429:
            return self._rate_error(status)
        if status == 401:
            return _err("bad_key", status)
        if status in (403, 410) and context == "download":
            return _err("expired_link", status)
        if status == 403 and context == "premium":
            return _err("premium", status)
        if status == 403:
            return _err("bad_key", status)
        if status == 404:
            return _err("not_found", status, what=what[0], what_es=what[1])
        detail = ""
        try:
            msg = json.loads(body.decode("utf-8")).get("message")
            if isinstance(msg, str) and msg.strip():
                detail = ": " + self._redact(msg.strip())[:200]
        except Exception:  # noqa: BLE001
            pass
        return _err("http", status, status=status if status is not None else "?", detail=detail)

    def _cached(self, path: str, what) -> object:
        now = self._clock()
        with self._lock:
            hit = self._cache.get(path)
            if hit and hit[0] > now:
                return hit[1]
        data = self._request(path, what=what)
        if self.cache_ttl > 0:
            with self._lock:
                self._cache[path] = (now + self.cache_ttl, data)
        return data

    # ------------------------------------------------------------- endpoints
    def validate(self) -> dict:
        """``{user_id, name, is_premium, is_supporter, profile_url}``; the key is not echoed back."""
        d = self._request("/users/validate.json", what=("your account", "tu cuenta"))
        if not isinstance(d, dict):
            raise _err("bad_answer")
        return {"user_id": d.get("user_id"), "name": d.get("name"),
                "is_premium": bool(d.get("is_premium")),
                "is_supporter": bool(d.get("is_supporter")),
                "profile_url": d.get("profile_url")}

    def mod(self, mod_id: int) -> dict:
        mod_id = int(mod_id)
        return self._cached(f"/games/{self.game}/mods/{mod_id}.json",
                            (f"mod {mod_id}", f"el mod {mod_id}"))

    def files(self, mod_id: int) -> dict:
        """``{"files": [...], "file_updates": [{old_file_id, new_file_id, ...}]}``"""
        mod_id = int(mod_id)
        d = self._cached(f"/games/{self.game}/mods/{mod_id}/files.json",
                         (f"the files of mod {mod_id}", f"los archivos del mod {mod_id}"))
        if not isinstance(d, dict):
            raise _err("bad_answer")
        d.setdefault("files", [])
        d.setdefault("file_updates", [])
        return d

    def file(self, mod_id: int, file_id: int) -> dict:
        mod_id, file_id = int(mod_id), int(file_id)
        return self._cached(f"/games/{self.game}/mods/{mod_id}/files/{file_id}.json",
                            (f"file {file_id} of mod {mod_id}",
                             f"el archivo {file_id} del mod {mod_id}"))

    def download_links(self, link: NxmLink | int, file_id: int | None = None) -> list[dict]:
        """CDN links ``[{name, short_name, url}]``, preferred first.

        Pass the parsed nxm link (non-Premium) or ``mod_id, file_id`` (Premium only).
        """
        if isinstance(link, NxmLink):
            if link.game != self.game:
                raise _err("other_game", game=link.game)
            if link.expired(self._clock()):
                raise _err("expired_link")
            mod_id, fid = link.mod_id, link.file_id
            query = {"key": link.key, "expires": link.expires} if link.key else None
            context = "download" if link.key else "premium"
        else:
            if file_id is None:
                raise TypeError("download_links(mod_id, file_id) needs file_id")
            mod_id, fid, query, context = int(link), int(file_id), None, "premium"
        d = self._request(f"/games/{self.game}/mods/{mod_id}/files/{fid}/download_link.json",
                          query, what=(f"file {fid} of mod {mod_id}",
                                       f"el archivo {fid} del mod {mod_id}"), context=context)
        if not isinstance(d, list):
            raise _err("bad_answer")
        out = []
        for e in d:
            if isinstance(e, dict) and isinstance(e.get("URI"), str):
                out.append({"name": e.get("name") or "", "short_name": e.get("short_name") or "",
                            "url": e["URI"]})
        return out

    def preview(self, url: str) -> object:
        """A file's content listing (content_preview_link). Not an API call:
        only https links on nexusmods.com hosts are followed, without the key."""
        from urllib.parse import urlparse
        u = urlparse(str(url or ""))
        host = (u.hostname or "").lower()
        if u.scheme != "https" or not (host == "nexusmods.com" or host.endswith(".nexusmods.com")):
            raise NexusError("That isn't a Nexus link.", "Ese no es un enlace de Nexus.", kind="bad_url")
        now = self._clock()
        with self._lock:
            hit = self._cache.get(url)
            if hit and hit[0] > now:
                return hit[1]
        req = urllib.request.Request(url, headers={"User-Agent": f"{self.app_name}/{self.app_version}",
                                                   "Accept": "application/json"})
        try:
            with self._open(req) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:  # noqa: BLE001
            raise NexusError(f"Couldn't read the file list from Nexus: {e}",
                             f"No pude leer la lista de archivos de Nexus: {e}", kind="http") from e
        with self._lock:
            self._cache[url] = (now + max(self.cache_ttl, 3600), data)
        return data

    def md5_search(self, md5: str) -> list[dict]:
        """Files on Nexus with this MD5: ``[{mod_id, file_id, mod_name, file_name, version,
        category, mod_version, size_kb, md5, uploaded_timestamp, game}]``. [] if none."""
        h = (md5 or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{32}", h):
            raise _err("bad_md5", value=(md5 or "")[:40])
        try:
            d = self._request(f"/games/{self.game}/mods/md5_search/{h}.json",
                              what=("that MD5", "ese MD5"))
        except NexusError as e:
            if e.kind == "not_found":
                return []
            raise
        if isinstance(d, dict):
            d = [d]
        out = []
        for e in d or []:
            if not isinstance(e, dict):
                continue
            m, f = e.get("mod") or {}, e.get("file_details") or {}
            out.append({
                "mod_id": m.get("mod_id"), "file_id": f.get("file_id"),
                "mod_name": m.get("name") or "", "file_name": f.get("name") or f.get("file_name") or "",
                "archive_name": f.get("file_name") or "",
                "version": f.get("version") or f.get("mod_version") or m.get("version") or "",
                "mod_version": m.get("version") or "",
                "category": category_of(f),
                "size_kb": f.get("size_kb"), "md5": (f.get("md5") or h).lower(),
                "uploaded_timestamp": f.get("uploaded_timestamp"),
                "game": m.get("domain_name") or self.game})
        return out


def category_of(f: dict) -> str:
    name = f.get("category_name")
    if isinstance(name, str) and name.strip():
        return name.strip().upper()
    return CATEGORY_BY_ID.get(f.get("category_id"), "UNKNOWN")


# ===================================================================== updates
def _latest_main(files: list[dict]) -> dict | None:
    mains = [f for f in files if category_of(f) == "MAIN"]
    if not mains:
        return None
    prim = [f for f in mains if f.get("is_primary")]
    pool = prim or mains
    return max(pool, key=lambda f: (f.get("uploaded_timestamp") or 0, f.get("file_id") or 0))


def follow_updates(file_id: int, file_updates: list[dict]) -> int:
    """Walks the old_file_id -> new_file_id chain to its end."""
    nxt: dict[int, tuple[int, int]] = {}
    for u in file_updates or []:
        try:
            old, new = int(u["old_file_id"]), int(u["new_file_id"])
        except (KeyError, TypeError, ValueError):
            continue
        ts = u.get("uploaded_timestamp") or 0
        if old not in nxt or ts >= nxt[old][1]:
            nxt[old] = (new, ts)
    seen, cur = {file_id}, file_id
    while cur in nxt:
        new = nxt[cur][0]
        if new in seen:
            break
        seen.add(new)
        cur = new
    return cur


def check_updates(client: Client, mods: Iterable[dict]) -> list[dict]:
    """For each ``{mod_id, file_id, version}`` (plus optional ``name``) returns
    ``{mod_id, file_id, current, latest, latest_file_id, name, file_name, category,
    status, changed, error}``. status: ok, update, removed or error."""
    out = []
    for m in mods:
        mod_id = int(m["mod_id"])
        fid = m.get("file_id")
        fid = int(fid) if fid not in (None, "") else None
        row = {"mod_id": mod_id, "file_id": fid, "current": m.get("version") or "",
               "latest": "", "latest_file_id": fid, "name": m.get("name") or "",
               "file_name": "", "category": "", "status": "ok", "changed": False, "error": None}
        try:
            data = client.files(mod_id)
        except NexusError as e:
            if e.kind in ("bad_key", "rate_limit", "no_key"):
                raise
            row.update(status="removed" if e.kind == "not_found" else "error",
                       error={"en": e.en, "es": e.es})
            out.append(row)
            continue
        files = [f for f in data.get("files", []) if isinstance(f, dict)]
        by_id = {f.get("file_id"): f for f in files}
        cur = by_id.get(fid) if fid is not None else None
        chain = None
        if fid is not None:
            end = follow_updates(fid, data.get("file_updates", []))
            if end != fid and end in by_id:
                chain = by_id[end]

        def live(f):
            return f is not None and category_of(f) not in DEAD_CATEGORIES
        if live(chain):
            target = chain
        elif live(cur):
            target = cur
        else:
            target = _latest_main(files) or chain
        if cur is not None and not row["current"]:
            row["current"] = cur.get("version") or cur.get("mod_version") or ""
        if cur is not None and not row["name"]:
            row["name"] = cur.get("name") or ""
        if target is None:
            row["status"] = "removed" if fid is not None and cur is None else "ok"
            out.append(row)
            continue
        row["latest"] = target.get("version") or target.get("mod_version") or ""
        row["latest_file_id"] = target.get("file_id")
        row["file_name"] = target.get("file_name") or ""
        row["category"] = category_of(target)
        if not row["name"]:
            row["name"] = target.get("name") or ""
        if fid is None:
            changed = bool(row["latest"]) and row["latest"] != row["current"]
        else:
            changed = row["latest_file_id"] != fid
        row["changed"] = changed
        row["status"] = "update" if changed else "ok"
        out.append(row)
    return out


# ===================================================================== downloads
_RESERVED = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
             *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10)),
             "COM¹", "COM²", "COM³", "LPT¹", "LPT²", "LPT³"}
_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def check_filename(name: str) -> str:
    """Returns ``name`` if it is a safe plain Windows file name, raises NexusError otherwise."""
    def bad(why, why_es):
        return NexusError(*(t.format(name=(name or "")[:80], why=why, why_es=why_es)
                            for t in _MESSAGES["bad_name"]), kind="bad_name")
    if not name or not name.strip():
        raise bad("it is empty", "está vacío")
    if "/" in name or "\\" in name or name in (".", "..") or ".." in Path(name.replace("\\", "/")).parts:
        raise bad("it points to another folder", "apunta a otra carpeta")
    if _BAD_CHARS.search(name):
        raise bad("it has characters Windows doesn't allow", "tiene caracteres que Windows no permite")
    if name[-1] in " .":
        raise bad("it ends with a dot or a space", "termina en punto o espacio")
    if name.split(".")[0].strip().upper() in _RESERVED:
        raise bad("it is a reserved Windows name", "es un nombre reservado de Windows")
    if len(name) > 200:
        raise bad("it is too long", "es demasiado largo")
    return name


def filename_from_disposition(value: str | None) -> str | None:
    if not value:
        return None
    msg = email.message.Message()
    msg["Content-Disposition"] = value
    try:
        name = msg.get_filename()
    except Exception:  # noqa: BLE001
        return None
    return name.strip() if name else None


def filename_from_url(url: str) -> str | None:
    path = urllib.parse.urlsplit(url).path
    last = path.rsplit("/", 1)[-1] if path else ""
    last = urllib.parse.unquote(last)
    return last or None


def file_md5(path: str | os.PathLike, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _numbered(p: Path, n: int) -> Path:
    return p.with_name(f"{p.stem} ({n}){p.suffix}")


def _existing_same(target: Path, md5: str) -> Path | None:
    if target.is_file() and file_md5(target) == md5:
        return target
    for n in range(2, 100):
        c = _numbered(target, n)
        if not c.exists():
            break
        if c.is_file() and file_md5(c) == md5:
            return c
    return None


def _free_name(target: Path) -> Path:
    if not target.exists():
        return target
    for n in range(2, 10000):
        c = _numbered(target, n)
        if not c.exists():
            return c
    raise FileExistsError(str(target))


def _inside(dest: Path, p: Path) -> Path:
    rp = p.resolve()
    if rp.parent != dest.resolve():
        raise NexusError(*(t.format(name=p.name, why="it points to another folder",
                                    why_es="apunta a otra carpeta") for t in _MESSAGES["bad_name"]),
                         kind="bad_name")
    return p


def download(url: str, dest_dir: str | os.PathLike, progress: Callable | None = None,
             filename: str | None = None, expected_md5: str | None = None,
             cancel: Callable[[], bool] | None = None, *, opener=None, timeout: float = 60.0,
             label: str | None = None, chunk: int = 1 << 20, identity: str | None = None) -> Path:
    """Downloads ``url`` into ``dest_dir`` and returns the final path.

    ``identity`` (e.g. "mod:file") guards resuming: a leftover ``.part`` from
    a different file with the same name is discarded instead of extended.

    Streams to ``<name>.part`` and resumes it with ``Range`` when possible. The
    name comes from ``filename``, else Content-Disposition, else the URL. An
    existing file with the same content is reused; a different one is never
    overwritten (``name (2).7z``). ``progress(label, done, total)``; ``cancel()``
    returning True stops it (the .part is kept).
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    want = (expected_md5 or "").strip().lower() or None
    if want and not re.fullmatch(r"[0-9a-f]{32}", want):
        raise _err("bad_md5", value=want[:40])
    guess = filename or filename_from_url(url)
    if guess:
        check_filename(guess)
    else:
        guess = "download-" + hashlib.sha1(urllib.parse.urlsplit(url).path.encode()).hexdigest()[:10]
    label = label or guess
    if want:
        same = _existing_same(_inside(dest, dest / guess), want)
        if same:
            if progress:
                sz = same.stat().st_size
                progress(label, sz, sz)
            return same
    part = _inside(dest, dest / (guess + ".part"))
    op = opener or urllib.request.build_opener()

    def fetch(start: int):
        hdr = {"User-Agent": f"{APP_NAME}/{__version__} (Python urllib)", "Accept": "*/*"}
        if start:
            hdr["Range"] = f"bytes={start}-"
        req = urllib.request.Request(url, headers=hdr)
        try:
            return op.open(req, timeout=timeout) if hasattr(op, "open") else op(req, timeout)
        except urllib.error.HTTPError as e:
            return e
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as e:
            why = getattr(e, "reason", None) or e.__class__.__name__
            raise _err("network", why=str(why)[:120]) from None

    if identity is not None:
        idf = part.with_name(part.name + ".id")
        try:
            same = idf.exists() and idf.read_text(encoding="utf-8") == identity
        except OSError:
            same = False
        if part.exists() and not same:
            part.unlink(missing_ok=True)
        try:
            idf.write_text(identity, encoding="utf-8")
        except OSError:
            pass
    start = part.stat().st_size if part.exists() else 0
    resp = fetch(start)
    status = getattr(resp, "status", None) or getattr(resp, "code", None) or resp.getcode()
    total = None
    try:
        if status == 416 and start:
            cr = _hget(resp.headers, "Content-Range") or ""
            m = re.search(r"/(\d+)\s*$", cr)
            resp.close()
            if m and int(m.group(1)) == start:
                total = start      # the .part is already complete
                resp = None
            else:
                part.unlink(missing_ok=True)
                start = 0
                resp = fetch(0)
                status = getattr(resp, "status", None) or getattr(resp, "code", None) or resp.getcode()
        if resp is not None:
            if status == 404:
                raise _err("not_found", 404, what="that download", what_es="esa descarga")
            if status in (401, 403, 410):
                raise _err("expired_link", status)
            if not (200 <= status < 300):
                raise _err("http", status, status=status, detail="")
            cd_name = filename_from_disposition(_hget(resp.headers, "Content-Disposition"))
            if cd_name and not filename:
                check_filename(cd_name)
            else:
                cd_name = None
            mode = "wb"
            length = _hget(resp.headers, "Content-Length")
            length = int(length) if length and str(length).strip().isdigit() else None
            if status == 206 and start:
                cr = _hget(resp.headers, "Content-Range") or ""
                m = re.match(r"\s*bytes\s+(\d+)-(\d+)/(\d+|\*)", cr)
                if m and int(m.group(1)) == start:
                    mode = "ab"
                    total = int(m.group(3)) if m.group(3) != "*" else None
                else:   # a range we didn't ask for: start over
                    resp.close()
                    part.unlink(missing_ok=True)
                    return download(url, dest, progress, filename, expected_md5, cancel,
                                    opener=opener, timeout=timeout, label=label, chunk=chunk,
                                    identity=identity)
            else:
                start = 0
                total = length
            done = start
            if progress:
                progress(label, done, total)
            with open(part, mode) as fh:
                while True:
                    if cancel and cancel():
                        raise _err("cancelled")
                    b = resp.read(chunk)
                    if not b:
                        break
                    fh.write(b)
                    done += len(b)
                    if progress:
                        progress(label, done, total)
            if total is not None and done < total:
                raise _err("short", done=done, total=total)
            guess = cd_name or guess
    finally:
        if resp is not None:
            try:
                resp.close()
            except Exception:  # noqa: BLE001
                pass
    got = file_md5(part)
    if want and got != want:
        part.unlink(missing_ok=True)
        raise _err("md5", got=got, want=want)
    target = _inside(dest, dest / guess)
    same = _existing_same(target, got)
    if same:
        part.unlink(missing_ok=True)
        return same
    final = _inside(dest, _free_name(target))
    os.replace(part, final)
    if progress:
        sz = final.stat().st_size
        progress(label, sz, sz)
    return final
