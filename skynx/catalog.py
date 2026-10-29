"""The Catalog: every mod of every modpack in the Library, as one list.

    build_catalog(library_root)               -> catalog (dict, JSON-ready)
    plan_build(catalog, picks, base)          -> plan (nothing written)
    execute_build(catalog, picks, base, dest) -> report (a new modpack)

The Library keeps modpacks (and loose Switch mods). The Catalog lists their
mod units (transfer.list_pack_mods) and folds the copies of the same mod that
live in different packs into one entry with several "versions":

- same main plugin once Drive's damage is folded (audit.norm_name), including
  the original name of a plugin the converter renamed;
- same plugin bytes (sha1), for plugins with real records (header-only dummy
  plugins all look alike, so they never link by content);
- units without a plugin (BSA-only) by their BSA names.

Each entry gets a category from cheap evidence (names, masters, the record
types the plugin adds or changes, what its BSAs contain, the LOOT group when
a masterlist is given), with a short reason in English and Spanish.

The user picks versions from any pack; plan_build checks the combined budget
(load list bytes, ini archive lists, BSAs, texture memory), where every master
comes from, what clashes, and what can't be satisfied. execute_build creates
the pack with builder.create_project and brings the picks pack by pack with
transfer.plan_transfer / apply_transfer (one history entry per source pack).
Source packs are only read.

Per pack facts are cached as JSON in cache_dir (default <library>/.catalog),
keyed by a cheap signature (Data listing with sizes and times, load list,
inis, .skynx records), so a second build is instant.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from collections import Counter
from pathlib import Path

from . import ccc as C
from . import knowledge as K
from .audit import norm_name
from .errors import SkynxError
from .ini import ARCHIVE_KEYS, ARCHIVE_LIST_LIMIT, parse_ini
from .pack import Pack

CATALOG_VERSION = 2
CACHE_DIR = ".catalog"
ARCHIVE_PEEK_LIMIT = 64 * 2**20      # read plugins inside archives (Ashiro's .7z) up to this size
HASH_MIN_BYTES = 512                 # smaller plugins are header-only dummies: no content link
MB = 2**20
# KokaNX measured (Oct 2026) about 500-700 MB of RAM left for mods on Switch.
RAM_FOR_MODS = (500 * MB, 700 * MB)
MEMORY_KEY = "sArchiveToLoadInMemoryList"
VANILLA = {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS}
CC_LOWER = {c.lower(): c for c in K.AE_CC_PLUGINS}
USSEP_LOW = K.USSEP_PLUGIN.lower()
USSEP_NORM = norm_name(K.USSEP_PLUGIN)
PLUGIN_EXT = (".esp", ".esm", ".esl")

CATEGORIES = [
    {"id": "followers", "en": "Followers", "es": "Seguidores"},
    {"id": "lands", "en": "New lands and dungeons", "es": "Tierras y mazmorras nuevas"},
    {"id": "items", "en": "Armor, weapons and clothes", "es": "Armaduras, armas y ropa"},
    {"id": "gameplay", "en": "Gameplay", "es": "Jugabilidad"},
    {"id": "visual", "en": "Visual", "es": "Visual"},
    {"id": "npcs", "en": "Characters (NPCs)", "es": "Personajes (NPC)"},
    {"id": "quests", "en": "Quests", "es": "Misiones"},
    {"id": "audio", "en": "Sound and music", "es": "Sonido y música"},
    {"id": "ui", "en": "Interface", "es": "Interfaz"},
    {"id": "patches", "en": "Patches", "es": "Parches"},
    {"id": "frameworks", "en": "Frameworks and resources", "es": "Frameworks y recursos"},
    {"id": "fixes", "en": "Fixes", "es": "Correcciones"},
    {"id": "other", "en": "Other", "es": "Otros"},
]
CATEGORY_IDS = [c["id"] for c in CATEGORIES]

FLAGS = {   # our own version flags (the rest come from transfer.FLAGS)
    "placeholder": ("Empty stand-in for {merge}, which has it merged in",
                    "Plugin vacío que reemplaza a uno que ya está dentro de {merge}"),
    "loose-mod": ("Loose mod in the Library", "Mod suelto en la Biblioteca"),
    "not-peeked": ("Still packed; its masters are checked when it's unpacked",
                   "Sigue comprimido; sus masters se revisan al descomprimirlo"),
}


class CatalogError(SkynxError):
    pass


def _tick(progress):
    return progress or (lambda *a, **k: None)


def _flag_texts(code: str, params: dict) -> dict:
    from . import transfer as T
    pair = FLAGS.get(code) or getattr(T, "FLAGS", {}).get(code) or (code, code)
    try:
        en, es = pair[0].format(**params), pair[1].format(**params)
    except (KeyError, IndexError, ValueError):
        en, es = pair
    return {"code": code, "en": en, "es": es}


def _and(names: list[str], es: bool = False) -> str:
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    shown, tail = names[:3], (f" (+{len(names) - 3})" if len(names) > 3 else "")
    return ", ".join(shown[:-1]) + (" y " if es else " and ") + shown[-1] + tail


def _plural(n: int, en: tuple[str, str], es: tuple[str, str]) -> tuple[str, str]:
    return (f"{n} {en[0] if n == 1 else en[1]}", f"{n} {es[0] if n == 1 else es[1]}")


# =================================================================== facts
def _sha1(path: Path) -> str | None:
    h = hashlib.sha1()
    try:
        with Path(path).open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


_CELL_CHILDREN = {6, 8, 9, 10}      # GRUP types holding placed objects (REFR, ACHR, NAVM, LAND...)


def _record_stats(path: Path, n_masters: int) -> dict | None:
    """New / override record counts by type, from record headers only. The
    placed objects inside cells are not walked one by one (that's most of the
    time on big plugins): their bytes are added up as "placed_bytes"."""
    import mmap
    import struct
    try:
        size = os.stat(path).st_size
    except OSError:
        return None
    if size < 24:
        return None
    new, ovr = Counter(), Counter()
    placed = 0
    try:
        with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            if mm[:4] != b"TES4":
                return None
            unpack = struct.unpack_from
            pos = 24 + unpack("<I", mm, 4)[0]
            end = len(mm)
            while pos + 24 <= end:
                typ = mm[pos:pos + 4]
                if typ == b"GRUP":
                    gsize, _label, gtype = unpack("<I4si", mm, pos + 4)
                    if gsize < 24:
                        break                                   # damaged
                    if gtype in _CELL_CHILDREN:
                        placed += gsize - 24
                        pos += gsize
                    else:
                        pos += 24
                    continue
                dsize, _flags, fid = unpack("<III", mm, pos + 4)
                (new if fid >> 24 >= n_masters else ovr)[typ.decode("latin-1")] += 1
                pos += 24 + dsize
    except (OSError, ValueError, struct.error):
        return None
    return {"new": new, "ovr": ovr, "placed_bytes": placed}


def _plugin_facts(path: Path, name: str, file_name: str) -> dict:
    """What the catalog needs from one plugin file: header, hash, record types."""
    from .loot import merged_components
    from .plugin import read_header
    out = {"name": name, "file": file_name, "hash": None, "size": 0, "records": 0, "masters": [],
           "esm": False, "light": False, "merge_of": [], "new": {}, "ovr": {}, "placed_bytes": 0,
           "error": None}
    try:
        h = read_header(path)
    except OSError as e:
        out["error"] = str(e)
        return out
    out.update(size=h.size, records=h.num_records, masters=list(h.masters), error=h.error or None,
               esm=h.is_master_flag or h.extension == ".esm",
               light=h.extension == ".esl" or h.is_light_flag,
               merge_of=merged_components(h))
    out["hash"] = _sha1(path)
    s = _record_stats(path, len(h.masters))
    if s:
        out["new"], out["ovr"], out["placed_bytes"] = dict(s["new"]), dict(s["ovr"]), s["placed_bytes"]
    return out


def _bsa_facts(path: Path) -> dict:
    """Directory-only facts: entry count and what kind of files it holds."""
    from .bsa import read_bsa
    out = {"entries": 0, "size": 0, "tops": {}, "dds": 0, "voice": 0, "hkx": 0, "error": None}
    try:
        out["size"] = path.stat().st_size
        arc = read_bsa(path)
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
        return out
    tops: Counter = Counter()
    for e in arc.entries:
        folder = e.folder.lower()
        tops[folder.split("\\", 1)[0]] += 1
        low = e.name.lower()
        if low.endswith(".dds"):
            out["dds"] += 1
        elif low.endswith(".hkx"):
            out["hkx"] += 1
        if folder.startswith("sound\\voice"):
            out["voice"] += 1
    out["entries"] = len(arc.entries)
    out["tops"] = dict(tops)
    return out


_KOKA_LIST2 = re.compile(r"[A-Za-z0-9](Ts|Vs|T|V)$")      # OdnTs, USSEPT, USSEPV (case sensitive)


def _list_keys(bsa_name: str, facts: dict | None) -> list[str]:
    """Ini list for a BSA nothing names after a plugin (same rule as
    builder._archive_key_for: textures and voices to list 2)."""
    if facts and facts.get("entries"):
        n = max(1, facts["entries"])
        if (facts.get("dds", 0) + facts.get("voice", 0)) / n > 0.5:
            return ["sResourceArchiveList2"]
        return ["sResourceArchiveList"]
    stem = Path(bsa_name).stem
    low = stem.lower()
    if "texture" in low or "voice" in low or _KOKA_LIST2.search(stem):
        return ["sResourceArchiveList2"]
    return ["sResourceArchiveList"]


def _peek_archive(archive: Path, wanted: dict[str, str], tick) -> dict[str, dict]:
    """Plugin facts for some members of a .7z/.zip, extracted to a temp folder.
    wanted: member name -> file name."""
    from .intake import extracted_path, safe_extract
    out: dict[str, dict] = {}
    if not wanted:
        return out
    tmp = Path(tempfile.mkdtemp(prefix="skynx-catalog-"))
    try:
        tick(archive.name)
        safe_extract(archive, tmp, targets=list(wanted))
        for member, fname in wanted.items():
            p = extracted_path(tmp, member)
            if p.is_file():
                out[fname] = _plugin_facts(p, fname, fname)
    except Exception:  # noqa: BLE001
        return {}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def _unit_record(u, pack: Pack, tick) -> dict:
    """A transfer.ModUnit as JSON-ready facts."""
    target = dict(getattr(u, "target", {}) or {})
    kind = u.kind
    plugins = list(u.plugins)
    rec = {"id": u.id, "kind": kind, "name": u.name,
           "plugins": [target.get(p, p) for p in plugins], "files": plugins,
           "bsas": [target.get(b, b) for b in u.bsas], "bsa_files": list(u.bsas),
           "masters": list(u.masters) if u.masters is not None else None,
           "size": u.size, "tex_bytes": u.tex_bytes, "light": bool(u.light),
           "position": u.position, "twin_of": u.twin_of,
           "renamed": sorted(set((getattr(u, "renamed", {}) or {}).values())),
           "flags": [{"code": f["code"], "params": f.get("params", {})} for f in u.flags],
           "plugin_facts": [], "bsa_facts": {}, "ini": {}, "peeked": kind != "archive"}
    # plugins
    if kind == "archive":
        arc = getattr(u, "archive", None)
        if arc is not None and plugins and arc.stat().st_size <= ARCHIVE_PEEK_LIMIT:
            from .intake import list_names
            try:
                members = {m.name: Path(m.name).name for m in list_names(arc)
                           if not m.is_dir and Path(m.name).name in plugins}
            except Exception:  # noqa: BLE001
                members = {}
            got = _peek_archive(arc, members, tick)
            rec["plugin_facts"] = [got[p] for p in plugins if p in got]
            rec["peeked"] = len(got) == len(plugins)
            if rec["peeked"]:
                ms: list[str] = []
                for pf in rec["plugin_facts"]:
                    ms += [m for m in pf["masters"] if m not in ms]
                    rec["light"] = rec["light"] or pf["light"]
                rec["masters"] = ms
        elif not plugins:
            rec["peeked"] = True
    else:
        for p in plugins:
            path = u.files.get(p) if getattr(u, "files", None) else None
            path = path or (pack.data_dir / p)
            rec["plugin_facts"].append(_plugin_facts(path, target.get(p, p), p))
        for b in u.bsas:
            path = (u.files.get(b) if getattr(u, "files", None) else None) or (pack.data_dir / b)
            rec["bsa_facts"][target.get(b, b)] = _bsa_facts(path)
    # where the BSAs go in the destination inis (like transfer._plan_inis)
    ini: dict[str, list[str]] = {}
    listed: set[str] = set()
    for key, names in (u.ini or {}).items():
        for n in names:
            if n in u.bsas and key != MEMORY_KEY:
                lst = ini.setdefault(key, [])
                t = target.get(n, n)
                if t not in lst:
                    lst.append(t)
                listed.add(n)
    stems = {Path(p).stem.lower() for p in plugins}
    for n in u.bsas:
        if n in listed:
            continue
        s = Path(n).stem.lower()
        if kind == "plugin":
            continue
        if kind == "archive" and (s in stems or (s.endswith(" - textures") and s[:-11] in stems)):
            continue
        for key in _list_keys(n, rec["bsa_facts"].get(target.get(n, n))):
            ini.setdefault(key, []).append(target.get(n, n))
    rec["ini"] = ini
    return rec


# =================================================================== sources
def _stat_line(p: Path) -> str:
    try:
        st = p.stat()
        return f"{p.name}|{st.st_size}|{st.st_mtime_ns}"
    except OSError:
        return f"{p.name}|-"


def _pack_sig(pk: Pack) -> str:
    h = hashlib.sha1(f"v{CATALOG_VERSION}".encode())
    lines = []
    if pk.data_dir and pk.data_dir.is_dir():
        with os.scandir(pk.data_dir) as it:
            for e in it:
                try:
                    st = e.stat()
                    lines.append(f"D{e.name}|{e.is_dir()}|{st.st_size}|{st.st_mtime_ns}")
                except OSError:
                    lines.append(f"D{e.name}|-")
    for p in [pk.list_path] + list(pk.ini_paths):
        if p:
            lines.append("F" + _stat_line(p))
    meta = Path(pk.root) / ".skynx"
    if meta.is_dir():
        for p in sorted(meta.glob("*.json")):
            lines.append("M" + _stat_line(p))
    for line in sorted(lines):
        h.update(line.encode("utf-8", "replace") + b"\n")
    return h.hexdigest()


def _mod_sig(path: Path) -> str:
    h = hashlib.sha1(f"v{CATALOG_VERSION}".encode())
    if path.is_dir():
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = sorted(d for d in dirnames if d != ".skynx")
            for f in sorted(filenames):
                p = Path(dirpath) / f
                h.update(("F" + str(p.relative_to(path)) + _stat_line(p)).encode("utf-8", "replace"))
    else:
        h.update(_stat_line(path).encode("utf-8", "replace"))
    return h.hexdigest()


def _cache_file(cache_dir: Path, path: Path) -> Path:
    key = os.path.normcase(os.path.abspath(str(path)))
    return cache_dir / (hashlib.sha1(key.encode("utf-8", "replace")).hexdigest()[:20] + ".json")


def _load_cache(f: Path, sig: str) -> dict | None:
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(d, dict) and d.get("version") == CATALOG_VERSION and d.get("sig") == sig:
        return d
    return None


def _save_cache(f: Path, data: dict) -> None:
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(f.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, f)
    except OSError:
        pass       # a cache that can't be written only costs time


def _pack_source(path: Path, name: str, cache_dir: Path | None, tick) -> dict:
    from .transfer import list_pack_mods
    src = {"kind": "pack", "name": name, "path": str(path), "mode": "?", "units": [],
           "cached": False, "error": None, "data_dir": None}
    try:
        pk = Pack.open(path)
    except Exception as e:  # noqa: BLE001
        src["error"] = [f"Can't open it: {e}", f"No se puede abrir: {e}"]
        return src
    src["mode"], src["data_dir"] = pk.mode, str(pk.data_dir) if pk.data_dir else None
    if not pk.data_dir:
        src["error"] = ["It has no Data folder", "No tiene carpeta Data"]
        return src
    sig = _pack_sig(pk)
    cf = _cache_file(cache_dir, path) if cache_dir else None
    if cf:
        hit = _load_cache(cf, sig)
        if hit:
            hit["source"].update(name=name, path=str(path), cached=True)
            return hit["source"]
    try:
        units = list_pack_mods(pk, progress=lambda *a, **k: tick(name))
    except Exception as e:  # noqa: BLE001
        src["error"] = [getattr(e, "en", str(e)), getattr(e, "es", str(e))]
        return src
    dependents = Counter(m.lower() for h in pk.plugins.values() for m in h.masters)
    for u in units:
        r = _unit_record(u, pk, tick)
        for pf in r["plugin_facts"]:
            pf["dependents"] = dependents.get(pf["file"].lower(), 0) + (
                dependents.get(pf["name"].lower(), 0) if pf["name"].lower() != pf["file"].lower() else 0)
        src["units"].append(r)
    if cf:
        _save_cache(cf, {"version": CATALOG_VERSION, "sig": sig, "source": src})
    return src


def _mod_source(path: Path, name: str, cache_dir: Path | None, tick) -> dict | None:
    """A loose mod from Library\\Mods, when it's a Switch mod that can be added as it is."""
    from .builder import scan_mod
    from .intake import detect, list_names
    src = {"kind": "mod", "name": name, "path": str(path), "mode": None, "units": [],
           "cached": False, "error": None, "data_dir": None}
    try:
        sig = _mod_sig(path)
    except OSError:
        return None
    cf = _cache_file(cache_dir, path) if cache_dir else None
    if cf:
        hit = _load_cache(cf, sig)
        if hit:
            if hit.get("source") is None:
                return None
            hit["source"].update(name=name, path=str(path), cached=True)
            return hit["source"]
    try:
        d = detect(path, deep=False)
    except Exception:  # noqa: BLE001
        d = None
    if d is None or d.kind != "switch-mod" or d.action != "add":
        if cf:
            _save_cache(cf, {"version": CATALOG_VERSION, "sig": sig, "source": None})
        return None
    ev = d.evidence
    u = {"id": f"mod:{name}", "kind": "mod", "name": Path(name).stem if path.is_file() else name,
         "plugins": list(ev.get("plugins", [])), "files": list(ev.get("plugins", [])),
         "bsas": list(ev.get("bsas", [])), "bsa_files": list(ev.get("bsas", [])),
         "masters": None, "size": 0, "tex_bytes": None, "light": False, "position": None,
         "twin_of": None, "renamed": [], "flags": [{"code": "loose-mod", "params": {}}],
         "plugin_facts": [], "bsa_facts": {}, "ini": {}, "peeked": False}
    if path.is_dir():
        found = scan_mod(path)
        u["plugin_facts"] = [_plugin_facts(p, p.name, p.name) for p in found["plugins"]]
        u["bsa_facts"] = {p.name: _bsa_facts(p) for p in found["bsas"]}
        u["size"] = sum(p.stat().st_size for p in found["plugins"] + found["bsas"])
        from .transfer import bsa_facts as tfacts
        texs = [tfacts(p).get("tex") for p in found["bsas"]]
        u["tex_bytes"] = sum(texs) if None not in texs else None
        u["peeked"] = True
    else:
        u["size"] = path.stat().st_size
        if path.stat().st_size <= ARCHIVE_PEEK_LIMIT:
            try:
                members = {m.name: Path(m.name).name for m in list_names(path)
                           if not m.is_dir and Path(m.name).suffix.lower() in PLUGIN_EXT}
            except Exception:  # noqa: BLE001
                members = {}
            got = _peek_archive(path, members, tick)
            u["plugin_facts"] = [got[p] for p in u["plugins"] if p in got]
            u["peeked"] = len(got) == len(u["plugins"])
    if u["peeked"]:
        ms: list[str] = []
        for pf in u["plugin_facts"]:
            ms += [m for m in pf["masters"] if m not in ms]
            u["light"] = u["light"] or pf["light"]
        u["masters"] = ms
    stems = {Path(p).stem.lower() for p in u["plugins"]}
    for b in u["bsas"]:
        s = Path(b).stem.lower()
        if s in stems or (s.endswith(" - textures") and s[:-11] in stems):
            continue
        for key in _list_keys(b, u["bsa_facts"].get(b)):
            u["ini"].setdefault(key, []).append(b)
    src["units"] = [u]
    if cf:
        _save_cache(cf, {"version": CATALOG_VERSION, "sig": sig, "source": src})
    return src


# =================================================================== categories
_STRUCT = {"CELL", "WRLD", "REFR", "ACHR", "PGRE", "PHZD", "NAVM", "NAVI", "LAND", "KYWD", "FLST",
           "GLOB", "COBJ", "LVLI", "TES4", "DOBJ", "FORM"}
_PLACED = {"REFR", "ACHR", "PGRE", "PHZD", "NAVM", "LAND"}
_BUCKETS = {
    "items": {"ARMO", "ARMA", "WEAP", "AMMO"},
    "gameplay": {"PERK", "SPEL", "MGEF", "RACE", "CLAS", "ENCH", "GMST", "AVIF", "LVLN", "EXPL",
                 "PROJ", "HAZD", "SHOU", "WOOP", "ALCH", "INGR", "SCRL", "CSTY"},
    "npcs": {"NPC_", "OTFT", "HDPT", "FACT", "PACK"},
    "visual": {"WTHR", "CLMT", "LGTM", "IMGS", "IMAD", "LIGH", "TXST", "SPGD", "GRAS", "TREE",
               "WATR", "EFSH", "LENS", "VOLI", "LSCR", "STAT", "IDLE", "ANIO"},
    "audio": {"SNDR", "SOUN", "MUSC", "MUST", "SNCT", "SOPM", "ASPC", "REVB"},
    "quests": {"QUST", "DIAL", "INFO", "DLBR", "DLVW", "SCEN", "SMQN", "SMBN", "SMEN"},
}
_BUCKET_WORDS = {
    "items": ("armor and weapons", "armaduras y armas"),
    "gameplay": ("perks, spells, races or settings", "perks, hechizos, razas o ajustes"),
    "npcs": ("characters", "personajes"),
    "visual": ("weather, lighting or looks", "clima, luz o apariencia"),
    "audio": ("sounds and music", "sonidos y música"),
    "quests": ("quests and dialogue", "misiones y diálogos"),
}
_LOOT_MAP = {
    "Unofficial Patches": "fixes", "Script Fixes & Optimization": "fixes", "Fixes": "fixes",
    "Late Fixes & Changes": "fixes",
    "Resources & Frameworks": "frameworks", "Follower Frameworks": "frameworks",
    "Races & Classes": "gameplay", "Standing Stone Effects": "gameplay", "Economy": "gameplay",
    "Crafting": "gameplay", "Alchemy Overhauls": "gameplay", "Skills & Perks": "gameplay",
    "Vampire Gameplay Overhauls": "gameplay", "Alternate Start": "gameplay",
    "Leveled List Modifiers": "gameplay",
    "Cell Weather & Lighting": "visual", "Lux Interior Lighting": "visual", "Torch Lighting": "visual",
    "Water Overhauls": "visual", "No Grass": "visual", "Dynamic LOD": "visual",
    "Cell Music": "audio", "Immersive Citizens": "npcs", "Map Markers": "ui", "Paper Maps": "ui",
    "Palaces Castles Enhanced": "lands", "Winterhold Restored": "lands",
    "City Worldspace Movers": "lands", "Open Cities Skyrim": "lands",
    "Conflict Resolution Patches (Late)": "patches", "Dynamic Patches": "patches",
}


def _rx(words: str) -> re.Pattern:
    return re.compile(r"(?<![a-z])(?:" + words + r")(?![a-z])")


_NAME_STRONG = [
    ("fixes", _rx(r"unofficial|bug ?fix(?:es)?|engine fixes|fixes|fix")),
    ("followers", _rx(r"followers?|companions?|spouses?|inigo|lucien|auri|kaidan|vilja|sofia|"
                      r"recorder|kharjo|amazing follower|nff|eff")),
    ("ui", _rx(r"skyui|ui|hud|menus?|interface|compass|fonts?|map markers?|paper map|"
               r"loading screens?|quickloot|more ?hud|hotkeys?")),
    ("frameworks", _rx(r"frameworks?|xpmse|xp32|fnis|nemesis|skeleton|sex ?lab|racemenu|"
                       r"papyrus ?util|mcm helper|resource pack|resources")),
]
_NAME_WEAK = [
    ("audio", _rx(r"sounds?|music|audio|soundtrack|footsteps?|voices?|ambien\w*")),
    ("visual", _rx(r"textures?|retextures?|meshes|mesh|hd|4k|2k|1k|weathers?|lighting|lights?|lux|"
                   r"enb|grass|trees?|water|flora|landscapes?|clouds?|glossy|body|bodies|face|"
                   r"faces|hair|eyes|smim|animations?|anims?|idles?|skin|effects?|vfx|"
                   r"impacts?|particles?|lod")),
    ("items", _rx(r"armou?rs?|weapons?|swords?|bows?|daggers?|outfits?|cloth\w*|robes?|jewel\w*|"
                  r"staff|staves|shields?|helmets?|boots|gear|ammo|arrows?|axes?|maces?")),
    ("gameplay", _rx(r"perks?|ordinator|vokrii|adamant|spells?|magic|mysticism|apocalypse|odin|"
                     r"races?|imperious|morningstar|combat|valravn|wildcat|economy|trade|"
                     r"vendors?|gold|loot|skills?|training|stamina|survival|needs|alchemy|"
                     r"smithing|crafting|enchant\w*|summermyst|standing stones?|andromeda|"
                     r"vampires?|sacrilege|werewolf|werebeasts?|growl|faiths?|trua|religion|"
                     r"leveled|encounters?|difficulty|quick ?start|alternate start|ecco|"
                     r"character creation|carry weight|leveling|thunderchild|shouts?|"
                     r"dragons?|stones|pyp|protect your people|regen\w*")),
    ("quests", _rx(r"quests?|questline|adventures?|sagas?|mysteries|mystery")),
    ("lands", _rx(r"dungeons?|caves?|worldspaces?|islands?|cit(?:y|ies)|towns?|villages?|"
                  r"castles?|forts?|home|homes|house|manor|lands|realms?|ruins?|"
                  r"hold|holds|settlements?|hideouts?|lairs?|tower")),
    ("npcs", _rx(r"npcs?|citizens?|people|guards?|population|bijin|pandorable|"
                 r"characters|bandits|beautiful people")),
    ("frameworks", _rx(r"frameworks?|resources?|library|lib|api|assets?|core|utils?|"
                       r"papyrusutil|addons?")),
    ("patches", _rx(r"patch(?:es)?|compat\w*|tweaks?")),
]


def _is_base(name: str) -> bool:
    from .loot import _is_base as loot_base
    return loot_base(name)


def _main_plugin(u: dict) -> dict | None:
    """Plugin facts of the plugin that stands for the unit."""
    pfs = u.get("plugin_facts") or []
    names = u.get("plugins") or []
    if not names:
        return None
    if not pfs:
        return {"name": names[0], "file": (u.get("files") or names)[0], "hash": None, "size": 0,
                "records": 0, "masters": u.get("masters") or [], "esm": False, "light": u.get("light"),
                "merge_of": [], "new": {}, "ovr": {}, "error": None, "missing": True}
    if len(pfs) == 1:
        return pfs[0]
    lows = {p["name"].lower() for p in pfs}
    used = [p for p in pfs if any(p["name"].lower() == m.lower() for q in pfs for m in q["masters"])]
    if len(used) == 1:
        return used[0]
    from .transfer import stem_score
    unit = re.sub(r"\s*\d+(\.\d+)*\s*(nx)?$", "", u.get("name", ""), flags=re.I) or u.get("name", "")
    scored = sorted(pfs, key=lambda p: (-stem_score(unit, Path(p["name"]).stem),
                                        bool(re.search(r"patch|compat", p["name"].lower())),
                                        -p.get("size", 0)))
    del lows
    return scored[0]


def _haystack(v: dict) -> str:
    bits = [Path(p).stem for p in v["plugins"]] + [v.get("unit_name", "")]
    if not v["plugins"]:
        bits += [Path(b).stem for b in v["bsas"]]
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", " ".join(bits))
    return s.lower().replace("_", " ").replace("-", " ")


def categorize(v: dict, masterlist=None) -> tuple[str, list[str]]:
    """(category id, [why en, why es]) for one version of a mod."""
    main = v.get("_main")
    hay = _haystack(v)
    masters = [m for m in (main["masters"] if main else []) if not _is_base(m)]
    name = main["name"] if main else (v["bsas"][0] if v["bsas"] else v.get("unit_name", ""))
    low = name.lower()

    def say(cat, en, es):
        return cat, [en, es]

    # 1. strong names: unofficial patches and bug fixes
    for cat, rx in _NAME_STRONG[:1]:
        m = rx.search(hay)
        if m and len(masters) < 2:
            return say(cat, f"Its name says it's a fix ({m.group(0)}).",
                       f"Su nombre dice que es una corrección ({m.group(0)}).")
    # 2. patches
    if len(masters) >= 2:
        return say("patches", f"Patch between {_and(masters)}: it needs both as masters.",
                   f"Parche entre {_and(masters, True)}: necesita ambos como masters.")
    with_ussep = [m for m in (main["masters"] if main else [])
                  if not _is_base(m) or norm_name(m) == USSEP_NORM]
    if with_ussep and main and norm_name(main["name"]) != USSEP_NORM and \
            re.search(r"patch|compat|addon|add-on|tweak|ussep", low):
        return say("patches", f"Patch for {with_ussep[0]}, its master.",
                   f"Parche para {with_ussep[0]}, su master.")
    # 3. followers and interface by name
    for cat, rx in _NAME_STRONG[1:]:
        m = rx.search(hay)
        if m:
            label = next(c for c in CATEGORIES if c["id"] == cat)
            return say(cat, f"Its name says so ({m.group(0)}): {label['en'].lower()}.",
                       f"Su nombre lo dice ({m.group(0)}): {label['es'].lower()}.")
    # 4. LOOT group
    if masterlist is not None and main is not None:
        try:
            meta = masterlist.lookup(main["name"], main.get("file"))
        except Exception:  # noqa: BLE001
            meta = None
        cat = _LOOT_MAP.get(meta.group) if meta and meta.group else None
        if cat:
            return say(cat, f"LOOT puts it in '{meta.group}'.", f"LOOT lo pone en '{meta.group}'.")
    # 5. records
    if main is not None and (main.get("new") or main.get("ovr")):
        got = _by_records(main)
        if got:
            return got
    # 6. what its BSAs hold
    got = _by_bsas(v)
    if got:
        return got
    # 7. weak names
    for cat, rx in _NAME_WEAK:
        m = rx.search(hay)
        if m:
            label = next(c for c in CATEGORIES if c["id"] == cat)
            return say(cat, f"Guessed from its name ({m.group(0)}): {label['en'].lower()}.",
                       f"Deducido por el nombre ({m.group(0)}): {label['es'].lower()}.")
    if main is not None and main.get("records") == 0 and not v["bsas"]:
        return say("other", "Empty plugin (no records).", "Plugin vacío (sin registros).")
    return say("other", "No clear signal.", "Sin señales claras.")


def _by_records(main: dict):
    new, ovr = Counter(main.get("new") or {}), Counter(main.get("ovr") or {})
    both = new + ovr
    total = sum(both.values())
    if not total:
        return None
    if new["WRLD"]:
        en, es = _plural(new["WRLD"], ("new worldspace", "new worldspaces"),
                         ("espacio de mundo nuevo", "espacios de mundo nuevos"))
        return "lands", [f"Adds {en}.", f"Agrega {es}."]
    placed = main.get("placed_bytes") or 0
    mostly_new = new["CELL"] >= 0.5 * ovr["CELL"]
    if mostly_new and (new["CELL"] >= 3 or (new["CELL"] >= 1 and placed >= 8192 and new["NPC_"] < 4)):
        en, es = _plural(new["CELL"], ("new cell", "new cells"), ("celda nueva", "celdas nuevas"))
        return "lands", [f"Adds {en} (interiors or dungeons) with the objects placed in them.",
                         f"Agrega {es} (interiores o mazmorras) con los objetos colocados en ellas."]
    if 1 <= new["NPC_"] <= 3 and new["INFO"] >= 10 and 1 <= new["QUST"] <= 4:
        en, es = _plural(new["NPC_"], ("new character", "new characters"),
                         ("personaje nuevo", "personajes nuevos"))
        return "followers", [f"Adds {en} with their own dialogue ({new['INFO']} lines).",
                             f"Agrega {es} con diálogo propio ({new['INFO']} líneas)."]
    if (new["QUST"] >= 2 and new["INFO"] + new["DIAL"] >= 20) or (new["QUST"] >= 5 and new["INFO"] >= 10):
        return "quests", [f"Adds {new['QUST']} quests and {new['INFO']} dialogue lines.",
                          f"Agrega {new['QUST']} misiones y {new['INFO']} líneas de diálogo."]
    scored = {cat: sum(both[t] for t in types) for cat, types in _BUCKETS.items()}
    scored["visual"] -= new["STAT"]        # new statics build places; overridden ones are looks
    denom = sum(c for t, c in both.items() if t not in _STRUCT) + ovr["STAT"]
    cat, n = max(scored.items(), key=lambda kv: kv[1])
    if n >= 2 and denom and n >= 0.3 * denom:
        en_w, es_w = _BUCKET_WORDS[cat]
        return cat, [f"Mostly {en_w} ({n} of {denom} records).",
                     f"Sobre todo {es_w} ({n} de {denom} registros)."]
    only_new = sum(ovr.values()) <= 0.03 * total
    if main.get("esm") and only_new and main.get("dependents", 0) >= 2 and total >= 5:
        return "frameworks", [f"Master file with only new records that {main['dependents']} plugins "
                              "build on.",
                              f"Archivo master con solo registros nuevos que usan "
                              f"{main['dependents']} plugins."]
    return None


def _by_bsas(v: dict):
    facts = [f for f in (v.get("_bsa_facts") or {}).values() if f and f.get("entries")]
    if not facts:
        return None
    tops: Counter = Counter()
    hkx = 0
    for f in facts:
        tops.update(f.get("tops") or {})
        hkx += f.get("hkx", 0)
    n = sum(tops.values())
    if not n:
        return None
    snd = tops["sound"] + tops["music"]
    if snd / n > 0.5:
        return "audio", [f"Its BSAs are mostly sounds ({snd} of {n} files).",
                         f"Sus BSA son sobre todo sonidos ({snd} de {n} archivos)."]
    if tops["interface"] / n > 0.3:
        return "ui", [f"Its BSAs are mostly interface files ({tops['interface']} of {n}).",
                      f"Sus BSA son sobre todo archivos de interfaz ({tops['interface']} de {n})."]
    look = tops["textures"] + tops["meshes"]
    main = v.get("_main")
    small = main is None or (main.get("records") or 0) < 20
    if small and look / n >= 0.9:
        if hkx / n > 0.3:
            return "visual", [f"Animations ({hkx} of {n} files in its BSAs).",
                              f"Animaciones ({hkx} de {n} archivos en sus BSA)."]
        return "visual", [f"Only textures and meshes ({look} of {n} files).",
                          f"Solo texturas y modelos ({look} de {n} archivos)."]
    return None


# =================================================================== catalog
class _UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.p[max(a, b)] = min(a, b)


def _version(src: dict, u: dict) -> dict:
    main = _main_plugin(u)
    flags = [_flag_texts(f["code"], f.get("params") or {}) for f in u["flags"]]
    if u["kind"] in ("archive", "mod") and not u.get("peeked"):
        flags.append(_flag_texts("not-peeked", {}))
    plugins = u["plugins"]
    hashes = {pf["name"].lower(): pf["hash"] for pf in u.get("plugin_facts") or []}
    return {
        "pack": src["name"], "pack_path": src["path"], "source_kind": src["kind"],
        "data_dir": src.get("data_dir"),
        "edition": src.get("mode"), "unit_id": u["id"], "unit_kind": u["kind"],
        "unit_name": u["name"], "main": main["name"] if main else None,
        "plugins": plugins, "bsas": u["bsas"], "bsa_files": u.get("bsa_files", u["bsas"]),
        "files": u.get("files", plugins),
        "masters": u["masters"],
        "plugin_masters": {pf["name"]: pf["masters"] for pf in u.get("plugin_facts") or []},
        "size": u["size"], "tex_bytes": u["tex_bytes"],
        "ccc_bytes": sum(len(p.encode("cp1252", "replace")) + 2 for p in plugins),
        "hash": main.get("hash") if main else None,
        "hashes": [hashes.get(p.lower()) for p in plugins],
        "bsa_sizes": [(u.get("bsa_facts") or {}).get(b, {}).get("size") for b in u["bsas"]],
        "flags": flags, "light": bool(u["light"]), "ini": u.get("ini") or {},
        "position": u.get("position"), "renamed": u.get("renamed") or [],
        "records": main.get("records") if main else None,
        "merge_of": main.get("merge_of") if main else [],
        "placeholder": False,
        "_main": main, "_bsa_facts": u.get("bsa_facts") or {},
    }


def _tokens(v: dict) -> list[str]:
    out = []
    main = v["_main"]
    if main:
        out.append("p:" + norm_name(main["name"]))
        if main.get("file") and main["file"] != main["name"]:
            out.append("p:" + norm_name(main["file"]))
        for o in v["renamed"]:
            if Path(o).suffix.lower() in PLUGIN_EXT:
                out.append("p:" + norm_name(o))
        if (main.get("hash") and (main.get("size") or 0) >= HASH_MIN_BYTES
                and (main.get("records") or 0) > 0 and (main.get("new") or main.get("ovr"))):
            out.append("h:" + main["hash"])
    else:
        out += ["b:" + norm_name(b) for b in v["bsas"]]
    return out


def build_catalog(library_root, progress=None, cache_dir=None, masterlist=None) -> dict:
    """All mods of all packs (and loose Switch mods) in the Library, grouped by mod.
    `masterlist`: a loot.Masterlist or a path to masterlist.yaml (optional)."""
    from . import library as L
    t0 = time.time()
    tick = _tick(progress)
    root = L.ensure(library_root)
    cache = Path(cache_dir) if cache_dir else root / CACHE_DIR
    if masterlist is not None and not hasattr(masterlist, "lookup"):
        from .loot import load_masterlist
        masterlist = load_masterlist(Path(masterlist))
    from . import project as PJ
    rows = [{"kind": "pack", "name": p["name"], "path": p["path"]} for p in PJ.list_projects(root)]
    done = {str(r["path"]).lower() for r in rows}
    try:
        done |= {x["path"].lower() for x in PJ.legacy(root) if x.get("done")}
    except Exception:  # noqa: BLE001
        pass
    # packs from before projects count until they become one; packs being created never did
    rows += [r for r in L.list_library(root, health=False) if str(r["path"]).lower() not in done]
    sources = []
    for i, row in enumerate(rows):
        tick(row["name"], i, len(rows))
        if row.get("missing") or row.get("draft"):
            continue          # a pack being created isn't a source (it's made from the others)
        path = Path(row["path"])
        if row["kind"] == "pack":
            sources.append(_pack_source(path, row["name"], cache, tick))
        else:
            s = _mod_source(path, row["name"], cache, tick)
            if s:
                sources.append(s)
    return _assemble(sources, masterlist, time.time() - t0)


def _identical(vs: list[dict]) -> bool:
    """Same plugin bytes in every version (BSA-only mods: same BSA names and sizes)."""
    if len(vs) < 2:
        return True
    if any(v["plugins"] for v in vs):
        sigs = [tuple(sorted(h or "" for h in v["hashes"])) for v in vs]
        return all(v["plugins"] and None not in v["hashes"] for v in vs) and len(set(sigs)) == 1
    sigs = [tuple(sorted(zip([b.lower() for b in v["bsas"]], v["bsa_sizes"]))) for v in vs]
    return all(None not in v["bsa_sizes"] for v in vs) and len(set(sigs)) == 1


def _assemble(sources: list[dict], masterlist, seconds: float) -> dict:
    versions: list[dict] = []
    packs = []
    for s in sources:
        twins = 0
        for u in s["units"]:
            if u.get("twin_of"):
                twins += 1
                continue
            versions.append(_version(s, u))
        packs.append({"name": s["name"], "path": s["path"], "kind": s["kind"], "mode": s.get("mode"),
                      "data_dir": s.get("data_dir"), "units": len(s["units"]) - twins,
                      "hidden_twins": twins, "cached": s.get("cached", False), "error": s.get("error")})
    # merges: which packs carry which components inside a merge
    merged_in: dict[str, list[dict]] = {}
    for v in versions:
        for comp in v["merge_of"] or []:
            merged_in.setdefault(norm_name(comp), []).append(
                {"pack": v["pack"], "pack_path": v["pack_path"], "merge": v["main"], "unit_id": v["unit_id"]})
    for v in versions:
        main = v["_main"]
        if main and (main.get("records") or 0) == 0 and not v["bsas"]:
            hits = [m for m in merged_in.get(norm_name(main["name"]), []) if m["pack_path"] == v["pack_path"]]
            if hits:
                v["placeholder"] = True
                v["flags"].append(_flag_texts("placeholder", {"merge": hits[0]["merge"]}))
    # grouping
    uf = _UF(len(versions))
    seen: dict[str, int] = {}
    toks = []
    for i, v in enumerate(versions):
        t = _tokens(v)
        toks.append(t)
        for k in t:
            if k in seen:
                uf.union(seen[k], i)
            else:
                seen[k] = i
    groups: dict[int, list[int]] = {}
    for i in range(len(versions)):
        groups.setdefault(uf.find(i), []).append(i)
    entries = []
    for members in groups.values():
        vs = [versions[i] for i in members]
        keys = sorted({k for i in members for k in toks[i]},
                      key=lambda k: ({"p": 0, "b": 1, "h": 2}[k[0]], k))
        key = keys[0] if keys else f"u:{vs[0]['pack']}|{vs[0]['unit_id']}"
        names = Counter((Path(v["main"]).stem if v["main"] else v["unit_name"]) for v in vs)
        name = max(names.items(), key=lambda kv: (kv[1], "'" in kv[0], -len(kv[0])))[0]
        cats = []
        for v in vs:
            cat, why = categorize(v, masterlist)
            v["category"], v["category_why"] = cat, why
            cats.append(cat)
        cc = Counter(cats)
        best = max(cc.items(), key=lambda kv: (kv[1], kv[0] != "other",
                                               -CATEGORY_IDS.index(kv[0])))[0]
        why = next(v["category_why"] for v in vs if v["category"] == best)
        identical = _identical(vs)
        merge_of = next((v["merge_of"] for v in vs if v["merge_of"]), [])
        mains = {norm_name(v["main"]) for v in vs if v["main"]}
        inside = []
        for mn in mains:
            for hit in merged_in.get(mn, []):
                if norm_name(hit["merge"] or "") not in mains and hit not in inside:
                    inside.append({"pack": hit["pack"], "pack_path": hit["pack_path"],
                                   "merge": hit["merge"], "unit_id": hit["unit_id"]})
        for v in vs:
            v.pop("_main", None)
            v.pop("_bsa_facts", None)
        vs.sort(key=lambda v: (v["pack"].lower(), v["unit_id"]))
        entries.append({"key": key, "name": name, "kind": "plugin" if vs[0]["plugins"] else "bsa",
                        "category": best, "category_why": why,
                        "packs": sorted({v["pack"] for v in vs}),
                        "versions": vs, "identical": bool(identical),
                        "merge_of": merge_of, "inside_merges": inside})
    # keys must be unique for the UI
    used: Counter = Counter()
    for e in entries:
        used[e["key"]] += 1
        if used[e["key"]] > 1:
            e["key"] = f"{e['key']}#{used[e['key']]}"
    entries.sort(key=lambda e: e["name"].lower())
    counts = Counter(e["category"] for e in entries)
    return {"version": CATALOG_VERSION, "built": time.strftime("%Y-%m-%d %H:%M:%S"),
            "packs": packs, "entries": entries, "categories": CATEGORIES,
            "counts": {c: counts.get(c, 0) for c in CATEGORY_IDS},
            "stats": {"entries": len(entries), "versions": len(versions),
                      "shared": sum(1 for e in entries if len(e["packs"]) > 1),
                      "seconds": round(seconds, 3),
                      "cached_packs": sum(1 for p in packs if p["cached"])}}


# =================================================================== planning
def _pack_state(path: Path, base: dict) -> dict:
    """The starting point when the picks go into a pack that already exists
    (the pack being created): its load list, inis, BSAs and plugins."""
    pk = Pack.open(Path(path))
    edition = pk.mode
    st = {"edition": edition, "ccc": [], "inis": {}, "ussep": None, "problems": [], "bsas": [],
          "tex": int(base.get("tex_bytes") or 0), "size": pk.data_size(), "into": str(pk.root)}
    if not pk.data_dir:
        st["problems"].append(_problem("no-data", "block", "That pack has no Data folder.",
                                       "Ese pack no tiene carpeta Data."))
    # every line of the pack's load list, as the file has them ('#' lines count bytes too)
    st["ccc"] = C.parse_ccc(pk.list_path.read_bytes()).entries if pk.list_path and pk.list_path.exists() else []
    for ini in pk.inis:
        st["inis"][ini.path.name] = ini.path.read_bytes()
    from .draft import excluded_files
    parked = excluded_files(pk.root)              # marked "doesn't go": not in the pack for the plan
    st["bsas"] = [p.name for k, p in pk.bsas.items() if k not in parked]
    st["have"] = {norm_name(n) for n in pk.plugins if n not in parked} | \
        {norm_name(e) for e in st["ccc"] if not e.startswith("#")}
    st["have_files"] = {n.lower() for n in pk.data_files if n.lower() not in parked}
    st["lists"] = {n: {k: parse_ini(raw).archive_list(k) for k in ARCHIVE_KEYS
                       if parse_ini(raw).get("Archive", k) is not None}
                   for n, raw in st["inis"].items()}
    return st


def _base_state(base: dict) -> dict:
    """What create_project would start with, without writing anything.
    base["into"]: the picks go into that existing pack instead."""
    if base.get("into"):
        return _pack_state(Path(base["into"]), base)
    from .builder import CC_PRESETS, VANILLA_EN_INI, _archive_key_for, _vanilla_lists, find_base_files
    edition = (base.get("edition") or "AE").upper()
    lang = base.get("lang") or "en"
    st = {"edition": edition, "ccc": [], "inis": {}, "ussep": None, "problems": [], "bsas": [],
          "tex": 0, "size": 0}
    inis_dir = base.get("inis_dir")
    found = find_base_files(Path(inis_dir)) if inis_dir and Path(inis_dir).exists() else {"inis": [], "ccc": None}
    want = {"skyrim.ini", f"skyrim_{lang}.ini"}
    for p in found["inis"]:
        if p.name.lower() in want:
            st["inis"][p.name] = _vanilla_lists(p.read_bytes())
    if not any(n.lower() == "skyrim.ini" for n in st["inis"]):
        st["problems"].append(_problem("no-base-ini", "block",
                                       "There's no Skyrim.ini in the base inis folder.",
                                       "No hay Skyrim.ini en la carpeta de inis base."))
    if lang == "en" and not any(n.lower() == "skyrim_en.ini" for n in st["inis"]):
        st["inis"]["Skyrim_en.ini"] = VANILLA_EN_INI.encode("utf-8")
    preset = base.get("cc_preset") or "ussep"
    if edition == "AE":
        if preset == "base" and found["ccc"]:
            st["ccc"] = [e for e in C.read_ccc(found["ccc"]).entries if e.lower().startswith("cc")]
        else:
            st["ccc"] = list(CC_PRESETS.get(preset, K.USSEP_CC_MASTERS))
    variant = base.get("ussep")
    if variant:
        from .ussep import scan
        from .transfer import bsa_facts as tfacts
        info = scan(base.get("ussep_dir"))
        v = next((x for x in info["variants"] if x["id"] == variant), None)
        if not v or not info["bsas"]:
            st["problems"].append(_problem(
                "ussep-missing", "block",
                f"The USSEP folder ({info['folder']}) has no {variant} version with its BSAs.",
                f"La carpeta de USSEP ({info['folder']}) no tiene la versión {variant} con sus BSA."))
        elif edition == "SE" and v["cc"]:
            st["problems"].append(_problem(
                "ussep-cc-se", "block",
                "The SE version can't use Creation Club masters; pick USSEP No_CC.",
                "La versión SE no puede usar masters del Creation Club; elige USSEP No_CC."))
        else:
            if edition == "AE":
                have = {e.lower() for e in st["ccc"]}
                st["ccc"] += [m for m in v["cc"] if m.lower() not in have]
            st["ussep"] = {"variant": variant, "plugin": K.USSEP_PLUGIN, "bsas": info["bsas"]}
            folder = Path(info["folder"])
            st["size"] += v["size"]
            for b in info["bsas"]:
                p = folder / b
                st["bsas"].append(b)
                st["size"] += p.stat().st_size
                st["tex"] += tfacts(p).get("tex") or 0
                for key in _archive_key_for(p):
                    _ini_add(st["inis"], key, b, first=True)
    st["lists"] = {n: {k: parse_ini(raw).archive_list(k) for k in ARCHIVE_KEYS
                       if parse_ini(raw).get("Archive", k) is not None}
                   for n, raw in st["inis"].items()}
    return st


def _ini_add(inis: dict, key: str, bsa: str, first: bool = False) -> None:
    from .ini import set_archive_list
    for n, raw in list(inis.items()):
        ini = parse_ini(raw)
        if ini.get("Archive", key) is None:
            continue
        cur = ini.archive_list(key)
        if bsa.lower() in {c.lower() for c in cur}:
            continue
        cur.append(bsa)
        if first:
            cur = K.after_vanilla(cur, [bsa])
        inis[n] = set_archive_list(raw, key, cur)


def _problem(code: str, severity: str, en: str, es: str, fix: tuple[str, str] | None = None, **extra) -> dict:
    out = {"code": code, "severity": severity, "text": [en, es]}
    if fix:
        out["fix"] = list(fix)
    out.update(extra)
    return out


def _index(catalog: dict) -> tuple[dict, dict]:
    by_pick: dict[tuple[str, str], tuple[dict, dict]] = {}
    by_pack: dict[str, list[tuple[dict, dict]]] = {}
    for e in catalog.get("entries", []):
        for v in e["versions"]:
            by_pick[(v["pack_path"], v["unit_id"])] = (e, v)
            by_pack.setdefault(v["pack_path"], []).append((e, v))
    return by_pick, by_pack


def _cc_needed(v: dict) -> list[str]:
    from .edition import cc_masters
    return cc_masters(v.get("masters") or [])


def _has_esl(v: dict) -> bool:
    return any(str(p).lower().endswith(".esl") for p in v.get("plugins") or [])


def _pick_ref(e: dict, v: dict) -> dict:
    return {"key": e["key"], "pack": v["pack"], "pack_path": v["pack_path"], "unit_id": v["unit_id"]}


def _masters_of(v: dict) -> dict[str, list[str]] | None:
    if v.get("masters") is None:
        return None
    pm = v.get("plugin_masters") or {}
    if pm:
        return {p: pm.get(p, []) for p in v["plugins"]}
    return {p: list(v["masters"]) for p in v["plugins"]} if v["plugins"] else {}


def plan_build(catalog: dict, picks: list[dict], base: dict, progress=None) -> dict:
    """Check a selection before building: budget, masters, clashes. Writes nothing.

    picks: [{"key", "pack_path", "unit_id"}] in the order the user chose them.
    base: {"edition": "AE"|"SE", "inis_dir", "cc_preset": "ussep"|"all"|"none"|"base",
           "ussep": "All_CC"|"SurvivalMode"|"No_CC"|None, "ussep_dir", "lang": "en"}."""
    tick = _tick(progress)
    by_pick, by_pack = _index(catalog)
    st = _base_state(base)
    edition = st["edition"]
    problems: list[dict] = list(st["problems"])
    suggestions: list[dict] = []
    items: list[dict] = []
    skipped: list[dict] = []
    seen_keys: dict[str, dict] = {}
    # ---- the picks themselves
    for i, p in enumerate(picks):
        tick("plan", i, len(picks))
        hit = by_pick.get((str(p.get("pack_path")), p.get("unit_id")))
        if hit is None:
            problems.append(_problem("unknown-pick", "block",
                                     f"{p.get('unit_id')} is no longer in {p.get('pack_path')}. Build the "
                                     "catalog again.",
                                     f"{p.get('unit_id')} ya no está en {p.get('pack_path')}. Vuelve a "
                                     "armar el catálogo.", pick=p))
            continue
        e, v = hit
        it = {"key": e["key"], "name": e["name"], "category": e["category"], "pack": v["pack"],
              "pack_path": v["pack_path"], "unit_id": v["unit_id"], "source_kind": v["source_kind"],
              "reason": "picked", "needed_by": [], "status": "bring", "_v": v, "_e": e}
        main_n = norm_name(v["main"]) if v["main"] else None
        if st["ussep"] and (main_n == USSEP_NORM or (not v["plugins"] and v["bsas"] and
                            {b.lower() for b in v["bsas"]} <= {b.lower() for b in K.USSEP_KOKA_BSAS})):
            it["status"] = "covered"
            skipped.append({**_pick_ref(e, v), "name": e["name"], "reason": [
                f"The new pack already gets USSEP ({st['ussep']['variant']}) from the base.",
                f"El pack nuevo ya trae USSEP ({st['ussep']['variant']}) desde la base."]})
        elif edition == "SE" and _has_esl(v):
            it["status"] = "refused"
            skipped.append({**_pick_ref(e, v), "name": e["name"], "reason": [
                "It's an ESL (light plugin); the SE version can't load it. Convert mods turns it into an .esp.",
                "Es un ESL (plugin ligero); la versión SE no lo carga. Convertir mods lo pasa a .esp."]})
        elif edition == "SE" and _cc_needed(v):
            it["status"] = "refused"
            cc = ", ".join(_cc_needed(v)[:3])
            skipped.append({**_pick_ref(e, v), "name": e["name"], "reason": [
                f"It needs Creation Club content ({cc}), which the SE version doesn't have.",
                f"Necesita contenido del Creation Club ({cc}), que la versión SE no tiene."]})
        elif st.get("have") is not None and v["plugins"] and \
                all(norm_name(p) in st["have"] for p in v["plugins"]):
            it["status"] = "present"
            skipped.append({**_pick_ref(e, v), "name": e["name"], "reason": [
                "It's already in the pack.", "Ya está en el pack."]})
        elif st.get("have") is not None and not v["plugins"] and v["bsas"] and \
                all(b.lower() in st["have_files"] for b in v["bsas"]):
            it["status"] = "present"
            skipped.append({**_pick_ref(e, v), "name": e["name"], "reason": [
                "Its BSAs are already in the pack.", "Sus BSA ya están en el pack."]})
        elif e["key"] in seen_keys:
            it["status"] = "duplicate"
            first = seen_keys[e["key"]]
            skipped.append({**_pick_ref(e, v), "name": e["name"], "reason": [
                f"You also picked it from {first['pack']}; only that one is brought.",
                f"También lo elegiste de {first['pack']}; solo se trae ese."]})
        else:
            seen_keys[e["key"]] = it
        items.append(it)
    # ---- masters
    cc_have = {c.lower() for c in st["ccc"]}
    cc_added: list[str] = []
    providers: dict[str, dict] = {}

    def provide(it):
        for p in it["_v"]["plugins"] + list(it["_v"].get("files") or []) + list(it["_v"].get("renamed") or []):
            providers.setdefault(norm_name(p), it)
    for it in items:
        if it["status"] == "bring":
            provide(it)
    masters: list[dict] = []
    missing: list[dict] = []
    queue = [it for it in items if it["status"] == "bring"]
    done: set[int] = set()
    while queue:
        it = queue.pop(0)
        if id(it) in done:
            continue
        done.add(id(it))
        v = it["_v"]
        ms = _masters_of(v)
        if ms is None:
            masters.append({"plugin": v["unit_name"], "master": None, "from": "unknown",
                            "pick": _pick_ref(it["_e"], v),
                            "text": ["Still packed; its masters are checked when it's unpacked.",
                                     "Sigue comprimido; sus masters se revisan al descomprimirlo."]})
            continue
        own = {norm_name(p) for p in v["plugins"]}
        for plugin, mlist in ms.items():
            for m in mlist:
                ml, mn = m.lower(), norm_name(m)
                row = {"plugin": plugin, "master": m, "pick": _pick_ref(it["_e"], v)}
                if mn in own:
                    continue
                if ml in VANILLA:
                    row["from"] = "game"
                elif ml in CC_LOWER:
                    if ml in cc_have:
                        row["from"] = "cc"
                    elif edition == "AE":
                        row["from"] = "cc-added"
                        if CC_LOWER[ml] not in cc_added:
                            cc_added.append(CC_LOWER[ml])
                    else:
                        row["from"] = "missing"
                elif st["ussep"] and mn == USSEP_NORM:
                    row["from"] = "ussep"
                elif mn in (st.get("have") or ()):
                    row["from"] = "pack"
                elif mn in providers and providers[mn] is not it:
                    prov = providers[mn]
                    row["from"] = "auto" if prov["reason"] == "master" else "pick"
                    row["source"] = _pick_ref(prov["_e"], prov["_v"])
                    if prov["reason"] == "master" and plugin not in prov["needed_by"]:
                        prov["needed_by"].append(plugin)
                    if prov["pack_path"] != it["pack_path"]:
                        it.setdefault("_after", set()).add(prov["pack_path"])
                else:
                    same = _provider_in(by_pack.get(v["pack_path"], []), mn, v)
                    if same is not None and it["source_kind"] == "pack":
                        e2, v2 = same
                        auto = {"key": e2["key"], "name": e2["name"], "category": e2["category"],
                                "pack": v2["pack"], "pack_path": v2["pack_path"], "unit_id": v2["unit_id"],
                                "source_kind": v2["source_kind"], "reason": "master",
                                "needed_by": [plugin], "status": "bring", "_v": v2, "_e": e2}
                        if edition == "SE" and _has_esl(v2):
                            row["from"] = "missing"
                        else:
                            items.append(auto)
                            provide(auto)
                            queue.append(auto)
                            row["from"], row["source"] = "auto", _pick_ref(e2, v2)
                            seen_keys.setdefault(e2["key"], auto)
                    else:
                        row["from"] = "missing"
                if row["from"] == "missing":
                    others = []
                    for (pp, uid), (e3, v3) in by_pick.items():
                        if any(norm_name(x) == mn for x in v3["plugins"]) and not (edition == "SE" and _has_esl(v3)):
                            others.append(_pick_ref(e3, v3))
                    row["from"] = "other-pack" if others else "missing"
                    row["suggestions"] = others
                    missing.append(row)
                masters.append(row)
    # merge duplicates of needed_by for auto items brought twice
    merged: dict[tuple, dict] = {}
    final_items = []
    for it in items:
        k = (it["pack_path"], it["unit_id"])
        if it["status"] == "bring" and k in merged:
            for n in it["needed_by"]:
                if n not in merged[k]["needed_by"]:
                    merged[k]["needed_by"].append(n)
            continue
        if it["status"] == "bring":
            merged[k] = it
        final_items.append(it)
    items = final_items
    bring = [it for it in items if it["status"] == "bring"]
    for row in missing:
        sugg = row.get("suggestions") or []
        if sugg:
            s = sugg[0]
            problems.append(_problem(
                "missing-master", "block",
                f"{row['plugin']} needs {row['master']}; {s['pack']} has it.",
                f"{row['plugin']} necesita {row['master']}; {s['pack']} lo tiene.",
                fix=(f"Pick {row['master']} from {s['pack']} too.",
                     f"Elige también {row['master']} de {s['pack']}."),
                plugin=row["plugin"], master=row["master"]))
            suggestions.append({"code": "add-master", "add": [s], "text": [
                f"Add {row['master']} from {s['pack']} (needed by {row['plugin']}).",
                f"Agrega {row['master']} de {s['pack']} (lo necesita {row['plugin']})."]})
        else:
            problems.append(_problem(
                "missing-master", "block",
                f"{row['plugin']} needs {row['master']}, which no pack in the Library has.",
                f"{row['plugin']} necesita {row['master']}, que no tiene ningún pack de la Biblioteca.",
                fix=(f"Add {row['master']} to the Library as a loose mod, or leave {row['plugin']} out.",
                     f"Agrega {row['master']} a la Biblioteca como mod suelto, o deja fuera {row['plugin']}."),
                plugin=row["plugin"], master=row["master"]))
            suggestions.append({"code": "remove-needer", "remove": [row["pick"]], "text": [
                f"Leave out {row['plugin']} (its master {row['master']} isn't anywhere).",
                f"Deja fuera {row['plugin']} (su master {row['master']} no está en ningún lado)."]})
    # ---- clashes
    clashes = _clashes(items, bring, tick)
    for c in clashes:
        if c["kind"] in ("same-file", "in-merge"):
            problems.append(_problem("clash-" + c["kind"], "warn", *c["text"]))
    # ---- order of source packs
    order = _order(bring)
    # ---- budget
    budget = _budget(st, bring, cc_added, problems, suggestions, base)
    blocking = [p for p in problems if p["severity"] == "block"]
    for it in items:
        it.pop("_e", None)
        it.pop("_v", None)
        it.pop("_after", None)
    return {"ok": not blocking, "edition": edition, "items": items, "order": order,
            "masters": masters, "missing": missing, "cc_added": cc_added,
            "clashes": clashes, "skipped": skipped, "budget": budget,
            "problems": problems, "suggestions": suggestions,
            "ussep": st["ussep"]}


def _provider_in(versions: list[tuple[dict, dict]], mn: str, needer: dict):
    hits = [(e, v) for e, v in versions if v is not needer and (
        any(norm_name(p) == mn for p in v["plugins"])
        or any(norm_name(p) == mn for p in v.get("files") or [])
        or any(norm_name(p) == mn for p in v.get("renamed") or []))]
    hits.sort(key=lambda ev: (ev[1].get("placeholder", False), ev[1]["unit_id"]))
    return hits[0] if hits else None


_BSA_PATHS: dict[tuple, frozenset] = {}


def _bsa_paths(path: Path) -> frozenset | None:
    from .bsa import read_bsa
    try:
        st = path.stat()
    except OSError:
        return None
    k = (str(path), st.st_mtime_ns, st.st_size)
    if k not in _BSA_PATHS:
        try:
            _BSA_PATHS[k] = frozenset(e.path.lower() for e in read_bsa(path).entries)
        except Exception:  # noqa: BLE001
            _BSA_PATHS[k] = frozenset()
    return _BSA_PATHS[k]


def _clashes(items: list[dict], bring: list[dict], tick) -> list[dict]:
    out: list[dict] = []
    # two versions of the same mod
    by_key: dict[str, list[dict]] = {}
    for it in items:
        if it["status"] in ("bring", "duplicate"):
            by_key.setdefault(it["key"], []).append(it)
    for key, its in by_key.items():
        if len(its) > 1:
            same = its[0]["_e"]["identical"]
            out.append({"kind": "same-mod", "severity": "info" if same else "warn",
                        "picks": [_pick_ref(i["_e"], i["_v"]) for i in its],
                        "text": [f"{its[0]['name']} is picked from {_and([i['pack'] for i in its])}. "
                                 f"Only the one from {its[0]['pack']} is brought"
                                 + (" (they are identical)." if same else "; remove the one you don't want."),
                                 f"{its[0]['name']} está elegido de {_and([i['pack'] for i in its], True)}. "
                                 f"Solo se trae el de {its[0]['pack']}"
                                 + (" (son idénticos)." if same else "; quita el que no quieras.")]})
    # the same file name from two different mods
    files: dict[str, list[dict]] = {}
    for it in bring:
        for f in it["_v"]["plugins"] + it["_v"]["bsas"]:
            lst = files.setdefault(f.lower(), [])
            if it not in lst:
                lst.append(it)
    for f, its in files.items():
        keys = {i["key"] for i in its}
        if len(keys) > 1:
            name = next(x for x in its[0]["_v"]["plugins"] + its[0]["_v"]["bsas"] if x.lower() == f)
            out.append({"kind": "same-file", "severity": "warn", "file": name,
                        "picks": [_pick_ref(i["_e"], i["_v"]) for i in its],
                        "text": [f"{_and([i['name'] for i in its])} all bring a file called {name}; "
                                 "only the first one is kept.",
                                 f"{_and([i['name'] for i in its], True)} traen un archivo llamado {name}; "
                                 "solo se conserva el primero."]})
    # a mod picked on its own and a merge that already has it
    for it in bring:
        comps = {norm_name(c) for c in it["_v"].get("merge_of") or []}
        if not comps:
            continue
        for other in bring:
            if other is it or not other["_v"]["main"]:
                continue
            if norm_name(other["_v"]["main"]) in comps and not other["_v"].get("placeholder"):
                out.append({"kind": "in-merge", "severity": "warn", "merge": it["_v"]["main"],
                            "picks": [_pick_ref(it["_e"], it["_v"]), _pick_ref(other["_e"], other["_v"])],
                            "text": [f"{other['name']} is already inside the merge {it['_v']['main']}; "
                                     "having both repeats its changes. Keep one of them.",
                                     f"{other['name']} ya está dentro del merge {it['_v']['main']}; "
                                     "tener ambos repite sus cambios. Deja uno de los dos."]})
    # BSAs from different picks that hold the same files
    loaded = []
    for it in bring:
        v = it["_v"]
        if v["source_kind"] != "pack" or v["unit_kind"] == "archive":
            continue
        ddir = _data_dir(v)
        if ddir is None:
            continue
        for b in v.get("bsa_files") or v["bsas"]:
            paths = _bsa_paths(ddir / b)
            if paths:
                loaded.append((it, b, paths))
    for i in range(len(loaded)):
        a, an, ap = loaded[i]
        for j in range(i + 1, len(loaded)):
            b, bn, bp = loaded[j]
            if a["key"] == b["key"]:
                continue
            common = ap & bp if len(ap) < len(bp) else bp & ap
            if common:
                out.append({"kind": "bsa-overlap", "severity": "info", "bsas": [an, bn],
                            "picks": [_pick_ref(a["_e"], a["_v"]), _pick_ref(b["_e"], b["_v"])],
                            "count": len(common), "examples": sorted(common)[:3],
                            "text": [f"{an} ({a['name']}) and {bn} ({b['name']}) both have {len(common)} "
                                     "of the same files; the one that loads later wins.",
                                     f"{an} ({a['name']}) y {bn} ({b['name']}) tienen {len(common)} "
                                     "archivos iguales; gana el que carga después."]})
    out.sort(key=lambda c: ({"warn": 0, "info": 1}.get(c["severity"], 2), -c.get("count", 0)))
    return out


def _data_dir(v: dict) -> Path | None:
    d = v.get("data_dir")
    return Path(d) if d else None


def _order(bring: list[dict]) -> list[dict]:
    """Source packs in the order the user first picked from them, moved later
    only when a pick needs a master that a pick from another pack brings."""
    first: dict[str, int] = {}
    info: dict[str, dict] = {}
    deps: dict[str, set] = {}
    for n, it in enumerate(bring):
        k = it["pack_path"]
        first.setdefault(k, n)
        info.setdefault(k, {"pack": it["pack"], "pack_path": k, "source_kind": it["source_kind"],
                            "picks": [], "masters": []})
        (info[k]["picks"] if it["reason"] == "picked" else info[k]["masters"]).append(it["unit_id"])
        deps.setdefault(k, set()).update(d for d in it.get("_after", set()) if d != k)
    left = sorted(first, key=first.get)
    out = []
    while left:
        ready = [k for k in left if not (deps[k] & set(left))]
        k = ready[0] if ready else left[0]
        left.remove(k)
        out.append(info[k])
    return out


def _budget(st: dict, bring: list[dict], cc_added: list[str], problems: list, suggestions: list,
            base: dict) -> dict:
    edition = st["edition"]
    ae = edition == "AE"
    plugins = []
    for it in bring:
        for p in it["_v"]["plugins"]:
            if p.lower() not in {x.lower() for x in plugins}:
                plugins.append(p)
    have_lines = {x.lower() for x in st["ccc"]}
    lines = list(st["ccc"]) + [c for c in cc_added if c.lower() not in have_lines] + \
        ([K.USSEP_PLUGIN] if st["ussep"] else []) + [p for p in plugins if p.lower() not in have_lines]
    ccc_bytes = len(C.render(lines, "CRLF" if ae else "LF", True))
    base_bytes = len(C.render(list(st["ccc"]) + ([K.USSEP_PLUGIN] if st["ussep"] else []),
                              "CRLF" if ae else "LF", True))
    ccc = {"file": "Skyrim_aoc.ccc" if ae else "Plugins", "bytes": ccc_bytes, "base_bytes": base_bytes,
           "lines": len(lines), "cc_lines": sum(1 for e in lines if e.lstrip("#").lower().startswith("cc")),
           "limit": K.CCC_BYTE_LIMIT if ae else None, "warn": K.CCC_BYTE_WARN if ae else None,
           "status": "ok"}
    if ae and ccc_bytes > K.CCC_BYTE_LIMIT:
        ccc["status"] = "over"
        fix = ("Pick fewer plugins or shorter names.", "Elige menos plugins o nombres más cortos.")
        if (base.get("cc_preset") or "ussep") in ("all", "base") and not base.get("into"):
            light = list(K.USSEP_CC_MASTERS) + [c for c in cc_added if c not in K.USSEP_CC_MASTERS]
            saved = len(C.render(list(st["ccc"]), "CRLF", True)) - len(C.render(light, "CRLF", True))
            if saved > 0:
                fix = (f"Start from the 'ussep' Creation Club preset: it saves {saved} bytes.",
                       f"Usa el preset de Creation Club 'ussep': ahorra {saved} bytes.")
                suggestions.append({"code": "cc-preset", "cc_preset": "ussep", "saves": saved, "text": list(fix)})
        problems.append(_problem("ccc-over", "block",
                                 f"The load list would be {ccc_bytes} bytes; the limit is about {K.CCC_BYTE_LIMIT}.",
                                 f"La lista de carga quedaría en {ccc_bytes} bytes; el límite es de unos "
                                 f"{K.CCC_BYTE_LIMIT}.", fix=fix))
    elif ae and ccc_bytes > K.CCC_BYTE_WARN:
        ccc["status"] = "tight"
    # ini archive lists
    lists = {n: {k: list(v) for k, v in d.items()} for n, d in st["lists"].items()}
    missing_keys: set[str] = set()
    for it in bring:
        for key, names in (it["_v"].get("ini") or {}).items():
            targets = [n for n, d in lists.items() if key in d]
            if not targets:
                if key != MEMORY_KEY:
                    missing_keys.add(key)
                continue
            for n in targets:
                cur = lists[n][key]
                for b in names:
                    if b.lower() not in {c.lower() for c in cur}:
                        cur.append(b)
    inis = []
    for n, d in lists.items():
        for key, cur in d.items():
            chars = len(", ".join(cur))
            row = {"ini": n, "key": key, "chars": chars, "limit": ARCHIVE_LIST_LIMIT,
                   "entries": len(cur), "status": "ok" if chars <= ARCHIVE_LIST_LIMIT else "over"}
            if chars > ARCHIVE_LIST_LIMIT - 64 and row["status"] == "ok":
                row["status"] = "tight"
            inis.append(row)
            if row["status"] == "over":
                problems.append(_problem(
                    "ini-over", "block",
                    f"{key} in {n} would be {chars} characters; the limit is {ARCHIVE_LIST_LIMIT}.",
                    f"{key} en {n} quedaría en {chars} caracteres; el límite es {ARCHIVE_LIST_LIMIT}.",
                    fix=("Pick fewer mods with BSAs loaded from the ini, or shorten BSA names (Koka's tip: "
                         "'Mod - Meshes.bsa' to '1M.bsa').",
                         "Elige menos mods con BSA cargados desde el ini, o acorta nombres de BSA (consejo "
                         "de Koka: 'Mod - Meshes.bsa' a '1M.bsa')."), ini=n, key=key))
    for key in sorted(missing_keys):
        problems.append(_problem("ini-key-missing", "block",
                                 f"No base ini has {key}, so some BSAs wouldn't load.",
                                 f"Ningún ini base tiene {key}, así que algunos BSA no cargarían.", key=key))
    # BSAs, textures, size
    n_bsas = len(st["bsas"]) + sum(len(it["_v"]["bsas"]) for it in bring)
    tex = st["tex"] + sum(it["_v"]["tex_bytes"] or 0 for it in bring)
    unknown = [it["name"] for it in bring if it["_v"]["tex_bytes"] is None and it["_v"]["bsas"]]
    size = st["size"] + sum(it["_v"]["size"] or 0 for it in bring)
    lo, hi = RAM_FOR_MODS
    if tex > hi:
        status = "over"
        text = [f"Textures need about {tex / MB:.0f} MB; Koka measured only {lo // MB}-{hi // MB} MB left for "
                "mods on Switch. Expect crashes or missing textures.",
                f"Las texturas necesitan unos {tex / MB:.0f} MB; Koka midió que en la Switch quedan solo "
                f"{lo // MB}-{hi // MB} MB para mods. Puede cerrarse o faltar texturas."]
        big = sorted(bring, key=lambda it: -(it["_v"]["tex_bytes"] or 0))[:3]
        suggestions.append({"code": "textures", "remove": [_pick_ref(i["_e"], i["_v"]) for i in big], "text": [
            "The biggest textures: " + _and([f"{i['name']} ({(i['_v']['tex_bytes'] or 0) / MB:.0f} MB)" for i in big]),
            "Las texturas más grandes: " + _and([f"{i['name']} ({(i['_v']['tex_bytes'] or 0) / MB:.0f} MB)"
                                                 for i in big], True)]})
        problems.append(_problem("ram-over", "warn", *text))
    elif tex > lo:
        status = "tight"
        text = [f"Textures need about {tex / MB:.0f} MB, close to the {lo // MB}-{hi // MB} MB Koka measured "
                "for mods on Switch.",
                f"Las texturas necesitan unos {tex / MB:.0f} MB, cerca de los {lo // MB}-{hi // MB} MB que Koka "
                "midió para mods en la Switch."]
    else:
        status = "ok"
        text = [f"Textures need about {tex / MB:.0f} MB (Koka measured {lo // MB}-{hi // MB} MB left for mods "
                "on Switch).",
                f"Las texturas necesitan unos {tex / MB:.0f} MB (Koka midió {lo // MB}-{hi // MB} MB libres para "
                "mods en la Switch)."]
    return {"ccc": ccc, "inis": inis, "bsas": n_bsas, "plugins": len(plugins), "size": size,
            "tex_bytes": tex, "tex_unknown": unknown,
            "ram": {"tex_bytes": tex, "free_min": lo, "free_max": hi, "status": status, "text": text}}


# =================================================================== building
def execute_build(catalog: dict, picks: list[dict], base: dict, dest, progress=None,
                  force: bool = False) -> dict:
    """Create the new pack and bring the picks into it, pack by pack.
    Refuses when the plan has blocking problems, unless force=True."""
    from .builder import add_mod, create_project
    from .transfer import TransferError, apply_transfer, list_pack_mods, plan_transfer
    tick = _tick(progress)
    plan = plan_build(catalog, picks, base, progress)
    blocking = [p for p in plan["problems"] if p["severity"] == "block"]
    if blocking and not force:
        raise CatalogError(*blocking[0]["text"])
    if base.get("into"):
        dest = Path(base["into"])
    else:
        dest = Path(dest)
        create_project(dest, plan["edition"], Path(base["inis_dir"]), base.get("cc_preset") or "ussep",
                       lang=base.get("lang") or "en", ussep=base.get("ussep"),
                       ussep_dir=Path(base["ussep_dir"]) if base.get("ussep_dir") else None)
    report = {"ok": True, "dest": str(dest), "order": [o["pack"] for o in plan["order"]],
              "brought": [], "skipped": list(plan["skipped"]), "errors": [], "notes": [], "history": []}
    keys = {(it["pack_path"], it["unit_id"]): it for it in plan["items"]}
    for n, grp in enumerate(plan["order"]):
        tick(grp["pack"], n, len(plan["order"]))
        ids = [uid for uid in grp["picks"] if keys[(grp["pack_path"], uid)]["status"] == "bring"]
        if not ids:
            continue
        try:
            if grp["source_kind"] == "mod":
                rep = add_mod(Pack.open(dest), Path(grp["pack_path"]))
                if rep.history:
                    report["history"].append(rep.history)
                it = keys[(grp["pack_path"], ids[0])]
                report["brought"].append({"key": it["key"], "name": it["name"], "pack": grp["pack"],
                                          "unit_id": ids[0], "reason": "picked", "needed_by": [],
                                          "files": rep.added})
                report["notes"] += [list(x) for x in rep.notes]
                continue
            src = Pack.open(Path(grp["pack_path"]))
            units = list_pack_mods(src, progress=lambda *a, **k: tick(grp["pack"]))
            tp = plan_transfer(src, Pack.open(dest), ids, units=units, progress=lambda *a, **k: tick(grp["pack"]))
        except (TransferError, SkynxError) as e:
            report["errors"].append({"pack": grp["pack"], "text": [e.en, e.es]})
            continue
        except Exception as e:  # noqa: BLE001
            report["errors"].append({"pack": grp["pack"], "text": [str(e), str(e)]})
            continue
        for s in tp.skipped + tp.refused:
            report["skipped"].append({"pack": grp["pack"], "pack_path": grp["pack_path"], "unit_id": s["id"],
                                      "name": s["name"], "key": (keys.get((grp["pack_path"], s["id"])) or {}).get("key"),
                                      "reason": list(s["reason"])})
        if tp.errors or not tp.units:
            for e in tp.errors:
                report["errors"].append({"pack": grp["pack"], "text": list(e)})
            tp.cleanup()
            continue
        brought = [(b["unit"].id, "master" if b["reason"] == "master" else "picked", list(b["needed_by"]),
                    b["unit"].name) for b in tp.units]
        copies = {}
        for _s, d, uid in tp.copies:
            copies.setdefault(uid, []).append(d)
        try:
            rep = apply_transfer(tp, progress=lambda *a, **k: tick(grp["pack"]))
        except (TransferError, SkynxError) as e:
            report["errors"].append({"pack": grp["pack"], "text": [e.en, e.es]})
            continue
        if rep.get("history"):
            report["history"].append(rep["history"])
        report["notes"] += [list(x) for x in rep.get("notes", [])]
        for uid, reason, needed_by, name in brought:
            it = keys.get((grp["pack_path"], uid))
            report["brought"].append({"key": it["key"] if it else None, "name": it["name"] if it else name,
                                      "pack": grp["pack"], "unit_id": uid, "reason": reason,
                                      "needed_by": needed_by, "files": copies.get(uid, [])})
    report["ok"] = not report["errors"]
    report["budget"] = measure(Pack.open(dest), plan)
    return report


def measure(pack: Pack, plan: dict | None = None) -> dict:
    """The budget of a pack on disk (after building)."""
    raw = pack.list_path.read_bytes() if pack.list_path and pack.list_path.exists() else b""
    ae = pack.mode == "AE"
    inis = []
    for ini in pack.inis:
        for key in ARCHIVE_KEYS:
            if ini.get("Archive", key) is not None:
                chars = len(", ".join(ini.archive_list(key)))
                inis.append({"ini": ini.path.name, "key": key, "chars": chars, "limit": ARCHIVE_LIST_LIMIT,
                             "status": "over" if chars > ARCHIVE_LIST_LIMIT else "ok"})
    out = {"ccc": {"file": pack.list_path.name if pack.list_path else None, "bytes": len(raw),
                   "lines": len(C.parse_ccc(raw).entries) if raw else 0,
                   "limit": K.CCC_BYTE_LIMIT if ae else None,
                   "status": "over" if ae and len(raw) > K.CCC_BYTE_LIMIT else
                   ("tight" if ae and len(raw) > K.CCC_BYTE_WARN else "ok")},
           "inis": inis, "bsas": len(pack.bsas), "plugins": len(pack.plugins),
           "size": pack.data_size()}
    if plan is not None:
        out["tex_bytes"] = plan["budget"]["tex_bytes"]
        out["ram"] = plan["budget"]["ram"]
    return out
