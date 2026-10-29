"""What SkyNX Mods (the homebrew in extras/nxmods) and the app share on the SD.

SkyNX Mods turns plugins on and off on the console by editing
Skyrim_aoc.ccc. It keeps the full list, with '#' in front of the ones that are
off, in sdmc:/switch/SkyNXMods/skyrim.txt (the "side file"); its "on" lines
are exactly the .ccc's while nobody else touched the card.

Some mods also have BSAs listed in the inis (sResourceArchiveList...). Those
load whatever the .ccc says, so a plugin that's off would still bring its
textures and scripts. Here they are tied to their plugins:

* ``ini_owners``: which plugins each ini BSA belongs to (the mods the app
  added keep that in mods.json; otherwise a BSA named after the plugin);
* Pack leaves an ini BSA out when every plugin it belongs to is off;
* the app writes a manifest next to the side file (skyrim-ini.txt) with the
  full lists and the owners, so SkyNX Mods can do the same on the console.

Manifest lines, tab separated ('#' lines are comments):
  ini  <ini file name>  <key>  <full list as the project has it>
  own  <bsa>  <plugin>  [<plugin> ...]
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from . import ccc as C
from . import knowledge as K
from .ini import ARCHIVE_KEYS, parse_ini, set_archive_list
from .pack import Pack

SIDE_DIR = ("switch", "SkyNXMods")
SIDE_NAME = "skyrim.txt"
MANIFEST_NAME = "skyrim-ini.txt"
INFO_NAME = "skyrim-info.txt"       # what each plugin is (name, description, its BSAs)
PC_NAME = "skyrim-pc.txt"           # the list as the PC copied it, to go back to


def side_path(sd_root: Path) -> Path:
    return Path(sd_root).joinpath(*SIDE_DIR, SIDE_NAME)


def manifest_path(sd_root: Path) -> Path:
    return Path(sd_root).joinpath(*SIDE_DIR, MANIFEST_NAME)


def info_path(sd_root: Path) -> Path:
    return Path(sd_root).joinpath(*SIDE_DIR, INFO_NAME)


def pc_path(sd_root: Path) -> Path:
    return Path(sd_root).joinpath(*SIDE_DIR, PC_NAME)


# ------------------------------------------------------------------ what each mod is
DESC_FILE = "descriptions.json"


def descriptions_path(pack: Pack) -> Path:
    return Path(pack.root) / ".skynx" / DESC_FILE


def load_descriptions(pack: Pack) -> dict:
    import json
    f = descriptions_path(pack)
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except (OSError, ValueError):
        return {}


def set_description(pack: Pack, row_id: str, text: str, tx) -> None:
    """The person's own words about a mod (row id of the Mods page)."""
    import json
    d = load_descriptions(pack)
    text = " ".join((text or "").split())
    if text:
        d[row_id] = text
    else:
        d.pop(row_id, None)
    tx.write_bytes(descriptions_path(pack), json.dumps(d, indent=1, ensure_ascii=False).encode("utf-8"))


_NEXUS_TAIL = [
    re.compile(r"-\d+(-[\w.]+)*-\d{9,11}$"),                         # Nexus download: Name-123-1-0-1690000000
    re.compile(r"\s+\d+\s+[\d.]+\s+\d{4}-\d\d-\d\dT[\d-]+Z\s+\w+$"),  # Switch site: Name 313 2.0.2 2026-..Z abc
    re.compile(r"-\d{3,6}(-\d+)+$"),                                         # Nexus id + version: Name-4881-1-05
    re.compile(r"\s+v?\s*\d+(\.\d+)+$", re.I),                           # trailing version
]


def clean_mod_name(name: str) -> str:
    """'Madmen A Forsworn Overhaul NX 313 2.0.2 2026-06-14T12-34Z eXDeLpzqt' ->
    'Madmen A Forsworn Overhaul NX'; plugin file names lose the extension."""
    n = re.sub(r"\.(esp|esm|esl|bsa|zip|7z|rar)$", "", name.strip(), flags=re.I)
    for rx in _NEXUS_TAIL:
        n2 = rx.sub("", n).strip(" -_")
        if n2:
            n = n2
    return n


def _flat(text: str, limit: int = 400) -> str:
    t = " ".join(str(text or "").replace("\t", " ").split())
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


def cc_files(vanilla_dir, plugin: str) -> list[str]:
    """The game's BSAs of a Creation Club plugin (Name.bsa, Name - Textures.bsa)
    in the folder with the console's game files."""
    try:
        names = [p.name for p in Path(vanilla_dir).iterdir() if p.suffix.lower() == ".bsa"]
    except (OSError, TypeError):
        return []
    stem = Path(plugin).stem.lower()
    return sorted(n for n in names if n[:-4].lower() == stem or n.lower().startswith(stem + " - "))


def plugin_info(pack: Pack, extra: dict | None = None, vanilla_dir=None) -> list[dict]:
    """One entry per plugin of the load list: {"plugin", "title", "kind"
    ("cc"/"mod"), "desc_en", "desc_es", "files": [its BSAs]}. `extra`:
    row id -> {"title", "desc"} known by the app (Nexus name and summary)."""
    from . import ccinfo
    from .builder import mods_view
    extra = extra or {}
    user = load_descriptions(pack)
    by_plugin: dict[str, dict] = {}
    for r in mods_view(pack):
        x = extra.get(r["id"]) or {}
        title = x.get("title") or clean_mod_name(r["name"])
        desc = user.get(r["id"]) or x.get("desc") or ""
        for pl in r.get("plugins") or []:
            h = pack.plugins.get(pl.lower())
            d = desc
            if not d and h and h.description and not re.match(r"^\s*(v(ersion)?\b|\d)", h.description, re.I):
                d = h.description
            by_plugin[pl.lower()] = {"plugin": pl, "title": _flat(title, 80), "kind": "mod",
                                     "desc_en": _flat(d), "desc_es": _flat(d), "files": list(r.get("bsas") or [])}
    out = []
    for e in pack.list_entries:
        name = _bare(e)
        low = name.lower()
        if low in by_plugin:
            out.append(by_plugin[low])
            continue
        cc = ccinfo.info(name)
        if cc:
            out.append({"plugin": name, "title": cc["title"], "kind": "cc",
                        "desc_en": cc["desc"][0], "desc_es": cc["desc"][1],
                        "files": cc_files(vanilla_dir, name) if vanilla_dir else []})
    return out


WEIGHTS_FILE = "weights.json"
WEIGHT_KEYS = ("rec", "tex", "mesh", "audio", "other")


def _kind_of(folder: str) -> str:
    top = folder.replace("/", "\\").split("\\", 1)[0].lower()
    if top == "textures":
        return "tex"
    if top == "meshes":
        return "mesh"
    if top in ("sound", "music"):
        return "audio"
    return "other"


def bsa_parts(path: Path) -> dict[str, int]:
    """Bytes of a BSA by kind (textures, meshes, audio, other), counted as
    the game holds them: compressed files by their original size."""
    import struct
    from .bsa import read_bsa
    out = {k: 0 for k in WEIGHT_KEYS[1:]}
    arc = read_bsa(path)
    packed = [e for e in arc.entries if e.compressed]
    # Original sizes sit at each compressed file's start. Reading them all
    # means a seek per file (slow on archives with many thousands), so a
    # sample of up to SAMPLE files per kind gives the ratio for the rest.
    SAMPLE = 300
    ratio: dict[str, float] = {}
    by_kind: dict[str, list] = {}
    for e in packed:
        by_kind.setdefault(_kind_of(e.folder), []).append(e)
    with Path(path).open("rb") as f:
        for kind, items in by_kind.items():
            step = max(1, len(items) // SAMPLE)
            stored = orig = 0
            for e in items[::step]:
                try:
                    f.seek(e.offset)
                    if arc.embed_names:
                        f.read(f.read(1)[0])
                    orig += struct.unpack("<I", f.read(4))[0]
                    stored += e.size
                except Exception:  # noqa: BLE001
                    continue
            ratio[kind] = orig / stored if stored else 1.0
    for e in arc.entries:
        kind = _kind_of(e.folder)
        out[kind] += int(e.size * ratio[kind]) if e.compressed else e.size
    return out


def _weights_cache(pack: Pack) -> Path:
    return Path(pack.root) / ".skynx" / WEIGHTS_FILE


def bsa_weights(pack: Pack, names: list[str], progress=None, more: dict | None = None) -> dict[str, dict[str, int]]:
    """{bsa lower: bytes by kind} for the pack's BSAs among `names` (and the
    game's, in `more`: lower name -> path). Kept in .skynx/weights.json by size
    and date, so copying again is quick."""
    import json
    cache_path = _weights_cache(pack)
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        cache = {}
    out, changed = {}, False
    for i, name in enumerate(names):
        low = name.lower()
        path = pack.bsas.get(low) or (more or {}).get(low)
        if path is None or not path.exists():
            continue
        st = path.stat()
        stamp = [st.st_size, int(st.st_mtime)]
        hit = cache.get(low)
        if hit and hit.get("stamp") == stamp:
            out[low] = hit["parts"]
            continue
        if progress:
            progress(f"Measuring {path.name}", i, len(names))
        try:
            parts = bsa_parts(path)
        except Exception:  # noqa: BLE001
            continue
        cache[low] = {"stamp": stamp, "parts": parts}
        out[low] = parts
        changed = True
    if changed:
        try:
            _write(cache_path, json.dumps(cache, indent=0))
        except OSError:
            pass
    return out


def plugin_weight(pack: Pack, plugin: str, files: list[str], parts: dict[str, dict[str, int]],
                  vanilla_dir=None) -> dict[str, int]:
    """Bytes behind a plugin: its records (the plugin file, which the game
    keeps in memory while it's on) and its BSAs by kind (textures and meshes
    only take memory while their things are on screen; audio streams)."""
    w = {k: 0 for k in WEIGHT_KEYS}
    path = pack.data_files.get(plugin.lower())
    if (path is None or not path.exists()) and vanilla_dir:
        path = Path(vanilla_dir) / plugin          # a Creation Club plugin: in the game's files
    if path is not None and path.exists():
        w["rec"] = path.stat().st_size
    for b in files:
        for k, v in (parts.get(b.lower()) or {}).items():
            w[k] = w.get(k, 0) + v
    return w


def info_text(pack: Pack, extra: dict | None = None, progress=None, vanilla_dir=None) -> str:
    lines = ["# SkyNX Studio: what each plugin is, for SkyNX Mods.",
             "# p <plugin> <title> <kind> <description en> <description es> <its BSAs, | between>"
             " <KB: records:textures:meshes:audio:other>"]
    rows = plugin_info(pack, extra, vanilla_dir)
    more = {b.lower(): Path(vanilla_dir) / b for i in rows if i["kind"] == "cc" for b in i["files"]} \
        if vanilla_dir else {}
    parts = bsa_weights(pack, sorted({b for i in rows for b in i["files"]}), progress, more)
    for i in rows:
        w = plugin_weight(pack, i["plugin"], i["files"], parts, vanilla_dir if i["kind"] == "cc" else None)
        kb = ":".join(str((w[k] + 1023) // 1024) for k in WEIGHT_KEYS)
        lines.append("\t".join(["p", i["plugin"], i["title"], i["kind"], i["desc_en"], i["desc_es"],
                                "|".join(i["files"]), kb]))
    return "\n".join(lines) + "\n"


def _bare(e: str) -> str:
    return e.lstrip("#").strip()


def ini_owners(pack: Pack) -> dict[str, tuple[str, list[str]]]:
    """{bsa lower: (bsa name, [plugins it belongs to])} for the BSAs the inis
    list that belong to some plugin of the load list. The game's own BSAs
    and plugin-less ones (a main menu, fonts) aren't here."""
    from .builder import load_mods
    listed = {_bare(e).lower(): _bare(e) for e in pack.list_entries}
    in_inis: dict[str, str] = {}
    for ini in pack.inis:
        for key in ARCHIVE_KEYS:
            for b in ini.archive_list(key):
                in_inis.setdefault(b.lower(), b)
    out: dict[str, tuple[str, list[str]]] = {}
    for rec in load_mods(pack).values():
        plugins = [p for p in rec.get("plugins", []) if p.lower() in listed]
        if not plugins:
            continue
        for b in rec.get("bsas", []):
            low = b.lower()
            if low in in_inis:
                name, have = out.get(low, (in_inis[low], []))
                out[low] = (name, have + [p for p in plugins if p not in have])
    for low, name in listed.items():
        if low in {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS}:
            continue
        for b in pack.bsas_for_plugin(name):
            bl = b.name.lower()
            if bl in in_inis and bl not in out:
                out[bl] = (in_inis[bl], [name])
    return {k: v for k, v in out.items() if not k.startswith("skyrim - ")}


def ini_drops(pack: Pack) -> set[str]:
    """Lowercase ini BSAs whose plugins are all switched off with '#'."""
    off = {_bare(e).lower() for e in pack.list_entries if e.startswith("#")}
    if not off:
        return set()
    return {b for b, (_n, owners) in ini_owners(pack).items()
            if owners and all(o.lower() in off for o in owners)}


def filter_ini(raw: bytes, drops: set[str]) -> bytes:
    """The ini without the BSAs in `drops` in its archive lists."""
    if not drops:
        return raw
    ini = parse_ini(raw)
    for key in ARCHIVE_KEYS:
        if ini.get("Archive", key) is None:
            continue
        items = ini.archive_list(key)
        kept = [i for i in items if i.lower() not in drops]
        if kept != items:
            raw = set_archive_list(raw, key, kept)
    return raw


def manifest_text(pack: Pack) -> str:
    owners = ini_owners(pack)
    lines = ["# SkyNX Studio: BSAs in the inis that belong to plugins, for SkyNX Mods.",
             "# ini <file> <key> <full list> / own <bsa> <plugins>"]
    used: set[str] = set()
    for ini in pack.inis:
        for key in ARCHIVE_KEYS:
            if ini.get("Archive", key) is None:
                continue
            items = ini.archive_list(key)
            mine = [i for i in items if i.lower() in owners]
            if mine:
                lines.append("\t".join(["ini", ini.path.name, key, ", ".join(items)]))
                used.update(i.lower() for i in mine)
    for low in sorted(used):
        name, plugins = owners[low]
        lines.append("\t".join(["own", name, *plugins]))
    return "\n".join(lines) + "\n"


def side_text(pack: Pack) -> str:
    return "".join(e.strip() + "\n" for e in pack.list_entries if e.strip())


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    os.replace(tmp, path)


def write_sd_files(pack: Pack, sd_root: Path, extra: dict | None = None, progress=None,
                   vanilla_dir=None) -> list[str]:
    """After a copy to the SD: the full list (with what's off), the ini
    manifest, what each plugin is, and the list as the PC copied it (to go
    back to), so SkyNX Mods starts from what the project has. AE packs only."""
    if pack.mode != "AE" or not pack.list_entries:
        return []
    side = side_text(pack)
    _write(side_path(sd_root), side)
    _write(pc_path(sd_root), side)
    _write(manifest_path(sd_root), manifest_text(pack))
    _write(info_path(sd_root), info_text(pack, extra, progress, vanilla_dir))
    return [str(x(sd_root)) for x in (side_path, pc_path, manifest_path, info_path)]


def read_console(sd_root: Path) -> list[tuple[str, bool]] | None:
    """The list as SkyNX Mods left it: [(plugin, on)], or None when it never
    ran or the card's .ccc changed since (a copy from the PC, by hand)."""
    from .deploy import sd_contents
    side = side_path(sd_root)
    ccc = sd_contents(sd_root) / K.TITLE_AOC / "romfs" / "Skyrim_aoc.ccc"
    if not side.is_file() or not ccc.is_file():
        return None
    try:
        entries = C.parse_ccc(side.read_bytes()).entries
        on_card = [e.lower() for e in C.parse_ccc(ccc.read_bytes()).entries if not e.startswith("#")]
    except OSError:
        return None
    out = [(_bare(e), not e.startswith("#")) for e in entries if _bare(e)]
    if [n.lower() for n, on in out if on] != on_card:
        return None
    return out


def console_changes(pack: Pack, sd_root: Path) -> dict | None:
    """Plugins switched on or off on the console that the project has the
    other way: {"off": [...], "on": [...]}, or None when there's nothing."""
    con = read_console(sd_root)
    if con is None or pack.mode != "AE":
        return None
    project = {_bare(e).lower(): not e.startswith("#") for e in pack.list_entries}
    off = [n for n, on in con if not on and project.get(n.lower()) is True]
    on = [n for n, on in con if on and project.get(n.lower()) is False]
    return {"off": off, "on": on} if off or on else None


def use_console(pack: Pack, sd_root: Path, tx) -> dict:
    """Put the console's on/off choices in the project's load list ('#')."""
    ch = console_changes(pack, sd_root) or {"off": [], "on": []}
    if not ch["off"] and not ch["on"]:
        return ch
    path = pack.list_path
    raw = path.read_bytes()
    want = {n.lower(): False for n in ch["off"]} | {n.lower(): True for n in ch["on"]}
    mapping = {}
    for e in C.parse_ccc(raw).entries:
        low = _bare(e).lower()
        if low in want:
            new = _bare(e) if want[low] else "#" + _bare(e)
            if new != e:
                mapping[e] = new
    if mapping:
        tx.write_bytes(path, C.edit_lines(raw, mapping))
    return ch
