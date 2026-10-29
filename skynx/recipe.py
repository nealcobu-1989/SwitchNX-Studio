"""The pack recipe: how a modpack was built, without the mod files themselves.

A recipe can be read by a person (export_markdown), compared with an older
one (diff), checked against the pack as it is now (verify) and, later, used
to rebuild the pack from the user's own downloads (missing_sources is the
first step: find each mod's archive again). It never contains mod files, so
it can be shared without redistributing anybody's work.

    build(pack, userlist_path=None, full=False) -> dict
    save(pack, recipe) -> Path               .skynx/recipe.json + .skynx/recipes/
    history(pack) -> [{path, created, mods}]
    load(path) -> dict
    export_markdown(recipe, lang) -> str     file names only, no local paths
    diff(old, new) -> dict ; diff_text(d, lang) -> [str]
    verify(pack, recipe, full=False) -> [dict]
    missing_sources(recipe, search_dirs) -> [{mod, found, by, ...}]

Provenance ("source" block in every mods.json record, written when a mod
enters the pack; see source_block):
    {"kind": "nexus"|"archive"|"folder"|"pack"|"ussep"|"unknown",
     "path": original path, "file": its name, "size": bytes,
     "md5": archive md5 (archives) | "fingerprint": sha1 of (relpath, size) (folders),
     "nexus": {"mod_id", "file_id", "version", "name", ...} when known,
     "added": time}
Old records keep "source" as a plain path string; source_of() reads both.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import time
from pathlib import Path

from . import __version__
from . import knowledge as K

RECIPE_VERSION = 1
KEEP = 20
ARCHIVE_EXT = {".7z", ".zip", ".rar"}
PLUGIN_EXT = {".esp", ".esm", ".esl"}
NEXUS_URL = "https://www.nexusmods.com/{game}/mods/{mod_id}"
NEXUS_GAME = "skyrimspecialedition"
MTIME_SLACK = 2.0          # FAT32 (SD cards) keeps mtimes to 2 s
ARCHIVE_KEYS = ("sResourceArchiveList", "sResourceArchiveList2", "sArchiveToLoadInMemoryList")


# ================================================================ hashing
def _hash(path: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_file(path: Path) -> str:
    return _hash(path, "md5")


def sha1_file(path: Path) -> str:
    return _hash(path, "sha1")


def folder_fingerprint(folder: Path, files: list[Path] | None = None) -> str:
    """sha1 over the sorted (relative path, size) pairs: cheap (no reading),
    and the same for the same folder wherever it sits."""
    folder = Path(folder)
    pairs = []
    items = [Path(f) for f in files] if files is not None else \
        [p for p in folder.rglob("*") if p.is_file()]
    for p in items:
        try:
            rel = p.relative_to(folder).as_posix()
        except ValueError:
            rel = p.name
        try:
            pairs.append((rel, p.stat().st_size))
        except OSError:
            continue
    h = hashlib.sha1()
    for rel, size in sorted(pairs):
        h.update(f"{rel}\0{size}\n".encode("utf-8", "surrogateescape"))
    return h.hexdigest()


def basename(s) -> str | None:
    """File name of a path written on any system ('C:\\x\\y.7z' -> 'y.7z')."""
    if s is None:
        return None
    s = str(s).rstrip("/\\")
    return re.split(r"[\\/]", s)[-1] if s else None


# ================================================================ provenance
def norm_nexus(nexus: dict | None) -> dict | None:
    """What the Nexus code knows about a download: mod_id, file_id, version,
    name (plus any other plain values it passes, like "game")."""
    if not isinstance(nexus, dict):
        return None
    out = {}
    for k, v in nexus.items():
        if v is None or isinstance(v, (dict, list)):
            continue
        if k in ("mod_id", "file_id"):
            try:
                v = int(v)
            except (TypeError, ValueError):
                pass
        out[str(k)] = v
    return out or None


def source_block(path, kind: str | None = None, nexus: dict | None = None,
                 files: list[Path] | None = None, **extra) -> dict:
    """Provenance of a mod as it enters the pack. Archives get their md5
    (read in chunks), folders a fingerprint of names and sizes. `files`
    (the files actually taken from a folder) narrows the fingerprint."""
    nx = norm_nexus(nexus)
    out: dict = {"kind": kind or "unknown", "path": str(path) if path else None,
                 "file": basename(path), "size": None}
    p = Path(path) if path else None
    try:
        if p is not None and p.is_file():
            out["size"] = p.stat().st_size
            out["md5"] = md5_file(p)
            out["kind"] = kind or "archive"
        elif p is not None and p.is_dir():
            items = [Path(f) for f in files] if files is not None else \
                [q for q in p.rglob("*") if q.is_file()]
            out["size"] = sum(q.stat().st_size for q in items if q.exists())
            out["fingerprint"] = folder_fingerprint(p, items)
            out["kind"] = kind or "folder"
    except OSError:
        pass
    if nx:
        out["nexus"] = nx
        if out["kind"] in ("archive", "folder", "unknown"):
            out["kind"] = "nexus"
    out.update({k: v for k, v in extra.items() if v is not None})
    out["added"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return out


def source_of(rec: dict) -> dict:
    """The source block of a mods.json record, old (plain path) or new."""
    s = rec.get("source") if isinstance(rec, dict) else None
    if isinstance(s, dict):
        out = dict(s)
        out.setdefault("kind", "unknown")
        out.setdefault("file", basename(out.get("path")))
        return out
    if isinstance(s, list):          # several parts of one download
        s = s[0] if s else None
    if rec.get("ussep"):
        kind = "ussep"
    elif rec.get("from_pack"):
        kind = "pack"
    elif s and Path(basename(s) or "").suffix.lower() in ARCHIVE_EXT:
        kind = "archive"
    elif s:
        kind = "folder"
    else:
        kind = "unknown"
    out = {"kind": kind, "path": s, "file": basename(s), "legacy": True}
    if rec.get("from_pack"):
        out["pack"] = rec["from_pack"]
    if rec.get("added"):
        out["added"] = rec["added"]
    return out


def nexus_of(src: dict) -> dict | None:
    """Nexus info of a source block, or of the mod it came from (pack transfers)."""
    if not isinstance(src, dict):
        return None
    if src.get("nexus"):
        return src["nexus"]
    origin = src.get("origin")
    return origin.get("nexus") if isinstance(origin, dict) else None


def nexus_link(nx: dict | None) -> str | None:
    if not nx or not nx.get("mod_id"):
        return None
    return NEXUS_URL.format(game=nx.get("game") or NEXUS_GAME, mod_id=nx["mod_id"])


# ================================================================ build
def _recipe_dir(pack) -> Path:
    return Path(pack.root) / ".skynx"


def _read_json(p: Path, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8")) if Path(p).exists() else default
    except (OSError, ValueError):
        return default


def _ini_summary(pack) -> list[dict]:
    out = []
    for ini in pack.inis:
        p = ini.path
        lists = {k: ini.archive_list(k) for k in ARCHIVE_KEYS if ini.get("Archive", k) is not None}
        stest = [e.value for e in ini.entries
                 if e.section.lower() == "general" and e.key.lower().startswith("stestfile") and e.value]
        try:
            raw = p.read_bytes()
        except OSError:
            raw = b""
        out.append({"name": p.name, "size": len(raw), "sha1": hashlib.sha1(raw).hexdigest(),
                    "archives": lists, "stest": stest})
    return out


def _fingerprint(p: Path, full: bool) -> dict:
    st = p.stat()
    ext = p.suffix.lower()
    out = {"kind": "plugin" if ext in PLUGIN_EXT else ("bsa" if ext == ".bsa" else "other"),
           "size": st.st_size, "mtime": round(st.st_mtime, 1)}
    if out["kind"] == "plugin" or full:
        out["sha1"] = sha1_file(p)
    return out


def _clean_mod(mod_id: str, rec: dict, files: dict, order: list[str]) -> dict:
    src = source_of(rec)
    names = list(rec.get("plugins") or []) + list(rec.get("bsas") or [])
    low_files = {k.lower() for k in files}
    pos = [order.index(p.lower()) for p in rec.get("plugins") or [] if p.lower() in order]
    m = {"id": mod_id, "name": mod_id,
         "plugins": list(rec.get("plugins") or []), "bsas": list(rec.get("bsas") or []),
         "ini": [dict(e) for e in rec.get("ini") or [] if isinstance(e, dict)],
         "source": src, "converted": rec.get("converted") or None,
         "fomod": rec.get("fomod") or None, "fomod_choices": rec.get("fomod_choices") or None,
         "renamed": rec.get("renamed") or {}, "from_pack": rec.get("from_pack"),
         "added": rec.get("added"), "position": min(pos) if pos else None,
         "missing": [n for n in names if n.lower() not in low_files]}
    if src.get("nexus"):
        m["nexus"] = src["nexus"]
    for k in ("ussep", "from_unit", "reason", "needed_by", "name_fixed", "masters_patched"):
        if rec.get(k):
            m[k] = rec[k]
    return m


def build(pack, userlist_path=None, full: bool = False) -> dict:
    """The recipe of a pack as it is now. Cheap by default: plugins are
    hashed (they're small), BSAs only get size and modification time unless
    full=True (they can be GBs)."""
    from .builder import load_mods
    from .bsafix import load_renames
    from .dupfix import load_ignored
    root = Path(pack.root)
    files: dict[str, dict] = {}
    for low, p in sorted(pack.data_files.items()):
        ext = p.suffix.lower()
        if ext in PLUGIN_EXT or ext == ".bsa":
            try:
                files[p.name] = _fingerprint(p, full)
            except OSError:
                continue
    order_full = list(pack.list_entries)
    order = [e.lower() for e in order_full]
    mods_raw = load_mods(pack)
    mods = [_clean_mod(k, r, files, order) for k, r in mods_raw.items() if isinstance(r, dict)]
    owned = {n.lower() for m in mods for n in m["plugins"] + m["bsas"]}
    listed = {e.lstrip("#").strip().lower() for e in order_full} | {s.lower() for s in pack.stest_plugins()}
    in_ini = {b.lower() for v in pack.archive_lists().values() for b in v}
    unowned = []
    for name, f in files.items():
        if name.lower() in owned:
            continue
        unowned.append({"name": name, "kind": f["kind"], "source": {"kind": "unknown"},
                        "loaded": name.lower() in listed or name.lower() in in_ini
                        or (f["kind"] == "bsa" and _bsa_has_plugin(pack, name))})
    for a in sorted(pack.archives, key=lambda p: p.name.lower()):
        unowned.append({"name": a.name, "kind": "archive", "source": {"kind": "unknown"},
                        "loaded": False, "size": a.stat().st_size})
    renames = load_renames(pack)
    try:
        kept = sorted(load_ignored(pack))
    except Exception:  # noqa: BLE001
        kept = []
    loot_choices = {}
    if userlist_path:
        from .loot import load_userlist
        try:
            ul = load_userlist(Path(userlist_path))
        except Exception:  # noqa: BLE001
            ul = {"plugins": {}}
        here = {h.name.lower() for h in pack.plugins.values()} | listed
        here |= {str(o).lower() for o in renames.values()}
        here |= {str(o).lower() for m in mods for o in (m["renamed"] or {}).values()}
        loot_choices = {k: v for k, v in (ul.get("plugins") or {}).items() if k in here}
    project = _read_json(root / ".skynx" / "project.json", {})
    lp = pack.list_path
    try:
        list_raw = lp.read_bytes() if lp and lp.exists() else b""
    except OSError:
        list_raw = b""
    recipe = {
        "version": RECIPE_VERSION, "app": __version__,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"), "full": bool(full),
        "pack": {"name": root.name, "edition": pack.mode,
                 "list_file": lp.name if lp else None,
                 "list_sha1": hashlib.sha1(list_raw).hexdigest() if lp else None,
                 "list_bytes": len(list_raw),
                 "project": {k: project.get(k) for k in ("edition", "cc_preset", "ussep", "created")
                             if k in project} or None,
                 "other_inis": [p.name for p in pack.other_inis],
                 "loose_dirs": sorted(pack.loose_dirs)},
        "inis": _ini_summary(pack),
        "archive_lists": pack.archive_lists(),
        "load_order": order_full,
        "mods": mods,
        "unowned": unowned,
        "renames": renames,
        "kept_duplicates": kept,
        "loot": loot_choices,
        "files": files,
    }
    recipe["counts"] = {
        "mods": len(mods), "plugins": sum(1 for f in files.values() if f["kind"] == "plugin"),
        "bsas": sum(1 for f in files.values() if f["kind"] == "bsa"),
        "unowned": len(unowned), "load_order": len(order_full),
        "disabled": sum(1 for e in order_full if e.startswith("#")),
        "cc": sum(1 for e in order_full if _is_cc(e, files)),
        "bytes": sum(f["size"] for f in files.values()),
        "nexus": sum(1 for m in mods if nexus_of(m["source"]))}
    return recipe


def _bsa_has_plugin(pack, bsa: str) -> bool:
    s = Path(bsa).stem.lower()
    base = s[:-11] if s.endswith(" - textures") else s
    return any(Path(low).stem == base for low in pack.plugins)


_CC = {c.lower() for c in K.AE_CC_PLUGINS}


def _is_cc(entry: str, files: dict) -> bool:
    low = entry.lstrip("#").strip().lower()
    if low in _CC:
        return True
    return low.startswith("cc") and low not in {f.lower() for f in files}


# ================================================================ save / history
def save(pack, recipe: dict) -> Path:
    """Write .skynx/recipe.json and a dated copy in .skynx/recipes/ (the last
    20 are kept). Not a history entry: the recipe describes the pack, it
    isn't part of it."""
    d = _recipe_dir(pack)
    snaps = d / "recipes"
    snaps.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(recipe, indent=1, ensure_ascii=False).encode("utf-8")
    stamp = time.strftime("%Y%m%d-%H%M%S", time.strptime(recipe.get("created") or
                                                          time.strftime("%Y-%m-%d %H:%M:%S"),
                                                          "%Y-%m-%d %H:%M:%S"))
    snap, n = snaps / f"recipe-{stamp}.json", 2
    while snap.exists():
        snap, n = snaps / f"recipe-{stamp}-{n}.json", n + 1
    for target in (snap, d / "recipe.json"):
        tmp = target.with_name(target.name + ".part")
        tmp.write_bytes(raw)
        os.replace(tmp, target)
    for old in _snapshots(pack)[KEEP:]:
        try:
            old.unlink()
        except OSError:
            pass
    return d / "recipe.json"


def _snapshots(pack) -> list[Path]:
    d = _recipe_dir(pack) / "recipes"
    if not d.is_dir():
        return []
    def key(p: Path):
        m = re.match(r"recipe-(\d{8}-\d{6})(?:-(\d+))?\.json$", p.name)
        return (m.group(1), int(m.group(2) or 1)) if m else ("", 0)
    return sorted((p for p in d.glob("recipe-*.json")), key=key, reverse=True)


def history(pack) -> list[dict]:
    """Saved recipes, newest first: [{path, created, mods}]."""
    out = []
    for p in _snapshots(pack):
        r = _read_json(p, None)
        if not isinstance(r, dict):
            continue
        out.append({"path": str(p), "created": r.get("created"), "mods": len(r.get("mods") or [])})
    return out


def load(path) -> dict:
    """A saved recipe (raises on a broken file)."""
    from .errors import SkynxError
    try:
        r = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SkynxError(f"Can't read the recipe ({basename(path)}): {e}",
                         f"No se puede leer la receta ({basename(path)}): {e}") from e
    if not isinstance(r, dict) or "mods" not in r:
        raise SkynxError(f"{basename(path)} isn't a pack recipe.",
                         f"{basename(path)} no es una receta de modpack.")
    return r


def current(pack) -> dict | None:
    """The last saved recipe of a pack, or None."""
    p = _recipe_dir(pack) / "recipe.json"
    r = _read_json(p, None)
    return r if isinstance(r, dict) else None


def shareable(recipe: dict) -> dict:
    """A copy of the recipe with local paths reduced to file names."""
    r = json.loads(json.dumps(recipe))

    def strip(src):
        if isinstance(src, dict):
            if src.get("path"):
                src["path"] = basename(src["path"])
            if isinstance(src.get("origin"), dict):
                strip(src["origin"])
    for m in r.get("mods") or []:
        strip(m.get("source"))
    return r


# ================================================================ markdown
TXT = {
    "en": {
        "title": "Modpack recipe", "edition": "Edition", "created": "Recipe made", "app": "App",
        "counts": "{mods} mods, {plugins} plugins, {bsas} BSAs, {lo} lines in the load list "
                  "({cc} Creation Club, {off} switched off), {size} in Data",
        "mods": "Mods", "col_mod": "Mod", "col_src": "Source", "col_ver": "Version",
        "col_fomod": "FOMOD options", "col_conv": "Conversion", "col_ren": "Renamed",
        "kind_nexus": "Nexus", "kind_archive": "archive", "kind_folder": "folder",
        "kind_pack": "from the pack {pack}", "kind_ussep": "USSEP (KokaNX, {v})",
        "kind_unknown": "unknown", "no_mods": "No mod records yet (the pack wasn't built here).",
        "unowned": "Files with no known source",
        "unowned_note": "These plugins and BSAs were already in Data or were added outside the app.",
        "order": "Load order", "off": "switched off", "cc": "Creation Club", "missing": "not in Data",
        "inis": "Inis", "stest": "sTestFile plugins", "renames": "Safe renames (Doctor)",
        "kept": "Duplicates kept on purpose", "loot": "Load order choices (LOOT)",
        "after": "after", "group": "group", "note": "note", "yes": "yes", "no": "no",
        "sdk": "SDK", "pc": "PC DDS", "bc1": "BC1", "list_file": "Load list",
        "other_inis": "Other inis in the folder", "from": "was",
        "by_loot": "recognised by LOOT's list", "by_you": "confirmed by hand",
    },
    "es": {
        "title": "Receta del modpack", "edition": "Edición", "created": "Receta hecha", "app": "App",
        "counts": "{mods} mods, {plugins} plugins, {bsas} BSA, {lo} líneas en la lista de carga "
                  "({cc} del Creation Club, {off} desactivadas), {size} en Data",
        "mods": "Mods", "col_mod": "Mod", "col_src": "Origen", "col_ver": "Versión",
        "col_fomod": "Opciones FOMOD", "col_conv": "Conversión", "col_ren": "Renombrados",
        "kind_nexus": "Nexus", "kind_archive": "comprimido", "kind_folder": "carpeta",
        "kind_pack": "traído del pack {pack}", "kind_ussep": "USSEP (KokaNX, {v})",
        "kind_unknown": "desconocido", "no_mods": "Todavía no hay registros de mods (el pack no se armó aquí).",
        "unowned": "Archivos sin origen conocido",
        "unowned_note": "Estos plugins y BSA ya estaban en Data o se agregaron por fuera de la app.",
        "order": "Orden de carga", "off": "desactivado", "cc": "Creation Club", "missing": "no está en Data",
        "inis": "Inis", "stest": "Plugins en sTestFile", "renames": "Renombres seguros (Doctor)",
        "kept": "Duplicados que se dejaron a propósito", "loot": "Elecciones de orden (LOOT)",
        "after": "después de", "group": "grupo", "note": "nota", "yes": "sí", "no": "no",
        "sdk": "SDK", "pc": "DDS de PC", "bc1": "BC1", "list_file": "Lista de carga",
        "other_inis": "Otros inis en la carpeta", "from": "antes",
        "by_loot": "reconocido por la lista de LOOT", "by_you": "confirmado a mano",
    },
}


def _t(lang: str) -> dict:
    return TXT.get(lang, TXT["en"])


def _human(n: int | None) -> str:
    if n is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def _cell(s) -> str:
    """Safe inside a Markdown table cell, and never a local path."""
    s = "" if s is None else str(s)
    if re.search(r"^[A-Za-z]:[\\/]|^/|^\\\\", s) or ("\\" in s and "/" not in s and len(s.split("\\")) > 2):
        s = basename(s) or ""
    return s.replace("|", "\\|").replace("\n", " ").strip()


def _fomod_text(fomod) -> str:
    if not isinstance(fomod, dict):
        return ""
    parts = []
    for step, groups in fomod.items():
        if not isinstance(groups, dict):
            continue
        for group, opts in groups.items():
            if opts:
                parts.append(f"{group}: {', '.join(map(str, opts))}")
    return "; ".join(parts)


def _conv_text(conv, T) -> str:
    if not isinstance(conv, dict):
        return ""
    bits = [str(conv.get("preset") or "")]
    bits.append(T["sdk"] if conv.get("sdk") else T["pc"])
    if conv.get("bc1"):
        bits.append(T["bc1"])
    return ", ".join(b for b in bits if b)


def _ident_text(d: dict | None, T, fallback: str = "") -> str:
    """A link found by recognising the mod (not by where it was downloaded)."""
    if not d or not d.get("url"):
        return ""
    how = T["by_you"] if d.get("status") == "confirmed" else T["by_loot"] if d.get("status") == "likely" else ""
    label = _cell(d.get("title") or fallback or f"#{d.get('mod_id')}")
    return f"[{T['kind_nexus']}: {label}]({d['url']})" + (f" ({how})" if how else "")


def _source_text(m: dict, T, ident: dict | None = None) -> str:
    src = m.get("source") or {}
    nx = nexus_of(src)
    link = nexus_link(nx)
    if not link and ident and ident.get("url"):
        found = _ident_text(ident, T, m.get("name"))
        kind = src.get("kind") or "unknown"
        if kind in ("unknown", "nexus"):
            return found
        return f"{found}, " + _source_text(m, T)
    kind = src.get("kind") or "unknown"
    fname = _cell(src.get("file"))
    if kind == "pack":
        base = T["kind_pack"].format(pack=_cell(src.get("pack") or m.get("from_pack") or fname))
    elif kind == "ussep":
        base = T["kind_ussep"].format(v=_cell(m.get("ussep") or src.get("variant") or ""))
    elif kind in ("archive", "folder", "nexus"):
        base = (T["kind_" + kind] + (f" `{fname}`" if fname else "")) if kind != "nexus" else ""
    else:
        base = T["kind_unknown"]
    if link:
        label = _cell(nx.get("name") or m.get("name"))
        nexus = f"[{T['kind_nexus']}: {label}]({link})"
        if kind == "nexus" and fname:
            nexus += f" `{fname}`"
        return nexus if not base else f"{nexus}, {base}"
    return base


def export_markdown(recipe: dict, lang: str = "en", links: dict | None = None) -> str:
    """A page people can read and share: no local paths, only file names.
    links: mod id or plugin name (lower) -> what recognising it found
    (identify.brief), for mods with no download record."""
    links = {str(k).lower(): v for k, v in (links or {}).items() if v}
    T = _t(lang)
    p = recipe.get("pack") or {}
    c = recipe.get("counts") or {}
    files = recipe.get("files") or {}
    out = [f"# {T['title']}: {_cell(p.get('name'))}", ""]
    out.append(f"- {T['edition']}: **{p.get('edition') or '?'}**")
    if p.get("list_file"):
        out.append(f"- {T['list_file']}: `{_cell(p['list_file'])}`")
    out.append(f"- {T['created']}: {recipe.get('created')} ({T['app']} SwitchNX Studio {recipe.get('app')})")
    out.append("- " + T["counts"].format(mods=c.get("mods", 0), plugins=c.get("plugins", 0),
                                          bsas=c.get("bsas", 0), lo=c.get("load_order", 0),
                                          cc=c.get("cc", 0), off=c.get("disabled", 0),
                                          size=_human(c.get("bytes"))))
    out += ["", f"## {T['mods']}", ""]
    mods = recipe.get("mods") or []
    if mods:
        out.append(f"| {T['col_mod']} | {T['col_src']} | {T['col_ver']} | {T['col_fomod']} | "
                   f"{T['col_conv']} | {T['col_ren']} |")
        out.append("|---|---|---|---|---|---|")
        for m in mods:
            nx = nexus_of(m.get("source")) or {}
            ren = ", ".join(f"{_cell(o)} → {_cell(n)}" for n, o in (m.get("renamed") or {}).items())
            files_txt = ", ".join(_cell(f) for f in m.get("plugins") or []) or \
                ", ".join(_cell(f) for f in m.get("bsas") or [])
            name = f"**{_cell(m.get('name'))}**" + (f"<br>{files_txt}" if files_txt else "")
            ident = links.get(str(m.get("id")).lower()) or next(
                (links[p.lower()] for p in m.get("plugins") or [] if p.lower() in links), None)
            out.append(f"| {name} | {_source_text(m, T, ident)} | {_cell(nx.get('version'))} | "
                       f"{_cell(_fomod_text(m.get('fomod')))} | {_cell(_conv_text(m.get('converted'), T))} | "
                       f"{ren} |")
    else:
        out.append(T["no_mods"])
    un = recipe.get("unowned") or []
    if un:
        out += ["", f"## {T['unowned']}", "", T["unowned_note"], ""]
        plugs = {Path(u["name"]).stem.lower(): u["name"] for u in un if u["kind"] == "plugin"}
        with_bsas: dict[str, list[str]] = {}
        alone = []
        for u in un:
            if u["kind"] == "plugin":
                continue
            s = Path(u["name"]).stem.lower()
            base = s[:-11] if s.endswith(" - textures") else s
            if u["kind"] == "bsa" and base in plugs:
                with_bsas.setdefault(plugs[base], []).append(u["name"])
            else:
                alone.append(u["name"])
        for u in un:
            if u["kind"] == "plugin":
                extra = with_bsas.get(u["name"])
                found = _ident_text(links.get(u["name"].lower()), T, Path(u["name"]).stem)
                out.append(f"- `{_cell(u['name'])}`" +
                           (f" + {', '.join(_cell(b) for b in extra)}" if extra else "") +
                           (f" · {found}" if found else ""))
        out += [f"- `{_cell(n)}`" for n in alone]
    out += ["", f"## {T['order']}", ""]
    low_files = {f.lower() for f in files}
    for i, e in enumerate(recipe.get("load_order") or [], 1):
        name = e.lstrip("#").strip()
        tags = []
        if e.startswith("#"):
            tags.append(T["off"])
        if _is_cc(e, files):
            tags.append(T["cc"])
        elif name.lower() not in low_files and files:
            tags.append(T["missing"])
        out.append(f"{i}. `{_cell(name)}`" + (f" ({', '.join(tags)})" if tags else ""))
    out += ["", f"## {T['inis']}", ""]
    for ini in recipe.get("inis") or []:
        out.append(f"### {_cell(ini['name'])}")
        out.append("")
        for k, v in (ini.get("archives") or {}).items():
            out.append(f"- `{k}`: {', '.join(_cell(b) for b in v) or '(-)'}")
        if ini.get("stest"):
            out.append(f"- {T['stest']}: {', '.join(_cell(s) for s in ini['stest'])}")
        out.append("")
    if p.get("other_inis"):
        out.append(f"{T['other_inis']}: {', '.join(_cell(x) for x in p['other_inis'])}")
        out.append("")
    if recipe.get("renames"):
        out += [f"## {T['renames']}", ""]
        out += [f"- `{_cell(o)}` → `{_cell(n)}`" for n, o in recipe["renames"].items()]
        out.append("")
    if recipe.get("kept_duplicates"):
        out += [f"## {T['kept']}", ""]
        out += [f"- {_cell(k)}" for k in recipe["kept_duplicates"]]
        out.append("")
    if recipe.get("loot"):
        out += [f"## {T['loot']}", ""]
        for e in recipe["loot"].values():
            bits = []
            if e.get("group"):
                bits.append(f"{T['group']} {_cell(e['group'])}")
            if e.get("after"):
                bits.append(f"{T['after']} {', '.join(_cell(a) for a in e['after'])}")
            if e.get("note"):
                bits.append(f"{T['note']}: {_cell(e['note'])}")
            out.append(f"- `{_cell(e.get('name'))}`: {'; '.join(bits)}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# ================================================================ diff
def _mod_facts(m: dict, files: dict) -> dict:
    src = m.get("source") or {}
    nx = nexus_of(src) or {}
    conv = m.get("converted") or {}
    names = (m.get("plugins") or []) + (m.get("bsas") or [])
    return {
        "version": nx.get("version"), "nexus_file": nx.get("file_id"),
        "source": src.get("md5") or src.get("fingerprint") or src.get("file"),
        "plugins": sorted(m.get("plugins") or []), "bsas": sorted(m.get("bsas") or []),
        "ini": sorted(f"{e.get('key')}:{e.get('bsa')}" for e in m.get("ini") or []),
        "settings": {k: conv.get(k) for k in ("preset", "sdk", "bc1") if k in conv} or None,
        "fomod": m.get("fomod") or None, "renamed": m.get("renamed") or {},
        "files": {n: _file_sig(files.get(n)) for n in sorted(names)},
    }


def _file_sig(f: dict | None):
    if not f:
        return None
    return f.get("sha1") or f"{f.get('size')}"


def _moves(old: list[str], new: list[str]) -> list[dict]:
    """Entries present in both lists whose relative order changed (the fewest
    entries that explain the change)."""
    olow, nlow = [e.lower() for e in old], [e.lower() for e in new]
    common = set(olow) & set(nlow)
    a = [e for e in olow if e in common]
    b = [e for e in nlow if e in common]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    stay = set()
    for blk in sm.get_matching_blocks():
        stay |= set(a[blk.a:blk.a + blk.size])
    out = []
    for i, e in enumerate(nlow):
        if e in common and e not in stay:
            out.append({"name": new[i], "from": olow.index(e) + 1, "to": i + 1})
    return out


def diff(old: dict, new: dict) -> dict:
    """What changed between two recipes of the same pack."""
    of, nf = old.get("files") or {}, new.get("files") or {}
    om = {m["id"]: m for m in old.get("mods") or []}
    nm = {m["id"]: m for m in new.get("mods") or []}
    changed = []
    for mid in [k for k in nm if k in om]:
        a, b = _mod_facts(om[mid], of), _mod_facts(nm[mid], nf)
        ch = [{"field": k, "old": a[k], "new": b[k]} for k in a if a[k] != b[k]]
        if ch:
            changed.append({"id": mid, "changes": ch})
    ol, nl = old.get("load_order") or [], new.get("load_order") or []
    olow, nlow = {e.lower() for e in ol}, {e.lower() for e in nl}
    inis = []
    oi = {i["name"].lower(): i for i in old.get("inis") or []}
    ni = {i["name"].lower(): i for i in new.get("inis") or []}
    for k in sorted(set(oi) | set(ni)):
        a, b = oi.get(k), ni.get(k)
        if a is None or b is None:
            inis.append({"ini": (a or b)["name"], "added": a is None, "removed": b is None, "keys": {}})
            continue
        keys = {}
        for key in sorted(set(a.get("archives") or {}) | set(b.get("archives") or {})):
            la, lb = (a.get("archives") or {}).get(key, []), (b.get("archives") or {}).get(key, [])
            if la != lb:
                sa, sb = {x.lower() for x in la}, {x.lower() for x in lb}
                keys[key] = {"added": [x for x in lb if x.lower() not in sa],
                             "removed": [x for x in la if x.lower() not in sb],
                             "reordered": sa == sb}
        st = None
        if (a.get("stest") or []) != (b.get("stest") or []):
            st = {"old": a.get("stest") or [], "new": b.get("stest") or []}
        if keys or st or a.get("sha1") != b.get("sha1"):
            inis.append({"ini": b["name"], "keys": keys, "stest": st,
                         "other": not keys and not st and a.get("sha1") != b.get("sha1")})
    fch = [n for n in nf if n in of and _file_sig(of[n]) != _file_sig(nf[n])]
    ou = {u["name"].lower(): u["name"] for u in old.get("unowned") or []}
    nu = {u["name"].lower(): u["name"] for u in new.get("unowned") or []}
    oloot, nloot = old.get("loot") or {}, new.get("loot") or {}
    return {
        "old": old.get("created"), "new": new.get("created"),
        "edition": None if (old.get("pack") or {}).get("edition") == (new.get("pack") or {}).get("edition")
        else {"old": (old.get("pack") or {}).get("edition"), "new": (new.get("pack") or {}).get("edition")},
        "mods": {"added": [k for k in nm if k not in om], "removed": [k for k in om if k not in nm],
                 "changed": changed},
        "load_order": {"added": [e for e in nl if e.lower() not in olow],
                       "removed": [e for e in ol if e.lower() not in nlow],
                       "moved": _moves(ol, nl)},
        "inis": inis,
        "files": {"added": [n for n in nf if n not in of], "removed": [n for n in of if n not in nf],
                  "changed": fch},
        "unowned": {"added": [v for k, v in nu.items() if k not in ou],
                    "removed": [v for k, v in ou.items() if k not in nu]},
        "renames": {"added": {k: v for k, v in (new.get("renames") or {}).items()
                              if k not in (old.get("renames") or {})},
                    "removed": {k: v for k, v in (old.get("renames") or {}).items()
                                if k not in (new.get("renames") or {})}},
        "kept_duplicates": {"added": [x for x in new.get("kept_duplicates") or []
                                      if x not in (old.get("kept_duplicates") or [])],
                            "removed": [x for x in old.get("kept_duplicates") or []
                                        if x not in (new.get("kept_duplicates") or [])]},
        "loot": {"changed": sorted(k for k in set(oloot) | set(nloot) if oloot.get(k) != nloot.get(k))},
    }


DIFF_TXT = {
    "en": {
        "same": "Nothing changed.", "edition": "Edition: {old} → {new}",
        "mod_added": "Mod added: {x}", "mod_removed": "Mod removed: {x}",
        "mod_changed": "Mod changed: {x} ({what})",
        "f_version": "version {old} → {new}", "f_nexus_file": "Nexus file", "f_source": "source file",
        "f_plugins": "plugins", "f_bsas": "BSAs", "f_ini": "ini entries", "f_settings": "conversion settings",
        "f_fomod": "FOMOD options", "f_renamed": "renamed plugins", "f_files": "file contents",
        "lo_added": "In the load list now: {x}", "lo_removed": "Out of the load list: {x}",
        "lo_moved": "Moved in the load list: {x} (position {a} → {b})",
        "ini_added": "New ini: {x}", "ini_removed": "Ini removed: {x}",
        "ini_key": "{ini}, {key}: {what}", "ini_plus": "added {x}", "ini_minus": "removed {x}",
        "ini_reorder": "same BSAs, new order", "ini_stest": "{ini}: sTestFile plugins changed",
        "ini_other": "{ini}: other settings changed",
        "files_changed": "Files changed in Data: {x}", "un_added": "New files with no known source: {x}",
        "un_removed": "Files with no known source that are gone: {x}",
        "ren_added": "New safe renames: {x}", "kept_added": "Duplicates kept: {x}",
        "loot": "Load order choices changed: {x}",
    },
    "es": {
        "same": "No cambió nada.", "edition": "Edición: {old} → {new}",
        "mod_added": "Mod agregado: {x}", "mod_removed": "Mod quitado: {x}",
        "mod_changed": "Mod con cambios: {x} ({what})",
        "f_version": "versión {old} → {new}", "f_nexus_file": "archivo de Nexus", "f_source": "archivo de origen",
        "f_plugins": "plugins", "f_bsas": "BSA", "f_ini": "entradas de ini", "f_settings": "ajustes de conversión",
        "f_fomod": "opciones FOMOD", "f_renamed": "plugins renombrados", "f_files": "contenido de archivos",
        "lo_added": "Ahora en la lista de carga: {x}", "lo_removed": "Salió de la lista de carga: {x}",
        "lo_moved": "Cambió de lugar en la lista de carga: {x} (posición {a} → {b})",
        "ini_added": "Ini nuevo: {x}", "ini_removed": "Ini quitado: {x}",
        "ini_key": "{ini}, {key}: {what}", "ini_plus": "se agregó {x}", "ini_minus": "se quitó {x}",
        "ini_reorder": "mismos BSA, otro orden", "ini_stest": "{ini}: cambiaron los plugins de sTestFile",
        "ini_other": "{ini}: cambiaron otros ajustes",
        "files_changed": "Archivos de Data con cambios: {x}", "un_added": "Archivos nuevos sin origen conocido: {x}",
        "un_removed": "Archivos sin origen conocido que ya no están: {x}",
        "ren_added": "Renombres seguros nuevos: {x}", "kept_added": "Duplicados que se dejaron: {x}",
        "loot": "Cambiaron elecciones de orden: {x}",
    },
}


def _join(xs, n: int = 8) -> str:
    xs = [str(x) for x in xs]
    return ", ".join(xs[:n]) + (f" (+{len(xs) - n})" if len(xs) > n else "")


def diff_text(d: dict, lang: str = "en") -> list[str]:
    T = DIFF_TXT.get(lang, DIFF_TXT["en"])
    out = []
    if d.get("edition"):
        out.append(T["edition"].format(**d["edition"]))
    out += [T["mod_added"].format(x=x) for x in d["mods"]["added"]]
    out += [T["mod_removed"].format(x=x) for x in d["mods"]["removed"]]
    for c in d["mods"]["changed"]:
        what = []
        for ch in c["changes"]:
            if ch["field"] == "version":
                what.append(T["f_version"].format(old=ch["old"] or "?", new=ch["new"] or "?"))
            else:
                what.append(T["f_" + ch["field"]])
        out.append(T["mod_changed"].format(x=c["id"], what=", ".join(what)))
    lo = d["load_order"]
    if lo["added"]:
        out.append(T["lo_added"].format(x=_join(lo["added"])))
    if lo["removed"]:
        out.append(T["lo_removed"].format(x=_join(lo["removed"])))
    out += [T["lo_moved"].format(x=m["name"], a=m["from"], b=m["to"]) for m in lo["moved"]]
    for i in d["inis"]:
        if i.get("added"):
            out.append(T["ini_added"].format(x=i["ini"]))
            continue
        if i.get("removed"):
            out.append(T["ini_removed"].format(x=i["ini"]))
            continue
        for key, v in (i.get("keys") or {}).items():
            what = []
            if v["added"]:
                what.append(T["ini_plus"].format(x=_join(v["added"])))
            if v["removed"]:
                what.append(T["ini_minus"].format(x=_join(v["removed"])))
            if not what and v.get("reordered"):
                what.append(T["ini_reorder"])
            out.append(T["ini_key"].format(ini=i["ini"], key=key, what="; ".join(what)))
        if i.get("stest"):
            out.append(T["ini_stest"].format(ini=i["ini"]))
        if i.get("other"):
            out.append(T["ini_other"].format(ini=i["ini"]))
    owned_changes = {n for c in d["mods"]["changed"] for ch in c["changes"] if ch["field"] == "files"
                     for n in (ch["new"] or {})}
    loose = [f for f in d["files"]["changed"] if f not in owned_changes]
    if loose:
        out.append(T["files_changed"].format(x=_join(loose)))
    if d["unowned"]["added"]:
        out.append(T["un_added"].format(x=_join(d["unowned"]["added"])))
    if d["unowned"]["removed"]:
        out.append(T["un_removed"].format(x=_join(d["unowned"]["removed"])))
    if d["renames"]["added"]:
        out.append(T["ren_added"].format(x=_join(f"{o} → {n}" for n, o in d["renames"]["added"].items())))
    if d["kept_duplicates"]["added"]:
        out.append(T["kept_added"].format(x=_join(d["kept_duplicates"]["added"])))
    if d["loot"]["changed"]:
        out.append(T["loot"].format(x=_join(d["loot"]["changed"])))
    return out or [T["same"]]


# ================================================================ verify
VERIFY_TXT = {
    "missing": ("{f} is gone from Data", "{f} ya no está en Data"),
    "changed": ("{f} changed since the recipe", "{f} cambió desde la receta"),
    "touched": ("{f} has the same size but a newer date; it may have changed",
                "{f} tiene el mismo tamaño pero otra fecha; puede haber cambiado"),
    "extra": ("{f} is in Data but not in the recipe", "{f} está en Data pero no en la receta"),
    "order": ("The load list changed since the recipe", "La lista de carga cambió desde la receta"),
    "ini": ("{f} changed since the recipe", "{f} cambió desde la receta"),
    "ini-missing": ("{f} is gone", "{f} ya no está"),
    "edition": ("The pack's edition changed ({old} → {new})", "La edición del pack cambió ({old} → {new})"),
}


def _v(kind: str, f: str | None = None, mod: str | None = None, **kw) -> dict:
    en, es = VERIFY_TXT[kind]
    return {"kind": kind, "file": f, "mod": mod, **kw,
            "en": en.format(f=f, **kw), "es": es.format(f=f, **kw)}


def verify(pack, recipe: dict, full: bool = False) -> list[dict]:
    """What in the pack no longer matches the recipe. Cheap by default:
    plugins are hashed, BSAs compared by size and date (by hash with
    full=True when the recipe has their hashes)."""
    out = []
    files = recipe.get("files") or {}
    owner = {n.lower(): m["id"] for m in recipe.get("mods") or [] for n in m["plugins"] + m["bsas"]}
    now = {p.name.lower(): p for p in pack.data_files.values()
           if p.suffix.lower() in PLUGIN_EXT or p.suffix.lower() == ".bsa"}
    ed = (recipe.get("pack") or {}).get("edition")
    if ed and ed != pack.mode:
        out.append(_v("edition", old=ed, new=pack.mode))
    for name, f in files.items():
        p = now.get(name.lower())
        mod = owner.get(name.lower())
        if p is None:
            out.append(_v("missing", name, mod))
            continue
        try:
            st = p.stat()
        except OSError:
            out.append(_v("missing", name, mod))
            continue
        if st.st_size != f.get("size"):
            out.append(_v("changed", name, mod, how="size"))
        elif f.get("sha1") and (f.get("kind") == "plugin" or full):
            if sha1_file(p) != f["sha1"]:
                out.append(_v("changed", name, mod, how="sha1"))
        elif f.get("mtime") is not None and abs(st.st_mtime - f["mtime"]) > MTIME_SLACK:
            out.append(_v("touched", name, mod, how="mtime"))
    known = {n.lower() for n in files}
    for low, p in sorted(now.items()):
        if low not in known:
            out.append(_v("extra", p.name, None))
    if [e for e in pack.list_entries] != list(recipe.get("load_order") or []):
        lo_diff = diff({"load_order": recipe.get("load_order") or []},
                       {"load_order": list(pack.list_entries)})["load_order"]
        out.append(_v("order", (recipe.get("pack") or {}).get("list_file"), None, detail=lo_diff))
    have = {i.path.name.lower(): i for i in pack.inis}
    for ini in recipe.get("inis") or []:
        cur = have.get(ini["name"].lower())
        if cur is None:
            out.append(_v("ini-missing", ini["name"]))
            continue
        try:
            raw = cur.path.read_bytes()
        except OSError:
            raw = b""
        if hashlib.sha1(raw).hexdigest() != ini.get("sha1"):
            out.append(_v("ini", ini["name"]))
    return out


# ================================================================ sources for a rebuild
def _index(search_dirs) -> tuple[dict, dict, dict]:
    by_name_size: dict[tuple[str, int], list[Path]] = {}
    by_size: dict[int, list[Path]] = {}
    dirs: dict[str, list[Path]] = {}
    for d in search_dirs or []:
        d = Path(d)
        if not d.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(d):
            dirnames[:] = [x for x in dirnames if x != ".skynx"]
            for x in dirnames:
                dirs.setdefault(x.lower(), []).append(Path(dirpath) / x)
            for x in filenames:
                p = Path(dirpath) / x
                try:
                    s = p.stat().st_size
                except OSError:
                    continue
                by_name_size.setdefault((x.lower(), s), []).append(p)
                by_size.setdefault(s, []).append(p)
    return by_name_size, by_size, dirs


def missing_sources(recipe: dict, search_dirs) -> list[dict]:
    """Where each mod's original download is now: [{mod, kind, file, found,
    by}] with by = "md5" (same bytes, any name), "name+size", "fingerprint"
    (folders), "name" (old records with only a name) or None. Groundwork for
    rebuilding a pack from its recipe."""
    by_name_size, by_size, dirs = _index(search_dirs)
    md5_cache: dict[str, str] = {}

    def md5(p: Path) -> str | None:
        k = str(p)
        if k not in md5_cache:
            try:
                md5_cache[k] = md5_file(p)
            except OSError:
                md5_cache[k] = ""
        return md5_cache[k] or None

    out = []
    for m in recipe.get("mods") or []:
        src = m.get("source") or {}
        look = src
        if src.get("kind") == "pack" and isinstance(src.get("origin"), dict):
            look = src["origin"]       # the download the source pack's mod came from
        row = {"mod": m["id"], "kind": src.get("kind"), "file": look.get("file"),
               "found": None, "by": None}
        out.append(row)
        orig = Path(look["path"]) if look.get("path") else None
        name = (look.get("file") or "").lower()
        size = look.get("size")
        if look.get("md5"):
            cands = []
            if orig is not None and orig.is_file():
                cands.append(orig)
            cands += sorted(by_size.get(size, []), key=lambda p: (p.name.lower() != name, str(p)))
            for p in cands:
                if md5(p) == look["md5"]:
                    row["found"], row["by"] = str(p), "md5"
                    break
            continue
        if look.get("fingerprint"):
            cands = [orig] if orig is not None and orig.is_dir() else []
            cands += dirs.get(name, [])
            for p in cands:
                if folder_fingerprint(p) == look["fingerprint"]:
                    row["found"], row["by"] = str(p), "fingerprint"
                    break
            continue
        if src.get("kind") == "pack" and look is src:
            continue                   # a pack's own mod: no download to look for
        if name and size is not None and by_name_size.get((name, size)):
            row["found"], row["by"] = str(by_name_size[(name, size)][0]), "name+size"
        elif name and look.get("legacy"):
            hit = (orig if orig is not None and orig.exists() else None) or \
                next((p for (n, _s), ps in by_name_size.items() if n == name for p in ps), None) or \
                (dirs.get(name) or [None])[0]
            if hit:
                row["found"], row["by"] = str(hit), "name"
    return out
