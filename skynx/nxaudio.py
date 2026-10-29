"""Skyrim Switch sound containers.

Layouts come from the Skyrim NX Toolkit (Zappastuff's reverse engineering,
MIT licence) and were checked byte for byte against real converted voices.

FUZE (voices):
    "FUZE", u32 version=1, u32 lip_size, u32 sound_offset,
    lip data, zero padding to 4 bytes,
    Skyrim Opus header: u32 0xFFD58D0A, u32 duration_ms, u32 channels,
                        u32 header_size=0x14, u32 opus_size,
    Nintendo Opus data (starts 0x80000001), zero padding to 4 bytes.
MCADPCM (music and effects):
    u32 channels, then (offset, size) per channel, then one little-endian
    DSP-ADPCM stream per channel.
PC FUZ: "FUZE", u32 version, u32 lip_size, lip, XWMA or WAVE data.
"""
from __future__ import annotations

import struct

FUZE = b"FUZE"
OPUS_SIG = 0xFFD58D0A
NX_OPUS_MAGIC = b"\x01\x00\x00\x80"


class AudioFormatError(ValueError):
    pass


def _pad4(n: int) -> int:
    return (4 - n % 4) % 4


def build_fuz(lip: bytes, nx_opus: bytes, channels: int, duration_ms: int) -> bytes:
    if nx_opus[:4] != NX_OPUS_MAGIC:
        raise AudioFormatError("not a Nintendo Opus stream")
    lp = _pad4(len(lip))
    voff = 0x10 + len(lip) + lp
    out = bytearray(FUZE + struct.pack("<III", 1, len(lip), voff))
    out += lip + b"\x00" * lp
    out += struct.pack("<IIIII", OPUS_SIG, duration_ms, channels, 0x14, len(nx_opus))
    out += nx_opus
    out += b"\x00" * _pad4(len(out))
    return bytes(out)


def parse_nx_fuz(raw: bytes) -> dict:
    if raw[:4] != FUZE:
        raise AudioFormatError("not a FUZ file")
    _ver, lip_size, voff = struct.unpack_from("<III", raw, 4)
    if voff < 0x10 or voff > len(raw):
        raise AudioFormatError("not a Switch FUZ")
    head = raw[voff:voff + 20]
    if len(head) < 20:
        raise AudioFormatError("truncated")
    sig, dur, ch, hs, size = struct.unpack("<IIIII", head)
    if sig != OPUS_SIG:
        raise AudioFormatError("unknown sound header")
    return {"lip": raw[0x10:0x10 + lip_size], "duration_ms": dur, "channels": ch,
            "opus": raw[voff + hs:voff + hs + size]}


def split_pc_fuz(raw: bytes) -> tuple[bytes, bytes, str]:
    """PC FUZ -> (lip, audio, 'xwm' | 'wav'). Raises if it is a Switch FUZ."""
    if raw[:4] != FUZE:
        raise AudioFormatError("not a FUZ file")
    lip_size, = struct.unpack_from("<I", raw, 8)
    audio = raw[12 + lip_size:]
    kind = audio[8:12]
    if audio[:4] != b"RIFF" or kind not in (b"XWMA", b"WAVE"):
        raise AudioFormatError("not a PC FUZ")
    return raw[12:12 + lip_size], audio, "xwm" if kind == b"XWMA" else "wav"


def is_switch_fuz(raw: bytes) -> bool:
    try:
        parse_nx_fuz(raw)
        return True
    except (AudioFormatError, struct.error):
        return False


def check_mcadpcm(raw: bytes) -> int:
    """Validate an MCADPCM file; returns the channel count."""
    if len(raw) < 12:
        raise AudioFormatError("truncated")
    ch, = struct.unpack_from("<I", raw, 0)
    if ch not in (1, 2):
        raise AudioFormatError("bad channel count")
    for i in range(ch):
        off, size = struct.unpack_from("<II", raw, 4 + 8 * i)
        if off + size > len(raw) or off < 4 + 8 * ch:
            raise AudioFormatError("bad channel table")
    return ch


def wav_info(raw: bytes) -> dict:
    """channels, rate, bits and duration of a PCM WAV."""
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise AudioFormatError("not a WAV file")
    o, fmt, data = 12, None, None
    while o + 8 <= len(raw):
        cid, size = struct.unpack_from("<4sI", raw, o)
        if cid == b"fmt ":
            fmt = struct.unpack_from("<HHIIHH", raw, o + 8)
        elif cid == b"data":
            data = min(size, len(raw) - o - 8)
            break
        o += 8 + size + (size & 1)
    if not fmt or data is None:
        raise AudioFormatError("WAV without fmt or data")
    tag, ch, rate, _br, align, bits = fmt
    frames = data // max(1, align)
    return {"format": tag, "channels": ch, "rate": rate, "bits": bits,
            "duration_ms": int(frames * 1000 / rate) if rate else 0}
