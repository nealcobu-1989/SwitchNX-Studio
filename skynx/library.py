"""The Library: the user's modpacks and loose mods, in one place.

    <library root>/            default C:\\SkyNX\\Library (or $SKYNX_LIBRARY)
        Packs/<name>/          modpacks imported from a .zip/.7z, normalised so
                               the two title folders sit at the top
        Mods/                  loose mods (archives or folders)
        Drafts/<name>/         packs being created (see draft.py)
        Converted/<name>/      mods this app converted, kept to reuse in other
                               packs (plugins, BSAs and skynx-mod.json)
        .library.json          folders registered in place, and a health cache

Folders are never copied or moved: importing a folder, or adding an external
one (like C:\\SkyNX\\Other modpacks\\*), just records its path. Archives are
extracted with the same zip-slip checks as builder._extract, and an existing
pack folder is never overwritten (a " (2)" suffix is added).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid
from collections import Counter
from pathlib import Path

from . import knowledge as K
from .errors import SkynxError
from .intake import ARCHIVE_EXT, archive_type, detect, list_names, safe_extract, _title_layout

DEFAULT_ROOT = Path(r"C:\SkyNX\Library")
DB_NAME = ".library.json"
SEVERITIES = ("critico", "aviso", "ahorro", "info")
# Google Drive splits big folder downloads: "Pack-20261020T151515Z-001.zip", "-002.zip"...
DRIVE_PART = re.compile(r"^(?P<base>.+)-(?P<stamp>\d{8}T\d{6}Z)-(?P<part>\d{3})$")


class LibraryError(SkynxError):
    pass


def default_root() -> Path:
    env = os.environ.get("SKYNX_LIBRARY")
    return Path(env) if env else DEFAULT_ROOT


def ensure(library_root: Path | None = None) -> Path:
    root = Path(library_root or default_root())
    (root / "Mods").mkdir(parents=True, exist_ok=True)
    (root / "Converted").mkdir(parents=True, exist_ok=True)
    (root / "Projects").mkdir(parents=True, exist_ok=True)
    return root


def _children(d: Path) -> list[Path]:
    return sorted(d.iterdir()) if d.is_dir() else []


# ---------------------------------------------------------------- database
def _db_path(root: Path) -> Path:
    return Path(root) / DB_NAME


def _load_db(root: Path) -> dict:
    p = _db_path(root)
    try:
        db = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(db, dict):
            db.setdefault("entries", [])
            db.setdefault("cache", {})
            return db
    except (OSError, ValueError):
        pass
    return {"version": 1, "entries": [], "cache": {}}


def _save_db(root: Path, db: dict) -> None:
    p = _db_path(root)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(db, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)


def _key(p: Path) -> str:
    return os.path.normcase(os.path.abspath(str(p)))


def _record(root: Path, entry: dict) -> dict:
    db = _load_db(root)
    db["entries"] = [e for e in db["entries"] if _key(Path(e["path"])) != _key(Path(entry["path"]))]
    db["entries"].append(entry)
    _save_db(root, db)
    return entry


# ---------------------------------------------------------------- names
def clean_name(s: str) -> str:
    """Folder name for an imported pack: no Drive download stamp, no "(1)" from
    the browser, nothing Windows refuses."""
    m = DRIVE_PART.match(s)
    if m:
        s = m.group("base")
    s = re.sub(r"\s*\(\d+\)$", "", s)
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s or "Modpack"


def _unique(parent: Path, name: str) -> Path:
    cand, n = parent / name, 2
    while cand.exists():
        cand, n = parent / f"{name} ({n})", n + 1
    return cand


def _stem(p: Path) -> str:
    name = p.name
    for ext in ARCHIVE_EXT | {".rar"}:
        if name.lower().endswith(ext):
            return name[: -len(ext)]
    return name


def drive_parts(archive: Path) -> list[Path]:
    """All parts of a split Google Drive download that sit next to this one."""
    archive = Path(archive)
    m = DRIVE_PART.match(_stem(archive))
    if not m:
        return [archive]
    pat = re.compile(re.escape(m.group("base")) + "-" + m.group("stamp") + r"-\d{3}\.zip$", re.I)
    parts = sorted(p for p in archive.parent.iterdir() if p.is_file() and pat.match(p.name))
    return parts or [archive]


# ---------------------------------------------------------------- import
def _is_pack_folder(folder: Path) -> bool:
    from .pack import _find_dir
    return bool(_find_dir(folder, K.TITLE_BASE) or _find_dir(folder, K.TITLE_AOC))


def _title_dirs(tree: Path) -> dict[str, Path]:
    """Shallowest folder named after each Skyrim title id."""
    want = {K.TITLE_BASE.lower(): "base", K.TITLE_AOC.lower(): "aoc"}
    found: dict[str, Path] = {}
    for dirpath, dirnames, _ in os.walk(tree):
        depth = len(Path(dirpath).relative_to(tree).parts)
        if depth > 6:
            dirnames[:] = []
            continue
        for d in sorted(dirnames):
            k = want.get(d.lower())
            if k and k not in found:
                found[k] = Path(dirpath) / d
        dirnames[:] = [d for d in dirnames if d.lower() not in want]
    return found


def _prune_empty(tree: Path) -> None:
    for dirpath, dirnames, filenames in sorted(os.walk(tree), key=lambda t: -len(t[0])):
        p = Path(dirpath)
        if p != tree and not any(p.iterdir()):
            p.rmdir()


def import_pack(archive_or_folder: Path, library_root: Path | None = None, progress=None) -> dict:
    """Bring a modpack into the Library.

    A folder is registered where it is. A .zip/.7z is extracted into
    Packs/<clean name>/ with the title folders (01000A10041EA000,
    01000A10041EB009) moved to the top, whatever the archive had around them
    (an atmosphere/contents tree, a folder named after the pack...). Anything
    else in the archive is kept under extras/. Split Google Drive downloads
    (-001.zip, -002.zip...) next to the given part are merged.
    Returns the library entry."""
    src = Path(archive_or_folder)
    tick = progress or (lambda *a, **k: None)
    root = ensure(library_root)
    if src.is_dir():
        if not _is_pack_folder(src):
            raise LibraryError(f"{src.name} doesn't look like a modpack: it has no {K.TITLE_BASE} or "
                               f"{K.TITLE_AOC} folder.",
                               f"{src.name} no parece un modpack: no tiene carpeta {K.TITLE_BASE} ni "
                               f"{K.TITLE_AOC}.")
        return add_external(root, src, kind="pack")
    if archive_type(src) == "rar":
        list_names(src)        # raises the bilingual .rar message
    parts = drive_parts(src)
    layouts = [_title_layout(list_names(p)) for p in parts]
    if not any(layouts):
        raise LibraryError(f"{src.name} doesn't look like a modpack: it has no {K.TITLE_BASE} or "
                           f"{K.TITLE_AOC} folder. To add a single mod, use Mods.",
                           f"{src.name} no parece un modpack: no tiene carpeta {K.TITLE_BASE} ni "
                           f"{K.TITLE_AOC}. Para agregar un solo mod, usa Mods.")
    packs = root / "Packs"
    packs.mkdir(parents=True, exist_ok=True)
    staging = packs / f".importing-{uuid.uuid4().hex[:8]}"
    final: Path | None = None
    notes: list[tuple[str, str]] = []
    try:
        for i, p in enumerate(parts):
            tick(p.name, i, len(parts))
            safe_extract(p, staging, progress)
        titles = _title_dirs(staging)
        if not titles:
            raise LibraryError("After extracting it I couldn't find the title folders.",
                               "Después de extraerlo no encontré las carpetas de título.")
        final = _unique(packs, clean_name(_stem(src)))
        final.mkdir()
        for k, d in titles.items():
            os.replace(d, final / d.name)
        _prune_empty(staging)
        if staging.exists() and any(staging.iterdir()):
            extras = final / "extras"
            os.replace(staging, extras)
            notes.append(("Files outside the Skyrim folders were kept in extras.",
                          "Los archivos fuera de las carpetas de Skyrim quedaron en extras."))
        if "base" not in titles:
            notes.append((f"It only has {K.TITLE_AOC} (the load list); there's no Data folder.",
                          f"Solo trae {K.TITLE_AOC} (la lista de carga); no hay carpeta Data."))
        if len(parts) > 1:
            notes.append((f"Google Drive split it in {len(parts)} parts; I joined them.",
                          f"Google Drive lo partió en {len(parts)} partes; las uní."))
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        if final is not None:
            shutil.rmtree(final, ignore_errors=True)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    entry = {"kind": "pack", "name": final.name, "path": str(final), "external": False,
             "source": [str(p) for p in parts] if len(parts) > 1 else str(src),
             "added": time.strftime("%Y-%m-%d %H:%M:%S"),
             "layout": "atmosphere" if any(l and "atmosphere" in l for l in layouts) else "titles",
             "notes": [list(n) for n in notes]}
    return _record(root, entry)


def import_mod(source: Path, library_root: Path | None = None, progress=None) -> dict:
    """Put a loose mod in the Library: archives are copied into Mods/ (never
    overwriting), folders are registered where they are."""
    src = Path(source)
    root = ensure(library_root)
    if src.is_dir():
        return add_external(root, src, kind="mod")
    from .intake import bundle_to_folder, loose_bundle
    if loose_bundle(src):
        dest, n = root / "Mods" / src.stem, 2
        while dest.exists():
            dest, n = root / "Mods" / f"{src.stem} ({n})", n + 1
        bundle_to_folder(src, dest)
        return _record(root, {"kind": "mod", "name": dest.name, "path": str(dest), "external": False,
                              "source": str(src), "added": time.strftime("%Y-%m-%d %H:%M:%S")})
    if archive_type(src) is None:
        raise LibraryError(f"{src.name} isn't a folder, .zip or .7z",
                           f"{src.name} no es una carpeta, ni un .zip o .7z")
    (progress or (lambda *a, **k: None))(src.name)
    stem, ext = _stem(src), src.name[len(_stem(src)):]
    dest, n = root / "Mods" / src.name, 2
    while dest.exists():
        dest, n = root / "Mods" / f"{stem} ({n}){ext}", n + 1
    shutil.copy2(src, dest)
    return _record(root, {"kind": "mod", "name": dest.name, "path": str(dest), "external": False,
                          "source": str(src), "added": time.strftime("%Y-%m-%d %H:%M:%S")})


def add_external(library_root: Path | None, path: Path, kind: str | None = None) -> dict:
    """Record a folder (or archive) that stays where it is."""
    root = ensure(library_root)
    path = Path(path)
    if not path.exists():
        raise LibraryError(f"{path} doesn't exist", f"{path} no existe")
    if kind is None:
        kind = "pack" if path.is_dir() and _is_pack_folder(path) else "mod"
    return _record(root, {"kind": kind, "name": path.name, "path": str(path), "external": True,
                          "added": time.strftime("%Y-%m-%d %H:%M:%S")})


def forget(library_root: Path | None, path: Path) -> bool:
    """Drop a registered entry. Nothing is deleted from disk."""
    root = Path(library_root or default_root())
    db = _load_db(root)
    before = len(db["entries"])
    db["entries"] = [e for e in db["entries"] if _key(Path(e["path"])) != _key(Path(path))]
    db["cache"].pop(_key(Path(path)), None)
    _save_db(root, db)
    return len(db["entries"]) != before


def owned(library_root: Path | None, path: Path) -> bool:
    """True when `path` is a copy the Library made (inside Packs/ or Mods/)."""
    root = Path(library_root or default_root())
    try:
        rel = Path(path).resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return len(rel.parts) == 2 and rel.parts[0] in ("Packs", "Mods", "Converted", "Drafts")


def remove(library_root: Path | None, path: Path) -> dict:
    """Take an entry out of the Library. Copies the Library made are deleted
    from disk (otherwise the listing finds them again); folders registered
    where they are only leave the list."""
    root = Path(library_root or default_root())
    path = Path(path)
    deleted = False
    if owned(root, path) and path.exists():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        deleted = True
    forget(root, path)
    return {"ok": True, "deleted": deleted}


# ---------------------------------------------------------------- listing
def _mtime(p: Path | None) -> float:
    try:
        return p.stat().st_mtime if p else 0.0
    except OSError:
        return 0.0


def _signature(path: Path, kind: str) -> float:
    """Changes whenever something the health summary depends on changes: the
    folder, Data (files added or removed), the load list, the inis and the
    history (every change made by the app goes through it)."""
    if kind != "pack":
        if path.is_dir():
            return max([_mtime(path)] + [_mtime(c) for c in path.iterdir()])
        return _mtime(path) + path.stat().st_size / 1e12
    from .pack import Pack
    try:
        pk = Pack.open(path)
    except Exception:  # noqa: BLE001
        return _mtime(path)
    paths = [path, pk.data_dir, pk.list_path, pk.base_romfs, path / ".skynx" / "history",
             path / ".skynx" / "mods.json"] + list(pk.ini_paths)
    return max(_mtime(p) for p in paths)


def _size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames if d != ".skynx"]
        for f in filenames:
            try:
                total += (Path(dirpath) / f).stat().st_size
            except OSError:
                pass
    return total


def pack_health(path: Path) -> dict:
    from .audit import run_audit
    from .pack import Pack
    pk = Pack.open(path)
    res = run_audit(pk, deep=False)
    counts = Counter(f.severity for f in res.findings)
    sev = {s: counts.get(s, 0) for s in SEVERITIES}
    plugins = [e for e in pk.list_entries if not pk.is_cc(e) and not e.startswith("#")]
    if sev["critico"]:
        status = "broken"
        summary = (f"{sev['critico']} problems that stop something from loading",
                   f"{sev['critico']} problemas que impiden cargar algo")
    elif sev["aviso"]:
        status = "warn"
        summary = (f"{sev['aviso']} warnings", f"{sev['aviso']} avisos")
    else:
        status = "ok"
        summary = ("No problems found", "Sin problemas")
    return {"status": status, "severity": sev, "mode": pk.mode, "plugins": len(plugins),
            "bsas": len(pk.bsas), "ccc_bytes": pk.ccc.size if pk.ccc else None,
            "archives_in_data": len(pk.archives), "summary": list(summary)}


def mod_health(path: Path) -> dict:
    d = detect(path, deep=False)
    return {"status": "ok" if d.supported and d.kind != "unknown" else "warn",
            "kind": d.kind, "action": d.action, "summary": list(d.summary),
            "plugins": len(d.evidence.get("plugins", [])), "bsas": len(d.evidence.get("bsas", []))}


def list_library(library_root: Path | None = None, progress=None, health: bool = True,
                 kinds: tuple[str, ...] | None = None) -> list[dict]:
    """Packs and loose mods: Packs/*, Mods/* and everything registered in
    place. Each row: kind, name, path, external, size, missing, health.
    Health is cached in .library.json by path and modification signature."""
    root = ensure(library_root)
    tick = progress or (lambda *a, **k: None)
    db = _load_db(root)
    rows: dict[str, dict] = {}
    for p in _children(root / "Packs"):
        if not p.name.startswith(".") and p.is_dir():
            rows[_key(p)] = {"kind": "pack", "name": p.name, "path": str(p), "external": False}
    for p in _children(root / "Mods"):
        if not p.name.startswith("."):
            rows[_key(p)] = {"kind": "mod", "name": p.name, "path": str(p), "external": False}
    for p in _children(root / "Drafts"):
        if not p.name.startswith(".") and p.is_dir():
            rows[_key(p)] = {"kind": "pack", "name": p.name, "path": str(p), "external": False, "draft": True}
    for p in _children(root / "Converted"):
        if not p.name.startswith(".") and p.is_dir():
            rows[_key(p)] = {"kind": "mod", "name": p.name, "path": str(p), "external": False,
                             "converted": True}
    for e in db["entries"]:
        k = _key(Path(e["path"]))
        row = rows.setdefault(k, {"kind": e.get("kind", "mod"), "name": e.get("name") or Path(e["path"]).name,
                                  "path": e["path"], "external": bool(e.get("external"))})
        for f in ("source", "added", "notes"):
            if f in e:
                row[f] = e[f]
    out, dirty = [], False
    items = [(k, r) for k, r in rows.items() if not kinds or r["kind"] in kinds]
    for i, (k, row) in enumerate(items):
        path = Path(row["path"])
        tick(row["name"], i, len(items))
        row["id"] = row["path"]
        row["owned"] = owned(root, path)
        row["missing"] = not path.exists()
        if row["kind"] == "pack" and not row["missing"]:
            row["draft"] = bool(row.get("draft")) or (path / ".skynx" / "draft.json").is_file()
        row["size"], row["health"] = None, None
        if row["missing"]:
            out.append(row)
            continue
        try:
            sig = _signature(path, row["kind"])
        except OSError:
            sig = 0.0
        cached = db["cache"].get(k)
        if cached and cached.get("sig") == sig and (cached.get("health") or not health):
            row["size"], row["health"] = cached.get("size"), cached.get("health")
        else:
            row["size"] = _size(path)
            if health:
                try:
                    row["health"] = pack_health(path) if row["kind"] == "pack" else mod_health(path)
                except Exception as e:  # noqa: BLE001
                    en = getattr(e, "en", str(e))
                    es = getattr(e, "es", str(e))
                    row["health"] = {"status": "error", "summary": [en, es]}
            db["cache"][k] = {"sig": sig, "size": row["size"], "health": row["health"]}
            dirty = True
        out.append(row)
    if dirty:
        _save_db(root, db)
    out.sort(key=lambda r: (r["kind"] != "pack", r["name"].lower()))
    return out
