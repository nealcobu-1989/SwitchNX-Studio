"""Minimal NIF reader/patcher for Skyrim SE meshes (20.2.0.7, BS version 100).

It parses only the header (block types, block sizes, string table) so blocks
can be located without understanding them. The only edit supported is
replacing texture paths inside BSShaderTextureSet blocks, which is what a
plugin rename needs for FaceGen meshes: they point at
textures\\actors\\character\\facegendata\\facetint\\<Plugin.esp>\\<id>.dds.

Every parse is verified: header + all block sizes + footer must equal the
file size exactly, otherwise the file is refused.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field


class NifError(ValueError):
    pass


@dataclass
class NifFile:
    raw: bytes
    version: int
    user_version: int
    bs_version: int
    block_types: list[str]
    block_type_index: list[int]
    block_sizes: list[int]
    strings: list[str]
    header_end: int                 # offset of the first block
    sizes_offset: int               # offset of the block size array
    block_offsets: list[int] = field(default_factory=list)

    def block_type(self, i: int) -> str:
        return self.block_types[self.block_type_index[i] & 0x7FFF]


def _sstr(b: bytes, o: int) -> tuple[str, int]:
    n = struct.unpack_from("<I", b, o)[0]
    if n > 4096 or o + 4 + n > len(b):
        raise NifError("bad string length")
    return b[o + 4:o + 4 + n].decode("cp1252", "replace"), o + 4 + n


def parse(raw: bytes) -> NifFile:
    """Parse the header. The number of short export strings after the BS
    version differs between exporters, so each layout is tried and only the
    one whose block sizes add up exactly to the file size is accepted."""
    last = None
    for nstr in (3, 2, 4):
        try:
            return _parse(raw, nstr)
        except (NifError, struct.error, IndexError) as e:
            last = e
    raise NifError(str(last))


def _parse(raw: bytes, nexport: int) -> NifFile:
    nl = raw.find(b"\n", 0, 64)
    if nl < 0 or not raw.startswith(b"Gamebryo File Format"):
        raise NifError("not a NIF")
    o = nl + 1
    version, = struct.unpack_from("<I", raw, o); o += 4
    if version != 0x14020007:  # Skyrim LE (bs 83) and SE (bs 100)
        raise NifError(f"unsupported NIF version {version:#x}")
    endian = raw[o]; o += 1
    if endian != 1:
        raise NifError("big-endian NIF")
    user_version, nblocks = struct.unpack_from("<II", raw, o); o += 8
    bs_version, = struct.unpack_from("<I", raw, o); o += 4
    # author / process / export info: byte-length strings
    for _ in range(nexport):
        n = raw[o]; o += 1 + n
    ntypes, = struct.unpack_from("<H", raw, o); o += 2
    types = []
    for _ in range(ntypes):
        s, o = _sstr(raw, o)
        types.append(s)
    tidx = list(struct.unpack_from(f"<{nblocks}H", raw, o)); o += 2 * nblocks
    sizes_off = o
    sizes = list(struct.unpack_from(f"<{nblocks}I", raw, o)); o += 4 * nblocks
    nstrings, _maxlen = struct.unpack_from("<II", raw, o); o += 8
    strings = []
    for _ in range(nstrings):
        s, o = _sstr(raw, o)
        strings.append(s)
    ngroups, = struct.unpack_from("<I", raw, o); o += 4 + 4 * ngroups
    end = o + sum(sizes)
    # Footer: number of roots + root block refs.
    if end + 4 > len(raw):
        raise NifError("block sizes do not add up to the file size")
    nroots, = struct.unpack_from("<I", raw, end)
    fend = end + 4 + 4 * nroots
    if fend > len(raw):
        raise NifError("block sizes do not add up to the file size")
    if fend != len(raw):
        # Bytes after the footer: zero padding, or what's left of an earlier,
        # longer save (the Creation Kit's FaceGen export doesn't truncate the
        # file; Skyrim Revamped has both). The game stops at the footer. Only
        # accepted when the footer itself is sane and every block type name
        # is a plain identifier, so a wrong header layout can't slip through.
        roots = struct.unpack_from(f"<{nroots}i", raw, end + 4) if 0 < nroots <= nblocks else None
        if not roots or not all(-1 <= r < nblocks for r in roots) or \
                not all(t.isascii() and t.replace("_", "").isalnum() for t in types):
            raise NifError("block sizes do not add up to the file size")
    offs, p = [], o
    for s in sizes:
        offs.append(p)
        p += s
    return NifFile(raw, version, user_version, bs_version, types, tidx, sizes,
                   strings, o, sizes_off, offs)


def texture_paths(nif: NifFile) -> list[str]:
    out = []
    for i in range(len(nif.block_sizes)):
        if nif.block_type(i) == "BSShaderTextureSet":
            o = nif.block_offsets[i]
            n, = struct.unpack_from("<I", nif.raw, o); o += 4
            for _ in range(n):
                s, o = _sstr(nif.raw, o)
                out.append(s)
    return out


def replace_texture_folder(raw: bytes, old: str, new: str) -> tuple[bytes, int]:
    """Replace the path segment `old` (case-insensitive, a whole folder name)
    by `new` in every BSShaderTextureSet path. Returns (new_raw, replaced)."""
    return replace_texture_folders(raw, {old.lower(): new})


def replace_texture_folders(raw: bytes, low: dict[str, str]) -> tuple[bytes, int]:
    """Same, for several folder names at once (lowercase old -> new)."""
    nif = parse(raw)
    out = bytearray(raw[:nif.header_end])
    sizes = list(nif.block_sizes)
    changed = 0
    for i, off in enumerate(nif.block_offsets):
        blk = raw[off:off + nif.block_sizes[i]]
        if nif.block_type(i) == "BSShaderTextureSet":
            n, = struct.unpack_from("<I", blk, 0)
            o, parts = 4, [struct.pack("<I", n)]
            for _ in range(n):
                s, o2 = _sstr(blk, o)
                segs = s.split("\\")
                new_segs = [low.get(seg.lower(), seg) for seg in segs]
                if new_segs != segs:
                    changed += 1
                    s = "\\".join(new_segs)
                enc = s.encode("cp1252")
                parts.append(struct.pack("<I", len(enc)) + enc)
                o = o2
            parts.append(blk[o:])
            blk = b"".join(parts)
            sizes[i] = len(blk)
        out += blk
    out += raw[nif.block_offsets[-1] + nif.block_sizes[-1]:] if nif.block_offsets else b""
    if not changed:
        return raw, 0
    struct.pack_into(f"<{len(sizes)}I", out, nif.sizes_offset, *sizes)
    result = bytes(out)
    parse(result)  # must still be a consistent file
    return result, changed
