"""Suggest a load order the way LOOT does, from the official LOOT masterlist.

Source: github.com/loot/skyrimse, file masterlist.yaml, on the branch LOOT
itself reads (MASTERLIST_BRANCH). The syntax follows the LOOT metadata docs
(loot-api.readthedocs.io, "Metadata syntax"):

* `groups`: each group loads after the groups in its `after` list, transitively.
  A plugin with no group is in "default".
* `plugins`: `name` is a regex (whole name, case-insensitive) when it contains
  any of `:\\*?|`, otherwise an exact filename. A plugin's metadata is its exact
  entry merged with every regex entry that matches it.
* `after` and `req` mean "load after"; `req` also means "must be present".
  `inc` lists incompatible files. Items are a string or {name, display, condition}.
* `msg`: {type: say|warn|error, content (string or [{lang, text}]), subs, condition}.
* YAML anchors and merge keys (`<<:`) are resolved by the YAML loader.

What applies to the pack's load list (Skyrim_aoc.ccc in AE, `Plugins` in SE):

Fixed lines never move: vanilla masters, Hyrule.esm and, in AE, the Creation
Club entries. Disabled '#' lines, duplicates and entries whose file is missing
are "passengers": they stay right after the line they follow.

Hard rules, strongest first; a weaker rule that would contradict a stronger
one is dropped and reported:
  1. every plugin after its masters;
  2. master-flagged plugins (ESM flag, .esm or .esl) before the rest; a
     regular plugin that is a master of one of them goes with them;
  3. LOOT groups;
  4. masterlist `after` / `req` rules.
(Real LOOT puts rule 4 above rule 3; see AFTER_BEATS_GROUPS.)

Inside those rules the current order is kept as much as possible: a stable
topological sort that always takes the available plugin that is highest in
the current list. Sorting an already sorted list changes nothing.

Merged plugins (Merge Plugins, zMerge, the xEdit merge script) list what they
contain in the TES4 description ("Merged Plugin:" then one name per line).
For LOOT a merge is the union of its components: the latest of their groups,
their `after`/`req` rules and their notes (prefixed with the component name).
Rules that other plugins have about a component apply to the merge. Empty
plugins kept with a component's name so patches still find their master are
placeholders: they keep their master constraints and get no notes.

User choices (`load_userlist`) work like LOOT's userlist, in a small JSON
file: a chosen group replaces the masterlist group, `after` adds rules that
win over groups (not over masters or ESM flags).

Plugins LOOT doesn't know get a guessed group (`guess_group`) from cheap
evidence: masters, name, and the record types and new/override split.

Not done (real LOOT does them): record-overlap and asset-overlap ordering,
plugin CRC / version checks in conditions, Bash tags, dirty-plugin checks.
"""
from __future__ import annotations

import json
import mmap
import os
import re
import struct
import time
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from . import knowledge as K
from .errors import SkynxError
from .plugin import PluginHeader, _zstr, read_header

MASTERLIST_BRANCH = "v0.29"     # loot/skyrimse default branch, checked Oct 2026
MASTERLIST_URL = ("https://raw.githubusercontent.com/loot/skyrimse/"
                  f"{MASTERLIST_BRANCH}/masterlist.yaml")
USER_AGENT = "SwitchNX Studio"
CACHE_NAME = "masterlist.yaml"

# Real LOOT adds load-after/requirement edges before group edges, so a
# specific `after` rule wins over a group. The spec for this module ranks
# groups above `after`. Flip this to get LOOT's behaviour.
AFTER_BEATS_GROUPS = False

PLUGIN_EXT = (".esp", ".esm", ".esl")
_REGEX_CHARS = re.compile(r"[:\\*?|]")
_FIXED_NAMES = {n.lower() for n in K.VANILLA_MASTERS + K.SWITCH_MASTERS}
_CC_NAMES = {n.lower() for n in K.AE_CC_PLUGINS}


# ---------------------------------------------------------------------------
# Masterlist
# ---------------------------------------------------------------------------
class FileRef(NamedTuple):
    name: str
    display: str
    condition: str


class Message(NamedTuple):
    type: str            # say / warn / error
    en: str
    es: str              # the masterlist's Spanish text, or the English one
    condition: str


@dataclass
class PluginMeta:
    name: str
    group: str | None = None
    after: list[FileRef] = field(default_factory=list)
    req: list[FileRef] = field(default_factory=list)
    inc: list[FileRef] = field(default_factory=list)
    msg: list[Message] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)       # the mod's pages (often Nexus)
    url_names: dict[str, str] = field(default_factory=dict)   # page -> mod title, when the masterlist says

    def merge(self, other: "PluginMeta") -> None:
        if self.group is None:
            self.group = other.group
        self.urls.extend(u for u in other.urls if u not in self.urls)
        for k, v in other.url_names.items():
            self.url_names.setdefault(k, v)
        for attr in ("after", "req", "inc"):
            mine = getattr(self, attr)
            seen = {f.name.lower() for f in mine}
            mine.extend(f for f in getattr(other, attr) if f.name.lower() not in seen)
        self.msg.extend(other.msg)


def _fold1(name: str) -> str:
    """Google Drive turns apostrophes into '_': Ryn's == Ryn_s."""
    return name.lower().replace("’", "'").replace("'", "_")


def _fold2(name: str) -> str:
    """Last resort, used only when it matches one name: ignore apostrophes,
    underscores and spaces (Ryns == Ryn's, Alternate_Start == Alternate Start)."""
    return re.sub(r"['_’\s]", "", name.lower())


def _is_regex(name: str) -> bool:
    return bool(_REGEX_CHARS.search(name))


def _compile(pattern: str) -> re.Pattern | None:
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error:
        return None


def _text(content, lang: str) -> str:
    if isinstance(content, list):
        by = {str(c.get("lang", "")).lower(): str(c.get("text", "")) for c in content
              if isinstance(c, dict)}
        return by.get(lang) or by.get("en") or next(iter(by.values()), "")
    return str(content or "")


_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def _plain(s: str) -> str:
    """Markdown to short plain text: links as 'text (url)', no bold."""
    s = _MD_LINK.sub(lambda m: m.group(1) if m.group(1) == m.group(2)
                     else f"{m.group(1)} ({m.group(2)})", s)
    return s.replace("**", "").replace("__", "").strip()


def _subs(s: str, subs) -> str:
    for i, v in enumerate(subs or []):
        s = s.replace("{%d}" % i, str(v))
    return s


def _fileref(x) -> FileRef | None:
    if isinstance(x, str):
        return FileRef(x, "", "")
    if isinstance(x, dict) and x.get("name"):
        return FileRef(str(x["name"]), _plain(str(x.get("display") or "")),
                       str(x.get("condition") or ""))
    return None


def _meta(raw: dict) -> PluginMeta:
    m = PluginMeta(str(raw["name"]), raw.get("group"))
    for u in raw.get("url") or []:
        link = u.get("link") if isinstance(u, dict) else u
        if isinstance(link, str) and link.startswith("http") and link not in m.urls:
            m.urls.append(link)
            if isinstance(u, dict) and u.get("name"):
                m.url_names[link] = str(u["name"])
    for attr in ("after", "req", "inc"):
        items = raw.get(attr) or []
        getattr(m, attr).extend(f for f in map(_fileref, items) if f)
    for x in raw.get("msg") or []:
        if not isinstance(x, dict):
            continue
        en = _plain(_subs(_text(x.get("content"), "en"), x.get("subs")))
        es = _plain(_subs(_text(x.get("content"), "es"), x.get("subs")))
        m.msg.append(Message(str(x.get("type", "say")), en, es or en,
                             str(x.get("condition") or "")))
    return m


@dataclass
class Masterlist:
    path: Path | None
    groups: dict[str, list[str]]                 # group -> groups it loads after
    exact: dict[str, PluginMeta]                 # lower name -> metadata
    regex: list[tuple[re.Pattern, PluginMeta]]
    bad_regex: list[str] = field(default_factory=list)
    _f1: dict[str, str] = field(default_factory=dict, repr=False)
    _f2: dict[str, str | None] = field(default_factory=dict, repr=False)
    _order: list[str] = field(default_factory=list, repr=False)

    def __post_init__(self):
        for low in self.exact:
            self._f1.setdefault(_fold1(low), low)
            k = _fold2(low)
            self._f2[k] = None if k in self._f2 and self._f2[k] != low else low
        self._anc: dict[str, set[str]] = {}

    def group_ancestors(self, group: str) -> set[str]:
        """Every group that `group` loads after, transitively."""
        if group not in self._anc:
            out, stack = set(), list(self.groups.get(group, []))
            while stack:
                g = stack.pop()
                if g not in out and g != group:
                    out.add(g)
                    stack.extend(self.groups.get(g, []))
            self._anc[group] = out
        return self._anc[group]

    def _exact_key(self, name: str) -> str | None:
        low = name.lower()
        return (low if low in self.exact else self._f1.get(_fold1(low))
                or self._f2.get(_fold2(low)))

    def knows_exact(self, *names: str) -> bool:
        """True when one of `names` has its own entry (regex entries don't count)."""
        return any(n and self._exact_key(n) is not None for n in names)

    def lookup(self, *names: str) -> PluginMeta | None:
        """Metadata for the first of `names` that the masterlist knows,
        merged with every matching regex entry. Tolerates Drive damage."""
        for name in names:
            if not name:
                continue
            key = self._exact_key(name)
            variants = {name, name.replace("_", "'")}
            hits = [m for rx, m in self.regex if any(rx.fullmatch(v) for v in variants)]
            if key is None and not hits:
                continue
            out = PluginMeta(name)
            if key is not None:
                out.merge(self.exact[key])
            for m in hits:
                out.merge(m)
            return out
        return None


def load_masterlist(path: Path) -> Masterlist:
    """Parse a LOOT masterlist.yaml. Results are cached per file and mtime."""
    path = Path(path)
    try:
        st = path.stat()
        ck = (str(path.resolve()), st.st_mtime_ns, st.st_size)
    except OSError as e:
        raise SkynxError(f"Can't read the LOOT masterlist: {e}",
                         f"No se puede leer la masterlist de LOOT: {e}") from e
    if ck in _CACHE:
        return _CACHE[ck]
    try:
        import yaml
    except ImportError as e:     # pragma: no cover
        raise SkynxError("PyYAML is missing (pip install pyyaml).",
                         "Falta PyYAML (pip install pyyaml).") from e
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.load(f, Loader=loader)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        raise SkynxError(f"The LOOT masterlist is damaged: {e}",
                         f"La masterlist de LOOT está dañada: {e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("plugins"), list):
        raise SkynxError("The file is not a LOOT masterlist (no 'plugins').",
                         "El archivo no es una masterlist de LOOT (no tiene 'plugins').")
    groups: dict[str, list[str]] = {"default": []}
    for g in data.get("groups") or []:
        if isinstance(g, dict) and g.get("name"):
            groups[str(g["name"])] = [str(a) for a in g.get("after") or []]
    exact: dict[str, PluginMeta] = {}
    regex: list[tuple[re.Pattern, PluginMeta]] = []
    bad: list[str] = []
    for raw in data["plugins"]:
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        m = _meta(raw)
        if _is_regex(m.name):
            rx = _compile(m.name)
            if rx is None:
                bad.append(m.name)
            else:
                regex.append((rx, m))
        elif m.name.lower() in exact:
            exact[m.name.lower()].merge(m)
        else:
            exact[m.name.lower()] = m
    ml = Masterlist(path, groups, exact, regex, bad)
    _CACHE.clear()
    _CACHE[ck] = ml
    return ml


_CACHE: dict[tuple, Masterlist] = {}


def _looks_like_masterlist(data: bytes) -> bool:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return "\nplugins:" in text and "\ngroups:" in text and len(data) > 10_000


def fetch_masterlist(cache_dir: Path, url: str = MASTERLIST_URL,
                     timeout: float = 30) -> Path:
    """Download the masterlist into cache_dir and return its path.

    If the download fails, the copy already in cache_dir is kept and
    returned. Raises SkynxError only when there is no copy at all.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    dst = cache_dir / CACHE_NAME
    tmp = cache_dir / (CACHE_NAME + ".part")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
        if not _looks_like_masterlist(data):
            raise ValueError("downloaded file is not a LOOT masterlist")
        tmp.write_bytes(data)
        os.replace(tmp, dst)
        return dst
    except Exception as e:      # network, HTTP, disk: fall back to the old copy
        try:
            tmp.unlink()
        except OSError:
            pass
        if dst.exists():
            return dst
        raise SkynxError(f"Couldn't download the LOOT masterlist: {e}",
                         f"No se pudo descargar la masterlist de LOOT: {e}") from e


def masterlist_age_days(path: Path) -> float:
    return (time.time() - Path(path).stat().st_mtime) / 86400


def all_groups(masterlist: Masterlist) -> list[str]:
    """Every group in load order (each after the groups it loads after).
    Ties keep the masterlist's order, so the result is stable."""
    if masterlist._order:
        return list(masterlist._order)
    names = list(masterlist.groups)
    decl = {g: i for i, g in enumerate(names)}
    deps = {g: {a for a in masterlist.groups[g] if a in decl and a != g} for g in names}
    out: list[str] = []
    done: set[str] = set()
    while len(out) < len(names):
        ready = [g for g in names if g not in done and deps[g] <= done]
        if not ready:                                    # a cycle: keep declaration order
            ready = [g for g in names if g not in done]
        g = min(ready, key=decl.__getitem__)
        out.append(g)
        done.add(g)
    masterlist._order = out
    return list(out)


def _group_index(masterlist: Masterlist) -> dict[str, int]:
    return {g: i for i, g in enumerate(all_groups(masterlist))}


# ---------------------------------------------------------------------------
# Merged plugins
# ---------------------------------------------------------------------------
_MERGE_MARK = re.compile(r"merged\s+(?:plugin|file|esp)s?\b\s*[:\-]?", re.IGNORECASE)
_BULLETS = " \t-*•·>"


def _is_plugin_name(s: str) -> bool:
    return 4 < len(s) < 200 and s.lower().endswith(PLUGIN_EXT)


def _components_from(author: str, description: str, own: str = "") -> list[str]:
    """Components listed in a merged plugin's description, [] if it isn't one.

    Accepts the "Merged Plugin:" marker with any newline style, names on the
    marker line or one per line (comma / semicolon lists too). Without the
    marker, an author naming a merge tool (zMerge, Merge Plugins) and a
    description made only of plugin names also counts.
    """
    text = description or ""
    m = _MERGE_MARK.search(text)
    if m:
        body, strict = text[m.end():], False
    elif "merge" in (author or "").lower():
        body, strict = text, True
    else:
        return []
    out: list[str] = []
    seen = {own.lower()} if own else set()
    for raw in re.split(r"[\r\n]+", body):
        line = raw.strip().strip(_BULLETS).strip()
        if not line:
            continue
        pieces = [p.strip().strip(_BULLETS).strip() for p in re.split(r"[,;|]", line)]
        pieces = [p for p in pieces if p]
        if len(pieces) > 1 and all(_is_plugin_name(p) for p in pieces):
            names = pieces
        elif _is_plugin_name(line):
            names = [line]
        elif strict:
            return []                       # prose: not a bare list of plugins
        elif out:
            break                           # the list ended; the rest is free text
        else:
            continue
        for n in names:
            if n.lower() not in seen:
                seen.add(n.lower())
                out.append(n)
    if strict and len(out) < 2:
        return []
    return out


def _tes4_text(raw: bytes) -> tuple[str, str]:
    """(author, description) from a plugin's bytes."""
    if raw[:4] != b"TES4" or len(raw) < 24:
        return "", ""
    dsize = struct.unpack_from("<I", raw, 4)[0]
    data = raw[24:24 + dsize]
    author = desc = ""
    i, big = 0, None
    while i + 6 <= len(data):
        st, ss = struct.unpack_from("<4sH", data, i)
        i += 6
        if big is not None:
            ss, big = big, None
        payload = data[i:i + ss]
        i += ss
        if st == b"XXXX" and len(payload) >= 4:
            big = struct.unpack_from("<I", payload)[0]
        elif st == b"CNAM":
            author = _zstr(payload)
        elif st == b"SNAM":
            desc = _zstr(payload)
    return author, desc


def merged_components(src) -> list[str]:
    """Plugins merged into this one (Merge Plugins / zMerge), [] if it isn't a merge.
    `src` is a path, the plugin's bytes, or a PluginHeader. Game masters are
    never treated as merged in."""
    base = {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS}
    return [c for c in _merged_components(src) if c.lower() not in base]


# Switch-only plugins LOOT doesn't know, with the group they belong in.
# Used like a userlist entry the user hasn't overridden.
BUILTIN_GROUPS = {
    "unofficial skyrim nx patch.esp": ("Unofficial Skyrim NX Patch.esp", "Unofficial Patches"),
}


def _merged_components(src) -> list[str]:
    if isinstance(src, PluginHeader):
        return _components_from(src.author, src.description, src.name)
    if isinstance(src, (bytes, bytearray, memoryview)):
        return _components_from(*_tes4_text(bytes(src)))
    try:
        h = read_header(Path(src))
    except OSError:
        return []
    return _components_from(h.author, h.description, h.name)


# ---------------------------------------------------------------------------
# User choices (like LOOT's userlist)
# ---------------------------------------------------------------------------
USERLIST_VERSION = 1


def _normalize_userlist(raw) -> dict:
    plugins = raw.get("plugins") if isinstance(raw, dict) else None
    out: dict[str, dict] = {}
    for key, e in (plugins or {}).items() if isinstance(plugins, dict) else ():
        if not isinstance(e, dict):
            continue
        name = str(e.get("name") or key).strip()
        group = str(e.get("group") or "").strip()
        after = e.get("after") or []
        if isinstance(after, str):
            after = [after]
        after = [str(a).strip() for a in after if str(a).strip()]
        after = [a for i, a in enumerate(after) if a.lower() not in {b.lower() for b in after[:i]}]
        note = str(e.get("note") or "").strip()
        if name and (group or after or note):
            out[name.lower()] = {"name": name, "group": group, "after": after, "note": note}
    return {"version": USERLIST_VERSION, "plugins": out}


def load_userlist(path: Path) -> dict:
    """The user's choices: {"version": 1, "plugins": {lower name: {"name",
    "group", "after", "note"}}}. A missing file is an empty list."""
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"version": USERLIST_VERSION, "plugins": {}}
    except (OSError, ValueError) as e:
        raise SkynxError(f"Can't read your load order choices ({path.name}): {e}",
                         f"No se pueden leer tus elecciones de orden ({path.name}): {e}") from e
    return _normalize_userlist(raw)


def save_userlist(path: Path, data: dict) -> dict:
    """Write the choices atomically; returns the normalized data written."""
    path = Path(path)
    clean = _normalize_userlist(data)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".part")
        tmp.write_text(json.dumps(clean, indent=2, ensure_ascii=False, sort_keys=True),
                       encoding="utf-8")
        os.replace(tmp, path)
    except OSError as e:
        raise SkynxError(f"Can't save your load order choices: {e}",
                         f"No se pueden guardar tus elecciones de orden: {e}") from e
    return clean


def userlist_set(data: dict, name: str, group: str | None = None,
                 after: list[str] | None = None, note: str | None = None) -> dict:
    """Change one plugin's choices in `data` (None keeps a field, "" / [] clear it).
    An entry left with nothing is removed. Returns the normalized data."""
    data = _normalize_userlist(data)
    cur = data["plugins"].get(name.lower(), {"name": name, "group": "", "after": [], "note": ""})
    cur = dict(cur, name=name)
    if group is not None:
        cur["group"] = group
    if after is not None:
        cur["after"] = list(after)
    if note is not None:
        cur["note"] = note
    data["plugins"][name.lower()] = cur
    return _normalize_userlist(data)


def _user_index(userlist: dict | None) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for low, e in _normalize_userlist(userlist or {})["plugins"].items():
        idx.setdefault(low, e)
        idx.setdefault(_fold1(low), e)
    for low, (name, group) in BUILTIN_GROUPS.items():
        if low not in idx:
            e = {"name": name, "group": group, "after": [], "note": "built-in"}
            idx[low] = e
            idx.setdefault(_fold1(low), e)
    return idx


# ---------------------------------------------------------------------------
# Groups for people who aren't LOOT experts
# ---------------------------------------------------------------------------
FRIENDLY_GROUPS: list[dict[str, str]] = [
    {"group": "Fixes", "en": "Fixes", "es": "Correcciones",
     "en_help": "Bug fixes for the base game. They load early.",
     "es_help": "Arreglos de errores del juego base. Cargan temprano."},
    {"group": "Resources & Frameworks", "en": "Resources & frameworks", "es": "Recursos y frameworks",
     "en_help": "Shared resources and frameworks that other mods build on.",
     "es_help": "Recursos y frameworks compartidos que usan otros mods."},
    {"group": "New Content", "en": "New content only", "es": "Solo contenido nuevo",
     "en_help": "Mods that only add new places, items or characters and change nothing else.",
     "es_help": "Mods que solo agregan lugares, objetos o personajes nuevos y no cambian nada más."},
    {"group": "default", "en": "General / most mods", "es": "General / la mayoría de mods",
     "en_help": "Where LOOT puts most mods. The safe choice when unsure.",
     "es_help": "Donde LOOT pone la mayoría de los mods. La opción segura si hay dudas."},
    {"group": "Races & Classes", "en": "Races & classes", "es": "Razas y clases",
     "en_help": "Overhauls of the playable races or classes.",
     "es_help": "Cambios grandes a las razas jugables o a las clases."},
    {"group": "Skills & Perks", "en": "Skills & perks", "es": "Habilidades y perks",
     "en_help": "Perk trees and skill overhauls (like Ordinator).",
     "es_help": "Árboles de perks y cambios a las habilidades (como Ordinator)."},
    {"group": "High Priority Overrides", "en": "High priority overrides", "es": "Cambios de alta prioridad",
     "en_help": "Mods whose changes must win over almost every other mod.",
     "es_help": "Mods cuyos cambios deben ganarle a casi todos los demás."},
    {"group": "Conflict Resolution Patches (Late)", "en": "Conflict resolution patches",
     "es": "Parches de conflictos",
     "en_help": "Patches that settle conflicts between many mods. They load near the end.",
     "es_help": "Parches que resuelven conflictos entre muchos mods. Cargan casi al final."},
]


# ---------------------------------------------------------------------------
# Guessing a group for plugins LOOT doesn't know
# ---------------------------------------------------------------------------
_USSEP = "unofficial skyrim special edition patch.esp"
_CC_RX = re.compile(r"^cc[a-z]{3}sse\d{3}", re.IGNORECASE)
_PARENTS = {"CELL", "WRLD", "LAND", "NAVM", "NAVI"}      # overridden to place things in them
_PLACED = {"REFR", "ACHR", "PGRE", "PHZD", "NAVM", "LAND"}
_WALK_LIMIT = 400_000
_STATS: dict[tuple, dict | None] = {}
_TYPE_WORDS = {
    "WRLD": ("worldspaces", "espacios de mundo"), "CELL": ("cells", "celdas"),
    "NPC_": ("characters", "personajes"), "ARMO": ("armor", "armaduras"),
    "ARMA": ("armor models", "modelos de armadura"), "WEAP": ("weapons", "armas"),
    "QUST": ("quests", "misiones"), "DIAL": ("dialogue", "diálogos"), "INFO": ("dialogue", "diálogos"),
    "DLBR": ("dialogue", "diálogos"), "DLVW": ("dialogue", "diálogos"),
    "PACK": ("AI packages", "paquetes de IA"), "SMQN": ("quest triggers", "disparadores de misiones"),
    "IDLE": ("animations", "animaciones"), "MOVT": ("movement settings", "ajustes de movimiento"),
    "ARTO": ("art objects", "objetos de arte"), "SNDR": ("sounds", "sonidos"), "SOUN": ("sounds", "sonidos"),
    "TXST": ("texture sets", "juegos de texturas"), "OTFT": ("outfits", "atuendos"),
    "LVLN": ("leveled lists", "listas niveladas"), "KYWD": ("keywords", "palabras clave"),
    "CONT": ("containers", "contenedores"), "FACT": ("factions", "facciones"),
    "LIGH": ("lights", "luces"), "ENCH": ("enchantments", "encantamientos"),
    "SPGD": ("rain and snow effects", "efectos de lluvia y nieve"), "IMGS": ("image effects", "efectos de imagen"),
    "HDPT": ("hair and head parts", "peinados y partes de la cabeza"), "BOOK": ("books", "libros"),
    "REFR": ("placed objects", "objetos colocados"), "ACHR": ("placed characters", "personajes colocados"),
    "SPEL": ("spells", "hechizos"), "MGEF": ("magic effects", "efectos mágicos"),
    "COBJ": ("crafting recipes", "recetas de fabricación"), "LVLI": ("leveled lists", "listas niveladas"),
    "PERK": ("perks", "perks"), "RACE": ("races", "razas"), "ACTI": ("activators", "activadores"),
    "MISC": ("items", "objetos"), "STAT": ("static objects", "objetos estáticos"),
    "GLOB": ("settings", "variables"), "MESG": ("messages", "mensajes"), "FLST": ("lists", "listas"),
    "WTHR": ("weather", "clima"), "CLMT": ("climates", "climas"),
    "LAND": ("terrain", "terreno"), "NAVM": ("navmeshes", "navmesh"), "GMST": ("game settings", "ajustes del juego"),
}


def _is_base(name: str) -> bool:
    """Game files every pack has: vanilla, Hyrule, Creation Club, USSEP."""
    low = name.lower()
    return low in _FIXED_NAMES or low in _CC_NAMES or bool(_CC_RX.match(low)) or low == _USSEP


def _record_stats(path: Path, n_masters: int) -> dict | None:
    """New / override record counts by type, from the record headers only."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (str(path), st.st_mtime_ns, st.st_size, n_masters)
    if key in _STATS:
        return _STATS[key]
    new, ovr = Counter(), Counter()
    out = None
    try:
        with open(path, "rb") as f:
            if st.st_size >= 24:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    if mm[:4] == b"TES4":
                        pos = 24 + struct.unpack_from("<I", mm, 4)[0]
                        end, count = len(mm), 0
                        while pos + 24 <= end and count < _WALK_LIMIT:
                            typ = mm[pos:pos + 4]
                            if typ == b"GRUP":
                                if struct.unpack_from("<I", mm, pos + 4)[0] < 24:
                                    break                     # damaged
                                pos += 24                     # step inside the group
                                continue
                            dsize, _flags, fid = struct.unpack_from("<III", mm, pos + 4)
                            (new if fid >> 24 >= n_masters else ovr)[typ.decode("latin-1")] += 1
                            count += 1
                            pos += 24 + dsize
                        out = {"new": new, "ovr": ovr, "total": count}
    except (OSError, ValueError, struct.error):
        out = None
    _STATS[key] = out
    return out


def _words(counter: Counter, n: int = 3) -> tuple[str, str]:
    en, es = [], []
    for typ, _c in counter.most_common():
        w = _TYPE_WORDS.get(typ, (typ, typ))
        if w[0] not in en:
            en.append(w[0])
            es.append(w[1])
        if len(en) == n:
            break
    return ", ".join(en), ", ".join(es)


def _and(names: list[str], es: bool = False) -> str:
    if len(names) <= 1:
        return "".join(names)
    shown = names[:3]
    tail = f" (+{len(names) - 3})" if len(names) > 3 else ""
    return ", ".join(shown[:-1]) + (" y " if es else " and ") + shown[-1] + tail


def guess_group(path: Path, pack=None) -> tuple[str, tuple[str, str]]:
    """A LOOT group for a plugin the masterlist doesn't know, with the reason
    (English, Spanish). Conservative: LOOT itself puts most mods in 'default'."""
    path = Path(path)
    name = path.name
    h = None
    if pack is not None:
        h = (getattr(pack, "plugins", {}) or {}).get(name.lower())
    if h is None:
        try:
            h = read_header(path)
        except OSError:
            h = None
    if h is None:
        return "default", ("Couldn't read the plugin; 'default' is the safe choice.",
                           "No se pudo leer el plugin; 'default' es la opción segura.")
    low = name.lower()
    mods = [m for m in h.masters if not _is_base(m)]
    patchy = bool(re.search(r"patch|compat|fix", low))

    if h.num_records == 0 and not h.error:
        bsas = [b.name for b in pack.bsas_for_plugin(name)] if pack is not None and hasattr(
            pack, "bsas_for_plugin") else []
        if bsas:
            return "default", (
                f"Empty plugin that only loads {_and(bsas)}. Put it after the mods whose "
                "textures or meshes it should replace.",
                f"Plugin vacío que solo carga {_and(bsas, True)}. Va después de los mods cuyas "
                "texturas o modelos debe reemplazar.")
        return "default", ("Empty plugin (no records); its place doesn't change any record.",
                           "Plugin vacío (sin registros); su posición no cambia ningún registro.")
    if len(mods) >= 2:
        return "default", (
            f"Patch between {_and(mods)}: its masters already make it load after them. "
            "LOOT keeps patches like this in 'default'.",
            f"Parche entre {_and(mods, True)}: sus masters ya hacen que cargue después de ellos. "
            "LOOT deja este tipo de parches en 'default'.")
    if mods and patchy:
        return "default", (
            f"Patch for {mods[0]}, its master, so it already loads after it. "
            "LOOT keeps most patches in 'default'.",
            f"Parche para {mods[0]}, su master, así que ya carga después. "
            "LOOT deja la mayoría de los parches en 'default'.")
    if mods:
        return "default", (
            f"Uses {mods[0]} as a master, so it already loads after it. 'default' like most mods.",
            f"Usa {mods[0]} como master, así que ya carga después. 'default' como la mayoría.")
    if patchy:
        cc = [m for m in h.masters if _is_base(m) and m.lower() not in _FIXED_NAMES]
        if cc:
            return "default", (
                f"Its name says it's a patch, and it builds on {_and(cc)}. "
                "LOOT keeps most patches in 'default'.",
                f"Su nombre dice que es un parche, y se apoya en {_and(cc, True)}. "
                "LOOT deja la mayoría de los parches en 'default'.")
        return "default", (
            "Its name says it's a patch or fix for the base game. LOOT keeps most of these in 'default'.",
            "Su nombre dice que es un parche o arreglo del juego base. LOOT deja la mayoría en 'default'.")

    s = _record_stats(path, len(h.masters))
    if not s or not s["total"]:
        return "default", ("No clear signal (records couldn't be read).",
                           "Sin señales claras (no se pudieron leer los registros).")
    new, ovr, total = s["new"], s["ovr"], s["total"]
    both = new + ovr
    n_new = sum(new.values())
    pct_new = round(100 * n_new / total)
    for typ, group, en_w, es_w, least in (("RACE", "Races & Classes", "races", "razas", 3),
                                          ("PERK", "Skills & Perks", "perks", "perks", 5)):
        if both[typ] >= least and both[typ] >= 0.25 * total:
            return group, (
                f"{both[typ]} of its {total} records are {en_w}; LOOT puts mods like this in '{group}'.",
                f"{both[typ]} de sus {total} registros son {es_w}; LOOT pone mods así en '{group}'.")
    dependents = [p.name for p in (getattr(pack, "plugins", {}) or {}).values()
                  if any(m.lower() == low for m in p.masters)] if pack is not None else []
    real_ovr = sum(c for t, c in ovr.items() if t not in _PARENTS)
    parent_ovr = sum(c for t, c in ovr.items() if t in _PARENTS)
    only_new = total >= 20 and real_ovr <= 0.03 * total and parent_ovr <= 0.10 * total
    lands = sum(c for t, c in new.items() if t in _PLACED or t in ("CELL", "WRLD"))
    if only_new and (h.is_master_flag or low.endswith(".esm")) and dependents and lands < 0.3 * n_new:
        return "Resources & Frameworks", (
            f"Master file that only adds new records and that {_and(sorted(dependents))} build on.",
            f"Archivo master que solo agrega registros nuevos y que usan {_and(sorted(dependents), True)}.")
    placed = sum(c for t, c in new.items() if t in _PLACED)
    if only_new and placed >= 0.5 * n_new and new["CELL"] < ovr["CELL"]:
        return "default", (
            f"Mostly adds objects to existing places ({placed} placed records in {ovr['CELL']} "
            "existing cells). Not a pure 'New Content' mod, so 'default'.",
            f"Sobre todo agrega objetos a lugares que ya existen ({placed} registros colocados en "
            f"{ovr['CELL']} celdas existentes). No es solo contenido nuevo, así que 'default'.")
    if only_new:
        en_w, es_w = _words(new)
        return "New Content", (
            f"Only adds new records ({pct_new}% new: {en_w}) and uses only the base game as master. "
            "'New Content' loads before 'default', so other mods can still change these records.",
            f"Solo agrega registros nuevos ({pct_new}% nuevos: {es_w}) y su único master es el juego base. "
            "'New Content' carga antes de 'default', así que otros mods aún pueden cambiarlos.")
    if total < 20:
        rec_en, rec_es = ("record", "registro") if total == 1 else ("records", "registros")
        return "default", (f"Small plugin ({total} {rec_en}), no clear signal.",
                           f"Plugin pequeño ({total} {rec_es}), sin señales claras.")
    if n_new < 0.5 * total:
        en_w, es_w = _words(ovr)
        return "default", (
            f"Mostly changes existing records ({100 - pct_new}%: {en_w}). LOOT puts most mods like this in 'default'.",
            f"Sobre todo cambia registros existentes ({100 - pct_new}%: {es_w}). LOOT pone casi todos estos en 'default'.")
    return "default", (f"Adds and changes records ({pct_new}% new), no clear signal.",
                       f"Agrega y cambia registros ({pct_new}% nuevos), sin señales claras.")


# ---------------------------------------------------------------------------
# Conditions (a subset of the LOOT condition language, three-valued)
# ---------------------------------------------------------------------------
_TOKEN = re.compile(r'\s*(?:(\()|(\))|(,)|"([^"]*)"|([A-Za-z_]+)|([<>=!]=?|[0-9A-Fa-f.]+))')


class _Unknown(Exception):
    pass


class _Cond:
    """Evaluates conditions against the pack. Returns True, False or None
    (can't tell: CRCs, versions, files that may be inside a BSA)."""

    def __init__(self, ctx: "_Ctx"):
        self.ctx = ctx
        self.cache: dict[str, bool | None] = {}

    def __call__(self, cond: str) -> bool | None:
        if not cond:
            return True
        if cond not in self.cache:
            try:
                self.toks = self._lex(cond)
                self.i = 0
                v = self._or()
                if self.i != len(self.toks):
                    raise _Unknown
                self.cache[cond] = v
            except (_Unknown, IndexError, re.error):
                self.cache[cond] = None
        return self.cache[cond]

    @staticmethod
    def _lex(s: str) -> list[tuple[str, str]]:
        out, i = [], 0
        while i < len(s):
            if s[i].isspace():
                i += 1
                continue
            m = _TOKEN.match(s, i)
            if not m or m.end() == i:
                raise _Unknown
            i = m.end()
            if m.group(1): out.append(("(", "("))
            elif m.group(2): out.append((")", ")"))
            elif m.group(3): out.append((",", ","))
            elif m.group(4) is not None: out.append(("str", m.group(4)))
            elif m.group(5): out.append(("word", m.group(5)))
            else: out.append(("atom", m.group(6)))
        return out

    def _peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def _take(self, kind=None, value=None):
        t = self.toks[self.i]
        if (kind and t[0] != kind) or (value and t[1] != value):
            raise _Unknown
        self.i += 1
        return t[1]

    def _or(self):
        vals = [self._and()]
        while self._peek() == ("word", "or"):
            self.i += 1
            vals.append(self._and())
        if any(v is True for v in vals):
            return True
        return None if any(v is None for v in vals) else False

    def _and(self):
        vals = [self._not()]
        while self._peek() == ("word", "and"):
            self.i += 1
            vals.append(self._not())
        if any(v is False for v in vals):
            return False
        return None if any(v is None for v in vals) else True

    def _not(self):
        if self._peek() == ("word", "not"):
            self.i += 1
            v = self._not()
            return None if v is None else not v
        if self._peek()[0] == "(":
            self.i += 1
            v = self._or()
            self._take(")")
            return v
        return self._call()

    def _call(self):
        fn = self._take("word")
        self._take("(")
        args = []
        while self._peek()[0] != ")":
            k, v = self.toks[self.i]
            if k not in ("str", "atom", "word"):
                raise _Unknown
            args.append(v)
            self.i += 1
            if self._peek()[0] == ",":
                self.i += 1
        self._take(")")
        return self.ctx.function(fn, args)


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------
class Move(NamedTuple):
    name: str
    old_index: int
    new_index: int
    reason_key: str
    reason_args: dict


class Note(NamedTuple):
    level: str          # say / warn / error
    en: str
    es: str


@dataclass
class Suggestion:
    order: list[str]
    moves: list[Move]
    warnings: list[tuple[str, str]]
    notes: dict[str, list[Note]]
    changed: bool
    groups: dict[str, str] = field(default_factory=dict)   # plugin -> LOOT group
    merges: dict[str, list[str]] = field(default_factory=dict)       # merged plugin -> components
    dummies: dict[str, str] = field(default_factory=dict)            # placeholder -> merge ("" unknown)
    duplicates: list[tuple[str, str]] = field(default_factory=list)  # (plugin, merge that also has it)
    unknown: list[dict] = field(default_factory=list)   # {"name", "guess", "why": (en, es), "masters"}


REASONS: dict[str, tuple[str, str]] = {
    "master": ("after its master {master}", "después de su master {master}"),
    "master_of": ("before {plugin}, which uses it as a master",
                  "antes de {plugin}, que lo usa como master"),
    "flag_master": ("master-flagged plugins (ESM/ESL) load before regular plugins such as {plugin}",
                    "los plugins con flag de master (ESM/ESL) cargan antes que los normales como {plugin}"),
    "flag_regular": ("regular plugins load after master-flagged plugins such as {plugin}",
                     "los plugins normales cargan después de los que tienen flag de master como {plugin}"),
    "group": ("LOOT group '{group}' loads after group '{other}' ({plugin})",
              "el grupo de LOOT '{group}' carga después del grupo '{other}' ({plugin})"),
    "group_before": ("LOOT group '{group}' loads before group '{other}' ({plugin})",
                     "el grupo de LOOT '{group}' carga antes del grupo '{other}' ({plugin})"),
    "after": ("LOOT: after {plugin}", "LOOT: después de {plugin}"),
    "after_of": ("LOOT: {plugin} loads after it", "LOOT: {plugin} carga después de este"),
    "req": ("LOOT: requires {plugin}", "LOOT: requiere {plugin}"),
    "req_of": ("LOOT: {plugin} requires it", "LOOT: {plugin} lo requiere"),
    "chain": ("follows {plugin}, which had to move", "sigue a {plugin}, que tuvo que moverse"),
    # merged plugins
    "master_in": ("after its master {master}, which is inside {merge}",
                  "después de su master {master}, que está dentro de {merge}"),
    "master_in_of": ("before {plugin}, which uses {master} (inside this plugin) as a master",
                     "antes de {plugin}, que usa {master} (dentro de este plugin) como master"),
    "merge_group": ("LOOT group '{group}' (from {component}, inside {merge}) loads after "
                    "group '{other}' ({plugin})",
                    "el grupo de LOOT '{group}' (de {component}, dentro de {merge}) carga después "
                    "del grupo '{other}' ({plugin})"),
    "merge_group_before": ("LOOT group '{group}' (from {component}, inside {merge}) loads before "
                           "group '{other}' ({plugin})",
                           "el grupo de LOOT '{group}' (de {component}, dentro de {merge}) carga antes "
                           "del grupo '{other}' ({plugin})"),
    "after_in": ("LOOT: after {plugin} (inside {merge})", "LOOT: después de {plugin} (dentro de {merge})"),
    "after_in_of": ("LOOT: {plugin} loads after {component}, which is inside this plugin",
                    "LOOT: {plugin} carga después de {component}, que está dentro de este plugin"),
    "merge_after": ("LOOT: after {plugin} (rule of {component}, inside {merge})",
                    "LOOT: después de {plugin} (regla de {component}, dentro de {merge})"),
    "merge_after_of": ("LOOT: {plugin} loads after it (rule of {component}, inside {plugin})",
                       "LOOT: {plugin} carga después de este (regla de {component}, dentro de {plugin})"),
    # the user's own choices
    "user_group": ("your choice: group '{group}', which loads after group '{other}' ({plugin})",
                   "tu elección: grupo '{group}', que carga después del grupo '{other}' ({plugin})"),
    "user_group_before": ("your choice: group '{group}', which loads before group '{other}' ({plugin})",
                          "tu elección: grupo '{group}', que carga antes del grupo '{other}' ({plugin})"),
    "user_after": ("your choice: after {plugin}", "tu elección: después de {plugin}"),
    "switch_group": ("Switch plugin: group '{group}', which loads after group '{other}' ({plugin})",
                     "plugin de Switch: grupo '{group}', que carga después del grupo '{other}' ({plugin})"),
    "switch_group_before": ("Switch plugin: group '{group}', which loads before group '{other}' ({plugin})",
                            "plugin de Switch: grupo '{group}', que carga antes del grupo '{other}' ({plugin})"),
    "user_after_of": ("your choice: {plugin} loads after it", "tu elección: {plugin} carga después de este"),
}


def reason_text(key: str, args: dict) -> tuple[str, str]:
    en, es = REASONS.get(key, (key, key))
    try:
        return en.format(**args), es.format(**args)
    except (KeyError, IndexError):
        return en, es


def describe(move: Move) -> tuple[str, str]:
    return reason_text(move.reason_key, move.reason_args)


_RANK = {"master": 0, "master_of": 0, "flag_master": 1, "flag_regular": 1,
         "group": 2, "group_before": 2, "req": 3, "req_of": 3, "after": 3,
         "after_of": 3, "chain": 9,
         "merge_group": 2, "merge_group_before": 2, "user_group": 2, "user_group_before": 2, "switch_group": 2, "switch_group_before": 2,
         "after_in": 3, "after_in_of": 3, "merge_after": 3, "merge_after_of": 3,
         "user_after": 3, "user_after_of": 3, "master_in": 0, "master_in_of": 0}
_UP = {"master": "master_of", "group": "group_before", "after": "after_of", "req": "req_of",
       "master_in": "master_in_of",
       "after_in": "after_in_of", "merge_after": "merge_after_of", "user_after": "user_after_of"}


@dataclass
class _Unit:
    uid: int
    head: int                 # line index of the plugin
    lines: list[int]          # head + passengers
    name: str                 # as in the list
    orig: str                 # original name for masterlist lookups
    meta: PluginMeta | None = None
    group: str = "default"
    masterish: bool = False
    min_slot: int = -1        # must be placed at a line index > this
    comps: list[str] = field(default_factory=list)       # merged plugin: its components
    parts: list[tuple[str, PluginMeta | None]] = field(default_factory=list)
    placeholder: bool = False                            # empty stand-in for a merged plugin
    group_src: tuple[str, dict] | None = None            # ("merge"|"user", reason args)
    extra_anc: set[str] = field(default_factory=set)     # more groups it loads after
    user_after: list[str] = field(default_factory=list)


def _keys(name: str) -> tuple[str, str, str]:
    return name.lower(), _fold1(name), _fold2(name)


class _Ctx:
    """What conditions and rule targets can see of the pack."""

    def __init__(self, pack, units, fixed_names, comp_index=None):
        self.pack = pack
        self.units = units
        self.active: set[str] = set()            # every spelling, lowercased
        self.active_names: list[str] = []
        self.unit_by: list[dict[str, int]] = [{}, {}, {}]
        self.comp_by: list[dict[str, list[int]]] = comp_index or [{}, {}, {}]
        self.comp_low: set[str] = set(self.comp_by[0])
        for u in units:
            for n in {u.name, u.orig}:
                self._index(n, u.uid)
        for n in fixed_names | _FIXED_NAMES:
            self._mark(n)
        for u in units:
            self._mark(u.name)
            self._mark(u.orig)
            for c in u.comps:                    # merged content is loaded too
                self._mark(c)

    def _index(self, name, uid):
        for tier, key in enumerate(_keys(name)):
            self.unit_by[tier].setdefault(key, uid)

    def _own(self, name: str) -> int | None:
        for tier, key in enumerate(_keys(name)):
            if key in self.unit_by[tier]:
                return self.unit_by[tier][key]
        return None

    def merges_with(self, name: str) -> list[int]:
        """Merged plugins that contain `name`."""
        for tier, key in enumerate(_keys(name)):
            if key in self.comp_by[tier]:
                return self.comp_by[tier][key]
        return []

    def targets(self, name: str, placeholders: bool = False) -> list[int]:
        """Units a rule about `name` applies to: the plugin itself (unless it's
        an empty placeholder) and every merge that contains it."""
        own = self._own(name)
        out = [own] if own is not None and not self.units[own].placeholder else []
        out += [m for m in self.merges_with(name) if m not in out]
        if not out and own is not None and placeholders:
            out = [own]
        return out

    def _mark(self, name):
        if name.lower() not in self.active:
            self.active.add(name.lower())
            self.active_names.append(name)
        self.active.add(_fold1(name))

    def unit_for(self, name: str) -> int | None:
        ts = self.targets(name, placeholders=True)
        return ts[0] if ts else None

    def is_active(self, name: str) -> bool:
        if _is_regex(name):
            rx = _compile(name)
            if rx is None:
                raise _Unknown
            return any(rx.fullmatch(n) or rx.fullmatch(n.replace("_", "'"))
                       for n in self.active_names)
        return name.lower() in self.active or _fold1(name) in self.active

    def count_active(self, pattern: str) -> int:
        rx = _compile(pattern)
        if rx is None:
            raise _Unknown
        return sum(1 for n in self.active_names if rx.fullmatch(n))

    def file_state(self, path: str) -> bool | None:
        """True / False when we know, None when the file could be in a BSA."""
        p = path.replace("\\", "/")
        low = p.lower()
        if low.startswith("../") or low.startswith("skse/"):
            return False                     # PC executables, SKSE: not on Switch
        files = getattr(self.pack, "data_files", {}) or {}
        plugins = getattr(self.pack, "plugins", {}) or {}
        if "/" not in p:
            if _is_regex(p):
                rx = _compile(p)
                if rx is None:
                    raise _Unknown
                return any(rx.fullmatch(n) for n in list(files) + list(plugins))
            if low in files or low in plugins or low in _FIXED_NAMES or low in self.comp_low:
                return True
            if self.pack.mode == "AE" and low in _CC_NAMES:
                return True
            return False
        data = getattr(self.pack, "data_dir", None)
        if data and not _is_regex(p) and (Path(data) / p).exists():
            return True
        return None

    def function(self, fn: str, args: list[str]) -> bool | None:
        fn = fn.lower()
        if fn in ("file", "readable"):
            return self.file_state(args[0])
        if fn == "active":
            return self.is_active(args[0])
        if fn == "many":
            rx = _compile(args[0].rsplit("/", 1)[-1])
            if rx is None:
                raise _Unknown
            files = set(getattr(self.pack, "data_files", {}) or {}) | set(self.pack.plugins)
            return sum(1 for n in files if rx.fullmatch(n)) > 1
        if fn == "many_active":
            return self.count_active(args[0]) > 1
        if fn == "is_master":
            h = self.pack.plugins.get(args[0].lower())
            return bool(h and h.is_master_flag)
        if fn in ("checksum", "version", "product_version", "filename_version",
                  "description_contains"):
            return False if self.file_state(args[0]) is False and fn == "checksum" else None
        return None


def _masterish(header, name: str) -> bool:
    return bool(header.is_master_flag) or name.lower().endswith((".esm", ".esl"))


def _bits(mask: int):
    while mask:
        low = mask & -mask
        yield low.bit_length() - 1
        mask ^= low


def suggest(pack, masterlist: Masterlist, aliases: dict[str, str] | None = None,
            userlist: dict | None = None) -> Suggestion:
    """Suggest a LOOT-like order for pack.list_entries. Nothing is written.

    `aliases` maps a plugin's current name to its original name (renamed
    plugins). `userlist` is the user's choices (see load_userlist)."""
    entries = list(pack.list_entries)
    n = len(entries)
    alias = {k.lower(): v for k, v in (aliases or {}).items()}
    plugins = pack.plugins
    ae = pack.mode == "AE"
    warnings: list[tuple[str, str]] = []

    # -- classify lines --------------------------------------------------------
    fixed_line = [False] * n
    units: list[_Unit] = []
    seen: set[str] = set()
    fixed_names: set[str] = set()
    cur: int | None = None                   # unit that passengers attach to
    for i, e in enumerate(entries):
        low = e.lower()
        is_fixed = (not e.startswith("#") and
                    (low in _FIXED_NAMES or (ae and (low in _CC_NAMES or pack.is_cc(e)))))
        head = (not e.startswith("#") and not is_fixed and low in plugins and low not in seen)
        if is_fixed:
            fixed_line[i], cur = True, None
            fixed_names.add(e)
            seen.add(low)
        elif head:
            seen.add(low)
            u = _Unit(len(units), i, [i], e, alias.get(low, e))
            units.append(u)
            cur = u.uid
        elif cur is None:                    # passenger of a fixed line / list start
            fixed_line[i] = True
        else:
            units[cur].lines.append(i)

    # -- merged plugins and their placeholders --------------------------------------
    comp_index: list[dict[str, list[int]]] = [{}, {}, {}]
    merges: dict[str, list[str]] = {}
    for u in units:
        h = plugins[u.name.lower()]
        u.comps = _components_from(h.author, h.description, u.name)
        if u.orig.lower() != u.name.lower():
            u.comps = [c for c in u.comps if c.lower() != u.orig.lower()]
        if u.comps:
            merges[u.name] = list(u.comps)
            for c in u.comps:
                for tier, key in enumerate(_keys(c)):
                    lst = comp_index[tier].setdefault(key, [])
                    if u.uid not in lst:
                        lst.append(u.uid)

    ctx = _Ctx(pack, units, fixed_names, comp_index)
    dummies: dict[str, str] = {}
    duplicates: list[tuple[str, str]] = []
    for u in units:
        if u.comps:
            continue
        h = plugins[u.name.lower()]
        hosts = [m for m in (ctx.merges_with(u.orig) or ctx.merges_with(u.name)) if m != u.uid]
        if h.num_records == 0 and not h.error:
            bsas = pack.bsas_for_plugin(u.name) if hasattr(pack, "bsas_for_plugin") else []
            if hosts:
                u.placeholder = True
                dummies[u.name] = units[hosts[0]].name
            elif masterlist.knows_exact(u.orig, u.name) and not bsas:
                u.placeholder = True             # LOOT knows a mod with content; this is empty
                dummies[u.name] = ""
        elif hosts:
            for m in hosts:
                duplicates.append((u.name, units[m].name))
                warnings.append((
                    f"{u.name} is in the pack twice: as its own plugin and inside {units[m].name}.",
                    f"{u.name} está dos veces en el pack: como plugin propio y dentro de {units[m].name}."))

    cond = _Cond(ctx)
    fixed_index = {e.lower(): i for i, e in enumerate(entries) if fixed_line[i]
                   and not e.startswith("#")}
    by_low = {u.name.lower(): u.uid for u in units}
    k = len(units)

    # -- metadata ----------------------------------------------------------------
    uidx = _user_index(userlist)
    gidx = _group_index(masterlist)
    users: dict[int, dict] = {}

    def valid_group(u, g):
        if g in masterlist.groups:
            return g
        warnings.append((f"{u.name}: LOOT group '{g}' doesn't exist; using 'default'.",
                         f"{u.name}: el grupo de LOOT '{g}' no existe; se usa 'default'."))
        return "default"

    not_found: list[str] = []
    for u in units:
        u.meta = None if u.placeholder else masterlist.lookup(u.orig, u.name)
        u.parts = [(c, masterlist.lookup(c)) for c in u.comps]
        if u.meta is None and not u.placeholder and not any(m for _c, m in u.parts):
            not_found.append(u.name)
        g = valid_group(u, (u.meta.group if u.meta else None) or "default")
        if u.comps:
            cands = [(g, None)] if u.meta else []
            cands += [(valid_group(u, (m.group if m else None) or "default"), c) for c, m in u.parts]
            g, src = max(cands, key=lambda t: (gidx.get(t[0], -1), t[1] is None))
            if src is not None:
                u.group_src = ("merge", {"component": src, "merge": u.name})
            for cg, _c in cands:
                if cg != g:
                    u.extra_anc |= masterlist.group_ancestors(cg) | {cg}
            u.extra_anc.discard(g)     # all lower in group order than g: no cycle
        ue = next((uidx[x] for x in (u.name.lower(), u.orig.lower(), _fold1(u.name), _fold1(u.orig))
                   if x in uidx), None)
        if ue:
            users[u.uid] = ue
            if ue["group"]:
                if ue["group"] in masterlist.groups:
                    src = "switch" if ue.get("note") == "built-in" else "user"
                    g, u.group_src, u.extra_anc = ue["group"], (src, {}), set()
                else:
                    warnings.append((
                        f"{u.name}: your group '{ue['group']}' isn't a LOOT group; it was ignored.",
                        f"{u.name}: tu grupo '{ue['group']}' no es un grupo de LOOT; se ignoró."))
            u.user_after = list(ue["after"])
            if u.name in not_found and (ue["group"] or ue["after"]):
                not_found.remove(u.name)
        u.group = g
        u.masterish = _masterish(plugins[u.name.lower()], u.name)

    # -- rule 1: masters ------------------------------------------------------------
    preds: list[dict[int, tuple[str, dict]]] = [dict() for _ in range(k)]
    succs: list[set[int]] = [set() for _ in range(k)]
    reach = [0] * k                          # reach[x]: bitmask of units after x

    def add(u: int, v: int, kind: str, args: dict) -> bool:
        if u == v or (reach[v] >> u) & 1:
            return False
        if v not in succs[u]:
            succs[u].add(v)
            preds[v][u] = (kind, args)
        if not (reach[u] >> v) & 1:
            new = (1 << v) | reach[v]
            ub = 1 << u
            for x in range(k):
                if x == u or reach[x] & ub:
                    reach[x] |= new
        return True

    by_name = sorted(units, key=lambda u: (u.name.lower(), u.uid))
    for v in by_name:
        for m in plugins[v.name.lower()].masters:
            ml = m.lower()
            if ml in by_low:
                u = by_low[ml]
                if not add(u, v.uid, "master", {"master": units[u].name}):
                    if u != v.uid:
                        warnings.append((
                            f"{v.name} and {m} list each other as masters; the game can't load that.",
                            f"{v.name} y {m} se declaran master el uno del otro; el juego no puede cargar eso."))
            elif ml in fixed_index:
                v.min_slot = max(v.min_slot, fixed_index[ml])
            # a master that was merged: the content it patches is in the merge
            for mu in ctx.merges_with(m):
                if mu == v.uid:
                    continue
                if not add(mu, v.uid, "master_in", {"master": m, "merge": units[mu].name}):
                    warnings.append((
                        f"{v.name} needs {m}, which is inside {units[mu].name}, but "
                        f"{units[mu].name} has to load after {v.name}.",
                        f"{v.name} necesita {m}, que está dentro de {units[mu].name}, pero "
                        f"{units[mu].name} tiene que cargar después de {v.name}."))

    # -- rule 2: master flags (a non-master that a master needs goes with them) ------
    changed_flag = True
    while changed_flag:
        changed_flag = False
        for v in units:
            if v.masterish:
                for u in preds[v.uid]:
                    if not units[u].masterish:
                        units[u].masterish = changed_flag = True
    msec = 0
    for u in units:
        if u.masterish:
            msec |= 1 << u.uid
    regular = ((1 << k) - 1) & ~msec
    for u in units:                          # closure of the partition edges
        if u.masterish:
            reach[u.uid] |= regular
            for x in _bits(regular):
                reach[u.uid] |= reach[x]
    reach_hard = list(reach)

    def blocked_by_flags(u: int, v: int) -> bool:
        return not units[u].masterish and units[v].masterish

    # -- rules 3 and 4 --------------------------------------------------------------------
    skipped_groups: dict[tuple[int, str], list] = {}

    def group_rules():
        # Like LOOT: relations between named groups first, then the ones that
        # involve 'default', so a big default group doesn't decide everything.
        for with_default in (False, True):
            for v in by_name:
                anc = masterlist.group_ancestors(v.group) | v.extra_anc
                if anc:
                    group_pairs(v, anc, with_default)

    def group_pairs(v, anc, with_default):
        for u in by_name:
            if u.group in anc and with_default == ("default" in (u.group, v.group)):
                if blocked_by_flags(u.uid, v.uid):
                    continue             # flags win over groups, as in LOOT
                if not add(u.uid, v.uid, "group",
                           {"group": v.group, "other": u.group, "plugin": u.name}):
                    if (reach[v.uid] >> u.uid) & 1:
                        hit = skipped_groups.setdefault((v.uid, u.group), [[], True])
                        hit[0].append(u.name)
                        hit[1] = hit[1] and bool((reach_hard[v.uid] >> u.uid) & 1)

    def after_rules():
        for v in by_name:
            sources = ([(None, v.meta)] if v.meta else []) + [(c, m) for c, m in v.parts if m]
            for comp, meta in sources:
                for kind, refs in (("req", meta.req), ("after", meta.after)):
                    for f in refs:
                        if not f.name.lower().endswith(PLUGIN_EXT) or cond(f.condition) is not True:
                            continue
                        for u in ctx.targets(f.name):
                            if u == v.uid:
                                continue
                            target = units[u].name
                            if comp is not None:
                                k2, args = "merge_after", {"plugin": target, "component": comp,
                                                           "merge": v.name}
                            elif target.lower() != f.name.lower() and u in ctx.merges_with(f.name):
                                k2, args = "after_in", {"plugin": f.name, "merge": target}
                            else:
                                k2, args = kind, {"plugin": target}
                            if blocked_by_flags(u, v.uid) or (reach[v.uid] >> u) & 1:
                                why_en, why_es = ("master order or ESM flags", "orden de masters o flags ESM")
                                if not ((reach_hard[v.uid] >> u) & 1) and not blocked_by_flags(u, v.uid):
                                    why_en, why_es = ("LOOT groups or other rules",
                                                      "grupos de LOOT u otras reglas")
                                src_en = f" (rule of {comp})" if comp else ""
                                src_es = f" (regla de {comp})" if comp else ""
                                warnings.append((
                                    f"Ignored LOOT rule '{v.name} after {target}'{src_en}: "
                                    f"it conflicts with {why_en}.",
                                    f"Se ignoró la regla de LOOT '{v.name} después de {target}'{src_es}: "
                                    f"choca con {why_es}."))
                                continue
                            add(u, v.uid, k2, args)

    def user_rules():
        # The user's own 'after' rules win over groups (not over masters / flags).
        for v in by_name:
            for name in v.user_after:
                ts = [t for t in ctx.targets(name, placeholders=True) if t != v.uid]
                if not ts:
                    warnings.append((
                        f"Your rule '{v.name} after {name}': {name} isn't in the load order.",
                        f"Tu regla '{v.name} después de {name}': {name} no está en el orden de carga."))
                for u in ts:
                    target = units[u].name
                    if blocked_by_flags(u, v.uid) or (reach[v.uid] >> u) & 1:
                        warnings.append((
                            f"Ignored your rule '{v.name} after {target}': it conflicts with "
                            "master order or ESM flags.",
                            f"Se ignoró tu regla '{v.name} después de {target}': choca con el "
                            "orden de masters o los flags ESM."))
                        continue
                    add(u, v.uid, "user_after", {"plugin": target})

    user_rules()
    if AFTER_BEATS_GROUPS:
        after_rules(); group_rules()
    else:
        group_rules(); after_rules()
    for (vid, g), (names, hard) in sorted(skipped_groups.items(),
                                          key=lambda t: (units[t[0][0]].head, t[0][1])):
        v = units[vid]
        who = ", ".join(names[:3]) + (" ..." if len(names) > 3 else "")
        why_en = "they use it as a master" if hard else "of their masters or other LOOT rules"
        why_es = "lo usan como master" if hard else "sus masters u otras reglas de LOOT lo piden"
        if hard and v.comps:
            why_en = "they use it, or a plugin merged into it, as a master"
            why_es = "lo usan como master, a él o a un plugin que tiene adentro"
        warnings.append((
            f"LOOT group order skipped: {v.name} (group '{v.group}') stays before {who} "
            f"(group '{g}') because {why_en}.",
            f"Se omitió el orden de grupos de LOOT: {v.name} (grupo '{v.group}') queda antes de {who} "
            f"(grupo '{g}') porque {why_es}."))

    # -- stable topological sort into the free slots ---------------------------------------
    slots = [i for i in range(n) if not fixed_line[i]]
    indeg = [len(preds[x]) for x in range(k)]
    left = set(range(k))
    masters_left = sum(1 for u in units if u.masterish)
    placed: list[int] = []
    pos = 0
    while left:
        p = slots[pos]
        ready = sorted((x for x in left if indeg[x] == 0), key=lambda x: units[x].head)
        ok_flag = [x for x in ready if units[x].masterish or masters_left == 0]
        ok_slot = [x for x in ok_flag if units[x].min_slot < p]
        fits = [x for x in ok_slot
                if slots[pos + len(units[x].lines) - 1] - p == len(units[x].lines) - 1]
        if fits:
            x = fits[0]
        elif ok_slot:
            x = ok_slot[0]
            warnings.append((
                f"The disabled or missing lines after {units[x].name} had to be split by a fixed entry.",
                f"Las líneas desactivadas o faltantes después de {units[x].name} quedaron separadas por una entrada fija."))
        elif ok_flag:
            x = ok_flag[0]
            need = [m for m in plugins[units[x].name.lower()].masters
                    if fixed_index.get(m.lower(), -1) >= p]
            warnings.append((
                f"{units[x].name} needs {', '.join(need)}, a fixed entry further down; "
                "it can't be fixed by sorting.",
                f"{units[x].name} necesita {', '.join(need)}, una entrada fija que está más abajo; "
                "ordenar no lo arregla."))
        else:
            x = ready[0]                 # never expected: flags are consistent by construction
        placed.append(x)
        left.discard(x)
        pos += len(units[x].lines)
        if units[x].masterish:
            masters_left -= 1
        for y in succs[x]:
            indeg[y] -= 1

    order = list(entries)
    new_line = {}
    it = iter(slots)
    for x in placed:
        for li in units[x].lines:
            s = next(it)
            order[s] = entries[li]
            new_line[li] = s

    # -- moves: plugins outside the longest run that kept its order -------------------------
    seq = [units[x].head for x in placed]
    keep = _lis(seq, {u.head for u in units if new_line[u.head] == u.head})
    rank_new = {x: r for r, x in enumerate(placed)}
    rank_old = {u.uid: r for r, u in enumerate(sorted(units, key=lambda u: u.head))}
    moves: list[Move] = []
    for x in placed:
        u = units[x]
        if u.head in keep:
            continue
        key, args = _explain(u, units, preds, succs, rank_new[x] < rank_old[x], keep)
        moves.append(Move(u.name, u.head, new_line[u.head], key, args))
    moves.sort(key=lambda m: m.new_index)

    # -- notes ----------------------------------------------------------------------------
    notes: dict[str, list[Note]] = {}
    for u in sorted(units, key=lambda u: u.head):
        out = _notes_for(u, ctx, cond)
        ue = users.get(u.uid)
        if ue and ue["note"]:
            out.append(Note("say", ue["note"], ue["note"]))
        if out:
            notes[u.name] = out
    if not_found:
        shown = ", ".join(not_found[:8]) + (" ..." if len(not_found) > 8 else "")
        warnings.append((
            f"{len(not_found)} plugin(s) aren't in the LOOT masterlist and use group 'default': {shown}",
            f"{len(not_found)} plugin(s) no están en la masterlist de LOOT y usan el grupo 'default': {shown}"))

    # -- plugins LOOT doesn't know: a guessed group for the user to confirm -------------
    unknown: list[dict] = []
    for u in sorted(units, key=lambda u: u.head):
        low = u.name.lower()
        if (u.meta is not None or u.comps or u.placeholder or u.uid in users
                or _is_base(u.name) or _is_base(u.orig)):
            continue
        h = plugins[low]
        g, why = guess_group(h.path, pack)
        unknown.append({"name": u.name, "guess": g, "why": why, "masters": list(h.masters)})

    return Suggestion(order=order, moves=moves, warnings=warnings, notes=notes,
                      changed=order != entries, groups={u.name: u.group for u in units},
                      merges=merges, dummies=dummies, duplicates=duplicates, unknown=unknown)


def _lis(seq: list[int], same: set[int]) -> set[int]:
    """Values of a longest increasing subsequence of seq: the plugins that
    count as not moved. Ties keep, first, plugins whose line number didn't
    change (`same`), then the ones that come first in the new order, so a
    patch that goes below its target is the one reported as moved."""
    n = len(seq)
    score = [(1, int(v in same)) for v in seq]     # best run starting at i
    for i in range(n - 2, -1, -1):
        for j in range(i + 1, n):
            if seq[j] > seq[i]:
                cand = (score[j][0] + 1, score[j][1] + int(seq[i] in same))
                if cand > score[i]:
                    score[i] = cand
    out: set[int] = set()
    need, last = max(score, default=(0, 0)), -1
    for i in range(n):
        if need[0] and score[i] == need and seq[i] > last:
            out.add(seq[i])
            last = seq[i]
            need = (need[0] - 1, need[1] - int(seq[i] in same))
    return out


def _explain(u: _Unit, units, preds, succs, moved_up: bool, keep: set[int]) -> tuple[str, dict]:
    """The strongest rule that ties u to a plugin that did not move."""
    cands: list[tuple[bool, int, int, str, dict]] = []
    x = u.uid
    if not moved_up:
        for p, (kind, args) in preds[x].items():
            if units[p].head > u.head or units[p].head not in keep:
                key, a = kind, args
                if kind == "group" and u.group_src:
                    key, a = f"{u.group_src[0]}_group", {**args, **u.group_src[1]}
                cands.append((units[p].head not in keep, _RANK[key], -units[p].head, key, a))
        if not u.masterish:
            ys = [y for y in units if y.masterish and y.head > u.head]
            ys.sort(key=lambda y: (y.head not in keep, -y.head))
            if ys:
                cands.append((ys[0].head not in keep, 1, -ys[0].head, "flag_regular",
                              {"plugin": ys[0].name}))
    else:
        for s in succs[x]:
            if units[s].head < u.head or units[s].head not in keep:
                kind, args = preds[s][x]
                key = _UP[kind]
                a = {"plugin": units[s].name}
                if kind == "group":
                    a = {"group": u.group, "other": units[s].group, "plugin": units[s].name}
                    if u.group_src:
                        key = f"{u.group_src[0]}_group_before"
                        a.update(u.group_src[1])
                elif kind == "after_in":
                    a["component"] = args["plugin"]
                elif kind == "merge_after":
                    a["component"] = args["component"]
                elif kind == "master_in":
                    a["master"] = args["master"]
                cands.append((units[s].head not in keep, _RANK[key], units[s].head, key, a))
        if u.masterish:
            ys = [y for y in units if not y.masterish and y.head < u.head]
            ys.sort(key=lambda y: (y.head not in keep, y.head))
            if ys:
                cands.append((ys[0].head not in keep, 1, ys[0].head, "flag_master",
                              {"plugin": ys[0].name}))
    if cands:
        cands.sort(key=lambda c: (c[0], c[1], c[2]))
        return cands[0][3], cands[0][4]
    if preds[x]:
        p = max(preds[x], key=lambda p: units[p].head)
        return "chain", {"plugin": units[p].name}
    s = min(succs[x], key=lambda s: units[s].head) if succs[x] else None
    return "chain", {"plugin": units[s].name if s is not None else u.name}


def _notes_for(u: _Unit, ctx: _Ctx, cond: _Cond) -> list[Note]:
    """Notes from the plugin's own metadata, then from each merged component
    (prefixed with the component's name). Placeholders have no metadata."""
    out = _meta_notes(u.meta, u, ctx, cond) if u.meta else []
    for comp, m in u.parts:
        if m is None:
            continue
        for n in _meta_notes(m, u, ctx, cond):
            note = Note(n.level, f"{comp} (inside {u.name}): {n.en}",
                        f"{comp} (dentro de {u.name}): {n.es}")
            if note not in out:
                out.append(note)
    return out


def _meta_notes(m: PluginMeta, u: _Unit, ctx: _Ctx, cond: _Cond) -> list[Note]:
    out: list[Note] = []
    for msg in m.msg:
        if cond(msg.condition) is True and msg.en:
            out.append(Note(msg.type, _short(msg.en), _short(msg.es)))
    for f in m.req:
        if cond(f.condition) is not True:
            continue
        what = f.display or f.name
        if f.name.lower().endswith(PLUGIN_EXT):
            present = ctx.is_active(f.name)
        else:
            present = ctx.file_state(f.name)
        if present is False:
            out.append(Note("error", f"Requires {what}, which the pack doesn't load.",
                            f"Requiere {what}, que el pack no carga."))
    for f in m.inc:
        if cond(f.condition) is not True:
            continue
        what = f.display or f.name
        if f.name.lower().endswith(PLUGIN_EXT):
            present = ctx.is_active(f.name) and ctx.unit_for(f.name) != u.uid
        else:
            present = ctx.file_state(f.name)
        if present is True:
            out.append(Note("error", f"Incompatible with {what}.", f"Incompatible con {what}."))
    return out


def _short(s: str, limit: int = 300) -> str:
    s = " ".join(s.split())
    return s if len(s) <= limit else s[:limit - 1].rstrip() + "…"
