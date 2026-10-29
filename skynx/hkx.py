"""Havok animation files (.hkx): detect the platform and convert SE PC files.

Detection and conversion come from the Skyrim NX Toolkit (Zappastuff,
convert_hkx64.py / check_hkx.py, MIT licence):
- byte 16 is the pointer size (4 = 32-bit Oldrim, 8 = 64-bit),
- byte 18 is 0 on PC and 1 on Switch/PS4.
A 64-bit PC file becomes a Switch file by setting byte 18 and moving four
bytes of the section header. Skeletons and behavior graphs can't be converted
that way; the Toolkit asks for them to be replaced with Switch versions.
"""
from __future__ import annotations

PC_32, PC_64, NX_64, XML, UNKNOWN = "pc32", "pc64", "nx64", "xml", "?"
_HEADER = b"\x00" * 15 + b"\x80" + b"\x00" * 48


def classify(head: bytes) -> str:
    if head[:5] == b"<?xml":
        return XML
    if len(head) < 19:
        return UNKNOWN
    bits, nx = head[16], head[18]
    if bits == 4 and nx == 0:
        return PC_32
    if bits == 8:
        return {0: PC_64, 1: NX_64}.get(nx, UNKNOWN)
    return UNKNOWN


def blocker(raw: bytes) -> str | None:
    """Why a 64-bit PC file can't be converted automatically, or None."""
    if b"hkaSkeleton" in raw:
        return "skeleton"
    if b"hkbBehavior" in raw:
        return "behavior"
    return None


def convert_pc64(raw: bytes) -> bytes:
    if classify(raw[:32]) != PC_64:
        raise ValueError("not a 64-bit PC animation")
    if blocker(raw):
        raise ValueError(f"can't convert a {blocker(raw)} file")
    loc = raw.find(_HEADER)
    if loc <= 0:
        # The Toolkit leaves these untouched; so do we, and say so.
        raise ValueError("section header not found")
    off = 72 if raw.find(b"hkbProjectData") > 0 else 76
    return (raw[:18] + b"\x01" + raw[19:loc + 16] + raw[loc + 20:loc + off]
            + raw[loc:loc + 4] + raw[loc + off:])
