"""What separates a Switch mod for the Anniversary Edition from one for the
original Special Edition, and how to move a plugin from one to the other.

AE (1.1.x with the Anniversary add-on) reads everything SE reads: an SE mod
goes into an AE pack as it is (its plugins go to Skyrim_aoc.ccc instead of the
Plugins file, which the pack itself takes care of).

SE can't do three things AE can, so an AE mod needs adapting first:
- ESL: no .esl files and no ESL-flagged plugins (NX Toolkit wiki). The plugin
  becomes an .esp without the flag; folders named after it (voices, FaceGen),
  its masters in other plugins and the load list follow the new name.
- HEDR 1.71 (saved with CK 1.6.1130+): SE ignores the plugin; 1.70 is what
  KokaNX sets in SSEEdit.
- Creation Club content: SE has none, so a plugin whose masters include
  ccXXXSSE files can't load there. That can't be adapted, only reported.
"""
from __future__ import annotations

from . import knowledge as K

CC = {c.lower() for c in K.AE_CC_PLUGINS}


def is_cc(name: str) -> bool:
    low = name.lower()
    return low in CC or (low.startswith("cc") and "sse" in low[:12] and low.endswith((".esm", ".esl", ".esp")))


def cc_masters(masters) -> list[str]:
    return [m for m in masters if is_cc(m)]


def se_needs(h) -> dict:
    """What a plugin (PluginHeader) needs before SE can load it."""
    return {"esl": h.extension == ".esl" or bool(h.is_light_flag),
            "hedr": round(getattr(h, "hedr_version", 0) or 0, 2) >= 1.71,
            "cc": cc_masters(h.masters)}


def _n_masters(raw: bytes) -> int:
    import struct
    dsize = struct.unpack_from("<I", raw, 4)[0]
    data, i, n = raw[24:24 + dsize], 0, 0
    while i + 6 <= len(data):
        st, ss = struct.unpack_from("<4sH", data, i)
        if st == b"XXXX":
            big = struct.unpack_from("<I", data, i + 6)[0]
            i += 6 + ss + 6 + big
            continue
        n += st == b"MAST"
        i += 6 + ss
    return n


def low_formids(raw: bytes) -> int:
    """Own records with object IDs below 0x800 (only HEDR 1.71 allows them)."""
    from .records import iter_headers
    nm, count = _n_masters(raw), 0
    try:
        for typ, fid, _fl in iter_headers(raw):
            if typ != "TES4" and (fid >> 24) >= nm and (fid & 0xFFFFFF) < 0x800:
                count += 1
    except Exception:  # noqa: BLE001  (unreadable: don't touch the version)
        return -1
    return count


def adapt_bytes_for_se(raw: bytes) -> bytes:
    """Clear the ESL flag, and bring HEDR 1.71 down to 1.70 when that's safe:
    with own records below 0x800 the version stays (the Doctor explains how to
    renumber them first). Nothing else changes."""
    import struct
    from .plugin import clear_light_flag
    from .records import hedr_offset, set_hedr_version
    out = clear_light_flag(raw)
    o = hedr_offset(out)
    if o is not None and round(struct.unpack_from("<f", out, o)[0], 2) >= 1.71 and low_formids(out) == 0:
        out = set_hedr_version(out, K.HEDR_SE)
    return out


def cc_note(plugin: str, ms: list[str]) -> tuple[str, str]:
    s = ", ".join(ms[:4])
    return (f"{plugin} needs Creation Club content ({s}), which the SE version doesn't have: it won't load there.",
            f"{plugin} necesita contenido del Creation Club ({s}), que la versión SE no tiene: ahí no va a cargar.")
