"""Safe plugin renames inside a mod that is being converted.

A plugin's file name is written in many places. Renaming only the .esp is
what broke Auri's voice. Here every place we know of is updated together:

  the plugin file                     Mod.esp
  masters of other plugins            MAST subrecords
  voices                              sound\\voice\\Mod.esp\\...
  FaceGen meshes and tints            ...\\facegeom\\Mod.esp\\, ...\\facetint\\Mod.esp\\
  tint paths inside FaceGen meshes    BSShaderTextureSet strings (nif.py)
  scene sequences                     seq\\Mod.seq
  localized strings                   strings\\Mod_english.strings (and dl/il)
  scripts                             "Mod.esp" literals in .pex (pex.py)
  text configs (json, ini, ...)       exact file-name matches

The tree is a staging copy, never the user's files. Paths are lowercase
except plugin file names, as the converter writes them.
"""
from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path

from . import nif as NIF
from . import pex as PEX
from .plugin import rename_master_bytes

PLUGIN_EXT = (".esp", ".esm", ".esl")
NAME_FOLDERS = ("sound\\voice",
                "meshes\\actors\\character\\facegendata\\facegeom",
                "textures\\actors\\character\\facegendata\\facetint")
TEXT_EXT = {".json", ".ini", ".txt", ".toml", ".yaml", ".yml", ".xml", ".jslot", ".cfg"}
STRINGS_EXT = (".strings", ".dlstrings", ".ilstrings")
MAX_NAME = 60


class RenameError(ValueError):
    pass


# ----------------------------------------------------------------- names
def safe_name(name: str) -> str:
    """Same name without the characters that break on the way to the console:
    apostrophes and quotes (Google Drive turns them into '_'), accents,
    symbols, double dots, leading/trailing spaces."""
    stem, ext = name[:-4], name[-4:].lower()
    if ext not in PLUGIN_EXT:
        stem, ext = name, ""
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    stem = re.sub(r"['\"`´‘’“”]", "", stem)
    stem = re.sub(r"[^A-Za-z0-9 _\-+()\[\]&.,]", "_", stem)
    stem = re.sub(r"\.{2,}", ".", stem).strip(" ._")
    stem = re.sub(r"\s{2,}", " ", stem)
    return (stem or "Mod") + ext


def compact_name(name: str, max_len: int = 24) -> str:
    """Short version for the .ccc byte budget: words glued in CamelCase."""
    s = safe_name(name)
    stem, ext = (s[:-4], s[-4:]) if s[-4:].lower() in PLUGIN_EXT else (s, "")
    words = re.split(r"[^A-Za-z0-9]+", stem)
    glued = "".join(w[:1].upper() + w[1:] for w in words if w)
    return (glued[:max_len] or "Mod") + ext


def unique(name: str, taken: set[str]) -> str:
    stem, ext = (name[:-4], name[-4:]) if name[-4:].lower() in PLUGIN_EXT else (name, "")
    cand, n = name, 2
    while cand.lower() in taken:
        cand, n = f"{stem}{n}{ext}", n + 1
    return cand


def check_name(name: str) -> str | None:
    """Reason a new plugin name is not acceptable, or None."""
    if not name or name[-4:].lower() not in PLUGIN_EXT:
        return "ext"
    if safe_name(name) != name:
        return "chars"
    if len(name) > MAX_NAME:
        return "long"
    stem = name[:-4].split(".")[0].upper()
    if stem in {"CON", "PRN", "AUX", "NUL"} or re.fullmatch(r"(COM|LPT)[1-9]", stem):
        return "reserved"
    return None


# ----------------------------------------------------------------- tree helpers
def _child_ci(parent: Path, name: str) -> Path | None:
    if not parent.is_dir():
        return None
    low = name.lower()
    for c in parent.iterdir():
        if c.name.lower() == low:
            return c
    return None


def _merge_move(src: Path, dest: Path) -> None:
    if src.name.lower() == dest.name.lower() and src.parent == dest.parent:
        return  # same folder (only the case differs); BSA paths are lowercase anyway
    if not dest.exists():
        src.rename(dest)
        return
    for item in list(src.iterdir()):
        target = dest / item.name
        if item.is_dir():
            _merge_move(item, target)
        else:
            if target.exists():
                target.unlink()
            item.rename(target)
    src.rmdir()


def _fg_dir(tree: Path) -> Path | None:
    d = tree
    for part in NAME_FOLDERS[1].split("\\"):
        d = _child_ci(d, part) if d else None
    return d


def blockers(tree: Path, old: str) -> list[str]:
    """Files that mention `old` but can't be patched safely."""
    out = []
    fg = _fg_dir(tree)
    folder = _child_ci(fg, old) if fg else None
    if folder:
        for p in folder.rglob("*.nif"):
            try:
                NIF.parse(p.read_bytes())
            except Exception:  # noqa: BLE001
                out.append(str(p.relative_to(tree)))
    needle = old.lower().encode("cp1252", "replace")
    for p in tree.rglob("*.pex"):
        raw = p.read_bytes()
        if needle not in raw.lower():
            continue
        try:
            PEX.strings(raw)
        except Exception:  # noqa: BLE001
            out.append(str(p.relative_to(tree)))
    return out


# A plugin name inside a text config: only where a value starts (quotes, =,
# commas, separators, line start) and ends; "Patch.esp" must not match inside
# "Other Mod - Patch.esp".
_START = r"(?:(?<=^)|(?<=[\"'=,|~:;\\/\t>\[\(])|(?<=[=,:;] )|(?<=[=,:;]  ))"
_END = r"(?=$|[\"',|~:;\\/\t<\]\)\r\n]|\s*$|\s+[#;/])"


def _text_pattern(names) -> re.Pattern:
    alts = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    return re.compile(_START + "(" + alts + ")" + _END, re.I | re.M)


def _replace_text(raw: bytes, mapping: dict[str, str]) -> bytes | None:
    low = {o.lower(): n for o, n in mapping.items()}
    pat = _text_pattern(mapping)
    for enc, bom in (("utf-8-sig", b"\xef\xbb\xbf"), ("utf-16", b"\xff\xfe"),
                     ("utf-8", b""), ("cp1252", b"")):
        if bom and not raw.startswith(bom):
            continue
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if not pat.search(text):
            return None
        new_text = pat.sub(lambda m: low[m.group(1).lower()], text)
        try:
            if enc == "utf-16":
                return new_text.encode("utf-16")
            out_enc = "utf-8" if enc.startswith("utf-8") else enc
            return (bom if enc == "utf-8-sig" else b"") + new_text.encode(out_enc)
        except UnicodeEncodeError:
            return None
    return None


def _two_phase(pairs: list[tuple[Path, Path]]) -> None:
    """Rename many files/folders at once, so chains (A->B, B->C) and case-only
    changes work: everything goes to a temporary name first."""
    temps = []
    for i, (src, dest) in enumerate(pairs):
        tmp = src.with_name(f"{src.name}.skynx-ren{i}")
        src.rename(tmp)
        temps.append((tmp, dest))
    for tmp, dest in temps:
        if tmp.is_dir():
            _merge_move(tmp, dest)
        else:
            if dest.exists():
                raise RenameError(f"{dest.name} already exists")
            tmp.rename(dest)


def check_mapping(mapping: dict[str, str], tree: Path | None = None) -> None:
    """Two plugin FILES may not end up with the same name. Several old names
    (a plugin and the folder name its voices still use) may point to one."""
    olds = [o for o in mapping if tree is None or (_child_ci(tree, o) or Path("/nonexistent")).is_file()]
    news = [mapping[o].lower() for o in olds]
    if len(set(news)) != len(news):
        raise RenameError("two plugins would get the same name")


def apply(tree: Path, mapping: dict[str, str], log: list | None = None) -> dict:
    """Rename plugins old -> new everywhere inside `tree` (a staging Data folder),
    all at once (A->B and B->C in the same mapping are fine).
    Returns counters per kind."""
    log = log if log is not None else []
    counts = {"plugins": 0, "masters": 0, "folders": 0, "seq": 0, "strings": 0,
              "nif": 0, "pex": 0, "text": 0}
    mapping = {o: n for o, n in mapping.items() if o != n}
    if not mapping:
        return counts
    check_mapping(mapping, tree)
    low = {o.lower(): n for o, n in mapping.items()}
    # 1. plugin files themselves
    pairs = []
    for old, new in mapping.items():
        p = _child_ci(tree, old)
        if p and p.is_file():
            pairs.append((p, tree / new))
            log.append(f"{old} -> {new}")
    _two_phase(pairs)
    counts["plugins"] = len(pairs)
    # 2. masters of every plugin in the tree (one pass per plugin)
    for p in tree.iterdir():
        if p.is_file() and p.suffix.lower() in PLUGIN_EXT:
            raw = p.read_bytes()
            out, n = rename_masters(raw, low)
            if n:
                p.write_bytes(out)
                counts["masters"] += n
    # 3. folders named after the plugin
    for base in NAME_FOLDERS:
        parent = tree
        for part in base.split("\\"):
            parent = _child_ci(parent, part) if parent else None
        if not parent:
            continue
        pairs = []
        for d in list(parent.iterdir()):
            if d.is_dir() and d.name.lower() in low:
                new = low[d.name.lower()].lower()
                if d.name.lower() != new:
                    pairs.append((d, parent / new))
        _two_phase(pairs)
        counts["folders"] += len(pairs)
    # 4. seq and strings files: exactly <plugin>.seq and <plugin>_<language>.<ext>
    stems = {Path(o).stem.lower(): Path(n).stem.lower() for o, n in low.items()}
    seq = _child_ci(tree, "seq")
    if seq:
        pairs = [(f, seq / (stems[f.stem.lower()] + ".seq")) for f in seq.iterdir()
                 if f.is_file() and f.suffix.lower() == ".seq" and f.stem.lower() in stems]
        _two_phase(pairs)
        counts["seq"] = len(pairs)
    strings = _child_ci(tree, "strings")
    if strings:
        rx = re.compile(r"^(.*)_([a-z]+)(\.(?:strings|dlstrings|ilstrings))$", re.I)
        pairs = []
        for f in strings.iterdir():
            m = rx.match(f.name)
            if f.is_file() and m and m.group(1).lower() in stems:
                pairs.append((f, strings / f"{stems[m.group(1).lower()]}_{m.group(2).lower()}{m.group(3).lower()}"))
        _two_phase(pairs)
        counts["strings"] = len(pairs)
    # 5. tint paths inside FaceGen meshes of the renamed plugins
    fg = _fg_dir(tree)
    if fg:
        for new in low.values():
            d = _child_ci(fg, new)
            if not d:
                continue
            for p in d.rglob("*.nif"):
                raw = p.read_bytes()
                new_raw, n = NIF.replace_texture_folders(raw, low)
                if n:
                    p.write_bytes(new_raw)
                    counts["nif"] += n
    # 6. scripts and text configs
    needles = [o.lower().encode("cp1252", "replace") for o in low]
    for p in tree.rglob("*"):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext == ".pex":
            raw = p.read_bytes()
            lraw = raw.lower()
            if not any(nd in lraw for nd in needles):
                continue
            try:
                new_raw, n = PEX.rename_plugins(raw, low)
            except Exception as e:  # noqa: BLE001
                raise RenameError(f"{p.relative_to(tree)}: {e}") from e
            if n:
                p.write_bytes(new_raw)
                counts["pex"] += n
        elif ext in TEXT_EXT:
            raw = p.read_bytes()
            out = _replace_text(raw, mapping)
            if out is not None and out != raw:
                p.write_bytes(out)
                counts["text"] += 1
    return counts


def rename_masters(raw: bytes, low: dict[str, str]) -> tuple[bytes, int]:
    """Rename every master found in `low` (lowercase old -> new) in one pass."""
    from .plugin import read_masters
    n = 0
    for m in read_masters(raw):
        if m.lower() in low:
            n += 1
    if not n:
        return raw, 0
    # rename_master_bytes matches case-insensitively; go through temporary
    # placeholders so chained names can't collide.
    out = raw
    placeholders = {}
    for i, m in enumerate(read_masters(raw)):
        if m.lower() in low:
            ph = f"\x01skynx{i}\x01"
            out = rename_master_bytes(out, m, ph) or out
            placeholders[ph] = low[m.lower()]
    for ph, new in placeholders.items():
        out = rename_master_bytes(out, ph, new) or out
    return out, n
