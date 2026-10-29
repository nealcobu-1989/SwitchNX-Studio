"""External tools: an xEdit workspace for a pack, a tool registry, BSA
extraction and turning plugins on and off in the load list.

xEdit facts used here were read from the xEdit source (TES5Edit/TES5Edit,
branch dev-4.1.6, xEdit/xeInit.pas, xEdit/xeMainForm.pas, Core/wbLoadOrder.pas,
Core/wbCommandLine.pas):

* Parameters are "-Name:value" in one argument (wbFindCmdLineParam). -D: sets
  the Data folder, -P: the plugins.txt, -I: the game ini, -CustomIni: the
  custom ini. A missing game ini is fatal ("Fatal: Could not find ini"), so the
  workspace carries its own Skyrim.ini.
* -SSE forces the game mode (also detected from "sse" in the exe name).
* SSE mode: plugins.txt gives the order; "*Name" lines are active. Text after
  '#' is a comment. loadorder.txt is only read for TES5/Enderal/TES4R, not SSE.
* Skyrim.ccc is read from the folder ABOVE Data; plugins listed there that
  exist are forced active and load right after the official DLC, in its order.
  We list Hyrule.esm there first, so xEdit loads it where the Switch does.
* Saving writes "<name>.save.<timestamp>" and later renames the original into
  "<Data>\\SSEEdit Backups\\" and the .save file onto the original name (on exit
  unless the rename can be done at once). A hardlinked pack file is therefore
  never written: only the workspace name gets a new file. SEQ files ("Create
  SEQ File") are written in place, so loose files are copied, never linked.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import threading
import sys
from pathlib import Path

from . import ccc as C
from . import knowledge as K
from .errors import SkynxError
from .pack import PLUGIN_EXT, Pack

MANIFEST = "skynx-workspace.json"
WS_VERSION = 1
LOOSE_COPY = {"strings": {".strings", ".dlstrings", ".ilstrings"}, "seq": {".seq"}}
_EDIT_DIRS = re.compile(r".*edit (backups|cache)$", re.I)


class XToolsError(SkynxError):
    pass


def _note(code: str, en: str, es: str, **extra) -> dict:
    d = {"code": code, "en": en, "es": es}
    d.update(extra)
    return d


def _sha(p: Path) -> str:
    h = hashlib.sha1()
    with Path(p).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _same(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _ci_child(folder: Path | None, name: str) -> Path | None:
    if folder is None or not folder.is_dir():
        return None
    low = name.lower()
    for p in folder.iterdir():
        if p.name.lower() == low:
            return p
    return None


def _rmtree(path: Path) -> None:
    def onerr(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
            func(p)
        except OSError:
            pass
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=onerr)
    else:  # pragma: no cover
        shutil.rmtree(path, onerror=onerr)


# =========================================================================
# 1. xEdit workspace
# =========================================================================
def _place(src: Path, dst: Path, big: bool, allow_symlink: bool) -> str | None:
    """Link src at dst. Hardlink first, then symlink; plugins fall back to a
    copy, BSAs (big) are skipped. Returns the method or None."""
    try:
        os.link(src, dst)
        return "hardlink"
    except OSError:
        pass
    if allow_symlink:
        try:
            os.symlink(src, dst)
            return "symlink"
        except (OSError, NotImplementedError):
            pass
    if big:
        return None
    shutil.copy2(src, dst)
    return "copy"


def _is_cc(pack: Pack, name: str) -> bool:
    low = name.lower()
    return low.startswith("cc") and low not in pack.plugins


def _load_manifest(root: Path) -> dict | None:
    f = Path(root) / MANIFEST
    if not f.is_file():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_text(path: Path, lines: list[str]) -> None:
    text = "\r\n".join(lines) + "\r\n" if lines else ""
    try:
        data = text.encode("ascii")
    except UnicodeEncodeError:
        data = C.BOM + text.encode("utf-8", "surrogateescape")   # Delphi reads the BOM
    path.write_bytes(data)


def _vanilla_folder(folder: Path) -> Path:
    """The folder with the console's files: the one given or its BSAs, Data or
    romfs\\Data subfolder (the first that has Skyrim.esm, else one with BSAs)."""
    from .vanilla import bsa_folder
    cands = [folder] + [folder / s for s in ("BSAs", "Data", "romfs/Data")]
    for c in cands:
        hit = _ci_child(c, "Skyrim.esm")
        if hit and hit.is_file():
            return c
    return bsa_folder(folder)


def _norm(p) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(str(p))))


def workspace_owner(workspace) -> str | None:
    """The pack folder a workspace was made for (as written in its manifest)."""
    m = _load_manifest(_ws_root(workspace))
    return m.get("pack_root") if m else None


def relink_workspace(workspace, pack: Pack) -> bool:
    """A workspace made for a pack that has since moved (its old folder no
    longer exists): point its manifest at the pack's new folder, so kept edits
    can still be compared and brought back. Refuses when the old folder still
    exists (that would be a different pack with the same name)."""
    root = _ws_root(workspace)
    m = _load_manifest(root)
    if m is None:
        return False
    old = m.get("pack_root") or ""
    if _norm(old) == _norm(pack.root):
        return False
    if old and Path(old).exists():
        raise XToolsError(f"This working copy belongs to another pack with the same name ({old}).",
                          f"Esta copia de trabajo es de otro pack con el mismo nombre ({old}).")
    new_root = str(Path(os.path.abspath(pack.root)))
    old_n = _norm(old)
    for e in m.get("files", {}).values():
        src = e.get("src") or ""
        if e.get("kind") == "pack" and _norm(src).startswith(old_n + os.sep):
            e["src"] = os.path.join(new_root, os.path.relpath(os.path.abspath(src), os.path.abspath(old)))
    m["pack_root"] = new_root
    if pack.data_dir:
        m["data_dir"] = str(Path(os.path.abspath(pack.data_dir)))
    (root / MANIFEST).write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")
    return True


def pending_edits(st: dict) -> list[str]:
    """Everything in a sync_status that would be lost if the workspace went away."""
    return st["changed"] + st["conflicts"] + st["new"] + st["pending_saves"] + st["gone"] + st["vanilla_changed"]


def make_xedit_workspace(pack: Pack, vanilla_dir: Path | None, dest: Path, *,
                         force: bool = False, allow_symlink: bool = True,
                         zedit_stub: bool = False) -> dict:
    """Build a folder xEdit can open as a Skyrim SE game: dest\\Data with the
    console's vanilla masters/BSAs and the pack's plugins/BSAs linked in, plus
    plugins.txt, loadorder.txt, Skyrim.ccc and Skyrim.ini next to it.

    dest is rebuilt if it is an earlier workspace (refused while it holds
    edits that were not synced back, unless force=True). Any other non-empty
    folder is refused.
    """
    dest = Path(dest)
    old = _load_manifest(dest)
    if dest.exists() and any(dest.iterdir()):
        if old is None:
            raise XToolsError(f"{dest} is not empty and is not an xEdit workspace; I won't touch it.",
                              f"{dest} no está vacía y no es un espacio de xEdit; no la toco.")
        if not force:
            st = sync_status(pack, {"root": str(dest)}, check_root=False)
            pending = pending_edits(st)
            if pending:
                raise XToolsError("The workspace has edits that were not brought back to the pack: "
                                  + ", ".join(pending),
                                  "El espacio de trabajo tiene cambios que no se han traído al pack: "
                                  + ", ".join(pending))
        for child in list(dest.iterdir()):
            if child.is_dir() and not child.is_symlink():
                _rmtree(child)
            else:
                child.unlink()
    data = dest / "Data"
    data.mkdir(parents=True, exist_ok=True)
    notes: list[dict] = []
    files: dict[str, dict] = {}
    methods = {"hardlink": 0, "symlink": 0, "copy": 0}
    skipped: list[str] = []
    present: dict[str, str] = {}     # lower name -> spelling in the workspace

    def put(src: Path, kind: str, rel: str | None = None, copy_only: bool = False) -> bool:
        rel = rel or src.name
        dst = data / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if copy_only:
            shutil.copy2(src, dst)
            how = "copy"
        else:
            how = _place(src, dst, src.suffix.lower() == ".bsa", allow_symlink)
        if how is None:
            skipped.append(rel)
            return False
        methods[how] += 1
        entry = {"name": rel, "src": str(Path(os.path.abspath(src))), "kind": kind, "how": how,
                 "size": src.stat().st_size, "mtime_ns": dst.stat().st_mtime_ns}
        if src.suffix.lower() != ".bsa":
            entry["sha1"] = _sha(src)
        files[rel.replace("\\", "/").lower()] = entry
        if "/" not in rel and "\\" not in rel:
            present[rel.lower()] = rel
        return True

    # -- the pack's own files (they win over vanilla ones with the same name)
    pack_names = set()
    for low, h in sorted(pack.plugins.items()):
        put(h.path, "pack")
        pack_names.add(low)
    for low, p in sorted(pack.bsas.items()):
        put(p, "pack")
        pack_names.add(low)
    for d in pack.loose_dirs:
        exts = LOOSE_COPY.get(d.lower())
        if not exts:
            continue
        base = pack.data_dir / d
        for f in sorted(base.rglob("*")):
            if f.is_file() and f.suffix.lower() in exts:
                put(f, "pack", str(Path(d) / f.relative_to(base)), copy_only=True)
    others = [d for d in pack.loose_dirs if d.lower() not in LOOSE_COPY]
    if others:
        notes.append(_note("loose-skipped",
                           "Loose folders are not linked (xEdit only needs plugins and BSAs): " + ", ".join(others),
                           "Las carpetas sueltas no se enlazan (xEdit solo necesita plugins y BSA): " + ", ".join(others)))

    # -- vanilla files from the console dump
    missing: dict[str, dict] = {}

    def miss(name: str, kind: str) -> None:
        missing.setdefault(name.lower(), {"name": name, "kind": kind, "needed_by": []})

    vdir = _vanilla_folder(Path(vanilla_dir)) if vanilla_dir else None
    if vdir is None or not vdir.is_dir():
        notes.append(_note("no-vanilla", "No folder with the console's vanilla files; xEdit needs at least Skyrim.esm.",
                           "No hay carpeta con los archivos originales de la consola; xEdit necesita al menos Skyrim.esm."))
        vdir = None
    for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS:
        if m.lower() in pack_names:
            continue
        src = _ci_child(vdir, m)
        if src and src.is_file():
            put(src, "vanilla")
        else:
            miss(m, "vanilla")
    if vdir:
        for f in sorted(vdir.iterdir()):
            if f.is_file() and f.suffix.lower() == ".bsa" and K.is_vanilla_bsa(f.name):
                if f.name.lower() in pack_names:
                    notes.append(_note("pack-wins", f"The pack has its own {f.name}; using that one.",
                                       f"El pack trae su propio {f.name}; uso ese."))
                    continue
                put(f, "vanilla")

    # -- load list: CC plugins come from the console's AOC title, maybe extracted too
    order: list[tuple[str, bool, str]] = []          # (spelling, active, source)
    for name, src in pack.load_order():
        if src == "juego":
            continue
        active = not name.startswith("#")
        bare = name.lstrip("#").strip()
        if not bare:
            continue
        low = bare.lower()
        if low not in present and _is_cc(pack, bare):
            f = _ci_child(vdir, bare)
            if f and f.is_file():
                put(f, "cc")
                stem = Path(f.name).stem.lower()
                for b in vdir.iterdir():
                    s = Path(b.name).stem.lower()
                    if b.suffix.lower() == ".bsa" and s in (stem, stem + " - textures") \
                            and b.name.lower() not in present:
                        put(b, "cc")
            else:
                miss(bare, "cc")
                continue
        elif low not in present:
            miss(bare, "listed")
            continue
        order.append((present[low], active, src))

    # -- masters of active plugins that are nowhere
    active_low = {n.lower() for n, a, _ in order if a} | {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS}
    for n, a, _ in order:
        h = pack.plugins.get(n.lower())
        if not a or h is None:
            continue
        for m in h.masters:
            if m.lower() not in present:
                miss(m, "cc" if _is_cc(pack, m) else "master")
                missing[m.lower()]["needed_by"].append(h.name)
            elif m.lower() not in active_low:
                notes.append(_note("master-off", f"{h.name} needs {m}, which is switched off.",
                                   f"{h.name} necesita {m}, que está desactivado."))
    if skipped:
        notes.append(_note("bsa-skipped",
                           "These BSAs could not be linked (different drive and no symlink permission) and "
                           "were left out; xEdit will not see their assets: " + ", ".join(skipped),
                           "Estos BSA no se pudieron enlazar (otra unidad y sin permiso para enlaces "
                           "simbólicos) y quedaron por fuera; xEdit no verá sus archivos: " + ", ".join(skipped)))
    if methods["copy"]:
        notes.append(_note("copied", f"{methods['copy']} files were copied instead of linked (the workspace is on "
                                     "another drive). Put it on the same drive as the pack to save space.",
                           f"{methods['copy']} archivos se copiaron en vez de enlazarse (el espacio de trabajo "
                           "está en otra unidad). Ponlo en la misma unidad del pack para ahorrar espacio."))

    # -- the lists xEdit reads
    hyrule = present.get("hyrule.esm")
    ccc_lines = ([hyrule] if hyrule else []) + [n for n, a, _ in order if a and _is_cc(pack, n)]
    plugins_lines = [f"# plugins.txt made by SwitchNX Studio for {Path(pack.root).name}"]
    if hyrule:
        plugins_lines.append("*" + hyrule)
    plugins_lines += [("*" if a else "") + n for n, a, _ in order if n.lower() != "hyrule.esm"]
    loadorder_lines = [present[m.lower()] for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS if m.lower() in present]
    loadorder_lines += [n for n, _a, _ in order if n.lower() not in {x.lower() for x in loadorder_lines}]
    plugins_txt, loadorder_txt = dest / "plugins.txt", dest / "loadorder.txt"
    ccc_path, ini_path, custom_ini = dest / "Skyrim.ccc", dest / "Skyrim.ini", dest / "SkyrimCustom.ini"
    _write_text(plugins_txt, plugins_lines)
    _write_text(loadorder_txt, loadorder_lines)
    _write_text(ccc_path, ccc_lines)

    # Skyrim.ini: the pack's effective archive lists, limited to what is here
    ini_lines = ["[General]"]
    lang = None
    for ini in pack.inis:
        v = ini.get("General", "sLanguage")
        if v:
            lang = v.strip()
    ini_lines.append(f"sLanguage={lang or 'ENGLISH'}")
    ini_lines.append("[Archive]")
    absent_bsas = []
    for key, names in pack.archive_lists().items():
        keep = []
        for n in names:
            if n.lower() in present:
                keep.append(present[n.lower()])
            elif n not in absent_bsas:
                absent_bsas.append(n)
        ini_lines.append(f"{key}={', '.join(keep)}")
    _write_text(ini_path, ini_lines)
    if absent_bsas:
        notes.append(_note("ini-bsa-missing", "Archives in the inis that are not in the workspace: " + ", ".join(absent_bsas),
                           "Archivos de las inis que no están en el espacio de trabajo: " + ", ".join(absent_bsas)))
    if zedit_stub:
        (dest / "SkyrimSE.exe").write_bytes(b"")
        notes.append(_note("zedit-stub", "SkyrimSE.exe here is an empty placeholder so zEdit accepts the folder as a "
                                         "game path. It is not the game.",
                           "SkyrimSE.exe aquí es un archivo vacío para que zEdit acepte la carpeta como ruta del "
                           "juego. No es el juego."))

    manifest = {"version": WS_VERSION, "pack_root": str(Path(os.path.abspath(pack.root))),
                "data_dir": str(Path(os.path.abspath(pack.data_dir))) if pack.data_dir else None,
                "files": files}
    (dest / MANIFEST).write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"root": str(dest), "data": str(data), "plugins_txt": str(plugins_txt),
            "loadorder_txt": str(loadorder_txt), "ccc": str(ccc_path), "ini": str(ini_path),
            "custom_ini": str(custom_ini), "manifest": str(dest / MANIFEST),
            "missing": list(missing.values()), "notes": notes, "methods": methods,
            "skipped": skipped, "files": len(files)}


def open_existing_workspace(dest: Path) -> dict:
    """The paths of a workspace built earlier, to open it again as it is
    (keeping edits that were not brought back yet)."""
    dest = Path(dest)
    if _load_manifest(dest) is None:
        raise XToolsError(f"{dest} is not an xEdit workspace.", f"{dest} no es un espacio de xEdit.")
    return {"root": str(dest), "data": str(dest / "Data"), "plugins_txt": str(dest / "plugins.txt"),
            "loadorder_txt": str(dest / "loadorder.txt"), "ccc": str(dest / "Skyrim.ccc"),
            "ini": str(dest / "Skyrim.ini"), "custom_ini": str(dest / "SkyrimCustom.ini"),
            "manifest": str(dest / MANIFEST), "missing": [], "notes": [], "reused": True}


XEDIT_GAMES = ("SSE", "TES5", "TES5VR", "EnderalSE", "Enderal")


def xedit_command(exe: Path, workspace: dict, game: str = "SSE", extra=()) -> list[str]:
    """Command line that opens the workspace in xEdit. Never adds
    -AllowDirectSaves: direct saves would write through the hardlinks."""
    g = next((x for x in XEDIT_GAMES if x.lower() == game.lower().lstrip("-")), None)
    if g is None:
        raise XToolsError(f"Unknown xEdit game mode: {game}", f"Modo de juego de xEdit desconocido: {game}")
    extra = [str(x) for x in extra]
    if any(x.lower().lstrip("-/").startswith("allowdirectsaves") for x in extra):
        raise XToolsError("-AllowDirectSaves would write into the pack's files directly; not allowed here.",
                          "-AllowDirectSaves escribiría directo en los archivos del pack; aquí no se permite.")
    data = str(workspace["data"]).rstrip("\\/")
    return [str(exe), f"-{g}", f"-D:{data}", f"-P:{workspace['plugins_txt']}",
            f"-I:{workspace['ini']}", f"-CustomIni:{workspace['custom_ini']}", *extra]


def zedit_command(exe: Path, profile: str | None = None, app_mode: str | None = None) -> list[str]:
    """zEdit has no data-path parameter; it starts a saved profile by name
    (-profile:<name>) and picks a mode (-appMode:<mode>)."""
    cmd = [str(exe)]
    if profile:
        cmd.append(f"-profile:{profile}")
    if app_mode:
        cmd.append(f"-appMode:{app_mode}")
    return cmd


# -------------------------------------------------------------- sync back
def _ws_root(workspace) -> Path:
    if isinstance(workspace, dict):
        return Path(workspace["root"])
    return Path(workspace)


def sync_status(pack: Pack, workspace, check_root: bool = True) -> dict:
    """What sync_back would do, without doing it.

    changed: workspace files edited since the workspace was made (rel paths)
    conflicts: edited in the workspace AND changed in the pack meanwhile
    new: plugins / seq / strings created in the workspace
    in_place: pack files that changed through a link (already in the pack,
              but outside the history)
    pending_saves: xEdit's "*.save.*" files: xEdit is still open (or crashed)
    vanilla_changed: console files edited in the workspace (never synced)
    gone: pack files that no longer exist
    ignored: other new files
    """
    root = _ws_root(workspace)
    m = _load_manifest(root)
    if m is None:
        raise XToolsError(f"{root} is not an xEdit workspace.", f"{root} no es un espacio de xEdit.")
    if check_root and _norm(pack.root) != _norm(m.get("pack_root") or ""):
        raise XToolsError("This workspace was made for another pack.",
                          "Este espacio de trabajo se hizo para otro pack.")
    data = root / "Data"
    out = {"changed": [], "conflicts": [], "new": [], "in_place": [], "pending_saves": [],
           "ignored": [], "vanilla_changed": [], "gone": []}
    files = m.get("files", {})
    if not data.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(data):
        d = Path(dirpath)
        if d == data:
            dirnames[:] = [x for x in dirnames if not _EDIT_DIRS.match(x)]
        for fn in sorted(filenames):
            p = d / fn
            rel = p.relative_to(data).as_posix()
            if ".save." in fn.lower():
                out["pending_saves"].append(rel)
                continue
            if ".backup." in fn.lower():
                continue
            e = files.get(rel.lower())
            if e is not None:
                if e.get("sha1") is None:          # a BSA: xEdit never writes those
                    continue
                src = Path(e["src"])
                linked = _same(p, src)
                if linked:
                    if e["kind"] == "pack" and _sha(src) != e["sha1"]:
                        out["in_place"].append(rel)
                    continue
                st = p.stat()
                if st.st_size == e["size"] and st.st_mtime_ns == e.get("mtime_ns"):
                    continue                        # untouched since it was placed
                ws_sha = _sha(p)
                if ws_sha == e["sha1"]:
                    continue
                if e["kind"] != "pack":
                    out["vanilla_changed"].append(rel)
                    continue
                if not src.exists():
                    out["gone"].append(rel)
                    continue
                pack_sha = _sha(src)
                if pack_sha == ws_sha:
                    continue
                out["conflicts" if pack_sha != e["sha1"] else "changed"].append(rel)
                continue
            parts = rel.split("/")
            ext = Path(fn).suffix.lower()
            if (len(parts) == 1 and ext in PLUGIN_EXT) or \
                    (len(parts) > 1 and ext in LOOSE_COPY.get(parts[0].lower(), ())):
                tgt = _pack_target(pack, rel)
                if tgt is not None and tgt.is_file() and _sha(tgt) == _sha(p):
                    continue
                out["new"].append(rel)
            else:
                out["ignored"].append(rel)
    return out


def _pack_target(pack: Pack, rel: str) -> Path | None:
    """Where a workspace file goes in the pack, reusing existing folder casing."""
    if not pack.data_dir:
        return None
    cur = pack.data_dir
    parts = rel.split("/")
    for part in parts[:-1]:
        cur = _ci_child(cur, part) or cur / part
    hit = _ci_child(cur, parts[-1]) if cur.is_dir() else None
    return hit or cur / parts[-1]


def sync_back(pack: Pack, workspace, tx, force: bool = False) -> list[str]:
    """Bring plugins (and seq / strings files) edited in xEdit back into the
    pack through the Transaction. Returns the relative paths written.
    Refuses while xEdit still has renames pending (*.save.* files), and when
    a file also changed in the pack meanwhile (force=True: the workspace wins)."""
    st = sync_status(pack, workspace)
    if st["pending_saves"]:
        raise XToolsError("xEdit has not finished saving (close it first): " + ", ".join(st["pending_saves"]),
                          "xEdit no ha terminado de guardar (ciérralo primero): " + ", ".join(st["pending_saves"]))
    if st["conflicts"] and not force:
        raise XToolsError("These files changed both in xEdit and in the pack: " + ", ".join(st["conflicts"]),
                          "Estos archivos cambiaron en xEdit y también en el pack: " + ", ".join(st["conflicts"]))
    data = _ws_root(workspace) / "Data"
    done = []
    for rel in st["changed"] + st["conflicts"] + st["new"]:
        src = data / rel
        tgt = _pack_target(pack, rel)
        if tgt is None:
            continue
        if tgt.exists():
            tx.write_bytes(tgt, src.read_bytes())
        else:
            tx.copy_in(src, tgt)
        done.append(rel)
    if done:
        pack.reload()
    return done


# =========================================================================
# 2. Tool registry and launching
# =========================================================================
def known_tools() -> list[dict]:
    return [
        {"id": "sseedit", "name": "SSEEdit (xEdit)", "kind": "xedit",
         "exe_names": ["SSEEdit64.exe", "SSEEdit.exe", "xEdit64.exe", "xEdit.exe"],
         "source": "https://github.com/TES5Edit/TES5Edit",
         "how": {"en": "Opens the pack as a Skyrim SE game in a separate workspace folder. Save in xEdit, close it, "
                       "then bring the changes back; they go into the history and can be undone.",
                 "es": "Abre el pack como un juego de Skyrim SE en una carpeta de trabajo aparte. Guarda en xEdit, "
                       "ciérralo y luego trae los cambios; quedan en el historial y se pueden deshacer."}},
        {"id": "zedit", "name": "zEdit", "kind": "zedit", "exe_names": ["zEdit.exe"],
         "source": "https://github.com/z-edit/zedit",
         "how": {"en": "zEdit can't be pointed at a folder from the command line. In zEdit, create a profile with game "
                       "Skyrim SE and the workspace folder as game path (make the workspace with the zEdit option so "
                       "the folder passes zEdit's check). Then it can start that profile by name.",
                 "es": "A zEdit no se le puede indicar una carpeta por línea de comandos. En zEdit, crea un perfil con "
                       "el juego Skyrim SE y la carpeta de trabajo como ruta del juego (crea la carpeta con la opción "
                       "de zEdit para que pase su revisión). Después se puede abrir ese perfil por nombre."}},
        {"id": "nifskope", "name": "NifSkope", "kind": "nifskope", "exe_names": ["NifSkope.exe"],
         "how": {"en": "Opens a .nif mesh. Extract it from its BSA first if it is packed.",
                 "es": "Abre una malla .nif. Si está dentro de un BSA, sácala primero."}},
        {"id": "bae", "name": "Bethesda Archive Extractor", "kind": "bsa", "optional": True,
         "exe_names": ["bae.exe", "BAE.exe"],
         "how": {"en": "Optional. SwitchNX Studio can already extract BSAs by itself.",
                 "es": "Opcional. SwitchNX Studio ya puede sacar archivos de los BSA por su cuenta."}},
        {"id": "cao", "name": "Cathedral Assets Optimizer", "kind": "other", "optional": True,
         "exe_names": ["Cathedral_Assets_Optimizer.exe", "Cathedral Assets Optimizer.exe", "CAO.exe"],
         "how": {"en": "Optional. Optimizes meshes, textures and archives for PC; check every result before "
                       "putting it on the Switch.",
                 "es": "Opcional. Optimiza mallas, texturas y archivos para PC; revisa cada resultado antes de "
                       "llevarlo a la Switch."}},
        {"id": "other", "name": "Other program", "kind": "other", "exe_names": [],
         "how": {"en": "Any program you choose. It is started with the file or folder you pick.",
                 "es": "Cualquier programa que elijas. Se abre con el archivo o la carpeta que indiques."}},
    ]


DEFAULT_TOOL_DIRS = (Path(r"C:\SkyNX\Tools"),)


def _find_exe(folder: Path, names: set[str], depth: int) -> Path | None:
    try:
        entries = sorted(folder.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return None
    for p in entries:
        if p.is_file() and p.name.lower() in names:
            return p
    if depth > 0:
        for p in entries:
            if p.is_dir() and not p.name.startswith("."):
                hit = _find_exe(p, names, depth - 1)
                if hit:
                    return hit
    return None


def find_tool(tool_id: str, search_dirs=()) -> Path | None:
    """Look for the tool in the given folders, then C:\\SkyNX\\Tools, two
    levels deep (xEdit usually sits in its own versioned folder)."""
    tool = next((t for t in known_tools() if t["id"] == tool_id), None)
    if tool is None or not tool["exe_names"]:
        return None
    names = {n.lower() for n in tool["exe_names"]}
    order = {n.lower(): i for i, n in enumerate(tool["exe_names"])}
    for d in [Path(x) for x in search_dirs] + list(DEFAULT_TOOL_DIRS):
        if not d.is_dir():
            continue
        # prefer the first name in exe_names within the same folder level
        for want in sorted(names, key=order.get):
            hit = _find_exe(d, {want}, 2)
            if hit:
                return hit
    return None


DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000


def launch(cmd, cwd=None, popen=None, on_exit=None) -> int:
    """Start a program and return its pid without waiting. On Windows it is
    detached from SwitchNX Studio and gets no console window. If on_exit is
    given, a background thread waits for the program and calls
    on_exit(returncode) when it closes."""
    popen = popen or subprocess.Popen
    cmd = [str(c) for c in cmd]
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
          "close_fds": True}
    if cwd:
        kw["cwd"] = str(cwd)
    if os.name == "nt":
        # CREATE_NO_WINDOW is ignored together with DETACHED_PROCESS; detached
        # already means no console.
        kw["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    try:
        proc = popen(cmd, **kw)
    except OSError as e:
        raise XToolsError(f"Could not start {Path(cmd[0]).name}: {e}",
                          f"No se pudo abrir {Path(cmd[0]).name}: {e}") from e
    if on_exit is not None:
        def waiter():
            try:
                code = proc.wait()
            except Exception:  # noqa: BLE001
                code = None
            on_exit(code)
        threading.Thread(target=waiter, daemon=True, name="xedit-wait").start()
    return proc.pid


def discard_workspace(workspace) -> None:
    """Delete an xEdit workspace folder. Only a folder with our manifest is
    touched. Links inside are removed as links: the pack's and the console's
    original files stay where they are."""
    root = _ws_root(workspace)
    if not root.exists():
        return
    if _load_manifest(root) is None:
        raise XToolsError(f"{root} is not an xEdit workspace; I won't delete it.",
                          f"{root} no es un espacio de xEdit; no la borro.")
    _rmtree(root)       # shutil.rmtree: unlinks links and junctions, never follows them
    if root.exists():
        raise XToolsError(f"Some files in {root} couldn't be deleted (is xEdit still open?).",
                          f"No pude borrar algunos archivos de {root} (¿xEdit sigue abierto?).")


# =========================================================================
# 3. BSA extraction
# =========================================================================
_BAD_CHARS = set('<>:"|?*') | {chr(i) for i in range(32)}
_RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}


def safe_rel_parts(path: str) -> list[str] | None:
    """The path split in folders, or None if it can't be written safely on
    Windows (traversal, drive letters, illegal or reserved names)."""
    parts = re.split(r"[\\/]", path)
    if not parts or path.startswith(("\\", "/")):
        return None
    for part in parts:
        if part in ("", ".", ".."):
            return None
        if any(c in _BAD_CHARS for c in part) or part[-1] in " .":
            return None
        if part.split(".", 1)[0].strip().lower() in _RESERVED:
            return None
    return parts


def _matcher(only):
    if not only:
        return lambda p: True
    pats = [o.replace("/", "\\").lower() for o in ([only] if isinstance(only, str) else only)]

    def ok(p: str) -> bool:
        p = p.lower()
        for pat in pats:
            if any(c in pat for c in "*?["):
                if fnmatch.fnmatchcase(p, pat):
                    return True
            elif p == pat or p.startswith(pat.rstrip("\\") + "\\") or (pat.endswith("\\") and p.startswith(pat)):
                return True
        return False
    return ok


def _free_name(target: Path, data: bytes) -> tuple[Path, bool]:
    """(path to write, already identical)."""
    n = 2
    cand = target
    while cand.exists():
        if cand.is_file() and cand.stat().st_size == len(data) and cand.read_bytes() == data:
            return cand, True
        cand = target.with_name(f"{target.stem} ({n}){target.suffix}")
        n += 1
    return cand, False


def extract_bsa(bsa_path: Path, dest_dir: Path, progress=None, only=None, overwrite: bool = False) -> dict:
    """Write the archive's files (or those matching `only`: path prefixes or
    globs, case-insensitive, either slash) under dest_dir keeping folders.
    Unsafe names are refused. An existing different file is kept and the new
    one gets " (2)" unless overwrite=True."""
    from .bsa import read_bsa
    arc = read_bsa(Path(bsa_path))
    dest = Path(os.path.abspath(dest_dir))
    dest.mkdir(parents=True, exist_ok=True)
    want = _matcher(only)
    todo = [e for e in arc.entries if want(e.path)]
    out = {"bsa": Path(bsa_path).name, "files": 0, "bytes": 0, "same": 0, "renamed": [],
           "overwritten": 0, "refused": [], "errors": [], "total": len(todo)}
    with Path(bsa_path).open("rb") as f:
        for i, e in enumerate(todo):
            if progress:
                progress(i, len(todo), e.path)
            parts = safe_rel_parts(e.path)
            target = dest.joinpath(*parts) if parts else None
            if target is None or os.path.commonpath([dest, os.path.abspath(target)]) != str(dest):
                out["refused"].append(e.path)
                continue
            try:
                blob = arc.read_file(e, f)
            except Exception as ex:  # noqa: BLE001  (corrupt or unsupported entry)
                out["errors"].append({"path": e.path, "error": str(ex)})
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and overwrite:
                if target.is_file() and target.read_bytes() == blob:
                    out["same"] += 1
                    continue
                out["overwritten"] += 1
            elif target.exists():
                target, same = _free_name(target, blob)
                if same:
                    out["same"] += 1
                    continue
                out["renamed"].append(target.relative_to(dest).as_posix())
            tmp = target.with_name(target.name + ".skynx-tmp")
            try:
                tmp.write_bytes(blob)
                os.replace(tmp, target)
            except OSError as ex:
                if tmp.exists():
                    tmp.unlink()
                out["errors"].append({"path": e.path, "error": str(ex)})
                continue
            out["files"] += 1
            out["bytes"] += len(blob)
    if progress:
        progress(len(todo), len(todo), "")
    return out


def extract_pack_bsas(pack: Pack, names, dest: Path, progress=None, only=None,
                      overwrite: bool = False, separate: bool = True) -> dict:
    """Extract several of the pack's BSAs. With separate=True each goes into
    dest/<archive name without .bsa>/; otherwise all share dest (like Data)."""
    dest = Path(dest)
    res = {"archives": {}, "files": 0, "bytes": 0, "missing": []}
    picked = []
    for n in names:
        p = pack.bsas.get(str(n).lower())
        if p is None:
            res["missing"].append(str(n))
        else:
            picked.append(p)
    for k, p in enumerate(picked):
        def prog(done, total, path, _k=k, _name=p.name):
            if progress:
                progress(_k, len(picked), f"{_name}: {path}" if path else _name, done, total)
        target = dest / Path(p.name).stem if separate else dest
        r = extract_bsa(p, target, prog, only, overwrite)
        res["archives"][p.name] = r
        res["files"] += r["files"]
        res["bytes"] += r["bytes"]
    return res


# =========================================================================
# 4. Plugin manager: switch plugins on and off, and see their masters
# =========================================================================
_FIXED = {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS}


def _active_users(pack: Pack, name: str) -> list[str]:
    low = name.lower()
    out = []
    for e, _src in pack.load_order():
        if e.startswith("#"):
            continue
        h = pack.plugins.get(e.lower())
        if h and h.name.lower() != low and any(m.lower() == low for m in h.masters):
            out.append(h.name)
    return out


def set_plugin_active(pack: Pack, name: str, active: bool, tx, force: bool = False) -> dict:
    """Switch a plugin on or off with a '#' at the start of its line in
    Skyrim_aoc.ccc (AE) or Plugins (SE); the rest of the file keeps its bytes.
    Turning off a plugin that active plugins use as a master is refused
    (refused=True and the users are listed) unless force=True."""
    if name.strip().lower() in _FIXED:
        raise XToolsError(f"{name} belongs to the game and always loads.",
                          f"{name} es del juego y siempre carga.")
    path = pack.list_path
    if not path or not path.exists():
        raise XToolsError("This pack has no load list.", "Este pack no tiene lista de carga.")
    raw = path.read_bytes()
    low = name.strip().lower()
    lines = [e for e in C.parse_ccc(raw).entries if e.lstrip("#").strip().lower() == low]
    if not lines:
        raise XToolsError(f"{name} is not in the load list.", f"{name} no está en la lista de carga.")
    bare = lines[0].lstrip("#").strip()
    out = {"name": bare, "active": active, "changed": False, "refused": False, "users": [],
           "missing_masters": []}
    if not active:
        out["users"] = _active_users(pack, bare)
        if out["users"] and not force:
            out["refused"] = True
            out["active"] = True
            return out
    else:
        h = pack.plugins.get(low)
        if h:
            on = {e.lower() for e, _ in pack.load_order() if not e.startswith("#")}
            out["missing_masters"] = [m for m in h.masters if m.lower() not in on]
    mapping = {}
    for e in lines:
        new = bare if active else "#" + bare
        if e != new:
            mapping[e] = new
    if not mapping:
        return out
    new_raw = C.edit_lines(raw, mapping)
    size = C.over_limit(pack, raw, new_raw)
    if size:
        from .errors import SkynxError
        raise SkynxError(*C.limit_message(size))
    tx.write_bytes(path, new_raw)
    pack.reload()
    out["changed"] = True
    return out


def cc_off_unneeded(pack: Pack, tx, the_patch: bool = False) -> list[str]:
    """Switch off ('#') the Creation Club entries no active plugin uses as a
    master: each one is a BSA the game keeps open. With the_patch, the
    unofficial Creation Club patch (which uses most of them as masters) goes
    off first. Returns the plugins switched off, in one edit of the list."""
    path = pack.list_path
    if not path or not path.exists():
        raise XToolsError("This pack has no load list.", "Este pack no tiene lista de carga.")
    raw = path.read_bytes()
    entries = C.parse_ccc(raw).entries
    on = [e.strip() for e in entries if not e.startswith("#")]
    off: list[str] = []
    if the_patch:
        off += [e for e in on if e.lower().startswith("unofficial skyrim creation club content patch")]
    changed = True
    while changed:
        changed = False
        live = [e for e in on if e not in off]
        needs = set()
        for e in live:
            h = pack.plugins.get(e.lower())
            if h:
                needs |= {m.lower() for m in h.masters if m.lower() != e.lower()}
        for e in live:
            if pack.is_cc(e) and e.lower() not in needs and e.lower() not in {f.lower() for f in _FIXED}:
                off.append(e)
                changed = True
    if not off:
        return []
    gone = {e.lower() for e in off}
    mapping = {e: "#" + e.strip() for e in entries if not e.startswith("#") and e.strip().lower() in gone}
    new_raw = C.edit_lines(raw, mapping)
    size = C.over_limit(pack, raw, new_raw)
    if size:
        from .errors import SkynxError
        raise SkynxError(*C.limit_message(size))
    tx.write_bytes(path, new_raw)
    pack.reload()
    return off


def masters_view(pack: Pack) -> list[dict]:
    """Every plugin in load order (then plugins in Data that the list doesn't
    name), with its masters and who uses it.

    where: "game" (console's own), "pack" (file in Data), "cc" (Creation Club
    entry, provided by the console) or "missing".
    """
    rows: list[dict] = []
    pos: dict[str, int] = {}
    active: dict[str, bool] = {}
    for e, src in pack.load_order():
        bare = e.lstrip("#").strip()
        low = bare.lower()
        if not bare or low in pos:
            continue
        pos[low] = len(rows)
        active[low] = not e.startswith("#")
        if src == "juego" or low in _FIXED:
            where = "game"
        elif low in pack.plugins:
            where = "pack"
        elif _is_cc(pack, bare) and pack.mode == "AE":
            where = "cc"
        else:
            where = "missing"
        rows.append({"name": pack.plugins[low].name if low in pack.plugins else bare,
                     "active": active[low], "listed": src == "lista", "source": src, "where": where,
                     "present": where != "missing", "masters": [], "used_by": [], "active_users": []})
    for low, h in sorted(pack.plugins.items()):
        if low not in pos:
            pos[low] = len(rows)
            active[low] = False
            rows.append({"name": h.name, "active": False, "listed": False, "source": "data",
                         "where": "pack", "present": True, "masters": [], "used_by": [], "active_users": []})
    for row in rows:
        h = pack.plugins.get(row["name"].lower())
        if not h:
            continue
        me = pos[row["name"].lower()]
        for m in h.masters:
            ml = m.lower()
            r = rows[pos[ml]] if ml in pos else None
            row["masters"].append({"name": m, "present": bool(r and r["present"]),
                                   "active": bool(r and r["active"]),
                                   "before": bool(r is not None and pos[ml] < me)})
            if r is not None:
                r["used_by"].append(h.name)
                if row["active"]:
                    r["active_users"].append(h.name)
    return rows
