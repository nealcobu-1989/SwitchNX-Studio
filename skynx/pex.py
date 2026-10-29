"""Papyrus .pex string table: find and rename plugin file names.

Scripts call Game.GetFormFromFile(id, "Mod.esp") with the plugin name as a
literal string, so a plugin rename must patch those strings too. The string
table sits right after the header and everything else refers to strings by
index, so replacing an entry (even with a different length) keeps the file
valid. PC and Switch scripts share the same big-endian layout.
"""
from __future__ import annotations

import struct

MAGIC = b"\xfa\x57\xc0\xde"


class PexError(ValueError):
    pass


def _layout(raw: bytes) -> tuple[str, int, int, list[tuple[int, str]]]:
    """Returns (endian, table_start, table_end, [(offset, string)])."""
    if raw[:4] == MAGIC:
        en = ">"
    elif raw[:4] == MAGIC[::-1]:
        en = "<"
    else:
        raise PexError("not a Papyrus script")
    o = 4 + 2 + 2 + 8
    for _ in range(3):  # source file, user, machine
        n, = struct.unpack_from(en + "H", raw, o)
        o += 2 + n
    start = o
    count, = struct.unpack_from(en + "H", raw, o)
    o += 2
    items = []
    for _ in range(count):
        n, = struct.unpack_from(en + "H", raw, o)
        if o + 2 + n > len(raw):
            raise PexError("string table runs past the end of the file")
        # latin-1 keeps every byte as is, whatever the script's real encoding
        items.append((o, raw[o + 2:o + 2 + n].decode("latin-1")))
        o += 2 + n
    return en, start, o, items


def strings(raw: bytes) -> list[str]:
    return [s for _o, s in _layout(raw)[3]]


def mentions(raw: bytes, plugin: str) -> bool:
    p = _key(plugin)
    return any(s.lower() == p for s in strings(raw))


def _key(name: str) -> str:
    return name.encode("cp1252", "replace").decode("latin-1").lower()


def rename_plugin(raw: bytes, old: str, new: str) -> tuple[bytes, int]:
    return rename_plugins(raw, {old.lower(): new})


def rename_plugins(raw: bytes, low: dict[str, str]) -> tuple[bytes, int]:
    """Replace strings equal (ignoring case) to a key of `low` by its value."""
    en, start, end, items = _layout(raw)
    keys = {_key(k): v for k, v in low.items()}
    parts = [raw[:start], struct.pack(en + "H", len(items))]
    n = 0
    for _o, s in items:
        new = keys.get(s.lower())
        if new is not None:
            b = new.encode("cp1252")
            n += 1
        else:
            b = s.encode("latin-1")
        parts.append(struct.pack(en + "H", len(b)) + b)
    if not n:
        return raw, 0
    parts.append(raw[end:])
    out = b"".join(parts)
    _layout(out)
    return out, n
