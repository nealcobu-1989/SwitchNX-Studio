"""A modpack on disk, in the same layout it has on the SD card.

Accepts any of these as the root: the SD root, an `atmosphere` folder, a
`contents` folder, or a folder that directly holds the title-id folders.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from . import knowledge as K
from .ccc import CccFile, read_ccc
from .ini import IniFile, read_ini
from .plugin import PluginHeader, read_header

PLUGIN_EXT = {".esp", ".esm", ".esl"}
ARCHIVE_EXT = {".7z", ".zip", ".rar"}
# A project (project.py) keeps its working pack hidden in <root>/.skynx/work;
# the tools see that pack, the person sees Mods/, Base/ and Switch/.
PROJECT_FILE = "skynx-project.json"
PROJECT_WORK = (".skynx", "work")


def is_project(root: Path) -> bool:
    return (Path(root) / PROJECT_FILE).is_file()


def _find_dir(root: Path, name: str, max_depth: int = 5) -> Path | None:
    name = name.lower()
    root = Path(root)
    if root.name.lower() == name:
        return root
    for dirpath, dirnames, _ in os.walk(root):
        depth = Path(dirpath).relative_to(root).parts
        if len(depth) >= max_depth:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if not d.startswith(".skynx")]
        for d in dirnames:
            if d.lower() == name:
                return Path(dirpath) / d
    return None


def _child(parent: Path | None, name: str) -> Path | None:
    if parent is None or not parent.is_dir():
        return None
    for p in parent.iterdir():
        if p.name.lower() == name.lower():
            return p
    return None


@dataclass
class Pack:
    root: Path
    layout_root: Path | None = None     # where the title folders are (root, or a project's work folder)
    project: bool = False
    base_dir: Path | None = None        # .../01000A10041EA000
    aoc_dir: Path | None = None         # .../01000A10041EB009
    base_romfs: Path | None = None
    aoc_romfs: Path | None = None
    data_dir: Path | None = None
    ccc_path: Path | None = None
    plugins_path: Path | None = None    # SE "Plugins" file
    ini_paths: list[Path] = field(default_factory=list)       # active inis
    other_inis: list[Path] = field(default_factory=list)      # alternates
    mode: str = "?"                     # "AE", "SE" or "?"
    ccc: CccFile | None = None
    plugin_list: CccFile | None = None  # SE Plugins parsed with the same reader
    inis: list[IniFile] = field(default_factory=list)
    data_files: dict[str, Path] = field(default_factory=dict)  # lower name -> path
    plugins: dict[str, PluginHeader] = field(default_factory=dict)  # lower -> header
    bsas: dict[str, Path] = field(default_factory=dict)       # lower -> path
    archives: list[Path] = field(default_factory=list)        # .7z/.zip left in Data
    loose_dirs: list[str] = field(default_factory=list)

    # -- loading ------------------------------------------------------------
    @classmethod
    def open(cls, root: Path) -> "Pack":
        root = Path(root)
        p = cls(root=root)
        search = root
        if is_project(root):
            search = root.joinpath(*PROJECT_WORK)
            p.project = True
        p.layout_root = search
        p.base_dir = _find_dir(search, K.TITLE_BASE) if search.is_dir() else None
        p.aoc_dir = _find_dir(search, K.TITLE_AOC) if search.is_dir() else None
        p.base_romfs = _child(p.base_dir, "romfs")
        p.aoc_romfs = _child(p.aoc_dir, "romfs")
        p.data_dir = _child(p.base_romfs, "Data")
        p.ccc_path = _child(p.aoc_romfs, "Skyrim_aoc.ccc")
        p.plugins_path = _child(p.base_romfs, "Plugins")
        if p.base_romfs:
            for f in sorted(p.base_romfs.iterdir()):
                if f.is_file() and f.suffix.lower() == ".ini":
                    low = f.name.lower()
                    if low == "skyrim.ini" or (low.startswith("skyrim_") and low.count(".") == 1):
                        p.ini_paths.append(f)
                    else:
                        p.other_inis.append(f)
            # Skyrim.ini first, then language inis (they load after it)
            p.ini_paths.sort(key=lambda x: (x.name.lower() != "skyrim.ini", x.name.lower()))
        p.reload()
        return p

    def reload(self) -> None:
        self.ccc = read_ccc(self.ccc_path) if self.ccc_path and self.ccc_path.exists() else None
        self.plugin_list = (read_ccc(self.plugins_path)
                            if self.plugins_path and self.plugins_path.exists() else None)
        self.mode = "AE" if self.ccc else ("SE" if self.plugin_list else "?")
        self.inis = [read_ini(p) for p in self.ini_paths if p.exists()]
        self.data_files, self.plugins, self.bsas = {}, {}, {}
        self.archives, self.loose_dirs = [], []
        if self.data_dir and self.data_dir.is_dir():
            for f in self.data_dir.iterdir():
                if f.is_dir():
                    self.loose_dirs.append(f.name)
                    continue
                low = f.name.lower()
                self.data_files[low] = f
                ext = f.suffix.lower()
                if ext in PLUGIN_EXT:
                    self.plugins[low] = read_header(f)
                elif ext == ".bsa":
                    self.bsas[low] = f
                elif ext in ARCHIVE_EXT:
                    self.archives.append(f)

    # -- derived views ------------------------------------------------------
    @property
    def list_entries(self) -> list[str]:
        if self.mode == "AE" and self.ccc:
            return self.ccc.entries
        if self.mode == "SE" and self.plugin_list:
            return self.plugin_list.entries
        return []

    @property
    def list_bytes(self) -> int:
        """Bytes of the load list the console will read. In a project, Pack
        leaves out the lines switched off with '#'."""
        lst = self.ccc if self.mode == "AE" else self.plugin_list
        if not lst:
            return 0
        if getattr(self, "project", False):
            from .ccc import packed
            return len(packed(lst.raw))
        return lst.size

    @property
    def list_path(self) -> Path | None:
        return self.ccc_path if self.mode == "AE" else self.plugins_path

    def stest_plugins(self) -> list[str]:
        out = []
        for ini in self.inis:
            for e in ini.entries:
                if e.section.lower() == "general" and e.key.lower().startswith("stestfile"):
                    if e.value and e.value not in out:
                        out.append(e.value)
        return out

    def load_order(self) -> list[tuple[str, str]]:
        """(plugin, source) in the order the game sees them, best known model:
        vanilla masters, Hyrule, extra sTestFile plugins, then the list file."""
        seen: set[str] = set()
        out: list[tuple[str, str]] = []
        for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS:
            out.append((m, "juego")); seen.add(m.lower())
        listed = {e.lower() for e in self.list_entries}
        # sTestFile plugins that are not also in the list. Their real position
        # relative to the list is not confirmed; we model them before it.
        for t in self.stest_plugins():
            if t.lower() not in seen and t.lower() not in listed:
                out.append((t, "ini")); seen.add(t.lower())
        for e in self.list_entries:
            if e.lower() not in seen:
                out.append((e, "lista")); seen.add(e.lower())
        return out

    def archive_lists(self) -> dict[str, list[str]]:
        """Effective archive lists: later inis override earlier ones per key."""
        from .ini import ARCHIVE_KEYS
        out: dict[str, list[str]] = {}
        for ini in self.inis:
            for key in ARCHIVE_KEYS:
                if ini.get("Archive", key) is not None:
                    out[key] = ini.archive_list(key)
        return out

    def inis_for_key(self, key: str) -> list[Path]:
        """Every ini that sets this archive key. On Switch the language ini
        (Skyrim_en.ini, Skyrim_es.ini...) loads after Skyrim.ini and replaces
        the list, so an entry has to be in all of them to load in every language."""
        return [ini.path for ini in self.inis if ini.get("Archive", key) is not None]

    @property
    def lang_inis(self) -> list:
        return [ini for ini in self.inis if ini.path.name.lower() != "skyrim.ini"]

    def ini_for_key(self, key: str) -> Path | None:
        """The ini whose value for this archive key wins (last one that sets it)."""
        found = None
        for ini in self.inis:
            if ini.get("Archive", key) is not None:
                found = ini.path
        return found

    def is_cc(self, name: str) -> bool:
        low = name.lower()
        return low.startswith("cc") and low not in self.plugins

    def bsas_for_plugin(self, plugin: str) -> list[Path]:
        stem = Path(plugin).stem.lower()
        out = []
        for low, p in self.bsas.items():
            s = Path(low).stem
            if s == stem or s == stem + " - textures":
                out.append(p)
        return out

    def data_size(self) -> int:
        return sum(p.stat().st_size for p in self.data_files.values())
