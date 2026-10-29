"""Projects: a modpack you build, kept in a folder of its own.

    <Library>/Projects/<name>/
        skynx-project.json   what it is: name, where it started, last pack, last SD copy
        Mods/<mod>/          each mod's files (laid out as inside Data) and mod.json
        Base/                the inis, the load list, and Data files no mod owns
        Switch/              made by "Pack": the two folders that go to the console
        .skynx/work/         the working pack every tool uses (hidden)
        .skynx/...           history, trash and records, as in any pack

The working pack is an ordinary pack, so the Doctor, fixes, renames, load
order, conversions and SSEEdit work on it unchanged and every change goes to
the history. Mods/ and Base/ show the same files split by mod: they are hard
links to the working pack's files (copies where the drive can't link) and
`sync` keeps them in step after every change. A file changed or added by hand
in Mods/ or Base/ is brought into the working pack as an undoable change.

Nothing outside the project is ever written: a project made from another
pack, a zip or the SD starts as a copy (linked on the same drive), and the
source stays where it was.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from pathlib import Path

from . import knowledge as K
from .errors import SkynxError
from .pack import PROJECT_FILE, PROJECT_WORK, Pack, is_project

PROJECTS = "Projects"
MODS, BASE, OUT = "Mods", "Base", "Switch"
MOD_INFO = "mod.json"
STATE = "mirror.json"
BUILD_MARK = "skynx-build.json"
# .skynx records that travel with a pack when a project is made from it
RECORDS = ("mods.json", "renames.json", "doctor-ignore.json", "recipe.json", "project.json")


class ProjectError(SkynxError):
    pass


# ------------------------------------------------------------------ names and info
def projects_root(library_root: Path) -> Path:
    p = Path(library_root) / PROJECTS
    p.mkdir(parents=True, exist_ok=True)
    return p


def clean_name(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(s or ""))
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s[:80]


def _new_root(library_root: Path, name: str) -> Path:
    nm = clean_name(name)
    if not nm:
        raise ProjectError("Give the project a name.", "Ponle un nombre al proyecto.")
    if nm != str(name).strip():
        raise ProjectError("The name can't have < > : \" / \\ | ? *",
                           "El nombre no puede tener < > : \" / \\ | ? *")
    root = projects_root(library_root) / nm
    try:
        root.mkdir()                       # claimed now: a failed creation only removes what it made
    except FileExistsError:
        raise ProjectError(f"There's already a project called {nm}.", f"Ya hay un proyecto llamado {nm}.") from None
    return root


def read_info(root: Path) -> dict:
    try:
        d = json.loads((Path(root) / PROJECT_FILE).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def write_info(root: Path, **changes) -> dict:
    d = read_info(root)
    d.update(changes)
    p = Path(root) / PROJECT_FILE
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)
    return d


def work_root(root: Path) -> Path:
    return Path(root).joinpath(*PROJECT_WORK)


# ------------------------------------------------------------------ creating
def _finish(root: Path, name: str, origin: dict, register: bool = True, progress=None) -> Pack:
    """Mark the folder as a project (the marker goes last: a half-made folder
    never opens as a project), register its mods, and lay out Mods/ and Base/."""
    from . import draft as DR
    (root / ".skynx").mkdir(parents=True, exist_ok=True)
    if not DR.is_draft(root):
        DR.mark(root, name, origin)
    write_info(root, name=name, created=time.strftime("%Y-%m-%d %H:%M:%S"), origin=origin,
               format=1)
    pack = Pack.open(root)
    if not pack.base_dir and not pack.aoc_dir:
        raise ProjectError("The project has no Skyrim folders.", "El proyecto no tiene carpetas de Skyrim.")
    if register:
        register_rows(pack, origin)
    sync(pack, progress=progress)
    return Pack.open(root)


def _cleanup_failed(root: Path) -> None:
    shutil.rmtree(root, ignore_errors=True)


def new_empty(library_root: Path, name: str, edition: str, base: Path, cc_preset: str = "ussep",
              ussep: str | None = None, ussep_dir: Path | None = None) -> Pack:
    """A new project from the console's clean inis (builder.create_project)."""
    from .builder import create_project
    root = _new_root(library_root, name)
    work = work_root(root)
    try:
        create_project(work, edition, Path(base), cc_preset, ussep=ussep, ussep_dir=ussep_dir)
        _lift_records(work / ".skynx", root / ".skynx")
        shutil.rmtree(work / ".skynx", ignore_errors=True)
        return _finish(root, clean_name(name), {"kind": "new", "edition": edition}, register=False)
    except BaseException:
        _cleanup_failed(root)
        raise


def _lift_records(src: Path, dest: Path, extra: tuple[str, ...] = ()) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for n in RECORDS + extra:
        if (src / n).is_file():
            shutil.copy2(src / n, dest / n)
    if (src / "recipes").is_dir():
        shutil.copytree(src / "recipes", dest / "recipes", dirs_exist_ok=True)


def from_pack(library_root: Path, name: str, src: Path, progress=None, link: bool = False) -> Pack:
    """A new project that starts as an exact copy of a modpack: a folder, a
    .zip/.7z/.rar (split Google Drive downloads are joined), or another
    project. The source is not touched. A pack being created keeps which mods
    don't go. link=True shares the files with the source on the same drive
    (no extra space), but then a program that edits a file in place would
    change the source too, so it's off unless the person turns it on."""
    from . import draft as DR
    src = Path(src)
    root = _new_root(library_root, name)
    work = work_root(root)
    try:
        if src.is_file():
            origin = _extract_pack(src, root, work, progress)
        else:
            sp = Pack.open(src)
            if not sp.base_dir and not sp.aoc_dir:
                raise ProjectError(f"{src.name} doesn't look like a modpack: it has no {K.TITLE_BASE} or "
                                   f"{K.TITLE_AOC} folder.",
                                   f"{src.name} no parece un modpack: no tiene carpeta {K.TITLE_BASE} ni "
                                   f"{K.TITLE_AOC}.")
            work.mkdir(parents=True)
            stats = DR._copy_pack(sp, work, set(), progress, link, records=False)
            _lift_records(src / ".skynx", root / ".skynx", extra=("draft.json",))
            origin = {"kind": "project" if sp.project else "pack", "path": str(src),
                      "name": read_info(src).get("name") or src.name, "files": stats}
        nm = clean_name(name)
        if DR.is_draft(root):              # a pack being created: same parked mods, new name
            d = DR.load(root)
            d["name"] = nm
            d["origin"] = origin
            DR._save(root, d)
        return _finish(root, nm, origin, register=True, progress=progress)
    except BaseException:
        _cleanup_failed(root)
        raise


def _extract_pack(archive: Path, root: Path, work: Path, progress=None) -> dict:
    from .intake import archive_type, list_names, safe_extract, _title_layout
    from .library import _title_dirs, clean_name as lib_clean, drive_parts
    if archive_type(archive) is None:
        raise ProjectError(f"{archive.name} isn't a folder, .zip, .7z or .rar.",
                           f"{archive.name} no es una carpeta, ni un .zip, .7z o .rar.")
    parts = drive_parts(archive)
    if not any(_title_layout(list_names(p)) for p in parts):
        raise ProjectError(f"{archive.name} doesn't look like a modpack: it has no {K.TITLE_BASE} or "
                           f"{K.TITLE_AOC} folder. To add a single mod, use Add mods.",
                           f"{archive.name} no parece un modpack: no tiene carpeta {K.TITLE_BASE} ni "
                           f"{K.TITLE_AOC}. Para agregar un solo mod, usa Agregar mods.")
    staging = root / ".skynx" / "import"
    for i, p in enumerate(parts):
        if progress:
            progress(p.name, i, len(parts))
        safe_extract(p, staging, progress)
    titles = _title_dirs(staging)
    if not titles:
        raise ProjectError("After extracting it I couldn't find the title folders.",
                           "Después de extraerlo no encontré las carpetas de título.")
    work.mkdir(parents=True)
    for d in titles.values():
        os.replace(d, work / d.name)
    shutil.rmtree(staging, ignore_errors=True)
    return {"kind": "archive", "path": str(archive), "name": lib_clean(archive.stem),
            "parts": len(parts)}


def from_sd(library_root: Path, name: str, sd_root: Path, progress=None) -> Pack:
    """A new project with what's on the SD (it's only read)."""
    from .deploy import import_from_sd
    root = _new_root(library_root, name)
    try:
        import_from_sd(Path(sd_root), work_root(root), progress)
        return _finish(root, clean_name(name), {"kind": "sd", "path": str(sd_root)}, register=True,
                       progress=progress)
    except BaseException:
        _cleanup_failed(root)
        raise


def register_rows(pack: Pack, origin: dict) -> int:
    """Give every plugin (with its BSAs) and every ini-loaded BSA of a pack a
    mod record, so each one has a stable id and folder even after renames."""
    from .builder import _mods_file, load_mods, mods_view
    mods = load_mods(pack)
    n = 0
    src = {"kind": origin.get("kind", "pack"), "pack": origin.get("name"), "path": origin.get("path")}
    for r in mods_view(pack):
        if r["kind"] == "mod":
            continue
        base = Path(r["name"]).stem if r["plugins"] else Path(r["name"]).stem
        mid, k = base, 2
        while mid in mods:
            mid, k = f"{base} ({k})", k + 1
        mods[mid] = {"added": time.strftime("%Y-%m-%d %H:%M:%S"), "plugins": list(r["plugins"]),
                     "bsas": list(r["bsas"]), "ini": [], "source": dict(src),
                     "from_pack": origin.get("name"), "reason": "project"}
        n += 1
    if n:
        f = _mods_file(pack)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(mods, indent=1, ensure_ascii=False), encoding="utf-8")
    return n


# ------------------------------------------------------------------ Mods/ and Base/
def _rows(pack: Pack) -> list[dict]:
    """Every mod of the project, those that don't go included (goes=False)."""
    from . import draft as DR
    from .builder import load_mods, mods_view
    d = DR.load(pack.root) or {"excluded": {}}
    parked = DR.excluded_files(pack.root)
    rows = []
    for r in mods_view(pack):
        if r["id"] in d["excluded"]:
            continue
        files = {f.lower() for f in r.get("plugins", []) + r.get("bsas", [])}
        if files and files <= parked:        # parked under another id
            continue
        rows.append(dict(r, goes=True))
    for rid, rec in d["excluded"].items():
        rows.append({"id": rid, "name": rec.get("name") or rid, "kind": rec.get("kind") or "mod",
                     "plugins": rec.get("plugins", []), "bsas": rec.get("bsas", []), "goes": False})
    reg = load_mods(pack)
    for r in rows:
        r["record"] = reg.get(r["id"]) or {}
    return rows


def _folder(name: str) -> str:
    s = clean_name(name).rstrip(".") or "Mod"
    return s


def _folders(rows: list[dict]) -> dict[str, str]:
    """A folder name per mod, stable (same rows, same names) and unique
    regardless of case."""
    out, used = {}, set()
    for r in sorted(rows, key=lambda r: (str(r["id"]).lower(), str(r["id"]))):
        base = _folder(r["name"] if r.get("kind") == "mod" else Path(r["name"]).stem)
        f, k = base, 2
        while f.lower() in used or f.lower() in ("base", "switch"):
            f, k = f"{base} ({k})", k + 1
        used.add(f.lower())
        out[r["id"]] = f
    return out


def folders_for(pack: Pack) -> dict[str, str]:
    """{mod id: its folder in Mods/}."""
    return _folders(_rows(pack))


def _owner_index(rows: list[dict]) -> tuple[dict[str, str], dict[str, str]]:
    """(top-level Data file -> mod id, plugin name/stem -> mod id)."""
    top, plug = {}, {}
    for r in rows:
        for f in r.get("plugins", []) + r.get("bsas", []):
            top[f.lower()] = r["id"]
        for p in r.get("plugins", []):
            plug[p.lower()] = r["id"]
            plug.setdefault(Path(p).stem.lower(), r["id"])
    return top, plug


def _owner_of(rel_parts: list[str], top: dict, plug: dict) -> str | None:
    low = [x.lower() for x in rel_parts]
    if len(low) == 1:
        return top.get(low[0])
    # FaceGen, voices, SEQ...: a folder or file named after the plugin
    for x in low[:-1]:
        if x in plug:
            return plug[x]
    stem = Path(low[-1]).stem
    if low[0] == "seq" and stem in plug:
        return plug[stem]
    return None


def _walk_files(base: Path):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if not d.startswith(".skynx")]
        for fn in filenames:
            if fn.endswith((".skynx-tmp", ".skynx-ren", ".skynx-undo", ".skynx-mirror")):
                continue
            yield Path(dirpath) / fn


def desired(pack: Pack) -> tuple[dict[str, Path], dict[str, dict]]:
    """{path below the project root: file of the working pack it shows} and
    {mod folder: its rows info}."""
    rows = _rows(pack)
    folders = _folders(rows)
    top, plug = _owner_index(rows)
    out: dict[str, Path] = {}
    if pack.data_dir and pack.data_dir.is_dir():
        for p in _walk_files(pack.data_dir):
            parts = list(p.relative_to(pack.data_dir).parts)
            owner = _owner_of(parts, top, plug)
            tgt = (f"{MODS}/{folders[owner]}/" if owner else f"{BASE}/Data/") + "/".join(parts)
            out[tgt] = p
    special = {x.resolve() for x in pack.ini_paths + pack.other_inis if x.exists()}
    for f in (pack.ccc_path, pack.plugins_path):
        if f and f.exists():
            special.add(f.resolve())
    for tag, d in (("base", pack.base_dir), ("aoc", pack.aoc_dir)):
        if not d or not d.is_dir():
            continue
        for p in _walk_files(d):
            if pack.data_dir and pack.data_dir in p.parents:
                continue
            if p.resolve() in special:
                out[f"{BASE}/{p.name}"] = p
            else:
                out[f"{BASE}/Other/{tag}/" + p.relative_to(d).as_posix()] = p
    info = {folders[r["id"]]: r for r in rows}
    return out, info


def _stat(p: Path) -> list | None:
    try:
        s = p.stat()
        return [s.st_ino, s.st_size, s.st_mtime_ns]
    except OSError:
        return None


def _same(a: Path, b: Path) -> bool:
    """The same file on disk (a hard link). Network drives that report no file
    ids would make every pair look the same: those never count."""
    try:
        sa, sb = a.stat(), b.stat()
    except OSError:
        return False
    return bool(sa.st_ino) and sa.st_ino == sb.st_ino and sa.st_dev == sb.st_dev


def _replace(tmp: Path, dest: Path) -> None:
    try:
        os.replace(tmp, dest)
    except PermissionError:
        # a read-only file on Windows; every name of it lives inside the project
        if dest.exists():
            os.chmod(dest, 0o666)
        os.replace(tmp, dest)


def _place(src: Path, dest: Path, link: bool = True) -> str:
    """dest becomes the same file as src: a hard link, or a copy."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".skynx-mirror")
    if tmp.exists():
        tmp.unlink()
    how = "copy"
    if link:
        try:
            os.link(src, tmp)
            how = "link"
        except OSError:
            pass
    if how == "copy":
        shutil.copy2(src, tmp)
    _replace(tmp, dest)
    return how


def _aside(root: Path, rel: str, src: Path, move: bool) -> Path:
    """Keep a file the person touched in .skynx/mirror-conflicts instead of losing it."""
    keep = root / ".skynx" / "mirror-conflicts" / time.strftime("%Y%m%d-%H%M%S") / rel
    keep.parent.mkdir(parents=True, exist_ok=True)
    n = 2
    while keep.exists():
        keep = keep.with_name(f"{keep.stem} ({n}){keep.suffix}")
        n += 1
    if move:
        shutil.move(str(src), str(keep))
    else:
        shutil.copy2(src, keep)
    return keep


def _load_state(root: Path) -> dict:
    try:
        d = json.loads((Path(root) / ".skynx" / STATE).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(root: Path, state: dict) -> None:
    p = Path(root) / ".skynx" / STATE
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)


GAME_DIRS = {"meshes", "textures", "sound", "music", "scripts", "interface", "seq", "strings", "lodsettings",
             "grass", "shadersfx", "video", "dialogueviews", "source", "skse", "calientetools", "nemesis_engine",
             "actors", "facegen", "materials", "lightingtemplates", "vis"}
GAME_TOP_EXT = {".esp", ".esm", ".esl", ".bsa", ".ini", ".seq"}


def _work_target(pack: Pack, rel: str) -> Path | None:
    """Where a file added by hand to Mods/ or Base/ goes in the working pack.
    Only game files: a readme or a picture dropped next to a mod stays where it is."""
    parts = rel.split("/")
    inner = None
    if parts[0] == MODS and len(parts) >= 3:
        inner = parts[2:]
    elif parts[0] == BASE and len(parts) >= 3 and parts[1] == "Data":
        inner = parts[2:]
    if not inner or not pack.data_dir:
        return None
    if len(inner) == 1:
        if Path(inner[0]).suffix.lower() not in GAME_TOP_EXT or inner[0].lower() == MOD_INFO:
            return None
    elif inner[0].lower() not in GAME_DIRS:
        return None
    return pack.data_dir.joinpath(*inner)


def _mod_info(folder: str, row: dict) -> dict:
    rec = row.get("record") or {}
    src = rec.get("source") or {}
    out = {"name": row.get("name") or folder, "id": row["id"], "goes": bool(row.get("goes", True)),
           "plugins": row.get("plugins", []), "bsas": row.get("bsas", []),
           "added": rec.get("added"), "source": src or None}
    for k in ("version", "nexus", "converted", "renamed", "from_pack"):
        if rec.get(k):
            out[k] = rec[k]
    nx = src.get("nexus") if isinstance(src, dict) else None
    if nx and not out.get("version") and nx.get("version"):
        out["version"] = nx.get("version")
    return out


def _linkable(tgt: str) -> bool:
    """Files shown in Base/ itself (inis, the load list) are real copies, so an
    editor that saves in place can't change the project without the history."""
    return not (tgt.startswith(BASE + "/") and tgt.count("/") == 1)


def sync(pack: Pack, progress=None) -> dict:
    """Bring hand edits made in Mods/ and Base/ into the working pack (one
    undoable change), then make Mods/ and Base/ show the working pack again."""
    from .history import Transaction
    root = Path(pack.root)
    report = {"pulled": [], "conflicts": [], "restored": [], "inplace": [], "ignored": [],
              "placed": 0, "removed": 0, "held": 0}
    if not is_project(root):
        return {}
    if not (pack.data_dir and pack.data_dir.is_dir()):
        report["held"] = -1          # the working pack is missing: touch nothing
        return report
    state = _load_state(root)
    files = state.get("files", {})
    want, info = desired(pack)
    want_low = {k.lower() for k in want}
    # 1. what changed by hand since the last sync
    pulls: dict[str, list[Path]] = {}          # working file -> hand files that want to go there
    for tgt, ent in files.items():
        tp = root / tgt
        wp = root / ent["src"]
        ts = _stat(tp)
        if ts is None:
            if tgt in want:
                report["restored"].append(tgt)        # deleted by hand: shown again
            continue
        if ts == ent.get("t"):
            continue
        if _same(tp, wp):
            # edited in place by another program: it's in the project, without a backup
            report["inplace"].append(tgt)
            continue
        if tgt.split("/")[-1].lower() == MOD_INFO and tgt.count("/") == 2:
            continue
        ws = _stat(wp)
        if ws is None or ws != ent.get("s"):
            # the app changed or removed it meanwhile: its version stays, the hand edit is kept aside
            _aside(root, tgt, tp, move=ws is None)
            report["conflicts"].append(tgt)
            continue
        pulls.setdefault(str(wp).lower(), []).append((wp, tp))
    known = {k.lower() for k in files} | want_low
    for top in (MODS, BASE):
        d = root / top
        if not d.is_dir():
            continue
        for p in _walk_files(d):
            rel = p.relative_to(root).as_posix()
            if rel.lower() in known:
                continue
            wp = _work_target(pack, rel)
            if wp is None:
                if rel.split("/")[-1].lower() != MOD_INFO:
                    report["ignored"].append(rel)
                continue
            pulls.setdefault(str(wp).lower(), []).append((wp, p))
    # two hand files for one place: neither goes in, both are kept aside
    for key, pairs in list(pulls.items()):
        if len(pairs) > 1:
            for _wp, tp in pairs:
                _aside(root, tp.relative_to(root).as_posix(), tp, move=True)
                report["conflicts"].append(tp.relative_to(root).as_posix())
            del pulls[key]
    if pulls:
        with Transaction(root, "Changes made in the project folder") as tx:
            for ((wp, tp),) in pulls.values():
                tmp = wp.with_name(wp.name + ".skynx-tmp")
                wp.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(tp, tmp)
                tx.replace_with(wp, tmp)
                report["pulled"].append(tp.relative_to(root).as_posix())
        pack.reload()
        want, info = desired(pack)
        want_low = {k.lower() for k in want}
        # a file added by hand where it doesn't belong now shows where it does
        for rel in report["pulled"]:
            if rel.lower() not in want_low and rel not in files:
                (root / rel).unlink(missing_ok=True)
    # 2. show the working pack
    new_files: dict[str, dict] = {}
    for i, (tgt, src) in enumerate(sorted(want.items())):
        tp = root / tgt
        ent = files.get(tgt)
        ss, ts = _stat(src), _stat(tp)
        link = _linkable(tgt)
        fresh = ts is not None and ((link and _same(tp, src)) or (
            ent and ent.get("src") == src.relative_to(root).as_posix() and ent.get("t") == ts and ent.get("s") == ss))
        if not fresh:
            _place(src, tp, link)
            report["placed"] += 1
            ts = _stat(tp)
        new_files[tgt] = {"src": src.relative_to(root).as_posix(), "t": ts, "s": _stat(src)}
        if progress and i % 500 == 0:
            progress("Mods", i, len(want))
    # 3. what the project doesn't have anymore
    gone = [t for t in files if t not in want and t.lower() not in want_low]
    mod_files = sum(1 for t in want if t.startswith(MODS + "/"))
    old_mod_files = sum(1 for t in files if t.startswith(MODS + "/"))
    if gone and old_mod_files >= 5 and mod_files <= old_mod_files // 10:
        # (almost) every mod file vanished from the working pack at once: that's
        # not an edit. Leave Mods/ and Base/ as they are until it's back.
        report["held"] = len(gone)
        _save_state(root, state)
        return report
    for tgt in gone:
        ent = files[tgt]
        tp = root / tgt
        ts = _stat(tp)
        if ts is None:
            continue
        if ts != ent.get("t"):
            _aside(root, tgt, tp, move=True)          # changed by hand and gone from the project
            report["conflicts"].append(tgt)
        else:
            tp.unlink()
            report["removed"] += 1
    # 4. mod.json in each mod folder; folders of mods that are gone
    for folder, row in info.items():
        f = root / MODS / folder / MOD_INFO
        data = json.dumps(_mod_info(folder, row), indent=1, ensure_ascii=False)
        f.parent.mkdir(parents=True, exist_ok=True)
        try:
            same = f.read_text(encoding="utf-8") == data
        except OSError:
            same = False
        if not same:
            f.write_text(data, encoding="utf-8")
    mods_dir = root / MODS
    live = {k.lower() for k in info}
    if mods_dir.is_dir() and not report["held"]:
        for d in mods_dir.iterdir():
            if d.is_dir() and d.name.lower() not in live:
                left = [p for p in d.rglob("*") if p.is_file() and p.name.lower() != MOD_INFO]
                if not left:
                    shutil.rmtree(d, ignore_errors=True)
                elif (d / MOD_INFO).is_file():
                    (d / MOD_INFO).unlink()           # not a mod of the project anymore; your files stay
    for top in (MODS, BASE):
        _prune_empty(root / top)
    (root / BASE).mkdir(exist_ok=True)
    mods_dir.mkdir(exist_ok=True)
    _save_state(root, {"files": new_files, "time": time.strftime("%Y-%m-%d %H:%M:%S")})
    return report


def _prune_empty(tree: Path) -> None:
    if not tree.is_dir():
        return
    for dirpath, _dirs, _files in sorted(os.walk(tree), key=lambda t: -len(t[0])):
        p = Path(dirpath)
        if p != tree:
            try:
                p.rmdir()
            except OSError:
                pass


# ------------------------------------------------------------------ pack
def build(pack: Pack, progress=None) -> dict:
    """Make Switch/: the two folders that go to the console, as real copies of
    the working pack without the mods that don't go. Only what changed since
    the last Pack is copied again. Anything in Switch/ the app didn't put there
    (or that was changed by hand) goes to the project's trash, never deleted."""
    from . import draft as DR
    root = Path(pack.root)
    if not is_project(root):
        raise ProjectError("Only a project is packed.", "Solo se empaca un proyecto.")
    skip = DR.check_masters(pack)
    dest = root / OUT
    stamp = time.strftime("%Y%m%d-%H%M%S")
    trash = root / ".skynx" / "trash" / f"Switch-{stamp}"
    mark = dest / BUILD_MARK
    try:
        made = json.loads(mark.read_text(encoding="utf-8")).get("files", {}) if mark.is_file() else None
    except (OSError, ValueError):
        made = None
    if dest.exists() and made is None:
        trash.parent.mkdir(parents=True, exist_ok=True)
        os.replace(dest, trash)            # not made by the app: kept whole
        made = {}
    made = made or {}
    lr = pack.layout_root or root
    want: dict[str, Path] = {}
    data = pack.data_dir.resolve() if pack.data_dir else None
    for d in (pack.base_dir, pack.aoc_dir):
        if not d or not d.is_dir():
            continue
        for p in _walk_files(d):
            if data and p.parent.resolve() == data and p.name.lower() in skip:
                continue
            want[p.relative_to(lr).as_posix()] = p
    total = len(want)
    # BSAs listed in the inis whose plugins are all switched off don't load either
    from .console import filter_ini, ini_drops
    drops = ini_drops(pack)
    variant = ",".join(sorted(drops))
    base_romfs = pack.base_romfs.resolve() if pack.base_romfs else None

    def is_ini(src: Path) -> bool:
        return src.suffix.lower() == ".ini" and base_romfs is not None and src.parent.resolve() == base_romfs
    out_files: dict[str, dict] = {}
    moved: list[str] = []
    copied = kept = 0

    def put_aside(rel: str, p: Path):
        t = trash / rel
        t.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(t))
        moved.append(rel)
    for i, (rel, src) in enumerate(sorted(want.items())):
        d = dest / rel
        m = made.get(rel)
        ds, ss = _stat(d), _stat(src)
        v = variant if is_ini(src) else ""
        if ds is not None and m and m.get("d") == ds and m.get("s") == ss[1:] and m.get("v", "") == v:
            out_files[rel] = m
            kept += 1
            continue
        if ds is not None and (not m or m.get("d") != ds):
            put_aside(rel, d)              # changed or added by hand
        d.parent.mkdir(parents=True, exist_ok=True)
        tmp = d.with_name(d.name + ".skynx-tmp")
        if src.name.lower() in ("skyrim_aoc.ccc", "plugins") and pack.list_path and \
                src.resolve() == pack.list_path.resolve():
            from .ccc import packed
            tmp.write_bytes(packed(src.read_bytes()))     # switched-off lines don't go
            shutil.copystat(src, tmp)
        elif v:
            tmp.write_bytes(filter_ini(src.read_bytes(), drops))
            shutil.copystat(src, tmp)
        else:
            shutil.copy2(src, tmp)
        _replace(tmp, d)
        out_files[rel] = {"d": _stat(d), "s": ss[1:], **({"v": v} if v else {})}
        copied += 1
        if progress and i % 50 == 0:
            progress(src.name, i, total)
    if dest.is_dir():
        for p in _walk_files(dest):
            rel = p.relative_to(dest).as_posix()
            if rel in want or rel == BUILD_MARK:
                continue
            m = made.get(rel)
            if m and m.get("d") == _stat(p):
                p.unlink()                 # ours, and the project doesn't have it anymore
            else:
                put_aside(rel, p)
        _prune_empty(dest)
    dest.mkdir(parents=True, exist_ok=True)
    tmp = mark.with_name(mark.name + ".tmp")
    tmp.write_text(json.dumps({"made": time.strftime("%Y-%m-%d %H:%M:%S"), "files": out_files}),
                   encoding="utf-8")
    os.replace(tmp, mark)
    write_info(root, last_build=time.strftime("%Y-%m-%d %H:%M:%S"))
    sw = Pack.open(dest)
    raw = sw.list_path.read_bytes() if sw.list_path and sw.list_path.exists() else b""
    return {"dest": str(dest), "left_out": sorted(skip), "ccc_bytes": len(raw), "plugins": len(sw.plugins),
            "bsas": len(sw.bsas), "size": sw.data_size(), "copied": copied, "kept": kept,
            "set_aside": moved, "trash": str(trash) if moved else None,
            "ini_off": sorted(drops)}


# ------------------------------------------------------------------ listing
def _edition(work: Path) -> str:
    found = set()
    for dirpath, dirnames, filenames in os.walk(work):
        if len(Path(dirpath).relative_to(work).parts) >= 5:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if d.lower() != "data"]
        low = {f.lower() for f in filenames}
        if "skyrim_aoc.ccc" in low:
            return "AE"
        if "plugins" in low:
            found.add("SE")
    return "SE" if found else "?"


def summary(root: Path) -> dict:
    """What the project list shows; cheap (no plugin reading)."""
    root = Path(root)
    from . import draft as DR
    info = read_info(root)
    edition = _edition(work_root(root))
    mods_dir = root / MODS
    n = sum(1 for d in mods_dir.iterdir() if d.is_dir()) if mods_dir.is_dir() else 0
    d = DR.load(root) or {}
    off = len(d.get("excluded", {}))
    health = {}
    try:
        health = json.loads((root / ".skynx" / "summary.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return {"path": str(root), "name": info.get("name") or root.name, "edition": edition,
            "mods": n, "off": off, "created": info.get("created"), "origin": info.get("origin") or {},
            "last_build": info.get("last_build"), "last_sd": info.get("last_sd"),
            "opened": info.get("opened"), "health": health}


def list_projects(library_root: Path) -> list[dict]:
    base = projects_root(library_root)
    out = []
    for d in sorted(base.iterdir()):
        if d.is_dir() and not d.name.startswith(".") and is_project(d):
            try:
                out.append(summary(d))
            except Exception as e:  # noqa: BLE001
                out.append({"path": str(d), "name": d.name, "error": str(e)})
    out.sort(key=lambda p: (p.get("opened") or p.get("created") or ""), reverse=True)
    return out


def delete(library_root: Path, root: Path) -> Path:
    """Move a project to the Library's trash (a rename: instant, recoverable)."""
    root = Path(root)
    if not is_project(root):
        raise ProjectError("That folder isn't a project.", "Esa carpeta no es un proyecto.")
    dest = Path(library_root) / ".trash" / PROJECTS / f"{root.name}-{time.strftime('%Y%m%d-%H%M%S')}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.replace(root, dest)
    return dest


def legacy(library_root: Path) -> list[dict]:
    """Modpacks and packs being created from before projects (Library\\Packs,
    Library\\Drafts and packs registered in place), to turn into projects."""
    from .library import _load_db
    from . import draft as DR
    lib = Path(library_root)
    out, seen = [], set()
    done = {str((read_info(Path(p["path"])).get("origin") or {}).get("path") or "").lower()
            for p in list_projects(lib)}

    def add(p: Path, kind: str):
        k = os.path.normcase(os.path.abspath(p))
        if k in seen or not p.is_dir():
            return
        seen.add(k)
        out.append({"path": str(p), "name": p.name, "kind": "draft" if DR.is_draft(p) else kind,
                    "done": str(p).lower() in done})
    for sub, kind in (("Drafts", "draft"), ("Packs", "pack")):
        d = lib / sub
        if d.is_dir():
            for p in sorted(d.iterdir()):
                if not p.name.startswith("."):
                    add(p, kind)
    for e in _load_db(lib).get("entries", []):
        if e.get("kind") == "pack":
            add(Path(e["path"]), "pack")
    return out
