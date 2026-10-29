"""Font mods (Sovngarde and the like).

A font mod brings the font libraries (Interface\\fonts_*.swf, which can live in
a BSA) and Interface\\FontConfig.txt, which says which library each part of the
interface uses. The Switch port of Sovngarde (Nexus Switch 244) ships the
libraries in a BSA and tells you to put FontConfig.txt loose in
Data\\Interface; so that one file stays loose here, everything else goes into
BSAs as usual. Only one FontConfig.txt can be active: the last font mod added
wins, and removing it (or undoing) brings the previous one back.

    find_fontconfig(folder) -> Path | None   (a mod folder)
    parse(text) -> FontConfig
    LOOSE_REL                                (where it goes in Data)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

LOOSE_REL = ("Interface", "FontConfig.txt")
NAME = "fontconfig.txt"
# the font libraries the game itself has (Skyrim - Interface.bsa)
VANILLA_LIBS = {"interface\\fonts_console.swf", "interface\\fonts_en.swf", "interface\\fonts_fr.swf",
                "interface\\fonts_de.swf", "interface\\fonts_it.swf", "interface\\fonts_es.swf",
                "interface\\fonts_ru.swf", "interface\\fonts_pl.swf", "interface\\fonts_cz.swf",
                "interface\\fonts_ja.swf", "interface\\fonts_cn.swf", "interface\\fonts_zh.swf",
                "interface\\fonts_ptbr.swf", "interface\\fonts_ko.swf"}
_LIB = re.compile(r'^\s*fontlib\s+"([^"]+)"', re.I | re.M)
_MAP = re.compile(r'^\s*map\s+"([^"]+)"\s*=\s*"([^"]*)"', re.I | re.M)


@dataclass
class FontConfig:
    libs: list[str] = field(default_factory=list)       # normalized: interface\fonts_x.swf
    maps: dict[str, str] = field(default_factory=dict)  # $EverywhereFont -> Sovngarde


def norm(path: str) -> str:
    return path.replace("/", "\\").strip().lower()


def parse(text: str) -> FontConfig:
    fc = FontConfig()
    for m in _LIB.finditer(text):
        fc.libs.append(norm(m.group(1)))
    for m in _MAP.finditer(text):
        fc.maps[m.group(1)] = m.group(2)
    return fc


def read(path: Path) -> FontConfig:
    return parse(Path(path).read_bytes().decode("utf-8", "replace"))


def find_fontconfig(folder: Path) -> Path | None:
    """Interface/FontConfig.txt at the top of a mod's asset folders (any case,
    not under another asset folder such as meshes\\interface)."""
    folder = Path(folder)
    for p in folder.rglob("*"):
        if p.is_file() and p.name.lower() == NAME and p.parent.name.lower() == "interface":
            rel = [x.lower() for x in p.relative_to(folder).parts]
            if "fomod" in rel:
                continue
            i = rel.index("interface") if "interface" in rel else -1
            if i >= 0 and not any(x in ("meshes", "textures", "sound", "scripts") for x in rel[:i]):
                return p
    return None


def only_fontconfig(interface_dir: Path) -> bool:
    """True when a loose Interface folder holds nothing but FontConfig.txt
    (Mac/Windows junk aside)."""
    files = [p for p in Path(interface_dir).rglob("*") if p.is_file()
             and p.name.lower() not in (".ds_store", "thumbs.db", "desktop.ini")]
    return bool(files) and all(p.name.lower() == NAME and p.parent == Path(interface_dir) for p in files)


def label(fc: FontConfig) -> str:
    """The font a config puts on most of the interface (for messages)."""
    for key in ("$EverywhereFont", "$StartMenuFont", "$DialogueFont"):
        if fc.maps.get(key):
            return fc.maps[key]
    return next(iter(fc.maps.values()), "")
