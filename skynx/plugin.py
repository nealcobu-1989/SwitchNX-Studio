"""Read-only parser for Skyrim SE/AE plugin headers (.esp/.esm/.esl).

Only the TES4 header record is read: flags, HEDR version, record count,
author, description and master list. Nothing is ever written.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

FLAG_MASTER = 0x00000001
FLAG_LOCALIZED = 0x00000080
FLAG_LIGHT = 0x00000200

# HEDR versions seen in the wild.
HEDR_OLDRIM = 0.94       # Skyrim LE (form 43). Unsafe on SE/AE engine.
HEDR_SSE = 1.70
HEDR_SSE_NEW = 1.71      # 1.6.1130+ (expanded ESL range)


@dataclass
class PluginHeader:
    path: Path
    name: str
    size: int
    record_type: str = ""
    flags: int = 0
    form_version: int = 0
    hedr_version: float = 0.0
    num_records: int = 0
    next_object_id: int = 0
    author: str = ""
    description: str = ""
    masters: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def is_master_flag(self) -> bool:
        return bool(self.flags & FLAG_MASTER)

    @property
    def is_light_flag(self) -> bool:
        return bool(self.flags & FLAG_LIGHT)

    @property
    def is_localized(self) -> bool:
        return bool(self.flags & FLAG_LOCALIZED)

    @property
    def is_dummy(self) -> bool:
        """A header-only plugin (no records) whose only job is to load a BSA."""
        return self.num_records == 0 and not self.error

    @property
    def extension(self) -> str:
        return Path(self.name).suffix.lower()


def _zstr(b: bytes) -> str:
    b = b.split(b"\x00", 1)[0]
    for enc in ("utf-8", "cp1252"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("latin-1")


def read_header(path: Path) -> PluginHeader:
    path = Path(path)
    h = PluginHeader(path=path, name=path.name, size=path.stat().st_size)
    try:
        with path.open("rb") as f:
            head = f.read(24)
            if len(head) < 24:
                h.error = "file shorter than a record header"
                return h
            rtype, dsize, flags, _formid, _vc1, _vc2, fver, _unk = struct.unpack(
                "<4sIIIHHHH", head)
            h.record_type = rtype.decode("latin-1")
            h.flags = flags
            h.form_version = fver
            if rtype != b"TES4":
                h.error = f"first record is {h.record_type!r}, expected TES4"
                return h
            data = f.read(dsize)
            if len(data) < dsize:
                h.error = "TES4 record truncated"
                return h
    except OSError as e:
        h.error = str(e)
        return h

    i = 0
    big = None
    while i + 6 <= len(data):
        st, ss = struct.unpack_from("<4sH", data, i)
        i += 6
        if big is not None:
            ss, big = big, None
        payload = data[i:i + ss]
        i += ss
        if st == b"XXXX":
            big = struct.unpack("<I", payload)[0]
            continue
        if st == b"HEDR" and len(payload) >= 12:
            h.hedr_version, h.num_records, h.next_object_id = struct.unpack_from(
                "<fiI", payload)
            h.hedr_version = round(h.hedr_version, 2)
        elif st == b"CNAM":
            h.author = _zstr(payload)
        elif st == b"SNAM":
            h.description = _zstr(payload)
        elif st == b"MAST":
            h.masters.append(_zstr(payload))
    return h


def rename_master_bytes(raw: bytes, old: str, new: str) -> bytes | None:
    """Return the plugin bytes with MAST `old` renamed to `new` (case-insensitive
    match), rebuilding the TES4 header. None if `old` isn't a master."""
    if raw[:4] != b"TES4":
        raise ValueError("no es un plugin (falta TES4)")
    dsize = struct.unpack_from("<I", raw, 4)[0]
    head, data, rest = raw[:24], raw[24:24 + dsize], raw[24 + dsize:]
    out, i, changed = bytearray(), 0, False
    while i + 6 <= len(data):
        st, ss = struct.unpack_from("<4sH", data, i)
        payload = data[i + 6:i + 6 + ss]
        if st == b"XXXX":          # oversized next subrecord: copy both untouched
            big = struct.unpack("<I", payload)[0]
            nxt = data[i + 6 + ss:i + 6 + ss + 6 + big]
            out += data[i:i + 6 + ss] + nxt
            i += 6 + ss + 6 + big
            continue
        if st == b"MAST" and _zstr(payload).lower() == old.lower():
            enc = new.encode("cp1252") + b"\x00"
            out += struct.pack("<4sH", b"MAST", len(enc)) + enc
            changed = True
        else:
            out += data[i:i + 6 + ss]
        i += 6 + ss
    if not changed:
        return None
    out += data[i:]
    new_head = head[:4] + struct.pack("<I", len(out)) + head[8:]
    return bytes(new_head) + bytes(out) + rest


def clear_light_flag(raw: bytes) -> bytes:
    """Same plugin without the ESL flag (the SE version can't load light plugins).
    Compacted FormIDs stay valid in a regular plugin."""
    if raw[:4] != b"TES4":
        raise ValueError("not a plugin (TES4 missing)")
    flags = struct.unpack_from("<I", raw, 8)[0]
    if not flags & FLAG_LIGHT:
        return raw
    return raw[:8] + struct.pack("<I", flags & ~FLAG_LIGHT) + raw[12:]


def read_masters(raw: bytes) -> list[str]:
    """Masters of a plugin given its bytes."""
    if raw[:4] != b"TES4":
        return []
    dsize = struct.unpack_from("<I", raw, 4)[0]
    data = raw[24:24 + dsize]
    out, i = [], 0
    while i + 6 <= len(data):
        st, ss = struct.unpack_from("<4sH", data, i)
        if st == b"XXXX":
            big = struct.unpack_from("<I", data, i + 6)[0]
            i += 6 + ss + 6 + big
            continue
        if st == b"MAST":
            out.append(_zstr(data[i + 6:i + 6 + ss]))
        i += 6 + ss
    return out
