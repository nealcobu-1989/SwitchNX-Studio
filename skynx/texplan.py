"""Texture rules for the converter: target size and format per file.

Formats follow Koka's SNXT-DDS rules (DDS-Formats.ps1):
- Without the SDK the texture stays a PC DDS and everything is forced to
  DXT5 (BC3); BC5 normal maps are kept.
- With NvnTexpkg (SDK) BC1 stays BC1, R8 becomes BC1, BC4/RG8 become BC5,
  BC7 and the rest become BC3, and NvnTexpkg writes the native DFvN file.
  Only here can opaque textures drop to BC1 (half the memory), because BC1
  survives the conversion.
Sizes: Koka's base rules (1024 by default, 2048 for actors and Pandorable),
plus two lighter "Switch 1" presets, or "none" (no preset sizes). On top of
the preset, max_size (256..4096, the sizes Koka's NX Toolkit frontend offers)
caps the largest side of every texture. A texture is never enlarged, user
interface textures are never resized, and the full mip chain is rebuilt,
as Koka's rules do.

Code that only knows a preset name (diet.py) can get the cap too through
with_cap(): "koka:1024" means the koka sizes, at most 1024.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .textures import TexInfo, _mip_total

# Suffixes of non-colour maps (Skyrim NX Toolkit sizes.py notes).
MAP_SUFFIX = re.compile(r"_(n|msn|s|m|g|glow|emit|e|em|envmap|b|bl|p|h|sk|hh|hl|rim)\.dds$", re.I)
NO_RESIZE = re.compile(r"(^|\\)(interface|menus?)\\", re.I)
CHARACTER = re.compile(r"(^|\\)actors\\character\\", re.I)
ACTORS = re.compile(r"(^|\\)actors\\", re.I)
PANDORABLE = re.compile(r"(^|\\)pandorable", re.I)
SMALL_STUFF = re.compile(r"(^|\\)(clutter|effects|plants|landscape\\grass)\\", re.I)

PRESETS = ("koka", "diet", "extreme")
DEFAULT_PRESET = "diet"           # the "Switch version" sizes
NO_PRESET = "none"                       # only max_size (if any) limits the size
MAX_SIZES = (256, 512, 1024, 2048, 4096)


def with_cap(preset: str, max_size: int | None) -> str:
    """Preset name that also carries a max_size ("koka:1024")."""
    return f"{split_preset(preset)[0]}:{int(max_size)}" if max_size else preset


def split_preset(preset: str) -> tuple[str, int | None]:
    base, _, cap = (preset or "koka").partition(":")
    return base, (int(cap) if cap.isdigit() else None)


def check_max_size(v) -> int | None:
    """None/0/"" mean no cap; anything else must be one of MAX_SIZES."""
    if v in (None, 0, "", "none", "0"):
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = -1
    if n not in MAX_SIZES:
        raise ValueError(f"max_size must be one of {MAX_SIZES} or None, not {v!r}")
    return n


def max_side(rel: str, preset: str) -> int | None:
    """Largest side allowed for this texture (None: never resize). The preset
    rule is by area (side x side), like Koka's; a ":N" cap lowers it."""
    rel = rel.replace("/", "\\")
    if NO_RESIZE.search(rel):
        return None
    preset, cap = split_preset(preset)
    side = _preset_side(rel, preset)
    if cap:
        side = min(side, cap) if side else cap
    return side


def _preset_side(rel: str, preset: str) -> int | None:
    if preset == NO_PRESET:
        return None
    if preset == "koka":
        if ACTORS.search(rel) or PANDORABLE.search(rel):
            return 2048
        return 1024
    if preset == "diet":
        if MAP_SUFFIX.search(rel):
            return 512
        if SMALL_STUFF.search(rel):
            return 512
        return 1024
    # extreme
    if MAP_SUFFIX.search(rel):
        return 256
    if CHARACTER.search(rel):
        return 1024
    return 512


BPP = {"BC1": 0.5, "BC4": 0.5, "BC2": 1.0, "BC3": 1.0, "BC5": 1.0, "BC7": 1.0, "BC6H": 1.0,
       "RGBA8": 4.0, "BGRA8": 4.0, "R8": 1.0, "RG8": 2.0}
TEXCONV_FMT = {"BC1": "BC1_UNORM", "BC2": "BC2_UNORM", "BC3": "BC3_UNORM", "BC5": "BC5_UNORM"}


def target_format(src: str, sdk: bool) -> str:
    if src == "BC5":
        return "BC5"
    if not sdk:
        return "BC3"
    if src in ("BC1", "R8"):
        return "BC1"
    if src in ("BC4", "RG8"):
        return "BC5"
    if src == "BC2":
        return "BC2"
    return "BC3"


def est_bytes(fmt: str, w: int, h: int, mips: int, cube: bool = False) -> int:
    bpp = BPP.get(fmt, 1.0)
    block = fmt.startswith("BC")
    n = _mip_total(w, h, mips, bpp, block)
    return n * 6 if cube else n


def full_mips(w: int, h: int) -> int:
    n = 1
    while max(w, h) > 1:
        w, h = max(1, w // 2), max(1, h // 2)
        n += 1
    return n


@dataclass
class TexPlan:
    rel: str
    src_fmt: str
    w: int
    h: int
    mips: int
    cube: bool
    fmt: str
    tw: int
    th: int
    tmips: int
    texconv: bool          # texconv has to run (format, size or mips change)
    nvn: bool              # NvnTexpkg will run afterwards
    before: int
    after: int
    skip: str = ""         # why it is left alone ("switch", "unknown")

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("rel", "src_fmt", "w", "h", "fmt", "tw", "th",
                                              "texconv", "nvn", "before", "after", "skip")}


def plan_texture(rel: str, info: TexInfo | None, preset: str, sdk: bool,
                 max_size: int | None = None) -> TexPlan:
    """max_size: the largest side any non-interface texture may keep (halved
    until it fits; never enlarged), on top of the preset's own sizes."""
    if info is None or info.container == "?":
        return TexPlan(rel, "?", 0, 0, 0, False, "?", 0, 0, 0, False, False, 0, 0, "unknown")
    if info.container == "NVN":
        b = info.est_bytes
        return TexPlan(rel, info.fmt, info.width, info.height, info.mips, info.cubemap, info.fmt,
                       info.width, info.height, info.mips, False, False, b, b, "switch")
    w, h = info.width, info.height
    before = est_bytes(info.fmt, w, h, info.mips, info.cubemap)
    base, cap = split_preset(preset)
    cap = max_size or cap
    interface = bool(NO_RESIZE.search(rel.replace("/", "\\")))
    side = None if interface else _preset_side(rel.replace("/", "\\"), base)
    tw, th = w, h
    if side:
        while tw * th > side * side and min(tw, th) > 4:
            tw, th = max(1, tw // 2), max(1, th // 2)
    if cap and not interface:
        while max(tw, th) > cap:
            tw, th = max(1, tw // 2), max(1, th // 2)
    fmt = target_format(info.fmt, sdk)
    tmips = info.mips if interface else full_mips(tw, th)
    run = (fmt != info.fmt) or (tw, th) != (w, h) or tmips != info.mips
    after = est_bytes(fmt, tw, th, tmips, info.cubemap)
    return TexPlan(rel, info.fmt, w, h, info.mips, info.cubemap, fmt, tw, th, tmips, run, sdk,
                   before, after)


def texconv_args(exe, src, out_dir, plan: TexPlan) -> list:
    # -sepalpha: alpha resized/mipped on its own (the Toolkit always uses it);
    # -dx9: legacy DXT1/DXT5/ATI2 headers, the ones the Switch tools expect.
    args = [exe, "-nologo", "-y", "-dx9", "-sepalpha", "-f", TEXCONV_FMT[plan.fmt]]
    if (plan.tw, plan.th) != (plan.w, plan.h):
        args += ["-w", str(plan.tw), "-h", str(plan.th)]
    args += ["-m", str(plan.tmips if plan.tmips != full_mips(plan.tw, plan.th) else 0)]
    args += ["-o", out_dir, src]
    return args
