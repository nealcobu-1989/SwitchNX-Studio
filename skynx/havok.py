"""Havok files the byte patch in hkx.py can't convert, made Switch-native.

Switch (and PS4) packfiles use the layout rules 8-1-1-1: 64-bit pointers,
little endian, "reuse padding" on, empty base class on. PC SE uses 8-1-0-1.
For animations the two layouts match except for a few header bytes (hkx.py);
for behavior graphs, skeletons and character files they don't, so those have
to be written again by Havok itself.

Bethesda's HavokBehaviorPostProcess.exe (Creation Kit, hk_2010.2.0-r1) does
that: "--platformps4" writes 8-1-1-1. Tested against files from a working
Switch port (Oct 2026): byte-identical results. It reads XML packfiles and
32-bit binaries, not 64-bit ones, so a 64-bit PC file goes through XML first
with serde-hkx's hkxc.exe (open source, "convert -v xml"). The XML must say
contentsversion "hk_2010.2.0-r1"; Nemesis and serde-hkx write
"hk_2010.2.0 - r1", which HavokBehaviorPostProcess refuses to load.

    to_switch(raw, tools, tmp) -> bytes   (raises HavokError)
"""
from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from . import hkx as HKX
from .errors import SkynxError
from .tools import ToolError, Toolset, run

SWITCH_RULES = (8, 1, 1, 1)
_VERSION = re.compile(rb'contentsversion="hk_2010\.2\.0\s*-\s*r1"')


class HavokError(SkynxError):
    pass


def rules(raw: bytes) -> tuple | None:
    """Layout rules of a binary packfile (pointer size, little endian, reuse
    padding, empty base), or None for XML or something else."""
    if len(raw) < 20 or raw[:4] != b"\x57\xe0\xe0\x57":
        return None
    return tuple(raw[16:20])


def is_switch(raw: bytes) -> bool:
    return rules(raw) == SWITCH_RULES


def fix_xml(data: bytes) -> bytes:
    """The contents version as HavokBehaviorPostProcess expects it."""
    return _VERSION.sub(b'contentsversion="hk_2010.2.0-r1"', data, count=1)


def needs_havok(raw: bytes) -> str | None:
    """Why this file needs Havok's own tool ("xml", "pc32", "behavior",
    "skeleton"), or None when the byte patch (or nothing) is enough."""
    kind = HKX.classify(raw[:32])
    if kind == HKX.XML:
        return "xml"
    if kind == HKX.PC_32:
        return "pc32"
    if kind == HKX.PC_64:
        return HKX.blocker(raw)
    return None


def can_convert(tools: Toolset, why: str | None) -> bool:
    if not why:
        return True
    if why in ("xml", "pc32"):
        return tools.hbpp is not None
    return tools.hbpp is not None and tools.hkxc is not None


def _hbpp(tools: Toolset, src: Path, out: Path) -> bytes:
    run([tools.hbpp, "--platformps4", src, out], timeout=300)
    if not out.is_file():
        raise HavokError(f"HavokBehaviorPostProcess didn't write {out.name}",
                         f"HavokBehaviorPostProcess no escribió {out.name}")
    data = out.read_bytes()
    if not is_switch(data):
        raise HavokError(f"HavokBehaviorPostProcess wrote {out.name} in another format ({rules(data)})",
                         f"HavokBehaviorPostProcess escribió {out.name} en otro formato ({rules(data)})")
    return data


def to_switch(raw: bytes, tools: Toolset, tmp: Path | None = None, name: str = "file") -> bytes:
    """A Switch-native copy of a Havok file (XML, 32-bit, or 64-bit PC)."""
    if is_switch(raw):
        return raw
    why = needs_havok(raw)
    if HKX.classify(raw[:32]) == HKX.PC_64 and not why:
        why = "pc64"                      # an animation the byte patch couldn't handle
    if tools.hbpp is None:
        raise HavokError("HavokBehaviorPostProcess.exe is missing from the tools folder",
                         "Falta HavokBehaviorPostProcess.exe en la carpeta de herramientas")
    own = tmp is None
    work = Path(tempfile.mkdtemp(prefix="skynx-havok-")) if own else Path(tmp)
    work.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(name).stem) or "file"
    try:
        if why == "xml":
            src = work / f"{stem}.xml"
            src.write_bytes(fix_xml(raw))
            return _hbpp(tools, src, work / f"{stem}_nx.hkx")
        if why == "pc32":
            src = work / f"{stem}.hkx"
            src.write_bytes(raw)
            try:
                return _hbpp(tools, src, work / f"{stem}_nx.hkx")
            except (ToolError, HavokError):
                if tools.hkxc is None:
                    raise
            # some 32-bit files load only through XML
        if tools.hkxc is None:
            raise HavokError("hkxc.exe (serde-hkx) is missing from the tools folder",
                             "Falta hkxc.exe (serde-hkx) en la carpeta de herramientas")
        src = work / f"{stem}_pc.hkx"
        src.write_bytes(raw)
        xml = work / f"{stem}.xml"
        run([tools.hkxc, "convert", "-i", src, "-o", xml, "-v", "xml"], timeout=300)
        if not xml.is_file():
            raise HavokError(f"hkxc didn't write {xml.name}", f"hkxc no escribió {xml.name}")
        xml.write_bytes(fix_xml(xml.read_bytes()))
        return _hbpp(tools, xml, work / f"{stem}_nx.hkx")
    except ToolError as e:
        raise HavokError(f"{name}: {e}", f"{name}: {e}") from e
    finally:
        if own:
            shutil.rmtree(work, ignore_errors=True)
