"""Texture header inspection: PC DDS and Switch NVN (DFvN / XTX).

Only headers are read. Memory estimates use the real data size for NVN
textures and width x height x bits-per-pixel x mip factor for DDS.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

# NVN format ids seen in real Switch mods; bytes-per-pixel verified against
# data sizes (BC1 0.5 B/px, BC2/BC3 1 B/px, RGBA8 4 B/px).
NVN_FORMATS = {
    0x01: ("R8", 1.0), 0x0D: ("RG8", 2.0), 0x25: ("RGBA8", 4.0), 0x38: ("RGBA8_SRGB", 4.0),
    0x42: ("BC1", 0.5), 0x43: ("BC2", 1.0), 0x44: ("BC3", 1.0),
    0x49: ("BC4", 0.5), 0x4A: ("BC4S", 0.5), 0x4B: ("BC5", 1.0), 0x4C: ("BC5S", 1.0),
}
DXGI = {71: ("BC1", 0.5), 72: ("BC1", 0.5), 74: ("BC2", 1.0), 77: ("BC3", 1.0),
        78: ("BC3", 1.0), 80: ("BC4", 0.5), 83: ("BC5", 1.0), 95: ("BC6H", 1.0),
        98: ("BC7", 1.0), 99: ("BC7", 1.0), 28: ("RGBA8", 4.0), 29: ("RGBA8", 4.0),
        87: ("BGRA8", 4.0), 61: ("R8", 1.0), 49: ("RG8", 2.0)}
FOURCC = {b"DXT1": ("BC1", 0.5), b"DXT3": ("BC2", 1.0), b"DXT5": ("BC3", 1.0),
          b"ATI1": ("BC4", 0.5), b"BC4U": ("BC4", 0.5), b"ATI2": ("BC5", 1.0),
          b"BC5U": ("BC5", 1.0)}


@dataclass
class TexInfo:
    container: str          # "DDS" (PC), "NVN" (Switch), "?" unknown
    fmt: str
    width: int
    height: int
    mips: int
    cubemap: bool
    est_bytes: int

    @property
    def max_dim(self) -> int:
        return max(self.width, self.height)


def _mip_total(w: int, h: int, mips: int, bpp: float, block: bool) -> int:
    total = 0
    for _ in range(max(1, mips)):
        if block:
            bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
            total += int(bw * bh * 16 * bpp)
        else:
            total += int(w * h * bpp)
        w, h = max(1, w // 2), max(1, h // 2)
    return total


def inspect(head: bytes) -> TexInfo | None:
    if head[:4] == b"DFvN":
        off = struct.unpack_from("<I", head, 4)[0]
        while off + 0x24 <= len(head):
            mg, _hs, ds, doff, typ = struct.unpack_from("<4sIQQI", head, off)
            if mg != b"HBvN":
                break
            if typ == 2 and off + doff + 32 <= len(head):
                dsz, _al, w, h, _d, tgt, fmt, mips = struct.unpack_from(
                    "<QIIIIIII", head, off + doff)
                name = NVN_FORMATS.get(fmt, (f"nvn{fmt:#x}", 1.0))[0]
                return TexInfo("NVN", name, w, h, mips, tgt in (8, 9), int(dsz))  # NVN: 8 cube, 9 cube array
            off += doff + ds
        return TexInfo("NVN", "?", 0, 0, 0, False, 0)
    if head[:4] == b"DDS " and len(head) >= 128:
        h, w = struct.unpack_from("<II", head, 12)
        mips = struct.unpack_from("<I", head, 28)[0] or 1
        fourcc = head[84:88]
        caps2 = struct.unpack_from("<I", head, 112)[0]
        cube = bool(caps2 & 0x200)
        if fourcc == b"DX10" and len(head) >= 148:
            name, bpp = DXGI.get(struct.unpack_from("<I", head, 128)[0], ("dx10?", 1.0))
        elif fourcc in FOURCC:
            name, bpp = FOURCC[fourcc]
        else:
            bits = struct.unpack_from("<I", head, 88)[0]
            name, bpp = ("RGBA8" if bits == 32 else f"raw{bits}", max(bits, 8) / 8)
        block = name.startswith("BC")
        size = _mip_total(w, h, mips, bpp, block)
        if cube:
            size *= 6
        return TexInfo("DDS", name, w, h, mips, cube, size)
    return None


# ---------------------------------------------------------------- pixel checks
def is_opaque(raw: bytes) -> bool | None:
    """True when every pixel of the top mip of a PC DDS has alpha 255.

    Used by the BC1 diet: a texture whose alpha is never used can be stored as
    BC1 (half of BC3) without losing anything. None if it can't be decoded.
    """
    info = inspect(raw[:256])
    if not info or info.container != "DDS" or info.cubemap:
        return None
    try:
        import texture2ddecoder as t2d  # type: ignore
    except ImportError:
        return None
    w, h = info.width, info.height
    off = 148 if raw[84:88] == b"DX10" else 128
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    decoders = {"BC1": (t2d.decode_bc1, 8), "BC2": (None, 16), "BC3": (t2d.decode_bc3, 16),
                "BC7": (t2d.decode_bc7, 16)}
    if info.fmt in ("RGBA8", "BGRA8"):
        top = raw[off:off + w * h * 4]
        if len(top) < w * h * 4:
            return None
        alpha = top[3::4]
        return alpha.count(255) == len(alpha)
    if info.fmt == "BC2":
        # explicit 4-bit alpha: first 8 bytes of each 16-byte block
        top = raw[off:off + bw * bh * 16]
        return all(top[i:i + 8] == b"\xff" * 8 for i in range(0, len(top), 16))
    if info.fmt not in decoders:
        return None
    fn, bs = decoders[info.fmt]
    top = raw[off:off + bw * bh * bs]
    if len(top) < bw * bh * bs:
        return None
    try:
        px = fn(top, bw * 4, bh * 4)
    except Exception:  # noqa: BLE001
        return None
    alpha = px[3::4]
    return alpha.count(255) == len(alpha)
