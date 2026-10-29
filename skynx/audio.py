"""Audio format detection for .fuz / .xwm / .wav / .mcadpcm (headers only)."""
from __future__ import annotations

import struct

NX_OPUS_MAGIC = b"\x01\x00\x00\x80"   # Nintendo Opus header chunk id 0x80000001


def classify(name: str, head: bytes) -> str:
    """Return 'switch-opus', 'switch-mcadpcm', 'pc-xwma', 'pc-wav', 'switch?' or '?'."""
    low = name.lower()
    if low.endswith(".mcadpcm"):
        return "switch-mcadpcm"
    if head[:4] == b"FUZE" and len(head) >= 12:
        lip = struct.unpack_from("<I", head, 8)[0]
        tail = head[12 + lip: 12 + lip + 64] if 12 + lip < len(head) else b""
        if b"RIFF" in head[:12 + lip + 16] and b"XWMA" in head[:12 + lip + 32]:
            return "pc-xwma"
        if NX_OPUS_MAGIC in tail or NX_OPUS_MAGIC in head[:4096]:
            return "switch-opus"
        if tail[:4] == b"RIFF":
            return "pc-xwma"
        return "switch?"
    if head[:4] == b"RIFF":
        if head[8:12] == b"XWMA":
            return "pc-xwma"
        if head[8:12] == b"WAVE":
            return "pc-wav"
    if NX_OPUS_MAGIC in head[:64]:
        return "switch-opus"
    return "?"
