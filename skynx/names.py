"""Names in another language: plugins that rename the game's records.

Ports of mods often come from a translated upload: The Ordinary Women in the
test pack carried 61 NPC names in Russian ("Гердур" for Gerdur), because a
mod that changes a record copies all of it, name included. The game then shows
those names whatever language it runs in.

A name is "foreign" when the game's language uses the Latin alphabet and the
name doesn't: Cyrillic, Greek, CJK and the like, stored as UTF-8, or Windows
Cyrillic bytes (cp1251), which a Latin game shows as accented garbage.

For a record the plugin takes over from a master, the fix puts back the
master's name: read from the master itself when it isn't localized, or from
its .strings file (the game's, in Skyrim - Interface.bsa; a Creation Club
plugin's, in its own BSA) when it is. The plugin's own new records have no
name to go back to; they're only reported.
"""
from __future__ import annotations

import struct
from pathlib import Path

from .bsa import read_bsa
from .plugin import read_header
from .records import iter_records, iter_subrecords, replace_subrecord, rewrite_records

LOCALIZED = 0x80
LATIN_LANGS = {"en": "english", "es": "spanish", "fr": "french", "de": "german",
               "it": "italian", "pl": "polish"}
_MASTER_CACHE: dict[tuple, dict[int, bytes]] = {}
_STRINGS_CACHE: dict[tuple, dict[int, str]] = {}


def foreign(raw: bytes) -> str | None:
    """The name as text when it's written in a non-Latin script, else None."""
    b = raw.rstrip(b"\0")
    if not b:
        return None
    try:
        s = b.decode("utf-8")
    except UnicodeDecodeError:
        hi = sum(1 for c in b if c >= 0xC0)
        letters = sum(1 for c in b if c >= 0xC0 or chr(c).isalpha())
        if letters and hi / letters >= 0.6:          # Windows Cyrillic, not accented Latin
            return b.decode("cp1251", "replace")
        return None
    return s if any(ord(c) > 0x24F and c.isalpha() for c in s) else None


def _edid(subs: dict) -> str:
    return subs.get("EDID", b"").rstrip(b"\0").decode("cp1252", "replace")


_SCAN_CACHE: dict[tuple, list[dict]] = {}


def scan(plugin: Path) -> list[dict]:
    """[{formid, type, edid, name, master}] for records whose name is foreign;
    master is the plugin the record comes from (None for its own records).
    Localized plugins (names as string IDs) have nothing to scan."""
    plugin = Path(plugin)
    st = plugin.stat()
    key = (str(plugin), st.st_size, st.st_mtime)
    if key not in _SCAN_CACHE:
        _SCAN_CACHE[key] = _scan(plugin)
    return _SCAN_CACHE[key]


def _scan(plugin: Path) -> list[dict]:
    h = read_header(plugin)
    if h.flags & LOCALIZED:
        return []
    out = []
    for r in iter_records(plugin, has=[b"FULL"]):
        if not r.data:
            continue
        subs = dict(iter_subrecords(r.data))
        full = subs.get("FULL")
        if full is None or len(full) == 4 and not full.endswith(b"\0"):
            continue                                  # a string ID (localized plugin)
        name = foreign(full)
        if not name:
            continue
        idx = r.formid >> 24
        out.append({"formid": r.formid, "type": r.type, "edid": _edid(subs), "name": name,
                    "master": h.masters[idx] if idx < len(h.masters) else None})
    return out


def _master_fulls(path: Path, ids: set[int]) -> dict[int, bytes]:
    """FULL payloads of the master's own records with these local IDs."""
    st = path.stat()
    key = (str(path), st.st_size, st.st_mtime, frozenset(ids))
    if key not in _MASTER_CACHE:
        found: dict[int, bytes] = {}
        nmast = len(read_header(path).masters)
        for r in iter_records(path, has=[b"FULL"]):
            if r.data and r.formid >> 24 == nmast and r.formid & 0xFFFFFF in ids:
                full = dict(iter_subrecords(r.data)).get("FULL")
                if full is not None:
                    found[r.formid & 0xFFFFFF] = full
        _MASTER_CACHE[key] = found
    return _MASTER_CACHE[key]


def parse_strings(raw: bytes) -> dict[int, str]:
    """A .strings file (null-terminated entries)."""
    count, _size = struct.unpack_from("<II", raw, 0)
    base = 8 + 8 * count
    out = {}
    for i in range(count):
        sid, off = struct.unpack_from("<II", raw, 8 + 8 * i)
        start = base + off
        end = raw.find(b"\0", start)
        out[sid] = raw[start:end].decode("utf-8", "replace") if end >= 0 else ""
    return out


def _strings_for(master: str, lang: str, places: list[Path]) -> dict[int, str] | None:
    """The master's .strings in this language: loose under a strings folder, or
    inside a BSA in `places` (folders with the game's or the pack's BSAs)."""
    want = f"strings\\{Path(master).stem.lower()}_{lang}.strings"
    for folder in places:
        loose = folder / "strings" / f"{Path(master).stem}_{lang}.strings"
        if loose.is_file():
            return parse_strings(loose.read_bytes())
        if not folder.is_dir():
            continue
        for b in sorted(folder.glob("*.bsa")):
            try:
                st = b.stat()
                key = (str(b), st.st_size, st.st_mtime, want)
                if key in _STRINGS_CACHE:
                    return _STRINGS_CACHE[key]
                arc = read_bsa(b)
                e = next((e for e in arc.entries if e.path.lower() == want), None)
                if e is None:
                    continue
                _STRINGS_CACHE[key] = parse_strings(arc.read_file(e))
                return _STRINGS_CACHE[key]
            except Exception:  # noqa: BLE001
                continue
    return None


def game_names(found: list[dict], masters: dict[str, Path], lang: str,
               places: list[Path]) -> dict[int, str]:
    """{formid in the plugin: the master's name} for the foreign names that
    take over a master's record and whose master name could be read."""
    out: dict[int, str] = {}
    by_master: dict[str, list[dict]] = {}
    for f in found:
        if f["master"]:
            by_master.setdefault(f["master"], []).append(f)
    for m, fs in by_master.items():
        path = masters.get(m.lower())
        if not path or not path.is_file():
            continue
        try:
            fulls = _master_fulls(path, {f["formid"] & 0xFFFFFF for f in fs})
            localized = bool(read_header(path).flags & LOCALIZED)
        except Exception:  # noqa: BLE001
            continue
        table = _strings_for(m, lang, places) if localized else None
        for f in fs:
            raw = fulls.get(f["formid"] & 0xFFFFFF)
            if raw is None:
                continue
            if localized:
                if table is None or len(raw) < 4:
                    continue
                name = table.get(struct.unpack_from("<I", raw, 0)[0])
            else:
                name = raw.rstrip(b"\0").decode("cp1252", "replace")
            if name and not foreign(name.encode("utf-8")):
                out[f["formid"]] = name
    return out


def fix_names(plugin_raw: bytes, names: dict[int, str]) -> tuple[bytes, int]:
    """The plugin with these records' FULL set to the given names."""
    def enc(s: str) -> bytes:
        try:
            return s.encode("cp1252") + b"\0"
        except UnicodeEncodeError:
            return s.encode("utf-8") + b"\0"

    def edit(_typ, fid, data):
        if fid in names:
            return replace_subrecord(data, "FULL", enc(names[fid]))
        return None
    return rewrite_records(plugin_raw, edit)
