"""Behavior generation (FNIS / Nemesis mods) for a pack, outside Skyrim.

Mods with new animations (Flower Girls, SexLab...) don't bring the game's
behavior files: they bring a list (FNIS_<mod>_List.txt) or a Nemesis patch,
and a generator writes 0_master.hkx, defaultmale.hkx and the rest for the
whole pack. Tested on the user's PC (Oct 2026) against a working Switch port:

1. Nemesis runs on a work folder instead of Skyrim's Data: its nemesis.ini
   takes SkyrimDataDirectory=<folder>\\, and an empty SkyrimSE.exe next to
   that Data makes it treat the folder as Special Edition. It has to live in
   <folder>\\Nemesis_Engine. It has no command line: the person presses
   "Update Engine" and "Launch Nemesis Behavior Engine".
2. What it writes is 64-bit PC; havok.to_switch makes each file Switch-native
   (serde-hkx to XML, HavokBehaviorPostProcess --platformps4): identical,
   byte for byte, to the port's files.
3. The result goes into the pack as one more mod (GEN_ID), in one BSA listed
   in the ini after the others, so it wins over vanilla and other mods.

What each mod needs for this is kept when it's converted (capture): its
FNIS lists and the animations next to them, its own FNIS behavior files and
its Nemesis patch, all as the original PC files, in
<pack>/.skynx/behavior-sources/<mod id>/ (Data-relative paths).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from .errors import SkynxError
from .pack import Pack

SOURCES = (".skynx", "behavior-sources")
STATE = (".skynx", "behaviors.json")
WORK = (".skynx", "behaviors-work")
LOG = (".skynx", "behaviors-patchlog.txt")        # Nemesis' log of the last generation
GEN_ID = "SkyNX - Generated behaviors"
GEN_BSA = "SkyNXBehaviors.bsa"
NEMESIS_EXE = "Nemesis Unlimited Behavior Engine.exe"
DONE_MARK = "Behavior generation complete"

_LIST = re.compile(r"(^|\\)meshes\\actors\\.+\\animations\\(.+\\)?fnis_[^\\]+_list\.txt$")
_OWN_BEHAVIOR = re.compile(r"(^|\\)meshes\\actors\\.+\\behaviors\\fnis_[^\\]+_behavior\.hkx$")
_ANIMS = re.compile(r"(^|\\)meshes\\actors\\.+\\animations\\")


class BehaviorError(SkynxError):
    pass


# ------------------------------------------------------------------ capture
def capture(data: Path, extra: Path | None, dest: Path) -> int:
    """Copy what behavior generation needs from a mod's staged files (PC
    originals) to dest, keeping Data-relative paths. `extra` is the mod's own
    Nemesis_Engine folder when it has one. Returns how many files."""
    data = Path(data)
    files = {}
    for p in data.rglob("*"):
        if p.is_file():
            files[str(p.relative_to(data)).replace("/", "\\").lower()] = p
    want: dict[str, Path] = {}
    list_dirs = set()
    for rel, p in files.items():
        if _LIST.search(rel):
            want[rel] = p
            list_dirs.add(rel.rsplit("\\", 1)[0] + "\\")
        elif _OWN_BEHAVIOR.search(rel):
            want[rel] = p
    has_nemesis = bool(extra and Path(extra).is_dir() and any(Path(extra).rglob("*")))
    for rel, p in files.items():
        if not rel.endswith(".hkx") or not _ANIMS.search(rel):
            continue
        if has_nemesis or any(rel.startswith(d) for d in list_dirs):
            want[rel] = p
    n = 0
    for rel, p in want.items():
        out = Path(dest).joinpath(*p.relative_to(data).parts)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
        n += 1
    if has_nemesis:
        for p in Path(extra).rglob("*"):
            if p.is_file():
                out = Path(dest) / "Nemesis_Engine" / p.relative_to(extra)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, out)
                n += 1
    return n


def sources_dir(pack: Pack, mod_id: str | None = None) -> Path:
    base = Path(pack.root).joinpath(*SOURCES)
    return base / _safe(mod_id) if mod_id else base


def _safe(name: str) -> str:
    return "".join("_" if c in '<>:"/\\|?*' or ord(c) < 32 else c for c in str(name)).strip(" .") or "mod"


def store(pack: Pack, mod_id: str, src: Path) -> bool:
    """Keep a mod's captured sources in the pack (replacing older ones)."""
    src = Path(src)
    if not src.is_dir() or not any(p.is_file() for p in src.rglob("*")):
        return False
    dest = sources_dir(pack, mod_id)
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest)
    return True


def store_zip(pack: Pack, mod_id: str, zip_path: Path) -> bool:
    """The same from a Library copy, where the sources travel as a zip (a
    folder there would look like loose mod files)."""
    import zipfile
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        return False
    dest = sources_dir(pack, mod_id)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            parts = Path(info.filename).parts
            if info.is_dir() or any(x in ("..", "") for x in parts) or Path(info.filename).is_absolute():
                continue
            out = dest.joinpath(*parts)
            out.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as fi, out.open("wb") as fo:
                shutil.copyfileobj(fi, fo)
    return True


def make_zip(src: Path, zip_path: Path) -> None:
    import zipfile
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(Path(src).rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(src).as_posix())


# ------------------------------------------------------------------ what the pack has
def _excluded(pack: Pack) -> set[str]:
    try:
        from . import draft as DR
        d = DR.load(pack.root) or {}
        return set((d.get("excluded") or {}).keys())
    except Exception:  # noqa: BLE001
        return set()


def mods_with_sources(pack: Pack) -> list[dict]:
    """Mods of the pack (that go) with kept sources, in the order they were added."""
    from .builder import load_mods
    recs = load_mods(pack)
    out = []
    skip = _excluded(pack) | {GEN_ID}
    for mid, rec in recs.items():
        if mid in skip:
            continue
        d = sources_dir(pack, mid)
        if d.is_dir():
            files = [p for p in d.rglob("*") if p.is_file()]
            if files:
                lists = sum(1 for p in files if p.name.lower().startswith("fnis_") and p.suffix.lower() == ".txt")
                nem = (d / "Nemesis_Engine").is_dir()
                out.append({"id": mid, "dir": d, "files": len(files), "lists": lists, "nemesis": nem})
    return out


def inputs_hash(mods: list[dict]) -> str:
    h = hashlib.sha1()
    for m in mods:
        h.update(m["id"].encode("utf-8", "replace"))
        for p in sorted(Path(m["dir"]).rglob("*")):
            if p.is_file():
                st = p.stat()
                h.update(f"{p.relative_to(m['dir']).as_posix().lower()}|{st.st_size}".encode())
                if p.suffix.lower() == ".txt":
                    h.update(p.read_bytes())
    return h.hexdigest()


def load_state(pack: Pack) -> dict:
    f = Path(pack.root).joinpath(*STATE)
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    except (OSError, ValueError):
        return {}


def _save_state(pack: Pack, st: dict) -> None:
    f = Path(pack.root).joinpath(*STATE)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(st, indent=1, ensure_ascii=False), encoding="utf-8")


def status(pack: Pack, tools) -> dict:
    """{"needed", "state": "none"|"never"|"stale"|"ok", "mods", "generated", "tools"...}."""
    mods = mods_with_sources(pack)
    st = load_state(pack)
    from .builder import load_mods
    has_gen = GEN_ID in load_mods(pack)
    if not mods:
        state = "stale" if has_gen else "none"       # a generated set with nothing to generate from
    elif not st.get("hash") or not has_gen:
        state = "never"
    else:
        state = "ok" if st.get("hash") == inputs_hash(mods) else "stale"
    return {"needed": bool(mods) or has_gen, "state": state,
            "mods": [{k: v for k, v in m.items() if k != "dir"} for m in mods],
            "generated": st.get("generated"), "files": st.get("files"),
            "nemesis": bool(getattr(tools, "nemesis", None)), "havok": bool(getattr(tools, "can_havok", False))}


# ------------------------------------------------------------------ the work folder
def work_dir(pack: Pack) -> Path:
    return Path(pack.root).joinpath(*WORK)


def _snapshot(data: Path) -> dict:
    out = {}
    for p in data.rglob("*"):
        if p.is_file():
            rel = p.relative_to(data).as_posix()
            if rel.lower().startswith("nemesis_engine/"):
                continue
            st = p.stat()
            out[rel] = [st.st_size, st.st_mtime_ns]
    return out


def prepare(pack: Pack, tools) -> dict:
    """Make the work folder: Nemesis (a copy), every mod's sources in order,
    the empty SkyrimSE.exe and the nemesis.ini that points there."""
    if not getattr(tools, "nemesis", None):
        raise BehaviorError("Nemesis isn't in the tools folder (Tools\\Nemesis\\Nemesis_Engine).",
                            "Nemesis no está en la carpeta de herramientas (Tools\\Nemesis\\Nemesis_Engine).")
    mods = mods_with_sources(pack)
    if not mods:
        raise BehaviorError("No mod of this pack needs behaviors generated.",
                            "Ningún mod de este pack necesita generar comportamientos.")
    ws = work_dir(pack)
    if ws.exists():
        shutil.rmtree(ws)
    data = ws / "Data"
    data.mkdir(parents=True)
    (ws / "SkyrimSE.exe").write_bytes(b"")
    eng_src = Path(tools.nemesis)
    shutil.copytree(eng_src, data / "Nemesis_Engine", dirs_exist_ok=True)
    pkg = eng_src.parent
    if getattr(tools, "folder", None) is None or pkg.resolve() != Path(tools.folder).resolve():
        for item in pkg.iterdir():                  # the rest of Nemesis' download: meshes, scripts
            if item.is_dir() and item.name.lower() in ("meshes", "scripts"):
                shutil.copytree(item, data / item.name, dirs_exist_ok=True)
    eng = data / "Nemesis_Engine"
    for name in ("CriticalLog.txt", "UpdateLog.txt", "PatchLog.txt"):
        (eng / name).unlink(missing_ok=True)
    for sub in ("cache", "temp_behaviors"):
        if (eng / sub).exists():
            shutil.rmtree(eng / sub)
    ini = eng / "nemesis.ini"
    lines = ini.read_text(encoding="utf-8", errors="replace").splitlines() if ini.is_file() else []
    lines = [x for x in lines if not x.lower().startswith("skyrimdatadirectory=")]
    ini.write_text("\r\n".join([f"SkyrimDataDirectory={data}\\"] + lines) + "\r\n", encoding="utf-8")
    for m in mods:
        shutil.copytree(m["dir"], data, dirs_exist_ok=True)
    snap = _snapshot(data)
    info = {"started": time.time(), "hash": inputs_hash(mods), "mods": [m["id"] for m in mods],
            "snapshot": snap, "exe": str(eng / NEMESIS_EXE)}
    (ws / "work.json").write_text(json.dumps(info), encoding="utf-8")
    return {"work": str(ws), "exe": info["exe"], "mods": info["mods"],
            "patches": sorted({p.name for m in mods for p in (Path(m["dir"]) / "Nemesis_Engine" / "mod").glob("*")
                               if p.is_dir()})}


def launch(pack: Pack) -> subprocess.Popen:
    info = json.loads((work_dir(pack) / "work.json").read_text(encoding="utf-8"))
    exe = Path(info["exe"])
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = 0x00000008          # DETACHED_PROCESS: its own window, not ours
    return subprocess.Popen([str(exe)], cwd=str(exe.parent), **kw)


def nemesis_log(pack: Pack) -> dict:
    """What Nemesis' PatchLog says: done, errors."""
    f = work_dir(pack) / "Data" / "Nemesis_Engine" / "PatchLog.txt"
    if not f.is_file():
        return {"exists": False, "done": False, "errors": []}
    txt = f.read_text(encoding="utf-8", errors="replace")
    errs = [x.strip() for x in txt.splitlines() if re.search(r"\berror\b|failed to generate", x, re.I)]
    return {"exists": True, "done": DONE_MARK.lower() in txt.lower(), "errors": errs[:20]}


# ------------------------------------------------------------------ collect and install
def changed_files(pack: Pack) -> list[str]:
    ws = work_dir(pack)
    info = json.loads((ws / "work.json").read_text(encoding="utf-8"))
    before = info["snapshot"]
    now = _snapshot(ws / "Data")
    out = []
    for rel, st in now.items():
        low = rel.lower()
        name = low.rsplit("/", 1)[-1]
        if name.startswith("nemesis_") and name.endswith(".xml"):
            continue                                 # Nemesis' own caches
        if before.get(rel) != st:
            out.append(rel)
    return sorted(out)


def collect(pack: Pack, tools, progress=None) -> dict:
    """Make the generated files Switch-native and put them in the pack as one
    mod (replacing the previous set). Undoable like any added mod."""
    from . import havok as HV
    from .bsa import write_bsa
    from .builder import add_mod, load_mods, remove_mod
    tick = progress or (lambda *a, **k: None)
    log = nemesis_log(pack)
    if not log["done"]:
        raise BehaviorError("Nemesis didn't finish generating (its log has no \"Behavior generation complete\"). "
                            "Open it again and press Update Engine and Launch.",
                            "Nemesis no terminó de generar (su registro no dice \"Behavior generation complete\"). "
                            "Ábrelo otra vez y oprime Update Engine y Launch.")
    if not getattr(tools, "can_havok", False):
        raise BehaviorError("HavokBehaviorPostProcess.exe and hkxc.exe are needed to make them Switch files.",
                            "Hacen falta HavokBehaviorPostProcess.exe y hkxc.exe para pasarlos a Switch.")
    ws = work_dir(pack)
    data = ws / "Data"
    rels = changed_files(pack)
    gen = [r for r in rels if r.lower().endswith((".hkx", ".txt", ".pex"))]
    if not gen:
        raise BehaviorError("Nemesis didn't write any file.", "Nemesis no escribió ningún archivo.")
    out = ws / "out"
    if out.exists():
        shutil.rmtree(out)
    staged = ws / "stage"
    if staged.exists():
        shutil.rmtree(staged)
    tmp = ws / "tmp"
    pairs = []
    for i, rel in enumerate(gen):
        tick(rel.rsplit("/", 1)[-1], i + 1, len(gen))
        raw = (data / rel).read_bytes()
        if rel.lower().endswith(".hkx"):
            raw = HV.to_switch(raw, tools, tmp, rel.rsplit("/", 1)[-1])
        dest = staged.joinpath(*rel.lower().split("/"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        pairs.append((rel.lower().replace("/", "\\"), dest))
    out.mkdir(parents=True)
    write_bsa(pairs, out / GEN_BSA)
    tick("BSA")
    if GEN_ID in load_mods(pack):
        remove_mod(pack, GEN_ID)
        pack = Pack.open(pack.root)
    key = _ini_key(pack)
    rep = add_mod(pack, out, mod_id=GEN_ID, ini_keys={GEN_BSA: key},
                  meta={"generated": {"by": "Nemesis", "date": time.strftime("%Y-%m-%d %H:%M:%S")},
                        "source": {"kind": "generated", "name": "Nemesis"}})
    info = json.loads((ws / "work.json").read_text(encoding="utf-8"))
    st = {"hash": info["hash"], "mods": info["mods"], "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
          "files": len(pairs)}
    _save_state(pack, st)
    log_src = data / "Nemesis_Engine" / "PatchLog.txt"
    if log_src.is_file():
        shutil.copy2(log_src, Path(pack.root).joinpath(*LOG))
    shutil.rmtree(ws, ignore_errors=True)           # Nemesis' copy and caches: hundreds of MB
    return {"files": len(pairs), "hkx": sum(1 for r in gen if r.lower().endswith(".hkx")),
            "mod_id": rep.mod_id or GEN_ID, "errors": log["errors"]}


def _ini_key(pack: Pack) -> str:
    """The archive list with more room (like the "ini1" packing)."""
    from .ini import ARCHIVE_LIST_LIMIT
    best = None
    for key in ("sResourceArchiveList2", "sResourceArchiveList"):
        paths = pack.inis_for_key(key)
        if not paths:
            continue
        worst = max(len(", ".join(ini.archive_list(key) + [GEN_BSA])) for ini in pack.inis if ini.path in paths)
        if worst <= ARCHIVE_LIST_LIMIT and (best is None or worst < best[1]):
            best = (key, worst)
    if best is None:
        raise BehaviorError("No ini list has room for the generated behaviors' BSA.",
                            "Ninguna lista del ini tiene espacio para el BSA de los comportamientos generados.")
    return best[0]
