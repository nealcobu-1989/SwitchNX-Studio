"""Native Switch textures (NVN "DFvN" files, also called XTX): read and write.

Container (all little-endian), as found in every Switch texture we checked:

  File header, 16 bytes   "DFvN" (NvFD), u32 header size (16), u32 major 1,
                          u32 minor 1.
  Blocks, one after another until the end of the file. Each block starts
  with a 36-byte "HBvN" (NvBH) header:
      u32 magic, u32 header size (0x24), u64 data size,
      u64 data offset (from the start of this block), u32 type,
      u32 block id (0, 1, 2... in file order), u32 index within its type.
    type 2  texture info, 0x78 bytes:
      u64 data size, u32 alignment (512), u32 width, u32 height, u32 depth,
      u32 target (NVN: 1 = 2D, 4 = 2D array, 8 = cubemap, 9 = cube array),
      u32 format (NVN format id), u32 mip count, u32 slice size,
      u32 mip offsets[17] (inside the data block),
      u32 packaged layout[2] (4, 7: largest block height as log2 GOBs, and
      flags the driver reads), u32 reserved (0).
    type 3  texture data. Its data offset is chosen so the data starts on a
            512-byte boundary of the file (zero padding in between).
    type 5  end block, 24 bytes: u64 0, u32 texture count, u32 data block
            count, u64 0.

Texture data uses the Tegra X1 "block-linear" layout. Rows of bytes (one row
of BC blocks, or of pixels for uncompressed formats) are cut into GOBs of
64 bytes x 8 rows = 512 bytes. Inside a GOB the bytes go in 16-byte x 2-row
sectors:
    offset = (x % 64 // 32) * 256 + (y % 8 // 2) * 64 + (x % 32 // 16) * 32
             + (y % 2) * 16 + x % 16
GOBs are stacked vertically in blocks of "block height" GOBs (1, 2, 4, 8, 16
or 32), and blocks are laid out left to right, then top to bottom. The block
height starts at the packaged layout's maximum (16) and is halved while the
image (in GOBs) fits in half of it, separately for every mip level.

Two writers produced the files found in real Switch mods, and both are
reproduced byte for byte:

  "nvn"      Nintendo's NvnTexpkg (SDK). Every mip is padded to whole blocks
             of GOBs, mip offsets follow each other, padding is zero.
  "toolkit"  The Skyrim NX Toolkit without the SDK (its XTX writer). Mip
             offsets are the plain linear sizes, so every mip occupies its
             linear size only. Large mips are ordinary block-linear; for mips
             narrower than 64 bytes or shorter than 8 rows that writer packed
             GOBs more tightly (bits of x and y interleaved only as far as
             the image goes) and dropped bytes that fell outside the linear
             size. The toolkit always made power-of-two textures.

New files are always written in the "nvn" layout, which is the one the GPU
reads correctly at every mip level.

Arrays and cubemaps: each layer holds a full mip chain and layers follow
each other at "slice size" bytes. No real file with layers was available,
so this part is implemented from the layout rules but not verified.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field

import numpy as np

from .errors import SkynxError

FILE_MAGIC = b"DFvN"
BLOCK_MAGIC = b"HBvN"
FILE_HEADER = struct.Struct("<4sIII")
BLOCK_HEADER = struct.Struct("<4sIQQIII")
TEX_INFO = struct.Struct("<QIIIIIIII17IIII")
END_DATA = struct.Struct("<QIIQ")
BLOCK_INFO, BLOCK_DATA, BLOCK_END = 2, 3, 5

ALIGNMENT = 512
GOB_BYTES, GOB_W, GOB_H = 512, 64, 8
MAX_BH_LOG2 = 4              # packaged layout word 0 in every file: 16 GOBs
LAYOUT_FLAGS = 7             # packaged layout word 1 in every file
MAX_MIPS = 17

TARGET_2D, TARGET_2D_ARRAY, TARGET_CUBE, TARGET_CUBE_ARRAY = 1, 4, 8, 9


@dataclass(frozen=True)
class Fmt:
    nvn: int
    name: str
    block: int               # 4 for BC formats, 1 for plain pixels
    bpb: int                 # bytes per block (or per pixel)
    fourcc: bytes | None     # legacy DDS FourCC
    dxgi: int                # DXGI format for DX10 DDS headers


FORMATS = {f.nvn: f for f in (
    Fmt(0x01, "R8", 1, 1, None, 61),
    Fmt(0x0D, "RG8", 1, 2, None, 49),
    Fmt(0x25, "RGBA8", 1, 4, None, 28),
    Fmt(0x38, "RGBA8_SRGB", 1, 4, None, 29),
    Fmt(0x42, "BC1", 4, 8, b"DXT1", 71),
    Fmt(0x43, "BC2", 4, 16, b"DXT3", 74),
    Fmt(0x44, "BC3", 4, 16, b"DXT5", 77),
    Fmt(0x49, "BC4", 4, 8, b"ATI1", 80),
    Fmt(0x4A, "BC4S", 4, 8, None, 81),
    Fmt(0x4B, "BC5", 4, 16, b"ATI2", 83),
    Fmt(0x4C, "BC5S", 4, 16, None, 84),
)}
BY_NAME = {f.name: f for f in FORMATS.values()}
BY_FOURCC = {b"DXT1": 0x42, b"DXT3": 0x43, b"DXT5": 0x44, b"ATI1": 0x49, b"BC4U": 0x49,
             b"BC4S": 0x4A, b"ATI2": 0x4B, b"BC5U": 0x4B, b"BC5S": 0x4C}
BY_DXGI = {f.dxgi: f.nvn for f in FORMATS.values()}
BY_DXGI[87] = 0x25           # B8G8R8A8: channels are swapped on read


class NvnError(SkynxError):
    pass


def _err(en: str, es: str) -> NvnError:
    return NvnError(en, es)


# --------------------------------------------------------------------------
# Linear (PC) surfaces
# --------------------------------------------------------------------------
@dataclass
class Surface:
    """A texture in plain linear order: levels[layer][mip] -> bytes."""
    fmt: int
    width: int
    height: int
    cube: bool = False
    levels: list[list[bytes]] = field(default_factory=list)

    @property
    def mips(self) -> int:
        return len(self.levels[0]) if self.levels else 0

    @property
    def layers(self) -> int:
        return len(self.levels)

    @property
    def info(self) -> Fmt:
        return FORMATS[self.fmt]


def mip_dims(w: int, h: int, level: int) -> tuple[int, int]:
    return max(1, w >> level), max(1, h >> level)


def level_geometry(fmt: int, w: int, h: int, level: int) -> tuple[int, int]:
    """(bytes per row, rows) of one mip level, rows counted in blocks."""
    f = FORMATS[fmt]
    mw, mh = mip_dims(w, h, level)
    return -(-mw // f.block) * f.bpb, -(-mh // f.block)


def linear_size(fmt: int, w: int, h: int, level: int) -> int:
    wb, rows = level_geometry(fmt, w, h, level)
    return wb * rows


# --------------------------------------------------------------------------
# Block-linear addressing
# --------------------------------------------------------------------------
def block_height(rows: int, max_log2: int = MAX_BH_LOG2) -> int:
    """Block height in GOBs for an image `rows` rows high."""
    bh = 1 << max_log2
    gobs = -(-rows // GOB_H)
    while bh > 1 and gobs <= bh // 2:
        bh //= 2
    return bh


def nvn_level_size(wb: int, rows: int, bh: int) -> int:
    gobs_w = -(-wb // GOB_W)
    gobs_h = -(-rows // GOB_H)
    return gobs_w * (-(-gobs_h // bh) * bh) * GOB_BYTES


def _unit(wb: int) -> int:
    # Bytes inside a 16-byte sector row are contiguous in both layouts, so
    # we move data in chunks of up to 16 bytes.
    return math.gcd(wb, 16)


def _nvn_offsets(wb: int, rows: int, bh: int, unit: int) -> np.ndarray:
    """Byte offset of every `unit`-byte chunk of the image, shape (rows, wb/unit)."""
    x = np.arange(0, wb, unit, dtype=np.int64)[None, :]
    y = np.arange(rows, dtype=np.int64)[:, None]
    gobs_w = -(-wb // GOB_W)
    inside = ((x % 64) // 32) * 256 + ((y % 8) // 2) * 64 + ((x % 32) // 16) * 32 \
        + (y % 2) * 16 + x % 16
    block_rows = GOB_H * bh
    gob = ((y // block_rows) * gobs_w + x // GOB_W) * (GOB_BYTES * bh) \
        + ((y % block_rows) // GOB_H) * GOB_BYTES
    return gob + inside


def _toolkit_offsets(wb: int, rows: int, unit: int) -> np.ndarray:
    """Chunk offsets as the Skyrim NX Toolkit's XTX writer placed them.

    Address bits are taken alternately from x and y: x bits 0-3 (16 bytes),
    one y bit, x bit 4, two y bits, x bit 5, up to four y bits (the block
    height). A step is taken only while the (power-of-two) width still has
    more x bits than that step uses, and each y step takes at most the bits
    the height has left. What remains of x and y then selects the block,
    with rows of blocks one GOB-padded width apart. For large images this
    is exactly the block-linear layout above.
    """
    x = np.arange(0, wb, unit, dtype=np.int64)[None, :]
    y = np.arange(rows, dtype=np.int64)[:, None]
    xbits = (wb - 1).bit_length()          # log2 of the power-of-two width
    ybits = (rows - 1).bit_length()
    pitch = -(-wb // GOB_W) * GOB_W
    if xbits <= 4:                         # 16 bytes or less: one row per 64 bytes
        return y * pitch + x
    addr = x & 15
    xs, ys = x >> 4, y
    pos, xused, yused = 4, 4, 0
    ycnt = 1                               # first step always takes one y bit
    addr = addr | ((ys & 1) << pos)
    ys, pos, yused = ys >> 1, pos + 1, 1
    for _ in range(2):
        if xused + 1 >= xbits:
            break
        addr = addr | ((xs & 1) << pos)
        xs, pos, xused = xs >> 1, pos + 1, xused + 1
        ycnt = max(0, min(ybits - yused, ycnt * 2))
        addr = addr | ((ys & ((1 << ycnt) - 1)) << pos)
        ys, pos, yused = ys >> ycnt, pos + ycnt, yused + ycnt
    return addr | ((xs + ys * (pitch >> xused)) << pos)


def _deswizzle_level(buf: bytes, wb: int, rows: int, offsets: np.ndarray, unit: int,
                     size: int) -> bytes:
    src = np.frombuffer(buf, dtype=np.uint8)
    lin_size = wb * rows
    if size >= int(offsets.max()) + unit:
        chunks = src[:size].reshape(-1, unit)
        return chunks[(offsets // unit).ravel()].tobytes()
    # Toolkit files: chunks the writer dropped are left where they are.
    out = np.frombuffer(bytes(buf[:lin_size]).ljust(lin_size, b"\0"), np.uint8).copy()
    off = offsets.ravel()
    ok = off + unit <= size
    out.reshape(-1, unit)[ok] = src[:size - size % unit].reshape(-1, unit)[off[ok] // unit]
    return out.tobytes()


def _swizzle_level(lin: bytes, wb: int, rows: int, offsets: np.ndarray, unit: int,
                   size: int) -> bytes:
    src = np.frombuffer(lin, dtype=np.uint8).reshape(-1, unit)
    off = offsets.ravel()
    if size >= int(off.max()) + unit:
        out = np.zeros(size, dtype=np.uint8)
        out.reshape(-1, unit)[off // unit] = src
        return out.tobytes()
    out = np.frombuffer(lin, np.uint8).copy()
    ok = off + unit <= size
    out.reshape(-1, unit)[off[ok] // unit] = src[ok]
    return out.tobytes()


# --------------------------------------------------------------------------
# Layout plans
# --------------------------------------------------------------------------
@dataclass
class Layout:
    style: str
    level_sizes: list[int]
    mip_offsets: list[int]
    slice_size: int
    data_size: int
    block_heights: list[int]


def plan_layout(fmt: int, w: int, h: int, mips: int, layers: int = 1, style: str = "nvn",
                max_bh_log2: int = MAX_BH_LOG2) -> Layout:
    """Sizes and offsets of every level, computed from the image alone."""
    sizes, offs, bhs, o = [], [], [], 0
    for lv in range(mips):
        wb, rows = level_geometry(fmt, w, h, lv)
        if style == "nvn":
            bh = block_height(rows, max_bh_log2)
            size = nvn_level_size(wb, rows, bh)
        elif style == "toolkit":
            bh = 0
            size = wb * rows
        else:
            raise ValueError(style)
        offs.append(o)
        sizes.append(size)
        bhs.append(bh)
        o += size
    slice_size = o
    if layers > 1 and style == "nvn":
        # Layers start on a whole block of the first mip (unverified).
        unit = bhs[0] * GOB_BYTES
        slice_size = -(-o // unit) * unit
    return Layout(style, sizes, offs, slice_size, slice_size * layers, bhs)


def _level_offsets(style: str, wb: int, rows: int, bh: int, unit: int) -> np.ndarray:
    if style == "nvn":
        return _nvn_offsets(wb, rows, bh, unit)
    return _toolkit_offsets(wb, rows, unit)


# --------------------------------------------------------------------------
# DFvN files
# --------------------------------------------------------------------------
@dataclass
class NvnTexture:
    fmt: int
    width: int
    height: int
    depth: int
    target: int
    mips: int
    alignment: int
    data_size: int
    slice_size: int
    mip_offsets: list[int]
    layout: tuple[int, int, int]
    style: str                       # "nvn", "toolkit" or "?" (unknown writer)
    data: bytes = b""

    @property
    def name(self) -> str:
        f = FORMATS.get(self.fmt)
        return f.name if f else f"nvn{self.fmt:#x}"

    @property
    def cube(self) -> bool:
        return self.target in (TARGET_CUBE, TARGET_CUBE_ARRAY)

    @property
    def layers(self) -> int:
        if self.target in (TARGET_2D_ARRAY, TARGET_CUBE, TARGET_CUBE_ARRAY):
            return max(1, self.depth)
        return 1

    @property
    def supported(self) -> bool:
        return self.fmt in FORMATS and self.style != "?" and self.target in (
            TARGET_2D, TARGET_2D_ARRAY, TARGET_CUBE, TARGET_CUBE_ARRAY) and \
            (self.depth == 1 or self.target != TARGET_2D)


def is_nvn(raw: bytes) -> bool:
    return raw[:4] == FILE_MAGIC


def parse(raw: bytes) -> NvnTexture:
    """Read the container (first texture) and work out which writer made it."""
    if raw[:4] != FILE_MAGIC or len(raw) < FILE_HEADER.size:
        raise _err("Not a Switch texture (no DFvN header).",
                   "No es una textura de Switch (falta la cabecera DFvN).")
    _m, hsize, major, _minor = FILE_HEADER.unpack_from(raw, 0)
    if major != 1:
        raise _err(f"Unsupported DFvN version {major}.", f"Versión de DFvN no soportada: {major}.")
    off, info, data = hsize, None, None
    while off + BLOCK_HEADER.size <= len(raw):
        mg, _bh, dsize, doff, typ, _bid, _tix = BLOCK_HEADER.unpack_from(raw, off)
        if mg != BLOCK_MAGIC:
            raise _err(f"Broken DFvN block at byte {off}.", f"Bloque DFvN dañado en el byte {off}.")
        start = off + doff
        if typ == BLOCK_INFO and info is None:
            if dsize < TEX_INFO.size or start + TEX_INFO.size > len(raw):
                raise _err("Truncated DFvN texture info.", "Información de textura DFvN incompleta.")
            info = TEX_INFO.unpack_from(raw, start)
        elif typ == BLOCK_DATA and data is None:
            data = raw[start:start + dsize]
            if len(data) != dsize:
                raise _err("Truncated DFvN texture data.", "Datos de textura DFvN incompletos.")
        elif typ == BLOCK_END:
            break
        off = start + dsize
    if info is None or data is None:
        raise _err("DFvN file without texture info or data.",
                   "Archivo DFvN sin información o datos de textura.")
    dsz, align, w, h, depth, target, fmt, mips, slice_size = info[:9]
    offsets = list(info[9:9 + MAX_MIPS])
    layout = tuple(info[26:29])
    tex = NvnTexture(fmt, w, h, depth, target, mips, align, dsz, slice_size,
                     offsets[:mips], layout, "?", data)
    if fmt in FORMATS and 1 <= mips <= MAX_MIPS and w and h:
        for style in ("nvn", "toolkit"):
            if style == "toolkit" and (w & (w - 1) or h & (h - 1)):
                continue                     # the toolkit only made power-of-two sizes
            lay = plan_layout(fmt, w, h, mips, tex.layers, style, layout[0] or MAX_BH_LOG2)
            if lay.mip_offsets == tex.mip_offsets and lay.data_size == dsz \
                    and lay.slice_size == slice_size:
                tex.style = style
                break
    return tex


def deswizzle(tex: NvnTexture) -> Surface:
    """Linear surface of a parsed DFvN texture (all layers and mips)."""
    if not tex.supported:
        raise _err(f"This Switch texture can't be read ({tex.name}, target {tex.target}, "
                   f"{'unknown layout' if tex.style == '?' else 'unsupported'}).",
                   f"Esta textura de Switch no se puede leer ({tex.name}, destino {tex.target}, "
                   f"{'disposición desconocida' if tex.style == '?' else 'no soportada'}).")
    lay = plan_layout(tex.fmt, tex.width, tex.height, tex.mips, tex.layers, tex.style,
                      tex.layout[0] or MAX_BH_LOG2)
    surf = Surface(tex.fmt, tex.width, tex.height, tex.cube, [])
    for layer in range(tex.layers):
        base = layer * lay.slice_size
        lv_out = []
        for lv in range(tex.mips):
            wb, rows = level_geometry(tex.fmt, tex.width, tex.height, lv)
            unit = _unit(wb)
            offs = _level_offsets(tex.style, wb, rows, lay.block_heights[lv], unit)
            start = base + lay.mip_offsets[lv]
            buf = tex.data[start:start + lay.level_sizes[lv]]
            lv_out.append(_deswizzle_level(buf, wb, rows, offs, unit, lay.level_sizes[lv]))
        surf.levels.append(lv_out)
    return surf


def build(surf: Surface, style: str = "nvn") -> bytes:
    """A complete DFvN file for a linear surface. Every header field is computed."""
    if surf.fmt not in FORMATS:
        raise _err("Unsupported texture format for Switch.", "Formato de textura no soportado en Switch.")
    mips, layers = surf.mips, surf.layers
    if not 1 <= mips <= MAX_MIPS:
        raise _err(f"Too many mip levels ({mips}).", f"Demasiados niveles de mip ({mips}).")
    lay = plan_layout(surf.fmt, surf.width, surf.height, mips, layers, style)
    data = bytearray(lay.data_size)
    for layer, levels in enumerate(surf.levels):
        base = layer * lay.slice_size
        for lv, lin in enumerate(levels):
            wb, rows = level_geometry(surf.fmt, surf.width, surf.height, lv)
            if len(lin) != wb * rows:
                raise _err(f"Mip {lv} has the wrong size.", f"El mip {lv} tiene un tamaño incorrecto.")
            unit = _unit(wb)
            offs = _level_offsets(style, wb, rows, lay.block_heights[lv], unit)
            sw = _swizzle_level(lin, wb, rows, offs, unit, lay.level_sizes[lv])
            start = base + lay.mip_offsets[lv]
            data[start:start + len(sw)] = sw
    if surf.cube:
        target = TARGET_CUBE if layers == 6 else TARGET_CUBE_ARRAY
    else:
        target = TARGET_2D if layers == 1 else TARGET_2D_ARRAY
    depth = layers
    out = bytearray(FILE_HEADER.pack(FILE_MAGIC, FILE_HEADER.size, 1, 1))
    offsets = lay.mip_offsets + [0] * (MAX_MIPS - mips)
    info = TEX_INFO.pack(lay.data_size, ALIGNMENT, surf.width, surf.height, depth, target,
                         surf.fmt, mips, lay.slice_size, *offsets, MAX_BH_LOG2, LAYOUT_FLAGS, 0)
    out += BLOCK_HEADER.pack(BLOCK_MAGIC, BLOCK_HEADER.size, len(info), BLOCK_HEADER.size,
                             BLOCK_INFO, 0, 0) + info
    block = len(out)
    data_start = -(-(block + BLOCK_HEADER.size) // ALIGNMENT) * ALIGNMENT
    out += BLOCK_HEADER.pack(BLOCK_MAGIC, BLOCK_HEADER.size, len(data), data_start - block,
                             BLOCK_DATA, 1, 0)
    out += b"\0" * (data_start - len(out)) + data
    end = END_DATA.pack(0, 1, 1, 0)
    out += BLOCK_HEADER.pack(BLOCK_MAGIC, BLOCK_HEADER.size, len(end), BLOCK_HEADER.size,
                             BLOCK_END, 2, 0) + end
    return bytes(out)


# --------------------------------------------------------------------------
# PC DDS
# --------------------------------------------------------------------------
DDSD_CAPS, DDSD_HEIGHT, DDSD_WIDTH, DDSD_PITCH = 0x1, 0x2, 0x4, 0x8
DDSD_PIXELFORMAT, DDSD_MIPMAPCOUNT, DDSD_LINEARSIZE = 0x1000, 0x20000, 0x80000
DDPF_ALPHAPIXELS, DDPF_FOURCC, DDPF_RGB = 0x1, 0x4, 0x40
DDSCAPS_COMPLEX, DDSCAPS_TEXTURE, DDSCAPS_MIPMAP = 0x8, 0x1000, 0x400000
DDSCAPS2_CUBEMAP_ALL = 0xFE00


def write_dds(surf: Surface) -> bytes:
    f = surf.info
    w, h, mips = surf.width, surf.height, surf.mips
    compressed = f.block == 4
    flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT
    flags |= DDSD_LINEARSIZE if compressed else DDSD_PITCH
    if mips > 1:
        flags |= DDSD_MIPMAPCOUNT
    wb, rows = level_geometry(surf.fmt, w, h, 0)
    pitch = wb * rows if compressed else wb
    caps = DDSCAPS_TEXTURE | ((DDSCAPS_COMPLEX | DDSCAPS_MIPMAP) if mips > 1 else 0)
    caps2 = 0
    if surf.cube:
        caps |= DDSCAPS_COMPLEX
        caps2 = DDSCAPS2_CUBEMAP_ALL
    dx10 = b""
    if f.fourcc and (surf.layers == 1 or surf.cube and surf.layers == 6):
        pf = struct.pack("<II4s5I", 32, DDPF_FOURCC, f.fourcc, 0, 0, 0, 0, 0)
    elif f.nvn == 0x25 and (surf.layers == 1 or surf.cube and surf.layers == 6):
        pf = struct.pack("<II4s5I", 32, DDPF_RGB | DDPF_ALPHAPIXELS, b"\0" * 4, 32,
                         0xFF, 0xFF00, 0xFF0000, 0xFF000000)
    else:
        pf = struct.pack("<II4s5I", 32, DDPF_FOURCC, b"DX10", 0, 0, 0, 0, 0)
        count = surf.layers // 6 if surf.cube else surf.layers
        dx10 = struct.pack("<5I", f.dxgi, 3, 0x4 if surf.cube else 0, count, 0)
    hdr = struct.pack("<4s7I44x", b"DDS ", 124, flags, h, w, pitch, 0, mips)
    hdr += pf + struct.pack("<4I4x", caps, caps2, 0, 0)
    return hdr + dx10 + b"".join(b"".join(lv) for lv in surf.levels)


def read_dds(raw: bytes) -> Surface:
    """Linear surface of a PC DDS file (the formats Switch textures use)."""
    if raw[:4] != b"DDS " or len(raw) < 128:
        raise _err("Not a DDS file.", "No es un archivo DDS.")
    flags, h, w, _pitch, _depth, mips = struct.unpack_from("<6I", raw, 8)
    mips = mips if (flags & DDSD_MIPMAPCOUNT and mips) else 1
    pf_flags, fourcc, bits, rm, gm, bm, am = struct.unpack_from("<I4s5I", raw, 80)
    caps2 = struct.unpack_from("<I", raw, 112)[0]
    cube = bool(caps2 & 0x200)
    layers = 6 if cube else 1
    off, swap = 128, False
    if pf_flags & DDPF_FOURCC and fourcc == b"DX10":
        dxgi, _dim, misc, count = struct.unpack_from("<4I", raw, 128)
        off = 148
        if dxgi not in BY_DXGI:
            raise _err(f"DDS format {dxgi} has no Switch equivalent.",
                       f"El formato DDS {dxgi} no tiene equivalente en Switch.")
        fmt, swap = BY_DXGI[dxgi], dxgi == 87
        cube = bool(misc & 0x4)
        layers = max(1, count) * (6 if cube else 1)
    elif pf_flags & DDPF_FOURCC:
        if fourcc not in BY_FOURCC:
            raise _err(f"DDS format {fourcc!r} has no Switch equivalent.",
                       f"El formato DDS {fourcc!r} no tiene equivalente en Switch.")
        fmt = BY_FOURCC[fourcc]
    elif bits == 32 and (rm, gm, bm) == (0xFF, 0xFF00, 0xFF0000):
        fmt = 0x25
    elif bits == 32 and (rm, gm, bm) == (0xFF0000, 0xFF00, 0xFF):
        fmt, swap = 0x25, True
    elif bits == 8 and rm == 0xFF:
        fmt = 0x01
    else:
        raise _err("Unsupported uncompressed DDS layout.", "Disposición DDS sin comprimir no soportada.")
    surf = Surface(fmt, w, h, cube, [])
    for _ in range(layers):
        levels = []
        for lv in range(mips):
            n = linear_size(fmt, w, h, lv)
            chunk = raw[off:off + n]
            if len(chunk) != n:
                raise _err("The DDS file is truncated.", "El archivo DDS está incompleto.")
            if swap:
                a = np.frombuffer(chunk, np.uint8).reshape(-1, 4)[:, [2, 1, 0, 3]]
                chunk = a.tobytes()
            levels.append(chunk)
            off += n
        surf.levels.append(levels)
    return surf


# --------------------------------------------------------------------------
# Convenience
# --------------------------------------------------------------------------
def to_dds(raw: bytes) -> bytes:
    """DFvN file -> linear PC DDS with every mip (and layer)."""
    return write_dds(deswizzle(parse(raw)))


def from_dds(dds: bytes, style: str = "nvn") -> bytes:
    """Linear PC DDS -> DFvN file in the NvnTexpkg layout (or the toolkit's)."""
    return build(read_dds(dds), style)


def roundtrip(raw: bytes) -> bool:
    """True when deswizzling and rebuilding gives back exactly the same file."""
    tex = parse(raw)
    if not tex.supported:
        return False
    return build(deswizzle(tex), tex.style) == raw


def drop_mips(surf: Surface, levels: int) -> Surface:
    """The same texture without its `levels` largest mips (no re-encoding)."""
    w, h = mip_dims(surf.width, surf.height, levels)
    return Surface(surf.fmt, w, h, surf.cube, [lv[levels:] for lv in surf.levels])


def top_rgba(surf: Surface) -> np.ndarray | None:
    """Top mip of the first layer as an (h, w, 4) RGBA array, or None."""
    w, h = surf.width, surf.height
    data = surf.levels[0][0]
    name = surf.info.name
    if name.startswith("RGBA8"):
        return np.frombuffer(data, np.uint8).reshape(h, w, 4)
    try:
        import texture2ddecoder as t2d  # type: ignore
    except ImportError:
        return None
    bw, bh = -(-w // 4) * 4, -(-h // 4) * 4
    if name == "BC2":
        blocks = np.frombuffer(data, np.uint8).reshape(-1, 16)
        color = t2d.decode_bc1(np.ascontiguousarray(blocks[:, 8:]).tobytes(), bw, bh)
        px = np.frombuffer(color, np.uint8).reshape(bh, bw, 4)[:, :, [2, 1, 0, 3]].copy()
        nib = np.unpackbits(blocks[:, :8].reshape(-1, 8, 1), axis=2, bitorder="little")
        a = (nib.reshape(-1, 16, 4) * (1 << np.arange(4))).sum(axis=2) * 17
        bx = (bw // 4)
        a = a.reshape(bh // 4, bx, 4, 4).transpose(0, 2, 1, 3).reshape(bh, bw)
        px[:, :, 3] = a
        return px[:h, :w]
    fn = {"BC1": t2d.decode_bc1, "BC3": t2d.decode_bc3, "BC4": t2d.decode_bc4,
          "BC5": t2d.decode_bc5}.get(name)
    if fn is None:
        return None
    px = np.frombuffer(fn(data, bw, bh), np.uint8).reshape(bh, bw, 4)[:, :, [2, 1, 0, 3]]
    return px[:h, :w]


def is_opaque(surf: Surface) -> bool | None:
    """Every pixel of the top mip has alpha 255 (None if it can't be told)."""
    name = surf.info.name
    if name == "BC1":
        return None
    if name in ("BC4", "BC4S", "BC5", "BC5S", "R8", "RG8"):
        return True
    px = top_rgba(surf)
    if px is None:
        return None
    return bool((px[:, :, 3] == 255).all())
