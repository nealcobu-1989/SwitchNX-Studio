"""Nexus integration: nxm links, API client, downloads, updates, nxm handler, single instance."""
import email.message
import hashlib
import http.server
import io
import json
import socket
import sys
import threading
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))
from skynx import nexus as N  # noqa: E402
from skynx import nxm as X  # noqa: E402
import ipc  # noqa: E402

KEY = "SECRETKEY-abc123-very-private=="


# ================================================================ nxm links
def test_parse_nxm_good():
    l = N.parse_nxm("nxm://skyrimspecialedition/mods/12604/files/35407?key=AbC-12_x&expires=1700000000&user_id=42")
    assert (l.game, l.mod_id, l.file_id, l.key, l.expires, l.user_id) == (
        "skyrimspecialedition", 12604, 35407, "AbC-12_x", 1700000000, 42)
    assert "AbC" not in repr(l)
    assert l.expired(now=1700000001) and not l.expired(now=1600000000)
    # no query (Premium users can still use it)
    l2 = N.parse_nxm('  "NXM://SkyrimSpecialEdition/mods/1/files/2"  ')
    assert (l2.mod_id, l2.file_id, l2.key, l2.expires) == (1, 2, None, None)


def test_parse_nxm_encoded():
    enc = "nxm%3A%2F%2Fskyrimspecialedition%2Fmods%2F266%2Ffiles%2F999%3Fkey%3Dk%252Fz%26expires%3D5%26user_id%3D7"
    l = N.parse_nxm(enc)
    assert (l.mod_id, l.file_id, l.key, l.expires, l.user_id) == (266, 999, "k/z", 5, 7)
    l = N.parse_nxm("nxm://skyrimspecialedition/mods/266/files/999?key=a%2Bb%3D&expires=5")
    assert l.key == "a+b="


@pytest.mark.parametrize("url", ["https://www.nexusmods.com/skyrimspecialedition/mods/1",
                                 "nexus://skyrimspecialedition/mods/1/files/2", "", "nxm://",
                                 "nxm://skyrimspecialedition/mods/x/files/2",
                                 "nxm://skyrimspecialedition/mods/1",
                                 "nxm://skyrimspecialedition/mods/1/files/2?expires=soon"])
def test_parse_nxm_bad(url):
    with pytest.raises(N.NexusError) as e:
        N.parse_nxm(url)
    assert e.value.kind == "bad_link" and e.value.es != e.value.en


def test_parse_nxm_other_game_and_collections():
    with pytest.raises(N.NexusError) as e:
        N.parse_nxm("nxm://skyrim/mods/1/files/2?key=a&expires=1")
    assert e.value.kind == "other_game" and "skyrim" in e.value.en and "solo" in e.value.es
    with pytest.raises(N.NexusError) as e:
        N.parse_nxm("nxm://skyrimspecialedition/collections/qdurkx/revisions/3")
    assert e.value.kind == "collection"


# ================================================================ fake transport
def _headers(d):
    m = email.message.Message()
    for k, v in (d or {}).items():
        m[k] = str(v)
    return m


class Resp:
    def __init__(self, status, body=b"", headers=None):
        self.status, self._b, self.headers = status, io.BytesIO(body), _headers(headers)

    def read(self, n=-1):
        return self._b.read(n)

    def getcode(self):
        return self.status

    def close(self):
        pass


RL = {"X-RL-Hourly-Limit": 500, "X-RL-Hourly-Remaining": 499, "X-RL-Hourly-Reset": "2026-10-24T15:00:00+00:00",
      "X-RL-Daily-Limit": 20000, "X-RL-Daily-Remaining": 19990, "X-RL-Daily-Reset": "2026-10-25 00:00:00 +0000"}


class FakeOpener:
    """routes: path -> list of (status, json_or_bytes, headers); last entry repeats."""

    def __init__(self, routes, raise_http=True):
        self.routes, self.calls, self.raise_http = routes, [], raise_http

    def open(self, req, timeout=None):
        self.calls.append(req)
        path = req.full_url.split("api.nexusmods.com/v1", 1)[1]
        key = path.split("?", 1)[0]
        seq = self.routes[key]
        status, body, hdr = seq.pop(0) if len(seq) > 1 else seq[0]
        body = body if isinstance(body, bytes) else json.dumps(body).encode()
        hdr = {**RL, **(hdr or {})}
        if status >= 400 and self.raise_http:
            raise urllib.error.HTTPError(req.full_url, status, "err", _headers(hdr), io.BytesIO(body))
        return Resp(status, body, hdr)


def _client(routes, **kw):
    op = FakeOpener(routes, raise_http=kw.pop("raise_http", True))
    sleeps = []
    c = N.Client(KEY, app_version="9.9.9", opener=op, sleep=sleeps.append,
                 clock=lambda: 1792854000.0, **kw)  # 2026-10-24T14:20Z
    return c, op, sleeps


def test_headers_and_validate_hide_key():
    c, op, _ = _client({"/users/validate.json": [(200, {"user_id": 7, "key": KEY, "name": "Ale",
                                                        "email": "a@b", "is_premium": False,
                                                        "is_supporter": False,
                                                        "profile_url": "https://x"}, None)]})
    me = c.validate()
    assert me == {"user_id": 7, "name": "Ale", "is_premium": False, "is_supporter": False,
                  "profile_url": "https://x"}
    req = op.calls[0]
    h = {k.lower(): v for k, v in req.header_items()}
    assert h["apikey"] == KEY and h["application-name"] == "SwitchNX Studio"
    assert h["application-version"] == "9.9.9"
    assert KEY not in req.full_url and KEY not in repr(c) and KEY not in str(c)
    rl = c.rate_limit()
    assert rl["hourly_remaining"] == 499 and rl["daily_limit"] == 20000
    assert rl["daily_reset_ts"] == 1792886400.0


@pytest.mark.parametrize("raise_http", [True, False])
def test_error_mapping_and_no_leak(raise_http):
    c, _, _ = _client({
        "/users/validate.json": [(401, {"message": f"Please provide a valid API Key ({KEY})"}, None)],
        "/games/skyrimspecialedition/mods/5.json": [(404, {"message": "No Mod Found"}, None)],
        "/games/skyrimspecialedition/mods/6.json": [(400, {"message": f"weird {KEY}"}, None)],
        "/games/skyrimspecialedition/mods/1/files/2/download_link.json": [(403, {}, None)],
    }, raise_http=raise_http)
    with pytest.raises(N.NexusError) as e:
        c.validate()
    assert e.value.kind == "bad_key" and e.value.status == 401
    with pytest.raises(N.NexusError) as e2:
        c.mod(5)
    assert e2.value.kind == "not_found" and "5" in e2.value.es
    with pytest.raises(N.NexusError) as e3:
        c.mod(6)
    assert e3.value.kind == "http" and "***" in e3.value.en
    link = N.parse_nxm("nxm://skyrimspecialedition/mods/1/files/2?key=k&expires=1792900000")
    with pytest.raises(N.NexusError) as e4:
        c.download_links(link)
    assert e4.value.kind == "expired_link"
    with pytest.raises(N.NexusError) as e5:
        c.download_links(1, 2)
    assert e5.value.kind == "premium"
    for err in (e, e2, e3, e4, e5):
        blob = err.value.en + err.value.es + repr(err.value) + str(err.value)
        assert KEY not in blob
        assert err.value.__cause__ is None


def test_expired_link_checked_locally():
    c, op, _ = _client({})
    link = N.parse_nxm("nxm://skyrimspecialedition/mods/1/files/2?key=k&expires=100")
    with pytest.raises(N.NexusError) as e:
        c.download_links(link)
    assert e.value.kind == "expired_link" and not op.calls


def test_download_links_with_key():
    path = "/games/skyrimspecialedition/mods/1/files/2/download_link.json"
    c, op, _ = _client({path: [(200, [{"name": "Nexus CDN", "short_name": "Nexus CDN",
                                      "URI": "https://cf-files.nexusmods.com/cdn/1704/1/a.7z?md5=x"}], None)]})
    link = N.parse_nxm("nxm://skyrimspecialedition/mods/1/files/2?key=abc&expires=1792900000&user_id=3")
    assert c.download_links(link) == [{"name": "Nexus CDN", "short_name": "Nexus CDN",
                                       "url": "https://cf-files.nexusmods.com/cdn/1704/1/a.7z?md5=x"}]
    assert "key=abc" in op.calls[0].full_url and "expires=1792900000" in op.calls[0].full_url


def test_rate_limit_retry_then_ok():
    path = "/games/skyrimspecialedition/mods/3.json"
    c, op, sleeps = _client({path: [(429, {"msg": "slow"}, {"Retry-After": "2"}),
                                    (503, b"oops", None), (200, {"mod_id": 3, "name": "SkyUI"}, None)]})
    assert c.mod(3)["name"] == "SkyUI"
    assert len(op.calls) == 3 and sleeps[0] == 2.0 and len(sleeps) == 2
    assert c.mod(3)["name"] == "SkyUI" and len(op.calls) == 3      # cached


def test_rate_limit_exhausted_does_not_wait():
    path = "/games/skyrimspecialedition/mods/3.json"
    c, op, sleeps = _client({path: [(429, {}, {"X-RL-Hourly-Remaining": 0, "X-RL-Daily-Remaining": 0})]})
    with pytest.raises(N.NexusError) as e:
        c.mod(3)
    assert e.value.kind == "rate_limit" and len(op.calls) == 1 and not sleeps
    assert "h" in e.value.en and "límite" in e.value.es


def test_cache_ttl():
    path = "/games/skyrimspecialedition/mods/3/files.json"
    now = [1000.0]
    op = FakeOpener({path: [(200, {"files": [], "file_updates": []}, None)]})
    c = N.Client(KEY, opener=op, clock=lambda: now[0], cache_ttl=60)
    c.files(3); c.files(3)
    assert len(op.calls) == 1
    now[0] += 61
    c.files(3)
    assert len(op.calls) == 2


def test_no_key():
    c = N.Client("", opener=FakeOpener({}))
    with pytest.raises(N.NexusError) as e:
        c.validate()
    assert e.value.kind == "no_key"


# md5_search: list of {"mod": IModInfo, "file_details": IFileInfo} (Nexus-Mods/node-nexus-api types)
MD5_RESPONSE = [{
    "mod": {"name": "SkyUI", "summary": "Elegant, PC-friendly interface mod", "version": "5.2SE",
            "mod_id": 12604, "game_id": 1704, "domain_name": "skyrimspecialedition",
            "category_id": 42, "author": "SkyUI Team", "available": True, "status": "published",
            "created_timestamp": 1508525279, "updated_timestamp": 1508534012},
    "file_details": {"file_id": 35407, "name": "SkyUI", "version": "5.2SE", "category_id": 1,
                     "category_name": "MAIN", "is_primary": True, "size": 2726, "size_kb": 2726,
                     "file_name": "SkyUI_5_2_SE-12604-5-2SE.7z", "uploaded_timestamp": 1508534012,
                     "mod_version": "5.2SE", "md5": "1d3b6d8c4b2a2c1f2fd4f9f3d8a0a4b1"}}]


def test_md5_search():
    h = "1d3b6d8c4b2a2c1f2fd4f9f3d8a0a4b1"
    c, _, _ = _client({f"/games/skyrimspecialedition/mods/md5_search/{h}.json": [(200, MD5_RESPONSE, None)],
                       "/games/skyrimspecialedition/mods/md5_search/" + "0" * 32 + ".json":
                           [(404, {"message": "File hash '000' not matched"}, None)]})
    r = c.md5_search(h.upper())
    assert r[0]["mod_id"] == 12604 and r[0]["file_id"] == 35407 and r[0]["mod_name"] == "SkyUI"
    assert r[0]["file_name"] == "SkyUI" and r[0]["version"] == "5.2SE" and r[0]["category"] == "MAIN"
    assert r[0]["archive_name"] == "SkyUI_5_2_SE-12604-5-2SE.7z"
    assert c.md5_search("0" * 32) == []
    with pytest.raises(N.NexusError) as e:
        c.md5_search("nothex")
    assert e.value.kind == "bad_md5"


# ================================================================ updates
FILES_RESPONSE = {
    "files": [
        {"file_id": 100, "name": "Main", "version": "1.0", "category_id": 4, "category_name": "OLD_VERSION",
         "file_name": "m-1.0.7z", "uploaded_timestamp": 10},
        {"file_id": 110, "name": "Main", "version": "1.1", "category_id": 4, "category_name": "OLD_VERSION",
         "file_name": "m-1.1.7z", "uploaded_timestamp": 20},
        {"file_id": 120, "name": "Main", "version": "1.2", "category_id": 1, "category_name": "MAIN",
         "file_name": "m-1.2.7z", "uploaded_timestamp": 30, "is_primary": True},
        {"file_id": 200, "name": "Patch", "version": "1.0", "category_id": 3, "category_name": "OPTIONAL",
         "file_name": "p.7z", "uploaded_timestamp": 15},
        {"file_id": 300, "name": "Old thing", "version": "0.9", "category_id": 7, "category_name": "ARCHIVED",
         "file_name": "o.7z", "uploaded_timestamp": 5},
    ],
    "file_updates": [
        {"old_file_id": 100, "new_file_id": 110, "old_file_name": "m-1.0.7z", "new_file_name": "m-1.1.7z",
         "uploaded_timestamp": 20, "uploaded_time": "2020-01-01T00:00:00.000+00:00"},
        {"old_file_id": 110, "new_file_id": 120, "old_file_name": "m-1.1.7z", "new_file_name": "m-1.2.7z",
         "uploaded_timestamp": 30, "uploaded_time": "2020-02-01T00:00:00.000+00:00"},
        {"old_file_id": 120, "new_file_id": 100, "uploaded_timestamp": 1},   # bogus loop, ignored
    ]}


def test_check_updates_chain():
    c, op, _ = _client({"/games/skyrimspecialedition/mods/9/files.json": [(200, FILES_RESPONSE, None)],
                        "/games/skyrimspecialedition/mods/8/files.json": [(404, {}, None)]})
    rows = N.check_updates(c, [
        {"mod_id": 9, "file_id": 100, "version": "1.0"},
        {"mod_id": 9, "file_id": 120, "version": "1.2"},
        {"mod_id": 9, "file_id": 200, "version": "1.0"},
        {"mod_id": 9, "file_id": 300, "version": "0.9"},
        {"mod_id": 9, "file_id": None, "version": "1.1"},
        {"mod_id": 8, "file_id": 1, "version": "1"},
    ])
    a, b, p, arch, nofile, gone = rows
    assert (a["latest_file_id"], a["latest"], a["changed"], a["status"]) == (120, "1.2", True, "update")
    assert a["current"] == "1.0" and a["file_name"] == "m-1.2.7z" and a["name"] == "Main"
    assert (b["changed"], b["status"]) == (False, "ok")
    assert (p["changed"], p["latest_file_id"]) == (False, 200)
    assert (arch["changed"], arch["latest_file_id"]) == (True, 120)       # archived -> newest MAIN
    assert (nofile["changed"], nofile["latest"]) == (True, "1.2")
    assert gone["status"] == "removed" and gone["error"]["es"]
    assert len(op.calls) == 2                                            # files.json cached per mod
    assert N.follow_updates(100, FILES_RESPONSE["file_updates"]) == 120


# ================================================================ downloads
PAYLOAD = bytes(range(256)) * 4000      # ~1 MB


class _H(http.server.BaseHTTPRequestHandler):
    support_range = True
    disposition = None
    hits: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        _H.hits.append((self.path, self.headers.get("Range")))
        data = PAYLOAD
        rng = self.headers.get("Range")
        start = 0
        if rng and _H.support_range:
            start = int(rng.split("=")[1].split("-")[0])
            if start >= len(data):
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{len(data)}")
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
        else:
            self.send_response(200)
        if _H.disposition:
            self.send_header("Content-Disposition", _H.disposition)
        body = data[start:]
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def srv():
    _H.support_range, _H.disposition, _H.hits = True, None, []
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()
    s.server_close()


MD5 = hashlib.md5(PAYLOAD).hexdigest()


def test_download_basic_and_progress(srv, tmp_path):
    seen = []
    p = N.download(srv + "/cdn/1704/266/My%20Mod-266-1-0.7z?md5=x&expires=1", tmp_path,
                   progress=lambda l, d, t: seen.append((l, d, t)), expected_md5=MD5)
    assert p.name == "My Mod-266-1-0.7z" and p.read_bytes() == PAYLOAD
    assert seen[-1][1] == seen[-1][2] == len(PAYLOAD)
    assert not list(tmp_path.glob("*.part"))
    assert N.file_md5(p) == MD5


def test_download_resume(srv, tmp_path):
    (tmp_path / "a.7z.part").write_bytes(PAYLOAD[:300000])
    p = N.download(srv + "/a.7z", tmp_path, expected_md5=MD5)
    assert p.read_bytes() == PAYLOAD and _H.hits[-1][1] == "bytes=300000-"
    # complete .part (416 from server) is accepted as is
    (tmp_path / "b.7z.part").write_bytes(PAYLOAD)
    p = N.download(srv + "/b.7z", tmp_path)
    assert p.name == "b.7z" and p.read_bytes() == PAYLOAD
    # server without Range support: starts over
    _H.support_range = False
    (tmp_path / "c.7z.part").write_bytes(b"garbage" * 10)
    p = N.download(srv + "/c.7z", tmp_path, expected_md5=MD5)
    assert p.read_bytes() == PAYLOAD


def test_download_md5_mismatch(srv, tmp_path):
    with pytest.raises(N.NexusError) as e:
        N.download(srv + "/x.7z", tmp_path, expected_md5="0" * 32)
    assert e.value.kind == "md5"
    assert not list(tmp_path.iterdir())


def test_download_collision_and_identical_skip(srv, tmp_path):
    (tmp_path / "m.7z").write_bytes(b"something else")
    p = N.download(srv + "/m.7z", tmp_path)
    assert p.name == "m (2).7z" and p.read_bytes() == PAYLOAD
    assert (tmp_path / "m.7z").read_bytes() == b"something else"
    # identical file already there, md5 unknown: downloaded, compared, reused
    p2 = N.download(srv + "/m.7z", tmp_path)
    assert p2 == p and len(list(tmp_path.iterdir())) == 2
    # md5 known: no request at all
    n = len(_H.hits)
    p3 = N.download(srv + "/m.7z", tmp_path, expected_md5=MD5)
    assert p3 == p and len(_H.hits) == n


def test_download_content_disposition_and_cancel(srv, tmp_path):
    _H.disposition = "attachment; filename*=UTF-8''Caf%C3%A9%20Mod.7z"
    p = N.download(srv + "/download?id=1", tmp_path)
    assert p.name == "Café Mod.7z"
    _H.disposition = None
    with pytest.raises(N.NexusError) as e:
        N.download(srv + "/z.7z", tmp_path, cancel=lambda: True)
    assert e.value.kind == "cancelled" and (tmp_path / "z.7z.part").exists()


@pytest.mark.parametrize("name", ["../evil.7z", "..\\evil.7z", "a/b.7z", "CON", "nul.txt", "a:b.7z",
                                  "trail.", "C:\\x.7z"])
def test_download_rejects_bad_names(srv, tmp_path, name):
    with pytest.raises(N.NexusError) as e:
        N.download(srv + "/ok.7z", tmp_path / "d", filename=name)
    assert e.value.kind == "bad_name"


def test_download_rejects_bad_server_names(srv, tmp_path):
    _H.disposition = 'attachment; filename="../../evil.dll"'
    with pytest.raises(N.NexusError) as e:
        N.download(srv + "/download", tmp_path / "d")
    assert e.value.kind == "bad_name"
    with pytest.raises(N.NexusError):
        N.download(srv + "/x/..%2F..%2Fevil.7z", tmp_path / "d")
    assert not (tmp_path / "evil.dll").exists() and not (tmp_path / "evil.7z").exists()


# ================================================================ nxm handler (fake winreg)
class FakeWinreg:
    HKEY_CURRENT_USER, HKEY_CLASSES_ROOT = "HKCU", "HKCR"
    KEY_READ, KEY_ALL_ACCESS, REG_SZ = 1, 2, 1

    def __init__(self):
        self.keys = {}          # (root, lower path) -> {value name: value}
        self.names = {}

    def _k(self, root, path):
        return (root, path.lower())

    def OpenKey(self, root, path, res=0, access=1):
        k = self._k(root, path)
        if k not in self.keys:
            raise FileNotFoundError(path)
        return k

    def CreateKeyEx(self, root, path, res=0, access=2):
        parts = path.split("\\")
        for i in range(1, len(parts) + 1):
            k = self._k(root, "\\".join(parts[:i]))
            self.keys.setdefault(k, {})
            self.names.setdefault(k, parts[i - 1])
        return self._k(root, path)

    def QueryValueEx(self, k, name):
        vals = self.keys[k]
        if name not in vals:
            raise FileNotFoundError(name)
        return vals[name], 1

    def SetValueEx(self, k, name, res, typ, value):
        self.keys[k][name] = value

    def DeleteValue(self, k, name):
        if name not in self.keys[k]:
            raise FileNotFoundError(name)
        del self.keys[k][name]

    def EnumKey(self, k, i):
        root, p = k
        kids = sorted(self.names[c] for c in self.keys if c[0] == root and c[1].startswith(p + "\\")
                      and "\\" not in c[1][len(p) + 1:])
        if i >= len(kids):
            raise OSError("no more")
        return kids[i]

    def DeleteKey(self, root, path):
        k = self._k(root, path)
        if any(c[0] == root and c[1].startswith(k[1] + "\\") for c in self.keys):
            raise PermissionError("has subkeys")
        self.keys.pop(k, None)

    def CloseKey(self, k):
        pass

    def get(self, path, name=""):
        return self.keys.get(("HKCU", path.lower()), {}).get(name)


VORTEX = '"C:\\Program Files\\Black Tree Gaming Ltd\\Vortex\\Vortex.exe" -d "%1"'
OURS = '"C:\\Apps\\SwitchNX Studio\\SwitchNX Studio.exe" "%1"'


def test_register_preserves_and_restores_previous():
    wr = FakeWinreg()
    k = wr.CreateKeyEx("HKCU", X.CMD_PATH)
    wr.SetValueEx(k, "", 0, 1, VORTEX)
    icon = wr.CreateKeyEx("HKCU", X.ROOT_PATH + "\\DefaultIcon")
    wr.SetValueEx(icon, "", 0, 1, "vortex.ico")
    assert X.current_handler(wr) == VORTEX and not X.is_ours(VORTEX)
    r = X.register(OURS, winreg=wr)
    assert r == {"command": OURS, "previous": VORTEX, "changed": True}
    assert X.current_handler(wr) == OURS and X.is_ours(X.current_handler(wr))
    assert wr.get(X.ROOT_PATH) == "URL:NXM Protocol" and wr.get(X.ROOT_PATH, "URL Protocol") == ""
    assert wr.get(X.ROOT_PATH, X.PREV_VALUE) == VORTEX
    # registering again (new exe path) keeps the original previous handler
    r2 = X.register(OURS.replace("Apps", "Tools"), winreg=wr)
    assert r2["previous"] == VORTEX
    assert X.status(winreg=wr)["ours"]
    u = X.unregister(winreg=wr)
    assert u == {"restored": VORTEX, "removed": False}
    assert X.current_handler(wr) == VORTEX and wr.get(X.ROOT_PATH, X.PREV_VALUE) is None
    assert wr.get(X.ROOT_PATH + "\\DefaultIcon") == "vortex.ico"


def test_register_without_previous_then_remove():
    wr = FakeWinreg()
    src = X.default_command(False, "C:\\Py\\python.exe", "C:\\skynx\\app\\main.py")
    assert src == '"C:\\Py\\python.exe" "C:\\skynx\\app\\main.py" "%1"' and X.is_ours(src)
    assert X.default_command(True, "C:\\A\\SwitchNX Studio.exe", "x") == '"C:\\A\\SwitchNX Studio.exe" "%1"'
    r = X.register(src, winreg=wr)
    assert r["previous"] is None
    assert X.unregister(winreg=wr) == {"restored": None, "removed": True}
    assert not [k for k in wr.keys if "nxm" in k[1]] and X.current_handler(wr) is None
    with pytest.raises(ValueError):
        X.register('"x.exe"', winreg=wr)


def test_unregister_leaves_newer_foreign_handler():
    wr = FakeWinreg()
    X.register(OURS, winreg=wr)
    mo2 = '"C:\\MO2\\nxmhandler.exe" "%1"'
    wr.SetValueEx(wr.CreateKeyEx("HKCU", X.CMD_PATH), "", 0, 1, mo2)
    assert X.unregister(winreg=wr) == {"restored": None, "removed": False}
    assert X.current_handler(wr) == mo2


# ================================================================ single instance
def test_ipc_round_trip(tmp_path):
    tf = tmp_path / "ipc.json"
    got = []
    ev = threading.Event()
    s = ipc.Server(tf, lambda m: (got.append(m), ev.set()), ports=range(47811, 47816))
    port = s.start()
    try:
        assert 47811 <= port <= 47815
        data = json.loads(tf.read_text())
        assert data["port"] == port and len(data["token"]) > 20
        assert ipc.is_running(tf)
        url = "nxm://skyrimspecialedition/mods/1/files/2?key=a&expires=3"
        assert ipc.send(tf, url)
        assert ev.wait(2) and got == [{"nxm": url}]
        assert not ipc.send(tf, "https://evil.example/x")
        assert not ipc.send(tf, {"run": "calc.exe"})
        # someone without the token
        assert _raw(port, {"token": "wrong", "nxm": url})["ok"] is False
        assert _raw(port, {"token": data["token"], "nxm": "file:///c:/x"})["error"] == "not an nxm link"
        assert _raw(port, {"token": data["token"], "nxm": "nxm://a b"})["ok"] is False
        assert _raw(port, b"x" * 9000) is None or _raw(port, b"x" * 9000)["ok"] is False
        assert len(got) == 1
        # claim from a "second process": hands off and returns None
        assert ipc.claim(tf, lambda m: None, url=url) is None
        assert ev.wait(2) and got[-1] == {"nxm": url}
    finally:
        s.stop()
    assert not tf.exists() and not ipc.is_running(tf)


def test_ipc_claim_starts_when_nobody_runs(tmp_path):
    tf = tmp_path / "ipc.json"
    tf.write_text(json.dumps({"port": 47815, "token": "stale"}))     # leftover from a crash
    srv = ipc.claim(tf, lambda m: None, url=None, timeout=0.5)
    try:
        assert srv is not None and srv.running and ipc.is_running(tf)
    finally:
        srv.stop()


def _raw(port, payload):
    data = payload if isinstance(payload, bytes) else (json.dumps(payload) + "\n").encode()
    with socket.create_connection(("127.0.0.1", port), timeout=2) as s:
        try:
            s.sendall(data)
            line = s.makefile("rb").readline()
        except OSError:
            return None
    return json.loads(line) if line else None
