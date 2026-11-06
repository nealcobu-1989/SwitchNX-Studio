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


# ------------------------------------------------------------------ GetFormFromFile ids
# Opcodes and how many fixed arguments each takes (Skyrim's Papyrus); 23-25
# (callmethod, callparent, callstatic) are followed by a count and that many more.
_OPS = {0: 0, 1: 3, 2: 3, 3: 3, 4: 3, 5: 3, 6: 3, 7: 3, 8: 3, 9: 3, 10: 2, 11: 2, 12: 2, 13: 2, 14: 2,
        15: 3, 16: 3, 17: 3, 18: 3, 19: 3, 20: 1, 21: 2, 22: 2, 23: 3, 24: 2, 25: 3, 26: 1, 27: 3,
        28: 3, 29: 3, 30: 2, 31: 2, 32: 3, 33: 3, 34: 4, 35: 4}


def patch_formids(raw: bytes, plugin: str, idmap: dict[int, int]) -> tuple[bytes, list[tuple[int, int]]]:
    """Game.GetFormFromFile(id, "<plugin>") calls whose id is in idmap get the
    new id (a merge renumbered the form). Only the 4 bytes of each constant
    change. Returns (new bytes, [(old, new), ...])."""
    b = bytearray(raw)
    e = ">" if raw[:4] == bytes.fromhex("FA57C0DE") else "<"
    pos = [0]

    def take(fmt):
        v = struct.unpack_from(e + fmt, b, pos[0])[0]
        pos[0] += struct.calcsize(fmt)
        return v

    def wstr():
        n = take("H")
        v = bytes(b[pos[0]:pos[0] + n]).decode("latin-1")
        pos[0] += n
        return v
    take("I"); take("B"); take("B"); take("H"); pos[0] += 8
    wstr(); wstr(); wstr()
    table = [wstr() for _ in range(take("H"))]

    def sidx():
        return table[take("H")]

    def value():
        t = take("B")
        at = pos[0]
        if t in (1, 2):
            return t, sidx(), at
        if t == 3:
            return t, take("i"), at
        if t == 4:
            return t, take("f"), at
        if t == 5:
            return t, take("B"), at
        if t == 0:
            return t, None, at
        raise PexError(f"unknown value type {t}")
    if take("B"):                                  # debug info
        pos[0] += 8
        for _ in range(take("H")):
            sidx(); sidx(); sidx(); take("B"); n = take("H"); pos[0] += 2 * n
    for _ in range(take("H")):                     # user flags
        sidx(); take("B")
    want = plugin.lower()
    done: list[tuple[int, int]] = []

    def function():
        sidx(); sidx(); take("I"); take("B")
        for _ in range(take("H")):
            sidx(); sidx()
        for _ in range(take("H")):
            sidx(); sidx()
        for _ in range(take("H")):
            op = take("B")
            if op not in _OPS:
                raise PexError(f"unknown opcode {op}")
            args = [value() for _ in range(_OPS[op])]
            if op in (23, 24, 25):
                cnt = value()
                args += [value() for _ in range(cnt[1])]
            if op == 25 and len(args) >= 5 and str(args[1][1]).lower() == "getformfromfile":
                fid, name = args[3], args[4]
                if fid[0] == 3 and name[0] == 2 and name[1].lower() == want and (fid[1] & 0xFFFFFF) in idmap:
                    new = idmap[fid[1] & 0xFFFFFF]
                    struct.pack_into(e + "i", b, fid[2], new)
                    done.append((fid[1], new))
    for _ in range(take("H")):                     # objects
        sidx(); take("I"); sidx(); sidx(); take("I"); sidx()
        for _ in range(take("H")):
            sidx(); sidx(); take("I"); value()
        for _ in range(take("H")):
            sidx(); sidx(); sidx(); take("I"); fl = take("B")
            if fl & 4:
                sidx()
            if fl & 5 == 1:
                function()
            if fl & 6 == 2:
                function()
        for _ in range(take("H")):
            sidx()
            for _ in range(take("H")):
                sidx(); function()
    return bytes(b), done
