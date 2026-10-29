"""Mods left compressed inside Data (some packs ship them like that, e.g.
Ashiro's list): take their plugins and BSAs out into Data, activate the plugins
the load list doesn't have yet, and move the archive to the project's trash."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path, PurePosixPath

from .errors import SkynxError

PLUGIN_EXT = (".esp", ".esm", ".esl")
ASSET_TOPS = {"meshes", "textures", "sound", "music", "scripts", "interface", "seq", "strings",
              "lodsettings", "grass", "shadersfx", "video", "dialogueviews"}


class ArchiveFixError(SkynxError):
    pass


def plan(pack, name: str) -> dict:
    """What extracting Data/<name> would put in Data."""
    from . import variants as VA
    from .intake import archive_type, list_names, rar_tool
    arc = pack.data_dir / name
    if not arc.is_file():
        raise ArchiveFixError(f"{name} isn't in Data anymore.", f"{name} ya no está en Data.")
    if archive_type(arc) not in ("zip", "7z") and not (archive_type(arc) == "rar" and rar_tool()):
        raise ArchiveFixError(f"I can't open {name}; extract it by hand.",
                              f"No puedo abrir {name}; extráelo a mano.")
    members = [m for m in list_names(arc) if not m.is_dir and not VA.is_junk(m.name)]
    vres = VA.choose([m.name for m in members], pack.mode)
    members = [m for m in members if not VA.skipped(m.name, vres["skip"])]
    take, loose = {}, []
    for m in members:
        p = PurePosixPath(m.name.replace("\\", "/"))
        ext = p.suffix.lower()
        if ext in PLUGIN_EXT or ext == ".bsa":
            low = p.name.lower()
            if low in take and take[low] != m.name:
                raise ArchiveFixError(f"{name} has two files called {p.name}; extract it by hand and pick one.",
                                      f"{name} trae dos archivos llamados {p.name}; extráelo a mano y elige uno.")
            take[low] = m.name
        elif any(part.lower() in ASSET_TOPS for part in p.parts[:-1]):
            loose.append(m.name)
    if not take:
        raise ArchiveFixError(f"{name} has no plugins or BSAs, only loose files: open it from Convert mods.",
                              f"{name} no trae plugins ni BSA, solo archivos sueltos: ábrelo desde Convertir mods.")
    files = sorted(take.values(), key=lambda s: PurePosixPath(s).name.lower())
    listed = {e.lower().lstrip("*#").strip() for e in pack.list_entries}
    plugins = [PurePosixPath(f).name for f in files if PurePosixPath(f).suffix.lower() in PLUGIN_EXT]
    return {"name": name, "files": files, "plugins": plugins,
            "bsas": [PurePosixPath(f).name for f in files if f.lower().endswith(".bsa")],
            "unlisted": [p for p in plugins if p.lower() not in listed],
            "loose": len(loose), "note": VA.note(vres)}


def apply(pack, name: str, title: str | None = None, detail: str = "") -> dict:
    """Extract Data/<name> as if it were added from Add mods (same rules: the
    edition's version folder, SE adaptations, BSAs without a plugin to the ini,
    .ccc limit) and move the archive to the trash, all as one undoable step.
    Plugins the list already names keep their place."""
    from .builder import add_mod
    pl = plan(pack, name)
    arc = pack.data_dir / name
    rep = add_mod(pack, arc, mod_id=Path(name).stem, title=title,
                  meta={"source": {"kind": "archive", "file": name, "from": "Data"}},
                  also=lambda tx: tx.trash(arc))
    return {"extracted": rep.added, "activated": rep.list_added, "notes": rep.notes,
            "history": rep.history, "loose": pl["loose"]}
