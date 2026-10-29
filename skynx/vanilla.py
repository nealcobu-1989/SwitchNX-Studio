"""The game list: every file the console's game has, and what the game itself asks for.

The user puts the game's own files in a folder of their choice: the BSAs of
romfs\\Data (Skyrim - *.bsa, the Creation Club cc*.bsa) and its plugins
(Skyrim.esm, Update.esm, the DLC and CC .esm/.esl). The setting is passed to
the engine as a path (the engine never reads settings).

From them the app builds the game list, saved as JSON in `cache_dir`:

* files: every path inside those BSAs, plus loose files in subfolders,
  lowercase with backslashes ("meshes\\clutter\\bucket01.nif");
* refs: what the game's own content asks for: models and scripts of the
  game's plugins, textures named by the game's meshes. Some of those don't
  exist in the game either (vanilla races name upperbodyhumanmale.egt, which
  no BSA has), so a mod that copies such a record isn't missing anything.

The list is kept per BSA and per plugin. A file whose size and time haven't
changed is never read again, and one that is no longer in the folder stays in
the list ("kept"): the BSAs are only needed once, to build it. Copy a file
back (a game update) and it is read again; `forget_kept` drops the kept ones.
The game's plugins are still needed in the folder by xEdit.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from .bsa import read_bsa

INDEX_VERSION = 2
CACHE_NAME = "vanilla-index-{key}.json"
PLUGIN_EXT = (".esm", ".esl", ".esp")
# The BSAs every console copy has (the Switch has no Textures4..8). The list
# warns when one of these was never read, since its files would look missing.
CORE_BSAS = ("Skyrim - Animations.bsa", "Skyrim - Interface.bsa", "Skyrim - Meshes0.bsa",
             "Skyrim - Meshes1.bsa", "Skyrim - Misc.bsa", "Skyrim - Sounds.bsa",
             "Skyrim - Textures0.bsa")
_MEMO: dict[str, tuple[list, dict]] = {}


def bsa_folder(folder: Path) -> Path:
    """The folder that holds the BSAs: the one given, or its Data / romfs\\Data."""
    folder = Path(folder)
    if any(p.suffix.lower() == ".bsa" for p in _files(folder)):
        return folder
    for sub in ("Data", "romfs/Data"):
        cand = folder / sub
        if cand.is_dir() and any(p.suffix.lower() == ".bsa" for p in _files(cand)):
            return cand
    return folder


def _files(folder: Path) -> list[Path]:
    try:
        return [p for p in folder.iterdir() if p.is_file()]
    except OSError:
        return []


def signature(folder: Path) -> list:
    """[name, size, mtime] for every top-level entry (files and folders)."""
    folder = bsa_folder(folder)
    out = []
    try:
        entries = sorted(folder.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return []
    for p in entries:
        if p.name.lower().startswith("vanilla-index-"):
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        out.append([p.name, st.st_size if p.is_file() else -1, int(st.st_mtime)])
    return out


def _stat(p: Path) -> list:
    st = p.stat()
    return [st.st_size, int(st.st_mtime)]


def _read_bsa_entry(p: Path) -> dict:
    arc = read_bsa(p)
    files = sorted({e.path.lower().replace("/", "\\") for e in arc.entries})
    tex: list[str] = []
    if any(f.endswith(".nif") for f in files):
        from .requirements import nif_textures
        refs, _bad = nif_textures(arc)
        tex = sorted({t for _n, t in refs})
    return {"stat": _stat(p), "files": files, "tex_refs": tex}


def _read_plugin_entry(p: Path) -> dict:
    from . import records as REC
    s = REC.scan_plugin(p)
    return {"stat": _stat(p), "models": sorted(s.models),
            "scripts": sorted(f"scripts\\{x.lower()}.pex" for x in s.scripts)}


def _loose(folder: Path) -> list[str]:
    files: set[str] = set()
    if not folder.is_dir():
        return []
    for dirpath, dirnames, fnames in os.walk(folder):
        rel = Path(dirpath).relative_to(folder)
        if rel == Path("."):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            continue   # top-level files are the BSAs and plugins themselves
        for f in fnames:
            files.add(str(rel / f).replace("/", "\\").lower())
    return sorted(files)


def _cache_path(folder: Path, cache_dir: Path) -> Path:
    key = hashlib.sha1(str(Path(folder).resolve()).lower().encode("utf-8")).hexdigest()[:12]
    return Path(cache_dir) / CACHE_NAME.format(key=key)


def _saved(cp: Path | None) -> dict:
    if not cp or not cp.exists():
        return {}
    try:
        data = json.loads(cp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if data.get("version") == INDEX_VERSION else {}


def _write(cp: Path | None, data: dict) -> None:
    if not cp:
        return
    try:
        cp.parent.mkdir(parents=True, exist_ok=True)
        tmp = cp.with_name(cp.name + ".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, cp)
    except OSError:
        pass   # read-only place: keep it in memory only


def build_index(folder: Path, saved: dict | None = None, progress=None) -> dict:
    """{"version", "folder", "signature", "built",
        "bsas": {name: {"stat", "files", "tex_refs", "kept"?}},
        "plugins": {name: {"stat", "models", "scripts", "kept"?}},
        "loose": [paths], "errors": {name: message}}.
    Entries of `saved` whose file hasn't changed are reused, and the ones whose
    file is gone are kept."""
    say = progress or (lambda *a, **k: None)
    folder = bsa_folder(folder)
    saved = saved or {}
    old_b, old_p = saved.get("bsas", {}), saved.get("plugins", {})
    bsas: dict[str, dict] = {}
    plugins: dict[str, dict] = {}
    errors: dict[str, str] = {}
    present = sorted(_files(folder), key=lambda x: x.name.lower())
    work = [p for p in present if p.suffix.lower() == ".bsa" or p.suffix.lower() in PLUGIN_EXT]
    changed = False
    for i, p in enumerate(work):
        is_bsa = p.suffix.lower() == ".bsa"
        old, dest = (old_b, bsas) if is_bsa else (old_p, plugins)
        try:
            st = _stat(p)
        except OSError as e:
            errors[p.name] = str(e)
            continue
        prev = old.get(p.name)
        if prev and prev.get("stat") == st:
            dest[p.name] = {k: v for k, v in prev.items() if k != "kept"}
            continue
        say(p.name, i, len(work))
        try:
            dest[p.name] = _read_bsa_entry(p) if is_bsa else _read_plugin_entry(p)
            changed = True
        except Exception as e:  # noqa: BLE001
            errors[p.name] = str(e)
    for old, dest in ((old_b, bsas), (old_p, plugins)):
        for name, prev in old.items():
            if name not in dest:
                dest[name] = {**prev, "kept": True}
    loose = _loose(folder)
    changed = changed or loose != saved.get("loose") or errors != saved.get("errors", {})
    return {"version": INDEX_VERSION, "folder": str(folder), "signature": signature(folder),
            "built": time.time() if changed or not saved.get("built") else saved["built"],
            "bsas": bsas, "plugins": plugins, "loose": loose, "errors": errors}


def load(folder: Path, cache_dir: Path | None = None, progress=None) -> dict:
    """The game list as a dict (see build_index), up to date with the folder."""
    folder = bsa_folder(Path(folder))
    sig = signature(folder)
    memo = _MEMO.get(str(folder))
    if memo and memo[0] == sig:
        return memo[1]
    cp = _cache_path(folder, cache_dir) if cache_dir else None
    saved = _saved(cp)
    if saved and saved.get("signature") == sig:
        data = saved
    else:
        data = build_index(folder, saved, progress)
        _write(cp, data)
    _MEMO[str(folder)] = (sig, data)
    return data


def index(folder: Path, cache_dir: Path | None = None, progress=None) -> set[str]:
    """Every file path the game has (lowercase, backslashes). Empty set when
    nothing was ever readable."""
    data = load(folder, cache_dir, progress)
    out: set[str] = set(data.get("loose", []))
    for e in data.get("bsas", {}).values():
        out.update(e.get("files", []))
    return out


def ini_files(folder: Path, cache_dir: Path | None = None) -> set[str]:
    """The files of the game's own BSAs that load from the ini (Skyrim - *.bsa).
    The Creation Club BSAs load by their plugins' names, like a mod's."""
    data = load(folder, cache_dir)
    out: set[str] = set()
    for name, e in data.get("bsas", {}).items():
        if name.lower().startswith("skyrim - "):
            out.update(e.get("files", []))
    return out


def game_refs(folder: Path, cache_dir: Path | None = None) -> set[str]:
    """Paths the game's own content asks for: models and scripts of its plugins
    and textures of its meshes, whether or not they exist."""
    data = load(folder, cache_dir)
    out: set[str] = set()
    for e in data.get("plugins", {}).values():
        out.update(e.get("models", []))
        out.update(e.get("scripts", []))
    for e in data.get("bsas", {}).values():
        out.update(e.get("tex_refs", []))
    return out


def summary(folder: Path | None, cache_dir: Path | None = None) -> dict:
    """For Settings and the Doctor: {"files", "bsas", "plugins", "kept": [names],
    "missing_core": [names], "built", "errors"}. Empty when there's no list."""
    if not folder or status(folder, cache_dir) != "ok":
        return {}
    data = load(Path(folder), cache_dir)
    names = {n.lower() for n in data.get("bsas", {})}
    kept = sorted(n for group in ("bsas", "plugins")
                  for n, e in data.get(group, {}).items() if e.get("kept"))
    return {"files": len(index(Path(folder), cache_dir)), "bsas": len(data.get("bsas", {})),
            "plugins": len(data.get("plugins", {})), "kept": kept,
            "missing_core": [c for c in CORE_BSAS if c.lower() not in names],
            "built": data.get("built"), "errors": data.get("errors", {})}


def forget_kept(folder: Path, cache_dir: Path | None = None) -> int:
    """Drop the BSAs and plugins that are no longer in the folder. Returns how many."""
    folder = bsa_folder(Path(folder))
    data = load(folder, cache_dir)
    n = 0
    for group in ("bsas", "plugins"):
        for name in [k for k, e in data.get(group, {}).items() if e.get("kept")]:
            del data[group][name]
            n += 1
    if n:
        data["built"] = time.time()
        _write(_cache_path(folder, cache_dir) if cache_dir else None, data)
        _MEMO.pop(str(folder), None)
    return n


def status(folder: Path | None, cache_dir: Path | None = None) -> str:
    """'unset', 'missing' (path doesn't exist), 'empty' (no BSA in it and no
    saved list) or 'ok'."""
    if not folder:
        return "unset"
    folder = Path(folder)
    if folder.is_dir() and any(p.suffix.lower() == ".bsa" for p in _files(bsa_folder(folder))):
        return "ok"
    if cache_dir and _saved(_cache_path(bsa_folder(folder), cache_dir)).get("bsas"):
        return "ok"   # the BSAs were deleted after the list was built
    if not folder.is_dir():
        return "missing"
    return "empty"
