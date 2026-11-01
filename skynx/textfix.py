"""Texts a patch saved as "<Error: No strings file for lstring ID 00003729>".

A patch made in an editor that hadn't loaded the game's texts copies the error
message into the record instead of the text (Cell Patch NX: the objectives of
Rare Gifts, Delivery, Some Light Theft... showed it in the journal, Oct 2026).
The id is the game's own: its strings files have the real text, so it can be
put back. Only those subrecords change.
"""
from __future__ import annotations

import re
import struct
from pathlib import Path

from .bsa import read_bsa
from .names import parse_strings
from .plugin import read_header
from .records import _masters_of, iter_records, iter_subrecords, rewrite_records

MARK = b"<Error: No strings file for lstring ID "
ERR = re.compile(rb"<Error: No strings file for lstring ID ([0-9A-Fa-f]{8})>")
LOCALIZED = 0x80
_TABLES: dict[tuple, dict[int, str]] = {}


def scan(path: Path, deep: bool = True) -> list[dict]:
    """[{formid, type, sig, n, sid, master}] for each subrecord holding the error text.
    `n` counts the subrecords with that signature in the record (0 = first).
    Without `deep`, plugins whose raw bytes don't show the text are skipped
    (the text could still hide in a compressed record)."""
    path = Path(path)
    raw = path.read_bytes()
    if MARK not in raw and not deep:
        return []
    masters = _masters_of(path)
    out = []
    for r in iter_records(raw, has=[MARK]):
        if r.data is None:
            continue
        i = r.formid >> 24
        master = masters[i] if i < len(masters) else None
        seen: dict[str, int] = {}
        for sig, data in r.subrecords():
            n = seen.get(sig, 0)
            seen[sig] = n + 1
            m = ERR.search(data)
            if m:
                out.append({"formid": r.formid, "type": r.type, "sig": sig, "n": n,
                            "sid": int(m.group(1), 16), "master": master})
    return out


def _parse_dl(raw: bytes) -> dict[int, str]:
    """.dlstrings / .ilstrings: each entry starts with its length."""
    count, _size = struct.unpack_from("<II", raw, 0)
    base = 8 + 8 * count
    out = {}
    for i in range(count):
        sid, off = struct.unpack_from("<II", raw, 8 + 8 * i)
        n = struct.unpack_from("<I", raw, base + off)[0]
        out[sid] = raw[base + off + 4:base + off + 4 + n].rstrip(b"\0").decode("utf-8", "replace")
    return out


def _tables(master: str, lang: str, places: list[Path]) -> list[dict[int, str]]:
    """The master's three string tables in this language (missing ones left out)."""
    stem = Path(master).stem.lower()
    out = []
    for ext in ("strings", "dlstrings", "ilstrings"):
        want = f"strings\\{stem}_{lang}.{ext}"
        parse = parse_strings if ext == "strings" else _parse_dl
        found = None
        for folder in places:
            loose = Path(folder) / "strings" / f"{Path(master).stem}_{lang}.{ext}"
            if loose.is_file():
                found = parse(loose.read_bytes())
                break
            if not Path(folder).is_dir():
                continue
            for b in sorted(Path(folder).glob("*.bsa")):
                try:
                    st = b.stat()
                    key = (str(b), st.st_size, st.st_mtime_ns, want)
                    if key not in _TABLES:
                        arc = read_bsa(b)
                        e = next((e for e in arc.entries if e.path.lower() == want), None)
                        if e is None:
                            continue
                        _TABLES[key] = parse(arc.read_file(e))
                    found = _TABLES[key]
                    break
                except Exception:  # noqa: BLE001
                    continue
            if found is not None:
                break
        if found is not None:
            out.append(found)
    return out


def game_texts(found: list[dict], masters: dict[str, Path], lang: str,
               places: list[Path]) -> dict[tuple[int, str, int], str]:
    """{(formid, sig, n): the game's text} for the error texts whose id the
    record's (localized) master has in its string tables."""
    out = {}
    for m in {f["master"] for f in found if f["master"]}:
        path = masters.get(m.lower())
        try:
            if not path or not (read_header(path).flags & LOCALIZED):
                continue
        except Exception:  # noqa: BLE001
            continue
        tables = _tables(m, lang, places)
        for f in found:
            if f["master"] != m:
                continue
            text = next((t[f["sid"]] for t in tables if f["sid"] in t), None)
            if text:
                out[(f["formid"], f["sig"], f["n"])] = text
    return out


def restore(plugin_raw: bytes, texts: dict[tuple[int, str, int], str]) -> tuple[bytes, int]:
    """The plugin with those subrecords holding the game's text instead of the error."""
    def enc(s: str) -> bytes:
        try:
            return s.encode("cp1252") + b"\0"
        except UnicodeEncodeError:
            return s.encode("utf-8") + b"\0"

    def edit(_typ, fid, data):
        if not any(k[0] == fid for k in texts):
            return None
        out = bytearray()
        seen: dict[str, int] = {}
        changed = False
        for sig, d in iter_subrecords(data):
            n = seen.get(sig, 0)
            seen[sig] = n + 1
            new = texts.get((fid, sig, n))
            if new is not None and ERR.search(d):
                d = enc(new)
                changed = True
            if len(d) > 0xFFFF:
                return None
            out += sig.encode("latin-1") + struct.pack("<H", len(d)) + d
        return bytes(out) if changed else None
    return rewrite_records(plugin_raw, edit)
